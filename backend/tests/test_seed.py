import json
import shutil
from pathlib import Path

import pytest

from app.db.seed import (
    DEFAULT_SEED_DIR,
    SeedValidationError,
    load_seed,
    read_seed,
    validate_seed,
)
from app.repositories import knowledge_repository as repo


def test_real_seed_files_are_valid():
    bundle = read_seed()
    validate_seed(bundle)  # raises if anything is inconsistent
    assert len(bundle.sources) == 4
    assert len(bundle.mudras) == 52
    assert len({mudra.id for mudra in bundle.mudras}) == 52
    assert len({mudra.name.casefold() for mudra in bundle.mudras}) == 52
    assert len(bundle.movements) == 0  # nothing verified yet; none invented
    assert len(bundle.mappings) == 398
    assert len({mapping.id for mapping in bundle.mappings}) == 398
    assert all(mapping.source_id for mapping in bundle.mappings)


def test_52_record_catalogue_audit_coverage_is_explicit():
    bundle = read_seed()
    assert sum(m.category == "Asamyuta Hasta" for m in bundle.mudras) == 28
    assert sum(m.category == "Samyuta Hasta" for m in bundle.mudras) == 24
    assert {m.verification_status.value for m in bundle.mudras} == {"source_cited"}
    assert sum(bool(m.meaning) for m in bundle.mudras) == 49
    assert sum(bool(m.usage) for m in bundle.mudras) == 52
    assert sum(bool(m.description) for m in bundle.mudras) == 51
    assert sum(bool(m.practice_instructions) for m in bundle.mudras) == 0
    assert sum(bool(m.reference_image_path) for m in bundle.mudras) == 50
    assert {mapping.mudra_id for mapping in bundle.mappings} >= {
        "mudra_pataka", "mudra_tripataka", "mudra_ardhapataka", "mudra_allapadma"
    }


def test_dataset_crosswalk_maps_observed_folders_without_collapsing_variants():
    mapping_path = DEFAULT_SEED_DIR / "dataset_mapping.json"
    document = json.loads(mapping_path.read_text(encoding="utf-8"))
    rows = document["class_folders"]
    catalogue_ids = {mudra.id for mudra in read_seed().mudras}
    assert len(rows) == 50
    assert len({row["dataset_folder"] for row in rows}) == 50
    assert len({row["mudra_id"] for row in rows}) == 48
    assert sum(row["image_count"] for row in rows) == 28_431
    assert all(row["mudra_id"] in catalogue_ids for row in rows)
    variants = [row for row in rows if row["dataset_folder"].startswith("Katakamukha_")]
    assert {row["dataset_folder"] for row in variants} == {"Katakamukha_1", "Katakamukha_2", "Katakamukha_3"}
    assert {row["variant_id"] for row in variants} == {"katakamukha_1", "katakamukha_2", "katakamukha_3"}
    assert {row["mudra_id"] for row in variants} == {"mudra_katakamukha"}


def test_load_seed_is_idempotent(db_session):
    first = load_seed(db_session)
    second = load_seed(db_session)
    assert first == second
    assert len(repo.list_mudras(db_session, include_unverified=True)) == 52


def test_direct_repository_calls_remain_verified_only(db_session):
    load_seed(db_session)
    assert repo.list_mudras(db_session) == []
    assert repo.get_mappings_for_concept(db_session, "river") == []
    pataka = repo.get_mudra(db_session, "mudra_pataka", include_unverified=True)
    assert pataka.source.source_name.startswith("The Mirror of Gesture")
    assert pataka.practice_instructions is None  # not invented


def test_seeded_mapping_visible_with_flag(db_session):
    load_seed(db_session)
    found = repo.get_mappings_for_concept(db_session, "River", include_unverified=True)
    assert [m.mudra_id for m in found] == ["mudra_pataka"]


@pytest.fixture
def seed_copy(tmp_path):
    dest = tmp_path / "seed"
    shutil.copytree(DEFAULT_SEED_DIR, dest)
    return dest


def _edit(path: Path, fn):
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_rejects_unknown_source_id(seed_copy, tmp_path):
    _edit(seed_copy / "mudras.json", lambda d: d[0].update(source_id="nope"))
    with pytest.raises(SeedValidationError, match="unknown source_id"):
        validate_seed(read_seed(seed_copy), tmp_path)


def test_rejects_cited_status_without_source(seed_copy, tmp_path):
    _edit(seed_copy / "mudras.json", lambda d: d[0].update(source_id=None))
    with pytest.raises(SeedValidationError, match="requires a source_id"):
        validate_seed(read_seed(seed_copy), tmp_path)


def test_rejects_mapping_to_missing_mudra(seed_copy, tmp_path):
    _edit(seed_copy / "mappings.json", lambda d: d[0].update(mudra_id="ghost"))
    with pytest.raises(SeedValidationError, match="unknown mudra_id"):
        validate_seed(read_seed(seed_copy), tmp_path)


def test_rejects_missing_image_file(seed_copy, tmp_path):
    _edit(seed_copy / "mudras.json", lambda d: d[0].update(reference_image_path="missing.png"))
    with pytest.raises(SeedValidationError, match="image file not found"):
        validate_seed(read_seed(seed_copy), tmp_path)


def test_rejects_unknown_fields(seed_copy):
    _edit(seed_copy / "mudras.json", lambda d: d[0].update(mening="typo"))
    with pytest.raises(Exception):
        read_seed(seed_copy)


def test_reference_image_attribution_matches_registered_seed_paths():
    assets_dir = DEFAULT_SEED_DIR.parent / "assets" / "mudras"
    manifest = json.loads((assets_dir / "attributions.json").read_text(encoding="utf-8"))
    bundle = read_seed()
    seeded = {m.id: m.reference_image_path for m in bundle.mudras if m.reference_image_path}
    by_path = {item["local_asset_path"]: item for item in manifest}
    assert set(seeded.values()) <= set(by_path)
    assert all((DEFAULT_SEED_DIR.parent / "assets" / path).is_file() for path in seeded.values())
    assert all(by_path[path]["sha256"] for path in seeded.values())
    assert all(
        by_path[path]["license"] and by_path[path]["attribution"]
        for path in seeded.values()
    )
