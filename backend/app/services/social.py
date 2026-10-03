"""Social posts (X, Facebook, Threads) through Apify, routed into the shared analysis + ingestion pipeline.

Runs are slow (30-300 s, plus one LLM call per new post) and cost Apify credits, so they run in the background,
one at a time per organization and platform, and only when someone calls POST /feed/sources/{platform}/sync.
"""
import logging
import re
import threading

from app.config import settings
from app.db import get_db
from app.schemas.common import Platform
from app.schemas.companies import CompanyDraft
from app.schemas.feed import Mention
from app.services import news
from app.services.ingest import analyse_and_insert
from app.services.timeutil import from_ms
from app.sources import apify

log = logging.getLogger(__name__)

PLATFORMS = (Platform.x, Platform.facebook, Platform.threads)
MIN_ALIAS_CHARS = 3  # shorter aliases ("GS") match too many unrelated posts to prove relevance

_running: set[tuple[str, str]] = set()
_lock = threading.Lock()


def try_start(org_id: str, platform: Platform) -> bool:
    """Claim the (organization, platform) slot; False when a run is already in progress."""
    with _lock:
        key = (org_id, platform.value)
        if key in _running:
            return False
        _running.add(key)
        return True


def finish(org_id: str, platform: Platform) -> None:
    with _lock:
        _running.discard((org_id, platform.value))


def mentions_company(text: str, company: dict) -> bool:
    """Search engines return namesakes and loosely related posts: keep a post only if it names the company."""
    names = [company["name"], *(a for a in company.get("aliases") or [] if len(a.strip()) >= MIN_ALIAS_CHARS)]
    return any(re.search(rf"(?<!\w){re.escape(n.strip())}(?!\w)", text, re.I) for n in names if n.strip())


def to_item(m: Mention) -> dict:
    """Mention (apify adapter) -> row shape expected by `analyse_and_insert`."""
    return {
        "platform": m.platform.value, "external_id": m.id, "url": m.url, "author": m.author, "handle": m.handle,
        "text": m.text, "published_at": from_ms(m.at), "reach": m.reach,
    }


def fetch(company: dict, platform: Platform) -> list[dict]:
    draft = CompanyDraft(
        name=company["name"], website=company.get("website") or "", aliases=company.get("aliases") or [],
        sector=company["sector"], country=company["country"], people=company.get("people") or [], topics=company.get("topics") or [],
    )
    posts = apify.search_posts(
        draft, company["id"], news.queries_for(company), platforms=(platform,),
        limit=settings.apify_limit, max_age_days=settings.apify_max_age_days,
    )
    relevant = [m for m in posts if mentions_company(m.text, company)]
    log.info("Apify %s for %s: %d posts, %d name the company", platform.value, company["name"], len(posts), len(relevant))
    return [to_item(m) for m in relevant]


def sync_company(company: dict, platform: Platform) -> int:
    if not settings.apify_token:
        return 0
    try:
        return len(analyse_and_insert(company, fetch(company, platform)))
    except Exception:
        log.exception("%s sync failed for %s", platform.value, company["id"])
        return 0


def sync_org(org_id: str, platform: Platform) -> None:
    """Background task: every company of the organization, one platform."""
    try:
        companies = get_db().table("companies").select("*").eq("organization_id", org_id).execute().data
        added = sum(sync_company(c, platform) for c in companies)
        log.info("%s sync for organization %s added %d mentions", platform.value, org_id, added)
    except Exception:
        log.exception("%s sync failed for organization %s", platform.value, org_id)
    finally:
        finish(org_id, platform)
