# NrityaGuru — Frontend ↔ Backend API Contract (v0.1)

This is the contract the frontend is built against. The FastAPI backend must
return exactly these shapes (Pydantic models with the same field names).
The TypeScript mirrors live in `frontend/types/*.ts`, and the runtime checks in
`frontend/lib/validators.ts`. **If a field changes, update this file, the
types and the validators together.**

Conventions
- Base URL comes from `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`).
- JSON everywhere except the video upload (multipart).
- Timestamps: ISO 8601 strings in UTC, e.g. `"2026-10-24T14:30:00Z"`.
- IDs: integers.
- Nullable fields are always present (as `null`), never omitted.
- Errors use FastAPI's default shape: `{"detail": "message"}` or the 422 list form.
  Status codes the UI understands: 400/422 (validation), 404, 413 (file too large),
  503 (dependency unavailable, e.g. Gemini), anything else = generic error.
- CORS: allow the frontend origin (`http://localhost:3000` in development).

---

## 1. Health

`GET /health` → `200`
```json
{ "status": "ok", "db": "ok", "model_loaded": true }
```
`status`: `"ok" | "degraded"`. `db` and `model_loaded` are optional.

## 2. Mudras

`GET /api/mudras` → `200` — `MudraSummary[]`
```json
[{ "id": 1, "name": "Pataka", "hasta_type": "asamyuta", "meaning": "Flag", "image_url": "/static/mudras/pataka.jpg" }]
```
- `hasta_type`: `"asamyuta" | "samyuta" | null`
- `image_url`: absolute URL **or** a path relative to the backend (served by FastAPI `StaticFiles`), or `null`.

`GET /api/mudras/{id}` → `200` — `MudraDetail` (all summary fields plus):
```json
{
  "alt_names": [],
  "usage": "…",
  "instructions": "…",
  "source": "Abhinaya Darpana, verse …",
  "verification_status": "verified",
  "practice_reference_id": 101
}
```
- `verification_status`: `"verified" | "unverified" | "needs_review"`
- `practice_reference_id`: id from `/api/movements` if this mudra can be evaluated, else `null`.
- `404` if not found.

## 3. Knowledge retrieval

`POST /api/knowledge/retrieve`
```json
{ "text": "Krishna is singing and dancing in the garden." }
```
Validation: 3–500 characters after trimming (return 422 otherwise).

→ `200`
```json
{
  "query": "Krishna is singing and dancing in the garden.",
  "concepts": [
    {
      "concept": "garden",
      "supported": true,
      "matches": [
        { "id": 4, "name": "…", "hasta_type": "asamyuta", "meaning": "…", "image_url": "…", "rationale": "Why the KB links this mudra to the concept", "source": "…" }
      ]
    },
    { "concept": "krishna", "supported": false, "matches": [] }
  ]
}
```
- Several `matches` = alternative interpretations (the UI labels them "Option 1, 2…").
- `supported: false` / empty `matches` = no verified mapping; the UI says so instead of guessing.
- An empty `concepts` array is valid.

## 4. AI tutor

`POST /api/tutor/explain`
```json
{ "text": "learner's text", "mudra_ids": [1, 4] }
```
→ `200`
```json
{ "explanation": "Plain text, paragraphs separated by blank lines.", "used_mudra_ids": [1, 4], "unsupported_concepts": ["krishna"], "model_name": "gemini-2.5-flash" }
```
- The backend must ground the answer only in the knowledge-base rows for `mudra_ids`.
- `503` when Gemini is unavailable — the UI keeps the retrieval results visible and offers retry.

## 5. Practice references

`GET /api/movements` → `200` — `PracticeReference[]`
```json
[{ "id": 101, "name": "Pataka (hold)", "reference_type": "mudra", "description": "…", "mudra_ids": [1], "image_url": "…", "max_duration_seconds": 5 }]
```
- Only list references that the evaluation pipeline can actually evaluate.
- `reference_type`: `"mudra" | "sequence"`; `mudra_ids` is ordered for sequences.
- `max_duration_seconds` may be `null` (frontend default: 8 s).

## 6. Practice sessions

`POST /api/practice/sessions`
```json
{ "reference_id": 101 }
```
→ `201` (or 200) — `PracticeSession`
```json
{ "session_id": 12, "reference_id": 101, "status": "created", "created_at": "2026-10-24T14:30:00Z" }
```
`status`: `"created" | "uploaded" | "processing" | "evaluated" | "failed"`

`POST /api/practice/sessions/{session_id}/video` — `multipart/form-data`
| field | type | notes |
|---|---|---|
| `video` | file | `video/webm` (Chrome/Edge/Firefox) or `video/mp4` (Safari). Max 10 MB, max ~8 s. |
| `reference_id` | string (int) | must match the session's reference |

→ `200` — `PracticeSession` with `status: "uploaded"`. `413` if too large, `422` if wrong type.
The backend should accept **both WebM and MP4** (OpenCV can read both if FFmpeg is available).

`POST /api/practice/sessions/{session_id}/evaluate` (empty JSON body `{}`)
→ `200`
```json
{ "session_id": 12, "status": "evaluated", "result": { …EvaluationResult… }, "error": null }
```
- May instead return `"status": "processing"` with `result: null`; the frontend then polls
  `GET …/results` every 2 s for up to 90 s.
- `"status": "failed"` with a human-readable `error` (e.g. "No hands detected in enough frames").

`GET /api/practice/sessions/{session_id}/results` → `200`
```json
{ "session": { …PracticeSession… }, "result": { …EvaluationResult… } , "feedback": null }
```
`result` is `null` until evaluated; `feedback` is `null` until generated.

### EvaluationResult
```json
{
  "reference": { "id": 101, "name": "Pataka (hold)" },
  "predictions": [ { "label": "Pataka", "confidence": 0.91, "frame_start": 0, "frame_end": 59 } ],
  "dtw": { "distance": 12.48, "normalized": 0.21, "path_length": 60 },
  "frames_total": 60,
  "frames_with_landmarks": 57,
  "fps": 30,
  "deviations": [
    { "kind": "wrong_label", "message": "Between 0.8 s and 1.4 s the model detected Tripataka instead of Pataka.", "frame_start": 24, "frame_end": 42, "expected_label": "Pataka", "predicted_label": "Tripataka" }
  ],
  "warnings": ["Hand was not detected in 3 frames."],
  "model_version": "mlp-2026-10-20",
  "feature_schema": "hand_v1",
  "created_at": "2026-10-24T14:31:02Z"
}
```
- `predictions`: contiguous stretches of frames with the same MLP label; `confidence` is the
  model probability (0–1), **not** a correctness score.
- `dtw`: `null` if no sequence comparison was run. `normalized` is optional and must be defined
  in backend docs (e.g. distance ÷ path length).
- `deviations[].kind`: `"wrong_label" | "feature_deviation" | "high_alignment_cost" | "insufficient_landmarks"`.
- `fps` lets the UI show seconds instead of frame numbers (may be `null`).

## 7. Feedback

`POST /api/practice/sessions/{session_id}/feedback` (empty JSON body `{}`)
→ `200`
```json
{ "text": "Feedback paragraphs…", "model_name": "gemini-2.5-flash", "created_at": "…" }
```
- Generated **only** from the stored EvaluationResult + reference info.
- Idempotent: if feedback already exists, return it instead of calling Gemini again.
- `503` when Gemini is unavailable (results stay visible; user can retry).
- `409` if the session isn't evaluated yet.

## 8. Progress

`GET /api/progress` → `200`
```json
{
  "sessions": [
    { "session_id": 12, "reference_id": 101, "reference_name": "Pataka (hold)", "status": "evaluated", "created_at": "…",
      "dtw_normalized": 0.21, "top_label": "Pataka", "top_confidence": 0.91, "feedback_summary": "First line of feedback or null" }
  ]
}
```
Trends are drawn only from `dtw_normalized` and only for references with ≥ 2 evaluated sessions.

---

## Endpoints the backend still needs to build
All of the above are proposals; none are confirmed implemented yet. Suggested order:
`/health` → `/api/mudras` → `/api/knowledge/retrieve` → `/api/tutor/explain` →
`/api/movements` → sessions + upload → evaluate + results → feedback → progress.
Until an endpoint exists, the frontend shows a clear "couldn't reach the server" or
"not found" state, or you can develop against `NEXT_PUBLIC_USE_MOCK_API=true`.
