> Adopted from `ROSTER_PROMOTION_PIPELINE_PLAN.md` phase 6. Source: `.workflows/plan/roster-promotion-pipeline/phase-6.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 6: `FND` onto the roster — the first promotion through the new path

**Plan set:** `ROSTER_PROMOTION_PIPELINE_PLAN.md`
**Analysis:** `20261005-165054-XGER_code_analyzer.md`
**Satisfies:** R1 — *"include the fundamentals-driven strategy in paper trading"*
**Depends on:** Phase 5 (and transitively 1, 2)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/paper`

---

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

`FND` (`strategies.f_fundamental.FUNDAMENTAL`) is the sixth paper portfolio: `status='active'`,
`engine='book'`, `rules_id='monthly-hold'`, carrying an honest `gate_note` that names the six
M0005 dev-window trials it failed and claims no pass. It reaches the roster through phase 5's
`promote`, not by hand.

And — the part the analysis could not see — **the paper night's book decision now reaches the
fundamental panel at all.** `paper/book.py:decide_book` calls `allocator.targets(history, …)`
unconditionally, the history-only path. `f_fundamental`'s documented contract is that this path
sees no panel and therefore targets nothing. Put `FND` on the roster without changing
`decide_book` and it holds cash forever while every log line and every row says it decided — the
exact "silently-empty portfolio that looks like a deliberate cash position" this phase's exit
criteria forbid. `decide_book` (and `replay.expected_book`, so the replay still matches) learn the
`MarketAware` dispatch that `backtest/book_runner.py:289` has had since phase 6 of the EDGAR set.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** nothing.

**Renames:** nothing.

**Creates:**
- `paper.roster.FND_ID` = `"FND"` (`paper/roster.py`, beside `F1_ID`)
- `paper.roster.FUNDAMENTAL_PARAMS` (`paper/roster.py`) — `FundamentalParams(rank="composite", top=20)`
- `paper.roster.RESOLVER["FUNDAMENTAL"] = Binding(obj=FUNDAMENTAL, params=FUNDAMENTAL_PARAMS)`
  (`from_registry` stays `False`) — the one committed resolver entry this whole set adds, and the
  line phase 5's refusal exists to ask for
- a sixth `RosterRow` in `paper.roster.SEED_ROWS`, `sort=6`, id `FND` (which makes
  `ROSTER = from_rows(SEED_ROWS)` six entries long)
- `db/migrations/007_fnd.sql` — the `FND` roster row, additive, idempotent
- `engine/tests/test_paper_fnd.py` — the roster-level fundamental tests

**Signature changes:** none. `decide_book` and `expected_book` keep their signatures exactly.

**Behaviour changes (no signature change, declared because another phase calls these):**
- `paper.book.decide_book` — when `isinstance(allocator, MarketAware)` it now prepares from the
  `Market` and calls `targets_prepared`. **For every allocator that is not `MarketAware` the
  expression is byte-identical to today**, so `SPY`, `A`, `F4-MOM12-N20-TREND`, `F1-SPY-SMA200-M`
  and `C` are untouched. `FUNDAMENTAL` is the only `MarketAware` object in the tree.
- `paper.replay.expected_book` — passes `prepared=` to `run_rules` on the same condition, and only
  on that condition.

**Requires (from earlier phases).** Reconciled against phases 1 and 5 as shipped. Two items here
were guesses and both were wrong; the corrections are the whole of this plan's change.

- **Phase 5 — the flag is `--lab-status-stays`, and `--no-lab-record` does not exist.** This plan
  asked for a flag that writes the roster row and *skips the lab record*, on the premise that the
  lab cannot record a promotion of a `rejected` method. **The premise is false.** The fact about
  `lab/lab.sqlite` is right — `M0005` is `status='rejected'` with 6 trials and a frozen
  `source_sha`, and `transitions` has no row with `src='rejected'`, so `rejected` is terminal —
  but phase 5 measured what that actually blocks: only the `status` move. `methods.analysis` grows
  under `methods_analysis_grows` and `insights` is an append-only journal, so
  `lab.store.record_promotion` writes both at **any** status. `--lab-status-stays` records the
  promotion and leaves `M0005` at `rejected`, which is exactly the honest shape. Nothing in this
  phase touches M0005's status, verdict, hypothesis or `source_sha`, and no `TRANSITIONS` edge is
  added. **The Step 6 fallback SQL is therefore the escape hatch it was always labelled, not a
  co-equal option: the command works.**
- **Phase 5's `promote` writes the definition columns too**, not only the display ones:
  `object_name`, `registry_id` (NULL), `gate_note`, `gate_applicable`, alongside
  `status='active'`, `promoted_from='M0005'` and **no `paper_start`**. It then rebuilds the row
  through `roster.from_row` inside its transaction, so a row the paper night would refuse never
  commits. `--candidate M0005-ALL` is **required** — M0005 has six variants.
- **Phase 1 — `ROSTER` is no longer a literal.** It is `from_rows(SEED_ROWS)`, built through
  `RESOLVER: dict[str, Binding]`. So a sixth entry is **one `RESOLVER` entry plus one `RosterRow`
  in `SEED_ROWS`**, not a sixth `RosterEntry` appended to a tuple. Step 3 is written that way and
  the old "adaptation note" is gone — there is one shape, not three.
- **Phase 1 — `007_fnd.sql` must carry the definition columns.** `roster.from_row` raises
  `UnknownObject` on a row with a NULL `object_name` and `BadRosterRow` on one with no
  `gate_note`, and phase 1's `test_the_migration_rows_equal_the_seed_rows` compares the whole
  `strategies` table to `SEED_ROWS`. A migration that writes only display columns would fail both.
  `status` is still deliberately not named (006's `DEFAULT 'active'` covers it, and naming it
  would resurrect a strategy someone has retired).
- Phase 1 — `roster.RosterEntry` (now 18 fields), `roster.spec`, `roster.spec_digest`,
  `roster.strategy_params`, `roster.entry`, `roster.ROSTER_IDS` and `roster.MAX_LOOKBACK_BARS`
  keep their names and meanings.
- Phase 2 — a roster entry that is `active` with no `paper_start` starts on the next night
  (`commands/paper.py:plan_night` → `_start` → `store.freeze_spec`). `FND` is its first user.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/strategies/f_fundamental.py` — **not one line.** Its logic is correct
  and shipped; this phase puts it on the roster.
- `engine/src/seer_engine/commands/promote.py` (phase 5) — called, never edited.
- `engine/src/seer_engine/commands/paper.py` (phase 2) — not edited. `_start` and `_step_book`
  already route `book` entries through `decide_book`; nothing there needs to know about panels.
- `engine/src/seer_engine/paper/compare.py` (phase 3).
- `web/**` (phase 4), including `view.ts`'s `looks`/`CARD_BGS` and `scripts/seed-demo.mjs`.
- `engine/src/seer_engine/backtest/registry.py` — **never** (D1).
- `engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py` — read for the gate_note's
  numbers and for the `M0005-ALL` candidate, **never edited**. `lab/lab.sqlite` is written exactly
  once, by `promote` at Step 6, and only the two append-only paths: one `# Promotion` section on
  `methods.analysis` and one `insights` row. `M0005`'s status, `source_sha`, `hypothesis`,
  `verdict` and its six `trials` rows are untouched.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/paper/book.py` | modify | `:135-179` `decide_book` gains the `MarketAware` branch; imports at `:40-59` |
| `engine/src/seer_engine/paper/replay.py` | modify | `:331` `expected_book` passes `prepared=`; imports at `:40-45` |
| `engine/src/seer_engine/paper/roster.py` | modify | docstring, imports, `FND_ID`, `FUNDAMENTAL_PARAMS`, one `RESOLVER` entry, one `SEED_ROWS` row (phase 1's file; phase 1 named this extension point) |
| `db/migrations/007_fnd.sql` | new | the `FND` roster row — display **and** definition columns |
| `engine/tests/test_paper_fnd.py` | new | the roster-level panel / empty-panel tests |
| `engine/tests/test_paper_book.py` | modify | `:343+` three `decide_book` dispatch tests |
| `engine/tests/test_paper_roster.py` | modify | `:49-58` the sixth pin, `:78-79`, `:187-188` (phase 1's file) |
| `engine/tests/test_migrate.py` | modify | `:288` the sort-ordered id list |
| `engine/tests/test_paper_check.py` | modify | `:51` `ROSTER_IDS` (phase 2's file) |
| `docs/runbooks/paper.md` | modify | a "Promoting FND" section (the runbook the exit criteria are checked against) |

Nine engine files plus one runbook, against the index's draft "Files: 3". **Accepted by the
reconciler; the index's phase table now says 10.** The expansion is entirely `decide_book`'s
`MarketAware` gap, which the analysis did not reach — `paper/book.py` and `paper/replay.py` appear
in no other phase's `Owns`, so this phase takes them, and no file here is contended: phase 6 runs
after 1, 2 and 5, and the three files it edits that another phase owns
(`paper/roster.py`, `test_paper_roster.py`, `test_paper_check.py`) are **appended to**, never
rewritten, at extension points phases 1 and 2 named in their own Handoffs.

## Implementation Steps

### Step 1: `decide_book` reaches the panel for a `MarketAware` allocator

**File:** `engine/src/seer_engine/paper/book.py:40-59` (imports), `:135-179` (`decide_book`)

**Change:** `decide_book` is the one live decision path in the tree that never calls
`prepare_for`. `backtest/book_runner.py:289` does; `backtest/dev.py:457` does;
`paper/book.py:178` does not. `FUNDAMENTAL.targets(history, members, d, held, params)` runs
`targets_with_panel(history, EMPTY_PANEL, …)` by construction (`f_fundamental.py`'s `targets`),
so on this path **no symbol is ever eligible and the result is always `()`** — which is the
allocator's documented contract for "nothing is known about any filer", not a bug, and precisely
why it must not be the path the paper night takes.

The non-`MarketAware` expression below is character-for-character today's. That is deliberate:
invariant 1 forbids changing an existing test's result, and `F4`/`F1`/`C`/`A`/`SPY` must replay
bit for bit against paper state already written.

Add `replace` to the `dataclasses` import and the two allocator helpers:

```python
from dataclasses import dataclass, replace
```

```python
from seer_engine.strategies.allocator import Allocator, MarketAware, prepare_for
```

Replace the body of `decide_book` from `if not isinstance(market, Market):` to the end of the
function (currently `:158-179`) with:

```python
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    if not isinstance(allocator, Allocator):
        raise TypeError(f"allocator must be an Allocator, got {type(allocator).__name__}")
    _book_rules(rules)
    _session("data_date", data_date)
    held_now = _held(held)
    session = dates.next_session(data_date)
    if rules.resize_cadence is not None:
        raise ValueError(
            f"rules {rules.id!r} split rank and resize cadences; paper trading cannot decide them yet "
            "(the last rank session's basket is not stored). Backtest them with run_book."
        )
    if not is_decision_session(rules, session):
        return None, False
    assert is_rank_session(rules, session)  # no resize_cadence above, so every decision is a rank
    members = market.membership.members_on(data_date)
    # The idle position is the runner's residual, never a family's (as run_book).
    mine = held_now - {rules.idle_symbol} if rules.idle_symbol is not None else held_now
    history = {s: h.upto(data_date) for s, h in market.history.items()}
    if isinstance(allocator, MarketAware):
        # A MarketAware allocator reads more of the Market than its bars (FUNDAMENTAL reads
        # market.fundamentals), so handing it the history dict alone is not a degraded result,
        # it is a WRONG one: f_fundamental's history-only path finds every symbol ineligible
        # and returns (), forever, silently. This is run_book's own dispatch
        # (backtest/book_runner.py:289) brought to the nightly decision.
        #
        # The Market handed over carries `history` -- the same dict the plain path passes, cut
        # at data_date -- so no bar dated after data_date is reachable on either path. The
        # panel needs no cut of its own: panel.as_of(symbol, d) answers from facts with
        # filed <= d and only those, and `filed` IS the no-look-ahead boundary
        # (005_fundamentals.sql, "filed IS THE ONLY NO-LOOK-AHEAD BOUNDARY").
        prepared = prepare_for(allocator, replace(market, history=history))
        wanted = allocator.targets_prepared(prepared, members, data_date, mine, params)
    else:
        wanted = allocator.targets(history, members, data_date, mine, params)
    return _with_idle(market, rules, tuple(wanted), data_date)
```

Then extend the docstring. Replace the paragraph currently at `:152-156` (beginning
*"``backtest.book_runner.run_book`` does, so backtests…"* through *"Nothing dated after
``data_date`` is read."*) with:

```
    Split-cadence rules (``rules.resize_cadence``) are a ValueError here: a resize-only session
    needs the LAST RANK SESSION'S basket, and this function is stateless — the paper store does
    not carry it yet. ``backtest.book_runner.run_book`` does, so backtests and replays of split
    rules are correct; only the nightly live decision is refused, loudly rather than by silently
    re-ranking every week. Otherwise exactly ``run_book``'s decision: ``allocator.targets``
    on ``{s: h.upto(data_date)}``, ``market.membership.members_on(data_date)``, ``held`` minus
    ``rules.idle_symbol``, ``params``; then ``book_runner._with_idle``. ``held`` is the set of
    symbols the book holds at the night of ``data_date`` (``book.held()`` after that session
    settled). Nothing dated after ``data_date`` is read.

    A ``MarketAware`` allocator (``strategies.allocator.MarketAware``: it defines
    ``prepare_market``) takes ``run_book``'s prepared branch instead —
    ``targets_prepared(prepare_for(allocator, market_cut_at_data_date), …)``. It must: such an
    allocator reads part of the ``Market`` that ``history`` cannot carry, and for ``FUNDAMENTAL``
    the history-only path is not a worse answer but a fixed empty one (its docstring: with no
    panel no symbol is eligible, so ``targets`` returns ``()``). The branch is keyed on the
    protocol and nothing else, so an allocator without ``prepare_market`` runs today's expression
    unchanged.
```

**Impact:** `FND` can decide. Nothing else on the roster changes — `isinstance(FACTOR, MarketAware)`
and `isinstance(TIMING, MarketAware)` are both `False` (neither defines `prepare_market`), and
`STRATEGY_A`/`STRATEGY_C` never reach `decide_book` at all (they are `bracket`).

### Step 2: the replay takes the same path, so `paper_check` still matches

**File:** `engine/src/seer_engine/paper/replay.py:40-45` (imports), `:331`

**Change:** `expected_book` settles the window with `run_rules(…)` and no `prepared`, which inside
`run_book` means the `allocator.targets(history, …)` branch (`book_runner.py:287-289`). After
Step 1 the night decides `FND` through `targets_prepared`. Leave this alone and `paper_check`
reports `FND` mismatched on its very first decision session — an expected empty basket against a
stored real one. Both halves must dispatch the same way.

Add to the imports (after `from seer_engine.paper.bracket import decide_bracket`):

```python
from seer_engine.strategies.allocator import MarketAware, prepare_for
```

Replace line `:331`:

```python
        run = run_rules(market, allocator, params, rules, start, last, dividends=dividends, usd_idr=head.usd_idr)
```

with:

```python
        # A MarketAware allocator is replayed through run_book's prepared branch, exactly as
        # paper.book.decide_book decides it; `prepared` stays None for every other allocator so
        # the five strategies with a paper clock replay byte for byte as before. `market` is
        # passed uncut here because run_book cuts per session itself and FUNDAMENTAL indexes its
        # bars by date (History.index_of), never by last row -- the property
        # allocatorkit.assert_no_lookahead pins.
        prepared = prepare_for(allocator, market) if isinstance(allocator, MarketAware) else None
        run = run_rules(
            market,
            allocator,
            params,
            rules,
            start,
            last,
            prepared=prepared,
            dividends=dividends,
            usd_idr=head.usd_idr,
        )
```

**Impact:** `paper_check` replays `FND`. `prepared` is `None` for `FACTOR` and `TIMING`, so
`F4-MOM12-N20-TREND` and `F1-SPY-SMA200-M` replay through the identical call they do today.

### Step 3: the `FND` roster entry

**File:** `engine/src/seer_engine/paper/roster.py`

**Change (a), imports — after `:59` (`from seer_engine.strategies.f_factor import FACTOR`):**

```python
from seer_engine.strategies.f_fundamental import FUNDAMENTAL, FundamentalParams, fundamental_lookback
```

**Change (b), ids — after `F1_ID = "F1-SPY-SMA200-M"`:**

```python
FND_ID = "FND"
```

**Change (c), the parameters — immediately above `RESOLVER`:**

```python
# FND's parameters, written out here rather than imported from
# ``lab.methods.m0005_fundamental_factors``. They are that module's ``COMPOSITE`` value for value
# -- the four-factor blend, equal weights, top 20, the shipped liquidity floors, no trend gate --
# but the lab module must not become an input to a paper spec digest: its ``source_sha`` is frozen
# in ``lab/lab.sqlite`` and editing it for a lab reason would silently re-digest a started paper
# strategy. The roster says what it runs, in its own file, as it does for every other entry.
#
# WHY composite AND NOT the best of the six. M0005 recorded six dev-window trials; all six failed
# and M0005-VAL had the highest total return of them. Picking it would be choosing on the
# multiple-testing noise the lab's ``trials`` table exists to count. ``composite`` is the a-priori
# blend of the four factor families the method's sources name (Fama-French value, Novy-Marx gross
# profitability, Bernard-Thomas SUE, return on equity), chosen before the numbers and not by them.
#
# It is VALUE-EQUAL to m0005's ``COMPOSITE``, which is what `promote --candidate M0005-ALL` writes
# the spec from. That equality is pinned by a test (Step 5), because if the two ever drift the
# promoted row's stored digest and the roster's recomputed digest differ and `store.check_digest`
# refuses FND's second night with a SpecMismatch. The test is in the test file, where importing
# the lab module is free; this file must never import it.
FUNDAMENTAL_PARAMS = FundamentalParams(rank="composite", top=20)
```

**Change (d), the resolver entry — one line in `RESOLVER` (phase 1's extension point):**

```python
    "FUNDAMENTAL": Binding(obj=FUNDAMENTAL, params=FUNDAMENTAL_PARAMS),
```

`from_registry` stays at its `False` default, so `FND`'s row must carry `registry_id = NULL` —
D1, enforced by `from_row`, which refuses a non-registry object that names a `registry_id`.

**Change (e), the seed row — append to `SEED_ROWS` after the `C` row, before the tuple's close.**
`ROSTER` is `from_rows(SEED_ROWS)` (phase 1), so this *is* how the sixth entry comes into being;
there is no `RosterEntry` literal to append any more, and `lookback` is not a field of a row —
`from_row` computes it as `obj.lookback(params)` for a book entry, which is
`fundamental_lookback(FUNDAMENTAL_PARAMS)` = 20.

```python
    RosterRow(
        id=FND_ID,
        name="FND · Fundamentals",
        sub="Top 20 by SEC filing factors, monthly",
        icon="book-open",
        is_champion=False,
        is_benchmark=False,
        sort=6,
        engine="book",
        rules_id="monthly-hold",
        object_name="FUNDAMENTAL",
        registry_id=None,
        gate_note=(
            "M0005 dev window only (1996-01-03..2015-10-16, fundamental coverage 0.3151); failed "
            "beats SPY TR (+1.8% vs +351.4%), >= 100 trades (15) and DSR >= 0.95 (0.006)"
        ),
    ),
```

`gate_applicable`, `status` and `paper_end` stay at `RosterRow`'s defaults (`True`, `"active"`,
`None`). The import at Change (a) therefore does not need `MONTHLY_HOLD` — the row names the
preset by id and `rules_for` resolves it — but it does need `fundamental_lookback` only if the
test file asserts it directly; `from_row` reaches it through `obj.lookback(params)`.

Every number in that `gate_note` is read off `lab/lab.sqlite`'s `M0005-ALL` trial row
(`total_return` 0.0181, `spy_tr_return` 3.5142, `trades` 15, `dsr` 0.0055, `failed` = *"beats SPY
TR; >= 100 trades; DSR >= 0.95"*, window `dev` 1996-01-03..2015-10-16). The coverage figure is
`docs/runbooks/data-pipeline.md:266`. **Nothing here claims a pass**, `gate_applicable` is left at
its default `True`, and `backtest_gate(e)` is therefore `{"passed": False, "note": …}` — exactly
A's, F4's and F1's shape.

**Change (f), the module docstring.** Add to the bullet list, after the `C` bullet:

```
- ``FND``: point-in-time SEC fundamental factors (``strategies.f_fundamental.FUNDAMENTAL`` with
  ``FUNDAMENTAL_PARAMS``) under ``MONTHLY_HOLD``, the book engine. It is the one roster object
  that reads more of the ``Market`` than its bars: it satisfies ``allocator.MarketAware``, so
  ``paper.book.decide_book`` prepares it from the whole ``Market`` and it ranks on
  ``market.fundamentals``. On a ``Market`` with no panel it targets nothing — the honest reading
  of "no filing is known", and the reason a database without ``005_fundamentals.sql`` applied
  gives an all-cash FND rather than a wrong one.
```

And at `:33-36`, replace *"Every entry is ``passed: false`` today."* — it is still true, so keep
the sentence and append:

```
``FND`` is on the roster having failed its gate too (six M0005 dev-window trials, all six failed,
all six recorded in ``lab/lab.sqlite``): passing a gate has never been this roster's admission
criterion, and the gates bind the real-money decision, not paper membership.
```

**The acceptance condition for Changes (c)–(e):** `spec(entry("FND"))` must come out as Step 7's
pinned text, and the five older digests must not move. Do not hand-edit a pin to match the code.

**Impact:** `ROSTER_IDS` becomes a 6-tuple; `MAX_LOOKBACK_BARS` stays `253` (FND's lookback is
`fundamental_lookback(FUNDAMENTAL_PARAMS)` = `max(DV_N=20, trend n=0)` = **20**, well inside
`F4`'s 253, so `store.MARKET_WINDOW_DAYS` and `commands/paper.py:_check_window` need nothing, and
`test_paper_roster.py:188`'s pin does not move — the reconciler assigned `MAX_LOOKBACK_BARS` to
phase 1 and no phase changes it). The five existing `spec_digest` values are untouched — invariant
2 holds, because nothing above edits an existing seed row, `RESOLVER`'s existing entries,
`rules_dict`, `spec`, or `INITIAL_IDR`; appending to a dict and to a tuple cannot re-digest what
was already in them.

### Step 4: the display row — `db/migrations/007_fnd.sql`

**File:** `db/migrations/007_fnd.sql` *(new)*

**Change:** `commands/paper.py:plan_night:192` raises `PaperError` when a roster entry has no
`strategies` row, and `test_paper_roster.py::test_display_fields_equal_the_migration_rows` compares
the table to `ROSTER`. A freshly migrated database must therefore come up with `FND` already
present. This is the same split `C` has: `004_news_veto.sql` writes C's display row and `paper`
writes its spec and clock.

This migration and phase 5's `promote` write the **same row** in two different places —
`007_fnd.sql` for any database brought up from migrations (dev, CI, a new Neon), `promote` for the
live one, which has already been migrated past 006. They must agree, and the columns below are
exactly the ones `promote._insert` writes, minus `params` and `status`: `promote` additionally
freezes nothing (`paper_start` stays NULL and `params` stays `'{}'` until the first paper night),
and `status` rides 006's default. If the two ever disagree, phase 1's migration-equality test and
phase 5's `test_the_written_row_rebuilds_into_the_entry_the_night_will_read` fail in opposite
directions, which is the point of having both.

```sql
-- Seer schema v7: FND, point-in-time SEC fundamental factors, joins the paper roster
-- (plan roster-promotion-pipeline, phase 6; requirement R1).
-- Additive only: one roster display row, in 004_news_veto.sql's shape. No column is added,
-- dropped or narrowed, and no existing row is touched.
--
-- WHY A MIGRATION WHEN PHASE 5's `promote` WRITES THIS ROW. The two write the same row for two
-- different databases. `promote --method M0005 --id FND` writes it to the live Neon instance,
-- which is already migrated and whose roster is data (006_roster.sql). This file writes it to
-- every database that is brought up from migrations instead -- CI's throwaway schema, a fresh
-- local train database, a rebuilt Neon -- so that `paper` finds a strategies row for every
-- roster entry (commands/paper.py plan_night) and the roster/migration equality test holds.
--
-- THE FROZEN SPEC, paper_start AND THE PAPER CLOCK ARE NOT WRITTEN HERE. `paper` writes them on
-- the first night (store.freeze_spec), exactly as it does for SPY, A, F4, F1 and C. A row with
-- no paper_start is a strategy that starts on the next night; that is phase 2's path and FND is
-- its first user.
--
-- THE DEFINITION COLUMNS ARE NOT OPTIONAL. 006_roster.sql moved object_name, registry_id,
-- gate_note and gate_applicable onto `strategies`, and paper/roster.py's `from_row` READS them:
-- a row with a NULL object_name raises UnknownObject and one with no gate_note raises
-- BadRosterRow, either of which stops the whole paper night (invariant 9). They are also what
-- test_paper_roster.py's migration-equality test compares against SEED_ROWS. So every value below
-- is byte-for-byte roster.py's FND seed row.
--
-- status IS DELIBERATELY NOT NAMED. 006_roster.sql gives it DEFAULT 'active', which is what FND
-- wants, so leaving it out stops the ON CONFLICT branch from resurrecting a strategy someone has
-- since retired. (This file does require 006: it names 006's columns.)
--
-- promoted_from IS WRITTEN ON INSERT AND NEVER ON UPDATE. 'M0005' is the honest provenance: FND's
-- allocator and parameters are lab method M0005's M0005-ALL candidate, taken off that Candidate
-- unchanged, and `promote --method M0005 --candidate M0005-ALL` records exactly that on the live
-- database. It asserts no lab STATUS transition -- M0005 stays 'rejected', because the lab's
-- `transitions` table has no row whose src is 'rejected' and promote's --lab-status-stays is the
-- acknowledgement of that. Keeping it out of the DO UPDATE list means re-running this file can
-- never clobber what promote wrote.
INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id,
                        object_name, registry_id, gate_note, gate_applicable, promoted_from) VALUES
  ('FND', 'FND · Fundamentals', 'Top 20 by SEC filing factors, monthly', 'book-open', false, false,
   6, 'book', 'monthly-hold',
   'FUNDAMENTAL', NULL,
   'M0005 dev window only (1996-01-03..2015-10-16, fundamental coverage 0.3151); failed beats SPY TR (+1.8% vs +351.4%), >= 100 trades (15) and DSR >= 0.95 (0.006)',
   true, 'M0005')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, sub = EXCLUDED.sub, icon = EXCLUDED.icon,
  is_champion = EXCLUDED.is_champion, is_benchmark = EXCLUDED.is_benchmark, sort = EXCLUDED.sort,
  engine = EXCLUDED.engine, rules_id = EXCLUDED.rules_id, object_name = EXCLUDED.object_name,
  registry_id = EXCLUDED.registry_id, gate_note = EXCLUDED.gate_note,
  gate_applicable = EXCLUDED.gate_applicable;
```

The `gate_note` string here must be character-identical to `SEED_ROWS`' — phase 1's
`test_the_migration_rows_equal_the_seed_rows` compares them directly, so a reflowed line break is
a failing test, not a cosmetic difference.

**Impact:** every migrated database holds a sixth strategy row that `roster.from_row` can build.
`engine='book'` satisfies `003_paper.sql:6`'s CHECK (`'bracket', 'book', 'benchmark'`) without
widening it — invariant 5. Nothing is dropped and no CHECK is narrowed, so 007 is additive.
**No collision with phase 1's `006_roster.sql`:** 006 adds columns and backfills the five rows
003/004 inserted; 007 inserts one new row and names no column 006 did not create. They run in name
order, which is the order they depend on.

### Step 5: the tests

**File:** `engine/tests/test_paper_fnd.py` *(new)*

**Change:** the roster-level coverage. The allocator's own behaviour is already pinned by
`test_f_fundamental.py`; what is NOT pinned anywhere is that **the roster entry, the night's
decision path and the replay's decision path all reach the panel the same way**, and that a
`Market` with no panel yields no trades rather than wrong ones. That last one is this phase's
named exit criterion and it has to be asserted here, at the roster level, not at the allocator
level where it already passes.

```python
"""FND on the paper roster (plan roster-promotion-pipeline, phase 6; requirement R1).

The allocator itself is covered by test_f_fundamental.py. This module covers the three things
that only exist once FND is a ROSTER entry:

1. the entry is what the roster says it is, and its gate note claims nothing;
2. `paper.book.decide_book` -- the nightly decision -- reaches `market.fundamentals`, because
   FUNDAMENTAL's history-only path is a fixed empty result, not a degraded one;
3. A MARKET WITH NO PANEL YIELDS NO TRADES, NOT WRONG TRADES. A database without
   005_fundamentals.sql applied, or with `fundamental_facts` truncated (which production's is,
   deliberately -- see the data-pipeline runbook), gives FND an EMPTY_PANEL. The portfolio then
   holds cash. That must be an asserted, understood outcome and not a silence that reads like a
   deliberate cash position.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from seer_engine.backtest.market import EMPTY_FUNDAMENTALS, Market, Membership
from seer_engine.fundamentals import Fact, FundamentalPanel
from seer_engine.paper.book import decide_book
from seer_engine.paper.roster import (
    FND_ID,
    FUNDAMENTAL_PARAMS,
    RESOLVER,
    ROSTER_IDS,
    SEED_ROWS,
    backtest_gate,
    entry,
)
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies.allocator import MarketAware
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FACTOR
from seer_engine.strategies.f_fundamental import FUNDAMENTAL, FundamentalPrepared
from seer_engine.strategies.f_index import TIMING

from stratkit import hist, session_days

SYMBOLS: tuple[str, ...] = ("AAA", "BBB", "CCC", "DDD", "EEE")
# The first session of a month under MONTHLY_HOLD, so decide_book's data_date is the session
# before it and the decision is a rank session.
DECIDE_FOR = date(2026, 11, 2)
DATA_DATE = date(2026, 10, 30)


# ---- the world ---------------------------------------------------------------------------------


def _days() -> list[date]:
    return session_days(date(2026, 1, 2), date(2026, 11, 2))


def _history() -> dict[str, History]:
    """Five liquid names with distinct closes, every session of 2026 through DECIDE_FOR."""
    days = _days()
    out: dict[str, History] = {}
    for k, symbol in enumerate(SYMBOLS):
        closes = [100.0 + 10.0 * k + 0.05 * i for i in range(len(days))]
        out[symbol] = hist(symbol, days, closes, volume=5_000_000)
    return out


def _panel() -> FundamentalPanel:
    """A real panel: every symbol filed once, well inside max_stale_days, with every factor finite.

    The facts differ per symbol so the composite ranking has something to order by; the values
    themselves are not asserted, only that a panel produces targets and no panel produces none.
    """
    filed = date(2026, 8, 14)
    period = date(2026, 6, 30)
    facts: list[Fact] = []
    for k, symbol in enumerate(SYMBOLS):
        for tag, unit, value in (
            ("Assets", "USD", 1_000_000_000.0 + 1e8 * k),
            ("StockholdersEquity", "USD", 400_000_000.0 + 2e7 * k),
            ("NetIncomeLoss", "USD", 50_000_000.0 + 5e6 * k),
            ("Revenues", "USD", 900_000_000.0 + 3e7 * k),
            ("CostOfRevenue", "USD", 500_000_000.0),
            ("EntityCommonStockSharesOutstanding", "shares", 10_000_000.0 + 1e6 * k),
        ):
            facts.append(
                Fact(
                    symbol=symbol,
                    taxonomy="dei" if unit == "shares" else "us-gaap",
                    tag=tag,
                    unit=unit,
                    period_start=period if unit == "shares" else date(2026, 1, 1),
                    period_end=period,
                    accn=f"0000000000-26-{k:06d}",
                    val=value,
                    fy=2026,
                    fp="Q2",
                    form="10-Q",
                    filed=filed,
                )
            )
    return FundamentalPanel.from_facts(facts)


def _market(panel) -> Market:
    days = _days()
    return Market(
        history=_history(),
        membership=Membership(
            intervals=tuple((s, "SP500", days[0], None) for s in SYMBOLS),
        ),
        fx=tuple((d, Decimal("16000.0000")) for d in days),
        fundamentals=panel,
    )


@pytest.fixture
def with_panel() -> Market:
    return _market(_panel())


@pytest.fixture
def no_panel() -> Market:
    return _market(EMPTY_FUNDAMENTALS)


# ---- 1. the entry ------------------------------------------------------------------------------


def test_fnd_is_the_sixth_roster_entry():
    assert ROSTER_IDS[-1] == FND_ID == "FND"
    assert len(ROSTER_IDS) == 6
    e = entry(FND_ID)
    assert (e.sort, e.engine, e.rules_id, e.is_champion, e.is_benchmark) == (6, "book", "monthly-hold", False, False)
    assert e.obj is FUNDAMENTAL
    assert e.object_name == "FUNDAMENTAL"
    assert e.params is FUNDAMENTAL_PARAMS
    assert e.rules is MONTHLY_HOLD
    assert e.registry_id is None  # D1: promoted strategies never enter backtest.registry.REGISTRY


def test_fnd_claims_no_backtest_gate_pass():
    e = entry(FND_ID)
    gate = backtest_gate(e)
    assert gate == {"passed": False, "note": e.gate_note}
    assert e.gate_applicable is True  # the quant gate DOES apply to it; it simply has not passed
    assert "failed" in e.gate_note
    for word in ("passed", "pass ", "beat SPY"):
        assert word not in e.gate_note.replace("beats SPY TR", "")


def test_fnd_lookback_is_the_dollar_volume_window():
    # fundamental_lookback = max(DV_N=20, trend n=0). A filing's availability is its `filed`
    # date, not a bar count, so nothing here needs a long warm-up.
    assert entry(FND_ID).lookback == 20


def test_the_resolver_names_fundamental_and_the_seed_row_uses_it():
    """The extension point phase 1 defined and phase 5 refuses without: one RESOLVER entry.

    Checked here rather than in test_paper_roster.py so the FND-specific facts stay in one file.
    """
    binding = RESOLVER["FUNDAMENTAL"]
    assert binding.obj is FUNDAMENTAL
    assert binding.params is FUNDAMENTAL_PARAMS
    assert binding.from_registry is False       # D1: never a backtest.registry entry
    row = next(r for r in SEED_ROWS if r.id == FND_ID)
    assert (row.object_name, row.registry_id, row.rules_id) == ("FUNDAMENTAL", None, "monthly-hold")
    assert (row.status, row.paper_end, row.gate_applicable) == ("active", None, True)


def test_the_roster_params_equal_the_lab_candidate_promote_writes_from():
    """The one drift that would break FND's SECOND night, not its first.

    `promote --candidate M0005-ALL` freezes the spec from the LAB module's params object;
    `roster.from_row` rebuilds it from FUNDAMENTAL_PARAMS. The two are separate objects by design
    -- roster.py must never import a lab method, whose `source_sha` is frozen for lab reasons --
    so only value equality keeps `store.check_digest` quiet. Importing the lab module is free
    here; it is forbidden in roster.py.
    """
    from seer_engine.lab.methods.m0005_fundamental_factors import METHOD as M0005

    candidate = next(c for c in M0005.candidates if c.id == "M0005-ALL")
    assert candidate.params == FUNDAMENTAL_PARAMS
    assert candidate.allocator is FUNDAMENTAL
    assert candidate.rules is MONTHLY_HOLD
    # and therefore the digest the roster recomputes is the digest promote would have frozen
    assert candidate.params.as_dict() == FUNDAMENTAL_PARAMS.as_dict()


# ---- 2. the night reaches the panel ------------------------------------------------------------


def test_fundamental_is_the_only_market_aware_roster_object():
    assert isinstance(FUNDAMENTAL, MarketAware)
    # The guard that keeps Step 1's branch honest: if another roster object ever gains
    # prepare_market, it starts taking the prepared path and this test says so.
    assert not isinstance(FACTOR, MarketAware)
    assert not isinstance(TIMING, MarketAware)


def test_decide_book_ranks_fnd_from_the_market_panel(with_panel):
    e = entry(FND_ID)
    targets, idle_added = decide_book(with_panel, e.obj, e.params, e.rules, DATA_DATE, frozenset())
    assert targets, "FND decided nothing against a Market carrying a panel"
    assert idle_added is False  # MONTHLY_HOLD has no idle_symbol
    assert {t.symbol for t in targets} <= set(SYMBOLS)
    assert sum(t.weight for t in targets) <= Decimal(1)


def test_decide_book_would_rank_nothing_without_the_market_aware_branch(with_panel):
    """The regression this phase exists to prevent, stated as an assertion.

    `allocator.targets(history, ...)` is the expression decide_book used for every allocator
    before phase 6. For FUNDAMENTAL it is EMPTY_PANEL by construction, so it is not a slower or
    coarser answer -- it is a fixed empty one. If this ever stops being true, the branch in
    decide_book can go; until then removing it silently empties the portfolio.
    """
    e = entry(FND_ID)
    history = {s: h.upto(DATA_DATE) for s, h in with_panel.history.items()}
    members = with_panel.membership.members_on(DATA_DATE)
    assert e.obj.targets(history, members, DATA_DATE, frozenset(), e.params) == ()


def test_decide_book_prepares_fnd_from_the_whole_market(with_panel):
    prepared = entry(FND_ID).obj.prepare_market(with_panel)
    assert isinstance(prepared, FundamentalPrepared)
    assert prepared.panel is with_panel.fundamentals


def test_decide_book_for_fnd_reads_no_bar_from_the_session_on(with_panel):
    """No look-ahead at the roster level: later bars cannot change the decision for DATA_DATE."""
    e = entry(FND_ID)
    before = decide_book(with_panel, e.obj, e.params, e.rules, DATA_DATE, frozenset())
    cut = Market(
        history={s: h.upto(DATA_DATE) for s, h in with_panel.history.items()},
        membership=with_panel.membership,
        fx=tuple(row for row in with_panel.fx if row[0] <= DATA_DATE),
        fundamentals=with_panel.fundamentals,
    )
    assert decide_book(cut, e.obj, e.params, e.rules, DATA_DATE, frozenset()) == before


def test_decide_book_off_a_decision_session_is_none_for_fnd(with_panel):
    e = entry(FND_ID)
    # The session after 2026-10-29 is 2026-10-30, mid-month: not a MONTHLY_HOLD decision session.
    assert decide_book(with_panel, e.obj, e.params, e.rules, date(2026, 10, 29), frozenset()) == (None, False)


# ---- 3. no panel, no trades --------------------------------------------------------------------


def test_a_market_with_no_panel_yields_no_trades_not_wrong_trades(no_panel):
    """The exit criterion, at the roster level.

    EMPTY_FUNDAMENTALS is what every Market carried before 2dad9ff and what `io.load_panel`
    still returns when `fundamental_facts` is missing or empty -- production's state. FND must
    then target NOTHING. Not a partial basket from whichever symbols happen to have a fact; not
    an exception that fails the paper night for the other five strategies; nothing.
    """
    e = entry(FND_ID)
    assert no_panel.fundamentals is EMPTY_FUNDAMENTALS
    targets, idle_added = decide_book(no_panel, e.obj, e.params, e.rules, DATA_DATE, frozenset())
    assert targets == ()
    assert idle_added is False


def test_an_empty_panel_is_the_same_answer_through_both_paths(no_panel):
    """And the empty answer is the SAME empty answer the history-only path gives.

    This is the P4 identity at the roster level: with no panel, the branch decide_book takes
    cannot matter. It is what makes the all-cash outcome a contract rather than a coincidence.
    """
    e = entry(FND_ID)
    history = {s: h.upto(DATA_DATE) for s, h in no_panel.history.items()}
    members = no_panel.membership.members_on(DATA_DATE)
    assert decide_book(no_panel, e.obj, e.params, e.rules, DATA_DATE, frozenset())[0] == ()
    assert e.obj.targets(history, members, DATA_DATE, frozenset(), e.params) == ()
```

> **Implementer note on the fixtures.** `Fact`, `FundamentalPanel.from_facts`, `Membership`'s
> interval shape, and `stratkit.hist`/`session_days` are used here exactly as
> `engine/tests/test_f_fundamental.py:19-47` and its `real_panel_fx` fixture use them — copy the
> constructor calls from there if any keyword has drifted. The assertions above are the contract;
> the fixture spelling is not.

**File:** `engine/tests/test_paper_book.py:343+` (section 3, "decide_book wiring")

**Change:** add three tests to the section that already pins `decide_book`'s wiring, so the
dispatch is covered where a reader of `decide_book` will look for it. Append after
`test_decide_book_argument_checks` (`:381`):

```python
def test_decide_book_uses_targets_for_an_allocator_that_is_not_market_aware():
    """The unchanged path. A plain allocator must still be called through `targets`, with the
    history dict cut at data_date -- not through `targets_prepared`, and not with a Market."""
    seen: list[tuple] = []

    class Plain:
        id = "PLN"

        def lookback(self, params): return 1
        def symbols(self, params): return ()
        def holds(self, params): return ()
        def uses_members(self, params): return True
        def prepare(self, history): return dict(history)

        def targets(self, history, members, data_date, held, params):
            seen.append(("targets", sorted(history), sorted(members), data_date))
            return ()

        def targets_prepared(self, prepared, members, data_date, held, params):
            raise AssertionError("a non-MarketAware allocator must not take the prepared path")

    targets, idle_added = decide_book(wiring_market(), Plain(), None, MONTHLY_HOLD, D("2025-02-28"), frozenset())
    assert (targets, idle_added) == ((), False)
    assert [row[0] for row in seen] == ["targets"]


def test_decide_book_uses_targets_prepared_for_a_market_aware_allocator():
    """The new path. A MarketAware allocator is prepared from the Market and then asked for
    targets_prepared -- never asked for `targets`, which for FUNDAMENTAL is a fixed empty."""
    seen: list[tuple] = []

    class Aware:
        id = "AWR"

        def lookback(self, params): return 1
        def symbols(self, params): return ()
        def holds(self, params): return ()
        def uses_members(self, params): return True
        def prepare(self, history): return ("prepare", dict(history))

        def prepare_market(self, market):
            seen.append(("prepare_market", sorted(market.history), market.fundamentals))
            return ("prepared", market)

        def targets(self, history, members, data_date, held, params):
            raise AssertionError("a MarketAware allocator must not take the history-only path")

        def targets_prepared(self, prepared, members, data_date, held, params):
            seen.append(("targets_prepared", prepared[0], data_date))
            return ()

    market = wiring_market()
    targets, idle_added = decide_book(market, Aware(), None, MONTHLY_HOLD, D("2025-02-28"), frozenset())
    assert (targets, idle_added) == ((), False)
    assert [row[0] for row in seen] == ["prepare_market", "targets_prepared"]
    assert seen[0][2] is market.fundamentals  # the panel is carried over, not replaced
    assert seen[1][1] == "prepared"


def test_decide_book_cuts_the_history_it_prepares_a_market_aware_allocator_from():
    """prepare_market sees history cut at data_date, exactly as the plain path's dict is."""
    seen: list[dict] = []

    class Aware:
        id = "AWR"

        def lookback(self, params): return 1
        def symbols(self, params): return ()
        def holds(self, params): return ()
        def uses_members(self, params): return True
        def prepare(self, history): return dict(history)

        def prepare_market(self, market):
            seen.append({s: h.last_date() for s, h in market.history.items()})
            return None

        def targets(self, history, members, data_date, held, params):
            raise AssertionError("unreachable")

        def targets_prepared(self, prepared, members, data_date, held, params):
            return ()

    data_date = D("2025-02-28")
    decide_book(wiring_market(), Aware(), None, MONTHLY_HOLD, data_date, frozenset())
    assert seen and all(d is None or d <= data_date for d in seen[0].values())
```

> `wiring_market()` and `D` already exist in that file (`:343-385`). If `wiring_market()`'s
> sessions do not reach `2025-02-28`, reuse whatever `data_date` the neighbouring
> `test_decide_book_reads_members_and_history_at_data_date` (`:356`) passes — it is the same
> fixture and the same decision session.

**File:** `engine/tests/test_paper_roster.py`

**Change:** three literals widen to six entries. The five existing pinned digests are **not
touched** — invariant 2.

At `:49-58`, replace:

```python
F4 = "F4-MOM12-N20-TREND"
F1 = "F1-SPY-SMA200-M"

PINS = {
    "SPY": "ca309ea7f19d0b771f236c63309a2fcf28a82e16048528d738dc329a42d4d198",
    "A": "37cd89be4b4c82f9dc2d4f3bdd69551a7d31aef83119f23ee757f8ec6568362f",
    F4: "6c55c13acc487a6fccbe2c5c0eb91a36e39f3a5444555a0dbfba4ffba5b30deb",
    F1: "e7fbb32d1cc4e11b2d0d9b941ab01ac1a545e49a08c11bf8c70da5c54cad9e2f",
    "C": "6cea6cb8de993f6a3f2d7ef4b48c878654a57df16cab87f72a95e9dd49a1b762",
}
```

with:

```python
F4 = "F4-MOM12-N20-TREND"
F1 = "F1-SPY-SMA200-M"
FND = "FND"

PINS = {
    "SPY": "ca309ea7f19d0b771f236c63309a2fcf28a82e16048528d738dc329a42d4d198",
    "A": "37cd89be4b4c82f9dc2d4f3bdd69551a7d31aef83119f23ee757f8ec6568362f",
    F4: "6c55c13acc487a6fccbe2c5c0eb91a36e39f3a5444555a0dbfba4ffba5b30deb",
    F1: "e7fbb32d1cc4e11b2d0d9b941ab01ac1a545e49a08c11bf8c70da5c54cad9e2f",
    "C": "6cea6cb8de993f6a3f2d7ef4b48c878654a57df16cab87f72a95e9dd49a1b762",
    # FND joins the roster in phase 6 of roster-promotion-pipeline. Its spec is composite-rank
    # fundamentals, top 20, equal sizing, under monthly-hold. The five values above are
    # unchanged, byte for byte: adding an entry must never re-digest a started strategy.
    FND: "4a9dacc37478bf4d17b3ba35cbebd9e0c3f8759f122c4596f7cd9d076d8ef530",
}
```

At `:78-79`, replace:

```python
    assert ROSTER_IDS == ("SPY", "A", F4, F1, "C")
    assert [e.sort for e in ROSTER] == [1, 2, 3, 4, 5]
```

with:

```python
    assert ROSTER_IDS == ("SPY", "A", F4, F1, "C", FND)
    assert [e.sort for e in ROSTER] == [1, 2, 3, 4, 5, 6]
```

At `:187-188`, replace:

```python
    assert {e.id: e.lookback for e in ROSTER} == {"SPY": 1, "A": 200, F4: 253, F1: 200, "C": 200}
    assert MAX_LOOKBACK_BARS == 253
```

with:

```python
    assert {e.id: e.lookback for e in ROSTER} == {"SPY": 1, "A": 200, F4: 253, F1: 200, "C": 200, FND: 20}
    # FND's lookback is the 20-bar dollar-volume window: a filing's availability is its `filed`
    # date, not a bar count. The roster's longest lookback is still F4's 253.
    assert MAX_LOOKBACK_BARS == 253
```

**File:** `engine/tests/test_migrate.py:288`

**Change:** replace

```python
    assert [r[0] for r in rows] == ["SPY", "A", "F4-MOM12-N20-TREND", "F1-SPY-SMA200-M", "C"]
```

with

```python
    assert [r[0] for r in rows] == ["SPY", "A", "F4-MOM12-N20-TREND", "F1-SPY-SMA200-M", "C", "FND"]
```

`:18`'s `ROSTER_IDS` set is used only with `<=` (`:210`) and against the pre-004 state (`:181`), so
it stays as it is.

**File:** `engine/tests/test_paper_check.py:51`

**Change:** replace

```python
ROSTER_IDS = ("SPY", "A", F4, F1, "C")
```

with

```python
ROSTER_IDS = ("SPY", "A", F4, F1, "C", "FND")
```

The world those tests build seeds no `fundamental_facts`, so `store.load_market_window` gives
`EMPTY_FUNDAMENTALS`, so `FND` holds cash across all eight nights and `paper_check` replays it as
`ok` with zero fills. That is the right outcome and it is the empty-panel contract exercised
end to end, for free, through `paper` and `paper_check` both.

**Impact:** `test_paper_command.py` needs no edit (`ENTRIES`/`IDS` are derived from `roster.ROSTER`
at `:56-57`) and neither does `test_demo.py` (`len(ROSTER)` at `:109,111,144`).

### Step 6: run the promotion

**File:** none — this is the runbook step that satisfies D7, recorded in `docs/runbooks/paper.md`.

**Change:** `FND` must travel phase 5's path. Dry-run first, then the real write, against the live
Neon database:

The `RESOLVER` entry from Step 3 must be **committed** before this runs: `promote` asks the
resolver for the allocator's name and refuses when there is none. That refusal is phase 5's
designed behaviour and is the whole of D2's cost.

```bash
GATE_NOTE="M0005 dev window only (1996-01-03..2015-10-16, fundamental coverage 0.3151); failed beats SPY TR (+1.8% vs +351.4%), >= 100 trades (15) and DSR >= 0.95 (0.006)"

# 1. See what it would write, in both databases. Writes nothing.
"$SEER_PY" -m seer_engine --dry-run promote \
  --method M0005 --candidate M0005-ALL --id FND \
  --name "FND · Fundamentals" --sub "Top 20 by SEC filing factors, monthly" \
  --icon book-open --sort 6 --lab-status-stays --gate-note "$GATE_NOTE"

# 2. Write it. No --retire: FND JOINS the roster, it does not replace a horseman. The board
#    goes to five research strategies plus SPY, which is the point of R1.
"$SEER_PY" -m seer_engine promote \
  --method M0005 --candidate M0005-ALL --id FND \
  --name "FND · Fundamentals" --sub "Top 20 by SEC filing factors, monthly" \
  --icon book-open --sort 6 --lab-status-stays --gate-note "$GATE_NOTE"

# 3. Confirm: active, no paper clock yet, resolvable, and no claim of a gate pass.
psql "$DATABASE_URL_UNPOOLED" -c \
  "SELECT id, status, sort, engine, rules_id, object_name, registry_id, gate_applicable, paper_start, promoted_from FROM strategies WHERE id='FND'"

# 4. Commit the lab's record of it (promote appended an analysis section and an insight).
"$SEER_PY" -m seer_engine lab stage
git status --porcelain lab/lab.sqlite web/data/lab.json   # both expected to be dirty here
```

Three things about this command, each settled against phase 5's shipped contract:

- **`--candidate M0005-ALL` is required.** M0005 has six variants (VAL, ROE, GP, SUE, ALL, ALL-R)
  and they are different algorithms; `promote` refuses to guess. `M0005-ALL` is the one whose
  `params` is `FundamentalParams(rank="composite", top=20)` — Step 3's `FUNDAMENTAL_PARAMS`.
- **`--lab-status-stays`, not `--no-lab-record`.** `M0005` is `status='rejected'` and
  `lab/lab.sqlite`'s `transitions` table has no row with `src='rejected'`, so `rejected` is
  terminal and no status move is possible. But the lab still *records* the promotion: `analysis`
  grows by one `# Promotion` section and one `insights` row is appended, both of which the
  append-only triggers permit at any status. The flag is the acknowledgement that the roster is
  taking a method the lab has not passed — which is D5 in one word. `source_sha`, `hypothesis`,
  `verdict` and the six `trials` rows are untouched; no `TRANSITIONS` edge is added.
- **`promoted_from` is `'M0005'`.** It names the method the allocator and parameters came from.
  It asserts no lab transition, and the lab's own record (step 4) says in prose that the status
  did not move.

**Fallback — the documented equivalent (index exit criteria, "or a documented equivalent that
writes the same rows").** Only if the live database is unreachable from the machine running the
command. It is `007_fnd.sql`'s INSERT verbatim, in one transaction, with `status` named
explicitly; `paper_start` and `params` stay NULL/`'{}'` so `paper` freezes the spec and starts the
clock on the next night. If it is used, say so in the runbook section rather than letting the
row's provenance be undocumented — and note that the lab then carries **no** record of the
promotion, which is the real cost of the escape hatch and the reason to prefer the command.

**Impact:** on the next nightly run, `plan_night` finds `FND` with a row, `status='active'`, no
`paper_start` and no `paper_state`, puts it in `plan.start`, and `_start` freezes the spec
(digest `4a9dacc3…`) and writes `paper_start = rd.session_date`. From then on it is an ordinary
book strategy.

### Step 7: verify the spec digest did not drift

**File:** none — a check, run before committing Step 5's pin.

**Change:** the pin in `test_paper_roster.py` was computed against this tree. Confirm it, and
confirm the five older ones are untouched:

```bash
"$SEER_PY" - <<'PY'
from seer_engine.paper.roster import ROSTER, spec, spec_digest, spec_text
for e in ROSTER:
    print(f"{e.id:>20}  {spec_digest(spec(e))}")
print()
print(spec_text(spec(next(e for e in ROSTER if e.id == "FND"))))
PY
```

Expected, exactly:

```
                 SPY  ca309ea7f19d0b771f236c63309a2fcf28a82e16048528d738dc329a42d4d198
                   A  37cd89be4b4c82f9dc2d4f3bdd69551a7d31aef83119f23ee757f8ec6568362f
  F4-MOM12-N20-TREND  6c55c13acc487a6fccbe2c5c0eb91a36e39f3a5444555a0dbfba4ffba5b30deb
     F1-SPY-SMA200-M  e7fbb32d1cc4e11b2d0d9b941ab01ac1a545e49a08c11bf8c70da5c54cad9e2f
                   C  6cea6cb8de993f6a3f2d7ef4b48c878654a57df16cab87f72a95e9dd49a1b762
                 FND  4a9dacc37478bf4d17b3ba35cbebd9e0c3f8759f122c4596f7cd9d076d8ef530
```

and the FND spec text:

```
{"engine":"book","id":"FND","initial_idr":"20000000","object":"FUNDAMENTAL","object_id":"FND","params":{"max_stale_days":"400","min_dollar_volume":"20000000","min_price":"5","rank":"composite","sizing":"equal","top":"20","trend":"none","weights":"1:1:1:1"},"registry_digest":null,"registry_id":null,"rules":{"cadence":"monthly","cost_rate":"0.001","dividends":"true","engine":"book","entry":"open_limit","fractional":"false","id":"monthly-hold","idle_symbol":null,"max_positions":null,"resize":"true","time_stop":null},"rules_id":"monthly-hold"}
```

If a *first five* digest moved, an earlier phase in this set broke invariant 2 — stop and report
it, do not re-pin. If only FND's moved, the entry in Step 3 was mistyped; fix the entry, not the
pin. Note that `gate_note` is **not** part of the spec, so rewording it cannot move the digest —
the note can be corrected later without resetting a paper clock, exactly as `roster.py:33-34`
says.

### Step 8: the runbook

**File:** `docs/runbooks/paper.md`

**Change:** add a section recording what was done, because Step 6 has an effect outside git and
the Rollback below refers to it. Append:

```markdown
## FND joined the roster (2026-10, roster-promotion-pipeline phase 6)

`FND` — point-in-time SEC fundamental factors, `strategies.f_fundamental.FUNDAMENTAL` with
`rank="composite", top=20` under `monthly-hold` — is the sixth paper portfolio, written through
`promote --method M0005 --candidate M0005-ALL --id FND --lab-status-stays` (see the command in the
plan's Step 6). It is `status='active'` with no `paper_start`, so the next nightly run starts its
clock the ordinary way.

**It has not passed a backtest gate and does not claim to.** Its `gate_note` names the six M0005
dev-window trials recorded in `lab/lab.sqlite`, all six of which failed, and the dev window's
0.3151 fundamental coverage. That is the same standing A, F4 and F1 are on. Paper membership has
never required a gate pass; the gates bind the real-money decision, and the go-live checklist
(`CHECKS = 6`, per strategy) still reads `Paper only. Backtest gate not passed` for FND.

**`promoted_from` is `'M0005'`, and `M0005` is still `rejected` in the lab.** Those two facts sit
together on purpose. The column names the method the allocator and parameters came from; it
asserts no lab transition. `M0005` cannot move: `lab/lab.sqlite`'s `transitions` table has no edge
out of `rejected`. What the lab *does* carry is the promotion itself — `promote` appended a
`# Promotion` section to `methods.analysis` and one `insights` row, both permitted at any status
by the append-only triggers, and `--lab-status-stays` is the flag that says "record it, do not
move it". So the promotion is findable from either end, and nothing claims a gate the method did
not pass.

**If FND holds only cash, check the panel before checking the strategy.** `io.load_panel` returns
`EMPTY_FUNDAMENTALS` when `fundamental_facts` is missing or empty — which is production's
deliberate state (see the data-pipeline runbook's "Train/eval on a local database"). With no panel
no symbol is eligible and FND targets nothing. That is the documented contract, not a fault:

    SELECT count(*), max(filed) FROM fundamental_facts;

Zero rows there is the whole explanation. `engine/tests/test_paper_fnd.py` asserts this outcome so
it can never be mistaken for a deliberate cash position.
```

**Impact:** the one externally visible change in this phase set is documented where the operator
will look.

## Verification

**Build:**

```bash
"$SEER_PY" -m compileall -q "$SEER_WT/engine/src/seer_engine/paper" "$SEER_WT/engine/src/seer_engine/commands"
"$SEER_PY" -m ruff check engine/src engine/tests   # if ruff is configured for this tree
```

**Tests:**

```bash
# the phase's own surface, fastest first
"$SEER_PY" -m pytest engine/tests/test_paper_fnd.py engine/tests/test_paper_book.py \
                     engine/tests/test_f_fundamental.py -q

# the roster, the migration and the replay (these need PG_TEST_URL)
"$SEER_PY" -m pytest engine/tests/test_paper_roster.py engine/tests/test_migrate.py \
                     engine/tests/test_paper_command.py engine/tests/test_paper_check.py \
                     engine/tests/test_paper_replay.py engine/tests/test_demo.py -q

# the whole suite, which is the gate
"$SEER_PY" -m pytest engine/tests -q
```

**Expected delta** — off whatever this phase inherits, never an absolute (invariant 1):

| | with `PG_TEST_URL` | without |
|---|---|---|
| `test_paper_fnd.py` *(new)* | **+13 passed** | +13 passed |
| `test_paper_book.py` *(new tests)* | **+3 passed** | +3 passed |
| every other file | **0** — same tests, same results, widened literals | 0 |
| **total** | **+16 passed, +0 skipped** | **+16 passed, +0 skipped** |

`test_paper_fnd.py` touches no database, so none of its tests are `pg`-gated and the delta is the
same either way. No existing test changes its result: the edits in `test_paper_roster.py`,
`test_migrate.py` and `test_paper_check.py` widen literals whose tests passed before and pass
after. Phase 1's three `pg` roster tests
(`test_the_migration_rows_equal_the_seed_rows`, `test_the_database_rows_rebuild_the_roster_...`,
`test_read_roster_rows_...`) now see six rows and six seeds and **must still pass unedited** —
that is what `007_fnd.sql` carrying the definition columns buys. If any number other than `+16`
comes out, something regressed — find it before committing.

**Manual check:**

1. `FND` decides against a real panel. On a database with `fundamental_facts` populated
   (the local train database, `SEER_ENV_FILE=$SEER_MAIN/.env.local-train`):

   ```bash
   "$SEER_PY" -m seer_engine --dry-run -v paper --now 2026-11-01T23:00:00Z 2>&1 | grep -i fnd
   ```

   On a decision session this must log `FND <date>: equity …, N position(s), K target(s) for …`
   with `K > 0`. On a database with no facts it must log the same line with no targets and never
   raise — both are correct, and which one you got is decided by `SELECT count(*) FROM
   fundamental_facts`, not by the strategy.

2. `paper_check` replays it:

   ```bash
   "$SEER_PY" -m seer_engine paper_check
   ```

   `FND` must be `ok` (or `not-started` before its first night), never `mismatch`. A mismatch on
   `FND`'s targets means Steps 1 and 2 disagree — the night prepared and the replay did not, or
   the reverse.

**Exit criteria:**

- `ROSTER_IDS == ("SPY", "A", "F4-MOM12-N20-TREND", "F1-SPY-SMA200-M", "C", "FND")`, FND
  `status='active'`, `sort=6`, `engine='book'`, `rules_id='monthly-hold'`.
- `backtest_gate(entry("FND")) == {"passed": False, "note": <the M0005 trial note>}` and no file,
  row, page or log line says FND passed a gate.
- The row was written by `promote --method M0005 --candidate M0005-ALL --id FND
  --lab-status-stays` (or, only if the live database was unreachable, by the Step 6 fallback,
  recorded in the runbook), with `promoted_from='M0005'` and `object_name='FUNDAMENTAL'`.
- `roster.RESOLVER["FUNDAMENTAL"]` is committed, and `roster.FUNDAMENTAL_PARAMS` equals
  `m0005`'s `COMPOSITE` by value — the test that stops the two from drifting.
- `lab/lab.sqlite` carries the promotion (`methods.analysis` grew one `# Promotion` section, one
  `insights` row), `M0005` is still `rejected`, `source_sha` is untouched and no `trials` row was
  added.
- A `Market` with a panel gives `FND` targets; a `Market` with `EMPTY_FUNDAMENTALS` gives it
  exactly `()`, asserted at the roster level by `test_paper_fnd.py`, and `paper_check` replays
  either outcome as `ok`.
- The five pre-existing `spec_digest` values are byte-identical (Step 7).
- `"$SEER_PY" -m pytest engine/tests -q` is `+14 passed` on what the phase inherited.

## Handoffs

- **Phase 4 (`web/`) — `looks()` now has six strategies to colour.** `view.ts:16-17` define
  `CARD_BGS` and `LINES` with four entries each; `looks` (`:26-35`) wraps `CARD_BGS` modulo 4 and
  falls back to `var(--ink-2)` past the fourth line colour. With FND there are five research
  strategies, so two of them collide on one card background. Phase 4's exit criteria already name
  this; this phase does not touch `web/` and leaves it there. **R3, not R1.**
- **Phase 4 — `CHECKS = 6` needs no arithmetic change.** Checked, so phase 4 need not re-derive
  it: `CHECKS` is design §1's five forward rules plus the backtest-gate item, **per strategy**,
  not a count of strategies. FND scores exactly as A/F4/F1 do —
  `{passed: false, applicable: true}` → `['Paper only.', 'Backtest gate not passed']`. The
  checklist reads honestly with a fifth research strategy present without any edit.
- **Phase 4 — `web/scripts/seed-demo.mjs:307` hardcodes the four-horseman roster** and will
  under-seed the demo by one strategy. Phase 4 owns `web/`.
- **Phase 3 (`compare.py`) — FND is the `insufficient` case, and will be for months.** It starts
  with zero common sessions against five strategies that have been running since September. Its
  value to phase 3 is as the test fixture for "a three-week-old method does not win a
  leaderboard". **R3, not R1.**
- **Phase 5 — resolved, nothing is owed.** This plan asked phase 5 for a `--no-lab-record` flag;
  phase 5 ships `--lab-status-stays`, which is the correct answer to the same fact (`rejected` is
  terminal in `lab/lab.sqlite`'s `transitions`) and strictly better, because the promotion is
  still recorded. No handoff remains.
- **Not done here, deliberately: `backtest/registry.py` gains nothing.** `FND` reaches the roster
  through `roster.py`'s own object reference with `registry_id=None`, exactly as `A` and `C` do.
  D1 forbids the alternative and this phase does not test the water.
- **Not done here: re-running M0005.** The method is spent (`source_sha` frozen, six trials,
  `runner.preflight` refuses a second run) and the plan's Scope says so. A future fundamentals
  hypothesis gets a **new** method id, and if it is promoted it gets a **new** roster id with its
  own paper clock — never an edit to `FND` (invariant 3).
- **Noticed, not fixed: `decide_book`'s `resize_cadence` refusal** (`paper/book.py:166-170`) means
  `MONTHLY_RANK_WEEKLY_RESIZE` can never reach the roster. Unrelated to FND, which uses
  `MONTHLY_HOLD`, and out of scope here.

## Rollback

This phase is one commit on `feature/roster-promotion-pipeline`; `git revert` backs out every code
and test change. Reverting Steps 1 and 2 restores `decide_book` and `expected_book` to the
history-only call for every allocator — safe, because no non-`MarketAware` allocator ever took the
new branch.

Three effects outside git:

1. **The `FND` row.** While `FND` has **no `paper_start`** it has traded nothing and nothing
   references it:

   ```sql
   DELETE FROM strategies WHERE id = 'FND' AND paper_start IS NULL;
   ```

   Once it has traded a night, **do not delete it** — retire it, because deleting would destroy
   the record invariant 4 protects and orphan its `equity_snapshots`, `book_*` and `orders` rows:

   ```sql
   UPDATE strategies SET status = 'retired', paper_end = (
     SELECT max(date) FROM equity_snapshots WHERE strategy_id = 'FND'
   ) WHERE id = 'FND';
   ```

   Phase 2's night then skips it and its history stays on the board, marked retired.

2. **`007_fnd.sql`.** It is additive and idempotent; leaving it applied after a code revert leaves
   one unused `strategies` row, which `plan_night` ignores because nothing on the roster names it.
   To undo it, use the `DELETE` above. Do not delete the migration file from a tree whose database
   has already applied it — the ledger would disagree; revert the commit instead.

3. **The lab record.** Step 6 writes to `lab/lab.sqlite` through `promote` — an appended
   `analysis` section and one `insights` row. The lab is append-only by trigger, so neither can be
   deleted; the rollback is `git checkout -- lab/lab.sqlite web/data/lab.json`, which is why the
   database file is committed. Do it *before* any other lab write lands on top. `M0005`'s status,
   `source_sha`, `hypothesis`, `verdict` and six `trials` rows were never written, so nothing else
   in the lab needs undoing.
