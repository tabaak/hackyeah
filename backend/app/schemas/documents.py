from app.schemas.common import CamelModel, Classification, DocumentStatus


class Doc(CamelModel):
    id: str
    name: str
    size: int
    classification: Classification
    status: DocumentStatus
    summary: str | None = None  # AI summary; null while processing, and for restricted unless compliance


class DocumentUpdate(CamelModel):
    classification: Classification


class DocumentUrl(CamelModel):
    url: str
    expires_at: int  # Unix ms
