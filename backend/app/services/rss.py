"""Google News RSS: free, up to 100 articles per request, no API key (platform = news)."""
import html
import re
from datetime import date, timedelta
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx

from app.services.timeutil import iso

FEED_URL = "https://news.google.com/rss/search"
# country -> (hl, gl, ceid): the edition of Google News to search
EDITIONS = {
    "Poland": ("pl", "PL", "PL:pl"), "Germany": ("de", "DE", "DE:de"), "Ukraine": ("uk", "UA", "UA:uk"),
    "Lithuania": ("lt", "LT", "LT:lt"), "Czechia": ("cs", "CZ", "CZ:cs"), "United Kingdom": ("en-GB", "GB", "GB:en"),
    "United States": ("en-US", "US", "US:en"),
}
DEFAULT_EDITION = ("en-US", "US", "US:en")


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def parse(xml_text: str) -> list[dict]:
    """RSS items -> ingestion rows (platform, external_id, url, author, handle, text, published_at, reach)."""
    items = []
    for node in ET.fromstring(xml_text).iter("item"):
        title = _strip_html(node.findtext("title") or "")
        link = (node.findtext("link") or "").strip()
        source = node.find("source")
        outlet = _strip_html(source.text or "") if source is not None else ""
        if outlet and title.endswith(f" - {outlet}"):
            title = title[: -len(f" - {outlet}")].strip()  # Google appends the outlet to every headline
        if not (title and link):
            continue
        try:
            published = iso(parsedate_to_datetime(node.findtext("pubDate") or ""))
        except (TypeError, ValueError):
            continue
        items.append({
            "platform": "news",
            "external_id": (node.findtext("guid") or link).strip(),
            "url": link,
            "author": outlet,
            "handle": urlparse(source.get("url", "")).netloc if source is not None else "",
            "text": title,
            "published_at": published,
            "reach": 0,
        })
    return items


def fetch(query: str, country: str = "", days: int = 7, client: httpx.Client | None = None,
          *, after: date | None = None, before: date | None = None) -> list[dict]:
    """`days` = the last N days, or an explicit [after, before) range. A single request returns at most 100 articles,
    and `when:90d` does not return the newest 100 of 90 days: deep history needs short ranges (see `weekly_ranges`)."""
    hl, gl, ceid = EDITIONS.get(country, DEFAULT_EDITION)
    window = f"after:{after.isoformat()} before:{before.isoformat()}" if after and before else f"when:{days}d"
    own = client is None
    client = client or httpx.Client(timeout=20, follow_redirects=True)
    try:
        r = client.get(FEED_URL, params={"q": f"{query} {window}", "hl": hl, "gl": gl, "ceid": ceid})
        r.raise_for_status()
        return parse(r.text)
    finally:
        if own:
            client.close()


def weekly_ranges(days: int, today: date | None = None) -> list[tuple[date, date]]:
    """[after, before) week ranges covering the last `days` days, newest first; the last one ends tomorrow."""
    end = (today or date.today()) + timedelta(days=1)
    out = []
    while days > 0:
        step = min(7, days)
        out.append((end - timedelta(days=step), end))
        end -= timedelta(days=step)
        days -= step
    return out
