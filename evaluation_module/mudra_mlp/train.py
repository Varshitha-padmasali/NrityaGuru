"""Train and evaluate an MLP mudra classifier from data/hand_landmarks.csv.

Run from the evaluation_module folder:
    python -m mudra_mlp.train --csv data\\hand_landmarks.csv --out models

Honest-reporting notes:
  * Split is by IMAGE (stratified). The dataset has no performer ids, so this does NOT test
    generalisation to new people; real webcam accuracy will probably be lower.
  * Exact duplicate files are removed; files that appear under two labels are dropped.
  * Mirrored copies are added to the TRAINING set only. Validation/test use original images.
  * The scaler is fitted on training data only (inside the sklearn Pipeline).
"""
from __future__ import annotations

import argparse
import json
import platform
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from mudra_mlp.features import (
    FEATURE_SCHEMA_VERSION,
    FeatureError,
    feature_names,
    hand_features,
    mirrored_hand_features,
)

SEED = 42
MODEL_VERSION = "0.1-prototype"
HAND_COLS = [f"h0_{a}{i}" for i in range(21) for a in "xyz"]
DEFAULT_CLASSES = [
    "pathaka", "tripathaka", "arthapataka", "mushti", "shikaram", "soochi",
    "simhamugham", "trishoolam", "kapitham", "mayooram", "arthachandran", "kartharimukaham",
]
GRID = [{"hidden_layer_sizes": h, "alpha": a} for h in [(64,), (128, 64)] for a in [1e-4, 1e-3, 1e-2]]


def load_dataset(csv_path: Path, classes: list[str]):
    df = pd.read_csv(csv_path).copy()
    df["label_norm"] = df["label"].astype(str).str.strip().str.lower()
    wanted = [c.strip().lower() for c in classes]
    missing = sorted(set(wanted) - set(df["label_norm"]))
    if missing:
        raise SystemExit(f"Classes not found in CSV: {missing}\nAvailable: {sorted(df['label_norm'].unique())}")
    df = df[df["label_norm"].isin(wanted)]
    info = {"images_in_selected_classes": int(len(df))}

    df = df[df["n_hands"] >= 1]
    info["with_detected_hand"] = int(len(df))
    conflicts = df.groupby("md5")["label_norm"].nunique()
    bad_md5 = conflicts[conflicts > 1].index
    info["dropped_same_file_in_two_classes"] = int(df["md5"].isin(bad_md5).sum())
    df = df[~df["md5"].isin(bad_md5)]
    before = len(df)
    df = df.drop_duplicates(subset=["md5"])
    info["dropped_exact_duplicates"] = int(before - len(df))

    raw, labels = [], []
    skipped = 0
    for _, row in df.iterrows():
        coords = row[HAND_COLS].to_numpy(dtype=float)
        try:
            hand_features(coords)
        except FeatureError:
            skipped += 1
            continue
        raw.append(coords)
        labels.append(row["label_norm"])
    info["dropped_invalid_landmarks"] = skipped
    info["final_samples"] = len(labels)
    return np.array(raw), np.array(labels), info


def make_pipeline(hidden, alpha) -> Pipeline:
    return Pipeline([
        ("scale", StandardScaler()),
        ("mlp", MLPClassifier(hidden_layer_sizes=hidden, alpha=alpha, activation="relu", solver="adam",
                              max_iter=600, random_state=SEED)),
    ])


def train(csv_path: Path, classes: list[str], out_dir: Path, seed: int = SEED, verbose: bool = True) -> dict:
    raw, y, info = load_dataset(csv_path, classes)
    idx = np.arange(len(y))
    tr, tmp = train_test_split(idx, test_size=0.4, stratify=y, random_state=seed)
    va, te = train_test_split(tmp, test_size=0.5, stratify=y[tmp], random_state=seed)

    X = np.array([hand_features(r) for r in raw])
    X_mirror = np.array([mirrored_hand_features(r) for r in raw])
    X_train = np.vstack([X[tr], X_mirror[tr]])
    y_train = np.concatenate([y[tr], y[tr]])

    results = []
    best = None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=ConvergenceWarning)
        for cfg in GRID:
            pipe = make_pipeline(cfg["hidden_layer_sizes"], cfg["alpha"]).fit(X_train, y_train)
            val_pred = pipe.predict(X[va])
            _, _, f1, _ = precision_recall_fscore_support(y[va], val_pred, average="macro", zero_division=0)
            results.append({**cfg, "hidden_layer_sizes": list(cfg["hidden_layer_sizes"]),
                            "val_macro_f1": float(f1), "val_accuracy": float(accuracy_score(y[va], val_pred))})
            if best is None or f1 > best[0]:
                best = (f1, cfg, pipe)
    _, best_cfg, pipe = best

    pred = pipe.predict(X[te])
    labels_sorted = list(pipe.classes_)
    p, r, f1, _ = precision_recall_fscore_support(y[te], pred, average="macro", zero_division=0)
    _, _, wf1, _ = precision_recall_fscore_support(y[te], pred, average="weighted", zero_division=0)
    cm = confusion_matrix(y[te], pred, labels=labels_sorted)
    metrics = {
        "test_accuracy": float(accuracy_score(y[te], pred)),
        "test_macro_precision": float(p), "test_macro_recall": float(r),
        "test_macro_f1": float(f1), "test_weighted_f1": float(wf1),
        "chance_level_accuracy": 1.0 / len(labels_sorted),
        "per_class": classification_report(y[te], pred, labels=labels_sorted, output_dict=True, zero_division=0),
        "confusion_matrix": cm.tolist(), "confusion_matrix_labels": labels_sorted,
    }
    meta = {
        "model_version": MODEL_VERSION, "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "trained_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "classes": labels_sorted, "feature_names": feature_names(), "seed": seed,
        "best_config": {"hidden_layer_sizes": list(best_cfg["hidden_layer_sizes"]), "alpha": best_cfg["alpha"]},
        "split_sizes": {"train": int(len(tr)), "train_with_mirrored": int(len(X_train)),
                        "validation": int(len(va)), "test": int(len(te))},
        "dataset_report": info, "grid_results": results,
        "versions": {"python": platform.python_version(), "scikit-learn": sklearn.__version__,
                     "numpy": np.__version__, "pandas": pd.__version__},
        "limitations": ["Image-level split; no performer ids, so performer generalisation is untested.",
                        "Static images only; not validated on webcam video.",
                        "MLP scores are raw model outputs, not calibrated probabilities."],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipe, "metadata": meta}, out_dir / "mudra_mlp.joblib")
    (out_dir / "mudra_mlp_metrics.json").write_text(json.dumps({"metrics": metrics, "metadata": meta}, indent=2), encoding="utf-8")
    pd.DataFrame(cm, index=labels_sorted, columns=labels_sorted).to_csv(out_dir / "mudra_mlp_confusion_matrix.csv")

    if verbose:
        print("\nDATASET:", json.dumps(info))
        print("SPLIT:", meta["split_sizes"])
        print("\nVALIDATION (model selection):")
        for r_ in results:
            print(f"  hidden={r_['hidden_layer_sizes']!s:<10} alpha={r_['alpha']:<7} val_macro_f1={r_['val_macro_f1']:.3f}")
        print(f"\nCHOSEN: {meta['best_config']}")
        print(f"\nTEST accuracy={metrics['test_accuracy']:.3f} (chance={metrics['chance_level_accuracy']:.3f}) "
              f"macro P/R/F1 = {p:.3f}/{r:.3f}/{f1:.3f}")
        print("\n" + classification_report(y[te], pred, labels=labels_sorted, zero_division=0))
        print("Confusion matrix (rows = true, columns = predicted):")
        print(pd.DataFrame(cm, index=labels_sorted, columns=labels_sorted).to_string())
        print(f"\nSaved to {out_dir}: mudra_mlp.joblib, mudra_mlp_metrics.json, mudra_mlp_confusion_matrix.csv")
    return metrics


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--csv", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--classes", nargs="+", default=DEFAULT_CLASSES)
    args = ap.parse_args()
    train(args.csv, args.classes, args.out)


if __name__ == "__main__":
    main()