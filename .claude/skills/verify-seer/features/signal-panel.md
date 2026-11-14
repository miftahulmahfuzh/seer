# The signal panel (stage one of the lab)

## Sub-features

- `lab panel S0001 [S0002 ...] | --pending [--store DIR] [--sv-store DIR] [--jobs J]`: measures committed signal files (`engine/src/seer_engine/lab/signals/sNNNN_<slug>.py`) on a stock-by-month panel of the dev window, first on the dev store and then on the survivorship-check store, and records each signal's whole-window, pre-2009 and 2009-2015 readings on both stores in one transaction (`panel_signals`, `panel_results`). Per store and era it prints months, rank correlation (IC) and its t, the top bucket's annualised spread over the pool and its t, and the slope after momentum, beta, size and volatility and its t. A repeat prints "already panelled ... not measured again", loads no store and records nothing. `--pending` takes every committed signal with no panel on the dev store and lists an uncommitted file as `skipped`.
- `lab panel-map [--top K] [--kind signal|replay|all]`: every recorded panel ranked by the dev whole-window slope, with the published verdict (`clears` / `no` plus a `why not:` line), its q, the earlier panel it is a twin of, the three eras' spread and the survivorship-check slope. When nothing is recorded it prints "no panel recorded yet". It writes nothing.
- `lab next-signal-id`: the id alone on stdout, one past both the record and the committed signal files. The N line goes to stderr.
- Every one of the three ends with `Lab N (dev trials): X before, X after; luck gate N = G before, G after; test-window looks used: L before, L after`.
- Refused, exit 2, nothing loaded and nothing recorded: an unknown id; a named signal file that is untracked, modified or staged; a signal whose file changed after it was panelled; a dev store that declares the test window or carries a purpose marker; a missing, unmarked or other-purpose survivorship-check store; `--store` equal to `--sv-store`; neither ids nor `--pending`, or both. After the load: a dev store whose prices are not the benchmark's (D10).

## How to get to it (user POV)

The owner sees the panel on `/sera/signals` (phase 6) after a `lab stage`. The CLI is what an exploration session drives: write and commit a signal file, `lab panel` it, read `lab panel-map`.

## Driving it with verify.sh

```sh
$V up --no-web --empty
SV=/home/miftah/seer/engine/.research-sv          # verify.sh exports SEER_RESEARCH_STORE but not SEER_SV_STORE
$V labsql RUN "select count(*) from trials"       # T
$V lab RUN panel S0001 S0002 --sv-store $SV       # minutes: two store loads plus two frames; run in the background
                                                  # two blocks, each with dev and survivorship rows for all, pre2009, 2009-2015
                                                  # "2 signal(s) recorded"; "luck gate N = G before, G after"; exit 0
$V labsql RUN "select signal_id, store_role, era, months, ic_t, spread_t, fm_t from panel_results order by 1, 2, 3"   # 12 rows
$V lab RUN panel S0001 S0002 --sv-store $SV       # seconds: "already panelled", "nothing to measure"; exit 0
$V lab RUN panel-map                              # S0001 and S0002 ranked by slope, verdict and q on each row
$V lab RUN panel-map --kind replay                # "no replay panel recorded yet"
$V lab RUN next-signal-id                         # S0003
$V lab RUN panel S0001 --store /nonexistent --sv-store $SV    # exit 2: no manifest
$V lab RUN panel S0001 --sv-store /nonexistent                # exit 2: the survivorship-check store is required
$V labsql RUN "select count(*) from trials"       # T, unchanged
```

## Gotchas

- `$V lab` starts from `env -i` and does not export `SEER_SV_STORE`. Pass `--sv-store /home/miftah/seer/engine/.research-sv` every time, or the default resolves inside the worktree, where no store exists, and the run is refused.
- Never point `--store` at `engine/.research-test` to "check" the refusal. Use a scratch directory whose `manifest.json` declares `{"window_name": "test", "window_start": "2015-10-19", "window_end": "2026-11-13"}`. The command refuses it from the manifest, and nothing reads the real test store.
- The uncommitted-file refusal is driven by adding an untracked `sNNNN_*.py` (a copy of a seed signal with its id changed) to the checkout under test, running `lab panel` on it, then deleting it. Remove the file before anything else runs: `lab next-signal-id` counts it while it exists.
- A panel is keyed on the dev store's fingerprint. After a dev store change every signal is pending again, which is intended.
- Counts in this file are examples. Read them back with `labsql` (CLAUDE.md, Claim verification).

## Replay: `lab panel-replay`

- `lab panel-replay [M0614 ...] [--family-like PATTERN] [--limit N] [--store DIR] [--sv-store DIR] [--jobs 1|2]`: every recorded dev arm of every method whose family is like PATTERN (default `stock-%`) becomes a pick-set panel. The arm's own allocator is called at each month end with nothing held, its fixed instruments and names outside the pool are dropped, and the rest are measured on the dev store and then the survivorship-check store. Each arm is recorded in one transaction: a `panel_signals` row of kind `replay` under the candidate id with `method_id` set, plus its `panel_results` rows.
- The report prints how many arms were selected, already recorded and attempted; per store, the arms measured, the wall time and the time per arm; `recorded K replay panel(s), one transaction each`; the held-aware count; and a skipped table, counted by reason with one line per arm. The reasons are: method file does not import, arm no longer in its file, configuration drifted, bracket strategy, picks no index members, a store lacks its data, allocator raised, or never picked 5 pool names in a month. It ends with the same N / luck gate N / looks footer as `lab panel`.
- A re-run measures only arms with no panel on the current dev store, plus the ones it skipped before. With nothing left it prints "nothing to replay: no store was loaded".
- Refused, exit 2, nothing loaded: a named method with no dev trial in the family, a malformed id, and every store refusal `lab panel` makes. `--jobs` above 2 is refused by argparse (exit 2). Exit 1 only when the run attempted arms and the selection holds no replay panel at all.

### Driving it with verify.sh

```sh
$V up --no-web --empty
SV=/home/miftah/seer/engine/.research-sv
DB=$HOME/.local/state/seer-verify/RUN/lab.sqlite
sqlite3 "file:$DB?mode=ro" "select * from trials order by n" | sha256sum                 # keep
sqlite3 "file:$DB?mode=ro" "select id, source_sha from methods order by id" | sha256sum   # keep
$V lab RUN panel-replay --sv-store $SV --limit 20      # minutes: "20 attempted this run", "recorded K replay panel(s)", a skipped table; exit 0
$V labsql RUN "select count(*) from panel_signals where kind = 'replay'"                                   # K
$V labsql RUN "select count(*) from (select distinct signal_id, store_role from panel_results where signal_id in (select id from panel_signals where kind = 'replay'))"   # 2K
$V lab RUN panel-replay --sv-store $SV --jobs 1        # the rest of the sweep: run it in the background (see docs/runbooks/signal-panel.md for its measured time)
$V lab RUN panel-replay --sv-store $SV                 # "recorded 0"; every finished arm counted as already recorded; exit 0
$V lab RUN panel-replay M0205 --sv-store $SV           # exit 2: M0205 is not a stock-* method
$V lab RUN panel-replay --jobs 3                       # exit 2 (argparse)
$V lab RUN panel-map --kind replay --top 15            # the replays ranked by controlled slope, twins marked
sqlite3 "file:$DB?mode=ro" "select * from trials order by n" | sha256sum                 # same as kept
sqlite3 "file:$DB?mode=ro" "select id, source_sha from methods order by id" | sha256sum   # same as kept
git status --short engine/src/seer_engine/lab/methods                                    # nothing
```

### Gotchas (replay)

- Pass `--sv-store` every time: `$V lab` starts from `env -i` and does not export `SEER_SV_STORE`.
- The full sweep loads both stores and runs every recorded stock arm's allocator on each. Run it with Bash `run_in_background`, never under a foreground timeout, and never beside another store-loading command (invariant 6: at most two such sessions on this machine).
- An arm that was skipped is attempted again on every run, so a re-run after a complete sweep still loads both stores whenever any arm was skipped. That is by design: a fixed file or store may now feed it.
- Never run it against `/home/miftah/seer/lab/lab.sqlite` from a phase session. The production replay is run once from the main checkout by Sera (phase 7).
- `held-aware` arms (keep bands, rules that read what is held) are measured from an empty book every month. Their panel is an approximation, and the report says how many there are.
- Counts here are examples. Read them back with `labsql` (CLAUDE.md, Claim verification).
