"""M0047 — Weight the residual-momentum picks by real company size, with a ceiling on any one name.

Source: variation of M0034 (the size tilt that could only read trading volume), reserved by Sera
20261018-0517 for the owner's theme "books shaped like the market". Unblocked 2026-10-17, when
the research stores gained point-in-time shares outstanding from 1996 (EDGAR cover pages, then
XBRL, each usable from its filing day) and ``Market.market_value`` stopped multiplying an
unadjusted count by a split-adjusted close.

Why. Every strategy the owner ran from 2018 lost to SPY by a similar margin (insight 91), and
SPY is weighted by company size while these books give each of their twenty names an equal
slot. M0034 asked whether leaning the slots toward the bigger names pays, but it could only read
trading volume, which ranks companies like market value at a Spearman 0.69 and puts 35-40% of the
money on different names. This method asks the question with the real number: does sizing the
same residual-momentum picks the way the index sizes companies earn its concentration at any
ceiling, and does it close any of the gap a market-shaped yardstick opens.

What is the same as M0032-N20-RAW-FRAC-GT (and M0034-EQ): the SPY 200-day trend gate, F4's
screen, top-20 raw cumulative residual momentum, monthly, fractional shares at Gotrade's real
fees on the owner's monthly top-up. What this method adds:

    * ONE SHARE CLASS PER COMPANY. ``market_value`` answers each listed class with the whole
      company's count times that class's price, so GOOG and GOOGL would count Alphabet twice.
      The picks are walked in rank order and a second class of a company already chosen is
      skipped; the next name fills its slot. Applied to every arm, the equal one included, so
      the arms differ only in weighting.
    * SIZE WEIGHTS. Each pick's weight is proportional to ``market.market_value(symbol,
      data_date)``. The stock weights sum to picks / 20 (the equal book's exposure), so sizing
      moves money between names and never changes how much is invested. A pick whose size is
      unknown that day (no usable filing yet) is given the median known size among the picks:
      neutral, neither leaned on nor dropped. If no pick has a known size the book is equal
      weight. Assumption, written before any result.
    * A CEILING. No name above 10% (twice the equal slot) or 20% (four times), the excess spread
      over the names still under it (M0034's water-filling). One arm runs with no ceiling, to
      show what the ceiling is buying.
    * THE MEANINGLESS CONTROL. The same gate, screen, count, one-class rule and size weights,
      but the names are drawn in a fixed hash order (M0187's ``draw``) over exactly the names the
      residual ranking could score that day, re-drawn each quarter (March, June, September,
      December) and otherwise kept while still in the screen, with M0187's 40% keep band at a
      re-draw; a slot a holding leaves between re-draws is filled from the same hash order. If
      the size-weighted placebo matches the size-weighted momentum book, the lead is
      the size weighting's and not the ranking's.

Market-aware (``market_fields = ("shares",)``): the history-only path, and a market with no share
counts, target nothing, so ``lab run`` refuses this on a store without company size and the
contract kit sees an empty book. Pure: the hash is a function of its inputs and every read is of
bars and filings dated <= ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import Market
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    FACTOR_SYMBOLS,
    N20,
    ResidParams,
    ResidPrepared,
    resid_lookback,
    residual_scores,
)
from seer_engine.lab.methods.m0034_size_tilt_residual import _apply_ceiling, _floor_weight
from seer_engine.lab.methods.m0187_placebo_hash_order import draw
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED, FactorRow, prepare_factor, trend_on

ADDED = date(2026, 10, 18)

PICKS = ("residual", "placebo")
WEIGHTINGS = ("equal", "size")
REPICK_MONTHS = (3, 6, 9, 12)
KEEP_PCT = 40

#: Second listed classes of one filer, mapped to the class that names the company. Only the first
#: pick of a company is kept.
COMPANY: Mapping[str, str] = {
    "GOOGL": "GOOG", "FOXA": "FOX", "NWSA": "NWS", "UAA": "UA", "CMCSK": "CMCSA",
    "BATRK": "BATRA", "DISCK": "DISCA", "LBTYK": "LBTYA", "VIAB": "VIA", "LSXMK": "LSXMA",
    "FWONK": "FWONA",
}


def company(symbol: str) -> str:
    return COMPANY.get(symbol, symbol)


@dataclass(frozen=True, slots=True)
class SizeParams:
    """M0032's ranking (``inner``), how the twenty are picked, how they are sized, and the
    ceiling as an absolute weight (None = none)."""

    inner: ResidParams
    picks: str = "residual"
    weighting: str = "size"
    cap: float | None = None
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, ResidParams):
            raise TypeError(f"inner must be ResidParams, got {type(self.inner).__name__}")
        if self.picks not in PICKS:
            raise ValueError(f"picks must be one of {PICKS}, got {self.picks!r}")
        if self.weighting not in WEIGHTINGS:
            raise ValueError(f"weighting must be one of {WEIGHTINGS}, got {self.weighting!r}")
        if self.cap is not None:
            if isinstance(self.cap, bool) or not isinstance(self.cap, (int, float)):
                raise TypeError(f"cap must be a number or None, got {type(self.cap).__name__}")
            if not 1.0 / self.inner.inner.top <= self.cap <= 1.0:
                raise ValueError(f"cap must lie between the equal slot and 1, got {self.cap}")
            if self.weighting == "equal":
                raise ValueError("cap is meaningless on equal weights")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")
        if self.picks == "residual" and self.seed != 0:
            raise ValueError("seed is for the placebo picks only")

    def as_dict(self) -> dict[str, str]:
        out = {"picks": self.picks, "weighting": self.weighting,
               "cap": "none" if self.cap is None else repr(float(self.cap)),
               "seed": str(self.seed), "size": "market_value", "unknown_size": "median-of-picks",
               "one_class_per_company": ",".join(f"{k}>{v}" for k, v in sorted(COMPANY.items()))}
        if self.picks == "placebo":
            out["hash"] = "blake2b-8"
            out["repick_months"] = ",".join(str(m) for m in REPICK_MONTHS)
            out["keep_pct"] = str(KEEP_PCT)
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> SizeParams:
    if not isinstance(params, SizeParams):
        raise TypeError(f"params must be SizeParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True)
class SizePrepared:
    """M0007's prepared ranking inputs plus the market whose share counts size the picks."""

    resid: ResidPrepared
    market: Market | None


def one_per_company(order: Sequence[str], top: int) -> list[str]:
    """The first ``top`` symbols of ``order`` with at most one class of each company."""
    out: list[str] = []
    seen: set[str] = set()
    for s in order:
        if len(out) >= top:
            break
        c = company(s)
        if c in seen:
            continue
        seen.add(c)
        out.append(s)
    return out


def size_weights(sizes: Sequence[float | None], top: int, p: SizeParams) -> list[Decimal | None]:
    """One weight per pick, summing to len(sizes) / top. Unknown sizes take the median known."""
    if not sizes:
        return []
    eq = equal_weight(top)
    known = [s for s in sizes if s is not None and np.isfinite(s) and s > 0.0]
    if p.weighting == "equal" or not known:
        return [eq for _ in sizes]
    fill = float(np.median(known))
    raw = np.array([s if s is not None and np.isfinite(s) and s > 0.0 else fill for s in sizes],
                   dtype=np.float64)
    w = raw / float(raw.sum()) * (len(sizes) / top)
    if p.cap is not None:
        w = _apply_ceiling(w, float(p.cap))
    return [_floor_weight(float(x)) for x in w]


def placebo_order(scores: Mapping[str, float], data_date: date, held: frozenset[str],
                  rows: Mapping[str, FactorRow], p: SizeParams) -> list[str]:
    """The placebo's names in slot order. At a re-draw: held names under the keep band, then the
    hash order over the scorable names. Between re-draws: the holdings still in the screen, then
    the hash order to fill any slot a holding left."""
    stocks = sorted(s for s in held if s in rows and s not in EXCLUDED)
    order = sorted((s for s in scores if s not in EXCLUDED), key=lambda s: (draw(p.seed, s, data_date), s))
    if stocks and data_date.month not in REPICK_MONTHS:
        first = stocks
    else:
        frac = {s: k / len(order) for k, s in enumerate(order)}
        first = sorted((s for s in stocks if frac.get(s, 1.0) < KEEP_PCT / 100.0), key=lambda s: (frac[s], s))
    taken = set(first)
    return first + [s for s in order if s not in taken]


class MarketValueAllocator:
    """Residual-momentum (or hash-order placebo) picks, one class per company, sized by real
    market value under an optional ceiling. No share counts: no targets."""

    id = "M0047"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        return resid_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params).inner
        return tuple(sorted({p.market, *FACTOR_SYMBOLS(p.inner)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: SizePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SizeParams) -> tuple[Target, ...]:
        market = prepared.market
        if market is None or len(market.shares) == 0:  # no company size: target nothing
            return ()
        resid = prepared.resid
        if not trend_on(resid.history, data_date, p.inner.inner):
            return ()
        rows = resid.factor.rows_on(members, data_date, p.inner.inner)
        if not rows:
            return ()
        grid = resid.grid(p.inner.market)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, p.inner)
        by_symbol = {r.symbol: r for r in rows if r.symbol in scores and r.symbol not in EXCLUDED}
        top = p.inner.inner.top
        if p.picks == "residual":
            order = sorted(by_symbol, key=lambda s: (-scores[s], s))
        else:
            order = placebo_order({s: scores[s] for s in by_symbol}, data_date, held, by_symbol, p)
        chosen = one_per_company(order, top)
        sizes = [market.market_value(s, data_date) for s in chosen]
        out: list[Target] = []
        for s, w in zip(chosen, size_weights(sizes, top, p), strict=True):
            if w is None:
                continue
            t = target_from_close(s, by_symbol[s].close, w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no targets."""
        p = _check(params)
        return self._run(self.prepare(history), members, data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> SizePrepared:
        return SizePrepared(ResidPrepared(history, prepare_factor(history)), None)

    def prepare_market(self, market: Any) -> SizePrepared:
        if not isinstance(market, Market):
            raise TypeError(f"market must be a Market, got {type(market).__name__}")
        return SizePrepared(ResidPrepared(market.history, prepare_factor(market.history)), market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SizePrepared):
            raise TypeError(f"prepared must be SizePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


MARKETVALUE = MarketValueAllocator()

#: M0032-N20-RAW-FRAC-GT's ranking, verbatim: top-20 RAW cumulative residual momentum, SPY-200 gate.
RANKING = ResidParams(N20, scaled=False)


def _v(suffix: str, params: SizeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0047-{suffix}", family="M0047", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MARKETVALUE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0047",
    name="Weight the momentum picks by real company size, with a ceiling on any one name",
    family="stock-portfolio-construction",
    source_kind="variation",
    source_ref=(
        "variation of M0034 (size tilt by trading volume) with point-in-time market value from "
        "EDGAR share counts (stores of 2026-10-17); Sera 20261018-0517, theme 'books shaped like "
        "the market'; placebo frame of M0187"
    ),
    parent_id="M0034",
    hypothesis=(
        "Equal slots in a twenty-name momentum book lean toward the smaller index members compared "
        "with SPY, which weights by company size, and from 2018 SPY's big-company drift beat every "
        "book the lab tried (insight 91). M0034 tested a lean toward bigger names but could only "
        "read trading volume, which puts 35-40% of the money on different names than market value "
        "would. This method keeps M0032-N20-RAW-FRAC-GT's book exactly (SPY 200-day gate, F4 "
        "screen, top-20 raw residual momentum, monthly, fractional shares at Gotrade's real fees on "
        "the monthly top-up), keeps one share class per company, and sizes the twenty by "
        "point-in-time market value (filed share count times the close as it printed, from 1996), "
        "with no name above 10% (MV10) or 20% (MV20), plus an uncapped arm (MV) and the equal-slot "
        "control (EQ). Unknown sizes take the median known size among the picks. The meaningless "
        "control is the same frame and the same size weights on names drawn in a hash order over "
        "the same scorable names, re-drawn quarterly (PLC1-MV10, PLC1-MV20). Size-weighting is a "
        "very old idea (the cap-weighted index itself) and residual momentum was published in "
        "2011 (Blitz, Huij and Martens), inside the dev window. Success, written now: MV10 or MV20 "
        "beats total-return SPY on dev with a worst fall under the screen bar, beats EQ on return "
        "per unit of worst fall (MAR), keeps or improves EQ's edge over SPY in 2009-2015, and "
        "beats its own size-weighted placebo by at least 2 points a year. The expected direction "
        "on dev is a smaller worst fall and a lower return than EQ: the big names move less."
    ),
    expected_failure=(
        "Sizing by market value pulls the book toward the few biggest names the momentum screen "
        "happens to hold (in the 1990s GE, Microsoft, Cisco; later Exxon, Apple), so the book "
        "becomes a smaller, more concentrated copy of SPY's top end: lower volatility, but its "
        "edge over SPY shrinks with its distance from SPY, and the cap binds most months so MV10 "
        "ends up close to equal weight anyway while MV pays for concentration (one name at 30% or "
        "more, a deeper single-name fall such as Cisco in 2000-02). The size-weighted placebo "
        "probably beats SPY too on dev, because the gate and the screen do most of the work "
        "(M0187, M0198), and the size weighting moves both books together, so the gap to the "
        "placebo stays under 2 points. Coverage: before about 2000 many picks have no filed count "
        "and take the median, so the early years are close to equal weight and the test of the "
        "idea really lives in 2001-2015. The survivorship-check store, which holds the companies "
        "that died, should hurt the equal arm more than the size arms, since dead companies were "
        "mostly small; that is the one place a size tilt could look better than it is. And the "
        "method's ancestry runs through the residual-momentum family, which has a test-failed "
        "method, so the hard gate is expected to refuse promotion whatever dev says."
    ),
    candidates=(
        _v("EQ", SizeParams(RANKING, weighting="equal"),
           "Equal slots, one class per company: M0032's book under this allocator, the control"),
        _v("MV10", SizeParams(RANKING, weighting="size", cap=0.10),
           "Sized by real market value, no name above 10% (twice an equal slot)"),
        _v("MV20", SizeParams(RANKING, weighting="size", cap=0.20),
           "Sized by real market value, no name above 20% (four times an equal slot)"),
        _v("MV", SizeParams(RANKING, weighting="size"),
           "Sized by real market value with no ceiling: what the ceiling is buying"),
        _v("PLC1-MV10", SizeParams(RANKING, picks="placebo", weighting="size", cap=0.10, seed=1),
           "Placebo: hash-order names over the same scorable set, sized by market value, 10% ceiling"),
        _v("PLC1-MV20", SizeParams(RANKING, picks="placebo", weighting="size", cap=0.20, seed=1),
           "Placebo: the same hash-order names, sized by market value, 20% ceiling"),
    ),
    seen_keys=(
        "concept:market-value-weighted-momentum-book",
        "concept:size-weighted-placebo-control",
    ),
)
