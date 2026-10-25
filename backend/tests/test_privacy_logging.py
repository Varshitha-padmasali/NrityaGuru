"""Learner text, keys and upstream error text must never reach the logs."""
import json

from app.services.feedback_service import FeedbackService
from app.services.feedback_workflow import FeedbackWorkflow
from app.services.gemini_client import classify_error
from app.services.tutor_service import TutorService
from tests.factories import (
    FakeGenerator,
    InMemoryFeedbackStore,
    capture_logs,
    make_evidence,
    make_reference,
    make_retrieval,
)
from tests.test_feedback_workflow import GOOD, _workflow
from app.services.gemini_client import GeminiRateLimitError, GeminiTimeoutError

SECRET_TEXT = "UNIQUE-LEARNER-TEXT-98765"
SECRET_ERR = "key=SECRET-KEY-123 host=db password=hunter2"


def _joined(logs):
    return " | ".join(logs)


def _assert_clean(logs):
    text = _joined(logs)
    assert logs, "nothing was logged, so this check would prove nothing"
    for secret in (SECRET_TEXT, "SECRET-KEY-123", "hunter2", "UNIQUE-DEVIATION-TEXT"):
        assert secret not in text


def _retrieval():
    ref = make_reference(record_id="m1", source_id="s1", mapping_source_id=None)
    return make_retrieval([("river", [ref])], original_text=SECRET_TEXT)


def test_tutor_gemini_failure_does_not_log_text_or_error_message():
    svc = TutorService(FakeGenerator(error=GeminiTimeoutError(SECRET_ERR)))
    with capture_logs() as logs:
        svc.explain(_retrieval())
    _assert_clean(logs)


def test_tutor_rejected_output_does_not_log_text():
    bad = json.dumps({"summary": SECRET_TEXT, "concepts": [], "source_ids": ["INVENTED"]})
    for output in ("not json " + SECRET_TEXT, bad):
        with capture_logs() as logs:
            TutorService(FakeGenerator(output=output)).explain(_retrieval())
        _assert_clean(logs)


def test_feedback_failures_do_not_log_evidence_or_error_text():
    for gen in (FakeGenerator(error=GeminiRateLimitError(SECRET_ERR)),
                FakeGenerator(output="UNIQUE-DEVIATION-TEXT not json")):
        with capture_logs() as logs:
            FeedbackService(gen).generate(make_evidence("mock-session-deviation"))
        _assert_clean(logs)


def test_workflow_save_failure_does_not_log_session_or_text():
    wf, _ = _workflow(FakeGenerator(output=GOOD), store=InMemoryFeedbackStore(fail_save=True))
    with capture_logs() as logs:
        wf.run(None, "test-session-1")
    assert logs and "test-session-1" not in _joined(logs)


def test_classified_gemini_errors_keep_no_upstream_text():
    class Boom(Exception):
        code = 500

    err = classify_error(Boom(SECRET_ERR))
    assert "SECRET-KEY-123" not in str(err) and "hunter2" not in str(err)
