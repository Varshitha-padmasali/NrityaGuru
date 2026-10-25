"""Schemas for the AI tutor (Part 5)."""
from typing import Literal

from pydantic import BaseModel, Field

from app.core.enums import TutorFallbackReason


class ConceptExplanation(BaseModel):
    concept: str = Field(min_length=1, max_length=120)
    supported: bool
    explanation: str = Field(min_length=1, max_length=1200)
    source_ids: list[str] = Field(default_factory=list, max_length=20)


class TutorExplanation(BaseModel):
    """The structure Gemini must return (and the fallback builder also produces)."""

    summary: str = Field(min_length=1, max_length=1500)
    concepts: list[ConceptExplanation] = Field(default_factory=list, max_length=30)
    suggestions: list[str] = Field(default_factory=list, max_length=10)
    alternatives: list[str] = Field(default_factory=list, max_length=10)
    source_ids: list[str] = Field(default_factory=list, max_length=40)
    limitations: list[str] = Field(default_factory=list, max_length=20)


class TutorResult(BaseModel):
    mode: Literal["ai", "knowledge_only"]
    explanation: TutorExplanation
    model: str | None = None  # set only when Gemini produced the explanation
    fallback_reason: TutorFallbackReason | None = None
    notice: str | None = None  # user-facing sentence explaining a fallback
