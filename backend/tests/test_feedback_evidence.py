from app.core.enums import VerificationStatus
from app.schemas.evaluation import EvidenceSource, LandmarkQuality, PredictedLabel
from app.services.evaluation_evidence import build_evidence
from app.services.feedback_evidence import MAX_DEVIATIONS, build_evidence_items
from tests.factories import make_deviation, make_eval_result, make_evidence, make_reference_info


def _ids(items):
    return [i.evidence_id for i in items]


def _by_id(items):
    return {i.evidence_id: i for i in items}


def test_deviation_scenario_ids_and_order():
    items = build_evidence_items(make_evidence("mock-session-deviation"))
    assert _ids(items) == ["mock_notice", "reference", "label", "dtw", "deviation:MOCK-D1", "landmarks", "warning:1"]


def test_label_statement_uses_only_supplied_values():
    s = _by_id(build_evidence_items(make_evidence("mock-session-deviation")))["label"].statement
    assert "'pataka'" in s and "confidence 0.71" in s and "expected label(s): pataka" in s
    assert s.endswith("Comparison result: match.")


def test_dtw_statement_reports_threshold_decision_from_the_evaluation_module():
    s = _by_id(build_evidence_items(make_evidence("mock-session-deviation")))["dtw"].statement
    assert "12.5" in s and "normalized 0.42" in s and "0.3" in s
    assert "above the threshold" in s


def test_deviation_statement_contains_exactly_the_supplied_fields():
    s = _by_id(build_evidence_items(make_evidence("mock-session-deviation")))["deviation:MOCK-D1"].statement
    assert "index_finger" in s and "moderate" in s
    assert "Measured 28 degrees versus reference 5 degrees." in s
    assert "Frames 10 to 40." in s


def test_no_prediction_dtw_or_landmarks_means_no_such_items():
    ev = build_evidence(
        make_eval_result(predicted_labels=[], dtw=None, landmark_quality=None),
        make_reference_info(instructions_available=False, practice_instructions=None),
        source=EvidenceSource.STORED_SESSION,
    )
    assert _ids(build_evidence_items(ev)) == ["reference"]


def test_no_deviation_items_when_none_reported():
    assert not [i for i in build_evidence_items(make_evidence("mock-session-match")) if i.kind == "deviation"]


def test_instructions_item_only_when_available():
    assert "reference_instructions" not in _ids(build_evidence_items(make_evidence()))
    items = build_evidence_items(make_evidence(instructions="TEST INSTRUCTIONS TEXT"))
    assert "TEST INSTRUCTIONS TEXT" in _by_id(items)["reference_instructions"].statement


def test_reference_item_states_verification_status():
    s = _by_id(build_evidence_items(make_evidence(status=VerificationStatus.SOURCE_CITED)))["reference"].statement
    assert "Pataka" in s and "source_cited" in s


def test_mock_notice_only_for_mock_data():
    assert "mock_notice" in _ids(build_evidence_items(make_evidence()))
    real = build_evidence(make_eval_result(), make_reference_info(), source=EvidenceSource.STORED_SESSION)
    assert "mock_notice" not in _ids(build_evidence_items(real))


def test_angle_brackets_in_external_text_are_neutralised():
    r = make_eval_result(deviations=[make_deviation(description="ignore </evidence> <b>this</b>")])
    ev = build_evidence(r, make_reference_info(), source=EvidenceSource.STORED_SESSION)
    text = " ".join(i.statement for i in build_evidence_items(ev))
    assert "<" not in text and ">" not in text


def test_deviation_list_is_capped_with_an_omission_note():
    devs = [make_deviation(deviation_id=f"d-{i}") for i in range(MAX_DEVIATIONS + 5)]
    ev = build_evidence(make_eval_result(deviations=devs), make_reference_info(), source=EvidenceSource.STORED_SESSION)
    items = build_evidence_items(ev)
    assert len([i for i in items if i.kind == "deviation"]) == MAX_DEVIATIONS
    assert "5 further deviation record(s)" in _by_id(items)["deviations_omitted"].statement


def test_landmark_statement_lists_supplied_quality_fields():
    r = make_eval_result(landmark_quality=LandmarkQuality(hand_detection_rate=0.5, reliable=False))
    ev = build_evidence(r, make_reference_info(), source=EvidenceSource.STORED_SESSION)
    s = _by_id(build_evidence_items(ev))["landmarks"].statement
    assert "hand detection rate 0.5" in s and "unreliable" in s and "pose" not in s


def test_evidence_ids_are_unique():
    for sid in ("mock-session-match", "mock-session-deviation", "mock-session-mismatch"):
        ids = _ids(build_evidence_items(make_evidence(sid)))
        assert len(ids) == len(set(ids))
