"""Editable-table state helpers for the GUI (no Streamlit import; unit-tested).

The GUI keeps one dict of DataFrames (see :mod:`biossbd.gui.tables`) as the
single source of truth. Editors report their changes as Streamlit's
``{"edited_rows", "added_rows", "deleted_rows"}`` dict, applied here.
"""
from __future__ import annotations

import math

import pandas as pd

from ..dataquality import DataPoint
from .tables import SHARED  # noqa: F401  (re-exported for the app)


def apply_editor_changes(df: pd.DataFrame, changes: dict, keep_index: bool = False) -> pd.DataFrame:
    """Apply a Streamlit data_editor change set to a DataFrame (positional rows)."""
    out = df.copy()
    for r, cols in (changes.get("edited_rows") or {}).items():
        i = int(r)
        for c, v in cols.items():
            if c not in out.columns:
                continue
            j = out.columns.get_loc(c)
            try:
                out.iloc[i, j] = v
            except (TypeError, ValueError):
                out[c] = out[c].astype(object)
                out.iloc[i, j] = v
    deleted = changes.get("deleted_rows") or []
    if deleted:
        out = out.drop(out.index[[int(i) for i in deleted]])
    added = [r for r in (changes.get("added_rows") or []) if r]
    if added:
        new = pd.DataFrame(added).reindex(columns=out.columns)
        out = pd.concat([out.astype(object), new.astype(object)], ignore_index=not keep_index)
    if not keep_index:
        out = out.reset_index(drop=True)
    return out.infer_objects()


def sync_indicator_rows(tables: dict) -> None:
    """Keep one indicator row per alternative (adds new ones, drops removed ones)."""
    alts = [a for a in tables["alternatives"]["name"].tolist() if isinstance(a, str) and a.strip()]
    ind = tables["indicators"]
    if list(ind.index) != alts:
        new = ind.reindex(alts)
        new.index.name = "alternative"
        tables["indicators"] = new


def add_indicators(tables: dict, alternative: str, indicators: dict[str, DataPoint], dimension: str,
                   directions: dict[str, str] | None = None, step: int | None = None,
                   default_direction: str = "min") -> list[str]:
    """Attach indicator values to one alternative and create their definitions if missing."""
    sync_indicator_rows(tables)
    ind = tables["indicators"]
    specs = tables["specs"]
    added = []
    for name, dp in indicators.items():
        if name not in ind.columns:
            ind[name] = float("nan")
        ind.loc[alternative, name] = dp.value
        tables["indicator_meta"][(alternative, name)] = dp.model_dump(exclude={"value"})
        if specs.empty or name not in set(specs["name"]):
            row = {"name": name, "dimension": dimension,
                   "direction": (directions or {}).get(name, default_direction), "unit": dp.unit,
                   "scale_min": None, "scale_max": None, "weight": 1.0, "ordinal": False, "step": step,
                   "description": dp.source}
            specs = pd.concat([specs, pd.DataFrame([row])], ignore_index=True)
        added.append(name)
    tables["specs"] = specs
    tables["indicators"] = ind
    return added


def upsert_substance(tables: dict, sub: dict, alternative: str = SHARED) -> None:
    """Add a substance row, replacing one with the same name and alternative."""
    df = tables["substances"]
    row = {"alternative": alternative, "name": sub["name"], "cas": sub.get("cas", ""), "role": sub.get("role", ""),
           "h_codes": ", ".join(sub.get("h_codes", [])), "flash_point_c": sub.get("flash_point_c"),
           "lel_vol": sub.get("lel_vol"), "uel_vol": sub.get("uel_vol"), "oel_ppm": sub.get("oel_ppm")}
    if not df.empty:
        same = (df["name"].astype(str).str.lower() == sub["name"].lower()) & (df["alternative"] == alternative)
        df = df[~same]
    tables["substances"] = pd.concat([df.astype(object), pd.DataFrame([row]).astype(object)],
                                     ignore_index=True).infer_objects()


def is_blank(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x)) or (isinstance(x, str) and not x.strip())
