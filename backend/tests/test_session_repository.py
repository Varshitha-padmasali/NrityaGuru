"""Needs SQLAlchemy (not runnable in the authoring sandbox)."""
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.models import EvaluationRecord, FeedbackRecord, PracticeSession
from app.db.seed import load_seed
from app.repositories import session_repository as sessions
from app.repositories.errors import ReferenceMismatchError, SessionNotFoundError
from app.services.evaluation_evidence import parse_evaluation_payload
from tests.factories import make_eval_result


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def _result(sid="sess-0001", **over):
    return make_eval_result(session_id=sid, reference_mudra_id="mudra_pataka", expected_labels=["pataka"], **over)


def test_create_and_get_session(db_session):
    load_seed(db_session)
    sessions.create_session(db_session, "sess-0001", mudra_id="mudra_pataka")
    assert sessions.get_session(db_session, "sess-0001").mudra_id == "mudra_pataka"
    assert sessions.get_session(db_session, "nope") is None


@pytest.mark.parametrize("kwargs", [{}, {"mudra_id": "a", "movement_id": "b"}])
def test_exactly_one_reference_is_required(db_session, kwargs):
    with pytest.raises(ValueError):
        sessions.create_session(db_session, "sess-0001", **kwargs)


def test_unknown_reference_violates_the_foreign_key(db_session):
    with pytest.raises(IntegrityError):
        sessions.create_session(db_session, "sess-0001", mudra_id="no_such_mudra")


def test_database_check_blocks_a_session_without_any_reference(db_session):
    db_session.add(PracticeSession(id="sess-0002"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_evaluation_result_round_trips_through_the_database(db_session):
    load_seed(db_session)
    sessions.create_session(db_session, "sess-0001", mudra_id="mudra_pataka")
    sessions.save_evaluation_result(db_session, _result())
    parsed = parse_evaluation_payload(sessions.get_evaluation_payload(db_session, "sess-0001"))
    assert parsed.session_id == "sess-0001" and parsed.expected_labels == ["pataka"]
    assert parsed.is_mock is False


def test_saving_again_replaces_the_result(db_session):
    load_seed(db_session)
    sessions.create_session(db_session, "sess-0001", mudra_id="mudra_pataka")
    sessions.save_evaluation_result(db_session, _result())
    sessions.save_evaluation_result(db_session, _result(warnings=["second"]))
    assert _count(db_session, EvaluationRecord) == 1
    assert sessions.get_evaluation_payload(db_session, "sess-0001")["warnings"] == ["second"]


def test_result_for_a_missing_session_is_rejected(db_session):
    with pytest.raises(SessionNotFoundError):
        sessions.save_evaluation_result(db_session, _result())


def test_result_with_a_different_reference_is_rejected(db_session):
    load_seed(db_session)
    sessions.create_session(db_session, "sess-0001", mudra_id="mudra_pataka")
    wrong = make_eval_result(session_id="sess-0001", reference_mudra_id="mudra_tripataka")
    with pytest.raises(ReferenceMismatchError):
        sessions.save_evaluation_result(db_session, wrong)
    assert _count(db_session, EvaluationRecord) == 0


def test_missing_payload_is_none(db_session):
    assert sessions.get_evaluation_payload(db_session, "sess-0001") is None


def test_deleting_a_session_removes_its_results_and_feedback(db_session):
    load_seed(db_session)
    sessions.create_session(db_session, "sess-0001", mudra_id="mudra_pataka")
    sessions.save_evaluation_result(db_session, _result())
    db_session.add(FeedbackRecord(session_id="sess-0001", mode="ai", evidence_level="sufficient",
                                  result_json={"x": 1}))
    db_session.commit()
    assert sessions.delete_session(db_session, "sess-0001") is True
    assert _count(db_session, EvaluationRecord) == 0 and _count(db_session, FeedbackRecord) == 0
    assert sessions.delete_session(db_session, "sess-0001") is False
