import copy

import pytest

from sequence.reference import ReferenceSequenceError, validate_reference


@pytest.fixture
def reference():
    return {
        "schema_version": 1,
        "id": "teacher-reviewed-reference-001",
        "mudra_id": "mudra_pataka",
        "feature_schema": "hand-v1",
        "evaluator_version": "0.2-prototype",
        "normalization": "wrist_relative_hand_scale",
        "review_status": "teacher_verified",
        "feature_dimensions": 78,
        "frames": [[0.0] * 78, [0.1] * 78],
        "provenance": {
            "source": "consented_teacher_recording_001",
            "performer_consent": "consent_record_001",
            "reviewer": "dance_teacher_001",
            "review_date": "2026-10-26",
        },
    }


def test_valid_reference_is_accepted_and_detached(reference):
    loaded = validate_reference(reference, expected_feature_schema="hand-v1", expected_evaluator_version="0.2-prototype", expected_dimensions=78)
    assert len(loaded["frames"]) == 2
    loaded["frames"][0][0] = 99
    assert reference["frames"][0][0] == 0


@pytest.mark.parametrize("change, message", [
    (lambda p: p.update(review_status="candidate"), "teacher_verified"),
    (lambda p: p.update(feature_dimensions=62), "feature_dimensions"),
    (lambda p: p.update(frames=[[float("nan")]] * 2, feature_dimensions=1), "NaN"),
    (lambda p: p.update(frames=[]), "non-empty"),
    (lambda p: p["provenance"].pop("reviewer"), "provenance"),
])
def test_invalid_references_are_rejected(reference, change, message):
    payload = copy.deepcopy(reference)
    change(payload)
    with pytest.raises(ReferenceSequenceError, match=message):
        validate_reference(payload)


def test_feature_schema_mismatch_is_rejected(reference):
    with pytest.raises(ReferenceSequenceError, match="feature_schema"):
        validate_reference(reference, expected_feature_schema="pose_and_hand_v2")


def test_evaluator_version_and_dimensions_must_match(reference):
    with pytest.raises(ReferenceSequenceError, match="evaluator_version"):
        validate_reference(reference, expected_evaluator_version="0.3")
    with pytest.raises(ReferenceSequenceError, match="feature dimensions"):
        validate_reference(reference, expected_dimensions=63)
