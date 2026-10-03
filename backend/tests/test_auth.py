import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def token(**overrides) -> str:
    claims = {
        "sub": "u1", "aud": "authenticated", "iss": f"{settings.supabase_url}/auth/v1", "exp": int(time.time()) + 600,
        "email": "a@b.c", "app_metadata": {"provider": "google"}, "user_metadata": {"full_name": "Ann"},
        "user_role": "analyst", "organization_id": "o1",
    }
    claims.update(overrides)
    return jwt.encode(claims, settings.supabase_jwt_secret, algorithm="HS256")


def get_me(tok: str | None):
    return client.get("/api/v1/me", headers={"Authorization": f"Bearer {tok}"} if tok else {})


def test_google_user_gets_profile():
    r = get_me(token())
    assert r.status_code == 200
    assert r.json() == {"name": "Ann", "email": "a@b.c", "role": "analyst"}


@pytest.mark.parametrize("tok, code", [
    (None, 401),
    (lambda: token(exp=1), 401),
    (lambda: token(iss="https://evil/auth/v1"), 401),
    (lambda: jwt.encode({"sub": "u1"}, "other-secret-other-secret-other-xxx", algorithm="HS256"), 401),
    (lambda: jwt.encode({"sub": "u1"}, None, algorithm="none"), 401),
    (lambda: token(app_metadata={"provider": "email"}), 403),
    (lambda: token(user_role=None), 403),
])
def test_rejected_tokens(tok, code):
    assert get_me(tok() if callable(tok) else tok).status_code == code


def test_decision_requires_compliance():
    r = client.post("/api/v1/mentions/m1/response/decision", json={"approve": True},
                    headers={"Authorization": f"Bearer {token()}"})
    assert r.status_code == 403


def test_auth_endpoints_removed():
    assert client.post("/api/v1/auth/login").status_code == 404
