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


def query_for(company: dict) -> str:
    names = [company["name"], *(company.get("aliases") or [])]
    return " OR ".join(f'"{n}"' for n in dict.fromkeys(n.strip() for n in names if n.strip()))


def fetch(company: dict) -> list[dict]:
    body = {"q": query_for(company), "num": 20, "tbs": "qdr:d"}
    if gl := COUNTRY_GL.get(company.get("country", "")):
        body["gl"] = gl
    r = httpx.post("https://google.serper.dev/news", headers={"X-API-KEY": settings.serper_api_key}, json=body, timeout=20)
    r.raise_for_status()
    items = []
    for n in r.json().get("news", []):
        if not n.get("link"):
            continue
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
