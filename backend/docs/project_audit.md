# NrityaGuru Project Audit and Completion Record

Updated 27 October 2026. This report distinguishes code present in the repository from
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
- Docker Compose has PostgreSQL, backend, and frontend services. The backend image has a
  Dockerfile; the restored `frontend/` source has no Dockerfile even though Compose references
  one. An already-running frontend container remains healthy, but a clean frontend image build
  cannot be reproduced without changing frontend build configuration.

## Baseline audit

| Area | Before this implementation pass | Finding |
|---|---|---|
| Knowledge and RAG | Backend services, schemas, seed records, and API routes existed | 52 names/categories were source-cited; only three entries had sourced usage text; no teacher-verified entries |
| Dataset and classifier | Dataset validator and MLP/DTW code existed | 50 folders / 28,431 images; 48 candidate canonical IDs; no MediaPipe task asset, trained model bundle, or evaluation reference sequences |
| Frontend learning | Restored approved pages and UI are the source of truth | The frozen frontend expects numeric IDs/compact response shapes; backend canonical IDs and schemas used strings/richer objects |
| Webcam flow | Browser camera, recording, upload state machine, results and progress pages existed | Frontend called practice routes that FastAPI did not expose; it also treated string canonical reference IDs as numeric |
| Session/progress | Persistence models, repository, and feedback workflow existed | No HTTP progress route; no capture-to-database evaluation service |
| Database/deployment | SQLAlchemy, idempotent seed, Alembic and Compose are present | Frontend build file is missing; local SQLite contains seed data, and Compose PostgreSQL was initialized and migrated in this pass |
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
- Added backend-only adapters for the frozen frontend: deterministic numeric aliases over string
  database IDs, the UI's mudra/detail/retrieval/tutor response shapes, numeric practice session
  fields, `/api/movements` as the practice-target list, and the expected per-session feedback route.
  Canonical IDs remain available as `canonical_id`; internal persistence IDs are unchanged.
- Knowledge retrieval and catalogue endpoints include source-cited catalogue entries by default,
  labelling them `needs_review` and including their source. Records with no source require the
  explicit `ALLOW_UNVERIFIED_RECORDS` option. Practice-reference lookup remains verified-only. The UI receives no practice targets without valid
  model/reference assets.
- Made no changes to any file under `frontend/`; recorded SHA-256 hashes for all 133 frontend
  source/config files and verified them after implementation.
- Rebuilt and started the backend with PostgreSQL. Alembic revision `0002_practice_reference`
  ran and the repeatable seed loaded 52 mudras, 4 sources, and 398 mappings. No volume was removed.
- Configured Compose to load the server-only `backend/.env` for the backend container. Verified
  the Gemini setting is present by checking only its boolean state and confirmed backend
  readiness. No Gemini API request was made.
- Downloaded Google's official Hand Landmarker task to the ignored `artifacts/` directory, verified
  that it initializes in Linux Docker, and detected one hand in a local sample image. The full
  dataset pass was stopped because AMD64 emulation on this Apple Silicon host was too slow; no
  partial CSV or model was retained.

## Feature status

| Feature | Status | Evidence / dependency |
|---|---|---|
| FastAPI imports and HTTP app startup | Complete and live-tested | Running backend responds to health/readiness and frontend-shaped APIs inside Docker |
| PostgreSQL persistence | Complete and live-tested | Compose readiness passed; migration revision `0002_practice_reference` and PostgreSQL catalog queries succeeded |
| Idempotent knowledge seed | Complete and live-tested | PostgreSQL has 52 mudras, 4 sources, 398 mappings; startup seed is repeatable |
| Frozen frontend contract integration | Implemented and tested | Numeric aliases, catalogue/detail/retrieval/tutor/session/progress/feedback shapes adapted in backend; no frontend files changed |
| Gemini configuration and guarded integration | Configured; provider calls not made | `backend/.env` is loaded by Compose; backend reports key configured without revealing it; Gemini tests use fakes and pass; no live request was made |
| Knowledge retrieval and grounded fallback | Implemented and live-tested | River retrieved Pataka as `needs_review`; grounded fallback remains available when Gemini is unavailable |
| Dataset validation and canonical crosswalk | Dataset scan complete; task inference smoke-tested | 50 directories, 28,431 readable JPGs; official task detects a hand in Docker; candidate label crosswalk awaits expert review |
| MLP/DTW algorithms | Implemented and unit-tested | No trained bundle or genuine reference sequences; no real prediction/evaluation claim |
| Reference sequence format | Implemented and unit-tested | Version 1 validator exists; teacher-approved reference clips are still required |
| Browser camera and recording controls | Implemented with mocked tests | No real camera/browser end-to-end run was performed in this pass |
| Practice reference discovery | Complete as a safe capability boundary | Returns `[]` until model and validated reference sequences exist |
| Session API and bounded video decoding | Implemented, partial | Creation/upload/results endpoints, temp cleanup, and resource limits exist; evaluation still returns a structured unavailable response without a compatible task/model/reference and verified runtime |
| Reference persistence/intake | Implemented, partial | Versioned table and reviewer-token intake exist; no real recordings/reviews exist |
| Progress API | Implemented and tested | Numeric UI IDs; development history remains shared; no authenticated account separation |
| Existing frontend container | Reachable, read-only verified | Container health is healthy and it returns HTTP 200; no browser camera/console workflow was run |
| Fresh frontend image build | Blocked by strict frontend freeze | `frontend/Dockerfile` is absent while Compose points to it. Adding a build file or Tailwind PostCSS setup would change frontend build configuration and requires user approval |
| Database/session camera workflow | Partially implemented | Current practice-target list is empty. No session was written during live verification because no real model/reference target exists |

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

Latest results: backend 541 passed/1 deselected; evaluation 53 passed; vision 71 passed;
frontend Vitest 58 passed without editing frontend files.
The backend Docker image built and ran; PostgreSQL readiness and frontend HTTP 200 were verified.

## Reproducible local startup

With Docker Desktop running:

```bash
docker compose up -d --build db backend
```

PostgreSQL is available on host port 5433, FastAPI on `http://localhost:8000` (Swagger at `/docs`),
and the existing Next.js container on `http://localhost:3000`. Compose migrates and seeds PostgreSQL
on backend startup and reads the server-side key from `backend/.env`. The current frontend container
remains untouched. A clean frontend build cannot be performed until its missing Dockerfile is
supplied. Gemini provider authentication/model entitlement has not been verified with a live API
request. The configured browser origin is
`http://localhost:3000`.

Alembic migration execution was verified against the Compose PostgreSQL service. No Docker volume
was removed and the local SQLite database was left untouched.

## Remaining work and order

1. Run dataset extraction and MLP training on a native Linux/AMD64 host (or another suitable
   accelerator); report held-out metrics and verify uncertain class mappings with a dance teacher.
2. Collect genuine consented teacher recordings (the user can provide these), convert them to candidate references, obtain
   teacher review, and ingest the approved sequences.
3. Run the separate native-runtime smoke command with the produced artifacts; only then enable
   the evaluator gate and exercise the actual browser camera flow.
4. Only if authorized later, run a real Gemini API check; live calls were intentionally not made
   during this pass. Test the camera in a browser and supply authentic teacher references/model
   assets before enabling evaluation.
5. Ask before adding a frontend Dockerfile/PostCSS build setup; the strict frontend freeze currently
   prevents a clean frontend image build from source.
