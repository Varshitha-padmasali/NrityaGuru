"""Label mapping helpers backed by the backend's canonical seed catalogue."""
from __future__ import annotations

import hashlib
import json
import unicodedata
from functools import lru_cache
from pathlib import Path

CATALOGUE_PATH = Path(__file__).resolve().parents[2] / "backend" / "data" / "seed" / "mudras.json"


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


def catalogue_digest() -> str:
    records, _ = catalogue()
    stable = json.dumps(records, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def asamyuta_names() -> list[str]:
    records, _ = catalogue()
    return [record["name"] for record in records if record["category"] == "Asamyuta Hasta"]
