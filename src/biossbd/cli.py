"""Command-line interface: ``biossbd scope|gaps|safety|evaluate|dossier FILE.yaml``."""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from .scoping import load_system, safety_matrix, scoping_gaps


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="biossbd", description="bioSSbD-py: open SSbD toolbox")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, hlp in (("scope", "print the life-cycle safety matrix"),
                      ("gaps", "list scoping gaps"),
                      ("safety", "print safety KPIs per alternative"),
                      ("evaluate", "print dimension scores and Pareto front"),
                      ("dossier", "write the SSbD dossier (Markdown)")):
        sp = sub.add_parser(name, help=hlp)
        sp.add_argument("file", help="SSbD system YAML file")
        if name == "scope":
            sp.add_argument("--alternative", "-a", default=None)
        if name == "dossier":
            sp.add_argument("--output", "-o", default="ssbd_dossier.md")
            sp.add_argument("--no-mcda", action="store_true")
            sp.add_argument("--runs", type=int, default=2000)
    g = sub.add_parser("gui", help="open the graphical interface in your browser")
    g.add_argument("--port", type=int, default=8501)
    args = p.parse_args(argv)
    if args.cmd == "gui":
        return launch_gui(args.port)
    system = load_system(args.file)
    pd.set_option("display.width", 160)

    if args.cmd == "scope":
        alt = args.alternative or (system.alternatives[0].name if system.alternatives else None)
        print(f"Life-cycle safety matrix ({alt or system.name})\n")
        print(safety_matrix(system, alt))
    elif args.cmd == "gaps":
        print(scoping_gaps(system).to_string(index=False))
    elif args.cmd == "safety":
        from .safety.assess import safety_kpis
        for alt in system.alternatives or [None]:
            k = safety_kpis(system, alt)
            print(f"{k.alternative}: ISI={k.isi.total} (normalised {k.isi.normalised}), "
                  f"hazardous inventory={k.hazardous_inventory_kg:g} kg, "
                  f"high-risk units={len(k.high_risk_units)}")
    elif args.cmd == "evaluate":
        from .evaluation import Evaluation
        ev = Evaluation.from_system(system)
        print(ev.dimension_scores((1, 5)).round(2))
        print("\nPareto front:", ", ".join(ev.pareto_front()))
    elif args.cmd == "dossier":
        from .dossier import write_dossier
        path = write_dossier(system, args.output, mcda=not args.no_mcda, robustness_runs=args.runs)
        print(f"Dossier written to {path}")
    return 0


def launch_gui(port: int = 8501) -> int:
    """Start the Streamlit app (requires ``pip install "biossbd[gui]"``)."""
    import importlib.util
    import subprocess
    from pathlib import Path

    if importlib.util.find_spec("streamlit") is None:
        print('The GUI needs Streamlit: pip install "biossbd[gui]"')
        return 1
    app = Path(__file__).resolve().parent / "gui" / "app.py"
    return subprocess.call([sys.executable, "-m", "streamlit", "run", str(app),
                            "--server.port", str(port), "--browser.gatherUsageStats", "false"])


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
