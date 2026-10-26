"""Predict a mudra label from ONE hand's 63 landmark values (pixel units).

Only load model files you trained yourself: joblib/pickle files can run code when loaded.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np

if __package__ and __package__.startswith("evaluation_module."):
    from .catalogue import catalogue_digest
    from .features import FEATURE_SCHEMA_VERSION, FeatureError, hand_features
else:
    from mudra_mlp.catalogue import catalogue_digest
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
    return bundle


def predict_hand(bundle: dict, coords, top_k: int = 3) -> dict:
    try:
        x = hand_features(coords).reshape(1, -1)
    except FeatureError as exc:
        return {"status": "invalid_input", "message": str(exc)}
    pipe = bundle["pipeline"]
    proba = pipe.predict_proba(x)[0]
    order = np.argsort(proba)[::-1]
    classes = pipe.classes_
    return {
        "status": "success",
        "predicted_label": str(classes[order[0]]),
        "confidence": float(proba[order[0]]),
        "top": [{"label": str(classes[i]), "score": float(proba[i])} for i in order[:top_k]],
        "model_version": bundle["metadata"]["model_version"],
        "note": "confidence is a raw model score, not a calibrated probability",
    }
