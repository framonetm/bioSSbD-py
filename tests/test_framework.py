from biossbd.framework import COMPONENT_TO_STEPS, COMPONENTS, PDCA_CHECKLIST, STEPS, get_step, steps_table


def test_eleven_steps_and_nine_components():
    assert [s.number for s in STEPS] == list(range(1, 12))
    assert len(COMPONENTS) == 9
    assert set(COMPONENT_TO_STEPS) == set(COMPONENTS)


def test_pdca_checklist_complete():
    assert list(PDCA_CHECKLIST) == ["Plan", "Do", "Check", "Act"]
    for phase in PDCA_CHECKLIST.values():
        assert set(phase) == {"inputs", "tools", "kpis", "gate"}


def test_steps_table_and_lookup():
    t = steps_table()
    assert t.shape[0] == 11
    assert get_step(10).dimension == "environmental"
