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
   - **Executable?** Gotrade means long only and the regular session. Limit orders take
     fractional shares; a take-profit/stop-loss bracket needs whole shares. Leverage, shorting
     and non-default ETFs need owner inputs and are never eligible. Test them only as evidence.
4. **Write** `engine/src/seer_engine/lab/methods/mNNNN_<slug>.py` from `method_template.py`
   (this folder). Solo: the id comes from `lab next-id`, or from the backlog row.
   - 1–6 fixed variants. `hypothesis` and `expected_failure` are written **now**, before any result.
   - New logic is an `Allocator` with `id = "MNNNN"`. Reuse `f_factor`, `f_index`,
     `f_rotation`, `f_swing`, `allocator.VOLTARGET`/`BLEND` where you can.
     `TradeRules` presets live in `sim/rules.py`.
   - **Trade it the way paper would: fractional shares.** A book (many stocks, equal or weighted
     slots) uses `MONTHLY_HOLD_FRAC` or `MONTHLY_RANK_WEEKLY_RESIZE_FRAC`, never the whole-share
     `MONTHLY_HOLD`. Gotrade takes fractional limit orders (owner, 2026-10-07), and the paper roster
     trades every book that way. The lab starts at 20M IDR (about $1,450). Split 20–40 ways, that is
     a $22–70 slot, and at 2016+ share prices most stocks cost more than that. A whole-share book
     then sits in cash, and its test-window look measures the account size, not the method. The
     dev window hides this because its back-adjusted 1990s prices are tiny. M0021 spent a look
     learning this: 18% invested, +3.3% a year vs SPY +13.6%. Whole shares are only for a strategy
     holding a few names, and only when you say why in the hypothesis.
   - **Pay what Gotrade really charges.** From M0031 on, every variant runs at Gotrade's real
     fees: build it on `MONTHLY_HOLD_FRAC_GOTRADE` or `MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE`
     (`sim/rules.py`). They are the fractional presets with `cost_model="gotrade"`: the fee
     schedule fitted to the owner's own order receipts (`sim/costs.py`;
     `python -m seer_engine sean calibrate` checks it against every stored order). `lab run`
     refuses a flat-cost variant. The fees bite hardest on small slots: a $28 order pays $0.13
     (0.47%) where the lab used to assume 0.1%, so a 20–40-way book pays several times what the
     old trials paid to trade. SPY pays the same fees in the same run, so the comparison stays
     fair. Another cadence at real fees is `replace(<book preset>, cost_model="gotrade")`: it
     runs on dev, but `promote` needs a preset of its id, so queue a `feature-wish` insight for
     one if it wins.
   - Pure. Reads only bars dated ≤ `data_date`. Set `seen_keys`.
5. **Test, then commit** only the method file. Run `pytest -q tests/test_lab_methods.py` and
   `ruff check src tests`. If the contract test fails, fix the method; never weaken the test.
   The commit is the pre-registration. Push it to `main`: child: `git fetch origin && git rebase
   origin/main && git push origin HEAD:main`; solo: `git push`.
6. **Run** `lab run MNNNN`. It takes seconds to minutes. Use `run_in_background` and wait for it.
7. **Analyze honestly** in a scratch file, then `lab note MNNNN --file F --verdict "<one line>"`.
   The owner reads the analysis and the verdict on seertrade.site/sera (the method's page),
   and is not a quant. Write plainly: short sentences, everyday words, numbers with their meaning ("lost
   at most 13% from a peak, under the 20% limit"), and a plain gloss on any term you can't avoid
   (CAGR, drawdown, profit factor, DSR). Markdown is fine. Cover:
   - result vs total-return SPY, and which conditions failed and by how much
   - DSR at N, in words: how likely the result is real rather than luck after N tries. Say the N
     and the bar it was judged against — the bar is `DSR >= 0.90`, the owner's risk appetite since
     2026-10-07 (design §7.1), and N is one look per distinct method in the lab, floored at the
     measured participation ratio (`DSR_POLICY = "methods"` since 2026-10-08; it was one look per
     dev trial row before). Both are printed by `lab status`; neither is yours to change. Read
     the N off `lab status` rather than counting trials: a method's variants are one look, so the
     trial-row count is no longer the N.
   - worst year and when the drawdown hit
   - **why**: the mechanism, not just the numbers
   - whether the hypothesis held and whether the expected failure happened
   - comparison with the parent or near misses. A method from M0030 or earlier was measured at
     the flat 0.1%; compare against its numbers from `lab costs <id>` (both fees side by side),
     never against its recorded trial, or the fees decide the comparison instead of the idea
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
  recorded trial**, and moves the method `dev-eligible → promoted`. The file records the gate it
  passed — the five conditions, the DSR threshold in force and the N the multiple-testing policy
  resolved to that day — so the rule is pinned in git before any test number exists. It is written
  once and never rewritten: a re-run with a better-looking variant available is a refusal, not an
  update. It loads no store, runs no backtest and spends no look.
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
0. **Fit check, before anything is promoted.** The candidate's `rules` must be fractional
   (`fractional=True`, a `-frac` preset) whenever it holds more than a handful of names. If the
   best eligible variant is whole-share, do not promote it. Register a new variation method with
   one variant, the same config on the `-frac` twin, run it on dev, and promote that one if it is
   still eligible. A look spent on a configuration that could not buy its own picks is wasted and
   can never be retaken. Read the test trial's `exposure` against the dev trial's afterwards. A
   test exposure far below dev exposure means the look measured cash, and the analysis must say so.
   **And at real fees.** A method from M0030 or earlier ran at the flat 0.1%. Before promoting
   it, run `lab costs MNNNN` (report only: no trial, N unchanged; it journals what the fees did).
   If its best variant stops beating SPY, or breaks a go-live condition at real fees, do not
   promote it. If it still passes, register its real-fee twin as a one-variant variation method
   on the `-gotrade` preset, run it on dev, and promote that one if it is still eligible. Paper
   pays real fees, so the look is spent on the configuration paper would trade, or not at all.
0b. **Durability check, and the one moment buying data is worth it.** A twenty-year average hides
   a regime, and this lab has the scar: four of four test-window looks have failed on
   `beats SPY TR`, and all four roster strategies lost to a deposit-matched SPY over 2018-2026
   (insight 58). Before spending a look, run all three. Every one is report only -- no trial, no
   look, N unchanged:

   - `lab regime MNNNN` -- narrow versus broad markets. Read it knowing it does **not**
     discriminate on its own: almost every recorded method reads "pays in both", M0007-N20-RAW
     included at +6.6% narrow and +7.7% broad, and it went on to lose. Its value is the
     persistence line at the foot, which is what actually separates eras.
   - `engine/.venv/bin/python engine/scripts/survivorship_coverage.py` -- the edge by era of rising
     data coverage. The dev store prices 48% of index members in 1996 and 74% in 2014, and the 522
     it cannot price are disproportionately the companies that died (AABA, AAMRQ...). **A method
     whose edge lives in the low-coverage years and vanishes by 2009-2015 may be reading a hole in
     the data rather than the market.** Three of the four roster strategies were already negative
     in 2009-2015, on dev, years before the test window said so.
   - `lab walkforward MNNNN` -- the fold record, and **the one item on this list that is not
     advice**. Since 2026-10-09 `lab promote` *refuses* (`engine/src/seer_engine/lab/hardgate.py`):
     it exits 2, writes no pre-registration and moves no status, unless **both** hold --
     - **(F) folds.** The method beat the recorded SPY benchmark in a **majority** of its
       scoreable walk-forward folds, **and** it is scoreable on every fold the geometry yields,
       at least 4 of them. Fewer than 4 is refused as thin evidence, not waved through: a strict
       majority of an *odd* fold count is a coin flip at every odd count (n=3 is 0.5000, n=4 is
       0.3125), so "3 or more" would admit evidence weaker than 4 and no stronger than 1.
     - **(K) kin.** **No kin reads `test-failed`** -- kin being the method's `family` *and* its
       transitive ancestors through `parent_id`. A parent that failed out of sample disproves a
       method as surely as a sibling that failed; M0032 is M0007's realistic twin by `parent_id`
       and not by family string.

     **There is no override.** No `--force`, no environment variable, no "promote anyway". If the
     rule proves too strict the answer is an argued commit that changes it, because an override
     path is precisely the mechanism that produced the 0-for-5 roster. Do not look for one, do
     not work around it, and do not treat a refusal as a bug.

     **Read `lab status` before you plan a promotion**, not after the refusal. It prints each
     dev-eligible method's fold record and, under "Refused by the hard gate", the exact reason --
     so you can see a dead end before you spend a cycle walking into it.

     **`lab test` does not re-check (K).** A pre-registration is a promise and is not re-opened:
     if the family fails *after* the promotion but before the look, `lab test` prints a note and
     spends the look anyway. The moment kin matters is before `lab promote`, never after it.

   **THE BUY SIGNAL — say it loudly, do not sit on it.** The moment a method clears all four of:

   > **(a)** dev-eligible at the bars in force, **(b)** no method in its family has test-failed,
   > **(c)** a majority of walk-forward folds beaten, and **(d)** a *positive* edge in the
   > highest-coverage era (2009-2015), so the edge is not an artefact of the missing half

   ...that is the moment survivorship-free price history becomes worth paying for, and not before.
   Until then the lab has enough free evidence to reject a method without it; after then, the next
   two things that happen are a counted look and the owner's real money, and a one-month bulk
   download (roughly $30-150 -- Norgate, Sharadar via Nasdaq Data Link, or EOD Historical Data;
   all subscription, so pull the history and cancel, and read the licence first) costs less than
   being wrong about either.

   When it fires: record a `lab insight --kind risk` titled "Buy signal: MNNNN cleared the
   durability gate", name which of (a)(b)(c)(d) it cleared with the numbers, and put it at the TOP of
   the batch report. **Do not block on it and do not ask** -- the iron rule still holds, you never
   wait for a human -- but the owner must not be able to miss it.

   **The buy signal's (b) and the hard gate's (K) are not the same test, and that is deliberate.**
   The buy signal checks the `family` string only (`lab/walkforward.py`'s `BUY_CONDITIONS`, and
   `lab walkforward`'s own query); the gate also walks `parent_id`. A method can therefore read
   clean in `lab walkforward` and still be refused by `lab promote` — M0030's family is clean while
   its parent M0029 and grandparent M0021 both read `test-failed`. The gate is the stricter of the
   two and it is the one that decides whether a look is spent. The buy signal is a separate,
   owner-decided rule about when to **buy data**, not about when to promote, so it was left as it
   is rather than quietly widened.

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
| "It's eligible on dev, promote it as is" | Not in whole shares. Promote only the fractional configuration paper would trade (Promotion step 0). |
| "My new method looks better at the flat 0.1%" | From M0031 `lab run` refuses it. The owner pays real fees; a method that only wins at the old assumption does not win. |
| "Compare my numbers with that old trial's" | An old trial paid 0.1% a trade. Use `lab costs <old id>` and compare real fees with real fees. |
| "`lab costs` showed it survives, call it eligible" | Never. `lab costs` is a report, not a trial. Only a new variation method on the `-gotrade` preset can be judged at real fees. |
| "Max DD 21% is basically 20%" | The bar is 20% since 2026-10-07 (design §1 item 4, the owner's call) and "basically" is not a comparison. Never edit §1/§5, `tuning` thresholds or the P7a registry — they are the owner's dials, not yours. |
| "The luck bar is still too high; nudge it" | Never. `DSR_MIN` is the owner's risk appetite and `DSR_POLICY` is the owner's call on what counts as an independent look (design §7). Run `lab luck` to see the sensitivity, journal what you found, and leave both alone. |
| "Nothing worked, stop here" | Journal the insight and queue the next idea. |
| "Child: commit lab.sqlite too" | Never, and never `web/data/lab.json` either. A binary file committed by two sessions is a conflict nobody can merge. |
| "Solo: `git add lab/lab.sqlite` is quicker" | Always `lab stage`. It is the only thing that keeps `web/data/lab.json` in sync, and CI fails a lab commit without it. |

## Quick reference

```
lab status | lab show M0007 | lab next-id | lab seen --find momentum
lab run M0007                     # needs a committed method file
lab costs M0007                   # report only: best variant at the flat 0.1% vs Gotrade's real fees; journals it, N unchanged
lab note M0007 --file /tmp/a.md --verdict "..."
lab insight --kind data-wish --title "Quarterly fundamentals" --body "..." --method M0007
lab idea --name "..." --family ... --source-kind variation --parent M0007 --hypothesis "..."
lab block M0012 --on "quarterly fundamentals"   lab drop M0013 --why "duplicate of M0004"
lab stage                         # solo only: writes web/data/lab.json, git-adds it and lab/lab.sqlite
lab export                        # lab/lab.xlsx (gitignored)
lab export-json                   # web/data/lab.json without staging (lab stage already does this)
```
