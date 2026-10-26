# Concept extraction (Part 3)

Pipeline: validate -> tokenize -> drop stopwords -> classify -> merge repeats -> (optional) resolve against the knowledge base.

- Code: `app/services/text_processing.py`, `concept_extraction.py`, `concept_resolution.py`
- Schemas: `app/schemas/concepts.py`
- Deterministic: same input always gives the same output. No AI model is used.

## Classification rules (first match wins)
1. verb lexicon -> action (base form: singing -> sing)
2. entity-name hints -> entity
3. Capitalised word mid-sentence -> entity (heuristic)
4. unknown word ending in -ing -> action (heuristic; common -ing nouns excluded)
5. otherwise -> other

Each concept records `reason`, so you can always see which rule fired.
The word lists are classification hints only. They contain no Bharatanatyam knowledge.

## Known limitations
- Lexicons are English and small. Indic-script text is tokenized but not classified beyond "other".
- A capitalised word in the middle of a sentence (e.g. "the Moon") is treated as an entity: a known false positive.
- Nouns that are also verbs (dance, play, love) are labelled actions when in the verb lexicon.
- Multi-word concepts ("lotus flower") are not detected as one unit yet.
- Extracted concepts are candidates. Whether a mapping exists is decided only by the knowledge base.
