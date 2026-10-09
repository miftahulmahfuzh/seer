"""M0034 — Size the picks by how big they trade, not equally.

Source: a variation of M0032 (its only variant, M0032-N20-RAW-FRAC-GT), re-weighted. Prompted
by lab insight 58's first recommendation, and by the published equal-weight-versus-cap record:
the Russell 1000 Equal Weight index trailed its cap-weighted parent by roughly 3.9 points a
year from Q4 2014 to Q1 2025.

Idea: equal weights inside a top-20 book are an unstated bet that the typical pick keeps up
with the cap-weighted index the book is judged against. Nobody chose that bet, and insight 58
measured its cost on a constant-coverage breadth reading: the trailing three-year mean of the
equal-weight-minus-cap spread has been positive almost unbroken since late 2023 and peaked at
+0.68% a month in December 2025, above the dot-com peak of +0.53%, where 1996-2015 cleared
+0.17% in only 6 of 202 three-year windows. This method keeps M0032's ranking and execution
EXACTLY -- top-20 raw cumulative residual momentum, F4's screen, the SPY-200 trend gate,
monthly, fractional shares at Gotrade's measured fees on the owner's 5,000,000 IDR monthly
top-up -- and moves one dial only: how the twenty slots are sized.

WHAT THE SIZE DIAL READS, AND WHY IT IS NOT MARKET CAP. The reserved idea asked for a tilt by
point-in-time market capitalisation, computed the way ``f_fundamental`` computes it: EDGAR
shares outstanding times the close. That is not testable over this window. EDGAR's XBRL facts
begin in 2009 (measured: the store's panel has zero facts filed before 2009-07 and 21,179 in
2009), and the dev window opens 1996-01-03. A book that required a filed share count would
hold nothing at all for thirteen of the window's twenty years, and its trial would measure the
SEC's filing mandate rather than the idea. So the size dial here reads the one size measure the
store carries from 1993: **the 20-day mean of close times volume**, which ``f_factor`` already
computes for every eligible name as its liquidity screen (``FactorRow.dollar_volume``). No new
data path, no panel, nothing that is not already read on every rebalance.

How close a cousin that is, measured rather than assumed. On the 69 month-end data dates from
2010-01-29 to 2015-09-30, over names this very book ranked, with both measures present:

    Spearman rank correlation, whole eligible set   mean 0.686  median 0.687  (p10 0.658, p90 0.714)
    Spearman rank correlation, inside the top 20    mean 0.539  median 0.568  (p10 0.252, p90 0.773)
    share of the top 20 with a filed share count    mean 0.902
    weight distance between the two size-proportional books   mean 0.400, median 0.352
        (total-variation: the fraction of the book's money sitting on different names)

So trading size orders the universe much the way market value does, and is emphatically not the
same number: a book weighted by one puts about 35-40% of its money differently from a book
weighted by the other. This method therefore tests the SIZE DIAL, honestly labelled -- does
tilting a momentum book's weights toward its larger, more heavily traded names pay, and what
does it do to the worst fall -- and not the cap tilt the idea's title asked for. The true cap
tilt is queued as its own idea against the 2009-onward era, where the share counts exist.

A second reason the dial is worth turning in this direction: the names that trade most are the
names a real order moves least. Any weight this book shifts from a thin name to a thick one is
weight that fills closer to the price the backtest assumed.

FIVE VARIANTS, ONE DIAL, THE CONTROL IN THE MIDDLE. Equal weighting is not an endpoint of the
size dial, it is its centre, so measuring only the large-tilt side would leave the reading
one-sided. EQ reproduces M0032's configuration under this allocator (same picks, same weights)
and exists as the parity control: any difference the other four show is sizing and nothing
else. SIZE and SQRT tilt toward the bigger names, SIZE-C2 does so with a ceiling, and INV-SQRT
tilts the other way. Read together they say whether size is a direction that pays at all in
this book, or whether equal weighting was already sitting at the flat part of the curve.

Every piece reads only bars dated <= ``data_date``: the weights are a function of
``FactorRow.dollar_volume``, which is a 20-day window ending on ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    FACTOR_SYMBOLS,
    N20,
    ResidParams,
    ResidPrepared,
    build_grid,
    resid_lookback,
    residual_scores,
)
from seer_engine.sim.book import Target, WEIGHT_QUANTUM, equal_weight, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorRow,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 9)

#: How the chosen slots are sized. ``equal`` is M0032's; the rest read ``dollar_volume``.
TILTS: tuple[str, ...] = ("equal", "size", "sqrt", "inv_sqrt")


@dataclass(frozen=True, slots=True)
class TiltParams:
    """M0032's ranking (``inner``) plus the one dial this method moves.

    ``max_mult`` is a per-name ceiling as a multiple of the equal weight, applied after the
    tilt and redistributed to the names still under it. None means no ceiling. It is only
    meaningful for a tilt that can concentrate, which in this book is ``size``.
    """

    inner: ResidParams
    tilt: str = "equal"
    max_mult: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.inner, ResidParams):
            raise TypeError(f"inner must be ResidParams, got {type(self.inner).__name__}")
        if not isinstance(self.tilt, str):
            raise TypeError(f"tilt must be a str, got {type(self.tilt).__name__}")
        if self.tilt not in TILTS:
            raise ValueError(f"tilt must be one of {TILTS}, got {self.tilt!r}")
        if self.max_mult is not None:
            if isinstance(self.max_mult, bool) or not isinstance(self.max_mult, (int, float)):
                raise TypeError(f"max_mult must be a number or None, got {type(self.max_mult).__name__}")
            if not np.isfinite(self.max_mult) or self.max_mult < 1.0:
                raise ValueError(f"max_mult must be >= 1.0 (a ceiling below equal is infeasible), got {self.max_mult}")
            if self.tilt == "equal":
                raise ValueError("max_mult is meaningless on the equal tilt: every weight is already the equal weight")

    def as_dict(self) -> dict[str, str]:
        out = {"tilt": self.tilt, "max_mult": "none" if self.max_mult is None else repr(float(self.max_mult))}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _floor_weight(x: float) -> Decimal | None:
    """``to_weight(x)``, or None when ``x`` floors to zero (``f_factor``'s rule, verbatim)."""
    if not np.isfinite(x) or Decimal(repr(x)) < WEIGHT_QUANTUM:
        return None
    return to_weight(x)


def _apply_ceiling(w: np.ndarray, ceiling: float) -> np.ndarray:
    """``w`` with every entry capped at ``ceiling``, the excess spread over the names still under it.

    Water-filling, at most ``len(w)`` passes because each pass caps at least one more name.
    Feasible whenever ``ceiling`` is at least the mean of ``w``, which holds here: the ceiling
    is ``max_mult >= 1`` times the equal weight and the equal weight is the mean by construction.
    """
    w = w.astype(np.float64, copy=True)
    for _ in range(len(w)):
        over = w > ceiling
        if not over.any():
            break
        excess = float((w[over] - ceiling).sum())
        w[over] = ceiling
        free = (~over) & (w > 0.0)
        if not free.any():
            break
        w[free] += excess * w[free] / float(w[free].sum())
    return np.minimum(w, ceiling)


def tilt_weights(chosen: Sequence[FactorRow], params: TiltParams) -> list[Decimal | None]:
    """One weight per chosen row (None = floors to zero, the row is dropped). Σ of the non-None <= 1.

    Total exposure is ``len(chosen) / top`` under every tilt -- the same as equal weighting --
    so a tilt moves money between names and never changes how much of the book is invested.
    ``dollar_volume`` is finite and strictly above ``min_dollar_volume`` for every row
    ``factor_rows`` returns, so the roots and reciprocals below are always well defined.
    """
    if not chosen:
        return []
    top = params.inner.inner.top
    eq = equal_weight(top)
    if params.tilt == "equal":
        return [eq for _ in chosen]
    size = np.array([r.dollar_volume for r in chosen], dtype=np.float64)
    if params.tilt == "size":
        raw = size
    elif params.tilt == "sqrt":
        raw = np.sqrt(size)
    else:  # inv_sqrt
        raw = 1.0 / np.sqrt(size)
    scale = len(chosen) / top
    w = raw / float(raw.sum()) * scale
    if params.max_mult is not None:
        w = _apply_ceiling(w, float(eq) * float(params.max_mult))
    return [_floor_weight(float(x)) for x in w]


def _check(params: object) -> TiltParams:
    if not isinstance(params, TiltParams):
        raise TypeError(f"params must be TiltParams, got {type(params).__name__}")
    return params


def _targets(rows: list[FactorRow], scores: Mapping[str, float], p: TiltParams) -> tuple[Target, ...]:
    """M0032's chosen set, sized by ``tilt_weights`` instead of F4's equal weights."""
    scorable = [r for r in rows if r.symbol in scores and r.symbol not in EXCLUDED]
    chosen = sorted(scorable, key=lambda r: (-scores[r.symbol], r.symbol))[: p.inner.inner.top]
    out: list[Target] = []
    for row, weight in zip(chosen, tilt_weights(chosen, p), strict=True):
        if weight is None:
            continue
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


class SizeTiltAllocator:
    """M0032's book, with the twenty slots sized by how much the name trades.

    Selection is M0032's, name for name: the trend gate, F4's screen and the raw cumulative
    residual momentum ranking are reused unchanged from ``m0007_residual_momentum``. Only the
    weighting is this class's own. Held symbols get no special treatment -- the targets are
    exactly the new top set, so a name that falls out of it is signal-exited by the book engine.
    """

    id = "M0034"

    def lookback(self, params: Any) -> int:
        return resid_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params).inner
        return tuple(sorted({p.market, *FACTOR_SYMBOLS(p.inner)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner.inner)
        if not rows:
            return ()
        grid = build_grid(history, p.inner.market)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, p.inner)
        return _targets(rows, scores, p)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return ResidPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner.inner)
        if not rows:
            return ()
        grid = prepared.grid(p.inner.market)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, p.inner)
        return _targets(rows, scores, p)


SIZETILT = SizeTiltAllocator()

#: M0032-N20-RAW-FRAC-GT's ranking, verbatim: top-20 RAW cumulative residual momentum, SPY-200 gate.
RANKING = ResidParams(N20, scaled=False)


def _v(suffix: str, params: TiltParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0034-{suffix}", family="M0034", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SIZETILT, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0034",
    name="Size the picks by how big they trade, not equally: a size tilt inside the real-fee residual book",
    family="stock-portfolio-construction",
    source_kind="variation",
    source_ref=(
        "variation of M0032-N20-RAW-FRAC-GT, re-weighted; lab insight 58's first recommendation; "
        "Russell 1000 Equal Weight vs its cap-weighted parent, Q4 2014 - Q1 2025"
    ),
    parent_id="M0032",
    hypothesis=(
        "Equal weights inside the top-20 are an unstated bet that the typical pick keeps up with "
        "the cap-weighted index the book is judged against, and insight 58 measured that the bet "
        "has been losing since late 2023: on a constant-coverage breadth reading the trailing "
        "three-year mean of the equal-weight-minus-cap spread peaked at +0.68% a month in December "
        "2025, above the dot-com peak of +0.53%, where 1996-2015 cleared +0.17% in only 6 of 202 "
        "three-year windows. Published numbers agree -- the Russell 1000 Equal Weight index "
        "trailed its cap-weighted parent by roughly 3.9 points a year from Q4 2014 to Q1 2025. "
        "This method keeps M0032's ranking and execution exactly -- top-20 raw cumulative residual "
        "momentum, F4's screen, the SPY-200 trend gate, monthly, fractional shares at Gotrade's "
        "measured fees, funded 5,000,000 IDR on the 25th of each month -- and moves one dial: how "
        "the twenty slots are sized. The dial reads the 20-day mean of close times volume, which "
        "F4 already computes for every eligible name, NOT point-in-time market capitalisation: "
        "EDGAR's XBRL facts begin in 2009 and the dev window opens in 1996, so a book that needed "
        "a filed share count would hold nothing for thirteen of twenty years and would measure the "
        "SEC's filing mandate instead of the idea. Measured over the 69 month-end dates from "
        "2010-01-29 to 2015-09-30 where both exist, trading size and market value rank the "
        "eligible set alike at a Spearman correlation of 0.686 on average and the chosen top-20 at "
        "0.539, with 90% of the top-20 carrying a filed share count, and the two size-proportional "
        "books put about 35-40% of their money on different names (mean total-variation weight "
        "distance 0.400). Trading size is therefore a cousin of market value, not a stand-in for "
        "it, and this is a size-tilt trial honestly labelled. I expect the dev window to say the "
        "large tilt costs return: 1996-2015 is the era in which the typical stock did keep up, so "
        "the honest reading of a loss on dev is the size of an insurance premium against a regime "
        "the dev window does not contain. What is really being measured is how big that premium "
        "is, and whether leaning on the larger names shrinks the worst fall -- M0032 missed the "
        "20% limit by six tenths of a point -- enough to buy some of it back. Equal weighting is "
        "the centre of this dial, not its end, so the inverse tilt is run too: if leaning small "
        "also beats equal, the dial is noise and the premium is not worth paying."
    ),
    expected_failure=(
        "The size tilt does nothing measurable in either direction, because the universe is "
        "already the S&P 500 union the Nasdaq-100 and the trend-gated momentum screen keeps "
        "cutting it down to twenty large, liquid names whose trading sizes span perhaps one order "
        "of magnitude -- too narrow a spread for a weight tilt to move a twenty-year result by "
        "more than noise, and far narrower than the spread an all-cap equal-weight index runs "
        "against its parent. The second way it fails is the opposite and worse: the unconstrained "
        "size tilt concentrates. A single mega-cap can take 25-35% of a twenty-name book weighted "
        "by trading volume, which turns a diversified momentum book into a bet on one or two "
        "names, pushes the worst fall further past the 20% limit rather than back inside it, and "
        "makes the capped variant the only one that could ever be promoted. The third way, and "
        "the one that would make the whole direction a dead end, is that the inverse tilt wins "
        "too: both sides beating the control would mean the extra turnover of re-weighting is "
        "being paid back by nothing but noise, and the dial should be left where it is."
    ),
    candidates=(
        _v("EQ", TiltParams(RANKING, tilt="equal"),
           "Equal weights: M0032's configuration under this allocator, the parity control the tilts are read against"),
        _v("SIZE", TiltParams(RANKING, tilt="size"),
           "Weights proportional to 20-day mean dollar volume: the full lean toward the names that trade most"),
        _v("SQRT", TiltParams(RANKING, tilt="sqrt"),
           "Weights proportional to the square root of trading size: the half-way tilt, half the concentration"),
        _v("SIZE-C2", TiltParams(RANKING, tilt="size", max_mult=2.0),
           "The full size tilt with no name above twice the equal weight (10%), the excess spread over the rest"),
        _v("INV-SQRT", TiltParams(RANKING, tilt="inv_sqrt"),
           "The dial turned the other way, toward the smaller names: is equal weighting already at the flat part"),
    ),
    seen_keys=(
        "concept:size-weighted-momentum-book",
        "concept:equal-weight-versus-cap-weight-tilt",
    ),
)
