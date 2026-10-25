"""Evidence-only feedback built with fixed templates. No AI text; invents nothing."""
from app.core.enums import TutorFallbackReason
from app.schemas.evaluation import EvidenceLevel, LabelMatch, ValidatedEvidence
from app.schemas.feedback import EvidenceItem, FeedbackBody, Observation, Suggestion

NOTICE = {
    TutorFallbackReason.INSUFFICIENT_EVIDENCE: (
        "There is not enough reliable evidence from this session to give corrective feedback."
    ),
    TutorFallbackReason.NOT_CONFIGURED: (
        "The AI feedback service is not configured, so this shows the evaluation findings only."
    ),
}
DEFAULT_NOTICE = "The AI feedback is temporarily unavailable, so this shows the evaluation findings only."

CAPTURE_SUGGESTION = (
    "Try another attempt with your hands clearly in view and well lit, then compare again."
)
PRACTICE_SUFFIX = " This is reference-based practice assistance, not expert judgement."


def notice_for(reason: TutorFallbackReason) -> str:
    return NOTICE.get(reason, DEFAULT_NOTICE)


def _summary(ev: ValidatedEvidence) -> str:
    a = ev.assessment
    prefix = "MOCK TEST DATA. " if ev.is_mock else ""
    if a.level == EvidenceLevel.INSUFFICIENT:
        return prefix + "There is not enough reliable evidence from this practice session to give corrective feedback."
    if a.label_match == LabelMatch.MATCH:
        body = "The evaluation's top prediction matched the expected label for this reference."
    elif a.label_match == LabelMatch.MISMATCH:
        body = "The evaluation's top prediction did not match the expected label for this reference."
        if not a.can_name_specific_error:
            body += " The evaluation did not identify which finger or joint differs."
    else:
        body = "The evaluation could not compare the prediction with an expected label."
    return prefix + body + PRACTICE_SUFFIX


def build_evidence_only_feedback(ev: ValidatedEvidence, items: list[EvidenceItem]) -> FeedbackBody:
    by_id = {i.evidence_id: i for i in items}

    # Observations simply restate the evidence items, each citing itself. When the evidence is
    # insufficient (e.g. unreliable landmarks) findings built on that data, such as a label
    # "match", could mislead, so only the reason is stated. The rest stays in supporting_evidence.
    if ev.assessment.level == EvidenceLevel.INSUFFICIENT:
        kinds = ("landmarks",)
    else:
        kinds = ("label", "dtw", "deviation", "landmarks")
    observations = [
        Observation(text=i.statement, evidence_ids=[i.evidence_id]) for i in items if i.kind in kinds
    ][:8]

    # Suggestions are limited to: the reference instructions, reported specific deviations,
    # and capture advice when the evaluation module says landmarks were unreliable.
    suggestions: list[Suggestion] = []
    instructions = by_id.get("reference_instructions")
    if instructions is not None and ev.assessment.level != EvidenceLevel.INSUFFICIENT:
        suggestions.append(Suggestion(
            text="Compare your practice with the reference practice instructions. " + instructions.statement,
            evidence_ids=["reference_instructions"],
        ))
    for dev in ev.assessment.specific_deviations[:3]:
        item = by_id.get(f"deviation:{dev.deviation_id}")
        if item is not None:
            suggestions.append(Suggestion(
                text="Review this reported difference: " + item.statement,
                evidence_ids=[item.evidence_id],
            ))
    if ev.assessment.landmarks_reliable is False and "landmarks" in by_id:
        suggestions.append(Suggestion(text=CAPTURE_SUGGESTION, evidence_ids=["landmarks"]))

    return FeedbackBody(
        overall_summary=_summary(ev),
        observations=observations,
        suggestions=suggestions[:5],
        limitations=ev.assessment.limitations[:40],
    )
