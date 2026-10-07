# Method lab — design

Status: validated in brainstorming, 2026-10-04.

**Goal.** Keep searching for a strategy that beats SPY under design §1, with no end date, without
fooling ourselves. One `/explore-and-experiment-new-method` run explores one idea end to end and
logs it to a central, append-only lab database. Iron rule: we never stop trying; every run queues
at least one next idea.

**The risk is overfitting, not running out of ideas.** Thousands of trials on one dataset will
produce lucky winners. The lab counts every trial ever run and deflates each result by that
count (deflated Sharpe ratio), and the untouched test window (2015-10-19 → data end) is spent
one counted look at a time.

Owner decisions (2026-10-04): tracker = SQLite committed in the repo; promotion = luck-check then
one test-window look; scope = one idea with 1–6 fixed variants per run.

## 1. Lab database — `lab/lab.sqlite` (committed)

Accessed only through `seer_engine.lab.store` (stdlib `sqlite3`).

- **`methods`**: one row per idea. `id` (`M0001`…), `name`, `family` (free text), `parent_id`
  (variation of), `source_kind` (`paper`/`blog`/`github`/`knowledge`/`variation`/`backlog`/`seed`),
  `source_ref`, `hypothesis` (written before the run), `status`, `analysis` (markdown, appended),
  `verdict`, `created`, `updated`.
  Status moves forward only: `idea` → `registered` → `ran` → `rejected` | `dev-eligible` →
  `promoted` → `test-passed` | `test-failed` → `paper`. Side exit: `blocked-data` (needs data
  the store does not hold).
- **`trials`**: one row per backtest; this table is the multiple-testing count. Method, candidate
  id and digest, params, rules id, window (`dev`/`test`), start, end, store fingerprint, git sha,
  run time, metrics (return, CAGR, max DD, PF, trades, Sharpe, exposure, turnover, worst year,
  SPY TR return, MAR), failed conditions, eligible, DSR, `n_trials_at_run`, month-end equity
  curve. Append-only, enforced by triggers. At most one `test` trial per digest.
- **`ideas_seen`**: dedupe index of explored sources/fingerprints.
- **Seed:** P7a's 54 candidates as trials 1–54; A, A2 and B as historical methods.
- **View:** `python -m seer_engine lab export` → gitignored `lab/lab.xlsx` (one sheet per table
  plus a leaderboard by MAR); `sqlite3 lab/lab.sqlite` for queries.

## 2. Plug-and-play

- A method is one file, `engine/src/seer_engine/lab/methods/mNNNN_<slug>.py`, exporting
  `METHOD = Method(...)` with 1–6 fixed `Candidate`s. New signal logic is an `Allocator` in the
  same file, or an existing allocator with new params. `TradeRules`, the book engine, costs,
  dividends and whole-share sizing are reused unchanged.
- `Candidate` ids accept lab ids (`M0007-V2`) and lab families. The P7a registry and its cap
  stay frozen as a historical record.
- `python -m seer_engine lab run M0007`: refuses an uncommitted method file (the commit is the
  pre-registration), refuses a digest that already has a trial, runs each candidate through
  `dev.run_candidate` on the research store (dev window ≤ 2015-10-16, D9 guard intact), computes
  DSR with lab-wide N, inserts trials, advances the method status, prints a summary.
- A parametrized test runs the `allocatorkit` contract checks over every lab method.
- Ideas needing data the store lacks (fundamentals, intraday, options, sentiment) are logged as
  `blocked-data` with what is missing.
- ML methods get an expanding-window refit wrapper, built when the first one needs it.

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

## 4. The skill

`.claude/skills/explore-and-experiment-new-method/SKILL.md`. One run:

1. Preflight: clean `main`, pull, engine venv, research store, lock file.
2. `lab status`: N, test looks used, families tried, near-misses, backlog, blocked-data.
3. Choose one idea (variation of a near-miss, web research, knowledge, or backlog), testable and
   not in `ideas_seen`; write the hypothesis and the expected failure mode first.
4. Register: method file (+ allocator, + tests); commit = pre-registration.
5. `lab run`.
6. Analysis + verdict into the database.
7. Queue at least one next idea.
8. Promote if dev-eligible.
9. Commit + push; short report.

Guardrails: never edit `DEV_END`, design §1/§5, the paper roster or the P7a registry; never
delete or rewrite a trial; never touch the test window outside step 8; never tune after seeing a
result within a method (tuning is a new variation method with new trials). Nonstop:
`/loop /explore-and-experiment-new-method`.

## 5. Tests and build order

Tests: store (schema, append-only triggers, forward-only status, one test look per digest,
export), runner (dirty-tree and duplicate refusals, D9, DSR with lab-wide N, rows), method
contract test, seed import digests.

Build: (1) store, (2) `Method` + discovery + ids + contract test, (3) `lab` CLI
(`run`/`status`/`note`/`idea`/`export`), (4) seed import and committed DB, (5) `SKILL.md`,
(6) a first real run. `lab test` and the test-window store are specified here and built on first
promotion.

## 6. Revision 2026-10-04 (owner): no human in the loop, Sera, the journal

- **No human in the loop.** Both skills decide everything themselves and never ask: idea,
  variants, promotion (they build `lab test` and the test-window store on first need) and, on a
  test pass, a paper-roster entry with its own clock. Assumptions are written into the analysis.
  Design §1 and the no-real-money rule are unchanged.
- **`/sera-the-explorer <num-methods>`** coordinates up to 4 explore sessions at once, each in its
  own worktree (`explore/MNNNN`) and tmux window via `swarm.py launch`. It reserves diverse ideas
  as `idea` rows, refills slots as children finish, verifies each child, promotes serially,
  cleans up and writes a batch synthesis. Children share the main checkout's database through
  `SEER_LAB_DB` and commit only their method files; only Sera commits `lab/lab.sqlite`, through
  `lab stage` (git add under the write lock). `BEGIN IMMEDIATE` makes id allocation and the
  lab-wide N atomic across sessions.
- **`insights`**: an append-only journal (`observation`, `hypothesis`, `data-wish`,
  `feature-wish`, `risk`), the food-for-thought record that seertrade.site/sera shows.

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
