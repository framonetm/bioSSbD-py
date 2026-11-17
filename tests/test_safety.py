import pytest

from biossbd.safety import (ChemicalInput, ProcessInput, RiskItem, inherent_safety_index,
                            reliability_score, risk_table, safety_kpis)
from biossbd.safety import indices as ix
from conftest import L


def test_bands():
    assert ix.score_temperature(37) == 0
    assert ix.score_temperature(450) == 3
    assert ix.score_temperature(-10) == 1
    assert ix.score_pressure(1.0) == 0
    assert ix.score_pressure(0.2) == 1
    assert ix.score_pressure(30) == 2
    assert ix.score_inventory(0.6) == 0
    assert ix.score_inventory(12) == 2
    assert ix.score_explosiveness(4, 44) == 2   # H2S, range 40
    assert ix.score_toxicity(5) == 4             # H2S OEL 5 ppm
    assert ix.score_flammability(13) == 3        # ethanol
    assert ix.score_flammability(None, flammable_gas=True) == 4


def test_isi_worst_case_and_normalised():
    r = inherent_safety_index(
        [ChemicalInput(name="CH4", flammable_gas=True, lel_vol=5, uel_vol=15),
         ChemicalInput(name="H2S", flammable_gas=True, lel_vol=4, uel_vol=44, oel_ppm=5)],
        [ProcessInput(name="digester", inventory_t=0.15, temperature_c=37, pressure_bar=1.02)],
    )
    assert r.chemical["flammability"] == 4
    assert r.chemical["explosiveness"] == 2
    assert r.chemical["toxic_exposure"] == 4
    assert r.total == r.chemical_index + r.process_index == 10
    assert 0 < r.normalised < 1


def test_risk_item():
    r = RiskItem(name="Start-up instability", impact=5, likelihood=4, detectability=6)
    assert r.risk_index == 4.5 and r.risk_class == "Very High"
    assert r.product == 20
    assert r.rpn == 10 * 8 * 6


def test_risk_table_sorted(acod):
    t = risk_table(acod.get_alternative(L).risks)
    assert t.iloc[0]["risk"] == "Start-up instability"


def test_reliability_score_normalises_weights():
    s = {"a": 5, "b": 5, "c": 4, "d": 4, "e": 3}
    w = {"a": .20, "b": .25, "c": .20, "d": .15, "e": .10}  # sums to 0.90
    assert reliability_score(s, w) == pytest.approx(4.389, abs=1e-3)


def test_safety_kpis(acod):
    k = safety_kpis(acod, L)
    assert k.isi.total > 0
    assert "Biogas holder" in k.high_risk_units
    assert k.hazardous_inventory_kg >= 600
    assert k.top_risks[0]["risk"] == "Start-up instability"


def test_isi_discriminates_pretreatment(acod):
    """Steam-explosion pretreatment (coffee husk only) raises the pressure and equipment sub-indices."""
    isi = {a.name: safety_kpis(acod, a.name).isi for a in acod.alternatives}
    coffee = isi["Coffee husk + manure"]
    assert coffee.process["pressure"] == 1 and coffee.process["equipment"] == 3
    assert coffee.total == isi[L].total + 2
    assert isi[L].total == isi["Cacao husk + manure"].total
