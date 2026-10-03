from typing import Annotated, Literal

from pydantic import Field, field_validator

from app.schemas.common import CamelModel
from app.schemas.documents import Doc

Sector = Literal["Banking", "Defence", "Fintech", "Energy", "Other"]
Short = Annotated[str, Field(max_length=200)]
ShortList = Annotated[list[Short], Field(max_length=50)]


class CompanyDraft(CamelModel):
    name: str = Field(min_length=1, max_length=200)
    website: str = Field("", max_length=500)
    aliases: ShortList = []
    sector: Sector
    country: str = Field(min_length=1, max_length=100)
    people: ShortList = []
    topics: ShortList = []

    @field_validator('name', 'country', mode='before')
    @classmethod
    def strip_required_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class Company(CompanyDraft):
    id: str
    logo_url: str | None = None
    documents: list[Doc] = []
    created_at: int  # Unix ms


class CompanyLogo(CamelModel):
    logo_url: str


class CompaniesMeta(CamelModel):
    sectors: dict[str, list[str]]  # sector -> recommended topics
    countries: list[str]
