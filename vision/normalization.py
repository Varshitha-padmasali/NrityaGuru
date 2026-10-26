"""Landmark normalization for hands and body pose.

Normalizes:
- Hand landmarks relative to the wrist (origin) and wrist-to-middle-finger-base distance (palm scale).
- Pose landmarks relative to the shoulder midpoint (origin) and shoulder width (scale).

Guarantees scale and translation invariance while handling missing and degenerate landmarks
by producing explicit NaNs rather than misleading zeros.
"""

from __future__ import annotations

import math
from typing import Union
import numpy as np

from vision.schemas import (
    HandLandmarkSet,
    N_HAND_LANDMARKS,
    N_POSE_LANDMARKS,
    Point3D,
    PoseLandmarkSet,
)

# Reference landmark indices
HAND_WRIST_IDX: int = 0
HAND_MIDDLE_MCP_IDX: int = 9  # Base of middle finger (palm reference, matches Member 4 features.py)

POSE_LEFT_SHOULDER_IDX: int = 11
POSE_RIGHT_SHOULDER_IDX: int = 12
POSE_LEFT_HIP_IDX: int = 23
POSE_RIGHT_HIP_IDX: int = 24

EPSILON: float = 1e-6


class NormalizationError(ValueError):
    """Raised when landmark geometry is degenerate or unnormalizable."""


def normalize_hand_landmarks(
    hand: Union[HandLandmarkSet, np.ndarray, list[Point3D]],
) -> np.ndarray:
    """Normalize hand landmarks relative to wrist and palm scale.

    The wrist is translated to (0, 0, 0) and coordinates are divided by the
    distance from the wrist to the middle finger MCP joint (Landmark 9).

    Args:
        hand: HandLandmarkSet, array of shape (21, 3) or (63,), or list of 21 Point3D.

    Returns:
        np.ndarray of shape (21, 3) in normalized units.
        Returns array of NaNs if the hand is missing or degenerate.
    """
    nan_result = np.full((N_HAND_LANDMARKS, 3), np.nan, dtype=float)

    if isinstance(hand, HandLandmarkSet):
        if not hand.is_detected or not hand.landmarks:
            return nan_result
        coords = np.array([lm.to_array(include_visibility=False) for lm in hand.landmarks], dtype=float)
    elif isinstance(hand, list):
        if len(hand) != N_HAND_LANDMARKS:
            return nan_result
        coords = np.array([pt.to_array(include_visibility=False) for pt in hand], dtype=float)
    elif isinstance(hand, np.ndarray):
        arr = np.asarray(hand, dtype=float)
        if arr.shape == (N_HAND_LANDMARKS * 3,):
            coords = arr.reshape(N_HAND_LANDMARKS, 3)
        elif arr.shape == (N_HAND_LANDMARKS, 3):
            coords = arr
        else:
            return nan_result
    else:
        return nan_result

    # Check for NaN or infinite coordinates
    if not np.all(np.isfinite(coords)):
        return nan_result

    # Translate wrist to origin (0, 0, 0)
    wrist = coords[HAND_WRIST_IDX]
    shifted = coords - wrist

    # Compute palm scale reference (wrist to middle MCP distance)
    palm_scale = float(np.linalg.norm(shifted[HAND_MIDDLE_MCP_IDX]))
    if palm_scale < EPSILON:
        # Degenerate hand size (wrist and middle MCP coincide)
        return nan_result

    return shifted / palm_scale


def normalize_pose_landmarks(
    pose: Union[PoseLandmarkSet, np.ndarray, list[Point3D]],
    include_visibility: bool = True,
) -> np.ndarray:
    """Normalize body pose landmarks relative to shoulder midpoint and shoulder width.

    The shoulder midpoint is translated to (0, 0, 0) and coordinates are divided by
    the Euclidean distance between the left and right shoulders.
    If shoulders coincide or are degenerate, falls back to torso height (shoulder midpoint to hip midpoint).
    Visibilities (if requested) are preserved unchanged in [0, 1].

    Args:
        pose: PoseLandmarkSet, array of shape (33, 4)/(33, 3)/(132,), or list of 33 Point3D.
        include_visibility: Whether to return (33, 4) with visibilities or (33, 3).

    Returns:
        np.ndarray of shape (33, 4) or (33, 3).
        Returns array of NaNs for coordinates if pose is missing or degenerate.
    """
    dim = 4 if include_visibility else 3
    nan_result = np.full((N_POSE_LANDMARKS, dim), np.nan, dtype=float)
    if include_visibility:
        nan_result[:, 3] = 0.0  # zero visibility for missing pose

    if isinstance(pose, PoseLandmarkSet):
        if not pose.is_detected or not pose.landmarks:
            return nan_result
        coords = np.array([lm.to_array(include_visibility=False) for lm in pose.landmarks], dtype=float)
        visibilities = np.array([lm.visibility if lm.visibility is not None else 0.0 for lm in pose.landmarks], dtype=float)
    elif isinstance(pose, list):
        if len(pose) != N_POSE_LANDMARKS:
            return nan_result
        coords = np.array([pt.to_array(include_visibility=False) for pt in pose], dtype=float)
        visibilities = np.array([pt.visibility if pt.visibility is not None else 0.0 for pt in pose], dtype=float)
    elif isinstance(pose, np.ndarray):
        arr = np.asarray(pose, dtype=float)
        if arr.shape == (N_POSE_LANDMARKS * 4,):
            arr = arr.reshape(N_POSE_LANDMARKS, 4)
            coords = arr[:, :3]
            visibilities = arr[:, 3]
        elif arr.shape == (N_POSE_LANDMARKS, 4):
            coords = arr[:, :3]
            visibilities = arr[:, 3]
        elif arr.shape == (N_POSE_LANDMARKS * 3,):
            coords = arr.reshape(N_POSE_LANDMARKS, 3)
            visibilities = np.ones((N_POSE_LANDMARKS,), dtype=float)
        elif arr.shape == (N_POSE_LANDMARKS, 3):
            coords = arr
            visibilities = np.ones((N_POSE_LANDMARKS,), dtype=float)
        else:
            return nan_result
    else:
        return nan_result

    # Check for NaN or infinite coordinates
    if not np.all(np.isfinite(coords)):
        return nan_result

    # Center at shoulder midpoint
    left_shoulder = coords[POSE_LEFT_SHOULDER_IDX]
    right_shoulder = coords[POSE_RIGHT_SHOULDER_IDX]
    shoulder_mid = (left_shoulder + right_shoulder) / 2.0
    shifted = coords - shoulder_mid

    # Primary scale: shoulder width
    scale = float(np.linalg.norm(left_shoulder - right_shoulder))
    if scale < EPSILON:
        # Fallback scale: torso height (mid-shoulder to mid-hip)
        left_hip = coords[POSE_LEFT_HIP_IDX]
        right_hip = coords[POSE_RIGHT_HIP_IDX]
        hip_mid = (left_hip + right_hip) / 2.0
        scale = float(np.linalg.norm(shoulder_mid - hip_mid))
        if scale < EPSILON:
            # Degenerate pose scale
            return nan_result

    norm_coords = shifted / scale

    if include_visibility:
        return np.column_stack([norm_coords, visibilities])
    return norm_coords
