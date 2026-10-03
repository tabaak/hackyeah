"""Shared fixtures.

Unit tests never use the real .env values or the network: every test runs with TEST_SETTINGS.
Tests marked `live` keep the real settings and are skipped unless pytest runs with --live.
"""
import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi.testclient import TestClient

from app import deps, llm
from app.config import settings
from app.main import app

REPO = Path(__file__).resolve().parents[2]
API = "/api/v1"
SUPABASE_URL = "https://test-project.supabase.co"
JWT_SECRET = "test-jwt-secret-with-at-least-32-bytes"
USER_ID = "00000000-0000-4000-8000-000000000001"
ORG_ID = "00000000-0000-4000-8000-0000000000aa"

TEST_SETTINGS = {
    "supabase_url": SUPABASE_URL,
    "supabase_jwt_secret": JWT_SECRET,
    "serper_api_key": "test-serper-key",
    "openai_api_key": "sk-test",
    "openai_base_url": "https://api.openai.com/v1",
    "openai_model": "gpt-test",
    "local_llm_base_url": "http://localhost:8000/v1",
    "local_llm_model": "bonsai-2-27b",
    "local_llm_api_key": "not-needed",
    "llm_force": "",
    "llm_timeout_s": 5.0,
}

# The original cached functions, so tests can monkeypatch `deps._jwks_client` / `llm._client` safely.
_CACHED = (deps._jwks_client, llm._client)
DROP = object()  # claim value meaning "leave this claim out of the token"


def pytest_addoption(parser):
    parser.addoption("--live", action="store_true", default=False,
                     help="also run tests that call real services (Serper, OpenAI, local LLM, Supabase)")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return
    skip = pytest.mark.skip(reason="calls a real service: run with --live")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def test_settings(request, monkeypatch):
    for cached in _CACHED:
        cached.cache_clear()
    if "live" not in request.keywords:
        # Every setting is pinned; ones not listed (e.g. a newly added token) become "" so no real secret leaks in.
        for name, default in vars(type(settings)).items():
            if not name.startswith("_") and not callable(default):
                monkeypatch.setattr(settings, name, TEST_SETTINGS.get(name, "" if isinstance(default, str) else default))
    yield settings
    for cached in _CACHED:
        cached.cache_clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# --- Supabase-style access tokens -------------------------------------------------------------------

def make_claims(**overrides):
    """Claims of a provisioned Google user, as issued by Supabase with the custom access token hook."""
    now = int(time.time())
    claims = {
        "sub": USER_ID,
        "aud": "authenticated",
        "iss": f"{SUPABASE_URL}/auth/v1",
        "iat": now,
        "exp": now + 3600,
        "email": "anna.nowak@kestrel.example",
        "role": "authenticated",
        "app_metadata": {"provider": "google", "providers": ["google"]},
        "user_metadata": {"full_name": "Anna Nowak"},
        "user_role": "analyst",
        "organization_id": ORG_ID,
    }
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not DROP}


def hs256(secret=JWT_SECRET, **overrides):
    return jwt.encode(make_claims(**overrides), secret, algorithm="HS256")


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def analyst():
    return bearer(hs256())


@pytest.fixture
def compliance():
    return bearer(hs256(user_role="compliance"))


@pytest.fixture(scope="session")
def signing_keys():
    """alg -> (kid, private key) for the asymmetric keys Supabase uses."""
    return {
        "ES256": ("ec-test-key", ec.generate_private_key(ec.SECP256R1())),
        "RS256": ("rsa-test-key", rsa.generate_private_key(public_exponent=65537, key_size=2048)),
    }


@pytest.fixture
def jwks(monkeypatch, signing_keys):
    """Serve the test public keys as the project's JWKS without network. Returns the list of fetched URLs."""
    keys = []
    for alg, (kid, private_key) in signing_keys.items():
        algorithm = jwt.algorithms.ECAlgorithm if alg == "ES256" else jwt.algorithms.RSAAlgorithm
        keys.append(algorithm.to_jwk(private_key.public_key(), as_dict=True) | {"kid": kid, "alg": alg, "use": "sig"})
    fetched = []

    def fetch_data(self):
        fetched.append(self.uri)
        return {"keys": keys}

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", fetch_data)
    return fetched


def sign(alg, private_key, kid, **overrides):
    return jwt.encode(make_claims(**overrides), private_key, algorithm=alg, headers={"kid": kid})
