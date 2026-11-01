"""M0458 — December losers bounce in January: hold last year's worst index members for January only, SPY the rest of the year.

Source: general knowledge. Branch (1983) "Searching for seasonality in stock returns" and Reinganum
(1983) "The anomalous stock market behavior of small firms in January" (both Journal of Financial
Economics); Roll (1983) named the tax-loss-selling reading. Published 1983, so the dev window
(1996-2015) is long after the crowd knew it.
Idea: investors sell the year's losers in December to book a tax loss, which pushes them below value;
the pressure lifts on the first trading days of January and they bounce.

Mechanism of the book. On the last session before January (``S = next_session(d)`` falls in
January, the same reading M0120 uses for its calendar), rank point-in-time index members that pass
F4's screen ($5 price, 20M dollars traded a day) on their 252-session return through d, and hold the
worst decile equal weight, capped at 30 names so a slot is not thinner than a Gotrade fee can bear.
Every other month the whole book is SPY. The decile is ``ceil(0.1 * eligible)`` capped at 30.

Arms, all pre-registered here:

* ``LOSE``  worst-decile 12-month losers in January, SPY otherwise (the idea).
* ``WIN``   the mirror: best-decile winners in January, SPY otherwise.
* ``DRAW``  a decile picked by a fixed hash of (symbol, year), no opinion in it: same trades, same
  January-only habit, no ranking. It prices what *acting* costs, which cancels between LOSE and WIN.
* ``SPY``   always invested in SPY: the control the habit is judged against.

LOSE against DRAW is the real test: does ranking on losses beat a random decile held for the same
month. LOSE against SPY says whether the whole habit is worth its fees.

Assumptions, written before the run: the idea row said "worst-decile"; the cap at 30 is mine. The
formation window is the trailing 252 sessions through the last December close (calendar-year
return would need a month table; the difference is a few sessions). Reads only bars dated <= d.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from seer_engine import dates
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    DV_N,
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_rows,
    prepare_factor,
)
from seer_engine.strategies.f_index import TIMING, TimingParams

ADDED = date(2026, 11, 1)

Side = Literal["losers", "winners", "draw"]
_SIDES: tuple[str, ...] = ("losers", "winners", "draw")
SCREEN = FactorParams(rank="momentum", top=30, mom_n=252, mom_skip=0, trend=None)
DECILE = 0.10


@dataclass(frozen=True, slots=True)
class JanParams:
    side: Side = "losers"
    cap: int = 30
    month: int = 1  # the month the book is held in

    def __post_init__(self) -> None:
        if self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")
        if not isinstance(self.cap, int) or self.cap < 1:
            raise ValueError(f"cap must be an int >= 1, got {self.cap!r}")
        if not isinstance(self.month, int) or not 1 <= self.month <= 12:
            raise ValueError(f"month must be 1..12, got {self.month!r}")

    def as_dict(self) -> dict[str, str]:
        return {"side": self.side, "cap": str(self.cap), "month": str(self.month)}


def _check(params: object) -> JanParams:
    if not isinstance(params, JanParams):
        raise TypeError(f"params must be JanParams, got {type(params).__name__}")
    return params


def _draw_key(symbol: str, year: int) -> str:
    return hashlib.sha256(f"M0458|{symbol}|{year}".encode()).hexdigest()


def choose(rows: list[FactorRow], data_date: date, params: JanParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED]
    if not pool:
        return []
    k = min(params.cap, max(1, -(-len(pool) // 10)))  # ceil(0.1 * n), capped
    year = dates.next_session(data_date).year
    if params.side == "losers":
        pool.sort(key=lambda r: (r.momentum, r.symbol))
    elif params.side == "winners":
        pool.sort(key=lambda r: (-r.momentum, r.symbol))
    else:
        pool.sort(key=lambda r: _draw_key(r.symbol, year))
    return pool[:k]


def build(chosen: list[FactorRow], history: Mapping[str, History], data_date: date,
          params: JanParams) -> tuple[Target, ...]:
    if not chosen:
        return _spy(history, data_date)
    w = equal_weight(len(chosen))
    out = [t for r in chosen if (t := target_from_close(r.symbol, r.close, w)) is not None]
    return tuple(out) if out else _spy(history, data_date)


def _spy(history: Mapping[str, History], data_date: date) -> tuple[Target, ...]:
    h = history.get("SPY")
    if h is None or h.index_of(data_date) is None:
        return ()
    t = target_from_close("SPY", last_close(h, data_date), equal_weight(1))
    return (t,) if t is not None else ()


@dataclass
class JanPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)


class JanuaryTaxLossAllocator:
    """SPY, except in the held month, when a decile of index members replaces it.

    Held symbols get no special treatment: the book is re-chosen each month.
    """

    id = "M0458"

    def lookback(self, params: Any) -> int:
        _check(params)
        return max(DV_N, SCREEN.vol_n + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _on(self, data_date: date, p: JanParams) -> bool:
        return dates.next_session(data_date).month == p.month

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not self._on(data_date, p):
            return _spy(history, data_date)
        rows = factor_rows(history, members, data_date, SCREEN)
        return build(choose(rows, data_date, p), history, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> JanPrepared:
        return JanPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, JanPrepared):
            raise TypeError(f"prepared must be JanPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not self._on(data_date, p):
            return _spy(prepared.history, data_date)
        rows = prepared.factor.rows_on(members, data_date, SCREEN)
        return build(choose(rows, data_date, p), prepared.history, data_date, p)


JAN = JanuaryTaxLossAllocator()


def _v(suffix: str, params: JanParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0458-{suffix}", family="M0458",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=JAN, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0458",
    name="December losers bounce in January: the tax-loss-selling rebound among index members",
    family="stock-tax-loss-rebound",
    source_kind="knowledge",
    source_ref="",
    parent_id=None,
    hypothesis=(
        "Published 1983 (Branch; Reinganum; Roll), so the dev window 1996-2015 is after the crowd. "
        "Investors sell the year's losers in December for tax reasons, pushing them below value, "
        "and the pressure lifts in January. On the last session before January, among point-in-time "
        "index members passing F4's screen ($5, 20M dollars a day), hold the worst decile by "
        "252-session return (capped at 30 names) equal weight for January, SPY the other eleven "
        "months, in fractional shares at Gotrade's real fees on monthly-hold-frac-gotrade. Arms: "
        "LOSE (the idea), WIN (the mirror: best decile), DRAW (a hash-picked decile with the same "
        "January-only habit and no ranking), SPY (always invested, the control). If LOSE beats "
        "DRAW and WIN, ranking on losses carries the edge; if LOSE and WIN both beat DRAW the "
        "effect is January volatility, not tax selling. Success: LOSE beats total-return SPY with "
        "worst fall under the bar, LOSE > DRAW, and the gain holds in 2009-2015. Only one month "
        "in twelve is traded, so about 20 trades a year at most: the 100-trade bar may bind."
    ),
    expected_failure=(
        "Published long ago and tiny after fees: the January effect faded after the mid-1980s and "
        "among big index members (the screen keeps the book to large names) it was never strong. "
        "Eleven months of SPY plus one month of a 30-name book will track SPY within a point a "
        "year, so the DSR at N=294 will not clear 0.90 whatever the sign, and the trade count may "
        "fall under 100 over twenty years (about 20 a year, so it should just clear). The store has "
        "no delisted names, so the December losers that went on to die are missing and the "
        "survivors are the rebounders: survivorship flatters LOSE most in the thin-coverage late "
        "1990s. Expect LOSE ~ DRAW, and both to lag SPY after fees on 2009-2015."
    ),
    candidates=(
        _v("LOSE", JanParams(side="losers"),
           "Worst decile of 12-month losers (max 30) held for January, SPY otherwise"),
        _v("WIN", JanParams(side="winners"),
           "Mirror: best decile of 12-month winners held for January, SPY otherwise"),
        _v("DRAW", JanParams(side="draw"),
           "No-opinion arm: a hash-picked decile for January, SPY otherwise (prices the habit)"),
        Candidate(id="M0458-SPY", family="M0458", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                  allocator=TIMING, params=TimingParams(hold="SPY", signal="SPY", rule="always"),
                  rationale="Control: always invested in SPY, never switching", added=ADDED,
                  owner_inputs=()),
    ),
    seen_keys=(
        "concept:tax-loss-selling-january-rebound",
        "concept:december-losers-january-bounce",
    ),
)
