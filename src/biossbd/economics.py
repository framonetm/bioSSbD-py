"""Screening-level techno-economic indicators (BioSSbD step 11).

A transparent cash-flow model for early design: constant annual cash flows
after an initial investment. For detailed TEA use BioSTEAM/QSDsan.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CashFlowInput(BaseModel):
    capex: float = Field(ge=0, description="Total capital investment (currency)")
    opex: float = Field(ge=0, description="Annual operating cost (currency/yr)")
    revenue: float = Field(ge=0, description="Annual revenue incl. avoided costs and incentives (currency/yr)")
    lifetime: int = Field(20, ge=1, le=100, description="Economic lifetime (years)")
    discount_rate: float = Field(0.08, ge=0, lt=1)
    annual_output: float | None = Field(None, gt=0, description="Annual functional output, e.g. MWh/yr")
    output_unit: str = ""
    currency: str = "EUR"


class CashFlowResult(BaseModel):
    npv: float
    irr: float | None
    simple_payback_years: float | None
    discounted_payback_years: float | None
    annualised_capex: float
    levelised_cost: float | None  # (annualised capex + opex) / annual output
    benefit_cost_ratio: float | None


def crf(rate: float, n: int) -> float:
    """Capital recovery factor."""
    if rate == 0:
        return 1 / n
    return rate * (1 + rate) ** n / ((1 + rate) ** n - 1)


def npv(rate: float, capex: float, annual: float, n: int) -> float:
    if rate == 0:
        return -capex + annual * n
    return -capex + annual * (1 - (1 + rate) ** -n) / rate


def irr(capex: float, annual: float, n: int, lo: float = -0.99, hi: float = 10.0, tol: float = 1e-9) -> float | None:
    """Internal rate of return by bisection; None if no sign change."""
    f = lambda r: npv(r, capex, annual, n)  # noqa: E731
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        return None
    for _ in range(300):
        mid = (lo + hi) / 2
        fm = f(mid)
        if abs(fm) < tol:
            return mid
        if flo * fm < 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2


def cash_flow(inp: CashFlowInput) -> CashFlowResult:
    annual = inp.revenue - inp.opex
    r, n = inp.discount_rate, inp.lifetime
    disc_pb = None
    if annual > 0:
        cum = -inp.capex
        for t in range(1, n + 1):
            prev = cum
            cum += annual / (1 + r) ** t
            if cum >= 0:
                disc_pb = t - 1 + (-prev) / (cum - prev)
                break
    ann_capex = inp.capex * crf(r, n)
    pv_costs = inp.capex + npv(r, 0, inp.opex, n)
    pv_benefits = npv(r, 0, inp.revenue, n)
    return CashFlowResult(
        npv=npv(r, inp.capex, annual, n),
        irr=irr(inp.capex, annual, n) if inp.capex > 0 else None,
        simple_payback_years=inp.capex / annual if annual > 0 else None,
        discounted_payback_years=disc_pb,
        annualised_capex=ann_capex,
        levelised_cost=(ann_capex + inp.opex) / inp.annual_output if inp.annual_output else None,
        benefit_cost_ratio=pv_benefits / pv_costs if pv_costs > 0 else None,
    )


def to_indicators(inp: CashFlowInput, res: CashFlowResult, source: str = "bioSSbD screening cash-flow model") -> dict:
    """DataPoints ready to attach to an alternative (evidence = modelled)."""
    from .dataquality import DataPoint
    c = inp.currency
    out = {"Net present value": DataPoint(value=res.npv, unit=c, source=source, evidence="modelled")}
    if res.irr is not None:
        out["Internal rate of return"] = DataPoint(value=res.irr * 100, unit="%", source=source, evidence="modelled")
    if res.simple_payback_years is not None:
        out["Simple payback"] = DataPoint(value=res.simple_payback_years, unit="yr", source=source, evidence="modelled")
    if res.levelised_cost is not None:
        out["Levelised cost"] = DataPoint(value=res.levelised_cost, unit=f"{c}/{inp.output_unit or 'unit'}",
                                          source=source, evidence="modelled")
    return out


#: Direction for evaluation of the indicators above
DIRECTIONS = {"Net present value": "max", "Internal rate of return": "max", "Simple payback": "min",
              "Levelised cost": "min"}


# ---------------------------------------------------------------------------
# Biogas -> combined heat and power (CHP): from feedstock to cash flow
# ---------------------------------------------------------------------------
CH4_LHV_KWH_PER_M3 = 9.94  # 35.8 MJ/Nm3


class Feedstock(BaseModel):
    name: str
    tonnes_per_year: float = Field(ge=0)
    methane_yield_m3_per_t: float = Field(ge=0, description="Nm3 CH4 per tonne as received")
    source: str = ""


class BiogasCHPInput(BaseModel):
    """Farm-scale anaerobic digestion with a CHP engine (electricity valued at the avoided tariff)."""

    feedstocks: list[Feedstock]
    electrical_efficiency: float = Field(0.35, gt=0, le=0.5)
    thermal_efficiency: float = Field(0.0, ge=0, le=0.6, description="Set > 0 only if the heat is used")
    operating_hours: float = Field(7500, gt=0, le=8760)
    specific_capex_per_kwe: float = Field(6100, gt=0, description="Installed cost per kW electric")
    fixed_om_share: float = Field(0.05, ge=0, le=0.3, description="Fixed O&M as share of CAPEX per year")
    variable_om_per_kwh: float = Field(0.005, ge=0)
    electricity_price: float = Field(gt=0, description="Avoided or sold electricity (currency/kWh)")
    heat_price_per_kwh: float = Field(0.0, ge=0)
    lifetime: int = Field(20, ge=1, le=60)
    discount_rate: float = Field(0.10, ge=0, lt=1)
    currency: str = "USD"
    sources: dict[str, str] = Field(default_factory=dict)


class BiogasCHPResult(BaseModel):
    methane_m3_per_year: float
    electricity_mwh_per_year: float
    heat_mwh_per_year: float
    electrical_capacity_kwe: float
    capex: float
    opex: float
    revenue: float
    cash_flow: CashFlowResult


def biogas_chp(inp: BiogasCHPInput) -> tuple[BiogasCHPResult, CashFlowInput]:
    ch4 = sum(f.tonnes_per_year * f.methane_yield_m3_per_t for f in inp.feedstocks)
    energy_kwh = ch4 * CH4_LHV_KWH_PER_M3
    el_kwh = energy_kwh * inp.electrical_efficiency
    heat_kwh = energy_kwh * inp.thermal_efficiency
    kwe = el_kwh / inp.operating_hours
    capex = kwe * inp.specific_capex_per_kwe
    opex = capex * inp.fixed_om_share + el_kwh * inp.variable_om_per_kwh
    revenue = el_kwh * inp.electricity_price + heat_kwh * inp.heat_price_per_kwh
    cf_in = CashFlowInput(capex=capex, opex=opex, revenue=revenue, lifetime=inp.lifetime,
                          discount_rate=inp.discount_rate, annual_output=el_kwh / 1000 if el_kwh else None,
                          output_unit="MWh", currency=inp.currency)
    res = BiogasCHPResult(methane_m3_per_year=ch4, electricity_mwh_per_year=el_kwh / 1000,
                          heat_mwh_per_year=heat_kwh / 1000, electrical_capacity_kwe=kwe, capex=capex, opex=opex,
                          revenue=revenue, cash_flow=cash_flow(cf_in))
    return res, cf_in


def load_presets(path) -> dict[str, BiogasCHPInput]:
    """Read biogas-CHP presets (one per alternative) from YAML."""
    import yaml
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    common = data.get("common", {})
    out = {}
    for name, d in data["alternatives"].items():
        merged = {**common, **d, "sources": {**common.get("sources", {}), **d.get("sources", {})}}
        out[name] = BiogasCHPInput.model_validate(merged)
    return out
