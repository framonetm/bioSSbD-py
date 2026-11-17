# bioSSbD-py – notes for Claude Code

Open-source toolbox and step-by-step GUI for Safe-and-Sustainable-by-Design (SSbD) assessment of process-based
and bio-based systems. Author: Fernando Ramonet (CSIC-ITEFI). Licence: MIT. Methodology: BioSSbD (Ramonet 2026,
Biofuels Bioprod. Bioref., doi:10.1002/bbb.70178) and the revised EC SSbD framework (JRC 2025).

## Environment (Windows, this machine)
- Virtual environment: `.venv` in this folder (Python 3.13). Always use `.\.venv\Scripts\python.exe`.
- Tests: `.\.venv\Scripts\python.exe -m pytest -q` (set `$env:BIOSSBD_ONLINE="1"` for live PubChem/OWID tests).
- GUI: `.\.venv\Scripts\python.exe -m biossbd.cli gui` (Streamlit, http://localhost:8501).
- Full setup and report: `powershell -ExecutionPolicy Bypass -File .\setup_and_test.ps1` -> `test_report.txt`.

## Layout
- `src/biossbd/scoping.py` SSbD system model (YAML), life-cycle safety matrix, scoping gaps
- `src/biossbd/hazards.py`, `safety/` GHS + process hazards, risk matrix/FMEA, Heikkilä ISI
- `src/biossbd/evaluation.py`, `mcda.py` dimension scores, Pareto, trade-offs, MCDA, vectorised Monte Carlo
- `src/biossbd/economics.py` cash flow (NPV, IRR, payback, LCOE) and biogas-CHP model; presets in `data/acod_tea_presets.yaml`
- `src/biossbd/connectors/` PubChem, openLCA (olca-ipc), Brightway 2.5, Our World in Data
- `src/biossbd/registry.py` tools per SSbD step with licence and status (drives the GUI choices)
- `src/biossbd/gui/` Streamlit app (`app.py`), table state (`state.py`, `tables.py`), plots
- `tests/` pytest; `test_evaluation.py` reproduces the published AcoD screening exactly – keep it passing
- `examples/acod/acod_system.yaml` worked example (copy in `src/biossbd/data/` must stay identical)

## Current priorities
1. **openLCA live connection.** openLCA 2 with a database open and the IPC server on port 8080
   (Tools > Developer tools > IPC Server; full setup guide in `docs/openlca_setup.md`). Verify `connectors/openlca.py` against the real server:
   list product systems and LCIA methods, create a product system from a process, calculate, attach results.
2. **LCA data for materials, transport and energy.** Free databases from openLCA Nexus (e.g. USLCI, Agribalyse,
   ELCD) or Brightway imports. Add a GUI helper to search processes (materials, transport t·km, electricity mixes)
   and build a simple inventory per alternative (amounts per functional unit) -> GHG and other impacts.
3. **Real data for TEA.** Keep every parameter sourced in the presets YAML (`sources:`); never invent numbers.
4. Keep the GUI step-by-step: each step offers a choice of method/tool from `registry.py`.

## Rules
- Every new number needs a source (or is labelled ASSUMPTION). Every new method needs a test.
- Do not change published-result tests to make code pass.
- Optional heavy libraries stay optional extras (`pyproject.toml`); core = numpy, pandas, pydantic, pyyaml.
- Do not commit `.venv`, test reports or credentials.
