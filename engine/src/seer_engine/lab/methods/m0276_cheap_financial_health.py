"""M0276 — Cheap companies whose accounts are getting stronger: a financial-health score among the
cheapest index members.

Source: Piotroski (2000), "Value Investing: The Use of Historical Financial Statement Information
to Separate Winners from Losers", Journal of Accounting Research 38 (supplement), 1-41. Reserved by
Sera batch 20261022-1918 as an ``idea`` row; this file refines it and keeps its id.

Why this shape. Every value book the lab has run ranked on price arithmetic (long-term losers,
discount from the yearly high) and met the same objection: a cheap stock is usually cheap for a
reason, and a book of the cheapest names is a book of the companies the market has correctly
written off. Piotroski's answer is to stop asking *how* cheap and ask *which* cheap companies are
healing. Nine yes/no tests on two consecutive annual reports -- is it profitable, is cash coming in,
is profitability rising, is the profit backed by cash, is the balance sheet getting safer, is it
avoiding new shares, are margins and asset use improving -- separate the cheap companies that are
recovering from the ones that are dying. The paper found the high scorers beat the low scorers
inside the cheapest fifth by book-to-price by about 23 points a year over 1976-1996.

The lab can test this now only because the SEC filing panel exists, and only where it exists. Two
comparable fiscal years are visible for about 210 index members from March 2010 and 300+ from 2011
(measured on the dev store before this file was written: 0 on 2009-06-30, 16 on 2009-12-31, 209 on
2010-03-31, 304 on 2011-06-30, 334 on 2015-06-30). So:

    * BEFORE THE SCORE EXISTS every arm holds SPY. A scored pool smaller than ``MIN_POOL`` names
      means the panel does not yet describe the market, and the honest book is the yardstick. The
      dev row's 1996-2009 stretch is therefore SPY's own curve (less a few fees), its worst fall is
      SPY's 2008 fall, and the walk-forward record cannot reach the four folds the hard gate needs.
      **This method is not promotable by construction**; it is evidence, bought for one method id,
      about whether accounting health picks winners among cheap large companies in 2010-2015.
    * The history-only path (no panel, no share counts) targets nothing, per the market-aware
      contract.

How it chooses, on each monthly check (``monthly-hold-frac-gotrade``):

    * THE POOL. Index members (not SPY) with a bar dated ``data_date``, close >= $5 and 20-session
      mean trading value above $20M (F4's screen), whose latest annual report was for a fiscal year
      ending within ``MAX_FY_AGE_DAYS`` of the day, with the prior fiscal year (330-400 days
      earlier) visible too, positive book equity at the fiscal year end, a known company size of
      at least $500M (below that the share count was filed in the wrong units: Stryker's 2013
      count reads 378 shares), and
      at least ``MIN_TESTS`` of the eight score tests computable. One listing per company: listings
      whose latest fiscal-year net income and equity are identical are one filer (GOOG/GOOGL,
      FOX/FOXA, NWS/NWSA); their sizes are summed and the most-traded listing kept.
    * CHEAPNESS. Book-to-market: book equity at the latest fiscal year end over company size on
      the day. The cheap third is the top third of the pool by it.
    * THE SCORE. Eight of Piotroski's nine tests, each read from the two latest fiscal years as
      filed by ``data_date`` (the newer report's comparatives win, so both years are on one split
      and one accounting basis). Return on assets uses year-end assets, not the paper's
      beginning-of-year assets: the third year back is not in the newer report and reading it from
      an older one would mix bases. Tests:
        1 net income > 0              2 operating cash flow > 0
        3 return on assets rose       4 operating cash flow > net income
        5 equity / assets rose        (the panel has no debt tag; a rising equity share of assets
                                       is falling leverage, the paper's test 5 in its plainest form)
        6 diluted share count did not rise   (the paper's "no new equity issued")
        7 gross margin rose           8 asset turnover (revenue / assets) rose
      The current-ratio test is dropped: the panel carries no current assets or liabilities. A test
      whose inputs are missing is dropped for that company rather than guessed, and the score is the
      fraction passed of the tests available, so a company is never punished for a tag it did not
      file. Gross profit falls back to revenue minus cost of revenue when not tagged.
    * THE BOOK. ``top`` names, equal slots, fully invested. Incumbents keep their slot while they
      stay within the best ``BUFFER`` x ``top`` of their arm's order; free slots fill from the top
      of the order. The score moves once a year per company (when its 10-K lands) and cheapness
      moves with price, so without the buffer a name on the third's edge would be bought and sold
      month after month and the fee would decide the result. The buffer replaces the idea row's
      "rebalanced quarterly after filings": same purpose, one rule for every arm.

Arms, all 20 names, same pool, same fees, same buffer:

    HI20     the idea: cheap third, highest score first (ties: cheaper first, then symbol)
    LO20     the mirror: cheap third, lowest score first (ties: cheaper first) -- Piotroski's short leg
    R20      the opinion-free arm: cheap third in a fixed hash order redrawn once a year, so it
             churns about as often as the score does, and knows neither the score nor the order
             of cheapness inside the third. HI20 vs R20 is what acting on the score is worth.
    CHEAP20  the value-only arm: cheap third, cheapest first, no score. HI20 vs CHEAP20 asks whether
             health beats simply buying the deepest value.
    HIALL20  the score without cheapness: the whole pool, highest score first (ties: cheaper first).
             HI20 vs HIALL20 asks whether the score needs the value frame, as the paper says.

Market-aware (``market_fields = ("fundamentals", "shares")``). Pure: reads only bars dated
``<= data_date``, facts filed ``<= data_date`` and share counts public by ``data_date``.
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

ADDED = date(2026, 10, 22)

DV_N = 20  # F4's dollar-volume window
MIN_PRICE = 5.0
MIN_DOLLAR_VOLUME = 20_000_000.0
# An index member worth under $500M is a share count filed in the wrong units, not a bargain:
# measured before the run, Stryker's 2013 count reads 378 shares and its book-to-market 351,629.
MIN_MARKET_VALUE = 500_000_000.0
MAX_FY_AGE_DAYS = 480  # fiscal year end at most ~16 months old: a year plus a slow 10-K
PRIOR_MIN_DAYS, PRIOR_MAX_DAYS = 330, 400  # the prior fiscal year's end, before the latest
INSTANT_SLACK_DAYS = 10  # a balance dated within this of the fiscal year end belongs to it
MIN_TESTS = 6  # of the eight; fewer and the score is too thin to rank on
MIN_POOL = 150  # scored companies needed before the book acts; below it, hold SPY
BUFFER = 2  # incumbents keep their slot while within the best BUFFER x top of the order
MARKET = "SPY"
N_TESTS = 8

ARMS = ("hi", "lo", "random", "cheap", "hi_all")


@dataclass(frozen=True, slots=True)
class HealthParams:
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
            "tests": "ni>0,ocf>0,droa>0,ocf>ni,deq_assets>0,dshares<=0,dgm>0,dturn>0",
            "min_tests": str(MIN_TESTS),
            "cheap": "top-third-book-to-market",
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


def _check(params: object) -> HealthParams:
    if not isinstance(params, HealthParams):
        raise TypeError(f"params must be HealthParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True)
class HealthRow:
    symbol: str
    close: float
    dollar_volume: float
    book_to_market: float
    score: float  # fraction of available tests passed, in [0, 1]
    tests: int  # how many of the eight were available


@dataclass(frozen=True, slots=True, eq=False)
class HealthPrepared:
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


def _ratio(a: float | None, b: float | None) -> float | None:
    if not _fin(a) or not _fin(b) or b == 0.0:
        return None
    return a / b  # type: ignore[operator]


def _rose(new: float | None, old: float | None) -> bool | None:
    if not _fin(new) or not _fin(old):
        return None
    return new > old  # type: ignore[operator]


def health(sf: Any, t: date) -> tuple[float, int, float, float, float] | None:
    """``(score, tests_available, equity_fy0, net_income_fy0, fy0_end_ordinal)`` for one filer at
    ``t``, or None when the two fiscal years cannot be lined up. Reads only facts filed by ``t``."""
    ni = _annual(sf, ladder.NET_INCOME, t)
    if not ni:
        return None
    fy0 = max(ni)
    if (t - fy0).days > MAX_FY_AGE_DAYS:
        return None
    prior = [pe for pe in ni if PRIOR_MIN_DAYS <= (fy0 - pe).days <= PRIOR_MAX_DAYS]
    if not prior:
        return None
    fy1 = max(prior)
    ocf = _annual(sf, ladder.OPERATING_CASH_FLOW, t)
    rev = _annual(sf, ladder.REVENUE, t)
    cost = _annual(sf, ladder.COST_OF_REVENUE, t)
    gp = _annual(sf, ladder.GROSS_PROFIT, t)
    sh = _annual(sf, ladder.DILUTED_SHARES, t)
    a0, a1 = _instant_at(sf, ladder.ASSETS, t, fy0), _instant_at(sf, ladder.ASSETS, t, fy1)
    e0, e1 = _instant_at(sf, ladder.EQUITY, t, fy0), _instant_at(sf, ladder.EQUITY, t, fy1)
    if not _fin(e0) or e0 <= 0.0:  # type: ignore[operator]
        return None
    ni0, ni1 = ni[fy0], ni[fy1]
    ocf0 = ocf.get(fy0)
    r0, r1 = rev.get(fy0), rev.get(fy1)
    g0, g1 = _gross(gp, rev, cost, fy0), _gross(gp, rev, cost, fy1)
    tests: list[bool | None] = [
        ni0 > 0.0,
        (ocf0 > 0.0) if _fin(ocf0) else None,  # type: ignore[operator]
        _rose(_ratio(ni0, a0), _ratio(ni1, a1)),
        (ocf0 > ni0) if _fin(ocf0) else None,  # type: ignore[operator]
        _rose(_ratio(e0, a0), _ratio(e1, a1)),
        (sh[fy0] <= sh[fy1]) if (fy0 in sh and fy1 in sh and sh[fy1] > 0.0) else None,
        _rose(_ratio(g0, r0), _ratio(g1, r1)),
        _rose(_ratio(r0, a0), _ratio(r1, a1)),
    ]
    known = [x for x in tests if x is not None]
    if len(known) < MIN_TESTS:
        return None
    return sum(1 for x in known if x) / len(known), len(known), float(e0), float(ni0), float(fy0.toordinal())  # type: ignore[arg-type]


def _dollar_volume(h: History, i: int) -> float:
    close = h.close[i + 1 - DV_N : i + 1].reshape(1, DV_N)
    volume = h.volume[i + 1 - DV_N : i + 1].reshape(1, DV_N)
    with np.errstate(divide="ignore", invalid="ignore"):
        return float(mean_dollar_volume_window(close, volume, DV_N)[0])


def pool(prepared: HealthPrepared, members: AbstractSet[str], data_date: date) -> list[HealthRow]:
    """The scored pool on ``data_date``, one listing per company, sorted by symbol."""
    m = prepared.market
    if m is None:
        return []
    groups: dict[tuple[float, float, float], list[tuple[str, float, float, float, float, int]]] = {}
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
        hs = health(sf, data_date)
        if hs is None:
            continue
        mv = m.market_value(s, data_date)
        if not _fin(mv) or mv < MIN_MARKET_VALUE:
            continue
        score, n, e0, ni0, fy0 = hs
        groups.setdefault((e0, ni0, fy0), []).append((s, close, dv, float(mv), score, n))
    out: list[HealthRow] = []
    for (e0, _ni0, _fy0), listings in groups.items():
        size = sum(x[3] for x in listings)
        s, close, dv, _mv, score, n = max(listings, key=lambda x: (x[2], x[0]))
        out.append(HealthRow(s, close, dv, e0 / size, score, n))
    out.sort(key=lambda r: r.symbol)
    return out


def _draw(seed: int, symbol: str, data_date: date) -> int:
    key = f"{seed}|{symbol}|{data_date.year:04d}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")


def order(rows: list[HealthRow], data_date: date, p: HealthParams) -> list[str]:
    """The arm's preference order over the pool (cheap third, or the whole pool for ``hi_all``)."""
    if p.arm == "hi_all":
        frame = rows
    else:
        by_cheap = sorted(rows, key=lambda r: (-r.book_to_market, r.symbol))
        frame = by_cheap[: len(rows) // 3]
    if p.arm in ("hi", "hi_all"):
        key = lambda r: (-r.score, -r.book_to_market, r.symbol)  # noqa: E731
    elif p.arm == "lo":
        key = lambda r: (r.score, -r.book_to_market, r.symbol)  # noqa: E731
    elif p.arm == "cheap":
        key = lambda r: (-r.book_to_market, r.symbol)  # noqa: E731
    else:
        key = lambda r: (_draw(p.seed, r.symbol, data_date), r.symbol)  # noqa: E731
    return [r.symbol for r in sorted(frame, key=key)]


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


class CheapHealthAllocator:
    """Twenty index members chosen from the cheapest third by a financial-health score read from two
    annual reports (or one of four control orders), equal slots, fully invested; plain SPY until the
    filing panel scores at least ``MIN_POOL`` companies. History-only path: no targets."""

    id = "M0276"
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

    def _run(self, prepared: HealthPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: HealthParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        rows = pool(prepared, members, data_date)
        if len(rows) < MIN_POOL:
            h = prepared.history.get(MARKET)
            if h is None or h.index_of(data_date) is None:
                return ()
            t = target_from_close(MARKET, last_close(h, data_date), equal_weight(1))
            return () if t is None else (t,)
        picks = choose(order(rows, data_date, p), held, p.top)
        w = equal_weight(p.top)
        out: list[Target] = []
        for s in picks:
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no filings, no share counts, so no signal and no target."""
        return self._run(HealthPrepared(history, None), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> HealthPrepared:
        return HealthPrepared(history, None)

    def prepare_market(self, market: Any) -> HealthPrepared:
        if len(getattr(market, "fundamentals", ())) == 0 or len(getattr(market, "shares", ())) == 0:
            return HealthPrepared(market.history, None)
        return HealthPrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, HealthPrepared):
            raise TypeError(f"prepared must be HealthPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


CHEAP_HEALTH = CheapHealthAllocator()


def _v(suffix: str, params: HealthParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0276-{suffix}", family="M0276", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CHEAP_HEALTH, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0276",
    name=(
        "Cheap companies whose accounts are getting stronger: a financial-health score among the "
        "cheapest index members"
    ),
    family="stock-financial-health-score",
    source_kind="paper",
    source_ref=(
        "Piotroski (2000), Value Investing: The Use of Historical Financial Statement Information "
        "to Separate Winners from Losers, Journal of Accounting Research 38 (supplement) 1-41"
    ),
    parent_id=None,
    hypothesis=(
        "Published 2000, so the whole dev window is after publication and any edge here survived "
        "being known; the lab can only measure it in 2010-2015, where two comparable annual reports "
        "exist in the SEC panel for 200-330 index members (measured before the run: 209 on "
        "2010-03-31, 304 on 2011-06-30, 334 on 2015-06-30; 16 at the end of 2009). Piotroski's "
        "nine yes/no tests of improving health separate the cheap companies that are recovering "
        "from the ones the market has correctly written off. Eight are buildable here: positive "
        "profit, positive operating cash flow, rising return on (year-end) assets, cash flow above "
        "profit, a rising equity share of assets (the panel has no debt tag, so this stands in for "
        "falling leverage), no rise in diluted shares, rising gross margin, rising asset turnover; "
        "the current-ratio test is dropped (no current assets or liabilities in the panel) and a "
        "test with a missing input is dropped for that company, the score being the fraction passed "
        "of those available, at least six. Pool: F4-screened members ($5, $20M a day) with a fiscal "
        "year under 16 months old, its prior year visible, positive book equity and a known company "
        "size of at least $500M (smaller is a share count in the wrong units), one listing per company. Cheapness is book equity over company size; the cheap third "
        "is the frame. Twenty equal slots, monthly, incumbents kept while within the best forty of "
        "their arm's order (the buffer stands in for quarterly rebalancing so the fee does not "
        "decide). Before the panel scores 150 companies every arm holds SPY, so 1996-2009 is "
        "SPY's own curve and the method cannot reach four walk-forward folds: it is not promotable "
        "by construction and is run as evidence. Arms: HI20 (the idea), LO20 (the mirror, "
        "Piotroski's short leg), R20 (the cheap third in a yearly-redrawn hash order: the "
        "opinion-free arm that prices acting on the score), CHEAP20 (cheapest first, no score), "
        "HIALL20 (the score over the whole pool, no cheapness). Predictions, fixed now, judged on "
        "the recorded monthly curves sliced 2010-04 to 2015-10 against SPY's: (1) HI20 beats LO20 "
        "by at least 3 points a year; (2) HI20 beats R20 by at least 2 points a year, so acting on "
        "the score pays for its trading; (3) HI20 beats SPY total return over the slice; (4) HI20 "
        "beats HIALL20, so the score needs the value frame as the paper says. Success is (1), (2) "
        "and (3) together, on the dev store and on the survivorship-check store."
    ),
    expected_failure=(
        "Four ways, most likely first. (1) Large companies were not the paper's ground. Piotroski's "
        "edge lived in small, thinly followed, hard-to-short value stocks, where accounting news "
        "reaches the price slowly; index members are covered by dozens of analysts and their 10-Ks "
        "are read the day they land, so HI20 and LO20 land within noise of each other. (2) 2010-2015 "
        "was a decade in which value lost to growth and cheap stocks as a group trailed SPY, so "
        "even a working score lifts HI20 above R20 and CHEAP20 without lifting it above SPY: the "
        "frame is the opponent, not the signal. (3) The score is coarse: with six to eight tests "
        "it takes a handful of values, so the top twenty is decided as much by the cheapness "
        "tie-break as by health, and HI20 drifts toward CHEAP20. (4) Five and a half years is "
        "thin: a 3-point gap between two twenty-name books over 66 months is within what luck "
        "makes, so even a clean pass on (1)-(3) is suggestive, not proof. Whatever happens, the "
        "whole-window row fails the worst-fall screen on SPY's own 2008 fall and the walk-forward "
        "gate on folds; that is the construction, not the verdict."
    ),
    candidates=(
        _v("HI20", HealthParams(20, "hi"),
           "The idea: the 20 healthiest companies in the cheapest third"),
        _v("LO20", HealthParams(20, "lo"),
           "The mirror: the 20 least healthy companies in the cheapest third"),
        _v("R20", HealthParams(20, "random", seed=1),
           "No opinion: 20 names from the cheapest third in a yearly-redrawn hash order"),
        _v("CHEAP20", HealthParams(20, "cheap"),
           "Value only: the 20 cheapest companies, no health score"),
        _v("HIALL20", HealthParams(20, "hi_all"),
           "Health only: the 20 healthiest companies in the whole pool, cheap or not"),
    ),
    seen_keys=(
        "concept:piotroski-f-score",
        "concept:financial-health-score-in-cheap-third",
    ),
)
