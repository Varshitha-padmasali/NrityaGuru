"""Stable entry point for 'give me feedback for this session':

   load validated evidence -> reuse stored feedback if still valid -> generate -> store.

Used by the API; other modules can call FeedbackWorkflow.run(db, session_id) directly.
It does not import SQLAlchemy: persistence is injected (FeedbackStore).
"""
import hashlib
import json
import logging
from typing import Any, Protocol

from app.core.enums import TutorFallbackReason
from app.repositories.errors import PersistenceError
from app.schemas.evaluation import ValidatedEvidence
from app.schemas.feedback import FeedbackResult
from app.services.evaluation_evidence import EvidenceService
from app.services.feedback_service import FeedbackService

logger = logging.getLogger(__name__)

# Fallbacks whose outcome is deterministic. Transient ones (timeout, rate limit, no key...) are
# NOT reused, so a later request can try Gemini again.
REUSABLE_FALLBACKS = frozenset({TutorFallbackReason.INSUFFICIENT_EVIDENCE})


class FeedbackStore(Protocol):
    def latest(self, db: Any, session_id: str) -> FeedbackResult | None: ...

    def save(self, db: Any, result: FeedbackResult) -> None:
        """Raises PersistenceError on failure."""
        ...


def evidence_fingerprint(evidence: ValidatedEvidence) -> str:
    """Changes whenever the evaluation result OR the reference record changes, so stored
    feedback is never reused for different evidence."""
    payload = {
        "result": evidence.result.model_dump(mode="json"),
        "reference": evidence.reference.model_dump(mode="json"),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def is_reusable(stored: FeedbackResult, fingerprint: str) -> bool:
    if stored.evidence_fingerprint != fingerprint:
        return False
    return stored.mode == "ai" or stored.fallback_reason in REUSABLE_FALLBACKS


class FeedbackWorkflow:
    def __init__(
        self, evidence_service: EvidenceService, feedback_service: FeedbackService, store: FeedbackStore
    ) -> None:
        self._evidence = evidence_service
        self._feedback = feedback_service
        self._store = store

    def run(self, db: Any, session_id: str, *, regenerate: bool = False) -> FeedbackResult:
        # Raises EvaluationValidationError (unknown session, bad evidence, ...): the API maps it.
        evidence = self._evidence.load(db, session_id)
        fingerprint = evidence_fingerprint(evidence)
        persist = not evidence.is_mock  # MOCK test data is never stored or reused

        if persist and not regenerate:
            stored = self._latest_or_none(db, session_id)
            if stored is not None and is_reusable(stored, fingerprint):
                stored.saved = True
                stored.reused = True
                return stored

        result = self._feedback.generate(evidence)
        result.evidence_fingerprint = fingerprint
        if persist:
            try:
                self._store.save(db, result)
                result.saved = True
            except PersistenceError:
                logger.error("Feedback was generated but could not be saved.")
                result.saved = False
        return result

    def _latest_or_none(self, db: Any, session_id: str) -> FeedbackResult | None:
        try:
            return self._store.latest(db, session_id)
        except PersistenceError:
            logger.error("Stored feedback could not be read; generating new feedback.")
            return None
