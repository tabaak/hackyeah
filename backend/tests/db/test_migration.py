"""supabase/migrations against a real Postgres: Google-only sign-up, the access-token hook (and that the API
accepts its claims), tenancy via RLS, restricted documents, org propagation, approval invalidation,
vector search and cascades. Each test runs in its own rolled-back transaction."""
import uuid

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

from tests.conftest import API, bearer, hs256

pytestmark = pytest.mark.db
PUBLIC_TABLES = ["organizations", "profiles", "companies", "documents", "document_chunks", "clusters", "mentions",
                 "mention_responses", "approvals", "outbox", "notifications"]


def vec(*hot, dim=1536):
    v = [0.0] * dim
    for i in hot:
        v[i] = 1.0
    return "[" + ",".join(map(str, v)) + "]"


def test_migrations_apply(db):
    tables = db.column("select table_name from information_schema.tables "
                       "where table_schema = 'public' and table_type = 'BASE TABLE' order by 1")
    assert tables == sorted(PUBLIC_TABLES)
    assert db.value("select count(*) from pg_tables where schemaname = 'public' and not rowsecurity") == 0


# --- sign-up ----------------------------------------------------------------------------------------

def test_google_signup_provisions_org_and_analyst_profile(db):
    user, org = db.signup("anna@kestrel.example", full_name="Anna Nowak", organization="Kestrel Bank")
    assert db.rows("select name, email, role from public.profiles where user_id = %s", user) == \
        [("Anna Nowak", "anna@kestrel.example", "analyst")]
    assert db.value("select name from public.organizations where id = %s", org) == "Kestrel Bank"


def test_org_name_defaults_to_email_domain(db):
    _, org = db.signup("jan@aegis.example")
    assert db.value("select name from public.organizations where id = %s", org) == "aegis.example"


def test_every_signup_gets_its_own_org(db):
    _, org_a = db.signup("a@gmail.com")
    _, org_b = db.signup("b@gmail.com")
    assert org_a != org_b  # sharing an org needs an explicit invite


@pytest.mark.parametrize("provider", ["email", "github", None])
def test_non_google_signup_is_refused(db, provider):
    with db.role("supabase_auth_admin"):
        error = db.fails("insert into auth.users (email, raw_app_meta_data) values (%s, %s)",
                         "eve@evil.example", Jsonb({"provider": provider}))
    assert isinstance(error, psycopg.errors.RaiseException) and "Only Google sign-in is allowed" in str(error)
    assert db.value("select count(*) from public.profiles where email = 'eve@evil.example'") == 0


# --- access-token hook ------------------------------------------------------------------------------

def run_hook(db, user_id, claims=None):
    claims = claims or {"sub": str(user_id), "aud": "authenticated", "role": "authenticated"}
    with db.role("supabase_auth_admin"):
        return db.value("select public.custom_access_token_hook(%s)", Jsonb({"user_id": str(user_id), "claims": claims}))


def test_token_hook_adds_role_and_org(db):
    user, org = db.signup("anna@kestrel.example")
    out = run_hook(db, user)
    assert out["user_id"] == str(user)
    assert out["claims"] == {"sub": str(user), "aud": "authenticated", "role": "authenticated",
                             "user_role": "analyst", "organization_id": str(org)}


def test_token_hook_follows_role_changes(db):
    user, org = db.signup("cora@kestrel.example")
    db.invite(user, org, role="compliance")
    assert run_hook(db, user)["claims"]["user_role"] == "compliance"


def test_token_hook_leaves_unknown_users_unchanged(db):
    stranger = uuid.uuid4()
    claims = {"sub": str(stranger), "aud": "authenticated"}
    assert run_hook(db, stranger, claims)["claims"] == claims


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_token_hook_is_not_callable_by_clients(db, role):
    user, _ = db.signup("anna@kestrel.example")
    with db.role(role, user if role == "authenticated" else None):
        error = db.fails("select public.custom_access_token_hook(%s)", Jsonb({"user_id": str(user), "claims": {}}))
    assert isinstance(error, psycopg.errors.InsufficientPrivilege)


def test_api_accepts_the_claims_the_hook_produces(db, client):
    user, _ = db.signup("anna@kestrel.example", full_name="Anna Nowak")
    claims = run_hook(db, user, {"sub": str(user), "aud": "authenticated", "role": "authenticated"})["claims"]
    token = hs256(**claims, user_metadata={"full_name": "Anna Nowak"}, email="anna@kestrel.example")
    r = client.get(f"{API}/me", headers=bearer(token))
    assert r.status_code == 200 and r.json() == {"name": "Anna Nowak", "email": "anna@kestrel.example", "role": "analyst"}


def test_api_rejects_tokens_of_unprovisioned_users(db, client):
    stranger = uuid.uuid4()
    claims = run_hook(db, stranger, {"sub": str(stranger), "aud": "authenticated"})["claims"]
    no_profile = {"user_role": None, "organization_id": None} | claims
    r = client.get(f"{API}/me", headers=bearer(hs256(**no_profile)))
    assert r.status_code == 403 and r.json()["detail"] == "User profile is not provisioned"


# --- tenancy ----------------------------------------------------------------------------------------

@pytest.fixture
def two_orgs(db):
    a, org_a = db.signup("anna@kestrel.example")
    b, org_b = db.signup("ben@aegis.example")
    ca, cb = db.company(org_a, "Kestrel Bank"), db.company(org_b, "Aegis Works", sector="Defence")
    return {"a": a, "b": b, "org_a": org_a, "org_b": org_b, "company_a": ca, "company_b": cb}


def test_members_see_only_their_organization(db, two_orgs):
    db.mention(two_orgs["company_a"])
    db.mention(two_orgs["company_b"])
    with db.as_user(two_orgs["a"]):
        assert db.column("select name from public.companies") == ["Kestrel Bank"]
        assert db.column("select id from public.organizations") == [two_orgs["org_a"]]
        assert db.column("select email from public.profiles") == ["anna@kestrel.example"]
        assert db.column("select company_id from public.mentions") == [two_orgs["company_a"]]


def test_members_cannot_write_into_other_orgs(db, two_orgs):
    with db.as_user(two_orgs["a"]):
        assert db.value("insert into public.companies (organization_id, name, sector, country) "
                        "values (%s, 'Own', 'Banking', 'Poland') returning id", two_orgs["org_a"])
        error = db.fails("insert into public.companies (organization_id, name, sector, country) "
                         "values (%s, 'Planted', 'Banking', 'Poland')", two_orgs["org_b"])
        assert isinstance(error, psycopg.errors.InsufficientPrivilege)
        assert db.run("update public.companies set name = 'Hijacked' where id = %s", two_orgs["company_b"]) == 0
        assert db.run("delete from public.companies where id = %s", two_orgs["company_b"]) == 0
    assert db.value("select name from public.companies where id = %s", two_orgs["company_b"]) == "Aegis Works"


def test_anonymous_clients_see_nothing(db, two_orgs):
    document = db.document(two_orgs["company_a"])
    db.chunk(document)
    mention = db.mention(two_orgs["company_a"])
    db.notification(two_orgs["a"], two_orgs["org_a"], mention)
    with db.role("anon"):
        for table in PUBLIC_TABLES:
            query = sql.SQL("select count(*) from public.{}").format(sql.Identifier(table))
            assert db.conn.execute(query).fetchone()[0] == 0, table


def test_chunks_are_service_role_only(db, two_orgs):
    db.chunk(db.document(two_orgs["company_a"]))
    with db.as_user(two_orgs["a"]):
        assert db.value("select count(*) from public.document_chunks") == 0
    with db.role("service_role"):
        assert db.value("select count(*) from public.document_chunks") == 1


# --- documents --------------------------------------------------------------------------------------

@pytest.fixture
def library(db, two_orgs):
    for classification in ("public", "internal", "confidential", "restricted"):
        db.document(two_orgs["company_a"], classification)
    cora, _ = db.signup("cora@kestrel.example")
    db.invite(cora, two_orgs["org_a"], role="compliance")
    return two_orgs | {"compliance": cora}


def test_restricted_documents_are_compliance_only(db, library):
    with db.as_user(library["a"]):
        assert set(db.column("select classification from public.documents")) == {"public", "internal", "confidential"}
    with db.as_user(library["compliance"]):
        assert set(db.column("select classification from public.documents")) == \
            {"public", "internal", "confidential", "restricted"}


def test_clients_cannot_insert_documents(db, library):
    with db.as_user(library["a"]):
        error = db.fails("insert into public.documents (company_id, name, size, storage_path, classification) "
                         "values (%s, 'x.txt', 1, 'x', 'public')", library["company_a"])
    assert isinstance(error, psycopg.errors.InsufficientPrivilege)


def test_reclassifying_a_document_reclassifies_its_chunks(db, two_orgs):
    document = db.document(two_orgs["company_a"], "internal")
    db.chunk(document, index=0)
    db.chunk(document, index=1)
    db.run("update public.documents set classification = 'confidential' where id = %s", document)
    assert db.column("select distinct classification from public.document_chunks where document_id = %s", document) == \
        ["confidential"]


# --- organization propagation -----------------------------------------------------------------------

def test_child_rows_take_the_org_of_their_company(db, two_orgs):
    spoofed = db.mention(two_orgs["company_a"], organization_id=two_orgs["org_b"])
    assert db.value("select organization_id from public.mentions where id = %s", spoofed) == two_orgs["org_a"]
    document = db.document(two_orgs["company_a"])
    assert db.value("select organization_id from public.documents where id = %s", document) == two_orgs["org_a"]
    cluster = db.cluster(two_orgs["company_a"])
    assert db.value("select organization_id from public.clusters where id = %s", cluster) == two_orgs["org_a"]


def test_child_rows_need_an_existing_company(db):
    error = db.fails("insert into public.mentions (company_id, platform, external_id, text, published_at) "
                     "values (%s, 'news', 'x', 't', now())", uuid.uuid4())
    assert isinstance(error, psycopg.errors.RaiseException) and "not found" in str(error)


def test_responses_and_approvals_take_the_org_of_their_mention(db, two_orgs):
    mention = db.mention(two_orgs["company_a"])
    db.response(mention)
    approval = db.approval(mention)
    assert db.value("select organization_id from public.mention_responses where mention_id = %s", mention) == two_orgs["org_a"]
    assert db.value("select organization_id from public.approvals where id = %s", approval) == two_orgs["org_a"]


# --- mentions ---------------------------------------------------------------------------------------

def test_members_update_status_of_their_own_mentions_only(db, two_orgs):
    own, other = db.mention(two_orgs["company_a"]), db.mention(two_orgs["company_b"])
    with db.as_user(two_orgs["a"]):
        assert db.run("update public.mentions set status = 'dismissed' where id = %s", own) == 1
        assert db.run("update public.mentions set status = 'dismissed' where id = %s", other) == 0
    assert db.value("select status from public.mentions where id = %s", other) == "new"


@pytest.mark.xfail(strict=True, reason=(
    "Policy 'org members update mention status' allows updating every column, so any member can rewrite "
    "verdict/severity/text straight through Supabase (bypassing the API). Fix: revoke update on public.mentions "
    "from authenticated; grant update (status) on public.mentions to authenticated."))
def test_members_cannot_rewrite_ai_verdicts(db, two_orgs):
    mention = db.mention(two_orgs["company_a"])
    with db.as_user(two_orgs["a"]):
        error = db.fails("update public.mentions set verdict = 'supported_by_documents', severity = 'low' where id = %s", mention)
    assert isinstance(error, psycopg.errors.InsufficientPrivilege)


@pytest.mark.parametrize("column,value", [("platform", "instagram"), ("severity", "critical"), ("status", "archived"),
                                          ("verdict", "fake")])
def test_mention_checks(db, two_orgs, column, value):
    mention = db.mention(two_orgs["company_a"])
    error = db.fails(sql.SQL("update public.mentions set {} = %s where id = %s").format(sql.Identifier(column)),
                     value, mention)
    assert isinstance(error, psycopg.errors.CheckViolation)


def test_ingestion_is_idempotent(db, two_orgs):
    db.mention(two_orgs["company_a"], external_id="https://news.example/a")
    error = db.fails("insert into public.mentions (company_id, platform, external_id, text, published_at) "
                     "values (%s, 'news', 'https://news.example/a', 't', now())", two_orgs["company_a"])
    assert isinstance(error, psycopg.errors.UniqueViolation)
    assert db.run("insert into public.mentions (company_id, platform, external_id, text, published_at) "
                  "values (%s, 'news', 'https://news.example/a', 't', now()) "
                  "on conflict (company_id, platform, external_id) do nothing", two_orgs["company_a"]) == 0


# --- profiles and notifications ---------------------------------------------------------------------

def test_users_can_rename_themselves(db, two_orgs):
    with db.as_user(two_orgs["a"]):
        assert db.run("update public.profiles set name = 'Anna N.' where user_id = %s", two_orgs["a"]) == 1


@pytest.mark.parametrize("change", ["role = 'compliance'", "organization_id = %(org_b)s"])
def test_users_cannot_escalate_or_switch_org(db, two_orgs, change):
    with db.as_user(two_orgs["a"]):
        query = f"update public.profiles set {change} where user_id = %(a)s"
        try:
            with db.conn.transaction():
                db.conn.execute(query, {"a": two_orgs["a"], "org_b": two_orgs["org_b"]})
            error = None
        except psycopg.Error as e:
            error = e
    assert isinstance(error, psycopg.errors.InsufficientPrivilege)
    assert db.rows("select role, organization_id from public.profiles where user_id = %s", two_orgs["a"]) == \
        [("analyst", two_orgs["org_a"])]


def test_users_cannot_edit_other_profiles(db, two_orgs):
    with db.as_user(two_orgs["a"]):
        assert db.run("update public.profiles set name = 'x' where user_id = %s", two_orgs["b"]) == 0


def test_notifications_are_per_user(db, two_orgs):
    colleague, _ = db.signup("carl@kestrel.example")
    db.invite(colleague, two_orgs["org_a"])
    mine = db.notification(two_orgs["a"], two_orgs["org_a"])
    theirs = db.notification(colleague, two_orgs["org_a"])
    with db.as_user(two_orgs["a"]):
        assert db.column("select id from public.notifications") == [mine]
        assert db.run("update public.notifications set read_at = now() where id = %s", mine) == 1
        assert db.run("update public.notifications set read_at = now() where id = %s", theirs) == 0


# --- approvals --------------------------------------------------------------------------------------

def test_new_draft_invalidates_approvals_and_bumps_version(db, two_orgs):
    mention = db.mention(two_orgs["company_a"])
    db.response(mention, draft_hash="hash-1")
    pending, approved, rejected = (db.approval(mention, s) for s in ("pending", "approved", "rejected"))
    db.run("update public.mention_responses set draft = 'Edited', draft_hash = 'hash-2' where mention_id = %s", mention)
    status = dict(db.rows("select id, status from public.approvals where mention_id = %s", mention))
    assert status == {pending: "invalidated", approved: "invalidated", rejected: "rejected"}
    assert db.value("select draft_version from public.mention_responses where mention_id = %s", mention) == 2


def test_unchanged_draft_keeps_approvals(db, two_orgs):
    mention = db.mention(two_orgs["company_a"])
    db.response(mention, draft_hash="hash-1")
    approved = db.approval(mention, "approved")
    db.run("update public.mention_responses set needs_compliance = true where mention_id = %s", mention)
    assert db.value("select status from public.approvals where id = %s", approved) == "approved"
    assert db.value("select draft_version from public.mention_responses where mention_id = %s", mention) == 1


# --- vector search ----------------------------------------------------------------------------------

@pytest.fixture
def indexed(db, two_orgs):
    """One embedded chunk per classification in company A (all aligned with the query), plus decoys."""
    company = two_orgs["company_a"]
    for classification in ("public", "internal", "confidential", "restricted"):
        db.chunk(db.document(company, classification), vec(0))
    db.chunk(db.document(company, "public", status="processing"), vec(0))  # not indexed yet
    db.chunk(db.document(company, "public"), None)                       # no embedding
    db.chunk(db.document(two_orgs["company_b"], "public"), vec(0))      # another company
    return two_orgs


def search(db, company, ceiling=None, count=8, query=None):
    args = [company, query or vec(0), count] + ([ceiling] if ceiling else [])
    placeholders = ", ".join(["%s", "%s::extensions.vector", "%s"] + (["%s"] if ceiling else []))
    with db.role("service_role"):
        return db.rows(f"select document_name, classification, similarity from public.match_document_chunks({placeholders})", *args)


@pytest.mark.parametrize("ceiling,expected", [
    (None, {"public", "internal", "confidential"}),  # default ceiling: confidential
    ("confidential", {"public", "internal", "confidential"}),
    ("internal", {"public", "internal"}),
    ("public", {"public"}),
    ("restricted", set()),  # never returned, and an out-of-range ceiling fails closed
    ("top-secret", set()),
])
def test_vector_search_classification_ceiling(db, indexed, ceiling, expected):
    rows = search(db, indexed["company_a"], ceiling)
    assert {r[1] for r in rows} == expected
    assert len(rows) == len(expected)  # the processing, unembedded and other-company chunks never appear


def test_vector_search_orders_by_similarity_and_limits(db, two_orgs):
    company = two_orgs["company_a"]
    for hot in [(0,), (1,), (0, 1)]:
        db.chunk(db.document(company, "public"), vec(*hot))
    rows = search(db, company, count=2)
    assert len(rows) == 2
    assert rows[0][2] == pytest.approx(1.0) and rows[1][2] == pytest.approx(2 ** -0.5)


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_vector_search_is_not_callable_by_clients(db, indexed, role):
    with db.role(role, indexed["a"] if role == "authenticated" else None):
        error = db.fails("select * from public.match_document_chunks(%s, %s::extensions.vector)",
                         indexed["company_a"], vec(0))
    assert isinstance(error, psycopg.errors.InsufficientPrivilege)


# --- storage and cascades ---------------------------------------------------------------------------

def test_documents_bucket_is_private(db):
    assert db.rows("select public, file_size_limit, allowed_mime_types from storage.buckets where id = 'documents'") == \
        [(False, 20 * 1024 * 1024, ["application/pdf", "text/plain"])]


def test_deleting_a_company_removes_everything_below_it(db, two_orgs):
    company, org = two_orgs["company_a"], two_orgs["org_a"]
    db.chunk(db.document(company, "internal"), vec(0))
    mention = db.mention(company, cluster_id=db.cluster(company))
    db.response(mention)
    approval = db.approval(mention, "approved")
    db.run("insert into public.outbox (organization_id, mention_id, approval_id, channel, text) "
           "values (%s, %s, %s, 'simulated', 'Withdrawals work normally.')", org, mention, approval)
    db.notification(two_orgs["a"], org, mention)
    other_mention = db.mention(two_orgs["company_b"])

    assert db.run("delete from public.companies where id = %s", company) == 1
    for table in ("documents", "document_chunks", "clusters", "mentions", "mention_responses", "approvals", "outbox",
                  "notifications"):
        count = db.conn.execute(sql.SQL("select count(*) from public.{} where organization_id = %s")
                                .format(sql.Identifier(table)), (org,)).fetchone()[0]
        assert count == 0, table
    assert db.value("select count(*) from public.profiles where organization_id = %s", org) == 1
    assert db.value("select count(*) from public.mentions where id = %s", other_mention) == 1
