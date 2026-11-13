# Runbook — the random-twin yardstick backfill

From 2026-11-14 the lab's dev screen has a seventh condition: an arm passes only if it out-earned
at least 90% of its random twins, books that repeat its every decision with each picked stock
swapped for a randomly drawn index member of similar trading size (design §10). `lab run` measures
every new arm itself. The arms recorded before that date were never measured. They read as they
did until they are, and `lab promote` refuses every one of them until then.

This runbook measures them, once, on `main`. It writes the shared `lab/lab.sqlite`, so it runs in
the **main checkout**, never in a worktree or a verify run.

## Before you start

- `git pull` on `main`. The random-twin yardstick code must be on it.
- The dev research store is present and current: `/home/miftah/seer/engine/.research` (use the
  `sync-research-store` skill on a second machine). `lab yardstick` reads it. On the store an arm
  was recorded on, it first re-runs the arm and refuses one that no longer reproduces its recorded
  trades and return; on any other store it measures without that check and the reading says so.
- No Sera batch is running. Each measurement holds two worker processes, a child's `lab run` now
  holds two more, and the machine has 11 GiB of RAM.

## The three commands, in order

```bash
engine/.venv/bin/python -m seer_engine lab roles --backfill
```

Records the role (control, dose, idea or treatment) of every recorded dev arm whose method file can
be read, from its own rationale. It is safe to run twice: an arm already recorded is skipped. The
54 P7a seed rows have no method file and are skipped without failing. It prints how many arms it
recorded and how many it skipped. From here on a control arm reads not eligible.

```bash
engine/.venv/bin/python -m seer_engine lab yardstick --pending --jobs 2 > /tmp/yardstick.txt 2>&1; echo "exit $?"
```

Measures every arm that is due: a dev arm that is not a control and whose only failure today, if
any, is the yardstick itself. It prints one line per arm: how many of its twins it out-earned and
whether that clears 90% of its random twins, or `not-applicable` (no picked stock), or `unmatched`.
It writes one `trial_yardstick` row per arm and nothing else: no trial, no N, no test-window look.
Run it as a background job and wait for it to exit; never add `&` or `nohup`.

**What it costs.** On 2026-11-13 the lab held 192 non-control arms that read eligible, which is the
queue. Each arm is 200 twin simulations at about 2 seconds each (the analysis measured 2.6 s for a
first run and 1.5 s for a replay of `M0562-W60-B100`), so about 400 simulation-seconds per arm, and
about 200 seconds at `--jobs 2`. The whole queue is about 192 × 200 s ≈ 10.7 hours, plus 12 seconds
to load the store per command. Run it in batches with `--limit`:

```bash
engine/.venv/bin/python -m seer_engine lab yardstick --pending --limit 24 --jobs 2 > /tmp/yardstick.txt 2>&1; echo "exit $?"
```

24 arms is about 80 minutes. Stage and commit after each batch (below).

**`--jobs 2`, not more.** Every worker holds a full simulation of the market in memory. The result
is the same at any `--jobs` value, so a smaller number only costs time.

**Resuming.** Run the same command again. An arm that already has a reading on this store is not
measured twice (the row is keyed by trial, rule and store, and a second insert writes nothing), so
an interrupted batch picks up where it stopped. An arm that exits 2 because its re-run does not
reproduce its recorded trades and return writes nothing; note its id and leave it. It stays unmeasured,
and `lab promote` keeps refusing it.

```bash
engine/.venv/bin/python -m seer_engine lab reevaluate --demote
```

Moves every `dev-eligible` method that no longer has an eligible non-control arm at today's bars to
`rejected`, and appends a dated note to its analysis saying why. No trial row changes. Run it after
the last batch, and only then: a method whose arms are not all measured yet still reads as it did.
Afterwards, plain `engine/.venv/bin/python -m seer_engine lab reevaluate` moves back any `rejected`
method whose arm now clears every condition, the yardstick included.

## Stage and commit

After each batch and after `--demote`:

```bash
engine/.venv/bin/python -m seer_engine lab stage
git commit -m "lab: yardstick backfill, batch 3 (24 arms measured, 19 cleared)"   # numbers from the batch's own output
git push
```

and after `--demote`:

```bash
git commit -m "lab: yardstick backfill done (192 arms measured; 31 methods demoted to rejected)"   # numbers from the output
```

`lab stage` writes `web/data/lab.json` and git-adds it with `lab/lab.sqlite`; commit only those two
files. Quote counts read back from the command's output or the database, never from this page (CLAUDE.md,
Claim verification).

## Checking the result

```bash
engine/.venv/bin/python -m seer_engine lab status
```

"Promotable now" lists only methods whose chosen arm out-earned at least 90% of its random twins
(or holds no picked stock). Every other dev-eligible method sits under "Refused by the hard gate"
with the reason. An arm that lost to its twins carries the label `beats 90% of random twins` among
its failures.
