"""Practice and progress responses for the frontend."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class PracticeReferenceOut(BaseModel):
    id: int
    canonical_id: str
    name: str
    reference_type: Literal["mudra", "sequence"]
    description: str | None = None
    mudra_ids: list[int]
    image_url: str | None = None
    max_duration_seconds: int | None = None


class ProgressEntryOut(BaseModel):
    session_id: int
    reference_id: int
    reference_name: str
    status: Literal["created", "uploaded", "processing", "evaluated", "failed"]
    created_at: datetime
    dtw_normalized: float | None = None
    top_label: str | None = None
    top_confidence: float | None = None
    feedback_summary: str | None = None


class ProgressResponse(BaseModel):
    scope: Literal["shared_development"]
    sessions: list[ProgressEntryOut]


class CreatePracticeSessionIn(BaseModel):
    reference_id: int | str


class PracticeSessionOut(BaseModel):
    session_id: int
    reference_id: int
    status: Literal["created", "uploaded", "processing", "evaluated", "failed"]
    created_at: datetime
