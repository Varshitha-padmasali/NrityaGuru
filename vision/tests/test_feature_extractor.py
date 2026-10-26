"""Unit tests for fixed-schema 260-dim feature extractor and Member 4 adapter."""

import numpy as np
import pytest

from vision.feature_extractor import (
    ExtractedFrameFeatures,
    extract_frame_features,
    extract_hand_for_mlp,
    feature_names,
)
from vision.schemas import (
    FEATURE_DIM,
    HAND_FEAT_DIM,
    HandLandmarkSet,
    N_HAND_LANDMARKS,
    N_POSE_LANDMARKS,
    Point3D,
    PoseLandmarkSet,
)


def _make_hand(side: str = "Right", conf: float = 0.85) -> HandLandmarkSet:
    pts = [Point3D(x=0.3 + 0.01 * i, y=0.4 + 0.01 * i, z=-0.02 + 0.005 * i) for i in range(N_HAND_LANDMARKS)]
    # Ensure wrist and middle MCP separation
    pts[0] = Point3D(x=0.3, y=0.4, z=0.0)
    pts[9] = Point3D(x=0.3, y=0.5, z=0.0)
    return HandLandmarkSet(side=side, landmarks=pts, confidence=conf, is_detected=True)  # type: ignore


def _make_pose(conf: float = 0.92) -> PoseLandmarkSet:
    pts = [Point3D(x=0.5 + 0.005 * i, y=0.2 + 0.01 * i, z=0.01, visibility=0.9) for i in range(N_POSE_LANDMARKS)]
    pts[11] = Point3D(x=0.6, y=0.3, z=0.0, visibility=0.95)
    pts[12] = Point3D(x=0.4, y=0.3, z=0.0, visibility=0.95)
    return PoseLandmarkSet(landmarks=pts, confidence=conf, is_detected=True)


def test_feature_names_count_and_ordering():
    names = feature_names()
    assert len(names) == 260

    # Pose: [0:132]
    assert names[0] == "pose_lm0_x"
    assert names[1] == "pose_lm0_y"
    assert names[2] == "pose_lm0_z"
    assert names[3] == "pose_lm0_vis"
    assert names[131] == "pose_lm32_vis"

    # Left Hand: [132:196]
    assert names[132] == "left_hand_lm0_x"
    assert names[194] == "left_hand_lm20_z"
    assert names[195] == "left_hand_confidence"

    # Right Hand: [196:260]
    assert names[196] == "right_hand_lm0_x"
    assert names[258] == "right_hand_lm20_z"
    assert names[259] == "right_hand_confidence"


def test_extract_full_features():
    pose = _make_pose(conf=0.90)
    left_hand = _make_hand(side="Left", conf=0.82)
    right_hand = _make_hand(side="Right", conf=0.88)

    feat = extract_frame_features(
        frame_idx=10,
        timestamp_ms=333,
        pose=pose,
        left_hand=left_hand,
        right_hand=right_hand,
    )

    assert isinstance(feat, ExtractedFrameFeatures)
    assert feat.frame_idx == 10
    assert feat.timestamp_ms == 333
    assert feat.timestamp_s == pytest.approx(0.333)
    assert feat.schema_version == "260-v1"
    assert feat.pose_detected
    assert feat.left_hand_detected
    assert feat.right_hand_detected

    vec = feat.feature_vector
    assert vec.shape == (260,)
    assert vec.dtype == np.float64
    assert np.all(np.isfinite(vec))

    # Slice methods
    pose_feats = feat.get_pose_features()
    assert pose_feats.shape == (132,)

    left_coords = feat.get_left_hand_features(include_confidence=False)
    assert left_coords.shape == (63,)
    left_full = feat.get_left_hand_features(include_confidence=True)
    assert left_full.shape == (64,)
    assert left_full[-1] == pytest.approx(0.82)

    right_coords = feat.get_right_hand_features(include_confidence=False)
    assert right_coords.shape == (63,)
    right_full = feat.get_right_hand_features(include_confidence=True)
    assert right_full.shape == (64,)
    assert right_full[-1] == pytest.approx(0.88)


def test_missing_left_hand_slot():
    pose = _make_pose()
    left_hand = HandLandmarkSet.missing("Left")
    right_hand = _make_hand(side="Right", conf=0.91)

    feat = extract_frame_features(
        frame_idx=1,
        timestamp_ms=33,
        pose=pose,
        left_hand=left_hand,
        right_hand=right_hand,
    )

    assert feat.pose_detected
    assert not feat.left_hand_detected
    assert feat.right_hand_detected

    vec = feat.feature_vector
    # Pose is finite
    assert np.all(np.isfinite(vec[0:132]))

    # Left hand coordinates are NaN, confidence is 0.0
    assert np.all(np.isnan(vec[132:195]))
    assert vec[195] == 0.0

    # Right hand is finite
    assert np.all(np.isfinite(vec[196:260]))
    assert vec[259] == pytest.approx(0.91)


def test_missing_right_hand_slot():
    pose = _make_pose()
    left_hand = _make_hand(side="Left", conf=0.78)
    right_hand = HandLandmarkSet.missing("Right")

    feat = extract_frame_features(
        frame_idx=2,
        timestamp_ms=66,
        pose=pose,
        left_hand=left_hand,
        right_hand=right_hand,
    )

    assert feat.pose_detected
    assert feat.left_hand_detected
    assert not feat.right_hand_detected

    vec = feat.feature_vector
    # Left hand is finite
    assert np.all(np.isfinite(vec[132:196]))
    assert vec[195] == pytest.approx(0.78)

    # Right hand coordinates are NaN, confidence is 0.0
    assert np.all(np.isnan(vec[196:259]))
    assert vec[259] == 0.0


def test_both_hands_missing_frame_retained():
    pose = _make_pose()
    feat = extract_frame_features(
        frame_idx=3,
        timestamp_ms=100,
        pose=pose,
        left_hand=None,
        right_hand=None,
    )

    # Body frame is retained
    assert feat.pose_detected
    assert not feat.left_hand_detected
    assert not feat.right_hand_detected

    # Pose features finite
    assert np.all(np.isfinite(feat.get_pose_features()))

    # Hands coordinates are NaNs
    assert np.all(np.isnan(feat.get_left_hand_features(include_confidence=False)))
    assert np.all(np.isnan(feat.get_right_hand_features(include_confidence=False)))

    # Validity mask
    mask = feat.validity_mask()
    assert mask.shape == (260,)
    assert np.sum(mask[0:132]) == 132  # pose is valid
    assert np.sum(mask[132:195]) == 0  # left coords invalid
    assert np.sum(mask[196:259]) == 0  # right coords invalid


def test_member4_mlp_adapter_detected_hand():
    hand = _make_hand(side="Right")
    # First landmark is (0.3, 0.4, 0.0)
    coords = extract_hand_for_mlp(hand, width=640, height=480)

    assert coords is not None
    assert coords.shape == (63,)
    assert coords[0] == pytest.approx(0.3 * 640)
    assert coords[1] == pytest.approx(0.4 * 480)
    assert coords[2] == pytest.approx(0.0 * 640)
    assert np.all(np.isfinite(coords))


def test_member4_mlp_adapter_missing_hand_returns_none():
    missing_hand = HandLandmarkSet.missing("Left")
    assert extract_hand_for_mlp(missing_hand, width=640, height=480) is None
    assert extract_hand_for_mlp(None, width=640, height=480) is None


def test_member4_mlp_adapter_invalid_dimensions():
    hand = _make_hand()
    with pytest.raises(ValueError, match="positive"):
        extract_hand_for_mlp(hand, width=0, height=480)
    with pytest.raises(ValueError, match="positive"):
        extract_hand_for_mlp(hand, width=640, height=-10)
