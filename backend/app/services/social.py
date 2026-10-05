"""Social posts (X and Facebook through Apify; Bluesky and Reddit from free APIs), routed into the shared analysis + ingestion pipeline.

Runs are slow (30-300 s, plus one LLM call per new post) and cost Apify credits, so they run in the background,
one at a time per organization and platform, and only when someone calls POST /feed/sources/{platform}/sync.
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from app.config import settings
from app.db import get_db
from app.schemas.common import Platform
from app.schemas.companies import CompanyDraft
from app.schemas.feed import Mention
from app.services import bluesky, news, reddit, relevance
from app.services.ingest import analyse_and_insert
from app.services.timeutil import from_ms
from app.sources import apify

log = logging.getLogger(__name__)

PLATFORMS = (Platform.x, Platform.facebook)  # Apify
FREE = {Platform.bluesky: bluesky.fetch, Platform.reddit: reddit.fetch}  # no key, no cost
BACKGROUND = (*PLATFORMS, *FREE, Platform.news)  # everything that runs as a background job

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


def to_item(m: Mention) -> dict:
    """Mention (apify adapter) -> row shape expected by `analyse_and_insert`."""
    return {
        "platform": m.platform.value, "external_id": m.id, "url": m.url, "author": m.author, "handle": m.handle,
        "text": m.text, "published_at": from_ms(m.at), "reach": m.reach,
        "avatar_url": m.avatar_url, "media_urls": m.images,
    }


LIMITS = {  # read at call time so tests and env changes apply
    Platform.x: lambda: settings.apify_limit_x,
    Platform.facebook: lambda: settings.apify_limit_facebook,
}


def fetch(company: dict, platform: Platform) -> list[dict]:
    draft = CompanyDraft(
        name=company["name"], website=company.get("website") or "", aliases=company.get("aliases") or [],
        sector=company["sector"], country=company["country"], people=company.get("people") or [], topics=company.get("topics") or [],
    )
    posts = apify.search_posts(
        draft, company["id"], news.queries_for(company), platforms=(platform,),
        limit=LIMITS[platform](), max_age_days=settings.apify_max_age_days,
    )
    relevant = [m for m in posts if relevance.mentions_company(m.text, company)]
    log.info("Apify %s for %s: %d posts, %d name the company", platform.value, company["name"], len(posts), len(relevant))
    return [to_item(m) for m in relevant]


def sync_company(company: dict, platform: Platform) -> int:
    if platform == Platform.news:
        return news.sync_company(company)
    if platform in FREE:
        try:
            return len(analyse_and_insert(company, FREE[platform](company, news.queries_for(company))))
        except Exception:
            log.exception("%s sync failed for %s", platform.value, company["id"])
            return 0
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


def fill_feed(company: dict, platforms: list[Platform]) -> None:
    """Background task for a new company: the given sources at once, instead of waiting for the scheduler's next pass."""
    with ThreadPoolExecutor(len(platforms) or 1) as pool:
        list(pool.map(lambda p: sync_company(company, p), platforms))
