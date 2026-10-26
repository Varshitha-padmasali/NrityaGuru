# Architecture (Member 2 module)

## Layers
```
api/            HTTP only: validate request, call a service, shape the response     (FastAPI routers, deps)
services/       all logic: extraction, retrieval, prompts, validation, workflows    (no HTTP, little I/O)
integrations/   things outside this module: evaluation store (mock + PostgreSQL)
repositories/   all SQL: knowledge, sessions, evaluation results, feedback          (SQLAlchemy)
schemas/        Pydantic models: the shape of every request, response and contract
db/             engine/session, models, seed loader, table creation
core/           settings, enums, errors, logging, rate limiter
```
Rule: **services never write SQL and never import FastAPI; repositories never call Gemini; only `gemini_client.py` talks to Gemini.**
Services receive their dependencies (retrieval function, Gemini generator, store) as arguments, so each can be tested alone with fakes.

## Flow 1: learner text -> tutor answer (`POST /api/tutor/explain`)
1. `text_processing` validates the text (1-1000 chars, no control characters, contains a word); the original is kept untouched.
2. `concept_extraction` tokenizes and classifies candidate concepts (entity / action / other) with documented rules; it contains no cultural knowledge.
3. `knowledge_retrieval` looks each concept up: explicit mapping > exact name > alternate name > listed usage > (optional) keyword. It returns every match
   with source, verification status and limitations. Only `verified` records unless the server allows more.
4. If nothing was retrieved, Gemini is **not** called; the answer says no supported reference exists.
5. `tutor_prompt` builds a bounded prompt from the retrieved records only; `gemini_client` sends it; `tutor_validation` parses the JSON, checks its shape
   (Pydantic) and its claims (every cited id was retrieved; no support claimed without a retrieved reference).
6. Any failure returns the retrieved knowledge with fixed templates (`knowledge_only`). The retrieved records are always in the response.

## Flow 2: session id -> feedback (`POST /api/feedback/generate`)
1. `feedback_workflow` asks `evaluation_evidence` for validated evidence: session-id format -> trusted store -> same-session check -> schema/version check
   -> reference lookup in PostgreSQL -> mock-data guard -> `evaluation_assessment` (what the evidence can and cannot support).
2. Unless `regenerate`, stored feedback is reused when its evidence fingerprint still matches (and it was an AI answer or a deterministic "insufficient evidence").
3. `feedback_evidence` turns the evidence into numbered plain-language facts. If the evidence level is `insufficient`, Gemini is not called.
4. `feedback_prompt` -> Gemini -> `feedback_validation`: citations must exist; no body part, video word or number that the evidence does not contain.
5. Limitations always come from the deterministic assessment, never from Gemini. Failure returns evidence-only feedback from templates.
6. The result is stored (not for MOCK data) and returned with `saved` / `reused` flags.

## Role of each service
| Module | Role | Depends on |
|---|---|---|
| core/config.py | typed settings from `.env`; secrets as `SecretStr` | pydantic-settings |
| core/errors.py | maps domain errors to safe HTTP responses | services/repositories errors |
| core/rate_limit.py | per-IP sliding window | - |
| services/text_processing.py | validation, normalization, tokenizer with offsets | - |
| services/concept_extraction.py | candidate concepts + lookup keys | text_processing |
| services/knowledge_matching.py | pure matching rules, weakest-status, limitation texts | text_processing |
| services/knowledge_retrieval.py | concepts -> references (DB via repositories) | repositories, matching |
| services/tutor_prompt/validation/fallback/service.py | grounded explanation with guards and fallback | gemini_client |
| services/rag_pipeline.py | retrieval + tutor behind one call | injected callables |
| services/gemini_client.py | the only Gemini caller; safe error classification | google-genai (lazy) |
| services/evaluation_evidence.py, evaluation_assessment.py, reference_lookup.py | validate and assess evaluation results | integrations, repositories |
| integrations/evaluation_stub.py | store interface + 5 MOCK scenarios | - |
| integrations/database_evaluation_store.py | reads results stored by the evaluation module | repositories |
| services/feedback_evidence/prompt/validation/fallback/service.py | grounded feedback with guards and fallback | gemini_client |
| services/feedback_workflow.py | evidence -> reuse or generate -> store | injected store |
| repositories/* | all SQL; failures become `PersistenceError` | SQLAlchemy |

## Principles
1. **Grounding:** Gemini explains retrieved or evaluated facts; it is not a source of Bharatanatyam knowledge.
2. **Evidence-labelled by default:** `source_cited` and `verified` records are served with status and provenance; records with no source require explicit configuration.
3. **Graceful degradation:** a Gemini or save failure never loses the learner's information.
4. **Trust boundary:** the browser sends text and a session id, nothing else; evaluation results come only from the trusted store.
5. **Honest limits:** every answer carries limitations and a disclaimer; mock data is labelled everywhere it appears and never stored.

## Decisions and alternatives
| Decision | Alternative | Why this one |
|---|---|---|
| curated PostgreSQL knowledge + RAG | fine-tuning, or Gemini alone | auditable sources; no training data/cost; facts can be corrected by editing rows |
| deterministic concept extraction | LLM extraction | testable, free, predictable; LLM can be added later if measured to help |
| exact/alias/usage matching | PostgreSQL full-text search, embeddings | knowledge base is tiny; embeddings return a nearest neighbour even when no mapping exists, which would invent associations |
| prompt asks for JSON + our own validation | provider structured-output feature | fewer dependencies on SDK details; the grounding checks are needed anyway |
| guards reject suspicious AI text and fall back | trust the model | a made-up error about a learner's practice is worse than plainer wording |
| JSON(B) for evaluation/feedback documents | many normalized tables | versioned contracts read whole; re-validated on every read |
| in-memory rate limiter | Redis / gateway limiter | enough for a project; documented limits |
| Alembic baseline + additive migration | ad hoc `create_all` on every startup | preserves the existing schema while giving upgrades explicit version history |
