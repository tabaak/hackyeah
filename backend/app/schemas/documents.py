from app.schemas.common import CamelModel, Classification, DocumentStatus


class Doc(CamelModel):
    id: str
    name: str
    size: int
    classification: Classification
    status: DocumentStatus


class DocumentUpdate(CamelModel):
    classification: Classification


class DocumentUrl(CamelModel):
    url: str
    expires_at: str
