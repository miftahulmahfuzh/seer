"""M0234 — Let the instalment rule act on ordinary dips: shorten the staged re-entry's blackout.

Source: variation of M0136 (staged re-entry), itself a variation of M0113 and M0084. The banded
moving-average exit is 1992 and Faber's ten-month version 2007, so no fade argument applies.

Idea: M0136 carried a guard that was not part of the idea it tested. A below-the-200-day reading
within ``FRESH_EXIT_N`` = 32 sessions of an above-the-line reading counted as a fresh break and
went all the way to cash, with no instalment allowed. The guard exists for a real reason: without
it a fall out of a fully invested position becomes a trim to half rather than a clean exit. But 32
sessions is about six weeks, long enough to swallow an ordinary dip whole (August 2011: the staged
rule never took its half step, and HALF-UP63 matched the plain SMA200 control to the decimal in
2011-2012). The shortest blackout that keeps the clean exit is ONE monthly check: 23 sessions is
the longest gap between two monthly checks, so any blackout at or above 23 guarantees the first
below-the-line check after a break sells everything. This method makes the blackout a dial and
puts two settings of it on the same two staged rules M0136 tried: 23 sessions (the minimum that
preserves the exit) and 12 (below one check interval, which deliberately lets a mid-month
recovery ramp back in and shows what the guard was buying).

Everything else is M0136's, imported and not re-implemented: SPY only, fractional shares at
Gotrade's real fees, the same 253-bar lookback, the same exit gate, the same rungs, so every
difference against M0136-HALF-UP63 (blackout 32) is the blackout alone.

Controls are cited, not re-run (lab twins / lab show M0136): M0136-SMA200 (trial 764), M0136-UP63
(765), M0136-HALF-UP63 (766, the same rule at blackout 32) and M0136-HALF-SMA50 (767). They are
the recorded books on the current store with identical rules and allocator logic.

Reads only bars dated <= ``data_date``. Pure: no clock, no I/O, no randomness.
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
from seer_engine.lab.methods.m0113_trend_switch_reentry import entry_on
from seer_engine.lab.methods.m0136_staged_reentry import (
    _RUNG,
    BENCH,
    EXIT_GATE,
    LOOKBACK,
    SMA_N,
    StagedParams,
    above_sma,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import trend_on

ADDED = date(2026, 11, 13)
#: The longest gap between two monthly checks. A blackout of at least this guarantees that the
#: first below-the-line check after a break sells everything.
ONE_CHECK = 23


@dataclass(frozen=True, slots=True)
class BlackoutParams:
    """M0136's staged ramp plus the blackout length, which M0136 hard-wired to 32."""

    staged: StagedParams
    blackout: int = ONE_CHECK

    def __post_init__(self) -> None:
        if not isinstance(self.staged, StagedParams):
            raise TypeError(f"staged must be StagedParams, got {type(self.staged).__name__}")
        if self.staged.levels < 2:
            raise ValueError("the blackout only exists for a staged ramp: levels >= 2")
        if isinstance(self.blackout, bool) or not isinstance(self.blackout, int):
            raise TypeError(f"blackout must be an int, got {type(self.blackout).__name__}")
        if not 1 <= self.blackout <= 64:
            raise ValueError(f"blackout must be in [1, 64], got {self.blackout}")

    def as_dict(self) -> dict[str, str]:
        return {**self.staged.as_dict(), "blackout": str(self.blackout)}


def _check(params: object) -> BlackoutParams:
    if not isinstance(params, BlackoutParams):
        raise TypeError(f"params must be BlackoutParams, got {type(params).__name__}")
    return params


def fresh_break_n(h: History | None, data_date: date, n: int) -> bool:
    """True when SPY closed above its 200-day average within the last ``n`` sessions.

    Same test as M0136's ``fresh_break`` with the window as an argument; at n=32 the two agree.
    """
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None or i + 1 < SMA_N + 1:
        return False
    close = h.close
    first = max(SMA_N - 1, i + 1 - n)
    sums = np.cumsum(np.concatenate(([0.0], close[: i + 1].astype(float))))
    for j in range(first, i + 1):
        sma = (sums[j + 1] - sums[j + 1 - SMA_N]) / SMA_N
        if float(close[j]) > sma:
            return True
    return False


class ShortBlackoutStagedReentry:
    """M0136's ladder with the post-break blackout as a dial."""

    id = "M0234"

    def lookback(self, params: Any) -> int:
        _check(params)
        return LOOKBACK

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return False

    def _weight(self, history: Mapping[str, History], data_date: date, held: frozenset[str],
                p: BlackoutParams) -> Decimal | None:
        h = history.get(BENCH)
        s = p.staged
        if trend_on(history, data_date, EXIT_GATE):
            return _RUNG_FULL
        if fresh_break_n(h, data_date, p.blackout):
            return None  # the exit: a fresh break goes all the way to cash
        if s.levels == 3 and above_sma(h, data_date, 50):
            return _RUNG[(3, 2)]
        if entry_on(h, data_date, s) or (s.sticky and BENCH in held):
            return _RUNG[(s.levels, 1)]
        return None

    def _run(self, history: Mapping[str, History], data_date: date, held: frozenset[str],
             p: BlackoutParams) -> tuple[Target, ...]:
        h = history.get(BENCH)
        if h is None or h.index_of(data_date) is None:
            return ()
        weight = self._weight(history, data_date, held, p)
        if weight is None:
            return ()
        t = target_from_close(BENCH, last_close(h, data_date), weight)
        return () if t is None else (t,)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(history, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, Mapping):
            raise TypeError(f"prepared must be a Mapping, got {type(prepared).__name__}")
        return self._run(prepared, data_date, held, _check(params))


from seer_engine.lab.methods.m0136_staged_reentry import _FULL as _RUNG_FULL  # noqa: E402

BLACKOUT = ShortBlackoutStagedReentry()


def _v(suffix: str, staged: StagedParams, blackout: int, rationale: str) -> Candidate:
    return Candidate(id=f"M0234-{suffix}", family="M0234", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BLACKOUT, params=BlackoutParams(staged, blackout),
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0234",
    name="Let the instalment rule act on ordinary dips: a shorter blackout after a break",
    family="market-trend-switch",
    source_kind="variation",
    source_ref="variation of M0136 (staged re-entry; only the 32-session blackout is moved)",
    parent_id="M0136",
    hypothesis=(
        "M0136's staged re-entry carried a guard that was not part of the idea being tested: a "
        "drop below the 200-day average within 32 sessions of an above-the-line reading counted "
        "as a fresh break and went all the way to cash, with no instalment allowed. The guard is "
        "there for a real reason -- without it a fall out of a full position becomes a trim to "
        "half, and the clean exit is the half of the switch the lab has decided to keep -- but 32 "
        "sessions is about six weeks and swallows an ordinary dip whole. The market broke its "
        "200-day average in August 2011 and recovered inside the year; the staged rule never took "
        "its half step, and M0136-HALF-UP63 earned -2.1% in 2011 and +9.8% in 2012, identical to "
        "the SMA200 control, where M0113-UP63 earned -0.4% and +13.6% (all figures from the "
        "M0136 and M0113 write-ups; to be re-read from the lab before they are quoted). The "
        "shortest blackout that preserves the clean exit is one monthly check: 23 sessions is the "
        "longest gap between two monthly checks. Arms (same SPY-only frame, 253-bar lookback, "
        "fractional shares at Gotrade's real fees, same sessions as M0084, M0113 and M0136): "
        "HALF-UP63 at a 23-session blackout, HALF-UP63 at 12 (below one check interval, which "
        "deliberately lets a mid-month recovery ramp back in and shows what the guard was "
        "buying), and the same two for HALF-SMA50. Controls are CITED, not re-run: "
        "M0136-HALF-UP63 (trial 766, the same rule at blackout 32), M0136-HALF-SMA50 (767), "
        "M0136-UP63 (765), M0136-SMA200 (764), all the same book on the current store. A "
        "separate offline check, not a lab arm, confirms the new code path at blackout 32 gives "
        "the same targets as M0136's allocator. SUCCESS: a shortened blackout recovers most of "
        "the roughly 5.5 points lost in 2011-2012 without deepening the worst fall past "
        "M0136's 18.9% or re-opening the 2008 hole the 50-day arm fell into. No fade argument: "
        "the 200-day rule dates from 1992. Eligibility is not expected (a 100%-SPY book cannot "
        "clear 100 trades); the paired differences are the result."
    ),
    expected_failure=(
        "The guard was load-bearing: shortening it converts every short dip into a half-position "
        "round trip, so more trades at Gotrade's real fees, a shallower but more frequent bleed, "
        "and possibly a deeper 2008 because the May 2008 bounce now buys back sooner. The "
        "likelier failure is that even a full recovery of the 2011-2012 points leaves the staged "
        "rule behind full-size UP63 (UP63 earns more de-funded than HALF-UP63), so sizing is "
        "settled and the family closes with a clean answer. A third possibility: 23 and 12 "
        "sessions give the same curve (the dial never moved), which would be reported as one "
        "book, not a ladder."
    ),
    candidates=(
        _v("HALF-UP63-F23", StagedParams("up", 63, 2), 23,
           "Half in on the quarter-return, blackout cut from 32 to one check interval (23)"),
        _v("HALF-UP63-F12", StagedParams("up", 63, 2), 12,
           "Same, blackout below one check interval (12): a mid-month recovery may ramp back in"),
        _v("HALF-SMA50-F23", StagedParams("sma", 50, 2), 23,
           "Half in above the 50-day average, blackout 23"),
        _v("HALF-SMA50-F12", StagedParams("sma", 50, 2), 12,
           "Half in above the 50-day average, blackout 12"),
    ),
    seen_keys=(
        "concept:staged-reentry-short-blackout",
        "concept:fresh-break-guard-length",
    ),
)
