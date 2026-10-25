"""AI tutor: retrieved knowledge -> grounded, validated explanation (or safe fallback).

Flow: (no references? skip Gemini) -> build prompt -> Gemini -> parse JSON -> Pydantic shape
check -> grounding check -> result.  Any failure returns knowledge-only output instead.
There is no automatic retry here: a retry costs quota and time, and the fallback is useful.
"""
import logging
from typing import TYPE_CHECKING

from app.core.enums import TutorFallbackReason
from app.schemas.knowledge import RetrievalResponse
from app.schemas.tutor import TutorResult
from app.services.gemini_client import (
    GeminiError,
    GeminiNotConfiguredError,
    TextGenerator,
    build_text_generator,
)
from app.services.tutor_fallback import build_knowledge_only, summary_for
from app.services.tutor_prompt import SYSTEM_INSTRUCTION, build_user_prompt
from app.services.tutor_validation import (
    InvalidCitationError,
    MalformedOutputError,
    UngroundedOutputError,
    parse_json_object,
    validate_explanation,
)

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger(__name__)


class TutorService:
    def __init__(self, generator: TextGenerator | None, model: str | None = None) -> None:
        self._generator = generator
        self._model = model

    def explain(self, retrieval: RetrievalResponse) -> TutorResult:
        if not any(cr.references for cr in retrieval.concepts):
            return self._fallback(retrieval, TutorFallbackReason.NO_REFERENCES)
        if self._generator is None:
            return self._fallback(retrieval, TutorFallbackReason.NOT_CONFIGURED)

        prompt = build_user_prompt(retrieval)
        try:
            text = self._generator.generate(system_instruction=SYSTEM_INSTRUCTION, prompt=prompt)
        except GeminiError as exc:
            logger.warning("Tutor fallback: %s", exc.reason.value)
            return self._fallback(retrieval, exc.reason)

        try:
            explanation = validate_explanation(parse_json_object(text), retrieval)
        except MalformedOutputError:
            return self._fallback(retrieval, TutorFallbackReason.MALFORMED_OUTPUT)
        except InvalidCitationError:
            return self._fallback(retrieval, TutorFallbackReason.INVALID_CITATION)
        except UngroundedOutputError:
            return self._fallback(retrieval, TutorFallbackReason.UNGROUNDED_OUTPUT)

        return TutorResult(mode="ai", explanation=explanation, model=self._model)

    def _fallback(self, retrieval: RetrievalResponse, reason: TutorFallbackReason) -> TutorResult:
        if reason not in (TutorFallbackReason.NO_REFERENCES, TutorFallbackReason.NOT_CONFIGURED):
            logger.warning("Tutor returned knowledge-only output (reason=%s)", reason.value)
        return TutorResult(
            mode="knowledge_only",
            explanation=build_knowledge_only(retrieval, reason),
            fallback_reason=reason,
            notice=summary_for(reason),
        )


def build_tutor_service(settings: "Settings") -> TutorService:
    try:
        generator = build_text_generator(settings)
    except GeminiNotConfiguredError:
        logger.info("Gemini is not configured; tutor will return knowledge-only output.")
        return TutorService(None)
    return TutorService(generator, settings.gemini_model)
