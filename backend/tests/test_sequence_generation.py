import pytest

from app.db.seed import load_seed
from app.services.knowledge_retrieval import retrieve_for_text
from app.services.sequence_generation import generate_mudra_sequence


@pytest.mark.parametrize(
    ("text", "expected", "unmapped"),
    [
        ("The river flows.", ["mudra_pataka"], []),
        ("A tree and a crown.", ["mudra_tripataka"], []),
        ("The lotus blooms by the river.", ["mudra_allapadma", "mudra_pataka"], ["blooms"]),
        (
            "Krishna is singing and dancing in the garden.",
            ["mudra_hamsasya", "mudra_allapadma"],
            ["Krishna", "garden"],
        ),
    ],
)
def test_sentence_sequence_uses_cited_mappings_and_reports_gaps(db_session, text, expected, unmapped):
    load_seed(db_session)
    retrieval = retrieve_for_text(db_session, text, include_unverified=True)
    sequence = generate_mudra_sequence(retrieval)
    assert [step.mudra_id for step in sequence.steps] == expected
    assert [step.position for step in sequence.steps] == list(range(1, len(expected) + 1))
    assert all(step.evidence_kind == "source_supported" for step in sequence.steps)
    assert all(step.inferred is False for step in sequence.steps)
    assert {item.word for item in sequence.unmapped_concepts} == set(unmapped)
    assert sequence.ai_enhanced is False
    for step in sequence.steps:
        assert step.source_id == "src_mirror_of_gesture_1917"
        assert step.source_url.startswith("https://www.wisdomlib.org/")


def test_sequence_preserves_sentence_order_and_deduplicates_mudras(db_session):
    load_seed(db_session)
    retrieval = retrieve_for_text(
        db_session,
        "A river flows. Then clouds cover the river.",
        include_unverified=True,
    )
    sequence = generate_mudra_sequence(retrieval)
    assert [step.mudra_id for step in sequence.steps] == ["mudra_pataka"]
    assert sequence.steps[0].sentence_index == 0
    assert set(sequence.steps[0].related_words) >= {"river", "flows", "clouds"}


def test_unmapped_unknown_concept_is_retained(db_session):
    load_seed(db_session)
    retrieval = retrieve_for_text(db_session, "A zephyr dances.", include_unverified=True)
    sequence = generate_mudra_sequence(retrieval)
    assert {item.word for item in sequence.unmapped_concepts} >= {"zephyr"}


def test_plural_and_alternate_name_forms_keep_source_order(db_session):
    load_seed(db_session)
    retrieval = retrieve_for_text(
        db_session,
        "The clouds flow past a pathaka and then a tree.",
        include_unverified=True,
    )
    sequence = generate_mudra_sequence(retrieval)
    assert [step.mudra_id for step in sequence.steps] == ["mudra_pataka", "mudra_tripataka"]
    assert sequence.steps[0].related_words[:2] == ["clouds", "flow"]
