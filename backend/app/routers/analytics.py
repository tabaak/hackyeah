"""6. Analytics. Common params: company_id (optional, default all), range (24h | 7d | 30d, default 24h)."""
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query

from app.db import get_db
from app.deps import get_current_user
from app.schemas.analytics import AnalyticsSummary, HourBucket, PlatformReach, VerdictCount
from app.schemas.auth import CurrentUser
from app.schemas.common import Platform, Verdict
from app.services.timeutil import iso, now

router = APIRouter(prefix="/analytics", tags=["analytics"])
RANGES = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
RangeParam = Query("24h", pattern="^(24h|7d|30d)$")


def _mentions(user: CurrentUser, company_id: str | None, range_: str, fields: str) -> list[dict]:
    q = (
        get_db().table("mentions").select(fields).eq("organization_id", user.organization_id)
        .gte("published_at", iso(now() - RANGES[range_]))
    )
    if company_id:
        q = q.eq("company_id", company_id)
    return q.limit(10000).execute().data


@router.get("/summary", response_model=AnalyticsSummary)
def summary(company_id: str | None = None, range: str = RangeParam, user: CurrentUser = Depends(get_current_user)):
    rows = _mentions(user, company_id, range, "severity, status, cluster_id, injection_suspected")
    sev = Counter(r["severity"] for r in rows)
    st = Counter(r["status"] for r in rows)
    return AnalyticsSummary(
        total=len(rows), high=sev["high"], medium=sev["medium"], low=sev["low"],
        open_high=sum(1 for r in rows if r["severity"] == "high" and r["status"] == "new"),
        responded=st["responded"], dismissed=st["dismissed"],
        clusters=len({r["cluster_id"] for r in rows if r["cluster_id"]}),
        injections_blocked=sum(1 for r in rows if r["injection_suspected"]),
    )


@router.get("/mentions-by-hour", response_model=list[HourBucket])
def mentions_by_hour(company_id: str | None = None, user: CurrentUser = Depends(get_current_user)):
    """Last 24 hourly buckets (UTC), oldest first, by severity."""
    end = now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    starts = [end - timedelta(hours=24 - i) for i in range(24)]
    buckets = {s: Counter() for s in starts}
    for r in _mentions(user, company_id, "24h", "severity, published_at"):
        t = datetime.fromisoformat(r["published_at"].replace("Z", "+00:00"))
        start = t.replace(minute=0, second=0, microsecond=0)
        if start in buckets:
            buckets[start][r["severity"]] += 1
    return [HourBucket(hour=f"{s.hour:02d}:00", low=c["low"], medium=c["medium"], high=c["high"]) for s, c in buckets.items()]


@router.get("/reach-by-platform", response_model=list[PlatformReach])
def reach_by_platform(company_id: str | None = None, range: str = RangeParam, user: CurrentUser = Depends(get_current_user)):
    """Every platform, sorted by reach."""
    n, reach = Counter(), Counter()
    for r in _mentions(user, company_id, range, "platform, reach"):
        n[r["platform"]] += 1
        reach[r["platform"]] += r["reach"]
    out = [PlatformReach(platform=p, mentions=n[p.value], reach=reach[p.value]) for p in Platform]
    return sorted(out, key=lambda x: -x.reach)


@router.get("/claim-verification", response_model=list[VerdictCount])
def claim_verification(company_id: str | None = None, range: str = RangeParam, user: CurrentUser = Depends(get_current_user)):
    """Verdict distribution for medium and high severity mentions."""
    rows = _mentions(user, company_id, range, "severity, verdict")
    c = Counter(r["verdict"] for r in rows if r["severity"] != "low")
    return [VerdictCount(verdict=v, count=c[v.value]) for v in Verdict]
