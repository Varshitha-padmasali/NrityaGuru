# NrityaGuru Backend (Member 2)

Knowledge base, RAG tutor and feedback API. Implemented so far: Part 1 (FastAPI foundation), Part 2 (database + knowledge schema), Part 3 (concept extraction), Part 4 (retrieval + knowledge API), Part 5 (Gemini client + tutor service), Part 6 (RAG pipeline + /api/tutor/explain), Part 7 (evaluation contract + evidence validation), Part 8 (feedback + /api/feedback/generate), Part 9 (persistence + integration).

## Setup
    cd backend
    python -m venv .venv
    source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    cp .env.example .env             # Windows: copy .env.example .env

## Database (PostgreSQL via Docker)
    docker compose up -d db          # run from the repo root
    python -m app.db.init_db         # create tables (from backend/)
    python -m app.db.seed            # load validated seed data

## Run
    uvicorn app.main:app --reload    # http://127.0.0.1:8000/health and /docs

## Test
    pytest -v

See docs/schema.md (schema), docs/concept_extraction.md, docs/api_knowledge.md (endpoints), docs/gemini_tutor.md (Gemini + tutor), docs/rag_pipeline.md (pipeline, endpoint, evaluation), docs/evaluation_contract.md (contract with the evaluation module), docs/feedback.md (feedback endpoint and guards), docs/frontend_integration.md (for the frontend teammate).

Set `ALLOW_UNVERIFIED_RECORDS=true` in `.env` (development only) to see the seed records,
which are `source_cited` and therefore hidden by default.

## Gemini check
    python -m scripts.smoke_gemini    # needs GEMINI_API_KEY in .env
    pytest -m live                    # optional live test

## RAG evaluation
    python -m scripts.evaluate_rag    # needs seeded DB; writes eval_output/review_sheet.md for human scoring

## Evaluation contract
    python -m scripts.export_contract_schema   # writes docs/evaluation_result.schema.json for the evaluation teammate

## After pulling Part 9
    python -m app.db.init_db     # creates the 3 new tables (existing tables are untouched)
    curl http://127.0.0.1:8000/health/ready
