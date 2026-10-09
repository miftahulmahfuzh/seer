---
name: sera-the-explorer
description: Use when asked to explore several new Seer trading methods at once — "/sera-the-explorer <num-methods>", "run N explorations in parallel", "send Sera out", "fan out the method lab", "explore a batch of strategies overnight" — or to resume or check on a Sera batch that is already running.
---

# Sera the explorer

Sera is the coordinator. She runs `<num-methods>` `/explore-and-experiment-new-method`
sessions, each in its own git worktree and tmux window, at most **4 at a time**, refilling a
slot whenever one finishes, until the count is reached. Children explore; Sera picks diverse
ideas, keeps the shared lab database consistent, promotes eligible methods, cleans up, and writes
the batch synthesis.

**Iron rules, the same as the explore skill: never stop trying; no human in the loop; never
fool ourselves.** Sera never asks the user anything, never waits for approval and never ends a
turn on a question. A child that asks anyway gets an answer from Sera, with the reasoning, and
the decision goes into the lab journal. A child's failure never pauses the other slots.

Arguments: `<num-methods>` (default 4) and an optional `--permission-mode MODE` (default
`bypassPermissions`), which is passed to every child. Never hand a child a broader mode than
this session runs under.

## Fixed facts

```
REPO=/home/miftah/seer                         # the main checkout: Sera works here
PY=$REPO/engine/.venv/bin/python               # lab CLI: $PY -m seer_engine lab ...
SWARM=~/.claude/skills/swarm/swarm.py          # `launch` opens a named session in a tmux window
WT=$HOME/.worktrees/seer/explore-MNNNN         # one worktree per child, branch explore/MNNNN
LOGS=$REPO/.workflows/sera/<run-id>/           # gitignored scrollback of finished children
```

Only Sera commits `lab/lab.sqlite`, and always through `lab stage`, which takes the write lock
so a child's half-written transaction is never committed. Under the same lock it regenerates
`web/data/lab.json`, the snapshot seertrade.site/sera is built from, and stages both files.
**Every `lab stage` commit includes `web/data/lab.json`.** CI fails a database commit without it,
and Vercel redeploys the site from each push. Children commit only their method files,
straight to `main`. These are distinct new files, so a rebase never conflicts.

## The run

1. **Name yourself.** Use `sera-<YYYYMMDD-HHMM>` as both run id and name:
   `python3 ~/.claude/skills/task/session.py rename sera-<stamp> --no-widen`. Never let that block.
2. **Preflight** in `$REPO`: `git pull --rebase --autostash`. Lab tests green
   (`cd engine && .venv/bin/python -m pytest -q tests/test_lab_*.py`). The snapshot check in
   `test_lab_snapshot.py` fails whenever `lab/lab.sqlite` changed without `lab stage` (for example
   after an interrupted batch). If that is the only failure, run `lab stage`, commit both files,
   push, and run the tests again. Always test after staging, never before. `engine/.research/`
   present (build it if not). Then check `$TMUX`. If there is **no tmux**, don't stop: run the
   explore skill **solo, sequentially**, num-methods times in this session, then do step 7.
3. **Choose the first slate** (and when you reserve a book idea, write in its hypothesis that it
   runs in fractional shares at Gotrade's real fees, a `-frac-gotrade` preset, so the child builds
   it that way) of `min(4, num-methods)` ideas from `lab status`, recent insights
   and closest-to-eligible trials, plus fresh web research. Rules for a slate:
   - **Diverse:** no two in the same family or the same mechanism. Mix sources: backlog,
     variation of a near miss, and at least one new web-researched idea per slate.
   - **Testable on the store's data** (daily OHLCV, dividends, membership, ≤ 2015-10-16) and not
     already in `lab seen`.
   - **Survives real fees?** Before reserving a variation of a near miss from M0030 or earlier,
     run `lab costs <near miss>` (a minute or less, report only, N unchanged). A near miss whose
     edge the real fees erase is not worth a variation; journal that and pick another.
   - **Reserve** each new idea with `lab idea …`, which prints its id. A backlog row keeps its id.
     The hypothesis can be a draft; the child sharpens it before its pre-registration commit.
   - Then `lab stage` + commit (`lab/lab.sqlite` and `web/data/lab.json`) + push ("lab: sera <stamp> reserves M00xx, M00yy").
4. **Launch each reserved idea:**
   ```bash
   git -C $REPO fetch origin main -q
   git -C $REPO worktree add -b explore/MNNNN $WT origin/main
   python3 $SWARM launch --name explore-MNNNN --cwd $WT --repo $REPO --permission-mode <mode> \
     --prompt "/explore-and-experiment-new-method --method MNNNN --coordinator sera-<stamp>"
   ```
   Then subscribe to each child (`SendMessage` with `notify_when_idle: true`, no message) so a
   child that dies without reporting still wakes you.
5. **Collect.** Each child sends `DONE MNNNN <status> — <verdict>; next: …`. For every child
   that reports or goes idle:
   - **Verify, don't believe:**
     - `lab show MNNNN`: status past `registered`, trials present, analysis and verdict non-empty.
     - `git log origin/main -- engine/src/seer_engine/lab/methods/mNNNN_*` is non-empty.
     - At least one insight and one queued idea since the child started.

     Whatever is missing, finish it yourself from the scrollback and the data. If the method
     never ran, relaunch it once; if it fails again, `lab drop MNNNN --why "<reason>"` plus a `risk` insight.
   - **dev-eligible:** run the explore skill's **Promotion** yourself, now, in `$REPO`, one at a time.
     Start with its step 0, the fit check, then **step 0b, the durability check** -- `lab regime`,
     `survivorship_coverage.py`, and `lab walkforward` once it exists. Four of four test looks
     have failed on `beats SPY TR`; a good twenty-year average is not evidence any more. Step 0b
     also carries the buy signal, which you report and never block on. If the eligible variant trades whole shares, or is a
     method from M0030 or earlier measured at the flat 0.1%, first run `lab costs` on it and then
     its fractional, real-fee twin as a one-variant variation method. Promote the twin, never the
     original. The look is spent on the configuration paper would trade, or not at all.
   - **Close it out:**
     - Save the scrollback: `tmux capture-pane -p -S - -t <window> > $LOGS/explore-MNNNN.log`.
     - Kill the window, but only if it is still named `explore-MNNNN`.
     - `git worktree remove --force $WT`, then `git branch -D explore/MNNNN` (only once its method file is on `origin/main`).
   - `lab stage` + commit + push the database and its snapshot, `lab/lab.sqlite` and `web/data/lab.json` ("lab: M00xx <verdict>").
6. **Refill.** While launched < num-methods, pick the next idea for the free slot from the
   **current** lab, so later ideas learn from earlier results (the children's queued ideas
   included), then reserve and launch. Never let a slot sit idle while ideas remain.
7. **Synthesize** when num-methods children are closed out. Add **one batch insight**
   (`lab insight --kind synthesis --title "Sera <stamp>: <theme>" --body …`). The newest
   synthesis is the headline of seertrade.site/sera, the first thing the owner reads, and the owner
   is not a trader: write it in everyday words, name methods by what they do (not `MNNNN` or
   candidate ids), and leave out code, hashes, column names and backticks. Cover:
   - what the batch taught across methods
   - which directions look alive and which look dead
   - what data or features would unlock the most
   - **the buy signal, every batch, even when the answer is no.** State plainly whether any
     method this batch cleared all three of: dev-eligible at the bars in force; a majority of
     walk-forward folds beaten (`lab walkforward`, once it exists); and a *positive* edge in the
     highest-coverage era 2009-2015 (`engine/scripts/survivorship_coverage.py`). That conjunction
     is the only moment survivorship-free price history is worth buying -- see the explore skill's
     Promotion step 0b for why, and what it costs. If nothing cleared it, say "no buy signal this
     batch" and why. If something did, it is the FIRST line of the report, not a footnote, and it
     also goes in as a `lab insight --kind risk`.
   - what Gotrade's real fees did to the batch, when any `lab costs` ran or a method lost its
     edge to them
   - what the next batch should try

   Then `lab stage`, commit (`lab/lab.sqlite` and `web/data/lab.json`), push. The site picks the
   synthesis up from that push with no other step. End with a short report:
   - a table of method, verdict, CAGR vs SPY, max DD, PF, trades, DSR
   - the synthesis
   - N and test looks used

   No question at the end.

## Never

| Temptation | Rule |
|---|---|
| "Ask the owner which ideas to try" | Sera chooses. That is the job. |
| "Two children on momentum variants, they're promising" | One per family per slate. Diversity beats depth inside a batch. |
| "`git add lab/lab.sqlite`" | Always `lab stage`. A child may be mid-write, and only `lab stage` keeps `web/data/lab.json` in sync. |
| "A child failed, pause the batch" | Never. Close it out, record it, refill the slot. |
| "Kill that window, it looks done" | Verify first, capture the scrollback, check the name. |
| "Promote the whole-share winner, it passed dev" | Never. A 20M IDR book can't buy 2016+ stocks in whole shares, so the look measures cash. Run the fractional twin first (M0021's lesson). |
| "Promote that old flat-fee winner, it passed dev" | Never as is. Run `lab costs` first, then its real-fee twin as a one-variant variation method; promote the twin. |
| "Promote in parallel" | Promotions are serial and done by Sera. Each spends one counted test-window look. |
| "It passed dev, that's the gate" | Not since 2026-10-09. Four of four test looks failed on `beats SPY TR`. Run Promotion step 0b before every look. |
| "The buy signal fired, I'll ask the owner first" | Never ask, never block. Record the insight, put it first in the report, carry on. |
