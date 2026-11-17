"""The toolbox must reproduce the published AcoD screening (Supplementary Material S2)."""
import numpy as np
import pandas as pd
import pytest

from biossbd import Evaluation, IndicatorSpec
from conftest import CA, CO, L

S2_DIMENSIONS = {
    "Risk & reliability": [4.39, 3.0, 2.0],
    "Inherent safety": [4.29, 3.0, 1.86],
    "Environmental": [4.0, 4.5, 1.5],
    "Economic": [4.67, 3.33, 2.33],
    "Social": [4.25, 3.25, 2.25],
}
S2_METHODS = {
    "weighted_sum": [4.318, 3.417, 1.988],
    "geometric_mean": [4.313, 3.376, 1.964],
    "topsis": [0.917, 0.581, 0.0],
    "promethee_ii": [0.8, 0.2, -1.0],
    "maximin": [4.0, 3.0, 1.5],
}


@pytest.fixture(scope="module")
def ev(acod):
    return Evaluation.from_system(acod)


def test_dimension_scores_match_s2(ev):
    ds = ev.dimension_scores((1, 5)).round(2)
    for d, vals in S2_DIMENSIONS.items():
        assert ds[d].tolist() == pytest.approx(vals, abs=0.01)


def test_aggregation_methods_match_s2(ev):
    cm = ev.compare_methods()
    for m, vals in S2_METHODS.items():
        assert cm[m].tolist() == pytest.approx(vals, abs=1e-3)


def test_environmental_weight_threshold_matches_s2(ev):
    assert ev.weight_threshold("Environmental") == pytest.approx(0.715, abs=0.002)


def test_dashboard_pareto_and_tradeoffs(ev):
    db = ev.dashboard()
    assert set(db.columns) >= {"indicator", "alternative", "value", "rank", "criterion"}
    gs = db[(db.indicator == "Gas-safety requirements") & (db.alternative == CO)].iloc[0]
    assert gs["criterion"] == "fail" and gs["rank"] == 3
    assert ev.pareto_front() == [L, CA]
    assert ev.dominance().loc[L, CO]
    t = ev.tradeoffs()
    assert ((t.best_a == CA) | (t.best_b == CA)).any()   # environment favours cacao


def test_robustness_scores_only(ev):
    r = ev.robustness(n=1500, seed=1)
    assert r.p_order(L, CA, CO) > 0.99
    assert r.rank_acceptability.loc[CO, "rank 3"] == 1.0


def test_robustness_with_weights(ev):
    r = ev.robustness(n=1500, perturb_weights=True, seed=1)
    assert r.p_order(L, CA, CO) > 0.9
    assert np.allclose(r.rank_acceptability.sum(axis=1), 1)


def test_ratio_indicators_and_ranges():
    vals = pd.DataFrame({"GHG": [10.0, 20.0], "NPV": [5.0, 1.0]}, index=["A", "B"])
    specs = [IndicatorSpec(name="GHG", dimension="env", direction="min"),
             IndicatorSpec(name="NPV", dimension="eco")]
    ev = Evaluation(vals, specs, ranges={("A", "GHG"): (8.0, 30.0)})
    assert ev.pareto_front() == ["A"]
    r = ev.robustness(n=500, seed=0)
    assert 0 < r.rank_acceptability.loc["A", "rank 1"] <= 1


def test_missing_spec_raises():
    with pytest.raises(KeyError):
        Evaluation(pd.DataFrame({"x": [1.0]}, index=["A"]), [])
