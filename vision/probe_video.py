"""Command-line video inspection and landmark extraction utility for NrityaGuru.

Probes video streams, runs hand and body pose tracking, displays diagnostics,
and exports canonical 260-dim feature sequences (.npz) and metadata (.json).

Usage:
  # Mock dry-run (offline, no model files needed):
  python -m vision.probe_video --video path/to/video.mp4 --mock --out output/

  # Real inference (requires hand_landmarker.task & pose_landmarker.task):
  python -m vision.probe_video --video path/to/video.mp4 --out output/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence

from vision.detectors.base import MockHandBackend, MockPoseBackend
from vision.exporter import export_sequence
from vision.sequence_builder import ProcessedSequence, VisionPipeline


def format_report(sequence: ProcessedSequence, mode: str, npz_path: Path | None = None, json_path: Path | None = None) -> str:
    """Format human-readable diagnostics summary table."""
    meta = sequence.metadata
    q = sequence.quality_report

    status_str = "RELIABLE" if q.reliable else "UNRELIABLE"
    notes_str = "; ".join(q.notes) if q.notes else "(none)"

    lines = [
        "",
        "=" * 70,
        "                     NrityaGuru Video Probe Report",
        "=" * 70,
        f"Video Source      : {meta.path}",
        f"Resolution        : {meta.width} x {meta.height}",
        f"FPS               : {meta.fps:.2f}",
        f"Duration          : {meta.duration_s:.2f}s ({meta.frame_count} total frames in stream)",
        f"Codec (FourCC)    : {meta.fourcc or 'N/A'}",
        "-" * 70,
        f"Execution Mode    : {mode}",
        f"Frames Analysed   : {q.frames_analysed}",
        f"Hand Detection    : {q.hand_detection_rate:.1%}" if q.hand_detection_rate is not None else "Hand Detection    : N/A",
        f"Pose Detection    : {q.pose_detection_rate:.1%}" if q.pose_detection_rate is not None else "Pose Detection    : N/A",
        f"Tracking Status   : {status_str}",
        f"Quality Notes     : {notes_str}",
    ]

    if npz_path and json_path:
        lines.extend([
            "-" * 70,
            f"Exported NPZ      : {npz_path}",
            f"Exported JSON     : {json_path}",
        ])

    lines.append("=" * 70)
    lines.append("")
    return "\n".join(lines)


def probe_video(
    video_path: str | Path,
    out_path: str | Path | None = None,
    stride: int = 1,
    max_frames: int | None = None,
    mock: bool = False,
    hand_model: str | Path | None = None,
    pose_model: str | Path | None = None,
    verbose: bool = True,
) -> ProcessedSequence:
    """Process a video file, display diagnostics, and optionally export NPZ/JSON.

    Args:
        video_path: Path to input video file.
        out_path: Optional output directory or file path for NPZ/JSON export.
        stride: Process every Nth frame.
        max_frames: Maximum number of frames to analyze.
        mock: If True, uses mock backends (no MediaPipe model files required).
        hand_model: Optional path to hand_landmarker.task.
        pose_model: Optional path to pose_landmarker.task.
        verbose: If True, prints report to stdout.

    Returns:
        The ProcessedSequence object.
    """
    v_path = Path(video_path).resolve()
    if not v_path.is_file():
        raise FileNotFoundError(f"Video file not found: {v_path}")

    mode_label = "MOCK (Synthetic / Offline)" if mock else "REAL (MediaPipe Tasks)"

    if mock:
        pipeline = VisionPipeline(
            hand_backend=MockHandBackend(),
            pose_backend=MockPoseBackend(),
        )
    else:
        pipeline = VisionPipeline(
            hand_model_path=hand_model,
            pose_model_path=pose_model,
        )

    with pipeline:
        sequence = pipeline.process_video(v_path, stride=stride, max_frames=max_frames)

    npz_out: Path | None = None
    json_out: Path | None = None

    if out_path is not None:
        target = Path(out_path).resolve()
        if target.is_dir() or target.suffix == "":
            target.mkdir(parents=True, exist_ok=True)
            export_target = target / f"{v_path.stem}_sequence.npz"
        else:
            export_target = target
        npz_out, json_out = export_sequence(sequence, export_target)

    if verbose:
        report = format_report(sequence, mode=mode_label, npz_path=npz_out, json_path=json_out)
        print(report)

    return sequence


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m vision.probe_video",
        description="Probe a video file, extract 260-dim dance features, and export sequences.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--video", "-v",
        required=True,
        type=Path,
        help="Path to the input video file (.mp4, .avi, .webm, etc.).",
    )
    parser.add_argument(
        "--out", "-o",
        type=Path,
        default=None,
        help="Target output directory or .npz file path for exporting features and metadata.",
    )
    parser.add_argument(
        "--stride", "-s",
        type=int,
        default=1,
        help="Frame step size (default: 1, analyze every frame).",
    )
    parser.add_argument(
        "--max-frames", "-m",
        type=int,
        default=None,
        help="Optional maximum number of frames to process.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode using synthetic detectors (offline test without model assets).",
    )
    parser.add_argument(
        "--hand-model",
        type=Path,
        default=None,
        help="Explicit path to hand_landmarker.task model file.",
    )
    parser.add_argument(
        "--pose-model",
        type=Path,
        default=None,
        help="Explicit path to pose_landmarker.task model file.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        probe_video(
            video_path=args.video,
            out_path=args.out,
            stride=args.stride,
            max_frames=args.max_frames,
            mock=args.mock,
            hand_model=args.hand_model,
            pose_model=args.pose_model,
            verbose=True,
        )
        return 0
    except FileNotFoundError as err:
        sys.stderr.write(f"\n[ERROR] File not found:\n{err}\n\n")
        return 1
    except ValueError as err:
        sys.stderr.write(f"\n[ERROR] Invalid argument or video stream:\n{err}\n\n")
        return 2
    except Exception as err:
        sys.stderr.write(f"\n[FATAL] Video probing failed:\n{err}\n\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
