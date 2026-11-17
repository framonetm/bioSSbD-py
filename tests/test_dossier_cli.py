from biossbd.cli import main
from biossbd.dossier import build_dossier, md_table
from conftest import EXAMPLE

import pandas as pd


def test_md_table():
    assert md_table(pd.DataFrame()) == "_None._\n"
    s = md_table(pd.DataFrame({"a": [1.23456]}), index=False)
    assert "| a |" in s and "1.23" in s


def test_dossier_sections(acod):
    md = build_dossier(acod, robustness_runs=200)
    for h in ("## 1. Scoping analysis", "## 2. Safety assessment", "## 3. Sustainability and evaluation",
              "## 4. Data quality", "## 5. Coverage of the BioSSbD steps", "## 6. Limitations"):
        assert h in md
    assert "Pareto-optimal alternatives" in md
    assert "raw material" in md


def test_cli(tmp_path, capsys):
    assert main(["scope", str(EXAMPLE)]) == 0
    assert main(["gaps", str(EXAMPLE)]) == 0
    assert main(["safety", str(EXAMPLE)]) == 0
    assert main(["evaluate", str(EXAMPLE)]) == 0
    out = tmp_path / "d.md"
    assert main(["dossier", str(EXAMPLE), "-o", str(out), "--runs", "100"]) == 0
    assert out.read_text(encoding="utf-8").startswith("# SSbD dossier")
    assert "Pareto front" in capsys.readouterr().out
