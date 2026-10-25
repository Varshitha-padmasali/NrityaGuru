"""Load and validate the curated seed data.  Usage (from backend/):  python -m app.db.seed

The seed files in data/seed/*.json are validated BEFORE anything is written:
- unknown fields are rejected (catches typos)
- every record that is not 'unverified' must cite an existing source
- mappings must point to existing mudras/movements
- image/media paths must exist under data/assets/
Running the script twice is safe (records are upserted by id).
"""
import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session

from app.db.models import ConceptMapping, Movement, Mudra, Source, VerificationStatus
from app.repositories import knowledge_repository as repo

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SEED_DIR = BACKEND_DIR / "data" / "seed"
DEFAULT_ASSETS_DIR = BACKEND_DIR / "data" / "assets"


class SeedValidationError(ValueError):
    pass


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SeedSource(_Strict):
    id: str
    source_name: str
    source_url: str | None = None
    source_type: str
    author_or_organization: str | None = None
    publication_date: str | None = None
    access_date: date | None = None
    license_or_usage_notes: str | None = None
    reliability_notes: str | None = None


class SeedMudra(_Strict):
    id: str
    name: str
    alternate_names: list[str] = []
    category: str
    meaning: str | None = None
    usage: list[str] = []
    description: str | None = None
    practice_instructions: str | None = None
    reference_image_path: str | None = None
    source_id: str | None = None
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    verification_notes: str | None = None


class SeedMovement(_Strict):
    id: str
    name: str
    description: str | None = None
    movement_category: str
    practice_instructions: str | None = None
    reference_media_path: str | None = None
    source_id: str | None = None
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    verification_notes: str | None = None


class SeedMapping(_Strict):
    id: str
    concept: str
    mudra_id: str | None = None
    movement_id: str | None = None
    relationship_description: str | None = None
    interpretation_type: str
    source_id: str | None = None
    evidence_notes: str | None = None
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED

    @field_validator("concept")
    @classmethod
    def _normalize(cls, v: str) -> str:
        return repo.normalize_concept(v)


@dataclass
class SeedBundle:
    sources: list[SeedSource]
    mudras: list[SeedMudra]
    movements: list[SeedMovement]
    mappings: list[SeedMapping]


def _read(path: Path, model):
    with open(path, encoding="utf-8") as f:
        return [model(**item) for item in json.load(f)]


def read_seed(seed_dir: Path = DEFAULT_SEED_DIR) -> SeedBundle:
    return SeedBundle(
        sources=_read(seed_dir / "sources.json", SeedSource),
        mudras=_read(seed_dir / "mudras.json", SeedMudra),
        movements=_read(seed_dir / "movements.json", SeedMovement),
        mappings=_read(seed_dir / "mappings.json", SeedMapping),
    )


def validate_seed(bundle: SeedBundle, assets_dir: Path = DEFAULT_ASSETS_DIR) -> None:
    errors: list[str] = []
    source_ids = {s.id for s in bundle.sources}
    mudra_ids = {m.id for m in bundle.mudras}
    movement_ids = {m.id for m in bundle.movements}

    for label, items in (
        ("source", bundle.sources),
        ("mudra", bundle.mudras),
        ("movement", bundle.movements),
        ("mapping", bundle.mappings),
    ):
        ids = [i.id for i in items]
        if len(ids) != len(set(ids)):
            errors.append(f"duplicate {label} ids")

    for rec in [*bundle.mudras, *bundle.movements, *bundle.mappings]:
        if rec.source_id is not None and rec.source_id not in source_ids:
            errors.append(f"{rec.id}: unknown source_id '{rec.source_id}'")
        if rec.verification_status != VerificationStatus.UNVERIFIED and rec.source_id is None:
            errors.append(f"{rec.id}: status '{rec.verification_status.value}' requires a source_id")

    for m in bundle.mudras:
        if m.reference_image_path and not (assets_dir / m.reference_image_path).is_file():
            errors.append(f"{m.id}: image file not found: {m.reference_image_path}")
    for mv in bundle.movements:
        if mv.reference_media_path and not (assets_dir / mv.reference_media_path).is_file():
            errors.append(f"{mv.id}: media file not found: {mv.reference_media_path}")

    for mp in bundle.mappings:
        if mp.mudra_id is None and mp.movement_id is None:
            errors.append(f"{mp.id}: needs a mudra_id or movement_id")
        if mp.mudra_id is not None and mp.mudra_id not in mudra_ids:
            errors.append(f"{mp.id}: unknown mudra_id '{mp.mudra_id}'")
        if mp.movement_id is not None and mp.movement_id not in movement_ids:
            errors.append(f"{mp.id}: unknown movement_id '{mp.movement_id}'")

    if errors:
        raise SeedValidationError("; ".join(errors))


def load_seed(
    db: Session,
    seed_dir: Path = DEFAULT_SEED_DIR,
    assets_dir: Path = DEFAULT_ASSETS_DIR,
) -> dict[str, int]:
    bundle = read_seed(seed_dir)
    validate_seed(bundle, assets_dir)

    # Order matters: parents (sources) before children that reference them.
    for s in bundle.sources:
        repo.upsert(db, Source(**s.model_dump()))
    db.flush()
    for m in bundle.mudras:
        repo.upsert(db, Mudra(**m.model_dump()))
    for mv in bundle.movements:
        repo.upsert(db, Movement(**mv.model_dump()))
    db.flush()
    for mp in bundle.mappings:
        repo.upsert(db, ConceptMapping(**mp.model_dump()))
    db.commit()

    counts = {
        "sources": len(bundle.sources),
        "mudras": len(bundle.mudras),
        "movements": len(bundle.movements),
        "mappings": len(bundle.mappings),
    }
    logger.info("Seed loaded: %s", counts)
    return counts


if __name__ == "__main__":
    from app.core.logging import configure_logging
    from app.db.database import DatabaseNotConfiguredError, get_sessionmaker

    configure_logging("INFO")
    try:
        with get_sessionmaker()() as session:
            print("Seed loaded:", load_seed(session))
    except DatabaseNotConfiguredError as exc:
        print(exc)
        raise SystemExit(1)
    except SeedValidationError as exc:
        print("Seed data is invalid:", exc)
        raise SystemExit(1)
