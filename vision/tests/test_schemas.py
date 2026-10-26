"""Unit tests for vision schemas and data models."""

import math
import numpy as np
import pytest

from vision.schemas import (
    DataQualityReport,
    FEATURE_DIM,
    HAND_FEAT_DIM,
    HandLandmarkSet,
    LEFT_HAND_COORDS_SLICE,
    LEFT_HAND_SLICE,
    N_HAND_LANDMARKS,
    N_POSE_LANDMARKS,
    Point3D,
    POSE_FEAT_DIM,
    POSE_SLICE,
    PoseLandmarkSet,
    RIGHT_HAND_COORDS_SLICE,
    RIGHT_HAND_SLICE,
    VideoMetadata,
)


def test_schema_constants():
    assert N_POSE_LANDMARKS == 33
    assert N_HAND_LANDMARKS == 21
    assert POSE_FEAT_DIM == 132
    assert HAND_FEAT_DIM == 64
    assert FEATURE_DIM == 260
    assert POSE_SLICE == slice(0, 132)
    assert LEFT_HAND_SLICE == slice(132, 196)
    assert RIGHT_HAND_SLICE == slice(196, 260)
    assert LEFT_HAND_COORDS_SLICE == slice(132, 195)
    assert RIGHT_HAND_COORDS_SLICE == slice(196, 259)


def test_point3d_conversions():
    pt = Point3D(x=0.5, y=0.25, z=0.1, visibility=0.95)
    assert not pt.is_nan()
    arr3 = pt.to_array(include_visibility=False)
    assert arr3.shape == (3,)
    assert np.allclose(arr3, [0.5, 0.25, 0.1])

    arr4 = pt.to_array(include_visibility=True)
    assert arr4.shape == (4,)
    assert np.allclose(arr4, [0.5, 0.25, 0.1, 0.95])

    pixel_pt = pt.to_pixel(width=640, height=480)
    assert pixel_pt.x == pytest.approx(320.0)
    assert pixel_pt.y == pytest.approx(120.0)
    assert pixel_pt.z == pytest.approx(64.0)

    nan_pt = Point3D.nan_point()
    assert nan_pt.is_nan()


def test_hand_landmark_set_valid():
    pts = [Point3D(x=0.1 * i, y=0.05 * i, z=0.01 * i) for i in range(21)]
    hand = HandLandmarkSet(side="Right", landmarks=pts, confidence=0.88, is_detected=True)
    assert hand.is_detected
    assert hand.side == "Right"

    coords63 = hand.to_numpy(coords_only=True)
    assert coords63.shape == (63,)
    assert np.all(np.isfinite(coords63))

    vec64 = hand.to_numpy(coords_only=False)
    assert vec64.shape == (64,)
    assert vec64[-1] == pytest.approx(0.88)

    pixel_coords = hand.to_pixel_coords(100, 100)
    assert pixel_coords.shape == (63,)
    assert pixel_coords[0] == pytest.approx(0.0)


def test_hand_landmark_set_missing():
    missing_hand = HandLandmarkSet.missing("Left")
    assert not missing_hand.is_detected
    assert missing_hand.confidence == 0.0
    arr63 = missing_hand.to_numpy(coords_only=True)
    assert arr63.shape == (63,)
    assert np.all(np.isnan(arr63))

    arr64 = missing_hand.to_numpy(coords_only=False)
    assert arr64.shape == (64,)
    assert np.all(np.isnan(arr64[:63]))
    assert arr64[63] == 0.0


def test_hand_landmark_set_invalid_count():
    with pytest.raises(ValueError, match="must contain 21 points"):
        HandLandmarkSet(side="Left", landmarks=[Point3D(x=0, y=0, z=0)] * 5)


def test_pose_landmark_set_valid():
    pts = [Point3D(x=0.01 * i, y=0.02 * i, z=0.03 * i, visibility=0.9) for i in range(33)]
    pose = PoseLandmarkSet(landmarks=pts, confidence=0.92, is_detected=True)
    assert pose.is_detected

    arr132 = pose.to_numpy(include_visibility=True)
    assert arr132.shape == (132,)
    assert np.all(np.isfinite(arr132))

    arr99 = pose.to_numpy(include_visibility=False)
    assert arr99.shape == (99,)
    assert np.all(np.isfinite(arr99))


def test_pose_landmark_set_missing():
    missing_pose = PoseLandmarkSet.missing()
    assert not missing_pose.is_detected
    arr132 = missing_pose.to_numpy(include_visibility=True)
    assert arr132.shape == (132,)
    # Coordinate values are NaN, visibilities are 0.0
    assert np.all(np.isnan(arr132[0::4]))
    assert np.all(arr132[3::4] == 0.0)


def test_video_metadata_duration_calculation():
    meta = VideoMetadata(
        path="test.mp4",
        fps=30.0,
        frame_count=90,
        width=1280,
        height=720,
    )
    assert meta.duration_s == pytest.approx(3.0)


def test_data_quality_report_reliable():
    report = DataQualityReport.compute(
        frames_total=100,
        frames_analysed=100,
        frames_with_hand=95,
        frames_with_pose=98,
    )
    assert report.reliable is True
    assert report.hand_detection_rate == 0.95
    assert report.pose_detection_rate == 0.98
    assert len(report.notes) == 0


def test_data_quality_report_unreliable():
    report = DataQualityReport.compute(
        frames_total=100,
        frames_analysed=100,
        frames_with_hand=40,
        frames_with_pose=95,
    )
    assert report.reliable is False
    assert report.hand_detection_rate == 0.40
    assert len(report.notes) > 0
    assert "Hand detected in only 40/100 frames" in report.notes[0]
