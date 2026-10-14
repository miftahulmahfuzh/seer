"""M0148 — Let it settle: after the safety switch moves, forbid it to move again for K checks.

Source: the book, the gate-replacement frame and both triggers are M0143's, which is this
method's parent; the asymmetric-switch machinery underneath is M0113's.

Idea: M0143 answered the exit question with a no, and answered a second question nobody asked.
Every DOWN arm lost in exact proportion to HOW OFTEN IT CHANGED ITS MIND rather than to what it
measured. Time invested fell monotonically with the window -- 72.7% for the SMA200 exit, 70.7%
for DOWN126, 62.1% for DOWN63, 49.2% for DOWN21 -- while turnover rose monotonically the other
way: 5.37, 5.20, 5.65, 6.40. The mechanism is hysteresis. A 200-day average is heavily smoothed,
so a price above it tends to stay above it; a realised-return test flips sign repeatedly in a
chop, and every flip is a full liquidation followed by a later repurchase at a worse price. M0084
had already named whipsaw as the switch's standing cost, and M0096 dated the bill: this exact
book's post-2009 lag is the switch selling into the 2010, 2011 and 2015 dips and buying back
higher.

WHY THIS IS NOT M0101 AGAIN, AND THAT ASYMMETRY IS THE WHOLE BET. M0101 tried to buy hysteresis
on this same book by widening the threshold -- a band around the 200-day line -- and LOST: BAND-3
and BAND-5 finished at MAR 0.51 and 0.50 against the plain control's 0.57, and both broke the
drawdown screen. A band widens the threshold, so it delays the exit of a genuine crash by exactly
as much as it delays the exit of a chop; it pays for less whipsaw with a later exit, and that
trade has been measured and refused. A TIME LOCK does not move the threshold at all. The FIRST
exit of a genuine collapse arrives on precisely the session it arrives on today; only the rapid
re-flip afterwards is suppressed. Hysteresis in the time domain is the one domain nobody has
tried on this switch, and it is the only kind that can be bought without paying for it in the
three events the whole switch exists for.

THE RULE. The book is M0143-CALM-UP63 exactly -- the calm big dividend raisers behind a switch
that leaves on the 200-day cross and comes back when SPY's last 63 sessions have actually
returned positive, a dev-eligible arm at +11.3% funded against SPY's +7.2% -- plus ONE new
parameter. Once the switch has CHANGED STATE it may not change again for at least ``lock_k``
monthly checks. ``K0`` is the paired control and must reproduce M0143-CALM-UP63 to the digit;
``K1``, ``K2`` and ``K3`` lock for one, two and three checks; ``K3-SELL`` applies the same
three-check cool-off ONLY to the sell direction, leaving the buy-back free. That last arm exists
because M0143 showed the switch's two halves want opposite things -- quick to come back, slow to
leave -- and a symmetric cool-off may throw away the fast re-entry that FOUR books have now
confirmed (M0113, M0135, M0133, M0143). K3 against K3-SELL is therefore the cleanest pair in the
batch: same lock length, and the only difference is whether the buy-back is locked too.

THE STATE PROBLEM, AND HOW IT IS SOLVED WITHOUT ANY STATE. An allocator sees bars, members, the
data date, what the book holds, and its params. It is pure -- no clock, no I/O, no randomness,
reads only bars dated <= ``data_date`` -- and it may hold no mutable state, because one allocator
object is shared across the five variants of a run and across backtests. M0113 and M0133 express
the switch's asymmetry through ``held`` alone, which works because "am I in or out" is exactly
what the book knows. "How long since the flip" is NOT in ``held``, and there is nowhere to keep
it.

It does not have to be kept, because it can be RE-DERIVED from the bars. Three facts make that
exact. First, a monthly check's data date is the last NYSE session of the previous calendar
month: ``book_runner`` hands the allocator ``prev_session(session)`` and calls it on the first
NYSE session of each month. Second, those month ends are readable straight off SPY's own bar
dates -- SPY trades every NYSE session, so bar i is a month end exactly when bar i+1 falls in a
different month -- which needs no calendar and no clock. Third, the switch's transition is a pure
two-line function of SPY's closes: ``trend_on`` while in, ``entry_on(up, 63)`` while out, which is
M0143's ``_on`` with the state passed in rather than read off ``held``. So the machine can be
replayed forward over a bounded run of past checks, and ``past_checks`` plus ``_settled`` is that
replay.

WHAT THE REPLAY IS ALLOWED TO DECIDE, WHICH IS ALMOST NOTHING. The replay never chooses what the
book holds. ``held`` remains the authority on the current state, exactly as in M0143 -- and it is
a reliable authority here because this book parks its unfilled weight in SPY, so an "on" book
holds something even in a month with no live raiser, which is what M0143's CALM-SYM anchor
measured when it reproduced M0101-CTRL's 528 trades. The replay is consulted ONLY on a check
where a flip is actually proposed and only when ``lock_k`` is non-zero, and all it returns is a
count. A seed error near the warm-up edge can therefore at worst permit or delay one flip; it can
never make the book's state disagree with its holdings, and at ``lock_k = 0`` the replay is not
reached at all -- which is what makes K0 bit-for-bit M0143-CALM-UP63 rather than an approximation
of it.

THE WARM-UP IS PART OF THE RULE, NOT AN APPROXIMATION OF SOMETHING TRUER. The replay runs over
the last ``WARM`` monthly checks, seeded with the stateless 200-day gate at the earliest of them
and with the counter seeded "long settled", so a lock never binds on a state the replay merely
assumed. Replaying from the first bar in the history instead would be just as pure, but it would
make the answer depend on how far back a particular research store happens to reach -- different
on the dev store and the survivorship-check store -- and it would be re-run from scratch on every
one of ~237 checks. A fixed window is bounded, is declarable in ``lookback``, is identical on
every store, and defines the rule honestly: this is the switch warmed up over the last eight
monthly checks. The machine re-synchronises on its own wherever the two triggers agree, because
on such a check the next state is the same whatever the previous one was.

NOTHING ELSE MOVES. ``WARM`` and ``CHECK_SESSIONS`` are module constants rather than params, so
they are recorded by this file's source sha and not by any config digest: they are not knobs
being swept, and a later batch that wants to sweep them is a new pre-registration. ``lookback``
is 410 for every arm, which is above M0143's 253 and below the 426 the lab's longest-lookback
methods already declare; because this book reads only SPY and index membership, and the dev store
holds 739 SPY bars on or before the first membership snapshot, the dev window still opens
1996-01-03 and the five arms are scored on exactly the sessions M0143's six were.

Pure: reads only bars and dividends dated <= ``data_date``. ``held`` is read, which is the state
this switch needs and the only state it has; a deposit changes cash, not whether the book is in.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import RaisePrepared
from seer_engine.lab.methods.m0088_calm_big_raisers import CALM, choose
from seer_engine.lab.methods.m0101_calm_raisers_banded_switch import BOOK as CALM_BOOK
from seer_engine.lab.methods.m0101_calm_raisers_banded_switch import FABER_MONTHS
from seer_engine.lab.methods.m0113_trend_switch_reentry import ReentryParams, entry_on
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import factor_rows, trend_on

ADDED = date(2026, 10, 14)
BENCH = "SPY"  # the switch's yardstick, and the symbol whose bars date every monthly check
#: The gate the exit half reads: ("SPY", 200), M0088-C-LIVE-63's own inner gate, untouched.
GATE = CALM_BOOK.ann.base.inner
SMA_N = GATE.trend[1] if GATE.trend is not None else 200  # the 200 in "200-day", frozen
QUARTER = 63  # the interior peak the entry side found on four books
#: The buy-back trigger, M0143-CALM-UP63's verbatim: SPY's last 63 sessions returned positive.
ENTRY = ReentryParams("up", QUARTER)
#: Monthly checks the replay warms up over before the current one. Part of the rule (see above).
WARM = 8
#: Nominal NYSE sessions in a month, used only to bound the replay's slice and the lookback.
CHECK_SESSIONS = 21
#: Every arm's lookback, so the five are scored on identical sessions. 410: see the module
#: docstring and the phase plan for the three constraints it sits inside.
LOOKBACK = max(
    CALM.lookback(CALM_BOOK),
    SMA_N,
    QUARTER + 1,
    23 * (FABER_MONTHS + 1),
    SMA_N + CHECK_SESSIONS * (WARM + 2),
)

Side = Literal["both", "sell"]
_SIDES: tuple[str, ...] = ("both", "sell")
_MAX_LOCK = 12  # a cool-off longer than a year is not a cool-off; it is a different strategy


@dataclass(frozen=True, slots=True)
class TimeLockParams:
    """How long the switch must sit still after it moves, and in which direction that binds.

    ``lock_k = 0`` is M0143-CALM-UP63 exactly: the lock is never consulted and no replay runs.
    ``lock_side = "sell"`` gates only a flip to cash, leaving the buy-back as fast as it is today.
    """

    lock_k: int = 0
    lock_side: Side = "both"

    def __post_init__(self) -> None:
        if isinstance(self.lock_k, bool) or not isinstance(self.lock_k, int):
            raise TypeError(f"lock_k must be an int, got {type(self.lock_k).__name__}")
        if not 0 <= self.lock_k <= _MAX_LOCK:
            raise ValueError(f"lock_k must be in [0, {_MAX_LOCK}], got {self.lock_k}")
        if not isinstance(self.lock_side, str) or self.lock_side not in _SIDES:
            raise ValueError(f"lock_side must be one of {_SIDES}, got {self.lock_side!r}")
        if self.lock_k == 0 and self.lock_side != "both":
            raise ValueError("lock_k=0 is no lock at all; lock_side must stay 'both'")

    def as_dict(self) -> dict[str, str]:
        out = {
            "lock_k": str(self.lock_k),
            "lock_side": self.lock_side,
            "warm": str(WARM),
            "entry": ENTRY.entry,
            "entry_n": str(ENTRY.entry_n),
            "exit_rule": "sma200",
        }
        for k, v in CALM_BOOK.as_dict().items():
            out[f"book.{k}"] = v
        return out


def _check(params: object) -> TimeLockParams:
    if not isinstance(params, TimeLockParams):
        raise TypeError(f"params must be TimeLockParams, got {type(params).__name__}")
    return params


def past_checks(h: History, data_date: date, n: int) -> list[date]:
    """The last ``n`` monthly check dates strictly before ``data_date``, ascending.

    The book engine ranks on the first NYSE session of each calendar month and hands the
    allocator the session before it, so a monthly check's data date is the last session of the
    previous month. ``h`` is SPY, which trades every NYSE session, so bar i is such a session
    exactly when bar i+1 falls in a different month -- no calendar, no clock, and only bars dated
    strictly before ``data_date`` are read. Fewer than ``n`` come back when the history is short;
    an empty list when it holds nothing before ``data_date``.
    """
    if n < 1:
        return []
    j = int(np.searchsorted(h.dates, as_day(data_date), side="left"))
    if j <= 0:
        return []
    hi = min(len(h) - 1, j)
    lo = max(0, j - CHECK_SESSIONS * (n + 2))
    if hi <= lo:
        return []
    seg = h.dates[lo : hi + 1].astype("datetime64[M]")
    ends = lo + np.flatnonzero(seg[:-1] != seg[1:])
    ends = ends[ends < j]
    return [h.dates[int(i)].item() for i in ends[-n:]]


class TimeLockedSwitch:
    """M0143-CALM-UP63's book and switch, with a cool-off between the switch's own flips.

    On data date d: when the book holds anything the EXIT rule decides, and when it holds nothing
    the ENTRY rule decides -- M0143's ``held`` asymmetry, unchanged. The only new behaviour is
    that a decision to CHANGE state can be refused because the switch moved too recently. Off
    means all cash -- no targets at all, which the book engine reads as "sell everything". On
    means the inner book's own targets, unchanged: this allocator never re-ranks, re-weights or
    filters a pick, and owns no signal of its own.
    """

    id = "M0148"
    market_fields = ("dividends",)

    def lookback(self, params: Any) -> int:
        _check(params)
        return LOOKBACK

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return CALM.symbols(CALM_BOOK)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return CALM.holds(CALM_BOOK)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _raw(self, history: Mapping[str, History], data_date: date, in_market: bool) -> bool:
        """The unlocked switch: the 200-day exit while in, the positive-quarter entry while out.

        This is M0143's ``_on`` for ``AsymSwitchParams("calm", "up", 63, "sma200", 0)`` with the
        state passed in rather than read off ``held``, so the two cannot drift apart.
        """
        if in_market:
            return trend_on(history, data_date, GATE)
        return entry_on(history.get(BENCH), data_date, ENTRY)

    def _free(self, want: bool, settled: int, p: TimeLockParams) -> bool:
        """May the switch flip to ``want`` after sitting still for ``settled`` checks?"""
        if p.lock_side == "sell" and want:
            return True  # free to buy back: the cool-off binds only on the way out
        return settled > p.lock_k

    def _settled(self, history: Mapping[str, History], data_date: date,
                 p: TimeLockParams) -> int:
        """Checks the switch has gone without flipping, entering the check at ``data_date``.

        Replays the locked machine over the last ``WARM`` checks, seeded with the stateless gate
        and with the counter seeded "long settled" so an assumed state never holds a flip back.
        Pure: reads only bars dated <= ``data_date``.
        """
        h = history.get(BENCH)
        if h is None:
            return WARM
        checks = past_checks(h, data_date, WARM)
        if not checks:
            return WARM
        state = trend_on(history, checks[0], GATE)
        settled = WARM
        for d in checks[1:]:
            settled += 1
            want = self._raw(history, d, state)
            if want != state and self._free(want, settled, p):
                state, settled = want, 0
        return settled + 1

    def _on(self, history: Mapping[str, History], data_date: date, held: frozenset[str],
            p: TimeLockParams) -> bool:
        """Should the book be held after this check?

        Step for step: M0143's question first, and the lock only when that question's answer is a
        change of state. ``lock_k = 0`` returns before the replay is ever built, which is what
        makes the K0 arm reproduce M0143-CALM-UP63 rather than approximate it.
        """
        now_in = bool(held)
        want = self._raw(history, data_date, now_in)
        if want == now_in:
            return want  # nothing is proposed, so there is nothing for a cool-off to refuse
        if p.lock_k == 0:
            return want  # no lock: this is M0143-CALM-UP63's decision, byte for byte
        if p.lock_side == "sell" and want:
            return want  # the buy-back is never locked on the sell-only arm
        return want if self._settled(history, data_date, p) > p.lock_k else now_in

    def _run(self, prepared: RaisePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: TimeLockParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
            return ()
        if not self._on(prepared.history, data_date, held, p):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, GATE)
        else:
            rows = prepared.factor.rows_on(members, data_date, GATE)
        return choose(prepared.history, rows, prepared.calendar, data_date, held, CALM_BOOK)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar, so no event and no target, for every arm alike."""
        return self._run(RaisePrepared(history, None, EMPTY_DIVIDENDS), members, data_date, held,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> RaisePrepared:
        return CALM.prepare(history)

    def prepare_market(self, market: Any) -> RaisePrepared:
        return CALM.prepare_market(market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, RaisePrepared):
            raise TypeError(f"prepared must be RaisePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


SWITCH = TimeLockedSwitch()


def _v(suffix: str, params: TimeLockParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0148-{suffix}", family="M0148", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SWITCH, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0148",
    name="A cooling-off period on the safety switch: make it stay settled before it may flip again",
    family="stock-dividend-change-drift",
    source_kind="variation",
    source_ref=(
        "variation of M0143 (the calm big raisers behind an asymmetric switch); the switch frame "
        "and both triggers are M0113's; the hysteresis that is being bought is M0101's goal "
        "bought in the time domain instead of the price domain"
    ),
    parent_id="M0143",
    hypothesis=(
        "M0143 answered the exit question and the answer was no, but it answered a second "
        "question nobody asked, and that one has a live lever in it. Every DOWN arm lost in exact "
        "proportion to HOW OFTEN IT CHANGED ITS MIND, not to what it measured. Time invested fell "
        "monotonically with the window: 72.7% (SMA200 exit), 70.7% (DOWN126), 62.1% (DOWN63), "
        "49.2% (DOWN21), and turnover rose monotonically the other way (5.37, 5.20, 5.65, 6.40). "
        "The mechanism is hysteresis: a 200-day average is heavily smoothed so a price above it "
        "tends to stay above it, while a realised-return test flips sign repeatedly in a chop and "
        "each flip is a full liquidation plus a later repurchase. M0084 had already named whipsaw "
        "as the switch's standing cost and M0101's banded arms tried to buy hysteresis by "
        "widening the threshold and LOST (MAR 0.51 and 0.50 against the plain control's 0.57, "
        "both breaking the drawdown screen). DESIGN: buy hysteresis in the TIME domain instead of "
        "the price domain, which is the one way nobody has tried. Keep the exit at the 200-day "
        "cross and the entry at UP63 -- i.e. M0143-CALM-UP63 exactly, a dev-eligible arm at "
        "+11.3% funded against SPY's +7.2% -- and add one new parameter: once the switch has "
        "CHANGED STATE, it may not change again for at least K monthly checks. Variants: K=0 (the "
        "paired control, which must reproduce M0143-CALM-UP63 to the digit), K=1, K=2, K=3, and "
        "one arm applying the cool-off only to the SELL direction (free to buy back, slow to "
        "leave again), because M0143 showed the two halves want opposite things and a symmetric "
        "cool-off may throw away the fast re-entry that four books have now confirmed. "
        "WHY IT COULD WORK WHERE BANDS FAILED: a band widens the threshold, which delays the exit "
        "in a real crash as well as in a chop -- it pays for less whipsaw with a later exit, and "
        "M0101 measured that trade as a loss. A time lock does not move the threshold at all, so "
        "the FIRST exit of a genuine crash arrives on exactly the same session it does today; "
        "only the rapid re-flip is suppressed. That asymmetry is what makes it a different bet "
        "rather than a re-run of M0101. "
        "HOW THE LOCK IS EXPRESSED WITHOUT STATE, which is the one genuinely new piece of "
        "machinery here and is pre-registered with the rest. An allocator holds no state but what "
        "the book holds, and 'how long since the flip' is not in it. It is re-derived from the "
        "bars instead: a monthly check's data date is the last NYSE session of the previous "
        "month, those sessions are readable straight off SPY's own bar dates, and the switch's "
        "transition is a pure function of SPY's closes, so the machine is replayed forward over "
        "the last eight checks and the replay returns a count. The replay NEVER decides what the "
        "book holds -- held stays the authority on the current state, exactly as in M0143, and "
        "this book parks its unfilled weight in SPY so an 'on' book always holds something. The "
        "replay is consulted only on a check where a flip is actually proposed and only when K is "
        "non-zero, so at K=0 it is not reached at all and the control is M0143-CALM-UP63 bit for "
        "bit rather than an approximation of it. The lookback is 410 sessions for every arm, "
        "above M0143's 253 and below the 426 the lab's longest methods already declare; the dev "
        "window still opens 1996-01-03 because this book reads only SPY and the membership "
        "snapshot binds first, so the five arms are scored on exactly the sessions M0143's six "
        "were and the paired differences are the lock alone. "
        "HOST: the same calm big dividend raisers (M0088-C-LIVE-63) for continuity with M0143's "
        "six arms and because its kin reads clean -- family stock-dividend-change-drift holds no "
        "test-failed method and the line M0101 -> M0088 -> M0070 holds none. Same preset, "
        "monthly-hold-frac-gotrade, fractional at Gotrade's real fees on the owner's deposits. "
        "THE PAIR THAT CARRIES THE ASYMMETRY: K3 and K3-SELL share a three-check lock and differ "
        "only in whether the buy-back is locked too, so their difference is exactly the price of "
        "locking the half that four books have now shown wants to be fast. "
        "SUCCESS: a K that beats K=0 by at least a point a year with the worst fall no deeper AND "
        "a positive 2009-2015 edge, since M0143-CALM-UP63's was -0.5% and the chop years 2010, "
        "2011 and 2015 are exactly where M0096 diagnosed the switch losing the money."
    ),
    expected_failure=(
        "The switch already flips rarely under a 200-day average read monthly -- the SPY-only arm "
        "traded 18 times in 22 years -- so a cool-off may bind on almost no sessions and simply "
        "reproduce the control. That is a NULL RESULT and the verdict must report it as one, "
        "stated first and plainly, rather than dressed up as a small improvement: the honest "
        "headline in that case is how many checks the lock actually bound on, and if the answer "
        "is a handful then nothing was learned about hysteresis and the grid closes. "
        "The second risk is the opposite one, and it is worse: the sessions the lock DOES bind on "
        "may be the valuable ones. 2009's recovery was a fast re-entry after a fast exit, and a "
        "lock that forbids a re-flip for three months could hold the book in cash through exactly "
        "the recovery the lab spent three methods learning to catch. If the K arms lose their "
        "money in 2009 rather than gaining it in 2010, 2011 and 2015, the finding is that the "
        "switch's flips are not whipsaw at all but the signal, and the lab should stop looking "
        "for hysteresis on this book. "
        "Third, this book's own evidence is discouraging: it has now refused two exit "
        "improvements, and a third refusal may simply confirm that its switch is already at its "
        "best. "
        "Fourth, the readable numbers. Trade counts on a switch are tiny -- tens of flips over "
        "22 years -- so profit factor and DSR are close to meaningless here and no arm will clear "
        "a luck bar on the strength of them. The funded return, the worst fall, the 2009-2015 era "
        "split and the FLIP COUNT are the numbers to read, in that order, and the verdict says so "
        "before it says anything else. "
        "Fifth, the machinery. If K0 does not return M0143-CALM-UP63's 1996-01-03 start, 575 "
        "trades, 20.39% worst fall and 35.66% CAGR, then either the lookback moved the window or "
        "the decision path is not M0143's, and NONE of the other four numbers is readable; the "
        "correct response is to report the method unreadable rather than to explain the gap away. "
        "Sixth, the warm-up. The replay is defined over the last eight checks and seeded with the "
        "stateless gate, so the first checks of the window are decided by a machine that was "
        "assumed rather than observed. The counter is seeded 'long settled' so an assumed state "
        "never holds a flip back, which bounds the error to permitting a flip the true machine "
        "would have refused -- the conservative direction -- but it is an error and the verdict "
        "does not claim the lock is exact. "
        "Seventh, no interest is credited on idle cash, which flatters whichever arm is out of "
        "the market least. A lock that raises time invested therefore gets a small free "
        "advantage; on SPY a comparable swap moved time in market about 2.3 points and 1996-2015 "
        "T-bills paid roughly 2.5% a year, so any gap under a tenth of a point a year is noise "
        "for this reason alone and must not be reported as a finding."
    ),
    candidates=(
        _v("K0", TimeLockParams(0, "both"),
           "Anchor: no lock at all -- must reproduce M0143-CALM-UP63 to the digit"),
        _v("K1", TimeLockParams(1, "both"),
           "The switch must sit still for one monthly check after it moves"),
        _v("K2", TimeLockParams(2, "both"),
           "Two checks: a flip and its reversal cannot happen inside a quarter"),
        _v("K3", TimeLockParams(3, "both"),
           "Three checks: the longest symmetric cool-off, and the one most exposed to 2009"),
        _v("K3-SELL", TimeLockParams(3, "sell"),
           "The same three-check cool-off on the SELL side only: free to buy back, slow to leave"),
    ),
    seen_keys=(
        "concept:time-locked-trend-switch",
        "concept:switch-cooloff-hysteresis",
        "concept:hysteresis-in-the-time-domain",
    ),
)
