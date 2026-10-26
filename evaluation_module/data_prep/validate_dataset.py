"""Audit a folder-per-class image dataset against the backend mudra catalogue.

Example:
    python -m data_prep.validate_dataset --dataset data/mudra_dataset

The script never copies or modifies images. It writes a relative-path manifest and
reports missing catalogue classes; it does not assume the Kaggle dataset has 52 classes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOGUE = REPOSITORY_ROOT / "backend" / "data" / "seed" / "mudras.json"
DEFAULT_DATASET = Path(__file__).resolve().parents[1] / "data" / "mudra_dataset"
DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "data" / "mudra_dataset_manifest.json"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def normalize_label(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    return "".join(char for char in text if char.isalnum())


def load_label_map(catalogue_path: Path) -> tuple[dict[str, dict], list[dict]]:
    records = json.loads(catalogue_path.read_text(encoding="utf-8"))
    labels: dict[str, dict] = {}
    for record in records:
        for label in [record["name"], *record.get("alternate_names", [])]:
            key = normalize_label(label)
            previous = labels.get(key)
            if previous is not None and previous["id"] != record["id"]:
                raise ValueError(f"Ambiguous catalogue label {label!r}: {previous['id']} / {record['id']}")
            labels[key] = record
    return labels, records


def inspect_dataset(dataset_dir: Path, catalogue_path: Path = DEFAULT_CATALOGUE) -> dict:
    if not dataset_dir.is_dir():
        raise FileNotFoundError(f"Dataset directory does not exist: {dataset_dir}")
    label_map, catalogue = load_label_map(catalogue_path)
    files_by_class: dict[str, list[Path]] = defaultdict(list)
    unknown_labels: list[str] = []
    folder_map: dict[str, dict] = {}
    unsupported_files: list[str] = []

    for class_dir in sorted(p for p in dataset_dir.iterdir() if p.is_dir()):
        record = label_map.get(normalize_label(class_dir.name))
        if record is None:
            unknown_labels.append(class_dir.name)
            continue
        folder_map[class_dir.name] = {"mudra_id": record["id"], "canonical_name": record["name"]}
        for item in sorted(class_dir.rglob("*")):
            if not item.is_file():
                continue
            if item.suffix.casefold() not in IMAGE_EXTENSIONS:
                unsupported_files.append(item.relative_to(dataset_dir).as_posix())
                continue
            files_by_class[record["id"]].append(item)

    corrupt: list[str] = []
    duplicates: dict[str, list[str]] = defaultdict(list)
    class_counts = {record["id"]: {"name": record["name"], "images": 0, "valid_images": 0}
                    for record in catalogue}
    for mudra_id, paths in files_by_class.items():
        class_counts[mudra_id]["images"] = len(paths)
        for path in paths:
            relative = path.relative_to(dataset_dir).as_posix()
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            duplicates[digest].append(relative)
            image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            if image is None or image.size == 0:
                corrupt.append(relative)
            else:
                class_counts[mudra_id]["valid_images"] += 1

    duplicate_groups = [sorted(paths) for paths in duplicates.values() if len(paths) > 1]
    present = sorted(key for key, value in class_counts.items() if value["images"])
    missing = sorted(key for key, value in class_counts.items() if not value["images"])
    total = sum(value["images"] for value in class_counts.values())
    valid_total = sum(value["valid_images"] for value in class_counts.values())
    return {
        "dataset_source": "https://www.kaggle.com/datasets/geethikanambiar/mudra-dataset",
        "dataset_license": "unknown; inspect the Kaggle dataset license before redistribution or use",
        "dataset_directory": dataset_dir.name,
        "catalogue_count": len(catalogue),
        "class_folders": folder_map,
        "class_counts": class_counts,
        "classes_present": len(present),
        "mudra_ids_present": present,
        "missing_catalogue_mudra_ids": missing,
        "unknown_class_folders": unknown_labels,
        "image_count": total,
        "valid_image_count": valid_total,
        "corrupt_images": sorted(corrupt),
        "duplicate_content_groups": duplicate_groups,
        "unsupported_files": sorted(unsupported_files),
        "all_catalogue_classes_present": len(catalogue) == len(present) and not missing,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    parser.add_argument("--output", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    try:
        manifest = inspect_dataset(args.dataset, args.catalogue)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "catalogue_count": manifest["catalogue_count"],
        "classes_present": manifest["classes_present"],
        "image_count": manifest["image_count"],
        "valid_image_count": manifest["valid_image_count"],
        "unknown_class_folders": manifest["unknown_class_folders"],
        "missing_catalogue_class_count": len(manifest["missing_catalogue_mudra_ids"]),
        "manifest": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
