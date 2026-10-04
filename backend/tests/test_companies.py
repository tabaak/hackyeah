"""Company persistence and account isolation through the authenticated HTTP API."""
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.routers import companies as routes
from tests.test_auth import token

BODY = {
    "name": "Kestrel Bank", "website": "https://kestrel.example", "aliases": ["Kestrel"],
    "sector": "Banking", "country": "Poland", "people": [], "topics": ["Frozen withdrawals"],
}


def headers(org="o1", user="u1", **claims):
    return {"Authorization": f"Bearer {token(organization_id=org, sub=user, **claims)}"}


class MemoryDB:
    """Persist rows between requests, including requests from a fresh client."""
    def __init__(self):
        self.rows = {"companies": [], "documents": []}

    def table(self, name):
        return Query(self.rows[name])


class Query:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
        self.operation = "select"
        self.payload = None

    def select(self, *_):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def order(self, *_):
        return self

    def insert(self, payload):
        self.operation, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.operation, self.payload = "update", payload
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def execute(self):
        if self.operation == "insert":
            row = {"id": str(uuid4()), "created_at": "2026-10-03T12:00:00+00:00", "documents": [], **self.payload}
            self.rows.append(row)
            return SimpleNamespace(data=[deepcopy(row)])
        matches = [r for r in self.rows if all(r.get(k) == v for k, v in self.filters)]
        if self.operation == "update":
            for row in matches:
                row.update(self.payload)
        elif self.operation == "delete":
            self.rows[:] = [r for r in self.rows if r not in matches]
        return SimpleNamespace(data=deepcopy(matches))


@pytest.fixture
def client(monkeypatch):
    db = MemoryDB()
    monkeypatch.setattr(routes, "get_db", lambda: db)
    monkeypatch.setattr(settings, "demo_seed", False)
    monkeypatch.setattr(routes.social, "fill_feed", lambda *_: None)
    monkeypatch.setattr(routes.logos, "signed_urls", lambda _: {})
    monkeypatch.setattr(routes.logos, "remove", lambda _: None)
    with TestClient(app) as client:
        yield client, db


def test_company_is_saved_for_verified_account_and_restored_on_new_session(client):
    client, db = client
    # A client cannot select a different account or supply a browser-generated ID.
    body = {**BODY, "organizationId": "o2", "organization_id": "o2", "id": "browser-id"}
    response = client.post("/api/v1/companies", json=body, headers=headers())
    assert response.status_code == 201
    saved = response.json()
    assert saved["id"] != "browser-id"
    assert saved["createdAt"] > 0
    assert saved["documents"] == []
    assert db.rows["companies"][0]["organization_id"] == "o1"

    # Fresh client + a new access token must load the same persisted profile.
    with TestClient(app) as returning:
        response = returning.get("/api/v1/companies", headers=headers(jti="new-session"))
        assert response.status_code == 200
        assert response.json() == [saved]
    assert client.get("/api/v1/companies", headers=headers("o2", "u2")).json() == []


def test_other_account_cannot_read_update_or_delete_company(client):
    client, _ = client
    cid = client.post("/api/v1/companies", json=BODY, headers=headers()).json()["id"]
    path = f"/api/v1/companies/{cid}"
    other = headers("o2", "u2")
    assert client.get(path, headers=other).status_code == 404
    assert client.put(path, json={**BODY, "name": "Stolen"}, headers=other).status_code == 404
    assert client.delete(path, headers=other).status_code == 404
    assert client.get(path, headers=headers()).json()["name"] == BODY["name"]


def test_owner_can_update_without_changing_ownership(client):
    client, db = client
    cid = client.post("/api/v1/companies", json=BODY, headers=headers()).json()["id"]
    response = client.put(f"/api/v1/companies/{cid}", headers=headers(),
                          json={**BODY, "name": " Updated Bank ", "aliases": [" Bank ", "Bank", ""], "organizationId": "o2"})
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Bank"
    assert response.json()["aliases"] == ["Bank"]
    assert db.rows["companies"][0]["organization_id"] == "o1"
    assert client.delete(f"/api/v1/companies/{cid}", headers=headers()).status_code == 204
    assert client.get("/api/v1/companies", headers=headers()).json() == []


@pytest.mark.parametrize("field", ["name", "country"])
def test_blank_required_fields_are_rejected(client, field):
    client, db = client
    response = client.post("/api/v1/companies", json={**BODY, field: "   "}, headers=headers())
    assert response.status_code == 422
    assert db.rows["companies"] == []


def test_companies_require_sign_in(client):
    client, _ = client
    assert client.get("/api/v1/companies").status_code == 401
    assert client.post("/api/v1/companies", json=BODY).status_code == 401


def test_demo_seeding_remains_available(client, monkeypatch):
    client, _ = client
    seeded = []
    monkeypatch.setattr(settings, "demo_seed", True)
    monkeypatch.setattr(routes.demo, "seed_company", lambda row: seeded.append(row["id"]))
    response = client.post("/api/v1/companies", json=BODY, headers=headers())
    assert response.status_code == 201
    assert seeded == [response.json()["id"]]


@pytest.mark.parametrize("website", ["javascript:alert(document.cookie)", "data:text/html,<script>x</script>", "kestrel.example"])
def test_website_must_be_http_link(client, website):
    client, db = client
    assert client.post("/api/v1/companies", json={**BODY, "website": website}, headers=headers()).status_code == 422
    assert db.rows["companies"] == []


def test_company_lists_are_bounded(client):
    client, _ = client
    assert client.post("/api/v1/companies", json={**BODY, "aliases": ["a"] * 51}, headers=headers()).status_code == 422
    assert client.post("/api/v1/companies", json={**BODY, "people": ["x" * 201]}, headers=headers()).status_code == 422


@pytest.mark.parametrize("role,old,new,status", [
    ("analyst", "restricted", "public", 403),
    ("analyst", "confidential", "internal", 403),
    ("analyst", "internal", "confidential", 200),
    ("compliance", "restricted", "public", 200),
])
def test_only_compliance_lowers_classification(client, monkeypatch, role, old, new, status):
    client, db = client
    from app.routers import documents as doc_routes
    monkeypatch.setattr(doc_routes, "get_db", lambda: db)
    db.rows["documents"].append({"id": "d1", "organization_id": "o1", "name": "f.pdf", "size": 1,
                                 "classification": old, "status": "ready"})
    response = client.patch("/api/v1/documents/d1", json={"classification": new}, headers=headers(user_role=role))
    assert response.status_code == status
    assert db.rows["documents"][0]["classification"] == (new if status == 200 else old)
