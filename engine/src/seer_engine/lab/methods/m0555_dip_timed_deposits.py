"""M0555 — Dip-timed deposits: put each monthly top-up into SPY on its first close below its own
10-day average, waiting at most 10 sessions.

Source: variation of M0552. M0552 found the two-week over-reaction (FAJ 2025's SMAD signal) priced
into single stocks only before 2009, and a monthly 20-name book's churn left nothing over five
random books. The idea row asks the cheapest remaining use of the same signal: the owner is always
going to end up fully in SPY (that is the account's one real decision), so instead of ranking
stocks by it, apply it to WHEN the owner's own cash goes in. Turnover drops to about one purchase a
month and the fees are SPY's alone, so whatever this costs or earns is not swamped by a 20-name
book's trading.

THE MECHANISM is two new book-engine levers (``sim.rules.TradeRules``), the same shape as M0519's
``add_gate_vix``: a held position is topped up only on a session whose gate is open, new entries
and the idle-cash lever are untouched. ``add_gate_spy_sma`` (a session window) opens the gate on a
session whose PREVIOUS close had SPY below (``add_gate_spy_sma_above=True`` flips it to above) its
own N-session average; ``add_gate_max_wait`` forces the gate open, whatever the other condition
says, once that many sessions have passed since the account's last deposit (the run's starting
capital counts as session 0's "deposit", so the opening buy can be forced too). Both are computed
fresh each session from SPY's own price history and the known contribution calendar
(``backtest.book_runner``), never from a stored flag, so no run-to-run state leaks in.

ONE HONEST IMPRECISION, inherited from how ``add_gate_vix`` already works: the gate only governs
TOPPING UP a position the book already holds (``sim.book.step_book``, the ``p is not None`` branch).
A brand-new entry is never gated, so the very FIRST deposit -- the account's starting capital,
before SPY is held at all -- is invested immediately regardless of the gate. Every deposit after
that is a top-up to an existing SPY position and is gated correctly. This understates the DIP arm's
true wait by exactly one event out of roughly 237 over the dev window, which is why the finding has
to live in the 2009-2015 era and the funded number, not in the first few months of the curve.

THE HOST BOOK is one instrument, SPY, always wanted at full weight -- the allocator carries no dial
at all, because the whole subject of this method is WHEN cash converts into that weight, which the
TradeRules gate controls. Checked daily (``resize_cadence="daily"`` under a monthly rank, M0532's
ADD-DAILY shape) so the gate is read every session, never only on the deposit day; ``resize_band=0``
so any gap clears the band once the gate opens; ``resize_trims=False`` so a holding is never sold
back, matching "buy and hold forever"; fractional shares at Gotrade's real fees.

THE NO-OPINION ARM'S DELAY WAS MEASURED BEFORE ANY RETURN WAS READ, on SPY's own closes and the
owner's contribution calendar alone (a throwaway script against the dev store's bars.csv, no
backtest run). For each of the 237 dev-window deposit dates, the session count (0 = the credit
day itself) until SPY's close first fell below its own 10-day average, capped at 10:

    n = 237, mean wait 2.59 sessions, median 1
    distribution: 0:113  1:22  2:18  3:21  4:6  5:13  6:3  7:5  8:3  9:3  10(forced):30

The gate fires on the credit day itself in 113 of 237 cases and is forced at the 10-session
deadline in 30; the DELAY arm's fixed wait is the rounded mean, 3 sessions, so it isolates the cost
of WAITING from the cost of waiting on a SIGNAL.

FOUR ARMS, Gotrade real fees throughout:
  * DIP (the idea): ``add_gate_spy_sma=10, add_gate_max_wait=10``. Invest the deposit on SPY's
    first close below its own 10-day average, forced in after 10 sessions of no dip.
  * IMMEDIATE (today's habit, the plain baseline): no gate. The deposit is invested the day it is
    credited, same as every un-gated book in this lab.
  * DELAY3 (the no-opinion arm): ``add_gate_max_wait=3`` alone, no price condition. Always waits
    exactly 3 sessions then invests regardless of SPY's price -- the DIP arm's own average wait,
    with the signal removed, so a gap between DELAY3 and IMMEDIATE prices waiting itself and a gap
    between DIP and DELAY3 prices the SIGNAL.
  * MIRROR (the sign check): ``add_gate_spy_sma=10, add_gate_spy_sma_above=True,
    add_gate_max_wait=10``. Invest on SPY's first close ABOVE its own 10-day average instead, same
    10-session deadline. If MIRROR beats DIP, the dip-buying story is dead.

Judge 2009-2015 first: M0552's edge in the same signal was gone by then. The gain here is capped at
a few days' drift on one month's deposit against an account that is otherwise identical across
every arm, so the expectation going in is a fraction of a point a year at best, inside fee and
rounding noise.

Pure. The allocator reads only SPY's close on data_date; the gate levers read only bars and
contribution dates on or before data_date (``backtest.book_runner``).
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, TradeRules
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 11, 12)

SMA_WINDOW = 10
MAX_WAIT = 10
DELAY_SESSIONS = 3  # the DIP arm's own mean wait on the dev window, rounded; see module docstring


@dataclass(frozen=True, slots=True)
class Params:
    """No dial here: the whole subject is the TradeRules gate, read every session, not the book."""

    def as_dict(self) -> dict[str, str]:
        return {}


class SpyAlways:
    """SPY, always wanted at full weight. Every arm's timing difference lives in its TradeRules
    gate (``add_gate_spy_sma``, ``add_gate_max_wait``), never here: this allocator is the same
    function on every arm, so the gate is the only thing that can explain a difference between
    them. Lookback covers the gate's own SMA window plus a buffer, so the book-engine side always
    has enough SPY history once the run starts, even though the allocator itself needs only today's
    close."""

    id = "M0555"

    def lookback(self, params: Any) -> int:
        _check(params)
        return SMA_WINDOW + 2

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return False

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        _check(params)
        t = target_from_close("SPY", last_close(history.get("SPY"), data_date), to_weight(Decimal(1)))
        return () if t is None else (t,)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


def _check(params: object) -> Params:
    if not isinstance(params, Params):
        raise TypeError(f"params must be Params, got {type(params).__name__}")
    return params


ALLOC = SpyAlways()
PARAMS = Params()

# The shared chassis: SPY only, checked daily, add-only (never sell, never trim), fractional
# shares at Gotrade's real fees. M0532's ADD-DAILY shape (monthly rank, daily resize), since the
# basket never changes and only the weight's timing does.
BASE: TradeRules = replace(
    MONTHLY_HOLD_FRAC_GOTRADE,
    id="monthly-rank-daily-addsonly-frac-gotrade-spy",
    resize_cadence="daily",
    resize_band=Decimal("0"),
    resize_trims=False,
)
DIP: TradeRules = replace(
    BASE, id="monthly-rank-daily-addsonly-frac-gotrade-spy-sma10-wait10",
    add_gate_spy_sma=SMA_WINDOW, add_gate_max_wait=MAX_WAIT,
)
DELAY3: TradeRules = replace(
    BASE, id="monthly-rank-daily-addsonly-frac-gotrade-spy-delay3",
    add_gate_max_wait=DELAY_SESSIONS,
)
MIRROR: TradeRules = replace(
    BASE, id="monthly-rank-daily-addsonly-frac-gotrade-spy-sma10-above-wait10",
    add_gate_spy_sma=SMA_WINDOW, add_gate_spy_sma_above=True, add_gate_max_wait=MAX_WAIT,
)


def _v(suffix: str, rules: TradeRules, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0555-{suffix}", family="M0555", rules=rules, allocator=ALLOC, params=PARAMS,
        rationale=rationale, added=ADDED, owner_inputs=(),
    )


METHOD = Method(
    id="M0555",
    name=(
        "Dip-timed deposits: put each monthly top-up into SPY on its first close below its own "
        "10-day average, waiting at most 10 sessions"
    ),
    family="spy-deposit-timing",
    source_kind="variation",
    source_ref=(
        "M0552 (the two-week over-reaction priced into single stocks only before 2009); M0519 "
        "(add_gate_vix, the gate mechanism this reuses); M0532 and M0524 (deposit-timing and "
        "parking-in-SPY on a stock book, the closest recorded deposit-timing measurements)"
    ),
    parent_id="M0552",
    hypothesis=(
        "M0552 found the two-week over-reaction in single stocks only before 2009, and a monthly "
        "20-name book's churn left nothing over random picks. If the over-reaction still exists, "
        "the cheapest place to use it is the owner's own deposit: always fully in SPY, the only "
        "decision is which day each new top-up buys, so turnover is about one purchase a month and "
        "fees are SPY's own. Book: hold SPY; each month's deposit waits in cash until SPY first "
        "closes below its 10-day average, at most 10 sessions, then buys (add_gate_spy_sma=10, "
        "add_gate_max_wait=10 -- two new TradeRules levers, the same shape as M0519's "
        "add_gate_vix). Four arms, Gotrade real fees throughout: DIP (the rule); IMMEDIATE (today's "
        "habit, buy the deposit day it lands, no gate); DELAY3 (the no-opinion arm: always wait a "
        "FIXED 3 sessions with no price condition -- 3 is DIP's own mean wait on the dev window, "
        "rounded, measured on SPY's closes and the deposit calendar alone before any return was "
        "read: n=237, mean 2.59, median 1, distribution 0:113 1:22 2:18 3:21 4:6 5:13 6:3 7:5 8:3 "
        "9:3 10(forced):30); MIRROR (buy on the first close ABOVE the 10-day average instead, same "
        "10-session deadline, the sign check). One honest imprecision: the gate only governs "
        "topping up a position already held, so the account's very first deposit (before SPY is "
        "held at all) is invested immediately on every arm, un-gated; every deposit after that is "
        "gated correctly. Judge 2009-2015 first, since that is where M0552's version of this signal "
        "died. PREDICTIONS, written before any return was read. (1) DIP's funded return sits within "
        "a few tenths of a point of IMMEDIATE's and of DELAY3's, because the cash waits at most a "
        "handful of sessions a month on an account where the deposit is already a small and "
        "shrinking fraction of equity. (2) DIP beats DELAY3 by more than DELAY3 trails IMMEDIATE, "
        "if the signal is real; if DIP and DELAY3 are statistically indistinguishable, waiting (not "
        "the dip) is doing whatever work gets done. (3) MIRROR does not clearly beat DIP; if it "
        "does, the two-week over-reaction has inverted the same way M0552's mirror arm did after "
        "2008. (4) No arm beats total-return SPY by more than a fraction of a point: the lever here "
        "only ever times a few days of one month's deposit, on a book that is otherwise identical "
        "to holding SPY outright."
    ),
    expected_failure=(
        "The four arms read as one curve with noise-sized differences (a fraction of a point a "
        "year, inside the fee and rounding band), because the deposit this lever times is, after "
        "the first few years, a few tenths of a percent of the account (the same math M0119 and "
        "M0532 already found for stock books): there is too little money in play for a few days' "
        "price drift to move the funded number. Or DELAY3 matches IMMEDIATE almost exactly (waiting "
        "a few sessions costs nothing on its own) while DIP and MIRROR also match each other (the "
        "dip/above distinction never acted, because SPY crosses its own 10-day average often enough "
        "-- 113 of 237 deposits in the calibration dipped on the credit day itself -- that the "
        "'forced' 30-of-237 tail is the only place the arms could possibly diverge, and 30 events "
        "over 20 years is too few to read as a pattern. Or the opposite: DIP's forced-at-10 tail "
        "concentrates in falling markets (a dip takes 10 sessions to arrive exactly when SPY keeps "
        "falling past it), so DIP quietly buys MORE of its deposits near local lows than IMMEDIATE "
        "does, and any edge is really 'forced to wait through part of a fall', not 'bought the dip' "
        "-- which the era split and the fold record have to rule out before DIP can be credited with "
        "anything. The single worst case is that the one un-gated opening deposit (the honest "
        "imprecision above) happens to land in a favourable or unfavourable stretch and swings a "
        "twenty-year average by more than the real lever does; the analysis checks this by reading "
        "the era split rather than the whole-window number alone."
    ),
    candidates=(
        _v("DIP", DIP, "THE IDEA: invest the deposit on SPY's first close below its own 10-day average, forced in after 10 sessions"),
        _v("IMMEDIATE", BASE, "Control: today's habit, the deposit is invested the day it is credited, no gate"),
        _v("DELAY3", DELAY3, "No-opinion control: always wait a fixed 3 sessions (DIP's own mean wait) then invest, no price condition"),
        _v("MIRROR", MIRROR, "THE SIGN CHECK: invest on SPY's first close ABOVE its own 10-day average instead, same 10-session deadline"),
    ),
    seen_keys=(
        "concept:spy-deposit-dip-timing",
        "concept:deposit-timing-own-sma-gate",
    ),
)
