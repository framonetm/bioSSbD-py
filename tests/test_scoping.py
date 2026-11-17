import pytest
from pydantic import ValidationError

from biossbd import SSbDSystem, hazard_register, receptor_matrix, safety_matrix, scoping_gaps
from conftest import CO, L


def test_load_example(acod):
    assert acod.alternative_names == [L, "Cacao husk + manure", CO]
    assert len(acod.indicator_specs) == 21


def test_safety_matrix_covers_all_stages(acod):
    m = safety_matrix(acod, CO)
    assert list(m.index) == [s.name for s in acod.stages]
    assert m.loc["storage", "physical"] == 5           # methane in the gas holder
    assert m.loc["feedstock handling", "biological"] == 3  # bioaerosols, mycotoxins
    assert (m.loc["raw material"] == 0).all()           # no hazard declared yet


def test_alternative_specific_units(acod):
    reg_l = hazard_register(acod, L)
    reg_co = hazard_register(acod, CO)
    assert "Whey buffer tank" in set(reg_l["unit"])
    assert "mycotoxins" in set(reg_co["category"])
    assert "mycotoxins" not in set(reg_l["category"])


def test_receptors(acod):
    r = receptor_matrix(acod, CO)
    assert r.loc["feedstock handling", "workers"] >= 4
    assert r.loc["end of life", "soil"] >= 4


def test_gaps_flag_raw_material(acod):
    g = scoping_gaps(acod)
    assert list(g["stage"]) == ["raw material"]
    assert g.iloc[0]["aspect"] == "safety"


def test_gap_high_priority_when_hazard_unassessed():
    s = SSbDSystem.model_validate({
        "name": "t", "substances": [{"name": "methane"}],
        "units": [{"name": "holder", "stage": "storage", "substances": ["methane"]}],
    })
    g = scoping_gaps(s)
    row = g[(g.stage == "storage") & (g.aspect == "safety")].iloc[0]
    assert row.priority == "high"


def test_invalid_references_rejected():
    with pytest.raises(ValidationError):
        SSbDSystem.model_validate({"name": "t", "units": [{"name": "u", "stage": "nowhere"}]})
    with pytest.raises(ValidationError):
        SSbDSystem.model_validate({"name": "t", "units": [{"name": "u", "stage": "processing",
                                                            "substances": ["xylene"]}]})
    with pytest.raises(ValidationError):
        SSbDSystem.model_validate({"name": "t", "units": [{"name": "u", "stage": "processing",
                                                            "process_hazards": ["dragons"]}]})


def test_unknown_substance_without_codes_is_allowed():
    s = SSbDSystem.model_validate({
        "name": "t", "substances": [{"name": "lignin"}],
        "units": [{"name": "u", "stage": "processing", "substances": ["lignin"]}],
    })
    assert hazard_register(s).empty
