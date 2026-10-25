"""AI tutor endpoint (Part 6)."""
from functools import partial

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import check_unverified_allowed, enforce_tutor_rate_limit, get_tutor_service
from app.core.config import Settings, get_settings
from app.db.database import get_db
from app.schemas.rag import TutorExplainRequest, TutorExplainResponse
from app.services.knowledge_retrieval import retrieve_for_text
from app.services.rag_pipeline import RagPipeline
from app.services.tutor_service import TutorService

router = APIRouter(prefix="/api", tags=["tutor"])


@router.post(
    "/tutor/explain",
    response_model=TutorExplainResponse,
    dependencies=[Depends(enforce_tutor_rate_limit)],
)
def explain(
    body: TutorExplainRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    tutor: TutorService = Depends(get_tutor_service),
) -> TutorExplainResponse:
    check_unverified_allowed(body.include_unverified, settings)
    pipeline = RagPipeline(retrieve=partial(retrieve_for_text, db), tutor=tutor)
    return pipeline.run(
        body.text,
        include_unverified=body.include_unverified,
        include_keyword_matches=body.include_keyword_matches,
    )
