"""Minimal schemas consumed by the frozen frontend."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FrontendMudraSummary(BaseModel):
    id: int
    canonical_id: str
    name: str
    hasta_type: Literal["asamyuta", "samyuta"] | None = None
    meaning: str | None = None
    image_url: str | None = None


class FrontendMudraDetail(FrontendMudraSummary):
    alt_names: list[str]
    usage: str | None = None
    instructions: str | None = None
    source: str | None = None
    verification_status: Literal["verified", "unverified", "needs_review"]
    practice_reference_id: int | None = None
    category: str
    dataset_image_count: int = 0
    dataset_images_available: bool = False
    recognition_supported: bool = False
    limitations: list[str] = Field(default_factory=list)


class FrontendMudraMatch(FrontendMudraSummary):
    rationale: str | None = None
    source: str | None = None
    verification_status: Literal["verified", "unverified", "needs_review"] = "needs_review"


class FrontendConceptResult(BaseModel):
    concept: str
    supported: bool
    matches: list[FrontendMudraMatch]
    # Preserve the richer backend evidence alongside the compact UI fields.
    status: str
    references: list[dict]
    contains_unverified: bool = False
    note: str | None = None
    concept_detail: dict


class FrontendRetrieveResponse(BaseModel):
    query: str
    concepts: list[FrontendConceptResult]
    original_text: str
    include_unverified: bool
    include_keyword_matches: bool
    supported_count: int
    unsupported_count: int
    warnings: list[str]
    disclaimer: str


class FrontendPracticeReference(BaseModel):
    id: int
    canonical_id: str
    name: str
    reference_type: Literal["mudra", "sequence"]
    description: str | None = None
    mudra_ids: list[int]
    image_url: str | None = None
    max_duration_seconds: int | None = None


class FrontendPracticeSession(BaseModel):
    session_id: int
    reference_id: int
    status: Literal["created", "uploaded", "processing", "evaluated", "failed"]
    created_at: datetime
