"""Errors for evaluation evidence. Messages are safe to show to API callers."""
from app.core.enums import EvaluationErrorCode


class EvaluationValidationError(ValueError):
    def __init__(self, code: EvaluationErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
