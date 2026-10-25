"""Dynamic Time Warping (DTW) between a reference and a learner feature sequence.

Each sequence is a 2-D array of shape (n_frames, n_features). Frames are compared
with Euclidean distance. The cumulative cost follows

    D(i, j) = d(r_i, l_j) + min(D(i-1, j), D(i, j-1), D(i-1, j-1))

with D(0, 0) = d(r_0, l_0). The alignment must start at (0, 0) and end at
(n-1, m-1), and it only moves forward in time.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


class DTWInputError(ValueError):
    """Raised when a sequence cannot be compared (empty, wrong shape, NaN/inf...)."""


@dataclass(frozen=True)
class DTWResult:
    raw_cost: float          # sum of local distances along the best alignment path
    normalized_cost: float   # raw_cost / len(path)  (average local distance on the path)
    path: list[tuple[int, int]]  # (reference_index, learner_index) pairs, in time order
    reference_length: int
    learner_length: int


def _validate(name: str, seq) -> np.ndarray:
    try:
        arr = np.asarray(seq, dtype=float)
    except (TypeError, ValueError) as exc:
        raise DTWInputError(f"{name} is not a numeric array") from exc
    if arr.ndim != 2:
        raise DTWInputError(f"{name} must be 2-D (frames, features); got {arr.ndim}-D")
    if arr.shape[0] == 0 or arr.shape[1] == 0:
        raise DTWInputError(f"{name} is empty")
    if not np.all(np.isfinite(arr)):
        raise DTWInputError(f"{name} contains NaN or infinite values")
    return arr


def dtw(reference, learner) -> DTWResult:
    """Compare two sequences with DTW. Raises DTWInputError on invalid input."""
    ref = _validate("reference", reference)
    lea = _validate("learner", learner)
    if ref.shape[1] != lea.shape[1]:
        raise DTWInputError(
            f"feature dimension mismatch: reference {ref.shape[1]} vs learner {lea.shape[1]}"
        )

    n, m = ref.shape[0], lea.shape[0]
    # Local distance matrix: dist[i, j] = ||ref[i] - lea[j]||
    dist = np.linalg.norm(ref[:, None, :] - lea[None, :, :], axis=2)

    acc = np.full((n, m), np.inf)
    acc[0, 0] = dist[0, 0]
    for i in range(n):
        for j in range(m):
            if i == 0 and j == 0:
                continue
            best_prev = min(
                acc[i - 1, j] if i > 0 else np.inf,
                acc[i, j - 1] if j > 0 else np.inf,
                acc[i - 1, j - 1] if i > 0 and j > 0 else np.inf,
            )
            acc[i, j] = dist[i, j] + best_prev

    # Backtrack from (n-1, m-1) to (0, 0)
    i, j = n - 1, m - 1
    path = [(i, j)]
    while (i, j) != (0, 0):
        candidates = []
        if i > 0 and j > 0:
            candidates.append((acc[i - 1, j - 1], (i - 1, j - 1)))
        if i > 0:
            candidates.append((acc[i - 1, j], (i - 1, j)))
        if j > 0:
            candidates.append((acc[i, j - 1], (i, j - 1)))
        _, (i, j) = min(candidates, key=lambda c: c[0])  # ties prefer the diagonal
        path.append((i, j))
    path.reverse()

    raw = float(acc[n - 1, m - 1])
    return DTWResult(
        raw_cost=raw,
        normalized_cost=raw / len(path),
        path=path,
        reference_length=n,
        learner_length=m,
    )