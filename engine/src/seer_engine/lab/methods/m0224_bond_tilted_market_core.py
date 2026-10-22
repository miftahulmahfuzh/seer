"""M0224 — The market-shaped book leaning toward bond-like stocks: every index member at its real
size, tilted toward the companies that rise when Treasury yields fall.

Source: variation of M0201 (M0197's bond-like ranking, its 20 picks weighted by market value) and
its analysis: the bond-like ranking beat its rate-rising opposite at equal weight, at size weight
and on the survivorship-check store, but as a 20-name book it was no better than a size-weighted
random 20. The treasury-beta signal is the D.E. Shaw note (caia.org/node/6853), Maio & Santa-Clara
and Driessen, Kuiper & Beilo (2010s). Reserved by Sera 20261022-1918 as M0224.

Why this shape. M0201 asked the ranking to *pick* 20 names, and a 20-name book is a bet on 20
names whatever ranked them; its random 20 did as well. Here the ranking only *tilts* a book shaped
like the market, the FTSE/MSCI way M0222 and M0226 tilted it by dividend raises, so the tilt's
effect is a clean paired difference against the untilted core, against the opposite tilt and
against a random tilt of the same strength.

The core (refined from the reservation, written before any result). The reserved row named M0222's
top-50 core. M0226 has since measured that the top-50 core trails SPY by 1.2 points a year on the
owner's deposits while the whole screened market at size, 5% ceiling, beats it by 0.2: the
narrowness was the handicap, not the fees. A tilt judged on a core that starts a point behind can
only say "less behind", and the reservation's own expected failure names the other reason: the
bond-like edge M0201 lost lived partly in small utilities, which a top-50 core never holds. So the
core is M0226's, through M0222's own ``core`` and ``capped`` (imported unchanged): every F4-screened
member with a known point-in-time market value (``top`` past any day's member count), one class per
identical share count, weighted by market value, no company over 5%. CORE here is the same rule as
M0226-CORE under another allocator id, so it should reproduce M0226-CORE's +7.4%: a built-in check
that the tilt code leaves the core alone at power 0.

The score. On each monthly target date d, M0197's ``loadings`` (imported unchanged) fits every core
name's weekly log returns over the last 52 weeks on SPY's return and the change in the 10-year
yield; c is the yield loading. Across the core names with a loading, z = (c - mean) / sd, then
``side="bond"`` takes -z (rises when yields fall: up), ``"opp"`` takes +z (the paired opposite),
clipped to +-``zclip``, score = Phi(z). A name without a year of weekly marks, or a day with no
recent yield or fewer than ``min_names`` loadings, sits at a neutral 0.5 (the whole day neutral in
the second case). Weekly marks are monthly re-fits, not M0197's quarterly ones: the tilt is a
weight, not a slot, and the core re-weights monthly anyway.

The random twin. ``side="random"`` computes the bond scores and hands them, values and count
unchanged, to the same scored names in a blake2b hash order of seed, symbol and quarter (M0222's
``draw``): same core, same strength and spread, an order that knows nothing about yields.

Weights: market value x score^power, rescaled, capped at ``ceiling`` with the excess re-spread pro
rata (M0222's ``capped``). No SPY parking, no switch. Rules ``monthly-hold-frac-gotrade-tband``:
fractional, Gotrade's real fees, rebalance when a holding is 20% off its own target (a book of
hundreds of sub-1% weights would otherwise leave deposits in cash).

Market-aware: reads ``series`` (T10Y) and ``shares``; without either it targets nothing. Pure:
reads only bars, yields and share counts dated <= d.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_FLOOR, Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import NOT20
from seer_engine.lab.methods.m0197_treasury_yield_beta import loadings
from seer_engine.lab.methods.m0222_raise_tilted_market_core import capped, core, draw, phi
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    FactorPrepared,
    factor_lookback,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 22)
SIDES = ("bond", "opp", "random")
EVERY = 1000  # past any day's member count: the core is every member with a known size
CEIL = Decimal("0.05")
_W_Q = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class BondTiltParams:
    """``inner`` is F4's screen (no switch on any variant); ``top`` the core's size; ``ceiling``
    the most one company may weigh; ``power`` the tilt strength (0: no tilt); ``side`` the bond-
    like scores, their opposite, or the bond scores in a random order."""

    inner: FactorParams
    top: int = EVERY
    ceiling: Decimal = CEIL
    power: int = 1
    side: str = "bond"
    seed: int = 1
    zclip: float = 3.0
    min_names: int = 20
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name in ("top", "power", "seed", "min_names"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {v!r}")
        if self.top < 2 or self.power < 0 or self.min_names < 3:
            raise ValueError("top >= 2, power >= 0 and min_names >= 3")
        if not isinstance(self.ceiling, Decimal) or not (Decimal(0) < self.ceiling <= Decimal(1)):
            raise ValueError(f"ceiling must be a Decimal in (0, 1], got {self.ceiling!r}")
        if self.ceiling * self.top < 1:
            raise ValueError("ceiling x top must reach 1, or the weights cannot sum to 1")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if not isinstance(self.zclip, float) or not math.isfinite(self.zclip) or self.zclip <= 0:
            raise ValueError(f"zclip must be a finite float > 0, got {self.zclip!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"top": str(self.top), "ceiling": str(self.ceiling), "power": str(self.power),
               "side": self.side, "seed": str(self.seed), "zclip": repr(self.zclip),
               "min_names": str(self.min_names), "market": self.market,
               "loading": "m0197-weekly-52-t10y", "score": "normal-cdf-xs-z",
               "size": "market-value-one-class", "hash": "blake2b-8-quarter"}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> BondTiltParams:
    if not isinstance(params, BondTiltParams):
        raise TypeError(f"params must be BondTiltParams, got {type(params).__name__}")
    return params


@dataclass
class BondTiltPrepared:
    """The attributes M0222's ``core`` reads (history, factor, market) plus the yield series."""

    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared | None = field(repr=False)
    series: MarketSeries = field(repr=False)
    market: Any = field(repr=False, default=None)


def scores(prepared: BondTiltPrepared, names: list[str], data_date: date,
           p: BondTiltParams) -> dict[str, float]:
    """Each name's tilt score in (0, 1); 0.5 is neutral."""
    out = dict.fromkeys(names, 0.5)
    lv = loadings(prepared.history, prepared.series, names, data_date, p.market)
    if len(lv) < p.min_names:
        return out
    c = {s: bv[1] for s, bv in lv.items()}
    mean = statistics.fmean(c.values())
    sd = statistics.pstdev(c.values())
    if not sd > 0:
        return out
    sign = 1.0 if p.side == "opp" else -1.0
    real = {s: phi(max(-p.zclip, min(p.zclip, sign * (v - mean) / sd))) for s, v in c.items()}
    if p.side != "random":
        out.update(real)
        return out
    vals = sorted(real.values(), key=lambda v: (draw(p.seed, repr(v), data_date), v))
    takers = sorted(real, key=lambda s: (draw(p.seed, s, data_date), s))
    out.update(zip(takers, vals, strict=True))
    return out


def choose(prepared: BondTiltPrepared, members: AbstractSet[str], data_date: date,
           p: BondTiltParams) -> tuple[Target, ...]:
    book = core(prepared, members, data_date, p)  # type: ignore[arg-type]
    if len(book) < 2:
        return ()
    if p.power == 0:
        sc = dict.fromkeys((s for s, _, _ in book), 0.5)
    else:
        sc = scores(prepared, [s for s, _, _ in book], data_date, p)
    raw = {s: v * sc[s] ** p.power for s, _, v in book}
    w = capped(raw, float(p.ceiling))
    out: list[Target] = []
    for s, c, _ in sorted(book, key=lambda t: (-w[t[0]], t[0])):
        wt = Decimal(repr(w[s])).quantize(_W_Q, rounding=ROUND_FLOOR)
        if wt <= 0:
            continue
        t = target_from_close(s, c, wt)
        if t is not None:
            out.append(t)
    return tuple(out)


class BondTiltedCoreAllocator:
    """Every screened index company at its market value, tilted by its loading on 10-year yield
    changes (bond-like up, its opposite, or a random order of the same scores), capped per
    company. No yield or no share counts (the history-only path): no targets."""

    id = "M0224"
    market_fields = ("series", "shares")

    def lookback(self, params: Any) -> int:
        # As M0197: the screen's need only. A name without a year of weekly marks scores neutral.
        return factor_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: BondTiltPrepared, members: AbstractSet[str], data_date: date,
             p: BondTiltParams) -> tuple[Target, ...]:
        m = prepared.market
        if m is None or len(prepared.series) == 0 or len(m.shares) == 0:
            return ()  # no panel: target nothing (market-aware contract)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        return choose(prepared, members, data_date, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no yield and no share counts, so no target."""
        return self._run(BondTiltPrepared(history, None, EMPTY_SERIES), members, data_date,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> BondTiltPrepared:
        return BondTiltPrepared(history, prepare_factor(history), EMPTY_SERIES)

    def prepare_market(self, market: Any) -> BondTiltPrepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        return BondTiltPrepared(market.history, prepare_factor(market.history), series, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, BondTiltPrepared):
            raise TypeError(f"prepared must be BondTiltPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


BOND_TILT = BondTiltedCoreAllocator()


def _v(suffix: str, params: BondTiltParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0224-{suffix}", family="M0224", rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
                     allocator=BOND_TILT, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0224",
    name=(
        "The market-shaped book leaning toward bond-like stocks: every index company at its "
        "market value, tilted toward those that rise when yields fall, beside a random tilt"
    ),
    family="stock-treasury-beta",
    source_kind="variation",
    source_ref=(
        "M0201 (bond-like ranking at size weight) and M0197 (weekly 10-year yield loading); "
        "D.E. Shaw research note on Treasury beta (caia.org/node/6853); Maio & Santa-Clara; "
        "Driessen, Kuiper & Beilo; FTSE Russell factor-tilt method; M0222/M0226 (the tilted "
        "market core and its random twin)"
    ),
    parent_id="M0201",
    hypothesis=(
        "Treasury-beta pricing published in the 2010s; the dev window is before publication. "
        "The bond-like ranking (M0197's weekly loading on 10-year yield changes, net of SPY) beat "
        "its opposite at equal weight (+12.5% vs +7.7% on the deposits), at size weight under a "
        "10% cap (M0201: +9.5% vs +6.2%) and on the survivorship-check store (+8.0% vs +2.4%), but "
        "as a 20-name book it was no better than a size-weighted random 20 (+8.1% to +10.3%). "
        "Test it as a tilt on the market's own shape. Core (refined from the reserved top-50: "
        "M0226 measured the top-50 core 1.2 points a year behind SPY and the whole screened "
        "market 0.2 ahead): every F4-screened index member with a known point-in-time market "
        "value, one class per identical share count, weighted by market value, no company over "
        "5% (M0226's core through M0222's code). Score: M0197's 52-week weekly loading c, z = "
        "(c - cross-sectional mean) / sd over the core names with a loading, bond side -z, "
        "opposite +z, clipped +-3, score Phi(z), re-fit monthly; no loading or fewer than 20 "
        "loadings that day: neutral 0.5. Weight = value x score^power, rescaled, re-capped. "
        "Variants: CORE (power 0; should reproduce M0226-CORE), TILT1, TILT2, OPP2 (the opposite "
        "tilt, power 2), RAND1/RAND2 (the day's bond scores handed to the same names in a hash "
        "order, quarterly). All monthly, fractional, Gotrade's real fees, target-relative band, "
        "owner's deposits, no SPY parking, no switch. Success: TILT1 or TILT2 beats total-return "
        "SPY on the deposits, beats CORE and both RAND twins by 1+ point a year, does not trail "
        "SPY in 2009-2015, and its gap to OPP2 survives the check store. The 2x2 that prices the "
        "opinion: TILT2 vs OPP2 is the signal, CORE is the no-opinion arm, RAND2 the cost of "
        "tilting at that strength with no information."
    ),
    expected_failure=(
        "Size dominates the weights: a tilt of Phi(z)^2 moves a 5%-capped market book by tenths "
        "of a point a year, as the dividend tilt did on the same core (M0226: +0.1-0.3 over CORE, "
        "0.2-0.8 over its random twin). The bond-like end of the market is utilities, staples, "
        "pharma and REITs; in 1996-2015 falling yields paid them, but in 2009-2015 they lagged a "
        "tech-led rally, so the tilt trails CORE there and CORE already trails SPY by about a "
        "point after 2009. On the check store the dead companies cost about a point a year and "
        "erase any lead. Ungated, every variant falls about 50% in 2008, twice the 25% bar; the "
        "bond tilt may soften that fall by a few points (bond-like stocks fell less), which is "
        "the one thing it could add. A falling-yield era favours this tilt on dev; 2022's rising "
        "yields are exactly when it would have hurt, so any dev edge is partly the era."
    ),
    candidates=(
        _v("CORE", BondTiltParams(NOT20, power=0),
           "The yardstick: every member with a known size at market value, 5% ceiling, no tilt"),
        _v("TILT1", BondTiltParams(NOT20, power=1),
           "Market value x bond-like score (normal-CDF of minus the yield loading's z-score)"),
        _v("TILT2", BondTiltParams(NOT20, power=2),
           "Market value x bond-like score squared: the stronger tilt"),
        _v("OPP2", BondTiltParams(NOT20, power=2, side="opp"),
           "The opposite tilt, squared: toward stocks that rise when yields rise"),
        _v("RAND1", BondTiltParams(NOT20, power=1, side="random"),
           "Control: the same day's bond scores in a hash order, power 1"),
        _v("RAND2", BondTiltParams(NOT20, power=2, side="random"),
           "Control: the same day's bond scores in a hash order, power 2"),
    ),
    seen_keys=(
        "concept:treasury-beta",
        "concept:interest-rate-sensitivity",
        "concept:market-cap-weight",
        "concept:factor-tilt",
        "concept:random-tilt-control",
        "concept:whole-market-core",
    ),
)
