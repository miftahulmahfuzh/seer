"""M0157 — Buy before the report, not after: big companies in the month they are expected to report.

Source: Frazzini & Lamont (2007), The earnings announcement premium and trading volume, NBER
w13090; Barber, De George, Lehavy & Trueman (2013), The earnings announcement premium around the
globe, JFE.
Idea: stocks earn a premium in the month they are *expected* to announce earnings, and Frazzini
and Lamont find it largest in the biggest firms, tied to the volume surge the report brings. The
lab's event-drift family (M0063 and kin) trades the drift *after* a report; this method buys
*before* the next one and ranks on a calendar, not on a return, so it should move apart from both
the momentum books and the event-drift books.

The store has no earnings calendar, so it is inferred point in time from each stock's own past
news days. A *news day* of stock s is a session t with

    * volume ratio  volume[t] / median(volume[t-vol_base .. t-1]) >= ``vol_min`` (M0063's measure);
    * open gap      |open[t] / close[t-1] - 1| >= ``gap_min`` (either direction: a bad report is
                    a report too).

News days closer than ``cluster`` sessions to the previous one are one event (its first day), so
a two-day reaction is not read as two reports. On data date d (bar index i), only news days in the
``window`` sessions ending at i are read, in both paths, so the prepared and unprepared paths agree
whatever history precedes the window. The expected next report p is then:

    * ``mode="rhythm"`` / ``"off"``: the last four events t1 < t2 < t3 < t4 must be spaced on a
      quarterly rhythm (each gap in [``q_lo``, ``q_hi``] sessions); then p = t1 + 252, the same
      quarter a year on (the paper's own "same month last year" rule, made regular). ``rhythm``
      qualifies a stock when i + 1 <= p <= i + ``horizon``, i.e. its report falls in the month the
      book is about to hold. ``off`` is the control: the same regular reporters whose p falls
      *outside* the coming month.
    * ``mode="yearago"``: Frazzini-Lamont's plain rule with no rhythm check: an event in
      [i + 1 - 252, i + horizon - 252], a report in the same month a year ago.

Inside F4's liquidity and membership screen (and behind its SPY-200 switch when ``inner.trend`` is
set: all cash while it is off) qualifiers are ranked by 20-day dollar volume, the biggest first
(the premium is a big-company one), and the ``inner.top`` biggest are held at 1/top each. ``park``
puts what the empty slots leave into SPY, so a light reporting month (March, June...) is mostly SPY.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, N20_NOTREND, TREND
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    FactorPrepared,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 16)

_MODES = ("rhythm", "off", "yearago")
YEAR = 252  # sessions in a year: the expected report is the same quarter a year on


@dataclass(frozen=True, slots=True)
class PremiumParams:
    """``inner`` is F4's screen, trend switch and book size; the rest defines the calendar."""

    inner: FactorParams
    mode: str = "rhythm"
    vol_min: Decimal = Decimal("3")  # a news day trades >= vol_min x its median volume
    gap_min: Decimal = Decimal("0.005")  # and opens at least this far from the prior close
    vol_base: int = 60  # sessions in the volume median, ending the session before
    cluster: int = 10  # a news day within this many sessions of the last is the same event
    q_lo: int = 50  # a quarterly gap between events is at least this many sessions
    q_hi: int = 76  # and at most this many
    horizon: int = 22  # the coming month: an expected report in i+1 .. i+horizon qualifies
    window: int = 360  # news days are read only in the window sessions ending at d
    park: bool = True  # empty slots hold SPY (while the trend switch, if any, is on)
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
        for name, low in (("vol_base", 5), ("cluster", 1), ("q_lo", 1), ("q_hi", 1),
                          ("horizon", 1), ("window", 2)):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < low:
                raise ValueError(f"{name} must be an int >= {low}, got {v!r}")
        if self.q_hi < self.q_lo:
            raise ValueError("q_hi must be >= q_lo")
        if self.window < YEAR + self.cluster:
            raise ValueError(f"window must cover a year of events, got {self.window}")
        if not isinstance(self.park, bool):
            raise TypeError(f"park must be a bool, got {type(self.park).__name__}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "mode": self.mode,
            "vol_min": str(self.vol_min),
            "gap_min": str(self.gap_min),
            "vol_base": str(self.vol_base),
            "cluster": str(self.cluster),
            "q_lo": str(self.q_lo),
            "q_hi": str(self.q_hi),
            "horizon": str(self.horizon),
            "window": str(self.window),
            "park": str(self.park).lower(),
            "market": self.market,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> PremiumParams:
    if not isinstance(params, PremiumParams):
        raise TypeError(f"params must be PremiumParams, got {type(params).__name__}")
    return params


def premium_lookback(params: PremiumParams) -> int:
    return max(factor_lookback(params.inner), params.window + params.vol_base + 1)


# --------------------------------------------------------------------------- the news days


def news_cols(h: History, vol_base: int) -> tuple[np.ndarray, np.ndarray]:
    """Per bar t: volume over its trailing median, and |open gap|. Entry t reads bars t-vol_base..t."""
    n = len(h)
    vratio = np.full(n, np.nan)
    gap = np.full(n, np.nan)
    if n < vol_base + 1:
        return vratio, gap
    vol = h.volume
    med = np.median(sliding_window_view(vol[:-1], vol_base), axis=1)  # med[k] = median(vol[k..k+vb-1])
    t = np.arange(vol_base, n)
    base = med[t - vol_base]
    with np.errstate(divide="ignore", invalid="ignore"):
        vratio[t] = np.where(base > 0, vol[t] / base, np.nan)
        gap[1:] = np.abs(h.open[1:] / h.close[:-1] - 1.0)
    vratio[~np.isfinite(vratio)] = np.nan
    gap[~np.isfinite(gap)] = np.nan
    return vratio, gap


def events(vratio: np.ndarray, gap: np.ndarray, i: int, p: PremiumParams) -> np.ndarray:
    """Bar indices of the events (first day of each news-day cluster) in the window ending at i."""
    lo = max(i - p.window + 1, p.vol_base)
    if i < lo:
        return np.empty(0, dtype=np.int64)
    v = vratio[lo : i + 1]
    g = gap[lo : i + 1]
    ok = np.isfinite(v) & np.isfinite(g) & (v >= float(p.vol_min)) & (g >= float(p.gap_min))
    idx = np.flatnonzero(ok) + lo
    if idx.size <= 1:
        return idx
    keep = np.concatenate(([True], np.diff(idx) > p.cluster))
    return idx[keep]


def qualifies(ev: np.ndarray, i: int, p: PremiumParams) -> bool:
    """Whether the stock's expected report falls (or, for ``off``, does not fall) in the coming month."""
    if p.mode == "yearago":
        return bool(np.any((ev >= i + 1 - YEAR) & (ev <= i + p.horizon - YEAR)))
    if ev.size < 4:
        return False
    last4 = ev[-4:]
    gaps = np.diff(last4)
    if not bool(np.all((gaps >= p.q_lo) & (gaps <= p.q_hi))):
        return False
    expected = int(last4[0]) + YEAR
    if not p.q_lo <= expected - int(last4[-1]) <= p.q_hi:
        return False
    inside = i + 1 <= expected <= i + p.horizon
    return inside if p.mode == "rhythm" else not inside


class PremiumPrepared:
    """The F4 columns plus each symbol's news columns, computed on first use and cached."""

    def __init__(self, history: Mapping[str, History], factor: FactorPrepared | None) -> None:
        self.history = history
        self.factor = factor
        self._cache: dict[tuple[str, int], tuple[np.ndarray, np.ndarray]] = {}

    def cols(self, symbol: str, vol_base: int) -> tuple[np.ndarray, np.ndarray] | None:
        key = (symbol, vol_base)
        if key not in self._cache:
            h = self.history.get(symbol)
            if h is None:
                return None
            self._cache[key] = news_cols(h, vol_base)
        return self._cache[key]


# --------------------------------------------------------------------------- the allocator


class EarningsMonthAllocator:
    """The biggest screened members expected to report in the coming month; the rest in SPY."""

    id = "M0157"

    def lookback(self, params: Any) -> int:
        return premium_lookback(_check(params))

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
                 p: PremiumParams) -> tuple[Target, ...]:
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
            if qualifies(events(cols[0], cols[1], i, p), i, p):
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


PREMIUM = EarningsMonthAllocator()

N40 = FactorParams(rank="momentum", top=40, trend=TREND)  # N20's screen with 40 slots


def _v(suffix: str, params: PremiumParams, rationale: str, rules=MONTHLY_HOLD_FRAC_GOTRADE) -> Candidate:
    return Candidate(id=f"M0157-{suffix}", family="M0157", rules=rules, allocator=PREMIUM,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0157",
    name="Buy before the report, not after: big companies in the month they are expected to "
         "announce earnings",
    family="stock-earnings-announcement-premium",
    source_kind="paper",
    source_ref="Frazzini & Lamont 2007, NBER w13090 'The earnings announcement premium and "
               "trading volume'; Barber, De George, Lehavy & Trueman 2013",
    parent_id=None,
    hypothesis=(
        "Frazzini and Lamont (1972-2004, published 2007) find stocks earn a premium in the month "
        "they are EXPECTED to report earnings, largest among the biggest firms, tied to the volume "
        "surge around the report. This is a pre-event premium, not the post-report drift the "
        "event-drift family trades, and it ranks on a calendar rather than a past return, so it "
        "should not move with the failed momentum books. The store has no report calendar, so the "
        "expected month is inferred point in time from each stock's own news days (volume at "
        "least 3x its 60-day median and an open gap of at least 0.5% either way, M0063's volume "
        "measure; days within 10 sessions merged into one event). A company whose last four "
        "events sit on a quarterly rhythm (each 50-76 sessions apart) is expected to report again "
        "252 sessions after the oldest of the four, the same quarter a year on. At each month "
        "start the book holds up to 20 of the biggest screened index members (F4's liquidity "
        "screen, ranked by 20-day dollar volume) whose expected report falls in the next 22 "
        "sessions, at 5% each, the rest parked in SPY, behind the standard SPY-200 switch, "
        "monthly in fractional shares at Gotrade's real fees on the owner's deposits. Variants: "
        "R20-TREND (the main rule), R20-ALWAYS (no switch: the picking alone), R40-TREND (40 "
        "slots at 2.5%), YA20-TREND (the paper's plain rule: a report in the same month a year "
        "ago, no rhythm check) and OFF20-TREND (control: the same regular reporters expected NOT "
        "to report in the coming month). Success: R20-TREND beats total-return SPY on dev with a "
        "worst fall under the screen, beats SPY in 2009-2015, and OFF20-TREND is clearly worse "
        "than R20-TREND. Since the paper came out in 2007, 2009-2015 is judged first."
    ),
    expected_failure=(
        "Barber et al.'s replication puts most of the premium in small firms, and this book holds "
        "only the biggest, where Frazzini-Lamont's own premium was perhaps half a point a month; "
        "with a quarter of the money in SPY in light months and Gotrade's fees on a full monthly "
        "turnover (a stock reports once a quarter, so most picks change every month), the excess "
        "may be a point a year or less, too small to clear the luck bar at N near 100. The "
        "inferred calendar mislabels some months (a takeover or index-add day breaks the rhythm, "
        "a report that moves a week across a month end flips the month). A month-long hold "
        "through a report adds single-name jump risk the window does not see. And the premium is "
        "published (2007), so if it shows at all it may sit before 2009 and fade. If OFF20 does "
        "as well as R20, the calendar is not what is paying."
    ),
    candidates=(
        _v("R20-TREND", PremiumParams(N20),
           "Up to 20 of the biggest members expected to report next month, 5% each, rest SPY"),
        _v("R20-ALWAYS", PremiumParams(N20_NOTREND),
           "No switch: the calendar picking alone on top of SPY, always invested"),
        _v("R40-TREND", PremiumParams(N40),
           "40 slots at 2.5%: more names, less single-report risk, same calendar"),
        _v("YA20-TREND", PremiumParams(N20, mode="yearago"),
           "The paper's plain rule: reported in the same month a year ago, no rhythm check"),
        _v("OFF20-TREND", PremiumParams(N20, mode="off"),
           "Control: the same regular reporters whose next report is NOT in the coming month"),
    ),
    seen_keys=(
        "concept:earnings-announcement-premium",
        "concept:expected-earnings-month",
        "concept:pre-announcement-premium",
        "nber:w13090",
    ),
)
