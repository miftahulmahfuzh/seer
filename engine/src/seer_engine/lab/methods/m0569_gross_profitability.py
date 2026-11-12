"""M0569 -- Gross profitability: Novy-Marx's other side of value.

Source: Novy-Marx, R. (2010 working paper / 2013 published), "The Other Side of Value: The Gross
Profitability Premium", NBER Working Paper 15940 / Journal of Financial Economics 108(1), 1-28.
Reserved by Sera batch 20261112-1505 as an ``idea`` row; this file refines it and keeps its id.

Why this shape. Every value book this lab has run ranks on price arithmetic (book-to-market,
discount from the yearly high, long-term losers) and inherits the same objection: cheap stocks as
a group lagged the market for most of this lab's dev window (M0276's analysis, M0162). Novy-Marx's
answer is a *quality* measure built the same way a value measure is -- one ratio from two SEC
filing line items -- but pointed the other way: gross profit (revenue minus cost of revenue) over
total assets. His 1962-2009 sample found it predicts returns about as well as book-to-market and is
*negatively* correlated with it (-0.57), so a profitable-and-expensive stock and a
healthy-looking-cheap stock are different bets. Unlike M0276's Piotroski score (eight yes/no tests
needing two matched fiscal years), gross profitability is one ratio from one fiscal year, so it
should be computable everywhere M0276's two-year-matched score is not.

The lab can test this now only because the SEC filing panel exists, and only where it has revenue,
cost of revenue (or a reported gross profit tag) and total assets filed for a recent fiscal year.
Before the panel scores ``MIN_POOL`` companies every arm holds SPY, exactly as M0276 does: the
dev row's early stretch is SPY's own curve, its worst fall is SPY's 2008 fall, and the method
cannot reach the four walk-forward folds the hard gate needs. **This method is not promotable by
construction**; it is evidence, bought for one method id, about whether gross profitability picks
winners among liquid index members, and about whether it is redundant with book-to-market already
in the lab.

How it chooses, on each monthly check (``monthly-hold-frac-gotrade``):

    * THE POOL. Index members (not SPY) with a bar dated ``data_date``, close >= $5 and 20-session
      mean trading value above $20M (the F4 screen, reused from M0276), whose latest fiscal year
      (revenue and cost of revenue, or a reported gross profit tag) is visible and ends within
      ``MAX_FY_AGE_DAYS`` of the day, with assets and a positive book equity at that same fiscal
      year end, and a known company size of at least ``MIN_MARKET_VALUE`` (below that a share
      count is filed in the wrong units -- M0276's measured case). One listing per company:
      listings whose fiscal-year equity and gross profit are identical are one filer (GOOG/GOOGL,
      FOX/FOXA, NWS/NWSA); their sizes are summed and the most-traded listing kept.
    * THE SCORE. Gross profitability = gross profit / total assets, both read from the latest
      fiscal year visible by ``data_date``. Gross profit falls back to revenue minus cost of
      revenue when no gross-profit tag was filed (same fallback M0276 uses). Book-to-market =
      book equity at that fiscal year end / company size on the day, for the value-only control.
    * THE BOOK. ``top`` names, equal slots, fully invested, over the *same* pool for every arm (no
      cheap-third pre-filter: Novy-Marx's claim is that profitability stands on its own, not that
      it refines a value frame). Incumbents keep their slot while within the best ``BUFFER`` x
      ``top`` of their arm's order, same purpose as M0276's buffer: the ratio moves once a year
      per company and a name on the twentieth/twenty-first edge would otherwise be bought and sold
      every month on noise.

Arms, all 20 names, same pool, same fees:

    HI20       the idea: highest gross profitability first (ties: cheaper first, then symbol)
    LO20       the mirror: lowest gross profitability first (ties: cheaper first) -- the paper's
               short leg
    VALUE20    the value-only control: cheapest book-to-market first, no profitability at all.
               HI20 vs VALUE20, and the overlap between their rosters, is what the paper's -0.57
               correlation predicts: if the two books pick near-identical names here, gross
               profitability is redundant with book-to-market already in the lab
    RANDOM20   the opinion-free arm: the whole pool in a fixed hash order redrawn once a year, so
               it churns about as the score does and knows neither the ratio nor the order.
               HI20 vs RANDOM20 is what acting on the ratio is worth
    NOSWITCH20 the no-switch twin of HI20: picks the identical top-20 by gross profitability the
               first time the pool clears ``MIN_POOL`` (via ``held`` -- the backtest's own memory
               of the prior month's targets, not a hidden global), then **never re-ranks again**:
               every later month it simply re-targets whatever subset of that original 20 still
               has a bar, with no replacement. HI20 vs NOSWITCH20 is what the monthly re-ranking
               buys over a single buy-and-hold pick. Assumption, written down because no prior
               trial fixed it: "held" can arrive as ``{MARKET}`` (the SPY pre-panel fallback), and
               that is deliberately *not* treated as a lock-in -- the real 20-name pick is made
               the first month the panel is big enough, whichever month that turns out to be.

Market-aware (``market_fields = ("fundamentals", "shares")``). Pure: reads only bars dated
``<= data_date``, facts filed ``<= data_date`` and share counts public by ``data_date``. NOSWITCH20
is a pure function of its own inputs too: the lock-in reads only ``held`` (the engine's own
chronological state, passed as an argument every call) and the current ``data_date``'s panel, never
a stored date or any state outside its arguments.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.fundamentals import ladder
from seer_engine.fundamentals.panel import KIND_ANNUAL, KIND_INSTANT
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.indicators import mean_dollar_volume_window

ADDED = date(2026, 11, 12)

DV_N = 20  # F4's dollar-volume window
MIN_PRICE = 5.0
MIN_DOLLAR_VOLUME = 20_000_000.0
MIN_MARKET_VALUE = 500_000_000.0  # below this a filed share count is usually in the wrong units
MAX_FY_AGE_DAYS = 480  # fiscal year end at most ~16 months old: a year plus a slow 10-K
INSTANT_SLACK_DAYS = 10  # a balance dated within this of the fiscal year end belongs to it
MIN_POOL = 150  # scored companies needed before the book acts; below it, hold SPY
BUFFER = 2  # incumbents keep their slot while within the best BUFFER x top of the order
MARKET = "SPY"

ARMS = ("hi", "lo", "value", "random", "noswitch")


@dataclass(frozen=True, slots=True)
class ProfitParams:
    """``top`` names held; ``arm`` which order fills them (see the module docstring); ``seed``
    the random arm's hash seed."""

    top: int = 20
    arm: str = "hi"
    seed: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 100:
            raise ValueError(f"top must be an int in [1, 100], got {self.top!r}")
        if self.arm not in ARMS:
            raise ValueError(f"arm must be one of {ARMS}, got {self.arm!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        if self.arm != "random" and self.seed != 0:
            raise ValueError("seed is for the random arm only")

    def as_dict(self) -> dict[str, str]:
        out = {
            "top": str(self.top),
            "arm": self.arm,
            "score": "gross_profit/assets",
            "value": "equity/market_value",
            "min_pool": str(MIN_POOL),
            "before_pool": MARKET,
            "buffer": str(BUFFER),
            "max_fy_age_days": str(MAX_FY_AGE_DAYS),
            "min_price": "5",
            "min_dollar_volume": "20000000",
            "min_market_value": "500000000",
            "dv_n": str(DV_N),
        }
        if self.arm == "random":
            out["seed"] = str(self.seed)
            out["redraw"] = "yearly"
        return out


def _check(params: object) -> ProfitParams:
    if not isinstance(params, ProfitParams):
        raise TypeError(f"params must be ProfitParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True)
class ProfitRow:
    symbol: str
    close: float
    dollar_volume: float
    book_to_market: float
    gp_assets: float


@dataclass(frozen=True, slots=True, eq=False)
class ProfitPrepared:
    history: Mapping[str, History]
    market: Any  # None on the history-only path


def _fin(x: float | None) -> bool:
    return x is not None and math.isfinite(x)


def _annual(sf: Any, concept: str, t: date) -> dict[date, float]:
    """Each fiscal year's value of ``concept`` visible at ``t``, keyed by period end, chosen by the
    panel's own point-in-time rule (latest filing first, so a newer report's comparatives win)."""
    return {pe: e[0].val for pe, e in sf._best_by_period(concept, KIND_ANNUAL, t).items()}


def _instant_at(sf: Any, concept: str, t: date, period_end: date) -> float | None:
    """The balance of ``concept`` dated at ``period_end`` (within ``INSTANT_SLACK_DAYS``), as
    visible at ``t``; the closest such date wins, ties to the later one."""
    best: tuple[int, date, float] | None = None
    for pe, e in sf._best_by_period(concept, KIND_INSTANT, t).items():
        gap = abs((pe - period_end).days)
        if gap <= INSTANT_SLACK_DAYS and (best is None or (gap, -pe.toordinal()) < (best[0], -best[1].toordinal())):
            best = (gap, pe, e[0].val)
    return None if best is None else best[2]


def _gross(gp: dict[date, float], rev: dict[date, float], cost: dict[date, float], pe: date) -> float | None:
    if pe in gp:
        return gp[pe]
    if pe in rev and pe in cost:
        return rev[pe] - cost[pe]
    return None


def profitability(sf: Any, t: date) -> tuple[float, float, float, date] | None:
    """``(gp_assets, equity, gross_profit, fy0_end)`` for one filer at ``t``, or None when the
    latest fiscal year visible cannot be priced on gross profitability and book equity together.
    Reads only facts filed by ``t``."""
    rev = _annual(sf, ladder.REVENUE, t)
    cost = _annual(sf, ladder.COST_OF_REVENUE, t)
    gp = _annual(sf, ladder.GROSS_PROFIT, t)
    candidates = set(gp) | (set(rev) & set(cost))
    if not candidates:
        return None
    fy0 = max(candidates)
    if (t - fy0).days > MAX_FY_AGE_DAYS:
        return None
    g0 = _gross(gp, rev, cost, fy0)
    if not _fin(g0):
        return None
    a0 = _instant_at(sf, ladder.ASSETS, t, fy0)
    if not _fin(a0) or a0 <= 0.0:  # type: ignore[operator]
        return None
    e0 = _instant_at(sf, ladder.EQUITY, t, fy0)
    if not _fin(e0) or e0 <= 0.0:  # type: ignore[operator]
        return None
    return g0 / a0, float(e0), float(g0), fy0  # type: ignore[operator]


def _dollar_volume(h: History, i: int) -> float:
    close = h.close[i + 1 - DV_N : i + 1].reshape(1, DV_N)
    volume = h.volume[i + 1 - DV_N : i + 1].reshape(1, DV_N)
    with np.errstate(divide="ignore", invalid="ignore"):
        return float(mean_dollar_volume_window(close, volume, DV_N)[0])


def pool(prepared: ProfitPrepared, members: AbstractSet[str], data_date: date) -> list[ProfitRow]:
    """The scored pool on ``data_date``, one listing per company, sorted by symbol."""
    m = prepared.market
    if m is None:
        return []
    groups: dict[tuple[float, float, date], list[tuple[str, float, float, float, float]]] = {}
    for s in sorted(members):
        if s == MARKET:
            continue
        h = prepared.history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i + 1 < DV_N:
            continue
        close = float(h.close[i])
        if not math.isfinite(close) or close < MIN_PRICE:
            continue
        dv = _dollar_volume(h, i)
        if not math.isfinite(dv) or not dv > MIN_DOLLAR_VOLUME:
            continue
        sf = m.fundamentals.get(s)
        if sf is None:
            continue
        pr = profitability(sf, data_date)
        if pr is None:
            continue
        mv = m.market_value(s, data_date)
        if not _fin(mv) or mv < MIN_MARKET_VALUE:  # type: ignore[operator]
            continue
        gp_assets, e0, g0, fy0 = pr
        groups.setdefault((e0, g0, fy0), []).append((s, close, dv, float(mv), gp_assets))
    out: list[ProfitRow] = []
    for (e0, _g0, _fy0), listings in groups.items():
        size = sum(x[3] for x in listings)
        s, close, dv, _mv, gp_assets = max(listings, key=lambda x: (x[2], x[0]))
        out.append(ProfitRow(s, close, dv, e0 / size, gp_assets))
    out.sort(key=lambda r: r.symbol)
    return out


def _draw(seed: int, symbol: str, data_date: date) -> int:
    key = f"{seed}|{symbol}|{data_date.year:04d}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")


def order(rows: list[ProfitRow], data_date: date, p: ProfitParams) -> list[str]:
    """The arm's preference order over the whole pool (see the module docstring)."""
    if p.arm in ("hi", "noswitch"):
        key = lambda r: (-r.gp_assets, -r.book_to_market, r.symbol)  # noqa: E731
    elif p.arm == "lo":
        key = lambda r: (r.gp_assets, -r.book_to_market, r.symbol)  # noqa: E731
    elif p.arm == "value":
        key = lambda r: (-r.book_to_market, r.symbol)  # noqa: E731
    else:
        key = lambda r: (_draw(p.seed, r.symbol, data_date), r.symbol)  # noqa: E731
    return [r.symbol for r in sorted(rows, key=key)]


def choose(ranked: list[str], held: frozenset[str], top: int) -> list[str]:
    """Incumbents within the best ``BUFFER * top`` keep their slot; the rest fill in rank order."""
    keep_zone = set(ranked[: BUFFER * top])
    kept = [s for s in ranked if s in held and s in keep_zone][:top]
    chosen = list(kept)
    for s in ranked:
        if len(chosen) >= top:
            break
        if s not in chosen:
            chosen.append(s)
    return chosen


class GrossProfitabilityAllocator:
    """Twenty index members chosen by gross profit over total assets (or one of three control
    orders), equal slots, fully invested; plain SPY until the filing panel scores at least
    ``MIN_POOL`` companies. History-only path: no targets."""

    id = "M0569"
    market_fields = ("fundamentals", "shares")

    def lookback(self, params: Any) -> int:
        _check(params)
        return DV_N

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (MARKET,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (MARKET,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _spy(self, prepared: ProfitPrepared, data_date: date) -> tuple[Target, ...]:
        h = prepared.history.get(MARKET)
        if h is None or h.index_of(data_date) is None:
            return ()
        t = target_from_close(MARKET, last_close(h, data_date), equal_weight(1))
        return () if t is None else (t,)

    def _run(self, prepared: ProfitPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: ProfitParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        rows = pool(prepared, members, data_date)
        if p.arm == "noswitch" and held and held != frozenset({MARKET}):
            # Already locked in: hold exactly the original roster while it is still priceable,
            # never replacing a name that drops out and never adding one that was not in it.
            picks = sorted(held)
        elif len(rows) < MIN_POOL:
            return self._spy(prepared, data_date)
        else:
            picks = choose(order(rows, data_date, p), held, p.top) if p.arm != "noswitch" else (
                order(rows, data_date, p)[: p.top]
            )
        w = equal_weight(p.top)
        out: list[Target] = []
        for s in picks:
            h = prepared.history.get(s)
            if h is None or h.index_of(data_date) is None:
                continue
            t = target_from_close(s, last_close(h, data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no filings, no share counts, so no signal and no target."""
        return self._run(ProfitPrepared(history, None), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> ProfitPrepared:
        return ProfitPrepared(history, None)

    def prepare_market(self, market: Any) -> ProfitPrepared:
        if len(getattr(market, "fundamentals", ())) == 0 or len(getattr(market, "shares", ())) == 0:
            return ProfitPrepared(market.history, None)
        return ProfitPrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ProfitPrepared):
            raise TypeError(f"prepared must be ProfitPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


GROSS_PROFITABILITY = GrossProfitabilityAllocator()


def _v(suffix: str, params: ProfitParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0569-{suffix}", family="M0569", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=GROSS_PROFITABILITY, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0569",
    name="Gross profitability: Novy-Marx's other side of value",
    family="stock-gross-profitability",
    source_kind="paper",
    source_ref=(
        "Novy-Marx, R. (2010 working paper / 2013), The Other Side of Value: The Gross "
        "Profitability Premium, NBER Working Paper 15940 / Journal of Financial Economics 108(1)"
    ),
    parent_id=None,
    hypothesis=(
        "Novy-Marx found gross profit (revenue minus cost of revenue) over total assets predicts "
        "returns about as well as book-to-market in 1962-2009, negatively correlated with it "
        "(-0.57): a profitable-but-expensive stock and a healthy-looking-cheap stock are different "
        "bets. Unlike M0276's Piotroski score, this is one ratio from one fiscal year, so it is "
        "buildable wherever the panel has a recent year of revenue, cost of revenue (or a reported "
        "gross-profit tag) and assets -- expected to cover more of the dev window than M0276's "
        "two-matched-year requirement. Pool: F4-screened index members ($5, $20M/day) with a "
        "fiscal year under 16 months old, assets and positive book equity at that year end, and a "
        "known company size of at least $500M (smaller is a share count in the wrong units), one "
        "listing per company. All arms share the same pool -- no cheap-third pre-filter -- because "
        "the paper's claim is that profitability stands on its own, not that it refines a value "
        "frame. Twenty equal slots, monthly, incumbents kept while within the best forty of their "
        "arm's order (BUFFER x top, M0276's device: the ratio moves once a year per company, so "
        "without it a name on the edge would be bought and sold on noise). Before the panel scores "
        "150 companies every arm holds SPY, so the method cannot reach four walk-forward folds: "
        "not promotable by construction, run as evidence. Arms: HI20 (the idea, highest "
        "profitability first), LO20 (the mirror, lowest first), VALUE20 (cheapest book-to-market "
        "first, no profitability -- the control that prices whether GP adds anything value does "
        "not already give), RANDOM20 (the whole pool in a yearly-redrawn hash order -- the "
        "opinion-free control that prices what acting on the ratio costs), NOSWITCH20 (HI20's "
        "no-switch twin: the identical top-20 picked once, the first month the pool clears 150, "
        "then held unchanged for the rest of the window, replacement never attempted -- the "
        "control that prices what monthly re-ranking buys over a single buy-and-hold pick). "
        "Predictions, fixed now, judged first on 2009-2015 (the highest-coverage years) then on "
        "the whole scored stretch, against the recorded SPY benchmark: (1) HI20 beats LO20 by at "
        "least 3 points a year; (2) HI20 beats RANDOM20 by at least 2 points a year, so acting on "
        "the ratio pays for its trading; (3) HI20 beats VALUE20 by at least 2 points a year and "
        "the two books hold visibly different rosters (not the -0.57-correlation prediction that "
        "they would be near-identical); (4) HI20 beats HI20's own recorded total return versus "
        "SPY. Success is (1), (2) and (3) together on the dev store and on the survivorship-check "
        "store; if HI20 and VALUE20 instead pick near-identical names, the factor is redundant "
        "with book-to-market already in the lab, not a new source of edge."
    ),
    expected_failure=(
        "Four ways, most likely first. (1) Like M0276's index members, these are covered by dozens "
        "of analysts and 10-Ks are read the day they land, so any profitability edge the paper "
        "found among small, thinly-followed stocks lands within noise here. (2) The scored stretch "
        "(roughly 2010-2015, until the panel is deep enough) was a period in which large, already- "
        "profitable growth names kept compounding and cheap-but-weak names kept lagging regardless "
        "of the ratio, so HI20 beats LO20 and VALUE20 without beating SPY: the era is the opponent, "
        "not the signal. (3) Gross profitability for large, mature index members clusters near the "
        "top of the distribution (most of them are profitable), so the ranking is decided as much "
        "by the book-to-market tie-break as by the ratio itself, and HI20 drifts toward VALUE20 "
        "rather than away from it -- the opposite of what the -0.57 correlation predicts. (4) The "
        "scored window is short: a few points a year between two twenty-name books over five or "
        "six years is within what luck makes, so even a clean pass on (1)-(3) is suggestive, not "
        "proof. Whatever happens, the whole-window row fails the worst-fall screen on SPY's own "
        "2008 fall and the walk-forward gate on folds; that is the construction, not the verdict."
    ),
    candidates=(
        _v("HI20", ProfitParams(20, "hi"),
           "The idea: the 20 most profitable-per-asset companies in the pool"),
        _v("LO20", ProfitParams(20, "lo"),
           "The mirror: the 20 least profitable-per-asset companies in the pool"),
        _v("VALUE20", ProfitParams(20, "value"),
           "Value only: the 20 cheapest companies by book-to-market, no profitability score"),
        _v("RANDOM20", ProfitParams(20, "random", seed=1),
           "No opinion: 20 names from the whole pool in a yearly-redrawn hash order"),
        _v("NOSWITCH20", ProfitParams(20, "noswitch"),
           "HI20's no-switch twin: the same 20 names picked once and held unchanged"),
    ),
    seen_keys=(
        "concept:novy-marx-gross-profitability",
        "concept:quality-factor-vs-value-factor-overlap",
    ),
)
