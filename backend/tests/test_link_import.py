"""Add by link: POST /mentions/import and services/link_import (no network: fetchers are stubbed)."""
from types import SimpleNamespace

import httpx
import pytest

from app.deps import get_current_user
from app.main import app
from app.routers import companies as companies_router, feed
from app.schemas.auth import CurrentUser
from app.services import link_import as li
from tests.conftest import API, ORG_ID

COMPANY = {"id": "co-1", "organization_id": ORG_ID, "name": "Goldman Sachs"}
ROW = {
    "id": "m-1", "company_id": "co-1", "platform": "news", "author": "Reuters", "handle": "www.reuters.com",
    "text": "Goldman board discussed a plan", "published_at": "2026-09-28T10:00:00+00:00", "severity": "low",
    "verdict": "opinion", "reason": "No risk signals", "reach": 0, "clusters": None, "injection_suspected": False,
    "status": "new", "url": "https://www.reuters.com/a", "avatar_url": None, "media_urls": [],
}
PAGE = """<html><head><title>Fallback title</title>
<meta property="og:title" content="Bank freezes withdrawals &amp; blames IT">
<meta content="Customers could not withdraw cash for six hours." name="description">
<meta property="og:image" content="https://cdn.example.com/a.jpg">
<meta property="article:published_time" content="2026-10-03T08:15:00Z">
<meta property="og:url" content="https://news.example.com/bank-freeze">
<meta property="og:site_name" content="Example News">
</head><body></body></html>"""


# --- link parsing ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("url,tweet_id", [
    ("https://x.com/someone/status/1519480761749016577", "1519480761749016577"),
    ("https://twitter.com/someone/status/42?s=20", "42"),
    ("https://mobile.twitter.com/someone/statuses/7", "7"),
    ("http://www.x.com/someone/status/9/photo/1", "9"),
])
def test_x_status_links(url, tweet_id):
    assert li.X_STATUS.match(url).group(1) == tweet_id


@pytest.mark.parametrize("url", ["https://x.com/someone", "https://x.com/search?q=bank", "https://notx.com/a/status/1"])
def test_non_status_links_are_not_x_posts(url):
    assert not li.X_STATUS.match(url)


def test_parse_article_reads_open_graph():
    item = li.parse_article("https://news.example.com/bank-freeze?utm=1", PAGE)
    assert item["platform"] == "news"
    assert item["external_id"] == item["url"] == "https://news.example.com/bank-freeze"
    assert item["text"] == "Bank freezes withdrawals & blames IT — Customers could not withdraw cash for six hours."
    assert item["author"] == "Example News" and item["handle"] == "news.example.com"
    assert item["published_at"].startswith("2026-10-03T08:15:00")
    assert item["media_urls"] == ["https://cdn.example.com/a.jpg"] and item["reach"] == 0


def test_parse_article_falls_back_to_title_tag():
    item = li.parse_article("https://www.example.com/x", "<html><title>\n  Plain   title </title></html>")
    assert item["text"] == "Plain title" and item["author"] == "example.com" and item["media_urls"] == []


def test_parse_article_without_title_is_rejected():
    with pytest.raises(li.LinkImportError):
        li.parse_article("https://example.com", "<html><body>nothing</body></html>")


def test_bad_published_date_falls_back_to_now():
    page = '<meta property="og:title" content="T"><meta property="article:published_time" content="yesterday">'
    assert li.parse_article("https://example.com", page)["published_at"][:2] == "20"


@pytest.mark.parametrize("url,name", [
    ("https://www.facebook.com/page/posts/1", "Facebook"), ("https://m.facebook.com/story.php?id=1", "Facebook"),
    ("https://www.threads.net/@a/post/1", "Threads"), ("https://www.instagram.com/p/1", "Instagram"),
])
def test_unsupported_platforms_say_so(url, name):
    with pytest.raises(li.LinkImportError, match=name):
        li.item_for(url, "co-1")


@pytest.mark.parametrize("url", ["", "reuters.com/a", "ftp://example.com/a", "javascript:alert(1)"])
def test_only_web_links(url):
    with pytest.raises(li.LinkImportError, match="https://"):
        li.item_for(url, "co-1")


def test_item_for_routes_x_and_articles(monkeypatch):
    monkeypatch.setattr(li, "fetch_x", lambda url, tid, cid: {"via": "x", "id": tid})
    monkeypatch.setattr(li, "fetch_article", lambda url: {"via": "web", "url": url})
    assert li.item_for(" https://x.com/a/status/5 ", "co-1") == {"via": "x", "id": "5"}
    assert li.item_for("https://www.bankier.pl/a", "co-1") == {"via": "web", "url": "https://www.bankier.pl/a"}


def test_fetch_x_missing_post_is_a_clear_error(monkeypatch):
    monkeypatch.setattr(li.apify, "run_actor", lambda platform, body: [])
    with pytest.raises(li.LinkImportError, match="could not be loaded"):
        li.fetch_x("https://x.com/a/status/5", "5", "co-1")


# --- fetching: blocked sites go through search ----------------------------------------------------------------------

def _response(code: int, text: str = "", ctype: str = "text/html", url: str = "https://news.example.com/a") -> httpx.Response:
    return httpx.Response(code, text=text, headers={"content-type": ctype}, request=httpx.Request("GET", url))


def test_fetch_article_reads_the_page(monkeypatch):
    monkeypatch.setattr(li.httpx, "get", lambda *a, **k: _response(200, PAGE))
    assert li.fetch_article("https://news.example.com/a")["author"] == "Example News"


@pytest.mark.parametrize("code", [401, 403, 429])
def test_blocked_site_uses_search(monkeypatch, code):
    monkeypatch.setattr(li.httpx, "get", lambda *a, **k: _response(code))
    monkeypatch.setattr(li, "search_article", lambda url: {"via": "search", "url": url})
    assert li.fetch_article("https://www.reuters.com/a")["via"] == "search"


def test_other_http_errors_and_non_html_are_rejected(monkeypatch):
    monkeypatch.setattr(li.httpx, "get", lambda *a, **k: _response(404))
    with pytest.raises(li.LinkImportError, match="404"):
        li.fetch_article("https://example.com/a")
    monkeypatch.setattr(li.httpx, "get", lambda *a, **k: _response(200, "%PDF", "application/pdf"))
    with pytest.raises(li.LinkImportError, match="not a web page"):
        li.fetch_article("https://example.com/a.pdf")


def test_unreachable_page(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectTimeout("slow")
    monkeypatch.setattr(li.httpx, "get", boom)
    with pytest.raises(li.LinkImportError, match="ConnectTimeout"):
        li.fetch_article("https://example.com/a")


def _serper(monkeypatch, organic):
    monkeypatch.setattr(li.settings, "serper_api_key", "k")
    monkeypatch.setattr(li.httpx, "post", lambda *a, **k: httpx.Response(200, json={"organic": organic}, request=httpx.Request("POST", "https://s")))


def test_search_article_takes_the_same_page_only(monkeypatch):
    _serper(monkeypatch, [
        {"link": "https://www.instagram.com/p/1", "title": "Repost"},
        {"link": "https://www.reuters.com/a/", "title": "Goldman board", "snippet": "Plan for CEO", "date": "Sep 28, 2026"},
    ])
    item = li.search_article("https://reuters.com/a?utm_source=x")
    assert item["url"] == "https://www.reuters.com/a/" and item["text"] == "Goldman board — Plan for CEO"
    assert item["author"] == "reuters.com" and item["published_at"].startswith("2026-09-28")


def test_search_article_not_indexed(monkeypatch):
    _serper(monkeypatch, [{"link": "https://www.reuters.com/other", "title": "Other"}])
    with pytest.raises(li.LinkImportError, match="not indexed"):
        li.search_article("https://www.reuters.com/a")


def test_search_article_without_key(monkeypatch):
    monkeypatch.setattr(li.settings, "serper_api_key", "")
    with pytest.raises(li.LinkImportError, match="blocks automated reading"):
        li.search_article("https://www.reuters.com/a")


# --- POST /mentions/import --------------------------------------------------------------------------------------------

class FakeDB:
    """companies -> `companies` rows, mentions -> `mentions` rows; records filters."""

    def __init__(self, companies, mentions):
        self.tables, self.table_name, self.calls = {"companies": companies, "mentions": mentions}, None, []

    def table(self, name):
        self.table_name = name
        return self

    def __getattr__(self, name):
        return lambda *a, **k: (self.calls.append((self.table_name, name, a)) or self)

    def execute(self):
        return SimpleNamespace(data=self.tables[self.table_name])


@pytest.fixture
def importing(client, monkeypatch):
    def setup(companies=(COMPANY,), mentions=(ROW,), result=("news", "https://www.reuters.com/a", True), error=None):
        db = FakeDB(list(companies), list(mentions))
        monkeypatch.setattr(feed, "get_db", lambda: db)
        monkeypatch.setattr(companies_router, "get_db", lambda: db)

        def import_link(company, url):
            if error:
                raise li.LinkImportError(error)
            return result
        monkeypatch.setattr(feed.link_import, "import_link", import_link)
        return db
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id="u", organization_id=ORG_ID, name="A", email="a@b.c", role="analyst")
    yield client, setup
    app.dependency_overrides.pop(get_current_user, None)


def test_import_new_link_is_201_with_the_stored_mention(importing):
    client, setup = importing
    db = setup()
    r = client.post(f"{API}/mentions/import", json={"url": "https://www.reuters.com/a", "companyId": "co-1"})
    assert r.status_code == 201
    assert r.json()["id"] == "m-1" and r.json()["severity"] == "low"
    assert ("companies", "eq", ("organization_id", ORG_ID)) in db.calls
    assert ("mentions", "eq", ("external_id", "https://www.reuters.com/a")) in db.calls


def test_import_known_link_is_200(importing):
    client, setup = importing
    setup(result=("news", "https://www.reuters.com/a", False))
    assert client.post(f"{API}/mentions/import", json={"url": "https://www.reuters.com/a", "companyId": "co-1"}).status_code == 200


def test_import_for_another_organisations_company_is_404(importing):
    client, setup = importing
    setup(companies=())
    assert client.post(f"{API}/mentions/import", json={"url": "https://www.reuters.com/a", "companyId": "co-x"}).status_code == 404


def test_import_unreadable_link_is_422_with_the_reason(importing):
    client, setup = importing
    setup(error="Facebook links cannot be read directly.")
    r = client.post(f"{API}/mentions/import", json={"url": "https://facebook.com/a", "companyId": "co-1"})
    assert r.status_code == 422 and r.json()["detail"] == "Facebook links cannot be read directly."


def test_import_requires_url_and_company(importing):
    client, setup = importing
    setup()
    assert client.post(f"{API}/mentions/import", json={"url": "https://a.b"}).status_code == 422


def test_import_requires_sign_in(client):
    assert client.post(f"{API}/mentions/import", json={"url": "https://a.b", "companyId": "co-1"}).status_code in (401, 403)


def test_import_route_is_published():
    assert "post" in app.openapi()["paths"][f"{API}/mentions/import"]
