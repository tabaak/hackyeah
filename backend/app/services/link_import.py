"""Add one mention from a link, without waiting for search indexing (live demos, a post someone forwarded).

X posts are fetched by id through Apify (~2 s, ~$0.00015); any other web page is read from its OpenGraph tags (free).
Sites that block automated reading (Reuters, FT) are looked up on Google through Serper by their link (1 credit).
The item then goes through the usual analysis and ingestion, so it is scored, deduplicated and notified like any other.
"""
import html
import re
import time
from datetime import datetime
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.schemas.common import Platform
from app.services import social
from app.services.ingest import analyse_and_insert
from app.services.timeutil import from_ms, iso, now
from app.sources import apify, serper

X_STATUS = re.compile(r"^https?://(?:www\.|mobile\.)?(?:x|twitter)\.com/[^/]+/status(?:es)?/(\d+)", re.I)
UNSUPPORTED = {
    "facebook.com": "Facebook", "fb.com": "Facebook", "threads.net": "Threads", "threads.com": "Threads",
    "instagram.com": "Instagram", "tiktok.com": "TikTok", "linkedin.com": "LinkedIn",
}
MAX_HTML = 2_000_000
BLOCKED = {401, 403, 429, 451}  # bot protection or a paywall: the article exists, we just may not read it
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,pl;q=0.8",
}


class LinkImportError(ValueError):
    """The link cannot be imported; the message is shown to the user."""


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.").removeprefix("m.")


def fetch_x(url: str, tweet_id: str, company_id: str) -> dict:
    items = apify.run_actor(Platform.x, {"tweetIds": [tweet_id], "maxItems": 1})
    item = next((i for i in items if str(i.get("id")) == tweet_id), None)
    m = item and apify.to_mention(item, Platform.x, company_id, int(time.time() * 1000))
    if not m:
        raise LinkImportError("This X post could not be loaded. It may be deleted, private or from a suspended account.")
    return social.to_item(m)


def _meta(page: str, *names: str) -> str | None:
    for name in names:
        for pattern in (
            rf'<meta[^>]+(?:property|name)=["\']{re.escape(name)}["\'][^>]*content=["\']([^"\']*)["\']',
            rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']{re.escape(name)}["\']',
        ):
            m = re.search(pattern, page, re.I)
            if m and m.group(1).strip():
                return html.unescape(m.group(1).strip())
    return None


def news_item(link: str, title: str, snippet: str | None, source: str | None, published_at: str, image: str | None) -> dict:
    """Same row shape as the scheduled news search, so a later search hit for this link is a duplicate."""
    return {
        "platform": "news", "external_id": link, "url": link,
        "author": source or _host(link), "handle": urlparse(link).netloc,
        "text": f"{title} — {snippet}" if snippet and snippet != title else title,
        "published_at": published_at, "reach": 0,
        "avatar_url": None, "media_urls": [image] if image and image.startswith("http") else [],
    }


def parse_article(url: str, page: str) -> dict:
    title = _meta(page, "og:title", "twitter:title")
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
        title = html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else None
    if not title:
        raise LinkImportError("This page has no title to import.")
    description = _meta(page, "og:description", "description", "twitter:description")
    image = _meta(page, "og:image", "twitter:image")
    published = _meta(page, "article:published_time", "og:published_time", "date", "pubdate")
    try:
        published_at = iso(datetime.fromisoformat(published.replace("Z", "+00:00"))) if published else iso(now())
    except ValueError:
        published_at = iso(now())
    canonical = _meta(page, "og:url") or url
    return news_item(canonical if canonical.startswith("http") else url, title, description, _meta(page, "og:site_name"), published_at, image)


def _same_page(a: str, b: str) -> bool:
    key = lambda u: (_host(u), urlparse(u).path.rstrip("/"))
    return key(a) == key(b)


def search_article(url: str) -> dict:
    if not settings.serper_api_key:
        raise LinkImportError("This site blocks automated reading. Try an X post or another outlet.")
    try:
        r = httpx.post(serper.SERPER_SEARCH_URL, headers={"X-API-KEY": settings.serper_api_key}, json={"q": url, "num": 5}, timeout=20)
        r.raise_for_status()
        results = r.json().get("organic", [])
    except (httpx.HTTPError, ValueError) as e:
        raise LinkImportError(f"This site blocks automated reading and the search fallback failed ({type(e).__name__}).") from e
    hit = next((o for o in results if o.get("link") and _same_page(o["link"], url)), None)
    if not hit:
        raise LinkImportError("This site blocks automated reading and Google has not indexed this article yet. Try again in a few minutes.")
    published_at = from_ms(serper.parse_date(hit.get("date"), int(time.time() * 1000)))
    return news_item(hit["link"], hit.get("title", "").strip(), (hit.get("snippet") or "").strip(), None, published_at, hit.get("imageUrl"))


def fetch_article(url: str) -> dict:
    try:
        r = httpx.get(url, follow_redirects=True, timeout=15, headers=BROWSER_HEADERS)
    except httpx.HTTPError as e:
        raise LinkImportError(f"The page could not be reached ({type(e).__name__}).") from e
    if r.status_code in BLOCKED:
        return search_article(url)
    if r.status_code >= 400:
        raise LinkImportError(f"The page answered with HTTP {r.status_code}.")
    if "html" not in r.headers.get("content-type", "html"):
        raise LinkImportError("This link is not a web page.")
    return parse_article(str(r.url), r.text[:MAX_HTML])


def item_for(url: str, company_id: str) -> dict:
    url = url.strip()
    if not re.match(r"^https?://", url, re.I):
        raise LinkImportError("Paste a full link starting with https://")
    if m := X_STATUS.match(url):
        return fetch_x(url, m.group(1), company_id)
    host = _host(url)
    for domain, name in UNSUPPORTED.items():
        if host == domain or host.endswith("." + domain):
            raise LinkImportError(f"{name} links cannot be read directly. Paste an X post or a news article.")
    return fetch_article(url)


def import_link(company: dict, url: str) -> tuple[str, str, bool]:
    """Returns (platform, external_id, created). An already known link is not analysed again."""
    item = item_for(url, company["id"])
    inserted = analyse_and_insert(company, [item])
    return item["platform"], item["external_id"], bool(inserted)
