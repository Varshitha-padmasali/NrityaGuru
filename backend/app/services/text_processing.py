"""Input validation, normalization and tokenization. Pure Python, no framework imports.

The ORIGINAL text is never modified. Tokens carry character offsets into the original
so the frontend can highlight mentions.
"""
import re
import unicodedata
from dataclasses import dataclass

MAX_INPUT_CHARS = 1000

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")  # tab/newline/CR allowed
_JOINERS = ("'", "\u2019", "-")  # kept inside a word: "Krishna's", "well-known"
_SKIP_BEFORE_WORD = " \t\u00a0\"'\u201c\u2018("


class InputValidationError(ValueError):
    """Raised for input that cannot be processed. The message is safe to show to users."""


@dataclass(frozen=True)
class Token:
    text: str  # exactly as written in the original
    start: int
    end: int
    sentence_start: bool


def _is_word_char(ch: str) -> bool:
    # Letters (L*) and combining marks (M*): works for English and Indic scripts.
    return unicodedata.category(ch)[0] in ("L", "M")


def validate_input(text: object) -> str:
    """Return the text unchanged if acceptable, otherwise raise InputValidationError."""
    if not isinstance(text, str):
        raise InputValidationError("Input must be text.")
    if not text.strip():
        raise InputValidationError("Input is empty.")
    if len(text) > MAX_INPUT_CHARS:
        raise InputValidationError(f"Input is too long (maximum {MAX_INPUT_CHARS} characters).")
    if _CONTROL_CHARS.search(text):
        raise InputValidationError("Input contains unsupported control characters.")
    if not any(_is_word_char(c) for c in text):
        raise InputValidationError("Input must contain at least one word.")
    return text


def normalize_text(text: str) -> str:
    """Unicode NFKC, case-folded, whitespace collapsed. For display/debugging only."""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def normalize_token(token: str) -> str:
    """Normalize one word and drop a trailing possessive ('s)."""
    norm = unicodedata.normalize("NFKC", token).casefold()
    for suffix in ("'s", "\u2019s"):
        if norm.endswith(suffix) and len(norm) > len(suffix):
            return norm[: -len(suffix)]
    return norm


def _is_sentence_start(text: str, start: int) -> bool:
    i = start - 1
    while i >= 0 and text[i] in _SKIP_BEFORE_WORD:
        i -= 1
    return i < 0 or text[i] in ".!?\n\r"


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    i, n = 0, len(text)
    while i < n:
        if not _is_word_char(text[i]):
            i += 1
            continue
        j = i + 1
        while j < n:
            if _is_word_char(text[j]):
                j += 1
            elif text[j] in _JOINERS and j + 1 < n and _is_word_char(text[j + 1]):
                j += 2
            else:
                break
        tokens.append(Token(text[i:j], i, j, _is_sentence_start(text, i)))
        i = j
    return tokens
