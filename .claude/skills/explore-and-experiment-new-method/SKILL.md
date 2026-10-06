---
name: explore-and-experiment-new-method
description: Use when asked to explore, research, try or experiment with a new trading strategy or method for Seer — "/explore-and-experiment-new-method", "try another strategy", "find something that beats SPY", "keep searching", a /loop of exploration runs, a sera-the-explorer child session handed `--method MNNNN` — or when a lab method needs analysis, promotion or a follow-up variation.
---

# Explore and experiment with a new method

Three iron rules. Breaking the letter of a rule breaks its spirit too.

1. **We never stop trying, we never give up.** Each run explores **one idea** end to end,
   records every trial, writes what it learned, and leaves at least one next idea queued. A
   failed method is a result. A run that queues nothing is the only real failure.
2. **No human in the loop.** Decide everything yourself and assume where you have to. Never use
   `AskUserQuestion`, never end a turn on a question, never wait for approval: not for the idea,
   the variants, a failing check, a promotion or a paper-roster entry. Write down what you
   assumed, in the analysis or the commit message. The only allowed stop is a terminal one, such
   as missing tooling that cannot be built or a permission you don't have. Report it and end;
   never hold a prompt open.
3. **We never fool ourselves.** The lab counts every trial (N) and deflates each result by it.
   The test window (2015-10-19 → today) is spent one counted look at a time. Design §1 never moves.

Design: `docs/plans/2026-10-04-method-lab-design.md`. CLI: `python -m seer_engine lab --help`.

## Two modes

| | Solo (`/explore-and-experiment-new-method`) | Child (`… --method MNNNN --coordinator NAME`) |
|---|---|---|
| started by | the user or `/loop` | `/sera-the-explorer`, in its own worktree and tmux window |
| idea | you choose it | already reserved as an `idea` row `MNNNN`; refine it, keep its id |
| python | `engine/.venv/bin/python` | `PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python` (a worktree has no venv) |
| database | `lab/lab.sqlite` in this checkout | the shared one: `export SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research` |
| commits | method file, then `lab stage` (`lab/lab.sqlite` + `web/data/lab.json`), to `main` | method file only; **never commit `lab/lab.sqlite` or `web/data/lab.json`** (the coordinator does) |
| promotion | do it yourself (below) | `lab` marks it `dev-eligible`; report it, and the coordinator promotes |
| end | short report to the user | report to the coordinator (below), then stop |

Run every command from the checkout root (`engine/` for pytest). In child mode, `export` both
variables first in every shell.

`tests/test_lab_snapshot.py` checks that `web/data/lab.json` is the export of `lab/lab.sqlite`.
After any lab write (`run`, `note`, `insight`, `idea`, …) it fails until `lab stage` regenerates
the JSON, by design. So solo: run the full engine `pytest` only **after** `lab stage`. The
contract test in step 5 (`tests/test_lab_methods.py`) is unaffected. A child never stages: its
own checkout's database is untouched (it writes the shared one through `SEER_LAB_DB`), so the
check stays green there, and `lab stage` writes the JSON into the checkout that owns the database.

## One run

1. **Preflight.** Solo: if `main` has unrelated uncommitted changes, don't touch them; commit
   only your own paths. Pull. If `engine/.research/` is missing, build it
   (`python -m seer_engine research_store`, a few minutes).
2. **Read the lab.** `lab status` shows N, test looks, families, the trials closest to eligible,
   backlog, blocked ideas and the latest insights. Use `lab show <id>` for detail.
3. **Choose one idea** (child: it was chosen; start from the reserved row's name and hypothesis).
   Solo: pick the most promising of:
   - **variation**: attack the most common failure among the closest-to-eligible trials.
     `source_kind="variation"`, `parent_id` set.
   - **web**: SSRN, arXiv q-fin, Quantpedia, Alpha Architect, quant blogs, GitHub
     (WebSearch/WebFetch).
   - **knowledge**: what you already know.
   - **backlog**: an `idea` row. Reuse its id.

   Then check:
   - `lab seen --find <words>`. If it was already explored, pick another idea or make a real variation.
   - **Testable?** The store has daily OHLCV for 1993 → 2015-10-16 (~539 stocks plus ETFs,
     no delisted names), cash dividends, and point-in-time S&P 500 / Nasdaq-100 membership. No
     fundamentals, intraday, options, short interest or sentiment. If it isn't testable:
     `lab block <id> --on "<data>"` plus a `data-wish` insight. Solo: choose another idea.
     Child: report `blocked`.
   - **Executable?** Gotrade means long only, whole shares, regular session. Leverage, shorting
     and non-default ETFs need owner inputs and are never eligible. Test them only as evidence.
4. **Write** `engine/src/seer_engine/lab/methods/mNNNN_<slug>.py` from `method_template.py`
   (this folder). Solo: the id comes from `lab next-id`, or from the backlog row.
   - 1–6 fixed variants. `hypothesis` and `expected_failure` are written **now**, before any result.
   - New logic is an `Allocator` with `id = "MNNNN"`. Reuse `f_factor`, `f_index`,
     `f_rotation`, `f_swing`, `allocator.VOLTARGET`/`BLEND` where you can.
     `TradeRules` presets live in `sim/rules.py`.
   - Pure. Reads only bars dated ≤ `data_date`. Set `seen_keys`.
5. **Test, then commit** only the method file. Run `pytest -q tests/test_lab_methods.py` and
   `ruff check src tests`. If the contract test fails, fix the method; never weaken the test.
   The commit is the pre-registration. Push it to `main`: child: `git fetch origin && git rebase
   origin/main && git push origin HEAD:main`; solo: `git push`.
6. **Run** `lab run MNNNN`. It takes seconds to minutes. Use `run_in_background` and wait for it.
7. **Analyze honestly** in a scratch file, then `lab note MNNNN --file F --verdict "<one line>"`.
   The owner reads the analysis and the verdict on seertrade.site/sera (the method's page),
   and is not a quant. Write plainly: short sentences, everyday words, numbers with their meaning ("lost
   at most 13% from a peak, under the 15% limit"), and a plain gloss on any term you can't avoid
   (CAGR, drawdown, profit factor, DSR). Markdown is fine. Cover:
   - result vs total-return SPY, and which conditions failed and by how much
   - DSR at N, in words: how likely the result is real rather than luck after N tries
   - worst year and when the drawdown hit
   - **why**: the mechanism, not just the numbers
   - whether the hypothesis held and whether the expected failure happened
   - comparison with the parent or near misses
   - end with a paragraph that starts **`My opinion:`**. Say plainly whether this direction is
     worth more trials, what you would try next, and why. Commit to a view; no hedging.
   The verdict is one plain line the site shows next to the method's name.
8. **Journal at least one insight**: `lab insight --kind observation|hypothesis|data-wish|feature-wish|risk
   --title … --body … --method MNNNN`. Useful kinds: what this taught about markets, data you
   wish the lab had, a feature that would make the search better, a risk you noticed. The owner
   reads these on seertrade.site/sera (Journal and Ideas) as food for thought, and is not a trader.
   Write for a curious non-trader: a title that says the point, and a body that says what happened,
   why it matters and what to do about it, in everyday words.
   - Name methods by what they do ("the earnings-quality picker"), not by `MNNNN` or candidate ids.
   - No code, file paths, column names, `status='…'`, hashes or digests, and no backticks at all.
   - Spell out jargon or say it plainly: "worst fall" over "max DD", "gains vs losses" over "PF".
   - A number earns its place only with its meaning: "lost 13% at its worst, where SPY lost 55%".
   Ids, digests and mechanics belong in the method's analysis (step 7), which is the audit record.
   (`synthesis` is Sera's batch summary; a single run never uses it.)
9. **Queue at least one next idea**: `lab idea --name … --family … --source-kind … --hypothesis …`
   (plus `--parent`), drawn from what this result taught.
10. **Promotion** if `lab run` printed an ELIGIBLE trial: solo, see **Promotion** below; child, report it.
11. **Finish.**
    - Solo: run `lab stage`. It takes the database's write lock, regenerates `web/data/lab.json`
      (the snapshot seertrade.site/sera is built from) and `git add`s both files. Never
      `git add lab/lab.sqlite` by hand. Commit both files and push; Vercel redeploys the site from
      that push. Then give a short report: idea, result vs SPY, verdict, insight, next idea, N, test looks.
    - Child: make sure your method file is on `origin/main`. Then
      `SendMessage` to the coordinator (re-read `ListAgents` first):
      `DONE MNNNN <rejected|dev-eligible|blocked> — <verdict>; next: M00xx`. If the coordinator
      is gone, the database already holds everything, so just stop. Never commit `lab/lab.sqlite`
      or `web/data/lab.json`.

## Promotion (dev-eligible): autonomous, one counted look

Nobody approves this; you do it. Both commands exist — do not build them:

- **`lab promote <method>`:** picks the method's best eligible **dev** trial by MAR (one variant
  per method), writes `docs/lab/prereg/MNNNN.md` with the `config_digest` **copied from that
  recorded trial**, and moves the method `dev-eligible → promoted`. It is written once and never
  rewritten: a re-run with a better-looking variant available is a refusal, not an update. It
  loads no store, runs no backtest and spends no look.
- **`lab test <candidate>`:** takes the *variant* id (`M0007-RESID`), not the method id. It
  refuses a method that is not `promoted`, refuses a pre-registration that is missing,
  uncommitted, modified or names another configuration, refuses a configuration with no dev
  trial, and the database refuses a second look at any configuration
  (`UNIQUE(config_digest, window)` plus append-only triggers). `--dry-run` prints what would run
  and spends nothing. One `test` trial is recorded; **the lab's N does not move** (a look is not
  a search), and the method ends at `test-passed` or `test-failed`, both final.
- **The test-window store** lives at `engine/.research-test/` (gitignored), sessions 2015-10-19 →
  the latest session, built by `python -m seer_engine research_store --test-window`. It holds the
  same deep history as the dev store from 1993 — the window bounds what is *scored*, the store
  carries the lookback run-up — plus every session after `DEV_END`. Build it once, the first time
  something is promoted. `lab test` refuses a dev store pointed at it, and `lab run` refuses this
  one, so the two can never be swapped by accident.

Then:
1. `python -m seer_engine lab promote MNNNN`. Read what it printed, then **commit and push
   `docs/lab/prereg/MNNNN.md` before any test number exists** (design §3) — the command prints the
   exact `git add` / `git commit` lines. `lab test` refuses while the file is uncommitted, so this
   is not optional and not a formality.
2. `python -m seer_engine lab test MNNNN-X --dry-run` to read back what it will do, then the same
   command without `--dry-run`. That is the one look; there is never another.
3. Write the analysis and verdict (`lab note`).
4. **Pass:** `lab test` prints the exact `python -m seer_engine promote …` command, every argument
   filled in from the two recorded trials. **Run it** — you do not ask anyone (design §6). A new
   allocator is refused until it has two committed entries: a name in `RESOLVER`
   (`paper/roster.py`) and an evidence function under that name in `EVIDENCE`
   (`strategies/evidence.py`) — 2–6 plain-English facts per pick, the numbers its formula used,
   which become the site's "Why this pick". Add both, commit, then run it. It
   writes the roster row with no `paper_start`, so the next paper night freezes the spec and
   starts its own clock. Then `lab stage`, commit, push, verify. **Real money stays out of
   scope:** design §1 needs ≥ 3 months and ≥ 100 closed paper trades of forward paper first.
5. **Fail:** `test-failed` is final. There is no second look at that configuration, on any
   window. Queue a variation (`lab idea --source-kind variation --parent MNNNN …`) if the
   evidence supports one, and journal what the test window said that the dev window did not.

## Never

| Temptation | Rule |
|---|---|
| "I should check with the owner first" | You don't. Decide, write the assumption down, continue. |
| "One param tweak and it passes" | A tweak after a result is a **new variation method** with new trials. Never edit a method that has run (a test pins its sha). |
| "Re-run it, the store changed" | A configuration runs once per window. Renaming doesn't help: digests ignore the id. |
| "Peek at 2016–2026" | Only through Promotion. Never edit `DEV_END`. |
| "Delete that embarrassing trial" | Trials and insights are append-only (triggers). |
| "Max DD 16% is basically 15%" | Design §1 is fixed. Never edit §1/§5, `tuning` thresholds or the P7a registry. |
| "Nothing worked, stop here" | Journal the insight and queue the next idea. |
| "Child: commit lab.sqlite too" | Never, and never `web/data/lab.json` either. A binary file committed by two sessions is a conflict nobody can merge. |
| "Solo: `git add lab/lab.sqlite` is quicker" | Always `lab stage`. It is the only thing that keeps `web/data/lab.json` in sync, and CI fails a lab commit without it. |

## Quick reference

```
lab status | lab show M0007 | lab next-id | lab seen --find momentum
lab run M0007                     # needs a committed method file
lab note M0007 --file /tmp/a.md --verdict "..."
lab insight --kind data-wish --title "Quarterly fundamentals" --body "..." --method M0007
lab idea --name "..." --family ... --source-kind variation --parent M0007 --hypothesis "..."
lab block M0012 --on "quarterly fundamentals"   lab drop M0013 --why "duplicate of M0004"
lab stage                         # solo only: writes web/data/lab.json, git-adds it and lab/lab.sqlite
lab export                        # lab/lab.xlsx (gitignored)
lab export-json                   # web/data/lab.json without staging (lab stage already does this)
```
