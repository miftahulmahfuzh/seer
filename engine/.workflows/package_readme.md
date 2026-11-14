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
`reevaluate`, `demote`, `promote`, `test`, `stage`, `yardstick`, and the signal panel's `panel`,
`panel-map`, `next-signal-id` and `panel-replay`.

#### `lab run MNNNN [--amend] [--jobs J]`
Runs a committed method on the dev window and records every arm. `--jobs` (default 2) is the
number of worker processes for the random-twin yardstick; the reading does not depend on it.
After recording it logs one `random-twin yardstick:` line per measured arm, in the same format
`lab yardstick` prints. A method with an arm that picks index members is refused with exit 2 by
the panel gate (D21) unless it names a panelled signal or declares `panel_exempt` (see "The panel
gate" below); `--amend` is held to the same rule.

#### `lab yardstick (M0562 ... | --arm M0562-W60-B100 | --pending) [--limit N] [--jobs J] [--store DIR] [--dry-run]`
Measures recorded dev arms against their random twins. Exactly one way to pick arms: method ids
(their due arms), `--arm` (one recorded arm, due or not), or `--pending` (every due arm in the lab
with no reading on this store). Writes only `trial_yardstick`: no trial row, no N, no test look.
Default `--jobs` here is 1.

#### `lab promote MNNNN`
Pre-registers a dev-eligible method's best variant for the test window, behind the hard gate.

#### `lab panel (S0001 ... | --pending) [--store DIR] [--sv-store DIR] [--jobs J]`
Stage one of the lab: measures committed signal files (`lab/signals/sNNNN_<slug>.py`) on the
stock-by-month panel of the dev window, first on the dev store, then on the survivorship-check
store, and records each signal once both are measured. Exactly one of ids or `--pending` (every
committed signal with no panel on this dev store; an uncommitted file is listed and skipped).
`--store` defaults to `$SEER_RESEARCH_STORE` or `research.STORE_DIR`; `--sv-store` to
`$SEER_SV_STORE` or `research.SV_STORE_DIR` (from a worktree, export it to the main checkout's
`engine/.research-sv`). `--jobs` (default 1) fans scorers out to worker processes; readings do not
depend on it. A signal already panelled on this dev store is not re-measured. Exit 2 when any
signal has no whole-window reading on either store (it is not recorded). Prints N, the luck gate's
N and the looks before and after: none of them move.

#### `lab panel-map [--top K] [--kind signal|replay|all]`
Report only. Every recorded panel ranked by its dev whole-window controlled slope, with the
published verdict, its q, the panel it is a twin of and the top bucket's spread per era. Loads no
research store and writes nothing.

#### `lab next-signal-id`
The next free signal id alone on stdout (the N footer goes to stderr): one past both the record
and the committed signal files.

#### `lab panel-replay [M0614 ...] [--family-like PATTERN] [--limit N] [--store DIR] [--sv-store DIR] [--jobs J]`
Replays every recorded dev arm of each method whose family is LIKE `--family-like` (default
`stock-%`) through the panel as a pick set: the arm's own allocator is called at each dev month end
with that month's index members and nothing held, and the names it returns (minus fixed
instruments and names outside the pool) are its picks. Measured on the dev store, then the
survivorship-check store, and recorded per arm in one transaction as a `replay` panel under the
arm's candidate id. Already-recorded arms are skipped, so a stopped run resumes; `--limit` caps the
unfinished arms attempted. An arm that cannot be replayed (no import, drifted digest, missing data,
allocator raised, too few picks) is reported and the sweep goes on. `--jobs` is 1 or 2. Writes no
trial, status or journal entry: N, the luck gate's N and the looks do not move.

### Key Python entry points

```python
# lab/runner.py
def run_method(conn, method, path, data, *, git_sha, require_commit=True, amend=False,
               yardstick_jobs=1, measure=yardstick.measure) -> Run   # passes data.fingerprint to preflight
def preflight(conn, method, path, *, require_commit=True, amend=False,
              dev_fingerprint=None) -> Amendment | None   # calls hardgate.panel_gate last
def default_store_dir() -> Path    # $SEER_RESEARCH_STORE or research.STORE_DIR (the one env read)

# lab/method.py (phase 5)
SIGNAL_ID = re.compile(r"S\d{4}")                # pinned equal to signal.SIGNAL_ID by a test
PANEL_EXEMPT_KINDS = ("chassis", "control-study", "market")
Method.signal: str | None = None; Method.panel_exempt: str = ""   # shape-checked in __post_init__

# lab/signal_book.py (phase 5: the one chassis a panelled signal is booked on)
WIDTH = 20; SWITCH = ("SPY", 200); ID_PREFIX = "SB-"
GATED_SUFFIX = "N20"; NOGATE_SUFFIX = "N20-NOGATE"; RULES = MONTHLY_HOLD_FRAC_GOTRADE
class BookParams(trend=SWITCH | None); class SignalPrepared; class SignalBook; class MarketSignalBook
def book_allocator(signal) -> SignalBook          # allocator id "SB-" + signal.id
def standard_candidates(signal, method_id, added) -> tuple[Candidate, Candidate]  # (N20, N20-NOGATE)
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

# lab/panel_run.py (phase 3: what `lab panel`, `panel-map`, `next-signal-id` call)
DEV, SURVIVORSHIP = "dev", "survivorship"
class Subject; class StorePair; class StoreRun; class Selection; class Counts; class MapRow
def check_stores(dev_dir, sv_dir, *, command) -> StorePair      # manifests only; LabError on a bad pair
def load(store_dir, *, role, command) -> research.ResearchData  # dev window + purpose checked
def open_store(conn, pair, role, *, command) -> research.ResearchData  # dev: D10 pin + fingerprint
def select_signals(conn, ids, *, pending, command) -> Selection # ids + git, before any store loads
def split_recorded(conn, subjects, dev_fingerprint) -> tuple[tuple[Subject, ...], tuple[str, ...]]
def measure_stores(conn, subjects, pair, *, command, jobs=1) -> tuple[StoreRun, StoreRun]
def has_whole_window(reading) -> bool
def record(conn, subject, dev_run, sv_run, *, git_sha, measured) -> bool  # False: a peer got there first
def panel_map(conn, *, kind="all") -> tuple[str | None, list[MapRow], int]
def format_map(...) -> str; def format_reading(...) -> str; def footer(conn, before, *, lead) -> str
def next_signal_id(conn) -> str     # store.next_signal_id(conn, taken=signal.discover())

# lab/panel_replay.py (phase 4: what `lab panel-replay` calls; writes only through panel_run.record)
COMMAND = "lab panel-replay"; FAMILY_LIKE = "stock-%"
class Recorded; class Work; class Skip; class Outcome; class StorePass; class Report; class PickScorer
def select(conn, *, method_ids=(), family_like=FAMILY_LIKE) -> tuple[Recorded, ...]  # LabError on a bad id
def unfinished(conn, selected, dev_fingerprint) -> tuple[list[Recorded], int]
def resolve(selected, load) -> tuple[list[Work], list[Skip]]   # config_digest must equal the recorded one
def run(conn, dev_dir, sv_dir, *, git_sha, method_ids=(), family_like=None, limit=None, jobs=1,
        load=None, now=store.now_iso) -> Report
def format_report(rep: Report) -> str

# lab/hardgate.py
def check(conn, method_id) -> None                 # raises LabError on any refusal
def yardstick_refusal(conn, method_id, candidate_id) -> str | None
# (D21) the panel gate, run by runner.preflight (phase 5)
def picks_members(c) -> bool                       # backtest.dev._reads's rule, restated
def dev_store_dir() -> Path                        # delegates to runner.default_store_dir()
def dev_store_fingerprint(store_dir=None) -> str   # manifest.json only; ValueError if unreadable
def panel_refusal(conn, method, candidates, *, dev_fingerprint=None) -> str | None
def panel_gate(conn, method, candidates, *, dev_fingerprint=None) -> None   # raises LabError

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

1. Preflight (committed method file, unrun digest, store checks; a survivorship-check store is refused first). The panel gate (D21) is the last preflight refusal, after the repeat check and before any store loads.
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

**Data flow of `lab panel` (`lab/panel_run.py`, phase 3)**. Order is the contract:
1. `select_signals`: unknown ids, a signal file not committed exactly as it stands (the commit is
   the pre-registration) and a file changed since its panel are refused from git alone.
2. `check_stores`: both manifests, before either store loads. The dev side must declare the dev
   window with no purpose marker; the survivorship side must exist, be marked survivorship-check
   and cover the dev window. A test-window store is refused by its manifest and never read.
3. `split_recorded`: what `store.has_panel` already holds on the dev fingerprint is skipped, so a
   repeat loads nothing.
4. `measure_stores`: load the dev store through `open_store` (which applies `hardgate.pin_dev_store`,
   D10, and checks the loaded fingerprint still matches the manifest), build the frame once,
   measure every subject, drop it, then do the same on the survivorship-check store. The two
   stores (about 1 GB each) are never in memory together.
5. `record`: per subject, the `panel_signals` row and every `panel_results` row for both stores in
   one `BEGIN IMMEDIATE` transaction, re-asking `has_panel` under the lock. No half record, no
   trial, no journal entry.

Phase 4's replay reuses `Subject` (`mode="picks"`), `check_stores`, `open_store`, `record`,
`Counts` and `footer` with its own store loop, so the D10 pin and fingerprint check live once.
`panel_map` ranks on the dev store of the most recent dev panel; panels measured only on older dev
stores are counted, not ranked.

### The panel gate in `lab run` (D21, phase 5)

The seam between the two stages: the book lab runs only signals that cleared the panel.
`hardgate.panel_gate` is called last in `runner.preflight`, so a refusal loads no store, records
nothing and spends no method id (exit 2). Nothing that bypasses `runner.preflight` meets it
(`lab remeasure`, `lab costs`, `lab reevaluate`, `lab yardstick`, the seeded `H-*` rows,
`method.discover()`).

- **Who binds**: a method where an arm about to run (`all_candidates()`, or the pending
  amendment's candidates on `--amend`) picks index members (`picks_members`: a bracket strategy,
  or an allocator whose `uses_members(params)` is True). Market switches and ETF rotations never
  bind.
- **Ways through**: `panel_exempt` set (`"chassis: ..."`, `"control-study: ..."` or
  `"market: ..."` plus a reason, checked at construction) passes. `signal` set passes only if the
  signal is discoverable, every non-control arm (`control_shape.role_of`) has the config digest of
  one of `signal_book.standard_candidates` (checked first, no store needed), the signal has a panel
  on the dev fingerprint recorded from the file's current `source_sha`, and its published verdict
  clears there. Neither set: refused. A method may not set both.
- **Which store**: `run_method` passes `data.fingerprint`; its first `preflight` precedes any
  simulation, so that check is authoritative. A caller that has not loaded the store passes None
  and the gate reads the default store's `manifest.json` (`dev_store_fingerprint`), and only for a
  signal method whose arms already have the standard shape. The env read (`$SEER_RESEARCH_STORE`)
  lives in `runner.default_store_dir()`; `hardgate.dev_store_dir()` delegates to it so hardgate
  reads no environment variable.
- Fails closed: missing signal file, no panel on this store, changed signal file, no clearing
  verdict, or an unreadable manifest each refuse. No override flag.
- Existing test fixtures that run a member-picking `FACTOR`/`BLEND` method (`test_lab_exposure`,
  `test_lab_gate_probe`, `test_lab_survivorship`, `test_lab_yardstick_gate`) declare
  `panel_exempt="chassis: ..."`. `Method.signal` and `panel_exempt` sit outside every config
  digest, so no committed method file, sha or digest moved.

**The signal book (`lab/signal_book.py`)**: the one chassis. On each monthly decision date
(`MONTHLY_HOLD_FRAC_GOTRADE`) the pool is F4's screen (`tree_rank.SCREEN` via
`f_factor.factor_rows` / `FactorPrepared.rows_on`), each pool name is scored with
`Signal.scores` (the same cut the panel measured), and the `WIDTH` highest finite scores (ties by
symbol) are held at `equal_weight(WIDTH)`. The gated arm (`<method>-N20`) holds nothing when SPY
closes at or below its 200-day average (`f_factor.trend_on`); the `<method>-N20-NOGATE` arm never
steps aside. `BookParams` admits only those two settings. The allocator id is `"SB-" + signal.id`,
so two methods booking one signal get identical digests and the second is refused by the repeat
check: one signal, one book. A signal with `market_fields` gets a `MarketSignalBook`
(`prepare_market`; history-only path targets nothing). Pure: no DB, clock, files or randomness.
The method template (`.claude/skills/explore-and-experiment-new-method/method_template.py`) now
shows the signal form first and the own-allocator form with `panel_exempt` second.

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
the result is identical at any `jobs`. `lab panel` loads its two stores one after the other, never
together, and its `record` re-checks `has_panel` under the write lock so a parallel session that
recorded the same signal first wins and nothing is written twice.

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
engine/.venv/bin/python -m seer_engine lab next-signal-id
SEER_SV_STORE=/home/miftah/seer/engine/.research-sv \
  engine/.venv/bin/python -m seer_engine lab panel S0001        # signal file committed first
engine/.venv/bin/python -m seer_engine lab panel-map --top 20
SEER_SV_STORE=/home/miftah/seer/engine/.research-sv \
  engine/.venv/bin/python -m seer_engine lab panel-replay --limit 50
engine/.venv/bin/python -m seer_engine lab panel-map --kind replay --top 20
```

### Gotchas
- `lab promote` refuses a variant never measured against its twins (D20), even when `lab status` shows it dev-eligible under the staged rule. Run `lab yardstick --arm <candidate>` first.
- An arm recorded on or after `YARDSTICK_SINCE` with no reading reads not eligible; that is a hole in the record, fixed by `lab yardstick` then `lab reevaluate`.
- `unmatched` never clears: the fix is a new arm (an amendment), not a remeasure.
- argparse `help=` strings are %-interpolated; escape `%` as `%%`.
- Closed records (`backtest/registry.py`, past reports, existing lab rows) are frozen.
- `lab panel` and `lab panel-replay` need a survivorship-check store; a worktree has none, so export `SEER_SV_STORE` (and `SEER_RESEARCH_STORE`) to the main checkout's stores.

## Notes

The rules that bind the lab are in `docs/plans/2026-10-03-seer-design.md` (§1, the real-money bar)
and `docs/plans/2026-10-04-method-lab-design.md` (§10 covers the yardstick condition). The yardstick
was built in the random-twin-yardstick plan set (`.workflows/plan/RANDOM_TWIN_YARDSTICK_PLAN.md`):
phase 1 arm roles, phase 2 the twin engine, phase 3 the `trial_yardstick` record and
`lab yardstick`, phase 4 (task P1-ENG-VZXN) the yardstick as a dev-screen condition and hard-gate
clause D20.

The signal panel is the sera-signal-panel plan set (`.workflows/plan/sera-signal-panel/`): phase 1
the signal registry and pure evaluator, phase 2 (task P1-ENG-1MOB) the append-only panel tables,
`panel_verdict.published` and the `panel` key in `web/data/lab.json`, phase 3 (task P1-ENG-7F8X)
`lab/panel_run.py` and the `lab panel`, `lab panel-map` and `lab next-signal-id` commands
(feature-map entry `.claude/skills/verify-seer/features/signal-panel.md`), phase 4 (task
P1-ENG-3AY5) `lab/panel_replay.py` and `lab panel-replay`, the replay of recorded methods (runbook
`docs/runbooks/signal-panel.md`).

Documentation Created: 2026-11-13
