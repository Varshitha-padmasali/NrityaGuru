"""Compatibility adapters for the frozen Next.js API contracts.

The curated database uses stable string IDs. The current UI accepts numeric IDs,
so expose reversible-by-lookup numeric aliases at the HTTP boundary while keeping
canonical IDs in storage and in the optional ``canonical_id`` response field.
"""
from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Movement, Mudra, PracticeSession


def external_id(kind: str, canonical_id: str) -> int:
    """Return a deterministic positive 48-bit number (safe in JavaScript Number)."""
    digest = hashlib.sha256(f"nrityaguru:{kind}:{canonical_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:6], "big") or 1


def resolve_reference_id(db: Session, value: int | str) -> tuple[str, str] | None:
    """Resolve a UI alias or canonical string ID to (kind, database ID)."""
    raw = str(value)
    mudras = list(db.scalars(select(Mudra)))
    movements = list(db.scalars(select(Movement)))
    for kind, rows in (("mudra", mudras), ("movement", movements)):
        direct = next((row for row in rows if row.id == raw), None)
        if direct is not None:
            return kind, direct.id
    numeric_value = int(raw) if raw.isdigit() else None
    matches = [
        (kind, row.id)
        for kind, rows in (("mudra", mudras), ("movement", movements))
        for row in rows
        if numeric_value is not None and external_id(kind, row.id) == numeric_value
    ]
    if len(matches) > 1:
        raise RuntimeError("numeric reference ID collision")
    return matches[0] if matches else None


def external_session_id(session_id: str) -> int:
    if session_id.isdigit():
        return int(session_id)
    return external_id("session", session_id)


def resolve_session_id(db: Session, value: int | str) -> str | None:
    raw = str(value)
    if db.get(PracticeSession, raw) is not None:
        return raw
    if not raw.isdigit():
        return None
    matches = [
        session_id
        for session_id in db.scalars(select(PracticeSession.id))
        if external_session_id(session_id) == int(raw)
    ]
    if len(matches) > 1:
        raise RuntimeError("numeric session ID collision")
    return matches[0] if matches else None


def frontend_verification_status(status: object) -> str:
    value = getattr(status, "value", status)
    return {
        "verified": "verified",
        "source_cited": "needs_review",
        "unverified": "unverified",
    }.get(str(value), "needs_review")


def frontend_hasta_type(category: str | None) -> str | None:
    if not category:
        return None
    normalized = category.casefold()
    if "asamyuta" in normalized:
        return "asamyuta"
    if "samyuta" in normalized:
        return "samyuta"
    return None


def frontend_source(source: object | None) -> str | None:
    if source is None:
        return None
    name = getattr(source, "source_name", None)
    url = getattr(source, "source_url", None)
    if name and url:
        return f"{name} ({url})"
    return name or url
