# The night (engine)

## Sub-features

- `migrate`: applies `db/migrations/*.sql` (shared with web's `db:migrate`).
- `nightly`: fetches the session's bars (Massive), splits, dividends, USD/IDR, writes a `runs` row.
- `veto` / `explain`: the LLM news check and plain-language reasons (never fail the night).
- `paper`: settles and decides every roster strategy after a successful bars run.
  - 027 (Seer Adversarial): beside every decision of an active, non-benchmark, non-twin entry it writes
    `strategy_candidates`. A bracket method gets its own top 10 before any veto. A book gets its rank or
    kickoff targets, never a resize-only decision. `book_previews.next_decision_session` records the
    book's next rank session. A list error logs `no candidate list stored tonight` and never fails the night.
  - 027 also admits `A-GT` (plain A at Gotrade's fees), which starts on its first paper night.
- `paper_check`: replays every paper strategy and asserts the DB agrees (read-only).
- `sean marks`: marks the owner's real holdings to market.
- Schema only, written by mcp-notes: `adversary_verdicts` (append-only by trigger), `adversary_marks`,
  `adversary_leases`.
- Claude twins (Seer Adversarial): `paper` creates `<ID>-CX` for every active original except the
  benchmark and C, steps it one session behind, and drops what `adversary_verdicts` objected to
  before the session's open; `paper_check` replays twins.

## How to get to it (user POV)

The owner never runs these. GitHub Actions `nightly.yml` runs them at 06:17 UTC Tue–Sat. Their result is what Today, Positions and the Leaderboard show the next morning. The candidate lists are what the Seer Adversarial reviewer in mcp-notes reads to review the next session's picks.

## Driving it with verify.sh

```sh
$V up --no-web --empty                 # migrations only: 24 roster strategies, no sessions
$V doctor RUN                          # "database ok ... (27 migrations, strategies: 24)", "egress ok engine cannot reach api.github.com"
$V engine RUN nightly                  # ERROR MASSIVE_API_KEY is not set (checked ... engine.env); exit 2
$V engine RUN paper_check              # "paper_check: ok (0 of 24 roster strategies started)"; exit 0
$V engine RUN --dry-run paper          # "the bars run for session ... is missing; no paper step after a failed or missing bars run"; exit 1

# 027's schema and A-GT, read back
$V sql RUN "select id, engine, rules_id, object_name, status, paper_start, twin_of from strategies where id = 'A-GT'"
#   A-GT | bracket | design-v0-gotrade | STRATEGY_A | active | (null) | (null)
$V sql RUN "select table_name from information_schema.tables where table_schema = current_schema() and table_name in ('strategy_candidates','adversary_verdicts','adversary_marks','adversary_leases') order by 1"
#   the four tables
$V sql RUN "select tgname from pg_trigger where tgname = 'adversary_verdicts_append_only'"
#   one row

$V up --no-web --empty --net           # MODE=real-external(net=1 llm=0)
$V engine RUN --dry-run nightly        # "nightly failed ...: NightlyError: no SPY bars stored; run `backfill` first"; exit 1
```

Each of these is the correct end state for its DB, not a failure of the harness.

A paper night that writes candidate lists cannot run here (no bars; see Gotchas), so the lists, the
previews' `next_decision_session`, the append-only trigger and A-GT's first nights are proven by the DB
test journeys, with `PG_TEST_URL` set:

```sh
engine/.venv/bin/pytest -n0 engine/tests/test_adversary_schema.py engine/tests/test_paper_candidates.py
engine/.venv/bin/pytest -n0 engine/tests/test_paper_command.py -k "list or preview or twin or a_gt or catch_up or look_ahead"
```

### Claude twins (a real night on a seeded run)

`features/steps/twin-world.py` writes the engine suite's synthetic market (24 random-walk stocks
and SPY through 2026-10-09, `tests/test_paper_command.py`) and a successful bars-run row per night
into the RUN's own database, so `paper` can run for real. It refuses any URL that is not a
verify-seer run database. It also writes one `adversary_verdicts` row, the way mcp-notes' reviewer
does.

```sh
PY=engine/.venv/bin/python; TW=.claude/skills/verify-seer/features/steps/twin-world.py
$V up --no-web --empty                                   # RUN=...
$PY $TW world RUN                                        # "seeded RUN: ... 8 bars runs (2026-09-23..2026-10-02)"
$V engine RUN paper --now 2026-09-23T23:00:00Z           # exit 0; "Claude twin created" x3
$V sql RUN "select id, twin_of, status, paper_start, gate_applicable from strategies where twin_of is not null order by id"
    # A-GT-CX|A-GT, COSK-FR-GT-CX|COSK-FR-GT, RAW35-FR-GT-CX|RAW35-FR-GT; active; paper_start empty; f
for d in 24 25 28 29 30; do $V engine RUN paper --now 2026-09-${d}T23:00:00Z; done   # each exit 0
$V sql RUN "select strategy_id, last_session, pending_session from paper_state order by strategy_id"
    # originals 2026-09-30 | 2026-10-01; every *-CX 2026-09-29 | 2026-09-30
$V sql RUN "select symbol from book_targets where strategy_id = 'RAW35-FR-GT' and session_date = '2026-10-01' order by rank limit 2"
    # two symbols: H1, H2
$PY $TW verdict RUN RAW35-FR-GT 2026-10-01 H1 object 2026-10-01T12:00:00+00:00   # before the 13:30 UTC open
$PY $TW verdict RUN RAW35-FR-GT 2026-10-01 H2 object 2026-10-01T13:30:00+00:00   # at the open: late
$V engine RUN paper --now 2026-10-01T23:00:00Z           # exit 0: the twin decides 2026-10-01
$V sql RUN "select o.symbol, o.weight, t.weight from book_targets o left join book_targets t on t.strategy_id = 'RAW35-FR-GT-CX' and t.session_date = o.session_date and t.symbol = o.symbol where o.strategy_id = 'RAW35-FR-GT' and o.session_date = '2026-10-01' order by o.rank"
    # H1: twin weight empty; H2: twin weight present; every present twin weight >= the original's
$V engine RUN paper --now 2026-10-02T23:00:00Z           # exit 0: the twin settles 2026-10-01
$V sql RUN "select symbol from book_positions where strategy_id = 'RAW35-FR-GT-CX' and symbol = 'H1'"   # 0 rows
$V engine RUN paper_check                                # exit 0; every *-CX line "ok"
$V down RUN
```

## Gotchas

- On demo data (`up` without `--empty`) `paper_check` runs and reports `replay mismatch` for every seeded paper strategy (exit 1): the seeded history is hand-made, not simulated, so it cannot replay. That is the check working. Before 2026-11-03 it crashed instead (`UnknownObject: 'SPY': roster object name None`), because the seeder did not write migration 006's `object_name` column. A crash there now is a regression.
- A full real nightly cannot be produced: it needs a 10-year `backfill` from yfinance first. Mark journeys that need one `inconclusive`. That includes "the night wrote `strategy_candidates`"; use the pytest journeys above.
- `$V sql` is read-only, so the append-only trigger cannot be exercised here: an UPDATE is refused by the read-only transaction before the trigger runs. `test_adversary_schema.py` drives it.
- `--net` reaches Massive with the owner's free-tier key, which the production nightly shares (06:17, 09:41, 12:41 UTC). Keep `--net` drives few and away from those times.
- `veto` / `explain` with `--llm` spend the budget (default 3). On a DB with no candidates they make no call, which proves nothing. Seed state first.
- `backtest*`, `promote` and the store builders are refused (they write tracked reports, the roster or the shared stores).
- A twin is always one session behind: a `*-CX` `pending_session` is a session that already
  traded. That is the design (Decision D1), not a stuck night.
- On `up --empty` with no seeding, `paper` never runs (no bars run), so no twin exists and
  `doctor`'s strategy count is the migrated roster's. Twins appear only after a real night.
- If RAW35-FR-GT has no 2026-10-01 targets on the synthetic market, run the verdict journey on
  COSK-FR-GT instead (also a rank on 2026-10-01); mark it `inconclusive` if neither ranks.
