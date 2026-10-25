"""Needs SQLAlchemy. Reference lookup and the full evidence flow on the seed data."""
import pytest

from app.core.enums import EvaluationErrorCode as Code
from app.core.enums import VerificationStatus
from app.db.models import Movement, Source
from app.db.seed import load_seed
from app.integrations.evaluation_stub import MockEvaluationStore
from app.schemas.evaluation import EvidenceSource
from app.services.evaluation_errors import EvaluationValidationError
from app.services.evaluation_evidence import EvidenceService
from app.services.reference_lookup import UNKNOWN_REFERENCE_MESSAGE, lookup_reference
from tests.factories import make_eval_result

V = VerificationStatus


def test_mudra_reference_with_flag(db_session):
    load_seed(db_session)
    ref = lookup_reference(db_session, make_eval_result(reference_mudra_id="mudra_pataka"),
                           include_unverified=True)
    assert ref.record_type == "mudra" and ref.name == "Pataka"
    assert ref.verification_status == V.SOURCE_CITED
    assert ref.instructions_available is False  # seed has no practice instructions yet
    assert ref.source.id == "src_wikipedia_mudra_list"


def test_unverified_reference_is_hidden_by_default_with_same_message_as_missing(db_session):
    load_seed(db_session)
    with pytest.raises(EvaluationValidationError) as hidden:
        lookup_reference(db_session, make_eval_result(reference_mudra_id="mudra_pataka"))
    with pytest.raises(EvaluationValidationError) as missing:
        lookup_reference(db_session, make_eval_result(reference_mudra_id="no_such"), include_unverified=True)
    assert hidden.value.code == missing.value.code == Code.UNKNOWN_REFERENCE
    assert hidden.value.message == missing.value.message == UNKNOWN_REFERENCE_MESSAGE


def test_movement_reference_with_instructions(db_session):
    db_session.add(Source(id="src_t", source_name="TEST SOURCE (test data)", source_type="test"))
    db_session.flush()
    db_session.add(Movement(id="mv_test", name="TestAdavu", movement_category="TEST",
                            practice_instructions="TEST INSTRUCTIONS", source_id="src_t",
                            verification_status=V.VERIFIED))
    db_session.flush()
    r = make_eval_result(reference_mudra_id=None, reference_movement_id="mv_test")
    ref = lookup_reference(db_session, r)
    assert ref.record_type == "movement"
    assert ref.instructions_available is True
    assert ref.practice_instructions == "TEST INSTRUCTIONS"


def test_unknown_movement_is_rejected(db_session):
    r = make_eval_result(reference_mudra_id=None, reference_movement_id="nope")
    with pytest.raises(EvaluationValidationError) as e:
        lookup_reference(db_session, r)
    assert e.value.code == Code.UNKNOWN_REFERENCE


def test_full_flow_with_mock_store_and_seed(db_session):
    load_seed(db_session)
    svc = EvidenceService(MockEvaluationStore(), EvidenceSource.MOCK_STORE, include_unverified=True)
    ev = svc.load(db_session, "mock-session-deviation")
    assert ev.is_mock is True
    assert ev.reference.record_id == "mudra_pataka"
    assert ev.assessment.can_name_specific_error is True
    assert any("No verified practice instructions" in n for n in ev.assessment.limitations)
    assert any("not verified" in n for n in ev.assessment.limitations)


def test_full_flow_rejects_hidden_reference_in_verified_only_mode(db_session):
    load_seed(db_session)
    svc = EvidenceService(MockEvaluationStore(), EvidenceSource.MOCK_STORE, include_unverified=False)
    with pytest.raises(EvaluationValidationError) as e:
        svc.load(db_session, "mock-session-match")
    assert e.value.code == Code.UNKNOWN_REFERENCE
