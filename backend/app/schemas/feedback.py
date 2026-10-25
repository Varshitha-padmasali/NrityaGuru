"""Schemas for evidence-grounded corrective feedback (Part 8)."""
from typing import Literal

from pydantic import BaseModel, Field

from app.core.enums import TutorFallbackReason, VerificationStatus
from app.schemas.evaluation import SESSION_ID_PATTERN, EvidenceLevel


class FeedbackRequest(BaseModel):
    """Only a session id. Evaluation evidence is NEVER accepted from the client."""

    session_id: str = Field(pattern=SESSION_ID_PATTERN)
    regenerate: bool = False  # True = ignore stored feedback and generate a new one


class EvidenceItem(BaseModel):
    """One fact derived from the evaluation result. Built by code, never by Gemini."""

    evidence_id: str = Field(max_length=80)
    kind: Literal["reference", "instructions", "label", "dtw", "deviation", "landmarks", "warning"]
    statement: str = Field(max_length=900)


class Observation(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    evidence_ids: list[str] = Field(min_length=1, max_length=10)


class Suggestion(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    evidence_ids: list[str] = Field(min_length=1, max_length=10)


class FeedbackExplanation(BaseModel):
    """What Gemini must return. Limitations are NOT requested: code attaches them."""

    overall_summary: str = Field(min_length=1, max_length=1000)
    observations: list[Observation] = Field(default_factory=list, max_length=8)
    suggestions: list[Suggestion] = Field(default_factory=list, max_length=5)


class FeedbackBody(BaseModel):
    overall_summary: str
    observations: list[Observation] = Field(default_factory=list)
    suggestions: list[Suggestion] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)  # always deterministic (from the assessment)


class ReferenceSummary(BaseModel):
    record_type: Literal["mudra", "movement"]
    record_id: str
    name: str
    verification_status: VerificationStatus
    instructions_available: bool


class FeedbackResult(BaseModel):
    mode: Literal["ai", "evidence_only"]
    session_id: str
    reference: ReferenceSummary
    evidence_level: EvidenceLevel
    is_mock: bool  # True = test data, never a real evaluation
    feedback: FeedbackBody
    supporting_evidence: list[EvidenceItem]
    model: str | None = None
    fallback_reason: TutorFallbackReason | None = None
    notice: str | None = None
    saved: bool = False  # stored in PostgreSQL (False for MOCK data or if saving failed)
    reused: bool = False  # True = returned from storage, no new generation
    evidence_fingerprint: str | None = Field(default=None, max_length=64)  # SHA-256 of the evidence
    disclaimer: str = (
        "This feedback is generated from structured evaluation results (landmarks, classifier "
        "output and sequence comparison). No AI watched your video. It is reference-based "
        "practice assistance, not expert artistic judgement or a replacement for a teacher."
    )
