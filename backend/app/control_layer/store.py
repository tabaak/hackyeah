"""Local persistence. All content access is scoped by organization, including FTS."""
import hashlib
import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Conflict(Exception):
    pass


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)
        self.path = self.root / "control.sqlite3"
        self._lock = threading.RLock()
        # Create with restrictive permissions before SQLite opens it.
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        self.path.chmod(0o600)
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY, org TEXT NOT NULL, kind TEXT NOT NULL,
                    company TEXT, classification TEXT NOT NULL, data TEXT NOT NULL,
                    created TEXT NOT NULL, updated TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS records_scope ON records(org,kind,company);
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, org TEXT NOT NULL, kind TEXT NOT NULL, company TEXT,
                    role TEXT NOT NULL, classification TEXT NOT NULL DEFAULT 'restricted',
                    state TEXT NOT NULL, request TEXT NOT NULL, result TEXT,
                    error TEXT, idem TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    created TEXT NOT NULL, updated TEXT NOT NULL,
                    UNIQUE(org,kind,company,idem));
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY, org TEXT NOT NULL, job TEXT NOT NULL, data TEXT NOT NULL);
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
                    org UNINDEXED, company UNINDEXED, doc UNINDEXED, evidence UNINDEXED,
                    classification UNINDEXED, content);
            """)

    @contextmanager
    def db(self):
        with self._lock:
            db = sqlite3.connect(self.path, timeout=15)
            db.row_factory = sqlite3.Row
            try:
                with db:
                    yield db
            finally:
                db.close()

    def recover(self):
        with self.db() as db:
            db.execute("UPDATE jobs SET state='failed',error='interrupted',updated=? WHERE state IN ('queued','running')", (now(),))

    def save_file(self, data: bytes):
        directory = self.root / "files"
        directory.mkdir(exist_ok=True, mode=0o700)
        path = directory / str(uuid.uuid4())
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        return str(path)

    def put(self, org, kind, data, company=None, classification="internal", record_id=None):
        rid = record_id or str(uuid.uuid4())
        with self.db() as db:
            old = db.execute("SELECT org,kind FROM records WHERE id=?", (rid,)).fetchone()
            if old and (old["org"] != org or old["kind"] != kind):
                raise Conflict("Record ownership mismatch")
            db.execute("""INSERT INTO records VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET data=excluded.data,classification=excluded.classification,updated=excluded.updated""",
                       (rid, org, kind, company, classification, json.dumps(data), now(), now()))
        return rid

    def get(self, org, rid, kind=None):
        with self.db() as db:
            row = db.execute("SELECT * FROM records WHERE org=? AND id=?", (org, rid)).fetchone()
        if not row or (kind and row["kind"] != kind):
            return None
        return {**dict(row), "data": json.loads(row["data"])}

    def records(self, org, kind, company=None):
        with self.db() as db:
            sql, args = "SELECT * FROM records WHERE org=? AND kind=?", [org, kind]
            if company is not None:
                sql += " AND company=?"
                args.append(company)
            rows = db.execute(sql, args).fetchall()
        return [{**dict(r), "data": json.loads(r["data"])} for r in rows]

    def add_chunks(self, org, company, doc, evidence):
        with self.db() as db:
            db.execute("DELETE FROM chunks WHERE org=? AND doc=?", (org, doc))
            db.executemany("INSERT INTO chunks VALUES(?,?,?,?,?,?)", [
                (org, company, doc, e.id, e.classification, e.content) for e in evidence])

    def search(self, org, company, query, role, limit=8):
        import re
        words = list(dict.fromkeys(re.findall(r"\w{3,}", query)))[:25]
        if not words:
            return []
        match = " OR ".join('"' + w + '"' for w in words)
        with self.db() as db:
            rows = db.execute("""SELECT evidence,content,classification FROM chunks
                WHERE chunks MATCH ? AND org=? AND company=?
                AND (classification!='restricted' OR ?='compliance') ORDER BY rank LIMIT ?""",
                              (match, org, company, role, limit)).fetchall()
        return [dict(r) for r in rows]

    def create_job(self, org, kind, company, role, request, idem):
        fingerprint = digest(request)
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM jobs WHERE org=? AND kind=? AND company=? AND idem=?",
                             (org, kind, company, idem)).fetchone()
            if row:
                if row["fingerprint"] != fingerprint:
                    raise Conflict("Idempotency key reused with different input")
                return row["id"], False
            jid = str(uuid.uuid4())
            db.execute("""INSERT INTO jobs(id,org,kind,company,role,state,request,idem,fingerprint,created,updated)
                       VALUES(?,?,?,?,?,'queued',?,?,?,?,?)""",
                       (jid, org, kind, company, role, json.dumps(request), idem, fingerprint, now(), now()))
        return jid, True

    def job(self, org, jid):
        with self.db() as db:
            row = db.execute("SELECT * FROM jobs WHERE org=? AND id=?", (org, jid)).fetchone()
        if not row:
            return None
        out = dict(row)
        for k in ("request", "result"):
            out[k] = json.loads(out[k]) if out[k] else None
        return out

    def update_job(self, org, jid, state, result=None, classification="restricted", error=None):
        with self.db() as db:
            db.execute("UPDATE jobs SET state=?,result=?,classification=?,error=?,updated=? WHERE org=? AND id=?",
                       (state, json.dumps(result) if result is not None else None, classification, error, now(), org, jid))

    def audit(self, org, jid, data):
        with self.db() as db:
            db.execute("INSERT INTO audit(org,job,data) VALUES(?,?,?)", (org, jid, json.dumps({"at": now(), **data})))

    def audits(self, org, jid):
        with self.db() as db:
            rows = db.execute("SELECT data FROM audit WHERE org=? AND job=? ORDER BY id", (org, jid)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def latest_assessments(self, org):
        with self.db() as db:
            rows = db.execute("SELECT * FROM jobs WHERE org=? AND kind='assessment' AND state='succeeded' ORDER BY created DESC", (org,)).fetchall()
        seen, out = set(), []
        for r in rows:
            if r["company"] not in seen:
                seen.add(r["company"])
                out.append({**dict(r), "result": json.loads(r["result"])})
        return out
