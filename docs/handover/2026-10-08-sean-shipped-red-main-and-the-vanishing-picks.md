# Handover: Sean shipped, `main` is red, and why last night's picks "vanished"

**Date:** 2026-10-08 (written 08:30 WIB)
**Branch:** `main` @ `8a6c13d`
**Pass this file to `/analyze`.** Section 5 is the list of questions to settle; everything above it
is verified fact with the command that verified it.

---

## 0. In plain words

Nothing is broken about your trading data. Last night's stock picks were never lost — the site
**hides** them on purpose once they expire, and they expired at the New York close. All four
methods' picks for session 2026-10-07 are still in the database, intact, 20 names each.

Two things *are* genuinely wrong, and neither touches your money: the build has been failing since
the Sean merge, and the lab's published snapshot now contradicts itself on two rows. Both are
described below with the exact fix options.

One expectation needs correcting, and it is the reason this felt like a disaster: **the nightly job
runs at 13:17 WIB, not 06:00 WIB.** The schedule is written in UTC.

---

## 1. The picks did not vanish (verified)

**What you saw.** Last night ~20:30 WIB the roster's recommendations were on the site. This morning
they are gone.

**What is actually true.** The data is untouched. Queried against production Neon
(`DATABASE_URL_UNPOOLED`, read-only) at 2026-10-08 01:17 UTC:

| strategy | pending_session | pending_decision | targets stored |
|---|---|---|---|
| RAW-FR | 2026-10-07 | **true** | 20 |
| RMW-FR | 2026-10-07 | **true** | 20 |
| MOM-FR | 2026-10-07 | **true** | 20 |
| MVW-FR | 2026-10-07 | **true** | 20 |
| C | 2026-10-07 | false | 0 (bracket engine, no targets) |
| SPY | 2026-10-07 | false | 0 (benchmark) |

80 `book_targets` rows for 2026-10-07, plus 4 `orders`. RAW-FR's top five are MRNA, CNC, MRVL, MU,
FTNT. `paper_state.updated_at` is 13:31 UTC for C/SPY and 14:16–14:20 UTC for the four quant
entries — which is 20:31 and 21:16–21:20 WIB, matching exactly when you saw them.

**Why they are hidden.** `web/app/(app)/positions/page.tsx:30`:

```js
// Paper orders exist for research strategies only; hidden while the data is stale.
const showOrders = !!strat && !strat.isBenchmark && !run.stale;
```

and `web/lib/session.ts:32`: *"Picks are stale when the latest successful run targets an earlier
session."* Running the site's own function at the current moment:

```
now UTC = 2026-10-08T01:17:40Z   (08:17 WIB, 21:17 ET)
nextUsSession(now)        = 2026-10-08
isStale('2026-10-07', now) = true     ->  showOrders = false
```

The picks were a decision for the **2026-10-07 US session**. That session opened and closed while
you slept (close 16:00 ET = 03:00 WIB). Acting on them now would be acting on a spent decision, so
the page hides them. This is the design working, not a fault — but see question Q1: hiding them
with no explanation is indistinguishable from losing them, which is what made this alarming.

## 2. The P/L is not late — it was never due at 06:00 WIB (verified)

`paper_state.last_session` is still **2026-10-06**; `pending_session` is 2026-10-07 with
`pending_decision = true`. The 10-07 session has not been *stepped* yet, so there is no P/L to show:
`equity_snapshots` holds only 2026-10-06 rows, all at the starting 560.5067 USD.

The nightly that steps it is `.github/workflows/nightly.yml`:

```yaml
- cron: '17 6 * * 2-6'      # 06:17 UTC = 13:17 WIB
- cron: '41 9 * * 2-6'      # 09:41 UTC = 16:41 WIB   (retry)
- cron: '41 12 * * 2-6'     # 12:41 UTC = 19:41 WIB   (retry)
```

The file's own comment confirms the offset: *"Retry slots, 09:41 and 12:41 UTC (16:41 and 19:41
WIB)"*. So the first P/L for the roster's first paper session lands at **13:17 WIB today**, roughly
seven hours later than expected. Nothing is wrong; the clock was read as WIB.

The reason the run is that late is in the workflow's own header comment: the data vendor refuses a
session that is still "today" in Eastern time, so the run must happen the *morning after* the
session, after ET midnight.

## 3. `main` has been red since the Sean merge (verified)

Three consecutive CI failures on `main`: `37654291246`, `37697386965`, `37698865353`, plus
`37711466542` on the doc commit below. **Two independent causes, neither of them Sean being
broken.**

**3a. The engine skip-guard misfires.** `.github/workflows/engine-ci.yml:70` fails the build when any
line matches `^SKIPPED`, with the message *"engine tests were skipped; PG_TEST_URL did not reach
pytest"*. That message is now false — the run reports `3362 passed, 2 skipped`, so the DB tests ran.
Two deliberate `skipif`s trip it:

- `test_lab_costs.py:265` — needs `SEER_LAB_COSTS_LIVE`, which CI does not set.
- `test_lab_npolicy.py:319` — skips because `COMMITTED_DEV_TRIALS = 110` while `lab/lab.sqlite` now
  holds **128** trials. The lab moved; the constant did not.

The guard cannot distinguish a misconfiguration (what it was written for) from an intentional skip.

**3b. A real lab-snapshot inconsistency.** `web/lib/sera/lab.test.ts:50` asserts every scored trial
misses the luck check exactly when its score is under the bar. Two rows violate it:

| candidateId | dsrNow | failedNow | window |
|---|---|---|---|
| `M0021-B70-RAW` | 0.513013 | `['beats SPY TR']` | **test** |
| `M0029-B70-RAW-FRAC` | 0.388958 | `['beats SPY TR', 'max DD <= 20%']` | **test** |

Both are `window: "test"` rows, and the published gate is `dsrMin 0.90, dsrPolicy "all-trials",
dsrN 126 dev trials`. **This assertion has never seen a test-window trial before** — the lab went
from 0 test-window looks to 2. The DSR bar is a *dev-window* multiple-testing correction; a
pre-registered confirmatory look is not luck-gated the same way, which is why `failedNow` for these
rows correctly omits a DSR failure. So the data looks right and the test encodes a dev-only
assumption that has just expired. See Q2 — there is more than one defensible fix and it is a
lab-design call.

## 4. Sean, as shipped (verified)

7 phases, 116 files, ~40k insertions, merged at `b16cffd`; migration 015 applied; set pruned.
`/sean` in the web app (Overview / Trades / Plan), an `engine/src/seer_engine/sean/` package
(ledger, marks, equity, calibrate), a GLM-4.6V screenshot reader, and a nightly step
(`sean marks`, currently logging *"no orders yet; nothing to mark"*).

**The most consequential part is not the tracker — it is `sim/costs.py`.** Fitted to 30 real Gotrade
receipts, it finds that at the sizes actually traded (a few tens of dollars a slot) real fees are
**3–5× the assumed 0.1%/side** every lab trial has been measured at. Re-measured on the roster
(`449fa34`, report only, N unchanged at 126):

| method | assumed fees | real Gotrade fees |
|---|---|---|
| RAW `M0007-N20-RAW` | +1502% | **+1126%** |
| MOM `M0002-REL-85` | +940% | **+763%** |
| MVW `M0008-N30-C07` | +727% | **+536%** |
| RMW `M0022-W-TV16` | +789% | **+543%** |
| SPY, same fees | — | +350% |

All four still beat SPY, so no verdict is overturned. The fit documentation names the one receipt
that does not match the schedule (LLY $366.62 paid $1.08, not $1.10) rather than smoothing it away.

## 5. Questions the analysis must settle

**Q1 — a hidden pick should say it is hidden.** The staleness rule is right: a spent decision must
not be actionable. But the page currently renders the same emptiness for "last night's picks have
expired, the next set arrives 13:17 WIB" and for "nothing was ever produced" and for "the pipeline
failed". That ambiguity cost an owner an alarming morning, and it will do so again every single day,
because the picks go stale every single day at the New York close. Settle what the page should say
instead — the honest line is something like *"2026-10-07's decision is spent; the next runs
13:17 WIB"* — and whether the expired picks should remain visible, greyed and labelled, rather than
removed. Note the constraint: whatever is shown must never be mistakable for a live instruction.

**Q2 — the luck gate and the test window.** Pick one, and write down why: (a) the assertion excludes
`window === 'test'` rows; (b) the exporter stops publishing `dsrNow` on test rows, since a figure
nothing gates on invites exactly this; (c) test rows carry an explicit "not luck-gated" marker the
UI and the test both read. (b) and (c) touch the published snapshot and the Sera pages; (a) touches
one test. The deeper question is whether a test-window look should carry a DSR at all.

**Q3 — the CI skip-guard, and the constant that aged.** Two halves. First, narrow the guard so it
catches what it was written for without failing on deliberate skips (match the specific
"no PG_TEST_URL" signature, or allowlist known skip reasons). Second, decide what
`COMMITTED_DEV_TRIALS = 110` should be now that the lab holds 128 — a re-pin, a floor, or a value
derived from the committed database rather than typed. It will age again; prefer the form that
cannot.

**Q4 — a nightly run has been queued for over eight hours.** `37655513074`, queued since
2026-10-07T16:54 UTC. `nightly.yml` uses `concurrency: {group: seer-db-writer,
cancel-in-progress: false}`, so runs serialise rather than cancel; `sean.yml` and `repick.yml` should
be checked for membership in that group. Establish whether this is harmless (the nightly is
idempotent — it logs *"session already succeeded; nothing to do"*) or whether a stuck run can delay
tonight's real one, which is the one that produces the first P/L.

**Q5 — nobody is watching the thing that matters.** The roster's first paper session stepped with no
alert either way. CI has been red for ~9 hours with no signal. Settle what minimum monitoring the
owner gets — the candidate worth pricing is a single daily line (session stepped y/n, picks
published y/n, CI green y/n) rather than a dashboard nobody opens.

## 6. Owner context

Two standing preferences from the 2026-10-07 handover still bind: the owner **is not a quant**, so
prose stays plain — numbers with their meaning, no jargon without a gloss; and the owner **prefers
measuring to estimating**. Both were honoured in §14 and should be honoured here: Q1 in particular
is a plain-language problem, not a UI-polish problem.

The owner reads times in **WIB**. Every schedule in this repo is written in **UTC**. That mismatch
caused this morning's alarm and is worth fixing in the docs even where the crons stay as they are.

## 7. Verification

Everything above was measured, not assumed:

- Production Neon, read-only, 2026-10-08 01:17 UTC — `book_targets`, `orders`, `paper_state`,
  `equity_snapshots`, `strategies`. No write was issued.
- `isStale('2026-10-07', now)` executed against `web/lib/session.ts` via `npx tsx`: **true**.
- Engine suite on `main` @ `8a6c13d`: `3362 passed, 2 skipped` with both `PG_TEST_URL`
  (`postgresql://postgres:pg@localhost:55432/postgres`, documented at `engine/tests/conftest.py:6`)
  and `PYTHONPATH`.
- `lib/sera/lab.test.ts` reproduced locally: 1 failed, 9 passed.
- CI failures read from `gh run view --log-failed`.

## 8. What landed just before this

- `delisting-stress-roster-rules`, 5 phases, merged `3f112cf` — design §14 (the delisting stress
  test), method-lab §8 (the roster replacement rule), the dev-gate trades-bar guard, and the MOM-FR
  verdict (**keep**). Ledger at `.workflows/orchestration/delisting-stress-roster-rules/`.
- `8a6c13d` — P3, P3b and P6a in `engine/package_readme.md` now say explicitly that design §14 does
  **not** cover them: §14 ran on the dev window (1996–2015) against the research store on the four
  F-family book strategies, while those gates are Strategies A, A2 and B on Neon bars from
  2015-10-19. Their 115 unserved members are not the store's 404 in-window exits.
