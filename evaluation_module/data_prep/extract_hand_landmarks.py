"""Extract hand landmarks from a folder-per-class image dataset with MediaPipe HandLandmarker.

Usage (from the evaluation_module folder):

    python -m data_prep.extract_hand_landmarks --dataset "<dataset folder>" --model hand_landmarker.task --out data\\hand_landmarks.csv

Output CSV, one row per image:
    label, file, md5, width, height, padded, n_hands,
    h0_side, h0_score, h0_x0, h0_y0, h0_z0, ... h0_z20     (best-scoring hand)
    h1_side, h1_score, h1_x0, ... h1_z20                   (second hand, if any)

Coordinates are in PIXEL units (x*width, y*height, z*width) so that the geometry is not
distorted by the image aspect ratio. Normalise (wrist-relative, divide by hand size) later.
Missing hands are left EMPTY (not zero), so they cannot be mistaken for real measurements.
Handedness labels from still images can be swapped (MediaPipe assumes a mirrored selfie image),
so do not rely on h*_side as ground truth.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
N_LANDMARKS = 21
PAD_FRACTION = 0.30


def coord_columns(prefix: str) -> list[str]:
    return [f"{prefix}_{axis}{i}" for i in range(N_LANDMARKS) for axis in "xyz"]


HEADER = (
    ["label", "file", "md5", "width", "height", "padded", "n_hands"]
    + ["h0_side", "h0_score"] + coord_columns("h0")
    + ["h1_side", "h1_score"] + coord_columns("h1")
)


def read_image(path: Path):
    """Read an image as BGR. Uses np.fromfile so Windows paths with odd characters work."""
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def make_landmarker(model_path: Path, min_conf: float = 0.3):
    options = vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.IMAGE,
        num_hands=2,
        min_hand_detection_confidence=min_conf,
        min_hand_presence_confidence=min_conf,
        min_tracking_confidence=min_conf,
    )
    return vision.HandLandmarker.create_from_options(options)


def detect(landmarker, bgr):
    rgb = np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    return landmarker.detect(mp_image)


def hands_from_result(result, width: int, height: int):
    """Return [(score, side, flat_coords_63)] sorted by handedness score, best first."""
    hands = []
    for landmarks, handedness in zip(result.hand_landmarks, result.handedness):
        coords = np.array(
            [[lm.x * width, lm.y * height, lm.z * width] for lm in landmarks], dtype=float
        ).reshape(-1)
        category = handedness[0]
        hands.append((float(category.score), str(category.category_name), coords))
    hands.sort(key=lambda t: -t[0])
    return hands


def pad_image(bgr):
    h, w = bgr.shape[:2]
    p = int(max(h, w) * PAD_FRACTION)
    return cv2.copyMakeBorder(bgr, p, p, p, p, cv2.BORDER_REPLICATE)


def process_image(landmarker, bgr):
    """Try the image as-is, then with a border (helps when the hand fills the frame)."""
    h, w = bgr.shape[:2]
    hands = hands_from_result(detect(landmarker, bgr), w, h)
    if hands:
        return hands, w, h, 0
    padded = pad_image(bgr)
    ph, pw = padded.shape[:2]
    hands = hands_from_result(detect(landmarker, padded), pw, ph)
    return hands, pw, ph, 1


def build_row(label, path, md5, width, height, padded, hands):
    row = [label, path.name, md5, width, height, padded, len(hands)]
    for k in range(2):
        if k < len(hands):
            score, side, coords = hands[k]
            row += [side, f"{score:.4f}"] + [f"{v:.4f}" for v in coords]
        else:
            row += [""] * (2 + 3 * N_LANDMARKS)
    return row


def run(dataset: Path, landmarker, out_csv: Path, failed_csv: Path | None = None) -> dict:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    per_class = defaultdict(lambda: [0, 0])  # label -> [images, with_hand]
    seen_md5: dict[str, str] = {}
    duplicates = 0
    unreadable: list[str] = []
    no_hand: list[tuple[str, str]] = []

    class_dirs = sorted(p for p in dataset.iterdir() if p.is_dir())
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        for class_dir in class_dirs:
            label = class_dir.name
            files = sorted(p for p in class_dir.rglob("*") if p.suffix.lower() in IMAGE_EXTS)
            for path in files:
                per_class[label][0] += 1
                md5 = hashlib.md5(path.read_bytes()).hexdigest()
                if md5 in seen_md5:
                    duplicates += 1
                seen_md5.setdefault(md5, f"{label}/{path.name}")
                bgr = read_image(path)
                if bgr is None:
                    unreadable.append(str(path))
                    continue
                hands, w, h, padded = process_image(landmarker, bgr)
                if hands:
                    per_class[label][1] += 1
                else:
                    no_hand.append((label, path.name))
                writer.writerow(build_row(label, path, md5, w, h, padded, hands))

    if failed_csv is not None:
        with open(failed_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["label", "file"])
            writer.writerows(no_hand)
            for p in unreadable:
                writer.writerow(["UNREADABLE", p])

    total = sum(v[0] for v in per_class.values())
    detected = sum(v[1] for v in per_class.values())
    return {
        "total_images": total,
        "with_hand": detected,
        "unreadable": len(unreadable),
        "exact_duplicates": duplicates,
        "per_class": {k: tuple(v) for k, v in per_class.items()},
    }


def print_summary(summary: dict) -> None:
    total, ok = summary["total_images"], summary["with_hand"]
    rate = 100.0 * ok / total if total else 0.0
    print(f"\nImages: {total} | hand detected: {ok} ({rate:.1f}%) | "
          f"unreadable: {summary['unreadable']} | exact duplicate files: {summary['exact_duplicates']}")
    print(f"\n{'class':<22}{'images':>8}{'detected':>10}{'rate':>8}")
    for label, (n, d) in sorted(summary["per_class"].items(), key=lambda kv: kv[1][1] / max(kv[1][0], 1)):
        print(f"{label:<22}{n:>8}{d:>10}{(100.0 * d / n if n else 0.0):>7.0f}%")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--dataset", required=True, type=Path, help="folder that contains one sub-folder per class")
    parser.add_argument("--model", required=True, type=Path, help="path to hand_landmarker.task")
    parser.add_argument("--out", required=True, type=Path, help="output CSV path")
    parser.add_argument("--min-conf", type=float, default=0.3)
    args = parser.parse_args()
    if not args.model.exists():
        raise SystemExit(f"Model file not found: {args.model}")
    if not args.dataset.is_dir():
        raise SystemExit(f"Dataset folder not found: {args.dataset}")
    landmarker = make_landmarker(args.model, args.min_conf)
    failed = args.out.with_name(args.out.stem + "_failed.csv")
    summary = run(args.dataset, landmarker, args.out, failed)
    print_summary(summary)
    print(f"\nSaved: {args.out}\nImages without a detected hand: {failed}")


if __name__ == "__main__":
    main()