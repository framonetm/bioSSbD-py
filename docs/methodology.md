# Methodology

## Mapping to the frameworks

| BioSSbD step | Module | Revised EC SSbD element | PDCA |
| --- | --- | --- | --- |
| 1 Hazard identification | `scoping.hazard_register`, `hazards` | Safety assessment | Plan |
| 2 Risk and reliability | `safety.risk` | Safety assessment | Plan, Do |
| 3 Design integration and inherent safety | `safety.indices`, `safety.assess` | Safety assessment | Do, Check |
| 4–9 Operational safety, maintenance, emergency, compliance, training, TQM | documented in the dossier (`framework.STEPS`) | Safety assessment, documentation | Do–Act |
| 10 Environmental sustainability | `sustainability` adapters, `evaluation` | Environmental sustainability assessment | Plan, Check |
| 11 Social and economic sustainability | `sustainability` adapters, `evaluation` | Socio-economic sustainability assessment | Plan, Check |
| — | `scoping.scoping_gaps` | Scoping analysis | Plan |
| — | `evaluation.Evaluation` | Evaluation | Check |
| — | `dossier`, `pdca` | Documentation | Act |

## Scoping analysis

The SSbD system is a set of life-cycle stages, units assigned to stages, substances handled in units, and actors
engaged per stage. Alternatives (SSbD scenarios) add their own units, substances, risks and indicators to the shared
system. The **life-cycle safety matrix** is the maximum screening severity of all hazards reaching each stage;
the **receptor matrix** shows who is exposed (workers, public, installation, environment, soil, water).

Scoping gaps are reported when:
- a stage has identified hazards but no safety assessment (high priority);
- a stage has neither hazards nor a safety screening (medium);
- a stage inside the LCA boundary has no environmental assessment (medium);
- no actor is engaged for a stage (medium).

## Screening severity

GHS hazard statements are mapped to an ordinal severity (1–5) for screening only (`hazards.H_STATEMENTS`).
Biological and process hazards carry their own default severity (`hazards.PROCESS_HAZARDS`).

## Inherent Safety Index

Heikkilä (1999): chemical sub-index (heat of main and side reactions, chemical interaction, flammability,
explosiveness, toxic exposure, corrosivity; worst substance per property) plus process sub-index (inventory,
temperature, pressure, equipment, structure; worst unit per property). Lower is safer. The normalised ISI divides
by the maximum attainable score. Band tables are in `safety/indices.py`; check them against the original source
before regulatory use.

## Evaluation

Each indicator is mapped to [0, 1] with 1 = best, using fixed scale bounds (ordinal scores) or min–max across
alternatives (ratio indicators). Dimension scores are weighted means inside each dimension. With ordinal 1–5
indicators and `output_range=(1, 5)` this reproduces a classic scoring table.

The default reading is non-aggregated: dimension scores, rank per indicator, decision criteria, Pareto dominance
and trade-offs between dimensions. Aggregation rules differ in compensation: weighted sum and TOPSIS are fully
compensatory, geometric mean and PROMETHEE II partially, maximin not at all.

Robustness: ordinal scores move by −1/0/+1 with probabilities 0.25/0.5/0.25 (clipped to the scale); indicators with a
(low, high) range are drawn uniformly; weights are drawn from Dirichlet distributions (concentration 20 around the
base weights inside dimensions, flat across dimensions). Outputs: rank acceptability, probability of each full
order, and score percentiles.

## References

- Garmendia Aguirre, I. et al. (2025). *Safe and Sustainable by Design Chemicals and Materials. Revised framework (2025)*. JRC143022.
- Garmendia Aguirre, I. et al. (2026). The importance of the life cycle perspective for safety assessment in the European Commission's Safe and Sustainable by Design Framework. *Front. Toxicol.* 8:1909986.
- Heikkilä, A.-M. (1999). *Inherent safety in process plant design: an index-based approach*. VTT Publications 384.
- Ramonet, F. (2026). Operationalizing BioSSbD: a safe-and-sustainable-by-design framework for biorefineries. *Biofuels, Bioprod. Bioref.* doi:10.1002/bbb.70178.
- Li, Y. et al. (2022). QSDsan: an integrated platform for quantitative sustainable design of sanitation and resource recovery systems. *Environ. Sci.: Water Res. Technol.* 8, 2289–2303.
