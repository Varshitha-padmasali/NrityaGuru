"""Regression: runs the labelled evaluation set through the real retrieval on the seed data,
with a fake tutor (no network). Needs SQLAlchemy."""
from functools import partial

from app.db.seed import load_seed
from app.services.knowledge_retrieval import retrieve_for_text
from app.services.rag_evaluation import evaluate, load_cases
from app.services.tutor_service import TutorService


def test_every_labelled_case_passes_its_automated_checks(db_session):
    load_seed(db_session)
    retrieve = partial(retrieve_for_text, db_session, include_unverified=True)
    reports = evaluate(load_cases(), retrieve, TutorService(None))  # fallback path, deterministic
    failures = {r.case.id: r.retrieval_problems + r.tutor_problems for r in reports if not r.passed}
    assert failures == {}


def test_spec_example_returns_only_cited_mappings_without_gemini(db_session):
    load_seed(db_session)
    retrieve = partial(retrieve_for_text, db_session, include_unverified=True)
    report = next(
        r for r in evaluate(load_cases(), retrieve, TutorService(None))
        if r.case.id == "q02_spec_example_nothing_supported"
    )
    assert report.retrieval.supported_count == 2
    assert report.result.fallback_reason.value == "not_configured"
