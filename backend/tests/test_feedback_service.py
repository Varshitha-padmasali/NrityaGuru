import json

import pytest

from app.core.enums import TutorFallbackReason as R
from app.schemas.evaluation import EvidenceLevel
from app.services.feedback_service import FeedbackService
from app.services.gemini_client import (
    GeminiEmptyResponseError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeminiUnavailableError,
)
from tests.factories import FakeGenerator, make_evidence


def _good(**over):
    data = {
        "overall_summary": "This is MOCK test data. The top prediction matched the expected label, "
                           "and the evaluation reported a difference in the index finger.",
        "observations": [
            {"text": "The classifier's top prediction was 'pataka' with confidence 0.71.", "evidence_ids": ["label"]},
            {"text": "The evaluation reported that the index finger differs from the reference.",
             "evidence_ids": ["deviation:MOCK-D1"]},
        ],
        "suggestions": [
            {"text": "Review the index finger position against the reference.",
             "evidence_ids": ["deviation:MOCK-D1", "reference"]},
        ],
    }
    data.update(over)
    return json.dumps(data)


def _svc(gen, model="test-model"):
    return FeedbackService(gen, model)


# ---- AI path ----
def test_successful_ai_feedback():
    gen = FakeGenerator(output=_good())
    r = _svc(gen).generate(make_evidence("mock-session-deviation"))
    assert r.mode == "ai" and r.model == "test-model" and r.fallback_reason is None
    assert r.is_mock is True and r.session_id == "mock-session-deviation"
    assert r.evidence_level == EvidenceLevel.SUFFICIENT
    assert [o.evidence_ids for o in r.feedback.observations][1] == ["deviation:MOCK-D1"]
    assert "deviation:MOCK-D1" in [e.evidence_id for e in r.supporting_evidence]
    assert "[id=deviation:MOCK-D1]" in gen.last_prompt
    assert "No AI watched your video" in r.disclaimer


def test_limitations_are_always_the_deterministic_ones_never_the_models():
    ev = make_evidence("mock-session-deviation")
    r = _svc(FakeGenerator(output=_good(limitations=["INVENTED LIMITATION"]))).generate(ev)
    assert r.feedback.limitations == ev.assessment.limitations
    assert "INVENTED LIMITATION" not in r.feedback.limitations


def test_fenced_json_is_accepted():
    r = _svc(FakeGenerator(output="```json\n" + _good() + "\n```")).generate(make_evidence("mock-session-deviation"))
    assert r.mode == "ai"


# ---- guards -> evidence-only fallback ----
def _good_for_match(summary):
    """A payload that is valid for the mock-session-match scenario (no deviations)."""
    return json.dumps({
        "overall_summary": summary,
        "observations": [{"text": "The top prediction matched the expected label.", "evidence_ids": ["label"]}],
        "suggestions": [],
    })


@pytest.mark.parametrize(
    "bad_text",
    [
        "Relax your thumb and wrist.",
        "Hold the pose for 3 seconds.",
        "In your video the hand drifts.",
    ],
)
def test_invented_details_are_discarded(bad_text):
    out = _good_for_match("MOCK test data. " + bad_text)
    r = _svc(FakeGenerator(output=out)).generate(make_evidence("mock-session-match"))
    assert r.mode == "evidence_only" and r.fallback_reason == R.UNGROUNDED_OUTPUT
    assert bad_text not in r.feedback.overall_summary


def test_clean_payload_for_the_match_scenario_is_accepted():
    r = _svc(FakeGenerator(output=_good_for_match("MOCK test data. The top prediction matched."))).generate(
        make_evidence("mock-session-match"))
    assert r.mode == "ai"


def test_fabricated_evidence_id_is_discarded():
    bad = json.loads(_good())
    bad["observations"][0]["evidence_ids"] = ["deviation:MOCK-D9"]
    r = _svc(FakeGenerator(output=json.dumps(bad))).generate(make_evidence("mock-session-deviation"))
    assert r.mode == "evidence_only" and r.fallback_reason == R.INVALID_CITATION


def test_uncited_observation_is_discarded():
    bad = json.loads(_good())
    bad["observations"][0]["evidence_ids"] = []
    r = _svc(FakeGenerator(output=json.dumps(bad))).generate(make_evidence("mock-session-deviation"))
    assert r.mode == "evidence_only"
    assert r.fallback_reason in (R.INVALID_CITATION, R.MALFORMED_OUTPUT)  # depends on where it is caught


def test_malformed_output_is_discarded():
    r = _svc(FakeGenerator(output="Sure, here is some feedback!")).generate(make_evidence("mock-session-deviation"))
    assert r.fallback_reason == R.MALFORMED_OUTPUT


def test_wrong_structure_is_discarded():
    r = _svc(FakeGenerator(output=json.dumps({"hello": "world"}))).generate(make_evidence("mock-session-deviation"))
    assert r.fallback_reason == R.MALFORMED_OUTPUT


@pytest.mark.parametrize(
    "error,reason",
    [
        (GeminiTimeoutError("x"), R.TIMEOUT),
        (GeminiRateLimitError("x"), R.RATE_LIMITED),
        (GeminiUnavailableError("x"), R.UNAVAILABLE),
        (GeminiEmptyResponseError("x"), R.EMPTY_RESPONSE),
    ],
)
def test_gemini_failures_return_evidence_only(error, reason):
    r = _svc(FakeGenerator(error=error)).generate(make_evidence("mock-session-deviation"))
    assert r.mode == "evidence_only" and r.fallback_reason == reason and r.notice
    assert r.supporting_evidence  # the learner still gets the findings


# ---- Gemini not called ----
@pytest.mark.parametrize("sid", ["mock-session-poor-landmarks", "mock-session-empty"])
def test_insufficient_evidence_skips_gemini(sid):
    gen = FakeGenerator(output=_good())
    r = _svc(gen).generate(make_evidence(sid))
    assert gen.calls == 0
    assert r.mode == "evidence_only" and r.fallback_reason == R.INSUFFICIENT_EVIDENCE
    assert r.evidence_level == EvidenceLevel.INSUFFICIENT
    assert "not enough reliable evidence" in r.feedback.overall_summary


def test_not_configured_returns_evidence_only():
    r = FeedbackService(None).generate(make_evidence("mock-session-deviation"))
    assert r.mode == "evidence_only" and r.fallback_reason == R.NOT_CONFIGURED and r.model is None


# ---- content of the evidence-only answer ----
def test_mismatch_without_detail_never_names_a_cause():
    r = FeedbackService(None).generate(make_evidence("mock-session-mismatch"))
    body = r.feedback
    assert "did not match the expected label" in body.overall_summary
    assert "did not identify which finger or joint differs" in body.overall_summary
    text = body.overall_summary + " ".join(o.text for o in body.observations) + " ".join(s.text for s in body.suggestions)
    for word in ("thumb", "index", "wrist", "finger "):
        assert word not in text.replace("finger or joint", "")
    assert body.suggestions == []
    assert any("cause cannot be stated" in l for l in body.limitations)


def test_deviation_feedback_restates_only_reported_findings():
    r = FeedbackService(None).generate(make_evidence("mock-session-deviation"))
    sug = r.feedback.suggestions[0]
    assert sug.evidence_ids == ["deviation:MOCK-D1"] and "index_finger" in sug.text and "28" in sug.text
    assert {o.evidence_ids[0] for o in r.feedback.observations} >= {"label", "dtw", "deviation:MOCK-D1", "landmarks"}


def test_unreliable_landmarks_give_capture_advice_citing_the_evidence():
    r = FeedbackService(None).generate(make_evidence("mock-session-poor-landmarks"))
    assert [s.evidence_ids for s in r.feedback.suggestions] == [["landmarks"]]
    assert any("unreliable" in l for l in r.feedback.limitations)


def test_insufficient_evidence_does_not_present_findings_built_on_unreliable_data():
    r = FeedbackService(None).generate(make_evidence("mock-session-poor-landmarks"))
    assert [o.evidence_ids for o in r.feedback.observations] == [["landmarks"]]
    assert "Comparison result" not in " ".join(o.text for o in r.feedback.observations)
    # ...but nothing is hidden: the full evidence is still listed for transparency
    assert "label" in [e.evidence_id for e in r.supporting_evidence]


def test_empty_evidence_gives_no_observations_or_suggestions():
    r = FeedbackService(None).generate(make_evidence("mock-session-empty"))
    assert r.feedback.observations == [] and r.feedback.suggestions == []


def test_reference_instructions_are_offered_when_available():
    r = FeedbackService(None).generate(make_evidence("mock-session-match", instructions="TEST INSTRUCTIONS TEXT"))
    assert r.feedback.suggestions[0].evidence_ids == ["reference_instructions"]
    assert "TEST INSTRUCTIONS TEXT" in r.feedback.suggestions[0].text
    assert r.reference.instructions_available is True


def test_mock_data_is_marked_in_summary_and_flag():
    r = FeedbackService(None).generate(make_evidence("mock-session-match"))
    assert r.is_mock is True and r.feedback.overall_summary.startswith("MOCK TEST DATA.")


def test_match_summary_is_hedged_and_not_a_verdict():
    r = FeedbackService(None).generate(make_evidence("mock-session-match"))
    s = r.feedback.overall_summary
    assert "matched the expected label" in s and "not expert judgement" in s
    for word in ("perfect", "correct", "wrong", "incorrect", "video"):
        assert word not in s.lower()


def test_every_citation_in_the_result_exists_in_supporting_evidence():
    for sid in ("mock-session-match", "mock-session-deviation", "mock-session-mismatch", "mock-session-poor-landmarks"):
        r = FeedbackService(None).generate(make_evidence(sid))
        valid = {e.evidence_id for e in r.supporting_evidence}
        for entry in [*r.feedback.observations, *r.feedback.suggestions]:
            assert set(entry.evidence_ids) <= valid
