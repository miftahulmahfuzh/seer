"""M0165 — Hold SPY alone until SPY is a fifth below its year high, then lend a slice to the five-year losers.

Source: variation of M0104 (and its parents M0073, M0069: De Bondt & Thaler 1985, Does the Stock
Market Overreact?, Journal of Finance 40(3)), reserved by Sera batch sera-20261101-1522.
Idea: M0104 held a fixed 20% slice of five-year losers beside SPY at all times and learned that the
slice earned its lead only in the rebounds after 2002 and 2009, then gave it back. So hold the slice
only when the crash-rebound evidence says it pays: from the first session SPY closes 20% or more
below its highest close of the prior 252 sessions, for 12 or 24 months, then back to SPY alone.

One new allocator, ``CRASH``, a thin switch over parts the lab already trusts. When the slice is on
it hands the day to ``BLEND`` (an SPY core on ``TIMING`` always-SPY plus M0069's ``LTR`` on its
recorded F60 params, the same slice as M0104-C80-L60); when off it is ``TIMING`` holding SPY, which
is the whole book. So the satellite is exactly M0104's, and only *when* it is held is new.

The state is read from SPY's own bars, never carried: a latch scanned forward over the closes up to
d. It fires on the first session the drawdown from the prior-252-session high reaches the trigger,
stays on for ``hold_n`` sessions, and re-arms only after the window has ended and the drawdown has
healed above the trigger, so one long bear market is one episode, not many. Everything is a function
of bars dated <= d.

Assumptions, written before the run: "the bottom fifth of five-year losers" is the 20 lowest
formation returns (F60 top=20), the same slice M0104 held, so the two are comparable; a fifth of the
eligible pool would be larger and is not run. A year is 252 sessions, two years 504.
Every variant trades fractional shares at Gotrade's real fees on ``monthly-hold-frac-gotrade``,
which resizes to target each month, on the owner's deposits.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0069_long_term_reversal import F60, LTR, LtrParams
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import BLEND, BlendParams, BlendPart, LazyPrepared, _plain
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_index import TIMING, TimingParams

ADDED = date(2026, 11, 1)

SIGNAL = "SPY"
HIGH_N = 252  # the prior-year high: highest close of the last 252 sessions, today's included
YEAR = 252
ALWAYS_SPY = TimingParams(hold="SPY", signal="SPY", rule="always")


@dataclass(frozen=True, slots=True)
class CrashParams:
    """``slice_params`` is the satellite; ``share`` its weight while on; ``trigger`` the SPY fall
    that turns it on; ``hold_n`` sessions it stays; ``always`` skips the switch (the habit-off arm)."""

    slice_params: LtrParams
    share: Decimal = Decimal("0.2")
    trigger: Decimal = Decimal("0.2")
    hold_n: int = 2 * YEAR
    always: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.slice_params, LtrParams):
            raise TypeError(f"slice_params must be LtrParams, got {type(self.slice_params).__name__}")
        for name in ("share", "trigger"):
            v = getattr(self, name)
            if not isinstance(v, Decimal):
                raise TypeError(f"{name} must be a Decimal, got {type(v).__name__}")
            if not v.is_finite() or not 0 < v < 1:
                raise ValueError(f"{name} must be in (0, 1), got {v}")
        if isinstance(self.hold_n, bool) or not isinstance(self.hold_n, int) or self.hold_n < 1:
            raise ValueError(f"hold_n must be an int >= 1, got {self.hold_n!r}")
        if not isinstance(self.always, bool):
            raise TypeError("always must be a bool")

    def as_dict(self) -> dict[str, str]:
        out = {"share": _plain(self.share), "trigger": _plain(self.trigger),
               "hold_n": str(self.hold_n), "always": str(self.always)}
        for k, v in self.slice_params.as_dict().items():
            out[f"slice.{k}"] = v
        return out

    def blend(self) -> BlendParams:
        return BlendParams((BlendPart(TIMING, ALWAYS_SPY, Decimal(1) - self.share),
                            BlendPart(LTR, self.slice_params, self.share)))


def _check(params: object) -> CrashParams:
    if not isinstance(params, CrashParams):
        raise TypeError(f"params must be CrashParams, got {type(params).__name__}")
    return params


def slice_flags(close: np.ndarray, trigger: float, hold_n: int) -> np.ndarray:
    """Per bar of ``close``: is the slice on at that bar's close. Causal: bar i reads bars <= i.

    Fires on the first bar whose close is ``trigger`` or more below the highest close of the 252
    bars ending there, holds ``hold_n`` bars, and re-arms once the window is over and the fall has
    healed above the trigger.
    """
    n = close.shape[0]
    flags = np.zeros(n, dtype=bool)
    armed = True
    start = -1
    for i in range(HIGH_N - 1, n):
        hi = float(np.max(close[i - HIGH_N + 1 : i + 1]))
        dd = 1.0 - float(close[i]) / hi if hi > 0 else 0.0
        on = start >= 0 and i - start < hold_n
        if armed and dd >= trigger:
            armed, start, on = False, i, True
        elif not armed and not on and dd < trigger:
            armed = True
        flags[i] = on
    return flags


@dataclass
class CrashPrepared:
    lazy: LazyPrepared = field(repr=False)
    flags: dict[tuple[float, int], np.ndarray] = field(default_factory=dict, repr=False)


def _on(history: Mapping[str, History], flags: np.ndarray | None, data_date: date, p: CrashParams) -> bool:
    if p.always:
        return True
    h = history.get(SIGNAL)
    if h is None:
        return False
    end = int(np.searchsorted(h.dates, as_day(data_date), side="right"))
    if end < HIGH_N:
        return False
    if flags is None:
        flags = slice_flags(h.close[:end], float(p.trigger), p.hold_n)
    return bool(flags[end - 1])


class CrashEntryAllocator:
    """SPY alone, plus M0069's losers slice while an SPY crash episode is in its window."""

    id = "M0165"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(HIGH_N, BLEND.lookback(p.blend()))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return tuple(sorted(set(BLEND.symbols(p.blend())) | {SIGNAL}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return tuple(BLEND.holds(_check(params).blend()))

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True  # the slice ranks members; while off, the members are simply not asked for

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if _on(history, None, data_date, p):
            return BLEND.targets(history, members, data_date, held, p.blend())
        return TIMING.targets(history, members, data_date, held, ALWAYS_SPY)

    def prepare(self, history: Mapping[str, History]) -> CrashPrepared:
        return CrashPrepared(BLEND.prepare(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CrashPrepared):
            raise TypeError(f"prepared must be CrashPrepared, got {type(prepared).__name__}")
        p = _check(params)
        flags = None
        h = prepared.lazy.history.get(SIGNAL)
        if not p.always and h is not None:
            key = (float(p.trigger), p.hold_n)
            flags = prepared.flags.get(key)
            if flags is None:
                flags = prepared.flags[key] = slice_flags(h.close, key[0], key[1])
        if _on(prepared.lazy.history, flags, data_date, p):
            return BLEND.targets_prepared(prepared.lazy, members, data_date, held, p.blend())
        return TIMING.targets(prepared.lazy.history, members, data_date, held, ALWAYS_SPY)


CRASH = CrashEntryAllocator()

LOSERS = LtrParams(F60, side="losers")
WINNERS = LtrParams(F60, side="winners")


def _v(suffix: str, params: CrashParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0165-{suffix}", family="M0165", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CRASH, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0165",
    name="Hold SPY alone until the market is a fifth below its year high, then lend a slice to the five-year losers for a year or two",
    family="stock-core-satellite",
    source_kind="variation",
    source_ref=(
        "Variation of M0104 (M0073, M0069; De Bondt & Thaler 1985, Does the Stock Market "
        "Overreact?, Journal of Finance 40(3))"
    ),
    parent_id="M0104",
    hypothesis=(
        "Long-term reversal was published in 1985, so the dev window is already after the crowd. "
        "M0104 held a fixed 20% slice of the 20 biggest five-year losers beside SPY and found the "
        "slice earned its lead only in the rebounds after 2002 and 2009, then gave it back, ending "
        "no better than a winners slice. If the lead belongs to crash rebounds, the slice should be "
        "held only inside them. The book holds SPY alone until SPY closes 20% or more below its "
        "highest close of the prior 252 sessions, then holds the slice (20% or 30% of equity, the "
        "rest SPY) for 252 or 504 sessions, then returns to SPY alone and re-arms after the fall "
        "has healed. Fractional at Gotrade's real fees on monthly-hold-frac-gotrade, on the owner's "
        "deposits. Variants: S20-H12 (20% for 12 months), S20-H24 (20% for 24 months), S30-H24 "
        "(30% for 24 months, the dose check), S20-H24-W (the control: the same 20% for 24 months "
        "but the five-year WINNERS, so any lead belongs to 'beaten down' and not to 'a 20-name slice "
        "after a crash'), and S20-ALWAYS (the habit-off arm: the same 20% losers slice held at all "
        "times, M0104-C80-L60's configuration inside this pre-registration, so the lab can price "
        "what the switch is worth). Success: S20-H24 or S20-H12 beats SPY TR on dev, beats the "
        "winners control and the always-held arm, adds to SPY in 2001-2003 and 2009-2010 and matches "
        "it elsewhere, and clears the 2009-2015 era (which holds no crash episode at all, so it can "
        "only show 'matches SPY')."
    ),
    expected_failure=(
        "Only two or three episodes exist in 1996-2015 (about 2001-2003 and 2008-2010, perhaps one "
        "run together), so the luck score cannot clear 0.90 on so few events however good the "
        "numbers look; the fall is still SPY's 55% because the slice is held after the fall begins "
        "and is only a fifth of equity; 2009-2015 has no episode, so every variant equals SPY "
        "there and the era test is a tie that says nothing; the entry fires after a fifth of the "
        "fall has already happened and in 2008 well before the bottom, so the slice rides the rest "
        "of the fall and any lead is made on the rebound alone. 2020's crash rebounded within "
        "months, before a 12-month slice would show anything, but that is outside the dev window. "
        "Survivorship flatters the slice: the losers that died are missing from the store."
    ),
    candidates=(
        _v("S20-H12", CrashParams(LOSERS, Decimal("0.2"), Decimal("0.2"), YEAR),
           "SPY alone; 20% five-year losers for 12 months after SPY falls 20% from its year high"),
        _v("S20-H24", CrashParams(LOSERS, Decimal("0.2"), Decimal("0.2"), 2 * YEAR),
           "The same slice held 24 months: does a longer hold catch the whole rebound"),
        _v("S30-H24", CrashParams(LOSERS, Decimal("0.3"), Decimal("0.2"), 2 * YEAR),
           "Dose check: 30% slice for 24 months"),
        _v("S20-H24-W", CrashParams(WINNERS, Decimal("0.2"), Decimal("0.2"), 2 * YEAR),
           "Control: the same switch and slice size, but the five-year WINNERS"),
        _v("S20-ALWAYS", CrashParams(LOSERS, Decimal("0.2"), Decimal("0.2"), 2 * YEAR, always=True),
           "Habit-off arm: the same 20% losers slice at all times, no switch (M0104-C80-L60's configuration)"),
    ),
    seen_keys=(
        "concept:crash-entry-losers-slice",
        "concept:core-satellite-spy-losers",
    ),
)
