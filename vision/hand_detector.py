"""Hand landmark detector utilizing MediaPipe Tasks API.

Detects up to 2 hands in video frames with exact timestamp synchronization,
providing structured landmarks and confidence scores for Left and Right hands.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
import cv2
import numpy as np

from vision.detectors.base import (
    BaseHandBackend,
    HandDetectionResult,
    MediaPipeHandBackend,
)
from vision.schemas import FrameData


class HandDetector:
    """High-level hand detector wrapping MediaPipe Tasks HandLandmarker."""

    def __init__(
        self,
        model_path: str | Path | None = None,
        num_hands: int = 2,
        min_hand_detection_confidence: float = 0.5,
        min_hand_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        backend: BaseHandBackend | None = None,
    ) -> None:
        """Initialize hand detector.

        Args:
            model_path: Path to `hand_landmarker.task`. If None, checks env var
                MEDIAPIPE_HAND_MODEL_PATH or default `models/hand_landmarker.task`.
            num_hands: Maximum number of hands to detect (default: 2).
            min_hand_detection_confidence: Minimum detection score threshold.
            min_hand_presence_confidence: Minimum presence score threshold.
            min_tracking_confidence: Minimum tracking score threshold.
            backend: Optional pluggable BaseHandBackend (useful for dependency injection / mocking).
        """
        if backend is not None:
            self._backend = backend
            return

        resolved_path = None
        if model_path is not None:
            resolved_path = Path(model_path)
        elif "MEDIAPIPE_HAND_MODEL_PATH" in os.environ:
            resolved_path = Path(os.environ["MEDIAPIPE_HAND_MODEL_PATH"])
        else:
            default_path = Path("models/hand_landmarker.task")
            if default_path.exists():
                resolved_path = default_path

        if resolved_path is None or not resolved_path.is_file():
            raise FileNotFoundError(
                f"Hand Landmarker model file not found ({resolved_path or 'no path specified'}).\n"
                "Please configure MEDIAPIPE_HAND_MODEL_PATH or pass model_path='path/to/hand_landmarker.task'.\n"
                "To download the official MediaPipe model file:\n"
                "curl -L -o models/hand_landmarker.task "
                "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task\n"
                "For testing without models, pass backend=MockHandBackend()."
            )

        self._backend = MediaPipeHandBackend(
            model_path=resolved_path,
            num_hands=num_hands,
            min_hand_detection_confidence=min_hand_detection_confidence,
            min_hand_presence_confidence=min_hand_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def detect(
        self,
        frame: FrameData | np.ndarray,
        timestamp_ms: int | None = None,
    ) -> HandDetectionResult:
        """Detect hands from a FrameData object or raw image array.

        Args:
            frame: A FrameData instance from VideoReader, or raw BGR numpy array.
            timestamp_ms: Required if frame is a numpy array. Ignored if frame is FrameData.

        Returns:
            HandDetectionResult containing left_hand and right_hand sets and timestamp.
        """
        if isinstance(frame, FrameData):
            rgb = frame.rgb_image
            ts = frame.timestamp_ms
        elif isinstance(frame, np.ndarray):
            if timestamp_ms is None:
                raise ValueError("timestamp_ms must be provided when passing a raw image array.")
            rgb = np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            ts = timestamp_ms
        else:
            raise TypeError(f"Expected FrameData or np.ndarray, got {type(frame)}")

        return self._backend.detect_hands(rgb, ts)

    def __enter__(self) -> HandDetector:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        """Release detector resources."""
        if hasattr(self, "_backend") and self._backend is not None:
            self._backend.close()
