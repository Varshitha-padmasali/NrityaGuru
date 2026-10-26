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
- Knowledge-base IDs are stable strings such as `mudra_pataka`; practice/session IDs use their API-defined types.
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

`GET /api/mudras?include_unverified=true&limit=100` → `200` — catalogue records
```json
[{ "id": "mudra_pataka", "name": "Pataka", "alternate_names": ["pathaka"], "category": "Asamyuta Hasta", "meaning": "Flag", "usage": [], "description": null, "practice_instructions": null, "reference_image_path": null, "dataset_image_count": 568, "dataset_images_available": true, "dataset_classes": [{ "dataset_folder": "Pathaka(1)", "original_label": "Pathaka", "variant_id": null, "image_count": 568, "mapping_status": "observed_transliteration_crosswalk; teacher_review_pending" }], "recognition_supported": false, "source": null, "verification_status": "source_cited", "verification_notes": null, "limitations": [] }]
```
- The endpoint returns up to 100 records by default (maximum 200); `q` searches names and aliases.
- `include_unverified=true` is needed to retrieve the full 52-entry catalogue and requires `ALLOW_UNVERIFIED_RECORDS=true` on the backend.
- `dataset_image_count` and `dataset_images_available` describe dataset coverage. `recognition_supported` refers to a compatible loaded model; all current records return `false`.
- `reference_image_path` is a backend-served reference image, not a Kaggle dataset path. It is `null` unless the asset exists.

`GET /api/mudras/{id-or-name}?include_unverified=true` returns the same catalogue record shape. IDs, canonical names, and unambiguous aliases are accepted.

## 3. Knowledge retrieval

`POST /api/knowledge/retrieve`
```json
{ "text": "Krishna is singing and dancing in the garden.", "include_unverified": true, "include_keyword_matches": false }
```

→ `200`
```json
{
  "original_text": "Krishna is singing and dancing in the garden.",
  "concepts": [
    {
      "concept": { "text": "garden" },
      "status": "unsupported",
      "references": []
    },
    { "concept": { "text": "krishna" }, "status": "unsupported", "references": [] }
  ],
  "supported_count": 0,
  "unsupported_count": 2
}
```
- References carry source IDs, verification status, match type, and limitations. Several references are alternatives.
- `include_unverified` is opt-in and requires the backend setting. Gemini receives only the records returned by this retrieval.
- An empty `concepts` array is valid.

## 4. AI tutor

`POST /api/tutor/explain`
```json
{ "text": "learner's text", "include_unverified": true, "include_keyword_matches": false }
```
→ `200`
```json
{ "original_text": "learner's text", "tutor": { "mode": "knowledge_only", "explanation": { "summary": "…", "concepts": [], "suggestions": [], "alternatives": [], "source_ids": [], "limitations": [] }, "model": null, "fallback_reason": "no_references", "notice": "…" }, "retrieval": { "concepts": [] }, "disclaimer": "…" }
```
- The backend performs retrieval, then grounds and validates Gemini against those retrieved records. The retrieval is always returned, including when the tutor falls back to knowledge-only mode.
- `include_unverified` is opt-in and requires the backend setting. The UI preserves source status and limitations.

## 5. Movements and practice references

`GET /api/movements` → `200` — knowledge-base `MovementOut[]`.

`GET /api/practice/references` → `200` — only references backed by a teacher-verified,
compatible sequence and a locally installed model/task with the runtime smoke-test gate enabled.
It currently returns `[]`; dataset image folders alone do not qualify as performance references.
```json
[{ "id": 101, "name": "Pataka (hold)", "reference_type": "mudra", "description": "…", "mudra_ids": [1], "image_url": "…", "max_duration_seconds": 5 }]
```
- The example above is a contract shape, not a current record.
- `reference_type`: `"mudra" | "sequence"`; `mudra_ids` is ordered for sequences.
- `max_duration_seconds` may be `null` (frontend default: 8 s).

## 6. Practice sessions

`POST /api/practice/sessions`
```json
{ "reference_id": "mudra_pataka" }
```
→ `201` — `PracticeSession`
```json
{ "session_id": "generated-session-id", "reference_id": "mudra_pataka", "status": "created", "created_at": "2026-10-24T14:30:00Z" }
```
`status`: `"created" | "uploaded" | "processing" | "evaluated" | "failed"`

`POST /api/practice/sessions/{session_id}/video` — `multipart/form-data`
| field | type | notes |
|---|---|---|
| `video` | file | `video/webm`, `video/mp4`, or QuickTime. Configurable max 100 MB, default 45 s, 1920x1080, 5 fps sampling, and 5000 decoded frames. |
| `reference_id` | string | must match the session's reference |

The backend bounds requests before multipart spooling, validates the container, decodes frames in
a temporary directory, and removes the clip after processing. It returns a structured `503` and
marks the attempt failed when the task/model assets or verified native runtime are unavailable.
`413` is returned for size, duration, resolution or frame-count limits; `422` for malformed or
empty video; `415` for unsupported content types. Requires installed backend requirements.

`POST /api/practice/sessions/{session_id}/evaluate` (empty JSON body `{}`) returns a stored
evaluation using the frontend response adapter, or a structured dependency/runtime error.
`GET /api/practice/sessions/{session_id}/results` returns the persisted result, or `null` while
unevaluated. The main integration is not currently available because required assets are absent.
```json
{ "session_id": 12, "status": "evaluated", "result": { …EvaluationResult… }, "error": null }
```

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
  "model_version": "0.2-prototype",
  "feature_schema": "hand-v1",
  "created_at": "2026-10-24T14:31:02Z"
}
```
- `predictions`: contiguous stretches of frames with the same MLP label; `confidence` is a raw,
  uncalibrated model score (0–1), **not** a probability or correctness score.
- `dtw`: `null` if no sequence comparison was run. `normalized` is optional and must be defined
  in backend docs (e.g. distance ÷ path length).
- `deviations[].kind` follows the backend evidence contract; it is not a human artistic-quality judgement.
- `fps` lets the UI show seconds instead of frame numbers (may be `null`).

## 7. Feedback

`POST /api/feedback/generate` with `{ "session_id": "..." }`
→ `200`
```json
{ "text": "Feedback paragraphs…", "model_name": "gemini-2.5-flash", "created_at": "…" }
```
- Generated **only** from the stored EvaluationResult + reference info.
- Idempotent: if feedback already exists, return it instead of calling Gemini again.
- `503` when Gemini is unavailable (results stay visible; user can retry).
- `409` if the session isn't evaluated yet.

## 8. Progress

`GET /api/progress` → `200` — development/test-only installation-wide history. Production returns
`503 user_auth_not_configured`; no user identity or private ownership system exists.
```json
{
  "scope": "shared_development",
  "sessions": [
    { "session_id": 12, "reference_id": 101, "reference_name": "Pataka (hold)", "status": "evaluated", "created_at": "…",
      "dtw_normalized": 0.21, "top_label": "Pataka", "top_confidence": 0.91, "feedback_summary": "First line of feedback or null" }
  ]
}
```
Trends are drawn only from `dtw_normalized` and only for references with ≥ 2 evaluated sessions.

---

## Current route implementation
Health, catalogue, movement knowledge, retrieval, tutor, feedback, practice-reference discovery,
session creation, bounded upload/frame decoding, result retrieval and progress routes are
implemented. Landmark inference and persistence of real evaluation output are wired but blocked
by missing model/task/reference assets and the unverified native runtime. The frontend shows the
no-reference state until those requirements are met and reports structured API failures.
