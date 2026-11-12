"""M0564 — Industry momentum, diluted into a market-wide core: hold every known-industry member,
sized by market value, with a modest overweight toward the momentum-ranked winning industries.

Source: variation of M0563 (Moskowitz & Grinblatt 1999, Do Industries Explain Momentum?).
Idea: M0563 showed real money picking the 3-4 strongest FF12 industries by trailing return and
value-weighting every sizeable member inside beats SPY and a blind-industry draw by several points
a year (CAP-T3-W6: +8.5%/yr vs SPY's +7.2%, beating RANDOM-T3-W6's +5.0%/yr by 3.5 points), but
every arm's luck score (DSR 0.796-0.830) falls under the lab's 0.90 bar, and the switch-off control
shows 3-4 concentrated industry bets without the 200-day switch fall 47.3% in 2008 -- M0563's own
closing opinion named concentration, not the window or the switch, as the next thing to attack.

This method keeps M0563's exact industry-strength signal (FF12 industries, SIC-mapped, equal-weight
mean 6-1 member return, >= 5 pool members to be ranked) but changes what the book HOLDS: instead of
100% concentrated in 3 strong industries plus SPY for the rest, hold a market-value-weighted CORE
across every screened, known-industry member the store can size -- the same universe M0563 ranked
industries from, not a narrower pool -- with members of the chosen momentum industries given a
multiplicative overweight (``tilt``) before renormalizing. ``tilt=0`` holds the market-value-weighted
core with no industry opinion at all: the no-opinion control for the whole family, priced on THIS
book shape rather than borrowed from M0563's narrower one. Money the book can't size, and industries
with no known industry label, is excluded from the core (unknown industry is never bought, M0563's
rule); nothing is parked in SPY unless a tilt renormalizes to a shortfall, which does not happen
here since the core itself spans the whole known universe. Cash under SPY's 200-day average, as
every arm of this family -- M0563's own NOSW control already measured what dropping that switch
costs on a concentrated version of this book (47.3% max DD, 2008 at -33.1%) and this run does not
re-spend an arm re-asking that question on the diluted book; the assumption, written here before any
result, is that a market-wide core is at least as exposed to a trend reversal as the narrower one.

On data date d:

    * the pool is F4's screened members on d, same universe and industry mapping as M0563
      (``m0216_industry_winners_member_laggards.sector_of``); an unknown industry is excluded from
      ranking and from the book;
    * industries with >= 5 pool members are ranked by the equal-weight mean of member 6-1 return
      (``inner.mom_n=126, mom_skip=21``), exactly M0563's W6 window -- M0563 found 6-1 vs 12-1 moved
      its DSR by only 0.02, plausibly noise, so this run spends its arms on the dilution dial
      instead of re-testing the window;
    * every pool member across every eligible (>= 5 member) industry that the store can size
      (``m0221_cap_weighted_top_n.sized_pool``) is held, weighted by its own market value --
      the CORE, spanning every industry the signal can rank, not only the chosen ones;
    * each core member in one of the ``p.sectors`` strongest industries (``pick="momentum"``) gets
      its market-value weight multiplied by ``(1 + p.tilt)`` before the whole core is renormalized
      to sum to 1; ``p.tilt=0`` is the no-opinion core (every member at its plain market-value
      share, regardless of industry momentum); ``pick="hash"`` draws the same count of industries
      by a fixed monthly hash instead of momentum, at a fixed non-zero tilt, to separate "does
      overweighting ANY handful of industries help" from "does overweighting the MOMENTUM-ranked
      ones help";
    * no name above ``p.cap`` (10%) of the whole account, applied once across the renormalized core
      (M0034/M0221/M0563's water-filling);
    * no SPY holding and no cash band beyond the switch: the core already spans the whole known
      universe, so there is no unfilled remainder to park. Cash under SPY's 200-day average
      (F4's switch, ``inner.trend``), as every F4-frame book in this lab.

Why this is not a repeat of a recorded book. M0563's arms hold ONLY the 3-4 chosen industries (the
rest of the account sits in SPY); this book holds every known-industry member the store can size,
all the time, with the chosen industries merely overweighted inside that broader base -- a
materially different name count, different per-name weights and a different curve even at matching
``sectors``/window. ``CORE-TILT0`` in particular holds the whole known-industry universe at its
plain market value with no industry opinion, which no recorded M0563/M0216/M0217 arm does (their
every arm either narrows to a slot count or a chosen-industry subset). ``lab run`` checks every
arm's finished curve against the record regardless of this reasoning; if any arm still matches a
recorded curve, that is the system working and the arm must be re-declared truthfully.

Assumption, written before any result: the same 38-43% of pool member-days in 2009-2015 with no
known market value (mostly later-delisted names) that M0563 flagged applies here too, now spread
across the whole core rather than 3-4 industries; an edge (or its absence) that depends on the
uncovered half is a question for ``lab survivorship``, not this run.

Market-aware (``market_fields = ("shares",)``): the history-only path has no share counts, so by
contract it targets nothing (M0563's exact pattern). Rules are ``monthly-hold-frac-gotrade``:
fractional shares at Gotrade's real fees, asked monthly. Pure: no clock, randomness, files or
network in this file; reads only bars and share counts dated at or before d.
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
from seer_engine.lab.methods.m0034_size_tilt_residual import _apply_ceiling, _floor_weight
from seer_engine.lab.methods.m0216_industry_winners_member_laggards import sector_of
from seer_engine.lab.methods.m0221_cap_weighted_top_n import DV_N as TRADE_VALUE_N
from seer_engine.lab.methods.m0221_cap_weighted_top_n import sized_pool
from seer_engine.lab.methods.m0563_industry_momentum_value_weighted import (
    CapIndustryPrepared,
    MIN_MEMBERS,
    draw_industry,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.sim.book import Target
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 12)
PICKS = ("momentum", "hash")


@dataclass(frozen=True, slots=True)
class CoreTiltParams:
    """``inner`` is F4's screen, switch and industry-momentum window.

    ``inner.top`` is not read (no per-industry slot cap, no overall holding count: every sizeable
    core member is held), fixed at 500 by every variant below, carrying no meaning beyond
    ``FactorParams``'s own bookkeeping (M0563's exact convention).
    """

    inner: FactorParams
    sectors: int = 3
    tilt: float = 0.0
    pick: str = "momentum"
    cap: float | None = 0.10
    seed: int = 1
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if isinstance(self.sectors, bool) or not isinstance(self.sectors, int):
            raise TypeError(f"sectors must be an int, got {type(self.sectors).__name__}")
        if not 1 <= self.sectors <= 12:
            raise ValueError(f"sectors must be in 1..12, got {self.sectors}")
        if isinstance(self.tilt, bool) or not isinstance(self.tilt, (int, float)):
            raise TypeError(f"tilt must be a number, got {type(self.tilt).__name__}")
        if self.tilt < 0.0:
            raise ValueError(f"tilt must be >= 0, got {self.tilt}")
        if self.pick not in PICKS:
            raise ValueError(f"pick must be one of {PICKS}, got {self.pick!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        if self.cap is not None:
            if isinstance(self.cap, bool) or not isinstance(self.cap, (int, float)):
                raise TypeError(f"cap must be a number or None, got {type(self.cap).__name__}")
            if not 0.0 < float(self.cap) <= 1.0:
                raise ValueError(f"cap must lie in (0, 1], got {self.cap}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"sectors": str(self.sectors), "tilt": repr(float(self.tilt)), "pick": self.pick,
               "seed": str(self.seed), "cap": "none" if self.cap is None else repr(float(self.cap)),
               "market": self.market, "min_members": str(MIN_MEMBERS),
               "taxonomy": "ff12-edgar-sic", "trade_value_n": str(TRADE_VALUE_N)}
        if self.pick == "hash":
            out["hash"] = "blake2b-8"
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> CoreTiltParams:
    if not isinstance(params, CoreTiltParams):
        raise TypeError(f"params must be CoreTiltParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the signal


def _core_weights(prepared: CapIndustryPrepared, rows: list[FactorRow], data_date: date,
                   p: CoreTiltParams) -> dict[str, float]:
    """Every sizeable member of every ranked industry, value-weighted, with the chosen industries'
    members overweighted by ``(1 + p.tilt)`` before renormalizing. Pre-ceiling."""
    by_ind: dict[str, list[FactorRow]] = {}
    for r in rows:
        if r.symbol in EXCLUDED or r.symbol == p.market:
            continue
        ind = sector_of(r.symbol, data_date)
        if ind is None:
            continue
        by_ind.setdefault(ind, []).append(r)
    eligible = [ind for ind, rs in by_ind.items() if len(rs) >= MIN_MEMBERS]
    if not eligible:
        return {}
    chosen: set[str] = set()
    if p.tilt > 0.0:
        if p.pick == "momentum":
            strength = [(-sum(r.momentum for r in by_ind[ind]) / len(by_ind[ind]), ind) for ind in eligible]
            chosen = {ind for _, ind in sorted(strength)[: p.sectors]}
        else:
            chosen = set(sorted(eligible, key=lambda ind: (draw_industry(p.seed, ind, data_date), ind))[: p.sectors])
    mult: dict[str, float] = {}
    universe: set[str] = set()
    for ind in eligible:
        m = (1.0 + p.tilt) if ind in chosen else 1.0
        for r in by_ind[ind]:
            mult[r.symbol] = m
            universe.add(r.symbol)
    pool = sized_pool(prepared, universe, data_date)
    if not pool:
        return {}
    weighted = {s: v * mult.get(s, 1.0) for s, v in pool.items()}
    total = sum(weighted.values())
    if total <= 0.0:
        return {}
    return {s: w / total for s, w in weighted.items()}


# --------------------------------------------------------------------------- the allocator


class CoreTiltAllocator:
    """Market-value-weighted core across every known-industry member, overweighting the
    momentum-ranked industries by ``(1 + tilt)``. No share counts: no size, no targets."""

    id = "M0564"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), TRADE_VALUE_N)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_check(params).market,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: CapIndustryPrepared, members: AbstractSet[str], data_date: date,
              p: CoreTiltParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        if not rows:
            return ()
        raw = _core_weights(prepared, rows, data_date, p)
        if not raw:
            return ()
        out: list[Target] = []
        symbols = sorted(raw)
        w = np.array([raw[s] for s in symbols], dtype=np.float64)
        if p.cap is not None:
            w = _apply_ceiling(w, float(p.cap))
        for s, wt in zip(symbols, w):
            fw = _floor_weight(float(wt))
            if fw is None:
                continue
            t = target_from_close(s, last_close(prepared.history[s], data_date), fw)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no size and no target."""
        _check(params)
        return ()

    def prepare(self, history: Mapping[str, History]) -> CapIndustryPrepared:
        return CapIndustryPrepared(history, prepare_factor(history), None)

    def prepare_market(self, market: Any) -> CapIndustryPrepared:
        if not hasattr(market, "market_value") or len(market.shares) == 0:
            return CapIndustryPrepared(market.history, prepare_factor(market.history), None)
        return CapIndustryPrepared(market.history, prepare_factor(market.history), market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CapIndustryPrepared):
            raise TypeError(f"prepared must be CapIndustryPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


CORETILT = CoreTiltAllocator()

SW = ("SPY", 200)
W6 = FactorParams(rank="momentum", top=500, mom_n=126, mom_skip=21, trend=SW)


def _v(suffix: str, params: CoreTiltParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0564-{suffix}", family="M0564", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CORETILT, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0564",
    name="Industry momentum, diluted into a market-wide core",
    family="stock-industry-momentum",
    source_kind="variation",
    source_ref="M0563",
    parent_id="M0563",
    hypothesis=(
        "M0563 showed that real money picking winning industries by their own momentum, "
        "value-weighted, beats SPY and a blind-industry twin by several points a year, but its "
        "luck score (0.796-0.830 across its momentum-ranked arms) falls under the lab's 0.90 bar, "
        "plausibly because 3-4 concentrated industry bets are punished hardest by a bar calibrated "
        "against this many prior tries. Hypothesis: spreading the same momentum-ranked industry "
        "tilt across a broader base (a market-cap-weighted core across all known-industry members, "
        "with only a modest multiplicative overweight toward the momentum-ranked industries, rather "
        "than full concentration in 3-4 industries) keeps the proven industry-selection edge "
        "(M0563's CAP-T3-W6 beat a blind industry draw by 3.5 points a year of real money) while "
        "cutting the concentration that plausibly drives both the luck-score penalty and the "
        "catastrophic drawdown seen when the 200-day switch is removed (47.3% max drawdown with no "
        "safety switch, M0563-CAP-T3-W6-NOSW). Expect a smaller raw edge over SPY than M0563's "
        "concentrated arms, but a materially higher, possibly eligible, DSR. Three tilt strengths "
        "(25%, 50%, 100% overweight on the top-3 industries) probe whether DSR improves "
        "monotonically with dilution or whether the edge collapses before the luck bar is cleared; "
        "CORE-TILT0 (no industry opinion, plain market-value core) is the no-opinion control for "
        "the whole family on this diluted book shape; CORE-TILT50-RANDOM (the same 50% overweight, "
        "applied to a blind monthly hash draw of 3 industries instead of the momentum ranking) "
        "separates 'does overweighting any handful of industries help' from 'does overweighting "
        "the momentum-ranked ones specifically help'. Success: a tilted arm beats SPY TR on dev "
        "with worst fall <= 25%, PF >= 1.3, a majority of walk-forward folds, a positive lead over "
        "SPY in 2009-2015, a DSR materially above M0563's best (0.830), and beats both CORE-TILT0 "
        "and CORE-TILT50-RANDOM by at least 2 points a year of real money (the momentum-industry "
        "signal, not simply overweighting a handful of names or any blind handful of industries, "
        "must earn its keep after dilution)."
    ),
    expected_failure=(
        "Diluting the same signal across the whole known-industry universe may dilute the EDGE as "
        "much as the risk: the industry tilt could shrink below the 2-point bar over CORE-TILT0, "
        "meaning the momentum-selection skill that was real at full concentration (M0563's 3.5-point "
        "gap) does not survive being spread this thin, and the method proves concentration IS the "
        "edge rather than merely its risk. The DSR could also simply not clear 0.90 even diluted: "
        "M0563's three momentum-ranked arms already clustered at 0.796-0.830 despite very different "
        "concentration (3 vs 4 industries), so the luck bar may be reading something about this "
        "family's effect size relative to the lab's N rather than about concentration specifically, "
        "in which case dilution buys safety without buying DSR. The family's established 2009-2015 "
        "weakness (M0217 traced it to time in cash under the switch, not the industry mix) may "
        "persist unchanged on a diluted book, since the switch and its cash drag are unchanged here. "
        "Finally, a momentum-ranked industry tilt is kin of the test-failed momentum books (hardgate "
        "D14) whatever this method's family is called, and may be refused on kin if ever promoted, "
        "independent of what this run measures."
    ),
    candidates=(
        _v("CORE-TILT0", CoreTiltParams(W6, sectors=3, tilt=0.0, pick="momentum"),
           "Control: plain market-value-weighted core across every known-industry member the "
           "store can size, no industry opinion at all -- the no-opinion arm for whether any "
           "industry tilt helps over simply holding the known universe at its own market weight"),
        _v("CORE-TILT25", CoreTiltParams(W6, sectors=3, tilt=0.25, pick="momentum"),
           "Market-value core, momentum-ranked top-3 industries' members overweighted 1.25x "
           "before renormalizing -- the mildest dilution of M0563's concentrated bet"),
        _v("CORE-TILT50", CoreTiltParams(W6, sectors=3, tilt=0.50, pick="momentum"),
           "Market-value core, momentum-ranked top-3 industries' members overweighted 1.5x"),
        _v("CORE-TILT100", CoreTiltParams(W6, sectors=3, tilt=1.00, pick="momentum"),
           "Market-value core, momentum-ranked top-3 industries' members overweighted 2x -- the "
           "strongest tilt tried, closest in spirit to M0563's full concentration"),
        _v("CORE-TILT50-RANDOM", CoreTiltParams(W6, sectors=3, tilt=0.50, pick="hash"),
           "Control: the same 1.5x overweight as CORE-TILT50, applied to 3 industries drawn by a "
           "fixed monthly hash instead of momentum -- the no-opinion arm for WHICH industries get "
           "the tilt, isolating the momentum-selection signal from the overweighting structure"),
    ),
    seen_keys=(
        "concept:industry-momentum-diluted-core",
        "concept:market-wide-core-momentum-tilt",
        "concept:industry-momentum",
    ),
)
