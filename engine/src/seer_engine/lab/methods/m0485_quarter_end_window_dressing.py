"""M0485 — Quarter-end window dressing: the prior quarter's winners, held only around the quarter's turn.

Source: Lakonishok, Shleifer, Thaler & Vishny (1991), "Window dressing by pension fund managers",
American Economic Review 81(2); Ng & Wang (2004), "Institutional trading and the turn-of-the-year
effect", Journal of Financial Economics 74(2).
Idea: fund managers show their winners and shed their losers before each quarter's report goes
out, so the stocks that did best over the quarter should get a push in the last days of it and a
little after, when the buying stops. The test holds the index members with the best 63-session
return in a window of the last five sessions of each quarter plus the first three of the next, and
holds SPY the rest of the time.

Three controls make the result readable, and none of them is the stock picker's own opinion:

    * **DRAW** takes a hash-ordered draw of the same size from the same screened pool in the same
      window, so the window and the fees are the same and only the *rank* is removed.
    * **WIN-ALWAYS** holds the same winners the whole year (re-picked at each window opening), so
      the cost of stepping in and out by the calendar is priced against the calendar's opinion.
    * **SPY-ALWAYS** is the frame with every opinion removed.

The window is read on the session the decision fills at, ``S = next_session(d)``. The ranking is
fixed once, on the decision date ``R`` that precedes the window's first session, and held for the
whole window, so the book re-ranks four times a year and not daily. Reads only bars dated <= d
(``R <= d`` always); the NYSE calendar is treated as known in advance, as in M0120. Pure: the draw
is a fixed hash of seed, symbol and quarter-end date.
"""

from __future__ import annotations

import calendar
import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from types import MappingProxyType
from typing import Any, Literal

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
    factor_lookback,
    factor_rows,
    prepare_factor,
)

ADDED = date(2026, 11, 1)
BENCH = "SPY"
TOP = 20
BEFORE = 5  # sessions of the old quarter in the window
AFTER = 3  # sessions of the new quarter in the window
#: The lab's standard member screen with the trend gate off; momentum is the return over the last
#: 63 sessions (about one quarter), skipping nothing.
SCREEN = FactorParams(rank="momentum", top=TOP, mom_n=63, mom_skip=0, trend=None)
#: The ranking is made on R, up to a quarter (about 66 sessions) before the decision date in the
#: always-held arms, so the history window carries that run-up on top of the screen's own.
LOOKBACK = factor_lookback(SCREEN) + 70

Pick = Literal["winners", "draw", "spy"]
When = Literal["window", "always"]
_PICKS: tuple[str, ...] = ("winners", "draw", "spy")
_WHENS: tuple[str, ...] = ("window", "always")


@dataclass(frozen=True, slots=True)
class DressParams:
    """Who is picked, whether they are held only in the window, and the draw's seed."""

    pick: Pick = "winners"
    when: When = "window"
    seed: int = 0
    top: int = TOP

    def __post_init__(self) -> None:
        if not isinstance(self.pick, str) or self.pick not in _PICKS:
            raise ValueError(f"pick must be one of {_PICKS}, got {self.pick!r}")
        if not isinstance(self.when, str) or self.when not in _WHENS:
            raise ValueError(f"when must be one of {_WHENS}, got {self.when!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")
        if isinstance(self.top, bool) or not isinstance(self.top, int):
            raise TypeError(f"top must be an int, got {type(self.top).__name__}")
        if not 1 <= self.top <= 100:
            raise ValueError(f"top must be in [1, 100], got {self.top}")

    def as_dict(self) -> dict[str, str]:
        return {"pick": self.pick, "when": self.when, "seed": str(self.seed), "top": str(self.top)}


def _check(params: object) -> DressParams:
    if not isinstance(params, DressParams):
        raise TypeError(f"params must be DressParams, got {type(params).__name__}")
    return params


@lru_cache(maxsize=None)
def geometry(quarter_end: date) -> tuple[date, frozenset[date]]:
    """(R, window): the ranking decision date and the sessions the window covers."""
    old = dates.sessions(quarter_end - timedelta(days=20), quarter_end)[-BEFORE:]
    new = dates.sessions(quarter_end + timedelta(days=1), quarter_end + timedelta(days=14))[:AFTER]
    window = tuple(old) + tuple(new)
    return dates.prev_session(window[0]), frozenset(window)


def quarter_ends(year: int) -> tuple[date, ...]:
    return tuple(date(year, m, calendar.monthrange(year, m)[1]) for m in (3, 6, 9, 12))


def _ends_near(s: date) -> list[date]:
    return sorted(quarter_ends(s.year - 1) + quarter_ends(s.year))


def window_state(data_date: date) -> tuple[bool, date | None, date | None]:
    """(in_window, quarter_end, R) for the latest window opened on or before the decision."""
    s = dates.next_session(data_date)
    in_window = False
    latest: tuple[date, date] | None = None
    for qe in _ends_near(s):
        r, window = geometry(qe)
        if s in window:
            in_window = True
        if r <= data_date:
            latest = (qe, r)
    if latest is None:
        return in_window, None, None
    return in_window, latest[0], latest[1]


def draw(seed: int, symbol: str, quarter_end: date) -> int:
    """A fixed 64-bit hash of seed, symbol and the quarter-end date."""
    tag = f"{seed}|{symbol}|{quarter_end.isoformat()}".encode()
    return int.from_bytes(hashlib.blake2b(tag, digest_size=8).digest(), "big")


@dataclass(frozen=True, slots=True, eq=False)
class DressPrepared:
    history: Mapping[str, History]
    factor: FactorPrepared


class QuarterDressAllocator:
    """The picks while the window (or the whole year) says on, SPY otherwise."""

    id = "M0485"

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
        return _check(params).pick != "spy"

    def _spy(self, history: Mapping[str, History], data_date: date) -> tuple[Target, ...]:
        h = history.get(BENCH)
        if h is None or h.index_of(data_date) is None:
            return ()
        t = target_from_close(BENCH, last_close(h, data_date), equal_weight(1))
        return () if t is None else (t,)

    def _book(self, history: Mapping[str, History], rows: list[Any], qe: date, data_date: date,
              p: DressParams) -> tuple[Target, ...]:
        if p.pick == "winners":
            chosen = sorted(rows, key=lambda r: (-r.momentum, r.symbol))[: p.top]
        else:
            chosen = sorted(rows, key=lambda r: (draw(p.seed, r.symbol, qe), r.symbol))[: p.top]
        w = equal_weight(p.top)
        out: list[Target] = []
        for row in chosen:
            h = history.get(row.symbol)
            if h is None or h.index_of(data_date) is None:
                continue  # no bar today: this slot sits in cash rather than guess a price
            t = target_from_close(row.symbol, last_close(h, data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def _decide(self, history: Mapping[str, History], rows_at: Any, data_date: date,
                p: DressParams) -> tuple[Target, ...]:
        if p.pick == "spy":
            return self._spy(history, data_date)
        in_window, qe, r = window_state(data_date)
        if qe is None or r is None or (p.when == "window" and not in_window):
            return self._spy(history, data_date)
        book = self._book(history, rows_at(r), qe, data_date, p)
        return book if book else self._spy(history, data_date)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        return self._decide(history, lambda r: factor_rows(history, members, r, SCREEN),
                            data_date, p)

    def prepare(self, history: Mapping[str, History]) -> DressPrepared:
        return DressPrepared(MappingProxyType(dict(history)), prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, DressPrepared):
            raise TypeError(f"prepared must be DressPrepared, got {type(prepared).__name__}")
        p = _check(params)
        return self._decide(prepared.history,
                            lambda r: prepared.factor.rows_on(members, r, SCREEN), data_date, p)


DRESS = QuarterDressAllocator()


def _v(suffix: str, params: DressParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0485-{suffix}", family="M0485", rules=DAILY_HOLD_FRAC_GOTRADE,
                     allocator=DRESS, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0485",
    name="Quarter-end window dressing: prior-quarter winners in the last week",
    family="stock-quarter-end-dressing",
    source_kind="paper",
    source_ref=(
        "Lakonishok, Shleifer, Thaler & Vishny (1991), Window dressing by pension fund managers, "
        "AER 81(2); Ng & Wang (2004), Institutional trading and the turn-of-the-year effect, JFE"
    ),
    parent_id=None,
    hypothesis=(
        "Published 1991 and 2004, so the dev window's second half already sees a crowd that knows "
        "it; a fade after 2009 is the base case. Fund managers show winners and shed losers before "
        "each quarter ends. The index members with the best 63-session return, ranked once on the "
        "decision date before the window opens, are held at equal weight (20 names, fractional "
        "shares, Gotrade's real fees, a daily book) through the last five sessions of each quarter "
        "and the first three of the next, and the book sits in SPY the rest of the time, so the "
        "frame is SPY and the window is the only bet. Six variants: WIN (winners in the window), "
        "DRAW-A and DRAW-B (hash-ordered draws of 20 from the same screened pool in the same "
        "window, two seeds: the window and the fees are kept, the rank is removed), WIN-ALWAYS "
        "(the same winners held all year, re-picked each window opening, so the cost of the "
        "calendar habit is priced against the calendar's opinion), DRAW-ALWAYS (the draw held all "
        "year, so the third arm exists with no opinion in it) and SPY-ALWAYS (the frame with "
        "every opinion removed). The test: WIN beats SPY-ALWAYS on funded return after fees and "
        "beats both draws by more than their spread, clears the lab's dev screen (worst fall, "
        "profit factor, at least 100 trades) and is positive in 2009-2015. If WIN beats SPY but "
        "not the draws, the lift was the stock pool and not the window dressing."
    ),
    expected_failure=(
        "The effect is small (basis points a quarter), the book swaps 20 names four times a year "
        "and pays Gotrade's fee on every swap (about 160 orders a year on 20-name slots), and the "
        "benchmark leg is SPY itself so only the window can add return. Likely: WIN lags "
        "SPY-ALWAYS by the fee drag, and the two draws earn the same as WIN, meaning momentum "
        "rank adds nothing in an eight-session window. 2009-2015 is expected to lag because the "
        "anomaly was already published and crowded, and the 63-session winners of 2009-2011 were "
        "high-beta rebounders that mean-reverted. WIN-ALWAYS is a plain quarterly momentum book "
        "and kin of the lab's failed momentum books."
    ),
    candidates=(
        _v("WIN", DressParams("winners", "window"),
           "Prior-quarter winners in the quarter-end window, SPY otherwise"),
        _v("DRAW-A", DressParams("draw", "window", 4851),
           "A hash-ordered draw of the same size in the same window, SPY otherwise"),
        _v("DRAW-B", DressParams("draw", "window", 4852),
           "A second seed of the same blind draw in the same window"),
        _v("WIN-ALWAYS", DressParams("winners", "always"),
           "The same winners held all year, re-picked at each window opening"),
        _v("DRAW-ALWAYS", DressParams("draw", "always", 4851),
           "The blind draw held all year: the book with no opinion in it"),
        _v("SPY-ALWAYS", DressParams("spy", "always"),
           "Control: SPY only, through the same fee and deposit path"),
    ),
    seen_keys=(
        "concept:quarter-end-window-dressing",
        "concept:prior-quarter-winners-last-week",
    ),
)
