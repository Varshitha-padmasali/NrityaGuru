# Implementation status, evidence, limitations and final summary

Date of this update: 26 October 2026. The catalogue now includes the 52 names/categories from the referenced NCERT teaching list. This is not evidence that the Kaggle image dataset contains all 52 classes or that a model recognizes them.

## Evidence levels (what "tested" means here)
| Tag | Meaning |
|---|---|
| EXECUTED | run in the authoring sandbox. That sandbox could not install the real `pytest`, `pydantic`, `sqlalchemy`, `fastapi`, so these tests ran against small stand-ins that do **not** enforce Pydantic constraints/validators. They prove the logic, not that it passes on the real stack |
| STATIC | checked by `python -m scripts.static_checks` (imports, cycles, signatures, secrets, logging, settings, routes); executed, and shown to fail on deliberately injected faults |
| WRITTEN | the test exists but has not been run anywhere yet: run `pytest` on a normal machine |
| NONE | nothing verifies it |

## Feature checklist
| Part | Feature | Implemented | Evidence |
|---|---|---|---|
| 1 | FastAPI app, typed settings, safe logging, health | yes | WRITTEN (`test_config`, `test_health`) |
| 2 | PostgreSQL schema (sources, mudras, movements, concept_mappings), repositories, validated idempotent seed | yes | WRITTEN (`test_knowledge_repository`, `test_seed`); seed JSON cross-checked by script |
| 3 | Concept extraction (tokenizer with offsets, rules, lookup keys) | yes | EXECUTED (`test_text_processing`, `test_concept_extraction`); resolution WRITTEN |
| 4 | Retrieval, ranking, limitations, knowledge endpoints | yes | EXECUTED (`test_knowledge_matching`); retrieval + API WRITTEN |
| 5 | Gemini client, grounded tutor, fallback, error classification | yes | EXECUTED (`test_tutor_prompt/grounding/service`, `test_gemini_client`); SDK + live WRITTEN; **never run against the real Gemini API** |
| 6 | RAG pipeline, `/api/tutor/explain`, rate limiter, evaluation harness + 11 labelled cases | yes | EXECUTED (`test_rag_pipeline`, `test_rate_limit`, `test_rag_evaluation_checks`); API + regression set WRITTEN |
| 7 | Evaluation contract v1.0, validation, assessment, mock store, reference lookup | yes | EXECUTED (`test_evaluation_assessment`, `test_evaluation_evidence`); schema validators + lookup WRITTEN |
| 8 | Evidence items, grounded feedback, guards, evidence-only fallback, `/api/feedback/generate` | yes | EXECUTED (`test_feedback_evidence/prompt/validation/service`); API + schema WRITTEN |
| 9 | Sessions/results/feedback tables, workflow (reuse, fingerprint), GET feedback, CORS, readiness | yes | EXECUTED (`test_feedback_workflow`, `test_privacy_logging`); repositories, integration flows, API WRITTEN |
| 10 | Static checks (11), documentation, security checklist, viva notes | yes | EXECUTED + STATIC |

## Test numbers (counted from the source files)
| | Count |
|---|---|
| test functions including parametrized cases | 477 |
| of which EXECUTED in the sandbox (stand-ins) | 270, all passing |
| WRITTEN, not yet executed | 207 |
| expected on a normal machine, default run | 476 selected (the live test is deselected): 469 pass + 1 module skipped if `google-genai` is missing |

If a WRITTEN test fails when you run it, that is a real finding, not a surprise to be hidden: send me the output.

## Failure scenarios and the tests that cover them
Format `file::test`. These names are checked against the test files by a script.

| Scenario | Tests |
|---|---|
| no supported mapping: nothing invented, Gemini not called | `test_rag_pipeline.py::test_missing_mapping_means_no_gemini_call_and_no_invented_claim`; `test_knowledge_retrieval.py::test_unsupported_concept_gets_honest_note` |
| missing image file | `test_knowledge_retrieval.py::test_missing_image_file_is_dropped_and_flagged` |
| missing instructions / unreliable or empty evidence | `test_evaluation_assessment.py::test_missing_instructions_and_unverified_reference_are_reported`; `test_evaluation_assessment.py::test_nothing_usable_is_insufficient`; `test_feedback_service.py::test_insufficient_evidence_does_not_present_findings_built_on_unreliable_data` |
| invalid text / session id | `test_text_processing.py::test_invalid_inputs_rejected`; `test_evaluation_evidence.py::test_bad_session_ids_are_rejected_before_any_lookup`; `test_persistence_api.py::test_malformed_ids_return_422` |
| malformed evaluation payload | `test_evaluation_schema_pydantic.py::test_malformed_payloads_are_rejected` |
| Gemini timeout / rate limit / unavailable / empty | `test_tutor_service.py::test_gemini_failures_fall_back_to_knowledge`; `test_feedback_service.py::test_gemini_failures_return_evidence_only`; `test_gemini_client.py::test_http_codes_are_classified` |
| Gemini malformed output | `test_tutor_service.py::test_malformed_json_falls_back`; `test_feedback_service.py::test_malformed_output_is_discarded` |
| Gemini fabricated citation | `test_tutor_service.py::test_fabricated_source_id_falls_back`; `test_feedback_service.py::test_fabricated_evidence_id_is_discarded` |
| Gemini invented body part / number / video claim | `test_feedback_service.py::test_invented_details_are_discarded`; `test_feedback_validation.py::test_number_not_in_evidence_is_rejected` |
| Gemini not configured | `test_tutor_service.py::test_not_configured_returns_knowledge_only`; `test_feedback_service.py::test_not_configured_returns_evidence_only` |
| database not configured / failing | `test_knowledge_api.py::test_database_not_configured_returns_503`; `test_persistence_api.py::test_database_failure_returns_a_safe_503`; `test_tutor_api.py::test_database_down_returns_safe_503` |
| saving / reading stored feedback fails | `test_feedback_workflow.py::test_save_failure_still_returns_the_feedback`; `test_feedback_workflow.py::test_read_failure_falls_back_to_generating`; `test_persistence_api.py::test_save_failure_still_returns_feedback` |
| corrupt stored data | `test_feedback_repository.py::test_a_corrupt_stored_row_is_ignored_not_trusted`; `test_integration_flows.py::test_corrupt_evaluation_row_is_rejected` |
| secrets / learner text in logs | `test_privacy_logging.py::test_tutor_gemini_failure_does_not_log_text_or_error_message`; `test_privacy_logging.py::test_feedback_failures_do_not_log_evidence_or_error_text` |
| stored feedback never stale | `test_feedback_workflow.py::test_changed_evaluation_result_is_not_served_stale_feedback`; `test_feedback_workflow.py::test_changed_reference_record_is_not_served_stale_feedback` |
| end-to-end: knowledge -> tutor | `test_rag_pipeline.py::test_full_flow_returns_ai_answer_and_retrieval`; `test_integration_flows.py::test_knowledge_to_tutor_flow_cites_only_real_database_ids` |
| end-to-end: evaluation -> feedback | `test_feedback_workflow.py::test_first_run_generates_and_saves`; `test_integration_flows.py::test_evaluation_to_feedback_flow_with_storage_and_reuse` |

## Problems found and fixed during Part 10
| Finding | How it was found | Fix |
|---|---|---|
| `tests/test_feedback_api.py` (15 tests) overrode `get_evidence_service` and `get_feedback_service`, which no route uses after Part 9, so the tests would have run against the real workflow and failed | careful review, then confirmed by a script | tests now override `get_feedback_workflow`; new static check `tests only override dependencies that some route really uses` flags this class of mistake |
| the first version of my static checker crashed (it tried to write compiled output to `/dev/null`) | first run | uses the built-in `compile()` |
| earlier message said a missing SDK gives "7 skipped"; pytest reports the whole module as 1 skipped | recounting | corrected here and in the README |
| a doc sentence about capitalised words was confusing | review | reworded in `concept_extraction.md` |
Static-check validation: faults deliberately injected into a throwaway copy (bad import name, a genuine import cycle, undocumented setting, key-shaped string, logging an exception/prompt, `print`, SQL built from a string, misspelled/missing/extra arguments, stale override) were all reported.

## Known limitations and unverified functionality
**Knowledge base:** 52 source-cited names/categories: 28 Asamyuta and 24 Samyuta entries. Existing Pataka, Tripataka, and Ardhapataka meanings/usages and six concept mappings remain tied to their original secondary source. The other 49 have no invented meanings, usages, descriptions, instructions, or images. No record is teacher-verified; all remain hidden by default. The Kaggle dataset is absent and its license/class structure are unverified. See `mudra_catalogue.md`.
**Gemini:** never called for real in this work; the SDK usage follows Google's docs but is unexecuted; the model id may change (default `gemini-3.8-flash`); guards are heuristics (English only, can reject harmless text); wording faithfulness is not measured (a human review sheet exists, unfilled); no automatic retry.
**Evaluation integration:** the backend reads trusted stored results and retains the existing feedback guards. The adjacent evaluator trains a single-hand MLP with a 78-feature hand representation and DTW; training is now bound to canonical Asamyuta labels and excludes Samyuta classes. No model bundle or reference sequences are present, and there is no complete capture-to-database runtime service in this checkout. Historical 12-class metrics are not 52-class results.
**Infrastructure and security:** see `security_checklist.md` (no auth, no TLS, in-memory limiter, no lockfile, no retention policy). `create_all` instead of migrations; the reference-sequence table does not exist yet; PostgreSQL itself has not been exercised with these models (tests use SQLite).
**Testing:** the test counts above describe the previous backend-only audit and do not include the catalogue and dataset-manifest changes. Re-run the backend, evaluation, and frontend suites before relying on them. No dataset-dependent, PostgreSQL, Gemini-live, or full browser workflow was verified as part of the catalogue update.

## Not started / pending
Kaggle download, class-count/label/license verification, image manifest generation on the real data, teacher verification, practice instructions and reference images, Samyuta/two-hand MLP support, full capture-to-database orchestration, authentication, production deployment (TLS, backend container, secrets management), human faithfulness review, dependency lockfile, migrations.

## Final summary: what is genuinely implemented and tested
- **Implemented:** the full Member 2 backend described above: knowledge base and retrieval with provenance and verification status, a Gemini-based tutor and feedback generator that are grounded, validated and always fall back safely, an evaluation-evidence contract with a trusted store, persistence of sessions/results/feedback, and nine documented endpoints.
- **Tested for real (executed, stand-ins):** the logic of extraction, matching, prompts, grounding and invented-detail guards, Gemini error handling with a fake generator, the tutor and feedback services and the reuse/persistence workflow with fakes, evidence assessment, the rate limiter, privacy of logs, plus 11 static checks.
- **Written but not yet proven:** everything that needs the real libraries: the database layer, the HTTP endpoints, the strict Pydantic constraints, the SDK wrapper, and all live behaviour.
- **Not claimed:** accuracy of any kind, correctness of the Bharatanatyam content, correctness of the MLP/DTW pipeline, or that the whole NrityaGuru application is finished. This module is complete as a prototype, pending your test run on a normal machine.

## Reproduce this status yourself
```bash
cd backend && source .venv/bin/activate
python -m scripts.static_checks     # expect: All static checks passed.
pytest -q                           # expect: 476 selected; see the numbers above
```
