from app.schemas.common import CamelModel, Platform, Verdict


class AnalyticsSummary(CamelModel):
    total: int  # mentions in range
    high: int
    medium: int
    low: int
    open_high: int  # high severity, status new
    responded: int
    dismissed: int
    clusters: int  # distinct coordinated clusters
    injections_blocked: int


class HourBucket(CamelModel):
    hour: str  # "HH:00"
    low: int
    medium: int
    high: int


class PlatformReach(CamelModel):
    platform: Platform
    mentions: int
    reach: int


class VerdictCount(CamelModel):
    verdict: Verdict
    count: int
