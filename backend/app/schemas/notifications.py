from typing import Literal

from app.schemas.common import CamelModel, Severity


class Notification(CamelModel):
    id: str
    kind: Literal["critical_mention", "approval_requested", "approval_decided"]
    mention_id: str | None = None
    title: str
    severity: Severity
    at: int  # Unix ms
    read: bool = False


class NotificationList(CamelModel):
    items: list[Notification]
    open_count: int  # unread
