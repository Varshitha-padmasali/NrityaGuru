import pytest

from app.schemas.feedback import FeedbackExplanation, Observation, Suggestion
from app.services.feedback_evidence import build_evidence_items
from app.services.feedback_validation import (
    InvalidEvidenceCitationError,
    InventedDetailError,
    allowed_numbers,
    check_citations,
    check_no_invented_details,
)
from tests.factories import make_evidence


def _items(sid="mock-session-match"):
    return build_evidence_items(make_evidence(sid))


def _exp(summary="This is MOCK test data.", obs=(), sug=()):
    return FeedbackExplanation(
        overall_summary=summary,
        observations=[Observation(text=t, evidence_ids=ids) for t, ids in obs],
        suggestions=[Suggestion(text=t, evidence_ids=ids) for t, ids in sug],
    )


# ---- citations ----
def test_valid_citations_pass():
    check_citations(_exp(obs=[("ok", ["label"])], sug=[("ok", ["reference", "dtw"])]), _items())


def test_unknown_evidence_id_is_rejected():
    with pytest.raises(InvalidEvidenceCitationError):
        check_citations(_exp(obs=[("x", ["deviation:MOCK-D9"])]), _items())


def test_one_bad_id_among_good_ones_is_rejected():
    with pytest.raises(InvalidEvidenceCitationError):
        check_citations(_exp(sug=[("x", ["label", "invented"])]), _items())


def test_entry_without_citation_is_rejected():
    with pytest.raises(InvalidEvidenceCitationError):
        check_citations(_exp(obs=[("x", [])]), _items())


# ---- invented body parts ----
def test_body_part_not_in_evidence_is_rejected():
    with pytest.raises(InventedDetailError):
        check_no_invented_details(_exp(sug=[("Relax your thumb.", ["reference"])]), _items("mock-session-match"))


def test_generic_finger_advice_is_rejected_when_evidence_names_none():
    with pytest.raises(InventedDetailError):
        check_no_invented_details(_exp(summary="Check your fingers."), _items("mock-session-mismatch"))


def test_body_part_named_in_evidence_is_allowed():
    check_no_invented_details(
        _exp(obs=[("The index finger differs from the reference.", ["deviation:MOCK-D1"])]),
        _items("mock-session-deviation"),
    )


def test_other_body_part_is_still_rejected_when_only_index_finger_is_reported():
    with pytest.raises(InventedDetailError):
        check_no_invented_details(_exp(summary="Your wrist also looks off."), _items("mock-session-deviation"))


# ---- invented video claims ----
@pytest.mark.parametrize("text", ["In your video the hand moved.", "I watched the recording.", "On camera it looked fine."])
def test_claims_about_video_are_rejected(text):
    with pytest.raises(InventedDetailError):
        check_no_invented_details(_exp(summary=text), _items())


# ---- invented numbers ----
def test_number_not_in_evidence_is_rejected():
    with pytest.raises(InventedDetailError):
        check_no_invented_details(_exp(summary="Hold it for 3 seconds."), _items())


def test_numbers_from_evidence_are_allowed():
    check_no_invented_details(
        _exp(obs=[("Confidence was 0.92 and DTW distance was 12.5.", ["label", "dtw"])]), _items()
    )


def test_probability_written_as_percentage_is_allowed():
    assert 92.0 in allowed_numbers(_items())
    check_no_invented_details(_exp(summary="The classifier was 92% confident."), _items())


def test_wrong_percentage_is_rejected():
    with pytest.raises(InventedDetailError):
        check_no_invented_details(_exp(summary="The classifier was 55% confident."), _items())


def test_integer_form_of_a_supplied_float_is_allowed():
    check_no_invented_details(
        _exp(obs=[("The finger was off by 28 degrees compared with 5.", ["deviation:MOCK-D1"])]),
        _items("mock-session-deviation"),
    )


def test_plain_cautious_text_passes():
    check_no_invented_details(
        _exp(summary="This is MOCK test data. The top prediction matched the expected label."), _items()
    )
