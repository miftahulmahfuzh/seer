"""M0476 — year-start winners with an always-invested control (a 2x2: winners vs no-opinion draw, quarter vs all year).

Source: variation of M0470. M0470's mirror (best 12-month index members held January to March)
led SPY on the owner's deposits but no fully invested, no-opinion arm was registered, so the cost of
the seasonal habit was unpriced. Momentum is published (Jegadeesh and Titman 1993, Journal of
Finance), so the dev window 1996-2015 is after the crowd: expect fade and judge 2009-2015 first.

Mechanism, identical to M0470: ranked once at the December close among point-in-time index members
passing F4's screen ($5, 20M dollars a day) on 252-session return; the top decile (capped at 30) is
held equal weight, re-equalised monthly, on that December ranking. The all-year arms re-rank at
each quarter start (a December-ranked book held eleven months needs more history than the smoke
market carries, and a 252-day ranking that old is a different bet anyway). The arms differ only in what is
held outside the first quarter and in whether the pick has an opinion:

* ``WIN-Q``    winners January-March, SPY otherwise (M0470's mirror, the habit).
* ``WIN-ALL``  winners held all year, re-picked at each quarter start: the always-invested book.
* ``DRAW-Q``   a hash-picked decile January-March, SPY otherwise: the habit with no opinion.
* ``DRAW-ALL`` a hash-picked decile all year (re-drawn each quarter): always invested, no opinion.

WIN-Q vs WIN-ALL prices the seasonal switch; WIN vs DRAW (either schedule) prices the ranking;
the diagonal DRAW-ALL is the cost of simply holding 30 index names instead of SPY. Allocator id
is M0476 so the digests are new; the configuration is not a repeat of M0470-WIN.

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
class BookParams:
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


def _check(params: object) -> BookParams:
    if not isinstance(params, BookParams):
        raise TypeError(f"params must be BookParams, got {type(params).__name__}")
    return params


def _draw_key(symbol: str, stamp: str) -> str:
    return hashlib.sha256(f"M0476|{symbol}|{stamp}".encode()).hexdigest()


def choose(rows: list[FactorRow], data_date: date, params: BookParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED]
    if not pool:
        return []
    k = min(params.cap, max(1, -(-len(pool) // 10)))  # ceil(0.1 * n), capped
    stamp = data_date.isoformat()  # data_date is the quarter-start formation close
    if params.side == "losers":
        pool.sort(key=lambda r: (r.momentum, r.symbol))
    elif params.side == "winners":
        pool.sort(key=lambda r: (-r.momentum, r.symbol))
    else:
        pool.sort(key=lambda r: _draw_key(r.symbol, stamp))
    return pool[:k]


def build(chosen: list[FactorRow], history: Mapping[str, History], data_date: date,
          params: BookParams) -> tuple[Target, ...]:
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


class YearStartBookAllocator:
    """SPY, except in the held months, when a December-chosen decile of index members replaces it.

    The ranking is fixed at the December close; the later months only re-equalise it. With
    months=12 the book is held all year and re-picked at each quarter start.
    """

    id = "M0476"

    def lookback(self, params: Any) -> int:
        _check(params)
        # the formation close is at most a quarter (~66 sessions, 70 for slack) behind the rebalance
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

    def _on(self, data_date: date, p: BookParams) -> bool:
        return dates.next_session(data_date).month <= p.months

    def _formation(self, data_date: date) -> date:
        """The last session before the calendar quarter being held (data_date itself on that day).

        For the January-March arms this is the December close, as in M0470; the all-year arms
        re-pick at each quarter start so no ranking is ever older than a quarter.
        """
        nxt = dates.next_session(data_date)
        return dates.prev_session(date(nxt.year, 3 * ((nxt.month - 1) // 3) + 1, 1))

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


JAN = YearStartBookAllocator()


def _v(suffix: str, params: BookParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0476-{suffix}", family="M0476",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=JAN, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0476",
    name="Year-start winners with an always-invested control",
    family="stock-tax-loss-rebound",
    source_kind="variation",
    source_ref="parent M0470; Jegadeesh and Titman (1993), Journal of Finance",
    parent_id="M0470",
    hypothesis=(
        "M0470's mirror (best 12-month stocks held January to March) led SPY by 1.3 points a year "
        "on the owner's deposits, 8.5% vs 7.2%, but no fully invested, no-opinion arm was "
        "registered so the cost of the habit is unpriced. Register a 2x2 at Gotrade's real "
        "fractional fees (monthly-hold-frac-gotrade): the December winners decile (capped at 30, "
        "F4 screen, 252-session return) held January-March with SPY otherwise, the same rule "
        "held all year and re-picked at each quarter start, and a hash-picked decile on both schedules. "
        "Momentum was published in 1993, so expect fade and judge 2009-2015 first. Success: "
        "WIN-ALL or WIN-Q beats total-return SPY, worst fall under the bar, WIN > DRAW on the same "
        "schedule, and the gain holds in 2009-2015. Kin of failed momentum books is likely to "
        "block promotion."
    ),
    expected_failure=(
        "A widely published anomaly fades; winners in an index of large names are mostly SPY's "
        "own leaders and add little. The no-opinion all-year book probably lags SPY by the fees on "
        "a 30-name equal-weight book, so WIN-ALL will beat DRAW-ALL only by what momentum adds. "
        "The seasonal switch is likely worth little either way. The store has no delisted names, "
        "which flatters winners least and losers most. The DSR at the lab's N will not clear 0.90."
    ),
    candidates=(
        _v("WIN-Q", BookParams(side="winners", months=3),
           "Best-decile 12-month winners (max 30) held January-March, SPY otherwise (the habit)"),
        _v("WIN-ALL", BookParams(side="winners", months=12),
           "Winners held all year, re-picked each quarter start (always invested)"),
        _v("DRAW-Q", BookParams(side="draw", months=3),
           "Hash-picked decile January-March, SPY otherwise (the habit with no opinion)"),
        _v("DRAW-ALL", BookParams(side="draw", months=12),
           "Hash-picked decile held all year, re-drawn each quarter (always invested, no opinion)"),
    ),
    seen_keys=(
        "concept:year-start-winners-always-invested-control",
        "concept:standing-always-invested-control-for-every-timing-method",
    ),
)
