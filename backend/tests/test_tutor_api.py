"""Needs FastAPI + SQLAlchemy (not runnable in the authoring sandbox)."""
import json

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_limiter, get_tutor_service
from app.core.config import Settings, get_settings
from app.core.rate_limit import SlidingWindowLimiter
from app.db.database import DatabaseNotConfiguredError, get_db
from app.db.seed import load_seed
from app.main import create_app
from app.services.gemini_client import GeminiRateLimitError
from app.services.tutor_service import TutorService


class FakeGenerator:
    def __init__(self, output=None, error=None):
        self.output, self.error, self.calls = output, error, 0

    def generate(self, *, system_instruction, prompt):
        self.calls += 1
        if self.error:
            raise self.error
        return self.output


def _ai_output():
    return json.dumps({
        "summary": "River is listed for Pataka, from a cited source that is not yet verified.",
        "concepts": [{"concept": "river", "supported": True, "explanation": "TEST",
                      "source_ids": ["mudra_pataka"]}],
        "source_ids": ["mudra_pataka"],
        "limitations": ["not yet verified"],
    })


@pytest.fixture
def make_client(db_session):
    def _make(generator=None, allow_unverified=True, limiter=None):
        app = create_app()
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None, allow_unverified_records=allow_unverified
        )
        app.dependency_overrides[get_tutor_service] = lambda: TutorService(generator, "test-model" if generator else None)
        app.dependency_overrides[get_limiter] = lambda: limiter or SlidingWindowLimiter(1000, 60)
        return TestClient(app)

    return _make


def test_ai_answer_with_retrieval(db_session, make_client):
    load_seed(db_session)
    gen = FakeGenerator(_ai_output())
    r = make_client(gen).post("/api/tutor/explain", json={"text": "river", "include_unverified": True})
    assert r.status_code == 200
    body = r.json()
    assert body["tutor"]["mode"] == "ai"
    assert body["retrieval"]["supported_count"] == 1
    assert body["retrieval"]["concepts"][0]["references"][0]["record_id"] == "mudra_pataka"
    assert "teacher" in body["disclaimer"]


def test_gemini_rate_limit_returns_knowledge_with_200(db_session, make_client):
    load_seed(db_session)
    r = make_client(FakeGenerator(error=GeminiRateLimitError("x"))).post(
        "/api/tutor/explain", json={"text": "river", "include_unverified": True})
    assert r.status_code == 200
    body = r.json()
    assert body["tutor"]["mode"] == "knowledge_only"
    assert body["tutor"]["fallback_reason"] == "rate_limited"
    assert body["retrieval"]["supported_count"] == 1


def test_no_gemini_configured_still_answers(db_session, make_client):
    load_seed(db_session)
    r = make_client(None).post("/api/tutor/explain", json={"text": "river", "include_unverified": True})
    assert r.status_code == 200
    assert r.json()["tutor"]["fallback_reason"] == "not_configured"


def test_default_verified_only_mode_finds_nothing_and_skips_gemini(db_session, make_client):
    load_seed(db_session)
    gen = FakeGenerator(_ai_output())
    r = make_client(gen).post("/api/tutor/explain", json={"text": "river"})
    assert r.status_code == 200
    assert r.json()["tutor"]["fallback_reason"] == "no_references"
    assert gen.calls == 0


def test_unverified_request_forbidden_when_server_disallows(db_session, make_client):
    r = make_client(None, allow_unverified=False).post(
        "/api/tutor/explain", json={"text": "river", "include_unverified": True})
    assert r.status_code == 403


@pytest.mark.parametrize("payload", [{}, {"text": ""}, {"text": "   "}, {"text": "1234"}, {"text": "a" * 1001}])
def test_invalid_requests_return_422(make_client, payload):
    assert make_client(None).post("/api/tutor/explain", json=payload).status_code == 422


def test_rate_limit_returns_429_with_retry_after(db_session, make_client):
    load_seed(db_session)
    client = make_client(None, limiter=SlidingWindowLimiter(1, 60))
    assert client.post("/api/tutor/explain", json={"text": "river"}).status_code == 200
    r = client.post("/api/tutor/explain", json={"text": "river"})
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1


def test_database_down_returns_safe_503(make_client):
    client = make_client(None)

    def boom():
        raise DatabaseNotConfiguredError("DATABASE_URL is not set")

    client.app.dependency_overrides[get_db] = boom
    assert client.post("/api/tutor/explain", json={"text": "river"}).status_code == 503


def test_response_never_contains_secrets(db_session, make_client):
    load_seed(db_session)
    r = make_client(FakeGenerator(_ai_output())).post(
        "/api/tutor/explain", json={"text": "river", "include_unverified": True})
    assert "api_key" not in r.text.lower()
    assert "postgresql" not in r.text.lower()
