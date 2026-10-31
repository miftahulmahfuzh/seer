"""M0211 — Size-weighted breadth: hold SPY, step aside when the index's value sits mostly under its averages.

Source: variation of M0205 (the median-member breadth switch); Zweig (1986), Winning on Wall Street,
and the "percent of stocks above their 200-day average" breadth lore (published 1980s, so the dev
window sees it long after the crowd knew it).
Idea: M0205 read the *typical* member against its 200-day average and lost 18-36 points of extra
worst fall to SPY's own switch, because in 1999-2001 the giants and the typical stock moved apart.
SPY is size-weighted, so read breadth the way SPY is built: each member counts in proportion to
its company size, and the reading is the share of the index's total value that trades above its own
200-day average. Hold SPY while that share is at least one half, cash otherwise, read monthly.

Refinement of the reserved idea, written before any result: the idea row said price times shares
was not in the store and proposed 60-day dollar volume as the size weight. Shares outstanding
arrived on 2026-10-17 (``Market.market_value``: filed share count times the close as it printed,
splits handled), so the weight here is the real company size, not a trading-activity proxy. Dollar
volume on this store's back-adjusted closes would be scaled by later splits and would misweight
old dates. Where a member has no size (about 40% of member-days, mostly members with no bars) it is
left out of both numerator and denominator.

The reading, on data date d (SPY's session calendar, M0203's ``CloseGrid``):

    * every point-in-time member on d (S&P 500 union Nasdaq-100, SPY excluded) with a full SMA_L
      window of closes and a company size on d. Before 2014-04-03 the index lists Google under both
      GOOG and GOOGL with the identical whole-company share count; one name per identical count is
      kept so the company is weighed once;
    * ``reading = sum(size of members with close > SMA_L) / sum(size of all read members)``;
    * fewer than ``MIN_NAMES`` read members: "no signal", the switch stays on (SPY held), so a gap
      in the data never sends the book to cash.

Variants, every threshold fixed here:

    * ``SIZE200``: cash while the size-weighted share above the 200-day average is under 0.50.
    * ``SIZE100``: the same on the 100-day average, a faster reading aimed at the 2009 re-entry lag.
    * ``SIZE200-HYST``: asymmetric through ``held``: leave when the share falls under 0.40, return
      when it climbs to 0.50. Slow to leave, no slower to return than SIZE200.
    * ``SIZE-BOTH200``: cash only when SPY is under its own 200-day average AND the size-weighted
      share is under 0.50: two readings must agree.
    * ``COUNT200``: the share of members (not weighted by size) above their 200-day average, under
      0.50 -> cash. The control that isolates the weighting: the same breadth reading, same
      threshold, only the size weights removed.
    * ``SPY200``: the control. SPY's own 200-day switch (``f_factor.trend_on``) on this window.
      Every paired difference is therefore the breadth reading alone.

Frame: SPY is the only instrument ever held, at full weight, fractional shares at Gotrade's real
fees (``monthly-hold-frac-gotrade``), on the owner's monthly deposits. Off means no target: all
cash, no interest (not modelled; that flatters SPY). The always-invested SPY run the lab measures
beside every variant is the no-opinion arm for the cost of acting.

Known lean: the store has no delisted companies, so at each crash bottom the names that died are
missing and breadth reads healthier than the real index; exits come a little late, returns early.

Pure: reads only columns, share counts and closes dated at or before d.
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

ADDED = date(2026, 10, 31)
BENCH = "SPY"
MIN_NAMES = 100  # fewer read members than this reads "no signal" (switch stays on)
LOOKBACK = 200  # the slowest average any variant reads
SMA_GATE = FactorParams(rank="momentum", trend=(BENCH, 200))

Rule = Literal["size", "count", "both", "spy"]
_RULES: tuple[str, ...] = ("size", "count", "both", "spy")


@dataclass(frozen=True, slots=True)
class SizeBreadthParams:
    """How the switch is read. ``exit_below``/``enter_above`` apply to the share above the average."""

    rule: Rule = "size"
    sma: int = 200
    exit_below: Decimal = Decimal("0.5")  # held: leave when the share is under this
    enter_above: Decimal = Decimal("0.5")  # in cash: return when the share is at or over this

    def __post_init__(self) -> None:
        if not isinstance(self.rule, str) or self.rule not in _RULES:
            raise ValueError(f"rule must be one of {_RULES}, got {self.rule!r}")
        if not isinstance(self.sma, int) or isinstance(self.sma, bool) or not 20 <= self.sma <= LOOKBACK:
            raise ValueError(f"sma must be an int in [20, {LOOKBACK}], got {self.sma!r}")
        for name in ("exit_below", "enter_above"):
            v = getattr(self, name)
            if not isinstance(v, Decimal) or not v.is_finite() or not Decimal(0) < v < Decimal(1):
                raise ValueError(f"{name} must be a finite Decimal in (0, 1), got {v!r}")
        if self.exit_below > self.enter_above:
            raise ValueError("exit_below must not exceed enter_above (the band would re-enter at once)")

    def as_dict(self) -> dict[str, str]:
        return {"rule": self.rule, "sma": str(self.sma),
                "exit_below": format(self.exit_below.normalize(), "f"),
                "enter_above": format(self.enter_above.normalize(), "f")}


def _check(params: object) -> SizeBreadthParams:
    if not isinstance(params, SizeBreadthParams):
        raise TypeError(f"params must be SizeBreadthParams, got {type(params).__name__}")
    return params


@dataclass(eq=False)
class SizePrepared:
    history: Mapping[str, History] = field(repr=False)
    grid: CloseGrid | None = field(repr=False, default=None)
    market: Any = field(repr=False, default=None)
    cache: dict = field(repr=False, default_factory=dict)


def share_above(prepared: SizePrepared, members: AbstractSet[str], data_date: date,
                sma: int, weighted: bool) -> float | None:
    """Share of read members' size (or of their count) with close above SMA_sma; None on a thin cross-section."""
    grid, market = prepared.grid, prepared.market
    if grid is None or market is None:
        return None
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day or j + 1 - sma < 0:
        return None
    key = (data_date, sma, weighted, frozenset(members))
    if key in prepared.cache:
        return prepared.cache[key]
    names = sorted(s for s in members if s != BENCH and s in grid.row)
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)
    out: float | None = None
    if len(idx) >= MIN_NAMES:
        s = grid.csum[idx, j + 1] - grid.csum[idx, j + 1 - sma]
        n = grid.cnt[idx, j + 1] - grid.cnt[idx, j + 1 - sma]
        c = grid.close[idx, j]
        with np.errstate(divide="ignore", invalid="ignore"):
            r = c / (s / sma)
        ok = (n == sma) & np.isfinite(r)
        seen_counts: set[float] = set()
        above = tot = 0.0
        read = 0
        for k in np.flatnonzero(ok):
            sym = names[int(k)]
            sh = market.shares_on(sym, data_date)
            mv = market.market_value(sym, data_date)
            if sh is None or mv is None or not mv > 0.0:
                continue
            if sh in seen_counts:  # one company listed under two names with one whole-company count
                continue
            seen_counts.add(sh)
            w = mv if weighted else 1.0
            tot += w
            read += 1
            if r[k] > 1.0:
                above += w
        out = above / tot if read >= MIN_NAMES and tot > 0.0 else None
    prepared.cache[key] = out
    return out


class SizeBreadthAllocator:
    """100% SPY while the switch reads on, all cash while it reads off. Nothing else is held."""

    id = "M0211"
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
        _check(params)
        return True

    def _on(self, prepared: SizePrepared, members: AbstractSet[str], data_date: date,
            held: frozenset[str], p: SizeBreadthParams) -> bool:
        spy_on = trend_on(prepared.history, data_date, SMA_GATE)
        if p.rule == "spy":
            return spy_on
        m = share_above(prepared, members, data_date, p.sma, weighted=p.rule != "count")
        if m is None:
            breadth_on = True  # no reading: never let a data gap send the book to cash
        elif BENCH in held:
            breadth_on = m >= float(p.exit_below)
        else:
            breadth_on = m >= float(p.enter_above)
        if p.rule == "both":
            return spy_on or breadth_on
        return breadth_on

    def _run(self, prepared: SizePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SizeBreadthParams) -> tuple[Target, ...]:
        m = prepared.market
        if m is None or len(m.shares) == 0:
            return ()  # no panel: target nothing (market-aware contract)
        h = prepared.history.get(BENCH)
        if h is None or h.index_of(data_date) is None:
            return ()
        if not self._on(prepared, members, data_date, held, p):
            return ()
        t = target_from_close(BENCH, last_close(h, data_date), equal_weight(1))
        return () if t is None else (t,)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """History-only path: no share counts, so no targets (a market-aware allocator waits for its panel)."""
        _check(params)
        return ()

    def prepare(self, history: Mapping[str, History]) -> SizePrepared:
        return SizePrepared(history)

    def prepare_market(self, market: Any) -> SizePrepared:
        return SizePrepared(market.history, build_close_grid(market.history, BENCH), market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SizePrepared):
            raise TypeError(f"prepared must be SizePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


SIZEBREADTH = SizeBreadthAllocator()


def _v(suffix: str, params: SizeBreadthParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0211-{suffix}", family="M0211",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=SIZEBREADTH, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0211",
    name="Size-weighted breadth: time SPY by the share of the index's value above its 200-day average",
    family="market-trend-breadth-filter",
    source_kind="variation",
    source_ref=("variation of M0205 (median-member breadth switch); Zweig (1986), Winning on Wall "
                "Street, and percent-above-200-day breadth lore"),
    parent_id="M0205",
    hypothesis=(
        "Breadth timing is old (Zweig 1986), so the dev window sees it long after the crowd knew it "
        "and no fade argument is new. M0205 read the median member against its 200-day average and "
        "disagreed with SPY in 1999-2001 because the giants and the typical stock moved apart, which "
        "cost it 18-36 points of extra worst fall against SPY's own switch. Weight each point-in-time "
        "index member by its real company size (filed shares times the printed close, "
        "Market.market_value; the reserved idea proposed 60-day dollar volume because it believed "
        "shares were not in the store, but they are since 2026-10-17) and read the share of total "
        "size that trades above its own 200-day average. Hold SPY while it is at least 0.50, cash "
        "otherwise, read monthly, fractional shares at Gotrade's real fees on the owner's deposits. "
        "Members with no size are left out of numerator and denominator; fewer than 100 read "
        "members keeps SPY; one name per identical share count is kept (Google pre-2014-04-03). "
        "Variants, thresholds fixed now: SIZE200 (cash under 0.50); SIZE100 (same on the 100-day "
        "average, a faster reading); SIZE200-HYST (leave under 0.40, return at 0.50); SIZE-BOTH200 "
        "(cash only when SPY is under its 200-day average and the size share is under 0.50); "
        "COUNT200 (unweighted share of members above 200-day, under 0.50 -> cash: isolates the "
        "weighting); SPY200 (control: SPY's own 200-day switch, same window). SUCCESS: a size-weighted "
        "variant matches or beats SPY200 on worst fall AND beats it in 2009-2015 by returning to SPY "
        "earlier, beats SPY TR on the deposits, and beats SPY in a majority of walk-forward folds. "
        "Trades are few dozen, so eligibility on the 100-trade floor is not expected; the paired "
        "differences against SPY200 and COUNT200 are the result."
    ),
    expected_failure=(
        "A size-weighted breadth is close to SPY's own price trend, since SPY is itself the "
        "size-weighted index: SIZE200 reproduces SPY200 within a flip or two and adds nothing, and "
        "the 2009 re-entry lag stays (the 200-day average lags a V-shaped bottom whatever is "
        "weighed). Where it does differ it whipsaws in ordinary corrections (1998, 2010-2011, "
        "2015), selling low and buying back higher, which every lab market switch (M0084, M0113, "
        "M0097, M0205) paid for in 2009-2015. SIZE100 flips more and pays more in fees. The "
        "unweighted COUNT200 may do the same as the weighted ones, which would say the weighting "
        "was never the dial. About 40% of member-days have no size, so the reading is of the sized "
        "sub-index, and survivorship leaves the dead companies out of every crash bottom, so exits "
        "come late and returns early. Cash earns nothing in the simulator, so every switched "
        "variant's cost is an upper bound."
    ),
    candidates=(
        _v("SIZE200", SizeBreadthParams("size", 200),
           "Cash while under half of the index's value trades above its 200-day average"),
        _v("SIZE100", SizeBreadthParams("size", 100),
           "The same on the 100-day average, a faster reading for the re-entry lag"),
        _v("SIZE200-HYST", SizeBreadthParams("size", 200, Decimal("0.4"), Decimal("0.5")),
           "Leave when under 40% of value is above its average, return at 50%"),
        _v("SIZE-BOTH200", SizeBreadthParams("both", 200),
           "Cash only when SPY and the size-weighted share both read off"),
        _v("COUNT200", SizeBreadthParams("count", 200),
           "Control: the unweighted share of members above their 200-day average, no size weights"),
        _v("SPY200", SizeBreadthParams("spy", 200),
           "Control: SPY's own 200-day switch on this window, no breadth reading"),
    ),
    seen_keys=(
        "concept:breadth-size-weighted",
        "concept:breadth-timing-spy",
        "concept:sma200-trend-switch",
    ),
)
