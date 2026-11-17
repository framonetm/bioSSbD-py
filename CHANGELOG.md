# Changelog

## Unreleased
- `biossbd.lca_inventory`: inventory per alternative (materials, transport in t*km, energy) from background
  processes; totals are linear sums of amount × unit impact, with provenance per line (unsourced = ASSUMPTION)
- openLCA connector: `unit_impacts` (process target, falls back to a product system), `reference` (reference
  flow and unit), impact method passed with an explicit ref type
- GUI step 5 (openLCA): process search, inventory table with CSV load/save, contribution chart, attach GHG
  (or other) totals to every alternative

## 0.1.0 – step-by-step interface and connectors (2026-11-13)
- GUI rebuilt as a guided assessment (Start → Scoping → Hazard identification → Risk → Inherent safety →
  Environmental → Socio-economic → Evaluation → Robustness → PDCA → Dossier) with a method/tool choice per step
- `biossbd.registry`: methods, libraries, applications and databases per step with licence and live status
- `biossbd.connectors`: PubChem (search, GHS statements with notification shares, flash point, explosive and
  exposure limits), openLCA 2 via IPC, Brightway 2.5, Our World in Data (electricity carbon intensity)
- `biossbd.economics`: screening cash-flow model (NPV, IRR, payback, levelised cost, benefit-cost ratio)
- Indicators added from any tool keep their source and evidence type

## 0.1.0 – graphical interface (2026-11-13)
- Streamlit GUI (`biossbd gui`) with seven tabs: overview, scoping, safety, evaluation, robustness, PDCA, dossier
- Editable tables with live validation and YAML download
- `biossbd.gui.plots`: safety heatmaps, risk matrix, dimension bars, radar, rank acceptability
- Monte Carlo robustness vectorised (10,000 runs in well under a second)
- Example system bundled in the package (`biossbd.examples.acod()`)

## 0.1.0 (2026-11-13)
First public version.
- Scoping analysis: YAML-defined SSbD system, life-cycle safety and receptor matrices, scoping-gap check
- Hazard libraries: GHS hazard statements, common biorefinery substances, biological and process hazards
- Safety: risk matrix and FMEA, Heikkilä Inherent Safety Index, hazardous inventory KPIs
- Evaluation: dimension-level dashboard, Pareto dominance, trade-offs, decision criteria;
  MCDA (weighted sum, geometric mean, TOPSIS, PROMETHEE II, maximin) and Monte Carlo robustness
- PDCA iteration tracking with the Check gate
- Markdown SSbD dossier and command-line interface
- Experimental adapters for QSDsan/BioSTEAM and Brightway 2.5
- Worked example (anaerobic co-digestion) reproducing a published screening study; five tutorial notebooks
