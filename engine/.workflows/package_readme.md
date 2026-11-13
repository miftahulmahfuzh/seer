# Package: seer_engine

**Location**: `engine` (Python 3.11 package `seer_engine`, source in `engine/src/seer_engine/`)
**Last Updated**: 2026-11-14

## Overview

`seer_engine` is Seer's whole pipeline. It ingests point-in-time market data (universe membership,
daily bars, splits, dividends, USD/IDR, SEC fundamentals and shares outstanding) into Neon Postgres,
paper-trades the strategy roster every night through one shared fill simulator, marks the owner's
real Gotrade ledger to market, and hosts the **method lab**, the append-only SQLite record that
pre-registers, runs, screens and gates every candidate strategy against SPY.

**Key Responsibilities:**
- The nightly data pipeline (`nightly`, `backfill`, `universe`, `fundamentals`, `shares`), driven by the GitHub Actions cron.
- One deterministic fill simulator (`sim/`) shared by backtests, the lab and live paper trading, with Gotrade's fees (`sim/costs.py`).
- Paper trading (`paper/`) and the owner's real-money ledger (`sean/`, the twin of `web/lib/sean/ledger.ts`).
- The method lab (`lab/`): pre-registration, the dev screen, the N policy and deflated Sharpe, the hard gate in front of the test window, and the random-twin yardstick.

## Layout

| Path | What lives there |
|---|---|
| `cli.py`, `__main__.py` | `python -m seer_engine [--dry-run] [-v\|-vv] <command>`. Discovers commands; never edited to add one. |
| `commands/` | One module per subcommand, each exporting `HELP`, `add_arguments(p)`, `run(args) -> int`. |
| `sim/` | Pure fill simulator: order lifecycle, sizing, rules, contributions, charges, `costs.py` (Gotrade fees). No DB, network or clock. |
| `strategies/` | Pure functions from bar history to ranked `sim.Pick`s (A, B, C, factor/fundamental/rotation/swing allocators, `twin.py`). |
| `backtest/` | Strategy backtests, the dev-window runner (`dev.py`), `metrics.py`, `tuning.py` (`DEV_MAX_DRAWDOWN` and other screen bars), walk-forward. `registry.py` is a closed record. |
| `paper/` | Nightly paper trading: pure `roster`, `bracket`, `book`, `benchmark`, `replay`; `store` is the one impure edge. |
| `sean/` | The owner's real Gotrade orders: average-cost `ledger`, `marks`, `equity`, `calibrate`. |
| `fundamentals/`, `shares/` | SEC EDGAR derivations: concept ladder, SUE, point-in-time shares outstanding. |
| `lab/` | The method lab (see below). `lab/methods/mNNNN_<slug>.py` is one method per file exporting `METHOD = Method(...)`. |
| top-level modules | `config`, `db` (Postgres connection + transaction helper), `research` (the local dev-window research store), `runs`, `universe`, `bars`, `fx`, `dividends`, `splits`, data-vendor clients (`yahoo`, `massive`, `eodhd`, `finnhub`, `sec`), `llm`. |

## Exported API

### CLI surface

`seer_engine.cli:main` (also the `seer-engine` console script). Global flags: `--dry-run` rolls
back every write, `-v`/`-vv` raise logging. Subcommands are the modules in `commands/`; notable
ones: `migrate`, `nightly`, `backfill`, `universe`, `fundamentals`, `shares`, `paper`,
`paper_check`, `compare`, `promote` (lab variant onto the paper roster), `sean`, `research_store`,
`backtest*`, and `lab`.

**Exit codes**: 0 ok; 2 the lab's rules refused the request (`store.LabError`); 1 an error.

### The method lab (`seer_engine.lab`)

`lab` subcommands that matter for this document: `next-id`, `run MNNNN`, `show`, `status`,
`reevaluate`, `demote`, `promote`, `test`, `stage`, and `yardstick`.

#### `lab run MNNNN [--amend] [--jobs J]`
Runs a committed method on the dev window and records every arm. `--jobs` (default 2) is the
number of worker processes for the random-twin yardstick; the reading does not depend on it.
After recording it logs one `random-twin yardstick:` line per measured arm, in the same format
`lab yardstick` prints.

#### `lab yardstick (M0562 ... | --arm M0562-W60-B100 | --pending) [--limit N] [--jobs J] [--store DIR] [--dry-run]`
Measures recorded dev arms against their random twins. Exactly one way to pick arms: method ids
(their due arms), `--arm` (one recorded arm, due or not), or `--pending` (every due arm in the lab
with no reading on this store). Writes only `trial_yardstick`: no trial row, no N, no test look.
Default `--jobs` here is 1.

#### `lab promote MNNNN`
Pre-registers a dev-eligible method's best variant for the test window, behind the hard gate.

### Key Python entry points

```python
# lab/runner.py
def run_method(conn, method, path, data, *, git_sha, require_commit=True, amend=False,
               yardstick_jobs=1, measure=yardstick.measure) -> Run
def trial_rows(..., yardsticks: Mapping[str, yardstick.Measurement] | None = None) -> ...

# lab/yardstick.py
DRAWS = 200
STATUS_MEASURED, STATUS_NOT_APPLICABLE, STATUS_UNMATCHED = "measured", "not-applicable", "unmatched"
def measure(market, dividends, spy_dividends, candidate, *, initial_idr, contributions,
            draws=DRAWS, jobs=1, expect=None) -> Measurement   # raises Unreproducible

# lab/store.py
YARDSTICK_MIN_PERCENTILE = 0.90
YARDSTICK_LABEL = "beats 90% of random twins"   # f-string built from the percentile
YARDSTICK_SINCE = "2026-11-14"
def verdict(conn, trial, ...) -> Verdict
def yardstick_of(conn, trial_n) -> sqlite3.Row | None
def yardstick_clears(row) -> bool | None          # None = never measured
def yardstick_due(conn, trial, *, at=None) -> bool
def insert_yardstick(conn, row: YardstickRow) -> bool
def reevaluate_method(conn, method_id) -> Reevaluation
class LabError(RuntimeError)                      # -> exit code 2
# signal panel record (phase 2 of the sera-signal-panel set)
PANEL_KINDS = ("signal", "replay"); PANEL_STORE_ROLES = ("dev", "survivorship")
PANEL_ERAS = ("all", "pre2009", "2009-2015")
class PanelSignalRow; class PanelResultRow       # PanelResultRow.from_era(...)
def panel_signals(conn) -> list[dict]            # [] when the tables are absent
def panel_results(conn, signal_id=None) -> list[dict]   # oldest first
def has_panel(conn, signal_id, rule_id, store_fingerprint) -> bool
def next_signal_id(conn, taken=()) -> str        # "S0001"-style; replays never consume one
def insert_panel_signal(conn, row) -> bool       # False on a repeat; LabError on a changed file
def insert_panel_results(conn, rows) -> int      # new rows; whole batch checked before any write
SNAPSHOT_VERSION = 9                             # lab.json gains a trailing "panel" key

# lab/panel_verdict.py
RULE_ID = "panel-v1"; FDR = 0.10                 # RULE_ID must equal panel.RULE_ID
def current_dev_fingerprint(conn) -> str | None
def readings(conn, *, dev_fingerprint=None) -> dict[str, Readings]
def published(conn, *, dev_fingerprint=None) -> dict[str, Verdict]  # computed on read, never stored
def one_sided_p(t, months) -> float; def bh_qvalues(pvalues) -> list[float]

# lab/hardgate.py
def check(conn, method_id) -> None                 # raises LabError on any refusal
def yardstick_refusal(conn, method_id, candidate_id) -> str | None

# lab/prereg.py
def gate_text(conn=None) -> str                    # the gate as written into a pre-registration
```

## Internal Architecture

### The dev screen (`store.verdict`)

A dev arm is **dev-eligible** only when every condition clears, re-decided at call time against
today's bars (nothing recorded is trusted verbatim):

1. The five P7a D8 owner conditions (`backtest.dev.FAILURE_LABELS`), re-derived from recorded columns against the live `tuning` bars.
2. The luck test: DSR at the gate's *current* N (`store.DSR_MIN`, N from the `DSR_POLICY`).
3. Not a control arm (`CONTROL_LABEL`).
4. **The random-twin yardstick** (`YARDSTICK_LABEL`, added last): the arm must out-earn at least `YARDSTICK_MIN_PERCENTILE` (90%) of its random twins.

`Verdict.failed` lists failure labels in that order; `eligible == (failed == ())`.

### The random-twin yardstick

A *twin* replays the arm's own recorded decisions (same dates, weights, entries and exits) with each
picked stock swapped for a randomly drawn index member of similar trading size. `yardstick.measure`
re-runs the arm (checked against the recorded trades and total return, else `Unreproducible`),
simulates `DRAWS` twins, and reports the share the arm out-earned (ties count against the arm).

Clearing rule (`store.yardstick_clears`, the single rule every caller uses):
- **True**: `measured` at or above the bar, or `not-applicable` (a book with no picked stock, e.g. an ETF switch or a bracket arm, has nothing to swap).
- **False**: `measured` below the bar, `unmatched` (twins' median trade count or turnover outside half to twice the arm's), or any unknown status.
- **None**: no reading. The caller decides what that means.

**Staging (Decision D5, `store._yardstick_binds`)**:
- A control arm is never judged on the yardstick.
- When a reading exists, it decides, whatever the arm's run date.
- With no reading, the yardstick fails an arm only if every other condition passes **and** it was recorded on or after `YARDSTICK_SINCE` (such an arm went through a measuring `lab run`, so a missing reading is a hole in the record). Older unmeasured arms are judged on their other conditions until the backfill measures them (see `docs/runbooks/yardstick-backfill.md`).

`store._blocking` (the second, independent check `lab reevaluate` makes before a method may move
off `rejected`) restates the same rule without calling `_yardstick_binds`.

### The hard gate (`hardgate.check`, run by `lab promote`)

Refuses, with no override, a method whose folds or kin have already judged it. The clauses read
the variant `lab promote` would pre-register in this order: walk-forward folds (picks, then the
variant), (D18) not a control arm, **(D20) the yardstick**, (D19) not another method's or its own
control's book, (D16) an honest fall, (D17) a correctly shaped control.

**(D20)** is *not* staged: the variant must hold a reading that clears. A reading below the bar, an
`unmatched` reading, **and no reading at all** are refused (`yardstick_refusal`). Absence refuses
here because the measurement is always available: `lab yardstick --arm <candidate>` (or
`lab yardstick <method>`) takes it without spending a trial, N or look. D20 does not replace the
deflated Sharpe and does not touch the §1 real-money bar.

### Data flow of `lab run`

1. Preflight (committed method file, unrun digest, store checks; a survivorship-check store is refused first).
2. `dev.run_registry` simulates every arm.
3. `_measure_yardsticks`, **before the write lock**: provisional DSRs (`_provisional_dsrs`) pick the arms still worth measuring (`_due_for_yardstick`: not a control, clear of the five D8 conditions and the provisional luck test); each is measured at its own capital and funding. This is the slowest step and the lab-wide write lock is not held during it.
4. `store.begin_immediate`, then `trial_rows` decides again under the lock. An arm that clears everything but has no reading (luck moved between reads, or `Unreproducible`) is labelled with `YARDSTICK_LABEL`: the record fails closed, and `lab yardstick` + `lab reevaluate` is the way back.
5. Trials, roles, moments, funding, provenance and yardstick readings are inserted in one transaction; method status becomes `dev-eligible` or `rejected`.

### The signal panel record (stage one of the lab)

A stock-picking idea is measured on a stock-by-month panel (does its ranking order next month's
returns?) before it is ever simulated as a book. Phase 1 added the pure evaluator (`lab/panel.py`);
phase 2 adds its record and verdict. Neither table is a trial: no N, no test look.

- `panel_signals`: one row per thing measured, either a committed signal file (`S0001`, kind
  `signal`) or a replay of a recorded dev arm (its candidate id, kind `replay`, `method_id` set).
  A panelled signal is frozen: the same id from a different `source_sha` is refused.
- `panel_results`: one row per (signal, panel rule, research store, era) holding months, rank
  correlation, top-minus-pool spread and the controlled slope, each with its t-statistic.
- Both are `CREATE TABLE IF NOT EXISTS` on connect with no schema version (older checkouts sharing
  `SEER_LAB_DB` open the DB unchanged), every reader answers empty when they are absent, and
  triggers refuse every UPDATE and DELETE.

**Published verdict (`panel_verdict.published`)**: never stored, because the false-discovery
correction moves with every panel recorded. A panel clears when (1) its whole-window controlled
slope on the current dev store is positive and its one-sided p-value (Student's t on `months - 1`
df, computed without scipy) survives Benjamini-Hochberg at `FDR` across every distinct pick set on
that store; (2) its top bucket beat the pool in 2009-2015; (3) its whole-window slope stays
positive on the survivorship store. **Replay twins collapse**: panels with the same `picks_hash`
count once, carried by the earliest recorded (`created`, then id); later ones report `twin_of`,
show the first's q-value and never clear in their own name. `Verdict.reasons` are plain sentences
for `/sera/signals`.

**Snapshot**: `store.snapshot` (now `SNAPSHOT_VERSION = 9`) appends a `panel` block,
`{rule, fdr, signals: [...]}`, with each signal's verdict and its dev and survivorship readings.
One dev fingerprint is resolved once and used for both readings and verdicts; signals are ranked
by dev whole-window slope, unmeasured last, ties by id. `web/lib/sera/types.ts` mirrors the shape.

### Pre-registration text

`prereg.gate_text` writes the gate into every pre-registration file from live constants, so it now
names the yardstick ("beats 90% of random twins ... or held no picked stock") beside the five D8
conditions and the DSR bar. Files written before 2026-11-14 keep their own day's text.

## Dependencies

### External packages
- `psycopg[binary]`: Neon Postgres access (`db.py`).
- `pandas`, `numpy`: series and panel arithmetic; `pandas_market_calendars`: NYSE sessions.
- `yfinance`, `requests`: market data and vendor HTTP (Massive, EODHD, Finnhub, SEC, Frankfurter).
- `scikit-learn`: the walk-forward tree ranker (`lab/tree_rank.py`).
- `python-dotenv`: env loading; `openpyxl`: spreadsheet ingest.
- Dev: `pytest`, `pytest-xdist` (`-n auto`), `ruff` (E9 + F only, F401 ignored).

### Standard library
- `sqlite3`: the lab DB (`lab/lab.sqlite`, append-only via triggers).
- `multiprocessing` (yardstick workers), `argparse`, `dataclasses`, `decimal` (money), `logging`.

## Reverse Dependencies

- `.github/workflows/*.yml` (for example `backfill.yml`, `universe.yml`, `sean.yml`) run the CLI on GitHub Actions cron.
- `web/` reads what the engine writes to Neon, and `/sera` reads `web/data/lab.json` written by `lab stage`. Several engine constants (drawdown bar, contribution schedule, fee minimums, resize band) are mirrored in `web/` and a test asserts they match.
- Repo skills (`verify-seer`, `explore-and-experiment-new-method`, `sera-the-explorer`, `calculate-assets`) drive the `lab` CLI.

## Concurrency

The pipeline is single-process per command. Parallel sessions share the lab through
`SEER_LAB_DB` and the research store through `SEER_RESEARCH_STORE`. The lab serialises writers with
SQLite `BEGIN IMMEDIATE` (`store.begin_immediate`); `lab run` keeps the slow yardstick measurement
outside that lock and re-decides eligibility under it. `yardstick.measure` fans twins out to `jobs`
worker processes, each holding a full simulation in memory (hence the default of 2 in `lab run`);
the result is identical at any `jobs`.

## Error Handling

- `store.LabError` (and subclasses such as `prereg.PreregError`): the lab's rules refused; commands map it to exit 2. Refusal messages state what was not written and the way back.
- `yardstick.Unreproducible`: the arm did not re-run to its recorded trades and return; `lab run` records it not eligible and logs why. Any other exception during measurement propagates before anything is written.
- Tests never reach production: an autouse fixture points them at a nonexistent env file and an `.invalid` DB host.

## Performance

- The yardstick is the most expensive lab step: `DRAWS` (200) full simulations per measured arm, and only arms that clear every other condition are measured during `lab run`.
- The research store (`engine/.research/`) is a local, gitignored dataset so dev runs never hit Neon.

## Usage

```bash
python3.11 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'
engine/.venv/bin/python -m seer_engine lab next-id
engine/.venv/bin/python -m seer_engine lab run M0700            # method file committed first
engine/.venv/bin/python -m seer_engine lab yardstick --arm M0700-W60-B100
engine/.venv/bin/python -m seer_engine lab yardstick --pending --limit 20 --jobs 2
engine/.venv/bin/python -m seer_engine lab promote M0700
```

### Gotchas
- `lab promote` refuses a variant never measured against its twins (D20), even when `lab status` shows it dev-eligible under the staged rule. Run `lab yardstick --arm <candidate>` first.
- An arm recorded on or after `YARDSTICK_SINCE` with no reading reads not eligible; that is a hole in the record, fixed by `lab yardstick` then `lab reevaluate`.
- `unmatched` never clears: the fix is a new arm (an amendment), not a remeasure.
- argparse `help=` strings are %-interpolated; escape `%` as `%%`.
- Closed records (`backtest/registry.py`, past reports, existing lab rows) are frozen.

## Notes

The rules that bind the lab are in `docs/plans/2026-10-03-seer-design.md` (§1, the real-money bar)
and `docs/plans/2026-10-04-method-lab-design.md` (§10 covers the yardstick condition). The yardstick
was built in the random-twin-yardstick plan set (`.workflows/plan/RANDOM_TWIN_YARDSTICK_PLAN.md`):
phase 1 arm roles, phase 2 the twin engine, phase 3 the `trial_yardstick` record and
`lab yardstick`, phase 4 (task P1-ENG-VZXN) the yardstick as a dev-screen condition and hard-gate
clause D20.

The signal panel is the sera-signal-panel plan set (`.workflows/plan/sera-signal-panel/`): phase 1
the signal registry and pure evaluator, phase 2 (task P1-ENG-1MOB) the append-only panel tables,
`panel_verdict.published` and the `panel` key in `web/data/lab.json`. The `lab panel` and
`lab panel-map` commands that write and print it come in later phases.

Documentation Created: 2026-11-13
