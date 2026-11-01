"""M0453 — When in the month the gain came: last month's winners ranked by late-month share.

Source: Cakici et al., "Daily Return Information Factor" (Alpha Architect summary,
https://alphaarchitect.com/daily-stock-returns/). Short-horizon timing within a month is a
recent finding, so the dev window (ends 2015) sees it before the crowd; 2009-2015 is the first
filter. Two stocks with the same last-month return differ in WHEN the gain arrived: a gain
that came in the final week is fresh news the market has not yet priced; a gain that came in
the first three weeks has had time to be traded on or reverse.

Late share here is ``return of the last 5 trading days / return of the last 21`` (both
close-to-close, ending d), taken only over names whose 21-day return is positive so the ratio
has a sign. Not the same as M0028 / M0391 (short-term reversal: they buy the losers) and not
M0453 (path smoothness over 12-1).

``TimingAlloc`` is FACTOR's screen, point-in-time index pool, SPY 200-day switch and 20 equal
slots, monthly, with a 21-day return rank. ``mode``: "mom" the 20 best last-month returns (the
always-invested, no-timing-opinion control); "late" the 80 best last-month returns, then the 20
with the highest late share; "early" the same with the lowest (the mirror); an int is a seeded
draw of 20 from the pool (M0293's sticky hash). Pure; reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import draw
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FACTOR,
    FactorParams,
    FactorRow,
    factor_rows,
    factor_weights,
    trend_on,
)

ADDED = date(2026, 11, 1)

SWITCH = ("SPY", 200)
TOP = 20
WINNERS = 80
LOOK = 21
SKIP = 0
LAST = 5
MODES = ("mom", "late", "early")


@dataclass(frozen=True, slots=True)
class Params:
    """``mode`` is "mom", "late" or "early"; ``seed`` (an int) replaces it with a hash draw."""

    mode: str = "mom"
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.seed is None and self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if self.seed is not None and (isinstance(self.seed, bool) or not isinstance(self.seed, int)):
            raise TypeError(f"seed must be an int or None, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        return {"mode": self.mode, "seed": str(self.seed), "winners": str(WINNERS),
                "pool": "f4-screened-members"}

    def picker(self) -> FactorParams:
        return FactorParams(rank="momentum", top=TOP, mom_n=LOOK, mom_skip=SKIP, trend=SWITCH)


def late_share(h: History, data_date: date) -> float | None:
    """Return of the last LAST bars over the return of the last LOOK bars; None unless the
    window is complete, gap-free and the LOOK-bar return is positive."""
    i = h.index_of(data_date)
    if i is None or i - LOOK < 0:
        return None
    window = h.close[i - LOOK : i + 1]
    if not bool(np.all(window > 0)):
        return None
    total = float(window[-1] / window[0] - 1.0)
    if total <= 0.0:
        return None
    return float(window[-1] / window[-1 - LAST] - 1.0) / total


def choose(rows: Sequence[FactorRow], history: Mapping[str, History], data_date: date,
           p: Params) -> list[FactorRow]:
    if p.seed is not None:
        seed = p.seed
        return sorted(rows, key=lambda r: (float(draw(seed, r.symbol)), r.symbol))[:TOP]
    by_mom = sorted(rows, key=lambda r: (-r.momentum, r.symbol))
    if p.mode == "mom":
        return by_mom[:TOP]
    scored: list[tuple[float, FactorRow]] = []
    for r in by_mom[:WINNERS]:
        h = history.get(r.symbol)
        v = late_share(h, data_date) if h is not None else None
        if v is not None:
            scored.append((v, r))
    if not scored:
        return []
    half = len(scored) // 2
    ordered = sorted(scored, key=lambda t: (t[0], t[1].symbol))
    picked = ordered[:half] if p.mode == "early" else ordered[len(scored) - half:]
    return sorted((r for _, r in picked), key=lambda r: (-r.momentum, r.symbol))[:TOP]


def _targets(rows: Sequence[FactorRow], history: Mapping[str, History], data_date: date,
             params: Params) -> tuple[Target, ...]:
    chosen = choose(rows, history, data_date, params)
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, params.picker()), strict=True):
        if weight is None:
            continue
        t = target_from_close(row.symbol, row.close, weight)
        if t is not None:
            out.append(t)
    return tuple(out)


class TimingAlloc:
    """FACTOR's screen and switch, with the pick ordered by when last month's gain arrived."""

    id = "M0453"

    def lookback(self, params: Params) -> int:
        return FACTOR.lookback(params.picker())

    def symbols(self, params: Params) -> tuple[str, ...]:
        return FACTOR.symbols(params.picker())

    def holds(self, params: Params) -> tuple[str, ...]:
        return ()

    def uses_members(self, params: Params) -> bool:
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Params) -> tuple[Target, ...]:
        p = params.picker()
        if not trend_on(history, data_date, p):
            return ()
        return _targets(factor_rows(history, members, data_date, p), history, data_date, params)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return FACTOR.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Params) -> tuple[Target, ...]:
        p = params.picker()
        if not trend_on(prepared.history, data_date, p):
            return ()
        return _targets(prepared.rows_on(members, data_date, p), prepared.history, data_date, params)


TIMING = TimingAlloc()


def _v(suffix: str, params: Params, rationale: str) -> Candidate:
    return Candidate(id=f"M0453-{suffix}", family="M0453", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=TIMING, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0453",
    name="When in the month the gain came: last month's winners ranked by how late the return arrived",
    family="stock-return-timing",
    source_kind="paper",
    source_ref="Cakici et al., Daily Return Information Factor (Alpha Architect summary, alphaarchitect.com/daily-stock-returns)",
    hypothesis=(
        "Two stocks with the same last-month return differ in WHEN inside the month the gain "
        "arrived. Late share = return of the last 5 trading days over the return of the last 21, "
        "among names with a positive 21-day return. A gain that arrived in the final week is news "
        "not yet priced; one from the first three weeks has had time to be traded or to reverse. "
        "Published recently, so the dev window sees it before the crowd; 2009-2015 is the first "
        "filter. Arms, all behind SPY's 200-day switch, 20 equal slots, monthly, fractional "
        "shares at Gotrade's real fees, the F4-screened point-in-time index pool: LATE (the 80 "
        "best last-month returns, keep the half with the highest late share, hold the 20 best by "
        "return), EARLY (the same with the lowest-share half, the mirror), MOM (the 20 best "
        "last-month returns: same book, switch and fees, no timing opinion, the third arm that "
        "prices acting on the signal) and DRAW-1..3 (twenty names from the pool in sticky hash "
        "order, seeds 453-455, the error bar). Distinct from short-term reversal (M0028, M0391: "
        "they buy last month's losers) and from smooth-path momentum (M0443). SUCCESS, written "
        "now: LATE beats MOM and the best DRAW on 2009-2015 return vs SPY, EARLY does worse than "
        "MOM, and LATE clears the 20% fall bar and DSR 0.90. Predictions: LATE and MOM differ by "
        "under 2 points a year because the filter keeps 40 of 80 names already ranked high; "
        "last-month winners as a class lag SPY, since one-month returns tend to reverse."),
    expected_failure=(
        "The timing rank does no better than a random half of last month's winners: LATE, EARLY "
        "and MOM sit within the draws' spread. One-month winners reverse (M0028), so every arm "
        "may lag SPY in 2009-2015 through reversal, time in cash and fees on 20 monthly "
        "slots, and any edge in a recent paper may have faded. Three draws are a thin error "
        "bar. If so, queue the late share as a weight on a long-horizon book, or drop the family."),
    candidates=(
        _v("LATE", Params(mode="late"), "top 80 by 21-day return, highest late-share half, best 20"),
        _v("EARLY", Params(mode="early"), "top 80 by 21-day return, lowest late-share half, best 20"),
        _v("MOM", Params(mode="mom"), "20 best 21-day returns, no timing opinion"),
        _v("DRAW-1", Params(seed=453), "hash draw of 20 from the pool, seed 453"),
        _v("DRAW-2", Params(seed=454), "hash draw of 20 from the pool, seed 454"),
        _v("DRAW-3", Params(seed=455), "hash draw of 20 from the pool, seed 455"),
    ),
    seen_keys=("concept:late-month-gain-share-return-timing",),
)
