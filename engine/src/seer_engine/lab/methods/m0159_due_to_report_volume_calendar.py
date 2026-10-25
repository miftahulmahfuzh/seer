"""M0159 — Due to report, judged loosely: M0157's calendar rebuilt so it actually fires.

Source: Frazzini & Lamont (2007), The earnings announcement premium and trading volume, NBER
w13090. Parent: M0157, whose strict four-in-a-row rhythm qualified about 1.2 big companies a
month, so its main versions measured SPY behind the 200-day switch and not the premium.

A *news day* is now defined by volume alone: a session whose volume is at least ``vol_min`` times
the median of the ``vol_base`` sessions before it (M0063's measure, 2.5x here, no open-gap test),
days within ``cluster`` sessions merged into the first. A company is *due* on data date i (bar
index) when it had an event in the coming month's window one year earlier,
[i + 1 - 252, i + horizon - 252], AND one in the same window a quarter earlier,
[i + 1 - lag, i + horizon - lag]: a report that recurs both a year and a quarter back is a
calendar, a one-off takeover or index-add day is not. ``due`` holds up to ``inner.top`` of the
biggest due names by 20-day dollar volume; ``notdue`` is the control: names with at least
``min_events`` events in the window that are NOT due; ``any`` is the opinion-free arm: the same
biggest names with no calendar at all, which prices what the picking and the monthly churn cost
apart from the calendar's opinion. Empty slots park in SPY. Events are read only from the
``window`` sessions ending at d, in the prepared and unprepared paths alike, so they agree.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, N20_NOTREND, TREND
from seer_engine.lab.methods.m0157_earnings_month_premium import YEAR, PremiumPrepared, events, news_cols
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 25)

_MODES = ("due", "notdue", "any")


@dataclass(frozen=True, slots=True)
class DueParams:
    """``inner`` is F4's screen, trend switch and book size; the rest defines the calendar."""

    inner: FactorParams
    mode: str = "due"
    vol_min: Decimal = Decimal("2.5")
    gap_min: Decimal = Decimal("0")  # volume alone defines a news day
    vol_base: int = 60
    cluster: int = 10
    lag: int = 63  # the quarter-ago window
    horizon: int = 22
    window: int = 360
    min_events: int = 3  # the control's "regular news flow" floor
    park: bool = True
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in _MODES:
            raise ValueError(f"mode must be one of {_MODES}, got {self.mode!r}")
        for name in ("vol_min", "gap_min"):
            v = getattr(self, name)
            if not isinstance(v, Decimal) or not v.is_finite() or v < 0:
                raise ValueError(f"{name} must be a non-negative Decimal, got {v!r}")
        for name, low in (("vol_base", 5), ("cluster", 1), ("lag", 1), ("horizon", 1),
                          ("window", 2), ("min_events", 1)):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < low:
                raise ValueError(f"{name} must be an int >= {low}, got {v!r}")
        if self.window < YEAR + self.cluster:
            raise ValueError(f"window must cover a year of events, got {self.window}")
        if not isinstance(self.park, bool):
            raise TypeError(f"park must be a bool, got {type(self.park).__name__}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "mode": self.mode, "vol_min": str(self.vol_min), "gap_min": str(self.gap_min),
            "vol_base": str(self.vol_base), "cluster": str(self.cluster), "lag": str(self.lag),
            "horizon": str(self.horizon), "window": str(self.window),
            "min_events": str(self.min_events), "park": str(self.park).lower(),
            "market": self.market,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> DueParams:
    if not isinstance(params, DueParams):
        raise TypeError(f"params must be DueParams, got {type(params).__name__}")
    return params


def is_due(ev: np.ndarray, i: int, p: DueParams) -> bool:
    """An event in the coming month's window a year ago and another a quarter ago."""
    year = bool(np.any((ev >= i + 1 - YEAR) & (ev <= i + p.horizon - YEAR)))
    quarter = bool(np.any((ev >= i + 1 - p.lag) & (ev <= i + p.horizon - p.lag)))
    return year and quarter


def passes(ev: np.ndarray, i: int, p: DueParams) -> bool:
    if p.mode == "any":
        return True
    if p.mode == "due":
        return is_due(ev, i, p)
    return ev.size >= p.min_events and not is_due(ev, i, p)


class DueAllocator:
    """The biggest screened members due to report in the coming month; the rest in SPY."""

    id = "M0159"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(factor_lookback(p.inner), p.window + p.vol_base + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.market,) if p.park else ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _targets(self, prepared: PremiumPrepared, rows: list[Any], data_date: date,
                 p: DueParams) -> tuple[Target, ...]:
        chosen: list[tuple[float, str]] = []
        for r in rows:
            if r.symbol == p.market:
                continue
            h = prepared.history.get(r.symbol)
            cols = prepared.cols(r.symbol, p.vol_base)
            if h is None or cols is None:
                continue
            i = h.index_of(data_date)
            if i is None:
                continue
            if passes(events(cols[0], cols[1], i, p), i, p):  # type: ignore[arg-type]
                chosen.append((-r.dollar_volume, r.symbol))
        w = equal_weight(p.inner.top)
        out: list[Target] = []
        for _, s in sorted(chosen)[: p.inner.top]:
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        if p.park:
            rest = Decimal(1) - w * len(out)
            mh = prepared.history.get(p.market)
            if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
                t = target_from_close(p.market, last_close(mh, data_date), rest)
                if t is not None:
                    out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return self._targets(PremiumPrepared(history, None), rows, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> PremiumPrepared:
        return PremiumPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, PremiumPrepared) or prepared.factor is None:
            raise TypeError(f"prepared must be a prepared PremiumPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return self._targets(prepared, rows, data_date, p)


DUE = DueAllocator()

N40 = FactorParams(rank="momentum", top=40, trend=TREND)


def _v(suffix: str, params: DueParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0159-{suffix}", family="M0159", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=DUE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0159",
    name="Due to report, judged loosely: big companies with a heavy-trading day in the same month "
         "last year and one a quarter ago, against the same names not due",
    family="stock-earnings-announcement-premium",
    source_kind="variation",
    source_ref="Frazzini & Lamont 2007, NBER w13090; variation of M0157",
    parent_id="M0157",
    hypothesis=(
        "M0157's strict four-in-a-row rhythm qualified about 1.2 big companies a month, so its main "
        "versions measured SPY behind the 200-day switch rather than the earnings-month premium "
        "(Frazzini and Lamont, published 2007). Define a news day by volume alone (at least 2.5x "
        "the 60-day median, days within 10 sessions merged) and call a company due when it had a "
        "news day in the coming month's 22-session window one year earlier AND one in the window "
        "about 63 sessions earlier, which should give 20-40 genuine candidates a month and screen "
        "out one-off events. Hold up to 20 of the biggest by dollar volume, rest SPY, monthly, "
        "fractional at Gotrade's real fees, behind the SPY-200 switch; the same run carries the "
        "not-due control, an always-invested version and an opinion-free arm (the same biggest "
        "screened names with no calendar) that prices the book's habit apart from the calendar. "
        "Count qualifiers per month in the analysis before reading the returns. Judge 2009-2015 "
        "first; close the family if due and not-due do not separate there."
    ),
    expected_failure=(
        "The premium is published (2007) and Barber et al. put most of it in small firms, so among "
        "the biggest names it may be half a point a month and fade. Volume spikes also come from "
        "index adds, splits and takeovers, so 'due' may still mix in non-reports, and Gotrade's fees "
        "on a near-full monthly turnover can eat the lead. If the opinion-free arm does as well as "
        "the due book, the calendar is not what is paying."
    ),
    candidates=(
        _v("DUE20-TREND", DueParams(N20), "Up to 20 biggest due names, 5% each, rest SPY, switch on"),
        _v("DUE20-ALWAYS", DueParams(N20_NOTREND), "Same, no switch: the calendar picking alone"),
        _v("DUE40-TREND", DueParams(N40), "40 slots at 2.5%: less single-report risk"),
        _v("NOTDUE20-TREND", DueParams(N20, mode="notdue"),
           "Control: names with regular news days that are NOT due next month"),
        _v("ANY20-TREND", DueParams(N20, mode="any"),
           "Opinion-free arm: the biggest screened names with no calendar, same habit and churn"),
    ),
    seen_keys=(
        "concept:earnings-announcement-premium-volume-calendar",
        "concept:due-to-report-year-and-quarter-ago",
        "nber:w13090-variation",
    ),
)
