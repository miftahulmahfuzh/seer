"""M0113 — Slow to leave, quick to return: hold the 200-day exit fixed and vary only the buy-back.

Source: variation of M0084, which priced the safety switch alone (SPY only, nothing else in the
book) across four readings and two cadences.
Idea: M0084 found that the whole 22-year advantage of the 200-day switch is the three falls it
sits out -- 2001, 2002 and 2008 -- and that it pays for them everywhere else, most brutally in
2009, where the same slow average that correctly got it out kept it out through the recovery.
Over 2009-2015 every reading of it lost 6 to 11 points a year to simply holding SPY. So the exit
is the good half and the return is the expensive half. This method freezes the exit and moves
only the trigger that buys back.

The frame is M0084's, deliberately: SPY only, at full weight, nothing else ever held, fractional
shares at Gotrade's real fees on the owner's real deposits, and the same 253-bar lookback, so
every variant here is scored on exactly the same sessions as M0084's six and the paired
difference against M0084-MONTHLY (+9.1% a year funded, 18.9% worst fall, 11 trades) is the
buy-back trigger alone.

The switch is asymmetric, which is the whole point, and the asymmetry is expressed through
``held``: the allocator applies the EXIT rule only when SPY is already held, and the ENTRY rule
only when it is not. The exit is identical in every variant -- ``f_factor.trend_on`` unchanged,
SPY's close strictly above its 200-day average, the same gate F4, M0063, M0070, M0084 and M0101
run behind -- so a variant can only differ in how it comes back. Six entry rules, all read from
SPY's own closes, no new data:

    * ``entry="sma200"``: the control. Entry and exit are the same test, so this variant IS
      M0084's symmetric monthly switch under a new allocator id, and it must reproduce
      M0084-MONTHLY's 11 trades and 18.9% worst fall. If it does not, the asymmetry machinery is
      wrong and every other number here is unreadable.
    * ``entry="sma"`` with ``entry_n=50`` / ``20``: back in when SPY closes above its 50-day
      (respectively 20-day) average, while still under the 200-day one.
    * ``entry="up"`` with ``entry_n=63``: back in when SPY's 63-session return is positive.
    * ``entry="high"`` with ``entry_n=20``: back in when SPY closes at or above its highest close
      of the last 20 sessions.

The sixth variant, SMA50-W, is the asymmetric CADENCE rather than an asymmetric rule: the
entry is the 50-day average read WEEKLY while the exit stays roughly monthly. The book must
rank weekly for the entry to act weekly at all, so the exit is instead gated inside the
allocator to the weekly check whose ``data_date`` falls in the last seven calendar days of its
month (``month_end_window``). Seven consecutive calendar days hold exactly one weekly check's
data date in a normal month, so that is one exit check a month, which is what M0084-MONTHLY got
-- an approximation of the monthly clock, not the clock itself, and the control's trade count is
what says whether it behaved. This arm exists because M0084 showed weekly reading is destructive
only when it also causes SELLING: weekly WEEKLY lost 4.7 points a year to monthly MONTHLY, and
only 0.7 of that was fees.

Reads only bars dated <= ``data_date``; ``held`` is read, and that is intentional -- the state
this switch needs is "am I in or out", which is exactly what the book knows. A deposit cannot
move it: a deposit changes cash, not whether SPY is held. Pure: no clock, no I/O, no randomness.
"""

from __future__ import annotations

import calendar
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0063_earnings_day_jump import WEEKLY_HOLD_FRAC_GOTRADE
from seer_engine.lab.methods.m0084_trend_switch_price import FABER_MONTHS
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, trend_on

ADDED = date(2026, 10, 14)
BENCH = "SPY"  # the only instrument this method ever holds, and the switch's own yardstick
SMA_N = 200  # the exit average, frozen for every variant
#: M0084's constant, reused unchanged so the two methods are scored on the same sessions.
LOOKBACK = max(SMA_N, 23 * (FABER_MONTHS + 1))
#: F4's gate value: the exit is the lab's switch, not a re-implementation of it.
EXIT_GATE = FactorParams(rank="momentum", trend=(BENCH, SMA_N))
#: How many calendar days at the end of a month count as that month's exit check (SMA50-W only).
MONTH_END_DAYS = 7

Entry = Literal["sma200", "sma", "up", "high"]
_ENTRIES: tuple[str, ...] = ("sma200", "sma", "up", "high")
_MAX_ENTRY_N = 150  # entry windows must stay well inside LOOKBACK


@dataclass(frozen=True, slots=True)
class ReentryParams:
    """How SPY is bought back. The exit is fixed and carries no parameter."""

    entry: Entry = "sma200"
    entry_n: int = 0  # window the entry rule reads; 0 for "sma200", which reads SMA_N
    month_end_window: bool = False  # gate the exit to one check a month (weekly cadence only)

    def __post_init__(self) -> None:
        if not isinstance(self.entry, str) or self.entry not in _ENTRIES:
            raise ValueError(f"entry must be one of {_ENTRIES}, got {self.entry!r}")
        if isinstance(self.entry_n, bool) or not isinstance(self.entry_n, int):
            raise TypeError(f"entry_n must be an int, got {type(self.entry_n).__name__}")
        if self.entry == "sma200":
            if self.entry_n != 0:
                raise ValueError(f"entry_n must be 0 for entry='sma200', got {self.entry_n}")
        elif not 2 <= self.entry_n <= _MAX_ENTRY_N:
            raise ValueError(f"entry_n must be in [2, {_MAX_ENTRY_N}], got {self.entry_n}")
        if not isinstance(self.month_end_window, bool):
            raise TypeError(
                f"month_end_window must be a bool, got {type(self.month_end_window).__name__}"
            )

    def as_dict(self) -> dict[str, str]:
        return {
            "entry": self.entry,
            "entry_n": str(self.entry_n),
            "month_end_window": str(self.month_end_window),
        }


def _check(params: object) -> ReentryParams:
    if not isinstance(params, ReentryParams):
        raise TypeError(f"params must be ReentryParams, got {type(params).__name__}")
    return params


def is_month_end_check(d: date) -> bool:
    """True when ``d`` falls in the last ``MONTH_END_DAYS`` calendar days of its month.

    The weekly checks are about seven calendar days apart, so a seven-day window holds exactly
    one of them in a normal month: this turns a weekly rank cadence into a monthly exit check
    without the allocator knowing the session calendar.
    """
    last = calendar.monthrange(d.year, d.month)[1]
    return d.day > last - MONTH_END_DAYS


def entry_on(h: History | None, data_date: date, p: ReentryParams) -> bool:
    """True when the buy-back trigger fires on ``data_date``. Reads only bars dated <= it."""
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None:
        return False
    n = p.entry_n
    if i + 1 < n + (1 if p.entry == "up" else 0):
        return False
    close = h.close
    if p.entry == "sma":
        return bool(close[i] > float(np.mean(close[i + 1 - n : i + 1])))
    if p.entry == "up":
        return bool(close[i] > close[i - n])
    return bool(close[i] >= float(np.max(close[i + 1 - n : i + 1])))


class ReentryTrendSwitch:
    """100% SPY, with one fixed exit and a variant's own way back in. Nothing else is held."""

    id = "M0113"

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
        return False  # the switch reads SPY's own closes; index membership is never touched

    def _on(self, history: Mapping[str, History], data_date: date, held: frozenset[str],
            p: ReentryParams) -> bool:
        """Should SPY be held after this check? The exit rule when in, the entry rule when out."""
        if BENCH in held:
            if p.month_end_window and not is_month_end_check(data_date):
                return True  # not this month's exit check: the position is not reconsidered
            return trend_on(history, data_date, EXIT_GATE)
        if p.entry == "sma200":
            return trend_on(history, data_date, EXIT_GATE)
        return entry_on(history.get(BENCH), data_date, p)

    def _run(self, history: Mapping[str, History], data_date: date, held: frozenset[str],
             p: ReentryParams) -> tuple[Target, ...]:
        h = history.get(BENCH)
        if h is None or h.index_of(data_date) is None:  # no bar dated d: no new target
            return ()
        if not self._on(history, data_date, held, p):
            return ()
        t = target_from_close(BENCH, last_close(h, data_date), equal_weight(1))
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


SWITCH = ReentryTrendSwitch()


def _v(suffix: str, params: ReentryParams, rules: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0113-{suffix}", family="M0113", rules=rules, allocator=SWITCH,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())



# --------------------------------------------------------------------------- amendment 1

#: The yardstick's lookback, pinned to M0113's own ``LOOKBACK`` (253, M0084's constant). That
#: is what keeps this arm on exactly the sessions the six recorded arms ran on: all of them open
#: 1994-01-28, and so does this one. A bill read off an arm scored on a different window is not
#: a bill.
#:
#: ``LOOKBACK`` rather than a literal 253 on purpose: it says "the same sessions as every other
#: arm here" to a reader, which a number cannot.
ALWAYS_LOOKBACK = LOOKBACK

#: Full weight, once, so the target builder below allocates no new Decimal per session.
ALWAYS_FULL = equal_weight(1)



@dataclass(frozen=True, slots=True)
class AlwaysParams:
    """No dial at all: ``hold`` is held on every session and there is no gate to open.

    A separate params type rather than a ``ReentryParams`` with the exit disabled: the exit is
    fixed in every variant by design -- it is the half of the switch M0113 was built to hold
    still -- so "no exit at all" is a new allocator, not a new setting, and a recorded row that
    claimed an exit while none ran would be a lie.
    """

    hold: str = BENCH

    def __post_init__(self) -> None:
        if not isinstance(self.hold, str) or not self.hold or self.hold != self.hold.upper():
            raise ValueError(f"hold must be a non-empty upper-case symbol, got {self.hold!r}")

    def as_dict(self) -> dict[str, str]:
        return {"hold": self.hold, "gate": "none"}


def _always(params: object) -> AlwaysParams:
    if not isinstance(params, AlwaysParams):
        raise TypeError(f"params must be AlwaysParams, got {type(params).__name__}")
    return params


class AlwaysAllocator:
    """M0113's frame with the exit taken out: SPY held every session, never in cash.

    ``ReentryParams`` cannot express this. The exit is fixed in every variant by design -- it is
    the half of the switch M0113 was built to hold still -- so "no exit at all" is a new
    allocator, not a new setting. The lookback is M0113's own ``LOOKBACK`` (253, M0084's
    constant), which is what keeps this arm on exactly the sessions the six recorded arms ran on:
    all of them open 1994-01-28.
    """

    id = "M0113-ALWAYS"

    def lookback(self, params: Any) -> int:
        _always(params)
        return ALWAYS_LOOKBACK

    def symbols(self, params: Any) -> tuple[str, ...]:
        return (_always(params).hold,)

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_always(params).hold,)

    def uses_members(self, params: Any) -> bool:
        _always(params)
        return False

    def _run(self, history: Mapping[str, History], data_date: date,
             p: AlwaysParams) -> tuple[Target, ...]:
        h = history.get(p.hold)
        if h is None or h.index_of(data_date) is None:  # no bar dated d: never a new target
            return ()
        t = target_from_close(p.hold, last_close(h, data_date), ALWAYS_FULL)
        return () if t is None else (t,)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(history, data_date, _always(params))

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)  # one instrument: nothing to precompute

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, Mapping):
            raise TypeError(f"prepared must be a Mapping, got {type(prepared).__name__}")
        return self._run(prepared, data_date, _always(params))


ALWAYS = AlwaysAllocator()

AMEND_ALWAYS = Amendment(
    added=date(2026, 10, 27),
    why=(
        "Every M0113 arm carries the same 200-day exit, so the six paired differences price the "
        "buy-back trigger and nothing prices the exit. This arm holds SPY on every session of the "
        "same window, which is the only way to read what the exit itself costs."
    ),
    hypothesis=(
        "M0113 holds one exit fixed and moves only the way back in, and that design means the "
        "method cannot see its own largest term. M0084 reported the switch's whole advantage as "
        "three falls sat out and a 6-to-11-point annual loss to holding SPY over 2009-2015, but "
        "that was measured against SPY in a different run on a different allocator. M0389 then "
        "showed that pricing a step-aside habit against another step-aside arm understates it by "
        "roughly half. This arm is SPY at full weight on every session, on M0113's own monthly "
        "rule set at Gotrade's real fees, at M0113's own 253-bar lookback, so it opens 1994-01-28 "
        "with all six recorded arms and every difference against it is the exit plus that arm's "
        "own re-entry. Subtracting the control arm M0113-SMA200 from it gives the exit's own "
        "bill; subtracting each other arm from M0113-SMA200 gives the re-entry's, which is what "
        "M0113 already reported. Success is the two terms separated, with a statement of how much "
        "of M0113's recorded 2009-2015 gap was the exit rather than the trigger. This arm is a "
        "yardstick and not a candidate: a 100%-SPY book paying Gotrade's fees cannot beat "
        "total-return SPY, and it must not be promoted."
    ),
    expected_failure=(
        "M0113's arms trade between 11 and 43 times in twenty-two years, so profit factor and the "
        "luck score are close to meaningless on this method and the yardstick cannot repair that: "
        "whatever the exit's bill turns out to be, it rests on three episodes. The likeliest "
        "disappointing outcome is that the exit's bill comes out so large that it swamps every "
        "re-entry difference M0113 measured, which would mean the method's whole published "
        "ordering is a comparison between arms that all paid the same large bill -- true, useful, "
        "and a flat answer rather than an interesting one. Second, this arm will record the "
        "deepest fall in the method by a very wide margin: the six recorded arms sit between "
        "18.89% and 35.61%, and an unswitched SPY book holds the whole of 2000-2002 and 2008. "
        "Third, the arm runs later than the arms it prices; the evidence that this is survivable "
        "is the exact three-way reproduction of one configuration across two run dates measured "
        "on 2026-10-27 (M0038-DIV-OPEN, M0173-EXP100, M0336-NEVER), and if M0113-ALWAYS does not "
        "reproduce total-return SPY less Gotrade's fees over 1994-2015 to a comparable fidelity, "
        "the bill must be reported as unreadable rather than quoted."
    ),
    candidates=(
        Candidate(
            id="M0113-ALWAYS", family="M0113", rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=ALWAYS,
            params=AlwaysParams(),
            rationale=("Yardstick: SPY held on every session with no exit and no re-entry rule, "
                       "so the 200-day exit's own cost can be separated from the buy-back "
                       "trigger's instead of the two being quoted as one number."),
            added=date(2026, 10, 27), owner_inputs=(),
        ),
    ),
)


METHOD = Method(
    id="M0113",
    name="Slow to leave, quick to return: keep the 200-day exit and vary only how fast the safety rule buys back",
    family="market-trend-switch",
    source_kind="variation",
    source_ref="variation of M0084 (the safety switch priced on its own, SPY only)",
    parent_id="M0084",
    hypothesis=(
        "The moving-average switch is old -- published 1992 (the banded rule) and 2007 (Faber's "
        "10-month version) -- so nothing here is a new anomaly and no fade argument applies to "
        "it; what is new is which HALF of it is being paid for. M0084 priced the switch alone "
        "and found its whole 22-year advantage is sitting out 2001, 2002 and 2008, paid for "
        "everywhere else: it lost 18 points in 2009 alone and 10 points in 2003, both times "
        "because the same slow 200-day average that correctly got it out kept it out through the "
        "recovery, and in 2009-2015 every reading of it lost 6 to 11 points a year to simply "
        "holding SPY. The exit is the good half; the return is the expensive half. So hold the "
        "exit fixed -- at the monthly check, SPY's close under its 200-day average goes to cash, "
        "f_factor.trend_on unchanged -- and move ONLY the trigger that buys back. Frame: SPY "
        "only at full weight, fractional shares at Gotrade's real fees on the owner's deposits, "
        "the same 253-bar lookback as M0084, so every variant is scored on the same sessions and "
        "the paired difference against M0084-MONTHLY (+9.1% a year funded, 18.9% worst fall, 11 "
        "trades, de-funded +10.7% in 2009-2015 against SPY's +16.6%) is the buy-back trigger "
        "alone. The asymmetry is expressed through the held set: the exit rule is applied only "
        "while SPY is held, the entry rule only while it is not. Six buy-backs, all read from "
        "SPY's own closes with no new data: SMA200 (the control, which must reproduce "
        "M0084-MONTHLY's 11 trades and 18.9% fall under this allocator id, or the machinery is "
        "wrong); SMA50 and SMA20 (back in above the 50-day or 20-day average while still under "
        "the 200-day one); UP63 (back in when the 63-session return is positive); HIGH20 (back "
        "in at a 20-session high); and SMA50-W, the asymmetric CADENCE -- the 50-day trigger "
        "read WEEKLY while the exit is gated to one check a month, the one place where reading "
        "more often might pay, since M0084 showed weekly reading is destructive only when it "
        "also causes selling. SUCCESS: a variant that keeps the 2001, 2002 and 2008 exits, keeps "
        "the worst fall inside the bars in force, and closes at least half of M0084-MONTHLY's "
        "5.9-point 2009-2015 gap to SPY. Eligibility is not expected -- a 100%-SPY book cannot "
        "beat SPY except by sidestepping crashes for more than whipsaw costs, and the trade "
        "counts will be far under 100 -- so the paired differences are the result. Note the "
        "window starts 1994-01-28 here, not the usual 1996-01-03, so compare only with M0084's "
        "numbers. Note also that the drawdown bars moved on 2026-10-14: the dev screen is 50% "
        "and the real-money bar 25%, where the idea row was written against the old 20%."
    ),
    expected_failure=(
        "The obvious way this fails is whipsaw, and it is designed in: an entry that fires above "
        "the 50-day or 20-day average, or at a 20-session high, can fire while SPY is still well "
        "under its 200-day average -- which is precisely a bear-market bounce. The book then "
        "buys back into 2001, 2002 or 2008, the next monthly check sees it still under the "
        "200-day line and sells again, and the variant pays the fall it was supposed to sit out "
        "plus the fees. SMA20 and HIGH20 are the most exposed; UP63 is the most protected, "
        "because a positive 63-session return is hard to produce inside a crash, and it may "
        "therefore buy back barely sooner than the control and recover nothing. The likeliest "
        "overall outcome is that the fast triggers trade the 2009 recovery gap for a deeper 2008 "
        "fall -- better in the era most like today, worse exactly where the switch earns its "
        "keep -- which would mean the switch's two halves cannot be separated and the lab should "
        "stop trying. Trade counts stay tiny (tens over 22 years), so profit factor and DSR are "
        "close to meaningless here and no variant will clear the luck bar at N=82; the funded "
        "return, the worst fall and the 2009-2015 era split are the only readable numbers. "
        "SMA50-W carries one extra risk the others do not: its monthly exit check is an "
        "approximation -- the weekly check whose data date lands in the last seven calendar days "
        "of its month -- so a holiday-shifted month can give it two exit checks or none, and its "
        "flip count should be read against the control's before anything else about it is "
        "believed. Not modelled anywhere: interest on the cash held while the switch is off, "
        "which flatters SPY and penalises every switched variant, so every gap reported here is "
        "an upper bound on the switch's cost."
    ),
    candidates=(
        _v("SMA200", ReentryParams("sma200"), MONTHLY_HOLD_FRAC_GOTRADE,
           "Control: the symmetric 200-day switch, monthly -- must reproduce M0084-MONTHLY"),
        _v("SMA50", ReentryParams("sma", 50), MONTHLY_HOLD_FRAC_GOTRADE,
           "Out under the 200-day average, back in above the 50-day one, both read monthly"),
        _v("SMA20", ReentryParams("sma", 20), MONTHLY_HOLD_FRAC_GOTRADE,
           "The same exit, back in above the 20-day average: the fastest average trigger"),
        _v("UP63", ReentryParams("up", 63), MONTHLY_HOLD_FRAC_GOTRADE,
           "The same exit, back in when SPY's last-quarter return turns positive"),
        _v("HIGH20", ReentryParams("high", 20), MONTHLY_HOLD_FRAC_GOTRADE,
           "The same exit, back in when SPY closes at its highest in 20 sessions"),
        _v("SMA50-W", ReentryParams("sma", 50, True), WEEKLY_HOLD_FRAC_GOTRADE,
           "The 50-day trigger read weekly while the exit stays one check a month"),
    ),
    amendments=(AMEND_ALWAYS,),
    seen_keys=(
        "concept:asymmetric-trend-switch-reentry",
        "concept:fast-reentry-after-sma200-exit",
        "concept:asymmetric-switch-cadence",
    ),
)
