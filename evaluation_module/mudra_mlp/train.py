"""Train and evaluate an MLP mudra classifier from data/hand_landmarks.csv.

Run from the evaluation_module folder:
    python -m mudra_mlp.train --csv data\\hand_landmarks.csv --out models

Honest-reporting notes:
  * Split is grouped by perceptual image hash and stratified by label. The dataset has no
    performer ids, so this does NOT test generalisation to new people.
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
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

if __package__ and __package__.startswith("evaluation_module."):
    from .catalogue import asamyuta_names, canonical_record, catalogue_digest, dataset_mapping_digest, model_class_mapping
    from .features import FEATURE_SCHEMA_VERSION, FeatureError, feature_names, hand_features, mirrored_hand_features
else:
    from mudra_mlp.catalogue import asamyuta_names, canonical_record, catalogue_digest, dataset_mapping_digest, model_class_mapping
    from mudra_mlp.features import FEATURE_SCHEMA_VERSION, FeatureError, feature_names, hand_features, mirrored_hand_features

SEED = 42
MODEL_VERSION = "0.1-prototype"
HAND_COLS = [f"h0_{a}{i}" for i in range(21) for a in "xyz"]
DEFAULT_CLASSES = None  # Infer all catalogue Asamyuta classes actually represented in the CSV.
GRID = [{"hidden_layer_sizes": h, "alpha": a} for h in [(64,), (128, 64)] for a in [1e-4, 1e-3, 1e-2]]


def load_dataset(csv_path: Path, classes: list[str] | None, *, strict_catalogue: bool = True):
    df = pd.read_csv(csv_path).copy()
    required = {"label", "n_hands", "md5", "phash", *HAND_COLS}
    missing_columns = sorted(required - set(df.columns))
    if missing_columns:
        raise ValueError(f"landmark CSV is missing required columns: {missing_columns}")
    raw_labels = df["label"].astype(str).str.strip()
    mapped = [canonical_record(label) for label in raw_labels]
    if strict_catalogue:
        unknown = sorted({label for label, record in zip(raw_labels, mapped) if record is None})
        if unknown:
            raise ValueError(f"dataset contains labels absent from the canonical catalogue: {unknown}")
        df["label_norm"] = [record["name"] for record in mapped]
        df["mudra_category"] = [record["category"] for record in mapped]
        unsupported = int((df["mudra_category"] != "Asamyuta Hasta").sum())
        df = df[df["mudra_category"] == "Asamyuta Hasta"]
    else:
        df["label_norm"] = raw_labels.str.casefold()
        df["mudra_category"] = "synthetic_test_label"
        unsupported = 0

    available = sorted(df["label_norm"].unique())
    if classes is None:
        wanted = available
    elif strict_catalogue:
        requested = []
        for label in classes:
            record = canonical_record(label)
            if record is None:
                raise SystemExit(f"Class not found in canonical catalogue: {label}")
            if record["category"] != "Asamyuta Hasta":
                raise ValueError(f"The single-hand MLP cannot train on two-hand class {label!r}")
            requested.append(record["name"])
        if len(set(requested)) != len(requested):
            raise ValueError("classes contain duplicate labels after canonical alias resolution")
        wanted = requested
    else:
        wanted = [c.strip().casefold() for c in classes]
    missing = sorted(set(wanted) - set(available))
    if missing:
        raise SystemExit(f"Classes not found in CSV: {missing}\nAvailable: {available}")
    df = df[df["label_norm"].isin(wanted)]
    info = {
        "images_in_selected_classes": int(len(df)),
        "excluded_two_hand_class_rows": unsupported,
        "classes_selected": wanted,
    }

    df = df[df["n_hands"] >= 1]
    info["with_detected_hand"] = int(len(df))
    conflicts = df.groupby("md5")["label_norm"].nunique()
    bad_md5 = conflicts[conflicts > 1].index
    info["dropped_same_file_in_two_classes"] = int(df["md5"].isin(bad_md5).sum())
    df = df[~df["md5"].isin(bad_md5)]
    before = len(df)
    df = df.drop_duplicates(subset=["md5"])
    info["dropped_exact_duplicates"] = int(before - len(df))

    raw, labels, groups = [], [], []
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
        groups.append(str(row["phash"]))
    info["dropped_invalid_landmarks"] = skipped
    info["final_samples"] = len(labels)
    info["unique_perceptual_groups"] = len(set(groups))
    if not labels:
        raise ValueError("no valid hand-landmark rows remain after filtering")
    return np.array(raw), np.array(labels), np.array(groups), info


def make_pipeline(hidden, alpha, seed: int = SEED) -> Pipeline:
    return Pipeline([
        ("scale", StandardScaler()),
        ("mlp", MLPClassifier(hidden_layer_sizes=hidden, alpha=alpha, activation="relu", solver="adam",
                              max_iter=600, random_state=seed)),
    ])


def train(
    csv_path: Path,
    classes: list[str] | None,
    out_dir: Path,
    seed: int = SEED,
    verbose: bool = True,
    *,
    strict_catalogue: bool = True,
) -> dict:
    if classes is not None and (not classes or len({c.strip().casefold() for c in classes}) != len(classes)):
        raise ValueError("classes must be omitted or be a non-empty list of unique labels")
    raw, y, groups, info = load_dataset(csv_path, classes, strict_catalogue=strict_catalogue)
    counts = {label: int(np.sum(y == label)) for label in np.unique(y)}
    too_small = sorted(label for label in np.unique(y) if counts.get(label, 0) < 3)
    if too_small:
        raise ValueError(f"at least 3 valid samples per class are required for stratified train/validation/test splits: {too_small}")
    idx = np.arange(len(y))
    outer = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    trval, te = next(outer.split(idx, y, groups))
    inner = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=seed + 1)
    tr_rel, va_rel = next(inner.split(trval, y[trval], groups[trval]))
    tr, va = trval[tr_rel], trval[va_rel]
    if set(groups[tr]) & set(groups[va]) or set(groups[tr]) & set(groups[te]) or set(groups[va]) & set(groups[te]):
        raise RuntimeError("perceptually identical images leaked across train, validation or test splits")

    X = np.array([hand_features(r) for r in raw])
    X_mirror = np.array([mirrored_hand_features(r) for r in raw])
    X_train = np.vstack([X[tr], X_mirror[tr]])
    y_train = np.concatenate([y[tr], y[tr]])

    results = []
    best = None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=ConvergenceWarning)
        for cfg in GRID:
            pipe = make_pipeline(cfg["hidden_layer_sizes"], cfg["alpha"], seed=seed).fit(X_train, y_train)
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
        "class_count": len(labels_sorted),
        "strict_catalogue": strict_catalogue,
        "catalogue_digest": catalogue_digest() if strict_catalogue else None,
        "dataset_mapping_digest": dataset_mapping_digest() if strict_catalogue else None,
        "catalogue_class_count": len(asamyuta_names()) if strict_catalogue else None,
        "class_mapping": model_class_mapping(labels_sorted) if strict_catalogue else {},
        "preprocessing_configuration": {
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "input_hand_count": 1,
            "coordinates_per_hand": 63,
            "feature_count": len(feature_names()),
            "training_mirror_augmentation": True,
            "image_split_group": "64-bit-dct-perceptual-hash",
        },
        "low_confidence_raw_score_threshold": 0.5,
        "best_config": {"hidden_layer_sizes": list(best_cfg["hidden_layer_sizes"]), "alpha": best_cfg["alpha"]},
        "split_sizes": {"train": int(len(tr)), "train_with_mirrored": int(len(X_train)),
                        "validation": int(len(va)), "test": int(len(te)),
                        "train_perceptual_groups": int(len(set(groups[tr]))),
                        "validation_perceptual_groups": int(len(set(groups[va]))),
                        "test_perceptual_groups": int(len(set(groups[te])))},
        "dataset_report": info, "grid_results": results,
        "versions": {"python": platform.python_version(), "scikit-learn": sklearn.__version__,
                     "numpy": np.__version__, "pandas": pd.__version__},
        "limitations": ["Perceptual-hash group split; no performer ids, so performer generalisation is untested.",
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
    ap.add_argument("--classes", nargs="+", default=DEFAULT_CLASSES,
                    help="optional subset of catalogue class names/approved aliases (defaults to all represented single-hand classes)")
    args = ap.parse_args()
    train(args.csv, args.classes, args.out)


if __name__ == "__main__":
    main()
