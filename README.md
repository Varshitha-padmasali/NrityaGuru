# NrityaGuru

AI-assisted Bharatanatyam learning and practice platform (college mini-project).

| Folder | Owner | Status |
|---|---|---|
| `backend/` | Knowledge base, RAG tutor, evidence-grounded feedback | 52 source-cited catalogue entries; dataset and full model coverage remain unverified |
| `frontend/` | Next.js frontend | Existing UI; live API contract still needs alignment with backend schemas |
| `evaluation_module/` | Landmark extraction, MLP and DTW | Single-hand MLP pipeline; training assets are not included |
| `vision/` | Video, hand/pose landmarks and Member 4 adapter | Existing vision pipeline and tests |
| `evaluation_stub/` | Evaluation examples | Clearly labelled mock documentation/data only |
| `docker-compose.yml` | - | local PostgreSQL only (not a backend container) |

Start with `backend/README.md`.
See `backend/docs/mudra_catalogue.md` for catalogue provenance, dataset validation, and
the distinction between 52 knowledge records and the unverified Kaggle/model class coverage.
