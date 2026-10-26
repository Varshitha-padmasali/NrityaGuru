"""Knowledge endpoints (Part 4)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import check_unverified_allowed
from app.core.config import Settings, get_settings
from app.db.database import get_db
from app.repositories import knowledge_repository as repo
from app.schemas.frontend import FrontendMudraDetail, FrontendMudraSummary, FrontendRetrieveResponse
from app.schemas.knowledge import MovementOut, MudraOut, RetrievalResponse, RetrieveRequest
from app.services.knowledge_retrieval import movement_to_out, mudra_to_out, retrieve_for_text
from app.services.frontend_contract import (
    external_id,
    frontend_hasta_type,
    frontend_source,
    frontend_verification_status,
    resolve_reference_id,
)

router = APIRouter(prefix="/api", tags=["knowledge"])


@router.post("/knowledge/retrieve", response_model=FrontendRetrieveResponse)
def retrieve_knowledge(
    body: RetrieveRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    include_unverified = body.include_unverified or (
        settings.app_env != "production" and settings.allow_unverified_records
    )
    check_unverified_allowed(include_unverified, settings)
    result = retrieve_for_text(
        db,
        body.text,
        include_unverified=include_unverified,
        include_keyword_matches=body.include_keyword_matches,
    )
    concepts = []
    for resolved in result.concepts:
        matches = []
        for ref in resolved.references:
            if ref.record_type != "mudra":
                continue
            mudra = repo.get_mudra(
                db, ref.record_id, include_unverified=include_unverified, include_source_cited=True
            )
            if mudra is None:
                continue
            record = mudra_to_out(mudra)
            evidence_status = frontend_verification_status(mudra.verification_status)
            rationale = ref.evidence_notes[0] if ref.evidence_notes else f"Matched by {ref.match_type.value.replace('_', ' ')}."
            if evidence_status == "needs_review":
                rationale = f"{rationale} Source-cited information; teacher verification is pending."
            elif evidence_status == "unverified":
                rationale = f"{rationale} This record is unverified."
            matches.append({
                "id": external_id("mudra", mudra.id),
                "canonical_id": mudra.id,
                "name": mudra.name,
                "hasta_type": frontend_hasta_type(mudra.category),
                "meaning": mudra.meaning,
                "image_url": record.reference_image_path,
                "rationale": rationale,
                "source": frontend_source(ref.source or ref.mapping_source),
                "verification_status": evidence_status,
            })
        concepts.append({
            "concept": resolved.concept.text,
            "supported": resolved.status.value == "supported" and bool(matches),
            "matches": matches,
            "status": resolved.status.value,
            "references": [ref.model_dump(mode="json") for ref in resolved.references],
            "contains_unverified": resolved.contains_unverified,
            "note": resolved.note,
            "concept_detail": resolved.concept.model_dump(mode="json"),
        })
    return {
        "query": result.original_text,
        "concepts": concepts,
        "original_text": result.original_text,
        "include_unverified": result.include_unverified,
        "include_keyword_matches": result.include_keyword_matches,
        "supported_count": result.supported_count,
        "unsupported_count": result.unsupported_count,
        "warnings": result.warnings,
        "disclaimer": result.disclaimer,
    }


@router.get("/mudras", response_model=list[FrontendMudraSummary])
def list_mudras(
    category: str | None = None,
    q: str | None = Query(default=None, min_length=1, max_length=120),
    include_unverified: bool = False,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    include_unverified = include_unverified or (
        settings.app_env != "production" and settings.allow_unverified_records
    )
    check_unverified_allowed(include_unverified, settings)
    rows = repo.list_mudras(
        db,
        include_unverified=include_unverified,
        include_source_cited=True,
        category=category,
        query=q,
        limit=limit,
        offset=offset,
    )
    output = []
    for mudra in rows:
        record = mudra_to_out(mudra)
        output.append({
            "id": external_id("mudra", mudra.id),
            "canonical_id": mudra.id,
            "name": mudra.name,
            "hasta_type": frontend_hasta_type(mudra.category),
            "meaning": mudra.meaning,
            "image_url": record.reference_image_path,
        })
    return output


@router.get("/mudras/{mudra_id}", response_model=FrontendMudraDetail)
def get_mudra(
    mudra_id: str,
    include_unverified: bool = False,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    numeric_ui_id = mudra_id.isdigit()
    include_unverified = include_unverified or (
        numeric_ui_id and settings.app_env != "production" and settings.allow_unverified_records
    )
    check_unverified_allowed(include_unverified, settings)
    resolved_id = mudra_id
    if mudra_id.isdigit():
        resolved = resolve_reference_id(db, int(mudra_id))
        resolved_id = resolved[1] if resolved and resolved[0] == "mudra" else mudra_id
    mudra = repo.get_mudra(
        db, resolved_id, include_unverified=include_unverified, include_source_cited=True
    )
    if mudra is None:
        mudra = repo.get_mudra_by_name(
            db, mudra_id, include_unverified=include_unverified, include_source_cited=True
        )
    if mudra is None:
        # Same answer for "does not exist" and "exists but not verified": no information leak.
        raise HTTPException(status_code=404, detail="Mudra not found.")
    record = mudra_to_out(mudra)
    practice_reference_id = None
    if settings.evaluation_runtime_verified:
        from app.api.practice import list_practice_references

        practice_reference_id = next(
            (item.id for item in list_practice_references(db, settings) if item.canonical_id == mudra.id),
            None,
        )
    return {
        "id": external_id("mudra", mudra.id),
        "canonical_id": mudra.id,
        "name": mudra.name,
        "hasta_type": frontend_hasta_type(mudra.category),
        "meaning": mudra.meaning,
        "image_url": record.reference_image_path,
        "alt_names": mudra.alternate_names or [],
        "usage": "; ".join(mudra.usage or []) or None,
        "instructions": mudra.practice_instructions,
        "source": frontend_source(mudra.source),
        "verification_status": frontend_verification_status(mudra.verification_status),
        "practice_reference_id": practice_reference_id,
        "category": mudra.category,
        "dataset_image_count": record.dataset_image_count,
        "dataset_images_available": record.dataset_images_available,
        "recognition_supported": record.recognition_supported,
        "limitations": record.limitations,
    }


@router.get("/knowledge/movements", response_model=list[MovementOut])
def list_movements(
    category: str | None = None,
    include_unverified: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[MovementOut]:
    check_unverified_allowed(include_unverified, settings)
    rows = repo.list_movements(
        db, include_unverified=include_unverified, include_source_cited=True,
        category=category, limit=limit, offset=offset
    )
    return [movement_to_out(m) for m in rows]


@router.get("/movements")
def list_practice_targets(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    """The frozen frontend uses /api/movements for evaluable practice targets."""
    from app.api.practice import list_practice_references

    return [item.model_dump(mode="json") for item in list_practice_references(db, settings)]
