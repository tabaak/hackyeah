"""Background scheduler, deep news history and the notification age cutoff."""
import asyncio
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest

from app.schemas.common import Platform
from app.services import news, notifications, rss, scheduler, social
from app.services.timeutil import iso, now

COMPANY = {"id": "c1", "organization_id": "o1", "name": "Goldman Sachs", "aliases": ["Goldman"], "country": "United States"}


# --- intervals and start ----------------------------------------------------------------------------

@pytest.fixture
def cfg(monkeypatch):
    s = scheduler.settings
    for name, value in (("sync_enabled", True), ("sync_news_minutes", 60), ("sync_x_minutes", 180), ("sync_facebook_minutes", 720),
                        ("sync_threads_minutes", 0), ("sync_startup_delay_s", 120), ("serper_api_key", "k"), ("apify_token", "t")):
        monkeypatch.setattr(s, name, value)
    return s


def test_intervals_follow_settings(cfg):
    assert scheduler.intervals() == {Platform.news: 60, Platform.x: 180, Platform.facebook: 720, Platform.threads: 0}


def run_start(monkeypatch):
    started = []

    async def fake_loop(platform, minutes, delay):
        started.append((platform.value, minutes, delay))
        await asyncio.sleep(3600)

    monkeypatch.setattr(scheduler, "platform_loop", fake_loop)

    async def main():
        tasks = scheduler.start()
        await asyncio.sleep(0)
        names = sorted(t.get_name() for t in tasks)
        for t in tasks:
            t.cancel()
        return names

    return asyncio.run(main()), started


def test_start_creates_a_staggered_loop_per_enabled_source(cfg, monkeypatch):
    names, started = run_start(monkeypatch)
    assert names == ["sync-facebook", "sync-news", "sync-x"]  # threads is 0 = off
    assert started == [("news", 60, 120), ("x", 180, 180), ("facebook", 720, 240)]  # first pass staggered by a minute each


def test_start_does_nothing_when_disabled(cfg, monkeypatch):
    monkeypatch.setattr(cfg, "sync_enabled", False)
    assert run_start(monkeypatch) == ([], [])


def test_sources_without_credentials_are_not_scheduled(cfg, monkeypatch):
    monkeypatch.setattr(cfg, "apify_token", "")
    names, _ = run_start(monkeypatch)
    assert names == ["sync-news"]
    monkeypatch.setattr(cfg, "serper_api_key", "")
    monkeypatch.setattr(cfg, "news_rss", True)
    assert "sync-news" in run_start(monkeypatch)[0]  # RSS needs no key
    monkeypatch.setattr(cfg, "news_rss", False)
    assert run_start(monkeypatch)[0] == []


# --- one pass ---------------------------------------------------------------------------------------

@pytest.fixture
def slots(monkeypatch):
    monkeypatch.setattr(social, "_running", set())
    runs = []
    monkeypatch.setattr(scheduler.social, "sync_org", lambda org, p: (runs.append((org, p.value)), social.finish(org, p)))
    monkeypatch.setattr(scheduler, "organizations", lambda: ["o1", "o2"])
    return runs


def test_pass_syncs_every_organization(slots, monkeypatch):
    monkeypatch.setattr(scheduler, "ingested_recently", lambda *a: False)
    assert scheduler.run_platform(Platform.news, 60, first_pass=True) == 2
    assert slots == [("o1", "news"), ("o2", "news")]


def test_first_pass_skips_organizations_that_ingested_within_the_interval(slots, monkeypatch):
    monkeypatch.setattr(scheduler, "ingested_recently", lambda org, p, m: org == "o1")
    assert scheduler.run_platform(Platform.x, 180, first_pass=True) == 1 and slots == [("o2", "x")]
    slots.clear()
    assert scheduler.run_platform(Platform.x, 180, first_pass=False) == 2  # later passes always run


def test_pass_leaves_manual_runs_alone(slots, monkeypatch):
    monkeypatch.setattr(scheduler, "ingested_recently", lambda *a: False)
    assert social.try_start("o1", Platform.facebook)  # a manual sync of o1 is in progress
    assert scheduler.run_platform(Platform.facebook, 720, first_pass=False) == 1 and slots == [("o2", "facebook")]


class Chain:
    def __init__(self, rows):
        self.rows = rows

    def __getattr__(self, name):
        return self if name == "not_" else (lambda *a, **k: self)

    def execute(self):
        return SimpleNamespace(data=self.rows)


@pytest.mark.parametrize("minutes_ago,expected", [(10, True), (59, True), (61, False), (600, False)])
def test_ingested_recently(monkeypatch, minutes_ago, expected):
    row = {"ingested_at": iso(now() - timedelta(minutes=minutes_ago))}
    monkeypatch.setattr(scheduler, "get_db", lambda: Chain([row]))
    assert scheduler.ingested_recently("o1", Platform.news, 60) is expected


def test_never_ingested_is_not_recent(monkeypatch):
    monkeypatch.setattr(scheduler, "get_db", lambda: Chain([]))
    assert scheduler.ingested_recently("o1", Platform.news, 60) is False


def test_organizations_are_distinct_and_sorted(monkeypatch):
    monkeypatch.setattr(scheduler, "get_db", lambda: Chain([{"organization_id": "b"}, {"organization_id": "a"}, {"organization_id": "b"}]))
    assert scheduler.organizations() == ["a", "b"]


# --- the loop ---------------------------------------------------------------------------------------

def drive_loop(monkeypatch, run, stop_after):
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) >= stop_after:
            raise asyncio.CancelledError

    monkeypatch.setattr(scheduler.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(scheduler, "run_platform", run)

    async def main():
        with pytest.raises(asyncio.CancelledError):
            await scheduler.platform_loop(Platform.news, 30, 5)

    asyncio.run(main())
    return sleeps


def test_loop_waits_runs_and_repeats(monkeypatch):
    calls = []
    sleeps = drive_loop(monkeypatch, lambda p, m, first_pass: calls.append((p.value, m, first_pass)) or 1, stop_after=4)
    assert sleeps == [5, 1800, 1800, 1800]  # startup delay, then the interval
    assert calls == [("news", 30, True), ("news", 30, False), ("news", 30, False)]


def test_a_failing_pass_does_not_stop_the_loop(monkeypatch):
    calls = []

    def flaky(p, m, first_pass):
        calls.append(first_pass)
        if len(calls) == 1:
            raise RuntimeError("db down")
        return 1

    drive_loop(monkeypatch, flaky, stop_after=4)
    assert calls == [True, False, False]


# --- history run ------------------------------------------------------------------------------------

def stored_oldest(monkeypatch, days_ago):
    rows = [] if days_ago is None else [{"published_at": iso(now() - timedelta(days=days_ago))}]
    monkeypatch.setattr(news, "get_db", lambda: Chain(rows))


@pytest.fixture(autouse=True)
def clean_backfill(monkeypatch):
    monkeypatch.setattr(news, "_backfilled", set())
    monkeypatch.setattr(news.settings, "news_backfill_days", 60)
    monkeypatch.setattr(news.settings, "news_backfill_pages", 5)


@pytest.mark.parametrize("oldest,expected", [(None, True), (2, True), (13, True), (15, False), (80, False)])
def test_needs_backfill_until_there_is_history(monkeypatch, oldest, expected):
    stored_oldest(monkeypatch, oldest)
    assert news.needs_backfill(COMPANY) is expected


def test_backfill_can_be_switched_off_and_runs_once_per_session(monkeypatch):
    stored_oldest(monkeypatch, None)
    monkeypatch.setattr(news.settings, "news_backfill_days", 0)
    assert news.needs_backfill(COMPANY) is False
    monkeypatch.setattr(news.settings, "news_backfill_days", 60)
    news._backfilled.add("c1")
    assert news.needs_backfill(COMPANY) is False


def test_sync_runs_one_deep_pass_then_regular_ones(monkeypatch):
    stored_oldest(monkeypatch, 1)
    modes = []
    monkeypatch.setattr(news.settings, "serper_api_key", "k")
    monkeypatch.setattr(news, "fetch", lambda c, backfill=False: modes.append(backfill) or [])
    monkeypatch.setattr(news, "analyse_and_insert", lambda c, items: items)
    news.sync_company(COMPANY)
    news.sync_company(COMPANY)
    assert modes == [True, False]


def test_failed_history_run_is_not_retried_every_pass(monkeypatch):
    stored_oldest(monkeypatch, 1)
    monkeypatch.setattr(news.settings, "serper_api_key", "k")
    calls = []

    def boom(c, backfill=False):
        calls.append(backfill)
        raise httpx.ConnectError("down")

    monkeypatch.setattr(news, "fetch", boom)
    assert news.sync_company(COMPANY) == 0 and news.sync_company(COMPANY) == 0
    assert calls == [True, False]


def fetch_spy(monkeypatch):
    seen = SimpleNamespace(serper=[], rss=[])
    monkeypatch.setattr(news.settings, "serper_api_key", "k")
    monkeypatch.setattr(news.settings, "news_rss", True)
    monkeypatch.setattr(news, "_stored_titles", lambda cid: set())
    monkeypatch.setattr(news, "_serper_items", lambda c, window, pages: (seen.serper.append((window, pages)) or [], set()))
    monkeypatch.setattr(news, "_rss_items", lambda c, known, **kw: seen.rss.append(kw) or [])
    return seen


def test_regular_run_is_short_and_cheap(monkeypatch):
    seen = fetch_spy(monkeypatch)
    monkeypatch.setattr(news.settings, "news_window", "d")
    monkeypatch.setattr(news.settings, "serper_pages", 1)
    news.fetch(COMPANY)
    assert seen.serper == [("d", 1)] and seen.rss == [{"days": 2}]


def test_history_run_goes_back_months(monkeypatch):
    seen = fetch_spy(monkeypatch)
    news.fetch(COMPANY, backfill=True)
    assert seen.serper == [("m", 5)] and seen.rss == [{"history_days": 60}]


def test_rss_history_walks_week_by_week_and_dedupes(monkeypatch):
    calls = []

    def fake_fetch(query, country, days, client=None, *, after=None, before=None):
        calls.append((query, after, before))
        return [{"platform": "news", "external_id": f"{query}-{after}", "text": "Goldman Sachs news", "url": "u", "author": "a",
                 "handle": "h", "published_at": "x", "reach": 0}]

    monkeypatch.setattr(news.rss, "fetch", fake_fetch)
    out = news._rss_items(COMPANY, set(), history_days=60)
    assert len(calls) == 2 * 9  # two queries x nine weekly ranges
    assert len(out) == 1  # the same headline from every range is kept once
    assert all(a and b and (b - a).days <= 7 for _, a, b in calls)


# --- RSS ranges -------------------------------------------------------------------------------------

def test_weekly_ranges_cover_the_period_without_gaps():
    ranges = rss.weekly_ranges(60, today=date(2026, 10, 3))
    assert len(ranges) == 9 and ranges[0] == (date(2026, 9, 27), date(2026, 10, 4))  # newest first, ends tomorrow
    assert all(prev[0] == nxt[1] for prev, nxt in zip(ranges, ranges[1:]))  # contiguous
    assert (ranges[0][1] - ranges[-1][0]).days == 60
    assert rss.weekly_ranges(3, today=date(2026, 10, 3)) == [(date(2026, 10, 1), date(2026, 10, 4))]
    assert rss.weekly_ranges(0) == []


def test_rss_query_uses_the_range_operators():
    seen = []

    def handler(req):
        seen.append(req.url.params["q"])
        return httpx.Response(200, text="<rss><channel></channel></rss>")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rss.fetch("Pekao", "Poland", after=date(2026, 8, 1), before=date(2026, 8, 8), client=client)
        rss.fetch("Pekao", "Poland", 2, client)
    assert seen == ["Pekao after:2026-08-01 before:2026-08-08", "Pekao when:2d"]


# --- notifications: history must not alarm ----------------------------------------------------------

@pytest.fixture
def sent(monkeypatch):
    out = []
    monkeypatch.setattr(notifications, "notify", lambda org, kind, title, sev, mid, **kw: out.append(mid))
    monkeypatch.setattr(notifications.settings, "notify_max_age_hours", 72)
    return out


def test_only_recent_high_mentions_notify(sent):
    ago = lambda hours: iso(now() - timedelta(hours=hours))  # noqa: E731
    notifications.notify_high_mentions("o1", [
        {"id": "fresh", "severity": "high", "text": "t", "published_at": ago(2)},
        {"id": "edge", "severity": "high", "text": "t", "published_at": ago(71)},
        {"id": "old-news", "severity": "high", "text": "t", "published_at": ago(24 * 20)},
        {"id": "medium", "severity": "medium", "text": "t", "published_at": ago(1)},
        {"id": "no-date", "severity": "high", "text": "t"},
    ])
    assert sent == ["fresh", "edge", "no-date"]
