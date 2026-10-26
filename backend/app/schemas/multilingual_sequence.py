"""Schemas for the additive multilingual lyric-to-sequence API."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from app.core.enums import VerificationStatus
from app.services.text_processing import MAX_INPUT_CHARS


class SequenceMode(str, Enum):
    KNOWLEDGE_BASE = "knowledge_base"
    AI_ASSISTED = "ai_assisted"


CatalogueMode = Literal["all", "eight_mudra"]


class MultilingualSequenceRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)
    mode: SequenceMode = SequenceMode.AI_ASSISTED
    catalogue_mode: CatalogueMode = "all"
    include_unverified: bool = False


class SelectionType(str, Enum):
    TEACHER_VERIFIED = "teacher_verified"
    SOURCE_SUPPORTED = "source_supported"
    AI_INFERRED = "ai_inferred"


class LanguageInfo(BaseModel):
    code: str
    name: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    detection_method: str


class SemanticEvent(BaseModel):
    order: int = Field(ge=1)
    phrase: str
    event_type: str
    concepts: list[str] = Field(default_factory=list)
    lookup_terms: list[str] = Field(default_factory=list)
    negated: bool = False
    tense: str = "unspecified"
    relations: list[str] = Field(default_factory=list)
    context: str = ""


class SentenceTranslation(BaseModel):
    position: int = Field(ge=1)
    original_sentence: str
    english_translation: str | None = None
    translated: bool = False
    note: str | None = None


class SequenceCitation(BaseModel):
    source_id: str
    title: str
    url: str | None = None
    claim_scope: str


class MultilingualSequenceStep(BaseModel):
    position: int = Field(ge=1)
    event_order: int = Field(ge=1)
    original_text: str
    language: str
    phrase: str
    related_phrases: list[str] = Field(default_factory=list)
    event_orders: list[int] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    mudra_id: str
    mudra_name: str
    alternate_names: list[str] = Field(default_factory=list)
    hand_position_description: str | None = None
    selection_reason: str
    additional_selection_reasons: list[str] = Field(default_factory=list)
    context: str = ""
    source_citations: list[SequenceCitation] = Field(default_factory=list)
    verification_status: VerificationStatus
    image_url: str | None = None
    selection_type: SelectionType
    confidence: float = Field(ge=0, le=1)
    confidence_meaning: str
    uncertainty_notes: list[str] = Field(default_factory=list)


class UnmappedSequenceConcept(BaseModel):
    event_order: int
    phrase: str
    concept: str
    reason: str


class MultilingualSequenceResponse(BaseModel):
    original_input: str
    detected_language: LanguageInfo
    sentence_translations: list[SentenceTranslation] = Field(default_factory=list)
    events: list[SemanticEvent] = Field(default_factory=list)
    ordered_sequence: list[MultilingualSequenceStep] = Field(default_factory=list)
    unmapped_concepts: list[UnmappedSequenceConcept] = Field(default_factory=list)
    interpretation_caveats: list[str] = Field(default_factory=list)
    gemini_used: bool = False
    mode: SequenceMode
    catalogue_mode: CatalogueMode = "all"
    disclaimer: str = (
        "This is a semantic learning aid, not canonical Bharatanatyam choreography. "
        "AI-inferred associations are suggestions and must not be treated as traditional usages."
    )
