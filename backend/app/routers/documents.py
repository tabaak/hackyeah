"""2. Documents. Owners: Vitya (storage/DB), Sanya (processing and search)."""
from fastapi import APIRouter, File, Form, UploadFile

from app.deps import not_implemented
from app.schemas.common import Classification
from app.schemas.documents import Document, DocumentUrl

router = APIRouter(tags=["documents"])


@router.get("/documents", response_model=list[Document])
def list_documents():
    not_implemented()


@router.post("/documents/upload", response_model=Document, status_code=202)
def upload_document(file: UploadFile = File(...), classification: Classification = Form(...)):
    """Multipart PDF/TXT + classification; saves the file and starts background indexing."""
    not_implemented()


@router.get("/documents/{document_id}/url", response_model=DocumentUrl)
def get_document_url(document_id: str):
    """Temporary signed URL after the role and access check."""
    not_implemented()


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: str):
    """Deletes the file and its vector chunks."""
    not_implemented()
