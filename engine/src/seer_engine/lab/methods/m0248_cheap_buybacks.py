"""M0248 — Cheap buybacks: score a company on how hard it is buying back AND how cheaply.

Variation of M0243 (which filtered the buyback book on nearness to the 52-week high) and
grandchild of M0227 (the buyback book itself). Reserved by Sera batch 20261019-1014 as an ``idea``
row; this file refines it and keeps its id.

Why this shape, and why the previous run points here rather than away. M0243 split M0227's scored
pool into a near half and a far half by nearness to the 52-week high, held the twenty biggest
share-count shrinkers inside each, and kept the discarded half as a mirror. Three things came out
of it that were not known before, and all three were measured, not inferred:

    1. **The buyback signal is informative.** Twenty names drawn blind from the *identical* near
       half, at identical fees, earned +4.4% a year on the owner's deposits where the real picks
       earned +10.4%. That is the strongest control result this family has produced; the frame is
       not what earns.
    2. **The filter is orthogonal to buyback intensity.** The near and far halves shrink their
       share counts at 7.70% and 7.64% a year. Filtering on price does not quietly keep the milder
       shrinkers, which was ``expected_failure`` (3) of M0243 and did not happen.
    3. **The filter removed the half that earns.** The near half led SPY by +0.8 points a year in
       2009-2015 and LOST by 0.9 on the survivorship-check store. The discarded far half led by
       +3.5 and +6.0, against the unfiltered parent's +3.8.

That is the original Pontiff-Woodgate argument turned the right way up. A buyback is informative
because management is spending real money saying the stock is cheap, so the information is in the
*opportunistic* repurchase made well below the yearly high, not in the routine one made at it.
Large US companies now buy back stock quarter after quarter as policy, and that policy half --
exactly the half M0243 kept -- is the uninformative one.

So stop filtering and start scoring. Nothing is thrown away: every member of M0227's scored pool
is ranked twice, and a single combined score decides the book.

How it chooses, on each monthly check:

    * THE POOL. M0227's ``scored_pool`` verbatim -- every index member with a bar dated
      ``data_date`` whose split-adjusted share count can be compared with the count public 365
      days earlier, under all of the parent's pre-registered guards (at least 180 days between the
      two counts; a ratio within 3% of a common split ratio or outside 0.5-3.0 skipped; one listing
      per company, decided by 60-session trading value) -- intersected with the members that carry
      a nearness value (at least 252 closes). Every arm in this method, the placebo included, draws
      from that one pool, so no comparison inside the file is confounded by a different frame.
      Note the 252-bar requirement is what separates the ``B100`` arm below from M0227-S20: it is
      the same ranking on a slightly smaller pool, which is what makes it a *within-frame* control
      rather than a re-run of the parent.
    * THE TWO ORDERS. Order one, buyback intensity: the pool sorted ascending by M0227's issuance
      score (the log of new shares over carried-old), so the biggest shrinker is first. Order two,
      the discount: the pool sorted ascending by M0015's ``nearness`` (close over the highest close
      of the last 252 sessions), so the deepest discount from the yearly high is first. The idea
      row described the second piece as the log discount, ``-log(nearness)``; because the two
      pieces are combined by RANK and not by value, that log is a monotone relabelling of nearness
      and changes no book. Ranking on nearness ascending is written here instead, because it is
      the same thing and one fewer transform to audit.
    * THE SCORE. Each name's position in each order becomes a rank fraction in [0, 1]: position
      divided by (pool size - 1), 0.0 for the best. The combined score is
      ``w * rank_buyback + (1 - w) * rank_discount`` with ``w`` the buyback weight. Summing rank
      fractions rather than raw values is the point of the construction: neither piece's units nor
      its outliers can decide the book, and a company with a thousand-fold filing error (already
      guarded against upstream) could not dominate even if one slipped through.
    * THE PICK. The ``top`` lowest combined scores, ties broken by symbol, equal slots, fully
      invested. ``pick="random"`` instead takes ``top`` names from the identical pool in M0187's
      monthly-redrawn hash order: the same frame, the same fees, no knowledge of either signal.

The ladder. ``w`` runs 100, 75, 50, 25, 0, which is a dose-response ladder in the discount weight
rather than a single idea beside a placebo. The lab's own experience is that a ladder is the
stronger instrument (insight: more of a thing giving monotonically more lead excludes the frame by
construction, where a placebo only excludes one alternative). The two ends are within-frame
controls that the lab has separate readings for: ``B100`` is plain buyback intensity, which is
M0227-S20 on this pool, and ``D100`` is a plain deep-discount book, which the lab has already
rejected as long-term reversal at MAR 0.30 (M0069, M0073).

No timed arm, deliberately. M0227-S20-SW and M0243-NEAR20-SW both already sit dev-eligible behind
the SPY 200-day switch and both are refused by the hard gate at 2 of 4 walk-forward folds, so a
third would teach the lab nothing. More importantly, the walk-forward picker chooses each fold's
variant by MAR, so a braked arm in a method of unbraked arms hijacks the fold record of the whole
method -- which is precisely what M0243's analysis warned against doing again. This method
therefore expects to fail the dev screen on the 2008 fall and says so below. It is run to answer a
question, not to produce an eligible arm: the queued industry cap (M0239) is the separate, already
queued attempt at the fall, and its right test bed is whichever half of this ladder earns.

Window: the parent's, 1997-2015 in effect (a year of share counts must pass first), inside the dev
window ending 2015-10-16.

Market-aware (``market_fields = ("shares",)``): the history-only path has no share counts, so by
the contract it targets nothing. Rules are ``monthly-hold-frac-gotrade``: fractional shares at
Gotrade's real fees, asked monthly, on the owner's monthly top-up -- the same preset M0227, M0230
and M0243 ran on, so the comparison needs no cost translation. Pure: reads only bars and counts
public on or before ``data_date``.
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

ADDED = date(2026, 10, 19)

PICKS = ("combo", "random")


@dataclass(frozen=True, slots=True)
class CheapBuybackParams:
    """``top`` names held; ``w_pct`` the buyback weight in percent (100 = pure buyback intensity,
    0 = pure discount from the yearly high); ``pick`` the combined score or the blind hash draw;
    ``seed`` that draw's seed."""

    top: int
    w_pct: int = 50
    pick: str = "combo"
    seed: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 200:
            raise ValueError(f"top must be an int in [1, 200], got {self.top!r}")
        if isinstance(self.w_pct, bool) or not isinstance(self.w_pct, int) or not 0 <= self.w_pct <= 100:
            raise ValueError(f"w_pct must be an int in [0, 100], got {self.w_pct!r}")
        if self.pick not in PICKS:
            raise ValueError(f"pick must be one of {PICKS}, got {self.pick!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        if self.pick != "random" and self.seed != 0:
            raise ValueError("seed is for the random (placebo) pick only")

    @property
    def w(self) -> float:
        """The buyback weight as a fraction; the discount carries ``1 - w``."""
        return self.w_pct / 100.0

    def as_dict(self) -> dict[str, str]:
        out = {
            "top": str(self.top),
            "w_pct": str(self.w_pct),
            "pick": self.pick,
            "combine": "rank-fraction-sum",
            "discount": "nearness-ascending",
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


def _check(params: object) -> CheapBuybackParams:
    if not isinstance(params, CheapBuybackParams):
        raise TypeError(f"params must be CheapBuybackParams, got {type(params).__name__}")
    return params


def rank_fractions(order: list[str]) -> dict[str, float]:
    """Position in ``order`` mapped to [0, 1]: 0.0 for the first name, 1.0 for the last. A pool of
    one is all zeros, which is the only sensible reading of "best and worst at once"."""
    n = len(order)
    if n <= 1:
        return {s: 0.0 for s in order}
    return {s: i / (n - 1) for i, s in enumerate(order)}


def combined(pool: Mapping[str, float], near: Mapping[str, float],
             p: CheapBuybackParams) -> dict[str, float]:
    """``w * rank(buyback intensity) + (1 - w) * rank(discount)`` for every name in ``pool``, each
    rank a fraction in [0, 1] with 0.0 the biggest shrinker / the deepest discount. Both orders
    break ties by symbol, so the construction is deterministic and signal-blind at the margin."""
    by_shrink = sorted(pool, key=lambda s: (pool[s], s))
    by_discount = sorted(pool, key=lambda s: (near[s], s))
    rs, rd = rank_fractions(by_shrink), rank_fractions(by_discount)
    w = p.w
    return {s: w * rs[s] + (1.0 - w) * rd[s] for s in pool}


class CheapBuybackAllocator:
    """The ``top`` index members with the lowest combined score -- part buyback intensity, part
    discount from the 52-week high, combined as a weighted sum of rank fractions over M0227's
    scored pool -- equal slots, fully invested. No share counts (history-only path): no targets."""

    id = "M0248"
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
             p: CheapBuybackParams) -> tuple[Target, ...]:
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
        pool = {s: scored[s] for s in near}
        if not pool:
            return ()
        if p.pick == "combo":
            score = combined(pool, near, p)
            order = sorted(pool, key=lambda s: (score[s], s))
        else:
            order = sorted(pool, key=lambda s: (draw(p.seed, s, data_date), s))
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


CHEAP_BUYBACK = CheapBuybackAllocator()


def _v(suffix: str, params: CheapBuybackParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0248-{suffix}", family="M0248", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CHEAP_BUYBACK, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0248",
    name=(
        "Cheap buybacks: score a company on how hard it is buying back its stock AND how far below "
        "its yearly high it is buying it"
    ),
    family="stock-net-share-issuance",
    source_kind="variation",
    source_ref=(
        "variation of M0243 (the buyback book filtered near the yearly high), grandchild of M0227; "
        "Pontiff & Woodgate (2008) JF 63(2) 921-945, "
        "https://ideas.repec.org/a/bla/jfinan/v63y2008i2p921-945.html; George & Hwang (2004) JF "
        "59(5) doi:10.1111/j.1540-6261.2004.00695.x; placebo draw of M0187"
    ),
    parent_id="M0243",
    hypothesis=(
        "M0243 established three things by filtering the buyback book on nearness to the 52-week "
        "high and keeping the discarded half as a mirror. (1) The buyback signal is genuinely "
        "informative: twenty names drawn blind from the identical filtered half, at identical "
        "fees, earned +4.4% a year against the real picks' +10.4%, the strongest control result "
        "this family has produced. (2) The filter is orthogonal to buyback intensity, measured: "
        "the near and far halves shrink their share counts at 7.70% and 7.64% a year, so filtering "
        "on price does not keep the milder shrinkers. (3) The filter removed the half that earns. "
        "The near half led SPY by +0.8% a year in 2009-2015 and LOST by 0.9% on the "
        "survivorship-check store; the discarded far half led by +3.5% and +6.0%, against the "
        "unfiltered parent's +3.8%. The mechanism is the original Pontiff-Woodgate argument turned "
        "the right way up: a buyback is informative because management is spending real money "
        "saying the stock is cheap, so the information is in the opportunistic repurchase made "
        "well below the yearly high, not the routine one made at it. Large US companies now buy "
        "back stock quarter after quarter as policy, which is exactly the uninformative half M0243 "
        "kept. So stop filtering and start scoring. Each month, take M0227's scored pool verbatim "
        "(all its split, units and one-listing-per-company guards), keep the members that also "
        "carry a 252-session nearness value, and rank that one pool twice: ascending by the log "
        "fall in split-adjusted share count over a year (the biggest shrinker first) and ascending "
        "by nearness to the 52-week high (the deepest discount first). Each position becomes a "
        "rank fraction in [0, 1], and the book holds the twenty lowest values of "
        "w * rank(buyback) + (1 - w) * rank(discount), equal slots, ties by symbol. Summing rank "
        "fractions rather than raw values means neither piece's units nor its outliers can decide "
        "the book and nothing is thrown away. The idea row described the discount as -log(nearness); "
        "because the pieces are combined by rank, that log is a monotone relabelling and the file "
        "ranks nearness ascending instead, which is the same book with one fewer transform. Arms, "
        "all twenty equal slots, monthly, fractional shares at Gotrade's real fees on the owner's "
        "monthly top-up, none of them timed: B100 (w=100, plain buyback intensity on this pool -- "
        "M0227-S20 as a within-frame control), B75 (w=75), EQ (w=50, the idea), D75 (w=25), D100 "
        "(w=0, a plain deep-discount book -- long-term reversal, which the lab has already rejected "
        "at MAR 0.30) and R (twenty names drawn blind from the identical pool in a monthly-redrawn "
        "hash order: the frame with neither signal). B100 through D100 are a five-rung "
        "dose-response ladder in the discount weight, which is a stronger instrument than a single "
        "arm beside a placebo: a lead that rises monotonically with the discount weight cannot be "
        "the frame. Predictions written before any result. (1) The ladder is monotone in 2009-2015 "
        "and the combination beats BOTH single ends there, on the dev store and on the "
        "survivorship-check store. (2) D100 falls deepest of the six, because a book of deeply "
        "discounted stocks in 2007 is a book of financials in 2008. (3) The 2008 fall stays past "
        "50% -- outside the lab's dev screen -- on every arm, because no arm is timed and M0243 and "
        "M0230 between them established the fall is a concentration problem that neither timing, a "
        "market core nor a price filter touches. (4) Every combo arm beats R by 3 or more points a "
        "year. Success is (1) and (4) together; it would say the discount carries information "
        "rather than merely reshaping the book, and it would make this ladder, not the plain pool, "
        "the right test bed for the queued industry cap (M0239). A monotone ladder running the "
        "WRONG way -- more discount weight, less lead -- is an equally useful result and closes the "
        "direction. Failing the dev drawdown screen is expected and is not itself the verdict."
    ),
    expected_failure=(
        "Five ways, in order of likelihood. (1) The ladder is flat. The two orders may be nearly "
        "the same order: the same buyback dollars retire more shares when the price is low, so the "
        "biggest shrinkers are already mechanically tilted toward companies whose price has "
        "fallen, and if the two rankings correlate strongly then every rung holds nearly the same "
        "twenty names and the whole ladder lands inside a point of itself. That is a measurement "
        "the method still earns -- it would say M0243's far-half result was the buyback signal "
        "operating with no price information added -- but it closes the combination as an idea. "
        "(2) The discount leg is long-term reversal wearing a new coat. D100 is a deep-discount "
        "book, and the lab has rejected that shape twice (M0069, M0073, best MAR 0.30). If the "
        "ladder is monotone but D100 does the earning, the method has rediscovered reversal inside "
        "a buyback pool, and the honest reading is that the pool is the filter and the discount is "
        "the engine -- which is a different method from the one argued here and would need the "
        "reversal literature's own decay caveat applied to it. (3) The 2008 concentration problem "
        "gets worse, not better. Tilting toward cheapness inside a buyback pool in 2007 is a direct "
        "instruction to buy the banks that were buying back stock while their prices fell, which is "
        "the exact failure mode M0227's expected_failure (3) named and M0243's far half confirmed "
        "at a 67.6% fall. The combination may well land nearer FAR20's fall than NEAR20's, and a "
        "book that earns 3 points more while falling 17 points deeper is not progress. (4) "
        "2009-2015 fades anyway. Both halves of this idea are published -- buybacks since 2006-2008, "
        "the 52-week-high effect since 2004 -- and the far half's +6.0 point lead on honest data was "
        "measured over 2009-2015 with a single ranking and 21 years of in-sample context behind it. "
        "A second ranking fitted on top of a result that was itself read after the fact is exactly "
        "how a lab fools itself, which is why the ladder and the predictions are written here "
        "before the run and why no rung will be tuned afterwards. (5) Rank-sum washes out the "
        "extremes. Adding rank fractions treats the gap between the first and second biggest "
        "shrinker as identical to the gap between the hundredth and the hundred-and-first, so a "
        "company retiring 25% of its stock is scored barely ahead of one retiring 12%. That is the "
        "deliberate price of robustness, but it may be the whole reason a combination underperforms "
        "the pure B100 end. None of these is a reason to tune w, the 252-session window, the "
        "combination rule or the parent's guards afterwards: each would be a new method with new "
        "trials."
    ),
    candidates=(
        _v("B100", CheapBuybackParams(20, w_pct=100),
           "Within-frame control: pure buyback intensity, the 20 biggest one-year share-count "
           "shrinkers in the pool, no discount information"),
        _v("B75", CheapBuybackParams(20, w_pct=75),
           "Buyback-heavy: three parts buyback intensity to one part discount from the yearly high"),
        _v("EQ", CheapBuybackParams(20, w_pct=50),
           "The idea: equal parts buyback intensity and discount from the yearly high"),
        _v("D75", CheapBuybackParams(20, w_pct=25),
           "Discount-heavy: one part buyback intensity to three parts discount from the yearly high"),
        _v("D100", CheapBuybackParams(20, w_pct=0),
           "Within-frame control: pure discount from the yearly high inside the buyback pool, no "
           "buyback-intensity information"),
        _v("R", CheapBuybackParams(20, pick="random", seed=1),
           "Placebo: 20 names from the identical pool in a monthly-redrawn hash order, neither "
           "signal"),
    ),
    seen_keys=(
        "concept:buyback-intensity-discount-rank-sum",
        "concept:cheap-buybacks-combined-score",
    ),
)
