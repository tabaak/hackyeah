from pydantic import BaseModel

from app.schemas.common import Classification, DocumentStatus


class Document(BaseModel):
    id: str
    filename: str
    classification: Classification
    status: DocumentStatus
    uploaded_at: str
    size_bytes: int | None = None


class DocumentUrl(BaseModel):
    url: str
    expires_at: str
