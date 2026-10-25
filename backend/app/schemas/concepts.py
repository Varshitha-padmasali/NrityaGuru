"""Typed schemas for concept extraction and resolution (Part 3)."""
from enum import Enum

from pydantic import BaseModel, Field

from app.services.text_processing import MAX_INPUT_CHARS


class ConceptType(str, Enum):
    ENTITY = "entity"  # person / character / deity name
    ACTION = "action"  # verb-like
    OTHER = "other"  # anything else (objects, places, nature, ...)


class Span(BaseModel):
    start: int
    end: int


class ConceptExtractionRequest(BaseModel):
    """Request body used by the API endpoints added in Parts 4 and 6."""

    text: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)


class ExtractedConcept(BaseModel):
    text: str  # first mention, as written
    normalized: str  # canonical lowercase form (verbs reduced to base form when known)
    concept_type: ConceptType
    lookup_keys: list[str]  # candidate keys for knowledge-base lookup, best first
    mentions: list[Span]  # offsets into original_text
    reason: str  # which rule produced this classification (transparency)


class ExtractionResult(BaseModel):
    original_text: str  # exactly what the user typed
    normalized_text: str
    concepts: list[ExtractedConcept]
    warnings: list[str] = Field(default_factory=list)
    method: str
    disclaimer: str = (
        "Extracted concepts are candidates only. They are not Bharatanatyam facts "
        "and do not imply that a mudra exists for each word."
    )


class ConceptSupportStatus(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"


class ResolvedConcept(BaseModel):
    concept: ExtractedConcept
    status: ConceptSupportStatus
    matched_keys: list[str] = Field(default_factory=list)
    mapping_ids: list[str] = Field(default_factory=list)
    mudra_ids: list[str] = Field(default_factory=list)
    movement_ids: list[str] = Field(default_factory=list)
    contains_unverified: bool = False  # True if any mapping is not 'verified'
    note: str | None = None


class ResolutionResult(BaseModel):
    original_text: str
    include_unverified: bool
    concepts: list[ResolvedConcept]
    supported_count: int
    unsupported_count: int
    warnings: list[str] = Field(default_factory=list)
