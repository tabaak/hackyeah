"""6. Analytics. Owners: Vitya / Max."""
from fastapi import APIRouter

from app.deps import not_implemented
from app.schemas.analytics import AiMetrics, CoordinationSignal, Narrative, Trends

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/trends", response_model=Trends)
def trends():
    """Mentions/incidents per hour and day; confirmed disinformation counted separately."""
    not_implemented()


@router.get("/narratives", response_model=list[Narrative])
def narratives():
    not_implemented()


@router.get("/coordination-signals", response_model=list[CoordinationSignal])
def coordination_signals():
    """New accounts, synchrony, duplicates; only from available data. Signals, not a verdict."""
    not_implemented()


@router.get("/ai-metrics", response_model=AiMetrics)
def ai_metrics():
    not_implemented()
