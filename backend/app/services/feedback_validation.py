"""Checks on Gemini's feedback. Pydantic checks the SHAPE; these check the CLAIMS.

Guards (heuristics, NOT proof of faithfulness; human review is still needed):
  1. every observation/suggestion cites evidence ids that really exist
  2. no body part (finger, wrist, ...) or video/camera word unless the evidence itself uses it
  3. no number unless it appears in the evidence (0-1 values may also appear as percentages)
If any guard fails the AI text is discarded and an evidence-only answer is returned instead.
"""
import re

from pydantic import ValidationError

from app.schemas.feedback import EvidenceItem, FeedbackExplanation
from app.services.tutor_validation import MalformedOutputError, parse_json_object  # noqa: F401

BODY_TERMS = frozenset(
    """thumb index middle ring little pinky finger fingers fingertip fingertips knuckle knuckles
    palm wrist elbow shoulder shoulders arm arms hip hips knee knees ankle ankles foot feet leg legs
    neck head""".split()
)
VIDEO_TERMS = frozenset("video videos footage watched watching recording recordings filmed camera".split())

_WORD = re.compile(r"[a-z]+")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


class InvalidEvidenceCitationError(ValueError):
    pass


class InventedDetailError(ValueError):
    pass


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.casefold()))


def _output_text(explanation: FeedbackExplanation) -> str:
    parts = [explanation.overall_summary]
    parts += [o.text for o in explanation.observations]
    parts += [s.text for s in explanation.suggestions]
    return " ".join(parts)


def allowed_numbers(items: list[EvidenceItem]) -> set[float]:
    allowed: set[float] = set()
    for item in items:
        for raw in _NUMBER.findall(item.statement):
            value = float(raw)
            allowed.add(round(value, 2))
            if 0 < value <= 1:  # 0.71 may be written as 71%
                allowed.add(round(value * 100, 2))
                allowed.add(float(round(value * 100)))
    return allowed


def check_citations(explanation: FeedbackExplanation, items: list[EvidenceItem]) -> None:
    valid = {i.evidence_id for i in items}
    for entry in [*explanation.observations, *explanation.suggestions]:
        if not entry.evidence_ids:
            raise InvalidEvidenceCitationError("An observation or suggestion has no evidence citation.")
        if set(entry.evidence_ids) - valid:
            raise InvalidEvidenceCitationError("An entry cites an evidence id that does not exist.")


def check_no_invented_details(explanation: FeedbackExplanation, items: list[EvidenceItem]) -> None:
    evidence_text = " ".join(i.statement for i in items)
    output_text = _output_text(explanation)

    risky = (_tokens(output_text) & (BODY_TERMS | VIDEO_TERMS)) - _tokens(evidence_text)
    if risky:
        raise InventedDetailError("The feedback mentions details that are not in the evidence.")

    invented = {round(float(n), 2) for n in _NUMBER.findall(output_text)} - allowed_numbers(items)
    if invented:
        raise InventedDetailError("The feedback contains a number that is not in the evidence.")


def validate_feedback(raw: dict, items: list[EvidenceItem]) -> FeedbackExplanation:
    try:
        explanation = FeedbackExplanation.model_validate(raw)
    except ValidationError:
        raise MalformedOutputError("The model output does not match the expected structure.") from None
    check_citations(explanation, items)
    check_no_invented_details(explanation, items)
    return explanation
