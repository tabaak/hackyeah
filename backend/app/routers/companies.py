"""2. Tracked companies and their documents."""
from fastapi import APIRouter, File, Form, UploadFile

from app.deps import not_implemented
from app.schemas.common import Classification
from app.schemas.companies import CompaniesMeta, Company, CompanyDraft
from app.schemas.documents import Doc

router = APIRouter(tags=["companies"])


@router.get("/companies", response_model=list[Company])
def list_companies():
    not_implemented()


@router.post("/companies", response_model=Company, status_code=201)
def create_company(body: CompanyDraft):
    not_implemented()


# Declared before /companies/{company_id} so "meta" is not parsed as an id.
@router.get("/companies/meta", response_model=CompaniesMeta)
def companies_meta():
    """Form reference data: sectors with recommended topics, and countries."""
    not_implemented()


@router.get("/companies/{company_id}", response_model=Company)
def get_company(company_id: str):
    not_implemented()


@router.put("/companies/{company_id}", response_model=Company)
def update_company(company_id: str, body: CompanyDraft):
    not_implemented()


@router.delete("/companies/{company_id}", status_code=204)
def delete_company(company_id: str):
    """Stops monitoring."""
    not_implemented()


@router.get("/companies/{company_id}/documents", response_model=list[Doc])
def list_company_documents(company_id: str):
    not_implemented()


@router.post("/companies/{company_id}/documents", response_model=list[Doc], status_code=202)
def upload_company_documents(
    company_id: str,
    files: list[UploadFile] = File(...),
    classifications: list[Classification] = Form(...),  # one per file, same order
):
    """Multipart PDF/TXT; saves files and starts background vector indexing."""
    not_implemented()
