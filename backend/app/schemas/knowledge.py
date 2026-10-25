"""Request/response schemas for the knowledge API (Part 4)."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.core.enums import MatchType, VerificationStatus
from app.schemas.concepts import ConceptSupportStatus, ExtractedConcept
from app.services.text_processing import MAX_INPUT_CHARS


class SourceOut(BaseModel):
    id: str
    source_name: str
    source_url: str | None = None
    source_type: str
    author_or_organization: str | None = None
    publication_date: str | None = None
    access_date: date | None = None
    license_or_usage_notes: str | None = None
    reliability_notes: str | None = None


class MudraOut(BaseModel):
    id: str
    name: str
    alternate_names: list[str] = Field(default_factory=list)
    category: str
    meaning: str | None = None
    usage: list[str] = Field(default_factory=list)
    description: str | None = None
    practice_instructions: str | None = None
    reference_image_path: str | None = None  # None if absent OR the file does not exist
    source: SourceOut | None = None
    verification_status: VerificationStatus
    verification_notes: str | None = None
    limitations: list[str] = Field(default_factory=list)


class MovementOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    movement_category: str
    practice_instructions: str | None = None
    reference_media_path: str | None = None
    source: SourceOut | None = None
    verification_status: VerificationStatus
    verification_notes: str | None = None
    limitations: list[str] = Field(default_factory=list)


class RetrieveRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)
    include_unverified: bool = False  # needs ALLOW_UNVERIFIED_RECORDS=true on the server
    include_keyword_matches: bool = False  # weak matches on single words inside usages


class RetrievedReference(BaseModel):
    """One mudra/movement retrieved for a concept. `record_id` is the stable citation id."""

    record_type: Literal["mudra", "movement"]
    record_id: str
    name: str
    category: str
    meaning: str | None = None
    description: str | None = None
    usage: list[str] = Field(default_factory=list)
    practice_instructions: str | None = None
    reference_media_path: str | None = None
    match_type: MatchType
    mapping_ids: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)
    interpretation_types: list[str] = Field(default_factory=list)
    evidence_notes: list[str] = Field(default_factory=list)
    verification_status: VerificationStatus  # weakest of record and mapping(s)
    source: SourceOut | None = None  # source of the record
    mapping_source: SourceOut | None = None  # source of the concept mapping
    limitations: list[str] = Field(default_factory=list)


class ConceptRetrieval(BaseModel):
    concept: ExtractedConcept
    status: ConceptSupportStatus
    references: list[RetrievedReference] = Field(default_factory=list)
    contains_unverified: bool = False
    note: str | None = None


class RetrievalResponse(BaseModel):
    original_text: str
    include_unverified: bool
    include_keyword_matches: bool
    concepts: list[ConceptRetrieval]
    supported_count: int
    unsupported_count: int
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "References come from a curated knowledge base and are learning aids, not expert "
        "artistic judgement. A concept can have several valid interpretations, and no "
        "mapping means no supported reference was found."
    )
