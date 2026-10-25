import pytest

from app.schemas.concepts import ConceptType
from app.services.concept_extraction import (
    MAX_CONCEPTS,
    VERB_FORM_TO_LEMMA,
    VERB_FORMS,
    extract_concepts,
)
from app.services.text_processing import InputValidationError


def _by_norm(result):
    return {c.normalized: c for c in result.concepts}


def test_spec_example_sentence():
    r = extract_concepts("Krishna is singing and dancing in the garden.")
    assert [c.normalized for c in r.concepts] == ["krishna", "sing", "dance", "garden"]
    assert [c.concept_type for c in r.concepts] == [
        ConceptType.ENTITY,
        ConceptType.ACTION,
        ConceptType.ACTION,
        ConceptType.OTHER,
    ]
    assert r.concepts[1].lookup_keys == ["sing", "singing"]
    assert r.warnings == []


def test_original_text_preserved_exactly():
    text = "  Krishna   dances \n\n"
    r = extract_concepts(text)
    assert r.original_text == text
    assert r.normalized_text == "krishna dances"


def test_mention_spans_point_into_original():
    text = "Krishna is dancing in the garden."
    garden = _by_norm(extract_concepts(text))["garden"]
    s = garden.mentions[0]
    assert text[s.start : s.end] == "garden"


def test_repeated_word_merged_with_all_mentions():
    r = extract_concepts("River river RIVER")
    assert len(r.concepts) == 1
    assert len(r.concepts[0].mentions) == 3


def test_irregular_verb_form():
    r = extract_concepts("She sang beautifully.")
    assert r.concepts[0].normalized == "sing"
    assert r.concepts[0].concept_type == ConceptType.ACTION


def test_possessive_entity():
    c = _by_norm(extract_concepts("Krishna's flute"))
    assert c["krishna"].concept_type == ConceptType.ENTITY
    assert "flute" in c


def test_unknown_capitalised_name_mid_sentence_is_entity():
    c = _by_norm(extract_concepts("Today Arjun walks"))
    assert c["arjun"].concept_type == ConceptType.ENTITY
    assert c["arjun"].reason == "capitalised_mid_sentence"
    assert c["today"].concept_type == ConceptType.OTHER  # sentence start: not assumed a name
    assert c["walk"].concept_type == ConceptType.ACTION


def test_all_caps_text_does_not_create_entities():
    r = extract_concepts("THE RIVER FLOWS")
    assert all(c.concept_type != ConceptType.ENTITY for c in r.concepts)


def test_multiline_lyrics_line_start_is_not_a_name():
    r = extract_concepts("Krishna dances.\nRiver flows\nthe moon rises")
    c = _by_norm(r)
    assert c["krishna"].concept_type == ConceptType.ENTITY
    assert c["river"].concept_type == ConceptType.OTHER


def test_plural_gets_singular_lookup_key():
    c = _by_norm(extract_concepts("clouds and stories"))
    assert c["cloud"].lookup_keys == ["cloud", "clouds"]
    assert c["story"].lookup_keys == ["story", "stories"]


def test_ing_noun_exception():
    c = _by_norm(extract_concepts("Good morning"))
    assert c["morning"].concept_type == ConceptType.OTHER


def test_unknown_ing_verb_gets_stem_keys():
    c = _by_norm(extract_concepts("chasing"))
    chasing = c["chasing"]
    assert chasing.concept_type == ConceptType.ACTION
    assert chasing.reason == "ing_suffix_rule"
    assert "chase" in chasing.lookup_keys and "chasing" in chasing.lookup_keys


def test_doubled_consonant_stem():
    c = _by_norm(extract_concepts("stopping"))
    assert "stop" in c["stopping"].lookup_keys


def test_stopword_only_input_gives_empty_result_with_warning():
    r = extract_concepts("is the of")
    assert r.concepts == []
    assert any("No candidate concepts" in w for w in r.warnings)


def test_concept_count_is_capped():
    words = " ".join(f"{chr(97 + i // 26)}{chr(97 + i % 26)}x" for i in range(40))
    r = extract_concepts(words)
    assert len(r.concepts) == MAX_CONCEPTS
    assert any(str(MAX_CONCEPTS) in w for w in r.warnings)


@pytest.mark.parametrize("bad", ["", "   ", "123 456", "hi\x00"])
def test_invalid_input_raises(bad):
    with pytest.raises(InputValidationError):
        extract_concepts(bad)


def test_verb_table_has_no_form_collisions():
    expected = sum(1 + len(forms) for forms in VERB_FORMS.values())
    assert len(VERB_FORM_TO_LEMMA) == expected


def test_result_carries_disclaimer_and_method():
    r = extract_concepts("river")
    assert "candidates" in r.disclaimer
    assert r.method == "deterministic_lexicon_v1"
