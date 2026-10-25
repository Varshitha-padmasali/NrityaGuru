# Gemini integration and AI tutor service (Part 5)

## What was verified (official Google docs, read on 24 Oct 2026)
| Topic | Finding | Source |
|---|---|---|
| Recommended model for new projects | `gemini-3.8-flash` (GA 2 Sep 2026); `gemini-3.5-flash-lite` is the cheaper option | Release notes, https://ai.google.dev/gemini-api/docs/changelog |
| `gemini-2.5-flash` | Not deprecated, but since 18 Sep 2026 access is limited to users who already used it; new projects are told to use newer models | same page; deprecations page: https://ai.google.dev/gemini-api/docs/deprecations |
| Sampling parameters | `temperature`, `top_p`, `top_k` are deprecated and ignored: we do not send them | https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.8 |
| Thinking | `thinking_level` LOW / MEDIUM (default) / HIGH. MINIMAL returns an error on 3.8 Flash | same page |
| SDK | `google-genai`; `client.models.generate_content(...)` with `GenerateContentConfig(system_instruction, response_mime_type="application/json")` | Google Gen AI SDK docs/source |
| Errors | `google.genai.errors.APIError` (`.code`, `.status`), `ClientError` 4xx, `ServerError` 5xx | SDK source |

**Not verified:** Google's newest docs lead with a newer "Interactions API" (`client.interactions.create`).
We use `generate_content`, which Google's release notes still list as supported. The exact free-tier
quota for `gemini-3.8-flash` could not be confirmed (3.8 Flash has an introductory paid price until 31 Dec 2026).
Nothing here has been run against the real API (no key or network in the authoring environment).

## Flow
retrieved knowledge -> (no references? skip Gemini) -> prompt -> Gemini -> parse JSON -> Pydantic shape check
-> grounding check -> `TutorResult(mode="ai")`. Any failure -> `TutorResult(mode="knowledge_only")`.

## Files
- `services/gemini_client.py` - the only module that calls Gemini; maps all failures to safe errors
- `services/tutor_prompt.py` - builds the prompt (pure); caps size; neutralises `<` `>` in learner text
- `services/tutor_validation.py` - JSON parsing + grounding checks
- `services/tutor_fallback.py` - deterministic knowledge-only output (no AI text)
- `services/tutor_service.py` - orchestration
- `schemas/tutor.py` - `TutorExplanation` (what Gemini must return), `TutorResult`

## Grounding checks (what is and is not guaranteed)
Guaranteed: no cited id that was not retrieved; no citing another concept's records; no "supported" claim
for a concept with no retrieved reference; every supported concept has a citation; unknown concepts rejected.
NOT guaranteed: that the wording is faithful. That needs human review (Part 6 evaluation).

## Failure -> fallback reason
| Situation | fallback_reason |
|---|---|
| nothing retrieved (Gemini not called) | no_references |
| no key / SDK missing | not_configured |
| 408 / 504 / timeout | timeout |
| 429 | rate_limited |
| 5xx / network | unavailable |
| 401 / 403 / 404 (bad key or model id) | auth_or_model_error |
| other 4xx | request_error |
| blank reply | empty_response |
| not JSON / wrong shape | malformed_output |
| fabricated or misplaced id | invalid_citation |
| unsupported claim | ungrounded_output |

No automatic retry (it costs quota and time; the fallback is useful). Upstream error text is never kept or logged.

## Citation ids
Allowed ids are the retrieved `record_id`s plus the `source.id` / `mapping_source.id` of those records.

## Try it for real
    pip install -r requirements.txt
    python -m scripts.smoke_gemini     # checks key + model id + SDK with one tiny prompt
    pytest -m live                     # optional live test (sends only mock test data)
