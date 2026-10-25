"""Evaluation harness for the RAG pipeline.

Two kinds of checks:
  AUTOMATED (this file): did retrieval find what the labelled case expects, and does the
  answer obey hard rules (no invented support, no forbidden terms, valid citations, mentions
  unverified status)? These are regression checks, NOT proof of domain correctness: the
  expectations come from the current knowledge-base contents.
  HUMAN (review sheet): relevance and faithfulness of the wording need a person (ideally your
  Bharatanatyam teacher). The sheet leaves those columns blank. No score is invented here.
"""
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.core.enums import TutorFallbackReason, VerificationStatus
from app.schemas.concepts import ConceptSupportStatus
from app.schemas.knowledge import RetrievalResponse
from app.schemas.tutor import TutorResult
from app.services.tutor_prompt import collect_citable_ids
from app.services.tutor_service import TutorService

DEFAULT_CASES_PATH = Path(__file__).resolve().parents[2] / "data" / "eval" / "rag_queries.json"


@dataclass
class EvalCase:
    id: str
    text: str
    expect_supported: list[str] = field(default_factory=list)
    expect_unsupported: list[str] = field(default_factory=list)
    expect_record_ids: list[str] = field(default_factory=list)
    forbidden_terms: list[str] = field(default_factory=list)
    note: str = ""
    known_limitation: bool = False


@dataclass
class CaseReport:
    case: EvalCase
    retrieval: RetrievalResponse
    result: TutorResult
    retrieval_problems: list[str]
    tutor_problems: list[str]

    @property
    def passed(self) -> bool:
        return not self.retrieval_problems and not self.tutor_problems


def load_cases(path: Path = DEFAULT_CASES_PATH) -> list[EvalCase]:
    with open(path, encoding="utf-8") as f:
        return [EvalCase(**item) for item in json.load(f)]


def check_retrieval(case: EvalCase, retrieval: RetrievalResponse) -> list[str]:
    problems: list[str] = []
    by_norm = {c.concept.normalized: c for c in retrieval.concepts}

    for name in case.expect_supported:
        c = by_norm.get(name)
        if c is None:
            problems.append(f"expected concept '{name}' was not extracted")
        elif c.status != ConceptSupportStatus.SUPPORTED:
            problems.append(f"expected '{name}' to be supported but it was not")
    for name in case.expect_unsupported:
        c = by_norm.get(name)
        if c is None:
            problems.append(f"expected concept '{name}' was not extracted")
        elif c.status != ConceptSupportStatus.UNSUPPORTED:
            problems.append(f"'{name}' should be unsupported but a reference was returned")

    allowed_support = set(case.expect_supported)
    for name, c in by_norm.items():
        if c.status == ConceptSupportStatus.SUPPORTED and name not in allowed_support:
            problems.append(f"unexpected support for '{name}' (possible invented mapping)")

    found_ids = {r.record_id for c in retrieval.concepts for r in c.references}
    for rid in case.expect_record_ids:
        if rid not in found_ids:
            problems.append(f"expected record '{rid}' was not retrieved")
    return problems


def _all_text(result: TutorResult) -> str:
    ex = result.explanation
    parts = [ex.summary, *ex.suggestions, *ex.alternatives, *ex.limitations]
    parts += [c.explanation for c in ex.concepts]
    return " ".join(parts).lower()


def check_tutor_result(case: EvalCase, retrieval: RetrievalResponse, result: TutorResult) -> list[str]:
    problems: list[str] = []
    has_refs = any(c.references for c in retrieval.concepts)

    if not has_refs:
        if result.mode != "knowledge_only" or result.fallback_reason != TutorFallbackReason.NO_REFERENCES:
            problems.append("nothing was retrieved, so Gemini should not have been used")

    text = _all_text(result)
    for term in case.forbidden_terms:
        if term.lower() in text:
            problems.append(f"forbidden term appears in the answer: '{term}'")

    unsupported = {
        c.concept.normalized for c in retrieval.concepts if c.status == ConceptSupportStatus.UNSUPPORTED
    }
    for item in result.explanation.concepts:
        if item.supported and item.concept.strip().lower() in unsupported:
            problems.append(f"answer claims support for unsupported concept '{item.concept}'")

    allowed = collect_citable_ids(retrieval)
    for sid in result.explanation.source_ids:
        if sid not in allowed:
            problems.append(f"answer cites unknown id '{sid}'")

    any_unverified = any(
        r.verification_status != VerificationStatus.VERIFIED for c in retrieval.concepts for r in c.references
    )
    if any_unverified and "verif" not in text:
        problems.append("references are not verified but the answer never says so (keyword heuristic)")
    return problems


def evaluate(
    cases: list[EvalCase],
    retrieve: Callable[[str], RetrievalResponse],
    tutor: TutorService,
) -> list[CaseReport]:
    reports = []
    for case in cases:
        retrieval = retrieve(case.text)
        result = tutor.explain(retrieval)
        reports.append(
            CaseReport(
                case=case,
                retrieval=retrieval,
                result=result,
                retrieval_problems=check_retrieval(case, retrieval),
                tutor_problems=check_tutor_result(case, retrieval, result),
            )
        )
    return reports


def render_review_sheet(reports: list[CaseReport]) -> str:
    lines = [
        "# NrityaGuru RAG review sheet",
        "",
        "Automated results below are regression checks only. The HUMAN columns are blank on purpose:",
        "please score relevance and faithfulness yourself (ideally with your Bharatanatyam teacher).",
        "",
    ]
    for r in reports:
        ex = r.result.explanation
        ids = sorted({x.record_id for c in r.retrieval.concepts for x in c.references}) or ["none"]
        lines += [
            f"## {r.case.id}: {r.case.text!r}",
            f"- mode: **{r.result.mode}**" + (f" (reason: {r.result.fallback_reason.value})" if r.result.fallback_reason else ""),
            f"- retrieved record ids: {', '.join(ids)}",
            f"- automated checks: **{'PASS' if r.passed else 'FAIL'}**",
        ]
        for p in [*r.retrieval_problems, *r.tutor_problems]:
            lines.append(f"  - problem: {p}")
        if r.case.known_limitation:
            lines.append(f"- known limitation: {r.case.note}")
        lines += [
            "",
            f"> {ex.summary}",
            "",
            "- HUMAN relevance (1-5): ____",
            "- HUMAN faithful to the retrieved records? (Y/N): ____",
            "- HUMAN notes: ____",
            "",
        ]
    return "\n".join(lines)
