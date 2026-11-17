"""Matplotlib figures used by the GUI and the notebooks."""
from __future__ import annotations

import textwrap

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, ListedColormap

SEVERITY_CMAP = LinearSegmentedColormap.from_list(
    "severity", ["#f4f4f4", "#fde7a9", "#f9b45a", "#ef7b3e", "#d43d2a", "#8e1b1b"], N=6)
PALETTE = ["#2f6db3", "#e08a2b", "#3a9a5b", "#b8423c", "#7a5ab8", "#8c6d31", "#4ba3b5"]


def heatmap(m: pd.DataFrame, title: str = "", vmax: float = 5, cmap=SEVERITY_CMAP, fmt: str = "{:.0f}"):
    fig, ax = plt.subplots(figsize=(1.2 + 1.05 * max(1, m.shape[1]), 0.9 + 0.5 * max(1, m.shape[0])))
    if m.empty or m.shape[1] == 0:
        ax.text(0.5, 0.5, "No hazards identified", ha="center", va="center")
        ax.axis("off")
        return fig
    ax.imshow(m.to_numpy(float), cmap=cmap, vmin=0, vmax=vmax, aspect="auto")
    ax.set_xticks(range(m.shape[1]), [textwrap.fill(str(c), 16) for c in m.columns], rotation=35, ha="right")
    ax.set_yticks(range(m.shape[0]), [str(i) for i in m.index])
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            v = m.iat[i, j]
            ax.text(j, i, fmt.format(v), ha="center", va="center",
                    color="white" if v >= 0.7 * vmax else "black", fontsize=9)
    ax.set_title(title, fontsize=11, loc="left")
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.tight_layout()
    return fig


def risk_matrix(rt: pd.DataFrame, title: str = "Risk matrix"):
    """Impact x likelihood grid. Risks are numbered markers (key in the legend below),
    spread inside their cell so that coincident risks never overlap."""
    fig, ax = plt.subplots(figsize=(6.4, 6.6))
    grid = np.add.outer(np.arange(1, 6), np.arange(1, 6)) / 2  # mean of I and L
    cmap = ListedColormap(["#cfe8cf", "#eef3b5", "#fde7a9", "#f6b26b", "#e06666"])
    ax.imshow(np.digitize(grid, [1.5, 2.5, 3.5, 4.5]), cmap=cmap, origin="lower",
              extent=(0.5, 5.5, 0.5, 5.5), alpha=0.9)
    if not rt.empty:
        rt = rt.reset_index(drop=True)
        offsets = [(0, 0), (-0.22, 0.2), (0.22, 0.2), (-0.22, -0.2), (0.22, -0.2), (0, 0.32), (0, -0.32)]
        k = rt.groupby(["likelihood", "impact"]).cumcount()
        n_in_cell = rt.groupby(["likelihood", "impact"])["risk"].transform("count")
        for i, r in rt.iterrows():
            j = int(k[i]) if n_in_cell[i] > 1 else 0
            dx, dy = offsets[(j + (1 if n_in_cell[i] > 1 else 0)) % len(offsets)] if n_in_cell[i] > 1 else (0, 0)
            x, y = r["likelihood"] + dx, r["impact"] + dy
            ax.scatter([x], [y], s=330, color="#1f2d3d", zorder=3, edgecolors="white", linewidths=1.2)
            ax.text(x, y, str(i + 1), color="white", ha="center", va="center", fontsize=9, weight="bold", zorder=4)
        key = "\n".join(textwrap.fill(f"{i + 1}. {r['risk']}", 42) for i, r in rt.iterrows())
        ax.text(0.0, -0.13, key, transform=ax.transAxes, ha="left", va="top", fontsize=8.5)
    ax.set(xlim=(0.5, 5.5), ylim=(0.5, 5.5), xticks=range(1, 6), yticks=range(1, 6),
           xlabel="Likelihood (1-5)", ylabel="Impact (1-5)")
    ax.set_title(title, fontsize=11, loc="left")
    fig.tight_layout()
    return fig


def dimension_bars(ds: pd.DataFrame, lo: float = 1, hi: float = 5):
    fig, ax = plt.subplots(figsize=(8, 3.8))
    n = ds.shape[0]
    width = 0.8 / max(n, 1)
    x = np.arange(ds.shape[1])
    for i, (alt, row) in enumerate(ds.iterrows()):
        ax.bar(x + (i - (n - 1) / 2) * width, row.to_numpy(), width, label=alt, color=PALETTE[i % len(PALETTE)])
    ax.set_xticks(x, [textwrap.fill(str(c), 14) for c in ds.columns], rotation=0, fontsize=8.5)
    ax.set_ylim(lo if lo > 0 else 0, hi)
    ax.set_ylabel(f"score ({lo:g} worst - {hi:g} best)")
    ax.legend(fontsize=8, frameon=False, ncols=min(n, 3), loc="upper center", bbox_to_anchor=(0.5, -0.18))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def radar(ds: pd.DataFrame, lo: float = 1, hi: float = 5):
    labels = [textwrap.fill(str(c), 14) for c in ds.columns]
    k = len(labels)
    ang = np.linspace(0, 2 * np.pi, k, endpoint=False).tolist()
    ang += ang[:1]
    fig, ax = plt.subplots(figsize=(5.6, 6.2), subplot_kw={"polar": True})
    for i, (alt, row) in enumerate(ds.iterrows()):
        v = row.tolist() + row.tolist()[:1]
        c = PALETTE[i % len(PALETTE)]
        ax.plot(ang, v, color=c, lw=2, label=alt)
        ax.fill(ang, v, color=c, alpha=0.12)
    ax.set_xticks(ang[:-1], labels, fontsize=8.5)
    ax.tick_params(axis="x", pad=14)
    ax.set_ylim(lo - 1 if lo >= 1 else 0, hi)
    ax.set_rlabel_position(90 / k)
    ax.tick_params(axis="y", labelsize=7, colors="#666666")
    ax.legend(fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.08), frameon=False,
              ncols=min(len(ds), 2))
    fig.tight_layout()
    return fig


def inventory_contributions(t: pd.DataFrame, unit: str = "", title: str = ""):
    """Horizontal stacked bars: alternatives x inventory categories (material, transport, ...)."""
    fig, ax = plt.subplots(figsize=(8, 1.4 + 0.55 * max(1, t.shape[0])))
    y = np.arange(t.shape[0])
    left_pos = np.zeros(t.shape[0])
    left_neg = np.zeros(t.shape[0])
    for j, cat in enumerate(t.columns):
        v = t[cat].to_numpy(float)
        left = np.where(v >= 0, left_pos, left_neg)
        ax.barh(y, v, left=left, height=0.55, color=PALETTE[j % len(PALETTE)], label=cat,
                edgecolor="white", linewidth=2)
        left_pos += np.where(v >= 0, v, 0)
        left_neg += np.where(v < 0, v, 0)
    tot = t.sum(axis=1).to_numpy(float)
    span = max(np.abs(left_pos).max(initial=0), np.abs(left_neg).max(initial=0)) or 1.0
    for i, v in enumerate(tot):
        ax.text(left_pos[i] + 0.01 * span, i, f"{v:.3g}", va="center", ha="left", fontsize=8.5, color="#333333")
    ax.set_yticks(y, [textwrap.fill(str(a), 22) for a in t.index], fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlim(min(0, left_neg.min(initial=0)) * 1.05, span * 1.15)
    ax.axvline(0, color="#888888", lw=0.8)
    ax.set_xlabel(unit)
    ax.set_title(title, fontsize=11, loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=0.3)
    ax.legend(fontsize=8, frameon=False, loc="center left", bbox_to_anchor=(1.01, 0.5))
    fig.tight_layout()
    return fig


def acceptability(ra: pd.DataFrame):
    return heatmap(ra * 100, title="Rank acceptability (% of Monte Carlo runs)", vmax=100,
                   cmap=LinearSegmentedColormap.from_list("blues", ["#f4f7fb", "#2f6db3"]), fmt="{:.0f}")
