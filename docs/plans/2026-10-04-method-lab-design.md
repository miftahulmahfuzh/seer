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
