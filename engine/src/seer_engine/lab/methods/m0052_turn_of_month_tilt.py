"""M0052 — Hold the stock book only over the turn of the month, SPY the rest of the time.

Source: Lakonishok & Smidt (1988), Are seasonal anomalies real? A ninety-year perspective, Rev.
Financial Studies 1(4); McConnell & Xu (2008), Equity returns at the turn of the month, Financial
Analysts Journal 64(2).
Idea: McConnell and Xu find that across 1926-2005 essentially all of the US equity premium arrived
in the four sessions from the last trading day of a month through the third of the next, as
month-end pay and pension flows are invested. If so, extra market exposure held only over those
sessions earns the premium at a higher rate than any other day of the month. Tested as a tilt, not
a timing switch, so it never sits in cash: SPY all month, and over the turn of the month a slice of
it moves into the highest-beta names among F4's screened index members (or into QQQ), then back.

Calendar: the decision on ``data_date`` d sets what is held from the open of ``next_session(d)``.
The tilt is held over the sessions from the second-last session of a month through the third
session of the next (five sessions: bought at the open of the second-last session, sold at the open
of the fourth), so the close-to-close returns of the last session and the first three are all
inside. The NYSE session calendar is published years ahead, so reading where a session falls in its
month is not a peek at prices. Within one window the basket is chosen once, on the night before the
window opens (the anchor), from bars dated <= the anchor; the window's later nights re-send that
basket with prices refreshed to d, so the daily clock does not churn the picks.

Pure: no clock, no randomness, no I/O. Reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from functools import lru_cache
from typing import Any, Literal

import numpy as np

from seer_engine import dates
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, to_weight
from seer_engine.sim.rules import DAILY_SWITCH
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import DV_N, EXCLUDED

ADDED = date(2026, 10, 9)

# Daily decisions, resized to the target weights (the SPY slice has to be sold to fund the tilt),
# fractional, at Gotrade's real fees. No preset of this id exists yet: it runs on dev, and a win
# would need a `feature-wish` for one before `promote` could take it.
DAILY_RESIZE_FRAC_GOTRADE = replace(
    DAILY_SWITCH, id="daily-resize-frac-gotrade", resize=True, fractional=True, cost_model="gotrade"
)

Window = Literal["tom", "mid"]
_WINDOWS: tuple[str, ...] = ("tom", "mid")
Tilt = Literal["beta", "qqq"]
_TILTS: tuple[str, ...] = ("beta", "qqq")


@dataclass(frozen=True, slots=True)
class TomParams:
    slice: float = 0.5  # share of equity moved out of SPY into the tilt during the window
    tilt: Tilt = "beta"  # "beta": the `top` highest-beta screened members; "qqq": QQQ
    window: Window = "tom"  # "tom": 2nd-last .. 3rd session; "mid": the 9th .. 13th session (control)
    top: int = 20
    beta_n: int = 60  # daily returns in the beta estimate
    min_dollar_volume: float = 20_000_000.0  # F4's screen: 20-day mean close x volume > this
    min_price: float = 5.0  # F4's screen: close >= this

    def __post_init__(self) -> None:
        if not 0.0 < self.slice <= 1.0:
            raise ValueError(f"slice must be in (0, 1], got {self.slice}")
        if self.tilt not in _TILTS:
            raise ValueError(f"tilt must be one of {_TILTS}, got {self.tilt!r}")
        if self.window not in _WINDOWS:
            raise ValueError(f"window must be one of {_WINDOWS}, got {self.window!r}")
        if self.top < 1 or self.beta_n < 20:
            raise ValueError("top must be >= 1 and beta_n >= 20")

    def as_dict(self) -> dict[str, str]:
        return {
            "slice": repr(self.slice),
            "tilt": self.tilt,
            "window": self.window,
            "top": str(self.top),
            "beta_n": str(self.beta_n),
            "min_dollar_volume": repr(self.min_dollar_volume),
            "min_price": repr(self.min_price),
        }


@lru_cache(maxsize=4096)
def _month_sessions(year: int, month: int) -> tuple[date, ...]:
    first = date(year, month, 1)
    last = date(year + (month == 12), month % 12 + 1, 1)
    return tuple(s for s in dates.sessions(first, last) if s.month == month)


def in_window(session: date, window: Window) -> bool:
    """True when ``session`` is a session the tilt is held over."""
    month = _month_sessions(session.year, session.month)
    k = month.index(session)  # 0-based position in its month
    if window == "tom":
        return k <= 2 or k >= len(month) - 2
    return 8 <= k <= 12


def anchor(data_date: date, window: Window) -> date:
    """The decision date of the window that ``next_session(data_date)`` sits in: the session before
    the window's first session. Never after ``data_date``; only valid when that session is in a window."""
    s = dates.next_session(data_date)
    while in_window(dates.prev_session(s), window):
        s = dates.prev_session(s)
    return dates.prev_session(s)


def _beta_basket(history: Mapping[str, History], members: AbstractSet[str], at: date,
                 params: TomParams) -> list[str]:
    """The ``top`` highest-beta screened members on ``at`` (bars dated <= ``at`` only), best first."""
    spy = history.get("SPY")
    if spy is None:
        return []
    j = spy.index_of(at)
    if j is None or j < params.beta_n:
        return []
    day = as_day(at)
    spy_days = spy.dates[j - params.beta_n : j + 1]
    spy_ret = np.diff(np.log(spy.close[j - params.beta_n : j + 1]))
    var = float(np.var(spy_ret))
    if not var > 0.0:
        return []
    scored: list[tuple[float, str]] = []
    for s in sorted(members):
        if s in EXCLUDED:
            continue
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(at)
        if i is None or i < params.beta_n or h.dates[i] != day:
            continue
        if not np.array_equal(h.dates[i - params.beta_n : i + 1], spy_days):
            continue  # a gap in the window: the returns would not line up with SPY's
        c = h.close[i - params.beta_n : i + 1]
        if not np.all(np.isfinite(c)) or not np.all(c > 0) or c[-1] < params.min_price:
            continue
        dv = float(np.mean(h.close[i - DV_N + 1 : i + 1] * h.volume[i - DV_N + 1 : i + 1]))
        if not dv > params.min_dollar_volume:
            continue
        r = np.diff(np.log(c))
        beta = float(np.mean((r - r.mean()) * (spy_ret - spy_ret.mean()))) / var
        if np.isfinite(beta):
            scored.append((-beta, s))
    return [s for _, s in sorted(scored)[: params.top]]


class Alloc:
    """SPY at full weight, except over the window, when ``slice`` of it moves into the tilt."""

    id = "M0052"

    def lookback(self, params: TomParams) -> int:
        return max(params.beta_n, DV_N) + 1 + 10  # + room for the anchor to sit a few sessions back

    def symbols(self, params: TomParams) -> tuple[str, ...]:
        return ("SPY", "QQQ") if params.tilt == "qqq" else ("SPY",)

    def holds(self, params: TomParams) -> tuple[str, ...]:
        return ("SPY", "QQQ") if params.tilt == "qqq" else ("SPY",)

    def uses_members(self, params: TomParams) -> bool:
        return params.tilt == "beta"

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: TomParams) -> tuple[Target, ...]:
        spy_close = last_close(history.get("SPY"), data_date)
        if spy_close is None:
            return ()
        spy_all = target_from_close("SPY", spy_close, to_weight(1))
        if not in_window(dates.next_session(data_date), params.window):
            return () if spy_all is None else (spy_all,)
        if params.tilt == "qqq":
            q_close = last_close(history.get("QQQ"), data_date)
            names = [] if q_close is None or history["QQQ"].index_of(data_date) is None else ["QQQ"]
        else:
            names = _beta_basket(history, members, anchor(data_date, params.window), params)
        out: list[Target] = []
        if names:
            w = to_weight(params.slice / len(names))
            for s in names:
                c = last_close(history.get(s), data_date)
                t = None if c is None else target_from_close(s, c, w)
                if t is not None:
                    out.append(t)
        if not out:
            return () if spy_all is None else (spy_all,)
        rest = 1.0 - params.slice
        if rest > 0.0:
            spy = target_from_close("SPY", spy_close, to_weight(rest))
            if spy is not None:
                out.append(spy)
        return tuple(out)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: TomParams) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


ALLOC = Alloc()


def _v(suffix: str, params: TomParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0052-{suffix}", family="M0052", rules=DAILY_RESIZE_FRAC_GOTRADE, allocator=ALLOC,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0052",
    name="Hold the stock book only over the turn of the month, SPY the rest of the time",
    family="stock-calendar-turn-of-month",
    source_kind="paper",
    source_ref=(
        "Lakonishok & Smidt (1988), Are seasonal anomalies real? A ninety-year perspective, Rev. "
        "Financial Studies 1(4); McConnell & Xu (2008), Equity returns at the turn of the month, "
        "Financial Analysts Journal 64(2)"
    ),
    parent_id=None,
    hypothesis=(
        "Published 1988 and again in 2008, so the dev window (1996-2015) straddles the second "
        "publication. McConnell and Xu find that across 1926-2005 essentially all of the US equity "
        "premium arrived in the four sessions from the last trading day of a month through the "
        "third of the next. If the flows behind it persist, extra market exposure held only then "
        "earns the premium at several times its usual daily rate. Held as a tilt, never as cash: "
        "SPY all month, and over five sessions (bought at the open of the second-last session, "
        "sold at the open of the fourth) a slice of 25%, 50% or 100% moves into the 20 highest "
        "60-day-beta names among F4's screened index members, equal weight, fractional, at "
        "Gotrade's real fees on the owner's funding; a fourth variant swaps the whole book into QQQ "
        "instead (two large orders, not forty small ones), and a fifth moves the 50% slice over a "
        "mid-month window of the same length (sessions 9-13) as the control that separates the "
        "calendar from plain beta and fees. Success: a TOM variant beats SPY TR with a worst fall "
        "under 20% and beats its mid-month control by a clear margin."
    ),
    expected_failure=(
        "The fees eat it. Every month the slice makes a round trip into the tilt and back, and so "
        "does the SPY it replaces: at Gotrade's schedule (0.2% trading fee, a minimum of $0.10, "
        "regulatory fee and 11% VAT on top) that is about 1.2% of the slice a month, some 14% of it "
        "a year, while a 1.5-beta basket over five sessions adds perhaps 0.3-0.5% a month even if "
        "the effect is intact. So every variant lags SPY, the 100% switch most of all, and the "
        "mid-month control lags by about the same amount, which would say the calendar adds "
        "little after costs. The effect has also faded since 2008, so 2009-2015 shows the least."
    ),
    candidates=(
        _v("T25", TomParams(slice=0.25), "25% of SPY into the 20 highest-beta members over the turn of the month"),
        _v("T50", TomParams(slice=0.5), "50% of SPY into the 20 highest-beta members over the turn of the month"),
        _v("T100", TomParams(slice=1.0),
           "The whole book into the 20 highest-beta members over the turn of the month, SPY otherwise"),
        _v("Q100", TomParams(slice=1.0, tilt="qqq"),
           "The whole book from SPY into QQQ over the turn of the month: the same tilt in two orders"),
        _v("MID50", TomParams(slice=0.5, window="mid"),
           "Control: the 50% high-beta slice over sessions 9-13 of the month instead of the turn"),
    ),
    seen_keys=("concept:turn-of-month", "concept:calendar-anomaly", "concept:turn-of-month-beta-tilt"),
)
