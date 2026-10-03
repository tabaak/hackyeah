"""Google News RSS: free, up to 100 articles per request, no API key (platform = news)."""
import html
import re
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


def fetch(query: str, country: str = "", days: int = 7, client: httpx.Client | None = None) -> list[dict]:
    hl, gl, ceid = EDITIONS.get(country, DEFAULT_EDITION)
    own = client is None
    client = client or httpx.Client(timeout=20, follow_redirects=True)
    try:
        r = client.get(FEED_URL, params={"q": f"{query} when:{days}d", "hl": hl, "gl": gl, "ceid": ceid})
        r.raise_for_status()
        return parse(r.text)
    finally:
        if own:
            client.close()
