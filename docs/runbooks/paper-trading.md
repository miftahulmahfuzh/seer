# Runbook — Seer paper trading (P4, paper-only)

Spec: [handover 2026-10-04](../handover/2026-10-04-paper-trading-ship.md) ·
Plan: `PAPER_TRADING_SHIP_PLAN.md` · Roadmap: [P4](../ROADMAP.md) ·
Bars, splits and FX: [data-pipeline.md](data-pipeline.md)

**Paper only.** The owner chose ROADMAP option (b) on 2026-10-04:
- SPY buy-and-hold is the champion;
- Seer recommends no real buys;
- four frozen portfolios trade on paper every night, and the app shows them month by month next
  to SPY.

Design §1 is unchanged: no strategy has passed a backtest gate, so nothing here leads to real
money, whatever the paper results show. One month of results is mostly luck. The monthly table is
for watching, not for deciding.

## The roster

Fixed on 2026-10-04, before any paper result (D1). Every entry starts from 20,000,000 IDR,
converted at the latest `fx_rates` rate on or before the first paper night's `data_date`; the rate
is stored in `paper_state.usd_idr`. Every entry starts on the same first paper session
(`strategies.paper_start`).

| Id | What it is | Engine | Rules | Backtest gate |
|---|---|---|---|---|
| `SPY` | Buy and hold SPY, dividends reinvested at the ex-date close (`benchmark.buy_and_hold` rules) | benchmark | — | champion and yardstick; not a strategy |
| `A` | Strategy A, `STRATEGY_A_PARAMS` (frozen in P3); 5-day brackets, 4 slots | bracket | `design-v0` | failed (P3, and the P3b rework) |
| `F4-MOM12-N20-TREND` | Top 20 S&P 500 ∪ NDX members by 12-1 momentum, SPY 200-day filter, monthly | book | `monthly-hold` | not passed: P7a dev window only, max DD 22.2% > 15% |
| `F1-SPY-SMA200-M` | Hold SPY while it closes above its 200-day average, checked monthly; else cash | book | `monthly-hold` | not passed: P7a dev window only, max DD 18.7% > 15%, 11 trades |

Monthly entries decide only on the first session of a month. A paper start in early October means
F4 and F1 hold cash until the open of Monday 2026-11-02, and their October shows 0%. That is the
same semantics the backtest runner (`run_book`) uses, so it is not a bug.

### Frozen means frozen: a change is a new id

`strategies.params` holds each entry's frozen spec:
- the engine;
- the strategy or allocator object;
- the registry id or `STRATEGY_A_PARAMS`;
- the rules id;
- the params;
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
├─ Check secrets             DATABASE_URL_UNPOOLED, MASSIVE_API_KEY (LLM_* are optional)
├─ Migrate                   db/migrations/*.sql not yet applied
├─ Nightly                   one transaction: missing sessions' bars (universe ∪ SPY ∪ symbols held or
│                            pending in paper state), splits (split_adjustments; history rewritten
│                            backwards, dividends too), cash dividends (Massive CD + SC → dividends),
│                            USD/IDR; runs.status = success.   A failure → no bars, no paper.
├─ Paper                     only if runs.status = success for run_dates(now).session_date.
│                            One transaction for all four strategies + runs.paper_status:
│                              for every session after paper_state.last_session through data_date:
│                                splits applied on that session (state rescaled once, in its own units)
│                                → settle (A: sim.step; F4/F1: sim.step_book; SPY: buy_and_hold rules)
│                                → dividends on the ex-date (F4, F1, SPY) → force-close symbols whose
│                                bars ended → equity snapshot
│                              then decide session_date (A: picks → size_picks → pending orders;
│                              F4/F1: targets on a month's first session → book_targets; SPY: hold)
├─ Paper check               read-only replay: run_rules / buy_and_hold over [paper_start, last
│                            session] on Neon's bars must equal what Paper stored. Red on mismatch.
└─ Explain                   optional LLM text for new paper entries; never fails the night
```

The web (Vercel) only reads. Today shows the SPY-champion "no buys" state. Positions and History
show every research strategy's paper orders and positions, labelled **paper**. The Leaderboard has
the metrics, the honest go-live checklist ("Backtest gate passed: no" for every entry) and the
**Month by month** sheet.

Timing follows the NYSE calendar (`dates.run_dates`):
- `data_date` is the last session whose close is at least an hour old;
- `session_date` is the next session, the one tonight's decisions are for;
- decisions for session S read only data dated ≤ `prev_session(S)` and members on that date (no
  look-ahead).

**First night.** The first scheduled run after the code is on `main` writes:
- each strategy's spec and `paper_start = session_date`;
- `paper_state`;
- a day-0 snapshot at `data_date`;
- the first decisions.

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
| `… -m seer_engine -v explain` | LLM explanations for new paper entries that have none yet | `orders.explanation`, `book_targets.explanation` |

Global flags go before the command: `--dry-run` (do everything, roll back) and `-v` (debug logs).

### Exit codes

| Command | 0 | 1 | 2 |
|---|---|---|---|
| `paper` | night stepped and decided (`runs.paper_status = success`), or already done for this session (no-op) | no successful bars run for the session (design §8: no paper step, nothing written); or the night failed: everything rolled back, `runs.paper_status = failed`, `paper_error` set (a changed spec digest fails here as `SpecMismatch`) | missing setting (`DATABASE_URL_UNPOOLED`) |
| `paper_check` | every started strategy equals its replay (strategies touched by a split are reported `split-affected`, not failed), or nothing has started yet (`not-started`) | a mismatch: the first differing snapshot, trade or position is logged; or `--require-sessions N` is given and a strategy stepped fewer than N sessions (`not-started` counts as 0) | missing setting (`DATABASE_URL_UNPOOLED`) |
| `explain` | always, including when any `LLM_*` is unset or empty (logged "explanations unavailable", no database connection) or an entry's LLM call fails (text stays NULL) | only a database error (connection or SQL), which `cli.main` turns into 1; the workflow step is `continue-on-error` | `LLM_*` set but `DATABASE_URL_UNPOOLED` missing |

## Failure states (design §8) and what the app shows

| What happened | Engine result | Workflow | App | Fix |
|---|---|---|---|---|
| Bars run failed (Massive or Frankfurter down, coverage < 90%) | `runs.status = failed`; `paper` refuses and writes nothing | red at "Nightly"; Paper, Paper check and Explain are skipped | stale-data screen ("do not trade") | nothing: the 01:00 retry, or `gh workflow run nightly.yml` |
| Paper failed (a bug, a DB error, Neon full) | whole paper transaction rolled back; `runs.paper_status = failed`, `paper_error` | red at "Paper" | paper warning on Positions; data stays at the last good night | read `paper_error` (Health check), fix, then `gh workflow run nightly.yml` (bars are a no-op, paper catches up every missed session) |
| Paper check mismatch | paper state already committed | red at "Paper check"; Explain still runs | no change | run `paper_check -v` locally; the log names the first difference. A mismatch is a same-path bug: open a card, do not edit rows by hand |
| A split on a held or pending symbol | state rescaled once (`apply_split` / `apply_book_split`); `paper_check` reports that strategy `split-affected` from then on | green | positions in post-split shares and prices | none: whole-share rounding across a split makes exact replay equality impossible (see Splits) |
| Explain failed or `LLM_*` not set | text stays NULL | green (`continue-on-error`) | "explanation unavailable" | Owner step 1 |
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
- re-runs `run_rules` for A, F4 and F1, or `buy_and_hold` for SPY, over
  `[paper_start, paper_state.last_session]` with the stored `paper_state.usd_idr`;
- compares every equity snapshot (day 0 included), every closed trade and every open order or
  position with what `paper` stored.

It is the proof that backtest and live share one code path (design §9, D7). It runs every night
after Paper, and before the release with `--require-sessions 5`.

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
PY
```

Storage: the paper tables add kilobytes per month. Watch the database size with the query in
[data-pipeline.md](data-pipeline.md#storage-budget). Neon free is 0.5 GB.

## Owner steps

These need the owner, so the pipeline session does not do them. Each one is independent. Run them
from the main checkout `/home/miftah/seer` after the feature branch is merged into `main`. No
command echoes a secret, and nothing is `source`d.

### 1. LLM secrets for the Explain step (optional)

Without them the night is still correct, and the app shows "explanation unavailable".

```bash
cd /home/miftah/seer
for n in LLM_API_KEY LLM_BASE_URL LLM_MODEL; do
  engine/.venv/bin/python -c "from dotenv import dotenv_values; print(dotenv_values('.env.local')['$n'], end='')" \
    | gh secret set "$n" --repo miftahulmahfuzh/seer
done
gh secret list --repo miftahulmahfuzh/seer     # LLM_API_KEY, LLM_BASE_URL, LLM_MODEL listed (values never shown)
```

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
   - The Health check shows `sessions ≥ 5` for all four strategies, and `paper_status = success`
     on each of those runs.
2. **Replay check on Neon:**
   `SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine -v paper_check --require-sessions 5`
   must exit 0 (`split-affected` is allowed and must be named in the release notes).
3. **App check** on the XS Max and on desktop, light and dark:
   - Today shows the SPY-champion "no buys" state;
   - Positions and History show A's paper orders labelled paper;
   - the Leaderboard's Month by month shows October as a partial month for all four, with the
     SPY column.
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

- **Stop paper trading, keep bars:** delete the "Paper", "Paper check" and "Explain" steps from
  `nightly.yml`, then commit and push. Paper state stays where it was.
- **Reset paper state** (this also resets the clock; the next nightly starts over with a new
  `paper_start`), in one transaction through Python:
  ```sql
  TRUNCATE paper_state, book_positions, book_targets, book_fills, book_trades;
  DELETE FROM orders WHERE strategy_id IN ('SPY', 'A', 'F4-MOM12-N20-TREND', 'F1-SPY-SMA200-M');
  DELETE FROM equity_snapshots WHERE strategy_id IN ('SPY', 'A', 'F4-MOM12-N20-TREND', 'F1-SPY-SMA200-M');
  UPDATE strategies SET paper_start = NULL, params = '{}'::jsonb;
  UPDATE runs SET paper_status = NULL, paper_error = NULL, paper_finished_at = NULL;
  ```
  The repo is public and losses are shown on purpose: never reset to hide a result.
- **Migration 003 is additive.** The web from before this set ignores its tables.
  `UPDATE strategies SET is_champion = (id = 'A')` restores the old champion flag, but A then
  shows research picks as advice, which the paper-only decision forbids. Prefer reverting the
  code to resetting the data.

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
