"""Needs the REAL pydantic (validators, patterns, ranges). Not runnable in the authoring sandbox."""
import pytest

from app.core.enums import EvaluationErrorCode as Code
from app.schemas.evaluation import EvaluationResult, FrameInterval, PredictedLabel
from app.services.evaluation_errors import EvaluationValidationError
from app.services.evaluation_evidence import parse_evaluation_payload

VALID = {
    "schema_version": "1.0",
    "session_id": "test-session-1",
    "reference_mudra_id": "mudra_pataka",
    "expected_labels": ["pataka"],
    "predicted_labels": [{"label": "pataka", "confidence": 0.9}],
}


def _payload(**over):
    data = dict(VALID)
    data.update(over)
    return data


def test_minimal_valid_payload_parses():
    r = parse_evaluation_payload(VALID)
    assert r.session_id == "test-session-1" and r.is_mock is False


def test_extra_unknown_fields_are_ignored():
    assert parse_evaluation_payload(_payload(surprise="x")).session_id == "test-session-1"


@pytest.mark.parametrize(
    "bad",
    [
        {"predicted_labels": [{"label": "pataka", "confidence": 1.5}]},
        {"predicted_labels": [{"label": "pataka", "confidence": -0.1}]},
        {"predicted_labels": [{"label": "<script>alert(1)</script>"}]},
        {"predicted_labels": [{"label": "line\nbreak"}]},
        {"session_id": "../etc"},
        {"session_id": "ab"},
        {"schema_version": "one"},
        {"reference_mudra_id": None},  # neither reference id set
        {"reference_movement_id": "mv_1"},  # both reference ids set
        {"dtw": {"distance": -1}},
        {"deviations": [{"deviation_id": "d1", "kind": "wizardry", "description": "x"}]},
        {"deviations": [{"deviation_id": "d1", "kind": "finger", "description": ""}]},
        {"landmark_quality": {"hand_detection_rate": 1.2}},
        {"expected_labels": ["x"] * 21},
    ],
)
def test_malformed_payloads_are_rejected(bad):
    with pytest.raises(EvaluationValidationError) as e:
        parse_evaluation_payload(_payload(**bad))
    assert e.value.code == Code.MALFORMED_RESULT


def test_non_object_payloads_are_rejected():
    for bad in (None, [], "text", 5):
        with pytest.raises(EvaluationValidationError):
            parse_evaluation_payload(bad)


def test_error_message_lists_fields_but_never_values():
    secret = "SUPER-SECRET-VALUE"
    with pytest.raises(EvaluationValidationError) as e:
        parse_evaluation_payload(_payload(session_id=secret + " bad id"))
    assert secret not in e.value.message
    assert "session_id" in e.value.message


@pytest.mark.parametrize("start,end", [(10, 5)])
def test_frame_interval_must_be_ordered(start, end):
    with pytest.raises(ValueError):
        FrameInterval(start_frame=start, end_frame=end)


def test_frame_interval_times_must_be_ordered():
    with pytest.raises(ValueError):
        FrameInterval(start_frame=0, end_frame=5, start_time_s=2.0, end_time_s=1.0)


def test_valid_interval_is_accepted():
    assert FrameInterval(start_frame=0, end_frame=0).end_frame == 0


def test_label_pattern_accepts_normal_names():
    for name in ("pataka", "Ardha Pataka", "pataka_left", "class-3", "v1.2"):
        assert PredictedLabel(label=name).label == name
