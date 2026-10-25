"""Fetch the practised mudra/movement and its instructions from PostgreSQL."""
from typing import TYPE_CHECKING

from app.core.enums import EvaluationErrorCode
from app.repositories import knowledge_repository as repo
from app.schemas.evaluation import EvaluationResult, ReferenceInfo
from app.services.evaluation_errors import EvaluationValidationError
from app.services.knowledge_retrieval import movement_to_out, mudra_to_out

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

UNKNOWN_REFERENCE_MESSAGE = "The referenced mudra or movement was not found or is not available."


def lookup_reference(
    db: "Session", result: EvaluationResult, *, include_unverified: bool = False
) -> ReferenceInfo:
    """Raises EvaluationValidationError(UNKNOWN_REFERENCE) for a missing OR hidden reference
    (same message for both, so existence of unverified records is not leaked)."""
    if result.reference_mudra_id is not None:
        mudra = repo.get_mudra(db, result.reference_mudra_id, include_unverified=include_unverified)
        if mudra is None:
            raise EvaluationValidationError(EvaluationErrorCode.UNKNOWN_REFERENCE, UNKNOWN_REFERENCE_MESSAGE)
        out = mudra_to_out(mudra)
        return ReferenceInfo(
            record_type="mudra", record_id=out.id, name=out.name, category=out.category,
            practice_instructions=out.practice_instructions,
            instructions_available=bool(out.practice_instructions),
            reference_media_path=out.reference_image_path,
            verification_status=out.verification_status, source=out.source, limitations=out.limitations,
        )

    movement = repo.get_movement(db, result.reference_movement_id, include_unverified=include_unverified)
    if movement is None:
        raise EvaluationValidationError(EvaluationErrorCode.UNKNOWN_REFERENCE, UNKNOWN_REFERENCE_MESSAGE)
    out = movement_to_out(movement)
    return ReferenceInfo(
        record_type="movement", record_id=out.id, name=out.name, category=out.movement_category,
        practice_instructions=out.practice_instructions,
        instructions_available=bool(out.practice_instructions),
        reference_media_path=out.reference_media_path,
        verification_status=out.verification_status, source=out.source, limitations=out.limitations,
    )
