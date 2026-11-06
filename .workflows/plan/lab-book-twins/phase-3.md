# Phase 3: Sera skills read the twin line

**Plan set:** `LAB_BOOK_TWINS_PLAN.md`
**Analysis:** `.workflows/analyze/20261106-151026-T7WN_code_analyzer.md`
**Satisfies:** R2 (the Sera relay never presents a control or an already-recorded book as a new one), R3 (slate selection knows a wrapped host re-measures a recorded book, and where the warning lives)
**Depends on:** Phase 1 (`lab twins`, the `Book twins` block in `lab run`, hardgate D19)
**Difficulty:** EASY
**Package:** `.claude/skills`

---

## Goal

After this phase the two Sera skills tell a coordinator and a child, at the points where they
pick, read and relay results, that a follow-up wrapping a recorded host produces a *book twin*;
that a control's or a book twin's money is never reported as a new book but named by its
first-recorded candidate; and that a treatment identical to its own control, or a dose ladder
that is one curve, is a finding ("never acted", "dial never moved"). Both skills name
`lab twins MNNNN` as the check and say that `lab promote` refuses a twin arm (D19).

## Interface Contract

**Deletes:** nothing
**Renames:** nothing
**Creates:** no symbols. New prose in two skill files (9 text edits, listed below).
**Signature changes:** none
**Requires (from earlier phases):**
- Phase 1: `python -m seer_engine lab twins [MNNNN|CANDIDATE ...]` exists and, per arm, prints its role and its first-recorded twin (lowest `n`, same window, same `trades`, byte-identical `curve_json`) with store fingerprints.
- Phase 1: `lab run` prints a block headed `Book twins` after the `Mirror pairs` block.
- Phase 1: `lab promote` refuses (hardgate D19) when the arm to pre-register is a twin of an earlier method's trial or of a same-method control.
- The skill text names only the command, the block heading and "D19". It quotes no line of phase 1's output format, so a wording change in phase 1 does not stale this phase. Reconciler checked phase 1's code: subcommand `lab twins ID [ID ...] [--window dev|test]`; `lab run` heading `Book twins:` (always printed, `Book twins: none. ...` when clean); flag line contains `the treatment never acted`; promote refusal ends `(D19)`. S1, S2, S4, E2-E5 match.
**Leaves alone (owned by others):** all engine code and tests, `.claude/skills/verify-seer/features/lab-cli.md` (Phase 1); `.claude/skills/calculate-assets/*` (Phase 2); every other skill.

**Vocabulary note for the reconciler.** Both skills already use "twin" for the *real-fee twin*
and the *fractional twin* (a one-variant variation method: `sera-the-explorer/SKILL.md:149-150,
211-212`, `explore-and-experiment-new-method/SKILL.md:368, 375, 447`). Every new sentence in this
phase says **"book twin"**, never bare "twin", so the two meanings never collide. Phase 1's
printed heading `Book twins` matches.

## Files

| File | Action | What changes |
|---|---|---|
| `.claude/skills/sera-the-explorer/SKILL.md` | modify | S1 slate rule (after line 92); S2 relay check under "Verify, don't believe" (after line 127); S3 report-table line (line 196); S4 two Never rows (after line 220) |
| `.claude/skills/explore-and-experiment-new-method/SKILL.md` | modify | E1 design-time note on the no-opinion arm (after line 200); E2 `Book twins` reading in step 7's Cover list (after line 244); E3 a gate trap (after line 329); E4 D19 in the `lab promote` bullet (line 340-341); E5 quick-reference line (after line 537) |

Line numbers are against `3b87070` (both files are untouched by phases 1 and 2).

## Facts quoted in the new text (re-measured this session)

Read back from the committed `lab/lab.sqlite` at `3b87070` with a read-only connection
(`sha256` of `curve_json`, grouped by `window` + `trades`):

| Claim in the text | Measured |
|---|---|
| M0488-DVC10-NEVER is M0125-DV-C10's book, first recorded as trial 519 | group {519 M0125-DV-C10, 1536 M0442-DVC10-NEVER, 1674 M0447-DVC10-NEVER, 1676 M0447-DVC10-RECOVER, 1677 M0447-DVC10-RECOVER-CAP730, 1734 M0488-DVC10-NEVER} |
| M0447-DVC10-RECOVER and -RECOVER-CAP730 share M0447-DVC10-NEVER's curve | same group as above |
| M0488-DVC10-DEEP10/15/20 and -DEEP15-NOFALL730 are one curve | group {1736, 1737, 1738, 1739} |
| M0447 and M0488's DVC10-FIXED730 arms are M0442-DVC10-FIXED730's curve | group {1537 M0442, 1675 M0447, 1735 M0488} |
| DEEPTAPE is the owner's name for that book | handover (the owner's note), not the DB; used as a name only |

No group count goes into the skill text. For reference only: 80 groups / 260 rows / 180
duplicates under the twin definition (any store), 74 / 195 / 121 within one store fingerprint, on
1,739 trials; both measured by the coordinator.

## Implementation Steps

Every step is an exact `old_string` → `new_string` pair for the Edit tool. Each `old_string` is
unique in its file.

### Step S1: Slate rule, a wrapped host is not a new book (R3)
**File:** `.claude/skills/sera-the-explorer/SKILL.md:90-93` (new bullet between "Survives real fees?" and "Reserve")
**Change:** insert one slate bullet.
**Old:**
```markdown
     edge the real fees erase is not worth a variation; journal that and pick another.
   - **Reserve** each new idea with `lab idea …`, which prints its id. A backlog row keeps its id.
```
**New:**
```markdown
     edge the real fees erase is not worth a variation; journal that and pick another.
   - **A wrapped host is not a new book.** A follow-up whose arms wrap a book the lab already
     ran (a never-aside or no-opinion control, or a host book under a new allocator id) gives
     that book a new digest, so `lab run` cannot refuse it, and the arm records as a *book twin*:
     the same curve and trades as a trial already in the lab. Reserve it anyway when the idea
     needs it: controls run beside the treatment, and N counts methods, so a book twin costs
     compute and no look. But the slate never counts that arm as a new book, and the hypothesis
     names the recorded host it repeats (M0488's never-aside arm is M0125-DV-C10's book, first
     recorded as trial 519). `lab idea` cannot warn, because an idea row has no arms yet. The
     check comes after the run: `lab run` prints a `Book twins` block, and `lab twins MNNNN`
     prints it again at any time.
   - **Reserve** each new idea with `lab idea …`, which prints its id. A backlog row keeps its id.
```
**Impact:** text only. Answers R3's "skill or `lab idea`": the skill, with the reason `lab idea` cannot.

### Step S2: Relay check under "Verify, don't believe" (R2)
**File:** `.claude/skills/sera-the-explorer/SKILL.md:125-128` (new sub-bullet after the Mirror pairs bullet, before "Whatever is missing")
**Old:**
```markdown
       synthesis either way — a batch that measured its signals and not their price is a finding
       about the batch.

     Whatever is missing, finish it yourself from the scrollback and the data. If the method
```
**New:**
```markdown
       synthesis either way — a batch that measured its signals and not their price is a finding
       about the batch.
     - **Which arms are book twins?** `lab twins MNNNN` (the `Book twins` block `lab run`
       printed) names each arm's role and the first-recorded trial with the same curve. Read it
       before relaying any arm's money or metrics, wherever the figure came from: a child's
       `DONE` line, `lab show`, or `/calculate-assets`. A control's or a book twin's money is
       never reported as a new book; name it by its first-recorded candidate. The case that
       made this rule: M0488-DVC10-NEVER was relayed as a new book, and it is M0125-DV-C10
       (trial 519), the book the owner already holds as DEEPTAPE. A treatment arm that shares
       its own control's curve means the treatment never acted, and a dose ladder whose rungs
       are one curve means the dial never moved. Both go in the synthesis as findings, not as
       books.

     Whatever is missing, finish it yourself from the scrollback and the data. If the method
```
**Impact:** text only.

### Step S3: The closing report table labels controls and book twins (R2)
**File:** `.claude/skills/sera-the-explorer/SKILL.md:196`
**Old:**
```markdown
   - a table of method, verdict, CAGR vs SPY, max DD, PF, trades, DSR
```
**New:**
```markdown
   - a table of method, verdict, CAGR vs SPY, max DD, PF, trades, DSR. A row for a control or a
     book twin says so and names its first-recorded candidate (`lab twins MNNNN`); it is never
     listed as a new book
```
**Impact:** text only.

### Step S4: Two Never rows (R2, R3)
**File:** `.claude/skills/sera-the-explorer/SKILL.md:220` (append after the last table row, which is the last line of the file)
**Old:**
```markdown
| "Its sibling test-failed, but this variant is genuinely different" | Kin is `family` plus every ancestor through `parent_id`. A disproven family does not get a retry under a new id — that is the mechanism the gate exists to close. |
```
**New:**
```markdown
| "Its sibling test-failed, but this variant is genuinely different" | Kin is `family` plus every ancestor through `parent_id`. A disproven family does not get a retry under a new id — that is the mechanism the gate exists to close. |
| "The control made the most money, report it as a find" | A control, or a book twin of a recorded trial, is never a new book. Run `lab twins MNNNN` and name it by its first-recorded candidate (M0488-DVC10-NEVER is M0125-DV-C10). |
| "This follow-up wraps a recorded host, so skip it" or "so count it as a new book" | Neither. It re-measures the host, which is fine: the control runs beside the treatment and N counts methods. Name the host in the hypothesis and don't count the arm as a new book. |
```
**Impact:** text only. Keeps the file ending in a table row (no trailing prose added).

### Step E1: Design time, the no-opinion arm is usually a book twin (R3)
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:199-201` (end of the "third arm with no opinion" bullet)
**Old:**
```markdown
     Check your own method with `lab dressing MNNNN` after it runs; it journals nothing and can
     be re-run freely.
   - Pure. Reads only bars dated ≤ `data_date`. Set `seen_keys`.
```
**New:**
```markdown
     Check your own method with `lab dressing MNNNN` after it runs; it journals nothing and can
     be re-run freely.
     That no-opinion arm usually repeats a book the lab already ran. Wrapping the host's params
     in your own allocator id gives it a new digest, so `lab run` cannot refuse it, and it
     records as a *book twin* of the host (step 7). That is expected and costs no look. Name the
     recorded host in the hypothesis, and never count the arm as a new book.
   - Pure. Reads only bars dated ≤ `data_date`. Set `seen_keys`.
```
**Impact:** text only. Solo mode chooses its own idea, so it needs the R3 note too.

### Step E2: Step 7 reads the `Book twins` block (R2)
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:242-245` (new Cover bullet after the parent-comparison bullet, before `My opinion:`)
**Old:**
```markdown
     never against its recorded trial, or the fees decide the comparison instead of the idea
   - end with a paragraph that starts **`My opinion:`**. Say plainly whether this direction is
```
**New:**
```markdown
     never against its recorded trial, or the fees decide the comparison instead of the idea
   - **book twins**, from the `Book twins` block `lab run` printed (`lab twins MNNNN` prints it
     again; `Book twins: none.` means no arm repeats a recorded book). It names each arm's role and the first-recorded trial with the same curve and the
     same trade count. Three readings, each a finding for the analysis and the journal. A
     control, or a host that repeats an earlier method's book, *is* that book: name it by its
     first-recorded candidate and never report it as a new result. **A treatment arm that shares
     its own control's curve means the treatment never acted**: M0447-DVC10-RECOVER and
     M0447-DVC10-RECOVER-CAP730 have M0447-DVC10-NEVER's curve. **A dose ladder whose rungs are
     one curve means the dial never moved**: M0488-DVC10-DEEP10, -DEEP15, -DEEP20 and
     -DEEP15-NOFALL730 are one curve. Say which in plain words, and never write up the rungs as a
     ladder that was measured.
   - end with a paragraph that starts **`My opinion:`**. Say plainly whether this direction is
```
**Impact:** text only.

### Step E3: A gate trap for the DONE line (R2)
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:329` (append to the trap list in **The gate**)
**Old:**
```markdown
- **N comes from `lab status`**, not from counting trial rows: a method's variants are one look.
```
**New:**
```markdown
- **N comes from `lab status`**, not from counting trial rows: a method's variants are one look.
- **A control or a book twin is not a new book.** Its money and metrics belong to the
  first-recorded trial, already in the lab. In the analysis, the insight and the `DONE` line,
  name it by its first-recorded candidate from `lab twins MNNNN`. M0488-DVC10-NEVER reached the
  owner as a new book; it is M0125-DV-C10, first recorded as trial 519.
```
**Impact:** text only. The string `- **N comes from \`lab status\`**` occurs once (line 329); line 233-234's mention is prose, not a bullet.

### Step E4: `lab promote` refuses a book-twin arm (R2)
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:340-341` (end of the `lab promote` bullet in **Promotion**)
**Old:**
```markdown
  update. It loads no store, runs no backtest and spends no look.
```
**New:**
```markdown
  update. It loads no store, runs no backtest and spends no look. It also refuses (hardgate D19)
  when that arm is a book twin: of an earlier method's trial (promote that method, or nothing),
  or of one of its own method's controls (the treatment never acted). M0447 and M0488 are both
  dev-eligible on an arm whose curve is M0442-DVC10-FIXED730's. Like the fold and kin refusals,
  D19 has no override.
```
**Impact:** text only. Describes phase 1's D19; does not restate its message text.

### Step E5: Quick reference line
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:537`
**Old:**
```markdown
lab run M0007                     # needs a committed method file
```
**New:**
```markdown
lab run M0007                     # needs a committed method file
lab twins M0488                   # report only: each arm's role and its first-recorded book twin (same curve); journals nothing
```
**Impact:** text only.

## Principles applied

- Laziness protocol: no new skill section, no helper script, no `lab idea` change. Nine inserted or extended passages at the five or so places a reader already stops (slate rules, Verify, report table, Never table; design bullet, Cover list, gate traps, Promotion, quick reference), each reusing the surrounding voice.
- Encode lessons in structure: the durable guard for R2 is phase 1's D19 refusal and the `Book twins` block, not prose. This phase points both skills at those mechanisms (`lab twins`, D19) instead of asking the reader to compare curves by eye; the prose only says how to read them and what to call the result.
- Make illegal states unrepresentable (applied to vocabulary): "twin" already means the real-fee or fractional twin in both skills, so every new sentence says "book twin", and the reconciler is told so in the Interface Contract.
- Prove it works: Proof drives the command the skills now name (`lab twins M0488`, `lab twins M0447`) through verify-seer and checks that its output matches the cases the text quotes, so the text cannot cite a command or a case the tool contradicts.

## Verification

**Build:** none (no code). `git -C /home/miftah/.worktrees/seer/lab-book-twins diff --name-only -- .claude/skills/sera-the-explorer .claude/skills/explore-and-experiment-new-method` prints exactly the two SKILL.md paths.
**Tests:** none needed for text; the engine suite is phase 1's (`PYTHONPATH=engine/src engine/.venv/bin/pytest engine/tests`, unchanged by this phase).
**Proof:**
- Harness: `.claude/skills/verify-seer` (lab drive against a private copy of `lab/lab.sqlite`). Run from the worktree root, after phase 1 has landed in it.
- Feature-map entries: none. The skills are not an app feature; the `lab twins` CLI entry (`features/lab-cli.md`) is phase 1's.
- Journeys:
  1. **Both skills carry the rules.** From the worktree root:
     ```sh
     S=.claude/skills/sera-the-explorer/SKILL.md; E=.claude/skills/explore-and-experiment-new-method/SKILL.md
     grep -c 'lab twins' $S          # >= 3
     grep -c 'lab twins' $E          # >= 4
     grep -c 'never reported as a new book\|never a new book\|never listed as a new book' $S   # >= 3
     grep -c 'never acted' $E        # >= 2
     grep -c 'dial never moved' $E   # 1
     grep -c 'D19' $E                # >= 2
     grep -c 'M0125-DV-C10' $S       # >= 3
     grep -n 'twin' $S $E | grep -v 'book twin\|Book twins\|lab twins\|real-fee twin\|fractional twin\|realistic twin\|\-frac. twin\|the twin\|its fractional' 
     ```
     Passes when every count meets its bound and the last command prints only the pre-existing
     lines `sera-the-explorer/SKILL.md:149-150` ("fractional, real-fee twin", "Promote the twin")
     and `explore.../SKILL.md:368` ("`-frac` twin") or nothing: no new bare "twin".
  2. **The command the skills name exists and agrees with S1/S2/E3** (needs phase 1):
     ```sh
     V=.claude/skills/verify-seer/scripts/verify.sh
     $V up --no-web --empty            # note RUN=
     $V lab $RUN twins M0488
     ```
     Passes when exit code is 0 and the output pairs `M0488-DVC10-NEVER` with `M0125-DV-C10`
     (and shows a trial number 519 or a fingerprint for it), and pairs `M0488-DVC10-FIXED730`
     with `M0442-DVC10-FIXED730`.
  3. **The never-acted and dial-never-moved cases E2 quotes are what the tool shows:**
     ```sh
     $V lab $RUN twins M0447
     $V labsql $RUN "select n, candidate_id, trades from trials where candidate_id like 'M0488-DVC10-DEEP%' order by n"
     $V lab $RUN twins M0488
     ```
     Passes when `M0447-DVC10-RECOVER` and `M0447-DVC10-RECOVER-CAP730` name the same
     first-recorded trial as `M0447-DVC10-NEVER` (M0125-DV-C10), and the four DEEP rows have one
     `trades` value and are reported by `lab twins M0488` as one book: `M0488-DVC10-DEEP15
     (treatment) is the first recording of this book`, and each later rung reads
     `= M0488-DVC10-DEEP15, an earlier arm of this method`.
  4. **E5's quick-reference line runs as written:** `$V lab $RUN twins --help` exits 0.
  Then `$V down $RUN`.
- Neighbor check: the edits only add lines except S3 and E4, which extend one line each. `git diff --numstat` shows 0 deletions for sera except 1 (S3) and for explore except 1 (E4); `grep -c '^| "' $S` rises by exactly 2 (the Never table still parses as one table).
- Cost: none (offline lab drive, no LLM).
**Exit criteria:** both skills name `lab twins` and state that a control's or a book twin's money is never a new book; the explore skill names "the treatment never acted", "the dial never moved" and D19; journeys 1-4 pass.

## Handoffs

- **Phase 2 (R2):** the S2 relay check names `/calculate-assets` as one source of a figure to check, but does not quote phase 2's output. When phase 2 lands, its role/twin line agrees with `lab twins` by construction (same reader). Phase 2's own SKILL.md rule is phase 2's.
- **Phase 1 (R1/R2):** duplicate counts are reconciled (80 / 260 / 180 any store; 74 / 195 / 121 one store). This phase quotes neither.
- Not done, out of scope for every phase: no edit to the `/calculate-assets` relay inside `redo-sera-experiments` or any other skill.

## Rollback

`git revert` the phase's commit, or `git checkout 3b87070 -- .claude/skills/sera-the-explorer/SKILL.md .claude/skills/explore-and-experiment-new-method/SKILL.md`. No data, no DB, no code depends on this text.

## Risks

- The edits name `lab twins`, the `Book twins` heading and D19; the reconciler confirmed all three against phase 1's code. A later rename in phase 1 would stale S1, S2, S4, E2-E5.
- "First recorded" for M0447-DVC10-RECOVER is M0125-DV-C10 (lowest `n`), not M0447-DVC10-NEVER. E2 therefore says the treatment "shares its own control's curve" rather than "is a twin of its control" so it reads correctly whichever name phase 1 prints first.
