"""3. Sources and ingestion. All parsers write to the single `mentions` table (platform = facebook | twitter | gnews)."""
from fastapi import APIRouter, Request

from app.deps import not_implemented
from app.schemas.common import SourceStatus, SyncRequested
from app.schemas.feed import TestQuery, TestQueryResult

router = APIRouter(prefix="/feed/sources", tags=["sources"])


# --- Facebook (Vitya) ---
@router.post("/facebook/sync", response_model=SyncRequested, status_code=202)
def facebook_sync():
    not_implemented()


@router.post("/facebook/webhook")
async def facebook_webhook(request: Request):
    """Meta notifications. Needs its own provider signature check; the user JWT does not replace it."""
    not_implemented()


@router.get("/facebook/status", response_model=SourceStatus)
def facebook_status():
    not_implemented()


# --- Twitter (Yarik) ---
@router.post("/twitter/sync", response_model=SyncRequested, status_code=202)
def twitter_sync():
    not_implemented()


@router.get("/twitter/status", response_model=SourceStatus)
def twitter_status():
    not_implemented()


@router.post("/twitter/test-query", response_model=TestQueryResult)
def twitter_test_query(body: TestQuery):
    """Checks a search query without saving anything to the feed."""
    not_implemented()


# --- Google News via Serper (Max) ---
@router.post("/gnews/sync", response_model=SyncRequested, status_code=202)
def gnews_sync():
    not_implemented()


@router.get("/gnews/status", response_model=SourceStatus)
def gnews_status():
    """Includes the remaining Serper credits."""
    not_implemented()
