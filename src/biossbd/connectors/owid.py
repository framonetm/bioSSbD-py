"""Our World in Data connector: country context indicators (CC BY 4.0).

Default indicator: lifecycle carbon intensity of electricity generation
(g CO2-eq/kWh), Ember with processing by Our World in Data.
"""
from __future__ import annotations

import io

import pandas as pd

from .http import get_text

GRAPHER = "https://ourworldindata.org/grapher"
CARBON_INTENSITY = "carbon-intensity-electricity"


def chart_csv(slug: str) -> pd.DataFrame:
    text = get_text(f"{GRAPHER}/{slug}.csv?v=1&csvType=full&useColumnShortNames=false", timeout=30)
    return pd.read_csv(io.StringIO(text))


def latest_by_country(df: pd.DataFrame) -> pd.DataFrame:
    """Latest year per country: columns country, code, year, value."""
    value_col = [c for c in df.columns if c not in ("Entity", "Code", "Year")][0]
    d = df.dropna(subset=[value_col])
    d = d[d["Code"].notna() & ~d["Code"].astype(str).str.startswith("OWID")]
    d = d.sort_values("Year").groupby("Entity", as_index=False).last()
    return d.rename(columns={"Entity": "country", "Code": "code", "Year": "year", value_col: "value"})[
        ["country", "code", "year", "value"]].reset_index(drop=True)


def grid_carbon_intensity() -> pd.DataFrame:
    return latest_by_country(chart_csv(CARBON_INTENSITY))
