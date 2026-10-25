"""Pure matching and labelling rules. No database, no framework imports.

Works on any object that has the attributes it reads (Mudra, Movement, or a test stand-in).
"""
from collections.abc import Iterable

from app.core.enums import MatchType, VerificationStatus
from app.services.text_processing import normalize_text

STATUS_RANK = {
    VerificationStatus.UNVERIFIED: 0,
    VerificationStatus.SOURCE_CITED: 1,
    VerificationStatus.VERIFIED: 2,
}

MATCH_PRIORITY = {
    MatchType.CONCEPT_MAPPING: 0,
    MatchType.EXACT_NAME: 1,
    MatchType.ALTERNATE_NAME: 2,
    MatchType.USAGE_LISTED: 3,
    MatchType.USAGE_KEYWORD: 4,
}


def weakest_status(statuses: Iterable[VerificationStatus]) -> VerificationStatus:
    """A result is only as trustworthy as its weakest ingredient."""
    return min(statuses, key=STATUS_RANK.__getitem__)


def match_record(
    record: object, keys: Iterable[str], *, include_keyword: bool = False
) -> MatchType | None:
    """Strongest name/alias/usage match of any key against one record, or None.

    Explicit concept mappings are handled separately (they live in their own table).
    Keyword matching (a word inside a usage phrase) is weak, so it is opt-in.
    """
    name = normalize_text(getattr(record, "name", "") or "")
    aliases = {normalize_text(a) for a in (getattr(record, "alternate_names", None) or [])}
    usages = [normalize_text(u) for u in (getattr(record, "usage", None) or [])]

    best: MatchType | None = None

    def consider(candidate: MatchType) -> None:
        nonlocal best
        if best is None or MATCH_PRIORITY[candidate] < MATCH_PRIORITY[best]:
            best = candidate

    for raw in keys:
        key = normalize_text(raw)
        if not key:
            continue
        if key == name:
            consider(MatchType.EXACT_NAME)
        elif key in aliases:
            consider(MatchType.ALTERNATE_NAME)
        elif key in usages:
            consider(MatchType.USAGE_LISTED)
        elif include_keyword and any(key in u.split() for u in usages):
            consider(MatchType.USAGE_KEYWORD)
    return best


def build_limitations(
    status: VerificationStatus,
    *,
    has_source: bool,
    media_listed: bool,
    media_available: bool,
    has_instructions: bool,
    match_type: MatchType | None = None,
) -> list[str]:
    """Plain-language caveats that travel with every retrieved record."""
    notes: list[str] = []
    if status == VerificationStatus.UNVERIFIED:
        notes.append("This record has no supporting source and is not verified.")
    elif status == VerificationStatus.SOURCE_CITED:
        notes.append(
            "Taken from a cited source but not yet cross-checked by an expert or a primary text."
        )
    if not has_source:
        notes.append("No source is recorded for this record.")
    if not media_listed:
        notes.append("No reference image or media is available yet.")
    elif not media_available:
        notes.append("A reference file is listed but was not found.")
    if not has_instructions:
        notes.append("No verified practice instructions are available yet.")
    if match_type == MatchType.USAGE_LISTED:
        notes.append(
            "Matched because the concept appears in the record's listed usages; "
            "there is no separate explicit mapping."
        )
    elif match_type == MatchType.USAGE_KEYWORD:
        notes.append(
            "Matched only by a single word inside a listed usage. This is weaker than an "
            "explicit mapping, so check that it is actually relevant."
        )
    return notes
