"""M0378 — Buyback confirmation filter on a yearly clock: M0375's level rank kept, its six-month
pace veto replaced with a year-over-year one.

Source: variation of M0375 (itself a variation of M0371, itself a variation of M0227, Pontiff &
Woodgate 2008). Reserved by Sera batch 20261026-0703 as an ``idea`` row; this file refines it and
keeps its id.

Idea. M0375 kept M0227's trailing-twelve-month level score as the only thing that decides ORDER
and used M0371's six-months-vs-prior-six-months pace-change score only to VETO a name: skip a
shrinker whose most recent half-year shrank its share count less than the half-year before it (or
reversed into issuance), and promote the next-best shrinker by level into the freed slot. Only the
switched variant cleared DSR (0.920); the plain filter made everything worse (DSR 0.681) and traded
roughly twice what the no-opinion arm traded, because a six-month pace estimate is the same noisy,
fast-moving number M0371 itself found costly when it tried to RANK on it -- a company near the
top-20 cutoff flips from "accelerating" to "decelerating" and back within a year on filing noise
alone, not a real change of direction (``lab show M0371``, ``lab show M0375``, 2026-10-26). This
variation keeps M0375's veto-and-promote construction unchanged and asks only whether a slower
clock -- a company's most recent twelve months of share-count change against the twelve months
before that, instead of six against six -- gives the same confirmation idea less to flip on. If the
churn was the six-month window's own noise rather than the confirmation idea itself, FILT20-YOY
should trade closer to its own no-opinion arm than M0375-FILT20 did to its. If the churn was never
the problem -- if the family's 2009-2015 shortfall is what sinks every cut of these filings
regardless of window length -- slowing the clock buys quieter trading and nothing else.

How. Each monthly check scores every index member on two measures built from the same filing
history M0227 already reads: the trailing-twelve-month log share-count change
(``m0227_net_share_shrinkers.issuance``, unmodified) decides order, and a year-over-year pace
change -- this year's issuance score minus last year's, read by calling M0227's own ``issuance()``
a second time at ``data_date`` minus ``LOOKBACK_DAYS`` -- decides the veto. Both measures reuse
M0227's identical missed-split and units-error guards (``looks_like_split``, ``RATIO_BAND``, the
180-day minimum count gap) unmodified; nothing here is retuned. A member scores only when BOTH the
current year's and the prior year's issuance score are available, so this file's pool needs three
point-in-time counts roughly a year apart (today, a year back, two years back), not the two a year
apart M0227 itself needs or the three six-months-apart M0371 and M0375 need -- strictly narrower
than either in the early, thin-filing years. The same identical-share-count dedupe every file in
this family uses (larger 60-session trading value wins) is applied once to the combined pool, so
UNFILT20-YOY and FILT20-YOY read the same universe and differ only in the filter.

Members are sorted by the level score, most negative (biggest shrinker) first -- M0227's own order,
restricted to this file's narrower pool. ``side="unfiltered"`` (UNFILT20-YOY) takes the top ``top``
names straight off that list: the no-opinion arm, run on the SAME pool as the treatment, so the
comparison is the filter and nothing else -- not a comparison against M0227's or M0375's own wider
pools. ``side="filtered"`` (FILT20-YOY) walks the same ordered list and skips any name whose
year-over-year pace score is positive -- its most recent twelve months shrank its share count less
than the twelve months before, or reversed into issuance -- continuing down the list until ``top``
names pass or the list runs out; a month where fewer than ``top`` names pass holds fewer names and
is reported as lower exposure, not papered over with a wider cut. The zero threshold is the same
reading of the sign M0371 and M0375 already defined and is fixed before any result. ``side="random"``
(PLC20-YOY, the matched-draw control, a separate allocator id) draws from the identical combined
pool, matched to the FILTERED arm's own trade count and turnover (``lab.control_draw.matched_book``),
because the filter -- not the unfiltered book -- is the thing whose cost in noise this run prices.

Assumptions written before any result. The dev window still trades from M0227's own start, but
later than M0227, M0371 or M0375 can: this file's pool needs a full two years of prior counts
(this year's issuance score and last year's each need their own year-back reading), so the earliest
a member can score is about two years after 1996, not one year (M0227) or roughly 1.5 (M0371,
M0375's combined pool). Market-aware (``market_fields = ("shares",)``): the history-only path has
no share counts, so by the contract it targets nothing. Rules are ``monthly-hold-frac-gotrade``:
fractional shares at Gotrade's real fees, asked monthly, on the owner's monthly top-up. Pure: reads
only bars and counts public on or before ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0198_size_weighted_placebo import trading_value
from seer_engine.lab.methods.m0227_net_share_shrinkers import DV_N, LOOKBACK_DAYS, issuance
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
                "veto_threshold": "yoy_pace>0", "veto_window_days": str(LOOKBACK_DAYS),
                "dv_n": str(DV_N), "class_rule": "identical-share-count"}


def _check(params: object) -> ConfirmParams:
    if not isinstance(params, ConfirmParams):
        raise TypeError(f"params must be ConfirmParams, got {type(params).__name__}")
    return params


def _gate(p: ConfirmParams) -> FactorParams:
    return FactorParams(rank="momentum", top=p.top, trend=p.trend)


def pace_change_yoy(market: Any, symbol: str, data_date: date) -> float | None:
    """This year's trailing-twelve-month log share-count change minus the twelve months before
    that, or None if either is missing. Reuses M0227's own ``issuance()`` window and guards twice
    rather than building a second implementation, so the veto reads on the same clock and the same
    split/units defences the level score does -- just one full turn of it earlier."""
    mid = data_date - timedelta(days=LOOKBACK_DAYS)
    recent = issuance(market, symbol, data_date)
    prior = issuance(market, symbol, mid)
    if recent is None or prior is None:
        return None
    return recent - prior


@dataclass(frozen=True, slots=True, eq=False)
class ConfirmPrepared:
    history: Mapping[str, History]
    market: Any  # the Market (share counts), or None on the history-only path


def combined_pool(prepared: ConfirmPrepared, members: AbstractSet[str],
                   data_date: date) -> dict[str, tuple[float, float]]:
    """symbol -> (level score, year-over-year pace score) for every member BOTH measures can score
    on ``data_date``, one listing per company (the identical-share-count dedupe this family uses)."""
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
        pace = pace_change_yoy(mk, s, data_date)
        if pace is None:
            continue
        n = mk.shares_on(s, data_date)
        dv = trading_value(h, data_date, DV_N)
        seen = by_count.get(n)
        if seen is None or (dv, s) > (seen[0], seen[1]):
            by_count[n] = (dv, s, level, pace)
    return {s: (level, pace) for _, s, level, pace in by_count.values()}


def ranked_book(pool: Mapping[str, tuple[float, float]], top: int, filtered: bool) -> tuple[str, ...]:
    """The level-ranked book from ``pool``: the ``top`` biggest shrinkers, skipping over any name
    the filter vetoes (a positive year-over-year pace score: its buyback is slowing or reversing)
    when ``filtered`` is True. Walks the SAME order either way, so a filtered book is the unfiltered
    book with some names removed and others promoted up to fill the slots, never re-sorted."""
    order = sorted(pool, key=lambda s: (pool[s][0], s))
    if not filtered:
        return tuple(order[:top])
    passing = [s for s in order if pool[s][1] <= 0.0]
    return tuple(passing[:top])


class ConfirmationAllocator:
    """The ``top`` biggest shrinkers by trailing-year level, equal slots, fully invested; with
    ``side="filtered"`` a name whose year-over-year buyback pace has turned positive (slowing or
    reversing) is skipped in favour of the next-best shrinker. Nothing while the switch, if any,
    is off. No share counts (history-only path): no targets. Does not run ``side="random"``; see
    ``MatchedDrawAllocator``."""

    id = "M0378"
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
    return Candidate(id=f"M0378-{suffix}", family="M0378", rules=MONTHLY_HOLD_FRAC_GOTRADE,
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
    """FILT20-YOY's shape with none of its identity: ``lab.control_draw``'s matched draw on this
    method's combined pool, matched to the ``side="filtered"`` book's own entries and turnover --
    because the filter, not the unfiltered rank, is the thing whose cost in noise this run prices."""

    id = "M0378-A1"
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
        """(the eligible pool, FILT20-YOY's own book) on ``data_date`` -- the filtered arm's own two."""
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
            data_date, held, tag="M0378", seed=p.seed,
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
    return Candidate(id=f"M0378-{suffix}", family="M0378", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                      allocator=MATCHED, params=params, rationale=rationale, added=ADDED,
                      owner_inputs=())


METHOD = Method(
    id="M0378",
    name=(
        "Buyback confirmation filter on a year-over-year clock, not six months"
    ),
    family="stock-net-share-issuance",
    source_kind="variation",
    source_ref="M0375",
    parent_id="M0375",
    hypothesis=(
        "M0375's six-months-against-six-months pace check flipped sign too often near the cutoff "
        "of the top-20 list, nearly doubling the book's trading without any return benefit -- only "
        "FILT20-SW cleared DSR (0.920); FILT20 alone made every metric worse (DSR 0.681) ('lab show "
        "M0375', 2026-10-26). This variation keeps M0375's veto-and-promote construction exactly "
        "and asks whether comparing a full year's buyback pace against the year before it, instead "
        "of six months against six, is slow-moving enough to keep the same confirmation idea without "
        "the sign-flipping churn. Book: FILT20-YOY, the 20 biggest trailing-twelve-month shrinkers "
        "by level from a pool scorable on both the level measure and the year-over-year pace "
        "measure, with the veto applied (skip a name whose most recent twelve months shrank its "
        "share count less than the twelve months before, or reversed into issuance); equal slots, "
        "monthly, fractional shares at Gotrade's real fees on the owner's monthly top-up "
        "(monthly-hold-frac-gotrade). Controls: UNFILT20-YOY, the same pool and the same level "
        "order with no veto (the no-opinion arm, isolating the filter itself on this file's own, "
        "narrower pool -- not M0375's or M0227's wider ones); FILT20-YOY-SW, FILT20-YOY behind the "
        "SPY 200-day switch; PLC20-YOY, a frame-matched blind draw from the same pool, matched to "
        "FILT20-YOY's own trade count and turnover (lab.control_draw), not UNFILT20-YOY's, because "
        "the filter is the thing whose noise this run is pricing. Window: M0227's own start, but "
        "later than M0375's pool opens, since a year-over-year pace reading needs two full years of "
        "prior counts rather than M0375's roughly 1.5. Predictions written before any result: "
        "trading drops versus M0375-FILT20 -- a yearly veto reading changes sign far less often than "
        "a six-month one estimated on overlapping, noisier filing gaps -- but the book likely still "
        "only clears the pool at a cost, not a clean win: the family's 2009-2015 shortfall is a "
        "property of these filings at any window length (M0227, M0243, M0345, M0351, M0371, M0375), "
        "and a slower-firing veto has fewer chances to catch a buyback that is really turning sour "
        "before the next monthly check, which cuts the other way against FILT20-YOY's return."
    ),
    expected_failure=(
        "Four ways, in order of likelihood. (1) Quieter but no better: FILT20-YOY trades closer to "
        "its own no-opinion arm than M0375-FILT20 did to its, confirming the six-month clock was "
        "the source of the churn -- but the veto still fires on so few months, or on names whose "
        "removal does not change the realised return, that FILT20-YOY lands statistically "
        "indistinguishable from UNFILT20-YOY: a quieter no-op is still a no-op. (2) The slower clock "
        "misses what the faster one caught: a buyback that is genuinely turning sour inside a single "
        "year shows up in the six-month veto a check or two sooner than in the year-over-year one, "
        "so FILT20-YOY holds a name through more of its own deterioration than FILT20 did and lands "
        "BELOW it on return or fall despite trading less. (3) The same 2009-2015 shortfall as the "
        "rest of the family: this is still a second-order cut of the same filings M0227, M0371 and "
        "M0375 already read, not a new data source, so it inherits whatever crowding or "
        "data-coverage shortfall they showed in the best-covered years regardless of the veto's "
        "clock speed. (4) The narrower, later-opening pool (needing two full years of prior counts, "
        "not 1.5) thins the book in the early years below even M0375's own effective universe, and a "
        "book that sometimes holds fewer than twenty names, or starts trading later, reads as lower, "
        "choppier exposure rather than a cleaner signal. Any of these is a rejection; none is a "
        "reason to retune the zero threshold or the window length afterward."
    ),
    candidates=(
        _v("UNFILT20-YOY", ConfirmParams(20, side="unfiltered", trend=None),
           "The 20 biggest shrinkers by level from the combined pool, no veto, no switch -- the "
           "no-opinion arm, same pool as FILT20-YOY"),
        _v("FILT20-YOY", ConfirmParams(20, side="filtered", trend=None),
           "The 20 biggest shrinkers by level, skipping any name whose year-over-year pace has "
           "turned positive, no switch"),
        _v("FILT20-YOY-SW", ConfirmParams(20, side="filtered", trend=SW),
           "FILT20-YOY behind the SPY 200-day switch"),
        _vm("PLC20-YOY", ConfirmParams(20, side="random", seed=1, trend=None),
            "Placebo, shape-matched: 20 names from the combined pool, matched to FILT20-YOY's own "
            "trade count and turnover by a monthly hash order (lab.control_draw), no switch"),
    ),
    seen_keys=(
        "concept:buyback-confirmation-filter-yoy",
    ),
)
