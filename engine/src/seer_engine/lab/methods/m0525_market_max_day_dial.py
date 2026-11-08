"""M0525 — SPY sized by the market's own biggest up-day last month (the "MAX" lottery dial).

Source: Alpha Architect, "factor MAX" (April 2026), a study of 172 factors; the stock-level MAX
effect is Bali, Cakici & Whitelaw (2011). Idea: after a month with a lottery-like single day,
the next month pays less. Here it is applied to the one thing the owner holds, SPY, so a decision
is one order a month and Gotrade's minimum fee barely bites.

Signal, read only from SPY closes dated <= data_date: the largest daily gain in the last 21
sessions, compared with the same number for each of the prior 60 non-overlapping 21-session
blocks (at least 12 needed, else fully invested). "High" means it sits in the top third of that
history. Exposure is a fixed fraction when high and 100% otherwise; never above 100% (no
leverage). Pure.
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
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 11, 8)

BLOCK = 21
HISTORY_BLOCKS = 60
MIN_PRIOR = 12
TOP_THIRD = 2.0 / 3.0


@dataclass(frozen=True, slots=True)
class Params:
    """``mode``: ``dial`` weight is ``hi_pct`` percent when the last month's biggest up-day is in
    its top third, else 100; ``rev`` the mirror: 100 when high, else ``hi_pct`` (more exposure
    after a lottery month); ``flat`` always ``flat`` percent, no opinion."""

    mode: str = "dial"
    hi_pct: int = 50
    flat: int = 0

    def as_dict(self) -> dict[str, str]:
        return {"mode": self.mode, "hi_pct": str(self.hi_pct), "flat_pct": str(self.flat)}


def is_high(history: Mapping[str, History], data_date: date) -> bool | None:
    """True when the last 21 sessions' biggest SPY gain is in the top third of its own prior
    history; None when SPY lacks the bars."""
    h = history.get("SPY")
    i = None if h is None else h.index_of(data_date)
    if h is None or i is None or i < BLOCK * (MIN_PRIOR + 1):
        return None
    lo = max(1, i - BLOCK * HISTORY_BLOCKS)
    c = np.asarray(h.close[lo - 1 : i + 1], dtype=float)
    r = c[1:] / c[:-1] - 1.0  # r[-1] is the return on data_date
    n = len(r) // BLOCK
    if n < MIN_PRIOR + 1:
        return None
    blocks = r[len(r) - n * BLOCK :].reshape(n, BLOCK).max(axis=1)
    cur, prior = blocks[-1], blocks[:-1]
    return bool(cur > np.quantile(prior, TOP_THIRD))


def exposure(history: Mapping[str, History], data_date: date, p: Params) -> Decimal:
    if p.mode == "flat":
        return Decimal(p.flat) / 100
    hi = is_high(history, data_date)
    if hi is None:
        return Decimal(1)
    if p.mode == "dial":
        return Decimal(p.hi_pct) / 100 if hi else Decimal(1)
    return Decimal(1) if hi else Decimal(p.hi_pct) / 100


class MaxDayDialAlloc:
    id = "M0525"

    def lookback(self, params: Params) -> int:
        return BLOCK * (MIN_PRIOR + 1) + 1

    def symbols(self, params: Params) -> tuple[str, ...]:
        return ("SPY",)

    def holds(self, params: Params) -> tuple[str, ...]:
        return ("SPY",)

    def uses_members(self, params: Params) -> bool:
        return False

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Params) -> tuple[Target, ...]:
        w = exposure(history, data_date, params)
        if w <= 0:
            return ()
        t = target_from_close("SPY", last_close(history.get("SPY"), data_date), w)
        return () if t is None else (t,)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Params) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


ALLOC = MaxDayDialAlloc()


def _v(suffix: str, params: Params, rationale: str) -> Candidate:
    return Candidate(id=f"M0525-{suffix}", family="M0525",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=ALLOC, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0525",
    name="The market's own biggest up-day last month as the exposure dial: after a lottery-like month, hold less of SPY",
    family="market-max-day-dial",
    source_kind="blog",
    source_ref="https://alphaarchitect.com/factor-max/",
    parent_id=None,
    hypothesis=(
        "Each month-end read SPY's largest daily gain over the last 21 sessions and compare it "
        "with the same number for the prior 60 non-overlapping months (12 needed, else fully "
        "invested). In its top third: DIAL50 holds 50% SPY and the rest cash, DIAL0 holds none; "
        "otherwise 100%. REV50 is the mirror (100% after a lottery month, 50% otherwise). "
        "Published in 2026 as a factor effect (the stock-level version, 2011), so the dev window "
        "cannot have been traded by the crowd; 2009-2015 (a bull decade where cash time is "
        "costliest) is the first filter. One instrument, one order a month, fractional shares at "
        "Gotrade fees. No-opinion arms: FLAT100 (always SPY, the zero of the dial) and the "
        "equal-average-exposure twins FLAT_D (the average monthly exposure DIAL50 held on SPY "
        "1996-2015) and FLAT_R (REV50's), each read from SPY closes before the run and no returns: the dial read high in 38% of 238 month-ends from 1996, so DIAL50 averaged 0.81 and REV50 0.69, rounded to 80% and 70%. "
        "The signal is real only if DIAL50 beats REV50 and FLAT_D; it beats SPY only if it beats "
        "FLAT100. FLAT100 repeats a recorded always-invested SPY book, so it is a book twin of "
        "that host and is named, never counted as new."
    ),
    expected_failure=(
        "The month-level effect is weak for an index (an index's biggest day is mostly a "
        "volatility reading, and big up-days cluster in crashes, when the next month rebounds). "
        "Expect the dial to behave like the volatility-managed SPY books (M0423, M0431), which "
        "cut the fall but lost to SPY because time in cash in a rising decade costs more than the "
        "dodged months pay. REV50 may even do better, and FLAT_D should match DIAL50 on return."
    ),
    candidates=(
        _v("DIAL50", Params(mode="dial", hi_pct=50), "the dial: 50% SPY after a lottery month"),
        _v("DIAL0", Params(mode="dial", hi_pct=0), "the dial, all the way to cash"),
        _v("REV50", Params(mode="rev", hi_pct=50), "mirror: 100% after a lottery month, else 50%"),
        _v("FLAT100", Params(mode="flat", flat=100), "dressing: always SPY, no opinion"),
        _v("FLATD", Params(mode="flat", flat=80), "dressing: DIAL50's average exposure"),
        _v("FLATR", Params(mode="flat", flat=70), "dressing: REV50's average exposure"),
    ),
    seen_keys=("concept:max-daily-return-dial", "concept:market-lottery-month-spy"),
)
