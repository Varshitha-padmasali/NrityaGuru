# Knowledge API (Part 4)

Base URL (dev): http://127.0.0.1:8000  -  interactive docs at /docs

| Method | Path | Purpose |
|---|---|---|
| POST | /api/knowledge/retrieve | text -> concepts -> supported references |
| GET | /api/mudras | list mudras (filter: category; paging: limit 1-200, offset >= 0) |
| GET | /api/mudras/{mudra_id} | one mudra |
| GET | /api/movements | list movements (currently empty: none verified yet) |

## Source-cited and verified records by default
Endpoints return `verified` and `source_cited` records by default. Source-cited results
include their source and verification status; they are not represented as teacher-verified.
`include_unverified=true` additionally exposes records without supporting sources, and is
allowed only when the server has `ALLOW_UNVERIFIED_RECORDS=true`. Otherwise the answer is **403**.

## POST /api/knowledge/retrieve
Request:
```json
{ "text": "Krishna is singing and dancing in the garden.",
  "include_unverified": false,
  "include_keyword_matches": false }
```
- `text`: 1-1000 characters.
- `include_keyword_matches`: also match a single word inside a listed usage (weak; labelled).

Response shape (per concept): `concept`, `status` (supported/unsupported), `references[]`,
`contains_unverified`, `note`. Each reference has: `record_type`, `record_id` (stable citation id),
`name`, `category`, `meaning`, `usage`, `practice_instructions`, `reference_media_path`,
`match_type`, `mapping_ids`, `relationships`, `evidence_notes`, `verification_status`
(weakest of record and mapping), `source`, `mapping_source`, `limitations[]`.
Top level also has `supported_count`, `unsupported_count`, `warnings`, `disclaimer`.

match_type, strongest first: concept_mapping, exact_name, alternate_name, usage_listed, usage_keyword.

## Status codes
| Code | Meaning |
|---|---|
| 200 | OK (also when nothing matched: concepts are marked `unsupported`) |
| 403 | unverified records requested but disabled on this server |
| 404 | mudra not found (same answer for "unverified": no information leak) |
| 422 | invalid input (empty, too long, no letters, bad paging) |
| 503 | database not configured or unavailable (message is generic, no internals) |

Error body: `{"detail": "..."}`. Validation errors from FastAPI use a list in `detail`.

## Example requests
```bash
curl -s -X POST http://127.0.0.1:8000/api/knowledge/retrieve \
  -H "Content-Type: application/json" \
  -d '{"text":"The river and the clouds","include_unverified":true}'

curl -s "http://127.0.0.1:8000/api/mudras?include_unverified=true"
curl -s "http://127.0.0.1:8000/api/mudras/mudra_pataka?include_unverified=true"
```
With the current seed data, the first call should return `river` and `cloud` mapped to
`mudra_pataka` with status `source_cited`. Run it yourself to see the exact JSON.
