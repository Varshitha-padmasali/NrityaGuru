"""End-to-end flows through the REAL database layer (SQLite in tests). Needs SQLAlchemy."""
import json

import pytest
from sqlalchemy import func, select

from app.core.enums import EvaluationErrorCode as Code
from app.db.models import EvaluationRecord, FeedbackRecord, Mudra, Source
from app.db.seed import load_seed
from app.integrations.database_evaluation_store import DatabaseEvaluationStore
from app.repositories import session_repository as sessions
from app.repositories.feedback_repository import SqlFeedbackStore
from app.schemas.evaluation import DtwSummary, EvidenceSource, LandmarkQuality, PredictedLabel
from app.services.evaluation_errors import EvaluationValidationError
from app.services.evaluation_evidence import EvidenceService
from app.services.feedback_service import FeedbackService
from app.services.feedback_workflow import FeedbackWorkflow
from app.services.knowledge_retrieval import retrieve_for_text
from app.services.tutor_service import TutorService
from tests.factories import FakeGenerator, make_eval_result

SID = "integ-session-1"

TUTOR_OUTPUT = json.dumps({
    "summary": "River is listed for Pataka in a cited source that is not yet verified.",
    "concepts": [{"concept": "river", "supported": True, "explanation": "Listed usage.",
                  "source_ids": ["src_mirror_of_gesture_1917"]}],
    "suggestions": [], "alternatives": [],
    "source_ids": ["mudra_pataka", "src_mirror_of_gesture_1917"], "limitations": ["not yet verified"],
})
FEEDBACK_OUTPUT = json.dumps({
    "overall_summary": "The top prediction matched the expected label. The reference is from a cited source and is not yet verified.",
    "observations": [{"text": "The top prediction was 'pataka' with confidence 0.9.", "evidence_ids": ["label"]}],
    "suggestions": [],
})


def _eval(**over):
    data = dict(
        session_id=SID, reference_mudra_id="mudra_pataka", expected_labels=["pataka"],
        predicted_labels=[PredictedLabel(label="pataka", confidence=0.9)],
        dtw=DtwSummary(distance=10.0, normalized_distance=0.1),
        landmark_quality=LandmarkQuality(hand_detection_rate=0.95, reliable=True),
    )
    data.update(over)
    return make_eval_result(**data)


def _workflow(gen, include_unverified=True):
    evidence = EvidenceService(DatabaseEvaluationStore(), EvidenceSource.STORED_SESSION,
                               include_unverified=include_unverified)
    return FeedbackWorkflow(evidence, FeedbackService(gen, "test-model"), SqlFeedbackStore())


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model))


@pytest.fixture
def prepared(db_session):
    load_seed(db_session)
    sessions.create_session(db_session, SID, mudra_id="mudra_pataka")
    sessions.save_evaluation_result(db_session, _eval())
    return db_session


# ---- knowledge -> tutor ----
def test_knowledge_to_tutor_flow_cites_only_real_database_ids(db_session):
    load_seed(db_session)
    retrieval = retrieve_for_text(db_session, "The river", include_unverified=True)
    result = TutorService(FakeGenerator(output=TUTOR_OUTPUT), "test-model").explain(retrieval)
    assert result.mode == "ai"
    for cited in result.explanation.source_ids:
        assert db_session.get(Mudra, cited) is not None or db_session.get(Source, cited) is not None


def test_knowledge_to_tutor_flow_without_supported_mapping_never_calls_gemini(db_session):
    load_seed(db_session)
    gen = FakeGenerator(output=TUTOR_OUTPUT)
    retrieval = retrieve_for_text(db_session, "A zephyr meets a quux.", include_unverified=True)
    result = TutorService(gen).explain(retrieval)
    assert gen.calls == 0 and result.fallback_reason.value == "no_references"


# ---- evaluation -> feedback ----
def test_evaluation_to_feedback_flow_with_storage_and_reuse(prepared):
    gen = FakeGenerator(output=FEEDBACK_OUTPUT)
    wf = _workflow(gen)
    first = wf.run(prepared, SID)
    assert first.mode == "ai" and first.saved is True and first.reference.name == "Pataka"
    assert any("No verified practice instructions" in n for n in first.feedback.limitations)
    second = wf.run(prepared, SID)
    assert second.reused is True and gen.calls == 1 and _count(prepared, FeedbackRecord) == 1
    wf.run(prepared, SID, regenerate=True)
    assert gen.calls == 2 and _count(prepared, FeedbackRecord) == 2


def test_replacing_the_evaluation_result_invalidates_stored_feedback(prepared):
    gen = FakeGenerator(output=FEEDBACK_OUTPUT)
    wf = _workflow(gen)
    wf.run(prepared, SID)
    sessions.save_evaluation_result(prepared, _eval(predicted_labels=[PredictedLabel(label="other", confidence=0.9)]))
    assert wf.run(prepared, SID).reused is False and gen.calls == 2


def test_corrupt_evaluation_row_is_rejected(db_session):
    load_seed(db_session)
    sessions.create_session(db_session, SID, mudra_id="mudra_pataka")
    db_session.add(EvaluationRecord(session_id=SID, schema_version="1.0",
                                    result_json={"schema_version": "1.0", "session_id": SID}))
    db_session.commit()
    with pytest.raises(EvaluationValidationError) as e:
        _workflow(FakeGenerator()).run(db_session, SID)
    assert e.value.code == Code.MALFORMED_RESULT


def test_mock_labelled_row_cannot_pass_as_a_real_evaluation(db_session):
    load_seed(db_session)
    sessions.create_session(db_session, SID, mudra_id="mudra_pataka")
    sessions.save_evaluation_result(db_session, _eval(is_mock=True))
    with pytest.raises(EvaluationValidationError) as e:
        _workflow(FakeGenerator()).run(db_session, SID)
    assert e.value.code == Code.MOCK_DATA_IN_REAL_STORE


def test_session_without_an_evaluation_is_not_found(db_session):
    load_seed(db_session)
    sessions.create_session(db_session, SID, mudra_id="mudra_pataka")
    with pytest.raises(EvaluationValidationError) as e:
        _workflow(FakeGenerator()).run(db_session, SID)
    assert e.value.code == Code.SESSION_NOT_FOUND


def test_hidden_unverified_reference_is_rejected_in_verified_only_mode(prepared):
    with pytest.raises(EvaluationValidationError) as e:
        _workflow(FakeGenerator(), include_unverified=False).run(prepared, SID)
    assert e.value.code == Code.UNKNOWN_REFERENCE


def test_deleting_a_session_removes_everything_and_the_flow_then_reports_not_found(prepared):
    wf = _workflow(FakeGenerator(output=FEEDBACK_OUTPUT))
    wf.run(prepared, SID)
    assert sessions.delete_session(prepared, SID) is True
    assert _count(prepared, EvaluationRecord) == 0 and _count(prepared, FeedbackRecord) == 0
    with pytest.raises(EvaluationValidationError) as e:
        wf.run(prepared, SID)
    assert e.value.code == Code.SESSION_NOT_FOUND
