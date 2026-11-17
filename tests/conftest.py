from pathlib import Path

import pytest

from biossbd import load_system

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "acod" / "acod_system.yaml"
L, CA, CO = "Lactoserum + manure", "Cacao husk + manure", "Coffee husk + manure"


@pytest.fixture(scope="session")
def acod():
    return load_system(EXAMPLE)
