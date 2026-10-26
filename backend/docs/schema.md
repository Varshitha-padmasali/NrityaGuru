# Database schema (Part 2)

```
sources 1 ──< mudras 1 ──< concept_mappings >── 1 movements >── 1 sources
   ^                              |
   └──────────────────────────────┘ (mapping also cites a source)
```

| Table | Purpose | Key columns |
|---|---|---|
| sources | Where information came from | id, source_name, source_url, source_type, access_date, license_or_usage_notes, reliability_notes |
| mudras | Hand gestures | id, name (unique), alternate_names (JSON), category, meaning, usage (JSON list), practice_instructions, reference_image_path, source_id (FK), verification_status |
| movements | Adavus / movements | id, name (unique), movement_category, practice_instructions, reference_media_path, source_id (FK), verification_status |
| concept_mappings | concept -> mudra and/or movement | id, concept (normalized), mudra_id (FK), movement_id (FK), interpretation_type, source_id (FK), evidence_notes, verification_status |

Rules enforced by the database: primary keys, foreign keys, unique names,
and a CHECK that every mapping has a mudra or a movement.

One concept can have MANY mapping rows, which is how several valid
interpretations are represented.

## Verification status
- `unverified` - no source; never authoritative
- `source_cited` - copied from a named source, not yet cross-checked
- `verified` - cross-checked against a primary text and/or a qualified teacher

Direct repository functions return `verified` records by default. Knowledge retrieval
explicitly includes `source_cited` rows so results can carry provenance and review labels;
set `include_unverified=True` only to additionally include records without sources.

## Not yet created (added in later parts)
reference_sequences (Part 7/9), practice_sessions, evaluation_results, feedback (Part 9).

---

# Part 9: sessions, evaluation results, feedback

```
practice_sessions 1 ──< 1 evaluation_results      (unique per session)
        │ └─────────< n feedback                  (history; newest row is "latest")
        ├── mudra_id  → mudras.id       } exactly one of the two (CHECK)
        └── movement_id → movements.id  }
```
| Table | Purpose | Key columns |
|---|---|---|
| practice_sessions | one practice attempt against one reference | id (= session_id), mudra_id / movement_id (FKs, exactly one), status, failure_reason, created_at |
| evaluation_results | the evaluation module's result | session_id (FK, UNIQUE, ON DELETE CASCADE), schema_version, is_mock, result_json (JSONB on PostgreSQL), created_at |
| feedback | feedback generated for a session | session_id (FK, ON DELETE CASCADE), mode, evidence_level, fallback_reason, model, is_mock, result_json, created_at; index (session_id, created_at) |
| reference_sequences | consented recorded feature sequence | target FK, schema/evaluator versions, finite frame matrix, provenance, reviewer identity/timestamp, review status, threshold |

**Why JSON for the two result documents?** Their schemas are versioned and always read whole. They are re-validated with
Pydantic on every read, so a corrupted or tampered row is rejected rather than trusted. The few fields queries need are real columns.

**Integrity checks on write:** the session must exist, and a result's reference must equal the session's reference.

## What is stored and why
| Data | Why | Not stored |
|---|---|---|
| session id, the practised mudra/movement | link results to a practice target | raw video, images, audio |
| the evaluation result (labels, confidence, DTW, deviations, landmark quality) | feedback must be reproducible and reusable | names, emails, device identifiers |
| generated feedback + its supporting evidence | show it again without calling Gemini; track improvement | learner free text typed into the tutor (not persisted at all) |
MOCK data is never stored. There is no automatic retention limit yet; `delete_session()` removes a session and, by cascade,
its evaluation and feedback (use it for deletion requests).

## Ownership (confirm with the team)
Created by Member 2 under the "avoid duplicates" rule, but **who writes `practice_sessions` and `evaluation_results` is not decided**:
the evaluation module (or whoever starts a session) should call `session_repository.create_session()` and
`save_evaluation_result()`. If a teammate already owns a sessions table, keep theirs and change the two foreign keys.

## Creating and upgrading the schema
Run `alembic upgrade head` from `backend/`. Revision 0001 adopts the existing SQLAlchemy schema
using non-destructive `create_all`; revision 0002 adds practice status and reference-sequence
storage to installations initialized before migrations. It preserves existing rows. The local
database was not migrated during this implementation pass.

Reference sequence intake requires `REFERENCE_REVIEW_TOKEN`. Teacher-verified records additionally
require the reviewer identity to match `REFERENCE_REVIEWER_IDENTITY`. Only verified rows are
discoverable; candidate rows remain review-only. No reference performance is currently stored.
