"""M0252 — Inside the cheapest third: do buybacks tell you anything a low price has not already told you?

Variation of M0248 (the buyback / discount rank-sum ladder). Reserved by Sera batch 20261024-1715
as an ``idea`` row; this file refines it and keeps its id.

Why a double sort. M0248 measured that the buyback ranking and the discount ranking are
near-orthogonal and that averaging their rank fractions earns less than either end, because each
signal's money is in its own tail. On honest data (2009-2015, survivorship-check store) the lead
over SPY rose with the discount weight while the share of the book that was actually buying back
stock fell, and the pure-discount end lost most of its dev-store lead once the dead companies were
restored. That reads as "cheapness earns, the buyback is a bankruptcy screen", but the rank-sum
cannot say whether the buyback carries RETURN information *given* cheapness. A double sort can:
cut the pool on one signal, then rank on the other inside the cut, so both stay in their own tail.

How it chooses, on each monthly check:

    * THE POOL. M0248's: M0227's ``scored_pool`` (all its split, units and one-listing-per-company
      guards) intersected with members that carry a 252-session nearness value.
    * THE BAND. The pool sorted by nearness (close over the highest close of the last 252
      sessions). The cheapest third is the ``len(pool) // 3`` names with the lowest nearness; the
      dearest third the same count with the highest. The cut size is the same for both bands, so
      the two are comparable.
    * THE PICK, inside the band, ``top`` names, equal slots, ties by symbol: the biggest
      share-count shrinkers (``shrink``), the biggest issuers (``issue``), or a monthly-redrawn
      blind hash draw (``random``, M0187's order, the same frame with neither signal).

Arms (all 20 slots, monthly, fractional at Gotrade's real fees on the owner's top-up, none timed,
the same preset M0248 ran on): CHEAP-S, CHEAP-I, CHEAP-R, and the mirror on the dearest third,
RICH-S, RICH-I, RICH-R. The RICH-R arm is the third arm with no opinion in it: the conditional
spread S minus R is read in both bands, so the band effect is separated from the signal effect.

Predictions and the close-out rule are in ``hypothesis`` and ``expected_failure``, written before
any result. Market-aware (``market_fields = ("shares",)``): the history-only path has no share
counts, so by the contract it targets nothing. Pure: reads only bars and counts public on or
before ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0015_52week_high import HIGH_N, nearness
from seer_engine.lab.methods.m0187_placebo_hash_order import draw
from seer_engine.lab.methods.m0227_net_share_shrinkers import (
    DV_N,
    LOOKBACK_DAYS,
    MIN_COUNT_GAP_DAYS,
    IssuancePrepared,
    scored_pool,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 24)

BANDS = ("cheap", "rich")
PICKS = ("shrink", "issue", "random")
BAND_FRACTION = 3  # the band is one third of the pool


@dataclass(frozen=True, slots=True)
class BandParams:
    """``top`` names held; ``band`` the third of the pool they are drawn from (``cheap`` = deepest
    discount from the yearly high, ``rich`` = nearest to it); ``pick`` how they are chosen inside
    the band; ``seed`` the blind draw's seed."""

    top: int
    band: str = "cheap"
    pick: str = "shrink"
    seed: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 200:
            raise ValueError(f"top must be an int in [1, 200], got {self.top!r}")
        if self.band not in BANDS:
            raise ValueError(f"band must be one of {BANDS}, got {self.band!r}")
        if self.pick not in PICKS:
            raise ValueError(f"pick must be one of {PICKS}, got {self.pick!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        if self.pick != "random" and self.seed != 0:
            raise ValueError("seed is for the random (placebo) pick only")

    def as_dict(self) -> dict[str, str]:
        out = {
            "top": str(self.top),
            "band": self.band,
            "pick": self.pick,
            "band_fraction": f"1/{BAND_FRACTION}",
            "band_on": "nearness-ascending",
            "high_n": str(HIGH_N),
            "tiebreak": "symbol",
            "lookback_days": str(LOOKBACK_DAYS),
            "min_count_gap_days": str(MIN_COUNT_GAP_DAYS),
            "dv_n": str(DV_N),
        }
        if self.pick == "random":
            out["seed"] = str(self.seed)
            out["redraw"] = "monthly"
        return out


def _check(params: object) -> BandParams:
    if not isinstance(params, BandParams):
        raise TypeError(f"params must be BandParams, got {type(params).__name__}")
    return params


def band_members(near: Mapping[str, float], band: str) -> list[str]:
    """The cheapest or dearest third of ``near`` by nearness, ties by symbol. The cut is
    ``len // 3`` for both bands so they hold the same number of names."""
    order = sorted(near, key=lambda s: (near[s], s))
    k = len(order) // BAND_FRACTION
    return order[:k] if band == "cheap" else order[len(order) - k:]


class CheapBandAllocator:
    """The ``top`` names inside the cheapest (or dearest) third of M0227's scored pool by nearness
    to the 52-week high, chosen by share-count shrinkage, issuance or a blind draw, equal slots,
    fully invested. No share counts (history-only path): no targets."""

    id = "M0252"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        _check(params)
        return max(DV_N, HIGH_N)

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
             p: BandParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        scored = scored_pool(prepared, members, data_date)
        if not scored:
            return ()
        near: dict[str, float] = {}
        for s in scored:
            v = nearness(prepared.history, s, data_date, HIGH_N)
            if v is not None:
                near[s] = v
        band = band_members(near, p.band)
        if not band:
            return ()
        if p.pick == "shrink":
            order = sorted(band, key=lambda s: (scored[s], s))
        elif p.pick == "issue":
            order = sorted(band, key=lambda s: (-scored[s], s))
        else:
            order = sorted(band, key=lambda s: (draw(p.seed, s, data_date), s))
        w = equal_weight(p.top)
        out: list[Target] = []
        for s in order[: p.top]:
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no signal and no target."""
        return self._run(IssuancePrepared(history, None), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> IssuancePrepared:
        return IssuancePrepared(history, None)

    def prepare_market(self, market: Any) -> IssuancePrepared:
        if not hasattr(market, "shares") or len(market.shares) == 0:
            return IssuancePrepared(market.history, None)
        return IssuancePrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, IssuancePrepared):
            raise TypeError(f"prepared must be IssuancePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


CHEAP_BAND = CheapBandAllocator()


def _v(suffix: str, params: BandParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0252-{suffix}", family="M0252", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CHEAP_BAND, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0252",
    name=(
        "Inside the cheapest third: do buybacks tell you anything a low price has not already "
        "told you?"
    ),
    family="stock-net-share-issuance",
    source_kind="variation",
    source_ref=(
        "variation of M0248 (the buyback / discount rank-sum ladder), grandchild of M0227; "
        "Pontiff & Woodgate (2008) JF 63(2) 921-945, "
        "https://ideas.repec.org/a/bla/jfinan/v63y2008i2p921-945.html; George & Hwang (2004) JF "
        "59(5) doi:10.1111/j.1540-6261.2004.00695.x; placebo draw of M0187"
    ),
    parent_id="M0248",
    hypothesis=(
        "M0248 measured, on both stores, that the buyback and discount rankings are near-orthogonal "
        "(rank correlation -0.09; the pure-buyback and pure-discount 20-name books share 1.1 names "
        "of 20), that averaging their rank fractions earns LESS than either end over the whole "
        "window (10.5%/yr vs 13.3% pure buyback and 19.0% pure discount), and that in 2009-2015 on "
        "the survivorship-check store the lead over SPY rose with the discount weight (+3.5 to "
        "+11.7 points a year) while the share of the book actually buying back stock fell from "
        "100% to 32%. The pure-discount end lost 11.8 points of its dev-store lead when the dead "
        "companies were restored; the equal mixture lost nothing. So cheapness looks like the "
        "engine and the buyback requirement like a bankruptcy screen. Open question: does a "
        "buyback carry RETURN information conditional on cheapness, or only survival information? "
        "Answer it by double sort so both signals stay in their own tail. Cut M0227's scored pool "
        "(its split, units and one-listing-per-company guards, intersected with members carrying "
        "a 252-session nearness value) to its cheapest third by nearness to the yearly high, then "
        "inside that band hold 20 names three ways: the biggest one-year share-count shrinkers "
        "(CHEAP-S), the biggest issuers (CHEAP-I) and a monthly-redrawn blind hash draw (CHEAP-R). "
        "Mirror the cut on the dearest third (RICH-S, RICH-I, RICH-R) so the conditional spread is "
        "read in both bands and the band effect is separated from the signal effect; RICH-R and "
        "CHEAP-R are the arms with no opinion in them. All twenty equal slots, monthly, fractional "
        "at Gotrade's real fees on the owner's top-up (the preset M0248 ran on), none timed. "
        "Published-anomaly note: buybacks (Pontiff-Woodgate 2008) and the 52-week-high effect "
        "(George-Hwang 2004) are both widely known, so any dev edge is likely to have faded. "
        "Predictions written before any result: (a) CHEAP-S beats CHEAP-R by 3+ points a year in "
        "2009-2015 on BOTH stores if buybacks add return information; (b) CHEAP-S beats CHEAP-I by "
        "3+ points, the sharper test because both are cheap; (c) CHEAP-S survives the restoration "
        "of the dead companies far better than CHEAP-I and CHEAP-R (the survival-screen "
        "prediction, which should hold even if (a) and (b) fail); (d) every cheap-band arm falls "
        "past 50% at its worst, because M0248 established the fall is unrelated to the price "
        "filter. Close-out rule: if CHEAP-S, CHEAP-I and CHEAP-R land within 2 points a year of "
        "each other on both stores while (c) still holds, the honest reading is that the "
        "net-share-issuance family is deep value with a bankruptcy screen attached, carries no "
        "return signal of its own, and should be closed; the screen itself becomes the reusable "
        "finding for any cheapness book the lab builds later."
    ),
    expected_failure=(
        "Four ways. (1) The three cheap arms are one book. A third of a pool of roughly 100-250 "
        "members is 30-80 names and the book holds 20 of them, so a large share of any two arms' "
        "picks may overlap, and the spread between them is then draw noise, not signal; the blind "
        "CHEAP-R arm measures how wide that noise is. A spread inside CHEAP-R's own month-to-month "
        "scatter is read as no information. (2) The 2008 fall stays past 50% on every cheap arm, "
        "because cheap financials in 2007 were falling knives and nothing here is timed or "
        "capped; failing the dev drawdown screen is expected and is not itself the verdict. "
        "(3) 2009-2015 fades: both signals are published, and a conclusion read from M0248's "
        "2009-2015 era is a conclusion fitted after the fact, which is why the arms and "
        "predictions are fixed here and no band width or lookback will be tuned afterwards. "
        "(4) The issuers lose for a reason that is not information: on the survivorship-check "
        "store the dead companies are disproportionately heavy issuers, so CHEAP-I may fall "
        "because it holds the companies that died, which is exactly the survival reading the "
        "close-out rule keeps separate from return information. A tweak after the result is a "
        "new method with new trials."
    ),
    candidates=(
        _v("CHEAP-S", BandParams(20, "cheap", "shrink"),
           "The idea: the 20 biggest one-year share-count shrinkers inside the cheapest third"),
        _v("CHEAP-I", BandParams(20, "cheap", "issue"),
           "Sharper control: the 20 biggest issuers inside the same cheapest third"),
        _v("CHEAP-R", BandParams(20, "cheap", "random", seed=1),
           "Placebo: 20 names drawn blind from the cheapest third, neither signal"),
        _v("RICH-S", BandParams(20, "rich", "shrink"),
           "Mirror band: the 20 biggest shrinkers inside the dearest third, nearest the yearly high"),
        _v("RICH-I", BandParams(20, "rich", "issue"),
           "Mirror band: the 20 biggest issuers inside the dearest third"),
        _v("RICH-R", BandParams(20, "rich", "random", seed=1),
           "Mirror placebo: 20 names drawn blind from the dearest third, neither signal"),
    ),
    seen_keys=(
        "concept:buyback-conditional-on-cheapness-double-sort",
        "concept:cheapest-third-buyback-shrinkers-issuers",
    ),
)
