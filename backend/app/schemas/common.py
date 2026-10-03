from enum import Enum

from pydantic import BaseModel


class Role(str, Enum):
    analyst = "analyst"
    compliance = "compliance"


class Platform(str, Enum):
    twitter = "twitter"
    facebook = "facebook"
    gnews = "gnews"


class Sentiment(str, Enum):
    negative = "negative"
    neutral = "neutral"
    positive = "positive"


class RiskLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class Severity(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class IncidentStatus(str, Enum):
    open = "open"
    review = "review"
    resolved = "resolved"


class Classification(str, Enum):
    public = "public"
    internal = "internal"
    confidential = "confidential"
    restricted = "restricted"


class DocumentStatus(str, Enum):
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Verdict(str, Enum):
    supported = "supported"
    contradicted = "contradicted"
    insufficient = "insufficient"
    opinion = "opinion"


class SourceStatus(BaseModel):
    healthy: bool
    last_sync_at: str | None = None
    detail: str | None = None


class SyncRequested(BaseModel):
    accepted: bool = True
    job_id: str | None = None
