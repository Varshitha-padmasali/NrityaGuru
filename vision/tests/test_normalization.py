"""Unit tests for hand and body pose landmark normalization.

Verifies:
- Translation invariance
- Scale invariance
- Canonical landmark centering (wrist origin, shoulder midpoint origin)
- Degenerate reference landmark handling (NaN propagation)
- Missing detection handling
"""

import numpy as np
import pytest

from vision.normalization import (
    HAND_MIDDLE_MCP_IDX,
    HAND_WRIST_IDX,
    POSE_LEFT_SHOULDER_IDX,
    POSE_RIGHT_SHOULDER_IDX,
    normalize_hand_landmarks,
    normalize_pose_landmarks,
)
from vision.schemas import (
    HandLandmarkSet,
    N_HAND_LANDMARKS,
    N_POSE_LANDMARKS,
    Point3D,
    PoseLandmarkSet,
)


def _make_hand_template(seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    pts = rng.normal(loc=0.5, scale=0.1, size=(N_HAND_LANDMARKS, 3))
    # Ensure wrist and middle MCP have non-zero separation
    pts[HAND_WRIST_IDX] = [0.4, 0.4, 0.0]
    pts[HAND_MIDDLE_MCP_IDX] = [0.4, 0.6, 0.0]
    return pts


def _make_pose_template(seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    pts = rng.normal(loc=0.5, scale=0.1, size=(N_POSE_LANDMARKS, 3))
    # Explicit distinct shoulders
    pts[POSE_LEFT_SHOULDER_IDX] = [0.6, 0.3, 0.0]
    pts[POSE_RIGHT_SHOULDER_IDX] = [0.4, 0.3, 0.0]
    vis = rng.uniform(0.7, 0.99, size=(N_POSE_LANDMARKS,))
    return pts, vis


# ---------------------------------------------------------------------------
# HAND NORMALIZATION TESTS
# ---------------------------------------------------------------------------

def test_hand_normalization_wrist_at_origin_and_unit_palm():
    pts = _make_hand_template()
    norm = normalize_hand_landmarks(pts)

    assert norm.shape == (21, 3)
    # Wrist is at (0, 0, 0)
    assert np.allclose(norm[HAND_WRIST_IDX], [0.0, 0.0, 0.0], atol=1e-7)
    # Distance from wrist to middle MCP is 1.0
    palm_dist = np.linalg.norm(norm[HAND_MIDDLE_MCP_IDX] - norm[HAND_WRIST_IDX])
    assert palm_dist == pytest.approx(1.0, abs=1e-6)


def test_hand_normalization_translation_invariance():
    pts = _make_hand_template()
    norm_base = normalize_hand_landmarks(pts)

    # Translate by arbitrary offset
    offset = np.array([125.0, -84.0, 33.0])
    pts_translated = pts + offset
    norm_translated = normalize_hand_landmarks(pts_translated)

    assert np.allclose(norm_base, norm_translated, atol=1e-6)


def test_hand_normalization_scale_invariance():
    pts = _make_hand_template()
    norm_base = normalize_hand_landmarks(pts)

    # Scale by arbitrary positive factor
    pts_scaled = pts * 4.25
    norm_scaled = normalize_hand_landmarks(pts_scaled)

    assert np.allclose(norm_base, norm_scaled, atol=1e-6)


def test_hand_normalization_degenerate_zero_size():
    pts = _make_hand_template()
    # Force wrist and middle MCP to coincide
    pts[HAND_MIDDLE_MCP_IDX] = pts[HAND_WRIST_IDX]
    norm = normalize_hand_landmarks(pts)

    # Must return NaNs, not crash or produce infinities
    assert norm.shape == (21, 3)
    assert np.all(np.isnan(norm))


def test_hand_normalization_missing_hand_returns_nans():
    missing_hand = HandLandmarkSet.missing("Left")
    norm = normalize_hand_landmarks(missing_hand)
    assert norm.shape == (21, 3)
    assert np.all(np.isnan(norm))


# ---------------------------------------------------------------------------
# POSE NORMALIZATION TESTS
# ---------------------------------------------------------------------------

def test_pose_normalization_shoulder_mid_origin_and_unit_width():
    pts, vis = _make_pose_template()
    norm = normalize_pose_landmarks(np.column_stack([pts, vis]), include_visibility=True)

    assert norm.shape == (33, 4)
    # Mid-shoulder is at origin (0, 0, 0)
    mid_shoulder = (norm[POSE_LEFT_SHOULDER_IDX, :3] + norm[POSE_RIGHT_SHOULDER_IDX, :3]) / 2.0
    assert np.allclose(mid_shoulder, [0.0, 0.0, 0.0], atol=1e-7)

    # Shoulder width is 1.0
    shoulder_dist = np.linalg.norm(norm[POSE_LEFT_SHOULDER_IDX, :3] - norm[POSE_RIGHT_SHOULDER_IDX, :3])
    assert shoulder_dist == pytest.approx(1.0, abs=1e-6)

    # Visibility values are preserved
    assert np.allclose(norm[:, 3], vis, atol=1e-6)


def test_pose_normalization_translation_invariance():
    pts, vis = _make_pose_template()
    pose_arr = np.column_stack([pts, vis])
    norm_base = normalize_pose_landmarks(pose_arr, include_visibility=False)

    # Translate by arbitrary offset
    offset = np.array([-210.0, 95.0, 18.0])
    pose_translated = np.column_stack([pts + offset, vis])
    norm_translated = normalize_pose_landmarks(pose_translated, include_visibility=False)

    assert np.allclose(norm_base, norm_translated, atol=1e-6)


def test_pose_normalization_scale_invariance():
    pts, vis = _make_pose_template()
    pose_arr = np.column_stack([pts, vis])
    norm_base = normalize_pose_landmarks(pose_arr, include_visibility=False)

    # Scale by arbitrary factor
    pose_scaled = np.column_stack([pts * 3.5, vis])
    norm_scaled = normalize_pose_landmarks(pose_scaled, include_visibility=False)

    assert np.allclose(norm_base, norm_scaled, atol=1e-6)


def test_pose_normalization_degenerate_zero_scale():
    pts, vis = _make_pose_template()
    # Force shoulders and hips to all coincide
    pts[:] = [0.5, 0.5, 0.5]
    norm = normalize_pose_landmarks(np.column_stack([pts, vis]), include_visibility=True)

    assert norm.shape == (33, 4)
    assert np.all(np.isnan(norm[:, :3]))
    assert np.all(norm[:, 3] == 0.0)


def test_pose_normalization_missing_pose_returns_nans():
    missing_pose = PoseLandmarkSet.missing()
    norm = normalize_pose_landmarks(missing_pose, include_visibility=True)
    assert norm.shape == (33, 4)
    assert np.all(np.isnan(norm[:, :3]))
    assert np.all(norm[:, 3] == 0.0)
