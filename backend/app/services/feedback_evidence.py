"""Turn a ValidatedEvidence into numbered, plain-language evidence items. Pure functions.

Every statement is assembled ONLY from fields the evaluation module supplied (or from our own
database record for the reference). Gemini later receives these items and must cite their ids.
"""
from app.schemas.evaluation import ValidatedEvidence
from app.schemas.feedback import EvidenceItem
from app.services.tutor_prompt import clean_text

MAX_DEVIATIONS = 15
MAX_INSTRUCTION_CHARS = 600


def _fmt(value: float) -> str:
    return f"{value:g}"  # 0.71 -> "0.71", 28.0 -> "28"


def _interval_text(interval) -> str:
    if interval is None:
        return ""
    text = f" Frames {interval.start_frame} to {interval.end_frame}."
    if interval.start_time_s is not None and interval.end_time_s is not None:
        text += f" Seconds {_fmt(interval.start_time_s)} to {_fmt(interval.end_time_s)}."
    return text


def build_evidence_items(ev: ValidatedEvidence) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    result, ref, assessment = ev.result, ev.reference, ev.assessment

    if ev.is_mock:
        items.append(EvidenceItem(
            evidence_id="mock_notice", kind="warning",
            statement="MOCK TEST DATA: this was not produced by a real evaluation.",
        ))

    items.append(EvidenceItem(
        evidence_id="reference", kind="reference",
        statement=clean_text(
            f"Practised reference: {ref.name} ({ref.record_type}); "
            f"verification status: {ref.verification_status.value}."
        ),
    ))
    if ref.instructions_available and ref.practice_instructions:
        items.append(EvidenceItem(
            evidence_id="reference_instructions", kind="instructions",
            statement="Reference practice instructions: "
            + clean_text(ref.practice_instructions, MAX_INSTRUCTION_CHARS),
        ))

    if assessment.top_label:
        text = f"The classifier's top prediction was '{clean_text(assessment.top_label, 80)}'"
        if assessment.top_confidence is not None:
            text += f" (confidence {_fmt(assessment.top_confidence)})"
        if result.expected_labels:
            text += "; expected label(s): " + ", ".join(clean_text(x, 80) for x in result.expected_labels)
        text += f". Comparison result: {assessment.label_match.value}."
        items.append(EvidenceItem(evidence_id="label", kind="label", statement=text))

    if result.dtw is not None:
        d = result.dtw
        text = f"DTW alignment distance to the reference sequence: {_fmt(d.distance)}"
        if d.normalized_distance is not None:
            text += f" (normalized {_fmt(d.normalized_distance)})"
        text += "."
        if d.threshold is not None:
            text += f" Threshold supplied by the evaluation module: {_fmt(d.threshold)}."
        if d.within_threshold is not None:
            text += " The evaluation module reports the result is " + (
                "within the threshold." if d.within_threshold else "above the threshold."
            )
        items.append(EvidenceItem(evidence_id="dtw", kind="dtw", statement=text))

    for dev in result.deviations[:MAX_DEVIATIONS]:
        head = f"Deviation {clean_text(dev.deviation_id, 60)} ({dev.kind}"
        if dev.body_part:
            head += f", {clean_text(dev.body_part, 60)}"
        if dev.severity:
            head += f", {dev.severity}"
        text = f"{head}): {clean_text(dev.description, 300)}"
        unit = f" {clean_text(dev.unit, 20)}" if dev.unit else ""
        if dev.measured_value is not None and dev.reference_value is not None:
            text += f" Measured {_fmt(dev.measured_value)}{unit} versus reference {_fmt(dev.reference_value)}{unit}."
        elif dev.measured_value is not None:
            text += f" Measured {_fmt(dev.measured_value)}{unit}."
        text += _interval_text(dev.interval)
        items.append(EvidenceItem(evidence_id=f"deviation:{dev.deviation_id}", kind="deviation", statement=text))
    omitted = len(result.deviations) - MAX_DEVIATIONS
    if omitted > 0:
        items.append(EvidenceItem(
            evidence_id="deviations_omitted", kind="warning",
            statement=f"{omitted} further deviation record(s) were left out to keep this short.",
        ))

    q = result.landmark_quality
    if q is not None:
        parts = []
        if q.hand_detection_rate is not None:
            parts.append(f"hand detection rate {_fmt(q.hand_detection_rate)}")
        if q.pose_detection_rate is not None:
            parts.append(f"pose detection rate {_fmt(q.pose_detection_rate)}")
        if q.frames_analysed is not None and q.frames_total is not None:
            parts.append(f"{q.frames_analysed} of {q.frames_total} frames analysed")
        if q.reliable is not None:
            parts.append("landmarks reported as " + ("reliable" if q.reliable else "unreliable"))
        for note in q.notes[:3]:
            parts.append(clean_text(note, 120))
        if parts:
            items.append(EvidenceItem(
                evidence_id="landmarks", kind="landmarks",
                statement="Landmark detection quality: " + "; ".join(parts) + ".",
            ))

    for index, warning in enumerate(result.warnings, start=1):
        items.append(EvidenceItem(
            evidence_id=f"warning:{index}", kind="warning",
            statement="Evaluation module warning: " + clean_text(warning, 200),
        ))
    return items
