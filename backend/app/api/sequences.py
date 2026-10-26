"""Multilingual lyric-to-mudra sequence endpoint (additive; legacy routes unchanged)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import check_unverified_allowed, enforce_tutor_rate_limit, get_sequence_generator
from app.core.config import Settings, get_settings
from app.db.database import get_db
from app.schemas.multilingual_sequence import (
    MultilingualSequenceRequest,
    MultilingualSequenceResponse,
)
from app.services.gemini_client import TextGenerator
from app.services.multilingual_sequence import generate_multilingual_sequence

router = APIRouter(prefix="/api/knowledge", tags=["knowledge sequence"])


@router.post(
    "/sequence",
    response_model=MultilingualSequenceResponse,
    dependencies=[Depends(enforce_tutor_rate_limit)],
)
def create_sequence(
    body: MultilingualSequenceRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    generator: TextGenerator | None = Depends(get_sequence_generator),
) -> MultilingualSequenceResponse:
    include_unverified = body.include_unverified or (
        settings.app_env != "production" and settings.allow_unverified_records
    )
    check_unverified_allowed(include_unverified, settings)
    return generate_multilingual_sequence(
        db,
        body.text,
        mode=body.mode,
        generator=generator,
        include_unverified=include_unverified,
        catalogue_mode=body.catalogue_mode,
    )
