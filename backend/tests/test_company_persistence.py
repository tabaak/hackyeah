"""Opt-in Supabase test. Uses existing profiles and removes only the company it creates.

RUN_COMPANY_INTEGRATION=1 .venv/bin/python -m pytest -q tests/test_company_persistence.py
"""
import os
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

ENV = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_COMPANY_INTEGRATION") != "1" or not ENV.get("SUPABASE_SERVICE_ROLE_KEY"),
    reason="opt-in: RUN_COMPANY_INTEGRATION=1 and backend/.env Supabase credentials required",
)


@pytest.fixture
def live(monkeypatch):
    from app.config import settings
    from app.db import get_db
    from app.deps import get_current_user
    from app.main import app
    from app.schemas.auth import CurrentUser

    monkeypatch.setattr(settings, "supabase_url", ENV["SUPABASE_URL"].rstrip("/"))
    monkeypatch.setattr(settings, "supabase_service_role_key", ENV["SUPABASE_SERVICE_ROLE_KEY"])
    monkeypatch.setattr(settings, "demo_seed", True)
    monkeypatch.setattr(settings, "serper_api_key", "")
    get_db.cache_clear()
    db = get_db()
    profiles = db.table("profiles").select("user_id, organization_id").limit(20).execute().data
    if not profiles:
        pytest.skip("needs an account that has signed in once")
    state = {"account": profiles[0]}

    def current_user():
        profile = state["account"]
        return CurrentUser(id=profile["user_id"], organization_id=profile["organization_id"],
                           name="Persistence test", email="persistence@example.com", role="analyst")

    app.dependency_overrides[get_current_user] = current_user
    try:
        with TestClient(app) as client:
            yield client, db, profiles, state
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        get_db.cache_clear()


def test_create_restore_and_account_isolation_in_supabase(live):
    client, db, profiles, state = live
    owner = state["account"]
    body = {"name": f"Persistence test {uuid4().hex[:8]}", "website": "https://persistence.example",
            "aliases": ["Persistence"], "sector": "Banking", "country": "Poland", "people": [], "topics": []}
    cid = None
    try:
        response = client.post("/api/v1/companies", json=body)
        assert response.status_code == 201, response.text
        saved = response.json()
        cid = saved["id"]
        row = db.table("companies").select("id, organization_id, name").eq("id", cid).single().execute().data
        assert row["organization_id"] == owner["organization_id"]
        assert row["name"] == body["name"]

        # Independent session/client reads the same database company, including its UUID.
        with TestClient(client.app) as returning:
            response = returning.get("/api/v1/companies")
            assert response.status_code == 200, response.text
            assert saved in response.json()

        mentions = db.table("mentions").select("id, organization_id").eq("company_id", cid).execute().data
        assert len(mentions) == 10  # demo data stays available
        assert all(m["organization_id"] == owner["organization_id"] for m in mentions)

        other = next((p for p in profiles if p["organization_id"] != owner["organization_id"]), None)
        if other:
            state["account"] = other
            response = client.get("/api/v1/companies")
            assert response.status_code == 200, response.text
            assert all(c["id"] != cid for c in response.json())
            path = f"/api/v1/companies/{cid}"
            assert client.get(path).status_code == 404
            assert client.put(path, json={**body, "name": "Unauthorized change"}).status_code == 404
            assert client.delete(path).status_code == 404
            assert db.table("companies").select("name").eq("id", cid).single().execute().data["name"] == body["name"]
    finally:
        if cid:
            db.table("companies").delete().eq("id", cid).eq("organization_id", owner["organization_id"]).execute()
        else:
            # Also clean up if a background seed fails after the company was committed.
            db.table("companies").delete().eq("name", body["name"]).eq("website", body["website"]).eq("organization_id", owner["organization_id"]).execute()
