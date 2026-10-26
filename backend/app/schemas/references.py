"""Ingestion contract for consented and teacher-reviewed reference sequences."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, FiniteFloat, model_validator


class ReferenceSequenceIn(BaseModel):
    schema_version: Literal[1]
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{2,79}$")
    mudra_id: str | None = Field(default=None, max_length=80)
    movement_id: str | None = Field(default=None, max_length=80)
    feature_schema: str = Field(min_length=1, max_length=80)
    evaluator_version: str = Field(min_length=1, max_length=80)
    normalization: str = Field(min_length=1, max_length=120)
    feature_dimensions: int = Field(ge=1, le=256)
    frames: list[list[FiniteFloat]] = Field(min_length=1, max_length=600)
    source: str = Field(min_length=1, max_length=1000)
    performer_consent_reference: str = Field(min_length=1, max_length=200)
    review_status: Literal["candidate", "teacher_verified", "rejected"]
    reviewer_identity: str | None = Field(default=None, max_length=200)
    reviewed_at: datetime | None = None
    threshold: FiniteFloat | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_reference(self):
        if (self.mudra_id is None) == (self.movement_id is None):
            raise ValueError("exactly one of mudra_id or movement_id is required")
        if self.review_status == "teacher_verified":
            if not self.reviewer_identity or self.reviewed_at is None:
                raise ValueError("teacher_verified references require reviewer_identity and reviewed_at")
        elif self.reviewer_identity is not None or self.reviewed_at is not None:
            raise ValueError("reviewer identity and timestamp are only accepted for verified references")
        if not self.frames or any(len(row) != self.feature_dimensions for row in self.frames):
            raise ValueError("every frame must match feature_dimensions")
        return self


class ReferenceSequenceOut(BaseModel):
    id: str
    mudra_id: str | None
    movement_id: str | None
    schema_version: int
    feature_schema: str
    evaluator_version: str
    normalization: str
    feature_dimensions: int
    source: str
    review_status: str
    reviewer_identity: str | None
    reviewed_at: datetime | None
    created_at: datetime
