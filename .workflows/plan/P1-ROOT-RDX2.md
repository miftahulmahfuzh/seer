> Adopted from `LAB_REALISTIC_GATE_PLAN.md` phase 3. Source: `.workflows/plan/lab-realistic-gate/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: `/redo-sera-experiments` — honest twins of named methods, as a batch

**Plan set:** `LAB_REALISTIC_GATE_PLAN.md`
**Analysis:** `20261008-135044-N7K3_code_analyzer.md`
**Satisfies:** R3 — a `/redo-sera-experiments <method-urls-or-ids>` skill that cleanly redoes one or
more named existing methods under the realistic configuration (Gotrade's real fees, fractional
shares, the owner's +5,000,000 IDR monthly top-up)
**Depends on:** Phase 1, Phase 2
**Difficulty:** NORMAL
**Package:** `.claude/skills/redo-sera-experiments`

---

## Scope revision (supersedes the first draft of this plan)

The owner extended R3 twice, in his own words:

> "well, maybe upgrade the skill so it can receive multiple methods, e.g: `/redo-sera-experiment M0022,M0020,M0019`"

> "maybe change it to `/redo-sera-experiments` so it is more clear in the skill name"

So R3 is now a **batch**, and the skill is **plural** — directory, file, frontmatter `name:`,
invocation and trigger phrasing. A single method is the one-element case of the batch, not a
separate path. The first draft's handoff note calling a roster-wide fan-out "a second requirement,
not R3" is **withdrawn**: it is R3 now and it is planned here.

Two coordinator rulings are folded in and treated as settled:

1. **`config_digest` will not change.** `real_costs.py` states the invariant ("Old methods keep
   their digests (plan invariant 2)") and rehashing would break dedupe against all 128 recorded
   trials. Funding is a property of the lab's era after phase 2, not of a configuration. The
   digest-collision refusal below is therefore **permanent and correct**, written as a rule rather
   than as a limitation awaiting a fix.
2. **`lab --help` is broken on `main`** (bare `0.1%` at `commands/lab.py:236` → argparse
   `ValueError`). The one-character fix is being folded into phase 1 or 2 at reconciliation, so it
   is **not planned here** and the skill may assume `lab --help` works. The first draft's workaround
   text and its handoff item are removed accordingly.

## Goal

A new skill at `.claude/skills/redo-sera-experiments/SKILL.md` turns
`/redo-sera-experiments M0022,M0020,M0019` — or the same ids as `seertrade.site/sera/methods/MNNNN`
URLs, or any mix — into one pre-registered variation twin per method, each running in fractional
shares at Gotrade's real fee schedule on the owner's real funding plan, and reports the whole batch
in one table against the parents. Each method runs through its own reserve → write → commit → run
cycle, and **one method's failure never aborts the batch**. The owner's original framing (purge the
old data) is refused, and the skill says why in his own plain terms with the twins presented as what
he actually asked for. No engine source is touched: phases 1 and 2 own all of it.

## Interface Contract

**Deletes:** nothing.

**Renames:** nothing in the repo. (Within this plan set only: the path this phase creates was
`.claude/skills/redo-sera-experiment/SKILL.md` in the first draft and is now the plural
`.claude/skills/redo-sera-experiments/SKILL.md`. The coordinator is updating the index's phase 3 row
and `creates:` path to match. Nothing was ever committed under the singular name, so there is no
rename to perform — only one path to agree on.)

**Creates:**
- `.claude/skills/redo-sera-experiments/SKILL.md` (new file, new directory)

**Signature changes:** none. This phase edits no Python, TypeScript, SQL or JSON.

**Requires (from earlier phases):**
- **Phase 1** — `store.DSR_POLICY == "methods"` and `npolicy.DEFAULT_POLICY == "methods"`, so the
  gate's N is the count of *distinct methods with a dev trial* (28 on the committed database,
  floored at `ceil(participation ratio)` = 3), not the 126 trial rows. Verified against `lab luck`:
  `methods N = 28`, `distinct methods 28`, `trial rows 126`, `participation ratio 2.338`.
  **This matters more for a batch than for a single twin**, and it is the whole answer to the
  owner's objection: a three-method batch adds **3** to the count — one per idea — not one per
  variant per method. Under the old `all-trials` counting the same batch would have added a trial
  row for every variant of every twin. The skill reads the policy, the N and the bar from
  `lab status` / `lab luck` at run time and types none of them, so a different phase-1 policy name
  leaves it correct.
- **Phase 2** — `lab run MNNNN` passes `contributions=sim.contributions.OWNER_MONTHLY` into
  `dev.run_registry` and writes one `store.FundingRow` per trial through `store.insert_funding`,
  inside `run_method`'s existing `BEGIN IMMEDIATE`, stamped with the trial number `insert_trials`
  assigned. Consequences the skill depends on:
  1. `trial_funding` gains a row per new trial carrying `mwr`, `spy_tr_mwr`, `deposits_usd`,
     `deposits_n`, `schedule`, `measured`.
  2. Because a funding row exists, `store.owner_failures` (`store.py:1095-1100`) judges the
     `beats SPY TR` condition **money-weighted** — `mwr` against `spy_tr_mwr` — via
     `dev.beats_spy_tr`, and `store.verdict` / `published_verdict` (`store.py:1322`, `:1359`) and
     the blocking check at `store.py:1428-1434` follow. Every twin in the batch is therefore scored
     against a SPY fed the identical dollars on the identical days.
  3. **Neither `lab show` nor the published snapshot exposes `mwr`** (measured: `_show` at
     `commands/lab.py:1042-1065` prints no funding field; `store.snapshot` has no funding key). The
     skill reads the money-weighted pair for the whole batch in **one read-only** `sqlite3` URI
     query — see Step 1 note 5 and Handoffs.
  4. **A funded twin's headline number is not comparable to its unfunded parent's**, and the gap is
     not subtle. Phase 2's funded smoke trial reports `total_return = 10.7821` (+1078%) and
     `mwr = 0.0764` (7.6%) **for the same run**: the first is mostly the owner's own deposits piling
     up, not performance. A parent recorded before funding existed was judged on total return against
     SPY TR; a twin is judged on money-weighted return against a SPY fed the same deposits. Those
     are different questions. Putting a parent's +15% CAGR beside a twin's +1078% "return" in one
     column would be actively misleading — the exact "we never fool ourselves" failure the lab's iron
     rules forbid. Step 1 note 10 records which metrics this contaminates and which survive; the
     skill's report is shaped around it.
  5. **The engine states this invariant itself**, so it is a property of the data rather than a
     quirk of phase 2: `metrics.strategy_metrics` (`metrics.py:251-254`) — "`total_return` and
     `cagr` are **deliberately left as they are** when deposits exist, and are then **not returns at
     all** — they are the recorded shape of the curve, which readers of the 128 historical trials
     depend on. `mwr` is the number that answers 'what did the money earn'."
  If phase 2 lands a different funding API, only that one SQL snippet in the skill's report step
  needs editing; nothing else in the file depends on its shape. The incomparability in (4) and (5)
  is **not** phase-2-implementation-specific — it follows from what a deposit is — so the report's
  shape stands however phase 2 is built.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/store.py`, `lab/npolicy.py`, `web/data/lab.json`, and the six test
  modules pinning `"all-trials"` / N=110 / the verdict digest (Phase 1)
- `engine/src/seer_engine/lab/runner.py`, `engine/src/seer_engine/backtest/dev.py` (Phase 2)
- `engine/src/seer_engine/commands/lab.py` — including the `%` help-string crash at `:236`, now
  owned by phase 1 or 2 per the coordinator
- `.claude/skills/sera-the-explorer/SKILL.md`,
  `.claude/skills/explore-and-experiment-new-method/SKILL.md` and its `method_template.py`,
  `.claude/skills/update-stale-sera-methods-page/SKILL.md` — read for shape and house voice,
  **not edited**
- `engine/tests/test_lab_gate_wording.py` `SCANNED` — see Handoffs. The skill is written so it does
  not need to be added.

## Files

| File | Action | What changes |
|---|---|---|
| `.claude/skills/redo-sera-experiments/SKILL.md` | create | the whole skill: batch argument parsing, the purge refusal in plain language, per-item classification and refusals, the serial per-method cycle, the resume story, the single end-of-batch publish, and the batch report |

One file. **No template file is added** — Step 2 establishes that a twin needs none, because
`m0029_blend_fractional.py` is already the worked precedent. The skill points at it and at
`explore-and-experiment-new-method/method_template.py` rather than duplicating either.

## Implementation Steps

### Step 1: Facts established against the live tree before writing a line

**File:** no edit — this is the verification the skill's correctness rests on, recorded so the
implementer need not redo it and a reviewer can check it. Run from `/home/miftah/seer` with
`./engine/.venv/bin/python`.

1. **Every CLI command and flag the skill names exists.** Verified one subcommand at a time
   (`python -m seer_engine lab <sub> --help`); all 15 named commands returned help successfully.

   | Command | Flags confirmed | Notes |
   |---|---|---|
   | `lab --db PATH <sub>` | `--db` is on the **`lab`** parser (`commands/lab.py:120`), before the subcommand | not needed in the main checkout; the default is `lab/lab.sqlite` |
   | `lab show METHOD` | positional only | **refuses a candidate id**: `lab show M0007-N20-RAW` → `no method M0007-N20-RAW` |
   | `lab status` | none | N, the live bar, test looks, families, near misses |
   | `lab luck` | `--at N` (repeatable), `--limit K` | read-only; the N each policy resolves to, every recorded DSR re-scored |
   | `lab costs METHOD` | `--candidate ID`, `--store DIR` | report only; journals one observation; N and looks unmoved |
   | `lab idea` | `--name`, `--family`, `--hypothesis`, `--source-kind {paper,blog,github,knowledge,variation}`, `--source-ref`, **`--parent`** | the flag is `--parent`, **not** `--parent-id`; prints the new id |
   | `lab next-id` | none | prints `M0032` today (M0031 is a reserved `idea` row) |
   | `lab run METHOD` | `--store DIR`, `--allow-coverage F` | |
   | `lab note METHOD` | `--file`, `--verdict` | appends a dated analysis section; `--verdict` replaces |
   | `lab insight` | `--kind {observation,hypothesis,data-wish,feature-wish,risk,synthesis}`, `--title`, `--body`, `--file`, `--method` | |
   | `lab seen` | positional `key`, `--method`, `--note`, `--find` | |
   | `lab block METHOD` | `--on` | |
   | `lab drop METHOD` | `--why` | |
   | `lab stage` | none | writes `web/data/lab.json`, `git add`s it and the database |
   | `lab export-json` | `--out F` | |
   | `lab promote` / `lab test` | — | **not used by this skill** |

2. **The method id is `M\d{4}` exactly** (`lab/method.py:27`), so a URL, a bare id and a candidate
   id all reduce to the same four digits with one regex. `H-*` ids (the P7a seed import) exist in
   `methods` but have no method file, so `lab run` can never target them.

3. **The twin's configuration digest differs from its parent's, so `lab run` accepts it.**
   `config_text` (`lab/method.py:33-38`) is `rules` + `allocator.id` + `params`; the candidate id
   and family are excluded, and the canonical `rules` text carries `fractional` and `cost_model`.
   Measured on M0007-N20-RAW:

   ```
   parent digest e9e42c63c3e7ea2e   rules=TradeRules(id='monthly-hold',…,fractional=False,…,cost_model='flat')
   twin   digest da5de315265a4fd0   rules=TradeRules(id='monthly-hold-frac-gotrade',…,fractional=True,…,cost_model='gotrade')
   ```

4. **The digest-collision refusal, and the correction that matters for the batch.** `contributions`
   is a `dev.run_registry` argument, not a `Candidate` field, so it is **not** in the digest — and
   per the coordinator's ruling the digest will not be changed to include it, because `real_costs.py`
   pins the invariant that old methods keep their digests and rehashing would break dedupe against
   all 128 recorded trials. Funding belongs to the lab's *era*, not to a configuration. **Therefore,
   permanently: a parent whose best variant already runs fractional at `cost_model="gotrade"` has no
   honest twin.** A verbatim re-run under the new funding is the same configuration and
   `runner.preflight` (`lab/runner.py:109-115`) refuses it with
   `<id> repeats <id>, which already ran on the dev window`.

   **Correction to the coordinator's note:** M0029 is **not** a live case of this. Measured across
   every method file in the tree (`discover()`, all 72 candidates), **no recorded method is
   fractional at Gotrade's fees today**:

   | rules preset | methods using it | twinnable? |
   |---|---|---|
   | `monthly-hold`, `weekly-hold`, `monthly-rank-*-resize` (whole-share, flat) | M0001, M0002, M0004, M0005, M0007, M0008, M0011, M0012, M0013, M0015, M0019, M0020, M0021, M0022, M0024 | yes — both dials move |
   | `monthly-hold-frac` (fractional, **flat** cost) | M0029, M0030 | **yes** — the cost dial still moves, so the digest differs |
   | `monthly-hold-frac-gotrade` / `*-frac-gotrade` | **none** | — |

   So refusal (a) is **currently unreachable for every method in the lab**, and the batch cannot
   trip over it by accident. It becomes reachable exactly once this skill has run: a twin it minted
   *is* fractional at Gotrade's fees, so re-invoking the skill on a twin's own id hits it. That is
   the realistic trigger — a batch re-run where the owner pastes a twin id instead of the parent's —
   and it is why the refusal must be per-item and non-fatal rather than a footnote.

5. **`mwr` is not printed or published** (`commands/lab.py:_show` at :1042 formats return, CAGR,
   maxDD, PF, trades, Sharpe, MAR, DSR, worst year — no funding field; `store.snapshot` at
   `store.py:2070` has no funding key). The skill reads it **read-only**, for the whole batch in one
   query, so the database is not migrated and dirtied by the read:

   ```bash
   /home/miftah/seer/engine/.venv/bin/python - <<'PY'
   import sqlite3
   c = sqlite3.connect("file:/home/miftah/seer/lab/lab.sqlite?mode=ro", uri=True)
   c.row_factory = sqlite3.Row
   for r in c.execute(
       "SELECT t.method_id, t.candidate_id, f.mwr, f.spy_tr_mwr, f.deposits_usd, f.deposits_n "
       "FROM trials t JOIN trial_funding f ON f.trial_n = t.n "
       "WHERE t.window = 'dev' ORDER BY t.n"):
       print(dict(r))
   PY
   ```

   Confirmed today: the schema holds `trial_funding`, `trials` = 128, the join returns **0** rows —
   nothing is funded yet, exactly as phase 2's contract says. **And the read leaves the file
   byte-identical** (`sha256sum -c` passed after the query), which is what makes it safe where a
   `lab` subcommand is not.

6. **`registry_problem`** (`commands/backtest_dev.py:486-514`) runs `git status --porcelain` and
   `git ls-files --error-unmatch` **in the method file's own parent directory**, and `discover()`
   (`lab/method.py:104`) resolves that directory from whichever `seer_engine` is on `sys.path`. This
   is why the skill works in the **main checkout** — see Step 3.

7. **Shipped documents may not state a luck bar as a number.**
   `engine/tests/test_lab_gate_wording.py:128` scans a `SCANNED` tuple with
   `BAR_WITH_NUMBER = (?:DSR|luck\s+check)\s*(?:>=|≥|of\s+at\s+least)\s*(\d+\.\d+)`. Its backtick
   exemption (`_code_spans`) is **per line**, so a fenced code block is *not* exempt. The skill
   types no bar number anywhere.

8. **A batch `synthesis` insight is swept, and that constrains how the batch report is journaled.**
   `test_the_newest_synthesis_does_not_state_a_bar_the_lab_does_not_apply` (`:300-326`) takes the
   newest `synthesis` row (`ORDER BY added DESC, id DESC`) — the row
   `web/app/sera/overview.ts` renders as the site's headline — and sweeps it with `PROSE_BARS`,
   which matches the *plain-English* idiom too ("our limit is 20%", "requires 0.90", "at the new 20%
   limit"). A batch of 2+ should write a synthesis (it is a batch, and it is the first thing the
   owner reads), so **the synthesis must state no bar and no limit as a number**. The other two
   synthesis fixtures (`:343`, `:390`) pin *older* rows by id and are unaffected by appending a
   newer one. Verified: `_insights` requires at least one synthesis to exist, which it does.

9. **The batch dedupe marker works and has no false positives.** `methods` carries
   `source_ref` (columns: `id, name, family, parent_id, source_kind, source_ref, hypothesis, status,
   analysis, verdict, blocked_on, source_sha, created, updated`). The skill stamps every twin's
   `source_ref` with a fixed prefix, so "has this parent already been twinned *by this skill*" is one
   read-only query:

   ```sql
   SELECT id, status FROM methods
   WHERE parent_id = ? AND source_kind = 'variation'
     AND source_ref LIKE 'redo-sera-experiments:%'
   ```

   This is necessary rather than cosmetic: **24 methods already have a `parent_id`**, and several
   are variations that are *not* this skill's twins — M0011 and M0012 of M0007, M0013 of M0002,
   M0029 of M0021, M0030 of M0029, M0031 (idea) of M0030. A plain
   `parent_id = ? AND source_kind = 'variation'` test would wrongly skip M0007, M0002, M0021 and
   M0029 on the very first invocation. Verified: the marker query returns **zero rows** today, and
   no existing `source_ref` begins with that prefix.

10. **Which metrics deposits contaminate, measured — this is what the batch report is shaped around.**
    Read out of the engine, not inferred:

    | Metric | How it is computed | Deposit-safe? | What the skill may do with it |
    |---|---|---|---|
    | `mwr` / `spy_tr_mwr` | `metrics.money_weighted_return`, an IRR over the opening cash, every deposit and the final mark | **yes, by construction** | **the headline.** Twin against a SPY fed the identical dollars on the identical days: like for like |
    | `total_return` | `last / first - 1` over raw equity (`metrics.py:277`) | **no** — "not a return at all" per the engine's own docstring | twin's own cell only, labelled as the shape of the curve. **Never** in a column shared with a parent |
    | `cagr` | `cagr_between`, same raw equity endpoints | **no** — the docstring's worked case: a book earning *nothing* records CAGR +600.9% on the owner's plan | same treatment as `total_return` |
    | `max_drawdown` | `(peak - equity) / peak` over raw equity snapshots (`metrics.py:261-265`), no cashflow term | **no** — deposits lift equity, so they lift the peak and *damp* the measured percentage fall | report for the twin; say deposits soften it; **not** like-for-like against an unfunded parent |
    | `profit_factor` | gross win / gross loss over closed-trade P/L in USD | **broadly** — a trade ratio, not an equity ratio | comparable, with the caveat that a bigger later book makes later trades weigh more |
    | `trades` | a count | **yes** | comparable |
    | `sharpe`, and therefore `dsr` | `_daily_returns` = `equity[i]/equity[i-1] - 1` (`book_runner.py:536`), **no cashflow adjustment** | **no** — see the risk below | report what the lab recorded; **never** claim it is comparable to the parent's; journal a `risk` insight when a funded twin's luck score looks surprisingly strong |
    | `worst_year` / `worst_year_return` | `_year_returns` = `value / base - 1` against the **opening** equity (`book_runner.py:552-560`) | **no** — cumulative against the start, inflated by deposits | report for the twin only, labelled; not compared to the parent's |

    **The `sharpe`/`dsr` row is a cross-phase risk, not a reporting nicety, and it is raised to the
    coordinator rather than handled here.** `_daily_returns` takes only the equity series; the
    deposits live separately on `BookResult.cashflows`. On the owner's plan the first deposit is
    about +50% of a 10,000,000 IDR book in a single session, and that spike enters the daily-return
    series, hence `daily_moments`, hence `deflated_sharpe`, hence the recorded `dsr` — **which is a
    gate condition**, not just a display. `backtest/book_runner.py` is in neither phase 1's nor
    phase 2's declared file list, so as currently scoped nothing corrects it. See Handoffs item 1.
    This phase does not plan a fix — it is engine work — but the skill is written so it never
    launders the number: it reports what was recorded, refuses the parent comparison, and journals
    the risk.

**Impact:** nothing is changed; this is the evidence that Step 5's file is accurate.

### Step 2: Decide the twin needs no template file

**File:** no edit — a decision recorded so the implementer does not add a second file.

`engine/src/seer_engine/lab/methods/m0029_blend_fractional.py` is already a twin of exactly this
shape: ~40 lines, importing its parent's params helper (`from
seer_engine.lab.methods.m0021_momentum_lowvol_blend import _blend`) and the shared allocator
(`BLEND`), swapping only `rules`, declaring **one** `Candidate`. A twin that reuses its parent's
allocator needs no `Allocator` class, so `explore-and-experiment-new-method/method_template.py` —
whose bulk *is* the allocator scaffold — is the wrong starting point and a copy would be mostly dead
code. The skill names `m0029_blend_fractional.py` as the file to copy and `method_template.py` as
the fallback for the rare twin whose parent's allocator cannot be reused. Neither is edited.

**Impact:** phase 3 ships one file. `.claude/skills/` has no manifest — skills are discovered from
`.claude/skills/<name>/SKILL.md` (confirmed: `git ls-files .claude/` lists only the four existing
skills' own files) — so there is no registration step, and the plural directory name is the only
place the new name has to be right.

### Step 3: Decide the batch runs serially in the main checkout, and say why not Sera's fan-out

**File:** no edit — a decision the skill's text then states, with the reasoning preserved so a
future reader does not "optimise" it into a race.

`sera-the-explorer` runs up to **4 children in parallel**, each in its own git worktree and tmux
window. That is right for Sera and wrong here, and the difference is not timidity — it is that
Sera's children do different work. **Four reasons, each independently sufficient:**

1. **`lab run` needs the research store, and the store is not in worktrees.** `engine/.research/` is
   gitignored and lives only in the main checkout; `--store` must point there. Sera's children get
   away with it by exporting `SEER_RESEARCH_STORE` at the main checkout — i.e. the parallelism never
   actually isolated the store, it only isolated the source tree. Here there is nothing to isolate:
   every twin reads the same store.
2. **Only `lab stage` may commit `lab/lab.sqlite`, and it takes the database's write lock.** Sera's
   design makes exactly one process (Sera) the committer precisely because a binary file written by
   two sessions is a conflict nobody can merge. A parallel redo batch would need that same single
   committer — which is this session — so the parallelism buys nothing and adds a lock to contend
   for. `lab run` itself opens `BEGIN IMMEDIATE` around its inserts, so two concurrent runs serialise
   at the database anyway, at the least predictable moment.
3. **`registry_problem` runs `git status` in the method file's own directory**, and `discover()`
   picks that directory from `sys.path` (Step 1.6). In a worktree the two agree only while
   `PYTHONPATH` is exported in *every* shell; one forgotten export and `lab run` either refuses a
   file that was committed or silently runs the main checkout's copy. Multiply that by N parallel
   worktrees and the failure is both likelier and harder to read.
4. **The work is minutes, not hours.** `lab run` is "seconds to minutes" per method and `lab costs`
   is about a minute. A three-method batch is a coffee, not a night. Sera parallelises because each
   child is a full research session with web research and analysis; a redo is a mechanical
   re-measurement with no thinking between items.

**So: one session, main checkout, one method at a time.** The checkout may still be shared with
other sessions, so the skill carries: commit by explicit pathspec, never `git add -A`, never
`git reset --hard`, never `git checkout`/`restore`/`stash` the shared `lab/lab.sqlite`.

**Impact:** no `PYTHONPATH` clause, no worktree setup or teardown, no tmux, no `SendMessage`
collection protocol in the skill. The isolation property the owner needs — one method's failure not
killing the batch — is delivered by the per-item loop in Step 4, not by process isolation.

### Step 4: Decide the per-item state machine, the resume story and the staging point

**File:** no edit — the three coupled decisions the skill's loop implements.

**(a) Per-item isolation.** Each requested parent gets its own full cycle: classify → cost pre-check
→ reserve → write file → commit → run → note. A failure anywhere in one item's cycle is caught,
journaled, recorded as a skip with its reason, and **the loop continues to the next item**. This is
`sera-the-explorer`'s rule ("A child's failure never pauses the other slots") implemented serially
instead of across slots. Nothing in one item's cycle is shared mutable state with another's except
the database, and every write to it is already atomic.

**(b) The durable state is the database and git, so resume is free.** The skill does not keep a
progress file. Each item's state is a query, and the classification is the resume:

| State | How it is detected | What the skill does |
|---|---|---|
| **S0 — not started** | no `methods` row with `parent_id = MNNNN AND source_kind='variation' AND source_ref LIKE 'redo-sera-experiments:%'` | the full cycle |
| **S1 — reserved, no file** | such a row exists, status `idea`, and no `m<its digits>_*.py` in the methods directory | reuse that id and its hypothesis; skip `lab idea`; write the file and continue |
| **S2 — file written, uncommitted** | the file exists and `git status --porcelain -- <file>` is non-empty | commit it (that is the pre-registration) and continue |
| **S3 — committed, not run** | the file is clean and tracked, and `SELECT count(*) FROM trials WHERE method_id = <twin>` is 0 | `lab run` and continue |
| **S4 — done** | the twin's status is `rejected` or `dev-eligible` and it has trials | nothing; include it in the report as already done |

Every one of those five is read-only to detect, and the transitions are exactly the cycle's steps —
so **re-invoking the skill with the same list resumes rather than duplicating**, and re-invoking with
a longer list picks up only the new members. This is also precisely the owner's dedupe request
("dedupe against a parent that already has a twin from an earlier run"): S4 is that dedupe, and S1–S3
are the interrupted-midway cases it would otherwise double-mint.

An interruption therefore leaves a well-defined tree: **every method file already committed is a
valid pre-registration and stays**, every twin already run keeps its trials (append-only, by design,
and meant to stay), and the next invocation continues from the first item that is not S4. Nothing
needs unwinding, and nothing may be: a committed pre-registration that were later deleted and
re-minted would be a hypothesis written after seeing a number.

**(c) Staging: once, at the end — and on any exit.** Taking the coordinator's recommendation, with
the cost stated.

- **Why once at the end.** The site gets one coherent redeploy instead of N, and the owner reads one
  finished batch rather than watching it assemble. `lab/lab.sqlite` is a binary: N staged commits of
  it are N chances to collide with a parallel session and N large blobs in history for one logical
  change. And a half-published batch is worse than an unpublished one — the site would show two of
  three twins with no synthesis explaining them.
- **What it costs on interruption.** A hard kill between the first `lab idea` and the final
  `lab stage` leaves the working-tree database holding rows that are not published: the snapshot is
  stale and `tests/test_lab_snapshot.py` is red until someone stages. That is a **known house
  condition with a known house fix**, already documented in both `sera-the-explorer` and
  `explore-and-experiment-new-method`: if it is the only failure, `lab stage`, commit both files,
  push, re-test. The skill's own preflight does exactly that, so **the next invocation repairs it
  before doing anything else**.
- **Why this does not weaken the resume story in (b).** Resume reads the **live** database file,
  which is on disk whether or not it has been committed. Publication and durability are decoupled:
  staging is about the website, not about remembering where the batch got to. That is what makes the
  end-of-batch choice safe.
- **Staging is the batch's finally block.** The skill stages, commits and pushes on *any* orderly
  exit — a completed batch, an empty batch that only journaled refusals, or an early stop — not only
  on the happy path. Only a hard kill can skip it, and that case is covered by the preflight above.
- **The method-file commits stay per item**, one commit each. They must: the commit *is* the
  pre-registration and `lab run` refuses an uncommitted file. A batch of three therefore produces
  three pre-registration commits plus one `lab stage` commit, which is also the better audit record —
  each hypothesis is frozen at its own timestamp, before its own run.

**Impact:** the skill needs no lockfile, no progress journal and no cleanup path; the loop plus five
read-only queries carry all of it.

### Step 5: Write the skill

**File:** `.claude/skills/redo-sera-experiments/SKILL.md` (new file; create the directory)

**Change:** write the file below verbatim.

**Code:**

````markdown
---
name: redo-sera-experiments
description: Use when the owner wants one or more existing Seer lab methods redone the way he really trades — "/redo-sera-experiments M0022,M0020,M0019", "/redo-sera-experiments https://seertrade.site/sera/methods/M0007", "redo these methods with the real Gotrade fees", "redo my roster methods realistically", "re-run M0022,M0020,M0019 with real fees and the monthly top-up", "purge M0007 and run it again properly", "these results don't represent how I actually trade". Takes a comma-separated list of method ids or seertrade.site method URLs, mints one pre-registered variation twin per method at Gotrade's real fees in fractional shares on the owner's real monthly top-up, and reports the whole batch beside the parents.
---

# Redo Sera experiments, honestly

## What you get

You asked for your methods' results to represent how you really trade: Gotrade's real fees,
fractional shares, and the 5,000,000 rupiah you add every month. **That is what this skill
produces**, for one method or for a list of them. It runs each one again under all three, and shows
the new numbers next to the old ones so you can see exactly what the realism cost.

The one thing it does **not** do is delete the old experiments. Three plain reasons:

1. **The old numbers are not wrong — they are a record of a different question.** They answer "what
   would this idea have done paying a tenth of a percent a trade, buying whole shares, on money that
   never grew". That is a real answer to a question you no longer care about. Keeping it is what
   lets us say what the realism cost, which is the interesting part.
2. **Deleting experiments would make every other result look better than it is.** The lab discounts
   every method for how many ideas we have tried — try enough things and something looks good by
   luck alone. Throw away a past try and that discount shrinks, so every *other* method's score
   quietly goes up without anyone having learned anything. That is the exact trick on ourselves the
   whole scoring system exists to stop. Deleting the embarrassing one is how people end up believing
   a strategy that does not work.
3. **The database will not let us.** The trials and methods tables are append-only: deleting a row
   is blocked by the schema itself (`trials_no_delete`, `trials_no_update`, `methods_no_delete`).
   That is not a setting someone forgot to turn off; it is the point.

So instead of deleting, we add: a **twin** per method. A twin is a new method that is the old one
with the realism switched on, registered before it runs, and judged on its own. The lab's own cost
report says this in so many words — "the only way a real-fee configuration is judged is a new method
that pre-registers it" (`lab/real_costs.py`) — and `sera-the-explorer` already requires it: *promote
the twin, never the original*.

**And the twins barely move anyone else's score.** The discount counts *distinct ideas*, not
individual settings, so a batch of three adds **three** to the count — one per idea — not one for
every setting each twin tries. Your objection that redoing a method rearranges everyone else's luck
was correct about the old counting, and the counting was fixed; it is no longer a reason not to redo
a method, or a reason to redo them one timid batch at a time. Read the live count and the live bar
off `lab status` and quote those, never numbers typed from memory.

## Three iron rules

The same three the other lab skills carry. Breaking the letter of a rule breaks its spirit too.

1. **We never stop trying, we never give up.** A twin that loses is a result, and a good one: it
   tells you the idea only worked because the fees were pretend. Journal it and queue what to try
   next. **One method's failure never stops the batch** — journal it, record the skip, move to the
   next. A batch that queues nothing is the only real failure.
2. **No human in the loop.** Decide everything yourself. Never `AskUserQuestion`, never end a turn
   on a question, never wait for approval — not for which variant to twin, not for a failing check,
   not for a push. Write down what you assumed, in the analysis or the commit message. The only
   allowed stop is terminal (missing tooling you cannot build, a permission you do not have): report
   it and end, never hold a prompt open.
3. **We never fool ourselves.** Every twin is registered *before* it runs, by committing its file.
   Every trial counts. Nothing is deleted, nothing is edited, and no number is compared to a bar
   from a different day.

## Invocation

```
/redo-sera-experiments M0022,M0020,M0019
/redo-sera-experiments M0022, M0020, M0019
/redo-sera-experiments https://seertrade.site/sera/methods/M0007
/redo-sera-experiments M0022,https://seertrade.site/sera/methods/M0020,M0007-N20-RAW
/redo-sera-experiments M0007
```

A single method is just the one-item batch. There is no separate path for it, and nothing below
behaves differently.

**Parse per item, not across the whole string**, so a candidate id keeps its variant suffix:

```bash
ARGS="$*"
printf '%s' "$ARGS" | tr ',' '\n' | tr -s ' \t' '\n' | sed '/^$/d' > /tmp/redo-items.txt
```

For each line: the parent is the first `M` followed by exactly four digits; the pinned variant, if
any, is the longer candidate id in the same item.

```bash
MNNNN=$(printf '%s' "$ITEM"  | grep -oE 'M[0-9]{4}' | head -1)
VARIANT=$(printf '%s' "$ITEM" | grep -oE 'M[0-9]{4}-[A-Z0-9-]+' | head -1)   # may be empty
```

That one rule covers every form above — bare ids, full URLs, candidate ids, commas with or without
spaces, and any mix in one invocation. **Dedupe by parent id, keeping the first occurrence** (and
its variant) so `M0007,M0007-N20-RAW` is one item, not two.

**The URL is never fetched.** The site is behind the Sera gate and the repo holds everything the
page is built from — the same rule `update-stale-sera-methods-page` follows.

### Refuse per item, never per batch

A bad item must not discard the batch. Check each, record the reason, **continue**:

- `lab show $MNNNN` prints `no method …` → the lab has no such method. Skip it, with that reason.
- the id starts with `H-` → the P7a seed import has no method file, so `lab run` can never target
  it. There is nothing to redo. Skip it, with that reason.
- the item contains no `M` plus four digits → not a method id at all. Skip it, with that reason.

Print the resolved plan before doing any work — the parents you will twin, in order, and every item
you are skipping with its reason — then start. Never ask whether to proceed.

## Fixed facts

```
REPO=/home/miftah/seer                             # the main checkout: work here, not a worktree
PY=$REPO/engine/.venv/bin/python                   # the only venv
LAB="$PY -m seer_engine lab"
STORE=$REPO/engine/.research                       # the dev research store: NOT in any worktree
METHODS=$REPO/engine/src/seer_engine/lab/methods   # where each twin's file goes
MARKER="redo-sera-experiments:"                    # the source_ref prefix every twin carries
```

**One session, in the main checkout, one method at a time.** Do **not** fan out into worktrees the
way `sera-the-explorer` does. Four reasons, and each is on its own enough:

1. `lab run` needs the research store, and the store is gitignored and lives only here. There is
   nothing per-method to isolate: every twin reads the same store.
2. Only `lab stage` may commit the lab database, and it takes the write lock. A binary file written
   by two sessions is a conflict nobody can merge, which is exactly why Sera makes herself the only
   committer. Parallel twins would still have to funnel through one committer — this session — so the
   parallelism buys nothing and adds a lock to contend for. `lab run` serialises at the database
   anyway.
3. `lab run` refuses an uncommitted method file by running `git status` in the *method file's own
   directory*, and it finds that directory through whichever `seer_engine` is importable. Here the
   venv and the sources are the same tree, so the two always agree. In a worktree they agree only
   while `PYTHONPATH` is exported in every single shell, and one forgotten export means `lab run`
   either refuses a file you did commit or silently runs the main checkout's copy.
4. A redo is minutes per method, mechanical, with no research between items. Sera parallelises
   because each of her children is a full research session; these are not.

The isolation that matters here is **per item, not per process**: see The batch loop.

The checkout may still be shared with other sessions, so:

- **Commit by explicit pathspec.** Never `git add -A`. Never `git reset --hard`.
- **Never `git checkout`, `git restore` or `git stash` `lab/lab.sqlite`.** It is a binary another
  session may be mid-write in. Bringing the checkout back to clean is a `pull`, never a restore.
- **Only `lab stage` commits `lab/lab.sqlite`, and every such commit also includes
  `web/data/lab.json`.** CI fails a database commit without its snapshot, and the site redeploys
  from each push.
- **Every `lab` subcommand migrates the database on connect, so even a read dirties the file.** When
  you need a column no command prints, open the database read-only instead (see the report step).

## 0. Preflight, once for the batch

```bash
cd $REPO
git pull --rebase --autostash
$LAB status                         # the live count, the live luck bar, the test looks used
cd engine && $PY -m pytest -q tests/test_lab_*.py; cd $REPO
```

`tests/test_lab_snapshot.py` fails whenever `lab/lab.sqlite` has changed without a `lab stage` — for
example **after an earlier batch of this skill was interrupted before it published**. If that is the
only failure, run `lab stage`, commit `lab/lab.sqlite` and `web/data/lab.json`, push, and re-run the
tests. Always test *after* staging, never before. This is the repair step for an interrupted batch,
so do it before anything else rather than working on top of an unpublished database.

If `$STORE` is missing, build it (`$PY -m seer_engine research_store`, a few minutes) or pull it with
`/sync-research-store`. Never point `--store` into a worktree: there is no store there, and a rebuild
is half an hour for nothing.

## 1. Classify every item, once, before touching anything

For each parent on the list, find out where it already stands. This is both the dedupe the owner
asked for and the resume for an interrupted batch — the state *is* the database and git, so there is
no progress file to keep and none to go stale.

```bash
$PY - <<PY
import sqlite3
c = sqlite3.connect("file:$REPO/lab/lab.sqlite?mode=ro", uri=True); c.row_factory = sqlite3.Row
for parent in """$PARENTS""".split():
    tw = c.execute(
        "SELECT id, status FROM methods WHERE parent_id = ? AND source_kind = 'variation' "
        "AND source_ref LIKE '$MARKER%'", (parent,)).fetchone()
    if tw is None:
        print(parent, "S0-not-started"); continue
    n = c.execute("SELECT count(*) FROM trials WHERE method_id = ?", (tw["id"],)).fetchone()[0]
    print(parent, tw["id"], tw["status"], "trials", n)
PY
```

| State | What you see | What to do |
|---|---|---|
| **S0 not started** | no twin row for this parent | the whole cycle below |
| **S1 reserved, no file** | a twin row, status `idea`, and no method file for its id | reuse that id and its hypothesis; **skip the reservation**; write the file and carry on |
| **S2 file written, uncommitted** | the file exists but `git status --porcelain -- <file>` is non-empty | commit it — that is its pre-registration — and carry on |
| **S3 committed, not run** | the file is clean and tracked, and the twin has no trials | run it and carry on |
| **S4 done** | the twin's status is `rejected` or `dev-eligible` and it has trials | nothing. Report it as already done |

**The marker is what makes this correct.** Many parents already have variations that are *not* this
skill's twins — the lab holds two dozen methods with a parent — so matching on "is a variation of
this parent" alone would wrongly skip methods that have never been redone. Every twin this skill
mints carries the marker prefix in its `source_ref`, and only that prefix counts.

**Never re-mint a twin that is S4, and never delete and redo one.** A pre-registration deleted and
written again is a hypothesis written after seeing a number, which is the one thing the lab exists to
prevent. If a twin was run and the owner wants a *different* realistic configuration, that is a new
variation of the twin, with its own hypothesis — not a redo of the redo.

## 2. The batch loop — one method at a time, failures contained

Work through the list in the order given. **Wrap each item.** Any failure inside one item — a cost
report that says stop, a refused run, a contract test that will not pass, an exception — is caught,
journaled, recorded as a skipped row with its reason, and then the loop moves to the next item. Never
let one method end the batch, and never leave a half-written method file behind: if an item fails
before its commit, delete its file so the next invocation sees a clean S1 rather than a puzzling S2.

### 2a. Read the parent

```bash
$LAB show $MNNNN
```

Note its status, family, source and parent; **its best recorded dev trial by MAR** — that is the
variant to twin, unless the item pinned a candidate id, in which case twin that one; and that
trial's CAGR vs SPY TR, max drawdown, profit factor, trades, DSR, the `N=` it was scored at, and
which conditions it `failed`.

That `N=` is the count on the trial's **run date**, not today's. Never compare a recorded DSR to
today's bar; `lab luck` re-scores every recorded DSR at today's count and that is the only number
worth quoting beside a twin's. Then read the parent's `TradeRules` preset out of its method file in
`$METHODS`.

### 2b. Two per-item refusals, both final, both non-fatal to the batch

**a. The parent is already fractional and already at Gotrade's real fees.** Then the only thing a
twin would change is the monthly top-up — and the funding is **not** part of what makes a
configuration distinct, permanently and by design: a configuration's identity is its rules,
allocator and parameters, and old methods keep their digests so that dedupe against every recorded
trial keeps working. Funding is a property of the lab's era, not of a configuration. So a verbatim
re-run is *the same configuration* and `lab run` refuses it
(`<id> repeats <id>, which already ran on the dev window`).

Do **not** nudge a parameter to make the configuration look different: that is a new method wearing
a redo's clothes, and it spends a new idea on a question nobody asked. Instead: say plainly that this
method is already measured at real fees in fractional shares, quote where it stands under today's
counting from `lab status` / `lab luck`, journal that as an observation, record the skip, and go to
the next item.

No method in the lab trips this today — the fractional ones still pay the old flat fee, so both dials
still move. It becomes live the moment this skill has run, because a twin *is* fractional at
Gotrade's fees: the realistic case is someone pasting a twin's id into a later batch instead of its
parent's. Which is exactly why this is a skip, not an abort.

**b. The parent's edge does not survive real fees.** For a parent numbered **M0030 or earlier** —
every one of which was measured at the lab's old flat assumption of a tenth of a percent a trade —
run the cost report *before* reserving anything for it:

```bash
$LAB costs $MNNNN                   # add --candidate <the pinned variant> when the item named one
```

A report, never a trial: no row is written, the lab's count does not move, no test-window look is
spent, and it journals one observation by itself. It re-runs the parent's best dev variant twice — at
the flat cost and at Gotrade's real schedule — and prints both side by side. If the real fees take
the variant below SPY, or break a go-live condition it used to clear, **a twin is not worth
minting**: the idea only worked because the fees were pretend, which is itself the answer the owner
came for. Make sure the journal says that in plain words, record the skip with its reason, and go to
the next item. This mirrors the rule `sera-the-explorer` already applies before reserving a variation
of a near miss.

Reserving nothing until both checks pass is deliberate: there is then no idea row to drop and no id
burned on an item that was never going to run.

### 2c. Reserve this twin

Skip this if the item is **S1** — reuse the id and hypothesis already reserved.

```bash
$LAB idea \
  --name "<the parent's idea, in fractional shares at Gotrade's real fees, on the monthly top-up>" \
  --family "<the parent's family, verbatim>" \
  --source-kind variation \
  --parent $MNNNN \
  --source-ref "redo-sera-experiments: <the parent's best variant id> on monthly-hold-frac-gotrade, funded monthly" \
  --hypothesis "<see below>"
```

The flag is `--parent`, not `--parent-id`. The command prints the new id — call it `$TWIN`.
(`lab next-id` tells you the next free one, but `lab idea` assigns it; never type an id.)

**`source_ref` must begin with the marker** `redo-sera-experiments:`. That prefix is how a later
batch knows this parent has already been redone *by this skill*, as opposed to merely having some
variation. Get it wrong and the next invocation mints a duplicate twin.

**The hypothesis is the pre-registration, so it must state the realism explicitly**, in three parts
written before any result exists:

1. that it runs **fractional**, so every slot is actually bought rather than left in cash;
2. that it pays **Gotrade's real fee schedule** (`cost_model="gotrade"`) — the one fitted to the
   owner's own order receipts — not the lab's old flat assumption;
3. that it is judged on the **owner's real funding plan**, 5,000,000 IDR arriving on the 25th of
   every month on top of the opening book, against a SPY fed the identical dollars on the identical
   days.

Then say what you expect: which of the parent's numbers should survive the realism and which should
not, and why. Name the parent's recorded figures so the comparison is pinned before the run. Write a
fresh hypothesis per twin — do not paste one item's across the batch; the parents differ and so do
the reasons.

`expected_failure` goes in the method file next, and is written now, not after.

**Do not stage or commit the database here.** The batch publishes once, at the end.

### 2d. Write this twin's method file

```bash
cp $METHODS/m0029_blend_fractional.py $METHODS/m<twin digits>_<slug>.py
```

`m0029_blend_fractional.py` is the worked precedent and the shortest honest twin in the tree: it
imports its parent's params helper and the shared allocator, swaps only `rules`, and declares one
candidate. Copy it and change the parent it imports from. Only if the parent's allocator genuinely
cannot be reused do you start from
`.claude/skills/explore-and-experiment-new-method/method_template.py` instead.

Rules for the file:

- **The module number must equal `METHOD.id`** (`m0032_*.py` ↔ `id="M0032"`), or `discover()` raises
  — and it raises for the *whole lab*, which would break every later item in the batch. Get this
  right before running anything.
- `source_kind="variation"`, `parent_id=$MNNNN`, `family` = the parent's family verbatim, and
  `source_ref` = **the same marker-prefixed string you reserved with**.
- `hypothesis` = what you reserved. `expected_failure` = the way it most likely fails, written now.
- **`rules` must be a real-fee fractional preset**: `sim.rules.MONTHLY_HOLD_FRAC_GOTRADE`, or
  `MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE` when the parent reranks monthly and resizes weekly, or
  `replace(<the parent's book preset>, fractional=True, cost_model="gotrade")` for any other cadence.
  **This is enforced, not requested.** `lab/real_costs.py:real_cost_problem` refuses to run any
  method numbered M0031 or later with a variant that is not a `book` rule set at
  `cost_model="gotrade"`, and `runner.preflight` raises it before any data is loaded. Every twin you
  mint is numbered above that line, so a flat-fee twin cannot run at all.
  *A `replace(...)` preset runs fine on dev, but `lab promote` needs a preset with its own id — if
  such a twin wins, queue a `feature-wish` insight for one.*
- **As few variants as the question needs — ideally one.** The point of a twin is to isolate the
  realism, and one variant adds one trial. Changing a second dial makes the twin a different idea and
  you can no longer tell which change moved the number. In a batch this compounds: the owner wants to
  read one row per method, not a grid.
- `seen_keys` must be unique per twin (something like `concept:<the parent's concept>-frac-gotrade`),
  or the second twin in the batch collides with the first.
- Pure: no clock, no randomness, no files, no network, no printing. Reads only bars dated
  ≤ `data_date`.

Check it, then lint:

```bash
cd $REPO/engine && $PY -m pytest -q tests/test_lab_methods.py && $PY -m ruff check src tests
cd $REPO
```

The contract test covers **every** method file, so a green run here also proves this twin has not
broken any earlier item's file. If it fails, fix this method. **Never weaken the test.** If it cannot
be made to pass, delete this twin's file, record the skip with the reason, and move to the next item —
leaving a broken file in place would fail every later item too.

### 2e. Commit this twin's file — this is its pre-registration

```bash
git add -- engine/src/seer_engine/lab/methods/m<twin digits>_<slug>.py
git commit -m "lab: $TWIN, the real-fee fractional twin of $MNNNN (pre-registration)"
```

**`lab run` refuses an uncommitted, modified or untracked method file** and says so:
`Commit the method file first: the commit is its pre-registration`. It checks with `git status` in the
file's own directory, so a staged-but-uncommitted file is refused too. This is not a formality and
not optional: the commit is what makes the hypothesis unchangeable before the numbers exist. Do not
skip ahead, do not batch these commits together at the end, and never pass `require_commit=False`
from a script.

One commit per twin, not one for the batch. Each hypothesis is then frozen at its own timestamp,
before its own run, which is the audit record the lab is for. Push at the end of the batch, or now if
you prefer — either is fine for the method files; only the database commit has to be last.

### 2f. Run it

```bash
$LAB run $TWIN --store $STORE
```

Seconds to minutes. Use `run_in_background` and wait for it. It prints each variant's line and marks
an `ELIGIBLE` trial. One `lab run` per method, ever — a method runs once.

Because the runner funds the book, the trial is scored on the owner's real funding plan: the
money-weighted return of the book against the money-weighted return of a SPY fed the identical
dollars on the identical days. That is what "beats SPY" means for a funded trial, and it is the
number to lead with.

If the run fails, record the skip with the reason and move on. The method file stays committed and
the item is **S3** for the next invocation, which will simply run it — nothing to clean up.

### 2g. Write this twin's own analysis

Each twin gets its own note; the batch report later is a summary, not a substitute.

```bash
$LAB note $TWIN --file /tmp/twin-$TWIN.md \
  --verdict "<one or two sentences: what the realism cost, and where this twin stands under today's bars>"
```

The analysis is what the owner reads on that method's page, and he is not a trader or a statistician.
Short sentences, everyday words, every number with its meaning ("lost at most 13% from a peak, inside
the limit"), and a plain gloss on any term you cannot avoid. Cover:

- what the realism cost, as the headline: fees, fractional fills, and the top-up
- **the money-weighted result against the SPY fed the same deposits** — in plain words, "what your
  money actually earned, against putting the same deposits into the market instead". This leads,
  because it is the only like-for-like comparison a funded run has
- **a sentence saying the total and yearly figures are not returns here.** With deposits, they are
  the shape of the curve and mostly your own money arriving; the engine leaves them that way on
  purpose. Never quote them beside the parent's as if they were the same measurement — the same rule
  as the batch report, and it applies just as much on a single method's page
- which conditions it misses and by how much
- how likely the result is real rather than luck after this many distinct ideas, with the count and
  the bar as `lab status` prints them today — and, for a funded run, the caveat that this is worked
  out from day-to-day account changes and the deposit days look like big up days. If it comes out
  surprisingly strong, say so and journal a `risk` insight
- the worst year and when the worst fall happened, noting that deposits make a fall look shallower
- **why** — the mechanism, not just the numbers
- whether the hypothesis held and whether the expected failure happened
- a closing paragraph starting **`My opinion:`** that commits to a view on whether this direction
  deserves more trials. No hedging.

Then go to the next item.

## 3. Journal and queue

Once the loop is done:

```bash
# one per batch of two or more: this becomes the site's headline
$LAB insight --kind synthesis --title "<the batch's theme, in plain words>" --file /tmp/batch.md
# plus at least one next idea, drawn from what the batch taught
$LAB idea --name "…" --family "…" --source-kind variation --parent <the most promising twin> --hypothesis "…"
```

For a **single-method** invocation use `--kind observation --method $TWIN` instead: a synthesis is a
batch summary, and the explore skill reserves it for exactly that.

The newest synthesis is the headline of seertrade.site/sera — the first thing the owner reads — and
he is not a trader. So: everyday words; name methods by what they do ("the residual-momentum book"),
never by their ids; no code, file paths, column names, hashes or backticks; spell out jargon ("worst
fall", not "max DD"; "gains against losses", not "PF"); and a number earns its place only with its
meaning. Cover what the realism cost across the batch, which ideas survived it and which only ever
worked on pretend fees, what that says about where to search next, and what the deposits changed
about how the results read.

**In the synthesis, quote only what the money earned** — the money-weighted rate against a SPY fed
the same deposits. Never quote a funded twin's total or yearly figure here: with deposits those are
mostly the owner's own money arriving, and on the site's headline, stripped of the table's labels,
such a number reads as performance. One sentence explaining that the twins are measured on what the
money earned, because money kept going in, is worth more to him than any figure.

**State no bar and no limit as a number, anywhere in the synthesis** — not "the limit is 20%", not
"we require 0.90". A guard checks the newest synthesis against the live bars precisely because a
sentence like that was still the site's headline after the owner moved a bar. Say "inside the limit"
or "short of the bar" and let the page show the number.

Ids and mechanics belong in each twin's analysis, which is the audit record.

## 4. Publish — once, at the end

```bash
$LAB stage
git add -- lab/lab.sqlite web/data/lab.json
git commit -m "lab: <N> real-fee fractional twins of <the parents> — <one-line outcome>"
git -c rebase.autoStash=true pull --rebase origin main
git push
cd $REPO/engine && $PY -m pytest -q; cd $REPO
```

**Once for the batch, not once per method.** The site gets one coherent redeploy instead of several,
the owner reads a finished batch rather than watching it assemble, and the lab database is a binary —
one staged commit is one chance of colliding with a parallel session instead of several, and one blob
in history for one logical change.

**Do this on any orderly exit**: a completed batch, a batch where every item was skipped and only
refusals were journaled, or an early stop. It is the batch's last step in every case, never only the
happy one.

The cost of publishing once is that a **hard** kill before this point leaves the working-tree
database holding rows that are not published: the snapshot is stale and `tests/test_lab_snapshot.py`
is red until someone stages. That is repaired by this skill's own preflight, which stages before
doing anything else. It does not affect resuming: step 1 reads the **live** database file, which is
on disk whether or not it has been committed, so where the batch got to is never lost — only its
publication is deferred.

`lab stage` takes the database's write lock, regenerates `web/data/lab.json` and `git add`s both
files. Never `git add lab/lab.sqlite` by hand, and never commit it without the snapshot. Vercel
redeploys the site from the push, with no other step.

If any twin came out **dev-eligible**, do not promote it. Promotion spends the one counted
test-window look and belongs to `/explore-and-experiment-new-method`'s Promotion section, or to Sera:
say in the report which twins are eligible and name the command. Spending a look is not this skill's
job, and spending several in a batch is how a test window gets burned in an afternoon.

## 5. The batch report

Read everything back, then write one table.

```bash
$LAB luck --limit 0                 # read-only: every recorded DSR re-scored at today's count
for T in $TWINS; do $LAB show $T; done
```

`lab show` does not print the money-weighted numbers and neither does the published snapshot. Read
them for the whole batch in one **read-only** query, so the database is not migrated and dirtied by
the read:

```bash
$PY - <<PY
import sqlite3
c = sqlite3.connect("file:$REPO/lab/lab.sqlite?mode=ro", uri=True); c.row_factory = sqlite3.Row
for r in c.execute(
    "SELECT t.method_id, t.candidate_id, f.mwr, f.spy_tr_mwr, f.deposits_usd, f.deposits_n "
    "FROM trials t JOIN trial_funding f ON f.trial_n = t.n "
    "WHERE t.window = 'dev' ORDER BY t.n"):
    print(dict(r))
PY
```

A twin with no row there received no deposits — the normal, definite answer for every trial recorded
before the runner was funded, not a missing value. Say so rather than leaving a blank.

### The one thing you must not get wrong in this report

**A twin's return and its parent's return must never share a column.** They are not the same
measurement.

The twin got deposits; the parent did not. So the twin's "total return" counts the money you put in
as if it were money you made. This is not a rounding difference — on a real funded run the engine
reports a total return of **+1078%** and a true earned rate of **7.6%** for the *same* run. Almost
all of that +1078% is your own deposits piling up. The engine says so itself: with deposits, total
return and yearly return "are **not returns at all** — they are the recorded shape of the curve".

So:

- **Never** put the parent's return and the twin's return in one column.
- The twin's total return and yearly return go in **their own labelled cells**, and the parent's
  equivalent cells stay **blank**, with the one-word reason *unfunded*.
- **The headline for every twin is the like-for-like pair**: what the twin's money actually earned,
  against a SPY given the exact same deposits on the exact same days. Both sides got the same money
  at the same time, so that comparison is honest and it is the only one that is.

Say it to the owner in his own words, early in the report, something like:

> Two different questions. The twin's number answers *"what rate did my money actually earn, given I
> kept adding to it every month"*. The old number answers *"what would one lump sum have grown to"*.
> The first is the one that describes how you really trade — so that is the one in the big column,
> and it is measured against putting those same monthly deposits into the market instead.

Three more cells deserve care, for the same reason:

- **worst fall** — deposits keep topping the account up, so a fall looks shallower than it was.
  Report the twin's, say deposits soften it, and do not line it up against the parent's.
- **how likely it is real** (the luck score) — for a funded run this is worked out from day-to-day
  changes in the account, and the days you deposited look like enormous up days. Report what the lab
  recorded, never call it comparable to the parent's, and if a twin's luck score comes out
  surprisingly strong, say so plainly and journal it with `lab insight --kind risk`. A number that
  flatters us is the one to distrust first.
- **gains against losses** and **trades** are fair to compare, with one caveat worth a sentence: the
  book is bigger later on, so later trades count for more.

### The table

**One row per method**, like-for-like columns first, the deposit-inflated ones last and labelled:

| method (what it does) | twin | verdict | what your money earned | the same deposits into the market instead | gains against losses | trades | worst fall (deposits soften this) | how likely it is real | the shape of the curve, mostly deposits |
|---|---|---|---|---|---|---|---|---|---|
| the twin | | | **the headline** | **the honest comparison** | | | | recorded | total and yearly, labelled |
| its parent, at real fees (from the cost report) | — | — | *unfunded* | *unfunded* | | | | recorded | |
| its parent, as recorded on pretend fees | — | — | *unfunded* | *unfunded* | | | | re-scored by `lab luck` | |

Three rows per method, not two, for the *other* reason the comparison can go wrong: the parent's
recorded numbers paid a tenth of a percent a trade, so the twin is compared against the parent's
**cost-report** row, and the recorded row is shown only as history. **Never compare a twin's numbers
to a parent's recorded numbers as if the fees were the same.** Between the two traps — different
fees, and different measures — every cell in this table has to be one or the other, deliberately.

Then, below the table, **one line per skipped method with its reason** — "already measured at real
fees, so there is nothing to redo", "the real fees wipe out its edge, so a twin is not worth
running", "the lab has no such method". A skip is a result and the owner should see it, not have to
notice its absence.

Read the luck bar and the count from `lab status` or `lab luck` and quote those. **Never type a bar or
a count into this file, the report, a synthesis or an analysis** — they are the owner's dials, they
move, and a typed number goes stale the next time they do.

Write the report in everyday words: no backticks, no column names, no ids in the prose. Finish with
the count and the looks as `lab status` prints them, which twins are eligible and what command would
spend a look on one, and the next idea you queued. **No question at the end.**

## Never

| Temptation | Rule |
|---|---|
| "He said purge them, so purge them" | Never. The schema refuses it, and deleting a past try raises every other method's score for free — the exact self-deception the scoring exists to stop. Mint the twins and explain the refusal in his words, early, before he has to ask. |
| "One id in the list is bad, so stop and ask" | Never. Skip that item with its reason and run the rest. A bad id costs one row of the report, not the batch. |
| "This method's run failed, abandon the batch" | Never. Journal it, record the skip, go to the next. A failure never pauses the others. |
| "Fan the batch out into worktrees like Sera does" | No. The research store is not in worktrees, only one session may commit the database, and the commit check runs in the method file's own directory. Serial in the main checkout avoids all three. |
| "Commit all the method files together at the end" | Never. Each commit is that twin's pre-registration and `lab run` refuses an uncommitted file. One commit per twin, before its own run. |
| "`lab stage` after each method so the site keeps up" | No. Once at the end: one redeploy, one binary commit, one coherent story. Stage on any exit, not only on success. |
| "This parent already has a twin row, skip it" | Only if the row carries this skill's marker in its source reference. Two dozen methods have some variation; that is not the same as having been redone. |
| "Delete the twin and redo it, the first run was bad" | Never. A pre-registration deleted and rewritten is a hypothesis written after seeing a number. A different configuration is a new variation of the twin, with its own hypothesis. |
| "Re-run the parent under the new funding" | A method runs once, and funding is permanently not part of what makes a configuration distinct, so the re-run is the same configuration and is refused. If the parent is already fractional at real fees, there is nothing to redo: say so, skip it, continue. |
| "The digest collides; nudge a parameter so it doesn't" | Never. That is a different method pretending to be a redo, and it spends an idea on a question nobody asked. |
| "`lab costs` showed it survives real fees, so it is fine now" | `lab costs` is a report, not a trial. Only the twin can be judged at real fees. |
| "Compare a twin to its parent's recorded numbers" | Not as like for like. The recorded numbers paid a tenth of a percent a trade. Compare against the parent's cost-report row; show the recorded row as history. |
| "Simplify the report: one return column for twin and parent" | **Never.** The twin got deposits and the parent did not, so its total return counts money you paid in as money you made — measured, +1078% against a true earned rate of 7.6% on the same run. One shared column turns that into a lie the owner cannot see. Separate columns, the parent's cell blank and marked unfunded. |
| "The twin returned +1078%, lead with that" | That is not a return. With deposits, total and yearly figures are the shape of the curve — the engine says so and leaves them that way deliberately. Lead with what the money earned, against a SPY fed the same deposits. |
| "The twin's luck score beats its parent's" | You cannot say that. For a funded run the luck score comes from day-to-day account changes, and deposit days look like huge up days. Report it, never compare it, and journal a risk insight if it looks surprisingly strong. |
| "Its worst fall improved on the parent's" | Not necessarily. Deposits keep topping the account up, which makes a fall look shallower. Report it, say that, do not line it up against an unfunded parent's. |
| "Six variants each, to find the best realistic version" | A twin isolates the realism. One variant. More dials and you cannot tell which change moved the number — and the owner wants one row per method, not a grid. |
| "Build it on the plain fractional preset, the fees are close enough" | `lab run` refuses it outright above M0030. The owner pays real fees; a method that only wins at the old assumption does not win. |
| "Write the luck bar into this file so the reader knows it" | Never type a bar or a count anywhere — not in prose, not in a transcript, not in a synthesis. They are the owner's dials and they move. Read them from `lab status`. |
| "`git add -A`, it's quicker" | Never. The checkout is shared; you would commit another session's work in progress. |
| "`git add lab/lab.sqlite`" | Always `lab stage`. It is the only thing that keeps the published snapshot in sync, and CI fails a lab commit without it. |
| "The lab database looks dirty, restore it" | Never `checkout`, `restore` or `stash` it. It is a binary another session may be mid-write in. Come back to clean with a `pull`. |
| "Three twins are eligible — promote them" | Not here, and especially not three. Promotion spends the one counted look per method and belongs to the explore skill or to Sera. |
| "Ask which variant to twin" | You don't. Take each parent's best recorded dev trial by MAR, or the candidate id he pasted. Write the assumption down and continue. |
| "Nothing in the batch survived the fees, stop here" | That *is* the answer he came for, and for a whole batch it is a strong one. Journal it plainly, queue the next idea, report it as a finding. |

## Quick reference

```
lab show M0007                 # a parent, its trials, its verdict (method id only, not a candidate id)
lab status                     # the live count, the live bar, test looks used
lab luck --limit 0             # read-only: every recorded DSR re-scored at today's count
lab costs M0007 [--candidate M0007-N20-RAW]
                               # report only: flat fees vs Gotrade's real ones; journals it, nothing spent
lab idea --name … --family … --source-kind variation --parent M0007 \
         --source-ref "redo-sera-experiments: …" --hypothesis …        # prints the new id
lab run M0032 --store /home/miftah/seer/engine/.research               # needs a committed file
lab note M0032 --file /tmp/twin-M0032.md --verdict "…"
lab insight --kind synthesis --title … --file /tmp/batch.md            # a batch; observation for a single method
lab stage                      # once, at the end: writes the snapshot, git-adds it and the database
```
````

**Impact:** `/redo-sera-experiments` becomes available for one method or a list (skills are
discovered from `.claude/skills/<name>/SKILL.md`; there is no manifest to update). Nothing in the
engine, the web app, the tests or the lab database changes, so both suites are unaffected by this
phase.

## Verification

**Build:** nothing to build. The phase adds one markdown file and touches no source.

```bash
cd /home/miftah/seer
test -f .claude/skills/redo-sera-experiments/SKILL.md
test ! -e .claude/skills/redo-sera-experiment            # the singular must not exist
head -4 .claude/skills/redo-sera-experiments/SKILL.md    # --- / name: redo-sera-experiments / description: / ---
```

**Tests:** the suites must be exactly as green as before the phase, which is the point — the phase
cannot break them.

```bash
cd /home/miftah/seer/engine && ./.venv/bin/python -m pytest -q
cd /home/miftah/seer && ./engine/.venv/bin/python -m ruff check engine
```

In the shared worktree, prefix pytest with the worktree's sources or it silently tests the main
checkout:

```bash
cd /home/miftah/.worktrees/seer/lab-realistic-gate/engine && \
  PYTHONPATH=/home/miftah/.worktrees/seer/lab-realistic-gate/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m pytest -q
```

Never pass `-o addopts` (it drops xdist and the suite goes serial: 342s instead of 62s).

**Manual checks — the things that make a skill fail at 3am:**

1. **The plural name is used everywhere.** The first must print nothing; the second must print the
   marker, the frontmatter name and the invocations:
   ```bash
   cd /home/miftah/seer
   grep -n 'redo-sera-experiment\b' .claude/skills/redo-sera-experiments/SKILL.md   # singular: must be empty
   grep -c 'redo-sera-experiments' .claude/skills/redo-sera-experiments/SKILL.md    # several
   ```

2. **No bar number is typed.** This must print nothing — it is
   `test_lab_gate_wording.BAR_WITH_NUMBER` run by hand, and keeping it empty is why the file needs no
   entry in that test's `SCANNED`:
   ```bash
   grep -nEi '(DSR|luck[[:space:]]+check)[[:space:]]*(>=|≥|of[[:space:]]+at[[:space:]]+least)[[:space:]]*[0-9]+\.[0-9]+' \
     .claude/skills/redo-sera-experiments/SKILL.md
   ```

3. **Every `lab` subcommand it names exists:**
   ```bash
   cd /home/miftah/seer
   for s in costs idea insight luck next-id note run show stage status; do
     ./engine/.venv/bin/python -m seer_engine lab "$s" --help >/dev/null 2>&1 || echo "MISSING: lab $s"
   done
   ```

4. **The three flags that differ from their obvious spelling:**
   ```bash
   ./engine/.venv/bin/python -m seer_engine lab idea  --help | grep -- '--parent'      # --parent, not --parent-id
   ./engine/.venv/bin/python -m seer_engine lab idea  --help | grep -- '--source-ref'  # the marker goes here
   ./engine/.venv/bin/python -m seer_engine lab costs --help | grep -- '--candidate'
   ```

5. **The argument parser handles every documented form.** Paste the skill's own parsing into a shell
   and check it yields three deduped parents, with `M0007`'s variant preserved:
   ```bash
   ARGS="M0022, https://seertrade.site/sera/methods/M0020,M0007-N20-RAW,M0007"
   printf '%s' "$ARGS" | tr ',' '\n' | tr -s ' \t' '\n' | sed '/^$/d' | while read -r ITEM; do
     printf '%s\t%s\n' "$(printf '%s' "$ITEM" | grep -oE 'M[0-9]{4}' | head -1)" \
                       "$(printf '%s' "$ITEM" | grep -oE 'M[0-9]{4}-[A-Z0-9-]+' | head -1)"
   done | awk '!seen[$1]++'
   # expect: M0022 / M0020 / M0007 with variant M0007-N20-RAW
   ```

6. **The measure-mismatch warning is present and the report is not single-column.** All four must
   print at least one hit:
   ```bash
   cd /home/miftah/seer
   F=.claude/skills/redo-sera-experiments/SKILL.md
   grep -c 'never share a column\|must never share a column' $F   # the standing warning
   grep -c 'unfunded' $F                                          # the blank-cell reason
   grep -c 'what your money earned' $F                            # the like-for-like headline column
   grep -c 'not returns at all\|not a return' $F                   # the engine's own framing
   ```
   And the twin-vs-parent trap must be named in the Never table, so it survives a future edit:
   ```bash
   grep -n 'one return column\|one shared column' $F
   ```

7. **The classification query runs read-only and returns nothing on a never-redone lab** (so a first
   batch mints every item rather than wrongly skipping one), **and leaves the file byte-identical:**
   ```bash
   cd /home/miftah/seer && sha256sum lab/lab.sqlite > /tmp/before.txt
   ./engine/.venv/bin/python -c "
   import sqlite3
   c=sqlite3.connect('file:/home/miftah/seer/lab/lab.sqlite?mode=ro',uri=True)
   print('twins:', c.execute(\"SELECT count(*) FROM methods WHERE source_kind='variation' AND source_ref LIKE 'redo-sera-experiments:%'\").fetchone()[0])
   print('funded trials:', c.execute('SELECT count(*) FROM trials t JOIN trial_funding f ON f.trial_n=t.n').fetchone()[0])"
   sha256sum -c /tmp/before.txt     # the read must not have changed the file
   ```
   Expected today: `twins: 0`, `funded trials: 0`, `lab/lab.sqlite: OK`.

**Exit criteria:**

- `.claude/skills/redo-sera-experiments/SKILL.md` exists, plural throughout, with frontmatter in the
  house shape — a `---` block carrying exactly `name:` (`redo-sera-experiments`) and `description:`,
  and the description carrying both batch and single-method trigger phrasings.
- It accepts a comma-separated list of bare ids, method URLs, candidate ids or any mix, with or
  without spaces; dedupes repeated parents; and treats a single method as the one-item case.
- **Refusals are per item.** A bad id, an already-real-fee parent and a parent whose edge the fees
  erase each produce a skip with a reason, and the batch continues. Manual check 5 passes.
- **Per-method isolation is explicit**, and the five-state resume table (S0–S4) is present with the
  marker-based dedupe query, so a re-invocation resumes rather than duplicating.
- The staging decision is stated — once at the end, on any orderly exit — together with what it costs
  on a hard kill and why it does not weaken resume.
- The batch report is one table, a row per method with the money-weighted return against a SPY fed the
  same deposits, plus a line per skip; written in everyday words with no backticks, column names or
  ids in the prose.
- **The report never shares a return column between a twin and its parent.** The twin's total and
  yearly figures sit in their own labelled cells; the parent's equivalents are blank and marked
  *unfunded*; the headline column is what the money earned against a SPY fed the same deposits. The
  plain-words explanation of the two different questions is present where the owner will read it, and
  the same rule is repeated for the per-twin analysis and for the synthesis.
- **The three soft cells are hedged, not compared:** worst fall (deposits soften it), the luck score
  (computed from day-to-day account changes that include deposit days; journal a `risk` insight if it
  flatters), and profit factor / trades (comparable, with later trades weighing more).
- The standing warning against collapsing the report into one shared column is in the skill's own
  `Never` table, not only in its output. Manual check 6 passes.
- The purge refusal is in the **first section**, in plain non-technical language, with the twins named
  as what the owner gets — the schema triggers, the "deleting a try raises everyone else's score"
  argument, `real_costs.py`'s "the only way a real-fee configuration is judged is a new method that
  pre-registers it", and `sera-the-explorer`'s "promote the twin, never the original" all present.
- The three iron rules are present, with rule 1 extended to the batch ("one method's failure never
  stops the batch").
- The pre-registration commit is named prominently, per twin, as the thing that makes `lab run` work.
- House rules are carried: `lab stage` only and always with the published snapshot; the research store
  at `$REPO/engine/.research`; commit by pathspec; never `git add -A` / `reset --hard` / restore the
  database.
- Nothing is promoted anywhere in the skill, and it says why.
- Manual checks 1–6 pass; both suites green; `git status --porcelain` shows the one new file and
  nothing else.

## Handoffs

1. **A funded trial's Sharpe — and therefore its recorded DSR, a *gate condition* — is computed over
   daily returns that include the deposit days. This is for the coordinator and phase 2, and it is
   the most consequential thing this phase found.**

   `_daily_returns` is `equity[i] / equity[i-1] - 1` (`backtest/book_runner.py:536`) with no
   cashflow term; the deposits live separately on `BookResult.cashflows`, which only
   `metrics.external_cashflows` reads. So once `lab run` funds the book, the session a deposit lands
   on records a spurious positive "return" equal to the deposit as a fraction of the book. On the
   owner's plan — +5,000,000 IDR onto a 10,000,000 IDR start — the **first** deposit is roughly
   **+50% in one session**. That spike flows into `_sharpe`, into `runner.daily_moments`, into
   `dev.deflated_sharpe`, and into the `dsr` written to `trials` — which `store.verdict` tests
   against the luck bar. A funded run's luck score is therefore inflated by its own funding, and
   `_year_returns` (`:552`, `value / base - 1` against the *opening* equity) inflates
   `worst_year_return` the same way.

   **Why it is not mine.** `backtest/book_runner.py` appears in neither phase 1's nor phase 2's
   declared file list, and this phase touches no engine source. **Why it cannot simply wait:** unlike
   `total_return` and `cagr` — which `metrics.strategy_metrics` leaves contaminated *deliberately*
   and documents as "not returns at all" — nothing documents or intends this one, and it changes a
   verdict rather than a display. Phase 2's exit criteria ("the gate's money-weighted branch is
   reachable and exercised by a test") would be met by an implementation that still records an
   inflated DSR.

   Options for whoever takes it, cheapest first: compute the daily-return series net of deposits
   (the deposit-day return becomes `(equity[i] - deposit[i]) / equity[i-1] - 1`); or leave
   `daily_returns` alone and have `lab/runner.py:_dsr` take the deposit-adjusted series for a funded
   run; or, if neither is in scope now, record the limitation in phase 2's plan and in the funding
   row's docstring so no reader mistakes a funded DSR for a clean one. **This phase assumes none of
   them**: the skill reports the recorded number, refuses to compare it with the parent's, and
   journals a `risk` insight when it flatters — which is honest under every option above and needs no
   rework once one is chosen.

2. **`mwr` is invisible on every surface the owner sees** (R2's neighbour, not R2 itself). Phase 2
   writes `trial_funding` and `store.owner_failures` judges the funded trial money-weighted — but
   `commands/lab.py:_show` does not print `mwr`/`spy_tr_mwr` and `store.snapshot` does not publish
   them, so the number that makes a twin *honest* never reaches `web/data/lab.json` or
   seertrade.site/sera. This skill compensates with a read-only SQL query, which is a workaround, not
   a fix — and the gap is now worse than for a single twin, because the batch report's headline column
   exists only inside this skill's own output. Publishing funding in the snapshot and printing it in
   `lab show` serves **R2**, so it belongs to phase 2 or a follow-up card, not here. **For the
   reconciler:** if phase 2 publishes it, the skill's report step should read the snapshot and the SQL
   snippet should be deleted.

3. **`engine/tests/test_lab_gate_wording.py:SCANNED`** could gain
   `".claude/skills/redo-sera-experiments/SKILL.md"`, making the "no stale bar number" guard permanent
   for this file instead of a manual check. That module is phase 1's (the index assigns it
   `test_lab_gate_wording.py:188`) and the addition is one line. This phase instead writes the skill
   so it states no bar number at all, which needs no test edit and cannot go stale. Left to phase 1 or
   a card.

4. **No test pins the batch's own invariants**, because the skill is a markdown document and there is
   nothing to import. The two that would be worth pinning if the skill ever grows a helper script: the
   argument parser (manual check 5) and the marker-based classification (manual check 6). A follow-up
   card could add `engine/tests/test_redo_twins.py` asserting that every method whose `source_ref`
   carries the marker is `source_kind='variation'`, has a `parent_id`, and runs at
   `cost_model="gotrade"` — a cheap, real guard against a twin minted wrong by hand. Out of scope
   here: it is a new test module, and this phase touches no test.

5. **No drive-by edits** to `sera-the-explorer/SKILL.md` or
   `explore-and-experiment-new-method/SKILL.md`, though both could now cross-reference
   `/redo-sera-experiments` in their Promotion sections and "Never" tables — Sera's "Promote that old
   flat-fee winner" row in particular now has a skill to point at. The phase scope forbids it and they
   are read-only here. A one-line cross-reference in each is a clean follow-up card.

6. **A roster-driven invocation** (`/redo-sera-experiments --roster`, reading the paper roster and
   twinning every entry) was the owner's original example — "methods that are included in the seer's
   roster". The batch form he settled on takes the ids explicitly, which is strictly more general and
   needs no roster coupling, so this phase stops there. Resolving the roster to a list of parents
   would need `paper/roster.py`, which is nobody's in this plan set. Worth a card once the first batch
   has run.

## Rollback

```bash
cd /home/miftah/seer
git rm -r --cached .claude/skills/redo-sera-experiments    # if already committed
rm -rf .claude/skills/redo-sera-experiments
```

Or, if the phase's commit is the tip: `git revert <sha>`.

That is the whole rollback. The phase creates one file in one new directory, registers nothing,
imports nothing, and changes no engine source, no test, no web asset and no row of `lab/lab.sqlite` —
so removing the directory returns the tree bit-for-bit to its pre-phase state and both suites stay
green either way.

**Nothing the skill *does* when invoked is rolled back by this**, and a batch makes that bigger: the
twins it has already minted are recorded methods with recorded trials, append-only by design, and are
meant to stay. Removing the skill removes the tool, never its results — which is the same property the
skill itself refuses to break when the owner asks it to purge.
