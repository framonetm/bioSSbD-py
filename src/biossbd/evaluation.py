"""Evaluation: compare SSbD alternatives transparently, then test robustness.

The default output is a *dashboard*: every indicator side by side, its rank,
pass/fail against the decision criteria set in the scoping analysis, Pareto
dominance and explicit trade-offs - without collapsing everything into one
score, as recommended by the revised EC SSbD framework.

Aggregated scores (``mcda``) and their Monte Carlo robustness (``robustness``)
are available as a second layer for screening studies that need a ranking.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from itertools import permutations

import numpy as np
import pandas as pd
from . import mcda
from .dataquality import DataPoint
from .scoping import Criterion, SSbDSystem
from .specs import IndicatorSpec


@dataclass
class RobustnessResult:
    n: int
    method: str
    scores: np.ndarray  # (n, n_alternatives)
    alternatives: list[str]
    rank_acceptability: pd.DataFrame
    order_probability: pd.Series
    summary: pd.DataFrame
    dimension_intervals: pd.DataFrame = field(default_factory=pd.DataFrame)

    def p_order(self, *order: str) -> float:
        return float(self.order_probability.get(" > ".join(order), 0.0))


class Evaluation:
    """Alternatives x indicators with metadata and decision criteria."""

    def __init__(self, values: pd.DataFrame, specs: list[IndicatorSpec],
                 criteria: list[Criterion] | None = None,
                 ranges: dict[tuple[str, str], tuple[float, float]] | None = None):
        self.specs = {s.name: s for s in specs}
        missing = [c for c in values.columns if c not in self.specs]
        if missing:
            raise KeyError(f"No IndicatorSpec for: {missing}")
        self.values = values[[s.name for s in specs if s.name in values.columns]].astype(float)
        self.criteria = criteria or []
        self.ranges = ranges or {}

    # -- construction -----------------------------------------------------
    @classmethod
    def from_system(cls, system: SSbDSystem, specs: list[IndicatorSpec] | None = None) -> "Evaluation":
        """Build from the alternatives' indicators; specs default to ``system.indicator_specs``."""
        specs = specs if specs is not None else system.indicator_specs
        if not specs:
            raise ValueError("No indicator specs given and none declared in the system")
        rows, ranges = {}, {}
        for alt in system.alternatives:
            rows[alt.name] = {}
            for k, dp in alt.indicators.items():
                rows[alt.name][k] = dp.value
                if isinstance(dp, DataPoint) and dp.has_range:
                    ranges[(alt.name, k)] = (dp.low, dp.high)
        df = pd.DataFrame.from_dict(rows, orient="index")
        df = df[[s.name for s in specs if s.name in df.columns]]
        return cls(df, [s for s in specs if s.name in df.columns], system.criteria, ranges)

    @property
    def alternatives(self) -> list[str]:
        return list(self.values.index)

    @property
    def dimensions(self) -> list[str]:
        seen: list[str] = []
        for s in self.specs.values():
            if s.dimension not in seen and s.name in self.values.columns:
                seen.append(s.dimension)
        return seen

    # -- orientation and normalisation -----------------------------------
    def _unit_scores(self, values: pd.DataFrame | None = None) -> pd.DataFrame:
        """Map every indicator to [0, 1] with 1 = best."""
        v = self.values if values is None else values
        out = pd.DataFrame(index=v.index)
        for c in v.columns:
            s = self.specs[c]
            x = v[c].astype(float)
            if s.scale is not None:
                lo, hi = s.scale
            else:
                lo, hi = self.values[c].min(), self.values[c].max()
            span = hi - lo
            if span:
                u = (x - lo) / span
                out[c] = (1 - u) if s.direction == "min" else u
            else:  # all alternatives equal: no difference to report
                out[c] = pd.Series(1.0, index=x.index)
        return out.clip(0, 1)

    def dimension_scores(self, output_range: tuple[float, float] = (0.0, 1.0),
                         values: pd.DataFrame | None = None,
                         weights: dict[str, float] | None = None) -> pd.DataFrame:
        """Weighted mean of normalised indicators per dimension.

        With ``output_range=(1, 5)`` and ordinal 1-5 indicators this reproduces
        the unweighted dimension means of a classic scoring table.
        """
        u = self._unit_scores(values)
        lo, hi = output_range
        out = {}
        for d in self.dimensions:
            cols = [c for c in u.columns if self.specs[c].dimension == d]
            w = np.array([(weights or {}).get(c, self.specs[c].weight) for c in cols], float)
            out[d] = lo + (hi - lo) * (u[cols].to_numpy() @ (w / w.sum()))
        return pd.DataFrame(out, index=u.index)

    # -- transparent (non-aggregated) layer ------------------------------
    def dashboard(self) -> pd.DataFrame:
        """Long table: value, rank (1 = best) and criterion check per indicator."""
        rows = []
        for c in self.values.columns:
            s = self.specs[c]
            asc = s.direction == "min"
            ranks = self.values[c].rank(ascending=asc, method="min")
            crits = [k for k in self.criteria if k.indicator == c]
            for alt in self.alternatives:
                v = self.values.at[alt, c]
                status = ""
                if crits:
                    status = "pass" if all(k.passes(v) for k in crits) else "fail"
                rng = self.ranges.get((alt, c))
                rows.append({"dimension": s.dimension, "indicator": c, "unit": s.unit,
                             "alternative": alt, "value": v,
                             "range": f"{rng[0]:g}-{rng[1]:g}" if rng else "",
                             "rank": int(ranks[alt]), "criterion": status})
        return pd.DataFrame(rows)

    def best_by_indicator(self) -> pd.Series:
        out = {}
        for c in self.values.columns:
            s = self.specs[c]
            col = self.values[c]
            best = col.min() if s.direction == "min" else col.max()
            out[c] = ", ".join(col.index[col == best])
        return pd.Series(out, name="best")

    def dominance(self) -> pd.DataFrame:
        """Boolean matrix: row alternative Pareto-dominates column alternative."""
        u = self._unit_scores().to_numpy()
        n = len(self.alternatives)
        D = np.zeros((n, n), bool)
        for i in range(n):
            for j in range(n):
                if i != j:
                    D[i, j] = np.all(u[i] >= u[j]) and np.any(u[i] > u[j])
        return pd.DataFrame(D, index=self.alternatives, columns=self.alternatives)

    def pareto_front(self) -> list[str]:
        D = self.dominance()
        return [a for a in self.alternatives if not D[a].any()]

    def tradeoffs(self) -> pd.DataFrame:
        """Pairs of dimensions whose best alternative differs (a trade-off to discuss)."""
        ds = self.dimension_scores()
        best = {d: ds[d].idxmax() for d in ds.columns}
        rows = []
        dims = list(ds.columns)
        for i, a in enumerate(dims):
            for b in dims[i + 1:]:
                if best[a] != best[b]:
                    rows.append({"dimension_a": a, "best_a": best[a], "dimension_b": b, "best_b": best[b]})
        return pd.DataFrame(rows, columns=["dimension_a", "best_a", "dimension_b", "best_b"])

    def criteria_summary(self) -> pd.DataFrame:
        if not self.criteria:
            return pd.DataFrame()
        rows = []
        for k in self.criteria:
            if k.indicator not in self.values.columns:
                continue
            for alt in self.alternatives:
                v = self.values.at[alt, k.indicator]
                rows.append({"alternative": alt, "indicator": k.indicator,
                             "rule": f"{k.operator} {k.threshold:g}", "value": v,
                             "pass": k.passes(v)})
        return pd.DataFrame(rows)

    # -- aggregated layer -------------------------------------------------
    def mcda(self, method: str = "weighted_sum", dimension_weights: dict[str, float] | None = None,
             output_range: tuple[float, float] = (1.0, 5.0)) -> pd.Series:
        ds = self.dimension_scores(output_range)
        w = np.array([(dimension_weights or {}).get(d, 1.0) for d in ds.columns], float)
        return pd.Series(mcda.aggregate(ds.to_numpy(), w, method), index=ds.index, name=method)

    def compare_methods(self, dimension_weights: dict[str, float] | None = None) -> pd.DataFrame:
        out = {m: self.mcda(m, dimension_weights) for m in mcda.METHODS}
        df = pd.DataFrame(out)
        return df

    def weight_threshold(self, dimension: str, output_range=(1.0, 5.0), grid: int = 1001) -> float | None:
        """Smallest weight on ``dimension`` (others share the rest equally) at which the
        top-ranked alternative under equal weights changes. None if it never changes."""
        ds = self.dimension_scores(output_range)
        dims = list(ds.columns)
        if dimension not in dims or len(dims) < 2:
            return None
        X = ds.to_numpy()
        j = dims.index(dimension)
        others = np.delete(X, j, axis=1).mean(axis=1)
        base_top = int(np.argmax(X.mean(axis=1)))
        w = np.linspace(0, 1, grid)
        scores = np.outer(w, X[:, j]) + np.outer(1 - w, others)  # (grid, n_alt)
        tops = scores.argmax(axis=1)
        mask = (tops != base_top) & (w > 1 / len(dims))
        return round(float(w[mask][0]), 3) if mask.any() else None

    def robustness(self, n: int = 10_000, method: str = "weighted_sum",
                   perturb_scores: bool = True, perturb_weights: bool = False,
                   dimension_weights: dict[str, float] | None = None,
                   within_concentration: float = 20.0, seed: int | None = 2026,
                   output_range=(1.0, 5.0)) -> RobustnessResult:
        """Monte Carlo propagation of score and weight uncertainty (vectorised).

        - ordinal indicators: +-1 step with probabilities 0.25/0.5/0.25, clipped to the scale
        - indicators with a (low, high) range: uniform draw within the range
        - weights: Dirichlet within dimensions (centred on base weights, concentration
          ``within_concentration``) and flat Dirichlet across dimensions
        """
        rng = np.random.default_rng(seed)
        alts, dims = self.alternatives, self.dimensions
        cols = list(self.values.columns)
        na, ni, nd = len(alts), len(cols), len(dims)
        base = self.values.to_numpy(float)
        specs = [self.specs[c] for c in cols]
        lo = np.array([s.scale[0] if s.scale else self.values[c].min() for s, c in zip(specs, cols)])
        hi = np.array([s.scale[1] if s.scale else self.values[c].max() for s, c in zip(specs, cols)])
        span = np.where(hi - lo == 0, 1.0, hi - lo)
        flip = np.array([s.direction == "min" for s in specs])
        ordinal = np.array([s.ordinal for s in specs])
        dim_idx = np.array([dims.index(s.dimension) for s in specs])
        w_base = np.array([s.weight for s in specs], float)

        # scores
        X = np.broadcast_to(base, (n, na, ni)).copy()
        if perturb_scores:
            if ordinal.any():
                step = rng.choice([-1.0, 0.0, 1.0], size=(n, na, int(ordinal.sum())), p=[0.25, 0.5, 0.25])
                X[:, :, ordinal] = np.clip(X[:, :, ordinal] + step, lo[ordinal], hi[ordinal])
            for (a, c), (rlo, rhi) in self.ranges.items():
                if a in alts and c in cols and not ordinal[cols.index(c)]:
                    X[:, alts.index(a), cols.index(c)] = rng.uniform(rlo, rhi, size=n)
        U = (X - lo) / span
        U = np.where(flip, 1 - U, U)
        U = np.clip(U, 0, 1)

        # within-dimension weights (n, ni), normalised per dimension
        W = np.broadcast_to(w_base, (n, ni)).copy()
        if perturb_weights:
            for d in range(nd):
                m = dim_idx == d
                if m.sum() > 1:
                    alpha = within_concentration * w_base[m] / w_base[m].sum()
                    W[:, m] = rng.dirichlet(alpha, size=n)
        M = np.zeros((ni, nd))
        M[np.arange(ni), dim_idx] = 1.0
        Wsum = W @ M  # (n, nd)
        Wn = W / Wsum[:, dim_idx]
        D = np.einsum("nai,ni,id->nad", U, Wn, M)
        D = output_range[0] + (output_range[1] - output_range[0]) * D

        # across-dimension weights
        base_dw = np.array([(dimension_weights or {}).get(d, 1.0) for d in dims], float)
        base_dw /= base_dw.sum()
        DW = rng.dirichlet(np.ones(nd), size=n) if perturb_weights else np.broadcast_to(base_dw, (n, nd))

        if method == "weighted_sum":
            scores = np.einsum("nad,nd->na", D, DW)
        else:
            scores = np.array([mcda.aggregate(D[k], DW[k], method) for k in range(n)])

        order_idx = np.argsort(-scores, axis=1, kind="stable")
        ranks = np.argsort(order_idx, axis=1) + 1
        names = np.array(alts)
        orders = Counter(" > ".join(names[row]) for row in order_idx)
        ra = pd.DataFrame({f"rank {r}": (ranks == r).mean(axis=0) for r in range(1, na + 1)}, index=alts)
        op = pd.Series({k: v / n for k, v in orders.most_common()}, name="probability")
        summ = pd.DataFrame({"median": np.median(scores, 0), "p2.5": np.percentile(scores, 2.5, 0),
                             "p97.5": np.percentile(scores, 97.5, 0)}, index=alts)
        di = pd.DataFrame({f"{d} p2.5": np.percentile(D[:, :, j], 2.5, 0) for j, d in enumerate(dims)}
                          | {f"{d} p97.5": np.percentile(D[:, :, j], 97.5, 0) for j, d in enumerate(dims)},
                          index=alts)
        return RobustnessResult(n, method, scores, alts, ra, op, summ, di)


def all_orders(alternatives: list[str]) -> list[str]:
    return [" > ".join(p) for p in permutations(alternatives)]
