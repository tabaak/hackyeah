"""3. Documents (by id)."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from app.db import DOCUMENTS_BUCKET, get_db, not_found
from app.deps import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.common import Role
from app.schemas.documents import Doc, DocumentUpdate, DocumentUrl
from app.services import documents, mappers
from app.services.timeutil import now, to_ms

router = APIRouter(tags=["documents"])
URL_TTL_S = 300


def load_document(document_id: str, user: CurrentUser) -> dict:
    rows = get_db().table("documents").select("*").eq("id", document_id).eq("organization_id", user.organization_id).execute().data
    if not rows:
        raise not_found("Document")
    return rows[0]


@router.patch("/documents/{document_id}", response_model=Doc)
def update_document(document_id: str, body: DocumentUpdate, user: CurrentUser = Depends(get_current_user)):
    """Changes the classification (chunks follow via a DB trigger)."""
    load_document(document_id, user)
    row = get_db().table("documents").update({"classification": body.classification.value}).eq("id", document_id).execute().data[0]
    return mappers.doc(row)


@router.get("/documents/{document_id}/url", response_model=DocumentUrl)
def get_document_url(document_id: str, user: CurrentUser = Depends(get_current_user)):
    """Temporary signed URL. Restricted documents: compliance only."""
    doc = load_document(document_id, user)
    if doc["classification"] == "restricted" and user.role != Role.compliance:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Restricted documents are visible to compliance only")
    signed = get_db().storage.from_(DOCUMENTS_BUCKET).create_signed_url(doc["storage_path"], URL_TTL_S)
    url = signed.get("signedURL") or signed.get("signedUrl")
    return DocumentUrl(url=url, expires_at=to_ms(now() + timedelta(seconds=URL_TTL_S)))


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: str, user: CurrentUser = Depends(get_current_user)):
    """Deletes the file and its vector chunks."""
    documents.remove(load_document(document_id, user))
