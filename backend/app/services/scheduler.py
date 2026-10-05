"""Repeats the collection in the background, one loop per source (SYNC_*_MINUTES, 0 = off).

A loop waits SYNC_STARTUP_DELAY_SECONDS (staggered per source), then for every organization with companies runs the
same job as POST /feed/sources/{platform}/sync, sleeps the interval, and repeats. It shares the "one run per
organization and platform" slot with manual syncs, so a run is never doubled.

Restart protection: the first pass after a restart skips an organization whose source already ingested something
within the interval (uvicorn --reload restarts on every code edit; each restart would otherwise spend credits).
"""
import asyncio
import logging

from app.config import settings
from app.db import get_db
from app.schemas.common import Platform
from app.services import social
from app.services.timeutil import now, to_ms

log = logging.getLogger(__name__)
STAGGER_S = 60


def intervals() -> dict[Platform, int]:
    """Minutes between runs per source; 0 = off."""
    return {
        Platform.news: settings.sync_news_minutes,
        Platform.x: settings.sync_x_minutes,
        Platform.facebook: settings.sync_facebook_minutes,
        Platform.reddit: settings.sync_reddit_minutes,
        Platform.bluesky: settings.sync_bluesky_minutes,
    }


def has_credentials(platform: Platform) -> bool:
    if platform == Platform.news:
        return bool(settings.serper_api_key or settings.news_rss)
    if platform in social.FREE:
        return True  # no key
    return bool(settings.apify_token)


def organizations() -> list[str]:
    rows = get_db().table("companies").select("organization_id").execute().data
    return sorted({r["organization_id"] for r in rows})


def ingested_recently(org_id: str, platform: Platform, minutes: int) -> bool:
    rows = (
        get_db().table("mentions").select("ingested_at").eq("organization_id", org_id).eq("platform", platform.value)
        .not_.like("external_id", "demo-%").order("ingested_at", desc=True).limit(1).execute().data
    )
    return bool(rows) and to_ms(rows[0]["ingested_at"]) > to_ms(now()) - minutes * 60_000


def run_platform(platform: Platform, minutes: int, *, first_pass: bool) -> int:
    """Blocking: one collection pass over every organization. Returns how many organizations were synced."""
    synced = 0
    for org_id in organizations():
        if first_pass and ingested_recently(org_id, platform, minutes):
            log.info("Scheduler: %s for organization %s ran within %d min, skipped after restart", platform.value, org_id, minutes)
            continue
        if not social.try_start(org_id, platform):
            continue  # a manual run is in progress
        social.sync_org(org_id, platform)  # releases the slot itself
        synced += 1
    return synced


async def platform_loop(platform: Platform, minutes: int, delay_s: int) -> None:
    await asyncio.sleep(delay_s)
    first = True
    while True:
        try:
            synced = await asyncio.to_thread(run_platform, platform, minutes, first_pass=first)
            log.info("Scheduler: %s pass done for %d organization(s); next in %d min", platform.value, synced, minutes)
        except Exception:
            log.exception("Scheduler: %s pass failed", platform.value)
        first = False
        await asyncio.sleep(minutes * 60)


def start() -> list[asyncio.Task]:
    """Create the loops for every enabled source that has credentials."""
    if not settings.sync_enabled:
        return []
    tasks = []
    for platform, minutes in intervals().items():
        if minutes <= 0:
            continue
        if not has_credentials(platform):
            log.warning("Scheduler: %s is set to every %d min but has no credentials; not scheduled", platform.value, minutes)
            continue
        delay = settings.sync_startup_delay_s + len(tasks) * STAGGER_S
        tasks.append(asyncio.create_task(platform_loop(platform, minutes, delay), name=f"sync-{platform.value}"))
        log.info("Scheduler: %s every %d min, first pass in %d s", platform.value, minutes, delay)
    return tasks
