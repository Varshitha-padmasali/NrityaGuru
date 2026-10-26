"""Validation and loading for provenance-bearing DTW reference sequences.

Reference files contain normalized feature vectors, not video or raw landmarks.
They must be reviewed genuine performances and match the learner feature schema.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


SCHEMA_VERSION = 1


class ReferenceSequenceError(ValueError):
    """A reference file is malformed or incompatible with the evaluator."""


def validate_reference(
    payload: Any,
    *,
    expected_feature_schema: str | None = None,
    expected_evaluator_version: str | None = None,
    expected_dimensions: int | None = None,
) -> dict:
    if not isinstance(payload, dict):
        raise ReferenceSequenceError("reference must be a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ReferenceSequenceError(f"schema_version must be {SCHEMA_VERSION}")
    required_text = ("id", "mudra_id", "feature_schema", "evaluator_version", "normalization", "review_status")
    for key in required_text:
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            raise ReferenceSequenceError(f"{key} must be a non-empty string")
    if payload["review_status"] != "teacher_verified":
        raise ReferenceSequenceError("only teacher_verified sequences can be used as references")
    if expected_feature_schema and payload["feature_schema"] != expected_feature_schema:
        raise ReferenceSequenceError("feature_schema does not match the evaluator")
    if expected_evaluator_version and payload["evaluator_version"] != expected_evaluator_version:
        raise ReferenceSequenceError("evaluator_version does not match the evaluator")
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict) or not all(
        isinstance(provenance.get(k), str) and provenance[k].strip()
        for k in ("source", "performer_consent", "reviewer", "review_date")
    ):
        raise ReferenceSequenceError("provenance requires source, performer_consent, reviewer, and review_date")
    try:
        sequence = np.asarray(payload.get("frames"), dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ReferenceSequenceError("frames must be a numeric matrix") from exc
    if sequence.ndim != 2 or min(sequence.shape, default=0) == 0:
        raise ReferenceSequenceError("frames must be a non-empty 2-D matrix")
    if sequence.shape[0] > 600 or sequence.shape[1] > 256:
        raise ReferenceSequenceError("frames exceed the version 1 limits")
    if not np.isfinite(sequence).all():
        raise ReferenceSequenceError("frames contain NaN or infinite values")
    declared_dimensions = payload.get("feature_dimensions")
    if isinstance(declared_dimensions, bool) or declared_dimensions != sequence.shape[1]:
        raise ReferenceSequenceError("feature_dimensions does not match frames")
    if expected_dimensions is not None and sequence.shape[1] != expected_dimensions:
        raise ReferenceSequenceError("feature dimensions do not match the evaluator")
    # Return a detached JSON-compatible representation after numeric validation.
    normalized = dict(payload)
    normalized["frames"] = sequence.tolist()
    return normalized


def load_reference(
    path: str | Path,
    *,
    expected_feature_schema: str | None = None,
    expected_evaluator_version: str | None = None,
    expected_dimensions: int | None = None,
) -> dict:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReferenceSequenceError(f"cannot read reference file: {exc}") from exc
    return validate_reference(
        payload,
        expected_feature_schema=expected_feature_schema,
        expected_evaluator_version=expected_evaluator_version,
        expected_dimensions=expected_dimensions,
    )
