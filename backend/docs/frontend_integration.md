# Frontend integration guide (Member 2 backend)

Base URL (dev): `http://127.0.0.1:8000`. Interactive docs: `/docs`. Machine-readable contract: `/openapi.json`
(for TypeScript types you can generate from it, for example with the `openapi-typescript` tool; not verified here).
CORS: the browser origin must be listed in `CORS_ALLOW_ORIGINS` (default `http://localhost:3000`). No cookies or login are used yet.

## The learning loop and the calls behind it
| Step | Call | Notes |
|---|---|---|
| 1. learner types a sentence/lyrics | `POST /api/tutor/explain` | returns the AI explanation AND the retrieved records |
| (optional) browse references | `GET /api/mudras`, `GET /api/mudras/{id}`, `GET /api/movements` | source-cited and verified by default; unsupported rows require server opt-in |
| 2. learner practises on camera | not this backend | camera, MediaPipe, MLP, DTW belong to the evaluation module, which stores a result for a session id |
| 3. show feedback | `POST /api/feedback/generate` `{"session_id": "..."}` | reuses stored feedback unless `"regenerate": true` |
| 4. show it again later / progress | `GET /api/feedback/{session_id}` | no generation, no cost; 404 if none yet |
| health | `GET /health`, `GET /health/ready` | ready = database reachable |

Never send evaluation results from the browser: the feedback endpoint accepts only a session id and ignores anything else.

## Endpoints
### POST /api/tutor/explain
Request: `{ "text": string (1-1000), "include_unverified"?: boolean, "include_keyword_matches"?: boolean }`
Response: `{ original_text, tutor, retrieval, disclaimer }`
- `tutor.mode`: `"ai"` or `"knowledge_only"`; if `knowledge_only`, `tutor.fallback_reason` says why and `tutor.notice` is a sentence you can show.
- `tutor.explanation`: `summary`, `concepts[] {concept, supported, explanation, source_ids}`, `suggestions`, `alternatives`, `source_ids`, `limitations`.
- `retrieval.concepts[]`: each has `status` ("supported"/"unsupported"), `references[]` (name, meaning, usage, `verification_status`, `source`, `reference_media_path`, `limitations`) and `note`.
UI rules: always show `verification_status` and `limitations`; show several `references` as alternatives; never present an `unsupported` concept as having a mudra.

### POST /api/feedback/generate
Request: `{ "session_id": string, "regenerate"?: boolean }`
Response: `{ mode, session_id, reference, evidence_level, is_mock, feedback, supporting_evidence, model, fallback_reason, notice, saved, reused, disclaimer }`
- `mode`: `"ai"` or `"evidence_only"` (findings without AI wording). Show `notice` when it is `evidence_only`.
- `feedback`: `overall_summary`, `observations[] {text, evidence_ids}`, `suggestions[] {text, evidence_ids}`, `limitations[]`.
- `supporting_evidence[]`: `{evidence_id, kind, statement}`; observations cite these ids. Use them for "why am I seeing this?".
- `evidence_level`: `sufficient` | `limited` | `insufficient`. Show a cautious style for `limited` and no corrective claims for `insufficient`.
- `is_mock: true` means TEST DATA: display a clear "test data" banner.
- Always show `limitations` and `disclaimer` (it states that no AI watched the video).

### GET /api/feedback/{session_id}
Same response shape, `reused: true`. 404 `{"detail": "..."}` if no feedback has been stored.

## Errors
Shape: `{"detail": string}` and, for evaluation problems, `"code"`. Validation errors from FastAPI use a LIST in `detail`.
| Status | Meaning | Frontend behaviour |
|---|---|---|
| 200 | OK (also when Gemini failed: check `mode`) | render normally |
| 403 | unverified records requested but disabled | do not retry |
| 404 | no such session / no stored feedback / mudra not found | show "not available yet" |
| 422 | invalid input or unusable evaluation (`code`: invalid_session_id, malformed_result, unsupported_version, unknown_reference) | fix input / report |
| 429 | rate limit; header `Retry-After` (seconds) | wait, then retry |
| 502/500 | server-side inconsistency (`session_mismatch`, `mock_data_in_real_store`) | show generic error |
| 503 | database or evaluation store unavailable (`store_unavailable`) | "try again shortly" |

## fallback_reason values
`no_references`, `not_configured`, `timeout`, `rate_limited`, `unavailable`, `auth_or_model_error`, `request_error`, `empty_response`,
`malformed_output`, `invalid_citation`, `ungrounded_output`, `insufficient_evidence`. The UI only needs `mode` and `notice`; the reason is for support/debugging.

## Privacy notes for the UI
The backend never receives video. Do not send images or video to it. Session ids must be unguessable (UUID4) until login exists, because
anyone who knows a session id can read its feedback.
