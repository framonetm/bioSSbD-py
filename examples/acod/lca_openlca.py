"""Climate-change LCA of the AcoD worked example with openLCA 2 and USLCI.

Reproduces ``acod_lca_results.yaml``. Requirements:

- openLCA 2 with the USLCI database (v1.2026-09.0) open and the IPC server on port 8080;
- ``pip install "biossbd[openlca]"``.

What it does (all objects are created in a ``bioSSbD`` folder of the open database and are
overwritten, not duplicated, on re-runs because their UUIDs are fixed):

1. Creates the method "bioSSbD GWP100 for USLCI (IPCC AR6 subset)". USLCI uses the Federal
   LCA Commons elementary-flow list (FEDEFL), and the generic openLCA LCIA method pack does
   not characterise those flows (see docs/openlca_setup.md). The method maps the AR6 GWP100
   factors of the three main greenhouse gases to the FEDEFL air-emission flows: CO2 fossil 1,
   CH4 fossil 29.8, CH4 biogenic 27.0, N2O 273. Biogenic CO2 is not counted.
2. Creates one foreground process per alternative for one year of operation: net electricity
   from the CHP (reference output), co-substrate delivery by truck (USLCI, t*km) and fugitive
   methane from digester, gas holder and engine slip (2 % of the methane produced, 0.717 kg/m3).
3. Builds a product system per process, calculates it and adds the credit for the grid
   electricity the plant displaces, using the country's lifecycle carbon intensity
   (Ember via Our World in Data, 2025).

Plant sizes and methane yields come from ``biossbd.examples.tea_presets_path()``.
"""
from __future__ import annotations

import uuid

import olca_ipc as ipc
import olca_schema as o

from biossbd.economics import biogas_chp, load_presets
from biossbd.examples import tea_presets_path

PORT = 8080
NS = uuid.UUID("6f1d1c2e-9a7b-4b8e-9a51-0b1a5d5d0a11")  # namespace for the fixed UUIDs
CATEGORY = "bioSSbD/AcoD worked example"

TRUCK = "711ab26a-94a2-33f9-89da-560c55808297"  # Transport, single unit truck; short-haul; diesel powered (US)
ENERGY = "f6811440-ee37-11de-8a39-0800200c9a66"  # flow property Energy (MJ)
MASS = "93a60a56-a3c8-11da-a746-0800200b9a66"  # flow property Mass (kg)
METHANE_BIOGENIC = "eeb36263-bf18-3ccb-b8ba-765c07a9e4bf"  # FEDEFL Methane, biogenic; emission/air

LEAK = 0.02  # ASSUMPTION: fugitive CH4 as share of CH4 produced
RHO_CH4 = 0.717  # kg/m3 at 0 C, 1 atm
GWP_CH4_BIOGENIC = 27.0  # IPCC AR6 GWP100, non-fossil methane
AR6 = {"Carbon dioxide": 1.0, "Methane": 29.8, "Methane, biogenic": 27.0, "Nitrous oxide": 273.0}

# Co-substrate delivery distance by truck (ASSUMPTION) and grid intensity (Ember 2026 via OWID, 2025)
SITES = {
    "Lactoserum + manure": {"km": 30, "grid_g_per_kwh": 186.81, "country": "Colombia"},
    "Cacao husk + manure": {"km": 50, "grid_g_per_kwh": 109.95, "country": "Brazil"},
    "Coffee husk + manure": {"km": 50, "grid_g_per_kwh": 474.02, "country": "Mexico"},
}


def uid(name: str) -> str:
    return str(uuid.uuid5(NS, name))


def unit_ref(client: ipc.Client, process_id: str) -> tuple[o.Ref, o.Ref, o.Ref]:
    """(flow, flow property, unit) of a process's quantitative reference."""
    p = client.get(o.Process, process_id)
    q = next(e for e in p.exchanges if e.is_quantitative_reference)
    return q.flow, q.flow_property, q.unit


def kg_unit(client: ipc.Client) -> o.Ref:
    p = client.get(o.Process, TRUCK)
    return next(e.unit for e in p.exchanges if e.unit and e.unit.name == "kg")


def mj_unit(client: ipc.Client) -> o.Ref:
    g = client.get(o.FlowProperty, ENERGY)
    group = client.get(o.UnitGroup, g.unit_group.id)
    u = next(u for u in group.units if u.name == "MJ")
    return o.Ref(ref_type=o.RefType.Unit, id=u.id, name=u.name)


def put_gwp_method(client: ipc.Client, kg: o.Ref) -> str:
    flows = [d for d in client.get_descriptors(o.Flow)
             if d.flow_type == o.FlowType.ELEMENTARY_FLOW and d.name in AR6
             and "emission/air" in (d.category or "")]
    factors = [o.ImpactFactor(flow=o.Ref(ref_type=o.RefType.Flow, id=d.id),
                              flow_property=o.Ref(ref_type=o.RefType.FlowProperty, id=MASS),
                              unit=kg, value=AR6[d.name]) for d in flows]
    ic = o.ImpactCategory(id=uid("gwp100-ar6-fedefl"),
                          name="Climate change, GWP100 (IPCC AR6; CO2, CH4, N2O; FEDEFL)",
                          category="bioSSbD", ref_unit="kg CO2 eq", impact_factors=factors)
    client.put(ic)
    m = o.ImpactMethod(id=uid("gwp100-ar6-fedefl-method"), name="bioSSbD GWP100 for USLCI (IPCC AR6 subset)",
                       category="bioSSbD", impact_categories=[o.Ref(ref_type=o.RefType.ImpactCategory, id=ic.id)])
    client.put(m)
    return m.id


def put_plant(client: ipc.Client, name: str, mwh: float, ch4_m3: float, tkm: float,
              elec_flow: str, kg: o.Ref, mj: o.Ref) -> str:
    t_flow, t_fp, t_unit = unit_ref(client, TRUCK)
    p = o.Process(
        id=uid(f"plant/{name}"), name=f"AcoD biogas CHP, {name} (1 year)", category=CATEGORY,
        process_type=o.ProcessType.UNIT_PROCESS, last_internal_id=3,
        exchanges=[
            o.Exchange(internal_id=1, flow=o.Ref(ref_type=o.RefType.Flow, id=elec_flow),
                       flow_property=o.Ref(ref_type=o.RefType.FlowProperty, id=ENERGY), unit=mj,
                       amount=mwh * 3600, is_input=False, is_quantitative_reference=True),
            o.Exchange(internal_id=2, flow=t_flow, flow_property=t_fp, unit=t_unit, amount=tkm, is_input=True,
                       default_provider=o.Ref(ref_type=o.RefType.Process, id=TRUCK)),
            o.Exchange(internal_id=3, flow=o.Ref(ref_type=o.RefType.Flow, id=METHANE_BIOGENIC),
                       flow_property=o.Ref(ref_type=o.RefType.FlowProperty, id=MASS), unit=kg,
                       amount=ch4_m3 * LEAK * RHO_CH4, is_input=False),
        ])
    client.put(p)
    return p.id


def existing_system(client: ipc.Client, process_id: str) -> o.Ref | None:
    """The product system already built from a process, so that re-runs do not add duplicates.

    openLCA assigns a new UUID to every created product system; the plant process (fixed UUID) is updated
    in place by ``put`` and the linked system picks the update up when it is calculated.
    """
    for d in client.get_descriptors(o.ProductSystem):
        ps = client.get(o.ProductSystem, d.id)
        if ps and ps.ref_process and ps.ref_process.id == process_id:
            return o.Ref(ref_type=o.RefType.ProductSystem, id=d.id, name=d.name)
    return None


def main() -> None:
    client = ipc.Client(PORT)
    kg, mj = kg_unit(client), mj_unit(client)
    method = put_gwp_method(client, kg)
    elec = o.Flow(id=uid("electricity"), name="Electricity, from AcoD biogas CHP (bioSSbD example)",
                  category=CATEGORY, flow_type=o.FlowType.PRODUCT_FLOW,
                  flow_properties=[o.FlowPropertyFactor(
                      flow_property=o.Ref(ref_type=o.RefType.FlowProperty, id=ENERGY),
                      conversion_factor=1.0, is_ref_flow_property=True)])
    client.put(elec)

    print(f"{'alternative':22s} {'plant t':>8s} {'transport':>9s} {'fugitive':>9s} "
          f"{'avoided':>8s} {'net t':>7s} {'kg/MWh':>8s}")
    for name, inp in load_presets(tea_presets_path()).items():
        chp, _ = biogas_chp(inp)
        site = SITES[name]
        co_substrate_t = sum(f.tonnes_per_year for f in inp.feedstocks if f.name != "cattle manure")
        tkm = co_substrate_t * site["km"]
        pid = put_plant(client, name, chp.electricity_mwh_per_year, chp.methane_m3_per_year, tkm, elec.id, kg, mj)
        system = existing_system(client, pid) or client.create_product_system(
            o.Ref(ref_type=o.RefType.Process, id=pid),
            o.LinkingConfig(prefer_unit_processes=False, provider_linking=o.ProviderLinking.PREFER_DEFAULTS))
        result = client.calculate(o.CalculationSetup(
            target=o.Ref(ref_type=o.RefType.ProductSystem, id=system.id),
            impact_method=o.Ref(ref_type=o.RefType.ImpactMethod, id=method)))
        result.wait_until_ready()
        plant = float(result.get_total_impacts()[0].amount)
        result.dispose()
        fugitive = chp.methane_m3_per_year * LEAK * RHO_CH4 * GWP_CH4_BIOGENIC
        avoided = chp.electricity_mwh_per_year * site["grid_g_per_kwh"]  # MWh x g/kWh = kg
        net = plant - avoided
        print(f"{name:22s} {plant / 1e3:8.1f} {(plant - fugitive) / 1e3:9.1f} {fugitive / 1e3:9.1f} "
              f"{avoided / 1e3:8.1f} {net / 1e3:7.1f} {net / chp.electricity_mwh_per_year:8.1f}")


if __name__ == "__main__":
    main()
