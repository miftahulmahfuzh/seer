# Runbook — M0396: running the ten never-step-aside amendments

Pre-registered on 2026-10-27 by the `floor-reservation-yardstick` plan set, phase 3. **Nothing in
that phase ran.** This runbook is how the arms get run, later, deliberately, by one session.

## Before anything

1. **The amendments must be on `main`.** `lab run --amend` records a row against the file's
   current sha, and `lab stage` targets the MAIN checkout even from a worktree. Running these from
   a feature branch leaves the shared `lab/lab.sqlite` holding rows for shas that are not on
   `main` — the stale-lab.sqlite trap. Merge phase 3 to `main` first, and run from
   `/home/miftah/seer`.
2. **No other `lab run` may be in flight.** A concurrent `lab run` can silently lose trials with
   no error, and it also reddens three lab tests in a way that reads like a broken frozen record.
   Check first, and run these **one at a time, never concurrently**. A wave of concurrent lab
   phases has taken this laptop down twice.
3. **Environment.** The research store is not in worktrees; point `--store` at the main checkout.
   ```bash
   export SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite
   export SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research
   ```

## The ten commands, in this order

Run each on its own, check `$?`, and **never pipe a lab command through `grep`** — the pipe owns
the exit code, and a retry on `lab note` double-appends permanently. Redirect to a file instead.

```bash
cd /home/miftah/seer
for M in M0038 M0039 M0113 M0136 M0167 M0245 M0260 M0261 M0262 M0334; do
  echo "=== $M ==="   # run these ONE AT A TIME, by hand; the loop is the ORDER, not a script
done

engine/.venv/bin/python -m seer_engine lab run M0038 --amend --store engine/.research > /tmp/m0038.log 2>&1; echo $?
engine/.venv/bin/python -m seer_engine lab run M0039 --amend --store engine/.research > /tmp/m0039.log 2>&1; echo $?
engine/.venv/bin/python -m seer_engine lab run M0113 --amend --store engine/.research > /tmp/m0113.log 2>&1; echo $?
engine/.venv/bin/python -m seer_engine lab run M0136 --amend --store engine/.research > /tmp/m0136.log 2>&1; echo $?
engine/.venv/bin/python -m seer_engine lab run M0167 --amend --store engine/.research > /tmp/m0167.log 2>&1; echo $?
engine/.venv/bin/python -m seer_engine lab run M0245 --amend --store engine/.research > /tmp/m0245.log 2>&1; echo $?
engine/.venv/bin/python -m seer_engine lab run M0260 --amend --store engine/.research > /tmp/m0260.log 2>&1; echo $?
engine/.venv/bin/python -m seer_engine lab run M0261 --amend --store engine/.research > /tmp/m0261.log 2>&1; echo $?
engine/.venv/bin/python -m seer_engine lab run M0262 --amend --store engine/.research > /tmp/m0262.log 2>&1; echo $?
engine/.venv/bin/python -m seer_engine lab run M0334 --amend --store engine/.research > /tmp/m0334.log 2>&1; echo $?
```

The order is deliberate: the six single-instrument arms first (they are seconds each), then the
three book arms and M0334 (minutes each). M0113 and M0136 must be run back to back, and M0261 and
M0262 must be run back to back, because each pair's two arms are supposed to produce the same
number and a long gap between them weakens that check.

## Exit codes

- **0** — the amendment ran and one `method_amendments` row was appended. The method's status is
  explicitly unchanged, and the lab's N does not move: `store.DSR_POLICY` counts methods.
- **2** — the lab's rules refused the request. Read the message; it is one of:
  - the method file is uncommitted or dirty — the commit **is** the pre-registration;
  - the method has not run, or its status is `promoted`, `test-passed`, `test-failed` or `paper`
    (none of the ten is, as of 2026-10-27);
  - the method already has a `window='test'` trial (none of the ten does);
  - the amendment has already run, or a recorded amendment no longer matches the file;
  - a candidate repeats a configuration that already has a dev trial — **stop and re-measure**,
    because that means something changed since this was planned;
  - a variant is not priced at Gotrade's real fees.
- **1** — an error. Not a refusal. Read the traceback.

## After all ten

```bash
engine/.venv/bin/python -m seer_engine lab stage
```
`lab stage` writes `web/data/lab.json` and git-adds it with `lab.sqlite`. Commit **by index**, not
by pathspec: `git commit -- <paths>` re-reads the tree and defeats `lab stage`. Write the message
to a file and use `git commit -F`; backticks in a `-m` string are shell-substituted and silently
delete words, which has destroyed commits in this repo twice.

## Reading the result

- The bill of a step-aside habit is **ALWAYS's de-funded annual return minus that arm's**.
  `trials.curve_json` is the FUNDED curve and `trials.cagr` is deposit-contaminated; annualizing
  either directly reports deposits as return. De-fund with `regime.defunded(curve, deposits)`,
  deposits from `hardgate.trial_deposits`; `dressing.leg_of(conn, row)` hands you both.
- Check **M0113-ALWAYS against M0136-ALWAYS** and **M0261-ALWAYS against M0262-ALWAYS** first.
  Each pair is the same book on the same rules over the same sessions, so a disagreement larger
  than rounding means the retrofit is broken and no bill from this batch is readable.
- Check **M0334-ALWAYS against the recorded M0332-M12-1-NOSW**, which is the same book through a
  different allocator id.
- None of these arms may be promoted. Each is a buy-and-hold book, not a strategy, and
  `lab promote` has no role filter: it can select a declared diagnostic arm. Every one of the ten
  rationales opens with `Yardstick:`, which `control_shape.role_of` reads as `control`.

## The three methods that are NOT in this list, and why

`M0173`, `M0336` and `M0338` already carry a never-step-aside arm — `M0173-EXP100`
(*"Control: the dividend book never stepping aside for the curve watch"*), `M0336-NEVER` and
`M0338-NOSW` (*"no opinion: same book, switch off, always invested"*). The handover's census used
`max(trials.exposure) < 0.98`, and a stock book that never steps aside still reads about 0.97
because it always carries a little cash. `M0038`'s dividend half is covered the same way by
`M0038-DIV-OPEN`, which is also the yardstick for `M0039`'s and `M0167`'s dividend arms: all three
methods' DIV host is one configuration, and the lab refuses a second registration of a
configuration that already has a dev trial.

**Thirteen by the handover's read, ten in fact.** The superseded figure is recorded here rather
than deleted, because it is what the handover and every artifact built from it say. Re-measured
against `file:/home/miftah/seer/lab/lab.sqlite?mode=ro` on 2026-10-27: `M0038-DIV-OPEN`,
`M0173-EXP100` and `M0336-NEVER` are the identical book to every recorded digit — 576 trades,
turnover 4.296218435760635, exposure 0.9745847525069085, max_drawdown 0.5764932745904585 —
reached through three different allocator ids and run on two dates eight days apart.
`M0338-NOSW` is 1474 trades, turnover 7.348194427678176, exposure 0.971273318761785,
max_drawdown 0.6086749832160752.
