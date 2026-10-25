import json

import pytest

from app.core.enums import TutorFallbackReason as R
from app.core.enums import VerificationStatus
from app.services.gemini_client import GeminiTimeoutError
from app.services.rag_pipeline import RagPipeline
from app.services.text_processing import InputValidationError
from app.services.tutor_service import TutorService
from tests.factories import FakeGenerator, make_reference, make_retrieval


def _retrieval_with_support():
    ref = make_reference(record_id="m1", name="TestMudra", status=VerificationStatus.SOURCE_CITED,
                         source_id="s1", mapping_source_id=None)
    return make_retrieval([("river", [ref]), ("krishna", [])], original_text="river and Krishna")


def _good_ai_output():
    return json.dumps({
        "summary": "TEST SUMMARY not yet verified",
        "concepts": [
            {"concept": "river", "supported": True, "explanation": "TEST", "source_ids": ["m1"]},
            {"concept": "krishna", "supported": False, "explanation": "TEST", "source_ids": []},
        ],
        "source_ids": ["m1"],
    })


class SpyRetriever:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def __call__(self, text, **kwargs):
        self.calls.append((text, kwargs))
        if self.error:
            raise self.error
        return self.response


def test_full_flow_returns_ai_answer_and_retrieval():
    retriever = SpyRetriever(_retrieval_with_support())
    gen = FakeGenerator(output=_good_ai_output())
    out = RagPipeline(retriever, TutorService(gen, model="test-model")).run("river and Krishna")
    assert out.tutor.mode == "ai"
    assert out.tutor.model == "test-model"
    assert out.retrieval.supported_count == 1
    assert out.original_text == "river and Krishna"
    assert "learning aid" in out.disclaimer
    assert gen.calls == 1


def test_options_are_passed_to_retrieval():
    retriever = SpyRetriever(_retrieval_with_support())
    RagPipeline(retriever, TutorService(None)).run(
        "river", include_unverified=True, include_keyword_matches=True
    )
    text, kwargs = retriever.calls[0]
    assert text == "river"
    assert kwargs == {"include_unverified": True, "include_keyword_matches": True}


def test_defaults_are_conservative():
    retriever = SpyRetriever(_retrieval_with_support())
    RagPipeline(retriever, TutorService(None)).run("river")
    assert retriever.calls[0][1] == {"include_unverified": False, "include_keyword_matches": False}


def test_gemini_failure_still_returns_the_retrieved_knowledge():
    retriever = SpyRetriever(_retrieval_with_support())
    out = RagPipeline(retriever, TutorService(FakeGenerator(error=GeminiTimeoutError("x")))).run("river")
    assert out.tutor.mode == "knowledge_only"
    assert out.tutor.fallback_reason == R.TIMEOUT
    assert out.retrieval.concepts[0].references[0].record_id == "m1"
    assert "TestMudra" in out.tutor.explanation.concepts[0].explanation


def test_missing_mapping_means_no_gemini_call_and_no_invented_claim():
    gen = FakeGenerator(output=_good_ai_output())
    retriever = SpyRetriever(make_retrieval([("krishna", []), ("garden", [])]))
    out = RagPipeline(retriever, TutorService(gen)).run("Krishna in the garden")
    assert gen.calls == 0
    assert out.tutor.fallback_reason == R.NO_REFERENCES
    assert all(c.supported is False for c in out.tutor.explanation.concepts)
    assert out.tutor.explanation.source_ids == []
    assert out.retrieval.supported_count == 0


def test_fabricated_citation_from_gemini_is_not_returned_as_ai_answer():
    bad = json.loads(_good_ai_output())
    bad["source_ids"] = ["m1", "INVENTED"]
    out = RagPipeline(SpyRetriever(_retrieval_with_support()),
                      TutorService(FakeGenerator(output=json.dumps(bad)))).run("river")
    assert out.tutor.mode == "knowledge_only"
    assert out.tutor.fallback_reason == R.INVALID_CITATION
    assert "INVENTED" not in out.tutor.explanation.source_ids


def test_invalid_input_propagates():
    retriever = SpyRetriever(error=InputValidationError("Input is empty."))
    with pytest.raises(InputValidationError):
        RagPipeline(retriever, TutorService(None)).run("   ")
