"""Inventory per alternative. Unit impacts below are synthetic test values, not LCA data."""
from types import SimpleNamespace as R

import matplotlib
import pandas as pd
import pytest

matplotlib.use("Agg")

from biossbd import lca_inventory as inv  # noqa: E402
from biossbd.gui import plots  # noqa: E402

UNIT = {  # per reference unit
    "steel": [R(category="Climate change", unit="kg CO2 eq", amount=2.0), R(category="Acidification", unit="mol H+ eq", amount=0.01)],
    "lorry": [R(category="Climate change", unit="kg CO2 eq", amount=0.1), R(category="Acidification", unit="mol H+ eq", amount=0.001)],
    "grid": [R(category="Climate change", unit="kg CO2 eq", amount=0.5), R(category="Acidification", unit="mol H+ eq", amount=0.002)],
}


def _lines():
    df = pd.DataFrame([
        {"alternative": "A", "category": "material", "process": "steel", "amount": 10, "unit": "kg", "source": "BOM", "process_id": "steel"},
        {"alternative": "A", "category": "transport", "process": "lorry", "amount": 50, "unit": "t*km", "source": "", "process_id": "lorry"},
        {"alternative": "A", "category": "energy", "process": "grid", "amount": 4, "unit": "kWh", "source": "meter", "process_id": "grid"},
        {"alternative": "B", "category": "energy", "process": "grid", "amount": 20, "unit": "kWh", "source": "meter", "process_id": "grid"},
        {"alternative": "B", "category": "nonsense", "process": "steel", "amount": -1, "unit": "kg", "source": "avoided", "process_id": "steel"},
        {"alternative": None, "category": "material", "process": "", "amount": None, "unit": "", "source": "", "process_id": None},
    ])
    return inv.lines_from_frame(df)


def test_lines_parse_and_roundtrip():
    lines = _lines()
    assert len(lines) == 5  # blank row skipped
    assert lines[4].category == "other"
    assert lines[1].is_assumption and not lines[0].is_assumption
    assert inv.lines_from_frame(inv.lines_to_frame(lines)) == lines


def test_totals_are_linear_sums():
    contrib = inv.contributions(_lines(), UNIT)
    tot = inv.totals(contrib)
    # A: 10*2 + 50*0.1 + 4*0.5 = 27 ; B: 20*0.5 - 1*2 = 8
    assert tot.loc["A", "Climate change [kg CO2 eq]"] == pytest.approx(27.0)
    assert tot.loc["B", "Climate change [kg CO2 eq]"] == pytest.approx(8.0)
    assert tot.loc["A", "Acidification [mol H+ eq]"] == pytest.approx(0.1 + 0.05 + 0.008)
    by = inv.by_inventory_category(contrib, "Climate change")
    assert list(by.columns) == ["material", "transport", "energy", "other"]
    assert by.loc["A", "transport"] == pytest.approx(5.0) and by.loc["B", "material"] == 0.0


def test_missing_unit_impacts_raises():
    with pytest.raises(KeyError, match="lorry"):
        inv.contributions(_lines(), {"steel": UNIT["steel"], "grid": UNIT["grid"]})


def test_ghg_categories():
    names = ["Climate change", "Acidification", "Global warming potential (GWP100)", "Climate change - Fossil"]
    assert inv.ghg_categories(names) == ["Climate change", "Global warming potential (GWP100)", "Climate change - Fossil"]


def test_indicators_carry_provenance():
    ind = inv.to_indicators(_lines(), UNIT, "EF 3.1", impact_categories=["Climate change"])
    a, b = ind["A"]["Climate change"], ind["B"]["Climate change"]
    assert a.value == pytest.approx(27.0) and a.unit == "kg CO2 eq/FU"
    assert a.evidence == "assumed" and "ASSUMPTION" in a.source and "EF 3.1" in a.source
    assert b.evidence == "modelled" and "Acidification" not in ind["B"]


def test_inventory_plot():
    contrib = inv.contributions(_lines(), UNIT)
    fig = plots.inventory_contributions(inv.by_inventory_category(contrib, "Climate change"), unit="kg CO2 eq")
    assert fig.axes
    matplotlib.pyplot.close(fig)
