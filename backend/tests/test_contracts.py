"""Contracts between layers that must agree: frontend types (mock.ts), Endpoints.md, Pydantic schemas,
SQL CHECK constraints and defaults, Supabase auth config and the Serper country map.
Static checks: they need no database and run in every environment."""
import re
import tomllib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.analytics import HourBucket, PlatformReach
from app.schemas.auth import Me
from app.schemas.common import (ApprovalState, CamelModel, Classification, DocumentStatus, MentionStatus, Platform,
                                Role, Severity, Verdict)
from app.schemas.companies import Company, CompanyDraft
from app.schemas.documents import Doc
from app.schemas.feed import Cluster, Mention, MentionStatusUpdate
from app.schemas.notifications import Notification, NotificationList
from app.schemas.response import Approval, ClaimCheck, Decision, Disclosure, EvidenceItem, MentionResponse
from app.sources.serper import COUNTRY_GL, MOCK_COMPANY, to_mention
from tests.conftest import REPO

MOCK_TS = (REPO / "frontend/src/lib/mock.ts").read_text()
COMPANY_SETUP_TSX = (REPO / "frontend/src/components/CompanySetup.tsx").read_text()
ENDPOINTS_MD = (REPO / "Endpoints.md").read_text()
SQL = "\n".join(p.read_text() for p in sorted((REPO / "supabase/migrations").glob("*.sql")))
SUPABASE_CONFIG = tomllib.loads((REPO / "supabase/config.toml").read_text())


def values(enum):
    return {e.value for e in enum}


def fields(model):
    """JSON field names (camelCase aliases) of a Pydantic model."""
    return {f.alias or name for name, f in model.model_fields.items()}


def names(csv):
    """Leading identifier of each comma-separated part: 'aliases[], documents: Doc[]' -> {aliases, documents}."""
    return {m[1] for part in csv.split(",") if (m := re.match(r"\s*(\w+)", part))}


def sketch(text):
    """Parse an object sketch from Endpoints.md, e.g. `{ a, b: { c, d }, e: [{ f }] }`,
    into (top-level names, {name: nested names})."""
    text = re.sub(r"//[^\n]*", "", text).strip()
    assert text.startswith("{") and text.endswith("}"), text
    inner = re.sub(r'"[^"]*"', "", text[1:-1])
    nested = {k: names(v) for k, v in re.findall(r"(\w+):\s*\[?\{([^{}]*)\}\]?", inner)}
    return names(re.sub(r"\[?\{[^{}]*\}\]?", "", inner)), nested


# --- frontend (frontend/src/lib/mock.ts) ------------------------------------------------------------

def ts_union(name):
    m = re.search(rf"export type {name} = ([^\n]+)", MOCK_TS)
    assert m, f"type {name} not found in mock.ts"
    return set(re.findall(r"'([^']+)'", m[1]))


def ts_interface(name):
    """{field: type} of `export interface <name> { ... }` (nested braces allowed on one line)."""
    start = MOCK_TS.index("{", MOCK_TS.index(f"export interface {name} "))
    depth = 0
    for end in range(start, len(MOCK_TS)):
        depth += {"{": 1, "}": -1}.get(MOCK_TS[end], 0)
        if depth == 0:
            break
    return dict(re.findall(r"^\s+(\w+)\??:\s*(.+?)\s*$", MOCK_TS[start + 1:end], re.M))


def ts_const_keys(name):
    block = MOCK_TS[MOCK_TS.index(f"export const {name}"):]
    block = block[:block.index("\n}\n")]
    return set(re.findall(r"^\s+(\w+): \[", block, re.M))


@pytest.mark.parametrize("ts_name,enum", [
    ("Severity", Severity), ("Classification", Classification), ("Platform", Platform),
    ("Verdict", Verdict), ("PostStatus", MentionStatus),
])
def test_frontend_enums_match_backend(ts_name, enum):
    assert ts_union(ts_name) == values(enum)


def test_frontend_document_status():
    ts = set(re.findall(r"'([^']+)'", ts_interface("Doc")["status"]))
    assert values(DocumentStatus) - ts == {"failed"}  # Endpoints.md: the UI shows `failed` as a processing error
    assert ts <= values(DocumentStatus)


@pytest.mark.parametrize("ts_name,model,backend_only", [
    ("Doc", Doc, set()),
    ("Company", Company, set()),
    ("Post", Mention, {"url"}),  # link to the original article; the frontend type does not have it yet
])
def test_frontend_interfaces_match_schemas(ts_name, model, backend_only):
    ts = set(ts_interface(ts_name))
    assert ts <= fields(model), f"backend lacks {ts - fields(model)}"
    assert fields(model) - ts == backend_only


def test_frontend_cluster_shape():
    assert set(re.findall(r"(\w+):", ts_interface("Post")["cluster"])) == fields(Cluster)


def test_company_form_sends_company_draft():
    omitted = re.search(r"export type CompanyDraft = Omit<Company, ([^>]+)>", COMPANY_SETUP_TSX)[1]
    assert fields(CompanyDraft) == set(ts_interface("Company")) - set(re.findall(r"'(\w+)'", omitted))


def test_every_frontend_country_has_a_news_region():
    countries = set(re.findall(r"'([^']+)'", re.search(r"export const COUNTRIES = \[([^\]]*)\]", MOCK_TS)[1]))
    assert countries == set(COUNTRY_GL)


# --- Endpoints.md -----------------------------------------------------------------------------------

def md_enum_table():
    rows = re.findall(r"^\| `(\w+)`(?: \(([^)]*)\))? \| (.+?) \|$", ENDPOINTS_MD, re.M)
    return {(name, qualifier): set(re.findall(r"`([^`]+)`", vals)) for name, qualifier, vals in rows}


@pytest.mark.parametrize("key,enum", [
    (("platform", ""), Platform), (("severity", ""), Severity), (("verdict", ""), Verdict),
    (("status", "згадка"), MentionStatus), (("classification", "документ"), Classification),
    (("status", "документ"), DocumentStatus),
])
def test_endpoints_md_enums(key, enum):
    assert md_enum_table()[key] == values(enum)


def md_block(title):
    return re.search(rf"\*\*{re.escape(title)}\*\*\n```\n(\{{.*?\}})\n```", ENDPOINTS_MD, re.S)[1]


def test_endpoints_md_models():
    assert sketch(md_block("Company"))[0] == fields(Company)
    assert sketch(re.search(r"\*\*Doc\*\* — `(\{[^`]*\})`", ENDPOINTS_MD)[1])[0] == fields(Doc)
    top, nested = sketch(md_block("Mention (Post)"))
    assert top == fields(Mention) - {"url"}  # see test_frontend_interfaces_match_schemas
    assert nested["cluster"] == fields(Cluster)


def test_endpoints_md_counter_post_response():
    block = re.search(r"`GET /mentions/\{id\}/response`[^\n]*\n\s*```\n(.*?)\n\s*```", ENDPOINTS_MD, re.S)[1]
    top, nested = sketch(block)
    assert top == fields(MentionResponse)
    assert nested == {"claimCheck": fields(ClaimCheck), "evidence": fields(EvidenceItem),
                      "disclosure": fields(Disclosure), "approval": fields(Approval)}
    states = re.search(r"state: ([^,]+),", block)[1]
    assert set(re.findall(r'"(\w+)"', states)) == values(ApprovalState)


def test_endpoints_md_request_and_small_bodies():
    assert names(re.search(r"`POST /companies` — створення компанії `\{([^}]*)\}`", ENDPOINTS_MD)[1]) == fields(CompanyDraft)
    assert names(re.search(r"`GET /me` — поточний користувач `\{([^}]*)\}`", ENDPOINTS_MD)[1]) == fields(Me)
    status = re.search(r"`PATCH /mentions/\{id\}/status` — `\{ status: ([^}]*)\}`", ENDPOINTS_MD)[1]
    assert fields(MentionStatusUpdate) == {"status"} and set(re.findall(r'"(\w+)"', status)) == values(MentionStatus)
    assert names(re.search(r"рішення compliance `\{([^}]*)\}`", ENDPOINTS_MD)[1]) == fields(Decision)
    assert names(re.search(r"інциденти[^`]*`\{([^}]*)\}`", ENDPOINTS_MD)[1]) == fields(Notification)
    assert "`openCount`" in ENDPOINTS_MD and fields(NotificationList) == {"items", "openCount"}
    assert names(re.search(r"бакети `\{([^}]*)\}`", ENDPOINTS_MD)[1]) == fields(HourBucket)
    assert names(re.search(r"`\[\{([^}]*)\}\]` \(«Reach by platform»\)", ENDPOINTS_MD)[1]) == fields(PlatformReach)


# --- SQL (supabase/migrations) ----------------------------------------------------------------------

def sql_tables():
    return dict(re.findall(r"create table (?:public|private)\.(\w+) \((.*?)\n\);", SQL, re.S))


def sql_check(table, column):
    m = re.search(rf"check \({column} in \(([^)]*)\)\)", sql_tables()[table])
    assert m, f"no CHECK on {table}.{column}"
    return set(re.findall(r"'([^']+)'", m[1]))


@pytest.mark.parametrize("table,column,expected", [
    ("mentions", "platform", values(Platform)),
    ("mentions", "severity", values(Severity)),
    ("notifications", "severity", values(Severity)),
    ("mentions", "verdict", values(Verdict)),
    ("mentions", "status", values(MentionStatus)),
    ("documents", "classification", values(Classification)),
    ("document_chunks", "classification", values(Classification)),
    ("documents", "status", values(DocumentStatus)),
    ("profiles", "role", values(Role)),
    ("approvals", "required_role", values(Role)),
    ("companies", "sector", ts_const_keys("SECTORS")),
])
def test_sql_checks_match_enums(table, column, expected):
    assert sql_check(table, column) == expected


def test_sql_mention_defaults_match_ingestion_placeholders():
    """Serper ingestion fills the same neutral values the DB uses as defaults."""
    table = sql_tables()["mentions"]
    defaults = dict(re.findall(r"^\s+(severity|verdict|status|reason)\s+text not null default '([^']*)'", table, re.M))
    m = to_mention({"link": "https://news.example/a", "title": "t"}, "c-1", 0)
    assert defaults == {"severity": m.severity.value, "verdict": m.verdict.value, "status": m.status.value,
                        "reason": m.reason}


def test_every_public_table_has_row_level_security():
    tables = set(re.findall(r"create table public\.(\w+)", SQL))
    secured = set(re.findall(r"alter table public\.(\w+)\s+enable row level security", SQL))
    assert len(tables) >= 10 and tables == secured


# --- Supabase auth config ---------------------------------------------------------------------------

def test_supabase_auth_is_google_only():
    auth = SUPABASE_CONFIG["auth"]
    assert auth["external"]["google"]["enabled"] is True
    assert auth["email"]["enable_signup"] is False
    assert auth["sms"]["enable_signup"] is False
    assert auth["enable_anonymous_sign_ins"] is False


def test_supabase_config_has_no_inline_secrets():
    google = SUPABASE_CONFIG["auth"]["external"]["google"]
    assert google["client_id"].startswith("env(") and google["secret"].startswith("env(")


def test_token_hook_is_configured_and_defined():
    hook = SUPABASE_CONFIG["auth"]["hook"]["custom_access_token"]
    assert hook["enabled"] is True
    schema, function = hook["uri"].removeprefix("pg-functions://postgres/").split("/")
    assert f"create function {schema}.{function}(event jsonb)" in SQL


def test_token_hook_sets_the_claims_the_api_reads():
    body = SQL.split("create function public.custom_access_token_hook")[1].split("$$;")[0]
    assert set(re.findall(r"jsonb_set\(claims, '\{(\w+)\}'", body)) == {"user_role", "organization_id"}
    deps = (REPO / "backend/app/deps.py").read_text()
    assert re.search(r"""claims\.get\(["']user_role["']\)""", deps)
    assert re.search(r"""claims\.get\(["']organization_id["']\)""", deps)


# --- JSON naming ------------------------------------------------------------------------------------

def test_openapi_json_is_camel_case():
    app.openapi_schema = None
    schemas = app.openapi()["components"]["schemas"]
    bad = {f"{name}.{prop}" for name, s in schemas.items() for prop in s.get("properties", {})
           if not re.fullmatch(r"[a-z][a-zA-Z0-9]*", prop)}
    assert not bad


def _camel_models(cls=CamelModel):
    for sub in cls.__subclasses__():
        yield sub
        yield from _camel_models(sub)


@pytest.mark.parametrize("model", sorted(set(_camel_models()), key=lambda m: m.__name__), ids=lambda m: m.__name__)
def test_models_accept_camel_and_snake_case(model):
    snake = {name for name in model.model_fields if "_" in name}
    for name in snake:
        alias = model.model_fields[name].alias
        assert alias and "_" not in alias, f"{model.__name__}.{name}"


def test_response_models_serialize_camel_case():
    demo = FastAPI()

    @demo.get("/mention", response_model=Mention)
    def mention():
        return to_mention({"link": "https://news.example/a", "title": "t", "source": "Daily Ledger"}, "c-1", 0)

    body = TestClient(demo).get("/mention").json()
    assert body["companyId"] == "c-1" and "company_id" not in body
    assert NotificationList.model_validate({"items": [], "openCount": 2}).open_count == 2
    assert NotificationList.model_validate({"items": [], "open_count": 2}).open_count == 2


def test_mock_company_matches_frontend_form():
    assert MOCK_COMPANY.sector in ts_const_keys("SECTORS")
    assert set(MOCK_COMPANY.model_dump(by_alias=True)) == fields(CompanyDraft)
