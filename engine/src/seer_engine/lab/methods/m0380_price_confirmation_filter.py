"""M0380 — Price confirmation instead of a second buyback-pace cut: M0375's level rank kept, its
filing-based veto replaced by one read off the share price.

Source: variation of M0378 (itself a variation of M0375 → M0371 → M0227, Pontiff & Woodgate 2008).
Reserved by Sera batch 20261026-1017 as an ``idea`` row; this file refines it and keeps its id.

Idea. The buyback book (M0227) ranks index members by how much their split-adjusted share count
shrank over the trailing year and holds the twenty biggest shrinkers. Two attempts have now tried
to CONFIRM a pick with a second reading of the very same filings. M0375 compared the last six
months of share-count change against the six before it and vetoed a name whose buyback was slowing;
M0378 did the same on a yearly clock. Both cost money against doing nothing: on the owner's
deposits M0375's unfiltered arm earned +12.8% a year and its filtered arm +10.3%; M0378's
unfiltered arm earned +12.1% and its filtered arm +9.3%, which was also below its own blind
shape-matched draw at +10.8% (``lab show M0375``, ``lab show M0378``, 2026-10-26). The reserved
idea for this run reads that split as a filing-noise problem and proposes a veto from a genuinely
different source: skip a level-ranked shrinker whose own share price has been clearly weak over
the trailing few months, either outright or against the index.

What this run is really asking. There is a third reading, and it is the one this file is built to
settle. M0243 already filtered this exact pool on a price measure -- nearness to the 52-week high
-- and found the kept half earned +10.4% a year on the owner's deposits where the parent book with
no filter at all earned +13.0% (``lab show M0243``, ``lab show M0227``, 2026-10-26). Three
different filters, two data sources, one pattern: every filter so far put on this book has cost
roughly two to three points a year against the same book unfiltered. So the question this run can
actually answer is not "is price a better confirmation source than filings" but "is the cost the
filter, or is the cost FILTERING" -- whether a book whose picks are already chosen by one thing
simply cannot be improved by vetoing some of them, whatever the veto reads. A price veto is the
cleanest available third source, because it shares no input at all with the level rank: it reads
bars where the rank reads filings.

How. Each monthly check scores every index member on two measures. The ORDER is M0227's own
trailing-twelve-month log share-count change (``m0227_net_share_shrinkers.issuance``, unmodified,
with its identical missed-split and units-error guards and its 180-day minimum count gap). The
VETO reads the member's own trailing ``PX_N``-session price return. ``PX_N`` is 126 sessions, about
six months -- deliberately the same window length M0375's filing-based pace check used, so this run
changes the veto's DATA SOURCE and holds its clock fixed, which is exactly the comparison M0378
could not make when it changed the clock instead.

Two vetoes are registered, both at a zero threshold fixed before any result and never retuned:
``veto="abs"`` skips a name whose own trailing 126-session return is negative (a shrinker buying
back stock while its own price falls -- the distress case), and ``veto="rel"`` skips a name whose
own trailing 126-session return is below SPY's over the identical 126 sessions (weak against the
index, which is a different thing: in a bull market almost nothing is down outright, and in a
crash almost everything is). The two fire on very different months by construction, and saying so
now is the point of registering both: an absolute veto is partly a disguised market-timing device,
because in a falling market it empties the book, while a relative veto keeps its firing rate
roughly steady across regimes. The pool does not depend on which veto is chosen -- a member scores
when BOTH the level measure and its own 126-session return are available -- so every arm in this
file reads the identical universe and differs only in the veto.

The same identical-share-count dedupe every file in this family uses (larger 60-session trading
value wins) is applied once to that pool. Members are sorted by the level score, most negative
(biggest shrinker) first. ``side="unfiltered"`` takes the top ``top`` names straight off that list:
the no-opinion arm, on this file's own pool, so the comparison prices the veto and nothing else.
``side="filtered"`` walks the SAME order, skips any name the veto rejects and continues down the
list until ``top`` names pass or the list runs out, so a filtered book is the unfiltered book with
names removed and others promoted up, never re-sorted; a month where fewer than ``top`` names pass
holds fewer names and is reported as lower exposure, not papered over with a wider cut.
``side="random"`` (a separate allocator id) draws blind from the identical pool, matched to the
corresponding FILTERED arm's own trade count and turnover (``lab.control_draw.matched_book``) --
one draw per veto, because the filter and not the unfiltered rank is the thing whose cost in noise
this run prices.

Assumptions written before any result. The pool opens earlier than M0378's and at roughly M0227's
own start: a 126-session price history is cheap where M0378 needed two full years of prior filings,
so this file's universe is the widest of the three confirmation methods and closest to M0227's.
One blind draw per veto is a single draw. The lab has measured what that costs: across nine
recorded groups of arms identical in every respect except the shuffling seed, changing only the
seed moved the twenty-year funded return by 0.06 to 2.70 points a year, median 1.40, and the rule
of thumb written from it is that a lead over a blind draw under about 1.5 points a year is
unreadable (insights 576 and 585). So this file fixes its own reading rule in advance: a gap under
1.5 points a year between a filtered arm and its own draw will be reported as unreadable, not as a
small win, and the worst fall and the gains-to-losses ratio -- which the same work found barely
wobble with the seed -- will be read instead. Market-aware (``market_fields = ("shares",)``): the history-only path
has no share counts, so by the contract it targets nothing. Rules are ``monthly-hold-frac-gotrade``:
fractional shares at Gotrade's real fees, asked monthly, on the owner's monthly top-up. Pure: reads
only bars and counts public on or before ``data_date``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0198_size_weighted_placebo import trading_value
from seer_engine.lab.methods.m0227_net_share_shrinkers import DV_N, issuance
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED, FactorParams, trend_on

ADDED = date(2026, 10, 26)
SIDES = ("filtered", "unfiltered", "random")
VETOS = ("abs", "rel", "none")
PX_N = 126  # sessions of trailing price return the veto reads: M0375's own six-month clock
BENCH = "SPY"  # the index the relative veto compares a name against


@dataclass(frozen=True, slots=True)
class PriceConfirmParams:
    """``top`` names held; ``veto`` the price check ("abs" outright weakness, "rel" weakness
    against the index, "none" only on the no-opinion arm); ``side`` filtered, unfiltered or random
    (the matched-draw control); ``seed`` the control's draw seed; ``trend`` the switch, (symbol, n)
    or None, set by every variant."""

    top: int
    veto: str = "abs"
    side: str = "filtered"
    seed: int = 0
    trend: tuple[str, int] | None = None

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 200:
            raise ValueError(f"top must be an int in [1, 200], got {self.top!r}")
        if self.veto not in VETOS:
            raise ValueError(f"veto must be one of {VETOS}, got {self.veto!r}")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if (self.side == "unfiltered") != (self.veto == "none"):
            raise ValueError(
                "the no-opinion arm is the only one with no veto: side='unfiltered' requires "
                f"veto='none' and vice versa, got side={self.side!r}, veto={self.veto!r}"
            )
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        FactorParams(rank="momentum", top=self.top, trend=self.trend)  # validates the switch

    def as_dict(self) -> dict[str, str]:
        return {"top": str(self.top), "veto": self.veto, "side": self.side, "seed": str(self.seed),
                "trend": "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}",
                "veto_threshold": {"abs": "px_return<0", "rel": f"px_return<{BENCH}_return",
                                   "none": "none"}[self.veto],
                "px_n": str(PX_N), "bench": BENCH, "dv_n": str(DV_N),
                "class_rule": "identical-share-count"}


def _check(params: object) -> PriceConfirmParams:
    if not isinstance(params, PriceConfirmParams):
        raise TypeError(f"params must be PriceConfirmParams, got {type(params).__name__}")
    return params


def _gate(p: PriceConfirmParams) -> FactorParams:
    return FactorParams(rank="momentum", top=p.top, trend=p.trend)


def trailing_return(h: History, data_date: date, n: int) -> float | None:
    """The simple price return over the last ``n`` sessions through the bar dated ``data_date``,
    or None when there is no bar on that date, fewer than ``n`` bars before it, or the earlier
    close is not a usable positive number. Split-adjusted closes, so a split is not a return."""
    i = h.index_of(data_date)
    if i is None or i < n:
        return None
    then = float(h.close[i - n])
    now = float(h.close[i])
    if not math.isfinite(then) or not math.isfinite(now) or then <= 0.0:
        return None
    return now / then - 1.0


@dataclass(frozen=True, slots=True, eq=False)
class PricePrepared:
    history: Mapping[str, History]
    market: Any  # the Market (share counts), or None on the history-only path


def bench_return(prepared: PricePrepared, data_date: date) -> float | None:
    """SPY's own trailing ``PX_N``-session return on ``data_date``, the bar the relative veto
    compares every candidate against. None when SPY has no bar dated ``data_date``."""
    h = prepared.history.get(BENCH)
    return None if h is None else trailing_return(h, data_date, PX_N)


def combined_pool(prepared: PricePrepared, members: AbstractSet[str],
                  data_date: date) -> dict[str, tuple[float, float]]:
    """symbol -> (level score, own trailing ``PX_N``-session price return) for every member BOTH
    measures can score on ``data_date``, one listing per company (the identical-share-count dedupe
    this family uses: the larger 60-session trading value wins). The pool does not depend on which
    veto a variant chose, so every arm in this file reads the same universe."""
    mk = prepared.market
    if mk is None:
        return {}
    by_count: dict[float, tuple[float, str, float, float]] = {}
    for s in sorted(members):
        if s in EXCLUDED:
            continue
        h = prepared.history.get(s)
        if h is None or h.index_of(data_date) is None:
            continue
        level = issuance(mk, s, data_date)
        if level is None:
            continue
        px = trailing_return(h, data_date, PX_N)
        if px is None:
            continue
        n = mk.shares_on(s, data_date)
        dv = trading_value(h, data_date, DV_N)
        seen = by_count.get(n)
        if seen is None or (dv, s) > (seen[0], seen[1]):
            by_count[n] = (dv, s, level, px)
    return {s: (level, px) for _, s, level, px in by_count.values()}


def ranked_book(pool: Mapping[str, tuple[float, float]], top: int, veto: str,
                bench: float | None) -> tuple[str, ...]:
    """The level-ranked book from ``pool``: the ``top`` biggest shrinkers, skipping over any name
    the price veto rejects. ``veto="none"`` takes the list straight; ``"abs"`` skips a name whose
    own trailing return is negative; ``"rel"`` skips a name whose own trailing return is below
    ``bench``. Walks the SAME order in every case, so a filtered book is the unfiltered book with
    names removed and others promoted up to fill the slots, never re-sorted. A relative veto with
    no benchmark reading cannot be applied and holds nothing, rather than silently falling back."""
    order = sorted(pool, key=lambda s: (pool[s][0], s))
    if veto == "none":
        return tuple(order[:top])
    if veto == "rel":
        if bench is None:
            return ()
        floor = bench
    else:
        floor = 0.0
    passing = [s for s in order if pool[s][1] >= floor]
    return tuple(passing[:top])


class PriceConfirmationAllocator:
    """The ``top`` biggest shrinkers by trailing-year share-count level, equal slots, fully
    invested; with ``side="filtered"`` a name whose own trailing six-month price return is weak --
    outright (``veto="abs"``) or against the index (``veto="rel"``) -- is skipped in favour of the
    next-best shrinker. Nothing while the switch, if any, is off. No share counts (history-only
    path): no targets. Does not run ``side="random"``; see ``MatchedDrawAllocator``."""

    id = "M0380"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(DV_N, PX_N, 0 if p.trend is None else p.trend[1])

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (BENCH,) if p.trend is None else tuple(sorted({BENCH, p.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: PricePrepared, members: AbstractSet[str], data_date: date,
             p: PriceConfirmParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, _gate(p)):
            return ()
        if p.side == "random":
            raise ValueError(
                "PriceConfirmationAllocator does not run side='random'; use MatchedDrawAllocator"
            )
        pool = combined_pool(prepared, members, data_date)
        if not pool:
            return ()
        names = ranked_book(pool, p.top, p.veto, bench_return(prepared, data_date))
        w = equal_weight(p.top)
        out: list[Target] = []
        for s in names:
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no signal and no target."""
        return self._run(PricePrepared(history, None), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> PricePrepared:
        return PricePrepared(history, None)

    def prepare_market(self, market: Any) -> PricePrepared:
        if not hasattr(market, "shares") or len(market.shares) == 0:
            return PricePrepared(market.history, None)
        return PricePrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, PricePrepared):
            raise TypeError(f"prepared must be PricePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


CONFIRM = PriceConfirmationAllocator()

SW = ("SPY", 200)


def _v(suffix: str, params: PriceConfirmParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0380-{suffix}", family="M0380", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CONFIRM, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


def _check_control(params: object) -> PriceConfirmParams:
    """``PriceConfirmParams``, plus the one thing a control's params may not say.

    The matched draw differs from a filtered arm in its allocator id and in nothing else, so the
    params must still read ``side="random"``: a blind book must not describe itself as a ranked
    one. It keeps the ``veto`` field because the draw is matched to THAT veto's arm, and a reader
    of the recorded trial has to be able to tell which of the two it controls."""
    if not isinstance(params, PriceConfirmParams):
        raise TypeError(f"params must be PriceConfirmParams, got {type(params).__name__}")
    if params.side != "random":
        raise ValueError(f"the matched draw is a control: side must be 'random', got {params.side!r}")
    if params.veto == "none":
        raise ValueError("a matched draw controls a filtered arm: veto must be 'abs' or 'rel'")
    return params


class MatchedDrawAllocator:
    """A filtered arm's shape with none of its identity: ``lab.control_draw``'s matched draw on
    this method's pool, matched to the ``side="filtered"`` book of the SAME ``veto`` -- its own
    entries and turnover -- because the veto, not the unfiltered rank, is what this run prices."""

    id = "M0380-A1"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check_control(params)
        inner = max(DV_N, PX_N, 0 if p.trend is None else p.trend[1])
        return control_draw.lookback_for(inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check_control(params)
        return (BENCH,) if p.trend is None else tuple(sorted({BENCH, p.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check_control(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check_control(params)
        return True

    def _select(self, prepared: PricePrepared, members: AbstractSet[str], data_date: date,
                p: PriceConfirmParams) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """(the eligible pool, the controlled filtered arm's own book) on ``data_date``."""
        pool = combined_pool(prepared, members, data_date)
        if not pool:
            return (), ()
        book = ranked_book(pool, p.top, p.veto, bench_return(prepared, data_date))
        return tuple(sorted(pool)), book

    def _run(self, prepared: PricePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: PriceConfirmParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, _gate(p)):
            return ()
        names = control_draw.matched_book(
            lambda d: self._select(prepared, members, d, p),
            data_date, held, tag=f"M0380-{p.veto}", seed=p.seed,
        )
        w = equal_weight(p.top)
        out: list[Target] = []
        for s in names:
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no pool and no target."""
        return self._run(PricePrepared(history, None), members, data_date, held,
                         _check_control(params))

    def prepare(self, history: Mapping[str, History]) -> PricePrepared:
        return PricePrepared(history, None)

    def prepare_market(self, market: Any) -> PricePrepared:
        if not hasattr(market, "shares") or len(market.shares) == 0:
            return PricePrepared(market.history, None)
        return PricePrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, PricePrepared):
            raise TypeError(f"prepared must be PricePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check_control(params))


MATCHED = MatchedDrawAllocator()


def _vm(suffix: str, params: PriceConfirmParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0380-{suffix}", family="M0380", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MATCHED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0380",
    name="Price confirmation on the buyback book, not a second cut of the same filings",
    family="stock-net-share-issuance",
    source_kind="variation",
    source_ref="M0378",
    parent_id="M0378",
    hypothesis=(
        "Every confirmation filter this lab has put on the buyback book so far has cost money "
        "against the same book unfiltered, and the two that read a second cut of the share-count "
        "filings cost about the same as the one that read the price. On the owner's deposits: "
        "M0375's six-month pace veto earned +10.3% a year where its own unfiltered arm earned "
        "+12.8%; M0378's year-over-year pace veto earned +9.3% where its unfiltered arm earned "
        "+12.1%, and lost even to its own blind shape-matched draw at +10.8%; and M0243's "
        "nearness-to-the-52-week-high filter earned +10.4% where the unfiltered parent book "
        "(M0227) earned +13.0% ('lab show M0375', 'lab show M0378', 'lab show M0243', 'lab show "
        "M0227', 2026-10-26). The reserved idea for this run reads the M0375-versus-M0378 split as "
        "a filing-noise problem and proposes a veto from a different source. This file registers "
        "that veto and uses it to ask the larger question the three results together now pose: is "
        "the cost the particular filter, or is the cost FILTERING -- can a book whose picks are "
        "already chosen by one measure be improved by vetoing some of them at all, whatever the "
        "veto reads? Book: the 20 biggest trailing-twelve-month share-count shrinkers by level "
        "(M0227's score and guards, unmodified) from a pool scorable on both the level measure and "
        "a 126-session trailing price return, with a price veto applied -- skip the name and "
        "promote the next-best shrinker into the slot. 126 sessions is deliberately M0375's own "
        "six-month clock, so this run changes the veto's data source and holds its window length "
        "fixed, which is the comparison M0378 could not make when it changed the clock instead. "
        "Equal slots, monthly, fractional shares at Gotrade's real fees on the owner's monthly "
        "top-up (monthly-hold-frac-gotrade), target max drawdown 20% or less, gains-to-losses 1.3 "
        "or better, well over 100 trades. Two vetoes at a zero threshold fixed now and never "
        "retuned: FILT20-PX-ABS skips a shrinker whose own six-month price return is negative (the "
        "distress case -- buying back stock while the price falls), FILT20-PX-REL skips one whose "
        "six-month return is below SPY's over the identical sessions (weak against the index). "
        "They fire on very different months on purpose: an absolute veto empties the book in a "
        "falling market and so is partly a disguised market-timing device, while a relative veto "
        "keeps a roughly steady firing rate across regimes. Controls: UNFILT20-PX, the same pool "
        "and the same level order with no veto at all (the no-opinion arm, which is what each "
        "filtered arm has to beat for the veto to be worth anything); FILT20-PX-REL-SW, the "
        "relative arm behind the SPY 200-day switch, the only construction in this family that has "
        "ever reached the drawdown bar; and PLC20-PX-ABS and PLC20-PX-REL, blind shape-matched "
        "draws from the identical pool, each matched to its own filtered arm's trade count and "
        "turnover. Predictions written before any result. (1) The relative veto beats the absolute "
        "one on worst fall but not on return, because removing names that are merely weaker than "
        "the index is a milder cut than emptying the book in a crash. (2) Neither filtered arm "
        "beats UNFILT20-PX by more than a point a year; the honest prior from three prior filters "
        "is that both land two to three points BELOW it. (3) The absolute arm's worst fall lands "
        "well below the unfiltered arm's, and that will be the switch in disguise rather than "
        "better picking -- readable because the switched relative arm is in the same run. (4) "
        "Only the switched arm can reach the 20% drawdown bar, as in every other member of this "
        "family. Success is a filtered arm beating UNFILT20-PX by more than a point a year AND "
        "beating its own blind draw by more than 1.5 points a year, which is the lab's own "
        "measured width for a single shuffling seed (0.06 to 2.70 points, median 1.40, across "
        "nine seed-only groups; insights 576 and 585). Anything less closes the question of "
        "filtering this book rather than opening a tuning exercise."
    ),
    expected_failure=(
        "Five ways, in order of likelihood. (1) The same two-to-three-point tax as every other "
        "filter: both FILT20-PX-ABS and FILT20-PX-REL land below UNFILT20-PX by roughly what "
        "M0375's, M0378's and M0243's filters cost, and the finding is that this book cannot be "
        "improved by vetoing its own picks at all -- the cost is the filtering, not the filter. "
        "That would be a clean, general result and a rejection, and it is the outcome this file "
        "expects. (2) The absolute veto is a market-timing switch wearing a stock filter's "
        "clothes: its worst fall drops sharply, its 2009-2015 return drops with it, and the "
        "improvement is entirely the months it spent holding fewer than twenty names or nothing at "
        "all. The lab has measured that safety devices do not stack and that time out of the "
        "market is one of the two expensive dials, so a lower fall bought this way is not a "
        "discovery. (3) Momentum in disguise, the other way round: vetoing weak price is a "
        "momentum tilt, and M0243 already found the price-strong half of this pool earned no more "
        "than the price-weak half (+10.4% against +10.3% a year) while the discarded half was the "
        "one that beat the market after 2009. If the two filtered arms land within a point of each "
        "other and of their own blind draws, the price veto is adding noise and nothing else. (4) "
        "The family's 2009-2015 shortfall survives regardless: every member of this family has "
        "been weak in the best-covered years, and a new veto source does not change where the "
        "underlying ranking earns its money. (5) Thin separation in the years that matter: in a "
        "bull market almost no index member is down over six months, so the absolute veto barely "
        "fires in the long stretches and fires on everything in 2008 -- biting hardest exactly "
        "when a crash is not selective. Any of these is a rejection. None is a reason to retune "
        "the zero thresholds, the 126-session window, the top of 20, or M0227's guards afterwards."
    ),
    candidates=(
        _v("UNFILT20-PX", PriceConfirmParams(20, veto="none", side="unfiltered", trend=None),
           "The 20 biggest shrinkers by level from this file's pool, no veto, no switch -- the "
           "no-opinion arm every filtered arm has to beat"),
        _v("FILT20-PX-ABS", PriceConfirmParams(20, veto="abs", side="filtered", trend=None),
           "Skip any shrinker whose own 126-session price return is negative, no switch"),
        _v("FILT20-PX-REL", PriceConfirmParams(20, veto="rel", side="filtered", trend=None),
           "Skip any shrinker whose 126-session return is below SPY's over the same sessions, no "
           "switch"),
        _v("FILT20-PX-REL-SW", PriceConfirmParams(20, veto="rel", side="filtered", trend=SW),
           "FILT20-PX-REL behind the SPY 200-day switch -- the only construction in this family "
           "that has reached the drawdown bar"),
        _vm("PLC20-PX-ABS", PriceConfirmParams(20, veto="abs", side="random", seed=1, trend=None),
            "Placebo, shape-matched: 20 names from the identical pool by a monthly hash order, "
            "matched to FILT20-PX-ABS's own trade count and turnover (lab.control_draw)"),
        _vm("PLC20-PX-REL", PriceConfirmParams(20, veto="rel", side="random", seed=1, trend=None),
            "Placebo, shape-matched: 20 names from the identical pool by a monthly hash order, "
            "matched to FILT20-PX-REL's own trade count and turnover (lab.control_draw)"),
    ),
    seen_keys=(
        "concept:buyback-price-confirmation-filter",
        "concept:trailing-return-veto-on-a-stock-screen",
    ),
)
