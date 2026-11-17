import pandas as pd
import pytest
from pydantic import ValidationError

from biossbd import Evaluation
from biossbd.gui.tables import SHARED, system_to_tables, tables_to_dict, tables_to_system
from biossbd.scoping import hazard_register
from conftest import CO, L


def test_round_trip_preserves_system(acod):
    t = system_to_tables(acod)
    s2 = tables_to_system(t)
    assert s2.alternative_names == acod.alternative_names
    assert [u.name for u in s2.units] == [u.name for u in acod.units]
    assert len(s2.indicator_specs) == len(acod.indicator_specs)
    assert s2.get_alternative(L).indicators["Process stability"].source == "Table 6"
    assert hazard_register(s2, CO).equals(hazard_register(acod, CO))
    ev1, ev2 = Evaluation.from_system(acod), Evaluation.from_system(s2)
    pd.testing.assert_frame_equal(ev1.dimension_scores(), ev2.dimension_scores())
    assert len(s2.get_alternative(L).risks) == 7


def test_edit_indicator_changes_scores(acod):
    t = system_to_tables(acod)
    t["indicators"].loc[CO, "GHG score (grid intensity)"] = 5
    s2 = tables_to_system(t)
    ds = Evaluation.from_system(s2).dimension_scores((1, 5))
    assert ds.loc[CO, "Environmental"] == pytest.approx(3.5)


def test_add_unit_and_blank_rows_ignored(acod):
    t = system_to_tables(acod)
    new = pd.DataFrame([{"alternative": SHARED, "name": "Farm residue collection", "stage": "raw material",
                         "substances": "", "process_hazards": "bioaerosols", "inventory_kg": 0},
                        {"alternative": SHARED, "name": None}])
    t["units"] = pd.concat([t["units"], new], ignore_index=True)
    s2 = tables_to_system(t)
    assert "Farm residue collection" in [u.name for u in s2.units]


def test_invalid_edit_raises(acod):
    t = system_to_tables(acod)
    t["units"].loc[0, "stage"] = "nowhere"
    with pytest.raises(ValidationError):
        tables_to_system(t)


def test_dict_is_yaml_ready(acod):
    import yaml
    d = tables_to_dict(system_to_tables(acod))
    assert yaml.safe_load(yaml.safe_dump(d))["name"] == acod.name
