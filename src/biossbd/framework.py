"""The BioSSbD methodology as data.

Encodes the 11-step assessment methodology, the nine safety-driven design
components and the Plan-Do-Check-Act (PDCA) checklist from

    Ramonet, F. (2026). Operationalizing BioSSbD: a safe-and-sustainable-by-design
    framework for biorefineries. Biofuels, Bioproducts and Biorefining.
    https://doi.org/10.1002/bbb.70178

and links them to the elements of the revised EC SSbD framework
(Garmendia Aguirre et al., 2025, JRC143022): scoping analysis, safety
assessment, environmental and socio-economic sustainability assessment,
evaluation and documentation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass(frozen=True)
class Step:
    number: int
    name: str
    description: str
    scope: str
    indicators: tuple[str, ...]
    criteria: str
    dimension: str  # safety | environmental | socio-economic
    ec_element: str  # element of the revised EC SSbD framework
    pdca: tuple[str, ...] = field(default_factory=tuple)


STEPS: tuple[Step, ...] = (
    Step(1, "Hazard identification",
         "Biological, chemical (e.g. H2S in biogas) and operational hazards specific to "
         "biorefineries, including microbial agents, feedstock contamination and combustible biofuels.",
         "Feedstocks, biorefinery processes",
         ("Type of hazard", "Severity of hazard"),
         "All relevant hazards identified before design",
         "safety", "Safety assessment", ("Plan",)),
    Step(2, "Risk and reliability assessment",
         "Risk matrices, FMEA and fault trees (IEC 31010:2019) to assess likelihood and severity "
         "of hazards and ensure system reliability.",
         "Biorefinery operations and design",
         ("Risk scores", "Fault tolerance", "Reliability indices"),
         "Risks controlled to acceptable thresholds",
         "safety", "Safety assessment", ("Plan", "Do")),
    Step(3, "Design integration and inherent safety",
         "Embedding safety in early design: substitution, minimisation, moderation, simplification.",
         "Early-stage design",
         ("Process safety index (normalised)", "Inherent safety metrics",
          "Hazardous inventory mass (kg)", "Substitution ratio (%)",
          "Number of high-risk units requiring active protection"),
         "Hazard reduction at source; demonstrable application of inherent safety principles",
         "safety", "Safety assessment", ("Do", "Check")),
    Step(4, "Control measures and operational safety",
         "Engineering and administrative controls and PPE to manage residual risks "
         "(e.g. H2S detection, fire suppression).",
         "Operational phase",
         ("Protocol effectiveness", "PPE compliance"),
         "Risk reduced to ALARA levels",
         "safety", "Safety assessment", ("Do",)),
    Step(5, "Monitoring, maintenance and reliability",
         "Continuous monitoring and TPM-based maintenance of critical systems.",
         "Maintenance and operations",
         ("Downtime", "Preventive actions", "Incident frequency"),
         "Preventive systems function as designed; incident rates minimised",
         "safety", "Safety assessment", ("Check", "Act")),
    Step(6, "Emergency preparedness and response",
         "Emergency planning and training for biorefinery-specific scenarios.",
         "Entire facility",
         ("Frequency of drills", "Plan effectiveness"),
         "Meets or exceeds emergency response standards",
         "safety", "Safety assessment", ("Do", "Act")),
    Step(7, "Compliance, auditing and regulation",
         "Ongoing review for compliance with safety and environmental rules (e.g. ATEX).",
         "Full system",
         ("Audit outcomes", "Corrective actions"),
         "Full regulatory alignment and continual improvement",
         "safety", "Documentation", ("Check",)),
    Step(8, "Communication, training and safety culture",
         "Safety communication and training adapted to biorefinery risks.",
         "Personnel and stakeholders",
         ("Training frequency", "Cultural maturity level"),
         "Strong safety awareness and engagement at all levels",
         "safety", "Scoping analysis (actors)", ("Do", "Act")),
    Step(9, "Continuous improvement and TQM",
         "Iterative improvement using TQM and kaizen.",
         "Entire life cycle",
         ("Number and effectiveness of improvements",),
         "Demonstrable, measurable improvements over time",
         "safety", "Evaluation", ("Act",)),
    Step(10, "Environmental sustainability (LCA)",
         "ISO 14040/44-aligned LCA covering GHG, energy, water, toxicity, land use, "
         "eutrophication, acidification, particulate matter, ozone formation, resources, biodiversity.",
         "Entire biorefinery life cycle",
         ("GHG intensity (kg CO2-eq/MJ)", "Cumulative energy demand (MJ/MJ)",
          "Water intensity (m3/t biomass)", "Toxicity indicators", "Land-use indicators"),
         "Impacts reduced relative to benchmark or baseline",
         "environmental", "Environmental sustainability assessment", ("Plan", "Check")),
    Step(11, "Social and economic sustainability",
         "Social acceptance, health impacts and cost externalities.",
         "Value chain and communities",
         ("SASWROIM", "Social acceptance", "Net benefit"),
         "Positive net impact; minimised risks; viable economics",
         "socio-economic", "Socio-economic sustainability assessment", ("Plan", "Check")),
)

COMPONENTS: tuple[str, ...] = (
    "Hazard identification",
    "Risk and reliability assessment",
    "Design integration",
    "Inherent safety principles",
    "Control measures",
    "Monitoring, maintenance and reliability",
    "Emergency preparedness",
    "Compliance and auditing",
    "Communication and training",
)

#: Mapping of design components to assessment steps.
COMPONENT_TO_STEPS: dict[str, tuple[int, ...]] = {
    "Hazard identification": (1,),
    "Risk and reliability assessment": (2,),
    "Design integration": (3,),
    "Inherent safety principles": (3,),
    "Control measures": (4,),
    "Monitoring, maintenance and reliability": (5, 9),
    "Emergency preparedness": (6,),
    "Compliance and auditing": (7,),
    "Communication and training": (8,),
}

PDCA_CHECKLIST: dict[str, dict[str, str]] = {
    "Plan": {
        "inputs": "Process flow diagram; feedstock data; preliminary mass and energy balances",
        "tools": "HAZID; screening FMEA; screening LCA (ISO 14040/44); preliminary TEA",
        "kpis": "Identified hazard categories; preliminary GHG intensity; major hotspot units",
        "gate": "Go/no-go for conceptual configuration; prioritised risk and sustainability hotspots",
    },
    "Do": {
        "inputs": "Selected configuration; material inventory; energy integration options",
        "tools": "Inherent safety principles (substitution, minimisation); heat integration; risk matrix refinement",
        "kpis": "Process safety index (baseline vs revised); projected GHG intensity; hazardous inventory mass",
        "gate": "Design freeze with embedded inherent safety and sustainability measures",
    },
    "Check": {
        "inputs": "Updated design; revised balances; operational assumptions",
        "tools": "Simplified inherent safety index; prospective LCA update; reliability check; targeted safety audit",
        "kpis": "Change in safety index; change in GHG; change in hazardous inventory; downtime risk",
        "gate": "Validation of directional improvement; confirmation of acceptable thresholds",
    },
    "Act": {
        "inputs": "Monitoring data (if operational) or updated assumptions",
        "tools": "KPI monitoring; audit review; continuous improvement loop (TQM/kaizen)",
        "kpis": "Incident frequency; energy intensity; emissions intensity; corrective actions",
        "gate": "Iterative design update; next-cycle improvement targets",
    },
}


def steps_table() -> pd.DataFrame:
    """Return the 11 steps as a DataFrame."""
    return pd.DataFrame(
        [
            {
                "step": s.number,
                "name": s.name,
                "dimension": s.dimension,
                "EC SSbD element": s.ec_element,
                "PDCA": ", ".join(s.pdca),
                "indicators": "; ".join(s.indicators),
                "criteria": s.criteria,
            }
            for s in STEPS
        ]
    ).set_index("step")


def get_step(number: int) -> Step:
    for s in STEPS:
        if s.number == number:
            return s
    raise KeyError(f"No BioSSbD step {number}; valid steps are 1-11")
