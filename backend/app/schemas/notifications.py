from app.schemas.common import CamelModel, Severity


class Notification(CamelModel):
    id: str
    mention_id: str
    title: str
    severity: Severity
    at: int  # Unix ms
    read: bool = False


class NotificationList(CamelModel):
    items: list[Notification]
    open_count: int
