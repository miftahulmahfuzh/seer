"""M0375 — Buyback confirmation filter: keep M0227's level rank, use M0371's pace change only to
veto a name, never to rank one.

Source: variation of M0371 (itself a variation of M0227, Pontiff & Woodgate 2008). Reserved by
Sera batch 20261026-0703 as an ``idea`` row; this file refines it and keeps its id.

Idea. M0227 ranks index members on the LEVEL of net share-count shrinkage over the trailing
twelve months and is dev-eligible. M0371 asked whether the CHANGE in that pace -- the most recent
six months' shrinkage against the prior six months' -- is itself a better ranking signal, and was
rejected: speeding up beats slowing down, but ranking on the six-month difference roughly doubled
the book's trading against the level measure and lost to it on return, fall and the luck test
(``lab show M0371``, 2026-10-26). A ranking signal and a filter are not the same use of the same
information. M0371 spent its whole book re-sorting every month by a noisier, faster-moving number;
this variation keeps the level measure as the only thing that decides ORDER -- the slow, sticky
ranking M0227 already found some edge in -- and asks the pace-change measure only a yes/no
question: is this name's buyback *clearly slowing down or reversing into issuance right now*, even
though its trailing year still reads as a shrinker. A name the filter vetoes is skipped and the
next-best shrinker by level takes its slot. If the acceleration measure's directional information
(M0371's own accepted half: ACC20 beat DEC20) survives being used this narrow way, the book should
keep most of S20's low turnover while quietly avoiding the shrinkers whose buyback is already
running out of steam -- the ones most likely to re-rate like M0227's own worst case, a company that
bought back stock right up until it could not afford to any more.

How. Each monthly check scores every index member on BOTH measures from the same filing history:
the trailing-twelve-month log share-count change (``m0227_net_share_shrinkers.issuance``) and the
six-months-vs-prior-six-months log change (``m0371_buyback_acceleration.acceleration``), using
each file's own guards unmodified (missed-split and units-error bands, the 180- and 90-day minimum
count gaps). A member scores only when BOTH measures are available, so this file's pool is the
intersection of M0227's and M0371's -- strictly inside M0227's, since the acceleration measure
needs three point-in-time counts roughly six months apart rather than two a year apart. The same
identical-share-count dedupe both parents use (larger 60-session trading value wins) is applied
once to the combined pool, so UNFILTERED and FILTERED read the same universe and differ only in
the filter.

Members are sorted by the level score, most negative (biggest shrinker) first -- exactly M0227's
own order, restricted to this narrower pool. ``filter="off"`` (UNFILTERED) takes the top ``top``
names straight off that list: the no-opinion arm, run on the same pool as the treatment so the
comparison is the filter and nothing else, not a comparison against M0227-S20's own wider pool.
``filter="on"`` (FILTERED) walks the same ordered list and skips any name whose acceleration score
is positive -- its most recent six months shrank its share count less than the six months before,
or reversed into issuance -- continuing down the list until ``top`` names pass or the list runs
out, whichever comes first; a month where fewer than ``top`` names pass holds fewer names and is
reported as lower exposure, not papered over with a wider cut. The zero threshold is the natural
reading of the sign M0371 already defined (``side="accel"``/``"decel"``) and is fixed before any
result precisely so there is no dial to retune afterward. ``side="random"`` (the matched-draw
control, a separate allocator id) draws from the identical combined pool, matched to the FILTERED
arm's own trade count and turnover (``lab.control_draw.matched_book``), because the filter is the
thing whose cost in noise this run wants to price, not the unfiltered book.

Assumptions written before any result. The dev window still trades from M0227's own start
(1997-2015): this file's pool is a subset of M0227's and a subset of M0371's (it needs both
measures where M0371 needed only its own two), so it holds no more names on any date than either
parent and likely holds strictly fewer during the early, thin-filing years. Market-aware
(``market_fields = ("shares",)``): the history-only path has no share counts, so by the contract it
targets nothing. Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees,
asked monthly, on the owner's monthly top-up. Pure: reads only bars and counts public on or before
``data_date``.
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
from seer_engine.lab.methods.m0198_size_weighted_placebo import trading_value
from seer_engine.lab.methods.m0227_net_share_shrinkers import DV_N, issuance
from seer_engine.lab.methods.m0371_buyback_acceleration import acceleration
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED, FactorParams, trend_on

ADDED = date(2026, 10, 26)
SIDES = ("filtered", "unfiltered", "random")


@dataclass(frozen=True, slots=True)
class ConfirmParams:
    """``top`` names held; ``side`` filtered, unfiltered or random (the matched-draw control);
    ``seed`` the control's draw seed; ``trend`` the switch, (symbol, n) or None, set by every
    variant."""

    top: int
    side: str = "filtered"
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
        return {"top": str(self.top), "side": self.side, "seed": str(self.seed),
                "trend": "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}",
                "veto_threshold": "accel>0", "dv_n": str(DV_N),
                "class_rule": "identical-share-count"}


def _check(params: object) -> ConfirmParams:
    if not isinstance(params, ConfirmParams):
        raise TypeError(f"params must be ConfirmParams, got {type(params).__name__}")
    return params


def _gate(p: ConfirmParams) -> FactorParams:
    return FactorParams(rank="momentum", top=p.top, trend=p.trend)


@dataclass(frozen=True, slots=True, eq=False)
class ConfirmPrepared:
    history: Mapping[str, History]
    market: Any  # the Market (share counts), or None on the history-only path


def combined_pool(prepared: ConfirmPrepared, members: AbstractSet[str],
                   data_date: date) -> dict[str, tuple[float, float]]:
    """symbol -> (level score, acceleration score) for every member BOTH measures can score on
    ``data_date``, one listing per company (the identical-share-count dedupe both parents use)."""
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
        accel = acceleration(mk, s, data_date)
        if accel is None:
            continue
        n = mk.shares_on(s, data_date)
        dv = trading_value(h, data_date, DV_N)
        seen = by_count.get(n)
        if seen is None or (dv, s) > (seen[0], seen[1]):
            by_count[n] = (dv, s, level, accel)
    return {s: (level, accel) for _, s, level, accel in by_count.values()}


def ranked_book(pool: Mapping[str, tuple[float, float]], top: int, filtered: bool) -> tuple[str, ...]:
    """The level-ranked book from ``pool``: the ``top`` biggest shrinkers, skipping over any name
    the filter vetoes (a positive acceleration score: its buyback is slowing or reversing) when
    ``filtered`` is True. Walks the SAME order either way, so a filtered book is the unfiltered
    book with some names removed and others promoted up to fill the slots, never re-sorted."""
    order = sorted(pool, key=lambda s: (pool[s][0], s))
    if not filtered:
        return tuple(order[:top])
    passing = [s for s in order if pool[s][1] <= 0.0]
    return tuple(passing[:top])


class ConfirmationAllocator:
    """The ``top`` biggest shrinkers by trailing-year level, equal slots, fully invested; with
    ``side="filtered"`` a name whose recent buyback pace has turned positive (slowing or
    reversing) is skipped in favour of the next-best shrinker. Nothing while the switch, if any,
    is off. No share counts (history-only path): no targets. Does not run ``side="random"``; see
    ``MatchedDrawAllocator``."""

    id = "M0375"
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

    def _run(self, prepared: ConfirmPrepared, members: AbstractSet[str], data_date: date,
              p: ConfirmParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, _gate(p)):
            return ()
        pool = combined_pool(prepared, members, data_date)
        if not pool:
            return ()
        if p.side not in ("filtered", "unfiltered"):
            raise ValueError("ConfirmationAllocator does not run side='random'; use MatchedDrawAllocator")
        names = ranked_book(pool, p.top, filtered=(p.side == "filtered"))
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
        return self._run(ConfirmPrepared(history, None), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> ConfirmPrepared:
        return ConfirmPrepared(history, None)

    def prepare_market(self, market: Any) -> ConfirmPrepared:
        if not hasattr(market, "shares") or len(market.shares) == 0:
            return ConfirmPrepared(market.history, None)
        return ConfirmPrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                          held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ConfirmPrepared):
            raise TypeError(f"prepared must be ConfirmPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


CONFIRM = ConfirmationAllocator()

SW = ("SPY", 200)


def _v(suffix: str, params: ConfirmParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0375-{suffix}", family="M0375", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                      allocator=CONFIRM, params=params, rationale=rationale, added=ADDED,
                      owner_inputs=())


def _check_control(params: object) -> ConfirmParams:
    """``ConfirmParams``, plus the one thing a control's params may not say.

    The matched draw differs from the filtered arm in its allocator id and in nothing else, so the
    params must still read ``side="random"``: a blind book must not describe itself as a ranked one.
    """
    if not isinstance(params, ConfirmParams):
        raise TypeError(f"params must be ConfirmParams, got {type(params).__name__}")
    if params.side != "random":
        raise ValueError(f"the matched draw is a control: side must be 'random', got {params.side!r}")
    return params


class MatchedDrawAllocator:
    """FILT20's shape with none of its identity: ``lab.control_draw``'s matched draw on this
    method's combined pool, matched to the ``side="filtered"`` book's own entries and turnover --
    because the filter, not the unfiltered rank, is the thing whose cost in noise this run prices."""

    id = "M0375-A1"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check_control(params)
        inner = max(DV_N, 0 if p.trend is None else p.trend[1])
        return control_draw.lookback_for(inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check_control(params)
        return ("SPY",) if p.trend is None else tuple(sorted({"SPY", p.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check_control(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check_control(params)
        return True

    def _select(self, prepared: ConfirmPrepared, members: AbstractSet[str], data_date: date,
                p: ConfirmParams) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """(the eligible pool, FILT20's own book) on ``data_date`` -- the filtered arm's own two."""
        pool = combined_pool(prepared, members, data_date)
        if not pool:
            return (), ()
        return tuple(sorted(pool)), ranked_book(pool, p.top, filtered=True)

    def _run(self, prepared: ConfirmPrepared, members: AbstractSet[str], data_date: date,
              held: frozenset[str], p: ConfirmParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        gate = FactorParams(rank="momentum", top=p.top, trend=p.trend)
        if not trend_on(prepared.history, data_date, gate):
            return ()
        names = control_draw.matched_book(
            lambda d: self._select(prepared, members, d, p),
            data_date, held, tag="M0375", seed=p.seed,
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
        return self._run(ConfirmPrepared(history, None), members, data_date, held,
                          _check_control(params))

    def prepare(self, history: Mapping[str, History]) -> ConfirmPrepared:
        return ConfirmPrepared(history, None)

    def prepare_market(self, market: Any) -> ConfirmPrepared:
        if not hasattr(market, "shares") or len(market.shares) == 0:
            return ConfirmPrepared(market.history, None)
        return ConfirmPrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                          held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ConfirmPrepared):
            raise TypeError(f"prepared must be ConfirmPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check_control(params))


MATCHED = MatchedDrawAllocator()


def _vm(suffix: str, params: ConfirmParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0375-{suffix}", family="M0375", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                      allocator=MATCHED, params=params, rationale=rationale, added=ADDED,
                      owner_inputs=())


METHOD = Method(
    id="M0375",
    name=(
        "Buyback confirmation filter: rank by the level of share shrinkage, veto a name whose "
        "pace is now slowing or reversing"
    ),
    family="stock-net-share-issuance",
    source_kind="variation",
    source_ref="M0371",
    parent_id="M0371",
    hypothesis=(
        "M0227 ranks on the trailing-twelve-month level of share shrinkage and is dev-eligible. "
        "M0371 tried ranking on the CHANGE in that pace instead (recent six months against the "
        "prior six) and was rejected: ACC20 beat DEC20 (directional information is there) but "
        "re-sorting every month by the noisier six-month difference roughly doubled the book's "
        "trading against the level measure and lost to it on return, fall and the luck test. This "
        "variation uses the two measures for different jobs instead of making them compete: the "
        "level score still decides ORDER (M0227's own slow, sticky ranking), and the pace-change "
        "score only VETOES a name whose most recent six months shrank its share count less than "
        "the six months before (or reversed into issuance), with the next-best shrinker by level "
        "promoted into the freed slot. Book: FILT20, the 20 biggest shrinkers by level from a pool "
        "scorable on BOTH measures, with the veto applied; equal slots, monthly, fractional shares "
        "at Gotrade's real fees on the owner's monthly top-up (monthly-hold-frac-gotrade). "
        "Controls: UNFILT20, the same pool and the same level order with no veto (the no-opinion "
        "arm, isolating the filter itself rather than the narrower pool); FILT20-SW, FILT20 behind "
        "the SPY 200-day switch; PLC20, a frame-matched blind draw from the same pool, matched to "
        "FILT20's own trade count and turnover (lab.control_draw), not UNFILT20's, because the "
        "filter is the thing whose noise this run is pricing. Window: 1997-2015, the intersection "
        "of M0227's and M0371's pools. Predictions written before any result: FILT20 trades only "
        "modestly more than UNFILT20 -- a veto-and-promote rule changes a handful of names a month "
        "at the margin, not the whole sort -- and recovers at least part of ACC20's edge over DEC20 "
        "while keeping most of S20's low turnover; in 2009-2015 FILT20's edge over total-return SPY "
        "is at most a point or two, the same shortfall every stock-net-share-issuance variant has "
        "shown so far (M0227, M0243, M0345, M0351, M0371)."
    ),
    expected_failure=(
        "Four ways, in order of likelihood. (1) The filter is a no-op in practice: if the names "
        "near the bottom of the level-ranked top twenty rarely carry a positive acceleration "
        "score, the veto fires on only a handful of month-years across the whole window and "
        "FILT20 lands statistically indistinguishable from UNFILT20 -- the two measures were never "
        "disagreeing enough to matter. (2) The filter fires on exactly the wrong names: a company "
        "whose buyback pace looks like it is slowing because it just finished a large one-time "
        "repurchase authorization is not in trouble, and vetoing it trades a real shrinker for a "
        "weaker one further down the list, so FILT20 lands BELOW UNFILT20. (3) The same 2009-2015 "
        "shortfall as the rest of the family: this is still a second-order cut of the same filings "
        "M0227 and M0371 already read, not a new data source, so it inherits whatever crowding or "
        "data-coverage shortfall they showed in the best-covered years. (4) The narrower combined "
        "pool (both measures must score, not just one) thins the book in the early, sparse-filing "
        "years below even M0371's own effective universe, and a book that sometimes holds fewer "
        "than twenty names reads as lower, choppier exposure rather than a cleaner signal. Any of "
        "these is a rejection; none is a reason to retune the zero threshold or add a size band to "
        "the veto afterward."
    ),
    candidates=(
        _v("UNFILT20", ConfirmParams(20, side="unfiltered", trend=None),
           "The 20 biggest shrinkers by level from the combined pool, no veto, no switch -- the "
           "no-opinion arm, same pool as FILT20"),
        _v("FILT20", ConfirmParams(20, side="filtered", trend=None),
           "The 20 biggest shrinkers by level, skipping any name whose recent pace has turned "
           "positive, no switch"),
        _v("FILT20-SW", ConfirmParams(20, side="filtered", trend=SW),
           "FILT20 behind the SPY 200-day switch"),
        _vm("PLC20", ConfirmParams(20, side="random", seed=1, trend=None),
            "Placebo, shape-matched: 20 names from the combined pool, matched to FILT20's own "
            "trade count and turnover by a monthly hash order (lab.control_draw), no switch"),
    ),
    seen_keys=(
        "concept:buyback-confirmation-filter",
    ),
)
