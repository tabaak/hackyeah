from pydantic import BaseModel


class Notification(BaseModel):
    id: str
    kind: str  # burst | critical_incident | draft_awaiting_approval
    title: str
    created_at: str
    read: bool = False
    incident_id: str | None = None
