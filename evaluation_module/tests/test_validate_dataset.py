import numpy as np

from data_prep import validate_dataset


def test_manifest_maps_canonical_label_and_reports_missing_and_duplicates(tmp_path, monkeypatch):
    dataset = tmp_path / "dataset"
    label = dataset / "pataka"
    label.mkdir(parents=True)
    (label / "a.jpg").write_bytes(b"same-image-bytes")
    (label / "b.jpg").write_bytes(b"same-image-bytes")
    monkeypatch.setattr(validate_dataset.cv2, "imdecode", lambda *_: np.ones((2, 2), dtype=np.uint8))

    report = validate_dataset.inspect_dataset(dataset)

    assert report["catalogue_count"] == 52
    assert report["classes_present"] == 1
    assert report["all_catalogue_classes_present"] is False
    assert report["class_folders"]["pataka"] == {"mudra_id": "mudra_pataka", "canonical_name": "Pataka"}
    assert report["class_counts"]["mudra_pataka"]["valid_images"] == 2
    assert report["duplicate_content_groups"] == [["pataka/a.jpg", "pataka/b.jpg"]]
    assert len(report["missing_catalogue_mudra_ids"]) == 51


def test_manifest_reports_unknown_labels_and_corrupt_images(tmp_path, monkeypatch):
    dataset = tmp_path / "dataset"
    (dataset / "unknown-class").mkdir(parents=True)
    known = dataset / "Pataka"
    known.mkdir()
    (known / "broken.png").write_bytes(b"broken")
    monkeypatch.setattr(validate_dataset.cv2, "imdecode", lambda *_: None)

    report = validate_dataset.inspect_dataset(dataset)

    assert report["unknown_class_folders"] == ["unknown-class"]
    assert report["corrupt_images"] == ["Pataka/broken.png"]
    assert report["class_counts"]["mudra_pataka"]["valid_images"] == 0
