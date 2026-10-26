"""Unit tests for NPZ and JSON sequence export, safe loading, and round-trip fidelity."""

import json
from pathlib import Path
import numpy as np
import pytest

from vision.detectors.base import MockHandBackend, MockPoseBackend
from vision.exporter import (
    EXPORT_FORMAT_VERSION,
    SCHEMA_VERSION,
    export_sequence,
    load_sequence,
)
from vision.sequence_builder import ProcessedSequence, VisionPipeline
from vision.video_reader import create_synthetic_video


def _create_sample_sequence(tmp_path: Path, num_frames: int = 10, detect_hands: bool = True) -> ProcessedSequence:
    video_path = create_synthetic_video(tmp_path / "sample.mp4", num_frames=num_frames, fps=25.0)
    hand_backend = MockHandBackend(detect_left=detect_hands, detect_right=detect_hands, confidence=0.85)
    pose_backend = MockPoseBackend(detect_pose=True, confidence=0.92)

    with VisionPipeline(hand_backend=hand_backend, pose_backend=pose_backend) as pipeline:
        return pipeline.process_video(video_path)


def test_export_and_roundtrip_loading(tmp_path: Path):
    seq = _create_sample_sequence(tmp_path, num_frames=8, detect_hands=True)

    out_npz, out_json = export_sequence(seq, tmp_path / "run1" / "dance_seq.npz")
    assert out_npz.is_file()
    assert out_json.is_file()

    # Inspect JSON structure
    with open(out_json, "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["export_format_version"] == EXPORT_FORMAT_VERSION
    assert meta["schema_version"] == SCHEMA_VERSION
    assert meta["feature_dimension"] == 260
    assert meta["num_frames"] == 8
    assert "feature_layout" in meta
    assert "video_metadata" in meta
    assert "landmark_quality" in meta
    assert meta["landmark_quality"]["reliable"] is True
    assert meta["landmark_quality"]["hand_detection_rate"] == 1.0

    # Test Member 2 LandmarkQuality schema compatibility directly
    import sys
    backend_path = str(Path(__file__).resolve().parents[2] / "backend")
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    from app.schemas.evaluation import LandmarkQuality
    member2_quality = LandmarkQuality.model_validate(meta["landmark_quality"])
    assert member2_quality.reliable is True
    assert member2_quality.hand_detection_rate == 1.0

    # Load back with allow_pickle=False
    loaded = load_sequence(out_npz)

    assert isinstance(loaded, ProcessedSequence)
    assert loaded.num_frames == 8

    # Array and type equivalence
    assert loaded.features.dtype == np.float64
    assert np.allclose(loaded.features, seq.features, equal_nan=True)

    assert loaded.timestamps_ms.dtype == np.int64
    assert np.array_equal(loaded.timestamps_ms, seq.timestamps_ms)

    assert loaded.timestamps_s.dtype == np.float64
    assert np.allclose(loaded.timestamps_s, seq.timestamps_s)

    assert loaded.frame_indices.dtype == np.int64
    assert np.array_equal(loaded.frame_indices, seq.frame_indices)

    assert loaded.detection_mask.dtype == bool
    assert np.array_equal(loaded.detection_mask, seq.detection_mask)

    assert loaded.validity_mask.dtype == bool
    assert np.array_equal(loaded.validity_mask, seq.validity_mask)

    # Frame properties
    for orig_f, load_f in zip(seq.frames, loaded.frames):
        assert orig_f.frame_idx == load_f.frame_idx
        assert orig_f.timestamp_ms == load_f.timestamp_ms
        assert orig_f.pose_detected == load_f.pose_detected
        assert orig_f.left_hand_detected == load_f.left_hand_detected
        assert orig_f.right_hand_detected == load_f.right_hand_detected


def test_nan_preservation_and_masks_roundtrip(tmp_path: Path):
    # Sequence with missing hands
    seq = _create_sample_sequence(tmp_path, num_frames=6, detect_hands=False)

    npz_path, json_path = export_sequence(seq, tmp_path / "missing_hands.npz")
    loaded = load_sequence(npz_path, json_path)

    # Missing hand coordinates are preserved as NaN
    assert np.all(np.isnan(loaded.get_left_hand_matrix(include_confidence=False)))
    assert np.all(np.isnan(loaded.get_right_hand_matrix(include_confidence=False)))

    # Pose coordinates remain finite
    assert np.all(np.isfinite(loaded.get_pose_matrix()))

    # Validity mask matches
    assert np.array_equal(loaded.validity_mask, seq.validity_mask)
    assert np.array_equal(loaded.detection_mask, seq.detection_mask)
    assert loaded.quality_report.reliable is False


def test_load_missing_files_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="NPZ sequence file not found"):
        load_sequence(tmp_path / "non_existent.npz")

    # NPZ exists, but JSON is missing
    dummy_npz = tmp_path / "dummy.npz"
    np.savez(dummy_npz, a=np.zeros(5))
    with pytest.raises(FileNotFoundError, match="Companion JSON metadata file not found"):
        load_sequence(dummy_npz)


def test_load_corrupted_npz_missing_keys(tmp_path: Path):
    npz_path = tmp_path / "corrupt.npz"
    json_path = tmp_path / "corrupt.json"

    # Save incomplete NPZ
    np.savez(npz_path, features=np.zeros((5, 260)))
    with open(json_path, "w") as f:
        json.dump({
            "feature_dimension": 260,
            "video_metadata": {"path": "x", "fps": 30.0, "frame_count": 5, "duration_s": 0.1, "width": 100, "height": 100},
            "landmark_quality": {"reliable": True, "frames_total": 5, "frames_analysed": 5},
        }, f)

    with pytest.raises(KeyError, match="missing required arrays"):
        load_sequence(npz_path, json_path)


def test_load_mismatched_feature_dimensions(tmp_path: Path):
    npz_path = tmp_path / "bad_dim.npz"
    json_path = tmp_path / "bad_dim.json"

    # Save NPZ with 100 features instead of 260
    np.savez(
        npz_path,
        features=np.zeros((4, 100)),
        timestamps_ms=np.arange(4),
        timestamps_s=np.arange(4) / 30.0,
        frame_indices=np.arange(4),
        detection_mask=np.zeros((4, 3), dtype=bool),
        validity_mask=np.zeros((4, 100), dtype=bool),
    )
    with open(json_path, "w") as f:
        json.dump({
            "feature_dimension": 260,
            "video_metadata": {"path": "x", "fps": 30.0, "frame_count": 4, "duration_s": 0.1, "width": 100, "height": 100},
            "landmark_quality": {"reliable": True, "frames_total": 4, "frames_analysed": 4},
        }, f)

    with pytest.raises(ValueError, match="features array must have shape"):
        load_sequence(npz_path, json_path)


def test_allow_pickle_is_enforced(tmp_path: Path):
    # Attempting to load an object array with allow_pickle=False should fail
    bad_npz = tmp_path / "pickle.npz"
    bad_json = tmp_path / "pickle.json"

    # Save object array requiring pickle
    obj_array = np.array([{"key": "value"}], dtype=object)
    np.savez(
        bad_npz,
        features=np.zeros((1, 260)),
        timestamps_ms=np.array([0]),
        timestamps_s=np.array([0.0]),
        frame_indices=np.array([0]),
        detection_mask=np.zeros((1, 3), dtype=bool),
        validity_mask=np.zeros((1, 260), dtype=bool),
        extra_obj=obj_array,
    )
    with open(bad_json, "w") as f:
        json.dump({
            "feature_dimension": 260,
            "video_metadata": {"path": "x", "fps": 30.0, "frame_count": 1, "duration_s": 0.1, "width": 100, "height": 100},
            "landmark_quality": {"reliable": True, "frames_total": 1, "frames_analysed": 1},
        }, f)

    # Standard loading loads successfully without loading extra_obj as pickle
    loaded = load_sequence(bad_npz, bad_json)
    assert loaded.num_frames == 1
