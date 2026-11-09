"""M0531 -- Disprove the dearest-share-price book: HIGH20 against four blind draws and the biggest 20.

Parent: M0383 (the printed share price). Reserved by Sera batch 20261109-0854 as an ``idea`` row;
this file refines it and keeps its id.

M0383-HIGH20 -- the 20 highest *printed* (unadjusted) share prices among point-in-time index
members, behind SPY's 200-day switch -- earned +13.4% a year on the owner's deposits against +7.2%
for SPY and +11.2% for its one blind draw (M0383-BLIND20), DSR 0.976 at N=248. That blind draw was
matched to LOW20's book, not to HIGH20's, and one draw is not a control anyway: 19 blind rules
span 7.5 points a year in this lab. A 2.2-point lead over one draw is unreadable.

This file re-asks the question the way it should have been asked. Same screened pool as M0383
(``eligible_pool``, imported, not copied), same $-price rank, same fractional shares at Gotrade's
real fees, and:

* ``HIGH20`` -- the treatment, re-run under this file's own allocator id (a new digest, so the lab
  accepts it and it records as a book twin of M0383-HIGH20; that is expected and costs no look).
* ``BLIND-A`` .. ``BLIND-D`` -- four fresh blind draws from the same pool, each matched on HIGH20's
  own book size, entry count and churn through ``lab.control_draw.matched_book``, seeds 531-534.
  Four draws give a spread; HIGH20 must beat the spread, not a point.
* ``BIG20`` -- the 20 biggest companies by point-in-time market value in the same pool. Dear
  prices may simply be big companies (SPY's drift is the opponent): if BIG20 matches HIGH20, the
  price number is size wearing a label.

The dead companies are read afterwards with ``lab survivorship M0531`` on the survivorship-check
store; they are not a variant. M0383's ADJLOW20 is a look-ahead diagnostic and is not carried.

Published-anomaly note: Birru & Wang (2016) is recent and the dev window ends in 2015, so a dev
edge here is an edge from before the crowd, and may fade.
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
from seer_engine.lab.methods.m0383_nominal_price_level_tilt import (
    CLASS_DV_N,
    MIN_DOLLAR_VOLUME,
    MIN_PRINTED_PRICE,
    PoolRow,
    PricePrepared,
    eligible_pool,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import DV_N, FactorParams, trend_on

ADDED = date(2026, 11, 9)

SIDES = ("high", "big", "random")


@dataclass(frozen=True, slots=True)
class DearParams:
    """``top`` names held; ``side`` one of :data:`SIDES`; ``seed`` the blind draw's seed; ``trend``
    the switch, (symbol, n) or None."""

    top: int
    side: str = "high"
    seed: int = 0
    trend: tuple[str, int] | None = None

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 200:
            raise ValueError(f"top must be an int in [1, 200], got {self.top!r}")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        FactorParams(rank="momentum", top=self.top, trend=self.trend)  # validates the switch

    def as_dict(self) -> dict[str, str]:
        return {
            "top": str(self.top),
            "side": self.side,
            "seed": str(self.seed),
            "trend": "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}",
            "min_printed_price": str(MIN_PRINTED_PRICE),
            "min_dollar_volume": str(MIN_DOLLAR_VOLUME),
            "dv_n": str(DV_N),
            "class_dv_n": str(CLASS_DV_N),
            "class_rule": "identical-share-count",
            "price_basis": "printed",
        }


def _check(params: object) -> DearParams:
    if not isinstance(params, DearParams):
        raise TypeError(f"params must be DearParams, got {type(params).__name__}")
    return params


def _gate(p: DearParams) -> FactorParams:
    return FactorParams(rank="momentum", top=p.top, trend=p.trend)


def ranked(pool: Mapping[str, PoolRow], top: int, side: str) -> tuple[str, ...]:
    """The ``top`` highest printed prices (``high``) or biggest companies (``big``); ties break on
    the symbol so the book is a pure function of the pool."""
    if side == "high":
        order = sorted(pool, key=lambda s: (-pool[s].printed, s))
    elif side == "big":
        order = sorted(pool, key=lambda s: (-pool[s].cap, s))
    else:
        raise ValueError(f"ranked does not serve side={side!r}")
    return tuple(order[:top])


class _Base:
    market_fields = ("shares",)

    def _inner(self, p: DearParams) -> int:
        return max(DV_N, CLASS_DV_N, 0 if p.trend is None else p.trend[1])

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return ("SPY",) if p.trend is None else tuple(sorted({"SPY", p.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def prepare(self, history: Mapping[str, History]) -> PricePrepared:
        return PricePrepared(history, None)

    def prepare_market(self, market: Any) -> PricePrepared:
        if not hasattr(market, "shares") or not market.shares.has_splits():
            return PricePrepared(market.history, None)
        return PricePrepared(market.history, market)

    @staticmethod
    def _targets(prepared: PricePrepared, names: AbstractSet[str] | list[str] | tuple[str, ...],
                 data_date: date, top: int) -> tuple[Target, ...]:
        w = equal_weight(top)
        out: list[Target] = []
        for s in names:
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)


class DearAllocator(_Base):
    """The ``top`` highest printed prices (``high``) or biggest companies (``big``) of M0383's
    screened pool, equal slots, fully invested; nothing while the switch is off."""

    id = "M0531"

    def lookback(self, params: Any) -> int:
        return self._inner(_check(params))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no splits and no counts, so no printed price and no target."""
        return ()

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, PricePrepared):
            raise TypeError(f"prepared must be PricePrepared, got {type(prepared).__name__}")
        p = _check(params)
        if p.side == "random":
            raise ValueError("DearAllocator does not run side='random'; use BlindAllocator")
        if prepared.market is None or not trend_on(prepared.history, data_date, _gate(p)):
            return ()
        pool = eligible_pool(prepared, members, data_date)
        if not pool:
            return ()
        return self._targets(prepared, ranked(pool, p.top, p.side), data_date, p.top)


class BlindAllocator(_Base):
    """HIGH20's shape with none of its opinion: ``lab.control_draw``'s frame-matched draw from the
    same pool, matched to the ``side="high"`` book's size, entry count and churn."""

    id = "M0531-A1"

    def lookback(self, params: Any) -> int:
        return control_draw.lookback_for(self._inner(_check(params)))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return ()

    def _select(self, prepared: PricePrepared, members: AbstractSet[str], data_date: date,
                p: DearParams) -> tuple[tuple[str, ...], tuple[str, ...]]:
        pool = eligible_pool(prepared, members, data_date)
        if not pool:
            return (), ()
        return tuple(sorted(pool)), ranked(pool, p.top, "high")

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, PricePrepared):
            raise TypeError(f"prepared must be PricePrepared, got {type(prepared).__name__}")
        p = _check(params)
        if p.side != "random":
            raise ValueError(f"the blind draw is a control: side must be 'random', got {p.side!r}")
        if prepared.market is None or not trend_on(prepared.history, data_date, _gate(p)):
            return ()
        names = control_draw.matched_book(
            lambda d: self._select(prepared, members, d, p),
            data_date, held, tag="M0531", seed=p.seed,
        )
        return self._targets(prepared, names, data_date, p.top)


DEAR = DearAllocator()
BLIND = BlindAllocator()
SW = ("SPY", 200)


def _v(suffix: str, allocator: Any, params: DearParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0531-{suffix}", family="M0531", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


def _blind(letter: str, seed: int) -> Candidate:
    return _v(f"BLIND-{letter}", BLIND, DearParams(top=20, side="random", seed=seed, trend=SW),
              f"Blind draw {letter} (seed {seed}): the same pool, HIGH20's own size, entry count "
              "and churn, none of its names.")


METHOD = Method(
    id="M0531",
    name="Disprove the dearest-share-price book: the 20 highest printed prices against four blind "
         "draws, a size-matched control and the dead companies",
    family="stock-nominal-price-level",
    source_kind="variation",
    source_ref=(
        'Birru & Wang (2016), "Nominal Price Illusion", Journal of Financial and Quantitative '
        "Analysis; parent M0383"
    ),
    parent_id="M0383",
    hypothesis=(
        "M0383-HIGH20 (the 20 highest printed, unadjusted share prices among point-in-time index "
        "members, behind SPY's 200-day switch) earned +13.4% a year on the owner's deposits "
        "against +7.2% for SPY and +11.2% for its one blind draw, DSR 0.976 at N=248 (recorded "
        "figures, to be re-read before any is quoted). One blind draw is not a control: 19 blind "
        "rules span 7.5 points a year in this lab, so a 2.2-point lead over one draw is "
        "unreadable, and that draw was matched to LOW20's book, not HIGH20's. This method re-runs "
        "HIGH20 (same rule, fractional shares at Gotrade's real fees) under its own allocator id "
        "-- a book twin of M0383-HIGH20, expected and free -- beside four fresh blind draws "
        "matched on HIGH20's own size, entry count and churn (seeds 531-534), and BIG20, the 20 "
        "biggest companies by point-in-time market value from the same pool, because dear prices "
        "may just be big companies. Predicted before any result: HIGH20 reproduces M0383's "
        "recorded book; its lead over the four draws' mean is real but smaller than the 2.2 "
        "points, and BIG20 reproduces most of it, because the dearest prices are the big "
        "compounders. The survivorship-check store is read afterwards with lab survivorship, not "
        "as a variant. M0383's ADJLOW20 is a look-ahead diagnostic and is not carried. Published "
        "2016, so a dev edge is from before the crowd and may fade."
    ),
    expected_failure=(
        "HIGH20 sits inside the four draws' spread, or BIG20 matches it. Second: the edge is all "
        "pre-2009 and 2009-2015 says no. Third: the survivorship-check store (dead companies "
        "restored) shrinks it, since the dearest prices belong to survivors."
    ),
    candidates=(
        _v("HIGH20", DEAR, DearParams(top=20, side="high", trend=SW),
           "The treatment: the 20 highest printed prices in the screened pool, behind the switch."),
        _blind("A", 531),
        _blind("B", 532),
        _blind("C", 533),
        _blind("D", 534),
        _v("BIG20", DEAR, DearParams(top=20, side="big", trend=SW),
           "The size control: the 20 biggest companies by market value in the same pool."),
    ),
    seen_keys=(
        "concept:nominal-price-level-disproof",
        "concept:dearest-price-vs-four-blind-draws",
        "concept:dearest-price-vs-size-control",
    ),
)
