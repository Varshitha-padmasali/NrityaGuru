# NrityaGuru: Member 3 (Vision) <-> Member 4 (MLP & DTW Evaluator) Integration Guide

This document defines the formal data contract, coordinate conventions, missing-data semantics, and code integration patterns between **Member 3 (Computer Vision)** and **Member 4 (MLP Mudra Classifier & DTW Evaluator)**.

---

## 1. Executive Summary

Member 3 extracts time-ordered 260-dimensional landmark feature sequences from dance videos.
Member 4 evaluates single-hand mudras (12 classes) using an MLP and compares temporal movement sequences using Dynamic Time Warping (DTW).

The vision module provides two primary interfaces for Member 4:
1. **Offline / Batch**: Compressed `.npz` sequence archives + companion `.json` metadata files.
2. **Direct Python API / Adapter**: [`vision.adapter_member4`](file:///C:/Users/Admin/mini%20project/NrityaGuru/vision/adapter_member4.py) which adapts 260-dim feature vectors and `ProcessedSequence` objects directly into Member 4's `learner_frames` format (`list[np.ndarray | None]`).

---

## 2. 260-Dimensional Feature Schema

Each video frame produces a 1D NumPy array `(260,)` with `dtype=float64`:

| Index Range | Dimension | Sub-Feature | Component Description | Missing Value Semantics |
| :--- | :---: | :--- | :--- | :--- |
| `[0:132]` | 132 | **Body Pose** | 33 landmarks $\times$ 4: $[x, y, z, \text{visibility}]$ | Spatial coords: `NaN`<br>Visibility: `0.0` |
| `[132:195]` | 63 | **Left Hand** | 21 landmarks $\times$ 3: $[x, y, z]$ | Spatial coords: `NaN` |
| `[195]` | 1 | **Left Hand Conf** | MediaPipe hand detection/presence score $[0.0, 1.0]$ | Confidence: `0.0` |
| `[196:259]` | 63 | **Right Hand** | 21 landmarks $\times$ 3: $[x, y, z]$ | Spatial coords: `NaN` |
| `[259]` | 1 | **Right Hand Conf** | MediaPipe hand detection/presence score $[0.0, 1.0]$ | Confidence: `0.0` |

### Constant Slices in Code
```python
from vision.schemas import (
    POSE_SLICE,               # slice(0, 132)
    LEFT_HAND_SLICE,          # slice(132, 196)
    RIGHT_HAND_SLICE,         # slice(196, 260)
    LEFT_HAND_COORDS_SLICE,   # slice(132, 195)  -> 63 values for MLP
    RIGHT_HAND_COORDS_SLICE,  # slice(196, 259)  -> 63 values for MLP
)
```

---

## 3. Coordinate Conventions & Units

### 3.1 Vision Module Canonical Coordinates (Inside 260-dim vector)
- **Pose `[0:132]`**:
  - Origin $(0, 0, 0)$: Shoulder midpoint $\frac{\text{Left Shoulder} + \text{Right Shoulder}}{2}$.
  - Scale: Euclidean distance between left and right shoulders (falls back to torso height if shoulders degenerate).
  - Visibility: Component index 3 in each landmark quad, preserved in $[0.0, 1.0]$.
- **Hands `[132:195]` & `[196:259]`**:
  - Origin $(0, 0, 0)$: Wrist (Landmark 0).
  - Scale: Euclidean distance from wrist (Landmark 0) to middle finger base (Landmark 9 / Middle MCP).

### 3.2 Member 4 Pixel Coordinates vs. Normalized Coordinates
- **Member 4's MLP Training Convention**:
  - Member 4's `mudra_mlp.features.hand_features` expects 63 coordinates in **pixel units** $(x \cdot W, y \cdot H, z \cdot W)$.
  - *Why pixel units?* Raw MediaPipe $[0, 1]$ coordinates divide $x$ by width and $y$ by height. On non-square video frames (e.g., $1920 \times 1080$), computing Euclidean distances directly on $[0, 1]$ distorts angles and proportions. Converting to pixel units restores isotropic geometry before Member 4's own internal size normalization.
- **Adapter Support**:
  - If source frame width $W$ and height $H$ are provided, [`vision.adapter_member4`](file:///C:/Users/Admin/mini%20project/NrityaGuru/vision/adapter_member4.py) scales the coordinates to $(x \cdot W, y \cdot H, z \cdot W)$ automatically.
  - If $W$ and $H$ are omitted, normalized unit coordinates are returned.

---

## 4. Missing Landmarks, NaNs, and Masks

### 4.1 Golden Rule: NEVER Silent Zeroes
- Coordinate $(0, 0, 0)$ is a **valid spatial measurement** (e.g. wrist position).
- Missing landmarks are **always represented as IEEE 754 `NaN`** in feature matrices.
- Confidence scores and visibilities are set to `0.0` when missing.

### 4.2 Member 4 `learner_frames` Semantics
- In Member 4's `mudra_eval.build_result.build_evaluation_result(learner_frames=...)`, missing hand frames **must be `None`** (not an array filled with NaNs or zeroes):
  - If `None` is received, Member 4's result builder counts the missed frame, excludes it from MLP classification, and excludes it from DTW.
  - If NaNs are accidentally passed inside an array, Member 4's `validate_hand` raises a `FeatureError("landmarks contain NaN or infinite values")`.
- The adapter function `sequence_to_member4_frames(...)` guarantees that every missed frame is returned as `None`.

---

## 5. Exported NPZ & JSON Artifacts

The vision exporter produces two paired files:

### 5.1 NPZ Array Bundle (`<name>_features.npz`)
Loaded securely with `np.load(path, allow_pickle=False)`:
- `features`: `(T, 260)` `float64` array containing all frame vectors.
- `timestamps_ms`: `(T,)` `int64` array of millisecond timestamps.
- `timestamps_s`: `(T,)` `float64` array of second timestamps.
- `frame_indices`: `(T,)` `int64` array of source video frame numbers.
- `detection_mask`: `(T, 3)` `bool` array: `[pose_detected, left_hand_detected, right_hand_detected]`.
- `validity_mask`: `(T, 260)` `bool` array: `True` where coordinate is finite (not `NaN`).

### 5.2 Companion JSON Metadata (`<name>_metadata.json`)
```json
{
  "export_format_version": "1.0",
  "schema_version": "260-v1",
  "feature_dimension": 260,
  "num_frames": 90,
  "video_metadata": {
    "path": "dance_sample.mp4",
    "fps": 30.0,
    "frame_count": 90,
    "duration_s": 3.0,
    "width": 1280,
    "height": 720
  },
  "landmark_quality": {
    "hand_detection_rate": 0.9444,
    "pose_detection_rate": 1.0,
    "frames_total": 90,
    "frames_analysed": 90,
    "reliable": true,
    "notes": []
  }
}
```

The `landmark_quality` object conforms directly to Member 2's `LandmarkQuality` schema in `backend/app/schemas/evaluation.py`.

---

## 6. How Member 4 Consumes Vision Data (Code Examples)

### Pattern A: Loading from Exported Files (Recommended for Pipeline)

```python
import numpy as np
from vision.exporter import load_sequence
from vision.adapter_member4 import (
    sequence_to_member4_frames,
    check_sequence_readiness_for_member4,
)
from evaluation_module.mudra_eval.build_result import build_evaluation_result

# 1. Safely load sequence and companion metadata (allow_pickle=False is enforced)
sequence = load_sequence("output/dance_sample_features.npz")

# 2. Check quality & readiness (verifies >= 80% detection rate and >= 2 frames for DTW)
readiness = check_sequence_readiness_for_member4(sequence)
print(f"Can evaluate: {readiness['can_evaluate']} | Reliable: {readiness['reliable']}")

# 3. Adapt 260-dim sequence into Member 4's expected learner_frames format
#    side="auto" chooses whichever hand was detected with highest confidence.
#    Automatically scales to pixel units using sequence.metadata (width, height).
learner_frames = sequence_to_member4_frames(sequence, side="auto")

# 4. Pass directly to Member 4's build_evaluation_result
evaluation_result = build_evaluation_result(
    session_id="session-1234",
    learner_frames=learner_frames,
    reference_frames=reference_frames,  # Reference frames in same format
    bundle=mlp_bundle,
    expected_labels=["pataka"],
    reference_mudra_id="mudra_pataka",
)
```

### Pattern B: Extracting Single Frame Hand Coordinates from 260-dim Vector

```python
from vision.adapter_member4 import extract_hand_for_mlp

# frame_260 is a (260,) float64 numpy array
# Extracts 63 coordinates in pixel units, or None if no hand detected
hand_coords = extract_hand_for_mlp(
    frame_260,
    side="auto",       # or "Right" or "Left"
    width=1280,        # optional: scales to pixel space
    height=720,
)

if hand_coords is not None:
    # hand_coords is shape (63,) with finite pixel coordinates
    # Pass to Member 4's MLP predictor:
    pred = predict_hand(mlp_bundle, hand_coords)
```

### Pattern C: Dynamic Time Warping (DTW) on Full Dance Sequences

If Member 4 or the backend wishes to run DTW on whole-body dance sequences rather than single-hand features:

```python
from vision.adapter_member4 import sequence_to_dtw_matrix
from evaluation_module.sequence.dtw import dtw

# Extract finite pose feature matrices (T, 132), dropping invalid frames with NaNs
ref_matrix, ref_indices = sequence_to_dtw_matrix(reference_sequence, target="pose", drop_invalid=True)
learner_matrix, lea_indices = sequence_to_dtw_matrix(learner_sequence, target="pose", drop_invalid=True)

# Run DTW sequence comparison
dtw_res = dtw(ref_matrix, learner_matrix)
print(f"Alignment cost: {dtw_res.normalized_cost:.4f}")
```

---

## 7. Status of Integration Assumptions

| Area | Contract Agreement | Status | Team Action Required |
| :--- | :--- | :---: | :--- |
| **Vector Dimension** | 260 features per frame (`132` pose + `64` left hand + `64` right hand) | **Verified** | None. Fully verified by tests. |
| **Missing Hands** | `None` in `learner_frames`; `NaN` in feature matrices | **Verified** | None. Preserved by exporter and adapter. |
| **Pixel Coordinates** | Scaled by $(x \cdot W, y \cdot H, z \cdot W)$ | **Verified** | Automated by `sequence_to_member4_frames`. |
| **Single-Hand Selection** | Member 4 MLP only supports 12 single-hand classes. Adapter provides `side="auto"` (dominant/higher confidence) or explicit `"Right"` / `"Left"`. | **Functional** | Confirm with Member 4 if auto-selection by confidence is acceptable for two-handed gestures. |
| **DTW Thresholds** | DTW calculates normalized distance, but `threshold` and `within_threshold` remain `null` in Member 4's output. | **Open** | Needs calibration against real expert recordings. |
| **Pose DTW** | Member 4 currently evaluates DTW only over 78 hand features. Vision provides full 132-dim pose sequences. | **Available** | Backend/Member 4 can incorporate pose DTW when full-body evaluation is enabled. |
