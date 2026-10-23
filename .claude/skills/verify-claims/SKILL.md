---
name: verify-claims
description: Use before any number leaves this session — "/verify-claims docs/plans/2026-10-23-handover.md", "check these figures before I report", "verify the claims in my analysis", "are those counts right", "I wrote this from the handover, confirm it", or before reporting a method's result to a coordinator, writing a journal entry, or answering the owner with a figure. Re-measures every numeric claim in a document against lab.sqlite and the research store, names the arm and the store each figure came from, and lists every downstream artifact a mismatch has already contaminated.
---

# Verify every claim before it leaves this session

**One rule: a number is unverified until this session measured it.** Not read it in a handover,
not carried it from a brief, not remembered it from a run that scrolled past. The lab's recurring
failure is not bad arithmetic — it is a correct number quoted against the wrong arm, the wrong
store or the wrong day, which reads as fact and cannot be told apart from one by a reader.

Arguments: a path to the document to check (an analysis doc, a handover, a draft journal entry, a
message about to be sent). With no argument, check the numbers in this session's own last report.

## 1. Collect the claims

Read the document and list every figure that asserts something about the world. All of these
count, and the ones people skip are in the second group:

- returns, CAGR, drawdown, profit factor, MAR, Sharpe, exposure, turnover, trade counts
- **method and trial ids**, insight ids, candidate ids
- **counts and denominators** — "4 of 22 variants", "67 clusters", "nine dev-eligible methods"
- **population sizes** — how many methods, trials, symbols, folds, draws
- comparisons to SPY, to a control arm, to a sibling variant, to another store
- dates and windows, including "the dev window ends …" and any era boundary

Anything with a digit in it that a reader could act on. A claim with no digits but a quantifier
("every variant", "none of them", "the only one that") is a claim about a count: verify it too.

## 2. Read the lab, do not run it

Measure from a read-only connection, never from a write path:

```bash
engine/.venv/bin/python - <<'PY'
import sqlite3
c = sqlite3.connect('file:lab/lab.sqlite?mode=ro', uri=True)
...
PY
```

Why: `trials`, `trial_funding`, `trial_moments`, `trial_provenance`, `method_folds`,
`method_amendments` and `insights` all carry `_no_update` and `_no_delete` triggers, `methods`
carries `methods_analysis_grows`, `methods_hypothesis_frozen` and `methods_status_forward`. The
lab is a record, and verification must not be able to write to it even by accident. A `lab`
subcommand opens the DB for writing and applies any pending migration on connect — measured
2026-10-23 on an up-to-date schema it left the file byte-identical, but with a migration pending
it dirties `lab/lab.sqlite`, which a peer session is also writing.

When only a report command can produce the figure (`lab gate`, `lab exposure`, `lab survivorship`,
`lab walkforward`, `lab timing`, `lab costs`, `lab names`, `lab turnover`, `lab shortfall`,
`lab regime`, `lab kin`, `lab dressing`, `lab control`, `lab luck`), run it — they are read-only by
design — and **never pipe it through `grep`**: the pipeline's status is grep's, so a refusal
(exit 2) or an error (exit 1) reads as success. Redirect to a file in the scratchpad and read that.

## 3. Measure each claim at its own source

| Claim | Where it actually lives |
|---|---|
| a trial's return, fall, PF, exposure, turnover | `trials` row for that `n` |
| what the owner's money did | `trial_funding.mwr` against `trial_funding.spy_tr_mwr` |
| "beat SPY" | both of the above, and say which one you mean |
| pass / fail, eligibility | `trials.failed`, `trials.eligible` — and the bars in force **today** |
| luck / DSR | `lab luck`, or `published_verdict` in `lab/store.py` — never the stored `dsr` alone |
| fold record | `method_folds` (`folds_won`, `folds_total`, `majority`) |
| a journal claim | the `insights` row by **id**, not by title |
| a method's state | `methods.status`, `methods.verdict` |
| anything about prices | the store the trial actually used: `trials.store_fingerprint` |
| the web mirror | `web/data/lab.json`, which CI checks row for row against the DB |

## 4. The traps that make a right number wrong

Each of these has already shipped a false statement from this lab. Check every claim against the
ones that apply before calling it verified.

- **Two return columns.** Funded and de-funded disagree in sign on dozens of trials (30 of 761
  when that was last counted; re-count rather than quoting it). The pass/fail
  screen reads the money column; the fold majority reads the other. A return quoted without saying
  which is not a verified number.
- **Two stores.** A ratio taken across the dev store and the survivorship-check store is not a
  comparison — one such "0.0059 miss" was a store boundary worth 0.0067. Read
  `store_fingerprint` for **both** arms of any gap you quote.
- **The arm.** `best_dev_eligible` has no role filter, and the era-edge column is hindsight-best,
  not the promoted arm. Before quoting "the method's result", name the candidate id and check
  whether that arm is the treatment or the control it was registered to beat.
- **The day.** DSR is scored against the trial count at its run date and moves when unrelated
  methods land; a recorded `failed` was judged against the bar in force then, not now. Never cross
  a recorded verdict with a live bar.
- **The era.** A lead measured whole-window can reverse after 2009, and the price of a point of
  exposure ranges 34x between eras. A single-window number is a claim about that window only.
- **Draw noise.** 19 identical rules span 7.5 pts/yr and 21 pts of fall. A lead under ~15 pts
  against one blind draw is inside the coin's own width, so "it beat the control" needs k draws and
  p = 1/(k+1), not one.
- **Title collisions.** In one audit, 7 of 12 journal rows that looked like duplicates were
  different arms.
  Identify an insight by id and `doc_key`, never by title.

## 5. Produce the table

One row per claim, nothing summarised away:

```
claim (as written) | source command | measured | MATCH / MISMATCH / UNVERIFIABLE
```

`UNVERIFIABLE` is a real and useful verdict — a figure from a run whose store is gone, or from a
report that cannot be reproduced. Say so plainly; do not quietly let it through as a MATCH.

## 6. On a mismatch, chase it downstream

The wrong number has usually already been copied somewhere. Fix the document, then walk this list
and name every one that needs correcting, whether or not you can correct it yourself:

- **the journal** — `insights` rows cannot be edited or deleted. Correct one by appending a new
  entry with `lab insight --kind … --supersedes <id>` (or `lab link <new> --supersedes <old>` for
  an entry written before the journal had versions). The wrong entry keeps its place and gains a
  successor. Carry the `--doc-key` across so the two read as versions of one thing.
- **`methods.analysis`** — grows only, so a wrong analysis is corrected by appending the
  correction, never by rewriting the prose.
- **the web mirror** — re-run `lab stage` from the main checkout, or CI goes red on the row-for-row
  check.
- **`.workflows/todos.md`, handovers, plan docs** under `docs/plans/` that quote the figure.
- **memory files** in `~/.claude/projects/-home-miftah-seer/memory/` — a wrong one gets corrected
  or deleted, and the index line with it.
- **messages already sent** — any coordinator, sibling session or report that already has the
  number. You cannot unsend it; say explicitly in your report which messages carried the bad figure.

## 7. Then report

Lead with the verdict — how many claims, how many matched — then the mismatches with their
corrections, then the table. If everything matched, say that in one line and name the commands
that proved it, so the next session can re-run them instead of trusting this one.
