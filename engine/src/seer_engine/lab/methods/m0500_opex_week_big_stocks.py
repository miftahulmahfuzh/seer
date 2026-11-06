"""M0500 — Big stocks in option-expiration week: the largest index members only in the third-Friday week.

Source: Stivers & Sun (2013), "Returns and option activity over the option-expiration week for
S&P 100 stocks", Journal of Banking & Finance 37(11). Reserved by Sera batch 20261106-1616.
Idea: S&P 100 stocks earned about 0.45% in the week ending on the month's third Friday against
about 0.12% in other weeks (1996-2008); the authors tie it to option market makers unwinding delta
hedges into expiration, and the week after partly gives it back. The test holds the 25 largest
point-in-time index members by company size (``Market.market_value``), equal weight, during that
week and SPY (or cash) the rest of the month.

The arms, all on M0079's ``daily-hold-frac-gotrade`` (fractional shares, Gotrade's real fees,
asked every session; the book only changes at a week boundary):

    * **OPEX-SPY**: the big 25 in option-expiration week, SPY otherwise. The treatment.
    * **OPEX-CASH**: the big 25 in option-expiration week, cash otherwise. The paper's own framing
      (the week's return, nothing else), at a fraction of the market's exposure; never a strategy
      on its own, it isolates the week.
    * **WEEK1-SPY**: the calendar coin. The same rotation on the week ending the month's FIRST
      Friday, two weeks away from expiration: same names, same fees, same number of switches, a
      week with no expiration in it.
    * **POST-SPY**: the mirror. The same rotation on the week after expiration, which the paper
      says partly reverses. If OPEX beats POST by the paper's margin the signal is there.
    * **BIG-ALWAYS**: the third arm with no opinion. The same big 25 held every week, re-picked at
      each expiration week's opening, never stepping into SPY. Prices the habit of switching.
    * **SPY-ALWAYS**: SPY only on the same chassis, the frame with every opinion removed. Expected
      to be a book twin of M0485-SPY-ALWAYS (same preset, same SPY-only target); not a new book.

Assumptions written before any result. A week is the sessions Monday through Friday of the
calendar week holding the given Friday (when that Friday is a holiday the week ends Thursday, as
expiration did). The book is decided on the close before the week's first session and fills at
that session's open, so it holds Monday open to the next Monday open: it misses the gap into the
week and carries the gap out of it, a shift of one overnight from the paper's Friday-close
measure. The names are ranked once, on that decision date ``R``, and held through the week. Size
is market value with one share class per company (identical share count, the larger value kept --
the dedupe older size-weighted methods use), over the lab's standard member screen with the
trend gate off. Before share counts exist (1996) or on any session the book is empty, the arm
holds its off-week holding instead. The NYSE calendar is treated as known in advance, as in M0120
and M0485.

Market-aware (``market_fields = ("shares",)``): ``lab run`` refuses it on a store without share
counts, and every arm targets nothing on the history-only path (the lab's contract), so all six
arms run on the same store and the same code path. Pure: reads only bars and share counts dated
<= ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from typing import Any

import numpy as np

from seer_engine import dates
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0079_dividend_announcement_window import DAILY_HOLD_FRAC_GOTRADE
from seer_engine.sim.book import Target, equal_weight
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
)

ADDED = date(2026, 11, 6)
BENCH = "SPY"
TOP = 25
#: The lab's standard member screen with the trend gate off; the rank field is unused, size ranks.
SCREEN = FactorParams(rank="momentum", top=TOP, trend=None)
#: BIG-ALWAYS ranks at the latest expiration week's opening, up to about 25 sessions before d.
LOOKBACK = factor_lookback(SCREEN) + 40

WEEKS = ("opex", "week1", "post", "always", "spy")
OFFS = ("spy", "cash")


@dataclass(frozen=True, slots=True)
class OpexParams:
    """``week`` which week holds the big book (or always / spy only); ``off`` what is held otherwise."""

    week: str = "opex"
    off: str = "spy"
    top: int = TOP

    def __post_init__(self) -> None:
        if self.week not in WEEKS:
            raise ValueError(f"week must be one of {WEEKS}, got {self.week!r}")
        if self.off not in OFFS:
            raise ValueError(f"off must be one of {OFFS}, got {self.off!r}")
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 100:
            raise ValueError(f"top must be an int in [1, 100], got {self.top!r}")

    def as_dict(self) -> dict[str, str]:
        return {"week": self.week, "off": self.off, "top": str(self.top),
                "rank": "market-value", "class_rule": "identical-share-count"}


def _check(params: object) -> OpexParams:
    if not isinstance(params, OpexParams):
        raise TypeError(f"params must be OpexParams, got {type(params).__name__}")
    return params


def friday(year: int, month: int, k: int) -> date:
    """The k-th Friday of the month."""
    first = date(year, month, 1)
    return first + timedelta(days=(4 - first.weekday()) % 7 + 7 * (k - 1))


@lru_cache(maxsize=None)
def week_of(year: int, month: int, which: str) -> tuple[date, ...]:
    """The sessions of the month's chosen week: Monday to Friday of the calendar week."""
    if which == "week1":
        fri = friday(year, month, 1)
    elif which == "post":
        fri = friday(year, month, 3) + timedelta(days=7)
    else:  # opex (and the re-pick date for always)
        fri = friday(year, month, 3)
    return tuple(dates.sessions(fri - timedelta(days=4), fri))


def _months_near(s: date) -> list[tuple[int, int]]:
    out = []
    for dm in (-1, 0, 1):
        m = s.month + dm
        y = s.year + (m - 1) // 12
        out.append((y, (m - 1) % 12 + 1))
    return out


def window_state(data_date: date, which: str) -> tuple[bool, date | None]:
    """(in_week, R): whether the fill session lies in the chosen week, and the ranking date.

    For ``always`` R is the latest expiration week's decision date on or before ``data_date``."""
    s = dates.next_session(data_date)
    if which == "always":
        latest = None
        for y, m in _months_near(s):
            wk = week_of(y, m, "opex")
            if wk and dates.prev_session(wk[0]) <= data_date:
                latest = dates.prev_session(wk[0])
        return True, latest
    for y, m in _months_near(s):
        wk = week_of(y, m, which)
        if wk and s in wk:
            return True, dates.prev_session(wk[0])
    return False, None


@dataclass(frozen=True, slots=True, eq=False)
class OpexPrepared:
    history: Mapping[str, History]
    factor: FactorPrepared | None  # None on the plain history path
    market: Any  # the Market (share counts), or None when there is none


def _rows(prep: OpexPrepared, members: AbstractSet[str], d: date) -> list[FactorRow]:
    if prep.factor is not None:
        return prep.factor.rows_on(members, d, SCREEN)
    return factor_rows(prep.history, members, d, SCREEN)


def biggest(prep: OpexPrepared, rows: list[FactorRow], r: date, top: int) -> list[str]:
    """The ``top`` largest screened members by market value on R, one class per company."""
    mk = prep.market
    by_count: dict[float, tuple[float, str]] = {}
    for row in rows:
        v = mk.market_value(row.symbol, r)
        n = mk.shares_on(row.symbol, r)
        if v is None or n is None or not (np.isfinite(v) and v > 0.0):
            continue
        seen = by_count.get(n)
        if seen is None or (float(v), row.symbol) > seen:
            by_count[n] = (float(v), row.symbol)
    return [s for _, s in sorted(by_count.values(), key=lambda x: (-x[0], x[1]))[:top]]


def _spy(history: Mapping[str, History], d: date) -> tuple[Target, ...]:
    h = history.get(BENCH)
    if h is None or h.index_of(d) is None:
        return ()
    t = target_from_close(BENCH, last_close(h, d), equal_weight(1))
    return () if t is None else (t,)


def _run(prep: OpexPrepared, members: AbstractSet[str], d: date, p: OpexParams) -> tuple[Target, ...]:
    if prep.market is None:  # the lab's market-aware contract: no panel, no targets, on every arm
        return ()
    off = (lambda: _spy(prep.history, d)) if p.off == "spy" else (lambda: ())
    if p.week == "spy":
        return _spy(prep.history, d)
    in_week, r = window_state(d, p.week)
    if not in_week or r is None:
        return off()
    names = biggest(prep, _rows(prep, members, r), r, p.top)
    w = equal_weight(p.top)
    out: list[Target] = []
    for s in names:
        h = prep.history.get(s)
        if h is None or h.index_of(d) is None:
            continue  # no bar today: this slot sits in cash rather than guess a price
        t = target_from_close(s, last_close(h, d), w)
        if t is not None:
            out.append(t)
    return tuple(out) if out else off()


class OpexWeekAllocator:
    """The 25 largest index members in the chosen week of the month, SPY or cash otherwise."""

    id = "M0500"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        _check(params)
        return LOOKBACK

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def uses_members(self, params: Any) -> bool:
        return _check(params).week != "spy"

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no arm targets anything (the contract)."""
        return _run(OpexPrepared(history, None, None), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> OpexPrepared:
        return OpexPrepared(history, None, None)

    def prepare_market(self, market: Any) -> OpexPrepared:
        sized = hasattr(market, "market_value") and len(market.shares) > 0
        return OpexPrepared(market.history, prepare_factor(market.history), market if sized else None)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, OpexPrepared):
            raise TypeError(f"prepared must be OpexPrepared, got {type(prepared).__name__}")
        return _run(prepared, members, data_date, _check(params))


OPEX = OpexWeekAllocator()


def _v(suffix: str, params: OpexParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0500-{suffix}", family="M0500", rules=DAILY_HOLD_FRAC_GOTRADE,
                     allocator=OPEX, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0500",
    name="Big stocks in option-expiration week: hold the largest index members only in the week of each month's third Friday",
    family="stock-option-expiration-week",
    source_kind="paper",
    source_ref=(
        "Stivers & Sun (2013), Returns and option activity over the option-expiration week for "
        "S&P 100 stocks, Journal of Banking & Finance 37(11) 4226-4240; "
        "https://ideas.repec.org/a/eee/jbfina/v37y2013i11p4226-4240.html"
    ),
    parent_id=None,
    hypothesis=(
        "Published 2013 on a 1996-2008 sample, so the dev window is almost all in-sample for the "
        "paper and only 2013-2015 is out of sample; a strong dev result proves little and the "
        "verdict must say so. Stivers and Sun find S&P 100 stocks earn about 0.45% in the week "
        "ending on the month's third Friday against about 0.12% in other weeks, tied to option "
        "market makers' hedge rebalancing, with a partial reversal the week after. Treatment "
        "OPEX-SPY: the 25 largest point-in-time index members by market value (one class per "
        "company), equal weight, held Monday open to the next Monday open over expiration week, "
        "SPY otherwise; fractional shares at Gotrade's real fees, decided daily. Arms: OPEX-CASH "
        "(cash off-week, isolates the week), WEEK1-SPY (the calendar coin: the same rotation on "
        "the first-Friday week), POST-SPY (the mirror: the week after expiration), BIG-ALWAYS "
        "(the same big 25 every week, the no-opinion arm that prices the switching habit) and "
        "SPY-ALWAYS (the frame; expected to be a book twin of M0485-SPY-ALWAYS, not a new book). "
        "The test: OPEX-SPY beats SPY-ALWAYS on funded return after fees, beats WEEK1-SPY and "
        "POST-SPY by more than their gap to each other, beats BIG-ALWAYS (else the gain is the big "
        "stocks, not the week), clears the dev screen (worst fall, profit factor, 100 trades) "
        "and is positive against SPY in 2009-2015."
    ),
    expected_failure=(
        "The effect is about a third of a percent a week on 12 weeks a year (the paper's 0.45% "
        "less 0.12%), on about a quarter of the sessions, but the book swaps all of SPY for 25 names "
        "and back every month, roughly 600 orders a year on small slots, and Gotrade's fee on "
        "each eats most or all of it. Likely: OPEX-SPY lags SPY-ALWAYS by the fee drag, WEEK1-SPY "
        "and POST-SPY land within a point of it (the calendar coin cannot be told from the "
        "treatment), and BIG-ALWAYS tracks SPY closely because the big 25 are a large share of the "
        "index. A widely published anomaly fades: 2009-2015 expected to show no edge, and the "
        "one-overnight shift from the paper's Friday-close measure may cost part of the week. "
        "OPEX-CASH holds the market a quarter of the time and cannot beat SPY on return."
    ),
    candidates=(
        _v("OPEX-SPY", OpexParams("opex", "spy"),
           "The 25 biggest members in option-expiration week, SPY otherwise"),
        _v("OPEX-CASH", OpexParams("opex", "cash"),
           "The 25 biggest members in option-expiration week, cash otherwise: the week alone"),
        _v("WEEK1-SPY", OpexParams("week1", "spy"),
           "Calendar coin: the same rotation on the first-Friday week, no expiration in it"),
        _v("POST-SPY", OpexParams("post", "spy"),
           "Mirror: the same rotation on the week after expiration, which the paper says reverses"),
        _v("BIG-ALWAYS", OpexParams("always", "spy"),
           "No-opinion arm: the same big 25 every week, re-picked monthly, never switching"),
        _v("SPY-ALWAYS", OpexParams("spy", "spy"),
           "Control: SPY only, through the same fee and deposit path"),
    ),
    seen_keys=(
        "concept:option-expiration-week",
        "concept:third-friday-week-big-stocks",
    ),
)
