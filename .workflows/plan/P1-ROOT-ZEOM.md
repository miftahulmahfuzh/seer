> Adopted from `STRATEGY_C_NEWS_VETO_PLAN.md` phase 7. Source: `.workflows/plan/strategy-c-news-veto/phase-7.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 7: Ship: Veto workflow step, live smoke, docs

**Plan set:** `STRATEGY_C_NEWS_VETO_PLAN.md`
**Analysis:** `20261004-171449-C5V8_code_analyzer.md`
**Spec:** `docs/handover/2026-10-04-strategy-c-news-veto.md`
**Satisfies:** R3 (the `Veto` step between `Nightly` and `Paper`, inside the 45-minute job), R5 (engine readme, paper runbook, ROADMAP P6 with D11's wording)
**Depends on:** Phase 4, 5, 6 (and through them 1, 2, 3)
**Difficulty:** NORMAL
**Package:** repo (`.github/workflows`, `docs/`, `engine/package_readme.md`, `.env.example`)

---

## Goal

After this phase the nightly job runs `veto` between `Nightly` and `Paper` as a step that can never
fail the night, and every document an operator or the owner reads describes Strategy C as it ships:
the night's new step, every veto failure state and what C and the app do in it, the four repo secrets
the owner must set, C's own paper clock, the reset procedure, and P6's new "Done when". The phase-3
clients and the phase-1 prompt/parser are proven once against real Finnhub and z.ai by a local,
read-only smoke whose timings are written into the runbook.

No engine or web source changes in this phase. No Neon access. No GitHub secret is set.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- Workflow step `Veto` in `.github/workflows/nightly.yml` (job `nightly`, between steps `Nightly` and `Paper`; no `id`).
- Runbook section `## Strategy C: the news check` in `docs/runbooks/paper-trading.md` (GitHub anchor `#strategy-c-the-news-check`, linked from ROADMAP P6 and from the runbook itself).
- Readme sections `### veto (P6, Strategy C)`, `### strategies.c (P6, Strategy C)`, `### finnhub (P6)`, `## Migration 004 (...)`, `### Strategy C: the news check (P6)` (Usage) in `engine/package_readme.md`.
- A scratch smoke script `veto_smoke.py` in the implementer's scratchpad directory, **not committed** (the repo has no `engine/scripts/` or `scripts/` convention — checked: neither directory exists).
**Signature changes:** none.
**Requires (from earlier phases):**
- `python -m seer_engine [--dry-run] [-v] veto` exists and exits 0 on every per-candidate failure, 1 only when the session's bars run is not `success` or on a database error, 2 on a missing `DATABASE_URL_UNPOOLED` (Phase 4, K6).
- `seer_engine.finnhub`: `load_key()`, `Client(key, ...)`, `.company_news(symbol, start, end) -> list[Headline]`, `.earnings(symbol, start, end) -> date | None`, `FinnhubError` whose text is already scrubbed of the key (Phase 3, K5).
- `seer_engine.llm.Client.complete(system, prompt, *, temperature=None, thinking=None, max_tokens=None)` (Phase 3, K5).
- `seer_engine.strategies.c`: `STRATEGY_C_PARAMS`, `SYSTEM_PROMPT`, `VERDICTS`, `news_dates`, `earnings_window`, `select_headlines`, `user_prompt`, `parse_verdict`, `FROZEN_MODEL = "glm-5.3"`, `PROMPT_VERSION = "c-veto-v1"`, `STRATEGY_C_ID = "C-news-veto"` (Phase 1, K1).
- Migration `004_news_veto.sql`, roster entry `C` with `gate_applicable=False`, store `NewsVerdict` / `has_vetoes` / `write_vetoes` / `read_vetoes` / `allowed_between`, `news_vetoes` in `demo.DEMO_TABLES` (Phase 2, K2–K4).
- `paper` decides C from stored verdicts; `paper_check` replays C from them; `explain` covers C (Phase 5, K7).
- Positions "Vetoed tonight" sheet with the strings "`n` checked · `k` allowed", the no-rows line "No news check for {date}: A had no candidates, or the check did not run. C buys nothing this session." (`web/lib/vetoes.ts` `noCheckLine`), "News check failed for {date}: C sits this session out." plus the shared reason when every row failed; checklist row "Not applicable"; score lines "Paper only. No backtest gate." / "Real money needs an owner decision" (Phase 6, K8). The runbook quotes these strings exactly.
- **H1 (accepted by reconciliation; Phase 4 carries the code and two tests):** `veto` writes nothing once `paper` has already decided the session (`runs.real_run(conn, S).paper_status == "success"`), checked before any network call and re-checked inside its write transaction; it exits 0 ("too late"). The runbook rows and readme bullets below describe that guard.
**Leaves alone (owned by others):** every file under `engine/src/**`, `engine/tests/**`, `db/**` (phases 1–5), `web/**` (phase 6), the `Check secrets`, `Migrate`, `Nightly`, `Paper`, `Paper check` and `Explain` steps' commands and conditions (unchanged), the other workflows, Neon, GitHub repo secrets, `docs/handover/**`, `docs/backtests/**`, `docs/plans/**`.

## Files

| File | Action | What changes |
|---|---|---|
| `.github/workflows/nightly.yml` | modify (lines 26–28, insert after line 67) | job timeout comment names Veto (value stays 45); new `Veto` step |
| `docs/runbooks/paper-trading.md` | modify (lines 3–5, 7–11, 19–29, 37–45, 63–105, 107–129, 131–144, 171–181, insert after 181, 183–204, 206–223, 274–307, 309–326) | the night with Veto, C in the roster, commands and exit codes, failure states, new "Strategy C: the news check" section with measured timings, health check, owner step 1 for four secrets, release checklist, rollback/reset incl. `news_vetoes` |
| `engine/package_readme.md` | modify (lines 4, 30, 34–124, 375–405, 738, 1304–1313, 1342, 1354–1360, 1394, 1396–1404, 1408–1416, 1418–1435, 1448–1450, 1497–1506, 1598–1607, 1675–1690, 1718–1723) | `veto` command, `strategies.c`, `finnhub`, `llm` keyword options, roster/store additions, migration 004, data flow, usage, performance, gotchas, notes |
| `docs/ROADMAP.md` | modify (lines 88, 91–95, 97–103) | P6 entry rewritten (C on paper, D11 "Done when"); P5 owner-check line; v0.1.0 note on C's clock |
| `.env.example` | modify (line 19) | comment for `FINNHUB_API_KEY` |
| `<scratchpad>/veto_smoke.py` | create, not committed | live read-only smoke (Step 1) |

Line numbers are those of `HEAD` (`d9cecce`): invariant 9 makes phase 7 the only phase touching these
five files, so they are unchanged when phases 1–6 land.

## Implementation Steps

### Step 1: Live smoke against Finnhub and z.ai (local, read-only, not committed)

**File:** `<scratchpad>/veto_smoke.py` — the implementer's session scratchpad directory (outside the
worktree; never `git add`ed).
**Change:** run phases 1 and 3 end to end the way `commands/veto.py` chains them, for 10 liquid
symbols, with no database. Run it **after** phases 1–6 are merged into the worktree branch and the
worktree venv is current (`engine/.venv/bin/pip install -e 'engine[dev]'` if `finnhub.py` is not yet
importable).

Rules: never `source` `.env.local`; never print a secret (every printed line is passed through
`llm.scrub` for both keys); never import `seer_engine.db` or connect to Neon (the script's last line
proves psycopg was not loaded).

**Code:**
```python
"""Phase 7 live smoke: Strategy C's news check against real Finnhub and z.ai, no database.

Exercises finnhub.Client (phase 3), llm.Client's keyword options (phase 3) and strategies.c's
news_dates / earnings_window / select_headlines / user_prompt / parse_verdict (phase 1) for ten
liquid symbols, exactly as commands/veto.py chains them, and prints per-call timings for
docs/runbooks/paper-trading.md. Never imports seer_engine.db, never prints a secret (every
printed line is scrubbed of both keys).

    cd /home/miftah/.worktrees/seer/strategy-c-news-veto
    SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python <scratchpad>/veto_smoke.py
"""

from __future__ import annotations

import statistics
import sys
import time
from datetime import datetime, timezone

from seer_engine import config, dates, finnhub, llm
from seer_engine.strategies import c

SYMBOLS = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "JPM", "BRK.B", "XOM", "UNH")


def _stats(name: str, xs: list[float]) -> str:
    if not xs:
        return f"{name}: no successful calls"
    return (
        f"{name}: n={len(xs)} min={min(xs):.2f}s median={statistics.median(xs):.2f}s "
        f"max={max(xs):.2f}s"
    )


def main() -> int:
    config.load_env()
    key = finnhub.load_key()
    cfg = llm.load_config()
    if key is None or cfg is None:
        print("FINNHUB_API_KEY or LLM_* missing from SEER_ENV_FILE; nothing to smoke", file=sys.stderr)
        return 2
    secrets = (key, cfg.api_key)

    def say(line: str) -> None:
        for secret in secrets:
            line = llm.scrub(line, secret)
        print(line, flush=True)

    params = c.STRATEGY_C_PARAMS
    if cfg.model != params.model:
        say(f"LLM_MODEL {cfg.model} is not C's frozen model {params.model}: veto would mark every verdict failed")
        return 1

    started_at = datetime.now(timezone.utc)
    session = dates.run_dates(started_at).session_date
    news_from, news_to = c.news_dates(started_at, params.news_days)
    win_start, win_end = c.earnings_window(session, params.earnings_sessions)
    fh = finnhub.Client(key)
    client = llm.Client(cfg, timeout=30.0, retries=1)

    say(
        f"started {started_at:%Y-%m-%dT%H:%M:%S}Z  session {session}  news {news_from}..{news_to}  "
        f"earnings window {win_start}..{win_end}  model {cfg.model}  prompt {params.prompt_version}"
    )
    say(f"{'symbol':<7}{'news_s':>7}{'earn_s':>7}{'llm_s':>7}{'items':>6}{'shown':>6}  {'earnings':<10}  {'verdict':<7}  reason")

    t_news: list[float] = []
    t_earn: list[float] = []
    t_llm: list[float] = []
    counts = {v: 0 for v in c.VERDICTS}
    shown_counts: list[int] = []
    with_earnings: list[str] = []
    t_all = time.perf_counter()
    for symbol in SYMBOLS:
        news_s = earn_s = llm_s = float("nan")
        n_items = n_shown = 0
        earnings = None
        try:
            t = time.perf_counter()
            items = fh.company_news(symbol, news_from, news_to)
            news_s = time.perf_counter() - t
            t_news.append(news_s)
            n_items = len(items)
            shown = c.select_headlines(items, started_at, params.max_headlines)
            n_shown = len(shown)

            t = time.perf_counter()
            earnings = fh.earnings(symbol, win_start, win_end)
            earn_s = time.perf_counter() - t
            t_earn.append(earn_s)

            prompt = c.user_prompt(symbol, session, win_end, earnings, started_at, shown, params)
            t = time.perf_counter()
            reply = client.complete(
                c.SYSTEM_PROMPT,
                prompt,
                temperature=float(params.temperature),
                thinking=params.thinking,
                max_tokens=params.max_tokens,
            )
            llm_s = time.perf_counter() - t
            t_llm.append(llm_s)
            verdict, reason = c.parse_verdict(reply)
        except finnhub.FinnhubError as exc:
            verdict, reason = "failed", f"Finnhub: {exc}"[:300]
        except llm.LlmError as exc:
            verdict, reason = "failed", f"LLM: {exc}"[:300]
        counts[verdict] += 1
        shown_counts.append(n_shown)
        if earnings is not None:
            with_earnings.append(f"{symbol} {earnings.isoformat()}")
        say(
            f"{symbol:<7}{news_s:>7.2f}{earn_s:>7.2f}{llm_s:>7.2f}{n_items:>6}{n_shown:>6}  "
            f"{(earnings.isoformat() if earnings else 'none'):<10}  {verdict:<7}  {reason}"
        )
    wall = time.perf_counter() - t_all

    say("")
    say(_stats("finnhub company-news", t_news))
    say(_stats("finnhub calendar/earnings", t_earn))
    say(_stats("llm complete", t_llm))
    say(f"loop wall {wall:.1f}s for {len(SYMBOLS)} symbols")
    say(f"verdicts allow={counts['allow']} veto={counts['veto']} failed={counts['failed']}")
    say(f"headlines shown per symbol min={min(shown_counts)} max={max(shown_counts)}")
    say(f"earnings in window: {', '.join(with_earnings) or 'none'}")
    say(f"psycopg loaded: {'psycopg' in sys.modules}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Run:**
```bash
cd /home/miftah/.worktrees/seer/strategy-c-news-veto
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python <scratchpad>/veto_smoke.py | tee <scratchpad>/veto_smoke.out
```
Expected: exit 0; 10 symbol rows; `failed=0` (a `failed` row is a finding: read its reason, decide
whether it is transient, re-run once, and record both runs); every `news_s` ≥ about 1.0 s after the
first call (the client's spacing); `psycopg loaded: False`. Keep `veto_smoke.out` in the scratchpad
only; its numbers go into the runbook (Step 3, section "Measured") and one readme line (Step 4.13).
If the smoke finds a defect in a phase-1/3 module, do not fix it here: stop and hand it back to that
phase (Handoffs).

**Impact:** none on the tree. Two Finnhub calls per symbol (≤ 20, inside 60/min) and 10 LLM calls.

### Step 2: The `Veto` workflow step

**File:** `.github/workflows/nightly.yml:26` (job comment) and `:68` (new step after `Nightly`, before `Paper`)
**Change:** complete file below. Differences from `HEAD`: the job's timeout comment (lines 26–27) now
names Veto and the measured budget, the value stays `45`; a new `Veto` step. `Check secrets` is
**not** extended: the four new secrets are optional by design (D12) and their absence must never stop
the night. `Paper` keeps its default `if: success()`: a failed `continue-on-error` step leaves
`success()` true, so Paper runs whatever Veto did; a failed Nightly skips Veto and Paper alike.

**Why 45 minutes still holds** (analysis "Measurements"): Nightly ≈ 40 s per missing session (3 Massive
calls at 12.5 s spacing), so even a 10-session catch-up is ≈ 7 min; Veto nominal ≈ 1 min (10 × (2
Finnhub calls ≈ 0.35 s each at ≥ 1 s spacing + one LLM call of 1.6–4 s)), and its worst case is cut
at 10 min by the step limit; Paper's first-night dry run took 6.94 s on Neon; Paper check 1.38 s
before any session; install + checkout ≈ 1 min. Sum of worst plausible values ≈ 20 min, leaving
Explain more than 20 min. The 10-minute step limit is the hard bound: per candidate the worst
non-stopping path is 2 Finnhub calls (15 s timeout, one retry each) plus one LLM call (30 s, one
retry, 2 s backoff) ≈ 2 min, and the 3-consecutive-failure stop only fires on consecutive failures.

**Code:**
```yaml
name: Nightly

on:
  schedule:
    # 23:00 UTC Mon-Fri = 06:00 WIB Tue-Sat = 19:00 EDT / 18:00 EST after each US session.
    - cron: '0 23 * * 1-5'
    # Retry slot, 01:00 UTC Tue-Sat. No-op when the 23:00 run already succeeded.
    - cron: '0 1 * * 2-6'
  workflow_dispatch:
    inputs:
      dry_run:
        description: 'Fetch and compute everything, then roll back (writes nothing)'
        type: boolean
        default: false

permissions:
  contents: read

concurrency:
  group: seer-db-writer
  cancel-in-progress: false

jobs:
  nightly:
    runs-on: ubuntu-latest
    # 45, not 30: nightly makes 3 Massive calls per missing session (bars, splits, dividends) at
    # 12.5 s spacing (about 40 s a session), then Veto (about 1 min, never more than its own
    # 10-minute limit), Paper, Paper check and Explain run in the same job.
    timeout-minutes: 45
    env:
      DATABASE_URL_UNPOOLED: ${{ secrets.DATABASE_URL_UNPOOLED }}
      MASSIVE_API_KEY: ${{ secrets.MASSIVE_API_KEY }}
      DRY_RUN: ${{ inputs.dry_run == true }}
      PYTHONUNBUFFERED: '1'
    steps:
      - name: Check secrets
        run: |
          missing=0
          for name in DATABASE_URL_UNPOOLED MASSIVE_API_KEY; do
            if [ -z "${!name}" ]; then
              echo "::error::Repository secret $name is not set. See docs/runbooks/data-pipeline.md (Owner steps)."
              missing=1
            fi
          done
          exit "$missing"

      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip
          cache-dependency-path: engine/pyproject.toml

      - name: Install engine
        run: python -m pip install -e engine

      - name: Migrate
        run: |
          flags=()
          if [ "$DRY_RUN" = "true" ]; then flags+=(--dry-run); fi
          python -m seer_engine "${flags[@]}" migrate

      - name: Nightly
        run: |
          flags=(-v)
          if [ "$DRY_RUN" = "true" ]; then flags+=(--dry-run); fi
          python -m seer_engine "${flags[@]}" nightly

      # Strategy C's news check (handover D6): A's first 10 candidates for the next session,
      # Finnhub headlines and earnings dates, one LLM verdict each, stored in news_vetoes before
      # Paper reads them. Never fails the night: missing secrets, a Finnhub or LLM outage, an
      # LLM_MODEL other than C's frozen one, a crash or the 10-minute limit only make C sit the
      # session out (a failed or missing verdict is no trade, design §8); the other four
      # strategies never read it. Nominally about 1 minute. A re-run for a session already
      # checked makes no calls. See docs/runbooks/paper-trading.md (Strategy C: the news check).
      - name: Veto
        continue-on-error: true
        timeout-minutes: 10
        env:
          FINNHUB_API_KEY: ${{ secrets.FINNHUB_API_KEY }}
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
          LLM_BASE_URL: ${{ secrets.LLM_BASE_URL }}
          LLM_MODEL: ${{ secrets.LLM_MODEL }}
        run: |
          flags=(-v)
          if [ "$DRY_RUN" = "true" ]; then flags+=(--dry-run); fi
          python -m seer_engine "${flags[@]}" veto

      - name: Paper
        run: |
          flags=(-v)
          if [ "$DRY_RUN" = "true" ]; then flags+=(--dry-run); fi
          python -m seer_engine "${flags[@]}" paper

      # Replay check (D7): the stored paper state must equal a one-shot run_rules / buy_and_hold
      # replay. Read-only. A mismatch turns the run red (GitHub emails); paper state is already
      # committed and the next night still runs. See docs/runbooks/paper-trading.md.
      - name: Paper check
        id: paper_check
        run: |
          flags=(-v)
          if [ "$DRY_RUN" = "true" ]; then flags+=(--dry-run); fi
          python -m seer_engine "${flags[@]}" paper_check

      # Optional LLM explanations (D9). Never fails the night: missing secrets or any LLM error
      # leave the text NULL ("unavailable" in the app). Runs after a red Paper check too, but
      # not after a failed Nightly or Paper.
      - name: Explain
        if: ${{ success() || steps.paper_check.outcome == 'failure' }}
        continue-on-error: true
        env:
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
          LLM_BASE_URL: ${{ secrets.LLM_BASE_URL }}
          LLM_MODEL: ${{ secrets.LLM_MODEL }}
        run: |
          flags=(-v)
          if [ "$DRY_RUN" = "true" ]; then flags+=(--dry-run); fi
          python -m seer_engine "${flags[@]}" explain
```
**Impact:** from the first scheduled run after the merge, `veto` runs every night. An unset secret
expands to an empty string; `config.get` treats empty as unset, so every verdict is `failed` (D12).

### Step 3: `docs/runbooks/paper-trading.md`

Apply the edits in order. Each quotes the current text exactly and gives its full replacement.

#### 3.1 Header links (lines 3–5)

Old:
```markdown
Spec: [handover 2026-10-04](../handover/2026-10-04-paper-trading-ship.md) ·
Plan: `PAPER_TRADING_SHIP_PLAN.md` · Roadmap: [P4](../ROADMAP.md) ·
Bars, splits and FX: [data-pipeline.md](data-pipeline.md)
```
New:
```markdown
Spec: [handover 2026-10-04](../handover/2026-10-04-paper-trading-ship.md) ·
Plan: `PAPER_TRADING_SHIP_PLAN.md` · Roadmap: [P4, P6](../ROADMAP.md) ·
Strategy C: [handover](../handover/2026-10-04-strategy-c-news-veto.md), `STRATEGY_C_NEWS_VETO_PLAN.md` ·
Bars, splits and FX: [data-pipeline.md](data-pipeline.md)
```

#### 3.2 Paper-only bullets (lines 7–11)

Old:
```markdown
- four frozen portfolios trade on paper every night, and the app shows them month by month next
  to SPY.
```
New:
```markdown
- five frozen portfolios trade on paper every night (the four of P4, plus Strategy C since P6),
  and the app shows them month by month next to SPY.
```

#### 3.3 The roster: intro and table (lines 19–29)

Old:
```markdown
Fixed on 2026-10-04, before any paper result (D1). Every entry starts from 20,000,000 IDR,
converted at the latest `fx_rates` rate on or before the first paper night's `data_date`; the rate
is stored in `paper_state.usd_idr`. Every entry starts on the same first paper session
(`strategies.paper_start`).
```
New:
```markdown
Fixed on 2026-10-04, before any paper result (D1). `C` was added by the Strategy C set (P6), also
before any paper result. Every entry starts from 20,000,000 IDR, converted at the latest `fx_rates`
rate on or before its first paper night's `data_date`; the rate is stored in `paper_state.usd_idr`.
The four P4 entries share one first paper session (`strategies.paper_start`). `C` has its own: the
session decided on the first scheduled night after the Strategy C merge (see
[Strategy C: the news check](#strategy-c-the-news-check)).
```

In the table, after the row starting `` | `F1-SPY-SMA200-M` | `` (line 29), add:
```markdown
| `C` | Strategy C: A's first 10 ranked candidates for the session, minus every symbol whose nightly news check did not say `allow` (Finnhub headlines and earnings dates, LLM `glm-5.3`, prompt `c-veto-v1`); 5-day brackets, 4 slots | bracket | `design-v0` | not applicable: an LLM strategy (design §1 item 5); counted as not passed |
```

#### 3.4 Frozen means frozen (lines 37–44)

Old:
```markdown
- the params;
- a sha256 `digest` of the canonical spec text;
```
New:
```markdown
- the params (for `C` also: the candidate cap, the news window and headline cap, the prompt version
  and full prompt text, the LLM call settings and the LLM model `glm-5.3`);
- a sha256 `digest` of the canonical spec text;
```

#### 3.5 The night (lines 63–105): replace the whole block from `## The night` through the paragraph ending `Nothing before \`paper_start\` is paper evidence (D11).`

New:
````markdown
## The night

```
GitHub Actions nightly.yml   cron 23:00 UTC Mon-Fri (06:00 WIB), retry 01:00 UTC; group seer-db-writer
│
├─ Check secrets             DATABASE_URL_UNPOOLED, MASSIVE_API_KEY (FINNHUB_API_KEY and LLM_* are optional)
├─ Migrate                   db/migrations/*.sql not yet applied
├─ Nightly                   one transaction: missing sessions' bars (universe ∪ SPY ∪ symbols held or
│                            pending in paper state), splits (split_adjustments; history rewritten
│                            backwards, dividends too), cash dividends (Massive CD + SC → dividends),
│                            USD/IDR; runs.status = success.   A failure → no bars, no veto, no paper.
├─ Veto                      Strategy C's news check for session_date; never fails the night
│                            (continue-on-error, 10-minute step limit). A's first 10 ranked candidates
│                            → per candidate: Finnhub headlines of the last 3 days published before the
│                            step started, earnings dates in the 5-session window, one LLM verdict
│                            (allow / veto / failed) → news_vetoes, one transaction. A session already
│                            checked: no calls, no writes.
├─ Paper                     only if runs.status = success for run_dates(now).session_date.
│                            One transaction for all five strategies + runs.paper_status:
│                              for every session after paper_state.last_session through data_date:
│                                splits applied on that session (state rescaled once, in its own units)
│                                → settle (A, C: sim.step; F4/F1: sim.step_book; SPY: buy_and_hold rules)
│                                → dividends on the ex-date (F4, F1, SPY) → force-close symbols whose
│                                bars ended → equity snapshot
│                              then decide session_date (A: picks → size_picks → pending orders;
│                              C: A's picks minus every symbol without a stored `allow` → size_picks;
│                              F4/F1: targets on a month's first session → book_targets; SPY: hold)
├─ Paper check               read-only replay: run_rules / buy_and_hold over [paper_start, last
│                            session] on Neon's bars must equal what Paper stored (C from its stored
│                            verdicts; the LLM is never re-asked). Red on mismatch.
└─ Explain                   optional LLM text for new paper entries (C's included); never fails the night
```

The web (Vercel) only reads. Today shows the SPY-champion "no buys" state. Positions and History
show every research strategy's paper orders and positions, labelled **paper**; Positions for `C`
also shows **Vetoed tonight**, the news check behind its pending orders. The Leaderboard has the
metrics, the honest go-live checklist ("Backtest gate passed: no" for every entry, "Not applicable"
for `C`) and the **Month by month** sheet.

Timing follows the NYSE calendar (`dates.run_dates`):
- `data_date` is the last session whose close is at least an hour old;
- `session_date` is the next session, the one tonight's decisions are for;
- decisions for session S read only data dated ≤ `prev_session(S)` and members on that date (no
  look-ahead); C's verdicts for S read only news published before that night's Veto step started.

**First night.** The first scheduled run after the code is on `main` writes:
- each strategy's spec and `paper_start = session_date`;
- `paper_state`;
- a day-0 snapshot at `data_date`;
- the first decisions.

`C`'s first night is the first scheduled run after the Strategy C merge: Migrate applies `004`, Veto
writes C's first verdicts, and Paper starts `C` the same way while the four others step as usual.

Nothing before `paper_start` is paper evidence (D11).
````

#### 3.6 Commands and exit codes (lines 107–129)

In the Commands table, after the row starting `` | `… -m seer_engine -v explain` `` (line 119), add:
```markdown
| `… -m seer_engine --dry-run -v veto` | Strategy C's news check for `run_dates(now).session_date`: real Finnhub and LLM calls, then rolls back | nothing |
| `… -m seer_engine -v veto` | the same, kept. Only the nightly job runs this for real: verdicts written by hand at another hour would be what Paper then trades on | `news_vetoes` |
```

In the Exit codes table, after the row starting `` | `explain` | `` (line 129), add:
```markdown
| `veto` | verdicts written (any mix of `allow`, `veto`, `failed`, all `failed` included); no candidates tonight; the session is already checked; or Paper has already decided the session (too late, nothing written) | no successful bars run for the session (nothing written, no call); or a database error. The workflow step is `continue-on-error`, so neither fails the night | missing setting (`DATABASE_URL_UNPOOLED`) |
```

#### 3.7 Failure states table (lines 131–144)

Old row (line 135):
```markdown
| Bars run failed (Massive or Frankfurter down, coverage < 90%) | `runs.status = failed`; `paper` refuses and writes nothing | red at "Nightly"; Paper, Paper check and Explain are skipped | stale-data screen ("do not trade") | nothing: the 01:00 retry, or `gh workflow run nightly.yml` |
```
New:
```markdown
| Bars run failed (Massive or Frankfurter down, coverage < 90%) | `runs.status = failed`; `paper` refuses and writes nothing | red at "Nightly"; Veto, Paper, Paper check and Explain are skipped | stale-data screen ("do not trade") | nothing: the 01:00 retry, or `gh workflow run nightly.yml` |
```

After the row starting `| Explain failed or \`LLM_*\` not set |` (line 139), add:
```markdown
| Veto failed in any way (secrets missing, Finnhub or LLM down, wrong `LLM_MODEL`, crash, 10-minute limit) | C buys nothing it has no `allow` for; the other four strategies are untouched | green (Veto shows a warning when it failed) | Positions for C: "Vetoed tonight" with the reason, or "No news check for {date}: A had no candidates, or the check did not run. C buys nothing this session." | see [Strategy C: the news check](#strategy-c-the-news-check) |
```

#### 3.8 Replay check (lines 171–181)

Old:
```markdown
- re-runs `run_rules` for A, F4 and F1, or `buy_and_hold` for SPY, over
  `[paper_start, paper_state.last_session]` with the stored `paper_state.usd_idr`;
```
New:
```markdown
- re-runs `run_rules` for A, C, F4 and F1, or `buy_and_hold` for SPY, over
  `[paper_start, paper_state.last_session]` with the stored `paper_state.usd_idr`. C's replay
  uses the verdicts stored in `news_vetoes` (only `allow` is bought; `veto`, `failed` and a missing
  row are not); the LLM is never asked again;
```

#### 3.9 New section, inserted after the Replay check section (after line 181, before `## Health checks`)

The `‹…›` values are filled from Step 1's `veto_smoke.out`; no `‹` may remain (Verification).

````markdown
## Strategy C: the news check

Spec: [handover](../handover/2026-10-04-strategy-c-news-veto.md) (D1–D12). Plan:
`STRATEGY_C_NEWS_VETO_PLAN.md`. C is A with a second opinion: it takes the stocks A would buy for
the next session and buys only those whose recent news the LLM lets through. A backtest of C would
be contaminated (the LLM has read the past's news, design §4), so C is judged only on paper, month
by month next to A.

### What the Veto step does

For `session_date` S, in `commands/veto.py`, after a successful Nightly and before Paper:
1. Nothing to do when `news_vetoes` already holds C's rows for S ("already checked": no Finnhub or
   LLM call), or when Paper has already decided S (too late: nothing written).
2. A's ranked picks for S from Neon's bars through `prev_session(S)` (the same
   `STRATEGY_A` / `STRATEGY_A_PARAMS` call Paper makes), the first 10 only. None: nothing written.
3. Per candidate, in rank order:
   - Finnhub `company-news` over the last 3 days (ET dates), keeping items published **before the
     step started**, newest first, at most 20;
   - Finnhub `calendar/earnings` over S .. the 5th session from S;
   - one LLM call under the frozen prompt `c-veto-v1` (temperature 0, thinking disabled,
     `max_tokens` 1024, 30 s timeout, one retry) → `allow` or `veto` with a one-sentence reason.
4. One transaction writes one row per candidate: rank, symbol, verdict, reason, model, prompt
   version, the headlines shown (id, time, source, headline; never the summaries), the earnings date
   found, and `decided_at` (the step's start, which is the news cutoff).

Paper then gives C A's candidates minus every symbol without a stored `allow`, through the same
`decide_bracket` / `size_picks` as A. Lower ranks refill slots a veto freed, up to rank 10.

### Measured (‹YYYY-MM-DD›, local smoke, 10 liquid symbols, real Finnhub free key and z.ai `glm-5.3`)

| Call | Calls | Min | Median | Max |
|---|---|---|---|---|
| Finnhub `company-news` (includes the client's ≥ 1 s spacing) | ‹n› | ‹…› s | ‹…› s | ‹…› s |
| Finnhub `calendar/earnings` (includes the spacing) | ‹n› | ‹…› s | ‹…› s | ‹…› s |
| LLM verdict (`glm-5.3`, temperature 0, thinking disabled, `max_tokens` 1024) | ‹n› | ‹…› s | ‹…› s | ‹…› s |

- The whole loop over 10 symbols: ‹…› s wall. A night has at most 10 candidates (A's median is 15
  picks, so the cap binds on 61.6 % of nights; about 7.8 checked per night on 2016–2026 bars).
- Verdicts: ‹a› allow, ‹v› veto, ‹f› failed; headlines shown per symbol ‹min›–‹max›; earnings found
  in the window: ‹symbols and dates, or none›.
- Budget: the step's 10-minute limit is the worst case; the nightly job's 45 minutes still holds
  (Nightly ≈ 40 s per missing session, Paper ≈ 7 s, Paper check seconds).
- Smoke script: run from the session scratchpad, never committed, no database connection.

### Failure states and what C and the app do

A failed or missing verdict is **no trade** for that candidate (design §8). Veto never fails the
night, and the other four strategies never read its rows. In every case below, C's open positions
still settle normally; only new buys are affected. "Vetoed tonight" is the sheet under C's paper
orders on Positions: it lists the `veto` and `failed` rows (symbol, verdict, the one-line reason,
headline count) and a line "`n` checked · `k` allowed".

| What happened | `news_vetoes` for S | C for session S | App (Positions, C) | Workflow | Fix |
|---|---|---|---|---|---|
| `FINNHUB_API_KEY` or any `LLM_*` secret not set | one `failed` row per candidate, the reason names the missing setting | buys nothing | every candidate listed `failed`, the shared reason shown once | green | Owner step 1 |
| `LLM_MODEL` is not `glm-5.3` | every row `failed`: "LLM_MODEL <x> is not C's frozen model glm-5.3" | buys nothing | the shared reason | green | set `LLM_MODEL` back to `glm-5.3` (Owner step 1). Another model is a new id (below) |
| Finnhub error, LLM timeout or HTTP error, or an unparsable reply, for one candidate | that row `failed` with the redacted error | skips that candidate; the others can still be bought | that row listed `failed` with its reason | green | none (transient) |
| Three network failures in a row | the rest `failed`: "skipped after 3 consecutive failures" | buys only what was allowed before the stop | those rows listed `failed` | green | none; if it repeats for several nights, check Finnhub and z.ai status and the secrets |
| Veto crashed, hit a database error or its 10-minute limit | none (the write is one transaction at the end) | buys nothing (missing = failed) | "No news check for {date}: A had no candidates, or the check did not run. C buys nothing this session." | green, Veto shows a warning | read the Veto step log. Do not re-run Veto for that session: the 01:00 retry and any manual re-run write nothing once Paper has decided S |
| No successful bars run for S | none (Veto is skipped, or exits 1 without a call) | no paper step at all | stale-data screen | red at "Nightly" | as for a failed bars run |
| A has no candidates tonight | none | decides an empty list, like A | "No news check for {date}: A had no candidates, or the check did not run. C buys nothing this session." (the same line as a check that did not run: `veto` writes no rows on a night with no candidates, so the app cannot tell the two apart and says so; A shows no new orders that night either) | green | none |
| Catch-up night (Paper steps several sessions at once after missed nights) | rows only for the newest session; earlier sessions have none unless their own night's Veto ran | sits the earlier sessions out | unchanged for past sessions | green | none: the runbook's rule, not a bug |
| Re-run (01:00 retry, `gh workflow run`) after a written check | unchanged ("already checked") | unchanged | unchanged | green | none |
| `workflow_dispatch` with `dry_run` | real Finnhub and LLM calls, then rolled back | — | unchanged | green | none |

`paper` never fails because of C's verdicts, and `paper_check` replays C from exactly the rows Paper
used.

### C's clock

- `C`'s `paper_start` is the session decided on the **first scheduled night after the Strategy C
  merge** (Migrate applies `004` that night; no session is back-dated). The four P4 clocks do not
  move.
- **Until the four secrets exist, every verdict is `failed` and C makes no trades**: it holds its
  20,000,000 IDR in cash, and those flat sessions stay in its record (no reset to hide them). Set the
  secrets (Owner step 1) before the first scheduled night after the merge, so C trades from its
  first session.
- `paper_check --require-sessions 5` counts every roster strategy, `C` included. C's clock starts
  after the four P4 clocks, so the v0.1.0 operational check also waits for C's 5th stepped session.
- The 3-month forward clock of design §1 counts from C's own `paper_start`. It unlocks nothing: C has
  no backtest gate (design §1 item 5), and real money for C would need an explicit owner decision
  even if every other checklist row passed (D9).

### Changing the LLM model is a new id

`glm-5.3` is frozen into C's spec (`strategies.c.FROZEN_MODEL`, part of its digest), with the prompt
`c-veto-v1`. One `LLM_MODEL` secret serves both Explain and Veto:
- Set `LLM_MODEL` to anything else and every C verdict is `failed`: C sits out every night, nothing
  else changes, and Explain keeps working with the other model.
- Never edit `FROZEN_MODEL`, the prompt or any other C parameter in code: C's digest changes and
  Paper then fails the **whole night** with `SpecMismatch` (see The roster).
- To try another model or prompt, add a new roster entry with a new id that freezes it (a new
  handover, a new migration row, its own clock), as for any changed strategy. While `LLM_MODEL`
  points at the new model, C sits out.

### Storage

About 163 rows a month (≈ 7.8 candidates a night) × ≈ 3.4 KB (headlines ≈ 3.1 KB) ≈ 0.55 MB a month,
≈ 6.6 MB a year. Negligible on Neon's free 0.5 GB; no retention job.
````

#### 3.10 Health checks (lines 183–204)

Old (lines 197–200):
```python
    for r in conn.execute("SELECT strategy_id, count(*) - 1 AS sessions, min(date), max(date) "
                          "FROM equity_snapshots GROUP BY 1 ORDER BY 1"):
        print(r)
PY
```
New:
```python
    for r in conn.execute("SELECT strategy_id, count(*) - 1 AS sessions, min(date), max(date) "
                          "FROM equity_snapshots GROUP BY 1 ORDER BY 1"):
        print(r)
    # Strategy C's news checks, newest first: checked, allowed, vetoed, failed, decided at.
    for r in conn.execute("SELECT session_date, count(*), count(*) FILTER (WHERE verdict = 'allow'), "
                          "count(*) FILTER (WHERE verdict = 'veto'), count(*) FILTER (WHERE verdict = 'failed'), "
                          "min(decided_at) FROM news_vetoes WHERE strategy_id = 'C' "
                          "GROUP BY 1 ORDER BY 1 DESC LIMIT 10"):
        print(r)
    for r in conn.execute("SELECT session_date, rank, symbol, left(reason, 120) FROM news_vetoes "
                          "WHERE strategy_id = 'C' AND verdict = 'failed' "
                          "ORDER BY session_date DESC, rank LIMIT 10"):
        print(r)
PY
```

Old (lines 203–204):
```markdown
Storage: the paper tables add kilobytes per month. Watch the database size with the query in
[data-pipeline.md](data-pipeline.md#storage-budget). Neon free is 0.5 GB.
```
New:
```markdown
Storage: the paper tables add kilobytes per month, `news_vetoes` about 0.55 MB. Watch the database
size with the query in [data-pipeline.md](data-pipeline.md#storage-budget). Neon free is 0.5 GB.
```

#### 3.11 Owner step 1 (lines 212–223): replace the whole subsection

Old: from `### 1. LLM secrets for the Explain step (optional)` through the closing fence after
`gh secret list --repo miftahulmahfuzh/seer     # LLM_API_KEY, LLM_BASE_URL, LLM_MODEL listed (values never shown)`.

New:
````markdown
### 1. News and LLM secrets for Veto and Explain

Four repository secrets. Without them the night is still correct: Explain leaves "explanation
unavailable", and every Strategy C verdict is `failed`, so **C makes no trades** until they exist.
Set them before the first scheduled night after the Strategy C merge so that C trades from its first
session. `LLM_MODEL` must be `glm-5.3`, the model frozen into C's spec (another value makes every C
verdict `failed`, see [Changing the LLM model is a new id](#changing-the-llm-model-is-a-new-id)).

```bash
cd /home/miftah/seer
for n in FINNHUB_API_KEY LLM_API_KEY LLM_BASE_URL; do
  engine/.venv/bin/python -c "from dotenv import dotenv_values; print(dotenv_values('.env.local')['$n'], end='')" \
    | gh secret set "$n" --repo miftahulmahfuzh/seer
done
printf '%s' 'glm-5.3' | gh secret set LLM_MODEL --repo miftahulmahfuzh/seer
gh secret list --repo miftahulmahfuzh/seer     # FINNHUB_API_KEY, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL listed (values never shown)
```

Check on the next night: the Veto step log shows one verdict per candidate and no "is not set"
reason, and the Health check's `news_vetoes` query shows `allow`/`veto` rows for that session.
````

#### 3.12 Release checklist (lines 274–307)

Old (lines 282–283):
```markdown
   - The Health check shows `sessions ≥ 5` for all four strategies, and `paper_status = success`
     on each of those runs.
```
New:
```markdown
   - The Health check shows `sessions ≥ 5` for all five strategies (`C` counts too: its clock
     started later, so this waits for C's 5th session), and `paper_status = success` on each of
     those runs.
```

Old (lines 288–291):
```markdown
   - Today shows the SPY-champion "no buys" state;
   - Positions and History show A's paper orders labelled paper;
   - the Leaderboard's Month by month shows October as a partial month for all four, with the
     SPY column.
```
New:
```markdown
   - Today shows the SPY-champion "no buys" state;
   - Positions and History show A's and C's paper orders labelled paper, and Positions for C shows
     "Vetoed tonight";
   - the Leaderboard's Month by month shows each strategy's first month as a partial month, with
     the SPY column, and C's checklist reads "Backtest gate: Not applicable".
```

#### 3.13 Rollback (lines 309–326): replace the whole section body

Old: from `## Rollback` through the line `  code to resetting the data.` (line 326).

New:
````markdown
## Rollback

- **Stop paper trading, keep bars:** delete the "Veto", "Paper", "Paper check" and "Explain" steps
  from `nightly.yml`, then commit and push. Paper state stays where it was.
- **Stop only Strategy C's news check:** delete the "Veto" step. C then has no verdicts and buys
  nothing (missing = failed); its clock keeps running. The four other strategies are unaffected.
- **Reset paper state** (this also resets every clock; the next nightly starts over with a new
  `paper_start`), in one transaction through Python, in the day (never between 22:30 and 02:00
  UTC, while a nightly may run):
  ```sql
  TRUNCATE paper_state, book_positions, book_targets, book_fills, book_trades;
  DELETE FROM orders WHERE strategy_id IN ('SPY', 'A', 'F4-MOM12-N20-TREND', 'F1-SPY-SMA200-M', 'C');
  DELETE FROM equity_snapshots WHERE strategy_id IN ('SPY', 'A', 'F4-MOM12-N20-TREND', 'F1-SPY-SMA200-M', 'C');
  UPDATE strategies SET paper_start = NULL, params = '{}'::jsonb;
  UPDATE runs SET paper_status = NULL, paper_error = NULL, paper_finished_at = NULL;
  ```
- **Reset only C's clock** (the four others keep theirs; same timing rule), in one transaction
  through Python:
  ```sql
  DELETE FROM orders WHERE strategy_id = 'C';
  DELETE FROM equity_snapshots WHERE strategy_id = 'C';
  DELETE FROM paper_state WHERE strategy_id = 'C';
  UPDATE strategies SET paper_start = NULL, params = '{}'::jsonb WHERE id = 'C';
  ```
  C is a bracket strategy, so it has no `book_*` rows. The next nightly's Veto checks the new
  session and Paper starts C again with a new `paper_start`.
- **Neither reset deletes `news_vetoes`.** Verdicts are inputs and a record of what the news check
  said: Paper and the replay read only sessions from C's (new) `paper_start` on, so older rows are
  never traded on again, and keeping them keeps the record honest.
- The repo is public and losses are shown on purpose: never reset to hide a result, and never
  delete a vetoed or failed verdict to hide what the news check did.
- **Migration 003 is additive.** The web from before this set ignores its tables.
  `UPDATE strategies SET is_champion = (id = 'A')` restores the old champion flag, but A then
  shows research picks as advice, which the paper-only decision forbids. Prefer reverting the
  code to resetting the data.
- **Migration 004 is additive** (the `C` roster row and `news_vetoes`). Reverting the Strategy C code
  leaves them unread. Remove them only after the C reset above, with
  `DROP TABLE news_vetoes; DELETE FROM strategies WHERE id = 'C';` (no `orders`, `paper_state` or
  `equity_snapshots` row may reference `C`), and delete `004_news_veto.sql` from
  `schema_migrations` only if the file is also removed from `db/migrations/`.
````

(The "Ship check — 2026-10-04" section, lines 328–371, is a dated record and is **not** edited.)

#### 3.14 New dated record at the end of the file

Append after line 371:
````markdown

## Ship check — Strategy C (‹YYYY-MM-DD›)

Run from the worktree `/home/miftah/.worktrees/seer/strategy-c-news-veto` (phases 1–6 landed). Nothing
touched Neon or the GitHub secrets.

**CI commands, locally:**
- `ruff check engine`: ‹result›.
- `npx tsc --noEmit`: ‹result›.
- Engine tests: ‹N› passed in ‹time›, 0 skipped.
- Web tests: ‹files› files, ‹N› passed.
- actionlint: ‹result› for all four workflows.

**Live smoke** (Finnhub + z.ai, no database): see [Measured](#strategy-c-the-news-check) above.

**Remaining owner step:** 1 (the four secrets), before the first scheduled night after the merge.
C's clock starts that night.
````

### Step 4: `engine/package_readme.md`

#### 4.1 Last Updated (line 4)

Old:
```markdown
**Last Updated**: 2026-10-04 (P4 paper-only, phase 13 of `PAPER_TRADING_SHIP_PLAN.md`: migration 003, the `paper/` package, the book split rule, Massive dividends, the `paper`, `paper_check` and `explain` commands, ruff lint in CI)
```
New:
```markdown
**Last Updated**: ‹YYYY-MM-DD› (P6 Strategy C, phase 7 of `STRATEGY_C_NEWS_VETO_PLAN.md`: `strategies.c`, `finnhub`, `llm` call options, roster entry `C`, the `news_vetoes` store, migration 004, the `veto` command, `paper` / `paper_check` deciding and replaying C)
```
(‹YYYY-MM-DD› = the implementation date.)

#### 4.2 Key Responsibilities (after line 30)

Add one bullet after the bullet starting `- Nightly paper trading (P4, paper-only ...`:
```markdown
- Strategy C on paper (P6): a fifth roster entry `C` whose picks are A's first 10 ranked candidates minus every symbol whose nightly news check did not say `allow`. `strategies.c` holds the pure part (the `NewsVeto` strategy, the frozen prompt `c-veto-v1`, the JSON verdict parser); `finnhub.py` reads company news and earnings dates; the `veto` command asks the LLM once per candidate before `paper` and stores every verdict and the headlines it saw in `news_vetoes` (migration 004); `paper` and `paper_check` read only stored verdicts, so the replay never re-asks the LLM. A failed or missing verdict is no trade (design §8). No backtest gate applies (design §1 item 5)
```

#### 4.3 Layout (lines 34–124)

Old (line 55):
```
    llm.py                  optional Anthropic-compatible Messages call for `explain`; never raises past it (P4)
```
New:
```
    llm.py                  Anthropic-compatible Messages call for `explain` (P4) and `veto` (P6, with temperature/thinking/max_tokens per call)
    finnhub.py              Finnhub company news and earnings calendar, rate-limited, key in a header only (P6)
```

Old (line 66):
```
      roster.py             the frozen roster: four entries, canonical spec text, digest, backtest_gate
```
New:
```
      roster.py             the frozen roster: five entries (C since P6), canonical spec text, digest, backtest_gate
```

Old (line 71):
```
      store.py              load/save paper state, windowed market, splits and dividends queries (impure)
```
New:
```
      store.py              load/save paper state, windowed market, splits and dividends queries, news verdicts (impure)
```

After line 79 (`      b.py                  Strategy B (P6a): ...`), add:
```
      c.py                  Strategy C (P6): CParams, STRATEGY_C_PARAMS, the frozen prompt c-veto-v1, candidates(), NewsVeto, parse_verdict()
```

After line 115 (`      explain.py            \`explain\` command (P4)`), add:
```
      veto.py               `veto` command (P6): Strategy C's nightly news check
```

After line 123 (`db/migrations/003_paper.sql   (outside the package; ...`), add:
```
db/migrations/004_news_veto.sql (outside the package; the C roster row and news_vetoes; P6)
```

#### 4.4 New command section after `explain` (insert after line 405, before `## Exported API`)

Also, in the `paper` (P4) section, after the bullet starting `- **Every night**:` (line 385), add:
```markdown
- **Strategy C**: C's strategy object is given the verdicts stored in `news_vetoes` for the sessions being decided (`store.allowed_between`); only `allow` is bought, and a missing verdict counts as `failed`. `paper` makes no network call and never fails because of C's verdicts.
```
And in the `paper_check` (P4) section (line 397), replace:
```markdown
The read-only replay check (D7). See Usage, "Paper: replay check". "Not started" (no `paper_start`) is a pass.
```
with:
```markdown
The read-only replay check (D7). See Usage, "Paper: replay check". C is replayed from its stored verdicts, read in the same read-only transaction; the LLM is never asked again. "Not started" (no `paper_start`) is a pass.
```

New section:
````markdown
### `veto` (P6, Strategy C)

```
usage: seer_engine veto [-h] [--dry-run] [-v] [--now ISO8601]
```

Strategy C's nightly news check (handover D6; `docs/runbooks/paper-trading.md`, "Strategy C: the news check"). The nightly job runs it after `nightly` and before `paper`, as a `continue-on-error` step with a 10-minute limit. It runs outside `paper`'s transaction, so `paper` stays one network-free transaction.

- **Clock**: `started_at = now` (tz-aware UTC; `--now` for tests) is both the news cutoff and every row's `decided_at`. `rd = dates.run_dates(now)`; the session checked is `rd.session_date`.
- **Precondition**: the real `runs` row for that session has `status = success`. Otherwise exit 1, nothing written, no network call.
- **Nothing to do**: C already has rows for the session (`store.has_vetoes`): "already checked", exit 0, no Finnhub or LLM call. `paper` has already decided the session: "too late", exit 0, nothing written.
- **Candidates**: `strategies.c.candidates` on `store.load_market_window(conn, store.market_window_since(rd.data_date))` at `rd.data_date` (A's ranked picks, the first 10), read and rolled back before any network call. None: exit 0, nothing written.
- **Per candidate**, in rank order: `finnhub.Client.company_news(symbol, *news_dates(started_at, 3))` → `select_headlines(..., cutoff=started_at, cap=20)`; `finnhub.Client.earnings(symbol, *earnings_window(session, 5))`; `llm.Client(cfg, timeout=30.0, retries=1).complete(SYSTEM_PROMPT, user_prompt(...), temperature=float(params.temperature), thinking=params.thinking, max_tokens=params.max_tokens)` (0.0, "disabled", 1024, all from C's frozen `CParams`) → `parse_verdict`.
- **A failure is a verdict, never an exception**: `failed`, with a plain reason redacted and cut to 300 characters, when `FINNHUB_API_KEY` is unset, any `LLM_*` is unset, `LLM_MODEL` is not C's frozen model ("LLM_MODEL <x> is not C's frozen model glm-5.3"), Finnhub or the LLM errors, the reply is unparsable, or `MAX_CONSECUTIVE_FAILURES = 3` network failures in a row stopped the rest ("skipped after 3 consecutive failures").
- **One write**: one transaction re-checks `has_vetoes` (another run may have won) and writes every row with `store.write_vetoes`. `--dry-run` makes the real calls, then rolls back. No secret reaches a row or a log line.
- **Exit codes**: 0 = rows written (whatever the verdicts, all `failed` included), nothing to do, or no candidates; 1 = no successful bars run for the session, or a database error; 2 = missing setting (`DATABASE_URL_UNPOOLED`).
````

#### 4.5 New `strategies.c` section (insert after line 737, i.e. after the `strategies.b` bullets ending `with a ridge \`BParams\`.` and before `### backtest (P3)` at line 739)

````markdown
### strategies.c (P6, Strategy C)

Pure like the rest of `strategies/` (the purity tests cover it): no psycopg, requests, clock,
randomness, logging or `fromtimestamp`. The network half lives in `finnhub.py`, `llm.py` and
`commands/veto.py`.

- `PROMPT_VERSION = "c-veto-v1"`, `FROZEN_MODEL = "glm-5.3"`, `STRATEGY_C_ID = "C-news-veto"` (the object id in C's spec; the roster id is `C`). `Verdict = Literal["allow", "veto", "failed"]`, `VERDICTS`.
- `Headline(id, published, source, headline, summary)`: one Finnhub news item as C reads it; `published` is tz-aware UTC.
- `CParams(a=STRATEGY_A_PARAMS, max_candidates=10, news_days=3, max_headlines=20, max_summary_chars=280, earnings_sessions=5, model=FROZEN_MODEL, prompt_version=PROMPT_VERSION, temperature="0", thinking="disabled", max_tokens=1024)`; `as_dict()` gives every key as a plain string: A's params as `a.<key>`, `a_object`, `a_object_id`, the fields above, and the full `system_prompt` and `user_template` texts, so C's digest moves if any of them changes. `STRATEGY_C_PARAMS = CParams()`.
- `SYSTEM_PROMPT`, `USER_TEMPLATE`: the frozen `c-veto-v1` texts (the plan's K1, verbatim). The system prompt lists what is a veto (earnings inside the holding window or in the last 3 days; guidance cut, warning or large miss; accounting problems or fraud; a lawsuit, regulatory action, investigation or recall; M&A, spin-off or tender news; a halt, delisting, bankruptcy or going-concern doubt; a major analyst or credit downgrade; the CEO or CFO leaving) and asks for one JSON object `{"verdict": "allow" | "veto", "reason": "<one sentence>"}`.
- `candidates(history, members, data_date, params)` / `candidates_prepared(prepared, members, data_date, params)`: `STRATEGY_A.picks(...)` / `picks_prepared(...)` with `params.a`, cut to `params.max_candidates`. The one place C's candidates are computed (`veto` and `NewsVeto` both call it).
- `NewsVeto(allowed: Mapping[date, frozenset[str]], id=STRATEGY_C_ID, lookback=STRATEGY_A.lookback)` implements `Strategy`: `picks` keeps the candidates whose symbol is in `allowed[next_session(data_date)]`, in rank order; `prepare` is A's; `picks_prepared` is the same filter on `candidates_prepared`. `with_allowed(allowed)` returns a copy carrying stored verdicts. `STRATEGY_C = NewsVeto(allowed={})` (with no verdicts it never buys).
- `news_dates(started_at, days) -> (from, to)`: ET calendar dates for Finnhub; `to` is `started_at` in New York.
- `earnings_window(session, n) -> (session, the n-th session counting session as 1)`.
- `select_headlines(items, cutoff, cap)`: items published strictly before `cutoff`, newest first (ties: higher id first), at most `cap`.
- `user_prompt(symbol, session, window_end, earnings, cutoff, headlines, params) -> str`: `USER_TEMPLATE` filled; summaries cut to `max_summary_chars` at a word boundary; `No headlines.` when there are none.
- `parse_verdict(text) -> (verdict, reason)`: accepts surrounding whitespace and a fenced JSON block, takes the first `{...}` object; the verdict must be exactly `allow` or `veto` (case-insensitive) and the reason a non-empty string (whitespace collapsed, at most 300 characters). Anything else is `("failed", "unparsable reply: <first 120 chars>")`.
- `allowed_map(rows) -> {session: frozenset of allowed symbols}` from `(session, symbol, verdict)` rows.
````

#### 4.6 `paper.roster` and `paper.store` bullets (lines 1304–1313, 1342)

Old (line 1306):
```markdown
  - `RosterEntry` (frozen dataclass), one paper portfolio: `id, name, sub, icon, is_champion, is_benchmark, sort` (equal to migration 003's rows), `engine: Engine`, `rules: TradeRules | None`, `obj: Strategy | Allocator | None`, `object_name`, `params`, `registry_id: str | None`, `lookback: int`, `gate_note: str`.
  - `ROSTER: tuple[RosterEntry, ...]` (SPY, A, F4, F1), `ROSTER_IDS`, `MAX_LOOKBACK_BARS = max(e.lookback for e in ROSTER)`.
```
New:
```markdown
  - `RosterEntry` (frozen dataclass), one paper portfolio: `id, name, sub, icon, is_champion, is_benchmark, sort` (equal to the rows migrations 003 and 004 insert), `engine: Engine`, `rules: TradeRules | None`, `obj: Strategy | Allocator | None`, `object_name`, `params`, `registry_id: str | None`, `lookback: int`, `gate_note: str`, `gate_applicable: bool = True` (P6; false only for `C`).
  - `ROSTER: tuple[RosterEntry, ...]` (SPY, A, F4, F1, C), `ROSTER_IDS`, `MAX_LOOKBACK_BARS = max(e.lookback for e in ROSTER)`. `C` (P6): `C · News veto`, icon `gavel`, sort 5, engine `bracket`, rules `DESIGN_V0`, `obj = STRATEGY_C`, `params = STRATEGY_C_PARAMS`, gate note "Backtest gate: not applicable (LLM strategy, design §1 item 5)".
```

Old (line 1312):
```markdown
  - `spec_digest(s) -> str`: sha256 (hex) of `spec_text(s)` in UTF-8. The four digests are pinned in `tests/test_paper_roster.py`.
  - `backtest_gate(e) -> dict[str, Any]`: C2 `params.backtest_gate`, `passed` false for every entry, with `e.gate_note`.
```
New:
```markdown
  - `spec_digest(s) -> str`: sha256 (hex) of `spec_text(s)` in UTF-8. The five digests are pinned in `tests/test_paper_roster.py`; the four P4 digests never change.
  - `backtest_gate(e) -> dict[str, Any]`: C2 `params.backtest_gate`, `passed` false for every entry, with `e.gate_note`; for `C` also `"applicable": false` (the web shows "Not applicable" and counts it as not passed). Not part of the spec, so no digest depends on it.
```

After line 1342 (the `- Market:` bullet of `paper.store`), add:
```markdown
  - News verdicts (P6): `NewsVerdict(rank, symbol, verdict, reason, model, prompt_version, headlines, earnings_date, decided_at)`; `has_vetoes(conn, strategy_id, session) -> bool`; `write_vetoes(conn, strategy_id, session, verdicts) -> int` (plain INSERTs after validating ranks 1..n, unique symbols, a known verdict and a tz-aware `decided_at`; a duplicate is a database error, so callers check `has_vetoes` first in the same transaction); `read_vetoes(conn, strategy_id, session)` (by rank); `allowed_between(conn, strategy_id, start, end) -> dict[date, frozenset[str]]` (only `allow`, sessions `start..end` inclusive).
```

#### 4.7 `llm` and new `finnhub` sections (lines 1354–1360)

Old (line 1360):
```markdown
- `Client(cfg, *, transport=None, timeout=20.0, retries=1, backoff=2.0, max_tokens=400, sleep=time.sleep)`; `Client.complete(system, prompt) -> str`. The key goes out as both `x-api-key` and `Authorization: Bearer` (z.ai compatibility). `explain` catches every `LlmError`, so it never raises past it.
```
New:
```markdown
- `Client(cfg, *, transport=None, timeout=20.0, retries=1, backoff=2.0, max_tokens=400, sleep=time.sleep)`; `Client.complete(system, prompt, *, temperature=None, thinking=None, max_tokens=None) -> str`. The key goes out as both `x-api-key` and `Authorization: Bearer` (z.ai compatibility). `explain` calls it with no keywords, and its request body is byte-identical to P4's; `veto` (P6) passes `temperature=0.0`, `thinking="disabled"` (sent as `{"type": "disabled"}`) and `max_tokens=1024`, because `glm-5.3` with a small budget spends it on reasoning and returns no text. `explain` and `veto` catch every `LlmError`, so neither raises past it.

### finnhub (P6)

- `BASE_URL = "https://finnhub.io/api/v1"`, `MIN_INTERVAL = 1.0` (s between calls: the free tier's 60 a minute), `DEFAULT_TIMEOUT_S = 15.0`.
- `FinnhubError(message, status)`: a request failed after its retry. The text never holds the key.
- `load_key() -> str | None`: `config.get("FINNHUB_API_KEY")`.
- `Client(key, *, transport=None, base_url=BASE_URL, min_interval=MIN_INTERVAL, timeout=DEFAULT_TIMEOUT_S, retries=1, backoff=2.0, clock=time.monotonic, sleep=time.sleep)`; the key travels only in the `X-Finnhub-Token` header. One retry on a connection error, a timeout, 429 or 5xx (honouring a longer numeric `Retry-After`, capped at 60 s); anything else raises `FinnhubError`. Calls are spaced from the end of the previous attempt, retries included.
  - `company_news(symbol, start, end) -> list[Headline]` (`GET /company-news`; symbols in the dot form `bars` stores, e.g. `BRK.B`); items with a missing or non-integer `id` or `datetime`, or an empty headline, are dropped. No cutoff here: `veto` applies `select_headlines`.
  - `earnings(symbol, start, end) -> date | None` (`GET /calendar/earnings`): the earliest date in `[start, end]`, else None. For `BRK.B` the free tier returns the `BRK.A` row.
```

#### 4.8 Migration 004 (insert after line 1394, before `## Data Flow`)

```markdown
## Migration 004 (`db/migrations/004_news_veto.sql`, P6)

Additive only.

- Data: the `C` roster row (`C · News veto`, "A's picks, LLM can veto on news", icon `gavel`, sort 5, engine `bracket`, rules `design-v0`, not champion, not benchmark), as an upsert: 003 had deleted the old unreferenced `C` row.
- `news_vetoes(strategy_id → strategies, session_date, rank ≥ 1, symbol, verdict IN ('allow','veto','failed'), reason, model NULL when unset, prompt_version, headlines jsonb [{id, datetime, source, headline}] newest first, earnings_date, decided_at timestamptz)`, PK `(strategy_id, session_date, symbol)`, unique `(strategy_id, session_date, rank)`. One row per candidate checked; `paper` and `paper_check` read it, the LLM is never re-asked. About 0.55 MB a month.
- Demo-owned: `demo.DEMO_TABLES` includes `news_vetoes`. `paper`'s orphaned-rows guard does not count it (verdicts exist before C starts).
- Applied to Neon by the nightly `Migrate` step on the first scheduled run after the merge; that night also starts C's clock.
```

#### 4.9 Data Flow (lines 1396–1404)

After line 1404 (`5. The transaction commits, or rolls back and re-raises. ...`), add:
```markdown

`veto` (P6) is the one write command that calls the network after reading the database: it reads the
candidates in a transaction it rolls back, makes every Finnhub and LLM call with no transaction open,
then writes all its rows in one short transaction. A network failure becomes a `failed` row, never an
exception. The real night is `migrate` → `nightly` → `veto` → `paper` → `paper_check` → `explain`.
```

#### 4.10 Dependencies (lines 1408–1435)

After line 1414 (the `yfinance` bullet), add:
```markdown
- Finnhub REST (P6, no new package: `requests`): `company-news` and `calendar/earnings` on the free tier, 60 calls a minute.
```

After line 1435 (the `research` module-graph bullet), add:
```markdown
- `strategies.c` imports `dates`, `sim` (`Pick`), `strategies.a` (`STRATEGY_A`, `STRATEGY_A_PARAMS`, `AParams`) and `strategies.base`; never `finnhub`, `llm`, `db` or `universe`. `finnhub` imports `config`, `http` (`redact`), `requests` and `strategies.c` (`Headline`). `commands.veto` imports `db`, `dates`, `demo`, `runs`, `finnhub`, `llm`, `commands.nightly` (`_parse_now`), `paper.roster`, `paper.store`, `sim.sizing` (`Pick`) and `strategies.c`.
```

#### 4.11 Reverse Dependencies (lines 1448–1450)

Old (line 1449):
```markdown
- `web/lib/data.ts` reads `paper_state`, `book_positions`, `book_targets`, `book_trades`, `orders`, `equity_snapshots`, `runs.paper_*` and `strategies.params`/`paper_start` (read-only). The web never imports the engine; the schema in migration 003 is the contract.
- `.github/workflows/nightly.yml` runs `migrate` → `nightly` → `paper` → `paper_check` → `explain`; `.github/workflows/engine-ci.yml` runs `ruff check engine` (rules in `pyproject.toml`) before pytest.
```
New:
```markdown
- `web/lib/data.ts` reads `paper_state`, `book_positions`, `book_targets`, `book_trades`, `orders`, `equity_snapshots`, `news_vetoes` (P6, Positions' "Vetoed tonight"), `runs.paper_*` and `strategies.params`/`paper_start` (read-only; `params.backtest_gate.applicable`). The web never imports the engine; the schema in migrations 003 and 004 is the contract.
- `.github/workflows/nightly.yml` runs `migrate` → `nightly` → `veto` (P6, `continue-on-error`, 10 minutes) → `paper` → `paper_check` → `explain`; `.github/workflows/engine-ci.yml` runs `ruff check engine` (rules in `pyproject.toml`) before pytest.
```

#### 4.12 Performance (after line 1505, before `- There is no benchmark coverage for the DB writers.`)

Add:
```markdown
- Veto (P6), measured on ‹YYYY-MM-DD› from WSL2 with a local smoke (10 liquid symbols, no database): Finnhub `company-news` median ‹…› s and `calendar/earnings` median ‹…› s per call including the 1 s spacing, LLM verdict (`glm-5.3`, thinking disabled) median ‹…› s, ‹…› s for all 10. A night is at most 10 candidates, about 1 minute; the workflow step's 10-minute limit bounds the worst case. Details: the runbook's "Strategy C: the news check".
```

#### 4.13 Usage (after line 1607, before `### Backtest: run and read the report`)

Add:
````markdown
### Strategy C: the news check (P6)

```
cd <repo or worktree root>
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine --dry-run -v veto   # real calls, rolled back
```

`veto` needs `FINNHUB_API_KEY` and `LLM_*` (with `LLM_MODEL=glm-5.3`); without them every verdict is
`failed`. Only the nightly job runs it for real. Then `paper` decides C from the stored verdicts and
`paper_check` replays it from the same rows.
````

Also in "Paper: one night (P4)", step 5's A bullet (line 1585) is left as is, and after the A bullet add:
```markdown
   - C: exactly as A, with `e.obj.with_allowed(store.allowed_between(conn, "C", first, last))` as the strategy, so its picks are A's first 10 minus every symbol without a stored `allow`;
```
And line 1598:
Old: ``The real night runs only in `nightly.yml` (Paper → Paper check → Explain).``
New: ``The real night runs only in `nightly.yml` (Veto → Paper → Paper check → Explain).``

#### 4.14 Gotchas (after line 1690)

Add:
```markdown
- **C's verdicts are decided once.** `paper_check` replays C from `news_vetoes` and never re-asks the LLM. Never edit, delete or re-run verdicts for a session Paper already decided: the replay would no longer match what Paper did. `veto` refuses on its own once the session is checked or decided.
- **C's model is part of its spec.** `LLM_MODEL` must be `glm-5.3`; another value makes every C verdict `failed`. Editing `strategies.c.FROZEN_MODEL`, the prompt or any `CParams` field changes C's digest and fails the whole night with `SpecMismatch`. A different model or prompt is a new roster id.
- **No look-ahead in news.** `select_headlines` keeps only items published before the `veto` run started (`decided_at`); the earnings window is the schedule as known then.
```

#### 4.15 Notes (after line 1723)

Append:
```markdown

The P6 Strategy C sections (`strategies.c`, `finnhub`, the `llm` call options, roster entry `C`,
the `news_vetoes` store, migration 004, the `veto` command, and C in `paper`, `paper_check` and the
nightly flow) were added on ‹YYYY-MM-DD›. C runs on paper only: no backtest gate applies to an LLM
strategy (design §1 item 5), and real money for C would need an explicit owner decision. Design,
invariants and decisions: `STRATEGY_C_NEWS_VETO_PLAN.md` and
`docs/handover/2026-10-04-strategy-c-news-veto.md`; operations: `docs/runbooks/paper-trading.md`.
```

Note on `demo` (line 506): phase 2 adds `news_vetoes` to `DEMO_TABLES`. Replace the tuple in the
`DEMO_TABLES = (...)` bullet with the tuple exactly as `engine/src/seer_engine/demo.py` defines it
after phase 2 (read the file; do not guess the position).

### Step 5: `docs/ROADMAP.md`

#### 5.1 P5 owner checks (line 88)

Old:
```markdown
- Owner checks left ([runbook](runbooks/paper-trading.md#owner-steps)): the Google OAuth redirect URI for seertrade.site and a sign-in from the XS Max, Add to Home Screen, and the optional `LLM_*` repo secrets
```
New:
```markdown
- Owner checks left ([runbook](runbooks/paper-trading.md#owner-steps)): the Google OAuth redirect URI for seertrade.site and a sign-in from the XS Max, Add to Home Screen, and the `FINNHUB_API_KEY` and `LLM_*` repo secrets (optional for the night; Strategy C trades only with them)
```

#### 5.2 P6 entry (lines 91–95): replace the whole entry

Old:
```markdown
## P6 — Challengers
- Strategy B (ML ranker), walk-forward backtest, then forward paper
- Strategy C (Finnhub news + LLM veto on A's candidates), forward paper only
- Leaderboard + champion selection + go-live checklist
- **Done when:** A, B, C each have independent paper portfolios on the leaderboard
```
New:
```markdown
## P6 — Challengers · B closed (failed P6a); C code landed ‹YYYY-MM-DD›, on paper from the first scheduled nightly after the merge ([runbook](runbooks/paper-trading.md#strategy-c-the-news-check))
- Strategy B (ML ranker): walk-forward backtest failed P6a (above). Closed record: `STRATEGY_B_FROZEN = None`, no committed model, not on the paper roster (D11)
- Strategy C (Finnhub news + LLM veto on A's candidates), forward paper only: a backtest of an LLM on past news is contaminated (design §4). Spec: [handover](handover/2026-10-04-strategy-c-news-veto.md). Plan: `STRATEGY_C_NEWS_VETO_PLAN.md` (7 phases)
  - Each night the new Veto step takes A's first 10 ranked candidates for the next session, reads up to 20 Finnhub headlines from the last 3 days published before the step started plus the earnings dates in the 5-session window, and asks the LLM for `allow` or `veto` under the frozen prompt `c-veto-v1` and model `glm-5.3`. C buys A's candidates minus everything not allowed, through the same `DESIGN_V0` brackets as A
  - Any failure (missing secret, Finnhub or LLM error, unparsable reply, another `LLM_MODEL`) is a `failed` verdict: no trade (design §8), never a failed night
  - Verdicts and the headlines seen are stored in `news_vetoes` (migration 004); `paper_check` replays C from them and never re-asks the LLM
  - Backtest gate: not applicable (LLM strategy, design §1 item 5); the checklist counts it as not passed, and real money for C would need an explicit owner decision
  - Owner step: the repo secrets `FINNHUB_API_KEY`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` ([runbook](runbooks/paper-trading.md#owner-steps)). Until they exist every verdict is `failed` and C makes no trades
- Leaderboard, go-live checklist and Month by month landed with P4 (SPY is the champion); C appears in every roster view, and Positions shows its "Vetoed tonight" list
- **Done when:** A and C each have an independent paper portfolio; B failed P6a and is closed
```

#### 5.3 v0.1.0 release (lines 97–103)

Old:
```markdown
([release checklist](runbooks/paper-trading.md#release-checklist-v010)). P6 may trail into v0.2.0.
```
New:
```markdown
([release checklist](runbooks/paper-trading.md#release-checklist-v010)). P6 may trail into v0.2.0.
`paper_check --require-sessions 5` counts every roster strategy, so once Strategy C is on the roster
the check also waits for C's 5th paper session.
```

### Step 6: `.env.example`

**File:** `.env.example:19`
Old:
```
FINNHUB_API_KEY=
```
New:
```
# Finnhub company news + earnings dates for the `veto` command (Strategy C). Also a GitHub repo
# secret for the nightly Veto step: docs/runbooks/paper-trading.md, Owner steps.
FINNHUB_API_KEY=
```
**Impact:** none on code (python-dotenv and `web/scripts` ignore comments).

## Verification

**Build / lint:**
```bash
cd /home/miftah/.worktrees/seer/strategy-c-news-veto
docker run --rm -v "$PWD":/repo -w /repo rhysd/actionlint:latest -color      # must exit 0, no findings
engine/.venv/bin/python -c "import yaml,sys; d=yaml.safe_load(open('.github/workflows/nightly.yml')); s=[x.get('name') for x in d['jobs']['nightly']['steps']]; i=s.index('Veto'); assert s[i-1]=='Nightly' and s[i+1]=='Paper', s; v=d['jobs']['nightly']['steps'][i]; assert v['continue-on-error'] is True and v['timeout-minutes']==10 and set(v['env'])=={'FINNHUB_API_KEY','LLM_API_KEY','LLM_BASE_URL','LLM_MODEL'}; assert d['jobs']['nightly']['timeout-minutes']==45; print('nightly.yml ok', s)"
engine/.venv/bin/ruff check engine
```
(If `yaml` is not importable in the venv, run the same one-liner with `python3`; if Docker cannot pull
the image, record "actionlint unavailable" and rely on the YAML assertion, as the earlier ship phases did.)

**Tests (invariant 1, unchanged code must stay green):**
```bash
docker start seer-pg
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q   # 0 skipped
cd web && npx vitest run && npx tsc --noEmit
```

**Scope and secret checks:**
```bash
cd /home/miftah/.worktrees/seer/strategy-c-news-veto
git diff --name-only HEAD   # exactly: .env.example .github/workflows/nightly.yml docs/ROADMAP.md docs/runbooks/paper-trading.md engine/package_readme.md
grep -n '‹' docs/runbooks/paper-trading.md docs/ROADMAP.md engine/package_readme.md   # must print nothing
engine/.venv/bin/python - <<'PY'
import subprocess
from dotenv import dotenv_values
v = dotenv_values('/home/miftah/seer/.env.local')
diff = subprocess.run(['git', 'diff', 'HEAD'], capture_output=True, text=True, check=True).stdout
names = [k for k, val in v.items() if val and len(val) >= 8 and val in diff and k not in ('LLM_MODEL', 'LLM_BASE_URL')]
print('secret values found in the diff:', names or 'none')   # prints names only, never values
PY
```

**Manual check:** read the rendered runbook on GitHub after push (or a Markdown preview): the anchors
`#strategy-c-the-news-check`, `#changing-the-llm-model-is-a-new-id` and `#owner-steps` resolve; the
night diagram's box characters align.

**Exit criteria:**
- `nightly.yml` has `Veto` between `Nightly` and `Paper` with `continue-on-error: true`,
  `timeout-minutes: 10`, the four secrets as step env and the same flags pattern; the job stays 45
  minutes; actionlint clean (or the YAML assertion passes).
- The smoke ran against real Finnhub and z.ai with 10 symbols, `psycopg loaded: False`, and its timings
  are in the runbook's "Measured" table and the readme's Performance line; no `‹` remains.
- Runbook, readme, ROADMAP and `.env.example` updated as in Steps 3–6; CI commands green with 0
  skipped; the diff touches only the five files and holds no secret value.
- No Neon connection, no `gh secret set`, no source change.

## Handoffs

- **H1 → Phase 4, R2 — late verdicts break C's replay (accepted by reconciliation).** The 01:00 UTC
  retry (and any manual `gh workflow run`) runs Veto again. If the 23:00 Veto wrote nothing (crash,
  database error, or the 10-minute step limit), the 23:00 Paper already decided session S for C with no
  verdicts and committed; late verdicts would make `paper_check` replay buys Paper never made, a
  permanent red check. Phase 4 now carries the guard (`paper_status == "success"` → exit 0, no network
  call, nothing written; re-checked inside the write transaction) and two tests. This phase's runbook
  (3.6 exit-code row, 3.9 step 1 and the "Veto crashed" row) and readme (4.4 "Nothing to do" bullet,
  4.14 first gotcha) describe it.
- **Phase 6 (R4) — zero candidates vs a check that did not run (settled by reconciliation).** No marker
  table is added. Phase 6 shows one honest neutral line for every no-rows session ("No news check for
  {date}: A had no candidates, or the check did not run. C buys nothing this session."), and the runbook
  quotes it in the "Veto failed", "Veto crashed" and "A has no candidates" rows.
- **Explain has no step `timeout-minutes`.** Pre-existing; on a month's first session with many new
  F4/F1 targets its worst case (each LLM call 20 s, one retry) is long. Not changed here (the step is
  not part of this phase's scope). Reconciliation: not adopted; Explain keeps its current step as is.
- **Smoke defects.** If Step 1 shows a phase-1 or phase-3 defect (a parser miss on a real reply, a
  Finnhub field drift), it is reported back to that phase, not fixed here.
- **`.env.example` `LLM_MODEL`.** A comment that `LLM_MODEL` must be `glm-5.3` for C would help, but
  the scope names only the `FINNHUB_API_KEY` comment; the runbook's owner step says it instead.

## Rollback

Revert this phase's commit. That removes the `Veto` step (C then has no verdicts and buys nothing;
its clock keeps running if it had started) and restores the docs. Nothing in Neon or GitHub secrets
was changed by this phase, and the scratch smoke was never committed.
