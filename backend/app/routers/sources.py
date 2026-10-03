"""8. Sources and ingestion (internal, no UI). All sources write to the single `mentions` table."""
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.common import Platform, SourceStatus, SyncRequested
from app.services import news
from app.services.timeutil import to_ms

router = APIRouter(prefix="/feed/sources", tags=["sources"])
NOT_CONFIGURED = "No connector configured for this platform"


# Declared before /{platform}/... so "facebook" is matched here.
@router.post("/facebook/webhook")
async def facebook_webhook(request: Request):
    """Meta notifications. Needs its own provider signature check; the user JWT does not replace it."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, NOT_CONFIGURED)


@router.post("/{platform}/sync", response_model=SyncRequested, status_code=202)
def sync(platform: Platform, user: CurrentUser = Depends(get_current_user)):
    """Collection run for every company of the caller's organization. Implemented: news (Serper)."""
    if platform != Platform.news:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, NOT_CONFIGURED)
    if not settings.serper_api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "SERPER_API_KEY is not set")
    companies = get_db().table("companies").select("*").eq("organization_id", user.organization_id).execute().data
    added = sum(news.sync_company(c) for c in companies)
    return SyncRequested(accepted=True, added=added)


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
        ok = bool(settings.serper_api_key)
        return SourceStatus(healthy=ok, last_sync_at=last, detail=None if ok else "SERPER_API_KEY is not set")
    return SourceStatus(healthy=False, last_sync_at=last, detail=NOT_CONFIGURED)
