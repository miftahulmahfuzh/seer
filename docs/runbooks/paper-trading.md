# Runbook — Seer paper trading (P4, paper-only)

Spec: [handover 2026-10-04](../handover/2026-10-04-paper-trading-ship.md) ·
Plan: `PAPER_TRADING_SHIP_PLAN.md` · Roadmap: [P4, P6](../ROADMAP.md) ·
Strategy C: [handover](../handover/2026-10-04-strategy-c-news-veto.md), `STRATEGY_C_NEWS_VETO_PLAN.md` ·
Bars, splits and FX: [data-pipeline.md](data-pipeline.md)

**Paper only.** The owner chose ROADMAP option (b) on 2026-10-04:
- SPY buy-and-hold is the champion;
- Seer recommends no real buys;
- five frozen portfolios trade on paper every night (the four of P4, plus Strategy C since P6),
  and the app shows them month by month next to SPY.

Design §1 is unchanged: no strategy has passed a backtest gate, so nothing here leads to real
money, whatever the paper results show. One month of results is mostly luck. The monthly table is
for watching, not for deciding.

## The roster

Fixed on 2026-10-04, before any paper result (D1). `C` was added by the Strategy C set (P6), also
before any paper result. Every entry starts from 10,000,000 IDR (20,000,000 before 2026-10-07), converted at the latest `fx_rates`
rate on or before its first paper night's `data_date`; the rate is stored in `paper_state.usd_idr`.
The four P4 entries share one first paper session (`strategies.paper_start`). `C` has its own: the
session decided on the first scheduled night after the Strategy C merge (see
[Strategy C: the news check](#strategy-c-the-news-check)).

| Id | What it is | Engine | Rules | Backtest gate |
|---|---|---|---|---|
| `SPY` | Buy and hold SPY, dividends reinvested at the ex-date close (`benchmark.buy_and_hold` rules) | benchmark | — | champion and yardstick; not a strategy |
| `A` | Strategy A, `STRATEGY_A_PARAMS` (frozen in P3); 5-day brackets, 4 slots | bracket | `design-v0` | failed (P3, and the P3b rework) |
| `F4-MOM12-N20-TREND` | Top 20 S&P 500 ∪ NDX members by 12-1 momentum, SPY 200-day filter, monthly | book | `monthly-hold` | not passed: P7a dev window only, max DD 22.2% > 15% |
| `F1-SPY-SMA200-M` | Hold SPY while it closes above its 200-day average, checked monthly; else cash | book | `monthly-hold` | not passed: P7a dev window only, max DD 18.7% > 15%, 11 trades |
| `C` | Strategy C: A's first 10 ranked candidates for the session, minus every symbol whose nightly news check did not say `allow` (Finnhub headlines and earnings dates, LLM `glm-5.3`, prompt `c-veto-v1`); 5-day brackets, 4 slots | bracket | `design-v0` | not applicable: an LLM strategy (design §1 item 5); counted as not passed |

Monthly entries decide only on the first session of a month. A paper start in early October means
F4 and F1 hold cash until the open of Monday 2026-11-02, and their October shows 0%. That is the
same semantics the backtest runner (`run_book`) uses, so it is not a bug.

### Frozen means frozen: a change is a new id

`strategies.params` holds each entry's frozen spec:
- the engine;
- the strategy or allocator object;
- the registry id or `STRATEGY_A_PARAMS`;
- the rules id;
- the params (for `C` also: the candidate cap, the news window and headline cap, the prompt version
  and full prompt text, the LLM call settings and the LLM model `glm-5.3`);
- a sha256 `digest` of the canonical spec text;
- the `backtest_gate` note the app shows.

`paper` fails the night when a started strategy's stored digest differs from the code's
(`paper/roster.py`): `store.SpecMismatch`, everything rolled back, `runs.paper_status = failed`,
exit 1. A `paper_start` with no `paper_state` row is refused the same way until the clock is reset
(see Rollback).

To change anything about a strategy (a parameter, the rules, the universe), add a **new roster
entry with a new id**. Its paper clock starts on its own first night. Never edit an entry that has
a `paper_start`, and never reset a clock by deleting rows. Concretely:
1. Add the entry to `paper/roster.py` with a new id, and pin its digest in
   `tests/test_paper_roster.py`.
2. Add a migration `00N_*.sql` that inserts its display row (`id, name, sub, icon, sort, engine,
   rules_id`, `is_champion = false`), in the style of `003_paper.sql`.
3. Commit, push, merge. The next nightly writes its spec and `paper_start`.

New research ideas belong in a new handover (registry append under P7a's D6). Paper results are
never a reason to change a running entry.

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
│                              → each decided symbol's evidence (strategies/evidence.py) stored with it
│                                (orders / book_targets / book_previews .evidence, migration 009); the idle
│                                symbol gets none; an evidence error logs "<id> <date>: no evidence stored
│                                tonight (…)", stores NULL and never changes a decision or fails the night
├─ Paper check               read-only replay: run_rules / buy_and_hold over [paper_start, last
│                            session] on Neon's bars must equal what Paper stored (C from its stored
│                            verdicts; the LLM is never re-asked). Red on mismatch.
└─ Explain                   one or two plain sentences per new pick, from the evidence Paper stored
                             (C's included); replies are checked, a failing one stays NULL; never fails the night
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

## Commands

Run from the repo root or a worktree. Locally, point `SEER_ENV_FILE` at the main checkout's
`.env.local`. **Never `source` it** (`DATABASE_URL` has an unquoted `&`).

| Command | What it does | Writes |
|---|---|---|
| `SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine -v paper` | tonight's paper step for `run_dates(now)`; a no-op if that session's paper step already succeeded | `strategies.params/paper_start` (first night), `paper_state`, `orders`, `book_positions`, `book_targets`, `book_fills`, `book_trades`, `equity_snapshots`, `runs.paper_*` |
| `… -m seer_engine --dry-run -v paper` | the same, then rolls back (nothing persists) | nothing |
| `… -m seer_engine paper --now 2026-10-06T23:30:00Z` | the paper step as of a given UTC instant (format: `paper --help`) | as `paper` |
| `… -m seer_engine -v paper_check` | the replay check over every started strategy | nothing |
| `… -m seer_engine paper_check --require-sessions 5` | the same, and also requires ≥ 5 stepped sessions per strategy (the release check) | nothing |
| `… -m seer_engine -v explain` | "why this pick" notes for new paper entries that have evidence and no note yet (see [Explain: why this pick](#explain-why-this-pick)) | `orders.explanation`, `book_targets.explanation` |
| `… -m seer_engine --dry-run -v veto` | Strategy C's news check for `run_dates(now).session_date`: real Finnhub and LLM calls, then rolls back | nothing |
| `… -m seer_engine -v veto` | the same, kept. Only the nightly job runs this for real: verdicts written by hand at another hour would be what Paper then trades on | `news_vetoes` |

Global flags go before the command: `--dry-run` (do everything, roll back) and `-v` (debug logs).

### Exit codes

| Command | 0 | 1 | 2 |
|---|---|---|---|
| `paper` | night stepped and decided (`runs.paper_status = success`), or already done for this session (no-op) | no successful bars run for the session (design §8: no paper step, nothing written); or the night failed: everything rolled back, `runs.paper_status = failed`, `paper_error` set (a changed spec digest fails here as `SpecMismatch`) | missing setting (`DATABASE_URL_UNPOOLED`) |
| `paper_check` | every started strategy equals its replay (strategies touched by a split are reported `split-affected`, not failed), or nothing has started yet (`not-started`) | a mismatch: the first differing snapshot, trade or position is logged; or `--require-sessions N` is given and a strategy stepped fewer than N sessions (`not-started` counts as 0) | missing setting (`DATABASE_URL_UNPOOLED`) |
| `explain` | always, including when any `LLM_*` is unset or empty (logged "explanations unavailable", no database connection), an entry has no evidence (skipped), an entry's LLM call fails, or its reply fails the checks (text stays NULL) | only a database error (connection or SQL), which `cli.main` turns into 1; the workflow step is `continue-on-error` | `LLM_*` set but `DATABASE_URL_UNPOOLED` missing |
| `veto` | verdicts written (any mix of `allow`, `veto`, `failed`, all `failed` included); no candidates tonight; the session is already checked; or Paper has already decided the session (too late, nothing written) | no successful bars run for the session (nothing written, no call); or a database error. The workflow step is `continue-on-error`, so neither fails the night | missing setting (`DATABASE_URL_UNPOOLED`) |

## Failure states (design §8) and what the app shows

| What happened | Engine result | Workflow | App | Fix |
|---|---|---|---|---|
| Bars run failed (Massive or Frankfurter down, coverage < 90%) | `runs.status = failed`; `paper` refuses and writes nothing | red at "Nightly"; Veto, Paper, Paper check and Explain are skipped | stale-data screen ("do not trade") | nothing: the 01:00 retry, or `gh workflow run nightly.yml` |
| Paper failed (a bug, a DB error, Neon full) | whole paper transaction rolled back; `runs.paper_status = failed`, `paper_error` | red at "Paper" | paper warning on Positions; data stays at the last good night | read `paper_error` (Health check), fix, then `gh workflow run nightly.yml` (bars are a no-op, paper catches up every missed session) |
| Paper check mismatch | paper state already committed | red at "Paper check"; Explain still runs | no change | run `paper_check -v` locally; the log names the first difference. A mismatch is a same-path bug: open a card, do not edit rows by hand |
| A split on a held or pending symbol | state rescaled once (`apply_split` / `apply_book_split`); `paper_check` reports that strategy `split-affected` from then on | green | positions in post-split shares and prices | none: whole-share rounding across a split makes exact replay equality impossible (see Splits) |
| Explain failed, `LLM_*` not set, or a reply failed the checks | text stays NULL | green (`continue-on-error`) | the stored facts instead of the note, or "explanation unavailable" when there are none | Owner step 1 when `LLM_*` is missing; otherwise nothing (the log line `explanation rejected for …` names the reason) |
| Veto failed in any way (secrets missing, Finnhub or LLM down, wrong `LLM_MODEL`, crash, 10-minute limit) | C buys nothing it has no `allow` for; the other four strategies are untouched | green (Veto shows a warning when it failed) | Positions for C: "Vetoed tonight" with the reason, or "No news check for {date}: A had no candidates, or the check did not run. C buys nothing this session." | see [Strategy C: the news check](#strategy-c-the-news-check) |
| Holiday / weekend | the run finds the session already succeeded: bars no-op, paper no-op | green | unchanged | none |
| Data stale (no successful run for the next session) | — | — | stale-data screen first on Today | as for a failed bars run |
| Spec digest changed in code | `paper` fails the night with `SpecMismatch`: rolled back, `runs.paper_status = failed` | red at "Paper" | paper warning on Positions; data stays at the last good night | revert the change; a changed strategy needs a new id (see The roster) |
| Held symbol has no bar on a session (halted, delisted) | force-closed at its last mark that night, the runners' rule | green | trade with exit reason `forced` | none. If the symbol resumes trading, the replay check will flag it; record it in the ROADMAP |
| Schedules disabled after 60 days without a commit | nothing runs | — | stale | `gh workflow enable nightly.yml --repo miftahulmahfuzh/seer` |

## Splits and dividends

- **Units.** Paper state always stays in the units it was sized in:
  - marks are stored (`orders.mark`, `book_positions.mark`) and never rebuilt from `bars`;
  - `nightly` rewrites `bars` history backwards on a split, so a mark rebuilt from bars would
    already be adjusted and would be rescaled twice.
- **When a split touches state.** Only when `split_adjustments.applied = true` for (symbol,
  session), that is, when the stored history really moved. Then, before that session is settled:
  - bracket orders go through `sim.apply_split`: shares × factor (floored), prices ÷ factor, cash
    in lieu;
  - book positions and pending `book_targets` go through `sim.apply_book_split`: whole shares
    floored with cash in lieu, credited to cash and the position's `income_usd`; stop, take, mark
    and entry price ÷ the exact factor. A position that floors to zero closes as `forced` at the
    old mark.
- **Dividends.**
  - `nightly` stores Massive's cash dividends (types CD + SC, summed per symbol and ex-date) in
    `dividends` for every session it fetches. A split rewrites earlier dividend amounts with the
    bars.
  - On the ex-date, `F4` and `F1` (rules `dividends = true`) are credited for symbols they held
    the night before, and SPY is credited and reinvests at that close (whole shares).
  - `A` gets no dividends, exactly as in its backtest (`DESIGN_V0`).
- **Replay across a split.** A replay over today's adjusted bars sizes positions after the split,
  and the live state was sized before it. Whole-share rounding then differs, so `paper_check`
  reports such a strategy `split-affected` instead of failing it.

## Replay check (`paper_check`)

For every strategy with a `paper_start`, `paper_check`:
- loads Neon's bars from about 550 calendar days before `paper_start`;
- re-runs `run_rules` for A, C, F4 and F1, or `buy_and_hold` for SPY, over
  `[paper_start, paper_state.last_session]` with the stored `paper_state.usd_idr`. C's replay
  uses the verdicts stored in `news_vetoes` (only `allow` is bought; `veto`, `failed` and a missing
  row are not); the LLM is never asked again;
- compares every equity snapshot (day 0 included), every closed trade and every open order or
  position with what `paper` stored.

It is the proof that backtest and live share one code path (design §9, D7). It runs every night
after Paper, and before the release with `--require-sessions 5`.

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

### Measured (2026-10-04, local smoke, 10 liquid symbols, real Finnhub free key and z.ai `glm-5.3`)

| Call | Calls | Min | Median | Max |
|---|---|---|---|---|
| Finnhub `company-news` (the client's ≥ 1 s spacing had already passed during the previous LLM call) | 10 | 0.26 s | 0.29 s | 0.36 s |
| Finnhub `calendar/earnings` (includes the ≥ 1 s spacing after `company-news`) | 10 | 1.26 s | 1.26 s | 1.27 s |
| LLM verdict (`glm-5.3`, temperature 0, thinking disabled, `max_tokens` 1024) | 10 | 1.52 s | 3.05 s | 4.97 s |

- The whole loop over 10 symbols: 45.1 s wall. A night has at most 10 candidates (A's median is 15
  picks, so the cap binds on 61.6 % of nights; about 7.8 checked per night on 2016–2026 bars).
- Verdicts: 8 allow, 2 veto, 0 failed; headlines shown per symbol 13–20; earnings found
  in the window: none (window 2026-10-05..2026-10-09; the reasons for JPM and UNH name their mid-October
  reports from the headlines and place them outside the window). The two vetoes: AAPL (Supreme
  Court oral arguments inside the window) and XOM (a Wells Fargo downgrade on 2026-10-01).
- Symbols: AAPL, MSFT, NVDA, AMZN, GOOGL, META, JPM, BRK.B, XOM, UNH; news 2026-10-01..2026-10-04,
  cutoff 2026-10-04 11:26 UTC, session 2026-10-05.
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

### The paper books start with 10,000,000 IDR (2026-10-07)

Every paper book starts with `paper.capital.PAPER_INITIAL_IDR` = 10,000,000 IDR, the owner's own
Gotrade money, so the "About $X" amounts on Positions are the amounts the owner types into Gotrade
(it was `backtest.runner.INITIAL_IDR`, 20,000,000; the backtests keep that, since their records
are closed and only percentages matter there). The amount is part of every spec (`initial_idr`),
so every digest moved once. At 10,000,000 IDR (about $558) one SPY share no longer fits, so the
SPY benchmark buys fractional shares (Gotrade sells SPY in fractions): `paper.benchmark` and the
replay's `buy_and_hold(..., fractional=True)`; the backtest benchmark keeps whole shares.

Production's paper state was reset the same night, before any session had been stepped (day-0
cash rows and A's and C's first pending orders only), with the "Reset paper state" statements
below plus `TRUNCATE book_previews` and `paper_end = NULL`. The rows were saved first. Every
strategy's clock starts again on the next nightly. `news_vetoes` were kept. M0011's lab promotion
note records the spec digest before the change; the roster's digest for RM-FR is the current one.

### F4 and F1 trade fractional shares, RM replaces FND (migration 010)

The owner verified on 2026-10-07 that Gotrade takes fractional **limit** buys and sells (its
take-profit/stop-loss order needs whole shares, which only A and C use). In whole shares a
10,000,000 IDR book could not hold most of F4's and FND's 20 targets (about $55 each), and F1 could
hold one SPY share of its $1,116. So the same three methods run under `monthly-hold-frac`
(`monthly-hold` with `fractional=True`) as new roster ids `F4-MOM12-N20-TREND-FR`,
`F1-SPY-SMA200-M-FR`, and 010 retires the whole-share three (one session in cash, no trade; their
rows stay). FND is not carried over: the owner replaced it with `RM-FR`, lab M0011's braked residual
momentum (`RAW20-TV14-N21`), the only lab book that passes every owner rule and fails only the luck
test (DSR 0.897 < 0.95), put on paper to test it forward. It was promoted with
`promote --method M0011 --candidate M0011-RAW20-TV14-N21 --id RM-FR --fractional --retire FND
--lab-status-stays` (`--fractional` maps a variant's rules to their fractional preset); 010 writes the
same row for every other database. RM's lookback is 401 bars, so the night now loads 640 calendar
days of bars (`store.MARKET_WINDOW_DAYS`, was 550). F4 and F1 stay the registry candidates: `roster._registered` accepts rules
that differ from the candidate's in the share granularity only. Positions shows each book order's
weight and about how many dollars it buys at the strategy's paper equity. `paper_check
--require-sessions N` no longer counts a retired strategy short.

### Book strategies kick off on day one (migration 008)

A book strategy (F4, F1, FND) ranks on its cadence (monthly-hold: the first session of each month).
A clock that starts between two rank sessions would sit in cash until the next one, so the book
**kicks off**: it ranks once on its first session the night can decide (`paper.book.needs_kickoff`),
and `paper_state.kickoff_session` records that session. `paper_check` replays it with
`run_book(kickoff=...)`; backtests never pass one, so every backtest record is unchanged. The clocks
started on 2026-10-06 (before the rule) kick off on 2026-10-07.

Every night Paper also writes `book_previews`: what each book strategy would pick if it ranked
tonight. Positions shows it as "{F4} would pick now" between rebalances. Display only: nothing
trades on it and the replay never reads it.

### C's clock

- `C`'s `paper_start` is the session decided on the **first scheduled night after the Strategy C
  merge** (Migrate applies `004` that night; no session is back-dated). The four P4 clocks do not
  move.
- **Until the four secrets exist, every verdict is `failed` and C makes no trades**: it holds its
  10,000,000 IDR in cash, and those flat sessions stay in its record (no reset to hide them). Set the
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

## Explain: why this pick

The last step of the night writes the "Why this pick" text for every new paper entry: A's and
C's new pending orders, and new targets of F4, F1 and FND (a symbol the strategy already
holds is a re-weight and is skipped).

**What it reads.** Only the entry's `evidence` (migration 009). Paper writes it at decision time,
from `strategies/evidence.py`. It is a short list of plain facts with their numbers, such as "Its
price rose 48.2% from 12 months ago to 1 month ago." or "It ranked 3rd of 412 stocks checked on that
move, strongest first." The
prompt is the method's plain name ("Momentum", not "F4 · Momentum"), the stock symbol, those facts,
and the task: "in at most 2 short plain sentences, say why this method picked this stock, using only
these facts". There are no order prices, no share counts, no rule text and no "this is a paper trade"
(the site already labels everything **paper**). An entry with no evidence (NULL or an empty
list: written before 009, the idle symbol, or a night whose evidence function raised — Paper's log
then has `<strategy> <date>: no evidence stored tonight (…)`) is skipped and its text stays NULL.

**Why thinking is disabled.** The call is `temperature=0.0, thinking="disabled",
max_tokens=1024`, the same settings Veto uses. Before this, `glm-5.3` thought by default on a
400-token budget. Reasoning used up the budget, so the text stopped mid-sentence ("This is a paper
trade simulated by the Seer") or came back empty (NULL). Temperature 0 keeps the note a
restatement of the facts.

**The checks.** Every reply must pass all of these, or it is discarded (logged as
`explanation rejected for <strategy> <symbol>: <reason>`), and the text stays NULL:
- a complete sentence: it ends with `.`, `!` or `?`, and it has no `…` or `...`;
- at most 2 sentences and at most 320 characters. Nothing is ever cut, and no ellipsis is added;
- every number in the reply also appears in the facts. Before comparing, `$`, `,`, `%` and signs
  are removed and trailing zeros dropped, so `$1,850.00` matches `1850`. The digits of a ticker
  such as `S01` are not numbers. Numbers spelled out in words are not checked;
- no advice or prediction phrase: buy, sell, recommend, should, "will" with a price move (rise,
  fall, go up, ...), going to, expect, guarantee. Matches are whole words, so "buyback" and
  "unexpected" pass. "expect" is allowed only when the facts themselves use it (a past
  earnings result);
- not the same text as a note already accepted for the same strategy that night.

**Failures.** A call that raises (timeout, 5xx, a client bug) leaves that text NULL. After 3
calls in a row raise, no more calls are made that night. A rejected reply is not an outage,
because the LLM answered: it does not count toward the 3, and it resets the count. Explain
always exits 0 unless the database fails.

**Old entries.** Entries written before the evidence pipeline shipped have no evidence. They stay
as they are and are not re-explained. New entries get notes from the next night on.

## Health checks

```bash
cd /home/miftah/seer
engine/.venv/bin/python - <<'PY'
from seer_engine import config, db
config.load_env()
with db.connect() as conn:
    for r in conn.execute("SELECT id, status, paper_status, data_date, session_date, paper_finished_at, "
                          "left(paper_error, 160) FROM runs WHERE NOT is_demo ORDER BY id DESC LIMIT 10"):
        print(r)
    for r in conn.execute("SELECT s.id, s.paper_start, p.last_session, p.pending_session, p.cash_usd, p.equity_usd "
                          "FROM strategies s LEFT JOIN paper_state p ON p.strategy_id = s.id ORDER BY s.sort"):
        print(r)
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

Storage: the paper tables add kilobytes per month, `news_vetoes` about 0.55 MB. Watch the database
size with the query in [data-pipeline.md](data-pipeline.md#storage-budget). Neon free is 0.5 GB.

## Owner steps

These need the owner, so the pipeline session does not do them. Each one is independent. Run them
from the main checkout `/home/miftah/seer` after the feature branch is merged into `main`. No
command echoes a secret, and nothing is `source`d.

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

### 2. Google sign-in on seertrade.site

The app's Google callback is `https://seertrade.site/api/auth/callback/google`.
1. Open <https://console.cloud.google.com/apis/credentials> while signed in as the account that
   owns the OAuth client.
2. Under **OAuth 2.0 Client IDs**, open the client whose Client ID equals `AUTH_GOOGLE_ID` in
   `.env.local`.
3. **Authorized JavaScript origins** → **Add URI** → `https://seertrade.site`.
4. **Authorized redirect URIs** → **Add URI** → `https://seertrade.site/api/auth/callback/google`.
5. **Save**. Google says changes can take a few minutes.
6. On the iPhone, open <https://seertrade.site>, then **Continue with Google** with
   `ALLOWED_EMAIL`. Today must open. Any other Google account must land back on Sign-in, denied.

### 3. Vercel environment variables

Verified present on 2026-10-04 for Production and Preview: `ALLOWED_EMAIL`, `AUTH_GOOGLE_SECRET`, `AUTH_GOOGLE_ID`, `AUTH_SECRET`, `DATABASE_URL`. Only if one is
missing, or after rotating a value, re-add it from `.env.local` without echoing it, then redeploy:

```bash
cd /home/miftah/seer
eval "$(engine/.venv/bin/python -c 'import shlex; from dotenv import dotenv_values; v = dotenv_values(".env.local"); print("\n".join(f"export {k}={shlex.quote(v[k])}" for k in ("VERCEL_TOKEN", "VERCEL_ORG_ID", "VERCEL_PROJECT_ID")))')"
N=DATABASE_URL     # or AUTH_SECRET, AUTH_GOOGLE_ID, AUTH_GOOGLE_SECRET, ALLOWED_EMAIL
vercel env rm "$N" production --yes 2>/dev/null
engine/.venv/bin/python -c "from dotenv import dotenv_values; print(dotenv_values('.env.local')['$N'], end='')" | vercel env add "$N" production
git commit --allow-empty -m "chore: redeploy for env change" && git push origin main   # the Git integration redeploys
```

The web needs the **pooled** `DATABASE_URL` (Neon serverless driver). The engine uses
`DATABASE_URL_UNPOOLED`. Never run plain `vercel ls`: its pagination hint prints the token. Use
`vercel ls --format json`.

### 4. Domain and deploys: nothing to do

seertrade.site is already live and connected to the Vercel project (verified 2026-10-04:
`/` 307 → `/signin`, `/signin` 200, `/manifest.webmanifest` 200, `/api/auth/providers` 200 with callback `https://seertrade.site/api/auth/callback/google`). Production deploys itself from every push to `main` through the Vercel Git
integration, so merging this set ships the web. No DNS step remains for the owner.

Only if the Git integration is ever disconnected, deploy production by hand from a clean tree of
`main`:

```bash
D=$(mktemp -d) && git -C /home/miftah/seer archive origin/main | tar -x -C "$D" && (cd "$D" && vercel deploy --prod --yes)
```

### 5. Install on the iPhone (PWA)

In Safari, open <https://seertrade.site> → **Share** → **Add to Home Screen** → **Add**. The Seer
icon opens full screen.

## Release checklist (v0.1.0)

Do these in order, only after the paper clock has run. Owner rule: the README is written at
release, right before the GitHub release.

1. **≥ 5 consecutive paper sessions** ran unattended.
   - `gh run list --workflow nightly.yml --repo miftahulmahfuzh/seer --limit 10`: the last five
     scheduled runs are green through "Paper" and "Paper check".
   - The Health check shows `sessions ≥ 5` for all five strategies (`C` counts too: its clock
     started later, so this waits for C's 5th session), and `paper_status = success` on each of
     those runs.
2. **Replay check on Neon:**
   `SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine -v paper_check --require-sessions 5`
   must exit 0 (`split-affected` is allowed and must be named in the release notes).
3. **App check** on the XS Max and on desktop, light and dark:
   - Today shows the SPY-champion "no buys" state;
   - Positions and History show A's and C's paper orders labelled paper, and Positions for C shows
     "Vetoed tonight";
   - the Leaderboard's Month by month shows each strategy's first month as a partial month, with
     the SPY column, and C's checklist reads "Backtest gate: Not applicable".
4. **README.md**: write the full README (what Seer is, paper-only, the roster, how to run, links
   to the runbooks). `/update-readme` does not apply; this is the repo README.
5. **ROADMAP**: mark P4 "done <date>: 5 consecutive sessions, replay check passed" and v0.1.0
   "released <date>".
6. **Release:** commit and push, wait for CI to go green, then
   `gh release create v0.1.0 --repo miftahulmahfuzh/seer --target main --title "Seer v0.1.0: paper-only" --notes-file <notes.md>`.
   The notes say:
   - paper only;
   - design §1 unchanged;
   - no strategy has passed a backtest gate;
   - the paper start date;
   - the 5-night replay result;
   - the live URL.

The 3-month forward clock of design §1 counts from `paper_start`. It unlocks nothing by itself:
real money also needs a passed backtest gate, and none has passed.

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

## Ship check — 2026-10-04

Run from the worktree `/home/miftah/.worktrees/seer/paper-trading-ship` (phases 1–12 landed),
against Neon. Nothing below started the paper clock: every paper write was rolled back.

**CI commands, locally:**
- `ruff check engine` (ruff 0.16.10, rules E9 + F minus F401): All checks passed.
- `npx tsc --noEmit`: clean.
- Engine tests: 1972 passed in 244.84s (0:04:04), 0 skipped.
- Web tests: 9 files, 65 passed.
- actionlint: clean for all four workflows.

**Neon before:** 186 MB (bars 177 MB), migrations `001_init.sql, 002_engine.sql`, 0 orders, 0 snapshots; latest real run `success`, data_date 2026-10-02, session_date 2026-10-05.
**migrate:** `--dry-run migrate` → "would apply 003_paper.sql"; `migrate` → "apply 003_paper.sql"; a second `migrate` → "skip 003_paper.sql", "nothing to apply".
**Neon after:**
- 186 MB; `schema_migrations` = `001_init.sql, 002_engine.sql, 003_paper.sql`; the six tables `book_fills, book_positions, book_targets, book_trades, dividends, paper_state` exist;
- roster rows: `('SPY', champion, benchmark, 'benchmark', NULL, NULL)`, `('A', false, false, 'bracket', 'design-v0', NULL)`, `('F4-MOM12-N20-TREND', false, false, 'book', 'monthly-hold', NULL)`, `('F1-SPY-SMA200-M', false, false, 'book', 'monthly-hold', NULL)` (`id, is_champion, is_benchmark, engine, rules_id, paper_start`); B and C deleted.

**paper_check before any session:** four lines `paper_check: <id>  not-started  no paper start`, then `paper_check: ok (0 of 4 roster strategies started)`, exit 0 (1.38 s wall).

**paper, dry run on real data:**
- `now 2026-10-04T03:16:14Z -> data_date 2026-10-02, session_date 2026-10-05` (a Sunday in WIB; the real run for 2026-10-05 was already `success`, so no `--now` was needed);
- `bars window since 2025-03-31; 0 session(s) to step` (a first night only starts), then for each of SPY, A, F4-MOM12-N20-TREND, F1-SPY-SMA200-M: `paper starts 2026-10-05 with 1114.2061 USD (USD/IDR 17950.0000)`, then `dry-run: rolled back; nothing written`, exit 0. The INFO log names each start; the first decisions (A's pending orders; F4/F1 hold cash, since 2026-10-05 is not a month's first session) are written but not logged line by line;
- windowed load 247,310 bars since 2025-03-31 in 1.69 s (`store.load_market_window`, timed separately); inside the command the window plus splits and dividends took about 5 s;
- whole command 6.94 s wall, peak RSS 238 MB;
- afterwards `paper_state` 0 rows, no `paper_start`, 0 snapshots, 0 orders, 0 targets: nothing
  persisted.

**Vercel:**
- env present (Production, Preview): `ALLOWED_EMAIL`, `AUTH_GOOGLE_SECRET`, `AUTH_GOOGLE_ID`, `AUTH_SECRET`, `DATABASE_URL`;
- preview of the worktree tree: <https://seer-h37a5c4ys-seer16.vercel.app> (`vercel inspect`: status ● Ready, target preview; the URL sits behind Vercel Deployment Protection);
- production <https://seertrade.site> (still `main` before the merge): `/` 307 → `/signin`, `/signin` 200, `/manifest.webmanifest` 200, `/api/auth/providers` 200 with callback `https://seertrade.site/api/auth/callback/google`.

After the merge, the Git integration deploys the merged commit to production. Check that the top
production deployment's `githubCommitSha` is the merge commit:

```bash
vercel ls --format json | python3 -c 'import json,sys; d=[x for x in json.load(sys.stdin)["deployments"] if x.get("target")=="production"][0]; print(d["url"], d.get("state"), (d.get("meta") or {}).get("githubCommitSha"))'
```

**Remaining owner steps:** 1 (LLM secrets, optional), 2 (Google redirect URI check, and
sign-in on the phone) and 5 (Add to Home Screen). Step 3 is not needed: all five Vercel env names
are present. DNS is live: no step. The paper clock starts with the first scheduled nightly after the
merge.

## Ship check — Strategy C (2026-10-04)

Run from the worktree `/home/miftah/.worktrees/seer/strategy-c-news-veto` (phases 1–6 landed). Nothing
touched Neon or the GitHub secrets.

**CI commands, locally:**
- `ruff check engine` (ruff 0.16.10): All checks passed.
- `npx tsc --noEmit`: clean.
- Engine tests: 2159 passed in 321.33s (0:05:21), 0 skipped.
- Web tests: 10 files, 83 passed.
- actionlint: clean for all four workflows.

**Live smoke** (Finnhub + z.ai, no database): see [Measured](#strategy-c-the-news-check) above.

**Remaining owner step:** 1 (the four secrets), before the first scheduled night after the merge.
C's clock starts that night.

## FND joined the roster (2026-10, roster-promotion-pipeline phase 6)

`FND` — point-in-time SEC fundamental factors, `strategies.f_fundamental.FUNDAMENTAL` with
`rank="composite", top=20` under `monthly-hold` — is the sixth paper portfolio, written through
`promote --method M0005 --candidate M0005-ALL --id FND --lab-status-stays` (the command is below).
It is `status='active'` with no `paper_start`, so the next nightly run starts its clock the
ordinary way.

```bash
GATE_NOTE="M0005 dev window only (1996-01-03..2015-10-16, fundamental coverage 0.3151); failed beats SPY TR (+1.8% vs +351.4%), >= 100 trades (15) and DSR >= 0.95 (0.006)"

# 1. See what it would write, in both databases. Writes nothing.
"$SEER_PY" -m seer_engine --dry-run promote \
  --method M0005 --candidate M0005-ALL --id FND \
  --name "FND · Fundamentals" --sub "Top 20 by SEC filing factors, monthly" \
  --icon book-open --sort 6 --lab-status-stays --gate-note "$GATE_NOTE"

# 2. Write it. No --retire: FND JOINS the roster, it does not replace a horseman.
"$SEER_PY" -m seer_engine promote \
  --method M0005 --candidate M0005-ALL --id FND \
  --name "FND · Fundamentals" --sub "Top 20 by SEC filing factors, monthly" \
  --icon book-open --sort 6 --lab-status-stays --gate-note "$GATE_NOTE"

# 3. Confirm: active, no paper clock yet, resolvable, and no claim of a gate pass.
psql "$DATABASE_URL_UNPOOLED" -c \
  "SELECT id, status, sort, engine, rules_id, object_name, registry_id, gate_applicable, paper_start, promoted_from FROM strategies WHERE id='FND'"

# 4. Commit the lab's record of it (promote appended an analysis section and an insight).
"$SEER_PY" -m seer_engine lab stage
```

`--candidate M0005-ALL` is required: M0005 has six variants (VAL, ROE, GP, SUE, ALL, ALL-R) and
they are different algorithms, so `promote` refuses to guess. `M0005-ALL` is the one whose
`params` is `FundamentalParams(rank="composite", top=20)` — `roster.FUNDAMENTAL_PARAMS`, and
**not** the best-performing variant: choosing on the dev-window numbers would be choosing on the
multiple-testing noise the lab's `trials` table exists to count.

`db/migrations/007_fnd.sql` writes the same row for any database brought up from migrations (CI's
throwaway schema, a fresh local train database, a rebuilt Neon). The two must agree; phase 1's
migration-equality test and phase 5's row-rebuild test fail in opposite directions if they drift.

**It has not passed a backtest gate and does not claim to.** Its `gate_note` names the six M0005
dev-window trials recorded in `lab/lab.sqlite`, all six of which failed, and the dev window's
0.3151 fundamental coverage. That is the same standing A, F4 and F1 are on. Paper membership has
never required a gate pass; the gates bind the real-money decision, and the go-live checklist
(`CHECKS = 6`, per strategy) still reads `Paper only. Backtest gate not passed` for FND.

**`promoted_from` is `'M0005'`, and `M0005` is still `rejected` in the lab.** Those two facts sit
together on purpose. The column names the method the allocator and parameters came from; it
asserts no lab transition. `M0005` cannot move: `lab/lab.sqlite`'s `transitions` table has no edge
out of `rejected`. What the lab *does* carry is the promotion itself — `promote` appends a
`# Promotion` section to `methods.analysis` and one `insights` row, both permitted at any status
by the append-only triggers, and `--lab-status-stays` is the flag that says "record it, do not
move it". So the promotion is findable from either end, and nothing claims a gate the method did
not pass.

**The night reaches the panel through `MarketAware`.** `FUNDAMENTAL` is the one roster object that
reads more of the `Market` than its bars, so `paper.book.decide_book` prepares it from the whole
`Market` (`prepare_for` → `targets_prepared`) and `paper.replay.expected_book` passes the same
`prepared` to `run_rules`. Every other allocator takes the identical history-only expression it
always did. If the two halves ever diverge, `paper_check` reports FND `mismatch` on its first
decision session.

**If FND holds only cash, check the panel before checking the strategy.** `io.load_panel` returns
`EMPTY_FUNDAMENTALS` when `fundamental_facts` is missing or empty — which is production's
deliberate state (see the data-pipeline runbook's "Train/eval on a local database"). With no panel
no symbol is eligible and FND targets nothing. That is the documented contract, not a fault:

    SELECT count(*), max(filed) FROM fundamental_facts;

Zero rows there is the whole explanation. `engine/tests/test_paper_fnd.py` asserts this outcome so
it can never be mistaken for a deliberate cash position.
