"""M0318 — Does the dose lesson generalise? A second pick filter at depth, on a host whose blind
draws already beat the market.

Source: variation of M0302 (a trailing market-beta "calm" filter, dropping the jumpiest share of
M0197-Y20's pool before ranking). Company size as a safety screen, the reverse direction of the
small-firm size premium (Banz 1981, JFE 9(1); Fama & French 1992, JF 47(2)): here a LARGER company
is the "calm" end, kept, not a smaller one chased for extra return.

Idea. M0302 measured one filter at depth on a book with no cash rule: dropping the jumpiest three
fifths of the pool by trailing one-year market beta beat all four blind draws on the worst fall by
12.6 points on dev and 7.4 on the survivorship-check store -- real, seed-stable protection -- but
both filtered arms (0.40 and 0.60 dropped) still fell behind SPY in 2009-2015 on both stores (by
0.4 to 4.6 points a year), while every one of their four blind draws beat SPY in the same era on
both stores. Sixteen coin-versus-filter pairings across the whole M0302/M0293 dial went the coin's
way every time. That is one filter on one dial. Before the lab calls "a deep pool filter buys
protection it cannot afford" a property of filters in general, a second, genuinely different filter
needs to clear the same bar on the same chassis.

The obvious next candidate failed before a method file was written. M0232 (proximity to the
52-week high) was measured with `lab survivorship M0232 --no-journal`: all six of its variants fall
behind SPY in 2009-2015 on BOTH stores by 4.90 to 9.72 points a year, and its own no-opinion
placebo (M0232-PLC1) lags by 5.74 (dev) and 4.90 (survivorship) points on its own -- so on that
host the shortfall belongs to the book, not to the filter, and the comparison this idea needs
cannot be made. The rule that follows, and the one this method obeys: pick a filter whose host's
own no-opinion arms already beat SPY in 2009-2015 on both stores, checked BEFORE the file is
written, or a filter's shortfall can never be told apart from its host's.

Verified now, by re-running `lab survivorship M0197 --no-journal` in this session (trials #648-653):
M0197-Y20, the gate-off bond-like book this method reuses (``NOSW`` below, M0302's own host), leads
SPY in 2009-2015 by +7.0% a year on dev and +4.0% on the survivorship-check store -- positive on
both. (Its sibling M0197-Y20-OPP also clears both, +4.0%/+4.8%; the rate-neutral M0197-N20 does
NOT, -0.4%/-0.5%, which is why this method keeps M0302's exact host rather than picking a fresh
one.) M0197-Y20 is not itself a candidate -- DSR 0.732 at N=130, nowhere near the bar -- it is only
the frame this filter is judged inside, exactly as it was for M0302 and M0293.

THE SECOND FILTER, AND WHY IT MAY NOT REPEAT THE FIRST ANSWER. The filter is company size:
``Market.market_value(symbol, data_date)``, shares outstanding as filed by that day times the
close as it printed (``market_fields`` includes ``"shares"``), read fresh for every member of the
day's scored pool, same pool M0197's own regression already walks. Two deep rungs of the dial
survive from M0302's structure -- 0.40 and 0.60 of the pool dropped -- plus the mirror arm M0302
never ran at depth (its only mirror sat at M0293's shallow quarter dose), plus three blind draws
at the deepest rung rather than M0302's four, the one deliberate trim this run makes to stay
inside the lab's six-candidate cap per method; a fourth seed is queued as a follow-up only if the
three-draw spread is tight enough that one more could plausibly flip the read.

Size and beta are not obviously the same axis, and that is the point of running this as a second,
independent test rather than assuming the first answer repeats. M0197's own pre-registered fear
named the 2008 risk explicitly: Fannie Mae, Freddie Mac, KeyCorp and Fifth Third, at an average
trailing beta of 2.0 on 2008-06-30. All four were large, established financial institutions, not
small companies by market value -- Fannie Mae and Freddie Mac were federally-chartered mortgage
giants, KeyCorp and Fifth Third regional bank holding companies with multi-billion-dollar market
caps. A filter that drops the SMALLEST fraction of the pool does not touch any of them. So this
method is not predicting M0302's pattern will repeat; it is testing whether a filter aimed at a
different axis shows ANY of the same signature, and a clean null -- no separation from the blind
draws on the worst fall -- is itself the useful, pre-registered answer: it would show that the
dose lesson is tied to what a filter actually measures, not a generic property of narrowing a deep
pool at depth.

Coverage, named now. Market-value coverage runs 62-75% of dev member-days in 2009-2015 (lower
before, since the count is read class by class only from 2009 on) -- about a quarter to two fifths
of the scored pool has no usable size on a given re-pick date. A name with no market value on
``data_date`` (no filed share count within ``MARKET_VALUE_MAX_GAP_DAYS`` = 7 days, or no usable
close) is never dropped by the ``"small"``/``"big"`` filters -- it always survives, exactly as
M0201 treats an unknown size as neutral rather than penalising it -- and the blind draw's blind pool
is restricted to the same known-size subset, so the three mechanisms compete over an identical
eligible set. GOOG/GOOGL's shared share count (one company, two listed classes, same era) is
harmless here: a pure survive/drop decision does not sum share counts the way a weighting scheme
would, so no company is double-counted into the filter's dose.

Pure: every read is bars dated <= ``data_date``, the T10Y rows ``MarketSeries.upto`` returns for
that date, and ``Market.market_value`` as filed and priced on or before ``data_date``. Market-aware
(``market_fields = ("series", "shares")``): the history-only path has no yield fit and no size
lookup, so by the contract it targets nothing. Rules are ``monthly-hold-frac-gotrade``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0197_treasury_yield_beta import (
    REPICK_MONTHS,
    YieldBetaParams,
    choose,
    loadings,
)
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import NOSW, draw, drop_count
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.sim.book import Target
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorPrepared,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 23)

SIDES = ("small", "big", "blind")


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class SizeFilterParams:
    """``inner`` is the host, term for term. ``drop_frac`` is the share of the day's known-size
    pool thrown away before the host ranks what is left. ``side``: the smallest companies by
    market value go first (``"small"``, the idea), the biggest go first (``"big"``, the mirror),
    or a fixed per-symbol hash order over the same known-size subset (``"blind"``, the no-opinion
    arm). ``seed`` keys that hash and is read only when ``side == "blind"``. A company with no
    usable market value on the re-pick date is never dropped by ``"small"`` or ``"big"`` and is
    excluded from the ``"blind"`` draw's own pool, so all three compete over one eligible set.
    """

    inner: YieldBetaParams
    drop_frac: Decimal = Decimal("0")
    side: str = "small"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, YieldBetaParams):
            raise TypeError(f"inner must be YieldBetaParams, got {type(self.inner).__name__}")
        if not isinstance(self.drop_frac, Decimal) or not self.drop_frac.is_finite():
            raise TypeError(f"drop_frac must be a finite Decimal, got {self.drop_frac!r}")
        if not Decimal(0) <= self.drop_frac < Decimal(1):
            raise ValueError(f"drop_frac must be in [0, 1), got {self.drop_frac}")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"drop_frac": str(self.drop_frac), "side": self.side, "seed": str(self.seed),
               "size_from": "market-value", "unknown_size": "always-survives"}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> SizeFilterParams:
    if not isinstance(params, SizeFilterParams):
        raise TypeError(f"params must be SizeFilterParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the filter


def survivors(lv: Mapping[str, tuple[float, float]], market: Any, data_date: date,
              p: SizeFilterParams) -> dict[str, float]:
    """``lv``'s yield loadings (symbol -> (beta, c)) with ``drop_frac`` of the KNOWN-size subset
    removed. A symbol with no usable market value on ``data_date`` always survives."""
    sized: dict[str, float] = {}
    for s in lv:
        v = market.market_value(s, data_date)
        if v is not None and np.isfinite(v) and v > 0.0:
            sized[s] = float(v)
    k = drop_count(len(sized), p.drop_frac)
    if k <= 0:
        gone: set[str] = set()
    elif p.side == "small":
        gone = set(sorted(sized, key=lambda s: (sized[s], s))[:k])
    elif p.side == "big":
        gone = set(sorted(sized, key=lambda s: (-sized[s], s))[:k])
    else:  # blind: a fixed per-symbol hash order over the same known-size subset
        gone = set(sorted(sized, key=lambda s: (draw(p.seed, s), s))[:k])
    return {s: bc[1] for s, bc in lv.items() if s not in gone}


def filtered_frac(history: Mapping[str, History], series: MarketSeries, market: Any,
                  rows: list[Any], data_date: date, p: SizeFilterParams) -> dict[str, float]:
    """The host's rank fraction over the surviving pool: 0 is the first name the book wants."""
    inner = p.inner
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != inner.market)
    lv = loadings(history, series, pool, data_date, inner.market)
    if not lv:
        return {}
    kept = survivors(lv, market, data_date, p)
    if not kept:
        return {}
    if inner.side == "bond":
        key = dict(kept)
    elif inner.side == "opp":
        key = {s: -c for s, c in kept.items()}
    else:
        key = {s: abs(c) for s, c in kept.items()}
    order = sorted(kept, key=lambda s: (key[s], s))
    return {s: k / len(order) for k, s in enumerate(order)}


# --------------------------------------------------------------------------- the allocator


@dataclass(frozen=True, slots=True, eq=False)
class SizeFilterPrepared:
    history: Mapping[str, History]
    series: MarketSeries
    factor: FactorPrepared | None
    market: Any  # the Market, for market_value; None on the history-only path


class SizeFilterAllocator:
    """M0197's bond-like book, picking from a pool with one end of its market-value sort removed.

    Everything but the filter is the host's: the screen, the shared yearly fit, the 20 equal
    slots, the 40% keep band, the quarterly re-rank, no switch, and SPY in any slot left over.
    With ``drop_frac = 0`` nothing is removed and the book is the host exactly.
    """

    id = "M0318"
    market_fields = ("series", "shares")

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).inner.inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        inner = _check(params).inner
        fixed = {inner.market}
        if inner.inner.trend is not None:
            fixed.add(inner.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_check(params).inner.market,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: SizeFilterPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SizeFilterParams) -> tuple[Target, ...]:
        inner = p.inner
        if len(prepared.series) == 0 or prepared.market is None:  # market-aware contract
            return ()
        if not trend_on(prepared.history, data_date, inner.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, inner.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, inner.inner)
        stocks = [s for s in held if s != inner.market and s not in EXCLUDED]
        repick = not stocks or data_date.month in REPICK_MONTHS
        frac = (filtered_frac(prepared.history, prepared.series, prepared.market, rows, data_date,
                              p) if repick else {})
        return choose(prepared.history, members, frac, data_date, held, inner)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no market, so no size lookup and no target."""
        return self._run(SizeFilterPrepared(history, EMPTY_SERIES, None, None), members,
                         data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> SizeFilterPrepared:
        return SizeFilterPrepared(history, EMPTY_SERIES, prepare_factor(history), None)

    def prepare_market(self, market: Any) -> SizeFilterPrepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        return SizeFilterPrepared(market.history, series, prepare_factor(market.history), market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SizeFilterPrepared):
            raise TypeError(f"prepared must be SizeFilterPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


SIZEFILTER = SizeFilterAllocator()


def _v(suffix: str, drop_frac: str, side: str, seed: int, rationale: str) -> Candidate:
    return Candidate(id=f"M0318-{suffix}", family="M0318", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SIZEFILTER,
                     params=SizeFilterParams(NOSW, drop_frac=Decimal(drop_frac), side=side,
                                             seed=seed),
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0318",
    name=(
        "Does the dose lesson generalise? A second pick filter at depth, on a host whose blind "
        "draws already beat the market"
    ),
    family="stock-pick-filter-dose",
    source_kind="variation",
    source_ref=(
        "variation of M0302 (deep pool filter on M0197-Y20's book, the gate-off bond-like book); "
        "M0232 (52-week-high proximity) checked and disqualified first; company size as a safety "
        "screen, the reverse direction of the small-firm size premium (Banz 1981, JFE 9(1); "
        "Fama & French 1992, JF 47(2))"
    ),
    parent_id="M0302",
    hypothesis=(
        "M0302 found that dropping the jumpiest three fifths of M0197-Y20's pool by trailing "
        "market beta beats all four blind draws on the worst fall by 12.6 points on dev and 7.4 "
        "on the survivorship-check store, while both filtered arms still fall behind SPY in "
        "2009-2015 on both stores and all sixteen coin-versus-filter pairings on the whole dial go "
        "the coin's way. This method asks whether that shape -- real fall protection, no "
        "era edge, beaten by the coin on return -- is a property of pick filters at depth in "
        "general, or specific to a beta-based filter. The obvious next candidate, M0232 "
        "(proximity to the 52-week high), was checked and ruled out before any file was written: "
        "`lab survivorship M0232 --no-journal` showed all six variants losing to SPY in "
        "2009-2015 on both stores by 4.90-9.72 points a year, and its own no-opinion placebo "
        "(M0232-PLC1) alone lags by 5.74/4.90 points -- the shortfall belongs to that host, not "
        "to the filter, so the comparison this idea needs cannot be made there. The rule that "
        "follows: pick a filter whose host's own no-opinion arms already beat SPY in 2009-2015 on "
        "both stores, checked before the file is written. Re-verified in this session "
        "(`lab survivorship M0197 --no-journal`, trials #648-653): M0197-Y20, M0302's own "
        "gate-off host, leads SPY in 2009-2015 by +7.0% a year on dev and +4.0% on the "
        "survivorship-check store, positive on both, so this method keeps M0302's exact host "
        "(``NOSW``) rather than picking a fresh one. The second filter is company size: "
        "``Market.market_value``, read fresh for the day's scored pool. Six arms, all on NOSW: "
        "D40 and D60 (drop the smallest 40% and 60% of the pool's known-size names before "
        "ranking, the dose ladder), D60-MIRROR (drop the BIGGEST 60% instead -- the deep mirror "
        "M0302 never ran, since its only mirror sat at M0293's shallow quarter dose), and three "
        "blind draws at the deepest rung (D60-R1/R2/R3, one hash order over the same known-size "
        "pool) rather than M0302's four, the one deliberate trim made to fit the lab's "
        "six-candidate cap; a fourth seed is queued as a follow-up only if the three-draw spread "
        "leaves room for one more to flip the read. Predictions, written now, on the recorded "
        "de-funded worst fall and the funded 2009-2015 edge: D60's worst fall lands within 5 "
        "points of NOSW's own bare fall (62.1% dev) and inside the three-draw blind spread, "
        "because the names M0197 itself named as the 2008 danger -- Fannie Mae, Freddie Mac, "
        "KeyCorp, Fifth Third, at an average trailing beta of 2.0 -- were large, established "
        "financial institutions, not small companies by market value, so a smallest-60%-dropped "
        "filter does not touch them; D40's fall sits between D60's and NOSW's bare fall if there "
        "is any dose response at all, and within a few points of both if there is none; "
        "D60-MIRROR falls at least as deep as D60 and the blind draws, since concentrating in the "
        "smallest, least-covered share of the pool should if anything raise risk rather than "
        "lower it; and both D60 and D60-MIRROR hold a 2009-2015 funded edge within about 3 points "
        "of NOSW's own +7.0%/+4.0%, because the final pick is still the host's own yield-loading "
        "rank inside whichever pool survives, so a size-based pre-filter is not expected to move "
        "the era result the way a beta-based one did. A clean null here -- no separation on the "
        "fall, no separation across eras -- is itself the pre-registered, useful answer: it would "
        "show the dose lesson is tied to what a filter actually measures, not a generic property "
        "of narrowing a deep pool at depth. This method is not a candidate at any dose; it "
        "measures one question for the lab's own bookkeeping."
    ),
    expected_failure=(
        "The likeliest failure is the clean null stated above: size and crash risk may simply be "
        "different axes on this host, and all six arms -- D40, D60, D60-MIRROR and the three "
        "blind draws -- land within a few points of each other and of NOSW's bare 62.1% fall, "
        "because the pool's 2008 damage came from a handful of large financial institutions a "
        "size filter cannot see. If so, the honest reading is narrow: this filter adds nothing, "
        "not that filters at depth never work -- M0302 already showed one that does. Second, "
        "market-value coverage runs only 62-75% of the dev pool in 2009-2015 and is lower before "
        "it, so the 'known-size' subset drop_count draws from shrinks across the window; an early "
        "dose that looks weaker than a late one may be reading coverage, not the filter, and the "
        "analysis checks this before crediting any era difference to size. Third, the mirror may "
        "not move the way predicted: if the smallest, least-covered names the mirror concentrates "
        "in happen to be thinly-traded utilities and REITs rather than anything that failed in "
        "2008 (M0197's own gate-off book is already bond-like by construction), D60-MIRROR could "
        "land no worse than D60, which would say the host's own sort already dominates whatever "
        "size does. Fourth, three blind draws are one fewer than M0302's four and the lab has "
        "measured that nineteen identical rules span 7.5 points of return and 20.7 points of "
        "worst fall; a three-draw spread could by chance look tighter or wider than the true "
        "spread, and any claim that leans on the exact width of that spread is weaker than M0302's "
        "own four-draw reading and is written as such in the analysis. None of these is a reason "
        "to add a dose, change the host, re-seed a draw, or extend the cap after the run."
    ),
    candidates=(
        _v("D40", "0.40", "small", 0,
           "Drop the smallest 40% of the pool's known-size names before ranking, no switch: the "
           "shallow rung of the size dose ladder"),
        _v("D60", "0.60", "small", 0,
           "Drop the smallest 60% of the pool's known-size names, no switch: the idea, the "
           "deepest dose, read against M0302's own deep-rung reading on a different axis"),
        _v("D60-MIRROR", "0.60", "big", 0,
           "Drop the BIGGEST 60% instead, keeping the smallest and unknown-size names: the deep "
           "mirror M0302 never ran, the gap this method exists to fill"),
        _v("D60-R1", "0.60", "blind", 318,
           "Control: drop the same count by a fixed per-symbol hash over the known-size pool — "
           "the no-opinion arm that prices what dropping any three fifths of the sizeable names "
           "buys"),
        _v("D60-R2", "0.60", "blind", 319,
           "Control: the same hash-drawn placebo on a second seed, so the blind arm has a spread"),
        _v("D60-R3", "0.60", "blind", 320,
           "Control: the same hash-drawn placebo on a third seed"),
    ),
    seen_keys=(
        "concept:company-size-as-a-safety-filter-on-a-host-book",
        "concept:deep-pool-filter-dose-generalisation",
        "concept:size-filter-mirror-arm-at-depth",
    ),
)
