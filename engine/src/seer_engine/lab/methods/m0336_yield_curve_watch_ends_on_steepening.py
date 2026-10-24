"""M0336 — End the yield-curve watch when the curve steepens, not on a fixed two-year clock.

Source: general knowledge, a variation on M0173, M0167 and M0038 (Estrella & Mishkin 1996, NY Fed
Current Issues 2(7); public through the whole dev window). Reserved as an idea row by Sera
20261024-1624.

M0038, M0167 and M0173 showed the curve watch's one cost is the 2009 rebound it sits out, and that
resizing the book (M0173's dial) does not fix it. The fixed 730-day clock keeps the watch open for
two years after the last inverted day even when the curve has long since steepened. Here the same
watch opens on the same day (the first day T10Y < T13W after a closed spell) and the same book is
in cash while it is open, but it closes when the spread T10Y - T13W has stayed at or above a
threshold on every published day for ``confirm_days`` calendar days. It re-opens on the next
inverted day. The state is a pure scan of readings dated on or before the data date.

The two numbers are fixed in advance, from the textbook, not fitted: a 3-month confirmation (about
one quarter of trading days) and a threshold ladder of 0.5, 1.0 and 1.5 percentage points. The
ladder is three arms of the pre-registration, not a search; no arm is picked afterwards on its
own merit, and the controls are in the same run.

Variants:

    * ``NEVER``: the book never steps aside. The control with no opinion in it.
    * ``FIXED730``: M0038's clock on this allocator (M0173-EXP00's rule). The control that holds
      the habit but not the new close rule.
    * ``STEEP050``, ``STEEP100``, ``STEEP150``: the watch closes on the steepening rule.

Same book (M0076-X-M's picks, its own SPY-200 switch removed), same monthly re-pick and weekly
resize, same fractional Gotrade fees. Cash earns nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date, timedelta
from bisect import bisect_right
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import MarketSeries
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0038_yield_curve_watch_gate import (
    DIV_CURVE,
    DIV_OPEN,
    CurvePrepared,
    watch_open,
)
from seer_engine.lab.methods.m0076_dividend_raise_on_announcement import ANNOUNCED, AnnParams
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 24)

MODES = ("never", "fixed", "steep")


@dataclass(frozen=True, slots=True)
class WatchParams:
    """The dividend book in cash while the ``T10Y - T13W`` watch is open, closed by ``mode``."""

    mode: str
    threshold: float = 1.0  # percentage points of T10Y - T13W
    confirm_days: int = 90  # calendar days the spread must hold at or above threshold
    watch_days: int = 730  # the fixed clock (mode "fixed"), kept from M0038
    div: AnnParams = DIV_OPEN

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.threshold, bool) or not isinstance(self.threshold, (int, float)) or self.threshold < 0:
            raise ValueError(f"threshold must be a float >= 0, got {self.threshold!r}")
        for name in ("confirm_days", "watch_days"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise ValueError(f"{name} must be an int >= 1, got {v!r}")
        if not isinstance(self.div, AnnParams):
            raise TypeError(f"div must be AnnParams, got {type(self.div).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "threshold": str(self.threshold),
               "confirm_days": str(self.confirm_days), "watch_days": str(self.watch_days)}
        for k, v in self.div.as_dict().items():
            out[f"div.{k}"] = v
        return out


def _check(params: object) -> WatchParams:
    if not isinstance(params, WatchParams):
        raise TypeError(f"params must be WatchParams, got {type(params).__name__}")
    return params


def spread_rows(series: MarketSeries) -> tuple[tuple[date, float], ...]:
    """``T10Y - T13W`` on every date both were published, ascending."""
    shorts = dict(series.upto("T13W", date.max))
    return tuple((d, v - shorts[d]) for d, v in series.upto("T10Y", date.max) if d in shorts)


def watch_transitions(rows: tuple[tuple[date, float], ...], threshold: float,
                      confirm_days: int) -> tuple[tuple[date, ...], tuple[bool, ...]]:
    """When the steepening-closed watch changed state: (dates, state after each), ascending.

    Closed until the first inverted day (spread < 0). Open until the spread has been at or above
    ``threshold`` on every published day of an unbroken run lasting ``confirm_days`` calendar days.
    Any day under the threshold breaks the run; an inverted day while closed re-opens the watch.
    """
    dates: list[date] = []
    flags: list[bool] = []
    open_ = False
    run: date | None = None
    for d, s in rows:
        if not open_:
            if s < 0:
                open_, run = True, None
                dates.append(d)
                flags.append(True)
            continue
        if s >= threshold:
            run = run or d
            if d - run >= timedelta(days=confirm_days):
                open_, run = False, None
                dates.append(d)
                flags.append(False)
        else:
            run = None
    return tuple(dates), tuple(flags)


def steep_open(trans: tuple[tuple[date, ...], tuple[bool, ...]], data_date: date) -> bool:
    dates, flags = trans
    i = bisect_right(dates, data_date)
    return bool(i) and flags[i - 1]


class SteepPrepared:
    """The dividend host plus the dated spread; transitions per (threshold, confirm) cached on first use."""

    def __init__(self, base: CurvePrepared, rows: tuple[tuple[date, float], ...]) -> None:
        self.base = base
        self.rows = rows
        self._cache: dict[tuple[float, int], tuple[tuple[date, ...], tuple[bool, ...]]] = {}

    def transitions(self, threshold: float, confirm_days: int) -> tuple[tuple[date, ...], tuple[bool, ...]]:
        key = (threshold, confirm_days)
        if key not in self._cache:
            self._cache[key] = watch_transitions(self.rows, threshold, confirm_days)
        return self._cache[key]


class SteepAllocator:
    """M0038's dividend host, the watch closed by the curve steepening instead of the clock."""

    id = "M0336"
    market_fields = ("dividends", "series")

    def lookback(self, params: Any) -> int:
        return ANNOUNCED.lookback(_check(params).div)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return tuple(sorted({"SPY", *ANNOUNCED.symbols(_check(params).div)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return ANNOUNCED.holds(_check(params).div)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prep: SteepPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: WatchParams) -> tuple[Target, ...]:
        base = prep.base
        if not base.inverted:  # no series: target nothing (market-aware contract)
            return ()
        if p.mode == "fixed":
            open_ = watch_open(base.inverted.get("T13W", ()), data_date, p.watch_days)
        elif p.mode == "steep":
            open_ = steep_open(prep.transitions(p.threshold, p.confirm_days), data_date)
        else:
            open_ = False
        if open_:
            return ()
        return ANNOUNCED.targets_prepared(base.host, members, data_date, held, p.div)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no series, so no gate reading and no target."""
        return self._run(SteepPrepared(CurvePrepared(history, {}, None), ()), members, data_date,
                         held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> SteepPrepared:
        return SteepPrepared(DIV_CURVE.prepare(history), ())

    def prepare_market(self, market: Any) -> SteepPrepared:
        series = market.series
        rows = spread_rows(series) if isinstance(series, MarketSeries) and len(series) else ()
        return SteepPrepared(DIV_CURVE.prepare_market(market), rows)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SteepPrepared):
            raise TypeError(f"prepared must be SteepPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


STEEP = SteepAllocator()


def _v(suffix: str, params: WatchParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0336-{suffix}", family="M0336",
                     rules=MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE, allocator=STEEP,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0336",
    name="End the curve watch when the curve steepens, not on a fixed two-year clock",
    family="macro-regime-gate",
    source_kind="variation",
    source_ref="M0173",
    parent_id="M0173",
    hypothesis=(
        "M0038, M0167 and M0173 show the curve watch's only cost is the 2009 rebound it sits out, and "
        "resizing does not fix it. The inverted-curve signal was published in 1991 and 1996 and is "
        "public through the whole dev window, so any edge is not from being early to it. The fixed "
        "730-day clock keeps the watch open long after the curve has steepened again. Here the "
        "watch opens as in M0038 (first day the 10-year yield is under the 13-week bill) and closes "
        "once the 10y-13w spread has stayed at or above a threshold on every published day for 90 "
        "calendar days, re-opening on the next inverted day. The threshold ladder (0.5, 1.0, 1.5 "
        "points) and the 3-month confirmation are fixed in advance from convention and are three "
        "arms, not a search. Book: M0076-X-M's big-dividend-raise picks, its own SPY-200 switch "
        "removed, monthly re-pick, weekly resize, fractional at Gotrade's real fees. Variants: "
        "NEVER (never steps aside: the control with no opinion in it, which prices what acting on "
        "the warning costs), FIXED730 (M0038's clock on this allocator: the control with the habit "
        "but not the new close rule), STEEP050, STEEP100, STEEP150. Assumed: cash earns nothing; a "
        "reading needs both yields dated the same day; before the series starts the watch is "
        "closed; a gap-day (no yield print) neither extends nor breaks a run. Success: a positive "
        "2009-2015 lead over SPY without losing the 2000-02 and 2008 saves that FIXED730 holds, and "
        "a majority of walk-forward folds."
    ),
    expected_failure=(
        "The curve steepens fast out of an inversion because the 13-week bill falls (cuts), which "
        "happens in 2001 and 2007 while stocks are still falling, so the watch re-opens or never "
        "stays shut and closes early: the book returns to full size at the start of each bear "
        "market's first leg and takes it. The rule then gives up the saves without earning the 2009 "
        "rebound, and lands between NEVER and FIXED730 on every measure. With two warnings in "
        "twenty years the fold record is again about 2 of 4, and no arm is likely to clear the 0.90 "
        "luck bar at this N."
    ),
    candidates=(
        _v("NEVER", WatchParams("never"), "Control: the dividend book never stepping aside for the curve"),
        _v("FIXED730", WatchParams("fixed"), "Control: the watch closes on M0038's 730-day clock"),
        _v("STEEP050", WatchParams("steep", threshold=0.5),
           "The watch closes after 90 days with the curve at least 0.5 points steep"),
        _v("STEEP100", WatchParams("steep", threshold=1.0),
           "The watch closes after 90 days with the curve at least 1.0 points steep"),
        _v("STEEP150", WatchParams("steep", threshold=1.5),
           "The watch closes after 90 days with the curve at least 1.5 points steep"),
    ),
    seen_keys=(
        "concept:yield-curve-steepening-watch-close",
        "concept:yield-curve-gate",
        "concept:macro-regime-gate",
    ),
)
