"""Fixed-schema 260-dimensional feature extraction for NrityaGuru.

Combines body pose, left hand, and right hand into a canonical 260-dimensional
feature vector per frame:
  - Pose: [0:132] (33 landmarks x 4: x, y, z, visibility)
  - Left Hand: [132:196] (21 landmarks x 3: x, y, z + 1 confidence)
  - Right Hand: [196:260] (21 landmarks x 3: x, y, z + 1 confidence)

Includes the Member 4 pixel-coordinate conversion adapter for single-hand MLP classification.
Missing landmarks are represented explicitly with NaNs and boolean validity masks.
"""

from __future__ import annotations

from typing import Any, Literal
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

from vision.normalization import normalize_hand_landmarks, normalize_pose_landmarks
from vision.schemas import (
    FEATURE_DIM,
    HAND_FEAT_DIM,
    HandLandmarkSet,
    LEFT_HAND_COORDS_SLICE,
    LEFT_HAND_SLICE,
    N_HAND_LANDMARKS,
    N_POSE_LANDMARKS,
    POSE_FEAT_DIM,
    POSE_SLICE,
    PoseLandmarkSet,
    RIGHT_HAND_COORDS_SLICE,
    RIGHT_HAND_SLICE,
)

SCHEMA_VERSION: str = "260-v1"


def feature_names() -> list[str]:
    """Return explicit names for all 260 feature dimensions."""
    names: list[str] = []

    # Pose (132 values)
    for i in range(N_POSE_LANDMARKS):
        for component in ("x", "y", "z", "vis"):
            names.append(f"pose_lm{i}_{component}")

    # Left Hand (64 values: 63 coordinates + 1 confidence)
    for i in range(N_HAND_LANDMARKS):
        for component in ("x", "y", "z"):
            names.append(f"left_hand_lm{i}_{component}")
    names.append("left_hand_confidence")

    # Right Hand (64 values: 63 coordinates + 1 confidence)
    for i in range(N_HAND_LANDMARKS):
        for component in ("x", "y", "z"):
            names.append(f"right_hand_lm{i}_{component}")
    names.append("right_hand_confidence")

    return names


class ExtractedFrameFeatures(BaseModel):
    """Normalized fixed-schema feature vector and validity flags for one video frame."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    frame_idx: int = Field(ge=0)
    timestamp_ms: int = Field(ge=0)
    timestamp_s: float = Field(ge=0.0)
    feature_vector: np.ndarray  # Shape: (260,), dtype: float64
    pose_detected: bool
    left_hand_detected: bool
    right_hand_detected: bool
    schema_version: str = SCHEMA_VERSION

    @field_validator("feature_vector")
    @classmethod
    def validate_vector(cls, v: np.ndarray) -> np.ndarray:
        arr = np.asarray(v, dtype=np.float64)
        if arr.shape != (FEATURE_DIM,):
            raise ValueError(f"Feature vector must have shape ({FEATURE_DIM},), got {arr.shape}")
        return arr

    def get_pose_features(self) -> np.ndarray:
        """Return the 132-dim pose feature slice [0:132]."""
        return self.feature_vector[POSE_SLICE]

    def get_left_hand_features(self, include_confidence: bool = False) -> np.ndarray:
        """Return the left hand feature slice: (63,) coords or (64,) with confidence."""
        if include_confidence:
            return self.feature_vector[LEFT_HAND_SLICE]
        return self.feature_vector[LEFT_HAND_COORDS_SLICE]

    def get_right_hand_features(self, include_confidence: bool = False) -> np.ndarray:
        """Return the right hand feature slice: (63,) coords or (64,) with confidence."""
        if include_confidence:
            return self.feature_vector[RIGHT_HAND_SLICE]
        return self.feature_vector[RIGHT_HAND_COORDS_SLICE]

    def validity_mask(self) -> np.ndarray:
        """Return boolean mask of shape (260,), True where coordinate is finite (not NaN)."""
        return np.isfinite(self.feature_vector)


def extract_frame_features(
    frame_idx: int,
    timestamp_ms: int,
    pose: PoseLandmarkSet | None = None,
    left_hand: HandLandmarkSet | None = None,
    right_hand: HandLandmarkSet | None = None,
) -> ExtractedFrameFeatures:
    """Construct a canonical 260-dimensional feature vector for a video frame.

    Args:
        frame_idx: Sequential frame index.
        timestamp_ms: Frame timestamp in milliseconds.
        pose: Detected PoseLandmarkSet, or None if missing.
        left_hand: Detected Left HandLandmarkSet, or None if missing.
        right_hand: Detected Right HandLandmarkSet, or None if missing.

    Returns:
        ExtractedFrameFeatures object containing the 260-dim vector and validity flags.
    """
    timestamp_s = timestamp_ms / 1000.0

    # 1. Pose normalization (132 values)
    pose_detected = bool(pose and pose.is_detected)
    if pose_detected and pose is not None:
        norm_pose = normalize_pose_landmarks(pose, include_visibility=True)
        pose_flat = norm_pose.reshape(-1)
        # If normalization resulted in all NaNs (degenerate pose)
        if not np.any(np.isfinite(norm_pose[:, :3])):
            pose_detected = False
    else:
        pose_flat = np.full((POSE_FEAT_DIM,), np.nan, dtype=np.float64)
        pose_flat[3::4] = 0.0  # zero visibilities for missing pose

    # 2. Left Hand normalization (63 coords + 1 confidence = 64 values)
    left_detected = bool(left_hand and left_hand.is_detected)
    if left_detected and left_hand is not None:
        norm_left = normalize_hand_landmarks(left_hand).reshape(-1)
        left_conf = float(left_hand.confidence)
        if not np.any(np.isfinite(norm_left)):
            left_detected = False
            left_conf = 0.0
    else:
        norm_left = np.full((N_HAND_LANDMARKS * 3,), np.nan, dtype=np.float64)
        left_conf = 0.0

    # 3. Right Hand normalization (63 coords + 1 confidence = 64 values)
    right_detected = bool(right_hand and right_hand.is_detected)
    if right_detected and right_hand is not None:
        norm_right = normalize_hand_landmarks(right_hand).reshape(-1)
        right_conf = float(right_hand.confidence)
        if not np.any(np.isfinite(norm_right)):
            right_detected = False
            right_conf = 0.0
    else:
        norm_right = np.full((N_HAND_LANDMARKS * 3,), np.nan, dtype=np.float64)
        right_conf = 0.0

    # Combine into 260-dim vector
    feature_vector = np.concatenate([
        pose_flat,
        norm_left,
        np.array([left_conf], dtype=np.float64),
        norm_right,
        np.array([right_conf], dtype=np.float64),
    ]).astype(np.float64)

    return ExtractedFrameFeatures(
        frame_idx=frame_idx,
        timestamp_ms=timestamp_ms,
        timestamp_s=timestamp_s,
        feature_vector=feature_vector,
        pose_detected=pose_detected,
        left_hand_detected=left_detected,
        right_hand_detected=right_detected,
        schema_version=SCHEMA_VERSION,
    )


# ---------------------------------------------------------------------------
# MEMBER 4 CONVERSION ADAPTER
# ---------------------------------------------------------------------------

def extract_hand_for_mlp(
    hand: HandLandmarkSet | None,
    width: int,
    height: int,
) -> np.ndarray | None:
    """Extract 63 hand landmark values in PIXEL units for Member 4's MLP classifier.

    Member 4's `mudra_mlp.features.hand_features` and `mudra_eval.build_result`
    expect raw pixel coordinates (x*width, y*height, z*width) as input, or None
    when no hand was detected in the frame.

    Args:
        hand: Detected HandLandmarkSet, or None.
        width: Source video frame width in pixels (> 0).
        height: Source video frame height in pixels (> 0).

    Returns:
        np.ndarray of shape (63,) with pixel units, or None if hand is missing.
    """
    if width <= 0 or height <= 0:
        raise ValueError(f"Frame width and height must be positive, got ({width}, {height})")

    if hand is None or not hand.is_detected or not hand.landmarks:
        return None

    # Check for NaNs
    coords = hand.to_pixel_coords(width, height)
    if not np.all(np.isfinite(coords)):
        return None

    return coords
