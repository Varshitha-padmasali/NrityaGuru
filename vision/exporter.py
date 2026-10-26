"""Export and safe loading utilities for NrityaGuru feature sequences and metadata.

Serializes ProcessedSequence into:
  1. Compressed NPZ archive containing features, timestamps, indices, and masks.
  2. Companion JSON file containing video metadata, quality report, and layout specs.

Enforces:
  - allow_pickle=False during loading to prevent arbitrary code execution vulnerabilities.
  - Strict shape, type, and schema validation.
  - Exact preservation of NaNs, masks, and timestamps.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Tuple
import numpy as np

from vision.feature_extractor import ExtractedFrameFeatures
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

EXPORT_FORMAT_VERSION: str = "1.0"
SCHEMA_VERSION: str = "260-v1"

REQUIRED_NPZ_KEYS = {
    "features",
    "timestamps_ms",
    "timestamps_s",
    "frame_indices",
    "detection_mask",
    "validity_mask",
}


def export_sequence(
    sequence: ProcessedSequence,
    output_path: str | Path,
    json_path: str | Path | None = None,
) -> Tuple[Path, Path]:
    """Export a ProcessedSequence to compressed NPZ and companion JSON files.

    Args:
        sequence: The ProcessedSequence to serialize.
        output_path: Target path for the .npz file (or base name without extension).
        json_path: Optional explicit path for the companion .json file. Defaults to
            output_path with .json extension.

    Returns:
        Tuple of (npz_file_path, json_file_path).
    """
    out_npz = Path(output_path).resolve()
    if out_npz.suffix.lower() != ".npz":
        out_npz = out_npz.with_suffix(".npz")

    out_json = Path(json_path).resolve() if json_path is not None else out_npz.with_suffix(".json")

    out_npz.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    # 1. Save compressed NPZ array bundle
    np.savez_compressed(
        out_npz,
        features=sequence.features.astype(np.float64),
        timestamps_ms=sequence.timestamps_ms.astype(np.int64),
        timestamps_s=sequence.timestamps_s.astype(np.float64),
        frame_indices=sequence.frame_indices.astype(np.int64),
        detection_mask=sequence.detection_mask.astype(bool),
        validity_mask=sequence.validity_mask.astype(bool),
    )

    # 2. Build companion JSON metadata
    quality_dict = {
        "hand_detection_rate": sequence.quality_report.hand_detection_rate,
        "pose_detection_rate": sequence.quality_report.pose_detection_rate,
        "frames_total": sequence.quality_report.frames_total,
        "frames_analysed": sequence.quality_report.frames_analysed,
        "reliable": sequence.quality_report.reliable,
        "notes": sequence.quality_report.notes,
    }

    metadata_payload = {
        "export_format_version": EXPORT_FORMAT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "feature_dimension": FEATURE_DIM,
        "num_frames": sequence.num_frames,
        "feature_layout": {
            "pose_slice": [POSE_SLICE.start, POSE_SLICE.stop],
            "left_hand_slice": [LEFT_HAND_SLICE.start, LEFT_HAND_SLICE.stop],
            "right_hand_slice": [RIGHT_HAND_SLICE.start, RIGHT_HAND_SLICE.stop],
            "left_hand_coords_slice": [LEFT_HAND_COORDS_SLICE.start, LEFT_HAND_COORDS_SLICE.stop],
            "right_hand_coords_slice": [RIGHT_HAND_COORDS_SLICE.start, RIGHT_HAND_COORDS_SLICE.stop],
            "left_hand_confidence_idx": LEFT_HAND_SLICE.stop - 1,
            "right_hand_confidence_idx": RIGHT_HAND_SLICE.stop - 1,
        },
        "coordinate_conventions": {
            "pose": "Normalized relative to shoulder midpoint (origin) and shoulder width (scale). Component 4 is visibility [0, 1].",
            "hands": "Normalized relative to wrist (origin) and wrist-to-middle-MCP distance (palm scale). Final component is confidence.",
            "missing_values": "Explicit IEEE 754 NaN for missing spatial coordinates; 0.0 for confidence and visibility.",
        },
        "video_metadata": sequence.metadata.model_dump(mode="json"),
        "landmark_quality": quality_dict,
    }

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(metadata_payload, f, indent=2)

    return out_npz, out_json


def load_sequence(
    npz_path: str | Path,
    json_path: str | Path | None = None,
) -> ProcessedSequence:
    """Safely load and reconstruct a ProcessedSequence from NPZ and JSON files.

    Enforces allow_pickle=False for secure loading, and validates array dimensions
    and metadata integrity.

    Args:
        npz_path: Path to the .npz archive.
        json_path: Optional explicit path to the .json metadata file. Defaults to
            npz_path with .json extension.

    Returns:
        Reconstructed ProcessedSequence instance.
    """
    in_npz = Path(npz_path).resolve()
    if not in_npz.is_file():
        raise FileNotFoundError(f"NPZ sequence file not found: {in_npz}")

    in_json = Path(json_path).resolve() if json_path is not None else in_npz.with_suffix(".json")
    if not in_json.is_file():
        raise FileNotFoundError(f"Companion JSON metadata file not found: {in_json}")

    # 1. Load JSON metadata
    with open(in_json, "r", encoding="utf-8") as f:
        meta_data = json.load(f)

    if not isinstance(meta_data, dict):
        raise ValueError(f"Invalid JSON metadata structure in {in_json}")

    # Check schema compatibility
    if meta_data.get("feature_dimension") != FEATURE_DIM:
        raise ValueError(
            f"Incompatible feature dimension: file has {meta_data.get('feature_dimension')}, expected {FEATURE_DIM}"
        )

    video_meta = VideoMetadata.model_validate(meta_data["video_metadata"])
    quality_report = DataQualityReport.model_validate(meta_data["landmark_quality"])

    # 2. Load NPZ archive with allow_pickle=False for safety
    with np.load(str(in_npz), allow_pickle=False) as npz_data:
        missing_keys = REQUIRED_NPZ_KEYS - set(npz_data.files)
        if missing_keys:
            raise KeyError(f"NPZ file {in_npz} is missing required arrays: {missing_keys}")

        features = np.asarray(npz_data["features"], dtype=np.float64)
        ts_ms = np.asarray(npz_data["timestamps_ms"], dtype=np.int64)
        ts_s = np.asarray(npz_data["timestamps_s"], dtype=np.float64)
        indices = np.asarray(npz_data["frame_indices"], dtype=np.int64)
        det_mask = np.asarray(npz_data["detection_mask"], dtype=bool)
        val_mask = np.asarray(npz_data["validity_mask"], dtype=bool)

    # 3. Validate matrix shapes
    if features.ndim != 2 or features.shape[1] != FEATURE_DIM:
        raise ValueError(f"features array must have shape (T, {FEATURE_DIM}), got {features.shape}")

    t = features.shape[0]
    if ts_ms.shape != (t,):
        raise ValueError(f"timestamps_ms shape {ts_ms.shape} does not match frame count {t}")
    if ts_s.shape != (t,):
        raise ValueError(f"timestamps_s shape {ts_s.shape} does not match frame count {t}")
    if indices.shape != (t,):
        raise ValueError(f"frame_indices shape {indices.shape} does not match frame count {t}")
    if det_mask.shape != (t, 3):
        raise ValueError(f"detection_mask shape {det_mask.shape} does not match (T, 3)")
    if val_mask.shape != (t, FEATURE_DIM):
        raise ValueError(f"validity_mask shape {val_mask.shape} does not match (T, {FEATURE_DIM})")

    # 4. Reconstruct ExtractedFrameFeatures list
    frames: list[ExtractedFrameFeatures] = []
    for i in range(t):
        frame_feat = ExtractedFrameFeatures(
            frame_idx=int(indices[i]),
            timestamp_ms=int(ts_ms[i]),
            timestamp_s=float(ts_s[i]),
            feature_vector=features[i],
            pose_detected=bool(det_mask[i, 0]),
            left_hand_detected=bool(det_mask[i, 1]),
            right_hand_detected=bool(det_mask[i, 2]),
            schema_version=meta_data.get("schema_version", SCHEMA_VERSION),
        )
        frames.append(frame_feat)

    return ProcessedSequence(
        metadata=video_meta,
        frames=frames,
        features=features,
        timestamps_ms=ts_ms,
        timestamps_s=ts_s,
        frame_indices=indices,
        detection_mask=det_mask,
        validity_mask=val_mask,
        quality_report=quality_report,
    )
