"""M0251 — The price of risk as a timing signal: hold more of the market when insurance is dear.

Source: Bollerslev, Tauchen & Zhou (2009), "Expected Stock Returns and Variance Risk Premia",
Review of Financial Studies 22(11) 4463-4492. Reserved by Sera 20261019-1014.

Idea: the variance risk premium is what an investor is paid to carry the market's swings --
the variance the option market charges for, less the variance that actually turns up. The
paper finds it predicts stock returns at the quarterly horizon, better than the dividend yield
or the price-earnings ratio. The store has no options, but it has the fear index and SPY's
daily bars, which is all the paper's own empirical proxy needs: implied variance is the fear
index squared, and expected future realised variance is proxied by the realised variance just
past (the "no-change" forecast the paper uses). So::

    VRP(d) = VIX(d)^2  -  252 / rv_n * sum of the last rv_n squared daily SPY log returns

both in annualised percent-squared, read from rows dated <= d only.

The level of that number means nothing on its own -- it scales with the volatility regime --
so the rule reads its **rank inside its own trailing ``rank_n`` sessions**. ``q`` is the share
of those readings at or below today's. Three rungs, decided once a month:

    ``q >= hi``        the premium is in the top third of its own recent range  -> SPY at 1.0
    ``lo <= q < hi``   the middle third                                         -> SPY at 0.5
    ``q <  lo``        the bottom third                                         -> cash

``mode`` picks which way round that ladder runs:

    * ``"ladder"``  the idea: full when the premium is high, cash when it is low.
    * ``"mirror"``  the falsification arm: the same three rungs, reversed. If the mirror does
      as well, the ladder is measuring the *shape* of a part-invested book, not the premium.
    * ``"binary"``  full in the top two thirds, cash in the bottom third: the half-weight
      middle rung removed, so the ladder's middle rung can be priced on its own.

**What the probe found before this file was committed** (rankings only, no returns): over
1994-2015 the month-end rungs split 35% cash, 26% half, 39% full, and the rung changed in 151
of 260 month steps, so this is a busy signal, not a buy-and-hold in disguise. The premium is
*negative* 13% of sessions and goes deeply negative in crashes -- October 2008 reads -4315,
the lowest in the window -- because trailing realised variance explodes above the fear index
when the fall is already happening. So the ladder sits in cash through a crash and steps back
to full once insurance is dear again relative to a calm tape (January and February 2009 both
read full). That is the opposite of what the reserved idea row expected, and it is written
into ``expected_failure`` below as it stands, not as it was guessed.

No reading is not a signal: when the fear index's latest row is more than ``STALE_DAYS`` old,
or there are not yet ``rank_n + rv_n`` SPY closes, every mode holds SPY at full weight. That
keeps the early window identical across arms, so a paired difference against the HOLD control
is the signal and never a coverage artefact.

Market-aware: ``prepare_market`` carries the series. The history-only path has no series and
targets nothing, per the lab's market-aware contract.

Eligibility is not expected and is not the point. A book that holds one instrument cannot beat
SPY except by sidestepping falls for more than its whipsaw costs, and its round-trip count will
be far under the 100 the gate wants. The readable results are the paired differences: ladder
against HOLD (does the premium pay?), ladder against MIRROR (is it the premium or the shape?),
ladder against SPY-200 (does it beat the switch the lab already trusts?), and LADDER-CASH
against LADDER (how much of every timing method's reported cost is simply idle cash earning
nothing?).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_index import TIMING, TimingParams

ADDED = date(2026, 10, 19)

STALE_DAYS = 7  # a fear-index row older than this (calendar days) is no reading: hold full

# The ladder with idle cash credited the 13-week Treasury bill yield, read point in time from the
# store's own series. One lever away from the preset above, and the only arm that differs from
# LADDER at all. It raises the owner input "cash-yield" (nobody has checked that Gotrade pays
# interest on idle dollars), so paper refuses it and it can never be promoted -- it exists to
# measure what every cash-holding method in this lab has silently been charged.
MONTHLY_HOLD_FRAC_GOTRADE_CASH = replace(
    MONTHLY_HOLD_FRAC_GOTRADE, id="monthly-hold-frac-gotrade-cash", cash_yield="T13W"
)

Mode = Literal["ladder", "mirror", "binary"]
_MODES: tuple[str, ...] = ("ladder", "mirror", "binary")


@dataclass(frozen=True, slots=True)
class VrpParams:
    """``mode`` picks the ladder's direction; ``lo``/``hi`` are its two rank cut-offs."""

    mode: Mode = "ladder"
    rv_n: int = 22  # sessions of SPY returns in the realised variance (about one month)
    rank_n: int = 252  # sessions of premium readings the rank is taken inside (about one year)
    lo: float = 1.0 / 3.0
    hi: float = 2.0 / 3.0

    def __post_init__(self) -> None:
        if not isinstance(self.mode, str) or self.mode not in _MODES:
            raise ValueError(f"mode must be one of {_MODES}, got {self.mode!r}")
        for name, lowest in (("rv_n", 2), ("rank_n", 2)):
            x = getattr(self, name)
            if isinstance(x, bool) or not isinstance(x, int) or x < lowest:
                raise ValueError(f"{name} must be an int >= {lowest}, got {x!r}")
        for name in ("lo", "hi"):
            x = getattr(self, name)
            if isinstance(x, bool) or not isinstance(x, float) or not 0.0 < x <= 1.0:
                raise ValueError(f"{name} must be a float in (0, 1], got {x!r}")
        if not self.lo < self.hi:
            raise ValueError(f"lo {self.lo} must be below hi {self.hi}")

    def as_dict(self) -> dict[str, str]:
        return {"mode": self.mode, "rv_n": str(self.rv_n), "rank_n": str(self.rank_n),
                "lo": repr(self.lo), "hi": repr(self.hi)}


def _check(params: object) -> VrpParams:
    if not isinstance(params, VrpParams):
        raise TypeError(f"params must be VrpParams, got {type(params).__name__}")
    return params


def premium_rank(history: Mapping[str, History], series: MarketSeries, data_date: date,
                 p: VrpParams) -> float | None:
    """``q``: the share of the trailing ``rank_n`` premium readings at or below today's.

    None when the signal cannot be read -- too little history, or no fresh fear index -- which
    every mode treats as "hold full weight", not as a bearish reading.
    """
    h = history.get("SPY")
    if h is None:
        return None
    bars = h.upto(data_date)
    need = p.rank_n + p.rv_n
    if len(bars) < need:
        return None
    latest = series.upto("VIX", data_date, last=1)
    if not latest or (data_date - latest[-1][0]) > timedelta(days=STALE_DAYS):
        return None

    # Exactly the last `need` closes, left to right, so the answer cannot depend on how much
    # history was loaded (the lookback contract).
    closes = [float(x) for x in bars.close[-need:]]
    days = [d.item() for d in bars.dates[-need:]]
    rets: list[float] = []
    for i in range(1, need):
        prev, cur = closes[i - 1], closes[i]
        if not (prev > 0.0 and cur > 0.0):
            return None
        rets.append(100.0 * math.log(cur / prev))

    readings: list[float] = []
    # Session index i in [rv_n, need); its realised variance reads rets[i - rv_n : i].
    for i in range(p.rv_n, need):
        vix = series.value_on("VIX", days[i])
        if vix is None or vix <= 0.0:
            return None
        total = 0.0
        for r in rets[i - p.rv_n:i]:
            total += r * r
        readings.append(vix * vix - 252.0 * total / p.rv_n)
    if len(readings) != p.rank_n:
        return None

    today = readings[-1]
    at_or_below = 0
    for x in readings:
        if x <= today:
            at_or_below += 1
    return at_or_below / p.rank_n


def rung(q: float | None, p: VrpParams) -> int:
    """0 = cash, 1 = half weight, 2 = full weight. No reading is full weight, not cash."""
    if q is None:
        return 2
    step = 2 if q >= p.hi else (1 if q >= p.lo else 0)
    if p.mode == "mirror":
        return 2 - step
    if p.mode == "binary":
        return 2 if step >= 1 else 0
    return step


@dataclass(frozen=True, slots=True, eq=False)
class VrpPrepared:
    history: Mapping[str, History]
    series: MarketSeries


class VrpAllocator:
    """SPY at full weight, half weight or nothing, by where the premium sits in its own range."""

    id = "M0251"
    market_fields = ("series",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return p.rank_n + p.rv_n

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return False

    def _run(self, prepared: VrpPrepared, data_date: date, held: frozenset[str],
             p: VrpParams) -> tuple[Target, ...]:
        if len(prepared.series) == 0:  # no series: target nothing (market-aware contract)
            return ()
        step = rung(premium_rank(prepared.history, prepared.series, data_date, p), p)
        if step == 0:
            return ()
        h = prepared.history.get("SPY")
        if h is None or (h.index_of(data_date) is None and "SPY" not in held):
            return ()  # a symbol with no bar dated d is never a NEW target
        weight = equal_weight(1) if step == 2 else equal_weight(2)
        t = target_from_close("SPY", last_close(h, data_date), weight)
        return () if t is None else (t,)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no series, so no reading and no target."""
        return self._run(VrpPrepared(history, EMPTY_SERIES), data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> VrpPrepared:
        return VrpPrepared(history, EMPTY_SERIES)

    def prepare_market(self, market: Any) -> VrpPrepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        return VrpPrepared(market.history, series)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, VrpPrepared):
            raise TypeError(f"prepared must be VrpPrepared, got {type(prepared).__name__}")
        return self._run(prepared, data_date, held, _check(params))


VRP = VrpAllocator()


def _v(suffix: str, allocator: Any, params: Any, rationale: str,
       rules: Any = MONTHLY_HOLD_FRAC_GOTRADE) -> Candidate:
    return Candidate(id=f"M0251-{suffix}", family="M0251", rules=rules, allocator=allocator,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0251",
    name=("The price of risk as a timing signal: hold more of the market when insurance "
          "against its swings is expensive"),
    family="volatility-risk-premium",
    source_kind="paper",
    source_ref=("Bollerslev, Tauchen & Zhou (2009), Expected Stock Returns and Variance Risk "
                "Premia, Review of Financial Studies 22(11) 4463-4492"),
    parent_id=None,
    hypothesis=(
        "Bollerslev, Tauchen and Zhou (2009) found that the variance risk premium -- what the "
        "option market charges for variance, less the variance that actually turns up -- predicts "
        "stock returns at the quarterly horizon, and does it better than the dividend yield or the "
        "price-earnings ratio. The store has no options but it has the fear index and SPY's daily "
        "bars, which is all the paper's own empirical proxy needs: implied variance is the fear "
        "index squared and expected future realised variance is proxied by the realised variance "
        "just past (the no-change forecast), so the premium is VIX(d) squared less 252/22 times the "
        "sum of the last 22 squared daily SPY log returns, both annualised, read from rows dated on "
        "or before d. The level means nothing on its own, so the rule reads the premium's rank "
        "inside its own trailing 252 sessions: top third SPY at full weight, middle third half "
        "weight, bottom third cash, decided once a month in fractional shares at Gotrade's real "
        "fees on the owner's 5,000,000 IDR monthly top-up. Variants: LADDER (the idea), MIRROR (the "
        "falsification arm, the same three rungs reversed -- if it does as well, the ladder is "
        "measuring the shape of a part-invested book and not the premium), BINARY (full in the top "
        "two thirds, cash in the bottom third, which prices the half-weight middle rung on its own), "
        "HOLD (control: SPY at full weight always, same rules and same fees, so the paired "
        "difference is the signal alone), SPY-200 (control: the 200-day switch the lab already "
        "trusts, on the same monthly rules), and LADDER-CASH (the ladder with idle cash credited "
        "the 13-week Treasury bill yield -- one lever away from LADDER and the only difference). "
        "A ranking probe run before this file was committed (rungs and dates only, no returns) "
        "found the month-end rungs split 35% cash, 26% half and 39% full over 1994-2015, with the "
        "rung changing in 151 of 260 month steps, so the signal is busy and not degenerate. "
        "Assumed: no fresh fear index or too little history means full weight, not cash, so every "
        "arm's early window is identical; the premium is read on day d's close and traded at the "
        "next open; idle cash earns nothing except in LADDER-CASH. Success: LADDER beats HOLD on "
        "funded return with a shallower worst fall, beats MIRROR clearly, and beats SPY-200 on at "
        "least one of return and depth of fall, with a positive 2009-2015 edge. Eligibility is not "
        "expected: a one-instrument book has far fewer than 100 round trips and cannot clear the "
        "luck bar at N=158, so the paired differences are the result."
    ),
    expected_failure=(
        "The reserved idea row expected this rule to be fully invested into crashes, because the "
        "premium is highest in crises. The probe says the opposite and that correction is written "
        "here before any return is known: with trailing realised variance as the forecast, the "
        "premium goes deeply NEGATIVE in a crash -- October 2008 is the lowest reading in the "
        "window -- because realised variance explodes above the fear index once the fall is already "
        "happening. So the ladder is a defensive signal, and its real failure mode is the one every "
        "reactive risk rule in this lab has had: it sells after the drop and buys back after the "
        "rebound. The probe's 151 rung changes in 260 months is a flip roughly every other month, "
        "each paying Gotrade's fees on a 20M IDR book, and most of those flips are noise in a "
        "rising market. Expect the ladder to cut the 2008 fall and to give the saving back across "
        "2009-2015, the years this lab weighs most, where it is in cash or half weight about 61% of "
        "months during the longest rally in the window. March 2009 is the sharpest warning in the "
        "probe: the ladder reads full in January and February 2009 and then CASH at the end of "
        "March, one rung change at the exact bottom. A second, quieter failure is that the premium "
        "and the 200-day switch may be the same signal twice -- both go defensive after a fall -- in "
        "which case LADDER-SPY-200 differences are noise and the idea adds nothing to what the lab "
        "already owns. A third: the paper is from 2009, so the 2009-2015 half of the window is "
        "post-publication and the edge there is the faded one. The half-weight rung is the most "
        "likely thing to be worthless -- a 26%-of-months rung that splits the difference should "
        "earn about half the ladder's gap to HOLD and nothing more, which BINARY will show. "
        "Finally, idle cash earning nothing penalises every arm but HOLD, and in 1994-2007 "
        "Treasury bills paid 4-5%, so a book in cash a third of the time is charged more than a "
        "point a year that a real account would have earned: LADDER-CASH measures exactly that, and "
        "if the whole of LADDER's gap to HOLD is closed by it, then this lab's verdicts on the "
        "200-day switch, the fear-spike gate and every other cash-holding rule are all overstated."
    ),
    candidates=(
        _v("LADDER", VRP, VrpParams("ladder"),
           "SPY full / half / cash by where the variance premium sits in its own trailing year"),
        _v("MIRROR", VRP, VrpParams("mirror"),
           "Falsification: the same three rungs reversed, full weight when the premium is lowest"),
        _v("BINARY", VRP, VrpParams("binary"),
           "The half-weight middle rung removed: full in the top two thirds, cash in the bottom"),
        _v("HOLD", TIMING, TimingParams(hold="SPY", signal="SPY", rule="always"),
           "Control: SPY at full weight always, on the same monthly rules and the same real fees"),
        _v("SPY-200", TIMING, TimingParams(hold="SPY", signal="SPY", rule="sma", n=200),
           "Control: the 200-day switch the lab already trusts, on the same monthly rules"),
        _v("LADDER-CASH", VRP, VrpParams("ladder"),
           "The ladder with idle cash credited the 13-week Treasury bill yield",
           MONTHLY_HOLD_FRAC_GOTRADE_CASH),
    ),
    seen_keys=(
        "concept:variance-risk-premium",
        "concept:implied-minus-realised-variance",
        "concept:vix-rank-exposure-ladder",
        "concept:cash-yield-credit",
    ),
)
