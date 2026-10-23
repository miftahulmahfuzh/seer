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
SV=$REPO/engine/.research-sv                   # the survivorship-check store; children reach it via SEER_SV_STORE=$SV
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
   present (build it if not), and `engine/.research-sv/` present
   (`$PY -m seer_engine survivorship_store --report` prints its coverage; rebuild per
   `docs/runbooks/survivorship-store.md` if it is missing). Each child exports
   `SEER_SV_STORE=$SV` from the explore skill's table, so it can keep a survivorship-check promise
   the same day. Then check `$TMUX`. If there is **no tmux**, don't stop: run the
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
   child that dies without reporting still wakes you. **If this coordinator is not a Claude Code
   session** — it has no `SendMessage` tool, for example it runs under Hermes — skip the
   subscription and poll `tmux capture-pane -p -t explore-MNNNN` plus the shared database. A child
   that reports "no agent named sera-<stamp> is reachable" is behaving correctly; that message is
   not a failure and needs no relaunch.
5. **Collect.** Each child sends `DONE MNNNN <status> — <verdict>; next: …` when it can reach the
   coordinator; with a non-Claude coordinator, read its pane. For every child that reports or goes
   idle:
   - **Verify, don't believe:**
     - `lab show MNNNN`: status past `registered`, trials present, analysis and verdict non-empty.
     - `git log origin/main -- engine/src/seer_engine/lab/methods/mNNNN_*` is non-empty.
     - At least one insight and one queued idea since the child started.
     - **If one arm reverses another, is there a third arm with no opinion in it?** `lab run`
       prints a `Mirror pairs:` block when two of a method's arms differ in exactly one
       reversing setting, and says `unpriced` when nothing always-invested can price them. The
       explore skill asks children for that third arm at design time; this is the only place
       anything re-checks. A reversed arm alone proves the *signal* is real and says nothing
       about what *acting* on it costs, because both arms pay that cost equally and it cancels —
       measured 2026-10-21 (insight 523), 22 of 28 recorded pairs can never be priced. The
       repair is an Amendment in the child's own method file, so it costs no method id and no N:
       ask the child for it while its worktree is still open, or write it yourself. `lab
       dressing MNNNN` says what is recoverable and journals nothing. Report it in the
       synthesis either way — a batch that measured its signals and not their price is a finding
       about the batch.

     Whatever is missing, finish it yourself from the scrollback and the data. If the method
     never ran, relaunch it once; if it fails again, `lab drop MNNNN --why "<reason>"` plus a `risk` insight.
   - **dev-eligible:** run the explore skill's **Promotion** yourself, now, in `$REPO`, one at a time.
     Start with its step 0, the fit check, then **step 0b, the durability check** -- `lab regime`,
     `survivorship_coverage.py`, and `lab walkforward`. Four test looks are spent and all four
     failed on `beats SPY TR` -- but they bought **two** distinct books, not four (M0021, M0022
     and M0029 are one book; only M0002 is separate), so the record is 0-for-2 and the budget was
     spent twice on the same thing. Quote both numbers. A good twenty-year average is still not
     evidence, and `lab walkforward`'s buy signal now reports one row per book, not per method id.
     **`lab promote` now refuses, it does not warn.** Since 2026-10-09 it exits 2 unless the method
     beat SPY in a majority of at least four scoreable walk-forward folds **and** no kin reads
     `test-failed` -- kin being its `family` plus every ancestor through `parent_id`. **There is no
     override and no flag.** When it refuses: record it (`lab note`, and a `risk` insight if the
     whole family is now closed), put the reason in the batch report, and move to the next idea.
     You do not ask the owner, you do not pause the batch, and you do not go looking for a way
     round -- the iron rules hold here exactly as everywhere else. `lab status` shows every
     dev-eligible method's fold record and, under "Refused by the hard gate", the reason, so check
     it *before* you plan a promotion.
     Step 0b also carries the buy signal, which you report and never block on. If the eligible
     variant trades whole shares, or is a method from M0030 or earlier measured at the flat 0.1%,
     first run `lab costs` on it and then its fractional, real-fee twin as a one-variant variation
     method. Promote the twin, never the original. The look is spent on the configuration paper
     would trade, or not at all.
   - **Close it out:**
     - Save the scrollback: `tmux capture-pane -p -S - -t <window> > $LOGS/explore-MNNNN.log`.
       tmux keeps a short history, so a log of about one screen is normal; the database is the
       audit record, not the log.
     - Kill the window, but only if it is still named `explore-MNNNN`.
     - `git worktree remove --force $WT`, then `git branch -D explore/MNNNN` (only once its method file is on `origin/main`).
   - `lab stage` + commit + push the database and its snapshot, `lab/lab.sqlite` and `web/data/lab.json` ("lab: M00xx <verdict>").
6. **Refill.** While launched < num-methods, pick the next idea for the free slot from the
   **current** lab, so later ideas learn from earlier results (the children's queued ideas
   included), then reserve and launch. Never let a slot sit idle while ideas remain.
7. **Synthesize** when num-methods children are closed out. **Gate it before you write it.**
   Every figure in a synthesis arrived in a child's `DONE` line or its pane, so all of them are
   someone else's measurement, and the synthesis itself is append-only: it cannot be edited once
   it is in. Read the batch's numbers back from the database yourself: the verdict table,
   each method's eligibility, and above all the buy signal, whose four conditions are claims
   about runs you did not watch finish. The explore skill's **The gate** is the pass;
   `/verify-claims` is the long form. Then add **one batch insight**
   (`lab insight --kind synthesis --title "Sera <stamp>: <theme>" --body …`). The newest
   synthesis is the headline of seertrade.site/sera, the first thing the owner reads, and the owner
   is not a trader: write it in everyday words, name methods by what they do (not `MNNNN` or
   candidate ids), and leave out code, hashes, column names and backticks. Cover:
   - what the batch taught across methods
   - which directions look alive and which look dead
   - what data or features would unlock the most
   - **the buy signal, every batch, even when the answer is no.** State plainly whether any
     method this batch cleared all four of: dev-eligible at the bars in force; no method in its
     family has test-failed; a majority of walk-forward folds beaten (`lab walkforward`); and a
     *positive* edge in the highest-coverage era 2009-2015
     (`engine/scripts/survivorship_coverage.py`). That conjunction is the only moment
     survivorship-free price history is worth buying -- see the explore skill's Promotion step 0b
     for why, and what it costs. If nothing cleared it, say "no buy signal this batch" and why. If
     something did, it is the FIRST line of the report, not a footnote, and it also goes in as a
     `lab insight --kind risk`. Say too whether the hard gate refused anything this batch, and on
     which of the two conditions -- a batch where every promotion was refused is a finding about
     the lab, and the owner should read it in the synthesis rather than infer it from silence.
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
| "`git pull --rebase --autostash` before each lab commit" | Only at preflight, before any child runs. Mid-batch, autostash rewrites `lab/lab.sqlite` on disk under a child's open connection (SQLite then reports "readonly database", and a write in that window is lost). Sync with `git fetch` + `git merge --ff-only origin/main` (it leaves untouched dirty files alone), then `lab stage`, commit, push; if the push is rejected, `git reset --soft HEAD~1 && git reset` and repeat. |
| "It passed dev, that's the gate" | Not since 2026-10-09. Four test looks are spent, all four failed on `beats SPY TR`, and they bought two distinct books, not four -- 0-for-2, and three looks went to one book (insight 529). Run Promotion step 0b before every look, and check the candidate against the books already spent. |
| "The buy signal fired, I'll ask the owner first" | Never ask, never block. Record the insight, put it first in the report, carry on. |
| "`lab promote` refused it, I'll find a way round" | There is no way round. No `--force`, no environment variable, no editing the method to dodge the kin walk. Record the refusal, report it, take the next idea. |
| "Its fold record is 2 of 4 but the twenty-year numbers are great" | That is the gate's entire point, and the 0-for-5 roster is what the twenty-year numbers bought. `lab promote` exits 2. |
| "That older method sits in the Promotable-now list, so promote it" | The list is the gate's letter, not the durability check. Run `lab walkforward` first; a negative 2009-2015 edge means no look. A batch promotes its own children's results, not an earlier batch's leftovers. |
| "Its sibling test-failed, but this variant is genuinely different" | Kin is `family` plus every ancestor through `parent_id`. A disproven family does not get a retry under a new id — that is the mechanism the gate exists to close. |
