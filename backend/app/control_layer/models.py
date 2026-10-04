from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt
from pydantic.alias_generators import to_camel

LEVELS = ("public", "internal", "confidential", "restricted")
Classification = Literal["public", "internal", "confidential", "restricted"]
SECTORS = ["Banking", "Defence", "Fintech", "Energy", "Other", "Insurance", "Technology",
           "Telecommunications", "Healthcare", "Industrials", "Transport & Logistics",
           "Consumer & Retail", "Agriculture & Food", "Real Estate", "Professional Services"]
EVENT_KINDS = ("deal", "investigation", "scandal", "operational_crisis", "data_breach",
               "regulatory", "other")


class Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    def wire(self):
        return self.model_dump(mode="json", by_alias=True)


def highest(*labels: str) -> str:
    # Unknown labels must never mean public.
    return max(labels, key=LEVELS.index) if labels else "restricted"


def risk_category(score: int | None) -> str:
    return "unknown" if score is None else "low" if score <= 3 else "medium" if score <= 6 else "high"


class Evidence(Model):
    id: str
    content: str
    classification: Classification = "internal"
    origin: Literal["public_feed", "document", "policy"] = "document"
    source_url: str | None = None
    published_at: str | None = None
    independent: bool = False


class Reference(Model):
    evidence_id: str
    quote: str = Field(min_length=8)


class SensitiveFinding(Model):
    category: str = Field(max_length=100)
    quote: str = Field(min_length=1)


class Sensitivity(Model):
    classification: Classification
    findings: list[SensitiveFinding]


class Claim(Model):
    text: str
    verdict: Literal["supported", "contradicted", "insufficient_evidence"]
    references: list[Reference]
    limitations: list[str]
    next_check: str


class Event(Model):
    event_key: str
    kind: Literal["deal", "investigation", "scandal", "operational_crisis", "data_breach", "regulatory", "other"]
    summary: str
    occurred_at: str | None = None
    references: list[Reference]
    claims: list[Claim]


class Extraction(Model):
    relevant: bool
    events: list[Event]


class Risk(Model):
    risk_score: StrictInt | None = Field(ge=0, le=10)
    coverage_sufficient: bool
    rationale: str
    references: list[Reference]
    gaps: list[str]


class ExceptionRule(Model):
    id: str
    conditions: list[str] = Field(min_length=1)


class Clause(Model):
    id: str
    text: str = Field(min_length=8)
    applies_to: list[str] = Field(min_length=1)
    effect: Literal["requirement", "prohibition"]
    exceptions: list[ExceptionRule] = []
    remediation: list[str] = []
    required_evidence: list[str] = []


class PolicyStructure(Model):
    clauses: list[Clause] = Field(min_length=1)


class PolicyMatch(Model):
    clause_ids: list[str]


class PolicyCreate(Model):
    name: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=20, max_length=60000)
    classification: Classification = "confidential"


class AssessmentRequest(Model):
    purpose: Literal["onboarding", "crisis"] = "onboarding"
    days: int = Field(default=60, ge=1, le=365)
    policy_id: str | None = None
    # Baseline bypasses relevance filtering, never privacy checks.
    baseline: bool = False


class SectorUpdate(Model):
    sector: str
