# Phase 2: Retire and activate: the paper night honours roster lifecycle

**Plan set:** `ROSTER_PROMOTION_PIPELINE_PLAN.md`
**Analysis:** `20261005-165054-XGER_code_analyzer.md`
**Satisfies:** R2 — replacing a horseman must not require editing engine code; phase 1 made the
roster *readable* from data, this phase makes it *changeable over time* (retire, activate)
without rewriting one row of history.
**Depends on:** Phase 1
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/commands` (with the write side of `engine/src/seer_engine/paper/store.py`)

## Runtime preamble

Every phase plan opens with this block and every command in this set assumes it.

```bash
export SEER_WT=/home/miftah/.worktrees/seer/roster-promotion-pipeline
export SEER_PY=/home/miftah/seer/engine/.venv/bin/python
export PYTHONPATH=$SEER_WT/engine/src                        # wins over the editable .pth
export SEER_MAIN=/home/miftah/seer
export SEER_ENV_FILE=$SEER_MAIN/.env.local-train             # ABSOLUTE, always
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
cd "$SEER_WT"
"$SEER_PY" -c 'import seer_engine, pathlib; print(pathlib.Path(seer_engine.__file__).resolve())'
# must print $SEER_WT/engine/src/seer_engine/__init__.py
```

Measured on the `fundamental-panel-coverage` set that landed today: the worktree has **no venv of
its own**, `/home/miftah/seer/engine/.venv` is an *editable* install pointing at
`/home/miftah/seer/engine/src`, and `engine/pyproject.toml` sets `testpaths` but no `pythonpath`.
Without `PYTHONPATH` a phase can edit this worktree and watch `main`'s code pass the tests.

For `web/`: `cd $SEER_WT/web && npm ci` once, then `npm test` and `npm run build`.

---

## Goal

After this phase the paper night reads its roster from the database rather than from the compiled
`roster.ROSTER` tuple, and honours three lifecycle states that did not exist before: a
`status='retired'` strategy is skipped entirely (no orders, no equity snapshot, no `paper_state`
step) and carries a `paper_end` equal to the last session it actually traded; a `status='active'`
strategy with no `paper_start` starts on the next night exactly as a new entry does today, through
`store.freeze_spec`; and a roster row whose object cannot be resolved stops the night with a named
error instead of vanishing from the board. Nothing is deleted and nothing is mutated:
`store.check_digest`'s `SpecMismatch` refusal stays live on every active, started strategy and is
still tested.

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** nothing. No symbol, no column, no row, no file.

**Renames:** nothing.

**Creates:**

- `seer_engine.commands.paper.Retired` — a frozen dataclass, `(entry, paper_end, stamp)`
  (`commands/paper.py`, inserted before `NightPlan`)
- `seer_engine.paper.store.retire(conn, strategy_id) -> date | None`
  (`paper/store.py`, after `check_digest`) — **this is the function phase 5 must call**
- `seer_engine.paper.store.set_paper_end(conn, strategy_id, paper_end) -> None`
  (`paper/store.py`, after `retire`)

**Signature changes:**

- `commands.paper.NightPlan` gains a third field: `NightPlan(start, step)` ->
  `NightPlan(start, step, retired)`. `start` and `step` keep their current types and meaning.
  `NightPlan.empty()` keeps its signature and widens its meaning (see Step 2).
- `commands.paper._night(conn, rd, plan, run_id)` keeps its signature; its trading body moves
  verbatim into a new private `commands.paper._trade(conn, rd, plan)`.
- `commands.paper_check.check(conn)` keeps its signature; it now resolves its entries from the
  `strategies` rows instead of passing `roster.ROSTER` to `_check`.
- `commands.paper.plan_night(entries, rows, states, rd)` keeps its signature exactly. It is still
  pure and still takes the entries from its caller.

**Requires (from earlier phases) — Phase 1. Reconciled against phase 1's shipped Interface
Contract; these are the real names, not guesses:**

1. `store.StrategyRow` carries `sub`, `icon`, `status: str`, `paper_end: date | None`,
   `promoted_from: str | None`, `object_name: str | None`, `registry_id: str | None`,
   `gate_note: str | None` and `gate_applicable: bool`, populated by `store.read_strategies`,
   `store.read_roster_rows` and `store.read_strategy` from `006_roster.sql`'s columns. I read
   `row.status` and `row.paper_end`; I never write `promoted_from`.
2. `store.read_roster_rows(conn) -> tuple[StrategyRow, ...]` — the roster rows, i.e. every
   `strategies` row with `engine IS NOT NULL`, `ORDER BY sort, id`. **This is the query this
   phase uses, not `read_strategies`**: `read_strategies` returns legacy display rows with a NULL
   `engine` too, and `roster.from_rows` raises `BadRosterRow` on those (correctly — it refuses to
   guess). Retired rows ARE returned; only the night drops them.
3. `roster.from_rows(rows: Iterable[roster.Row]) -> tuple[RosterEntry, ...]` — pure, no database,
   no clock; `store.StrategyRow` satisfies `roster.Row` structurally. One `RosterEntry` per row,
   sorted by `(sort, id)`, which is the order `read_roster_rows` already returns. **It returns an
   entry for a retired row too**: retirement is a skip decided by the night, never a reason to
   stop resolving an object, and letting retirement hide an unresolvable name would be exactly
   the confusion invariant 9 forbids. `roster.from_rows(store.read_roster_rows(conn))` is the
   whole data path.
4. **`roster.from_rows` resolves a row that has never been frozen** — `paper_start IS NULL` and
   `params = '{}'::jsonb`, which is every row in a freshly migrated database. **Settled:** phase 1
   put the resolver key in its own column, `strategies.object_name` (migration 006, backfilled on
   the five existing rows), *not* in `params->'spec'->>'object'`. So an unfrozen row resolves, and
   `test_paper_command.py`'s `test_first_night_starts_every_roster_strategy`,
   `test_paper_check.py:170` and every row phase 5's `promote` inserts all work. Nothing in this
   phase reads `params->'spec'->>'object'` for resolution.
5. An unresolvable row raises `roster.UnknownObject` (a `roster.RosterError`, which is a
   `LookupError`) whose message contains the offending strategy id **and the unresolved object
   name** (invariant 9); a bad `rules_id` raises `roster.UnknownRules` and any other malformed
   row raises `roster.BadRosterRow`. I do not catch any of them —
   `paper.execute`'s existing `except Exception` turns it into a failed paper step, and
   `_error_text` prefixes it with the class name, so the stored `runs.paper_error` reads
   `<NamedError>: ...`. My test asserts on the message, not on the class.
6. `roster.ROSTER`, `roster.ROSTER_IDS`, `roster.entry`, `roster.strategy_params`,
   `roster.spec`/`spec_text`/`spec_digest` keep working unchanged (phase 1 recomputes `ROSTER` as
   `from_rows(SEED_ROWS)`; its value is element-wise identical). `RosterEntry` gains two trailing
   defaulted fields (`status`, `paper_end`) and nothing else moves.
   `commands/veto.py:327` and `engine/tests/test_paper_c.py` still use the compiled tuple and
   this phase does not move them.
7. `roster.active(entries)` exists and filters to `status == "active"`. **This phase does not use
   it**: `plan_night` reads `row.status` directly, because it must also decide whether tonight
   owes the entry a `paper_end` stamp, which `active()` cannot express. `active()` stays phase 1's
   exported filter for every other caller.

**Requires (from this phase) — Phase 5, read this literally:**

`promote --retire <id>` must call **`store.retire(conn, id)`** inside the same transaction as its
`INSERT INTO strategies`. It takes the status change *and* the `paper_end` stamp together, so the
swap is atomic and the board never shows five active horsemen or three. It writes nothing but
`strategies.status` and `strategies.paper_end`; it deletes nothing (invariant 4). It returns the
stamped `paper_end` (`None` when the strategy never traded). Re-retiring an already-retired row is
a no-op that returns the stored `paper_end`, so an interrupted swap can be re-run; a missing row
is a `store.StoreError`. Phase 5 must **not** write `status` or `paper_end` with its own SQL.

**Leaves alone (owned by others):**

- `engine/src/seer_engine/paper/roster.py` — Phase 1, including `MAX_LOOKBACK_BARS`; see Handoffs.
- `db/migrations/*.sql` — Phase 1 (006) and Phase 6 (007). This phase adds no migration.
- `engine/src/seer_engine/paper/store.py`'s **read** side (`StrategyRow`, `_STRATEGY_SQL`,
  `_strategy`, `read_strategies`, `read_strategy`) — Phase 1.
- `engine/src/seer_engine/paper/compare.py` — Phase 3.
- `web/` — Phase 4.
- `engine/src/seer_engine/commands/promote.py`, `engine/src/seer_engine/lab/store.py` — Phase 5.
- The `FND` roster entry and `strategies/f_fundamental.py` — Phase 6.
- `engine/src/seer_engine/backtest/registry.py` — **never** (index decision D1).
- `engine/tests/test_paper_roster.py` — Phase 1. The pinned digests are not touched here.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/paper/store.py` | modify | add `retire` and `set_paper_end` after `check_digest` (:200); update the module docstring's roster-row bullet (:5-7) |
| `engine/src/seer_engine/commands/paper.py` | modify | module docstring (:9-11), add `Retired` and widen `NightPlan` (:80-92), source the entries from the rows and log the skips in `execute` (:139-157), the retired branch in `plan_night` (:173-214), split `_night` into `_night` + `_trade` (:305-341) |
| `engine/src/seer_engine/commands/paper_check.py` | modify | `check` resolves entries from the `strategies` rows (:100-104); docstring line :5 |
| `engine/tests/test_paper_command.py` | modify | +6 tests and two helpers after `snaps` (:233) |
| `engine/tests/test_paper_store.py` | modify | +4 tests after `test_freeze_spec_...` (:84) |
| `engine/tests/test_paper_check.py` | modify | +1 test |

---

## Implementation Steps

### Step 1: `store.retire` and `store.set_paper_end` — the only two writers of the lifecycle columns

**File:** `engine/src/seer_engine/paper/store.py:200` (immediately after `check_digest`, before the
`# ---- paper_state` banner at :203)

**Change:** add the two write-side functions. `retire` is what a human and phase 5's `promote`
call; `set_paper_end` is what the paper night calls to repair a retirement taken by hand SQL (the
index's own Rollback section writes exactly such SQL). Neither touches a history table.

**Code:**

```python
def retire(conn: psycopg.Connection, strategy_id: str) -> date | None:
    """Retire ``strategy_id``: ``status = 'retired'`` and ``paper_end`` = the last session it
    actually traded.

    The last session actually traded is ``paper_state.last_session``: once the status is
    ``retired`` the paper night steps the strategy no further, so that row is final. A strategy
    that never started (no ``paper_state``) retires with ``paper_end`` NULL.

    Retirement is a status change and a date, **nothing else** (plan invariant 4): no
    ``equity_snapshots``, ``orders``, ``book_positions``, ``book_targets``, ``book_fills``,
    ``book_trades`` or ``paper_state`` row is read for anything but the date, and none is written
    or deleted. The strategy keeps its whole track record and stays on the leaderboard.

    Returns the stamped ``paper_end``. A row that is already retired is left exactly as it is and
    its stored ``paper_end`` is returned, so an interrupted swap can be re-run; a missing row is a
    ``StoreError``. The caller's transaction decides (``promote`` retires and inserts the
    replacement in one transaction, so the board never shows two rosters).
    """
    row = read_strategy(conn, strategy_id)
    if row is None:
        raise StoreError(f"no strategies row {strategy_id!r}")
    if row.status == "retired":
        return row.paper_end
    state = read_paper_state(conn, strategy_id)
    paper_end = None if state is None else state.last_session
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE strategies SET status = 'retired', paper_end = %s WHERE id = %s AND status = 'active'",
            (paper_end, strategy_id),
        )
        _one_row(cur, f"retire {strategy_id}")
    return paper_end


def set_paper_end(conn: psycopg.Connection, strategy_id: str, paper_end: date) -> None:
    """Stamp ``paper_end`` on a retired strategy that has none.

    ``retire`` stamps it already; this is the repair for a retirement taken by hand
    (``UPDATE strategies SET status = 'retired' ...``, as the plan index's Rollback writes it).
    The paper night calls it on the first night after such a retirement, inside the night's own
    transaction. Only a retired row whose ``paper_end`` is still NULL is written; an active row,
    a missing row or one already stamped is a ``StoreError``, because each of those means the
    caller's picture of the lifecycle is wrong.
    """
    _session("paper_end", paper_end)
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE strategies SET paper_end = %s WHERE id = %s AND status = 'retired' AND paper_end IS NULL",
            (paper_end, strategy_id),
        )
        _one_row(cur, f"paper_end {strategy_id}")
```

Then update the module docstring's roster-row bullet so the file still describes itself. Replace
`engine/src/seer_engine/paper/store.py:5-7`:

```
- Roster rows: ``strategies`` read; the frozen spec (C2) and ``paper_start`` written once;
  the stored digest checked against the code's.
```

with:

```
- Roster rows: ``strategies`` read; the frozen spec (C2) and ``paper_start`` written once;
  the stored digest checked against the code's. The lifecycle columns (006) have exactly two
  writers here: ``retire`` (``status`` + ``paper_end``, what ``promote --retire`` calls) and
  ``set_paper_end`` (the night's repair of a hand-written retirement). Retiring deletes nothing.
```

**Impact:** `store` gains two functions and no behaviour changes for any existing caller.
`_session` rejects a non-session `paper_end`, which cannot happen from `paper_state.last_session`
but keeps the invariant local. `retire` depends on phase 1's `StrategyRow.status` / `.paper_end`.

---

### Step 2: `Retired` and the widened `NightPlan`

**File:** `engine/src/seer_engine/commands/paper.py:80-92` (replacing the whole `NightPlan` block)

**Change:** the night plan grows a third list. A retired entry is not a *kind of* start or step —
it is the deliberate absence of both — so it gets its own value with its own name, and the name
says "retired", never "skipped", so a reader can never confuse it with the hard error of an
unresolvable entry.

**Code:**

```python
@dataclass(frozen=True)
class Retired:
    """A ``status='retired'`` roster entry: tonight it takes no decisions at all.

    No orders, no equity snapshot, no ``paper_state`` step, and no row of its history is touched
    (plan invariant 4) — it keeps every snapshot, order, book row and trade it ever wrote.

    ``paper_end`` is the last session it actually traded (``paper_state.last_session``), or None
    when it never started. ``stamp`` is True when the stored ``strategies.paper_end`` is still
    NULL and tonight must write it: that is the repair for a retirement taken by hand SQL, since
    ``store.retire`` stamps it at retirement time.
    """

    entry: RosterEntry
    paper_end: date | None
    stamp: bool


@dataclass(frozen=True)
class NightPlan:
    """What tonight does.

    ``start``: active roster entries with no paper state yet (they start tonight).
    ``step``: (entry, its state) for active entries whose last session is before rd.data_date.
    ``retired``: every retired entry, with the ``paper_end`` it has or needs. They trade nothing.
    """

    start: tuple[RosterEntry, ...]
    step: tuple[tuple[RosterEntry, PaperState], ...]
    retired: tuple[Retired, ...] = ()

    def empty(self) -> bool:
        """Nothing to write tonight.

        A retired entry keeps the night awake only while its ``paper_end`` is unstamped: once
        stamped it costs nothing every night thereafter, so a roster that is all-retired settles
        into the ordinary no-op.
        """
        return not self.start and not self.step and not any(r.stamp for r in self.retired)
```

**Impact:** `NightPlan(start=..., step=...)` keeps working (the new field defaults to `()`), so no
existing construction site breaks. `empty()` is now also True for a night whose only retired
entries are already stamped.

---

### Step 3: `plan_night` sorts active from retired, and refuses an unknown status

**File:** `engine/src/seer_engine/commands/paper.py:173-214` (replacing the whole function)

**Change:** the retired branch comes first and `continue`s before `check_digest`: a retired
strategy takes no decision, so there is no decision to refuse. The refusal stays live and
reachable on every **active, started** entry, which is every entry the night actually trades — and
`test_changed_frozen_spec_is_refused` keeps exercising it unchanged. An unknown `status` is a hard
`PaperError`, not a silent fall-through to active: a value the night does not understand must stop
the night, in the same spirit as invariant 9.

**Code:**

```python
def plan_night(
    entries: Sequence[RosterEntry],
    rows: Mapping[str, StrategyRow],
    states: Mapping[str, PaperState],
    rd: dates.RunDates,
) -> NightPlan:
    """Which entries start tonight, which step, and which are retired, after the frozen-spec checks.

    A ``status='retired'`` entry is a **deliberate skip**: it is collected into ``NightPlan.retired``
    and takes no decision, no snapshot and no ``paper_state`` step. It is not an error, and it is
    not the same thing as an entry whose object cannot be resolved — that one never reaches this
    function, because ``roster.from_rows`` raises before the plan exists and the night stops
    (plan invariant 9).

    Raises ``store.SpecMismatch`` when an **active** entry's set ``paper_start`` holds a spec
    digest other than the code's (handover D4: a changed strategy needs a new id). Raises
    PaperError when an entry has no ``strategies`` row, carries a status this night does not
    understand, has ``paper_start`` but no paper state (its clock must be reset first), has paper
    state but no ``paper_start``, or when the stored pending session is not the session after the
    last one stepped.
    """
    start: list[RosterEntry] = []
    step: list[tuple[RosterEntry, PaperState]] = []
    retired: list[Retired] = []
    for e in entries:
        row = rows.get(e.id)
        if row is None:
            raise PaperError(f"strategies row {e.id!r} is missing; run `migrate` (003) first")
        if row.status not in ("active", "retired"):
            raise PaperError(
                f"strategy {e.id!r} has status {row.status!r}; the paper night understands only "
                f"'active' and 'retired'"
            )
        state = states.get(e.id)
        if row.status == "retired":
            last_traded = None if state is None else state.last_session
            retired.append(
                Retired(
                    entry=e,
                    paper_end=row.paper_end if row.paper_end is not None else last_traded,
                    stamp=row.paper_end is None and last_traded is not None,
                )
            )
            continue
        store.check_digest(row, roster.strategy_params(e)["digest"])
        if state is None:
            if row.paper_start is not None:
                raise PaperError(
                    f"strategy {e.id!r} has paper_start {row.paper_start} but no paper_state; reset its "
                    f"paper clock (paper runbook) before it can start"
                )
            start.append(e)
            continue
        if row.paper_start is None:
            raise PaperError(f"strategy {e.id!r} has paper state but no paper_start")
        if state.last_session >= rd.data_date:
            continue
        expected = dates.next_session(state.last_session)
        if state.pending_session != expected:
            raise PaperError(
                f"strategy {e.id!r}: pending session {state.pending_session} is not the session "
                f"after its last one ({state.last_session} -> {expected})"
            )
        step.append((e, state))
    return NightPlan(start=tuple(start), step=tuple(step), retired=tuple(retired))
```

**Impact:** a strategy added as `active` with no `paper_start` still falls into `start` through the
untouched `state is None and row.paper_start is None` branch — that is the whole of the "starts on
the next night exactly as a new entry does today" requirement, and it needed no new code once the
entries come from the rows. Retired entries never reach `check_digest`, `freeze_spec`,
`init_paper_state` or any engine step.

---

### Step 4: `execute` reads the roster from the database and names the two skips apart in the log

**File:** `engine/src/seer_engine/commands/paper.py:139-157` (replacing the body from
`try:` through the `with db.transaction(conn, dry_run): _night(...)` pair)

**Change:** the entries come from `store.read_roster_rows` through phase 1's resolver instead of
from the compiled `roster.ROSTER`. That one substitution is what makes a roster change a data
change. `read_roster_rows` (not `read_strategies`) is the right query: it is the one that filters
to `engine IS NOT NULL`, which is exactly the set `roster.from_rows` can build, and it already
returns `ORDER BY sort, id`. The retired entries are logged before the `empty()` return so a quiet
night still says why a strategy is missing from the board's activity.

**Code — the replacement for `execute`'s inner block (lines 139-157 become):**

```python
    try:
        try:
            strategy_rows = store.read_roster_rows(conn)
            # The roster is data (phase 1). An entry whose object cannot be resolved raises here,
            # by name, and the whole night stops (plan invariant 9) -- that is NOT the deliberate
            # skip a retired entry gets below, and the two never share a code path or a log line.
            entries = roster.from_rows(strategy_rows)
            rows = {row.id: row for row in strategy_rows}
            states: dict[str, PaperState] = {}
            for e in entries:
                state = store.read_paper_state(conn, e.id)
                if state is not None:
                    states[e.id] = state
        finally:
            conn.rollback()
        plan = plan_night(entries, rows, states, rd)
        for r in plan.retired:
            log.info(
                "%s: retired; no orders, no equity snapshot, no paper_state step. paper_end %s%s",
                r.entry.id,
                "-" if r.paper_end is None else r.paper_end,
                " (stamped tonight)" if r.stamp else "",
            )
        if plan.empty():
            log.info(
                "every active roster strategy is stepped through %s; nothing to do", rd.data_date
            )
            return 0

        with db.transaction(conn, dry_run):
            runs.start_paper(conn, run_id)
        with db.transaction(conn, dry_run):
            _night(conn, rd, plan, run_id)
    except Exception as e:  # noqa: BLE001 - every failure must become a failed paper step
        message = _error_text(e)
        conn.rollback()
        log.error("paper failed for session %s: %s", rd.session_date, message)
        if dry_run:
            log.info("dry-run: would mark the paper step failed")
            return 1
        with db.transaction(conn, False):
            runs.fail_paper(conn, run_id, message)
        return 1
    if dry_run:
        log.info("dry-run: rolled back; nothing written")
    return 0
```

**Impact:** `commands/paper.py:141`'s `store.read_strategies(conn)` call is replaced by
`store.read_roster_rows(conn)` and the separate `roster.ROSTER` iteration at `:143`/`:149`
disappears — phase 1's handoff asked for exactly that collapse, and this is it.
`roster.ROSTER` is no longer referenced by `commands/paper.py`; the import of `roster`
stays, for `roster.strategy_params` in `plan_night` and `_start`. The unresolvable-entry error is
raised inside the existing `try`, so it rolls back, logs `paper failed for session ...: <Named
error>: ...` and writes `runs.paper_error` — a hard, named stop, never a gap in an equity curve.

---

### Step 5: `_night` stamps `paper_end`, then trades — and trades nothing when there is nothing to trade

**File:** `engine/src/seer_engine/commands/paper.py:305-341` (replacing the whole `_night`
function; `_check_window` at :295 is untouched)

**Change:** `_night` becomes the transaction's orchestrator. The `paper_end` stamps come first and
cost no market load; the trading body moves verbatim into `_trade` and runs only when there is an
entry to start or step. Without this split, a night whose only work is a retirement stamp would
reach `min(lasts)` on an empty list and raise `ValueError`.

**Code:**

```python
def _night(conn: psycopg.Connection, rd: dates.RunDates, plan: NightPlan, run_id: int) -> None:
    """The single paper transaction's body (the caller's db.transaction commits or rolls back).

    Retirements are settled first and cost nothing: a retired strategy keeps every history row it
    ever wrote, and the only column tonight may write for it is ``paper_end`` (invariant 4). The
    market window is loaded only when something actually trades, so an all-retired roster is a
    cheap night, not a crash.
    """
    for r in plan.retired:
        if not r.stamp or r.paper_end is None:
            continue
        store.set_paper_end(conn, r.entry.id, r.paper_end)
        log.info("%s: paper_end %s, the last session it traded; its history is kept", r.entry.id, r.paper_end)
    if plan.start or plan.step:
        _trade(conn, rd, plan)
    runs.finish_paper(conn, run_id)


def _trade(conn: psycopg.Connection, rd: dates.RunDates, plan: NightPlan) -> None:
    """Start and step every active entry on tonight's bars window. Never called with nothing to do."""
    lasts = [state.last_session for _, state in plan.step]
    if plan.start:
        lasts.append(rd.data_date)
    earliest = min(lasts)
    since = store.market_window_since(earliest)  # earliest - store.MARKET_WINDOW_DAYS (550) days
    _check_window(since, earliest, list(plan.start) + [e for e, _ in plan.step])

    market = store.load_market_window(conn, since)
    window = dates.sessions(dates.next_session(earliest), rd.data_date)
    tonight = _Tonight(
        market=market,
        splits={s: store.applied_splits_on(conn, s) for s in window},
        dividends=store.dividends_between(conn, window[0], window[-1]) if window else {},
    )
    log.info(
        "bars window since %s; %d session(s) to step (%s..%s)",
        since,
        len(window),
        window[0] if window else "-",
        window[-1] if window else "-",
    )

    for e in plan.start:
        _start(conn, e, rd, tonight)
    for e, state in plan.step:
        sessions = dates.sessions(dates.next_session(state.last_session), rd.data_date)
        if e.engine == "bracket":
            _step_bracket(conn, e, sessions, tonight)
        elif e.engine == "book":
            _step_book(conn, e, sessions, tonight)
        elif e.engine == "benchmark":
            _step_benchmark(conn, e, sessions, tonight)
        else:
            raise PaperError(f"strategy {e.id!r} has unknown engine {e.engine!r}")
```

**Impact:** `_check_window` (:295) now sees only the entries that trade tonight, which it already
did — but the consequence is new and wanted: **retiring a long-lookback strategy relaxes the
window requirement**, because its `lookback` leaves `max(...)` with it. The unknown-engine guard
(:340, now in `_trade`) is unchanged and still reachable on every active entry; retired entries
never reach it, which is correct — a retired strategy with an engine this build no longer knows is
history, not a night to fail.
`test_failure_mid_night_leaves_no_partial_state_and_marks_failed` monkeypatches
`paper._step_book`, which `_trade` still calls by module attribute, so it keeps working.

---

### Step 6: the module docstring tells the new truth

**File:** `engine/src/seer_engine/commands/paper.py:9-11`

**Change:** replace flow step 3 and add the lifecycle to the flow, so the file's own contract is
not stale. Replace:

```
  3. read the roster rows and paper_state; a set paper_start under a different spec digest is
     refused (``store.check_digest``: a changed strategy needs a new id, handover D4)
  4. every roster strategy already stepped through rd.data_date: no-op, exit 0, nothing written
     (a re-run, a weekend or a holiday lands here)
```

with:

```
  3. read the roster rows (``store.read_roster_rows``) and resolve them into roster entries
     (``roster.from_rows``); a
     row whose object cannot be resolved stops the night with a named error and writes nothing
     (plan invariant 9). A ``status='retired'`` entry is then skipped deliberately: no orders, no
     equity snapshot, no ``paper_state`` step, and its ``paper_end`` is stamped with the last
     session it actually traded if it has none. For every **active** entry, a set paper_start
     under a different spec digest is refused (``store.check_digest``: a changed strategy needs a
     new id, handover D4). An active entry with no ``paper_start`` -- one just added to the
     roster -- starts tonight exactly as any new entry does (step 6).
  4. every active roster strategy already stepped through rd.data_date and every retirement
     already stamped: no-op, exit 0, nothing written (a re-run, a weekend or a holiday lands here)
```

**Impact:** documentation only.

---

### Step 7: `paper_check` replays the database roster, retirements included

**File:** `engine/src/seer_engine/commands/paper_check.py:100-104` (inside `check`)

**Change:** the replay must check the same roster the night traded, or a promoted strategy would
never be replayed and a strategy dropped from the database would be replayed from nothing. A
retired strategy is replayed exactly as before — it has a `paper_start` and a `paper_state`, and
`replay` does not read `status`. That is invariant 4 working: the record stays verifiable forever.

**Code — the replacement for `check`:**

```python
def check(conn: psycopg.Connection) -> tuple[CheckResult, ...]:
    """One ``CheckResult`` per roster entry, in roster order. Writes nothing.

    The roster is read from the ``strategies`` rows in this same read-only transaction, so the
    replay checks exactly what the night traded. A retired strategy is replayed like any other:
    it keeps its ``paper_start``, its ``paper_state`` and every history row, so its record stays
    verifiable after it stops trading (plan invariant 4).

    ``conn`` must have autocommit off and no transaction in progress; the read-only transaction
    this opens is always rolled back.
    """
    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise ValueError("paper_check needs a connection with no transaction in progress")
    try:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        return _check(conn, roster.from_rows(store.read_roster_rows(conn)))
    finally:
        conn.rollback()
```

And the docstring line at `paper_check.py:5`, replace:

```
For every roster strategy with a paper start, replay it from ``paper_start`` through its last
```

with:

```
For every strategy on the database roster -- retired ones included -- with a paper start, replay
it from ``paper_start`` through its last
```

**Impact:** `_check` keeps its signature and body. `store` is already imported at :35; `roster` is
too. `test_paper_check.py:170`'s `assert tuple(found) == ROSTER_IDS` keeps passing because
`read_roster_rows` returns `ORDER BY sort, id`, which is the migration's sort 1..5 — the compiled
tuple's order.

---

### Step 8: tests — the night (6)

**File:** `engine/tests/test_paper_command.py`, two helpers and six tests appended after `snaps`
(:233), before the `# ---- tests ----` banner for the helpers and at the end of the DB tests for
the rest.

**Change:** add the helpers first.

**Code — helpers, after `snaps` (:233):**

```python
def lifecycle(conn, strategy_id: str):
    """``(status, paper_end)`` of one strategies row."""
    return q(conn, "SELECT status, paper_end FROM strategies WHERE id = %s", (strategy_id,))[0]


def retire_by_hand(conn, strategy_id: str) -> None:
    """Retire without going through ``store.retire``: status only, paper_end left NULL.

    This is the plan index's Rollback-style hand SQL, and the case the night must repair.
    """
    with db.transaction(conn, False):
        conn.execute("UPDATE strategies SET status = 'retired' WHERE id = %s", (strategy_id,))


def make_unresolvable(conn, strategy_id: str) -> None:
    """Break ``strategy_id``'s name->object link in the database.

    The link is ``strategies.object_name`` (migration 006, phase 1) -- a column of its own, not
    ``params->'spec'->>'object'``, which is NULL until a strategy has been frozen. Setting it to a
    name ``roster.RESOLVER`` does not know is exactly the typo invariant 9 is about. The test below
    cannot pass silently if the break does not take: it asserts the night fails.
    """
    with db.transaction(conn, False):
        conn.execute(
            "UPDATE strategies SET object_name = 'NO_SUCH_OBJECT' WHERE id = %s",
            (strategy_id,),
        )
```

**Code — the six tests, appended after `test_dry_run_writes_nothing` (:404):**

```python
# ---- the roster lifecycle (phase 2) -----------------------------------------------------------


def test_a_retired_strategy_is_skipped_and_keeps_its_history(world):
    from seer_engine.paper import store

    for d in NIGHTS[:3]:
        assert night(world, d) == 0
    before_a = {
        "snaps": snaps(world, "A"),
        "state": q(world, "SELECT * FROM paper_state WHERE strategy_id = 'A'"),
        "orders": q(world, "SELECT id FROM orders WHERE strategy_id = 'A' ORDER BY id"),
    }
    assert before_a["snaps"] and before_a["state"]
    last_traded = before_a["state"][0][1]

    with db.transaction(world, False):
        assert store.retire(world, "A") == last_traded
    assert lifecycle(world, "A") == ("retired", last_traded)

    assert night(world, NIGHTS[3]) == 0
    # A wrote nothing more: no snapshot, no order, no paper_state step.
    assert snaps(world, "A") == before_a["snaps"]
    assert q(world, "SELECT * FROM paper_state WHERE strategy_id = 'A'") == before_a["state"]
    assert q(world, "SELECT id FROM orders WHERE strategy_id = 'A' ORDER BY id") == before_a["orders"]
    assert lifecycle(world, "A") == ("retired", last_traded)
    # and every active strategy did step.
    for sid in IDS:
        if sid == "A":
            continue
        assert snaps(world, sid)[-1][0] == dates.run_dates(night_of(NIGHTS[3])).data_date
    assert paper_run(world, NIGHTS[3])[0][0] == "success"


def test_retiring_by_hand_stamps_paper_end_on_the_next_night(world, caplog):
    import logging

    for d in NIGHTS[:3]:
        assert night(world, d) == 0
    [(_, last_traded)] = q(world, "SELECT strategy_id, last_session FROM paper_state WHERE strategy_id = 'A'")
    retire_by_hand(world, "A")
    assert lifecycle(world, "A") == ("retired", None)

    caplog.set_level(logging.INFO, logger="seer_engine.commands.paper")
    assert night(world, NIGHTS[3]) == 0
    assert lifecycle(world, "A") == ("retired", last_traded)
    assert "A: retired; no orders, no equity snapshot, no paper_state step" in caplog.text
    assert snaps(world, "A")[-1][0] == last_traded  # still no new snapshot


def test_a_stamped_retirement_leaves_later_nights_untouched(world):
    for d in NIGHTS[:3]:
        assert night(world, d) == 0
    retire_by_hand(world, "A")
    assert night(world, NIGHTS[3]) == 0  # stamps paper_end
    before = everything(world)
    assert night(world, NIGHTS[3]) == 0  # same night again: nothing left to do
    assert everything(world) == before


def test_a_retired_strategy_is_not_digest_checked_but_an_active_one_still_is(world):
    for d in NIGHTS[:2]:
        assert night(world, d) == 0
    with db.transaction(world, False):
        world.execute("UPDATE strategies SET params = jsonb_set(params, '{digest}', '\"0000\"') WHERE id = 'A'")
        world.execute("UPDATE strategies SET params = jsonb_set(params, '{digest}', '\"0000\"') WHERE id = 'C'")
    # C retired: its changed digest is never compared, because it takes no decision.
    retire_by_hand(world, "C")
    assert night(world, NIGHTS[2]) == 1  # A is still active, so SpecMismatch still stops the night
    [(status, error, _)] = paper_run(world, NIGHTS[2])
    assert status == "failed" and "SpecMismatch: A: stored spec digest" in error and "new id" in error
    # Put A back and the night runs, with C's bad digest still in the row and still unexamined.
    with db.transaction(world, False):
        world.execute(
            "UPDATE strategies SET params = jsonb_set(params, '{digest}', to_jsonb(%s::text)) WHERE id = 'A'",
            (roster.strategy_params(ENTRIES["A"])["digest"],),
        )
    assert go(world, NIGHTS[2]) == 0
    assert q(world, "SELECT params->>'digest' FROM strategies WHERE id = 'C'") == [("0000",)]


def test_an_active_strategy_with_no_paper_start_starts_on_the_next_night(world):
    # C is retired before the first night, so it never starts; it is reactivated three nights in.
    retire_by_hand(world, "C")
    for d in NIGHTS[:3]:
        assert night(world, d) == 0
    assert q(world, "SELECT count(*) FROM paper_state WHERE strategy_id = 'C'") == [(0,)]
    assert q(world, "SELECT paper_start FROM strategies WHERE id = 'C'") == [(None,)]

    with db.transaction(world, False):
        world.execute("UPDATE strategies SET status = 'active', paper_end = NULL WHERE id = 'C'")
    assert night(world, NIGHTS[3]) == 0

    start = session_of(NIGHTS[3])
    day0 = dates.run_dates(night_of(NIGHTS[3])).data_date
    assert q(world, "SELECT paper_start, params->>'digest' FROM strategies WHERE id = 'C'") == [
        (start, roster.strategy_params(ENTRIES["C"])["digest"])
    ]
    assert q(world, "SELECT last_session, pending_session FROM paper_state WHERE strategy_id = 'C'") == [
        (day0, start)
    ]
    assert [r[0] for r in snaps(world, "C")] == [day0]
    assert lifecycle(world, "C") == ("active", None)


def test_an_unresolvable_roster_entry_stops_the_night_and_is_not_a_skip(world):
    assert night(world, N0) == 0
    make_unresolvable(world, "A")
    before = everything(world)
    assert night(world, NIGHTS[1]) == 1
    assert everything(world) == before
    [(status, error, _)] = paper_run(world, NIGHTS[1])
    assert status == "failed"
    assert "A" in error and "NO_SUCH_OBJECT" in error
    # Invariant 9: a hard named error, never the deliberate skip a retired entry gets.
    assert "retired" not in error.lower() and "skip" not in error.lower()
```

**Impact:** `dates` is already imported in the test module (:18); `db` too. `logging` is imported
locally in the one test that needs `caplog`. The existing
`test_changed_frozen_spec_is_refused` is **not** modified — invariant 3 keeps its dedicated test.

---

### Step 9: tests — the store (4)

**File:** `engine/tests/test_paper_store.py`, appended after
`test_freeze_spec_writes_params_and_start_once_and_check_digest_compares` (:84), before the
`# --- day 0 and paper_state` banner.

**Code:**

```python
def test_retire_stamps_paper_end_from_paper_state_and_keeps_every_history_row(pg):
    store.init_paper_state(pg, "A", paper_start=S1, cash0=CASH0, usd_idr=RATE)
    store.write_paper_state(pg, "A", cash=CASH0, equity=CASH0, last_session=S2)
    before = pg.execute("SELECT count(*) FROM equity_snapshots WHERE strategy_id = 'A'").fetchone()[0]
    assert before == 1

    assert store.retire(pg, "A") == S2
    row = store.read_strategy(pg, "A")
    assert (row.status, row.paper_end) == ("retired", S2)
    # Invariant 4: retirement is a status change and a date, nothing else.
    assert pg.execute("SELECT count(*) FROM equity_snapshots WHERE strategy_id = 'A'").fetchone()[0] == before
    assert store.read_paper_state(pg, "A").last_session == S2
    pg.rollback()


def test_retire_of_a_strategy_that_never_traded_leaves_paper_end_null(pg):
    assert store.retire(pg, "A") is None
    row = store.read_strategy(pg, "A")
    assert (row.status, row.paper_end, row.paper_start) == ("retired", None, None)
    pg.rollback()


def test_retire_is_a_no_op_on_an_already_retired_row_and_a_missing_row_is_an_error(pg):
    store.init_paper_state(pg, "A", paper_start=S1, cash0=CASH0, usd_idr=RATE)
    assert store.retire(pg, "A") == dates.prev_session(S1)
    store.write_paper_state(pg, "A", cash=CASH0, equity=CASH0, last_session=S2)
    # Already retired: the stored paper_end stands, it is not re-stamped from the newer state.
    assert store.retire(pg, "A") == dates.prev_session(S1)
    assert store.read_strategy(pg, "A").paper_end == dates.prev_session(S1)
    with pytest.raises(store.StoreError, match="no strategies row"):
        store.retire(pg, "nope")
    pg.rollback()


def test_set_paper_end_writes_only_a_retired_row_with_no_paper_end(pg):
    with pytest.raises(store.StoreError, match="paper_end A"):
        store.set_paper_end(pg, "A", S2)  # still active
    pg.rollback()
    pg.execute("UPDATE strategies SET status = 'retired' WHERE id = 'A'")
    store.set_paper_end(pg, "A", S2)
    assert store.read_strategy(pg, "A").paper_end == S2
    with pytest.raises(store.StoreError, match="paper_end A"):
        store.set_paper_end(pg, "A", S3)  # already stamped
    pg.rollback()
    with pytest.raises(ValueError, match="not an NYSE session"):
        store.set_paper_end(pg, "A", date(2026, 10, 3))
```

**Impact:** `dates` and `pytest` are already imported at :14 and :12; `date` at :7. The
already-retired no-op is asserted to keep the *older* `paper_end`, which is the point: the date is
the last session actually traded, and a retired strategy trades no more.

---

### Step 10: tests — the replay over a retirement (1)

**File:** `engine/tests/test_paper_check.py`, appended at the end of the DB tests.

**Code:**

```python
def test_the_replay_passes_over_a_window_containing_a_retirement(world):
    from seer_engine.paper import store

    for d in NIGHTS[:4]:
        night(world, d)
    [(last_traded,)] = q(world, "SELECT last_session FROM paper_state WHERE strategy_id = 'A'")
    with db.transaction(world, False):
        assert store.retire(world, "A") == last_traded
    for d in NIGHTS[4:]:
        night(world, d)

    found = results(world)
    assert tuple(found) == ROSTER_IDS  # retired, but still on the board and still checked
    assert found["A"].status in ("ok", "split-affected"), text(found)
    assert found["A"].last_session == last_traded
    assert found["SPY"].last_session == LAST
    assert paper_check.execute(world) == 0
```

**Impact:** proves invariant 4 end to end — a retired strategy's whole record still replays
exactly, long after it stopped trading.

---

## Verification

**Build:**

```bash
"$SEER_PY" -m compileall -q "$SEER_WT/engine/src/seer_engine/commands/paper.py" \
  "$SEER_WT/engine/src/seer_engine/commands/paper_check.py" \
  "$SEER_WT/engine/src/seer_engine/paper/store.py"
"$SEER_PY" -m ruff check "$SEER_WT/engine"
"$SEER_PY" -m ruff format --check "$SEER_WT/engine"
```

**Tests:**

```bash
# the phase's own surface first
"$SEER_PY" -m pytest "$SEER_WT/engine/tests/test_paper_command.py" \
  "$SEER_WT/engine/tests/test_paper_store.py" \
  "$SEER_WT/engine/tests/test_paper_check.py" \
  "$SEER_WT/engine/tests/test_paper_roster.py" -q
# then the whole suite, with and without Postgres
"$SEER_PY" -m pytest "$SEER_WT/engine/tests" -q
env -u PG_TEST_URL "$SEER_PY" -m pytest "$SEER_WT/engine/tests" -q
```

**Test DELTA (off whatever this phase inherits from phase 1 — never an absolute):**

- **+11 tests**, all of them DB tests.
- With `PG_TEST_URL` exported: **+11 passed, +0 skipped**.
- Without `PG_TEST_URL`: **+0 passed, +11 skipped** (the `pg_url` fixture skips them).
- **No existing test changes its result.** In particular `test_changed_frozen_spec_is_refused`,
  `test_first_night_starts_every_roster_strategy`, `test_seven_nights_step_every_session_and_equal_the_runners`,
  `test_no_look_ahead`, `test_dry_run_writes_nothing` and every pinned digest in
  `test_paper_roster.py` pass **unchanged**.

The eleven: 6 in `test_paper_command.py`, 4 in `test_paper_store.py`, 1 in `test_paper_check.py`,
named in Steps 8-10.

**Manual check:**

```bash
# a dry night against the local train DB: the log must name each retired entry on its own line
"$SEER_PY" -m seer_engine --dry-run -v paper --now 2026-10-05T23:00:00Z 2>&1 | grep -E 'retired|paper_end'
```

Read the output for the one thing this phase is about: a retired strategy's line says
`retired; no orders, no equity snapshot, no paper_state step`, and an unresolvable one does not
appear at all because the night stopped with a named error before planning.

**Exit criteria:**

1. `paper` skips `status='retired'` entries: no `orders`, no `equity_snapshots`, no `paper_state`
   row is written for them on any night.
2. Retiring sets `paper_end` to the last session actually traded — at retirement time through
   `store.retire`, or on the next night through `store.set_paper_end` when the retirement was
   taken by hand — and no history row is deleted.
3. A strategy that is `active` with no `paper_start` starts on the next night through
   `store.freeze_spec`, with `paper_start = rd.session_date` and a day-0 snapshot, exactly as a new
   entry does today.
4. `store.check_digest`'s `SpecMismatch` refusal is reachable on every active started strategy and
   `test_changed_frozen_spec_is_refused` still passes, untouched.
5. An unresolvable roster entry fails the night with a named error, writes nothing, and its message
   contains neither "retired" nor "skip".
6. `paper_check` replays a window containing a retirement and exits 0, with the retired strategy
   still in its results.

---

## Handoffs

Found while planning, deliberately left to its owner:

- **`roster.MAX_LOOKBACK_BARS` — settled by the reconciler, owned by phase 1, not an open
  question.** It stays `max(e.lookback for e in ROSTER)`, where phase 1's `ROSTER` is
  `from_rows(SEED_ROWS)` — i.e. the max over the **seeded** roster, not over whatever the live
  database happens to hold. That is correct and deliberate: nothing in the night reads it
  (`_check_window`, `commands/paper.py:295`, recomputes `max(e.lookback …)` over tonight's trading
  entries), its only consumers are `test_paper_roster.py:188` (pins 253) and `:194` (pins that the
  550-day window covers it), and the *live* guard against a promoted strategy whose lookback the
  night cannot feed is phase 5's `promote.check_lookback`, which runs at promotion time against
  `store.MARKET_WINDOW_DAYS`. Phase 6 adds `FND` with lookback 20, so the value stays 253 and the
  pin is untouched. **No phase changes this symbol.** Not touched here.
- **`store.freeze_spec` does not check `status`.** A retired row can still be frozen by a direct
  call. `plan_night` makes that unreachable from the night, and adding `AND status = 'active'`
  would change `freeze_spec`'s error path for no present gain. **Phase 5** should decide whether
  `promote` wants that guard when it inserts rows.
- **`paper_check --require-sessions N` will fail a just-promoted strategy** (it has stepped 1
  session). `.github/workflows/nightly.yml:104` runs `paper_check` with **no** `--require-sessions`,
  so the nightly gate is unaffected, and no roster change in this set can break it. If **phase 6**
  or a later operator turns the flag on, `replay.failures` (`paper/replay.py:658`) is where a
  "started fewer than N sessions ago" exemption would go. Not in scope here.
- **The leaderboard's retired marker** reads `strategies.status` and `strategies.paper_end`, which
  this phase makes real. **Phase 4** owns the rendering. R3, not R2 — not mine.
- **Re-activating a retired strategy** (`status='active'`, `paper_end=NULL`) is plain SQL today,
  as the plan index's Rollback writes it, and my test uses it. No `store.activate` is added:
  nothing in this set calls one, and the index documents the SQL. If **phase 5** grows an
  `unretire`, it belongs there.
- **`web/scripts/seed-demo.mjs:307`** seeds a demo roster with the four compiled ids. It will need
  `status='active'` once the column exists. **Phase 1** (the migration's default `'active'` covers
  it) and **phase 4** (`web/`). Not touched here.

---

## Rollback

This phase is one commit on `feature/roster-promotion-pipeline`; `git revert` backs it out and the
tree returns to a night that trades the compiled `roster.ROSTER`. Nothing here is irreversible:

- **No migration, no schema change.** `006_roster.sql` is phase 1's; reverting this phase leaves
  the columns in place and unread by the engine.
- **The only data this phase writes outside the ordinary night** is
  `strategies.status` / `strategies.paper_end`. To undo a retirement:
  `UPDATE strategies SET status = 'active', paper_end = NULL WHERE id = '<id>';` — the strategy
  resumes on the next night with its history intact, because this phase deletes nothing. It will
  catch up every session it missed while retired, exactly as a missed night catches up today.
- **No paper clock is reset**, no `paper_start` is cleared, no snapshot, order, book row or trade
  is removed by any code path added here.
- If a retirement was stamped with the wrong `paper_end`, clear it
  (`UPDATE strategies SET paper_end = NULL WHERE id = '<id>';`) and the next night re-stamps it
  from `paper_state.last_session` through `store.set_paper_end`.
