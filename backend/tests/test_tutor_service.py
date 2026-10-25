import json

import pytest

from app.core.enums import TutorFallbackReason as R
from app.core.enums import VerificationStatus
from app.services.gemini_client import (
    GeminiEmptyResponseError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeminiUnavailableError,
)
from app.services.tutor_service import TutorService
from tests.factories import FakeGenerator, make_reference, make_retrieval

V = VerificationStatus


def _retrieval():
    ref = make_reference(record_id="m1", name="TestMudra", status=V.SOURCE_CITED,
                         source_id="s1", mapping_source_id=None, limitations=["TEST limitation"])
    return make_retrieval([("river", [ref]), ("krishna", [])])


def _good_json(**over):
    data = {
        "summary": "TEST SUMMARY",
        "concepts": [
            {"concept": "river", "supported": True, "explanation": "TEST", "source_ids": ["m1"]},
            {"concept": "krishna", "supported": False, "explanation": "TEST", "source_ids": []},
        ],
        "suggestions": [],
        "alternatives": [],
        "source_ids": ["m1", "s1"],
        "limitations": ["not yet verified"],
    }
    data.update(over)
    return json.dumps(data)


def test_successful_ai_explanation():
    gen = FakeGenerator(output=_good_json())
    result = TutorService(gen, model="test-model").explain(_retrieval())
    assert result.mode == "ai"
    assert result.model == "test-model"
    assert result.fallback_reason is None
    assert result.explanation.summary == "TEST SUMMARY"
    assert "record_id=m1" in gen.last_prompt


def test_fenced_json_is_accepted():
    gen = FakeGenerator(output="```json\n" + _good_json() + "\n```")
    assert TutorService(gen).explain(_retrieval()).mode == "ai"


def test_no_references_skips_gemini_entirely():
    gen = FakeGenerator(output=_good_json())
    result = TutorService(gen).explain(make_retrieval([("krishna", [])]))
    assert gen.calls == 0
    assert result.mode == "knowledge_only"
    assert result.fallback_reason == R.NO_REFERENCES
    assert result.explanation.concepts[0].supported is False
    assert result.explanation.source_ids == []


def test_not_configured_returns_knowledge_only():
    result = TutorService(None).explain(_retrieval())
    assert result.mode == "knowledge_only"
    assert result.fallback_reason == R.NOT_CONFIGURED
    assert result.model is None


@pytest.mark.parametrize(
    "error,reason",
    [
        (GeminiTimeoutError("x"), R.TIMEOUT),
        (GeminiRateLimitError("x"), R.RATE_LIMITED),
        (GeminiUnavailableError("x"), R.UNAVAILABLE),
        (GeminiEmptyResponseError("x"), R.EMPTY_RESPONSE),
    ],
)
def test_gemini_failures_fall_back_to_knowledge(error, reason):
    result = TutorService(FakeGenerator(error=error)).explain(_retrieval())
    assert result.mode == "knowledge_only"
    assert result.fallback_reason == reason
    assert result.notice


def test_malformed_json_falls_back():
    result = TutorService(FakeGenerator(output="Sure! Here is an answer")).explain(_retrieval())
    assert result.fallback_reason == R.MALFORMED_OUTPUT


def test_wrong_structure_falls_back():
    result = TutorService(FakeGenerator(output=json.dumps({"hello": "world"}))).explain(_retrieval())
    assert result.fallback_reason == R.MALFORMED_OUTPUT


def test_fabricated_source_id_falls_back():
    result = TutorService(FakeGenerator(output=_good_json(source_ids=["m1", "INVENTED"]))).explain(_retrieval())
    assert result.mode == "knowledge_only"
    assert result.fallback_reason == R.INVALID_CITATION


def test_ungrounded_claim_falls_back():
    bad = {"concept": "krishna", "supported": True, "explanation": "TEST", "source_ids": []}
    out = _good_json(concepts=[
        {"concept": "river", "supported": True, "explanation": "TEST", "source_ids": ["m1"]}, bad])
    result = TutorService(FakeGenerator(output=out)).explain(_retrieval())
    assert result.fallback_reason == R.UNGROUNDED_OUTPUT


def test_fallback_contains_only_retrieved_facts():
    result = TutorService(None).explain(_retrieval())
    ex = result.explanation
    river = ex.concepts[0]
    assert river.supported and "TestMudra" in river.explanation
    assert "meaning: TEST MEANING" in river.explanation
    assert "not yet verified" in river.explanation
    assert set(river.source_ids) == {"m1", "s1"}
    assert ex.suggestions == []
    assert "TEST limitation" in ex.limitations
    assert any("No AI explanation" in l for l in ex.limitations)


def test_fallback_lists_multiple_references_as_alternatives():
    refs = [make_reference(record_id="m1", name="One"), make_reference(record_id="m2", name="Two")]
    result = TutorService(None).explain(make_retrieval([("moon", refs)]))
    assert result.explanation.alternatives == ["moon: One, Two"]
