"""6. Analytics. Common params: company_id (optional, default all), range (default 24h)."""
from fastapi import APIRouter

from app.deps import not_implemented
from app.schemas.analytics import AnalyticsSummary, HourBucket, PlatformReach, VerdictCount

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def summary(company_id: str | None = None, range: str = "24h"):
    not_implemented()


@router.get("/mentions-by-hour", response_model=list[HourBucket])
def mentions_by_hour(company_id: str | None = None, range: str = "24h"):
    """24 hourly buckets by severity."""
    not_implemented()


@router.get("/reach-by-platform", response_model=list[PlatformReach])
def reach_by_platform(company_id: str | None = None, range: str = "24h"):
    not_implemented()


@router.get("/claim-verification", response_model=list[VerdictCount])
def claim_verification(company_id: str | None = None, range: str = "24h"):
    """Verdict distribution for medium and high severity mentions."""
    not_implemented()
