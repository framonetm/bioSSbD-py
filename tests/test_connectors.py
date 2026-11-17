"""Connector tests with sample responses (offline). Live tests run only with BIOSSBD_ONLINE=1."""
import os
from types import SimpleNamespace

import pandas as pd
import pytest

from biossbd.connectors import openlca, owid, pubchem
from biossbd.connectors.http import ConnectorError

ONLINE = os.environ.get("BIOSSBD_ONLINE") == "1"

GHS_SAMPLE = {"Record": {"RecordNumber": 402, "Section": [{"TOCHeading": "Safety and Hazards", "Section": [
    {"TOCHeading": "Hazards Identification", "Section": [{"TOCHeading": "GHS Classification", "Information": [
        {"Name": "Pictogram(s)", "Value": {"StringWithMarkup": [{"String": " ", "Markup": []}]}},
        {"Name": "Signal", "Value": {"StringWithMarkup": [{"String": "Danger"}]}},
        {"Name": "GHS Hazard Statements", "Value": {"StringWithMarkup": [
            {"String": "H220 (100%): Extremely flammable gas [Danger Flammable gases]"},
            {"String": "H280 (93.5%): Contains gas under pressure; may explode if heated"},
            {"String": "H330 (100%): Fatal if inhaled [Danger Acute toxicity, inhalation]"},
            {"String": "H400 (88.2%): Very toxic to aquatic life"},
            {"String": "H335 (2.1%): May cause respiratory irritation"}]}},
        {"Name": "Precautionary Statement Codes", "Value": {"StringWithMarkup": [{"String": "P210, P260"}]}},
    ]}]}]}]}}


def test_parse_ghs_shares_and_signal():
    codes, signal, raw = pubchem.parse_ghs(GHS_SAMPLE)
    assert signal == "Danger"
    assert codes["H220"] == 100 and codes["H335"] == 2.1
    assert len(raw) == 5
    sd = pubchem.SafetyData(cid=402, name="Hydrogen Sulfide", h_codes=codes)
    assert sd.accepted_codes(min_share=10) == ["H220", "H280", "H330", "H400"]
    sub = sd.to_substance(role="emission", min_share=10)
    assert sub["name"] == "hydrogen sulfide" and "H335" not in sub["h_codes"]


def test_parse_ghs_combined_codes_and_empty():
    d = {"Information": [{"Name": "GHS Hazard Statements",
                          "Value": {"StringWithMarkup": [{"String": "H302+H312: Harmful"}, {"String": "H360FD"}]}}]}
    codes, _, _ = pubchem.parse_ghs(d)
    assert set(codes) == {"H302", "H312", "H360"}
    assert pubchem.parse_ghs(None) == ({}, "", [])


def test_parse_search_payloads():
    props = {"PropertyTable": {"Properties": [
        {"CID": 297, "MolecularFormula": "CH4", "MolecularWeight": "16.043", "Title": "Methane"}]}}
    c = pubchem.parse_properties(props)[0]
    assert (c.cid, c.name, c.formula, c.molecular_weight) == (297, "Methane", "CH4", 16.043)
    assert c.url.endswith("/297")
    syn = {"InformationList": {"Information": [{"CID": 297, "Synonym": ["methane", "Marsh gas", "74-82-8"]}]}}
    assert pubchem.parse_cas(syn) == "74-82-8"
    assert pubchem.parse_autocomplete({"dictionary_terms": {"compound": ["methane", "methanol"]}}) == ["methane", "methanol"]


def test_parse_physical_data():
    assert pubchem.parse_flash_point(["-306 °F (-188 °C) (closed cup)"]) == -188
    assert pubchem.parse_flash_point(["55 °F"]) == pytest.approx(12.8, abs=0.1)
    assert pubchem.parse_flash_point(["not applicable"]) is None
    assert pubchem.parse_explosive_limits(["Lower flammable limit: 4.0% by volume; Upper flammable limit: 44% by volume"]) == (4.0, 44.0)
    assert pubchem.parse_explosive_limits(["5-15%"]) == (5.0, 15.0)
    assert pubchem.parse_oel_ppm(["TLV-TWA: 1 ppm; STEL 5 ppm"]) == 1.0
    assert pubchem.parse_oel_ppm(["no data"]) is None


def test_owid_latest_by_country():
    df = pd.DataFrame({"Entity": ["Colombia", "Colombia", "Brazil", "World"],
                       "Code": ["COL", "COL", "BRA", "OWID_WRL"],
                       "Year": [2023, 2024, 2024, 2024],
                       "Carbon intensity of electricity - gCO2/kWh": [210.0, 207.0, 62.0, 470.0]})
    out = owid.latest_by_country(df)
    assert list(out.country) == ["Brazil", "Colombia"]
    assert out.set_index("country").loc["Colombia", "value"] == 207.0


class _Ref(SimpleNamespace):
    pass


class FakeSchema:
    class ProductSystem: ...
    class ImpactMethod: ...
    class Process: ...
    class RefType:
        ProductSystem = "ProductSystem"
        Process = "Process"
        ImpactMethod = "ImpactMethod"
    Ref = _Ref

    class CalculationSetup(SimpleNamespace):
        pass


class FakeResult:
    disposed = False
    def wait_until_ready(self): return self
    def get_total_impacts(self):
        return [SimpleNamespace(impact_category=SimpleNamespace(name="Climate change", ref_unit="kg CO2 eq"), amount=2.5),
                SimpleNamespace(impact_category=SimpleNamespace(name="Acidification", ref_unit="mol H+ eq"), amount=0.01)]
    def dispose(self): FakeResult.disposed = True


class FakeClient:
    def get_descriptors(self, cls):
        names = {"ProductSystem": ["Biogas, CHP", "AD plant"], "ImpactMethod": ["EF 3.1"],
                 "Process": ["anaerobic digestion of manure", "electricity, grid"]}[cls.__name__]
        return [_Ref(id=f"id-{n}", name=n) for n in names]
    def calculate(self, setup):
        assert setup.target.ref_type == "ProductSystem"
        return FakeResult()
    def create_product_system(self, ref):
        return _Ref(id="ps-new", name="new system")


def test_openlca_wrapper_with_fake_client():
    ol = openlca.OpenLCA(client=FakeClient(), schema=FakeSchema)
    assert ol.ping()
    assert [p.name for p in ol.product_systems()] == ["AD plant", "Biogas, CHP"]
    assert [p.name for p in ol.processes("digestion")] == ["anaerobic digestion of manure"]
    res = ol.calculate("id-AD plant", "id-EF 3.1", amount=1.0)
    assert res[0].category == "Climate change" and res[0].amount == 2.5
    assert FakeResult.disposed
    ind = openlca.to_indicators(res, source="openLCA: AD plant / EF 3.1")
    assert ind["Climate change"].unit == "kg CO2 eq" and ind["Climate change"].evidence == "modelled"
    assert ol.create_product_system("id-x").id == "ps-new"


def test_openlca_unit_impacts_and_reference():
    class ProcessTarget(FakeClient):
        def calculate(self, setup):
            assert setup.impact_method.ref_type == "ImpactMethod"
            assert setup.amount == 1.0
            self.target = setup.target.ref_type
            return FakeResult()
        def get(self, cls, uid):
            unit = SimpleNamespace(name="t*km")
            return SimpleNamespace(exchanges=[
                SimpleNamespace(is_quantitative_reference=False, flow=SimpleNamespace(name="diesel"), unit=unit),
                SimpleNamespace(is_quantitative_reference=True, flow=SimpleNamespace(name="transport, lorry"),
                                unit=unit)])
    cl = ProcessTarget()
    ol = openlca.OpenLCA(client=cl, schema=FakeSchema)
    assert ol.unit_impacts("p1", "m1")[0].amount == 2.5 and cl.target == "Process"
    assert ol.reference("p1") == ("transport, lorry", "t*km")

    class NoProcessTarget(ProcessTarget):
        def calculate(self, setup):
            if setup.target.ref_type == "Process":
                raise RuntimeError("target type not supported")
            return super().calculate(setup)
    cl = NoProcessTarget()
    assert openlca.OpenLCA(client=cl, schema=FakeSchema).unit_impacts("p1", "m1")[1].category == "Acidification"
    assert cl.target == "ProductSystem"  # fell back to a product system created from the process


def test_openlca_unreachable_raises():
    class Down(FakeClient):
        def get_descriptors(self, cls):
            raise OSError("connection refused")
    ol = openlca.OpenLCA(client=Down(), schema=FakeSchema)
    assert not ol.ping()
    with pytest.raises(ConnectorError):
        ol.product_systems()


@pytest.mark.skipif(not ONLINE, reason="set BIOSSBD_ONLINE=1 to run live PubChem tests")
def test_pubchem_live():
    cands = pubchem.search("hydrogen sulfide")
    assert cands and cands[0].cid == 402
    sd = pubchem.safety_data(402, cands[0].name)
    assert "H220" in sd.h_codes and "H330" in sd.h_codes


@pytest.mark.skipif(not ONLINE, reason="set BIOSSBD_ONLINE=1 to run live OWID tests")
def test_owid_live():
    df = owid.grid_carbon_intensity()
    assert "Colombia" in set(df.country)
