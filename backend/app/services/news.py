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
from app.services.timeutil import iso, now, to_ms

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
HISTORY_DAYS = 14  # a company whose oldest stored article is newer than this gets one deep history run
_backfilled: set[str] = set()  # companies whose history run was attempted since this process started


def _serper_items(company: dict, window: str, pages: int) -> tuple[list[dict], set[str]]:
    """Serper returns 10 articles per page whatever `num` says, so pages are requested one by one (1 credit each)."""
    window = window if window in WINDOW_DAYS else "w"
    items, titles, seen = [], set(), set()
    for q in queries_for(company):
        for page in range(1, max(1, pages) + 1):
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
        .order("published_at", desc=True).limit(5000).execute().data
    )
    return {relevance.title_key(r["text"].split(" — ")[0]) for r in rows}


def _rss_items(company: dict, known_titles: set[str], *, days: int = 2, history_days: int = 0) -> list[dict]:
    """Free extra volume. The same article also arrives through Serper under another link, so skip known headlines.
    `history_days` > 0 walks back week by week (one request is capped at 100 articles)."""
    out, seen = [], set(known_titles)
    ranges = rss.weekly_ranges(history_days) if history_days else [None]
    for q in queries_for(company):
        for rng in ranges:
            try:
                rows = rss.fetch(q, company.get("country", ""), days, after=rng[0] if rng else None, before=rng[1] if rng else None)
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


def needs_backfill(company: dict) -> bool:
    """True when the company has no news older than HISTORY_DAYS yet and its history run was not attempted this session."""
    if settings.news_backfill_days <= 0 or company["id"] in _backfilled:
        return False
    rows = (
        get_db().table("mentions").select("published_at").eq("company_id", company["id"]).eq("platform", "news")
        .order("published_at").limit(1).execute().data
    )
    return not rows or to_ms(rows[0]["published_at"]) > to_ms(now()) - HISTORY_DAYS * 86_400_000


def fetch(company: dict, *, backfill: bool = False) -> list[dict]:
    """Regular run: the newest articles (NEWS_WINDOW, SERPER_PAGES). History run: a month of Serper pages plus
    NEWS_BACKFILL_DAYS of weekly RSS ranges."""
    window, pages = ("m", settings.news_backfill_pages) if backfill else (settings.news_window, settings.serper_pages)
    items, titles = _serper_items(company, window, pages) if settings.serper_api_key else ([], set())
    if settings.news_rss:
        known = titles | _stored_titles(company["id"])
        if backfill:
            items += _rss_items(company, known, history_days=settings.news_backfill_days)
        else:
            items += _rss_items(company, known, days=max(2, WINDOW_DAYS.get(window, 2)))
    return items


def sync_company(company: dict) -> int:
    if not settings.serper_api_key and not settings.news_rss:
        return 0
    try:
        backfill = needs_backfill(company)
        if backfill:
            _backfilled.add(company["id"])
            log.info("Loading news history (%d days) for %s", settings.news_backfill_days, company["name"])
        return len(analyse_and_insert(company, fetch(company, backfill=backfill)))
    except Exception:
        log.exception("News sync failed for %s", company["id"])
        return 0
