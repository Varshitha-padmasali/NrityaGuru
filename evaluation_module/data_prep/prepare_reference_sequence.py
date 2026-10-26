"""Convert a consented reference performance video to a candidate sequence JSON.

This tool never marks recordings teacher-verified. Review the candidate with a
qualified Bharatanatyam teacher, then ingest it through the protected backend
reference-sequence endpoint. The source video is not copied or retained.

Run from the repository root, under a compatible MediaPipe environment:
  python -m evaluation_module.data_prep.prepare_reference_sequence \
    --video ./teacher-recording.mp4 --task ./hand_landmarker.task \
    --mudra-id mudra_pataka --source "consented teacher studio recording" \
    --consent-reference CONSENT-RECORD-001 --out ./candidate-reference.json
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import tempfile
import os

import cv2

if __package__ and __package__.startswith("evaluation_module."):
    from .extract_hand_landmarks import make_landmarker, process_image
    from ..mudra_mlp.features import FEATURE_SCHEMA_VERSION, FeatureError, hand_features
else:
    from .extract_hand_landmarks import make_landmarker, process_image
    from mudra_mlp.features import FEATURE_SCHEMA_VERSION, FeatureError, hand_features


def build_candidate(*, reference_id: str, target_id: str, source: str,
                    consent_reference: str, frames: list[list[float]],
                    evaluator_version: str = "0.2-prototype") -> dict:
    if not reference_id.strip() or not target_id.strip():
        raise ValueError("reference_id and target_id are required")
    if not source.strip() or not consent_reference.strip():
        raise ValueError("source and consent_reference are required")
    if not frames:
        raise ValueError("no usable hand frames were extracted")
    if len(frames) > 600:
        raise ValueError("candidate sequence exceeds the 600-frame schema limit")
    if any(len(frame) != 78 or any(not math.isfinite(value) for value in frame) for frame in frames):
        raise ValueError("each extracted frame must contain 78 finite hand-v1 features")
    return {
        "schema_version": 1,
        "id": reference_id,
        "mudra_id": target_id,
        "feature_schema": FEATURE_SCHEMA_VERSION,
        "evaluator_version": evaluator_version,
        "normalization": "wrist_relative_hand_scale",
        "feature_dimensions": 78,
        "frames": frames,
        "source": source,
        "performer_consent_reference": consent_reference,
        "review_status": "candidate",
    }


def extract_candidate(video: Path, task: Path, target_id: str, source: str,
                      consent_reference: str, output: Path, reference_id: str,
                      sample_fps: float = 5.0) -> dict:
    if not video.is_file():
        raise FileNotFoundError(f"video not found: {video}")
    if not task.is_file():
        raise FileNotFoundError(f"MediaPipe task file not found: {task}")
    if not (0 < sample_fps <= 15):
        raise ValueError("sample_fps must be greater than 0 and at most 15")
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        capture.release()
        raise ValueError("video could not be opened")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    declared_frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if (not math.isfinite(fps) or not math.isfinite(declared_frames) or fps <= 0
            or fps > 120 or declared_frames <= 0 or declared_frames > 120 * fps
            or declared_frames / fps > 120):
        capture.release()
        raise ValueError("video must have valid frame metadata and be no longer than 120 seconds")
    interval = max(1, round(fps / sample_fps))
    frames: list[list[float]] = []
    decoded = 0
    landmarker = make_landmarker(task)
    try:
        while True:
            ok, bgr = capture.read()
            if not ok:
                break
            if bgr.shape[1] * bgr.shape[0] > 1920 * 1080:
                raise ValueError("video frame exceeds 1920x1080 pixels")
            if decoded % interval == 0:
                hands, _, _, _ = process_image(landmarker, bgr)
                if hands:
                    try:
                        frames.append(hand_features(hands[0][2]).astype(float).tolist())
                    except FeatureError:
                        pass
                if len(frames) > 600:
                    raise ValueError("video produces more than 600 sampled reference frames")
            decoded += 1
    finally:
        capture.release()
        landmarker.close()
    if not frames:
        raise ValueError("no usable hand landmarks were detected")
    candidate = build_candidate(
        reference_id=reference_id,
        target_id=target_id,
        source=source,
        consent_reference=consent_reference,
        frames=frames,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent,
                                     prefix=f".{output.name}.", suffix=".tmp", delete=False) as f:
        temp_path = Path(f.name)
        json.dump(candidate, f, allow_nan=False, separators=(",", ":"))
        f.write("\n")
    os.replace(temp_path, output)
    return {"output": str(output), "decoded_frames": decoded, "landmark_frames": len(frames),
            "source_fps": fps, "status": "candidate_requires_teacher_review"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--mudra-id", required=True)
    parser.add_argument("--reference-id", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--consent-reference", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sample-fps", type=float, default=5.0)
    args = parser.parse_args()
    try:
        summary = extract_candidate(args.video, args.task, args.mudra_id, args.source,
                                    args.consent_reference, args.out, args.reference_id,
                                    args.sample_fps)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
