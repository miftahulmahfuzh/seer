# Handover: the lab re-runs identical control books under new digests

Written 2026-11-06 by Sera 20261106-1411 (session 2O-3B) for an `/analyze` session. Every
figure below was read back from `lab/lab.sqlite` or re-run in that session unless marked
**unverified**.

## The bug the owner saw

The batch's calculate-assets run on M0488 reported its never-aside control at Rp 2,146.7M
(2018-04-01 to 2026-10-08). The owner's top-4 note already holds that exact book as DEEPTAPE
(M0447-DVC10-NEVER). The owner read it as "Sera redid DEEPTAPE on the Lenovo after the GPD ran
it". The cause is not a skipped research-store sync: the store fingerprint was the same on every
run, and `lab.sqlite` travels through git and had been pulled.

## Measured facts

The same book was recorded three times, once per method, each as that method's no-opinion
control:

| trial | candidate | config_digest | store_fingerprint | total_return | trades |
|---|---|---|---|---|---|
| 1536 | M0442-DVC10-NEVER | 74800775… | 640fc25e… | 249.05533983053 | 1210 |
| 1674 | M0447-DVC10-NEVER | 1b048f46… | 640fc25e… | 249.05533983053 | 1210 |
| 1734 | M0488-DVC10-NEVER | ead6da40… | 640fc25e… | 249.05533983053 | 1210 |

`calculate_assets.py` on M0447-DVC10-NEVER and M0488-DVC10-NEVER gives identical output to the
rupiah (Rp 2,146,659,096, 764 trades, 40.1% deepest fall).

Why the digests differ: each method file (`m0442_*`, `m0447_*`, `m0488_*`) wraps M0125's host
`WeightParams` in its own params dataclass (for example `WatchHostParams` with `mode`,
`watch_days`, a deep-fall threshold...). The digest covers the wrapper, so the same book gets a
new identity in every follow-up method. The runner's "already-run digest" refusal never fires.
See memory `seer-shared-params-cannot-gain-a-field`: this is the same mechanism.

## What to analyze and fix, robustly

1. **Identity of a book, apart from the method that wraps it.** The goal is to detect that a
   candidate is behaviourally the same book as a recorded trial (same targets on every decision
   date on the same store), not just the same params text. Options to weigh:
   - a canonical "effective config" digest (strip inert wrapper fields, for example `mode=never`
     makes the watch fields dead),
   - a result fingerprint (curve hash and trade count) checked after the run,
   - or a cheap pre-run probe of targets on a sample of dates.
   Decide what happens on a match: reuse the recorded trial as the control (with provenance), or
   run it anyway and mark it a duplicate. **Constraints:** the protocol requires controls to run
   beside the treatment, so a reused control must stay attached to the new method. N policy
   counts methods, not arms (memory `seer-lab-n-policy-overcounts-looks`). Closed records and
   existing digests are frozen: never rewrite trials 1536/1674/1734.
2. **Reporting surfaces that present a control as a new candidate.** The calculate-assets skill
   ran the "main + control" arms and Sera relayed the control's money as if it were a new book.
   Related known gaps: `lab promote` and `best_dev_eligible` have no role filter (memories
   `seer-promoted-variant-can-be-a-control-arm`,
   `seer-promote-has-no-role-filter-for-diagnostic-arms`). Check whether one role-aware
   "is this a control, and is it a book already recorded?" helper should feed promote,
   calculate-assets, `lab status` near-miss lists and the Sera skill.
3. **Sera's slate selection.** The sera-the-explorer skill picks follow-ups from the backlog
   without asking whether a new method's arms re-measure a recorded book. Decide whether the
   skill or `lab idea` should warn.
4. **A related reproducibility question (cause unverified).** COSK (M0179-N20) read
   Rp 1,783.1M to 2026-10-06 in an earlier session's run and Rp 1,819.7M to 2026-10-08 today,
   while LONGHAUL, STAYPUT and DEEPTAPE all ended lower than before. Two sessions of market move
   may or may not explain it. The earlier figure came from note J-60F, so it was not re-measured
   here. Re-run COSK to 2026-10-06 and say whether calculate-assets output changed for a fixed
   end date (store change, code change, or nondeterminism). Memory
   `seer-old-trial-returns-are-not-reproducible` is relevant.

## Pointers

- Runner digest checks: `engine/src/seer_engine/lab/runner.py` (search `check_digest`).
- Method files: `engine/src/seer_engine/lab/methods/m0442_*.py`, `m0447_*.py`, `m0488_*.py`,
  host in `m0125_index_book_volume_weight.py`.
- Calculate-assets: `.claude/skills/calculate-assets/` (`calculate_assets.py`, `SKILL.md`).
- Sera skill: `.claude/skills/sera-the-explorer/SKILL.md`.
- Owner's top-4 note: mcp-notes J-60F.

Follow CLAUDE.md: smallest change that fixes it, prove it with the `verify-seer` skill, keep
`lab.sqlite` append-only, and use explicit pathspecs when committing.
