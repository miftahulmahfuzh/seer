> Adopted from `EODHD_SURVIVORSHIP_MARKET_PLAN.md` phase 4. Source: `.workflows/plan/eodhd-survivorship-market/phase-4.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 4: `lab survivorship` report command

**Plan set:** `EODHD_SURVIVORSHIP_MARKET_PLAN.md`
**Analysis:** `20261010-181548-E7HD_code_analyzer.md`
**Satisfies:** R4 — a report-only measurement that reruns a recorded method's variants on the survivorship-check store beside the dev store (yearly return vs SPY, max DD, PF, DSR inputs, 2009-2015 era, walk-forward folds); no trial, N unchanged; journaled
**Depends on:** Phase 1 (`ResearchData.purpose`, `research.SV_STORE_DIR`, the built SV store), Phase 3 (edits `commands/lab.py` first: `lab unblock`)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab` (+ one subcommand in `engine/src/seer_engine/commands/lab.py`)

---

## Goal

After this phase, `python -m seer_engine lab survivorship M0069 [M0007 ...]` re-runs every recorded
dev variant of each named method at its recorded capital and funding. It runs them first on the
dev store and then on the survivorship-check store, and never holds both stores in memory at once.
It prints the two results side by side with the change, plus N and the test-window looks before
and after. With `--csv` it writes the full grid. Unless `--no-journal` is set, it journals one
plain-words `observation` per method. It writes nothing else: no `trials`, `trial_moments`,
`trial_funding` or `trial_provenance` row, and no status or pre-registration change.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- module `seer_engine.lab.survivorship_check` (`engine/src/seer_engine/lab/survivorship_check.py`) with:
  `SV_PURPOSE = research.SURVIVORSHIP_PURPOSE` (phase 1's constant, value `"survivorship-check"`), `DEV_LABEL = "dev"`, `SV_LABEL = "survivorship"`,
  `HIGH_COVERAGE = (date(2009, 1, 1), date(2015, 10, 16))`, `CSV_HEADER`;
  dataclasses `Variant`, `MethodPlan`, `Side`, `StoreRun`, `VariantRow`, `MethodReport`;
  functions `resolve_method(method_id) -> Method`, `plan_method(conn, method_id) -> MethodPlan`,
  `plan_methods(conn, ids) -> tuple[MethodPlan, ...]`, `peek_purpose(store_dir) -> str | None`,
  `check_stores(dev_dir, sv_dir) -> None`, `load_checked(store_dir, *, survivorship) -> ResearchData`,
  `side_of(...)`, `run_store(conn, plans, data, label, bench) -> dict`,
  `measure_store(conn, plans, store_dir, *, survivorship, bench) -> StoreRun`,
  `compare(plans, dev_run, sv_run, geo) -> tuple[MethodReport, ...]`,
  `format_report(rep, dev_run, sv_run, n_folds) -> str`, `summary_line(rep) -> str`,
  `insight_text(rep) -> (title, body)`, `journal(conn, rep) -> int`,
  `csv_rows(reports, dev_run, sv_run) -> list[list[str]]`, `write_csv(reports, dev_run, sv_run, path) -> Path`.
- `commands/lab.py`: the `lab survivorship` entry in the module docstring's command list,
  subparser `survivorship` (positional `method` nargs `+`, `--store`, `--sv-store`,
  `--no-journal`, `--csv PATH`), handler `_survivorship(conn, args)`, `_HANDLERS["survivorship"]`.
- the `--csv` grid's columns are `CSV_HEADER` exactly (phase 5's `combine.py`/`summarize.py` read
  them by name): `method_id, candidate_id, store` (`dev` | `survivorship`), …, `reproduced`
  (`1`/`0` on dev rows, empty on survivorship rows), `yearly_return`, `spy_yearly_return`, `lead`,
  `beats_spy`, `max_drawdown`, `profit_factor`, …, `era_edge`, `wf_won`, `wf_scored`,
  `wf_majority`, `wf_stable`; fractions, not percents.
- test file `engine/tests/test_lab_survivorship.py`.

**Signature changes:** none.
**Requires (from earlier phases):**
- Phase 1 (confirmed against phase-1.md): `research.ResearchData.purpose: str | None = None` (the
  last field, so `dataclasses.replace(data, purpose=...)` works); `research.SV_STORE_DIR: Path`;
  `research.SURVIVORSHIP_PURPOSE = "survivorship-check"`; `research.load_store(sv_dir)` (default
  `window=DEV_WINDOW`, no extra keyword) **loads** a purpose-marked store — `_read_manifest` only
  subtracts and validates the key — and surfaces it on `ResearchData.purpose`; the dev store loads
  with `purpose is None`. `research.declared_purpose(store_dir) -> str | None` reads the manifest
  alone (ValueError when it is missing, unparseable or names an unknown purpose); `peek_purpose`
  wraps it.
- Phase 1: the real SV store built at `/home/miftah/seer/engine/.research-sv` (needed only for the smoke run).
- Phase 3: `commands/lab.py` already carries `lab unblock` (its subparser, `_unblock` and `"unblock"` in
  `_HANDLERS`). This phase's insertions are anchored on text that phase 3 does not touch (see Step 2).
  `Market` gains a defaulted `series` field. That is harmless here, because the tests build `Market`
  through `dataclasses.replace`.
**Leaves alone (owned by others):** `research.py`, `survivorship.py`, `commands/survivorship_store.py`
(Phase 1); `eodhd.py` (Phase 2); `backtest/market.py`, `commands/market_series.py`, `lab unblock` (Phase 3);
`lab/hardgate.py` rules, `lab/runner.py`, `lab/real_costs.py`, `lab/walkforward.py`, every trial-writing path;
both stores' contents; `docs/lab/survivorship/` and the method-list runs (Phase 5).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/survivorship_check.py` | create | the whole report: plan, refusals, per-store runs, comparison, terminal table, CSV, journal text |
| `engine/src/seer_engine/commands/lab.py` | modify | docstring: `lab survivorship` entry after the `lab costs` block (base line 56); `survivorship` subparser after the `walkforward` subparser (base line 327); `_survivorship` handler after `_walkforward` (base line 2090); `"survivorship": _survivorship` after `"names": _names,` (base line 2215). Phase 1 (+8 lines at :1259) and phase 3 (`unblock`, 3 docstring lines at :63, a subparser at :342, a handler after `_block`, a `_HANDLERS` entry) land first and shift these numbers: locate every insertion by its quoted anchor |
| `engine/tests/test_lab_survivorship.py` | create | fixture dev + SV stores, report, collapse, N/looks invariance, refusals, memory order, CSV, journal text |

## Executor environment (do this first, in the worktree)

```bash
cd /home/miftah/.worktrees/seer/eodhd-survivorship-market
git branch --show-current            # must print feature/eodhd-survivorship-market
# phase 1 Step 0's recipe, idempotent: own venv (main's venv is an editable install of the main
# checkout and tests the wrong tree), read-only symlinks, their exclude lines
test -x engine/.venv/bin/python || { /home/miftah/.pyenv/versions/3.11.0/bin/python -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'; }
test -e engine/.research || ln -s /home/miftah/seer/engine/.research engine/.research
test -e engine/.cache    || ln -s /home/miftah/seer/engine/.cache engine/.cache
EXCL=$(git rev-parse --git-path info/exclude)
for p in engine/.cache engine/.research; do grep -qxF "$p" "$EXCL" || echo "$p" >> "$EXCL"; done
# Phase 1 and 3 must have landed on this branch:
engine/.venv/bin/python -c "from seer_engine import research; import dataclasses; \
assert 'purpose' in {f.name for f in dataclasses.fields(research.ResearchData)}; print(research.SV_STORE_DIR)"
grep -n '"unblock"' engine/src/seer_engine/commands/lab.py
```

`SEER_LAB_DB` is **not** set for this phase. The tests use temporary databases. The smoke run uses
a scratch copy of the main checkout's live DB, made with sqlite's backup API, and passes
`--no-journal`, so nothing is written anywhere.

## Implementation Steps

### Step 1: The report module
**File:** `engine/src/seer_engine/lab/survivorship_check.py` (new)
**Change:** The whole measurement. The design choices behind it:

- **Every refusal that needs no store happens before either store loads.** That covers: not a
  method id, no method file, no dev trial, no recorded variant still in the file, a trial with no
  recorded capital (`runner.recorded_capital` raises), a funded trial whose schedule moved
  (`hardgate.trial_deposits(conn, trial, [])` raises the same count mismatch the gate does), no
  REF-SPY-HOLD geometry (`hardgate.geometry` raises), the same directory given twice, and a
  manifest whose `purpose` is wrong. The manifest check is a cheap read of `manifest.json`.
  `load_checked` then makes the authoritative check on `ResearchData.purpose` after the full load.
- **Memory.** `measure_store` loads a store, runs every variant, keeps only a `Side` per
  variant, then drops its only reference and runs `gc.collect()` before returning. A `Side` holds
  numbers, a monthly curve of about 240 points and a deposit map, never a `DevRow`, a result or the
  market. The handler calls it for the dev store first and the SV store second, so the two stores
  are never alive together.
- **`run_registry` grouping.** `run_registry` takes one `initial_idr` and one `contributions` per
  call. Variants are grouped by `(recorded capital, recorded schedule)` **within each method** and
  chunked at `dev.MAX_CANDIDATES`. Calls are per method rather than across methods because
  `run_registry` refuses two different allocator objects that share an id, and two method files
  are free to define the same allocator id. The only cost is one allocator preparation per
  method.
- **The yearly measure.** It is `Metrics.mwr` when the run received deposits and `Metrics.cagr`
  otherwise. `mwr is None` means unfunded and `cagr` is then the money-weighted return, which is
  `metrics.Metrics`'s own contract. SPY TR is read the same way from `row.spy_tr`.
- **DSR.** It is `dev.deflated_sharpe` on the re-run's own daily moments, at the trial's recorded
  `n_trials_at_run` and the recorded `trial_moments.var_trials`. When no moments row exists, the
  report says "no recorded var_trials" and computes nothing.
- **De-funding.** `hardgate.trial_deposits(conn, recorded_trial_row, rerun_curve)` builds the
  schedule from the recorded trial's dates and `trial_funding` row, then buckets it on the re-run's
  curve. It is the single de-funding path the gate, `lab regime` and `lab walkforward` share.
- **Era and folds.** `HIGH_COVERAGE` is duplicated from `commands/lab.py` rather than imported,
  because a `lab/` module must not import a command module, and a test pins the two equal. The
  walk-forward uses `hardgate.geometry(conn)`, the same benchmark curve and folds the gate uses.
- **Dev reproduction.** It uses `real_costs.REPRO_TOL` (relative, against `max(1, |recorded|)`),
  the same rule `lab costs` uses.

**Code:**
```python
"""``lab survivorship M0069 [M0007 ...]``: recorded methods re-run on the survivorship-check store.

Every lab result so far was measured on ``engine/.research``, which prices about 59% of the
index-member days of 1996-2015, mostly the survivors: the companies that went bankrupt, were bought
or renamed are the ones yfinance could not serve. Phase 1 of the EODHD plan built a second
dev-window store, ``engine/.research-sv``, that adds most of them back from EODHD and is marked
``purpose: "survivorship-check"`` in its manifest. This module answers one question per method: how
much did the missing companies flatter the result the lab recorded?

**A report, not a trial.** For each named method, every variant with a recorded dev trial that is
still in the method file is re-run through ``dev.run_registry`` at the trial's recorded capital
(``runner.recorded_capital``) and funding (``runner.recorded_contributions``) -- once on the dev
store, then once on the survivorship-check store -- and the two are printed side by side. Nothing is
written but, unless ``--no-journal``, one ``observation`` per method: no ``trials``,
``trial_moments``, ``trial_funding`` or ``trial_provenance`` row, no status, no pre-registration. So
``store.dev_trial_count`` (the lab's N) and ``store.test_looks`` cannot move, and a survivorship-check
result can never be recorded as a dev trial of the original method -- mixing price fingerprints
inside one method's trial set is exactly what ``lab/hardgate.py`` exists to refuse.

**Refusals before any store loads.** Everything that needs no bars is checked first: the method ids,
their files, their recorded trials, capital and funding, the benchmark geometry, and both stores'
manifest ``purpose`` (the dev store must have none, the check store must read
``"survivorship-check"``). ``load_checked`` repeats the purpose check on the loaded
``ResearchData.purpose`` -- the authoritative one -- and ``research.load_store`` refuses a
test-window store on its own.

**Memory.** Each store is about 2.5M bar rows. ``measure_store`` loads one, runs every variant,
keeps only small ``Side`` records, and drops the store before returning, so the dev store is freed
before the survivorship-check store is loaded. The two are never alive together.
"""

from __future__ import annotations

import csv
import gc
import logging
import math
import sqlite3
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.dev import Candidate, DevRow
from seer_engine.backtest.metrics import DASH, fmt_num, fmt_pct, fmt_pf, fmt_signed_pct
from seer_engine.commands.backtest_dev import daily_moments, month_end_curve
from seer_engine.lab import hardgate, runner, store
from seer_engine.lab import walkforward as wf
from seer_engine.lab.method import METHOD_ID, Method, discover
from seer_engine.lab.real_costs import REPRO_TOL
from seer_engine.sim.contributions import ContributionSchedule

log = logging.getLogger(__name__)

SV_PURPOSE = research.SURVIVORSHIP_PURPOSE  # the manifest marker phase 1 writes on engine/.research-sv
DEV_LABEL = "dev"
SV_LABEL = "survivorship"
#: The era in which the dev store prices the most of the index -- ``commands/lab.py``'s
#: ``HIGH_COVERAGE``, repeated here because a ``lab`` module does not import a command module.
#: ``test_lab_survivorship`` pins the two equal.
HIGH_COVERAGE = (date(2009, 1, 1), date(2015, 10, 16))


# --------------------------------------------------------------------------- what to re-run


@dataclass(frozen=True)
class Variant:
    """One recorded dev variant, resolved against the database before any store loads."""

    candidate: Candidate
    trial_n: int
    trial: sqlite3.Row = field(compare=False, repr=False)
    capital: Decimal
    contributions: ContributionSchedule | None
    recorded_total_return: float | None
    recorded_dsr: float | None
    recorded_mar: float | None
    n_at_run: int | None
    var_trials: float | None  # trial_moments.var_trials; None when no moments row was recorded

    @property
    def funded(self) -> bool:
        return self.contributions is not None


@dataclass(frozen=True)
class MethodPlan:
    method: Method
    variants: tuple[Variant, ...]
    missing: tuple[str, ...]  # recorded candidate ids that are no longer in the method file


def resolve_method(method_id: str) -> Method:
    """The committed ``METHOD`` for a lab method id (``store.LabError`` otherwise)."""
    if not isinstance(method_id, str) or METHOD_ID.fullmatch(method_id) is None:
        raise store.LabError(
            f"{method_id!r} is not a lab method id; `lab survivorship` takes methods like M0069"
        )
    methods = discover()
    if method_id not in methods:
        raise store.LabError(
            f"no method file for {method_id} in seer_engine/lab/methods/. `lab survivorship` "
            f"re-runs the committed method file, not a database row"
        )
    return methods[method_id][0]


def _f(x: object) -> float | None:
    return None if x is None else float(x)


def plan_method(conn: sqlite3.Connection, method_id: str) -> MethodPlan:
    """Every recorded dev variant of ``method_id`` that is still in its method file.

    Resolves each variant's recorded capital, funding, N and ``var_trials`` now, so a trial that
    cannot be re-run as the measurement it was is refused before a store is opened. A funded
    trial's schedule is checked against its recorded deposit count here too
    (``hardgate.trial_deposits`` with an empty curve buckets nothing but still raises on a moved
    schedule).
    """
    method = resolve_method(method_id)
    trials = [t for t in store.trials_of(conn, method.id) if t["window"] == "dev"]
    if not trials:
        raise store.LabError(
            f"{method.id} has no dev trial; `lab survivorship` re-runs what the lab recorded. "
            f"Run it with `lab run {method.id}` first"
        )
    by_id = {c.id: c for c in method.candidates}
    seen: set[str] = set()
    variants: list[Variant] = []
    missing: list[str] = []
    for t in trials:  # trials_of orders by n: the first recording of a variant wins
        cid = str(t["candidate_id"])
        if cid in seen:
            continue
        seen.add(cid)
        candidate = by_id.get(cid)
        if candidate is None:
            missing.append(cid)
            continue
        n = int(t["n"])
        capital = runner.recorded_capital(conn, n)
        contributions = runner.recorded_contributions(conn, n)
        if contributions is not None:
            hardgate.trial_deposits(conn, t, [])
        moments = store.moments_of(conn, n)
        variants.append(
            Variant(
                candidate=candidate,
                trial_n=n,
                trial=t,
                capital=capital,
                contributions=contributions,
                recorded_total_return=_f(t["total_return"]),
                recorded_dsr=_f(t["dsr"]),
                recorded_mar=_f(t["mar"]),
                n_at_run=None if t["n_trials_at_run"] is None else int(t["n_trials_at_run"]),
                var_trials=None if moments is None else float(moments["var_trials"]),
            )
        )
    if not variants:
        raise store.LabError(
            f"{method.id}: none of its recorded variants ({', '.join(missing)}) is in its method "
            f"file any more; there is nothing to re-run"
        )
    return MethodPlan(method, tuple(variants), tuple(missing))


def plan_methods(conn: sqlite3.Connection, ids: Sequence[str]) -> tuple[MethodPlan, ...]:
    """``plan_method`` for each id, upper-cased and de-duplicated in the order given."""
    out: list[MethodPlan] = []
    done: set[str] = set()
    for raw in ids:
        mid = str(raw).strip().upper()
        if mid in done:
            continue
        done.add(mid)
        out.append(plan_method(conn, mid))
    if not out:
        raise store.LabError("name at least one method, e.g. `lab survivorship M0069`")
    return tuple(out)


# --------------------------------------------------------------------------- the two stores


def peek_purpose(store_dir: Path) -> str | None:
    """The manifest's ``purpose`` without loading a bar: ``research.declared_purpose``, with its
    refusals (no manifest, not JSON, an unknown purpose) as ``store.LabError``."""
    try:
        return research.declared_purpose(Path(store_dir))
    except OSError as e:
        raise store.LabError(f"{store_dir}: cannot read the manifest ({e})") from e
    except ValueError as e:
        raise store.LabError(
            f"{e}. Point the flag at a built store (the dev store and engine/.research-sv live in "
            f"the main checkout)"
        ) from e


def check_stores(dev_dir: Path, sv_dir: Path) -> None:
    """Refuse a wrong pair of stores before either is loaded (``store.LabError``)."""
    if Path(dev_dir).resolve() == Path(sv_dir).resolve():
        raise store.LabError(
            f"--store and --sv-store both name {Path(dev_dir).resolve()}; the report compares the "
            f"dev store with the survivorship-check store, so it needs two different stores"
        )
    dev_purpose = peek_purpose(dev_dir)
    if dev_purpose is not None:
        raise store.LabError(
            f"{dev_dir} is a {dev_purpose!r} store, not the dev store. --store must be the store "
            f"the lab's trials were recorded on"
        )
    sv_purpose = peek_purpose(sv_dir)
    if sv_purpose != SV_PURPOSE:
        raise store.LabError(
            f"{sv_dir} is not a survivorship-check store (its manifest's purpose is "
            f"{sv_purpose!r}, not {SV_PURPOSE!r}). Build one with "
            f"`python -m seer_engine survivorship_store --build`"
        )


def load_checked(store_dir: Path, *, survivorship: bool) -> research.ResearchData:
    """Load one store on the dev window and check its purpose (``store.LabError`` otherwise)."""
    try:
        data = research.load_store(Path(store_dir))
    except FileNotFoundError as e:
        raise store.LabError(f"research store {store_dir} is missing {e.filename or e}") from e
    except ValueError as e:
        raise store.LabError(
            f"{store_dir}: {e}. `lab survivorship` re-runs the dev window and nothing else, so a "
            f"test-window store is refused here"
        ) from e
    if data.window != research.DEV_WINDOW:
        raise store.LabError(
            f"{store_dir} was built for the {data.window.name!r} window; `lab survivorship` "
            f"re-runs the dev window and nothing else"
        )
    if survivorship and data.purpose != SV_PURPOSE:
        raise store.LabError(
            f"{store_dir} loaded with purpose {data.purpose!r}, not {SV_PURPOSE!r}; it is not the "
            f"survivorship-check store"
        )
    if not survivorship and data.purpose is not None:
        raise store.LabError(
            f"{store_dir} loaded with purpose {data.purpose!r}; the dev side must be the store the "
            f"lab's trials were recorded on, which carries none"
        )
    return data


# --------------------------------------------------------------------------- one run's numbers


@dataclass(frozen=True)
class Side:
    """One variant's numbers on one store. Holds no market, result or DevRow."""

    store: str  # DEV_LABEL | SV_LABEL
    candidate_id: str
    start: date
    end: date
    funded: bool
    total_return: float | None
    yearly: float | None  # money-weighted when the run was fed deposits, else CAGR
    spy_yearly: float | None  # SPY TR's same measure, same money on the same days
    beats_spy: bool
    max_drawdown: float | None
    profit_factor: float | None
    trades: int
    sharpe: float | None  # annualized
    sr_daily: float | None
    t: int
    skew: float | None
    kurt: float | None  # not excess
    dsr: float | None  # at the recorded N and var_trials; None when either is missing
    era_yearly: float | None  # de-funded CAGR over HIGH_COVERAGE
    era_spy_yearly: float | None  # the recorded REF-SPY-HOLD curve's, same slice
    curve: tuple[tuple[date, float], ...] = field(compare=False, repr=False)
    deposits: Mapping[date, float] = field(compare=False, repr=False)

    @property
    def lead(self) -> float | None:
        """Yearly return minus SPY TR's, in the same measure."""
        if self.yearly is None or self.spy_yearly is None:
            return None
        return self.yearly - self.spy_yearly

    @property
    def era_edge(self) -> float | None:
        if self.era_yearly is None or self.era_spy_yearly is None:
            return None
        return self.era_yearly - self.era_spy_yearly


def side_of(
    label: str,
    v: Variant,
    row: DevRow,
    curve: Sequence[tuple[date, float]],
    deposits: Mapping[date, float],
    bench: Sequence[tuple[date, float]],
) -> Side:
    m = row.stats.metrics
    yearly = m.mwr if m.mwr is not None else m.cagr
    spy_yearly = row.spy_tr.mwr if row.spy_tr.mwr is not None else row.spy_tr.cagr
    returns = row.stats.daily_returns
    t = len(returns)
    moments = daily_moments(returns)
    if moments is None:
        sr = skew = kurt = dsr = None
    else:
        sr, skew, kurt = moments
        dsr = (
            None
            if v.var_trials is None or v.n_at_run is None
            else dev.deflated_sharpe(sr, v.n_at_run, v.var_trials, t, skew, kurt)
        )
    mine = wf.measure(curve, HIGH_COVERAGE[0], HIGH_COVERAGE[1], deposits)
    theirs = wf.measure(bench, HIGH_COVERAGE[0], HIGH_COVERAGE[1])
    return Side(
        store=label,
        candidate_id=row.candidate.id,
        start=row.start,
        end=row.end,
        funded=v.funded,
        total_return=m.total_return,
        yearly=yearly,
        spy_yearly=spy_yearly,
        beats_spy=bool(row.beats_spy),
        max_drawdown=m.max_drawdown,
        profit_factor=m.profit_factor,
        trades=int(m.trades),
        sharpe=row.stats.sharpe,
        sr_daily=sr,
        t=t,
        skew=skew,
        kurt=kurt,
        dsr=dsr,
        era_yearly=None if mine is None else mine.cagr,
        era_spy_yearly=None if theirs is None else theirs.cagr,
        curve=tuple(curve),
        deposits=dict(deposits),
    )


def run_store(
    conn: sqlite3.Connection,
    plans: Sequence[MethodPlan],
    data: research.ResearchData,
    label: str,
    bench: Sequence[tuple[date, float]],
) -> dict[tuple[str, str], Side]:
    """Every variant of every plan on ``data``: ``{(method id, candidate id): Side}``.

    One ``dev.run_registry`` call per (method, recorded capital, recorded schedule), chunked at
    ``dev.MAX_CANDIDATES``. Never across methods: two method files may define different allocator
    objects under one id, which ``run_registry`` refuses within a call.
    """
    out: dict[tuple[str, str], Side] = {}
    for plan in plans:
        mid = plan.method.id
        groups: dict[tuple[Decimal, ContributionSchedule | None], list[Variant]] = {}
        for v in plan.variants:
            groups.setdefault((v.capital, v.contributions), []).append(v)
        for (capital, contributions), group in groups.items():
            by_id = {v.candidate.id: v for v in group}
            for i in range(0, len(group), dev.MAX_CANDIDATES):
                chunk = group[i : i + dev.MAX_CANDIDATES]

                def on_result(_i: int, result: object, row: DevRow, *, _mid: str = mid,
                              _by_id: Mapping[str, Variant] = by_id) -> None:
                    v = _by_id[row.candidate.id]
                    curve = month_end_curve(result.snapshots)
                    deposits = hardgate.trial_deposits(conn, v.trial, list(curve))
                    side = side_of(label, v, row, curve, deposits, bench)
                    out[(_mid, v.candidate.id)] = side
                    log.info(
                        "[%s] %s: total return %s, yearly %s vs SPY %s, max DD %s, trades %d",
                        label, row.candidate.id, fmt_signed_pct(side.total_return),
                        fmt_signed_pct(side.yearly), fmt_signed_pct(side.spy_yearly),
                        fmt_pct(side.max_drawdown), side.trades,
                    )

                dev.run_registry(
                    data.market, data.dividends, data.spy_dividends,
                    tuple(v.candidate for v in chunk),
                    on_result=on_result, contributions=contributions, initial_idr=capital,
                )
    return out


@dataclass(frozen=True)
class StoreRun:
    """What one store produced. Strings and Sides only: the store itself is gone."""

    label: str
    store_dir: str
    fingerprint: str
    price_fingerprint: str | None
    sides: Mapping[tuple[str, str], Side] = field(compare=False, repr=False)


def measure_store(
    conn: sqlite3.Connection,
    plans: Sequence[MethodPlan],
    store_dir: Path,
    *,
    survivorship: bool,
    bench: Sequence[tuple[date, float]],
) -> StoreRun:
    """Load one store, run every variant on it, free it, return the numbers."""
    label = SV_LABEL if survivorship else DEV_LABEL
    t0 = time.perf_counter()
    data = load_checked(store_dir, survivorship=survivorship)
    log.info("%s store %s loaded (%.1fs)", label, str(data.fingerprint)[:12], time.perf_counter() - t0)
    try:
        sides = run_store(conn, plans, data, label, bench)
        return StoreRun(
            label=label,
            store_dir=str(store_dir),
            fingerprint=str(data.fingerprint),
            price_fingerprint=data.price_fingerprint,
            sides=sides,
        )
    finally:
        del data  # the only reference: the store is freed before the caller loads the next one
        gc.collect()
        log.info("%s store released (%.1fs)", label, time.perf_counter() - t0)


# --------------------------------------------------------------------------- the comparison


@dataclass(frozen=True)
class VariantRow:
    method_id: str
    variant: Variant
    dev: Side
    sv: Side

    @property
    def reproduced(self) -> bool | None:
        """Did the dev re-run land on the recorded total return? None when either is missing."""
        recorded, measured = self.variant.recorded_total_return, self.dev.total_return
        if recorded is None or measured is None:
            return None
        return abs(measured - recorded) <= REPRO_TOL * max(1.0, abs(recorded))


@dataclass(frozen=True)
class MethodReport:
    method_id: str
    method_name: str
    missing: tuple[str, ...]
    rows: tuple[VariantRow, ...]
    dev_record: wf.Record
    sv_record: wf.Record

    @property
    def headline(self) -> VariantRow:
        """The best recorded variant by MAR (ties: lower trial number; no MAR ranks last)."""
        return sorted(
            self.rows,
            key=lambda r: (
                r.variant.recorded_mar is None,
                -(r.variant.recorded_mar or 0.0),
                r.variant.trial_n,
            ),
        )[0]

    @property
    def worse(self) -> int:
        """Variants that earn less a year on the survivorship-check store."""
        return sum(
            1 for r in self.rows
            if r.dev.yearly is not None and r.sv.yearly is not None and r.sv.yearly < r.dev.yearly
        )

    @property
    def reproduced(self) -> bool:
        return all(r.reproduced is not False for r in self.rows)


def _record(
    method_id: str, sides: Sequence[Side], geo: hardgate.Geometry
) -> wf.Record:
    curves = {s.candidate_id: list(s.curve) for s in sides}
    deps = {s.candidate_id: dict(s.deposits) for s in sides}
    return wf.Record(method_id, wf.evaluate(curves, list(geo.bench), geo.folds, deps))


def compare(
    plans: Sequence[MethodPlan], dev_run: StoreRun, sv_run: StoreRun, geo: hardgate.Geometry
) -> tuple[MethodReport, ...]:
    out: list[MethodReport] = []
    for plan in plans:
        mid = plan.method.id
        rows = tuple(
            VariantRow(
                mid, v, dev_run.sides[(mid, v.candidate.id)], sv_run.sides[(mid, v.candidate.id)]
            )
            for v in plan.variants
        )
        out.append(
            MethodReport(
                method_id=mid,
                method_name=plan.method.name,
                missing=plan.missing,
                rows=rows,
                dev_record=_record(mid, [r.dev for r in rows], geo),
                sv_record=_record(mid, [r.sv for r in rows], geo),
            )
        )
    return tuple(out)


# --------------------------------------------------------------------------- the terminal report


def _finite(x: float | None) -> bool:
    return x is not None and math.isfinite(x)


def _pts(a: float | None, b: float | None) -> str:
    """``b - a`` as percentage points, signed."""
    if not (_finite(a) and _finite(b)):
        return DASH
    return f"{(b - a) * 100:+.1f} pts"


def _diff(a: float | None, b: float | None, digits: int = 2) -> str:
    if not (_finite(a) and _finite(b)):
        return DASH
    return f"{b - a:+.{digits}f}"


def _folds(rec: wf.Record) -> str:
    return rec.summary() + (", majority" if rec.majority else "")


def _variant_block(row: VariantRow) -> list[str]:
    v, d, s = row.variant, row.dev, row.sv
    measure = "money-weighted" if v.funded else "CAGR"
    if v.var_trials is None:
        dsr_row = ("DSR", "no recorded var_trials", "no recorded var_trials", DASH)
    elif v.n_at_run is None:
        dsr_row = ("DSR", "no recorded N", "no recorded N", DASH)
    else:
        dsr_row = (
            f"DSR at recorded N={v.n_at_run}",
            fmt_num(d.dsr, 3), fmt_num(s.dsr, 3), _diff(d.dsr, s.dsr, 3),
        )
    rows: list[tuple[str, str, str, str]] = [
        ("total return", fmt_signed_pct(d.total_return), fmt_signed_pct(s.total_return),
         _pts(d.total_return, s.total_return)),
        (f"yearly return ({measure})", fmt_signed_pct(d.yearly), fmt_signed_pct(s.yearly),
         _pts(d.yearly, s.yearly)),
        (f"SPY TR yearly ({measure})", fmt_signed_pct(d.spy_yearly), fmt_signed_pct(s.spy_yearly),
         _pts(d.spy_yearly, s.spy_yearly)),
        ("lead over SPY a year", fmt_signed_pct(d.lead), fmt_signed_pct(s.lead), _pts(d.lead, s.lead)),
        ("max drawdown", fmt_pct(d.max_drawdown), fmt_pct(s.max_drawdown),
         _pts(d.max_drawdown, s.max_drawdown)),
        ("profit factor", fmt_pf(d.profit_factor), fmt_pf(s.profit_factor),
         _diff(d.profit_factor, s.profit_factor)),
        ("trades", str(d.trades), str(s.trades), f"{s.trades - d.trades:+d}"),
        ("Sharpe (annualized)", fmt_num(d.sharpe), fmt_num(s.sharpe), _diff(d.sharpe, s.sharpe)),
        ("daily Sharpe", fmt_num(d.sr_daily, 4), fmt_num(s.sr_daily, 4), _diff(d.sr_daily, s.sr_daily, 4)),
        ("T (daily returns)", str(d.t), str(s.t), f"{s.t - d.t:+d}"),
        ("skew", fmt_num(d.skew, 3), fmt_num(s.skew, 3), _diff(d.skew, s.skew, 3)),
        ("kurtosis", fmt_num(d.kurt, 3), fmt_num(s.kurt, 3), _diff(d.kurt, s.kurt, 3)),
        dsr_row,
        ("2009-2015 lead over SPY a year", fmt_signed_pct(d.era_edge), fmt_signed_pct(s.era_edge),
         _pts(d.era_edge, s.era_edge)),
    ]
    width = max(len(r[0]) for r in rows)
    out = [
        f"  {d.candidate_id}  (trial #{v.trial_n}, {'funded' if v.funded else 'lump sum'}, "
        f"capital {v.capital:,.0f} IDR, {d.start}..{d.end})",
        f"    {'':<{width}}  {'dev':>14}  {'survivorship':>14}  {'change':>12}",
    ]
    out += [f"    {a:<{width}}  {b:>14}  {c:>14}  {e:>12}" for a, b, c, e in rows]
    head = f"    recorded dev trial #{v.trial_n}: total return {fmt_signed_pct(v.recorded_total_return)}"
    rep = row.reproduced
    if rep is None:
        out.append(f"{head}; there is no number to check the dev re-run against")
    elif rep:
        out.append(f"{head}; the dev re-run reproduces it")
    else:
        out.append(
            f"{head}; the dev re-run measured {fmt_signed_pct(d.total_return)} -- the store or the "
            f"engine changed since it ran, so compare the two re-runs with each other, not with "
            f"the recorded trial"
        )
    return out


def format_report(rep: MethodReport, dev_run: StoreRun, sv_run: StoreRun, n_folds: int) -> str:
    """One method's terminal table. Ids and labels are fine here."""
    out = [
        f"lab survivorship {rep.method_id} -- {rep.method_name}: {len(rep.rows)} recorded "
        f"variant(s), dev store {dev_run.fingerprint[:12]} vs survivorship-check store "
        f"{sv_run.fingerprint[:12]}",
        "report only: no trial row, no moments, no funding, no status change; the lab's N and "
        "the test-window looks do not move",
    ]
    if rep.missing:
        out.append(
            f"not re-run (recorded, but no longer in the method file): {', '.join(rep.missing)}"
        )
    for row in rep.rows:
        out.append("")
        out += _variant_block(row)
    out.append("")
    changed = (rep.dev_record.won, len(rep.dev_record.scored), rep.dev_record.majority) != (
        rep.sv_record.won, len(rep.sv_record.scored), rep.sv_record.majority
    )
    out.append(
        f"  walk-forward vs the recorded SPY hold ({n_folds} folds): dev {_folds(rep.dev_record)}; "
        f"survivorship {_folds(rep.sv_record)} -- {'changed' if changed else 'unchanged'}"
    )
    return "\n".join(out)


def summary_line(rep: MethodReport) -> str:
    h = rep.headline
    d, s = h.dev, h.sv
    return (
        f"{rep.method_id} ({h.variant.candidate.id}): yearly {fmt_signed_pct(d.yearly)} -> "
        f"{fmt_signed_pct(s.yearly)} (SPY {fmt_signed_pct(d.spy_yearly)} -> "
        f"{fmt_signed_pct(s.spy_yearly)}), max DD {fmt_pct(d.max_drawdown)} -> "
        f"{fmt_pct(s.max_drawdown)}, 2009-2015 lead {fmt_signed_pct(d.era_edge)} -> "
        f"{fmt_signed_pct(s.era_edge)}, folds {rep.dev_record.summary()} -> "
        f"{rep.sv_record.summary()}; {rep.worse} of {len(rep.rows)} variants earn less a year"
        + ("" if rep.reproduced else "; WARNING: a dev re-run did not reproduce its trial")
    )


# --------------------------------------------------------------------------- the journal


def _say_folds(rec: wf.Record) -> str:
    n = len(rec.scored)
    if n == 0:
        return "no period it could be judged on"
    return f"{rec.won} of {n} periods won"


def insight_text(rep: MethodReport) -> tuple[str, str]:
    """``(title, body)`` in plain words for a non-trader: no ids, no code, no symbols."""
    h = rep.headline
    d, s = h.dev, h.sv
    years = f"{d.start.year}–{d.end.year}"
    money = (
        "the same starting money and the same monthly top-ups"
        if h.variant.funded else "the same starting money"
    )
    intro = (
        f"The lab re-ran the {len(rep.rows)} version(s) of this method it had already tested, over "
        f"the same {years} history, twice: once on the usual price history, and once on a check "
        f"history that adds back most of the companies the usual one is missing -- companies "
        f"that left the index by failing, being bought out or changing their name. Same rules, "
        f"{money}. The numbers below are for its best version."
    )
    bullets = "\n".join(
        (
            f"- Return a year: {fmt_signed_pct(d.yearly)} on the usual history, "
            f"{fmt_signed_pct(s.yearly)} with the missing companies added (SPY: "
            f"{fmt_signed_pct(d.spy_yearly)} and {fmt_signed_pct(s.spy_yearly)}).",
            f"- Worst fall from a peak: {fmt_pct(d.max_drawdown)} and {fmt_pct(s.max_drawdown)}.",
            f"- In 2009–2015, the years the usual history covers best, its lead over SPY was "
            f"{fmt_signed_pct(d.era_edge)} a year before and {fmt_signed_pct(s.era_edge)} after.",
        )
    )
    head = (
        "The check that picks a version on earlier years and then judges it on later years it "
        "had not seen"
    )
    if (rep.dev_record.won, len(rep.dev_record.scored)) == (
        rep.sv_record.won, len(rep.sv_record.scored)
    ):
        folds = f"{head} did not change: {_say_folds(rep.dev_record)} on both histories."
    else:
        folds = (
            f"{head} moved from {_say_folds(rep.dev_record)} to {_say_folds(rep.sv_record)}."
        )
    if d.yearly is None or s.yearly is None:
        verdict = "Its yearly return could not be measured on both histories."
    else:
        gap = s.yearly - d.yearly
        if abs(gap) < 0.005:
            verdict = (
                "The missing companies barely move it: its yearly return changed by less than "
                "half a point."
            )
        elif gap < 0:
            verdict = (
                f"The missing companies flattered it: with them added it earns "
                f"{abs(gap) * 100:.1f} points a year less."
            )
        else:
            verdict = (
                f"The missing companies did not flatter it: with them added it earns "
                f"{gap * 100:.1f} points a year more."
            )
    verdict += f" {rep.worse} of its {len(rep.rows)} version(s) earn less a year with them added."
    if not rep.reproduced:
        verdict += (
            " The re-run on the usual history did not land exactly on the number the lab "
            "recorded, so the two re-runs are compared with each other, not with the record."
        )
    title = f"{rep.method_name}: what the missing companies did to it"
    body = "\n\n".join(
        (
            intro,
            bullets,
            folds,
            verdict,
            "This was a check, not a new try: the lab's count of tries did not move and no "
            "verdict changed.",
        )
    )
    return title, body


def journal(conn: sqlite3.Connection, rep: MethodReport) -> int:
    """One ``observation`` on the method. The caller owns the transaction. Returns its id."""
    title, body = insight_text(rep)
    return store.add_insight(conn, kind="observation", title=title, body=body, method_id=rep.method_id)


# --------------------------------------------------------------------------- the CSV grid

CSV_HEADER: tuple[str, ...] = (
    "method_id", "candidate_id", "store", "store_fingerprint", "price_fingerprint", "trial_n",
    "funded", "capital_idr", "start", "end", "total_return", "recorded_total_return",
    "reproduced", "yearly_return", "spy_yearly_return", "lead", "beats_spy", "max_drawdown",
    "profit_factor", "trades", "sharpe", "sr_daily", "t", "skew", "kurt", "n_at_run",
    "var_trials", "dsr", "recorded_dsr", "era_yearly", "era_spy_yearly", "era_edge",
    "wf_won", "wf_scored", "wf_majority", "wf_stable",
)


def _cell(x: object) -> str:
    if x is None:
        return ""
    if isinstance(x, bool):
        return "1" if x else "0"
    if isinstance(x, float):
        return repr(x)  # full precision; inf stays "inf"
    if isinstance(x, date):
        return x.isoformat()
    return str(x)


def csv_rows(
    reports: Sequence[MethodReport], dev_run: StoreRun, sv_run: StoreRun
) -> list[list[str]]:
    out: list[list[str]] = [list(CSV_HEADER)]
    for rep in reports:
        for row in rep.rows:
            v = row.variant
            for run, side, rec in ((dev_run, row.dev, rep.dev_record), (sv_run, row.sv, rep.sv_record)):
                out.append([
                    _cell(x) for x in (
                        rep.method_id, side.candidate_id, side.store, run.fingerprint,
                        run.price_fingerprint, v.trial_n, v.funded, v.capital, side.start,
                        side.end, side.total_return, v.recorded_total_return,
                        row.reproduced if side.store == DEV_LABEL else None,
                        side.yearly, side.spy_yearly, side.lead, side.beats_spy,
                        side.max_drawdown, side.profit_factor, side.trades, side.sharpe,
                        side.sr_daily, side.t, side.skew, side.kurt, v.n_at_run, v.var_trials,
                        side.dsr, v.recorded_dsr, side.era_yearly, side.era_spy_yearly,
                        side.era_edge, rec.won, len(rec.scored), rec.majority, rec.stable,
                    )
                ])
    return out


def write_csv(
    reports: Sequence[MethodReport], dev_run: StoreRun, sv_run: StoreRun, path: Path
) -> Path:
    """Write the full grid to ``path`` (parents created). Returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(csv_rows(reports, dev_run, sv_run))
    return path
```
**Impact:** New module only. It is imported lazily by the new handler, so nothing else loads it. It
calls only reading functions: `store.trials_of`, `moments_of`, `funding_of` (through `runner`),
`provenance_of` (through `runner.recorded_capital`), `hardgate.geometry` and `trial_deposits`, and
`store.add_insight` when journaling. The `Variant.trial` field carries `compare=False` so the frozen
dataclass never tries to hash a `sqlite3.Row`.

### Step 2: The `survivorship` subcommand
**File:** `engine/src/seer_engine/commands/lab.py`. There are three insertions. The anchors are
quoted text, because phase 3's `unblock` insertions shift line numbers. Phase 3 adds its parser
near `block`, its handler near `_block` and its `_HANDLERS` entry near `"block"`. None of those
touch the anchors below.

**2a. Subparser.** Insert this immediately after the `walkforward` subparser's last line,
`    s.add_argument("--eval-years", type=int, default=None, metavar="N")` (line 327 today), and
before `    s = sub.add_parser("idea", help="queue an idea in the backlog")`:
```python

    s = sub.add_parser(
        "survivorship",
        help="report only: recorded methods re-run on the survivorship-check store beside the dev store",
        description=(
            "Re-run every recorded dev variant of each named method at its recorded capital and "
            "funding, first on the dev store and then on the survivorship-check store (the dev "
            "store plus the bars of members it could not price), never holding both in memory. "
            "Prints them side by side: yearly return against SPY in the same measure, max "
            "drawdown, profit factor, trades, the DSR inputs at the recorded N and var_trials, "
            "the 2009-2015 lead over SPY and the walk-forward record. Records no trial, no "
            "moments, no funding and no status, so the lab's N and the test-window looks do not "
            "move; one plain-words observation per method is journaled unless --no-journal."
        ),
    )
    s.add_argument("method", nargs="+", metavar="M0069", help="the methods to re-run")
    s.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR),
        help=f"the dev store the trials were recorded on (default: {research.STORE_DIR}, or "
             "$SEER_RESEARCH_STORE); a store with a purpose marker or a test window is refused",
    )
    s.add_argument(
        "--sv-store",
        type=Path,
        default=research.SV_STORE_DIR,
        help=f"the survivorship-check store (default: {research.SV_STORE_DIR}); refused unless "
             "its manifest says purpose survivorship-check",
    )
    s.add_argument("--no-journal", action="store_true",
                   help="print the report and write nothing at all, not even the observation")
    s.add_argument("--csv", type=Path, default=None, metavar="PATH",
                   help="also write the full grid (variant x store) to PATH as CSV, full precision")
```
(No bare `%` in any `help=`: `test_cli.py::test_every_parsers_help_text_formats_without_raising`.)

**2b. Handler.** Insert this immediately after `_walkforward`'s closing lines
`    print("\nNothing was recorded. No research store was opened.")` / `    return 0` (lines 2089-2090
today), and before `def _idea(conn, args) -> int:`:
```python


def _survivorship(conn, args) -> int:
    """``lab survivorship M0069 [M0007 ...]``: recorded methods on the survivorship-check store.

    Report only. Every refusal that needs no bars -- method ids, files, recorded trials, capital,
    funding, the benchmark geometry, the two stores' manifest purpose -- is made before either
    store loads. The dev store is loaded, run and freed before the survivorship-check store is
    loaded. Nothing is written except one observation per method (none with --no-journal); N and
    the test-window looks are printed before and after so the invariant is visible.
    """
    from seer_engine.lab import hardgate
    from seer_engine.lab import survivorship_check as svc

    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    dev_dir, sv_dir = Path(args.store), Path(args.sv_store)
    plans = svc.plan_methods(conn, args.method)
    geo = hardgate.geometry(conn)
    svc.check_stores(dev_dir, sv_dir)
    n_before = store.dev_trial_count(conn)
    looks_before = store.test_looks(conn)
    t0 = time.perf_counter()
    dev_run = svc.measure_store(conn, plans, dev_dir, survivorship=False, bench=geo.bench)
    sv_run = svc.measure_store(conn, plans, sv_dir, survivorship=True, bench=geo.bench)
    reports = svc.compare(plans, dev_run, sv_run, geo)
    for rep in reports:
        print(svc.format_report(rep, dev_run, sv_run, len(geo.folds)))
        print()
    print("summary (best recorded variant by MAR; dev -> survivorship-check):")
    for rep in reports:
        print(f"  {svc.summary_line(rep)}")
    if args.csv is not None:
        written = svc.write_csv(reports, dev_run, sv_run, Path(args.csv))
        print(f"\ngrid written to {written}")
    if args.no_journal:
        tail = "No journal entry (--no-journal), so `lab stage` is not needed."
    else:
        with conn:
            entries = [svc.journal(conn, rep) for rep in reports]
        tail = (
            f"journal entries {', '.join(f'#{e}' for e in entries)} written (one observation per "
            f"method). Solo: `python -m seer_engine lab stage` so seertrade.site/sera shows them."
        )
    print(
        f"\nNo trial was recorded. Lab N (dev trials): {n_before} before, "
        f"{store.dev_trial_count(conn)} after; test-window looks used: {looks_before} before, "
        f"{store.test_looks(conn)} after. {tail}"
    )
    log.info("lab survivorship: %d method(s) done (%.1fs)", len(reports), time.perf_counter() - t0)
    return 0
```

**2c. Dispatch.** In `_HANDLERS`, immediately after `    "names": _names,` (line 2215 at base), add:
```python
    "survivorship": _survivorship,
```

**2d. Module docstring.** In the command list at the top of `commands/lab.py`, insert after the
`lab costs` entry's last line,
`                                    row, no moments, no status change: N and the looks do not move`,
and before `    lab idea --name ... --hypothesis ...   queue an idea (prints its id)`:
```
    lab survivorship M0069 [M0007 ...] [--store DIR] [--sv-store DIR] [--csv PATH] [--no-journal]
                                    report only: re-run every recorded dev variant of each method
                                    at its recorded capital and funding on the dev store and on
                                    the survivorship-check store (engine/.research-sv), side by
                                    side; journal one observation per method. No trial row, no
                                    moments, no status change: N and the looks do not move
```
(Phase 3's `lab unblock` lines sit after `lab block`, further down the same list.)

**Impact:** One new subcommand and its docstring entry. The existing parsers and handlers are
unchanged. `time`, `Path`, `os`, `research`, `dev`, `store` and `log` are already imported in
`commands/lab.py`.

### Step 3: Tests
**File:** `engine/tests/test_lab_survivorship.py` (new)
**Change:** The fixtures follow `test_lab_costs.py`. The lab is a temporary DB seeded with `seed(c)`,
which gives the REF-SPY-HOLD curve that `hardgate.geometry` needs (4 folds, measured). The dev store
is `labkit.smoke_data()`. The survivorship-check store is the same market plus one extra member,
`ZZZ`, that collapses about 12% a session from session 300 to 2% of its price and stops trading at
session 330. Its `purpose` is `"survivorship-check"`. Two factor variants are used, both with
`top=9` and `trend=None`, so every eligible member is held and the collapse must reach the book.
Measured with this exact construction on the worktree code: dev total return +1015.9% against
+940.8% on the survivorship-check store; money-weighted 7.05% against -0.99%. Stores are stood in
for by monkeypatching `research.load_store`, as `test_lab_costs.py` does. Each store directory
holds only a `manifest.json`, enough for the pre-load purpose check.
**Code:**
```python
"""``lab survivorship``: recorded methods re-run on the survivorship-check store (EODHD plan phase 4).

Report only: N, the looks and every trial-side table stay as they were; refusals come before any
store loads; the two stores are never alive at once; a collapse the dev store cannot see lowers the
result on the check store.
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import weakref
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from labkit import SMOKE_FIRST, smoke_data, smoke_history, smoke_test_data

from seer_engine import cli, dates, research
from seer_engine.backtest.dev import DEV_END, Candidate
from seer_engine.backtest.market import Membership
from seer_engine.commands import lab as lab_command
from seer_engine.lab import hardgate, runner, store
from seer_engine.lab import survivorship_check as svc
from seer_engine.lab.method import Method
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FACTOR, FactorParams

HERE = Path(__file__)
COLLAPSE_AT, LAST_BAR = 300, 330  # session indices into the smoke window
PARAMS_A = FactorParams(rank="lowvol", top=9, mom_n=60, mom_skip=0, vol_n=20, trend=None)
PARAMS_B = FactorParams(rank="momentum", top=9, mom_n=40, mom_skip=0, vol_n=20, trend=None)


def _cand(cid: str, params: FactorParams) -> Candidate:
    return Candidate(
        id=cid, family="M0001", rules=MONTHLY_HOLD_FRAC, allocator=FACTOR, params=params,
        rationale="test", added=date(2026, 10, 10), owner_inputs=(),
    )


def _method(cands=None) -> Method:
    return Method(
        id="M0001", name="Quiet stocks held equally", family="factor", source_kind="knowledge",
        source_ref="", hypothesis="h", expected_failure="f",
        candidates=cands or (_cand("M0001-A", PARAMS_A), _cand("M0001-B", PARAMS_B)),
    )


def _collapsed(days: list[date]) -> History:
    """A member priced like the others until COLLAPSE_AT, then ~12% a session down to 2% of its
    price, and no bar after LAST_BAR: a bankruptcy the dev store never saw."""
    h = smoke_history("ZZZ", 99, days)
    f = np.ones(len(days))
    for i in range(COLLAPSE_AT, len(days)):
        f[i] = max(0.02, 1.0 - 0.12 * (i - COLLAPSE_AT + 1))
    cut = slice(0, LAST_BAR)

    def px(a: np.ndarray) -> np.ndarray:
        return np.round(a * f, 2)[cut]

    return History("ZZZ", h.dates[cut], px(h.open), px(h.high), px(h.low), px(h.close), h.volume[cut])


def _sv_data() -> research.ResearchData:
    base = smoke_data()
    days = dates.sessions(SMOKE_FIRST, DEV_END)
    history = dict(base.market.history)
    history["ZZZ"] = _collapsed(days)
    membership = Membership(intervals=base.market.membership.intervals + (("ZZZ", days[0], None),))
    return replace(
        base,
        market=replace(base.market, history=history, membership=membership),
        fingerprint="smoke-sv",
        price_fingerprint="smoke-sv",
        manifest={"purpose": svc.SV_PURPOSE},
        purpose=svc.SV_PURPOSE,
    )


@pytest.fixture(scope="module")
def dev_data():
    return smoke_data()


@pytest.fixture(scope="module")
def sv_data():
    return _sv_data()


@pytest.fixture()
def lab(tmp_path):
    path = tmp_path / "lab.sqlite"
    c = store.connect(path)
    seed(c)
    yield c, path
    c.close()


@pytest.fixture()
def recorded(lab, dev_data, monkeypatch):
    conn, _ = lab
    m = _method()
    runner.run_method(conn, m, HERE, dev_data, git_sha="x", require_commit=False)
    monkeypatch.setattr(svc, "discover", lambda: {"M0001": (m, HERE)})
    return m


def _dirs(tmp_path, dev_manifest=None, sv_manifest=None) -> tuple[Path, Path]:
    d, s = tmp_path / "dev-store", tmp_path / "sv-store"
    d.mkdir()
    s.mkdir()
    (d / "manifest.json").write_text(json.dumps({"fingerprint": "smoke"} if dev_manifest is None else dev_manifest))
    (s / "manifest.json").write_text(json.dumps(
        {"fingerprint": "smoke-sv", "purpose": svc.SV_PURPOSE} if sv_manifest is None else sv_manifest
    ))
    return d, s


def _loader(by_dir, alive_at_load=None):
    """A stand-in for research.load_store: a fresh ResearchData per call, so a test can watch
    the previous one die before the next is handed out."""
    returned: list[weakref.ref] = []

    def load(store_dir, **kw):
        got = by_dir[Path(store_dir)]
        if isinstance(got, BaseException):
            raise got
        if alive_at_load is not None:
            alive_at_load.append(sum(1 for r in returned if r() is not None))
        fresh = replace(got)
        returned.append(weakref.ref(fresh))
        return fresh

    return load


def _untouched(conn):
    """Everything `lab survivorship` must leave as it found it (insights excepted)."""
    return (
        store.dev_trial_count(conn),
        store.test_looks(conn),
        conn.execute("SELECT count(*) FROM trials").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_funding").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_provenance").fetchone()[0],
        tuple(tuple(r) for r in conn.execute("SELECT id, status, verdict, source_sha FROM methods ORDER BY id")),
    )


def _insights(conn) -> int:
    return conn.execute("SELECT count(*) FROM insights").fetchone()[0]


def _measure(conn, dev_data, sv_data, tmp_path, monkeypatch):
    d, s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data, s: sv_data}))
    plans = svc.plan_methods(conn, ["M0001"])
    geo = hardgate.geometry(conn)
    svc.check_stores(d, s)
    dev_run = svc.measure_store(conn, plans, d, survivorship=False, bench=geo.bench)
    sv_run = svc.measure_store(conn, plans, s, survivorship=True, bench=geo.bench)
    return svc.compare(plans, dev_run, sv_run, geo), dev_run, sv_run, geo


# ---- the measurement ---------------------------------------------------------------------------


def test_the_collapse_lowers_the_result_and_nothing_is_written(lab, dev_data, sv_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    before, notes = _untouched(conn), _insights(conn)
    reports, dev_run, sv_run, _geo = _measure(conn, dev_data, sv_data, tmp_path, monkeypatch)
    (rep,) = reports
    assert [r.variant.candidate.id for r in rep.rows] == ["M0001-A", "M0001-B"]
    a = rep.rows[0]
    assert a.reproduced is True
    assert a.variant.funded and a.dev.funded
    assert a.sv.total_return < a.dev.total_return
    assert a.sv.yearly < a.dev.yearly
    assert rep.worse >= 1
    assert a.dev.dsr is not None and a.variant.var_trials is not None  # moments were recorded
    assert (dev_run.fingerprint, sv_run.fingerprint) == ("smoke", "smoke-sv")
    assert _untouched(conn) == before and _insights(conn) == notes


def test_the_dev_rerun_runs_at_the_recorded_capital_and_funding(lab, dev_data, sv_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    seen: list = []
    real = svc.dev.run_registry

    def spy(*a, **k):
        seen.append((k.get("initial_idr"), k.get("contributions")))
        return real(*a, **k)

    monkeypatch.setattr(svc.dev, "run_registry", spy)
    _measure(conn, dev_data, sv_data, tmp_path, monkeypatch)
    n = int(store.trials_of(conn, "M0001")[0]["n"])
    want = (runner.recorded_capital(conn, n), runner.recorded_contributions(conn, n))
    assert seen == [want, want]  # one call per store: both variants share capital and schedule


def test_the_two_stores_are_never_alive_at_once(lab, dev_data, sv_data, recorded, tmp_path, monkeypatch):
    _, path = lab
    d, s = _dirs(tmp_path)
    alive: list[int] = []
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data, s: sv_data}, alive))
    argv = ["lab", "--db", str(path), "survivorship", "M0001", "--store", str(d), "--sv-store", str(s), "--no-journal"]
    assert cli.main(argv) == 0
    assert alive == [0, 0]  # the dev store was gone before the check store was loaded


def test_dsr_says_so_when_no_var_trials_was_recorded(lab, dev_data, sv_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    monkeypatch.setattr(svc.store, "moments_of", lambda c, n: None)
    reports, dev_run, sv_run, geo = _measure(conn, dev_data, sv_data, tmp_path, monkeypatch)
    (rep,) = reports
    assert all(r.dev.dsr is None and r.sv.dsr is None for r in rep.rows)
    assert "no recorded var_trials" in svc.format_report(rep, dev_run, sv_run, len(geo.folds))


def test_a_variant_gone_from_the_file_is_listed_not_run(lab, dev_data, sv_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    only_a = _method((_cand("M0001-A", PARAMS_A),))
    monkeypatch.setattr(svc, "discover", lambda: {"M0001": (only_a, HERE)})
    reports, dev_run, sv_run, geo = _measure(conn, dev_data, sv_data, tmp_path, monkeypatch)
    (rep,) = reports
    assert rep.missing == ("M0001-B",)
    assert [r.variant.candidate.id for r in rep.rows] == ["M0001-A"]
    assert "no longer in the method file): M0001-B" in svc.format_report(rep, dev_run, sv_run, len(geo.folds))


def test_high_coverage_matches_the_walkforward_command():
    assert svc.HIGH_COVERAGE == lab_command.HIGH_COVERAGE


# ---- the command -------------------------------------------------------------------------------


def test_cli_reports_journals_and_writes_the_grid(lab, dev_data, sv_data, recorded, tmp_path, monkeypatch, capsys):
    conn, path = lab
    before, notes = _untouched(conn), _insights(conn)
    d, s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data, s: sv_data}))
    grid = tmp_path / "out" / "grid.csv"
    argv = ["lab", "--db", str(path), "survivorship", "m0001", "M0001",
            "--store", str(d), "--sv-store", str(s), "--csv", str(grid)]
    assert cli.main(argv) == 0
    out = capsys.readouterr().out
    assert "report only" in out and "survivorship" in out and "reproduces it" in out
    assert "walk-forward vs the recorded SPY hold (4 folds)" in out
    assert f"Lab N (dev trials): {before[0]} before, {before[0]} after" in out
    assert _untouched(conn) == before
    assert _insights(conn) == notes + 1  # one method, named twice: one observation
    rows = list(csv.reader(grid.open(encoding="utf-8")))
    assert rows[0] == list(svc.CSV_HEADER)
    assert [(r[1], r[2]) for r in rows[1:]] == [
        ("M0001-A", "dev"), ("M0001-A", "survivorship"), ("M0001-B", "dev"), ("M0001-B", "survivorship"),
    ]
    assert float(rows[2][rows[0].index("total_return")]) < float(rows[1][rows[0].index("total_return")])


def test_no_journal_writes_nothing(lab, dev_data, sv_data, recorded, tmp_path, monkeypatch, capsys):
    conn, path = lab
    before, notes = _untouched(conn), _insights(conn)
    d, s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data, s: sv_data}))
    argv = ["lab", "--db", str(path), "survivorship", "M0001", "--store", str(d), "--sv-store", str(s), "--no-journal"]
    assert cli.main(argv) == 0
    assert "No journal entry" in capsys.readouterr().out
    assert _untouched(conn) == before and _insights(conn) == notes


def test_the_journal_entry_is_plain_words(lab, dev_data, sv_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    (rep,), *_ = _measure(conn, dev_data, sv_data, tmp_path, monkeypatch)
    before = _untouched(conn)
    with conn:
        entry = svc.journal(conn, rep)
    row = conn.execute("SELECT * FROM insights WHERE id = ?", (entry,)).fetchone()
    assert row["kind"] == "observation" and row["method_id"] == "M0001"
    assert row["title"] == "Quiet stocks held equally: what the missing companies did to it"
    for text in (row["title"], row["body"]):
        for banned in ("M0001", "`", "_", "DSR", "MAR", "var"):
            assert banned not in text, banned
    assert "flattered it" in row["body"]
    assert "count of tries did not move" in row["body"]
    assert _untouched(conn) == before


# ---- refusals ----------------------------------------------------------------------------------


def _boom(*a, **k):
    raise AssertionError("a store must not be loaded for a refusal")


@pytest.mark.parametrize(
    ("dev_manifest", "sv_manifest"),
    [
        (None, {"fingerprint": "smoke-sv"}),                                   # check store unmarked
        (None, {"purpose": "something-else"}),                                 # wrong marker
        ({"purpose": svc.SV_PURPOSE}, None),                                   # the check store as --store
    ],
)
def test_cli_refuses_a_wrong_store_pair_before_loading(lab, recorded, tmp_path, monkeypatch, dev_manifest, sv_manifest):
    _, path = lab
    d, s = _dirs(tmp_path, dev_manifest, sv_manifest)
    monkeypatch.setattr(research, "load_store", _boom)
    assert cli.main(["lab", "--db", str(path), "survivorship", "M0001", "--store", str(d), "--sv-store", str(s)]) == 2


def test_cli_refuses_the_same_store_twice_and_a_missing_manifest(lab, recorded, tmp_path, monkeypatch):
    _, path = lab
    d, _s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store", _boom)
    assert cli.main(["lab", "--db", str(path), "survivorship", "M0001", "--store", str(d), "--sv-store", str(d)]) == 2
    assert cli.main(["lab", "--db", str(path), "survivorship", "M0001", "--store", str(d),
                     "--sv-store", str(tmp_path / "nowhere")]) == 2


def test_cli_refuses_unknown_or_unrun_methods_before_loading(lab, recorded, tmp_path, monkeypatch):
    _, path = lab
    d, s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store", _boom)
    for mid in ("M9999", "H-P7A", "nonsense"):
        assert cli.main(["lab", "--db", str(path), "survivorship", mid, "--store", str(d), "--sv-store", str(s)]) == 2
    conn = store.connect(path)
    try:
        other = Method(id="M0002", name="never ran", family="factor", source_kind="knowledge",
                       source_ref="", hypothesis="h", expected_failure="f",
                       candidates=(Candidate(id="M0002-A", family="M0002", rules=MONTHLY_HOLD_FRAC,
                                             allocator=FACTOR, params=PARAMS_A, rationale="t",
                                             added=date(2026, 10, 10), owner_inputs=()),))
        monkeypatch.setattr(svc, "discover", lambda: {"M0002": (other, HERE)})
        with pytest.raises(store.LabError, match="has no dev trial"):
            svc.plan_methods(conn, ["M0002"])
    finally:
        conn.close()


def test_a_trial_with_no_recorded_capital_is_refused_before_loading(lab, recorded, monkeypatch):
    conn, _ = lab

    def none(c, n):
        return None

    monkeypatch.setattr(store, "provenance_of", none)
    with pytest.raises(store.LabError, match="no recorded starting capital"):
        svc.plan_methods(conn, ["M0001"])


def test_load_checked_refuses_a_wrong_purpose_or_window(dev_data, sv_data, tmp_path, monkeypatch):
    d, s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data, s: sv_data}))
    with pytest.raises(store.LabError, match="not 'survivorship-check'"):
        svc.load_checked(d, survivorship=True)  # the manifest peek can lie; the loaded data cannot
    with pytest.raises(store.LabError, match="carries none"):
        svc.load_checked(s, survivorship=False)
    t = tmp_path / "test-store"
    monkeypatch.setattr(research, "load_store", _loader({t: smoke_test_data()}))
    with pytest.raises(store.LabError, match="dev window"):
        svc.load_checked(t, survivorship=False)
    monkeypatch.setattr(research, "load_store", _loader({t: ValueError("declares the 'test' window")}))
    with pytest.raises(store.LabError, match="test-window store is refused"):
        svc.load_checked(t, survivorship=False)


def test_cli_exits_2_when_the_dev_store_is_a_test_window_store(lab, recorded, sv_data, tmp_path, monkeypatch):
    _, path = lab
    d, s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: ValueError("declares the 'test' window"), s: sv_data}))
    before = _untouched(store.connect(path))
    assert cli.main(["lab", "--db", str(path), "survivorship", "M0001", "--store", str(d), "--sv-store", str(s)]) == 2
    assert _untouched(store.connect(path)) == before


# ---- opt-in: the real stores -------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("SEER_LAB_SURVIVORSHIP_LIVE"),
    reason="set SEER_LAB_SURVIVORSHIP_LIVE=1 to run lab survivorship M0069 on the real stores",
)
def test_lab_survivorship_m0069_on_the_real_stores(tmp_path, capsys):
    dev_dir = Path(os.environ.get("SEER_RESEARCH_STORE") or "/home/miftah/seer/engine/.research")
    sv_dir = Path(os.environ.get("SEER_RESEARCH_SV_STORE") or "/home/miftah/seer/engine/.research-sv")
    live_db = Path(os.environ.get("SEER_LAB_DB") or store.COMMITTED_DB)
    db = tmp_path / "lab.sqlite"
    src = sqlite3.connect(f"file:{live_db}?mode=ro", uri=True)
    dst = sqlite3.connect(db)
    src.backup(dst)  # a consistent copy even while a Sera batch writes; the source is never written
    src.close()
    dst.close()
    argv = ["lab", "--db", str(db), "survivorship", "M0069", "--store", str(dev_dir),
            "--sv-store", str(sv_dir), "--no-journal"]
    assert cli.main(argv) == 0
    out = capsys.readouterr().out
    assert "lab survivorship M0069" in out and "No journal entry" in out
```
**Impact:** Test-only. One run of the fixture method (2 variants, 473 sessions) plus two re-runs
per test: seconds. If the plain-words check trips on a phrase (the banned list includes `_` and
`var`), adjust the **body wording** in `insight_text`, not the test. One example: "variant" must
not appear, because it contains "var". The text above uses "version" for that reason. The live
test is skipped unless its env var is set.

### Step 4: Lint, full suite, smoke run, commit
See Verification. Commit on `feature/eodhd-survivorship-market` only. Stage exactly the three
files by path, never `git add -A`, because the store symlinks are untracked:
```bash
cd /home/miftah/.worktrees/seer/eodhd-survivorship-market
git add engine/src/seer_engine/lab/survivorship_check.py engine/src/seer_engine/commands/lab.py engine/tests/test_lab_survivorship.py
# (commands/lab.py carries the 2a-2d insertions only: the docstring entry, subparser, handler, dispatch)
git commit -m "lab: survivorship report command (lab survivorship) -- dev vs survivorship-check store, report only

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```
Do not merge or push to `main` from this phase. The coordinator or Phase 5 owns integration.

## Verification

**Build/lint:** `engine/.venv/bin/ruff check engine`. The base (`5e5ec5c`) already carries one
finding, `F841` at `engine/tests/test_lab_prereg.py:722` (`done` is unused). It is not this
phase's, so leave it alone (see Handoffs). The phase passes when ruff reports exactly that one
finding and nothing in the three files this phase touches.

**Pre-validated:** the Step 1-3 code blocks were extracted verbatim from this file and run on a
scratch copy of the worktree. That copy carried a stand-in for phase 1 (`ResearchData.purpose:
str | None = None` and `SV_STORE_DIR`) and the Step 2 insertions. Results:
`test_lab_survivorship.py` 17 passed and 1 skipped (the live test), `test_cli.py` passed, and
the full suite failed only on two scratch-layout artifacts. ruff reported nothing on the new code.
After that run the reconciler pointed `SV_PURPOSE` at `research.SURVIVORSHIP_PURPOSE`, rewrote
`peek_purpose` over `research.declared_purpose` (dropping `import json`) and added the Step 2d
docstring entry; the refusal tests cover the rewritten path.
**Tests (new file first, then the full suite):**
```bash
cd /home/miftah/.worktrees/seer/eodhd-survivorship-market
engine/.venv/bin/python -m pytest engine/tests/test_lab_survivorship.py -q -n0
engine/.venv/bin/python -m pytest engine/tests/test_lab_costs.py engine/tests/test_cli.py engine/tests/test_lab_walkforward.py -q
engine/.venv/bin/python -m pytest engine/tests -q
```
**Manual check (smoke run on real data, writes nothing):**
```bash
cd /home/miftah/.worktrees/seer/eodhd-survivorship-market
# phase 2 (parallel) may be swapping the SV store in: wait until no build is running, with a
# Monitor until-loop, never a foreground sleep:
#   until ! pgrep -f '[s]eer_engine.*(survivorship_store|market_series)'; do sleep 60; done
# If the SV load still fails its sha check (phase 2 swapped the store in mid-load), wait for quiet
# again and rerun once; only a second failure is a finding.
SCR=$(mktemp -d)
engine/.venv/bin/python -c "import sqlite3,sys; s=sqlite3.connect('file:/home/miftah/seer/lab/lab.sqlite?mode=ro', uri=True); d=sqlite3.connect(sys.argv[1]); s.backup(d); d.close(); s.close()" "$SCR/lab.sqlite"
/usr/bin/time -v engine/.venv/bin/python -m seer_engine -v lab --db "$SCR/lab.sqlite" survivorship M0069 \
  --store /home/miftah/seer/engine/.research \
  --sv-store /home/miftah/seer/engine/.research-sv \
  --no-journal --csv "$SCR/m0069.csv" 2>&1 | tee "$SCR/m0069.log"
grep -E "Maximum resident set size|Elapsed" "$SCR/m0069.log"
sha256sum /home/miftah/seer/engine/.research/manifest.json /home/miftah/seer/engine/.research-sv/manifest.json   # same before and after
```
Run it in the background (`run_in_background`) if it takes several minutes. M0069 has 5 funded
dev variants, so the run is two store loads and 10 backtests. Check the following:
- every variant prints `the dev re-run reproduces it`. If one does not, record that in the
  handoff and do not "fix" it here. It means the dev store or the engine moved since the trial,
  and that belongs to phase 5's reading.
- the log shows `dev store released` before `survivorship store ... loaded`.
- the peak RSS is roughly one store's worth, not two.
- `N before == N after` and the looks line likewise.
- `$SCR/m0069.csv` has 11 lines (a header plus 5 variants × 2 stores).
- the main checkout's DB is untouched. It was opened read-only, and the copy is in `$SCR`.

**Exit criteria:** `lab survivorship` runs end to end on the fixture stores in tests. It lowers the
fixture method's result on the collapse store. It refuses an unmarked or wrongly marked check
store, a marked dev store, the same store twice, a test-window store, an unknown method and an
unrun method, all before any store load, except the test-window case, which `load_store` itself
refuses. It never moves N, looks, `trials`, `trial_moments`, `trial_funding` or `trial_provenance`.
The smoke run on M0069 against the real stores completes with `--no-journal`. The full engine suite
and ruff pass.

## Handoffs

- **Phase 5 (R5, R6):** runs `lab survivorship` on M0069 and then the roster, the near misses and
  the dividend-date methods, with `--csv docs/lab/survivorship/<name>.csv` and without
  `--no-journal`, under `SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite`. One journal observation per
  method is this phase's output. The cross-method `synthesis` insight is Phase 5's.
- **Phase 5 (docs):** add `lab survivorship ...` to the explore skill's Promotion step 0b and its
  command block. The `commands/lab.py` docstring entry is this phase's (Step 2d): phase 5 touches
  no engine code.
- **Phase 1 (resolved):** `SV_PURPOSE` is `research.SURVIVORSHIP_PURPOSE`; `peek_purpose` reuses
  `research.declared_purpose`; a plain `research.load_store(sv_dir)` loads the marked store (phase
  1's `_read_manifest` only validates the key).
- **Unowned drive-by:** the pre-existing ruff `F841` at `engine/tests/test_lab_prereg.py:722` is
  left for whoever next touches that file.
- **Not done here, deliberately:** this command does not call `runner.preflight_data` or
  `hardgate.pin_dev_store`. Both are trial-writing-path guards, and the check store is meant to
  carry different prices. Phase 1 may also have put its purpose refusal into `preflight_data`. A
  method that needs a calendar, fundamentals or series the check store lacks shows up as a
  different number, not a refusal. Phase 1 carries `fundamentals.csv` byte for byte and re-matches
  the announcements; market series reach the SV store in phase 5 and the dev store post-landing (no
  method measured in this set reads them).

## Rollback

Revert the single commit. Nothing persistent is produced except journal observations, if someone
ran the command without `--no-journal`. The journal is append-only, so a wrong observation is
answered by a correcting insight. The stores and the trial tables are never written.
