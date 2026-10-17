"""M0221 — The honest yardstick: the biggest index members held in proportion to their real market value.

Source: general knowledge (how the S&P 500 itself is built: members weighted by market value);
reserved by Sera batch 20261018-0517 for the owner's theme "books shaped like the market"; insight
391; M0122 (trading value as the size stand-in, which cost return on all three books it re-sized)
and M0198 (the placebo re-sized by trading value). Not a stock-picking idea. A yardstick.

Why it exists. Every book in this lab holds equal slots among index members, and SPY does not: it
holds each company in proportion to its market value. M0122 and M0198 could only approximate that
shape with trading value, because the store had no sound company size. Since 2026-10-17 it does
(``Market.market_value``: shares outstanding as filed by that day times the close as it printed).
So build the plainest market-shaped book there is and ask two things. (1) Does a cap-weighted
top-N of the store's own members track SPY, including 2009-2015? If it does, the store can price
the market's shape and the lab's long 2009-2015 shortfall is a property of equal slots and the
200-day switch, not of the data. If even this drifts from SPY, the drift is the store's coverage
(dead companies missing, share counts unknown) and every "beats SPY" in the lab carries that
error. (2) What does the switch cost a book shaped like the market?

How. On each monthly check, among the day's index members with a bar dated ``data_date`` and a
known market value, collapse share classes of one company (GOOG/GOOGL, FOX/FOXA, NWS/NWSA: the
store answers the whole company's count for each class, so two members with the identical share
count are one company; the class with the larger 60-session trading value stays), rank by market
value and hold the top ``top``. ``weighting="cap"``: weights proportional to market value, no name
above ``cap`` of the account, the excess spread over the names under it (M0034's water-filling);
fully invested, nothing parked. ``weighting="equal"``: the same names at 1/top each (the contrast
arm: the lab's usual shape on the market's biggest names). ``pick="random"``: the control of the
same shape -- ``top`` names drawn from the same eligible pool in a fixed hash order of
(seed, symbol) that knows nothing about prices or size, then cap-weighted exactly like the real
arm. The hash order does not change from month to month, so the control's book changes only when
membership or coverage does, as the real arm's does; it pays for no churn the real one does not.

The switch: ``trend=("SPY", 200)`` holds nothing while SPY closes at or below its 200-day average
(``f_factor.trend_on``); every variant sets it explicitly.

Assumptions written before any result. The 10% ceiling is the one pre-registered here; it binds
on top-20 in the late 1990s and 2012-2015 (GE, Microsoft, Apple, Exxon each near or above 10% of
a 20-name book) and almost never on top-50 or top-100. The weight is recomputed every month, so
a held name drifts with its price and the book engine's 1%-of-equity band decides whether the
drift trades; between months a cap-weighted book drifts toward its own cap weights for free.
Members with no known market value (about 44% of dev member-days, mostly names with no bars at
all) cannot be held by any arm, so the "biggest N" is the biggest N the store can see. BRK.B's
2010-11 figures count class A shares only and Alphabet goes unknown from 2014 (it files its count
per class), so both read too small or not at all; that is part of what this yardstick measures.

Market-aware (``market_fields = ("shares",)``): the history-only path has no share counts, so by
the contract it targets nothing. Rules are ``monthly-hold-frac-gotrade``: fractional shares at
Gotrade's real fees, asked monthly. Pure: reads only bars and share counts dated <= ``data_date``.
"""

from __future__ import annotations

import hashlib
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
from seer_engine.lab.methods.m0198_size_weighted_placebo import trading_value
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED, FactorParams, trend_on

ADDED = date(2026, 10, 18)
DV_N = 60  # sessions of trading value that decide which share class of a company stays
WEIGHTINGS = ("cap", "equal")
PICKS = ("size", "random")


@dataclass(frozen=True, slots=True)
class CapTopParams:
    """``top`` names held; ``weighting`` cap or equal; ``cap`` the per-name ceiling (cap weighting
    only); ``pick`` size (the biggest) or random (the control); ``seed`` the control's hash seed;
    ``trend`` the switch, (symbol, n) or None, set by every variant."""

    top: int
    weighting: str = "cap"
    cap: float | None = 0.10
    pick: str = "size"
    seed: int = 0
    trend: tuple[str, int] | None = None

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 500:
            raise ValueError(f"top must be an int in [1, 500], got {self.top!r}")
        if self.weighting not in WEIGHTINGS:
            raise ValueError(f"weighting must be one of {WEIGHTINGS}, got {self.weighting!r}")
        if self.pick not in PICKS:
            raise ValueError(f"pick must be one of {PICKS}, got {self.pick!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        if self.cap is not None:
            if self.weighting == "equal":
                raise ValueError("cap is meaningless on equal weights")
            if isinstance(self.cap, bool) or not isinstance(self.cap, (int, float)):
                raise TypeError(f"cap must be a number or None, got {type(self.cap).__name__}")
            if not 1.0 / self.top <= float(self.cap) <= 1.0:
                raise ValueError(f"cap must lie in [1/top, 1], got {self.cap}")
        FactorParams(rank="momentum", top=self.top, trend=self.trend)  # validates the switch

    def as_dict(self) -> dict[str, str]:
        return {"top": str(self.top), "weighting": self.weighting,
                "cap": "none" if self.cap is None else repr(float(self.cap)),
                "pick": self.pick, "seed": str(self.seed),
                "trend": "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}",
                "dv_n": str(DV_N), "class_rule": "identical-share-count"}


def _check(params: object) -> CapTopParams:
    if not isinstance(params, CapTopParams):
        raise TypeError(f"params must be CapTopParams, got {type(params).__name__}")
    return params


def _gate(p: CapTopParams) -> FactorParams:
    return FactorParams(rank="momentum", top=p.top, trend=p.trend)


def draw(seed: int, symbol: str) -> int:
    """The control's fixed order: a hash of (seed, symbol) that knows nothing about the market."""
    key = f"M0221|{seed}|{symbol}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")


@dataclass(frozen=True, slots=True, eq=False)
class CapTopPrepared:
    history: Mapping[str, History]
    market: Any  # the Market (share counts and market value), or None on the history-only path


def sized_pool(prepared: CapTopPrepared, members: AbstractSet[str], data_date: date) -> dict[str, float]:
    """Market value of every member that can be held on ``data_date``, one share class per company."""
    mk = prepared.market
    if mk is None:
        return {}
    by_count: dict[float, tuple[float, str, float]] = {}
    for s in sorted(members):
        if s in EXCLUDED:
            continue
        h = prepared.history.get(s)
        if h is None or h.index_of(data_date) is None:
            continue
        v = mk.market_value(s, data_date)
        n = mk.shares_on(s, data_date)
        if v is None or n is None or not (np.isfinite(v) and v > 0.0):
            continue
        dv = trading_value(h, data_date, DV_N)
        seen = by_count.get(n)
        if seen is None or (dv, s) > (seen[0], seen[1]):
            by_count[n] = (dv, s, v)
    return {s: v for _, s, v in by_count.values()}


def weights(values: list[float], p: CapTopParams) -> list[Decimal | None]:
    """One weight per pick, summing to at most 1."""
    if p.weighting == "equal":
        return [equal_weight(p.top) for _ in values]
    w = np.array(values, dtype=np.float64)
    w = w / float(w.sum())
    if p.cap is not None:
        w = _apply_ceiling(w, max(float(p.cap), 1.0 / len(values)))
    return [_floor_weight(float(x)) for x in w]


class CapTopAllocator:
    """The top-N index members by real market value (or N in a fixed hash order), cap- or
    equal-weighted, fully invested; nothing while the switch, if any, is off. No share counts
    (history-only path): no targets."""

    id = "M0221"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(DV_N, 0 if p.trend is None else p.trend[1])

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return ("SPY",) if p.trend is None else tuple(sorted({"SPY", p.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: CapTopPrepared, members: AbstractSet[str], data_date: date,
             p: CapTopParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, _gate(p)):
            return ()
        pool = sized_pool(prepared, members, data_date)
        if not pool:
            return ()
        if p.pick == "size":
            order = sorted(pool, key=lambda s: (-pool[s], s))
        else:
            order = sorted(pool, key=lambda s: (draw(p.seed, s), s))
        picks = order[: p.top]
        out: list[Target] = []
        for s, w in zip(picks, weights([pool[s] for s in picks], p), strict=True):
            if w is None:
                continue
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no size and no target."""
        return self._run(CapTopPrepared(history, None), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> CapTopPrepared:
        return CapTopPrepared(history, None)

    def prepare_market(self, market: Any) -> CapTopPrepared:
        if not hasattr(market, "market_value") or len(market.shares) == 0:
            return CapTopPrepared(market.history, None)
        return CapTopPrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CapTopPrepared):
            raise TypeError(f"prepared must be CapTopPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


CAPTOP = CapTopAllocator()

SW = ("SPY", 200)


def _v(suffix: str, params: CapTopParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0221-{suffix}", family="M0221", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CAPTOP, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0221",
    name=(
        "The honest yardstick: the biggest index members held in proportion to their real market "
        "value, with and without the 200-day switch"
    ),
    family="market-shape-yardstick",
    source_kind="knowledge",
    source_ref=(
        "S&P 500 cap-weighting; Sera 20261018-0517 owner theme 'books shaped like the market'; "
        "insight 391; M0122 and M0198 (trading value as the size stand-in)"
    ),
    parent_id=None,
    hypothesis=(
        "Not a picker but the yardstick every picker needs. Now that the store carries point-in-time "
        "market value, hold each month the top N index members by real market value (one share "
        "class per company), weighted by market value with no name above 10% of the account, fully "
        "invested, fractional shares at Gotrade's real fees on the owner's monthly top-up. Arms: "
        "C50 (top 50, no switch), C100 (top 100, no switch, the closest to SPY's shape), C20 (top "
        "20, no switch, concentrated), C50-SW (top 50 behind the SPY 200-day switch), E50 (the same "
        "top 50 at equal weight: the lab's usual shape on the biggest names), and R50 (50 members "
        "drawn in a fixed hash order that ignores size and price, cap-weighted: the meaningless "
        "control of the same shape). Predictions, written before any result: C100 and C50 track "
        "total-return SPY within about a point a year over 1996-2015 and within about a point in "
        "2009-2015, with worst falls near SPY's 55% in 2008; C20 trails SPY after 2009 by more, "
        "because the 10% ceiling binds on the giants; C50-SW gives up return after 2009 to whipsaws "
        "but roughly halves the 2008 fall; E50 leads the cap arms before 2009 and trails after; "
        "R50 lands nearer the equal-weight arm than SPY, because without size ranking it holds "
        "mostly mid-sized members. Success is a yardstick that tracks SPY, not a book that beats "
        "it: no arm is expected to pass the gate, and none is for promotion (it would simply be "
        "SPY with fees). Cap weighting is not a published anomaly; it is the market itself."
    ),
    expected_failure=(
        "The store, not the shape. About 44% of dev member-days have no market value (mostly "
        "members with no bars at all, many of them the companies that later died), so the biggest "
        "N is the biggest N the store can see; Berkshire reads too small in 2010-11 and Alphabet "
        "goes unknown from 2014. If C100 drifts from SPY by more than about a point a year -- "
        "above it because the missing names were the losers (survivorship), or below it because "
        "missing giants carried SPY -- the yardstick measures the store's holes and the verdict "
        "must say so; the survivorship-check store re-run then decides which. Second, fees: a "
        "100-name book on a 20M IDR account means slots of about $15 at the start, where Gotrade's "
        "minimum charges bite hardest, so C100 may trail C50 on fees alone in the early years. "
        "Third, the 10% ceiling on C20 moves money from the biggest names to the rest every month "
        "and may trade more than the uncapped arms. Fourth, a 2009-2015 lag on C50 would mean the "
        "lab's measuring frame itself handicaps any member book against SPY, which is worth knowing "
        "even though it is the uncomfortable answer."
    ),
    candidates=(
        _v("C50", CapTopParams(50, trend=None),
           "Top 50 members by market value, cap-weighted with a 10% ceiling, no switch"),
        _v("C100", CapTopParams(100, trend=None),
           "Top 100 members by market value, cap-weighted with a 10% ceiling, no switch"),
        _v("C20", CapTopParams(20, trend=None),
           "Top 20 members by market value, cap-weighted with a 10% ceiling, no switch"),
        _v("C50-SW", CapTopParams(50, trend=SW),
           "Top 50 by market value, cap-weighted, behind the SPY 200-day switch"),
        _v("E50", CapTopParams(50, weighting="equal", cap=None, trend=None),
           "Contrast: the same top 50 by market value at equal weight, no switch"),
        _v("R50", CapTopParams(50, pick="random", seed=1, trend=None),
           "Control: 50 members in a fixed size-blind hash order, cap-weighted, no switch"),
    ),
    seen_keys=(
        "concept:cap-weighted-top-n",
        "concept:market-shape-yardstick-real-cap",
    ),
)
