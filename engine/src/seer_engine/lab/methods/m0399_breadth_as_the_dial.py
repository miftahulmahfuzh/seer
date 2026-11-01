"""M0399 — Breadth as the dial: read the market's narrowness directly instead of through smoothness.

Source: variation on M0394 (smoothness as a weight), itself from M0036 (Da, Gurun & Warachka 2014,
Frog in the Pan, RFS 27(7), SSRN 1777988). The breadth quantity is the one ``lab regime`` labels
months with: the index's return less the equal-weighted average return of its members. That
spread was published as "market concentration / narrow leadership" work by many authors and is
not new; what is new here is only using it to size slots, not to time the book.

**What M0394 left on the table.** Its dial tilts the same twenty momentum names toward the smooth
paths. ``lab regime`` then showed the dial is worth +2.5 points a year in narrow months and -2.6
in broad ones, so it is a bet on breadth wearing a quality reading's clothes. This method keeps
the bet and removes the clothes: the tilt *direction* is set by a direct, point-in-time breadth
reading, so the smooth names are favoured only while the market is narrow and the jumpy ones only
while it is broad.

**Why it is not a market timer.** Breadth is one number per day, the same for every name. It
cannot, on its own, move money between names. It acts here by flipping the sign of M0394's
within-book tilt, and total exposure is held identical to equal weighting (M0394's
``tilt_weights``, imported unchanged), so the book is never in less cash than the plain twenty.
Whatever it earns is the *reallocation*, not a time out of the market.

**The reading.** Over the last ``window`` = 63 sessions ending at the data date, the market
symbol's compounded return minus the mean compounded return of the point-in-time members that
have 80% of the window. Positive = narrow (the index beat its average member). Fewer than 30
scoreable members = no reading = no tilt. Only bars dated <= the data date are read.

**The arms** (2x2 of opinion and habit, plus controls). PLAIN is no opinion at all. FIX50 is
M0394's SM50 again, a fixed smooth tilt: the "habit with no breadth" corner. BR25 and BR50 tilt
toward the smooth names when narrow and the jumpy when broad. RV50 is the same breadth reading
with the sign reversed, the mirror that proves the signal and not the dressing. DRAW is the blind,
turnover-matched control. Frame and fees are M0394's: ``monthly-hold-frac-gotrade``, F4 N20
momentum screen with the SPY-200 gate, funded 5,000,000 IDR on the 25th.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, ReturnGrid
from seer_engine.lab.methods.m0394_smoothness_as_a_weight import (
    SMOOTH,
    Prepared,
    WeightParams,
    weight_lookback,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History, as_day

ADDED = date(2026, 11, 1)

MIN_MEMBERS = 30
"""Fewest scoreable members for a reading; matches ``backtest.regime.MIN_MEMBERS``."""

MIN_FRAC = 0.8
"""A member counts only when it has this share of the window's daily returns."""

MODES = ("fixed", "signed", "reversed")


@dataclass(frozen=True, slots=True)
class BreadthParams:
    """``weights`` is M0394's dial (its ``tilt`` is the strength); ``mode`` says who sets the sign.

    ``fixed``: the sign is ``weights.tilt``'s own, as in M0394. ``signed``: smooth names when the
    breadth spread is positive (narrow), jumpy when it is not. ``reversed``: the opposite.
    """

    weights: WeightParams
    window: int = 63
    mode: str = "fixed"

    def __post_init__(self) -> None:
        if not isinstance(self.weights, WeightParams):
            raise TypeError(f"weights must be WeightParams, got {type(self.weights).__name__}")
        if isinstance(self.window, bool) or not isinstance(self.window, int) or self.window < 5:
            raise ValueError(f"window must be an int >= 5, got {self.window!r}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if self.mode != "fixed" and self.weights.tilt < 0:
            raise ValueError("a breadth-signed arm carries a non-negative strength")

    def as_dict(self) -> dict[str, str]:
        out = {"window": str(self.window), "mode": self.mode}
        for k, v in self.weights.as_dict().items():
            out[f"w.{k}"] = v
        return out


def _check(params: object) -> BreadthParams:
    if not isinstance(params, BreadthParams):
        raise TypeError(f"params must be BreadthParams, got {type(params).__name__}")
    return params


def breadth_spread(grid: ReturnGrid, members: AbstractSet[str], data_date: date, window: int,
                   market: str) -> float | None:
    """Market return less the mean member return over ``window`` sessions to ``data_date``.

    Positive means narrow. None when the date is off the market calendar, the window does not
    fit, or fewer than ``MIN_MEMBERS`` members carry enough of it.
    """
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day or j - window + 1 < 0 or market not in grid.row:
        return None
    lo = j - window + 1
    block = grid.rets[:, lo : j + 1]

    def compound(rows: np.ndarray) -> np.ndarray:
        r = block[rows]
        return np.prod(1.0 + np.where(np.isfinite(r), r, 0.0), axis=1) - 1.0

    mk = compound(np.asarray([grid.row[market]]))[0]
    idx = np.asarray(
        [grid.row[s] for s in members if s in grid.row and s != market], dtype=np.int64
    )
    if idx.size == 0:
        return None
    have = np.isfinite(block[idx]).sum(axis=1)
    idx = idx[have >= math.ceil(MIN_FRAC * window)]
    if idx.size < MIN_MEMBERS:
        return None
    avg = float(np.mean(compound(idx)))
    return float(mk) - avg if math.isfinite(avg) and math.isfinite(float(mk)) else None


def effective(params: BreadthParams, spread: float | None) -> WeightParams:
    """The M0394 dial this month: sign from breadth in a breadth arm, no tilt without a reading."""
    w = params.weights
    if params.mode == "fixed" or w.seed is not None:
        return w
    if spread is None or float(w.tilt) == 0.0:
        return replace(w, tilt=0.0)
    narrow = spread > 0.0
    smooth = narrow if params.mode == "signed" else not narrow
    return replace(w, tilt=abs(float(w.tilt)) * (1.0 if smooth else -1.0))


class BreadthDialAllocator:
    """M0394's twenty names and slot sizes, with the tilt's sign read from market breadth."""

    id = "M0399"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(weight_lookback(p.weights), p.window + 2)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return SMOOTH.symbols(_check(params).weights)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def prepare(self, history: Mapping[str, History]) -> Prepared:
        return SMOOTH.prepare(history)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self.targets_prepared(SMOOTH.prepare(history), members, data_date, held, params)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        spread = None
        if p.mode != "fixed":
            grid = prepared.grid(p.weights.market)
            if grid is not None:
                spread = breadth_spread(grid, members, data_date, p.window, p.weights.market)
        return SMOOTH.targets_prepared(prepared, members, data_date, held, effective(p, spread))


BREADTH = BreadthDialAllocator()


def _v(suffix: str, tilt: float, mode: str, rationale: str, seed: int | None = None) -> Candidate:
    return Candidate(
        id=f"M0399-{suffix}", family="M0399", rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=BREADTH,
        params=BreadthParams(WeightParams(inner=N20, tilt=tilt, seed=seed), mode=mode),
        rationale=rationale, added=ADDED, owner_inputs=(),
    )


METHOD = Method(
    id="M0399",
    name="Breadth as the dial: sizing the momentum twenty on a direct market-narrowness reading",
    family="stock-breadth-tilt",
    source_kind="variation",
    source_ref="M0394 (via M0036, Da, Gurun & Warachka 2014, RFS 27(7), SSRN 1777988)",
    parent_id="M0394",
    hypothesis=(
        "M0394 found that tilting the plain twenty-name momentum book toward smooth-path names "
        "earned +2.5 points a year more in narrow months and -2.6 less in broad ones (lab regime, "
        "237 months, 99 narrow, 138 broad), so the dial lost 0.58 points a year net: a bet on "
        "breadth in a quality reading's clothes. This method reads breadth directly: over 63 "
        "sessions, the index return less the equal-weighted mean member return, computed from "
        "bars alone, point in time. The tilt toward smooth names applies while that spread is "
        "positive (narrow) and flips toward the jumpy names when it is not. Every arm holds the "
        "same twenty names as the plain book with total exposure equal to equal weighting, so "
        "nothing is vetoed and no arm can sit in more cash than another. "
        "Pass bars, stated before any result: the signed arms (BR25, BR50) must beat PLAIN and "
        "FIX50 on funded CAGR, must be ordered BR50 > BR25 > PLAIN > RV50 on the same measure, "
        "and RV50 must lose to PLAIN by about what BR50 wins, all with BR50 clear of the DRAW "
        "control's width (about 7.5 points a year in this lab) and positive over 2009-2015. "
        "The frame is M0394's: monthly-hold-frac-gotrade, F4 N20 momentum, SPY-200 gate, funded "
        "5,000,000 IDR on the 25th. The market-concentration literature is widely read, so any "
        "dev edge is a pre-crowd edge and is likely to fade."
    ),
    expected_failure=(
        "A one-number-per-day signal cannot pick between names, so the likeliest outcome is that "
        "the sign flip adds only noise: a trailing 63-session breadth reading is a lagging label "
        "and breadth regimes switch slower than the monthly rebalance only on average, so each "
        "flip pays turnover for a tilt whose value was already earned. Then BR25, BR50 and RV50 "
        "will sit inside the draw's width and below PLAIN once real fees are paid, as M0394's "
        "whole ladder did. The second failure is that the tilt, being small and rank-based, is "
        "invisible against draw noise. The third is the fall: every arm still owns twenty "
        "momentum stocks, so the drawdown will exceed the real-money limit for the same reason the "
        "parent's did, and kin to M0394's momentum family should refuse promotion. Exposure is "
        "identical by construction, so if the arms differ it is the reallocation, not cash; "
        "exposure is read beside return on every arm."
    ),
    candidates=(
        _v("PLAIN", 0.0, "fixed",
           "The plain twenty, equal slots, no opinion: the zero of the dial and the no-opinion "
           "corner of the 2x2."),
        _v("FIX50", 0.5, "fixed",
           "M0394's smooth tilt at 0.5, a fixed sign: the habit-without-breadth corner, so what "
           "the breadth reading adds is priced against it."),
        _v("BR25", 0.25, "signed",
           "Mild breadth dial: smooth tilt 0.25 while narrow, jumpy tilt 0.25 while broad."),
        _v("BR50", 0.5, "signed",
           "Middle breadth dial: smooth tilt 0.5 while narrow, jumpy 0.5 while broad."),
        _v("RV50", 0.5, "reversed",
           "Mirror of BR50: same reading, opposite sign. Must lose by about what BR50 wins or the "
           "signal is not what is being measured."),
        _v("DRAW", 0.0, "fixed",
           "Control: twenty names drawn from the same pool by hash, turnover-matched to PLAIN.",
           seed=399),
    ),
    seen_keys=(
        "concept:breadth-signed-slot-tilt",
        "concept:breadth-as-direct-weight-dial",
        "concept:index-minus-equal-weight-spread-sizing",
    ),
)
