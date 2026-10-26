"""Knowledge retrieval: extracted concepts -> supported mudras/movements.

Order of evidence, strongest first:
  explicit concept mapping > exact name > alternate name > listed usage > usage keyword
Multiple matches are all returned (alternatives), never collapsed to one "right" answer.

Decision: PostgreSQL full-text search is NOT used yet. The curated knowledge base is tiny
(tens of records), exact/alias/usage matching is faster to reason about and portable to the
SQLite test database. Revisit when the knowledge base is large or free-text search is needed.
"""
from dataclasses import dataclass, field
import json
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.enums import MatchType, VerificationStatus
from app.db.models import Movement, Mudra, Source
from app.db.seed import DEFAULT_ASSETS_DIR
from app.repositories import knowledge_repository as repo
from app.schemas.concepts import ConceptSupportStatus, ExtractedConcept
from app.schemas.knowledge import (
    ConceptRetrieval,
    MovementOut,
    MudraOut,
    RetrievalResponse,
    RetrievedReference,
    SourceOut,
)
from app.services.concept_extraction import extract_concepts
from app.services.concept_resolution import NO_SUPPORT_NOTE
from app.services.knowledge_matching import (
    MATCH_PRIORITY,
    build_limitations,
    match_record,
    weakest_status,
)

MAX_RECORDS_SCANNED = 1000
MULTIPLE_NOTE = (
    "Several references match this concept. They are alternatives, "
    "not a single correct answer."
)
DATASET_MAPPING_PATH = Path(__file__).resolve().parents[2] / "data" / "seed" / "dataset_mapping.json"


@lru_cache(maxsize=1)
def dataset_image_counts() -> dict[str, int]:
    """Counts from the generated, checked-in folder crosswalk; images stay outside the repo."""
    try:
        rows = json.loads(DATASET_MAPPING_PATH.read_text(encoding="utf-8"))["class_folders"]
    except (OSError, KeyError, json.JSONDecodeError):
        return {}
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["mudra_id"]] = counts.get(row["mudra_id"], 0) + int(row.get("image_count", 0))
    return counts


@lru_cache(maxsize=1)
def dataset_classes_by_mudra() -> dict[str, list[dict]]:
    try:
        rows = json.loads(DATASET_MAPPING_PATH.read_text(encoding="utf-8"))["class_folders"]
    except (OSError, KeyError, json.JSONDecodeError):
        return {}
    result: dict[str, list[dict]] = {}
    for row in rows:
        result.setdefault(row["mudra_id"], []).append(row)
    return result


# ---------- serialization helpers ----------
def media_available(path: str | None, assets_dir: Path = DEFAULT_ASSETS_DIR) -> bool:
    """True only if the file exists INSIDE the assets directory (blocks ../ tricks)."""
    if not path:
        return False
    root = assets_dir.resolve()
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return candidate.is_file()


def media_url_path(path: str | None, assets_dir: Path = DEFAULT_ASSETS_DIR) -> str | None:
    """Return a same-backend static URL only for an existing, contained asset."""
    if not media_available(path, assets_dir):
        return None
    return f"/static/{Path(path).as_posix().lstrip('/')}"


def source_to_out(source: Source | None) -> SourceOut | None:
    if source is None:
        return None
    return SourceOut(
        id=source.id,
        source_name=source.source_name,
        source_url=source.source_url,
        source_type=source.source_type,
        author_or_organization=source.author_or_organization,
        publication_date=source.publication_date,
        access_date=source.access_date,
        license_or_usage_notes=source.license_or_usage_notes,
        reliability_notes=source.reliability_notes,
    )


def mudra_to_out(m: Mudra, assets_dir: Path = DEFAULT_ASSETS_DIR) -> MudraOut:
    available = media_available(m.reference_image_path, assets_dir)
    image_count = dataset_image_counts().get(m.id, 0)
    dataset_classes = sorted(dataset_classes_by_mudra().get(m.id, []), key=lambda row: row["dataset_folder"])
    return MudraOut(
        id=m.id,
        name=m.name,
        alternate_names=list(m.alternate_names or []),
        category=m.category,
        meaning=m.meaning,
        usage=list(m.usage or []),
        description=m.description,
        practice_instructions=m.practice_instructions,
        reference_image_path=media_url_path(m.reference_image_path, assets_dir),
        dataset_image_count=image_count,
        dataset_images_available=image_count > 0,
        dataset_classes=[{
            "dataset_folder": row["dataset_folder"],
            "original_label": row["original_label"],
            "variant_id": row.get("variant_id"),
            "image_count": int(row.get("image_count", 0)),
            "mapping_status": row["mapping_status"],
        } for row in dataset_classes],
        # The repository has a training pipeline but no loaded inference model/API artifact.
        recognition_supported=False,
        source=source_to_out(m.source),
        verification_status=m.verification_status,
        verification_notes=m.verification_notes,
        limitations=build_limitations(
            m.verification_status,
            has_source=m.source is not None,
            media_listed=bool(m.reference_image_path),
            media_available=available,
            has_instructions=bool(m.practice_instructions),
        ),
    )


def movement_to_out(m: Movement, assets_dir: Path = DEFAULT_ASSETS_DIR) -> MovementOut:
    available = media_available(m.reference_media_path, assets_dir)
    return MovementOut(
        id=m.id,
        name=m.name,
        description=m.description,
        movement_category=m.movement_category,
        practice_instructions=m.practice_instructions,
        reference_media_path=media_url_path(m.reference_media_path, assets_dir),
        source=source_to_out(m.source),
        verification_status=m.verification_status,
        verification_notes=m.verification_notes,
        limitations=build_limitations(
            m.verification_status,
            has_source=m.source is not None,
            media_listed=bool(m.reference_media_path),
            media_available=available,
            has_instructions=bool(m.practice_instructions),
        ),
    )


# ---------- retrieval ----------
@dataclass
class _Candidate:
    record: Mudra | Movement
    record_type: str
    match_type: MatchType
    mapping_ids: list[str] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)
    interpretation_types: list[str] = field(default_factory=list)
    evidence_notes: list[str] = field(default_factory=list)
    mapping_statuses: list[VerificationStatus] = field(default_factory=list)
    mapping_source: Source | None = None

    def add_match(self, match_type: MatchType) -> None:
        if MATCH_PRIORITY[match_type] < MATCH_PRIORITY[self.match_type]:
            self.match_type = match_type


def _collect(
    db: Session,
    concept: ExtractedConcept,
    mudras: list[Mudra],
    movements: list[Movement],
    *,
    include_unverified: bool,
    include_keyword: bool,
) -> list[_Candidate]:
    candidates: dict[tuple[str, str], _Candidate] = {}
    seen_mappings: set[str] = set()

    # 1) Explicit curated mappings. The mapped target is re-checked so a trusted mapping
    #    can never smuggle in an untrusted (or missing) mudra/movement.
    for key in concept.lookup_keys:
        for mapping in repo.get_mappings_for_concept(
            db, key, include_unverified=include_unverified, include_source_cited=True
        ):
            if mapping.id in seen_mappings:
                continue
            seen_mappings.add(mapping.id)
            targets = []
            if mapping.mudra_id:
                targets.append(
                    ("mudra", repo.get_mudra(db, mapping.mudra_id, include_unverified=include_unverified, include_source_cited=True))
                )
            if mapping.movement_id:
                targets.append(
                    ("movement", repo.get_movement(db, mapping.movement_id, include_unverified=include_unverified, include_source_cited=True))
                )
            for record_type, record in targets:
                if record is None:
                    continue
                cand = candidates.setdefault(
                    (record_type, record.id),
                    _Candidate(record, record_type, MatchType.CONCEPT_MAPPING),
                )
                cand.add_match(MatchType.CONCEPT_MAPPING)
                cand.mapping_ids.append(mapping.id)
                if mapping.relationship_description:
                    cand.relationships.append(mapping.relationship_description)
                cand.interpretation_types.append(mapping.interpretation_type)
                if mapping.evidence_notes:
                    cand.evidence_notes.append(mapping.evidence_notes)
                cand.mapping_statuses.append(mapping.verification_status)
                if cand.mapping_source is None:
                    cand.mapping_source = mapping.source

    # 2) Name / alternate name / usage matching on the records themselves.
    for record_type, records in (("mudra", mudras), ("movement", movements)):
        for record in records:
            match_type = match_record(record, concept.lookup_keys, include_keyword=include_keyword)
            if match_type is None:
                continue
            existing = candidates.get((record_type, record.id))
            if existing is None:
                candidates[(record_type, record.id)] = _Candidate(record, record_type, match_type)
            else:
                existing.add_match(match_type)

    return list(candidates.values())


def _to_reference(cand: _Candidate, assets_dir: Path) -> RetrievedReference:
    rec = cand.record
    is_mudra = cand.record_type == "mudra"
    media_path = rec.reference_image_path if is_mudra else rec.reference_media_path
    available = media_available(media_path, assets_dir)
    status = weakest_status([rec.verification_status, *cand.mapping_statuses])

    limitations = build_limitations(
        status,
        has_source=rec.source is not None,
        media_listed=bool(media_path),
        media_available=available,
        has_instructions=bool(rec.practice_instructions),
        match_type=cand.match_type,
    )
    if cand.mapping_ids and cand.mapping_source is None:
        limitations.append("The concept mapping has no source recorded.")

    return RetrievedReference(
        record_type=cand.record_type,
        record_id=rec.id,
        name=rec.name,
        category=rec.category if is_mudra else rec.movement_category,
        meaning=rec.meaning if is_mudra else None,
        description=rec.description,
        usage=list(rec.usage or []) if is_mudra else [],
        practice_instructions=rec.practice_instructions,
        reference_media_path=media_url_path(media_path, assets_dir),
        match_type=cand.match_type,
        mapping_ids=sorted(set(cand.mapping_ids)),
        relationships=cand.relationships,
        interpretation_types=sorted(set(cand.interpretation_types)),
        evidence_notes=cand.evidence_notes,
        verification_status=status,
        source=source_to_out(rec.source),
        mapping_source=source_to_out(cand.mapping_source),
        limitations=limitations,
    )


def retrieve_for_text(
    db: Session,
    text: str,
    *,
    include_unverified: bool = False,
    include_keyword_matches: bool = False,
    assets_dir: Path = DEFAULT_ASSETS_DIR,
) -> RetrievalResponse:
    """Full Part 3 + Part 4 flow. Raises InputValidationError for unusable input."""
    extraction = extract_concepts(text)
    mudras = repo.list_mudras(db, include_unverified=include_unverified, include_source_cited=True, limit=MAX_RECORDS_SCANNED)
    movements = repo.list_movements(db, include_unverified=include_unverified, include_source_cited=True, limit=MAX_RECORDS_SCANNED)

    results: list[ConceptRetrieval] = []
    for concept in extraction.concepts:
        candidates = _collect(
            db, concept, mudras, movements,
            include_unverified=include_unverified,
            include_keyword=include_keyword_matches,
        )
        references = sorted(
            (_to_reference(c, assets_dir) for c in candidates),
            key=lambda r: (MATCH_PRIORITY[r.match_type], r.name),
        )
        if not references:
            results.append(
                ConceptRetrieval(
                    concept=concept, status=ConceptSupportStatus.UNSUPPORTED, note=NO_SUPPORT_NOTE
                )
            )
            continue
        results.append(
            ConceptRetrieval(
                concept=concept,
                status=ConceptSupportStatus.SUPPORTED,
                references=references,
                contains_unverified=any(
                    r.verification_status != VerificationStatus.VERIFIED for r in references
                ),
                note=MULTIPLE_NOTE if len(references) > 1 else None,
            )
        )

    supported = sum(r.status == ConceptSupportStatus.SUPPORTED for r in results)
    return RetrievalResponse(
        original_text=extraction.original_text,
        include_unverified=include_unverified,
        include_keyword_matches=include_keyword_matches,
        concepts=results,
        supported_count=supported,
        unsupported_count=len(results) - supported,
        warnings=list(extraction.warnings),
    )
