"""Stored feedback. Wraps database failures in PersistenceError (never leaks SQL/URLs)."""
import logging

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import FeedbackRecord
from app.repositories.errors import PersistenceError
from app.schemas.feedback import FeedbackResult

logger = logging.getLogger(__name__)


class SqlFeedbackStore:
    def latest(self, db: Session, session_id: str) -> FeedbackResult | None:
        try:
            row = db.scalars(
                select(FeedbackRecord)
                .where(FeedbackRecord.session_id == session_id)
                .order_by(FeedbackRecord.created_at.desc(), FeedbackRecord.id.desc())
                .limit(1)
            ).first()
        except SQLAlchemyError as exc:
            logger.error("Reading stored feedback failed: %s", type(exc).__name__)
            raise PersistenceError("Stored feedback could not be read.") from None
        if row is None:
            return None
        try:
            stored = FeedbackResult.model_validate(row.result_json)
        except ValidationError:
            logger.error("A stored feedback row failed validation (row id %s); ignoring it.", row.id)
            return None
        stored.saved = True
        stored.reused = True
        return stored

    def save(self, db: Session, result: FeedbackResult) -> None:
        try:
            db.add(
                FeedbackRecord(
                    session_id=result.session_id,
                    mode=result.mode,
                    evidence_level=result.evidence_level.value,
                    fallback_reason=result.fallback_reason.value if result.fallback_reason else None,
                    model=result.model,
                    is_mock=result.is_mock,
                    result_json=result.model_dump(mode="json"),
                )
            )
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.error("Saving feedback failed: %s", type(exc).__name__)
            raise PersistenceError("Feedback could not be saved.") from None
