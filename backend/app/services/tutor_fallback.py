"""Deterministic 'knowledge only' explanation. Built from retrieved records with fixed
templates; contains no AI-written text and invents nothing."""
from app.core.enums import TutorFallbackReason, VerificationStatus
from app.schemas.knowledge import RetrievalResponse
from app.schemas.tutor import ConceptExplanation, TutorExplanation
from app.services.tutor_prompt import collect_citable_ids, shown_references

STATUS_TEXT = {
    VerificationStatus.VERIFIED: "verified",
    VerificationStatus.SOURCE_CITED: "from a cited source, not yet verified",
    VerificationStatus.UNVERIFIED: "unverified",
}

_UNAVAILABLE = (
    "The AI explanation is temporarily unavailable, so this shows the retrieved "
    "reference information only."
)

SUMMARY = {
    TutorFallbackReason.NO_REFERENCES: (
        "The knowledge base has no supported reference for these concepts yet, "
        "so there is nothing to explain."
    ),
    TutorFallbackReason.NOT_CONFIGURED: (
        "The AI explanation service is not configured, so this shows the retrieved "
        "reference information only."
    ),
}

NO_SUPPORT_TEXT = "No supported reference was found in the knowledge base for this concept."
NO_AI_LIMITATION = "No AI explanation was generated; this is retrieved reference information only."


def summary_for(reason: TutorFallbackReason) -> str:
    return SUMMARY.get(reason, _UNAVAILABLE)


def build_knowledge_only(retrieval: RetrievalResponse, reason: TutorFallbackReason) -> TutorExplanation:
    concepts: list[ConceptExplanation] = []
    alternatives: list[str] = []
    limitations: list[str] = []

    for cr in retrieval.concepts:
        refs = shown_references(cr)
        label = cr.concept.text[:120]
        if not refs:
            concepts.append(
                ConceptExplanation(concept=label, supported=False, explanation=NO_SUPPORT_TEXT, source_ids=[])
            )
            continue

        parts = []
        ids: set[str] = set()
        for ref in refs:
            piece = ref.name
            if ref.meaning:
                piece += f" (meaning: {ref.meaning})"
            piece += f", {STATUS_TEXT[ref.verification_status]}"
            parts.append(piece)
            ids.add(ref.record_id)
            if ref.source is not None:
                ids.add(ref.source.id)
            if ref.mapping_source is not None:
                ids.add(ref.mapping_source.id)
            for lim in ref.limitations:
                if lim not in limitations:
                    limitations.append(lim)

        concepts.append(
            ConceptExplanation(
                concept=label,
                supported=True,
                explanation=("Retrieved: " + "; ".join(parts) + ".")[:1200],
                source_ids=sorted(ids),
            )
        )
        if len(refs) > 1:
            alternatives.append(f"{label}: " + ", ".join(r.name for r in refs))

    limitations = [NO_AI_LIMITATION, *limitations][:20]
    return TutorExplanation(
        summary=summary_for(reason),
        concepts=concepts,
        suggestions=[],
        alternatives=alternatives[:10],
        source_ids=sorted(collect_citable_ids(retrieval))[:40],
        limitations=limitations,
    )
