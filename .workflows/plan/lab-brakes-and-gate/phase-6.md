# Phase 6: The owner's two decisions: §5.1's N strings, and the amendment rule

**Plan set:** `LAB_BRAKES_AND_GATE_PLAN.md`
**Analysis:** `docs/analyzer/20261012-124247-B4K9_code_analyzer.md`
**Satisfies:** R5 — surface §5.1 (the ten `Lab N (dev trials)` strings) to the owner as a decision, and do not fix it
**Depends on:** Phase 1
**Difficulty:** NORMAL
**Package:** `docs/plans`

---

## Goal

After this phase the owner has two written decisions in front of him and neither has been made
for him. The first is that every lab command prints a luck hurdle of 354 when the gate it
actually applies is 74, with the three options the previous session named and no recommendation
attached. The second is that this plan set, on his instruction, let a method that has already run
accept new pre-registered variants — and that the policy which is supposed to charge for extra
looks does not charge for them, a gap stated plainly with the question put to him rather than
answered.

**No source file changes.** This phase writes two markdown documents and nothing else. In
particular the ten printed strings this memo is *about* are not touched.

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates:** `docs/plans/2026-10-12-lab-n-and-amendments-owner-decision.md` (new file);
section `## 9. Revision 2026-10-12 …` appended to `docs/plans/2026-10-04-method-lab-design.md`
**Signature changes:** none

**Requires (from earlier phases):**
- Phase 1 has built the amendment mechanism — a method that has already run can be given an
  additional, separately dated and separately pre-registered block of candidates, recorded under
  its own `method_id`, reached through `lab run --amend MNNNN`; `methods.source_sha` is never
  rewritten and the trigger `methods_source_sha_once` stays in place; each amendment appends a
  row to a new append-only `method_amendments` table carrying its own source hash, date and git
  sha. These are the index's Decisions D2 and D3 and the index's Phase 1 **Owns** line, which is
  binding on Phase 1.
- Phase 1 has **not** changed `npolicy.py`, `store.gate` or `store.pending_gate` (index Phase 1
  **Does not touch**), so the memo's measured N figures still describe the shipped gate.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/commands/lab.py` — **not one of the ten `Lab N (dev trials)` strings**
  at lines 1399, 1684, 1718, 1739, 1785, 1817, 1870, 1923, 2238, 2287 (numbered at base commit
  `d3c1ec4`; phases 1 and 2 shift them, and neither edits one). Index invariant 9.
- all of `engine/`, `lab/`, `web/`, `db/` (Phases 1–5)
- `engine/src/seer_engine/lab/methods/m0030_*.py` (Phase 3), `m0053_*.py` (Phase 4)
- `docs/backtests/2026-10-12-brakes-and-gate.md` (Phase 5) — this phase's memo is a **policy**
  document and must not restate or depend on that write-up's results
- `docs/plans/LAB_BRAKES_AND_GATE_PLAN.md` — the index; the reconciler owns it
- `docs/plans/HANDOVER_20261012-the-hurdle-counts-methods.md` — a closed record, quoted not edited

## Files

| File | Action | What changes |
|---|---|---|
| `docs/plans/2026-10-12-lab-n-and-amendments-owner-decision.md` | create | the whole file: Decision A (§5.1's N strings) and Decision B (the amendment trade-off) |
| `docs/plans/2026-10-04-method-lab-design.md` | modify (append at EOF, after line 512) | a new `## 9.` dated revision recording the amendment rule beside the 2026-10-04 decision it qualifies |

Nothing else. `git diff --stat` must show exactly these two paths.

## Facts this phase asserts, and where each was measured

Index invariant 10: every figure carries its date and what it was measured on. All of the
following were **re-verified in this session, 2026-10-12**, on a byte-identical copy of the
committed `lab/lab.sqlite` (md5 `4a34ddb823ec88a5e86afeb5d7e1b7c9`; the original was not opened,
because a lab command migrates the file on connect), using the worktree's source on
`PYTHONPATH` and the main checkout's venv:

```
store.gate(conn)                       -> Gate(n=74, policy='methods')
store.dev_trial_count(conn)            -> 354          (dev trial ROWS)
npolicy.dev_method_count(conn)         -> 74           (distinct methods with a dev trial)
participation ratio                    -> 2.1946       -> ceil = 3, floor does NOT bind
mean pairwise correlation              -> 0.648  over 354 curves on 102 common month-ends
store.pending_gate(conn,'M0030',3)     -> Gate(n=74)   (free)
store.pending_gate(conn,'M0053',3)     -> Gate(n=74)   (free)
store.pending_gate(conn,'M9999',1)     -> Gate(n=75)   (+1, retroactive for all 130 method rows)
SELECT count(*) FROM methods           -> 130
```

Also verified in this session:
- `grep -n 'Lab N (dev trials)' engine/src/seer_engine/commands/lab.py` returns exactly ten hits,
  at **1399, 1684, 1718, 1739, 1785, 1817, 1870, 1923, 2238, 2287** — the handover's line numbers
  are still correct on this worktree's base, `d3c1ec4`.

  **The count stays ten after this plan set; the line numbers do not** (reconciler, C8). Phase 1
  adds `--amend` to the `run` subparser near `:195` and extends `_run`'s tail, so every one of the
  ten shifts down by a dozen or so lines, and phase 2 inserts a whole subcommand above most of
  them. Quote the numbers **at `d3c1ec4`**, as the handover does and as the memo below does, and
  say so where they appear. Phase 2's new `lab gate` command deliberately adds **no eleventh
  instance** — it prints the hurdle and the row count under separate labels — so the *count* is
  stable even though the positions are not. Re-run the `grep -c` on the branch before committing
  this phase: it must still print 10.
- The string `Lab N (dev trials)` appears in **23** markdown files in the repo, **0** of them
  under `docs/runbooks/`, 3 under `docs/`, and twice in `engine/package_readme.md`. The handover
  wrote "a command surface that several runbooks quote"; the memo below restates that as the
  previous session's stated reason and records what a grep on 2026-10-12 actually found, rather
  than repeating an unverified claim. That is the §7 pattern.
- `runner.preflight` (`engine/src/seer_engine/lab/runner.py:174-178`) is the freeze being
  qualified: `"{method.id} is already {status}: a method runs once. A change is a new variation
  method (source_kind='variation', parent_id=...)"`.
- `lab/method.py:30` `MAX_VARIANTS = 6`; `lab/method.py:77-78` enforces `1 <= len(candidates) <= 6`.
- `docs/plans/2026-10-04-method-lab-design.md` is **512 lines**, ends with `…cannot manufacture.\n`,
  and its last section is `### 8.6 The rule, in short`. The next free top-level number is **9**.

---

## Implementation Steps

### Step 1: Write the owner decision memo

**File:** `docs/plans/2026-10-12-lab-n-and-amendments-owner-decision.md` (new file, does not exist)
**Change:** create the file with exactly the text below.

Register note for the implementer: the prose is plain on purpose — `CLAUDE.md` says text the
owner reads carries no ids, digests or code. Line numbers, symbol names and counts live only
inside the blocks marked **For the implementer**. Do not promote them into the prose, and do not
add a recommendation to Decision A: the user's instruction was "Surface it, do not fix it."

**Code:**

````markdown
# Two decisions for the owner — 2026-10-12

**Status:** open. Nothing in this document has been decided, and nothing in the code has been
changed because of it.
**Written by:** the brakes-and-gate plan set, as its last phase.
**Asks for:** two answers. They are independent — either can be answered without the other.

This memo carries the two things that work could not settle for itself.

The first is a number the lab has been printing to you incorrectly since 8 October. It is the
single number you use to judge whether a new idea is worth trying, and it is wrong by a factor
of about five.

The second is a rule the lab lived by until today and does not any more. It was changed on your
own instruction, and the change bought something real. It also gave something up, quietly, and
you have not yet been asked whether that is a trade you want.

Neither has been acted on beyond writing it down. The first is laid out with its options and no
recommendation. The second is laid out with its gap and a question.

---

## Decision A — the hurdle the lab prints is not the hurdle it applies

### What you see

Every lab command signs off with a line telling you how big the luck hurdle is. Today it says
**354**.

### What the lab actually does

It uses **74**.

The two numbers answer different questions. 354 is how many backtests the lab has ever run on
the development window. 74 is how many separate *ideas* those backtests came from. On 8 October
the hurdle was changed to count ideas instead of backtests — that was the right change and it is
in force. The printed line was not changed with it. It has been reporting the old number for
four days.

### Why it matters

The hurdle is the price of looking. Every new thing you try makes it harder for everything else
to clear the bar, and the size of that penalty is the whole reason the lab counts.

- A **brand-new idea** looks, from the printed line, like it adds roughly one part in three
  hundred and fifty. It actually adds one part in seventy-four. It is about five times more
  expensive than the screen says.
- A **new version of an idea the lab already holds** looks, from the printed line, like it costs
  exactly the same as a new idea. It costs **nothing at all**. The hurdle does not move.

So the screen has been telling you that exploring broadly is cheap and that refining what you
have is expensive, when the truth is the reverse. That is backwards in the exact direction that
costs the most: it encourages the one activity the lab's own evidence says is least likely to
find anything new.

### The three options

These are the three the previous session named. They are reproduced as it stated them, and this
document deliberately does not choose between them.

1. **Print both numbers.** The hurdle and the backtest count, side by side, labelled so the
   difference is visible. Nothing is hidden; the line gets longer and you read two numbers where
   you used to read one.
2. **Print the hurdle, and label the backtest count separately.** The prominent number becomes
   the one that is actually applied; the row count keeps a place but stops being called the
   hurdle.
3. **Leave the screen alone and fix only the wording in the documents.** The printed number keeps
   meaning what it has always meant, and the papers around it stop calling it the hurdle. This has
   already been done to the documents (see below); choosing this option means stopping there.

### Why nothing was changed

The previous session's stated reason, kept as written: altering what you read is a decision about
your own mental model, not a wording fix, and it touches a command surface that several runbooks
quote.

A check on 2026-10-12 found that the exact printed phrase appears in twenty-three documents in
this repository — none of them in the runbooks folder, three elsewhere in the documents folder,
and twice in the engine's own package notes. So the "several runbooks" part is not quite right;
the blast radius is smaller than it was described as being. It is still more than one place, and
it is still your call, which is why this memo exists rather than a patch.

This plan set's own reason for not touching it is simpler: you said so. The instruction that
opened this work was "do not act on it — that is the owner's decision, not yours. Surface it, do
not fix it."

### What has already been corrected

Only documents, and only to stop them calling the backtest count "the lab's N". That landed on
12 October as a documents-only change. No command, no screen and no stored number moved.

### One command already prints it the clear way, so you can see what that reads like

This same batch of work added one new lab command — the one that prices the market switch across
the books. It is new, so it had no printed line to inherit, and rather than copy the wording this
decision is about, it signs off with two numbers under two labels: the hurdle called the hurdle,
and the backtest count called the backtest count.

That is **option 1 above, demonstrated once**, on a surface nothing else depends on. It is put
here as evidence, not as a recommendation: you can run that command, see the shape of the line,
and decide whether you want the other ten to read that way. **None of the ten was touched** — the
instruction that opened this work was to surface them, not to fix them, and they are exactly as
they were.

> **For the implementer.** The new command is `lab gate` (`_gate` in
> `engine/src/seer_engine/commands/lab.py`, lab-brakes-and-gate phase 2). Its closing `print`
> reads `Luck hurdle N: <store.gate(conn).n> (policy <...>)` and `Dev trial rows: <before> before,
> <after> after`. It deliberately contains no instance of the string `Lab N (dev trials)`, and
> phase 2's own test asserts that. `grep -c 'Lab N (dev trials)'` on that file still returns
> **10**, both at base commit `d3c1ec4` and after this whole plan set lands.

> **For the implementer — the technical detail behind Decision A.** This block exists so the
> change can be made without re-deriving anything. It is not part of the prose above.
>
> Ten printed lines in `engine/src/seer_engine/commands/lab.py` read
> `Lab N (dev trials) is now <count>` or `… is still <count>`:
>
> ```
> engine/src/seer_engine/commands/lab.py:1399, 1684, 1718, 1739, 1785, 1817, 1870, 1923, 2238, 2287
> ```
>
> Those line numbers are at base commit `d3c1ec4`. The brakes-and-gate work shifts them (it adds a
> flag to one subparser and a whole new subcommand to the same file) without editing any of the
> ten; `grep -n` on whatever branch does the work gives the current positions, and `grep -c` still
> gives ten.
>
> The count is `store.dev_trial_count(conn)`. The gate's N is `store.gate(conn).n`, resolved by
> `npolicy.effective_n` under `store.DSR_POLICY = "methods"`.
>
> Measured 2026-10-12 on a copy of the committed `lab/lab.sqlite` (md5 `4a34ddb8…`; the original
> was not opened, because a lab command migrates the file on connect):
>
> ```
> store.gate(conn)                    -> Gate(n=74, policy='methods')
> store.dev_trial_count(conn)         -> 354 dev trial rows
> npolicy.dev_method_count(conn)      -> 74 distinct methods with a dev trial
> store.pending_gate(conn,'M0030',3)  -> Gate(n=74)    a variant of an existing method: free
> store.pending_gate(conn,'M9999',1)  -> Gate(n=75)    a new method id: +1, retroactively,
>                                                       for all 130 recorded method rows
> ```
>
> The documents-only correction is commit `e9715b2`: `lab/exposure.py`'s module docstring, and
> the exposure plan's invariant 3 and Reconciliation Log C8.
>
> Whoever acts on option 1 or 2 should expect to touch `engine/package_readme.md` (two hits) in
> the same change, and should not expect to touch `docs/runbooks/` (zero hits, verified
> 2026-10-12).

---

## Decision B — a method may now be amended, and nothing charges for it

### What changed

Until today a method in the lab ran **once**. Once it had a result, its file was frozen: if you
wanted to try a different setting of the same idea, you opened a new method, and the new method
cost you a point of hurdle.

As of this plan set, a method that has already run can be given a **new, separately dated block
of extra versions to try**, written down before they are run, and recorded against the method it
belongs to rather than against a new one. Everything else about pre-registration is unchanged:
the block is committed to the repository before anything runs, it carries its own hypothesis and
its own stated expected failure, and nothing that has already been recorded can be edited.

### Why it was done

Because of Decision A's number, read the other way round.

Under the hurdle the lab has applied since 8 October, a new method id costs **+1** — and that
penalty applies backwards, to every one of the 130 methods already on file, making each of them
very slightly harder to believe. A new version of a method that already exists costs **zero**.
Measured on 12 October: adding versions to the two methods this plan set is working on leaves the
hurdle at 74; opening one new method id would move it to 75.

You made that the hard constraint on this work — the new versions had to be versions of the
existing methods, not new methods. The old freeze made that impossible to express, so the freeze
had to grow a door.

It is worth saying plainly that the freeze was not written for the world it now lives in. When
"a change is a new method" was written down, the hurdle counted individual backtests, and a new
method with six versions cost six. Under today's hurdle it costs one. The rule was calibrated
against a price that no longer exists.

### What still guards it

Four things, and they are the reason this is a door rather than a hole.

1. **Nothing recorded is rewritten.** The original record of what a method was when it first ran
   is untouched and still enforced by the database itself. An amendment adds a row; it never
   edits one.
2. **Each amendment is pre-registered in its own right.** Its own date, its own written
   hypothesis, its own stated expected failure, committed before it runs. The commit is the
   pre-registration, exactly as before.
3. **Every version already on file still has to match what the lab holds for it, exactly.** If an
   amendment changed anything about an old version — even by accident — the check fails. This is
   a stronger test than the one it replaces, not a weaker one.
4. **Tuning after seeing a result is still forbidden.** The amendment must be written before the
   run, not after reading it. That rule did not move.

### The gap, stated plainly

The hurdle's own protection against one idea being pushed indefinitely is a floor: the hurdle can
never fall below how many genuinely independent results the lab's own curves show it has.

Measured on 12 October, that floor is **3**, against a hurdle of **74**.

It does not bind. It is nowhere near binding, and nothing else charges for an amendment. So the
honest statement is this: **a method could be amended again and again, indefinitely, and the
hurdle would stay at 74 the whole time.** Each amendment is free. There is no cap and no counter.

That is a real way to fool yourself, and it is the same shape as the thing this lab was built to
prevent — enough attempts at one idea will eventually produce a good-looking number, and if
nothing counts the attempts, nothing deflates the number.

This plan set did not invent a limit. Choosing "three amendments per method" or "six" or "the
hurdle counts amendments too" is picking a number that changes what every future result means,
and that is your call, not a planner's.

### The question

Pick one, or say something else:

- Should a method's amendments be **capped**, and if so at what — a lifetime limit on amendments,
  or a lifetime limit on total versions across all of them?
- Should the hurdle **count amendments as looks**, so that each one costs what it costs?
- Or is the floor described above the **intended and sufficient** answer — the lab already prices
  a family of versions of one idea at zero on purpose, and an amendment is simply another member
  of that family?

Until this is answered, the amendment door is open and uncounted. That is the state of things as
of 12 October, written down rather than left to be discovered.

> **For the implementer — the technical detail behind Decision B.** Not part of the prose above.
>
> The mechanism: a `Method` may carry one or more `Amendment` blocks, each with its own date,
> hypothesis, expected failure and 1..6 `Candidate`s; `lab run --amend MNNNN` executes an
> amendment's never-run digests and records the trials under the existing `method_id`.
> `methods.source_sha` is never rewritten and the trigger `methods_source_sha_once` stays in
> place; each amendment appends a row to the append-only `method_amendments` table carrying its
> own source hash, date and git sha. The freeze test becomes two checks — the file hashes to the
> latest recorded amendment's sha, **and** every recorded candidate still digests to the
> `config_digest` the lab holds.
>
> The refusal that was qualified is `runner.preflight`
> (`engine/src/seer_engine/lab/runner.py:174-178`):
> `"{method.id} is already {status}: a method runs once. A change is a new variation method
> (source_kind='variation', parent_id=...)"`.
>
> The gap, precisely: under `DSR_POLICY = "methods"`,
> `npolicy.effective_n` resolves `n = max(dev_method_count, ceil(participation_ratio))`.
> Measured 2026-10-12 on a copy of the committed database (md5 `4a34ddb8…`):
>
> ```
> dev_method_count      -> 74
> participation_ratio   -> 2.1946   -> ceil = 3
> n = max(74, 3)        -> 74       NCount.floored is False: the floor does not bind
> mean pairwise corr    -> 0.648 over 354 curves on 102 common month-ends
> ```
>
> `pending_gate(conn, '<an existing method>', k)` returns `Gate(74)` for every `k`, so no number
> of amendments moves N. This is the index's Decision D8.

---

## How every number here was measured

Every figure in this document is dated and says what it was measured on. That is deliberate: the
session before this one spent its time correcting measured numbers that had been written down as
permanent facts and then quietly went stale.

- All hurdle, backtest-count and method-count figures: **2026-10-12**, on a byte-identical copy of
  the committed lab database, with the original left unopened and unchanged.
- The ten printed lines and their positions: **2026-10-12**, on this plan set's base commit.
- The count of documents quoting the printed phrase: **2026-10-12**, a search across the whole
  repository.
- Nothing here was measured against the test window, and no test-window look was spent.

If you are reading this more than a few weeks after it was written, re-measure before acting on
any number in it.
````

**Impact:** a new document; nothing imports it, nothing tests it, nothing depends on it. It is
the deliverable R5 asks for.

---

### Step 2: Append the dated revision to the design doc

**File:** `docs/plans/2026-10-04-method-lab-design.md:512` (append at end of file — the file is
512 lines and ends with `…cannot manufacture.` followed by a single newline; the last existing
section is `### 8.6 The rule, in short`)
**Change:** append the text below, preceded by one blank line, so the new section begins at what
is currently line 513. Do not edit a single existing line: §2's and §4's original wording stays
as it is, exactly the way §7 and §8 left §3's wording alone.

Authority note for the implementer: §6, §7 and §8 are all headed `(owner)` because the owner
decided them. This one must **not** be, because he did not. It records what was built under his
instruction, and it says out loud which part is still his to settle.

**Code:**

````markdown

## 9. Revision 2026-10-12 (built under the owner's instruction of 2026-10-12; one question still open): a method may be amended

**This section is not an owner decision.** §6, §7 and §8 record things the owner decided. This one
records a change made by a plan set acting under his instruction of 2026-10-12 — "these must be
VARIANTS of the existing method files (free in N) and not new method ids" — and it flags the part
that is still his to settle and has not been put to him before now. Read it as "this is what the
lab does as of today, and here is the piece nobody has decided".

The sections it qualifies are left exactly as written. Corrections here are dated rather than
overwritten, so the original still records what was believed when it was written.

### 9.1 What changed

A method that has already run may now carry one or more **amendments**: additional fixed variants,
pre-registered in their own right and recorded under the method's own id.

Before this, `lab run` refused outright — "a method runs once. A change is a new variation method"
— and the only path to a new variant was a new method id.

### 9.2 §2's "1–6 fixed variants per run" — an amendment is a run

**Clarified, not changed.** The 2026-10-04 owner decisions line at the top of this document reads
"scope = one idea with 1–6 fixed variants **per run**", and §2 says a method file exports
`METHOD = Method(...)` with 1–6 fixed `Candidate`s.

The cap is now read the way that sentence is written: **per run**. The method's original candidate
tuple keeps its own 1–6, and each amendment carries its own 1–6. There is no cap on a method's
lifetime total — see §9.5, which is the open question.

This reading was forced by the data, not chosen for convenience: one method in the lab already
holds five recorded candidates, so a per-lifetime cap of six would have left room for one variant
and silenced the question this plan set was asked to answer on that book.

### 9.3 §4's guardrail — qualified, not lifted

**Qualified, §4 guardrails, the last clause only.** The original wording, 2026-10-04, stands as
written:

> never tune after seeing a result within a method (tuning is a new variation method with new
> trials)

**The prohibition is unchanged. The remedy has a second form.** Tuning after seeing a result is
still forbidden, and nothing in this revision permits it. What changes is that "a new variation
method with new trials" is no longer the *only* way to try a different setting of the same idea: a
**pre-registered amendment** — committed, with its own date, its own hypothesis and its own stated
expected failure, all written before any result is seen — is now a second legitimate path, and it
does not mint a method id.

The distinction that matters is unchanged and is the whole point: *pre-registered* versus
*post-hoc*. An amendment written before the run is pre-registration. A variant chosen after
reading a result is tuning, and it is still refused.

### 9.4 Why, and what still guards it

**Why.** Under the `methods` N policy in force since 2026-10-08, a new method id costs **+1 N**,
retroactively, for every method already on file; a variant of an existing method costs **nothing**.
Measured 2026-10-12 on a copy of the committed `lab/lab.sqlite` (md5 `4a34ddb8…`):
`store.pending_gate` on an existing method returns `Gate(n=74)` for any batch size, and on a new
id `Gate(n=75)` against 130 recorded method rows. The 2026-10-04 freeze was written when N was the
dev trial **row** count, where a method with six variants cost six, not one. The rule was
calibrated against a price that no longer exists.

**What still guards it.**

- `methods.source_sha` is never rewritten; the trigger `methods_source_sha_once` stays in place
  and keeps meaning exactly what it says.
- Each amendment appends a row to an append-only `method_amendments` table with its own source
  hash, date and git sha. The commit is still the pre-registration, and an uncommitted or dirty
  file is still refused.
- The freeze test becomes two checks, stronger together than the one they replace: the file hashes
  to the **latest** recorded sha, **and** every candidate already recorded still digests to the
  `config_digest` the lab holds.
- `trials`, `trial_moments`, `trial_funding` and `trial_provenance` stay append-only. No recorded
  row is edited or deleted.

### 9.5 The open question — not decided here

The `methods` policy's only guard against one idea being amended without limit is its floor,
`N = max(distinct_methods, ceil(participation_ratio))`. Measured 2026-10-12 on the committed
database, that floor is `ceil(2.19) = 3` against 74 methods. **It does not bind**, and nothing else
charges for an amendment: a method could in principle be amended indefinitely with N never moving
off 74.

No cap was invented here. Choosing a number changes what every future result means, and that is
the owner's call.

The question is put to him in `docs/plans/2026-10-12-lab-n-and-amendments-owner-decision.md`
(Decision B), together with the separate question of what `lab` should print as N (Decision A).
**Until he answers, this section describes a door that is open and uncounted.**
````

**Impact:** the design document gains a ninth top-level section. No existing line changes, so
nothing that quotes §2, §3 or §4 by line goes stale. No code reads this file.

---

### Step 3: The phase's own exit checks

**File:** none — these are commands, not edits.
**Change:** run all four and record the output. Steps 1 and 2 are not done until these pass.

**Code:**

```bash
cd /home/miftah/.worktrees/seer/lab-brakes-and-gate

# 1. exactly two files, both under docs/plans/
git status --porcelain
git diff --stat HEAD -- docs/plans/

# 2. THE phase's own check: zero bytes of engine/ changed
test -z "$(git diff HEAD -- engine/)" && echo "OK: engine/ untouched" || { echo "FAIL"; exit 1; }

# 3. the ten strings are byte-for-byte unchanged
test -z "$(git diff HEAD -- engine/src/seer_engine/commands/lab.py)" \
  && echo "OK: commands/lab.py untouched" || { echo "FAIL"; exit 1; }
grep -c 'Lab N (dev trials)' engine/src/seer_engine/commands/lab.py   # must print 10

# 4. nothing else moved either
test -z "$(git diff HEAD -- lab/ web/ db/)" && echo "OK: lab/ web/ db/ untouched" || { echo "FAIL"; exit 1; }
```

**Impact:** turns "this phase changed no code" from a claim into a check. Check 2 is the exit
criterion the scope statement asks for by name.

---

## Verification

**Build:** none — no code changes. The two files are markdown and nothing imports them.

**Tests:** the suite is untouched but must still be green, which is index invariant 1.

```bash
docker start seer-pg
cd /home/miftah/.worktrees/seer/lab-brakes-and-gate
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
PYTHONPATH=/home/miftah/.worktrees/seer/lab-brakes-and-gate/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests
```

Expected: the same pass/skip counts as the commit this phase starts from. Re-measure rather than
asserting a figure — on `main` @ `d3c1ec4` the baseline was 4364 passed / 3 skipped, but peer
phases 1–4 add tests, so whatever this phase inherits is the number it must leave behind
unchanged. This phase adds no test and removes none; a changed count means something else moved.

**Manual check:**

- Read the memo's Decision A end to end and confirm it names **no** preferred option. The
  instruction was "Surface it, do not fix it"; a memo that recommends one is a memo that fixed it.
- Read the memo's Decision B and confirm the gap is stated without softening — the sentence "a
  method could be amended again and again, indefinitely, and the hurdle would stay at 74 the whole
  time" must survive editing.
- Confirm §9's heading does **not** say `(owner)`, and that §9.1's first paragraph says the owner
  has not decided this.
- Confirm no line of §2, §3, §4, §6, §7 or §8 of the design document changed:
  `git diff HEAD -- docs/plans/2026-10-04-method-lab-design.md` must be a pure append — every
  line in the hunk prefixed `+`, none prefixed `-`.
- Confirm the prose in the memo carries no method ids, digests or code outside the two blocks
  headed **For the implementer**.

**Exit criteria:**

1. `docs/plans/2026-10-12-lab-n-and-amendments-owner-decision.md` exists and carries both
   decisions: §5.1 stated as the handover states it (ten line numbers, 354 against 74, the three
   options named and none chosen), and the amendment rule's integrity trade-off with its one open
   question.
2. `docs/plans/2026-10-04-method-lab-design.md` carries a `## 9.` dated revision recording the
   amendment rule **beside** the 2026-10-04 wording it qualifies, with no existing line edited and
   no claim that the owner decided it.
3. `git diff HEAD -- engine/` is **empty**.
4. `git diff HEAD --stat` lists exactly two paths, both under `docs/plans/`.
5. `grep -c 'Lab N (dev trials)' engine/src/seer_engine/commands/lab.py` still returns 10 — on
   the branch with phases 1 and 2 landed, not only at `d3c1ec4` (reconciler, C8). The ten are
   untouched and phase 2's new command adds none.
6. The memo says **ten**, and its line numbers are labelled as being at base commit `d3c1ec4`.
7. The suite is green at whatever count this phase inherited.

---

## Handoffs

- **The §5.1 fix itself — to the owner, not to a phase.** If he picks option 1 or 2, the work is
  the ten lines at `commands/lab.py:1399, 1684, 1718, 1739, 1785, 1817, 1870, 1923, 2238, 2287`
  **as numbered at `d3c1ec4`** — re-grep on whatever branch does the work, because phases 1 and 2
  shift them — plus `lab gate`'s closing print as the worked example of what option 1 reads like,
  plus the two hits in `engine/package_readme.md`, plus whatever asserts the printed text in
  `engine/tests/`. That is a new plan set, and it still serves R5 only in the sense of closing it;
  no phase of **this** set may do it (index invariant 9).
- **Phase 5's write-up.** `docs/backtests/2026-10-12-brakes-and-gate.md` reports what the
  amendments actually produced. This memo deliberately states no result from those runs, so the
  two can land in either order and neither needs re-editing when the other does. If Phase 5 lands
  first, do **not** fold its numbers into this memo — it is a policy document.
- **A lifetime cap on amendments, if the owner wants one.** It would live in `lab/method.py`
  (a `Method`-level validation across `candidates` plus every `Amendment`) or in `npolicy.py`
  (counting amendments as looks). Neither is designed here, and neither belongs to any phase of
  this set — index Decision D8 chose "rely on the shipped policy, and surface the gap".
- **A mechanism that keeps a measured number from going stale.** Handover §7 names this as the
  pattern behind every correction that session made, and nothing executable yet depends on any
  figure in these two documents. Out of scope for R5; worth a plan of its own.
- **`DELISTING_STRESS_ROSTER_RULES_PLAN.md`'s "N is 110 and stays 110".** Handover §5.2
  deliberately left it, reading it as a record bounded to its own branch. Still left. Not R5.

## Rollback

Text only, and both changes are confined to `docs/plans/`.

```bash
cd /home/miftah/.worktrees/seer/lab-brakes-and-gate
git revert <this phase's commit>
```

Or, before the commit:

```bash
rm docs/plans/2026-10-12-lab-n-and-amendments-owner-decision.md
git checkout -- docs/plans/2026-10-04-method-lab-design.md
```

Reverting this phase removes the owner's written decisions and leaves the amendment mechanism
Phase 1 built in place, undocumented — which is the state the handover's §7 warns about. If this
phase is reverted and Phase 1 is not, say so in the handover.

No other phase depends on these two files: Phases 1–5 touch code, the lab database and a backtest
write-up, and none of them reads a plan document at runtime. Reverting this phase alone cannot
break the build or the suite.
