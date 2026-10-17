"""M0205 — The trend readings as a market crash filter: hold SPY, step aside when the typical stock is down-trend.

Source: variation of M0203 (the trend factor: moving averages over every horizon, used to rank
stocks); Zweig (1986), Winning on Wall Street, and decades of "percent of stocks above their
200-day average" breadth lore; Han, Zhou & Zhu (2016) for the moving-average readings themselves.
Idea: M0203 used each stock's price against its long moving averages to *rank* stocks, and an
equal-slot pick of index members leans small, so it fought SPY's big-company drift and lost after
2009. Used as *timing* instead, the same readings need not fight anything: hold SPY at full weight
and move to cash only when the typical index member is trading well under its own long average --
a broad, internal sign of a bear market that SPY's own 200-day line, dominated by a few giants,
may read late (or early) -- and buy SPY back when the typical member recovers.

The reading, on data date d (column ``j`` of SPY's session calendar, M0203's ``CloseGrid``):

    * for every point-in-time index member on d (S&P 500 union Nasdaq-100, SPY itself excluded)
      with all L closes in columns (j - L, j], the ratio close(j) / SMA_L(j);
    * the breadth reading is the **median** of those ratios over at least ``MIN_NAMES`` names. A
      thinner cross-section reads "no signal" and the switch stays on (SPY held), so a gap in the
      data can never be the thing that sends the book to cash.

The median is used rather than the share of names above their average because it carries depth as
well as count: "the typical stock is 5% under its 200-day line" is a stronger statement than "half
the stocks are a hair under it", and a fixed depth threshold is the only knob a variant sets.

The variants, every threshold fixed here before any result:

    * ``MED200``: cash while the median reading on the 200-day average is under 1.00.
    * ``MED400``: the same on the 400-day average (the slow end of M0203's horizons): fewer flips,
      later exits.
    * ``MED200-95``: cash only while the median stock is more than 5% under its 200-day average.
      Deeper trigger, meant to ignore 2010-2012-style corrections and catch only real bears.
    * ``MED200-HYST``: asymmetric, through ``held`` as M0113: while SPY is held, leave when the
      median falls under 0.97; while in cash, return when it climbs back over 1.00. Slow to leave,
      quick-ish to return.
    * ``BOTH200``: cash only while SPY's own close is under its 200-day average (``f_factor.trend_on``,
      the lab's switch, unchanged) **and** the median member is under its own. Two readings must
      agree, so false exits from either alone are skipped.
    * ``SPY200``: the control. SPY's own 200-day switch alone, the lab's standard frame (M0084's
      MONTHLY), re-run here on this method's window (1996 on, because the book reads members) so
      every paired difference is the breadth reading alone.

Frame: SPY is the only thing ever held, at full weight, fractional shares at Gotrade's real fees
(``monthly-hold-frac-gotrade``), on the owner's monthly deposits, read once a month. When the
switch reads off, no target: all cash, no interest (not modelled; that flatters SPY).

Known lean, written down before the run: the store has no delisted companies, so in every crash the
names that went on to die are missing from the median. The dead were the worst trenders, so the
measured breadth reads *healthier* than the real index did at the bottom; the switch exits a little
later and returns a little earlier than one fed full data would. Coverage also rises from about
half the index in 1996 to three quarters in 2014, so the median's sample changes over the window.

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
from seer_engine.lab.methods.m0203_trend_factor import CloseGrid, build_close_grid
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import FactorParams, trend_on

ADDED = date(2026, 10, 17)
BENCH = "SPY"  # the only instrument ever held, and the calendar the readings are laid on
MIN_NAMES = 100  # a median over fewer members reads "no signal" (switch stays on)
LOOKBACK = 400  # the slowest average any variant reads; one constant, one shared window
SMA_GATE = FactorParams(rank="momentum", trend=(BENCH, 200))  # the lab's own SPY switch

Rule = Literal["breadth", "both", "spy"]
_RULES: tuple[str, ...] = ("breadth", "both", "spy")


@dataclass(frozen=True, slots=True)
class BreadthParams:
    """How the switch is read. ``exit_below``/``enter_above`` apply to the median ratio."""

    rule: Rule = "breadth"
    sma: int = 200
    exit_below: Decimal = Decimal(1)  # held: leave when the median is under this
    enter_above: Decimal = Decimal(1)  # in cash: return when the median is at or over this

    def __post_init__(self) -> None:
        if not isinstance(self.rule, str) or self.rule not in _RULES:
            raise ValueError(f"rule must be one of {_RULES}, got {self.rule!r}")
        if not isinstance(self.sma, int) or isinstance(self.sma, bool) or not 20 <= self.sma <= LOOKBACK:
            raise ValueError(f"sma must be an int in [20, {LOOKBACK}], got {self.sma!r}")
        for name in ("exit_below", "enter_above"):
            v = getattr(self, name)
            if not isinstance(v, Decimal) or not v.is_finite() or not Decimal("0.5") < v < Decimal("1.5"):
                raise ValueError(f"{name} must be a finite Decimal in (0.5, 1.5), got {v!r}")
        if self.exit_below > self.enter_above:
            raise ValueError("exit_below must not exceed enter_above (the band would re-enter at once)")

    def as_dict(self) -> dict[str, str]:
        return {"rule": self.rule, "sma": str(self.sma),
                "exit_below": format(self.exit_below.normalize(), "f"),
                "enter_above": format(self.enter_above.normalize(), "f")}


def _check(params: object) -> BreadthParams:
    if not isinstance(params, BreadthParams):
        raise TypeError(f"params must be BreadthParams, got {type(params).__name__}")
    return params


def median_ratio(grid: CloseGrid, members: AbstractSet[str], data_date: date, sma: int) -> float | None:
    """Median over members of close / SMA_sma on ``data_date``; None when fewer than MIN_NAMES read."""
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day or j + 1 - sma < 0:
        return None
    idx = np.asarray(sorted(grid.row[s] for s in members if s != BENCH and s in grid.row), dtype=np.int64)
    if len(idx) < MIN_NAMES:
        return None
    s = grid.csum[idx, j + 1] - grid.csum[idx, j + 1 - sma]
    n = grid.cnt[idx, j + 1] - grid.cnt[idx, j + 1 - sma]
    c = grid.close[idx, j]
    with np.errstate(divide="ignore", invalid="ignore"):
        r = c / (s / sma)
    ok = (n == sma) & np.isfinite(r)
    if int(ok.sum()) < MIN_NAMES:
        return None
    return float(np.median(r[ok]))


@dataclass(frozen=True, slots=True, eq=False)
class BreadthPrepared:
    history: Mapping[str, History] = field(repr=False)
    grid: CloseGrid | None = field(repr=False)


class BreadthFilterAllocator:
    """100% SPY while the switch reads on, all cash while it reads off. Nothing else is held."""

    id = "M0205"

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
        return True  # the breadth reading is over point-in-time index members

    def _on(self, history: Mapping[str, History], grid: CloseGrid | None, members: AbstractSet[str],
            data_date: date, held: frozenset[str], p: BreadthParams) -> bool:
        spy_on = trend_on(history, data_date, SMA_GATE)
        if p.rule == "spy":
            return spy_on
        m = None if grid is None else median_ratio(grid, members, data_date, p.sma)
        if m is None:
            breadth_on = True  # no reading: never let a data gap be what sends the book to cash
        elif BENCH in held:
            breadth_on = m >= float(p.exit_below)
        else:
            breadth_on = m >= float(p.enter_above)
        if p.rule == "both":
            return spy_on or breadth_on  # off only when both readings say off
        return breadth_on

    def _run(self, history: Mapping[str, History], grid: CloseGrid | None, members: AbstractSet[str],
             data_date: date, held: frozenset[str], p: BreadthParams) -> tuple[Target, ...]:
        h = history.get(BENCH)
        if h is None or h.index_of(data_date) is None:  # no bar dated d: no new target
            return ()
        if not self._on(history, grid, members, data_date, held, p):
            return ()
        t = target_from_close(BENCH, last_close(h, data_date), equal_weight(1))
        return () if t is None else (t,)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        grid = None if p.rule == "spy" else build_close_grid(history, BENCH)
        return self._run(history, grid, members, data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> BreadthPrepared:
        return BreadthPrepared(history, build_close_grid(history, BENCH))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, BreadthPrepared):
            raise TypeError(f"prepared must be BreadthPrepared, got {type(prepared).__name__}")
        return self._run(prepared.history, prepared.grid, members, data_date, held, _check(params))


BREADTH = BreadthFilterAllocator()


def _v(suffix: str, params: BreadthParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0205-{suffix}", family="M0205", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BREADTH, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0205",
    name="The trend readings as a market crash filter: hold SPY, step aside when the average stock sits far below its long averages",
    family="market-trend-breadth-filter",
    source_kind="variation",
    source_ref=(
        "variation of M0203 (the trend factor's moving-average readings, used to rank stocks); "
        "Zweig (1986), Winning on Wall Street, and percent-above-200-day breadth lore; "
        "Han, Zhou & Zhu (2016), A trend factor, JFE 122(2)"
    ),
    parent_id="M0203",
    hypothesis=(
        "Breadth timing is old (Zweig 1986; 'percent of stocks above their 200-day average' is a "
        "chart-room staple), so no fade argument is new here and the dev window sees it long after "
        "the crowd knew it. M0203 showed the moving-average readings, used to RANK stocks, rebuild "
        "momentum and lose to SPY after 2009 because an equal-weight pick of index members leans "
        "small. Used as TIMING instead they need not fight SPY's big-company drift: hold SPY at full "
        "weight, monthly, fractional shares at Gotrade's real fees on the owner's deposits, and go "
        "to cash only while the MEDIAN point-in-time index member trades under its own long moving "
        "average (close / SMA, median over at least 100 members with full history; a thinner "
        "cross-section keeps SPY). Variants, all thresholds fixed now: MED200 (median close/SMA200 "
        "under 1.00 -> cash); MED400 (the same on the 400-day average); MED200-95 (cash only below "
        "0.95, deeper trigger to skip corrections); MED200-HYST (leave below 0.97 while held, return "
        "at 1.00 while in cash); BOTH200 (cash only when SPY is under its own 200-day average AND "
        "the median member is under its own); SPY200 (control: the lab's SPY 200-day switch alone, "
        "re-run on this window from 1996 so the paired difference is the breadth reading). The "
        "comparison point from the lab: M0084-MONTHLY (SPY's 200-day switch, from 1994) earned +9.1% "
        "a year on deposits vs +7.7% for SPY with an 18.9% worst fall, but lost 6 points a year to "
        "SPY in 2009-2015 because it sat out the 2009 recovery. SUCCESS: a breadth variant beats "
        "the SPY200 control on funded return AND on 2009-2015, beats SPY TR on the deposits, keeps "
        "the worst fall well under SPY's, and wins a majority of walk-forward folds. The trade count "
        "will be far under 100, so eligibility is not expected; the paired differences are the "
        "result."
    ),
    expected_failure=(
        "Whipsaw: the median stock dips under its 200-day average in ordinary corrections (1998, "
        "2010, 2011, 2015) as well as in bears, and each false exit sells low and buys back higher, "
        "which the lab's other market switches (M0084, M0113, M0097) all found costs more than the "
        "2008 dodge saves once the window reaches 2009-2015. The breadth reading may also simply be "
        "SPY's switch in disguise -- the median member and SPY move together in every real bear -- "
        "so MED200 and SPY200 may differ by only a few flips, and BOTH200 by fewer. The 400-day "
        "reading is slow enough to exit 2008 late and return 2009 late, the worst of both. "
        "Survivorship leans the breadth reading healthy at every bottom (the dead companies are "
        "missing), so exits come late and returns early compared with true data. Trades will "
        "number a few dozen, so profit factor and DSR are close to meaningless and no variant "
        "should clear the luck bar or the 100-trade floor. Cash earns nothing in the simulator, "
        "so every switched variant's cost is an upper bound."
    ),
    candidates=(
        _v("MED200", BreadthParams("breadth", 200),
           "Cash while the median index member is under its 200-day average"),
        _v("MED400", BreadthParams("breadth", 400),
           "Cash while the median index member is under its 400-day average"),
        _v("MED200-95", BreadthParams("breadth", 200, Decimal("0.95"), Decimal("0.95")),
           "Cash only while the median member is more than 5% under its 200-day average"),
        _v("MED200-HYST", BreadthParams("breadth", 200, Decimal("0.97"), Decimal(1)),
           "Leave when the median member is 3% under its 200-day line, return when back on it"),
        _v("BOTH200", BreadthParams("both", 200),
           "Cash only when SPY and the median member are both under their 200-day averages"),
        _v("SPY200", BreadthParams("spy", 200),
           "Control: the lab's own SPY 200-day switch on this window, no breadth reading"),
    ),
    seen_keys=(
        "concept:breadth-median-above-sma",
        "concept:breadth-timing-spy",
        "concept:sma200-trend-switch",
    ),
)
