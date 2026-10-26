# NrityaGuru backend (Member 2 module)

The knowledge and AI layer of NrityaGuru, an AI-assisted Bharatanatyam learning tool: a curated, source-tracked knowledge base in
PostgreSQL, concept extraction, retrieval, a Gemini RAG tutor, and evidence-grounded corrective feedback for results produced by the
evaluation module (OpenCV, MediaPipe, MLP, DTW).

The frontend, vision pipeline, and MLP/DTW code live in sibling directories. The backend reads
trusted evaluation results from PostgreSQL; a complete capture-to-storage runtime path and
production model assets are not present in this checkout.

**Honest status:** the knowledge seed contains 52 source-cited names/categories, not 52 fully
verified gesture descriptions. The Kaggle image dataset is absent, its license and actual classes
are unverified, and the Gemini code has not been run against the real API. Read
`docs/implementation_status.md` and `docs/mudra_catalogue.md`.

## How it fits together
```
Next.js frontend (separate) --HTTP--> FastAPI (this module)
   text   -> concept extraction -> retrieval (PostgreSQL) -> Gemini tutor -> validated answer (+ retrieved records)
   session id -> trusted store -> evidence assessment -> Gemini feedback -> validated feedback (stored, reusable)
Evaluation module (separate) --writes--> PostgreSQL (practice_sessions, evaluation_results)
```
Details: `docs/architecture.md`.

## Requirements
- Python 3.11 or newer recommended (3.10 minimum)
- Docker (for the local PostgreSQL) or your own PostgreSQL
- Optional: a Gemini API key from https://aistudio.google.com/apikey (without one, the tutor and feedback return the retrieved/evidence-only answer)

## Quick start (macOS/Linux; Windows PowerShell notes below)
Run these from the repository root unless stated.
```bash
docker compose up -d db                      # 1. local PostgreSQL (change the password for anything beyond your laptop)
cd backend
python3 -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt              # 2. dependencies (version ranges; run `pip freeze > requirements.lock.txt` to record exact versions)
cp .env.example .env                         # 3. settings (Windows: copy .env.example .env). Put your real key only in .env
python -m app.db.init_db                     # 4. create the tables (safe to repeat; only creates missing ones)
python -m app.db.seed                        # 5. load the validated seed data (safe to repeat)
python -m scripts.smoke_gemini               # 6. optional: checks your key, model id and SDK with one tiny request
uvicorn app.main:app --reload                # 7. run the API at http://127.0.0.1:8000 (interactive docs at /docs)
```
Try it:
```bash
curl http://127.0.0.1:8000/health/ready
curl -s -X POST http://127.0.0.1:8000/api/tutor/explain -H "Content-Type: application/json" \
  -d '{"text":"The river and the clouds","include_unverified":true}'
curl -s -X POST http://127.0.0.1:8000/api/feedback/generate -H "Content-Type: application/json" \
  -d '{"session_id":"mock-session-deviation"}'
```
The seed mudras are `source_cited`, not `verified`, so they are hidden unless `ALLOW_UNVERIFIED_RECORDS=true` (set in `.env.example` for development).

## Configuration (`.env`, loaded by `app/core/config.py`)
| Variable | Default | Meaning |
|---|---|---|
| APP_ENV | development | development / testing / production |
| LOG_LEVEL | INFO | DEBUG / INFO / WARNING / ERROR |
| GEMINI_API_KEY | unset | secret; backend only, never sent to the browser |
| GEMINI_MODEL | gemini-3.8-flash | model id (recommended for new projects by Google's Oct 2026 release notes; check https://ai.google.dev/gemini-api/docs/deprecations) |
| GEMINI_TIMEOUT_SECONDS | 30 | per request, 0 < value <= 120 |
| GEMINI_THINKING_LEVEL | unset | optional LOW / MEDIUM / HIGH (MINIMAL is rejected by the model) |
| TUTOR_RATE_LIMIT_PER_MINUTE | 20 | per client IP, shared by tutor and feedback endpoints |
| DATABASE_URL | unset | secret; e.g. postgresql+psycopg://user:password@localhost:5432/nrityaguru |
| ALLOW_UNVERIFIED_RECORDS | false (example file: true) | development only: let callers see source_cited/unverified records, clearly labelled |
| USE_MOCK_EVALUATION | false (example file: true) | development only: serve five MOCK evaluation sessions until the real module exists |
| CORS_ALLOW_ORIGINS | http://localhost:3000 | browser origins allowed to call the API, comma separated |
For production: `ALLOW_UNVERIFIED_RECORDS=false`, `USE_MOCK_EVALUATION=false`, a strong database password, your real frontend origin.

## Running the tests
```bash
cd backend && source .venv/bin/activate
pytest -q                          # everything except the live test
python -m scripts.static_checks    # 11 static checks (also run inside pytest)
pytest -m live                     # optional: one real Gemini call, mock data only
```
Expected summary: **476 passed, 1 deselected** with `google-genai` installed; **469 passed, 1 skipped, 1 deselected** without it
(the whole SDK test file is skipped as one module). If your numbers differ, see `docs/implementation_status.md`.

## API
Nine endpoints, listed in `docs/api_reference.md`.

## Project layout
```
app/
  api/
    deps.py
    feedback.py
    health.py
    knowledge.py
    tutor.py
  core/
    config.py
    enums.py
    errors.py
    logging.py
    rate_limit.py
  db/
    database.py
    init_db.py
    models.py
    seed.py
  integrations/
    database_evaluation_store.py
    evaluation_stub.py
  main.py
  repositories/
    errors.py
    feedback_repository.py
    knowledge_repository.py
    session_repository.py
  schemas/
    concepts.py
    evaluation.py
    feedback.py
    knowledge.py
    rag.py
    tutor.py
  services/
    concept_extraction.py
    concept_resolution.py
    evaluation_assessment.py
    evaluation_errors.py
    evaluation_evidence.py
    feedback_evidence.py
    feedback_fallback.py
    feedback_prompt.py
    feedback_service.py
    feedback_validation.py
    feedback_workflow.py
    gemini_client.py
    knowledge_matching.py
    knowledge_retrieval.py
    rag_evaluation.py
    rag_pipeline.py
    reference_lookup.py
    text_processing.py
    tutor_fallback.py
    tutor_prompt.py
    tutor_service.py
    tutor_validation.py
scripts/
  evaluate_rag.py
  export_contract_schema.py
  smoke_gemini.py
  static_checks.py
data/
  assets/
  eval/
    rag_queries.json
  seed/
    mappings.json
    movements.json
    mudras.json
    sources.json
docs/
  api_knowledge.md
  api_reference.md
  architecture.md
  concept_extraction.md
  evaluation_contract.md
  feedback.md
  frontend_integration.md
  gemini_tutor.md
  implementation_status.md
  rag_pipeline.md
  schema.md
  security_checklist.md
  viva_preparation.md
tests/   (one test_*.py per area, plus conftest.py and factories.py)
```

## Documentation index
| File | Content |
|---|---|
| docs/architecture.md | layers, data flows, role of each service, decisions and alternatives |
| docs/api_reference.md | every endpoint, statuses and errors |
| docs/implementation_status.md | feature checklist, test evidence, known limitations, final summary |
| docs/security_checklist.md | security and privacy controls and their evidence |
| docs/viva_preparation.md | questions and answers, demo script |
| docs/schema.md | database tables and what is stored |
| docs/concept_extraction.md, api_knowledge.md, gemini_tutor.md, rag_pipeline.md, evaluation_contract.md, feedback.md, frontend_integration.md | per-feature detail |

## Troubleshooting
| Symptom | Fix |
|---|---|
| `DATABASE_URL is not set` / 503 "database is not configured" | `cp .env.example .env` inside `backend/` and restart |
| `connection refused` | the container is not running: `docker compose ps`, then `docker compose up -d db` |
| `relation ... does not exist` | `python -m app.db.init_db` |
| everything `unsupported` / 404 for a seed mudra | the seed records are not verified: set `ALLOW_UNVERIFIED_RECORDS=true` in `.env` and restart |
| `fallback_reason: not_configured` | no `GEMINI_API_KEY` (or SDK missing): add the key, restart |
| `auth_or_model_error` | wrong key or model id: run `python -m scripts.smoke_gemini`; try `GEMINI_MODEL=gemini-3.5-flash-lite` |
| `rate_limited` / HTTP 429 | quota or per-IP limit reached: wait, or raise `TUTOR_RATE_LIMIT_PER_MINUTE` |
| `store_unavailable` (503) on feedback | no evaluation integration yet: set `USE_MOCK_EVALUATION=true` for the mock sessions |
| browser CORS error | add the frontend URL to `CORS_ALLOW_ORIGINS` and restart |
Windows: use `copy` instead of `cp`, `.venv\Scripts\Activate.ps1` to activate, and run the same `python -m ...` commands.
