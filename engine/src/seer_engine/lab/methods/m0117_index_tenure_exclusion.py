"""M0117 — Leave out the newly added: an index book that skips members the index only just bought.

Source: Greenwood & Sammon, The Disappearing Index Effect (HBS working paper 23-025);
Vijh & Wang, Index Additions and Operating Performance, Financial Management 2022.
Idea: when a company is added to a big index, every index fund has to buy it on the same day.
That forced buying lifts the price into the addition and gives it back afterwards, and the
companies chosen tend to be at a profitability peak they do not hold. So the edge, if there is
one, is an *exclusion*: hold the index's liquid members as usual, but leave out the ones the
index only just bought, and let the money go to the next-most-traded member instead.

This is the first method in the lab that ranks on nothing but the membership calendar the store
has always carried. There is no price signal in it at all -- not momentum, not volatility, not
volume direction -- so by construction it should move differently from every book that has
already spent its test look.

On data date d:

  * **the pool**: index members (point-in-time S&P 500 ∪ Nasdaq-100) with a bar on d, at least
    ``DV_N`` bars of history, a close at or above ``min_price``, and 20-day mean dollar volume
    above ``min_dollar_volume``. This is F4's liquidity screen and nothing else -- deliberately
    NOT ``f_factor.factor_rows``, whose eligibility also demands a finite 252-day momentum and so
    would quietly throw out exactly the young companies this method is about.
  * **tenure**: each symbol's membership spells are merged into union spells (a company in both
    indices has one spell, a company that left and came back has two). Its tenure on d is the age
    of the spell covering d. ``min_tenure_months = 0`` excludes nobody: that is the control.
  * **left censoring**: the two snapshot files begin on 1996-01-02 (487 symbols) and 2007-02-01
    (51 symbols). Every symbol in a file's first row "starts" on that date, which is the data's
    first sight of it, not an addition -- the next-busiest start date in the whole store has 9
    symbols, so the two are unmistakable. A spell whose start date is shared by ``epoch_min`` or
    more symbols is therefore treated as tenure-unknown and is never excluded. Without this the
    book would be empty for its first three years and would throw out half of the Nasdaq-100 in
    February 2007, and both would be an artefact of the files rather than of the market.
  * **the book**: the pool minus the too-new names, the ``top`` most heavily traded of what is
    left, equal weight 1/``top``, held for a month. Held names get no special treatment: each
    month is a fresh pick, so a name excluded this month is sold.

The interval start is the effective date the snapshot is dated on, which is public on the day,
so nothing here reads the future. Membership itself is already point-in-time.

Fractional shares at Gotrade's real fees: a 50-name book on the owner's deposits cannot fill
whole-share slots in its first years, and the fee minimum on a small slot is exactly where this
kind of broad book either survives or does not.
"""

from __future__ import annotations

import calendar
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import DV_N, EXCLUDED, FactorPrepared, prepare_factor

ADDED = date(2026, 10, 12)

Spells = Mapping[str, tuple[tuple[date, date | None], ...]]


def _check_int(name: str, v: object, lo: int) -> int:
    if not isinstance(v, int) or isinstance(v, bool):
        raise TypeError(f"{name} must be an int, got {type(v).__name__}")
    if v < lo:
        raise ValueError(f"{name} must be >= {lo}, got {v}")
    return v


def _check_float(name: str, v: object, lo: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TypeError(f"{name} must be a float, got {type(v).__name__}")
    x = float(v)
    if not (x >= lo):
        raise ValueError(f"{name} must be >= {lo}, got {x}")
    return x


@dataclass(frozen=True, slots=True)
class TenureParams:
    """The book's size and liquidity floor, plus the one lever under test."""

    top: int = 50
    min_tenure_months: int = 0  # 0 = exclude nobody (the control)
    min_dollar_volume: float = 20_000_000.0  # F4's floor: 20-day mean close x volume, strict
    min_price: float = 5.0
    epoch_min: int = 20  # a start date shared by this many symbols is a snapshot, not an addition

    def __post_init__(self) -> None:
        _check_int("top", self.top, 1)
        _check_int("min_tenure_months", self.min_tenure_months, 0)
        _check_int("epoch_min", self.epoch_min, 2)
        object.__setattr__(
            self, "min_dollar_volume", _check_float("min_dollar_volume", self.min_dollar_volume, 0.0)
        )
        object.__setattr__(self, "min_price", _check_float("min_price", self.min_price, 0.01))

    def as_dict(self) -> dict[str, str]:
        return {
            "top": str(self.top),
            "min_tenure_months": str(self.min_tenure_months),
            "min_dollar_volume": f"{self.min_dollar_volume:.0f}",
            "min_price": f"{self.min_price:.2f}",
            "epoch_min": str(self.epoch_min),
        }


def _check(params: object) -> TenureParams:
    if not isinstance(params, TenureParams):
        raise TypeError(f"params must be TenureParams, got {type(params).__name__}")
    return params


# ---- the membership calendar ---------------------------------------------------------------


def merge_spells(
    intervals: tuple[tuple[str, date, date | None], ...],
) -> tuple[dict[str, tuple[tuple[date, date | None], ...]], dict[date, int]]:
    """Per-symbol union spells, plus how many symbols each spell start is shared by.

    A symbol listed in both indices, or listed twice because a snapshot split its run, becomes
    one spell; a symbol that genuinely left and rejoined keeps two. The counts are what the
    left-censoring test reads: a date hundreds of symbols "start" on is a file's first row.
    """
    by: dict[str, list[tuple[date, date | None]]] = {}
    for symbol, start, end in intervals:
        by.setdefault(symbol, []).append((start, end))
    spells: dict[str, tuple[tuple[date, date | None], ...]] = {}
    counts: dict[date, int] = {}
    for symbol, rows in by.items():
        merged: list[list[Any]] = []
        for start, end in sorted(rows, key=lambda r: (r[0], r[1] is None, r[1])):
            if merged and (merged[-1][1] is None or merged[-1][1] >= start):
                if merged[-1][1] is not None and (end is None or end > merged[-1][1]):
                    merged[-1][1] = end
            else:
                merged.append([start, end])
        spells[symbol] = tuple((a, b) for a, b in merged)
        for a, _ in merged:
            counts[a] = counts.get(a, 0) + 1
    return spells, counts


def months_before(d: date, n: int) -> date:
    """``d`` minus ``n`` calendar months, the day clamped to the shorter month's end."""
    m = d.month - 1 - n
    year = d.year + m // 12
    month = m % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def too_new(
    spells: Spells, counts: Mapping[date, int], symbol: str, data_date: date, p: TenureParams
) -> bool:
    """True when ``symbol``'s current membership spell began inside the last ``min_tenure_months``.

    False for a symbol whose spell starts on a snapshot epoch (tenure unknown, so not an
    addition), for one with no spell covering ``data_date``, and for every symbol when
    ``min_tenure_months`` is 0.
    """
    if p.min_tenure_months <= 0:
        return False
    cut = months_before(data_date, p.min_tenure_months)
    for start, end in spells.get(symbol, ()):
        if start <= data_date and (end is None or data_date < end):
            if counts.get(start, 0) >= p.epoch_min:
                return False
            return start > cut
    return False


# ---- the pool ------------------------------------------------------------------------------


def liquid_rows(
    fp: FactorPrepared, members: AbstractSet[str], data_date: date, p: TenureParams
) -> list[tuple[float, str, float]]:
    """``(dollar_volume, symbol, close)`` for every member that clears the liquidity screen on d."""
    day = as_day(data_date)
    lo = int(np.searchsorted(fp.dates, day, side="left"))
    hi = int(np.searchsorted(fp.dates, day, side="right"))
    if lo == hi:
        return []
    window = slice(lo, hi)
    close = fp.close[window]
    dv = fp.dollar_volume[window]
    ok = (
        (fp.nbars[window] >= DV_N)
        & np.isfinite(close)
        & np.isfinite(dv)
        & (dv > p.min_dollar_volume)
        & (close >= p.min_price)
    )
    out: list[tuple[float, str, float]] = []
    for j in (int(j) for j in np.flatnonzero(ok)):
        symbol = fp.symbols[int(fp.sym[lo + j])]
        if symbol in EXCLUDED or symbol not in members:
            continue
        out.append((float(dv[j]), symbol, float(close[j])))
    return out


@dataclass(frozen=True, eq=False)
class TenurePrepared:
    """The rolling liquidity columns, and the membership calendar when there is one.

    ``spells`` is None on the history-only path: without a ``Market`` there is no membership
    calendar, the exclusion cannot be applied, and a book built anyway would silently be the
    control. The market-aware contract is to target nothing instead.
    """

    factor: FactorPrepared = field(repr=False)
    spells: Spells | None = None
    counts: Mapping[date, int] = field(default_factory=dict, repr=False)


class IndexTenureAllocator:
    """The most heavily traded index members, minus the ones the index only just bought."""

    id = "M0117"
    market_fields = ()  # reads Market.membership, which every store carries

    def lookback(self, params: Any) -> int:
        _check(params)
        return DV_N

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()  # no fixed instrument: it reads members only

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(
        self, prepared: TenurePrepared, members: AbstractSet[str], data_date: date, p: TenureParams
    ) -> tuple[Target, ...]:
        if prepared.spells is None:  # no membership calendar (market-aware contract)
            return ()
        rows = liquid_rows(prepared.factor, members, data_date, p)
        rows.sort(key=lambda r: (-r[0], r[1]))  # most traded first, ties by symbol
        weight = equal_weight(p.top)
        out: list[Target] = []
        for _, symbol, close in rows:
            if len(out) >= p.top:
                break
            if too_new(prepared.spells, prepared.counts, symbol, data_date, p):
                continue
            target = target_from_close(symbol, close, weight)
            if target is not None:
                out.append(target)
        return tuple(out)

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        """The history-only path: no membership calendar, so no book."""
        return self._run(TenurePrepared(prepare_factor(history)), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> TenurePrepared:
        return TenurePrepared(prepare_factor(history))

    def prepare_market(self, market: Any) -> TenurePrepared:
        spells, counts = merge_spells(tuple(market.membership.intervals))
        return TenurePrepared(prepare_factor(market.history), spells, counts)

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        if not isinstance(prepared, TenurePrepared):
            raise TypeError(f"prepared must be TenurePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


TENURE = IndexTenureAllocator()


def _v(suffix: str, params: TenureParams, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0117-{suffix}",
        family="M0117",
        rules=MONTHLY_HOLD_FRAC_GOTRADE,
        allocator=TENURE,
        params=params,
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0117",
    name="Leave out the newly added: an index book that skips members the index only just bought",
    family="stock-index-tenure",
    source_kind="paper",
    source_ref=(
        "Greenwood & Sammon, The Disappearing Index Effect (HBS working paper 23-025); "
        "Vijh & Wang, Index Additions and Operating Performance, Financial Management 2022"
    ),
    parent_id=None,
    hypothesis=(
        "The lab has never used the one piece of data it already holds and nothing else mines: "
        "the point-in-time membership calendar, which says exactly when each company joined the "
        "index. Greenwood and Sammon (2023) and Vijh and Wang (2022) report that a company added "
        "to a big index arrives after a run-up driven by index funds having to buy it and then "
        "gives it back -- about -0.8% abnormal five days after and -1.4% a month after, across "
        "450 additions since 2000 -- and that additions underperform matched peers on "
        "profitability for three years. So the test is an exclusion, not a pick: hold the 50 "
        "most heavily traded index members at 2% each, rebalanced monthly, but leave out any "
        "company whose membership began within the last N months, and let the money go to the "
        "next most traded member instead. Variants sweep N over 6, 12, 24 and 36 months against "
        "C, the identical book with no exclusion; C and SPY are both the yardstick, and because "
        "treatment and control differ only in the excluded names, the gap between them is the "
        "whole of the measurement. Two honesty requirements were fixed before the run. First, "
        "the store serves 539 of about 1,061 requested members and the ones it cannot serve are "
        "disproportionately the companies that were deleted, so any tenure-based book is "
        "survivorship-flattered by construction: lab survivorship is to be run on the result and "
        "reported, and the exclusion framing was chosen over a tenure ranking because dropping "
        "the new is far less sensitive to who is missing than keeping the old. Second, the two "
        "snapshot files begin in January 1996 and February 2007 and every symbol in a first row "
        "appears to start there, so a start date shared by 20 or more symbols is treated as the "
        "data's first sight rather than an addition and is never excluded. The signal is "
        "structural with no price term in it at all, so it should move very little with the "
        "momentum, blend and dividend books that have already lost their test look. Success: a "
        "tenure variant beats C and beats total-return SPY on dev with a worst fall under 20%, "
        "and beats SPY in 2009-2015 as well as whole-window. Fractional shares at Gotrade's real "
        "fees on monthly-hold-frac-gotrade and the owner's monthly deposits."
    ),
    expected_failure=(
        "Two failures are more likely than success. The first is that the exclusion is simply too "
        "small to matter: measured before the run, at 50 names a 12-month exclusion changes the "
        "book in 76% of months and removes 1.3 names of 50 on average, so even a two-point-a-year "
        "drag on the excluded names moves the book by well under a tenth of a point a year, which "
        "no DSR at an N in the hundreds will ever call real. The second is that the base book "
        "loses regardless. Fifty equal 2% slots among index members is an equal-weight large-cap "
        "book, and insight 91 is that SPY's big-company drift beat every such book after 2018; "
        "the exclusion is an overlay on that base and cannot rescue it. The anomaly is also "
        "exactly the kind the lab's own lesson warns about: Greenwood and Sammon's title is that "
        "the index effect has been *disappearing*, and they date the fade to the 2000s, so the "
        "dev window ending in 2015 may show an edge that was already gone before the owner could "
        "trade it -- if an edge shows at all it should be visibly weaker in 2009-2015 than before "
        "2009. Mechanically, monthly rebalancing of a 50-name book at the fee minimum on small "
        "early slots is a real drag, and the longer exclusions (24 and 36 months) throw out "
        "enough of the book that they start to be a bet on old companies, which is the "
        "survivorship-flattered direction the design was chosen to avoid."
    ),
    candidates=(
        _v("C", TenureParams(), "control: the 50 most traded members, equal weight, nobody excluded"),
        _v("N06", TenureParams(min_tenure_months=6), "leave out members added in the last 6 months"),
        _v("N12", TenureParams(min_tenure_months=12), "leave out members added in the last 12 months"),
        _v("N24", TenureParams(min_tenure_months=24), "leave out members added in the last 24 months"),
        _v("N36", TenureParams(min_tenure_months=36), "leave out members added in the last 36 months"),
    ),
    seen_keys=(
        "concept:index-membership-tenure",
        "concept:exclude-recent-index-additions",
        "concept:index-inclusion-effect",
    ),
)
