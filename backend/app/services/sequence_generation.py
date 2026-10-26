"""Deterministic sentence-to-mudra sequencing over retrieved, cited evidence.

This module intentionally does not add an HTTP response field. The frozen frontend's
existing retrieve contract is concept-grouped; a caller can use this result internally
or adopt a future versioned sequence contract after approval.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from app.core.enums import MatchType, VerificationStatus
from app.schemas.knowledge import RetrievalResponse, RetrievedReference
from app.services.knowledge_matching import MATCH_PRIORITY


class SequenceAlternative(BaseModel):
    mudra_id: str
    mudra_name: str
    reason: str
    source_id: str | None = None
    verification_status: VerificationStatus


class SequenceStep(BaseModel):
    position: int
    sentence_index: int
    related_word: str
    related_words: list[str] = Field(default_factory=list)
    mudra_id: str
    mudra_name: str
    reason: str
    context: list[str] = Field(default_factory=list)
    source_id: str | None = None
    source_url: str | None = None
    verification_status: VerificationStatus
    evidence_kind: Literal["source_supported", "unverified"]
    inferred: bool = False
    reference_image_path: str | None = None
    uncertainty: list[str] = Field(default_factory=list)
    alternatives: list[SequenceAlternative] = Field(default_factory=list)


class UnmappedConcept(BaseModel):
    word: str
    sentence_index: int
    reason: str


class MudraSequence(BaseModel):
    original_text: str
    steps: list[SequenceStep] = Field(default_factory=list)
    unmapped_concepts: list[UnmappedConcept] = Field(default_factory=list)
    generation_mode: Literal["deterministic_retrieval"] = "deterministic_retrieval"
    ai_enhanced: Literal[False] = False
    disclaimer: str = (
        "This is an ordered learning aid from cited knowledge-base matches, not a canonical "
        "Bharatanatyam choreography or teacher-approved transition sequence."
    )


def _sentence_index(text: str, offset: int) -> int:
    prefix = text[:offset]
    return len(re.findall(r"[.!?](?:[\"')\]]*)\s+", prefix))


def _rank(reference: RetrievedReference, concept: str) -> tuple[int, int, int, str]:
    status_rank = {
        VerificationStatus.VERIFIED: 0,
        VerificationStatus.SOURCE_CITED: 1,
        VerificationStatus.UNVERIFIED: 2,
    }[reference.verification_status]
    normalized_concept = concept.casefold()
    exact_context_penalty = 0 if any(normalized_concept in row.casefold() for row in reference.relationships) else 1
    return (
        status_rank,
        MATCH_PRIORITY[reference.match_type],
        exact_context_penalty,
        reference.record_id,
    )


def generate_mudra_sequence(retrieval: RetrievalResponse) -> MudraSequence:
    """Order supported mudra candidates by first mention; retain alternatives and evidence.

    One primary step is emitted per distinct mudra, so repeated concepts do not make a
    learner repeat the same hand shape. Unsupported concepts are preserved explicitly.
    """
    output = MudraSequence(original_text=retrieval.original_text)
    emitted: dict[str, int] = {}

    for resolved in retrieval.concepts:
        concept = resolved.concept
        offset = min((mention.start for mention in concept.mentions), default=0)
        sentence = _sentence_index(retrieval.original_text, offset)
        candidates = [
            reference for reference in resolved.references
            if reference.record_type == "mudra"
        ]
        if not candidates:
            output.unmapped_concepts.append(UnmappedConcept(
                word=concept.text,
                sentence_index=sentence,
                reason=resolved.note or "No source-backed mudra mapping is curated for this concept.",
            ))
            continue

        ranked = sorted(candidates, key=lambda ref: _rank(ref, concept.normalized))
        primary = next((item for item in ranked if item.record_id not in emitted), None)
        if primary is None:
            duplicate = next((item for item in ranked if item.record_id in emitted), None)
            if duplicate is not None:
                step = output.steps[emitted[duplicate.record_id]]
                if concept.text not in step.related_words:
                    step.related_words.append(concept.text)
            continue
        emitted[primary.record_id] = len(output.steps)
        source = primary.mapping_source or primary.source
        evidence_kind = (
            "source_supported"
            if source is not None and primary.verification_status != VerificationStatus.UNVERIFIED
            else "unverified"
        )
        reason = (
            primary.relationships[0]
            if primary.relationships
            else f"Matched the entered concept to the listed {primary.match_type.value.replace('_', ' ')}."
        )
        alternatives = [SequenceAlternative(
            mudra_id=ref.record_id,
            mudra_name=ref.name,
            reason=(ref.relationships[0] if ref.relationships else f"Also matched by {ref.match_type.value.replace('_', ' ')}."),
            source_id=(ref.mapping_source or ref.source).id if (ref.mapping_source or ref.source) else None,
            verification_status=ref.verification_status,
        ) for ref in ranked if ref.record_id != primary.record_id]
        output.steps.append(SequenceStep(
            position=len(output.steps) + 1,
            sentence_index=sentence,
            related_word=concept.text,
            related_words=[concept.text],
            mudra_id=primary.record_id,
            mudra_name=primary.name,
            reason=reason,
            context=primary.usage,
            source_id=source.id if source else None,
            source_url=source.source_url if source else None,
            verification_status=primary.verification_status,
            evidence_kind=evidence_kind,
            reference_image_path=primary.reference_media_path,
            uncertainty=list(primary.limitations),
            alternatives=alternatives,
        ))

    return output
