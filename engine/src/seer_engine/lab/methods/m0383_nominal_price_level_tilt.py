"""M0383 -- Nominal price level: rank index members on the dollar price that actually printed.

Source: Green & Hwang (2009), "Price-Based Return Comovement", Journal of Financial Economics;
Birru & Wang (2016), "Nominal Price Illusion", Journal of Financial and Quantitative Analysis.
Reserved by Sera batch 20261026-1017 as an ``idea`` row; this file refines it and keeps its id.

Idea. A share's raw dollar price is close to economically meaningless: a company that is worth the
same amount can print $12 a share or $1,200 a share depending only on how often its board has split
the stock. Both papers argue investors nonetheless respond to the number itself -- low-priced
shares attract lottery-seeking, retail-driven demand and come to move together as a group, a
"cheapness illusion" that is supposed to be independent of company size. No method in this lab has
ranked on the printed price level before. The nearest kin rank on something else entirely: the
lottery-avoidance book ranks on extreme daily returns (M0091, rejected -- the calm stocks tied SPY
and fell 30%), the expected-skewness book on a modelled forecast (M0342, dev-eligible but beaten by
random picks behind the same switch, and 7.3 points a year behind SPY in 2009-2015).

**The number the store hands you is not the number that printed.** The research store's closes are
back-adjusted for every split the vendor applied, so a company that split a lot reads far cheaper
in the early years than it ever traded. Apple's close on 1998-06-15 is stored as $0.25; it printed
at $27.50 that day. Nvidia's 2013 close is stored as $0.36 and printed at $14.49. Netflix's
2013-06-17 close is stored as $3.27 and printed at $229.23. The printed price is recoverable, and
only since splits arrived in the store (2026-10-17/18): ``Market.shares.raw_factor(symbol, d)`` is
the product of every split effective after ``d``, so ``close * raw_factor`` is the price as it
printed, which this file checked against five known real-world closes before it was written (AAPL
$645.57 on 2014-06-06 and $94.25 on 2014-06-10 across its 7:1 split, GOOGL $693.02 and AMZN $562.44
on 2015-10-15, KO $61.06 on 2000-01-14). Volume is split-adjusted in the same direction, so
close * volume is already split-invariant and the dollar-volume floor needs no repair.

How. Each monthly check builds one pool and every arm reads it: an index member with a bar on
``data_date``, a 20-session mean dollar volume above $20 million (F4's own floor, unchanged, and
leak-free), a printed price of at least $5 (F4's own floor, applied to the printed number instead
of the adjusted one), and a known point-in-time company size. The identical-share-count dedupe
this lab's size-aware files use is applied once to that pool -- the listing with the larger
60-session trading value wins -- so one company occupies one slot and Google's two tickers before
2014 do not take two. ``side`` then decides the book, equal slots, fully invested:

* ``"low"`` (LOW20) -- the 20 lowest printed prices. The treatment.
* ``"high"`` (HIGH20) -- the 20 highest printed prices. The mirror: a rule run beside its own
  inversion shows whether the signal is real, and says nothing about what acting on it costs.
* ``"small"`` (SMALL20) -- the 20 smallest companies by point-in-time market value, same pool.
  The size confound the hypothesis names as its first expected failure, measured on this file's
  own universe rather than quoted across another method's.
* ``"adj-low"`` (ADJLOW20) -- the 20 lowest **stored, split-adjusted** closes. **A diagnostic, never
  a strategy.** Its rank is unknowable on the day it trades, because it depends on splits that had
  not happened yet, so it is a measurement of how much return the store's back-adjustment can
  manufacture out of nothing -- and it is explicitly not promotable, not tradeable, and not to be
  read as a result however well it does. It is here because the lab's standard F4 screen floors the
  adjusted close at $5 and so has been structurally excluding Apple, Nvidia, Netflix, Amazon,
  Monster, Broadcom, O'Reilly, TJX and Starbucks in exactly the years they compounded, and the lab
  should know what that number is worth before deciding whether to repair the screen.
* ``"random"`` (BLIND20) -- the no-opinion arm, a separate allocator id: ``lab.control_draw``'s
  frame-matched blind draw from the identical pool, matched to LOW20's own book size, entry count
  and turnover. LOW20 and HIGH20 pay the same trading cost and it cancels between them, so without
  this arm the run could tell a real signal from a lucky one and could not tell a dead rule from a
  badly dressed one (insight 523: of 28 reversed pairs in this lab, only 6 could ever be priced).

LOW20-NOSW repeats LOW20 with the SPY 200-day switch off, which is the method's second habit and
the one that reverses on the owner's own window (M0287).

Assumptions written before any result, all fixed here. Pool characteristics were measured on seven
dates before this file was written, and they are universe properties, not results: the pool runs
140 names in 1998 to 396 in 2015; requiring a known company size costs 1-5% of it, because the $20
million dollar-volume floor has already removed the names that never filed; the printed-price floor
and the adjusted-price floor disagree on about 4% of the pool in 1998 and on almost none by 2015.
Printed price is only weakly related to size -- Spearman 0.18 to 0.33 across those seven dates --
and weakly related to 12-1 momentum (0.00 to 0.37), so the cheap book is not merely a small book or
a loser book, which is the single most encouraging thing known about this idea going in. The
cheapest twenty are real index names, not penny stocks: Xerox, Huntington, Regions, KeyCorp, Bank
of America, AES, Ford, Micron, AMD, Boston Scientific. After 2008 that list is heavily banks, which
is a concentration risk this file predicts rather than discovers. One more thing was seen
before this file was committed and is recorded here rather than discovered later: from the 2014
class C dividend, Alphabet's two listings answer two different share counts, so the dedupe
correctly does not collapse them and HIGH20 holds Google in two of its twenty slots in the later
years. That is left alone. The dedupe rule is the lab's existing one and choosing a different one
after seeing a book is a tuned dial; it touches a control arm, not the treatment; and the two
listings really are two securities after 2014. Market-aware
(``market_fields = ("shares",)``): the history-only path has no splits and no counts, so by the
contract it targets nothing. Rules are ``monthly-hold-frac-gotrade``: fractional shares at
Gotrade's real fees, asked monthly, on the owner's monthly top-up. Pure: reads only bars, splits
and counts public on or before ``data_date``.
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
from seer_engine.strategies.f_factor import DV_N, EXCLUDED, FactorParams, trend_on

ADDED = date(2026, 10, 26)

SIDES = ("low", "high", "small", "adj-low", "random")

MIN_PRINTED_PRICE = 5.0
"""F4's own ``min_price``, applied to the price that printed instead of the adjusted one.

Not a new dial and not a tuned one: 5.0 is the number ``FactorParams`` already defaults to and the
conventional penny-stock line. What changes here is only which close it is compared against."""

MIN_DOLLAR_VOLUME = 20_000_000.0
"""F4's own ``min_dollar_volume``, unchanged. Split-invariant: the store adjusts close down and
volume up by the same factor, so their product is the dollar volume that printed."""

CLASS_DV_N = 60
"""Sessions of trading value that decide which listing of one company keeps the slot, as every
size-aware file in this lab uses (M0198, M0227 and its children)."""


@dataclass(frozen=True, slots=True)
class PriceLevelParams:
    """``top`` names held; ``side`` one of :data:`SIDES`; ``seed`` the blind draw's draw seed;
    ``trend`` the switch, (symbol, n) or None, set by every variant."""

    top: int
    side: str = "low"
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
        return {
            "top": str(self.top),
            "side": self.side,
            "seed": str(self.seed),
            "trend": "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}",
            "min_printed_price": str(MIN_PRINTED_PRICE),
            "min_dollar_volume": str(MIN_DOLLAR_VOLUME),
            "dv_n": str(DV_N),
            "class_dv_n": str(CLASS_DV_N),
            "class_rule": "identical-share-count",
            "price_basis": "printed" if self.side != "adj-low" else "store-adjusted",
        }


def _check(params: object) -> PriceLevelParams:
    if not isinstance(params, PriceLevelParams):
        raise TypeError(f"params must be PriceLevelParams, got {type(params).__name__}")
    return params


def _gate(p: PriceLevelParams) -> FactorParams:
    return FactorParams(rank="momentum", top=p.top, trend=p.trend)


def printed_close(h: History, market: Any, symbol: str, data_date: date) -> float | None:
    """The close as it printed on ``data_date``: the stored, split-adjusted close multiplied by
    every split the vendor applied after that day (``ShareCounts.raw_factor``).

    None when there is no bar dated ``data_date`` or the read is not finite. Reads nothing dated
    after ``data_date``: ``raw_factor`` is a property of the store's own adjustment of the past,
    not a forecast, and the number it returns is what a newspaper printed that morning.
    """
    i = h.index_of(data_date)
    if i is None:
        return None
    adj = float(h.close[i])
    if not (adj > 0.0 and adj == adj and adj != float("inf")):
        return None
    return adj * market.shares.raw_factor(symbol, data_date)


def dollar_volume(h: History, data_date: date, n: int = DV_N) -> float:
    """``n``-session mean close times volume through ``data_date``; split-invariant."""
    return trading_value(h, data_date, n)


@dataclass(frozen=True, slots=True, eq=False)
class PricePrepared:
    history: Mapping[str, History]
    market: Any  # the Market (splits and counts), or None on the history-only path


@dataclass(frozen=True, slots=True)
class PoolRow:
    """One company's three ranking numbers on a decision date."""

    printed: float  # the close as it printed, dollars
    adjusted: float  # the store's back-adjusted close, dollars
    cap: float  # point-in-time company size, dollars


def eligible_pool(prepared: PricePrepared, members: AbstractSet[str],
                  data_date: date) -> dict[str, PoolRow]:
    """symbol -> :class:`PoolRow` for every member that clears the screen on ``data_date``, one
    listing per company.

    The screen, fixed before any result: a bar dated ``data_date``; a 20-session mean dollar volume
    strictly above $20 million (F4's own floor); a printed price of at least $5 (F4's own floor,
    read on the printed close); and a known point-in-time company size, which every arm needs so
    that SMALL20 ranks on the same universe the price arms do. Two listings of one company share an
    identical share count, and the one with the larger 60-session trading value keeps the slot.
    """
    mk = prepared.market
    if mk is None:
        return {}
    by_count: dict[float, tuple[float, str, PoolRow]] = {}
    for s in sorted(members):
        if s in EXCLUDED:
            continue
        h = prepared.history.get(s)
        if h is None:
            continue
        printed = printed_close(h, mk, s, data_date)
        if printed is None or printed < MIN_PRINTED_PRICE:
            continue
        if dollar_volume(h, data_date) <= MIN_DOLLAR_VOLUME:
            continue
        cap = mk.market_value(s, data_date)
        if cap is None or not cap > 0.0:
            continue
        n = mk.shares_on(s, data_date)
        if n is None:
            continue
        i = h.index_of(data_date)
        row = PoolRow(printed=printed, adjusted=float(h.close[i]), cap=cap)
        dv = trading_value(h, data_date, CLASS_DV_N)
        seen = by_count.get(n)
        if seen is None or (dv, s) > (seen[0], seen[1]):
            by_count[n] = (dv, s, row)
    return {s: row for _, s, row in by_count.values()}


def ranked_book(pool: Mapping[str, PoolRow], top: int, side: str) -> tuple[str, ...]:
    """The ``top`` names ``side`` asks for, out of ``pool``. Ties break on the symbol, so the book
    is a pure function of the pool and never of dictionary order."""
    if side == "low":
        order = sorted(pool, key=lambda s: (pool[s].printed, s))
    elif side == "high":
        order = sorted(pool, key=lambda s: (-pool[s].printed, s))
    elif side == "small":
        order = sorted(pool, key=lambda s: (pool[s].cap, s))
    elif side == "adj-low":
        order = sorted(pool, key=lambda s: (pool[s].adjusted, s))
    else:
        raise ValueError(f"ranked_book does not serve side={side!r}")
    return tuple(order[:top])


class PriceLevelAllocator:
    """The ``top`` names at one end of a ranking over this file's screened pool, equal slots, fully
    invested; nothing while the switch, if any, is off. No splits or counts (the history-only
    path): no targets. Does not run ``side="random"``; see :class:`MatchedDrawAllocator`."""

    id = "M0383"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(DV_N, CLASS_DV_N, 0 if p.trend is None else p.trend[1])

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return ("SPY",) if p.trend is None else tuple(sorted({"SPY", p.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: PricePrepared, members: AbstractSet[str], data_date: date,
             p: PriceLevelParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if p.side == "random":
            raise ValueError("PriceLevelAllocator does not run side='random'; use MatchedDrawAllocator")
        if not trend_on(prepared.history, data_date, _gate(p)):
            return ()
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
        """The history-only path: no splits and no counts, so no printed price and no target."""
        return self._run(PricePrepared(history, None), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> PricePrepared:
        return PricePrepared(history, None)

    def prepare_market(self, market: Any) -> PricePrepared:
        if not hasattr(market, "shares") or not market.shares.has_splits():
            return PricePrepared(market.history, None)
        return PricePrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, PricePrepared):
            raise TypeError(f"prepared must be PricePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


LEVEL = PriceLevelAllocator()


def _check_control(params: object) -> PriceLevelParams:
    """``PriceLevelParams``, plus the one thing a control's params may not say: a blind book must
    not describe itself as a ranked one, so ``side`` must read ``"random"``."""
    p = _check(params)
    if p.side != "random":
        raise ValueError(f"the matched draw is a control: side must be 'random', got {p.side!r}")
    return p


class MatchedDrawAllocator:
    """LOW20's shape with none of its opinion: ``lab.control_draw``'s frame-matched draw from this
    file's own pool, matched to the ``side="low"`` book's size, entry count and turnover. LOW20 and
    HIGH20 pay the same trading cost and it cancels between them; this arm is what prices it."""

    id = "M0383-A1"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check_control(params)
        inner = max(DV_N, CLASS_DV_N, 0 if p.trend is None else p.trend[1])
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

    def _select(self, prepared: PricePrepared, members: AbstractSet[str], data_date: date,
                p: PriceLevelParams) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """(the eligible pool, LOW20's own book) on ``data_date``."""
        pool = eligible_pool(prepared, members, data_date)
        if not pool:
            return (), ()
        return tuple(sorted(pool)), ranked_book(pool, p.top, "low")

    def _run(self, prepared: PricePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: PriceLevelParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, _gate(p)):
            return ()
        names = control_draw.matched_book(
            lambda d: self._select(prepared, members, d, p),
            data_date, held, tag="M0383", seed=p.seed,
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
        """The history-only path: no splits and no counts, so no pool and no target."""
        return self._run(PricePrepared(history, None), members, data_date, held,
                         _check_control(params))

    def prepare(self, history: Mapping[str, History]) -> PricePrepared:
        return PricePrepared(history, None)

    def prepare_market(self, market: Any) -> PricePrepared:
        if not hasattr(market, "shares") or not market.shares.has_splits():
            return PricePrepared(market.history, None)
        return PricePrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, PricePrepared):
            raise TypeError(f"prepared must be PricePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check_control(params))


MATCHED = MatchedDrawAllocator()

SW = ("SPY", 200)


def _v(suffix: str, params: PriceLevelParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0383-{suffix}", family="M0383", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=LEVEL, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


def _vm(suffix: str, params: PriceLevelParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0383-{suffix}", family="M0383", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MATCHED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0383",
    name="Cheapest and dearest printed share price, not the store's adjusted one",
    family="stock-nominal-price-level",
    source_kind="paper",
    source_ref=(
        'Green & Hwang (2009), "Price-Based Return Comovement", Journal of Financial Economics; '
        'Birru & Wang (2016), "Nominal Price Illusion", Journal of Financial and Quantitative '
        "Analysis"
    ),
    parent_id=None,
    hypothesis=(
        "A share's printed dollar price carries no information about what a company is worth -- a "
        "board decides it by how often it splits the stock -- yet Green & Hwang (2009) and Birru & "
        "Wang (2016) report that investors respond to the number itself: low-priced shares draw "
        "lottery-seeking retail demand and come to move together as a group, a cheapness illusion "
        "said to be independent of company size. No method in this lab has ranked on printed price "
        "before; the nearest kin rank on extreme daily returns (M0091, rejected) and on a modelled "
        "skewness forecast (M0342, dev-eligible but beaten by random picks behind the same switch "
        "and 7.3 points a year behind SPY in 2009-2015). Two things make this testable only now. "
        "First, the store's closes are back-adjusted, so the cheap-looking names in it are the "
        "companies that split the most -- Netflix's 2013-06-17 close is stored as $3.27 and printed "
        "at $229.23 -- and the printed price became recoverable only when splits arrived in the "
        "store on 2026-10-17/18, as close times ShareCounts.raw_factor, checked here against five "
        "known real closes before this file was written. Second, that same back-adjustment means "
        "F4's standard $5 price floor has been screening out Apple, Nvidia, Netflix, Amazon, "
        "Monster, Broadcom, O'Reilly, TJX and Starbucks in the years they compounded, so a method "
        "about printed price must build its own screen rather than inherit that one. Book: LOW20, "
        "the 20 lowest printed prices among index members clearing a $20 million dollar-volume "
        "floor (F4's own, split-invariant), a $5 printed-price floor (F4's own number read on the "
        "printed close) and a known point-in-time company size, one listing per company by the "
        "identical-share-count rule, equal slots, monthly, behind the SPY 200-day switch, "
        "fractional shares at Gotrade's real fees on the owner's monthly top-up. Controls: HIGH20, "
        "the same pool ranked the other way (the mirror, which shows whether the signal is real "
        "and cannot price what acting on it costs); BLIND20, a frame-matched blind draw from the "
        "identical pool matched to LOW20's own size, entry count and turnover (the no-opinion arm "
        "that does price it); SMALL20, the 20 smallest companies in the same pool, which is the "
        "size confound measured on this file's own universe instead of quoted across another "
        "method's; LOW20-NOSW, LOW20 with the switch off. ADJLOW20 ranks on the store's adjusted "
        "close and is a DIAGNOSTIC, NEVER A STRATEGY: its rank depends on splits that had not "
        "happened yet, so it is unknowable on the day it trades, is not promotable and is not to "
        "be read as a result however well it does -- it exists to price how much return the "
        "back-adjustment can manufacture, which is what the lab needs in order to decide whether "
        "to repair F4's screen. Predictions written before any result, from pool measurements made "
        "on seven dates: printed price is only weakly related to size (Spearman 0.18-0.33) and to "
        "12-1 momentum (0.00-0.37), so LOW20 is not merely a small book or a loser book and should "
        "separate from SMALL20 -- that weak correlation is the single most encouraging thing known "
        "about this idea going in; the pool runs 140 names in 1998 to 396 in 2015 and the company-"
        "size requirement costs only 1-5% of it; and the cheapest twenty after 2008 are heavily "
        "banks (Huntington, Regions, KeyCorp, Bank of America, Fifth Third), so LOW20 should carry "
        "a financial-sector concentration and a deeper 2008-2009 fall than SPY."
    ),
    expected_failure=(
        "Five ways, in order of likelihood. (1) The cheap book is a bank book. After 2008 the "
        "lowest printed prices in the index are dominated by banks and other post-crisis "
        "wreckage, so LOW20 is a concentrated sector bet wearing a price label: it should fall "
        "far harder than SPY in 2008-2009 and break the 20% drawdown bar, and whatever it earns "
        "afterwards is the financial sector's recovery and not a price-level effect. (2) No "
        "readable signal at all. LOW20 and HIGH20 land inside the blind draw's own width -- 19 "
        "blind rules span 7.5 points a year in this lab, and one draw is not a control -- so the "
        "pair proves nothing and the honest verdict is that the effect, if it exists, is smaller "
        "than this chassis can read. (3) Published and faded. Green & Hwang is 2009 and Birru & "
        "Wang 2016; the dev window ends in 2015, so it can only show the edge from before the "
        "crowd traded it, and this lab has watched that exact shape invert out of sample before "
        "(M0050). Even a clean dev win should be expected to fade. (4) The mirror wins instead. "
        "SPY's opponent is big-company drift, and the dearest twenty are the big compounders, so "
        "HIGH20 may simply beat LOW20 by holding what the index holds -- in which case the "
        "finding is about size and drift, which the lab already knows, and not about the price "
        "number. (5) 2009-2015 says no. Every twenty-year edge this lab has found was earned "
        "before 2009, and three of four roster strategies were already negative in 2009-2015 on "
        "dev years before the test window confirmed it. If LOW20's lead is all pre-2009 it is not "
        "worth a variation however good its average. Separately, and not a failure of the idea: "
        "ADJLOW20 is expected to beat everything, because ranking on a number contaminated by "
        "future splits is a look-ahead; if it does not, the back-adjustment matters less than this "
        "file argues and the F4 screen repair is less urgent."
    ),
    candidates=(
        _v("LOW20", PriceLevelParams(top=20, side="low", trend=SW),
           "The treatment: the 20 lowest printed share prices in the screened pool, behind the switch."),
        _v("HIGH20", PriceLevelParams(top=20, side="high", trend=SW),
           "The mirror: the same pool ranked the other way, so a real signal shows as a spread."),
        _vm("BLIND20", PriceLevelParams(top=20, side="random", seed=383, trend=SW),
            "The no-opinion arm: a blind draw from the identical pool matched to LOW20's own size, "
            "entries and turnover, which is the only thing here that prices what acting costs."),
        _v("SMALL20", PriceLevelParams(top=20, side="small", trend=SW),
           "The size confound: the 20 smallest companies in the same pool. If LOW20 matches this, "
           "printed price is size wearing a different label and the idea collapses into M0333's."),
        _v("ADJLOW20", PriceLevelParams(top=20, side="adj-low", trend=SW),
           "DIAGNOSTIC, NOT A STRATEGY: the 20 lowest store-adjusted closes, a rank that is "
           "unknowable on the day it trades. Prices the look-ahead the back-adjustment carries. "
           "Never promotable and never to be read as a result."),
        _v("LOW20-NOSW", PriceLevelParams(top=20, side="low", trend=None),
           "LOW20's second habit: the same book with the SPY 200-day switch off."),
    ),
    seen_keys=(
        "concept:nominal-price-level",
        "concept:printed-vs-adjusted-close",
        "doi:10.1016/j.jfineco.2009.05.001",
        "data:splits.csv-raw-factor",
    ),
)
