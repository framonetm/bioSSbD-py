"""bioSSbD-py: an open-source toolbox for Safe-and-Sustainable-by-Design
assessment of process-based and bio-based systems.

Main entry points::

    from biossbd import load_system, safety_matrix, scoping_gaps, Evaluation
    from biossbd.safety import safety_kpis
    from biossbd.dossier import write_dossier
"""
__version__ = "0.1.0"

from .dataquality import DataPoint  # noqa: E402
from .evaluation import Evaluation  # noqa: E402
from .framework import COMPONENTS, PDCA_CHECKLIST, STEPS, steps_table  # noqa: E402
from .pdca import Cycle, Iteration  # noqa: E402
from .scoping import (  # noqa: E402
    Alternative, SSbDSystem, hazard_register, load_system, receptor_matrix, safety_matrix, scoping_gaps,
)
from .specs import IndicatorSpec  # noqa: E402
from . import registry  # noqa: E402

__all__ = [
    "Alternative", "COMPONENTS", "Cycle", "DataPoint", "Evaluation", "IndicatorSpec", "Iteration",
    "PDCA_CHECKLIST", "SSbDSystem", "STEPS", "__version__", "hazard_register", "load_system",
    "receptor_matrix", "registry", "safety_matrix", "scoping_gaps", "steps_table",
]
