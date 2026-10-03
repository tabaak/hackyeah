"""2. Tracked companies and their documents."""
import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status

from app.config import settings
from app.db import get_db, not_found
from app.deps import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.common import Classification
from app.schemas.companies import CompaniesMeta, Company, CompanyDraft
from app.schemas.documents import Doc
from app.services import demo, documents, mappers, news

router = APIRouter(tags=["companies"])

# Mirrors the frontend's SECTORS / COUNTRIES.
SECTORS = {
    "Banking": ["Liquidity / bank run", "Frozen withdrawals", "App or card outage", "Data breach", "Regulatory action", "Fraud & scams"],
    "Defence": ["Delivery delays", "Export control", "Product failure", "Sanctions", "Leadership", "Data breach"],
    "Fintech": ["Frozen accounts", "App outage", "Data breach", "Licence / regulator", "Fraud & scams"],
    "Energy": ["Supply disruption", "Safety incident", "Pricing", "Environmental", "Regulatory action"],
    "Other": ["Product quality", "Data breach", "Leadership", "Legal action", "Layoffs"],
}
COUNTRIES = ["Poland", "Germany", "Ukraine", "Lithuania", "Czechia", "United Kingdom", "United States", "Global"]
MAX_FILES = 8


def load_company(company_id: str, user: CurrentUser, select: str = "*") -> dict:
    rows = get_db().table("companies").select(select).eq("id", company_id).eq("organization_id", user.organization_id).execute().data
    if not rows:
        raise not_found("Company")
    return rows[0]


def _clean(body: CompanyDraft) -> dict:
    strip = lambda xs: list(dict.fromkeys(x.strip() for x in xs if x.strip()))
    return {
        "name": body.name.strip(), "website": body.website.strip(), "aliases": strip(body.aliases), "sector": body.sector,
        "country": body.country, "people": strip(body.people), "topics": strip(body.topics),
    }


@router.get("/companies", response_model=list[Company])
def list_companies(user: CurrentUser = Depends(get_current_user)):
    rows = (
        get_db().table("companies").select(mappers.COMPANY_SELECT)
        .eq("organization_id", user.organization_id).order("created_at").execute().data
    )
    return [mappers.company(r) for r in rows]


@router.post("/companies", response_model=Company, status_code=201)
def create_company(body: CompanyDraft, background: BackgroundTasks, user: CurrentUser = Depends(get_current_user)):
    row = get_db().table("companies").insert({**_clean(body), "organization_id": user.organization_id}).execute().data[0]
    if settings.demo_seed:
        demo.seed_company(row)
    background.add_task(news.sync_company, row)  # no-op without SERPER_API_KEY
    return mappers.company(row)


# Declared before /companies/{company_id} so "meta" is not parsed as an id.
@router.get("/companies/meta", response_model=CompaniesMeta)
def companies_meta():
    """Form reference data: sectors with recommended topics, and countries."""
    return CompaniesMeta(sectors=SECTORS, countries=COUNTRIES)


@router.get("/companies/{company_id}", response_model=Company)
def get_company(company_id: str, user: CurrentUser = Depends(get_current_user)):
    return mappers.company(load_company(company_id, user, mappers.COMPANY_SELECT))


@router.put("/companies/{company_id}", response_model=Company)
def update_company(company_id: str, body: CompanyDraft, user: CurrentUser = Depends(get_current_user)):
    load_company(company_id, user)
    get_db().table("companies").update(_clean(body)).eq("id", company_id).execute()
    return mappers.company(load_company(company_id, user, mappers.COMPANY_SELECT))


@router.delete("/companies/{company_id}", status_code=204)
def delete_company(company_id: str, user: CurrentUser = Depends(get_current_user)):
    """Stops monitoring; deletes the company's mentions, documents and stored files."""
    load_company(company_id, user)
    for d in get_db().table("documents").select("id, storage_path").eq("company_id", company_id).execute().data:
        documents.remove(d)
    get_db().table("companies").delete().eq("id", company_id).execute()


@router.get("/companies/{company_id}/documents", response_model=list[Doc])
def list_company_documents(company_id: str, user: CurrentUser = Depends(get_current_user)):
    load_company(company_id, user)
    rows = get_db().table("documents").select("*").eq("company_id", company_id).order("created_at").execute().data
    return [mappers.doc(r) for r in rows]


@router.post("/companies/{company_id}/documents", response_model=list[Doc], status_code=202)
async def upload_company_documents(
    company_id: str,
    background: BackgroundTasks,
    files: list[UploadFile] = File(...),
    classifications: list[Classification] = Form(...),  # one per file, same order
    user: CurrentUser = Depends(get_current_user),
):
    """Multipart PDF/TXT; saves files and indexes them in the background (status processing -> ready | failed)."""
    if len(files) != len(classifications):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "One classification per file is required")
    if len(files) > MAX_FILES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Up to {MAX_FILES} files per upload")
    payloads = []
    for f in files:
        name = f.filename or "file"
        if not documents.content_type_for(name):
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"{name}: only PDF and TXT are supported")
        data = await f.read()
        if len(data) > documents.MAX_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"{name}: larger than 5 MB")
        payloads.append((name, data))

    # Sync supabase client: run it in a thread to keep the event loop free.
    await asyncio.to_thread(load_company, company_id, user)
    created = []
    for (name, data), cls in zip(payloads, classifications):
        row = await asyncio.to_thread(documents.upload, user.organization_id, company_id, user.id, name, data, cls.value)
        background.add_task(documents.process_document, row["id"], data)
        created.append(mappers.doc(row))
    return created
