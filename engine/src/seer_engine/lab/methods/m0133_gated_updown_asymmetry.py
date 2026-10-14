"""M0133 — Lean into the swing, then step out of it: the most-asymmetric companies behind the
market-trend switch.

Source: a variation of M0110, which split "how far did this company fall" into a market half and
an own-account half and found that shelter *can* be bought by selection but stops half-way --
SPY fell 55.2% over the dev window, the best-sheltered book 39.9%, and every point of shelter
cost 3 to 6 points a year of lost recovery after 2009.

The one arm of M0110 that pointed the other way was ``DP20-UP``: rank each F4-screened member on
**upside participation minus downside participation** -- over the past 252 sessions, the stock's
summed return on SPY's up days divided by SPY's own, less the same quantity computed on SPY's
down days -- and hold the 20 highest. It earned +10.3% a year on the owner's deposits against
SPY TR's +7.2%, and it beat SPY by 7.7 points a year over 2009-2015. That second number is why
this method exists. Across the 83 lab methods carrying a written verdict, roughly a quarter beat
SPY over the whole dev window and then lost to it after 2009, and every other dev-window edge
this lab holds was earned *before* 2009. This one is the only recorded edge that points the
right way in time, and 2009-2015 is the best-covered, most present-day stretch the dev window
has.

Its single defect is the size of the fall: 74.0% peak to trough, with 2008 at -57.6%, against a
50% dev screen and a 25% real-money bar. That defect is precisely the one the lab has already
measured a fix for. The SPY 200-day trend gate helped 22 of 22 variants over the whole dev
window, and every gate-off arm was worse on return **and** on drawdown at the same time -- the
gate is not a drag to be removed, it is a free improvement on both axes. So this method re-runs
M0110's asymmetry rank with the gate on, and keeps a paired gate-off arm so the gate's whole
contribution stays measurable rather than assumed.

The ranking math is M0110's, reused rather than re-derived: ``_participation`` is imported from
that module so a share of these numbers and a share of M0110's come out of the same code, and a
difference between the two methods can only be the gate, the book size or the eligibility filter.
The screen, the weighting and the pricing are F4's, inherited through ``FactorParams`` with
``trend=None`` in every variant -- the gate here is this allocator's own, never F4's, so that
member eligibility is bit-identical whether the gate is on or off and the gate-on/gate-off
difference is the gate alone.

The five arms:

* ``G20`` -- the asymmetry rank, 20 equal slots, gated on SPY's 200-day average. The headline,
  and the direct paired comparison against the recorded ``M0110-DP20-UP`` (same rank, same
  screen, same fees, same slots, gate off).
* ``G40`` -- the same gated book over 40 slots. A 74% fall is partly single-name risk; 40 names
  at 2.5% each halve it without touching the signal.
* ``N40`` -- 40 slots, **gate off**. The paired control, which must fall harder than ``G40``.
  With ``M0110-DP20-UP`` already recorded, the four cells of (20, 40) x (gate on, gate off) are
  then complete, and the gate's effect can be read at both book sizes instead of one.
* ``G20-UP1`` -- gated, 20 slots, but a name is eligible only when its **upside participation is
  strictly above 1.0**. The spread rewards a name for both halves of the asymmetry, and it cannot
  by itself tell "outruns the market on the way up and gives less back on the way down" from
  "simply does less in both directions" -- the second is cash with extra fees and is exactly what
  M0110's shelter arms bought. This filter keeps only names that genuinely outrun the market on
  its good days, then ranks those on the spread.
* ``G20-UP63`` -- gated, 20 slots, with an **asymmetric switch**. The exit is unchanged (out when
  SPY closes under its 200-day average); the way back in is M0113's measured-better trigger, back
  when SPY's last 63 sessions have actually returned positive. M0113 priced the two buy-backs
  against each other on SPY alone over the same window: the price cross earned +9.1% a year funded
  at an 18.9% worst fall, the positive-quarter trigger +9.7% at 20.7%. This arm exists because the
  gate's known cost is the recovery -- it sells late and buys back later -- and the recovery is
  what this ranking is built to capture.

Assumptions, written before the run:

- The reserved idea listed a third arm as "the gated book at 40 names with the same slot size".
  Forty names at a 20-name slot size is 200% of the account, which is leverage, needs owner
  inputs and could never be eligible; read the other way it is simply ``G40``. The slot goes to
  ``G20-UP63`` instead, which attacks the failure this method's own hypothesis names -- that the
  gate eats the recovery the ranking exists to capture -- with a trigger the lab has already
  measured rather than a dial invented after the fact.
- The gate is this allocator's, not F4's, and ``inner.trend`` is ``None`` in every variant. F4's
  ``factor_rows`` never applies the trend gate anyway (the FACTOR allocator applies it separately),
  so setting it there would have changed nothing; keeping it ``None`` makes that explicit and
  keeps the screened universe identical across the gated and ungated arms.
- "Am I invested" for the asymmetric switch is ``held`` being non-empty, which is what M0113 used
  on SPY. When the gate is off the book targets nothing and the engine sells everything, so the
  next check sees an empty ``held`` and applies the entry rule. A deposit cannot move this: a
  deposit changes cash, not whether anything is held.
- ``G20-UP1`` may hold fewer than 20 names when fewer than 20 screened members outrun the market
  on its up days, and the remainder simply sits in cash. That is the honest reading of the filter
  and the arm is partly a measurement of how often it binds; the recorded exposure says how much
  of the result is the filter and how much is cash.
- Participation is computed on plain total-price returns over split- and dividend-adjusted bars,
  one session of SPY's own calendar at a time, with M0110's coverage floors unchanged (80% of the
  window's qualifying sessions and at least 20 of them). A name that cannot clear them is not held.
- ``inner.rank`` stays ``"momentum"`` so the recorded screen reads identically to M0110's and to
  every other F4-framed method; this allocator re-ranks every eligible row itself and the momentum
  column only gates eligibility through its finiteness.
- Reads only bars dated <= ``data_date``. Pure: no clock, no I/O, no randomness.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20_NOTREND, ReturnGrid, build_grid
from seer_engine.lab.methods.m0110_downside_participation import (
    MIN_DAYS,
    CapturePrepared,
    _participation,  # M0110's participation math, imported so both methods share one implementation
    targets_from_scores,
)
from seer_engine.lab.methods.m0113_trend_switch_reentry import ReentryParams, entry_on
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 14)

SMA_N = 200  # the exit average, F4's and M0113's, frozen for every gated variant
UP_N = 63  # the asymmetric buy-back's window: one quarter of sessions
#: F4's own gate value, so "out" here means exactly what it means everywhere else in the lab.
EXIT_GATE = FactorParams(rank="momentum", trend=("SPY", SMA_N))
#: M0113's measured-better buy-back, reused unchanged.
UP_ENTRY = ReentryParams("up", UP_N)

Gate = Literal["none", "sma200", "sma200-up63"]
_GATES: tuple[str, ...] = ("none", "sma200", "sma200-up63")


@dataclass(frozen=True, slots=True)
class AsymParams:
    """``inner`` is F4's screen, book size and weighting; the rest is the rank, the filter and the gate."""

    inner: FactorParams
    window: int = 252  # daily returns in the participation estimate (252 = one year)
    market: str = "SPY"
    gate: Gate = "sma200"
    min_up: float | None = None  # hold only names whose upside participation exceeds this

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.inner.trend is not None:
            raise ValueError(f"inner.trend must be None: the gate is this method's, got {self.inner.trend!r}")
        if isinstance(self.window, bool) or not isinstance(self.window, int):
            raise TypeError(f"window must be an int, got {type(self.window).__name__}")
        if self.window < 60:
            raise ValueError(f"window must be >= 60, got {self.window}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")
        if not isinstance(self.gate, str) or self.gate not in _GATES:
            raise ValueError(f"gate must be one of {_GATES}, got {self.gate!r}")
        if self.min_up is not None:
            if isinstance(self.min_up, bool) or not isinstance(self.min_up, (int, float)):
                raise TypeError(f"min_up must be None or a float, got {type(self.min_up).__name__}")
            value = float(self.min_up)
            if not np.isfinite(value):
                raise ValueError(f"min_up must be finite, got {value!r}")
            object.__setattr__(self, "min_up", value)

    def as_dict(self) -> dict[str, str]:
        out = {
            "window": str(self.window),
            "market": self.market,
            "gate": self.gate,
            "min_up": "none" if self.min_up is None else repr(self.min_up),
        }
        for key, v in self.inner.as_dict().items():
            out[f"inner.{key}"] = v
        return out


def _check(params: object) -> AsymParams:
    if not isinstance(params, AsymParams):
        raise TypeError(f"params must be AsymParams, got {type(params).__name__}")
    return params


def asym_scores(
    grid: ReturnGrid, symbols: list[str], data_date: date, params: AsymParams
) -> dict[str, float]:
    """Each symbol's rank key on ``data_date``, **lowest first** (absent = not scorable or filtered).

    The key is ``-(up - down)``, so the most asymmetric name sorts first. ``up`` and ``down`` are
    M0110's participation ratios over the window's up and down market sessions. When ``min_up`` is
    set, a name whose upside participation does not strictly exceed it is dropped before ranking.
    Reads only calendar columns at or before ``data_date``.
    """
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day:
        return {}
    w0 = j - params.window + 1
    if w0 < 1:  # column 0 of the grid can hold no return
        return {}
    mrow = grid.row.get(params.market)
    if mrow is None:
        return {}
    names = [s for s in symbols if s in grid.row and s not in EXCLUDED]
    if not names:
        return {}
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)
    m = grid.rets[mrow, w0 : j + 1]
    r = grid.rets[idx, w0 : j + 1]
    finite = np.isfinite(m)
    down = finite & (m < 0.0)
    up = finite & (m > 0.0)
    n_down, n_up = int(down.sum()), int(up.sum())
    if n_down < MIN_DAYS or n_up < MIN_DAYS:
        return {}
    dn, live_dn = _participation(r, m, down, n_down)
    upc, live_up = _participation(r, m, up, n_up)
    score = -(upc - dn)
    good = live_dn & live_up & np.isfinite(score)
    if params.min_up is not None:
        good = good & (upc > params.min_up)
    return {names[k]: float(score[k]) for k in (int(v) for v in np.flatnonzero(good))}


class GatedAsymmetryAllocator:
    """F4's screen and book, ranked on the up/down participation spread, behind a market switch.

    The gate is read on every check. ``"none"`` is always invested; ``"sma200"`` holds only while
    SPY closes strictly above its 200-day average; ``"sma200-up63"`` keeps that exit but comes back
    only when SPY's last 63 sessions have returned positive, so the exit and the entry differ.
    Held symbols get no special treatment inside the book -- a name that falls out of the chosen
    set is signal-exited by the book engine -- but ``held`` being non-empty is what tells the
    asymmetric switch that it is currently invested.
    """

    id = "M0133"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(factor_lookback(p.inner), p.window + 1, SMA_N, UP_N + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return tuple(sorted({p.market, EXIT_GATE.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _invested(self, history: Mapping[str, History], data_date: date, held: frozenset[str],
                  p: AsymParams) -> bool:
        """Should the book be invested after this check? The exit rule when in, the entry when out."""
        if p.gate == "none":
            return True
        if p.gate == "sma200" or held:
            return trend_on(history, data_date, EXIT_GATE)
        return entry_on(history.get(p.market), data_date, UP_ENTRY)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        rows = factor_rows(history, members, data_date, p.inner)
        if not rows or not self._invested(history, data_date, held, p):
            return ()
        grid = build_grid(history, p.market)
        if grid is None:
            return ()
        return targets_from_scores(rows, asym_scores(grid, [r.symbol for r in rows], data_date, p), p)

    def prepare(self, history: Mapping[str, History]) -> CapturePrepared:
        return CapturePrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CapturePrepared):
            raise TypeError(f"prepared must be CapturePrepared, got {type(prepared).__name__}")
        p = _check(params)
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        if not rows or not self._invested(prepared.history, data_date, held, p):
            return ()
        grid = prepared.grid(p.market)
        if grid is None:
            return ()
        return targets_from_scores(rows, asym_scores(grid, [r.symbol for r in rows], data_date, p), p)


ASYM = GatedAsymmetryAllocator()

N20 = N20_NOTREND  # F4's screen, 20 equal slots, no F4 gate (this method brings its own)
N40 = replace(N20_NOTREND, top=40)


def _v(suffix: str, params: AsymParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0133-{suffix}", family="M0133", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=ASYM, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0133",
    name=("Lean into the swing, then step out of it: the most-asymmetric companies behind the "
          "market-trend switch"),
    family="stock-updown-asymmetry",
    source_kind="variation",
    source_ref=(
        "variation of M0110 (the up/down participation spread, ungated), putting the lab's "
        "200-day market switch in front of it; the buy-back of the fifth arm is M0113-UP63"
    ),
    parent_id="M0110",
    hypothesis=(
        "M0110-DP20-UP was a side effect of a shelter run and was the only thing in it that "
        "looked like an edge: ranking F4-screened members on upside participation minus downside "
        "participation (both measured over the past 252 sessions, the stock's summed return on "
        "SPY's up days over SPY's own, less the same on SPY's down days) and holding the 20 "
        "highest earned +10.3% a year against SPY TR's +7.2% on deposit-matched money, and beat "
        "SPY by 7.7 points a year over 2009-2015 -- the best post-2009 figure recorded in this "
        "lab, and the opposite sign to every other dev-window edge, all of which were earned "
        "before 2009. Its one defect is a 74.0% worst fall, with 2008 at -57.6%. That defect is "
        "exactly the one the SPY 200-day trend gate is measured to fix: it helped 22 of 22 "
        "variants whole-window, and the gate-off arms were worse on return AND drawdown at once. "
        "This re-runs the same ranking with the gate on. Variants: the plain gated book at 20 and "
        "40 names; an ungated 40-name arm as the paired control that must fall harder; one arm "
        "that ranks on the same spread but requires upside participation above 1.0 outright, to "
        "separate 'outruns the market both ways' from 'simply swings more'; and one that keeps "
        "the 200-day exit but buys back on M0113's measured-better trigger, a positive last "
        "quarter. Success: a gated variant keeps most of the +3.1 point whole-window lead and "
        "most of the +7.7 point 2009-2015 lead while bringing the fall under 50% on the dev "
        "screen and ideally near 25%."
    ),
    expected_failure=(
        "The likeliest failure is that the gate and this ranking want opposite things. The lab's "
        "own measurement of the 200-day switch is that it earns its whole twenty-year advantage "
        "in 2001, 2002 and 2008 and pays for it everywhere else, and over 2009-2015 every reading "
        "of it lost 6 to 11 points a year to simply holding SPY (M0084, M0113). This method's "
        "entire claim is a +7.7 point lead over 2009-2015. The most-asymmetric names are the ones "
        "that give the most back in a fall and run hardest in the recovery, so the gate will sell "
        "them after the fall has happened and buy them back after the bounce has happened -- it "
        "should cut the 74% fall and cut the post-2009 lead with it, and the honest outcome is a "
        "book that passes the drawdown screen and no longer beats SPY where it matters. The "
        "second failure is identity: the spread rank may simply be high-beta momentum under a new "
        "name, in which case it will read as behavioural kin of the test-failed momentum books "
        "once it has a gated curve, and the hard gate will bar promotion however good the numbers "
        "look. That correlation is to be measured and reported early, not hoped away. The third "
        "is survivorship: M0110's asymmetry arm lost 2.0 points a year on the fuller price "
        "history, more than any other arm except the control, so part of the edge is companies "
        "the dev store cannot price. Publication risk is low -- the up/down capture ratio is an "
        "old practitioner measure and the asymmetry direction is not the crowded one -- but a "
        "high-beta book dressed as a factor is exactly what fades first when the market's shape "
        "favours the largest companies, which is what beat every strategy this lab tried after "
        "2018."
    ),
    candidates=(
        _v("G20", AsymParams(N20, gate="sma200"),
           "The 20 most asymmetric names, behind the 200-day switch: the headline"),
        _v("G40", AsymParams(N40, gate="sma200"),
           "The same gated rank over 40 slots: less single-name risk, same signal"),
        _v("N40", AsymParams(N40, gate="none"),
           "40 slots, gate off: the paired control, which must fall harder than G40"),
        _v("G20-UP1", AsymParams(N20, gate="sma200", min_up=1.0),
           "Gated 20, but only names that genuinely outrun the market on its up days"),
        _v("G20-UP63", AsymParams(N20, gate="sma200-up63"),
           "Gated 20 that sells on the 200-day cross and buys back on a positive quarter"),
    ),
    seen_keys=(
        "concept:gated-up-down-capture-asymmetry",
        "concept:upside-participation-eligibility-filter",
        "concept:asymmetric-reentry-on-a-stock-book",
    ),
)
