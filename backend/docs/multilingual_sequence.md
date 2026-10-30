# Multilingual lyric-to-mudra sequence service

## Current integration state

`POST /api/knowledge/sequence` is an additive endpoint; `/api/knowledge/retrieve` and its response shape are unchanged. It returns ordered semantic events, one English-translation result per sentence, sequence steps, citations, verification labels, and unmapped concepts.

`LearnWorkspace` calls `/api/knowledge/sequence` and renders its ordered gesture steps, sentence translations, evidence labels, images, caveats, and unresolved concepts. It also retains the existing retrieval and tutor calls so the concept-grouped results continue to appear. The frontend files were already changed in the working tree before this backend pass and were left untouched here.

## Modes

- `knowledge_base`: deterministic, source-backed retrieval only. It uses all 52 catalogue entries by default; unresolved concepts stay in `unmapped_concepts`.
- `ai_assisted` is the endpoint default and uses at most two Gemini prompts. Prompt 1 is sent only for non-English input: identify the language, translate every sentence into English, and extract ordered English content words/actions with their original text spans. English input uses local extraction and an identity translation. The English terms are searched in the knowledge base, and supported source-backed matches are selected deterministically. Prompt 2 is one batched request for only the unmatched terms; it chooses at most one best fit from the full 52-mudra catalogue. Catalogue-only selections are marked `ai_inferred`, and mudra description sources are never presented as evidence for that inferred association. If there are no unmatched terms, prompt 2 is skipped.
- If Gemini is absent, errors, or returns invalid/incomplete output for a non-English sentence, the service falls back to deterministic extraction/retrieval and marks that translation unavailable. English sentences still receive an identity translation without Gemini. Offline script detection identifies Kannada, Telugu, Tamil, and Devanagari scripts; it does not translate them or distinguish Hindi from Sanskrit. Language coverage and translation quality depend on the configured Gemini model; poetic interpretation can remain uncertain.
- Optional `catalogue_mode="eight_mudra"` restricts retrieval and AI candidates to the existing IDs for Pataka, Tripataka, Mushti, Kapitha/Kapittha, Allapadma, Hamsasya, Mayura, and Shikhara. It leaves out-of-set concepts unmapped rather than substituting another mudra.

The model and API key come from the existing settings and Gemini client (`GEMINI_MODEL`, `GEMINI_API_KEY`). No model name or key is introduced by this feature. AI self-reported confidence is explicitly described as uncalibrated; the 0.8/1.0 values for database matches are evidence-tier scores, not probabilities.

## Grounding and limits

- Gemini event phrases must be exact, ordered substrings of the original input. The original text, phrase, detected language, relations, tense, and negation are retained.
- Only adjacent repeated mudras with the same selection/evidence class are collapsed; a repeated gesture after another event or with different evidence provenance stays in its chronological position.
- Selection IDs must exist in the current database and in the available catalogue. Source citations and image URLs are attached only from database records.
- A source-cited match remains `source_cited`; it is not teacher-verified. An AI-inferred association does not turn a mudra's descriptive source into evidence for that association.
- Learn retrieval and the knowledge catalogue explicitly include source-cited rows by default so their evidence can be shown. Rows without a source remain opt-in. Camera evaluation reference lookup keeps the stricter verified-only repository default.
- Negated events cannot inherit a positive source-backed mapping; a model suggestion in that case remains AI-inferred with an explicit uncertainty note.
- The output is a semantic learning aid, not canonical choreography. The database currently has no teacher-verified sequence set.
- The Kannada, Telugu, Tamil, Sanskrit, and Hindi plumbing tests use mocked Gemini outputs. They verify schema validation, one translation entry per sentence, ordering, original phrase retention, candidate grounding, and source/inference labels; they do not verify real translations or a live Gemini call. No live API key/model request was made during tests.

## Tests and local commands

The service/API tests cover the supplied English examples, the peacock/dancing/rain sequence shape, unknown terms, multi-sentence translations, alternate spellings, five Indic scripts/languages with mocked model output, malformed/incomplete output, invalid IDs, negation, offline fallback, access restrictions, and eight-mudra restriction.

```bash
cd backend
../.venv/bin/python -m pytest -q
```

Rebuild and restart only the backend (the service will safely re-run the existing idempotent seed):

```bash
docker compose build backend
docker compose up -d backend
```

The Learn UI is wired to the sequence response. The local backend is running against a fresh,
ignored SQLite database seeded with 52 mudras and 398 mappings. The server-side Gemini setting is
configured and is never exposed to the browser. No live model call was made during this pass; mock
Gemini, validation, timeout retry, and fallback paths are covered by the test suite. The last
observed live request (from the user's screenshot session) received HTTP 504 twice; the client now
retries one transient timeout before using the honest deterministic fallback.
