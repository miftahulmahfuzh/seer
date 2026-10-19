"""M0136 — Come back halfway first: a staged re-entry, so a false start costs half as much.

Source: variation of M0113, which held the 200-day exit fixed and moved only the buy-back
trigger. M0113's parent M0084 priced the safety switch on its own (SPY only, nothing else held).
Idea: M0113 established that the switch's two failure modes sit on opposite sides of one knob.
Buy back too slowly -- the symmetric 200-day control, or a 20-session high -- and the recovery is
slept through. Buy back too eagerly on a price-above-a-line test (the 50-day or 20-day average)
and the money is back inside the crash. M0113-UP63 found a middle trigger that avoids both by
asking a harder question (a positive 63-session return), but it closed only about a third of the
post-2009 gap. This method attacks the same whipsaw from the other direction: instead of a better
ON/OFF trigger, make the position SIZE the thing that moves.

The frame is M0084's and M0113's, deliberately unchanged: SPY only, nothing else ever held,
fractional shares at Gotrade's real fees on the owner's real deposits, the same 253-bar lookback
and therefore exactly the same sessions, so every number here is paired against M0084-MONTHLY
(funded CAGR 31.68%, MAR 0.483, 11 trades) and M0113-UP63 (31.35% ... 32.14%, MAR 0.469, 18
trades) with the staging as the only difference.

**The exit is unchanged, and keeping it unchanged is the hard part.** The book engine tells an
allocator only *whether* SPY is held, never *how much* of it, so a three-state ladder cannot read
its own rung out of ``held``. The rung is instead recovered from price alone, and the exit is
protected by a freshness test: a below-the-200-day reading that comes within ``FRESH_EXIT_N``
sessions of an above-the-200-day one is a *fresh break*, and a fresh break always goes to cash,
exactly as in M0084 and M0113. ``FRESH_EXIT_N`` is 32 sessions, comfortably longer than the
longest gap between two monthly checks (about 23 sessions) and far shorter than any of the three
bear markets the switch is paid to sit out, which ran hundreds of sessions below the line. So the
first monthly check after a break always sells everything; only once the fall has lasted more
than a month and a half can the ladder buy anything back.

The rungs, read on each monthly check from SPY's own closes and no new data:

    * above the 200-day average -> **full weight**, in every variant;
    * else a fresh break -> **cash**, in every variant (the exit);
    * else, for a staged variant, the highest rung whose condition holds:
      above the 50-day average -> two thirds (three-step variants only);
      the first trigger on -> one half (two-step) or one third (three-step);
      nothing -> cash.

``levels=1`` restores M0113's binary switch verbatim, ``held``-asymmetry and all, so SMA200 and
UP63 are true paired controls rather than approximations: SMA200 must reproduce M0084-MONTHLY's
11 trades and 0.483 MAR, and UP63 must reproduce M0113-UP63's 18 trades and 0.469 MAR. If either
fails to reproduce, the staging machinery is wrong and nothing else on this page is readable.

``sticky`` is the one arm that reads ``held`` while staged: once the part position exists it is
kept even if the first trigger reverses, and only a fresh break can sell it. That separates the
two halves of the whipsaw cost -- the re-buying and the re-selling -- which the binary switch
charges for together.

Reads only bars dated <= ``data_date``. ``held`` is read, and a deposit cannot move it: a deposit
changes cash, not whether SPY is held. Pure: no clock, no I/O, no randomness.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0084_trend_switch_price import FABER_MONTHS
from seer_engine.lab.methods.m0113_trend_switch_reentry import entry_on
from seer_engine.sim.book import Target, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, trend_on

ADDED = date(2026, 10, 19)
BENCH = "SPY"  # the only instrument this method ever holds, and the ladder's own yardstick
SMA_N = 200  # the exit average, frozen for every variant
MID_SMA_N = 50  # the middle rung of a three-step ramp: the 50-day average
#: M0084's constant, reused unchanged so all three methods are scored on the same sessions.
LOOKBACK = max(SMA_N, 23 * (FABER_MONTHS + 1))
#: F4's gate value: the exit is the lab's switch, not a re-implementation of it.
EXIT_GATE = FactorParams(rank="momentum", trend=(BENCH, SMA_N))
#: A below-the-line reading this close behind an above-the-line one is a fresh break -> cash.
#: Longer than the longest gap between monthly checks (~23 sessions), far shorter than a bear.
FRESH_EXIT_N = 32

Entry = Literal["sma200", "sma", "up"]
_ENTRIES: tuple[str, ...] = ("sma200", "sma", "up")
_MAX_ENTRY_N = 150  # entry windows must stay well inside LOOKBACK
_LEVELS: tuple[int, ...] = (1, 2, 3)
#: The weight of rung k of an n-rung ladder, quantized down like every other weight.
_RUNG: dict[tuple[int, int], Decimal] = {
    (2, 1): to_weight(Decimal(1) / Decimal(2)),
    (3, 1): to_weight(Decimal(1) / Decimal(3)),
    (3, 2): to_weight(Decimal(2) / Decimal(3)),
}
_FULL = to_weight(Decimal(1))


@dataclass(frozen=True, slots=True)
class StagedParams:
    """How SPY is bought back, and in how many steps. The exit carries no parameter."""

    entry: Entry = "sma200"
    entry_n: int = 0  # window the first trigger reads; 0 for "sma200", which reads SMA_N
    levels: int = 1  # 1 = M0113's binary switch; 2 = half then full; 3 = third, two thirds, full
    sticky: bool = False  # the part position is kept when the first trigger reverses

    def __post_init__(self) -> None:
        if not isinstance(self.entry, str) or self.entry not in _ENTRIES:
            raise ValueError(f"entry must be one of {_ENTRIES}, got {self.entry!r}")
        if isinstance(self.entry_n, bool) or not isinstance(self.entry_n, int):
            raise TypeError(f"entry_n must be an int, got {type(self.entry_n).__name__}")
        if self.entry == "sma200":
            if self.entry_n != 0:
                raise ValueError(f"entry_n must be 0 for entry='sma200', got {self.entry_n}")
            if self.levels != 1:
                raise ValueError("entry='sma200' is the symmetric control and has only one step")
        elif not 2 <= self.entry_n <= _MAX_ENTRY_N:
            raise ValueError(f"entry_n must be in [2, {_MAX_ENTRY_N}], got {self.entry_n}")
        if isinstance(self.levels, bool) or not isinstance(self.levels, int):
            raise TypeError(f"levels must be an int, got {type(self.levels).__name__}")
        if self.levels not in _LEVELS:
            raise ValueError(f"levels must be one of {_LEVELS}, got {self.levels}")
        if not isinstance(self.sticky, bool):
            raise TypeError(f"sticky must be a bool, got {type(self.sticky).__name__}")
        if self.sticky and self.levels == 1:
            raise ValueError("sticky needs a part position to be sticky about: levels >= 2")

    def as_dict(self) -> dict[str, str]:
        return {
            "entry": self.entry,
            "entry_n": str(self.entry_n),
            "levels": str(self.levels),
            "sticky": str(self.sticky),
        }


def _check(params: object) -> StagedParams:
    if not isinstance(params, StagedParams):
        raise TypeError(f"params must be StagedParams, got {type(params).__name__}")
    return params


def above_sma(h: History | None, data_date: date, n: int) -> bool:
    """True when the last close through ``data_date`` is strictly above its own ``n``-day mean."""
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None or i + 1 < n:
        return False
    close = h.close
    return bool(close[i] > float(np.mean(close[i + 1 - n : i + 1])))


def fresh_break(h: History | None, data_date: date) -> bool:
    """True when SPY closed above its 200-day average within the last ``FRESH_EXIT_N`` sessions.

    This is what keeps the exit identical to M0084's and M0113's. A ladder that reads only
    today's conditions would answer a fall out of a full position with a trim to a part position;
    the freshness test forces that first below-the-line check to go all the way to cash, and only
    lets the ladder act once the market has been under its 200-day average for longer than the
    gap between two monthly checks.
    """
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None or i + 1 < SMA_N + 1:
        return False
    close = h.close
    first = max(SMA_N - 1, i + 1 - FRESH_EXIT_N)
    # Rolling 200-day means over [first, i], compared with each day's own close.
    sums = np.cumsum(np.concatenate(([0.0], close[: i + 1].astype(float))))
    for j in range(first, i + 1):
        sma = (sums[j + 1] - sums[j + 1 - SMA_N]) / SMA_N
        if float(close[j]) > sma:
            return True
    return False


class StagedReentryTrendSwitch:
    """SPY at full, part or no weight: one fixed exit and a variant's own ramp back in."""

    id = "M0136"

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
        return False  # the ladder reads SPY's own closes; index membership is never touched

    def _weight(self, history: Mapping[str, History], data_date: date, held: frozenset[str],
                p: StagedParams) -> Decimal | None:
        """How much SPY should be held after this check, or None for cash."""
        h = history.get(BENCH)
        if p.levels == 1:
            # M0113's binary switch, verbatim: the exit rule while held, the entry rule while out.
            on = (trend_on(history, data_date, EXIT_GATE)
                  if BENCH in held or p.entry == "sma200"
                  else entry_on(h, data_date, p))
            return _FULL if on else None
        if trend_on(history, data_date, EXIT_GATE):
            return _FULL
        if fresh_break(h, data_date):
            return None  # the exit, unchanged: a fall out of the market goes all the way to cash
        if p.levels == 3 and above_sma(h, data_date, MID_SMA_N):
            return _RUNG[(3, 2)]
        if entry_on(h, data_date, p) or (p.sticky and BENCH in held):
            return _RUNG[(p.levels, 1)]
        return None

    def _run(self, history: Mapping[str, History], data_date: date, held: frozenset[str],
             p: StagedParams) -> tuple[Target, ...]:
        h = history.get(BENCH)
        if h is None or h.index_of(data_date) is None:  # no bar dated d: no new target
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
        return dict(history)  # SPY-only and cheap: nothing to precompute

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, Mapping):
            raise TypeError(f"prepared must be a Mapping, got {type(prepared).__name__}")
        return self._run(prepared, data_date, held, _check(params))


LADDER = StagedReentryTrendSwitch()


def _v(suffix: str, params: StagedParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0136-{suffix}", family="M0136", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=LADDER, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0136",
    name="Come back halfway first: a staged re-entry that makes a false start cost half as much",
    family="market-trend-switch",
    source_kind="variation",
    source_ref="variation of M0113 (the 200-day exit held fixed, only the buy-back moved)",
    parent_id="M0113",
    hypothesis=(
        "M0113 showed the buy-back half of the shared 200-day safety switch is where the money "
        "goes, and that the two failure modes sit on opposite sides of one knob. Buy back too "
        "slowly (the symmetric 200-day control, or a 20-session high) and the recovery is slept "
        "through: the control lost 5.9 points a year to SPY over 2009-2015 and the 20-session "
        "high lost 9.8. Buy back too eagerly on a price-above-a-line test (the 50-day or 20-day "
        "average) and the money is back inside the crash: 2008 went from flat to -10.7%, 2001 to "
        "-15.2%, and the worst fall from 18.9% to 25-36%. M0113-UP63 found a trigger that avoids "
        "both by asking a harder question (a positive 63-session return), but it still closed "
        "only about a third of the 2009-2015 gap, so the knob is not yet where it should be. "
        "This method attacks the same whipsaw from a different direction: instead of a better "
        "ON/OFF trigger, make the position SIZE the thing that moves. The exit is unchanged -- a "
        "fresh break below the 200-day average goes all the way to cash -- and re-entry comes in "
        "steps: a part position when the early trigger fires, the rest only once SPY has "
        "reclaimed its 200-day average. A false start then costs half (or a third) of what it "
        "cost the 50-day trigger, while a genuine bottom is participated in from months earlier, "
        "which is exactly the asymmetry M0113's year-by-year table asks for. The switch's two "
        "halves are nothing new -- the banded moving-average rule is 1992 and Faber's ten-month "
        "version 2007 -- so no fade argument applies; what is new is paying for the buy-back in "
        "instalments rather than all at once. Frame: SPY only, fractional shares at Gotrade's "
        "real fees on the owner's deposits, the same 253-bar lookback as M0084 and M0113, so all "
        "three are scored on exactly the same sessions and every difference is the staging "
        "alone. Six variants: the two paired controls SMA200 (which must reproduce "
        "M0084-MONTHLY's 11 trades and 0.483 MAR) and UP63 (which must reproduce M0113-UP63's 18 "
        "trades and 0.469 MAR); HALF-UP63 and HALF-SMA50 (half in on the quarter-return and on "
        "the 50-day cross respectively, full in above the 200-day); THIRDS-UP63 (a third on the "
        "quarter-return, two thirds above the 50-day average, the rest above the 200-day, so the "
        "ramp has three steps); and HALF-UP63-HOLD (the same as HALF-UP63 but the half position "
        "is NOT sold if the early trigger reverses, only on a fresh 200-day break, which tests "
        "whether the re-selling or the re-buying is what costs). SUCCESS: a staged variant that "
        "beats M0113-UP63's funded return AND closes at least half of the control's 5.9-point "
        "2009-2015 gap, without pushing the worst fall past 25%. Eligibility is not expected -- a "
        "100%-SPY book cannot clear the 100-trade bar and the trade counts will be in the tens -- "
        "so the paired differences are the result, and profit factor and DSR are close to "
        "meaningless here. Note the window starts 1994-01-28, not the usual 1996-01-03, so "
        "compare only with M0084's and M0113's numbers."
    ),
    expected_failure=(
        "The obvious failure is that half a position earns half the recovery, so the staged "
        "versions land exactly halfway between the control and UP63 on every number and teach "
        "nothing a weighted average of the two would not have told us -- in which case the answer "
        "is that the trigger, not the sizing, is the lever, and this family should be closed. The "
        "second risk is that holding a part position through a continued fall is the worst of "
        "both worlds: exposed to the crash and under-exposed to the recovery, which would show up "
        "as a deeper fall than UP63 with no more return. May 2008 is the specific date to look "
        "at: SPY's 63-session return turned positive that spring while it was still under its "
        "200-day average and more than a month past its break, so every staged variant is "
        "expected to be holding a part position going into the autumn of 2008, and HALF-UP63-HOLD "
        "to still be holding it at the bottom. The third risk is mechanical and is why the two "
        "controls exist: the book engine tells an allocator only whether SPY is held, never how "
        "much, so the ladder's rung is recovered from price with a 32-session freshness test "
        "rather than from the book's state. If that recovery is wrong, the exit is no longer "
        "M0084's and the paired differences are unreadable -- SMA200 and UP63 reproducing their "
        "parents to the decimal is the check, and if either misses, nothing else here should be "
        "believed. Fourth, the ladder trades more than the binary switch by construction (a trim "
        "and an add where the switch had one flip), and at Gotrade's real fees on a 20M IDR book "
        "those part-sized orders pay the worst of the fee schedule, so some of the gap will be "
        "eaten before it is earned. Not modelled anywhere: interest on the cash held while the "
        "switch is off or half off, which flatters SPY and penalises every switched variant, so "
        "every gap reported here is an upper bound on the switch's cost."
    ),
    candidates=(
        _v("SMA200", StagedParams("sma200"),
           "Control: the symmetric 200-day switch -- must reproduce M0084-MONTHLY"),
        _v("UP63", StagedParams("up", 63, 1),
           "Control: M0113's best buy-back, all at once -- must reproduce M0113-UP63"),
        _v("HALF-UP63", StagedParams("up", 63, 2),
           "Half in when the last quarter turns positive, the rest above the 200-day average"),
        _v("HALF-SMA50", StagedParams("sma", 50, 2),
           "Half in above the 50-day average, the rest above the 200-day one"),
        _v("THIRDS-UP63", StagedParams("up", 63, 3),
           "A third on the quarter-return, two thirds above the 50-day, the rest above the 200-day"),
        _v("HALF-UP63-HOLD", StagedParams("up", 63, 2, True),
           "The same half-step, but the half is kept unless a fresh 200-day break sells it"),
    ),
    seen_keys=(
        "concept:staged-partial-reentry-after-sma200-exit",
        "concept:position-size-ramp-trend-switch",
        "concept:half-weight-bear-market-reentry",
    ),
)
