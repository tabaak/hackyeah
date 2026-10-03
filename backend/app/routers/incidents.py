"""5. Incidents and AI. Owners: Sanya (LLM), Vitya (storage and API)."""
from fastapi import APIRouter

from app.deps import not_implemented
from app.schemas.common import IncidentStatus, Severity
from app.schemas.incidents import (
    ApproveRequest,
    Draft,
    DraftUpdate,
    Incident,
    IncidentSummary,
    PublishResult,
    ResolveRequest,
)

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentSummary])
def list_incidents(
    severity: Severity | None = None,
    status: IncidentStatus | None = None,
    is_injection_attempt: bool | None = None,
):
    not_implemented()


@router.get("/{incident_id}", response_model=Incident)
def get_incident(incident_id: str):
    """Cluster, burst, claims, evidence, draft, disclosure check."""
    not_implemented()


@router.post("/{incident_id}/generate-counter-argument", response_model=Draft, status_code=202)
def generate_counter_argument(incident_id: str):
    """Generates or regenerates an evidence-based reply. May conclude 'insufficient evidence' instead of rebutting."""
    not_implemented()


@router.patch("/{incident_id}/draft", response_model=Draft)
def update_draft(incident_id: str, body: DraftUpdate):
    """Manual edit: re-runs the disclosure check and drops any earlier approval."""
    not_implemented()


@router.post("/{incident_id}/request-approval", response_model=Incident)
def request_approval(incident_id: str):
    """Confidential evidence requires the `compliance` role."""
    not_implemented()


@router.post("/{incident_id}/approve", response_model=Incident)
def approve(incident_id: str, body: ApproveRequest):
    """A human approves a specific draft version and hash."""
    not_implemented()


@router.post("/{incident_id}/publish", response_model=PublishResult)
def publish(incident_id: str):
    """Checks the approval, then writes to the simulated outbox."""
    not_implemented()


@router.post("/{incident_id}/resolve", response_model=Incident)
def resolve(incident_id: str, body: ResolveRequest):
    """Closes with a reason. 'dismiss' was also proposed as the name."""
    not_implemented()
