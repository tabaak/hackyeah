from pydantic import BaseModel


class TrendPoint(BaseModel):
    bucket: str  # hour or day, ISO 8601
    mentions: int
    incidents: int
    confirmed_disinformation: int = 0


class Trends(BaseModel):
    points: list[TrendPoint]


class Narrative(BaseModel):
    id: str
    title: str
    mentions: int
    verification_status: str


class CoordinationSignal(BaseModel):
    kind: str  # new_accounts | synchrony | duplicates
    description: str
    count: int


class AiMetrics(BaseModel):
    blocked_actions: int
    tokens: int
    estimated_cost_usd: float
    gateway_latency_p50_ms: float | None = None
    gateway_latency_p95_ms: float | None = None
