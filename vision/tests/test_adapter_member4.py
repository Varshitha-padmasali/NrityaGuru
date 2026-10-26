"""Tests for vision.adapter_member4 module.

Validates:
  - Exact slicing of 63-coordinate hand vectors from 260-dim vectors.
  - Proper return of None (never NaNs or zeros) for missing hands.
  - Pixel scaling (x*width, y*height, z*width).
  - Auto-selection between left and right hands based on detection and confidence.
  - Full sequence adaptation to Member 4's expected learner_frames list.
  - DTW matrix extraction and NaN dropping.
  - Readiness checks for evaluation prerequisites.
"""

from __future__ import annotations

import numpy as np
import pytest

from vision.adapter_member4 import (
    AdapterInputError,
    check_sequence_readiness_for_member4,
    extract_hand_for_mlp,
    sequence_to_dtw_matrix,
    sequence_to_member4_frames,
)
from vision.schemas import (
    DataQualityReport,
    FEATURE_DIM,
    LEFT_HAND_COORDS_SLICE,
    LEFT_HAND_SLICE,
    POSE_SLICE,
    RIGHT_HAND_COORDS_SLICE,
    RIGHT_HAND_SLICE,
    VideoMetadata,
)
from vision.sequence_builder import ProcessedSequence


def _create_mock_260_vector(
    has_pose: bool = True,
    has_left: bool = True,
    has_right: bool = True,
    left_conf: float = 0.85,
    right_conf: float = 0.95,
) -> np.ndarray:
    """Helper to create a deterministic 260-dim feature vector."""
    vec = np.zeros((FEATURE_DIM,), dtype=np.float64)

    # Pose [0:132]
    if has_pose:
        vec[POSE_SLICE] = 0.5
    else:
        vec[POSE_SLICE] = np.nan
        vec[3:132:4] = 0.0  # zero visibilities

    # Left Hand [132:196]
    if has_left:
        vec[LEFT_HAND_COORDS_SLICE] = np.linspace(0.1, 0.9, 63)
        vec[LEFT_HAND_SLICE.stop - 1] = left_conf
    else:
        vec[LEFT_HAND_COORDS_SLICE] = np.nan
        vec[LEFT_HAND_SLICE.stop - 1] = 0.0

    # Right Hand [196:260]
    if has_right:
        vec[RIGHT_HAND_COORDS_SLICE] = np.linspace(0.2, 0.8, 63)
        vec[RIGHT_HAND_SLICE.stop - 1] = right_conf
    else:
        vec[RIGHT_HAND_COORDS_SLICE] = np.nan
        vec[RIGHT_HAND_SLICE.stop - 1] = 0.0

    return vec


def test_extract_hand_right_and_left():
    vec = _create_mock_260_vector(has_left=True, has_right=True)

    # Right hand
    right = extract_hand_for_mlp(vec, side="Right")
    assert right is not None
    assert right.shape == (63,)
    np.testing.assert_allclose(right, np.linspace(0.2, 0.8, 63))

    # Left hand
    left = extract_hand_for_mlp(vec, side="Left")
    assert left is not None
    assert left.shape == (63,)
    np.testing.assert_allclose(left, np.linspace(0.1, 0.9, 63))


def test_extract_hand_pixel_scaling():
    vec = _create_mock_260_vector(has_right=True)
    w, h = 640, 480

    scaled = extract_hand_for_mlp(vec, side="Right", width=w, height=h)
    assert scaled is not None
    assert scaled.shape == (63,)

    # x is scaled by w, y by h, z by w
    raw_right = np.linspace(0.2, 0.8, 63)
    expected = raw_right.copy()
    expected[0::3] *= w
    expected[1::3] *= h
    expected[2::3] *= w

    np.testing.assert_allclose(scaled, expected)


def test_extract_hand_auto_selection():
    # Both detected: chooses right because right_conf (0.95) > left_conf (0.85)
    vec_both = _create_mock_260_vector(has_left=True, has_right=True, left_conf=0.85, right_conf=0.95)
    auto_both = extract_hand_for_mlp(vec_both, side="auto")
    assert auto_both is not None
    np.testing.assert_allclose(auto_both, np.linspace(0.2, 0.8, 63))

    # Both detected: chooses left if left_conf > right_conf
    vec_left_higher = _create_mock_260_vector(has_left=True, has_right=True, left_conf=0.99, right_conf=0.50)
    auto_left = extract_hand_for_mlp(vec_left_higher, side="auto")
    assert auto_left is not None
    np.testing.assert_allclose(auto_left, np.linspace(0.1, 0.9, 63))

    # Only left detected
    vec_only_left = _create_mock_260_vector(has_left=True, has_right=False)
    auto_only_left = extract_hand_for_mlp(vec_only_left, side="auto")
    assert auto_only_left is not None
    np.testing.assert_allclose(auto_only_left, np.linspace(0.1, 0.9, 63))

    # Only right detected
    vec_only_right = _create_mock_260_vector(has_left=False, has_right=True)
    auto_only_right = extract_hand_for_mlp(vec_only_right, side="auto")
    assert auto_only_right is not None
    np.testing.assert_allclose(auto_only_right, np.linspace(0.2, 0.8, 63))

    # Neither detected: returns None
    vec_none = _create_mock_260_vector(has_left=False, has_right=False)
    auto_none = extract_hand_for_mlp(vec_none, side="auto")
    assert auto_none is None


def test_missing_hand_returns_none_never_nan_or_zero():
    vec_missing = _create_mock_260_vector(has_left=False, has_right=False)

    assert extract_hand_for_mlp(vec_missing, side="Right") is None
    assert extract_hand_for_mlp(vec_missing, side="Left") is None
    assert extract_hand_for_mlp(vec_missing, side="auto") is None


def test_adapter_validation_errors():
    # Wrong dimensions
    with pytest.raises(AdapterInputError, match="260-dimensional"):
        extract_hand_for_mlp(np.zeros(200))

    # Non-numeric
    with pytest.raises(AdapterInputError, match="must be numeric"):
        extract_hand_for_mlp(["bad"] * 260)

    # Incomplete width/height
    vec = _create_mock_260_vector()
    with pytest.raises(AdapterInputError, match="Both width and height"):
        extract_hand_for_mlp(vec, width=640, height=None)

    # Negative width/height
    with pytest.raises(AdapterInputError, match="must be positive"):
        extract_hand_for_mlp(vec, width=-640, height=480)

    # Invalid side
    with pytest.raises(AdapterInputError, match="Invalid side"):
        extract_hand_for_mlp(vec, side="Head")  # type: ignore


def test_sequence_to_member4_frames():
    # Create 3-frame sequence: frame 0 has hand, frame 1 missing hand, frame 2 has hand
    v0 = _create_mock_260_vector(has_right=True)
    v1 = _create_mock_260_vector(has_right=False)
    v2 = _create_mock_260_vector(has_right=True)
    matrix = np.stack([v0, v1, v2], axis=0)

    frames = sequence_to_member4_frames(matrix, side="Right", width=640, height=480)
    assert len(frames) == 3
    assert frames[0] is not None
    assert frames[1] is None
    assert frames[2] is not None
    assert frames[0].shape == (63,)


def test_sequence_to_dtw_matrix():
    # 4 frames: 0, 1 valid pose; 2 NaN pose; 3 valid pose
    v0 = _create_mock_260_vector(has_pose=True)
    v1 = _create_mock_260_vector(has_pose=True)
    v2 = _create_mock_260_vector(has_pose=False)
    v3 = _create_mock_260_vector(has_pose=True)
    matrix = np.stack([v0, v1, v2, v3], axis=0)

    # DTW for pose with drop_invalid=True
    dtw_mat, valid_indices = sequence_to_dtw_matrix(matrix, target="pose", drop_invalid=True)
    assert dtw_mat.shape == (3, 132)
    assert np.all(np.isfinite(dtw_mat))
    np.testing.assert_array_equal(valid_indices, [0, 1, 3])

    # DTW for full features
    dtw_full, valid_full = sequence_to_dtw_matrix(matrix, target="full", drop_invalid=True)
    # frame 2 has NaN pose, so frame 2 dropped
    assert dtw_full.shape == (3, 260)
    np.testing.assert_array_equal(valid_full, [0, 1, 3])


def test_check_sequence_readiness_for_member4():
    # Sequence of 10 frames, 9 with hands (90% > 80%)
    frames_ok: list[np.ndarray | None] = [np.ones((63,)) for _ in range(9)] + [None]
    diag_ok = check_sequence_readiness_for_member4(frames_ok)
    assert diag_ok["can_evaluate"] is True
    assert diag_ok["reliable"] is True
    assert diag_ok["hand_detection_rate"] == 0.9
    assert diag_ok["can_run_dtw"] is True
    assert len(diag_ok["warnings"]) == 0

    # Sequence of 10 frames, 5 with hands (50% < 80%)
    frames_low: list[np.ndarray | None] = [np.ones((63,)) for _ in range(5)] + [None] * 5
    diag_low = check_sequence_readiness_for_member4(frames_low)
    assert diag_low["can_evaluate"] is True
    assert diag_low["reliable"] is False
    assert diag_low["hand_detection_rate"] == 0.5
    assert len(diag_low["warnings"]) >= 1

    # Sequence with only 1 valid frame (cannot run DTW)
    frames_single: list[np.ndarray | None] = [np.ones((63,))] + [None] * 4
    diag_single = check_sequence_readiness_for_member4(frames_single)
    assert diag_single["can_run_dtw"] is False
    assert any("DTW requires at least 2" in w for w in diag_single["warnings"])


def test_member4_feature_pipeline_integration():
    """Verify that adapted frames match Member 4's exact mudra_mlp.features contract."""
    # Synthesize realistic hand: 21 landmarks
    # landmark 0 (wrist) at (100, 200, 0), landmark 9 (middle MCP) at (100, 150, 0) -> palm size = 50 px
    hand_pts = np.zeros((21, 3), dtype=np.float64)
    hand_pts[0] = [100.0, 200.0, 0.0]  # wrist
    hand_pts[9] = [100.0, 150.0, 0.0]  # middle MCP (distance = 50.0)
    # fingertips 4, 8, 12, 16, 20
    for tip_idx in [4, 8, 12, 16, 20]:
        hand_pts[tip_idx] = [100.0 + tip_idx * 5, 100.0, 0.0]

    flat_coords = hand_pts.reshape(-1)
    assert flat_coords.shape == (63,)

    # Place in right hand slot of 260-dim vector
    vec = np.zeros((FEATURE_DIM,), dtype=np.float64)
    vec[RIGHT_HAND_COORDS_SLICE] = flat_coords
    vec[RIGHT_HAND_SLICE.stop - 1] = 0.99  # confidence

    extracted = extract_hand_for_mlp(vec, side="Right")
    assert extracted is not None
    assert extracted.shape == (63,)

    # Simulate Member 4's normalise_hand and hand_features logic
    coords_reshaped = extracted.reshape(21, 3)
    wrist = coords_reshaped[0]
    shifted = coords_reshaped - wrist
    palm_scale = float(np.linalg.norm(shifted[9]))
    norm_hand = shifted / palm_scale

    assert np.allclose(norm_hand[0], [0.0, 0.0, 0.0])
    assert np.isclose(np.linalg.norm(norm_hand[9]), 1.0)
