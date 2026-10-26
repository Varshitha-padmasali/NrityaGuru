"""Unit tests for hand and pose detectors, backends, and error handling."""

from pathlib import Path
import numpy as np
import pytest

from vision.detectors.base import (
    HandDetectionResult,
    MockHandBackend,
    MockPoseBackend,
    PoseDetectionResult,
)
from vision.hand_detector import HandDetector
from vision.pose_detector import PoseDetector
from vision.schemas import FrameData
from vision.video_reader import VideoReader, create_synthetic_video


def test_hand_detector_both_hands_detected():
    backend = MockHandBackend(detect_left=True, detect_right=True, confidence=0.88)
    detector = HandDetector(backend=backend)

    dummy_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    res = detector.detect(dummy_frame, timestamp_ms=150)

    assert isinstance(res, HandDetectionResult)
    assert res.timestamp_ms == 150
    assert res.both_detected
    assert res.any_detected

    assert res.left_hand.is_detected
    assert res.left_hand.side == "Left"
    assert len(res.left_hand.landmarks) == 21
    assert res.left_hand.confidence == pytest.approx(0.88)

    assert res.right_hand.is_detected
    assert res.right_hand.side == "Right"
    assert len(res.right_hand.landmarks) == 21
    assert res.right_hand.confidence == pytest.approx(0.88)


def test_hand_detector_single_right_hand():
    backend = MockHandBackend(detect_left=False, detect_right=True, confidence=0.75)
    detector = HandDetector(backend=backend)

    frame_data = FrameData(
        frame_idx=2,
        timestamp_ms=200,
        timestamp_s=0.2,
        image=np.zeros((100, 100, 3), dtype=np.uint8),
        width=100,
        height=100,
    )
    res = detector.detect(frame_data)

    assert res.timestamp_ms == 200
    assert not res.both_detected
    assert res.any_detected

    # Left hand is missing: explicit NaNs, not zero
    assert not res.left_hand.is_detected
    assert np.all(np.isnan(res.left_hand.to_numpy(coords_only=True)))

    # Right hand is detected
    assert res.right_hand.is_detected
    assert len(res.right_hand.landmarks) == 21
    assert res.right_hand.confidence == pytest.approx(0.75)


def test_hand_detector_neither_hand_detected():
    backend = MockHandBackend(detect_left=False, detect_right=False)
    detector = HandDetector(backend=backend)

    res = detector.detect(np.zeros((50, 50, 3), dtype=np.uint8), timestamp_ms=500)
    assert not res.any_detected
    assert not res.both_detected
    assert not res.left_hand.is_detected
    assert not res.right_hand.is_detected
    assert np.all(np.isnan(res.left_hand.to_numpy(coords_only=True)))
    assert np.all(np.isnan(res.right_hand.to_numpy(coords_only=True)))


def test_hand_detector_missing_model_raises_file_not_found():
    with pytest.raises(FileNotFoundError, match="Hand Landmarker model file not found"):
        HandDetector(model_path="nonexistent_hand_model.task")


def test_hand_detector_raw_array_without_timestamp_raises():
    detector = HandDetector(backend=MockHandBackend())
    with pytest.raises(ValueError, match="timestamp_ms must be provided"):
        detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))


def test_hand_detector_invalid_type_raises():
    detector = HandDetector(backend=MockHandBackend())
    with pytest.raises(TypeError, match="Expected FrameData or np.ndarray"):
        detector.detect("not_an_image")  # type: ignore


def test_hand_detector_context_manager():
    backend = MockHandBackend()
    with HandDetector(backend=backend) as detector:
        res = detector.detect(np.zeros((20, 20, 3), dtype=np.uint8), timestamp_ms=0)
        assert res.timestamp_ms == 0
    assert len(backend.call_history) == 1


def test_pose_detector_detected():
    backend = MockPoseBackend(detect_pose=True, confidence=0.94)
    detector = PoseDetector(backend=backend)

    frame_data = FrameData(
        frame_idx=5,
        timestamp_ms=333,
        timestamp_s=0.333,
        image=np.zeros((200, 200, 3), dtype=np.uint8),
        width=200,
        height=200,
    )
    res = detector.detect(frame_data)

    assert isinstance(res, PoseDetectionResult)
    assert res.timestamp_ms == 333
    assert res.is_detected
    assert res.pose.is_detected
    assert len(res.pose.landmarks) == 33
    assert res.pose.confidence == pytest.approx(0.94)

    arr132 = res.pose.to_numpy(include_visibility=True)
    assert arr132.shape == (132,)
    assert np.all(np.isfinite(arr132))


def test_pose_detector_missing():
    backend = MockPoseBackend(detect_pose=False)
    detector = PoseDetector(backend=backend)

    res = detector.detect(np.zeros((100, 100, 3), dtype=np.uint8), timestamp_ms=667)
    assert not res.is_detected
    assert not res.pose.is_detected
    arr132 = res.pose.to_numpy(include_visibility=True)
    assert np.all(np.isnan(arr132[0::4]))  # coordinates are NaN
    assert np.all(arr132[3::4] == 0.0)      # visibilities are 0.0


def test_pose_detector_missing_model_raises_file_not_found():
    with pytest.raises(FileNotFoundError, match="Pose Landmarker model file not found"):
        PoseDetector(model_path="nonexistent_pose_model.task")


def test_pose_detector_raw_array_without_timestamp_raises():
    detector = PoseDetector(backend=MockPoseBackend())
    with pytest.raises(ValueError, match="timestamp_ms must be provided"):
        detector.detect(np.zeros((50, 50, 3), dtype=np.uint8))


def test_detectors_video_stream_pipeline(tmp_path: Path):
    video_path = create_synthetic_video(tmp_path / "stream_test.mp4", num_frames=10, fps=20.0)

    hand_backend = MockHandBackend(detect_left=True, detect_right=True)
    pose_backend = MockPoseBackend(detect_pose=True)

    hand_detector = HandDetector(backend=hand_backend)
    pose_detector = PoseDetector(backend=pose_backend)

    with VideoReader(video_path) as reader:
        frames_seen = 0
        last_ms = -1
        for frame in reader:
            hand_res = hand_detector.detect(frame)
            pose_res = pose_detector.detect(frame)

            assert hand_res.timestamp_ms == frame.timestamp_ms
            assert pose_res.timestamp_ms == frame.timestamp_ms
            assert hand_res.timestamp_ms > last_ms
            last_ms = hand_res.timestamp_ms

            assert hand_res.both_detected
            assert pose_res.is_detected
            frames_seen += 1

        assert frames_seen == 10
