"""Decide what the evaluation evidence can and cannot support. Pure functions, no I/O.

Nothing here invents a metric, label, deviation or timestamp: every statement is derived from
fields the evaluation module actually supplied. Numeric cut-offs below are CONSERVATIVE
DEFAULTS chosen by Member 2 (not calibrated); agree final values with the evaluation member.
"""
from app.core.enums import VerificationStatus
from app.schemas.evaluation import (
    Deviation,
    EvaluationResult,
    EvidenceAssessment,
    EvidenceLevel,
    LabelMatch,
    LandmarkQuality,
    PredictedLabel,
    ReferenceInfo,
)

LOW_CONFIDENCE = 0.5
LANDMARK_UNRELIABLE_BELOW = 0.5  # only used when `reliable` is not stated by the evaluation module

MOCK_NOTE = "MOCK TEST DATA: this was not produced by a real evaluation."
DTW_NOTE = (
    "DTW measures how closely the movement sequence aligns with the reference sequence. "
    "It does not identify what is wrong."
)
MISMATCH_NO_DETAIL = (
    "A mismatch with the expected label was reported, but no specific finger or joint deviation "
    "was provided, so the cause cannot be stated."
)


def _norm(text: str) -> str:
    return " ".join(text.casefold().split())


def top_prediction(predictions: list[PredictedLabel]) -> PredictedLabel | None:
    """Highest-confidence prediction; predictions without confidence rank last."""
    if not predictions:
        return None
    return max(predictions, key=lambda p: (p.confidence is not None, p.confidence or 0.0))


def compare_labels(expected: list[str], predictions: list[PredictedLabel]) -> LabelMatch:
    top = top_prediction(predictions)
    if not expected or top is None:
        return LabelMatch.UNKNOWN
    expected_set = {_norm(e) for e in expected}
    return LabelMatch.MATCH if _norm(top.label) in expected_set else LabelMatch.MISMATCH


def landmark_reliability(quality: LandmarkQuality | None) -> tuple[bool | None, str | None]:
    """Return (reliable or None if unknown, optional note)."""
    if quality is None:
        return None, "No landmark-quality information was provided."
    if quality.reliable is not None:
        return quality.reliable, None
    rates = [r for r in (quality.hand_detection_rate, quality.pose_detection_rate) if r is not None]
    if not rates:
        return None, "No landmark-quality information was provided."
    return (
        min(rates) >= LANDMARK_UNRELIABLE_BELOW,
        "Landmark reliability was not stated by the evaluation module; it was estimated from the detection rates.",
    )


def split_deviations(deviations: list[Deviation]) -> tuple[list[Deviation], list[Deviation]]:
    """(specific, general). Specific = names a body part or gives a measurement."""
    specific = [d for d in deviations if d.body_part or d.measured_value is not None]
    general = [d for d in deviations if d not in specific]
    return specific, general


def assess(result: EvaluationResult, reference: ReferenceInfo) -> EvidenceAssessment:
    limitations: list[str] = []
    if result.is_mock:
        limitations.append(MOCK_NOTE)

    # --- classifier evidence ---
    top = top_prediction(result.predicted_labels)
    match = compare_labels(result.expected_labels, result.predicted_labels)
    low_confidence = False
    if top is None:
        limitations.append("No predicted label was provided, so gesture recognition cannot be discussed.")
    else:
        if top.confidence is None:
            limitations.append("No confidence value was provided for the predicted label.")
        elif top.confidence < LOW_CONFIDENCE:
            low_confidence = True
            limitations.append(
                f"The classifier's confidence is low ({top.confidence:.2f}); treat the predicted label with caution."
            )
    if not result.expected_labels:
        limitations.append("No expected label was provided, so the prediction cannot be compared.")

    # --- sequence evidence ---
    dtw_available = result.dtw is not None
    limitations.append(DTW_NOTE if dtw_available else "No DTW comparison was provided.")

    # --- landmark quality ---
    reliable, landmark_note = landmark_reliability(result.landmark_quality)
    if landmark_note:
        limitations.append(landmark_note)
    if reliable is False:
        limitations.append("Landmark detection was unreliable, so the findings may not reflect the performance.")

    # --- deviations ---
    specific, general = split_deviations(result.deviations)
    if match == LabelMatch.MISMATCH and not specific:
        limitations.append(MISMATCH_NO_DETAIL)
    if general:
        limitations.append(
            "Some deviation records have no body part or measurement, so they can only be described in general terms."
        )

    # --- reference ---
    if not reference.instructions_available:
        limitations.append(
            "No verified practice instructions are available for this reference, so advice cannot "
            "be tied to reference instructions."
        )
    if reference.verification_status != VerificationStatus.VERIFIED:
        limitations.append(
            f"The reference record is not verified (status: {reference.verification_status.value})."
        )

    # --- warnings from the evaluation module ---
    for warning in result.warnings:
        limitations.append(f"Evaluation module warning: {warning}")

    # --- overall level ---
    has_any_evidence = bool(result.predicted_labels) or dtw_available or bool(result.deviations)
    if reliable is False or not has_any_evidence:
        level = EvidenceLevel.INSUFFICIENT
    elif reliable is True and match != LabelMatch.UNKNOWN and dtw_available and not low_confidence:
        level = EvidenceLevel.SUFFICIENT
    else:
        level = EvidenceLevel.LIMITED

    return EvidenceAssessment(
        level=level,
        label_match=match,
        top_label=top.label if top else None,
        top_confidence=top.confidence if top else None,
        dtw_available=dtw_available,
        landmarks_reliable=reliable,
        specific_deviations=specific,
        general_deviations=general,
        can_name_specific_error=bool(specific),
        limitations=limitations,
    )
