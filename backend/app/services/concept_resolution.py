"""Connects extracted concepts to the knowledge base (the retrieval interface).

Part 3 only answers: "does the knowledge base have an explicit mapping for this concept?"
Part 4 builds full retrieval (mudra/movement records, sources, ranking) on top of it.

Known gap handled in Part 4: a mapping is reported even if the mudra it points to is not
trusted. Part 4 will re-check the target record before presenting it.
"""
from sqlalchemy.orm import Session

from app.db.models import VerificationStatus
from app.repositories import knowledge_repository as repo
from app.schemas.concepts import (
    ConceptSupportStatus,
    ExtractionResult,
    ResolutionResult,
    ResolvedConcept,
)

NO_SUPPORT_NOTE = (
    "No supported reference was found in the knowledge base. "
    "This does not prove that no traditional gesture exists for this concept."
)


def resolve_concepts(
    db: Session,
    extraction: ExtractionResult,
    *,
    include_unverified: bool = False,
) -> ResolutionResult:
    resolved: list[ResolvedConcept] = []

    for concept in extraction.concepts:
        mappings = {}
        matched_keys: list[str] = []
        for key in concept.lookup_keys:
            found = repo.get_mappings_for_concept(
                db, key, include_unverified=include_unverified, include_source_cited=True
            )
            if found:
                matched_keys.append(key)
            for m in found:
                mappings.setdefault(m.id, m)

        if not mappings:
            resolved.append(
                ResolvedConcept(
                    concept=concept,
                    status=ConceptSupportStatus.UNSUPPORTED,
                    note=NO_SUPPORT_NOTE,
                )
            )
            continue

        ordered = sorted(mappings.values(), key=lambda m: m.id)
        resolved.append(
            ResolvedConcept(
                concept=concept,
                status=ConceptSupportStatus.SUPPORTED,
                matched_keys=matched_keys,
                mapping_ids=[m.id for m in ordered],
                mudra_ids=sorted({m.mudra_id for m in ordered if m.mudra_id}),
                movement_ids=sorted({m.movement_id for m in ordered if m.movement_id}),
                contains_unverified=any(
                    m.verification_status != VerificationStatus.VERIFIED for m in ordered
                ),
            )
        )

    supported = sum(r.status == ConceptSupportStatus.SUPPORTED for r in resolved)
    return ResolutionResult(
        original_text=extraction.original_text,
        include_unverified=include_unverified,
        concepts=resolved,
        supported_count=supported,
        unsupported_count=len(resolved) - supported,
        warnings=list(extraction.warnings),
    )
