"""M0243 — Buyback shrinkers near their yearly high: the buyback book with the falling knives removed.

Variation of M0227 (the buyback book) with M0015's nearness-to-the-52-week-high as a *filter*
rather than a ranking. Reserved by Sera batch 20261019-0853 as an ``idea`` row; this file refines
it and keeps its id.

Why this shape. M0227 found the lab's strongest live stock signal: the twenty index members whose
split-adjusted share count fell most over a year earned +13.0% a year on the owner's deposits where
SPY earned +7.2%, and they beat both the opposite book (the biggest issuers, +9.2%) and a hash-drawn
placebo on the same pool (+7.7%). What killed it was the fall -- 58.7% in 2008 -- and the only arm
that passed the dev screen hid behind the SPY 200-day switch, which then sat out the 2009-11
rebound and lost that walk-forward fold outright. M0230 tried to replace the timing with a market
core and failed for the arithmetic reason: a core that holds SPY through a crash falls with it.

So this method attacks the fall from inside the picks instead. A company that is buying back stock
*while its price sits near its own yearly high* is returning cash from strength. A company buying
back stock while its price sits 60% below its high is, often enough, a management team defending a
collapsing share price with the last of the balance sheet -- the falling knife the parent's 2008
book was full of. The lab has one piece of evidence that this distinction is real and not a
backtest artefact: nearness to the 52-week high is the only filter measured here that earns MORE
when the dead companies are put back on the survivorship-check store (+1.3 points a year, while its
mirror loses 3.5 and falls 15 points deeper), because a company heading for bankruptcy is, by
construction, far below its high.

The danger, written down before any result, is that the filter does not remove falling knives at
all but simply turns the book into a momentum book, which this lab has measured many times and
which loses after 2009. The arms are built so one comparison answers that: ``NEAR20-R`` draws
twenty names blind from the identical near band, so it is the whole filter with none of the
buyback signal. If it matches ``NEAR20``, the buybacks are decoration.

How it chooses, on each monthly check:

    * THE POOL. M0227's ``scored_pool`` verbatim: every index member with a bar dated
      ``data_date`` whose split-adjusted share count can be compared with the count public 365
      days earlier, under all of the parent's pre-registered guards (at least 180 days between the
      two counts; a ratio within 3% of a common split ratio or outside 0.5-3.0 is skipped; one
      listing per company, decided by 60-session trading value). The score is the log of new over
      carried-old: negative for a shrinker, positive for an issuer.
    * THE FILTER. ``nearness`` (M0015, verbatim): ``close[d] / max(close over the last 252
      sessions)``, in (0, 1]. Closes, not intraday highs, so a stray print cannot set the high. A
      pool member with no nearness value (under 252 bars) is dropped. The remainder is sorted by
      (nearness, symbol) and cut by RANK into ``cut`` equal parts; ``side="near"`` keeps the
      topmost part, ``side="far"`` the bottom one. Ties at nearness 1.0 are common in a strong
      market and are broken by SYMBOL alone -- deliberately not by momentum (M0232's tiebreak) and
      deliberately not by the buyback score, so the band is identical for the shrink arm and for
      the placebo, and the comparison between them is clean.
    * THE PICK. Inside the band, the ``top`` most-negative issuance scores (the biggest shrinkers),
      equal slots, fully invested. ``pick="random"`` instead takes ``top`` names from the same band
      in M0187's monthly-redrawn hash order: the same filter, the same fees, no knowledge of
      buybacks. (M0227's own placebo used a *sticky* hash order and traded 41 times in twenty
      years, failing the trade-count condition; this one is redrawn each month, so it turns over
      like the book it controls for.)
    * THE SWITCH. ``trend=("SPY", 200)``, when set, holds nothing while SPY closes at or below its
      200-day average (``f_factor.trend_on``). Only ``NEAR20-SW`` carries it.

Coverage, measured before this file was committed (pool COUNTS only; no returns were read): the
scorable pool runs 170-184 names in 1997 and 369-378 by 2015, so the near half holds 85-189 names
and the near third 56-126. Twenty slots fill in every month of the window; there is no thin-band
problem of the kind M0232 had to allow for, and no unfilled slot ever sits in cash for want of
candidates.

Window: the parent's, 1997-2015 in effect (a year of share counts must pass first), inside the
dev window ending 2015-10-16.

Market-aware (``market_fields = ("shares",)``): the history-only path has no share counts, so by
the contract it targets nothing. Rules are ``monthly-hold-frac-gotrade``: fractional shares at
Gotrade's real fees, asked monthly, on the owner's monthly top-up -- the same preset the parent and
M0230 ran on, so the comparison needs no cost translation. Pure: reads only bars and counts public
on or before ``data_date``.
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
from seer_engine.strategies.f_factor import FactorParams, trend_on

ADDED = date(2026, 10, 19)

SIDES = ("near", "far")
PICKS = ("shrink", "random")


@dataclass(frozen=True, slots=True)
class NearShrinkParams:
    """``top`` names held; ``cut`` the number of equal-count nearness bands the pool is split into
    (2 = halves, 3 = thirds); ``side`` which band is kept (``near`` the topmost, ``far`` the
    bottom); ``pick`` the buyback ranking or the blind hash draw; ``seed`` that draw's seed;
    ``trend`` the SPY switch, (symbol, n) or None."""

    top: int
    cut: int = 2
    side: str = "near"
    pick: str = "shrink"
    seed: int = 0
    trend: tuple[str, int] | None = None

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 200:
            raise ValueError(f"top must be an int in [1, 200], got {self.top!r}")
        if isinstance(self.cut, bool) or not isinstance(self.cut, int) or not 2 <= self.cut <= 5:
            raise ValueError(f"cut must be an int in [2, 5], got {self.cut!r}")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if self.pick not in PICKS:
            raise ValueError(f"pick must be one of {PICKS}, got {self.pick!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        if self.pick != "random" and self.seed != 0:
            raise ValueError("seed is for the random (placebo) pick only")
        FactorParams(rank="momentum", top=self.top, trend=self.trend)  # validates the switch

    def as_dict(self) -> dict[str, str]:
        out = {
            "top": str(self.top),
            "cut": str(self.cut),
            "side": self.side,
            "pick": self.pick,
            "trend": "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}",
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


def _check(params: object) -> NearShrinkParams:
    if not isinstance(params, NearShrinkParams):
        raise TypeError(f"params must be NearShrinkParams, got {type(params).__name__}")
    return params


def _gate(p: NearShrinkParams) -> FactorParams:
    return FactorParams(rank="momentum", top=p.top, trend=p.trend)


def band(pool: Mapping[str, float], history: Mapping[str, History], data_date: date,
         p: NearShrinkParams) -> list[str]:
    """The kept nearness band of ``pool``: an equal-count ``cut``-th of the members that carry a
    nearness value, the topmost when ``side="near"`` and the bottom one when ``side="far"``.
    Sorted ascending by (nearness, symbol); the symbol tiebreak is signal-blind on purpose."""
    scored: list[tuple[float, str]] = []
    for s in pool:
        v = nearness(history, s, data_date, HIGH_N)
        if v is not None:
            scored.append((v, s))
    if not scored:
        return []
    scored.sort()
    size = len(scored) // p.cut
    if size < 1:
        return []
    chosen = scored[-size:] if p.side == "near" else scored[:size]
    return [s for _, s in chosen]


class NearShrinkAllocator:
    """The ``top`` biggest one-year share-count shrinkers inside the near (or far) nearness band of
    M0227's scored pool, equal slots, fully invested; nothing while the switch, if any, is off. No
    share counts (history-only path): no targets."""

    id = "M0243"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(DV_N, HIGH_N, 0 if p.trend is None else p.trend[1])

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return ("SPY",) if p.trend is None else tuple(sorted({"SPY", p.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: IssuancePrepared, members: AbstractSet[str], data_date: date,
             p: NearShrinkParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, _gate(p)):
            return ()
        pool = scored_pool(prepared, members, data_date)
        if not pool:
            return ()
        kept = band(pool, prepared.history, data_date, p)
        if not kept:
            return ()
        if p.pick == "shrink":
            order = sorted(kept, key=lambda s: (pool[s], s))
        else:
            order = sorted(kept, key=lambda s: (draw(p.seed, s, data_date), s))
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


NEAR_SHRINK = NearShrinkAllocator()

SW = ("SPY", 200)


def _v(suffix: str, params: NearShrinkParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0243-{suffix}", family="M0243", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=NEAR_SHRINK, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0243",
    name=(
        "Buyback shrinkers near their yearly high: the buyback book with the falling knives removed"
    ),
    family="stock-net-share-issuance",
    source_kind="variation",
    source_ref=(
        "variation of M0227 (the buyback book) filtered by M0015's nearness to the 52-week high; "
        "Pontiff & Woodgate (2008) JF 63(2) 921-945, "
        "https://ideas.repec.org/a/bla/jfinan/v63y2008i2p921-945.html; George & Hwang (2004) JF "
        "59(5) doi:10.1111/j.1540-6261.2004.00695.x; placebo of M0187"
    ),
    parent_id="M0227",
    hypothesis=(
        "The lab's strongest live stock signal is the buyback book (M0227): the twenty index "
        "members whose split-adjusted share count fell most over a year earned +13.0% a year on "
        "the owner's deposits where SPY earned +7.2%, beating both the opposite book (+9.2%) and a "
        "placebo on the same pool (+7.7%). What killed it was the fall: 58.7% in 2008, and the only "
        "arm that passed the dev screen hid behind the SPY 200-day switch, which then gave back "
        "2009-2015 and lost that walk-forward fold to cash. M0230 showed a market core cannot fix "
        "that, because a core falls with the crash it sits in. So attack the fall from inside the "
        "picks: a company buying back stock while its price sits near its own yearly high is "
        "returning cash from strength; one buying back while its price sits far below its high is "
        "often a management team defending a collapsing share price. The lab has evidence the "
        "distinction is real rather than a backtest artefact: nearness to the 52-week high is the "
        "only filter measured here that earns MORE when the dead companies are put back on the "
        "survivorship-check store (+1.3 points a year, where its mirror loses 3.5 and falls 15 "
        "deeper), because a company heading for bankruptcy is by construction far below its high. "
        "Each month, take M0227's scored pool verbatim (all its split, units and one-listing-per-"
        "company guards), sort it by nearness (close over the highest close of the last 252 "
        "sessions, ties broken by symbol alone so the band is signal-blind), cut it into equal-count "
        "bands by rank, and hold the twenty biggest shrinkers inside the kept band. Coverage was "
        "measured before this file was committed, pool counts only and no returns: the scorable "
        "pool runs 170-184 names in 1997 and 369-378 by 2015, so the near half holds 85-189 and the "
        "near third 56-126; twenty slots fill in every month. Arms, all twenty equal slots, monthly, "
        "fractional shares at Gotrade's real fees on the owner's monthly top-up: NEAR20 (the near "
        "half, the idea), FAR20 (the bottom half, the mirror: the falling knives the filter is "
        "meant to remove), NEAR20-T3 (the near third, a stricter dose of the same filter), NEAR20-R "
        "(twenty names drawn blind from the identical near half in a monthly-redrawn hash order: "
        "the whole filter with none of the buyback signal) and NEAR20-SW (NEAR20 behind the SPY "
        "200-day switch, the only arm that can reach the 20% drawdown bar). Predictions written "
        "before any result. (1) NEAR20 beats FAR20 by 3 or more points a year AND falls at least 8 "
        "points less deeply -- the filter separates. (2) NEAR20 beats NEAR20-R by 2 or more points "
        "a year; if it does not, the nearness filter is doing all the work and this is M0015 in "
        "disguise, which already lost. (3) The fall: NEAR20 lands between 40% and 50%, below the "
        "parent's 58.7% but far above the 20% bar; only NEAR20-SW reaches the bar, near the "
        "parent's switched 25.8%. (4) The real question is 2009-2015 and the folds: NEAR20 never "
        "leaves the market, so it should win 3 of 4 walk-forward folds where the parent's switched "
        "arm won 2, and keep a positive lead over SPY in 2009-2015. (5) The dose: NEAR20-T3 lands "
        "between NEAR20 and the parent on return; if the stricter filter earns MORE, the filter is "
        "the engine and the buybacks are decoration. Success is (1), (2) and (4) together. Success "
        "on (1) alone, with the placebo matching and the folds still lost, is a rejection."
    ),
    expected_failure=(
        "Five ways, in order of likelihood. (1) Momentum in disguise: the near band is a momentum "
        "band, so NEAR20-R lands within a point of NEAR20 and the method measures nearness rather "
        "than capital allocation. The lab has already measured plain nearness twice -- M0015 at MAR "
        "0.58 and M0232's NEAR-ALL arm at +6.1% a year against SPY's +7.2% at these very fees -- so "
        "a book that is only nearness is a book that already lost, and that would close this "
        "direction rather than open a tuning exercise. (2) The crash is not selective: 2008 took "
        "the near half down with the far half, which is what a crash means, so NEAR20 still falls "
        "past 50% and only the switched arm reaches the bar. That puts the method back exactly "
        "where M0227 was, with timing as the only brake and the 2009-11 fold lost to cash again. "
        "(3) The filter removes the signal it is meant to protect: the same buyback dollars retire "
        "more shares when the price is low, so the biggest shrinkers are mechanically tilted toward "
        "companies whose price has fallen, and keeping only the near half systematically keeps the "
        "SMALLER shrinkers. Then NEAR20 earns less than the parent's +13.0% and still falls far -- "
        "worse on both axes at once, which is a rejection and not a dial to turn. (4) Thin "
        "separation: the near and far halves of a buyback pool may be nearly the same companies in "
        "a bull market, where almost everything sits near its high, so the filter only bites in the "
        "years it is least needed and does nothing in 2008 when it matters. (5) Decay: buybacks "
        "have been public since 2008 and the 52-week-high effect since 2004, so both halves of this "
        "idea are published and the dev window straddles both publications; 2009-2015 is the "
        "honest read and a twenty-year average earned before 2009 is a dead edge. One caution "
        "pointing the other way, written down now so it is not read as a discovery later: nearness "
        "is the one filter that improves on the survivorship-check store, so the check store may "
        "flatter this book rather than cut it. That is a reason to read the check store, not a "
        "reason to trust the dev number more. None of these is a reason to tune the cut, the 252-"
        "session window or the parent's guards afterwards."
    ),
    candidates=(
        _v("NEAR20", NearShrinkParams(20, cut=2, side="near"),
           "The 20 biggest one-year share-count shrinkers inside the near half by nearness to the "
           "52-week high, no switch"),
        _v("FAR20", NearShrinkParams(20, cut=2, side="far"),
           "The mirror: the 20 biggest shrinkers inside the FAR half, the falling knives"),
        _v("NEAR20-T3", NearShrinkParams(20, cut=3, side="near"),
           "A stricter dose: the 20 biggest shrinkers inside the near THIRD by nearness"),
        _v("NEAR20-R", NearShrinkParams(20, cut=2, side="near", pick="random", seed=1),
           "Placebo: 20 names from the identical near half in a monthly-redrawn hash order"),
        _v("NEAR20-SW", NearShrinkParams(20, cut=2, side="near", trend=SW),
           "NEAR20 behind the SPY 200-day switch: the only arm that can reach the 20% bar"),
    ),
    seen_keys=(
        "concept:buyback-shrinkers-near-high",
        "concept:net-share-issuance-nearness-filter",
    ),
)
