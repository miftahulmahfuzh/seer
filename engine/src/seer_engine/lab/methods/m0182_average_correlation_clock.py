"""M0182 — Average correlation as the market's own risk gauge: hold SPY, step down when the
typical pair of big stocks moves too closely together (or, the paper's sign, too loosely).

Source: Pollet & Wilson (2010), "Average correlation and stock market returns", Journal of
Financial Economics 96(3), 364-380. Parent: M0178, which used correlation to *pick* stocks.
Idea: market variance factors into average variance times average correlation. Pollet & Wilson
argue that average variance is mostly idiosyncratic noise and forecasts nothing, while the
average *correlation* among large stocks is the systematic half, and that it forecasts the
market's own excess return **positively** -- tightly-linked markets are risky markets, and risk
is paid for. Trading-room lore says exactly the opposite: a correlation spike means everything is
selling off together, so get out. Both cannot be right, and this lab has two correlation methods
(M0174, M0178) that already showed correlation fails as a *stock picker* after 2009. So the
question here is only whether it says anything useful about the *market*, in either direction,
and the method registers both signs rather than one.

**This is a paired experiment, not a candidate for the roster.** The book holds SPY and nothing
else, monthly, so it will trade a few dozen times in twenty years, far under design §1's 100-trade
floor. No variant can be eligible and none is meant to be. What the run buys is six curves that
differ in exactly one place each, against the lab's own SPY 200-day switch.

The reading, on data date d (column ``j`` of SPY's session calendar):

    * **The panel.** Of the point-in-time index members (S&P 500 union Nasdaq-100, SPY excluded)
      that have a close in *every* one of the last ``LOOKBACK`` sessions, the ``POOL`` with the
      highest 20-day mean close x volume on d. One fixed set of names serves every reading in
      this call, so the band below compares like with like instead of a reshuffling cross-section.
      Fewer than ``POOL`` qualifying names reads "no signal".
    * **The number.** Over a window of ``window`` sessions ending at column t, each name's daily
      returns are centred and scaled to unit length; the average pairwise correlation is then
      (||sum of the scaled rows||^2 - n) / (n(n-1)). That identity is Pollet & Wilson's own
      shortcut and costs O(n x window) instead of a full n x n correlation matrix. A name whose
      returns do not move at all over the window is dropped; under ``MIN_PANEL`` survivors reads
      "no signal".
    * **The band.** The same number is read again at columns j - 10k for k = 1..30, so today's
      reading sits inside 31 readings spanning the last 300 sessions (about fourteen months). The
      state is "high" when today is at or above the 80th percentile of those 31, and "low" when
      it is at or below the 20th. A band of its own recent history, rather than a fixed level,
      because average correlation drifts upward across the window as index funds grow, and a
      fixed threshold would simply become "is it after 2008".

``LOOKBACK`` is one constant for every variant, including the control, so all six start on the
same session and every paired difference is the rule and nothing else.

The variants, every threshold fixed here before any result:

    * ``HI-OFF``: the trading-room sign. All cash while correlation is high **and** SPY is under
      its 200-day average. It can only ever be in cash on a subset of the plain switch's cash
      months, so against ``SPY200`` it answers one question: do the high-correlation bear months
      carry the switch's whole value, and are the rest of its exits the whipsaw that M0084, M0097
      and M0205 all paid for?
    * ``HI-OFF-W126``: the same on a six-month correlation window instead of a quarter. Slower,
      fewer flips.
    * ``HI-HALF``: the same trigger, but half in SPY rather than all cash. If the full exit is too
      blunt an instrument, a half step should keep most of the protection for less of the lag.
    * ``HI-ALONE``: correlation only, no trend condition. The high-correlation reading has to earn
      its living with no switch behind it. This is the pure anti-Pollet-Wilson bet.
    * ``LO-OFF``: **the paper's own sign**, as a control and as a claim. If average correlation
      forecasts returns positively, the months to avoid are the *low*-correlation ones, so this
      sits out when correlation is low and SPY is under its 200-day average. It is cash on a
      subset of exactly the same switch months as ``HI-OFF``, just the complementary subset, so
      the two together say whether correlation sorts those months at all. If both beat the plain
      switch, the correlation reading did nothing and "be in cash less often" did everything.
    * ``SPY200``: the control. The lab's own SPY 200-day switch, nothing else, on this window.

Frame: SPY is the only thing ever held, fractional shares at Gotrade's real fees
(``monthly-hold-frac-gotrade``), on the owner's monthly deposits, read once a month. Cash earns
nothing in the simulator, which flatters SPY and makes every switched variant's cost an upper
bound.

Known leans, written down before the run. The store has no delisted companies, so the panel is
made of survivors; a correlation read over survivors misses the names that fell together hardest
and so reads calmer at every bottom than the real market did. The panel is also the *busiest*
hundred members, which is the half of the index least damaged by that gap and the half closest to
what SPY is actually weighted in -- that is deliberate, and it is M0178's lesson. Coverage rises
from about half the index in 1996 to three quarters in 2014, so the pool the busiest hundred are
drawn from grows across the window.

Pure: no clock, randomness, files or network; reads only columns at or before d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import EXCLUDED, FactorParams, trend_on

ADDED = date(2026, 10, 19)
BENCH = "SPY"  # the only instrument ever held, and the calendar every reading is laid on
POOL = 100  # the busiest members the correlation is read over, Pollet & Wilson's "large stocks"
MIN_PANEL = 80  # of those, how many must have moved at all over the window for a reading
DV_N = 20  # sessions of mean close x volume that decide "busiest"
BAND_STEP = 10  # sessions between the readings that make up the band
BAND_K = 31  # readings in the band: today plus 30 older ones, spanning 300 sessions
MAX_WINDOW = 126  # the longest correlation window any variant reads
LOOKBACK = BAND_STEP * (BAND_K - 1) + MAX_WINDOW + 1  # 427: one window for every variant
SMA_GATE = FactorParams(rank="momentum", trend=(BENCH, 200))  # the lab's own SPY switch

Rule = Literal["hi", "lo", "spy"]
_RULES: tuple[str, ...] = ("hi", "lo", "spy")


@dataclass(frozen=True, slots=True)
class CorrClockParams:
    """How the clock reads. ``band`` is the quantile of the trailing readings that marks the edge:
    a ``hi`` rule triggers at or above it, a ``lo`` rule at or below it."""

    rule: Rule = "hi"
    window: int = 63
    band: Decimal = Decimal("0.8")
    weight_off: Decimal = Decimal(0)  # SPY weight while the clock says step down
    with_trend: bool = True  # also require SPY under its 200-day average before stepping down

    def __post_init__(self) -> None:
        if not isinstance(self.rule, str) or self.rule not in _RULES:
            raise ValueError(f"rule must be one of {_RULES}, got {self.rule!r}")
        if isinstance(self.window, bool) or not isinstance(self.window, int):
            raise TypeError(f"window must be an int, got {type(self.window).__name__}")
        if not 20 <= self.window <= MAX_WINDOW:
            raise ValueError(f"window must be in [20, {MAX_WINDOW}], got {self.window}")
        if not isinstance(self.band, Decimal) or not self.band.is_finite():
            raise TypeError(f"band must be a finite Decimal, got {self.band!r}")
        if self.rule == "hi" and not Decimal("0.5") <= self.band <= Decimal("0.99"):
            raise ValueError(f"a hi band must be in [0.5, 0.99], got {self.band}")
        if self.rule == "lo" and not Decimal("0.01") <= self.band <= Decimal("0.5"):
            raise ValueError(f"a lo band must be in [0.01, 0.5], got {self.band}")
        if not isinstance(self.weight_off, Decimal) or not self.weight_off.is_finite():
            raise TypeError(f"weight_off must be a finite Decimal, got {self.weight_off!r}")
        if not Decimal(0) <= self.weight_off < Decimal(1):
            raise ValueError(f"weight_off must be in [0, 1), got {self.weight_off}")
        if not isinstance(self.with_trend, bool):
            raise TypeError(f"with_trend must be a bool, got {type(self.with_trend).__name__}")

    def as_dict(self) -> dict[str, str]:
        return {
            "rule": self.rule,
            "window": str(self.window),
            "band": format(self.band.normalize(), "f"),
            "weight_off": format(self.weight_off.normalize(), "f"),
            "with_trend": str(self.with_trend),
        }


def _check(params: object) -> CorrClockParams:
    if not isinstance(params, CorrClockParams):
        raise TypeError(f"params must be CorrClockParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True, eq=False)
class Panel:
    """Every symbol's closes on ``market``'s calendar, plus prefix sums of close x volume.

    ``dvsum[k, t]`` is the sum of the finite close x volume products in columns < t and
    ``dvcnt[k, t]`` their count, so the 20-day mean through column t is
    (dvsum[t + 1] - dvsum[t + 1 - 20]) / 20 when the count is 20. A prefix sum through t reads
    columns <= t only and adds in the same order however much history follows, so a reading on
    history cut at d is bit-identical to the same reading on the whole history.
    """

    row: Mapping[str, int]
    dates: np.ndarray  # datetime64[D]
    close: np.ndarray  # (n_symbols, n_dates), NaN where the symbol has no bar that session
    dvsum: np.ndarray  # (n_symbols, n_dates + 1)
    dvcnt: np.ndarray  # (n_symbols, n_dates + 1) int64


def build_panel(history: Mapping[str, History], market: str) -> Panel | None:
    """The close and dollar-volume grid on ``market``'s session calendar, or None without it."""
    m = history.get(market)
    if m is None or len(m) < 2:
        return None
    cal = m.dates
    ncal = len(cal)
    symbols = tuple(sorted(history))
    close = np.full((len(symbols), ncal), np.nan, dtype=np.float64)
    dv = np.zeros((len(symbols), ncal), dtype=np.float64)
    ok = np.zeros((len(symbols), ncal), dtype=bool)
    for k, symbol in enumerate(symbols):
        h = history[symbol]
        if len(h) == 0:
            continue
        pos = np.searchsorted(cal, h.dates)
        inside = pos < ncal
        safe = np.where(inside, pos, 0)
        on_cal = inside & (cal[safe] == h.dates)
        c = np.asarray(h.close, dtype=np.float64)
        v = np.asarray(h.volume, dtype=np.float64)
        good = on_cal & np.isfinite(c) & (c > 0.0) & np.isfinite(v) & (v >= 0.0)
        close[k, safe[good]] = c[good]
        dv[k, safe[good]] = c[good] * v[good]
        ok[k, safe[good]] = True
    dvsum = np.zeros((len(symbols), ncal + 1), dtype=np.float64)
    dvsum[:, 1:] = np.cumsum(dv, axis=1)
    dvcnt = np.zeros((len(symbols), ncal + 1), dtype=np.int64)
    dvcnt[:, 1:] = np.cumsum(ok, axis=1)
    for a in (close, dvsum, dvcnt):
        a.setflags(write=False)
    return Panel({s: k for k, s in enumerate(symbols)}, cal, close, dvsum, dvcnt)


def busiest_panel(panel: Panel, members: AbstractSet[str], j: int) -> np.ndarray | None:
    """Row indices of the ``POOL`` busiest members with a close in every one of the last
    ``LOOKBACK`` sessions through column ``j``, in row (symbol) order; None when too few."""
    lo = j + 1 - LOOKBACK
    if lo < 0:
        return None
    rows = sorted(panel.row[s] for s in members if s not in EXCLUDED and s in panel.row)
    if len(rows) < POOL:
        return None
    idx = np.asarray(rows, dtype=np.int64)
    idx = idx[np.isfinite(panel.close[idx, lo : j + 1]).all(axis=1)]
    if len(idx) < POOL:
        return None
    s = panel.dvsum[idx, j + 1] - panel.dvsum[idx, j + 1 - DV_N]
    n = panel.dvcnt[idx, j + 1] - panel.dvcnt[idx, j + 1 - DV_N]
    dollar = np.where(n == DV_N, s / DV_N, -1.0)
    order = np.lexsort((idx, -dollar))[:POOL]  # busiest first, ties by row (symbol) order
    if (dollar[order] <= 0.0).any():
        return None
    return np.sort(idx[order])


def average_correlation(panel: Panel, idx: np.ndarray, t: int, window: int) -> float | None:
    """The average pairwise correlation of ``idx``'s daily returns over the ``window`` sessions
    ending at column ``t``, through the scaled-sum identity; None when it cannot be read."""
    if t - window < 0:
        return None
    c = panel.close[idx, t - window : t + 1]
    if not np.isfinite(c).all():
        return None
    r = c[:, 1:] / c[:, :-1] - 1.0
    d = r - r.mean(axis=1, keepdims=True)
    length = np.sqrt((d * d).sum(axis=1))
    good = np.isfinite(length) & (length > 0.0)
    n = int(good.sum())
    if n < MIN_PANEL:
        return None
    z = d[good] / length[good, None]
    s = z.sum(axis=0)
    return float((float(s @ s) - n) / (n * (n - 1)))


def band_state(panel: Panel, members: AbstractSet[str], data_date: date, window: int,
               band: Decimal) -> tuple[bool, bool] | None:
    """(at or above the band, at or below it) for today's reading inside its own trailing 31,
    or None when any of the 31 cannot be read."""
    day = as_day(data_date)
    j = int(np.searchsorted(panel.dates, day, side="right")) - 1
    if j < 0 or panel.dates[j] != day:
        return None
    idx = busiest_panel(panel, members, j)
    if idx is None:
        return None
    vals: list[float] = []
    for k in range(BAND_K):
        v = average_correlation(panel, idx, j - BAND_STEP * k, window)
        if v is None:
            return None
        vals.append(v)
    now = vals[0]
    arr = np.asarray(vals, dtype=np.float64)
    q = float(band)
    return now >= float(np.quantile(arr, q)), now <= float(np.quantile(arr, q))


@dataclass(frozen=True, slots=True, eq=False)
class CorrClockPrepared:
    history: Mapping[str, History] = field(repr=False)
    panel: Panel | None = field(repr=False)


class AverageCorrelationClock:
    """100% SPY unless the clock says step down, and then ``weight_off`` of SPY (often nothing)."""

    id = "M0182"

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
        _check(params)
        return True  # the correlation is read over point-in-time index members

    def _weight(self, history: Mapping[str, History], panel: Panel | None,
                members: AbstractSet[str], data_date: date, p: CorrClockParams) -> Decimal:
        spy_on = trend_on(history, data_date, SMA_GATE)
        if p.rule == "spy":
            return Decimal(1) if spy_on else Decimal(0)
        state = None if panel is None else band_state(panel, members, data_date, p.window, p.band)
        if state is None:
            return Decimal(1)  # no reading: a data gap never sends the book to cash
        flag = state[0] if p.rule == "hi" else state[1]
        if flag and (not spy_on or not p.with_trend):
            return p.weight_off
        return Decimal(1)

    def _run(self, history: Mapping[str, History], panel: Panel | None, members: AbstractSet[str],
             data_date: date, p: CorrClockParams) -> tuple[Target, ...]:
        h = history.get(BENCH)
        if h is None or h.index_of(data_date) is None:  # no bar dated d: no new target
            return ()
        w = self._weight(history, panel, members, data_date, p)
        if w <= 0:
            return ()
        t = target_from_close(BENCH, last_close(h, data_date), w)
        return () if t is None else (t,)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not isinstance(held, frozenset):
            raise TypeError(f"held must be a frozenset, got {type(held).__name__}")
        panel = None if p.rule == "spy" else build_panel(history, BENCH)
        return self._run(history, panel, members, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> CorrClockPrepared:
        return CorrClockPrepared(history, build_panel(history, BENCH))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CorrClockPrepared):
            raise TypeError(f"prepared must be CorrClockPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not isinstance(held, frozenset):
            raise TypeError(f"held must be a frozenset, got {type(held).__name__}")
        panel = None if p.rule == "spy" else prepared.panel
        return self._run(prepared.history, panel, members, data_date, p)


CLOCK = AverageCorrelationClock()


def _v(suffix: str, params: CorrClockParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0182-{suffix}", family="M0182", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CLOCK, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0182",
    name=(
        "How tightly stocks move together, as a signal about the market: hold SPY, and read "
        "average stock-to-stock correlation as the market's own risk gauge"
    ),
    family="market-average-correlation",
    source_kind="paper",
    source_ref=(
        "Pollet & Wilson (2010), Average correlation and stock market returns, Journal of "
        "Financial Economics 96(3), 364-380; builds on M0174/M0178, which used correlation to "
        "pick stocks rather than to read the market"
    ),
    parent_id="M0178",
    hypothesis=(
        "Pollet & Wilson (2010) split market variance into average variance times average "
        "correlation and find that only the correlation half forecasts the market, with a "
        "POSITIVE sign: when big stocks move together, the market is risky and the risk is paid "
        "for. Trading-room lore says the opposite, that a correlation spike means get out. This "
        "lab's two correlation methods (M0174, M0178) showed correlation fails as a stock picker "
        "after 2009; this asks whether it reads the market instead, and registers BOTH signs so "
        "the answer cannot be a choice made after the fact. The book holds SPY alone, monthly, "
        "fractional shares at Gotrade's real fees on the owner's deposits. The reading is the "
        "average pairwise correlation of daily returns among the 100 busiest point-in-time index "
        "members with full history, compared against its own last 31 readings over 300 sessions "
        "(a band of its own recent history, because average correlation drifts up across the "
        "window as index funds grow). Variants, all fixed now: HI-OFF (cash when correlation is "
        "top-20% AND SPY is under its 200-day average); HI-OFF-W126 (the same on a six-month "
        "correlation window); HI-HALF (half in SPY instead of all cash); HI-ALONE (cash on the "
        "correlation reading alone, no trend condition -- the pure anti-paper bet); LO-OFF (the "
        "PAPER's sign: cash when correlation is bottom-20% and SPY is under its 200-day average); "
        "SPY200 (control: the lab's SPY 200-day switch alone, same window). HI-OFF and LO-OFF are "
        "each in cash on a complementary subset of SPY200's cash months, so together they say "
        "whether correlation sorts those months at all. SUCCESS: one sign beats SPY200 on funded "
        "return AND on 2009-2015 AND its mirror loses, so the correlation reading and not merely "
        "'be in cash less often' did the work. The trade count will be a few dozen, far under the "
        "100-trade floor, so NO variant can be eligible and none is meant to be: the paired "
        "differences are the whole result, and that is assumed and accepted before the run."
    ),
    expected_failure=(
        "The lab has priced four market clocks already -- the SPY 200-day switch (M0084), the "
        "typical-stock breadth filter (M0205), the cross-sectional dispersion clock (M0118) and "
        "the breadth regime switch (M0097) -- and every one of them cost money once the window "
        "reached 2009-2015, because sitting out the 2009 recovery costs more than dodging 2008 "
        "saves. The most likely result here is the same: HI-OFF trims a few of the plain switch's "
        "exits, which helps a little in 2010-2011 and hurts in 2008, and lands within noise of "
        "SPY200 either way. The second most likely result is the one that kills the idea cleanly: "
        "HI-OFF and LO-OFF both land near SPY200, which would mean correlation does not sort the "
        "switch's cash months at all and the reading is empty -- M0118's verdict, where the idea "
        "and its exact opposite both lost. HI-ALONE should be the worst variant, because a "
        "correlation band with no trend behind it will sit out strong, tightly-correlated bull "
        "runs (1997-1999, 2013) as readily as crashes. Survivorship leans the panel calm at every "
        "bottom (the names that fell together hardest are the ones missing from the store), so "
        "every high-correlation trigger fires later and weaker than it would on honest data. "
        "Profit factor and DSR are close to meaningless on a few dozen trades and no variant "
        "should clear the luck bar. Cash earns nothing in the simulator, so every switched "
        "variant's measured cost is an upper bound."
    ),
    candidates=(
        _v("HI-OFF", CorrClockParams("hi", 63, Decimal("0.8"), Decimal(0), True),
           "Cash when stocks move unusually closely together and SPY is under its 200-day average"),
        _v("HI-OFF-W126", CorrClockParams("hi", 126, Decimal("0.8"), Decimal(0), True),
           "The same, reading correlation over six months instead of a quarter"),
        _v("HI-HALF", CorrClockParams("hi", 63, Decimal("0.8"), Decimal("0.5"), True),
           "Half in SPY, not all cash, on the same high-correlation trigger"),
        _v("HI-ALONE", CorrClockParams("hi", 63, Decimal("0.8"), Decimal(0), False),
           "Cash on high correlation alone, with no trend condition behind it"),
        _v("LO-OFF", CorrClockParams("lo", 63, Decimal("0.2"), Decimal(0), True),
           "The paper's sign: cash when correlation is unusually low and SPY is under its average"),
        _v("SPY200", CorrClockParams("spy", 63, Decimal("0.8"), Decimal(0), True),
           "Control: the lab's own SPY 200-day switch on this window, no correlation reading"),
    ),
    seen_keys=(
        "concept:average-correlation-market-timing",
        "concept:correlation-regime-band",
        "concept:pollet-wilson-average-correlation",
    ),
)
