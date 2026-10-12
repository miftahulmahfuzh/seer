"""M0118 — Pick stocks only when stocks are worth picking: the spread between members as the clock.

Source: Gorman, Sapra & Weigand, "The Cross-Sectional Dispersion of Stock Returns, Alpha and the
Information Ratio" (SSRN 1444868, 2010); "Stock-selection timing", J. Banking & Finance (2021).
Reserved by Sera 20261012-1842.

Every safety rule this lab has priced reads the market's own *level* -- SPY against its 200-day
average -- and M0084 measured that rule to death: it is essentially one 2008 trade, it cost 6 to
11 points a year after 2009, and reading it weekly instead of monthly costs another 4.7 points.
This prices a different clock, one that reads the *cross-section*. When the index's members move
apart -- a wide spread of one-month returns across them -- there is something for a picker to
pick; when they all move together, there is not, and the honest thing is to hold the market.

Priced on its own, the way M0084 priced the 200-day switch on its own, so the reading is the
clock and not a picker wearing a clock. Deliberately NOT ridden on a residual-momentum or
multi-factor-blend book: those are kin of four test-failed methods and the measurement would be
wasted on a book the hard gate would refuse anyway.

On data_date d:

    * the **reading set** is the ``universe`` point-in-time members (S&P 500 union Nasdaq-100,
      SPY excluded) with the highest median dollar volume (close x volume) over the last
      ``dv_n`` bars, among those carrying ``LOOKBACK_BARS`` bars of history through d;
    * each reading-set name's **return series** is close[i-k] / close[i-k-ret_n] - 1 for
      k = median_n-1 ... 0, i.e. its trailing ``ret_n``-bar total return (bars are split- and
      dividend-adjusted) as of each of the last ``median_n`` sessions;
    * **dispersion** on a session is the cross-sectional standard deviation of those returns
      across the reading set. That gives ``median_n`` readings ending with today's;
    * **mode**: today's dispersion against the ``quantile`` of those ``median_n`` readings.
      At or above it the members are moving apart, so hold the basket; below it they are moving
      together, so hold SPY. ``invert=True`` reads the same clock the other way (basket when the
      members move together), because a clock tested in one direction only is half a test.
      ``always=True`` is the control: the basket every month, no clock at all;
    * **basket targets**: ``slots`` equal weights, an evenly spaced sample of the reading set by
      dollar-volume rank (ranks 1, 1+k, 1+2k, ... with k = universe // slots), so the sample
      spans the giants to the hundredth name instead of being the giants alone.

Why 50 slots and not 20 (an assumption, written before the run): M0097 ran this exact basket
shape at 20 slots and earned +3.2% a year on the owner's deposits against SPY's +7.2%, while its
100-name arm earned +7.4%. Twenty evenly spaced names out of a hundred is a thin, high-turnover
sample, and a clock bolted to it would be measured against a book that was already losing for
reasons the clock cannot fix. Fifty 2% slots sit at double the simulator's 1%-of-equity top-up
band (``sim.rules.RESIZE_BAND``), so monthly deposits still reach held names rather than piling
up as cash, and the sample is wide enough to behave like "the typical big member".

Why every variant shares one ``LOOKBACK_BARS`` (315 bars + 1, the longest any variant needs):
M0084's lesson. If each variant started where its own lookback allowed, the slow-normalising arm
would be scored on a later, easier window and each paired difference would be part clock, part
calendar. One fixed lookback means every arm is scored on the same sessions and each difference
is the clock alone.

Known bias, written before the run: dispersion at past sessions is computed over **today's**
reading set, because the lab's point-in-time membership is available for d only. Names that
joined the index after a violent run are therefore in the historical cross-section before they
were index members, which inflates past dispersion slightly and biases the threshold upward --
i.e. toward the SPY side of the clock. The reading set is also aligned by bar count back from d
rather than by calendar date, so a member that missed a session shifts by one bar inside the
window; the dev store's big members have near-complete bars, so this is small, and it is the same
convention M0097 used.

Fractional shares at Gotrade's real fees, monthly (``monthly-hold-frac-gotrade``), funded on the
owner's monthly top-up. Pure: reads only bars dated <= d; ``held`` is not read at all.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 12)
BENCH = "SPY"
#: Bars of history every variant demands, whatever its own params: the longest sweep arm needs
#: median_n=252 readings of a ret_n=63 return (315 bars), so all six are scored on one window.
LOOKBACK_BARS = 316


@dataclass(frozen=True, slots=True)
class ClockParams:
    ret_n: int = 21  # bars in each member's return (about one month)
    median_n: int = 252  # trailing dispersion readings the threshold is taken over
    quantile: float = 0.5  # basket at or above this quantile of those readings
    universe: int = 100  # members in the reading set, by median dollar volume
    slots: int = 50  # basket names held (an evenly spaced sample of the reading set)
    dv_n: int = 60  # bars in the median dollar volume
    invert: bool = False  # read the clock the other way: basket when the members move together
    always: bool = False  # control: the basket every month, no clock

    def __post_init__(self) -> None:
        for name in ("ret_n", "median_n", "universe", "slots", "dv_n"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise ValueError(f"{name} must be an int >= 1, got {v!r}")
        if self.slots > self.universe:
            raise ValueError(f"slots ({self.slots}) must be <= universe ({self.universe})")
        if self.median_n < 2:
            raise ValueError(f"median_n must be >= 2, got {self.median_n}")
        if self.median_n + self.ret_n > LOOKBACK_BARS - 1:
            raise ValueError(
                f"median_n + ret_n ({self.median_n + self.ret_n}) exceeds the shared lookback "
                f"({LOOKBACK_BARS - 1}); raise LOOKBACK_BARS before a slower arm is added"
            )
        if isinstance(self.quantile, bool) or not isinstance(self.quantile, float):
            raise TypeError(f"quantile must be a float, got {type(self.quantile).__name__}")
        if not 0.0 <= self.quantile <= 1.0:
            raise ValueError(f"quantile must lie in [0, 1], got {self.quantile!r}")
        for name in ("invert", "always"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool, got {type(getattr(self, name)).__name__}")

    def as_dict(self) -> dict[str, str]:
        return {"ret_n": str(self.ret_n), "median_n": str(self.median_n),
                "quantile": repr(self.quantile), "universe": str(self.universe),
                "slots": str(self.slots), "dv_n": str(self.dv_n),
                "invert": str(self.invert), "always": str(self.always)}


def _check(params: object) -> ClockParams:
    if not isinstance(params, ClockParams):
        raise TypeError(f"params must be ClockParams, got {type(params).__name__}")
    return params


def reading_set(history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                p: ClockParams) -> list[tuple[str, int]]:
    """(symbol, row of d) for the ``universe`` most-traded members, most-traded first."""
    scored: list[tuple[float, str, int]] = []
    for s in sorted(members):
        if s == BENCH:
            continue
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < LOOKBACK_BARS - 1:
            continue
        dv = h.close[i - p.dv_n + 1 : i + 1] * h.volume[i - p.dv_n + 1 : i + 1]
        if not bool(np.all(np.isfinite(dv))):
            continue
        med = float(np.median(dv))
        if not med > 0.0:
            continue
        scored.append((-med, s, i))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [(s, i) for _, s, i in scored[: p.universe]]


def dispersion_series(history: Mapping[str, History], rows: list[tuple[str, int]],
                      p: ClockParams) -> np.ndarray | None:
    """The last ``median_n`` cross-sectional standard deviations, oldest first; None with none.

    Row k of the stacked matrix is one member's trailing ``ret_n``-bar return as of each of the
    last ``median_n`` sessions. Two members are the fewest a spread can be read across.
    """
    span = p.median_n + p.ret_n
    stack: list[np.ndarray] = []
    for s, i in rows:
        c = history[s].close[i - span + 1 : i + 1]
        if c.shape[0] != span:
            continue
        past, now = c[: -p.ret_n], c[p.ret_n :]
        if not bool(np.all(np.isfinite(c))) or not bool(np.all(past > 0.0)):
            continue
        stack.append(now / past - 1.0)
    if len(stack) < 2:
        return None
    return np.std(np.vstack(stack), axis=0, ddof=1)


def basket_mode(series: np.ndarray, p: ClockParams) -> bool:
    """True for the basket: today's spread at or above the ``quantile`` of the trailing ones."""
    wide = bool(float(series[-1]) >= float(np.quantile(series, p.quantile)))
    return (not wide) if p.invert else wide


class DispersionClockAllocator:
    """An equal-weight basket of big members while they move apart; SPY while they move together.

    Held symbols get no special treatment: a basket name that leaves the sample is sold, and a
    switch sells the whole side being left.
    """

    id = "M0118"

    def lookback(self, params: Any) -> int:
        _check(params)
        return LOOKBACK_BARS

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        rows = reading_set(history, members, data_date, p)
        if not rows:
            return ()  # no reading set: stand aside rather than guess
        if not p.always:
            series = dispersion_series(history, rows, p)
            if series is None:
                return ()
            if not basket_mode(series, p):
                t = target_from_close(BENCH, last_close(history.get(BENCH), data_date), equal_weight(1))
                return () if t is None else (t,)
        step = max(p.universe // p.slots, 1)
        chosen = [s for s, _ in rows[::step][: p.slots]]
        w = equal_weight(p.slots)
        out: list[Target] = []
        for s in chosen:
            t = target_from_close(s, last_close(history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


CLOCK = DispersionClockAllocator()


def _v(suffix: str, params: ClockParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0118-{suffix}", family="M0118", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CLOCK, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0118",
    name="Pick stocks only when stocks are worth picking: the spread between index members as the exposure clock",
    family="cross-sectional-dispersion-clock",
    source_kind="paper",
    source_ref=(
        "Gorman, Sapra & Weigand, The Cross-Sectional Dispersion of Stock Returns, Alpha and the "
        "Information Ratio (SSRN 1444868, 2010); Stock-selection timing, J. Banking & Finance (2021)"
    ),
    parent_id=None,
    hypothesis=(
        "Every safety rule this lab has priced reads the market's own level -- SPY against its "
        "200-day average -- and M0084 measured that rule to death: essentially one 2008 trade that "
        "four books share, 6 to 11 points a year of cost after 2009, and another 4.7 points for "
        "reading it weekly instead of monthly. This prices a different clock, one that reads the "
        "cross-section. Published 2010 and 2021, so the dev window sees the 2010 finding only part "
        "pre-crowd and should be expected to fade; the 2021 restatement is entirely after the dev "
        "window. Each month: take the 100 most-traded point-in-time S&P 500 / Nasdaq-100 members "
        "(60-day median dollar volume), measure the cross-sectional standard deviation of their "
        "trailing one-month total returns, and compare today's reading with the median of the last "
        "252 such readings. At or above it the members are moving apart, so there is something for "
        "a picker to pick: hold the basket -- 50 equal 2% slots, an evenly spaced sample of the 100 "
        "by dollar-volume rank. Below it they move together and nothing is worth picking: hold 100% "
        "SPY. Monthly, fractional shares at Gotrade's real fees (monthly-hold-frac-gotrade), funded "
        "on the owner's monthly top-up. Variants: D21-M252 (the book); D63-M252 (a three-month "
        "spread, slower and less noisy); D21-M126 (the same spread against a six-month normal, so "
        "the threshold adapts twice as fast and the clock may flip more often); D21-M252-Q70 (the basket only in the widest 30% of readings); "
        "D21-M252-INV (the identical clock read the other way, because a clock tested in one "
        "direction only is half a test); ALWAYS (control: the basket every month, no clock). All "
        "six share one 315-bar lookback, so every paired difference is the clock and not the "
        "calendar. SUCCESS IS A MEASUREMENT, NOT ELIGIBILITY: both sides of this clock are fully "
        "invested in equities, so none of the six can sidestep 2008 and none is expected to clear "
        "the 20% worst-fall bar or to be promoted. The question under test is whether any clocked "
        "arm beats the ALWAYS control by a point a year or more on the owner's deposits with no "
        "worse fall, and -- separately, because every gate in this lab earns its whole reputation "
        "in one autumn -- whether it is still ahead of the control over 2009-2015 alone."
    ),
    expected_failure=(
        "Cross-sectional dispersion is not a neutral statistic: it spikes in crises. The widest "
        "spreads in 1996-2015 are 2000-2002 and 2008, exactly when an equal-weight basket of "
        "members is punished hardest relative to SPY, so the plain reading (wide spread -> basket) "
        "may well buy the basket into both falls and look worse than the control on return AND on "
        "worst fall at once. If that happens the INV arm will look good for the same mechanical "
        "reason and will be a crisis-avoidance rule wearing a dispersion costume, not evidence that "
        "the paper's finding transfers -- the paper's claim is about the spread between good and "
        "bad PICKED portfolios, and an unpicked equal-weight basket may simply have no exposure to "
        "it. Dispersion is also strongly autocorrelated and slow, so against its own trailing "
        "median the clock will sit on one side for years at a time, give only a handful of flips "
        "over twenty years, and have far too few switch decisions for its result to be anything but "
        "a story about 2000 and 2008 -- M0084's exact failure. The Q70 arm will be in SPY most of "
        "the time and will converge on buy-and-hold SPY minus fees. Both sides are fully invested, "
        "so every variant almost certainly fails the 20% worst-fall bar (SPY itself fell about 55% "
        "over 1996-2015) and probably the luck bar too; the funded return, the gap to the control, "
        "and the 2009-2015 split are the only readable numbers. The historical cross-section is "
        "computed over today's member list, which leans the threshold slightly toward SPY. Not "
        "modelled: interest on cash, of which there is none here -- the book is always in SPY or in "
        "stocks, so unlike M0084 this method is not flattered by an unpaid cash yield."
    ),
    candidates=(
        _v("D21-M252", ClockParams(),
           "The book: one-month spread against its own one-year median; wide -> 50-name basket, narrow -> SPY"),
        _v("D63-M252", ClockParams(ret_n=63),
           "A three-month spread instead of a one-month one: slower, less noisy, fewer flips"),
        _v("D21-M126", ClockParams(median_n=126),
           "The same spread judged against a six-month normal, so the threshold adapts twice as fast"),
        _v("D21-M252-Q70", ClockParams(quantile=0.7),
           "A higher bar: the basket only in the widest 30% of readings, SPY the rest of the time"),
        _v("D21-M252-INV", ClockParams(invert=True),
           "The identical clock read the other way: basket while the members move together"),
        _v("ALWAYS", ClockParams(always=True),
           "Control: the 50-name basket every month, no clock, so each difference is the clock alone"),
    ),
    seen_keys=(
        "concept:cross-sectional-dispersion-clock",
        "url:https://www.ssrn.com/abstract=1444868",
    ),
)
