"""Google News via Serper (platform = news)."""
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from app.config import settings
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


def fetch(company: dict) -> list[dict]:
    articles, seen = [], set()
    for q in queries_for(company):
        body = {"q": q, "num": 20, "tbs": "qdr:d"}
        if gl := COUNTRY_GL.get(company.get("country", "")):
            body["gl"] = gl
        r = httpx.post("https://google.serper.dev/news", headers={"X-API-KEY": settings.serper_api_key}, json=body, timeout=20)
        r.raise_for_status()
        for n in r.json().get("news", []):
            if n.get("link") and n["link"] not in seen:
                seen.add(n["link"])
                articles.append(n)
    items = []
    for n in articles:
        items.append({
            "platform": "news",
            "external_id": n["link"],
            "url": n["link"],
            "author": n.get("source") or "",
            "handle": urlparse(n["link"]).netloc,
            "text": " — ".join(x for x in (n.get("title"), n.get("snippet")) if x),
            "published_at": parse_date(n.get("date")),
            "reach": 0,  # Serper has no audience data
        })
    return items


def sync_company(company: dict) -> int:
    if not settings.serper_api_key:
        return 0
    try:
        return len(analyse_and_insert(company, fetch(company)))
    except Exception:
        log.exception("News sync failed for %s", company["id"])
        return 0
