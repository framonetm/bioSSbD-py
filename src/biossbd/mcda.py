"""Multi-criteria aggregation rules.

All functions take a matrix ``X`` (alternatives x criteria) in which *higher is
better* and a weight vector ``w`` that sums to one, and return one score per
alternative (higher = preferred).

The revised EC SSbD framework favours a transparent, non-aggregated reading
of safety and sustainability results. Use these rules as a sensitivity check
alongside :meth:`biossbd.evaluation.Evaluation.dashboard`, not instead of it.
Compensatory rules (weighted sum, TOPSIS) let a good score offset a bad one;
partially or non-compensatory rules (geometric mean, PROMETHEE II, maximin)
limit that.
"""
from __future__ import annotations

import numpy as np

COMPENSATORY = {"weighted_sum": "full", "topsis": "full", "geometric_mean": "partial",
                "promethee_ii": "partial", "maximin": "none"}


def _check(X: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    X = np.asarray(X, float)
    w = np.asarray(w, float)
    if X.ndim != 2 or X.shape[1] != w.size:
        raise ValueError("X must be (n_alternatives, n_criteria) and w of length n_criteria")
    if np.any(w < 0):
        raise ValueError("weights must be non-negative")
    return X, w / w.sum()


def weighted_sum(X, w) -> np.ndarray:
    X, w = _check(X, w)
    return X @ w


def geometric_mean(X, w) -> np.ndarray:
    X, w = _check(X, w)
    if np.any(X <= 0):
        raise ValueError("geometric mean requires strictly positive scores")
    return np.exp(np.log(X) @ w)


def topsis(X, w) -> np.ndarray:
    X, w = _check(X, w)
    norm = np.sqrt((X ** 2).sum(0))
    norm[norm == 0] = 1.0
    V = X / norm * w
    pos, neg = V.max(0), V.min(0)
    dp = np.sqrt(((V - pos) ** 2).sum(1))
    dn = np.sqrt(((V - neg) ** 2).sum(1))
    denom = dp + dn
    denom[denom == 0] = 1.0
    return dn / denom


def promethee_ii(X, w) -> np.ndarray:
    """PROMETHEE II net flows with the usual (strict) preference function."""
    X, w = _check(X, w)
    n = X.shape[0]
    if n < 2:
        return np.zeros(n)
    phi = np.zeros(n)
    for a in range(n):
        for b in range(n):
            if a != b:
                phi[a] += (w * (X[a] > X[b])).sum() - (w * (X[b] > X[a])).sum()
    return phi / (n - 1)


def maximin(X, w=None) -> np.ndarray:
    """Score of the worst criterion (weights ignored)."""
    X = np.asarray(X, float)
    return X.min(1)


METHODS = {
    "weighted_sum": weighted_sum,
    "geometric_mean": geometric_mean,
    "topsis": topsis,
    "promethee_ii": promethee_ii,
    "maximin": maximin,
}


def aggregate(X, w, method: str = "weighted_sum") -> np.ndarray:
    if method not in METHODS:
        raise KeyError(f"Unknown method '{method}'. Available: {sorted(METHODS)}")
    return METHODS[method](X, w)
