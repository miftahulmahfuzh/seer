"""M0239 — Buyback shrinkers with a cap on how much of the book sits in one industry at once.

Source: variation of M0230 (itself a variation of M0227); Pontiff & Woodgate (2008), "Share
Issuance and Cross-Sectional Returns", Journal of Finance 63(2) 921-945. Reserved by Sera batch
sera-20261031-1634 as an ``idea`` row; this file refines it and keeps its id.

Why this shape. M0230 showed the buyback book's one fault is the 2008 fall (about 55-59%), and that
no outside fix works: half the account in SPY barely moved it because SPY fell 55% in the same
months, and the 200-day switch that does fix it costs the 2009-2015 years and the walk-forward
folds. So this attacks the fall inside the pick. A screen that ranks only on share-count change can
load one industry (banks buying back stock just before 2008) at exactly the wrong moment. The
book here is M0227's S20 verbatim -- same scored pool, same 20 equal slots, monthly, fractional,
Gotrade's real fees -- with one addition: ``sectors.select_capped`` walks the shrinker ranking and
skips a name whose Fama-French 12 industry already holds ``cap`` names. Overflow goes to the next
best shrinker outside that industry. The cap is never relaxed: a slot the ranking cannot fill under
the cap stays in cash, which can only make the book more spread, never less.

Arms (cap as a share of the 20 slots): CAP20 = 4 names, CAP30 = 6, CAP40 = 8. UNCAP is the cap
switched off (cap 20) on the same ``-tband`` preset, so the cap is the only difference between it
and the others (M0227-S20 itself ran on the plain preset). It is also the third arm with no opinion
in it: the always-invested, never-capped book against which the price of acting on the cap is
read. PLC20 and PLC30 cap the same ranking on a **fake industry label**: each symbol takes the real
label of another symbol chosen by a date-free blake2b hash over the sector map's labelled symbols,
so the fake groups have the real groups' sizes in expectation but know nothing about the business.
CAP beating PLC says the gain came from avoiding the banks and not from holding a wider book.

Sector labels are EDGAR's latest SIC per filer mapped to FF12 (``seer_engine.sectors``): not
point-in-time for a company that changed trade, so it can blur the cap but reads no prices and
cannot leak the future. Every unlabelled name shares one capped ``Unknown`` bucket. The rules are
``monthly-hold-frac-gotrade-tband`` (the band against each holding's own 5% slot, as M0230 chose
for comparability with M0227).

Market-aware (``market_fields = ("shares",)``): no share counts means no pool and no target.
Pure: reads only bars and share counts public on or before ``data_date``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Any

from seer_engine import sectors
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0227_net_share_shrinkers import (
    ISSUANCE,
    IssuanceParams,
    IssuancePrepared,
    scored_pool,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 31)
TOP = 20
LABEL_DATE = date(2010, 1, 4)  # the date at which the fake labels borrow real ones: fixed, not tuned
LABELS = ("real", "fake")


@lru_cache(maxsize=1)
def sector_map() -> sectors.SectorMap:
    return sectors.load()


@lru_cache(maxsize=1)
def _labelled() -> tuple[tuple[str, str], ...]:
    """Every symbol the map labels on LABEL_DATE, sorted, with its real FF12 code."""
    m = sector_map()
    out = []
    for s in sorted(m.index):
        lab = m.sector_of(s, LABEL_DATE)
        if lab:
            out.append((s, lab))
    return tuple(out)


def _h(seed: int, symbol: str) -> int:
    return int.from_bytes(hashlib.blake2b(f"{seed}|{symbol}".encode(), digest_size=8).digest(), "big")


def fake_label(symbol: str, seed: int) -> str:
    """A hash-drawn label with the real labels' sizes in expectation, constant over time."""
    pool = _labelled()
    return pool[_h(seed, symbol) % len(pool)][1]


@dataclass(frozen=True, slots=True)
class CapParams:
    """``cap`` the most names one industry may hold among ``TOP`` slots; ``labels`` ``real`` or
    ``fake`` (the hash-drawn placebo, ``seed``)."""

    cap: int
    labels: str = "real"
    seed: int = 1

    def __post_init__(self) -> None:
        for name in ("cap", "seed"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if not 1 <= self.cap <= TOP:
            raise ValueError(f"cap must be in [1, {TOP}], got {self.cap}")
        if self.labels not in LABELS:
            raise ValueError(f"labels must be one of {LABELS}, got {self.labels!r}")

    def as_dict(self) -> dict[str, str]:
        return {"cap": str(self.cap), "top": str(TOP), "labels": self.labels,
                "seed": str(self.seed), "sectors": "ff12-edgar-latest-sic-unknown-shared",
                "fake_labels_on": LABEL_DATE.isoformat(),
                **{f"sleeve.{k}": v for k, v in IssuanceParams(TOP).as_dict().items()}}


def _check(params: object) -> CapParams:
    if not isinstance(params, CapParams):
        raise TypeError(f"params must be CapParams, got {type(params).__name__}")
    return params


def picks(prepared: IssuancePrepared, members: AbstractSet[str], data_date: date,
          p: CapParams) -> list[str]:
    """M0227's shrinker order over the scored pool, walked under the industry cap."""
    pool = scored_pool(prepared, members, data_date)
    if not pool:
        return []
    order = sorted(pool, key=lambda k: (pool[k], k))
    if p.labels == "real":
        sector_of = sector_map().sector_of
    else:
        def sector_of(s: str, on: date) -> str | None:
            return fake_label(s, p.seed)
    return sectors.select_capped(order, data_date, TOP, p.cap, sector_of)


class CappedShrinkAllocator:
    id = "M0239"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        _check(params)
        return ISSUANCE.lookback(IssuanceParams(TOP))

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: IssuancePrepared, members: AbstractSet[str], data_date: date,
             p: CapParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        w = equal_weight(TOP)
        out: list[Target] = []
        for s in picks(prepared, members, data_date, p):
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no pool and no target."""
        return self._run(IssuancePrepared(history, None), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> IssuancePrepared:
        return ISSUANCE.prepare(history)

    def prepare_market(self, market: Any) -> IssuancePrepared:
        return ISSUANCE.prepare_market(market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, IssuancePrepared):
            raise TypeError(f"prepared must be IssuancePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


CAPPED = CappedShrinkAllocator()


def _v(suffix: str, params: CapParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0239-{suffix}", family="M0239", rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
                     allocator=CAPPED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0239",
    name=(
        "Buyback shrinkers with a cap on how much of the book sits in one industry at once"
    ),
    family="stock-net-share-issuance",
    source_kind="variation",
    source_ref=(
        "variation of M0230 and M0227; Pontiff & Woodgate (2008) JF 63(2) 921-945, "
        "https://ideas.repec.org/a/bla/jfinan/v63y2008i2p921-945.html; industry cap as in "
        "M0213 and M0214"
    ),
    parent_id="M0230",
    hypothesis=(
        "Buyback anomaly published 2008. M0230 isolated the problem: the shrinker book earns its "
        "keep in the modern era but is killed by a roughly 55-59% fall in 2008, and neither a SPY "
        "core nor the 200-day switch fixes it without costing the 2009-2015 years or the folds. "
        "So attack the fall inside the pick. Mechanism: concentration, not timing. In 2007-08 the "
        "heaviest buyers of their own stock were banks buying back shares just before they "
        "collapsed, so a ranking on share-count change alone loads one industry at the worst "
        "moment. Book: M0227-S20 verbatim (20 equal slots, monthly, fractional, Gotrade real fees, "
        "owner's top-up, no switch, on the tband preset) with no more than a fixed number of names "
        "in any one Fama-French 12 industry on any decision day, overflow going to the next-best "
        "shrinkers outside it, an unfilled slot staying in cash. Arms: CAP20 (4 names per "
        "industry), CAP30 (6), CAP40 (8), UNCAP (no cap, same preset: the always-invested "
        "no-opinion control, so the cap is the only difference), PLC20 and PLC30 (the 4 and 6 "
        "caps on a hash-assigned fake industry label with the real groups' sizes in expectation, "
        "to separate the cap from the act of spreading out). Predictions written before any "
        "result. (1) CAP20 and CAP30 cut the 2008 fall by 10-20 points from UNCAP's, to roughly "
        "40-48%. (2) They cost under one point a year of return against UNCAP. (3) They keep a "
        "positive 2009-2015 edge over total-return SPY. (4) They beat PLC20 and PLC30, which says "
        "the gain came from avoiding the banks and not from a wider book. Industry labels are "
        "EDGAR's latest SIC mapped to FF12, so a company that changed trade carries its end "
        "state: the cap is blurred, not leaked."
    ),
    expected_failure=(
        "Three ways. (1) Still over the 20% bar even at the 20% cap: 2008 was a fall in "
        "everything and a book fully in stocks fell with it whatever it owned, so the fall moves "
        "a few points and not twenty. This is the most likely outcome and is pre-registered. "
        "(2) The cap costs more return than it saves fall, because the top shrinkers cluster in "
        "one industry for a good reason (M0213 lost 1.1 points a year to a sector cap and M0214 "
        "half a point). (3) The fake-label placebo matches the real cap, meaning the cap is just "
        "width and the width findings already cover it. Also: published anomalies fade, and the "
        "dev window straddles publication. None of these is a reason to tune the cap or the "
        "label afterwards."
    ),
    candidates=(
        _v("CAP20", CapParams(4), "At most 4 of 20 names (20%) in any one industry"),
        _v("CAP30", CapParams(6), "At most 6 of 20 names (30%) in any one industry"),
        _v("CAP40", CapParams(8), "At most 8 of 20 names (40%) in any one industry"),
        _v("UNCAP", CapParams(20), "No cap: M0227-S20's book on the tband preset, the control"),
        _v("PLC20", CapParams(4, labels="fake"), "Placebo: 4-per-group cap on hash-drawn fake labels"),
        _v("PLC30", CapParams(6, labels="fake"), "Placebo: 6-per-group cap on hash-drawn fake labels"),
    ),
    seen_keys=(
        "concept:net-share-issuance",
        "concept:buyback-shrinkers",
        "concept:industry-capped-shrinkers",
    ),
)
