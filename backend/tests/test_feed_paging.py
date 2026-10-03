"""Paging back through history: GET /mentions?before_timestamp=..."""
from types import SimpleNamespace

import pytest

from app.deps import get_current_user
from app.main import app
from app.routers import feed
from app.schemas.auth import CurrentUser
from app.services.timeutil import from_ms
from tests.conftest import API, ORG_ID


class Recorder:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return lambda *a, **k: (self.calls.append((name, a)) or self)

    def execute(self):
        return SimpleNamespace(data=[])


@pytest.fixture
def signed_in(client, monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(feed, "get_db", lambda: rec)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id="u", organization_id=ORG_ID, name="A", email="a@b.c", role="analyst")
    yield client, rec
    app.dependency_overrides.pop(get_current_user, None)


def test_before_timestamp_filters_inclusively(signed_in):
    client, rec = signed_in
    assert client.get(f"{API}/mentions?limit=200&before_timestamp=1790000000000").status_code == 200
    assert ("lte", ("published_at", from_ms(1790000000000))) in rec.calls
    assert ("limit", (200,)) in rec.calls


def test_without_before_timestamp_there_is_no_upper_bound(signed_in):
    client, rec = signed_in
    client.get(f"{API}/mentions")
    assert not [c for c in rec.calls if c[0] in ("lte", "lt")]


def test_before_and_since_combine(signed_in):
    client, rec = signed_in
    client.get(f"{API}/mentions?since_timestamp=1780000000000&before_timestamp=1790000000000")
    assert ("gt", ("published_at", from_ms(1780000000000))) in rec.calls and ("lte", ("published_at", from_ms(1790000000000))) in rec.calls


def test_before_timestamp_must_be_a_number(signed_in):
    client, _ = signed_in
    assert client.get(f"{API}/mentions?before_timestamp=yesterday").status_code == 422
