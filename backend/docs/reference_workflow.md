# Reference performance recording and review

`reference_sequences` stores normalized hand-feature matrices only. It does not store video or
performer identity. The version 1 contract requires one target, `hand-v1` features (78 values per
frame for the current single-hand pipeline), normalization and evaluator versions, a source
description, and a consent-record reference.

## Prepare a candidate from a genuine recording

Use a real recording made with the performer’s consent. The command extracts a hand feature at up
to five frames per second and emits `review_status: candidate`; it cannot mark a record verified.
The source video is read locally and is not copied into the project or database.

```bash
python3.12 -m venv .venv-eval
source .venv-eval/bin/activate
python -m pip install -r evaluation_module/requirements.txt
python -m evaluation_module.data_prep.prepare_reference_sequence \
  --video /path/to/consented-recording.mp4 \
  --task /path/to/hand_landmarker.task \
  --mudra-id mudra_pataka \
  --reference-id pataka-teacher-001 \
  --source "consented teacher studio recording" \
  --consent-reference CONSENT-RECORD-001 \
  --out /path/to/pataka-candidate.json
```

Inspect the JSON and recording with a qualified Bharatanatyam teacher. Check the mudra mapping,
capture quality, feature schema, and sequence boundaries. A teacher with server-configured
reviewer credentials can submit the JSON to `POST /api/reference-sequences` with
`X-Reference-Review-Token`; the configured `REFERENCE_REVIEWER_IDENTITY` must match the review
metadata. Only `teacher_verified` rows appear in `GET /api/reference-sequences`.

The ingestion route rejects malformed frames and incompatible dimensions, records reviewer
identity/timestamp, prevents ID replacement, and stores only sequence features and provenance. The
project currently has no consented performance recordings or teacher approval. The native task
runtime failed its initialization smoke test on the current macOS setup, so candidate extraction
and the authenticated ingestion request are implemented but have not been verified end to end.
