> Adopted from `DELISTING_STRESS_ROSTER_RULES_PLAN.md` phase 4. Source: `.workflows/plan/delisting-stress-roster-rules/phase-4.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 4: A test that pins the dev gate's trades bar

**Plan set:** `DELISTING_STRESS_ROSTER_RULES_PLAN.md`
**Analysis:** `20261007-170515-0CU0_code_analyzer.md`
**Satisfies:** R2 — Q2, *"is go-live item 1 calibrated?"*. The owner decided it on 2026-10-07 and
session `seer-fc` has implemented the decision, including a design §13 that records the dev-gate
asymmetry in full. What is left, and all this phase owns, is the executable half: nothing in the
suite fails if `dev._MIN_TRADES` moves.
**Depends on:** none
**Difficulty:** EASY
**Package:** `engine/tests`

> **Revised mid-planning, 2026-10-07, on the coordinator's instruction.** The first draft of this
> phase also added `docs/handover/2026-10-07-dev-gate-trades-bar.md`. `seer-fc` landed design §13
> plus explanatory comments at `backtest/dev.py:86-90`, `backtest/dev_report.py:57` and
> `backtest/tuning.py:44`, which covers everything that note was going to say. **The note is dropped
> as pure duplication.** This phase is now one new file.

---

## Goal

After this phase, moving `backtest.dev._MIN_TRADES` fails the engine suite with a message that
explains why the dev-window gate keeps a trades bar that design §1 item 1 no longer has, points the
reader at design §13 and at the comment above the constant, and says what the change costs. The
measurement §13 rests on — 2 of 110 trials held out by the bar, both carrying `dsr IS NULL`, so
dropping it changes zero eligibility verdicts — is re-taken from the committed lab database on every
CI run instead of only being written down.

Nothing executable changes: `_MIN_TRADES` stays at 100, the 110 recorded dev trials keep the basis
they were judged on, and the lab's N stays at 110.

**Why this is still worth a phase after §13 landed.** `seer-fc`'s protection is three prose comments
and a design section. A comment cannot notice when someone deletes the line beneath it. Verified:
`grep -rn "_MIN_TRADES" engine --include="*.py"` returns only `backtest/dev.py:86,379` and
`lab/store.py:990,1019,1200,1319,1320,1876` — **no test file pins it**. A pinning test is this
repo's own idiom for a constant that carries a decision: `web/lib/golive.test.ts` pins the two
`MAX_DRAWDOWN` definitions to each other, `test_lab_npolicy.py`'s
`test_the_shipped_defaults_reproduce_todays_n` holds N at 110, and `test_lab_gate_wording.py` holds
every shipped gate label to the live constants.

## Interface Contract

**Deletes:** nothing
**Renames:** nothing
**Creates:** one new file, `engine/tests/test_dev_trades_bar.py` — module constants `TRADES_BAR`,
`PAPER_MONTHS`, `RECORD`, `TRADES_LABEL`, `HELD_OUT_BY_THE_TRADES_BAR`, and three test functions.
No package exports a new symbol; the module is collected by pytest and imported by nothing.
**Signature changes:** none
**Requires (from earlier phases):** none. `depends_on` is empty and the file reads only symbols that
exist at the plan's base commit, and at `ba8a05b` which the branch is now merged to.
**Requires (from outside the plan set):** nothing, in either direction. The test passes **both**
before and after `seer-fc`'s §13 revision reaches this branch — verified by running it against both
trees (see Step 2). It reads `tuning.MIN_PAPER_MONTHS` through `getattr(..., None)` and never
imports it unconditionally, because that symbol does not exist at `3683d7b`.
**Leaves alone (owned by others):**
- `engine/src/seer_engine/backtest/dev.py` — imported and read, never written. Specifically **not**
  `_MIN_TRADES` (`dev.py:86`), **not** `FAILURE_LABELS` (`dev.py:71-79`), **not** the comment
  `seer-fc` added above the constant.
- `docs/plans/2026-10-03-seer-design.md` — §1, §5 and the new §13 are `seer-fc`'s and are forbidden
  by the lab skill's standing guardrails. The test *cites* §13 in its failure messages; this phase
  writes no documentation at all.
- Every other file `seer-fc` claimed or has modified: `backtest/metrics.py`, `backtest/tuning.py`,
  `backtest/dev_report.py`, `backtest/report.py`, `backtest/b_report.py`, `backtest/wf_report.py`,
  `backtest/walkforward.py`, `backtest/b_walkforward.py`, `web/lib/golive.ts`, `web/lib/metrics.ts`,
  `web/lib/golive.test.ts`, and `engine/tests/test_backtest_{tuning,metrics,walkforward,b_walkforward,report,b_report}.py`.
  `test_backtest_tuning.py` being both claimed and already modified is why this guard gets its own
  module.
- `lab/lab.sqlite` — opened read-only (`store.connect_readonly`, `mode=ro`), never written. No
  trial, no insight, N stays 110, 0 test-window looks stay 0.
- Phase 1's `engine/src/seer_engine/delisting.py`, `engine/scripts/delisting_stress.py` and
  `engine/tests/test_delisting.py`; phase 2's and phase 3's design-doc sections; phase 5's
  `docs/handover/2026-10-07-mom-fr-under-the-replacement-rule.md`.

**Nothing downstream depends on this phase.** No later phase reads this file, no code imports the
test module, and no symbol is created, renamed or removed. The reconciler can schedule this phase
anywhere in the set, or drop it, without touching another plan.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/tests/test_dev_trades_bar.py` | create | new file, no line reference — the complete text is in Step 2 |

Read-only reference points the test imports or cites, none of which this phase may edit:

| File:line | What is there | Why this phase reads it |
|---|---|---|
| `engine/src/seer_engine/backtest/dev.py:86` | `_MIN_TRADES = 100`, under `seer-fc`'s comment ending *"Not yours to 'tidy'."* | the constant being pinned |
| `engine/src/seer_engine/backtest/dev.py:71-79` | `FAILURE_LABELS`, 4th entry `">= 100 trades"` | the test unpacks it rather than hardcoding the label |
| `engine/src/seer_engine/backtest/dev.py:375-382` | `make_row`'s `passed` tuple, `m.trades >= _MIN_TRADES` | where the bar is actually applied |
| `engine/src/seer_engine/backtest/tuning.py:45` *(post-§13 only)* | `MIN_PAPER_MONTHS = _metrics.MIN_PAPER_MONTHS` | the forward-paper dial; absent at `3683d7b`, read with `getattr` |
| `engine/src/seer_engine/lab/store.py:980-1023` | `owner_failures` | the correct way to re-judge a recorded trial against today's constants |
| `engine/src/seer_engine/lab/store.py:57,377` | `COMMITTED_DB`, `connect_readonly` | read-only access to the committed lab database |
| `docs/plans/2026-10-03-seer-design.md` §13 *(post-§13 only)* | *"Revision 2026-10-07 (owner): go-live item 1 is 18 months, and counts no trades"* | what every failure message points at |
| `docs/plans/2026-10-04-method-lab-design.md:127-157` | lab design §7.1 | "a luck test that cannot be evaluated is one that was not passed" |
| `docs/plans/2026-10-04-method-lab-design.md:263-280` | lab design §7.6 | the 54 P7a seed trials with `dsr IS NULL`, and `lab remeasure`'s seed path |
| `.github/workflows/engine-ci.yml:65-73` | `grep -q '^SKIPPED' pytest.out && exit 1` | why the test may not use `pytest.skip` — see Step 2 |

## Implementation Steps

### Step 1: Take the current `origin/main`, then record which world this branch is in

**File:** none — a working-tree step.
**Change:** rebase onto the latest `origin/main` so the test runs against whatever `seer-fc` has
actually landed, then note which of the two states is true. **The test in Step 2 passes either way**
— this check is for the implementer's confidence and for the verification numbers, not for a branch
in the code.

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules
git fetch origin
git merge --no-edit origin/main   # MERGE, never rebase -- see below
grep -n "18 months\|100 closed trades" docs/plans/2026-10-03-seer-design.md
grep -n "MIN_PAPER_MONTHS" engine/src/seer_engine/backtest/tuning.py
sed -n '80,92p'  engine/src/seer_engine/backtest/dev.py
```

**Never `git rebase` here.** The original draft of this step said rebase. This worktree is shared
with the other phases of the set running concurrently; rebasing rewrites their commits out from
under them. Phase 2 and the plan index both say merge, and so does this phase now.

**Read the result as follows:**

- **Landed** — `tuning.py` defines `MIN_PAPER_MONTHS`, design §1 item 1 reads *"≥ 18 months of
  forward paper trading"*, §13 exists, and `dev.py:86` carries the new comment. All three tests in
  Step 2 assert; expect **3 passed**.
  **This is the world the branch is already in** — verified by the reconciler on 2026-10-07 at
  `origin/main` @ `ba8a05b`: `metrics.py:32` defines `MIN_PAPER_MONTHS = 18`, `tuning.py:45`
  re-exports it, design §1 item 1 reads *"≥ 18 months of forward paper trading"*, `§13` exists at
  line 232, and `dev.py:85-89` carries the comment ending *"Not yours to 'tidy'."* Expect **3
  passed**.
- **Not landed** — none of the above; the branch is back before `ba8a05b`, where §1 item 1 reads
  *"≥ 3 months of forward paper trading **and** ≥ 100 closed trades"*. The second test's forward-bar
  assertion is inert and the other two still assert; expect **3 passed, 0 skipped**. **This branch
  is no longer reachable from the current `origin/main`**; the dual-world design is kept only so
  the test cannot be broken by a revert.

**Verified by running the Step 2 file against both trees** (the worktree at `3683d7b`, and the main
checkout with `seer-fc`'s uncommitted work applied): 3 passed in each, 0 skipped in each.

**Do not implement the §13 change yourself in either case**, and do not block on it. Design §1 and
§13 are `seer-fc`'s, and the lab skill's standing guardrails
(`docs/plans/2026-10-04-method-lab-design.md:75`) forbid editing §1 from here.

**Impact:** none to the tree. If the rebase conflicts, the conflicts are in peer phases' files — this
phase's only file is new and unique to it.

### Step 2: Write the guard test

**File:** `engine/tests/test_dev_trades_bar.py` (new file)
**Change:** create it with exactly the text below.

Three things about its shape, each of which was a decision:

1. **It is its own module**, not a case in `engine/tests/test_backtest_tuning.py`. That file is
   claimed by `seer-fc` and is already modified in the shared checkout; and the explanation is the
   payload here, which does not belong inside a tuning-dial test.
2. **No `pytest.skip`, anywhere.** `tuning.MIN_PAPER_MONTHS` does not exist at `3683d7b`, so the
   obvious move is to skip that half — and it is not available. `.github/workflows/engine-ci.yml:65-73`
   runs `pytest -q -rs | tee pytest.out` and then `grep -q '^SKIPPED' pytest.out && exit 1`: **any**
   skipped test fails the job, by design, because a silently skipped suite is how 385 Postgres-gated
   tests once passed for free. The second test therefore asserts something true in both worlds first
   and returns early from the half that cannot yet apply.
3. **Live constants, never `trials.failed`.** All 110 recorded rows carry the superseded
   `"DSR >= 0.95"` label and the superseded 15% drawdown bar, because `trials` is append-only and a
   recorded label names the bar in force on its run date. `store.owner_failures` is the function that
   re-judges a row against today's constants, and the third test uses it.

The text below was drafted and run against this worktree before this plan was written: **3 passed,
0 skipped** on the pre-§13 tree and **3 passed, 0 skipped** on the post-§13 tree, and
`ruff check --no-cache` clean on both.

**Code:**

```python
"""The dev-window gate keeps its 100-closed-trades bar; design §1 item 1 no longer has one.

That asymmetry is deliberate, dated and recorded -- design §13, "Revision 2026-10-07 (owner):
go-live item 1 is 18 months, and counts no trades", and the comment above the constant itself at
``backtest/dev.py``. What it did not have was anything that fails. Three prose comments and a design
section are the right record and the wrong guard: a comment cannot notice when someone deletes the
line beneath it.

**The thing being guarded.** The owner replaced item 1's "≥ 100 closed trades" with "≥ 18 months of
forward paper trading" on 2026-10-07, because a trade count scales with how many names a book holds
rather than with how much evidence exists about it. The dev-window gate -- which design §1 item 5's
"identical rules" applies to every lab candidate -- kept its own trades condition. The next reader to
find one gate asking for trades and the other not will reasonably try to make them agree, and the
cheap way to make them agree is to delete ``_MIN_TRADES``. That silently re-judges the recorded basis
of all 110 dev trials: ``lab.store.owner_failures`` and ``lab.store.published_verdict`` re-derive
every verdict from this constant **at read time**, and ``trials`` is append-only, so the rows stay
byte for byte while what they mean changes underneath the leaderboard.

This file is the house guard for exactly that shape of mistake, next to
``web/lib/golive.test.ts`` (which pins the two ``MAX_DRAWDOWN`` definitions to each other),
``test_lab_npolicy.py``'s ``test_the_shipped_defaults_reproduce_todays_n`` (which holds N at 110) and
``test_lab_gate_wording.py`` (which holds the shipped gate labels to the live constants).

**Written against the live constants, never against ``trials.failed``.** All 110 recorded rows carry
the superseded ``"DSR >= 0.95"`` label and the superseded 15% drawdown bar, because ``trials`` is
append-only and a recorded label names the bar in force on its run date. ``store.owner_failures`` is
the function that re-judges a recorded row against today's constants, and the third test uses it.

It is its own module rather than a case in ``test_backtest_tuning.py`` because that file belongs to
the session that landed the §13 revision, and because the failure messages below are the payload --
not the assertions.
"""

from __future__ import annotations

import sqlite3

from seer_engine.backtest import dev, tuning
from seer_engine.lab import store

#: The dev-window bar as the owner left it on 2026-10-07. A literal, not a reference: a guard that
#: reads the value it guards from the thing it guards passes unconditionally.
TRADES_BAR = 100

#: The forward-paper bar design §1 item 1 now states, in months. ``None`` on a tree that predates the
#: §13 revision, which the second test returns early on rather than skipping -- CI fails on any
#: skipped test, and the asymmetry being described does not exist on such a tree anyway.
PAPER_MONTHS: int | None = getattr(tuning, "MIN_PAPER_MONTHS", None)

#: The dated record of the decision, for every failure message below to point at.
RECORD = "docs/plans/2026-10-03-seer-design.md §13"

#: The label ``dev.make_row`` writes into ``trials.failed`` when the trades bar is the miss.
#: Unpacked in ``FAILURE_LABELS`` order, exactly as ``store.owner_failures`` unpacks it.
_SPY, _DRAWDOWN, _PF, TRADES_LABEL, _OWNER = dev.FAILURE_LABELS

#: Measured 2026-10-07 against the committed lab database, read-only, with no trial recorded and the
#: lab's N unmoved at 110: the only recorded dev trials whose **sole** miss against today's five
#: owner conditions is the trades bar. 26 of 110 clear all five with the bar; 28 without it. Both are
#: P7a seed trials carrying ``dsr IS NULL`` -- which is what the third test is really about.
HELD_OUT_BY_THE_TRADES_BAR: tuple[tuple[str, int], ...] = (
    ("F1-SPY-10MSMA-M", 13),
    ("F1-SPY-SMA200-M", 11),
)


def test_the_dev_window_gate_still_requires_a_hundred_closed_trades() -> None:
    """``dev._MIN_TRADES`` is 100, and the reason it is 100 is no longer the reason it once was."""
    assert dev._MIN_TRADES == TRADES_BAR, (
        f"`backtest.dev._MIN_TRADES` is {dev._MIN_TRADES}, not {TRADES_BAR}.\n"
        f"\n"
        f"If you changed it because design §1 item 1 no longer mentions trades: please change it\n"
        f"back, and read {RECORD} and the comment above the constant in\n"
        f"backtest/dev.py before deciding again. The owner deleted item 1's trades clause on\n"
        f"2026-10-07 and left this one standing on purpose. The two gates ask different questions:\n"
        f"item 1 asks how much forward evidence a strategy has accumulated making real decisions,\n"
        f"which is a question about time -- hence 18 months -- and the dev-window gate asks whether\n"
        f"a 20-year backtest produced enough closed trades for its profit factor and drawdown to\n"
        f"mean anything, which is a question about sample size. Deleting the clause from item 1 was\n"
        f"right. Deleting it here moves the sample-size problem out of condition 1 and into\n"
        f"condition 3: the two trials this bar holds out score profit factors of 75.45 and 14.48\n"
        f"off 11 and 13 closed trades over twenty years, and neither number means anything.\n"
        f"\n"
        f"It is also not a free edit. All 110 recorded dev trials were judged against this\n"
        f"constant; `lab.store.owner_failures` and `lab.store.published_verdict` re-judge them\n"
        f"against it at read time, and `trials` is append-only -- so moving it re-decides what the\n"
        f"lab's whole record means without leaving a mark anywhere. That may still be the right\n"
        f"call one day. It is an owner decision, it needs a dated revision in\n"
        f"docs/plans/2026-10-03-seer-design.md alongside §13, and it is not a tidy-up.\n"
        f"\n"
        f"If the owner has since decided to move it: record the decision and its date in the design\n"
        f"doc, then set TRADES_BAR here to the new value."
    )


def test_the_forward_paper_bar_and_the_dev_trades_bar_are_two_separate_dials() -> None:
    """The dev gate still has a trades condition, and §1 item 1's bar is a dial of its own.

    There is no arithmetic relationship to assert between 18 months and 100 trades, and inventing
    one would be worse than asserting nothing: §13's point is precisely that the forward gate
    stopped counting trades, so any equation tying the two together would re-introduce the coupling
    the owner removed. What is worth pinning is that **both dials exist and each is held to its own
    value**, so moving one can never quietly carry the other along.

    **Why the second half is conditional and not a ``pytest.skip``.** ``tuning.MIN_PAPER_MONTHS``
    arrives with the §13 revision and does not exist on a tree that predates it, so this file must
    pass on both. A skip is not available: ``.github/workflows/engine-ci.yml`` greps the run for
    ``^SKIPPED`` and fails the job on any hit, because a silently skipped suite is how 385
    Postgres-gated tests once passed for free. The first assertion below therefore holds in both
    worlds and the second is inert until the revision merges.
    """
    assert TRADES_LABEL in dev.FAILURE_LABELS, (
        f"`dev.FAILURE_LABELS` no longer carries a closed-trades condition.\n"
        f"\n"
        f"The dev-window gate keeps its trades bar even though design §1 item 1 dropped one\n"
        f"({RECORD}); removing the label removes the condition from every candidate the lab screens\n"
        f"and from the `failed` string every future trial records. If that is intended it is an\n"
        f"owner decision with a dated revision behind it, and this test is what to update once that\n"
        f"revision exists."
    )
    if PAPER_MONTHS is None:
        return
    assert PAPER_MONTHS == 18, (
        f"`tuning.MIN_PAPER_MONTHS` is {PAPER_MONTHS}, not 18.\n"
        f"\n"
        f"That is design §1 item 1's forward-paper bar, set by the owner on 2026-10-07 ({RECORD}).\n"
        f"It is an owner dial and it moves by a dated revision, not by a code change. If the owner\n"
        f"moved it, record that and update this test.\n"
        f"\n"
        f"Note what this test does NOT say: it does not tie 18 months to the dev gate's 100 trades\n"
        f"in any way. They are two dials with two units measuring two different things, and §13's\n"
        f"whole point is that the forward gate stopped counting trades. Moving this one is never a\n"
        f"reason to move `dev._MIN_TRADES`, and moving that one is never a reason to move this."
    )


def test_the_trades_bar_holds_out_two_trials_and_neither_of_them_has_a_luck_score() -> None:
    """The measurement §13 rests on, re-taken from the committed database on every run.

    This is the fact that made the asymmetry cheap rather than merely defensible: the two trials the
    dev trades bar holds out are both P7a seed imports with ``dsr IS NULL``, and under method-lab
    design §7.1 a luck test that cannot be evaluated is one that was not passed. So dropping the bar
    today would newly clear two candidates through the five owner conditions and change **zero**
    eligibility verdicts. The sample-size argument binds future trials that do carry a DSR; it does
    not bind these two, and §13 says so.

    The set is recomputed from the recorded columns against the live constants, never parsed out of
    ``trials.failed``. It can therefore move for a legitimate reason -- the owner lowering
    ``tuning.MAX_DRAWDOWN`` would drop both of these out of it, since they sit at 18.7% and 18.9%
    against today's 20% bar. That is not a bug in this test: it means §13's measurement has gone
    stale, and §13 is what to update.

    Read-only: ``mode=ro``, no trial recorded, the lab's N unmoved at 110, no test-window look spent.
    """
    conn: sqlite3.Connection = store.connect_readonly(store.COMMITTED_DB)
    try:
        rows = conn.execute("SELECT * FROM trials WHERE window = 'dev'").fetchall()
    finally:
        conn.close()

    held_out = sorted(
        (str(r["candidate_id"]), int(r["trades"]), r["dsr"])
        for r in rows
        if store.owner_failures(r) == (TRADES_LABEL,)
    )
    assert [(name, count) for name, count, _ in held_out] == list(HELD_OUT_BY_THE_TRADES_BAR), (
        f"the set of recorded dev trials whose only miss is the trades bar has changed.\n"
        f"Measured 2026-10-07 and written into {RECORD}: {list(HELD_OUT_BY_THE_TRADES_BAR)}.\n"
        f"Measured now:{' ' * 31}{[(name, count) for name, count, _ in held_out]}.\n"
        f"\n"
        f"This set is recomputed from the recorded columns against the live constants, so an owner\n"
        f"moving `tuning.MAX_DRAWDOWN`, `tuning.MIN_PROFIT_FACTOR` or `dev._MIN_TRADES`\n"
        f"legitimately changes it. If that is what happened, re-take the measurement and update\n"
        f"both this list and the one in {RECORD}, whose argument is built on it."
    )
    scored = [(name, count, dsr) for name, count, dsr in held_out if dsr is not None]
    assert not scored, (
        f"a trial held out by the dev trades bar now carries a luck score: {scored}.\n"
        f"\n"
        f"{RECORD} argues that dropping the dev trades bar would change zero eligibility verdicts\n"
        f"today, and the whole of that argument is that both held-out trials are P7a seed imports\n"
        f"with `dsr IS NULL` -- under method-lab design §7.1 a luck test that cannot be evaluated is\n"
        f"one that was not passed, so the trades bar is not what is keeping them out. `lab\n"
        f"remeasure`'s seed path (method-lab design §7.6) can give a seed trial a DSR, and if it has\n"
        f"given one to a trial in this set, re-check whether that trial now clears the luck bar and\n"
        f"rewrite §13's 'zero verdicts actually change' finding before anyone leans on it again."
    )
```

**Impact:** +3 tests in the engine suite, +0 skipped. None touches Postgres, so none is affected by
`PG_TEST_URL`; the third reads `lab/lab.sqlite` read-only through `store.connect_readonly`
(`mode=ro`, no schema, no migration, no write). Runtime measured at 0.89–1.18s for the three. No
existing test changes behaviour — nothing else in the suite asserts on `_MIN_TRADES`, verified by the
grep quoted under **Goal**.

### Step 3: Confirm nothing outside this phase's one file changed

**File:** none — a working-tree check.
**Change:** this phase runs in a worktree shared with the other phases of the set, so peers' edits
show up in `git status`. Confirm this phase added exactly one file and modified none.

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules
git status --porcelain -- engine/tests engine/src docs
git diff --stat -- engine/src docs lab web
```

The second command must print **nothing attributable to this phase**. If it shows a diff against
`backtest/dev.py` or `docs/plans/2026-10-03-seer-design.md`, either this phase has broken its own
contract or it is seeing a peer's in-flight edit — check `git diff` before assuming the former.

Commit with an explicit path allowlist; the worktree is shared and `git add -A` would sweep a peer
phase's half-finished work into this commit:

```bash
git add engine/tests/test_dev_trades_bar.py
git commit -F - <<'MSG'
test(backtest): pin the dev gate's trades bar, which design §1 item 1 no longer has

The owner deleted item 1's trades clause on 2026-10-07 (design §13) and left the
dev-window gate's _MIN_TRADES = 100 standing. seer-fc protected that asymmetry with
prose -- a design section and three comments -- and a comment cannot notice when
somebody deletes the line beneath it. This is the executable half.

Three tests: the constant is still 100, the failure message explains why the two gates
differ and what moving it costs, and the measurement §13 rests on (exactly two of the
110 recorded trials held out by the bar alone, both with no luck score, so zero
eligibility verdicts change today) is re-derived from the committed lab database on
every CI run instead of only being written down.

Nothing executable changes. The lab is opened read-only: N stays 110, 0 test-window
looks stay 0.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
git show --stat --name-only HEAD   # must list exactly that one path
```

**Impact:** none. A verification step.

## Verification

Postgres first — the suite skips 385 tests silently without it, and CI fails on any skip:

```bash
docker start seer-pg   # idempotent; it is usually already up
```

**Build:** Python has no compile step. The lint gate is:

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine && \
  /home/miftah/seer/engine/.venv/bin/python -m ruff check --no-cache src tests
```

Expect `All checks passed!`. Verified against the Step 2 text on both trees.

**Tests — this phase's three, first:**

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine && \
  PYTHONPATH=/home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine/src \
  PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  /home/miftah/seer/engine/.venv/bin/python -m pytest -q -rs tests/test_dev_trades_bar.py
```

Expect **`3 passed`** and **no `SKIPPED` line**, whether or not §13 has reached the branch.
Measured at 1.18s pre-§13 and 0.89s post-§13.

**Tests — the full suite:**

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine && \
  PYTHONPATH=/home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine/src \
  PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  /home/miftah/seer/engine/.venv/bin/python -m pytest -q -rs
```

Both environment variables are mandatory, for different reasons:

- **`PYTHONPATH`** — `engine/.venv` has `seer_engine` installed editable against the **main
  checkout**'s `src`. Without it pytest silently tests `/home/miftah/seer` rather than this branch,
  and this phase's third test would read the main checkout's `lab/lab.sqlite` through
  `store.COMMITTED_DB` (which resolves via `config.REPO_ROOT`, derived from the imported package's
  own path).
- **`PG_TEST_URL`** — without it the suite reports **2812 passed / 385 skipped** instead of
  **3197 / 0**. Both read as "green". Never report a pass count taken without it, and note that
  `.github/workflows/engine-ci.yml:65-73` fails the job on any `^SKIPPED` line, so a skipped run is
  a red run, not a quiet one.

Do **not** add `-o addopts="-ra"`. `pytest-xdist` is installed in that venv (verified: 3.8.0 against
pytest 9.1.1), `addopts = "-ra -n auto"` works, and overriding it costs about 5.5× wall clock.

Expected: **3200 passed, 0 skipped, 0 failed** — the 3197 of the base tree (re-counted by the
reconciler at `ba8a05b`, unchanged by `seer-fc`'s go-live commit) plus this phase's 3 — *if this
phase is the only one that has landed in the shared worktree*. Peer phase 1 adds tests of its own,
so the absolute number will be higher once it lands. **What this phase asserts
is `0 failed` and `0 skipped`, and that `tests/test_dev_trades_bar.py::` contributes exactly 3
passes.**

**Manual check — read the failure message, which is the whole point of the test.** Render it without
editing `dev.py`, by moving the constant in memory only:

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine && \
  PYTHONPATH=/home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine/src:tests \
  /home/miftah/seer/engine/.venv/bin/python - <<'PY'
from seer_engine.backtest import dev
dev._MIN_TRADES = 0
import test_dev_trades_bar as t
try:
    t.test_the_dev_window_gate_still_requires_a_hundred_closed_trades()
except AssertionError as e:
    print(e)
else:
    print("NO FAILURE -- the guard does not read the live constant")
PY
```

Read what it prints as if you were the engineer who had just made that change for tidiness. It must
name design §13 and the `dev.py` comment, say why the two gates differ, and say what moving the
constant costs — without requiring the reader to already know any of it. **This mutates nothing on
disk**; confirm with `git diff -- src/seer_engine/backtest/dev.py`, which must be empty.

**Also confirm the two invariants this phase could break:**

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules && \
  PYTHONPATH=engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab status | head -20
git status --porcelain lab/lab.sqlite      # must print nothing
```

`lab status` must still report **N = 110** and **0 test-window looks**, and `lab/lab.sqlite` must be
unmodified.

**Exit criteria:**

1. `engine/tests/test_dev_trades_bar.py` exists and its 3 tests pass with **0 skipped**, on whichever
   side of `seer-fc`'s §13 revision the branch happens to be.
2. Moving `_MIN_TRADES` in memory makes the first test fail with prose a surprised engineer can act
   on, naming design §13 and the comment above the constant.
3. The third test re-derives the measurement §13 states — exactly `F1-SPY-10MSMA-M` (13 trades) and
   `F1-SPY-SMA200-M` (11 trades) held out by the trades bar alone, both with `dsr IS NULL` — from the
   committed lab database rather than from a hardcoded claim.
4. `engine/src/seer_engine/backtest/dev.py`, `docs/plans/2026-10-03-seer-design.md` and every other
   `seer-fc`-claimed file show no diff from this phase; the commit lists exactly one path.
5. `ruff check --no-cache src tests` is clean; the full suite is `0 failed, 0 skipped` with both
   environment variables set; `lab status` reports N = 110 and 0 test-window looks; `lab/lab.sqlite`
   is unmodified.

## Handoffs

Found while planning, deliberately **not** done here, with the owner of each. None blocks this phase
and none changes behaviour.

1. **The handover note this phase originally owned is cancelled, not deferred.** Design §13 carries
   the asymmetry, the measurement (2 of 110, PF 75.45 and 14.48 off 11 and 13 trades) and the
   `dsr IS NULL` finding. A second document saying the same thing would be the kind of duplicate
   record that goes stale first and then misleads. **Nobody should write it.**
2. **`docs/plans/2026-10-03-seer-design.md` §11's recap** (`:149-151` at `3683d7b`) still reads
   *"nothing trades real money without ≥ 3 months of forward paper and ≥ 100 closed trades"*,
   superseded by the same-day item 1 revision. **Belongs to `seer-fc`**, which owns §1, §11 and §13.
   Worth confirming it was swept when §13 landed; this phase may not touch it.
3. **Whether `F1-SPY-SMA200-M` and `F1-SPY-10MSMA-M` should be luck-tested.** `lab remeasure`'s seed
   path (method-lab design §7.6) could give both a DSR, which would turn §13's "zero verdicts change"
   from a fact into a question. That is lab work, it is no phase of this plan set, and this phase's
   third test is what will flag it if it happens.
4. **Nothing for R1, R3 or R4.** This phase found no work belonging to phases 1, 2, 3 or 5, and
   serves no requirement other than R2.

## Rollback

`git revert` this phase's single commit, or delete the one file it adds:

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules
rm engine/tests/test_dev_trades_bar.py
```

Nothing else is affected. The phase modifies no existing file, migrates no database, writes no trial,
changes no `config_digest`, spends no test-window look and moves no N — so there is nothing for a
rollback to repair. The suite returns to its prior pass count and every other phase of the set is
unaffected, since no phase reads this file.
