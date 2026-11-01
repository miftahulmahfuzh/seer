"""M0470 — year-start losers over a quarter: hold last year's worst index members from January through March.

Source: variation of M0458. Branch (1983) and Reinganum (1983) (Journal of Financial Economics) found
the turn-of-the-year effect; published 1983, so the dev window (1996-2015) is long after the crowd.
M0458 held the worst decile for January only and led a random decile by about half a point a year
but trailed SPY, with one month in twelve of exposure. This variation gives the same bet three
months to work: January, February and March.

Mechanism of the book. The ranking is made once a year, on the last session before January, among
point-in-time index members that pass F4's screen ($5 price, 20M dollars traded a day), on their
252-session return through that December close. The worst decile (ceil(0.1 * eligible), capped at
30) is held equal weight. The same December ranking is kept for the February and March rebalances
(it is NOT re-ranked on the new trailing return, which would turn it into a different bet). Names
that left the index by then drop out of the pool; the rest are re-equalised monthly, as every
monthly-hold-frac book is. From April to December the whole book is SPY.

Arms, all pre-registered here:

* ``LOSE``  worst-decile 12-month losers, January-March, SPY otherwise (the idea).
* ``WIN``   the mirror: best-decile winners.
* ``DRAW``  a decile picked by a fixed hash of (symbol, year), no opinion in it: same trades, same
  three-month habit, no ranking. It prices what *acting* costs, which cancels between LOSE and WIN.
* Always-invested SPY is NOT a variant: it is configuration-identical to M0251-HOLD, which `lab run`
  refuses to repeat; the run scores against total-return SPY at the same fees.

LOSE against DRAW is the real test; LOSE against SPY says whether the habit is worth its fees.

Assumptions, written before the run: formation fixed at the December close; held names are priced
from the history at each rebalance. Reads only bars dated <= data_date.
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

ADDED = date(2026, 11, 1)

Side = Literal["losers", "winners", "draw"]
_SIDES: tuple[str, ...] = ("losers", "winners", "draw")
SCREEN = FactorParams(rank="momentum", top=30, mom_n=252, mom_skip=0, trend=None)
DECILE = 0.10


@dataclass(frozen=True, slots=True)
class JanParams:
    side: Side = "losers"
    cap: int = 30
    months: int = 3  # January through this many months

    def __post_init__(self) -> None:
        if self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")
        if not isinstance(self.cap, int) or self.cap < 1:
            raise ValueError(f"cap must be an int >= 1, got {self.cap!r}")
        if not isinstance(self.months, int) or not 1 <= self.months <= 12:
            raise ValueError(f"months must be 1..12, got {self.months!r}")

    def as_dict(self) -> dict[str, str]:
        return {"side": self.side, "cap": str(self.cap), "months": str(self.months)}


def _check(params: object) -> JanParams:
    if not isinstance(params, JanParams):
        raise TypeError(f"params must be JanParams, got {type(params).__name__}")
    return params


def _draw_key(symbol: str, year: int) -> str:
    return hashlib.sha256(f"M0470|{symbol}|{year}".encode()).hexdigest()


def choose(rows: list[FactorRow], data_date: date, params: JanParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED]
    if not pool:
        return []
    k = min(params.cap, max(1, -(-len(pool) // 10)))  # ceil(0.1 * n), capped
    year = dates.next_session(data_date).year  # data_date is the December formation close
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
    out = []
    for r in chosen:  # priced on data_date, not on the December formation close
        h = history.get(r.symbol)
        if h is None or h.index_of(data_date) is None:
            continue
        t = target_from_close(r.symbol, last_close(h, data_date), w)
        if t is not None:
            out.append(t)
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


class YearStartLosersAllocator:
    """SPY, except in the held quarter, when a December-chosen decile of index members replaces it.

    The ranking is fixed at the December close; the later months only re-equalise it.
    """

    id = "M0470"

    def lookback(self, params: Any) -> int:
        _check(params)
        # the formation close is up to a quarter (~66 sessions, 70 for slack) behind the rebalance
        return max(DV_N, SCREEN.vol_n + 1, SCREEN.mom_n + 1) + 70

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
        return dates.next_session(data_date).month <= p.months

    def _formation(self, data_date: date) -> date:
        """The last session of the December before the held quarter (data_date itself in December)."""
        return dates.prev_session(date(dates.next_session(data_date).year, 1, 1))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not self._on(data_date, p):
            return _spy(history, data_date)
        f = self._formation(data_date)
        rows = factor_rows({k: h.upto(f) for k, h in history.items() if h.index_of(f) is not None},
                           members, f, SCREEN) if f != data_date else factor_rows(history, members, data_date, SCREEN)
        return build(choose(rows, f, p), history, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> JanPrepared:
        return JanPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, JanPrepared):
            raise TypeError(f"prepared must be JanPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not self._on(data_date, p):
            return _spy(prepared.history, data_date)
        f = self._formation(data_date)
        rows = prepared.factor.rows_on(members, f, SCREEN)
        return build(choose(rows, f, p), prepared.history, data_date, p)


JAN = YearStartLosersAllocator()


def _v(suffix: str, params: JanParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0470-{suffix}", family="M0470",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=JAN, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0470",
    name="Year-start losers: hold last year's worst index members through the first quarter",
    family="stock-tax-loss-rebound",
    source_kind="variation",
    source_ref="parent M0458; Branch (1983) and Reinganum (1983), Journal of Financial Economics",
    parent_id="M0458",
    hypothesis=(
        "M0458 held the worst-decile 12-month losers for January only and led a random decile by "
        "about half a point a year but trailed SPY. Hold the same book January through March "
        "(three months of exposure instead of one). Published 1983 (Branch; Reinganum; Roll), so "
        "the dev window 1996-2015 is after the crowd: expect fade, and judge 2009-2015 first. On the "
        "last session before January, among point-in-time index members passing F4's screen ($5, "
        "20M dollars a day), rank on 252-session return and hold the worst decile (capped at 30) "
        "equal weight through March on that December ranking; SPY April to December. Fractional "
        "shares at Gotrade's real fees on monthly-hold-frac-gotrade. Arms: LOSE (the idea), WIN "
        "(the mirror: best decile), DRAW (a hash-picked decile, same three-month habit, no ranking: "
        "the always-invested no-opinion control for the habit's cost). Always-invested SPY is the "
        "run's own benchmark (a variant would repeat M0251-HOLD, which the lab refuses). Success: "
        "LOSE beats total-return SPY, worst fall under the bar, LOSE > DRAW, and the gain holds in "
        "2009-2015. Three months in twelve are traded."
    ),
    expected_failure=(
        "The January effect faded after the mid-1980s and among large index members it was never "
        "strong. Nine months of SPY plus three of a 30-name book will track SPY within a point or "
        "two a year, so the DSR at the lab's N will not clear 0.90 whatever the sign. The store has "
        "no delisted names, so December losers that went on to die are missing and the survivors "
        "are the rebounders: survivorship flatters LOSE most in the thin-coverage late 1990s. "
        "Extra months after January may dilute the effect (it is concentrated in the first days) "
        "and add fees. Expect LOSE ~ DRAW, and both to lag SPY after fees on 2009-2015."
    ),
    candidates=(
        _v("LOSE", JanParams(side="losers"),
           "Worst decile of 12-month losers (max 30) held January-March, SPY otherwise"),
        _v("WIN", JanParams(side="winners"),
           "Mirror: best decile of 12-month winners held January-March, SPY otherwise"),
        _v("DRAW", JanParams(side="draw"),
           "No-opinion arm: a hash-picked decile for January, SPY otherwise (prices the habit)"),
    ),
    seen_keys=(
        "concept:tax-loss-selling-january-rebound",
        "concept:year-start-losers-first-quarter",
    ),
)
