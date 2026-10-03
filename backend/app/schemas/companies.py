from typing import Literal

from pydantic import Field

from app.schemas.common import CamelModel
from app.schemas.documents import Doc

Sector = Literal["Banking", "Defence", "Fintech", "Energy", "Other"]


class CompanyDraft(CamelModel):
    name: str = Field(min_length=1, max_length=200)
    website: str = ""
    aliases: list[str] = []
    sector: Sector
    country: str = Field(min_length=1)
    people: list[str] = []
    topics: list[str] = []


class Company(CompanyDraft):
    id: str
    documents: list[Doc] = []
    created_at: int  # Unix ms


class CompaniesMeta(CamelModel):
    sectors: dict[str, list[str]]  # sector -> recommended topics
    countries: list[str]
