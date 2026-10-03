"""4. Live feed of mentions."""
import asyncio
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.db import get_db, not_found
from app.deps import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.common import MentionStatus, Platform, Severity
from app.schemas.feed import Mention, MentionStatusUpdate
from app.services import mappers
from app.services.timeutil import from_ms, iso, now

router = APIRouter(tags=["mentions"])
STREAM_POLL_S = 5


def load_mention(mention_id: str, user: CurrentUser, select: str = mappers.MENTION_SELECT) -> dict:
    rows = get_db().table("mentions").select(select).eq("id", mention_id).eq("organization_id", user.organization_id).execute().data
    if not rows:
        raise not_found("Mention")
    return rows[0]


def query_mentions(user: CurrentUser, company_id=None, severity=None, platform=None, status=None, since: str | None = None, limit: int = 50, before: str | None = None) -> list[dict]:
    q = get_db().table("mentions").select(mappers.MENTION_SELECT).eq("organization_id", user.organization_id)
    if company_id:
        q = q.eq("company_id", company_id)
    if severity:
        q = q.eq("severity", severity)
    if platform:
        q = q.eq("platform", platform)
    if status:
        q = q.eq("status", status)
    if since:
        q = q.gt("published_at", since)
    if before:
        q = q.lte("published_at", before)  # inclusive: mentions sharing the last timestamp of a page are not skipped
    return q.order("published_at", desc=True).limit(limit).execute().data


@router.get("/mentions", response_model=list[Mention])
def list_mentions(
    company_id: str | None = None,
    severity: Severity | None = None,
    platform: Platform | None = None,
    status: MentionStatus | None = None,
    since_timestamp: int | None = Query(None, description="Unix ms; only mentions published after it"),
    since_id: str | None = Query(None, description="Only mentions published after this mention"),
    before_timestamp: int | None = Query(None, description="Unix ms; only mentions published at or before it (next page of older ones)"),
    limit: int = Query(50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
):
    since = from_ms(since_timestamp) if since_timestamp else None
    if since_id:
        since = load_mention(since_id, user, "published_at")["published_at"]
    rows = query_mentions(user, company_id, severity and severity.value, platform and platform.value, status and status.value, since, limit,
                          from_ms(before_timestamp) if before_timestamp else None)
    return [mappers.mention(r) for r in rows]


# Declared before /mentions/{mention_id} so "stream" is not parsed as an id.
@router.get("/mentions/stream", response_class=StreamingResponse)
async def stream_mentions(request: Request, company_id: str | None = None, user: CurrentUser = Depends(get_current_user)):
    """Server-sent events: one `mention` event per new mention (polls every 5 s). Alternative to polling with `since_id`."""
    async def events():
        since = iso(now())
        yield ": connected\n\n"
        while not await request.is_disconnected():
            await asyncio.sleep(STREAM_POLL_S)
            rows = await asyncio.to_thread(query_mentions, user, company_id, None, None, None, since, 200)
            for r in reversed(rows):
                yield f"event: mention\ndata: {json.dumps(mappers.mention(r).model_dump(by_alias=True, mode='json'))}\n\n"
            if rows:
                since = rows[0]["published_at"]
            else:
                yield ": keep-alive\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.get("/mentions/{mention_id}", response_model=Mention)
def get_mention(mention_id: str, user: CurrentUser = Depends(get_current_user)):
    return mappers.mention(load_mention(mention_id, user))


@router.patch("/mentions/{mention_id}/status", response_model=Mention)
def update_mention_status(mention_id: str, body: MentionStatusUpdate, user: CurrentUser = Depends(get_current_user)):
    load_mention(mention_id, user, "id")
    get_db().table("mentions").update({"status": body.status.value}).eq("id", mention_id).execute()
    return mappers.mention(load_mention(mention_id, user))
