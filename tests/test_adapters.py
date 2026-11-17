"""Adapter tests run only where the optional libraries are installed."""
import pytest

from biossbd.dataquality import DataPoint, as_datapoint, summarise


def test_datapoint():
    d = as_datapoint({"value": 2, "low": 1, "high": 3, "evidence": "measured"})
    assert d.has_range and d.quality == 5
    assert as_datapoint(4).evidence == "assumed"
    with pytest.raises(ValueError):
        DataPoint(value=1, low=3, high=2)
    q = summarise([d, as_datapoint(4)])
    assert q.n == 2 and q.share_with_range == 0.5


def test_tea_adapter_with_dummy_object():
    from biossbd.sustainability.qsdsan_adapter import indicators_from_tea

    class FakeTEA:
        NPV = 1e6
        EAC = 2e5
        def IRR(self):
            return 0.12
    out = indicators_from_tea(FakeTEA())
    assert out["NPV"].value == 1e6 and out["IRR"].value == 0.12
    assert "TCI" not in out


def test_qsdsan_lca_adapter_with_dummy_lca():
    pytest.importorskip("qsdsan")
    from biossbd.sustainability import indicators_from_qsdsan

    class FakeLCA:
        indicators = ()
        def get_total_impacts(self):
            return {"GlobalWarming": 2000.0}
    out = indicators_from_qsdsan(FakeLCA(), functional_unit=1000)
    assert out["GlobalWarming"].value == 2.0


def test_qsdsan_import_smoke():
    qs = pytest.importorskip("qsdsan")
    assert hasattr(qs, "LCA")


def test_brightway_import_smoke():
    pytest.importorskip("bw2data")
    pytest.importorskip("bw2calc")
    import bw2data as bd
    assert hasattr(bd, "projects")
