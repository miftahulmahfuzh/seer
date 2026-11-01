"""M0462 — Sell a plain 12-1 winner once its own fall from its high since purchase passes a limit.

Source: a variation of M0460 (same 12-1 winners, same F4 screen, always invested), carrying a
per-stock trailing exit. Neighbours already in the lab: M0019 (a stop fixed at the entry price),
M0020 (the same with weekly re-entry), M0204 (a weekly loud-fall exit) -- all closed or rejected.
What none of them did: trail the stop from the stock's own HIGH since it was bought, so a winner
that has run up is protected at its peak and not at its cost. Trailing stops are old practice
(Kaufman, Trading Systems and Methods; Kaminski and Lo 2014, "When do stop-loss rules stop
losses?", J. Financial Markets 18).

**THE CLOCK.** Same as M0204: the split monthly/weekly cadence cannot drop one name mid-month, and
the book engine fixes a stop at entry, so a trailing stop cannot ride on a resting order. The
method runs on a weekly rank cadence (fractional, Gotrade's real fees) and rebuilds the month's
basket as a pure function of bars at every weekly decision:

    * S = the session after data date d; A = the first NYSE session of S's month; the ANCHOR is
      a = prev_session(A), the data date a month-start monthly-hold run would rank on;
    * the basket is the top twenty by 12-1 momentum among F4-screened members at a;
    * a name's HIGH is the highest close from the anchor through each check date; the CHECK dates
      are a, the data date before every ISO-week-opening session in (A, S], and d;
    * a name whose close on any check date is at or below high * (1 - limit) is out for the rest
      of the month (no refill until the re-pick), re-read statelessly from bars on every decision;
    * survivors keep their 1/20 weight; a freed slot is cash.

The anchor close stands in for the purchase price (the buy fills at the next open). The mirror arm
sells on the same rule applied to gains: a name at or above anchor close * (1 + limit) is out.
Every piece reads only bars dated at or before d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine import dates
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20_NOTREND
from seer_engine.lab.methods.m0064_pairs_laggard import WEEKLY_HOLD_FRAC_GOTRADE
from seer_engine.sim.book import Target
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    factor_lookback,
    factor_rows,
    factor_weights,
    prepare_factor,
    rank_rows,
)

ADDED = date(2026, 11, 1)

Side = Literal["none", "fall", "gain"]
_SIDES: tuple[str, ...] = ("none", "fall", "gain")
ANCHOR_SLACK = 25  # sessions in the longest month, plus slack


@dataclass(frozen=True, slots=True)
class DDExitParams:
    """``inner`` is F4's screen and book size; ``side`` which move triggers the exit; ``limit`` its size."""

    inner: FactorParams
    side: Side = "fall"
    limit: float = 0.15

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")
        if isinstance(self.limit, bool) or not isinstance(self.limit, float) or not 0.0 < self.limit < 1.0:
            raise ValueError(f"limit must be a float in (0, 1), got {self.limit!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "limit": repr(self.limit)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> DDExitParams:
    if not isinstance(params, DDExitParams):
        raise TypeError(f"params must be DDExitParams, got {type(params).__name__}")
    return params


def anchor_and_checks(data_date: date) -> tuple[date, tuple[date, ...]]:
    """The month's anchor data date and every check date from it through ``data_date``."""
    session = dates.next_session(data_date)
    month = dates.sessions(date(session.year, session.month, 1), session)
    anchor = dates.prev_session(month[0])
    checks = {anchor, data_date}
    for s in month[1:]:
        if s.isocalendar()[:2] != dates.prev_session(s).isocalendar()[:2]:
            checks.add(dates.prev_session(s))
    return anchor, tuple(sorted(c for c in checks if c <= data_date))


def exited(h: History | None, anchor: date, checks: tuple[date, ...], p: DDExitParams) -> bool:
    """True when the exit fired on any check date, reading closes from the anchor on."""
    if p.side == "none" or h is None or len(h) == 0:
        return False
    lo = int(np.searchsorted(h.dates, as_day(anchor), side="right")) - 1
    if lo < 0:
        return False
    base = float(h.close[lo])
    if not (np.isfinite(base) and base > 0.0):
        return False
    high = base
    for w in checks:
        k = int(np.searchsorted(h.dates, as_day(w), side="right")) - 1
        if k <= lo:
            continue
        seg = h.close[lo : k + 1]
        seg = seg[np.isfinite(seg)]
        if seg.size == 0:
            continue
        high = float(seg.max())
        c = float(h.close[k])
        if not (np.isfinite(c) and c > 0.0):
            continue
        if p.side == "fall" and c <= high * (1.0 - p.limit):
            return True
        if p.side == "gain" and c >= base * (1.0 + p.limit):
            return True
    return False


def _close_at(h: History | None, data_date: date) -> float | None:
    if h is None or len(h) == 0:
        return None
    k = int(np.searchsorted(h.dates, as_day(data_date), side="right")) - 1
    if k < 0:
        return None
    c = float(h.close[k])
    return c if np.isfinite(c) and c > 0.0 else None


class DrawdownExitAllocator:
    """The month's top-20 12-1 winners, re-read weekly, minus names past the exit. Nothing remembered."""

    id = "M0462"

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).inner) + ANCHOR_SLACK

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.inner.trend[0],) if p.inner.trend is not None else ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _decide(self, history: Mapping[str, History], rows, data_date: date,
                p: DDExitParams) -> tuple[Target, ...]:
        anchor, checks = anchor_and_checks(data_date)
        chosen = [r for r in rank_rows(rows(anchor), p.inner) if r.symbol not in EXCLUDED]
        out: list[Target] = []
        for row, weight in zip(chosen, factor_weights(chosen, p.inner), strict=True):
            if weight is None or exited(history.get(row.symbol), anchor, checks, p):
                continue
            close = _close_at(history.get(row.symbol), data_date)
            if close is None:
                continue
            target = target_from_close(row.symbol, close, weight)
            if target is not None:
                out.append(target)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)

        def rows(day: date):
            return factor_rows({s: h.upto(day) for s, h in history.items()}, members, day, p.inner)

        return self._decide(history, rows, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> tuple[Mapping[str, History], FactorPrepared]:
        return history, prepare_factor(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        history, factor = prepared
        p = _check(params)
        return self._decide(history, lambda day: factor.rows_on(members, day, p.inner), data_date, p)


DDEXIT = DrawdownExitAllocator()


def _v(suffix: str, side: Side, limit: float, rationale: str) -> Candidate:
    return Candidate(id=f"M0462-{suffix}", family="M0462", rules=WEEKLY_HOLD_FRAC_GOTRADE,
                     allocator=DDEXIT, params=DDExitParams(N20_NOTREND, side, limit),
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0462",
    name="Sell a winner once its own fall passes a limit",
    family="stock-own-drawdown-exit",
    source_kind="variation",
    parent_id="M0460",
    source_ref=(
        "M0460 for the host book (plain 12-1 winners, F4 screen, always invested); M0019, M0020, "
        "M0204 for the neighbouring per-stock exits; Kaminski and Lo 2014, J. Financial Markets 18"
    ),
    hypothesis=(
        "Trailing stops are decades old (published well before the dev window), so any edge is "
        "likely already crowded. No ranking tried so far has cut the worst fall of an always-"
        "invested momentum book. M0019 and M0020 stopped a name from its ENTRY price and M0204 sold "
        "on a loud short-term fall; this trails the stop from each name's own high since purchase, "
        "so a winner that has run is protected at its peak. RULE: each month hold the top 20 12-1 "
        "momentum names of the F4-screened members (5% each, no market switch); at each weekly "
        "check sell any name whose close is at or below its high since the month's anchor close "
        "times (1 - limit); no refill until the next monthly re-pick; a freed slot is cash. Clock: "
        "weekly rank cadence, fractional, Gotrade real fees (weekly-hold-frac-gotrade), since the "
        "split cadence only rescales total weight. Arms: FALL10, FALL15, FALL25 (the limit); GAIN15 "
        "(the mirror: sell a name up 15% from its anchor close, which tests whether the fall side "
        "matters at all); NONE (the same picks on the same weekly clock with no exit: the "
        "third arm that prices what acting on the exit costs, so a mirror reversal can be told "
        "from a dead rule). Success: a FALL arm cuts NONE's worst fall by 3+ points without losing "
        "more than 1 point a year, beats SPY TR on deposit-matched money, is positive in 2009-2015, "
        "and GAIN15 trails it clearly. Assumption: the anchor close stands in for the purchase "
        "price; the limits are fixed now, not tuned."
    ),
    expected_failure=(
        "M0019 and M0020 found per-stock exits fire together in market-wide falls, sell near the "
        "bottom and miss the rebound; M0155 found the book never owns the names that fell furthest. "
        "A momentum book's worst falls are crashes and rebounds (1998, 2000-02, 2009), so the "
        "tighter limits whipsaw most: FALL10 trades the most, pays Gotrade fees on small slots and "
        "sits in cash through recoveries, trailing NONE by 1-3 points a year without a lower worst "
        "fall. GAIN15 will likely trail worst, since it cuts the winners. The line runs through "
        "plain momentum, whose kin has test-failed, so any dev-eligible arm is a by-product and the "
        "hard gate will refuse it."
    ),
    candidates=(
        _v("FALL15", "fall", 0.15, "Sell a name 15% below its high since purchase: the main arm"),
        _v("FALL10", "fall", 0.10, "Tighter limit: more protection, more whipsaw"),
        _v("FALL25", "fall", 0.25, "Looser limit: fires only on real collapses"),
        _v("GAIN15", "gain", 0.15, "The mirror: sell a name up 15% from its anchor close"),
        _v("NONE", "none", 0.15, "Same picks, same weekly clock, no exit: the always-invested control"),
    ),
    seen_keys=(
        "concept:own-high-trailing-stop-momentum",
        "concept:per-stock-trailing-drawdown-exit",
    ),
)
