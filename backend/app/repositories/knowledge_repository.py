"""Database access for the knowledge base. No Gemini or HTTP code belongs here.

Rule: direct repository calls return `verified` records by default. Knowledge retrieval
may explicitly include `source_cited` records, which must remain labelled with provenance.
Pass include_unverified=True only for configured development/admin workflows.
"""
import json
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    ConceptMapping,
    Movement,
    Mudra,
    Source,
    VerificationStatus,
)
from app.services.text_processing import normalize_text

DATASET_MAPPING_PATH = Path(__file__).resolve().parents[2] / "data" / "seed" / "dataset_mapping.json"


@lru_cache(maxsize=1)
def _dataset_labels_by_mudra() -> dict[str, list[str]]:
    try:
        rows = json.loads(DATASET_MAPPING_PATH.read_text(encoding="utf-8"))["class_folders"]
    except (OSError, KeyError, json.JSONDecodeError):
        return {}
    result: dict[str, list[str]] = {}
    for row in rows:
        result.setdefault(row["mudra_id"], []).extend([row["dataset_folder"], row["original_label"]])
    return result


def normalize_concept(text: str) -> str:
    return normalize_text(text)


def _allowed(include_unverified: bool, include_source_cited: bool = False) -> list[VerificationStatus]:
    if include_unverified:
        return list(VerificationStatus)
    if include_source_cited:
        return [VerificationStatus.VERIFIED, VerificationStatus.SOURCE_CITED]
    return [VerificationStatus.VERIFIED]


# ---------- sources ----------
def get_source(db: Session, source_id: str) -> Source | None:
    return db.get(Source, source_id)


# ---------- mudras ----------
def get_mudra(
    db: Session, mudra_id: str, *, include_unverified: bool = False,
    include_source_cited: bool = False,
) -> Mudra | None:
    mudra = db.get(Mudra, mudra_id)
    if mudra is None or mudra.verification_status not in _allowed(include_unverified, include_source_cited):
        return None
    return mudra


def get_mudra_by_name(
    db: Session, name: str, *, include_unverified: bool = False,
    include_source_cited: bool = False,
) -> Mudra | None:
    key = normalize_concept(name)
    if not key:
        return None
    stmt = select(Mudra).where(Mudra.verification_status.in_(_allowed(include_unverified, include_source_cited)))
    for mudra in db.scalars(stmt):
        names = [mudra.name, *(mudra.alternate_names or []), *_dataset_labels_by_mudra().get(mudra.id, [])]
        if any(normalize_concept(candidate) == key for candidate in names):
            return mudra
    return None


def list_mudras(
    db: Session,
    *,
    include_unverified: bool = False,
    include_source_cited: bool = False,
    category: str | None = None,
    query: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Mudra]:
    stmt = select(Mudra).where(Mudra.verification_status.in_(_allowed(include_unverified, include_source_cited)))
    if category:
        stmt = stmt.where(Mudra.category == category)
    records = list(db.scalars(stmt.order_by(Mudra.name)))
    if query and query.strip():
        key = normalize_concept(query)
        records = [
            record for record in records
            if any(key in normalize_concept(name) for name in [
                record.name, *(record.alternate_names or []), *_dataset_labels_by_mudra().get(record.id, [])
            ])
        ]
    return records[offset : offset + limit]


# ---------- movements ----------
def get_movement(
    db: Session, movement_id: str, *, include_unverified: bool = False,
    include_source_cited: bool = False,
) -> Movement | None:
    movement = db.get(Movement, movement_id)
    if movement is None or movement.verification_status not in _allowed(include_unverified, include_source_cited):
        return None
    return movement


def list_movements(
    db: Session,
    *,
    include_unverified: bool = False,
    include_source_cited: bool = False,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Movement]:
    stmt = select(Movement).where(Movement.verification_status.in_(_allowed(include_unverified, include_source_cited)))
    if category:
        stmt = stmt.where(Movement.movement_category == category)
    stmt = stmt.order_by(Movement.name).limit(limit).offset(offset)
    return list(db.scalars(stmt))


# ---------- concept mappings ----------
def get_mappings_for_concept(
    db: Session, concept: str, *, include_unverified: bool = False,
    include_source_cited: bool = False,
) -> list[ConceptMapping]:
    """All explicit mappings for one concept (there may be several interpretations).

    Returns [] when nothing is mapped. Part 4 additionally checks that the mapped
    mudra/movement itself is trusted before presenting it.
    """
    stmt = (
        select(ConceptMapping)
        .where(
            ConceptMapping.concept == normalize_concept(concept),
            ConceptMapping.verification_status.in_(_allowed(include_unverified, include_source_cited)),
        )
        .order_by(ConceptMapping.id)
    )
    return list(db.scalars(stmt))


# ---------- writes (used by the seed script) ----------
def upsert(db: Session, instance):
    """Insert or update by primary key. Safe to run repeatedly."""
    return db.merge(instance)
