import pytest

from biossbd import Cycle, Iteration


def test_check_gate():
    c = Cycle()
    c.add(Iteration(label="v0", phase="Plan", kpis={"isi_normalised": 0.40, "ghg_intensity": 0.05}))
    c.add(Iteration(label="v1", phase="Check", kpis={"isi_normalised": 0.30, "ghg_intensity": 0.04}))
    df = c.check("v0", "v1")
    assert df["improved"].all()
    assert c.gate("v0", "v1")
    c.add(Iteration(label="v2", phase="Check", kpis={"isi_normalised": 0.35, "ghg_intensity": 0.03}))
    assert not c.gate("v1", "v2")
    assert c.history().shape == (3, 2)
    with pytest.raises(ValueError):
        c.add(Iteration(label="v0", phase="Act"))
