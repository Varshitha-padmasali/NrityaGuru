"""Shared FastAPI dependencies."""
import math
from functools import lru_cache

from fastapi import Depends, HTTPException, Request

from app.core.config import Settings, get_settings
from app.core.rate_limit import SlidingWindowLimiter
from app.services.evaluation_evidence import EvidenceService, build_evidence_service
from app.repositories.feedback_repository import SqlFeedbackStore
from app.services.feedback_service import FeedbackService, build_feedback_service
from app.services.feedback_workflow import FeedbackWorkflow
from app.services.tutor_service import TutorService, build_tutor_service


def check_unverified_allowed(include_unverified: bool, settings: Settings) -> None:
    if include_unverified and not settings.allow_unverified_records:
        raise HTTPException(
            status_code=403,
            detail="Access to unverified records is disabled on this server.",
        )


def require_development_session_access(settings: Settings = Depends(get_settings)) -> None:
    """Until authenticated owners exist, never expose installation-wide session data in prod."""
    if settings.app_env == "production":
        raise HTTPException(
            status_code=503,
            detail={
                "code": "user_auth_not_configured",
                "message": "Private practice sessions are unavailable until authenticated ownership is configured.",
            },
        )


@lru_cache
def _cached_tutor_service() -> TutorService:
    return build_tutor_service(get_settings())


def get_tutor_service() -> TutorService:
    """One shared service (and Gemini client) per process. Tests override this dependency."""
    return _cached_tutor_service()


@lru_cache
def _cached_evidence_service() -> EvidenceService:
    return build_evidence_service(get_settings())


def get_evidence_service() -> EvidenceService:
    """Tests override this dependency."""
    return _cached_evidence_service()


@lru_cache
def _cached_feedback_service() -> FeedbackService:
    return build_feedback_service(get_settings())


def get_feedback_service() -> FeedbackService:
    """Tests override this dependency."""
    return _cached_feedback_service()


def get_feedback_store() -> SqlFeedbackStore:
    return SqlFeedbackStore()


@lru_cache
def _cached_workflow() -> FeedbackWorkflow:
    return FeedbackWorkflow(_cached_evidence_service(), _cached_feedback_service(), SqlFeedbackStore())


def get_feedback_workflow() -> FeedbackWorkflow:
    """The stable entry point used by the feedback endpoint. Tests override this dependency."""
    return _cached_workflow()


@lru_cache
def _cached_limiter() -> SlidingWindowLimiter:
    return SlidingWindowLimiter(get_settings().tutor_rate_limit_per_minute, 60.0)


def get_limiter() -> SlidingWindowLimiter:
    return _cached_limiter()


# Shared budget: the tutor and feedback endpoints both call the paid Gemini API.
def enforce_tutor_rate_limit(
    request: Request, limiter: SlidingWindowLimiter = Depends(get_limiter)
) -> None:
    key = request.client.host if request.client else "unknown"
    allowed, retry_after = limiter.check(key)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a moment and try again.",
            headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
        )
