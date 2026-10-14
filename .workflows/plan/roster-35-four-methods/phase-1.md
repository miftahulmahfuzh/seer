# Phase 1: M0156 — the roster's other book on the honest tape

**Plan set:** `ROSTER_35_FOUR_METHODS_PLAN.md`
**Analysis:** `docs/analyzer/20261014-150738-B7K4_code_analyzer.md`
**Satisfies:** R3 (M0156 — survivorship-check `M0002-REL-85`, the roster book never checked at all), R6 (no test-window look is spent)
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab`

---

## Goal

The paper roster holds two books the owner mirrors with his own money. One of them —
`MOM-FR-GT`, which is `M0002-REL-85` — has never been read on the survivorship-check store in any
form, and has never been run as a lab trial at the fees and share basis the owner actually pays.
After this phase both holes are closed: the free report says what the missing companies do to
M0002's recorded book, and one new method id carries that book at five widths on the owner's real
trading basis, read on both price histories as a single paired curve.

---

## What the idea row says, and what the code says back

`M0156` is already an `idea` row (`parent_id = M0152`, `family = stock-momentum-risk-managed`).
Its frozen hypothesis sets two steps. Both are read here as the specification.

**Step one** — `lab survivorship M0002` — is free: it records no trial, no moments, no funding and
no status, so `store.dev_trial_count` and `store.test_looks` cannot move
(`lab/survivorship_check.py` module docstring; `commands/lab.py:_survivorship` prints both before
and after).

**Step two** is conditional. The idea's own failure branch:

> Failure: M0002's recorded trials are at a cost model or share basis that makes the check-store
> re-run non-comparable, in which case step two becomes a realistic twin at real fees first (the
> `redo-sera-experiments` shape) and the survivorship read follows it.

**That branch fires, and it is settled by the record, not by judgement.** Every recorded M0002
trial (`#75`–`#80` dev, `#131` test) is at `rules_id = monthly-hold`:

```
rules=TradeRules(id='monthly-hold',engine='book',cadence='monthly',entry='open_limit',
  max_positions=None,time_stop=None,resize=True,fractional=False,dividends=True,
  idle_symbol=None,cost_rate=0.001)
```

- `fractional=False` — whole shares. The owner trades fractionally.
- `cost_rate=0.001` with the flat cost model — not Gotrade's measured schedule.
- No `trial_funding` row for any of `#75`–`#80` — **unfunded**, at 20,000,000 IDR of static
  capital. M0152's curve is funded (10,000,000 IDR opening, +5,000,000 IDR on the 25th, 237
  deposits) and `seer-lab-runner-is-unfunded` forbids sharing a return column between a funded
  trial and an unfunded one.
- `resize_basis` is the old equity basis, which `seer-resize-band-never-fires` shows never fires —
  the tape does not invest the deposits.

Three independent mismatches against the basis M0152 measured the other roster book on. So the
step-one report is a real reading of the *picking rule*, and is **not** a reading of the owner's
book. Step two is therefore both the realistic twin and the width sweep, in one method id.

---

## The decision this plan is required to make and write down: a new id, not an amendment

**Spend `M0156`. Do not amend.** The argument, in the order the code forces it:

1. **Amending `M0002` is mechanically impossible.** `runner.AMEND_CLOSED = ("promoted",
   "test-passed", "test-failed", "paper")` (`lab/runner.py:210`). `M0002` reads `test-failed`.
   `lab run --amend M0002` is refused before anything loads, and the refusal is correct: design §3
   gives one look per configuration and a tested book that kept growing variants under its own id
   would be the fishing the pre-registration exists to stop.
2. **Amending `M0152` is possible and wrong.** `M0152` reads `dev-eligible`, so it *is* amendable.
   But (a) it is a different allocator — `RESIDMOM` against `REGIME` — and a different family
   (`stock-residual-momentum` against `stock-momentum-risk-managed`); (b) `store.best_dev_eligible`
   returns exactly one variant per method and that is the single variant `promote`
   pre-registers — an amendment would make `M0152`'s one promotion candidate a choice *between two
   different picking rules*; and (c) `M0152`'s own committed hypothesis says of this very book
   "Not fixable inside this method id; it will be named in the verdict and queued as the next
   idea." That sentence is frozen pre-registration. Overriding it to save an N is exactly the kind
   of after-the-fact convenience the freeze exists to refuse.
3. **The N cost is real but small, and measurable rather than assumed.** `store.DSR_POLICY =
   "methods"`, and `npolicy.effective_n` computes `n = max(dev_method_count, ceil(participation_
   ratio))`. Measured on the committed database today: **94 distinct methods have a dev trial**
   (469 dev trial rows, 170 method rows). So minting M0156 moves N from 94 to 95 — a 1.1% move,
   applied retroactively, against the 1-in-75 scale the `Amendment` docstring was written against
   in October 2026. It is not free and the plan says so; it is also not the deterrent it was.
4. **No new id is actually spent.** `M0156` is already reserved as an `idea` row. The alternative
   to running it is `lab drop M0156`, which spends the id anyway and buys nothing.
5. **Promotion is not sought and is not available.** The line runs through `M0002`, which is
   test-failed, so the hard gate refuses on kin whatever the arms score. The deliverable is a
   roster number, not a candidate — so M0156's own DSR verdict is not what the +1 N endangers.

---

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates:**
- `seer_engine.lab.methods.m0156_regime_book_width.METHOD` — new file
  `engine/src/seer_engine/lab/methods/m0156_regime_book_width.py`
- `seer_engine.lab.methods.m0156_regime_book_width.WIDTHS`, `REL85`, `_picks`, `_v`
- five new dev trial rows under `method_id = 'M0156'` (candidates `M0156-N20`, `-N25`, `-N30`,
  `-N35`, `-N45`), plus their `trial_moments`, `trial_funding`, `trial_provenance` and one
  `method_folds` row
- `methods` row `M0156` moves `idea -> registered -> (dev-eligible | rejected)`; `name`,
  `hypothesis`, `family`, `source_kind`, `source_ref` and `parent_id` are **overwritten from the
  method file** by `runner.run_method` (`lab/runner.py:719-727`) because the row reads `idea`
- two `insights` rows of kind `observation` (one per `lab survivorship` invocation)
- `docs/lab/survivorship/mom-book-2026-10-14.csv` (step one's grid)
- `docs/lab/survivorship/mom-width-curve-2026-10-14.csv` (step two's grid)
- `docs/lab/survivorship/mom-width-curve-2026-10-14.md` (the paired curve, trough dates, eras)

**Signature changes:** none. No existing module is edited.

**Requires (from earlier phases):** nothing. This phase has no `depends_on`.

**Leaves alone (owned by others):**
- `docs/lab/survivorship/grid.csv` — `survivorship_record.GRID_PATH` points hard-gate D16 at that
  exact file. Never appended to, by this phase or any other.
- `engine/src/seer_engine/paper/roster.py`, `strategies/evidence.py`, `db/migrations/021_*.sql`,
  the roster test pins — Phase 2. **This phase produces `MOM-FR-GT`'s number and does not act on
  it.** Phase 2 changes `RAW-FR-GT` only.
- `lab/methods/m0155_*.py` (Phase 3), `m0149_*.py` (Phase 4), `m0148_*.py` (Phase 5).
- `engine/src/seer_engine/lab/methods/m0002_asymmetric_vol_regime.py`,
  `m0007_residual_momentum.py`, `m0128_near_miss_fixed_tape.py`, `m0152_roster_width_rungs.py` —
  read and **imported from**, never edited. Editing any of them would move a recorded
  `config_digest` and fail
  `test_every_recorded_configuration_still_digests_to_its_recorded_digest`.
- `engine/.research-test` — never opened. No `--store` points at it and `lab test` is never run.

**Shared mutable artifact:** `lab/lab.sqlite` + `web/data/lab.json`. Phases 1, 3, 4 and 5 all
write it; phase 2 regenerates `web/data/lab.json` alone. Every DB-writing command, `lab run`
included, is inside a lab-write-lock hold that ends with `lab stage` + commit + push (plan
invariant 7, defined in Step 1). This phase takes **two** holds: A around Step 1, B from Step 5
through Step 8.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/methods/m0156_regime_book_width.py` | create | the whole method: 5 width rungs of `M0002-REL-85` on `monthly-hold-frac-gotrade-tband` |
| `docs/lab/survivorship/mom-book-2026-10-14.csv` | create | step one's grid: 6 recorded M0002 variants × 2 stores, at the recorded basis |
| `docs/lab/survivorship/mom-width-curve-2026-10-14.csv` | create | step two's grid: 5 M0156 arms × 2 stores, at the owner's basis |
| `docs/lab/survivorship/mom-width-curve-2026-10-14.md` | create | the paired curve, the trough dates and the era table, in plain language |
| `lab/lab.sqlite` | modify | 5 dev trials, 1 method status move, 2 observations, 1 analysis/verdict |
| `web/data/lab.json` | modify | regenerated by `lab stage` |
| `docs/lab/survivorship/grid.csv` | **untouched** | D16 reads it; appending would change which promotions the gate refuses |

---

## Implementation Steps

### Step 0: fix the preconditions before anything runs

**File:** none — shell only.
**Change:** record the invariants this phase must not move, and confirm both stores are reachable.

**Code:**
```bash
cd /home/miftah/seer
git rev-parse --abbrev-ref HEAD   # expect: main

# Invariant 8: any `lab` command migrates lab.sqlite on connect, even a read.
# Hash it first so a read-only command that dirties it can be restored by path.
sha256sum lab/lab.sqlite | tee /tmp/claude-1000/-home-miftah-seer/lab-before.sha

engine/.venv/bin/python -m seer_engine lab status
# WRITE DOWN: "test-window looks used: 4". It must still read 4 at the end of this phase.

# Both stores present and correctly marked, without loading a bar:
engine/.venv/bin/python - <<'PY'
from pathlib import Path
from seer_engine import research
for d in ("engine/.research", "engine/.research-sv"):
    print(d, "purpose:", research.declared_purpose(Path(d)))
PY
# expect: engine/.research purpose: None
#         engine/.research-sv purpose: survivorship-check
```

If `lab status` dirtied the database and no trial was written, restore it by path:
`git checkout -- lab/lab.sqlite` (never `reset --hard`; the checkout is shared).

**Impact:** nothing is written. This is the before-reading of the two numbers (N, looks) that the
exit criteria compare against.

---

### Step 1: the free read — `lab survivorship M0002`

**File:** `docs/lab/survivorship/mom-book-2026-10-14.csv` (created by the command)
**Change:** re-run all six recorded `M0002` dev variants at their recorded capital
(20,000,000 IDR) and funding (none) on the dev store and then on the survivorship-check store, and
print them side by side. One `observation` is journaled per method.

**Code:**
```bash
cd /home/miftah/seer
engine/.venv/bin/python -m seer_engine -v lab survivorship M0002 \
  --csv docs/lab/survivorship/mom-book-2026-10-14.csv \
  2>&1 | tee /tmp/claude-1000/-home-miftah-seer/m0002-survivorship.log
```

Run it in the background: two full store loads of ~2.5M bar rows each, six variants per store.
Budget 30–60 minutes. `-v` prints a per-variant line as each finishes, so progress is visible.

Both stores are **never alive together** (`measure_store` frees one before loading the next), so
`seer-research-store-memory-budget`'s ~1 GB figure is the peak, not 2 GB.

**Reading the result — the part that must not be got wrong.** The report prints `max_drawdown`
for each variant on each store. For `M0002-REL-85`:

- The **delta** (check minus dev) is the finding. It is measured on one basis both sides, so it is
  internally valid and is the first survivorship signal this picking rule has ever had.
- The **level** is not the owner's bar. The recorded basis is unfunded whole-share flat-fee, and
  `MOM-FR-GT` is funded, fractional, at Gotrade's real fees. Deposits change a worst fall
  (M0007-N20-RAW falls 19.59% unfunded on dev; the same picks funded on the fixed tape,
  `M0128-RAW20`, fall 20.65%). So a check-store number above 25% here is **an alarm, not a
  breach**.

**What to say, and where.** If the check-store worst fall for `M0002-REL-85` clears 25%, that
leads everything written in this phase — the verdict's first line, the `.md`'s first line, and the
report back to the coordinator — stated as: *the roster's relative-strength book has never been
priced against the honest history, and the first look at the closest thing the lab holds to it
falls further than the owner's bar allows. The measurement that settles it is step two.* Plain
language, no ids, no digests (invariant 10).

If the gap is under +1.0 point on the fall and under 0.5 pt/yr on the return, say that too, just as
plainly: the relative-strength book may be genuinely less survivorship-sensitive than the
residual-momentum one, which would be a real and reassuring difference between the two books.
**Either answer leaves step two unchanged** — see Step 2's note on why.

**Impact:** `lab/lab.sqlite` gains one `insights` row. No trial, no moments, no funding, no status.
N stays 469 dev rows / 94 methods; looks stay 4. The command prints both before and after; copy
that line into the log.

**This step is lock-hold A, and the hold ends here.** `lab survivorship` journals an
`observation`, so it dirties `lab/lab.sqlite` for the whole 30–60 minutes it runs. Take the lab
write lock *before* the command and release it only after the pair is committed and pushed — the
hold ends at Step 1 rather than running to Step 8, so phases 3, 4 and 5 are not blocked while
Step 2's method file is written.

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

Inside that hold, after the command finishes:

```bash
cd /home/miftah/seer
git add -- docs/lab/survivorship/mom-book-2026-10-14.csv
git commit -m "lab: M0156 -- the roster's relative-strength book, read on both price histories

Report only: no trial was recorded by this measurement and the lab's test-window looks did
not move, staying at four.

<one paragraph of the finding, in plain language, leading with the owner-facing fact if this
book's worst fall on the honest history is outside his bar>

docs/lab/survivorship/grid.csv is untouched: survivorship_record.GRID_PATH points the hard
gate's D16 at that exact file, so appending would change which promotions the gate refuses as
a side effect of a research run.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

# the journaled observation, through the index (lab stage git-adds the pair)
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab stage
git commit -m "lab: M0156 -- survivorship observation for the relative-strength book

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push origin main

git diff --quiet HEAD -- lab/lab.sqlite web/data/lab.json || { echo "STILL DIRTY -- do not release"; }
flock -u 9
```

---

### Step 2: write the method file

**File:** `engine/src/seer_engine/lab/methods/m0156_regime_book_width.py` (new)
**Change:** five rungs of `M0002-REL-85`'s picking rule, nothing moved but the slot count, on the
preset M0152's curve was measured on.

**The rung set is fixed by this plan, before step one runs, and does not depend on its result.**
20, 25, 30, 35, 45. Choosing rungs after reading step one would be specification search; fixing
them here removes the question entirely. 20 is the anchor and is the realistic twin of today's
roster book. 25/30/35 span the interval where M0152 found the whole of the residual-momentum
book's protection. 45 prices the far end, where M0152 found the two histories converge. 70 is left
out to keep the run inside one session (see Handoffs).

**Preset:** `monthly-hold-frac-gotrade-tband`, imported as `MONTHLY_TBAND` from
`m0128_near_miss_fixed_tape`. Not `monthly-hold-frac-gotrade`, which is what the live `MOM-FR-GT`
roster entry trades. The reason is written into the hypothesis: the equity-basis resize band never
fires, so a non-banded tape leaves the deposits in cash and every width reading on it is
confounded (`seer-resize-band-never-fires`). `MONTHLY_HOLD_FRAC_GOTRADE_TBAND` carries no owner
input and is promotable, so `rule_owner_inputs` returns `()`.

**Digest safety:** `config_text` digests rules, allocator id and params and never the candidate id.
`M0156-N20` differs from the recorded `M0002-REL-85` (`#79`) in its rule set, so the digests differ
and `trials.UNIQUE(config_digest, window)` is not threatened. No trial anywhere carries
`allocator_id = 'M0002'` at any preset but `monthly-hold` (checked on the committed database).

**Code:**

```python
"""M0156 — The roster's OTHER book, priced the way the owner trades it, at five widths.

Source: a variation of M0152, which asked this question of the roster's residual-momentum book
and answered 35 names. This method asks it of the book M0152 explicitly could not reach.

**The hole this exists to close.** The paper roster holds two books the owner mirrors with his own
money. ``RAW-FR-GT`` is M0007-N20-RAW's picks; M0152 measured it at seven widths on both price
histories and found its twenty-name form falls 25.05% on the survivorship-check store against a
real-money bar of 25%. ``MOM-FR-GT`` is this book -- M0002-REL-85, momentum de-risked only when
its own volatility is above its own median -- and it has **no row in
docs/lab/survivorship/grid.csv, no reading on the check store in any form, and no lab trial at the
fees and share basis the owner actually pays.** It is also a twenty-name book: the exact shape that
came out worst in M0152.

**Why a new method id rather than an amendment.** ``runner.AMEND_CLOSED`` refuses an amendment on
any method that has spent its test-window look, and M0002 reads ``test-failed`` -- so the natural
host is closed by design, and correctly: design section 3 gives one look per configuration.
M0152 is amendable but is the wrong host: a different allocator, a different family, and
``store.best_dev_eligible`` returns exactly one variant per method, so an amendment would make
M0152's single promotion candidate a choice between two different picking rules. M0152's own
frozen hypothesis also says of this book, before any of its results were seen, that it is "not
fixable inside this method id". Measured cost of the new id: the lab's N moves from 94 distinct
methods to 95 under ``store.DSR_POLICY = "methods"``, applied retroactively. Accepted, and stated
here rather than discovered later.

**What the free report could and could not settle.** ``lab survivorship M0002`` re-runs the
recorded M0002 trials at their recorded basis -- whole shares, the lab's old flat 0.1% a trade,
and **unfunded**, because none of trials #75-#80 has a ``trial_funding`` row. Three independent
mismatches against M0152's curve, which is fractional, at Gotrade's measured schedule, and funded
on the owner's plan. So that report measures the *picking rule's* survivorship sensitivity and
cannot measure the owner's book. This method measures the owner's book. Its rung set was fixed in
the implementation plan before that report was run, so no result selected it.

**Nothing varies but the slot count.** ``_picks`` is M0002-REL-85's parameters with ``top`` moved
through ``dataclasses.replace`` and nothing else: the same momentum screen, the same SPY 200-day
all-cash gate, the same 63-session short volatility window against the same 378-session reference
median, the same 0.85 multiple of its own normal volatility, the same equal money per slot. A
reading at 25 names and a reading at 35 names differ in one integer.

**The preset is monthly-hold-frac-gotrade-tband, and that is deliberately NOT what the live roster
entry trades.** ``MOM-FR-GT`` runs on ``monthly-hold-frac-gotrade``, whose resize band is read
against equity and, measured 2026-10-14, never fires in a many-name book -- so the owner's monthly
deposits reach the book only through turnover and a slow book sits half in cash. Every width
reading on that tape is confounded. The banded preset is the tape that invests the deposits, is
what M0152's whole curve is measured on, and carries no owner input. The gap between this
measurement and the live entry's rule set is real, is named here, and is a roster question rather
than a lab one.

Assumptions written down before the run:

- **PROMOTION IS NOT AVAILABLE AND IS NOT SOUGHT.** This line runs through M0002, which is
  test-failed, so the hard gate refuses on kin (D9/D13) whatever these arms score. Any arm that
  reads ELIGIBLE on the dev screen is a by-product and must not be reported as a candidate.
- **Deposits soften every fall in this file alike.** These numbers line up against M0152's,
  M0139's and M0128's, which are funded identically (10,000,000 IDR opening, +5,000,000 IDR on the
  25th, 237 deposits), and against no unfunded trial anywhere -- M0002's own recorded trials
  included.
- **The check store is a cross-check, not truth.** It adds most of the members the dev store
  cannot price and not all of them, and real collapses were kept while data errors were cleaned,
  which is a judgement call. That is why the decision rule below asks for a cushion under the
  owner's bar rather than for the bar itself.
- Pure: every arm reads only bars dated <= ``data_date``; the preset is looked up by id so the
  file names the rule set exactly as the trial will record it.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0002_asymmetric_vol_regime import MOM20_TREND, REGIME, RegimeParams
from seer_engine.lab.methods.m0128_near_miss_fixed_tape import MONTHLY_TBAND
from seer_engine.sim.rules import rule_owner_inputs

ADDED = date(2026, 10, 14)

#: The rungs this method buys. Fixed in the implementation plan before `lab survivorship M0002`
#: was run, so no result selected them. 20 is the roster's own width and the realistic twin;
#: 25/30/35 span the interval where M0152 found the whole of the other book's protection; 45
#: prices the far end, where M0152 found the two histories converge.
WIDTHS: tuple[int, ...] = (20, 25, 30, 35, 45)

#: M0002-REL-85's own regime rule, verbatim -- the four positional arguments M0002's own
#: ``_v("REL-85", ...)`` passes: scale by min(1, 0.85 x its median vol / its current vol), a
#: 63-session short window against a 378-session reference median, full exposure at or below
#: normal. ``target_vol`` is unused in "relative" mode and is left at the value M0002 recorded.
#: The literals are written out rather than read off ``RegimeParams`` as class attributes:
#: ``RegimeParams`` is ``@dataclass(frozen=True, slots=True)`` and a slots dataclass exposes a
#: slot descriptor under the field name, not the default value.
REL85 = RegimeParams(MOM20_TREND, "relative", Decimal("0.12"), Decimal("0.85"))


def _picks(top: int) -> RegimeParams:
    """M0002-REL-85's params with only ``top`` moved: same screen, same gate, same regime rule."""
    return replace(REL85, inner_params=replace(MOM20_TREND, top=top))


def _v(top: int, rationale: str) -> Candidate:
    return Candidate(id=f"M0156-N{top}", family="M0156", rules=MONTHLY_TBAND, allocator=REGIME,
                     params=_picks(top), rationale=rationale, added=ADDED,
                     owner_inputs=rule_owner_inputs(MONTHLY_TBAND))


METHOD = Method(
    id="M0156",
    name="The roster's relative-strength book, priced the way the owner trades it, at five widths",
    family="stock-momentum-risk-managed",
    source_kind="variation",
    source_ref=(
        "M0152 for the question, the paired-curve method and the seven-rung curve on the roster's "
        "other book; M0002-REL-85 (trial #79) for the picking rule, which is what the paper "
        "roster entry MOM-FR-GT holds; M0128 for the banded real-fee preset; "
        "docs/lab/survivorship/roster-width-curve-2026-10-14.csv for the curve this one is read "
        "beside"
    ),
    parent_id="M0152",
    hypothesis=(
        "A measurement whose output is a number the owner will act on with real money, not a "
        "candidate. The paper roster holds two books and he mirrors both. M0152 measured the "
        "first at seven widths on both price histories and recommended thirty-five names. The "
        "second -- this one, momentum de-risked only when its own volatility is above its own "
        "median -- has never been read on the survivorship-check store, has no row in the "
        "committed survivorship grid, and has never been run at the fees or the share basis the "
        "owner pays. It is a twenty-name book, which is the width that came out worst in M0152. "
        "This method runs it at twenty, twenty-five, thirty, thirty-five and forty-five names on "
        "monthly-hold-frac-gotrade-tband, funded on the owner's plan against a SPY fed the "
        "identical deposits on the identical days, and then lab survivorship re-reads all five on "
        "the check store -- report only, no trial, no look -- so the two roster books can be read "
        "as two paired curves on one tape instead of one curve and a blank. "
        "THE TWENTY-NAME ARM IS THE DELIVERABLE AS MUCH AS THE CURVE IS. It is the first time "
        "this book has been priced at Gotrade's real fees in fractional shares on a tape that "
        "invests the deposits, and the first time it has been read against the history that keeps "
        "the companies that went bankrupt. Whatever the width answer turns out to be, the owner "
        "ends this run knowing what half his money has actually been doing. "
        "WHAT IS PREDICTED, in numbers, before any result. (1) THE DEV CURVE SAYS NOTHING, as it "
        "did for the other book. All five dev-store worst falls land inside 17% to 23% with no "
        "reliable ordering in width. The dev store misses about four in ten of the days companies "
        "sat in the index and the ones it misses are overwhelmingly the ones that failed, so "
        "behind a market gate it is structurally blind to what width protects against and can "
        "only ever show what width costs. (2) THE CHECK CURVE FALLS WITH WIDTH, and the "
        "twenty-name arm is the one at risk. Predicted check-store worst falls: 23% to 28% at "
        "twenty names, 21% to 25% at twenty-five, 20% to 24% at thirty, 19% to 23% at "
        "thirty-five, 18% to 22% at forty-five. Equivalently the gap between the two histories "
        "should start between +2 and +6 points at twenty names and close to under +1 by "
        "forty-five, on the schedule both previously measured books showed. (3) THE RETURN COST "
        "IS SMALL BELOW ABOUT THIRTY-FIVE NAMES AND REAL ABOVE IT, as it was on both previous "
        "books: within half a point a year from twenty to thirty-five, and one to three points "
        "a year by forty-five. (4) THE DECISION RULE, FIXED NOW SO THE RESULT CANNOT CHOOSE IT. "
        "The recommended width is the narrowest rung whose check-store worst fall is at or under "
        "23.0% -- the owner's 25% bar less a two-point cushion, because the check store is a "
        "cross-check and not truth and a recommendation resting on a tenth of a point of margin "
        "is not a recommendation -- provided its check-store return is within 1.0 point a year of "
        "the twenty-name arm's. If no rung satisfies both, the recommendation is the rung with "
        "the best check-store MAR and the verdict says plainly that the owner is being asked to "
        "buy safety with return. If the twenty-name arm itself clears 23.0%, the recommendation "
        "is TWENTY and the finding is that the two roster books differ -- which would be a "
        "genuine and reassuring result and must be reported as the primary one, not as an "
        "absence. (5) WHEN, NOT ONLY HOW FAR. The survivorship report gives the size of each "
        "worst fall and never its date, so 'the whole effect is one bad year' cannot be excluded "
        "from its rows alone. The month-end equity curve of every arm on both stores is available "
        "in process, so the peak month and the trough month of each worst fall will be computed "
        "and reported beside it, together with the worst fall inside each of 1998, the dot-com "
        "years, 2006, the financial crisis and 2010-2015. The prediction, carried over from the "
        "other book, is that the narrow arms trough in the spring of 2006 -- a 2% market dip that "
        "made a new high by September -- and the wide arms trough in 1998. If the dates instead "
        "cluster in the crises, that is a different mechanism from the one M0152 found and leads "
        "the verdict. (6) THE LIVE ROSTER ENTRY TRADES A DIFFERENT RULE SET from the one measured "
        "here: its resize band is read against equity and, measured on 2026-10-14, a band read "
        "that way never fires in a many-name book, so the monthly deposits reach the book only "
        "through turnover. The banded preset used here is the tape that invests them and is what "
        "the other book's whole curve was measured on. The size of that difference for THIS book "
        "is not measured by this method and the verdict must not pretend otherwise. "
        "ELIGIBILITY IS NOT THE POINT AND PROMOTION IS REFUSED. This line runs through M0002, "
        "which is test-failed, so the hard gate refuses promotion on kin whatever these arms "
        "score. Accepted before the run."
    ),
    expected_failure=(
        "THE MOST LIKELY DISAPPOINTMENT IS A FLAT CHECK CURVE. If all five check-store falls land "
        "within a point of each other and within the bar, then width buys this book nothing, the "
        "roster's second entry needs no change, and the five rungs priced one null result. That "
        "is still worth recording -- it would be the first evidence that the two roster books "
        "carry different single-name risk, and it would mean the owner can stop worrying about "
        "half of what he holds -- but it is a thinner result than the one predicted and the "
        "verdict must say so in its first paragraph rather than dress it up. "
        "Specific failures written now. (1) THE CURVE COULD RUN THE WRONG WAY. A wider book owns "
        "more of the shortlist and therefore more of the companies the dev store cannot price, so "
        "the check store could punish width rather than reward it, as it did to M0123's "
        "all-shortlist basket. A check-store fall that RISES from twenty to forty-five names "
        "would be a stronger argument for keeping twenty than any dev number and the verdict "
        "would have to carry it. (2) THE REGIME BRAKE COULD BE DOING THE WORK WIDTH WOULD "
        "OTHERWISE DO. This book already de-risks when its own volatility is high for itself, and "
        "a single holding collapsing inside a twenty-name book raises the basket's volatility. If "
        "so, the check-store falls will be flat in width AND the twenty-name arm will spend "
        "measurably more of the window below full exposure than the forty-five-name arm does. "
        "That is a mechanism, not a null, and it is the most interesting thing this method could "
        "find -- it would say the two roster books want different widths for a reason rather than "
        "by accident. (3) ONE ERA COULD BE DOING ALL THE WORK. If every arm's worst fall is dated "
        "inside one stretch and the 2009-2015 era leads are flat across width, this is a "
        "measurement of one episode dressed as a measurement of width. The trough dates are "
        "computed precisely so this cannot be glossed over; if the answer is one episode, the "
        "verdict leads with it and the recommendation is downgraded to a leaning rather than a "
        "number. (4) REPRODUCTION FIRST. lab survivorship prints a dev re-run beside the recorded "
        "trial. Any arm whose dev re-run does not land on its recorded trial has a meaningless "
        "side-by-side and must be dropped from the curve rather than quoted. (5) FEES AND FILL AT "
        "THE WIDE END. This account ramps from 10,000,000 IDR, so a forty-five-name book holds "
        "slots near 28 USD in its early years, where Gotrade's per-order floor is a large share "
        "of the order. Trade counts are quoted so the claim stays checkable. (6) THE CHECK STORE "
        "IS NOT TRUTH, and a recommendation that turns on the difference between 23% and 25% on "
        "it turns on which data errors somebody chose to clean. If the chosen rung clears 23.0% "
        "by less than half a point, the verdict must say the margin is inside the cross-check's "
        "own uncertainty and recommend the next rung out. (7) DEPOSITS SOFTEN EVERY WORST FALL "
        "HERE ALIKE and no figure may be lined up against an unfunded trial -- M0002's own "
        "recorded trials #75 to #80 included, which is the whole reason this method exists rather "
        "than a re-read of them. (8) THE RECOMMENDATION IS ABOUT WIDTH AND NOT ABOUT WHETHER TO "
        "HOLD THIS BOOK AT ALL. M0002 is test-failed and so is this line; nothing here says the "
        "picking rule works. It says only what it costs to hold it in twenty slots rather than "
        "more."
    ),
    candidates=tuple(
        _v(top, rationale)
        for top, rationale in (
            (20, "Twenty names: the roster's own width, and the first time this book has been "
                 "priced at the owner's real fees on a tape that invests his deposits"),
            (25, "Twenty-five names: the first rung past the roster, and the test of whether any "
                 "protection arrives gradually or in one step"),
            (30, "Thirty names: the rung that bought nothing on the other book, included so the "
                 "two curves can be read against each other rung for rung"),
            (35, "Thirty-five names: the width the other roster book was recommended at, asked of "
                 "this one"),
            (45, "Forty-five names: prices the far end, where the two price histories converged "
                 "on both books measured so far"),
        )
    ),
    seen_keys=(
        "concept:regime-vol-book-name-count",
        "concept:roster-relative-strength-book-width-on-the-check-store",
    ),
)
```

**Impact:** a new, unrun method file. Nothing recorded moves. Both `seen_keys` were checked against
`ideas_seen` on the committed database and are free.

---

### Step 3: prove the file before committing it

**File:** none — shell only.
**Change:** the pre-registration commit is irreversible in substance (the hypothesis is frozen by
it), so the file is proved first.

**Code:**
```bash
cd /home/miftah/seer

engine/.venv/bin/ruff check engine

# The method discovers, its candidates build, and the five configurations are distinct:
engine/.venv/bin/python - <<'PY'
from seer_engine.lab.method import config_digest, discover
m, path = discover()["M0156"]
cands = m.all_candidates()
print("file:", path)
print("name:", m.name)
for c in cands:
    print(f"  {c.id:12s} top={c.params.inner_params.top:3d} rules={c.rules.id} "
          f"owner_inputs={c.owner_inputs} digest={config_digest(c)[:12]}")
assert len({config_digest(c) for c in cands}) == len(cands), "duplicate configuration"
assert all(c.rules.id == "monthly-hold-frac-gotrade-tband" for c in cands)
assert all(c.rules.fractional and c.rules.cost_model == "gotrade" for c in cands)
print("lookback:", m.candidates[0].allocator.lookback(m.candidates[0].params), "bars")

# The N20 arm must be M0002-REL-85's params EXACTLY -- only the rule set differs:
from seer_engine.lab.methods.m0002_asymmetric_vol_regime import METHOD as M0002
rel85 = next(c for c in M0002.all_candidates() if c.id == "M0002-REL-85")
n20 = next(c for c in cands if c.id == "M0156-N20")
assert n20.params == rel85.params, (n20.params, rel85.params)
assert n20.allocator is rel85.allocator
print("N20 params match M0002-REL-85 exactly; only the rule set differs")
PY

# No recorded trial already holds any of these digests (UNIQUE(config_digest, window)):
engine/.venv/bin/python - <<'PY'
import sqlite3
from seer_engine.lab import store
from seer_engine.lab.method import config_digest, discover
conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
have = {r[0] for r in conn.execute("SELECT config_digest FROM trials")}
m, _ = discover()["M0156"]
clash = [c.id for c in m.all_candidates() if config_digest(c) in have]
print("clashes:", clash or "none")
assert not clash
PY

# The real-cost rule, as `runner.preflight` will apply it:
engine/.venv/bin/python - <<'PY'
from seer_engine.lab.method import discover
from seer_engine.lab.real_costs import real_cost_problem
print("real_cost_problem:", real_cost_problem(discover()["M0156"][0]) or "none")
PY

# Nothing recorded drifted (this is the test that catches an accidental edit to an imported
# params dataclass or to m0002's file):
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
engine/.venv/bin/pytest engine/tests -k "digest or method or lab_method or prereg" -q
```

Expected: ruff clean; five distinct digests; `lookback` 379 bars (`max(FACTOR.lookback,
m + 1)`), comfortably under the 473-bar smoke-fixture cap
(`seer-lab-method-lookback-capped-by-smoke-fixture`); `real_cost_problem: none`; no clashes;
the digest-stability tests green.

**Impact:** none written. If any assertion fires, fix the file and repeat — **do not commit a file
that has not passed this step**, because the commit is the pre-registration and a corrected
hypothesis after a failed run is not a pre-registration.

---

### Step 4: pre-register — commit and push the method file, alone

**File:** `engine/src/seer_engine/lab/methods/m0156_regime_book_width.py`
**Change:** the commit IS the pre-registration (plan invariant 3). `runner.preflight` refuses an
uncommitted or dirty file through `registry_problem`.

**Code:**
```bash
cd /home/miftah/seer
git add engine/src/seer_engine/lab/methods/m0156_regime_book_width.py
git commit -m "lab: M0156 pre-registered -- the roster's other book, priced the way the owner trades it, at five widths

The paper roster holds two books and the owner mirrors both with his own money. M0152
measured the first at seven widths on both price histories and recommended thirty-five
names. The second has never been read on the survivorship-check store, has no row in the
committed survivorship grid, and has never been run at the fees or the share basis the
owner pays -- its recorded trials are unfunded, in whole shares, at the lab's old flat
cost. It is a twenty-name book, which is the width that came out worst in M0152.

Five rungs -- 20, 25, 30, 35, 45 -- of M0002-REL-85's picking rule with nothing moved but
the slot count, on monthly-hold-frac-gotrade-tband, funded on the owner's plan. The rung
set was fixed in the implementation plan before the free survivorship report was run, so
no result selected it. The twenty-name arm is the deliverable as much as the curve is: it
is the first honest price of what half the owner's money has been doing.

A new id rather than an amendment: runner.AMEND_CLOSED refuses an amendment on a
test-failed method, and M0002 is test-failed; M0152 is amendable but is a different
allocator and a different family, and store.best_dev_eligible returns one variant per
method, so an amendment would make M0152's single promotion candidate a choice between two
picking rules. Measured cost: the lab's N moves from 94 distinct methods to 95.

Promotion is refused on kin through M0002 and is not sought. No test-window look is spent.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push origin main
```

**No backticks anywhere inside that `-m` string** — command substitution has eaten commit text in
this repo before (invariant 11).

If the push is rejected because another phase pushed first: **do not `git pull --rebase`**. This
commit touches no `lab/` file, so a mixed `git reset` to the pushed head plus `git merge --ff-only`
is unnecessary here — simply `git fetch origin && git rebase origin/main` is safe for a commit that
contains only a new file under `lab/methods/`. The replay hazard
(`seer-rebase-replays-stale-lab-sqlite`) applies to commits that carry `lab/lab.sqlite`, which this
one does not. **Step 6's commit does, and there the rule binds.**

**Impact:** the method file is on `origin/main`. `lab run M0156` will now accept it.

---

### Step 5: run it, then read it on both stores

**File:** `docs/lab/survivorship/mom-width-curve-2026-10-14.csv` (created by the second command)
**Change:** five dev trials recorded under `M0156`, then re-read on the check store as a report.

**Code:**
```bash
cd /home/miftah/seer

# TAKE THE LAB WRITE LOCK HERE -- this opens lock-hold B, which runs from `lab run M0156`
# through Step 8's push. `lab run` leaves the shared lab/lab.sqlite dirty for its whole
# duration, so it is inside the hold and the four lab phases' runs queue rather than overlap.
# Full protocol and preconditions: Step 1, and the plan index's invariant 7.
exec 9>/home/miftah/seer/.git/seer-lab.lock
flock -w 21600 9 || { echo "lab lock still held after 6h -- find out who has it; do NOT force"; exit 1; }
echo "phase-1 pid $$ $(date -Is)" >&9
git fetch origin && git merge --ff-only origin/main
git diff --quiet HEAD -- lab/lab.sqlite web/data/lab.json || { echo "pair dirty, nobody held the lock -- STOP"; exit 1; }

engine/.venv/bin/python -m seer_engine -v lab run M0156 \
  2>&1 | tee /tmp/claude-1000/-home-miftah-seer/m0156-run.log

engine/.venv/bin/python -m seer_engine lab show M0156
```

Expected: five trial rows, each with a `trial_funding` row reading `+5,000,000 IDR on the 25th of
each month` / `deposits_n 237` / `deposits_usd 148087.9806`, and a `trial_provenance` row reading
`initial_idr 10000000`. Those three numbers are what make this curve comparable to M0152's,
M0139's and M0128's — **check them before going further**; if they differ, the comparison in the
`.md` is void and the verdict says so instead of quoting a joint table.

```bash
engine/.venv/bin/python - <<'PY'
import sqlite3
from seer_engine.lab import store
conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
for r in conn.execute("""
  SELECT t.n, t.candidate_id, t.max_drawdown, t.mar, t.trades, t.eligible,
         p.initial_idr, f.deposits_n, f.deposits_usd, f.mwr, f.spy_tr_mwr
  FROM trials t
  LEFT JOIN trial_provenance p ON p.trial_n = t.n
  LEFT JOIN trial_funding f ON f.trial_n = t.n
  WHERE t.method_id = 'M0156' ORDER BY t.n"""):
    print(dict(r))
PY
```

Then the paired read. **This is a report: no trial, no look.**

```bash
engine/.venv/bin/python -m seer_engine -v lab survivorship M0156 \
  --csv docs/lab/survivorship/mom-width-curve-2026-10-14.csv \
  2>&1 | tee /tmp/claude-1000/-home-miftah-seer/m0156-survivorship.log
```

Budget 40–90 minutes: two full store loads, five arms per store. Run it in the background and
watch the `-v` per-variant lines.

Confirm from the command's own tail line that `test-window looks used: 4 before, 4 after`.

**If the run lands after midnight local time, rename both CSVs and the `.md` to the date the run
completed** and use that date everywhere. A dated file whose date is not its date is worse than no
date.

**Impact:** `lab/lab.sqlite` gains five trials with their moments, funding and provenance, one
`method_folds` row, one method status move (`idea -> registered -> dev-eligible|rejected`) and one
`observation`. The lab's dev trial count goes 469 -> 474 and its distinct-method count 94 -> 95.
Test-window looks stay 4.

---

### Step 6: the columns the survivorship report does not carry — when, and in which era

**File:** `/tmp/claude-1000/-home-miftah-seer/scratchpad/m0156_when.py` (scratch, not committed)
**Change:** `lab survivorship` prints the size of each worst fall and never its date. M0152's
published curve carries both because they were computed in process from `Side.curve` and
`Side.deposits`. This script does the same for M0156.

**Code:**
```python
"""M0156's paired curve with the two columns the survivorship report does not carry.

`Side` holds the month-end equity curve and the deposits that were paid into it, so the
de-funded worst fall, the months it ran between, and the worst fall inside any stretch can all be
recomputed here. Nothing is written to the lab: this opens the database read-only through the same
`plan_methods` path the command uses, loads each store once, and prints a table.

The era bounds below are THIS SCRIPT'S definition. They are chosen to match the stretches named in
docs/lab/survivorship/roster-width-curve-2026-10-14.md but were not recovered from the code that
produced that file, so a cross-file era comparison is approximate to about a month. Everything
compared WITHIN this file uses one definition and is exact.
"""

from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

from seer_engine.backtest.regime import defunded
from seer_engine.lab import hardgate, store
from seer_engine.lab import survivorship_check as svc

ERAS: tuple[tuple[str, date, date], ...] = (
    ("1998", date(1998, 1, 1), date(1998, 12, 31)),
    ("2000-02", date(2000, 1, 1), date(2002, 12, 31)),
    ("2006", date(2006, 1, 1), date(2006, 12, 31)),
    ("2008-09", date(2008, 1, 1), date(2009, 12, 31)),
    ("2010-15", date(2010, 1, 1), date(2015, 10, 16)),
)


def worst_fall(curve: list[tuple[date, float]]) -> tuple[float, date | None, date | None]:
    """Largest peak-to-trough fall of an ALREADY de-funded curve, with its two months."""
    peak = None
    peak_at: date | None = None
    worst, p_at, t_at = 0.0, None, None
    for when, value in curve:
        if peak is None or value > peak:
            peak, peak_at = value, when
        if peak and peak > 0.0:
            fall = 1.0 - value / peak
            if fall > worst:
                worst, p_at, t_at = fall, peak_at, when
    return worst, p_at, t_at


def main(method_id: str, out: Path) -> int:
    conn = store.connect_readonly(store.DB_PATH)
    plans = svc.plan_methods(conn, [method_id])
    geo = hardgate.geometry(conn)
    dev_dir, sv_dir = svc.research.STORE_DIR, svc.research.SV_STORE_DIR
    svc.check_stores(Path(dev_dir), Path(sv_dir))
    runs = {
        "dev": svc.measure_store(conn, plans, Path(dev_dir), survivorship=False, bench=geo.bench),
        "check": svc.measure_store(conn, plans, Path(sv_dir), survivorship=True, bench=geo.bench),
    }
    header = [
        "names", "candidate_id", "store", "max_drawdown_daily", "max_drawdown_monthend",
        "mdd_peak_month", "mdd_trough_month", "funded_yearly", "spy_yearly", "mar_funded",
        "era_2009_2015_edge", "trades", *(f"era_{name.replace('-', '_')}" for name, _, _ in ERAS),
    ]
    rows: list[list[object]] = [header]
    for plan in plans:
        for v in plan.variants:
            names = v.candidate.params.inner_params.top
            for label, run in runs.items():
                side = run.sides[(plan.method.id, v.candidate.id)]
                clean = defunded(list(side.curve), side.deposits)
                whole, p_at, t_at = worst_fall(clean)
                mar = None if not whole else (side.yearly or 0.0) / whole
                era_cols = [
                    round(worst_fall([(d, x) for d, x in clean if lo <= d <= hi])[0], 6)
                    for _, lo, hi in ERAS
                ]
                rows.append([
                    names, side.candidate_id, label,
                    round(side.max_drawdown, 6) if side.max_drawdown is not None else "",
                    round(whole, 6),
                    p_at.isoformat()[:7] if p_at else "",
                    t_at.isoformat()[:7] if t_at else "",
                    round(side.yearly, 7) if side.yearly is not None else "",
                    round(side.spy_yearly, 7) if side.spy_yearly is not None else "",
                    round(mar, 4) if mar is not None else "",
                    round(side.era_edge, 6) if side.era_edge is not None else "",
                    side.trades, *era_cols,
                ])
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    for row in rows:
        print(", ".join(str(x) for x in row))
    print(f"\nwritten to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], Path(sys.argv[2])))
```

```bash
cd /home/miftah/seer
engine/.venv/bin/python /tmp/claude-1000/-home-miftah-seer/scratchpad/m0156_when.py \
  M0156 docs/lab/survivorship/mom-width-curve-2026-10-14.csv
```

Note this **overwrites** the CSV `lab survivorship --csv` wrote in Step 5 with the richer grid, in
the same column shape as `roster-width-curve-2026-10-14.csv` so the two files read side by side.
Keep the survivorship command's own grid as `mom-width-curve-raw-2026-10-14.csv` if both are
wanted; the `.md` must say which columns came from where.

This script opens both stores a second time. If the session is short on time, skip it and record
in the verdict that the trough dates were not computed — a missing column is honest, a guessed one
is not.

**Impact:** nothing written to `lab/lab.sqlite`. `connect_readonly` never migrates.

---

### Step 7: write the curve in plain language, and the verdict

**File:** `docs/lab/survivorship/mom-width-curve-2026-10-14.md` (new);
`/tmp/claude-1000/-home-miftah-seer/scratchpad/m0156-verdict.md` (scratch, fed to `lab note`)

**Change:** two pieces of prose. The `.md` is the dated record beside M0152's, in the same shape.
The verdict goes into the lab database and onto seertrade.site/sera, so it carries **no ids, no
digests and no code** (invariant 10).

**The `.md` must contain, in this order:**

1. A first line saying this is report-only: no trial was recorded by the survivorship
   measurements, the lab's test-window looks did not move.
2. **If step one or step two put this book's check-store fall outside the owner's 25% bar, that
   sentence is the first thing after it,** stated as a live fact about half of what the owner holds
   with his own money.
3. Why this file is separate from `grid.csv` — `survivorship_record.GRID_PATH` points hard-gate
   D16 at that exact file, so appending would change which promotions the gate refuses as a side
   effect of a research run. Same reason M0152's file is separate; this is upholding a 2026-10-14
   decision, not re-opening it.
4. The paired curve: names, dev fall, check fall, gap, dev %/yr, check %/yr, dev MAR, check MAR,
   trades.
5. The "when" table: peak month, trough month, and the worst fall inside each era — with the
   note that the era bounds are this file's own definition and a cross-file comparison to
   `roster-width-curve-2026-10-14.csv` is approximate to about a month.
6. The two roster books beside each other at the rungs they share (20, 25, 30, 35, 45), with the
   caveat stated once: both are funded identically and both are on the banded preset, so the
   comparison is sound; neither is on the rule set the live roster entries actually trade.
7. The recommendation, and whether it follows the pre-registered decision rule or departs from it.
   **If it departs, say so and say why**, as M0152 did.
8. Limits: the check store is a cross-check and not truth; month-end granularity makes each era
   figure a floor on the daily one; this is a width finding and not a verdict on the picking rule;
   and the live `MOM-FR-GT` entry trades the un-banded preset, whose effect on this book is not
   measured here.

**The verdict, via `lab note`:**

```bash
cd /home/miftah/seer
engine/.venv/bin/python -m seer_engine lab note M0156 \
  --file /tmp/claude-1000/-home-miftah-seer/scratchpad/m0156-verdict.md \
  --verdict "<one plain sentence: the width this book should be held at, or that it is safe where it is>"
```

`lab note` appends a dated section and never rewrites what is there; write the file with its own
`### 2026-10-14` opening line only if a duplicate heading is acceptable — `store.append_analysis`
treats an author's own `### <today>` line as the section head, so one is correct and two is not.

**Impact:** `lab/lab.sqlite` gains an analysis section and a verdict string; the new `.md` and CSVs
are untracked until Step 8.

---

### Step 8: stage, commit and push — serialised against the other lab phases

**File:** `lab/lab.sqlite`, `web/data/lab.json`, and the three `docs/lab/survivorship/` files.
**Change:** the only step that contends with Phases 3, 4 and 5.

**This step closes lock-hold B** — the hold taken at Step 5, before `lab run M0156`, and carried
through the whole measurement. The lock, its preconditions and its release are defined once below
and are identical in every phase of this set.

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

Step 1's CSV and its journaled observation were already committed inside lock-hold A, so this
commit carries only step two's artifacts.

**Code:**
```bash
cd /home/miftah/seer

# 1. The documents go first, by explicit pathspec, in their own commit. They do not touch the
#    lab pair, so this commit is safe to rebase if the push races.
git add docs/lab/survivorship/mom-book-2026-10-14.csv \
        docs/lab/survivorship/mom-width-curve-2026-10-14.csv \
        docs/lab/survivorship/mom-width-curve-2026-10-14.md
git commit -m "lab: M0156 -- the roster's relative-strength book, read on both price histories

Report only: no trial was recorded by these measurements and the lab's test-window looks
did not move, staying at four.

<one paragraph of the finding, in plain language, leading with the owner-facing fact if
this book's worst fall on the honest history is outside his bar>

docs/lab/survivorship/grid.csv is untouched: survivorship_record.GRID_PATH points the hard
gate's D16 at that exact file, so appending would change which promotions the gate refuses
as a side effect of a research run. These are their own dated files, as M0152's are.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

# 2. The lab pair, THROUGH THE INDEX. `lab stage` writes web/data/lab.json and git-adds it
#    with lab/lab.sqlite. A pathspec commit re-reads the working tree and defeats that
#    (seer-lab-stage-commit-needs-the-index), so the commit below takes NO paths.
engine/.venv/bin/python -m seer_engine lab stage
git commit -m "lab: M0156 -- <one plain sentence verdict>

Five widths of the roster's relative-strength book -- 20, 25, 30, 35, 45 names -- at
Gotrade's real fees in fractional shares on the tape that invests the owner's deposits,
funded on his plan, then re-read on the history that keeps the companies that went
bankrupt. The first time this book has been priced either way.

<the number, and the recommendation, in plain language>

Promotion was refused on kin and was never sought. The lab's test-window looks are
unchanged at four.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

git push origin main
```

**If that push is rejected:** another lab phase pushed while this one held the lock, which means
the lock was not held. **Do not `git pull --rebase`** — it replays this session's `lab.sqlite` over
whatever the other phase wrote (`seer-rebase-replays-stale-lab-sqlite`). Instead:

```bash
git fetch origin
git log --oneline --name-only HEAD..origin/main | grep -E '^lab/|^web/data/lab\.json' || echo "no lab files upstream"
```

- If the upstream commits touch **no** `lab/` file and not `web/data/lab.json`: a mixed
  `git reset` to `HEAD~2`, then `git merge --ff-only origin/main`, then redo the two commits above
  — `lab stage` again before the second one. No stash, no replay.
- If they **do** touch the lab pair: the live `lab/lab.sqlite` in the working tree already contains
  both sessions' writes (one file, one checkout). Reset mixed to `origin/main` after fetching, run
  `lab stage` once, and commit the pair as a single commit whose message names both methods. Then
  verify trial `n` is contiguous and that the other phase's trials survived:
  ```bash
  engine/.venv/bin/python -m seer_engine lab status
  ```

**Impact:** everything this phase produced is on `origin/main`. `lab stage` also regenerates
`web/data/lab.json`, and CI checks it agrees with `lab.sqlite` row for row.

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

**Build:** `engine/.venv/bin/ruff check engine` — CI lint is bugs only (E9 and F, minus F401).

**Tests:**
```bash
cd /home/miftah/seer
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
engine/.venv/bin/pytest engine/tests
```
DB tests need Postgres and **CI fails if they skip** (plan invariant 1):
`docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16`

The two tests that matter most to this phase, and why:
- `test_every_recorded_configuration_still_digests_to_its_recorded_digest` — proves that importing
  `MOM20_TREND`, `REGIME` and `RegimeParams` from `m0002_asymmetric_vol_regime` did not move any
  recorded digest. If this goes red, the new method file edited something it only meant to read.
- the `lab.json` / `lab.sqlite` agreement test — proves `lab stage` ran and both halves were
  committed.

**No web change:** this phase touches nothing under `web/` but `web/data/lab.json`, which
`lab stage` generates. `cd web && npx tsc --noEmit && npm test` is not required, but is cheap and
is the thing that catches a malformed snapshot.

**Manual check:**
```bash
engine/.venv/bin/python -m seer_engine lab status   # test-window looks used: 4
engine/.venv/bin/python -m seer_engine lab show M0156
git status --short                                  # clean; nothing of another phase's staged
```

**Exit criteria:**

1. `lab survivorship M0002` has run, its grid is committed as a dated file, and the paired
   dev/check numbers for all six recorded `M0002` variants are reported.
2. If either step put this book's check-store worst fall outside the owner's 25% bar, that is the
   **first** statement in the verdict, in the `.md`, and in the report back to the coordinator —
   stated as a live fact about half of what the owner holds with his own money, with its basis
   named (step one's figure is unfunded whole-share flat-fee; step two's is the owner's own basis).
3. `M0156` is pre-registered by its own commit, run, and carries a written verdict; its five arms
   are recorded with funding and provenance matching M0152's (10,000,000 IDR opening, 237 deposits,
   148087.9806 USD).
4. The paired dev/check width curve for `M0002-REL-85`'s picking rule exists as a dated CSV and a
   plain-language `.md` under `docs/lab/survivorship/`.
5. `docs/lab/survivorship/grid.csv` is byte-identical to its state at `661870d`:
   `git diff --stat 661870d -- docs/lab/survivorship/grid.csv` prints nothing.
6. `lab status` reads **4** test-window looks, before and after.
7. `ruff` clean, `pytest engine/tests` green with `PG_TEST_URL` exported.
8. `lab/lab.sqlite` and `web/data/lab.json` are committed together, through the index, and agree.

---

## Handoffs

- **The roster change for `MOM-FR-GT` is not made here, and is not Phase 2's either.** Phase 2 owns
  `RAW-FR-GT` only and its scope explicitly excludes `MOM-FR-GT`. This phase produces the number;
  acting on it is a second, separately argued roster commit with its own migration, after the owner
  has seen the finding. Serves R1, which is not in this phase's `satisfies`.
- **`MOM-FR-GT` trades `monthly-hold-frac-gotrade`, not the banded preset this curve is measured
  on.** The equity-basis resize band never fires in a many-name book, so the live entry's deposits
  reach it only through turnover. Moving the live entry to the banded rule set would move its spec
  digest and fail the next paper night with `SpecMismatch` (plan invariant 4), so it is a new
  roster entry with a fresh paper clock, not an edit. Its own change, its own plan.
- **`M0128` is absent from `grid.csv`, so hard-gate D16 cannot see that the roster's residual-
  momentum book breaches the bar.** Named in the 2026-10-14 handover as a real hole, deliberately
  not urgent (M0128 is already blocked on folds and on kin). `M0156`'s arms will be absent for the
  same reason. Closing the hole deserves its own argued commit with the gate's tests run.
- **The 70-name rung is not bought.** M0152's curve shows both previously measured books converge
  by 45–50 names, so 70 would price the flat part. If the check curve for this book is still
  falling at 45, that is new information and a 70-name rung becomes worth an amendment on `M0156`
  — which is free, because `M0156` will read `dev-eligible` or `rejected`, both of which are
  outside `runner.AMEND_CLOSED`.
- **The era bounds in Step 6's script are this plan's own definition** and were not recovered from
  whatever produced `roster-width-curve-2026-10-14.csv`. Re-running both methods' arms through one
  script would make the two files exactly comparable at the cost of two more full store loads.
  Worth doing only if a cross-book era claim becomes load-bearing.
- **The regime brake may be substituting for width** (expected-failure 2). If the check curve comes
  out flat, measuring how much of the window each arm spends below full exposure would say whether
  that is why. `lab exposure M0156` reads most of it for free — no trial, no look, no method id —
  and is a follow-up, not part of this phase.

---

## Rollback

**The lab half cannot be rolled back, and that is the point.** `trials`, `trial_moments`,
`trial_funding`, `trial_provenance`, `insights` and `ideas_seen` all carry `BEFORE DELETE` and
`BEFORE UPDATE` triggers that raise. `M0156`'s five dev trials and the two observations are
permanent, and the lab's N stays at 95 distinct methods. Undoing a lab phase means **writing a
further note**, never editing a row:

```bash
engine/.venv/bin/python -m seer_engine lab note M0156 \
  --file <a dated section saying what was wrong and why the earlier reading should not be used>
engine/.venv/bin/python -m seer_engine lab stage && git commit -m "lab: M0156 -- correction"
```

**The file half reverts cleanly.** `git revert` the pre-registration commit removes
`m0156_regime_book_width.py`; `git revert` the documents commit removes the three
`docs/lab/survivorship/` files. Neither revert touches `lab.sqlite`, so the recorded trials remain
and `plan_method` would then refuse a re-read with *"none of its recorded variants is in its method
file any more"* — which is the correct refusal and is why the file should be restored rather than
left reverted if the trials are to stay readable.

**Nothing outside the lab is touched**, so there is no migration to undo, no roster clock to
restart, no spec digest to put back, and no paper night at risk.
