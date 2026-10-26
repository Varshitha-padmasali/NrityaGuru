"""End-to-end frame processing pipeline for NrityaGuru Vision Module.

Coordinates:
  VideoReader -> HandDetector -> PoseDetector -> Feature Extraction -> Quality Report

Produces a chronological, time-ordered sequence of 260-dimensional feature vectors
with explicit timestamps, frame indices, validity masks, and Member 2-compatible
data quality metrics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator, Literal, Union
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from vision.detectors.base import BaseHandBackend, BasePoseBackend
from vision.feature_extractor import (
    ExtractedFrameFeatures,
    extract_frame_features,
    extract_hand_for_mlp,
)
from vision.hand_detector import HandDetector
from vision.pose_detector import PoseDetector
from vision.schemas import (
    DataQualityReport,
    FEATURE_DIM,
    FrameData,
    LEFT_HAND_COORDS_SLICE,
    LEFT_HAND_SLICE,
    POSE_SLICE,
    RIGHT_HAND_COORDS_SLICE,
    RIGHT_HAND_SLICE,
    VideoMetadata,
)
from vision.video_reader import VideoReader


class ProcessedSequence(BaseModel):
    """Result of end-to-end video processing containing feature matrices and quality metrics."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    metadata: VideoMetadata
    frames: list[ExtractedFrameFeatures]
    features: np.ndarray  # Shape (T, 260), dtype float64
    timestamps_ms: np.ndarray  # Shape (T,), dtype int64
    timestamps_s: np.ndarray  # Shape (T,), dtype float64
    frame_indices: np.ndarray  # Shape (T,), dtype int64
    detection_mask: np.ndarray  # Shape (T, 3), dtype bool: [pose, left_hand, right_hand]
    validity_mask: np.ndarray  # Shape (T, 260), dtype bool: True where finite
    quality_report: DataQualityReport

    @property
    def num_frames(self) -> int:
        """Number of analyzed frames in the sequence (T)."""
        return len(self.frames)

    def get_pose_matrix(self) -> np.ndarray:
        """Return the (T, 132) pose feature matrix."""
        if self.num_frames == 0:
            return np.empty((0, 132), dtype=np.float64)
        return self.features[:, POSE_SLICE]

    def get_left_hand_matrix(self, include_confidence: bool = False) -> np.ndarray:
        """Return the (T, 63) or (T, 64) left hand feature matrix."""
        if self.num_frames == 0:
            dim = 64 if include_confidence else 63
            return np.empty((0, dim), dtype=np.float64)
        sl = LEFT_HAND_SLICE if include_confidence else LEFT_HAND_COORDS_SLICE
        return self.features[:, sl]

    def get_right_hand_matrix(self, include_confidence: bool = False) -> np.ndarray:
        """Return the (T, 63) or (T, 64) right hand feature matrix."""
        if self.num_frames == 0:
            dim = 64 if include_confidence else 63
            return np.empty((0, dim), dtype=np.float64)
        sl = RIGHT_HAND_SLICE if include_confidence else RIGHT_HAND_COORDS_SLICE
        return self.features[:, sl]

    def extract_mlp_hand_sequence(
        self,
        side: Literal["Left", "Right"] = "Right",
        width: int | None = None,
        height: int | None = None,
    ) -> list[np.ndarray | None]:
        """Extract a list of 63-value pixel-coordinate vectors for Member 4's MLP.

        Returns a list of length T where each entry is an (63,) float array in pixel units
        or None when the hand was not detected in that frame.
        """
        w = width or self.metadata.width
        h = height or self.metadata.height

        out: list[np.ndarray | None] = []
        for f in self.frames:
            # Reconstruct pixel coords if detected
            detected = f.left_hand_detected if side == "Left" else f.right_hand_detected
            if not detected:
                out.append(None)
                continue

            sl = LEFT_HAND_COORDS_SLICE if side == "Left" else RIGHT_HAND_COORDS_SLICE
            norm_coords = f.feature_vector[sl]
            if not np.all(np.isfinite(norm_coords)):
                out.append(None)
                continue

            # Scale to pixel units: x*w, y*h, z*w
            pixel_coords = norm_coords.copy()
            pixel_coords[0::3] *= w
            pixel_coords[1::3] *= h
            pixel_coords[2::3] *= w
            out.append(pixel_coords)

        return out


class VisionPipeline:
    """End-to-end computer vision processing pipeline for Bharatanatyam dance videos."""

    def __init__(
        self,
        hand_detector: HandDetector | None = None,
        pose_detector: PoseDetector | None = None,
        hand_model_path: str | Path | None = None,
        pose_model_path: str | Path | None = None,
        hand_backend: BaseHandBackend | None = None,
        pose_backend: BasePoseBackend | None = None,
    ) -> None:
        """Initialize the vision pipeline with detectors.

        Args:
            hand_detector: Optional pre-configured HandDetector.
            pose_detector: Optional pre-configured PoseDetector.
            hand_model_path: Path to hand_landmarker.task if creating a new detector.
            pose_model_path: Path to pose_landmarker.task if creating a new detector.
            hand_backend: Optional pluggable backend for hand detection (e.g. MockHandBackend).
            pose_backend: Optional pluggable backend for pose detection (e.g. MockPoseBackend).
        """
        if hand_detector is not None:
            self.hand_detector = hand_detector
        else:
            self.hand_detector = HandDetector(
                model_path=hand_model_path,
                backend=hand_backend,
            )

        if pose_detector is not None:
            self.pose_detector = pose_detector
        else:
            self.pose_detector = PoseDetector(
                model_path=pose_model_path,
                backend=pose_backend,
            )

    def process_video(
        self,
        video_source: str | Path | int,
        stride: int = 1,
        max_frames: int | None = None,
    ) -> ProcessedSequence:
        """Process video and generate time-ordered features and quality diagnostics.

        Args:
            video_source: Video file path or webcam index.
            stride: Process every Nth frame (default: 1).
            max_frames: Maximum number of frames to process, or None for all.

        Returns:
            ProcessedSequence containing matrices, metadata, and quality report.
        """
        with VideoReader(video_source, stride=stride, max_frames=max_frames) as reader:
            metadata = reader.metadata
            frames_extracted: list[ExtractedFrameFeatures] = []

            frames_total = metadata.frame_count if metadata.frame_count > 0 else 0
            frames_analysed = 0
            frames_with_hand = 0
            frames_with_pose = 0

            for frame_data in reader:
                frames_analysed += 1

                # 1. Detect hands and pose
                hand_res = self.hand_detector.detect(frame_data)
                pose_res = self.pose_detector.detect(frame_data)

                # 2. Extract normalized 260-dim feature vector
                features = extract_frame_features(
                    frame_idx=frame_data.frame_idx,
                    timestamp_ms=frame_data.timestamp_ms,
                    pose=pose_res.pose,
                    left_hand=hand_res.left_hand,
                    right_hand=hand_res.right_hand,
                )
                frames_extracted.append(features)

                # 3. Track detection statistics
                if features.left_hand_detected or features.right_hand_detected:
                    frames_with_hand += 1
                if features.pose_detected:
                    frames_with_pose += 1

            if frames_total == 0:
                frames_total = frames_analysed

            # 4. Generate data quality report
            quality = DataQualityReport.compute(
                frames_total=frames_total,
                frames_analysed=frames_analysed,
                frames_with_hand=frames_with_hand,
                frames_with_pose=frames_with_pose,
            )

            # 5. Compile sequence matrices
            n_frames = len(frames_extracted)
            if n_frames > 0:
                feat_matrix = np.stack([f.feature_vector for f in frames_extracted], axis=0)
                ts_ms = np.array([f.timestamp_ms for f in frames_extracted], dtype=np.int64)
                ts_s = np.array([f.timestamp_s for f in frames_extracted], dtype=np.float64)
                indices = np.array([f.frame_idx for f in frames_extracted], dtype=np.int64)
                det_mask = np.array(
                    [[f.pose_detected, f.left_hand_detected, f.right_hand_detected] for f in frames_extracted],
                    dtype=bool,
                )
                val_mask = np.isfinite(feat_matrix)
            else:
                feat_matrix = np.empty((0, FEATURE_DIM), dtype=np.float64)
                ts_ms = np.empty((0,), dtype=np.int64)
                ts_s = np.empty((0,), dtype=np.float64)
                indices = np.empty((0,), dtype=np.int64)
                det_mask = np.empty((0, 3), dtype=bool)
                val_mask = np.empty((0, FEATURE_DIM), dtype=bool)

            return ProcessedSequence(
                metadata=metadata,
                frames=frames_extracted,
                features=feat_matrix,
                timestamps_ms=ts_ms,
                timestamps_s=ts_s,
                frame_indices=indices,
                detection_mask=det_mask,
                validity_mask=val_mask,
                quality_report=quality,
            )

    def close(self) -> None:
        """Release pipeline detector resources."""
        self.hand_detector.close()
        self.pose_detector.close()

    def __enter__(self) -> VisionPipeline:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
