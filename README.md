# NrityaGuru

AI-assisted Bharatanatyam learning and practice platform (college mini-project).

| Folder | Owner | Status |
|---|---|---|
| `backend/` | Knowledge base, tutor, practice sessions, upload/decode, feedback | 52 source-cited catalogue entries; no verified model or movement references |
| `frontend/` | Next.js frontend | Mudra catalogue, details, retrieval and tutor use the backend schemas |
| `evaluation_module/` | Landmark extraction, MLP and DTW | Reproducible data/training/reference preparation; model and task assets are not included |
| `vision/` | Video, hand/pose landmarks and Member 4 adapter | Existing vision pipeline and tests |
| `evaluation_stub/` | Evaluation examples | Clearly labelled mock documentation/data only |
| `docker-compose.yml` | - | local PostgreSQL, FastAPI and Next.js services |

Start with `backend/README.md`.
See `backend/docs/mudra_catalogue.md` for catalogue provenance, dataset validation, and
the distinction between 52 knowledge records, 50 dataset folders/48 mapped IDs, and the absent
loaded model.
See `backend/docs/project_audit.md` for verified status and remaining external dependencies.
For MacBook Air M1 startup, dataset preparation, evaluator setup, and reviewer-managed reference
intake, follow [the M1 runbook](backend/docs/mac_m1_runbook.md).

With Docker Desktop running, start PostgreSQL and the backend without disturbing the frozen
frontend using `docker compose up -d --build db backend`. The current frontend container is already
running from its existing image. A fresh frontend image rebuild is blocked because the restored
`frontend/` directory has no Dockerfile; no frontend files were changed. Practice targets remain
empty until compatible MediaPipe/model artifacts and teacher-reviewed reference sequences exist.
Development progress is shared and production session endpoints remain disabled until
authentication/ownership is implemented. See [the audit](backend/docs/project_audit.md) for the
verified runtime status and the exact frontend rebuild blocker.
