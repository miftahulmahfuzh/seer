# Pre-registrations

One file per promoted method: `MNNNN.md`, written by

    python -m seer_engine lab promote MNNNN

and committed and pushed **before** `python -m seer_engine lab test MNNNN-VARIANT` is run
(method lab design §3).

## Why the file exists

The lab gets one look at the test window per configuration. The database enforces the *count*
(`UNIQUE(config_digest, window)` on `trials`, plus triggers that refuse every UPDATE and DELETE).
It cannot enforce *which* configuration the look is spent on, and it cannot stop a disappointing
answer from retroactively becoming a different question.

This file is that half. It names one variant and its `config_digest` before any test number
exists. `lab test` refuses to run while the file is missing, uncommitted, modified, or naming a
different candidate, and `lab promote` never rewrites a file that is already here — a better
variant found later is a new method with its own dev trials, not an edit.

## Format

A strict `key: value` block between two `---` lines at the top of the file, then prose. The
block is machine-read (`seer_engine.lab.prereg.parse`); the prose is not.

| Key | What it is |
|---|---|
| `method` | the method id, `MNNNN` — matches the file name |
| `candidate` | the one pre-registered variant, `MNNNN-SUFFIX` |
| `config_digest` | sha256 of the variant's canonical configuration, **copied from the recorded dev trial** |
| `rules_id`, `allocator_id` | what the variant trades with, for a reader |
| `dev_trial` | the `trials.n` the digest was copied from |
| `dev_window` | that trial's `start..end` |
| `test_window` | `2015-10-19..data end` — the start is the first session after `DEV_END`; the end is pinned by the test trial, because the test store reaches the latest session available when it is built |
| `gate` | the conditions the variant passed on the dev window, **including the DSR threshold in force and the multiple-testing policy with the N it resolved to** on the day the file was written (design §7). Both are settings the owner can move, so both are pinned here |
| `mar`, `dsr`, `n_trials_at_run` | the dev numbers it passed with. `n_trials_at_run` is **the N that trial's DSR was deflated by**, whatever the policy in force on its run date resolved to — the trial-row count for every row recorded before 2026-10-08 (`all-trials`), the distinct-method count after it (`methods`). It is not the row count and must not be read as one; the N the gate used is the one stated in `gate` |
| `store_fingerprint`, `git_sha` | the research store and the engine that produced them |
| `date` | the day it was pre-registered; it does not move on a re-run |
| `folds` | the walk-forward record at promotion: folds won, folds scoreable, whether the pick was stable, and the minimum in force that day (`seer_engine.lab.hardgate`). `not recorded: …` on a file written before the gate existed |
| `family_state` | whether any method in this one's `family` or ancestry read `test-failed` when it was promoted. The state **at promotion**; `lab test` does not re-check it, it prints a note |

Every value is read as text. The file is the record.

## Reading one back

```python
from seer_engine.lab import prereg

p = prereg.require_committed("M0007-V2")  # PreregError unless it exists, parses and is committed
p.config_digest
```
