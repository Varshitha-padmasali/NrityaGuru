"""Run the labelled RAG evaluation set.  From backend/:   python -m scripts.evaluate_rag

Needs: PostgreSQL running and seeded (python -m app.db.seed).
With GEMINI_API_KEY set it uses the real model (about 8 calls); without it, the tutor returns
knowledge-only output, so the answer-level checks cover the fallback path only.
Writes eval_output/review_sheet.md for HUMAN scoring. It prints no quality percentage:
automated checks are regression checks, not proof of domain correctness.
"""
from functools import partial
from pathlib import Path

from app.core.config import get_settings
from app.db.database import DatabaseNotConfiguredError, get_sessionmaker
from app.services.knowledge_retrieval import retrieve_for_text
from app.services.rag_evaluation import evaluate, load_cases, render_review_sheet
from app.services.tutor_service import build_tutor_service


def main() -> None:
    settings = get_settings()
    tutor = build_tutor_service(settings)
    print("Tutor mode:", "live Gemini (" + settings.gemini_model + ")" if settings.gemini_configured
          else "fallback only (no GEMINI_API_KEY)")
    try:
        with get_sessionmaker()() as db:
            retrieve = partial(retrieve_for_text, db, include_unverified=True)
            reports = evaluate(load_cases(), retrieve, tutor)
    except DatabaseNotConfiguredError as exc:
        print(exc)
        raise SystemExit(1)

    for r in reports:
        flag = "PASS" if r.passed else "FAIL"
        extra = f"  [known limitation]" if r.case.known_limitation else ""
        print(f"{flag}  {r.case.id}  mode={r.result.mode}{extra}")
        for p in [*r.retrieval_problems, *r.tutor_problems]:
            print("      -", p)

    out = Path(__file__).resolve().parents[1] / "eval_output" / "review_sheet.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(render_review_sheet(reports), encoding="utf-8")
    failed = [r for r in reports if not r.passed]
    print(f"\n{len(reports) - len(failed)} of {len(reports)} cases passed the automated checks.")
    print("Review sheet for human scoring:", out)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
