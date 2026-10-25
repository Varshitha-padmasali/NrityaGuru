"""Hand-landmark feature engineering, shared by training AND prediction.

Input: 21 MediaPipe hand landmarks as 63 numbers (x0,y0,z0,x1,y1,z1,...) in pixel units,
as written by data_prep/extract_hand_landmarks.py.

Features (78 numbers):
  * 63 normalised coordinates: wrist moved to the origin, everything divided by the
    wrist -> middle-finger-base distance (so hand position and hand size no longer matter)
  * 5 fingertip -> wrist distances (normalised)
  * 10 fingertip <-> fingertip distances (normalised)
"""
from __future__ import annotations

from itertools import combinations

import numpy as np

N_LANDMARKS = 21
FEATURE_SCHEMA_VERSION = "hand-v1"
WRIST, MIDDLE_MCP = 0, 9
FINGERTIPS = (4, 8, 12, 16, 20)
TIP_NAMES = ("thumb", "index", "middle", "ring", "pinky")


class FeatureError(ValueError):
    """Raised when hand landmarks cannot be turned into features."""


def validate_hand(coords) -> np.ndarray:
    try:
        arr = np.asarray(coords, dtype=float)
    except (TypeError, ValueError) as exc:
        raise FeatureError("landmarks are not numeric") from exc
    if arr.shape == (N_LANDMARKS * 3,):
        arr = arr.reshape(N_LANDMARKS, 3)
    if arr.shape != (N_LANDMARKS, 3):
        raise FeatureError(f"expected 21 landmarks x 3 values, got shape {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise FeatureError("landmarks contain NaN or infinite values")
    return arr


def normalise_hand(coords) -> np.ndarray:
    pts = validate_hand(coords)
    pts = pts - pts[WRIST]
    scale = float(np.linalg.norm(pts[MIDDLE_MCP]))
    if scale < 1e-6:
        raise FeatureError("hand has zero size (wrist and middle-finger base coincide)")
    return pts / scale


def _features_from_normalised(pts: np.ndarray) -> np.ndarray:
    tips = pts[list(FINGERTIPS)]
    tip_wrist = np.linalg.norm(tips, axis=1)
    tip_pairs = [np.linalg.norm(tips[i] - tips[j]) for i, j in combinations(range(5), 2)]
    return np.concatenate([pts.reshape(-1), tip_wrist, np.array(tip_pairs)])


def hand_features(coords) -> np.ndarray:
    return _features_from_normalised(normalise_hand(coords))


def mirrored_hand_features(coords) -> np.ndarray:
    """Features of the left/right mirror image (used to augment training data)."""
    pts = normalise_hand(coords).copy()
    pts[:, 0] *= -1.0
    return _features_from_normalised(pts)


def feature_names() -> list[str]:
    names = [f"{a}{i}" for i in range(N_LANDMARKS) for a in "xyz"]
    names += [f"dist_{t}_wrist" for t in TIP_NAMES]
    names += [f"dist_{TIP_NAMES[i]}_{TIP_NAMES[j]}" for i, j in combinations(range(5), 2)]
    return names