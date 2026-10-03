"""8. Sources and ingestion (internal, no UI). All sources write to the single `mentions` table."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.common import Platform, SourceStatus, SyncRequested
from app.services import social
from app.services.timeutil import to_ms

router = APIRouter(prefix="/feed/sources", tags=["sources"])
NOT_CONFIGURED = "No connector configured for this platform"


# Declared before /{platform}/... so "facebook" is matched here.
@router.post("/facebook/webhook")
async def facebook_webhook(request: Request):
    """Meta notifications. Needs its own provider signature check; the user JWT does not replace it."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, NOT_CONFIGURED)


@router.post("/{platform}/sync", response_model=SyncRequested, status_code=202)
def sync(platform: Platform, background: BackgroundTasks, user: CurrentUser = Depends(get_current_user)):
    """Collection run for every company of the caller's organization. news (Serper + Google News RSS) and x / facebook
    (Apify) take minutes (one LLM call per risky item) and cost credits, so they run in the background:
    `added` is 0, watch the feed and `status`; 409 while a run of the same platform is in progress."""
    if platform in social.BACKGROUND:
        if platform == Platform.news and not (settings.serper_api_key or settings.news_rss):
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "SERPER_API_KEY is not set and NEWS_RSS is off")
        if platform != Platform.news and not settings.apify_token:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "APIFY_TOKEN is not set")
        if not social.try_start(user.organization_id, platform):
            raise HTTPException(status.HTTP_409_CONFLICT, f"A {platform.value} sync is already running")
        background.add_task(social.sync_org, user.organization_id, platform)
        return SyncRequested(accepted=True, added=0)
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, NOT_CONFIGURED)


@router.get("/{platform}/status", response_model=SourceStatus)
def source_status(platform: Platform, user: CurrentUser = Depends(get_current_user)):
    """Whether a connector is configured, and when the platform last produced a mention for this organization."""
    rows = (
        get_db().table("mentions").select("ingested_at").eq("organization_id", user.organization_id)
        .eq("platform", platform.value).not_.like("external_id", "demo-%")
        .order("ingested_at", desc=True).limit(1).execute().data
    )
    last = to_ms(rows[0]["ingested_at"]) if rows else None
    if platform == Platform.news:
        ok = bool(settings.serper_api_key or settings.news_rss)
        return SourceStatus(healthy=ok, last_sync_at=last, detail=None if ok else "SERPER_API_KEY is not set and NEWS_RSS is off")
    if platform in social.PLATFORMS:
        ok = bool(settings.apify_token)
        return SourceStatus(healthy=ok, last_sync_at=last, detail=None if ok else "APIFY_TOKEN is not set")
    return SourceStatus(healthy=False, last_sync_at=last, detail=NOT_CONFIGURED)
