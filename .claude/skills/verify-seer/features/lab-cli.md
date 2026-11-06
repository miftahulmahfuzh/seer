# The lab CLI

## Sub-features

- Read: `lab status` (near-miss and closest-to-eligible rows end in `[role; = first-recorded twin]` tags), `lab show MNNNN`, `lab next-id`, `lab luck`, `lab twins MNNNN|CANDIDATE ...` (which arms are a book the lab already recorded under another id) and the report-only commands (`costs`, `timing`, `kin`, ...).
- Write (to the run's private copy only): `lab idea`, `note`, `insight`, `block`/`unblock`, `drop`, `run` (a committed method on the dev window; prints a `Book twins:` block after the mirror pairs).
- Refused: `lab test`, `promote`, `stage`, `export`, `export-json`, `seed`, and any `--db`.

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
$V lab RUN idea --name "verify-seer smoke idea" --family verify-smoke --hypothesis "harness check, never run" --source-kind knowledge
                           # prints M0490; exit 0
$V labsql RUN "select id, name, status from methods where family = 'verify-smoke'"   # M0490 | verify-seer smoke idea | idea
sha1sum lab/lab.sqlite; git status --porcelain lab web/data                       # hash unchanged, nothing listed
$V lab RUN test M0007      # verify: engine: 'lab test' is never driven (...)
$V lab RUN stage           # verify: engine: 'lab stage' is never driven (...)
```

## Gotchas

- The counts above are the committed lab's at the commit under test. Read them back with `labsql` instead of quoting these (CLAUDE.md, Claim verification).
- The copy is taken read-only at `up`, so a peer's later `lab run` against the shared DB is invisible to the run, and the run's writes are invisible to everyone.
- `lab run` reads the dev research store from the main checkout (`SEER_RESEARCH_STORE`) and refuses an uncommitted method file, exactly as in real use. It takes minutes.
- Never prove anything with the test window. `lab test` is refused because a look spends the budget and contaminates every later method.
- `lab promote` is refused here, so a hard-gate clause (D19 included) is proven through `lab status`'s "Refused by the hard gate" block, which runs the same `hardgate.check`, plus read-only Python against the run's copy (`~/.local/state/seer-verify/RUN/lab.sqlite`, `mode=ro`).
````
