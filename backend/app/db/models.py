"""SQLAlchemy models for the curated Bharatanatyam knowledge base (Part 2).

Tables: sources, mudras, movements, concept_mappings, practice_sessions, evaluation_results, feedback.
reference_sequences is still to be added with the evaluation module.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.enums import VerificationStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


def _status_column() -> Mapped[VerificationStatus]:
    return mapped_column(
        Enum(
            VerificationStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
        index=True,
    )


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source_name: Mapped[str] = mapped_column(String(300), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    source_type: Mapped[str] = mapped_column(String(60), nullable=False)
    author_or_organization: Mapped[str | None] = mapped_column(String(300))
    publication_date: Mapped[str | None] = mapped_column(String(20))  # "1917" or "2021-05-01"
    access_date: Mapped[date | None] = mapped_column(Date)
    license_or_usage_notes: Mapped[str | None] = mapped_column(Text)
    reliability_notes: Mapped[str | None] = mapped_column(Text)


class Mudra(Base):
    __tablename__ = "mudras"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    alternate_names: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    meaning: Mapped[str | None] = mapped_column(Text)
    usage: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    practice_instructions: Mapped[str | None] = mapped_column(Text)
    reference_image_path: Mapped[str | None] = mapped_column(String(500))
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"), index=True)
    verification_status: Mapped[VerificationStatus] = _status_column()
    verification_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    source: Mapped[Source | None] = relationship()


class Movement(Base):
    __tablename__ = "movements"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    movement_category: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    practice_instructions: Mapped[str | None] = mapped_column(Text)
    reference_media_path: Mapped[str | None] = mapped_column(String(500))
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"), index=True)
    verification_status: Mapped[VerificationStatus] = _status_column()
    verification_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    source: Mapped[Source | None] = relationship()


class ConceptMapping(Base):
    """Explicit link: concept (e.g. 'river') -> mudra and/or movement.

    One concept may have several rows (several valid interpretations).
    """

    __tablename__ = "concept_mappings"
    __table_args__ = (
        CheckConstraint(
            "mudra_id IS NOT NULL OR movement_id IS NOT NULL",
            name="ck_mapping_has_target",
        ),
        Index("ix_concept_mappings_concept", "concept"),
    )

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    concept: Mapped[str] = mapped_column(String(120), nullable=False)  # stored normalized
    mudra_id: Mapped[str | None] = mapped_column(ForeignKey("mudras.id"))
    movement_id: Mapped[str | None] = mapped_column(ForeignKey("movements.id"))
    relationship_description: Mapped[str | None] = mapped_column(Text)
    interpretation_type: Mapped[str] = mapped_column(String(60), nullable=False)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"))
    evidence_notes: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[VerificationStatus] = _status_column()

    mudra: Mapped[Mudra | None] = relationship()
    movement: Mapped[Movement | None] = relationship()
    source: Mapped[Source | None] = relationship()


# ---------------------------------------------------------------------------
# Part 9: practice sessions, stored evaluation results, stored feedback.
# Only structured data is stored: NO video, NO images, NO personal identifiers.
# JSON is used for the two result documents because their schemas are versioned and
# always read whole; they are re-validated with Pydantic every time they are read.
# On PostgreSQL the JSON columns are JSONB.
# ---------------------------------------------------------------------------
JSONType = JSON().with_variant(JSONB(), "postgresql")


class PracticeSession(Base):
    """One practice attempt against one reference (a mudra OR a movement)."""

    __tablename__ = "practice_sessions"
    __table_args__ = (
        CheckConstraint(
            "(mudra_id IS NOT NULL AND movement_id IS NULL) OR "
            "(mudra_id IS NULL AND movement_id IS NOT NULL)",
            name="ck_session_one_reference",
        ),
        CheckConstraint(
            "status IN ('created', 'uploaded', 'processing', 'evaluated', 'failed')",
            name="ck_practice_session_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # the session_id
    mudra_id: Mapped[str | None] = mapped_column(ForeignKey("mudras.id"), index=True)
    movement_id: Mapped[str | None] = mapped_column(ForeignKey("movements.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="created", server_default="created", index=True)
    failure_reason: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReferenceSequence(Base):
    """A provenance-bearing reference sequence; only teacher-reviewed rows are publishable."""

    __tablename__ = "reference_sequences"
    __table_args__ = (
        CheckConstraint(
            "(mudra_id IS NOT NULL AND movement_id IS NULL) OR "
            "(mudra_id IS NULL AND movement_id IS NOT NULL)",
            name="ck_reference_sequence_one_target",
        ),
        CheckConstraint("schema_version = 1", name="ck_reference_sequence_schema_v1"),
        CheckConstraint(
            "review_status IN ('candidate', 'teacher_verified', 'rejected')",
            name="ck_reference_sequence_review_status",
        ),
        Index("ix_reference_sequences_review_target", "review_status", "mudra_id", "movement_id"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    mudra_id: Mapped[str | None] = mapped_column(ForeignKey("mudras.id", ondelete="CASCADE"))
    movement_id: Mapped[str | None] = mapped_column(ForeignKey("movements.id", ondelete="CASCADE"))
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    feature_schema: Mapped[str] = mapped_column(String(80), nullable=False)
    evaluator_version: Mapped[str] = mapped_column(String(80), nullable=False)
    normalization: Mapped[str] = mapped_column(String(120), nullable=False)
    frames: Mapped[list] = mapped_column(JSONType, nullable=False)
    feature_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(1000), nullable=False)
    performer_consent_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    reviewer_identity: Mapped[str | None] = mapped_column(String(200))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    threshold: Mapped[float | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvaluationRecord(Base):
    """The evaluation module's result for a session (at most one per session)."""

    __tablename__ = "evaluation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    schema_version: Mapped[str] = mapped_column(String(10), nullable=False)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeedbackRecord(Base):
    """Feedback generated for a session. Several rows per session are allowed (regeneration)."""

    __tablename__ = "feedback"
    __table_args__ = (Index("ix_feedback_session_created", "session_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)  # ai | evidence_only
    evidence_level: Mapped[str] = mapped_column(String(20), nullable=False)
    fallback_reason: Mapped[str | None] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(80))
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
