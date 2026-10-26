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
import json
import os
from collections import defaultdict
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

if __package__ and __package__.startswith("evaluation_module."):
    from ..mudra_mlp.catalogue import dataset_record
else:  # Support the documented module invocation from evaluation_module/.
    from mudra_mlp.catalogue import dataset_record

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
N_LANDMARKS = 21
PAD_FRACTION = 0.30


def coord_columns(prefix: str) -> list[str]:
    return [f"{prefix}_{axis}{i}" for i in range(N_LANDMARKS) for axis in "xyz"]


HEADER = (
    ["label", "mudra_id", "dataset_folder", "variant_id", "file", "md5", "phash",
     "width", "height", "padded", "n_hands"]
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
        # Request CPU explicitly; some MediaPipe builds still require a native GPU
        # service internally, in which case this host must fail clearly at startup.
        base_options=mp_python.BaseOptions(
            model_asset_path=str(model_path), delegate=mp_python.BaseOptions.Delegate.CPU
        ),
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


def perceptual_hash(bgr) -> str:
    """64-bit DCT perceptual hash used to keep near-identical photos in one split group."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    low = cv2.dct(small)[:8, :8]
    values = low.flatten()
    median = float(np.median(values[1:]))
    return "".join("1" if value > median else "0" for value in values)


def build_row(label, mudra_id, dataset_folder, variant_id, path, md5, phash, width, height, padded, hands):
    row = [label, mudra_id, dataset_folder, variant_id or "", path.name, md5, phash,
           width, height, padded, len(hands)]
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
    unknown = [p.name for p in class_dirs if dataset_record(p.name) is None]
    if unknown:
        raise ValueError(
            "unknown dataset class folders: " + ", ".join(unknown)
            + "; add an exact reviewed folder mapping to backend/data/seed/dataset_mapping.json"
        )
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        for class_dir in class_dirs:
            record, mapping = dataset_record(class_dir.name)
            label, mudra_id = record["name"], record["id"]
            variant_id = mapping.get("variant_id")
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
                phash = perceptual_hash(bgr)
                hands, w, h, padded = process_image(landmarker, bgr)
                if hands:
                    per_class[label][1] += 1
                else:
                    no_hand.append((label, path.name))
                writer.writerow(build_row(label, mudra_id, class_dir.name, variant_id,
                                          path, md5, phash, w, h, padded, hands))

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
    parser.add_argument("--dataset", type=Path, default=None, help="folder that contains one sub-folder per class; defaults to NRITYAGURU_DATASET_DIR or the local development cache")
    parser.add_argument("--model", required=True, type=Path, help="path to hand_landmarker.task")
    parser.add_argument("--out", required=True, type=Path, help="output CSV path")
    parser.add_argument("--min-conf", type=float, default=0.3)
    args = parser.parse_args()
    if not args.model.exists():
        raise SystemExit(f"Model file not found: {args.model}")
    mapping_path = Path(__file__).resolve().parents[2] / "backend" / "data" / "seed" / "dataset_mapping.json"
    mapping_doc = json.loads(mapping_path.read_text(encoding="utf-8"))
    default_dataset = Path(mapping_doc["dataset"]["local_development_default"])
    if not default_dataset.is_dir():
        default_dataset = Path(__file__).resolve().parents[1] / "data" / "mudra_dataset"
    dataset = args.dataset or Path(os.environ.get("NRITYAGURU_DATASET_DIR", str(default_dataset)))
    if not dataset.is_dir():
        raise SystemExit(f"Dataset folder not found: {dataset}; set NRITYAGURU_DATASET_DIR or pass --dataset")
    landmarker = make_landmarker(args.model, args.min_conf)
    failed = args.out.with_name(args.out.stem + "_failed.csv")
    summary = run(dataset, landmarker, args.out, failed)
    print_summary(summary)
    print(f"\nSaved: {args.out}\nImages without a detected hand: {failed}")


if __name__ == "__main__":
    main()
