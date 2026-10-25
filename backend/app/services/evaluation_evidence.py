"""Validate evaluation results and turn them into ValidatedEvidence.

Pipeline:  session id format -> trusted store -> same-session check -> schema/version check
           -> reference lookup (PostgreSQL) -> mock-data guard -> assessment.
Anything that fails raises EvaluationValidationError with a stable code.
"""
import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from pydantic import ValidationError

from app.core.enums import EvaluationErrorCode as Code
from app.integrations.evaluation_stub import (
    EvaluationStore,
    EvaluationUnavailableError,
    MockEvaluationStore,
)
from app.schemas.evaluation import (
    SESSION_ID_PATTERN,
    SUPPORTED_MAJOR_VERSION,
    EvaluationResult,
    EvidenceSource,
    ReferenceInfo,
    ValidatedEvidence,
)
from app.services.evaluation_assessment import assess
from app.services.evaluation_errors import EvaluationValidationError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.core.config import Settings

_SESSION_ID_RE = re.compile(SESSION_ID_PATTERN)

ReferenceLookup = Callable[..., ReferenceInfo]  # (db, result, *, include_unverified)


def parse_evaluation_payload(payload: object) -> EvaluationResult:
    """For raw JSON from the evaluation module / a database column. Error text lists only
    FIELD NAMES, never the submitted values."""
    if not isinstance(payload, dict):
        raise EvaluationValidationError(Code.MALFORMED_RESULT, "The evaluation result must be a JSON object.")
    try:
        return EvaluationResult.model_validate(payload)
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in err.get("loc", ())) or "(root)" for err in exc.errors()})
        raise EvaluationValidationError(
            Code.MALFORMED_RESULT, "The evaluation result is invalid in: " + ", ".join(fields[:10])
        ) from None


def check_schema_version(result: EvaluationResult) -> None:
    try:
        major = int(result.schema_version.split(".")[0])
    except (ValueError, IndexError):
        major = -1
    if major != SUPPORTED_MAJOR_VERSION:
        raise EvaluationValidationError(
            Code.UNSUPPORTED_VERSION,
            f"Unsupported evaluation schema version (this server supports {SUPPORTED_MAJOR_VERSION}.x).",
        )


def build_evidence(
    result: EvaluationResult, reference: ReferenceInfo, *, source: EvidenceSource
) -> ValidatedEvidence:
    """Pure step: version check, mock-data guard, assessment."""
    check_schema_version(result)
    if result.is_mock and source != EvidenceSource.MOCK_STORE:
        raise EvaluationValidationError(
            Code.MOCK_DATA_IN_REAL_STORE, "Mock evaluation data cannot be used as a real evaluation."
        )
    return ValidatedEvidence(
        evidence_source=source,
        is_mock=source == EvidenceSource.MOCK_STORE or result.is_mock,
        result=result,
        reference=reference,
        assessment=assess(result, reference),
    )


class EvidenceService:
    def __init__(
        self,
        store: EvaluationStore,
        source: EvidenceSource,
        *,
        include_unverified: bool = False,
        reference_lookup: ReferenceLookup | None = None,
    ) -> None:
        self._store = store
        self._source = source
        self._include_unverified = include_unverified
        self._lookup = reference_lookup

    def load(self, db: "Session", session_id: str) -> ValidatedEvidence:
        if not isinstance(session_id, str) or not _SESSION_ID_RE.match(session_id):
            raise EvaluationValidationError(Code.INVALID_SESSION_ID, "The session id is not valid.")

        try:
            result = self._store.get(db, session_id)
        except EvaluationUnavailableError:
            raise EvaluationValidationError(
                Code.STORE_UNAVAILABLE, "Evaluation results are not available right now."
            ) from None
        if result is None:
            raise EvaluationValidationError(Code.SESSION_NOT_FOUND, "No evaluation was found for this session.")
        if result.session_id != session_id:
            raise EvaluationValidationError(Code.SESSION_MISMATCH, "The stored evaluation does not match this session.")

        check_schema_version(result)
        lookup = self._lookup
        if lookup is None:
            from app.services.reference_lookup import lookup_reference  # needs the database layer

            lookup = lookup_reference
        reference = lookup(db, result, include_unverified=self._include_unverified)
        return build_evidence(result, reference, source=self._source)


def build_evidence_service(settings: "Settings") -> EvidenceService:
    if settings.use_mock_evaluation:
        return EvidenceService(
            MockEvaluationStore(), EvidenceSource.MOCK_STORE,
            include_unverified=settings.allow_unverified_records,
        )
    from app.integrations.database_evaluation_store import DatabaseEvaluationStore  # needs SQLAlchemy

    return EvidenceService(
        DatabaseEvaluationStore(), EvidenceSource.STORED_SESSION,
        include_unverified=settings.allow_unverified_records,
    )
