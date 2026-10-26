"""Unit tests for the VisionPipeline and ProcessedSequence end-to-end flow."""

from pathlib import Path
import numpy as np
import pytest

from vision.detectors.base import MockHandBackend, MockPoseBackend
from vision.schemas import DataQualityReport
from vision.sequence_builder import ProcessedSequence, VisionPipeline
from vision.video_reader import create_synthetic_video


def test_end_to_end_pipeline_success(tmp_path: Path):
    video_path = create_synthetic_video(tmp_path / "dance_clip.mp4", num_frames=12, fps=24.0)

    hand_backend = MockHandBackend(detect_left=True, detect_right=True, confidence=0.88)
    pose_backend = MockPoseBackend(detect_pose=True, confidence=0.95)

    with VisionPipeline(hand_backend=hand_backend, pose_backend=pose_backend) as pipeline:
        seq = pipeline.process_video(video_path)

    assert isinstance(seq, ProcessedSequence)
    assert seq.num_frames == 12

    # Feature matrix shape and dtype
    assert seq.features.shape == (12, 260)
    assert seq.features.dtype == np.float64
    assert np.all(np.isfinite(seq.features))

    # Strict timestamp monotonicity
    assert seq.timestamps_ms.shape == (12,)
    assert np.all(np.diff(seq.timestamps_ms) > 0)
    assert np.all(seq.timestamps_s == pytest.approx(seq.timestamps_ms / 1000.0))

    # Frame indices
    assert np.array_equal(seq.frame_indices, np.arange(12))

    # Detection and validity masks
    assert seq.detection_mask.shape == (12, 3)
    assert np.all(seq.detection_mask)  # all detected
    assert seq.validity_mask.shape == (12, 260)
    assert np.all(seq.validity_mask)

    # Data quality report
    assert isinstance(seq.quality_report, DataQualityReport)
    assert seq.quality_report.reliable is True
    assert seq.quality_report.hand_detection_rate == 1.0
    assert seq.quality_report.pose_detection_rate == 1.0
    assert seq.quality_report.frames_total >= 11
    assert seq.quality_report.frames_analysed == 12

    # Sub-matrix accessors
    pose_mat = seq.get_pose_matrix()
    assert pose_mat.shape == (12, 132)

    left_coords = seq.get_left_hand_matrix(include_confidence=False)
    assert left_coords.shape == (12, 63)
    left_full = seq.get_left_hand_matrix(include_confidence=True)
    assert left_full.shape == (12, 64)
    assert np.allclose(left_full[:, -1], 0.88)

    right_coords = seq.get_right_hand_matrix(include_confidence=False)
    assert right_coords.shape == (12, 63)
    right_full = seq.get_right_hand_matrix(include_confidence=True)
    assert right_full.shape == (12, 64)
    assert np.allclose(right_full[:, -1], 0.88)

    # Member 4 MLP sequence export
    mlp_right = seq.extract_mlp_hand_sequence(side="Right")
    assert len(mlp_right) == 12
    for item in mlp_right:
        assert item is not None
        assert item.shape == (63,)
        assert np.all(np.isfinite(item))


def test_pipeline_stride_and_max_frames(tmp_path: Path):
    video_path = create_synthetic_video(tmp_path / "long_clip.mp4", num_frames=30, fps=30.0)

    hand_backend = MockHandBackend()
    pose_backend = MockPoseBackend()

    pipeline = VisionPipeline(hand_backend=hand_backend, pose_backend=pose_backend)
    seq = pipeline.process_video(video_path, stride=2, max_frames=8)

    assert seq.num_frames == 8
    assert seq.features.shape == (8, 260)
    assert np.array_equal(seq.frame_indices, np.arange(8))
    # Stride of 2 means timestamp steps are ~66.6ms apart
    diffs = np.diff(seq.timestamps_ms)
    assert np.all(diffs >= 60)


def test_pipeline_missing_hands_quality_report(tmp_path: Path):
    video_path = create_synthetic_video(tmp_path / "no_hands.mp4", num_frames=10, fps=20.0)

    # No hands detected, pose is detected
    hand_backend = MockHandBackend(detect_left=False, detect_right=False)
    pose_backend = MockPoseBackend(detect_pose=True)

    pipeline = VisionPipeline(hand_backend=hand_backend, pose_backend=pose_backend)
    seq = pipeline.process_video(video_path)

    # Frames are retained because pose was present
    assert seq.num_frames == 10
    assert seq.detection_mask.shape == (10, 3)
    # Pose detected, left missing, right missing
    assert np.all(seq.detection_mask[:, 0])
    assert not np.any(seq.detection_mask[:, 1])
    assert not np.any(seq.detection_mask[:, 2])

    # Pose features are finite
    assert np.all(np.isfinite(seq.get_pose_matrix()))

    # Hand coordinates are explicit NaNs
    assert np.all(np.isnan(seq.get_left_hand_matrix(include_confidence=False)))
    assert np.all(np.isnan(seq.get_right_hand_matrix(include_confidence=False)))

    # Quality report marks tracking as unreliable
    assert seq.quality_report.reliable is False
    assert seq.quality_report.hand_detection_rate == 0.0
    assert seq.quality_report.pose_detection_rate == 1.0
    assert len(seq.quality_report.notes) > 0
    assert "Hand detected in only 0/10 frames" in seq.quality_report.notes[0]

    # Member 4 MLP sequence returns None for each frame
    mlp_right = seq.extract_mlp_hand_sequence(side="Right")
    assert len(mlp_right) == 10
    assert all(x is None for x in mlp_right)


def test_pipeline_missing_video_raises():
    pipeline = VisionPipeline(hand_backend=MockHandBackend(), pose_backend=MockPoseBackend())
    with pytest.raises(FileNotFoundError):
        pipeline.process_video("does_not_exist.mp4")


def test_empty_sequence_helpers():
    meta = VideoReader("dummy", stride=1).metadata if False else None
    # Test accessor behavior on empty sequence
    from vision.schemas import VideoMetadata
    meta = VideoMetadata(path="empty.mp4", fps=30.0, frame_count=0, duration_s=0.0, width=100, height=100)
    empty_seq = ProcessedSequence(
        metadata=meta,
        frames=[],
        features=np.empty((0, 260), dtype=np.float64),
        timestamps_ms=np.empty((0,), dtype=np.int64),
        timestamps_s=np.empty((0,), dtype=np.float64),
        frame_indices=np.empty((0,), dtype=np.int64),
        detection_mask=np.empty((0, 3), dtype=bool),
        validity_mask=np.empty((0, 260), dtype=bool),
        quality_report=DataQualityReport(reliable=False),
    )
    assert empty_seq.num_frames == 0
    assert empty_seq.get_pose_matrix().shape == (0, 132)
    assert empty_seq.get_left_hand_matrix().shape == (0, 63)
    assert empty_seq.get_right_hand_matrix().shape == (0, 63)
    assert empty_seq.extract_mlp_hand_sequence() == []
