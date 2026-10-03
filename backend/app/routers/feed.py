"""4. Live Feed and Dashboard. Owners: Vitya (DB), Max (web/Flutter)."""
from fastapi import APIRouter, Query

from app.deps import not_implemented
from app.schemas.common import Platform, Sentiment
from app.schemas.feed import DashboardSummary, FeedPage, Mention

router = APIRouter(tags=["feed"])


@router.get("/feed", response_model=FeedPage)
def list_feed(
    limit: int = Query(50, ge=1, le=200),
    since_id: str | None = None,
    since_timestamp: str | None = None,
    platform: Platform | None = None,  # omitted = all
    sentiment: Sentiment | None = None,
):
    not_implemented()


@router.get("/feed/{mention_id}", response_model=Mention)
def get_mention(mention_id: str):
    not_implemented()


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary():
    not_implemented()
