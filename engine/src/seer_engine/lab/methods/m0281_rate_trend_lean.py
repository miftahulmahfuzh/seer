"""M0281 — Lean with the rate trend: the market-shaped book leaning toward bond-like stocks while
the 10-year yield is falling and toward rate-rising stocks while it is rising.

Source: variation of M0224 (the whole-market core tilted by M0197's 10-year yield loading) and its
analysis. Reserved by Sera 20261022-1954 as M0281. Treasury-beta pricing: the D.E. Shaw note
(caia.org/node/6853), Maio & Santa-Clara, Driessen, Kuiper & Beilo (2010s); the rate-trend read is
the oldest macro rule there is.

Why this shape. M0224's strong bond-like lean beat its opposite by 0.6 points a year over 1996-2015
(0.8 on the survivorship-check store) but reversed in 2009-2015: the opposite lean kept pace with
SPY while the bond lean trailed by 2.7 points a year. A fixed lean is a bet on one rate era. The
mechanism the treasury-beta papers give is a rate *regime*: bond-like stocks pay while yields fall
and lag while they rise. So the lean here follows the yield's own trend instead of holding a side.
It is still a lean on the market's shape (M0224's core, scores and cap, imported unchanged), so the
switch's worth is a clean paired difference against no lean, the two fixed leans and its mirror.

The regime. On each monthly target date d: Y = T10Y's latest value on or before d, Y0 = its latest
value on or before d minus ``months`` x 30.4375 days (12 months: d - 365.25 days, floored to a
date). If the latest row is older than STALE_DAYS, or there is no Y0, the day is neutral (CORE's
weights). Y < Y0 (yields fell over the year): ``regime="switch"`` leans bond-like, ``"mirror"``
leans rate-rising; Y >= Y0: the other way round. ``"fixed"`` keeps the tilt's own side.

The arms (written before any result). SWITCH and MIRROR are the rule and its reverse; together
they say whether the regime read is a signal. BOND2 and OPP2 always lean one way, and CORE never
leans: the third arm with no opinion in it, which prices what leaning itself costs (M0224 measured
the habit at about 0.8 points a year, the average of its two leans against CORE). Power 2 on every
leaning arm, M0224's stronger lean, because the weaker one moved the book by tenths. BOND2, OPP2
and CORE repeat M0224's TILT2, OPP2 and CORE under this allocator; they should reproduce them, a
built-in check that the regime code leaves the lean alone.

Rules ``monthly-hold-frac-gotrade-tband``: fractional, Gotrade's real fees, re-weight when a
holding drifts 20% off its own target. No SPY parking, no 200-day switch.

Market-aware: reads ``series`` (T10Y) and ``shares``; without either it targets nothing. Pure:
reads only bars, yields and share counts dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import NOT20
from seer_engine.lab.methods.m0197_treasury_yield_beta import RATE, STALE_DAYS
from seer_engine.lab.methods.m0224_bond_tilted_market_core import (
    BOND_TILT,
    BondTiltParams,
    BondTiltPrepared,
    choose,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import trend_on

ADDED = date(2026, 10, 22)
REGIMES = ("fixed", "switch", "mirror")
_MONTH_DAYS = 30.4375


@dataclass(frozen=True, slots=True)
class RateTrendParams:
    """``tilt`` is M0224's lean (its side is used only when ``regime="fixed"``); ``regime`` picks
    the side from the yield's trend; ``months`` is how far back the trend looks."""

    tilt: BondTiltParams
    regime: str = "switch"
    months: int = 12

    def __post_init__(self) -> None:
        if not isinstance(self.tilt, BondTiltParams):
            raise TypeError(f"tilt must be BondTiltParams, got {type(self.tilt).__name__}")
        if self.regime not in REGIMES:
            raise ValueError(f"regime must be one of {REGIMES}, got {self.regime!r}")
        if isinstance(self.months, bool) or not isinstance(self.months, int) or self.months < 1:
            raise ValueError(f"months must be an int >= 1, got {self.months!r}")
        if self.regime != "fixed" and self.tilt.side == "random":
            raise ValueError("a regime picks bond or opp; a random tilt has no side to switch")

    def as_dict(self) -> dict[str, str]:
        out = {"regime": self.regime, "months": str(self.months), "rate": RATE,
               "stale_days": str(STALE_DAYS), "trend": "level-vs-months-ago"}
        for k, v in self.tilt.as_dict().items():
            out[f"tilt.{k}"] = v
        return out


def _check(params: object) -> RateTrendParams:
    if not isinstance(params, RateTrendParams):
        raise TypeError(f"params must be RateTrendParams, got {type(params).__name__}")
    return params


def falling(prepared: BondTiltPrepared, data_date: date, months: int) -> bool | None:
    """True when the 10-year yield is below its level ``months`` ago; None when unknown."""
    last = prepared.series.upto(RATE, data_date, last=1)
    if not last or (data_date - last[0][0]).days > STALE_DAYS:
        return None
    then = prepared.series.value_on(RATE, data_date - timedelta(days=int(months * _MONTH_DAYS)))
    if then is None:
        return None
    return last[0][1] < then


def lean(prepared: BondTiltPrepared, data_date: date, p: RateTrendParams) -> BondTiltParams:
    """The day's M0224 lean: the fixed one, or the side the yield's trend picks (no lean when the
    trend is unknown)."""
    if p.regime == "fixed" or p.tilt.power == 0:
        return p.tilt
    f = falling(prepared, data_date, p.months)
    if f is None:
        return replace(p.tilt, power=0)
    bond = f if p.regime == "switch" else not f
    return replace(p.tilt, side="bond" if bond else "opp")


class RateTrendLeanAllocator:
    """M0224's whole-market core leaned bond-like or rate-rising by the 10-year yield's trend."""

    id = "M0281"
    market_fields = ("series", "shares")

    def lookback(self, params: Any) -> int:
        return BOND_TILT.lookback(_check(params).tilt)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return BOND_TILT.symbols(_check(params).tilt)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: BondTiltPrepared, members: AbstractSet[str], data_date: date,
             p: RateTrendParams) -> tuple[Target, ...]:
        m = prepared.market
        if m is None or len(prepared.series) == 0 or len(m.shares) == 0:
            return ()  # no panel: target nothing (market-aware contract)
        if not trend_on(prepared.history, data_date, p.tilt.inner):
            return ()
        return choose(prepared, members, data_date, lean(prepared, data_date, p))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no yield and no share counts, so no target."""
        p = _check(params)
        return BOND_TILT.targets(history, members, data_date, held, p.tilt)

    def prepare(self, history: Mapping[str, History]) -> BondTiltPrepared:
        return BOND_TILT.prepare(history)

    def prepare_market(self, market: Any) -> BondTiltPrepared:
        return BOND_TILT.prepare_market(market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, BondTiltPrepared):
            raise TypeError(f"prepared must be BondTiltPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


RATE_TREND = RateTrendLeanAllocator()


def _p(regime: str, power: int = 2, side: str = "bond") -> RateTrendParams:
    return RateTrendParams(BondTiltParams(NOT20, power=power, side=side), regime=regime)


def _v(suffix: str, params: RateTrendParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0281-{suffix}", family="M0281", rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
                     allocator=RATE_TREND, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0281",
    name=(
        "Lean with the rate trend: a market-shaped book that tilts toward bond-like stocks while "
        "10-year yields are falling and toward rate-rising stocks while they are rising"
    ),
    family="stock-treasury-beta-regime",
    source_kind="variation",
    source_ref=(
        "M0224 (bond-like lean on the whole-market core) and its analysis; M0197 (weekly 10-year "
        "yield loading); D.E. Shaw research note on Treasury beta (caia.org/node/6853); Maio & "
        "Santa-Clara; Driessen, Kuiper & Beilo"
    ),
    parent_id="M0224",
    hypothesis=(
        "Treasury-beta pricing published in the 2010s; the rate-trend read is decades old. "
        "M0224's bond-like lean beat its opposite by 0.6 points a year over 1996-2015 (0.8 on the "
        "check store) but reversed in 2009-2015 (opposite lean +0.0 vs SPY, bond lean -2.7). Use "
        "the reversal: on the whole-market base (every sized member at market value, one class "
        "per identical share count, 5% ceiling, monthly, fractional, Gotrade fees, target-"
        "relative band; M0224's core, scores and cap unchanged), lean power 2 toward the "
        "bond-like side when the 10-year yield is below its level 12 months ago and toward the "
        "rate-rising side when it is at or above it; a stale (over 7 days) or missing yield "
        "leans nowhere. Arms: SWITCH, MIRROR (the reverse rule), BOND2 (always bond), OPP2 "
        "(always opposite) and CORE (no lean, the no-opinion arm); BOND2/OPP2/CORE should "
        "reproduce M0224's TILT2/OPP2/CORE. Success: SWITCH beats CORE and total-return SPY on "
        "the owner's deposits, beats MIRROR, does not trail SPY in 2009-2015, and its gap to "
        "MIRROR holds on the check store. Assumption: 12 months and the level comparison are "
        "fixed now, not searched."
    ),
    expected_failure=(
        "The yield's 12-month trend is slow and public, and stock prices move before it does: by "
        "the time a year of falling yields is visible, bond-like stocks have already re-priced. "
        "The lean costs about 0.8 points a year in churn and in weight moved off the biggest "
        "companies (M0224), and switching sides adds turnover on top, so SWITCH trails CORE "
        "even if it beats MIRROR. 2009-2015 had mostly falling-then-flat yields with sharp "
        "rises in 2009, 2013 and 2015, so the switch spends that era mostly on the bond side, "
        "the side that lost then. Ungated, every arm falls about 50% in 2008, twice the 25% bar; "
        "nothing here touches that."
    ),
    candidates=(
        _v("SWITCH", _p("switch"),
           "Lean bond-like while the 10-year yield is below its level a year ago, rate-rising otherwise"),
        _v("MIRROR", _p("mirror"),
           "The reverse rule: rate-rising while yields fall, bond-like while they rise"),
        _v("BOND2", _p("fixed"), "Always lean bond-like, power 2 (M0224-TILT2 under this allocator)"),
        _v("OPP2", _p("fixed", side="opp"),
           "Always lean rate-rising, power 2 (M0224-OPP2 under this allocator)"),
        _v("CORE", _p("fixed", power=0),
           "No lean: every member with a known size at market value, 5% ceiling (the no-opinion arm)"),
    ),
    seen_keys=(
        "concept:treasury-beta",
        "concept:interest-rate-sensitivity",
        "concept:rate-regime-switch",
        "concept:yield-trend",
        "concept:market-cap-weight",
        "concept:factor-tilt",
        "concept:whole-market-core",
    ),
)
