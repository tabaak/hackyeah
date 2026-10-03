"""Throwaway Postgres (pgvector) in Docker with the parts of Supabase the migrations rely on.

Every test runs in a transaction that is rolled back, so tests are independent and leave nothing behind.
Skipped when Docker or the image is unavailable (scripts/test-all.sh pulls the image first).
"""
import json
import os
import shutil
import subprocess
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from tests.conftest import REPO

IMAGE = os.getenv("PG_TEST_IMAGE", "pgvector/pgvector:pg17")
STUB = Path(__file__).with_name("supabase_stub.sql")
MIGRATIONS = sorted((REPO / "supabase" / "migrations").glob("*.sql"))


def _docker(*args):
    return subprocess.run(["docker", *args], capture_output=True, text=True)


@pytest.fixture(scope="session")
def postgres():
    if not shutil.which("docker"):
        pytest.skip("Docker is not installed")
    if _docker("info").returncode:
        pytest.skip("Docker daemon is not running")
    if _docker("image", "inspect", IMAGE).returncode:
        pytest.skip(f"Docker image {IMAGE} is missing: docker pull {IMAGE}")
    name = f"palladion-test-pg-{uuid.uuid4().hex[:8]}"
    started = _docker("run", "-d", "--rm", "--name", name, "-e", "POSTGRES_PASSWORD=test", "-p", "127.0.0.1::5432", IMAGE)
    if started.returncode:
        pytest.fail(f"docker run failed: {started.stderr}")
    try:
        port = _docker("port", name, "5432/tcp").stdout.split()[0].rsplit(":", 1)[1]
        dsn = f"postgresql://postgres:test@127.0.0.1:{port}/postgres"
        deadline = time.monotonic() + 60
        while True:
            try:
                with psycopg.connect(dsn, connect_timeout=2) as conn:
                    conn.execute("select 1")
                break
            except psycopg.OperationalError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.5)
        yield dsn
    finally:
        _docker("stop", "-t", "2", name)


@pytest.fixture(scope="session")
def migrated(postgres):
    with psycopg.connect(postgres, autocommit=True) as conn:
        conn.execute(STUB.read_text())
        for migration in MIGRATIONS:
            conn.execute(migration.read_text())
    return postgres


class Db:
    """Thin helpers over one connection; everything happens in the test's transaction."""

    def __init__(self, conn):
        self.conn = conn

    def run(self, query, *params):
        return self.conn.execute(query, params or None).rowcount

    def rows(self, query, *params):
        return self.conn.execute(query, params or None).fetchall()

    def column(self, query, *params):
        return [r[0] for r in self.rows(query, *params)]

    def value(self, query, *params):
        row = self.conn.execute(query, params or None).fetchone()
        return row[0] if row else None

    def fails(self, query, *params):
        """Run in a savepoint; return the database error (or None if it succeeded)."""
        try:
            with self.conn.transaction():
                self.conn.execute(query, params or None)
        except psycopg.Error as error:
            return error
        return None

    @contextmanager
    def role(self, role, user_id=None):
        """Act as a Supabase role (and, for `authenticated`, as a user), the way PostgREST runs a request."""
        claims = {"role": role} | ({"sub": str(user_id)} if user_id else {})
        self.conn.execute(sql.SQL("set local role {}").format(sql.Identifier(role)))
        self.conn.execute("select set_config('request.jwt.claims', %s, true), set_config('request.jwt.claim.sub', %s, true)",
                          (json.dumps(claims), str(user_id or "")))
        try:
            yield self
        finally:
            if self.conn.info.transaction_status == TransactionStatus.INTRANS:
                self.conn.execute("reset role")
                self.conn.execute("select set_config('request.jwt.claims', '', true), set_config('request.jwt.claim.sub', '', true)")

    def as_user(self, user_id):
        return self.role("authenticated", user_id)

    # --- seed data (as the migration owner, i.e. like the service role) ---

    def signup(self, email, provider="google", full_name="Anna Nowak", organization=None):
        """Create an auth user the way GoTrue does; the sign-up trigger provisions org + profile."""
        meta = {"full_name": full_name} | ({"organization": organization} if organization else {})
        with self.role("supabase_auth_admin"):
            user_id = self.value("insert into auth.users (email, raw_app_meta_data, raw_user_meta_data) "
                                 "values (%s, %s, %s) returning id", email, Jsonb({"provider": provider}), Jsonb(meta))
        return user_id, self.value("select organization_id from public.profiles where user_id = %s", user_id)

    def invite(self, user_id, org_id, role="analyst"):
        self.run("update public.profiles set organization_id = %s, role = %s where user_id = %s", org_id, role, user_id)

    def company(self, org_id, name="Kestrel Bank", sector="Banking"):
        return self.value("insert into public.companies (organization_id, name, sector, country) "
                          "values (%s, %s, %s, 'Poland') returning id", org_id, name, sector)

    def document(self, company_id, classification="internal", status="ready"):
        return self.value("insert into public.documents (company_id, name, size, storage_path, classification, status) "
                          "values (%s, %s, 10, %s, %s, %s) returning id",
                          company_id, f"{classification}.txt", f"test/{uuid.uuid4()}", classification, status)

    def chunk(self, document_id, embedding=None, index=0):
        return self.value(
            "insert into public.document_chunks (organization_id, document_id, chunk_index, content, classification, embedding) "
            "select organization_id, id, %s, 'chunk of ' || name, classification, %s::extensions.vector "
            "from public.documents where id = %s returning id", index, embedding, document_id)

    def cluster(self, company_id):
        return self.value("insert into public.clusters (company_id) values (%s) returning id", company_id)

    def mention(self, company_id, external_id=None, organization_id=None, cluster_id=None):
        return self.value("insert into public.mentions (company_id, organization_id, cluster_id, platform, external_id, text, published_at) "
                          "values (%s, %s, %s, 'news', %s, 'Kestrel Bank froze all withdrawals', now()) returning id",
                          company_id, organization_id, cluster_id, external_id or str(uuid.uuid4()))

    def response(self, mention_id, draft="Withdrawals work normally.", draft_hash="hash-1"):
        self.run("insert into public.mention_responses (mention_id, draft, draft_hash) values (%s, %s, %s)",
                 mention_id, draft, draft_hash)

    def approval(self, mention_id, status="pending", required_role="analyst"):
        return self.value("insert into public.approvals (mention_id, payload_hash, draft_version, required_role, status) "
                          "values (%s, 'hash-1', 1, %s, %s) returning id", mention_id, required_role, status)

    def notification(self, user_id, org_id, mention_id=None):
        return self.value("insert into public.notifications (organization_id, user_id, mention_id, kind, title, severity) "
                          "values (%s, %s, %s, 'critical_mention', 'Bank run rumour', 'high') returning id",
                          org_id, user_id, mention_id)


@pytest.fixture
def db(migrated):
    conn = psycopg.connect(migrated)
    try:
        yield Db(conn)
    finally:
        conn.rollback()
        conn.close()
