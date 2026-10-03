"""5. Counter-post for a mention. Owners: LLM generation and approval flow."""
from fastapi import APIRouter, Depends

from app.deps import not_implemented, require_compliance
from app.schemas.response import Decision, DraftUpdate, MentionResponse

router = APIRouter(prefix="/mentions/{mention_id}/response", tags=["response"])


@router.get("", response_model=MentionResponse)
def get_response(mention_id: str):
    """Claim check, evidence, draft, disclosure check, approval state."""
    not_implemented()


@router.post("/generate", response_model=MentionResponse, status_code=202)
def generate_response(mention_id: str):
    """LLM draft from the company's documents; with no documents the draft makes no factual claims."""
    not_implemented()


@router.patch("/draft", response_model=MentionResponse)
def update_draft(mention_id: str, body: DraftUpdate):
    """Saves edited text; updates the hash and resets any previous approval."""
    not_implemented()


@router.post("/approve", response_model=MentionResponse)
def approve(mention_id: str):
    """Analyst approval when no confidential data is used; stores the text hash and sets status=responded."""
    not_implemented()


@router.post("/request-approval", response_model=MentionResponse)
def request_approval(mention_id: str):
    """Sends the draft to compliance when confidential documents are involved."""
    not_implemented()


@router.post("/decision", response_model=MentionResponse, dependencies=[Depends(require_compliance)])
def decide(mention_id: str, body: Decision):
    """Compliance decision. Role `compliance` only."""
    not_implemented()
