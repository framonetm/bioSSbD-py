"""Bridges to process simulation, TEA and LCA libraries.

The adapters turn results from QSDsan/BioSTEAM and Brightway into
:class:`biossbd.dataquality.DataPoint` indicators that can be attached to an
alternative and evaluated with :class:`biossbd.evaluation.Evaluation`.
Both libraries are optional dependencies and are imported only when used:

    pip install "biossbd[qsdsan]"      # QSDsan + BioSTEAM
    pip install "biossbd[brightway]"   # Brightway 2.5
"""
from .brightway_adapter import indicators_from_brightway
from .qsdsan_adapter import indicators_from_qsdsan, indicators_from_tea

__all__ = ["indicators_from_brightway", "indicators_from_qsdsan", "indicators_from_tea"]
