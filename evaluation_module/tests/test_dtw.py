import numpy as np
import pytest

from sequence.dtw import DTWInputError, dtw


def test_identical_sequences_have_zero_cost():
    seq = np.random.default_rng(0).normal(size=(20, 5))
    result = dtw(seq, seq)
    assert result.raw_cost == pytest.approx(0.0)
    assert result.path == [(i, i) for i in range(20)]


def test_hand_computed_example():
    # ref 0,2 vs learner 1: both ref frames must match the single learner frame -> 1 + 1
    result = dtw([[0.0], [2.0]], [[1.0]])
    assert result.raw_cost == pytest.approx(2.0)
    assert result.path == [(0, 0), (1, 0)]


def test_same_shape_at_different_speed_is_cheap_and_different_shape_is_not():
    t_ref = np.linspace(0, 2 * np.pi, 50)
    t_slow = np.linspace(0, 2 * np.pi, 75)  # same movement, slower
    ref = np.sin(t_ref)[:, None]
    slow = np.sin(t_slow)[:, None]
    other = np.cos(3 * t_slow)[:, None]     # a genuinely different movement
    same = dtw(ref, slow)
    diff = dtw(ref, other)
    assert same.reference_length == 50 and same.learner_length == 75
    assert same.normalized_cost < 0.1 * diff.normalized_cost


def test_different_lengths_are_handled():
    result = dtw(np.zeros((3, 2)), np.zeros((10, 2)))
    assert result.raw_cost == pytest.approx(0.0)
    assert result.path[0] == (0, 0) and result.path[-1] == (2, 9)


def test_path_is_monotonic_with_valid_steps():
    rng = np.random.default_rng(1)
    result = dtw(rng.normal(size=(12, 3)), rng.normal(size=(17, 3)))
    assert result.path[0] == (0, 0)
    assert result.path[-1] == (11, 16)
    for (i0, j0), (i1, j1) in zip(result.path, result.path[1:]):
        assert (i1 - i0, j1 - j0) in {(1, 0), (0, 1), (1, 1)}


def test_normalized_cost_is_raw_over_path_length():
    rng = np.random.default_rng(2)
    r = dtw(rng.normal(size=(6, 2)), rng.normal(size=(8, 2)))
    assert r.normalized_cost == pytest.approx(r.raw_cost / len(r.path))


def test_result_is_reproducible():
    rng = np.random.default_rng(3)
    a, b = rng.normal(size=(9, 4)), rng.normal(size=(11, 4))
    assert dtw(a, b) == dtw(a, b)


@pytest.mark.parametrize("bad", [[], np.empty((0, 3)), np.empty((3, 0))])
def test_empty_sequences_rejected(bad):
    with pytest.raises(DTWInputError):
        dtw(bad, np.ones((4, 3)))
    with pytest.raises(DTWInputError):
        dtw(np.ones((4, 3)), bad)


def test_dimension_mismatch_rejected():
    with pytest.raises(DTWInputError, match="dimension"):
        dtw(np.ones((4, 3)), np.ones((4, 2)))


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_nan_and_inf_rejected(value):
    bad = np.ones((4, 3))
    bad[2, 1] = value
    with pytest.raises(DTWInputError, match="NaN or infinite"):
        dtw(bad, np.ones((4, 3)))


def test_one_dimensional_input_rejected():
    with pytest.raises(DTWInputError, match="2-D"):
        dtw([1.0, 2.0, 3.0], [[1.0], [2.0]])