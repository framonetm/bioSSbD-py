"""bioSSbD-py graphical interface: a step-by-step SSbD assessment.

Launch with ``biossbd gui``. Each step lets the user choose a method, an
open-source tool or a public database (see :mod:`biossbd.registry`), and all
results are stored in one SSbD system that can be downloaded as YAML.
"""
from __future__ import annotations

import hashlib
import json

import matplotlib

matplotlib.use("Agg")

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
import yaml  # noqa: E402
from matplotlib import pyplot as plt  # noqa: E402
from pydantic import ValidationError  # noqa: E402

import biossbd  # noqa: E402
from biossbd import Evaluation, SSbDSystem, registry, steps_table  # noqa: E402
from biossbd import economics as econ  # noqa: E402
from biossbd.connectors import ConnectorError  # noqa: E402
from biossbd.dataquality import DataPoint  # noqa: E402
from biossbd.dossier import _step_coverage, build_dossier  # noqa: E402
from biossbd.examples import acod_path, empty_system_dict  # noqa: E402
from biossbd.framework import PDCA_CHECKLIST, get_step  # noqa: E402
from biossbd.gui import plots  # noqa: E402
from biossbd.gui.state import (add_indicators, apply_editor_changes, sync_indicator_rows,  # noqa: E402
                               upsert_substance)
from biossbd.gui.tables import SHARED, system_to_tables, tables_to_dict, tables_to_system  # noqa: E402
from biossbd.hazards import PROCESS_HAZARDS, SUBSTANCES  # noqa: E402
from biossbd.mcda import COMPENSATORY, METHODS  # noqa: E402
from biossbd.pdca import Cycle, Iteration  # noqa: E402
from biossbd.safety import indices as isi_mod  # noqa: E402
from biossbd.safety.assess import safety_kpis  # noqa: E402
from biossbd.safety.risk import risk_table  # noqa: E402
from biossbd.scoping import hazard_register, load_system, receptor_matrix, safety_matrix, scoping_gaps  # noqa: E402

st.set_page_config(page_title="bioSSbD-py", layout="wide")

PAGES = ["Start", "1 · Scoping", "2 · Hazard identification", "3 · Risk & reliability", "4 · Inherent safety",
         "5 · Environmental (LCA)", "6 · Socio-economic", "7 · Evaluation", "8 · Robustness", "9 · PDCA",
         "10 · Dossier", "Tools & data sources"]
STEP_OF_PAGE = {"1 · Scoping": "Scoping", "2 · Hazard identification": "Hazard identification",
                "3 · Risk & reliability": "Risk and reliability", "4 · Inherent safety": "Inherent safety",
                "5 · Environmental (LCA)": "Environmental sustainability",
                "6 · Socio-economic": "Socio-economic sustainability", "7 · Evaluation": "Evaluation",
                "8 · Robustness": "Evaluation", "10 · Dossier": "Documentation"}


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------
def load_into_state(system: SSbDSystem, label: str) -> None:
    st.session_state.T = system_to_tables(system)
    st.session_state.last_valid = system
    st.session_state.source = label
    st.session_state.V = st.session_state.get("V", 0) + 1
    for k in ("robustness", "dossier", "pc_candidates", "pc_safety", "lca_results", "pc_bulk", "inv_result"):
        st.session_state[k] = None
    st.session_state.cycle = Cycle()


if "T" not in st.session_state:
    load_into_state(load_system(acod_path()), "Example: anaerobic co-digestion")
    st.session_state.page = PAGES[0]

T: dict = st.session_state.T
V: int = st.session_state.V
sync_indicator_rows(T)


def _on_edit(name: str, key: str, keep_index: bool) -> None:
    st.session_state.T[name] = apply_editor_changes(st.session_state.T[name], st.session_state[key], keep_index)


def editor(name: str, *, num_rows: str = "dynamic", column_config: dict | None = None, keep_index: bool = False,
           height: int | None = None) -> None:
    key = f"ed_{name}_{V}"
    kw = dict(key=key, num_rows=num_rows, hide_index=not keep_index, column_config=column_config or {},
              on_change=_on_edit, args=(name, key, keep_index))
    if height:
        kw["height"] = height
    st.data_editor(T[name], **kw)


def show_fig(fig) -> None:
    st.pyplot(fig)
    plt.close(fig)


def go(page: str) -> None:
    st.session_state.page = page


def nav_buttons(page: str) -> None:
    i = PAGES.index(page)
    st.divider()
    c1, _, c3 = st.columns([1, 4, 1])
    if i > 0:
        c1.button(f"← {PAGES[i - 1]}", on_click=go, args=(PAGES[i - 1],), key=f"prev_{page}")
    if i < len(PAGES) - 1:
        c3.button(f"{PAGES[i + 1]} →", on_click=go, args=(PAGES[i + 1],), key=f"next_{page}", type="primary")


def step_header(page: str, numbers: tuple[int, ...] = ()) -> None:
    st.header(page.split("· ")[-1])
    if numbers:
        st.caption("BioSSbD " + " · ".join(f"step {n}: {get_step(n).name}" for n in numbers))


def tool_picker(step: str, key: str, default: str | None = None) -> str:
    tools = registry.tools_for(step)
    ids = [t.id for t in tools]
    labels = {t.id: f"{t.name}  —  {t.status()}" for t in tools}
    idx = ids.index(default) if default in ids else 0
    tid = st.radio("Method / tool / data source", ids, index=idx, format_func=lambda i: labels[i],
                   key=f"tool_{key}", horizontal=False)
    t = registry.get(tid)
    st.caption(f"{t.description}  ·  Licence: {t.licence}  ·  [{t.url}]({t.url})")
    if not t.installed():
        st.warning(f"Not installed on this computer. Install with: `{t.install}` and restart the interface.")
    return tid


def system_hash(d: dict) -> str:
    return hashlib.sha1(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()


def alt_names() -> list[str]:
    return [a for a in T["alternatives"]["name"].tolist() if isinstance(a, str) and a.strip()]


def stage_names() -> list[str]:
    return [s for s in T["stages"]["name"].tolist() if isinstance(s, str) and s.strip()]


def add_results_ui(results: dict[str, DataPoint], default_dimension: str, step: int, key: str,
                   directions: dict[str, str] | None = None) -> None:
    """Review results, choose the alternative and dimension, then attach them."""
    if not results:
        return
    df = pd.DataFrame([{"include": True, "indicator": k, "value": v.value, "unit": v.unit, "source": v.source}
                       for k, v in results.items()])
    edited = st.data_editor(df, hide_index=True, key=f"rev_{key}", disabled=["value", "unit", "source"],
                            column_config={"include": st.column_config.CheckboxColumn("include")})
    c1, c2, c3 = st.columns(3)
    alts = alt_names()
    target = c1.selectbox("Attach to alternative", alts, key=f"tgt_{key}") if alts else None
    dim = c2.text_input("Dimension", default_dimension, key=f"dim_{key}")
    direction = c3.selectbox("Better when", ["min", "max"], key=f"dir_{key}",
                             help="Default direction for new indicators (impacts: min)")
    if st.button("Add to system", type="primary", key=f"add_{key}", disabled=target is None):
        chosen = {}
        for r in edited.to_dict("records"):
            if r["include"]:
                old = results[r["indicator"]]
                name = str(r["indicator"]).strip()
                chosen[name] = old
        dirs = {k: (directions or {}).get(k, direction) for k in chosen}
        names = add_indicators(T, target, chosen, dim, directions=dirs, step=step)
        st.success(f"Added {len(names)} indicator(s) to “{target}”. See 7 · Evaluation.")


# ---------------------------------------------------------------------------
# validate the current tables
# ---------------------------------------------------------------------------
def validate():
    try:
        s = tables_to_system(T)
        st.session_state.last_valid = s
        return s, None
    except (ValidationError, ValueError, KeyError, TypeError) as e:
        return st.session_state.last_valid, e


system, error = validate()


def evaluation():
    if not (system.indicator_specs and system.alternatives and any(a.indicators for a in system.alternatives)):
        return None
    try:
        return Evaluation.from_system(system)
    except (KeyError, ValueError):
        return None


def _on_inv_edit(key: str) -> None:
    st.session_state.inv_table = apply_editor_changes(st.session_state.inv_table, st.session_state[key])


def inventory_ui(data: dict, methods: list) -> None:
    """Build a small inventory per alternative from openLCA processes and calculate its impacts."""
    from biossbd import lca_inventory as inv
    from biossbd.connectors import openlca as olc
    st.subheader("Inventory per alternative")
    st.caption("One line per input and functional unit (FU), in the unit of the process reference flow "
               "(kg for materials, t*km for transport, kWh or MJ for energy). Each process is calculated once "
               "per reference unit, including its supply chain, and scaled by the amount. Give the source of "
               "every amount; lines without one are flagged as ASSUMPTION.")
    if st.session_state.get("inv_table") is None:
        st.session_state.inv_table = inv.empty_frame()
    st.session_state.setdefault("inv_v", 0)
    c = st.columns([3, 1])
    q = c[0].text_input("Search processes", key="inv_q", placeholder="e.g. lorry, electricity, cement")
    c[1].write("")
    if c[1].button("Search", key="inv_search") and q:
        try:
            st.session_state.inv_procs = olc.OpenLCA(data["port"]).processes(q, limit=200)
        except ConnectorError as e:
            st.error(str(e))
    found = st.session_state.get("inv_procs") or []
    alts = alt_names()
    if found and alts:
        c = st.columns([4, 2, 1.3, 1.3])
        fi = c[0].selectbox("Process", range(len(found)), key="inv_proc",
                            format_func=lambda i: f"{found[i].name}" + (f"  ({found[i].category})"
                                                                         if found[i].category else ""))
        ia = c[1].selectbox("Alternative", alts, key="inv_alt")
        cat = c[2].selectbox("Category", inv.CATEGORIES, key="inv_cat")
        amt = c[3].number_input("Amount per FU", value=0.0, key="inv_amt", format="%g")
        src = st.text_input("Source of the amount", key="inv_src",
                            placeholder="e.g. plant mass balance 2024; Ramonet 2026, Table 3")
        if st.button("Add line", key="inv_add"):
            try:
                _, unit = olc.OpenLCA(data["port"]).reference(found[fi].id)
            except ConnectorError:
                unit = ""
            row = {"alternative": ia, "category": cat, "process": found[fi].name, "amount": amt, "unit": unit,
                   "source": src, "process_id": found[fi].id}
            st.session_state.inv_table = pd.concat([st.session_state.inv_table.astype(object),
                                                    pd.DataFrame([row]).astype(object)],
                                                   ignore_index=True).infer_objects()
            st.session_state.inv_v += 1
    elif found and not alts:
        st.info("Define alternatives in 1 · Scoping first.")
    key = f"inv_ed_{st.session_state.inv_v}"
    st.data_editor(st.session_state.inv_table, key=key, num_rows="dynamic", hide_index=True,
                   on_change=_on_inv_edit, args=(key,), disabled=["process", "process_id"],
                   column_config={
                       "alternative": st.column_config.SelectboxColumn("alternative", options=alts),
                       "category": st.column_config.SelectboxColumn("category", options=list(inv.CATEGORIES)),
                       "amount": st.column_config.NumberColumn("amount per FU", format="%g"),
                       "process_id": st.column_config.TextColumn("openLCA id")})
    c = st.columns([1, 2])
    c[0].download_button("Download inventory (CSV)", st.session_state.inv_table.to_csv(index=False),
                         file_name="inventory.csv", mime="text/csv", key="inv_dl")
    up = c[1].file_uploader("Load inventory (CSV)", type="csv", key="inv_up")
    if up is not None and st.session_state.get("inv_up_name") != up.name:
        st.session_state.inv_table = inv.lines_to_frame(inv.lines_from_frame(pd.read_csv(up)))
        st.session_state.inv_up_name = up.name
        st.session_state.inv_v += 1
        st.rerun()
    lines = inv.lines_from_frame(st.session_state.inv_table)
    if not lines:
        return
    n_assumed = sum(ln.is_assumption for ln in lines)
    if n_assumed:
        st.warning(f"{n_assumed} line(s) have no source and will be reported as ASSUMPTION.")
    mi = st.selectbox("LCIA method", range(len(methods)), key="inv_method", format_func=lambda i: methods[i].name)
    if st.button("Calculate inventory", type="primary", key="inv_calc"):
        cache = st.session_state.setdefault("inv_cache", {})
        cl = olc.OpenLCA(data["port"])
        mid = methods[mi].id
        try:
            pids = list(dict.fromkeys(ln.process_id for ln in lines))
            bar = st.progress(0.0, text="Calculating processes in openLCA...")
            for k, pid in enumerate(pids):
                if (pid, mid) not in cache:
                    cache[(pid, mid)] = cl.unit_impacts(pid, mid)
                bar.progress((k + 1) / len(pids))
            bar.empty()
            st.session_state.inv_result = {"lines": lines, "unit": {p: cache[(p, mid)] for p in pids},
                                           "method": methods[mi].name}
        except ConnectorError as e:
            st.error(str(e))
    res = st.session_state.get("inv_result")
    if not res:
        return
    contrib = inv.contributions(res["lines"], res["unit"])
    if contrib.empty:
        st.info("openLCA returned no impact results for these processes.")
        return
    cats = list(dict.fromkeys(contrib["impact_category"]))
    ghg = inv.ghg_categories(cats)
    sel = st.selectbox("Impact category to plot", cats, index=cats.index(ghg[0]) if ghg else 0, key="inv_plot_cat")
    unit = contrib.loc[contrib["impact_category"] == sel, "impact_unit"].iloc[0]
    show_fig(plots.inventory_contributions(inv.by_inventory_category(contrib, sel), unit=f"{unit} per FU",
                                           title=f"{sel} · {res['method']}"))
    st.dataframe(inv.totals(contrib), width="stretch")
    with st.expander("Contribution of each line"):
        st.dataframe(contrib, hide_index=True, width="stretch")
    attach = st.multiselect("Impact categories to attach as indicators", cats, default=ghg or cats[:1],
                            key="inv_attach")
    if st.button("Attach totals to each alternative", key="inv_attach_btn", disabled=not attach):
        ind = inv.to_indicators(res["lines"], res["unit"], res["method"], impact_categories=attach)
        for alt, dps in ind.items():
            add_indicators(T, alt, dps, "Environmental (LCA)", step=10)
        st.success(f"Attached {len(attach)} indicator(s) to {len(ind)} alternative(s). See 7 · Evaluation.")


# ---------------------------------------------------------------------------
# sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("bioSSbD-py")
    st.caption(f"Safe-and-Sustainable-by-Design toolbox · v{biossbd.__version__}")
    page = st.radio("Assessment steps", PAGES, key="page")
    st.divider()
    st.markdown(f"**System:** {system.name}  \n**Source:** {st.session_state.source}")
    if error is None:
        st.success("All inputs valid")
    else:
        st.error("An edit is not valid; results use the last valid version.")
        with st.expander("Details"):
            st.code(str(error)[:2000], language=None)
    current = tables_to_dict(T) if error is None else system.model_dump(exclude_defaults=True)
    st.download_button("Download system (YAML)", yaml.safe_dump(current, sort_keys=False, allow_unicode=True),
                       file_name="ssbd_system.yaml", mime="text/yaml")


# ---------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------
if page == "Start":
    st.header("Start")
    st.markdown("Work through the steps in the sidebar. At each step you choose the method, open-source tool or "
                "public database to use; every result is stored with its source in one SSbD system that you can "
                "download as YAML and document in the dossier.")
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("Open or start a system")
        choice = st.radio("Source", ["Worked example (anaerobic co-digestion)", "Upload YAML", "New empty system"],
                          key="src_choice")
        upload = st.file_uploader("SSbD system YAML", type=["yaml", "yml"]) if choice == "Upload YAML" else None
        if st.button("Open", type="primary"):
            try:
                if choice.startswith("Worked"):
                    load_into_state(load_system(acod_path()), "Example: anaerobic co-digestion")
                elif choice == "Upload YAML":
                    if upload is None:
                        raise ValueError("Choose a YAML file first")
                    load_into_state(SSbDSystem.model_validate(yaml.safe_load(upload.getvalue())),
                                    f"File: {upload.name}")
                else:
                    load_into_state(SSbDSystem.model_validate(empty_system_dict()), "New system")
                st.rerun()
            except (ValidationError, ValueError, yaml.YAMLError) as e:
                st.error(f"Could not open: {e}")
    with c2:
        st.subheader("Progress")
        gaps = scoping_gaps(system)
        m = st.columns(3)
        m[0].metric("Alternatives", len(system.alternatives))
        m[1].metric("Indicators", len(system.indicator_specs))
        m[2].metric("Scoping gaps", len(gaps))
        cov = _step_coverage(system, None)
        st.dataframe(steps_table()[["name", "PDCA"]].join(cov[["status"]]), width="stretch", height=250)
    st.subheader("System and intended innovation")
    g = T["general"]
    c1, c2 = st.columns(2)
    g["name"] = c1.text_input("System name", g["name"], key=f"g_name_{V}")
    g["functional_unit"] = c2.text_input("Functional unit", g["functional_unit"], key=f"g_fu_{V}")
    g["system_boundary"] = c1.text_input("System boundary", g["system_boundary"], key=f"g_sb_{V}")
    g["trl"] = c2.number_input("Technology readiness level", 1, 9, value=int(g["trl"] or 4), key=f"g_trl_{V}")
    g["innovation_description"] = st.text_area("Intended innovation", g["innovation_description"], key=f"g_inn_{V}")
    c1, c2 = st.columns(2)
    g["objectives"] = c1.text_area("Objectives (one per line)", g["objectives"], key=f"g_obj_{V}")
    g["design_actions"] = c2.text_area("(Re)design actions (one per line)", g["design_actions"], key=f"g_da_{V}")
    g["principles"] = st.text_input("SSbD principles (comma-separated)", g["principles"], key=f"g_pr_{V}")
    st.subheader("Alternatives (SSbD scenarios) to compare")
    editor("alternatives")

elif page == "1 · Scoping":
    step_header(page)
    st.markdown("Define the **SSbD system**: life-cycle stages, actors, substances and process units, and plan "
                "the assessments per stage (Scoping analysis of the revised EC SSbD framework).")
    tool_picker("Scoping", "scoping", "yaml")
    alts = alt_names()
    stages = stage_names()
    with st.expander("Life-cycle stages", expanded=False):
        editor("stages", column_config={"in_lca_boundary": st.column_config.CheckboxColumn("in LCA boundary")})
    with st.expander("Actors along the life cycle"):
        editor("actors", column_config={"stages": st.column_config.TextColumn(
            "stages", help="Comma-separated stage names: " + ", ".join(stages))})
    with st.expander("Substances", expanded=True):
        st.caption("Add substances from PubChem or the built-in library below, or type them in. "
                   "Empty h_codes = use the built-in library.")
        editor("substances", column_config={
            "alternative": st.column_config.SelectboxColumn("alternative", options=[SHARED, *alts]),
            "role": st.column_config.SelectboxColumn(
                "role", options=["feedstock", "intermediate", "product", "auxiliary", "emission"])})
        t1, t2 = st.tabs(["Search PubChem", "Built-in library"])
        with t1:
            c1, c2 = st.columns([3, 1])
            q = c1.text_input("Name or CAS number", key="pc_query", placeholder="e.g. furfural or 98-01-1")
            if c2.button("Search", key="pc_search") and q:
                from biossbd.connectors import pubchem
                try:
                    with st.spinner("Searching PubChem..."):
                        st.session_state.pc_candidates = pubchem.search(q)
                        st.session_state.pc_safety = None
                    if not st.session_state.pc_candidates:
                        st.warning("No compound found.")
                except ConnectorError as e:
                    st.error(str(e))
            cands = st.session_state.get("pc_candidates") or []
            if cands:
                st.dataframe(pd.DataFrame([{"CID": c.cid, "name": c.name, "formula": c.formula, "CAS": c.cas,
                                            "MW": c.molecular_weight, "link": c.url} for c in cands]),
                             hide_index=True, width="stretch",
                             column_config={"link": st.column_config.LinkColumn("PubChem")})
                pick = st.selectbox("Compound", range(len(cands)), key="pc_pick",
                                    format_func=lambda i: f"{cands[i].name} (CID {cands[i].cid}, {cands[i].cas or 'no CAS'})")
                if st.button("Get safety data", key="pc_fetch"):
                    from biossbd.connectors import pubchem
                    try:
                        with st.spinner("Retrieving GHS classification and safety data..."):
                            st.session_state.pc_safety = pubchem.safety_data(cands[pick].cid, cands[pick].name)
                    except ConnectorError as e:
                        st.error(str(e))
            sd = st.session_state.get("pc_safety")
            if sd is not None:
                st.markdown(f"**{sd.name}** · CID {sd.cid} · CAS {sd.cas or '—'} · Signal word: "
                            f"{sd.signal_word or '—'}")
                share = st.slider("Accept hazard statements reported by at least (% of notifications)", 0, 100, 10,
                                  key="pc_share")
                codes = pd.DataFrame([{"accept": (s is None or s >= share), "code": c,
                                       "share (%)": s} for c, s in sorted(sd.h_codes.items())])
                codes_ed = st.data_editor(codes, hide_index=True, key=f"pc_codes_{sd.cid}_{share}",
                                          disabled=["code", "share (%)"]) if not codes.empty else codes
                if codes.empty:
                    st.info("No GHS hazard statements reported in PubChem.")
                c = st.columns(4)
                fp = c[0].number_input("Flash point (°C)", value=sd.flash_point_c, key=f"pc_fp_{sd.cid}")
                lel = c[1].number_input("LEL (vol %)", value=sd.lel_vol, key=f"pc_lel_{sd.cid}")
                uel = c[2].number_input("UEL (vol %)", value=sd.uel_vol, key=f"pc_uel_{sd.cid}")
                oel = c[3].number_input("OEL, 8-h TWA (ppm)", value=sd.oel_ppm, key=f"pc_oel_{sd.cid}")
                with st.expander("Source text from PubChem (check before accepting)"):
                    for k, v in sd.raw.items():
                        st.markdown(f"**{k}**")
                        for s in v[:12]:
                            st.caption(s)
                c = st.columns(3)
                role = c[0].selectbox("Role", ["intermediate", "feedstock", "product", "auxiliary", "emission"],
                                      key="pc_role")
                where = c[1].selectbox("Belongs to", [SHARED, *alts], key="pc_alt")
                name = c[2].text_input("Name in the system", sd.name.lower(), key=f"pc_name_{sd.cid}")
                if st.button("Add substance to system", type="primary", key="pc_add"):
                    acc = codes_ed[codes_ed["accept"]]["code"].tolist() if not codes.empty else []
                    upsert_substance(T, {"name": name, "cas": sd.cas, "role": role, "h_codes": acc,
                                         "flash_point_c": fp, "lel_vol": lel, "uel_vol": uel, "oel_ppm": oel}, where)
                    st.success(f"Added {name}. Assign it to process units below.")
                    st.rerun()
        with t2:
            lib = st.multiselect("Built-in substances", sorted(SUBSTANCES), key="lib_pick")
            if st.button("Add selected", key="lib_add") and lib:
                for n in lib:
                    upsert_substance(T, {"name": n, "role": "intermediate", "h_codes": list(SUBSTANCES[n].h_codes),
                                         "cas": SUBSTANCES[n].cas})
                st.rerun()
    with st.expander("Process units", expanded=True):
        st.caption("Process hazards available: " + ", ".join(sorted(PROCESS_HAZARDS)) + ".")
        editor("units", column_config={
            "alternative": st.column_config.SelectboxColumn("alternative", options=[SHARED, *alts]),
            "stage": st.column_config.SelectboxColumn("stage", options=stages),
            "substances": st.column_config.TextColumn("substances", help="Comma-separated substance names"),
            "inventory_kg": st.column_config.NumberColumn("inventory (kg)", min_value=0.0),
            "temperature_c": st.column_config.NumberColumn("T (°C)"),
            "pressure_bar": st.column_config.NumberColumn("P (bar abs)", min_value=0.0),
            "equipment_score": st.column_config.NumberColumn("equipment (0-4)", min_value=0, max_value=4, step=1),
            "structure_score": st.column_config.NumberColumn("structure (0-5)", min_value=0, max_value=5, step=1)})
    with st.expander("Planned and completed assessments per stage"):
        editor("assessments", column_config={
            "stage": st.column_config.SelectboxColumn("stage", options=["all", *stages]),
            "aspect": st.column_config.SelectboxColumn(
                "aspect", options=["safety", "environmental", "socio-economic", "functionality"]),
            "status": st.column_config.SelectboxColumn("status", options=["planned", "done", "not needed"])})
    st.subheader("Life-cycle safety matrix")
    sel = st.selectbox("Alternative", system.alternative_names or [None], key="sc_alt")
    by = st.radio("Hazard columns", ["group", "category"], horizontal=True, key="sc_by")
    c1, c2 = st.columns(2)
    with c1:
        show_fig(plots.heatmap(safety_matrix(system, sel, by=by), title="Max severity per stage (0 = none identified)"))
    with c2:
        show_fig(plots.heatmap(receptor_matrix(system, sel), title="Who is exposed"))
    st.subheader("Scoping gaps")
    gaps = scoping_gaps(system)
    if gaps.empty:
        st.success("No scoping gaps.")
    else:
        st.dataframe(gaps, hide_index=True, width="stretch")

elif page == "2 · Hazard identification":
    step_header(page, (1,))
    tid = tool_picker("Hazard identification", "hazid", "ghs-library")
    subs = system.substances_for(None) + [s for a in system.alternatives for s in a.substances]
    src = pd.DataFrame([{"substance": s.name, "CAS": s.cas or "",
                         "classification source": "explicit" if s.h_codes is not None else
                         ("built-in library" if s.name.lower() in SUBSTANCES else "missing"),
                         "H-codes": ", ".join(s.resolved_h_codes())} for s in subs]).drop_duplicates("substance")
    st.subheader("Substances and their classification")
    st.dataframe(src, hide_index=True, width="stretch")
    if tid == "pubchem":
        st.markdown("Look up every substance in PubChem and review the proposed classifications.")
        share = st.slider("Minimum share of notifications (%)", 0, 100, 10, key="bulk_share")
        if st.button("Look up all substances", type="primary"):
            from biossbd.connectors import pubchem
            rows = []
            prog = st.progress(0.0)
            for i, s in enumerate(src["substance"].tolist()):
                try:
                    c = pubchem.search(s, max_results=1)
                    if c:
                        sd = pubchem.safety_data(c[0].cid, c[0].name)
                        rows.append({"apply": True, "substance": s, "PubChem match": c[0].name, "CID": c[0].cid,
                                     "proposed H-codes": ", ".join(sd.accepted_codes(share)), "CAS": sd.cas})
                    else:
                        rows.append({"apply": False, "substance": s, "PubChem match": "not found"})
                except ConnectorError as e:
                    rows.append({"apply": False, "substance": s, "PubChem match": f"error: {e}"})
                prog.progress((i + 1) / len(src))
            st.session_state.pc_bulk = pd.DataFrame(rows)
        bulk = st.session_state.get("pc_bulk")
        if bulk is not None and not bulk.empty:
            ed = st.data_editor(bulk, hide_index=True, key="pc_bulk_ed",
                                disabled=[c for c in bulk.columns if c not in ("apply", "proposed H-codes")])
            if st.button("Apply selected classifications"):
                df = T["substances"].copy()
                for r in ed.to_dict("records"):
                    if r.get("apply") and isinstance(r.get("proposed H-codes"), str):
                        m = df["name"].astype(str).str.lower() == r["substance"].lower()
                        df.loc[m, "h_codes"] = r["proposed H-codes"]
                        if r.get("CAS"):
                            df.loc[m, "cas"] = r["CAS"]
                T["substances"] = df
                st.success("Classifications updated.")
                st.rerun()
    st.subheader("Hazard register")
    sel = st.selectbox("Alternative", system.alternative_names or [None], key="hz_alt")
    st.dataframe(hazard_register(system, sel), hide_index=True, width="stretch")
    with st.expander("Biological and process hazard library"):
        st.dataframe(pd.DataFrame([{"hazard": h.key, "group": h.group, "severity": h.severity,
                                    "typical stages": ", ".join(h.typical_stages), "description": h.description}
                                   for h in PROCESS_HAZARDS.values()]), hide_index=True, width="stretch")

elif page == "3 · Risk & reliability":
    step_header(page, (2,))
    tool_picker("Risk and reliability", "risk", "risk-matrix")
    alts = alt_names()
    st.caption("Impact and likelihood on 1-5 scales; add a detection rating (1-10) to obtain FMEA risk priority numbers.")
    editor("risks", column_config={
        "alternative": st.column_config.SelectboxColumn("alternative", options=alts),
        "stage": st.column_config.SelectboxColumn("stage", options=["", *stage_names()]),
        "impact": st.column_config.NumberColumn("impact (1-5)", min_value=1, max_value=5, step=1),
        "likelihood": st.column_config.NumberColumn("likelihood (1-5)", min_value=1, max_value=5, step=1),
        "detectability": st.column_config.NumberColumn("detection (1-10)", min_value=1, max_value=10, step=1)})
    sel = st.selectbox("Alternative", system.alternative_names or [None], key="rk_alt")
    if sel:
        rt = risk_table(system.get_alternative(sel).risks)
        c1, c2 = st.columns([3, 2])
        with c1:
            show_fig(plots.risk_matrix(rt, title=f"Risk matrix · {sel}"))
        with c2:
            if not rt.empty:
                key_t = rt[["risk", "class", "I_x_L", "RPN"]].copy()
                key_t.index = range(1, len(key_t) + 1)
                key_t.index.name = "#"
                st.dataframe(key_t, width="stretch")
        if not rt.empty:
            with st.expander("Full risk table"):
                st.dataframe(rt, hide_index=True, width="stretch")

elif page == "4 · Inherent safety":
    step_header(page, (3,))
    tool_picker("Inherent safety", "isi", "isi")
    with st.expander("Reaction data (for the chemical sub-index)"):
        c = st.columns(3)
        h_main = c[0].number_input("Heat of main reaction (J/g)", value=0.0, step=50.0)
        h_side = c[1].number_input("Heat of side reactions (J/g)", value=0.0, step=50.0)
        inter = c[2].number_input("Chemical interaction (0-4)", 0, 4, 0)
    rows = []
    for a in (system.alternatives or [None]):
        k = safety_kpis(system, a, h_main, h_side, inter)
        rows.append({"alternative": k.alternative or system.name, "ISI": k.isi.total,
                     "ISI (normalised)": k.isi.normalised, "hazardous inventory (kg)": k.hazardous_inventory_kg,
                     "high-risk units": len(k.high_risk_units), "max severity": k.max_severity})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    sel = st.selectbox("Alternative", system.alternative_names or [None], key="isi_alt")
    k = safety_kpis(system, sel, h_main, h_side, inter)
    c1, c2 = st.columns(2)
    c1.dataframe(pd.Series(k.isi.chemical, name="chemical sub-index").to_frame(), width="stretch")
    c2.dataframe(pd.Series(k.isi.process, name="process sub-index").to_frame(), width="stretch")
    st.markdown("**High-risk units:** " + (", ".join(k.high_risk_units) or "none"))
    if st.button("Use these KPIs as indicators (step 3)"):
        for r in rows:
            add_indicators(T, r["alternative"], {
                "ISI (normalised)": DataPoint(value=r["ISI (normalised)"], source="Heikkilä ISI (bioSSbD)",
                                              evidence="modelled"),
                "Hazardous inventory": DataPoint(value=r["hazardous inventory (kg)"], unit="kg",
                                                 source="bioSSbD hazard register", evidence="modelled")},
                "Inherent safety (ISI)", step=3)
        st.success("Added to all alternatives. See 7 · Evaluation.")
    with st.expander("Scoring bands used (edit in biossbd/safety/indices.py)"):
        st.json({"heat of reaction J/g": isi_mod.HEAT_OF_REACTION_BANDS,
                 "explosiveness UEL-LEL vol%": isi_mod.EXPLOSIVENESS_BANDS,
                 "inventory t (ISBL)": isi_mod.INVENTORY_ISBL_BANDS, "toxicity OEL ppm": isi_mod.TOXICITY_BANDS})

elif page == "5 · Environmental (LCA)":
    step_header(page, (10,))
    tid = tool_picker("Environmental sustainability", "lca", "openlca")
    if tid == "openlca":
        from biossbd.connectors import openlca as olc
        c = st.columns([1, 1, 2])
        port = c[0].number_input("IPC port", value=8080, step=1)
        if c[1].button("Connect", type="primary"):
            try:
                cl = olc.OpenLCA(int(port))
                with st.spinner("Reading the open openLCA database..."):
                    st.session_state.olca = {"systems": cl.product_systems(), "methods": cl.impact_methods(),
                                             "port": int(port)}
            except ConnectorError as e:
                st.session_state.olca = None
                st.error(f"{e}. In openLCA open a database, then Tools > Developer tools > IPC Server > Start.")
        data = st.session_state.get("olca")
        if data:
            st.success(f"Connected: {len(data['systems'])} product systems, {len(data['methods'])} LCIA methods.")
            with st.expander("Create a product system from a process"):
                qp = st.text_input("Process name contains", key="olca_q")
                if st.button("Find processes") and qp:
                    try:
                        st.session_state.olca_procs = olc.OpenLCA(data["port"]).processes(qp)
                    except ConnectorError as e:
                        st.error(str(e))
                procs = st.session_state.get("olca_procs") or []
                if procs:
                    pi = st.selectbox("Process", range(len(procs)), format_func=lambda i: procs[i].name)
                    if st.button("Create product system"):
                        try:
                            with st.spinner("Linking providers..."):
                                ps = olc.OpenLCA(data["port"]).create_product_system(procs[pi].id)
                            data["systems"].append(ps)
                            st.success(f"Created “{ps.name}”.")
                        except ConnectorError as e:
                            st.error(str(e))
            systems, methods = data["systems"], data["methods"]
            if systems and methods:
                c = st.columns([2, 2, 1])
                si = c[0].selectbox("Product system", range(len(systems)), format_func=lambda i: systems[i].name)
                mi = c[1].selectbox("LCIA method", range(len(methods)), format_func=lambda i: methods[i].name)
                amount = c[2].number_input("Amount (FU)", value=1.0, min_value=0.0)
                if st.button("Calculate in openLCA", type="primary"):
                    try:
                        with st.spinner("Calculating..."):
                            res = olc.OpenLCA(data["port"]).calculate(systems[si].id, methods[mi].id, amount)
                        st.session_state.lca_results = olc.to_indicators(
                            res, source=f"openLCA: {systems[si].name} / {methods[mi].name}")
                    except ConnectorError as e:
                        st.error(str(e))
            else:
                st.info("The open database has no product systems or no LCIA methods.")
            if methods:
                inventory_ui(data, methods)
    elif tid == "brightway":
        from biossbd.connectors import brightway as bw
        if bw.installed():
            try:
                projs = bw.projects()
            except Exception as e:
                projs = []
                st.error(f"Brightway error: {e}")
            if projs:
                c = st.columns(2)
                proj = c[0].selectbox("Project", projs, key="bw_proj")
                dbs = bw.databases(proj)
                db = c[1].selectbox("Database", dbs, key="bw_db") if dbs else None
                q = st.text_input("Search activities", key="bw_q", placeholder="e.g. biogas")
                if db and q:
                    acts = bw.search(proj, db, q)
                    if acts:
                        ai = st.selectbox("Activity", range(len(acts)), key="bw_act",
                                          format_func=lambda i: f"{acts[i].name} [{acts[i].location}] ({acts[i].unit})")
                        mf = st.text_input("Filter LCIA methods", "climate", key="bw_mf")
                        meths = bw.methods(proj, mf)
                        chosen = st.multiselect("LCIA methods", meths, format_func=lambda m: " | ".join(m),
                                                key="bw_meths")
                        amount = st.number_input("Amount", value=1.0, key="bw_amount")
                        if st.button("Calculate in Brightway", type="primary", disabled=not chosen):
                            with st.spinner("Calculating..."):
                                st.session_state.lca_results = bw.calculate(proj, acts[ai].key, chosen, amount)
                    else:
                        st.info("No activity found.")
            else:
                st.info("No Brightway projects found. Create one and import a database first.")
    elif tid == "qsdsan":
        st.markdown("Build and simulate process models (e.g. ADM1 anaerobic digestion) with QSDsan in Python, "
                    "then import the results:")
        st.code("from biossbd.sustainability import indicators_from_qsdsan, indicators_from_tea\n"
                "ind = indicators_from_qsdsan(lca, functional_unit=total_MJ) | indicators_from_tea(tea)\n"
                "# then add them to the alternative in your YAML or with biossbd.gui.state.add_indicators",
                language="python")
    elif tid == "owid":
        from biossbd.connectors import owid
        if st.button("Load latest country data", type="primary"):
            try:
                with st.spinner("Downloading from Our World in Data..."):
                    st.session_state.owid = owid.grid_carbon_intensity()
            except ConnectorError as e:
                st.error(str(e))
        df = st.session_state.get("owid")
        if df is not None:
            alts = alt_names()
            countries = df["country"].tolist()
            res = {}
            cols = st.columns(max(1, len(alts)))
            for i, a in enumerate(alts):
                ctry = cols[i].selectbox(a, countries, key=f"owid_{a}")
                r = df[df.country == ctry].iloc[0]
                cols[i].caption(f"{r.value:.0f} g CO2-eq/kWh ({int(r.year)})")
                res[a] = DataPoint(value=float(r.value), unit="g CO2-eq/kWh",
                                   source=f"Ember via Our World in Data, {ctry} {int(r.year)}", evidence="measured")
            dim = st.text_input("Dimension", "Environmental (context)", key="owid_dim")
            if st.button("Add grid carbon intensity to all alternatives"):
                for a, dp in res.items():
                    add_indicators(T, a, {"Grid carbon intensity": dp}, dim, step=10)
                st.success("Added. See 7 · Evaluation.")
    else:
        st.markdown("Enter values from literature, reports or other software, with their source.")
        man = st.data_editor(pd.DataFrame([{"indicator": "", "value": None, "unit": "", "source": "",
                                            "evidence": "literature"}]), num_rows="dynamic", hide_index=True,
                             key="man_env", column_config={"evidence": st.column_config.SelectboxColumn(
                                 "evidence", options=["measured", "modelled", "literature", "expert", "assumed"])})
        rows = [r for r in man.to_dict("records") if r["indicator"] and r["value"] is not None
                and not pd.isna(r["value"])]
        st.session_state.lca_results = {r["indicator"]: DataPoint(value=float(r["value"]), unit=r["unit"] or "",
                                                                  source=r["source"] or "manual entry",
                                                                  evidence=r["evidence"]) for r in rows} or None
    if tid in ("openlca", "brightway", "manual") and st.session_state.get("lca_results"):
        st.subheader("Review and attach results")
        add_results_ui(st.session_state.lca_results, "Environmental (LCA)", 10, f"lca_{tid}")

elif page == "6 · Socio-economic":
    step_header(page, (11,))
    tid = tool_picker("Socio-economic sustainability", "eco", "biogas-chp")
    if tid == "biogas-chp":
        from biossbd.examples import tea_presets_path
        presets = econ.load_presets(tea_presets_path())
        alts = alt_names()
        a = st.selectbox("Alternative", alts, key="bg_alt") if alts else None
        base = presets.get(a) or next(iter(presets.values()))
        if a not in presets:
            st.info("No preset for this alternative; starting from the first worked-example preset. Edit all values.")
        st.markdown("**Feedstocks** (methane yield per tonne as received)")
        fs = st.data_editor(pd.DataFrame([f.model_dump() for f in base.feedstocks]), num_rows="dynamic",
                            hide_index=True, key=f"bg_fs_{a}")
        c = st.columns(4)
        price = c[0].number_input(f"Electricity price ({base.currency}/kWh)", value=float(base.electricity_price),
                                  step=0.005, format="%.3f", key=f"bg_price_{a}")
        capex_kw = c[1].number_input(f"Specific CAPEX ({base.currency}/kWe)", value=float(base.specific_capex_per_kwe),
                                     step=100.0, key=f"bg_capex_{a}")
        om = c[2].number_input("Fixed O&M (% of CAPEX/yr)", value=base.fixed_om_share * 100, step=0.5,
                               key=f"bg_om_{a}") / 100
        rate = c[3].number_input("Discount rate (%)", value=base.discount_rate * 100, step=0.5, key=f"bg_r_{a}") / 100
        c = st.columns(4)
        eta = c[0].number_input("Electrical efficiency (%)", value=base.electrical_efficiency * 100, step=1.0,
                                key=f"bg_eta_{a}") / 100
        hours = c[1].number_input("Operating hours (h/yr)", value=float(base.operating_hours), step=100.0,
                                  key=f"bg_h_{a}")
        life = c[2].number_input("Lifetime (yr)", 1, 60, int(base.lifetime), key=f"bg_life_{a}")
        vom = c[3].number_input(f"Variable O&M ({base.currency}/kWh)", value=float(base.variable_om_per_kwh),
                                step=0.001, format="%.3f", key=f"bg_vom_{a}")
        try:
            feeds = [econ.Feedstock(**{k: v for k, v in r.items() if k in ("name", "tonnes_per_year",
                                                                          "methane_yield_m3_per_t", "source")
                                       and v is not None and not (isinstance(v, float) and pd.isna(v))})
                     for r in fs.to_dict("records") if r.get("name")]
            inp = base.model_copy(update=dict(feedstocks=feeds, electricity_price=price,
                                              specific_capex_per_kwe=capex_kw, fixed_om_share=om,
                                              discount_rate=rate, electrical_efficiency=eta, operating_hours=hours,
                                              lifetime=int(life), variable_om_per_kwh=vom))
            res, cf_in = econ.biogas_chp(inp)
            r = res.cash_flow
            m = st.columns(4)
            m[0].metric("Methane", f"{res.methane_m3_per_year:,.0f} m³/yr")
            m[1].metric("Electricity", f"{res.electricity_mwh_per_year:,.0f} MWh/yr")
            m[2].metric("CHP size", f"{res.electrical_capacity_kwe:,.1f} kWe")
            m[3].metric("CAPEX", f"{res.capex:,.0f} {inp.currency}")
            m = st.columns(4)
            m[0].metric("NPV", f"{r.npv:,.0f} {inp.currency}")
            m[1].metric("IRR", f"{r.irr * 100:.1f} %" if r.irr is not None else "—")
            m[2].metric("Payback", f"{r.simple_payback_years:.1f} yr" if r.simple_payback_years else "—")
            m[3].metric("Levelised cost", f"{r.levelised_cost:,.0f} {inp.currency}/MWh" if r.levelised_cost else "—")
            with st.expander("Sources and assumptions"):
                for k, v in inp.sources.items():
                    st.markdown(f"- **{k}**: {v}")
                st.caption("Plant size (tonnes/yr) and operating hours are assumptions; electricity is valued at "
                           "the avoided business tariff; heat is not valued unless a heat price is set.")
            dim = st.text_input("Dimension", "Economic (TEA)", key="bg_dim")
            if st.button("Add to alternative", type="primary", disabled=a is None, key="bg_add"):
                ind = econ.to_indicators(cf_in, r, source="bioSSbD biogas-CHP model; " + "; ".join(inp.sources.values()))
                ind["Electricity output"] = DataPoint(value=res.electricity_mwh_per_year, unit="MWh/yr",
                                                      source="bioSSbD biogas-CHP model", evidence="modelled")
                add_indicators(T, a, ind, dim, directions={**econ.DIRECTIONS, "Electricity output": "max"}, step=11)
                st.success(f"Added economic indicators to “{a}”.")
        except (ValueError, TypeError) as e:
            st.error(f"Check the inputs: {e}")
    elif tid == "cashflow":
        alts = alt_names()
        a = st.selectbox("Alternative", alts, key="cf_alt") if alts else None
        c = st.columns(4)
        cur = c[3].text_input("Currency", "EUR", key="cf_cur")
        capex = c[0].number_input(f"Capital investment ({cur})", value=1_000_000.0, step=10_000.0, min_value=0.0)
        opex = c[1].number_input(f"Operating cost ({cur}/yr)", value=80_000.0, step=1_000.0, min_value=0.0)
        rev = c[2].number_input(f"Revenue + avoided costs ({cur}/yr)", value=220_000.0, step=1_000.0, min_value=0.0)
        c = st.columns(4)
        life = c[0].number_input("Lifetime (yr)", 1, 100, 20)
        rate = c[1].number_input("Discount rate (%)", 0.0, 50.0, 8.0) / 100
        out = c[2].number_input("Annual output", value=0.0, min_value=0.0, help="Leave 0 to skip levelised cost")
        unit = c[3].text_input("Output unit", "MWh", key="cf_unit")
        inp = econ.CashFlowInput(capex=capex, opex=opex, revenue=rev, lifetime=int(life), discount_rate=rate,
                                 annual_output=out or None, output_unit=unit, currency=cur)
        r = econ.cash_flow(inp)
        m = st.columns(5)
        m[0].metric("NPV", f"{r.npv:,.0f} {cur}")
        m[1].metric("IRR", f"{r.irr * 100:.1f} %" if r.irr is not None else "—")
        m[2].metric("Payback", f"{r.simple_payback_years:.1f} yr" if r.simple_payback_years else "—")
        m[3].metric("Levelised cost", f"{r.levelised_cost:,.2f} {cur}/{unit}" if r.levelised_cost else "—")
        m[4].metric("Benefit/cost", f"{r.benefit_cost_ratio:.2f}" if r.benefit_cost_ratio else "—")
        dim = st.text_input("Dimension", "Economic (TEA)", key="cf_dim")
        if st.button("Add to alternative", type="primary", disabled=a is None):
            add_indicators(T, a, econ.to_indicators(inp, r), dim, directions=econ.DIRECTIONS, step=11)
            st.success(f"Added economic indicators to “{a}”.")
    elif tid == "qsdsan":
        st.code("from biossbd.sustainability import indicators_from_tea\nind = indicators_from_tea(tea)",
                language="python")
    else:
        st.markdown("Enter social or economic indicators (e.g. S-LCA scores, jobs, acceptance) with their source.")
        man = st.data_editor(pd.DataFrame([{"indicator": "", "value": None, "unit": "", "source": "",
                                            "evidence": "literature"}]), num_rows="dynamic", hide_index=True,
                             key="man_soc", column_config={"evidence": st.column_config.SelectboxColumn(
                                 "evidence", options=["measured", "modelled", "literature", "expert", "assumed"])})
        rows = [r for r in man.to_dict("records") if r["indicator"] and r["value"] is not None
                and not pd.isna(r["value"])]
        res = {r["indicator"]: DataPoint(value=float(r["value"]), unit=r["unit"] or "",
                                         source=r["source"] or "manual entry", evidence=r["evidence"]) for r in rows}
        if res:
            add_results_ui(res, "Social", 11, "soc")

elif page == "7 · Evaluation":
    step_header(page)
    st.caption("Results are read dimension by dimension, as recommended by the revised EC SSbD framework.")
    with st.expander("Indicator values (alternatives × indicators)"):
        editor("indicators", num_rows="fixed", keep_index=True)
    with st.expander("Indicator definitions"):
        editor("specs", column_config={
            "direction": st.column_config.SelectboxColumn("direction", options=["max", "min"]),
            "ordinal": st.column_config.CheckboxColumn("ordinal"),
            "step": st.column_config.NumberColumn("BioSSbD step", min_value=1, max_value=11, step=1)})
    with st.expander("Decision criteria"):
        editor("criteria", column_config={"operator": st.column_config.SelectboxColumn(
            "operator", options=[">=", "<=", ">", "<"])})
    ev = evaluation()
    if ev is None:
        st.info("Add indicators to the alternatives (steps 4-6) to see the evaluation.")
    else:
        incomplete = ev.values.isna().any()
        if incomplete.any():
            st.warning("Some alternatives lack values for: " + ", ".join(incomplete[incomplete].index)
                       + ". Fill them in above before comparing.")
        else:
            ds = ev.dimension_scores((1, 5))
            c1, c2 = st.columns([3, 2])
            with c1:
                show_fig(plots.dimension_bars(ds))
            with c2:
                if ds.shape[1] >= 3:
                    show_fig(plots.radar(ds))
            st.dataframe(ds.round(2), width="stretch")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Pareto-optimal:** {', '.join(ev.pareto_front())}")
                to = ev.tradeoffs()
                st.markdown("**Trade-offs between dimensions**")
                if to.empty:
                    st.write("None.")
                else:
                    st.dataframe(to, hide_index=True, width="stretch")
            with c2:
                st.markdown("**Best alternative per indicator**")
                st.dataframe(ev.best_by_indicator().to_frame(), width="stretch")
            cs = ev.criteria_summary()
            if not cs.empty:
                st.markdown("**Decision criteria**")
                st.dataframe(cs, hide_index=True, width="stretch")
            with st.expander("Full dashboard"):
                st.dataframe(ev.dashboard(), hide_index=True, width="stretch")

elif page == "8 · Robustness":
    step_header(page)
    tool_picker("Evaluation", "mcda", "mcda")
    ev = evaluation()
    if ev is None or ev.values.isna().any().any():
        st.info("Complete the indicator values in 7 · Evaluation first.")
    else:
        dims = ev.dimensions
        st.subheader("Dimension weights")
        wc = st.columns(len(dims))
        weights = {d: wc[i].slider(d, 0.0, 1.0, round(1.0 / len(dims), 2), 0.05, key=f"w_{d}")
                   for i, d in enumerate(dims)}
        if sum(weights.values()) == 0:
            weights = {d: 1.0 for d in dims}
        st.dataframe(ev.compare_methods(weights).round(3), width="stretch")
        st.caption("Compensation: " + ", ".join(f"{m} = {c}" for m, c in COMPENSATORY.items()))
        with st.expander("Weight at which the top-ranked alternative changes"):
            st.dataframe(pd.DataFrame({"dimension": dims, "threshold weight": [ev.weight_threshold(d) for d in dims]}),
                         hide_index=True, width="stretch")
        st.subheader("Monte Carlo")
        c = st.columns(4)
        method = c[0].selectbox("Aggregation rule", list(METHODS), key="rb_method")
        n = c[1].select_slider("Runs", [1000, 5000, 10000, 50000], value=10000)
        ps = c[2].checkbox("Perturb scores", True)
        pw = c[3].checkbox("Perturb weights", True)
        key = system_hash(current) + f"{method}{n}{ps}{pw}{sorted(weights.items())}"
        if st.button("Run Monte Carlo", type="primary"):
            st.session_state.robustness = (key, ev.robustness(n=n, method=method, perturb_scores=ps,
                                                              perturb_weights=pw, dimension_weights=weights))
        res = st.session_state.get("robustness")
        if res:
            rkey, r = res
            if rkey != key:
                st.warning("Inputs changed since this run; press Run again.")
            c1, c2 = st.columns(2)
            with c1:
                show_fig(plots.acceptability(r.rank_acceptability))
            with c2:
                st.dataframe(r.order_probability.to_frame().round(3), width="stretch")
                st.dataframe(r.summary.round(3), width="stretch")

elif page == "9 · PDCA":
    step_header(page)
    st.caption("Record the KPIs of successive design iterations; the Check gate passes when no tracked KPI gets worse.")
    with st.expander("BioSSbD PDCA checklist"):
        st.dataframe(pd.DataFrame(PDCA_CHECKLIST).T, width="stretch")
    cycle: Cycle = st.session_state.cycle
    ev = evaluation()
    with st.form("pdca_add"):
        c = st.columns(4)
        label = c[0].text_input("Iteration label", f"v{len(cycle.iterations)}")
        phase = c[1].selectbox("Phase", ["Plan", "Do", "Check", "Act"])
        alt_p = c[2].selectbox("Take KPIs from", system.alternative_names or [None])
        note = c[3].text_input("What changed")
        if st.form_submit_button("Record current KPIs"):
            kk = safety_kpis(system, alt_p)
            kpis = {"isi_normalised": kk.isi.normalised, "hazardous_inventory_kg": kk.hazardous_inventory_kg,
                    "high_risk_units": float(len(kk.high_risk_units))}
            cycle.directions["high_risk_units"] = "min"
            if ev is not None and alt_p in ev.alternatives and not ev.values.isna().any().any():
                for d, v in ev.dimension_scores((1, 5)).loc[alt_p].items():
                    kpis[f"score: {d}"] = round(float(v), 3)
                    cycle.directions[f"score: {d}"] = "max"
            try:
                cycle.add(Iteration(label=label, phase=phase, kpis=kpis, changes=[note] if note else []))
                st.success(f"Recorded {label}")
            except ValueError as e:
                st.error(str(e))
    if cycle.iterations:
        st.dataframe(cycle.history(), width="stretch")
        if len(cycle.iterations) >= 2:
            labels = [i.label for i in cycle.iterations]
            c = st.columns(2)
            b = c[0].selectbox("Before", labels, index=len(labels) - 2)
            a = c[1].selectbox("After", labels, index=len(labels) - 1)
            if a != b:
                st.dataframe(cycle.check(b, a), hide_index=True, width="stretch")
                if cycle.gate(b, a):
                    st.success("Check gate passed.")
                else:
                    st.error("Check gate not passed: a KPI got worse. Justify the trade-off or iterate.")
        if st.button("Clear iterations"):
            st.session_state.cycle = Cycle()
            st.rerun()
    else:
        st.info("Record the current design as v0, change the system, then record v1.")

elif page == "10 · Dossier":
    step_header(page)
    c = st.columns(3)
    author = c[0].text_input("Author")
    with_mcda = c[1].checkbox("Include aggregation and robustness", True)
    runs = c[2].select_slider("Monte Carlo runs", [0, 1000, 5000, 10000], value=5000)
    if st.button("Generate dossier", type="primary"):
        st.session_state.dossier = build_dossier(system, mcda=with_mcda, robustness_runs=runs, author=author)
    md = st.session_state.get("dossier")
    if md:
        st.download_button("Download dossier (Markdown)", md, file_name="ssbd_dossier.md", mime="text/markdown")
        with st.container(border=True):
            st.markdown(md)

elif page == "Tools & data sources":
    st.header("Tools & data sources")
    st.markdown("Methods, open-source libraries, applications and public databases that bioSSbD-py can use, with "
                "their licence and status on this computer. Install missing ones and restart the interface.")
    st.dataframe(registry.status_table(), hide_index=True, width="stretch",
                 column_config={"url": st.column_config.LinkColumn("website")})
    if st.button("Check connections"):
        from biossbd.connectors import http as h
        from biossbd.connectors import openlca as olc
        st.write("PubChem:", "reachable" if h.online("https://pubchem.ncbi.nlm.nih.gov") else "not reachable")
        st.write("Our World in Data:", "reachable" if h.online("https://ourworldindata.org") else "not reachable")
        if olc.installed():
            try:
                ok = olc.OpenLCA(8080).ping()
            except ConnectorError:
                ok = False
            st.write("openLCA IPC (port 8080):", "connected" if ok else "not running")
        else:
            st.write("openLCA IPC: olca-ipc not installed")

nav_buttons(page)
