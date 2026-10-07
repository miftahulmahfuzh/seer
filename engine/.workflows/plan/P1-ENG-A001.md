# P1-ENG-A001 — The gate-wording guard sweeps the lab journal's newest synthesis

**Card:** [miftahulmahfuzh/seer#1](https://github.com/miftahulmahfuzh/seer/issues/1)
**Date:** 2026-10-07 · round 1
**Files:** `engine/tests/test_lab_gate_wording.py`

## The bug, restated

The Sera Overview headlined insight #21 (a `synthesis` row, `2026-10-06T13:43:21`) saying
*"we require 0.95"* while the gate panel on the same page read **0.90**. The page was faithful;
the record had gone stale under it. `0033820` fixed the symptom by appending insight #27, so
`newest(kind === 'synthesis')` promotes the current note and #21 recedes into the Journal.

Phase 7's guard, `test_lab_gate_wording.py`, could not have caught it: `SCANNED` is ten shipped
files and journal bodies are not among them.

## The measurement that decided the design

The card suggests reusing `BAR_WITH_NUMBER` and adding journal bodies to the sweep. **Measured
against all 27 committed insights, `BAR_WITH_NUMBER` matches zero of them** — including #21.

The reason is structural, not incidental. `BAR_WITH_NUMBER` is
`(?:DSR|luck\s+check)\s*(?:>=|≥|of\s+at\s+least)\s*(\d+\.\d+)` — the engineering idiom, which is
how `SKILL.md`, `prereg.py` and `derive.ts` write a threshold. Sera's journal is written **for the
owner, in plain English**, and never uses it:

| Insight | How it states the bar |
|---|---|
| #21 | "on a scale where **we require 0.95**" |
| #21 | "fell 19.6% at its worst, **past our 15% limit**" |
| #15 | "at its worst it fell 22% from a peak, and **our limit is 15%**" |
| #27 | "**The luck bar moved to 0.90** and the **drawdown bar to 20%**" |

So adding `SCANNED` entries as suggested would have shipped a guard that is **green on the exact
document that caused the bug** — the same class of silent-pass defect as `derive.ts` hard-matching
`'DSR >= 0.95'`, one level up. A vacuous guard is worse than none, because it reads as coverage.

## Approaches considered

| # | Approach | Verdict |
|---|---|---|
| **A** | **Prose matcher beside `BAR_WITH_NUMBER`, same module, same `_code_spans()`, scoped to the newest synthesis, compared against live constants** | **chosen** |
| B | Require a superseded bar to be written in backticks, so the existing `_code_spans()` exemption does all the work | **impossible** |
| C | Reuse `BAR_WITH_NUMBER` unchanged; add journal bodies to `SCANNED` | rejected on evidence |
| D | Have Sera state bars via a rendered template token the exporter fills in | rejected on scope |

**Why B is impossible, not merely worse.** It would require rewriting insight #27 to put its
`0.95` reference in backticks. `insights` carries `insights_no_update` and `insights_no_delete`
triggers that `RAISE(ABORT)` — the table is append-only by construction. The card also said
outright not to let the design force a rewrite of #27. B is ruled out by the schema, not by taste.

**Why C is rejected.** Measured: 0 matches across 27 insight bodies. See above.

**Why D is rejected.** Changing how the journal is authored touches the explorer skill, the
`lab insight` command and the export, makes Sera's prose less readable to its one reader, and
still leaves every historical insight exempt by construction — which A achieves for free.
Criterion *Scope*: not the smallest change that fully satisfies the card.

**Scoring A against the four criteria.** *Convention* — it is the shape phase 7 already uses
(a regex pinned to a live constant, a span exemption, one parametrised test). *Scope* — one test
file, no production code, no data rewritten. *Verifiability* — the gate proves it, and the
non-vacuity pin below proves the guard is not green by accident. *Reversibility* — one commit,
test-only.

## The design

### Scope rule (from the card, adopted as written)

- **In scope:** the newest `synthesis` insight only — the one `overview.ts` renders as its
  headline. If it states a luck bar it must equal `store.DSR_MIN`; if it states a drawdown bar it
  must equal `tuning.MAX_DRAWDOWN`.
- **Out of scope:** every older insight, of any kind. History, exempt by construction.
- `_code_spans()` is reused verbatim, so a backticked literal in an insight body is exempt by the
  same mechanism as in the docs sweep.

### The prose matcher

A bar noun, then a **present-tense copula or destination**, then a number:

```
REL = (?:is|are|to|at|=|>=|≥|of\s+at\s+least)
```

The whole design sits in what that set **omits**. `from`, `by`, `within`, `of`, `as` and `was`
are absent on purpose, because each marks a number that is *not* the rule in force:

| Phrase in insight #27 | Why it does not match |
|---|---|
| "the luck bar went **from** 0.95 to 0.90" | `from` → the superseded side. The `to 0.90` half matches, and passes. |
| "the drawdown limit **from** 15% to 20%" | same; `to 20%` matches and passes |
| "**quoted** the luck bar **as** 0.95" | `as` → a quotation of another document |
| "clears the luck bar **by** 0.016" | `by` → a margin, not a bar |
| "**within** 0.03 of the bar" | number precedes the noun; `of` → a margin |

This is what replaces a historical-words blacklist. A blacklist is itself a loophole — anyone can
type the escape word — whereas these are the ordinary grammar of superseding, and they are the
prose analogue of `_code_spans()`: both say *this number is quoted, not asserted*.

Routing a bare `bar`/`limit` ("our limit is 15%") to the right constant is done **by the number's
form**: a percentage is the drawdown bar, a bare decimal is the luck bar. That is how the prose
itself reads throughout the corpus, and it is why an unqualified sentence can be swept at all.

### Measured behaviour

Against all 27 committed insights:

- **#27 (newest synthesis, in scope): 5 matches, all correct, zero false positives.** Every trap
  listed above is correctly skipped. #27 needs no rewrite.
- **#21: `require 0.95` → stale, and `past our 15% limit` → stale.** The guard catches the exact
  sentence that contradicted the gate panel on prod, on both bars.
- #10, #15, #18 flag too, and are out of scope under the newest-synthesis rule.

### Why a non-vacuity pin is required

A guard scoped to "the newest row" is **untestable from live data alone**, because today the
newest row is correct — the test passes whether the matcher works or matches nothing. That is
precisely the failure mode this card is about, one level up again.

So a second test pins the matcher against insight **#21's committed text** and asserts it still
produces a hit. #21 is permanent (append-only table, triggers refusing `UPDATE`/`DELETE`) and is
the exact text that caused the bug, so it is the right fixture. If a future edit narrows the
matcher into uselessness, that test fails loudly instead of the guard going quietly green.

### The selection mirror

`overview.ts` picks the headline with `newest(snap.insights.filter(i => i.kind === 'synthesis'))`.
If the page ever headlines something else, the Python guard would be guarding a row nobody sees.
Pinned by reading `overview.ts` and asserting the selection is still that — the same mirror
technique as `test_the_web_mirrors_the_engines_luck_label_prefix`, for the same reason.

### Source of the data

`store.connect_readonly(store.COMMITTED_DB)`, as
`test_the_committed_snapshot_is_the_export_of_the_committed_database` already does.
`COMMITTED_DB` rather than `DB_PATH`, because the guard is about what ships to the page, and in a
swarm worktree `SEER_LAB_DB` points elsewhere. Reading the database rather than `web/data/lab.json`
is equivalent and already pinned: that existing invariant test asserts the two are byte-identical.

## Ambiguity calls recorded

1. **The prose matcher is not applied to the ten `SCANNED` documents.** The card scopes this to
   the journal; widening the docs sweep to plain-English bar statements is a larger change with
   its own false-positive surface. Narrow reading taken. The wider reading — one matcher over
   everything — is a reasonable follow-up card and is not foreclosed by anything here.
2. **The phase-7 self-pinning risk is deliberately not addressed.** The card calls it "worth
   considering in the same pass". Considered: all three label-mirror pins live in files phase 7
   owns, so a future phase could change a label and "fix" the failures by editing the pins. There
   is no mechanical answer to that *inside* a test suite — a test cannot stop itself being edited.
   The one thing in scope was done instead: the new guard compares against `store.DSR_MIN` and
   `tuning.MAX_DRAWDOWN`, never a typed literal, so it cannot be "fixed" by retyping a number.

## Steps

1. Extend `engine/tests/test_lab_gate_wording.py`: the prose matcher (`PROSE_BAR`, routing, the
   shared `_code_spans()` exemption), the newest-synthesis guard, the non-vacuity pin against
   insight #21, the `overview.ts` selection mirror.
2. Module docstring: record the division of labour between the two matchers — technical idiom vs
   owner-facing prose — adjacent in one file, so an edit to one is made in sight of the other.
3. Gate: the repo's CI (`.github/workflows/engine-ci.yml`) — ruff, then full pytest, then the web
   job's `tsc --noEmit` and `vitest run`.

## Risks

- **The matcher is prose-shaped, so it will meet sentences nobody anticipated.** Mitigated by
  scoping to one row and by the measured zero-false-positive result on the only in-scope row;
  a future false positive is a one-line fix to `REL` or the noun set, not a redesign.
- **Routing by number form** (percent → drawdown, decimal → luck) holds across the whole corpus
  today. A synthesis writing the drawdown bar as `0.20` would route to the luck bar and flag.
  Accepted: that sentence does not exist, and a false flag is loud and cheap, unlike a silent pass.
