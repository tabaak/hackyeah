"""Apify social sources in the API: relevance filter, mapping, background sync endpoint, per-organization lock."""
from types import SimpleNamespace

import pytest

from app.deps import get_current_user
from app.main import app
from app.schemas.auth import CurrentUser
from app.schemas.common import Platform
from app.services import social
from app.sources import apify
from tests.conftest import API, ORG_ID

COMPANY = {"id": "c1", "name": "Goldman Sachs", "aliases": ["Goldman", "GS"], "website": "", "sector": "Banking",
           "country": "United States", "people": [], "topics": ["Data breach"]}
NOW = 1_800_000_000_000
TWEET = {"id": "1", "text": "Goldman Sachs data breach rumours", "url": "https://x.com/a/status/1",
         "createdAt": "Fri Oct 02 10:00:00 +0000 2026", "likeCount": 5, "retweetCount": 2, "replyCount": 1,
         "author": {"userName": "alice", "name": "Alice"}}


@pytest.fixture(autouse=True)
def clean_slots(monkeypatch):
    monkeypatch.setattr(social, "_running", set())


# --- relevance filter -------------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Goldman Sachs freezes withdrawals", True),
    ("goldman sachs, again", True),
    ("Goldman says rates will fall", True),             # alias
    ("Mr. Goldmann is a nice guy", False),               # namesake / longer word
    ("Goldmans Sachs?", False),
    ("The GS strategy of my gym", False),                # 2-char alias never counts
    ("Totally unrelated post about oil prices", False),
    ("#Goldman rally", True),
    ("(Goldman)", True),
])
def test_mentions_company(text, expected):
    assert social.mentions_company(text, COMPANY) is expected


def test_regex_metacharacters_in_names_are_escaped():
    assert social.mentions_company("Johnson & Johnson (J&J) recall", {"name": "Johnson & Johnson", "aliases": ["J&J"]})
    assert not social.mentions_company("anything", {"name": "A.B", "aliases": []}) and social.mentions_company("A.B news", {"name": "A.B", "aliases": []})
    assert not social.mentions_company("AxB news", {"name": "A.B", "aliases": []})


# --- mapping and fetch ------------------------------------------------------------------------------

def test_to_item_has_the_ingest_shape():
    m = apify.to_mention(TWEET, Platform.x, "c1", NOW)
    item = social.to_item(m)
    assert set(item) == {"platform", "external_id", "url", "author", "handle", "text", "published_at", "reach"}
    assert item["platform"] == "x" and item["external_id"] == m.id and item["reach"] == 8
    assert item["published_at"].startswith("2026-10-02T10:00:00")


def test_fetch_passes_bounds_and_filters_irrelevant_posts(monkeypatch):
    monkeypatch.setattr(social.settings, "apify_limit", 7)
    monkeypatch.setattr(social.settings, "apify_max_age_days", 14)
    seen = {}
    unrelated = apify.to_mention({**TWEET, "id": "2", "text": "Weather is nice today"}, Platform.x, "c1", NOW)
    related = apify.to_mention(TWEET, Platform.x, "c1", NOW)

    def fake_search(draft, company_id, queries, **kw):
        seen.update(company=draft.name, company_id=company_id, queries=queries, **kw)
        return [related, unrelated]

    monkeypatch.setattr(apify, "search_posts", fake_search)
    items = social.fetch(COMPANY, Platform.x)
    assert [i["external_id"] for i in items] == [related.id]
    assert seen == {"company": "Goldman Sachs", "company_id": "c1", "queries": ["Goldman Sachs", "Goldman"],
                    "platforms": (Platform.x,), "limit": 7, "max_age_days": 14}


# --- sync_company -----------------------------------------------------------------------------------

def test_sync_company_ingests_and_counts(monkeypatch):
    monkeypatch.setattr(social.settings, "apify_token", "t")
    monkeypatch.setattr(social, "fetch", lambda c, p: [{"external_id": "a"}, {"external_id": "b"}])
    monkeypatch.setattr(social, "analyse_and_insert", lambda c, items: items[:1])  # one was a duplicate
    assert social.sync_company(COMPANY, Platform.x) == 1


def test_sync_company_without_token_does_nothing(monkeypatch):
    monkeypatch.setattr(social.settings, "apify_token", "")
    monkeypatch.setattr(social, "fetch", lambda *a: pytest.fail("must not call Apify without a token"))
    assert social.sync_company(COMPANY, Platform.x) == 0


def test_sync_company_failure_is_contained(monkeypatch):
    monkeypatch.setattr(social.settings, "apify_token", "t")

    def boom(*a):
        raise RuntimeError("apify down")

    monkeypatch.setattr(social, "fetch", boom)
    assert social.sync_company(COMPANY, Platform.x) == 0


def test_sync_org_runs_every_company_and_always_releases_the_slot(monkeypatch):
    rows = [{"id": "c1"}, {"id": "c2"}]
    db = SimpleNamespace(table=lambda name: SimpleNamespace(select=lambda *a: SimpleNamespace(
        eq=lambda *a: SimpleNamespace(execute=lambda: SimpleNamespace(data=rows)))))
    monkeypatch.setattr(social, "get_db", lambda: db)
    called = []
    monkeypatch.setattr(social, "sync_company", lambda c, p: called.append(c["id"]) or 3)
    assert social.try_start("o1", Platform.x)
    social.sync_org("o1", Platform.x)
    assert called == ["c1", "c2"]
    assert social.try_start("o1", Platform.x)  # slot released

    monkeypatch.setattr(social, "get_db", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    social.sync_org("o1", Platform.x)
    assert social.try_start("o1", Platform.x)  # released even when the run crashed


def test_slots_are_per_organization_and_platform():
    assert social.try_start("o1", Platform.x)
    assert not social.try_start("o1", Platform.x)
    assert social.try_start("o2", Platform.x) and social.try_start("o1", Platform.facebook)
    social.finish("o1", Platform.x)
    assert social.try_start("o1", Platform.x)


# --- endpoint ---------------------------------------------------------------------------------------

@pytest.fixture
def signed_in(client):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="u1", organization_id=ORG_ID, name="Anna", email="a@b.c", role="analyst")
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def runs(monkeypatch):
    started = []
    monkeypatch.setattr(social, "sync_org", lambda org, platform: started.append((org, platform.value)))
    return started


@pytest.mark.parametrize("platform", ["x", "facebook", "threads"])
def test_sync_starts_a_background_run(signed_in, runs, monkeypatch, platform):
    monkeypatch.setattr(social.settings, "apify_token", "t")
    r = signed_in.post(f"{API}/feed/sources/{platform}/sync")
    assert r.status_code == 202 and r.json() == {"accepted": True, "added": 0}
    assert runs == [(ORG_ID, platform)]


def test_second_sync_while_running_is_409(signed_in, runs, monkeypatch):
    monkeypatch.setattr(social.settings, "apify_token", "t")
    assert signed_in.post(f"{API}/feed/sources/x/sync").status_code == 202
    r = signed_in.post(f"{API}/feed/sources/x/sync")  # the fake run never released the slot
    assert r.status_code == 409 and "already running" in r.json()["detail"]
    assert len(runs) == 1
    assert signed_in.post(f"{API}/feed/sources/facebook/sync").status_code == 202  # other platform is independent


def test_sync_without_token_is_503_and_starts_nothing(signed_in, runs, monkeypatch):
    monkeypatch.setattr(social.settings, "apify_token", "")
    r = signed_in.post(f"{API}/feed/sources/threads/sync")
    assert r.status_code == 503 and "APIFY_TOKEN" in r.json()["detail"]
    assert runs == [] and social.try_start(ORG_ID, Platform.threads)  # no slot was taken


@pytest.mark.parametrize("platform", ["reddit", "telegram", "tiktok", "linkedin"])
def test_other_platforms_are_still_501(signed_in, runs, monkeypatch, platform):
    monkeypatch.setattr(social.settings, "apify_token", "t")
    assert signed_in.post(f"{API}/feed/sources/{platform}/sync").status_code == 501 and runs == []


def test_sync_requires_a_user(client, runs):
    assert client.post(f"{API}/feed/sources/x/sync").status_code == 401 and runs == []


class FakeChain:
    def __getattr__(self, name):
        return self if name == "not_" else (lambda *a, **k: self)

    def execute(self):
        return SimpleNamespace(data=[])


@pytest.mark.parametrize("token,healthy", [("t", True), ("", False)])
def test_status_reflects_the_token(signed_in, monkeypatch, token, healthy):
    from app.routers import sources
    monkeypatch.setattr(sources, "get_db", lambda: FakeChain())
    monkeypatch.setattr(social.settings, "apify_token", token)
    body = signed_in.get(f"{API}/feed/sources/x/status").json()
    assert body["healthy"] is healthy and body["lastSyncAt"] is None
    assert ("APIFY_TOKEN" in (body["detail"] or "")) is (not healthy)
