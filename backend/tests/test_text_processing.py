import pytest

from app.services.text_processing import (
    MAX_INPUT_CHARS,
    InputValidationError,
    normalize_text,
    normalize_token,
    tokenize,
    validate_input,
)


@pytest.mark.parametrize(
    "bad",
    ["", "   ", "\n\t", "1234 !!! ???", "a" * (MAX_INPUT_CHARS + 1), "hello\x00world"],
)
def test_invalid_inputs_rejected(bad):
    with pytest.raises(InputValidationError):
        validate_input(bad)


def test_non_string_rejected():
    with pytest.raises(InputValidationError):
        validate_input(None)


def test_valid_input_returned_unchanged():
    text = "  Krishna   dances \n"
    assert validate_input(text) == text


def test_normalize_text():
    assert normalize_text("  Krishna   DANCES \n") == "krishna dances"


def test_possessive_is_dropped():
    assert normalize_token("Krishna's") == "krishna"
    assert normalize_token("Krishna\u2019s") == "krishna"


def test_tokens_have_exact_offsets():
    text = "Krishna, dance!"
    toks = tokenize(text)
    assert [t.text for t in toks] == ["Krishna", "dance"]
    for t in toks:
        assert text[t.start : t.end] == t.text


def test_sentence_start_detection():
    toks = tokenize('River flows. "The" moon\nRises')
    flags = {t.text: t.sentence_start for t in toks}
    assert flags["River"] is True
    assert flags["flows"] is False
    assert flags["The"] is True
    assert flags["moon"] is False
    assert flags["Rises"] is True


def test_hyphen_and_apostrophe_stay_inside_word():
    assert [t.text for t in tokenize("well-known Krishna's")] == ["well-known", "Krishna's"]


def test_indic_script_is_tokenized_as_words():
    toks = tokenize("\u0915\u0943\u0937\u094d\u0923 \u0928\u0943\u0924\u094d\u092f")
    assert len(toks) == 2
