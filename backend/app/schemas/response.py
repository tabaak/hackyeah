from app.schemas.common import ApprovalState, CamelModel, Classification, Verdict


class ClaimCheck(CamelModel):
    verdict: Verdict
    reason: str


class EvidenceItem(CamelModel):
    doc_id: str
    name: str
    classification: Classification  # `restricted` documents are never used


class Disclosure(CamelModel):
    needs_compliance: bool
    reason: str


class Approval(CamelModel):
    state: ApprovalState = ApprovalState.none
    by: str | None = None
    at: int | None = None


class MentionResponse(CamelModel):
    claim_check: ClaimCheck
    evidence: list[EvidenceItem] = []
    draft: str
    disclosure: Disclosure
    injection_blocked: bool = False
    approval: Approval


class DraftUpdate(CamelModel):
    text: str


class Decision(CamelModel):
    approve: bool
    comment: str | None = None
