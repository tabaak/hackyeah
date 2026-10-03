"""Google News via Serper (platform = news)."""
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.db import get_db
from app.services import relevance, rss
from app.services.ingest import analyse_and_insert
from app.services.timeutil import iso, now

log = logging.getLogger(__name__)

COUNTRY_GL = {"Poland": "pl", "Germany": "de", "Ukraine": "ua", "Lithuania": "lt", "Czechia": "cz",
              "United Kingdom": "uk", "United States": "us"}
UNITS = {"min": "minutes", "minute": "minutes", "hour": "hours", "day": "days", "week": "weeks"}


def parse_date(value: str | None) -> str:
    """Serper gives '3 hours ago' or 'Jan 5, 2026'; unknown formats count as now."""
    if value:
        m = re.match(r"(\d+)\s+(min|minute|hour|day|week)s?\s+ago", value.strip(), re.I)
        if m:
            return iso(now() - timedelta(**{UNITS[m.group(2).lower()]: int(m.group(1))}))
        for fmt in ("%b %d, %Y", "%d %b %Y", "%Y-%m-%d"):
            try:
                return iso(datetime.strptime(value.strip(), fmt).replace(tzinfo=timezone.utc))
            except ValueError:
                pass
    return iso(now())


def queries_for(company: dict) -> list[str]:
    """The company name, then its first other name. Plain text on purpose: Serper /news returns nothing for
    quoted phrases and for `"A" OR "B"` queries (checked: `"Goldman Sachs" OR "Goldman"` -> 0, `Goldman Sachs` -> 10)."""
    name = company["name"].strip()
    alias = next((a.strip() for a in company.get("aliases") or [] if a.strip() and a.strip().lower() != name.lower()), None)
    return [name, *([alias] if alias else [])]


def query_for(company: dict) -> str:
    return queries_for(company)[0]


WINDOW_DAYS = {"h": 1, "d": 1, "w": 7, "m": 30}


def _serper_items(company: dict) -> tuple[list[dict], set[str]]:
    """Serper returns 10 articles per page whatever `num` says, so pages are requested one by one (1 credit each)."""
    window = settings.news_window if settings.news_window in WINDOW_DAYS else "w"
    items, titles, seen = [], set(), set()
    for q in queries_for(company):
        for page in range(1, max(1, settings.serper_pages) + 1):
            body = {"q": q, "num": 10, "tbs": f"qdr:{window}", "page": page}
            if gl := COUNTRY_GL.get(company.get("country", "")):
                body["gl"] = gl
            r = httpx.post("https://google.serper.dev/news", headers={"X-API-KEY": settings.serper_api_key}, json=body, timeout=20)
            r.raise_for_status()
            articles = r.json().get("news", [])
            for n in articles:
                if not n.get("link") or n["link"] in seen:
                    continue
                seen.add(n["link"])
                titles.add(relevance.title_key(n.get("title") or ""))
                items.append({
                    "platform": "news",
                    "external_id": n["link"],
                    "url": n["link"],
                    "author": n.get("source") or "",
                    "handle": urlparse(n["link"]).netloc,
                    "text": " — ".join(x for x in (n.get("title"), n.get("snippet")) if x),
                    "published_at": parse_date(n.get("date")),
                    "reach": 0,  # Serper has no audience data
                    "avatar_url": None,
                    "media_urls": [n["imageUrl"]] if n.get("imageUrl") else [],
                })
            if len(articles) < 10:
                break  # last page
    return items, titles


def _stored_titles(company_id: str) -> set[str]:
    rows = (
        get_db().table("mentions").select("text").eq("company_id", company_id).eq("platform", "news")
        .order("published_at", desc=True).limit(2000).execute().data
    )
    return {relevance.title_key(r["text"].split(" — ")[0]) for r in rows}


def _rss_items(company: dict, known_titles: set[str]) -> list[dict]:
    """Free extra volume. The same article also arrives through Serper under another link, so skip known headlines."""
    days = WINDOW_DAYS.get(settings.news_window, 7)
    out, seen = [], set(known_titles)
    for q in queries_for(company):
        try:
            rows = rss.fetch(q, company.get("country", ""), days)
        except (httpx.HTTPError, ET.ParseError) as e:
            log.warning("Google News RSS failed for %r: %s", q, e)
            continue
        for row in rows:
            key = relevance.title_key(row["text"])
            if key in seen or not relevance.mentions_company(row["text"], company):
                continue
            seen.add(key)
            out.append({**row, "avatar_url": None, "media_urls": []})
    return out


def fetch(company: dict) -> list[dict]:
    items, titles = _serper_items(company) if settings.serper_api_key else ([], set())
    if settings.news_rss:
        items += _rss_items(company, titles | _stored_titles(company["id"]))
    return items


def sync_company(company: dict) -> int:
    if not settings.serper_api_key and not settings.news_rss:
        return 0
    try:
        return len(analyse_and_insert(company, fetch(company)))
    except Exception:
        log.exception("News sync failed for %s", company["id"])
        return 0
