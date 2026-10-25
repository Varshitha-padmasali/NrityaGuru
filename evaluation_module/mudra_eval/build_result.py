"""Combine MLP predictions and a DTW comparison into an EvaluationResult.

The output is a plain dict that follows the backend contract v1.0
(backend/docs/evaluation_contract.md). Rules this module follows:
  * Only report what was actually measured. No finger-level claims are made, because the
    MLP and DTW cannot measure them; label mismatches are reported as general deviations.
  * DTW distance is reported as an alignment cost. threshold / within_threshold are left empty
    because no threshold has been validated on real performance data.
  * Frames where no hand was detected are not zero-filled; they are dropped and counted.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from mudra_mlp.features import FEATURE_SCHEMA_VERSION, FeatureError, hand_features
from mudra_mlp.predict import predict_hand
from sequence.dtw import DTWInputError, dtw

SCHEMA_VERSION = "1.0"
RELIABLE_DETECTION_RATE = 0.8   # prototype assumption, NOT a calibrated value
MIN_DEVIATION_FRAMES = 3        # ignore 1-2 frame flickers when reporting label deviations
MIN_DEVIATION_CONFIDENCE = 0.6  # transition frames are low-confidence; do not report them (prototype assumption)
MAX_PREDICTIONS = 100           # contract limit
MAX_DEVIATIONS = 50             # contract limit


def _analyse(frames, bundle):
    """Per frame: dict(label, confidence, features) or None if the hand is missing/invalid."""
    out = []
    for coords in frames:
        if coords is None:
            out.append(None)
            continue
        pred = predict_hand(bundle, coords)
        if pred["status"] != "success":
            out.append(None)
            continue
        out.append({"label": pred["predicted_label"], "confidence": pred["confidence"],
                    "features": hand_features(coords)})
    return out


def _reference_features(frames) -> np.ndarray:
    feats = []
    for coords in frames:
        if coords is None:
            continue
        try:
            feats.append(hand_features(coords))
        except FeatureError:
            continue
    return np.array(feats)


def _segments(analysed):
    """Merge consecutive frames with the same predicted label into segments."""
    segs = []
    for i, a in enumerate(analysed):
        if a is None:
            continue
        if segs and segs[-1]["label"] == a["label"] and segs[-1]["end"] == i - 1:
            segs[-1]["end"] = i
            segs[-1]["conf"].append(a["confidence"])
        else:
            segs.append({"label": a["label"], "start": i, "end": i, "conf": [a["confidence"]]})
    return segs


def build_evaluation_result(*, session_id: str, learner_frames, reference_frames, bundle,
                            expected_labels: list[str], reference_mudra_id: str | None = None,
                            reference_movement_id: str | None = None,
                            reference_sequence_id: str | None = None, is_mock: bool = False) -> dict:
    """learner_frames / reference_frames: lists with one entry per frame, each either a
    63-value hand-landmark vector (pixel units) or None when no hand was detected."""
    if (reference_mudra_id is None) == (reference_movement_id is None):
        raise ValueError("give exactly one of reference_mudra_id / reference_movement_id")

    warnings = ["Prototype MLP trained on static images (image-level split); not validated on video or new performers.",
                "DTW distance is an alignment cost; no pass/fail threshold has been validated."]
    analysed = _analyse(learner_frames, bundle)
    total = len(learner_frames)
    valid = sum(a is not None for a in analysed)

    # ---- predicted labels (segments) ----
    segs = _segments(analysed)
    if len(segs) > MAX_PREDICTIONS:
        segs = sorted(sorted(segs, key=lambda s: s["start"] - s["end"])[:MAX_PREDICTIONS], key=lambda s: s["start"])
        warnings.append(f"More than {MAX_PREDICTIONS} label segments; only the longest are reported.")
    predicted = [{"label": s["label"],
                  "confidence": round(float(min(max(np.mean(s["conf"]), 0.0), 1.0)), 4),
                  "interval": {"start_frame": s["start"], "end_frame": s["end"],
                               "start_time_s": None, "end_time_s": None}} for s in segs]

    # ---- deviations: only label mismatches the MLP itself observed ----
    expected_lower = {e.lower() for e in expected_labels}
    deviations = []
    for k, s in enumerate(segs, start=1):
        length = s["end"] - s["start"] + 1
        if (s["label"].lower() not in expected_lower and length >= MIN_DEVIATION_FRAMES
                and float(np.mean(s["conf"])) >= MIN_DEVIATION_CONFIDENCE and len(deviations) < MAX_DEVIATIONS):
            deviations.append({
                "deviation_id": f"MLP-D{len(deviations) + 1}", "kind": "hand_pose", "body_part": None,
                "description": f"Hand shape classified as '{s['label']}' in frames {s['start']}-{s['end']}; "
                               f"expected {', '.join(expected_labels) or 'unknown'}.",
                "measured_value": None, "reference_value": None, "unit": None, "severity": None,
                "interval": {"start_frame": s["start"], "end_frame": s["end"], "start_time_s": None, "end_time_s": None},
                "source_module": "mlp"})

    # ---- DTW on frames where a hand was detected ----
    dtw_summary = None
    learner_feats = np.array([a["features"] for a in analysed if a is not None])
    ref_feats = _reference_features(reference_frames)
    if len(learner_feats) >= 2 and len(ref_feats) >= 2:
        try:
            res = dtw(ref_feats, learner_feats)
            dtw_summary = {"distance": float(res.raw_cost), "normalized_distance": float(res.normalized_cost),
                           "threshold": None, "within_threshold": None,
                           "reference_sequence_id": reference_sequence_id,
                           "feature_schema_version": FEATURE_SCHEMA_VERSION}
        except DTWInputError as exc:
            warnings.append(f"DTW could not be computed: {exc}")
    else:
        warnings.append("Not enough frames with a detected hand to run DTW.")

    # ---- landmark quality ----
    rate = (valid / total) if total else None
    reliable = bool(rate is not None and valid > 0 and rate >= RELIABLE_DETECTION_RATE)
    notes = [] if reliable else [f"Hand detected in {valid} of {total} frames "
                                 f"(reliable needs >= {RELIABLE_DETECTION_RATE:.0%}, a prototype assumption)."]
    quality = {"hand_detection_rate": None if rate is None else round(rate, 4), "pose_detection_rate": None,
               "frames_total": total, "frames_analysed": valid, "reliable": reliable, "notes": notes}

    return {
        "schema_version": SCHEMA_VERSION, "session_id": session_id,
        "reference_movement_id": reference_movement_id, "reference_mudra_id": reference_mudra_id,
        "expected_labels": list(expected_labels), "predicted_labels": predicted,
        "dtw": dtw_summary, "deviations": deviations, "landmark_quality": quality, "warnings": warnings,
        "mlp_model_version": bundle["metadata"]["model_version"],
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "is_mock": is_mock,
    }