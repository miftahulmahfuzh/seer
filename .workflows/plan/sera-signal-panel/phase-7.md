# Phase 7: Skills, runbook and docs for the two-stage flow

**Plan set:** `SERA_SIGNAL_PANEL_PLAN.md`
**Analysis:** `.workflows/analyze/20261113-200537-K7P2_code_analyzer.md`
**Satisfies:** R5 — Sera and the explore skill route every stock-picking idea through the signal panel, sweep many at once, and launch a child only for a cleared signal or a non-signal idea
**Criteria:** R5.1, R5.2
**Depends on:** Phase 3, 4, 5 (and, through them, 1 and 2)
**Difficulty:** NORMAL
**Package:** `.claude/skills`, `docs`

---

## Goal

The two skills an unattended session executes word for word now describe the two-stage lab.
`sera-the-explorer` gets a first-replay preflight, a **sweep** (Sera writes K signal files, commits
them once, panels them, reads the corrected map), a child slate made only of cleared signals and
non-signal ideas, and one synthesis per run. `explore-and-experiment-new-method` makes a stock-picking
idea a signal before any method file exists, makes queuing a next idea optional, and documents the
one fixed chassis and the three `panel_exempt` prefixes. CLAUDE.md, README.md, the redo skill's
twin-minting passage and the Sera half of the signal-panel runbook say the same thing.

## Interface Contract

**Deletes:** prose rules only:
- `explore-and-experiment-new-method/SKILL.md` iron rule 1's "leaves at least one next idea queued … A run that queues nothing is the only real failure." (line 10-12)
- step 9's mandatory "Queue at least one next idea" (line 308)
- `sera-the-explorer/SKILL.md`'s unscoped "One per family per slate" Never row (line 252)
- Sera's "At least one insight and one queued idea since the child started" check (line 140)
- CLAUDE.md's "queue the follow-up ideas" protocol step (line 89)

**Renames:** Sera's run steps are renumbered: old 3 (slate), 4 (launch), 5 (collect), 6 (refill) and 7 (synthesize) become 4, 5, 6, 7 and 8. A new 2b (first replay) and a new 3 (the sweep) go in ahead of them. Nothing outside this file cites Sera's step numbers. I checked with `grep -rn "sera-the-explorer.*step" .claude docs`, which returns no hits.
**Creates:** prose only. Two new sections are appended to `docs/runbooks/signal-panel.md`: "A sweep, step by step" and "The first replay".
**Signature changes:** none.
**Requires (from earlier phases), by exact name. Each one is checked by J3's `--help` sweep:**
- Phase 3: `lab panel SNNNN [SNNNN ...] | --pending [--store DIR] [--sv-store DIR] [--jobs J]`, `lab panel-map [--top K] [--kind signal|replay|all]`, `lab next-signal-id` (one past both the record and every committed signal file). `lab panel-map`'s verdict column reads `clears` or `no`, with a `why not:` line under a `no`; with no replay rows it prints "no replay panel recorded yet". `lab panel` exits 2 and records nothing for an uncommitted or modified signal file, a non-dev store, or a missing survivorship store. A second `lab panel` on an already-recorded signal records nothing new. `lab panel-map` prints each panel's verdict and names a twin.
- Phase 4: `lab panel-replay [MNNNN ...] [--family-like 'stock-%'] [--limit N] [--store DIR] [--sv-store DIR] [--jobs 1|2]` (`--jobs` accepts only 1 or 2). It skips candidates already recorded on the current dev store and prints `recorded K replay panel(s)`. `--limit N` takes the first N unfinished arms in trial order, previously skipped arms included, so Sera runs the replay without `--limit` (reconciled). It also creates `docs/runbooks/signal-panel.md` (the operator half), whose headings are "A signal sweep (`lab panel`)", "The replay (`lab panel-replay`)", "Checking that nothing frozen moved" and "Who runs the production replay".
- Phase 5: `Method.signal: str | None`, `Method.panel_exempt: str` with the prefixes of `method.PANEL_EXEMPT_KINDS = ("chassis", "control-study", "market")`, each followed by `:` and a reason. The gate's refusal ends "(lab/hardgate.py, D21)"; an unpanelled picker's says it "picks index members (…) and names neither a panelled signal (`signal=`) nor a panel exemption (`panel_exempt=`)", and a signal method with a hand-built arm's says "so its arms are that signal's standard book". `seer_engine.lab.signal_book.standard_candidates(signal, method_id, added)` is the one chassis (`MONTHLY_HOLD_FRAC_GOTRADE`, twenty equal slots from `tree_rank.SCREEN`, one arm behind the SPY 200-day switch, one never stepping aside). It also adds a signal form to `method_template.py`, and the `runner.preflight` refusal (exit 2, no N).
- Phase 1: `engine/src/seer_engine/lab/signals/sNNNN_<slug>.py` exporting `SIGNAL = Signal(...)` with the fields of the shared contract (including `idea_id`). It also creates `.claude/skills/explore-and-experiment-new-method/signal_template.py` and `engine/tests/test_lab_signals.py`.
**Leaves alone (owned by others):** every file under `engine/` and `web/`; `method_template.py` (phase 5); `signal_template.py` (phase 1); `.claude/skills/verify-seer/features/*` (phases 3, 4, 5 and 6); the operator half of `docs/runbooks/signal-panel.md` (phase 4).

## Files

| File | Action | What changes |
|---|---|---|
| `.claude/skills/sera-the-explorer/SKILL.md` | replace whole file (1-268) | Sweep, first replay, child slate scoped to cleared signals and non-signal ideas, one synthesis per run, whole-space `risk` insight, new Never rows |
| `.claude/skills/explore-and-experiment-new-method/SKILL.md` | modify (lines 10-12, 27, 74, 82-90, 121-124, 160-161, 251, 278, 308-313, 318-328, 362-364, 384, 431, 438, 594, 598-615) | Iron rule 1, signal fork 3a and the queued-row procedure, signal limits, the chassis and `panel_exempt`, the panel-gate refusal, optional step 9, gate traps, Never and Quick reference |
| `.claude/skills/redo-sera-experiments/SKILL.md` | modify (after line 332) | Twin carries `panel_exempt="chassis: real-fee twin of M00xx"` |
| `CLAUDE.md` | modify (lines 27-28, 70-80, 84-90) | Layout `lab/signals/` and the panel; the two stages; the protocol order |
| `README.md` | modify (lines 191-193, 334-338, 451-470, 520, 634) | Signals page mention, research section 9, the method-lab tour and diagram, layout, CLI row |
| `docs/runbooks/signal-panel.md` | append (after phase 4's last line) | "A sweep, step by step", "The first replay" |

## Implementation Steps

Every figure quoted below was measured by this planner on 2026-11-13 from `/home/miftah/seer/lab/lab.sqlite`, opened read-only (`mode=ro`), at commit `b0652d2`:
- 197 methods have status `idea`. 194 of them have `source_kind = 'variation'`.
- 138 `idea` rows have a family beginning `stock-`.
- 464 methods have reached a verdict (rejected, dev-eligible or test-failed). 350 of those have a family beginning `stock-`.

The implementer must not change these numbers. They are dated records.

Steps 1, 2 and 6 contain the **complete** text to write. Steps 3-5 and 7 give each changed passage as an exact `old` string and its exact `new` string, for the Edit tool.

### Step 1: Rewrite `sera-the-explorer/SKILL.md`
**File:** `.claude/skills/sera-the-explorer/SKILL.md:1-268`
**Change:** Replace the whole file with the text below. Rules for child sessions that are kept (peer sweep, the 4-at-a-time cap, verify-don't-believe, mirror pairs, twins, promotion steps 0/0b, the claim-verifier gate) are carried over verbatim wherever they still apply. The test `engine/tests/test_lab_gate_wording.py::test_no_shipped_document_states_a_yardstick_bar_the_lab_does_not_apply` requires this file to keep stating "90% of its random twins". The text below keeps that phrase in step 6.
**Code:**

~~~~markdown
---
name: sera-the-explorer
description: Use when asked to explore several new Seer trading methods at once — "/sera-the-explorer <num-methods>", "run N explorations in parallel", "send Sera out", "fan out the method lab", "explore a batch of strategies overnight", "run a signal sweep", "panel the queued stock ideas" — or to resume or check on a Sera batch that is already running.
---

# Sera the explorer

Sera is the coordinator, and the lab has two stages.

**Stage one is the signal panel.** A rule for choosing which stocks to hold is written as a
signal file and measured on a stock-by-month panel of every index member, on the dev store and
on the survivorship store. One false-discovery correction runs across every panel the lab has
recorded. Sera runs stage one herself, in this session, with no children. A **sweep** writes K
signals, commits them in one pre-registration commit, panels them, and reads the corrected map.

**Stage two is the book lab.** A child `/explore-and-experiment-new-method` session runs one
method through `lab run`, in its own git worktree and tmux window. Sera launches a child for
only two kinds of idea:
- a signal that cleared the panel, run as its one fixed book;
- an idea that is not a stock-picking signal at all: a market switch, a brake, portfolio
  construction, a deposit rule or a control study.

Children run at most **4 at a time**. Sera refills a slot when one finishes, until
`<num-methods>` children have been launched. She keeps the shared lab database consistent,
promotes eligible methods, cleans up, and writes **one synthesis per run**, covering the sweep
and every child.

Why two stages: on 2026-11-13, 350 of the 464 methods that had reached a verdict were
stock-picking families. Each of those was tested as one concentrated book, where the luck of
which names landed in the book swamps a typical signal's effect. The panel asks the earlier
question, whether a ranking orders next month's returns across the whole pool, at a fraction of
the cost. Only a ranking that survives the correction earns a book.

**Iron rules, the same as the explore skill: never stop trying; no human in the loop; never
fool ourselves.**
- Sera never asks the user anything, never waits for approval and never ends a turn on a
  question.
- A child that asks anyway gets an answer from Sera, with the reasoning, and the decision goes
  into the lab journal.
- A child's failure never pauses the other slots.
- A sweep in which nothing cleared is a finding, not a failure.

Arguments:
- `<num-methods>` (default 4): how many child sessions this run launches.
- `--sweep K` (default 12): how many signals the sweep writes. `--sweep 0` skips the sweep, for
  a run that only works the non-signal backlog.
- `--permission-mode MODE` (optional, default `bypassPermissions`): passed to every child. Never
  hand a child a broader mode than this session runs under.

## Fixed facts

```
REPO=/home/miftah/seer                         # the main checkout: Sera works here
PY=$REPO/engine/.venv/bin/python               # lab CLI: $PY -m seer_engine lab ...
SWARM=~/.claude/skills/swarm/swarm.py          # `launch` opens a named session in a tmux window
WT=$HOME/.worktrees/seer/explore-MNNNN         # one worktree per child, branch explore/MNNNN
LOGS=$REPO/.workflows/sera/<run-id>/           # gitignored scrollback of finished children, panel and replay output
SV=$REPO/engine/.research-sv                   # the survivorship-check store; children reach it via SEER_SV_STORE=$SV
SIGNALS=$REPO/engine/src/seer_engine/lab/signals                              # one signal per file: sNNNN_<slug>.py exporting SIGNAL
SIGNAL_TEMPLATE=$REPO/.claude/skills/explore-and-experiment-new-method/signal_template.py
```

Only Sera commits `lab/lab.sqlite`, and always through `lab stage`. `lab stage` takes the write
lock, so a child's half-written transaction is never committed. Under the same lock it
regenerates `web/data/lab.json`, the snapshot seertrade.site/sera is built from, and stages
both files.
- **Every `lab stage` commit includes `web/data/lab.json`.** CI fails a database commit
  without it, and Vercel redeploys the site from each push.
- Commit a stage with `git commit -m "…"` and **no pathspec**. A pathspec re-reads both files
  from the working tree and undoes the snapshot the stage took under the lock.
- Children commit only their method files, straight to `main`. These are distinct new files,
  so a rebase never conflicts.
- Sera commits signal files herself, in the sweep's one pre-registration commit (step 3e). A
  child never writes or panels a signal.

## The run

1. **Name yourself.** Use `sera-<YYYYMMDD-HHMM>` as both run id and name:
   `python3 ~/.claude/skills/task/session.py rename sera-<stamp> --no-widen`. Never let that block.
1b. **Peer sweep: is another Sera already out?** The owner may start a second batch while one is
   running. Two batches that never talk reserve and explore the same ideas. Do this before
   preflight and before choosing anything:
   - **Find the peers.** Check `tmux list-sessions` and `tmux list-windows -a -F '#S #W'` for
     other `sera-*` sessions and live `explore-M*` windows (skip your own). Check
     `git -C $REPO worktree list` for `explore/MNNNN` branches. In Claude Code, `ListAgents`
     shows peer `sera-*` sessions too.
   - **Ask each live peer coordinator.** `SendMessage` to `sera-<its stamp>`: "Sera <your stamp>
     is starting a batch. Reply with every method id, signal id and idea you are exploring,
     sweeping or have queued, one line each (id, mechanism, family), your remaining slot count,
     and whether a `lab panel` or `lab panel-replay` of yours is running." Wait a few minutes at
     most for the reply, then go on. If a peer doesn't answer, or has no `SendMessage` (a
     non-Claude coordinator), read its pane instead: `tmux capture-pane -p -S - -t <session>`.
   - **The database is the truth, the reply is a hint.** Cross-check against `lab status` and
     `lab seen`. They show every id a peer has reserved or registered, because the lab database
     is shared through `SEER_LAB_DB`. Also check `ls $SIGNALS`, which shows every signal file a
     peer has committed.
   - **Keep an exclusion list** of the peers' ideas, families and mechanisms for the whole run.
     Step 4's child slate and every step-7 refill must avoid it: the same family or the same
     mechanism counts as a repeat, not only the same id. Re-read `lab status` at each refill,
     since the peer keeps reserving.
   - **For the sweep,** a peer's family is allowed, because the correction counts both
     sweeps. A peer's ranking is not: skip any signal whose rule a peer's reply or a committed
     signal file already holds.
   - **Share capacity.** The 4-at-a-time cap is across all Seras on this machine, not per Sera,
     because eight children at once is the memory crash the cap exists to prevent. Count live
     `explore-M*` windows and launch only `4 - live` children now; the rest wait for a slot in
     step 7.
   - **One store-loader at a time.** `lab panel` and `lab panel-replay` load both research
     stores. Never start yours while a peer's runs (`ps -eo args | grep '[l]ab panel'` lists
     them) or while any child's `lab run` is live. Wait, re-checking every few minutes.
   - If no peer exists, this step costs nothing: carry on.
   - Never ask the owner about any of this, and never touch a peer's windows, worktrees,
     reservations or signal files. Note the peer and the exclusion list in the run's report.
2. **Preflight** in `$REPO`:
   - **Sync.** Run `git pull --rebase --autostash` **only if step 1b found no peer batch
     running**. With children live, autostash rewrites `lab/lab.sqlite` under their open
     connections; use `git fetch` + `git merge --ff-only origin/main` instead (see Never).
   - **Lab tests green:** `cd engine && .venv/bin/python -m pytest -q tests/test_lab_*.py`.
     This set includes `test_lab_signals.py`, the signal contract.
   - **Snapshot check.** `test_lab_snapshot.py` fails whenever `lab/lab.sqlite` changed without
     `lab stage`, for example after an interrupted batch or replay. If that is the only failure,
     run `lab stage`, commit both files, push, and run the tests again. Always test after
     staging, never before.
   - **Stores.** `engine/.research/` must be present; build it if not. `engine/.research-sv/`
     must be present: `$PY -m seer_engine survivorship_store --report` prints its coverage, and
     `docs/runbooks/survivorship-store.md` says how to rebuild it if it is missing. The panel
     needs both stores. Each child exports `SEER_SV_STORE=$SV` from the explore skill's table,
     so it can keep a survivorship-check promise the same day.
   - **tmux.** Check `$TMUX`. If there is **no tmux**, don't stop: do steps 2b and 3 here, then
     run the explore skill **solo, sequentially**, once per child idea, in this session, then do
     step 8.
2b. **First replay, once per lab.** Before the panel can judge anything, it needs the map of what
   the lab already tried: every recorded dev candidate of every method whose family begins
   `stock-`, replayed as a pick set.
   - **When.** Run `lab panel-map --kind replay`. Replay if it prints "no replay panel recorded
     yet", or if
     `git -C $REPO log origin/main --oneline --grep 'lab: panel replay'` shows batches but no
     `lab: panel replay complete` commit (an interrupted replay). Otherwise skip this step.
   - **Where.** From `$REPO`, never from a worktree: the replay writes the shared database.
     Never while any child's `lab run` (yours or a peer's) or another `lab panel` is live.
   - **How.** Run it whole, with no `--limit`. Make the `lab panel-replay` itself the Bash call
     with `run_in_background: true`, redirected to a file, and never add `&` or `nohup`.
     `docs/runbooks/signal-panel.md` records how long it took on this machine.
     ```bash
     $PY -m seer_engine lab panel-replay --family-like 'stock-%' --store $REPO/engine/.research --sv-store $SV --jobs 2 > $LOGS/replay-<k>.txt 2>&1
     ```
     Then `lab stage`, `git commit -m "lab: panel replay, batch <k>"`, push. If it was
     interrupted, run it again: a finished arm is not measured twice. It is done when a run
     prints `recorded 0 replay panel(s)`. Never use `--limit` here: it counts arms that were
     skipped before, so once enough of them sit at the front of the queue a limited batch records
     nothing while work remains.
   - **Synthesis.** Then write the map's synthesis: one `lab insight --kind synthesis --title
     "Sera <stamp>: the map of every stock-picking rule the lab has tried"`. Base it on
     `lab panel-map --kind replay`. Gate it through the `claim-verifier` exactly as in step 8.
     In everyday words, it says:
     - how many recorded books were replayed;
     - how many distinct pick sets that came to, once twins are collapsed;
     - how many cleared the correction;
     - which kinds of ranking lead and which read as noise;
     - what that means for the queued ideas.
   - **Publish.** `lab stage`, `git commit -m "lab: panel replay complete — the map of the
     explored space"`, push. Then go on to step 3 in the same run.
3. **The sweep (stage one), in this session, before any child runs.** Skip it with `--sweep 0`.
   Also skip it when a peer's children or store-loaders stay live for the whole run (step 1b),
   and say so in the report.
   a. **Choose K ideas** (default 12), each a rule for choosing which stocks to hold.
      - **Backlog first, oldest first.** These are the `idea` rows whose family begins `stock-`
        (138 on 2026-11-13). List them read-only; a `lab` command would migrate the database
        on connect:
        ```bash
        $PY - <<'EOF'
        import sqlite3
        c = sqlite3.connect("file:/home/miftah/seer/lab/lab.sqlite?mode=ro", uri=True)
        for row in c.execute(
            "SELECT id, family, name FROM methods "
            "WHERE status = 'idea' AND family LIKE 'stock-%' ORDER BY id"
        ):
            print(*row, sep="  |  ")
        EOF
        ```
        `lab show MNNNN` gives a row's hypothesis.
      - **Sort each row into one of three kinds:**
        - **A ranking.** Its new part is which stocks it picks. It becomes a signal in this
          sweep, with `idea_id="MNNNN"`.
        - **A wrapper on another method's picks.** Its new part is a brake, a cadence, a
          sizing or an exposure dial on a book whose picks come from a named host. It is not a
          signal. It is judged by the host's replay verdict in `lab panel-map --kind replay`:
          - The host's picking cleared: the idea stays a child-session idea and goes to the
            child slate (step 4) with `panel_exempt="chassis: <the wrapper> on <host candidate>'s
            picks"`.
          - The host did not clear: `lab drop MNNNN --why "panel: its picks are <host>'s, which
            did not clear the panel"`. A dial on a ranking the panel read as noise is not run.
        - **Not about stocks at all** (a market switch, a deposit rule, a control study). It
          goes to the child slate unchanged.
      - **Then new rankings** from fresh web research (SSRN, arXiv q-fin, Quantpedia, Alpha
        Architect, quant blogs), until the sweep holds K.
      - **The one-per-family rule and "at least one web idea per slate" do not apply to a
        sweep.** A sweep may hold twelve variants of one family. The correction, not diversity,
        guards against luck, and every variant counts in it.
      - **Testable on the store's data and inside the signal contract.** A signal is pure and
        reads bars dated on or before the data date only. Its lookback is at most 473 bars. A
        signal that reads company fundamentals scores names only from 2009, where the
        fundamentals panel starts, so its before-2009 era is empty.
      - **Not already measured.** Run `lab seen --find <words>` for each idea, and do not
        repeat a ranking the map already holds.
   b. **Number them.** `lab next-signal-id` prints the first free id: one past both the panel
      record and every committed signal file, so a peer's committed but unpanelled signal never
      shares your number. Number the sweep consecutively from it (S00aa … S00bb).
   c. **Write each file** as `$SIGNALS/sNNNN_<slug>.py` from `$SIGNAL_TEMPLATE`, exporting
      `SIGNAL = Signal(...)` with these fields:
      - `id`;
      - a plain `name` that says what it ranks on;
      - a `family` named by what it ranks on;
      - `source_kind` (`paper`, `blog`, `github`, `knowledge` or `variation`) and `source_ref`.
        A backlog row's signal copies the row's family, source kind and source ref;
      - `hypothesis` and `expected_failure`, written now, before any number exists;
      - `lookback` (1-473);
      - `score` (higher is better; a name with no opinion gets no value);
      - `market_fields`, when it reads market series or share counts;
      - `seen_keys`;
      - `idea_id`, for a backlog row.
   d. **Test.** `cd $REPO/engine && $PY -m pytest -q -n0 tests/test_lab_signals.py && $PY -m
      ruff check src tests`. If the contract test fails, fix the signal; never weaken the test.
   e. **One commit for the whole sweep. That commit is the pre-registration.**
      - Sync first with `git fetch origin main -q && git merge --ff-only origin/main`, then
        run `test_lab_signals.py` again. A duplicate id means a peer pushed a signal with your
        number first: renumber yours from a fresh `lab next-signal-id`.
      - Then name every file of the sweep explicitly:
        `git add -- <each file>` and `git commit -m "lab: sera <stamp> pre-registers
        S00aa..S00bb" -- <each file>`, then `git push origin HEAD:main`.
      - If the push is rejected, run `git reset --soft HEAD~1 && git reset`, sync, test and
        commit again. Nothing has been measured yet, so nothing is spent.
      - `lab panel` refuses an uncommitted or modified signal file (exit 2, nothing recorded).
   f. **Panel them.** Run this as the Bash call itself, with `run_in_background: true` and no
      `&`:
      ```bash
      $PY -m seer_engine lab panel --pending --store $REPO/engine/.research --sv-store $SV --jobs 2 > $LOGS/panel.txt 2>&1
      ```
      - **What it measures.** `--pending` panels every committed signal that has no panel on
        these stores. Each one is measured on both stores, over the whole window, before 2009
        and 2009-2015. For each, it gives the months measured, the rank correlation and its t,
        the top-minus-pool spread a year and its t, and the slope on next month's return after
        removing momentum, beta, size and volatility, with its t.
      - **What it costs.** It records no trial and leaves N unchanged.
      - **Exit codes.** Exit 2 means refused and nothing recorded: an uncommitted file, a store
        that is not the dev store, or a missing survivorship store. Fix the cause and run it
        again.
      - **Publish.** Then `lab stage`, `git commit -m "lab: sera <stamp> panels S00aa..S00bb"`,
        push.
   g. **Read the map once the whole sweep is recorded.** Run `lab panel-map --kind signal`,
      and `--kind all` for the replays beside it.
      - The verdict is computed on read across every recorded panel, so a sweep's own panels
        move the bar for everyone. Never judge one signal before the rest of its sweep is in.
      - A signal **clears** only when all three hold:
        - its dev whole-window controlled slope is positive, and survives the correction
          across every distinct pick set the lab holds;
        - its dev 2009-2015 top-minus-pool spread is positive;
        - its survivorship whole-window slope is positive.
      - The map's verdict column reads `clears` or `no`, and a `why not:` line under each `no`
        names every failed condition in plain words.
   h. **Act on each signal of the sweep:**
      - **Cleared.** It earns one book. A backlog signal keeps its row's id (`idea_id`). A new
        idea is reserved now:
        `lab idea --name "<signal name>" --family <signal family> --source-kind <signal
        source_kind> --hypothesis "The one fixed book of signal S00xx: <what it ranks on>.
        Panel: <the three readings in words>."`
        It goes first in the child slate.
      - **Not cleared, backlog row:** `lab drop MNNNN --why "panel: <the map's reason, in plain
        words>"`. An idea with no trial costs no N.
      - **Not cleared, new idea:** there is nothing to drop. The signal file and its panel are
        the record.
      - **Never edit a signal after its panel.** A changed parameter is a new signal id, in a
        later sweep, and it counts in the correction.
      - Then `lab stage`, `git commit -m "lab: sera <stamp> sweep verdicts: reserves M00xx,
        drops M00yy"`, push.
4. **Choose the child slate.** It holds up to `min(4 - live, num-methods)` ideas, chosen in
   this order:
   - cleared signals from step 3, one child each;
   - then non-signal ideas: market switches, brakes, portfolio construction, deposit rules,
     control studies, and the wrappers step 3a routed here. Draw them from `lab status`, recent
     insights and closest-to-eligible trials, plus fresh web research.

   **Never launch a child for a stock-picking idea that has not cleared the panel.** `lab run`
   refuses it anyway (exit 2), and a child spent finding that out is a wasted slot.

   What each reserved hypothesis must say:
   - **A cleared signal's book** needs nothing about the chassis. It is fixed:
     `standard_candidates` on `MONTHLY_HOLD_FRAC_GOTRADE`, one arm behind the SPY 200-day
     switch and one never stepping aside.
   - **Any other book idea:** write that it runs in fractional shares at Gotrade's real fees,
     on a `-frac-gotrade` preset, so the child builds it that way.
   - **A non-signal idea whose book picks index members** names its exemption. The child writes
     it into the method file as `panel_exempt`, using one of three prefixes:
     - `chassis: …`: how a book is built or traded changes, and its picks are a named host's.
     - `market: …`: a market-wide switch decides how much to hold, not which stocks.
     - `control-study: …`: the method exists to measure a control.

   Rules for a child slate:
   - **Diverse, among the non-signal ideas:** no two in the same family or the same mechanism.
     Mix sources: backlog, a variation of a near miss, and at least one new web-researched
     idea per slate when the slate has room. These rules are for child slates only, never for a
     sweep. Cleared signals are not held to the family rule, since each earned its book. Two
     cleared signals that `lab panel-map` shows as twins (the same picks) get one child.
   - **Testable on the store's data** (daily OHLCV, dividends, membership, ≤ 2015-10-16) and not
     already in `lab seen`.
   - **Survives real fees?** Before reserving a variation of a near miss from M0030 or earlier,
     run `lab costs <near miss>` (a minute or less, report only, N unchanged). A near miss whose
     edge the real fees erase is not worth a variation; journal that and pick another.
   - **A repeated book is refused, not recorded.**
     - `lab run` compares every arm's finished equity curve and trade count with the record
       *before* it writes anything.
     - If an arm's book was first recorded by **another** method and the arm does not say so,
       the run exits 2 and names the arm and the first recording (`M0246-SPY200 = M0205-SPY200,
       first recorded (trial 690, …)`). Nothing is recorded, no arm's result is printed and no N
       is spent.
     - An arm says so in one of two ways, both in its committed rationale: it is a control
       ("Control: …"), or it names the method it repeats (M0488's never-aside arm names M0125).
     - A batch whose **every** arm repeats a recorded book is refused even when all are
       declared, because it would measure nothing new (every arm of M0447 did).
     - A wrapper allocator or params class that gives a host a new digest no longer slips past.
       The refusal reads the curve, not the digest.
   - **Read the neighbour list before you settle a slate.**
     - `lab idea …` prints the new id on stdout. On stderr it prints up to five methods already
       in the lab whose name, family and hypothesis share the most words with it. It is a hint
       and never refuses.
     - If one is the same idea, `lab drop MNNNN --why "same idea as M00xx"` (an idea with no
       trial costs no N) and choose another.
     - Otherwise write the closest one into the hypothesis ("closest recorded: M00xx, which …")
       so the child designs against it.
   - **Cite a recorded control, don't re-run it.**
     - `lab idea …` also lists, on stderr, the controls those neighbours already hold, named by
       first recording (`M0108-DD20  trial 342, …, current store`). Put the ones that fit the
       frame into the reserved hypothesis ("control cited: M0108-DD20, trial 342"), so the child
       does not spend an arm re-measuring them.
     - Batch 0721 re-ran eight such arms (M0545, M0561, M0606). Each was accepted as a declared
       control and added a trial row and run time with no new evidence.
     - Cite a listed control only when the child's own control would be the same rules,
       allocator and params, and the line says `current store`. Anything else is run as a
       declared control, as before. Nothing about `lab run`'s repeat refusal changes.
   - **Reserve** each new idea with `lab idea …`, which prints its id. A backlog row keeps its id.
     The hypothesis can be a draft; the child sharpens it before its pre-registration commit.
   - Then `lab stage` + `git commit -m "lab: sera <stamp> reserves M00xx, M00yy"` + push.
5. **Launch each reserved idea:**
   ```bash
   git -C $REPO fetch origin main -q
   git -C $REPO worktree add -b explore/MNNNN $WT origin/main
   python3 $SWARM launch --name explore-MNNNN --cwd $WT --repo $REPO --permission-mode <mode> \
     --prompt "/explore-and-experiment-new-method --method MNNNN --coordinator sera-<stamp>"
   ```
   - **Subscribe** to each child (`SendMessage` with `notify_when_idle: true`, no message), so a
     child that dies without reporting still wakes you.
   - **If this coordinator is not a Claude Code session** (it has no `SendMessage` tool, for
     example it runs under Hermes), skip the subscription. Poll
     `tmux capture-pane -p -t explore-MNNNN` plus the shared database instead.
   - A child that reports "no agent named sera-<stamp> is reachable" is behaving correctly. That
     message is not a failure and needs no relaunch.
6. **Collect.** Each child sends `DONE MNNNN <status> — <verdict>; next: M00xx` (or
   `next: none`) when it can reach the coordinator. With a non-Claude coordinator, read its
   pane. For every child that reports or goes idle:
   - **Verify, don't believe:**
     - `lab show MNNNN`: status past `registered`, trials present, analysis and verdict
       non-empty. For a signal book, the method names its signal, and its non-control arms are
       the standard chassis (`lab run` refused anything else).
     - `git log origin/main -- engine/src/seer_engine/lab/methods/mNNNN_*` is non-empty.
     - At least one insight since the child started. A queued idea is expected only when the
       child's result named one. The explore skill's step 9 is optional, and `next: none` is a
       valid report.
     - **If one arm reverses another, is there a third arm with no opinion in it?**
       - `lab run` prints a `Mirror pairs:` block when two of a method's arms differ in exactly
         one reversing setting. It says `unpriced` when nothing always-invested can price them.
       - The explore skill asks children for that third arm at design time. This is the only
         place anything re-checks.
       - A reversed arm alone proves the *signal* is real and says nothing about what *acting*
         on it costs, because both arms pay that cost equally and it cancels. Measured
         2026-10-21 (insight 523): 22 of 28 recorded pairs can never be priced.
       - The repair is an Amendment in the child's own method file, so it costs no method id
         and no N. Ask the child for it while its worktree is still open, or write it yourself.
         `lab dressing MNNNN` says what is recoverable and journals nothing.
       - Report it in the synthesis either way. A batch that measured its signals and not their
         price is a finding about the batch.
     - **Which arms are book twins?**
       - `lab twins MNNNN` (the `Book twins` block `lab run` printed) names each arm's role and
         the first-recorded trial with the same curve.
       - Read it before relaying any arm's money or metrics, wherever the figure came from: a
         child's `DONE` line, `lab show`, or `/calculate-assets`.
       - A control's or a book twin's money is never reported as a new book; name it by its
         first-recorded candidate. The case that made this rule: M0488-DVC10-NEVER was relayed
         as a new book, and it is M0125-DV-C10 (trial 519), the book the owner already holds as
         DEEPTAPE.
       - A treatment arm that shares its own control's curve means the treatment never acted. A
         dose ladder whose rungs are one curve means the dial never moved. Both go in the
         synthesis as findings, not as books.

     Whatever is missing, finish it yourself from the scrollback and the data. If the method
     never ran, relaunch it once. If it fails again, `lab drop MNNNN --why "<reason>"` plus a
     `risk` insight. A signal book that `lab run` now refuses because its signal stopped
     clearing (later panels joined the correction) is dropped the same way:
     `--why "panel: no longer clears after later panels joined the correction"`.
   - **dev-eligible:** run the explore skill's **Promotion** yourself, now, in `$REPO`, one at a
     time.
     - Start with its step 0, the fit check, then **step 0b, the durability check**: `lab
       regime`, `survivorship_coverage.py`, and `lab walkforward`.
     - Four test looks are spent and all four failed on `beats SPY TR`. They bought **two**
       distinct books, not four (M0021, M0022 and M0029 are one book; only M0002 is separate),
       so the record is 0-for-2 and the budget was spent twice on the same thing. Quote both
       numbers.
     - A good twenty-year average is still not evidence, and `lab walkforward`'s buy signal now
       reports one row per book, not per method id.
     - **`lab promote` now refuses, it does not warn.** Since 2026-10-09 it exits 2 unless the
       method beat SPY in a majority of at least four scoreable walk-forward folds **and** no
       kin reads `test-failed`. Kin is its `family` plus every ancestor through `parent_id`.
       **There is no override and no flag.**
     - When it refuses: record it (`lab note`, and a `risk` insight if the whole family is now
       closed), put the reason in the run's report, and move to the next idea. You do not ask
       the owner, you do not pause the batch, and you do not go looking for a way round. The
       iron rules hold here exactly as everywhere else.
     - `lab status` shows every dev-eligible method's fold record and, under "Refused by the
       hard gate", the reason. Check it *before* you plan a promotion.
     - `lab promote` also refuses an arm with no random-twin reading that clears (hardgate D20):
       an arm must have out-earned at least 90% of its random twins. An arm recorded before
       2026-11-14 may not be measured yet; `lab yardstick MNNNN` measures it, then promote again.
     - Step 0b also carries the buy signal, which you report and never block on.
     - **A signal book (allocator `SB-S00xx`) that turns dev-eligible and promotable** cannot be
       promoted yet: `lab promote` and the paper roster resolve an allocator by preset id, and a
       signal book is built per signal. Do not try. Record
       `lab insight --kind feature-wish --title "Promote a signal book: the resolver must rebuild SB-S00xx from its signal"`,
       and put it FIRST in the run's report. It is the first follow-up the panel set left open.
     - If the eligible variant trades whole shares, or is a method from M0030 or earlier
       measured at the flat 0.1%, first run `lab costs` on it. Then run its fractional, real-fee
       twin as a one-variant variation method, with `panel_exempt="chassis: real-fee twin of
       M00xx"` when it picks index members. Promote the twin, never the original. The look is
       spent on the configuration paper would trade, or not at all.
   - **Close it out:**
     - Save the scrollback: `tmux capture-pane -p -S - -t <window> > $LOGS/explore-MNNNN.log`.
       tmux keeps a short history, so a log of about one screen is normal; the database is the
       audit record, not the log.
     - Kill the window, but only if it is still named `explore-MNNNN`.
     - `git worktree remove --force $WT`, then `git branch -D explore/MNNNN` (only once its
       method file is on `origin/main`).
   - `lab stage` + commit + push the database and its snapshot, `lab/lab.sqlite` and
     `web/data/lab.json` ("lab: M00xx <verdict>").
7. **Refill.** While launched < num-methods, pick the next child idea for the free slot from the
   **current** lab, so later ideas learn from earlier results (the children's queued ideas
   included).
   - **What to pick:** a cleared signal not yet booked, else a non-signal idea. Reserve it and
     launch it. Never let a slot sit idle while such ideas remain.
   - **A stock-picking idea that turns up mid-batch** (a child's queued idea, a fresh thought)
     waits for the next sweep. Never launch a child for it.
   - **Between batches**, when no child is running, the coordinator may do either of two jobs.
     Never do either while children run: each holds two workers or both stores, and so does
     each child's `lab run`.
     - Work down the yardstick backfill: `lab yardstick --pending --limit N --jobs 2`
       (`docs/runbooks/yardstick-backfill.md`), then `lab stage` + commit + push ("lab:
       yardstick backfill, batch k").
     - Run a further sweep (step 3).
   - A child never demotes, promotes, panels, replays or runs the backfill.
8. **Synthesize once per run.** Do it when the sweep is panelled and num-methods children are
   closed out. With no children, do it right after the sweep. There is never one synthesis per
   four methods.

   **Gate it before you write it.**
   - Every child figure arrived in a `DONE` line or a pane, so it is someone else's
     measurement. The synthesis itself is append-only: it cannot be edited once it is in.
   - Read the run's numbers back from the database yourself:
     - the sweep's readings and verdicts from `lab panel-map`;
     - the verdict table and each method's eligibility;
     - above all the buy signal, whose four conditions are claims about runs you did not watch
       finish.
   - Hand the draft synthesis and the closing tables to the `claim-verifier` subagent
     (`Agent(subagent_type="claim-verifier", …)`), and treat `BLOCK` as final. A synthesis is
     the one artifact built mostly from other agents' numbers, so it is the one where
     self-checking is weakest.
   - The explore skill's **The gate** is the pass. The claim format and emission map are in
     `/verify-claims`.

   Then add **one insight**: `lab insight --kind synthesis --title "Sera <stamp>: <theme>"
   --body …`.
   - The newest synthesis is the headline of seertrade.site/sera, the first thing the owner
     reads, and the owner is not a trader. Write it in everyday words. Name signals and methods
     by what they do, not by `S00xx`, `MNNNN` or candidate ids. Leave out code, hashes, column
     names and backticks.
   - Write the correction in words ("after allowing for every ranking the lab has tried").
     Never write it as "the bar is N%": the site's wording test reads the newest synthesis and
     compares any stated bar with the lab's drawdown and luck bars.

   Cover:
   - **the sweep:**
     - how many signals it panelled;
     - how many cleared the correction;
     - what the three readings said across them, in words, and which held and which broke: the
       controlled slope on the dev store, the 2009-2015 top-minus-pool spread, and the slope on
       the store with the dead companies back;
     - which queued ideas were dropped because of it.
   - **a sweep in which nothing cleared says so as its finding,** first, not as an apology.
   - **the whole-space verdict.** It applies when `lab panel-map --kind all` shows no cleared
     panel after the full replay (step 2b) **and** step 3a's backlog query returns no ranking
     left.
     - Write this insight:
       `lab insight --kind risk --title "Price-and-volume stock picking is closed in this universe"`.
     - Its body, in plain words: how many rankings and recorded books the panel measured; that
       none survived the correction on both stores; and what is left to try (market switches,
       brakes, portfolio construction, new data).
     - Say it first in the report. Do not ask the owner about it.
   - what the books taught: each cleared signal's book and each non-signal child;
   - which directions look alive and which look dead;
   - what data or features would unlock the most;
   - **the buy signal, every run, even when the answer is no.**
     - State plainly whether any method this run cleared all four of:
       - dev-eligible at the bars in force;
       - no method in its family has test-failed;
       - a majority of walk-forward folds beaten (`lab walkforward`);
       - a *positive* edge in the highest-coverage era 2009-2015
         (`engine/scripts/survivorship_coverage.py`).
     - That conjunction is the only moment survivorship-free price history is worth buying.
       The explore skill's Promotion step 0b says why, and what it costs.
     - If nothing cleared it, say "no buy signal this run" and why. With no book run, the why is
       that no method ran a book.
     - If something did, it is the FIRST line of the report, not a footnote, and it also goes in
       as a `lab insight --kind risk`.
     - Say too whether the hard gate refused anything this run, and on which of the two
       conditions. A run where every promotion was refused is a finding about the lab, and the
       owner should read it in the synthesis rather than infer it from silence.
   - what Gotrade's real fees did to the run, when any `lab costs` ran or a method lost its edge
     to them;
   - what the next sweep should try.

   Then `lab stage`, commit (`lab/lab.sqlite` and `web/data/lab.json`), push. The site picks the
   synthesis up from that push with no other step.

   End with a short report:
   - the whole-space verdict first, if it was written; the buy signal first, if it fired;
   - a table of the sweep's signals: signal, family, cleared or not, the dev controlled slope
     and its t, the 2009-2015 spread, the survivorship slope;
   - a table of method, verdict, CAGR vs SPY, max DD, PF, trades, DSR. A row for a control or a
     book twin says so and names its first-recorded candidate (`lab twins MNNNN`); it is never
     listed as a new book;
   - the synthesis;
   - N and test looks used. The panel never moves N.

   No question at the end.

## Never

| Temptation | Rule |
|---|---|
| "Ask the owner which ideas to try" | Sera chooses. That is the job. |
| "Ask the owner whether the universe is closed" | Never. The map answers it. Write the `risk` insight (step 8) and say it first in the report. |
| "Launch a child for this stock-picking idea, the panel is slow" | Never. A rule for choosing stocks is a signal first: the sweep panels it, and only a cleared signal gets a child. `lab run` refuses an unpanelled picking method (exit 2). |
| "Write a `panel_exempt` on this picking rule to get past the gate" | Never. An exemption is a claim in the pre-registration. A new ranking under `chassis:` falsifies it exactly as relabelling a treatment as a control does. |
| "Re-run that signal with a tweaked lookback, it nearly cleared" | A tweak is a new signal id, written and committed as its own pre-registration in a later sweep, and it counts in the correction. Never edit a signal file after its panel. |
| "Two children on momentum variants, they're promising" | One per family per **child** slate: diversity beats depth among books. A **sweep** may hold twelve momentum variants, because the correction, not diversity, guards against luck. |
| "Panel the sweep while the children run" or "replay beside a live `lab run`" | Never. `lab panel` and `lab panel-replay` load both research stores. Sweep first, children after; replay only when nothing else is loading a store. |
| "Judge the first signal before the rest of the sweep is panelled" | Never. The verdict is computed across every recorded panel, so read `lab panel-map` once the whole sweep is in. |
| "`git add lab/lab.sqlite`" | Always `lab stage`. A child may be mid-write, and only `lab stage` keeps `web/data/lab.json` in sync. |
| "A child failed, pause the batch" | Never. Close it out, record it, refill the slot. |
| "Kill that window, it looks done" | Verify first, capture the scrollback, check the name. |
| "Promote the whole-share winner, it passed dev" | Never. A 20M IDR book can't buy 2016+ stocks in whole shares, so the look measures cash. Run the fractional twin first (M0021's lesson). |
| "Promote that old flat-fee winner, it passed dev" | Never as is. Run `lab costs` first, then its real-fee twin as a one-variant variation method (with its `chassis:` exemption); promote the twin. |
| "Promote in parallel" | Promotions are serial and done by Sera. Each spends one counted test-window look. |
| "`git pull --rebase --autostash` before each lab commit" | Only at preflight, before any child runs. Mid-batch, autostash rewrites `lab/lab.sqlite` on disk under a child's open connection (SQLite then reports "readonly database", and a write in that window is lost). Sync with `git fetch` + `git merge --ff-only origin/main` (it leaves untouched dirty files alone), then `lab stage`, commit, push; if the push is rejected, `git reset --soft HEAD~1 && git reset` and repeat. |
| "It passed dev, that's the gate" | Not since 2026-10-09. Four test looks are spent, all four failed on `beats SPY TR`, and they bought two distinct books, not four -- 0-for-2, and three looks went to one book (insight 529). Run Promotion step 0b before every look, and check the candidate against the books already spent. |
| "The buy signal fired, I'll ask the owner first" | Never ask, never block. Record the insight, put it first in the report, carry on. |
| "`lab promote` refused it, I'll find a way round" | There is no way round. No `--force`, no environment variable, no editing the method to dodge the kin walk. Record the refusal, report it, take the next idea. |
| "Its fold record is 2 of 4 but the twenty-year numbers are great" | That is the gate's entire point, and the 0-for-5 roster is what the twenty-year numbers bought. `lab promote` exits 2. |
| "That older method sits in the Promotable-now list, so promote it" | The list is the gate's letter, not the durability check. Run `lab walkforward` first; a negative 2009-2015 edge means no look. A batch promotes its own children's results, not an earlier batch's leftovers. |
| "Its sibling test-failed, but this variant is genuinely different" | Kin is `family` plus every ancestor through `parent_id`. A disproven family does not get a retry under a new id — that is the mechanism the gate exists to close. |
| "The control made the most money, report it as a find" | A control, or a book twin of a recorded trial, is never a new book. Run `lab twins MNNNN` and name it by its first-recorded candidate (M0488-DVC10-NEVER is M0125-DV-C10). |
| "This follow-up wraps a recorded host, so skip it" or "so count it as a new book" | Neither. Re-measuring the host is fine as a *declared* control, which runs beside the treatment. Undeclared, `lab run` refuses it. Name the host in the hypothesis and the arm's rationale, and never count the arm as a new book. |
| "`lab run` refused a repeated book, ask the owner" or "mark the treatment as a control to get it through" | Neither. The child changes the arm so it holds a new book, or declares it truthfully if re-measuring is the point, re-commits the method file (the new pre-registration) and re-runs. No owner step, and nothing was spent. Relabelling a treatment as a control to pass the check falsifies the pre-registration. |
~~~~

**Impact:** `test_lab_gate_wording.py` scans this file for the yardstick bar. "90% of its random twins" survives in step 6, so that test stays green. Nothing in this file states a luck or drawdown bar as a number. Sera's next run follows the new procedure.

### Step 2: Iron rule 1 and the two-modes table (explore skill)
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:10-12` and `:27`
**Change:** Two Edit calls.

Edit 2a. Old:
```markdown
1. **We never stop trying, we never give up.** Each run explores **one idea** end to end,
   records every trial, writes what it learned, and leaves at least one next idea queued. A
   failed method is a result. A run that queues nothing is the only real failure.
```
New:
```markdown
1. **We never stop trying, we never give up.** Each run explores **one idea** end to end,
   records every trial or panel, and writes what it learned. A failed method is a result, and
   so is a signal that did not clear the panel. A run queues a next idea only when its result
   names one (step 9). On 2026-11-13, 194 of the 197 ideas waiting in the queue were variations
   nobody had run: a rule that made every run add one built a pile, not a search.
```

Edit 2b. Old:
```markdown
| idea | you choose it | already reserved as an `idea` row `MNNNN`; refine it, keep its id |
```
New:
```markdown
| idea | you choose it; a rule for choosing which stocks to hold is a signal first (step 3a) | already reserved as an `idea` row `MNNNN`: either the book of a signal that cleared the panel (its hypothesis names `S00xx`; build its one fixed chassis, step 4) or an idea that is not a stock-picking signal (refine it, keep its id). A child never writes or panels a signal |
```
**Impact:** Prose only. The R5.2 queue rule is now stated.

### Step 3: Step 2's packet, the signal fork 3a, and the signal limits (explore skill)
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:74`, `:89-91`, `:121-124`
**Change:** Three Edit calls.

Edit 3a. Old:
```markdown
   > • N, the DSR bar, and test looks spent, as `lab status` prints them
```
New:
```markdown
   > • N, the DSR bar, and test looks spent, as `lab status` prints them
   > • if the reserved row names a signal `S00xx`: its readings and verdict as `lab panel-map`
   >   prints them
```

Edit 3b. Old:
```markdown
   - **backlog**: an `idea` row. Reuse its id.

   Then check:
```
New:
~~~~markdown
   - **backlog**: an `idea` row. Reuse its id.

   **The first fork: is this a rule for choosing which stocks to hold?** Then it is a
   **signal**, and it goes through the panel before any method file exists.
   - This applies to every new picking rule. It also applies to every queued idea row whose
     family begins `stock-` and whose new part is a ranking.
   - It does not apply to a market switch, a brake, portfolio construction, a deposit rule or a
     control study. Those go straight to step 4 as a method with a `panel_exempt` reason.
   - Two rules do not apply to signal ideas: "queue at least one next idea" (gone, step 9) and
     Sera's one-per-family slate rule. A sweep may hold many variants of one family, because
     every variant counts in the panel's correction.
   - Child mode never takes this fork. A child is handed the book of a signal that already
     cleared, or a non-signal idea.

   **3a. A signal (solo; Sera does the same for a whole sweep):**
   1. **Write the file.** `lab next-signal-id` prints the id (`S00xx`). Write
      `engine/src/seer_engine/lab/signals/s00xx_<slug>.py` from `signal_template.py` (this
      folder). It exports `SIGNAL = Signal(...)` with these fields:
      - `id`;
      - a plain `name`;
      - a `family` named by what it ranks on;
      - `source_kind` and `source_ref`;
      - `hypothesis` and `expected_failure`, written **now**, before any number exists;
      - `lookback` (at most 473 bars);
      - `score` (higher is better; a name with no opinion gets no value);
      - `market_fields`, if it reads market series or share counts;
      - `seen_keys`;
      - `idea_id="M00yy"`, when it answers a queued idea row.
   2. **A queued stock-signal idea row becomes a signal like this.** `lab show M00yy` gives the
      row's name, family and hypothesis.
      - **Its new part is which stocks it picks.** The signal copies the row's family, source
        kind and source ref, sharpens the hypothesis into a score, and sets `idea_id="M00yy"`.
        The row keeps its id for the book, if the signal clears.
      - **Its new part is a brake, a cadence or a sizing dial on another method's picks.** It
        is not a signal. It is judged by the host's replay verdict in
        `lab panel-map --kind replay`. If the host cleared, go to step 4 with
        `panel_exempt="chassis: <the wrapper> on <host candidate>'s picks"`. If the host did not
        clear, run `lab drop M00yy --why "panel: its picks are <host>'s, which did not clear the panel"`.
   3. **Test.** `cd engine && pytest -q tests/test_lab_signals.py && ruff check src tests`. Fix
      the signal; never weaken the test.
   4. **Commit only the signal file and push it.** The commit is the pre-registration:
      `lab: S00xx pre-registered — <the idea in plain words>`. `lab panel` refuses an
      uncommitted or modified signal file (exit 2, nothing recorded).
   5. **Panel it:** `lab panel S00xx`. Run it like `lab run` in step 6: the command itself, in
      the background, redirected to a file.
      - It measures the signal on the dev store and on the survivorship store, each over the
        whole window, before 2009 and 2009-2015.
      - For each, it reports the months measured, the rank correlation and its t, the
        top-minus-pool spread a year and its t, and the slope on next month's return after
        removing momentum, beta, size and volatility, with its t.
      - It records no trial, and N does not move.
   6. **Read the verdict in `lab panel-map`.** A signal clears only when all three hold:
      - its dev whole-window controlled slope is positive, and survives the false-discovery
        correction across every distinct pick set the lab has recorded;
      - its dev 2009-2015 spread is positive;
      - its survivorship whole-window slope is positive.

      The verdict names each failed condition in plain words. It is computed on read, so it can
      change as later panels join the correction.
   7. **Journal one insight** (step 8) saying what the panel found, in plain words. Gate it
      first.
   8. **Stop unless it cleared.**
      - **Not cleared:** drop the idea row it answered,
        `lab drop M00yy --why "panel: <the verdict's reason, plain>"`. Then `lab stage`, commit,
        push, and report (step 11). Do not write a method file. Do not tweak the signal and
        panel it again: a changed parameter is a new signal id, and it counts in the correction.
      - **Cleared:** keep `M00yy`, or reserve the book with `lab idea …`, and go to step 4's
        signal form.

   Then check:
~~~~

Edit 3c. Old:
```markdown
     size-weighted book should still carry a weight ceiling (M0047).
     If it isn't testable:
```
New:
```markdown
     size-weighted book should still carry a weight ceiling (M0047).
     A **signal** has two more limits. Its lookback is capped at 473 bars, the smoke fixture
     every lab rule is checked on. A signal that reads company fundamentals has a panel only
     from 2009, where the fundamentals panel starts, so its before-2009 era is empty.
     If it isn't testable:
```
**Impact:** This states R5.2's three parts: the panel comes before any method file; the queue rule and the slate rule do not apply to signals; and a queued stock-signal row becomes a signal by the procedure in item 2.

### Step 4: Step 4's two forms, step 6's refusal, step 7's comparison (explore skill)
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:160-161`, `:251`, `:278`
**Change:** Three Edit calls.

Edit 4a. Old:
```markdown
4. **Write** `engine/src/seer_engine/lab/methods/mNNNN_<slug>.py` from `method_template.py`
   (this folder). Solo: the id comes from `lab next-id`, or from the backlog row.
```
New:
```markdown
4. **Write** `engine/src/seer_engine/lab/methods/mNNNN_<slug>.py` from `method_template.py`
   (this folder). Solo: the id comes from `lab next-id`, or from the backlog row.
   - **A cleared signal: one fixed chassis.**
     - The method file names the signal and takes its arms from the signal book:
       `signal="S00xx"` and `candidates=standard_candidates(...)` from
       `seer_engine.lab.signal_book`, as `method_template.py`'s signal form shows, plus any
       declared controls.
     - That is twenty equal slots from the pool, on `MONTHLY_HOLD_FRAC_GOTRADE`, with one arm
       behind the SPY 200-day switch and one never stepping aside.
     - No hand-written allocator, no extra treatment arm, no dial. The panel already chose the
       ranking; the book only prices it.
     - `lab run` refuses a signal method that has any other non-control arm (exit 2, nothing
       recorded, no N spent).
     - Fractional shares, real fees and the mirror's third arm (bullets below) are already true
       of the chassis. The control-citing bullet still applies.
   - **Not a signal: name the exemption.** `lab run` refuses a method that has an arm picking
     index members but no cleared signal (exit 2, no N spent), unless the method carries
     `panel_exempt`. That is one line beginning with one of three prefixes:
     - `chassis: …`: the idea changes how a book is built or traded (width, weights, cadence,
       a brake on the book's own account, a deposit rule, real fees), and its picks are a named
       host's. Examples: `chassis: real-fee twin of M0029`, `chassis: per-stock 200-day exit on
       a book of every eligible member`.
     - `market: …`: a market-wide switch decides how much to hold, not which stocks. Example:
       `market: VIX term-structure switch over M0007-N20-RAW's picks`.
     - `control-study: …`: the method exists to measure a control (a random draw, a placebo, a
       blind arm).

     The exemption is a claim in the pre-registration, and it is honest only when it is true.
     An arm whose picks differ from the named host's by a ranking is a signal, whatever the
     line says. Writing `chassis:` on a new picking rule to get past the gate falsifies the
     pre-registration, exactly as relabelling a treatment as a control does.
```

Edit 4b. Old:
```markdown
   `lab run MNNNN` again (`--amend` for an amendment). Never relabel a treatment as a control to
   get past the check.
```
New:
```markdown
   `lab run MNNNN` again (`--amend` for an amendment). Never relabel a treatment as a control to
   get past the check.
   **Exit 2 whose message ends "(lab/hardgate.py, D21)"** is the panel gate, and it has one of
   these causes. "picks index members (…) and names neither a panelled signal (`signal=`) nor a
   panel exemption (`panel_exempt=`)": the method has a picking arm and no answer. "so its arms
   are that signal's standard book": it names a signal and carries a non-control arm that is not
   the signal's standard book. "has no panel on the dev store this run would load", "did not
   clear the panel on this dev store" or "no longer hashes to the sha its panel was measured on":
   the named signal is not cleared on this store as committed. Nothing was recorded and no N was
   spent. Fix it without asking anyone:
   - A picking idea goes back to step 3a as a signal (child: report `blocked` with the line).
   - A signal method is rebuilt from `standard_candidates` alone, plus declared controls.
   - A true chassis change, market switch or control study adds its honest `panel_exempt` line.

   Then re-commit and re-run. A signal that cleared when the run was planned can stop clearing
   when later panels join the correction, because the verdict is computed on read. Solo: then
   `lab drop MNNNN --why "panel: no longer clears after later panels joined the correction"`.
   Child: report `blocked` with that reason. Never add an exemption to a picking rule to get
   through.
```

Edit 4c. Old:
```markdown
   - whether the hypothesis held and whether the expected failure happened
```
New:
```markdown
   - whether the hypothesis held and whether the expected failure happened
   - for a signal's book: what the panel's three readings predicted, against what the book did
```
**Impact:** Prose only. These lines name phase 5's refusal and fields; Handoffs asks the reconciler to check them.

### Step 5: Optional step 9, the report formats, the gate, promotion twins, Never, Quick reference (explore skill)
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:308-313`, `:318-319`, `:324`, `:362-364`, `:383-384`, `:431`, `:438`, `:594`, `:598-615`
**Change:** Nine Edit calls.

Edit 5a. Old:
```markdown
9. **Queue at least one next idea**: `lab idea --name … --family … --source-kind … --hypothesis …`
   (plus `--parent`), drawn from what this result taught. It prints the new id on stdout and, on
   stderr, the five methods already in the lab whose wording is closest. Read them. If one is
   the same idea, `lab drop` the new id with the reason. Otherwise name the closest recorded
   method in the hypothesis so the next session designs against it. The same stderr also
   lists the controls those methods hold; cite them in the next hypothesis instead of re-running.
```
New:
```markdown
9. **Queue a next idea only when the result names one (optional).**
   - Why optional: a queue entry nobody will run is noise. On 2026-11-13, 194 of the 197 ideas
     in the queue were variations nobody had run (iron rule 1). If the result names no next
     step, queue nothing, and say `next: none` in the report.
   - When it does name one: `lab idea --name … --family … --source-kind … --hypothesis …` (plus
     `--parent`). It prints the new id on stdout. On stderr it prints the five methods already
     in the lab whose wording is closest. Read them. If one is the same idea, `lab drop` the
     new id with the reason. Otherwise name the closest recorded method in the hypothesis, so
     the next session designs against it. The same stderr also lists the controls those methods
     hold; cite them in the next hypothesis instead of re-running.
   - A next idea that is a rule for choosing stocks waits in the queue for a sweep, which turns
     it into a signal (step 3a). A signal that did not clear never queues its own tweak: a
     tweak is a new signal, written in a later sweep, and it counts in the correction.
```

Edit 5b. Old:
```markdown
      that push. Then give a short report: idea, result vs SPY, verdict, insight, next idea, N, test looks.
```
New:
```markdown
      that push. Then give a short report: the idea (for a signal, its three readings and
      whether it cleared), result vs SPY when a book ran, verdict, insight, next idea or "none",
      N, test looks. A panel never moves N.
```

Edit 5c. Old:
```markdown
      `DONE MNNNN <rejected|dev-eligible|blocked> — <verdict>; next: M00xx`. When it reports no
```
New:
```markdown
      `DONE MNNNN <rejected|dev-eligible|blocked> — <verdict>; next: M00xx` (or `next: none`
      when the result named no next step). When it reports no
```

Edit 5d. Old:
```markdown
Every number you are about to write goes in a row — result vs SPY, N, the DSR bar, DSR itself,
worst year, the fall, exposure, turnover, trades, the parent comparison, the fold record, every
method, candidate and insight id.
```
New:
```markdown
Every number you are about to write goes in a row — result vs SPY, N, the DSR bar, DSR itself,
worst year, the fall, exposure, turnover, trades, the parent comparison, the fold record, every
panel reading (months, the controlled slope and its t, the 2009-2015 spread, the survivorship
slope, the corrected q) and verdict, and every method, candidate, signal and insight id.
```

Edit 5e. Old:
```markdown
  owner as a new book; it is M0125-DV-C10, first recorded as trial 519.

## Promotion
```
New:
```markdown
  owner as a new book; it is M0125-DV-C10, first recorded as trial 519.
- **A panel verdict moves.** It is computed on read, across every recorded panel. A "clears" or
  a q copied from an earlier `lab panel-map` may be stale, so read it again right before
  writing it.
- **A panel reading is not a book.** A cleared signal has not beaten SPY, and has no DSR, until
  its book has run. Never write a panel's spread as a return.

## Promotion
```

Edit 5f. Old:
```markdown
   one variant, the same config on the `-frac` twin, run it on dev, and promote that one if it is
```
New:
```markdown
   one variant, the same config on the `-frac` twin (with `panel_exempt="chassis: fractional
   twin of MNNNN"` when it picks index members), run it on dev, and promote that one if it is
```

Edit 5g. Old:
```markdown
   promote it. If it still passes, register its real-fee twin as a one-variant variation method
```
New:
```markdown
   promote it. If it still passes, register its real-fee twin as a one-variant variation method
   (with `panel_exempt="chassis: real-fee twin of MNNNN"` when it picks index members)
```

Edit 5h. Old:
```markdown
| "Nothing worked, stop here" | Journal the insight and queue the next idea. |
```
New:
```markdown
| "Nothing worked, stop here" | Journal the insight and report it. Queue a next idea only if the result names one (step 9). A signal that did not clear is a finished result, not a failure. |
| "This picking idea is obviously good; skip the panel and write the method" | Never. A rule for choosing stocks is a signal first (step 3a). `lab run` refuses an unpanelled picking method (exit 2). |
| "The panel nearly cleared; nudge the lookback and panel it again" | A changed parameter is a new signal id, written and committed as its own pre-registration, and it counts in the correction. Never edit a signal file after its panel. |
| "Mark it `panel_exempt`, it's basically a chassis change" | Only when it is true: the picks are a named host's. A new ranking under an exemption falsifies the pre-registration. |
| "Add a second treatment arm to the signal's book" | Never. A cleared signal runs on one fixed chassis (`standard_candidates`); `lab run` refuses any other non-control arm. |
| "Queue a next idea, the old rule says every run must" | Not any more. 194 of the 197 queued ideas on 2026-11-13 were variations nobody had run. Queue one only when the result names it. |
```

Edit 5i. Old:
````markdown
lab status | lab show M0007 | lab next-id | lab seen --find momentum
lab run M0007                     # needs a committed method file; exit 2 if an undeclared arm repeats another method's book
````
New:
````markdown
lab status | lab show M0007 | lab next-id | lab seen --find momentum
lab next-signal-id                # the next free signal id
lab panel S0003                   # stage one: a committed signal on the dev and survivorship stores, three eras; no trial, N unchanged; exit 2 if uncommitted
lab panel --pending               # every committed signal with no panel on the current stores
lab panel-map --top 20 --kind signal   # every panel ranked by its controlled slope, with the corrected verdict; --kind replay|all
lab run M0007                     # needs a committed method file; exit 2 if an undeclared arm repeats another method's book, or a picking arm has no cleared signal and no panel_exempt
````
**Impact:** Prose only. These lines contain no luck-bar or drawdown number, so `test_lab_gate_wording.py`'s `SCANNED` sweep of this file stays green.

### Step 6: Append the Sera half of the runbook
**File:** `docs/runbooks/signal-panel.md`, appended after phase 4's last line
**Change:** Append the text below verbatim, preceded by one blank line. Phase 4 owns everything above it. If phase 4 used either heading itself, rename ours to "A sweep, step by step (Sera)" / "The first replay (Sera)" and leave theirs alone.
**Code:**

~~~~markdown
## A sweep, step by step

This section is for Sera (`.claude/skills/sera-the-explorer`, step 3) or a solo explore session
panelling one signal. Run it in the main checkout, where the research stores live. Run it only
when nothing else is loading a store:
- no child's `lab run`: `tmux list-windows -a -F '#S #W' | grep explore-M` prints nothing;
- no other `lab panel` or `lab panel-replay`: `ps -eo args | grep '[l]ab panel'` prints
  nothing.

```bash
REPO=/home/miftah/seer
PY=$REPO/engine/.venv/bin/python
SV=$REPO/engine/.research-sv
LOGS=$REPO/.workflows/sera/<run-id>
cd $REPO

# 1. Ids: the first free one (it counts committed signal files with no panel yet), then consecutive.
$PY -m seer_engine lab next-signal-id

# 2. Write one engine/src/seer_engine/lab/signals/sNNNN_<slug>.py per idea from
#    .claude/skills/explore-and-experiment-new-method/signal_template.py, then name them all:
SWEEP="engine/src/seer_engine/lab/signals/s0003_<slug>.py engine/src/seer_engine/lab/signals/s0004_<slug>.py"

# 3. The contract test (purity, unique ids, no look-ahead) and lint.
(cd engine && $PY -m pytest -q -n0 tests/test_lab_signals.py && $PY -m ruff check src tests)

# 4. The pre-registration: one commit for the whole sweep, by explicit path.
git fetch origin main -q && git merge --ff-only origin/main
git add -- $SWEEP
git commit -m "lab: sera <stamp> pre-registers S0003..S0004" -- $SWEEP
git push origin HEAD:main

# 5. Stage one: every committed signal with no panel on these two stores.
$PY -m seer_engine lab panel --pending --store $REPO/engine/.research --sv-store $SV --jobs 2 > $LOGS/panel.txt 2>&1; echo "exit $?"

# 6. Publish the panel rows.
$PY -m seer_engine lab stage
git commit -m "lab: sera <stamp> panels S0003..S0004"
git push origin HEAD:main

# 7. The corrected verdicts, once the whole sweep is recorded.
$PY -m seer_engine lab panel-map --kind signal
$PY -m seer_engine lab panel-map --kind all
```

| `lab panel` exit | Meaning | What to do |
|---|---|---|
| 0 | every pending signal was recorded, or nothing was pending | read the map (step 7 above) |
| 2 | refused; nothing recorded: a signal file uncommitted or modified, a store that is not the dev store, or no survivorship store | commit the file, point `--store` at `engine/.research`, or rebuild the survivorship store (`docs/runbooks/survivorship-store.md`), then run again |
| 1 | an error | read the traceback in `$LOGS/panel.txt`, fix, run again; a signal already recorded on these stores is skipped |

After reading the map, act on each signal of the sweep:
- **Cleared.** Reserve its book with `lab idea`, or keep the queued row the signal's `idea_id`
  names. Hand it to one child: a method file with `signal="S00xx"` and `standard_candidates(...)`
  plus declared controls, nothing else.
- **Not cleared.** `lab drop M00yy --why "panel: <reason>"` for the queued row it answered.
  Nothing, for a new idea.

Then `lab stage`, commit, push. A signal file is never edited after its panel; a tweak is a new
signal id in a later sweep. Every `lab panel`, `lab panel-replay` and `lab panel-map` leaves the
luck gate's N unchanged.

## The first replay

The replay records one pick-set panel per recorded dev candidate of every method whose family
begins `stock-`. It touches no trial, config digest or method file. It is the first job of the
panel, and it is run **once per lab, by Sera's preflight** (`sera-the-explorer`, step 2b), from
the main checkout. No plan phase and no worktree ever runs it against the shared
`lab/lab.sqlite`.

**When.** Run it when `lab panel-map --kind replay` prints "no replay panel recorded yet", or when `main` carries
`lab: panel replay, batch <k>` commits but no `lab: panel replay complete` commit (an
interrupted replay).

**Never** run it while a child's `lab run`, a sweep's `lab panel` or a peer's replay is live.
Each of these loads the research stores, and five concurrent sessions have already taken this
machine down.

```bash
REPO=/home/miftah/seer
PY=$REPO/engine/.venv/bin/python
SV=$REPO/engine/.research-sv
LOGS=$REPO/.workflows/sera/<run-id>
cd $REPO

# The whole replay in one run, no --limit (it counts previously skipped arms; see "The replay" above).
$PY -m seer_engine lab panel-replay --family-like 'stock-%' --store $REPO/engine/.research --sv-store $SV --jobs 2 > $LOGS/replay-<k>.txt 2>&1; echo "exit $?"
$PY -m seer_engine lab stage
git commit -m "lab: panel replay, batch <k>"     # no pathspec: lab stage staged both files under its lock
git push origin HEAD:main
```

If a run was interrupted, run it again (batch k+1): a finished arm is not measured twice. It is
done when a run prints `recorded 0 replay panel(s)`. Then read `lab panel-map --kind replay`: twins
are collapsed, and each row has its corrected verdict.

Write the map's synthesis as one `lab insight --kind synthesis`, in plain words, gated by the
`claim-verifier` subagent. It says:
- how many recorded books were replayed;
- how many distinct pick sets that came to;
- how many cleared;
- which kinds of ranking lead and which read as noise;
- what that means for the queued ideas.

Then publish it:

```bash
$PY -m seer_engine lab stage
git commit -m "lab: panel replay complete — the map of the explored space"
git push origin HEAD:main
```

If the map shows no cleared panel, and the queue has no stock-picking ranking left, Sera writes
the `risk` insight that names this universe as closed for price-and-volume stock picking
(`sera-the-explorer`, step 8).
~~~~
**Impact:** Prose only. The file is phase 4's creation; this step only adds to its end.

### Step 7: CLAUDE.md, README.md and the redo skill
**File:** `CLAUDE.md:27-28`, `:70-80`, `:84-90`; `README.md:191-193`, `:334-338`, `:451-470`, `:520`, `:634`; `.claude/skills/redo-sera-experiments/SKILL.md:331-332`
**Change:** Ten Edit calls.

Edit 7a (`CLAUDE.md`). Old:
```markdown
  - `lab/`: pre-registration, N policy, hard gate, DSR. `lab/methods/mNNNN_<slug>.py` holds one
    method per file, each exporting `METHOD = Method(...)`.
```
New:
```markdown
  - `lab/`: pre-registration, N policy, hard gate, DSR. `lab/methods/mNNNN_<slug>.py` holds one
    method per file, each exporting `METHOD = Method(...)`. `lab/signals/sNNNN_<slug>.py` holds
    one stock-picking signal per file, each exporting `SIGNAL = Signal(...)`. `lab/panel.py`
    measures a signal on a stock-by-month panel (stage one), and `lab/signal_book.py` is the one
    fixed book a cleared signal runs as (stage two).
```

Edit 7b (`CLAUDE.md`). Old:
```markdown
- The method file must be **committed before** `lab run MNNNN`. That commit is the
  pre-registration, and the runner refuses uncommitted or already-run digests.
```
New:
```markdown
- The method file must be **committed before** `lab run MNNNN`. That commit is the
  pre-registration, and the runner refuses uncommitted or already-run digests.
- **Two stages.** A rule for choosing which stocks to hold is a signal first. Commit its file
  (get the id from `lab next-signal-id`); then `lab panel SNNNN` measures it on the dev store and
  the survivorship store, records the readings append-only and spends no N. `lab panel-map`
  ranks every panel under one false-discovery correction, computed on read. Only a signal that
  clears gets a method, and that method is `signal="SNNNN"` plus `standard_candidates(...)`.
  `lab run` refuses (exit 2) a method with an arm that picks index members unless it names a
  cleared signal or carries `panel_exempt` (`chassis:`, `market:` or `control-study:`). A signal
  file is never edited after its panel; a tweak is a new id.
```

Edit 7c (`CLAUDE.md`). Old:
```markdown
- Commit messages follow the existing style: `lab: M00NN pre-registered — …` and
  `lab: M00NN rejected (plain reason)`.
```
New:
```markdown
- Commit messages follow the existing style: `lab: M00NN pre-registered — …`,
  `lab: M00NN rejected (plain reason)`, `lab: S00NN pre-registered — …` and, for a sweep,
  `lab: sera <stamp> pre-registers S00aa..S00bb`.
```

Edit 7d (`CLAUDE.md`). Old:
```markdown
hand-written random arm is a control, not the luck test) → survivorship and sanity check → record
the verdict (accept or reject) in the journal → queue the follow-up ideas → report to the
coordinator. Pre-registration is not skippable, least of all when the result looks obvious.
```
New:
```markdown
hand-written random arm is a control, not the luck test) → survivorship and sanity check → record
the verdict (accept or reject) in the journal → queue a follow-up idea only when the result names
one → report to the coordinator. A stock-picking idea runs a shorter order first, as a signal:
verify the store → commit the signal file → `lab panel` → read the corrected verdict in
`lab panel-map` → journal → stop unless it cleared. Only a cleared signal goes on to the steps
above, as its one fixed book. Pre-registration is not skippable, least of all when the result
looks obvious.
```

Edit 7e (`README.md`). Old:
```markdown
| **Ideas** — the backlog, the blocked-on-data wishlist, the reading list | **How it works** — the path, the calendar, the hurdles, the honesty rules |

Every chart on these pages is hand-built SVG
```
New:
```markdown
| **Ideas** — the backlog, the blocked-on-data wishlist, the reading list | **How it works** — the path, the calendar, the hurdles, the honesty rules |

**Signals** (`/sera/signals`) is the map of the lab's first stage. It shows every stock-picking
rule the lab has measured on the signal panel, its own new ideas and the replayed picks of every
book it already ran, ranked. Each rule is named by what it does, with its verdict in everyday
words.

Every chart on these pages is hand-built SVG
```

Edit 7f (`README.md`). Old:
```markdown
Two skills drive the lab end to end with nobody in the loop: one explores a single idea
(pre-register → run → plain-language analysis → at least one insight → at least one queued idea),
and one fans out several of those in parallel, each in its own git worktree and terminal window,
promotes what qualifies, and closes the batch with a synthesis. Every roster change, promotion and
rejection is journalled.
```
New:
```markdown
Two skills drive the lab end to end with nobody in the loop. A stock-picking idea is first
written as a signal and measured on a stock-by-month panel of every index member, on two data
stores, under one false-discovery correction across every panel ever recorded. Sera writes and
panels a dozen at a time in one session. Only a signal that survives the correction becomes a
book: one pre-registered method on one fixed chassis, run by a child session in its own git
worktree and terminal window. An idea that is not a stock-picking rule (a market switch, a
brake, a deposit rule) goes to a child the same way. Sera promotes what qualifies and closes each
run with one synthesis. Every roster change, promotion and rejection is journalled.
```

Edit 7g (`README.md`). Old:
````markdown
not match its database, and the site reads only that snapshot.

```
idea  →  pre-registered file (committed)  →  dev run  →  verdict
                                                 │
                                        dev-eligible?  →  promote  →  one test-window look
                                                 │                          │
                                              rejected                 pass / fail
                                                                            │
                                                                     forward paper
                                                                            │
                                                                       18 months
                                                                            │
                                                                       real money
```
````
New:
````markdown
not match its database, and the site reads only that snapshot.

The lab has two stages.

**Stage one is the signal panel.** A rule for choosing which stocks to hold is a signal: a
committed file with a pre-registered hypothesis, scored for every index member at every month
end of the development window. `lab panel` measures how well that score orders next month's
returns, on the development store and on a second store that has the dead companies back. It
reads the whole window, before 2009, and 2009-2015 apart. It gives a rank correlation, a
top-minus-pool spread, and a slope after removing momentum, beta, size and volatility, each with
its t-statistic.

The panel carries its own multiple-testing correction, Benjamini-Hochberg across every distinct
pick set ever recorded, the lab's replayed books included. For that reason a panel never counts
toward the luck gate's N. A signal clears only when three things hold: its controlled slope
survives that correction, its 2009-2015 spread is positive, and its slope stays positive with
the dead companies back.

**Stage two is the book lab below**, and it runs a cleared signal on one fixed chassis only.
`lab run` refuses a stock-picking method whose signal has not cleared.

```
stock-picking idea  →  signal file (committed)  →  panel: two stores, three eras, one correction
                                                                │
                                                     clears?  ──┴── no  →  recorded; nothing spent
                                                        │
                                                       yes
                                                        │
other idea  ─────────→  pre-registered file (committed)  →  dev run  →  verdict
                                                                │
                                                       dev-eligible?  →  promote  →  one test-window look
                                                                │                          │
                                                             rejected                 pass / fail
                                                                                           │
                                                                                    forward paper
                                                                                           │
                                                                                      18 months
                                                                                           │
                                                                                      real money
```
````

Edit 7h (`README.md`). Old:
```markdown
    lab/           pre-registration, the N policy, the derived verdict, methods/
```
New:
```markdown
    lab/           pre-registration, the N policy, the derived verdict, methods/, signals/, the panel
```

Edit 7i (`README.md`). Old:
```markdown
| `lab run/test/promote/remeasure/reevaluate/luck/status/costs/names` | The method lab |
```
New:
```markdown
| `lab run/test/promote/remeasure/reevaluate/luck/status/costs/names` | The method lab |
| `lab panel/panel-map/panel-replay/next-signal-id` | Stage one: measure stock-picking signals on the panel, rank them under the correction |
```

Edit 7j (`redo-sera-experiments/SKILL.md`). Old:
```markdown
- `source_kind="variation"`, `parent_id=$MNNNN`, `family` = the parent's family verbatim, and
  `source_ref` = **the same marker-prefixed string you reserved with**.
```
New:
```markdown
- `source_kind="variation"`, `parent_id=$MNNNN`, `family` = the parent's family verbatim, and
  `source_ref` = **the same marker-prefixed string you reserved with**.
- **`panel_exempt="chassis: real-fee twin of $MNNNN"`**, with the parent's id written out (for
  example `chassis: real-fee twin of M0029`).
  - A twin changes how its parent trades, not which stocks it picks, and that is what a
    `chassis:` exemption says.
  - Without it, `lab run` refuses any twin whose parent picks index members (exit 2, nothing
    recorded, no N spent). Since the signal panel landed, a stock-picking method must name a
    cleared signal or carry an exemption.
  - `m0029_blend_fractional.py` predates the field, so the copy does not carry the line. Add it.
  - Never write any other text there: the exemption is a claim in the pre-registration.
```
**Impact:** Prose only. Nothing under README's "Where the search stands" changes. That table is a dated record ("As of the committed snapshot (2026-10-08)").

## Principles applied

- Laziness protocol: CLAUDE.md, README and the redo skill get the smallest edits that keep them true. "Where the search stands" and the rest of README are untouched. In the explore skill only the passages the new flow contradicts are rewritten, as targeted edits, not a whole-file rewrite. Sera's skill is the exception, rewritten whole, because its step order itself changes.
- Build the lever: a "does every command exist" check is tedious and error-prone by eye. J3 is a script that extracts every `lab <cmd> --flag` from the six touched files and checks each against that command's real `--help`. I prototyped it here against today's files: 27 commands in the two skills, 0 bad.
- Encode lessons in structure: two traps found while planning are now explicit rules in the steps, not left to an implementer's memory.
  - The site's wording test (`test_lab_gate_wording.py`) reads the newest synthesis and both skills, so Sera is told to write the correction in words, never as "the bar is N%" (step 1, step 8). The neighbor check runs that test.
  - A `lab stage` commit with a pathspec undoes the stage, so Sera's skill says "no pathspec" once, in its ownership paragraph.
- Make illegal states unrepresentable (applied as prose): the three `panel_exempt` prefixes are each defined by when they are honest. An exemption on a new ranking is named as falsifying the pre-registration, so the rule matches phase 5's code-level prefix check rather than inviting free text.

## Verification

**Build:** none (prose only). `PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m ruff check engine` stays green, since no Python changes.
**Tests:** `cd engine && PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q -n 2 tests/test_lab_gate_wording.py`. It scans both skills for stated luck and yardstick bars.
**Proof:** the two SKILL.md files, read mechanically, carry the procedures R5.1 and R5.2 require. Every `lab` command and flag that any touched file names exists in the landed CLI.
- Harness: `.claude/skills/verify-seer`. Its feature map is not touched by this phase. The CLI behaviour these docs name is proven by phases 3, 4 and 5 through `features/signal-panel.md` and `features/lab-cli.md`. This phase's journeys are grep plus `--help`, run from the worktree root with no Postgres and no store.
- Feature-map entries: none. Skills and docs are not a user-facing surface of the app. The surfaces they describe have entries owned by phases 3, 4, 5 and 6.
- Setup for every journey: `cd /home/miftah/.worktrees/seer/sera-signal-panel && S=$(mktemp -d) && cp /home/miftah/seer/lab/lab.sqlite $S/lab.sqlite && export SEER_LAB_DB=$S/lab.sqlite PYTHONPATH=$PWD/engine/src PY=/home/miftah/seer/engine/.venv/bin/python`
- Journeys:
  - **J1** · traces R5.1 — `F=.claude/skills/sera-the-explorer/SKILL.md; for p in 'The sweep (stage one), in this session, before any child runs' 'lab panel --pending' 'pre-registers' 'S00aa..S00bb' 'lab panel-map --kind signal' 'Synthesize once per run' 'Never launch a child for a stock-picking idea that has not cleared the panel' 'cleared signals from step 3, one child each' 'lab panel-replay --family-like' 'Price-and-volume stock picking is closed in this universe' 'do not apply to a' 'panel_exempt' '90% of its random twins'; do grep -qF -- "$p" $F && echo "ok   $p" || { echo "MISS $p"; false; }; done` → passes when all 13 lines print `ok` and the loop exits 0. The phrases cover the sweep writing and committing several signal files in one commit, `lab panel` run on them, one synthesis per run, a child launched only for a cleared signal or a non-signal idea, plus the replay, the whole-space verdict, the exemption, and the yardstick bar the wording test needs.
  - **J2** · traces R5.2 — `F=.claude/skills/explore-and-experiment-new-method/SKILL.md; for p in 'The first fork: is this a rule for choosing which stocks to hold?' 'goes through the panel before any method file exists' '3a. A signal' 'lab panel S00xx' 'Stop unless it cleared' 'Two rules do not apply to signal ideas' 'one-per-family slate rule' 'A queued stock-signal idea row becomes a signal like this' 'idea_id="M00yy"' 'Queue a next idea only when the result names one (optional)' 'standard_candidates' 'control-study:' '194 of the 197'; do grep -qF -- "$p" $F && echo "ok   $p" || { echo "MISS $p"; false; }; done; grep -c 'A run that queues nothing is the only real failure' $F` → passes when all 13 lines print `ok` and the final count prints `0`. The phrases cover the signal-before-method rule, the queue and slate rules stated as not applying to signals, and the queued-row-to-signal procedure; the old rule is gone.
  - **J3** · traces R5.1, R5.2 — write `$S/skill_cmds.py` from the block below, then run `$PY $S/skill_cmds.py .claude/skills/sera-the-explorer/SKILL.md .claude/skills/explore-and-experiment-new-method/SKILL.md .claude/skills/redo-sera-experiments/SKILL.md CLAUDE.md README.md docs/runbooks/signal-panel.md; echo "exit $?"` → passes when every line starts `ok`, the lines include `ok  lab panel`, `ok  lab panel-map`, `ok  lab panel-replay` and `ok  lab next-signal-id`, the last line reads `<n> commands, 0 bad`, and it prints `exit 0`. Before phases 3-4 land, the same run prints `BAD lab panel exit 2`; that is the expected failure.
    ```python
    """Every `lab <cmd> --flag` a document names, checked against that command's --help."""
    import os
    import re
    import subprocess
    import sys

    py = os.environ["PY"]
    span = re.compile(r"`([^`\n]+)`")
    cmd = re.compile(r"(?<![\w/.-])lab ([a-z][a-z-]*)((?:(?!(?<![\w/.-])lab ).)*)")
    found: dict[str, set[str]] = {}
    for path in sys.argv[1:]:
        text = open(path, encoding="utf-8").read()
        chunks = span.findall(text)
        fenced = False
        for line in text.splitlines():
            if line.strip().startswith(("```", "~~~")):
                fenced = not fenced
                continue
            if fenced:
                chunks.append(line)
        for chunk in chunks:
            for m in cmd.finditer(chunk):
                flags = set(re.findall(r"(?<![\w-])--[a-z][a-z-]*", m.group(2)))
                found.setdefault(m.group(1), set()).update(flags)
    bad = 0
    for name in sorted(found):
        r = subprocess.run([py, "-m", "seer_engine", "lab", name, "--help"], capture_output=True, text=True)
        missing = [f for f in sorted(found[name]) if f not in r.stdout]
        ok = r.returncode == 0 and not missing
        bad += not ok
        line = ("ok  " if ok else "BAD ") + f"lab {name}"
        if r.returncode:
            line += f" exit {r.returncode}"
        if missing:
            line += f" missing {missing}"
        print(line)
    print(f"{len(found)} commands, {bad} bad")
    sys.exit(1 if bad else 0)
    ```
  - **J4** · traces R5.1 — `F=.claude/skills/sera-the-explorer/SKILL.md; grep -c 'One per family per slate. Diversity beats depth inside a batch.' $F; grep -c 'At least one insight and one queued idea since the child started' $F; grep -c 'A \*\*sweep\*\* may hold twelve momentum variants' $F; git diff --stat origin/main -- $F .claude/skills/explore-and-experiment-new-method/SKILL.md` → passes when the three counts print `0`, `0`, `1`. The old unscoped slate rule and the mandatory queued-idea check are gone, and the Never row is scoped to child slates. The diff stat lists both skill files.
- Neighbor check: `test_lab_gate_wording.py` reads both skills and the newest synthesis, and is the existing check most likely to break. Run `cd engine && $PY -m pytest -q -n 2 tests/test_lab_gate_wording.py` → passes when it reports all passed and 0 failed. Also run `git status --porcelain -- engine web lab` → passes when it prints nothing, which proves no code, snapshot or lab database was touched.
- Cost: none. No LLM turn, no store load, no `lab run`.
**Exit criteria:** J1-J4 and the neighbor check pass on the worktree after phases 3, 4 and 5 have landed. Both skills describe the sweep, the stage-two launch for a cleared signal, the unchanged path for non-signal ideas, the routing of queued stock-signal rows, and the first replay. Every command and flag named in the six files exists.

## Handoffs

- **Phase 3 (resolved by the reconciler):** `lab next-signal-id` returns one past both `panel_signals` and every discovered signal file (`store.next_signal_id(conn, taken=discover())`), so the `ls $SIGNALS` numbering workaround is gone from both the skill and the runbook. `lab panel-map` prints `clears` / `no` with a `why not:` line, now quoted in Sera's step 3g. `lab panel --pending` accepts `--store`, `--sv-store` and `--jobs 2`.
- **Phase 4 (resolved by the reconciler):** `lab panel-replay` skips arms already recorded on the current dev store and prints `recorded K replay panel(s)`. Its `--limit` counts previously skipped arms, so Sera's step 2b and "The first replay" run it without `--limit` and stop when a run records 0. Phase 4's runbook headings ("A signal sweep (`lab panel`)", "The replay (`lab panel-replay`)", "Checking that nothing frozen moved", "Who runs the production replay") do not collide with this phase's two, and phase 4's last section now points to "The first replay" instead of describing its commit.
- **Phase 5 (gate, chassis, template):**
  - The skills name `Method.signal`, `Method.panel_exempt`, the prefixes `chassis:`, `market:`, `control-study:`, `seer_engine.lab.signal_book.standard_candidates(...)` and "`method_template.py`'s signal form".
  - The skills give **no** literal call of `standard_candidates` and defer to the template. If phase 5's template shows a different import (for example importing `SIGNAL` from the signal module rather than `discover()`), nothing here needs changing.
  - Reconciled: explore step 6 (Edit 4b) now quotes phase 5's refusal text: the "(lab/hardgate.py, D21)" tail and each cause's phrase as `hardgate.panel_refusal` prints it.
  - Phase 5's runner-test fixtures and any `lab-cli.md` refusal line are theirs.
- **Phase 1:** the skills name `signal_template.py` in the explore skill's folder, `engine/tests/test_lab_signals.py`, the signals package path, and the `Signal` field list from the shared contract (`idea_id` included).
- **Phase 6:** README now says `/sera/signals` "shows every stock-picking rule … ranked, each named by what it does, with its verdict in everyday words". If phase 6's page differs (for example it hides replays), the reconciler should adjust Edit 7e's one sentence.
- **Not done, deliberately (no phase owns it):**
  - The explore skill's "Testable?" bullet still says the store has "No fundamentals". The lab's own records say a fundamentals panel exists from 2009, and the new signal-limit sentence (Edit 3c) says so. Rewriting the older sentence is a drive-by correction outside R5. It is left for a follow-up card.
  - README's "Where the search stands" numbers are dated 2026-10-08 and stale. They are a dated record and outside R5.

## Rollback

Revert this phase's commit (six prose files). Nothing reads them at runtime, and no data changes. If the panel phases are reverted too, revert this one first, so no skill names a command that no longer exists. J3 is the check: run on a tree without phase 3, it prints `BAD lab panel exit 2`.
