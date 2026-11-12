"""M0583 -- Round-number price barrier: stocks just above a round-dollar close vs just below.

Source: Donaldson & Kim, "Round Numbers and Security Returns"; Shiller (2015) on anchoring.
Reserved by Sera batch 20261112-1645 as an ``idea`` row; this file refines it and keeps its id.

Idea. Shiller (2015) and Donaldson & Kim argue investors anchor on round-dollar prices as a
psychological reference point: a stock that has just traded above $50 is read as having "cleared"
resistance and may keep drifting, while one sitting just under $50 is read as still facing it. No
method in this lab has ranked on proximity to a round number before. The nearest kin rank on the
printed price *level* itself (M0383/M0531/M0536, "stock-nominal-price-level") -- this is a
different claim: it says nothing about whether $12 beats $120, only whether $50.10 beats $49.90.

How. A barrier is defined by a two-tier scheme, the one M0583's own pre-registration names: the
nearest *whole dollar* for a printed price under $100, the nearest *round ten* at or above it --
so a stock's barrier step is $1 below $100 and $10 from $100 up (``round_step``). The signed gap
to that barrier, as a fraction of the step (``gap_frac = (price - nearest_round) / step``, always
in [-0.5, 0.5]), is scale-free across both tiers: a stock five cents above its nearest dollar and
one fifty cents above its nearest ten are read as equally "just cleared". Each monthly check reads
one pool and every arm selects from it: an index member (excluding SPY) with a bar on
``data_date``, a 20-session mean dollar volume above $20 million (``f_factor``'s own floor,
unchanged), and a **printed** price of at least $5 -- the close as it actually traded, not the
store's back-adjusted one, recovered as ``close * Market.shares.raw_factor`` (``price_floor``,
the module M0383 built and M0387 repaired the $5 floor with). A round-number barrier is a fact
about the number a ticker tape actually printed; ranking on the back-adjusted close would ask,
for a stock trading at $27.50 in 1998 and stored today at $0.25 after seven splits, whether $0.25
is near a round dollar -- a question nobody standing at a terminal in 1998 could have asked.
``side`` then ranks that pool and holds, equal slots, fully invested, no trend switch (the idea is
read in isolation from the lab's market-wide gate, which is a separate, already well-studied axis):

* ``"above"`` (ABOVE20) -- up to 20 names with the smallest *positive* ``gap_frac``: the printed
  close just cleared its nearest round number from below. The treatment.
* ``"below"`` (BELOW20) -- up to 20 names with the smallest-magnitude *negative* ``gap_frac``:
  the printed close sits just under its nearest round number, not yet cleared. The mirror: run
  beside its own inversion, it shows whether the signal is real and says nothing about what
  acting on it costs.
* ``"random"`` (BLIND20) -- the no-opinion arm, a separate allocator id: ``lab.control_draw``'s
  frame-matched blind draw from the identical pool, matched to ABOVE20's own book size, entry
  count and turnover. ABOVE20 and BELOW20 pay the same trading cost and it cancels between them;
  without this arm the run could tell a real signal from a lucky one and could not tell a dead
  rule from a badly dressed one (insight 523).

Assumptions, fixed before any result. Two listings of one company (e.g. GOOG/GOOGL) are scored
and may both be held: a round-number barrier is a fact about the specific quoted price a listing
prints, not a company fundamental, so there is no reason one listing's barrier position should
stand in for the other's, unlike the size- or price-level-ranked files in this lab that dedupe by
share count. The $5/$20M screen is expected to run 140-400 names a month, the same order as
M0383's pool (same floors, same universe). The two-tier step is a modelling choice, not a fitted
one: it is the scheme M0583's own idea row named before this file existed ("whole dollar, or
round ten for higher-priced names"), and no other threshold was tried. Market-aware
(``market_fields = ("shares",)``): the history-only path has no splits, so by the contract it
targets nothing. Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real
fees, asked monthly, on the owner's monthly top-up. Pure: reads only bars and splits public on or
before ``data_date``.
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
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import DV_N, EXCLUDED
from seer_engine.strategies.price_floor import MIN_PRICE, PRINTED, check_market, printed_close

ADDED = date(2026, 11, 12)

MIN_DOLLAR_VOLUME = 20_000_000.0
"""``f_factor``'s own floor, unchanged, on a split-invariant dollar-volume read."""

SIDES = ("above", "below", "random")


def round_step(price: float) -> float:
    """$1 below $100, $10 at or above it -- the two-tier scheme this idea was reserved with."""
    return 1.0 if price < 100.0 else 10.0


def nearest_round_number(price: float) -> float:
    """The nearest round number to ``price`` under :func:`round_step`'s two-tier scheme."""
    step = round_step(price)
    return round(price / step) * step


@dataclass(frozen=True, slots=True)
class BarrierParams:
    """``top`` names held per side; ``side`` one of :data:`SIDES`; ``seed`` the blind draw's seed."""

    top: int
    side: str = "above"
    seed: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 200:
            raise ValueError(f"top must be an int in [1, 200], got {self.top!r}")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")

    def as_dict(self) -> dict[str, str]:
        return {
            "top": str(self.top),
            "side": self.side,
            "seed": str(self.seed),
            "min_printed_price": str(MIN_PRICE),
            "min_dollar_volume": str(MIN_DOLLAR_VOLUME),
            "dv_n": str(DV_N),
            "price_basis": "printed",
            "barrier_scheme": "dollar-below-100-ten-above",
        }


def _check(params: object) -> BarrierParams:
    if not isinstance(params, BarrierParams):
        raise TypeError(f"params must be BarrierParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True, eq=False)
class BarrierPrepared:
    history: Mapping[str, History]
    market: Any  # the Market (splits), or None on the history-only path


@dataclass(frozen=True, slots=True)
class PoolRow:
    gap_frac: float  # (printed close - nearest round number) / step; in [-0.5, 0.5]


def eligible_pool(prepared: BarrierPrepared, members: AbstractSet[str],
                  data_date: date) -> dict[str, PoolRow]:
    """symbol -> :class:`PoolRow` for every member clearing the screen on ``data_date``: a bar
    dated ``data_date``; a 20-session mean dollar volume strictly above $20 million; a printed
    price of at least $5 (``price_floor.MIN_PRICE``, read on the printed close)."""
    mk = prepared.market
    if mk is None:
        return {}
    check_market(mk, PRINTED)
    out: dict[str, PoolRow] = {}
    for s in sorted(members):
        if s in EXCLUDED:
            continue
        h = prepared.history.get(s)
        if h is None:
            continue
        p = printed_close(h, mk, s, data_date)
        if p is None or p < MIN_PRICE:
            continue
        if trading_value(h, data_date, DV_N) <= MIN_DOLLAR_VOLUME:
            continue
        step = round_step(p)
        gap_frac = (p - nearest_round_number(p)) / step
        out[s] = PoolRow(gap_frac=gap_frac)
    return out


def ranked_book(pool: Mapping[str, PoolRow], top: int, side: str) -> tuple[str, ...]:
    """The ``top`` names closest to a round-number barrier on ``side``, out of ``pool``. Ties
    break on the symbol, so the book is a pure function of the pool and never of dict order."""
    if side == "above":
        order = sorted(
            (s for s in pool if pool[s].gap_frac > 0.0),
            key=lambda s: (pool[s].gap_frac, s),
        )
    elif side == "below":
        order = sorted(
            (s for s in pool if pool[s].gap_frac < 0.0),
            key=lambda s: (-pool[s].gap_frac, s),
        )
    else:
        raise ValueError(f"ranked_book does not serve side={side!r}")
    return tuple(order[:top])


class BarrierAllocator:
    """The ``top`` names closest to a round-dollar barrier on one side, equal slots, fully
    invested, no trend switch. No splits (the history-only path): no targets. Does not run
    ``side="random"``; see :class:`MatchedDrawAllocator`."""

    id = "M0583"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        _check(params)
        return DV_N

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: BarrierPrepared, members: AbstractSet[str], data_date: date,
             p: BarrierParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if p.side == "random":
            raise ValueError("BarrierAllocator does not run side='random'; use MatchedDrawAllocator")
        pool = eligible_pool(prepared, members, data_date)
        if not pool:
            return ()
        w = equal_weight(p.top)
        out: list[Target] = []
        for s in ranked_book(pool, p.top, p.side):
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no splits, so no printed price and no target."""
        return self._run(BarrierPrepared(history, None), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> BarrierPrepared:
        return BarrierPrepared(history, None)

    def prepare_market(self, market: Any) -> BarrierPrepared:
        if not hasattr(market, "shares") or not market.shares.has_splits():
            return BarrierPrepared(market.history, None)
        return BarrierPrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, BarrierPrepared):
            raise TypeError(f"prepared must be BarrierPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


BARRIER = BarrierAllocator()


def _check_control(params: object) -> BarrierParams:
    """``BarrierParams``, plus the one thing a control's params may not say: a blind book must
    not describe itself as a ranked one, so ``side`` must read ``"random"``."""
    p = _check(params)
    if p.side != "random":
        raise ValueError(f"the matched draw is a control: side must be 'random', got {p.side!r}")
    return p


class MatchedDrawAllocator:
    """ABOVE20's shape with none of its opinion: ``lab.control_draw``'s frame-matched draw from
    this file's own pool, matched to the ``side="above"`` book's size, entry count and turnover.
    ABOVE20 and BELOW20 pay the same trading cost and it cancels between them; this arm prices it."""

    id = "M0583-A1"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        _check_control(params)
        return control_draw.lookback_for(DV_N)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check_control(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check_control(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check_control(params)
        return True

    def _select(self, prepared: BarrierPrepared, members: AbstractSet[str], data_date: date,
                p: BarrierParams) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """(the eligible pool, ABOVE20's own book) on ``data_date``."""
        pool = eligible_pool(prepared, members, data_date)
        if not pool:
            return (), ()
        return tuple(sorted(pool)), ranked_book(pool, p.top, "above")

    def _run(self, prepared: BarrierPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: BarrierParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        names = control_draw.matched_book(
            lambda d: self._select(prepared, members, d, p),
            data_date, held, tag="M0583", seed=p.seed,
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
        """The history-only path: no splits, so no pool and no target."""
        return self._run(BarrierPrepared(history, None), members, data_date, held,
                         _check_control(params))

    def prepare(self, history: Mapping[str, History]) -> BarrierPrepared:
        return BarrierPrepared(history, None)

    def prepare_market(self, market: Any) -> BarrierPrepared:
        if not hasattr(market, "shares") or not market.shares.has_splits():
            return BarrierPrepared(market.history, None)
        return BarrierPrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, BarrierPrepared):
            raise TypeError(f"prepared must be BarrierPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check_control(params))


MATCHED = MatchedDrawAllocator()


def _v(suffix: str, params: BarrierParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0583-{suffix}", family="M0583", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BARRIER, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


def _vm(suffix: str, params: BarrierParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0583-{suffix}", family="M0583", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MATCHED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0583",
    name="Round-number price barrier: stocks just above a round-dollar close vs just below",
    family="stock-round-number-barrier",
    source_kind="paper",
    source_ref=(
        'Donaldson & Kim, "Round Numbers and Security Returns"; Shiller (2015) on anchoring; '
        "web search 2026-11-12 (emerald.com, efmaefm.org, core.ac.uk summaries)"
    ),
    parent_id=None,
    hypothesis=(
        "Shiller (2015) and Donaldson & Kim argue investors anchor on round-dollar prices as a "
        "psychological reference point -- a stock trading just above a round number (e.g. "
        "$50.10) is read as having cleared resistance and may keep drifting, while one just below "
        "($49.90) sits at the barrier. No method in this lab has ranked on proximity to a round "
        "number before; the nearest kin rank on the printed price level itself "
        "(M0383/M0531/M0536, stock-nominal-price-level), which is a claim about $12 vs $120, not "
        "about $50.10 vs $49.90, and this file is explicitly distinct from it. Barrier defined by "
        "a two-tier scheme named in this idea's own pre-registration: nearest whole dollar for a "
        "printed price under $100, nearest round ten at or above it; the signed gap to that "
        "barrier as a fraction of the step is scale-free across both tiers. Book: ABOVE20, up to "
        "20 names with the smallest positive gap (just cleared) among index members (ex-SPY) "
        "clearing a $20 million dollar-volume floor (f_factor's own, split-invariant) and a $5 "
        "printed-price floor (price_floor's own number, read on the close as it actually traded, "
        "not the store's back-adjusted one) -- ranking on the back-adjusted close would ask "
        "whether a stock stored today at $0.25 after seven splits is near a round dollar, a "
        "question nobody at a terminal in 1998 could have asked, when it printed at $27.50. "
        "Controls: BELOW20, the same pool ranked the other way (the mirror, which shows whether "
        "the signal is real and cannot price what acting on it costs); BLIND20, a frame-matched "
        "blind draw from the identical pool matched to ABOVE20's own size, entries and turnover "
        "(the no-opinion arm that does price it). No trend switch: this file reads the "
        "stock-selection signal in isolation from the lab's market-wide gate, a separate, "
        "already well-studied axis (M0007/M0287 family)."
    ),
    expected_failure=(
        "Four ways, in order of likelihood. (1) No readable signal at all. ABOVE20 and BELOW20 "
        "land inside the blind draw's own width -- 19 blind rules span 7.5 points a year in this "
        "lab, and one draw is not a control -- so the pair proves nothing and the honest verdict "
        "is that the effect, if real, is smaller than this chassis can read. (2) Published and "
        "faded. Donaldson & Kim is an older paper and Shiller 2015 popularised the idea further; "
        "the dev window ends in 2015, so a clean dev win can only show the edge from before "
        "quant desks started placing orders deliberately away from round numbers to avoid this "
        "exact exploitation, which several market-microstructure papers document as having "
        "happened by the 2000s. (3) It is a price-level effect wearing a different label. A $1 "
        "step below $100 is a much larger relative move than a $10 step above $100, so ABOVE20 "
        "and BELOW20 may simply tilt toward cheaper names the same way M0383's LOW20 does (that "
        "method's cheap book skewed heavily toward banks after 2008); if ABOVE20's holdings "
        "overlap M0383's LOW20 book materially, this idea has not separated from the family it "
        "claims to be distinct from. (4) 2009-2015 says no. Every twenty-year edge this lab has "
        "found was earned before 2009, and three of four roster strategies were already negative "
        "in 2009-2015 on dev years before the test window confirmed it. If ABOVE20's lead is all "
        "pre-2009 it is not worth a variation however good its average."
    ),
    candidates=(
        _v("ABOVE20", BarrierParams(top=20, side="above"),
           "The treatment: up to 20 names with the smallest positive gap to their nearest round-"
           "dollar barrier (just cleared it)."),
        _v("BELOW20", BarrierParams(top=20, side="below"),
           "The mirror: the same pool ranked the other way, so a real signal shows as a spread."),
        _vm("BLIND20", BarrierParams(top=20, side="random", seed=583),
            "The no-opinion arm: a blind draw from the identical pool matched to ABOVE20's own "
            "size, entries and turnover, which is the only thing here that prices what acting "
            "costs."),
    ),
    seen_keys=(
        "concept:round-number-barrier",
        "concept:anchoring-round-dollar",
        "concept:nominal-price-level",  # distinct from, but neighbours, M0383's family
    ),
)
