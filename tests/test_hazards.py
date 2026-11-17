import pytest

from biossbd.hazards import PROCESS_HAZARDS, SUBSTANCES, classify_h, get_substance


def test_classify_h():
    assert classify_h("H220") == ("physical", "flammable", 5)
    assert classify_h("h330")[1] == "acute toxicity"
    assert classify_h("H360Fd")[2] == 5
    with pytest.raises(KeyError):
        classify_h("H999")


def test_library_codes_are_known():
    for s in SUBSTANCES.values():
        for c in s.h_codes:
            classify_h(c)


def test_h2s_is_very_toxic_and_flammable():
    s = get_substance("Hydrogen sulfide")
    assert "H330" in s.h_codes and "H220" in s.h_codes


def test_process_hazards_have_valid_severity():
    assert all(1 <= h.severity <= 5 for h in PROCESS_HAZARDS.values())
