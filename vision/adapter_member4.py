"""Integration Adapter for Member 4's MLP and DTW Evaluation Module.

Provides bidirectional translation and extraction utilities between Member 3's
canonical 260-dimensional vision sequence format and Member 4's single-hand
63-coordinate pixel-space MLP input requirement and multi-frame DTW evaluator.

Adheres strictly to Member 4's contract:
  - Missing hands are represented as None (never filled with zeros or fake coordinates).
  - Valid coordinates are shape (63,) float64 arrays (21 landmarks x 3: x, y, z).
  - Explicit validation prevents corrupted, infinite, or malformed data from masquerading
    as legitimate detections.
"""

from __future__ import annotations

from typing import Any, Literal, Sequence, Tuple, Union
import numpy as np

from vision.schemas import (
    FEATURE_DIM,
    LEFT_HAND_COORDS_SLICE,
    LEFT_HAND_SLICE,
    POSE_SLICE,
    RIGHT_HAND_COORDS_SLICE,
    RIGHT_HAND_SLICE,
    VideoMetadata,
)
from vision.sequence_builder import ProcessedSequence

HandSide = Literal["Right", "Left", "auto"]


class AdapterInputError(ValueError):
    """Raised when input to the Member 4 adapter is malformed or invalid."""


def extract_hand_for_mlp(
    feature_vector: Union[np.ndarray, Sequence[float]],
    side: HandSide = "Right",
    width: int | None = None,
    height: int | None = None,
) -> np.ndarray | None:
    """Extract a 63-coordinate single-hand landmark vector from a 260-dim feature vector.

    Conforms to Member 4's `mudra_mlp.features.hand_features` input specification:
      - Shape: (63,) representing 21 landmarks x [x, y, z].
      - Missing hand: returns None (Member 4's `build_result._analyse` expects None).
      - Never substitutes zeros or synthetic landmarks for missing detections.

    Args:
        feature_vector: 260-dimensional frame feature vector.
        side: "Right" (default), "Left", or "auto" (selects the detected hand with
            highest confidence).
        width: Optional source frame width. If provided alongside height, scales
            normalized coordinates to pixel units (x*width, y*height, z*width).
        height: Optional source frame height.

    Returns:
        np.ndarray of shape (63,) with dtype float64, or None if the requested hand
        was not detected or contains NaNs.

    Raises:
        AdapterInputError: If feature_vector is not a 260-dimensional numeric vector,
            or if width/height are invalid.
    """
    if (width is not None and width <= 0) or (height is not None and height <= 0):
        raise AdapterInputError(f"width and height must be positive integers, got ({width}, {height})")
    if (width is None) != (height is None):
        raise AdapterInputError("Both width and height must be provided together, or both None.")

    try:
        arr = np.asarray(feature_vector, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise AdapterInputError("feature_vector must be numeric") from exc

    if arr.shape != (FEATURE_DIM,):
        raise AdapterInputError(f"Expected 260-dimensional feature vector, got shape {arr.shape}")

    # Inspect Left Hand [132:196] and Right Hand [196:260]
    left_coords = arr[LEFT_HAND_COORDS_SLICE]
    left_conf = float(arr[LEFT_HAND_SLICE.stop - 1])
    left_valid = bool(left_conf > 0.0 and np.all(np.isfinite(left_coords)))

    right_coords = arr[RIGHT_HAND_COORDS_SLICE]
    right_conf = float(arr[RIGHT_HAND_SLICE.stop - 1])
    right_valid = bool(right_conf > 0.0 and np.all(np.isfinite(right_coords)))

    # Determine which hand to extract
    chosen_coords: np.ndarray | None = None
    if side == "auto":
        if right_valid and left_valid:
            chosen_coords = right_coords if right_conf >= left_conf else left_coords
        elif right_valid:
            chosen_coords = right_coords
        elif left_valid:
            chosen_coords = left_coords
        else:
            return None
    elif side == "Right":
        if not right_valid:
            return None
        chosen_coords = right_coords
    elif side == "Left":
        if not left_valid:
            return None
        chosen_coords = left_coords
    else:
        raise AdapterInputError(f"Invalid side '{side}'; must be 'Right', 'Left', or 'auto'")

    out = chosen_coords.copy()
    if width is not None and height is not None:
        # Scale to pixel units: x*width, y*height, z*width (Member 4 data_prep convention)
        out[0::3] *= width
        out[1::3] *= height
        out[2::3] *= width

    return out


def sequence_to_member4_frames(
    sequence: Union[ProcessedSequence, np.ndarray],
    side: HandSide = "Right",
    width: int | None = None,
    height: int | None = None,
) -> list[np.ndarray | None]:
    """Convert an entire feature sequence to Member 4's expected learner_frames format.

    Directly produces the `learner_frames` list for:
    `evaluation_module.mudra_eval.build_result.build_evaluation_result(learner_frames=...)`

    Args:
        sequence: Either a `ProcessedSequence` or a 2D NumPy array of shape (T, 260).
        side: Hand selection strategy ("Right", "Left", or "auto").
        width: Optional video width. If sequence is a ProcessedSequence and width is None,
            reads width from sequence.metadata.width.
        height: Optional video height. If sequence is a ProcessedSequence and height is None,
            reads height from sequence.metadata.height.

    Returns:
        List of length T where each element is either:
          - np.ndarray of shape (63,) in pixel units (or normalized units if dimensions omitted).
          - None if no hand was detected in that frame.
    """
    if isinstance(sequence, ProcessedSequence):
        features = sequence.features
        w = width if width is not None else sequence.metadata.width
        h = height if height is not None else sequence.metadata.height
    elif isinstance(sequence, np.ndarray):
        features = sequence
        w = width
        h = height
    else:
        try:
            features = np.asarray(sequence, dtype=np.float64)
            w = width
            h = height
        except Exception as exc:
            raise AdapterInputError("sequence must be a ProcessedSequence or numeric 2D array") from exc

    if features.ndim != 2 or features.shape[1] != FEATURE_DIM:
        raise AdapterInputError(f"Expected 2D feature matrix of shape (T, {FEATURE_DIM}), got {features.shape}")

    frames: list[np.ndarray | None] = []
    for i in range(features.shape[0]):
        vec = features[i]
        hand = extract_hand_for_mlp(vec, side=side, width=w, height=h)
        frames.append(hand)

    return frames


def sequence_to_dtw_matrix(
    sequence: Union[ProcessedSequence, np.ndarray],
    target: Literal["pose", "both_hands", "right_hand", "left_hand", "full"] = "full",
    drop_invalid: bool = True,
) -> Tuple[np.ndarray, np.ndarray]:
    """Extract a 2D clean matrix for Dynamic Time Warping (DTW) sequence alignment.

    Args:
        sequence: ProcessedSequence or 2D array of shape (T, 260).
        target: Feature subset to extract:
            - "full": All 260 features.
            - "pose": 132 pose features [0:132].
            - "both_hands": 128 hand features [132:260].
            - "right_hand": 64 right hand features [196:260].
            - "left_hand": 64 left hand features [132:196].
        drop_invalid: If True, drops frames containing any NaN values in the selected
            slice (required by Member 4's DTW which forbids NaNs).

    Returns:
        Tuple of (matrix, valid_frame_indices):
            - matrix: 2D np.ndarray of shape (N, D) where all values are finite float64.
            - valid_frame_indices: 1D np.ndarray of original frame indices retained.
    """
    if isinstance(sequence, ProcessedSequence):
        features = sequence.features
        indices = sequence.frame_indices
    else:
        features = np.asarray(sequence, dtype=np.float64)
        indices = np.arange(features.shape[0], dtype=np.int64)

    if features.ndim != 2 or features.shape[1] != FEATURE_DIM:
        raise AdapterInputError(f"Expected shape (T, {FEATURE_DIM}), got {features.shape}")

    if target == "full":
        sub_matrix = features
    elif target == "pose":
        sub_matrix = features[:, POSE_SLICE]
    elif target == "both_hands":
        sub_matrix = features[:, LEFT_HAND_SLICE.start : RIGHT_HAND_SLICE.stop]
    elif target == "right_hand":
        sub_matrix = features[:, RIGHT_HAND_SLICE]
    elif target == "left_hand":
        sub_matrix = features[:, LEFT_HAND_SLICE]
    else:
        raise AdapterInputError(f"Unknown target '{target}'")

    if drop_invalid:
        valid_rows = np.all(np.isfinite(sub_matrix), axis=1)
        return sub_matrix[valid_rows], indices[valid_rows]

    return sub_matrix, indices


def check_sequence_readiness_for_member4(
    sequence: Union[ProcessedSequence, list[np.ndarray | None]],
    min_detection_rate: float = 0.80,
    min_frames: int = 2,
) -> dict[str, Any]:
    """Check whether a sequence satisfies Member 4's evaluation prerequisites.

    Member 4's `build_result.py` defines:
      - Reliable tracking requires >= 80% detection rate.
      - DTW requires at least 2 valid frames in both reference and learner.

    Args:
        sequence: Either a ProcessedSequence or a list of adapted 63-dim hand vectors/None.
        min_detection_rate: Threshold for marking tracking reliable (default: 0.80).
        min_frames: Minimum valid frames required to compute DTW (default: 2).

    Returns:
        Dict with readiness diagnostics:
          - "can_evaluate": bool
          - "hand_detection_rate": float
          - "valid_frames": int
          - "total_frames": int
          - "can_run_dtw": bool
          - "warnings": list[str]
    """
    warnings: list[str] = []

    if isinstance(sequence, ProcessedSequence):
        frames = sequence_to_member4_frames(sequence, side="auto")
    elif isinstance(sequence, list):
        frames = sequence
    else:
        raise AdapterInputError("sequence must be ProcessedSequence or list of hand vectors")

    total = len(frames)
    valid = sum(1 for f in frames if f is not None)
    rate = (valid / total) if total > 0 else 0.0

    can_run_dtw = valid >= min_frames
    if not can_run_dtw:
        warnings.append(f"Only {valid} valid hand frame(s) detected; DTW requires at least {min_frames}.")

    reliable = rate >= min_detection_rate
    if not reliable:
        warnings.append(
            f"Hand detection rate ({rate:.1%}) is below Member 4's reliable threshold ({min_detection_rate:.0%})."
        )

    can_evaluate = valid > 0

    return {
        "can_evaluate": can_evaluate,
        "reliable": reliable,
        "hand_detection_rate": round(rate, 4),
        "valid_frames": valid,
        "total_frames": total,
        "can_run_dtw": can_run_dtw,
        "warnings": warnings,
    }
