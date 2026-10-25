"""CONTRACT between the evaluation module (OpenCV, MediaPipe, MLP, DTW) and the Member 2 backend.

Version 1.0.  The evaluation module PRODUCES an EvaluationResult. Member 2 only CONSUMES it and
never invents any field. Optional fields may be omitted/null when the evaluation module cannot
supply them; the feedback code then states the limitation instead of guessing.
See docs/evaluation_contract.md for the field-by-field description and open questions.
"""
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.core.enums import VerificationStatus
from app.schemas.knowledge import SourceOut

SUPPORTED_MAJOR_VERSION = 1
SESSION_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$"
REFERENCE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{1,79}$"
LABEL_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9 _.:+-]{0,79}$"


class FrameInterval(BaseModel):
    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=0)
    start_time_s: float | None = Field(default=None, ge=0)
    end_time_s: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _ordered(self):
        if self.end_frame < self.start_frame:
            raise ValueError("end_frame must not be before start_frame")
        if (
            self.start_time_s is not None
            and self.end_time_s is not None
            and self.end_time_s < self.start_time_s
        ):
            raise ValueError("end_time_s must not be before start_time_s")
        return self


class PredictedLabel(BaseModel):
    label: str = Field(pattern=LABEL_PATTERN)
    confidence: float | None = Field(default=None, ge=0, le=1)
    interval: FrameInterval | None = None


class DtwSummary(BaseModel):
    """DTW measures alignment COST against the reference sequence. It does not say what is wrong."""

    distance: float = Field(ge=0)
    normalized_distance: float | None = Field(default=None, ge=0)
    threshold: float | None = Field(default=None, ge=0)  # supplied by the evaluation module
    within_threshold: bool | None = None  # decided by the evaluation module, not by us
    reference_sequence_id: str | None = Field(default=None, pattern=REFERENCE_ID_PATTERN)
    feature_schema_version: str | None = Field(default=None, max_length=40)


class Deviation(BaseModel):
    """A difference the evaluation module itself detected. Never created by Member 2 or Gemini."""

    deviation_id: str = Field(pattern=REFERENCE_ID_PATTERN)
    kind: Literal["finger", "joint", "hand_pose", "timing", "posture", "other"]
    body_part: str | None = Field(default=None, max_length=60)  # e.g. "index_finger"
    description: str = Field(min_length=1, max_length=300)
    measured_value: float | None = None
    reference_value: float | None = None
    unit: str | None = Field(default=None, max_length=20)
    severity: Literal["minor", "moderate", "major"] | None = None
    interval: FrameInterval | None = None
    source_module: Literal["mlp", "dtw", "landmark_rules"] | None = None


class LandmarkQuality(BaseModel):
    hand_detection_rate: float | None = Field(default=None, ge=0, le=1)
    pose_detection_rate: float | None = Field(default=None, ge=0, le=1)
    frames_total: int | None = Field(default=None, ge=0)
    frames_analysed: int | None = Field(default=None, ge=0)
    # Preferred: the evaluation module states whether landmarks were reliable enough.
    reliable: bool | None = None
    notes: list[str] = Field(default_factory=list, max_length=10)


class EvaluationResult(BaseModel):
    schema_version: str = Field(pattern=r"^\d+\.\d+$")
    session_id: str = Field(pattern=SESSION_ID_PATTERN)
    # Exactly one of the two reference ids must be set.
    reference_movement_id: str | None = Field(default=None, pattern=REFERENCE_ID_PATTERN)
    reference_mudra_id: str | None = Field(default=None, pattern=REFERENCE_ID_PATTERN)
    expected_labels: list[str] = Field(default_factory=list, max_length=20)
    predicted_labels: list[PredictedLabel] = Field(default_factory=list, max_length=100)
    dtw: DtwSummary | None = None
    deviations: list[Deviation] = Field(default_factory=list, max_length=50)
    landmark_quality: LandmarkQuality | None = None
    warnings: list[str] = Field(default_factory=list, max_length=20)
    mlp_model_version: str | None = Field(default=None, max_length=60)
    created_at: datetime | None = None
    is_mock: bool = False  # True for test data. Must never be shown as a real evaluation.

    @model_validator(mode="after")
    def _exactly_one_reference(self):
        if (self.reference_movement_id is None) == (self.reference_mudra_id is None):
            raise ValueError("exactly one of reference_movement_id / reference_mudra_id is required")
        return self


# ---------- what Member 2 builds from a result ----------
class EvidenceLevel(str, Enum):
    SUFFICIENT = "sufficient"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


class LabelMatch(str, Enum):
    MATCH = "match"  # top predicted label is one of the expected labels
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"  # predictions or expected labels missing


class EvidenceSource(str, Enum):
    STORED_SESSION = "stored_session"  # fetched by session id from the trusted store
    MOCK_STORE = "mock_store"  # MOCK test data


class ReferenceInfo(BaseModel):
    """Reference instructions for the practised mudra/movement, read from PostgreSQL."""

    record_type: Literal["mudra", "movement"]
    record_id: str
    name: str
    category: str
    practice_instructions: str | None = None
    instructions_available: bool
    reference_media_path: str | None = None
    verification_status: VerificationStatus
    source: SourceOut | None = None
    limitations: list[str] = Field(default_factory=list)


class EvidenceAssessment(BaseModel):
    level: EvidenceLevel
    label_match: LabelMatch
    top_label: str | None = None
    top_confidence: float | None = None
    dtw_available: bool
    landmarks_reliable: bool | None = None  # None = unknown
    specific_deviations: list[Deviation] = Field(default_factory=list)
    general_deviations: list[Deviation] = Field(default_factory=list)
    can_name_specific_error: bool  # True only if a deviation names a body part or measurement
    limitations: list[str] = Field(default_factory=list)


class ValidatedEvidence(BaseModel):
    evidence_source: EvidenceSource
    is_mock: bool
    result: EvaluationResult
    reference: ReferenceInfo
    assessment: EvidenceAssessment
