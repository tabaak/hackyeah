"""4. Live feed of mentions."""
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.deps import not_implemented
from app.schemas.common import MentionStatus, Platform, Severity
from app.schemas.feed import Mention, MentionStatusUpdate

router = APIRouter(tags=["mentions"])


@router.get("/mentions", response_model=list[Mention])
def list_mentions(
    company_id: str | None = None,
    severity: Severity | None = None,
    platform: Platform | None = None,
    status: MentionStatus | None = None,
    since_timestamp: int | None = None,
    since_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
):
    not_implemented()


# Declared before /mentions/{mention_id} so "stream" is not parsed as an id.
@router.get("/mentions/stream", response_class=StreamingResponse)
def stream_mentions(company_id: str | None = None):
    """Optional SSE alternative to polling with `since_id`."""
    not_implemented()


@router.get("/mentions/{mention_id}", response_model=Mention)
def get_mention(mention_id: str):
    not_implemented()


@router.patch("/mentions/{mention_id}/status", response_model=Mention)
def update_mention_status(mention_id: str, body: MentionStatusUpdate):
    not_implemented()
