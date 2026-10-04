---
name: explore-and-experiment-new-method
description: Use when asked to explore, research, try or experiment with a new trading strategy or method for Seer — "/explore-and-experiment-new-method", "try another strategy", "find something that beats SPY", "keep searching", a /loop of exploration runs — or when a lab method needs analysis, promotion or a follow-up variation.
---

# Explore and experiment with a new method

**Iron rule: we never stop trying, we never give up.** Each run explores **one idea** end to
end, records every trial in the lab, and leaves at least one next idea queued. A failed method
is still a result. A run that leaves nothing queued is the only real failure.

**Second rule: we never fool ourselves.** Trying thousands of methods guarantees some lucky
winners. The lab counts every trial (N) and deflates each result by it. The test window
(2015-10-19 → today) is spent one counted look at a time. Breaking the letter of these rules
also breaks their spirit.

Design: `docs/plans/2026-10-04-method-lab-design.md`. CLI: `python -m seer_engine lab --help`.
Run everything from `engine/` with `.venv/bin/python -m seer_engine lab ...`.

## One run

1. **Preflight.** `main` clean and pulled; `engine/.venv` exists; `engine/.research/` exists
   (if missing: `python -m seer_engine research_store`, which takes a few minutes). One run at a time.
2. **Read the lab.** Run `lab status`, which shows N, test looks used, families, near misses,
   backlog and blocked ideas. Run `lab show <id>` on anything relevant.
3. **Choose one idea.** Pick whichever is most promising:
   - **variation**: attack the most common failure among the near misses (today: max DD > 15%).
     `source_kind="variation"`, `parent_id` set.
   - **web**: SSRN, arXiv q-fin, Quantpedia, Alpha Architect, quant blogs, GitHub. Use the
     WebSearch/WebFetch tools.
   - **knowledge**: what you already know.
   - **backlog**: an `idea` row from `lab status`. Reuse its id.

   Before committing to it:
   - `lab seen --find <words>`: if the idea was already explored, pick another, or make a real
     variation of it.
   - **Testable?** The store has daily OHLCV (1993–2015-10-16, ~539 stocks plus ETFs, no
     delisted names), cash dividends, and point-in-time S&P 500 / Nasdaq-100 membership. It has
     no fundamentals, intraday bars, options, short interest or sentiment. If the idea needs one
     of those: `lab idea ...` then `lab block <id> --on "<data>"`, and choose another idea. Blocked
     ideas still count as exploring.
   - **Executable?** Gotrade means long only, whole shares, regular session. Leverage, shorting,
     non-default ETFs and fractional shares need owner inputs and can never be eligible. Test
     them only as evidence.
4. **Write the method file** `engine/src/seer_engine/lab/methods/mNNNN_<slug>.py`. The id comes
   from `lab next-id`, or from the backlog row. Copy `method_template.py` from this skill's folder. Rules:
   - 1–6 fixed variants. Write `hypothesis` and `expected_failure` **now**, before any result.
   - New logic is an `Allocator` (see `strategies/allocator.py`; reuse `f_factor`, `f_index`,
     `f_rotation`, `f_swing`, `allocator.VOLTARGET`/`BLEND` where you can). Its `id` must be
     unique (use the method id, e.g. `"M0007"`). Pick `TradeRules` presets from `sim/rules.py`.
   - Pure: no clock, randomness, files, network or printing. Only reads bars dated ≤ `data_date`.
   - Set `seen_keys` (e.g. `("url:https://…", "concept:dual-momentum-sectors")`).
5. **Test, then commit.** Run `.venv/bin/python -m pytest -q tests/test_lab_methods.py` and
   `ruff check`. The contract test catches look-ahead. Then commit **only** the method file and
   push. That commit is the pre-registration.
6. **Run.** `lab run MNNNN`. Stock-universe methods take minutes; leave them running.
7. **Analyze honestly.** Write the analysis to a scratch file and record it with
   `lab note MNNNN --file F --verdict "<one line>"`. Cover:
   - the result vs total-return SPY, and which conditions failed and by how much
   - DSR and N
   - the worst year and when the drawdown happened
   - why: the mechanism, not just the numbers
   - whether the hypothesis held, and whether the expected failure happened
   - a comparison with the parent or near misses
8. **Queue at least one next idea.** `lab idea --name … --family … --source-kind … --hypothesis …`
   (plus `--parent` for a variation). It should come from what this result taught.
9. **Promotion.** Only if `lab run` printed an ELIGIBLE trial (status `dev-eligible`), go to
   **Promotion** below.
10. **Commit + push** `lab/lab.sqlite` together with anything new. Then report to the user in a
    few lines: the idea, the result table vs SPY, the verdict, the next idea, N, and test looks used.

## Promotion (only when dev-eligible)

`lab test` and the test-window store do not exist yet; they get built on the first promotion.
**Stop and tell the user**, then build them under the design §3 rules:
- Pre-register the best eligible variant (by MAR, one per method) in `docs/lab/prereg/MNNNN.md`.
  Commit and push it before any test number exists.
- One look per configuration, enforced by `UNIQUE(config_digest, window)`.
- The gate on the test window is the same five conditions.
- On a pass, stop: a paper roster entry is the owner's decision. Design §1 never moves.

## Never

| Temptation | Rule |
|---|---|
| "One param tweak and it passes" | Tweaks after seeing a result are a **new variation method**: new file, new trials, N grows. Never edit a method that has run (a test pins its sha). |
| "Re-run it, the store changed" | A config runs once per window. Rename tricks fail: digests ignore the id. |
| "Peek at 2016–2026 to sanity-check" | No. The test window is only reached through Promotion. Never edit `DEV_END`. |
| "Delete that embarrassing trial" | Trials are append-only (triggers). Every try is reported. |
| "Max DD 16% is basically 15%" | Design §1 is fixed. Never edit §1/§5, `tuning` thresholds, the paper roster or the P7a registry. |
| "Nothing worked, stop here" | Queue the next idea. Record blocked ideas. Never end a run with an empty backlog. |
| "Run three ideas in one go" | One idea per run. For nonstop work: `/loop /explore-and-experiment-new-method`. |

## Quick reference

```
lab status | lab show M0007 | lab next-id | lab seen --find momentum
lab run M0007                     # committed method file required
lab note M0007 --file /tmp/a.md --verdict "Fails max DD (21%); trend filter too slow in 2008"
lab idea --name "..." --family ... --source-kind variation --parent M0007 --hypothesis "..."
lab block M0012 --on "quarterly fundamentals"   lab drop M0013 --why "duplicate of M0004"
lab export                        # lab/lab.xlsx (gitignored)
```
