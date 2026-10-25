# RAG pipeline and tutor API (Part 6)

    text -> validate -> extract concepts -> retrieve (PostgreSQL) -> build context -> Gemini
         -> parse -> shape check -> grounding check -> response  (retrieved knowledge always included)

Code: `services/rag_pipeline.py` (orchestration), `api/tutor.py` (endpoint), `api/deps.py` (shared dependencies),
`core/rate_limit.py` (limiter). Retrieval and tutor are the Part 4 and Part 5 services, unchanged.

## POST /api/tutor/explain
Request:
```json
{ "text": "Clouds and a tree", "include_unverified": false, "include_keyword_matches": false }
```
Response: `original_text`, `tutor`, `retrieval`, `disclaimer`.
- `tutor.mode`: `"ai"` or `"knowledge_only"`; `tutor.fallback_reason` explains a fallback (see docs/gemini_tutor.md)
- `tutor.explanation`: `summary`, `concepts[]`, `suggestions`, `alternatives`, `source_ids`, `limitations`
- `retrieval`: the full Part 4 response (records, sources, verification status, limitations). Always present.

| Code | Meaning |
|---|---|
| 200 | OK. Also when Gemini failed: you get `knowledge_only` with the retrieved records |
| 403 | `include_unverified` requested but disabled on this server |
| 422 | invalid input (empty, too long, no letters) |
| 429 | rate limit (header `Retry-After`) |
| 503 | database not configured/unavailable (generic message) |

A Gemini failure is deliberately NOT an HTTP error: the learner still receives the retrieved knowledge.

## Rules the pipeline enforces
- Nothing retrieved -> Gemini is not called; the answer says no supported reference exists.
- Gemini output that cites an id it was not given, or claims support nobody retrieved, is discarded.
- Retrieved records are returned with every answer, so the frontend can show them next to the explanation.
- Learner text is never logged. The API key never appears in responses.

## Rate limiting
In-memory sliding window per client IP (`TUTOR_RATE_LIMIT_PER_MINUTE`, default 20). Limits: per server
process, resets on restart, and behind a proxy `request.client.host` is the proxy address. Use Redis or the
gateway's limiter for real production.

## Evaluation method
Cases: `data/eval/rag_queries.json` (11 labelled queries incl. the spec example, an unmapped word, a prompt
injection attempt, and one known limitation).

1. Automated (`services/rag_evaluation.py`): expected supported/unsupported concepts, expected records, no
   unexpected support (possible invented mapping), no forbidden terms, valid citations, Gemini not used when
   nothing was retrieved, unverified status mentioned (keyword heuristic).
2. Regression test: `tests/test_rag_eval_set.py` runs all cases on the seed data with a fake tutor.
3. Live run: `python -m scripts.evaluate_rag` (real Gemini if a key is set). Writes
   `eval_output/review_sheet.md` with BLANK columns for human relevance (1-5) and faithfulness (Y/N).

What this does and does not show: the automated checks are regression checks. The expectations come from the
current seed data, so they prove the pipeline behaves as designed, not that the Bharatanatyam content is correct.
Faithfulness of the wording needs a human. No accuracy percentage is reported because 11 cases built from 3
unverified records cannot support one.

## Known limitation found while building the evaluation
Multi-word concepts are not detected: "temple tower" is a listed usage of Ardhapataka, but the input
"temple tower" is split into "temple" and "tower", so nothing is found (case q11). Candidate fix for later:
look up adjacent word pairs/triples against the mapping and usage lists.

## Are embeddings / semantic retrieval justified now? No.
- With 3 seed records, retrieval misses come from missing data and the multi-word gap, not from vocabulary mismatch.
- Embeddings always return a nearest neighbour, which pushes toward the failure your rules forbid: a confident-looking
  mudra for a word that has no supported mapping (e.g. "garden" is close to "forest").
- Cheaper first fixes: add synonyms as alternate names / mapping rows (curated and sourced), and phrase matching.

When to revisit: the knowledge base has hundreds of verified records AND a labelled query set shows
real misses on synonyms/paraphrases (e.g. "stream" for "river").
How: same PostgreSQL with the pgvector extension (no separate vector database), Google's `gemini-embedding-2`
(GA April 2026) or another embedding model, cosine similarity, top-k. Semantic hits would be a separate, clearly
labelled lower-confidence tier ("possibly related, not a mapping"), never a verified mapping, and measured
(recall@k on the labelled set) before being enabled.
