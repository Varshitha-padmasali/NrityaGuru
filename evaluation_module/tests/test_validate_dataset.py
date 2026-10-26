import json

import numpy as np

from data_prep import validate_dataset


def test_manifest_uses_exact_mapping_counts_duplicates_and_dims(tmp_path, monkeypatch):
    dataset = tmp_path / "dataset"
    folder = dataset / "Pathaka(1)"
    folder.mkdir(parents=True)
    (folder / "a.jpg").write_bytes(b"same-image-bytes")
    (folder / "b.jpg").write_bytes(b"same-image-bytes")
    monkeypatch.setattr(validate_dataset.cv2, "imdecode", lambda *_: np.ones((3, 7, 3), dtype=np.uint8))
    rows = tmp_path / "files.jsonl"

    report = validate_dataset.inspect_dataset(dataset, files_manifest=rows)

    assert report["catalogue_count"] == 52
    assert report["observed_folder_count"] == 1
    assert report["distinct_canonical_labels_with_images"] == 1
    assert report["folder_counts"]["Pathaka(1)"]["mudra_id"] == "mudra_pataka"
    assert report["folder_counts"]["Pathaka(1)"]["valid_images"] == 2
    assert report["exact_duplicate_group_count"] == 1
    assert report["exact_duplicate_file_count"] == 2
    entries = [json.loads(line) for line in rows.read_text().splitlines()]
    assert entries[0]["canonical_label"] == "mudra_pataka"
    assert (entries[0]["width"], entries[0]["height"]) == (7, 3)
    assert entries[0]["path"] == "Pathaka(1)/a.jpg"


def test_manifest_reports_unmapped_corrupt_and_unsupported(tmp_path, monkeypatch):
    dataset = tmp_path / "dataset"
    (dataset / "unknown-class").mkdir(parents=True)
    known = dataset / "Mushti(1)"
    known.mkdir()
    (known / "broken.png").write_bytes(b"broken")
    (known / "notes.txt").write_text("not an image")
    monkeypatch.setattr(validate_dataset.cv2, "imdecode", lambda *_: None)

    report = validate_dataset.inspect_dataset(dataset)

    assert report["unknown_class_folders"] == ["unknown-class"]
    assert report["corrupt_or_unreadable_images"] == ["Mushti(1)/broken.png"]
    assert report["unsupported_files"] == ["Mushti(1)/notes.txt"]
    assert report["folder_counts"]["Mushti(1)"]["valid_images"] == 0


def test_katakamukha_variants_keep_distinct_source_labels_and_one_root_id():
    folder_map, _ = validate_dataset.load_mapping(validate_dataset.DEFAULT_MAPPING)
    variants = [folder_map[f"Katakamukha_{index}"] for index in range(1, 4)]
    assert [row["dataset_folder"] for row in variants] == ["Katakamukha_1", "Katakamukha_2", "Katakamukha_3"]
    assert {row["variant_id"] for row in variants} == {"katakamukha_1", "katakamukha_2", "katakamukha_3"}
    assert {row["mudra_id"] for row in variants} == {"mudra_katakamukha"}
