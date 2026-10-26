"""Predict a mudra label from ONE hand's 63 landmark values (pixel units).

Only load model files you trained yourself: joblib/pickle files can run code when loaded.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np

if __package__ and __package__.startswith("evaluation_module."):
    from .catalogue import canonical_record, catalogue_digest, dataset_mapping_digest
    from .features import FEATURE_SCHEMA_VERSION, FeatureError, hand_features
else:
    from mudra_mlp.catalogue import canonical_record, catalogue_digest, dataset_mapping_digest
    from mudra_mlp.features import FEATURE_SCHEMA_VERSION, FeatureError, hand_features


def load_bundle(path: Path | str, *, allow_non_catalogue: bool = False) -> dict:
    bundle = joblib.load(path)
    if not isinstance(bundle, dict) or "pipeline" not in bundle or "metadata" not in bundle:
        raise ValueError("not a valid mudra model bundle")
    if bundle["metadata"].get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        raise ValueError("model was trained with a different feature schema version")
    metadata = bundle["metadata"]
    pipeline_classes = [str(label) for label in bundle["pipeline"].classes_]
    if metadata.get("classes") != pipeline_classes:
        raise ValueError("model class metadata does not match the classifier class ordering")
    if metadata.get("strict_catalogue") is not True:
        if not allow_non_catalogue:
            raise ValueError("model labels are not bound to the canonical mudra catalogue")
    elif metadata.get("catalogue_digest") != catalogue_digest():
        raise ValueError("model was trained against a different mudra catalogue; retrain it before inference")
    elif metadata.get("dataset_mapping_digest") != dataset_mapping_digest():
        raise ValueError("model was trained against a different dataset-folder mapping; retrain it before inference")
    return bundle


def predict_hand(bundle: dict, coords, top_k: int = 3, *, expected_label: str | None = None) -> dict:
    try:
        x = hand_features(coords).reshape(1, -1)
    except FeatureError as exc:
        return {"status": "invalid_input", "message": str(exc)}
    pipe = bundle["pipeline"]
    classes = [str(label) for label in pipe.classes_]
    if expected_label is not None:
        record = canonical_record(expected_label) if bundle["metadata"].get("strict_catalogue") else None
        expected = record["name"] if record else expected_label
        if expected not in classes:
            return {"status": "class_unavailable", "requested_label": expected_label,
                    "available_labels": classes, "message": "This mudra is not supported by the loaded model."}
    proba = pipe.predict_proba(x)[0]
    order = np.argsort(proba)[::-1]
    confidence = float(proba[order[0]])
    threshold = float(bundle["metadata"].get("low_confidence_raw_score_threshold", 0.5))
    low_confidence = confidence < threshold
    return {
        "status": "low_confidence" if low_confidence else "success",
        "predicted_label": None if low_confidence else classes[order[0]],
        "candidate_label": classes[order[0]],
        "confidence": confidence,
        "top": [{"label": classes[i], "score": float(proba[i])} for i in order[:top_k]],
        "model_version": bundle["metadata"]["model_version"],
        "confidence_threshold": threshold,
        "note": "confidence is a raw model score, not a calibrated probability; low-confidence results do not return a mudra label",
    }
