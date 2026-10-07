# Phase 7: Docs, the pre-registration wording, and the site's gate

**Plan set:** `LAB_LUCK_GATE_PLAN.md`
**Analysis:** `20261007-085606-D3K1_code_analyzer.md`
**Satisfies:** R1 — the gate admits nothing at 110 trials. This phase is the half of R1 that is
*words*: the rule as written down, in the design document, in the committed pre-registration
format, in the skill the next unattended session reads, and on the site the owner looks at.
**Depends on:** Phase 4 (and, through it, Phases 1 and 2) and **Phase 8** — `tuning.MAX_DRAWDOWN`
is 0.20 and `dev.FAILURE_LABELS`'s drawdown entry follows it, both of which this phase's wording,
fixtures and regenerated snapshot state. Phase 8 also moves the constant's home into
`backtest/metrics.py` with `tuning` re-exporting it; this phase reads it as `tuning.MAX_DRAWDOWN`
either way.
**Difficulty:** NORMAL
**Package:** `docs` + `web` (with three narrow engine edits: the snapshot gate dict, `prereg.py`'s
wording, and their tests)

> **Written against Decisions D1 and D1b as revised 2026-10-07.** The lever that moved is the
> **threshold** — `DSR_MIN` 0.95 → 0.90, the owner's stated risk appetite — and **not** the N.
> `DSR_POLICY` ships as `all-trials`, so design §3's sentence "N = all lab trials" is **still
> true and must not be rewritten**. An earlier draft of this plan amended the N sentence; that
> draft is superseded in full by this file.

---

## Goal

After this phase, every place that states the lab's luck gate states the gate the lab actually
applies: `DSR >= 0.90`, deflated by N = every dev trial in the lab. The design document records
the threshold change the way it records every other decision — as a dated revision that quotes the
sentence it supersedes and attributes the change to the owner, not to an inference — and it records
what was deliberately *not* changed, with the measurement that made that a choice rather than an
oversight. `web/data/lab.json` publishes the policy name, the N it resolved to and the evidence
behind the alternatives, so the unpulled lever stays visible on the site rather than living only in
a plan file.

Nothing here changes a verdict or a constant. `DSR_MIN`, `DSR_POLICY`, `DSR_LABEL`, the gate logic
and every recorded trial belong to phase 4; this phase reads them and writes them down.

---

## Interface Contract

**Creates:**
- `lab.store._gate_n(conn) -> dict[str, Any]` (`engine/src/seer_engine/lab/store.py`, new private
  helper immediately above `snapshot`)
- snapshot keys `gate.dsrPolicy` (str), `gate.dsrN` (int), `gate.dsrNBasis` (str) — additive;
  every existing `gate` key keeps its name, position and meaning. `gate.dsrMin` keeps its name and
  changes **value** only, because phase 4 changed the constant it reads.
- `web/lib/sera/types.ts`: `DsrPolicy`, `DSR_POLICIES`, `DSR_POLICY_LABEL`
- `web/lib/sera/lab.ts`: `requireGate(snap)` — a build-time guard on the three new keys
- `web/lib/sera/derive.ts`: `DSR_FAILURE_PREFIX` **and `DRAWDOWN_FAILURE_PREFIX`** — both
  threshold-bearing labels are matched by prefix (Step 13); exit criterion 0 requires both
- `web/app/sera/overview.ts`: `Luck` gains `refX`, `n`, `policy`, `basis`
- `docs/plans/2026-10-04-method-lab-design.md` §7, "Revision 2026-10-07 (owner)"
- `engine/tests/test_lab_gate_wording.py` (new)

**Signature changes:**
- `prereg.gate_text()` -> `prereg.gate_text(conn: sqlite3.Connection | None = None)`.
  Both existing test call sites keep working unchanged (`conn=None`); the two call sites inside
  `promote_method` start passing `conn`, so **every pre-registration this lab writes states the
  threshold it was judged against and the N in force the day it was written.**

**Deletes:** nothing. No symbol, no config key, no file.

**Renames:** nothing.

**Requires (from earlier phases) — read this list before implementing:**

1. **Phase 4 — `store.DSR_MIN = 0.90`.** D1's headline, the owner's call of 2026-10-07. The index's
   Phase 4 section names phase 4 as its **sole owner** and says "no document is true until it
   lands", which is exactly right: design §7 attributes a threshold change to the owner,
   `prereg.gate_text` interpolates `store.DSR_MIN` into a committed file, and the site's luck bar
   draws `gate.dsrMin`. **Phase 7 does not make this edit** and must not — changing the threshold
   is what makes M0022 eligible, which is phase 4's exit criterion, and two phases writing one
   constant is how a swarm loses it.
2. **Phase 4 — `store.DSR_POLICY = "all-trials"`.** The policy default, deliberately left where it
   is (D1). This phase reads it and documents its value; it never assigns to it.
3. **Phase 4 — the shared prefix-matching luck-label helper, exported from `store.py`.** The index
   now makes this phase 4's obligation: `trials` is append-only, so the 110 recorded rows carry
   `"DSR >= 0.95"` **forever** while a trial judged after the threshold moves carries
   `"DSR >= 0.90"`, and every reader must match by **prefix**, never by equality with the live
   constant. Phase 5 (`commands/lab.py:206`) and phase 7 (`web/lib/sera/derive.ts:20`) are the two
   named callers.

   **Phase 7 cannot call that helper**, and this is the one place the index's instruction does not
   transfer: `derive.ts` is TypeScript running in the Next build, with no path to a Python symbol.
   What Step 13 does instead is mirror the prefix as a single named constant
   (`DSR_FAILURE_PREFIX`) and then *pin the mirror to the engine* two ways, so it cannot drift
   silently:
   - Step 9's guard test reads `derive.ts`, extracts the literal, and asserts
     `store.DSR_LABEL.startswith(...)` — a real cross-language check that holds whatever phase 4
     names its helper, because it tests the property rather than the name.
   - Step 14 asserts against the committed snapshot's own data: every entry in every trial's
     `failed` array either is a known D8 label or starts with the prefix.

   So the dependency on phase 4 is now only the prefix *shape*, which the index guarantees. If
   phase 4 ever changes it, both pins fail loudly rather than rendering a missed luck check as a
   green tick.
4. **Phase 1 — `seer_engine.lab.npolicy.effective_n(conn, policy) -> NCount`**, where `NCount`
   carries:
   - `.n: int` — the multiple-testing N, **>= 0**. Reconciled: an earlier draft of this phase
     asked for `>= 1` on any database. Phase 1's `all-trials` policy is the literal dev row
     count and **returns 0 on an empty lab**, deliberately — it is the "what the lab did before"
     baseline and `lab luck` prints it against the others. `snapshot` runs on empty fixtures, so
     this phase's guard and its snapshot assertion both accept `>= 0`. Do not ask phase 1 to
     floor `all-trials` to make a display guard happy.
   - `.policy: str` — the policy name, one of `"all-trials"`, `"methods"`, `"effective"`
   - `.basis: str` — **one line, no newline, non-empty** — the evidence for `.n` in plain words,
     e.g. `"110 dev trials, every variant run counted as one independent look"`. This string is
     written verbatim into every committed `docs/lab/prereg/MNNNN.md` and into
     `web/data/lab.json`, so it must be stable for a given database and must not wrap.
   - `effective_n` must work on a **read-only** connection (`store.connect_readonly`) and on a
     database still at `schema_version = 1`:
     `test_the_committed_snapshot_is_the_export_of_the_committed_database` opens the committed
     database `mode=ro`, and `snapshot`'s docstring promises it reads only what v1 and v2 share.
     Reading `trials.curve_json` satisfies both.
   - **`.basis` exists and is named `basis`** — reconciled. Phase 1's `NCount` drafted only an
     `evidence()` method, which repeats "N = … under policy …" that `gate_text` and the site
     already say for themselves. Phase 1 now carries a `basis` **property** alongside it,
     specified to this phase's contract: one line, never empty, no newline, stable for a given
     database, saying only *what was counted*. On the committed lab under `all-trials` it reads
     `"110 dev trials, every variant run counted as one independent look"` — which is the string
     this phase's `fixture.ts` mirrors. Because it is a property rather than a field it is **not**
     in `dataclasses.asdict(count)`; phase 5 reads the fields generically and this phase asks for
     `basis` by name, so both are correct.
5. **Phase 4 — the committed `lab/lab.sqlite` migration has landed**, so `web/data/lab.json` is
   regenerated once, here, from the post-phase-4 database.

**Shared with phase 8, which lands first (wave 1) — reconciled in round 2.** An earlier draft of
the index said phase 8 "does not touch" these; it does. Phase 8 moves only the drawdown number in
each; this phase rewrites the whole gate object **and must quote the post-phase-8 state**, i.e.
`maxDrawdown: 0.2` / `"maxDrawdown":0.2` already in place. Every block in Steps 10, 15, 18b and 19e
below is written that way.

| File | phase 8 writes | this phase writes |
|---|---|---|
| `web/lib/sera/fixture.ts` | `GATE.maxDrawdown` 0.15 -> 0.2 | the whole `GATE` literal, carrying 0.2 forward and adding `dsrMin: 0.9` + the three N keys |
| `web/app/sera/overview.test.ts` | `snap()`'s gate drawdown | `snap()`'s gate wholesale + the `luck` assertions |
| `web/app/sera/how/view.test.ts` | the `loose` override -> `maxDrawdown: 0.3, dsrMin: 0.8` | the same override, **identical values**, plus the three `Luck check` assertions |
| `web/lib/sera/derive.test.ts` | the `reads targets from the gate` override -> `maxDrawdown: 0.3, minProfitFactor: 1.5, minTrades: 50` | `:43`'s target string and the luck-check case; **not** that override |
| `web/app/sera/methods/view.test.ts` | one fixture's `maxDrawdown` 0.18 -> 0.23 | the methods view's gate wording |
| `engine/tests/test_lab_snapshot.py` | the `gate` dict's drawdown assertion | the same dict, wholesale, asserting `gate["maxDrawdown"] == tuning.MAX_DRAWDOWN` from the constant |
| `web/data/lab.json` | regenerated after its constant moves | regenerated again, last (Decision D10) |

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/store.py` — **everything except the `_gate_n` helper, the `gate`
  dict inside `snapshot` and one sentence of `snapshot`'s docstring.** `DSR_MIN`, `DSR_POLICY`,
  `DSR_LABEL`, `TRANSITIONS`, `verdict`, `best_dev_eligible`, `_snapshot_trial`, `_migrate`,
  `SCHEMA_VERSION` and the `lab-wide N` comment at `store.py:314` are **phase 4's** (phase 2's for
  the schema).
- `engine/src/seer_engine/lab/runner.py` — phases 2 and 4.
- `engine/src/seer_engine/commands/lab.py` — phases 3 and 5. In particular `commands/lab.py:206`
  (`f != store.DSR_LABEL`, which filters recorded `failed` strings against a constant that moved)
  is phase 5's to fix; see **Handoffs**.
- `engine/src/seer_engine/lab/npolicy.py` — phase 1.
- `engine/src/seer_engine/paper/roster.py` — phase 6. Its one-line wording for design §3's
  paper-entry sentence is **applied by this phase to the design document** (Step 1, marked
  `<!-- PHASE-6-WORDING -->` for the reconciler) but authored there.
- `lab/lab.sqlite` — phase 4 is its only writer (Decisions D5).
- Phase 5's `lab status` ratchet warning (D1b). §7 refers to it; the CLI wording is phase 5's.

---

## Files

| File | Action | What changes |
|---|---|---|
| `docs/plans/2026-10-04-method-lab-design.md` | modify | §3 bullets 1 and 4 get superseded/amended markers (the sentences themselves are preserved verbatim); a new §7 "Revision 2026-10-07 (owner)" carries the threshold change, the lever deliberately not pulled, the measurement behind both, the deferred ratchet (D1b) and the paper-entry amendment |
| `engine/src/seer_engine/lab/prereg.py` | modify | `gate_text` takes a `conn` and states the threshold *and* the N (`:149-167`); `promote_method` passes it (`:470`, `:490`); `render`'s prose and `_analysis_body` name the bar the trial was judged against (`:203-205`, `:413-422`) |
| `docs/lab/prereg/README.md` | modify | the `gate` and `mar, dsr, n_trials_at_run` rows of the format table |
| `.claude/skills/explore-and-experiment-new-method/SKILL.md` | modify | step 7's "DSR at N" bullet, the Promotion section's `lab promote` bullet, one new Never row |
| `engine/package_readme.md` | modify | the two lines that state the gate's numbers (`:1868-1874`, `:2420`) |
| `engine/src/seer_engine/lab/store.py` | modify | **only** `_gate_n` (new, above `snapshot`), the `gate` dict (`:829-837`) and one docstring sentence (`:808`) |
| `engine/tests/test_lab_snapshot.py` | modify | the `gate` assertion at `:170-171` |
| `engine/tests/test_lab_prereg.py` | modify | `test_the_recorded_gate_names_every_condition_the_lab_applies` at `:390-395` |
| `engine/tests/test_lab_gate_wording.py` | create | two guards: no shipped doc, skill, readme or committed format states a bar other than `store.DSR_MIN`; and the web's luck-label prefix matches `store.DSR_LABEL` |
| `web/lib/sera/types.ts` | modify | `gate` gains three keys; `DsrPolicy`, `DSR_POLICIES`, `DSR_POLICY_LABEL` |
| `web/lib/sera/lab.ts` | modify | `requireGate` build-time validation of the gate block |
| `web/lib/sera/lab.test.ts` | modify | `:12` gate-key loop gains `dsrN`; policy and basis asserted |
| `web/lib/sera/derive.ts` | modify | the luck-check failure label is matched by prefix, so both `DSR >= 0.95` and `DSR >= 0.90` rows read as misses (`:14-21`, `:64-68`) |
| `web/lib/sera/derive.test.ts` | modify | the `0.95 or more` target; a case proving both labels read (`:43`, `:63-67`) |
| `web/lib/sera/fixture.ts` | modify | `GATE.dsrMin` 0.95 → 0.9; the three new keys |
| `web/lib/sera/glossary.ts` | modify | the `dsr` and `tries` plain-English definitions |
| `web/app/sera/overview.ts` | modify | `luck()` gains the N reference line and the policy fields (`:309-333`) |
| `web/app/sera/overview.test.ts` | modify | `snap()`'s gate; the `luck` assertions |
| `web/app/sera/page.tsx` | modify | the Tries stat's sub (`:97`), the luck section's caption and aria label, `refX` passed to the chart (`:231-263`) |
| `web/app/sera/methods/view.ts` | modify | `conditionTip` and `conditionSentence` for `dsr` (`:159`, `:179-180`) |
| `web/app/sera/methods/view.test.ts` | modify | the luck-check sentence at `:146` |
| `web/app/sera/methods/[id]/page.tsx` | modify | the DSR cell carries the N it was scored at (`:329`) |
| `web/app/sera/how/view.ts` | modify | the dev stage's `countTip` (`:86`), `hurdles`' `dsr.plain` (`:200-204`), `honestyRules`' `counted` body (`:215-219`) |
| `web/app/sera/how/view.test.ts` | modify | the three `Luck check ≥ 0.95` assertions (`:61`, `:65`, `:108`, `:111`) |
| `web/data/lab.json` | regenerate | `lab export-json` after phase 4's constant and database change |

---

## Implementation Steps

Order matters only at the ends: **Step 1 is free-standing**, Steps 2–8 must land before Steps 9–11
(the engine tests read the new wording), and **Step 20 is last**, because the regenerated snapshot
must be the export of the post-phase-4 database with the post-phase-4 `DSR_MIN` and the post-Step-8
gate dict.

### Step 1: The design document records the owner's threshold change, and the lever not pulled

**File:** `docs/plans/2026-10-04-method-lab-design.md:56-66` (markers) and `:113` (append §7)
**Change:** §3's sentences are **not rewritten**. Bullet 1 gets a pointer saying its *threshold* is
superseded; its N clause stays, because it is still exactly what the code does. Bullet 4 gets an
amendment pointer for D3. A new §7 — shaped like §6 "Revision 2026-10-04 (owner)" — carries the
owner's decision, the measurement that bounded it, the lever left alone, the deferred ratchet and
the paper-entry amendment.

The tone matters and is load-bearing: **the threshold change is the owner's call on risk appetite,
not a conclusion drawn from the correlation evidence.** A reader in six months must be able to
overturn it by disagreeing about risk appetite, without having to re-argue the statistics.

**Code — replace lines 56-66 (the whole of `## 3. Promotion`) with:**

```markdown
## 3. Promotion

- **Dev-eligible** = the five P7a D8 conditions (beats SPY TR, max DD ≤ 15%, PF ≥ 1.3, ≥ 100
  trades, no owner inputs) **and** DSR ≥ 0.95 with N = all lab trials.
  *(Two thresholds superseded 2026-10-07, both on the owner's instruction: the luck bar is now
  **0.90** — §7.1 — and the drawdown bar is now **20%**, which is design §1 item 4's own
  constant and is recorded there; §7.5 points at it. The N clause stands: N is still every dev
  trial in the lab, and §7.2 says why it was left there on purpose. The *set* of five conditions
  is unchanged.)*
- The best dev-eligible variant by MAR (one per method) is pre-registered in
  `docs/lab/prereg/MNNNN.md`, committed and pushed before any test number exists.
- `python -m seer_engine lab test <candidate>` runs it **once** on the test window; the database
  refuses a second look. The test-window store is built the first time something is promoted,
  never before. Every summary shows "test-window looks used: k".
- Fail → `test-failed`, final. Pass → `test-passed`, and the skill stops for the owner: a paper
  roster entry (new id, own clock) is the owner's call; real money still needs all of design §1.
  *(Amended 2026-10-07 — see §7.4. Paper membership never required a test pass; what changed is
  that the basis is now recorded on every roster entry.)*
```

**Code — append at the END OF THE FILE, after §6's last line.** (Do not use a line number: the
§3 replacement above swaps an 11-line region for a 19-line one, so every number past it has moved
by 8. Anchor on §6's closing text.)

```markdown

## 7. Revision 2026-10-07 (owner): the luck bar at 0.90, and the N left alone

§3's sentences above stand as written and are not edited. This section says what superseded them,
who decided it and on what, so a reader can overturn it knowing exactly what it rested on.

### 7.1 The threshold: `DSR_MIN` 0.95 → 0.90 (owner)

**Superseded, §3 bullet 1, the threshold only.** The original wording, 2026-10-04:

> **Dev-eligible** = the five P7a D8 conditions (beats SPY TR, max DD ≤ 15%, PF ≥ 1.3, ≥ 100
> trades, no owner inputs) **and** DSR ≥ 0.95 with N = all lab trials.

**It now reads:** dev-eligible = the same five P7a D8 conditions **and** **DSR ≥ 0.90**, with
N = all lab trials, unchanged.

**This is an owner decision on risk appetite, not a conclusion from the data.** The owner's words,
2026-10-07: *"this 0.95 threshold is too high man. my risk appetite is 0.90."* `DSR_MIN` is what
the owner is willing to be wrong about; nothing in the measurements below argues for 0.90 over
0.95, and nothing in them could. They bound the decision; they do not make it.

**What it admits, measured before the change was made — this lever alone, with the drawdown bar
still at 15%.** At DSR ≥ 0.90 with N = 110, **exactly two candidates become dev-eligible** — `M0022-W-TV14` (DSR 0.912, MAR 0.86) and `M0022-W-TV16`
(DSR 0.916, MAR 0.82), the two highest-MAR books in the lab, and **both already pass all five owner
conditions**. The best by MAR, which is the one `lab promote` would pre-register, is W-TV14.
Nothing else moves: `M0011-RAW20-TV14-N21` at 0.884 stays out, and `M0020-W-NOSTOP` and
`M0007-N20-RAW` still fail max drawdown, which no threshold can rescue. One lever, chosen by the
owner, admitted the right two. (With the owner's *second* change of the same day — the 20%
drawdown bar, §7.5 — the set becomes **three**: `M0020-W-NOSTOP` joins it. The two numbers are
not in conflict; they measure one lever and two.)

**What is unchanged.** The five P7a D8 conditions, `backtest.dev.deflated_sharpe` (byte for byte),
`DEV_END`, the D9 guard, the P7a registry, and every recorded `dsr`, `eligible`, `failed` and
`n_trials_at_run` on all 110 dev trials. `trials` is append-only and nothing in this revision
rewrites a verdict; the gate is read at evaluation time, so the new threshold applies to the next
evaluation and the record of what each trial scored stays exactly as it was.

### 7.2 The N: measured, selectable, and deliberately left at `all-trials`

The second lever was built and **not pulled.** `lab/npolicy.py` now implements three named
multiple-testing policies, and `lab.store.DSR_POLICY` chooses between them. It ships as
**`all-trials`** — N = every dev trial in the lab, which is exactly what §3 has said since
2026-10-04 and is still what the gate does.

The alternatives are measured rather than guessed, from the month-end equity curves already stored
in `trials.curve_json` — 110 dev curves over the 102 month-ends common to all of them. No backtest
was re-run and no test-window look was spent:

| policy | what it counts | N on 2026-10-07 |
|---|---|---|
| **`all-trials`** (in force) | every dev trial row | **110** |
| `methods` | distinct methods with a dev trial, floored at ⌈participation ratio⌉ | 23 |
| `effective` | the measured participation ratio | ≈2 |

| measure | value |
|---|---|
| mean pairwise correlation ρ̄ across the 110 dev curves | 0.595 (median 0.640) |
| effective N, participation ratio | 2.44 |
| effective N, 1 + (N−1)·ρ̄ | 1.7 |
| distinct methods with a dev trial | 23 (11 P7a families + 12 lab methods) |
| trial rows | 110 |

`deflated_sharpe` assumes N **independent** trial Sharpes, and 110 rows at ρ̄ = 0.595 are not
independent, so N = 110 does overstate the hurdle. That is a real finding and it is why the policy
module exists.

**Why the owner moved the thresholds and not the N.** At (N = 110, DSR ≥ 0.90, max DD ≤ 20%)
**three** candidates become eligible, all three already passing every owner condition. At
(N = 23, 0.90, 20%) **all seven** luck-only candidates do, including `M0011-RAW20-TV12` at
MAR 0.60 — four more than the owner asked for, admitted by a change the owner did not make.
Pulling the N lever as well would also make it impossible to tell afterwards which change did the
work. The threshold was the owner's stated preference; the N stays where the
design document has always said it is, now with the evidence against it written down and the
alternative one constant away.

**Overturning this is one constant.** All three policies are implemented and tested, and
`python -m seer_engine lab luck` prints the leaderboard under each side by side, so the gate's
sensitivity to N is inspectable without editing anything. Setting `lab.store.DSR_POLICY` to
`"methods"` pulls the second lever on the next evaluation, with no data change: every recorded
column is preserved byte-for-byte and the verdict is derived at read time.

### 7.3 The ratchet is deferred, not removed

R1's complaint — the bar rises with every exploration regardless of merit — is **not fixed** by
0.90. **The threshold change resets the clock; it does not stop it**, and the clock is short.

`M0022-W-TV16` scores 0.916 at N = 110 and clears. It falls below 0.90 at **N = 143** (DSR 0.8997)
— **33 more dev trials**, roughly one and a half Sera nights at about 25 trials a night. The curve
keeps going the same way: ≈0.877 by N = 200. So the runway bought here is measured in days, not
weeks, and the mechanism that produced the first deadlock is untouched and still running.

That is the whole reason the warning below exists. The runway is made visible
rather than left to be rediscovered 110 trials late: `lab status` warns when the best luck-only
candidate is within 0.03 of the bar and names the N that would sink it. When that warning fires —
and on current evidence it fires almost immediately — the choice on the table is the one this
revision deliberately left open: pull the N lever (§7.2), move the threshold again, or accept the
deadlock and say so out loud. What must not happen again is the search grinding for a hundred
trials against a bar nothing can clear, with nothing on the screen saying so.


### 7.4 Paper membership and the lab verdict

<!-- PHASE-6-WORDING: phase 6 (paper/roster.py) hands the reconciler the exact sentence for the
     paragraph below. The text here states Decisions D3 and is correct as written; replace it only
     if phase 6's wording differs. -->

**Amended, §3 bullet 4, and §6's "on a test pass, a paper-roster entry with its own clock".**
Paper membership **does not require a test pass** and never did: `paper/roster.py` admits on the
owner's judgement, and the design §1 gates bind the *real-money* decision, not paper membership.
That position and §3's wording were both live at once, which is why RM-FR (lab M0011) and RMW-FR
(lab M0022) traded on paper while both methods read `rejected` in `lab/lab.sqlite`, with no record
of why but a commit message.

**What changed on 2026-10-07 is the silence, not the policy.** Every roster entry whose id names a
lab candidate now carries a recorded `lab_provenance` — the lab method and candidate id, the lab
status at admission, and the admission basis (`test-passed`, or `owner-override` with its reason) —
held outside the spec digest, like `gate_note`, and checked against `lab/lab.sqlite` by a test. The
divergence is now a stated fact with a reason. No started roster id changes its `spec_digest`;
nothing is retired or re-admitted.

### 7.5 The drawdown bar: 15% → 20% (owner), recorded in §1

The owner's second risk-appetite change of 2026-10-07: `backtest.tuning.MAX_DRAWDOWN` 0.15 → 0.20.
Because that constant **is** design §1's go-live condition #4, the change is recorded there rather
than restated here, and §1 item 4 carries its own dated revision note. This section exists so a
reader of §3 and §7.1 is not left thinking the luck bar was the only thing that moved.

Scope, as the owner chose it when the fork was put to them explicitly: **both** the lab's
dev-window screen and design §1's real-money go-live bar. One number, read by both, in one place.

What it admits in the lab, measured: `M0020-W-NOSTOP` (max DD 19.3%, DSR 0.913 re-evaluated at
N = 110) becomes dev-eligible, taking the lab from two eligible candidates to three.
`M0019-RAW20-S25` is still out at 20.7%, outside even the new bar. `M0007-N20-RAW` clears the new
bar at 19.6% and is still out on the luck test — its DSR re-evaluated at today's N = 110 is 0.898
against a 0.90 bar, where its *recorded* 0.914 was computed at N = 85. Two P7a seed trials come
inside the bar and stay ineligible, **for two different reasons**: `F9-SPY200M70-MOM30` (19.2%)
passes every owner condition and is held out by the luck test alone — its `dsr` is NULL, and a
luck test that cannot be evaluated is one that was not passed, until §7.6's re-run measures it at
0.857; `F3-SEC-TOP3-6M-TREND` (19.5%) also records `owner inputs` — the nine sector ETFs — which
is not a threshold, which no constant re-decides, and which keeps it out whatever its luck test
later says.

### 7.6 Luck-testing the P7a seed

Fifty-four of the lab's 110 dev trials — the P7a seed import — record `dsr IS NULL`
(`lab/seed.py:136`: "P7a reported it for one row only"). They are already inside the
multiple-testing count, so they pay the full penalty every other candidate pays and receive no
verdict in return; and under the rule in §7.1 a trial whose luck test cannot be evaluated fails
it, which makes them permanently ineligible by data gap rather than by merit.

The owner's call, 2026-10-07: re-run them. `lab remeasure` gains a seed path and a resumable
batch mode that recovers each trial's daily moments and writes `trial_moments` rows — and
**nothing else**. No `trials` row is inserted, so the lab's N and its trial-Sharpe variance are
identical before and after, which is the point: luck-testing what the lab has already counted
raises the bar for nobody. The 54 candidates are all still in the frozen P7a registry, so they
are runnable without touching that record.

`F9-SPY200M70-MOM30` is the case that made it urgent: at the new 20% drawdown bar it passes every
owner condition, and from the recorded columns alone its DSR is underdetermined across roughly
0.74–0.98 — straddling the 0.90 bar. No amount of arithmetic on what is written down can settle
it; only the re-run can.
```

**Impact:** the design document gains a §7 and three pointers. Nothing reads this file
programmatically; the guard test added in Step 9 **exempts it by name**, because the superseded
threshold is quoted here on purpose.

---

### Step 2: `prereg.gate_text` states the bar it was judged against, and the N in force

**File:** `engine/src/seer_engine/lab/prereg.py:149-167`
**Change:** the N clause — `"N = every dev trial in the lab"` — is **accurate and stays**, but it
is rebuilt from `store.DSR_POLICY` rather than typed, so it cannot silently become false the day
the policy default moves. What is added is the **threshold**, interpolated from `store.DSR_MIN`:
0.90 and 0.95 produce different verdicts, so a committed file that does not say which bar it
cleared is not a record of anything.

The threshold is read from `store.DSR_MIN` directly rather than relied on inside `store.DSR_LABEL`,
because `DSR_LABEL` is also the literal written into the append-only `trials.failed` column and
phase 4 may hold it steady for matching. Stating the number from the constant that decides it is
correct either way.

**Code — replace the whole of `gate_text`:**

```python
def gate_text(conn: sqlite3.Connection | None = None) -> str:
    """The **dev** gate this variant passed, in the lab's own words.

    Built from ``dev.FAILURE_LABELS``, ``store.DSR_MIN`` and ``store.DSR_POLICY`` rather than
    retyped, so a file written next year cannot claim a condition the code stopped applying, a
    bar the owner has moved, or an N the gate stopped deflating by.

    Two numbers, both of which decide the verdict and neither of which can be recovered from the
    other. The **threshold** moved on 2026-10-07 (design §7.1: the owner set ``DSR_MIN`` to 0.90),
    and a pre-registration written at 0.90 records a different claim from one written at 0.95, so
    the file has to say which. The **N** is whatever the policy named in ``store.DSR_POLICY``
    resolves to -- ``all-trials``, every dev trial in the lab, as design §3 has always said and
    §7.2 deliberately left it -- and the number it came to that day is the multiple-testing count
    the deflation actually used.

    ``conn`` resolves that N and the one-line evidence behind it. ``promote_method`` always passes
    one, so **every committed pre-registration carries both numbers for the day it was written**,
    which is the whole point of a pre-registration: the rule is pinned before the look. The
    ``conn=None`` form names the threshold and the policy and stops short of the count; it exists
    for refusal messages and for tests that build a ``Prereg`` with no database behind them.

    This is what the variant passed to become ``dev-eligible``; it is **not** the gate the one
    test-window look is judged by. That one is the five P7a D8 conditions alone -- DSR is
    recorded on the test trial and is not a condition, because a pre-registered look has no
    selection among results to deflate (``runner.test_trial_row``). ``render`` says so in the
    file's prose, so a reader of the pre-registration cannot mistake one for the other.

    The returned string is always a single line: it is a ``key: value`` field in a committed file
    whose parser splits on newlines (``parse``), so ``npolicy``'s evidence line must not wrap.
    """
    from seer_engine.backtest import dev
    from seer_engine.lab import npolicy

    conditions = "; ".join(dev.FAILURE_LABELS[:-1])
    head = (
        f"dev-eligible = the five P7a D8 conditions ({conditions}; no {dev.FAILURE_LABELS[-1]}) "
        f"and DSR >= {store.DSR_MIN:.2f}, deflated by the multiple-testing N that the "
        f"'{store.DSR_POLICY}' policy resolves to"
    )
    if conn is None:
        return head
    n = npolicy.effective_n(conn, store.DSR_POLICY)
    return f"{head}: N = {n.n} when this file was written ({n.basis})"
```

**Impact:** the `gate` field of every future pre-registration carries both numbers.
`docs/lab/prereg/` holds **only `README.md`** today — verified by `ls docs/lab/prereg/`, and by the
database, which reports `promoted = 0` — so **no already-committed pre-registration exists to fail
`parse` or `check_digest`**, and none can be invalidated by this change. `gate` is a free-text
field that nothing compares across files; `parse(render(p, name)) == p` still holds because the
value is one line and `parse` splits on the first `:` of each line, which is the key separator.

---

### Step 3: `promote_method` passes the connection

**File:** `engine/src/seer_engine/lab/prereg.py:466-471` and `:490`
**Change:** both call sites inside `promote_method` hand `gate_text` the open connection, so the
refusal message and the written file both carry the N. Both are already inside
`store.begin_immediate(conn)`; `effective_n` only reads, so it is safe under the write lock.

**Code — replace `:466-471`:**

```python
        status = str(row["status"])
        if status not in ("dev-eligible", "promoted"):
            raise PreregError(
                f"{method_id} is {status!r}, and only a dev-eligible method is pre-registered. "
                f"The gate is: {gate_text(conn)}"
            )
```

**Code — replace the one line inside the `Prereg(...)` construction (`:490`):**

```python
            gate=gate_text(conn),
```

**Impact:** none on control flow.

---

### Step 4: `render`'s prose names the bar the trial was judged against

**File:** `engine/src/seer_engine/lab/prereg.py:203-205`
**Change:** the file reads `DSR {p.dsr} at N = {p.n_trials_at_run}` and never says what bar that
DSR had to clear. With the threshold now a thing that moves, the recorded number alone is not a
record of a pass.

**Code — replace lines 203-205 of `render`'s f-string:**

```
**Gate passed, on the dev window {p.dev_window}:** {p.gate}.
MAR {p.mar}, DSR {p.dsr}, recorded at `n_trials_at_run` = {p.n_trials_at_run} on dev trial
#{p.dev_trial}. The bar that DSR cleared and the N it was deflated by are both stated in the gate
line above, because both are settings the owner can move (design §7) and a number without them is
not a record of a pass.
Research store `{p.store_fingerprint}`, engine `{p.git_sha}`.
```

**Impact:** prose only. `FIELDS`, `parse` and the front-matter block are untouched, so
`parse(render(p, name)) == p` is unaffected — `render`'s prose is never read back.

---

### Step 5: the analysis note the promotion appends says the same thing

**File:** `engine/src/seer_engine/lab/prereg.py:413-422`
**Change:** `_analysis_body` writes into `methods.analysis`, which the site renders, and carries
the same bare `at N = …` claim.

**Code — replace `_analysis_body` entirely:**

```python
def _analysis_body(p: Prereg, path: Path) -> str:
    return (
        f"{MARKER}`{p.candidate}` (dev trial #{p.dev_trial}, config digest "
        f"`{p.config_digest}`, MAR {p.mar}, DSR {p.dsr} at N = {p.n_trials_at_run}; the bar it "
        f"cleared is the one named in the pre-registration's gate line).\n\n"
        f"Pre-registration: `{repo_path(path)}`, written before any test number exists and "
        f"committed before the look is spent (design §3). The test window is {p.test_window}; "
        f"`lab test {p.candidate}` spends the one look this configuration gets, and the database "
        f"refuses a second (`UNIQUE(config_digest, window)`). No `trials` row was written here: "
        f"a pre-registration is not a backtest and does not move the lab's N."
    )
```

**Impact:** `MARKER` and `_RECORDED` are unchanged, so `promote_method`'s idempotence key still
matches — `_RECORDED` captures only the backticked candidate id, and that part of the sentence is
byte-identical. No method is currently `promoted`, so no committed analysis holds the old text.

---

### Step 6: the pre-registration README describes the fields as they now are

**File:** `docs/lab/prereg/README.md`, the Format table rows for `gate` and
`mar`, `dsr`, `n_trials_at_run`

**Code — replace those two rows:**

```markdown
| `gate` | the conditions the variant passed on the dev window, **including the DSR threshold in force and the multiple-testing policy with the N it resolved to** on the day the file was written (design §7). Both are settings the owner can move, so both are pinned here |
| `mar`, `dsr`, `n_trials_at_run` | the dev numbers it passed with. `n_trials_at_run` is the trial-row count recorded with that trial; under the `all-trials` policy it is also the N the DSR deflated by, but the N the gate used is the one stated in `gate`, which stays correct if the policy changes |
```

**Impact:** documentation only.

---

### Step 7: the skill stops teaching the old bar

**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:89`, `:127-131`, `:176`

**Code — replace line 89 (step 7's analysis bullet):**

```markdown
   - DSR at N, in words: how likely the result is real rather than luck after N tries. Say the N
     and the bar it was judged against — the bar is `DSR >= 0.90`, the owner's risk appetite since
     2026-10-07 (design §7.1), and N is every dev trial in the lab (§7.2). Both are printed by
     `lab status`; neither is yours to change.
```

**Code — replace the `lab promote` bullet at `:127-131`:**

```markdown
- **`lab promote <method>`:** picks the method's best eligible **dev** trial by MAR (one variant
  per method), writes `docs/lab/prereg/MNNNN.md` with the `config_digest` **copied from that
  recorded trial**, and moves the method `dev-eligible → promoted`. The file records the gate it
  passed — the five conditions, the DSR threshold in force and the N the multiple-testing policy
  resolved to that day — so the rule is pinned in git before any test number exists. It is written
  once and never rewritten: a re-run with a better-looking variant available is a refusal, not an
  update. It loads no store, runs no backtest and spends no look.
```

**Code — insert one row into the Never table, after line 176
("Max DD 16% is basically 15%"):**

```markdown
| "The luck bar is still too high; nudge it" | Never. `DSR_MIN` is the owner's risk appetite and `DSR_POLICY` is the owner's call on what counts as an independent look (design §7). Run `lab luck` to see the sensitivity, journal what you found, and leave both alone. |
```

**Impact:** the skill's analysis step, promotion step and guardrails match the code. Nothing in the
skill is executed, so no test changes.

---

### Step 8: the engine readme, and the snapshot's gate block

**File (a):** `engine/package_readme.md:1868-1874` and `:2420`

**Code — replace lines 1868-1874 (the `gate_text()` bullet):**

```markdown
- `gate_text(conn=None)` is **built** from `backtest.dev.FAILURE_LABELS`, `store.DSR_MIN` and
  `store.DSR_POLICY` rather than retyped, so a pre-registration cannot claim a condition the code
  stopped applying, a bar the owner has moved, or an N the gate stopped deflating by. What it
  states is the **dev** gate the variant passed to become `dev-eligible`: the five P7a D8
  conditions plus `DSR >= DSR_MIN` (0.90 since 2026-10-07, the owner's risk appetite — design
  §7.1), deflated by the N the policy in `store.DSR_POLICY` resolves to (`all-trials` = every dev
  trial in the lab, left there deliberately — §7.2). `promote_method` always passes the
  connection, so every committed file carries the threshold, the policy name *and* the count it
  resolved to that day; the `conn=None` form stops short of the count and exists for refusal
  messages and for tests that build a `Prereg` with no database. It is *not* the gate the one
  test-window look is judged by: that is the five D8 conditions alone, because a pre-registered
  look has no selection among results to deflate, so DSR is recorded on the test trial and is not
  a condition. `render` says so in the file's prose, so a reader of the pre-registration cannot
  mistake one for the other.
```

**Code — replace line 2420:**

```markdown
- **The gate named in a pre-registration is the dev gate, not the test gate.** `prereg.gate_text` states what the variant passed to become `dev-eligible` (the five P7a D8 conditions plus `DSR >= store.DSR_MIN`, deflated by the N that `store.DSR_POLICY` resolves to — both pinned into the file, because both are settings the owner can move; design §7). The one test-window look is judged by the five D8 conditions alone; DSR is recorded on the test trial and is not a condition, because a pre-registered look has no selection among results to deflate and a look is not a search.
```

**File (b):** `engine/src/seer_engine/lab/store.py` — the snapshot gate dict only
**Change:** `_gate_n` is added immediately above `snapshot` (after `_snapshot_trial`, which ends at
`:799`), and the `gate` dict spreads it in. **This is phase 7's only edit to `store.py`.**
`dsrMin` needs no edit: it reads `DSR_MIN`, which phase 4 moved to 0.90.

**Code — insert between `_snapshot_trial` and `snapshot`:**

```python
def _gate_n(conn: sqlite3.Connection) -> dict[str, Any]:
    """The multiple-testing N the luck gate deflates by, and the evidence behind it.

    Three keys rather than one number, because the number alone is not reviewable. A reader of
    ``web/data/lab.json`` -- or of seertrade.site/sera, which draws this beside the luck bar --
    has to be able to see *which* policy produced the N and *what measurement* that policy rests
    on. That matters more here than it would if the policy had changed: it did not. ``DSR_POLICY``
    ships as ``all-trials`` on purpose (design §7.2), and publishing the name, the count and the
    evidence is what keeps the lever that was deliberately not pulled visible on the site rather
    than buried in a plan file.

    Resolved at snapshot time from ``DSR_POLICY`` and never stored, so flipping that one constant
    moves the published gate on the next export with no data change -- the same property the
    derived verdict has. Reads only ``trials``, which schema v1 and v2 share, so ``snapshot``'s
    promise to work on a read-only, unmigrated connection still holds.
    """
    from seer_engine.lab import npolicy

    n = npolicy.effective_n(conn, DSR_POLICY)
    return {"dsrPolicy": n.policy, "dsrN": n.n, "dsrNBasis": n.basis}
```

**Code — replace the `gate` entry of `snapshot`'s returned dict (`:829-837`):**

```python
        "gate": {
            "maxDrawdown": tuning.MAX_DRAWDOWN,
            "minProfitFactor": tuning.MIN_PROFIT_FACTOR,
            "minTrades": dev._MIN_TRADES,
            "dsrMin": DSR_MIN,
            **_gate_n(conn),
            "devStart": research.STORE_START.isoformat(),
            "devEnd": dev.DEV_END.isoformat(),
            "testStart": dates.next_session(dev.DEV_END).isoformat(),
        },
```

**Code — replace the last sentence of `snapshot`'s docstring (`:808`):**

```python
    schema v1 and v2 share and never touches ``meta``, so it works on a read-only connection to
    a database that has not been migrated. Gate and data facts come from the engine's constants;
    the gate's ``dsrPolicy`` / ``dsrN`` / ``dsrNBasis`` are resolved from ``DSR_POLICY`` against
    ``trials`` at export time rather than stored, so the published gate follows the constant
    (design §7).
```

**Impact:** `web/data/lab.json`'s `gate` block gains three keys in a fixed position and `dsrMin`
changes value. `SNAPSHOT_VERSION` stays **1**: the key change is purely additive, every existing
key keeps its name and meaning, and the only reader is `web/`, which ships from the same commit as
the JSON — there is no out-of-band consumer a version bump would protect. What *does* protect it is
Step 12's build-time guard. `test_the_committed_snapshot_is_the_export_of_the_committed_database`
now requires Step 20.

---

### Step 9: the guard — no shipped document states a bar the lab does not apply

**File:** `engine/tests/test_lab_gate_wording.py` (new)
**Change:** a cheap test that fails the moment a document claims a luck bar other than the one in
`store.DSR_MIN`. It is written against the **live constant**, not against the literal `0.95`, so it
catches the *next* threshold move as well as this one — which is the whole lesson of this phase:
the last move left six places saying 0.95 and nothing noticed.

**It does not forbid "every dev trial"** — that phrase is now correct (`DSR_POLICY = "all-trials"`),
and forbidding it would be the previous draft's mistake. It also never flags code that interpolates
the constant (`DSR >= {store.DSR_MIN:.2f}`, `Luck check ≥ ${num(gate.dsrMin)}`): those have no digit
after the operator, which is exactly the shape the guard wants to encourage.

The design document is **exempted by name**, because §3 preserves the superseded sentence and §7.1
quotes it. A second test pins the web's luck-label prefix to the engine's constant (**Requires** 3).

**Code — the whole file:**

```python
"""Phase 7 (lab-luck-gate): no shipped document states a luck bar the lab does not apply.

The owner moved ``DSR_MIN`` from 0.95 to 0.90 on 2026-10-07 (design §7.1), and six shipped files
went on claiming 0.95 -- the skill the unattended explorer reads, the format every pre-registration
is written in, two readmes and two pages of the site. The threshold lives in exactly one place in
the code and must read the same way everywhere it is written down.

This test is therefore written against ``store.DSR_MIN`` rather than against the literal ``0.95``:
the bar is a dial the owner turns, and a guard that only knows the last value is a guard that has
to be rewritten every time it would have been useful.

A stale bar in a skill, a readme or the committed pre-registration format is worse than no bar at
all: ``SKILL.md`` is what the next unattended exploration session reads and acts on, and
``prereg.gate_text``'s words are copied verbatim into every ``docs/lab/prereg/MNNNN.md`` the lab
will ever write -- files that are committed before a test number exists and are never rewritten.

Two things this test deliberately does **not** do:

- It does not forbid "every dev trial" or "N = all lab trials". ``DSR_POLICY`` ships as
  ``all-trials`` (design §7.2), so those phrases are *correct*; the N lever was measured and
  deliberately left alone, and a test that scrubbed the wording would make the design document lie.
- It does not scan ``docs/plans/2026-10-04-method-lab-design.md``. That document records decisions
  by appending dated revisions, so §3 keeps its original sentence and §7 quotes it as the thing it
  supersedes. Deleting it there would destroy the record this test exists to protect.

It also does not scan files the recorded ``trials.failed`` strings live in: ``trials`` is
append-only, so the 110 rows judged under 0.95 carry that exact text forever and any test fixture
asserting on them is quoting data, not stating the rule.
"""

from __future__ import annotations

import re

import pytest

from seer_engine import config
from seer_engine.lab import prereg, store

#: A statement of the luck bar with a number in it: "DSR >= 0.95", "DSR ≥ 0.9",
#: "Luck check ≥ 0.95", "luck check of at least 0.90". The number is captured and compared against
#: the live constant, so this guard catches the *next* threshold move too and not only this one --
#: which is the point, because the last one went unrecorded in six places at once.
#:
#: Code that interpolates the constant (``DSR >= {store.DSR_MIN:.2f}``,
#: ``Luck check ≥ ${num(gate.dsrMin)}``) has no digit after the operator and never matches: reading
#: the threshold from the gate is always the right answer, and this regex is shaped to leave it
#: alone.
BAR_WITH_NUMBER = re.compile(
    r"(?:DSR|luck\s+check)\s*(?:>=|≥|of\s+at\s+least)\s*(\d+\.\d+)",
    re.I,
)

#: Files this phase is responsible for. Paths are relative to the repository root.
SCANNED: tuple[str, ...] = (
    ".claude/skills/explore-and-experiment-new-method/SKILL.md",
    "docs/lab/prereg/README.md",
    "engine/package_readme.md",
    "engine/src/seer_engine/lab/prereg.py",
    "web/lib/sera/glossary.ts",
    "web/lib/sera/derive.ts",
    "web/app/sera/overview.ts",
    "web/app/sera/page.tsx",
    "web/app/sera/how/view.ts",
    "web/app/sera/methods/view.ts",
)


@pytest.mark.parametrize("rel", SCANNED)
def test_no_shipped_document_states_a_luck_bar_the_lab_does_not_apply(rel: str) -> None:
    path = config.REPO_ROOT / rel
    assert path.is_file(), f"{rel} is gone; update SCANNED or restore the file"
    hits = []
    for i, line in enumerate(path.read_text(encoding="utf-8").split("\n"), start=1):
        for written in BAR_WITH_NUMBER.findall(line):
            if float(written) != store.DSR_MIN:
                hits.append(f"  line {i}: says {written}, the gate applies {store.DSR_MIN}: {line.strip()}")
    assert not hits, (
        f"{rel} states a luck bar the lab does not apply. The threshold is the owner's dial "
        f"(design §7.1, moved from 0.95 to {store.DSR_MIN} on 2026-10-07), so a document that "
        f"types the number goes stale the next time it moves -- prefer reading it from "
        f"`store.DSR_MIN` or from `gate.dsrMin`:\n" + "\n".join(hits)
    )


def test_the_gate_text_is_built_from_the_constants_that_decide_the_verdict() -> None:
    """The words written into every pre-registration are built, not retyped (``gate_text``).

    Both numbers: the bar the owner set, and the policy that chooses N. Neither can be recovered
    from the other, so a pre-registration that names only one is not a record of a pass.
    """
    text = prereg.gate_text()
    assert f"{store.DSR_MIN:.2f}" in text
    assert store.DSR_POLICY in text
    assert all(float(w) == store.DSR_MIN for w in BAR_WITH_NUMBER.findall(text))


#: The two literals in ``web/`` that have to agree with the engine's threshold-bearing labels.
_WEB_PREFIX = re.compile(r"DSR_FAILURE_PREFIX\s*=\s*'([^']*)'")
_WEB_DD_PREFIX = re.compile(r"DRAWDOWN_FAILURE_PREFIX\s*=\s*'([^']*)'")


def test_the_web_mirrors_the_engines_drawdown_label_prefix() -> None:
    """The drawdown twin of the luck-label pin, and new since the owner moved that bar too.

    ``tuning.MAX_DRAWDOWN`` is 0.20 since 2026-10-07 (design §1 item 4, phase 8), so the engine
    writes ``max DD <= 20%`` while 30 committed rows say ``max DD <= 15%``. Both are misses. The
    site matches the shape; this test is what keeps the shape equal to the engine's.
    """
    from seer_engine.backtest import dev

    src = (config.REPO_ROOT / "web" / "lib" / "sera" / "derive.ts").read_text(encoding="utf-8")
    m = _WEB_DD_PREFIX.search(src)
    assert m is not None, (
        "web/lib/sera/derive.ts no longer defines DRAWDOWN_FAILURE_PREFIX as a single-quoted "
        "literal; if the web stopped matching the drawdown label by prefix, say so here"
    )
    prefix = m.group(1)
    assert prefix, "an empty prefix would mark every failure as a drawdown miss"
    assert dev.FAILURE_LABELS[1].startswith(prefix), (
        f"the engine writes {dev.FAILURE_LABELS[1]!r} into trials.failed, but the site looks for "
        f"{prefix!r}. Every missed drawdown would render as a pass on seertrade.site/sera"
    )
    assert "max DD <= 15%".startswith(prefix), (
        "the 30 committed rows judged under the old 15% bar must still read as drawdown misses"
    )


def test_the_web_mirrors_the_engines_luck_label_prefix() -> None:
    """``web/lib/sera/derive.ts`` matches the luck label by prefix; this pins that prefix here.

    ``trials`` is append-only, so a row judged before 2026-10-07 carries ``DSR >= 0.95`` for ever
    and one judged after carries ``DSR >= 0.90``. Both are misses. Phase 4 exports a prefix matcher
    from ``store`` for the Python readers; the web cannot call it -- ``derive.ts`` is TypeScript in
    the Next build, with no path to a Python symbol -- so it mirrors the prefix as one constant,
    and this test is the mirror's pin.

    The property, not the helper's name, is what is checked: whatever phase 4 calls its matcher,
    ``DSR_LABEL`` has to start with what the web looks for, or the site renders a failed luck check
    as a green tick -- silently, and on the one page the owner actually reads.
    """
    src = (config.REPO_ROOT / "web" / "lib" / "sera" / "derive.ts").read_text(encoding="utf-8")
    m = _WEB_PREFIX.search(src)
    assert m is not None, (
        "web/lib/sera/derive.ts no longer defines DSR_FAILURE_PREFIX as a single-quoted literal; "
        "if the web stopped matching the luck label by prefix, say so here and delete this test"
    )
    prefix = m.group(1)
    assert prefix, "DSR_FAILURE_PREFIX is empty: that would mark every failure as a luck miss"
    assert store.DSR_LABEL.startswith(prefix), (
        f"the engine writes {store.DSR_LABEL!r} into trials.failed, but the site looks for "
        f"{prefix!r}. Every luck-check miss would render as a pass on seertrade.site/sera"
    )
```

**Impact:** one new test file, 2 + 10 parametrized cases. It does **not** scan `lab/runner.py`,
`lab/store.py` or `commands/lab.py`: those are phases 2, 4 and 5's files and those phases own their
wording (see **Handoffs**).

---

### Step 10: the snapshot test asserts the new gate block

**File:** `engine/tests/test_lab_snapshot.py:170-171`
**Change:** three new keys, and `dsrMin` read from the constant rather than pinned to a literal —
the threshold is the owner's dial, and a test that hardcodes it turns the next adjustment into a
test failure for no benefit. The N is asserted structurally, because its value is phase 1's
arithmetic over the fixture's trials and pinning it here would give that arithmetic a second home.

`tuning` must be imported in that module for the new assertion
(`from seer_engine.backtest import tuning`); `store` already is.

**Code — replace lines 170-171:**

```python
    gate = s["gate"]
    assert list(gate) == [
        "maxDrawdown", "minProfitFactor", "minTrades", "dsrMin",
        "dsrPolicy", "dsrN", "dsrNBasis", "devStart", "devEnd", "testStart",
    ]
    assert {k: gate[k] for k in ("minProfitFactor", "minTrades",
                                 "devStart", "devEnd", "testStart")} == {
        "minProfitFactor": 1.3, "minTrades": 100,
        "devStart": "1993-01-29", "devEnd": "2015-10-16", "testStart": "2015-10-19"}
    # BOTH bars are the owner's dials and BOTH moved on 2026-10-07 (design §7.1 and §1 item 4):
    # published from the constants, never pinned here. A test that hardcodes an owner-set number
    # turns the next adjustment into a test failure for no benefit -- which is what happened to
    # the six files this phase is fixing.
    assert gate["dsrMin"] == store.DSR_MIN
    assert gate["maxDrawdown"] == tuning.MAX_DRAWDOWN
    # The N is resolved from the policy at export time, not stored: assert the contract the web
    # reads (a known policy, a usable integer, one line of evidence), not phase 1's arithmetic.
    assert gate["dsrPolicy"] == store.DSR_POLICY
    assert isinstance(gate["dsrN"], int) and gate["dsrN"] >= 0
    assert isinstance(gate["dsrNBasis"], str) and gate["dsrNBasis"]
    assert "\n" not in gate["dsrNBasis"]  # it is a one-line field in a committed prereg file too
```

**Impact:** `store` is already imported in that module.

---

### Step 11: the prereg test asserts both numbers and both forms

**File:** `engine/tests/test_lab_prereg.py:390-395`
**Change:** extend the existing test rather than add one — it is the test that exists to stop the
gate line drifting from the code, and it now has two numbers to guard instead of one.

**Code — replace the whole test:**

```python
def test_the_recorded_gate_names_every_condition_the_lab_applies(tmp_path):
    """The gate line is built from the engine's own labels, so it cannot drift from the code.

    Two forms. Without a connection it names the five conditions, the threshold and the policy.
    With one it also carries the N that policy resolved to and the evidence for it, which is what
    ``promote_method`` writes into the committed file.
    """
    text = prereg.gate_text()
    for label in dev.FAILURE_LABELS:
        assert label in text
    assert f"{store.DSR_MIN:.2f}" in text  # the bar the owner set (design §7.1)
    assert store.DSR_POLICY in text  # the policy that chooses N (design §7.2)

    conn = store.connect(tmp_path / "lab.sqlite")
    try:
        resolved = prereg.gate_text(conn)
    finally:
        conn.close()
    assert resolved.startswith(text)  # the conn form only appends
    assert "N = " in resolved
    assert "\n" not in resolved  # one `key: value` line in the committed file
```

**Impact:** `store.connect` and `tmp_path` are both already used across that module.

---

### Step 12: the web gate type, and the build-time guard

**File (a):** `web/lib/sera/types.ts`

**Code — replace the `gate` block inside `LabSnapshot` (`:6-14`):**

```ts
  gate: {
    maxDrawdown: number;
    minProfitFactor: number;
    minTrades: number;
    /** The luck bar (`lab.store.DSR_MIN`): 0.90 since 2026-10-07, the owner's risk appetite. */
    dsrMin: number;
    /** Which multiple-testing policy sets the luck check's N (`lab.store.DSR_POLICY`, design §7.2). */
    dsrPolicy: DsrPolicy;
    /** The N that policy resolves to on this snapshot's data. Resolved at export time, not stored. */
    dsrN: number;
    /** One line of evidence for that N, written by the engine. Display as given; never parse it. */
    dsrNBasis: string;
    devStart: '1993-01-29';
    devEnd: '2015-10-16';
    testStart: '2015-10-19';
  };
```

**Code — add after `export type Gate = LabSnapshot['gate'];` (`:115`):**

```ts
/**
 * The named multiple-testing policies the luck gate can deflate by (`lab/npolicy.py`).
 * `all-trials` is in force and was left there deliberately (design §7.2); the other two are
 * measured, tested and one constant away, which is why the site names the one in use.
 */
export type DsrPolicy = 'all-trials' | 'methods' | 'effective';
```

**Code — add at the end of the file, beside the other `satisfies` lists:**

```ts
export const DSR_POLICIES = [
  'all-trials',
  'methods',
  'effective',
] as const satisfies readonly DsrPolicy[];

/** What each policy counts, in the site's own plain words. Never show the identifier alone. */
export const DSR_POLICY_LABEL: Record<DsrPolicy, string> = {
  'all-trials': 'one look per variant run',
  methods: 'one look per distinct idea',
  effective: 'one look per independent return stream',
};
```

**File (b):** `web/lib/sera/lab.ts`
**Change:** `raw` is cast, not parsed. A `lab.json` regenerated by an engine that predates this
phase would reach the page as `undefined` and render "N = undefined" rather than fail.

**Code — replace lines 5-9:**

```ts
import raw from '../../data/lab.json';
import { trialsByMethod } from './derive';
import { DSR_POLICIES } from './types';
import type { LabInsight, LabMethod, LabSnapshot, LabTrial } from './types';

/**
 * Build-time guard on the gate block every page reads.
 *
 * `raw` is cast, not validated, so a `web/data/lab.json` exported by an engine that predates the
 * N policy (design §7.2) would reach the luck bar as `undefined` and render silently wrong rather
 * than fail. The snapshot and this file always ship in the same commit — `lab stage` runs
 * `export-json`, and an engine test asserts the committed JSON is byte-for-byte the export of the
 * committed database — so a mismatch here can only mean the JSON was not regenerated.
 */
function requireGate(snap: LabSnapshot): LabSnapshot {
  const g = snap.gate;
  const ok =
    g != null &&
    Number.isFinite(g.dsrMin) &&
    Number.isInteger(g.dsrN) &&
    g.dsrN >= 0 &&
    DSR_POLICIES.includes(g.dsrPolicy) &&
    typeof g.dsrNBasis === 'string' &&
    g.dsrNBasis.length > 0;
  if (!ok) {
    throw new Error(
      'web/data/lab.json is missing a usable gate.dsrPolicy / gate.dsrN / gate.dsrNBasis. ' +
        'Regenerate it with `python -m seer_engine lab export-json` and commit it.',
    );
  }
  return snap;
}

export const lab = requireGate(raw as unknown as LabSnapshot);
```

**Impact:** the web build fails loudly on a stale snapshot instead of rendering a wrong number.

---

### Step 13: the site reads both luck-check failure labels

**File:** `web/lib/sera/derive.ts:13-21` and `:64-68`
**Change:** `FAILURE_LABEL.dsr` hard-matches the literal `'DSR >= 0.95'` against `trial.failed`.
`trials` is append-only, so the 110 rows judged under 0.95 carry that string **forever**, while
every trial judged after phase 4 carries `'DSR >= 0.90'`. A literal match reads one of the two as a
*pass*, which is the worst failure mode this page has: a trial that missed the luck check would
show a tick.

This is the one place in `web/` that hardcodes the threshold, and it is why the guard test in Step
9 scans `derive.ts`.

**Code — replace lines 13-21:**

```ts
/**
 * The engine's label for each condition, exactly as it appears in `trial.failed`.
 *
 * The luck check is the exception and is matched by prefix instead (`DSR_FAILURE_PREFIX`):
 * `trials` is append-only, so a trial judged before the owner moved the bar on 2026-10-07 carries
 * `DSR >= 0.95` for ever and one judged after carries `DSR >= 0.90`. Both mean "missed the luck
 * check", and matching one literal would quietly render the other as a pass.
 */
export const FAILURE_LABEL: Record<Exclude<ConditionKey, 'dsr' | 'drawdown'>, string> = {
  spy: 'beats SPY TR',
  pf: 'PF >= 1.3',
  trades: '>= 100 trades',
  owner: 'owner inputs',
};

/**
 * The two labels that carry a threshold in their own text, and so must be matched by prefix.
 *
 * `trials` is append-only, so a row judged before 2026-10-07 carries `DSR >= 0.95` and
 * `max DD <= 15%` for ever, while a row judged after carries `DSR >= 0.90` and `max DD <= 20%` —
 * the owner moved both bars that day. Matching either literal would render the other as a
 * **pass**, which is the worst failure this page has: a missed hurdle shown as a green tick.
 *
 * These mirror `store.LUCK_LABEL_PREFIX` and the live `dev.FAILURE_LABELS` drawdown entry; the
 * engine-side pins in Steps 9 and 14 are what keep the mirror honest.
 */
export const DSR_FAILURE_PREFIX = 'DSR >= ';
export const DRAWDOWN_FAILURE_PREFIX = 'max DD <= ';
```

**Code — replace `conditionOk` (`:63-68`):**

```ts
/** true = passed, false = missed, null = not measured. */
export function conditionOk(trial: LabTrial, key: ConditionKey): boolean | null {
  if (key === 'dsr') {
    if (trial.failed.some((f) => f.startsWith(DSR_FAILURE_PREFIX))) return false;
    return trial.dsr === null ? null : true;
  }
  if (key === 'drawdown') {
    return !trial.failed.some((f) => f.startsWith(DRAWDOWN_FAILURE_PREFIX));
  }
  if (trial.failed.includes(FAILURE_LABEL[key])) return false;
  return true;
}
```

> **Reconciled — the drawdown prefix is new, and it is the same bug one row down.** The owner's
> second change of 2026-10-07 (`tuning.MAX_DRAWDOWN` 0.15 → 0.20, Decision **D6**, phase 8) gives
> the drawdown label exactly the staleness the luck label has. Thirty of the 110 committed rows
> record `max DD <= 15%`, and the engine will write `max DD <= 20%` from now on.
>
> **This page stays a display of the recorded string, deliberately.** It shows what the lab said
> on the day a trial ran — which is why `trial.failed` fixtures saying `DSR >= 0.95` are correct
> and must not be rewritten. What it must never do is confuse "said it missed" with "said
> nothing". The engine's *verdict* is a different question and is answered elsewhere
> (`store.verdict` re-derives every threshold condition from the trial's columns); this page does
> not and should not try to reproduce it.

**Impact:** `FAILURE_LABEL` is used nowhere else in `web/` (verified: `derive.ts:14` and `:66` are
its only two occurrences), so narrowing its key type is safe. Every existing test that passes
`failed: ['DSR >= 0.95']` keeps its meaning — those fixtures quote recorded data, which is exactly
right and must not be rewritten.

---

### Step 14: the web contract test covers the new keys

**File:** `web/lib/sera/lab.test.ts:1-16`

**Code — replace lines 1-16:**

```ts
import { describe, expect, it } from 'vitest';
import { childrenOf, insightsOf, lab, methodById, trialsOf } from './lab';
import { DSR_POLICIES, INSIGHT_KINDS, METHOD_STATUSES, SOURCE_KINDS } from './types';

describe('lab snapshot (web/data/lab.json)', () => {
  it('has exactly the contract keys', () => {
    expect(lab.version).toBe(1);
    expect(Object.keys(lab).sort()).toEqual(
      ['asOf', 'benchmark', 'data', 'gate', 'ideasSeen', 'insights', 'methods', 'summary', 'trials', 'version'].sort(),
    );
    expect(typeof lab.asOf).toBe('string');
    for (const k of ['maxDrawdown', 'minProfitFactor', 'minTrades', 'dsrMin', 'dsrN'] as const) {
      expect(Number.isFinite(lab.gate[k])).toBe(true);
    }
    // The N the luck bar is deflated by, and the evidence for it (design §7.2).
    expect(DSR_POLICIES).toContain(lab.gate.dsrPolicy);
    expect(Number.isInteger(lab.gate.dsrN) && lab.gate.dsrN >= 0).toBe(true);
    expect(lab.gate.dsrNBasis.length).toBeGreaterThan(0);
    expect(lab.gate.devStart).toBe('1993-01-29');
  });

  it('writes every failure label in a shape conditionOk can read', () => {
    // `trials` is append-only: rows judged before 2026-10-07 carry `DSR >= 0.95`, rows judged
    // after carry `DSR >= 0.90`, and `conditionOk` reads the luck check by prefix for exactly
    // that reason. Checked against the real snapshot rather than a fixture, because the failure
    // this guards against is a label the engine starts writing that the site stops recognising —
    // which renders a missed hurdle as a tick, silently, on the page the owner reads.
    const known = new Set(Object.values(FAILURE_LABEL));
    const unreadable = lab.trials
      .flatMap((t) => t.failed)
      .filter(
        (f) =>
          !known.has(f) &&
          !f.startsWith(DSR_FAILURE_PREFIX) &&
          !f.startsWith(DRAWDOWN_FAILURE_PREFIX),
      );
    expect([...new Set(unreadable)]).toEqual([]);
  });

  it('still reads the two labels the owner moved the bars on', () => {
    // Both prefixes must actually match something in the committed snapshot, or the pin above
    // would pass vacuously after a label change that silenced them.
    const all = lab.trials.flatMap((t) => t.failed);
    expect(all.some((f) => f.startsWith(DSR_FAILURE_PREFIX))).toBe(true);
    expect(all.some((f) => f.startsWith(DRAWDOWN_FAILURE_PREFIX))).toBe(true);
  });
```

Add the two imports this needs to the `./derive` import at the top of the file (there is none
today — `lab.test.ts` imports only from `./lab` and `./types`):

```ts
import { DRAWDOWN_FAILURE_PREFIX, DSR_FAILURE_PREFIX, FAILURE_LABEL } from './derive';
```

**Impact:** none beyond the assertions. `FAILURE_LABEL` and `DSR_FAILURE_PREFIX` are both exported
by Step 13. This is the second of the two pins promised in **Requires** 3: Step 9 pins the web's
prefix to the engine's constant, and this pins it to the data the engine has actually written.

---

### Step 15: the shared test fixture carries the gate the lab now applies

**File:** `web/lib/sera/fixture.ts:4-12`
**Change:** `GATE` is `Gate`-typed, so it stops type-checking without the three keys. Its values
mirror the real lab on 2026-10-07 — bar 0.90, policy `all-trials`, N 110 — so the `/sera/how`
assertions read as facts.

**Code — replace the `GATE` constant:**

```ts
export const GATE: Gate = {
  maxDrawdown: 0.2,
  minProfitFactor: 1.3,
  minTrades: 100,
  dsrMin: 0.9,
  dsrPolicy: 'all-trials',
  dsrN: 110,
  dsrNBasis: '110 dev trials, every variant run counted as one independent look',
  devStart: '1993-01-29',
  devEnd: '2015-10-16',
  testStart: '2015-10-19',
};
```

**Impact:** every suite importing `GATE` (`how/view.test.ts`, `derive.test.ts`,
`methods/view.test.ts`) compiles again; three assertions move with it (Steps 18b, 19c, 19d).

---

### Step 16: the glossary defines the luck check by the rule in force

**File:** `web/lib/sera/glossary.ts:54-61`

**Code — replace both entries:**

```ts
  dsr: {
    term: 'Luck check (DSR)',
    plain:
      'The chance a result is real skill rather than the luckiest of many tries, after discounting ' +
      'for how many tries have been counted. The bar it has to clear is the owner’s call on how ' +
      'much doubt is acceptable.',
  },
  tries: {
    term: 'N (tries)',
    plain:
      'Every test the lab has ever run, all kept on the record and all counted, so the luck check ' +
      'can discount a winner found by trying many things. Trying more raises the bar for everyone.',
  },
```

**Impact:** `glossary.test.ts` asserts only that every condition key has a term, not the prose.

---

### Step 17: the luck bar draws the N it deflates by

**File:** `web/app/sera/overview.ts:309-333`
**Change:** `luck()` gains a vertical reference line at `gate.dsrN`. The chart's x-axis is already
"tries counted when it ran", so the N in force is a line on that same axis — and under
`all-trials` it sits right at the leading edge of the cloud, which is the honest picture of D1b's
ratchet: every new dot pushes the line right. The policy and its evidence come back with it so
`page.tsx` can caption the section without reaching into the gate twice.

**Code — replace the whole `(5) The luck bar` section:**

```ts
// ---- (5) The luck bar ---------------------------------------------------------------------------

export type Luck = {
  points: ScatterPoint[];
  refY: RefLine[];
  /** The N the gate deflates by today, on the same axis as each try's own N. */
  refX: RefLine[];
  yTicks: Tick[];
  above: number;
  total: number;
  n: number;
  policy: DsrPolicy;
  /** One line of evidence for `n`, written by the engine. Shown as given. */
  basis: string;
};

export function luck(snap: LabSnapshot): Luck | null {
  const gate = snap.gate;
  const rows = devTrials(snap).filter((t): t is LabTrial & { dsr: number } => t.dsr !== null);
  if (rows.length === 0) return null;
  const points: ScatterPoint[] = rows.map(t => ({
    id: `t${t.n}`,
    x: t.nTrialsAtRun,
    y: t.dsr,
    color: t.eligible ? ELIGIBLE_COLOR : t.dsr >= gate.dsrMin ? ABOVE_COLOR : LAB_COLOR,
    r: t.eligible ? 8 : 6,
    tip: `${t.candidateId}: DSR ${ratioText(t.dsr)}, scored at N = ${t.nTrialsAtRun}`,
    href: methodHref(t.methodId),
  }));
  return {
    points,
    refY: [{ value: gate.dsrMin, label: `Luck bar ${ratioText(gate.dsrMin)}`, color: 'var(--neg)' }],
    refX: [
      {
        value: gate.dsrN,
        label: `N = ${gate.dsrN} today`,
        color: 'var(--ink-3)',
        dash: '4 3',
        tip: gate.dsrNBasis,
      },
    ],
    yTicks: [0, 0.25, 0.5, 0.75, 1].map(v => ({ value: v, label: v.toFixed(2) })),
    above: rows.filter(t => t.dsr >= gate.dsrMin).length,
    total: rows.length,
    n: gate.dsrN,
    policy: gate.dsrPolicy,
    basis: gate.dsrNBasis,
  };
}
```

**Code — add `DsrPolicy` to the type import at `:15`:**

```ts
import type { DsrPolicy, LabInsight, LabMethod, LabSnapshot, LabTrial } from '../../lib/sera/types';
```

**Impact:** `ScatterChart` already accepts `refX` (`ScatterChart.tsx:46`, drawn by `VRef`) and
already folds `refX` values into the x extent, so the line is always in view.

---

### Step 18: the overview page says which bar, which N, and why

**File (a):** `web/app/sera/page.tsx:90-98` and `:231-263`
**Change:** the Tries stat's sub-line ("Every try raises the bar for luck") is *true* under
`all-trials` and stays — but it now carries the number, because that is D1b's ratchet in one line.
The luck section names the bar, the policy, its N and the evidence.

**Code — add the types import (new line, after `:16`):**

```tsx
import { DSR_POLICY_LABEL } from '@/lib/sera/types';
```

**Code — replace the Tries `Stat` (`:90-98`):**

```tsx
              <Stat
                label={
                  <>
                    Tries (<T k="tries">N</T>)
                  </>
                }
                value={String(st.tries)}
                sub={`All ${g.dsrN} are counted, and every new one raises the bar`}
              />
```

**Code — replace the `(5) The luck bar` section (`:231-263`):**

```tsx
        {/* (5) The luck bar */}
        <Section
          className={s.luck}
          eyebrow="The luck bar"
          title={lk ? `${lk.above} of ${lk.total} cleared the luck bar` : 'No luck scores yet'}
          caption={
            lk
              ? `The more we try, the likelier one looks good by chance, so each try's luck score must reach ${ratioText(g.dsrMin)} — the owner's call on how much doubt is acceptable. The discount counts ${DSR_POLICY_LABEL[lk.policy]}: N = ${lk.n} today (${lk.basis}). Each dot sits at the N it was scored at on the day it ran, so the cloud drifts right as the search goes on.`
              : `Each try's luck score must reach ${ratioText(g.dsrMin)}, discounted by ${DSR_POLICY_LABEL[g.dsrPolicy]}.`
          }
        >
          {lk ? (
            <ScatterChart
              ariaLabel={`Luck score of ${lk.total} tries against the number of tries counted, with the ${ratioText(g.dsrMin)} bar and the N = ${lk.n} the gate deflates by today`}
              points={lk.points}
              refY={lk.refY}
              refX={lk.refX}
              yDomain={[0, 1]}
              yTicks={lk.yTicks}
              includeZeroX
              xFormat={fmtNumber(0)}
              xLabel="Tries counted when it ran (N)"
              yLabel="Luck score (DSR)"
              height={460}
              legend={
                <Legend
                  items={[
                    { label: 'Below the bar', color: LAB_COLOR, shape: 'dot' },
                    { label: 'Above the bar', color: ABOVE_COLOR, shape: 'dot' },
                    { label: 'Cleared every hurdle', color: ELIGIBLE_COLOR, shape: 'dot' },
                  ]}
                />
              }
            />
          ) : (
            <p className={s.empty}>Luck scores start with the lab&apos;s own tries; the older ones were run before it existed.</p>
          )}
        </Section>
```

**File (b):** `web/app/sera/overview.test.ts:86-94` and `:246-259`
**Change:** `snap()`'s gate needs the new keys and the new bar; `above` moves from 1 to 2 because
the fixture's `dsr: 0.9` trial now clears a 0.9 bar — which is precisely the change the owner made,
reproduced in miniature.

**Code — replace the `gate` block of `snap()` (`:86-94`):**

```ts
  gate: {
    maxDrawdown: 0.2,
    minProfitFactor: 1.3,
    minTrades: 100,
    dsrMin: 0.9,
    dsrPolicy: 'all-trials',
    dsrN: 4,
    dsrNBasis: '4 dev trials, every variant run counted as one independent look',
    devStart: '1993-01-29',
    devEnd: '2015-10-16',
    testStart: '2015-10-19',
  },
```

**Code — replace the `luck` describe (`:246-259`):**

```ts
describe('luck', () => {
  it('plots only tries with a DSR against the gate line', () => {
    const l = luck(snap())!;
    expect(l.points).toHaveLength(2);
    expect(l.refY[0].value).toBe(0.9);
    expect(l.above).toBe(2); // 0.90 and 0.97 both clear a 0.90 bar
    expect(l.points.map(p => p.x)).toEqual([4, 4]);
    expect(l.yTicks.map(t => t.label)).toEqual(['0.00', '0.25', '0.50', '0.75', '1.00']);
  });
  it('marks the N the gate deflates by today, with its evidence', () => {
    const l = luck(snap())!;
    expect(l.refX[0].value).toBe(4);
    expect(l.refX[0].label).toBe('N = 4 today');
    expect(l.refX[0].tip).toBe('4 dev trials, every variant run counted as one independent look');
    expect(l.n).toBe(4);
    expect(l.policy).toBe('all-trials');
  });
  it('is null when no try has a DSR', () => {
    const base = snap();
    expect(luck({ ...base, trials: base.trials.map(t => ({ ...t, dsr: null })) })).toBeNull();
  });
});
```

**Impact:** `overview.test.ts:167`'s `trialTip` assertion ("misses: Beats SPY, Luck check") is
unaffected — it reads `trial.failed`, not the threshold, and Step 13's prefix matcher still catches
that row's recorded `'DSR >= 0.95'`.

---

### Step 19: the method page and the /sera/how page

**File (a):** `web/app/sera/methods/view.ts:152-182`
**Change:** `conditionTip('dsr')` says "counting every try the lab has made", which is correct and
stays, now with the number. `conditionSentence('dsr')` prints the DSR at two decimals against a
threshold that is also two decimals — at 0.90 that reads `0.90 < 0.90`, which is nonsense. DSR
differences live in the third decimal (0.899 vs 0.916), so the score is shown at three.

**Code — replace the `dsr` case of `conditionTip` (`:159`):**

```ts
    case 'dsr': return `A luck-adjusted score of at least ${fixed(gate.dsrMin, 2)}, discounted by all ${count(gate.dsrN)} tries counted so far (${gate.dsrNBasis})`;
```

**Code — replace the `dsr` case of `conditionSentence` (`:179-180`):**

```ts
    case 'dsr':
      return `${label}: ${yn} (${fixed(t.dsr, 3)} ${ok ? '≥' : '<'} ${fixed(gate.dsrMin, 2)}, scored at N = ${count(t.nTrialsAtRun)}).`;
```

**File (b):** `web/app/sera/methods/view.test.ts:143-148`
**Change:** the asserted sentence moves with the fixture's new bar and the three-decimal score
(`trial().dsr === 0.899`).

**Code — replace the `w.sentence` expectation:**

```ts
    expect(w.sentence).toBe(
      'Beats SPY: no (7.6% vs 7.9% a year). Max drawdown: yes (12.9% ≤ 15%). ' +
      'Profit factor: yes (2.27 ≥ 1.3). Trade count: yes (1,130 ≥ 100). ' +
      'Owner inputs: yes (none needed). ' +
      'Luck check: no (0.899 < 0.90, scored at N = 58).',
    );
```

**File (c):** `web/app/sera/methods/[id]/page.tsx:329`
**Change:** the DSR column shows a bare number whose meaning depends on the N it was scored at.

**Code — replace line 329:**

```tsx
                  <td className={`num ${s.r}`}>
                    {fixed(t.dsr, 2)}
                    {t.dsr !== null && <span className={s.vs}> at N {count(t.nTrialsAtRun)}</span>}
                  </td>
```

`count` and `fixed` are already imported from `../view` (`:21`); `s.vs` already exists
(`[id]/method.module.css:48`).

**File (d):** `web/app/sera/how/view.ts:86`, `:200-204`, `:215-219`

**Code — replace the dev stage's `countTip` (`:86`):**

```ts
      countTip: `N = ${count(c.devTrials)}: every try on the practice years, the early Seer research included — and all ${count(g.dsrN)} of them discount the luck check`,
```

**Code — replace the `dsr` entry of `hurdles` (`:200-204`):**

```ts
    dsr: {
      title: 'Not just luck',
      target: `Luck check ≥ ${num(gate.dsrMin)}`,
      plain: `Try enough ideas and one will look great by chance. The luck check discounts a result for every try ever made (N = ${count(gate.dsrN)} so far, out of ${count(tries)} runs on the practice years), so the bar rises as the lab keeps searching. How high it has to reach — ${num(gate.dsrMin)} — is the owner's call on how much doubt is acceptable.`,
    },
```

**Code — replace the `counted` entry of `honestyRules` (`:215-219`):**

```ts
    {
      key: 'counted',
      title: 'Every try is counted',
      body: `${plural(devTrials, 'try', 'tries')} so far, failures included, and none is ever removed. The luck check uses all ${count(g.dsrN)} of them, so trying more never makes a winner easier to find — it makes it harder.`,
    },
```

**File (e):** `web/app/sera/how/view.test.ts:60-65`, `:106-111`
**Change:** three assertions pin `0.95`, and the "reads it from the gate" case at `:63` overrides
`dsrMin` to `0.9`, which is now the default and would no longer prove anything. It moves to `0.8`.

**Code — replace lines 60-65 exactly (inside `it('reads the windows and thresholds from the gate')`):**

```ts
    expect(st[3].detail.join(' | ')).toBe(
      'Beat SPY + dividends | Worst fall ≤ 20% | PF ≥ 1.3 · 100+ trades | No owner inputs | Luck check ≥ 0.9',
    );
    // 0.3 / 0.8, not 0.2 / 0.9: once the defaults ARE 0.2 and 0.9 an override to those values is
    // a no-op and the case passes while proving nothing. The override has to differ from the
    // default or it is not testing that the value is read from the gate.
    const loose = pipelineStages(snap({ gate: { ...GATE, maxDrawdown: 0.3, dsrMin: 0.8 } }));
    expect(loose[3].detail).toContain('Worst fall ≤ 30%');
    expect(loose[3].detail).toContain('Luck check ≥ 0.8');
```

**Code — replace lines 106-111 (the `hurdles` assertions):**

```ts
    expect(h.map(x => x.target)).toEqual([
      'More than SPY total return', 'Max drawdown ≤ 20%', 'Profit factor ≥ 1.3', 'At least 100 trades',
      'Nothing left for the owner to decide', 'Luck check ≥ 0.9',
    ]);
    expect(h.map(x => x.term)).toEqual(['spyTr', 'maxDrawdown', 'profitFactor', 'trades', 'ownerInputs', 'dsr']);
    expect(h[5].plain).toContain('N = 110'); // the gate's N, from GATE.dsrN
    expect(h[5].plain).toContain('58'); // the tries argument, still quoted
```

Only two things change in that block: the trailing `Luck check ≥ 0.95` → `≥ 0.9`, and the
`loose` override `dsrMin: 0.9` → `0.8` so the case still proves the value is read from the gate
rather than from a constant that now happens to equal it. Lines 57-59 and 66 are untouched.

**File (f):** `web/lib/sera/derive.test.ts:43` and `:63-67`
**Change:** the `0.95 or more` target follows `GATE.dsrMin`, and the luck-check case gains proof
that both recorded labels read as a miss — the regression Step 13 exists to prevent.

**Code — replace line 43:**

```ts
    expect(checks[5]).toMatchObject({ value: '0.97', target: '0.9 or more', ok: true });
```

**Code — replace the `marks an unmeasured luck check…` test (`:63-67`):**

```ts
  it('marks an unmeasured luck check as null, and a failed one as false under either bar', () => {
    const historical = trial({ dsr: null, failed: ['beats SPY TR'] });
    expect(gateChecks(historical, GATE)[5]).toMatchObject({ value: 'not measured', ok: null });
    // `trials` is append-only: rows judged before 2026-10-07 keep `DSR >= 0.95` for ever, and
    // rows judged after carry `DSR >= 0.90`. Both are misses; matching one literal would show
    // the other as a tick.
    const old = trial({ dsr: 0.4, failed: ['DSR >= 0.95'] });
    expect(gateChecks(old, GATE)[5]).toMatchObject({ value: '0.40', ok: false });
    const recent = trial({ dsr: 0.4, failed: ['DSR >= 0.90'] });
    expect(gateChecks(recent, GATE)[5]).toMatchObject({ value: '0.40', ok: false });
  });
```

**Impact:** `derive.test.ts:113`'s `failed: ['max DD <= 15%', 'DSR >= 0.95']` and
`methods/view.test.ts:154`, `:211` all quote recorded data and keep working unchanged under the
prefix matcher.

---

### Step 20: regenerate `web/data/lab.json` — last

**File:** `web/data/lab.json`
**Change:** regenerated from the committed database. **Run this only after phases 8 and 4 have
landed**, because the JSON must be the export of the post-phase-4 database with phase 8's
`MAX_DRAWDOWN = 0.20`, phase 4's `DSR_MIN = 0.90` and the post-Step-8 gate block:
`test_the_committed_snapshot_is_the_export_of_the_committed_database` asserts the two are
byte-identical, so a regeneration done earlier would have to be redone.

> **`web/data/lab.json` has three writers in this set, and the rule is one line (Decision D10).**
> Phase 8 regenerates it when it moves `gate.maxDrawdown`; phase 4 regenerates it when it moves
> `gate.dsrMin` and the two method statuses; this phase regenerates it last, when it adds
> `gate.dsrPolicy` / `dsrN` / `dsrNBasis`. Each writes the file **by re-running the export**, and
> each stages it in its own explicit path allowlist. **It is never hand-edited and a conflict in
> it is never merged** — the resolution is always to re-run `lab export-json` on the current tree
> and commit the result. The file is a projection of `lab/lab.sqlite` plus the engine's
> constants; whichever phase last changed either of those owns the projection until the next one
> does.

**Command:**

```bash
cd /home/miftah/.worktrees/seer/lab-luck-gate/engine && \
  PYTHONPATH=/home/miftah/.worktrees/seer/lab-luck-gate/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab export-json
```

**Expected gate diff:**

```diff
-"gate":{"maxDrawdown":0.2,"minProfitFactor":1.3,"minTrades":100,"dsrMin":0.95,"devStart":…
+"gate":{"maxDrawdown":0.2,"minProfitFactor":1.3,"minTrades":100,"dsrMin":0.9,"dsrPolicy":"all-trials","dsrN":110,"dsrNBasis":"…","devStart":…

(`maxDrawdown` already reads **0.2** on BOTH sides: phase 8 is in wave 1 and regenerates this
file itself, so by the time this phase runs the 0.15 -> 0.2 move is already in the committed
snapshot. If it still reads 0.15 here, phase 8 has not landed and this step must wait.)
```

Phase 4's own change to `methods.status` for M0022 will also show in the `methods` array and in
`summary.byStatus` — that part of the diff belongs to phase 4 and appears here only because this is
the regeneration that follows it.

**Do not** run `lab stage`: it `git add`s `lab/lab.sqlite` as well, and the swarm shares one
worktree (`/home/miftah/.worktrees/seer/lab-luck-gate`), so this phase's commit must stage an
explicit path allowlist — `web/data/lab.json` yes, `lab/lab.sqlite` never.

**Impact:** the site's gate block becomes real data; `requireGate` passes.

---

## Verification

**Build (web):**
```bash
cd /home/miftah/.worktrees/seer/lab-luck-gate/web && npm run build
```

**Tests (web):**
```bash
cd /home/miftah/.worktrees/seer/lab-luck-gate/web && npm test
```

**Tests (engine)** — the worktree has no `engine/.venv`; use the main checkout's interpreter with
`PYTHONPATH` pointed at the worktree's `src`, which shadows the editable install:
```bash
cd /home/miftah/.worktrees/seer/lab-luck-gate/engine && \
  PYTHONPATH=/home/miftah/.worktrees/seer/lab-luck-gate/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m pytest -q
```

Narrower, while iterating:
```bash
... -m pytest -q tests/test_lab_gate_wording.py tests/test_lab_prereg.py \
                 tests/test_lab_snapshot.py tests/test_lab_test_window.py tests/test_lab_runner.py
```

**Manual check — the bar sweep.** From the worktree root:
```bash
grep -rnE "(DSR|[Ll]uck check) *(>=|≥|of at least) *0\.95" \
  docs .claude engine/package_readme.md engine/src/seer_engine/lab/prereg.py web/app web/lib
```
The **only** acceptable hits are in `docs/plans/2026-10-04-method-lab-design.md` — §3's preserved
original sentence and §7.1's quotation of it. Anything else is a miss. Recorded failure labels
inside test fixtures (`failed: ['DSR >= 0.95']`) are data, not a statement of the rule, and are
outside this pattern because they are not preceded by `>=`-with-spaces in the matched shape; if one
shows up, read it before changing it.

**Manual check — the N wording is still there and still correct:**
```bash
grep -rn "every dev trial\|all lab trials" docs .claude engine/package_readme.md \
  engine/src/seer_engine/lab/prereg.py
```
Hits are **expected and correct**: `DSR_POLICY` is `all-trials`. What must not appear is a claim
that the N *changed*.

**Manual check — the page.** `npm run dev` in `web/`, open `/sera`: the luck-bar caption gives the
bar as `0.90`, names the policy in plain words, gives `N = 110` with the engine's evidence line,
and the chart carries a red horizontal line at 0.90 and a dashed vertical line labelled
`N = 110 today` at the right-hand edge of the cloud. Three dots (M0022-W-TV14, M0022-W-TV16 and
M0020-W-NOSTOP, which the 20% drawdown bar brings in) now sit above the bar in the "cleared every
hurdle" colour. `/sera/how`'s "Not just luck" hurdle reads
`Luck check ≥ 0.9`. `/sera/methods/M0022`: the DSR column shows `0.92 at N 110`, and the Luck check
tick is green on both W-TV14 and W-TV16 while every trial recorded with `DSR >= 0.95` in `failed`
still shows a cross.

**Exit criteria:**
0. `web/lib/sera/derive.ts` matches **both** threshold-bearing labels by prefix
   (`DSR_FAILURE_PREFIX`, `DRAWDOWN_FAILURE_PREFIX`), and both prefixes are pinned to the engine
   — `store.DSR_LABEL` and `dev.FAILURE_LABELS[1]` each start with theirs, and so do the
   historical `"DSR >= 0.95"` and `"max DD <= 15%"` on the committed rows
   (`test_the_web_mirrors_the_engines_luck_label_prefix`,
   `test_the_web_mirrors_the_engines_drawdown_label_prefix`, and the data pin in Step 14).
1. The bar sweep finds `0.95`-as-the-gate **only** in the design document, in §3 (preserved) and
   §7.1 (quoted as superseded).
2. `docs/plans/2026-10-04-method-lab-design.md` has a §7 dated 2026-10-07 that quotes §3's original
   sentence, attributes the threshold change to the owner's stated risk appetite, records that the
   N lever was measured (ρ̄ = 0.595, participation ratio 2.44, 23 methods, 110 rows) and
   deliberately **not** pulled, gives the three-vs-seven eligibility measurement that made it a
   choice (three clear at N = 110, all seven luck-only candidates at N = 23), and records D1b's deferred ratchet with the N that re-closes it — **N = 143, 33 more
   dev trials** — stated as a reset of the clock rather than a fix.
3. `python -m seer_engine lab export-json` produces a `gate` block with `dsrMin == store.DSR_MIN`
   and carrying `dsrPolicy`, `dsrN` and `dsrNBasis`; `web/data/lab.json` is that export
   byte-for-byte.
4. A trial whose recorded `failed` contains `DSR >= 0.95` **and** one containing `DSR >= 0.90` both
   render the luck check as a miss on the site.
5. `npm run build` and `npm test` pass in `web/`; `pytest` passes in `engine/`.
6. `store.DSR_MIN`, `store.DSR_POLICY`, `store.DSR_LABEL`, `backtest.dev.deflated_sharpe`,
   `TRANSITIONS`, every `trials` row and `lab/lab.sqlite` are byte-for-byte as phase 4 left them.
7. `store.test_looks(conn)` still reads `0` — nothing here runs a backtest at all.

---

## Handoffs

- **Phase 4 — the shared luck-label matcher (settled in the index; nothing left to decide).**
  Phase 4 owns `DSR_MIN = 0.90`, `DSR_LABEL = "DSR >= 0.90"` and a prefix-matching helper exported
  from `store.py`. Phase 7's half is Step 13 (`derive.ts` matches the `"DSR >= "` prefix) plus the
  two pins in Steps 9 and 14. The one thing the reconciler should carry back to phase 4: **the web
  cannot call the Python helper**, so phase 4's helper and `derive.ts`'s `DSR_FAILURE_PREFIX` are
  two expressions of one rule, and Step 9's test is what keeps them equal. If phase 4 renames the
  helper that is fine — the test checks `store.DSR_LABEL.startswith(...)`, the property, not the
  name.
- **`commands/lab.py:206` — settled, and it is phase 4's.** Both phase 5 and this phase flagged
  the same defect. One owner per file region: **phase 4** fixes it (its Step 7e), because the rule
  it delegates to (`store.owner_failures`) is phase 4's symbol in phase 4's file. Reconciled
  further: that call site now passes the **row**, not `row["failed"]` — the engine stopped reading
  conditions out of recorded strings altogether when the owner moved the drawdown bar too. Step
  9's guard deliberately does not scan `commands/lab.py`.
- **Phase 5 — the ratchet warning.** D1b: `lab status` warns when the best luck-only candidate is
  within 0.03 of the bar, naming the N that would sink it. Design §7.3 states that behaviour as a
  promise; if phase 5 words it differently or scopes it differently, the reconciler should align
  §7.3 with what phase 5 actually ships, because §7.3 is the design document making a commitment on
  phase 5's behalf.
- **Phase 5 — `lab luck`.** Design §7.2 refers to the subcommand by name as the way to inspect
  the gate's sensitivity to N. If phase 5 names it differently, the reconciler fixes that one
  reference.
- **Phase 2/4 — `lab/runner.py:8` and `lab/store.py:314`.** Both docstring/comment lines say
  `"N = every dev trial in the lab"` / `"lab-wide N"`. Under `all-trials` **both are still
  correct**, so there is nothing to fix today — but if either phase ever flips the default, they
  are the two places that go stale first. Noted, not actioned.
- **Phase 6 — design §3's paper-entry sentence.** §7.4 is written to Decisions D3 and is marked
  `<!-- PHASE-6-WORDING -->`. If phase 6's one-line wording for `roster.py`'s doctrine paragraph
  differs, the reconciler replaces §7.4's second paragraph with it; the structure (amendment marker
  in §3 bullet 4, body in §7.4) stays.
- **Not done, deliberately:** `docs/ROADMAP.md:78` records M0001 as "DSR 0.90 at N = 58". That is a
  dated historical record of what happened, not a statement of the rule, and rewriting it would
  falsify the log. Left alone.
- **Not done, deliberately:** `SNAPSHOT_VERSION` stays `1`. See Step 8's Impact for the reasoning
  and for the guard that replaces a version bump.
- **Not done, deliberately:** test fixtures that pass `failed: ['DSR >= 0.95']` or
  `['max DD <= 15%']` are **not** updated to `0.90` / `20%`. They quote what the append-only table
  actually holds; changing them would remove the only coverage of the older labels, which is
  exactly what the two prefix matchers exist to handle.

- **To phase 8 — the three files where this phase's gate work and yours meet.** This phase owns
  `web/lib/sera/fixture.ts`'s `GATE`, `web/app/sera/overview.test.ts`'s `snap()` gate and
  `web/app/sera/how/view.test.ts`, because it rewrites each of those gate objects wholesale for
  the three new keys; splitting one gate literal between two phases is a guaranteed collision. So
  **this phase carries the drawdown number in those three files** (`maxDrawdown: 0.2`,
  `Worst fall ≤ 20%`) as part of its own edits. Phase 8 owns `web/lib/metrics.ts` — a different
  file, a different checklist, and the one that hardcodes both the label and the comparison — plus
  `backtest/tuning.py`, `backtest/metrics.py`, `dev.FAILURE_LABELS` and design §1 item 4.
  **Design document:** phase 8 owns §1 item 4 and its dated revision note; this phase owns §3 and
  §7, including §7.5's pointer at §1. Disjoint regions in one file; same protocol as `store.py`.

- **To phase 8 — the override-is-a-no-op trap, which bites whoever merges second.**
  `how/view.test.ts` and `derive.test.ts` override the gate to a non-default value *to prove the
  page reads the gate rather than a constant*. Once the defaults become `0.2` and `0.9`, an
  override **to** `0.2` / `0.9` is a no-op: the test passes and proves nothing. This phase moves
  `web/app/sera/how/view.test.ts`'s override to `maxDrawdown: 0.3, dsrMin: 0.8` for that reason.
  **Reconciled, round 2:** phase 8 moves the *same* line to the *same* values, and additionally
  owns `web/lib/sera/derive.test.ts`'s override (`maxDrawdown: 0.3, minProfitFactor: 1.5,
  minTrades: 50` — no `dsrMin`), which this phase does not touch. Phase 8 is in wave 1 and lands
  first; this phase's block is written to be identical, so the merge is a no-op where they
  overlap. **Whoever merges second must check the override *values*, not merely that the file
  merged** — if a resolution puts either back to `0.2` or `0.9`, the test passes while proving
  nothing. Note the real paths: `web/app/sera/how/view.test.ts` and `web/lib/sera/derive.test.ts`
  (there is no `web/app/sera/how/derive.test.ts`).

- **To phase 9 — the site shows a recorded string and must keep doing so.** When phase 9
  luck-tests the 54 seed trials it writes `trial_moments` rows and **no** `trials` rows, so every
  `trials[*].failed`, `.dsr` and `.eligible` in `web/data/lab.json` is unchanged and nothing on
  this site moves. If a later phase ever wanted the site to show the *derived* verdict instead of
  the recorded one, that is a new snapshot key and a deliberate decision — `store.verdict` is
  there for it — not a quiet change to what `trials[*]` means.

---

## Risks

1. **`DSR_MIN` does not land in phase 4.** Ownership is settled — the index names phase 4 as its
   sole owner — so this is now an ordering risk, not an ambiguity. If phase 7 is implemented first,
   design §7.1 asserts a threshold the code does not apply, `prereg.gate_text` writes
   `DSR >= 0.95` into a committed file while §7.1 says 0.90, and
   `test_the_gate_text_is_built_from_the_constants_that_decide_the_verdict` still *passes*, because
   it reads the constant rather than the number. **Mitigation:** `Depends on: Phase 4` is a hard
   dependency, not a preference; exit criterion 6 and the bar sweep are the human checks.
2. **A luck-check label that does not start with `"DSR >= "`.** Index-guaranteed as phase 4's
   obligation, and now pinned twice from this side — Step 9 against `store.DSR_LABEL`, Step 14
   against the committed snapshot's own `failed` arrays — so a change fails a test instead of
   rendering a missed hurdle as a green tick. Residual risk: both pins live in files phase 7 owns,
   so a future phase that changes the label and "fixes" the tests by editing them would get away
   with it. The failure mode is worth restating wherever that happens.
3. **`npolicy.effective_n` is slow on a read-only connection.** `snapshot_json` is called
   repeatedly across the engine test suite, and under `all-trials` the honest answer is a single
   `COUNT(*)` — but if phase 1 computes the correlation matrix eagerly for the evidence line, every
   snapshot pays for 110 curves. **Mitigation:** Requires 4 asks for a total, read-only
   `effective_n`; if the suite slows noticeably, phase 1 memoizes or makes the basis for
   `all-trials` cheap.
4. **`num(0.9)` renders `0.9`, not `0.90`.** The `/sera/how` page will read `Luck check ≥ 0.9`.
   That is consistent with how the page already renders `PF ≥ 1.3` and is left alone deliberately;
   the two places where the extra digit matters (`conditionTip`, `conditionSentence`) use
   `fixed(gate.dsrMin, 2)` instead.

---

## Rollback

`git revert <phase-7 commit>` restores every file, `web/data/lab.json` included — the snapshot is
committed text, not a build artifact, so the revert is complete and needs no regeneration step.

Nothing in this phase is load-bearing for another: with phase 7 reverted, phases 1–6 still build and
still pass, the gate still decides verdicts under `store.DSR_MIN` and `store.DSR_POLICY`, and the
only loss is that the documents and the site describe a bar the code no longer applies — with one
real consequence worth knowing about: `web/lib/sera/derive.ts` reverts to matching the literal
`'DSR >= 0.95'`, so any trial recorded under `"DSR >= 0.90"` would show its missed luck check as a
pass. **If phase 7 is reverted while phase 4 stands, re-apply Step 13 on its own.**

Partial rollback, otherwise:
- **Engine only** — `git checkout HEAD~1 -- engine/src/seer_engine/lab/store.py
  engine/src/seer_engine/lab/prereg.py engine/tests/ web/data/lab.json`, then
  `git checkout HEAD~1 -- web/` as well: the `gate` keys and `requireGate` must go together, or the
  web build fails on the regenerated JSON (by design).
- **Web only** — not separable from `web/data/lab.json`; revert both or neither.
