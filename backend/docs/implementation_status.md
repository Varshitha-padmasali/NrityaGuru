# NrityaGuru implementation status

Updated 27 October 2026. The complete repository audit, baseline findings, verified changes,
commands, and remaining work are in [project_audit.md](project_audit.md).

## Current status

| Capability | Status |
|---|---|
| FastAPI knowledge and RAG service | Implemented; retrieval/fallback works without Gemini credentials |
| Knowledge base | 52 source-cited names/categories; no entries are teacher-verified |
| Dataset | 50 folders / 28,431 valid JPGs / 48 candidate canonical IDs; crosswalk still requires teacher review |
| Frozen frontend integration | Backend adapters now match its numeric IDs and compact response shapes; no frontend files were modified. API endpoints verified inside the running containers |
| Gemini | Grounded service and safe fallback implemented; `backend/.env` is loaded in Compose and the setting is verified, but no live provider call was made in this pass |
| Browser camera | Capture and recording components exist and have mock-based coverage; real hardware not tested |
| Practice references | API returns an empty list until a compatible classifier and validated reference sequences exist |
| Practice session/API | Session creation, bounded video upload/decode, result retrieval, and explicit unavailable responses implemented; landmark inference is blocked |
| Reference management | Versioned SQL storage and reviewer-token protected intake/list endpoints implemented; no authentic recordings are available |
| MLP | Training/prediction pipeline exists; no trained artifact is available |
| DTW | Sequence algorithm exists; no authentic reference sequences are available |
| Reference sequence contract | Version 1 validator, candidate preparation CLI, persistence and reviewer-token intake are implemented; no authentic recordings are present |
| Progress/access | Development history is explicitly installation-wide/shared; progress, session, result and feedback access are blocked in production until authentication is added |
| Database | PostgreSQL was healthy before the Docker daemon became unavailable; local fresh SQLite is migrated and seeded with 52 mudras, 4 sources, and 398 mappings |
| Deployment | Backend image rebuilt and running; an existing frontend container is healthy. Frontend source has no Dockerfile, so a clean frontend image rebuild is blocked by the strict frontend freeze |

## Test evidence

Latest executed checks:

- Backend: 541 passed, 1 deselected, 1 third-party deprecation warning after retry and fallback-message updates.
- Evaluation module: 53 passed (run with `PYTHONPATH=.` from `evaluation_module/`), including variant exclusion, model dependency-version checks, candidate preparation and reference-contract tests.
- Vision module: 71 passed.
- Frontend: 58 Vitest tests passed; the restored frontend source/config was left unchanged.
- PostgreSQL: Compose DB and backend are running; `/health/ready` reports `database: ok`; the live
  schema is at Alembic revision `0002_practice_reference`; 52 mudras, 3 sources, 6 mappings.
  The frontend container responds HTTP 200. Read-only API checks return all 52 mudras with numeric
  UI IDs, a source-cited river→Pataka match labelled `needs_review`, knowledge-only tutor fallback,
  and zero practice targets while evaluation assets are absent.
- Frontend: 58 Vitest tests passed. No frontend source/config files were changed. SHA-256
  verification passed for all 133 baseline files. The existing
  healthy container was not rebuilt; the repository's `frontend/` directory has no Dockerfile.
- Dataset validation: 50 folders and 28,431 images decoded; 0 unreadable images.
- Backend `docker compose up -d --build db backend`: passed without removing volumes. Full
  frontend image rebuild is not available under the strict frontend freeze because no Dockerfile
  exists in the restored frontend source.
- Practice/reference and video-limit API tests are included in the 497 backend pass total.

The Python suites use deterministic unit/integration fixtures; they do not establish real Gemini,
camera, model-accuracy, or trained-model behavior. PostgreSQL connectivity/migrations and live API
response shapes were separately checked in the running containers.

## Important limits

The official MediaPipe hand task file was downloaded to ignored `artifacts/`. It initializes and
detects a hand in a sample image in the Linux/amd64 evaluation image. Full extraction was attempted
in four workers, but Docker Desktop's daemon exited with an unexpected EOF; only partial CSVs were
produced and removed, no MLP was trained, and no accuracy is reported. The macOS native MediaPipe
graph also failed on this host. The backend evaluation gate remains off. Artifacts are not in Git.

The local SQLite database was not reset or migrated. Compose initialized its PostgreSQL volume,
then applied Alembic revision `0002_practice_reference` and idempotently seeded 52 mudras, three
sources, and 398 mappings. No practice session was written during live verification. Compose passed
the key setting through to the backend container; the key itself was never printed or logged.

No real reference sequences or reference media are present. Candidate/verified intake is now
persistent and reviewer-token gated. Synthetic demo sequences and mock
evaluation responses are explicitly test-only and must not be presented as real performance
results.
