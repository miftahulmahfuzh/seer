"""M0371 — Buyback acceleration: rank shrinkers by how fast their pace is speeding up, not its level.

Source: variation of M0227 (Pontiff & Woodgate 2008 net share issuance). Reserved by Sera batch
20261026-0703 as an ``idea`` row; this file refines it and keeps its id.

Idea. M0227 ranks index members on the level of net share-count shrinkage over the trailing
twelve months: it beats a random draw and total-return SPY before 2009, but its switched variant
(M0227-S20-SW) is dev-eligible and still refused promotion -- its own walk-forward pick wins only
2 of the 4 folds, even though S20-SW held fixed across every fold wins 3 of 4 (``lab status``,
2026-10-26). This variation asks a narrower question: does the CHANGE in pace -- shrinkage over
the most recent six months compared with shrinkage over the six months before that -- carry
information the trailing twelve-month level does not. The construction mirrors the acceleration
already used for price momentum (``f_factor``): split one lookback window in two and score the
difference. A company stepping up its buyback pace may be a different signal from one that has
bought back the same steady amount all year, even though both can show an identical trailing-year
level.

How. On each monthly check, for every scorable index member: read the share count at
``data_date``, at ``data_date`` minus ``HALF_DAYS`` (about six months), and at ``data_date`` minus
``2 * HALF_DAYS`` (about a year), each carried across splits exactly as M0227 reads them
(``ShareCounts.split_factor``), using the same missed-split and units-error guards M0227 already
defines (``looks_like_split``, ``RATIO_BAND``, imported rather than copied), applied separately to
each half so a split inside one half does not leak into the other's ratio. The recent half's log
change and the prior half's log change are each required to come from counts at least
``MIN_HALF_GAP_DAYS`` apart -- half of M0227's 180-day bar, because each half is itself half as
long. The score is ``recent - prior``: more negative means the company is shrinking its share
count faster now than it was six months ago. ``side="accel"`` holds the ``top`` fastest-
accelerating shrinkers; ``side="decel"`` the opposite book (shrinkage pace slowing, or tipping into
fresh issuance); ``side="random"`` is the control, a blind draw from the same scored pool matched
to ``side="accel"``'s own trade count and turnover (``lab.control_draw.matched_book``) rather than
a date-free hash order. M0227's own R20 control was found, after it ran, to trade 0.07x its arm
and needed an amendment to fix; this file builds the matched draw in from the start instead of
repeating that mistake. Two members answering the identical share count on the same day are one
company listed twice; only the one with the larger 60-session trading value is kept, same as M0227.

Assumptions written before any result. Halving the window halves the filing gap each half-score is
built on, so this book's pool is a strict subset of M0227's: a member must answer three point-in-
time counts spaced roughly six months apart, not two spaced a year apart, so a company that files
only annually scores on the level measure and not on this one. The dev window still trades
1997-2015 (M0227's own one-year lead-in already pays for this file's two six-month ones). Market-
aware (``market_fields = ("shares",)``): the history-only path has no share counts, so by the
contract it targets nothing. Rules are ``monthly-hold-frac-gotrade``: fractional shares at
Gotrade's real fees, asked monthly, on the owner's monthly top-up. Pure: reads only bars and counts
public on or before ``data_date``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0198_size_weighted_placebo import trading_value
from seer_engine.lab.methods.m0227_net_share_shrinkers import DV_N, RATIO_BAND, looks_like_split
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED, FactorParams, trend_on

ADDED = date(2026, 10, 26)
HALF_DAYS = 182  # each half roughly six calendar months; 2 * HALF_DAYS = 364, four days short of
                 # M0227's 365, which costs nothing since both windows read the same point-in-time counts
MIN_HALF_GAP_DAYS = 90  # half of M0227's 180-day bar: each half is itself half as long
SIDES = ("accel", "decel", "random")


@dataclass(frozen=True, slots=True)
class AccelParams:
    """``top`` names held; ``side`` accel, decel or random (the matched-draw control); ``seed`` the
    control's draw seed; ``trend`` the switch, (symbol, n) or None, set by every variant."""

    top: int
    side: str = "accel"
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
                "half_days": str(HALF_DAYS), "min_half_gap_days": str(MIN_HALF_GAP_DAYS),
                "ratio_band": f"{RATIO_BAND[0]!r}:{RATIO_BAND[1]!r}", "dv_n": str(DV_N),
                "class_rule": "identical-share-count"}


def _check(params: object) -> AccelParams:
    if not isinstance(params, AccelParams):
        raise TypeError(f"params must be AccelParams, got {type(params).__name__}")
    return params


def _gate(p: AccelParams) -> FactorParams:
    return FactorParams(rank="momentum", top=p.top, trend=p.trend)


def half_issuance(market: Any, symbol: str, newer: date, older: date) -> float | None:
    """Log change in ``symbol``'s split-adjusted share count between ``older`` and ``newer``."""
    shares = market.shares
    new_c, old_c = shares.count(symbol, newer), shares.count(symbol, older)
    if new_c is None or old_c is None:
        return None
    if (new_c.counted - old_c.counted).days < MIN_HALF_GAP_DAYS:
        return None
    new_n, old_n = shares.shares_on(symbol, newer), shares.shares_on(symbol, older)
    if new_n is None or old_n is None or not (new_n > 0.0 and old_n > 0.0):
        return None
    ratio = new_n / (old_n * shares.split_factor(symbol, older, newer))
    if not math.isfinite(ratio) or not RATIO_BAND[0] < ratio < RATIO_BAND[1] or looks_like_split(ratio):
        return None
    return math.log(ratio)


def acceleration(market: Any, symbol: str, data_date: date) -> float | None:
    """Recent six-month log change minus prior six-month log change, or None if either is missing."""
    mid = data_date - timedelta(days=HALF_DAYS)
    old = data_date - timedelta(days=2 * HALF_DAYS)
    recent = half_issuance(market, symbol, data_date, mid)
    prior = half_issuance(market, symbol, mid, old)
    if recent is None or prior is None:
        return None
    return recent - prior


@dataclass(frozen=True, slots=True, eq=False)
class AccelPrepared:
    history: Mapping[str, History]
    market: Any  # the Market (share counts), or None on the history-only path


def scored_pool(prepared: AccelPrepared, members: AbstractSet[str], data_date: date) -> dict[str, float]:
    """The acceleration score of every member that can be held on ``data_date``, one listing per company."""
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
        score = acceleration(mk, s, data_date)
        if score is None:
            continue
        n = mk.shares_on(s, data_date)
        dv = trading_value(h, data_date, DV_N)
        seen = by_count.get(n)
        if seen is None or (dv, s) > (seen[0], seen[1]):
            by_count[n] = (dv, s, score)
    return {s: score for _, s, score in by_count.values()}


class AccelerationAllocator:
    """The ``top`` members whose buyback pace is accelerating fastest (or decelerating fastest),
    equal slots, fully invested; nothing while the switch, if any, is off. No share counts
    (history-only path): no targets. Does not run ``side="random"``; see ``MatchedDrawAllocator``."""

    id = "M0371"
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

    def _run(self, prepared: AccelPrepared, members: AbstractSet[str], data_date: date,
             p: AccelParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, _gate(p)):
            return ()
        pool = scored_pool(prepared, members, data_date)
        if not pool:
            return ()
        if p.side == "accel":
            order = sorted(pool, key=lambda s: (pool[s], s))
        elif p.side == "decel":
            order = sorted(pool, key=lambda s: (-pool[s], s))
        else:
            raise ValueError("AccelerationAllocator does not run side='random'; use MatchedDrawAllocator")
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
        return self._run(AccelPrepared(history, None), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> AccelPrepared:
        return AccelPrepared(history, None)

    def prepare_market(self, market: Any) -> AccelPrepared:
        if not hasattr(market, "shares") or len(market.shares) == 0:
            return AccelPrepared(market.history, None)
        return AccelPrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, AccelPrepared):
            raise TypeError(f"prepared must be AccelPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


ACCEL = AccelerationAllocator()

SW = ("SPY", 200)


def _v(suffix: str, params: AccelParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0371-{suffix}", family="M0371", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=ACCEL, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


def _check_control(params: object) -> AccelParams:
    """``AccelParams``, plus the one thing a control's params may not say.

    The matched draw differs from a ranked arm in its allocator id and in nothing else, so the
    params must still read ``side="random"``: a blind book must not describe itself as a ranked one.
    """
    if not isinstance(params, AccelParams):
        raise TypeError(f"params must be AccelParams, got {type(params).__name__}")
    if params.side != "random":
        raise ValueError(f"the matched draw is a control: side must be 'random', got {params.side!r}")
    return params


class MatchedDrawAllocator:
    """ACC20's shape with none of its identity: ``lab.control_draw``'s matched draw on this
    method's scored pool, matched to the ``side="accel"`` book's own entries and turnover (built
    in from the start rather than amended afterwards, as M0227-A1 had to be)."""

    id = "M0371-A1"
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

    def _select(self, prepared: AccelPrepared, members: AbstractSet[str], data_date: date,
                p: AccelParams) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """(the eligible pool, ACC20's own book) on ``data_date`` -- the accel arm's own two."""
        pool = scored_pool(prepared, members, data_date)
        if not pool:
            return (), ()
        order = sorted(pool, key=lambda s: (pool[s], s))
        return tuple(sorted(pool)), tuple(order[: p.top])

    def _run(self, prepared: AccelPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: AccelParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        gate = FactorParams(rank="momentum", top=p.top, trend=p.trend)
        if not trend_on(prepared.history, data_date, gate):
            return ()
        names = control_draw.matched_book(
            lambda d: self._select(prepared, members, d, p),
            data_date, held, tag="M0371", seed=p.seed,
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
        return self._run(AccelPrepared(history, None), members, data_date, held,
                         _check_control(params))

    def prepare(self, history: Mapping[str, History]) -> AccelPrepared:
        return AccelPrepared(history, None)

    def prepare_market(self, market: Any) -> AccelPrepared:
        if not hasattr(market, "shares") or len(market.shares) == 0:
            return AccelPrepared(market.history, None)
        return AccelPrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, AccelPrepared):
            raise TypeError(f"prepared must be AccelPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check_control(params))


MATCHED = MatchedDrawAllocator()


def _vm(suffix: str, params: AccelParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0371-{suffix}", family="M0371", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MATCHED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0371",
    name=(
        "Buyback acceleration: rank shrinkers by how fast their buyback pace is speeding up, not "
        "just its level"
    ),
    family="stock-net-share-issuance",
    source_kind="variation",
    source_ref="M0227",
    parent_id="M0227",
    hypothesis=(
        "M0227 ranks index members on the level of net share-count shrinkage over the trailing "
        "year and is dev-eligible, but its switched variant is refused promotion because its own "
        "walk-forward pick wins only 2 of 4 folds (lab status, 2026-10-26), even though the fixed "
        "S20-SW variant alone wins 3 of 4. This variation asks whether the CHANGE in pace -- "
        "shrinkage over the most recent six months compared with shrinkage over the prior six "
        "months, the same acceleration construction already used for price momentum -- carries "
        "information the trailing twelve-month level does not. Book: the 20 names whose buyback "
        "pace is accelerating fastest (ACC20), equal slots, monthly, fractional shares at "
        "Gotrade's real fees on the owner's monthly top-up (monthly-hold-frac-gotrade). Controls: "
        "the 20 names whose pace is decelerating fastest (DEC20, the opposite book) and a "
        "frame-matched blind draw from the same scored pool (PLC20, matched to ACC20's own trade "
        "count and turnover by lab.control_draw rather than a date-free hash order). ACC20-SW adds "
        "the SPY 200-day switch. Window: 1997-2015 (M0227's one-year lead-in already covers this "
        "file's two six-month ones). Predictions written before any result: ACC20 beats DEC20 and "
        "PLC20 by a point or two a year, mostly before 2009, echoing M0227's own era split; in "
        "2009-2015 ACC20's edge over total-return SPY is at most a point, the same shortfall the "
        "whole stock-net-share-issuance family has shown on every variant tried so far (M0227, "
        "M0243, M0345, M0351). Compared directly against M0227's own S20 (same window, same fees), "
        "ACC20 does NOT clearly beat it: differencing two six-month windows roughly doubles the "
        "measurement noise of one twelve-month level estimate, so the acceleration book is expected "
        "to land close to or below S20, not meaningfully above it."
    ),
    expected_failure=(
        "Four ways, in order of likelihood. (1) Noise doubling: a six-month shrinkage estimate is "
        "noisier than a twelve-month one, and differencing two of them (recent minus prior) "
        "compounds that noise rather than cancelling it, so ACC20 reads as a weaker, jumpier "
        "version of M0227-S20 with a similar or worse Sharpe and no information the level did not "
        "already carry. (2) The same 2009-2015 shortfall as the rest of the family: all four prior "
        "stock-net-share-issuance variants (M0227, M0243, M0345, M0351) trail or barely match SPY "
        "in the dev store's best-covered, most recent years, and acceleration is a second-order cut "
        "of the same underlying filings, not a new data source, so it inherits the same shortfall. "
        "(3) A thinner pool than M0227's: each half-window needs its own 90-day-apart pair of "
        "counts, so a company that files close to once a year (common among smaller or newly "
        "public index members) scores on the level measure but not on this one, shrinking ACC20's "
        "effective universe below S20's and widening both books' variance. (4) Decay: Pontiff and "
        "Woodgate published the level effect in 2008 and this measure is a derivative cut of the "
        "same filings, so if the level itself is partly crowded by 2009-2015, its rate of change is "
        "at least as crowded. Any of these is a rejection; none is a reason to retune HALF_DAYS or "
        "the guards afterwards."
    ),
    candidates=(
        _v("ACC20", AccelParams(20, side="accel", trend=None),
           "The 20 members whose buyback pace is accelerating fastest, no switch"),
        _v("ACC20-SW", AccelParams(20, side="accel", trend=SW),
           "The same 20 fastest-accelerating shrinkers behind the SPY 200-day switch"),
        _v("DEC20", AccelParams(20, side="decel", trend=None),
           "Opposite: the 20 members whose buyback pace is decelerating fastest (or tipping into "
           "fresh issuance), no switch"),
        _vm("PLC20", AccelParams(20, side="random", seed=1, trend=None),
            "Frame-matched blind draw: 20 names from the same scored pool, matched to ACC20's own "
            "trade count and turnover, no switch"),
    ),
    seen_keys=(
        "concept:buyback-acceleration",
    ),
)
