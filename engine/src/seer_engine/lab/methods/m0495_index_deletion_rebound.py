"""M0495 — Bought after being dropped: index deletions that keep trading, held for the rebound.

Source: Chen, Noronha & Singal, The Price Response to S&P 500 Index Additions and Deletions:
Evidence of Asymmetry and a New Explanation, Journal of Finance 59(4), 2004; disputed by Kumar,
Lawrence, Prakash & Rodriguez, Journal of Banking & Finance, 2023.
Idea: when a company leaves the index, every index fund must sell it on the same day, whatever
the company's prospects. Chen, Noronha and Singal found the price drop around a deletion is
temporary and comes back over the following months; Kumar et al. say a real decline remains.
This book takes the rebound side: it holds the names that left in the last few months and
still trade, and parks everything else in SPY.

On data date d:

  * **the exits**: each symbol's membership spells in the S&P 500 ∪ Nasdaq-100 union are merged
    (M0117's ``merge_spells``), and a spell's end is an exit. A name that left one index but is
    still in the other has not left the union and is not an exit. The interval end is the
    effective date the snapshot is dated on, so an exit dated <= d is public on d.
  * **the pool**: names whose most recent exit falls in ``(d - window_months, d]``, which are not
    a member on d (a ticker that came back is not a deletion any more), and which still trade:
    a bar dated d, a close at or above ``min_price``, 20-day mean dollar volume above
    ``min_dollar_volume``, and no gap longer than ``max_gap_days`` calendar days between bars
    from ``continuity_days`` before the exit through d. The last test is there because the dev
    store carries reused tickers: measured before the run, GENZ has bars to 2015 that trade near
    $31 on ~24,500 shares a day, which is not Genzyme. A reused ticker shows up as a gap at the
    hand-over, and the dollar-volume floor catches the rest.
  * **the book**: up to ``floor(1 / slot)`` of the pool, most recent exit first (ties by symbol),
    ``slot`` each, the rest of the money in SPY. A name ages out of the book ``window_months``
    after its exit, so the window is the holding period.
  * **the matched control** (``control="losers"``): the same count n the deletion book would hold
    on d, filled with liquid current members that fell the most over the last ``loser_n`` bars,
    same slot, rest in SPY. Deleted names have nearly always fallen hard first, so this asks
    whether being *dropped* adds anything to having simply *fallen*. It holds nothing at all on
    a date the deletion book holds nothing, so the two arms are invested on the same days.

Fractional shares at Gotrade's real fees: slots of 10-20% of a 20M IDR book are $130-270, under
one share of many names, and every trade pays the fee minimum.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0117_index_tenure_exclusion import merge_spells, months_before
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day

ADDED = date(2026, 11, 6)

IDLE = "SPY"
DV_N = 20
CONTROLS = ("none", "losers")


@dataclass(frozen=True, slots=True)
class DeletionParams:
    """How long after an exit a name stays in the book, how big a slot is, and the control."""

    window_months: int = 6
    slot: float = 0.10
    control: str = "none"  # "losers": the matched fallen-member twin
    loser_n: int = 126
    min_price: float = 1.0
    min_dollar_volume: float = 2_000_000.0
    max_gap_days: int = 7
    continuity_days: int = 30

    def __post_init__(self) -> None:
        for name in ("window_months", "loser_n", "max_gap_days", "continuity_days"):
            v = getattr(self, name)
            if not isinstance(v, int) or isinstance(v, bool) or v < 1:
                raise ValueError(f"{name} must be an int >= 1, got {v!r}")
        if not (0.0 < float(self.slot) <= 1.0):
            raise ValueError(f"slot must be in (0, 1], got {self.slot!r}")
        if self.control not in CONTROLS:
            raise ValueError(f"control must be one of {CONTROLS}, got {self.control!r}")
        if not (self.min_price > 0 and self.min_dollar_volume >= 0):
            raise ValueError("min_price must be > 0 and min_dollar_volume >= 0")

    @property
    def slots(self) -> int:
        return max(1, math.floor(1.0 / self.slot + 1e-9))

    def as_dict(self) -> dict[str, str]:
        return {
            "window_months": str(self.window_months),
            "slot": f"{self.slot:.4f}",
            "control": self.control,
            "loser_n": str(self.loser_n),
            "min_price": f"{self.min_price:.2f}",
            "min_dollar_volume": f"{self.min_dollar_volume:.0f}",
            "max_gap_days": str(self.max_gap_days),
            "continuity_days": str(self.continuity_days),
        }


def _check(params: object) -> DeletionParams:
    if not isinstance(params, DeletionParams):
        raise TypeError(f"params must be DeletionParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, eq=False)
class DeletionPrepared:
    """The price history, and each symbol's union exits when a membership calendar exists."""

    history: Mapping[str, History] = field(repr=False)
    exits: Mapping[str, tuple[date, ...]] | None = None


def _liquid_close(h: History, i: int, p: DeletionParams) -> float | None:
    """The close on bar ``i`` when it clears the price and dollar-volume floors, else None."""
    if i + 1 < DV_N:
        return None
    close = float(h.close[i])
    if not math.isfinite(close) or close < p.min_price:
        return None
    window = slice(i + 1 - DV_N, i + 1)
    dv = float(np.mean(h.close[window] * h.volume[window]))
    if not math.isfinite(dv) or dv <= p.min_dollar_volume:
        return None
    return close


def deletion_pool(
    prepared: DeletionPrepared, members: AbstractSet[str], data_date: date, p: DeletionParams
) -> list[tuple[date, str, float]]:
    """``(exit, symbol, close)`` for every recent deletion that still trades on d, newest first."""
    assert prepared.exits is not None
    cut = months_before(data_date, p.window_months)
    day = as_day(data_date)
    out: list[tuple[date, str, float]] = []
    for symbol, exits in prepared.exits.items():
        if symbol == IDLE or symbol in members:
            continue
        recent = [e for e in exits if cut < e <= data_date]
        if not recent:
            continue
        exit_day = max(recent)
        h = prepared.history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None:
            continue
        close = _liquid_close(h, i, p)
        if close is None:
            continue
        lo = int(np.searchsorted(h.dates, as_day(exit_day - timedelta(days=p.continuity_days))))
        span = h.dates[lo : i + 1]
        if len(span) < 2 or span[0] > as_day(exit_day) or span[-1] != day:
            continue
        gaps = np.diff(span).astype("timedelta64[D]").astype(int)
        if int(gaps.max()) > p.max_gap_days:
            continue
        out.append((exit_day, symbol, close))
    out.sort(key=lambda r: (-r[0].toordinal(), r[1]))
    return out


def loser_pool(
    history: Mapping[str, History], members: AbstractSet[str], data_date: date, p: DeletionParams
) -> list[tuple[float, str, float]]:
    """``(return over loser_n bars, symbol, close)`` for liquid current members, worst first."""
    out: list[tuple[float, str, float]] = []
    for symbol in sorted(members):
        if symbol == IDLE:
            continue
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < p.loser_n:
            continue
        close = _liquid_close(h, i, p)
        if close is None:
            continue
        past = float(h.close[i - p.loser_n])
        if not (math.isfinite(past) and past > 0):
            continue
        out.append((close / past - 1.0, symbol, close))
    out.sort()
    return out


class DeletionReboundAllocator:
    """Recent index deletions that still trade, a fixed slot each, the rest in SPY."""

    id = "M0495"
    market_fields = ()  # reads Market.membership, which every store carries

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(p.loser_n + 1, DV_N, 31 * p.window_months + p.continuity_days)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (IDLE,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (IDLE,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(
        self, prepared: DeletionPrepared, members: AbstractSet[str], data_date: date, p: DeletionParams
    ) -> tuple[Target, ...]:
        if prepared.exits is None:  # no membership calendar (market-aware contract)
            return ()
        picks = deletion_pool(prepared, members, data_date, p)[: p.slots]
        if p.control == "losers":
            n = len(picks)
            picks_c = [(s, c) for _, s, c in loser_pool(prepared.history, members, data_date, p)[:n]]
        else:
            picks_c = [(s, c) for _, s, c in picks]
        slot = Decimal(f"{p.slot:.4f}")
        out: list[Target] = []
        for symbol, close in picks_c:
            t = target_from_close(symbol, close, slot)
            if t is not None:
                out.append(t)
        rest = Decimal(1) - slot * len(out)
        if rest > 0:
            h = prepared.history.get(IDLE)
            i = h.index_of(data_date) if h is not None else None
            if i is not None:
                t = target_from_close(IDLE, float(h.close[i]), rest)
                if t is not None:
                    out.append(t)
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
        return self._run(DeletionPrepared(dict(history)), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> DeletionPrepared:
        return DeletionPrepared(dict(history))

    def prepare_market(self, market: Any) -> DeletionPrepared:
        spells, _ = merge_spells(tuple(market.membership.intervals))
        exits = {s: tuple(e for _, e in sp if e is not None) for s, sp in spells.items()}
        return DeletionPrepared(
            {s: h for s, h in market.history.items()}, {s: e for s, e in exits.items() if e}
        )

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        if not isinstance(prepared, DeletionPrepared):
            raise TypeError(f"prepared must be DeletionPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


DELETION = DeletionReboundAllocator()


def _v(suffix: str, params: DeletionParams, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0495-{suffix}",
        family="M0495",
        rules=MONTHLY_HOLD_FRAC_GOTRADE,
        allocator=DELETION,
        params=params,
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0495",
    name="Bought after being dropped: S&P 500 deletions that keep trading, held for the rebound",
    family="stock-index-deletion-rebound",
    source_kind="paper",
    source_ref=(
        "Chen, Noronha & Singal (2004, Journal of Finance) asymmetric add/delete response; "
        "Kumar, Lawrence, Prakash & Rodriguez (2023, Journal of Banking & Finance) dispute it"
    ),
    parent_id=None,
    hypothesis=(
        "Index funds must sell a company the day it leaves the index, a forced sale unrelated to "
        "the company's prospects. Chen, Noronha and Singal (2004) found the deletion price drop "
        "does not last and comes back over the next months; Kumar et al. (2023) say a real "
        "decline remains. The rebound was published in 2004, so the dev window's 2009-2015 years "
        "are already after the crowd could trade it. The book: on each monthly re-pick, hold the "
        "names that left the S&P 500 / Nasdaq-100 union within the last 1, 3 or 6 months and "
        "still trade (a bar on the day, price at least $1, 20-day dollar volume over $2M, no gap "
        "longer than a week since a month before the exit, and not back in the index), newest "
        "exit first, a fixed 10% slot each (20% in one arm), and the rest of the money in SPY. "
        "The window is the holding period: a name ages out of the book that many months after "
        "its exit. Measured before the run with this session's own script: 557 union exits in "
        "1996-2015, of which only 85 have dev-store bars from before the exit through three "
        "months after (104 on the survivorship-check store), about four a year, so the book "
        "sits mostly in SPY and the slot size is what lets the deletions move it at all. The "
        "control L6 holds, on each re-pick, exactly as many names as D6 would, at the same slot, "
        "but chooses liquid current members with the worst 126-day return, so the gap D6 minus "
        "L6 is what being dropped adds to having fallen. SPY is the always-invested no-opinion "
        "arm, since every variant's residual is SPY. Success: D6 or D3 beats total-return SPY "
        "and L6 on dev with a worst fall under the bar, and is ahead of SPY in 2009-2015 too. "
        "Fractional shares at Gotrade's real fees on monthly-hold-frac-gotrade and the owner's "
        "monthly deposits. Read 2009-2015 first; lab survivorship is mandatory before any "
        "verdict because deletions that later died are mostly missing from the dev store."
    ),
    expected_failure=(
        "The book is thin: about four tradeable deletions a year, so at a 10% slot it is roughly "
        "70-90% SPY and any edge on the deletions is diluted to a fraction of a point a year, "
        "which no DSR at the lab's N will call real; the most likely verdict is 'SPY with a few "
        "expensive extra trades'. The survivorship direction is against it: deleted companies "
        "are exactly the ones that go on to die, the dev store keeps the survivors, so a dev "
        "edge should shrink on the survivorship-check store. Kumar et al. say the decline is "
        "permanent, and if they are right the deletions lag SPY and L6 does no better. The "
        "anomaly is twenty years old, so an edge should be visibly weaker in 2009-2015 than "
        "before 2009. The 20% slot arm amplifies whatever the deletions do, and with names "
        "that fall 50% in 2008 its worst fall may cross the bar."
    ),
    candidates=(
        _v("D1", DeletionParams(window_months=1), "exits in the last month, 10% each, rest SPY"),
        _v("D3", DeletionParams(window_months=3), "exits in the last 3 months, 10% each, rest SPY"),
        _v("D6", DeletionParams(window_months=6), "exits in the last 6 months, 10% each, rest SPY"),
        _v(
            "D6S20",
            DeletionParams(window_months=6, slot=0.20),
            "exits in the last 6 months, 20% each (at most five), rest SPY",
        ),
        _v(
            "L6",
            DeletionParams(window_months=6, control="losers"),
            "control: as many as D6 holds, but current members with the worst 126-day return",
        ),
    ),
    seen_keys=(
        "concept:index-deletion-rebound",
        "concept:index-deletion-effect",
        "concept:forced-index-selling",
    ),
)
