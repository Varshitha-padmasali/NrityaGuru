"""Video reader with OpenCV for frame extraction, timestamping, and metadata.

Handles local files, synthetic test streams, and video device indices.
Ensures monotonically increasing timestamps required by MediaPipe Tasks VIDEO mode.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator, Iterator
import cv2
import numpy as np

from vision.schemas import FrameData, VideoMetadata


class VideoReader:
    """Robust OpenCV video wrapper providing frame-by-frame iteration and exact timestamps."""

    def __init__(
        self,
        source: str | Path | int,
        stride: int = 1,
        max_frames: int | None = None,
    ) -> None:
        """Initialize video reader.

        Args:
            source: Path to video file, or integer webcam index.
            stride: Step size between frames (1 = every frame, 2 = every other frame).
            max_frames: Maximum number of frames to read, or None for all.
        """
        self._is_closed = True
        self._cap = None

        if stride < 1:
            raise ValueError(f"stride must be >= 1, got {stride}")
        self.stride = stride
        self.max_frames = max_frames

        if isinstance(source, (str, Path)) and not isinstance(source, int):
            self.source_path = Path(source)
            if not self.source_path.exists():
                raise FileNotFoundError(f"Video file not found: {self.source_path}")
            self.source_str = str(self.source_path.resolve())
        else:
            self.source_path = None
            self.source_str = source

        self._cap = cv2.VideoCapture(self.source_str)
        if not self._cap.isOpened():
            raise ValueError(f"Failed to open video source: {source}")

        self._is_closed = False

        # Extract stream properties
        raw_fps = self._cap.get(cv2.CAP_PROP_FPS)
        self.fps = float(raw_fps) if (raw_fps and raw_fps > 0 and not np.isnan(raw_fps)) else 30.0

        raw_count = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.frame_count = max(0, raw_count)

        self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Decode fourcc code
        fourcc_val = int(self._cap.get(cv2.CAP_PROP_FOURCC))
        self.fourcc = "".join([chr((fourcc_val >> 8 * i) & 0xFF) for i in range(4)]).strip()

        duration = (self.frame_count / self.fps) if (self.fps > 0 and self.frame_count > 0) else 0.0
        self.metadata = VideoMetadata(
            path=str(self.source_str),
            fps=self.fps,
            frame_count=self.frame_count,
            duration_s=duration,
            width=self.width,
            height=self.height,
            fourcc=self.fourcc,
        )
        self._is_closed = False

    def __enter__(self) -> VideoReader:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        """Release underlying OpenCV video capture resource."""
        if not getattr(self, "_is_closed", True) and hasattr(self, "_cap") and self._cap is not None:
            self._cap.release()
            self._is_closed = True

    def __del__(self) -> None:
        self.close()

    def frames(self) -> Generator[FrameData, None, None]:
        """Generate frames with strictly monotonic timestamps and sequential frame indices."""
        if self._is_closed:
            raise RuntimeError("Cannot read from a closed VideoReader.")

        # Reset read position to beginning
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        source_idx = 0
        yielded_count = 0
        last_timestamp_ms = -1

        while True:
            if self.max_frames is not None and yielded_count >= self.max_frames:
                break

            ret, frame = self._cap.read()
            if not ret or frame is None:
                break

            if source_idx % self.stride == 0:
                # Calculate deterministic, strictly monotonic timestamps
                calc_ms = int(round((source_idx / self.fps) * 1000.0))
                # Ensure monotonicity even in edge cases
                timestamp_ms = max(calc_ms, last_timestamp_ms + 1)
                last_timestamp_ms = timestamp_ms
                timestamp_s = timestamp_ms / 1000.0

                h, w = frame.shape[:2]
                yield FrameData(
                    frame_idx=yielded_count,
                    timestamp_ms=timestamp_ms,
                    timestamp_s=timestamp_s,
                    image=frame,
                    width=w,
                    height=h,
                )
                yielded_count += 1

            source_idx += 1

    def __iter__(self) -> Iterator[FrameData]:
        return self.frames()


def create_synthetic_video(
    output_path: str | Path,
    num_frames: int = 30,
    width: int = 320,
    height: int = 240,
    fps: float = 30.0,
    color: tuple[int, int, int] = (40, 40, 180),
) -> Path:
    """Create a synthetic test video with a moving shape for deterministic unit testing.

    Args:
        output_path: Path where the test video will be written.
        num_frames: Number of frames to generate.
        width: Video frame width in pixels.
        height: Video frame height in pixels.
        fps: Frames per second.
        color: Base background BGR color.

    Returns:
        Path object pointing to the created video.
    """
    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # Use mp4v or XVID codec (widely supported on Windows)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_file), fourcc, fps, (width, height))

    if not writer.isOpened():
        # Fallback to XVID
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        out_file = out_file.with_suffix(".avi")
        writer = cv2.VideoWriter(str(out_file), fourcc, fps, (width, height))

    if not writer.isOpened():
        raise RuntimeError(f"Could not open VideoWriter for path: {out_file}")

    try:
        radius = 20
        for i in range(num_frames):
            frame = np.full((height, width, 3), color, dtype=np.uint8)
            # Draw moving circle across frames
            cx = int(radius + (i / max(num_frames - 1, 1)) * (width - 2 * radius))
            cy = int(height / 2)
            cv2.circle(frame, (cx, cy), radius, (255, 255, 255), -1)
            # Add frame index indicator
            cv2.putText(
                frame,
                f"F{i}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )
            writer.write(frame)
    finally:
        writer.release()

    if not out_file.exists() or out_file.stat().st_size == 0:
        raise RuntimeError(f"Failed to generate valid synthetic video at {out_file}")

    return out_file
