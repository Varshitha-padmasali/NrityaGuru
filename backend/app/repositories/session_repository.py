"""Practice sessions and stored evaluation results.

WHO CALLS THIS: the evaluation module (or the session owner) calls create_session() and
save_evaluation_result(). Member 2 only READS evaluation results (via DatabaseEvaluationStore).
Confirm with the team who owns practice_sessions before the first real deployment.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EvaluationRecord, PracticeSession
from app.repositories.errors import ReferenceMismatchError, SessionNotFoundError
from app.schemas.evaluation import EvaluationResult


def create_session(
    db: Session, session_id: str, *, mudra_id: str | None = None, movement_id: str | None = None
) -> PracticeSession:
    if (mudra_id is None) == (movement_id is None):
        raise ValueError("exactly one of mudra_id / movement_id is required")
    session = PracticeSession(id=session_id, mudra_id=mudra_id, movement_id=movement_id)
    db.add(session)
    db.commit()
    return session


def get_session(db: Session, session_id: str) -> PracticeSession | None:
    return db.get(PracticeSession, session_id)


def save_evaluation_result(db: Session, result: EvaluationResult) -> EvaluationRecord:
    """Insert or replace the evaluation for a session.

    Integrity checks: the session must exist, and the result's reference must be the one the
    session was created for (so a result cannot be attached to the wrong practice target).
    """
    session = db.get(PracticeSession, result.session_id)
    if session is None:
        raise SessionNotFoundError("No practice session exists for this result.")
    if session.mudra_id != result.reference_mudra_id or session.movement_id != result.reference_movement_id:
        raise ReferenceMismatchError("The result's reference does not match the practice session.")

    payload = result.model_dump(mode="json")
    record = db.scalars(
        select(EvaluationRecord).where(EvaluationRecord.session_id == result.session_id)
    ).first()
    if record is None:
        record = EvaluationRecord(session_id=result.session_id)
        db.add(record)
    record.schema_version = result.schema_version
    record.is_mock = result.is_mock
    record.result_json = payload
    db.commit()
    return record


def get_evaluation_payload(db: Session, session_id: str) -> dict | None:
    record = db.scalars(
        select(EvaluationRecord).where(EvaluationRecord.session_id == session_id)
    ).first()
    return None if record is None else record.result_json


def delete_session(db: Session, session_id: str) -> bool:
    """Privacy: removes the session and (via ON DELETE CASCADE) its evaluation and feedback."""
    session = db.get(PracticeSession, session_id)
    if session is None:
        return False
    db.delete(session)
    db.commit()
    return True
