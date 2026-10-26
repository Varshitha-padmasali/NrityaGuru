"""Tests for mudra_eval.build_result using SYNTHETIC hands. They check the software and the
contract format, not real mudra recognition."""
import numpy as np
import pandas as pd
import pytest

pydantic = pytest.importorskip("pydantic")
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from data_prep.extract_hand_landmarks import HEADER
from mudra_eval.build_result import build_evaluation_result
from mudra_mlp.predict import load_bundle
from mudra_mlp.train import train

# ---- COPY of the backend contract v1.0 (backend/app/schemas/evaluation.py), used only to validate output ----
SESSION_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$"
REFERENCE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{1,79}$"
LABEL_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9 _.:+-]{0,79}$"


class FrameInterval(BaseModel):
    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=0)
    start_time_s: float | None = Field(default=None, ge=0)
    end_time_s: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _ordered(self):
        if self.end_frame < self.start_frame:
            raise ValueError("end_frame must not be before start_frame")
        return self


class PredictedLabel(BaseModel):
    label: str = Field(pattern=LABEL_PATTERN)
    confidence: float | None = Field(default=None, ge=0, le=1)
    interval: FrameInterval | None = None


class DtwSummary(BaseModel):
    distance: float = Field(ge=0)
    normalized_distance: float | None = Field(default=None, ge=0)
    threshold: float | None = Field(default=None, ge=0)
    within_threshold: bool | None = None
    reference_sequence_id: str | None = Field(default=None, pattern=REFERENCE_ID_PATTERN)
    feature_schema_version: str | None = Field(default=None, max_length=40)


class Deviation(BaseModel):
    deviation_id: str = Field(pattern=REFERENCE_ID_PATTERN)
    kind: Literal["finger", "joint", "hand_pose", "timing", "posture", "other"]
    body_part: str | None = Field(default=None, max_length=60)
    description: str = Field(min_length=1, max_length=300)
    measured_value: float | None = None
    reference_value: float | None = None
    unit: str | None = Field(default=None, max_length=20)
    severity: Literal["minor", "moderate", "major"] | None = None
    interval: FrameInterval | None = None
    source_module: Literal["mlp", "dtw", "landmark_rules"] | None = None


class LandmarkQuality(BaseModel):
    hand_detection_rate: float | None = Field(default=None, ge=0, le=1)
    pose_detection_rate: float | None = Field(default=None, ge=0, le=1)
    frames_total: int | None = Field(default=None, ge=0)
    frames_analysed: int | None = Field(default=None, ge=0)
    reliable: bool | None = None
    notes: list[str] = Field(default_factory=list, max_length=10)


class EvaluationResult(BaseModel):
    schema_version: str = Field(pattern=r"^\d+\.\d+$")
    session_id: str = Field(pattern=SESSION_ID_PATTERN)
    reference_movement_id: str | None = Field(default=None, pattern=REFERENCE_ID_PATTERN)
    reference_mudra_id: str | None = Field(default=None, pattern=REFERENCE_ID_PATTERN)
    expected_labels: list[str] = Field(default_factory=list, max_length=20)
    predicted_labels: list[PredictedLabel] = Field(default_factory=list, max_length=100)
    dtw: DtwSummary | None = None
    deviations: list[Deviation] = Field(default_factory=list, max_length=50)
    landmark_quality: LandmarkQuality | None = None
    warnings: list[str] = Field(default_factory=list, max_length=20)
    mlp_model_version: str | None = Field(default=None, max_length=60)
    created_at: datetime | None = None
    is_mock: bool = False

    @model_validator(mode="after")
    def _exactly_one_reference(self):
        if (self.reference_movement_id is None) == (self.reference_mudra_id is None):
            raise ValueError("exactly one of reference_movement_id / reference_mudra_id is required")
        return self


# ---- synthetic data helpers ----
def template(seed):
    rng = np.random.default_rng(seed)
    pts = rng.normal(size=(21, 3)) * 20
    pts[9] += [0, -60, 0]
    return pts


def synthetic_csv(path, n_classes=3, per_class=30):
    rows, rng = [], np.random.default_rng(0)
    for c in range(n_classes):
        base = template(100 + c)
        for k in range(per_class):
            pts = (base + rng.normal(scale=1.5, size=base.shape)) * rng.uniform(0.8, 1.2) + rng.uniform(-50, 50, 3)
            row = dict.fromkeys(HEADER, "")
            row.update(label=f"class{c}", file=f"{c}_{k}.png", md5=f"md5_{c}_{k}", width=100, height=100,
                       padded=0, n_hands=1, h0_side="Right", h0_score=0.9)
            for i in range(21):
                row[f"h0_x{i}"], row[f"h0_y{i}"], row[f"h0_z{i}"] = pts[i]
            rows.append(row)
    pd.DataFrame(rows, columns=HEADER).to_csv(path, index=False)


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    d = tmp_path_factory.mktemp("m")
    synthetic_csv(d / "lm.csv")
    train(d / "lm.csv", ["class0", "class1", "class2"], d / "models", verbose=False)
    return load_bundle(d / "models" / "mudra_mlp.joblib")


def frames_of(cls, n, seed=0):
    rng = np.random.default_rng(seed)
    return [(template(100 + cls) + rng.normal(scale=1.0, size=(21, 3))).reshape(-1) for _ in range(n)]


def build(bundle, learner, reference=None, expected=("class1",), **kw):
    return build_evaluation_result(
        session_id="test-session-1", learner_frames=learner,
        reference_frames=reference if reference is not None else frames_of(1, 15, seed=9),
        bundle=bundle, expected_labels=list(expected), reference_mudra_id="mudra_test",
        reference_sequence_id="TEST-SEQ-1", **kw)


def test_correct_performance_is_valid_and_has_no_deviation(bundle):
    r = build(bundle, frames_of(1, 25))
    EvaluationResult.model_validate(r)
    assert [p["label"] for p in r["predicted_labels"]] == ["class1"]
    assert r["predicted_labels"][0]["interval"] == {"start_frame": 0, "end_frame": 24, "start_time_s": None, "end_time_s": None}
    assert r["deviations"] == []
    assert r["dtw"]["threshold"] is None and r["dtw"]["within_threshold"] is None
    assert r["landmark_quality"]["reliable"] is True and r["is_mock"] is False


def test_wrong_mudra_gives_label_deviation_and_larger_dtw(bundle):
    good = build(bundle, frames_of(1, 25))
    bad = build(bundle, frames_of(2, 25))
    EvaluationResult.model_validate(bad)
    assert [p["label"] for p in bad["predicted_labels"]] == ["class2"]
    assert len(bad["deviations"]) == 1 and bad["deviations"][0]["source_module"] == "mlp"
    assert bad["deviations"][0]["body_part"] is None          # no finger-level claim
    assert bad["dtw"]["normalized_distance"] > 5 * good["dtw"]["normalized_distance"]


def test_slower_performance_still_aligns(bundle):
    ref = frames_of(1, 10, seed=3)
    slow = [f for f in frames_of(1, 10, seed=4) for _ in range(3)]      # 3x slower
    r = build(bundle, slow, reference=ref)
    assert r["dtw"]["normalized_distance"] < 1.0 and r["deviations"] == []


def test_missing_hands_are_dropped_and_flagged(bundle):
    learner = frames_of(1, 20)
    for i in range(0, 20, 2):
        learner[i] = None
    r = build(bundle, learner)
    EvaluationResult.model_validate(r)
    q = r["landmark_quality"]
    assert q["frames_total"] == 20 and q["frames_analysed"] == 10 and q["reliable"] is False and q["notes"]
    assert len(r["predicted_labels"]) == 10     # gaps break segments


def test_no_usable_frames_still_returns_valid_result(bundle):
    r = build(bundle, [None] * 10)
    EvaluationResult.model_validate(r)
    assert r["predicted_labels"] == [] and r["dtw"] is None
    assert r["landmark_quality"]["reliable"] is False


def test_needs_exactly_one_reference_id(bundle):
    kw = dict(session_id="test-session-1", learner_frames=frames_of(1, 5), reference_frames=frames_of(1, 5),
              bundle=bundle, expected_labels=["class1"])
    with pytest.raises(ValueError):
        build_evaluation_result(**kw)
    with pytest.raises(ValueError):
        build_evaluation_result(**kw, reference_mudra_id="a1", reference_movement_id="b1")