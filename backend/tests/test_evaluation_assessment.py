from app.core.enums import VerificationStatus
from app.schemas.evaluation import (
    DtwSummary,
    EvidenceLevel,
    LabelMatch,
    LandmarkQuality,
    PredictedLabel,
)
from app.services.evaluation_assessment import (
    DTW_NOTE,
    LOW_CONFIDENCE,
    MISMATCH_NO_DETAIL,
    MOCK_NOTE,
    assess,
    compare_labels,
    landmark_reliability,
    split_deviations,
    top_prediction,
)
from tests.factories import make_deviation, make_eval_result, make_reference_info

V = VerificationStatus


def _p(label, conf=None):
    return PredictedLabel(label=label, confidence=conf)


# ---- labels ----
def test_top_prediction_prefers_highest_confidence():
    assert top_prediction([_p("a", 0.2), _p("b", 0.9), _p("c", 0.5)]).label == "b"


def test_predictions_without_confidence_rank_last():
    assert top_prediction([_p("a"), _p("b", 0.1)]).label == "b"
    assert top_prediction([_p("a"), _p("b")]).label == "a"
    assert top_prediction([]) is None


def test_label_comparison():
    assert compare_labels(["Pataka"], [_p("pataka", 0.9)]) == LabelMatch.MATCH
    assert compare_labels(["pataka"], [_p("tripataka", 0.9)]) == LabelMatch.MISMATCH
    assert compare_labels([], [_p("pataka")]) == LabelMatch.UNKNOWN
    assert compare_labels(["pataka"], []) == LabelMatch.UNKNOWN


def test_only_the_top_prediction_decides_the_match():
    preds = [_p("pataka", 0.3), _p("tripataka", 0.8)]
    assert compare_labels(["pataka"], preds) == LabelMatch.MISMATCH


# ---- landmarks ----
def test_explicit_reliable_flag_wins_over_rates():
    q = LandmarkQuality(hand_detection_rate=0.1, reliable=True)
    assert landmark_reliability(q) == (True, None)


def test_reliability_estimated_from_rates_with_a_note():
    ok, note = landmark_reliability(LandmarkQuality(hand_detection_rate=0.9, pose_detection_rate=0.8))
    assert ok is True and "estimated" in note
    bad, _ = landmark_reliability(LandmarkQuality(hand_detection_rate=0.9, pose_detection_rate=0.3))
    assert bad is False


def test_reliability_unknown_without_information():
    assert landmark_reliability(None)[0] is None
    assert landmark_reliability(LandmarkQuality())[0] is None


# ---- deviations ----
def test_specific_vs_general_deviations():
    specific = make_deviation(deviation_id="dev-a", body_part="thumb")
    measured = make_deviation(deviation_id="dev-b", body_part=None, measured_value=3.0)
    general = make_deviation(deviation_id="dev-c", body_part=None)
    s, g = split_deviations([specific, measured, general])
    assert [d.deviation_id for d in s] == ["dev-a", "dev-b"]
    assert [d.deviation_id for d in g] == ["dev-c"]


# ---- full assessment ----
def test_strong_evidence_is_sufficient_and_names_no_invented_error():
    a = assess(make_eval_result(), make_reference_info())
    assert a.level == EvidenceLevel.SUFFICIENT
    assert a.label_match == LabelMatch.MATCH
    assert a.can_name_specific_error is False
    assert DTW_NOTE in a.limitations


def test_mismatch_without_specific_deviation_states_it_cannot_name_a_cause():
    r = make_eval_result(predicted_labels=[_p("other", 0.9)])
    a = assess(r, make_reference_info())
    assert a.label_match == LabelMatch.MISMATCH
    assert MISMATCH_NO_DETAIL in a.limitations
    assert a.can_name_specific_error is False


def test_specific_deviation_allows_naming_the_error():
    r = make_eval_result(predicted_labels=[_p("other", 0.9)], deviations=[make_deviation()])
    a = assess(r, make_reference_info())
    assert a.can_name_specific_error is True
    assert MISMATCH_NO_DETAIL not in a.limitations
    assert a.specific_deviations[0].body_part == "index_finger"


def test_general_deviation_is_flagged():
    r = make_eval_result(deviations=[make_deviation(body_part=None)])
    a = assess(r, make_reference_info())
    assert a.can_name_specific_error is False
    assert any("general terms" in n for n in a.limitations)


def test_low_confidence_limits_the_evidence():
    r = make_eval_result(predicted_labels=[_p("testmudra", LOW_CONFIDENCE - 0.01)])
    a = assess(r, make_reference_info())
    assert a.level == EvidenceLevel.LIMITED
    assert any("confidence is low" in n for n in a.limitations)


def test_missing_dtw_limits_the_evidence():
    a = assess(make_eval_result(dtw=None), make_reference_info())
    assert a.dtw_available is False
    assert a.level == EvidenceLevel.LIMITED
    assert "No DTW comparison was provided." in a.limitations


def test_unreliable_landmarks_make_evidence_insufficient():
    r = make_eval_result(landmark_quality=LandmarkQuality(reliable=False))
    a = assess(r, make_reference_info())
    assert a.level == EvidenceLevel.INSUFFICIENT
    assert any("unreliable" in n for n in a.limitations)


def test_nothing_usable_is_insufficient():
    r = make_eval_result(predicted_labels=[], dtw=None, deviations=[], landmark_quality=None)
    a = assess(r, make_reference_info())
    assert a.level == EvidenceLevel.INSUFFICIENT
    assert any("No predicted label" in n for n in a.limitations)


def test_unknown_landmark_quality_is_limited_not_sufficient():
    a = assess(make_eval_result(landmark_quality=None), make_reference_info())
    assert a.landmarks_reliable is None
    assert a.level == EvidenceLevel.LIMITED


def test_missing_instructions_and_unverified_reference_are_reported():
    ref = make_reference_info(instructions_available=False, practice_instructions=None,
                              verification_status=V.SOURCE_CITED)
    a = assess(make_eval_result(), ref)
    assert any("No verified practice instructions" in n for n in a.limitations)
    assert any("not verified (status: source_cited)" in n for n in a.limitations)


def test_mock_data_is_labelled():
    assert MOCK_NOTE in assess(make_eval_result(is_mock=True), make_reference_info()).limitations


def test_evaluation_warnings_are_passed_through():
    a = assess(make_eval_result(warnings=["camera too far"]), make_reference_info())
    assert "Evaluation module warning: camera too far" in a.limitations


def test_assessment_reports_only_supplied_values():
    r = make_eval_result(predicted_labels=[_p("testmudra", 0.9)])
    a = assess(r, make_reference_info())
    assert a.top_label == "testmudra" and a.top_confidence == 0.9
    assert a.specific_deviations == [] and a.general_deviations == []
