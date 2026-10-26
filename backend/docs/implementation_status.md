# NrityaGuru implementation status

Updated 26 October 2026. The complete repository audit, baseline findings, verified changes,
commands, and remaining work are in [project_audit.md](project_audit.md).

## Current status

| Capability | Status |
|---|---|
| FastAPI knowledge and RAG service | Implemented; retrieval/fallback works without Gemini credentials |
| Knowledge base | 52 source-cited names/categories; no entries are teacher-verified |
| Dataset | 50 folders / 28,431 valid JPGs / 48 candidate canonical IDs; crosswalk still requires teacher review |
| Frontend catalogue and learning flow | Connected to real backend schemas; local HTTP retrieval was verified |
| Gemini | Grounded service and safe fallback implemented; real API call not run because no key is configured |
| Browser camera | Capture and recording components exist and have mock-based coverage; real hardware not tested |
| Practice references | API returns an empty list until a compatible classifier and validated reference sequences exist |
| Practice session/API | Session creation, bounded video upload/decode, result retrieval, and explicit unavailable responses implemented; landmark inference is blocked |
| Reference management | Versioned SQL storage and reviewer-token protected intake/list endpoints implemented; no authentic recordings are available |
| MLP | Training/prediction pipeline exists; no trained artifact is available |
| DTW | Sequence algorithm exists; no authentic reference sequences are available |
| Reference sequence contract | Version 1 validator, candidate preparation CLI, persistence and reviewer-token intake are implemented; no authentic recordings are present |
| Progress/access | Development history is explicitly installation-wide/shared; progress, session, result and feedback access are blocked in production until authentication is added |
| Database | SQLAlchemy schema, idempotent seed, Alembic baseline/upgrade revisions; PostgreSQL/Docker not verified in this environment |
| Deployment | Dockerfiles and Compose services added; Docker daemon unavailable for execution |

## Test evidence

Latest executed checks:

- Backend: 495 passed, 1 deselected, 1 third-party deprecation warning.
- Evaluation module: 53 passed (run with `PYTHONPATH=.` from `evaluation_module/`), including variant exclusion, model dependency-version checks, candidate preparation and reference-contract tests.
- Vision module: 71 passed.
- Frontend: 58 passed; TypeScript, ESLint, and webpack production build passed.
- Local database setup: a separate temporary SQLite database initialized and seeded successfully
  (52 mudras, 3 sources, 6 mappings). Uvicorn could not bind TCP or Unix sockets under the
  sandbox; route behavior was exercised with FastAPI TestClient. The earlier browser/API smoke
  flow verified the knowledge pages and unavailable practice state.
- Dataset validation: 50 folders and 28,431 images decoded; 0 unreadable images.
- `docker compose config -q`: passed. Container build/run was not possible because Docker
  Desktop is not running.
- Practice/reference and video-limit API tests are included in the 495 backend pass total.
  Alembic execution is not verified because package installation failed without network access.

The Python suites use deterministic unit/integration fixtures; they do not establish real Gemini,
camera, model-accuracy, PostgreSQL, or trained-model behavior.

## Important limits

The real MediaPipe hand task file was downloaded to temporary storage and tested on this Mac.
MediaPipe's native graph failed to start because it required an unavailable macOS GPU service,
even with CPU delegate selection and a second tested MediaPipe version. The Linux/amd64
extraction/training container and runbook are present, but Docker could not run here. No real
landmarks were extracted, no MLP was trained, and no accuracy is reported. Artifacts are not in Git.

The local SQLite database was inspected read-only and contains 52 mudras, three sources, six
concept mappings, zero movements, and zero practice sessions/results/feedback. The database was
not reset or migrated. A separate temporary SQLite database was initialized for a smoke setup.
Alembic revisions adopt the existing `create_all` schema and add practice status/reference
tables, but migration execution remains unverified here.

No real reference sequences or reference media are present. Candidate/verified intake is now
persistent and reviewer-token gated. Synthetic demo sequences and mock
evaluation responses are explicitly test-only and must not be presented as real performance
results.
