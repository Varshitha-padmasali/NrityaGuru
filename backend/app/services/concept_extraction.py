"""Deterministic candidate-concept extraction (no AI model, no database).

Pipeline: validate -> tokenize -> drop stopwords -> classify -> merge repeats.

Classification order (first match wins):
  1. verb lexicon        -> ACTION  (reduced to base form: singing -> sing)
  2. entity-name lexicon -> ENTITY
  3. Capitalised word in the middle of a sentence -> ENTITY (heuristic)
  4. unknown word ending in -ing                  -> ACTION (heuristic)
  5. everything else                              -> OTHER

IMPORTANT: these lists are classification HINTS to separate names from actions from
other words. They contain no Bharatanatyam knowledge. What a concept maps to is decided
only by the curated knowledge base.
"""
from app.schemas.concepts import ConceptType, ExtractedConcept, ExtractionResult, Span
from app.services.text_processing import (
    Token,
    normalize_text,
    normalize_token,
    tokenize,
    validate_input,
)

METHOD = "deterministic_lexicon_v1"
MAX_CONCEPTS = 30

STOPWORDS = frozenset(
    """a an the and or but if then so of in on at to from by with for about into over under
    up down out off as is are was were be been being am do does did done have has had having
    it its this that these those he she they we you i me him her them us my your his their our
    who whom what which when where why how not no yes very just also too than there here can
    could will would shall should may might must let like all some any each every both more
    most other such only own same""".split()
)

# lemma -> inflected forms. Small on purpose; extend as needed.
VERB_FORMS: dict[str, tuple[str, ...]] = {
    "sing": ("sings", "singing", "sang", "sung"),
    "dance": ("dances", "danced", "dancing"),
    "walk": ("walks", "walked", "walking"),
    "run": ("runs", "running", "ran"),
    "jump": ("jumps", "jumped", "jumping"),
    "play": ("plays", "played", "playing"),
    "eat": ("eats", "eating", "ate", "eaten"),
    "drink": ("drinks", "drinking", "drank", "drunk"),
    "sleep": ("sleeps", "sleeping", "slept"),
    "sit": ("sits", "sitting", "sat"),
    "stand": ("stands", "standing", "stood"),
    "look": ("looks", "looked", "looking"),
    "cry": ("cries", "cried", "crying"),
    "laugh": ("laughs", "laughed", "laughing"),
    "fly": ("flies", "flying", "flew", "flown"),
    "swim": ("swims", "swimming", "swam"),
    "pray": ("prays", "prayed", "praying"),
    "bow": ("bows", "bowed", "bowing"),
    "hold": ("holds", "holding", "held"),
    "carry": ("carries", "carried", "carrying"),
    "give": ("gives", "giving", "gave", "given"),
    "take": ("takes", "taking", "took", "taken"),
    "come": ("comes", "coming", "came"),
    "go": ("goes", "going", "went", "gone"),
    "speak": ("speaks", "speaking", "spoke", "spoken"),
    "call": ("calls", "called", "calling"),
    "love": ("loves", "loved", "loving"),
    "fight": ("fights", "fighting", "fought"),
    "bless": ("blesses", "blessed", "blessing"),
    "praise": ("praises", "praised", "praising"),
    "worship": ("worships", "worshipped", "worshipping"),
    "dream": ("dreams", "dreamed", "dreaming"),
    "think": ("thinks", "thinking", "thought"),
}

VERB_FORM_TO_LEMMA: dict[str, str] = {}
for _lemma, _forms in VERB_FORMS.items():
    VERB_FORM_TO_LEMMA[_lemma] = _lemma
    for _form in _forms:
        VERB_FORM_TO_LEMMA[_form] = _lemma

# Names used only to label a word as ENTITY. Not a claim about any tradition.
ENTITY_HINTS = frozenset(
    """krishna radha rama sita shiva parvati ganesha hanuman lakshmi saraswati vishnu
    durga brahma indra arjuna""".split()
)

# Words ending in -ing that are normally nouns, so the -ing heuristic must not fire.
_ING_EXCEPTIONS = frozenset(
    """morning evening spring string thing something anything nothing everything wedding
    building ceiling feeling king ring wing""".split()
)


def _unique(items: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for item in items:
        if item and item not in seen:
            seen[item] = None
    return list(seen)


def _singular(word: str) -> str:
    if len(word) <= 3:
        return word
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("sses", "shes", "ches", "xes", "zes")):
        return word[:-2]
    if word.endswith(("ss", "us", "is")):
        return word
    if word.endswith("s"):
        return word[:-1]
    return word


def _ing_stems(word: str) -> list[str]:
    stem = word[:-3]
    stems = [stem, stem + "e"]
    if len(stem) >= 2 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
        stems.insert(0, stem[:-1])  # running -> run
    return stems


def _is_title_case(text: str) -> bool:
    return text[0].isupper() and not text.isupper()


def _classify(token: Token, norm: str) -> tuple[ConceptType, str, list[str], str]:
    """Return (type, normalized, lookup_keys, reason)."""
    lemma = VERB_FORM_TO_LEMMA.get(norm)
    if lemma is not None:
        return ConceptType.ACTION, lemma, _unique([lemma, norm]), "verb_lexicon"
    if norm in ENTITY_HINTS:
        return ConceptType.ENTITY, norm, [norm], "entity_lexicon"
    if _is_title_case(token.text) and not token.sentence_start:
        return ConceptType.ENTITY, norm, [norm], "capitalised_mid_sentence"
    if norm.endswith("ing") and len(norm) > 4 and norm not in _ING_EXCEPTIONS:
        return ConceptType.ACTION, norm, _unique([norm, *_ing_stems(norm)]), "ing_suffix_rule"
    singular = _singular(norm)
    return ConceptType.OTHER, singular, _unique([singular, norm]), "default_candidate"


def extract_concepts(text: str) -> ExtractionResult:
    """Extract candidate concepts. Raises InputValidationError for unusable input."""
    validate_input(text)

    merged: dict[str, ExtractedConcept] = {}
    for token in tokenize(text):
        norm = normalize_token(token.text)
        if len(norm) < 2 or norm in STOPWORDS:
            continue
        ctype, normalized, keys, reason = _classify(token, norm)
        span = Span(start=token.start, end=token.end)
        if normalized in merged:
            merged[normalized].mentions.append(span)
        else:
            merged[normalized] = ExtractedConcept(
                text=token.text,
                normalized=normalized,
                concept_type=ctype,
                lookup_keys=keys,
                mentions=[span],
                reason=reason,
            )

    concepts = list(merged.values())
    warnings: list[str] = []
    if len(concepts) > MAX_CONCEPTS:
        concepts = concepts[:MAX_CONCEPTS]
        warnings.append(f"Only the first {MAX_CONCEPTS} concepts were kept.")
    if not concepts:
        warnings.append("No candidate concepts were found in the input.")

    return ExtractionResult(
        original_text=text,
        normalized_text=normalize_text(text),
        concepts=concepts,
        warnings=warnings,
        method=METHOD,
    )
