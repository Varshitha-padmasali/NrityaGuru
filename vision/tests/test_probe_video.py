"""Unit tests for the CLI probe_video tool and argument parsing."""

from pathlib import Path
import pytest

from vision.probe_video import build_parser, main, probe_video
from vision.sequence_builder import ProcessedSequence
from vision.video_reader import create_synthetic_video


def test_cli_argument_parser():
    parser = build_parser()
    args = parser.parse_args(["--video", "input.mp4", "--mock", "--stride", "2", "--max-frames", "50"])
    assert str(args.video) == "input.mp4"
    assert args.mock is True
    assert args.stride == 2
    assert args.max_frames == 50


def test_cli_mock_execution_and_export(tmp_path: Path, capsys):
    video_path = create_synthetic_video(tmp_path / "clip.mp4", num_frames=8, fps=20.0)
    out_dir = tmp_path / "probe_output"

    ret = main([
        "--video", str(video_path),
        "--mock",
        "--out", str(out_dir),
    ])

    assert ret == 0
    captured = capsys.readouterr()
    assert "NrityaGuru Video Probe Report" in captured.out
    assert "MOCK (Synthetic / Offline)" in captured.out
    assert "Tracking Status   : RELIABLE" in captured.out
    assert "Exported NPZ" in captured.out

    npz_file = out_dir / "clip_sequence.npz"
    json_file = out_dir / "clip_sequence.json"
    assert npz_file.is_file()
    assert json_file.is_file()


def test_cli_missing_video_exits_error(capsys):
    ret = main(["--video", "does_not_exist_xyz.mp4", "--mock"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "[ERROR] File not found" in captured.err


def test_cli_real_mode_missing_model_exits_error(tmp_path: Path, capsys):
    video_path = create_synthetic_video(tmp_path / "clip2.mp4", num_frames=3)
    # Running without --mock when model files are not present should exit with code 1
    ret = main(["--video", str(video_path)])
    assert ret == 1
    captured = capsys.readouterr()
    assert "[ERROR] File not found" in captured.err
    assert "model file not found" in captured.err.lower()


def test_probe_video_programmatic_api(tmp_path: Path):
    video_path = create_synthetic_video(tmp_path / "prog.mp4", num_frames=6)
    seq = probe_video(
        video_path=video_path,
        mock=True,
        max_frames=4,
        verbose=False,
    )
    assert isinstance(seq, ProcessedSequence)
    assert seq.num_frames == 4
    assert seq.features.shape == (4, 260)
