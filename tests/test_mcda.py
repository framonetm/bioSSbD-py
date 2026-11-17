import numpy as np
import pytest

from biossbd import mcda


def test_weights_normalised():
    X = np.array([[1, 2], [2, 1]], float)
    assert mcda.weighted_sum(X, [2, 2]).tolist() == [1.5, 1.5]


def test_maximin_and_geometric():
    X = np.array([[5, 1], [3, 3]], float)
    assert mcda.maximin(X).tolist() == [1, 3]
    assert mcda.geometric_mean(X, [1, 1])[1] > mcda.geometric_mean(X, [1, 1])[0]
    with pytest.raises(ValueError):
        mcda.geometric_mean(np.array([[0, 1]]), [1, 1])


def test_unknown_method():
    with pytest.raises(KeyError):
        mcda.aggregate(np.ones((2, 2)), [1, 1], "electre")
