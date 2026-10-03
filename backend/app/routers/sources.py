"""8. Sources and ingestion (internal, no UI). All parsers write to the single `mentions` table."""
from fastapi import APIRouter, Depends, Request

from app.deps import get_current_user, not_implemented
from app.schemas.common import Platform, SourceStatus, SyncRequested

router = APIRouter(prefix="/feed/sources", tags=["sources"])


# Declared before /{platform}/... so "facebook" is matched here.
@router.post("/facebook/webhook")
async def facebook_webhook(request: Request):
    """Meta notifications. Needs its own provider signature check; the user JWT does not replace it."""
    not_implemented()


@router.post("/{platform}/sync", response_model=SyncRequested, status_code=202, dependencies=[Depends(get_current_user)])
def sync(platform: Platform):
    """Collection run for one platform (facebook, x, news via Serper/RSS, ...)."""
    not_implemented()


@router.get("/{platform}/status", response_model=SourceStatus, dependencies=[Depends(get_current_user)])
def status(platform: Platform):
    """Token validity, last sync, rate limits / remaining credits."""
    not_implemented()
