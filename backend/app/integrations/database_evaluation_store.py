"""EvaluationStore backed by PostgreSQL: reads what the evaluation module stored.

Every row is re-validated with the contract schema on read, so a corrupted or tampered row is
rejected (MALFORMED_RESULT) instead of being trusted.
"""
from typing import Any

from app.repositories.session_repository import get_evaluation_payload
from app.schemas.evaluation import EvaluationResult
from app.services.evaluation_evidence import parse_evaluation_payload


class DatabaseEvaluationStore:
    def get(self, db: Any, session_id: str) -> EvaluationResult | None:
        payload = get_evaluation_payload(db, session_id)
        if payload is None:
            return None
        return parse_evaluation_payload(payload)
