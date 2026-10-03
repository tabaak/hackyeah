"""JWT verification (app/deps.py) exercised through the real API: /me, route protection, the compliance gate."""
import base64
import json
import re
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from tests.conftest import API, DROP, JWT_SECRET, ORG_ID, SUPABASE_URL, USER_ID, bearer, hs256, make_claims, sign
from tests.test_routes import api_routes

ME = f"{API}/me"


def get_me(client, token):
    return client.get(ME, headers=bearer(token))


def expect_401(response, detail):
    assert response.status_code == 401, response.text
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json()["detail"] == detail


# --- accepted tokens --------------------------------------------------------------------------------

def test_valid_token_returns_profile(client):
    r = get_me(client, hs256())
    assert r.status_code == 200
    assert r.json() == {"name": "Anna Nowak", "email": "anna.nowak@kestrel.example", "role": "analyst"}


def test_me_does_not_expose_internal_ids(client):
    body = json.dumps(get_me(client, hs256()).json())
    assert USER_ID not in body and ORG_ID not in body


def test_compliance_role(client):
    assert get_me(client, hs256(user_role="compliance")).json()["role"] == "compliance"


@pytest.mark.parametrize("metadata,name", [
    ({"full_name": "Anna Nowak", "name": "anna"}, "Anna Nowak"),
    ({"name": "anna"}, "anna"),
    ({}, ""),
    (DROP, ""),
])
def test_name_from_google_metadata(client, metadata, name):
    assert get_me(client, hs256(user_metadata=metadata)).json()["name"] == name


def test_issuer_not_checked_when_supabase_url_unset(client, monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "")
    assert get_me(client, hs256(iss="https://anything.example/auth/v1")).status_code == 200


@pytest.mark.parametrize("alg", ["ES256", "RS256"])
def test_asymmetric_token_verified_with_project_jwks(client, jwks, signing_keys, alg):
    kid, key = signing_keys[alg]
    r = get_me(client, sign(alg, key, kid))
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "analyst"
    assert jwks == [f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"]


def test_jwks_is_fetched_once(client, jwks, signing_keys):
    kid, key = signing_keys["ES256"]
    for _ in range(3):
        assert get_me(client, sign("ES256", key, kid)).status_code == 200
    assert len(jwks) == 1


# --- rejected tokens (401) --------------------------------------------------------------------------

def test_missing_header(client):
    expect_401(client.get(ME), "Missing bearer token")


def test_other_auth_scheme(client):
    expect_401(client.get(ME, headers={"Authorization": "Basic YW5uYTpzZWNyZXQ="}), "Missing bearer token")


def test_garbage_token(client):
    expect_401(get_me(client, "not-a-jwt"), "Invalid or expired token")


@pytest.mark.parametrize("overrides", [
    {"exp": int(time.time()) - 10},
    {"nbf": int(time.time()) + 600},
    {"exp": DROP},
    {"sub": DROP},
    {"aud": "anon"},
    {"aud": DROP},
    {"iss": "https://other-project.supabase.co/auth/v1"},
    {"iss": DROP},
], ids=["expired", "not-yet-valid", "no-exp", "no-sub", "wrong-aud", "no-aud", "other-project-iss", "no-iss"])
def test_invalid_claims(client, overrides):
    expect_401(get_me(client, hs256(**overrides)), "Invalid or expired token")


def test_wrong_hs256_secret(client):
    expect_401(get_me(client, hs256(secret="another-secret-with-at-least-32-bytes")), "Invalid or expired token")


def test_hs256_refused_without_configured_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    expect_401(get_me(client, hs256()), "HS256 tokens are not accepted")


def _unsigned(claims):
    def part(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{part({'alg': 'none', 'typ': 'JWT'})}.{part(claims)}."


def test_alg_none_refused(client):
    expect_401(get_me(client, _unsigned(make_claims())), "Unsupported token algorithm")


def test_other_hmac_alg_refused(client):
    token = jwt.encode(make_claims(), JWT_SECRET + "-padding-for-hs512-key-length!!!", algorithm="HS512")
    expect_401(get_me(client, token), "Unsupported token algorithm")


def test_forged_asymmetric_signature(client, jwks, signing_keys):
    kid, _ = signing_keys["ES256"]
    attacker_key = ec.generate_private_key(ec.SECP256R1())
    expect_401(get_me(client, sign("ES256", attacker_key, kid)), "Invalid or expired token")


def test_unknown_key_id(client, jwks, signing_keys):
    _, key = signing_keys["ES256"]
    expect_401(get_me(client, sign("ES256", key, "rotated-away")), "Invalid or expired token")


@pytest.mark.xfail(strict=True, reason=(
    "BUG deps.py: the header `alg` is trusted when a JWKS key is used; a token naming the kid of a key of another "
    "type makes PyJWT raise TypeError -> 500 instead of 401. Fix: reject when signing_key.algorithm_name != alg."))
@pytest.mark.parametrize("token_alg,key_alg", [("RS256", "ES256"), ("ES256", "RS256")])
def test_key_type_mismatch(jwks, signing_keys, token_alg, key_alg):
    key_kid, _ = signing_keys[key_alg]
    _, signer = signing_keys[token_alg]
    with TestClient(app, raise_server_exceptions=False) as raw_client:
        expect_401(get_me(raw_client, sign(token_alg, signer, key_kid)), "Invalid or expired token")


def test_asymmetric_refused_without_supabase_url(client, jwks, signing_keys, monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "")
    kid, key = signing_keys["ES256"]
    expect_401(get_me(client, sign("ES256", key, kid)), "SUPABASE_URL is not configured")


def test_jwks_outage_is_401_not_500(client, signing_keys, monkeypatch):
    def unreachable(self):
        raise jwt.exceptions.PyJWKClientConnectionError("connection refused")

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", unreachable)
    kid, key = signing_keys["ES256"]
    expect_401(get_me(client, sign("ES256", key, kid)), "Invalid or expired token")


# --- valid token, not allowed (403) -----------------------------------------------------------------

@pytest.mark.parametrize("overrides,detail", [
    ({"app_metadata": {"provider": "email"}}, "Only Google sign-in is allowed"),
    ({"app_metadata": {}}, "Only Google sign-in is allowed"),
    ({"app_metadata": DROP}, "Only Google sign-in is allowed"),
    ({"user_role": DROP}, "User profile is not provisioned"),
    ({"user_role": "admin"}, "User profile is not provisioned"),
    ({"organization_id": DROP}, "User profile is not provisioned"),
    ({"organization_id": ""}, "User profile is not provisioned"),
], ids=["email-provider", "no-provider", "no-app-metadata", "no-role", "unknown-role", "no-org", "empty-org"])
def test_forbidden(client, overrides, detail):
    r = get_me(client, hs256(**overrides))
    assert r.status_code == 403 and r.json()["detail"] == detail


# --- every route ------------------------------------------------------------------------------------

PATH_VALUES = {"platform": "news"}
WEBHOOK = f"{API}/feed/sources/facebook/webhook"
ROUTES = api_routes()
ROUTE_IDS = [f"{m} {p.removeprefix(API)}" for m, p in ROUTES]

COMPANY = {"name": "Kestrel Bank", "sector": "Banking", "country": "Poland"}
VALID_REQUEST = {
    ("POST", "/companies"): {"json": COMPANY},
    ("PUT", "/companies/{company_id}"): {"json": COMPANY},
    ("POST", "/companies/{company_id}/documents"): {
        "files": [("files", ("faq.txt", b"Withdrawals work normally.", "text/plain"))],
        "data": {"classifications": ["internal"]},
    },
    ("PATCH", "/documents/{document_id}"): {"json": {"classification": "internal"}},
    ("PATCH", "/mentions/{mention_id}/status"): {"json": {"status": "dismissed"}},
    ("PATCH", "/mentions/{mention_id}/response/draft"): {"json": {"text": "Withdrawals work normally."}},
    ("POST", "/mentions/{mention_id}/response/decision"): {"json": {"approve": True}},
}
ANALYST_STATUS = {("GET", "/me"): 200, ("POST", "/mentions/{mention_id}/response/decision"): 403}


def concrete(path):
    return re.sub(r"\{(\w+)\}", lambda m: PATH_VALUES.get(m[1], "id-1"), path)


@pytest.mark.parametrize("method,path", ROUTES, ids=ROUTE_IDS)
def test_every_route_requires_a_token(client, method, path):
    r = client.request(method, concrete(path))
    # The Meta webhook authenticates by provider signature instead of a user JWT (not implemented yet).
    assert r.status_code == (501 if path == WEBHOOK else 401), r.text


@pytest.mark.parametrize("method,path", ROUTES, ids=ROUTE_IDS)
def test_every_route_rejects_non_google_users(client, method, path):
    r = client.request(method, concrete(path), headers=bearer(hs256(app_metadata={"provider": "email"})))
    assert r.status_code == (501 if path == WEBHOOK else 403), r.text


@pytest.mark.parametrize("method,path", ROUTES, ids=ROUTE_IDS)
def test_authorized_request_reaches_handler(client, analyst, method, path):
    key = (method, path.removeprefix(API))
    r = client.request(method, concrete(path), headers=analyst, **VALID_REQUEST.get(key, {}))
    assert r.status_code == ANALYST_STATUS.get(key, 501), r.text


def test_decision_requires_compliance_role(client, analyst, compliance):
    url = f"{API}/mentions/m-1/response/decision"
    r = client.post(url, headers=analyst, json={"approve": True})
    assert r.status_code == 403 and r.json()["detail"] == "Compliance role required"
    assert client.post(url, headers=compliance, json={"approve": True}).status_code == 501
