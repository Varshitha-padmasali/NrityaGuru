"""Needs FastAPI + SQLAlchemy (not runnable in the authoring sandbox)."""
import json

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_evidence_service, get_feedback_service, get_limiter
from app.core.config import Settings
from app.core.rate_limit import SlidingWindowLimiter
from app.db.database import get_db
from app.integrations.evaluation_stub import MockEvaluationStore, UnavailableEvaluationStore
from app.main import create_app
from app.schemas.evaluation import EvidenceSource
from app.services.evaluation_errors import EvaluationValidationError
from app.services.evaluation_evidence import EvidenceService, build_evidence_service
from app.services.feedback_service import FeedbackService
from app.core.enums import EvaluationErrorCode
from app.services.gemini_client import GeminiRateLimitError
from tests.factories import FakeGenerator, make_reference_info


def _fake_lookup(db, result, *, include_unverified=False):
    return make_reference_info(record_id="mudra_pataka", name="Pataka")


def _good_output():
    return json.dumps({
        "overall_summary": "This is MOCK test data. The evaluation reported a difference in the index finger.",
        "observations": [{"text": "The index finger differs from the reference.", "evidence_ids": ["deviation:MOCK-D1"]}],
        "suggestions": [],
    })


@pytest.fixture
def make_client():
    def _make(generator=None, evidence_service=None, limiter=None):
        app = create_app()
        app.dependency_overrides[get_db] = lambda: None
        app.dependency_overrides[get_evidence_service] = lambda: evidence_service or EvidenceService(
            MockEvaluationStore(), EvidenceSource.MOCK_STORE, reference_lookup=_fake_lookup)
        app.dependency_overrides[get_feedback_service] = lambda: FeedbackService(generator, "test-model" if generator else None)
        app.dependency_overrides[get_limiter] = lambda: limiter or SlidingWindowLimiter(1000, 60)
        return TestClient(app)

    return _make


def _post(client, sid="mock-session-deviation", **extra):
    return client.post("/api/feedback/generate", json={"session_id": sid, **extra})


def test_ai_feedback_for_a_stored_session(make_client):
    r = _post(make_client(FakeGenerator(_good_output())))
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "ai" and body["is_mock"] is True
    assert body["reference"]["name"] == "Pataka"
    assert any(e["evidence_id"] == "deviation:MOCK-D1" for e in body["supporting_evidence"])
    assert body["feedback"]["limitations"]
    assert "No AI watched your video" in body["disclaimer"]


def test_client_supplied_evaluation_claims_are_ignored(make_client):
    r = _post(make_client(None), sid="mock-session-match",
              predicted_labels=[{"label": "tripataka", "confidence": 0.99}], expected_labels=["x"])
    assert r.status_code == 200
    label = next(e for e in r.json()["supporting_evidence"] if e["evidence_id"] == "label")
    assert "'pataka'" in label["statement"] and "tripataka" not in label["statement"]


def test_gemini_failure_still_returns_the_findings(make_client):
    r = _post(make_client(FakeGenerator(error=GeminiRateLimitError("x"))))
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "evidence_only" and body["fallback_reason"] == "rate_limited"
    assert body["feedback"]["observations"]


def test_no_gemini_configured_still_answers(make_client):
    assert _post(make_client(None)).json()["fallback_reason"] == "not_configured"


def test_insufficient_evidence_skips_gemini(make_client):
    gen = FakeGenerator(_good_output())
    r = _post(make_client(gen), sid="mock-session-poor-landmarks")
    assert r.json()["fallback_reason"] == "insufficient_evidence" and gen.calls == 0


def test_unknown_session_returns_404_with_code(make_client):
    r = _post(make_client(None), sid="no-such-session")
    assert r.status_code == 404 and r.json()["code"] == "session_not_found"


@pytest.mark.parametrize("sid", ["ab", "../etc/passwd", "a b c", "x" * 65])
def test_malformed_session_ids_return_422(make_client, sid):
    assert _post(make_client(None), sid=sid).status_code == 422


def test_missing_body_field_returns_422(make_client):
    assert make_client(None).post("/api/feedback/generate", json={}).status_code == 422


def test_unconfigured_evaluation_integration_returns_503(make_client):
    svc = EvidenceService(UnavailableEvaluationStore(), EvidenceSource.STORED_SESSION)
    r = _post(make_client(None, evidence_service=svc))
    assert r.status_code == 503 and r.json()["code"] == "store_unavailable"


def test_unknown_reference_returns_422_with_code(make_client):
    def lookup(db, result, *, include_unverified=False):
        raise EvaluationValidationError(EvaluationErrorCode.UNKNOWN_REFERENCE, "not available")

    svc = EvidenceService(MockEvaluationStore(), EvidenceSource.MOCK_STORE, reference_lookup=lookup)
    r = _post(make_client(None, evidence_service=svc))
    assert r.status_code == 422 and r.json()["code"] == "unknown_reference"


def test_rate_limit_returns_429(make_client):
    client = make_client(None, limiter=SlidingWindowLimiter(1, 60))
    assert _post(client).status_code == 200
    r = _post(client)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1


def test_response_never_contains_secrets_or_internals(make_client):
    text = _post(make_client(FakeGenerator(_good_output()))).text.lower()
    for forbidden in ("api_key", "postgresql", "traceback", "password"):
        assert forbidden not in text
