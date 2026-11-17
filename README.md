# bioSSbD-py

**An open-source toolbox for Safe-and-Sustainable-by-Design (SSbD) assessment of process-based and bio-based systems.**

bioSSbD-py turns the [revised EC SSbD framework](https://publications.jrc.ec.europa.eu/repository/handle/JRC143022) (JRC, 2025) and the
[BioSSbD methodology for biorefineries](https://doi.org/10.1002/bbb.70178) (Ramonet, 2026) into code you can run, test and cite:

| Framework element | What the toolbox does |
| --- | --- |
| **Scoping analysis** | Describe the SSbD system (substances, units, life-cycle stages, actors, alternatives) in one YAML file; build the life-cycle **safety matrix** (stage × hazard × receptor); report **scoping gaps** |
| **Safety assessment** | GHS and biological/process hazard libraries; risk matrix and FMEA; Heikkilä **Inherent Safety Index**; hazardous inventory KPIs |
| **Sustainability assessment** | Indicators with provenance and uncertainty; experimental adapters for **QSDsan/BioSTEAM** (process models incl. ADM1, TEA, LCA) and **Brightway 2.5** |
| **Evaluation** | Dimension-level dashboard without a single score, Pareto dominance, explicit trade-offs, decision criteria; MCDA (weighted sum, geometric mean, TOPSIS, PROMETHEE II, maximin) and **Monte Carlo robustness** as a sensitivity layer |
| **Documentation** | Markdown **SSbD dossier**; Plan-Do-Check-Act iteration tracking with the Check gate |

Safety is assessed at **every life-cycle stage**, not only where a chemical is handled, so that safety and sustainability share one
system boundary, as the revised framework's Scoping Analysis requires.

## Install

```bash
pip install -e .                      # core (numpy, pandas, pydantic, pyyaml)
pip install -e ".[dev,notebooks]"     # + tests and tutorial notebooks
pip install -e ".[qsdsan,brightway]"  # + process models, TEA and LCA (Python >= 3.12)
pip install -e ".[gui]"               # + graphical interface (Streamlit)
```

On Windows, QSDsan needs the *Microsoft C++ Build Tools* to compile one dependency (`numpoly`),
or use conda-forge: `conda install -c conda-forge numpoly chaospy` before `pip install qsdsan`.

## Graphical interface: a step-by-step assessment

```bash
pip install -e ".[gui]"          # add ",openlca,brightway,qsdsan" for the LCA engines
biossbd gui                      # opens http://localhost:8501
```

On Windows you can run `start_gui.ps1`. The sidebar leads through the assessment. At every step you choose the
method, open-source tool or public database to use, and each option shows its licence and whether it is ready on
your computer:

| Step | Methods, tools and data sources |
| --- | --- |
| Start | Open the worked example, a YAML file or a new system; describe the innovation and alternatives |
| 1 · Scoping | Stages, actors, units, assessments; **substance finder (PubChem)** or built-in library; life-cycle safety matrix; scoping gaps |
| 2 · Hazard identification | Built-in GHS/process-hazard library or **PubChem** look-up of all substances, with review |
| 3 · Risk & reliability | Risk matrix and FMEA |
| 4 · Inherent safety | Heikkilä Inherent Safety Index, hazardous inventory |
| 5 · Environmental (LCA) | **openLCA 2** (product systems + LCIA methods via IPC), **Brightway 2.5** (projects, activities, methods), QSDsan results, **Our World in Data** grid carbon intensity, or manual entry with provenance |
| 6 · Socio-economic | Screening cash-flow model (NPV, IRR, payback, levelised cost), QSDsan/BioSTEAM TEA, manual S-LCA indicators |
| 7 · Evaluation | Dimension scores, Pareto front, trade-offs, criteria |
| 8 · Robustness | Weights, five aggregation rules, Monte Carlo rank acceptability |
| 9 · PDCA | Design iterations and the Check gate |
| 10 · Dossier | Generate and download the SSbD dossier |
| Tools & data sources | Status, licence and installation of every connector |

Every value keeps its source and evidence type; download the whole system as YAML from the sidebar.

### Connecting openLCA

1. Install [openLCA 2](https://www.openlca.org) and import a database (free ones on [openLCA Nexus](https://nexus.openlca.org), e.g. USLCI, Agribalyse, ELCD).
2. Open the database, then **Tools → Developer tools → IPC Server → Start** (port 8080).
3. `pip install "biossbd[openlca]"`, then in step 5 choose openLCA and press **Connect**.

The LCIA methods must use the same elementary-flow list as the database (e.g. FEDEFL for USLCI); otherwise
openLCA returns 0 for every impact without an error. bioSSbD-py raises `MethodMismatchError` in that case, and
`OpenLCA.method_coverage()` shows how many inventory flows a method characterises. Full guide and checks:
[docs/openlca_setup.md](docs/openlca_setup.md). The openLCA connector is **experimental**: listing, process
search and direct process calculation are verified against openLCA 2 with USLCI; impact totals still await a
matching LCIA method set.

### Connecting Brightway

Create a Brightway 2.5 project and import a database (e.g. ecoinvent with your licence via `ecoinvent_interface`,
or free data with `bw2io`). Step 5 lists your projects, databases, activities and LCIA methods.

## Quick start

```python
from biossbd import load_system, safety_matrix, scoping_gaps, Evaluation
from biossbd.safety import safety_kpis

system = load_system("examples/acod/acod_system.yaml")

safety_matrix(system, "Coffee husk + manure")    # stage x hazard group, max severity 1-5
scoping_gaps(system)                              # what the scoping still misses
safety_kpis(system, "Lactoserum + manure").isi    # Inherent Safety Index

ev = Evaluation.from_system(system)
ev.dimension_scores((1, 5))                       # read dimension by dimension
ev.pareto_front(), ev.tradeoffs()
ev.robustness(n=10_000, perturb_weights=True).rank_acceptability
```

Command line:

```bash
biossbd scope    examples/acod/acod_system.yaml
biossbd gaps     examples/acod/acod_system.yaml
biossbd evaluate examples/acod/acod_system.yaml
biossbd dossier  examples/acod/acod_system.yaml -o acod_dossier.md
```

## Worked example and validation

`examples/acod/` models manure-centred anaerobic co-digestion with cheese whey, cacao husk and coffee husk.
Its scores come from a published screening study, and `tests/test_evaluation.py` checks that the toolbox
reproduces that study's dimension scores, all five aggregation rules and the environmental-weight
threshold exactly. Unit inventories in the example are illustrative placeholders.

## Tutorials

The `notebooks/` folder doubles as course material:

1. Scoping analysis – the SSbD system and the life-cycle safety matrix
2. Safety assessment – risk, reliability and inherent safety
3. Evaluation and robustness – trade-offs before rankings
4. Documentation and PDCA – the dossier and the Check gate
5. Bridge to process models and LCA databases (experimental)

## Design principles

- **Transparent before aggregated.** Results are read per dimension; aggregation is a sensitivity check.
- **Provenance everywhere.** Every value records its source and evidence type (measured, modelled, literature, expert, assumed).
- **Screening defaults are editable.** Hazard severities and index bands are module-level tables you can inspect and override.
- **Build on, don't fork.** Process modelling, TEA and LCA come from QSDsan/BioSTEAM and Brightway as optional dependencies.

## Limitations

Version 0.1 is a screening tool. Verify substance classifications against the ECHA C&L Inventory or current safety data sheets.
Ordinal scores are comparative, not measurements. The QSDsan and Brightway adapters are experimental; an ADM1-based process model
of the AcoD example is planned for 0.2.

## Citing

See `CITATION.cff`. Please also cite the methods you use (Heikkilä 1999 for the ISI; QSDsan, BioSTEAM and Brightway where applicable).

## Licence

MIT. Contributions welcome – see `CONTRIBUTING.md`.
