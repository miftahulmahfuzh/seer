# Code Analysis: the handover's four open questions (delisting stress test, go-live item 1, MOM-FR, roster churn)

**Type:** Feature Implementation (a diagnostic harness) + Feature Update (two policy documents)
**Date:** 2026-10-07 17:05:15
**Session ID:** 20261007-170515-0CU0
**Plan:** `DELISTING_STRESS_ROSTER_RULES_PLAN.md` (5 phases)
**Worktree:** `/home/miftah/.worktrees/seer/delisting-stress-roster-rules`, branch `feature/delisting-stress-roster-rules` (base `origin/main` @ `3683d7b`)

---

## User Input

### Original User Request

```
/analyze docs/handover/2026-10-07-roster-first-night-and-survivorship.md
```

The target is a handover document, and the document names its own deliverable: §5, "Questions
the analysis must settle". Its preamble is the instruction — *"Pass this file straight to
`/analyze` in a fresh session and read all of it first… This exists so a fresh session can pick
up the open threads in §5 without re-deriving the state."* §5 is therefore the specification,
and §§0–4 and 6–7 are the state it says not to re-derive.

The four questions, verbatim from §5:

> **Q1 — the delisting stress test (the main open item).** §3 is an absence of evidence from an
> era contrast that is confounded with regime. The test that isolates the mechanism has not been
> run: inject synthetic delistings into the ranking universe at the historical rate and solve for
> the **break-even delisting return** — how bad the assumed loss must be before the edge vanishes
> — then judge whether that number is plausible. Framing it as break-even avoids having to guess
> a delisting return, which is the part no free source can give us. Open: where it lives (a lab
> method would spend a trial and move N, which is probably wrong for a diagnostic), and whether it
> needs the position level or can be approximated from the recorded curves.
>
> **Q2 — is go-live item 1 calibrated?** Item 1 asks for ≥ 3 months **and** ≥ 100 closed trades.
> Trades bind, not months, and by a wide margin: [RMW-FR 80.3 trades/yr → 14.9 months; RAW-FR
> 80.7 → 14.9; MOM-FR 58.0 → 20.7; MVW-FR 61.8 → 19.4]. So "3 months of paper" is really 15–21
> months, and every future roster swap resets that clock for the entry it replaces. This is the
> owner's dial (`backtest/dev.py:86`, `_MIN_TRADES = 100`), not the analysis's — but the owner may
> not realise the 3 months is decorative, and should be told before the clock has been running a
> year.
>
> **Q3 — is `MOM-FR` the weakest of the five?** Its era edge is +6.2 / +8.2 / **−2.3**, the least
> stable of the four quant entries, and it has the slowest path to a verdict (20.7 months). It was
> admitted as F4's bet inside the drawdown bar. Worth asking whether a better occupant of that slot
> exists in the lab, **but not before** reading the warning in Q4.
>
> **Q4 — do not churn the roster on lab results.** Every swap restarts a ~15-month clock (Q2), and
> DSR falls monotonically as Sera explores (§2), so "it no longer passes the luck test" will become
> true of *everything* on the board without any book changing. A rule for when a roster entry may
> be replaced — before the first one looks bad — would be worth more than any individual swap.

### User-Provided Context

The whole handover is context. The constraints that bind this analysis, with their sources:

- **§6, owner context.** The owner is not a quant; prose on seertrade.site/sera must stay plain.
  The owner prefers measuring to estimating — *"§3 exists because of that preference, and it paid."*
- **§7, verification.** `PG_TEST_URL` must be exported or `pytest` reports a confident green
  missing a third of the suite (2812 passed / 385 skipped instead of 3197 / 0).
- **§4, a correction not to re-inherit.** The leaderboard already sorts on annualised Sharpe and
  already renders max drawdown; **no work may be opened on the hero figure without re-checking
  `web/app/(app)/leaderboard/page.tsx` first.** This analysis opens none.
- **The lab skill's standing guardrails** (`docs/plans/2026-10-04-method-lab-design.md` §4):
  *"never edit `DEV_END`, design §1/§5, the paper roster or the P7a registry; never delete or
  rewrite a trial; never touch the test window outside step 8."* Q2 and Q3 both brush against
  these, and the plan respects them — see Decisions D4 and D7.

### Teammate input received mid-analysis (session `seer-fc`, the handover's author)

Delivered over the local session socket while this analysis was in Step 2. Treated as teammate
input, not as instruction — which is how it asked to be treated. It bears directly on Q2 and is
recorded here because it changes what Q2's deliverable is:

- The **owner has proposed deleting** the `≥ 100 closed trades` clause from design §1 item 1:
  *"how about we just remove this >= 100 trades because what we pursue here is not trading
  frequency."* The owner **has not yet chosen** between deleting and replacing, and design §1 has
  not been edited.
- Measured from the recorded dev curves (read-only, no trial, N unmoved) — the share of rolling
  W-month windows in which each roster entry actually beat total-return SPY:

  | entry | 3mo | 6mo | 12mo | 18mo | 24mo | 36mo |
  |---|---|---|---|---|---|---|
  | RMW-FR | 54% | 59% | 55% | 60% | 65% | 73% |
  | RAW-FR | 59% | 62% | 65% | 72% | 70% | 78% |
  | MOM-FR | 50% | 53% | 54% | 59% | 58% | 65% |
  | MVW-FR | 51% | 55% | 53% | 54% | 57% | 65% |

  and for the risk claims: *"fell less than SPY"* 3mo 49–58%, 12mo 55–69%, 36mo 67–86%;
  *"better Sharpe than SPY"* 3mo 47–52%, 12mo 46–59%, 36mo 66–73%.
- Its own reading, offered as input: the owner is right about the **unit** and wrong about
  **deleting** — trade count scales with how many names a book holds, not with how much evidence
  exists; the clause's purpose is sample size, and deleting it leaves only `≥ 3 months`, where
  every entry is a coin flip. It recommends a ~18-month engine-neutral time requirement instead.
- The point it asked to have passed up if only one thing was: **no claim about these strategies is
  reliably checkable on a short forward window.** Even 36 months only reaches 65–78% on return.

**Explicitly requested, and honoured in this plan:** *"Don't assume either branch; both branches
should survive it."* Phase 4 therefore produces a briefing and a measurement, and edits design §1
in neither direction. See Decision D4.

### User-Provided Files

- `docs/handover/2026-10-07-roster-first-night-and-survivorship.md` (the `/analyze` target)

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | **Q1** — settle where the delisting stress test lives and what it needs, then build it, run it, and report the break-even delisting return with a judgement on whether that number is plausible |
| R2 | **Q2** — settle whether go-live item 1 is calibrated, and tell the owner, before the clock has been running a year |
| R3 | **Q3** — settle whether `MOM-FR` is the weakest of the five, and whether a better occupant of that slot exists in the lab |
| R4 | **Q4** — write the rule for when a roster entry may be replaced, before the first one looks bad |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement.** Four open threads, two of them diagnostics that need code and
two of them policies that need documents. They are not equally sized and they are not independent:
§5 states one ordering constraint in its own prose — Q3 is *"worth asking… **but not before**
reading the warning in Q4"* — and that is a dependency, not a suggestion.

**R1 (Q1)** is the only one that needs new engine-adjacent code. §3 and design §12 both record the
same limitation in the same words: the era contrast is confounded with regime, so it is *"evidence
against the simple bias story, never proof the hole is harmless."* The test that would isolate the
mechanism injects delistings the backtest never saw and asks how bad they must be before the edge
disappears. The break-even framing is what makes it answerable without a paid feed: the unknown
(the delisting return) becomes the output instead of an input.

**R2 (Q2)** is a calibration question whose answer is already known and whose deliverable is
therefore a briefing, not a change. Item 1 asks for `≥ 3 months` **and** `≥ 100 closed trades`;
the second binds at 15–21 months and the first is decorative. The owner has since proposed
deleting the trade clause outright, and has not decided. The work is to put the measurement in
front of the owner — including the teammate's rolling-window numbers, which say something larger
and worse than Q2 asked about — and to leave the dial where it is.

**R3 (Q3)** asks a comparative question against the lab. Measured below: **26** of the 110
recorded dev trials clear all five owner conditions at today's bars, and `M0002-REL-85` (MOM-FR)
ranks 12th among them by DSR and 8th by MAR. So better-scoring occupants demonstrably exist. The
question is therefore not "does one exist" but "does that justify a swap", and §5 says that may
not be answered before R4 exists.

**R4 (Q4)** asks for a replacement rule written before the first entry looks bad — precisely so
the rule is not written to justify a swap somebody already wants. Two mechanisms make it urgent
and both are already measured: a swap restarts a ~15-month clock (Q2), and DSR falls monotonically
as Sera explores (§2; lab design §7.3 puts `M0022-W-TV16` below the bar at N = 143, about a day and
a half of exploration).

**Success Criteria.**

- R1: a committed, read-only, repeatable harness that records no trial and does not move the
  lab's N; a break-even delisting return per roster entry; and a stated judgement on plausibility,
  recorded where design §12 said it would be recorded.
- R2: the owner has the number and the fork in front of them, in plain language, and design §1 is
  unedited.
- R3: a stated verdict on MOM-FR with the lab evidence behind it, decided *under* R4's rule.
- R4: a rule that exists and names its own trigger conditions, committed before any swap.

**Key Considerations.**

- **Nothing here may spend a test-window look.** §7: *"0 test-window looks used"*, and the test
  window is still completely unspent. The stress test runs on the dev-window store only.
- **Nothing here may move the lab's N.** A recorded trial is the multiple-testing count; a
  diagnostic that inserts one makes every future candidate pay for a question that was not a
  search. `survivorship_coverage.py` is the precedent and it records nothing.
- **Nothing here may change `config_digest`.** §3's own reason for not buying a feed is that
  rebuilding `engine/.research` *"changes every `config_digest`, resetting all 110 trials and
  their DSRs."* The stress test must perturb an in-memory `Market`, never the store on disk.
- **Costs are not an obstacle, which was not obvious before it was measured.** One full
  dev-window `run_candidate` is 2–3 seconds (below). A Monte Carlo over four entries, a grid of
  assumed delisting returns and ~100 seeds is hours, not days.

**Assumptions.** Stated here, planned against, and re-stated at the points in the plan that rest
on them:

1. The dev-window store on disk is the one the 110 trials were run against. Its fingerprint is
   checked by `load_store`, so a drift is an error rather than a silent difference.
2. A symbol's disappearance from `market.history` is an adequate model of a delisting, because
   that is exactly what the engine already does with one (`book_runner` step 4, verified below).
3. The historical hazard measured from the store's own membership is the right injection rate.
   Measured below as 4.0%/yr (unserved exits) against a 5.1%/yr all-exit rate.

---

## Analysis Scope

### Explicitly Mentioned Files

- `docs/handover/2026-10-07-roster-first-night-and-survivorship.md`

### Discovered Related Files

Reached by following the handover's own `file:line` citations and then the call chains out of them:

- `engine/scripts/survivorship_coverage.py` — the precedent harness (§3's reproduction command)
- `engine/src/seer_engine/backtest/dev.py` — `run_candidate`, `make_row`, `_MIN_TRADES`, `deflated_sharpe`
- `engine/src/seer_engine/backtest/book_runner.py` — `run_book`, the force-close path
- `engine/src/seer_engine/sim/book.py` — `close_book_unpriced`, `step_book`
- `engine/src/seer_engine/backtest/market.py` — `Market`, `Membership`
- `engine/src/seer_engine/research.py` — `load_store`, `ResearchData`, the fingerprint
- `engine/src/seer_engine/lab/store.py` — `DSR_MIN`, `DSR_POLICY`, `verdict`, `owner_failures`, `gate`
- `engine/src/seer_engine/lab/runner.py` — what records a trial, and what does not
- `engine/src/seer_engine/lab/npolicy.py` — the three N policies
- `engine/src/seer_engine/lab/method.py` — `discover`, `config_digest`
- `engine/src/seer_engine/paper/roster.py` — `RESOLVER`, `LAB_PROVENANCE`, `SEED_ROWS`, `spec_digest`
- `engine/src/seer_engine/paper/compare.py` — `MIN_COMMON_SESSIONS`, the Sharpe ranking
- `web/lib/golive.ts`, `web/lib/metrics.ts` — the six-rule go-live checklist
- `docs/plans/2026-10-03-seer-design.md` — §1 (the five conditions), §11, §12
- `docs/plans/2026-10-04-method-lab-design.md` — §3 (promotion), §4 (guardrails), §7
- `docs/plans/2026-10-05-delisted-and-fundamentals.md` — the 133-symbol diagnostic, the recycled-ticker bug

---

## Current Dataflow

### Entry Point: `engine/scripts/survivorship_coverage.py` — the precedent

**Location:** `engine/scripts/survivorship_coverage.py:1`
**Trigger:** `engine/.venv/bin/python engine/scripts/survivorship_coverage.py`
**Input:** none. It opens `engine/.research` and `lab/lab.sqlite` itself.
**Validation:** `load_store` verifies every file's sha256 and the manifest fingerprint.
**State changes:** **none.** `sqlite3.connect(f"file:{LAB}?mode=ro", uri=True)` — read-only by URI.
**Why it matters here:** its module docstring states the contract R1's harness must copy —
*"Read-only: it loads the research store and the lab database, writes nothing, records no trial,
and does not move the lab's N."* It achieves that by slicing `trials.curve_json` rather than
re-running. R1 cannot: see **Exit Points** below.

### Entry Point: `dev.run_candidate` — the only way to produce a new curve

**Location:** `engine/src/seer_engine/backtest/dev.py:398` (`run_candidate`)
**Trigger:** a direct Python call. `lab run` reaches it through `dev.run_registry`.
**Input:** `(market, dividends, spy_dividends, candidate, *, prepared, window=DEV_WINDOW)`
**Validation:** `_check_market` and `_check_dividends` raise `DevWindowError` for any bar, FX row
or dividend after `window.end` — the D9 guard, absolute by default.
**Next step:** `_run` → `book_runner.run_rules` → `run_book`.
**The fact that decides R1's shape:** `run_candidate` is **pure**. It touches no database, writes
no row, and has no idea the lab exists. `tests/test_strategy_purity.py` globs the module to keep
it that way. **A trial is recorded by `lab/runner.py`, not by `dev.py`** — `runner.run_method`
calls `store.insert_trials` after the run. So calling `run_candidate` directly spends no trial and
moves no N, which resolves the first half of Q1's open question.

### Processing Chain — how a delisting already behaves

1. **Ranking universe is formed.**
   - **Location:** `engine/src/seer_engine/backtest/book_runner.py:290`
   - `members = market.membership.members_on(data_date)`, handed to
     `allocator.targets_prepared(prepared, members, data_date, mine, params)`.
   - The allocator intersects `members` with the symbols it actually has bars for. **A member with
     no bars is silently absent from the ranking** — which is precisely the 522-symbol hole, and
     precisely the lever a synthetic injection pulls.

2. **A held symbol whose bars end is force-closed at its mark.**
   - **Location:** `engine/src/seer_engine/backtest/book_runner.py:317-326`
   - `gone = [p.symbol for p in book.positions if _gone(market, p.symbol, session)]`, then
     `close_book_unpriced(book, gone, rules)`.
   - **Location:** `engine/src/seer_engine/sim/book.py:742-785`
   - `_close_out(p, when, p.mark, "forced", p.days_held, rules, "forced")` — sold **at its mark**,
     reason `"forced"`, `exit_date = book.last_session`.
   - **This is the single most important fact for R1.** The engine already models a delisting, and
     it models it at a **delisting return of exactly 0%**: the position is liquidated at the last
     price anyone saw. Every recorded backtest therefore assumes that a company that stops being
     priced is sold whole at its last close. That assumption is invisible today because no symbol
     in the store disappears mid-window; it becomes the thing under test the moment one does.

3. **The injection point follows from (2) without an engine change.** Truncating a symbol's
   `History` at a chosen death date and rewriting that last bar to `close × (1 + r)` makes the
   engine do the rest: the name leaves the ranking universe after the truncation (step 1), and the
   position force-closes at the rewritten mark (step 2). `Market` is a frozen dataclass with a
   `history` mapping, so the perturbation is a rebuild of one dict — no edit to `sim/`, no edit to
   `backtest/`, and therefore no risk to the 110 recorded trials.

### Data Persistence

**The research store:** `engine/.research/` — `bars.csv` 129 MB, `dividends.csv`, `fx.csv`,
`unserved.csv` (523 lines = 522 symbols + header), `fundamentals.csv`, `manifest.json`.
`load_store` verifies per-file sha256 **and** the fingerprint. Measured load time: **11.3 s**.
R1 writes nothing here. Doing so would change every `config_digest` (§3's stated reason for not
buying a feed) and invalidate all 110 trials.

**The lab database:** `lab/lab.sqlite`, committed, append-only. `trials` has triggers refusing
every UPDATE and DELETE, and `UNIQUE(config_digest, window)`. 110 dev trials, 0 test trials.
R1 opens it read-only, if at all.

### Exit Points

- `survivorship_coverage.py` prints two tables to stdout; design §12 holds the recorded copy.
- `run_candidate` returns `(RunResult | BookResult, DevRow)` — in memory, nothing persisted.
- **What `trials.curve_json` can and cannot answer.** It is a **month-end equity curve** and
  nothing else: `commands/backtest_dev.month_end_curve` produces it, and `survivorship_coverage.py`
  slices it by era, which is all an equity curve supports. It carries no positions, no symbols and
  no trades. A delisting injection changes *which names are held*, so the perturbed equity path
  cannot be derived from the unperturbed one. **Q1's second open question therefore resolves to
  "position level" — the backtest must be re-run.** The measurement below is what makes that
  affordable rather than prohibitive.

---

## Key Data Structures

### Struct: `Market`
**Location:** `engine/src/seer_engine/backtest/market.py:105`
**Fields:** `history: Mapping[str, History]`, `membership: Membership`, `fx`, `fundamentals`
**Used in:** `run_book` (`book_runner.py:290`, `:303`), `candidate_window` (`dev.py:~300`)
**Why it matters:** frozen, and `dataclasses.replace` is already used on it inside `dev._run` to
swap `fx` for an early window. The same move swaps `history` for a perturbed one. The precedent
for perturbing a `Market` by `replace` is therefore already in the tree, in the module R1 calls.

### Struct: `Membership`
**Location:** `engine/src/seer_engine/backtest/market.py:56`
**Fields:** `intervals: tuple[tuple[str, date, date | None], ...]`, plus swept `_breaks`/`_segments`
**Used in:** `members_on(d)` — one bisect per decision session.
**Why it matters:** `intervals` is where the historical exit dates live, and therefore where the
injection's hazard rate and death-date distribution are measured from. `end` is **exclusive** and
`None` means still a member.

### Struct: `DevRow`
**Location:** `engine/src/seer_engine/backtest/dev.py:~218`
**Fields:** `candidate, start, end, stats, spy_tr, spy_price, beats_spy, mar, eligible, failed, window`
**Used in:** `make_row`, `finalists`, and `lab/runner.py` when it builds a `TrialRow`.
**Why it matters:** it is the comparable unit. A stressed run and an unstressed run both produce
one, and `row.stats.metrics` carries `cagr`, `max_drawdown`, `profit_factor`, `trades` — every
number the break-even solver needs, and `spy_tr` to measure the edge against.

### Struct: `TrialRow` columns (`trials`)
**Location:** `lab/lab.sqlite`, schema in `engine/src/seer_engine/lab/store.py`
**Columns (verified by query):** `n, method_id, candidate_id, config_digest, config_text,
rules_id, allocator_id, window, start, end, store_fingerprint, git_sha, run_at, total_return,
cagr, max_drawdown, profit_factor, trades, sharpe, exposure, turnover, worst_year,
worst_year_return, spy_tr_return, spy_tr_cagr, mar, failed, eligible, dsr, n_trials_at_run,
curve_json`
**Why it matters:** `curve_json` is the only path-like column, and it is month-end equity. There
is no position or trade column. This is the measured basis for the "position level" finding above.

---

## Dependencies

### Configuration

- `seer_engine.config.REPO_ROOT` — resolves `engine/.research` and `lab/lab.sqlite`.
- `lab.store.DSR_MIN = 0.90`, `lab.store.DSR_POLICY = "all-trials"` (N = 110 today).
- `backtest.tuning.MAX_DRAWDOWN = 0.20`, `MIN_PROFIT_FACTOR = 1.3`, `dev._MIN_TRADES = 100`.
- `SEER_LAB_DB` — parallel explorer sessions share the main checkout's lab database through it.
  **A worktree session that reads `lab/lab.sqlite` by `config.REPO_ROOT` reads its own checkout's
  copy**, which is what a read-only diagnostic wants.

### Environment

- `PG_TEST_URL` — **required for the engine test suite.** Without it: 2812 passed, 385 skipped.
  With it: 3197 passed, 0 skipped (§7). Every phase's verification command exports it.
- `engine/.venv` — the engine virtualenv. The research store is gitignored and lives in the
  **main checkout**, not in a worktree.

### External Services

None. Every phase here is offline: the research store is local, the lab database is committed,
and no phase fetches a price.

---

## Measurements taken during this analysis

Read-only, no trial recorded, no test-window look spent, the lab's N unmoved at 110. These exist
because the owner prefers measuring to estimating (§6) and because three of the four questions
turn on a number that was unknown when the handover was written.

### M1 — one dev-window run costs 2–3 seconds

```
load_store: 11.3s  symbols=539
M0007-N20-RAW: prepare 0.2s  run 2.3s  start=1996-01-03 end=2015-10-16 trades=1596 cagr=0.1505 dd=0.1959
M0022-W-TV16: prepare 0.2s  run 3.3s  start=1996-01-03 end=2015-10-16 trades=1589 cagr=0.1168 dd=0.1431
```

The store loads once per process at 11.3 s; each additional candidate run is 2–3 s. **This is what
makes R1 a Monte Carlo rather than a thought experiment.** 4 entries × 8 assumed delisting returns
× 100 seeds = 3,200 runs ≈ 2.7 hours single-threaded, and the runs are embarrassingly parallel.

It also reproduces the handover's own numbers exactly — `M0007-N20-RAW` at `dd=0.1959` is §2's
19.6%, and `M0022-W-TV16` at `cagr=0.1168` is design §11's book. The store on disk is the one the
110 trials were run against.

### M2 — the historical delisting hazard, from the store's own membership

```
ever-members: 1041  served: 519  unserved: 522
symbols whose last membership ended inside the window: 514
  of those, unserved (no bars at all):   404
  of those, served (we have their bars): 110
mean members on a mid-year date: 510
window years: 19.8  total exits: 514  exits/yr: 26.0
approx member-years: 10096
  annual exit hazard:                                     5.091%
  annual UNSERVED-exit hazard (the names a free feed drops): 4.001%
unserved members with no in-window exit: 118
Q-suffix (bankruptcy) unserved: 32
```

Exits by year: 1996:17, 1997:27, 1998:32, 1999:37, 2000:49, 2001:24, 2002:22, 2003:9, 2004:17,
2005:14, 2006:31, 2007:43, 2008:38, 2009:27, 2010:19, 2011:22, 2012:26, 2013:24, 2014:15, 2015:21.

**The hole decomposes into two populations, and only one of them is simulable.** This was not
visible in §3, which counted the 522 as one number:

- **404 names left the index inside the window and have no bars.** These are the survivorship case
  proper: a strategy could have bought one, held it down, and taken a delisting return the backtest
  never charged. **This is what R1 injects**, at the measured 4.0%/yr.
- **118 names were still index members at `DEV_END` and have no bars at all.** They never died
  inside the window; they died afterwards and a free feed dropped them retroactively. Their absence
  is not survivorship flattery — it is a thinner ranking pool for 20 years. **No delisting injection
  can model them**, because the missing thing is a price path, not a death.

The exit count also rises in exactly the years a reader would expect (49 in 2000, 43 in 2007,
38 in 2008), which is a sanity check on the membership data rather than a finding.

### M3 — 26 candidates clear all five owner conditions at today's bars

Re-judged through `store.owner_failures` and `store.verdict` at the live gate (N = 110,
policy `all-trials`, `DSR_MIN` 0.90). The recorded `failed` strings are **not** what this reads:
all 110 rows carry the old `"DSR >= 0.95"` label and the pre-2026-10-07 drawdown bar, so the four
threshold conditions are recomputed from the recorded columns against the live constants.

| candidate | DSR @ N=110 | MAR | CAGR | max DD | trades | eligible |
|---|---|---|---|---|---|---|
| M0022-W-TV16 **(RMW-FR)** | 0.9156 | 0.816 | 11.68% | 14.31% | 1589 | **yes** |
| M0020-W-NOSTOP | 0.9127 | 0.793 | 15.27% | 19.27% | 1620 | **yes** |
| M0022-W-TV14 | 0.9122 | 0.857 | 10.59% | 12.36% | 1592 | **yes** |
| M0007-N20-RAW **(RAW-FR)** | 0.8985 | 0.768 | 15.05% | 19.59% | 1596 | no |
| M0011-RAW20-TV14-N21 | 0.8844 | 0.763 | 10.80% | 14.15% | 1588 | no |
| M0020-W-S20 | 0.8764 | 0.750 | 14.16% | 18.88% | 1744 | no |
| M0019-TV14N21-S20 | 0.8684 | 0.791 | 9.89% | 12.50% | 1657 | no |
| … 4 more between 0.83 and 0.86 … | | | | | | |
| **M0002-REL-85 (MOM-FR)** | **0.8278** | **0.684** | 12.56% | 18.37% | 1148 | no |
| … 12 more below … | | | | | | |
| M0008-N30-C07 **(MVW-FR)** | 0.7802 | 0.564 | 11.27% | 19.97% | 1223 | no |
| F9-SPY200M70-MOM30 | *NULL* | 0.635 | 12.22% | 19.24% | 635 | no |

**MOM-FR ranks 12th of 26 by DSR and 8th by MAR** (seven candidates sit strictly above it on MAR). Better-scoring occupants of its slot
demonstrably exist, and two of them (`M0020-W-NOSTOP`, `M0022-W-TV14`) are *fully dev-eligible*
today while MOM-FR is not. That is the evidence R3 needs — and it is also exactly the evidence Q4
warns is about to become available for every entry on the board, which is why the plan orders R4
before R3.

**One thing the table does not say, and R3's phase must weigh.** `M0020-W-NOSTOP` and
`M0022-W-TV14` are the weekly-brake family — the family RMW-FR already occupies. MOM-FR is the
roster's only regime-scaled total-return momentum book. A swap on DSR alone would raise the
roster's average lab score and collapse its family diversity at the same time, which is a cost no
column above prices.

---

## Reference List

Every site that the four requirements touch. R1 adds files rather than changing them; R2 and R4
add documents; R3 edits at most one roster provenance line, and only if its verdict is "swap".

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `survivorship_coverage.main` | `engine/scripts/survivorship_coverage.py:76` | def · precedent | `engine/scripts` |
| `ERAS`, `ROSTER` | `engine/scripts/survivorship_coverage.py:40,47` | config | `engine/scripts` |
| `spy_total_return` | `engine/scripts/survivorship_coverage.py:51` | def · reusable | `engine/scripts` |
| `cagr_and_fall` | `engine/scripts/survivorship_coverage.py:68` | def · reusable | `engine/scripts` |
| `load_store` | `engine/src/seer_engine/research.py` | call | `seer_engine` |
| `ResearchData.unserved` | `engine/src/seer_engine/research.py:193` | field | `seer_engine` |
| `STORE_DIR` | `engine/src/seer_engine/research.py:73` | config | `seer_engine` |
| `run_candidate` | `engine/src/seer_engine/backtest/dev.py:398` | def · call | `backtest` |
| `make_row` | `engine/src/seer_engine/backtest/dev.py:~288` | def | `backtest` |
| `DEV_WINDOW`, `DEV_END` | `engine/src/seer_engine/backtest/dev.py:60,54` | config | `backtest` |
| `_MIN_TRADES = 100` | `engine/src/seer_engine/backtest/dev.py:86` | config · **R2's dial** | `backtest` |
| `FAILURE_LABELS` | `engine/src/seer_engine/backtest/dev.py:71` | config | `backtest` |
| `run_book` members lookup | `engine/src/seer_engine/backtest/book_runner.py:290` | call · **R1 injection point** | `backtest` |
| `_gone` / `close_book_unpriced` | `engine/src/seer_engine/backtest/book_runner.py:317` | call · **R1 injection point** | `backtest` |
| `close_book_unpriced` | `engine/src/seer_engine/sim/book.py:742` | def | `sim` |
| `Market.history` | `engine/src/seer_engine/backtest/market.py:105` | field · **R1 perturbs** | `backtest` |
| `Membership.intervals` | `engine/src/seer_engine/backtest/market.py:63` | field · **R1 reads** | `backtest` |
| `Membership.members_on` | `engine/src/seer_engine/backtest/market.py:98` | def | `backtest` |
| `tuning.MAX_DRAWDOWN` | `engine/src/seer_engine/backtest/tuning.py` | config | `backtest` |
| `store.DSR_MIN = 0.90` | `engine/src/seer_engine/lab/store.py:121` | config | `lab` |
| `store.DSR_POLICY` | `engine/src/seer_engine/lab/store.py:~175` | config | `lab` |
| `store.verdict` | `engine/src/seer_engine/lab/store.py:1176` | def · R3 reads | `lab` |
| `store.published_verdict` | `engine/src/seer_engine/lab/store.py:1243` | def · R3 reads | `lab` |
| `store.owner_failures` | `engine/src/seer_engine/lab/store.py:980` | def · R3 reads | `lab` |
| `store.gate` | `engine/src/seer_engine/lab/store.py:886` | def | `lab` |
| `store.insert_trials` | `engine/src/seer_engine/lab/store.py` | def · **R1 must NOT call** | `lab` |
| `runner.run_method` | `engine/src/seer_engine/lab/runner.py` | def · **R1 must NOT call** | `lab` |
| `npolicy.effective_n` | `engine/src/seer_engine/lab/npolicy.py:259` | def | `lab` |
| `method.discover` | `engine/src/seer_engine/lab/method.py:104` | def · R1 resolves candidates | `lab` |
| `RESOLVER` | `engine/src/seer_engine/paper/roster.py:351` | config | `paper` |
| `LAB_PROVENANCE` | `engine/src/seer_engine/paper/roster.py:393` | config · R3 may touch | `paper` |
| `SEED_ROWS` | `engine/src/seer_engine/paper/roster.py:732` | config · **R4 must NOT edit** | `paper` |
| `MAX_LOOKBACK_BARS` | `engine/src/seer_engine/paper/roster.py:997` | config | `paper` |
| `RAW_ID`/`MOM_ID`/`MVW_ID` | `engine/src/seer_engine/paper/roster.py:146-148` | config | `paper` |
| `MIN_COMMON_SESSIONS = 63` | `engine/src/seer_engine/paper/compare.py:61` | config · R2 context | `paper` |
| `checklist` (item 1) | `web/lib/metrics.ts:58-77` | def · **R2's surface** | `web` |
| `MAX_DRAWDOWN = 0.2` | `web/lib/golive.ts:21` | config | `web` |
| `rankCmp` | `web/app/(app)/leaderboard/view.ts:215-217` | def · §4 context | `web` |
| design §1 item 1 | `docs/plans/2026-10-03-seer-design.md:16-21` | doc · **R2's subject, NOT edited** | `docs` |
| design §12 | `docs/plans/2026-10-03-seer-design.md:167` | doc · **R1 extends** | `docs` |
| lab design §4 guardrails | `docs/plans/2026-10-04-method-lab-design.md:75` | doc · binds every phase | `docs` |
| lab design §7.3 (the ratchet) | `docs/plans/2026-10-04-method-lab-design.md:202` | doc · **R4's evidence** | `docs` |
| lab design §7.4 (paper vs lab) | `docs/plans/2026-10-04-method-lab-design.md:221` | doc · **R4 extends** | `docs` |
| delisted decision doc §2.6 | `docs/plans/2026-10-05-delisted-and-fundamentals.md` | doc · R1 context | `docs` |

---

## Impact Points (files that WILL need changes)

1. `engine/src/seer_engine/delisting.py` **(new)** — the hazard estimator and the `Market`
   perturbation. A module, not a script, because it needs unit tests. **Phase 1.**
2. `engine/scripts/delisting_stress.py` **(new)** — the Monte Carlo driver and the break-even
   solver, in `survivorship_coverage.py`'s shape and under its read-only contract. **Phase 1.**
3. `engine/tests/test_delisting.py` **(new)** — purity, hazard arithmetic, perturbation
   correctness, and the guard that the harness records no trial. **Phase 1.**
4. `docs/plans/2026-10-03-seer-design.md` — a new §13 holding the break-even result, in §12's
   voice. §12's last paragraph promises exactly this section. **Phase 2.** *(§1 is not touched.)*
5. `lab/lab.sqlite` — one `insights` row (`kind='risk'`) recording the stress-test finding.
   Append-only, no trial, N unmoved. **Phase 2.**
6. `docs/plans/2026-10-04-method-lab-design.md` — a new §8, the roster replacement rule,
   extending §7.4's paper-vs-lab divergence. **Phase 3.**
7. `docs/handover/2026-10-07-go-live-item-1-calibration.md` **(new)** — R2's briefing, both
   branches alive. **Phase 4.**
8. `docs/handover/2026-10-07-mom-fr-under-the-replacement-rule.md` **(new)** — R3's verdict,
   decided under phase 3's rule. **Phase 5.**
9. `engine/src/seer_engine/paper/roster.py` — **only if** phase 5's verdict is "swap", and then
   only `LAB_PROVENANCE`/`SEED_ROWS` under a new id with its own clock. On the evidence in M3 the
   expected verdict is "keep", so the expected edit is none. **Phase 5, conditional.**

**This document describes. The plan files prescribe.**
