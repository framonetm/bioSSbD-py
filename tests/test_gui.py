"""GUI tests: plots always; the Streamlit app only where Streamlit is installed."""
from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg")

from biossbd import Evaluation, safety_matrix  # noqa: E402
from biossbd.gui import plots  # noqa: E402
from biossbd.safety import risk_table  # noqa: E402
from conftest import CO, L  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "src" / "biossbd" / "gui" / "app.py"


def test_plots(acod):
    ev = Evaluation.from_system(acod)
    ds = ev.dimension_scores((1, 5))
    for fig in (plots.heatmap(safety_matrix(acod, CO)), plots.risk_matrix(risk_table(acod.get_alternative(L).risks)),
                plots.dimension_bars(ds), plots.radar(ds),
                plots.acceptability(ev.robustness(n=200).rank_acceptability)):
        assert fig.axes
        matplotlib.pyplot.close(fig)


def test_bundled_example_matches_examples_folder():
    from biossbd.examples import acod_path
    repo = Path(__file__).resolve().parents[1] / "examples" / "acod" / "acod_system.yaml"
    assert acod_path().read_text(encoding="utf-8") == repo.read_text(encoding="utf-8")


PAGES = ["Start", "1 · Scoping", "2 · Hazard identification", "3 · Risk & reliability", "4 · Inherent safety",
         "5 · Environmental (LCA)", "6 · Socio-economic", "7 · Evaluation", "8 · Robustness", "9 · PDCA",
         "10 · Dossier", "Tools & data sources"]


def _app():
    st_testing = pytest.importorskip("streamlit.testing.v1")
    at = st_testing.AppTest.from_file(str(APP), default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    return at


def test_app_starts():
    at = _app()
    assert any("All inputs valid" in s.value for s in at.sidebar.success)


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders(page):
    at = _app()
    at.sidebar.radio(key="page").set_value(page).run()
    assert not at.exception, at.exception


def test_robustness_and_dossier_buttons():
    at = _app()
    at.sidebar.radio(key="page").set_value("8 · Robustness").run()
    next(b for b in at.button if b.label == "Run Monte Carlo").click().run()
    assert not at.exception, at.exception
    at.sidebar.radio(key="page").set_value("10 · Dossier").run()
    next(b for b in at.button if b.label == "Generate dossier").click().run()
    assert not at.exception, at.exception


def test_lca_inventory_end_to_end(monkeypatch):
    """Step 5 inventory with a fake openLCA server: add a line, calculate, attach GHG totals."""
    from types import SimpleNamespace as R

    from biossbd.connectors import openlca as olc

    class FakeOLCA:
        def __init__(self, port=8080):
            pass
        def processes(self, q, limit=50):
            return [olc.Item("p-lorry", "transport, freight, lorry")]
        def reference(self, pid):
            return "transport, freight, lorry", "t*km"
        def unit_impacts(self, pid, mid):  # synthetic test value
            return [olc.ImpactResult("Climate change", "kg CO2 eq", 0.1)]

    monkeypatch.setattr(olc, "OpenLCA", FakeOLCA)
    at = _app()
    at.session_state["olca"] = {"systems": [], "methods": [R(id="m1", name="EF 3.1")], "port": 8080}
    at.sidebar.radio(key="page").set_value("5 · Environmental (LCA)").run()
    at.text_input(key="inv_q").set_value("lorry").run()
    at.button(key="inv_search").click().run()
    at.number_input(key="inv_amt").set_value(50.0).run()
    at.text_input(key="inv_src").set_value("haulage records").run()
    at.button(key="inv_add").click().run()
    assert at.session_state["inv_table"].iloc[0]["unit"] == "t*km"
    at.button(key="inv_calc").click().run()
    assert not at.exception, at.exception
    at.button(key="inv_attach_btn").click().run()
    assert not at.exception, at.exception
    alt = at.session_state["inv_table"].iloc[0]["alternative"]
    assert at.session_state["T"]["indicators"].loc[alt, "Climate change"] == pytest.approx(5.0)


def test_cash_flow_adds_indicators():
    at = _app()
    at.sidebar.radio(key="page").set_value("6 · Socio-economic").run()
    next(b for b in at.button if b.label == "Add to alternative").click().run()
    assert not at.exception, at.exception
    at.sidebar.radio(key="page").set_value("7 · Evaluation").run()
    assert not at.exception, at.exception
