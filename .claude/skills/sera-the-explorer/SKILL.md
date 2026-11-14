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
     $PY -m seer_engine lab panel-replay --family-like 'stock-%' --store $REPO/engine/.research --sv-store $SV --jobs 1 > $LOGS/replay-<k>.txt 2>&1
     ```
     Keep `--jobs 1`: it is the only setting a full replay has been measured to the end on
     this machine (the runbook says why).
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
      - `lab panel` refuses a named signal file that is uncommitted or modified (exit 2,
        nothing recorded). `--pending` lists an uncommitted file and skips it.
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
      - **Exit codes.** Exit 2 means refused and nothing recorded: a named file that is
        uncommitted (`--pending` lists it as skipped instead: read the log for one), a store
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
