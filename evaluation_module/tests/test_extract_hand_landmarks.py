"""Tests the extraction logic with a FAKE landmarker (no model file needed)."""
import csv
from types import SimpleNamespace

import cv2
import numpy as np

from data_prep.extract_hand_landmarks import HEADER, N_LANDMARKS, run


class FakeLandmarker:
    """Detects a hand only if the image is bright; returns known landmark values."""

    def detect(self, mp_image):
        arr = mp_image.numpy_view()
        if arr.mean() < 100:
            return SimpleNamespace(hand_landmarks=[], handedness=[])
        lms = [SimpleNamespace(x=0.5, y=0.25, z=0.1) for _ in range(N_LANDMARKS)]
        cat = SimpleNamespace(score=0.9, category_name="Right")
        return SimpleNamespace(hand_landmarks=[lms], handedness=[[cat]])


def _write(path, value, shape=(40, 80, 3)):
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(path.suffix, np.full(shape, value, dtype=np.uint8))
    assert ok
    buf.tofile(str(path))


def test_extraction_counts_pixels_and_missing_values(tmp_path):
    ds = tmp_path / "ds"
    _write(ds / "pathaka" / "a (1).png", 200)           # detected
    _write(ds / "pathaka" / "b.jpg", 200)               # detected
    _write(ds / "mushti" / "dark.png", 10)              # not detected, even after padding
    (ds / "mushti" / "broken.png").write_bytes(b"not an image")
    (ds / "mushti" / "notes.txt").write_text("ignored")

    out = tmp_path / "out" / "lm.csv"
    summary = run(ds, FakeLandmarker(), out, tmp_path / "out" / "failed.csv")

    assert summary["total_images"] == 4          # txt ignored
    assert summary["with_hand"] == 2
    assert summary["unreadable"] == 1
    assert summary["per_class"]["pathaka"] == (2, 2)
    assert summary["per_class"]["mushti"] == (2, 0)

    rows = list(csv.DictReader(open(out, encoding="utf-8")))
    assert list(rows[0].keys()) == HEADER
    good = next(r for r in rows if r["file"] == "a (1).png")
    # width 80, height 40 -> x = 0.5*80, y = 0.25*40, z = 0.1*80 (pixel units)
    assert float(good["h0_x0"]) == 40.0 and float(good["h0_y0"]) == 10.0 and float(good["h0_z0"]) == 8.0
    assert good["h1_x0"] == "" and good["n_hands"] == "1"       # missing hand is EMPTY, not 0
    dark = next(r for r in rows if r["file"] == "dark.png")
    assert dark["n_hands"] == "0" and dark["h0_x0"] == "" and dark["padded"] == "1"


def test_duplicates_are_counted(tmp_path):
    ds = tmp_path / "ds"
    _write(ds / "a" / "1.png", 200)
    _write(ds / "b" / "2.png", 200)   # identical bytes -> exact duplicate
    summary = run(ds, FakeLandmarker(), tmp_path / "lm.csv")
    assert summary["exact_duplicates"] == 1