import json

import pytest

from app.core.enums import EvaluationErrorCode as Code
from app.core.enums import TutorFallbackReason as R
from app.integrations.evaluation_stub import MockEvaluationStore
from app.schemas.evaluation import EvidenceSource, LandmarkQuality, PredictedLabel
from app.services.evaluation_errors import EvaluationValidationError
from app.services.evaluation_evidence import EvidenceService
from app.services.feedback_service import FeedbackService
from app.services.feedback_workflow import FeedbackWorkflow, evidence_fingerprint, is_reusable
from app.services.gemini_client import GeminiTimeoutError
from tests.factories import (
    FakeGenerator,
    InMemoryFeedbackStore,
    capture_logs,
    make_eval_result,
    make_evidence,
    make_reference_info,
)

GOOD = json.dumps({
    "overall_summary": "The top prediction matched the expected label.",
    "observations": [{"text": "The top prediction was 'testmudra' with confidence 0.9.", "evidence_ids": ["label"]}],
    "suggestions": [],
})
GOOD_MOCK = json.dumps({
    "overall_summary": "This is MOCK test data. The top prediction matched.",
    "observations": [{"text": "The top prediction matched the expected label.", "evidence_ids": ["label"]}],
    "suggestions": [],
})


class _EvStore:
    def __init__(self, result):
        self.result = result

    def get(self, db, session_id):
        return self.result


class _SequenceGenerator:
    """Fails with the given errors first, then returns the output."""

    def __init__(self, errors, output):
        self.errors, self.output, self.calls = list(errors), output, 0

    def generate(self, *, system_instruction, prompt):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return self.output


def _lookup(db, result, *, include_unverified=False):
    return make_reference_info()


def _workflow(gen, *, result=None, store=None, lookup=_lookup):
    evidence = EvidenceService(_EvStore(result or make_eval_result()), EvidenceSource.STORED_SESSION,
                               reference_lookup=lookup)
    store = store if store is not None else InMemoryFeedbackStore()
    return FeedbackWorkflow(evidence, FeedbackService(gen, "test-model"), store), store


def test_first_run_generates_and_saves():
    gen = FakeGenerator(output=GOOD)
    wf, store = _workflow(gen)
    r = wf.run(None, "test-session-1")
    assert r.mode == "ai" and r.saved is True and r.reused is False
    assert gen.calls == 1 and len(store.rows) == 1
    assert r.evidence_fingerprint and len(r.evidence_fingerprint) == 64


def test_second_run_reuses_stored_feedback_without_calling_gemini():
    gen = FakeGenerator(output=GOOD)
    wf, store = _workflow(gen)
    first = wf.run(None, "test-session-1")
    second = wf.run(None, "test-session-1")
    assert gen.calls == 1 and len(store.rows) == 1
    assert second.reused is True and second.saved is True
    assert second.feedback.overall_summary == first.feedback.overall_summary


def test_regenerate_forces_a_new_generation():
    gen = FakeGenerator(output=GOOD)
    wf, store = _workflow(gen)
    wf.run(None, "test-session-1")
    r = wf.run(None, "test-session-1", regenerate=True)
    assert gen.calls == 2 and len(store.rows) == 2 and r.reused is False


def test_transient_fallback_is_saved_but_not_reused():
    gen = _SequenceGenerator([GeminiTimeoutError("x")], GOOD)
    wf, store = _workflow(gen)
    first = wf.run(None, "test-session-1")
    assert first.mode == "evidence_only" and first.fallback_reason == R.TIMEOUT and first.saved is True
    second = wf.run(None, "test-session-1")
    assert second.mode == "ai" and second.reused is False and gen.calls == 2


def test_insufficient_evidence_outcome_is_reused():
    gen = FakeGenerator(output=GOOD)
    wf, store = _workflow(gen, result=make_eval_result(landmark_quality=LandmarkQuality(reliable=False)))
    first = wf.run(None, "test-session-1")
    second = wf.run(None, "test-session-1")
    assert first.fallback_reason == R.INSUFFICIENT_EVIDENCE
    assert second.reused is True and gen.calls == 0 and len(store.rows) == 1


def test_changed_evaluation_result_is_not_served_stale_feedback():
    gen = FakeGenerator(output=GOOD)
    store = InMemoryFeedbackStore()
    wf1, _ = _workflow(gen, store=store)
    wf1.run(None, "test-session-1")
    changed = make_eval_result(predicted_labels=[PredictedLabel(label="other", confidence=0.9)])
    wf2, _ = _workflow(gen, result=changed, store=store)
    r = wf2.run(None, "test-session-1")
    assert r.reused is False and gen.calls == 2 and len(store.rows) == 2


def test_changed_reference_record_is_not_served_stale_feedback():
    gen = FakeGenerator(output=GOOD)
    store = InMemoryFeedbackStore()
    wf1, _ = _workflow(gen, store=store)
    wf1.run(None, "test-session-1")

    def newer_lookup(db, result, *, include_unverified=False):
        return make_reference_info(practice_instructions="NEW VERIFIED INSTRUCTIONS")

    wf2, _ = _workflow(gen, store=store, lookup=newer_lookup)
    assert wf2.run(None, "test-session-1").reused is False


def test_mock_data_is_never_saved_or_reused():
    gen = FakeGenerator(output=GOOD_MOCK)
    evidence = EvidenceService(MockEvaluationStore(), EvidenceSource.MOCK_STORE, reference_lookup=_lookup)
    store = InMemoryFeedbackStore()
    wf = FeedbackWorkflow(evidence, FeedbackService(gen, "test-model"), store)
    a = wf.run(None, "mock-session-match")
    b = wf.run(None, "mock-session-match")
    assert a.is_mock is True and a.saved is False and b.reused is False
    assert store.rows == [] and gen.calls == 2


def test_save_failure_still_returns_the_feedback():
    gen = FakeGenerator(output=GOOD)
    wf, _ = _workflow(gen, store=InMemoryFeedbackStore(fail_save=True))
    with capture_logs() as logs:
        r = wf.run(None, "test-session-1")
    assert r.mode == "ai" and r.saved is False
    assert any("could not be saved" in m for m in logs)


def test_read_failure_falls_back_to_generating():
    gen = FakeGenerator(output=GOOD)
    wf, store = _workflow(gen, store=InMemoryFeedbackStore(fail_latest=True))
    r = wf.run(None, "test-session-1")
    assert gen.calls == 1 and r.saved is True and r.reused is False


def test_evidence_errors_propagate():
    evidence = EvidenceService(_EvStore(None), EvidenceSource.STORED_SESSION, reference_lookup=_lookup)
    wf = FeedbackWorkflow(evidence, FeedbackService(None), InMemoryFeedbackStore())
    with pytest.raises(EvaluationValidationError) as e:
        wf.run(None, "no-such-session")
    assert e.value.code == Code.SESSION_NOT_FOUND


def test_invalid_session_id_is_rejected_before_any_store_access():
    store = InMemoryFeedbackStore()
    evidence = EvidenceService(_EvStore(make_eval_result()), EvidenceSource.STORED_SESSION, reference_lookup=_lookup)
    with pytest.raises(EvaluationValidationError) as e:
        FeedbackWorkflow(evidence, FeedbackService(None), store).run(None, "../etc/passwd")
    assert e.value.code == Code.INVALID_SESSION_ID and store.rows == []


def test_fingerprint_is_stable_and_sensitive():
    a = evidence_fingerprint(make_evidence("mock-session-match"))
    assert a == evidence_fingerprint(make_evidence("mock-session-match"))
    assert a != evidence_fingerprint(make_evidence("mock-session-deviation"))
    assert a != evidence_fingerprint(make_evidence("mock-session-match", instructions="X"))


def test_reuse_rules():
    ok = FeedbackService(None).generate(make_evidence("mock-session-poor-landmarks"))  # insufficient
    ok.evidence_fingerprint = "f1"
    assert is_reusable(ok, "f1") and not is_reusable(ok, "other")
    transient = FeedbackService(None).generate(make_evidence("mock-session-match"))  # not_configured
    transient.evidence_fingerprint = "f1"
    assert not is_reusable(transient, "f1")
