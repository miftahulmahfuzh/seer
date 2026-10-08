# P1-ENG-A002 — Publish the money-weighted return to the Sera site

**Card**: [miftahulmahfuzh/seer#3](https://github.com/miftahulmahfuzh/seer/issues/3) · round 1 ·
2026-10-08
**Branch**: `task/3-publish-the-money-weighted-return-to` off `origin/main` @ `4560c2a`

## The problem

`lab-realistic-gate` phase 2 made `lab run` fund the book on the owner's real schedule
(+5,000,000 IDR on the 25th of each month, 10,000,000 IDR start) and records one `trial_funding`
row per funded trial carrying `mwr` and `spy_tr_mwr`. Neither reaches anything the owner can see:
`lab show` does not print them, `store.snapshot` does not publish them, and
`/redo-sera-experiments` works around that with a raw SQL snippet against the database.

Measured by phase 2 on one funded run: `total_return` 10.7821 (+1078%) against `mwr` 0.0764
(7.6%). Almost all of the +1078% is the owner's own deposits accumulating — `metrics.py` says so
itself ("not returns at all … the recorded shape of the curve"). Until `mwr` is published the site
shows the flattering number and hides the true one.

**State at the base commit**: 128 trials, **0** funding rows. So this change publishes two null
fields today and lights up the first time `/redo-sera-experiments` runs a twin. Everything below
is therefore verified against a synthetic funded row in the tests, not against committed data.

## Approaches

### A. Two new nullable trial fields, and a column of their own on the method page — **chosen**

`trials[].mwr` and `trials[].spyTrMwr`, null for an unfunded row. On `/sera/methods/[id]` the
funded pair gets its own labelled column, shown only when some trial on the page has one; on such
a row the Return and "Growth a year" cells go blank with the reason, because with deposits in the
book neither is a return.

| Criterion | |
|---|---|
| Convention | `spyTrReturn` / `spyTrCagr` are already published this way, and `luckGated` is the precedent for publishing a fact the web must not re-derive. |
| Scope | Exactly the two fields the card names, and one page. |
| Verifiability | The snapshot contract test pins the key set and the version; a vitest fixture with a funded trial proves the column and the blanking. |
| Reversibility | One commit: the fields are additive and nothing reads them unless they are non-null. |

### B. Swap the money-weighted numbers into the existing Return / Growth-a-year columns

Smallest possible diff — no new column, no conditional rendering. **Lost** on the card's own
floor: a funded trial's headline would then sit in the same column as 128 unfunded total returns,
two orders of magnitude apart. That is precisely the comparison this task exists to prevent.

### C. Publish a `funding` sub-object: `mwr`, `spyTrMwr`, `depositsUsd`, `depositsN`, `schedule`

Richest, and `schedule` is genuinely good prose for the page ("+5,000,000 IDR on the 25th of each
month"). **Lost** on scope: three of the five keys have no consumer, and every published key is a
contract `test_lab_snapshot.py` pins for ever. The two the card names are added now; the rest can
follow a card that needs them.

## The ambiguity, and which reading was built (4c)

**"A funded trial"** could mean a row that *has* a `trial_funding` row, or a row whose
money-weighted pair is actually measurable. They differ for a book that was wiped out: funded, but
`mwr` is NULL.

Built: **money-weighted display iff both `mwr` and `spyTrMwr` are non-null** — which is exactly
`dev.beats_spy_tr`'s own branch (`if mwr is not None and spy_mwr is not None`). The losing reading
is a third published marker, a `funded: boolean` alongside the pair, in the shape of `luckGated`.
It lost because the engine *itself* falls back to the total-return comparison when either number is
missing, so a row marked "funded" while its verdict was decided on total return would make the page
disagree with the tick printed beside it — the same class of defect as `0.912 < 0.90`. No third
field is published; one helper in `derive.ts` mirrors the engine's branch and says so.

## Steps

1. **`engine/src/seer_engine/lab/store.py`**
   - `SNAPSHOT_VERSION` 4 → 5, with the reason written in the running comment block above it.
   - `_snapshot_trial(t, v)` → `_snapshot_trial(t, v, f)` where `f` is the `trial_funding` row or
     `None`; it adds `"mwr"` and `"spyTrMwr"` through `_num`.
   - `snapshot`'s `trials` comprehension passes `funding_of(conn, t["n"])`, the same per-row read
     `published_verdict` already makes in this loop. `funding_of` answers `None` on an unmigrated
     read-only connection, which is what keeps `snapshot`'s promise.
2. **`engine/src/seer_engine/commands/lab.py`** — `_show` prints a second line for a trial with a
   funding row: what the money earned, against the same deposits in SPY TR, with the deposit count
   and the schedule in the owner's own words, and one clause saying the return above counts the
   deposits as gains.
3. **`engine/tests/test_lab_snapshot.py`** — `TRIAL_KEYS` gains the two keys, the version pin goes
   to 5, and two tests: an unfunded trial publishes both as null; a trial with a `trial_funding`
   row publishes both numbers.
4. **`web/lib/sera/types.ts`** — `version: 5`, the two fields on `LabTrial`, documented as *not a
   return comparison* and as the pair `beats SPY TR` is decided on for a funded row.
5. **`web/lib/sera/fixture.ts`** — `mwr: null, spyTrMwr: null` in `trial()`.
6. **`web/lib/sera/derive.ts`** — `moneyWeighted(t)` returns `{ mwr, spyTrMwr }` or null, mirroring
   `dev.beats_spy_tr`; `gateChecks`'s `spy` row reads it so the value and target printed beside the
   tick are the numbers the engine judged on.
7. **`web/app/sera/methods/view.ts`** — `conditionSentence('spy')` says the money-weighted sentence
   for such a row; `techRows` appends the two rows only for such a row.
8. **`web/app/sera/methods/[id]/page.tsx`** — the conditional column, and the blanked cells.
9. **`web/lib/sera/glossary.ts`** — one entry, in everyday words: what rate your money actually
   earned, given you kept adding to it.
10. **`.claude/skills/redo-sera-experiments/SKILL.md`** — the raw SQL snippet goes; the step reads
    the numbers off `lab show` instead.
11. **`web/data/lab.json`** regenerated by `lab export-json`, then `lab/lab.sqlite` restored by
    path (every lab command migrates it on connect, so even a read dirties it) and **only** the
    JSON committed.

## Done when

- A funded trial's `mwr` and `spy_tr_mwr` show on its method page, labelled so a non-trader can
  tell which number is which, and never in a column shared with an unfunded total return.
- `lab show` prints both for a funded trial.
- The 128 unfunded trials render exactly as they do today, both fields null.
- The SQL snippet is gone from `/redo-sera-experiments`.
- The repo's CI gate passes: `ruff`, the engine suite, and the web's `vitest` / `tsc` / `next
  build`.
