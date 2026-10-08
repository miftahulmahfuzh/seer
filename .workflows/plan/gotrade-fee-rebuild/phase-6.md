# Phase 6: Paper accepts a deposit

**Plan set:** `GOTRADE_FEE_REBUILD_PLAN.md`
**Analysis:** `20261008-091321-H3M8_code_analyzer.md`
**Satisfies:** R3 — the owner's real funding plan (10,000,000 IDR start, +5,000,000 IDR on the 25th of each month) reaches paper
**Depends on:** Phase 5 — `sim/contributions.py` exists and defines the schedule; this phase consumes it in exactly one test and never defines a second one
**Difficulty:** HARD
**Package:** `engine.paper`, `db`

---

## Goal

After this phase paper can **write money down and credit it to a book on the session it lands on**.
Today it cannot: `paper_state.initial_cash_usd` is written once (`store.py:417`) and never updated,
the only later UPDATE (`store.py:449`) writes `cash_usd`, `equity_usd` and `last_session`, and a
measured `grep -rniE "deposit|contribut|top.?up|cashflow|add_cash"` over `engine/src`, `web/lib`,
`web/app` and `db/migrations` returns six hits, every one the English word "contributes" in an
unrelated docstring. A new `paper_contributions` table holds one **dated** row per deposit — IDR,
the rate, and the dollars — and a new store path credits it to the engine's cash before the session
steps. A deposit raises cash and equity and is **not** a fill, **not** a trade and **not** a return;
`paper_contributions` is the only thing that records it, which is exactly what phase 7 needs to tell
"the book grew" from "the owner added money".

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** none. Nothing is removed, renamed or re-signed. This phase is purely additive.

**Renames:** none.

**Creates:**
- `db/migrations/016_contributions.sql` — table `paper_contributions`, index `paper_contributions_session`. **016 is taken; phase 12 keeps 017.**
- `paper.store.Contribution` (dataclass, `store.py`, new section after `write_kickoff`)
- `paper.store.IDR_QUANTUM` (`Decimal("0.01")`, `store.py`)
- `paper.store.contribution_session` (`store.py`)
- `paper.store.record_contribution` (`store.py`)
- `paper.store.read_contribution` (`store.py`)
- `paper.store.read_contributions` (`store.py`) — **phase 7's dated cashflows read through this**
- `paper.store.accrue_contributions` (`store.py`)
- `paper.store.due_contributions` (`store.py`)
- `paper.store.apply_contributions` (`store.py`)
- `paper.book.deposit_book` (`book.py`)

**Signature changes:** none. `init_paper_state`, `write_paper_state`, `write_pending`,
`write_kickoff`, `load_book`, `save_book_night`, `settle_book`, `decide_book` all keep the exact
signatures they have today.

**Schema changes:** one new table and one new index. **No existing table is altered.** No
`paper_state` row is read for modification, rewritten or deleted. `paper_state.initial_cash_usd`
stays write-once and keeps its present meaning: *the capital on day 0*, not *the capital to date*.

**Requires (from earlier phases):**
- Phase 5 has created `engine/src/seer_engine/sim/contributions.py` and it exports a schedule
  value object plus the owner's instance. See **Assumptions** for the exact names assumed; only
  `engine/tests/test_paper_store.py` imports it, so a name mismatch is a one-line fix.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/paper/roster.py` and `db/migrations/017_*` — phase 12
- `engine/src/seer_engine/paper/benchmark.py` — phase 3
- `engine/src/seer_engine/paper/bracket.py` and everything under `engine/src/seer_engine/sim/` — phase 4
- `engine/src/seer_engine/sim/contributions.py`, `backtest/runner.py`, `backtest/book_runner.py` — phase 5
- `backtest/metrics.py`, `backtest/benchmark.py`, `backtest/dev.py`, `lab/store.py` — phase 7
- everything under `web/` — phases 9 and 10

**Assigned by the reconciler, 2026-10-08** (the draft of this plan listed all four as unclaimed):

| file | owner | why |
|---|---|---|
| `engine/src/seer_engine/commands/paper.py` | **phase 12** | index Decision D10 — four phases want it and two of them are concurrent |
| `engine/src/seer_engine/paper/replay.py` | **phase 12** | D10, same block |
| `engine/src/seer_engine/commands/paper_check.py` | **phase 12** | one label line, travels with `replay.py` |
| `engine/src/seer_engine/paper/compare.py` + `engine/src/seer_engine/commands/compare.py` | **THIS PHASE** | Handoff 3 and Step 10 — it needs this phase's `read_contributions` and nothing else |

**Also fenced off for phase 12:** `paper/store.py:1127-1145` (`load_benchmark`). This phase owns
`store.py` but **must not touch `load_benchmark`** — phase 3's `cost_model` keyword lands there and
D10 keeps every wire in phase 12. This phase's regions in that file are the deposit path (`:417`,
`:449`) and the new contributions section between `write_kickoff` and `save_book_preview`, all
line-disjoint from `:1127`.

---

## Decisions this phase settles

### D6a. A contribution is recorded in IDR **and** USD, with the rate between them

All three columns, all frozen when the row is written.

| column | why it must be there |
|---|---|
| `amount_idr` | The schedule is an IDR fact. The owner decides, thinks and sends 5,000,000 IDR. A USD-only row would silently re-fix the deposit at one rate and make the schedule unreproducible from the stored record. |
| `usd_idr` | The rate moves between deposits and that movement is real: the same 5,000,000 IDR buys fewer dollars when the rupiah is weaker, and the book must feel it. It is also the audit trail — without it `amount_usd` is a number with no derivation. |
| `amount_usd` | The book trades in USD and phase 7's money-weighted return integrates **dollar** cashflows; an IRR cannot cross currencies. |

**Which rate.** `usd_idr_on(session_date)` — the latest `fx_rates` row dated on or before the
session the money lands on. That is the same source and the same rule `paper` already converts the
day-0 start at (`commands/paper.py:709` `view.usd_idr_on(rd.data_date)`), and the dollars exist on
the session the book can first spend them, not on the calendar date the transfer was initiated.

**Why frozen.** `fx_rates` is backfilled. If `amount_usd` were recomputed on read, a corrected old
rate would silently move a stepped book's history. `paper_state` already uses exactly this pattern
(`usd_idr` = "the rate initial cash was converted at", `003_paper.sql:25`); this is that convention
continued, not a new one. The conversion itself reuses `sim.model.initial_cash_usd(idr, usd_idr)`
— the *same* function day 0 uses — so a deposit and a start never round differently.

### D6b. A table, not a column on `paper_state`

A running total (`initial_cash_usd += deposit`) would let paper hold the money but would destroy
the thing the measurement needs. A deposit raises ending equity **without being a return**, so
every return measure must be able to separate the two, and that needs the **dated** cashflows —
one row per deposit, with its date — which is what a money-weighted return integrates over. A
total cannot be un-summed. Stated directly in the phase scope and in Decisions D4.

### D6c. The deposit lands on the first NYSE session **on or after** the calendar date

The owner deposits on the 25th; the exchange calendar produces the lag. No lag is baked in.
Measured here, 2026-10-08, with `seer_engine.dates` over the twelve months from 2026-10-25:

```
due date    session?  lands on     next month's 1st session  calendar gap  idle sessions
2026-10-25  no        2026-10-26   2026-11-02                 8d            5
2026-11-25  yes       2026-11-25   2026-12-01                 6d            3
2026-12-25  no        2026-12-28   2027-01-04                10d            4
2027-01-25  yes       2027-01-25   2027-02-01                 7d            5
2027-02-25  yes       2027-02-25   2027-03-01                 4d            2
2027-03-25  yes       2027-03-25   2027-04-01                 7d            4
2027-04-25  no        2027-04-26   2027-05-03                 8d            5
2027-05-25  yes       2027-05-25   2027-06-01                 7d            4
2027-06-25  yes       2027-06-25   2027-07-01                 6d            4
2027-07-25  no        2027-07-26   2027-08-02                 8d            5
2027-08-25  yes       2027-08-25   2027-09-01                 7d            5
2027-09-25  no        2027-09-27   2027-10-01                 6d            4
                                              mean 7.0 calendar days, range 4-10
```

Command that produced it (run from the worktree root):

```
PYTHONPATH=engine/src python -c "
from datetime import date
from seer_engine import dates
for y,m in [(2026,10),(2026,11),(2026,12),(2027,1),(2027,2),(2027,3),(2027,4),(2027,5),(2027,6),(2027,7),(2027,8),(2027,9)]:
    due=date(y,m,25); land=due if dates.is_session(due) else dates.next_session(due)
    ny,nm=(y+1,1) if m==12 else (y,m+1); first=date(ny,nm,1)
    first=first if dates.is_session(first) else dates.next_session(first)
    print(due, dates.is_session(due), land, first, (first-due).days,
          len([s for s in dates.sessions(land,first) if s<first]))"
```

Two measured facts come out of it and both are encoded:
**four of the twelve 25ths are not sessions**, so the landing date must be computed, not assumed;
and **the money then sits as idle cash for 2 to 5 sessions** before the next month's first session
deploys it. That idle cash is reproduced, not smoothed away — depositing at the rotation would
overstate returns.

### D6d. One row per strategy, per due date

Every roster entry runs its own 10,000,000 IDR paper book (`commands/paper.py:712`,
`paper/capital.py:11`), so each receives its own copy of the same schedule. That is what makes the
gap fixable **below** the engines rather than per-method: the four quant books, C (bracket) and SPY
(benchmark) all read one table through one store path. Verified 2026-10-08 in answer to the owner
asking whether every roster method accounts for his monthly contribution — none of them do, and the
concept did not exist.

### D6e. `apply_contributions` does **not** write `paper_state`

The night loads a book once and holds it in memory across the sessions it steps; `save_book_night`
is the only writer of `cash_usd`, and has been since 003. If `apply_contributions` also wrote
`paper_state.cash_usd`, the night's later save would overwrite it and the two bookkeepings would
drift. So `apply_contributions` stamps the rows applied and **returns the dollars**; the night adds
them to the state it is stepping (`deposit_book` for a book; a one-line `cash` bump for a bracket
`Portfolio` or a `BenchmarkState`). Money recorded once, carried once, written once.

### D6f. Crediting a session that was already stepped is a `StoreError`

`docs/runbooks/paper-trading.md:60-68` and plan invariant 3: settled history is never rewritten.
`apply_contributions` refuses any `session <= paper_state.last_session`.

---

## Files

| File | Action | What changes |
|---|---|---|
| `db/migrations/016_contributions.sql` | create | the `paper_contributions` table and its index; additive, lands inert while paper is paused |
| `engine/src/seer_engine/paper/store.py` | modify | imports at `:39` and `:55`; a new "contributions" section inserted after `write_kickoff` ends at `:491` and before `save_book_preview` at `:493`; module docstring bullet near `:17` |
| `engine/src/seer_engine/paper/book.py` | modify | `PRICE_QUANTUM` added to the import at `:50`; `deposit_book` inserted after `rank_basket` ends at `:326` and before `settle_book` at `:329`; module docstring paragraph after `:35` |
| `engine/tests/test_paper_store.py` | modify | imports near `:19`; a new "contributions" section appended after the last test (`:649`) |
| `engine/tests/test_paper_book.py` | modify | `deposit_book` added to the import at `:48-55`; two tests appended after the last test (`:1067`) |
| `engine/src/seer_engine/paper/compare.py` | modify (**assigned by the reconciler**) | `_returns` (`:192`) takes the per-session deposits so a deposit is not read as a return; `compare`'s signature carries them; the module docstring says so. Step 10 |
| `engine/src/seer_engine/commands/compare.py` | modify (**assigned by the reconciler**) | the impure edge reads `store.read_contributions` and hands the dated dollars to `compare`. Step 10 |

Seven files. The plan index's draft said 5; the two `compare` files are the reconciler's assignment
(Handoff 3 below).

---

## Implementation Steps

### Step 1: The migration

**File:** `db/migrations/016_contributions.sql` (new file)
**Change:** one new table and one new index. Nothing existing is altered; no data statement runs.
**Code:**

```sql
-- Seer schema v16: the owner's monthly contribution reaches paper (plan gotrade-fee-rebuild,
-- R3, phase 6; the owner's decision, relayed 2026-10-08).
--
-- WHAT WAS MISSING. Until this file paper had exactly one record of capital,
-- paper_state.initial_cash_usd, and exactly one writer for it (paper/store.py init_paper_state's
-- INSERT). The only later UPDATE writes cash_usd, equity_usd and last_session. There was no
-- column, and no table, in which money arriving after day 0 could be written down. The owner
-- adds 5,000,000 IDR to a 10,000,000 IDR start on the 25th of every month, so every paper book
-- -- the four quant books, C and SPY alike -- was modelling a strategy the owner is not running.
-- The gap is BELOW every engine, so it is closed once, here, and not per method.
--
-- WHY A TABLE AND NOT A COLUMN. A running total (initial_cash_usd += deposit) would let paper
-- hold the money but would destroy the thing the measurement needs. A deposit raises ending
-- equity WITHOUT being a return, so every return measure has to be able to tell "the book grew"
-- from "the owner added money". That needs the DATED cashflows, one row per deposit, which is
-- what a money-weighted return integrates over. A total cannot be un-summed.
--
-- WHY ALL THREE OF IDR, THE RATE AND USD. The owner thinks and deposits in IDR; the book trades
-- in USD; and the rate moves between deposits, which is real -- the same 5,000,000 IDR buys
-- fewer dollars when the rupiah is weaker.
--   amount_idr   what he actually sends. The schedule is an IDR fact; a USD-only row would
--                silently re-fix the deposit at one rate and be unreproducible.
--   usd_idr      the fx_rates rate on session_date: the latest rate dated on or before it, which
--                is exactly what paper already converts the day-0 start at
--                (commands/paper.py's view.usd_idr_on, backtest.market.usd_idr_on).
--   amount_usd   the dollars credited, computed as sim.model.initial_cash_usd(amount_idr,
--                usd_idr) -- the SAME conversion day 0 uses, so a deposit and a start never
--                round differently.
-- All three are frozen the night the row is written, because fx_rates is backfilled and a
-- stepped book's history must not move when an old rate is corrected. paper_state.usd_idr
-- ("the rate initial cash was converted at", 003_paper.sql) is this same convention.
--
-- WHY TWO DATES. due_date is the owner's calendar date, the 25th. session_date is the first NYSE
-- session on or after it; the exchange calendar produces the lag and no lag is baked in.
-- Measured 2026-10-08 over the twelve months from 2026-10-25: four of the twelve 25ths are not
-- sessions, and after landing the money sits as idle cash for 2 to 5 sessions before the next
-- month's first session deploys it (mean 7.0 calendar days from the 25th to that session, range
-- 4 to 10). Reproducing that idle cash is the point; depositing at the rotation would overstate
-- returns.
--
-- ONE ROW PER (STRATEGY, DUE DATE). Every roster entry runs its own 10,000,000 IDR paper book
-- (paper/capital.py PAPER_INITIAL_IDR), so each receives its own copy of the same schedule.
--
-- applied_at is NULL until the paper night that steps session_date credits the money to that
-- strategy's state. Crediting a session already stepped is refused in the store, not here
-- (docs/runbooks/paper-trading.md:60-68: settled history is never rewritten).
--
-- ADDITIVE AND INERT. One new table and one index; nothing existing is altered and no
-- paper_state row is read or rewritten. PAPER_PAUSED is 'true' and zero sessions have been
-- stepped, and .github/workflows/nightly.yml:48 confirms Migrate still runs while paused -- so
-- this lands empty and stays empty until the owner resumes. Nothing outside paper reads it yet.
CREATE TABLE IF NOT EXISTS paper_contributions (
  strategy_id   text NOT NULL REFERENCES strategies(id),
  due_date      date NOT NULL,                         -- the owner's calendar date (the 25th)
  session_date  date NOT NULL,                         -- first NYSE session on or after due_date
  amount_idr    numeric(18,2) NOT NULL CHECK (amount_idr > 0),
  usd_idr       numeric(12,4) NOT NULL CHECK (usd_idr > 0),   -- the rate on session_date
  amount_usd    numeric(14,4) NOT NULL CHECK (amount_usd > 0),-- frozen when the row is written
  applied_at    timestamptz,                           -- NULL until session_date's night credits it
  recorded_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (strategy_id, due_date),
  CHECK (session_date >= due_date)
);
CREATE INDEX IF NOT EXISTS paper_contributions_session
  ON paper_contributions (strategy_id, session_date);
```

**Impact:** `conftest.py`'s `pg` fixture globs `db/migrations/*.sql` in name order and applies all
of them, so every DB test sees the new table with no fixture change. `commands/migrate.py` and
`web/scripts/migrate.mjs` share `schema_migrations` keyed on the file name, so either runner
applies it once.

---

### Step 2: `store.py` imports

**File:** `engine/src/seer_engine/paper/store.py:39` and `:55`
**Change:** `Callable` for the injected FX lookup, and `initial_cash_usd` for the conversion.
**Code:** replace line 39

```python
from collections.abc import Iterable, Mapping, Sequence
```

with

```python
from collections.abc import Callable, Iterable, Mapping, Sequence
```

and replace line 55

```python
from seer_engine.sim.model import Event, Order, Portfolio, Snapshot
```

with

```python
from seer_engine.sim.model import Event, Order, Portfolio, Snapshot, initial_cash_usd
```

**Impact:** none beyond the two names. `seer_engine.sim.model` is already imported here; phase 4
changes `buy_cost` / `sell_proceeds` in that module but not `initial_cash_usd`, so there is no
collision.

---

### Step 3: `store.py` module docstring

**File:** `engine/src/seer_engine/paper/store.py:17` (inside the bullet list, after the
`paper_state` bullet)
**Change:** add one bullet so the module's own description stays true.
**Code:** insert immediately after the line

```
- ``paper_state``: one row per paper strategy, the state between nights.
```

the lines

```
- ``paper_contributions`` (migration 016): the owner's dated deposits, one row per (strategy,
  calendar due date), with the IDR he sends, the rate it converted at and the dollars credited.
  Below every engine: the four quant books, the bracket control C and the SPY benchmark all take
  their deposits through ``accrue_contributions`` and ``apply_contributions``. A deposit is a
  cashflow, never a fill and never a trade, so nothing in ``book_fills`` or ``orders`` records it.
```

**Impact:** documentation only.

---

### Step 4: the contributions section in `store.py`

**File:** `engine/src/seer_engine/paper/store.py` — insert between `write_kickoff` (ends `:491`)
and `save_book_preview` (`:493`)
**Change:** the whole deposit path, engine-agnostic. Note it takes **plain dates and a plain
amount**, never a schedule object, so `paper/store.py` imports nothing from
`sim/contributions.py`: the schedule is read by the caller (see Handoffs).
**Code:**

```python
# --------------------------------------------------------------------------- contributions

IDR_QUANTUM = Decimal("0.01")  # paper_contributions.amount_idr, numeric(18,2)

_CONTRIBUTION_COLUMNS = (
    "strategy_id, due_date, session_date, amount_idr, usd_idr, amount_usd, applied_at"
)


@dataclass(frozen=True)
class Contribution:
    """One ``paper_contributions`` row: money the owner added, dated.

    ``due_date`` is his own calendar date (the 25th of the month); ``session_date`` is the first
    NYSE session on or after it, the session the money reaches the book on. ``amount_idr`` is
    what he sends, ``usd_idr`` the rate it converted at, ``amount_usd`` the dollars credited --
    all three frozen when the row was written. ``applied`` is True once a stepped session took it.
    """

    strategy_id: str
    due_date: date
    session_date: date
    amount_idr: Decimal
    usd_idr: Decimal
    amount_usd: Decimal
    applied: bool


def _contribution(row: Sequence[Any]) -> Contribution:
    return Contribution(
        strategy_id=row[0],
        due_date=row[1],
        session_date=row[2],
        amount_idr=row[3],
        usd_idr=row[4],
        amount_usd=row[5],
        applied=row[6] is not None,
    )


def contribution_session(due_date: date) -> date:
    """The NYSE session a deposit dated ``due_date`` lands on.

    ``due_date`` itself when it is a session, otherwise the next one. The owner deposits on a
    calendar date and the exchange calendar produces the lag; no lag is baked in. Measured
    2026-10-08 over the twelve months from 2026-10-25, four of the twelve 25ths are not sessions
    and the gap from the 25th to the next month's first session is a mean of 7.0 calendar days
    ranging 4 to 10, so a fixed lag would be wrong in ten months of twelve.

    Pure, like ``market_window_since``. ``dates.next_session`` raises past the loaded calendar's
    range, as it does everywhere else.
    """
    _date("due_date", due_date)
    return due_date if dates.is_session(due_date) else dates.next_session(due_date)


def read_contribution(conn: psycopg.Connection, strategy_id: str, due_date: date) -> Contribution | None:
    """The contribution of ``strategy_id`` dated ``due_date``, or None."""
    _date("due_date", due_date)
    row = conn.execute(
        f"SELECT {_CONTRIBUTION_COLUMNS} FROM paper_contributions "
        "WHERE strategy_id = %s AND due_date = %s",
        (strategy_id, due_date),
    ).fetchone()
    return None if row is None else _contribution(row)


def read_contributions(conn: psycopg.Connection, strategy_id: str) -> tuple[Contribution, ...]:
    """Every contribution of ``strategy_id``, ``due_date`` ascending.

    These are the dated cashflows a money-weighted return integrates over. Equity alone cannot
    say whether a rise was the book growing or the owner adding money; these rows can, which is
    why the deposit is kept as rows and not as a running total.
    """
    rows = conn.execute(
        f"SELECT {_CONTRIBUTION_COLUMNS} FROM paper_contributions "
        "WHERE strategy_id = %s ORDER BY due_date",
        (strategy_id,),
    ).fetchall()
    return tuple(_contribution(r) for r in rows)


def record_contribution(
    conn: psycopg.Connection,
    strategy_id: str,
    *,
    due_date: date,
    amount_idr: Decimal,
    usd_idr: Decimal,
) -> Contribution:
    """Write down one deposit of ``amount_idr`` dated ``due_date``, converted at ``usd_idr``.

    ``session_date`` is ``contribution_session(due_date)``. ``amount_usd`` is
    ``sim.model.initial_cash_usd(amount_idr, usd_idr)`` -- the same conversion the day-0 start
    uses, so a deposit and a start never round differently.

    Writing the same ``(strategy_id, due_date)`` again changes nothing and returns the row
    already stored. The rate a deposit converted at is frozen the first night it is recorded,
    because ``fx_rates`` is backfilled and a stepped book's history must not move when an old
    rate is corrected (``paper_state.usd_idr`` is the same convention).
    """
    _date("due_date", due_date)
    _exact("amount_idr", amount_idr, IDR_QUANTUM)
    _exact("usd_idr", usd_idr)
    if amount_idr <= 0:
        raise ValueError(f"amount_idr must be > 0, got {amount_idr}")
    if usd_idr <= 0:
        raise ValueError(f"usd_idr must be > 0, got {usd_idr}")
    session_date = contribution_session(due_date)
    amount_usd = initial_cash_usd(amount_idr, usd_idr)
    conn.execute(
        "INSERT INTO paper_contributions "
        "(strategy_id, due_date, session_date, amount_idr, usd_idr, amount_usd) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (strategy_id, due_date) DO NOTHING",
        (strategy_id, due_date, session_date, amount_idr, usd_idr, amount_usd),
    )
    stored = read_contribution(conn, strategy_id, due_date)
    if stored is None:
        raise StoreError(f"{strategy_id}: the contribution for {due_date} was not written")
    return stored


def accrue_contributions(
    conn: psycopg.Connection,
    strategy_id: str,
    due_dates: Sequence[date],
    amount_idr: Decimal,
    *,
    through: date,
    usd_idr_on: Callable[[date], Decimal],
) -> tuple[Contribution, ...]:
    """Record every deposit in ``due_dates`` that has landed by ``through``; return them in date
    order, newly written or already stored.

    ``due_dates`` are the schedule's calendar dates. They are passed as plain dates on purpose:
    the schedule itself is a pure value object in ``sim.contributions`` and the night reads it,
    so this module never depends on the schedule's shape and there is exactly one schedule in
    the system.

    A date is recorded once its landing session (``contribution_session``) is on or before
    ``through`` -- the session the night is about to step -- and never before, because the rate
    is read **on the landing session**: ``usd_idr_on`` is the night's own
    ``backtest.market.Market.usd_idr_on`` (the latest ``fx_rates`` row dated on or before that
    date), the same source the day-0 start converts at. A date already recorded is left exactly
    as it is and ``usd_idr_on`` is not called for it, so a backfill can never move it.
    """
    _session("through", through)
    _exact("amount_idr", amount_idr, IDR_QUANTUM)
    if isinstance(due_dates, (str, Mapping)) or not isinstance(due_dates, Sequence):
        raise TypeError(f"due_dates must be a sequence of dates, got {type(due_dates).__name__}")
    if not callable(usd_idr_on):
        raise TypeError("usd_idr_on must be callable: date -> Decimal")
    out: list[Contribution] = []
    for due in sorted({_date("due_date", d) for d in due_dates}):
        if contribution_session(due) > through:
            continue
        stored = read_contribution(conn, strategy_id, due)
        if stored is not None:
            out.append(stored)
            continue
        out.append(
            record_contribution(
                conn,
                strategy_id,
                due_date=due,
                amount_idr=amount_idr,
                usd_idr=usd_idr_on(contribution_session(due)),
            )
        )
    return tuple(out)


def due_contributions(
    conn: psycopg.Connection, strategy_id: str, session: date
) -> tuple[Contribution, ...]:
    """The contributions landing on ``session`` that no session has credited yet, by ``due_date``."""
    _session("session", session)
    rows = conn.execute(
        f"SELECT {_CONTRIBUTION_COLUMNS} FROM paper_contributions "
        "WHERE strategy_id = %s AND session_date = %s AND applied_at IS NULL ORDER BY due_date",
        (strategy_id, session),
    ).fetchall()
    return tuple(_contribution(r) for r in rows)


def apply_contributions(conn: psycopg.Connection, strategy_id: str, session: date) -> Decimal:
    """Credit ``session``'s contributions: stamp them applied and return the dollars to add to
    the engine's cash. ``Decimal("0.0000")`` when none land on ``session``.

    The night calls this for each session it is about to step, **before** the step, and adds the
    result to the state it is stepping: ``paper.book.deposit_book`` for a book, the ``cash``
    field for a bracket ``sim.Portfolio`` or a ``paper.benchmark.BenchmarkState``. The money is
    then written by that engine's own ``save_*_night``, which is what it has always been for
    ``cash_usd``: this function deliberately does NOT write ``paper_state``, so the deposit is
    recorded once, carried once and written once, with no second bookkeeping to drift.

    ``session`` must be after ``paper_state.last_session``. Crediting a session already stepped
    would rewrite settled history (docs/runbooks/paper-trading.md:60-68), so it is a StoreError;
    the row stays unapplied and visible rather than being silently dropped.

    Calling it twice over the same session credits once: the second call sees no unapplied row.
    """
    _session("session", session)
    state = _require_state(conn, strategy_id)
    if session <= state.last_session:
        raise StoreError(
            f"{strategy_id}: {session} was already stepped (last_session {state.last_session}); "
            "a contribution cannot be credited to a settled session"
        )
    rows = due_contributions(conn, strategy_id, session)
    if not rows:
        return Decimal("0.0000")
    conn.execute(
        "UPDATE paper_contributions SET applied_at = now() "
        "WHERE strategy_id = %s AND session_date = %s AND applied_at IS NULL",
        (strategy_id, session),
    )
    total = Decimal("0.0000")
    for c in rows:
        total += c.amount_usd
    return _exact("credited", total)
```

**Impact:** `store.py` grows one self-contained section. No existing function, query or signature
changes, so every current caller and every current test is untouched. Like the rest of the module
it neither commits nor rolls back: the night's `db.transaction` decides, and a failed night rolls
the `applied_at` stamps back with everything else.

---

### Step 5: `book.py` import

**File:** `engine/src/seer_engine/paper/book.py:50`
**Change:** `PRICE_QUANTUM` for the deposit's exactness check.
**Code:** replace line 50

```python
from seer_engine.prices import Bar
```

with

```python
from seer_engine.prices import PRICE_QUANTUM, Bar
```

**Impact:** `seer_engine.prices` is a pure module (no psycopg, no clock), so
`tests/test_strategy_purity.py`'s glob over `seer_engine/paper/*.py` still passes. `replace` is
already imported at `book.py:42`.

---

### Step 6: `book.py` module docstring

**File:** `engine/src/seer_engine/paper/book.py` — after the paragraph ending at `:35`
(`... plan Decisions, "Force-close rule live"`), before the closing `"""` on `:36`
**Change:** one paragraph, so the module says what the new function is for.
**Code:** insert

```

``deposit_book`` is the third piece: the owner adds 5,000,000 IDR on the 25th of each month, and
``paper.store.apply_contributions`` converts and dates it. The night credits it to the book with
``deposit_book`` **before** ``settle_book`` for the session it lands on, so that session's buys can
spend it. A deposit raises cash and equity and nothing else: it is not a fill, not a trade, and
leaves no ``book_fills`` row, because a rise in equity that is not a return has to stay
distinguishable from one that is. The money then sits as cash until the next decision session
deploys it -- measured, 2 to 5 sessions over the twelve months from 2026-10-25 -- and that idle
cash is reproduced, not smoothed away.
```

**Impact:** documentation only.

---

### Step 7: `deposit_book`

**File:** `engine/src/seer_engine/paper/book.py` — insert between `rank_basket` (ends `:326`) and
`settle_book` (`:329`)
**Change:** the pure credit for the book engine.
**Code:**

```python
def deposit_book(book: Book, amount_usd: Decimal) -> Book:
    """``book`` with ``amount_usd`` of new money in cash, before the session it lands on.

    Cash and equity both rise by the amount -- the book really is worth that much more the moment
    the money arrives -- and nothing else moves: no position, no mark, no ``last_session``. The
    deposit is a cashflow, not a fill and not a trade, so it produces no ``Fill`` and no
    ``Trade`` and ``paper_contributions`` is the only record of it.

    ``settle_book`` recomputes equity from cash and the marks (``sim.book.step_book``'s
    ``_valuation``), so the session's snapshot carries the deposit with no further help; crediting
    equity here keeps the book self-consistent for a caller that reads it before stepping.

    ``amount_usd`` must be a positive Decimal the cash column holds exactly (4 dp). Pure, like the
    rest of this module.
    """
    if not isinstance(book, Book):
        raise TypeError(f"book must be a Book, got {type(book).__name__}")
    if not isinstance(amount_usd, Decimal):
        raise TypeError(f"amount_usd must be a Decimal, got {type(amount_usd).__name__}")
    if not amount_usd.is_finite():
        raise ValueError(f"amount_usd must be finite, got {amount_usd!r}")
    if amount_usd <= 0:
        raise ValueError(f"amount_usd must be > 0, got {amount_usd}")
    if amount_usd.quantize(PRICE_QUANTUM) != amount_usd:
        raise ValueError(
            f"amount_usd {amount_usd} has more decimals than cash holds ({PRICE_QUANTUM})"
        )
    return replace(book, cash=book.cash + amount_usd, equity=book.equity + amount_usd)
```

**Impact:** `Book.__post_init__` revalidates both fields on `replace`. Nothing else in `book.py`
is touched, so `decide_book` / `settle_book` / `needs_kickoff` / `last_rank_session` /
`rank_basket` keep their exact behaviour and `test_paper_book.py`'s "equals `run_book` field for
field" group is unaffected.

---

### Step 8: `test_paper_store.py` — imports and the contributions section

**File:** `engine/tests/test_paper_store.py:19` (import block) and after the last test at `:649`
**Change:** add the section. `date`, `Decimal`, `pytest` and `store` are already imported at
`:7-18`; `D`, `S0`..`S5`, `CASH0`, `RATE` and `BOOK_ID` are already defined at `:34-47`.
**Code:** add the import (phase 5's module; see **Assumptions**) after line 19
(`from seer_engine.paper import store`):

```python
from seer_engine.sim.contributions import OWNER_MONTHLY
```

then append:

```python
# --------------------------------------------------------------------------- contributions

# The owner's deposit (his decision, relayed 2026-10-08): 5,000,000 IDR on the 25th of each month.
CONTRIB_IDR = D("5000000.00")
DUE_WEEKEND = date(2026, 9, 26)   # a Saturday -> lands on S0, 2026-09-28
DUE_SESSION = date(2026, 9, 30)   # a Wednesday -> lands on itself, S2
DUE_LATE = date(2026, 10, 3)      # a Saturday -> lands on S5, 2026-10-05


def test_contribution_session_lands_on_the_date_itself_or_the_next_session():
    assert store.contribution_session(DUE_SESSION) == S2
    assert store.contribution_session(DUE_WEEKEND) == S0
    assert store.contribution_session(DUE_LATE) == S5
    # Measured 2026-10-08: four of the twelve 25ths from 2026-10-25 are not NYSE sessions, so the
    # landing date has to be computed. December's is the widest gap in the year.
    assert store.contribution_session(date(2026, 10, 25)) == date(2026, 10, 26)
    assert store.contribution_session(date(2026, 11, 25)) == date(2026, 11, 25)
    assert store.contribution_session(date(2026, 12, 25)) == date(2026, 12, 28)
    with pytest.raises(TypeError):
        store.contribution_session("2026-09-30")


def test_the_owner_monthly_schedule_lands_where_the_calendar_says_it_does():
    """The schedule phase 5 defines, read through this phase's landing rule. One schedule only."""
    due = OWNER_MONTHLY.dates_in(date(2026, 10, 1), date(2027, 9, 30))
    assert len(due) == 12
    assert due[0] == date(2026, 10, 25) and due[-1] == date(2027, 9, 25)
    assert all(d.day == 25 for d in due)
    landed = [store.contribution_session(d) for d in due]
    assert sum(1 for d, s in zip(due, landed) if s != d) == 4  # four 25ths are not sessions
    assert landed[0] == date(2026, 10, 26)
    assert landed[2] == date(2026, 12, 28)


def test_record_contribution_freezes_the_rate_and_the_dollars(pg):
    c = store.record_contribution(pg, "A", due_date=DUE_WEEKEND, amount_idr=CONTRIB_IDR, usd_idr=RATE)
    assert (c.strategy_id, c.due_date, c.session_date) == ("A", DUE_WEEKEND, S0)
    assert (c.amount_idr, c.usd_idr, c.amount_usd) == (CONTRIB_IDR, RATE, D("312.5000"))
    assert c.applied is False
    # Writing it again at another rate changes nothing: fx_rates is backfilled and a recorded
    # deposit must not move under it.
    again = store.record_contribution(
        pg, "A", due_date=DUE_WEEKEND, amount_idr=CONTRIB_IDR, usd_idr=D("17841.0000")
    )
    assert again == c
    assert store.read_contributions(pg, "A") == (c,)
    assert store.read_contribution(pg, "A", DUE_SESSION) is None


def test_record_contribution_converts_as_day_zero_does(pg):
    # 17841.0000 is the rate the frozen production book started at: 10,000,000 IDR -> 560.5067 USD.
    c = store.record_contribution(
        pg, "A", due_date=DUE_SESSION, amount_idr=CONTRIB_IDR, usd_idr=D("17841.0000")
    )
    assert c.amount_usd == D("280.2533")
    assert c.amount_usd == initial_cash_usd(CONTRIB_IDR, D("17841.0000"))


def test_record_contribution_refuses_what_the_columns_cannot_hold(pg):
    with pytest.raises(ValueError):
        store.record_contribution(pg, "A", due_date=DUE_SESSION, amount_idr=D("5000000.001"), usd_idr=RATE)
    with pytest.raises(ValueError):
        store.record_contribution(pg, "A", due_date=DUE_SESSION, amount_idr=D("0.00"), usd_idr=RATE)
    with pytest.raises(ValueError):
        store.record_contribution(pg, "A", due_date=DUE_SESSION, amount_idr=CONTRIB_IDR, usd_idr=D("0.0000"))
    with pytest.raises(TypeError):
        store.record_contribution(pg, "A", due_date=DUE_SESSION, amount_idr=5000000.0, usd_idr=RATE)
    assert store.read_contributions(pg, "A") == ()


def test_accrue_records_only_what_has_landed_and_keeps_the_rate_it_was_written_at(pg):
    rates = {S0: RATE, S2: D("17841.0000"), S5: D("16500.0000")}
    due = [DUE_LATE, DUE_WEEKEND, DUE_SESSION]  # out of order on purpose
    rows = store.accrue_contributions(
        pg, BOOK_ID, due, CONTRIB_IDR, through=S2, usd_idr_on=rates.__getitem__
    )
    assert [c.due_date for c in rows] == [DUE_WEEKEND, DUE_SESSION]
    assert [c.session_date for c in rows] == [S0, S2]
    assert [c.amount_usd for c in rows] == [D("312.5000"), D("280.2533")]
    # DUE_LATE lands on S5, after tonight: not recorded yet.
    assert [c.due_date for c in store.read_contributions(pg, BOOK_ID)] == [DUE_WEEKEND, DUE_SESSION]

    later = store.accrue_contributions(
        pg, BOOK_ID, due, CONTRIB_IDR, through=S5, usd_idr_on=rates.__getitem__
    )
    assert [c.due_date for c in later] == [DUE_WEEKEND, DUE_SESSION, DUE_LATE]
    assert later[0].usd_idr == RATE and later[1].usd_idr == D("17841.0000")
    assert later[2].amount_usd == D("303.0303")  # 5,000,000 / 16,500


def test_accrue_does_not_read_the_rate_for_a_date_it_already_has(pg):
    store.record_contribution(pg, BOOK_ID, due_date=DUE_SESSION, amount_idr=CONTRIB_IDR, usd_idr=RATE)

    def boom(_d):
        raise AssertionError("usd_idr_on must not be called for an already-recorded date")

    rows = store.accrue_contributions(pg, BOOK_ID, [DUE_SESSION], CONTRIB_IDR, through=S2, usd_idr_on=boom)
    assert [c.usd_idr for c in rows] == [RATE]


def test_apply_contributions_credits_once_and_never_a_settled_session(pg):
    store.init_paper_state(pg, BOOK_ID, paper_start=S1, cash0=CASH0, usd_idr=RATE)  # last_session = S0
    store.record_contribution(pg, BOOK_ID, due_date=DUE_WEEKEND, amount_idr=CONTRIB_IDR, usd_idr=RATE)
    store.record_contribution(pg, BOOK_ID, due_date=DUE_SESSION, amount_idr=CONTRIB_IDR, usd_idr=RATE)

    # S0 is the day-0 session: already settled, so its deposit cannot be credited to it.
    with pytest.raises(store.StoreError):
        store.apply_contributions(pg, BOOK_ID, S0)
    assert store.apply_contributions(pg, BOOK_ID, S1) == D("0.0000")   # nothing lands on S1
    assert store.apply_contributions(pg, BOOK_ID, S2) == D("312.5000")
    assert [c.applied for c in store.read_contributions(pg, BOOK_ID)] == [False, True]
    # A second pass over the same session credits nothing twice.
    assert store.apply_contributions(pg, BOOK_ID, S2) == D("0.0000")
    assert store.due_contributions(pg, BOOK_ID, S2) == ()
    # paper_state is untouched: the night's own save is the only writer of cash_usd.
    state = store.read_paper_state(pg, BOOK_ID)
    assert (state.cash_usd, state.equity_usd, state.initial_cash_usd) == (CASH0, CASH0, CASH0)


def test_two_deposits_landing_on_one_session_are_credited_together(pg):
    store.init_paper_state(pg, BOOK_ID, paper_start=S1, cash0=CASH0, usd_idr=RATE)
    # A Saturday and the Sunday after it both land on the Monday.
    store.record_contribution(pg, BOOK_ID, due_date=date(2026, 10, 3), amount_idr=CONTRIB_IDR, usd_idr=RATE)
    store.record_contribution(pg, BOOK_ID, due_date=date(2026, 10, 4), amount_idr=CONTRIB_IDR, usd_idr=RATE)
    assert [c.session_date for c in store.read_contributions(pg, BOOK_ID)] == [S5, S5]
    assert store.apply_contributions(pg, BOOK_ID, S5) == D("625.0000")


def test_contributions_are_per_strategy(pg):
    store.record_contribution(pg, "A", due_date=DUE_SESSION, amount_idr=CONTRIB_IDR, usd_idr=RATE)
    assert len(store.read_contributions(pg, "A")) == 1
    assert store.read_contributions(pg, BOOK_ID) == ()
    assert store.read_contributions(pg, "SPY") == ()


def test_apply_contributions_without_a_paper_state_row_is_a_store_error(pg):
    store.record_contribution(pg, "A", due_date=DUE_SESSION, amount_idr=CONTRIB_IDR, usd_idr=RATE)
    with pytest.raises(store.StoreError):
        store.apply_contributions(pg, "A", S2)
```

`initial_cash_usd` is needed by `test_record_contribution_converts_as_day_zero_does`; the file
already imports from `seer_engine.sim` at `:22-32`, so add `initial_cash_usd` to that import list
(alphabetically it sits between `close_unpriced` and `size_picks`).

**Impact:** ten new tests, all DB-backed except the two calendar ones, which run without Postgres.
No existing test is edited.

---

### Step 9: `test_paper_book.py` — the deposit tests

**File:** `engine/tests/test_paper_book.py:48-55` (import) and after the last test at `:1067`
**Change:** add `deposit_book` to the `seer_engine.paper.book` import, then append two tests.
Note this file's `D` is **simkit's date helper** and `P` is the Decimal helper.
**Code:** the import becomes

```python
from seer_engine.paper.book import (
    BookNight,
    decide_book,
    deposit_book,
    last_rank_session,
    needs_kickoff,
    rank_basket,
    settle_book,
)
```

and append:

```python
# ============================================================== contributions


def _funded_book() -> Book:
    """A book holding 10 AAA at 15 with 100 in cash: equity 250, settled on 2026-09-30."""
    held = Position(
        symbol="AAA",
        shares=P("10"),
        mark=P("15"),
        entry_date=D("2026-09-28"),
        entry_price=P("14"),
        days_held=2,
        cost_usd=P("140.14"),
        income_usd=P("0"),
        stop=None,
        take=None,
    )
    return Book(cash=P("100"), equity=P("250"), positions=(held,), last_session=D("2026-09-30"))


def test_deposit_book_raises_cash_and_equity_and_moves_nothing_else():
    book = _funded_book()
    out = deposit_book(book, P("280.2533"))  # 5,000,000 IDR at 17,841
    assert out.cash == P("380.2533")
    assert out.equity == P("530.2533")
    assert out.positions == book.positions
    assert out.last_session == book.last_session
    assert book.cash == P("100") and book.equity == P("250")  # the input is untouched


def test_deposit_book_argument_checks():
    book = _funded_book()
    with pytest.raises(TypeError):
        deposit_book(book, 280.2533)
    with pytest.raises(TypeError):
        deposit_book("not a book", P("100"))
    with pytest.raises(ValueError):
        deposit_book(book, Decimal("0"))
    with pytest.raises(ValueError):
        deposit_book(book, Decimal("-100.0000"))
    with pytest.raises(ValueError):
        deposit_book(book, Decimal("100.00001"))


def test_a_deposit_on_a_non_decision_session_sits_as_cash_and_is_not_a_fill():
    """The idle week, in one session: the money arrives, raises equity, buys nothing."""
    funded = deposit_book(_funded_book(), P("280.2533"))
    night = settle_book(
        funded,
        D("2026-10-01"),
        {"AAA": Bar("AAA", D("2026-10-01"), P("15"), P("15"), P("15"), P("15"), 1_000_000)},
        None,  # not a decision session: nothing is ranked, so nothing is bought
        False,
        MONTHLY_HOLD,
        {},
        (),
        lambda _symbol: D("2026-10-01"),
    )
    assert night.snapshot.cash_usd == P("380.2533")     # the deposit is still cash
    assert night.snapshot.equity_usd == P("530.2533")   # 380.2533 + 10 x 15
    assert night.snapshot.invested_usd == P("150")
    assert night.fills == () and night.trades == ()     # a deposit is not a fill and not a trade
    assert night.book.positions[0].days_held == 3
```

**Impact:** three new tests. The "equals `run_book` field for field" group is unaffected: nothing it
calls changed, and `deposit_book` is never called on its path.

---

### Step 10: a deposit is not a return, on the paper comparison too

**Files:** `engine/src/seer_engine/paper/compare.py` (`:192` `_returns`, and `compare`'s signature);
`engine/src/seer_engine/commands/compare.py` (the impure edge that reads `equity_snapshots`)
**Change:** assigned by the reconciler from Handoff 3. `compare.py` is **pure** — no database, no
clock — and that stays true: the deposits arrive as an argument, exactly as the equity rows already
do.

**The defect, stated precisely.** `_returns` is
`equity[i] / equity[i - 1] - 1` over consecutive snapshot dates. On the session a deposit lands,
`equity[i]` includes it, so the "return" of that session is the strategy's return **plus the deposit
divided by yesterday's equity**. At the owner's scale that is a fabricated +50% on month 1, +33% on
month 2, and so on — it then flows into `_cagr`, `_sharpe` and `_max_drawdown`, which are the three
ranked figures on the leaderboard. Six roster entries all receive the same schedule on the same
session, so every one of them gets the same fabricated spike and the *ranking* survives; the
*numbers the owner reads* do not, and invariant 6 is about the numbers.

**The fix, in one line of arithmetic:** the deposit is removed from the ending equity before the
ratio is taken.

```python
def _returns(points: Sequence[Point], deposits: Mapping[date, float] = {}) -> tuple[float, ...]:
    """Session returns over consecutive points, with external deposits removed.

    ``equity[i]`` includes any money the owner added on that session, and money arriving is not a
    return -- a book that earns nothing and is handed 5,000,000 IDR would otherwise report the
    deposit as performance (plan set Decision D4, measured in phase 7 as +600.9% over a year).
    So the credited dollars are taken out of the ending equity before the ratio:
    ``(equity[i] - deposit[i]) / equity[i - 1] - 1``.

    ``deposits`` maps a session date to the dollars credited at the OPEN of that session
    (``paper.store.read_contributions``, whose ``session_date`` is exactly this key, and whose
    ``amount_usd`` is exactly this value). Empty -- the default, and every strategy that has
    received nothing -- leaves every number bit-for-bit as it was.
    """
    out: list[float] = []
    for i in range(1, len(points)):
        day, equity = points[i]
        out.append((equity - deposits.get(day, 0.0)) / points[i - 1][1] - 1.0)
    return tuple(out)
```

`_cagr` is the other figure that reads equity endpoints directly. It is **not** changed here: with
deposits it is the wrong question, and the right one is phase 7's money-weighted return, which this
phase does not own. Instead `compare` carries, per row, the total deposited over the window, and
`_cagr`'s value is suppressed (`None`) for any strategy whose window received one — `None` is
already a value every caller of `_cagr` handles (`"the span is zero calendar days"`), and reporting
nothing beats reporting a number that counts the owner's own money as growth. Phase 7's
`backtest.metrics.money_weighted_return` is the eventual replacement; record it as a follow-up
rather than importing `backtest` into a pure `paper` module here.

`compare(...)` gains a trailing defaulted parameter
`deposits: Mapping[str, Mapping[date, float]] = {}` — strategy id to its session-dated dollars —
threaded to `_returns` and summed onto each row. Every existing caller passes nothing and is
unchanged.

**`engine/src/seer_engine/commands/compare.py`** is the one impure edge and does the read:

```python
deposits = {
    sid: {c.session_date: float(c.amount_usd) for c in store.read_contributions(conn, sid) if c.applied}
    for sid in strategy_ids
}
```

`if c.applied` matters: an accrued-but-not-yet-credited row has not reached any equity snapshot, so
subtracting it would under-report. **This phase's** `store.apply_contributions` (Step 4) is what
sets it, and phase 12's Step 7c is what calls it from the night.

**Tests** — append to `engine/tests/test_paper_compare.py` (or the file that covers `compare.py` in
the tree; it is not otherwise touched by this phase):

```python
def test_a_deposit_is_not_a_return():
    # 1000 -> 1312.50 on the session a 312.50 deposit lands: the strategy returned 0%, not +31%.
    points = ((D("2026-09-28"), 1000.0), (D("2026-09-29"), 1312.50))
    assert _returns(points) == (0.3125,)                                   # today: wrong
    assert _returns(points, {D("2026-09-29"): 312.50}) == (0.0,)           # with the deposit out
    # And an unfunded curve is untouched, which is every strategy on the roster today.
    assert _returns(points, {}) == _returns(points)
```

**Impact:** both files are additive-with-defaults, so every existing `compare` call and every test
in `test_paper_compare.py` is unchanged. Inert today: zero sessions stepped, no contribution row,
so `deposits` is empty for every strategy and every ranked figure is bit-identical.

---

## Verification

**Postgres (DB tests need it):**

```
docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
```

**Build / lint:**

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild && PYTHONPATH=engine/src python -c "import seer_engine.paper.store, seer_engine.paper.book"
```

**Tests** (from the worktree root; `PYTHONPATH` is **required** — without it pytest silently tests
the main checkout instead of this branch; never pass `-o addopts`):

```
PYTHONPATH=engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  python -m pytest engine/tests/test_paper_store.py engine/tests/test_paper_book.py \
  engine/tests/test_strategy_purity.py -q
```

then the whole suite:

```
PYTHONPATH=engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  python -m pytest engine/tests -q -n auto
```

`main` is RED for two known reasons (handover §6), neither of them this phase's. The check is that
this phase adds **no new** failure, not that the count is zero.

**Manual check:**
1. The migration applies cleanly and is additive:
   `PYTHONPATH=engine/src python -m pytest engine/tests/test_paper_store.py -q -k contribution`
   exercises it through the `pg` fixture, which applies every `db/migrations/*.sql` in name order.
2. `ls db/migrations/` shows `016_contributions.sql` and **no** `017_*` — phase 12 owns 017.
3. `grep -rn "paper_state" db/migrations/016_contributions.sql` returns nothing: no existing row
   is read or rewritten, which is what makes landing this while paper is paused safe.
4. The frozen state is undisturbed. Nothing in this phase writes `paper_state`, `book_targets`,
   `orders` or `equity_snapshots`, so `last_session = 2026-10-06`, `pending_session = 2026-10-07`,
   the 80 `book_targets` rows, the 4 `orders` rows and the 560.5067 USD starting snapshots all
   stay exactly as they are.

**Exit criteria:**
- `paper_contributions` exists; a deposit can be written down in IDR with its rate and its dollars,
  and `store.read_contributions` hands back the **dated** cashflows phase 7 needs.
- `store.apply_contributions(conn, id, session)` returns the dollars landing on that session,
  stamps them applied, credits nothing twice, and refuses a session already stepped.
- `paper.book.deposit_book` raises a book's **cash and equity by the same amount** and produces no
  fill and no trade; `settle_book` carries the deposit into the session's snapshot with
  `invested_usd` unchanged. **Equity, not cash alone, is load-bearing and is asserted:** both engines
  size from the last snapshot's equity (`sim/sizing.py:137` `slot_budget = q(portfolio.equity /
  SLOTS)`, `sim/book.py:536` `equity = book.equity`), so crediting cash alone would leave every
  deposit permanently under-deployed. The same rule binds the two one-line adapters phase 12 writes
  for `sim.Portfolio` and `BenchmarkState` (Handoff 1), and phase 12's exit criteria assert it there.
- **(Step 10)** `paper.compare._returns` removes a session's deposit before taking the ratio, so a
  book that earns nothing and receives 312.50 USD reports a 0% session return, not +31%; with no
  deposits every ranked figure is bit-identical to today's.
- The engine suite reports no failure that was not already failing on `main`.
- `PAPER_PAUSED` is still `'true'` and no roster entry, started or otherwise, was edited.
- `git diff engine/src/seer_engine/paper/store.py` shows **no** change at or near `:1127`
  (`load_benchmark` is phase 12's region — see Interface Contract).

---

## Handoffs

**1. One call site turns this on — `engine/src/seer_engine/commands/paper.py`. ASSIGNED: PHASE 12**
(index Decision **D10**, taken after this plan was dispatched; written out verbatim as phase 12's
Step 7c). The capability is complete and tested here, but nothing calls it in production until the
night does. `commands/paper.py` is wanted by phases 3, 4, 6 and 12, two of which run concurrently in
wave 1, so D10 gives the whole file to phase 12 — which is also the phase whose exit criteria say the
successor entries must carry the contribution schedule *from their first night*. The work, named
exactly:

- In `_step_book` (`commands/paper.py:787`), at the top of the `for s in sessions:` loop, before
  `settle_book`:
  ```python
  credited = store.apply_contributions(conn, e.id, s)
  if credited:
      book = deposit_book(book, credited)
  ```
  with `deposit_book` added to the `seer_engine.paper.book` import.
- The same two lines in the bracket loop (`_step_bracket`) and the benchmark loop
  (`_step_benchmark`), with the **engine-appropriate adapter**:
  ```python
  # sim.Portfolio (bracket) -- CASH AND EQUITY, both:
  pf = replace(pf, cash=pf.cash + credited, equity=pf.equity + credited)
  # paper.benchmark.BenchmarkState -- the same two fields:
  bench = replace(bench, cash=bench.cash + credited, equity=bench.equity + credited)
  ```
  **Equity, not cash alone — this is the load-bearing half.** Measured: both engines size from the
  last snapshot's equity (`sim/sizing.py:137` `slot_budget = q(portfolio.equity / SLOTS)`;
  `sim/book.py:536` `equity = book.equity`), so a deposit credited to cash alone would leave the
  money permanently under-deployed — the book would hold it and never size against it.
  `deposit_book` above already does both; the two one-line adapters must match it.
- Once per night, per entry, before the session loop:
  ```python
  store.accrue_contributions(
      conn, e.id,
      OWNER_MONTHLY.dates_in(paper_start, sessions[-1]),
      OWNER_MONTHLY.amount_idr,
      through=sessions[-1],
      usd_idr_on=view.usd_idr_on,
  )
  ```
  This is the one place the schedule object from `sim/contributions.py` is read.

**2. `engine/src/seer_engine/paper/replay.py` must feed the same deposits to the replay — R3, and a
`paper check` failure the first night after a deposit if it is not done. ASSIGNED: PHASE 12** (D10). `expected_bracket`
(`:283`), `expected_book` (`:332`) and `expected_benchmark` (`:411`) each rebuild the expected
record from `cash0 = initial_cash_usd(PAPER_INITIAL_IDR, head.usd_idr)` and a one-shot
`run_rules` / `buy_and_hold`. Once a contribution lands, the stored record holds money the replay
does not, and `judge` reports a mismatch on every session after it. The fix is to carry **this
phase's stored rows** onto `PaperHead` and hand the runner `(session_date, amount_usd)` pairs — the
**record, not the schedule** (index Decision **D18**). That distinction is this phase's to insist
on: D6a freezes each deposit's rate on its landing session precisely so a backfilled `fx_rates`
cannot move a stepped book's history, and re-deriving those dollars from `OWNER_MONTHLY` at one
rate would undo it. Phase 5's `contributions=` accepts both forms for exactly this reason
(`sim.contributions.Contributions` / `credit_for`), and phase 7's `buy_and_hold` already takes the
dated form. **Inert today:** zero sessions stepped, paper
paused, no contribution row exists, so nothing fails until the owner resumes. It is phase 12's
Step 7d, alongside handoff 1 — settled, not suggested.

**3. `engine/src/seer_engine/paper/compare.py` reads returns straight off equity — R3, phase 7's
question in paper's clothing. ASSIGNED BY THE RECONCILER TO THIS PHASE. See Step 10 below.**
`_returns` (`:192`), `_cagr` (`:210`), `_sharpe` (`:219`) and `_max_drawdown` (`:197`) all treat a
rise in `equity_snapshots` as a return. A deposit raises equity without being one, so every one of
those four numbers is wrong the first month a contribution lands — exactly the failure Decision D4
names.

The reconciler's reasoning, recorded so it is not re-litigated: the index's **Scope** says the
contribution model is in scope *"in full — schedule, backtest, paper, money-weighted return and
dollar-cost-averaged benchmark together, because a half-built one is worse than none (D4)"*, and
paper's own return measure is the "paper" half of that sentence (rung 4). It is assigned **here**
rather than to phase 7 or 12 because this phase owns the data it needs
(`store.read_contributions`), owns the deposit path whose double-counting is the bug, and has the
fixtures to test it; phase 7 is `engine.backtest`/`engine.lab` and never touches `paper/`, and
phase 12 is already carrying the whole wiring layer under D10.

It stays **inert while paused** — zero sessions stepped, no contribution row exists — so it is a
correctness fix landing ahead of the first night that would need it, which is the whole shape of
this plan set.

**4. `engine/src/seer_engine/commands/paper_check.py:200` publishes `"initial_cash":
state.initial_cash_usd`. ASSIGNED: PHASE 12**, travelling with handoff 2. Once deposits exist that
field is "capital on day 0", not "capital in", and whatever reads it should say which. One line.

**5. `web/` reads nothing of this yet — phase 10 may want to.** Phase 10 derives the owner's real
wallet from the same schedule and the Sean ledger, deliberately *not* from paper. `paper_contributions`
is per-paper-strategy and is **not** the owner's wallet: it is six parallel 10,000,000 IDR books
each receiving the same schedule. Phase 10 should keep deriving cash from `sim/contributions.py`
plus `sean_orders`, and should not read this table. Flagged because phase 10's brief asks to be told
if a new table the site could read appears — it does, and the answer is "do not read it".

**6. Not done, deliberately:** no `initial_cash_usd` writer, no running total anywhere, no change
to `paper_state`'s shape, no new engine parameter, no roster entry, no change to
`PAPER_PAUSED`. Each of those belongs to another phase or to no phase.

---

## Assumptions

1. **Phase 5 has landed.** This plan's draft guessed the names `OWNER_SCHEDULE` and `due_dates`; the
   reconciler replaced every one of them with what phase 5 actually defines. **These are now facts
   read off `phase-5.md`, not assumptions:**
   - `seer_engine.sim.contributions.OWNER_MONTHLY` — the module-level instance,
     `ContributionSchedule(amount_idr=Decimal("5000000"), day_of_month=25)`;
   - `OWNER_MONTHLY.dates_in(first: date, last: date) -> tuple[date, ...]` — every contribution date
     in `[first, last]`, **both ends inclusive**, ascending. (Phase 5 also has
     `due(after, through)`, which is *exclusive* of `after`; this phase wants `dates_in`, because it
     is listing a window's schedule, not asking a per-session question.)
   - `OWNER_MONTHLY.amount_idr -> Decimal` — `Decimal("5000000")`.

   **Only `engine/tests/test_paper_store.py` imports it** (Step 8's second test), and Handoff 1's
   snippet names it. `paper/store.py` and `paper/book.py` import nothing from that module by
   design: they take plain dates and a plain `Decimal`. `_exact("amount_idr", ..., IDR_QUANTUM)`
   accepts `Decimal("5000000")` (`.quantize(Decimal("0.01"))` is equal); a value with three or more
   decimals it would reject, and phase 5's has none.

2. **Phase 4 has landed** (wave W1) and `sim/model.initial_cash_usd` is unchanged by it. Phase 4's
   file list names `buy_cost` and `sell_proceeds` in `sim/model.py`, not `initial_cash_usd`;
   `sim/costs.py` is untouchable by invariant 5. If phase 4 did move `initial_cash_usd`, only
   Step 2's import line changes.

3. **Phase 3 has landed** and `paper/benchmark.BenchmarkState` still exposes a cash field with a
   `replace`-able name. Nothing here imports it; it matters only to Handoff 1.

4. **The frozen production state is as measured** (2026-10-08, read-only against Neon):
   `paper_state.last_session = 2026-10-06`, `pending_session = 2026-10-07`, 80 `book_targets` rows
   and 4 `orders` rows for 2026-10-07, starting `equity_snapshots` at 560.5067 USD. That figure
   pins the start rate: `initial_cash_usd(10_000_000, 17841.0000) = 560.5067` exactly, which is why
   `17841.0000` appears in the tests as a real rate rather than an invented one
   (`PYTHONPATH=engine/src python -c "from decimal import Decimal; from
   seer_engine.sim.model import initial_cash_usd; print(initial_cash_usd(Decimal('10000000'),
   Decimal('17841.0000')))"`).

---

## Rollback

This phase is one commit on `feature/gotrade-fee-rebuild`; `git revert` it. It is additive in every
file it touches, so reverting restores the tree exactly: no signature, no query and no existing
function changed, and `git revert` removes the migration file along with the code.

**If the migration has already been applied to a database**, `git revert` leaves the table behind,
empty and unreferenced. `DROP TABLE IF EXISTS paper_contributions;` plus
`DELETE FROM schema_migrations WHERE name = '016_contributions.sql';` removes it, and that is safe
unconditionally **only while the table is empty** — which it is for as long as `PAPER_PAUSED` is
`'true'` and no night has run, because nothing but the paper night writes a row. Once rows exist
they are the record of real deposits; drop nothing and revert the code only.

**Do not revert this phase alone.** Decisions D4: phases 5, 6 and 7 are one unit. Contributions
without the money-weighted measure make every CAGR in the system a flattering number, which is
strictly worse than having no contributions at all. Revert all three or none.
