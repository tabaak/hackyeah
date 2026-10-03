from app.schemas.common import CamelModel
from app.schemas.documents import Doc


class CompanyDraft(CamelModel):
    name: str
    website: str = ""
    aliases: list[str] = []
    sector: str  # Banking | Defence | Fintech | Energy | Other
    country: str
    people: list[str] = []
    topics: list[str] = []


class Company(CompanyDraft):
    id: str
    documents: list[Doc] = []
    created_at: int  # Unix ms


class CompaniesMeta(CamelModel):
    sectors: dict[str, list[str]]  # sector -> recommended topics
    countries: list[str]
