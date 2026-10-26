# NrityaGuru Project Audit and Completion Record

Updated 26 October 2026. This report distinguishes code present in the repository from
features verified against a live service, real camera, Gemini, PostgreSQL, or trained model.

## Architecture found

- Next.js/React/TypeScript frontend. It contains the learning and mudra pages, API client,
  browser camera/MediaRecorder hooks, practice state machine, results view, and progress UI.
- FastAPI backend. Its knowledge path is text normalization and concept extraction → curated
  mapping/retrieval from SQLAlchemy → grounded tutor response. Tutor and corrective feedback
  use the Google Gen AI SDK when configured and validated evidence-only fallbacks otherwise.
- SQLAlchemy models and idempotent JSON seed data cover sources, 52 mudras, movements,
  concept mappings, practice sessions, evaluation results, and feedback.
- `vision/` contains video reading, hand/pose detector adapters, normalization, feature
  extraction, sequence construction, and the Member 4 adapter.
- `evaluation_module/` contains dataset validation, hand-landmark extraction from still images,
  a single-hand MLP training/inference pipeline, and DTW sequence comparison.
- Docker Compose originally contained PostgreSQL only. Backend/frontend container definitions
  and health checks have now been added, but Docker could not be run in this environment.

## Baseline audit

| Area | Before this implementation pass | Finding |
|---|---|---|
| Knowledge and RAG | Backend services, schemas, seed records, and API routes existed | 52 names/categories were source-cited; only three entries had sourced usage text; no teacher-verified entries |
| Dataset and classifier | Dataset validator and MLP/DTW code existed | 50 folders / 28,431 images; 48 candidate canonical IDs; no MediaPipe task asset, trained model bundle, or evaluation reference sequences |
| Frontend learning | Catalogue, text retrieval, tutor, and detail pages existed | Frontend knowledge contracts had already been aligned to backend; real Gemini was unconfigured |
| Webcam flow | Browser camera, recording, upload state machine, results and progress pages existed | Frontend called practice routes that FastAPI did not expose; it also treated string canonical reference IDs as numeric |
| Session/progress | Persistence models, repository, and feedback workflow existed | No HTTP progress route; no capture-to-database evaluation service |
| Database/deployment | SQLAlchemy `create_all`, repeatable seed, Postgres compose service | No migrations; Docker daemon absent; an existing local SQLite database has 52 mudras but zero movement/session rows |
| QA | Backend/evaluation/vision/frontend test suites existed | Frontend lint had one actual error; docs overstated route completion and had stale test claims |

## Corrected in this pass

- Added `GET /api/practice/references`. It publishes no targets until the application has a
  compatible trained classifier and validated reference sequence; the current response is an
  honest empty list. A Kaggle image folder is not treated as a performance sequence.
- Added `GET /api/progress`, which reads persisted session, evaluation, and feedback records
  without inventing missing predictions or metrics. History remains global because there is no
  authentication/user model.
- Added a versioned reference-sequence validator at `evaluation_module/sequence/reference.py`.
  It requires teacher verification, source/consent/reviewer provenance, finite non-empty feature
  matrices, and an exact feature-schema match. It does not add or imply that any reference data
  currently exists.
- Added a persisted `reference_sequences` table, Alembic adoption/upgrade revisions, and
  reviewer-token protected candidate/verified intake with a server-configured reviewer identity.
- Added practice-session creation, bounded temporary video upload, MP4/WebM container validation,
  OpenCV frame decoding limits, result retrieval, and structured errors when evaluator artifacts
  or a validated native runtime are absent. Temporary video files are removed after each request.
- Disabled `/api/progress` in production while identity/ownership is absent; development/test
  progress remains installation-wide and is documented as shared.
- Changed the frontend practice-reference client to use `/api/practice/references`, keeping the
  existing knowledge-base `/api/movements` route distinct. Practice route IDs are now treated as
  strings so canonical IDs work without numeric coercion.
- Updated the practice empty state to explain the missing model/reference dependency.
- Removed the TypeScript lint error and two unused-variable warnings found by `npm run lint`.
- Added full-stack Dockerfiles and Compose services for API and frontend alongside PostgreSQL,
  with startup seed and readiness checks. Docker execution remains unverified because the local
  Docker daemon is unavailable.

## Feature status

| Feature | Status | Evidence / dependency |
|---|---|---|
| FastAPI imports and HTTP app startup | Complete and tested | Earlier local HTTP smoke covered health/readiness, catalogue, retrieval, tutor fallback, practice and progress. In the latest pass, Uvicorn TCP and Unix-socket binds were denied by the sandbox; route behavior was still exercised with TestClient. |
| PostgreSQL persistence | Implemented, not verified here | Alembic revisions and Compose config exist; Docker daemon unavailable, tests use SQLite |
| Idempotent knowledge seed | Complete and tested | Backend tests and existing local database contain 52 seeded records |
| Knowledge retrieval and grounded fallback | Implemented and unit-tested | Real Gemini request not run; no API key was available |
| Dataset validation and canonical crosswalk | Complete for current local dataset scan | 50 directories, 28,431 readable JPGs, no corrupt images; candidate label crosswalk awaits expert review |
| MLP/DTW algorithms | Implemented and unit-tested | No trained bundle or genuine reference sequences; no real prediction/evaluation claim |
| Reference sequence format | Implemented and unit-tested | Version 1 validator exists; no reference recordings have been supplied/reviewed |
| Browser camera and recording controls | Implemented with mocked tests | No real camera/browser end-to-end run was performed in this pass |
| Practice reference discovery | Complete as a safe capability boundary | Returns `[]` until model and validated reference sequences exist |
| Session API and bounded video decoding | Implemented, partial | Creation/upload/results endpoints, temp cleanup, and resource limits exist; evaluation still returns a structured unavailable response without a compatible task/model/reference and verified runtime |
| Reference persistence/intake | Implemented, partial | Versioned table and reviewer-token intake exist; no real recordings/reviews exist |
| Progress API | Implemented and tested | Reads existing persistence schema; no authenticated account separation |
| Frontend production build and live pages | Complete and tested | `next build --webpack` passed; production server returned 200 for home, learn, mudras, practice and progress; browser verified the catalogue, river → Pataka retrieval/fallback, practice unavailable state, and empty history |
| Full Docker stack | Implemented, not verified | Docker CLI could not connect to local daemon |

## Data and ML constraints

The dataset scan and exact per-folder crosswalk are documented in `mudra_catalogue.md` and
`../data/seed/dataset_mapping.json`. Dataset folder aliases, spelling normalization, and the
three Katakamukha folders remain candidate mappings requiring Bharatanatyam teacher validation.
The MLP's 27 single-hand candidate labels are not certified classes. The 24 two-hand catalogue
entries are not supported by the current single-hand MLP. Historical metric files are not
reproducible results for the current mapping/model.

The frontend recording component captures locally and submits to the new bounded upload route.
When multipart dependencies and OpenCV are installed, FastAPI validates and decodes the temporary
clip before returning an honest evaluator-unavailable response if model/task assets or a verified
runtime are absent. No authentic reference sequence is present, so DTW cannot compare a learner
with a genuine teacher performance. No frame-based feedback can currently be produced.

## Verified commands

```bash
# backend/
../.venv/bin/pytest -q

# evaluation_module/
PYTHONPATH=. ../.venv/bin/pytest -q tests

# vision/
../.venv/bin/pytest -q tests

# frontend/
npm test
npm run typecheck
npm run lint
npm run build
```

Latest results: backend 495 passed/1 deselected; evaluation 53 passed; vision 71 passed;
frontend 58 passed plus typecheck, lint and production build. `docker compose config -q`
passed. The full current detailed status is in [implementation_status.md](implementation_status.md).

## Reproducible local startup

With Docker Desktop running:

```bash
docker compose up --build
```

PostgreSQL is available on port 5432, FastAPI on `http://localhost:8000` (Swagger at `/docs`),
and Next.js on `http://localhost:3000`. Compose seeds the database on API startup. Set
`GEMINI_API_KEY` in the shell before Compose if live Gemini explanations are desired; no key is
required for retrieval or fallback explanations. The configured browser origin is
`http://localhost:3000`.

Alembic migrations now adopt the existing `create_all` schema and add practice/reference tables
without dropping records. The local database was not reset, and migration execution was not
verified because Alembic could not be installed without network access.

## Remaining work and order

1. Run the Linux/amd64 evaluation container from `mac_m1_runbook.md` to process actual dataset
   images, train the MLP, and produce honest held-out metrics; verify uncertain class mappings
   with a dance teacher before describing classes as culturally verified.
2. Collect genuine consented teacher recordings, convert them to candidate references, obtain
   teacher review, and ingest the approved sequences.
3. Run the separate native-runtime smoke command with the produced artifacts; only then enable
   the evaluator gate and exercise the actual browser camera flow.
4. Run PostgreSQL and Docker checks, real Gemini smoke test with user credentials, and a
   deployment security review. Alembic migrations exist but were not run in this environment.
