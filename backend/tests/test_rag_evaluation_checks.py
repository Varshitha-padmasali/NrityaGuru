from app.core.enums import TutorFallbackReason as R
from app.core.enums import VerificationStatus
from app.schemas.tutor import ConceptExplanation, TutorExplanation, TutorResult
from app.services.rag_evaluation import (
    EvalCase,
    check_retrieval,
    check_tutor_result,
    load_cases,
    render_review_sheet,
    CaseReport,
)
from tests.factories import make_reference, make_retrieval

V = VerificationStatus


def _retrieval():
    ref = make_reference(record_id="m1", source_id="s1", mapping_source_id=None, status=V.SOURCE_CITED)
    return make_retrieval([("river", [ref]), ("krishna", [])])


def _result(summary="TEST not yet verified", concepts=None, source_ids=None, mode="ai", reason=None):
    ex = TutorExplanation(summary=summary, concepts=concepts or [], source_ids=source_ids or [])
    return TutorResult(mode=mode, explanation=ex, fallback_reason=reason)


def test_eval_set_file_is_well_formed():
    cases = load_cases()
    ids = [c.id for c in cases]
    assert len(cases) >= 10 and len(ids) == len(set(ids))
    assert any(c.known_limitation for c in cases)
    assert any(not c.expect_supported for c in cases)  # includes cases with nothing supported


def test_retrieval_check_passes_when_expectations_match():
    case = EvalCase(id="t", text="x", expect_supported=["river"], expect_unsupported=["krishna"],
                    expect_record_ids=["m1"])
    assert check_retrieval(case, _retrieval()) == []


def test_retrieval_check_flags_missing_support_and_missing_record():
    case = EvalCase(id="t", text="x", expect_supported=["river", "krishna"], expect_record_ids=["zzz"])
    problems = check_retrieval(case, _retrieval())
    assert any("'krishna'" in p and "supported" in p for p in problems)
    assert any("zzz" in p for p in problems)


def test_retrieval_check_flags_unexpected_support_as_possible_invention():
    case = EvalCase(id="t", text="x", expect_supported=[], expect_unsupported=["krishna"])
    assert any("unexpected support for 'river'" in p for p in check_retrieval(case, _retrieval()))


def test_retrieval_check_flags_unextracted_concept():
    case = EvalCase(id="t", text="x", expect_supported=["lotus"])
    assert any("was not extracted" in p for p in check_retrieval(case, _retrieval()))


def test_tutor_check_passes_clean_answer():
    res = _result(concepts=[ConceptExplanation(concept="river", supported=True, explanation="T", source_ids=["m1"])],
                  source_ids=["m1"])
    assert check_tutor_result(EvalCase(id="t", text="x"), _retrieval(), res) == []


def test_tutor_check_flags_forbidden_term():
    case = EvalCase(id="t", text="x", forbidden_terms=["fakemudra"])
    res = _result(summary="Krishna uses Fakemudra, not yet verified")
    assert any("forbidden term" in p for p in check_tutor_result(case, _retrieval(), res))


def test_tutor_check_flags_support_claimed_for_unsupported_concept():
    res = _result(concepts=[ConceptExplanation(concept="krishna", supported=True, explanation="T")])
    assert any("claims support" in p for p in check_tutor_result(EvalCase(id="t", text="x"), _retrieval(), res))


def test_tutor_check_flags_unknown_citation():
    res = _result(source_ids=["INVENTED"])
    assert any("unknown id" in p for p in check_tutor_result(EvalCase(id="t", text="x"), _retrieval(), res))


def test_tutor_check_requires_mentioning_unverified_status():
    res = _result(summary="Rivers use a flag-like gesture.")
    assert any("never says so" in p for p in check_tutor_result(EvalCase(id="t", text="x"), _retrieval(), res))


def test_tutor_check_requires_no_gemini_when_nothing_retrieved():
    empty = make_retrieval([("krishna", [])])
    ai = _result(summary="Something confident", mode="ai")
    assert any("should not have been used" in p for p in check_tutor_result(EvalCase(id="t", text="x"), empty, ai))
    ok = _result(summary="None found", mode="knowledge_only", reason=R.NO_REFERENCES)
    assert check_tutor_result(EvalCase(id="t", text="x"), empty, ok) == []


def test_review_sheet_has_blank_human_columns_and_no_invented_scores():
    case = EvalCase(id="t1", text="river")
    res = _result(summary="TEST not yet verified")
    sheet = render_review_sheet([CaseReport(case, _retrieval(), res, [], [])])
    assert "HUMAN relevance (1-5): ____" in sheet
    assert "HUMAN faithful" in sheet
    assert "automated checks: **PASS**" in sheet
