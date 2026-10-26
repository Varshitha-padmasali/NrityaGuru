"""Label mapping helpers backed by the backend's canonical seed catalogue."""
from __future__ import annotations

import hashlib
import json
import unicodedata
from functools import lru_cache
from pathlib import Path

CATALOGUE_PATH = Path(__file__).resolve().parents[2] / "backend" / "data" / "seed" / "mudras.json"
DATASET_MAPPING_PATH = CATALOGUE_PATH.with_name("dataset_mapping.json")


def normalize_label(label: str) -> str:
    text = unicodedata.normalize("NFKC", label).casefold()
    return "".join(char for char in text if char.isalnum())


@lru_cache(maxsize=1)
def catalogue() -> tuple[list[dict], dict[str, dict]]:
    records = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))
    labels: dict[str, dict] = {}
    for record in records:
        for label in [record["name"], *record.get("alternate_names", [])]:
            key = normalize_label(label)
            previous = labels.get(key)
            if previous is not None and previous["id"] != record["id"]:
                raise ValueError(f"Ambiguous mudra class label {label!r}")
            labels[key] = record
    return records, labels


def canonical_record(label: str) -> dict | None:
    return catalogue()[1].get(normalize_label(label))


@lru_cache(maxsize=1)
def dataset_folders() -> dict[str, dict]:
    """Return exact source-folder mappings; do not fuzzy-match unknown labels."""
    document = json.loads(DATASET_MAPPING_PATH.read_text(encoding="utf-8"))
    return {row["dataset_folder"]: row for row in document["class_folders"]}


def dataset_record(folder: str) -> tuple[dict, dict] | None:
    """Return (canonical catalogue record, source mapping) for an exact folder label."""
    mapping = dataset_folders().get(folder)
    if mapping is None:
        return None
    record = next((item for item in catalogue()[0] if item["id"] == mapping["mudra_id"]), None)
    if record is None:
        raise ValueError(f"dataset folder {folder!r} points to unknown mudra id {mapping['mudra_id']!r}")
    return record, mapping


def catalogue_digest() -> str:
    records, _ = catalogue()
    stable = json.dumps(records, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def dataset_mapping_digest() -> str:
    stable = json.dumps(dataset_folders(), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def model_class_mapping(class_names: list[str]) -> dict[str, dict]:
    records = {row["name"]: row for row in catalogue()[0]}
    folders: dict[str, list[str]] = {}
    for folder, row in dataset_folders().items():
        folders.setdefault(row["mudra_id"], []).append(folder)
    result = {}
    for label in class_names:
        record = records.get(label)
        if record is None:
            continue
        result[label] = {"mudra_id": record["id"], "category": record["category"],
                         "dataset_folders": sorted(folders.get(record["id"], []))}
    return result


def asamyuta_names() -> list[str]:
    records, _ = catalogue()
    return [record["name"] for record in records if record["category"] == "Asamyuta Hasta"]
