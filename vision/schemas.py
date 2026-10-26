"""Pydantic schemas and data models for the NrityaGuru Vision Module.

Defines point, landmark, frame, metadata, and quality structures.
Maintains exact dimension alignment (260 features per frame) and compatibility
with Member 2's LandmarkQuality contract and Member 4's MLP/DTW evaluators.
"""

from __future__ import annotations

import math
from typing import Any, Literal
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# --- FEATURE SCHEMA CONSTANTS ---
N_POSE_LANDMARKS: int = 33
N_HAND_LANDMARKS: int = 21

# 33 pose landmarks * 4 (x, y, z, visibility) = 132
POSE_FEAT_DIM: int = N_POSE_LANDMARKS * 4

# 21 hand landmarks * 3 (x, y, z) + 1 (detection score/presence) = 64 per hand
HAND_FEAT_DIM: int = (N_HAND_LANDMARKS * 3) + 1

# Total frame vector dimension: 132 + 64 + 64 = 260
FEATURE_DIM: int = POSE_FEAT_DIM + (HAND_FEAT_DIM * 2)

# Slice boundaries in the 260-value vector
POSE_SLICE = slice(0, POSE_FEAT_DIM)  # [0:132]
LEFT_HAND_SLICE = slice(POSE_FEAT_DIM, POSE_FEAT_DIM + HAND_FEAT_DIM)  # [132:196]
RIGHT_HAND_SLICE = slice(POSE_FEAT_DIM + HAND_FEAT_DIM, FEATURE_DIM)  # [196:260]

# Coordinate slices for Member 4's single-hand MLP (63 values each)
LEFT_HAND_COORDS_SLICE = slice(132, 195)
RIGHT_HAND_COORDS_SLICE = slice(196, 259)

RELIABLE_DETECTION_THRESHOLD = 0.80  # Consistent with Member 4's contract assumption


class Point3D(BaseModel):
    """A 3D coordinate point with optional visibility and presence scores."""

    model_config = ConfigDict(frozen=True)

    x: float
    y: float
    z: float
    visibility: float | None = None
    presence: float | None = None

    def is_nan(self) -> bool:
        """Check if any primary spatial coordinate is NaN."""
        return math.isnan(self.x) or math.isnan(self.y) or math.isnan(self.z)

    def to_array(self, include_visibility: bool = False) -> np.ndarray:
        """Convert to NumPy array: shape (3,) or (4,)."""
        if include_visibility:
            vis = 0.0 if (self.visibility is None or math.isnan(self.visibility)) else self.visibility
            return np.array([self.x, self.y, self.z, vis], dtype=float)
        return np.array([self.x, self.y, self.z], dtype=float)

    def to_pixel(self, width: int, height: int) -> Point3D:
        """Scale normalized coordinates [0, 1] to pixel units [width, height]."""
        return Point3D(
            x=self.x * width,
            y=self.y * height,
            z=self.z * width,
            visibility=self.visibility,
            presence=self.presence,
        )

    @classmethod
    def nan_point(cls) -> Point3D:
        """Create a point with NaN coordinates representing a missing landmark."""
        return cls(x=float("nan"), y=float("nan"), z=float("nan"), visibility=0.0, presence=0.0)


class HandLandmarkSet(BaseModel):
    """Set of 21 landmarks for a single hand (Left or Right)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    side: Literal["Left", "Right"]
    landmarks: list[Point3D] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_detected: bool = True

    @field_validator("landmarks")
    @classmethod
    def validate_landmarks_count(cls, v: list[Point3D]) -> list[Point3D]:
        if v and len(v) != N_HAND_LANDMARKS:
            raise ValueError(f"Hand landmark set must contain {N_HAND_LANDMARKS} points, got {len(v)}")
        return v

    def to_numpy(self, coords_only: bool = True) -> np.ndarray:
        """Return flat numpy array: (63,) if coords_only, or (64,) including confidence score.
        Returns array of NaNs if hand was not detected.
        """
        if not self.is_detected or not self.landmarks:
            dim = 63 if coords_only else 64
            arr = np.full((dim,), np.nan, dtype=float)
            if not coords_only:
                arr[-1] = 0.0  # zero confidence
            return arr

        coords = np.array([lm.to_array(include_visibility=False) for lm in self.landmarks], dtype=float).reshape(-1)
        if coords_only:
            return coords
        return np.append(coords, self.confidence)

    def to_pixel_coords(self, width: int, height: int) -> np.ndarray:
        """Convert landmarks to 63-value flat array in pixel units (expected by Member 4 MLP)."""
        if not self.is_detected or not self.landmarks:
            return np.full((63,), np.nan, dtype=float)
        pixels = [lm.to_pixel(width, height).to_array(include_visibility=False) for lm in self.landmarks]
        return np.array(pixels, dtype=float).reshape(-1)

    @classmethod
    def missing(cls, side: Literal["Left", "Right"]) -> HandLandmarkSet:
        """Construct an explicit missing hand representation."""
        return cls(
            side=side,
            landmarks=[Point3D.nan_point() for _ in range(N_HAND_LANDMARKS)],
            confidence=0.0,
            is_detected=False,
        )


class PoseLandmarkSet(BaseModel):
    """Set of 33 landmarks for body pose."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    landmarks: list[Point3D] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_detected: bool = True

    @field_validator("landmarks")
    @classmethod
    def validate_landmarks_count(cls, v: list[Point3D]) -> list[Point3D]:
        if v and len(v) != N_POSE_LANDMARKS:
            raise ValueError(f"Pose landmark set must contain {N_POSE_LANDMARKS} points, got {len(v)}")
        return v

    def to_numpy(self, include_visibility: bool = True) -> np.ndarray:
        """Return flat numpy array: (132,) if include_visibility else (99,).
        Returns array of NaNs if pose was not detected.
        """
        dim = 132 if include_visibility else 99
        if not self.is_detected or not self.landmarks:
            arr = np.full((dim,), np.nan, dtype=float)
            if include_visibility:
                # set visibilities to 0.0
                arr[3::4] = 0.0
            return arr

        arr = np.array([lm.to_array(include_visibility=include_visibility) for lm in self.landmarks], dtype=float)
        return arr.reshape(-1)

    @classmethod
    def missing(cls) -> PoseLandmarkSet:
        """Construct an explicit missing pose representation."""
        return cls(
            landmarks=[Point3D.nan_point() for _ in range(N_POSE_LANDMARKS)],
            confidence=0.0,
            is_detected=False,
        )


class VideoMetadata(BaseModel):
    """Metadata extracted from a video source."""

    path: str
    fps: float = Field(gt=0.0)
    frame_count: int = Field(ge=0)
    duration_s: float = Field(ge=0.0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fourcc: str = ""

    @model_validator(mode="before")
    @classmethod
    def calculate_duration(cls, data: Any) -> Any:
        if isinstance(data, dict):
            fps = data.get("fps", 0.0)
            fc = data.get("frame_count", 0)
            if "duration_s" not in data or data["duration_s"] is None:
                data["duration_s"] = (fc / fps) if fps > 0 else 0.0
        return data


class FrameData(BaseModel):
    """A raw image frame extracted by the video reader."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    frame_idx: int = Field(ge=0)
    timestamp_ms: int = Field(ge=0)
    timestamp_s: float = Field(ge=0.0)
    image: np.ndarray  # BGR image array
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    @property
    def rgb_image(self) -> np.ndarray:
        """Return RGB copy of the frame (required by MediaPipe)."""
        import cv2
        return np.ascontiguousarray(cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB))


class FrameLandmarks(BaseModel):
    """All detected landmarks and synthesized features for a single video frame."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    frame_idx: int = Field(ge=0)
    timestamp_ms: int = Field(ge=0)
    timestamp_s: float = Field(ge=0.0)
    pose: PoseLandmarkSet | None = None
    left_hand: HandLandmarkSet | None = None
    right_hand: HandLandmarkSet | None = None
    feature_vector: list[float] | None = None

    @property
    def pose_detected(self) -> bool:
        return bool(self.pose and self.pose.is_detected)

    @property
    def left_hand_detected(self) -> bool:
        return bool(self.left_hand and self.left_hand.is_detected)

    @property
    def right_hand_detected(self) -> bool:
        return bool(self.right_hand and self.right_hand.is_detected)

    @property
    def any_hand_detected(self) -> bool:
        return self.left_hand_detected or self.right_hand_detected


class DataQualityReport(BaseModel):
    """Data quality and tracking reliability report for a video sequence.

    Directly conforms to Member 2's LandmarkQuality contract schema
    in backend/app/schemas/evaluation.py.
    """

    hand_detection_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    pose_detection_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    frames_total: int = Field(default=0, ge=0)
    frames_analysed: int = Field(default=0, ge=0)
    reliable: bool = False
    notes: list[str] = Field(default_factory=list, max_length=10)

    @classmethod
    def compute(
        cls,
        frames_total: int,
        frames_analysed: int,
        frames_with_hand: int,
        frames_with_pose: int,
        reliable_threshold: float = RELIABLE_DETECTION_THRESHOLD,
    ) -> DataQualityReport:
        """Compute tracking rates and reliability from raw frame counts."""
        if frames_analysed == 0 or frames_total == 0:
            return cls(
                hand_detection_rate=0.0,
                pose_detection_rate=0.0,
                frames_total=frames_total,
                frames_analysed=frames_analysed,
                reliable=False,
                notes=["No frames were successfully analysed from the video."],
            )

        hand_rate = round(float(frames_with_hand / frames_analysed), 4)
        pose_rate = round(float(frames_with_pose / frames_analysed), 4)
        notes: list[str] = []

        reliable = bool(hand_rate >= reliable_threshold and pose_rate >= reliable_threshold)
        if not reliable:
            if hand_rate < reliable_threshold:
                notes.append(
                    f"Hand detected in only {frames_with_hand}/{frames_analysed} frames "
                    f"({hand_rate:.1%}, needs >={reliable_threshold:.0%})."
                )
            if pose_rate < reliable_threshold:
                notes.append(
                    f"Pose detected in only {frames_with_pose}/{frames_analysed} frames "
                    f"({pose_rate:.1%}, needs >={reliable_threshold:.0%})."
                )

        return cls(
            hand_detection_rate=hand_rate,
            pose_detection_rate=pose_rate,
            frames_total=frames_total,
            frames_analysed=frames_analysed,
            reliable=reliable,
            notes=notes,
        )
