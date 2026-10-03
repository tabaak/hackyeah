"""3. Documents (by id)."""
from fastapi import APIRouter

from app.deps import not_implemented
from app.schemas.documents import Doc, DocumentUpdate, DocumentUrl

router = APIRouter(tags=["documents"])


@router.patch("/documents/{document_id}", response_model=Doc)
def update_document(document_id: str, body: DocumentUpdate):
    """Changes the classification."""
    not_implemented()


@router.get("/documents/{document_id}/url", response_model=DocumentUrl)
def get_document_url(document_id: str):
    """Temporary signed URL after the role and access check."""
    not_implemented()


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: str):
    """Deletes the file and its vector chunks."""
    not_implemented()
