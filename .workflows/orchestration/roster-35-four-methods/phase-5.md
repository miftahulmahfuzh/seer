# Phase 5: M0148 — a time-lock on the switch

**Plan set:** `ROSTER_35_FOUR_METHODS_PLAN.md`
**Analysis:** `docs/analyzer/20261014-150738-B7K4_code_analyzer.md`
**Satisfies:** R5 (a time-lock on the safety switch), R6 (the test-window look count stays 4)
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab/methods`

---

## Goal

M0148 stops being an `idea` row and becomes a run method with a written verdict. Five
pre-registered arms ask one question: once the 200-day safety switch has changed state, does
forbidding it to change again for K monthly checks buy back the money M0096 diagnosed it losing in
the 2010, 2011 and 2015 chops? The K=0 arm reproduces `M0143-CALM-UP63` to the digit, so every
other number in the batch is readable or the batch is declared unreadable; and the verdict reports
how often the lock actually bound, because a lock that binds on almost no sessions is a null
result and must be reported as one.

---

## What the idea row already fixes, and is not re-opened

`M0148` is an `idea` row in `lab/lab.sqlite`, created 2026-10-14T06:25:24Z, family
`stock-dividend-change-drift`, `source_kind='variation'`, `parent_id='M0143'`. Its hypothesis is
long and is the specification. Read it before writing anything:

```bash
cp /home/miftah/seer/lab/lab.sqlite /tmp/lab-ro-p5.sqlite
sqlite3 -line /tmp/lab-ro-p5.sqlite \
  "select id,name,family,source_kind,parent_id,status,hypothesis from methods where id='M0148';"
```

(Copy first. Any `lab` command migrates `lab.sqlite` on connect, **even a read** —
`seer-lab-commands-migrate-lab-sqlite-on-connect`. `sqlite3` on a copy touches nothing.)

What the row fixes, and what this plan therefore does not re-derive:

- **The finding being exploited (M0143).** Every DOWN arm lost in proportion to how often it
  changed its mind, not to what it measured. Time invested fell monotonically with the window —
  72.7% (SMA200 exit), 70.7% (DOWN126), 62.1% (DOWN63), 49.2% (DOWN21) — while turnover rose the
  other way (5.37, 5.20, 5.65, 6.40). The mechanism is hysteresis: a 200-day average is heavily
  smoothed, so a price above it tends to stay above it; a realised-return test flips sign
  repeatedly in a chop and every flip is a full liquidation plus a later repurchase.
- **Why this is not a re-run of M0101, which is the whole bet.** M0101's banded arms bought
  hysteresis in the **price** domain by widening the threshold and **lost**: MAR 0.51 and 0.50
  against the plain control's 0.57, both breaking the drawdown screen. A band widens the
  threshold, so it delays the exit of a real crash exactly as much as it delays the exit of a
  chop — it pays for less whipsaw with a later exit, and M0101 measured that trade as a loss. A
  time lock **does not move the threshold at all**: the first exit of a genuine crash arrives on
  exactly the session it arrives on today, and only the rapid re-flip is suppressed. That
  asymmetry is what makes it a different bet, and it is the one domain nobody has tried.
- **The host.** `M0088-C-LIVE-63`, the calm big dividend raisers, same preset
  `monthly-hold-frac-gotrade`, fractional at Gotrade's real fees on the owner's deposits. For
  continuity with M0143's six arms and because its kin reads clean: family
  `stock-dividend-change-drift` holds no test-failed method and the line M0101 → M0088 → M0070
  holds none.
- **What is not re-tested.** The entry window (63 sessions is an interior peak; 21 and 126 are
  both worse, replicated on four books: M0113, M0135, M0133, M0143) and the exit rule (M0143 found
  longer and smoother monotonically better, so the sell side is already optimal). The SPY 200-day
  gate is not a drag to remove — it helped 22 of 22 variants whole-window and every gate-off arm
  was worse on return *and* drawdown at once (`seer-spy-200-day-gate-is-not-a-drag-to-remove`).

### The arm being reproduced, from the committed lab

`M0143-CALM-UP63`, trial `n = 467`:

| field | recorded value |
|---|---|
| `start` | `1996-01-03` |
| `end` | `2015-10-16` |
| `rules_id` | `monthly-hold-frac-gotrade` |
| `trades` | `575` |
| `max_drawdown` | `0.203878693852035` |
| `cagr` | `0.356585884750022` |
| `profit_factor` | `3.5875800969148` |
| `dsr` | `0.941320611624543` |
| `exposure` | `0.727299711190942` |
| `turnover` | `5.3708010584678` |
| `mar` | `0.554541613404695` |
| `eligible` | `1` |
| funded `mwr` | `0.113059219827549` (+11.3%) |
| funded `spy_tr_mwr` | `0.0718802442815947` (+7.2%) |

`M0148-K0` must return every one of these. `start` is the one that catches a lookback mistake, and
`trades` is the one that catches a decision-path mistake.

---

## The one genuinely new mechanical question, and how it is answered

A time lock needs state the allocator does not have. An allocator sees bars, members, the data
date, `held` and its params. It is **pure** — no clock, no I/O, no randomness, reads only bars
dated `<= data_date` — and it must carry no mutable instance state, because one allocator object
is shared across variants and across backtests. M0113 and M0133 express the switch's asymmetry
through `held` alone, and that works because "am I in or out" is exactly what the book knows.
**"How long since the flip" is not in `held`.**

### The four facts the answer is built on

1. **A monthly check's data date is the last NYSE session of the previous calendar month.**
   `book_runner.run_book` opens with `data_date = dates.prev_session(start)` and ends every
   session with `data_date = session`, so at the top of session `s` the allocator is handed
   `prev_session(s)`. It is called when `is_rank_session(rules, s)` is true, and
   `sim.rules._first_of("monthly", s)` is true exactly when `s` is the first NYSE session of its
   calendar month. So the check data dates are the month-end sessions, plus one kickoff at
   `prev_session(window start)`.
2. **Those boundaries are readable off SPY's own bar dates, with no calendar import.** SPY trades
   every NYSE session, so bar `i` of SPY's history is a month-end session exactly when bar `i+1`
   falls in a different month. The reconstruction is a numpy comparison over
   `h.dates.astype("datetime64[M]")` and reads only bars dated `<= data_date`.
3. **The switch's own transition is a pure two-line function of SPY's closes.** With the exit held
   at the 200-day cross and the entry at UP63, the next state is
   `trend_on(d)` when the machine is in and `entry_on(up, 63)(d)` when it is out — M0143's `_on`
   with the state passed in instead of read off `held`. Replaying it forward over a bounded run of
   past check dates is therefore pure, deterministic and reproducible.
4. **`held` remains the authority on the current state, and `park=True` makes it reliable.**
   `M0088-C-LIVE-63` parks the unfilled weight in SPY (`RaiseParams.park=True`), so an "on" book
   holds SPY even in a month with no live raiser. M0143's `CALM-SYM` anchor reproducing
   M0101-CTRL's 528 trades is the measured evidence that `bool(held)` and the switch's true state
   do not part on this book.

### The design, and why it is this one

> **The replay never makes the decision. It only answers "how long has the switch sat still?",
> and it is consulted only on a check where a flip is actually proposed and K > 0.**

On data date `d`:

1. `now_in = bool(held)` — the current state, exactly as M0143 reads it.
2. `want = raw(now_in, d)` — the exit rule when in, the entry rule when out. Byte for byte
   M0143-CALM-UP63's question.
3. If `want == now_in`, return it. No flip is proposed, so the lock is irrelevant and is not
   computed.
4. If `p.lock_k == 0`, return `want`. **K=0 is not "the replay with K=0"; K=0 never reaches the
   replay at all.** This is what makes the K0 arm bit-for-bit M0143-CALM-UP63.
5. On the sell-only arm, if `want` is True (a buy-back), return it. The cool-off gates only the
   exit.
6. Otherwise replay the machine over the last `WARM` past checks to get `settled`, the number of
   checks the switch has gone without flipping entering `d`, and allow the flip only when
   `settled > p.lock_k`.

**Why the replay is used only for the counter.** A seeded replay can diverge from the book's true
trajectory on the first checks after its seed. If the replay drove the *decision*, a seed error
would change what the book holds. Driving only the *counter* means a seed error can at worst
delay or permit one flip near the warm-up edge — it cannot make the book's state disagree with
`held`, and it cannot touch the K0 arm at all.

**Why a fixed-length warm-up and not a replay from the window's first session.** The alternative —
replay from the first bar in the history — is also pure, but it makes the result depend on how far
back the store happens to reach, which differs between `engine/.research` and the
survivorship-check store, and it would be re-run from scratch on every one of ~237 checks. A fixed
`WARM` is bounded, declarable in `lookback`, identical on every store, and is a *definition of the
rule* rather than an approximation of some platonic machine: "the switch, warmed up over the last
eight monthly checks". The docstring says exactly that, so no later reader mistakes it for a bug.

**The seed.** The state at the warm-up anchor is seeded with the stateless 200-day gate,
`trend_on(anchor)`, and the counter is seeded at `WARM` — "long settled", so the lock never binds
on a state the replay merely assumed. The machine then self-synchronises: at any check where
`trend_on` and `entry_on(up,63)` agree, the next state is the same whatever the previous state
was, and historically the two agree in the large majority of months.

### Rejected alternatives, and why

| Alternative | Why not |
|---|---|
| Add a `lock_k` field to `ReentryParams` (m0113) or to `AsymSwitchParams` (m0143) | Moves every recorded `config_digest` that names those dataclasses — `seer-shared-params-cannot-gain-a-field`. Both files are frozen against their recorded shas. The new state is wrapped in **this** file behind the new allocator id `M0148`. |
| Keep the counter on the allocator instance | Not pure. One allocator object is shared across the five variants inside a single `run_registry` call and across backtests; mutable state would leak between arms and the P4 identity check would fail. |
| Infer the past state backwards from `held` and the raw triggers | Ambiguous exactly when it matters: when `trend_on(d)` and `entry_on(d)` agree, both possible previous states produce the observed outcome, so the flip cannot be dated. |
| Count calendar months from a stored flip date | There is nothing to store. The allocator is handed no state but `held`. |
| Replay from the first bar of the history | Pure, but store-dependent, undeclarable in `lookback`, and quadratic in the number of checks. |

### The lookback arithmetic, measured not estimated

The replay slices at most `CHECK_SESSIONS * (WARM + 2)` bars back to find `WARM` month ends, and
the earliest of those needs `SMA_N` bars behind it for `trend_on`. So

    LOOKBACK = max(CALM.lookback(CALM_BOOK), SMA_N, QUARTER + 1, 23 * (FABER_MONTHS + 1),
                   SMA_N + CHECK_SESSIONS * (WARM + 2))
             = max(253, 200, 64, 253, 200 + 21 * 10)
             = 410

Three constraints, all checked against the tree rather than guessed:

- **The smoke fixture's hard cap.** `tests/labkit.py:20` — `SMOKE_FIRST = date(2013, 12, 2)`,
  "473 NYSE sessions through DEV_END". Measured on the fixture, a lookback of 410 leaves the smoke
  candidate window opening 2015-07-21 with **63 sessions** to run, so
  `test_candidate_runs_a_smoke_window`'s `len(result.snapshots) >= 2` holds with room. 431 would
  leave 42 and 452 only 21. The largest lookback any method in the lab declares today is **426**
  (`M0128-W-NOSTOP-CASH`, `M0053-RESON20-TV16`, `M0022-W-TV16`, …), so 410 is inside proven
  territory and no frozen feature window is shrunk (`seer-lab-method-lookback-capped-by-smoke-fixture`).
- **The dev window must not move, or K0 cannot reproduce.** `dev.candidate_window` starts at the
  first session whose data date gives every symbol the candidate reads its full lookback, and —
  because `uses_members` is True — not before `MEMBERSHIP_START = 1996-01-02`. The only symbol
  this method reads is SPY, and the dev store holds **739 SPY bars on or before 1996-01-02**
  (`awk -F, '$1=="SPY" && $2<="1996-01-02"' engine/.research/bars.csv | wc -l`). 410 < 739, so
  `ready` stays at `MEMBERSHIP_START` and the window still opens **1996-01-03**, exactly as
  M0143's did. All five arms share the lookback, so the paired differences are exact.
- **`WARM` is a module constant, not a params field.** `_canon` digests a dataclass by its
  `fields`, so `WARM` and `CHECK_SESSIONS` are recorded by the file's `source_sha`, not by the
  config digest. That is deliberate: they are not knobs being swept, and putting them in the
  digest would invite a later batch to sweep them.

---

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates:**
- `seer_engine.lab.methods.m0148_switch_time_lock` (new file) exporting
  `METHOD`, `SWITCH` (allocator id `"M0148"`), `TimeLockedSwitch`, `TimeLockParams`,
  `past_checks`, `GATE`, `ENTRY`, `WARM`, `CHECK_SESSIONS`, `LOOKBACK`, `QUARTER`, `BENCH`,
  `SMA_N`
- `engine/tests/test_m0148_switch_time_lock.py` (new file)
- five `trials` rows (`M0148-K0`, `M0148-K1`, `M0148-K2`, `M0148-K3`, `M0148-K3-SELL`) plus their
  `trial_moments`, `trial_funding`, `trial_provenance`; `methods.M0148` moves
  `idea` → `registered` → (`dev-eligible` | `rejected`); one `insights` row
- regenerated `web/data/lab.json`

**Signature changes:** none
**Requires (from earlier phases):** nothing. This phase depends on no other phase.
**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/methods/m0143_quarter_return_exit.py` and
  `m0113_trend_switch_reentry.py` — frozen against their recorded shas; imported, never edited.
- `m0088_calm_big_raisers.py`, `m0101_calm_raisers_banded_switch.py`, `m0070_*`, `m0076_*` —
  imported, never edited.
- `engine/src/seer_engine/lab/methods/m0155_*.py` (Phase 3), `m0149_*.py` (Phase 4),
  `m0156_*.py` (Phase 1).
- `engine/src/seer_engine/paper/roster.py`, `db/migrations/` (Phase 2).
- `docs/lab/survivorship/grid.csv` — never appended to, by anyone.
- `engine/src/seer_engine/backtest/registry.py`.

**Allocator id claimed:** `"M0148"`. Unique across the lab —
`test_allocator_ids_are_unique_across_methods` enforces it. Phases 3 and 4 claim `"M0155"` and
`"M0149"`.
**`seen_keys` claimed:** `concept:time-locked-trend-switch`,
`concept:switch-cooloff-hysteresis`, `concept:hysteresis-in-the-time-domain`. All three are about
a market switch's *timing*; phases 3 and 4 are brakes on stock books and must not reuse them.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/methods/m0148_switch_time_lock.py` | create | the whole method: `TimeLockParams`, `past_checks`, the `TimeLockedSwitch` allocator, five candidates, `METHOD` |
| `engine/tests/test_m0148_switch_time_lock.py` | create | the lock's logic, which the shared contract test cannot reach: K=0 is M0143's decision verbatim, the lock pins, the sell-only arm lets a buy-back through, the check dates are month ends |
| `lab/lab.sqlite` | append | written by `lab run M0148`, `lab note`, `lab insight` |
| `web/data/lab.json` | regenerate | written and git-added by `lab stage` |

---

## Implementation Steps

### Step 1: Write the method file

**File:** `engine/src/seer_engine/lab/methods/m0148_switch_time_lock.py` (new, whole file)
**Change:** the complete method. Nothing else in the tree is touched.
**Code:**

```python
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
```

**Impact:** adds one method file. Nothing else in the tree changes, so nothing else can break.
`test_lab_methods.py` picks it up automatically through `discover()` and gives it the purity
check, the allocator-contract check, the smoke-window run and the allocator-id uniqueness check
for free.

---

### Step 2: Write the method's own test module

**File:** `engine/tests/test_m0148_switch_time_lock.py` (new, whole file)
**Change:** cover what the shared contract test cannot reach. `test_lab_methods.py` drives only
the history-only path of a market-aware allocator, where M0148 targets nothing by contract, so
the lock itself has no coverage there without this file.
**Code:**

```python
"""M0148's time lock, which the shared contract test cannot reach.

``tests/test_lab_methods.py`` drives a market-aware allocator's history-only path, where M0148
targets nothing by contract, so the three things that make this method what it is -- that K=0 is
M0143's decision verbatim, that a non-zero K actually pins the switch, and that the sell-only arm
leaves the buy-back free -- have no coverage there. They have it here, on a hand-built SPY
history whose shape is chosen so the unlocked switch whipsaws.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from seer_engine.lab.methods.m0143_quarter_return_exit import SWITCH as M0143_SWITCH
from seer_engine.lab.methods.m0143_quarter_return_exit import AsymSwitchParams
from seer_engine.lab.methods.m0148_switch_time_lock import (
    BENCH,
    SWITCH,
    TimeLockParams,
    TimeLockedSwitch,
    past_checks,
)
from seer_engine.strategies.base import History

from seer_engine import dates

FIRST = date(2010, 1, 4)
LAST = date(2015, 10, 16)
SESSIONS = dates.sessions(FIRST, LAST)


def _history(close: np.ndarray) -> History:
    d = np.array([np.datetime64(s, "D") for s in SESSIONS], dtype="datetime64[D]")
    c = np.asarray(close, dtype=np.float64)
    return History(BENCH, d, c.copy(), c.copy(), c.copy(), c.copy(), np.ones(len(d)))


def _chop(period: int = 150, amplitude: float = 0.22) -> History:
    """A sine wave slow enough to cross its own 200-day average again and again."""
    i = np.arange(len(SESSIONS), dtype=np.float64)
    return _history(100.0 * (1.0 + amplitude * np.sin(2.0 * np.pi * i / period)))


def _checks(h: History) -> list[date]:
    """Every monthly check date this history carries, ascending."""
    return past_checks(h, SESSIONS[-1], 10_000)


def _trajectory(h: History, params: TimeLockParams) -> list[bool]:
    """The switch's state after each monthly check, driven through ``held`` as the book does."""
    history = {BENCH: h}
    state = False
    out: list[bool] = []
    for d in _checks(h):
        held = frozenset({BENCH}) if state else frozenset()
        state = SWITCH._on(history, d, held, params)
        out.append(state)
    return out


def _flips(states: list[bool]) -> int:
    return sum(1 for a, b in zip(states, states[1:]) if a != b)


def test_past_checks_returns_month_end_sessions_ascending():
    h = _chop()
    got = past_checks(h, date(2015, 6, 1), 4)
    assert got == [date(2015, 2, 27), date(2015, 3, 31), date(2015, 4, 30), date(2015, 5, 29)]
    assert all(dates.next_session(d).month != d.month for d in got)


def test_past_checks_is_strictly_before_the_data_date():
    h = _chop()
    assert date(2015, 5, 29) not in past_checks(h, date(2015, 5, 29), 4)
    assert past_checks(h, SESSIONS[0], 4) == []


def test_k0_asks_exactly_the_question_m0143_asks():
    """The K0 arm must be M0143-CALM-UP63's decision, not an approximation of it."""
    h = _chop()
    history = {BENCH: h}
    mine = TimeLockParams(0, "both")
    theirs = AsymSwitchParams("calm", "up", 63, "sma200", 0)
    seen = 0
    for d in _checks(h):
        for held in (frozenset(), frozenset({BENCH})):
            assert SWITCH._on(history, d, held, mine) is M0143_SWITCH._on(history, d, held, theirs)
            seen += 1
    assert seen > 0


class _NoReplay(TimeLockedSwitch):
    """The switch with its replay booby-trapped: reaching it at all is the failure."""

    def _settled(self, history, data_date, p):  # noqa: D102
        raise AssertionError("K=0 must decide without the replay")


def test_k0_never_consults_the_replay():
    """``_settled`` is not reached at K=0, which is what makes the reproduction exact."""
    h = _chop()
    history = {BENCH: h}
    switch = _NoReplay()
    for d in _checks(h):
        switch._on(history, d, frozenset(), TimeLockParams(0, "both"))
        switch._on(history, d, frozenset({BENCH}), TimeLockParams(0, "both"))


def test_a_longer_lock_flips_fewer_times_in_a_chop():
    h = _chop()
    counts = [_flips(_trajectory(h, TimeLockParams(k, "both"))) for k in (0, 1, 2, 3)]
    assert counts[0] > 0, "the fixture must whipsaw, or it proves nothing"
    assert counts[0] >= counts[1] >= counts[2] >= counts[3]
    assert counts[3] < counts[0], "a three-check lock must actually bind on this fixture"


def test_the_sell_only_arm_buys_back_inside_its_own_cool_off():
    """K3 locks both directions; K3-SELL must re-enter at least as often as K3 does."""
    h = _chop()
    both = _trajectory(h, TimeLockParams(3, "both"))
    sell = _trajectory(h, TimeLockParams(3, "sell"))
    entries_both = sum(1 for a, b in zip(both, both[1:]) if not a and b)
    entries_sell = sum(1 for a, b in zip(sell, sell[1:]) if not a and b)
    assert entries_sell >= entries_both
    assert sell != both, "on a whipsawing fixture the two arms must part somewhere"


def test_the_replay_reads_no_bar_after_the_data_date():
    h = _chop()
    d = date(2015, 5, 29)
    full = SWITCH._settled({BENCH: h}, d, TimeLockParams(3, "both"))
    cut = SWITCH._settled({BENCH: h.upto(d)}, d, TimeLockParams(3, "both"))
    assert full == cut
```

**Impact:** new test module only. If `test_a_longer_lock_flips_fewer_times_in_a_chop` cannot be
made to bind on the sine fixture, tune `period`/`amplitude` until the K=0 arm flips at least four
times — a fixture on which the lock never binds proves nothing, and the assertion says so.

---

### Step 3: Commit and push the method file — the pre-registration

**File:** none (git)
**Change:** the commit *is* the pre-registration. `lab/prereg.registry_problem` refuses an
uncommitted or dirty method file, and the runner refuses a `config_digest` the `trials` table
already holds. The file is never written or edited after a result is seen.

Take the lab write lock first — this opens the hold that runs through Step 7's push. The lock's
exact commands are in Step 7 and in the plan index's invariant 7. Phases 1, 3 and 4 also write
`lab/lab.sqlite`, and **`lab run` is inside the hold**, so the four lab phases' runs queue rather
than overlap. The hold starts here — not at Step 4 — only because the pre-registration commit and
push take seconds and it is simpler to open the window once; what matters is that nothing writes
`lab/lab.sqlite` outside it, and that it is not released until Step 7's push leaves
`lab/lab.sqlite` and `web/data/lab.json` identical to `HEAD`.

```bash
cd /home/miftah/seer

# open the hold (full protocol and preconditions: Step 7, and the plan index's invariant 7)
exec 9>/home/miftah/seer/.git/seer-lab.lock
flock -w 21600 9 || { echo "lab lock still held after 6h -- find out who has it; do NOT force"; exit 1; }
echo "phase-5 pid $$ $(date -Is)" >&9
git fetch origin && git merge --ff-only origin/main
git diff --quiet HEAD -- lab/lab.sqlite web/data/lab.json || { echo "pair dirty, nobody held the lock -- STOP"; exit 1; }

# green before anything is committed
engine/.venv/bin/ruff check engine
engine/.venv/bin/pytest engine/tests -q

# commit by explicit pathspec; never `git add -A` (seer-swarm-shared-worktree)
git add engine/src/seer_engine/lab/methods/m0148_switch_time_lock.py \
        engine/tests/test_m0148_switch_time_lock.py
git commit -m "lab: M0148 pre-registered — a cooling-off period on the safety switch

Hold M0143-CALM-UP63's book and switch exactly, and add one parameter: once the switch
has changed state it may not change again for K monthly checks. K=0 is the paired
control and reproduces M0143-CALM-UP63 to the digit; K=1, 2 and 3 lock both directions;
K3-SELL locks only the way out, leaving the buy-back as fast as four books have now
shown it wants to be.

This is not M0101 again. A band widens the threshold and so delays the exit of a real
crash as much as the exit of a chop, and M0101 measured that trade as a loss. A time
lock does not move the threshold, so the first exit of a collapse arrives on the same
session it does today and only the rapid re-flip is suppressed.

The lock needs state an allocator does not have. It is re-derived from the bars: a
monthly check's data date is the last session of the previous month, those sessions are
readable off SPY's own bar dates, and the switch's transition is a pure function of
SPY's closes, so the machine is replayed over the last eight checks. The replay only
counts; held still decides. At K=0 it is never reached.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

**Impact:** the file is frozen from here. A later edit makes `lab run` refuse it and makes
`test_lab_methods.py` red once the method has a recorded sha.

---

### Step 4: Run the method on the dev window

**File:** none (CLI)
**Change:** five dev trials recorded under `M0148`.

```bash
cd /home/miftah/seer
engine/.venv/bin/python -m seer_engine lab status | head -20        # test looks must read 4
engine/.venv/bin/python -m seer_engine lab run M0148 --store engine/.research \
  2>&1 | tee /tmp/m0148-run.log
engine/.venv/bin/python -m seer_engine lab status | head -20        # still 4
```

`--store engine/.research` is the dev store, named explicitly. **Never** `engine/.research-test`,
and **never** `lab test` — R6.

The run is long (the calm-raisers panel over 1996-2015, five arms). Run it in the background and
let it finish; a quiet `lab run` shell is not a stall.

**Impact:** `lab/lab.sqlite` grows by five `trials` rows and their moments/funding/provenance;
`methods.M0148.source_sha` is written once; the lab's N moves by one **method**, retroactively, on
every published verdict. That cost is known and accepted by the plan index.

---

### Step 5: Check the anchor before reading anything else

**File:** none (read-only query against a copy)
**Change:** none. This is the gate on every other number in the batch.

```bash
cd /home/miftah/seer
cp lab/lab.sqlite /tmp/lab-ro-p5-after.sqlite
sqlite3 -line /tmp/lab-ro-p5-after.sqlite "
  select candidate_id, start, end, trades, max_drawdown, cagr, profit_factor,
         exposure, turnover, dsr, eligible
    from trials where method_id='M0148' order by n;"
sqlite3 -line /tmp/lab-ro-p5-after.sqlite "
  select t.candidate_id, f.mwr, f.spy_tr_mwr
    from trials t join trial_funding f on f.trial_n = t.n
   where t.method_id='M0148' order by t.n;"
```

`M0148-K0` must read, exactly:

| field | required |
|---|---|
| `start` | `1996-01-03` |
| `trades` | `575` |
| `max_drawdown` | `0.203878693852035` |
| `cagr` | `0.356585884750022` |
| `profit_factor` | `3.5875800969148` |
| `exposure` | `0.727299711190942` |
| `turnover` | `5.3708010584678` |
| `mwr` | `0.113059219827549` |

**If `start` is not `1996-01-03`**, the lookback moved the window: the arms are not scored on
M0143's sessions and nothing in the batch is comparable to anything. **If `trades` is not 575**,
the decision path is not M0143's. Either way the honest response is to record the method as
unreadable in the verdict and stop — not to explain the gap away. `seer-old-trial-returns-are-not-reproducible`
does not apply here: that note is about comparing a re-run to a *recorded* row across a cost-model
change, and K0 is the same preset, the same store and the same window as trial `n = 467`.

**Impact:** none to the tree. Read-only; the copy is what is queried, so `lab.sqlite` is not
migrated.

---

### Step 6: Measure how often the lock actually bound

**File:** none (read-only)
**Change:** none. This is the number the phase's exit criteria name, and it decides whether the
result is a finding or a null.

The flip count is not a stored column, so read it off the recorded curves and the trade counts:

```bash
cd /home/miftah/seer
engine/.venv/bin/python -m seer_engine lab show M0148
engine/.venv/bin/python -m seer_engine lab exposure M0148     # time invested, per arm
engine/.venv/bin/python -m seer_engine lab regime M0148       # the chop years against the rest
engine/.venv/bin/python -m seer_engine lab kin M0148          # per the lab's standing practice
```

Three readings, in this order:

1. **Did the lock bind at all?** Compare each K arm's `turnover` and `exposure` against K0's
   (5.3708010584678 and 0.727299711190942). Identical to the digit means the lock never bound on
   a single check and the arm is a byte-for-byte re-run of the control — a **null result**, which
   the verdict reports as one, first, in plain language.
2. **Where did it bind?** `lab regime` splits by market breadth; the 2009-2015 era split is what
   M0096's diagnosis predicts and is what the idea's success criterion names. A gain that is not
   present in 2009-2015 is a pre-2009 artefact and the verdict says so before it says anything
   else.
3. **What did it cost in 2009?** The expected-failure's second risk. If the K arms lose money in
   2009 rather than gaining it in 2010, 2011 and 2015, the finding is that the switch's flips are
   signal and not whipsaw.

`lab kin` is read per the lab's practice, and with
`seer-behavioural-kin-reports-only-the-best-twin` in mind: `behavioural_kin` reports one twin per
*failed method*, not per variant, so a clean headline does not clear every arm. The host's line
(M0101 → M0088 → M0070, family `stock-dividend-change-drift`) holds no test-failed method, so this
is a confirmation rather than a gate.

**Impact:** none to the tree. `lab show`, `lab exposure`, `lab regime` and `lab kin` are report-only
and record no trial and no look — but they are `lab` commands and so migrate `lab.sqlite` on
connect. Hash before and restore by path if it moved:

```bash
sha256sum lab/lab.sqlite > /tmp/m0148-lab.sha   # before the report commands
sha256sum -c /tmp/m0148-lab.sha || git checkout -- lab/lab.sqlite   # after, if nothing was run
```

(Do **not** restore after `lab run` — that is the run's own output.)

---

### Step 7: Write the verdict, stage, commit, push

**File:** `lab/lab.sqlite`, `web/data/lab.json`
**Change:** the analysis and verdict, then the web snapshot.

The verdict is plain language for the owner: no ids, no digests, no code (plan invariant 10). It
says, in this order: whether the control reproduced; how often the lock bound; what it cost or
bought in 2009-2015; and the answer to the question the idea asked.

```bash
cd /home/miftah/seer
cat > /tmp/m0148-note.md <<'EOF'
<the analysis: the anchor check first, then the flip counts, then the era split>
EOF
engine/.venv/bin/python -m seer_engine lab note M0148 --file /tmp/m0148-note.md \
  --verdict "<one or two plain sentences the owner can read>"

engine/.venv/bin/python -m seer_engine lab insight \
  --text "<the one thing worth remembering, in plain language>"
```

This closes the lock-hold opened at Step 4, before `lab run M0148`. The draft said only the
stage-and-commit was serialised; reconciliation widened it — a run leaves the shared binary
`lab/lab.sqlite` dirty for its whole duration, and while it is dirty no other session can commit
a snapshot matching the committed database, and another phase's `lab stage` would sweep this
run's half-finished rows into its commit. The four lab runs queue.

#### The lab write lock — one mechanism, defined, identical in every phase of this set

Reconciled 2026-10-14. Every phase plan and the plan index carry these exact commands. Earlier
drafts said "take the write lock" without ever defining one; `lab stage`'s own `BEGIN EXCLUSIVE`
(`commands/lab.py:2824`) covers only `write_snapshot` + `git add` and is released before the
commit, so it is **not** the lock meant here.

```bash
LAB_LOCK=/home/miftah/seer/.git/seer-lab.lock   # inside .git/: no `git add` can ever reach it

# TAKE IT. fd 9 is the handle; the kernel drops it when this shell exits, even on a crash.
exec 9>"$LAB_LOCK"
flock -w 21600 9 || { echo "lab lock still held after 6h -- find out who has it; do NOT force"; exit 1; }
echo "phase-N pid $$ $(date -Is)" >&9        # who holds it, for a human who opens the file

# PROVE THE PAIR IS CLEAN. When nobody holds the lock this must pass. If it fails, a session
# died inside its window and the tree is in an unknown state -- STOP and report, do not repair.
cd /home/miftah/seer
git fetch origin && git merge --ff-only origin/main
git diff --quiet HEAD -- lab/lab.sqlite web/data/lab.json || {
  echo "the lab pair is dirty and nobody held the lock -- STOP"; flock -u 9; exit 1; }

#   ... the critical section ...

# RELEASE.
flock -u 9
```

**The rule, in one line: you may not release the lock with `lab/lab.sqlite` or
`web/data/lab.json` differing from `HEAD`.**

**What is inside a hold.** Every command that writes a lab row — `lab survivorship` (it journals
an `observation`), `lab run`, `lab note`, `lab insight`, `lab seen`, `lab reevaluate` — plus the
`lab stage` (or, for phase 2, `lab export-json`), `git commit` and `git push` that return the pair
to clean. **`lab run` is inside the hold**, which means the four lab phases' runs queue rather
than overlap. That reverses the draft index's "the runs may overlap", and the reason is
build-green: a run leaves the shared binary `lab/lab.sqlite` dirty for its whole duration, and
while it is dirty (a) no other session can export a snapshot that matches the committed database,
so phase 2's `web/data/lab.json` commit cannot be made correct, and (b) any other phase's
`lab stage` would `git add` the half-finished run's rows into its own commit, because `lab stage`
stages the whole file. Two independent measurements agree: `lab run`s contend on one sqlite file
(phase 1 Step 5), and each run loads a whole research store at ~1 GB
(`seer-research-store-memory-budget`), so four at once is RAM pressure on a 16 GB machine. The
cost is honest and accepted: the four lab runs are serial, and the set takes as long as their sum.

**Take short holds, not one long one.** A hold that spans writing a method file starves every
other session for nothing. Each phase's plan names its own hold boundaries below; where a phase
has two or three DB-writing windows separated by file-writing work, it takes two or three holds,
each ending with a stage, a commit and a push.

**What the lock buys:** when no session holds it,
`git diff --quiet HEAD -- lab/lab.sqlite web/data/lab.json` is true. That is the only condition
under which an exported snapshot matches the database committed beside it — which is exactly what
`engine/tests/test_lab_snapshot.py:1054
test_the_committed_snapshot_is_the_export_of_the_committed_database` byte-compares, and CI runs it.

Inside that hold:

```bash
cd /home/miftah/seer
engine/.venv/bin/python -m seer_engine lab stage
# `lab stage` writes web/data/lab.json and git-adds it WITH lab/lab.sqlite, through the index.
# A bare commit: `git commit -- <paths>` re-reads the working tree and defeats the staging
# (seer-lab-stage-commit-needs-the-index).
git commit -m "lab: M0148 — <the plain verdict, no backticks>

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

**If the push is rejected:** do **not** `git pull --rebase`. It replays a stale `lab.sqlite` over
whatever the other phases wrote (`seer-rebase-replays-stale-lab-sqlite`). Instead:

```bash
git fetch origin
git log --oneline HEAD..origin/main -- lab/ web/data/lab.json   # must be empty
git reset --mixed HEAD~1        # keep the working tree, including the live lab.sqlite
git merge --ff-only origin/main
engine/.venv/bin/python -m seer_engine lab stage
git commit -m "lab: M0148 — <the plain verdict>

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

Never `git reset --hard`. Sessions share this one checkout and one index.

**Impact:** `lab.sqlite` and `web/data/lab.json` must agree row for row; CI checks it. They are
the only two paths in that commit.

---

### The two shared artifacts, and the rules that govern them

#### `web/data/lab.json` — one generator, one commit shape, one recovery

Reconciled 2026-10-14, settling a contradiction between the index's old phase-2 boundary and
phase 2's own measurement. The whole rule, binding on all five phases:

1. **It is never hand-edited, and never `git checkout --`'d back.** It is generated output. The
   only correct copy is the export of the `lab/lab.sqlite` committed beside it.
2. **Lab phases (1, 3, 4, 5) regenerate it with `lab stage`**, which `git add`s it *together with*
   `lab/lab.sqlite`, and commit the pair with a bare `git commit -m …` and nothing else in that
   commit (`seer-lab-stage-commit-needs-the-index`).
3. **Phase 2 regenerates it with `lab export-json` and commits it ALONE by pathspec.**
   `export-json` writes the same bytes to the same path and never touches the git index
   (`commands/lab.py:_export_json` vs `_stage`); `lab stage` would `git add lab/lab.sqlite` too,
   and phase 2 writes no lab row, so staging it would sweep another phase's in-flight trials into
   phase 2's commit. `commands/lab.py:1757-1761` names `export-json` for exactly this situation.
4. **Phase 2 must regenerate it — "phase 2 does not touch the lab's artifacts" cannot hold and is
   withdrawn.** `lab/store.py:2966-2977` builds the snapshot's `paper` block from
   `roster.LAB_PROVENANCE` filtered by `roster.active()`. Retiring `RAW-FR-GT` changes the
   snapshot's bytes (measured: the `paper` array loses one element), and
   `engine/tests/test_lab_snapshot.py:1054` byte-compares the committed file against a live
   export. CI runs that test.
5. **Either generator runs inside the lab write lock**, and the holder has already proved
   `git diff --quiet HEAD -- lab/lab.sqlite`. So the snapshot committed is always the export of
   the database committed.
6. **Finding it ahead of your own commit is normal, not an error.** Another phase landed trials
   after you took your reading. Do not revert it and do not hand-merge it: bring `HEAD` forward
   with `git fetch origin && git merge --ff-only origin/main` — **never `git pull --rebase`**,
   which replays a stale `lab.sqlite` over what the other phases wrote
   (`seer-rebase-replays-stale-lab-sqlite`) — then re-run your generator and commit what comes
   out. If `git diff` is then empty, the other phase's commit already carries your change: commit
   nothing and say so in the close-out. **Whoever lands last is right, and that is by design** —
   the snapshot is a pure function of the database and the roster, so the last regeneration over
   the merged state is the only one that can be correct.

---

### Post-set step: `lab reevaluate` — owned by the last lab phase to land

Reconciled 2026-10-14. Phase 5's draft handed this off to "whoever closes the plan set"; nobody
was "whoever", so it is assigned here by a rule that picks out exactly one session and needs no
coordinator.

All four lab phases move the lab's N by one **method** each, retroactively, on every published
verdict (`seer-lab-n-policy-overcounts-looks`). N rising makes the luck bar harder, never easier,
so nothing can be wrongly loosened by waiting — but `lab reevaluate` is the command that re-judges
every `rejected` method against the bars in force now, and running it once after the fourth run
lands is what keeps the published lab honest. **Once, after all four — not four times.**

**You are the last if, immediately after your own push, all four ids have left `idea`:**

```bash
cd /home/miftah/seer
engine/.venv/bin/python - <<'PY'
import sqlite3
c = sqlite3.connect("file:lab/lab.sqlite?mode=ro", uri=True)   # ro: cannot migrate or dirty it
c.row_factory = sqlite3.Row
rows = {r["id"]: r["status"] for r in c.execute(
    "SELECT id, status FROM methods WHERE id IN ('M0148','M0149','M0155','M0156')")}
print(rows)
print("I AM LAST" if len(rows) == 4 and all(s != "idea" for s in rows.values())
      else "not last -- another lab phase still owes a run")
PY
```

A phase that decides **not** to run its method records that with
`lab drop <id> --reason "<plain reason>"`, which moves the row off `idea`. That is what keeps this
check total: an id can never sit at `idea` forever and leave the set with no last phase.

**If you are last, run it inside the same lock hold** — `lab reevaluate` writes (it can take the
one edge `rejected -> dev-eligible`, `commands/lab.py:1699`) and the whole sweep is one
transaction:

```bash
engine/.venv/bin/python -m seer_engine lab reevaluate

# only if it printed a non-zero "N method(s) moved"; otherwise commit nothing
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab stage
git commit -m "lab: re-judged every rejected method at the new luck bar

Four questions were asked this week, so the bar's multiple-testing count moved by four and
every recorded verdict is read against it. Nothing was re-run and no new measurement was
taken: this is the lab re-reading what it already holds.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push origin main
```

`lab reevaluate` loads no research store, runs no backtest, inserts no trial and cannot reach the
test window — **the look count stays 4**, and it prints the count it found. If it prints
`0 method(s) moved`, that is a result: commit nothing and say so in the close-out.

**If you are not last, do nothing** — and name in your close-out which of the four ids were still
`idea`, so the next phase to finish can see it is becoming the last.

---

## Verification

**Build (lint):**

```bash
cd /home/miftah/seer && engine/.venv/bin/ruff check engine
```

**Tests:**

```bash
cd /home/miftah/seer
docker start seer-pg 2>/dev/null || docker run -d --name seer-pg \
  -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
engine/.venv/bin/pytest engine/tests
```

DB tests must not skip — CI fails if they do. The checks that matter for this phase and run
automatically once the file exists:

| test | what it proves for M0148 |
|---|---|
| `test_method_source_is_pure[M0148]` | no clock, no randomness, no I/O, no forbidden import or attribute |
| `test_allocator_contract[M0148-*]` | valid targets, the P4 identity, no look-ahead; and, being market-aware, that it targets nothing with no panel |
| `test_candidate_runs_a_smoke_window[M0148-*]` | all five arms run to `DEV_END` on the 473-bar fixture at a 410-session lookback |
| `test_allocator_ids_are_unique_across_methods` | `"M0148"` collides with no other method, including phases 3 and 4 |
| `test_every_recorded_configuration_still_digests_to_its_recorded_digest` | nothing this file imports moved a frozen digest in M0070, M0076, M0088, M0101, M0113 or M0143 |
| `test_m0148_switch_time_lock.py` (new) | K=0 is M0143's decision verbatim and never reaches the replay; a longer lock flips fewer times; the sell-only arm re-enters freely; the replay reads no bar after the data date |

**Manual check, in order:**

1. `lab status` reads **4** test looks before the run and **4** after. R6.
2. `M0148-K0`'s recorded row matches trial `n = 467` on `start`, `trades`, `max_drawdown`, `cagr`,
   `profit_factor`, `exposure`, `turnover` and funded `mwr`. The table in Step 5 is the
   comparison.
3. `git status` shows no modified file under `engine/.research*`, `docs/lab/survivorship/`, or any
   other phase's paths.
4. `docs/lab/survivorship/grid.csv` is unchanged (`git diff --stat -- docs/lab/survivorship/`
   empty). Never appended to.
5. `lab.sqlite` and `web/data/lab.json` were committed together, by `lab stage` plus a bare
   `git commit -m`.

**Exit criteria:**

- `M0148-K0` reproduces `M0143-CALM-UP63` on every column listed above **or** the method is
  recorded as unreadable and the verdict says so as its first sentence.
- The verdict states, in plain language, **how often the lock actually bound** — and if the answer
  is "almost never", it is reported as a null result rather than dressed up as a finding.
- Five trials are recorded under `M0148`, the method's status has moved off `idea`, and a verdict
  is written.
- `lab status` reads 4 test looks.
- `ruff check engine` and `pytest engine/tests` are green; `lab.sqlite` and `web/data/lab.json`
  agree row for row.

---

## Handoffs

Work this phase found and is deliberately leaving alone.

- **The survivorship-check read of M0148 (no requirement id; not R5).** The time lock's whole
  premise is about whipsaw cost, which is a turnover story and is visible on the dev store. The
  honest-tape read would be a separate `lab survivorship M0148` call, which records no trial and
  no look. It is **not** done here: R5 is the method's dev run and verdict, and plan invariant 9
  ("both stores or it does not count") binds claims about **width and single-name falls**, which
  this phase makes none of. Note for whoever picks it up: SPY's history on `engine/.research-sv`
  may not reach 739 bars before 1996-01-02, in which case a 410-session lookback could move the
  check-store window and the paired comparison would need its own control. Measure that before
  running it.
- **Sweeping `WARM`.** The warm-up length is a module constant, recorded by the file's source sha
  and not by any config digest, precisely so it is not swept inside this method. If the batch
  shows the lock binding on real sessions and the counter's accuracy starts to matter, that is an
  `Amendment` to M0148 — pre-registered by its own commit, recorded under the same id, and
  costing the lab no extra N.
- **A time lock on any other host.** The clean-kin host menu is small
  (`seer-kin-clean-host-menu-is-small`); M0088's line is one of the few that reads clean end to
  end. Porting the lock to `M0133-N40` (R4's book) would be a different method and belongs to
  nobody yet. Phase 4 owns M0149 and must not grow it.
- **The 35-name roster width (R1).** Phase 2's. This phase touches no roster file.
- **`lab reevaluate` after the four runs land — no longer a handoff; it is owned.** Reconciliation
  2026-10-14 assigned it to whichever of phases 1, 3, 4 and 5 lands last, decided by a check this
  phase runs on itself after its own push. See *Post-set step: `lab reevaluate`* above. If that
  check says this phase is last, running it is part of this phase, not a chore left for somebody.

---

## Rollback

This phase appends to an append-only database, so "rolling back" means writing a further note,
never editing a row.

- **The trials cannot be undone.** `trials_no_update` and `trials_no_delete` triggers refuse it,
  and `methods_no_delete` refuses the method row. That is the point of the lab: a question asked
  is a question counted. If the batch turns out to have been a mistake, the correction is a second
  `lab note` appended to the analysis (`methods_analysis_grows` allows growth, never rewriting).
- **The method file** can be reverted with `git revert <pre-registration sha>` — but only if
  `lab run M0148` has **not** happened. Once it has, `methods.source_sha` pins the file and
  `test_lab_methods.py` goes red the moment the file no longer hashes to it. After the run, the
  file is frozen and stays.
- **The test module** is freely revertable at any time: `git revert` or
  `git rm engine/tests/test_m0148_switch_time_lock.py`. It is new, nothing imports it, and no
  other test depends on it.
- **`web/data/lab.json`** is regenerated from `lab.sqlite` by `lab stage`; it is never hand-edited
  and never rolled back on its own, because CI checks the two agree row for row.
- **Nothing outside `engine/src/seer_engine/lab/methods/`, `engine/tests/`, `lab/lab.sqlite` and
  `web/data/lab.json` is touched**, so no other phase's work can be caught in a revert of this one.
