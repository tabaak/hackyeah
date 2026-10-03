"""7. Notifications (bell: latest open incidents)."""
from fastapi import APIRouter

from app.deps import not_implemented
from app.schemas.notifications import Notification, NotificationList

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationList)
def list_notifications():
    not_implemented()


@router.patch("/{notification_id}/read", response_model=Notification)
def mark_read(notification_id: str):
    not_implemented()


@router.post("/mark-all-read", status_code=204)
def mark_all_read():
    not_implemented()
