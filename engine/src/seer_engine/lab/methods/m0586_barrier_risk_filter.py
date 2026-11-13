"""M0586 -- Round-number barrier as a risk filter behind the trend switch, not a side bet.

Source: variation of M0583 (Donaldson & Kim, "Round Numbers and Security Returns"; Shiller 2015).
Reserved by Sera batch 20261113-1055 as an ``idea`` row; this file refines it and keeps its id.

Idea. M0583 read proximity to a round-dollar barrier as a *direction* (just cleared vs just
under) and found the reverse of the anchoring story, with only a thin edge over a blind draw
and a 60%+ fall in every ungated arm. This file asks the narrower question the idea row named:
is the barrier a *volatility* clue? A stock whose printed price sits right on a psychological
level may be choppy as orders pile up around it; one in the middle of its step has no such
magnet. So the treatment holds the names FAR from any barrier (largest distance to the nearest
round number) and its mirror holds the names closest to one (either side), both behind the
lab's existing SPY 200-day switch, which M0133 showed is what keeps an otherwise 60-70% fall
inside the screen.

How. Same pool, barrier scheme and printed-price basis as M0583 (imported, not copied:
``eligible_pool``). ``abs(gap_frac)`` is the distance to the barrier as a fraction of its step,
in [0, 0.5]. ``far`` takes the 20 largest, ``near`` the 20 smallest. ``gate`` holds cash on any
day SPY is not strictly above its 200-day average (``f_factor.trend_on``, as M0084/M0133).

Arms (fractional shares at Gotrade's real fees, monthly, equal slots):

* FAR20 -- far from a barrier, gated. The treatment.
* NEAR20 -- closest to a barrier, gated. The mirror: shows whether distance is a real signal.
* BLIND20 -- the no-opinion arm, a hash-drawn placebo (``control_draw`` matched draw) from the
  identical pool, matched to FAR20's own book size, entries and turnover, behind the same gate.
* FAR20-NOGATE -- FAR20 with the switch removed: the other half of the 2x2, so the cost and
  worth of the switch can be read separately from the screen's. Control: M0583-BLIND20 (trial
  2092, same pool, ungated blind draw of ABOVE20's shape) is cited as the ungated blind book,
  not re-run.

Pure: reads only bars and splits public on or before ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0583_round_number_barrier import (
    BarrierPrepared,
    PoolRow,
    eligible_pool,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import DV_N, FactorParams, trend_on

ADDED = date(2026, 11, 13)

SMA_N = 200
GATE = FactorParams(rank="momentum", trend=("SPY", SMA_N))
SIDES = ("far", "near", "random")


@dataclass(frozen=True, slots=True)
class FilterParams:
    """``top`` names; ``side`` far/near/random; ``gated`` whether the SPY 200-day switch applies."""

    top: int
    side: str = "far"
    gated: bool = True
    seed: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 200:
            raise ValueError(f"top must be an int in [1, 200], got {self.top!r}")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if not isinstance(self.gated, bool):
            raise ValueError(f"gated must be a bool, got {self.gated!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")

    def as_dict(self) -> dict[str, str]:
        return {
            "top": str(self.top), "side": self.side, "gated": str(self.gated), "seed": str(self.seed),
            "gate": f"SPY>SMA{SMA_N}", "barrier_scheme": "dollar-below-100-ten-above",
            "price_basis": "printed", "distance": "abs(gap_frac)",
        }


def _check(params: object) -> FilterParams:
    if not isinstance(params, FilterParams):
        raise TypeError(f"params must be FilterParams, got {type(params).__name__}")
    return params


def ranked_book(pool: Mapping[str, PoolRow], top: int, side: str) -> tuple[str, ...]:
    """``top`` names by distance to the barrier: ``far`` the largest, ``near`` the smallest.
    Ties break on the symbol, so the book never depends on dict order."""
    if side == "far":
        order = sorted(pool, key=lambda s: (-abs(pool[s].gap_frac), s))
    elif side == "near":
        order = sorted(pool, key=lambda s: (abs(pool[s].gap_frac), s))
    else:
        raise ValueError(f"ranked_book does not serve side={side!r}")
    return tuple(order[:top])


class _Base:
    market_fields = ("shares",)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def prepare(self, history: Mapping[str, History]) -> BarrierPrepared:
        return BarrierPrepared(history, None)

    def prepare_market(self, market: Any) -> BarrierPrepared:
        if not hasattr(market, "shares") or not market.shares.has_splits():
            return BarrierPrepared(market.history, None)
        return BarrierPrepared(market.history, market)

    def _names(self, prepared: BarrierPrepared, members: AbstractSet[str], data_date: date,
               held: frozenset[str], p: FilterParams) -> tuple[str, ...]:
        raise NotImplementedError

    def _run(self, prepared: BarrierPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: FilterParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if p.gated and not trend_on(prepared.history, data_date, GATE):
            return ()
        w = equal_weight(p.top)
        out: list[Target] = []
        for s in self._names(prepared, members, data_date, held, p):
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no splits, so no printed price and no target."""
        return self._run(BarrierPrepared(history, None), members, data_date, held, _check(params))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, BarrierPrepared):
            raise TypeError(f"prepared must be BarrierPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


class FilterAllocator(_Base):
    """far/near from the barrier, equal slots, behind the SPY 200-day switch when ``gated``."""

    id = "M0586"

    def lookback(self, params: Any) -> int:
        _check(params)
        return max(DV_N, SMA_N)

    def _names(self, prepared, members, data_date, held, p):
        if p.side == "random":
            raise ValueError("FilterAllocator does not run side='random'; use MatchedDrawAllocator")
        pool = eligible_pool(prepared, members, data_date)
        return ranked_book(pool, p.top, p.side) if pool else ()


class MatchedDrawAllocator(_Base):
    """FAR20's shape with none of its opinion: a frame-matched hash-drawn placebo from the same
    pool. The controlled book is read without the gate (the gate is applied to today's decision
    in ``_run``), so the draw's turnover is the screen's, not the switch's."""

    id = "M0586-A1"

    def lookback(self, params: Any) -> int:
        _check(params)
        return control_draw.lookback_for(max(DV_N, SMA_N))

    def _select(self, prepared, members, data_date, p):
        pool = eligible_pool(prepared, members, data_date)
        if not pool:
            return (), ()
        return tuple(sorted(pool)), ranked_book(pool, p.top, "far")

    def _names(self, prepared, members, data_date, held, p):
        return tuple(control_draw.matched_book(
            lambda d: self._select(prepared, members, d, p),
            data_date, held, tag="M0586", seed=p.seed,
        ))


FILTER = FilterAllocator()
MATCHED = MatchedDrawAllocator()


def _v(suffix: str, alloc: Any, params: FilterParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0586-{suffix}", family="M0586", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=alloc, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0586",
    name="Round-number barrier as a risk filter behind the trend switch, not a side bet",
    family="stock-round-number-barrier",
    source_kind="variation",
    source_ref="M0583 (Donaldson & Kim, Round Numbers and Security Returns; Shiller 2015)",
    parent_id="M0583",
    hypothesis=(
        "M0583 (round-number barrier as a direction; published 2015-era anchoring literature) "
        "found just-under beat just-cleared, the reverse of prediction, a 1-2.5 point a year edge "
        "over a blind draw, and 60-65% falls in all three ungated arms (trials 2090, 2091, 2092). "
        "Here the barrier is read as a volatility clue: names far from any round-dollar level "
        "(largest abs gap to the nearest round number as a fraction of its step, printed price, "
        "M0583's pool and scheme) should be calmer than names sitting on one, and behind the SPY "
        "200-day switch (M0133's 200-day gate) the book should keep its worst fall inside the "
        "lab's screen. FAR20 is the treatment, NEAR20 its mirror, BLIND20 a hash-drawn placebo "
        "matched to FAR20's size and turnover behind the same gate (the no-opinion arm), and "
        "FAR20-NOGATE removes the switch to give the 2x2 with the gate on and off. Control: "
        "the ungated blind book is M0583-BLIND20 (trial 2092, same pool, matched to ABOVE20's "
        "shape rather than FAR20's) and is cited, not re-run. 20 names, fractional shares at "
        "Gotrade's real fees, monthly, since the book is wide."
    ),
    expected_failure=(
        "(1) The gate does all the work: FAR20, NEAR20 and BLIND20 land inside one another's "
        "width (blind rules span several points a year here), so distance to a barrier carries "
        "no volatility information and the verdict is that the switch, not the screen, is the "
        "result. (2) The switch costs it: M0084 found the switch lost 6-11 points a year to SPY "
        "over 2009-2015, so even a calmer book is likely to trail SPY in the best-covered years. "
        "(3) Far-from-barrier is a price-level proxy: a $1 step below $100 is a wide band, so "
        "FAR20 may just tilt to a price range rather than anything about psychology. (4) A "
        "published anomaly that faded: the dev window ends in 2015."
    ),
    candidates=(
        _v("FAR20", FILTER, FilterParams(top=20, side="far", gated=True),
           "The treatment: 20 names farthest from a round-dollar barrier, behind the 200-day switch."),
        _v("NEAR20", FILTER, FilterParams(top=20, side="near", gated=True),
           "The mirror: 20 names closest to a barrier, same gate, so a real signal shows as a spread."),
        _v("BLIND20", MATCHED, FilterParams(top=20, side="random", gated=True, seed=586),
           "Control: a hash-drawn placebo from the identical pool matched to FAR20's size, entries "
           "and turnover, behind the same gate; the no-opinion arm that prices acting."),
        _v("FAR20-NOGATE", FILTER, FilterParams(top=20, side="far", gated=False),
           "The switch removed: FAR20 never stepping aside, the other half of the 2x2."),
    ),
    seen_keys=(
        "concept:round-number-barrier-risk-filter",
        "concept:round-number-barrier",
    ),
)
