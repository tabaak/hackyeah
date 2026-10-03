"""Serper Google News ingestion (app/sources/serper.py), offline: recorded response + fake HTTP transport."""
import json
from pathlib import Path

import httpx
import pytest

from app.schemas.common import MentionStatus, Platform, Severity, Verdict
from app.sources.serper import (MOCK_COMPANY, SERPER_NEWS_URL, SerperError, build_queries, parse_date, search_news,
                                to_mention)

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "serper_news.json").read_text())
NOW = 1_800_000_000_000
MINUTE, HOUR, DAY = 60_000, 3_600_000, 86_400_000


def company(**overrides):
    return MOCK_COMPANY.model_copy(update=overrides)


class FakeSerper:
    """Transport that records requests and answers from a queue (default: the recorded fixture)."""

    def __init__(self, *responses):
        self.requests, self.responses = [], list(responses)

    def __call__(self, request):
        self.requests.append(request)
        response = self.responses.pop(0) if self.responses else httpx.Response(200, json=FIXTURE)
        if isinstance(response, Exception):
            raise response
        return response

    @property
    def bodies(self):
        return [json.loads(r.content) for r in self.requests]

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self))


def article(link, date="1 hour ago", **extra):
    return {"title": f"Title {link}", "link": link, "snippet": "Snippet.", "date": date, "source": "Daily Ledger"} | extra


# --- queries ----------------------------------------------------------------------------------------

def test_default_queries():
    assert build_queries(MOCK_COMPANY) == ["Bank Pekao", "Pekao", "Bank Pekao Frozen withdrawals", "Bank Pekao Data breach"]


def test_queries_are_plain_text():
    # Measured on Serper: quoted phrases and OR-queries returned 0 results.
    assert all('"' not in q and " OR " not in q for q in build_queries(MOCK_COMPANY))


@pytest.mark.parametrize("overrides,expected", [
    ({"aliases": []}, ["Bank Pekao", "Bank Pekao Frozen withdrawals", "Bank Pekao Data breach"]),
    ({"aliases": ["bank pekao", "Pekao"]}, ["Bank Pekao", "Pekao", "Bank Pekao Frozen withdrawals", "Bank Pekao Data breach"]),
    ({"aliases": ["  ", "Pekao"]}, ["Bank Pekao", "Pekao", "Bank Pekao Frozen withdrawals", "Bank Pekao Data breach"]),
    ({"name": "  Bank Pekao ", "aliases": [" Pekao "]}, ["Bank Pekao", "Pekao", "Bank Pekao Frozen withdrawals", "Bank Pekao Data breach"]),
    ({"topics": []}, ["Bank Pekao", "Pekao"]),
    ({"topics": ["Data breach", "Data breach"]}, ["Bank Pekao", "Pekao", "Bank Pekao Data breach"]),
], ids=["no-aliases", "alias-equal-to-name", "blank-alias", "whitespace", "no-topics", "duplicate-topics"])
def test_query_variants(overrides, expected):
    assert build_queries(company(**overrides)) == expected


@pytest.mark.parametrize("limit", [1, 2, 3])
def test_query_cap(limit):
    assert len(build_queries(MOCK_COMPANY, max_queries=limit)) == limit


# --- dates ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("28 minutes ago", NOW - 28 * MINUTE),  # actual Serper format for fresh articles
    ("1 minute ago", NOW - MINUTE),
    ("5 mins ago", NOW - 5 * MINUTE),
    ("1 min ago", NOW - MINUTE),
    ("30 seconds ago", NOW - 30_000),
    ("3 hours ago", NOW - 3 * HOUR),
    ("1 hr ago", NOW - HOUR),
    ("4 days ago", NOW - 4 * DAY),
    ("1 week ago", NOW - 7 * DAY),
    ("3 weeks ago", NOW - 21 * DAY),
    ("1 month ago", NOW - 30 * DAY),
    ("2 years ago", NOW - 730 * DAY),
    ("  2 Days Ago ", NOW - 2 * DAY),
    ("yesterday", NOW - DAY),
    ("Oct 2, 2026", 1_790_899_200_000),
    ("2 Oct 2026", 1_790_899_200_000),
    ("2026-10-02", 1_790_899_200_000),
    ("in 2 days", NOW),
    ("garbage", NOW),
    ("", NOW),
    (None, NOW),
])
def test_parse_date(text, expected):
    assert parse_date(text, NOW) == expected


# --- article -> mention -----------------------------------------------------------------------------

def test_article_to_mention():
    m = to_mention(FIXTURE["news"][0], "c-1", NOW)
    a = FIXTURE["news"][0]
    assert m.platform == Platform.news and m.company_id == "c-1"
    assert m.url == a["link"] and m.handle == "media.pekao.com.pl"
    assert m.author == a["source"]
    assert m.text == f"{a['title']}. {a['snippet']}"
    assert m.at == NOW - 4 * DAY
    assert (m.severity, m.verdict, m.status) == (Severity.low, Verdict.insufficient_evidence, MentionStatus.new)
    assert (m.reason, m.reach, m.cluster, m.injection) == ("", 0, None, False)


def test_mention_id_is_stable_and_company_scoped():
    a = article("https://news.example/a")
    assert to_mention(a, "c-1", NOW).id == to_mention(a, "c-1", NOW + DAY).id
    assert to_mention(a, "c-1", NOW).id != to_mention(a, "c-2", NOW).id
    assert to_mention(a, "c-1", NOW).id != to_mention(article("https://news.example/b"), "c-1", NOW).id


def test_mention_fallbacks():
    m = to_mention({"link": "https://www.bankier.pl/x", "title": " Only title "}, "c-1", NOW)
    assert m.handle == "bankier.pl" and m.author == "bankier.pl"  # www. stripped; no source -> host
    assert m.text == "Only title"
    assert m.at == NOW  # no date


# --- search -----------------------------------------------------------------------------------------

def test_search_request_shape(test_settings):
    fake = FakeSerper()
    with fake.client() as client:
        search_news(MOCK_COMPANY, "c-1", client=client)
    assert [str(r.url) for r in fake.requests] == [SERPER_NEWS_URL] * 4
    assert all(r.method == "POST" and r.headers["x-api-key"] == test_settings.serper_api_key for r in fake.requests)
    assert fake.bodies[0] == {"q": "Bank Pekao", "num": 10, "tbs": "qdr:w", "gl": "pl"}
    assert [b["q"] for b in fake.bodies] == build_queries(MOCK_COMPANY)


def test_explicit_queries_are_used_verbatim():
    fake = FakeSerper()
    with fake.client() as client:
        search_news(MOCK_COMPANY, "c-1", queries=["Pekao bank run"], client=client)
    assert [b["q"] for b in fake.bodies] == ["Pekao bank run"]


@pytest.mark.parametrize("period,tbs", [("h", "qdr:h"), ("d", "qdr:d"), ("w", "qdr:w"), ("m", "qdr:m")])
def test_period(period, tbs):
    fake = FakeSerper()
    with fake.client() as client:
        search_news(MOCK_COMPANY, "c-1", period=period, per_query=5, max_queries=1, client=client)
    assert fake.bodies == [{"q": "Bank Pekao", "num": 5, "tbs": tbs, "gl": "pl"}]


def test_invalid_period_fails_before_any_request():
    fake = FakeSerper()
    with fake.client() as client, pytest.raises(ValueError):
        search_news(MOCK_COMPANY, "c-1", period="year", client=client)
    assert fake.requests == []


@pytest.mark.parametrize("country,gl", [("Poland", "pl"), ("United Kingdom", "gb"), ("Global", None), ("Atlantis", None)])
def test_country_region(country, gl):
    fake = FakeSerper()
    with fake.client() as client:
        search_news(company(country=country), "c-1", max_queries=1, client=client)
    assert fake.bodies[0].get("gl") == gl


def test_results_deduplicated_sorted_and_linkless_skipped():
    fake = FakeSerper(
        httpx.Response(200, json={"news": [article("https://a.example/1", "3 days ago"), article("https://a.example/2", "1 hour ago")]}),
        httpx.Response(200, json={"news": [article("https://a.example/1", "3 days ago"), {"title": "no link"}]}),
        httpx.Response(200, json={}),
    )
    with fake.client() as client:
        found = search_news(MOCK_COMPANY, "c-1", max_queries=3, client=client)
    assert [m.url for m in found] == ["https://a.example/2", "https://a.example/1"]
    assert len({m.id for m in found}) == 2


def test_recorded_response_maps_cleanly():
    fake = FakeSerper()
    with fake.client() as client:
        found = search_news(MOCK_COMPANY, "c-1", client=client)
    assert len(found) == len(FIXTURE["news"])  # the same articles for every query collapse to one each
    assert [m.at for m in found] == sorted((m.at for m in found), reverse=True)
    dumped = found[0].model_dump(by_alias=True)
    assert dumped["companyId"] == "c-1" and dumped["url"].startswith("https://")


@pytest.mark.parametrize("response,message", [
    (httpx.Response(403, text='{"message": "Unauthorized."}'), "Serper 403"),
    (httpx.Response(429, text="Too many requests"), "Serper 429"),
    (httpx.Response(200, text="<html>proxy error</html>"), "Serper request failed"),
    (httpx.ConnectError("no route to host"), "Serper request failed"),
    (httpx.ReadTimeout("timed out"), "Serper request failed"),
], ids=["forbidden", "rate-limited", "not-json", "connection-error", "timeout"])
def test_errors_raise_serper_error(response, message):
    fake = FakeSerper(response)
    with fake.client() as client, pytest.raises(SerperError, match=message):
        search_news(MOCK_COMPANY, "c-1", client=client)
    assert len(fake.requests) == 1  # stops at the first failure


def test_missing_api_key(test_settings, monkeypatch):
    monkeypatch.setattr(test_settings, "serper_api_key", "")
    with pytest.raises(SerperError, match="SERPER_API_KEY"):
        search_news(MOCK_COMPANY, "c-1")


def test_own_client_is_closed(monkeypatch):
    fake, created, real_client = FakeSerper(), [], httpx.Client

    def factory(**kwargs):
        created.append(real_client(transport=httpx.MockTransport(fake), **kwargs))
        return created[-1]

    monkeypatch.setattr(httpx, "Client", factory)
    search_news(MOCK_COMPANY, "c-1", max_queries=1)
    assert len(created) == 1 and created[0].is_closed and len(fake.requests) == 1
