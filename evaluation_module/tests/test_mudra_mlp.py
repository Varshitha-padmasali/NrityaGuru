"""Software tests on SYNTHETIC data. They prove the code works, NOT that real mudras are recognised."""
import numpy as np
import pandas as pd
import pytest

from data_prep.extract_hand_landmarks import HEADER
from mudra_mlp.features import FeatureError, hand_features, mirrored_hand_features
from mudra_mlp.predict import load_bundle, predict_hand
from mudra_mlp.train import train


def template(seed):
    rng = np.random.default_rng(seed)
    pts = rng.normal(size=(21, 3)) * 20
    pts[9] += [0, -60, 0]          # make sure wrist -> middle base is not tiny
    return pts


def synthetic_csv(path, n_classes=3, per_class=30):
    rows, rng = [], np.random.default_rng(0)
    for c in range(n_classes):
        base = template(100 + c)
        for k in range(per_class):
            pts = (base + rng.normal(scale=1.5, size=base.shape)) * rng.uniform(0.8, 1.2) + rng.uniform(-50, 50, 3)
            row = dict.fromkeys(HEADER, "")
            row.update(label=f"class{c}", file=f"{c}_{k}.png", md5=f"md5_{c}_{k}", phash=f"{c}_{k:016d}", width=100, height=100,
                       padded=0, n_hands=1, h0_side="Right", h0_score=0.9)
            for i in range(21):
                row[f"h0_x{i}"], row[f"h0_y{i}"], row[f"h0_z{i}"] = pts[i]
            rows.append(row)
    pd.DataFrame(rows, columns=HEADER).to_csv(path, index=False)


def test_feature_length_and_invariance():
    pts = template(1)
    f = hand_features(pts)
    assert f.shape == (78,)
    moved_scaled = pts * 3.0 + np.array([40, -10, 5])
    assert np.allclose(f, hand_features(moved_scaled))


def test_mirrored_features_match_flipped_input():
    pts = template(2)
    flipped = pts * np.array([-1, 1, 1])
    assert np.allclose(mirrored_hand_features(pts), hand_features(flipped))


@pytest.mark.parametrize("bad", [np.zeros(62), np.full(63, np.nan), np.zeros(63), "abc", np.full(63, np.inf)])
def test_bad_landmarks_rejected(bad):
    with pytest.raises(FeatureError):
        hand_features(bad)


def test_train_save_load_predict(tmp_path):
    csv_path = tmp_path / "lm.csv"
    synthetic_csv(csv_path)
    metrics = train(csv_path, ["class0", "class1", "class2"], tmp_path / "models", verbose=False,
                    strict_catalogue=False)
    assert metrics["test_accuracy"] > 0.9
    assert (tmp_path / "models" / "mudra_mlp.joblib").exists()
    assert (tmp_path / "models" / "mudra_mlp_metrics.json").exists()
    bundle = load_bundle(tmp_path / "models" / "mudra_mlp.joblib", allow_non_catalogue=True)
    assert bundle["metadata"]["split_sizes"]["train_perceptual_groups"] == bundle["metadata"]["split_sizes"]["train"]
    out = predict_hand(bundle, template(100 + 1))      # a class1-shaped hand
    assert out["status"] == "success" and out["predicted_label"] == "class1"
    assert 0.0 <= out["confidence"] <= 1.0


def test_prediction_distinguishes_unavailable_and_low_confidence(tmp_path):
    csv_path = tmp_path / "lm.csv"
    synthetic_csv(csv_path)
    train(csv_path, ["class0", "class1", "class2"], tmp_path / "models", verbose=False,
          strict_catalogue=False)
    bundle = load_bundle(tmp_path / "models" / "mudra_mlp.joblib", allow_non_catalogue=True)
    unavailable = predict_hand(bundle, template(100), expected_label="not-trained")
    assert unavailable["status"] == "class_unavailable"
    bundle["metadata"]["low_confidence_raw_score_threshold"] = 1.01
    low = predict_hand(bundle, template(101))
    assert low["status"] == "low_confidence"
    assert low["predicted_label"] is None and low["candidate_label"]


def test_predict_invalid_input_returns_status(tmp_path):
    csv_path = tmp_path / "lm.csv"
    synthetic_csv(csv_path)
    train(csv_path, ["class0", "class1", "class2"], tmp_path / "m", verbose=False,
          strict_catalogue=False)
    bundle = load_bundle(tmp_path / "m" / "mudra_mlp.joblib", allow_non_catalogue=True)
    assert predict_hand(bundle, np.zeros(10))["status"] == "invalid_input"


def test_unknown_class_is_reported(tmp_path):
    csv_path = tmp_path / "lm.csv"
    synthetic_csv(csv_path)
    with pytest.raises(SystemExit):
        train(csv_path, ["class0", "nope"], tmp_path / "m", verbose=False, strict_catalogue=False)
