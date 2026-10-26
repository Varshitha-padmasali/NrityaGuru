# NrityaGuru

AI-assisted Bharatanatyam learning and practice platform (college mini-project).

| Folder | Owner | Status |
|---|---|---|
| `backend/` | Knowledge base, RAG tutor, evidence-grounded feedback | 52 source-cited catalogue entries; dataset image counts exposed in API |
| `frontend/` | Next.js frontend | Mudra catalogue, details, retrieval and tutor use the backend schemas |
| `evaluation_module/` | Landmark extraction, MLP and DTW | 27 mapped single-hand labels; model and MediaPipe task assets are not included |
| `vision/` | Video, hand/pose landmarks and Member 4 adapter | Existing vision pipeline and tests |
| `evaluation_stub/` | Evaluation examples | Clearly labelled mock documentation/data only |
| `docker-compose.yml` | - | local PostgreSQL only (not a backend container) |

Start with `backend/README.md`.
See `backend/docs/mudra_catalogue.md` for catalogue provenance, dataset validation, and
the distinction between 52 knowledge records, 50 dataset folders/48 mapped IDs, and the absent
loaded model.
