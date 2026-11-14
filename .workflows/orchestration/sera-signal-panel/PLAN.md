# Plan: Sera signal panel — screen a stock-picking idea on a stock-by-month panel before it becomes a book

**Slug:** sera-signal-panel
**Date:** 2026-11-13 20:05 WIB
**Analysis:** `.workflows/analyze/20261113-200537-K7P2_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/sera-signal-panel`
**Branch:** `feature/sera-signal-panel` (base: `origin/main` @ `b0652d2`)
**Phases:** 7
**Status:** phase 4/7 complete
**Coordinator:** —

---

## Why

Build a signal panel as stage one of Sera's exploration (the Seer method lab), so a stock-picking idea is screened on a stock-by-month panel before it ever becomes a full book backtest.

Problem (measured this session from lab/lab.sqlite, read-only): 664 methods, 422 run in 2,265 dev backtests, 184 dev-eligible, 0 promotable (hard gate refuses 179), 6 of 6 test looks failed on "beats SPY TR". 350 of the 464 methods with a verdict are stock-signal families. 32 of 35 batch syntheses since 2026-11-01 carry a null headline (random picks match, the switch does the work, no buy signal). Each idea is tested as one concentrated book through the full simulator; on the only two arms with a 200-random-twin reading, twins with identical dates and weights spread about 3.6 pts/yr (p5-p95), larger than a typical signal effect. Only 2 of 364 eligible dev trials have a yardstick reading. engine/src/seer_engine/lab/ has ~a dozen book-level de-noising modules (control_draw, control_shape, control_weight, dressing, shortfall, exposure, gate_probe, timing, turnover, twins, yardstick) and no cross-sectional signal evaluator.

Constraints: closed records are frozen (existing lab rows, config digests, registry); shared lab params cannot gain a field; lookback cap of 473 bars on History in the smoke fixture; fundamentals panel starts 2009; market-cap coverage is partial; research store memory ~1.79 MB/symbol on a 15 GB laptop; tests must never reach production; verify-seer feature map must be updated for user-facing changes; plain-language text for the owner. Open risks to analyse: survivorship in the dev store, look-ahead in the panel builder, multiple-testing policy interaction with the existing N policy and DSR, whether panel looks should count against N, and how a panel "no" on the whole space is recorded as a finding.

Owner, same conversation: "i am fine if you want to propose a huge refactor, a huge architectural change, removing a big module, cutting some big chunk off.. i just care about results, i dont care about how much effort it would take, how much tokens it would cost. just BE RUTHLESS".

## Requirements

| ID | What the user asked for (verbatim) | Phases |
|---|---|---|
| R1 | A signal registry: a signal is a pure function (symbol, data_date, look-ahead-safe history/market) -> score, one per file or entry, pre-registered by commit like methods are. | 1, 3 |
| R2 | A new `lab panel` command: for every index member and month in the dev window (ends 2015-10-16, never the test window), signal value and next-month return; reports top-minus-pool spread and rank correlation with error bars, split by era (2009-2015 on its own), raw and after removing momentum, beta, size and volatility; a false-discovery correction across all registered signals; runs on both the dev store and the survivorship store (engine/.research-sv) and reports both. | 1, 2, 3 |
| R3 | First job: replay the signals of the already-run stock-signal methods (lab/methods/mNNNN_*.py, family like 'stock-%') through the panel in one pass, producing a ranked map of the explored space. Decide how to extract the ranking function from existing Allocators without changing any config digest or frozen record. | 2, 3, 4 |
| R4 | Stage two unchanged: the book lab (pre-registration, hard gate, DSR, yardstick, test budget, Gotrade fees) runs only signals that clear the panel, on one fixed chassis. Define the panel bar and where it is enforced (lab idea / lab run refusal, exit 2). | 3, 5 |
| R5 | Skill changes: .claude/skills/sera-the-explorer and .claude/skills/explore-and-experiment-new-method — signal ideas go through the panel instead of one agent session + worktree + tmux window each; drop the "queue at least one next idea" rule and the one-per-family slate rule for signal ideas; one synthesis per panel sweep rather than per four methods; route the 138 queued stock-signal ideas through the panel. | 7 |
| R6 | Persistence and site: decide whether panel results live in lab.sqlite (new append-only table + migration, snapshot in web/data/lab.json, CI row-for-row check) and how /sera shows them in plain language. | 2, 6 |

### Acceptance Criteria

| ID | Pattern | Criterion | Phases | Journeys |
|---|---|---|---|---|
| R1.1 | ubiquitous | THE SYSTEM SHALL discover every `engine/src/seer_engine/lab/signals/sNNNN_<slug>.py` module exporting `SIGNAL`, and its contract test SHALL fail for a signal that is impure, repeats an id, or returns a different score when bars dated after the data date change. | 1 | P1.J1, P1.J2 |
| R1.2 | unwanted | IF a signal file named to `lab panel` is uncommitted or modified in the working tree THEN THE SYSTEM SHALL exit 2 and record nothing. | 3 | P3.J2 |
| R2.1 | event | WHEN `lab panel SNNNN` runs THE SYSTEM SHALL record, for the dev store and the survivorship store and for each era (whole window, before 2009, 2009-2015), the months measured, the mean monthly rank correlation and its t-statistic, the annualised top-bucket-minus-pool spread and its t-statistic, and the slope on next-month return after controlling for momentum, beta, size and volatility with its t-statistic. | 1, 3 | P1.J3, P1.J4, P1.J5, P3.J1 |
| R2.2 | unwanted | IF the store handed to `lab panel` declares any window other than dev, or the survivorship store is missing, THEN THE SYSTEM SHALL exit 2 and record nothing. | 3 | P3.J3 |
| R2.3 | event | WHEN `lab panel-map` runs THE SYSTEM SHALL print every recorded panel ranked by its controlled slope, each with a verdict computed by a Benjamini-Hochberg correction across all distinct recorded panels. | 2, 3 | P2.J3, P2.J4, P2.J5, P3.J4 |
| R3.1 | event | WHEN `lab panel-replay` runs THE SYSTEM SHALL record one pick-set panel per recorded dev candidate of every method whose family begins `stock-`, obtained by calling the candidate's own allocator at each month end with nothing held, while leaving every `trials` row, config digest and recorded source sha byte-identical. | 4 | P4.J1, P4.J2, P4.J3, P4.J4, P4.J5 |
| R3.2 | state | WHILE two recorded panels hold the identical pick set in every month THE SYSTEM SHALL count them as one panel in the correction and show the later one as a twin of the first in `lab panel-map`. | 2, 3 | P2.J3, P2.J4, P2.J5, P3.J5 |
| R4.1 | unwanted | IF `lab run` is given a method with a candidate that picks index members and the method names neither a registered signal whose published panel verdict clears on the current dev store nor a panel exemption THEN THE SYSTEM SHALL exit 2, record nothing and spend no N. | 5 | P5.J1, P5.J3, P5.J4 |
| R4.2 | unwanted | IF a method names a signal and any of its non-control candidates is not that signal's standard-chassis book THEN THE SYSTEM SHALL exit 2 and record nothing. | 5 | P5.J2, P5.J3, P5.J4 |
| R4.3 | ubiquitous | THE SYSTEM SHALL leave the luck gate's N unchanged by any `lab panel`, `lab panel-replay` or `lab panel-map` run. | 3 | P3.J1, P3.J4 |
| R5.1 | ubiquitous | THE SYSTEM SHALL carry, in `.claude/skills/sera-the-explorer/SKILL.md`, a sweep procedure in which one session writes and commits several signal files, runs `lab panel` on them, writes one synthesis for the sweep, and launches a child session only for a signal that cleared or for an idea that is not a stock-picking signal. | 7 | P7.J1, P7.J3, P7.J4 |
| R5.2 | ubiquitous | THE SYSTEM SHALL carry, in `.claude/skills/explore-and-experiment-new-method/SKILL.md`, the rule that a stock-picking idea is written as a signal file and panelled before any method file, with the queue-one-idea rule and the one-per-family slate rule stated as not applying to signal ideas, and the procedure that turns a queued stock-signal idea row into a signal. | 7 | P7.J2, P7.J3 |
| R6.1 | event | WHEN `lab stage` or `lab export-json` runs THE SYSTEM SHALL write a `panel` key into `web/data/lab.json` that the snapshot test byte-compares against the export of `lab/lab.sqlite`. | 2 | P2.J1, P2.J3 |
| R6.2 | event | WHEN the owner opens `/sera/signals` THE SYSTEM SHALL show the ranked signal map with each row named by what the signal does, its verdict in everyday words, and no method ids, digests or code. | 6 | P6.J2, P6.J3 |
| R6.3 | unwanted | IF the lab database holds no panel tables or no panel rows THEN THE SYSTEM SHALL publish an empty `panel` list and `/sera/signals` SHALL render an empty state. | 2, 6 | P2.J1, P2.J2, P6.J1 |

## Scope

**In scope:** a signal registry and pure panel evaluator; two additive append-only tables and a `panel` snapshot key; `lab panel`, `lab panel-map`, `lab next-signal-id`, `lab panel-replay`; a hard-gate rule in `lab run` plus a one-chassis signal book; a `/sera/signals` page; rewritten Sera and explore skills, a runbook, the feature map.

**Out of scope:**
- Deleting any existing lab module (`control_draw`, `dressing`, `shortfall`, …). They still serve stage two and recorded methods; removing them is a separate decision once the panel has run.
- Any change to an existing `trials` row, config digest, method file, shared params class, DSR, the N policy, the test window or `lab promote`.
- **Promoting a signal book.** `lab promote` and the paper resolver resolve a promoted variant's allocator by preset id and cannot yet rebuild an `SB-*` signal book (built per signal, not a preset). Not built here because nothing can reach promotion until a signal clears the panel **and** the hard gate; it is the first follow-up when one does. Phase 7's skill text tells Sera to record a `feature-wish` insight and report it first if a signal book ever turns dev-eligible and promotable.
- Running the production replay against the shared `lab/lab.sqlite`. Phase 4 proves it on a copy; the recording run happens from the main checkout after landing (Decisions).
- A schema version bump. The two tables are additive (`store.py:612-615`).

## Shared contracts

The names below are what the reconciled plans define. Where a plan refines the draft, the plan wins and is quoted here.

**`seer_engine/lab/signal.py` (phase 1)**

```python
SIGNAL_ID = re.compile(r"S\d{4}")
MODULE_NAME = re.compile(r"s(\d{4})_[a-z0-9_]+")
MAX_LOOKBACK = 473  # labkit's smoke fixture, the same ceiling control_draw.FIXTURE_BARS names
MARKET_FIELDS = ("fundamentals", "dividends", "announcements", "series", "shares")
ScoreFn = Callable[[Mapping[str, History], "Market", AbstractSet[str], date], Mapping[str, float]]

@dataclass(frozen=True)
class Signal:
    id: str                 # "S0001"
    name: str               # plain words: what it ranks on
    family: str             # named by what it ranks on, as methods are
    source_kind: str        # method.SOURCE_KINDS
    source_ref: str
    hypothesis: str
    expected_failure: str
    lookback: int           # 1..MAX_LOOKBACK bars through data_date
    score: ScoreFn          # higher is better; a missing or NaN symbol has no opinion
    market_fields: tuple[str, ...] = ()
    idea_id: str | None = None   # the queued method idea row this signal answers, if any
    seen_keys: tuple[str, ...] = ()
    def scores(self, market, pool, data_date) -> dict[str, float]   # applies visible(); the ONLY call path

def visible(market, data_date, lookback) -> tuple[dict[str, History], Market]
def signals_package() -> ModuleType
def discover(package: ModuleType | None = None) -> dict[str, tuple[Signal, Path]]   # package seer_engine.lab.signals
source_sha = method.source_sha   # the same function object
```

`Signal.scores(market, pool, data_date)` hands `score` each symbol's last `lookback` bars dated on or before `data_date` and a `Market` rebuilt on those bars (`signal.visible`), so look-ahead through bars is impossible; `market`'s other readers are point-in-time through their own date argument. The panel (phase 1) and the signal book (phase 5) both call `Signal.scores`, never `score`.

**`seer_engine/lab/panel.py` (phase 1), pure: no DB, no clock, no files**

```python
RULE_ID = "panel-v1"
ERAS = ("all", "pre2009", "2009-2015")
ERA_SPLIT = date(2009, 1, 1)
TOP_FRACTION = 0.10      # top bucket = top_size(scored) = max(TOP_MIN, ceil(TOP_FRACTION * scored))
TOP_MIN = 10
MIN_SCORED = 30          # a month with fewer scored names is skipped ("score" mode)
MIN_PICKS = 5            # a month with fewer picks is skipped ("picks" mode)
MIN_ERA_MONTHS = 12      # an era with fewer measured months is LEFT OUT of a reading
CONTROLS = ("momentum", "beta", "volatility", "size"); MARKET = "SPY"; MODES = ("score", "picks")
Scorer = Callable[["Market", AbstractSet[str], date], Mapping[str, float]]

@dataclass(frozen=True)
class EraStats:
    era: str; months: int; mean_pool: float; mean_scored: float
    ic_mean: float | None; ic_t: float | None          # None in "picks" mode, never None in "score" mode
    spread_top: float; spread_t: float                 # ANNUALISED (x12), as a fraction
    fm_slope: float; fm_t: float                       # MONTHLY: next-month return per 1 sd of score (or per pick dummy)
    top_turnover: float                                # mean monthly share of the top bucket replaced
    # every float present is finite; a t over < 2 months or zero sd is 0.0

@dataclass(frozen=True)
class PanelReading:
    stats: tuple[EraStats, ...]    # one per ERAS entry with >= MIN_ERA_MONTHS months, ERAS order; may be empty
    picks_hash: str                # sha256 over "{decision date}:{sorted top-bucket symbols}\n" per measured month
    dropped_exits: int             # stock-months dropped for having no bar after entry
    def era(self, name) -> EraStats | None

PanelFrame(market, months)  # months: tuple[PanelMonth, ...]
def build_frame(data: ResearchData) -> PanelFrame      # built once per store; ValueError for a window ending after DEV_END
def signal_scorer(signal: Signal) -> Scorer            # returns signal.scores
def measure(frame, scorer, *, mode="score") -> PanelReading   # never raises for a scorer with no measurable month: empty stats
```

Fixed definitions (Decisions): decision dates are the last NYSE session of each month from the first month with a pool through the last whose exit is on or before `DEV_END`; the pool is the members that pass `tree_rank.SCREEN` on that date, computed with `f_factor.factor_rows` (the single-window twin of `FactorPrepared.rows_on`, equal by f_factor's contract); the forward return is a total return (dividends by ex-date) from the close of the session after the decision date to the close of the session after the next decision date; controls are 12-1 momentum, 252-session beta to SPY, 60-session volatility and log 20-session dollar volume.

**`seer_engine/lab/store.py` additions (phase 2), no schema version bump**

```sql
CREATE TABLE IF NOT EXISTS panel_signals (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK (kind IN ('signal','replay')),
    name TEXT NOT NULL, family TEXT NOT NULL, hypothesis TEXT NOT NULL, expected_failure TEXT NOT NULL,
    source_kind TEXT NOT NULL, source_ref TEXT NOT NULL DEFAULT '',
    method_id TEXT REFERENCES methods(id), source_sha TEXT NOT NULL, created TEXT NOT NULL,
    CHECK (kind <> 'signal' OR (id GLOB 'S[0-9][0-9][0-9][0-9]' AND method_id IS NULL)),
    CHECK (kind <> 'replay' OR (method_id IS NOT NULL AND substr(id, 1, length(method_id) + 1) = method_id || '-')));
CREATE TABLE IF NOT EXISTS panel_results (
    signal_id TEXT NOT NULL REFERENCES panel_signals(id), rule_id TEXT NOT NULL,
    store_role TEXT NOT NULL CHECK (store_role IN ('dev','survivorship')), store_fingerprint TEXT NOT NULL,
    era TEXT NOT NULL CHECK (era IN ('all','pre2009','2009-2015')), months INTEGER NOT NULL CHECK (months >= 1),
    mean_pool REAL NOT NULL, mean_scored REAL NOT NULL,
    ic_mean REAL, ic_t REAL, spread_top REAL NOT NULL, spread_t REAL NOT NULL,
    fm_slope REAL NOT NULL, fm_t REAL NOT NULL, top_turnover REAL NOT NULL CHECK (top_turnover BETWEEN 0 AND 1),
    picks_hash TEXT NOT NULL, git_sha TEXT NOT NULL, measured TEXT NOT NULL,
    PRIMARY KEY (signal_id, rule_id, store_fingerprint, era),
    CHECK ((ic_mean IS NULL) = (ic_t IS NULL)));
```

Both append-only by the usual trigger pair (non-empty-text CHECKs omitted above; phase 2 Step 1 has them). A signal's id is `S0001`; a replay's id is the candidate id it replays (`M0614-V1`), with `method_id` set. `store_fingerprint` is the store's **full** `ResearchData.fingerprint` (the manifest's `"fingerprint"`, what `trials.store_fingerprint` holds), not its price fingerprint. API:
- `PANEL_KINDS`, `PANEL_STORE_ROLES`, `PANEL_ERAS` (duplicates `panel.ERAS`), `PanelSignalRow`, `PanelResultRow` (+ `PanelResultRow.from_era(stats, *, signal_id, rule_id, store_role, store_fingerprint, picks_hash, git_sha, measured)`), `PANEL_SIGNAL_COLUMNS`, `PANEL_RESULT_COLUMNS`.
- `insert_panel_signal(conn, row) -> bool`: True inserted; **False** (writes nothing, no raise) for an existing id with the same `source_sha`; `LabError` for an existing id with a different sha, and for a replay that is not a dev trial of its method. Does not commit.
- `insert_panel_results(conn, rows) -> int`: the number inserted; a repeated primary key is **skipped**; `LabError` before anything is written for an unknown signal, a non-finite number, half an IC pair, an IC on a replay, an unknown era or role, a fingerprint already recorded under the other role, or eras of one reading with different `picks_hash`. Does not commit.
- `panel_signals(conn) -> list[dict]` (by id), `panel_results(conn, signal_id=None) -> list[dict]` (oldest first), `has_panel(conn, signal_id, rule_id, store_fingerprint) -> bool`, `next_signal_id(conn, taken=()) -> str` (one above every recorded signal id and every signal id in `taken`; `lab next-signal-id` passes every discovered signal file's id). Every reader answers `[]` / `False` / `"S0001"` when the tables are absent.

**`seer_engine/lab/panel_verdict.py` (phase 2)**

```python
RULE_ID = "panel-v1"   # duplicates panel.RULE_ID; phase 3's test pins the two equal
FDR = 0.10
@dataclass(frozen=True)
class Verdict:
    signal_id: str; clears: bool; q: float | None; reasons: tuple[str, ...]; twin_of: str | None
Readings(dev, survivorship)
def one_sided_p(t, months) -> float          # Student's t on months - 1 df, written on math
def bh_qvalues(pvalues) -> list[float]
def current_dev_fingerprint(conn) -> str | None
def readings(conn, *, dev_fingerprint=None) -> dict[str, Readings]
def published(conn, *, dev_fingerprint: str | None = None) -> dict[str, Verdict]
# reason sentences: UNMEASURED_REASON, TWIN_REASON, SLOPE_REASON, CHANCE_REASON,
# RECENT_MISSING_REASON, RECENT_REASON, SURVIVORSHIP_MISSING_REASON, SURVIVORSHIP_REASON
```

A panel clears when all three hold: its dev whole-window controlled slope is positive and its one-sided p-value survives Benjamini-Hochberg at `FDR` across every distinct `picks_hash` recorded on that dev fingerprint (the first-recorded panel of a pick set carries it; later ones are twins and never clear); its dev 2009-2015 top-minus-pool spread is positive; its survivorship whole-window controlled slope is positive. A **missing** dev `2009-2015` row or survivorship `all` row (fewer than 12 months, or never measured) fails its condition with its own plain-words reason. `reasons` names each failed condition in plain words. The verdict is computed on read, never stored.

**Snapshot (phase 2):** `SNAPSHOT_VERSION = 9`; a new last top-level key
`"panel": {"rule": "panel-v1", "fdr": 0.1, "signals": [{"id", "kind", "name", "family", "methodId", "clears", "q", "reasons", "twinOf", "dev": {"all": {...}|null, "pre2009": {...}|null, "recent": {...}|null} | null, "survivorship": {...} | null}]}`
where era `2009-2015` is published under `recent` and each era object is `{"months", "ic", "icT", "spread" (annualised), "spreadT", "slope" (monthly), "slopeT", "turnover"}`. `dev` is null for a panel not measured on the current dev store. Signals are sorted by dev whole-window slope, unmeasured last, ties by id. A replay's `name` is its method's own `methods.name`. Web types: `LabPanel`, `LabPanelSignal`, `LabPanelStore`, `LabPanelEra`, `PanelKind`, `PANEL_KINDS` (pinned to `store.PANEL_KINDS`).

**CLI (phases 3 and 4), flat names like every other `lab` subcommand**
- `lab panel SNNNN [SNNNN ...] | --pending  [--store DIR] [--sv-store DIR] [--jobs J]`
- `lab panel-map [--top K] [--kind signal|replay|all]` (verdict column `clears` / `no`, a `why not:` line under a `no`; empty replay state "no replay panel recorded yet"; headers mark slopes `/mo` and spreads `/yr`)
- `lab next-signal-id` (the id alone on stdout)
- `lab panel-replay [MNNNN ...] [--family-like PATTERN] [--limit N] [--store DIR] [--sv-store DIR] [--jobs 1|2]` (default family `stock-%`; `--limit` counts previously skipped arms)

**`seer_engine/lab/panel_run.py` (phase 3), shared with phase 4:** `DEV`, `SURVIVORSHIP`, `Subject(row, scorer, mode)`, `StorePair(dev_dir, sv_dir, dev_fingerprint)`, `StoreRun(role, fingerprint, readings)`, `check_stores(dev_dir, sv_dir, *, command) -> StorePair`, `load(store_dir, *, role, command)`, **`open_store(conn, pair, role, *, command) -> ResearchData`** (the one loader: `load` plus, for dev, the D10 pin and the manifest-fingerprint check), `measure_stores`, `has_whole_window(reading)`, `record(conn, subject, dev_run, sv_run, *, git_sha, measured) -> bool`, `Counts.read(conn)`, `footer(conn, before, *, lead)`, `panel_map`, `format_map`, `next_signal_id(conn)`. Phase 4 runs its own grouped store loop (`lab/panel_replay.py`) but loads through `open_store` and writes through `record`.

**Stage-two seam (phase 5)**
- `method.SIGNAL_ID` (restated; pinned equal to `signal.SIGNAL_ID`), `method.PANEL_EXEMPT_KINDS = ("chassis", "control-study", "market")`; `Method` gains `signal: str | None = None` and `panel_exempt: str = ""` (begins `<kind>:` and a reason; never both).
- `seer_engine/lab/signal_book.py`: `WIDTH = 20`, `SWITCH = ("SPY", 200)`, `ID_PREFIX = "SB-"`, `BookParams(trend)`, `SignalBook` / `MarketSignalBook` (MarketAware when the signal declares `market_fields`), `book_allocator(signal)` (allocator id `"SB-" + signal.id`), `standard_candidates(signal, method_id, added) -> (<mid>-N20, <mid>-N20-NOGATE)` — the one chassis: `MONTHLY_HOLD_FRAC_GOTRADE`, twenty equal slots from `tree_rank.SCREEN`'s pool ranked by `Signal.scores`, one arm behind the SPY 200-day switch and one never stepping aside.
- `hardgate` (D21): `picks_members(c)`, `dev_store_dir()`, `dev_store_fingerprint(store_dir=None)`, `panel_refusal(conn, method, candidates, *, dev_fingerprint=None) -> str | None`, `panel_gate(...)` raising `LabError`; called last in `runner.preflight(..., dev_fingerprint=None)`; `run_method` passes `data.fingerprint`.

## Invariants

1. The tree builds and its own tests pass at the end of every phase: `ruff check engine`, the phase's own engine test files, and for web phases `npx tsc --noEmit && npm test`.
2. No existing `trials` row, config digest, `methods.source_sha`, method file under `lab/methods/`, shared params class or `backtest/registry.py` entry changes. `test_every_recorded_configuration_still_digests_to_its_recorded_digest` stays green untouched.
3. No phase runs `lab run`, `lab test`, `lab promote`, `lab stage`, or any writing `lab` command against `/home/miftah/seer/lab/lab.sqlite`. Every engine command a phase runs sets `SEER_LAB_DB` to a scratch copy or to the worktree's own `lab/lab.sqlite`.
4. Nothing reads `engine/.research-test`. The panel accepts a store only when its manifest declares the dev window.
5. The research stores are read from the main checkout (`SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research`, `SEER_SV_STORE=/home/miftah/seer/engine/.research-sv`); a worktree never rebuilds one.
6. In the worktree, python is `PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python`; pytest runs with `-n 2` at most. At most two phase sessions run at once on this machine (five took WSL down twice).
7. `lab/lab.sqlite` and `web/data/lab.json` are derived artifacts. **No phase branch carries a changed `lab/lab.sqlite`**: phase 2 exports `web/data/lab.json` in the worktree and restores the DB with `git checkout -- lab/lab.sqlite`. At landing, take `main`'s `lab/lab.sqlite` untouched as it is at that moment, run `lab export-json` on it with the landed code, and commit `web/data/lab.json` (and `lab/lab.sqlite` only if its bytes changed) by explicit path. Never merge either file; never `lab stage` from a worktree.
8. No new runtime dependency. Rank correlation, the regression and the correction are written on numpy.
9. Commit explicit file paths only; other sessions share the main checkout.
10. Text the owner reads (the `/sera/signals` page, sweep syntheses) uses plain language: no ids, digests or code. argparse help strings contain no bare `%`.
11. **Known baseline failure.** `engine/tests/test_lab_hardgate.py::test_the_buy_signal_fires_on_the_promoted_arm_and_the_set_moved_both_ways` was reported failing on base `b0652d2` by the phase-5 planner (not re-measured by the reconciler). A phase that sees it fail re-runs that test file alone on the untouched base before blaming itself, and does not "fix" it.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Signal registry and the pure panel evaluator | R1, R2 | `engine/lab` | 8 | — | HARD | `.workflows/plan/sera-signal-panel/phase-1.md` | `P1-ENG-6CGV` | — |
| 2 | Panel record: tables, published verdict, snapshot key | R2, R3, R6 | `engine/lab`, `web/lib/sera` | 11 | — | HARD | `.workflows/plan/sera-signal-panel/phase-2.md` | `P1-ENG-1MOB` | — |
| 3 | `lab panel`, `lab panel-map`, `lab next-signal-id` | R1, R2, R3, R4 | `engine/commands`, `engine/lab` | 5 | 1, 2 | NORMAL | `.workflows/plan/sera-signal-panel/phase-3.md` | `P1-ENG-7F8X` (done 2026-11-14) | — |
| 4 | Replay the recorded stock-signal methods | R3 | `engine/lab`, `engine/commands` | 5 | 3 | HARD | `.workflows/plan/sera-signal-panel/phase-4.md` | `P1-ENG-3AY5` | — |
| 5 | The panel gate in `lab run` and the one-chassis signal book | R4 | `engine/lab` | 12 | 1, 2 | HARD | `.workflows/plan/sera-signal-panel/phase-5.md` | `P1-ENG-KGFN` (done 2026-11-14) | — |
| 6 | The signal map on `/sera/signals` | R6 | `web` | 8 | 2 | NORMAL | `.workflows/plan/sera-signal-panel/phase-6.md` | `P1-WEB-4JM6` | — |
| 7 | Skills, runbook and docs for the two-stage flow | R5 | `.claude/skills`, `docs` | 6 | 3, 4, 5 | NORMAL | `.workflows/plan/sera-signal-panel/phase-7.md` | `P1-ROOT-F485` | — |

Phase 2 spans three Rs and cannot be split: the tables (R2), the twin rule inside the published verdict (R3.2) and the snapshot key (R6.1, R6.3) are one record with one byte-compared export, and a tree holding half of it fails the snapshot test. Phase 3 serves R3 through the printing half of R3.2 (`lab panel-map`'s twin column), which phase 2's handoff assigned to it.

`Depends on` is unchanged from the draft and verified against the plans' imports: 3 imports `panel`, `signal` (1) and `store`, `panel_verdict` (2); 4 imports `panel_run` (3); 5 imports `signal` and `panel.RULE_ID` (1) and the panel store API and `panel_verdict` (2), and none of phase 3's code; 6 imports only phase 2's web types; 7 names commands and files from 3, 4 and 5 and appends to phase 4's runbook.

### Phase 1 — Signal registry and the pure panel evaluator
**Satisfies:** R1, R2
**Owns:** `lab/signal.py`, `lab/signals/__init__.py`, two seed signals (`s0001` twelve-minus-one momentum as the known-positive check, `s0002` a hash-order draw as the known-null check), `lab/panel.py`, `.claude/skills/explore-and-experiment-new-method/signal_template.py`, `tests/test_lab_signals.py` (purity walk, smoke run on `labkit.smoke_market`, id uniqueness, perturb-the-future look-ahead check, negative tests), `tests/test_lab_panel.py` (60-member synthetic market from 2005: planted-signal recovery, null signal, total return with a dividend, a name whose bars stop, era split, picks mode incl. too few picks -> empty stats, hash stability).
**Does not touch:** `store.py`, `commands/lab.py`, `method.py`, `runner.py`, anything under `web/`.
**Exit criteria:** `discover()` returns both seed signals; `measure` recovers a planted signal and reads a null one as null on a synthetic market; both test files pass; J4/J5 print three finite era lines per seed signal on both real stores.

### Phase 2 — Panel record: tables, published verdict, snapshot key
**Satisfies:** R2, R3, R6
**Owns:** the two tables and their API in `store.py`; `lab/panel_verdict.py`; the `panel` snapshot key and `SNAPSHOT_VERSION = 9`; `tests/test_lab_panel_record.py`; the version and key-list asserts in `tests/test_lab_snapshot.py` and `tests/test_lab_books.py`; the `PANEL_KINDS` web==engine pin in `tests/test_lab_gate_wording.py`; `web/lib/sera/types.ts` (`version: 9`, `LabPanel` types), `web/lib/sera/lab.test.ts`, `web/app/sera/overview.test.ts`; the regenerated worktree `web/data/lab.json`; the proof script `.workflows/plan/sera-signal-panel/phase-2-drive.py`. `lab/lab.sqlite` is exported from and then restored by `git checkout`: the branch never carries it (invariant 7).
**Does not touch:** `panel.py`, `signal.py`, `commands/lab.py`, `web/lib/sera/fixture.ts`, any page or component under `web/app` other than the one test literal.
**Exit criteria:** rows insert once and never update; `published` returns the verdicts the contract defines, twins collapsed; the snapshot test, `tsc` and vitest are green with an empty `panel.signals`; `lab/lab.sqlite` is byte-identical to the base.

### Phase 3 — `lab panel`, `lab panel-map`, `lab next-signal-id`
**Satisfies:** R1, R2, R3, R4
**Owns:** the three subcommands in `commands/lab.py` (parser, handler, `_HANDLERS`, module docstring); `lab/panel_run.py` (incl. `open_store`, shared with phase 4); `tests/test_lab_panel_cli.py` (incl. the `RULE_ID`/`ERAS` equality pin between phases 1 and 2; real-evaluator tests on a 40-member market from 2005); `.claude/skills/verify-seer/features/signal-panel.md` and its README row.
**Does not touch:** `panel.py` and `store.py` beyond calling them; `runner.py`; `hardgate.py` beyond calling `pin_dev_store`.
**Exit criteria:** on a scratch DB and the real stores, `lab panel S0001 S0002` records 2 signals x 2 stores x up to 3 eras, a second run records nothing new, an uncommitted signal and a non-dev store each exit 2, `panel-map` shows a twin in its twin-of column, and `lab status`'s N is the same before and after.

### Phase 4 — Replay the recorded stock-signal methods
**Satisfies:** R3
**Owns:** `lab/panel_replay.py` (candidate -> picks scorer through `prepare_for` and `targets_prepared` with `held=frozenset()`, fixed `holds()` instruments and non-pool names removed, months with fewer than `MIN_PICKS` skipped by `measure`; stores loaded through `panel_run.open_store`; row name = the method's own name); `lab panel-replay` in `commands/lab.py`; `tests/test_lab_panel_replay.py`; `docs/runbooks/signal-panel.md` (operator half, timings measured in this phase); an appended `## Replay` section in `features/signal-panel.md`.
**Does not touch:** any file under `lab/methods/`; `trials`; the three subcommands phase 3 added except to sit beside them; `panel_run.py`.
**Exit criteria:** on a scratch copy of the lab DB and the real stores, `lab panel-replay` over every `stock-%` method completes, `lab panel-map` prints the ranked map with twins collapsed, and the sha256 of every `trials` row and of `methods.source_sha` is unchanged.

### Phase 5 — The panel gate in `lab run` and the one-chassis signal book
**Satisfies:** R4
**Owns:** `Method.signal`, `Method.panel_exempt`, `method.SIGNAL_ID`, `method.PANEL_EXEMPT_KINDS` in `lab/method.py`; `lab/signal_book.py` (scores through `Signal.scores`); the D21 rule in `hardgate.py` and its call in `runner.preflight`; `method_template.py`; `tests/test_lab_panel_gate.py`, `tests/test_lab_signal_book.py`; the `panel_exempt` fixture edits in `tests/test_lab_exposure.py`, `tests/test_lab_gate_probe.py`, `tests/test_lab_survivorship.py`, `tests/test_lab_yardstick_gate.py` (no other phase edits them); the refusal line and gotcha in `features/lab-cli.md`.
**Does not touch:** `commands/lab.py`; `store.py`; any recorded method file.
**Exit criteria:** `lab run` on a scratch DB refuses an unpanelled member-picking method with exit 2 and an unchanged trial count, refuses a signal method with a hand-written treatment arm, accepts a signal method built from `standard_candidates` whose signal clears, and accepts an exempt chassis method; the full engine suite is green apart from invariant 11's baseline.

### Phase 6 — The signal map on `/sera/signals`
**Satisfies:** R6
**Owns:** `web/app/sera/signals/page.tsx`, `view.ts`, `view.test.ts`, `signals.module.css`; the seventh tab in `web/components/sera/SeraNav.tsx` and `SeraNav.module.css`; the "six-tab bar" comment in `web/components/sera/PageHeader.tsx`; `.claude/skills/verify-seer/features/sera.md`.
**Does not touch:** `types.ts` beyond importing the phase-2 types; `fixture.ts`; `features/README.md`; the engine.
**Exit criteria:** the page renders an empty state on the committed snapshot and a ranked map on a fixture snapshot, at 390 and 1280 wide in both themes, with no id, digest or code in the owner-visible text (the committed-snapshot pin covers `reasons`; fixture tests cover every printed string); a measured store with a missing era reads "not enough months to say".

### Phase 7 — Skills, runbook and docs for the two-stage flow
**Satisfies:** R5
**Owns:** `.claude/skills/sera-the-explorer/SKILL.md`, `.claude/skills/explore-and-experiment-new-method/SKILL.md`, the one paragraph in `.claude/skills/redo-sera-experiments/SKILL.md` that mints a twin (it now carries `panel_exempt`), `CLAUDE.md` (Layout, The lab, Experiment protocol), `README.md`, and the two Sera-facing sections appended to `docs/runbooks/signal-panel.md` ("A sweep, step by step", "The first replay").
**Does not touch:** any code; `signal_template.py`; `method_template.py`; any feature-map file.
**Exit criteria:** both skills describe the sweep, the stage-two launch for a cleared signal, the unchanged path for non-signal ideas, the routing of queued stock-signal idea rows (wrappers judged by the host's replay verdict), the first replay run without `--limit`, and the `feature-wish` step for a promotable signal book; every command they name exists with those flags (J3).

## Reconciliation Log

| # | Conflict | Kind | Phases | Resolution |
|---|---|---|---|---|
| 1 | Which fingerprint a panel is keyed on | contract drift | 2, 3, 4, 5 | Full `ResearchData.fingerprint` (coordinator decision 1). Phases 3-5 already used it; phase 2's table comment, Requires and the index contract now say so; phase 5's "reconciler to confirm" handoff closed. |
| 2 | `fm_slope` units unstated; spread vs slope easy to mix | contract drift | 1, 2, 3, 6 | Slope monthly, spread annualised (decision 2): phase 2 `PanelResultRow` docstring and `types.ts` comment, phase 3 column headers (`slope/mo`, `sprd/yr`) and map header line, phase 6 `controlled()` comment (slope never printed as a figure; yearly = x12). |
| 3 | An era with < 12 months yields no row; downstream assumed rows | unmet assumption | 1, 2, 6 | Decision 3: phase 2 missing-row reasons reworded ("not enough months"), snapshot `dev`/eras nullable in the contract; phase 6 Requires corrected to nullable and `readings()` renders "not enough months to say", with a new vitest case. |
| 4 | Picks mode with no measurable month: raise or empty? | unmet assumption | 1, 4 | Decision 4: phase 1 `measure` docstring and contract deviation 5 state "empty stats, never raises" (its test already pinned it); phase 4 reports TOO_FEW, detail reworded to cover the 12-month rule. |
| 5 | Duplicate-key handling: phase 4 caught IntegrityError, phase 2 skips | duplicate work | 2, 3, 4 | Decision 5: phase 2's skip is the one mechanism. Phase 4's try/except and the `NOT_WRITTEN` category removed (code, contract, feature map, runbook table); phase 3 handoff (d) marked resolved; phase 4 Requires states the same-sha / different-sha rule. |
| 6 | `next_signal_id` computed twice (phase 3 re-implemented the file max) | duplicate work | 2, 3, 7 | Decision 6: `panel_run.next_signal_id` is `store.next_signal_id(conn, taken=signal.discover())`; phase 3 Requires updated; phase 7's `ls $SIGNALS` workaround removed from the skill and runbook. |
| 7 | Does phase 2's branch carry `lab/lab.sqlite`? | file collision | 2, index | Decision 7: invariant 7 rewritten; phase 2 Owns, Step 9 rationale and landing handoff now say export JSON, restore DB by `git checkout`, at landing commit JSON (and DB only if bytes changed) by explicit path. |
| 8 | `RULE_ID` / `ERAS` defined in both phase 1 and phase 2 | duplicate work | 1, 2, 3 | Decision 8: kept duplicated for independence; phase 3 adds `test_the_record_and_the_evaluator_agree_on_the_rule_and_the_eras` (Files row, Step 6 prose, J5). |
| 9 | Store loading duplicated (`panel_replay._open` vs `measure_stores`) | duplicate work | 3, 4 | Decision 9: `panel_run.open_store(conn, pair, role, *, command)` added in phase 3 and used by `measure_stores`; phase 4's `_open` deleted, calls `open_store`; unused `hardgate`/`research` imports dropped. |
| 10 | Signal book called `panel.signal_scorer`; phase 1 handoff asks for `Signal.scores` | contract drift | 1, 5 | Decision 10: `signal_book` calls `self.signal.scores(market, pool, d)`, `panel` import dropped; phase 5 Requires names the real phase-1 method and its `visible` cut. Phases 3/4 checked against `PanelFrame(market, months)`, `build_frame`, `signal_scorer`, `measure` and `factor_rows`: consistent; index reuse line fixed to `factor_rows`. |
| 11 | Replay row name (`name: rationale`) and phase 6's no-ids pin on names | contract drift | 4, 6 | Decision 11: phase 4 records `method.name` (test updated); phase 6's committed-snapshot pin covers `reasons` only; fixture tests unchanged; `PageHeader.tsx` already in phase 6's Files. |
| 12 | Wrapper idea routing: re-host-or-drop vs drop | contract drift | 7 | Decision 12: host cleared -> child idea with `panel_exempt="chassis: ..."`; host not cleared -> `lab drop`. Both skills edited. `--sweep K` (default 12, 0 skips) and `<num-methods>` = children kept. |
| 13 | Promoting an `SB-*` signal book has no owner | gap | 5, 7, index | Decision 13: added to Out of scope with the reason; phase 7 Sera step 6 records a `feature-wish` insight and reports it first; phase 5 handoff reworded. Not an open question. |
| 14 | Pre-existing red test on base | gap | 5, index | Decision 14: invariant 11 added; phase 5 Verification points to it. |
| 15 | Phase 7 guessed command flags, refusal text, panel-map tokens | contract drift | 7 | Decision 15: Requires now `--jobs J` (panel) / `--jobs 1|2` (replay), exemption prefixes from `PANEL_EXEMPT_KINDS`, the gate's refusal phrases quoted in explore step 6, `clears`/`no` + `why not:` and "no replay panel recorded yet" quoted. Feature-map owners verified: `signal-panel.md` 3 then 4 (4 quotes 3's end), `README.md` 3, `lab-cli.md` 5, `sera.md` 6; `commands/lab.py` 3 then 4; the explore skill folder 1/5/7. |
| 16 | `lab panel-replay --limit N` counts previously skipped arms, so Sera's "repeat batches until one records nothing new" could stop with work left | gap | 4, 7 | Phase 7 step 2b and "The first replay" run the replay without `--limit` and stop when a run records 0; phase 4's runbook explains `--limit` is for the first timing batch only. |
| 17 | Phase 4 runbook said commit the `lab stage` output "by explicit path"; phase 7 says no pathspec | contract drift | 4, 7 | Phase 4's last section becomes "Who runs the production replay", pointing to phase 7's "The first replay", which commits with no pathspec (rung 6: `lab stage` commits by index). Headings checked: no collision. |
| 18 | Phase 3/4 real-evaluator fixtures started 2007: pre-2009 era exactly `MIN_ERA_MONTHS` | gap (fragile) | 3, 4 | Both fixtures start 2005 (about 36 pre-2009 months). Checked: 40 smoke members all pass F4's screen (volume x price far above 20M), so `MIN_SCORED` 30, `TOP_MIN` 10 and `MIN_PICKS` 5 hold; S0001's 253-bar lookback is not used by these fixtures. |
| 19 | R3.2's "show ... in `lab panel-map`" half was printed by phase 3 but owned only by phase 2 | untraced (by hand) | 2, 3 | Phase 3 now owns R3.2 too (Satisfies R3, Criteria R3.2, J5 runs the twin test); Requirements and criteria tables updated. |
| 20 | Index Files counts and Owns lines drifted from the plans (phase 2 named `fixture.ts`, omitted `test_lab_gate_wording.py` and the drive script; phase 5 fixtures) | contract drift | index | Phase table counts 8/11/5/5/12/8/6; Owns lines rewritten from each plan's Files table. |
| 21 | Phase 5's optional handoff: pass `dev_fingerprint` from `commands/lab.py:_run` | ordering/ownership | 3, 5 | Not adopted: phase 3 owns `commands/lab.py` and only adds blocks; `run_method`'s check (with `data.fingerprint`, before any simulation) is authoritative. Noted in phase 5. |
| 22 | Checks (b)-(e) | verification | all | (b) phase 5's four fixture files are in its Files table and no other phase edits them. (c) phase 2 alone: the only hand-built `LabSnapshot` is `overview.test.ts`'s `snap()`, updated; phase 6 alone adds files and derives types from `LabSnapshot['panel']`; `how/view.test.ts` uses only `LabSnapshot['data']`. (d) `Depends on` unchanged, every edge proven by an import or an appended file. (e) every plan uses scratch/verify copies, main-checkout stores, no `.research-test`, pytest `-n 2` or less. |
| 23 | Round 2: phase 6 Step 2 prose and its principles line still said the committed-snapshot pin covers every `name` and reason; its code (and Decision 11) pins `reasons` only | contract drift | 6 | Both prose lines rewritten to "reasons only"; code unchanged. |
| 24 | Round 2: phase 4 Goal and `panel_replay` module docstring still said the sweep "runs in `--limit` batches" | contract drift | 4, 7 | Reworded to the reconciled rule: a full sweep runs with no `--limit` until it records 0; `--limit` times a first batch only. |
| 25 | Round 2 verification (no edit needed) | verification | 1-7 | `open_store(conn, pair, role, *, command)` matches at `measure_stores` and phase 4's `_store_pass`; phase 4 tests patch `research.load_store`, which `open_store` reaches through `load`. `store.next_signal_id(taken=...)` iterates `discover()`'s dict keys (signal ids). No `NOT_WRITTEN`/IntegrityError left in phases 4 or 7. Replay `name=method.name` in phase 4 code and test; phase 2 exports `panel_signals.name`. `signal_book` calls `self.signal.scores(market, pool, data_date)`; phase 5 imports `panel.RULE_ID` only inside `hardgate.panel_refusal` (phase 1, so `Depends on: 1, 2` holds). Missing eras: `published`, `readings`, `_snapshot_panel*`, `types.ts`, `format_reading`, `panel_map`/`format_map` and phase 6 `readings()` all use `.get`/null checks. Units consistent in phase 2 docstring/types, phase 3 headers, phase 6. Phase 3 Criteria/Files/J5 agree with the criteria table. Phase 7's commands, flags, prefixes, the D21 refusal phrases and "no replay panel recorded yet"/"recorded 0 replay panel(s)" exist verbatim in phases 3-5. Fixtures from 2005-01-03: the first pool needs 253 bars (about late Jan 2006), so pre-2009 has about 35 measured months of 40 scored names (`_last_close`, lookback 1) or 6 picks (`Toy`, 6 of 40), above `MIN_ERA_MONTHS`, `MIN_SCORED` and `MIN_PICKS`. |

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| Where panel results live | `lab/lab.sqlite`, two additive append-only tables, no schema version bump; a `panel` key in the snapshot | 6: convention (`store.py:612-615`, the `trial_yardstick` precedent) |
| How to extract a ranking from an existing Allocator | Do not extract a score. Call the candidate's own `targets_prepared` at each month end with nothing held and treat the returned names as a pick set; report spread and controlled slope, leave rank correlation empty | 5: user's raw input ("without changing any config digest or frozen record") |
| A replay month in which the allocator's switch is off | Skipped and counted; the panel measures the picking, not the timing | 4: the index's Why (the wrapper dominates the signal) |
| Do panel looks count against the luck gate's N | No. The panel carries its own correction; a cleared signal that becomes a method enters N as any method does | 4: Why; N is defined over `trials` |
| The correction's population | One population: every distinct pick set ever recorded on the current dev store, replays included | 5: raw input ("across all registered signals"), read conservatively |
| The panel bar | Benjamini-Hochberg at 0.10 on the dev controlled slope, positive 2009-2015 spread, positive survivorship slope | 5: raw input lists exactly these three readings |
| Where the bar is enforced | `lab run` (and `--amend`), in `runner.preflight`, exit 2. `lab idea` stays free: an idea row costs nothing and is how a queued idea waits for its signal | 5: raw input ("lab idea / lab run refusal, exit 2") |
| Which methods the gate binds | Any method with an arm about to run that is a bracket `Strategy` or an allocator whose `uses_members` is True, unless it carries `panel_exempt` beginning `chassis:`, `control-study:` or `market:` | 4: Requirements R4 ("only signals that clear") |
| Size control | Log 20-session dollar volume; `Market.market_value` covers about 57% of dev member-days | 6: convention (the yardstick sizes by dollar volume) |
| Forward return timing | Next-session close to next-session close, dividends by ex-date; a name with no bar at exit takes its last close, one with no bar after entry is dropped and counted | 6: convention (the book trades the session after the decision) |
| Who runs the production replay | Not this plan set. Phase 4 proves it on a copy; Sera's rewritten preflight runs it once from the main checkout when the panel holds no replay rows | 1: invariant 3 |
| How a whole-space "no" is recorded | As the sweep's synthesis plus one `risk` insight naming the universe as closed, written by Sera from `lab panel-map`; no new record type | 6: convention (journal kinds) |
| Deleting the book-level diagnostic modules | Not in this set | 3: nothing in any phase removes a caller |
| Fingerprint the panel is keyed on | The store's full `ResearchData.fingerprint` (what `trials.store_fingerprint` holds), not the price fingerprint; a refreshed optional file means a re-panel, which is cheap | [6: convention] (coordinator decision 1) |
| Units of `fm_slope` and `spread_top` | `fm_slope` is a monthly next-month return per 1 sd of score (or per pick dummy); `spread_top` is annualised; a yearly slope is x12 and the two are never printed as one unit | [3: phase 1's code blocks] (decision 2) |
| An era with fewer than 12 measured months | No row; `published` fails a missing dev 2009-2015 or survivorship whole-window row with a plain-words reason; snapshot `dev`, `survivorship` and era objects may be null; the page says "not enough months to say" | [3: phase 1's code blocks] (decision 3) |
| Picks mode with no month of `MIN_PICKS` picks | `measure` returns empty stats and never raises; phase 4 reports the arm skipped (too few picks) and records nothing | [2: phase 4 exit criteria] (decision 4) |
| Repeat-insert semantics | `insert_panel_signal`: False for same id and sha, `LabError` for a different sha; `insert_panel_results`: skips a repeated key, returns the number inserted; neither commits. Phase 4's IntegrityError catch removed as dead | [3: phase 2's code blocks] (decision 5) |
| Next signal id | `store.next_signal_id(conn, taken=())`; `lab next-signal-id` passes every discovered signal file's id | [3: phase 2's code blocks] (decision 6) |
| Does phase 2's branch carry `lab/lab.sqlite` | No: export `web/data/lab.json` in the worktree, restore the DB by `git checkout`; at landing export on `main`'s DB and commit the JSON (and the DB only if its bytes changed) by explicit path; never `lab stage` from a worktree | [3: phase 2's code blocks] (decision 7) |
| `RULE_ID` / `ERAS` defined twice | Duplicated as `panel_verdict.RULE_ID` / `store.PANEL_ERAS` so phase 2 stays independent of phase 1; phase 3 owns the equality test; the snapshot publishes `2009-2015` as `recent` | [3: phase 2's code blocks] (decision 8) |
| Replay's store loop | Its own grouped loop (phase 4), not `measure_stores`; the shared load + D10 pin + fingerprint check is `panel_run.open_store` in phase 3, which phase 4 calls | [phase 4's stated reasons; 6: one loader] (decision 9) |
| How the signal book scores | Through `Signal.scores(market, pool, d)` (phase 1's real method, applying `visible`), MarketAware when the signal declares `market_fields`; still passes allocatorkit's P4 identity and no-look-ahead checks | [3: phase 1's code blocks] (decision 10) |
| A replay row's `name` | The method's own `methods.name`; "(variant k of n)" on the page tells arms apart; the committed-snapshot no-ids pin covers `reasons` only | [5: user input "named by what the signal does"; 6] (decision 11) |
| A queued idea that wraps another method's picks | Judged by the host's replay verdict: host cleared -> child-session idea with `panel_exempt="chassis: ..."`; host did not clear -> `lab drop` with the plain reason. Sera's `--sweep K` (default 12, 0 skips) accepted; `<num-methods>` counts children only | [5: user input "route the 138 queued stock-signal ideas through the panel"] (decision 12) |
| Promoting an `SB-*` signal book | Out of scope; Sera records a `feature-wish` insight and reports it first if one ever turns dev-eligible and promotable | [4: Scope] (decision 13) |
| A red test on the untouched base | Invariant 11: re-run the file alone on the base before blaming the phase; never "fix" it | [6: convention] (decision 14) |
| Command names, flags, exemption prefixes and refusal text in the docs | Exactly as phases 3, 4 and 5 define and print them | [3: phases 3-5's code blocks] (decision 15) |
| How Sera runs the first replay | One run with no `--limit`, re-run until it records 0; `--limit` only for a first timing batch | [3: phase 4's code: `unfinished` keeps skipped arms first in trial order] (reconciler) |
| How the replay's `lab stage` is committed | `git commit -m` with no pathspec, as Sera's skill says; phase 4's runbook defers to phase 7's section | [6: convention — `lab stage` commits by index] (reconciler) |

## Open Questions

_None._

## Rollback

Per phase: revert the phase's commit; phases 1, 3, 4, 6 and 7 add files and subcommands nothing else depends on at runtime (revert 4 before 3, and 7 before 3, 4 and 5). Phase 5 is the only one that changes what `lab run` accepts; reverting it restores the old behaviour with no data change. Phase 2's tables are additive and append-only: after a revert they remain in `lab.sqlite` unread, and `lab export-json` on the reverted code regenerates the version-8 snapshot. As a whole: revert the merge, re-export, commit both derived files.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f .workflows/plan/SERA_SIGNAL_PANEL_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows, resumable on any machine:

    /analyze-orchestrator -f .workflows/plan/SERA_SIGNAL_PANEL_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan .workflows/plan/SERA_SIGNAL_PANEL_PLAN.md
