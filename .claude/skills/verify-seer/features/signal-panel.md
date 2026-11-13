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
