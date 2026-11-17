"""SSbD dossier: a Markdown report documenting scoping, safety, sustainability,
evaluation and data quality, following the documentation element of the
revised EC SSbD framework."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from . import __version__
from .dataquality import summarise
from .evaluation import Evaluation
from .framework import STEPS
from .safety.assess import safety_kpis
from .safety.risk import risk_table
from .scoping import SSbDSystem, receptor_matrix, safety_matrix, scoping_gaps


def md_table(df: pd.DataFrame, index: bool = True, floatfmt: str = "{:.3g}") -> str:
    """Render a DataFrame as a GitHub-flavoured Markdown table (no extra dependency)."""
    if df is None or df.empty:
        return "_None._\n"
    d = df.copy()
    if index:
        d = d.reset_index()
    def fmt(v):
        if isinstance(v, float):
            return floatfmt.format(v) if pd.notna(v) else ""
        if isinstance(v, (list, tuple)):
            return ", ".join(map(str, v))
        return "" if v is None else str(v).replace("|", "/").replace("\n", " ")
    head = "| " + " | ".join(map(str, d.columns)) + " |"
    sep = "| " + " | ".join("---" for _ in d.columns) + " |"
    body = ["| " + " | ".join(fmt(v) for v in row) + " |" for row in d.itertuples(index=False)]
    return "\n".join([head, sep, *body]) + "\n"


def _step_coverage(system: SSbDSystem, ev: Evaluation | None) -> pd.DataFrame:
    has_units = any(system.units_for(a) for a in (system.alternatives or [None]))
    has_risks = any(a.risks for a in system.alternatives)
    dims = {s.dimension.lower() for s in system.indicator_specs}
    steps_with_ind = {s.step for s in system.indicator_specs if s.step}
    rows = []
    for st in STEPS:
        auto = {1: has_units, 2: has_risks, 3: has_units,
                10: any("environment" in d for d in dims),
                11: any("econom" in d or "social" in d for d in dims)}.get(st.number, False)
        status = "covered" if (auto or st.number in steps_with_ind) else (
            "to document (operational phase)" if 4 <= st.number <= 9 else "missing")
        rows.append({"step": st.number, "name": st.name, "PDCA": ", ".join(st.pdca), "status": status})
    return pd.DataFrame(rows).set_index("step")


def build_dossier(system: SSbDSystem, mcda: bool = True, robustness_runs: int = 2000,
                  author: str = "", title: str | None = None) -> str:
    """Return the dossier as a Markdown string."""
    out: list[str] = []
    w = out.append
    w(f"# SSbD dossier: {title or system.name}\n")
    w(f"_Generated with bioSSbD-py {__version__} on {date.today().isoformat()}"
      f"{' by ' + author if author else ''}. Screening-level results; see Limitations._\n")

    # 1 scoping ---------------------------------------------------------------
    w("## 1. Scoping analysis\n")
    w("### 1.1 SSbD system\n")
    w(f"- **Functional unit:** {system.functional_unit or 'not defined'}\n"
      f"- **System boundary:** {system.system_boundary}\n"
      f"- **Life-cycle stages:** {', '.join(s.name for s in system.stages)}\n"
      f"- **Alternatives (SSbD scenarios):** {', '.join(system.alternative_names) or 'none'}\n")
    inv = system.innovation
    w("### 1.2 Intended innovation\n")
    w(f"{inv.description or '_Not described._'}\n")
    for label, items in (("Objectives", inv.objectives), ("Principles", inv.principles),
                         ("(Re)design actions", inv.design_actions)):
        if items:
            w(f"**{label}:**\n" + "".join(f"- {i}\n" for i in items))
    if inv.trl:
        w(f"Technology readiness level: TRL {inv.trl}\n")
    w("### 1.3 Actors along the life cycle\n")
    w(md_table(pd.DataFrame([a.model_dump() for a in system.actors]), index=False))
    if system.criteria:
        w("### 1.4 Decision criteria\n")
        w(md_table(pd.DataFrame([c.model_dump() for c in system.criteria]), index=False))
    w("### 1.5 Scoping gaps\n")
    w(md_table(scoping_gaps(system), index=False))

    # 2 safety ----------------------------------------------------------------
    w("## 2. Safety assessment (life-cycle perspective)\n")
    w("Maximum screening severity (1-5, 0 = none identified) per life-cycle stage. "
      "Stages with zeros are either hazard-free or not yet assessed.\n")
    alts = system.alternatives or [None]
    kpi_rows = []
    for alt in alts:
        name = alt.name if alt else system.name
        w(f"### 2.{alts.index(alt) + 1} {name}\n")
        w("**Stage x hazard group**\n\n" + md_table(safety_matrix(system, alt)))
        w("\n**Stage x receptor**\n\n" + md_table(receptor_matrix(system, alt)))
        if alt is not None and alt.risks:
            w("\n**Risk and reliability (step 2)**\n\n" + md_table(
                risk_table(alt.risks)[["risk", "stage", "impact", "likelihood", "risk_index",
                                       "I_x_L", "class", "mitigation"]], index=False))
        k = safety_kpis(system, alt)
        kpi_rows.append({"alternative": name, "ISI": k.isi.total, "ISI (normalised)": k.isi.normalised,
                         "hazardous inventory (kg)": k.hazardous_inventory_kg,
                         "high-risk units": len(k.high_risk_units), "max severity": k.max_severity})
    w("### Inherent safety KPIs (step 3)\n")
    w(md_table(pd.DataFrame(kpi_rows), index=False))

    # 3 sustainability and evaluation -----------------------------------------
    ev = None
    if system.indicator_specs and system.alternatives:
        ev = Evaluation.from_system(system)
        w("## 3. Sustainability and evaluation\n")
        w("### 3.1 Dimension scores (1 = worst, 5 = best; not aggregated)\n")
        w(md_table(ev.dimension_scores((1, 5)).round(2)))
        w("### 3.2 Best alternative per indicator\n")
        w(md_table(ev.best_by_indicator().to_frame()))
        w("### 3.3 Dominance and trade-offs\n")
        w(f"Pareto-optimal alternatives: **{', '.join(ev.pareto_front())}**\n\n")
        w(md_table(ev.tradeoffs(), index=False))
        cs = ev.criteria_summary()
        if not cs.empty:
            w("### 3.4 Decision criteria\n" + md_table(cs, index=False))
        if mcda:
            w("### 3.5 Aggregated scores (sensitivity layer)\n")
            w("Aggregation is reported only to test whether the comparison is robust to the "
              "aggregation rule; it does not replace the dimension-level reading above.\n\n")
            w(md_table(ev.compare_methods().round(3)))
            if robustness_runs:
                r = ev.robustness(n=robustness_runs, perturb_scores=True, perturb_weights=True)
                w(f"\nMonte Carlo ({robustness_runs} runs, score and weight perturbation): "
                  "rank acceptability\n\n" + md_table(r.rank_acceptability.round(3)))
                w("\n" + md_table(r.order_probability.head(5).to_frame().round(3)))

        # data quality
        w("## 4. Data quality\n")
        pts = [dp for a in system.alternatives for dp in a.indicators.values()]
        q = summarise(pts)
        w(f"- Data points: {q.n}\n- By evidence type: {q.by_evidence}\n"
          f"- Mean quality score (1 assumed - 5 measured): {q.mean_quality}\n"
          f"- Share with an uncertainty range: {q.share_with_range}\n")

    # 5 coverage --------------------------------------------------------------
    w("## 5. Coverage of the BioSSbD steps\n")
    w(md_table(_step_coverage(system, ev)))

    w("## 6. Limitations\n")
    w("- Hazard severities and inherent-safety bands are screening defaults; verify substance "
      "classifications against the ECHA C&L Inventory or current safety data sheets.\n"
      "- Ordinal scores are comparative indicators, not measurements.\n"
      "- Results support early-stage comparison of alternatives and do not predict plant performance.\n")
    return "\n".join(out)


def write_dossier(system: SSbDSystem, path: str | Path, **kwargs) -> Path:
    path = Path(path)
    path.write_text(build_dossier(system, **kwargs), encoding="utf-8")
    return path
