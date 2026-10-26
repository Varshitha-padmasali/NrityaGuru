"""Base interfaces and backends for hand and pose detection.

Provides decoupled backends:
- MediaPipe Tasks API backend (for real inference with .task models)
- Mock backends (for deterministic, reproducible unit testing without model downloads)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from vision.schemas import (
    HandLandmarkSet,
    N_HAND_LANDMARKS,
    N_POSE_LANDMARKS,
    Point3D,
    PoseLandmarkSet,
)


class HandDetectionResult(BaseModel):
    """Result of hand detection for a single video frame."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    left_hand: HandLandmarkSet
    right_hand: HandLandmarkSet
    timestamp_ms: int = Field(ge=0)

    @property
    def any_detected(self) -> bool:
        return self.left_hand.is_detected or self.right_hand.is_detected

    @property
    def both_detected(self) -> bool:
        return self.left_hand.is_detected and self.right_hand.is_detected


class PoseDetectionResult(BaseModel):
    """Result of pose detection for a single video frame."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    pose: PoseLandmarkSet
    timestamp_ms: int = Field(ge=0)

    @property
    def is_detected(self) -> bool:
        return self.pose.is_detected


class BaseHandBackend(ABC):
    """Abstract interface for hand landmark detection backends."""

    @abstractmethod
    def detect_hands(self, rgb_image: np.ndarray, timestamp_ms: int) -> HandDetectionResult:
        """Detect hands from an RGB image frame and return structured results."""
        pass

    def close(self) -> None:
        """Release any hardware/model resources."""
        pass


class BasePoseBackend(ABC):
    """Abstract interface for body pose landmark detection backends."""

    @abstractmethod
    def detect_pose(self, rgb_image: np.ndarray, timestamp_ms: int) -> PoseDetectionResult:
        """Detect body pose from an RGB image frame and return structured results."""
        pass

    def close(self) -> None:
        """Release any hardware/model resources."""
        pass


# ---------------------------------------------------------------------------
# MOCK BACKENDS (For deterministic, offline unit testing)
# ---------------------------------------------------------------------------

class MockHandBackend(BaseHandBackend):
    """Synthetic hand detector backend for reproducible unit testing without model files."""

    def __init__(
        self,
        detect_left: bool = True,
        detect_right: bool = True,
        confidence: float = 0.90,
    ) -> None:
        self.detect_left = detect_left
        self.detect_right = detect_right
        self.confidence = confidence
        self.call_history: list[tuple[int, tuple[int, ...]]] = []

    def detect_hands(self, rgb_image: np.ndarray, timestamp_ms: int) -> HandDetectionResult:
        self.call_history.append((timestamp_ms, rgb_image.shape))

        # Build left hand
        if self.detect_left:
            pts_left = [
                Point3D(x=0.2 + 0.01 * i, y=0.5 + 0.01 * i, z=-0.05 + 0.005 * i)
                for i in range(N_HAND_LANDMARKS)
            ]
            left_hand = HandLandmarkSet(
                side="Left",
                landmarks=pts_left,
                confidence=self.confidence,
                is_detected=True,
            )
        else:
            left_hand = HandLandmarkSet.missing("Left")

        # Build right hand
        if self.detect_right:
            pts_right = [
                Point3D(x=0.7 + 0.01 * i, y=0.5 + 0.01 * i, z=-0.05 + 0.005 * i)
                for i in range(N_HAND_LANDMARKS)
            ]
            right_hand = HandLandmarkSet(
                side="Right",
                landmarks=pts_right,
                confidence=self.confidence,
                is_detected=True,
            )
        else:
            right_hand = HandLandmarkSet.missing("Right")

        return HandDetectionResult(
            left_hand=left_hand,
            right_hand=right_hand,
            timestamp_ms=timestamp_ms,
        )


class MockPoseBackend(BasePoseBackend):
    """Synthetic pose detector backend for reproducible unit testing without model files."""

    def __init__(
        self,
        detect_pose: bool = True,
        confidence: float = 0.92,
    ) -> None:
        self.detect_pose_flag = detect_pose
        self.confidence = confidence
        self.call_history: list[tuple[int, tuple[int, ...]]] = []

    def detect_pose(self, rgb_image: np.ndarray, timestamp_ms: int) -> PoseDetectionResult:
        self.call_history.append((timestamp_ms, rgb_image.shape))

        if self.detect_pose_flag:
            pts = [
                Point3D(
                    x=0.5 + 0.005 * (i % 5),
                    y=0.2 + 0.02 * i,
                    z=0.01 * (i % 3),
                    visibility=0.95,
                    presence=0.95,
                )
                for i in range(N_POSE_LANDMARKS)
            ]
            pose = PoseLandmarkSet(
                landmarks=pts,
                confidence=self.confidence,
                is_detected=True,
            )
        else:
            pose = PoseLandmarkSet.missing()

        return PoseDetectionResult(
            pose=pose,
            timestamp_ms=timestamp_ms,
        )


# ---------------------------------------------------------------------------
# MEDIAPIPE TASKS BACKENDS (Real model inference)
# ---------------------------------------------------------------------------

class MediaPipeHandBackend(BaseHandBackend):
    """Real HandLandmarker backend utilizing MediaPipe Tasks Python API."""

    def __init__(
        self,
        model_path: str | Path,
        num_hands: int = 2,
        min_hand_detection_confidence: float = 0.5,
        min_hand_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        path = Path(model_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(
                f"MediaPipe Hand Landmarker model file not found at: {path}\n"
                "To download the official model file, run:\n"
                "curl -L -o models/hand_landmarker.task "
                "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
            )

        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        base_options = mp_python.BaseOptions(
            model_asset_path=str(path), delegate=mp_python.BaseOptions.Delegate.CPU
        )
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=num_hands,
            min_hand_detection_confidence=min_hand_detection_confidence,
            min_hand_presence_confidence=min_hand_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)

    def detect_hands(self, rgb_image: np.ndarray, timestamp_ms: int) -> HandDetectionResult:
        rgb_contiguous = np.ascontiguousarray(rgb_image)
        mp_image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB,
            data=rgb_contiguous,
        )
        result = self._landmarker.detect_for_video(mp_image, int(timestamp_ms))

        left_hand = HandLandmarkSet.missing("Left")
        right_hand = HandLandmarkSet.missing("Right")

        if result.hand_landmarks and result.handedness:
            for landmarks, handedness in zip(result.hand_landmarks, result.handedness):
                category = handedness[0]
                detected_side = str(category.category_name).capitalize()
                score = float(category.score)

                pts = [
                    Point3D(
                        x=float(lm.x),
                        y=float(lm.y),
                        z=float(lm.z),
                        visibility=getattr(lm, "visibility", None),
                        presence=getattr(lm, "presence", None),
                    )
                    for lm in landmarks
                ]

                # Assign or update if confidence is higher
                if detected_side == "Left":
                    if not left_hand.is_detected or score > left_hand.confidence:
                        left_hand = HandLandmarkSet(
                            side="Left",
                            landmarks=pts,
                            confidence=score,
                            is_detected=True,
                        )
                elif detected_side == "Right":
                    if not right_hand.is_detected or score > right_hand.confidence:
                        right_hand = HandLandmarkSet(
                            side="Right",
                            landmarks=pts,
                            confidence=score,
                            is_detected=True,
                        )

        return HandDetectionResult(
            left_hand=left_hand,
            right_hand=right_hand,
            timestamp_ms=timestamp_ms,
        )

    def close(self) -> None:
        if hasattr(self, "_landmarker") and self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None


class MediaPipePoseBackend(BasePoseBackend):
    """Real PoseLandmarker backend utilizing MediaPipe Tasks Python API."""

    def __init__(
        self,
        model_path: str | Path,
        min_pose_detection_confidence: float = 0.5,
        min_pose_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        path = Path(model_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(
                f"MediaPipe Pose Landmarker model file not found at: {path}\n"
                "To download the official model file, run:\n"
                "curl -L -o models/pose_landmarker.task "
                "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task"
            )

        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        base_options = mp_python.BaseOptions(
            model_asset_path=str(path), delegate=mp_python.BaseOptions.Delegate.CPU
        )
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=min_pose_detection_confidence,
            min_pose_presence_confidence=min_pose_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)

    def detect_pose(self, rgb_image: np.ndarray, timestamp_ms: int) -> PoseDetectionResult:
        rgb_contiguous = np.ascontiguousarray(rgb_image)
        mp_image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB,
            data=rgb_contiguous,
        )
        result = self._landmarker.detect_for_video(mp_image, int(timestamp_ms))

        if result.pose_landmarks and len(result.pose_landmarks) > 0:
            raw_landmarks = result.pose_landmarks[0]
            pts = [
                Point3D(
                    x=float(lm.x),
                    y=float(lm.y),
                    z=float(lm.z),
                    visibility=float(lm.visibility) if hasattr(lm, "visibility") and lm.visibility is not None else None,
                    presence=float(lm.presence) if hasattr(lm, "presence") and lm.presence is not None else None,
                )
                for lm in raw_landmarks
            ]
            # Average visibility as overall confidence indicator
            vis_list = [p.visibility for p in pts if p.visibility is not None]
            conf = float(np.mean(vis_list)) if vis_list else 0.85
            pose = PoseLandmarkSet(
                landmarks=pts,
                confidence=conf,
                is_detected=True,
            )
        else:
            pose = PoseLandmarkSet.missing()

        return PoseDetectionResult(
            pose=pose,
            timestamp_ms=timestamp_ms,
        )

    def close(self) -> None:
        if hasattr(self, "_landmarker") and self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
