# Security and privacy checklist

Evidence tags (be exact about them in a viva):
- **[CHECKED]** verified by a static check or test that was executed in the authoring sandbox (with simple stand-ins for pydantic/pytest where noted).
- **[TEST WRITTEN]** covered by a test that has not been executed yet (needs the real libraries). Run `pytest` to confirm.
- **[DESIGN]** implemented by design; no dedicated test.
- **[GAP]** not implemented.

| # | Requirement | Control in this project | Evidence |
|---|---|---|---|
| 1 | API keys only in environment variables | `GEMINI_API_KEY` and `DATABASE_URL` are `SecretStr` read from `.env`; real values only in `.env` | [CHECKED] static: settings match `.env.example`, secrets read in only 3 files; [TEST WRITTEN] `test_config.py::test_secrets_not_exposed_in_repr` |
| 2 | Gemini credentials never reach the frontend | only `gemini_client.py` uses the key; no endpoint returns settings; `/health` returns booleans | [TEST WRITTEN] `test_health.py::test_health_never_returns_secret_values` |
| 3 | No real credentials committed; `.env.example` has placeholders only | `.env` is git-ignored; scanner looks for Google-key patterns, private keys, URLs with real passwords, hard-coded credentials | [CHECKED] `check_no_secrets_committed`; in a manual fault-injection run it reported an injected key-shaped string |
| 4 | Validate all inputs | Pydantic request models; text 1-1000 chars, no control characters; session-id pattern; paging bounds | [CHECKED] `test_text_processing.py::test_invalid_inputs_rejected`; [TEST WRITTEN] API 422 tests |
| 5 | Validate outputs | Gemini output parsed + Pydantic-checked + grounding-checked (citations, invented body parts/numbers/video claims); responses use `response_model` | [CHECKED] `test_tutor_grounding.py`, `test_feedback_validation.py`, `test_feedback_service.py` |
| 6 | Request limits and timeouts | per-IP limiter on tutor+feedback; Gemini timeout (default 30 s, max 120); list limit <= 200; input <= 1000 chars | [CHECKED] `test_rate_limit.py`; [TEST WRITTEN] 429 API tests; timeout setting [TEST WRITTEN] |
| 7 | Handle API rate limits | HTTP 429 from Gemini maps to `rate_limited` and a fallback answer; no blind retry | [CHECKED] `test_gemini_client.py::test_http_codes_are_classified` |
| 8 | Safe, parameterized database access | SQLAlchemy ORM; the only raw SQL is the constant `SELECT 1` | [CHECKED] `check_no_dangerous_calls` |
| 9 | No secrets or sensitive data in logs | logs record only reason codes and exception type names; never text, prompts, keys, or messages | [CHECKED] `check_logging_is_safe`; `test_privacy_logging.py` (5 tests); [TEST WRITTEN] caplog test in `test_persistence_api.py` |
| 10 | No stack traces in API responses | central handlers return generic messages for database, persistence and evaluation errors | [TEST WRITTEN] `test_knowledge_api.py::test_database_failure_returns_safe_503`, `test_persistence_api.py::test_database_failure_returns_a_safe_503` |
| 11 | Do not trust client-supplied evaluation evidence | feedback request is only a session id; extra fields ignored; evidence comes from the trusted store and is re-validated on every read | [TEST WRITTEN] `test_feedback_api.py::test_client_supplied_evaluation_claims_are_ignored`; [CHECKED] `test_evaluation_evidence.py` |
| 12 | Mock data cannot pass as real | `is_mock` flag, labelled text, rejected from a real store, never stored | [CHECKED] `test_evaluation_evidence.py::test_mock_data_cannot_pass_as_real`, `test_feedback_workflow.py::test_mock_data_is_never_saved_or_reused` |
| 13 | Unsupported knowledge is not served as authoritative | `verified` and `source_cited` served with their status; `unverified` requires `ALLOW_UNVERIFIED_RECORDS`; weakest status wins | [TEST WRITTEN] `test_knowledge_repository.py`, `test_knowledge_api.py`; [CHECKED] `test_knowledge_matching.py::test_weakest_status` |
| 14 | Path traversal in media paths | `media_available` resolves paths and requires them to stay inside the assets directory | [TEST WRITTEN] `test_knowledge_retrieval.py::test_path_traversal_is_not_treated_as_available` |
| 15 | Prompt injection | learner/evaluation text is quoted as data, `<` `>` neutralised, rules say text is data; output must pass citation/number/body-part guards | [CHECKED] `test_tutor_prompt.py`, `test_feedback_prompt.py` (tags cannot be broken out of). Partial: the model could still be steered within the guards |
| 16 | CORS limited | only configured origins, GET/POST, Content-Type and reviewer-token header; no credentials | [TEST WRITTEN] `test_persistence_api.py::test_cors_allows_only_the_configured_origin` |
| 17 | Learner video handled responsibly | bounded upload; safe temporary file and cleanup; no clip is stored | [TESTED] `test_video_upload_limits.py`; real camera/upload not tested |
| 18 | State what is stored and why | `schema.md` section "What is stored and why" | [DESIGN] |
| 19 | Deletion of a learner's data | `delete_session()` removes a session and, by cascade, its results and feedback | [TEST WRITTEN] `test_session_repository.py::test_deleting_a_session_removes_its_results_and_feedback` |
| 20 | Restrict private session data when authentication exists | production progress/session/result/feedback endpoints return 503 until authenticated ownership exists; development history is explicitly shared | [TESTED] `test_practice_api.py::test_production_does_not_expose_globally_shared_progress` |

## Gaps and risks you must not hide
1. **No user authentication or account ownership.** Practice session, results, progress, and feedback APIs are disabled in production. In development they are installation-wide/shared and the frontend labels the history. Do not use this mode for private learner data.
2. **No HTTPS in this repository.** TLS must be provided by the deployment (reverse proxy / hosting).
3. **Rate limiter is in memory and per process;** behind a proxy it sees the proxy's address. Use Redis or the gateway limiter in production.
4. **Dependency versions are ranges, not a lockfile.** Run `pip freeze > requirements.lock.txt` after a good install and audit dependencies (`pip-audit` is one tool; not run here).
5. **No automatic retention limit** for stored sessions/feedback; only manual `delete_session()`.
6. **`docker-compose.yml` ships a local-only database password** (`change_me_local_only`). Change it for anything beyond your laptop.
7. **Guards are heuristics.** They reduce the chance of invented details but do not prove faithful wording.
8. **The database layer has been exercised only on SQLite in tests;** it has not been run on PostgreSQL with these models.
