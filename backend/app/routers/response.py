"""5. Counter-post for a mention: claim check, evidence, draft, disclosure check, approvals."""
from fastapi import APIRouter, Depends, HTTPException, status

from app.db import get_db, not_found
from app.deps import get_current_user, require_compliance
from app.routers.feed import load_mention
from app.schemas.auth import CurrentUser
from app.schemas.common import Role
from app.schemas.response import Approval, ClaimCheck, Decision, Disclosure, DraftRevision, DraftUpdate, EvidenceItem, MentionResponse
from app.services import analysis, responses, retrieval
from app.services.notifications import notify
from app.services.timeutil import iso, now, to_ms

router = APIRouter(prefix="/mentions/{mention_id}/response", tags=["response"])
MENTION_FIELDS = "id, organization_id, company_id, platform, text, reach, severity, verdict, reason, injection_suspected, status"


def _company(company_id: str) -> dict:
    return get_db().table("companies").select("*").eq("id", company_id).single().execute().data


def _row(mention_id: str) -> dict | None:
    rows = get_db().table("mention_responses").select("*").eq("mention_id", mention_id).execute().data
    return rows[0] if rows else None


def _latest_approval(mention_id: str) -> dict | None:
    rows = (
        get_db().table("approvals").select("*").eq("mention_id", mention_id)
        .neq("status", "invalidated").order("created_at", desc=True).limit(1).execute().data
    )
    return rows[0] if rows else None


def _build(mention: dict, row: dict) -> MentionResponse:
    a = _latest_approval(mention["id"])
    approval = Approval()
    if a and a["status"] in ("pending", "approved"):
        by = None
        if a["status"] == "approved" and a["decided_by"]:
            p = get_db().table("profiles").select("name, email").eq("user_id", a["decided_by"]).execute().data
            by = (p[0]["name"] or p[0]["email"]) if p else None
        approval = Approval(state=a["status"], by=by, at=to_ms(a["decided_at"] or a["created_at"]))
    return MentionResponse(
        claim_check=ClaimCheck(verdict=mention["verdict"], reason=mention["reason"]),
        evidence=[EvidenceItem(**e) for e in row["evidence"]],
        draft=row["draft"],
        disclosure=Disclosure(needs_compliance=row["needs_compliance"], reason=row["disclosure_reason"]),
        injection_blocked=row["injection_blocked"],
        approval=approval,
    )


def _generate(mention: dict) -> dict:
    """Retrieve evidence, re-check the claim, draft, run the disclosure check, and store the result."""
    company = _company(mention["company_id"])
    hits = retrieval.search(company["id"], mention["text"])
    verdict, reason = mention["verdict"], mention["reason"]
    assessed = analysis.assess(company, mention["text"], mention["reach"], hits)
    if assessed.by_llm:
        verdict, reason = assessed.verdict, assessed.reason
    elif not hits and verdict in ("contradicted_by_documents", "supported_by_documents"):
        verdict, reason = "insufficient_evidence", f"No uploaded documents address this claim. {reason}"
    if (verdict, reason) != (mention["verdict"], mention["reason"]):
        get_db().table("mentions").update({"verdict": verdict, "reason": reason}).eq("id", mention["id"]).execute()
        mention.update(verdict=verdict, reason=reason)

    draft = responses.generate_draft(company, mention, verdict, reason, hits)
    needs, why, findings = responses.disclosure_check(draft, hits)
    data = {
        "draft": draft,
        "draft_hash": responses.draft_hash(draft),
        "evidence": retrieval.evidence_docs(hits),
        "needs_compliance": needs,
        "disclosure_reason": why,
        "disclosure_findings": findings,
        "injection_blocked": mention["injection_suspected"],
    }
    if _row(mention["id"]):
        return get_db().table("mention_responses").update(data).eq("mention_id", mention["id"]).execute().data[0]
    return get_db().table("mention_responses").insert({**data, "mention_id": mention["id"]}).execute().data[0]


def _require_row(mention_id: str) -> dict:
    row = _row(mention_id)
    if not row:
        raise HTTPException(status.HTTP_409_CONFLICT, "No draft yet: GET or generate the response first")
    return row


@router.get("", response_model=MentionResponse)
def get_response(mention_id: str, user: CurrentUser = Depends(get_current_user)):
    """Claim check, evidence, draft, disclosure check, approval state. Generates the first draft on first open."""
    mention = load_mention(mention_id, user, MENTION_FIELDS)
    row = _row(mention_id) or _generate(mention)
    return _build(mention, row)


@router.post("/generate", response_model=MentionResponse)
def generate_response(mention_id: str, user: CurrentUser = Depends(get_current_user)):
    """(Re)generates the draft from the company's documents; invalidates earlier approvals."""
    mention = load_mention(mention_id, user, MENTION_FIELDS)
    return _build(mention, _generate(mention))


@router.patch("/draft", response_model=MentionResponse)
def update_draft(mention_id: str, body: DraftUpdate, user: CurrentUser = Depends(get_current_user)):
    """Saves edited text. A changed hash resets approvals and bumps the version (DB trigger)."""
    mention = load_mention(mention_id, user, MENTION_FIELDS)
    _require_row(mention_id)
    text = body.text.strip()
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Draft is empty")
    return _build(mention, _save_draft(mention, text, retrieval.search(mention["company_id"], mention["text"])))


def _save_draft(mention: dict, text: str, hits: list[dict]) -> dict:
    needs, why, findings = responses.disclosure_check(text, hits)
    return get_db().table("mention_responses").update({
        "draft": text, "draft_hash": responses.draft_hash(text),
        "needs_compliance": needs, "disclosure_reason": why, "disclosure_findings": findings,
    }).eq("mention_id", mention["id"]).execute().data[0]


@router.post("/revise", response_model=MentionResponse)
def revise(mention_id: str, body: DraftRevision, user: CurrentUser = Depends(get_current_user)):
    """AI rewrite of the current text per the editor's instruction (tone, length, main point); saved like a manual edit."""
    mention = load_mention(mention_id, user, MENTION_FIELDS)
    _require_row(mention_id)
    text, instruction = body.text.strip(), body.instruction.strip()
    if not text or not instruction:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Draft and instruction are required")
    hits = retrieval.search(mention["company_id"], mention["text"])
    revised = responses.revise_draft(_company(mention["company_id"]), mention, text, instruction, hits)
    if not revised:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The AI model is unavailable. Edit the text manually or try again.")
    return _build(mention, _save_draft(mention, revised, hits))


@router.post("/approve", response_model=MentionResponse)
def approve(mention_id: str, user: CurrentUser = Depends(get_current_user)):
    """Approves the current draft (hash recorded) and marks the mention responded.
    Drafts that need compliance can only be approved by the compliance role."""
    mention = load_mention(mention_id, user, MENTION_FIELDS)
    row = _require_row(mention_id)
    if row["needs_compliance"] and user.role != Role.compliance:
        raise HTTPException(status.HTTP_409_CONFLICT, "This draft relies on confidential documents: request compliance approval")
    decided = {"status": "approved", "decided_by": user.id, "decided_at": iso(now())}
    pending = _latest_approval(mention_id)
    if pending and pending["status"] == "pending" and pending["payload_hash"] == row["draft_hash"]:
        get_db().table("approvals").update(decided).eq("id", pending["id"]).execute()
    else:
        get_db().table("approvals").insert({
            "organization_id": user.organization_id, "mention_id": mention_id,
            "payload_hash": row["draft_hash"], "draft_version": row["draft_version"],
            "required_role": "compliance" if row["needs_compliance"] else "analyst",
            "requested_by": user.id, **decided,
        }).execute()
    get_db().table("mentions").update({"status": "responded"}).eq("id", mention_id).execute()
    return _build(mention, row)


@router.post("/request-approval", response_model=MentionResponse)
def request_approval(mention_id: str, user: CurrentUser = Depends(get_current_user)):
    """Sends the current draft to the organization's compliance users."""
    mention = load_mention(mention_id, user, MENTION_FIELDS)
    row = _require_row(mention_id)
    latest = _latest_approval(mention_id)
    if latest and latest["payload_hash"] == row["draft_hash"] and latest["status"] in ("pending", "approved"):
        return _build(mention, row)  # already requested or approved for this exact text
    get_db().table("approvals").insert({
        "organization_id": user.organization_id, "mention_id": mention_id,
        "payload_hash": row["draft_hash"], "draft_version": row["draft_version"],
        "required_role": "compliance", "requested_by": user.id,
    }).execute()
    notify(user.organization_id, "approval_requested", f"Approval requested: {mention['text']}", mention["severity"],
           mention_id, roles=("compliance",))
    return _build(mention, row)


@router.post("/decision", response_model=MentionResponse)
def decide(mention_id: str, body: Decision, user: CurrentUser = Depends(require_compliance)):
    """Compliance decision on the pending request. Role `compliance` only."""
    mention = load_mention(mention_id, user, MENTION_FIELDS)
    row = _require_row(mention_id)
    pending = _latest_approval(mention_id)
    if not pending or pending["status"] != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "No pending approval request")
    if pending["payload_hash"] != row["draft_hash"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "The draft changed after the request; request approval again")
    get_db().table("approvals").update({
        "status": "approved" if body.approve else "rejected",
        "decided_by": user.id, "decided_at": iso(now()), "comment": body.comment,
    }).eq("id", pending["id"]).execute()
    if body.approve:
        get_db().table("mentions").update({"status": "responded"}).eq("id", mention_id).execute()
    if pending["requested_by"]:
        verb = "approved" if body.approve else "rejected"
        notify(user.organization_id, "approval_decided", f"Response {verb}: {mention['text']}", mention["severity"],
               mention_id, user_ids=[pending["requested_by"]])
    return _build(mention, row)
