---
name: update-stale-sera-methods-page
description: Use when a page on seertrade.site/sera reads against a bar the lab no longer holds — "/update-stale-sera-methods-page https://seertrade.site/sera/methods/M0022", "this method page is stale", "the checklist says 0.912 < 0.90", "the verdict still says rejected", "the page contradicts the gate panel", or after the owner moves DSR_MIN, MAX_DRAWDOWN, MIN_PROFIT_FACTOR or the N policy and the site has to catch up.
---

# Update a stale Sera method page

**One rule: no number on the page may be read against a bar from a different day.**

That is the whole job. `Luck check: no (0.912 < 0.90)` shipped to the owner because the cross came
from a trial's recorded `failed` (`DSR >= 0.95`, the bar on its run date) and the number beside it
came from the live gate. Both halves were correct; together they were nonsense. Every check below
exists to make that shape impossible, on **every** surface of the page — not just the one the owner
happened to look at.

**No human in the loop.** Decide and assume; never `AskUserQuestion`, never end a turn on a
question, never wait for approval. Write what you assumed into the commit message. Commit to `main`
and push at the end. The only allowed stop is terminal (missing tooling, a permission you lack).

## Invocation

```
/update-stale-sera-methods-page https://seertrade.site/sera/methods/M0022
/update-stale-sera-methods-page M0022
```

Take `MNNNN` (or `H-*`) from the argument; the URL is not fetched (the site is behind the Sera
gate, and the repo holds everything the page is built from).

## Where the page comes from

```
lab/lab.sqlite  --(lab export-json)-->  web/data/lab.json  --(next build)-->  the page
```

- `gate` in the snapshot is **resolved at export time** from `tuning.MAX_DRAWDOWN`,
  `tuning.MIN_PROFIT_FACTOR`, `dev._MIN_TRADES`, `store.DSR_MIN` and `store.DSR_POLICY`. Move a
  constant, re-export, and the published bars move with no data change.
- Each trial is published **twice**: the record (`failed` / `eligible` / `dsr` / `nTrialsAtRun`,
  the run date's bars, append-only, never changes) and the verdict (`failedNow` / `eligibleNow` /
  `dsrNow`, from `store.published_verdict` against that same gate). Snapshot v2.
- The prose (`methods.verdict`, `methods.analysis`, `insights.body`) is written by hand and is
  **not** derived from anything.

## Two kinds of staleness — fix each its own way

| | Derived | Written |
|---|---|---|
| what | ticks, counts, colours, chart reference lines, captions, table cells | the lede, the analysis sections, journal insights |
| source | `gate` + the trial's verdict fields | `methods.verdict`, `methods.analysis`, `insights.body` |
| fix | re-export; if a reader still mixes bars, fix the reader | `verdict`: rewrite. `analysis`: **append** a dated section |
| rewrite history? | nothing to rewrite | **No.** `methods_analysis_grows` refuses a rewrite and `insights` refuses UPDATE and DELETE |

A dated analysis section names the bars of its own day and stays exactly as written — that is the
lab's record, not a bug. The reader must still be able to tell *now* from *then*, which is what the
new section and the rewritten `verdict` are for. If an **insight** body names a superseded bar, you
cannot edit it: add a new insight that supersedes it and say so in the report.

## 1. Set up

```bash
REPO=/home/miftah/seer
PY=$REPO/engine/.venv/bin/python                  # the only venv; a worktree has none
WT=$HOME/.worktrees/seer/sera-MNNNN               # branch sera/MNNNN
git -C $REPO fetch origin main -q
git -C $REPO worktree add -b sera/MNNNN $WT origin/main
```

Work in `$WT`. Two things never move there:

- **The lab database is `$REPO/lab/lab.sqlite`.** It is shared with every parallel session; the
  worktree's copy is a stale duplicate. Every `lab` write passes `--db $REPO/lab/lab.sqlite`.
- **Python runs from `$REPO`'s venv**, with the worktree's sources:
  `PYTHONPATH=$WT/engine/src $PY -m pytest …` from `$WT/engine`. Without `PYTHONPATH` pytest
  silently tests the main checkout and you learn nothing about the branch.

Read the current bars once, and never hardcode them anywhere afterwards:

```bash
$PY -c "import json;g=json.load(open('$WT/web/data/lab.json'))['gate'];print(json.dumps(g,indent=2))"
$PY -m seer_engine lab --db $REPO/lab/lab.sqlite show MNNNN
```

## 2. Audit every surface

`web/app/sera/methods/[id]/page.tsx` in order. Go through **all** of it — a page is not fixed
because its loudest panel is. For each surface decide: derived or written, and does it agree with
the gate you just printed?

| # | Surface | Reads | Must |
|---|---|---|---|
| 1 | Header lede | `method.verdict` | state today's standing; no superseded bar as if current |
| 2 | Status chip | `method.status` | match `lab show`; run `lab reevaluate MNNNN` if a bar moved and it still reads `rejected` |
| 3 | `N = …` chip | `max(nTrialsAtRun)` | labelled as the run-date count, not as the gate's N |
| 4 | The idea | `hypothesis` | **frozen.** It is the pre-registration. Never edit it, even when it names an old bar |
| 5 | What could go wrong | `expectedFailure` | **frozen**, same reason |
| 6 | Did it work? | `workedSummary(best, gate)` | every one of the six sentences compares a number to the bar **at the same N** |
| 7 | Growth of 1 | curves | no bars involved; check the window text |
| 8 | Drawdowns | `gate.maxDrawdown` ref line | the line and its caption come from `gate`, not a literal |
| 9 | Year by year | curves | no bars involved |
| 10 | Against the hurdles | `gate.maxDrawdown` pass zone | zone, caption and the method's own dots agree with the gate |
| 11 | Every variant | `marks(t)`, `dsrNow`, `conditionTip(k, gate)` | every tick from `failedNow`; the DSR column at `gate.dsrN`; header tips from `gate` |
| 12 | Analysis | `methods.analysis` | sections are dated records; the newest must say where it stands now |
| 13 | Insights | `insights.body` | cannot be edited; supersede if wrong |
| 14 | Technical detail | `techRows(t)` | the record, and **labelled** as the record |

Then sweep for the shape mechanically, across the whole site rather than this page:

```bash
cd $WT
# Any reader that decides a pass/fail from the record instead of the verdict.
grep -rn --include='*.ts' --include='*.tsx' -e '\.failed\b' -e '\.eligible\b' -e '\.dsr\b' \
  web/app/sera web/lib/sera | grep -v '\.test\.'
# A bar written as a literal instead of read from the gate.
grep -rn --include='*.ts' --include='*.tsx' -E '0\.9[05]|15%|20%' web/app/sera web/lib/sera \
  web/components/sera | grep -v '\.test\.'
```

Every hit must be one of: a `*Now` field, a `gate.*` read, or an explicitly labelled display of the
run-date record. Anything else is the bug.

**Never re-threshold a DSR yourself.** `dsr` belongs to the N it was scored at. `M0007-N20-RAW`
records 0.9138 at N = 85 and reads 0.8985 at N = 110 — a pass and a fail from the same number.
Only the engine can re-score it (`store.dsr_at`); the web reads `dsrNow` and nothing else.

## 3. Fix

**Derived.** Change the reader (or the engine, if the snapshot is not publishing what a reader
needs) and re-export:

```bash
cp $REPO/lab/lab.sqlite $WT/lab/lab.sqlite
PYTHONPATH=$WT/engine/src $PY -m seer_engine lab --db $WT/lab/lab.sqlite export-json
```

Export with the **branch's** engine, or the committed JSON will not be the export of the committed
database and `test_the_committed_snapshot_is_the_export_of_the_committed_database` will say so.

**Written.** One command does both halves; `--verdict` replaces, the file is appended as a new
dated section (the date header is added for you — do not write one):

```bash
$PY -m seer_engine lab --db $REPO/lab/lab.sqlite note MNNNN \
  --file /tmp/note.md --verdict "<one or two sentences: the result, then where it stands under the bars in force now>"
```

The appended section should say, in the owner's plain English: which bars moved and when; where
each variant stands under them, in a table; which conclusions above are superseded and which still
hold; and that the numbers did not change — the bars did. Keep the method's own voice.

Then re-copy and re-export (the prose is in the database now), and re-read the page's source for
any sentence that the change has made false.

## 4. Gates — all of them, from `$WT`

```bash
cd $WT/engine && PYTHONPATH=$WT/engine/src $PY -m pytest -q          # never pass -o addopts; xdist is in addopts
cd $WT && $PY -m ruff check engine                                   # CI's first engine step
cd $WT/web && npx tsc --noEmit -p tsconfig.json && npx vitest run && npm run build
```

Four of these carry the invariant directly, and a red one is the answer, not an obstacle:

- `engine/tests/test_lab_snapshot.py` — the committed JSON is the export of the committed database.
- `engine/tests/test_lab_gate_wording.py` — shipped files and the newest `synthesis` insight do not
  state a superseded bar. **Add any new shipped file that states a rule to its `SCANNED`.**
- `web/lib/sera/lab.test.ts` — against the real snapshot: a scored trial misses the luck check
  exactly when its score is under the bar, the same for the drawdown, and record and verdict still
  differ somewhere (so the first two pins are not vacuous).
- `npm run build` — Vercel's gate. A build that fails here deploys nothing.

If you changed a rendering rule, pin the new behaviour before moving on. A fix with no test is a
fix that comes back.

## 5. Commit to main and push

```bash
cd $WT
sha256sum $REPO/lab/lab.sqlite $WT/lab/lab.sqlite    # must match: a parallel session may have written
git add -- <every path you touched, listed explicitly> lab/lab.sqlite web/data/lab.json
git commit        # see below
git -c rebase.autoStash=true pull --rebase origin main
cd $WT/web && npm run build                           # once more if the rebase brought anything in
cd $WT && git push origin main
git -C $REPO worktree remove --force $WT && git -C $REPO branch -D sera/MNNNN
git -C $REPO pull --rebase origin main    # its lab.sqlite now equals HEAD and reads clean
```

- **List paths explicitly.** The checkout is shared: `git add -A` would commit another session's
  work in progress.
- **Commit `lab/lab.sqlite` and `web/data/lab.json` together, always.** CI fails a database commit
  without its snapshot, and the site redeploys from each push.
- If the two SHAs differ, a parallel session wrote to the lab between your copy and your commit:
  re-copy, re-export, re-run the gates, and **include its rows** rather than reverting them.
- **Never `git checkout`, `git restore` or `git stash` the shared `lab/lab.sqlite`.** It is a
  binary another session may be mid-write in, and discarding it loses rows silently. Bringing the
  main checkout back to clean is a `pull`, never a restore.
- The commit message says which bars moved, which surfaces were reading the wrong day, what now
  reads what, and the counts from the gates you ran.

Then report to the owner: the surfaces that were stale, the ones you checked and found correct,
anything that could not be edited (frozen hypotheses, insight bodies) and what supersedes it.

## Never

- Rewrite a dated analysis section, a hypothesis, an expected failure or an insight. They name the
  bars of their own day; that is the record working, not failing.
- Compare `dsr` to `gate.dsrMin`. Use `dsrNow`.
- Hardcode a bar anywhere — a page, a caption, a test, this skill. Read it from `gate`.
- Weaken a test to make a page pass.
- Leave `lab/lab.sqlite` committed without `web/data/lab.json`, or either one exported by an engine
  other than the one in the same commit.
