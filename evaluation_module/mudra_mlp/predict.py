"""Predict a mudra label from ONE hand's 63 landmark values (pixel units).

Only load model files you trained yourself: joblib/pickle files can run code when loaded.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np

from mudra_mlp.features import FEATURE_SCHEMA_VERSION, FeatureError, hand_features


def load_bundle(path: Path | str) -> dict:
    bundle = joblib.load(path)
    if not isinstance(bundle, dict) or "pipeline" not in bundle or "metadata" not in bundle:
        raise ValueError("not a valid mudra model bundle")
    if bundle["metadata"].get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        raise ValueError("model was trained with a different feature schema version")
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