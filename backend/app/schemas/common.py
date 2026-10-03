from enum import Enum

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """JSON is camelCase (matches the frontend); Python code stays snake_case."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Role(str, Enum):
    analyst = "analyst"
    compliance = "compliance"


class Platform(str, Enum):
    x = "x"
    facebook = "facebook"
    reddit = "reddit"
    telegram = "telegram"
    tiktok = "tiktok"
    linkedin = "linkedin"
    news = "news"


class Severity(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class Verdict(str, Enum):
    contradicted_by_documents = "contradicted_by_documents"
    supported_by_documents = "supported_by_documents"
    insufficient_evidence = "insufficient_evidence"
    opinion = "opinion"


class MentionStatus(str, Enum):
    new = "new"
    responded = "responded"
    dismissed = "dismissed"


class Classification(str, Enum):
    public = "public"
    internal = "internal"
    confidential = "confidential"
    restricted = "restricted"


class DocumentStatus(str, Enum):
    processing = "processing"
    ready = "ready"
    failed = "failed"


class ApprovalState(str, Enum):
    none = "none"
    pending = "pending"
    approved = "approved"


class SourceStatus(CamelModel):
    healthy: bool
    last_sync_at: int | None = None  # Unix ms
    detail: str | None = None


class SyncRequested(CamelModel):
    accepted: bool = True
    added: int = 0  # new mentions stored
