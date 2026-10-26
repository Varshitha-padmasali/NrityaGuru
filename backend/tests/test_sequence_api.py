import json

from fastapi.testclient import TestClient

from app.api.deps import get_limiter, get_sequence_generator
from app.core.config import Settings, get_settings
from app.core.rate_limit import SlidingWindowLimiter
from app.db.database import get_db
from app.db.seed import load_seed
from app.main import create_app


class QueueGenerator:
    def __init__(self, *responses):
        self.responses = list(responses)

    def generate(self, *, system_instruction, prompt):
        return json.dumps(self.responses.pop(0), ensure_ascii=False)


def _client(db_session, *, generator=None, allow_unverified=True):
    settings = Settings(
        _env_file=None,
        app_env="testing",
        allow_unverified_records=allow_unverified,
        tutor_rate_limit_per_minute=60,
    )
    app = create_app(settings)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_sequence_generator] = lambda: generator
    app.dependency_overrides[get_limiter] = lambda: SlidingWindowLimiter(60, 60)
    return TestClient(app)


def test_sequence_api_returns_three_ordered_steps_for_peacock_rain_dancing(db_session):
    load_seed(db_session)
    text = "Peacock is dancing in the rain."
    analysis = {
        "language_code": "en", "language_name": "English", "language_confidence": 0.99,
        "sentence_translations": [{"order": 1, "translation": "A peacock is dancing in the rain."}],
        "events": [
            {"order": 1, "phrase": "Peacock", "event_type": "entity", "concepts": ["peacock"], "lookup_terms": ["peacock"], "negated": False, "context": "subject"},
            {"order": 2, "phrase": "dancing", "event_type": "action", "concepts": ["dancing"], "lookup_terms": ["dance"], "negated": False, "context": "action"},
            {"order": 3, "phrase": "rain", "event_type": "nature", "concepts": ["rain"], "lookup_terms": ["rain"], "negated": False, "context": "setting"},
        ],
        "caveats": [],
    }
    decisions = {"selections": [
        {"event_order": 1, "mudra_ids": ["mudra_mayura"], "reason": "AI suggestion for the bird concept.", "confidence": 0.44, "uncertainty": []},
        {"event_order": 2, "mudra_ids": ["mudra_allapadma"], "reason": "Retrieved source usage.", "confidence": 0.8, "uncertainty": []},
        {"event_order": 3, "mudra_ids": ["mudra_pataka"], "reason": "AI suggestion for the weather concept.", "confidence": 0.29, "uncertainty": []},
    ]}
    client = _client(db_session, generator=QueueGenerator(analysis, decisions))
    response = client.post("/api/knowledge/sequence", json={"text": text})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "ai_assisted" and body["gemini_used"] is True
    assert body["sentence_translations"] == [{
        "position": 1,
        "original_sentence": text,
        "english_translation": "A peacock is dancing in the rain.",
        "translated": True,
        "note": None,
    }]
    assert [step["phrase"] for step in body["ordered_sequence"]] == ["Peacock", "dancing", "rain"]
    assert [step["mudra_id"] for step in body["ordered_sequence"]] == ["mudra_mayura", "mudra_allapadma", "mudra_pataka"]
    assert [step["selection_type"] for step in body["ordered_sequence"]] == ["source_supported", "source_supported", "ai_inferred"]
    assert body["ordered_sequence"][0]["source_citations"][0]["claim_scope"] == (
        "The source is recorded for this concept-to-mudra association; it is not teacher-verified unless the status says verified."
    )


def test_sequence_api_returns_one_translation_for_each_sentence(db_session):
    load_seed(db_session)
    client = _client(db_session)
    response = client.post("/api/knowledge/sequence", json={"text": "The river flows. A tree stands."})
    assert response.status_code == 200
    body = response.json()
    assert len(body["sentence_translations"]) == 2
    assert [item["original_sentence"] for item in body["sentence_translations"]] == ["The river flows.", "A tree stands."]
    assert all(item["translated"] is False and item["english_translation"] is None for item in body["sentence_translations"])
    assert body["gemini_used"] is False


def test_sequence_api_respects_unverified_access_setting(db_session):
    load_seed(db_session)
    client = _client(db_session, allow_unverified=False)
    response = client.post("/api/knowledge/sequence", json={"text": "river", "include_unverified": True})
    assert response.status_code == 403
