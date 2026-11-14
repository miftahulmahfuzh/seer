# The signal panel: running a replay and a signal sweep

Stage one of the lab measures a stock-picking idea on a stock-by-month panel of the dev window
before it can become a book. This runbook is the operator's half: how to run `lab panel` on new
signal files and `lab panel-replay` over the recorded stock-signal methods, what they cost on this
machine, and how to check that nothing frozen moved. The Sera-facing procedure (sweeps, syntheses,
when to launch a child session) is the last section.

Every figure below was measured on 2026-11-14 in the phase-4 proof run (verify-seer run
1114-061317-129963), with `/usr/bin/time -v`, against a copy of the lab database and the main checkout's
stores. Re-measure after a store or panel-rule change; do not scale these by hand.

## Before you start

- Stores: `SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research` and
  `SEER_SV_STORE=/home/miftah/seer/engine/.research-sv` (or `--store` / `--sv-store`). A worktree
  has neither and never rebuilds one. Both commands refuse a test-window store from its manifest
  and never read `engine/.research-test`.
- Database: a session that is not the production replay points `SEER_LAB_DB` at a scratch copy
  (`cp /home/miftah/seer/lab/lab.sqlite "$SCRATCH/lab.sqlite"`). Lab commands migrate the file on
  connect, so even a read dirties the shared one.
- Machine: one store-loading command at a time beside at most one other session. Five
  concurrent sessions took WSL down twice.

## A signal sweep (`lab panel`)

```sh
python -m seer_engine lab next-signal-id                      # the id for the next signal file
# write engine/src/seer_engine/lab/signals/sNNNN_<slug>.py, commit it (the commit is the pre-registration)
python -m seer_engine lab panel SNNNN [SNNNN ...]             # or --pending for every committed, unpanelled signal
python -m seer_engine lab panel-map --kind signal             # ranked, with the published verdict
```

Measured: `lab panel S0001 S0002` took 0:41.23 wall at 1,096,924 kB maximum resident
memory. That covers both store loads and both frames, so most of the time is fixed per run, not
per signal: panel several signals in one command rather than one command each.

## The replay (`lab panel-replay`)

The first job of the panel: every recorded dev arm of every `stock-*` method as a pick-set panel,
so the explored space reads as one ranked map. The arm's own allocator is called at each month end
with nothing held, and its picks are measured on both stores. Nothing in `trials`, no config
digest and no method file changes.

```sh
python -m seer_engine lab panel-replay --limit 20 --jobs 1    # a first batch, to time this machine
python -m seer_engine lab panel-replay --jobs 1               # the rest; run in the background
python -m seer_engine lab panel-replay                        # resume or confirm: finished arms are not re-measured
python -m seer_engine lab panel-map --kind replay --top 40    # the explored space, ranked, twins marked
```

Measured:

| Run | Arms | Wall | Per arm (dev / survivorship) | Max RSS |
|---|---|---|---|---|
| `--limit 20 --jobs 1` (J2) | 20 attempted | 2:34.51 | 2.11 s / 2.75 s | 1,187,228 kB |
| full sweep `--jobs 1` (J3) | 1700 attempted of 1720 selected | 1:17:51 | 1.03 s / 1.52 s | 3,588,884 kB |
| re-run after the sweep `--jobs 1` (J4) | 41 attempted | 1:01.69 | n/a | 1,228,744 kB |

The full sweep recorded 1659 replay panels and skipped 41 arms. Of the
recorded arms, 289 change their picks when handed a holding (keep bands, rules that read
what is held). Their panels are read from an empty book every month, an approximation.

`--jobs 2` forks two workers after each store loads; each prepares its own allocators. It was not
timed: the proof's first full sweep ran at `--jobs 2` beside one other session and was cut off
when WSL restarted, so the sweep above was re-run at `--jobs 1`, which is the setting to use on
this machine until a `--jobs 2` sweep has been measured to the end. Never go above two.

`--limit N` takes the first N **unfinished** arms in trial order, and an arm skipped on an earlier
run is still unfinished. Once N or more skipped arms sit at the front of the queue, a `--limit N`
batch attempts only them and records nothing while work remains. Use `--limit` for the first
timing batch only; run the rest without it. A full run is done when a re-run prints
`recorded 0 replay panel(s)`.

### Reading the skipped table

| Reason | What it means | What to do |
|---|---|---|
| method file does not import | the committed file raises on import today | nothing; a frozen file is not edited to make it replayable |
| arm is no longer in its method file | the recorded candidate id is not declared any more | nothing |
| arm's configuration differs from the recorded one | `config_digest` moved, usually through an imported params class | report it: this is the frozen-record drift `test_every_recorded_configuration_still_digests_to_its_recorded_digest` guards |
| bracket strategy, not an allocator | a `DESIGN_V0` bracket arm | nothing; the panel reads book allocators |
| does not pick index members | the allocator trades fixed instruments only | nothing; there is no pick set |
| a store lacks data the allocator reads | the named store has no dividends, series, shares or fundamentals | repair the store (`docs/runbooks/survivorship-store.md`) and re-run |
| allocator raised | the allocator failed on this store; the detail names the exception | read the detail; the arm is attempted again next run |
| never picked 5 pool names in a month | the switch was never on, or the picks were never in the pool | nothing; it has no pick set to measure |

A skipped arm is attempted again on every run, so a re-run after a complete sweep still loads both
stores whenever anything was skipped (J4 above).

## Checking that nothing frozen moved

Run before and after any replay on a copy, and compare:

```sh
sqlite3 "file:$SEER_LAB_DB?mode=ro" "select * from trials order by n" | sha256sum
sqlite3 "file:$SEER_LAB_DB?mode=ro" "select id, source_sha from methods order by id" | sha256sum
git status --short engine/src/seer_engine/lab/methods        # must print nothing
```

Both hashes must match, and the git status must be empty. In the phase-4 proof both hashes were
unchanged across J2, J3 and J4.

## Who runs the production replay

Sera's preflight, once, from the main checkout, against the shared `lab/lab.sqlite`, when the
panel holds no replay rows. The procedure, including how its `lab stage` commit is made, is in
"The first replay" below. A phase session never runs it.

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
| 0 | every pending signal was recorded, or nothing was pending; `--pending` lists an uncommitted signal file as skipped | commit any skipped file and run again, then read the map (step 7 above) |
| 2 | refused; nothing recorded: a named signal file uncommitted or modified, a store that is not the dev store, or no survivorship store | commit the file, point `--store` at `engine/.research`, or rebuild the survivorship store (`docs/runbooks/survivorship-store.md`), then run again |
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
# --jobs 1: the only setting a full replay has been measured to the end on this machine.
$PY -m seer_engine lab panel-replay --family-like 'stock-%' --store $REPO/engine/.research --sv-store $SV --jobs 1 > $LOGS/replay-<k>.txt 2>&1; echo "exit $?"
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
