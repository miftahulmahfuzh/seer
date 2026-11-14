# The lab CLI

## Sub-features

- Read: `lab status` (near-miss and closest-to-eligible rows end in `[role; = first-recorded twin]` tags), `lab show MNNNN`, `lab next-id`, `lab luck`, `lab twins MNNNN|CANDIDATE ...` (which arms are a book the lab already recorded under another id), `lab roles [MNNNN ...]` (each dev arm's recorded role -- control, dose, idea, treatment -- and its source, or what its method file reads now; no ids: counts by role and source) and the report-only commands (`costs`, `timing`, `kin`, ...).
- Write (to the run's private copy only): `lab idea` (prints the id on stdout and the five closest methods by shared words on stderr, then the control arms those methods already hold, by first recording ("Controls those methods already hold ...")), `note`, `insight`, `block`/`unblock`, `drop`, `run` (a committed method on the dev window; prints a `Book twins:` block after the mirror pairs; records each arm's role, and a control arm is recorded `not a control arm` and never makes the method dev-eligible), `roles --backfill` (one role row per dev arm that has none and whose method file can be read; a second run records 0), `reevaluate --demote` (moves a dev-eligible method with no eligible non-control arm today to rejected, with a dated note in its analysis; no trial row changes). `yardstick` (`lab yardstick MNNNN | --arm CANDIDATE | --pending [--limit N] [--jobs J] [--dry-run]`: random twins of a recorded dev arm, one `trial_yardstick` row per arm and store, never a trial; a repeat prints "already measured" and writes nothing). `run` also measures every arm that clears the other six conditions against its random twins before recording it (`--jobs J`, default 2), logs one line per measured arm, and records an arm that lost to them with the label `beats 90% of random twins`.
- Refused: `lab run` when an arm repeats a book another method recorded first and does not declare it (a control, or a rationale naming that method), or when every arm repeats a recorded book (exit 2, nothing written, no arm metric printed); `lab run` (and `--amend`) on a method with an arm that chooses among index members unless it names a signal whose published panel verdict clears on the dev store being loaded and its non-control arms are exactly that signal's standard book (`signal_book.standard_candidates`), or it declares `panel_exempt` (`chassis:`, `control-study:` or `market:` and a reason): exit 2 before the store loads, nothing written, the dev trial and method counts unchanged (hardgate D21); `lab yardstick --arm` on a control arm, an unknown arm or method, or an arm recorded on the loaded store that no longer reproduces its trade count and return (exit 2, nothing written); `lab test`, `promote`, `stage`, `export`, `export-json`, `seed`, and any `--db`. `lab promote` on a method whose chosen arm has no random-twin reading that clears (hardgate D20; proven through `lab status`, see Gotchas).

## How to get to it (user POV)

The owner reads the lab through `/sera`. The CLI is what the exploration sessions (`sera-the-explorer`) drive, and its writes reach Sera only through `lab stage` + a commit, which a verify run never does.

## Driving it with verify.sh

```sh
$V up --no-web --empty
$V lab RUN status          # "dev trials (one row per recorded backtest): 1690", "test-window looks used: 5", "methods: 503"
$V lab RUN show M0007      # "M0007 Residual momentum: ... [dev-eligible]", then "Hypothesis:"
$V lab RUN next-id         # M0490
$V lab RUN twins M0488     # "M0488-DVC10-NEVER (control) = M0125-DV-C10, first recorded (trial 519, M0125, ..."; exit 0
$V lab RUN twins M0447     # "*** the same book as this method's own control M0447-DVC10-NEVER: the treatment never acted"
$V lab RUN twins M0001-TYPO   # exit 2: an unknown id is refused, never read as "no twins"
$V lab RUN status          # with no reading in the copy: "Promotable now" reads "(none)"; every method that was promotable sits under "Refused by the hard gate" with "has never been measured against its random twins"
$V lab RUN yardstick --arm M0562-W60-B100 --jobs 2 --dry-run   # one table row: twins = yardstick.DRAWS, "beaten" b/DRAWS, a 12-hex "draw set", "(dry run: not recorded)"; exit 0; minutes
$V lab RUN yardstick --arm M0562-W60-B100 --jobs 2   # the same row without the note; "1 arm(s) recorded"; "Lab N (dev trials): X before, X after"; exit 0
$V lab RUN yardstick --arm M0562-W60-B100            # "already measured on store ...; not measured again", "0 arm(s) recorded"; exit 0; no twins simulated
$V labsql RUN "select trial_n, rule_id, status, draws, beaten, reproduced from trial_yardstick"   # one row, reproduced 1 when the trial was recorded on this store
$V lab RUN status          # M0562 is back under "Promotable now" only if M0562-W60-B100 out-earned at least 90% of its twins (or reads not-applicable); otherwise it stays refused with "(D20)"
$V lab RUN idea --name "verify-seer smoke idea" --family verify-smoke --hypothesis "harness check, never run" --source-kind knowledge
                           # stdout: the new id; stderr: "Closest methods already in the lab ..." and up to 5 ids; plus a "Controls those methods already hold" block when a neighbour holds a control; exit 0
$V labsql RUN "select id, name, status from methods where family = 'verify-smoke'"   # M0490 | verify-seer smoke idea | idea
sha1sum lab/lab.sqlite; git status --porcelain lab web/data                       # hash unchanged, nothing listed
$V lab RUN roles --backfill   # "recorded R role(s) (source backfill); skipped K dev arm(s) whose method file or arm cannot be read (in H-..., ...)"; exit 0
$V labsql RUN "select role, source, count(*) from trial_roles group by 1, 2"   # the R rows, source backfill
$V lab RUN roles --backfill   # "recorded 0 role(s)": idempotent
$V lab RUN roles M0202        # one line per dev arm: candidate, role, source (its placebo arms read control)
$V lab RUN reevaluate --demote   # "M method(s) moved dev-eligible -> rejected"; trials unchanged (labsql count before = after)
$V lab RUN test M0007      # verify: engine: 'lab test' is never driven (...)
$V lab RUN stage           # verify: engine: 'lab stage' is never driven (...)
```

## Gotchas

- The counts above are the committed lab's at the commit under test. Read them back with `labsql` instead of quoting these (CLAUDE.md, Claim verification).
- The copy is taken read-only at `up`, so a peer's later `lab run` against the shared DB is invisible to the run, and the run's writes are invisible to everyone.
- `lab run` reads the dev research store from the main checkout (`SEER_RESEARCH_STORE`) and refuses an uncommitted method file, exactly as in real use. It takes minutes.
- Never prove anything with the test window. `lab test` is refused because a look spends the budget and contaminates every later method.
- `lab promote` is refused here, so a hard-gate clause (D19 included) is proven through `lab status`'s "Refused by the hard gate" block, which runs the same `hardgate.check`, plus read-only Python against the run's copy (`~/.local/state/seer-verify/RUN/lab.sqlite`, `mode=ro`).
- The repeat refusal cannot be driven through `$V lab RUN run`: that needs a committed method file, and a verify run never commits. Drive `runner.run_method` with a throwaway method built from a recorded method's arms instead, against the run's lab copy (`~/.local/state/seer-verify/RUN/lab.sqlite`) and the main checkout's dev store, with `SEER_ENV_FILE=~/.local/state/seer-verify/RUN/engine.env` and `PYTHONPATH=<checkout>/engine/src`. The phase-1 plan of `lab-run-refuses-repeat-books` carries such a script (`repeat_drive.py`). An SPY-only arm loads the whole dev store and takes minutes. A recorded arm copied unchanged is refused earlier, by the digest guard (`... which already ran on the dev window`), so the copy needs a new digest from a field its rule ignores: M0205's `spy` rule reads neither `sma` nor `exit_below`, so `exit_below=0.99` is the same book under a new digest. For the same reason a fresh arm must change a field the rule reads (`rule="breadth", sma=187`), not the SPY arm's `sma`.
- Run `lab roles --backfill` before `lab reevaluate --demote`. A control arm counts as a control only once its role is recorded, so a demotion before the backfill under-reaches (it never over-reaches); the command prints how many arms of the swept methods still have no role.
- `lab yardstick` loads the dev store from the main checkout and simulates `yardstick.DRAWS` twins per arm: a few minutes per arm at `--jobs 1`. Run it in the background (Bash `run_in_background`), not under a 10-minute foreground timeout. An arm recorded on another store than the one loaded is measured without the reproduction check and records `reproduced` NULL. `--arm` refuses a control by its recorded role or, before `lab roles --backfill`, by its rationale.
- The yardstick (D20) is proven like D19: through `lab status`'s refused block and read-only Python against the run's copy. `lab run`'s own measurement needs a committed method file, so it is proven by `engine/tests/test_lab_yardstick_gate.py` (an injected `measure`, plus one real-engine run at five draws).
- The panel gate (D21) cannot be driven through `$V lab RUN run`: that needs a committed method file. Drive `commands.lab.run` with `method.discover` replaced by a throwaway method whose path is a tracked, clean file (any engine module), against the run's lab copy (`SEER_LAB_DB=~/.local/state/seer-verify/RUN/lab.sqlite`) with `SEER_RESEARCH_STORE` at the main checkout's dev store and `research.load_store` replaced by a tripwire, so a method the gate lets through stops at the load instead of spending minutes. Give the throwaway method an arm no recorded method holds (an unrecorded width, say): the repeat check runs before the gate and exits 2 with its own message, which reads like a pass. The phase-5 plan of `sera-signal-panel` carries such a script (`panel_gate_drive.py`). A cleared signal needs panel rows on the store's manifest fingerprint: on a copy, `lab panel SNNNN` writes them, or the script seeds a plainly clearing reading.
