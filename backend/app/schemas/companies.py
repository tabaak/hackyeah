from typing import Literal

from pydantic import Field, field_validator

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

    @field_validator('name', 'country', mode='before')
    @classmethod
    def strip_required_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class Company(CompanyDraft):
    id: str
    documents: list[Doc] = []
    created_at: int  # Unix ms


class CompaniesMeta(CamelModel):
    sectors: dict[str, list[str]]  # sector -> recommended topics
    countries: list[str]
