"""Database access for the knowledge base. No Gemini or HTTP code belongs here.

Rule: by default only `verified` records are returned. Pass include_unverified=True
to also see `source_cited` and `unverified` records (for admin/dev use and clearly
labelled output only).
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    ConceptMapping,
    Movement,
    Mudra,
    Source,
    VerificationStatus,
)
from app.services.text_processing import normalize_text


def normalize_concept(text: str) -> str:
    return normalize_text(text)


def _allowed(include_unverified: bool) -> list[VerificationStatus]:
    return list(VerificationStatus) if include_unverified else [VerificationStatus.VERIFIED]


# ---------- sources ----------
def get_source(db: Session, source_id: str) -> Source | None:
    return db.get(Source, source_id)


# ---------- mudras ----------
def get_mudra(db: Session, mudra_id: str, *, include_unverified: bool = False) -> Mudra | None:
    mudra = db.get(Mudra, mudra_id)
    if mudra is None or mudra.verification_status not in _allowed(include_unverified):
        return None
    return mudra


def get_mudra_by_name(db: Session, name: str, *, include_unverified: bool = False) -> Mudra | None:
    stmt = select(Mudra).where(
        func.lower(Mudra.name) == name.strip().lower(),
        Mudra.verification_status.in_(_allowed(include_unverified)),
    )
    return db.scalars(stmt).first()


def list_mudras(
    db: Session,
    *,
    include_unverified: bool = False,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Mudra]:
    stmt = select(Mudra).where(Mudra.verification_status.in_(_allowed(include_unverified)))
    if category:
        stmt = stmt.where(Mudra.category == category)
    stmt = stmt.order_by(Mudra.name).limit(limit).offset(offset)
    return list(db.scalars(stmt))


# ---------- movements ----------
def get_movement(
    db: Session, movement_id: str, *, include_unverified: bool = False
) -> Movement | None:
    movement = db.get(Movement, movement_id)
    if movement is None or movement.verification_status not in _allowed(include_unverified):
        return None
    return movement


def list_movements(
    db: Session,
    *,
    include_unverified: bool = False,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Movement]:
    stmt = select(Movement).where(Movement.verification_status.in_(_allowed(include_unverified)))
    if category:
        stmt = stmt.where(Movement.movement_category == category)
    stmt = stmt.order_by(Movement.name).limit(limit).offset(offset)
    return list(db.scalars(stmt))


# ---------- concept mappings ----------
def get_mappings_for_concept(
    db: Session, concept: str, *, include_unverified: bool = False
) -> list[ConceptMapping]:
    """All explicit mappings for one concept (there may be several interpretations).

    Returns [] when nothing is mapped. Part 4 additionally checks that the mapped
    mudra/movement itself is trusted before presenting it.
    """
    stmt = (
        select(ConceptMapping)
        .where(
            ConceptMapping.concept == normalize_concept(concept),
            ConceptMapping.verification_status.in_(_allowed(include_unverified)),
        )
        .order_by(ConceptMapping.id)
    )
    return list(db.scalars(stmt))


# ---------- writes (used by the seed script) ----------
def upsert(db: Session, instance):
    """Insert or update by primary key. Safe to run repeatedly."""
    return db.merge(instance)
