"""Needs FastAPI + SQLAlchemy (not runnable in the authoring sandbox)."""
import json
import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.deps import get_feedback_store, get_feedback_workflow, get_limiter
from app.core.config import Settings, get_settings
from app.core.rate_limit import SlidingWindowLimiter
from app.db.database import get_db
from app.db.seed import load_seed
from app.integrations.database_evaluation_store import DatabaseEvaluationStore
from app.main import create_app
from app.repositories import session_repository as sessions
from app.repositories.feedback_repository import SqlFeedbackStore
from app.schemas.evaluation import DtwSummary, EvidenceSource, LandmarkQuality, PredictedLabel
from app.services.evaluation_evidence import EvidenceService
from app.services.feedback_service import FeedbackService
from app.services.feedback_workflow import FeedbackWorkflow
from tests.factories import FakeGenerator, InMemoryFeedbackStore, make_eval_result

SID = "api-session-1"
OUTPUT = json.dumps({
    "overall_summary": "The top prediction matched the expected label.",
    "observations": [{"text": "The top prediction was 'pataka' with confidence 0.9.", "evidence_ids": ["label"]}],
    "suggestions": [],
})
ORIGIN = "http://localhost:3000"


@pytest.fixture
def make_client(db_session):
    load_seed(db_session)
    sessions.create_session(db_session, SID, mudra_id="mudra_pataka")
    sessions.save_evaluation_result(db_session, make_eval_result(
        session_id=SID, reference_mudra_id="mudra_pataka", expected_labels=["pataka"],
        predicted_labels=[PredictedLabel(label="pataka", confidence=0.9)],
        dtw=DtwSummary(distance=10.0, normalized_distance=0.1),
        landmark_quality=LandmarkQuality(hand_detection_rate=0.95, reliable=True)))

    def _make(generator=None, workflow_store=None, settings=None):
        settings = settings or Settings(_env_file=None, allow_unverified_records=True, cors_allow_origins=ORIGIN)
        app = create_app(settings)
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_settings] = lambda: settings
        wf = FeedbackWorkflow(
            EvidenceService(DatabaseEvaluationStore(), EvidenceSource.STORED_SESSION, include_unverified=True),
            FeedbackService(generator, "test-model" if generator else None),
            workflow_store or SqlFeedbackStore(),
        )
        app.dependency_overrides[get_feedback_workflow] = lambda: wf
        app.dependency_overrides[get_feedback_store] = lambda: SqlFeedbackStore()
        app.dependency_overrides[get_limiter] = lambda: SlidingWindowLimiter(1000, 60)
        return TestClient(app)

    return _make


def _post(client, sid=SID, **extra):
    return client.post("/api/feedback/generate", json={"session_id": sid, **extra})


def test_second_request_reuses_stored_feedback(make_client):
    gen = FakeGenerator(OUTPUT)
    client = make_client(gen)
    first, second = _post(client).json(), _post(client).json()
    assert first["mode"] == "ai" and first["saved"] is True and first["reused"] is False
    assert second["reused"] is True and gen.calls == 1


def test_regenerate_creates_a_new_feedback(make_client):
    gen = FakeGenerator(OUTPUT)
    client = make_client(gen)
    _post(client)
    assert _post(client, regenerate=True).json()["reused"] is False and gen.calls == 2


def test_get_returns_the_stored_feedback_without_generating(make_client):
    gen = FakeGenerator(OUTPUT)
    client = make_client(gen)
    assert client.get(f"/api/feedback/{SID}").status_code == 404  # nothing stored yet
    _post(client)
    r = client.get(f"/api/feedback/{SID}")
    assert r.status_code == 200 and r.json()["reused"] is True and gen.calls == 1


@pytest.mark.parametrize("sid", ["ab", "a b c", "x" * 65])
def test_malformed_ids_return_422(make_client, sid):
    client = make_client(None)
    assert client.get(f"/api/feedback/{sid}").status_code == 422
    assert _post(client, sid=sid).status_code == 422


def test_unknown_session_returns_404_with_code(make_client):
    r = _post(make_client(None), sid="no-such-session")
    assert r.status_code == 404 and r.json()["code"] == "session_not_found"


def test_save_failure_still_returns_feedback(make_client):
    r = _post(make_client(FakeGenerator(OUTPUT), workflow_store=InMemoryFeedbackStore(fail_save=True)))
    assert r.status_code == 200 and r.json()["mode"] == "ai" and r.json()["saved"] is False


def test_database_failure_returns_a_safe_503(make_client):
    client = make_client(None)

    def boom():
        raise OperationalError("SELECT 1", {}, Exception("password=hunter2 host=db"))

    client.app.dependency_overrides[get_db] = boom
    for r in (_post(client), client.get(f"/api/feedback/{SID}")):
        assert r.status_code == 503 and "hunter2" not in r.text and "Traceback" not in r.text


def test_readiness_endpoint(make_client):
    client = make_client(None)
    assert client.get("/health/ready").json() == {"status": "ready", "database": "ok"}

    def boom():
        raise OperationalError("SELECT 1", {}, Exception("secret"))

    client.app.dependency_overrides[get_db] = boom
    r = client.get("/health/ready")
    assert r.status_code == 503 and "secret" not in r.text


def test_cors_allows_only_the_configured_origin(make_client):
    client = make_client(None)
    headers = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    ok = client.options("/api/feedback/generate", headers={"Origin": ORIGIN, **headers})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == ORIGIN
    bad = client.options("/api/feedback/generate", headers={"Origin": "https://evil.example", **headers})
    assert "access-control-allow-origin" not in bad.headers


def test_secrets_and_learner_data_never_reach_logs_or_responses(make_client, caplog):
    settings = Settings(
        _env_file=None, allow_unverified_records=True, cors_allow_origins=ORIGIN,
        gemini_api_key="fake-secret-key", database_url="postgresql+psycopg://u:pw-secret@h/db",
    )
    caplog.set_level(logging.DEBUG)
    client = make_client(FakeGenerator(OUTPUT), settings=settings)
    responses = [_post(client), _post(client, regenerate=True), client.get(f"/api/feedback/{SID}")]
    client.app.dependency_overrides[get_db] = lambda: (_ for _ in ()).throw(
        OperationalError("SELECT 1", {}, Exception("pw-secret")))
    responses.append(_post(client))
    for text in [r.text for r in responses] + [caplog.text]:
        assert "fake-secret-key" not in text and "pw-secret" not in text
        assert "postgresql+psycopg" not in text
