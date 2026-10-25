"""Corrective feedback: validated evidence -> grounded feedback (or evidence-only fallback).

Flow: evidence too weak? skip Gemini -> evidence items -> prompt -> Gemini -> parse -> shape check
      -> citation + invented-detail checks -> result. Any failure returns evidence-only feedback.
Gemini only ever receives STRUCTURED RESULTS. It never analyses a video.
"""
import logging
from typing import TYPE_CHECKING

from app.core.enums import TutorFallbackReason as Reason
from app.schemas.evaluation import EvidenceLevel, ValidatedEvidence
from app.schemas.feedback import (
    EvidenceItem,
    FeedbackBody,
    FeedbackResult,
    ReferenceSummary,
)
from app.services.feedback_evidence import build_evidence_items
from app.services.feedback_fallback import build_evidence_only_feedback, notice_for
from app.services.feedback_prompt import FEEDBACK_SYSTEM_INSTRUCTION, build_feedback_prompt
from app.services.feedback_validation import (
    InvalidEvidenceCitationError,
    InventedDetailError,
    MalformedOutputError,
    parse_json_object,
    validate_feedback,
)
from app.services.gemini_client import (
    GeminiError,
    GeminiNotConfiguredError,
    TextGenerator,
    build_text_generator,
)

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger(__name__)


class FeedbackService:
    def __init__(self, generator: TextGenerator | None, model: str | None = None) -> None:
        self._generator = generator
        self._model = model

    def generate(self, evidence: ValidatedEvidence) -> FeedbackResult:
        items = build_evidence_items(evidence)
        assessment = evidence.assessment

        if assessment.level == EvidenceLevel.INSUFFICIENT:
            return self._fallback(evidence, items, Reason.INSUFFICIENT_EVIDENCE)
        if self._generator is None:
            return self._fallback(evidence, items, Reason.NOT_CONFIGURED)

        prompt = build_feedback_prompt(items, assessment)
        try:
            text = self._generator.generate(system_instruction=FEEDBACK_SYSTEM_INSTRUCTION, prompt=prompt)
        except GeminiError as exc:
            return self._fallback(evidence, items, exc.reason)

        try:
            explanation = validate_feedback(parse_json_object(text), items)
        except MalformedOutputError:
            return self._fallback(evidence, items, Reason.MALFORMED_OUTPUT)
        except InvalidEvidenceCitationError:
            return self._fallback(evidence, items, Reason.INVALID_CITATION)
        except InventedDetailError:
            return self._fallback(evidence, items, Reason.UNGROUNDED_OUTPUT)

        body = FeedbackBody(
            overall_summary=explanation.overall_summary,
            observations=explanation.observations,
            suggestions=explanation.suggestions,
            limitations=assessment.limitations[:40],  # deterministic: never left to the model
        )
        return self._result("ai", evidence, items, body, model=self._model)

    def _fallback(self, evidence: ValidatedEvidence, items: list[EvidenceItem], reason: Reason) -> FeedbackResult:
        if reason not in (Reason.INSUFFICIENT_EVIDENCE, Reason.NOT_CONFIGURED):
            logger.warning("Feedback returned evidence-only output (reason=%s)", reason.value)
        body = build_evidence_only_feedback(evidence, items)
        return self._result(
            "evidence_only", evidence, items, body, fallback_reason=reason, notice=notice_for(reason)
        )

    @staticmethod
    def _result(mode, evidence, items, body, *, model=None, fallback_reason=None, notice=None) -> FeedbackResult:
        ref = evidence.reference
        return FeedbackResult(
            mode=mode,
            session_id=evidence.result.session_id,
            reference=ReferenceSummary(
                record_type=ref.record_type, record_id=ref.record_id, name=ref.name,
                verification_status=ref.verification_status,
                instructions_available=ref.instructions_available,
            ),
            evidence_level=evidence.assessment.level,
            is_mock=evidence.is_mock,
            feedback=body,
            supporting_evidence=items,
            model=model,
            fallback_reason=fallback_reason,
            notice=notice,
        )


def build_feedback_service(settings: "Settings") -> FeedbackService:
    try:
        generator = build_text_generator(settings)
    except GeminiNotConfiguredError:
        logger.info("Gemini is not configured; feedback will be evidence-only.")
        return FeedbackService(None)
    return FeedbackService(generator, settings.gemini_model)
