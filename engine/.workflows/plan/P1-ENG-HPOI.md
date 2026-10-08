> Adopted from `GOTRADE_FEE_REBUILD_PLAN.md` phase 5. Source: `.workflows/plan/gotrade-fee-rebuild/phase-5.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 5: A contribution schedule, and the lab's real capital

**Plan set:** `GOTRADE_FEE_REBUILD_PLAN.md`
**Analysis:** `20261008-091321-H3M8_code_analyzer.md`
**Satisfies:** R3 — measure what the owner will actually do: 10,000,000 IDR to start, 5,000,000 IDR
more on the 25th of every month. This phase builds the schedule and the lab's half of it; phase 6
gives paper a deposit and phase 7 gives the result an honest return measure.
**Depends on:** Phase 4 (it owns `sim/rules.py`, `sim/sizing.py`, `sim/lifecycle.py` and
`sim/split_adjust.py`, and creates `sim/charges.py` and `sim.rules.is_bracket`). Phase 4 leaves
`backtest/runner.py` **byte-identical** — that file is wholly this phase's.
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/sim`, `engine/src/seer_engine/backtest`

---

## Goal

After this phase the owner's funding plan is a value the system can carry: `5,000,000 IDR on the
25th of each month` is one frozen object, and both backtest runners honour it, crediting each
deposit at the open of the first NYSE session on or after its calendar date so the idle week the
25th really creates is reproduced rather than assumed away. The lab also stops measuring at twice
the owner's money: `INITIAL_IDR` becomes the real `10,000,000`, the same number
`paper.capital.PAPER_INITIAL_IDR` already holds.

Everything here defaults to off. With no schedule passed, every run is byte-identical to today's —
so nothing in this phase can flatter a return on its own. The measure that makes a fed book honest
is phase 7's, and D4 binds 5, 6 and 7 into one unit for exactly that reason.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Creates:**
- `seer_engine.sim.contributions` (new module, `engine/src/seer_engine/sim/contributions.py`)
- `seer_engine.sim.contributions.ContributionSchedule` — frozen, slotted, hashable; fields
  `amount_idr: Decimal`, `day_of_month: int = 25`; methods `dates_in(first, last)`,
  `due(after, through)`, `usd_at(usd_idr)`, `credit_usd(after, through, usd_idr)`
- `seer_engine.sim.contributions.OWNER_MONTHLY` — `ContributionSchedule(Decimal("5000000"), 25)`
- `seer_engine.sim.contributions.MAX_DAY_OF_MONTH` — `28`
- `seer_engine.sim.contributions.Contributions` — the type alias
  `ContributionSchedule | Sequence[tuple[date, Decimal]]`: a funding **plan**, or a **record** of
  deposits already made and already converted
- `seer_engine.sim.contributions.credit_for(contributions, after, session, usd_idr) -> Decimal` —
  the dollars landing at the open of `session`, for either form (**added by the reconciler**, index
  Decision **D18**: phase 12's replay must reproduce the dollars a night wrote, at the rates it
  froze, not recompute them at one rate)
- `engine/tests/test_sim_contributions.py` (new, 11 tests)
- test fixture constants: `test_backtest_runner.SCENARIO_IDR`, `test_book_runner.FIXTURE_IDR`,
  `test_backtest_labels.PARITY_IDR`, each `Decimal("20000000")`

**Signature changes:**
- `backtest.runner.run_backtest(..., *, prepared=None, initial_idr=INITIAL_IDR)` ->
  `(..., *, prepared=None, initial_idr=INITIAL_IDR, contributions: Contributions | None = None)`
- `backtest.book_runner.run_book(..., *, prepared, dividends, initial_idr, usd_idr, kickoff)` ->
  `(..., kickoff=None, contributions: Contributions | None = None)`
- `backtest.book_runner.run_rules(..., *, prepared, dividends, usd_idr, kickoff, initial_idr)` ->
  `(..., initial_idr=INITIAL_IDR, contributions: Contributions | None = None)` (pass-through
  to whichever engine the rules name)

  All three take `Contributions`, not `ContributionSchedule` alone — the plan **or** a record of
  dated, already-converted deposits (D18). Every caller that passes a schedule is unaffected; phase
  12's replay is the only caller that passes a record.
- **(reconciler, 2026-10-08)** `backtest.runner.run_backtest(...)` also gains
  `*, rules: TradeRules = DESIGN_V0`, forwarded to `size_picks` / `step` / `close_unpriced`
  (`runner.py:181`, `:186`, `:197`), and `run_rules` passes it through on the bracket branch. See
  **Step 2b**; this closes phase 4's Handoff H1, which the reconciler assigned here.
- `backtest.runner.RunResult` gains two trailing defaulted fields:
  `contributions: Contributions | None = None`, `cashflows: tuple[tuple[date, Decimal], ...] = ()`
- `backtest.book_runner.BookResult` gains the same two trailing defaulted fields

**Value changes (not a rename, not a deletion):**
- `backtest.runner.INITIAL_IDR`: `Decimal("20000000")` -> `Decimal("10000000")` (`runner.py:46`).
  The symbol stays; every import site keeps working. After this phase
  `backtest.runner.INITIAL_IDR == paper.capital.PAPER_INITIAL_IDR == Decimal("10000000")`.

**Deletes:** none. **Renames:** none.

**Requires (from earlier phases):** Phase 4.

> **Reconciled 2026-10-08 — read this before touching `runner.py`.** The draft of this plan said
> *"phase 4 may update `backtest/runner.py`'s two call sites, so this phase does not touch either
> call line"*. **That is now false, and in the safe direction: phase 4 does not touch
> `backtest/runner.py` at all.** Its own Interface Contract says so explicitly and its exit criterion
> 5 asserts `git diff --stat` shows the file unmodified. `runner.py` is therefore **wholly this
> phase's**, and this phase quotes it exactly as it stands at `485d416`.
>
> The reconciler also moved phase 4's Handoff H1 here: `run_backtest` gains the `rules` keyword and
> **this phase edits `runner.py:181`, `:186` and `:197`** to forward it (Step 2b). Without it
> `paper/replay.py` can only replay a bracket entry at `DESIGN_V0`, so phase 12's Gotrade C
> successor would fail its first `seer paper check` — see Step 2b for the full chain.

What this phase needs from phase 4, and nothing more:

- `sim.size_picks` / `sim.step` / `sim.close_unpriced` take a keyword-only `rules: TradeRules`
  defaulting to `DESIGN_V0` (phase 4's Interface Contract, *Signature changes*);
- `sim.rules.is_bracket(rules) -> bool` exists (phase 4's Step 1);
- `sim.charges.order_fee(side, price, shares, rules)` exists (phase 4's Step 4).

**Leaves alone (owned by others):**
- `engine/src/seer_engine/sim/__init__.py` (Phase 4). `sim.contributions` is **not** re-exported
  there, deliberately: `sim.costs` is not either, and every caller imports it by module path
  (`benchmark.py:37`, `rules.py:33`, `book.py:58`). Following that precedent keeps phase 4's
  `__init__.py` untouched.
- `sim/rules.py`, `sim/model.py`, `sim/sizing.py`, `sim/lifecycle.py`, `sim/split_adjust.py`,
  `paper/bracket.py` (Phase 4)
- `sim/costs.py` (invariant 5 — not modified by anyone)
- everything under `engine/src/seer_engine/paper/` (Phase 6)
- `backtest/metrics.py`, `backtest/benchmark.py`, `backtest/dev.py`, `lab/store.py` (Phase 7)
- `commands/backtest_dev.py` — it reads `INITIAL_IDR` at `:274` for the SPY curve's base cash and
  follows the new value with no edit (measured: no test moves). Phase 7 owns feeding it a schedule.
- `backtest/report.py`, `b_report.py`, `wf_report.py`, `dev_report.py` — their prose interpolates
  `{INITIAL_IDR:,}` and reprints itself. **Source untouched; only their tests' expected string moves.**
- `web/` anything (Phases 9, 10)
- `engine/package_readme.md:1861` and the `sim.costs` / `cost_model` passages at `:1440-1441`,
  `:1746`, `:1763`, `:1851` (Phase 4's readme region)
- `engine/package_readme.md:2963` (paper's init; see Handoffs)

**Scope note, settled by the reconciler.** The index's draft listed 5 files; measured, it is **11**,
and the index now says 11. Moving `INITIAL_IDR` breaks 10 tests in 5 files that the draft index
claimed for nobody. **This phase owns all five** — `test_book_runner.py`, `test_backtest_report.py`,
`test_backtest_b_report.py`, `test_backtest_wf_report.py` and `test_backtest_labels.py` — checked
against every other plan file: no other phase names any of them. In particular
`test_book_runner.py`, which this planner flagged as plausibly phase 4's because it exercises
`DESIGN_V0` parity, is **not** in phase 4's Files table; it stays here, together with its
`FIXTURE_IDR` pins, so the pin and the thing it pins never land in different commits.

## The contract phases 6, 7, 10 and 12 build on

Stated plainly, because four other phases depend on it.

1. **The object.** `ContributionSchedule(amount_idr: Decimal, day_of_month: int = 25)` — frozen,
   slotted, hashable, Decimal-only, denominated in **IDR** because that is the currency the owner's
   money arrives in. `OWNER_MONTHLY` is his plan: 5,000,000 IDR on the 25th.
2. **Calendar dates, never sessions.** The schedule knows nothing about the NYSE. It answers
   `dates_in(first, last)` (inclusive both ends) and `due(after, through)` (strictly after `after`,
   up to and including `through`).
3. **The crediting rule.** A contribution dated `d` is credited at the open of the **first NYSE
   session on or after `d`**. A runner gets that for free by calling `due(previous session, this
   session)` once per session; the first session of a run uses `prev_session(start)` as `after`, so
   a deposit dated on or before the run's data date belongs to the run before this one.
4. **Conversion.** One rate per run — the run's own `usd_idr`, the same rate its starting capital
   was converted at. `usd_at(usd_idr) = q(amount_idr / usd_idr)`, the identical rounding as
   `sim.initial_cash_usd`. Each deposit converts and rounds on its own, so the book receives the sum
   of real deposits, not a rounded multiple. **That is right for a backtest and wrong for a replay**,
   which is why a runner also accepts a **record** — `(session, usd)` pairs already converted at the
   rate of the day each landed — and `credit_for` returns those dollars untouched (D18). Paper
   freezes a deposit's rate on its landing session (phase 6, D6a); a replay that re-converted at one
   rate would move a stepped book's history the first time the rupiah did.
5. **Effect on a book: cash AND equity.** Both rise by the credit. This is not cosmetic — both
   engines size from the last snapshot's equity (`sim/book.py:536` `equity = book.equity`,
   `sim/sizing.py:137` `slot_budget = q(portfolio.equity / SLOTS)`), so crediting cash alone would
   leave the deposit permanently under-deployed.
6. **A deposit is not a return.** Phase 7 owns the measure that says so. This phase only records
   the facts it needs: `RunResult.cashflows` / `BookResult.cashflows` is
   `tuple[tuple[date, Decimal], ...]` in session order — the dated series an IRR consumes — and
   `.contributions` keeps the schedule itself.
7. **The default is `None`,** everywhere. No existing caller changes behaviour. Phases 7, 8 and 12
   switch it on explicitly.
8. **Nothing is persisted or serialized here.** Phase 6 owns the database shape, phase 12 owns
   `roster.spec`. **The spec shape is phase 12's and is strings-only** (`roster.spec` writes strings
   and nulls, because it is hashed into a frozen digest), so it is
   `"funding": {"amount_idr": "5000000", "cadence": "monthly", "day_of_month": "25"}` — note
   `"25"`, the string. `phase-12.md` pins `roster.OWNER_FUNDING` equal to this module's
   `OWNER_MONTHLY` in its own test, so the two cannot drift; this module serializes nothing itself.
9. **For the TypeScript mirror (phase 10).** The same two numbers and the same monthly rule, but a
   different question: the web side asks *how much cash does the owner have today*, and the money is
   in his Gotrade wallet from the **calendar** 25th, open market or not. So phase 10 needs no market
   calendar — it counts `dates_in(first deposit, today)` against the ledger. The two readings never
   disagree, because nothing can happen between sessions anyway.
10. **Capital.** `backtest.runner.INITIAL_IDR == paper.capital.PAPER_INITIAL_IDR ==
    Decimal("10000000")` after this phase. Phase 12's roster entries can state one number.

## Why the capital constant has to move, measured

`paper/capital.py:9-11` justifies the split: *"The backtests keep `backtest.runner.INITIAL_IDR`
(20,000,000 IDR; closed records, where only percentages matter)."* That is true of a flat
percentage fee and false of Gotrade's, whose `$0.10` per-order trading-fee floor makes the rate
depend on the slot. Measured here at 17,841 IDR/USD over 20 names:

| capital | cash | slot | buy fee | sell fee | round trip |
|---|---|---|---|---|---|
| 10,000,000 IDR | $560.5067 | $28.03 | $0.13 | $0.16 | **1.035%** |
| 15,000,000 IDR | $840.7600 | $42.04 | $0.14 | $0.17 | 0.737% |
| 20,000,000 IDR | $1121.0134 | $56.05 | $0.17 | $0.20 | 0.660% |

The command behind it (run from the worktree root):

```
PYTHONPATH=engine/src python - <<'PY'
from decimal import Decimal
from seer_engine.sim.costs import fee_parts
from seer_engine.sim.model import q
FX = Decimal("17841")
for idr in ("10000000", "15000000", "20000000"):
    cash = q(Decimal(idr) / FX); amt = q(cash / 20).quantize(Decimal("0.01"))
    b = fee_parts("buy", amt).total; s = fee_parts("sell", amt).total
    print(f"{int(idr):>11,} IDR  cash ${cash}  slot ${amt}  buy ${b} sell ${s}  round trip {(b+s)/amt*100:.3f}%")
PY
```

So the moment a lab method sets `cost_model="gotrade"`, a 20M lump measures a world 0.375
percentage points a round trip cheaper than the one the owner lives in. Moving `INITIAL_IDR` is a
correctness requirement that arrives with the fee model.

## Why the schedule must deposit on a calendar date

Measured here, reproducing the plan index's table and extending it with the number the simulator
actually reproduces — how many NYSE sessions the money sits idle:

| deposit | day | credited | rotation | gap | idle sessions |
|---|---|---|---|---|---|
| 2026-10-25 | Sun | 2026-10-26 | 2026-11-02 | 8 | 5 |
| 2026-11-25 | Wed | 2026-11-25 | 2026-12-01 | 6 | 3 |
| 2026-12-25 | Fri | 2026-12-28 | 2027-01-04 | 10 | 4 |
| 2027-01-25 | Mon | 2027-01-25 | 2027-02-01 | 7 | 5 |
| 2027-02-25 | Thu | 2027-02-25 | 2027-03-01 | 4 | 2 |
| 2027-03-25 | Thu | 2027-03-25 | 2027-04-01 | 7 | 4 |
| 2027-04-25 | Sun | 2027-04-26 | 2027-05-03 | 8 | 5 |
| 2027-05-25 | Tue | 2027-05-25 | 2027-06-01 | 7 | 4 |
| 2027-06-25 | Fri | 2027-06-25 | 2027-07-01 | 6 | 4 |
| 2027-07-25 | Sun | 2027-07-26 | 2027-08-02 | 8 | 5 |
| 2027-08-25 | Wed | 2027-08-25 | 2027-09-01 | 7 | 5 |
| 2027-09-25 | Sat | 2027-09-27 | 2027-10-01 | 6 | 4 |

Mean 7.0 calendar days, range 4 to 10; mean 4.2 idle sessions, range 2 to 5. The command:

```
PYTHONPATH=engine/src python - <<'PY'
from datetime import date
from seer_engine import dates
for y, m in [(2026,10),(2026,11),(2026,12)] + [(2027,k) for k in range(1,10)]:
    d = date(y, m, 25)
    c = d if dates.is_session(d) else dates.next_session(d)
    ny, nm = (y+1, 1) if m == 12 else (y, m+1)
    f = date(ny, nm, 1); rot = f if dates.is_session(f) else dates.next_session(f)
    idle = len([s for s in dates.sessions(c, rot) if s < rot])
    print(d, d.strftime("%a"), "credited", c, "rotation", rot, "gap", (rot-d).days, "idle", idle)
PY
```

A baked-in seven-day lag is wrong in ten months of twelve, and December's ten days is two and a
half times February's four. A schedule that deposited at the rotation instead would hold about a
week less idle cash every month and so quietly **overstate** returns. Reproducing the idle cash is
the point, not an incidental.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/sim/contributions.py` | create | the schedule as a pure value object |
| `engine/src/seer_engine/backtest/runner.py` | modify | `INITIAL_IDR` -> 10M; `contributions=` on `run_backtest`; credit at the top of the session loop; two new `RunResult` fields; **`rules=` on `run_backtest`, forwarded at `:181`, `:186`, `:197` (Step 2b)** |
| `engine/src/seer_engine/backtest/book_runner.py` | modify | `contributions=` on `run_book` and `run_rules`; credit at the top of the session loop; two new `BookResult` fields; **`is_bracket` dispatch at `:380` and `order_fee` at `:521-522` (Step 2b)** |
| `engine/tests/test_sim_contributions.py` | create | 11 tests for the value object |
| `engine/tests/test_backtest_runner.py` | modify | pin the hand-checked scenario at `SCENARIO_IDR`; re-point the capital assertion; 6 new contribution tests |
| `engine/tests/test_book_runner.py` | modify | pin the seeded and wiring fixtures at `FIXTURE_IDR` (9 call sites + 1 expectation); 2 new contribution tests |
| `engine/tests/test_backtest_labels.py` | modify | pin the labeler/simulator parity fixture at `PARITY_IDR` |
| `engine/tests/test_backtest_report.py` | modify | the Method section now prints `10,000,000 IDR` |
| `engine/tests/test_backtest_b_report.py` | modify | same, one line |
| `engine/tests/test_backtest_wf_report.py` | modify | same, one line |
| `engine/package_readme.md` | modify | the `sim/` tree entry, the `backtest.runner` bullet, the `run_book` signature |

## Implementation Steps

### Step 1: The contribution schedule as a value object
**File:** `engine/src/seer_engine/sim/contributions.py` (new)
**Change:** The whole module. Frozen slotted dataclass, Decimal only, `__post_init__` validation
with specific messages — `sim/costs.py` and `sim/rules.py`'s house style. It imports
`seer_engine.prices` for `PRICE_QUANTUM` and nothing else: no market calendar, no `sim.model`, no
clock, no I/O, no floats. That keeps `tests/test_sim_purity.py` happy and makes phase 10's
TypeScript mirror a transcription rather than a port.
**Code:**
```python
"""The owner's recurring contribution schedule as a value (R3, plan phase 5).

Until now every simulated book was a lump sum that never grew: ``backtest.runner`` converted
``INITIAL_IDR`` once and that was all the money there would ever be. The owner's real plan is
10,000,000 IDR to start and **5,000,000 IDR more on the 25th of every month, indefinitely**
(decided 2026-10-08). This module is that plan as one frozen value.

The schedule names CALENDAR dates, never sessions. The 25th is a date on the owner's bank
statement; whether the NYSE is open that day is the market's business, not the schedule's.
A runner credits a contribution dated ``d`` at the OPEN of the first NYSE session on or after
``d``, which it gets by asking ``due(previous session, this session)`` once per session.

That split is the whole point, and it was measured. The rank sessions are month-start, so a
deposit on the 25th waits for the next rotation before it can be invested:

    deposit      credited     rotation     gap            idle
    2026-10-25   2026-10-26   2026-11-02    8 cal days    5 sessions
    2026-11-25   2026-11-25   2026-12-01    6             3
    2026-12-25   2026-12-28   2027-01-04   10             4
    2027-01-25   2027-01-25   2027-02-01    7             5
    2027-02-25   2027-02-25   2027-03-01    4             2
    2027-03-25   2027-03-25   2027-04-01    7             4
    2027-04-25   2027-04-26   2027-05-03    8             5
    2027-05-25   2027-05-25   2027-06-01    7             4
    2027-06-25   2027-06-25   2027-07-01    6             4
    2027-07-25   2027-07-26   2027-08-02    8             5
    2027-08-25   2027-08-25   2027-09-01    7             5
    2027-09-25   2027-09-27   2027-10-01    6             4

Mean 7.0 calendar days, range 4 (February 2027) to 10 (December 2026); mean 4.2 idle NYSE
sessions, range 2 to 5. A schedule that baked in a fixed seven-day lag would be wrong in ten
months of twelve, and one that deposited at the rotation instead would hold a week less idle
cash every month and so quietly OVERSTATE returns. Reproducing the idle cash is the point.

``day_of_month`` is capped at 28 so a schedule can never silently skip February.

Amounts are in IDR, because that is the currency the owner's money arrives in. A runner converts
with ``usd_at`` at the SAME ``usd_idr`` it converted its starting capital at, so the contributed
dollars and the starting dollars are measured on one rate and the result is about the strategy
rather than about the rupiah.

Pure: no clock, no I/O, no floats, no market calendar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from seer_engine.prices import PRICE_QUANTUM

MAX_DAY_OF_MONTH = 28  # every month has a 28th; 29-31 would skip months


def _date(name: str, x: object) -> date:
    if isinstance(x, datetime) or not isinstance(x, date):
        raise TypeError(f"{name} must be a date, got {type(x).__name__}")
    return x


@dataclass(frozen=True, slots=True)
class ContributionSchedule:
    """``amount_idr`` arriving on ``day_of_month`` of every calendar month, indefinitely."""

    amount_idr: Decimal
    day_of_month: int = 25

    def __post_init__(self) -> None:
        if not isinstance(self.amount_idr, Decimal):
            raise TypeError(f"amount_idr must be a Decimal, got {type(self.amount_idr).__name__}")
        if not self.amount_idr.is_finite() or self.amount_idr <= 0:
            raise ValueError(f"amount_idr must be a finite amount > 0, got {self.amount_idr}")
        if isinstance(self.day_of_month, bool) or not isinstance(self.day_of_month, int):
            raise TypeError(f"day_of_month must be an int, got {type(self.day_of_month).__name__}")
        if not 1 <= self.day_of_month <= MAX_DAY_OF_MONTH:
            raise ValueError(
                f"day_of_month must be 1..{MAX_DAY_OF_MONTH} so no month is skipped, got {self.day_of_month}"
            )

    def dates_in(self, first: date, last: date) -> tuple[date, ...]:
        """Every contribution date in ``[first, last]``, both ends inclusive, ascending."""
        _date("first", first)
        _date("last", last)
        if last < first:
            return ()
        out: list[date] = []
        year, month = first.year, first.month
        while True:
            d = date(year, month, self.day_of_month)
            if d > last:
                break
            if d >= first:
                out.append(d)
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return tuple(out)

    def due(self, after: date, through: date) -> tuple[date, ...]:
        """Every contribution date ``d`` with ``after < d <= through``, ascending.

        This is the per-session question: with ``after`` the previous session and ``through``
        the session being stepped, the answer is every contribution whose first NYSE session on
        or after it is ``through``.
        """
        _date("after", after)
        return self.dates_in(after + timedelta(days=1), through)

    def usd_at(self, usd_idr: Decimal) -> Decimal:
        """One contribution in USD: ``q(amount_idr / usd_idr)``, as ``sim.initial_cash_usd``."""
        if not isinstance(usd_idr, Decimal):
            raise TypeError(f"usd_idr must be a Decimal, got {type(usd_idr).__name__}")
        if not usd_idr.is_finite() or usd_idr <= 0:
            raise ValueError(f"usd_idr must be > 0, got {usd_idr}")
        return (self.amount_idr / usd_idr).quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)

    def credit_usd(self, after: date, through: date, usd_idr: Decimal) -> Decimal:
        """The USD landing on ``through``: one ``usd_at`` per date in ``due(after, through)``.

        Each contribution is converted and rounded on its own, so the cash the book receives is
        the sum of the deposits the owner actually makes, not a rounded multiple.
        """
        one = self.usd_at(usd_idr)
        return one * len(self.due(after, through))


#: The owner's plan, measured from his own words (handover §8 Q3, decided 2026-10-08):
#: 5,000,000 IDR on the 25th of each month on top of a 10,000,000 IDR start.
OWNER_MONTHLY = ContributionSchedule(amount_idr=Decimal("5000000"), day_of_month=25)

#: What a runner will accept as funding: the owner's forward-looking PLAN, or a RECORD of deposits
#: that have already happened -- ``(session, usd)`` pairs, ascending, already landed and already
#: converted. Both answer one question, "how many dollars arrive at the open of this session", and
#: :func:`credit_for` is where they become one answer.
Contributions = ContributionSchedule | Sequence[tuple[date, Decimal]]


def credit_for(
    contributions: Contributions, after: date, session: date, usd_idr: Decimal
) -> Decimal:
    """The dollars credited at the open of ``session``, for a plan or for a record.

    A :class:`ContributionSchedule` is a PLAN: it names calendar dates, and the dollars are
    computed here at ``usd_idr``, this run's single rate. That is right for a backtest, which is
    asking about the strategy and not about the rupiah.

    A sequence of ``(session, usd)`` pairs is a RECORD: the deposits already happened, each was
    already converted at the rate of the day it landed, and those dollars are returned unchanged --
    ``usd_idr`` is not consulted at all. That is right for a REPLAY, which must reproduce the
    dollars a paper night actually wrote. ``paper.store.read_contributions`` is where such a record
    comes from: its ``session_date`` is the key and its ``amount_usd`` the value, each frozen at
    ``usd_idr_on(landing session)`` when the deposit was recorded (phase 6, D6a). Recomputing them
    at one rate would move a stepped book's history the first time the rupiah did, which is the
    one thing a replay may never do.

    ``after`` is the previous session; a record's dates are already landing sessions, so the
    window ``after < d <= session`` selects exactly ``d == session``.
    """
    _date("after", after)
    _date("session", session)
    if isinstance(contributions, ContributionSchedule):
        return contributions.credit_usd(after, session, usd_idr)
    if isinstance(contributions, (str, Mapping)) or not isinstance(contributions, Sequence):
        raise TypeError(
            "contributions must be a ContributionSchedule or a sequence of (date, Decimal) "
            f"pairs, got {type(contributions).__name__}"
        )
    total = Decimal("0.0000")
    previous: date | None = None
    for when, amount in contributions:
        _date("contribution date", when)
        if not isinstance(amount, Decimal):
            raise TypeError(f"contribution amount must be a Decimal, got {type(amount).__name__}")
        if amount <= 0:
            raise ValueError(f"contribution amount must be > 0, got {amount}")
        if previous is not None and when <= previous:
            raise ValueError(f"contributions not strictly ascending at {when}")
        previous = when
        if after < when <= session:
            total += amount
    return total
```
(the module has no `collections.abc` import yet — add `from collections.abc import Mapping, Sequence`
above `from dataclasses import dataclass`. `Sequence` is needed at module level by the
`Contributions` alias as well as inside `credit_for`.)

**Impact:** A new pure module in `sim/`. Nothing imports it yet. `sim/__init__.py` is **not**
touched (phase 4 owns it); callers import by module path, as every caller of `sim.costs` does.

**Why the union exists, settled by the reconciler (index Decision D18).** Phase 12's
`seer paper check` replay has to rebuild the *exact* record a paper night wrote, and phase 6 freezes
each deposit's rate on its landing session (its D6a) while a backtest deliberately uses one rate per
run (contract point 4 above). Those two are both right and they disagree, so a replay that handed a
runner the *plan* would diverge from the stored record the first time the rupiah moved — and
`judge` would report a mismatch on every session after it, which is precisely the failure phase 12's
Step 7d exists to prevent. `credit_for` is the one place the two readings meet. Phase 7's
`buy_and_hold(..., contributions=())` already speaks the dated-pairs half of this union, so all
three runners now take the same second language.

### Step 2: The lab's real capital, and the bracket loop's deposit
**File:** `engine/src/seer_engine/backtest/runner.py` — `:25`, `:45`, `:46`, `:70`, `:137`, `:160`,
`:170`, `:172`, `:214` (line numbers at `485d416`, before phase 4)
**Change:** six disjoint edits. **`runner.py:181` (`size_picks`), `:186` (`step`) and `:197`
(`close_unpriced`) are this phase's too — they are Step 2b, not phase 4's.** The draft of this step
said those three lines belonged to phase 4; the reconciler deleted that instruction, because phase 4
leaves `runner.py` byte-identical (its exit criterion 5). Do Step 2 and Step 2b in one commit: they
touch the same function.

0. `:24` — `from collections import Counter` gains a neighbour:
   `from collections.abc import Mapping, Sequence` (the validation below names both; `book_runner.py`
   already imports them)
1. `:25` — `from dataclasses import dataclass` -> `from dataclasses import dataclass, replace`
2. `:45` (just before `from seer_engine.strategies.base import Strategy`) — add the import
3. `:46` — the constant
4. `:70` (after `rejections: ...`, the last `RunResult` field) — two trailing defaulted fields
5. `:137` (after `initial_idr: Decimal = INITIAL_IDR,`) — the new keyword
6. `:160` — a type check beside the existing validation
7. `:170` / `:172` — the cashflow list and the credit at the top of the session loop
8. `:214` (inside the `RunResult(...)` return) — record both

**Code** (the complete changed regions; everything between them is untouched):
```python
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine import dates
from seer_engine.backtest.market import Market
from seer_engine.sim import (
    Event,
    Order,
    Snapshot,
    close_unpriced,
    initial_cash_usd,
    new_portfolio,
    size_picks,
    step,
)
from seer_engine.sim.contributions import (
    ContributionSchedule,
    Contributions,
    credit_for,
)
from seer_engine.strategies.base import Strategy

#: The owner's real Gotrade capital, the same number ``paper.capital.PAPER_INITIAL_IDR`` holds.
#: It was 20,000,000 while every simulated fee was a flat percentage, where only ratios matter.
#: Gotrade's measured schedule has a $0.10 per-order floor, so the rate depends on the slot:
#: at 17,841 IDR/USD over 20 names a 10M book pays 1.035% round trip and a 20M book 0.660%.
#: Measuring at 20M would price a cheaper world than the owner lives in.
INITIAL_IDR = Decimal("10000000")
```
```python
@dataclass(frozen=True)
class RunResult:
    """One backtest run.

    ``snapshots[0]`` is ``Snapshot(prev_session(start), cash0, cash0)``, then one per session
    (after any forced close). ``events`` is every simulator event in order, forced closes
    included. ``closed`` is every closed order in exit order; ``open_at_end`` the positions
    still open after ``end``. ``rejections`` counts ``size_picks`` rejections by reason,
    sorted by reason.

    ``contributions`` is the schedule the run was funded on, or None (the default, and every
    closed record). ``cashflows`` is ``(session, usd)`` per credited contribution in session
    order -- the dated series a money-weighted return is computed from. A contribution is money
    arriving, never a return: it raises cash and equity on its session and nothing else.
    """

    strategy_id: str
    params: Any
    start: date
    end: date
    usd_idr: Decimal
    initial_cash: Decimal
    snapshots: tuple[Snapshot, ...]
    events: tuple[Event, ...]
    closed: tuple[Order, ...]
    open_at_end: tuple[Order, ...]
    rejections: tuple[tuple[str, int], ...]
    contributions: Contributions | None = None
    cashflows: tuple[tuple[date, Decimal], ...] = ()
```
```python
def run_backtest(
    market: Market,
    strategy: Strategy,
    params: Any,
    start: date,
    end: date,
    *,
    prepared: Any = None,
    initial_idr: Decimal = INITIAL_IDR,
    contributions: Contributions | None = None,
) -> RunResult:
    """Run ``strategy`` with ``params`` on a fresh portfolio over every session in ``[start, end]``.

    ``start`` and ``end`` must be NYSE sessions, ``start <= end``. Starting cash is
    ``initial_cash_usd(initial_idr, market.usd_idr_on(start))``. With ``prepared`` (the value of
    ``allocator.prepare_for(strategy, market)`` -- ``strategy.prepare(market.history)`` unless
    the strategy is ``MarketAware``), picks come from ``strategy.picks_prepared``;
    without it, from ``strategy.picks`` on every history cut at ``data_date``. The strategy
    contract makes both give the same result.

    ``params`` may be a ``ParamsSchedule``: then ``start`` must not be before its first
    segment, and the picks for session S use ``params.at(S)``, keyed by the session being
    traded, not by ``data_date``. Orders keep the bracket they were placed with; the simulator
    never rewrites one. ``RunResult.params`` is the schedule itself. Any other ``params`` value
    is handed to the strategy unchanged for every session.

    ``contributions``: the owner's recurring deposit (``sim.contributions``), or None for a lump
    sum -- the default, so every existing caller and every closed record is unchanged. A
    contribution dated ``d`` is credited at the OPEN of the first session on or after ``d``,
    before that session's sizing, so the money is deployable the moment it lands and sits as idle
    cash until the strategy next buys. It raises cash AND equity (the slot budget is
    ``q(equity / SLOTS)``: crediting cash alone would leave the deposit under-deployed for good).
    It is converted at this run's single ``usd_idr``, the rate the starting capital used.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    _session("start", start)
    _session("end", end)
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    if contributions is not None and (
        isinstance(contributions, (str, Mapping))
        or not isinstance(contributions, (ContributionSchedule, Sequence))
    ):
        raise TypeError(
            "contributions must be a ContributionSchedule, a sequence of (date, Decimal) "
            f"pairs or None, got {type(contributions).__name__}"
        )
    schedule = params if isinstance(params, ParamsSchedule) else None
```
```python
    snapshots: list[Snapshot] = [Snapshot(data_date, pf.cash, pf.equity)]
    events: list[Event] = []
    rejections: Counter[str] = Counter()
    cashflows: list[tuple[date, Decimal]] = []

    for session in dates.sessions(start, end):
        if contributions is not None:
            credit = credit_for(contributions, data_date, session, usd_idr)
            if credit > 0:
                pf = replace(pf, cash=pf.cash + credit, equity=pf.equity + credit)
                cashflows.append((session, credit))
        members = market.membership.members_on(data_date)
```
```python
    return RunResult(
        strategy_id=strategy.id,
        params=params,
        start=start,
        end=end,
        usd_idr=usd_idr,
        initial_cash=cash0,
        snapshots=tuple(snapshots),
        events=tuple(events),
        closed=tuple(e.order for e in events if e.kind == "exit"),
        open_at_end=pf.open_orders(),
        rejections=tuple(sorted(rejections.items())),
        contributions=contributions,
        cashflows=tuple(cashflows),
    )
```
**Impact:** Every default backtest now runs on 10,000,000 IDR. Measured, that breaks 10 tests in 5
files (steps 5-9 fix all of them) and nothing else in the engine suite. `data_date` at the top of
the loop body is the previous session, or `prev_session(start)` on the first pass — exactly the
`after` the crediting rule wants; it is reassigned to `session` only at the bottom of the loop.

### Step 2b: `run_backtest` takes the rule set, so a bracket run can be priced (phase 4's H1)
**Files:** `engine/src/seer_engine/backtest/runner.py` — `:137` (the keyword list), `:181`, `:186`,
`:197`; `engine/src/seer_engine/backtest/book_runner.py` — `:380`, `:521-522`, and `run_rules`'s
bracket branch.
**Change:** assigned here by the reconciler (2026-10-08) from phase 4's Handoff H1 and H2, because
this phase owns both files and depends on phase 4.

**Why it cannot be left out.** `sim.size_picks` / `step` / `close_unpriced` take a `rules` keyword
after phase 4, but `run_backtest` has no way to pass one, so **there is no route from a rule set to
a bracket backtest at Gotrade's fees**. Two things downstream need that route:

- `paper/replay.py:290` hard-codes `run_rules(fixed, strategy, params, DESIGN_V0, …)`. Once phase 12
  creates the Gotrade C successor, `seer paper check` would replay it at the flat rate and report a
  mismatch on every session. (Phase 12 owns `replay.py` under D10 and fixes the call; it needs this
  parameter to exist.)
- `book_runner.run_rules:380` dispatches on `rules.engine == "bracket_v0"`, so a `"bracket"` rule
  set would be sent to the **book** engine and silently measured by the wrong simulator.

Nothing breaks before a Gotrade bracket entry steps a session, and `PAPER_PAUSED` is `'true'` with
zero sessions stepped — but phase 12 lands the entry, so the route has to exist by then.

**Code** — `runner.py`'s import block gains two names (fold into Step 2's import block):

```python
from seer_engine.sim.rules import DESIGN_V0, TradeRules
```

**Code** — `run_backtest`'s keyword list (Step 2 already adds `contributions`; this adds `rules`
after it, so the full tail is):

```python
    *,
    prepared: Any = None,
    initial_idr: Decimal = INITIAL_IDR,
    contributions: Contributions | None = None,
    rules: TradeRules = DESIGN_V0,
) -> RunResult:
```

with one paragraph appended to its docstring:

```
    ``rules`` prices every buy, fill and exit: ``DESIGN_V0`` (the default) is the flat 0.1% a side
    every closed §5 record was run at, ``DESIGN_V0_GOTRADE`` is Gotrade's measured schedule
    including its $0.10 per-order minimum. It is passed straight to ``sim.size_picks``,
    ``sim.step`` and ``sim.close_unpriced``; a book or fractional rule set raises there
    (``sim.charges.bracket_rules``).
```

**Code** — the three call sites, which are the only lines in `runner.py`'s session loop this phase
touches beyond Step 2's credit block:

```python
        sized = size_picks(pf, picks, session, rules=rules)       # runner.py:181
```
```python
        result = step(pf, session, bars, rules=rules)             # runner.py:186
```
```python
    pf, forced = close_unpriced(pf, gone, rules=rules)            # runner.py:197
```

(keep each line's existing arguments exactly as they are at `485d416`; only `, rules=rules` is
added.)

**Code** — `book_runner.run_rules:380`'s dispatch becomes `is_bracket`, so a `"bracket"` rule set
goes to the bracket simulator rather than to the book:

```python
    if is_bracket(rules):
        return run_backtest(
            market, strategy_or_allocator, params, start, end,
            prepared=prepared, initial_idr=initial_idr, contributions=contributions, rules=rules,
        )
```

with `is_bracket` added to `book_runner.py`'s `seer_engine.sim.rules` import. Step 3 writes this same
hunk out in its final form, so there is one version of it and nothing to merge.

**Code** — `book_runner.py:521-522`, phase 4's Handoff H2: a bracket run's cost is priced for the
metrics as `q(price * shares * COST_RATE)`, which understates under `cost_model="gotrade"`. Use the
rule set:

```python
            cost = order_fee(side, price, shares, rules)
```

with `from seer_engine.sim.charges import order_fee` added to `book_runner.py`'s imports. Under
`rules=DESIGN_V0` (every existing caller) `order_fee` is `q(price * shares * rules.cost_rate)` with
`cost_rate == COST_RATE`, so the number is bit-identical and no recorded metric moves — phase 4
measured 0 mismatches over 20,000 random pairs.

**Tests** — add to `engine/tests/test_book_runner.py`, in the block Step 6 opens:

```python
def test_run_rules_sends_a_bracket_rule_set_to_the_bracket_simulator():
    """A `"bracket"` rule set is §5, not a book: it must not be dispatched to step_book."""
    market = seeded_market(39)
    prepared = strategy_prepared(39, "A")
    got = run_rules(
        market, STRATEGY_A, DESIGN_PARAMS, DESIGN_V0_GOTRADE, SEED_START, SEED_END,
        prepared=prepared, initial_idr=FIXTURE_IDR,
    )
    assert isinstance(got, RunResult)  # not a BookResult
    assert got == run_backtest(
        market, STRATEGY_A, DESIGN_PARAMS, SEED_START, SEED_END,
        prepared=prepared, initial_idr=FIXTURE_IDR, rules=DESIGN_V0_GOTRADE,
    )
    # Gotrade is strictly dearer than flat, so the same strategy ends with less.
    assert got.snapshots[-1].equity_usd < sim_run(39, "A").snapshots[-1].equity_usd


def test_the_default_rule_set_leaves_every_closed_record_untouched():
    """`rules` defaults to DESIGN_V0, which is what every caller ran before the lever existed."""
    market = seeded_market(39)
    prepared = strategy_prepared(39, "A")
    assert run_backtest(
        market, STRATEGY_A, DESIGN_PARAMS, SEED_START, SEED_END,
        prepared=prepared, initial_idr=FIXTURE_IDR, rules=DESIGN_V0,
    ) == sim_run(39, "A")
```

**Impact:** `runner.py` grows one keyword and three `rules=rules` arguments; every existing caller is
positional-or-default and unchanged, so the closed A, A2, B and C records stay byte-identical. The
`is_bracket` dispatch is a no-op today — no `"bracket"` rule set reaches `run_rules` until phase 12 —
and `order_fee` is bit-identical under `DESIGN_V0`.

### Step 3: The book loop's deposit, and the dispatch pass-through
**File:** `engine/src/seer_engine/backtest/book_runner.py` — `:62`, `:103`, `:232`, `:259`, `:277`,
`:279`, `:349`, `:365`, `:393-395`, `:409`
**Change:** `from dataclasses import dataclass, replace` is already present at `:40`; only an
import, two dataclass fields, two keywords, one validation line, one loop block, one return block
and two pass-throughs are added.
**Code:**
```python
from seer_engine.sim.book import (
    Book,
    BookSnapshot,
    Fill,
    Position,
    Target,
    Trade,
    close_book_unpriced,
    new_book,
    step_book,
    to_weight,
)
from seer_engine.sim.contributions import (
    ContributionSchedule,
    Contributions,
    credit_for,
)
from seer_engine.sim.model import COST_RATE, initial_cash_usd, q
```
```python
@dataclass(frozen=True)
class BookResult:
    """One book-engine run.

    ``snapshots[0]`` is ``BookSnapshot(prev_session(start), cash0, cash0, 0)``, then one per
    session (after any forced close). ``fills`` is every fill in execution order, forced closes
    included; ``trades`` every closed holding episode in exit order; ``open_at_end`` the
    positions still held after ``end`` (marked, never liquidated). ``dividends_usd`` is the cash
    credited by dividends, ``costs_usd`` the sum of ``Fill.cost_usd``. ``rejections`` counts
    ``step_book`` rejections by reason, sorted by reason.

    ``contributions`` is the schedule the run was funded on, or None (the default, and every
    closed record). ``cashflows`` is ``(session, usd)`` per credited contribution in session
    order -- the dated series a money-weighted return is computed from.
    """

    allocator_id: str
    params: Any
    rules: TradeRules
    start: date
    end: date
    usd_idr: Decimal
    initial_cash: Decimal
    snapshots: tuple[BookSnapshot, ...]
    fills: tuple[Fill, ...]
    trades: tuple[Trade, ...]
    open_at_end: tuple[Position, ...]
    dividends_usd: Decimal
    costs_usd: Decimal
    rejections: tuple[tuple[str, int], ...]
    contributions: Contributions | None = None
    cashflows: tuple[tuple[date, Decimal], ...] = ()
```
`run_book`'s keyword list and validation (the docstring gains one paragraph; the rest of the
docstring is unchanged):
```python
def run_book(
    market: Market,
    allocator: Allocator,
    params: Any,
    rules: TradeRules,
    start: date,
    end: date,
    *,
    prepared: Any = None,
    dividends: DividendMap = _NO_DIVIDENDS,
    initial_idr: Decimal = INITIAL_IDR,
    usd_idr: Decimal | None = None,
    kickoff: date | None = None,
    contributions: Contributions | None = None,
) -> BookResult:
```
```python
    if not isinstance(dividends, Mapping):
        raise TypeError(f"dividends must be a Mapping, got {type(dividends).__name__}")
    if contributions is not None and (
        isinstance(contributions, (str, Mapping))
        or not isinstance(contributions, (ContributionSchedule, Sequence))
    ):
        raise TypeError(
            "contributions must be a ContributionSchedule, a sequence of (date, Decimal) "
            f"pairs or None, got {type(contributions).__name__}"
        )
```
The docstring paragraph to append to `run_book`'s docstring, after the ``kickoff`` paragraph:
```python
    """
    ``contributions``: the owner's recurring deposit (``sim.contributions``), or None for a lump
    sum -- the default, so every closed record is unchanged. A contribution dated ``d`` is
    credited at the OPEN of the first session on or after ``d``, before ``step_book`` sizes
    anything, so a deposit that lands between rotations sits as idle cash until the next rank
    session -- which is the point: the owner's 25th is a mean of 4.2 sessions before a month-start
    rotation. It raises cash AND equity, because ``step_book`` sizes every target from
    ``book.equity``. It is converted at this run's single rate.
    """
```
The loop and the return:
```python
    dividends_usd = _ZERO
    costs_usd = _ZERO
    cashflows: list[tuple[date, Decimal]] = []

    for session in dates.sessions(start, end):
        if contributions is not None:
            credit = credit_for(contributions, data_date, session, rate)
            if credit > 0:
                book = replace(book, cash=book.cash + credit, equity=book.equity + credit)
                cashflows.append((session, credit))
        held = book.held()
```
```python
    return BookResult(
        allocator_id=allocator.id,
        params=params,
        rules=rules,
        start=start,
        end=end,
        usd_idr=rate,
        initial_cash=cash0,
        snapshots=tuple(snapshots),
        fills=tuple(fills),
        trades=tuple(trades),
        open_at_end=book.positions,
        dividends_usd=dividends_usd,
        costs_usd=costs_usd,
        rejections=tuple(sorted(rejections.items())),
        contributions=contributions,
        cashflows=tuple(cashflows),
    )
```
`run_rules` takes the keyword and hands it to whichever engine the rules name. **Its bracket branch
is Step 2b's `is_bracket` dispatch — the final form is written out once, here, so there is no second
version of this hunk to reconcile:**
```python
def run_rules(
    market: Market,
    strategy_or_allocator: Strategy | Allocator,
    params: Any,
    rules: TradeRules,
    start: date,
    end: date,
    *,
    prepared: Any = None,
    dividends: DividendMap = _NO_DIVIDENDS,
    usd_idr: Decimal | None = None,
    kickoff: date | None = None,
    initial_idr: Decimal = INITIAL_IDR,
    contributions: Contributions | None = None,
) -> RunResult | BookResult:
```
```python
    if is_bracket(rules):
        return run_backtest(
            market, strategy_or_allocator, params, start, end,
            prepared=prepared, initial_idr=initial_idr, contributions=contributions, rules=rules,
        )
    if not isinstance(strategy_or_allocator, Allocator):
        raise TypeError(f"rules {rules.id!r} run an Allocator, got {type(strategy_or_allocator).__name__}")
    return run_book(
        market,
        strategy_or_allocator,
        params,
        rules,
        start,
        end,
        prepared=prepared,
        dividends=dividends,
        usd_idr=usd_idr,
        kickoff=kickoff,
        initial_idr=initial_idr,
        contributions=contributions,
    )
```
**Impact:** `rate` (not `usd_idr`) is the resolved rate in `run_book` — it may be overridden by the
caller, and the contributions must follow whatever the starting capital used. `replace` is already
imported at `:40`.

### Step 4: The value object's own tests
**File:** `engine/tests/test_sim_contributions.py` (new)
**Change:** 11 tests. No market, no database, no runner.
**Code:**
```python
"""The owner's contribution schedule (plan phase 5): ``sim.contributions``.

The schedule names calendar dates and nothing else; the runners turn them into sessions. Two
things are checked here and nowhere else: that the dates are the right calendar dates in every
month, including February and across a year end, and that the value object refuses a shape that
would silently skip a month. No market, no database.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from seer_engine.sim.contributions import (
    MAX_DAY_OF_MONTH,
    OWNER_MONTHLY,
    ContributionSchedule,
)


def D(s: str) -> date:
    return date.fromisoformat(s)


def test_the_owner_plan_is_five_million_on_the_twenty_fifth():
    assert OWNER_MONTHLY == ContributionSchedule(amount_idr=Decimal("5000000"), day_of_month=25)
    assert OWNER_MONTHLY.amount_idr == Decimal("5000000")
    assert OWNER_MONTHLY.day_of_month == 25


def test_dates_in_covers_every_month_including_february_and_a_year_end():
    got = OWNER_MONTHLY.dates_in(D("2026-10-01"), D("2027-03-31"))
    assert got == (
        D("2026-10-25"), D("2026-11-25"), D("2026-12-25"),
        D("2027-01-25"), D("2027-02-25"), D("2027-03-25"),
    )


def test_dates_in_is_inclusive_at_both_ends_and_empty_backwards():
    assert OWNER_MONTHLY.dates_in(D("2026-10-25"), D("2026-10-25")) == (D("2026-10-25"),)
    assert OWNER_MONTHLY.dates_in(D("2026-10-26"), D("2026-11-24")) == ()
    assert OWNER_MONTHLY.dates_in(D("2026-11-01"), D("2026-10-01")) == ()


def test_due_is_exclusive_of_after_and_inclusive_of_through():
    # The runner's question: with data_date 2026-10-23 (Fri) and session 2026-10-26 (Mon), the
    # Sunday 25th is due; asked again the following session it is not.
    assert OWNER_MONTHLY.due(D("2026-10-23"), D("2026-10-26")) == (D("2026-10-25"),)
    assert OWNER_MONTHLY.due(D("2026-10-26"), D("2026-10-27")) == ()
    assert OWNER_MONTHLY.due(D("2026-10-25"), D("2026-10-26")) == ()


def test_due_can_carry_more_than_one_month_over_a_long_gap():
    assert OWNER_MONTHLY.due(D("2026-10-01"), D("2026-12-31")) == (
        D("2026-10-25"), D("2026-11-25"), D("2026-12-25")
    )


def test_usd_at_rounds_like_initial_cash_usd():
    from seer_engine.sim.model import initial_cash_usd

    rate = Decimal("17841")  # the rate the fee measurements in the plan index were taken at
    assert OWNER_MONTHLY.usd_at(rate) == Decimal("280.2533")
    assert OWNER_MONTHLY.usd_at(rate) == initial_cash_usd(OWNER_MONTHLY.amount_idr, rate)


def test_credit_usd_is_one_converted_deposit_per_due_date():
    rate = Decimal("16000")
    one = OWNER_MONTHLY.usd_at(rate)
    assert one == Decimal("312.5000")
    assert OWNER_MONTHLY.credit_usd(D("2026-10-23"), D("2026-10-26"), rate) == one
    assert OWNER_MONTHLY.credit_usd(D("2026-10-26"), D("2026-10-27"), rate) == Decimal("0")
    assert OWNER_MONTHLY.credit_usd(D("2026-10-01"), D("2026-12-31"), rate) == one * 3


def test_a_day_of_month_that_would_skip_a_month_is_refused():
    for day in (29, 30, 31):
        with pytest.raises(ValueError, match="no month is skipped"):
            ContributionSchedule(Decimal("5000000"), day)
    assert MAX_DAY_OF_MONTH == 28
    assert ContributionSchedule(Decimal("5000000"), 28).dates_in(D("2027-02-01"), D("2027-02-28")) == (
        D("2027-02-28"),
    )


def test_the_value_object_refuses_a_bad_amount_or_day():
    with pytest.raises(TypeError, match="amount_idr must be a Decimal"):
        ContributionSchedule(5000000, 25)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="amount_idr must be a Decimal"):
        ContributionSchedule(5000000.0, 25)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="amount_idr must be a finite amount > 0"):
        ContributionSchedule(Decimal("0"), 25)
    with pytest.raises(ValueError, match="amount_idr must be a finite amount > 0"):
        ContributionSchedule(Decimal("-5000000"), 25)
    with pytest.raises(TypeError, match="day_of_month must be an int"):
        ContributionSchedule(Decimal("5000000"), True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="no month is skipped"):
        ContributionSchedule(Decimal("5000000"), 0)


def test_dates_and_rates_are_type_checked():
    with pytest.raises(TypeError, match="first must be a date"):
        OWNER_MONTHLY.dates_in(datetime(2026, 10, 1), D("2026-12-31"))
    with pytest.raises(TypeError, match="last must be a date"):
        OWNER_MONTHLY.dates_in(D("2026-10-01"), "2026-12-31")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="after must be a date"):
        OWNER_MONTHLY.due(datetime(2026, 10, 1), D("2026-12-31"))
    with pytest.raises(TypeError, match="usd_idr must be a Decimal"):
        OWNER_MONTHLY.usd_at(16000.0)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="usd_idr must be > 0"):
        OWNER_MONTHLY.usd_at(Decimal("0"))


def test_the_schedule_is_frozen_and_hashable():
    with pytest.raises(Exception):
        OWNER_MONTHLY.amount_idr = Decimal("1")  # type: ignore[misc]
    assert len({OWNER_MONTHLY, ContributionSchedule(Decimal("5000000"), 25)}) == 1
```
**Impact:** 11 new passing tests.

### Step 5: Pin the hand-checked scenario, re-point the capital assertion, test the credit
**File:** `engine/tests/test_backtest_runner.py` — `:39`, `:87`, `:159`, `:302-303`

The hand-checked scenario at `:167-200` is thirty lines of hand-derived arithmetic (share counts,
slot budgets, fills, forced closes) that was computed at 1250.0000 USD. Halving the capital would
require re-deriving every number by hand, which buys nothing: that test is about the **simulator's
arithmetic**, not about the lab's capital. Pin it at its own 20,000,000 and leave the hand-check
intact. The capital claim is made by a test of its own.

**Change 1** — `:39`, after `from seer_engine.sim import Pick, Snapshot`:
```python
from seer_engine.sim.contributions import OWNER_MONTHLY, ContributionSchedule
```
**Change 2** — `:87`, just above `START, END = D("2025-03-04"), D("2025-03-14")`:
```python
# The scenario below is hand-derived at 1250.0000 USD; it checks the simulator's arithmetic, not
# the lab's capital, so it pins its own 20,000,000 IDR rather than following INITIAL_IDR.
SCENARIO_IDR = Decimal("20000000")
```
**Change 3** — `:159`, inside `run_scenario`:
```python
def run_scenario(prepared: bool = False) -> tuple[RunResult, FixedPicks]:
    market = scenario_market()
    strategy = FixedPicks(TABLE)
    prep = strategy.prepare(market.history) if prepared else None
    return run_backtest(market, strategy, None, START, END, prepared=prep, initial_idr=SCENARIO_IDR), strategy
```
**Change 4** — replace `test_initial_idr_default` at `:302-303` with the block below (the new
contribution section goes in the same place, before the `survivorship` divider at `:306`):
```python
def test_initial_idr_is_the_owners_real_capital():
    """10,000,000 IDR, the same number ``paper.capital.PAPER_INITIAL_IDR`` holds.

    It used to be 20,000,000 on the ground that only percentages matter in a closed record.
    That is true of a flat percentage fee and false of Gotrade's, whose $0.10 per-order floor
    makes the rate depend on the slot: measured at 17,841 IDR/USD over 20 names, a 10M book
    pays 1.035% round trip and a 20M book 0.660%. Measuring at 20M would price a cheaper world
    than the owner lives in.
    """
    from seer_engine.paper.capital import PAPER_INITIAL_IDR

    assert INITIAL_IDR == Decimal("10000000")
    assert INITIAL_IDR == PAPER_INITIAL_IDR


# --------------------------------------------------------------------------- contributions


def test_no_schedule_leaves_the_run_exactly_as_it_was():
    market, start, end = smoke_market()
    prepared = STRATEGY_A.prepare(market.history)
    plain = run_backtest(market, STRATEGY_A, DESIGN_PARAMS, start, end, prepared=prepared)
    assert plain.contributions is None
    assert plain.cashflows == ()
    explicit = run_backtest(
        market, STRATEGY_A, DESIGN_PARAMS, start, end, prepared=prepared, contributions=None
    )
    assert explicit == plain


def test_a_contribution_is_credited_on_the_first_session_on_or_after_its_date():
    """The calendar date is the owner's; the NYSE calendar produces the lag.

    The smoke window is 2024-10-17 .. 2025-03-31 and holds six contributions. Four fall on a
    session (2024-10-25 Fri, 2024-11-25 Mon, 2025-02-25 Tue, 2025-03-25 Tue) and are credited
    that day. Two do not and are credited on the next session: 2024-12-25 is Christmas Day, an
    NYSE holiday, so it lands on 12-26; 2025-01-25 is a Saturday, so it lands on Monday 01-27.
    A schedule with a baked-in lag could not produce both the 1-day and the 2-day case.
    """
    market, start, end = smoke_market()
    prepared = STRATEGY_A.prepare(market.history)
    r = run_backtest(
        market, STRATEGY_A, DESIGN_PARAMS, start, end, prepared=prepared, contributions=OWNER_MONTHLY
    )
    assert r.contributions is OWNER_MONTHLY
    want = [
        (d if dates.is_session(d) else dates.next_session(d))
        for d in OWNER_MONTHLY.dates_in(start, end)
    ]
    assert [session for session, _ in r.cashflows] == want
    assert want == [D("2024-10-25"), D("2024-11-25"), D("2024-12-26"),
                    D("2025-01-27"), D("2025-02-25"), D("2025-03-25")]
    one = OWNER_MONTHLY.usd_at(r.usd_idr)
    assert one == P("312.5")
    assert all(amount == one for _, amount in r.cashflows)


def test_a_contribution_raises_cash_and_equity_on_its_session_and_is_not_a_return():
    """The deposit is money arriving, not a gain: cash and equity both rise by exactly it."""
    market, start, end = smoke_market()
    prepared = STRATEGY_A.prepare(market.history)
    plain = run_backtest(market, STRATEGY_A, DESIGN_PARAMS, start, end, prepared=prepared)
    fed = run_backtest(
        market, STRATEGY_A, DESIGN_PARAMS, start, end, prepared=prepared, contributions=OWNER_MONTHLY
    )
    assert fed.initial_cash == plain.initial_cash  # the start is unchanged
    assert fed.snapshots[0] == plain.snapshots[0]
    deposited = sum((amount for _, amount in fed.cashflows), Decimal("0"))
    assert deposited == OWNER_MONTHLY.usd_at(fed.usd_idr) * len(fed.cashflows)
    assert len(fed.cashflows) >= 6
    assert fed.snapshots[-1].equity_usd > plain.snapshots[-1].equity_usd


def test_the_first_sessions_credit_window_opens_after_data_date():
    """A contribution dated on or before ``prev_session(start)`` belongs to the run before this
    one: the first session credits only what is dated strictly after its data date."""
    market, _, _ = smoke_market()
    sessions = dates.sessions(D("2024-01-02"), D("2025-03-31"))
    start = D("2024-10-28")  # data_date 2024-10-25, a Friday session: that deposit is NOT ours
    end = D("2024-11-29")
    assert start in sessions and dates.prev_session(start) == D("2024-10-25")
    r = run_backtest(market, STRATEGY_A, DESIGN_PARAMS, start, end, contributions=OWNER_MONTHLY)
    assert [session for session, _ in r.cashflows] == [D("2024-11-25")]


def test_contributions_must_be_a_schedule():
    market, start, end = smoke_market()
    with pytest.raises(TypeError, match="contributions must be a ContributionSchedule"):
        run_backtest(market, STRATEGY_A, DESIGN_PARAMS, start, end, contributions="monthly")
    with pytest.raises(TypeError, match="contributions must be a ContributionSchedule"):
        run_backtest(market, STRATEGY_A, DESIGN_PARAMS, start, end, contributions=Decimal("5000000"))


def test_a_schedule_with_another_day_and_amount_is_honoured():
    market, start, end = smoke_market()
    tenth = ContributionSchedule(Decimal("1000000"), 10)
    r = run_backtest(market, STRATEGY_A, DESIGN_PARAMS, start, end, contributions=tenth)
    want = [
        (d if dates.is_session(d) else dates.next_session(d)) for d in tenth.dates_in(start, end)
    ]
    assert [session for session, _ in r.cashflows] == want
    assert all(amount == P("62.5") for _, amount in r.cashflows)  # 1,000,000 / 16,000
```
**Impact:** 17 tests -> 23, all passing. `smoke_market()` is defined at `:531` in the same file and
is the only fixture long enough (2024-01-02 .. 2025-03-31) to span a holiday 25th and a weekend 25th.

### Step 6: Pin the book-runner fixtures and test the book credit
**File:** `engine/tests/test_book_runner.py` — `:58`, `:83`, `:176`, `:190`, `:275`, `:277`, `:283`,
`:284`, `:294`, `:298`, `:321`, `:375`, `:376`, `:397`, `:579`, `:588`, and a new block before `:591`

The seeded market's module comment at `:79-82` says why the pin is right: *"Prices span 12 .. 700,
so with 20,000,000 IDR at 16000 (1250 USD, a 312.5 slot) the dear names are rejected
lt_one_share."* The fixture's price ladder is calibrated to that slot. Measured, at 625 USD the
seeded run stops producing a `gap` exit at all and
`test_seeded_market_exercises_every_v0_path[A]` and `[A2]` fail — the fixture would have to be
re-tuned to go on testing what it was built to test.

**Change 1** — `:58`, after `from seer_engine.sim.book import step_book as real_step_book`:
```python
from seer_engine.sim.contributions import OWNER_MONTHLY
```
**Change 2** — `:83`, just above `N_SESSIONS = 380`:
```python
# Both fixtures below are calibrated to a 1250 USD book (a 312.5 slot): the price ladder is what
# makes the dear names reject lt_one_share, and the wiring window's numbers are written out by
# hand. They pin their own 20,000,000 IDR rather than following INITIAL_IDR, which is now the
# owner's real 10,000,000.
FIXTURE_IDR = Decimal("20000000")
N_SESSIONS = 380
```
**Change 3** — nine call sites take `initial_idr=FIXTURE_IDR`:
```python
def sim_run(seed: int, key: str) -> RunResult:
    strategy, params = STRATEGIES[key]
    return run_backtest(
        seeded_market(seed), strategy, params, SEED_START, SEED_END,
        prepared=strategy_prepared(seed, key), initial_idr=FIXTURE_IDR
    )
```
```python
@lru_cache(maxsize=None)
def book_run(seed: int, key: str) -> BookResult:
    strategy, params = STRATEGIES[key]
    return run_book(
        seeded_market(seed),
        PICKS,
        PicksParams(strategy, params),
        V0_BOOK,
        SEED_START,
        SEED_END,
        prepared=picks_prepared(seed),
        initial_idr=FIXTURE_IDR,
    )
```
```python
@pytest.mark.parametrize("key", ["A", "A2", "B"])
def test_run_rules_design_v0_is_run_backtest(key):
    market = seeded_market(39)
    strategy, params = STRATEGIES[key]
    prepared = strategy_prepared(39, key)
    got = run_rules(
        market, strategy, params, DESIGN_V0, SEED_START, SEED_END, prepared=prepared, initial_idr=FIXTURE_IDR
    )
    assert isinstance(got, RunResult)
    assert got == run_backtest(
        market, strategy, params, SEED_START, SEED_END, prepared=prepared, initial_idr=FIXTURE_IDR
    )
    assert got == sim_run(39, key)


def test_run_rules_design_v0_plain_path_is_run_backtest():
    market = seeded_market(39)
    got = run_rules(market, STRATEGY_A, DESIGN_PARAMS, DESIGN_V0, SEED_START, SEED_END, initial_idr=FIXTURE_IDR)
    assert got == run_backtest(market, STRATEGY_A, DESIGN_PARAMS, SEED_START, SEED_END, initial_idr=FIXTURE_IDR)
    assert got == sim_run(39, "A")  # and the prepared path agrees (the Strategy contract)


def test_run_rules_design_v0_ignores_dividends_and_checks_usd_idr():
    market = seeded_market(39)
    prepared = strategy_prepared(39, "A")
    divs = {s: {SEED_DAYS[WARMUP + k]: Decimal("0.5") for k in range(0, 180, 7)} for s in SEED_SYMBOLS}
    got = run_rules(
        market, STRATEGY_A, DESIGN_PARAMS, DESIGN_V0, SEED_START, SEED_END,
        prepared=prepared, dividends=divs, usd_idr=Decimal("16000"), initial_idr=FIXTURE_IDR,
    )
    assert got == sim_run(39, "A")
    with pytest.raises(ValueError, match="usd_idr_on"):
        run_rules(
            market, STRATEGY_A, DESIGN_PARAMS, DESIGN_V0, SEED_START, SEED_END,
            usd_idr=Decimal("15000"), initial_idr=FIXTURE_IDR,
        )
```
```python
    market = scenario_market()
    sim = run_backtest(market, FixedPicks(V0_TABLE), None, V0_START, V0_END, initial_idr=FIXTURE_IDR)
    book = run_book(
        market, PICKS, PicksParams(FixedPicks(V0_TABLE), None), V0_BOOK, V0_START, V0_END, initial_idr=FIXTURE_IDR
    )
```
```python
def test_v0_book_prepared_equals_plain():
    strategy, params = STRATEGIES["A"]
    plain = run_book(
        seeded_market(39), PICKS, PicksParams(strategy, params), V0_BOOK, SEED_START, SEED_END,
        initial_idr=FIXTURE_IDR,
    )
    assert plain == book_run(39, "A")
```
```python
def test_run_book_first_snapshot_and_cash():
    market = wiring_market()
    r = run_book(market, Scripted(), None, DAILY_SWITCH, W_START, W_END, initial_idr=FIXTURE_IDR)
    assert (r.allocator_id, r.params, r.rules, r.start, r.end) == ("SCRIPTED", None, DAILY_SWITCH, W_START, W_END)
    assert (r.usd_idr, r.initial_cash) == (Decimal("16000"), P("1250"))
    assert r.snapshots[0] == BookSnapshot(D("2025-02-21"), P("1250"), P("1250"), P("0"))
    assert [s.date for s in r.snapshots[1:]] == dates.sessions(W_START, W_END)
    assert len(r.snapshots) == 16
    # Nothing targeted: nothing traded, cash flat.
    assert r.fills == () and r.trades == () and r.open_at_end == () and r.rejections == ()
    assert all(s == BookSnapshot(s.date, P("1250"), P("1250"), P("0")) for s in r.snapshots)
    other = run_book(
        market, Scripted(), None, DAILY_SWITCH, W_START, W_END, usd_idr=Decimal("8000"), initial_idr=FIXTURE_IDR
    )
    assert (other.usd_idr, other.initial_cash) == (Decimal("8000"), P("2500"))
    assert other.snapshots[0] == BookSnapshot(D("2025-02-21"), P("2500"), P("2500"), P("0"))
```
**Change 4** — `:321`, in `test_run_rules_book_engine_is_run_book`. That test does **not** pin a
fixture (it is about `run_rules == run_book`, both on the default), so its one expectation follows
the new default: `20,000,000 / 8,000 = 2500` becomes `10,000,000 / 8,000 = 1250`:
```python
    assert got.initial_cash == P("1250")
```
**Change 5** — two new tests, inserted after `test_run_book_first_snapshot_and_cash` and before the
`@pytest.mark.parametrize(("rules", "data_dates"), [` block:
```python
def test_run_book_credits_a_contribution_on_its_session_and_run_rules_passes_it_through():
    """Nothing is targeted here, so the deposit shows as pure cash: the idle money, visible.

    The wiring window is 2025-02-24 .. 2025-03-14 at 16,000 IDR/USD, so the owner's 5,000,000
    IDR is $312.50 and the only contribution in the window is 2025-02-25, a Tuesday session.
    Cash and equity both rise by it on that session and on no other.
    """
    market = wiring_market()
    plain = run_book(market, Scripted(), None, DAILY_SWITCH, W_START, W_END, initial_idr=FIXTURE_IDR)
    assert plain.contributions is None and plain.cashflows == ()
    fed = run_book(
        market, Scripted(), None, DAILY_SWITCH, W_START, W_END,
        initial_idr=FIXTURE_IDR, contributions=OWNER_MONTHLY,
    )
    assert fed.contributions is OWNER_MONTHLY
    assert fed.cashflows == ((D("2025-02-25"), P("312.5")),)
    assert fed.initial_cash == plain.initial_cash == P("1250")
    by_date = {s.date: s for s in fed.snapshots}
    assert by_date[D("2025-02-24")] == BookSnapshot(D("2025-02-24"), P("1250"), P("1250"), P("0"))
    assert by_date[D("2025-02-25")] == BookSnapshot(D("2025-02-25"), P("1562.5"), P("1562.5"), P("0"))
    assert by_date[W_END] == BookSnapshot(W_END, P("1562.5"), P("1562.5"), P("0"))
    # run_rules hands the schedule to whichever engine the rules name.
    assert run_rules(
        market, Scripted(), None, DAILY_SWITCH, W_START, W_END,
        initial_idr=FIXTURE_IDR, contributions=OWNER_MONTHLY,
    ) == fed


def test_run_book_refuses_a_contribution_that_is_not_a_schedule():
    with pytest.raises(TypeError, match="contributions must be a ContributionSchedule"):
        run_book(
            wiring_market(), Scripted(), None, DAILY_SWITCH, W_START, W_END, contributions="monthly"
        )
```
**Impact:** 57 tests -> 59, all passing.

### Step 7: Pin the labeler/simulator parity fixture
**File:** `engine/tests/test_backtest_labels.py` — `:336`, `:434`
**Change:** Measured, halving the capital moves one label by `1.13e-6` against a `1e-6` tolerance
(`S12`, 2024-01-11): a smaller slot rounds a share off and the cash-based return shifts. Pure
rounding noise, no semantic change — but the test is about the labeler agreeing with the simulator,
so pin the fixture rather than loosen the tolerance.
**Code** — after `RUN_SESSIONS = 14 ...` at `:336`:
```python
# The parity check is about the labeler agreeing with the simulator, not about the lab's capital:
# pin the 20,000,000 IDR this fixture's share counts were tuned at (backtest.runner.INITIAL_IDR is
# now the owner's real 10,000,000, which rounds a share off some slots and moves a return by ~1e-6).
PARITY_IDR = Decimal("20000000")
```
and at `:434`:
```python
        run = run_backtest(market, OnePick(d, p), None, s1, stop, prepared=(), initial_idr=PARITY_IDR)
```
**Impact:** 30 tests pass. `Decimal` is already imported at `:20`.

### Step 8: The three report tests print the new number
**Files:** `engine/tests/test_backtest_report.py:228`,
`engine/tests/test_backtest_b_report.py:479`, `engine/tests/test_backtest_wf_report.py:352`
**Change:** `backtest/report.py:232`, `b_report.py:474`, `wf_report.py:452` and `dev_report.py:452`
each interpolate `f"{INITIAL_IDR:,} IDR"` into the Method section. The **source is not touched** —
it reprints itself. Only the expected string moves.
**Code:**
```python
# engine/tests/test_backtest_report.py:228
    assert "10,000,000 IDR" in md
```
```python
# engine/tests/test_backtest_b_report.py:479
    assert "10,000,000 IDR" in md and "Actual/365.25" in md
```
```python
# engine/tests/test_backtest_wf_report.py:352
    assert "10,000,000 IDR" in md and "Actual/365.25" in md
```
**Impact:** `test_backtest_b_report.py:473`'s `assert "$20,000,000" in md` is a **universe market-cap
floor, not capital** — leave it alone (measured: it passes untouched).

### Step 9: The readme states the new capital and the new keyword
**File:** `engine/package_readme.md` — `:82`, `:1424-1425`, `:2146`
**Change:** three edits, all in regions no other phase owns. (The `sim.costs` / `cost_model`
passages at `:1440-1441`, `:1746`, `:1763`, `:1851` and `:1861` are phase 4's; a fuller
`sim.contributions` section near `:1861` is left to the readme-updater pass — see Handoffs.)

**`:82`** — one new line in the `sim/` tree, directly under `costs.py`:
```
      contributions.py      the owner's recurring deposit as a value: ContributionSchedule, OWNER_MONTHLY, MAX_DAY_OF_MONTH, Contributions, credit_for (plan phase 5)
```
**`:1424-1425`** — replace the two lines with:
```
- **`backtest.runner`**: `INITIAL_IDR = Decimal("10000000")` — the owner's real Gotrade capital, the
  same number `paper.capital.PAPER_INITIAL_IDR` holds. It was 20,000,000 while every simulated fee
  was a flat percentage, where only ratios matter; Gotrade's measured schedule has a $0.10
  per-order floor, so the rate depends on the slot (at 17,841 IDR/USD over 20 names a 10M book pays
  1.035% round trip and a 20M book 0.660%) and a 20M lump would price a cheaper world than the owner
  lives in.
  `run_backtest(market, strategy, params, start, end, *, prepared=None, initial_idr=INITIAL_IDR, contributions=None) -> RunResult`
```
and add, after the existing sentence describing `RunResult`'s fields (`:1429-1430`):
```
  `contributions` is a `sim.contributions.Contributions` or None (the default, and every closed
  record) — either the owner's `ContributionSchedule`, whose calendar dates are credited at the open
  of the first NYSE session on or after each of them and converted at this run's single rate, or a
  **record** of `(session, usd)` deposits already made and already converted, which are credited
  unchanged (that is what a paper replay passes, so it reproduces the dollars the night wrote). A
  credit raises cash **and** equity before that session sizes anything, and `RunResult` records what
  it was funded with plus `cashflows` — `(session, usd)` per credited deposit, the dated series a
  money-weighted return is computed from. A deposit is money arriving, never a return.
```
**`:2146`** — the `run_book` signature line:
```
- **`run_book(market, allocator, params, rules, start, end, *, prepared=None, dividends=..., initial_idr=INITIAL_IDR, usd_idr=None, kickoff=None, contributions=None) -> BookResult`**:
```
**Impact:** Documentation of record matches the code. No test reads these lines.

## Verification

**Build:** `PYTHONPATH=engine/src python -c "import seer_engine.backtest.book_runner"`

**Lint:** `cd engine && python -m ruff check src tests` — must print `All checks passed!`

**Tests** (from the worktree root; `PYTHONPATH` is required, or pytest silently tests the main
checkout; never pass `-o addopts`):
```
PYTHONPATH=engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  python -m pytest engine/tests -q -n auto
```
`main` is red for two known reasons (handover §6a, §6b) that phases 1 and 2 fix. **The check that
matters is that this phase adds no new failure.** Capture the failure set before and after:
```
git stash && PYTHONPATH=engine/src PG_TEST_URL=... python -m pytest engine/tests -q -n auto \
  2>&1 | grep -E '^(FAILED|ERROR)' | sort > /tmp/before.txt && git stash pop
PYTHONPATH=engine/src PG_TEST_URL=... python -m pytest engine/tests -q -n auto \
  2>&1 | grep -E '^(FAILED|ERROR)' | sort > /tmp/after.txt
comm -13 /tmp/before.txt /tmp/after.txt      # must print nothing
```
Measured here on a clean copy of the worktree, with every step above applied: `comm -13` printed
nothing, and the focused run
```
python -m pytest engine/tests/test_sim_contributions.py engine/tests/test_backtest_runner.py \
  engine/tests/test_book_runner.py engine/tests/test_backtest_labels.py \
  engine/tests/test_backtest_report.py engine/tests/test_backtest_b_report.py \
  engine/tests/test_backtest_wf_report.py -q -n0
```
is green.

**Manual check:** the deposit really follows the NYSE calendar rather than a baked-in lag —
```
PYTHONPATH=engine/src python - <<'PY'
import sys; sys.path.insert(0, "engine/tests")
from decimal import Decimal
from test_book_runner import seeded_market, strategy_prepared, STRATEGIES, SEED_START, SEED_END
from seer_engine.backtest.runner import run_backtest
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine import dates
s, p = STRATEGIES["A"]
r = run_backtest(seeded_market(39), s, p, SEED_START, SEED_END, prepared=strategy_prepared(39, "A"),
                 initial_idr=Decimal("20000000"), contributions=OWNER_MONTHLY)
for (sess, amt), d in zip(r.cashflows, OWNER_MONTHLY.dates_in(r.start, r.end)):
    first = d if dates.is_session(d) else dates.next_session(d)
    print(f"{d} {d:%a} -> {sess} {'OK' if sess == first else 'MISMATCH'} ${amt}")
PY
```
Measured, this prints nine OK lines over 2019-10-17 .. 2020-07-06, including the three cases a
fixed lag cannot produce: Christmas Day 2019-12-25 lands on 12-26, the Saturdays 2020-01-25 and
2020-04-25 land on the following Monday, and Memorial Day Monday 2020-05-25 lands on 05-26.

**Exit criteria:**
1. `+5,000,000 IDR on the 25th of each month` is one frozen value object, and both `run_backtest`
   and `run_book` honour it — crediting on the **calendar date's first session**, raising cash and
   equity, recording a dated `cashflows` series.
2. `backtest.runner.INITIAL_IDR == paper.capital.PAPER_INITIAL_IDR == Decimal("10000000")`, and a
   test asserts the equality rather than the literal alone.
3. With no schedule passed, every run is identical to today's: `contributions is None`,
   `cashflows == ()`, and the whole engine suite shows no failure it did not already have.
4. `python -m ruff check src tests` is clean.
5. **(Step 2b)** `run_backtest(..., rules=DESIGN_V0_GOTRADE)` runs and ends with strictly less equity
   than the same run at `DESIGN_V0`; `run_rules` sends a `"bracket"` rule set to `run_backtest` and
   not to `step_book`; and with `rules` left at its default every closed record is bit-identical.
6. **(D18)** `contributions=` accepts both forms. Passing `OWNER_MONTHLY` and passing the
   `(session, usd)` pairs that same run produced in `cashflows` give **identical** results — the
   round trip phase 12's replay depends on — and a record's dollars are credited exactly as given,
   never re-converted at the run's rate. Assert it as one test:
   `run(contributions=OWNER_MONTHLY) == run(contributions=run(contributions=OWNER_MONTHLY).cashflows)`.

## Handoffs

Work found and deliberately left where it belongs.

- **The money-weighted return (phase 7, R3).** This phase records the dated cashflows and nothing
  more. Phase 7 reads `RunResult.cashflows` / `BookResult.cashflows` — `tuple[(date, Decimal)]` in
  session order — and turns them into an IRR beside the CAGR, then restates every CAGR-phrased gate.
  Until it lands, a fed book's CAGR is a flattering number; that is D4, and why 5/6/7 ship together.
- **The dollar-cost-averaged SPY (phase 7, R3).** `backtest/benchmark.py`'s `buy_and_hold` /
  `spy_curves` take the **dated** half of this union — `Sequence[tuple[date, Decimal]]`, which is
  exactly `RunResult.cashflows` — so "beats SPY TR" compares two books holding the same money at the
  same times. Phase 7 reads it through `metrics.external_cashflows`; that is already its design, and
  `credit_for` is why the two halves are one vocabulary. `commands/backtest_dev.py:274` builds the SPY curve's
  base cash from `INITIAL_IDR` and now follows the new value automatically, but it will want the
  schedule too.
- **Paper's deposit (phase 6, R3).** `db/migrations/016_contributions.sql`, `paper/store.py`,
  `paper/book.py`. Phase 6 does **not** persist this object: it writes one **dated row per deposit**
  into `paper_contributions` (`amount_idr`, `usd_idr`, `amount_usd`), because a money-weighted
  return integrates dated dollars and a schedule cannot be un-summed. Paper's crediting rule is the
  same one as here — the first NYSE session on or after the calendar date — and its credit raises
  cash **and** equity, as both runners' do. The only place the schedule is serialized at all is
  phase 12's `roster.spec`, in phase 12's strings-only shape (contract point 8).
- **The owner's cash on the web (phase 10, R9).** `web/lib/sean/cash.ts` mirrors the two numbers and
  the monthly rule. It needs **no** NYSE calendar: the money is in the Gotrade wallet from the
  calendar 25th. See contract point 9.
- **The roster entries carrying the schedule (phase 12, R1).** `paper/roster.py`'s successor
  `SEED_ROWS` and `roster.spec`.
- **`engine/package_readme.md:2963`** says paper's first night writes
  `initial_cash_usd(INITIAL_IDR, ...)`, but `commands/paper.py:712` uses `PAPER_INITIAL_IDR`. A
  pre-existing documentation error in paper's section — numerically harmless once both constants are
  10,000,000, but still naming the wrong symbol. **Left to phase 6**, which owns that area.
- **A fuller `sim.contributions` section in the readme's `sim` chapter** (near `:1861`, after the
  `sim/costs.py` purity paragraph). Left to the readme-updater pass, because phase 4 edits that
  region heavily and a collision there costs more than the paragraph is worth.
- **`sim/__init__.py` does not re-export `contributions`.** Deliberate (phase 4 owns the file, and
  `sim.costs` sets the precedent). If a later phase wants the convenience import, it is a one-line
  addition to phase 4's file, not a defect here.

## Rollback

This phase is one commit on `feature/gotrade-fee-rebuild`; `git revert` it. The new module is
unreferenced after the revert and disappears with it; `INITIAL_IDR` returns to `Decimal("20000000")`
and the five test files return to their fixture-free form. Nothing is persisted, no migration runs,
no roster entry is written, and `PAPER_PAUSED` is untouched — so a revert is complete and leaves no
residue.

**But do not revert this phase alone.** Plan index D4 binds 5, 6 and 7 into one unit: contributions
without the money-weighted measure turn every CAGR in the system into a flattering number, which is
strictly worse than having no contributions at all. Revert all three or none. Phase 4 is also
underneath: reverting phase 4 requires reverting 5, 6, 7 and 12 as well.
