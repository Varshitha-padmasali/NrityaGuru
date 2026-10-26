"""Unit tests for the OpenCV video reader and synthetic video generation."""

from pathlib import Path
import numpy as np
import pytest

from vision.video_reader import VideoReader, create_synthetic_video


def test_video_reader_file_not_found():
    with pytest.raises(FileNotFoundError):
        VideoReader("non_existent_video_path.mp4")


def test_video_reader_invalid_stride():
    with pytest.raises(ValueError, match="stride must be >= 1"):
        VideoReader("dummy", stride=0)


def test_synthetic_video_creation_and_reading(tmp_path: Path):
    video_path = tmp_path / "test_clip.mp4"
    created = create_synthetic_video(
        video_path,
        num_frames=20,
        width=320,
        height=240,
        fps=25.0,
    )
    assert created.exists()
    assert created.stat().st_size > 0

    with VideoReader(created) as reader:
        meta = reader.metadata
        assert meta.width == 320
        assert meta.height == 240
        assert meta.fps == pytest.approx(25.0, abs=1.0)
        assert meta.frame_count >= 19

        frames = list(reader.frames())
        assert len(frames) == 20

        prev_ms = -1
        for idx, f in enumerate(frames):
            assert f.frame_idx == idx
            assert f.timestamp_ms > prev_ms, "Timestamps must increase monotonically"
            prev_ms = f.timestamp_ms
            assert f.timestamp_s == pytest.approx(f.timestamp_ms / 1000.0)
            assert f.width == 320
            assert f.height == 240
            assert f.image.shape == (240, 320, 3)
            assert f.rgb_image.shape == (240, 320, 3)


def test_video_reader_context_manager_close(tmp_path: Path):
    video_path = create_synthetic_video(tmp_path / "close_test.mp4", num_frames=5)
    reader = VideoReader(video_path)
    with reader:
        frames = list(reader)
        assert len(frames) == 5

    assert reader._is_closed
    with pytest.raises(RuntimeError, match="closed VideoReader"):
        list(reader.frames())


def test_video_reader_stride(tmp_path: Path):
    video_path = create_synthetic_video(tmp_path / "stride_test.mp4", num_frames=20)
    with VideoReader(video_path, stride=2) as reader:
        frames = list(reader.frames())
        assert len(frames) == 10
        for i, f in enumerate(frames):
            assert f.frame_idx == i


def test_video_reader_max_frames(tmp_path: Path):
    video_path = create_synthetic_video(tmp_path / "max_test.mp4", num_frames=25)
    with VideoReader(video_path, max_frames=8) as reader:
        frames = list(reader.frames())
        assert len(frames) == 8
