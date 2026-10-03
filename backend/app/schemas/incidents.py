from pydantic import BaseModel

from app.schemas.common import Classification, IncidentStatus, Role, Severity, Verdict


class Evidence(BaseModel):
    document_id: str
    title: str
    classification: Classification
    quote: str
    page: int | None = None


class Claim(BaseModel):
    id: str
    text: str
    verdict: Verdict | None = None
    evidence: list[Evidence] = []


class DisclosureFinding(BaseModel):
    text: str
    start: int
    end: int
    source_classification: Classification


class DisclosureCheck(BaseModel):
    findings: list[DisclosureFinding] = []
    required_approver: Role = Role.analyst


class Draft(BaseModel):
    version: int
    text: str
    hash: str
    approved_by: str | None = None
    approved_hash: str | None = None


class IncidentSummary(BaseModel):
    id: str
    title: str
    severity: Severity
    status: IncidentStatus
    is_injection_attempt: bool = False
    created_at: str


class Incident(IncidentSummary):
    cluster_id: str | None = None
    burst: dict | None = None
    claims: list[Claim] = []
    draft: Draft | None = None
    disclosure_check: DisclosureCheck | None = None
    analysis_status: str | None = None


class DraftUpdate(BaseModel):
    text: str
    expected_version: int | None = None


class ResolveRequest(BaseModel):
    reason: str


class ApproveRequest(BaseModel):
    draft_version: int
    draft_hash: str


class PublishResult(BaseModel):
    outbox_id: str
    published: bool
