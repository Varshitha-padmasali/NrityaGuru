import pytest

from app.schemas.tutor import ConceptExplanation, TutorExplanation
from app.services.tutor_validation import (
    InvalidCitationError,
    MalformedOutputError,
    UngroundedOutputError,
    check_grounding,
    parse_json_object,
)
from tests.factories import make_reference, make_retrieval


def _retrieval():
    return make_retrieval(
        [("river", [make_reference(record_id="m1", source_id="s1", mapping_source_id=None)]), ("krishna", [])]
    )


def _explanation(concepts, top_ids=None):
    return TutorExplanation(summary="TEST SUMMARY", concepts=concepts, source_ids=top_ids or [])


def _river(ids=("m1",), supported=True, name="river"):
    return ConceptExplanation(concept=name, supported=supported, explanation="TEST", source_ids=list(ids))


def _krishna(supported=False, ids=()):
    return ConceptExplanation(concept="krishna", supported=supported, explanation="TEST", source_ids=list(ids))


# ---- parse_json_object ----
def test_parse_plain_json():
    assert parse_json_object('{"a": 1}') == {"a": 1}


def test_parse_strips_markdown_fences():
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_object('```\n{"a": 1}\n```') == {"a": 1}


@pytest.mark.parametrize("bad", ["", "not json", "[1, 2]", '"text"', '{"a": '])
def test_parse_rejects_bad_output(bad):
    with pytest.raises(MalformedOutputError):
        parse_json_object(bad)


# ---- check_grounding ----
def test_valid_output_passes():
    check_grounding(_explanation([_river(), _krishna()], top_ids=["m1", "s1"]), _retrieval())


def test_fabricated_top_level_id_is_rejected():
    with pytest.raises(InvalidCitationError):
        check_grounding(_explanation([_river(), _krishna()], top_ids=["m1", "FAKE"]), _retrieval())


def test_fabricated_concept_level_id_is_rejected():
    with pytest.raises(InvalidCitationError):
        check_grounding(_explanation([_river(ids=("m1", "FAKE")), _krishna()]), _retrieval())


def test_unknown_concept_is_rejected():
    with pytest.raises(UngroundedOutputError):
        check_grounding(_explanation([_river(name="lotus")]), _retrieval())


def test_support_claimed_without_retrieved_reference_is_rejected():
    with pytest.raises(UngroundedOutputError):
        check_grounding(_explanation([_river(), _krishna(supported=True)]), _retrieval())


def test_citation_on_unsupported_concept_is_rejected():
    with pytest.raises(UngroundedOutputError):
        check_grounding(_explanation([_river(), _krishna(ids=("m1",))]), _retrieval())


def test_supported_concept_without_citation_is_rejected():
    with pytest.raises(UngroundedOutputError):
        check_grounding(_explanation([_river(ids=()), _krishna()]), _retrieval())


def test_citing_another_concepts_record_is_rejected():
    retrieval = make_retrieval(
        [
            ("river", [make_reference(record_id="mA", source_id="sA", mapping_source_id=None)]),
            ("cloud", [make_reference(record_id="mB", source_id="sB", mapping_source_id=None)]),
        ]
    )
    wrong = _explanation(
        [
            ConceptExplanation(concept="river", supported=True, explanation="T", source_ids=["mB"]),
            ConceptExplanation(concept="cloud", supported=True, explanation="T", source_ids=["mB"]),
        ]
    )
    with pytest.raises(InvalidCitationError):
        check_grounding(wrong, retrieval)


def test_concept_name_matching_is_case_insensitive():
    check_grounding(_explanation([_river(name=" RIVER "), _krishna()]), _retrieval())
