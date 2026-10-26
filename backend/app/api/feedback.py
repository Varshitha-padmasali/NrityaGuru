"""Corrective feedback endpoints (Parts 8-9)."""
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.api.deps import (
    enforce_tutor_rate_limit,
    get_feedback_store,
    get_feedback_workflow,
    require_development_session_access,
)
from app.db.database import get_db
from app.repositories.feedback_repository import SqlFeedbackStore
from app.schemas.evaluation import SESSION_ID_PATTERN
from app.schemas.feedback import FeedbackRequest, FeedbackResult
from app.services.feedback_workflow import FeedbackWorkflow

router = APIRouter(prefix="/api", tags=["feedback"])


@router.post(
    "/feedback/generate",
    response_model=FeedbackResult,
    dependencies=[Depends(enforce_tutor_rate_limit), Depends(require_development_session_access)],
)
def generate_feedback(
    body: FeedbackRequest,
    db: Session = Depends(get_db),
    workflow: FeedbackWorkflow = Depends(get_feedback_workflow),
) -> FeedbackResult:
    """Evidence is loaded from the trusted store by session id. The request carries NO
    evaluation data. Stored feedback is reused unless `regenerate` is true."""
    return workflow.run(db, body.session_id, regenerate=body.regenerate)


@router.get("/feedback/{session_id}", response_model=FeedbackResult, dependencies=[Depends(require_development_session_access)])
def get_stored_feedback(
    session_id: str = Path(pattern=SESSION_ID_PATTERN),
    db: Session = Depends(get_db),
    store: SqlFeedbackStore = Depends(get_feedback_store),
) -> FeedbackResult:
    """Latest stored feedback for a session (no Gemini call, no generation)."""
    stored = store.latest(db, session_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="No feedback has been stored for this session.")
    return stored
