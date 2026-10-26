"""M0387 -- Does repairing the stock screen's five-dollar price floor pay?

Source: variation of M0383 (the printed-vs-adjusted price level method), which measured the hole
this file prices. Reserved by Sera batch 20261026-1320 as an ``idea`` row; this file refines it and
keeps its id.

**The defect.** Every stock screen in this lab inherits F4's ``min_price = 5.0``: a member is
eligible only when its close is at least five dollars, the conventional penny-stock line. The
close it reads is the research store's, and the store's closes are back-adjusted for every split
the vendor applied afterwards. So the floor is not asking "did this share trade above five
dollars"; it is asking "did this share trade above five dollars *after* dividing by every split
between then and 2026". A company that split often reads far cheaper in the old years than it ever
traded, and the companies that split often are the companies that went up. The floor removes
exactly the names a momentum book is built to hold.

The size of the hole is M0383's own measurement, made on 2026-10-26 on the dev store over the 238
month-end sessions from 1996-01-31 to 2015-10-16: among members clearing the twenty-million-dollar
volume floor and a five-dollar **printed** price, the adjusted floor removed 1293 of 62923
member-months that also carry twenty sessions of trading history -- 2.05%, across 40 companies.
Two percent sounds like nothing. The two percent is Nvidia at 168 month-ends, Apple at 149, KLA at
137, CSX at 132, then Aimco, TJX, Lam Research, Amphenol, Amazon, Netflix, O'Reilly, Broadcom,
Starbucks, Monster and Fastenal.

**Why it is fixable only now.** The printed close is the stored close times
``Market.shares.raw_factor(symbol, d)``, the product of every split effective after ``d``. Split
dates reached the store on 2026-10-17/18; before that the printed number was unrecoverable.
M0383 checked the arithmetic against five known real-world closes (AAPL $645.57 on 2014-06-06 and
$94.25 on 2014-06-10 across its 7:1 split, GOOGL $693.02 and AMZN $562.44 on 2015-10-15, KO $61.06
on 2000-01-14) before it was committed, and this file imports that same verified helper rather
than writing a second one.

**Why this is not already answered.** M0383 ranks *on* price level, so its arms are cheap books and
dear books. This file does not rank on price at all. It runs the lab's plain 12-1 momentum book and
moves one dial: which close the five-dollar floor is compared against. That is a different
question, and it is the one that decides whether ~150 committed method files have been screening
on a number that does not exist.

**The ladder.** The floor is a habit, and a habit is priced by running the book with it on and off,
not by a two-point read (insight: two-point slope reads are wrong). The pools are nested almost
exactly -- ``raw_factor`` is at least 1 for a forward split, so a printed close is at or above the
adjusted one, and only a reverse split can flip that -- so the three bases are three rungs of one
dial:

* ``"adjusted"`` (ADJ20) -- the floor on the stored close. **What every screen in this lab does
  today.** The incumbent, and the thing the repair must beat to be worth landing.
* ``"printed"`` (PRN20) -- the floor on the price that printed. **The repair.**
* ``"none"`` (NONE20) -- no price floor at all. The far rung: the whole of what the floor costs,
  which bounds how much of it the repair can possibly recover.

**The three draws, and why there are three.** The nearest prior reading says the opinion in this
book may not be readable at all: M0383-BLIND20, a no-opinion frame-matched draw from M0383's pool,
recorded CAGR +35.5% against SPY total return +32.4% on the dev window and cleared the luck bar
(trial 1328). A 2.05% pool difference is far inside that width. So each rung carries its own
``lab.control_draw`` frame-matched draw, and all three draws share one tag and one seed, so the
keep hash and the entry hash run over symbols in the identical order on all three. The three draws
then differ by the pool and by nothing else, which is the cleanest reading of the floor this
chassis can produce: the difference between the ranked rungs minus the difference between the
blind rungs is the part of the repair that momentum is responsible for, and the blind spread alone
is the part that is simply "those names went up".

Chassis, fixed here and not tuned: 20 names, 12-1 momentum (``return_window(close, 252, 21)``,
F4's own defaults), equal slots, fully invested, monthly, behind the SPY 200-day switch, fractional
shares at Gotrade's real fees on the owner's monthly top-up. The dollar-volume floor is F4's own
$20 million over 20 sessions and is **not** touched: the store adjusts close down and volume up by
the same factor, so their product already prints the dollar volume that printed, and that screen
needs no repair. No company-size requirement and no share-class dedupe, because F4 has neither and
the incumbent arm has to be the incumbent. Market-aware (``market_fields = ("shares",)``): without
splits there is no printed price, so by the contract the history-only path targets nothing.
Pure: reads only bars and splits dated on or before ``data_date``.
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
from seer_engine.lab.methods.m0383_nominal_price_level_tilt import dollar_volume, printed_close
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import DV_N, EXCLUDED, FactorParams, trend_on

ADDED = date(2026, 10, 26)

BASES = ("adjusted", "printed", "none")
"""Which close the five-dollar floor is compared against. Three rungs of one dial."""

MIN_PRICE = 5.0
"""F4's own ``min_price``, unchanged in value. Only the number it is compared against moves."""

MIN_DOLLAR_VOLUME = 20_000_000.0
"""F4's own ``min_dollar_volume``: 20-session mean close times volume, strictly above. Untouched,
and split-invariant -- the store scales close down and volume up by the same factor."""

MOM_N = 252
MOM_SKIP = 21
"""F4's own 12-1 momentum window: ``close[i - MOM_SKIP] / close[i - MOM_N] - 1``."""

SW = ("SPY", 200)


@dataclass(frozen=True, slots=True)
class FloorParams:
    """``top`` names held; ``basis`` one of :data:`BASES`; ``draw`` True only for the blind arms;
    ``seed`` the draw seed; ``trend`` the switch, (symbol, n) or None."""

    top: int
    basis: str = "adjusted"
    draw: bool = False
    seed: int = 0
    trend: tuple[str, int] | None = SW

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 200:
            raise ValueError(f"top must be an int in [1, 200], got {self.top!r}")
        if self.basis not in BASES:
            raise ValueError(f"basis must be one of {BASES}, got {self.basis!r}")
        if not isinstance(self.draw, bool):
            raise TypeError(f"draw must be a bool, got {type(self.draw).__name__}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        FactorParams(rank="momentum", top=self.top, trend=self.trend)  # validates the switch

    def as_dict(self) -> dict[str, str]:
        return {
            "top": str(self.top),
            "price_floor_basis": self.basis,
            "draw": "yes" if self.draw else "no",
            "seed": str(self.seed),
            "trend": "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}",
            "min_price": "none" if self.basis == "none" else str(MIN_PRICE),
            "min_dollar_volume": str(MIN_DOLLAR_VOLUME),
            "dv_n": str(DV_N),
            "mom_n": str(MOM_N),
            "mom_skip": str(MOM_SKIP),
            "rule_id": control_draw.RULE_ID if self.draw else "ranked",
        }


def _check(params: object, *, draw: bool) -> FloorParams:
    if not isinstance(params, FloorParams):
        raise TypeError(f"params must be FloorParams, got {type(params).__name__}")
    if params.draw is not draw:
        want = "True" if draw else "False"
        raise ValueError(f"this allocator needs draw={want}, got draw={params.draw!r}")
    return params


def _gate(p: FloorParams) -> FactorParams:
    return FactorParams(rank="momentum", top=p.top, trend=p.trend)


def _inner_lookback(p: FloorParams) -> int:
    return max(MOM_N + 1, DV_N, 0 if p.trend is None else p.trend[1])


@dataclass(frozen=True, slots=True, eq=False)
class FloorPrepared:
    history: Mapping[str, History]
    market: Any  # the Market (splits), or None on the history-only path


def passes_floor(h: History, market: Any, symbol: str, data_date: date, basis: str) -> bool:
    """Does ``symbol`` clear the five-dollar price floor on ``data_date`` under ``basis``?

    ``"none"`` asks nothing. ``"adjusted"`` compares the store's back-adjusted close, which is
    what every screen in this lab does today. ``"printed"`` compares the close as it printed --
    the stored close times every split applied after that day -- which is the repair. Reads
    nothing dated after ``data_date``: a split's effect on the store's record of the past is not
    a forecast of the future.
    """
    if basis == "none":
        return True
    if basis == "adjusted":
        i = h.index_of(data_date)
        if i is None:
            return False
        c = float(h.close[i])
        return c == c and c >= MIN_PRICE
    p = printed_close(h, market, symbol, data_date)
    return p is not None and p >= MIN_PRICE


def momentum(h: History, data_date: date) -> float | None:
    """12-1 momentum through ``data_date``, or None when the bars or the read fall short."""
    i = h.index_of(data_date)
    if i is None or i < MOM_N:
        return None
    base = float(h.close[i - MOM_N])
    if not base > 0.0:
        return None
    m = float(h.close[i - MOM_SKIP]) / base - 1.0
    return m if m == m and m not in (float("inf"), float("-inf")) else None


def eligible_pool(prepared: FloorPrepared, members: AbstractSet[str], data_date: date,
                  basis: str) -> dict[str, float]:
    """symbol -> 12-1 momentum, for every member clearing the screen on ``data_date``.

    F4's screen exactly, with one dial moved: a member that is not SPY, with a bar dated
    ``data_date`` and at least 253 bars through it, a finite 12-1 momentum, a 20-session mean
    dollar volume strictly above $20 million, and a close of at least five dollars read under
    ``basis``.
    """
    mk = prepared.market
    if mk is None:
        return {}
    out: dict[str, float] = {}
    for s in sorted(members):
        if s in EXCLUDED:
            continue
        h = prepared.history.get(s)
        if h is None:
            continue
        m = momentum(h, data_date)
        if m is None:
            continue
        if dollar_volume(h, data_date) <= MIN_DOLLAR_VOLUME:
            continue
        if not passes_floor(h, mk, s, data_date, basis):
            continue
        out[s] = m
    return out


def ranked_book(pool: Mapping[str, float], top: int) -> tuple[str, ...]:
    """The ``top`` highest-momentum names in ``pool``, ties broken by symbol ascending."""
    return tuple(sorted(pool, key=lambda s: (-pool[s], s))[:top])


class FloorAllocator:
    """The 20 highest-momentum members of a pool screened at one of :data:`BASES`, equal slots,
    fully invested; nothing while the switch is off. Held names get no special treatment: the
    targets are the new top set, so a name that falls out is exited. No splits (the history-only
    path): no printed price to compare against, so no targets."""

    id = "M0387"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        return _inner_lookback(_check(params, draw=False))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params, draw=False)
        return ("SPY",) if p.trend is None else tuple(sorted({"SPY", p.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params, draw=False)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params, draw=False)
        return True

    def _run(self, prepared: FloorPrepared, members: AbstractSet[str], data_date: date,
             p: FloorParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, _gate(p)):
            return ()
        pool = eligible_pool(prepared, members, data_date, p.basis)
        if not pool:
            return ()
        w = equal_weight(p.top)
        out: list[Target] = []
        for s in ranked_book(pool, p.top):
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(FloorPrepared(history, None), members, data_date, _check(params, draw=False))

    def prepare(self, history: Mapping[str, History]) -> FloorPrepared:
        return FloorPrepared(history, None)

    def prepare_market(self, market: Any) -> FloorPrepared:
        if not hasattr(market, "shares") or not market.shares.has_splits():
            return FloorPrepared(market.history, None)
        return FloorPrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, FloorPrepared):
            raise TypeError(f"prepared must be FloorPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params, draw=False))


RANKED = FloorAllocator()


class FloorDrawAllocator:
    """The momentum book's shape with none of its opinion: ``lab.control_draw``'s frame-matched
    draw from the same screened pool, matched to that book's own size, entry count and turnover.

    One tag and one seed serve all three bases, so the keep hash and the entry hash run over
    symbols in the identical hash order on every rung and the three drawn books differ by the pool
    and by nothing else."""

    id = "M0387-A1"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        return control_draw.lookback_for(_inner_lookback(_check(params, draw=True)))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params, draw=True)
        return ("SPY",) if p.trend is None else tuple(sorted({"SPY", p.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params, draw=True)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params, draw=True)
        return True

    def _select(self, prepared: FloorPrepared, members: AbstractSet[str], data_date: date,
                p: FloorParams) -> tuple[tuple[str, ...], tuple[str, ...]]:
        pool = eligible_pool(prepared, members, data_date, p.basis)
        if not pool:
            return (), ()
        return tuple(sorted(pool)), ranked_book(pool, p.top)

    def _run(self, prepared: FloorPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: FloorParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, _gate(p)):
            return ()
        names = control_draw.matched_book(
            lambda d: self._select(prepared, members, d, p),
            data_date, held, tag="M0387", seed=p.seed,
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
        return self._run(FloorPrepared(history, None), members, data_date, held,
                         _check(params, draw=True))

    def prepare(self, history: Mapping[str, History]) -> FloorPrepared:
        return FloorPrepared(history, None)

    def prepare_market(self, market: Any) -> FloorPrepared:
        if not hasattr(market, "shares") or not market.shares.has_splits():
            return FloorPrepared(market.history, None)
        return FloorPrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, FloorPrepared):
            raise TypeError(f"prepared must be FloorPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params, draw=True))


DRAWN = FloorDrawAllocator()

SEED = 387


def _v(suffix: str, params: FloorParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0387-{suffix}", family="M0387", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=RANKED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


def _vd(suffix: str, params: FloorParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0387-{suffix}", family="M0387", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=DRAWN, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0387",
    name="Repairing the five-dollar price floor the stock screen reads off adjusted prices",
    family="stock-momentum",
    source_kind="variation",
    source_ref="M0383",
    parent_id="M0383",
    hypothesis=(
        "Every stock screen in this lab inherits F4's five-dollar minimum price, and it reads "
        "that price off the research store's split-adjusted close rather than the close that "
        "printed. The store divides the past by every split a company has had since, so a "
        "company that split often reads far cheaper in the old years than it ever traded, and the "
        "companies that split often are the ones that went up. M0383 measured the hole on "
        "2026-10-26 on the dev store: over the 238 month-end sessions from 1996-01-31 to "
        "2015-10-16, among members clearing the twenty-million-dollar volume floor and a "
        "five-dollar PRINTED price, the adjusted floor removed 1293 of 62923 qualifying "
        "member-months (2.05%) across 40 companies -- and that two percent is Nvidia at 168 "
        "month-ends, Apple at 149, KLA at 137, CSX at 132, then Aimco, TJX, Lam Research, "
        "Amphenol, Amazon, Netflix, O'Reilly, Broadcom, Starbucks, Monster and Fastenal. The "
        "repair is arithmetic and became possible only when split dates reached the store on "
        "2026-10-17/18: the printed close is the stored close times ShareCounts.raw_factor, "
        "checked by M0383 against five known real closes before it was committed, and imported "
        "here rather than rewritten. This file prices the repair instead of assuming it helps. It "
        "runs the lab's plain 12-1 momentum book -- 20 names, equal slots, monthly, behind the "
        "SPY 200-day switch, fractional shares at Gotrade's real fees on the owner's monthly "
        "top-up -- three times, identical in every respect except which close the five-dollar "
        "floor is compared against: the stored adjusted close (ADJ20, what the lab does today), "
        "the printed close (PRN20, the repair), and no floor at all (NONE20, the far rung, which "
        "bounds what the whole floor costs). The pools are nested except where a reverse split "
        "intervenes, so these are three rungs of one dial and not a two-point read. Each rung "
        "carries a frame-matched blind draw from its own pool under one shared tag and one shared "
        "seed, because the nearest prior reading says the opinion here may not be readable at "
        "all: a no-opinion draw from the parent's pool recorded +35.5% a year against SPY total "
        "return's +32.4% on this window and cleared the luck bar (trial 1328), and a 2.05% pool "
        "difference sits well inside that width. Sharing the seed makes the three draws differ by "
        "the pool and by nothing else, so the ranked spread minus the drawn spread is the part of "
        "the repair that momentum is responsible for. Predicts PRN20 beats ADJ20, because the "
        "names the repair restores are the window's best compounders and a momentum screen is "
        "precisely the screen that should want them; predicts PRN20 lands at or below NONE20, "
        "because the printed floor is the honest subset of no floor; and predicts PRN20 beats "
        "total-return SPY with a worst fall under 20%, a profit factor of at least 1.3 and well "
        "over 100 trades, on the strength of a 20-name momentum book behind the switch rather "
        "than on the floor repair, which is worth a point or two at most."
    ),
    expected_failure=(
        "Five ways, in order of likelihood. (1) The difference is unreadable. Two percent of "
        "member-months is a small dial and the draw noise in this lab is wide -- 19 blind rules "
        "span 7.5 points a year and 20.7 points of fall, and the parent's own blind draw cleared "
        "the luck bar on its own. ADJ20, PRN20 and NONE20 may land inside their own draws' spread, "
        "in which case the honest verdict is that the repair is smaller than this chassis can "
        "read and the lab should repair the screen for correctness rather than for return. (2) "
        "The restored names arrive too late to help. The floor bites hardest in the 1990s and "
        "early 2000s, when back-adjustment has the most splits to divide by; by 2009-2015, the "
        "era that actually predicts today and the one every roster strategy failed in, almost "
        "nothing is being removed. A repair whose whole lead is pre-2009 is not worth a variation "
        "however good its average, which is this lab's standing rule. (3) Momentum does not want "
        "them anyway. The floor removes a company only while its printed price is low relative to "
        "its later splits, which is before the compounding, not during it -- Nvidia is excluded in "
        "its cheap years, and a 12-1 momentum rank may simply not pick it then. In that case PRN20 "
        "and ADJ20 are nearly the same book and the restored names never reach the top twenty. (4) "
        "NONE20 wins, and the floor is pure cost. If dropping the floor entirely beats both, then "
        "the penny-stock screen is removing good names on both bases and the finding is about the "
        "floor as a concept, not about which close it reads -- a result worth having, but not the "
        "one this file predicts. (5) The repair makes it worse. The restored names are volatile "
        "high-split growth companies; a 20-name equal-weight book that holds more of them should "
        "fall harder, and PRN20 may beat ADJ20 on return while breaking the 20% drawdown bar, "
        "which would mean the lab's accidental floor was accidentally protecting it. Beyond the "
        "dial: this chassis is a plain momentum book, and plain momentum books in this lab lose "
        "to SPY on the owner's own 2018-2026 window even when they win on dev, so a dev win here "
        "is a statement about the screen and not a tradeable strategy."
    ),
    candidates=(
        _v("ADJ20", FloorParams(top=20, basis="adjusted"),
           "The incumbent: the five-dollar floor read on the store's split-adjusted close, which "
           "is what every stock screen in this lab does today."),
        _v("PRN20", FloorParams(top=20, basis="printed"),
           "The repair: the identical book with the five-dollar floor read on the close that "
           "actually printed."),
        _v("NONE20", FloorParams(top=20, basis="none"),
           "The far rung: the identical book with no price floor at all, which bounds the whole "
           "of what the floor costs and so bounds what the repair can recover."),
        _vd("ADJ20-D", FloorParams(top=20, basis="adjusted", draw=True, seed=SEED),
            "A blind draw from the incumbent's own pool in hash order, matched to that book's "
            "size, entries and turnover: the shape with none of the opinion."),
        _vd("PRN20-D", FloorParams(top=20, basis="printed", draw=True, seed=SEED),
            "A blind draw from the repaired pool in the same hash order under the same seed, so "
            "it differs from the incumbent's draw by the pool and by nothing else."),
        _vd("NONE20-D", FloorParams(top=20, basis="none", draw=True, seed=SEED),
            "A blind draw from the unfloored pool in the same hash order under the same seed, "
            "completing the no-opinion ladder beside the ranked one."),
    ),
    seen_keys=(
        "concept:printed-price-floor-repair",
        "concept:min-price-floor-basis",
        "concept:f4-screen-adjusted-close-defect",
    ),
)
