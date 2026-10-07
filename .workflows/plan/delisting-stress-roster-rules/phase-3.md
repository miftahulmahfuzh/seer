# Phase 3: The roster replacement rule

**Plan set:** `DELISTING_STRESS_ROSTER_RULES_PLAN.md`
**Analysis:** `20261007-170515-0CU0_code_analyzer.md`
**Satisfies:** R4 — Q4's rule for when a paper roster entry may be replaced, written before the
first entry looks bad
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `docs/plans`

---

## Goal

`docs/plans/2026-10-04-method-lab-design.md` gains one new top-level section — expected **§8**,
resolved at write time — stating when a paper roster entry may be replaced, what is never a
sufficient reason, and what a swap costs. After this phase, a session that wants to change the
roster has a rule to argue against instead of a leaderboard to argue from, and that rule exists
*before* any entry has a forward record anyone could call bad. It is a document: no code, no
database, no lab trial, N stays 110.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts.

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `docs/plans/2026-10-04-method-lab-design.md` **§8, "The roster replacement rule (2026-10-07)"**
  — appended at the file's tail, after §7.6. Section number resolved at write time (Step 1); §8 is
  the next free top-level number — **re-verified at `ba8a05b`**, where the file is 281 lines and its
  top-level headings are §1–§7 with §7.1–§7.6. **No collision with phase 2 is possible:** phase 2
  appends to a different document (`docs/plans/2026-10-03-seer-design.md`, where it takes §14).
- Six subsections, which are the stable citation handles phase 5 may use:
  - **§8.1 — What a swap costs, in one number** (the 18-month clock, both halves of the cost)
  - **§8.2 — Three reasons that are never enough on their own** (the refusals, `R1`/`R2`/`R3`)
  - **§8.3 — Five reasons that are enough** (the triggers, `T1`–`T5`)
  - **§8.4 — Retire, replace, add: three different actions** (and the record)
  - **§8.5 — Family diversity is a value, and no column prices it**
  - **§8.6 — The rule, in short** (the five questions a proposal must answer)

**Named refusals phase 5 may cite by label:**
- `§8.2 R1` — "its DSR fell below the bar" is never, by itself, a reason to replace an entry.
- `§8.2 R2` — "another candidate now scores higher" is never, by itself, a reason.
- `§8.2 R3` — "it is behind SPY" / "it had a bad run" is never, by itself, a reason.

**Named triggers phase 5 may cite by label:**
- `§8.3 T1` — the book is broken, or is not the book that was admitted.
- `§8.3 T2` — the **forward** record fails one of design §1's five conditions on its own terms
  (earliest at the entry's own 18-month mark; one carve-out for condition 4, max drawdown).
- `§8.3 T3` — the entry can never satisfy design §1 at all.
- `§8.3 T4` — the forward record is not a record of the strategy (a paper-night defect).
- `§8.3 T5` — the owner decides.

**Signature changes:** none.
**Requires (from earlier phases):** none. Phase 3 has no `depends_on`.
**Requires (from outside this plan set):** design §1 item 1 as the owner revised it on 2026-10-07
— **"≥ 18 months of forward paper trading"**, with the `≥ 100 closed trades` clause deleted.
**This has landed** — verified by the reconciler on the branch merged to `origin/main` @ `ba8a05b`:
`docs/plans/2026-10-03-seer-design.md:17` reads
`1. ≥ 18 months of forward paper trading  *(revised 2026-10-07; was "≥ 3 months … and ≥ 100 closed trades" — see §13)*`,
and `§13` is the dated revision note. That file is `seer-fc`'s and this phase **must not touch**
it. §8.1's prose cites the revision and says explicitly that it is recorded
in design §1 and §11 and applied elsewhere, so the section is correct whether or not `seer-fc`'s
commit has landed when this one does.

**Leaves alone (owned by others):**
- `docs/plans/2026-10-03-seer-design.md` — all of it (`seer-fc` + phase 2).
- `engine/src/seer_engine/paper/roster.py` — cited, never edited (phase 5, conditionally).
- `lab/lab.sqlite` — not opened. No insight, no trial, N stays 110.
- `docs/handover/2026-10-07-mom-fr-under-the-replacement-rule.md` — phase 5's document.
- Every file `seer-fc` claimed (plan index, *Out of scope*).

**Does not satisfy, and must not drift into:** R3. §8 names no roster entry as a candidate for
replacement. Judging `MOM-FR` is phase 5's work under R3; a rule that prejudges it is the exact
failure Q4 warns about.

## Files

| File | Action | What changes |
|---|---|---|
| `docs/plans/2026-10-04-method-lab-design.md` | modify | append one new top-level section at the file's tail, after §7.6 (currently ends at **line 281**). Nothing above line 281 is edited. |

## Implementation Steps

### Step 1: Resolve the section number

**File:** `docs/plans/2026-10-04-method-lab-design.md` (read only, no edit)
**Change:** read the file's existing top-level headings and take the next free integer. Do not
hardcode 8 without checking — another session may have appended one first.

**Command:**

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules
grep -n '^## [0-9]' docs/plans/2026-10-04-method-lab-design.md
wc -l docs/plans/2026-10-04-method-lab-design.md
```

**Expected — re-verified by the reconciler at `ba8a05b`, unchanged by the merge:**

```
18:## 1. Lab database — `lab/lab.sqlite` (committed)
39:## 2. Plug-and-play
56:## 3. Promotion
75:## 4. The skill
95:## 5. Tests and build order
106:## 6. Revision 2026-10-04 (owner): no human in the loop, Sera, the journal
122:## 7. Revision 2026-10-07 (owner): the luck bar at 0.90, and the N left alone
281 docs/plans/2026-10-04-method-lab-design.md
```

**If the highest is 7** → the new section is **§8** and Step 2's text is used verbatim.
**If something has appended an §8** → the new section is **§9**: replace every `8.` with `9.` and
every literal `§8` with `§9` in Step 2's text before writing (the internal cross-references
`§8.1`–`§8.6` are the only self-references; the `§7.x` and `§3` references are to other sections
and never change). Record the number used in the commit message so the reconciler and phase 5 can
follow it.

**Impact:** decides every self-reference in the appended text, and the handle phase 5 cites.

### Step 2: Append the section

**File:** `docs/plans/2026-10-04-method-lab-design.md:282` (append at EOF; the file ends with a
newline after `it; only the re-run can.`)
**Change:** append the text below verbatim, preceded by one blank line. No existing line is
touched. Keep the file's wrap discipline — prose lines at or under 99 columns, which the text
below already satisfies; §8.4's two long table rows are the only exceptions, and markdown table
rows cannot be wrapped.

**Code:**

```markdown

## 8. The roster replacement rule (2026-10-07)

**Why this exists, and why now.** Nothing on the paper roster has gone wrong. The first paper
night ran on 2026-10-07 with six entries — SPY, `C`, `RMW-FR`, `RAW-FR`, `MOM-FR`, `MVW-FR`
(handover `2026-10-07-roster-first-night-and-survivorship.md` §1) — and not one of them has a
forward record yet. That is exactly the moment to write this down, because a rule written after an
entry looks bad is a rule written to justify a swap somebody already wants. The instruction is Q4
of that handover's §5, verbatim:

> **Q4 — do not churn the roster on lab results.** Every swap restarts a ~15-month clock (Q2), and
> DSR falls monotonically as Sera explores (§2), so "it no longer passes the luck test" will become
> true of *everything* on the board without any book changing. A rule for when a roster entry may
> be replaced — before the first one looks bad — would be worth more than any individual swap.

**What this section binds, and what it does not.** It binds the agents: this skill,
`/sera-the-explorer`, and any session that proposes a roster change. It does not bind the owner.
Admission to the paper roster has always been the owner's judgement and was never the lab's gate
(§7.4; `paper/roster.py` module docstring), and removal sits in the same place. What the rule asks
of the owner is only what §7.4 already fixed for admission: that the reason be written on the
entry rather than left in a commit message.

**Who wrote it, and on what.** Written 2026-10-07 by the `/analyze` session for
`docs/handover/2026-10-07-roster-first-night-and-survivorship.md` (session
`20261007-170515-0CU0`), under the instruction in that handover's §5 Q4, before any roster entry
had a forward record. Overturned only by a dated revision in this section's style, saying who
decided and on what.

### 8.1 What a swap costs, in one number

Design §1 item 1 is the cost. As the owner revised it on 2026-10-07, it asks for **≥ 18 months of
forward paper trading**, and the old `≥ 100 closed trades` clause is deleted outright rather than
re-levelled. *(That revision is recorded in design §1 with its own dated note and in §11; it is
not restated here and this document does not edit it. The superseded reading — "≥ 3 months and
≥ 100 closed trades", which bound at 15 to 21 months depending on how often a book traded — is
what the handover's Q2 was about, and the per-entry month figures derived from trade rates are
superseded with it. **Build on 18 months flat.**)*

A replacement buys exactly two things:

- **a fresh 18-month wait** on the incoming entry, which has no forward evidence at all, and
- **the forfeit of however much of the incumbent's 18 months had already run.**

A swap six months into the roster's life does not move that slot six months closer to a
real-money decision. It moves it **twenty-four months away** from one: six months thrown away and
eighteen more to serve. On the roster's current start, the earliest date any entry can satisfy
item 1 is roughly **April 2028**, counted from each entry's own first paper session — and every
swap pushes its slot's date out by the full elapsed time plus eighteen months. **A swap is the
most expensive action available on this roster, and it buys nothing that can be measured on the
day it is made.**

Two things make that cost easy to miss, and both are worth saying out loud.

1. **The lab cannot see it.** No column in `lab/lab.sqlite` carries a paper clock. A candidate
   that scores better on the dev window scores better whether the roster has been running for a
   day or for a year, so a decision taken from the lab's leaderboard is taken with the price tag
   off the screen.
2. **The roster has no size limit.** Nothing in `paper/roster.py` or in the `strategies` table
   caps the number of entries; `roster.active` is a filter, not a quota. **A promising candidate
   does not have to displace anything.** Adding an entry starts one new clock and resets none.
   Adding is therefore almost always the cheaper move — §8.5 says what it does cost, because it is
   not free either.

### 8.2 Three reasons that are never enough on their own

**R1 — "its DSR fell below the bar."** Never, by itself.

§7.3 measures why. `M0022-W-TV16` scores 0.916 at N = 110 and is dev-eligible today; it falls
below the 0.90 bar at **N = 143** — 33 more dev trials, roughly one and a half Sera nights — and
to ≈0.877 by N = 200. Not one price changes in that interval, and no book changes a line. The
deflated Sharpe ratio is a correction for **how many things the lab has tried**, so it falls for
every candidate ever scored, forever, as a direct consequence of the lab working as designed.
Treating that fall as news about a book would retire the whole roster on a schedule set by how
busy Sera was last night.

Three of the four quant entries were in fact admitted *already failing* this test, each carrying
both numbers in its own `LAB_PROVENANCE` reason (handover §2: `M0007-N20-RAW` 0.914 at N = 85 and
0.899 at N = 110; `M0002-REL-85` 0.854 at N = 80 and 0.828 at N = 110; `M0008-N30-C07` 0.817 at
N = 74 and 0.780 at N = 110). Their scores falling further is the mechanism continuing, not a fact
arriving. A score that falls because the lab kept searching is a statement about selection, not
about the book — which is what `paper/roster.py` has said since the entries were admitted.

**R2 — "another candidate now scores higher."** Never, by itself.

Measured 2026-10-07 against the live gate (N = 110, `DSR_MIN` 0.90, the 20% drawdown bar):
**26 of the lab's 110 recorded dev trials clear all five owner conditions**, and several of them
score above entries that are on the roster. That number only grows as the lab searches. If "a
better-scoring candidate exists" were a trigger, it would fire permanently, for every slot, from
today — which is Q4's warning stated as arithmetic.

And the comparison is not like-for-like. A challenger's score and an incumbent's score are both
measurements on the same 1996–2015 dev window, which all 110 trials have now seen, selected from
by a search that is still running. The incumbent has one thing the challenger does not: forward
sessions that nobody could have selected on. **Forward paper outranks any dev-window difference,
because forward paper is the only evidence this project holds that was not searched over.** That
is also why these entries were admitted on the owner's judgement rather than on the lab's gate
(§7.4): paper trading is how a near-miss earns the right to be taken seriously, and a near-miss
cannot earn that if its clock is restarted every time the lab finds a prettier number.

**R3 — "it is behind SPY" / "it had a bad run."** Never, before §8.3's T2 can fire.

Measured from the recorded dev curves and recorded in `20261007-170515-0CU0_code_analyzer.md`
(measured by session `seer-fc`): the share of rolling windows in which each roster entry actually
beat total-return SPY is **50–59% at 3 months, 53–65% at 12 months, and 65–78% at 36 months**. A
book with a real edge loses to SPY in close to half of all quarters and in about a third of
three-year windows. A short losing stretch is therefore the expected behaviour of a strategy that
works. Reading it as failure is reading noise, and acting on it costs an 18-month clock (§8.1).

### 8.3 Five reasons that are enough

Each of these is a statement about the book, the code, the design conditions, or the owner — never
about the lab's leaderboard.

**T1 — the book is broken, or is not the book that was admitted.** A defect in the strategy, the
allocator, the trade rules, the evidence code, or the data it reads at decision time, such that
what traded is not what was described. This is the only trigger that waits for nothing. *Note the
mechanical consequence:* a fixed book is a **new id with its own clock**, never an edited entry —
`spec_digest` is pinned in `tests/test_paper_roster.py` and `paper` refuses a started id whose
stored digest differs (`paper/roster.py` module docstring). There is no such thing as repairing an
entry in place, so T1 always produces a retire plus an add (§8.4), never a correction.

**T2 — the forward record fails on its own terms.** The entry's **forward paper** record — not a
dev-window number, not a DSR re-scored at a larger N — fails one of design §1's five conditions.
The earliest honest date for this is the entry's own 18-month mark, for the reason in R3: before
then the forward record is too short to say anything, and §1 item 1 *is* the statement that it is
too short.

**One carve-out, and only one.** Condition 4 — max drawdown ≤ 20% — can fail early and
unambiguously, because a realised drawdown past the bar is a fact rather than a sample-size
question. An entry that draws down beyond 20% on paper has failed a condition that no number of
remaining months can un-fail over that record. No other condition gets this treatment: beating
SPY, profit factor and trade behaviour are all statements about a distribution, and all of them
need the full window.

**T3 — the entry can never satisfy design §1 at all.** The screen the owner applied on 2026-10-07
(handover §1), read literally: *can this ever meet the five conditions?* `F4-MOM12-N20-TREND-FR`
was retired because its 22.2% dev-window drawdown is outside the 20% bar, which item 4 refuses
permanently. `F1-SPY-SMA200-M-FR` was retired because it closed 11 trades in 22 dev-window years
against the then-standing 100-trade clause. Neither needed a forward record to be judged.

*A standing note on T3, because one of its own examples moved the same day.* The owner's revision
of item 1 deleted the trades clause, so `F1-SPY-SMA200-M-FR`'s recorded retirement basis
(`paper/roster.py`: "11 dev-window trades cannot pass owner condition 1 (>= 100)") no longer
describes a live condition. An entry retired under a condition that later moves is **not**
automatically re-admitted, and no session may re-admit one on that ground. What is true is that
its basis has changed, and saying so to the owner — who may then re-admit it under a new id with
its own clock, or not — is the correct action. The record is not edited either way: §7's rule is
to preserve superseded wording and date what superseded it.

**T4 — the forward record is not a record of the strategy.** A defect in the paper night rather
than in the book: a bar window that did not cover the entry's lookback
(`commands.paper._check_window`), missed sessions, a stale or wrong input, a verdict source that
was not there. The remedy is the same shape as T1 — the record is void, and the honest repair is a
new id with a clean clock, never a reinterpretation of a corrupt one.

**T5 — the owner decides.** Admission was never the lab's gate and neither is removal (§7.4;
`paper/roster.py` module docstring). The owner may retire or add any entry at any time for any
reason, including a reason this section calls insufficient. The one thing the rule asks is that
the reason is recorded in the shape §7.4 established — the basis and a one-line reason, carried on
the entry outside the spec digest — so that the next reader is not left with a commit message.
This rule sits inside the owner's judgement; it does not sit above it.

### 8.4 Retire, replace, add: three different actions

These are routinely said as if they were one thing. They are not.

| action | what it does | what it costs |
|---|---|---|
| **retire** | sets `status = 'retired'`; the entry stops trading tonight | the rest of that entry's own 18-month clock |
| **add** | a new row, a new id, a new paper clock | one new 18-month clock; nothing already running moves |
| **replace** | a retire and an add, taken together as one decision | both of the above |

**A replacement is never a primitive.** It is a retire that must be justified under §8.3 and an
add that must be justified on its own merits, and the rule is satisfied only if *both* halves
stand up alone. "This candidate scores better" is an argument for an add. It is not an argument
for the retire, and without a trigger from §8.3 the retire does not happen — which is the whole
content of R2, restated as a procedure.

**What happens to a retired entry's record.** Nothing is deleted, and this rule does not re-invent
the answer because `paper/roster.py` already holds it: `status` is lifecycle, not definition — *"a
retired entry keeps every row it ever wrote and stays on the leaderboard: it only stops trading"*
(module docstring; `roster.active` is the filter the paper night uses). `status` and `paper_end`
are deliberately outside `spec()`, so retiring an entry does not move its frozen digest and does
not disturb any other entry. The one exception is cosmetic and already shipped: an entry that is
retired **and never traded** is hidden from the app, because it has no record to show
(`web/lib/data.ts:101`, `WHERE NOT (status = 'retired' AND paper_start IS NULL)`).

So a retirement costs the roster that entry's forward clock. It costs the record nothing.

### 8.5 Family diversity is a value, and no column prices it

The four quant entries come from four different lab methods and are four different bets: M0022
(the weekly-brake book), M0007 (the same engine with the brake removed, admitted as the controlled
forward comparison of whether the brake pays), M0002 (regime-scaled total-return momentum) and
M0008 (minimum-variance sizing — the only entry that changes *sizing* rather than ranking). Each
is the roster's only holder of its family, so each slot is currently buying a different answer.

The lab's leaderboard does not know this, and left to itself it would spend it. Measured
2026-10-07: the two highest-scoring non-roster candidates in the lab are `M0020-W-NOSTOP`
(DSR 0.913) and `M0022-W-TV14` (DSR 0.912) — and **both are the weekly-brake family that `RMW-FR`
already occupies**. A roster assembled by taking the top of the DSR column would raise its average
lab score and collapse onto one family in the same move, and would then learn one thing forward
instead of four.

**The rule therefore states diversity as a value rather than as a formula.** Coverage across lab
families is a reason to keep an entry that no score will ever supply, and any session proposing a
roster change must say what family coverage the roster would lose. It is not a veto and it is not
arithmetic; it is a cost that has to appear in the argument, because no column will put it there.

**This is also the cost of "just add".** §8.1 says adding is cheap, and it is — but picking the
best of K paper entries after the fact is the same selection problem the lab deflates for (§7.2,
§7.3), applied to a forward window this project only gets one of. The more entries run, the better
the best of them looks for no reason at all. That is the real limit on roster size: not a quota in
the code, but the fact that forward evidence is the one thing here that cannot be re-run.

### 8.6 The rule, in short

Before proposing any roster change, a session must be able to answer all five:

1. **Which trigger in §8.3 fires?** Name it. If the answer is a lab score, a ranking, or a losing
   stretch, §8.2 has already refused it and there is nothing to propose.
2. **Is this a retire, an add, or both?** If both, justify each half separately (§8.4).
3. **How much forward clock does the retire throw away, and how much does the add commit to?** In
   months, counted from each entry's own first paper session, against the 18 of §8.1.
4. **What family coverage would the roster lose?** (§8.5.)
5. **Is the reason written on the entry**, in §7.4's shape, so the next reader does not need this
   conversation to understand the board? (§8.3 T5.)

The default answer is **no change**. That is not inertia: on 2026-10-07 the roster's entire
forward record was zero sessions old, and every month it is left alone is the only kind of
evidence this project cannot manufacture.
```

**Impact:** the lab design doc gains a policy section that binds every future session proposing a
roster change, and gives phase 5 a rule to apply by name. No code, no database, no test moves.
`§7.4`'s paper-vs-lab divergence now has a companion that says what *removal* costs, which it
previously did not.

### Step 3: Check the appended text for scope leaks

**File:** `docs/plans/2026-10-04-method-lab-design.md` (read only)
**Change:** none — a verification of Step 2's own boundaries, run before committing.

**Commands:**

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules

# 1. The rule must not name MOM-FR or M0002-REL-85 as a replacement candidate.
#    Expect exactly two hits for MOM-FR (the §8 preamble's roster list, and nothing else)
#    and zero hits for "M0002-REL-85" outside §8.2 R1's measured-numbers list.
awk '/^## 8\./,0' docs/plans/2026-10-04-method-lab-design.md | grep -n 'MOM-FR\|M0002'

# 2. Nothing above the new section changed.
git diff --stat docs/plans/2026-10-04-method-lab-design.md
git diff -U0 docs/plans/2026-10-04-method-lab-design.md | grep '^-[^-]' || echo "no deletions: correct"

# 3. No other file touched BY THIS PHASE. The worktree is shared with the other phases of the
#    set running concurrently, so scope the check to this phase's own path.
git status --porcelain -- docs/plans
```

**Expected:**
- `MOM-FR` appears once, in the §8 preamble's list of the six entries that ran the first night, and
  `M0002` appears twice: once in §8.2 R1's list of recorded DSR pairs and once in §8.5's list of
  the four families. Neither context proposes replacing it. **If the rule names `MOM-FR` as weak,
  as a candidate for replacement, or as the subject of any trigger, the text is wrong — fix it
  before committing.** Judging `MOM-FR` is phase 5's work (R3), not this phase's (R4).
- `git diff --stat` shows one file, insertions only, zero deletions.
- `git status --porcelain -- docs/plans` shows only
  `docs/plans/2026-10-04-method-lab-design.md`. **Unscoped it will also show phases 1, 2, 4 and 5's
  in-flight work** — this worktree is shared and that is expected, not a violation. The only thing
  that must be exactly right is this phase's own commit.

Then commit with an **explicit path allowlist** — never `git add -A`, which would sweep a peer
phase's half-finished work into this commit:

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules
git add docs/plans/2026-10-04-method-lab-design.md
git commit -F - <<'MSG'
docs(lab): the rule for when a paper roster entry may be replaced

Q4 of the 2026-10-07 handover, written before any entry has a forward record anyone
could call bad -- which is the point: a rule written after the first one looks bad is a
rule written to justify a swap. Appended as a new top-level section of the method-lab
design doc; nothing above it is edited.

Names three refusals (a falling luck score, a higher-scoring lab candidate, and a bad
run are each never enough on their own) and five triggers, and prices a swap at the
owner's new 18-month forward clock. Family diversity is named as a value no lab column
prices. No roster entry is named as a candidate for replacement -- judging MOM-FR is
phase 5's work under R3, and a rule that prejudged it would be the failure Q4 warns of.

No code, no database, no lab trial. N stays 110 and the test window stays unspent.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
git show --stat --name-only HEAD   # must list exactly that one path
```

**Impact:** catches the one failure mode Q4 names — a rule written to justify a swap — before it
is committed, and the one boundary violation the reconciler cares about.

## Verification

**Build:** no build. This phase changes one markdown file and no code.

**Headings and self-references** (Step 1's number must be the one actually used):

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules
grep -n '^## [0-9]' docs/plans/2026-10-04-method-lab-design.md
grep -n '^### 8\.' docs/plans/2026-10-04-method-lab-design.md   # expect 8.1 .. 8.6, six lines
awk 'length > 99 {print FILENAME":"FNR": "length}' docs/plans/2026-10-04-method-lab-design.md
```

The last command is expected to print the one pre-existing 148-column line (the §7.1 paragraph
that was already over at `3683d7b`) plus **exactly two lines from the new section — the `retire`
(121) and `add` (108) rows of §8.4's table, which are markdown table rows and cannot be wrapped**.
Any *prose* line from §8 over 99 columns is a mistake; rewrap it.

**Tests** (the suite must still be green; this phase cannot break it, and that is the point of
running it):

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine
PYTHONPATH=/home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  /home/miftah/seer/engine/.venv/bin/python -m pytest tests -q
```

Expect **0 failed, 0 skipped**, at a count no lower than **3197** — the branch baseline, re-counted
by the reconciler at `ba8a05b`. This phase adds no test, but phases 1 and 4 run concurrently in this
same worktree and add theirs, so a **higher** total is correct and a specific total must never be
asserted. Both environment variables are required: without `PG_TEST_URL`
the suite reports a confident `2812 passed, 385 skipped` that is missing every test reading the
`strategies` table; without `PYTHONPATH` pointing at **this worktree's** `engine/src`, pytest
silently tests the main checkout instead of the branch.

**Lab untouched** (invariants 2, 3, 4 — no trial, no N movement, no test-window look):

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules
git status --porcelain lab/   # expect: empty, UNLESS phase 2 has already landed its insight
```

This phase never opens `lab/lab.sqlite`, so N stays at 110 and 0 test-window looks stay 0 by
construction rather than by check. **One caveat for the swarm:** phase 2 legitimately modifies
`lab/lab.sqlite` and `web/data/lab.json` in this same worktree. If `git status` shows them dirty,
that is phase 2's work, not this phase's — confirm with `git diff --stat lab/` and that this
phase's commit lists only the one `docs/plans` path.

**Manual check:** read the new §8 end to end as the owner would, who is not a quant. Every number
must arrive with its meaning attached (18 months, 33 trials, 26 of 110, 50–78%), and every term of
art must be glossed in the sentence that uses it — "deflated Sharpe ratio" is glossed in §8.2 R1
as "a correction for how many things the lab has tried". If a sentence needs the reader to already
know the jargon, rewrite it.

**Exit criteria:**

1. `docs/plans/2026-10-04-method-lab-design.md` carries one new top-level section whose number is
   the next free one at write time, with six subsections §8.1–§8.6.
2. The rule names its own triggers (`T1`–`T5`, §8.3) and its own refusals (`R1`–`R3`, §8.2).
3. It is built on **18 months flat**, states that the 14.9/19.4/20.7-month per-entry table is
   superseded, and does not use those figures as live numbers.
4. It states explicitly that a falling DSR alone is never a reason to replace an entry, with
   §7.3's measured ratchet (0.916 at N = 110 → below 0.90 at N = 143 → ≈0.877 at N = 200) as the
   evidence.
5. It says what happens to a replaced entry's record, by citing `paper/roster.py` rather than
   re-inventing it, and distinguishes retire from add from replace.
6. It names family diversity as a value no lab column prices, with the measured
   `M0020-W-NOSTOP` / `M0022-W-TV14` fact behind it.
7. It is dated and attributed, and says who may overturn it and how.
8. It names no roster entry as a thing to be replaced.
9. `git diff` shows one file, insertions only, and the commit's file list equals the one-path
   allowlist. The full suite passes with **0 failed and 0 skipped** at a count no lower than the
   branch baseline of 3197.

## Handoffs

- **R3, the `MOM-FR` judgement — phase 5.** The analysis's M3 table (26 of 110 clear all five
  owner conditions; `M0002-REL-85` 12th by DSR and **8th of 26 by MAR** — seven candidates sit
  strictly above its MAR of 0.684030; an earlier draft of this line said 7th) is evidence for R3 and is *not*
  used here as an argument about any particular entry. §8 cites the 26 only as the general fact
  that makes R2 a permanent refusal. Phase 5 applies §8.3 and §8.2 by label and does not amend
  them; if phase 5 finds the rule cannot decide its case, that is a finding to report, not a
  licence to edit §8.
- **Design §1 item 1's new wording — `seer-fc`.** §8.1 cites "≥ 18 months of forward paper
  trading" and points at design §1 and §11 for the dated revision note. If `seer-fc`'s final
  wording differs in a way that changes the number, the reconciler should flag §8.1's first
  paragraph; nothing else in §8 depends on the exact phrasing.
- **R2's residue — phase 4.** The dev gate's surviving `_MIN_TRADES = 100`, now asymmetric with
  design §1 item 1, is phase 4's document. §8 deliberately says nothing about the dev gate: it is
  a rule about the paper roster, and the dev window's trades bar never gated paper membership.
- **`F1-SPY-SMA200-M-FR`'s now-void retirement basis.** §8.3's T3 note records that the condition
  it was retired under no longer exists, and that re-admission is the owner's call. **No phase in
  this plan set acts on it.** It is raised here so it is on the record rather than rediscovered as
  a surprise; a future session may put it to the owner.
- **A `lab status` or `lab` CLI surface for the rule.** §8.6's five questions could become a
  checklist the tooling prints when a session proposes a roster change, in the shape of §7.3's
  "within 0.03 of the bar" warning. Not built here — this phase is a document and adds no code.

## Rollback

`git checkout -- docs/plans/2026-10-04-method-lab-design.md` before the commit, or
`git revert <commit>` after it. The phase appends text to one markdown file and nothing else: no
code, no migration, no database row, no `config_digest`, no trial, no test-window look. Reverting
it leaves the tree exactly as it was at `ba8a05b` plus whatever the other phases landed, and the
suite still reports 0 failed / 0 skipped. Phase 5 is the only consumer; if §8 is reverted after phase 5 has
cited it, phase 5's document loses its reference and should be reverted with it.
