# Evaluation contract v1.0 (Member 2 <-> evaluation module)

Code: `app/schemas/evaluation.py` (schema), `app/services/evaluation_evidence.py` (validation),
`app/services/evaluation_assessment.py` (what the evidence supports), `app/integrations/evaluation_stub.py` (store + MOCK).
After you install the dependencies, `python -m scripts.export_contract_schema` writes a JSON Schema
file (`docs/evaluation_result.schema.json`) you can give the evaluation teammate.

## Trust model
- The evaluation module produces an `EvaluationResult`. Member 2 only reads it and never invents any field.
- Results are fetched **by session id from a trusted store**. There is deliberately NO endpoint that accepts
  evaluation results from the browser, so nobody can fake evidence.
- Mock data (`is_mock: true`) is only served when `USE_MOCK_EVALUATION=true` (development) and can never pass as real.

## Example (generated from the MOCK scenario `mock-session-deviation`; all values are test data)
```json
{
  "schema_version": "1.0",
  "session_id": "mock-session-deviation",
  "reference_movement_id": null,
  "reference_mudra_id": "mudra_pataka",
  "expected_labels": [
    "pataka"
  ],
  "predicted_labels": [
    {
      "label": "pataka",
      "confidence": 0.71,
      "interval": null
    }
  ],
  "dtw": {
    "distance": 12.5,
    "normalized_distance": 0.42,
    "threshold": 0.3,
    "within_threshold": false,
    "reference_sequence_id": "MOCK-SEQ-001",
    "feature_schema_version": "MOCK-1"
  },
  "deviations": [
    {
      "deviation_id": "MOCK-D1",
      "kind": "finger",
      "body_part": "index_finger",
      "description": "MOCK: index finger angle differs from the reference.",
      "measured_value": 28.0,
      "reference_value": 5.0,
      "unit": "degrees",
      "severity": "moderate",
      "interval": {
        "start_frame": 10,
        "end_frame": 40,
        "start_time_s": null,
        "end_time_s": null
      },
      "source_module": "landmark_rules"
    }
  ],
  "landmark_quality": {
    "hand_detection_rate": 0.97,
    "pose_detection_rate": 0.95,
    "frames_total": 90,
    "frames_analysed": 88,
    "reliable": true,
    "notes": []
  },
  "warnings": [
    "MOCK DATA: not produced by a real evaluation."
  ],
  "mlp_model_version": null,
  "created_at": null,
  "is_mock": true
}
```

## Fields
| Field | Required | Meaning / how Member 2 uses it |
|---|---|---|
| schema_version | yes | "major.minor". Major must be 1; other majors are rejected |
| session_id | yes | 3-64 chars: letters, digits, `_`, `-` (must not start with `_`/`-`) |
| reference_mudra_id / reference_movement_id | exactly one | id of the practised record in our database (e.g. `mudra_pataka`) |
| expected_labels | no | labels the classifier should output for this reference |
| predicted_labels[] | no | `label` (letters/digits/space/`_.:+-`), `confidence` 0-1 (optional), `interval` (optional) |
| dtw | no | `distance`, optional `normalized_distance`, `threshold`, `within_threshold`, `reference_sequence_id`, `feature_schema_version`. We never compute the verdict ourselves |
| deviations[] | no | differences the evaluation module detected: `deviation_id`, `kind`, `description`, optional `body_part`, `measured_value`, `reference_value`, `unit`, `severity`, `interval`, `source_module` |
| landmark_quality | no | `hand_detection_rate`, `pose_detection_rate` (0-1), `frames_total`, `frames_analysed`, **`reliable`** (preferred), `notes` |
| warnings[] | no | passed to the feedback as limitations |
| mlp_model_version, created_at | no | metadata |
| is_mock | no | true only for test data |

`interval` = `start_frame`, `end_frame` (end >= start), optional `start_time_s`, `end_time_s`.
Unknown extra fields are ignored. Limits: 100 predictions, 50 deviations, 20 warnings.

## What Member 2 concludes from the evidence (and what it refuses to)
- **Label match**: the highest-confidence prediction vs `expected_labels` (case-insensitive) -> match / mismatch / unknown.
- **Specific error**: only deviations that name a `body_part` or give a `measured_value` count as specific. If there is a
  mismatch but no specific deviation, the feedback must say the cause cannot be stated.
- **DTW**: always described as alignment cost, never as "what is wrong".
- **Low confidence** (< 0.5), **unreliable landmarks**, missing DTW / labels / instructions, unverified reference: each becomes a limitation.
- **Evidence level**: `insufficient` (landmarks unreliable, or no predictions + no DTW + no deviations) /
  `sufficient` (reliable landmarks + label comparison + DTW + not low confidence) / otherwise `limited`.
- The 0.5 cut-offs (confidence; and detection rate when `reliable` is absent) are conservative defaults chosen by Member 2,
  not calibrated values. Agree final numbers with the evaluation member.

## Rejections (stable codes; Part 8 will return these as HTTP errors)
| Code | When | Suggested HTTP |
|---|---|---|
| invalid_session_id | bad format | 422 |
| session_not_found | nothing stored | 404 |
| session_mismatch | store returned another session | 502/500 |
| malformed_result | fails the schema (message lists field NAMES only, never values) | 422 |
| unsupported_version | major != 1 | 422 |
| unknown_reference | mudra/movement missing OR not available (same message for both) | 422 |
| mock_data_in_real_store | `is_mock` true from a real store | 500 |
| store_unavailable | evaluation integration not configured/reachable | 503 |

## How the evaluation module delivers results (to be agreed)
Proposed: the evaluation module writes one `EvaluationResult` (as JSON) per session into a shared PostgreSQL table;
Part 9 adds the table and a store that reads it by `session_id`. Alternative: an authenticated service-to-service call
(needs a shared secret; not built). Not decided with the teammate yet.

## Questions to confirm with the evaluation teammate (copy/paste)
1. Do your labels (MLP class names) match our naming? Which string does the classifier output for Pataka (`pataka`? `Pataka`?)
2. Is the practised target a mudra (static pose), a movement (adavu), or both? Which ids will you send?
3. Can you supply `confidence` per prediction, and is it a calibrated probability or a raw score?
4. Do you decide DTW pass/fail (`within_threshold`) and give us the `threshold`? Is `distance` normalised?
5. Can you detect specific deviations (which finger/joint, measured vs reference value)? If not, leave `deviations` empty.
6. Will you set `landmark_quality.reliable` yourselves? What detection rate do you consider unreliable?
7. Do you report frame numbers, seconds, or both?
8. How do you deliver results: write to a shared table, or call our API? What identifies a session?
9. Do you store the reference sequence metadata (`reference_sequence_id`, `feature_schema_version`)? Which table?
10. Versioning: you bump `schema_version` minor for added optional fields and major for breaking changes.

## Note about the knowledge base
The seed mudras have no `practice_instructions` yet, so every assessment currently says "No verified practice
instructions are available". Add verified instructions (with your teacher) for feedback to be tied to a reference.
