import json

import pytest

from app.core.enums import VerificationStatus
from app.db.seed import load_seed
from app.schemas.multilingual_sequence import SequenceMode, SelectionType
from app.services.gemini_client import GeminiUnavailableError
from app.services.multilingual_sequence import _split_sentences, generate_multilingual_sequence


class QueueGenerator:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, *, system_instruction, prompt):
        self.calls.append((system_instruction, prompt))
        return json.dumps(self.responses.pop(0), ensure_ascii=False)


class FailOnSecondCall:
    def __init__(self, first_response):
        self.first_response = first_response
        self.calls = 0

    def generate(self, *, system_instruction, prompt):
        self.calls += 1
        if self.calls == 1:
            return json.dumps(self.first_response, ensure_ascii=False)
        raise GeminiUnavailableError("mock unavailable")


def _analysis(text, code="en", name="English"):
    phrases = {
        "Krishna is dancing in the garden.": [
            ("Krishna", "entity", ["Krishna"]),
            ("dancing", "action", ["dance"]),
            ("garden", "location", ["garden"]),
        ],
        "The lotus blooms beside the river.": [
            ("lotus", "object", ["lotus"]),
            ("blooms", "action", ["bloom"]),
            ("river", "nature", ["river"]),
        ],
        "ಕೃಷ್ಣನು ತೋಟದಲ್ಲಿ ನೃತ್ಯ ಮಾಡುತ್ತಾನೆ.": [
            ("ಕೃಷ್ಣನು", "entity", ["Krishna"]),
            ("ತೋಟದಲ್ಲಿ", "location", ["garden"]),
            ("ನೃತ್ಯ ಮಾಡುತ್ತಾನೆ", "action", ["dance"]),
        ],
    }
    rows = phrases.get(text, [(text, "action", ["dance"])])
    return {
        "language_code": code,
        "language_name": name,
        "language_confidence": 0.92,
        "sentence_translations": [
            {"order": i, "translation": sentence if code == "en" else "Mock English translation."}
            for i, sentence in enumerate(_split_sentences(text), start=1)
        ],
        "events": [
            {"order": i, "phrase": phrase, "event_type": kind, "concepts": [phrase],
             "lookup_terms": terms, "negated": False, "context": ""}
            for i, (phrase, kind, terms) in enumerate(rows, start=1)
        ],
        "caveats": [],
    }


def _add_translations(analysis, text):
    analysis["sentence_translations"] = [
        {"order": i, "translation": sentence if all(ord(char) < 128 for char in sentence) else "Mock English translation."}
        for i, sentence in enumerate(_split_sentences(text), start=1)
    ]
    return analysis


def _decisions(rows):
    return {"selections": rows}


def test_english_sequence_keeps_original_phrases_and_labels_inference(db_session):
    load_seed(db_session)
    text = "Krishna is dancing in the garden."
    generator = QueueGenerator(_decisions([
            {"event_order": 1, "mudra_ids": ["mudra_shikhara"], "reason": "An AI suggestion for the named figure.", "confidence": 0.42, "uncertainty": []},
            {"event_order": 3, "mudra_ids": ["mudra_pataka"], "reason": "A catalogue-only garden suggestion.", "confidence": 0.31, "uncertainty": []},
        ]))
    result = generate_multilingual_sequence(db_session, text, mode=SequenceMode.AI_ASSISTED, generator=generator, include_unverified=True)
    assert result.detected_language.code == "en" and result.gemini_used is True
    assert [step.phrase for step in result.ordered_sequence] == ["Krishna", "dancing", "garden"]
    assert [step.mudra_id for step in result.ordered_sequence] == ["mudra_shikhara", "mudra_allapadma", "mudra_pataka"]
    assert [step.selection_type for step in result.ordered_sequence] == [SelectionType.AI_INFERRED, SelectionType.SOURCE_SUPPORTED, SelectionType.AI_INFERRED]
    assert "does not support this AI-inferred association with the lyric concept" in result.ordered_sequence[0].source_citations[0].claim_scope
    assert result.ordered_sequence[1].source_citations[0].source_id == "src_mirror_of_gesture_1917"
    assert all(step.original_text == text for step in result.ordered_sequence)
    assert len(generator.calls) == 1


def test_source_supported_english_candidates_can_be_used_without_gemini(db_session):
    load_seed(db_session)
    text = "The river flows."
    result = generate_multilingual_sequence(db_session, text, mode=SequenceMode.KNOWLEDGE_BASE, generator=None, include_unverified=True)
    assert result.gemini_used is False
    assert [step.mudra_id for step in result.ordered_sequence] == ["mudra_pataka"]
    assert result.ordered_sequence[0].selection_type == SelectionType.SOURCE_SUPPORTED
    assert result.ordered_sequence[0].verification_status == VerificationStatus.SOURCE_CITED
    assert result.ordered_sequence[0].phrase == "river"
    assert result.ordered_sequence[0].related_phrases == ["river", "flows"]
    assert result.ordered_sequence[0].event_orders == [1, 2]


def test_repeated_mudra_after_another_event_keeps_temporal_position(db_session):
    load_seed(db_session)
    result = generate_multilingual_sequence(
        db_session, "A river, then a tree, then clouds.", mode="knowledge_base", include_unverified=True
    )
    assert [step.mudra_id for step in result.ordered_sequence] == [
        "mudra_pataka", "mudra_tripataka", "mudra_pataka"
    ]


@pytest.mark.parametrize(
    ("text", "expected_ids", "expected_unmapped"),
    [
        ("The lotus blooms beside the river.", ["mudra_allapadma", "mudra_pataka"], {"blooms", "beside"}),
        ("The mother lovingly holds her child.", [], {"mother", "lovingly", "holds", "child"}),
            ("The peacock spreads its feathers.", ["mudra_mayura"], {"spreads", "feathers"}),
        ("The lotus blooms by the river. Krishna is singing and dancing in the garden.",
         ["mudra_allapadma", "mudra_pataka", "mudra_hamsasya", "mudra_allapadma"], {"Krishna", "garden"}),
        ("Pathaka and Tripathaka appear beside the clouds.", ["mudra_pataka", "mudra_tripataka", "mudra_pataka"], set()),
    ],
)
def test_requested_english_lyrics_examples_use_database_or_report_gaps(db_session, text, expected_ids, expected_unmapped):
    load_seed(db_session)
    result = generate_multilingual_sequence(db_session, text, mode="knowledge_base", include_unverified=True)
    assert [step.mudra_id for step in result.ordered_sequence] == expected_ids
    assert expected_unmapped <= {row.concept for row in result.unmapped_concepts}
    assert all(step.selection_type == SelectionType.SOURCE_SUPPORTED for step in result.ordered_sequence)


def test_invalid_ai_ids_are_discarded_and_do_not_invent_citations(db_session):
    load_seed(db_session)
    text = "A zephyr arrives."
    generator = QueueGenerator(_decisions([
        {"event_order": 1, "mudra_ids": ["not_a_database_id"], "reason": "made up", "confidence": 0.9, "uncertainty": []},
    ]))
    result = generate_multilingual_sequence(db_session, text, mode="ai_assisted", generator=generator, include_unverified=True)
    assert result.ordered_sequence == []
    assert result.unmapped_concepts[0].concept == "zephyr"
    assert any("52-mudra catalogue" in caveat for caveat in result.interpretation_caveats)


def test_negated_source_match_is_not_mislabelled_as_a_traditional_positive_usage(db_session):
    load_seed(db_session)
    text = "The river does not flow."
    generator = QueueGenerator(_decisions([
        {"event_order": 2, "mudra_ids": ["mudra_pataka"], "reason": "Possible depiction despite negation.", "confidence": 0.3, "uncertainty": []},
    ]))
    result = generate_multilingual_sequence(db_session, text, mode="ai_assisted", generator=generator, include_unverified=True)
    flow_step = next(step for step in result.ordered_sequence if step.phrase == "flow")
    assert flow_step.selection_type == SelectionType.AI_INFERRED
    assert "negated" in " ".join(flow_step.uncertainty_notes)
    assert all("does not support this AI-inferred association" in citation.claim_scope for citation in flow_step.source_citations)


def test_reusing_a_mudra_does_not_merge_ai_inference_into_a_source_supported_step(db_session):
    load_seed(db_session)
    text = "The river is near the garden."
    generator = QueueGenerator(_decisions([
        {"event_order": 3, "mudra_ids": ["mudra_pataka"], "reason": "AI suggestion for garden.", "confidence": 0.3, "uncertainty": []},
    ]))
    result = generate_multilingual_sequence(db_session, text, mode="ai_assisted", generator=generator, include_unverified=True)
    assert [step.selection_type for step in result.ordered_sequence] == [SelectionType.SOURCE_SUPPORTED, SelectionType.AI_INFERRED]
    assert [step.phrase for step in result.ordered_sequence] == ["river", "garden"]


def test_eight_mudra_catalogue_never_substitutes_an_unrelated_gesture(db_session):
    load_seed(db_session)
    restricted = generate_multilingual_sequence(
        db_session, "The moon shines.", mode="knowledge_base", include_unverified=True, catalogue_mode="eight_mudra"
    )
    unrestricted = generate_multilingual_sequence(
        db_session, "The moon shines.", mode="knowledge_base", include_unverified=True
    )
    assert restricted.catalogue_mode == "eight_mudra"
    assert restricted.ordered_sequence == []
    assert {item.concept for item in restricted.unmapped_concepts} >= {"moon"}
    assert [step.mudra_id for step in unrestricted.ordered_sequence] == ["mudra_ardhachandra"]


def test_full_catalogue_is_default_and_ai_inference_still_uses_real_catalogue_ids(db_session):
    load_seed(db_session)
    text = "A zephyr appears."
    generator = QueueGenerator(_decisions([
        {"event_order": 1, "mudra_ids": ["mudra_berunda"], "reason": "A catalogue-only suggestion.", "confidence": 0.2, "uncertainty": []},
    ]))
    result = generate_multilingual_sequence(db_session, text, mode="ai_assisted", generator=generator, include_unverified=True)
    assert result.catalogue_mode == "all"
    assert result.ordered_sequence[0].mudra_id == "mudra_berunda"
    assert result.ordered_sequence[0].selection_type == SelectionType.AI_INFERRED
    assert result.ordered_sequence[0].source_citations


def test_selection_prompt_normalizes_catalogue_names_and_string_confidence(db_session):
    load_seed(db_session)
    text = "A zephyr appears."
    generator = QueueGenerator({"selections": [{
        "event_order": 1,
        "mudra_ids": ["Mayura"],
        "reason": "A bird-related catalogue suggestion.",
        "confidence": "0.55",
        "uncertainty": [],
        "model_note": "Extra explanatory fields are ignored.",
    }]})
    result = generate_multilingual_sequence(
        db_session, text, mode="ai_assisted", generator=generator, include_unverified=True
    )
    assert len(generator.calls) == 1  # English skips translation prompt 1.
    payload = json.loads(generator.calls[0][1])
    assert len(payload["catalogue"]) == 52
    assert [step.mudra_id for step in result.ordered_sequence] == ["mudra_mayura"]
    assert result.ordered_sequence[0].selection_type == SelectionType.AI_INFERRED


def test_english_identity_translation_does_not_depend_on_gemini(db_session):
    load_seed(db_session)
    result = generate_multilingual_sequence(db_session, "The river flows.", mode="ai_assisted", generator=None, include_unverified=True)
    assert result.gemini_used is False
    assert result.ordered_sequence[0].mudra_id == "mudra_pataka"
    assert result.detected_language.code == "en"
    assert result.sentence_translations[0].english_translation == "The river flows."


def test_english_identity_translates_every_sentence_without_gemini(db_session):
    load_seed(db_session)
    text = "The river flows. A tree stands."
    result = generate_multilingual_sequence(
        db_session, text, mode="ai_assisted", generator=None, include_unverified=True
    )
    assert result.gemini_used is False
    assert len(result.sentence_translations) == 2
    assert all(item.translated and item.english_translation == item.original_sentence for item in result.sentence_translations)


def test_gemini_transport_failure_reports_translation_unavailable_for_telugu(db_session):
    load_seed(db_session)

    class BrokenGenerator:
        def generate(self, *, system_instruction, prompt):
            raise GeminiUnavailableError("mock unavailable")

    text = "కృష్ణుడు నదిలో నడుస్తున్నాడు."
    result = generate_multilingual_sequence(db_session, text, mode="ai_assisted", generator=BrokenGenerator(), include_unverified=True)
    assert result.gemini_used is False
    assert result.ordered_sequence == []
    assert "temporarily unavailable" in result.sentence_translations[0].note
    assert "not configured" not in result.sentence_translations[0].note


def test_gemini_selection_failure_retains_only_database_matches(db_session):
    load_seed(db_session)
    text = "A zephyr appears beside the river."
    analysis = {
        "language_code": "en", "language_name": "English", "language_confidence": 0.99,
        "events": [
            {"order": 1, "phrase": "zephyr", "event_type": "nature", "concepts": ["zephyr"],
             "lookup_terms": ["zephyr"], "negated": False, "context": ""},
            {"order": 2, "phrase": "river", "event_type": "nature", "concepts": ["river"],
             "lookup_terms": ["river"], "negated": False, "context": ""},
        ],
        "caveats": [],
    }
    _add_translations(analysis, text)
    class BrokenSelectionGenerator:
        def generate(self, *, system_instruction, prompt):
            raise GeminiUnavailableError("mock unavailable")

    generator = BrokenSelectionGenerator()
    result = generate_multilingual_sequence(db_session, text, mode="ai_assisted", generator=generator, include_unverified=True)
    assert result.gemini_used is True
    assert [step.mudra_id for step in result.ordered_sequence] == ["mudra_pataka"]
    assert all(step.selection_type == SelectionType.SOURCE_SUPPORTED for step in result.ordered_sequence)
    assert any("database matches are still shown" in caveat for caveat in result.interpretation_caveats)


@pytest.mark.parametrize(
    ("text", "code", "name"),
    [
        ("ಕೃಷ್ಣನು ತೋಟದಲ್ಲಿ ನೃತ್ಯ ಮಾಡುತ್ತಾನೆ.", "kn", "Kannada"),
        ("కృష్ణుడు తోటలో నృత్యం చేస్తున్నాడు.", "te", "Telugu"),
        ("கிருஷ்ணன் தோட்டத்தில் நடனமாடுகிறார்.", "ta", "Tamil"),
        ("कृष्णः उद्याने नृत्यति।", "sa", "Sanskrit"),
        ("कृष्ण बगीचे में नाचता है।", "hi", "Hindi"),
    ],
)
def test_multilingual_analysis_preserves_script_and_returns_validated_sequence(db_session, text, code, name):
    load_seed(db_session)
    if code == "kn":
        selections = [
            {"event_order": 1, "mudra_ids": ["mudra_shikhara"], "reason": "AI suggestion", "confidence": 0.4, "uncertainty": []},
            {"event_order": 2, "mudra_ids": ["mudra_pataka"], "reason": "AI suggestion", "confidence": 0.3, "uncertainty": []},
            {"event_order": 3, "mudra_ids": ["mudra_allapadma"], "reason": "source candidate", "confidence": 0.8, "uncertainty": []},
        ]
    else:
        selections = [{"event_order": 1, "mudra_ids": ["mudra_allapadma"], "reason": "source candidate", "confidence": 0.8, "uncertainty": []}]
    generator = QueueGenerator(_analysis(text, code, name), _decisions(selections))
    result = generate_multilingual_sequence(db_session, text, mode="ai_assisted", generator=generator, include_unverified=True)
    assert result.original_input == text
    assert result.detected_language.code == code
    assert result.gemini_used is True
    assert result.ordered_sequence[0].phrase in text
    assert any(step.selection_type == SelectionType.SOURCE_SUPPORTED for step in result.ordered_sequence)


def test_devanagari_language_heuristic_does_not_confuse_hindi_and_sanskrit(db_session):
    load_seed(db_session)
    result = generate_multilingual_sequence(db_session, "कृष्णः उद्याने नृत्यति।", mode="knowledge_base", include_unverified=True)
    assert result.detected_language.code == "und-Deva"
    assert "ambiguous" in result.detected_language.name
    assert result.gemini_used is False


def test_unsupported_multilingual_concept_is_reported_without_fabricating_association(db_session):
    load_seed(db_session)
    text = "அறியாத பொருள்"
    result = generate_multilingual_sequence(db_session, text, mode="knowledge_base", include_unverified=True)
    assert result.detected_language.code == "ta"
    assert result.ordered_sequence == []
    assert result.unmapped_concepts
