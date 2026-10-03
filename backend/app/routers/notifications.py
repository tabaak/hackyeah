"""7. Notifications (bell): critical mentions and approval requests/decisions, per user."""
from fastapi import APIRouter, Depends, Query

from app.db import get_db, not_found
from app.deps import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.notifications import Notification, NotificationList
from app.services.timeutil import iso, now, to_ms

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _model(r: dict) -> Notification:
    return Notification(id=r["id"], kind=r["kind"], mention_id=r["mention_id"], title=r["title"], severity=r["severity"],
                        at=to_ms(r["created_at"]), read=r["read_at"] is not None)


@router.get("", response_model=NotificationList)
def list_notifications(limit: int = Query(20, ge=1, le=100), user: CurrentUser = Depends(get_current_user)):
    """Newest first; `openCount` = unread notifications."""
    db = get_db()
    rows = db.table("notifications").select("*").eq("user_id", user.id).order("created_at", desc=True).limit(limit).execute().data
    unread = db.table("notifications").select("id", count="exact").eq("user_id", user.id).is_("read_at", "null").limit(1).execute().count
    return NotificationList(items=[_model(r) for r in rows], open_count=unread or 0)


@router.patch("/{notification_id}/read", response_model=Notification)
def mark_read(notification_id: str, user: CurrentUser = Depends(get_current_user)):
    rows = (
        get_db().table("notifications").update({"read_at": iso(now())})
        .eq("id", notification_id).eq("user_id", user.id).execute().data
    )
    if not rows:
        raise not_found("Notification")
    return _model(rows[0])


@router.post("/mark-all-read", status_code=204)
def mark_all_read(user: CurrentUser = Depends(get_current_user)):
    get_db().table("notifications").update({"read_at": iso(now())}).eq("user_id", user.id).is_("read_at", "null").execute()
