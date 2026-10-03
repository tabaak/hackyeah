from pydantic import BaseModel

from app.schemas.common import Platform, RiskLevel, Sentiment


class Mention(BaseModel):
    id: str
    platform: Platform
    author: str | None = None
    text: str
    url: str | None = None
    published_at: str
    sentiment: Sentiment | None = None
    cluster_id: str | None = None


class FeedPage(BaseModel):
    items: list[Mention]
    next_cursor: str | None = None  # cursor semantics still to be fixed in the JSON contract


class DashboardSummary(BaseModel):
    overall_risk: RiskLevel
    total_mentions_24h: int
    active_incidents: int
    active_clusters: int
    pending_actions: int


class TestQuery(BaseModel):
    query: str


class TestQueryResult(BaseModel):
    count: int
    sample: list[Mention] = []
