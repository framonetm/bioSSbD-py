import pytest

from biossbd import economics as ec
from biossbd import registry


def test_registry_covers_every_step():
    for step in registry.STEPS:
        assert registry.tools_for(step), step
    t = registry.status_table()
    assert {"tool", "licence", "status"} <= set(t.columns)
    assert registry.get("isi").status() == "ready"
    assert registry.get("openlca").licence == "MPL-2.0"


def test_npv_irr_consistency():
    inp = ec.CashFlowInput(capex=1000, opex=50, revenue=250, lifetime=10, discount_rate=0.08,
                           annual_output=100, output_unit="MWh")
    r = ec.cash_flow(inp)
    assert r.npv == pytest.approx(-1000 + 200 * (1 - 1.08 ** -10) / 0.08)
    assert ec.npv(r.irr, 1000, 200, 10) == pytest.approx(0, abs=1e-6)
    assert r.irr == pytest.approx(0.1510, abs=1e-3)
    assert r.simple_payback_years == pytest.approx(5.0)
    assert 5 < r.discounted_payback_years < 10
    assert r.levelised_cost == pytest.approx((1000 * ec.crf(0.08, 10) + 50) / 100)
    ind = ec.to_indicators(inp, r)
    assert ind["Internal rate of return"].unit == "%"


def test_unprofitable_project():
    r = ec.cash_flow(ec.CashFlowInput(capex=1000, opex=300, revenue=200, lifetime=10))
    assert r.npv < 0 and r.simple_payback_years is None and r.irr is None


def test_crf_zero_rate():
    assert ec.crf(0, 10) == 0.1


def test_biogas_presets_and_balance():
    from biossbd.examples import tea_presets_path
    presets = ec.load_presets(tea_presets_path())
    assert set(presets) == {"Lactoserum + manure", "Cacao husk + manure", "Coffee husk + manure"}
    p = presets["Lactoserum + manure"]
    res, cf = ec.biogas_chp(p)
    assert res.methane_m3_per_year == pytest.approx(3000 * 18.0 + 1500 * 18.4)
    assert res.electricity_mwh_per_year == pytest.approx(res.methane_m3_per_year * 9.94 * 0.35 / 1000)
    assert res.capex == pytest.approx(res.electrical_capacity_kwe * 6100)
    assert p.sources["capex"].startswith("IRENA")
    assert cf.annual_output == pytest.approx(res.electricity_mwh_per_year)
