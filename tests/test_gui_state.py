import pandas as pd

from biossbd import DataPoint, Evaluation
from biossbd.gui.state import add_indicators, apply_editor_changes, sync_indicator_rows, upsert_substance
from biossbd.gui.tables import SHARED, system_to_tables, tables_to_system
from conftest import CO, L


def test_apply_editor_changes():
    df = pd.DataFrame({"name": ["a", "b", "c"], "x": [1.0, 2.0, 3.0]})
    out = apply_editor_changes(df, {"edited_rows": {1: {"x": 20.0}, "0": {"name": "A"}},
                                    "added_rows": [{"name": "d", "x": 4.0}, {}], "deleted_rows": [2]})
    assert out["name"].tolist() == ["A", "b", "d"]
    assert out["x"].tolist() == [1.0, 20.0, 4.0]
    out2 = apply_editor_changes(df, {"edited_rows": {0: {"x": "n/a"}}})
    assert out2.loc[0, "x"] == "n/a"


def test_indicator_editor_keeps_index(acod):
    t = system_to_tables(acod)
    out = apply_editor_changes(t["indicators"], {"edited_rows": {2: {"Workers": 5}}}, keep_index=True)
    assert out.index.tolist() == acod.alternative_names
    assert out.loc[CO, "Workers"] == 5


def test_add_indicators_creates_specs_and_meta(acod):
    t = system_to_tables(acod)
    add_indicators(t, L, {"Climate change": DataPoint(value=0.02, unit="kg CO2 eq/MJ", source="openLCA",
                                                       evidence="modelled")}, "Environmental (LCA)", step=10)
    add_indicators(t, CO, {"Climate change": DataPoint(value=0.05, unit="kg CO2 eq/MJ", source="openLCA",
                                                        evidence="modelled")}, "Environmental (LCA)", step=10)
    s = tables_to_system(t)
    assert s.get_alternative(L).indicators["Climate change"].evidence == "modelled"
    spec = [x for x in s.indicator_specs if x.name == "Climate change"][0]
    assert spec.direction == "min" and spec.dimension == "Environmental (LCA)"
    ev = Evaluation.from_system(s.model_copy(update={"alternatives": [s.get_alternative(L), s.get_alternative(CO)]}))
    assert "Environmental (LCA)" in ev.dimensions


def test_sync_rows_after_new_alternative(acod):
    t = system_to_tables(acod)
    t["alternatives"] = pd.concat([t["alternatives"], pd.DataFrame([{"name": "New", "description": ""}])],
                                  ignore_index=True)
    sync_indicator_rows(t)
    assert "New" in t["indicators"].index
    s = tables_to_system(t)
    assert s.get_alternative("New").indicators == {}


def test_upsert_substance(acod):
    t = system_to_tables(acod)
    upsert_substance(t, {"name": "ethanol", "cas": "64-17-5", "h_codes": ["H225", "H319"], "flash_point_c": 13.0})
    upsert_substance(t, {"name": "Ethanol", "h_codes": ["H225"]})
    rows = t["substances"][t["substances"]["name"].str.lower() == "ethanol"]
    assert len(rows) == 1 and rows.iloc[0]["h_codes"] == "H225"
    s = tables_to_system(t)
    assert any(x.name == "Ethanol" for x in s.substances)
    assert rows.iloc[0]["alternative"] == SHARED
