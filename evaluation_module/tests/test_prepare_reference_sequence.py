import pytest

from data_prep.prepare_reference_sequence import build_candidate


def test_candidate_sequence_is_never_marked_verified():
    candidate = build_candidate(
        reference_id="reference-pataka-001",
        target_id="mudra_pataka",
        source="consented teacher recording",
        consent_reference="consent-001",
        frames=[[0.0] * 78],
    )
    assert candidate["feature_schema"] == "hand-v1"
    assert candidate["feature_dimensions"] == 78
    assert candidate["review_status"] == "candidate"
    assert "reviewer_identity" not in candidate


@pytest.mark.parametrize("kwargs", [
    {"frames": []},
    {"frames": [[float("nan")] * 78]},
    {"frames": [[0.0] * 77]},
    {"source": "   "},
])
def test_candidate_rejects_missing_or_invalid_provenance_and_features(kwargs):
    args = {
        "reference_id": "reference-pataka-001",
        "target_id": "mudra_pataka",
        "source": "consented teacher recording",
        "consent_reference": "consent-001",
        "frames": [[0.0] * 78],
    }
    args.update(kwargs)
    with pytest.raises(ValueError):
        build_candidate(**args)
