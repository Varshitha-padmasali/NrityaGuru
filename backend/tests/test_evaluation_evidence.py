import pytest

from app.core.enums import EvaluationErrorCode as Code
from app.integrations.evaluation_stub import (
    MOCK_SCENARIOS,
    EvaluationUnavailableError,
    MockEvaluationStore,
    UnavailableEvaluationStore,
)
from app.schemas.evaluation import EvidenceLevel, EvidenceSource
from app.services.evaluation_errors import EvaluationValidationError
from app.services.evaluation_evidence import EvidenceService, build_evidence, check_schema_version
from tests.factories import make_eval_result, make_reference_info


def _fake_lookup(db, result, *, include_unverified=False):
    return make_reference_info(record_id=result.reference_mudra_id or result.reference_movement_id)


class _Store:
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error

    def get(self, db, session_id):
        if self.error:
            raise self.error
        return self.result


def _service(store, source=EvidenceSource.STORED_SESSION, lookup=_fake_lookup):
    return EvidenceService(store, source, reference_lookup=lookup)


# ---- version ----
@pytest.mark.parametrize("version", ["1.0", "1.7"])
def test_same_major_version_is_accepted(version):
    check_schema_version(make_eval_result(schema_version=version))


@pytest.mark.parametrize("version", ["2.0", "0.9", "3.0"])
def test_other_major_versions_are_rejected(version):
    with pytest.raises(EvaluationValidationError) as e:
        check_schema_version(make_eval_result(schema_version=version))
    assert e.value.code == Code.UNSUPPORTED_VERSION


# ---- mock-data guard ----
def test_mock_data_cannot_pass_as_real():
    with pytest.raises(EvaluationValidationError) as e:
        build_evidence(make_eval_result(is_mock=True), make_reference_info(), source=EvidenceSource.STORED_SESSION)
    assert e.value.code == Code.MOCK_DATA_IN_REAL_STORE


def test_mock_store_evidence_is_flagged_mock():
    ev = build_evidence(make_eval_result(is_mock=True), make_reference_info(), source=EvidenceSource.MOCK_STORE)
    assert ev.is_mock is True


def test_real_evidence_is_not_flagged_mock():
    ev = build_evidence(make_eval_result(), make_reference_info(), source=EvidenceSource.STORED_SESSION)
    assert ev.is_mock is False and ev.assessment.level == EvidenceLevel.SUFFICIENT


# ---- session id handling ----
@pytest.mark.parametrize("bad", ["", "ab", "a b c", "../etc/passwd", "x" * 65, "-leadinghyphen", "id;drop"])
def test_bad_session_ids_are_rejected_before_any_lookup(bad):
    store = _Store(make_eval_result())
    with pytest.raises(EvaluationValidationError) as e:
        _service(store).load(None, bad)
    assert e.value.code == Code.INVALID_SESSION_ID


def test_unknown_session_is_not_found():
    with pytest.raises(EvaluationValidationError) as e:
        _service(_Store(None)).load(None, "no-such-session")
    assert e.value.code == Code.SESSION_NOT_FOUND


def test_store_returning_a_different_session_is_rejected():
    with pytest.raises(EvaluationValidationError) as e:
        _service(_Store(make_eval_result(session_id="other-session"))).load(None, "test-session-1")
    assert e.value.code == Code.SESSION_MISMATCH


def test_unavailable_store_gives_a_safe_error():
    with pytest.raises(EvaluationValidationError) as e:
        _service(_Store(error=EvaluationUnavailableError("secret internals"))).load(None, "test-session-1")
    assert e.value.code == Code.STORE_UNAVAILABLE
    assert "secret" not in e.value.message


def test_unconfigured_integration_reports_unavailable():
    with pytest.raises(EvaluationValidationError) as e:
        _service(UnavailableEvaluationStore()).load(None, "test-session-1")
    assert e.value.code == Code.STORE_UNAVAILABLE


def test_unknown_reference_from_lookup_is_passed_through():
    def lookup(db, result, *, include_unverified=False):
        raise EvaluationValidationError(Code.UNKNOWN_REFERENCE, "not found")

    with pytest.raises(EvaluationValidationError) as e:
        _service(_Store(make_eval_result()), lookup=lookup).load(None, "test-session-1")
    assert e.value.code == Code.UNKNOWN_REFERENCE


def test_unsupported_version_in_store_is_rejected():
    with pytest.raises(EvaluationValidationError) as e:
        _service(_Store(make_eval_result(schema_version="3.0"))).load(None, "test-session-1")
    assert e.value.code == Code.UNSUPPORTED_VERSION


# ---- mock store scenarios ----
def test_every_mock_scenario_is_labelled_and_valid():
    store = MockEvaluationStore()
    for sid in MOCK_SCENARIOS:
        r = store.get(None, sid)
        assert r.is_mock is True and r.session_id == sid
        assert any("MOCK" in w for w in r.warnings)
        assert r.reference_mudra_id and r.reference_movement_id is None


def test_mock_store_unknown_session_and_fresh_copies():
    store = MockEvaluationStore()
    assert store.get(None, "nope") is None
    a, b = store.get(None, "mock-session-match"), store.get(None, "mock-session-match")
    a.warnings.append("changed")
    assert "changed" not in b.warnings


def test_mock_scenarios_produce_the_intended_assessments():
    svc = _service(MockEvaluationStore(), source=EvidenceSource.MOCK_STORE)
    levels = {sid: svc.load(None, sid).assessment for sid in MOCK_SCENARIOS}
    assert levels["mock-session-match"].level == EvidenceLevel.SUFFICIENT
    assert levels["mock-session-deviation"].can_name_specific_error is True
    assert levels["mock-session-mismatch"].can_name_specific_error is False
    assert levels["mock-session-poor-landmarks"].level == EvidenceLevel.INSUFFICIENT
    assert levels["mock-session-empty"].level == EvidenceLevel.INSUFFICIENT
    assert all(a for a in levels.values())
