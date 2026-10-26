"""Demo with SIMULATED sequences built from REAL dataset hand images (no real video).

Keyframes are real hand landmarks from data/hand_landmarks.csv. Frames between them are made by
linear interpolation, and the 'learner' holds each pose longer (slower) than the reference.
This shows how DTW + MLP behave; it is NOT a measurement of real dance performance.

Run from the evaluation_module folder:
    python -m demo.run_demo
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from mudra_eval.build_result import build_evaluation_result
from mudra_mlp.features import normalise_hand
from mudra_mlp.predict import load_bundle
from mudra_mlp.train import HAND_COLS


def keyframes_from_csv(csv_path: Path, labels: list[str], which: str) -> list[np.ndarray]:
    df = pd.read_csv(csv_path).copy()
    df["label_norm"] = df["label"].astype(str).str.strip().str.lower()
    df = df[df["n_hands"] >= 1].drop_duplicates(subset=["md5"]).sort_values(["label_norm", "file"])
    out = []
    for lab in labels:
        rows = df[df["label_norm"] == lab]
        if rows.empty:
            raise SystemExit(f"No detected-hand images for class '{lab}' in {csv_path}")
        row = rows.iloc[0] if which == "first" else rows.iloc[-1]
        out.append(normalise_hand(row[HAND_COLS].to_numpy(dtype=float)))
    return out


def make_sequence(keys: list[np.ndarray], hold: int, morph: int, noise: float, seed: int) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    frames: list[np.ndarray] = []
    for i, k in enumerate(keys):
        frames += [k] * hold
        if i + 1 < len(keys):
            for t in np.linspace(0, 1, morph + 2)[1:-1]:
                frames.append((1 - t) * k + t * keys[i + 1])
    return [(f + rng.normal(scale=noise, size=f.shape)).reshape(-1) for f in frames]


def drop_frames(frames, fraction: float, seed: int):
    rng = np.random.default_rng(seed)
    return [None if rng.random() < fraction else f for f in frames]


def describe(name: str, r: dict) -> None:
    merged = []   # show consecutive segments with the same label as one
    for p in r["predicted_labels"]:
        i = p["interval"]
        if merged and merged[-1][0] == p["label"]:
            merged[-1][2] = i["end_frame"]
        else:
            merged.append([p["label"], i["start_frame"], i["end_frame"]])
    segs = " -> ".join(f"{lab}[{s}-{e}]" for lab, s, e in merged)
    d = r["dtw"]
    q = r["landmark_quality"]
    print(f"\n=== {name} ===")
    print(f"labels over time : {segs or '(none)'}")
    print(f"DTW normalised   : {d['normalized_distance']:.3f}" if d else "DTW             : not available")
    print(f"hand detected    : {q['frames_analysed']}/{q['frames_total']} frames, reliable={q['reliable']}")
    print(f"deviations       : {len(r['deviations'])}" + "".join(f"\n   - {x['description']}" for x in r["deviations"]))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--csv", type=Path, default=Path("data/hand_landmarks.csv"))
    ap.add_argument("--model", type=Path, default=Path("models/mudra_mlp.joblib"))
    ap.add_argument("--sequence", nargs=3, default=["pathaka", "mushti", "shikaram"])
    ap.add_argument("--wrong-middle", default="trishoolam")
    ap.add_argument("--out", type=Path, default=Path("demo_output"))
    a = ap.parse_args()

    bundle = load_bundle(a.model)
    seq = [s.lower() for s in a.sequence]
    ref = make_sequence(keyframes_from_csv(a.csv, seq, "first"), hold=8, morph=4, noise=0.01, seed=1)
    good_keys = keyframes_from_csv(a.csv, seq, "last")
    wrong_keys = list(good_keys)
    wrong_keys[1] = keyframes_from_csv(a.csv, [a.wrong_middle.lower()], "last")[0]

    learner_good = make_sequence(good_keys, hold=14, morph=8, noise=0.02, seed=2)
    learner_wrong = make_sequence(wrong_keys, hold=14, morph=8, noise=0.02, seed=3)
    learner_missing = drop_frames(learner_good, 0.45, seed=4)

    scenarios = {
        "A_correct_but_slower": learner_good,
        "B_wrong_middle_mudra": learner_wrong,
        "C_correct_with_45pct_missing_hands": learner_missing,
    }
    a.out.mkdir(parents=True, exist_ok=True)
    print("SIMULATED sequences built from real dataset hand images (not real video).")
    print(f"expected order: {' -> '.join(seq)} (reference = {len(ref)} frames)")
    for name, frames in scenarios.items():
        result = build_evaluation_result(
            session_id=f"demo-{name[:1]}", learner_frames=frames, reference_frames=ref, bundle=bundle,
            expected_labels=seq, reference_mudra_id="mudra_demo_sequence", reference_sequence_id="DEMO-SEQ-001")
        describe(name, result)
        (a.out / f"{name}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nJSON results saved in {a.out}\\")


if __name__ == "__main__":
    main()