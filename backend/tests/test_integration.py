"""End-to-end flow against a real Supabase project. Skipped unless backend/.env has
SUPABASE_SERVICE_ROLE_KEY and INTEGRATION_USER_EMAIL (a user who signed in once).
Creates a company in that user's organization and deletes it afterwards."""
import os
import time

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

ENV = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
pytestmark = pytest.mark.skipif(
    not (ENV.get("SUPABASE_SERVICE_ROLE_KEY") and ENV.get("INTEGRATION_USER_EMAIL")),
    reason="needs backend/.env with SUPABASE_SERVICE_ROLE_KEY and INTEGRATION_USER_EMAIL",
)


@pytest.fixture(scope="module")
def ctx():
    from app.config import settings
    settings.supabase_url = ENV["SUPABASE_URL"].rstrip("/")
    settings.supabase_service_role_key = ENV["SUPABASE_SERVICE_ROLE_KEY"]
    settings.demo_seed = True

    from app.db import get_db
    from app.deps import get_current_user, require_compliance
    from app.main import app
    from app.schemas.auth import CurrentUser

    get_db.cache_clear()
    profile = get_db().table("profiles").select("*").eq("email", ENV["INTEGRATION_USER_EMAIL"]).single().execute().data
    state = {"role": "analyst"}

    def user():
        return CurrentUser(id=profile["user_id"], organization_id=profile["organization_id"], name=profile["name"],
                           email=profile["email"], role=state["role"])

    app.dependency_overrides[get_current_user] = user
    app.dependency_overrides[require_compliance] = user
    client = TestClient(app)
    yield client, state
    app.dependency_overrides.clear()


def test_full_flow(ctx):
    client, state = ctx
    body = {"name": f"Integration Bank {int(time.time())}", "website": "https://integration.example", "aliases": ["IntBank"],
            "sector": "Banking", "country": "Poland", "people": ["Jan Test"], "topics": ["Frozen withdrawals"]}
    r = client.post("/api/v1/companies", json=body)
    assert r.status_code == 201, r.text
    company = r.json()
    cid = company["id"]
    try:
        assert company["name"] == body["name"] and company["documents"] == []
        assert any(c["id"] == cid for c in client.get("/api/v1/companies").json())
        assert client.get("/api/v1/companies/meta").json()["sectors"]["Banking"]

        # Documents: upload, background processing, signed URL, reclassify.
        files = [("files", ("status.txt", b"All accounts, cards and transfers are operating normally. "
                                          b"Withdrawals were never frozen. ATM maintenance in one region finished at 9:00.", "text/plain"))]
        r = client.post(f"/api/v1/companies/{cid}/documents", files=files, data={"classifications": ["public"]})
        assert r.status_code == 202, r.text
        doc = r.json()[0]
        docs = client.get(f"/api/v1/companies/{cid}/documents").json()
        assert docs[0]["status"] == "ready", docs  # TestClient runs background tasks before returning
        assert client.get(f"/api/v1/documents/{doc['id']}/url").json()["url"].startswith("http")
        assert client.patch(f"/api/v1/documents/{doc['id']}", json={"classification": "confidential"}).json()["classification"] == "confidential"

        # Seeded mentions.
        mentions = client.get("/api/v1/mentions", params={"company_id": cid, "limit": 50}).json()
        assert len(mentions) == 10
        high = [m for m in mentions if m["severity"] == "high"]
        assert high and any(m["injection"] for m in mentions) and any(m["cluster"] for m in mentions)
        assert client.get("/api/v1/mentions", params={"company_id": cid, "severity": "low"}).json()
        newest = mentions[0]
        assert client.get("/api/v1/mentions", params={"company_id": cid, "since_id": newest["id"]}).json() == []

        # Counter-post: confidential evidence -> compliance flow.
        target = next(m for m in mentions if "withdraw" in m["text"].lower())
        resp = client.get(f"/api/v1/mentions/{target['id']}/response").json()
        assert resp["draft"] and resp["evidence"][0]["name"] == "status.txt"
        assert resp["disclosure"]["needsCompliance"] is True
        assert client.post(f"/api/v1/mentions/{target['id']}/response/approve").status_code == 409  # analyst
        resp = client.patch(f"/api/v1/mentions/{target['id']}/response/draft", json={"text": resp["draft"] + " Thank you."}).json()
        assert resp["draft"].endswith("Thank you.")
        assert client.post(f"/api/v1/mentions/{target['id']}/response/request-approval").json()["approval"]["state"] == "pending"
        # Editing after the request invalidates it.
        resp = client.patch(f"/api/v1/mentions/{target['id']}/response/draft", json={"text": "Edited after request."}).json()
        assert resp["approval"]["state"] == "none"
        client.post(f"/api/v1/mentions/{target['id']}/response/request-approval")
        state["role"] = "compliance"
        resp = client.post(f"/api/v1/mentions/{target['id']}/response/decision", json={"approve": True}).json()
        state["role"] = "analyst"
        assert resp["approval"]["state"] == "approved"
        assert client.get(f"/api/v1/mentions/{target['id']}").json()["status"] == "responded"

        # Dismiss.
        other = next(m for m in mentions if m["id"] != target["id"])
        assert client.patch(f"/api/v1/mentions/{other['id']}/status", json={"status": "dismissed"}).json()["status"] == "dismissed"

        # Analytics.
        s = client.get("/api/v1/analytics/summary", params={"company_id": cid}).json()
        assert s["total"] == 10 and s["responded"] == 1 and s["dismissed"] == 1 and s["clusters"] == 4 and s["injectionsBlocked"] == 1
        hours = client.get("/api/v1/analytics/mentions-by-hour", params={"company_id": cid}).json()
        assert len(hours) == 24 and sum(h["low"] + h["medium"] + h["high"] for h in hours) == 10
        reach = client.get("/api/v1/analytics/reach-by-platform", params={"company_id": cid}).json()
        assert len(reach) == 7 and reach[0]["reach"] >= reach[-1]["reach"]
        assert len(client.get("/api/v1/analytics/claim-verification", params={"company_id": cid}).json()) == 4

        # Notifications for high mentions.
        n = client.get("/api/v1/notifications").json()
        mine = [x for x in n["items"] if x["mentionId"] in {m["id"] for m in high}]
        assert mine and n["openCount"] >= 1
        assert client.patch(f"/api/v1/notifications/{mine[0]['id']}/read").json()["read"] is True

        # Sources.
        assert client.get("/api/v1/feed/sources/x/status").json()["healthy"] is False
        assert client.post("/api/v1/feed/sources/x/sync").status_code == 501

        assert client.delete(f"/api/v1/documents/{doc['id']}").status_code == 204
    finally:
        assert client.delete(f"/api/v1/companies/{cid}").status_code == 204
    assert client.get(f"/api/v1/companies/{cid}").status_code == 404
