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
    assert len(bundle.sources) == 3
    assert len(bundle.mudras) == 52
    assert len({mudra.id for mudra in bundle.mudras}) == 52
    assert len({mudra.name.casefold() for mudra in bundle.mudras}) == 52
    assert len(bundle.movements) == 0  # nothing verified yet; none invented
    assert len(bundle.mappings) == 6


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


def test_seeded_records_are_not_authoritative_yet(db_session):
    load_seed(db_session)
    # They are 'source_cited', not 'verified', so default retrieval hides them.
    assert repo.list_mudras(db_session) == []
    assert repo.get_mappings_for_concept(db_session, "river") == []
    pataka = repo.get_mudra(db_session, "mudra_pataka", include_unverified=True)
    assert pataka.source.source_name.startswith("List of mudras")
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
