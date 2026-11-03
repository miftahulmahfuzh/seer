# The night (engine)

## Sub-features

- `migrate`: applies `db/migrations/*.sql` (shared with web's `db:migrate`).
- `nightly`: fetches the session's bars (Massive), splits, dividends, USD/IDR, writes a `runs` row.
- `veto` / `explain`: the LLM news check and plain-language reasons (never fail the night).
- `paper`: settles and decides every roster strategy after a successful bars run.
- `paper_check`: replays every paper strategy and asserts the DB agrees (read-only).
- `sean marks`: marks the owner's real holdings to market.

## How to get to it (user POV)

The owner never runs these. GitHub Actions `nightly.yml` runs them at 06:17 UTC Tue–Sat. Their result is what Today, Positions and the Leaderboard show the next morning.

## Driving it with verify.sh

```sh
$V up --no-web --empty                 # migrations only: 23 roster strategies, no sessions
$V doctor RUN                          # "database ok ... (26 migrations, strategies: 23)", "egress ok engine cannot reach api.github.com"
$V engine RUN nightly                  # ERROR MASSIVE_API_KEY is not set (checked ... engine.env); exit 2
$V engine RUN paper_check              # "paper_check: ok (0 of 23 roster strategies started)"; exit 0
$V engine RUN --dry-run paper          # "the bars run for session ... is missing; no paper step after a failed or missing bars run"; exit 1

$V up --no-web --empty --net           # MODE=real-external(net=1 llm=0)
$V engine RUN --dry-run nightly        # "nightly failed ...: NightlyError: no SPY bars stored; run `backfill` first"; exit 1
```

Each of these is the correct end state for its DB, not a failure of the harness.

## Gotchas

- On demo data (`up` without `--empty`) `paper_check` runs and reports `replay mismatch` for all five strategies (exit 1): the seeded history is hand-made, not simulated, so it cannot replay. That is the check working. Before 2026-11-03 it crashed instead (`UnknownObject: 'SPY': roster object name None`), because the seeder did not write migration 006's `object_name` column. A crash there now is a regression.
- A full real nightly cannot be produced: it needs a 10-year `backfill` from yfinance first. Mark journeys that need one `inconclusive`.
- `--net` reaches Massive with the owner's free-tier key, which the production nightly shares (06:17, 09:41, 12:41 UTC). Keep `--net` drives few and away from those times.
- `veto` / `explain` with `--llm` spend the budget (default 3). On a DB with no candidates they make no call, which proves nothing. Seed state first.
- `backtest*`, `promote` and the store builders are refused (they write tracked reports, the roster or the shared stores).
