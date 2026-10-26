"""Validate the downloaded folder-per-class dataset without loading it all into memory.

The source-folder crosswalk lives in ``backend/data/seed/dataset_mapping.json``.
The scanner writes a JSON summary and a JSONL row per image. Unsupported files,
unmapped folders, corrupt images and exact duplicates are kept in the report.

Run from the repository root, or pass ``--dataset`` on another machine:
    python -m evaluation_module.data_prep.validate_dataset --update-mapping
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAPPING = REPOSITORY_ROOT / "backend" / "data" / "seed" / "dataset_mapping.json"
DEFAULT_DATASET = Path(
    os.environ.get(
        "NRITYAGURU_DATASET_DIR",
        "/Users/varshithapadmasali/.cache/kagglehub/datasets/onkarpathrikar/"
        "bharatanatyam-mudra-dataset-master-bm/versions/1/"
        "Bharatanatyam-Mudra-Dataset-master",
    )
)
DEFAULT_MANIFEST = REPOSITORY_ROOT / "evaluation_module" / "data" / "dataset_manifest.json"
DEFAULT_FILES = REPOSITORY_ROOT / "evaluation_module" / "data" / "dataset_files.jsonl"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def load_mapping(path: Path) -> tuple[dict[str, dict], dict]:
    mapping = json.loads(path.read_text(encoding="utf-8"))
    folders: dict[str, dict] = {}
    ids: set[str] = set()
    for row in mapping["class_folders"]:
        label = row["dataset_folder"]
        if label in folders:
            raise ValueError(f"duplicate dataset folder mapping: {label}")
        if not row.get("mudra_id") or not row.get("training_label"):
            raise ValueError(f"incomplete mapping for {label}")
        folders[label] = row
        ids.add(row["mudra_id"])
    return folders, mapping


def inspect_dataset(
    dataset_dir: Path,
    mapping_path: Path = DEFAULT_MAPPING,
    files_manifest: Path | None = None,
) -> dict:
    if not dataset_dir.is_dir():
        raise FileNotFoundError(f"Dataset directory does not exist: {dataset_dir}")
    folder_map, mapping_doc = load_mapping(mapping_path)
    found_dirs = sorted(path for path in dataset_dir.iterdir() if path.is_dir())
    unknown = sorted(path.name for path in found_dirs if path.name not in folder_map)
    absent = sorted(set(folder_map) - {path.name for path in found_dirs})
    per_folder: dict[str, dict] = {}
    per_canonical: dict[str, dict] = defaultdict(lambda: {"folders": [], "images": 0, "valid_images": 0})
    corrupt: list[str] = []
    unsupported: list[str] = []
    hashes: dict[str, list[str]] = defaultdict(list)
    file_count = 0

    output = None
    try:
        if files_manifest is not None:
            files_manifest.parent.mkdir(parents=True, exist_ok=True)
            output = files_manifest.open("w", encoding="utf-8")
        for class_dir in found_dirs:
            row = folder_map.get(class_dir.name)
            if row is None:
                # Do not read unknown classes into the training manifest.
                continue
            folder_result = {"mudra_id": row["mudra_id"], "original_label": row["original_label"],
                             "variant_id": row.get("variant_id"), "images": 0, "valid_images": 0}
            for path in sorted(p for p in class_dir.rglob("*") if p.is_file()):
                relative = path.relative_to(dataset_dir).as_posix()
                if path.suffix.casefold() not in IMAGE_EXTENSIONS:
                    unsupported.append(relative)
                    continue
                raw = path.read_bytes()
                digest = hashlib.sha256(raw).hexdigest()
                hashes[digest].append(relative)
                image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
                height, width = (image.shape[:2] if image is not None and image.size else (None, None))
                valid = width is not None and height is not None and width > 0 and height > 0
                file_count += 1
                folder_result["images"] += 1
                canonical = per_canonical[row["mudra_id"]]
                canonical["images"] += 1
                if valid:
                    folder_result["valid_images"] += 1
                    canonical["valid_images"] += 1
                else:
                    corrupt.append(relative)
                if output is not None:
                    output.write(json.dumps({
                        "path": relative,
                        "dataset_folder": class_dir.name,
                        "original_label": row["original_label"],
                        "mudra_id": row["mudra_id"],
                        "canonical_label": row["training_label"],
                        "variant_id": row.get("variant_id"),
                        "sha256": digest,
                        "width": width,
                        "height": height,
                        "valid_image": valid,
                    }, ensure_ascii=False) + "\n")
            per_folder[class_dir.name] = folder_result
            per_canonical[row["mudra_id"]]["folders"].append(class_dir.name)
    finally:
        if output is not None:
            output.close()

    duplicate_groups = [sorted(paths) for paths in hashes.values() if len(paths) > 1]
    records = json.loads((REPOSITORY_ROOT / "backend" / "data" / "seed" / "mudras.json").read_text(encoding="utf-8"))
    catalog_ids = {row["id"] for row in records}
    dangling = sorted({row["mudra_id"] for row in folder_map.values()} - catalog_ids)
    missing_model_classes = sorted(row["id"] for row in records
                                   if row["category"] == "Asamyuta Hasta"
                                   and row["id"] not in per_canonical)
    return {
        "dataset": mapping_doc["dataset"],
        "dataset_directory": dataset_dir.name,
        "catalogue_count": len(records),
        "mapped_folder_count": len(found_dirs) - len(unknown),
        "observed_folder_count": len(found_dirs),
        "folder_counts": per_folder,
        "canonical_counts": dict(sorted(per_canonical.items())),
        "distinct_canonical_labels_with_images": len(per_canonical),
        "image_count": file_count,
        "valid_image_count": sum(v["valid_images"] for v in per_folder.values()),
        "unknown_class_folders": unknown,
        "missing_mapped_folders": absent,
        "unknown_mudra_ids_in_mapping": dangling,
        "missing_asamyuta_model_classes": missing_model_classes,
        "corrupt_or_unreadable_images": sorted(corrupt),
        "exact_duplicate_group_count": len(duplicate_groups),
        "exact_duplicate_file_count": sum(map(len, duplicate_groups)),
        "extra_exact_duplicate_copies": sum(len(paths) - 1 for paths in duplicate_groups),
        "unsupported_files": sorted(unsupported),
        "file_manifest": files_manifest.name if files_manifest else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--output", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--files-output", type=Path, default=DEFAULT_FILES)
    parser.add_argument("--no-files-manifest", action="store_true")
    parser.add_argument("--update-mapping", action="store_true", help="refresh recorded per-folder image counts")
    parser.add_argument("--require-all", action="store_true", help="exit nonzero for unknown or absent mapped folders")
    args = parser.parse_args()
    try:
        report = inspect_dataset(args.dataset, args.mapping, None if args.no_files_manifest else args.files_output)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.update_mapping:
        mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
        mapping["dataset"]["observed_folder_count"] = report["observed_folder_count"]
        mapping["dataset"]["observed_image_count"] = report["image_count"]
        for row in mapping["class_folders"]:
            row["image_count"] = report["folder_counts"].get(row["dataset_folder"], {}).get("images", 0)
        args.mapping.write_text(json.dumps(mapping, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "catalogue_count", "observed_folder_count", "distinct_canonical_labels_with_images",
        "image_count", "valid_image_count", "unknown_class_folders", "missing_mapped_folders",
        "corrupt_or_unreadable_images", "exact_duplicate_group_count", "exact_duplicate_file_count",
        "extra_exact_duplicate_copies", "unsupported_files",
    )}, indent=2))
    if args.require_all and (report["unknown_class_folders"] or report["missing_mapped_folders"]
                             or report["unknown_mudra_ids_in_mapping"]):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
