"""Knowledge endpoints (Part 4)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import check_unverified_allowed
from app.core.config import Settings, get_settings
from app.db.database import get_db
from app.repositories import knowledge_repository as repo
from app.schemas.knowledge import MovementOut, MudraOut, RetrievalResponse, RetrieveRequest
from app.services.knowledge_retrieval import movement_to_out, mudra_to_out, retrieve_for_text

router = APIRouter(prefix="/api", tags=["knowledge"])


@router.post("/knowledge/retrieve", response_model=RetrievalResponse)
def retrieve_knowledge(
    body: RetrieveRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RetrievalResponse:
    check_unverified_allowed(body.include_unverified, settings)
    return retrieve_for_text(
        db,
        body.text,
        include_unverified=body.include_unverified,
        include_keyword_matches=body.include_keyword_matches,
    )


@router.get("/mudras", response_model=list[MudraOut])
def list_mudras(
    category: str | None = None,
    include_unverified: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[MudraOut]:
    check_unverified_allowed(include_unverified, settings)
    rows = repo.list_mudras(
        db, include_unverified=include_unverified, category=category, limit=limit, offset=offset
    )
    return [mudra_to_out(m) for m in rows]


@router.get("/mudras/{mudra_id}", response_model=MudraOut)
def get_mudra(
    mudra_id: str,
    include_unverified: bool = False,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MudraOut:
    check_unverified_allowed(include_unverified, settings)
    mudra = repo.get_mudra(db, mudra_id, include_unverified=include_unverified)
    if mudra is None:
        # Same answer for "does not exist" and "exists but not verified": no information leak.
        raise HTTPException(status_code=404, detail="Mudra not found.")
    return mudra_to_out(mudra)


@router.get("/movements", response_model=list[MovementOut])
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
        db, include_unverified=include_unverified, category=category, limit=limit, offset=offset
    )
    return [movement_to_out(m) for m in rows]
