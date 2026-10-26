"""AI tutor endpoint (Part 6)."""
from functools import partial

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import check_unverified_allowed, enforce_tutor_rate_limit, get_tutor_service
from app.core.config import Settings, get_settings
from app.db.database import get_db
from app.schemas.rag import TutorExplainRequest
from app.services.knowledge_retrieval import retrieve_for_text
from app.services.rag_pipeline import RagPipeline
from app.services.tutor_service import TutorService
from app.services.frontend_contract import external_id
from app.schemas.knowledge import RetrievalResponse

router = APIRouter(prefix="/api", tags=["tutor"])


@router.post(
    "/tutor/explain",
    dependencies=[Depends(enforce_tutor_rate_limit)],
)
def explain(
    body: TutorExplainRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    tutor: TutorService = Depends(get_tutor_service),
) -> dict:
    include_unverified = body.include_unverified or (
        settings.app_env != "production" and settings.allow_unverified_records
    )
    check_unverified_allowed(include_unverified, settings)
    pipeline = RagPipeline(retrieve=partial(retrieve_for_text, db), tutor=tutor)
    result = pipeline.run(
        body.text,
        include_unverified=include_unverified,
        include_keyword_matches=body.include_keyword_matches,
    )
    retrieval: RetrievalResponse = result.retrieval
    requested_ids = set(body.mudra_ids)
    retrieved_ids = {
        external_id("mudra", ref.record_id)
        for concept in retrieval.concepts
        for ref in concept.references
        if ref.record_type == "mudra"
    }
    used_ids = sorted(requested_ids & retrieved_ids) if requested_ids else sorted(retrieved_ids)
    output = result.model_dump(mode="json")
    output.update({
        "explanation": result.tutor.explanation.summary,
        "used_mudra_ids": used_ids,
        "unsupported_concepts": [
            concept.concept.text
            for concept in retrieval.concepts
            if concept.status.value == "unsupported"
        ],
        "model_name": result.tutor.model or "knowledge_only",
    })
    return output
