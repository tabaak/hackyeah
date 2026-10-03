"""Route inventory: Endpoints.md (sections 1-8) <-> the FastAPI app, route matching order, OpenAPI."""
import re
import sys
import warnings

import pytest
from fastapi import HTTPException

from app.main import app
from app.routers import analytics, companies, documents, feed, notifications, response, sources
from tests.conftest import API, REPO

ENDPOINTS_MD = (REPO / "Endpoints.md").read_text()


def api_routes():
    """(METHOD, full path) of every API operation, read from the OpenAPI schema (stable across FastAPI versions)."""
    app.openapi_schema = None
    paths = app.openapi()["paths"]
    return sorted((m.upper(), p) for p, ops in paths.items() if p.startswith(API) for m in ops)


def shape(path):
    """Compare paths by structure: /companies/{id} in the docs == /companies/{company_id} in code."""
    return re.sub(r"\{[^}]+\}", "{}", path)


def implemented():
    return {(m, shape(p.removeprefix(API))) for m, p in api_routes()}


def documented():
    current = ENDPOINTS_MD.split("### 9.")[0]  # section 9 lists planned endpoints that have no UI yet
    return {(m, shape(p)) for m, p in re.findall(r"`(GET|POST|PUT|PATCH|DELETE) (/[^`\s]*)`", current)}


def test_endpoints_md_is_parsed():
    assert len(documented()) >= 30


def test_every_documented_endpoint_is_implemented():
    assert sorted(documented() - implemented()) == []


def test_every_implemented_endpoint_is_documented():
    assert sorted(implemented() - documented()) == []


@pytest.fixture
def handler_name(monkeypatch):
    """Make every stub answer 501 with the name of the handler that actually ran."""
    def tracer():
        raise HTTPException(501, sys._getframe(1).f_code.co_name)

    for module in (analytics, companies, documents, feed, notifications, response, sources):
        monkeypatch.setattr(module, "not_implemented", tracer)


@pytest.mark.parametrize("method,path,handler", [
    ("GET", "/companies/meta", "companies_meta"),        # not get_company(company_id="meta")
    ("GET", "/companies/c-1", "get_company"),
    ("GET", "/mentions/stream", "stream_mentions"),       # not get_mention(mention_id="stream")
    ("GET", "/mentions/m-1", "get_mention"),
    ("GET", "/mentions/m-1/response", "get_response"),
    ("POST", "/feed/sources/facebook/webhook", "facebook_webhook"),
    ("POST", "/feed/sources/facebook/sync", "sync"),
    ("GET", "/feed/sources/facebook/status", "status"),
    ("POST", "/notifications/mark-all-read", "mark_all_read"),
    ("PATCH", "/notifications/n-1/read", "mark_read"),
])
def test_route_resolution_order(client, analyst, handler_name, method, path, handler):
    r = client.request(method, API + path, headers=analyst)
    assert r.status_code == 501 and r.json()["detail"] == handler


def test_openapi_has_unique_operation_ids():
    app.openapi_schema = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        schema = app.openapi()
    assert not [w for w in caught if "Duplicate Operation ID" in str(w.message)]
    ids = [op["operationId"] for ops in schema["paths"].values() for op in ops.values()]
    assert len(ids) == len(set(ids))


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
