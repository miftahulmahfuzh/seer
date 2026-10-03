# Phase 10: Dev report and pre-registration renderers

**Plan set:** `TRADE_RULES_DEV_SEARCH_PLAN.md`
**Analysis:** `20261003-195606-T7R2_code_analyzer.md`
**Satisfies:** R6 (the report's content: every handover §7.6 item), R7 (the pre-registration file's content), R8 (determinism, byte-identical renders, purity glob)
**Depends on:** Phase 9 (and through it phases 1, 2, 3)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/backtest`

---

## Goal

After this phase a pure module, `backtest/dev_report.py`, turns a `DevReport` value into the five
committed P7a files: the dev report Markdown, the rows CSV, the month-end curves CSV, the frontier
SVG, and the P7b pre-registration file (finalists exactly specified, or "none eligible"). Every
item of handover §7.6 is in the Markdown. Two renders of the same value are byte-identical. The
run date appears only inside sibling-file names (links), never as a fact. Nothing writes files and
nothing runs a candidate: phase 12 builds the value and writes the files.

## Interface Contract

**Deletes:** nothing
**Renames:** nothing
**Creates** (all in `engine/src/seer_engine/backtest/dev_report.py`, new):
- `DevReport` (frozen dataclass): **exactly the index contract's 14 fields, in that order**
  (`run_date, store_fingerprint, store_counts, unserved, survivorship, registry_digest, rows,
  finalists, spy_window, spy_price, spy_tr, top_years, curves, dsr`). No extra field, no default.
- `report_stem(run_date) -> str` = `f"{run_date.isoformat()}-p7a-dev-exploration"` (TypeError for a non-date or a datetime)
- `preregistration_name(run_date) -> str` = `f"{run_date.isoformat()}-p7b-preregistration.md"`
- `render_markdown(r) -> str`, `rows_csv(r) -> str`, `curves_csv(r) -> str`, `frontier_svg(r) -> str`,
  `render_preregistration(r) -> str`. Each validates `r` first (`ValueError`, or `dev.DevWindowError`
  which is a `ValueError`) and returns text ending in exactly one `"\n"`.
- Public constants: `TEST_START = date(2015, 10, 19)`, `TEST_SLICE_START = date(2018, 1, 2)`,
  `MIN_TRADES = 100`, `MAX_FINALISTS = 3`, `TOP_YEARS = 5`,
  `STORE_COUNT_KEYS = ("bar_rows", "symbols_requested", "symbols_served", "dividend_rows", "fx_rows")`
  (the **set** equals phase 12's; order here is only the render order),
  `FAIL_ORDER = ("beats SPY TR", "max DD <= 15%", "PF >= 1.3", ">= 100 trades", "owner inputs")`
  (phase 9's `DevRow.failed` labels, verbatim), `ROWS_CSV_HEADER` (below), `FENCE`, `MEMBERS_TEXT`.
- Private helpers the tests import: `_month_end_points` (same rule as phase 12's
  `month_end_curve`, used for the SPY columns), `_top_by_mar` (none-eligible table only).

`ROWS_CSV_HEADER` (phase 13's `p7a_facts.py` `COLS` should map onto these names):

```
id,family,allocator,rules,start,end,total_return,cagr,max_drawdown,profit_factor,trades,exposure,turnover,cost_drag,costs_usd,dividends_usd,sharpe,worst_year,worst_year_return,spy_tr_total_return,spy_tr_cagr,spy_price_total_return,mar,beats_spy,eligible,finalist,failed,owner_inputs
```

**How `DevReport` is constructed (phase 12 owns this; this phase only renders and checks it):**
`commands/backtest_dev.execute` builds it with keyword arguments, exactly as phase 12's plan
already does. `_validate` enforces what phase 12's construction produces:
- `rows` non-empty, ≤ `dev.MAX_CANDIDATES`, unique ids, every `row.end` passes
  `dev.check_dev_session` (D9 guard number three), `start <= end`;
- `store_counts` has every `STORE_COUNT_KEYS` key (extra keys are rendered after, sorted);
- `unserved` sorted and unique;
- `spy_window == (min(row.start), dev.DEV_END)`; both SPY curves' `snapshots[1].date` and
  `snapshots[-1].date` equal its ends;
- `finalists` ≤ 3, each one of `rows` (equality), eligible, families unique;
- `top_years` ≤ 5 entries, ids ⊆ row ids (order free: phase 12 puts finalists first, then by MAR);
- `curves` ids == row ids in registry order, each non-empty, last date ≤ `DEV_END`;
- `dsr` ids ⊆ row ids; with finalists, `dsr` ids == finalist ids in order; without, ≤ 1 entry.

**Requires (from earlier phases):**
- Phase 9 `seer_engine.backtest.dev`: `DEV_END`, `FX_START`, `MEMBERSHIP_START`, `MAX_CANDIDATES`,
  `Candidate` (fields `id, family, rules, allocator, params, rationale, added, owner_inputs`),
  `DevRow` (fields `candidate, start, end, stats, spy_tr, spy_price, beats_spy, mar, eligible,
  failed`, keyword-constructible), `check_dev_session` (raises a `ValueError` subclass after
  `DEV_END`), `finalists` (tests only). `DevRow.failed` labels are exactly `FAIL_ORDER`'s strings.
- Phase 3 `seer_engine.backtest.book_runner.RunStats` (fields `metrics, exposure, turnover,
  costs_usd, gross_pnl_usd, cost_drag, dividends_usd, sharpe, daily_returns, year_returns,
  worst_year`; tests construct it by keyword).
- Phase 2 `seer_engine.strategies.allocator.Allocator` (`runtime_checkable`; `.id`, `.holds(p)`,
  `.symbols(p)`, `.uses_members(p)`).
- Phase 1 `seer_engine.sim.rules`: `TradeRules` (a dataclass; `dataclasses.fields` order is the
  render order), `DESIGN_V0`, `describe_rules`; tests also use `MONTHLY_HOLD`, `DAILY_SWITCH`,
  `SWING_T20`.
- Existing, read-only: `metrics.to_fixed`, `fmt_signed_pct`, `fmt_pct`, `fmt_pf`, `fmt_num`,
  `curve_metrics`, `DASH`; `report._table`, `report._esc`, `report._nice_ticks` (private helpers,
  imported the same way `wf_report.py` and `b_report.py` already import them);
  `runner.INITIAL_IDR`, `runner.YearGap`; `benchmark.BenchmarkCurve`; `tuning.MAX_DRAWDOWN`,
  `tuning.MIN_PROFIT_FACTOR`.

**Leaves alone (owned by others):** every existing module (frozen set and the rest);
`backtest/dev.py` (9), `backtest/registry.py` (11), `commands/backtest_dev.py` and
`backtest/io.py` (12), docs (13).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/dev_report.py:1` | create | the whole module (Step 1) |
| `engine/tests/test_backtest_dev_report.py:1` | create | 32 tests (Step 2) |

No existing file changes. `tests/test_strategy_purity.py` globs `backtest/*.py`, so the new module
is covered without editing it.

## Decisions (recorded for the reconciler)

1. **No builder in this module.** Phase 12's plan already derives `top_years`, `curves` and `dsr` in
   `commands/backtest_dev.py` (`month_end_curve`, `top_years`, `deflated_sharpes`). Duplicating that
   here would give two sources of truth, so `dev_report` only renders and validates. An earlier draft
   of this phase had `build_dev_report`; it was dropped for this reason.
2. **`top_years` follows phase 12's rule** (plan index D-G: the finalists first, in finalist
   order, then the highest MAR by `(−MAR, id)`, up to 5), which keeps every finalist's
   year-by-year in the report. The section heading is "Year by year, top 5", and its text says
   "the finalists, then the highest MAR". `_validate` checks only the size and the ids.
3. **The run date appears only inside sibling-file names.** The Markdown links
   `<stem>-rows.csv`, `<stem>-curves.csv` and `<stem>-frontier.svg`; the pre-registration links
   `../backtests/<stem>.md` and `../backtests/<stem>-frontier.svg`. A valid link must name the file,
   and the file name carries the run date by contract. No other run-date text exists; the test
   `test_no_run_date_in_content_outside_file_names` proves it, and that two run dates give identical
   content once the stem is masked. **Phase 13's `p7a_dates.py` check "the run date must not appear
   inside any file" must mask the stem first** (see Handoffs).
4. **Params rendering.** `params.as_dict()` where it exists: every family's params, `AParams`,
   and phase 2's `PicksParams`/`BlendParams`/`VolTargetParams` (flattened, prefixed keys). The
   encoding is the shared one (plan index D-F: `"SYM:n"`, `"none"`, comma-joined sorted symbol
   tuples). Params without `as_dict()` (none in the registry; test fakes only) are rendered by
   walking dataclass fields in declaration order, allocators and strategies as `"<id>"`, never
   `repr` (which may print memory addresses). Anything else is a `TypeError`.
5. **Instruments.** For an `Allocator`: held = `holds(params)`, read = `symbols(params)`, plus
   "S&P 500 ∪ Nasdaq-100 members (point in time)" when `uses_members(params)`. For a bracket
   `Strategy` (`design-v0`, e.g. REF-A-V0): members only.
6. **Frontier.** x = max DD, y = CAGR, one dot per row with both values (others counted in the
   subtitle), classes `pt` / `el` (eligible, not kept) / `fi` (finalist, labelled), SPY total-return
   on `spy_window` as a labelled diamond, the 15% limit as a dashed line. Coordinates `f"{x:.1f}"`,
   ticks from `report._nice_ticks`, labels through `to_fixed`. Light and dark palettes like
   `report.equity_svg`.
7. **SPY columns in the curves CSV** use `_month_end_points`, which is the same formula as phase 12's
   `month_end_curve` (`float(equity / base)` in `Decimal`, last snapshot per month), so the SPY and
   candidate columns are comparable.
8. **The gate in the pre-registration** is design §1 applied on the main test window
   (2015-10-19 → data end). The 2018-01-02 slice is "reported beside it, information only" (D3).
9. **`added` dates are rendered** (Candidates table and each finalist block), because D6's per-append
   timestamp is part of the protocol record. They are registry data, not wall-clock.

## Implementation Steps

### Step 1: The renderer module
**File:** `engine/src/seer_engine/backtest/dev_report.py:1` (new)
**Change:** create the module. Sections of the Markdown, in order: title and D8 headline; Data
(store fingerprint and counts, unserved count); Method (D1, D3, D6 with the registry digest, D7 with
the trial count, D8, D9; simulation and metric definitions; every rule set used, through
`sim.rules.describe_rules`); Candidates (registry listing: allocator, rules, params, owner inputs,
added, rationale); Results (one row per candidate: return, CAGR, max DD, PF, trades, exposure,
turnover, cost drag, worst year, SPY TR on the same window, MAR, dev gate, owner inputs; link to the
rows CSV); Frontier (SVG link); SPY on the development window (price-only and total-return; link to
the curves CSV); Year by year, top 5 (plus SPY TR); Survivorship bias (D4 single-stock optimism,
ticker reuse, members-trading candidates, the `YearGap` table, the unserved symbols); Multiple
testing (trial count, deflated-Sharpe note and table); Finalists (D8) (failure counts, one sentence
per finalist, eligible-but-not-kept, or "None eligible"); Plain statements (≥ 100 trades excludes
low-turnover designs by construction; FX before 1999-01-04 only affects starting capital; the
owner's 2026-11-01 date vs §1, earliest about February 2027, SPY directly allowed).
The pre-registration: header (report link, registry digest, store fingerprint, trials, the
no-change rule); per finalist: id, family, allocator id, rule set id, rationale, added, instruments
held and read, owner inputs, the dev result sentence, the params JSON (`indent=2`), every
`TradeRules` field as a table and as a `TradeRules(...)` literal, the D4 note when it trades
members; then Test window (2015-10-19 → data end, 2018-01-02 slice beside it), Gate (§1
thresholds), Proposed design-§5 revision (D10: `design-v0` unchanged, each finalist rule set through
`describe_rules`, what stays from §5), the D4 paragraph and the owner's date. With no finalist:
"None eligible", P7b does not run, links to the frontier and the report, failure counts, the top 5
by MAR with why each failed, D4 and the owner's date.
**Code:**
```python
"""P7a development-window report and the P7b pre-registration file (handover §7.6, §7.7, D7, D8, D10).

Pure: takes a ``DevReport`` value and returns text. ``io.write_dev_report`` (phase 12) writes the
files. ``commands/backtest_dev.py`` (phase 12) builds the ``DevReport`` value: it runs the
registry, derives ``finalists`` (``dev.finalists``), ``top_years``, ``curves`` and ``dsr``, and
this module renders it after checking it is consistent (``_validate``).

Deterministic (plan invariant 6):
- every number goes through ``metrics.to_fixed`` (exact decimal rounding) or ``str(int)``;
- SVG coordinates are ``f"{x:.1f}"`` of floats computed the same way every time;
- iteration is in tuple (registry) order or an explicitly sorted order;
- ``run_date`` appears only inside the names of sibling files (links), never as a fact, so
  the content of a re-run with the same run date is byte-identical.

Nothing here reads a session after ``dev.DEV_END``: ``_validate`` rejects any row, curve or SPY
window that ends later (D9, a third guard after the store and the runner).
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from seer_engine.backtest.benchmark import BenchmarkCurve
from seer_engine.backtest.dev import (
    DEV_END,
    FX_START,
    MAX_CANDIDATES,
    MEMBERSHIP_START,
    Candidate,
    DevRow,
    check_dev_session,
)
from seer_engine.backtest.metrics import (
    DASH,
    curve_metrics,
    fmt_num,
    fmt_pct,
    fmt_pf,
    fmt_signed_pct,
    to_fixed,
)
from seer_engine.backtest.report import _esc, _nice_ticks, _table
from seer_engine.backtest.runner import INITIAL_IDR, YearGap
from seer_engine.backtest.tuning import MAX_DRAWDOWN, MIN_PROFIT_FACTOR
from seer_engine.sim.rules import DESIGN_V0, TradeRules, describe_rules
from seer_engine.strategies.allocator import Allocator

TEST_START = date(2015, 10, 19)  # P7b's main test window starts here (the session after DEV_END; D3)
TEST_SLICE_START = date(2018, 1, 2)  # the slice reported beside it, for comparison with A2 and B
MIN_TRADES = 100  # design §1 item 2, applied on dev by D8 (phase 9's ">= 100 trades" label)
MAX_FINALISTS = 3  # D8
TOP_YEARS = 5  # §7.6: "year by year for the top candidates"; phase 12 picks them (finalists first)
STORE_COUNT_KEYS: tuple[str, ...] = ("bar_rows", "symbols_requested", "symbols_served", "dividend_rows", "fx_rows")
FAIL_ORDER: tuple[str, ...] = ("beats SPY TR", "max DD <= 15%", "PF >= 1.3", ">= 100 trades", "owner inputs")
ROWS_CSV_HEADER = (
    "id,family,allocator,rules,start,end,total_return,cagr,max_drawdown,profit_factor,trades,"
    "exposure,turnover,cost_drag,costs_usd,dividends_usd,sharpe,worst_year,worst_year_return,"
    "spy_tr_total_return,spy_tr_cagr,spy_price_total_return,mar,beats_spy,eligible,finalist,failed,owner_inputs"
)
FENCE = "`" * 3
MEMBERS_TEXT = "S&P 500 ∪ Nasdaq-100 members (point in time)"

_COUNT_LABELS: tuple[tuple[str, str], ...] = (
    ("bar_rows", "Bar rows"),
    ("symbols_requested", "Symbols requested from yfinance"),
    ("symbols_served", "Symbols served"),
    ("dividend_rows", "Dividend rows"),
    ("fx_rows", "USD/IDR rows"),
)


# --------------------------------------------------------------------------- the value


@dataclass(frozen=True)
class DevReport:
    run_date: date  # appears in FILE NAMES only, never in rendered content
    store_fingerprint: str
    store_counts: Mapping[str, int]  # STORE_COUNT_KEYS (extra keys are rendered after, sorted)
    unserved: tuple[str, ...]  # sorted
    survivorship: tuple[YearGap, ...]  # runner.survivorship(market, MEMBERSHIP_START, DEV_END)
    registry_digest: str  # sha256 of backtest/registry.py's source bytes
    rows: tuple[DevRow, ...]  # registry order
    finalists: tuple[DevRow, ...]  # dev.finalists(rows)
    spy_window: tuple[date, date]  # (earliest row start, DEV_END)
    spy_price: BenchmarkCurve  # on spy_window
    spy_tr: BenchmarkCurve  # on spy_window
    top_years: tuple[tuple[str, tuple[tuple[int, float], ...]], ...]  # <= 5 rows: finalists, then by MAR
    curves: tuple[tuple[str, tuple[tuple[date, float], ...]], ...]  # month-end, one per row, registry order
    dsr: tuple[tuple[str, float | None], ...]  # per finalist, or the best-Sharpe row when none


def report_stem(run_date: date) -> str:
    """File stem of the report set: ``<run_date>-p7a-dev-exploration``."""
    return f"{_as_date('run_date', run_date).isoformat()}-p7a-dev-exploration"


def preregistration_name(run_date: date) -> str:
    """File name of the pre-registration: ``<run_date>-p7b-preregistration.md``."""
    return f"{_as_date('run_date', run_date).isoformat()}-p7b-preregistration.md"


# --------------------------------------------------------------------------- derived values


def _month_end_points(snapshots: Sequence[Any]) -> tuple[tuple[date, float], ...]:
    """The last snapshot of each calendar month as ``(date, float(equity / first equity))``,
    ascending; the same rule as phase 12's ``month_end_curve`` (used here for the SPY columns).
    ``snapshots`` are anything with ``date`` and a Decimal ``equity_usd``, in date order."""
    if not snapshots:
        raise ValueError("a curve needs at least one snapshot")
    base = snapshots[0].equity_usd
    if base <= 0:
        raise ValueError(f"the first snapshot's equity must be > 0, got {base}")
    last: dict[tuple[int, int], Any] = {}
    for s in snapshots:
        last[(s.date.year, s.date.month)] = s
    return tuple((s.date, float(s.equity_usd / base)) for _, s in sorted(last.items()))


def _year_returns(snapshots: Sequence[Any]) -> tuple[tuple[int, float], ...]:
    """Calendar-year returns, last snapshot of a year over the last snapshot of the year before
    (``snapshots[0]``, the starting cash, for the first year). The years are those of
    ``snapshots[1:]``. Same definition as ``book_runner.RunStats.year_returns``."""
    prev = float(snapshots[0].equity_usd)
    last_by_year: dict[int, float] = {}
    for s in snapshots[1:]:
        last_by_year[s.date.year] = float(s.equity_usd)
    out: list[tuple[int, float]] = []
    for year in sorted(last_by_year):
        value = last_by_year[year]
        out.append((year, value / prev - 1.0))
        prev = value
    return tuple(out)


def _top_by_mar(rows: Sequence[DevRow], n: int = TOP_YEARS) -> tuple[DevRow, ...]:
    """The ``n`` rows with the highest MAR (rows without one left out), ties by candidate id."""
    ranked = sorted((r for r in rows if r.mar is not None), key=lambda r: (-r.mar, r.candidate.id))
    return tuple(ranked[:n])


# --------------------------------------------------------------------------- validation


def _as_date(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    return d


def _validate(r: DevReport) -> None:
    _as_date("run_date", r.run_date)
    if not r.rows:
        raise ValueError("a dev report needs at least one row")
    if len(r.rows) > MAX_CANDIDATES:
        raise ValueError(f"{len(r.rows)} rows exceed the registry cap of {MAX_CANDIDATES}")
    ids = [row.candidate.id for row in r.rows]
    if len(set(ids)) != len(ids):
        raise ValueError(f"candidate ids are not unique: {ids}")
    for row in r.rows:
        check_dev_session(row.end)
        if row.start > row.end:
            raise ValueError(f"{row.candidate.id}: start {row.start} is after end {row.end}")
    missing = [k for k in STORE_COUNT_KEYS if k not in r.store_counts]
    if missing:
        raise ValueError(f"store_counts lacks {missing}")
    if list(r.unserved) != sorted(set(r.unserved)):
        raise ValueError("unserved must be sorted and unique")
    earliest = min(row.start for row in r.rows)
    if r.spy_window != (earliest, DEV_END):
        raise ValueError(f"spy_window must be ({earliest}, {DEV_END}), got {r.spy_window}")
    for curve in (r.spy_price, r.spy_tr):
        if len(curve.snapshots) < 2:
            raise ValueError(f"{curve.name}: needs the starting snapshot and at least one session")
        if curve.snapshots[1].date != r.spy_window[0] or curve.snapshots[-1].date != r.spy_window[1]:
            raise ValueError(f"{curve.name}: snapshots do not span the spy_window {r.spy_window}")
    if len(r.finalists) > MAX_FINALISTS:
        raise ValueError(f"{len(r.finalists)} finalists exceed {MAX_FINALISTS}")
    families = [f.candidate.family for f in r.finalists]
    if len(set(families)) != len(families):
        raise ValueError(f"finalists repeat a family: {families}")
    for f in r.finalists:
        if f not in r.rows:
            raise ValueError(f"finalist {f.candidate.id} is not one of the rows")
        if not f.eligible:
            raise ValueError(f"finalist {f.candidate.id} is not eligible")
    known = set(ids)
    if len(r.top_years) > TOP_YEARS or any(cid not in known for cid, _ in r.top_years):
        raise ValueError("top_years must name at most 5 of the rows")
    if [cid for cid, _ in r.curves] != ids:
        raise ValueError("curves must hold one curve per row, in row order")
    for cid, points in r.curves:
        if not points:
            raise ValueError(f"{cid}: empty curve")
        check_dev_session(points[-1][0])
    if any(cid not in known for cid, _ in r.dsr):
        raise ValueError("dsr names a candidate that is not a row")
    if r.finalists and [cid for cid, _ in r.dsr] != [f.candidate.id for f in r.finalists]:
        raise ValueError("dsr must hold one entry per finalist, in finalist order")
    if not r.finalists and len(r.dsr) > 1:
        raise ValueError("with no finalist, dsr holds at most the best-Sharpe row")


# --------------------------------------------------------------------------- candidate facts


def _param_value(v: Any) -> Any:
    """A JSON-ready, deterministic rendering of one parameter value. Never ``repr`` of an
    arbitrary object, which may hold a memory address.

    - an object with ``as_dict()`` (every family's params, ``AParams``) -> that dict, key order kept;
    - a dataclass (``BlendParams``, ``BlendPart``, ``VolTargetParams``, ``PicksParams``) -> its
      fields in declaration order, each rendered recursively;
    - an allocator or strategy object (non-dataclass with a ``str`` ``id``) -> ``"<id>"``;
    - tuples and lists -> lists; ``None`` -> null; ``bool`` -> ``"true"``/``"false"``;
      ``str``/``int``/``float``/``Decimal`` -> ``str(v)``.
    """
    as_dict = getattr(v, "as_dict", None)
    if callable(as_dict):
        d = as_dict()
        if not isinstance(d, dict):
            raise TypeError(f"{type(v).__name__}.as_dict() returned {type(d).__name__}, not dict")
        return d
    if is_dataclass(v) and not isinstance(v, type):
        return {f.name: _param_value(getattr(v, f.name)) for f in fields(v)}
    if isinstance(getattr(v, "id", None), str):
        return f"<{v.id}>"
    if isinstance(v, (tuple, list)):
        return [_param_value(x) for x in v]
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (str, int, float, Decimal)):
        return str(v)
    raise TypeError(f"cannot render params of type {type(v).__name__}: no as_dict() and not a dataclass")


def _params_dict(params: Any) -> dict[str, Any]:
    """``params.as_dict()`` (the contracted rendering), or the field walk of ``_param_value``
    for params without one (the phase-2 overlays). Always a dict."""
    d = _param_value(params)
    if not isinstance(d, dict):
        raise TypeError(f"cannot render params of type {type(params).__name__}: no as_dict() and not a dataclass")
    return d


def _params_json(params: Any) -> str:
    return json.dumps(_params_dict(params))  # key order kept, never sorted (report.params_line)


def _instruments(c: Candidate) -> tuple[tuple[str, ...], tuple[str, ...], bool]:
    """``(held fixed symbols, read fixed symbols, uses index members)``. A bracket ``Strategy``
    (``design-v0`` candidates) reads and holds members only."""
    a = c.allocator
    if isinstance(a, Allocator):
        return tuple(a.holds(c.params)), tuple(a.symbols(c.params)), bool(a.uses_members(c.params))
    return (), (), True


def _instrument_text(symbols: Sequence[str], members: bool) -> str:
    parts = [", ".join(symbols)] if symbols else []
    if members:
        parts.append(MEMBERS_TEXT)
    return " + ".join(parts) if parts else "none"


def _owner_text(c: Candidate) -> str:
    return ", ".join(c.owner_inputs) if c.owner_inputs else "none"


def _rule_value(v: Any) -> str:
    if v is None:
        return "none"
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _rules_literal(rules: TradeRules) -> str:
    """``TradeRules(id='…', engine='…', …)``: every field, in field order, as ``repr``."""
    return "TradeRules(" + ", ".join(f"{f.name}={getattr(rules, f.name)!r}" for f in fields(rules)) + ")"


def _distinct_rules(rows: Sequence[DevRow]) -> list[tuple[TradeRules, list[str]]]:
    """Each rule set in first-appearance order, with the ids that use it."""
    out: list[tuple[TradeRules, list[str]]] = []
    for row in rows:
        for rules, ids in out:
            if rules == row.candidate.rules:
                ids.append(row.candidate.id)
                break
        else:
            out.append((row.candidate.rules, [row.candidate.id]))
    return out


# --------------------------------------------------------------------------- formatting


def _span(start: date, end: date) -> str:
    return f"{start.isoformat()} → {end.isoformat()}"


def _worst(row: DevRow) -> str:
    w = row.stats.worst_year
    return DASH if w is None else f"{w[0]} {fmt_signed_pct(w[1])}"


def _turnover(v: float) -> str:
    return f"{to_fixed(v, 2)}×"


def _gate(row: DevRow, finalist_ids: set[str]) -> str:
    if row.candidate.id in finalist_ids:
        return "finalist"
    if row.eligible:
        return "eligible"
    return "fail: " + "; ".join(row.failed)


def _f(v: float | None, digits: int = 6) -> str:
    """A CSV float: fixed decimals, ``inf`` for an infinite profit factor, empty for None."""
    if v is None:
        return ""
    if v == math.inf:
        return "inf"
    return to_fixed(v, digits)


def _csv_field(text: str) -> str:
    if any(ch in text for ch in ',"\n'):
        return '"' + text.replace('"', '""') + '"'
    return text


def _fail_counts(rows: Sequence[DevRow]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for row in rows:
        for label in row.failed:
            counts[label] = counts.get(label, 0) + 1
    order = [k for k in FAIL_ORDER if k in counts] + sorted(k for k in counts if k not in FAIL_ORDER)
    return [(k, counts[k]) for k in order]


def _eligible_ranked(rows: Sequence[DevRow]) -> list[DevRow]:
    return sorted(
        (r for r in rows if r.eligible),
        key=lambda r: (r.mar is None, -(r.mar if r.mar is not None else 0.0), r.candidate.id),
    )


def _result_sentence(row: DevRow) -> str:
    m = row.stats.metrics
    return (
        f"on {_span(row.start, row.end)} it returned {fmt_signed_pct(m.total_return)} against SPY "
        f"total-return {fmt_signed_pct(row.spy_tr.total_return)}, with CAGR {fmt_signed_pct(m.cagr)}, "
        f"max drawdown {fmt_pct(m.max_drawdown)}, profit factor {fmt_pf(m.profit_factor)}, "
        f"{m.trades:,} closed trades and MAR {fmt_num(row.mar)}"
    )


# --------------------------------------------------------------------------- markdown sections


def _headline(r: DevReport) -> list[str]:
    n = len(r.rows)
    eligible = sum(1 for row in r.rows if row.eligible)
    if r.finalists:
        names = ", ".join(f"`{f.candidate.id}`" for f in r.finalists)
        verdict = (
            f"**D8 result:** {eligible} of {n} candidates are eligible on the development window. "
            f"Finalists: {names}. P7b runs each of them once on the test window."
        )
    else:
        verdict = (
            f"**D8 result:** none of the {n} candidates is eligible on the development window. "
            "**P7b does not run.** The frontier below is the evidence for the owner's next decision."
        )
    return [
        f"# P7a development-window exploration (data through {DEV_END.isoformat()})",
        "",
        verdict,
        "",
        f"No number in this report comes from a session after {DEV_END.isoformat()} (handover D9).",
        "",
    ]


def _data_section(r: DevReport) -> list[str]:
    lines = [
        "## Data",
        "",
        "The research store (`engine/.research/`, local and gitignored, never Neon; handover D5) is "
        "built by `python -m seer_engine research_store` and verified against its manifest on load.",
        "",
        f"- Store fingerprint: `{r.store_fingerprint}`",
    ]
    for key, label in _COUNT_LABELS:
        lines.append(f"- {label}: {r.store_counts[key]:,}")
    for key in sorted(k for k in r.store_counts if k not in STORE_COUNT_KEYS):
        lines.append(f"- {key}: {r.store_counts[key]:,}")
    lines += [
        f"- Every bar, dividend and FX row in the store is dated on or before {DEV_END.isoformat()}.",
        f"- S&P 500 membership from {MEMBERSHIP_START.isoformat()} and Nasdaq-100 membership from "
        "2007-02-01, point in time (`engine/data/`).",
        f"- Symbols yfinance returned nothing for: {len(r.unserved):,} (listed under Survivorship bias).",
        "",
    ]
    return lines


def _method_section(r: DevReport) -> list[str]:
    n = len(r.rows)
    lines = [
        "## Method",
        "",
        "**Protocol** (handover §3, fixed before any result existed):",
        "",
        "- **D1, split.** P7a explores on the development window only and ends with a pre-registration "
        "file naming at most 3 finalists. P7b runs those finalists once on the test window and applies "
        "the gate. No candidate here ran on the test window.",
        "- **D3, windows.** A candidate's window starts at the first NYSE session where every instrument "
        "it reads has enough bars for its lookback through the previous session; a candidate that "
        f"trades index members also needs a data date on or after {MEMBERSHIP_START.isoformat()}. Every "
        f"window ends {DEV_END.isoformat()}. Each candidate's own window is in its row; the earliest "
        f"start is {r.spy_window[0].isoformat()}.",
        "- **D6, registry.** Every candidate is fixed in `engine/src/seer_engine/backtest/registry.py`, "
        f"committed before this run, append-only, at most {MAX_CANDIDATES} entries, with fixed "
        f"parameters. sha256 of that file for this run: `{r.registry_digest}`.",
        f"- **D7, every try reported.** One row per registry candidate, none hidden. Trials: {n}.",
        "- **D8, finalists.** Eligible: beats SPY total-return over its own development window, max "
        f"drawdown ≤ {fmt_pct(MAX_DRAWDOWN, 0)}, profit factor ≥ {to_fixed(MIN_PROFIT_FACTOR, 1)}, "
        f"≥ {MIN_TRADES} closed trades, and no owner input (Gotrade-executable under the conservative "
        "defaults). Ranked by MAR = CAGR ÷ max drawdown, highest first, ties by candidate id. The top "
        f"{MAX_FINALISTS} are kept, at most one per family.",
        f"- **D9, test window untouched.** The dev runner refuses any session after {DEV_END.isoformat()}, "
        "and the store holds no row after it.",
        "",
        "**Simulation:**",
        "",
        f"- Each candidate starts a fresh book of {INITIAL_IDR:,} IDR, converted to USD once at the "
        f"USD/IDR rate on the later of its start and {FX_START.isoformat()}. Everything after that is USD.",
        "- Rule sets on engine `book` run on `seer_engine.sim.book`. `design-v0` runs on the unchanged "
        "design-§5 simulator (`run_backtest`). Cost per side, dividends, cadence and entry are as each "
        "rule set says (below).",
        "- SPY benchmarks: `benchmark.spy_curves` on each candidate's own window and starting cash, with "
        "SPY dividends from the research store. Price-only ignores dividends; total-return reinvests them.",
        "",
        "**Metrics:**",
        "",
        "- Return = last / first equity − 1. CAGR uses Actual/365.25. Max drawdown is measured on "
        "per-session equity.",
        "- A closed trade is one holding episode (shares 0 → > 0 → 0), dividends included in its P/L. "
        "Trims, adds and idle-instrument episodes are not trades. Profit factor = gross win / gross loss "
        "over closed trades.",
        "- Exposure = mean over sessions of invested value (idle instrument excluded) / equity. Turnover = "
        "traded notional / mean equity, per year. Cost drag = costs / gross P/L before costs (a dash when "
        "gross P/L ≤ 0).",
        "- Worst year: the lowest calendar-year return (last close of a year over the last close of the "
        "year before, or over the starting cash).",
        "",
        "**Rule sets used** (`seer_engine.sim.rules.describe_rules`):",
        "",
    ]
    for rules, ids in _distinct_rules(r.rows):
        lines.append(f"- `{rules.id}`, used by {len(ids)} candidate{'s' if len(ids) != 1 else ''}:")
        for text in describe_rules(rules):
            lines.append(f"  - {text}")
    lines.append("")
    return lines


def _candidates_section(r: DevReport) -> list[str]:
    rows = []
    for i, row in enumerate(r.rows, start=1):
        c = row.candidate
        rows.append(
            [
                str(i),
                f"`{c.id}`",
                c.family,
                f"`{c.allocator.id}`",
                f"`{c.rules.id}`",
                f"`{_params_json(c.params)}`",
                _owner_text(c),
                c.added.isoformat(),
                c.rationale,
            ]
        )
    return [
        "## Candidates",
        "",
        "The registry in order, exactly as run. A candidate with owner inputs needs the owner to verify a "
        "Gotrade feature first, so it cannot be a finalist (D8).",
        "",
        *_table(
            ["#", "ID", "Family", "Allocator", "Rules", "Parameters", "Owner inputs", "Added", "Rationale"],
            ["r", "l", "l", "l", "l", "l", "l", "l", "l"],
            rows,
        ),
        "",
    ]


def _results_section(r: DevReport) -> list[str]:
    stem = report_stem(r.run_date)
    finalist_ids = {f.candidate.id for f in r.finalists}
    rows = []
    for row in r.rows:
        m = row.stats.metrics
        rows.append(
            [
                f"`{row.candidate.id}`",
                _span(row.start, row.end),
                fmt_signed_pct(m.total_return),
                fmt_signed_pct(m.cagr),
                fmt_pct(m.max_drawdown),
                fmt_pf(m.profit_factor),
                f"{m.trades:,}",
                fmt_pct(row.stats.exposure),
                _turnover(row.stats.turnover),
                fmt_pct(row.stats.cost_drag),
                _worst(row),
                fmt_signed_pct(row.spy_tr.total_return),
                fmt_num(row.mar),
                _gate(row, finalist_ids),
                _owner_text(row.candidate),
            ]
        )
    return [
        "## Results",
        "",
        "Every candidate, in registry order. SPY TR is total-return SPY on the candidate's own window and "
        "starting cash. Dev gate is D8 on the development window: `finalist`, `eligible` (eligible but not "
        "kept), or the conditions failed.",
        "",
        *_table(
            [
                "ID",
                "Window",
                "Return",
                "CAGR",
                "Max DD",
                "PF",
                "Trades",
                "Exposure",
                "Turnover",
                "Cost drag",
                "Worst year",
                "SPY TR",
                "MAR",
                "Dev gate",
                "Owner inputs",
            ],
            ["l", "l", "r", "r", "r", "r", "r", "r", "r", "r", "l", "r", "r", "l", "l"],
            rows,
        ),
        "",
        f"Every column at full precision: [`{stem}-rows.csv`]({stem}-rows.csv).",
        "",
    ]


def _frontier_section(r: DevReport) -> list[str]:
    stem = report_stem(r.run_date)
    return [
        "## Frontier",
        "",
        f"![CAGR against max drawdown for every candidate, SPY total-return marked]({stem}-frontier.svg)",
        "",
        "Each dot is one candidate on its own window. Dots right of the dashed 15% line fail D8 on "
        "drawdown. The diamond is total-return SPY on "
        f"{_span(r.spy_window[0], r.spy_window[1])}. Finalists are labelled.",
        "",
    ]


def _spy_section(r: DevReport) -> list[str]:
    stem = report_stem(r.run_date)
    rows = []
    for curve, label in ((r.spy_price, "SPY price-only"), (r.spy_tr, "SPY total-return")):
        m = curve_metrics(curve)
        rows.append(
            [
                label,
                _span(r.spy_window[0], r.spy_window[1]),
                fmt_signed_pct(m.total_return),
                fmt_signed_pct(m.cagr),
                fmt_pct(m.max_drawdown),
                format(curve.dividends_usd, ",.2f"),
            ]
        )
    return [
        "## SPY on the development window",
        "",
        "Buy whole SPY shares at the first session's open after the 0.1% cost, hold, and mark at each "
        "close, from the earliest candidate start. Total-return reinvests each dividend at the ex-date "
        "close.",
        "",
        *_table(
            ["Curve", "Window", "Return", "CAGR", "Max DD", "Dividends (USD)"],
            ["l", "l", "r", "r", "r", "r"],
            rows,
        ),
        "",
        "Month-end values, each normalized to 1.0 at its own start, for every candidate and both SPY "
        f"curves: [`{stem}-curves.csv`]({stem}-curves.csv).",
        "",
    ]


def _years_section(r: DevReport) -> list[str]:
    out = ["## Year by year, top 5", ""]
    if not r.top_years:
        return out + ["No candidate has a defined MAR.", ""]
    spy_years = dict(_year_returns(r.spy_tr.snapshots))
    per = [dict(years) for _, years in r.top_years]
    all_years = sorted(set(spy_years).union(*[set(p) for p in per]))
    rows = []
    for y in all_years:
        cells = [str(y)]
        for p in per:
            cells.append(fmt_signed_pct(p[y]) if y in p else DASH)
        cells.append(fmt_signed_pct(spy_years[y]) if y in spy_years else DASH)
        rows.append(cells)
    header = ["Year", *[f"`{cid}`" for cid, _ in r.top_years], "SPY TR"]
    return out + [
        "Calendar-year returns of up to five candidates: the finalists, then the highest MAR, eligible "
        "or not. A first year is partial (from the window start). SPY TR is total-return SPY on "
        f"{_span(r.spy_window[0], r.spy_window[1])}.",
        "",
        *_table(header, ["l"] + ["r"] * (len(header) - 1), rows),
        "",
    ]


def _survivorship_section(r: DevReport) -> list[str]:
    rows: list[list[str]] = []
    tot_member = tot_missing = tot_never = tot_other = 0
    for g in r.survivorship:
        rows.append(
            [
                str(g.year),
                f"{g.member_sessions:,}",
                f"{g.missing:,}",
                f"{g.missing_never_fetched:,}",
                f"{g.missing_other:,}",
                fmt_pct(g.missing / g.member_sessions, 2) if g.member_sessions else DASH,
            ]
        )
        tot_member += g.member_sessions
        tot_missing += g.missing
        tot_never += g.missing_never_fetched
        tot_other += g.missing_other
    rows.append(
        [
            "All",
            f"{tot_member:,}",
            f"{tot_missing:,}",
            f"{tot_never:,}",
            f"{tot_other:,}",
            fmt_pct(tot_missing / tot_member, 2) if tot_member else DASH,
        ]
    )
    member_ids = [row.candidate.id for row in r.rows if _instruments(row.candidate)[2]]
    users = ", ".join(f"`{cid}`" for cid in member_ids) if member_ids else "none"
    return [
        "## Survivorship bias",
        "",
        "yfinance serves no delisted tickers. An index member that was delisted, acquired or went "
        "bankrupt before the store was built has no bars, so no candidate could ever hold it, including "
        "on the way down. **Development results on single stocks are therefore optimistic** (handover "
        "D4), by an amount this data cannot measure. ETF-only candidates have no survivorship bias.",
        "",
        "A second gap the counts below cannot see: **ticker reuse.** When a ticker passes to a different "
        "company, a past member's index interval is matched to the new company's prices. That member "
        "then looks served while its prices are not the member's. The store does not detect reuse, so "
        "the table understates the gap.",
        "",
        f"Candidates that trade index members: {users}.",
        "",
        "Per year, the (member, session) pairs with no bar. \"Never fetched\" are members with no bars "
        "at all; \"Other\" are members with bars elsewhere but none on that session (halts, sessions "
        "before a listing).",
        "",
        *_table(
            ["Year", "Member-sessions", "Missing", "Never fetched", "Other", "Missing share"],
            ["l", "r", "r", "r", "r", "r"],
            rows,
        ),
        "",
        f"Symbols yfinance returned nothing for ({len(r.unserved):,}): "
        + (", ".join(r.unserved) if r.unserved else "none")
        + ".",
        "",
    ]


def _multiple_testing_section(r: DevReport) -> list[str]:
    n = len(r.rows)
    by_id = {row.candidate.id: row for row in r.rows}
    out = [
        "## Multiple testing",
        "",
        f"- Trials: {n} candidates, every one reported here (D7). Reference candidates count as trials.",
        "- The best of many tries looks good partly by luck. The deflated Sharpe ratio (Bailey and López "
        "de Prado, 2014) is the probability that a candidate's true Sharpe ratio is above zero once the "
        "number of trials, the spread of Sharpe ratios across them, and the skew and fat tails of its "
        "daily returns are allowed for. Values below 0.95 do not clear the usual bar.",
        "",
    ]
    if not r.dsr:
        return out + ["No candidate has a defined Sharpe ratio, so no deflated Sharpe is shown.", ""]
    lead = "Finalists:" if r.finalists else "No finalist; shown for the candidate with the highest Sharpe ratio:"
    rows = [
        [f"`{cid}`", fmt_num(by_id[cid].stats.sharpe), fmt_num(value, 3)]
        for cid, value in r.dsr
    ]
    return out + [
        lead,
        "",
        *_table(["Candidate", "Sharpe (annualized)", "Deflated Sharpe"], ["l", "r", "r"], rows),
        "",
    ]


def _finalists_section(r: DevReport) -> list[str]:
    out = ["## Finalists (D8)", ""]
    counts = _fail_counts(r.rows)
    if counts:
        out += [
            "Candidates failing each D8 condition (a candidate can fail several):",
            "",
            *_table(["Condition", "Candidates failing"], ["l", "r"], [[k, f"{v:,}"] for k, v in counts]),
            "",
        ]
    eligible = _eligible_ranked(r.rows)
    if not r.finalists:
        return out + [
            "**None eligible.** No candidate met every D8 condition on the development window, so there "
            "are no finalists and P7b does not run. The frontier above shows what drawdown was reachable "
            "at a SPY-beating return; the owner decides next with it.",
            "",
        ]
    for i, f in enumerate(r.finalists, start=1):
        c = f.candidate
        rank = eligible.index(f) + 1
        out.append(
            f"{i}. `{c.id}` ({c.family}, rules `{c.rules.id}`) is eligible: {_result_sentence(f)}. It needs "
            f"no owner input, and it ranks {rank} of {len(eligible)} eligible by MAR, the best of family "
            f"{c.family}."
        )
    out.append("")
    finalist_families = {f.candidate.family: f.candidate.id for f in r.finalists}
    left = [row for row in eligible if row not in r.finalists]
    if left:
        out += ["Eligible but not kept:", ""]
        for row in left:
            fam = row.candidate.family
            why = (
                f"family {fam} already has `{finalist_families[fam]}`"
                if fam in finalist_families
                else f"outside the top {MAX_FINALISTS}"
            )
            out.append(f"- `{row.candidate.id}`: {why}.")
        out.append("")
    return out


def _owner_date_lines() -> list[str]:
    return [
        "- **The owner's 2026-11-01 date and design §1.** The owner plans to put 20,000,000 IDR of real "
        "money in on 2026-11-01. Design §1 is law: real money needs a strategy that has passed the "
        "backtest gate and then at least 3 months and at least 100 closed trades of forward paper "
        "trading. No strategy has passed, and P4 paper trading has not started. Even if a P7b finalist "
        "passes, the earliest §1-compliant date is about 3 months after its paper trading starts: around "
        "February 2027 at the soonest. §1 does not move to fit the date. The owner remains free to put "
        "the 20,000,000 IDR into SPY directly on 2026-11-01; that is the benchmark, and it needs no Seer "
        "approval.",
    ]


def _plain_section(r: DevReport) -> list[str]:
    only_trades = sum(1 for row in r.rows if tuple(row.failed) == (">= 100 trades",))
    return [
        "## Plain statements",
        "",
        f"- **§1's ≥ {MIN_TRADES} closed trades rule excludes low-turnover designs by construction.** A "
        "monthly switcher between one or two ETFs makes tens of round trips over the development window, "
        "not hundreds, so it cannot be eligible however good its return and drawdown are. That is design "
        "§1, unchanged, not a tuning choice; such rows are evidence for the owner, not finalists. "
        f"Candidates that failed on the trade count alone: {only_trades}.",
        f"- **FX before {FX_START.isoformat()} only affects starting capital.** USD/IDR exists from "
        f"{FX_START.isoformat()} (Frankfurter). A window that starts earlier converts its starting cash at "
        f"the {FX_START.isoformat()} rate. FX never enters a decision, a trade or the comparison with SPY, "
        "which are all in USD.",
        *_owner_date_lines(),
        "",
    ]


def render_markdown(r: DevReport) -> str:
    """The full dev report as Markdown, ending in exactly one newline."""
    _validate(r)
    out: list[str] = []
    out += _headline(r)
    out += _data_section(r)
    out += _method_section(r)
    out += _candidates_section(r)
    out += _results_section(r)
    out += _frontier_section(r)
    out += _spy_section(r)
    out += _years_section(r)
    out += _survivorship_section(r)
    out += _multiple_testing_section(r)
    out += _finalists_section(r)
    out += _plain_section(r)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- CSV


def rows_csv(r: DevReport) -> str:
    """One line per candidate in registry order, ``ROWS_CSV_HEADER`` columns. Floats at 6 dp
    (``to_fixed``), ``inf`` for an infinite profit factor, empty for None; lists ``;``-joined."""
    _validate(r)
    finalist_ids = {f.candidate.id for f in r.finalists}
    lines = [ROWS_CSV_HEADER]
    for row in r.rows:
        c = row.candidate
        m = row.stats.metrics
        w = row.stats.worst_year
        cells = [
            c.id,
            c.family,
            c.allocator.id,
            c.rules.id,
            row.start.isoformat(),
            row.end.isoformat(),
            _f(m.total_return),
            _f(m.cagr),
            _f(m.max_drawdown),
            _f(m.profit_factor),
            str(m.trades),
            _f(row.stats.exposure),
            _f(row.stats.turnover),
            _f(row.stats.cost_drag),
            _f(row.stats.costs_usd, 4),
            _f(row.stats.dividends_usd, 4),
            _f(row.stats.sharpe),
            "" if w is None else str(w[0]),
            "" if w is None else _f(w[1]),
            _f(row.spy_tr.total_return),
            _f(row.spy_tr.cagr),
            _f(row.spy_price.total_return),
            _f(row.mar),
            "true" if row.beats_spy else "false",
            "true" if row.eligible else "false",
            "true" if c.id in finalist_ids else "false",
            ";".join(row.failed),
            ";".join(c.owner_inputs),
        ]
        lines.append(",".join(_csv_field(x) for x in cells))
    return "\n".join(lines) + "\n"


def curves_csv(r: DevReport) -> str:
    """Month-end values normalized to 1.0 at each curve's own start: ``date``, one column per
    candidate (registry order), then ``spy_price`` and ``spy_tr`` (on ``spy_window``). Rows are
    the sorted union of every curve's month-end dates; a curve without that date is empty."""
    _validate(r)
    columns: list[dict[date, float]] = [dict(points) for _, points in r.curves]
    columns.append(dict(_month_end_points(r.spy_price.snapshots)))
    columns.append(dict(_month_end_points(r.spy_tr.snapshots)))
    all_dates = sorted(set().union(*[set(c) for c in columns]))
    header = ",".join(["date", *[_csv_field(cid) for cid, _ in r.curves], "spy_price", "spy_tr"])
    lines = [header]
    for d in all_dates:
        lines.append(",".join([d.isoformat(), *[_f(c.get(d)) for c in columns]]))
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- SVG

_SVG_W = 960
_SVG_H = 560
_ML, _MR, _MT, _MB = 80, 60, 90, 60
_SVG_STYLE = (
    ".bg{fill:#fcfcfb}.t1{fill:#0b0b0b}.t2{fill:#52514e}"
    ".grid{stroke:#e6e5e0;stroke-width:1}.axis{stroke:#a3a29c;stroke-width:1}"
    ".lim{stroke:#c0392b;stroke-width:1.5;stroke-dasharray:6 4}"
    ".pt{fill:#a3a29c}.el{fill:#2a78d6}.fi{fill:#1baf7a;stroke:#0b0b0b;stroke-width:1}.spy{fill:#eb6834}"
    "@media (prefers-color-scheme: dark){"
    ".bg{fill:#1a1a19}.t1{fill:#ffffff}.t2{fill:#c3c2b7}"
    ".grid{stroke:#33322f}.axis{stroke:#6b6a64}.lim{stroke:#e5675a}"
    ".pt{fill:#6b6a64}.el{fill:#3987e5}.fi{fill:#199e70;stroke:#ffffff}.spy{fill:#d95926}}"
)


def _pct_tick(v: float, step: float) -> str:
    digits = 0 if abs(step * 100 - round(step * 100)) < 1e-9 else 1
    text = to_fixed(v * 100, digits)
    return ("0" if text in ("-0", "-0.0") else text) + "%"


def frontier_svg(r: DevReport) -> str:
    """CAGR (y) against max drawdown (x), one dot per candidate with both, SPY total-return on
    ``spy_window`` as a diamond, the 15% drawdown limit dashed, finalists labelled. Self-contained,
    light and dark palettes, no script."""
    _validate(r)
    finalist_ids = {f.candidate.id for f in r.finalists}
    points = [
        (row, row.stats.metrics.max_drawdown, row.stats.metrics.cagr)
        for row in r.rows
        if row.stats.metrics.max_drawdown is not None and row.stats.metrics.cagr is not None
    ]
    spy = curve_metrics(r.spy_tr)
    spy_point = (spy.max_drawdown, spy.cagr) if spy.max_drawdown is not None and spy.cagr is not None else None
    xs = [p[1] for p in points] + [MAX_DRAWDOWN]
    ys = [p[2] for p in points] + [0.0]
    if spy_point is not None:
        xs.append(spy_point[0])
        ys.append(spy_point[1])
    x_ticks, x_step = _nice_ticks(0.0, max(xs))
    y_ticks, y_step = _nice_ticks(min(ys), max(ys))
    x_lo, x_hi = x_ticks[0], x_ticks[-1]
    y_lo, y_hi = y_ticks[0], y_ticks[-1]
    pw = _SVG_W - _ML - _MR
    ph = _SVG_H - _MT - _MB
    bottom = _MT + ph

    def px(v: float) -> float:
        return _ML + (v - x_lo) / (x_hi - x_lo) * pw

    def py(v: float) -> float:
        return _MT + (y_hi - v) / (y_hi - y_lo) * ph

    n = len(r.rows)
    title = f"Return against drawdown, {n} candidates, development window to {DEV_END.isoformat()}"
    subtitle = (
        f"{len(points)} of {n} plotted, each on its own window; SPY total-return on "
        f"{_span(r.spy_window[0], r.spy_window[1])}."
    )
    if len(points) < n:
        subtitle += f" Not plotted (no CAGR or drawdown): {n - len(points)}."
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_SVG_W} {_SVG_H}" '
        f'width="{_SVG_W}" height="{_SVG_H}" role="img" aria-labelledby="title desc" '
        'font-family="system-ui, -apple-system, Segoe UI, Helvetica, Arial, sans-serif">',
        f'<title id="title">{_esc(title)}</title>',
        '<desc id="desc">Scatter of CAGR against max drawdown for every P7a candidate on the '
        "development window, with total-return SPY and the 15% drawdown limit marked. The values "
        "are in the rows CSV next to this file.</desc>",
        f"<style>{_SVG_STYLE}</style>",
        f'<rect class="bg" x="0" y="0" width="{_SVG_W}" height="{_SVG_H}"/>',
        f'<text class="t1" x="{_ML}" y="24" font-size="16" font-weight="600">{_esc(title)}</text>',
        f'<text class="t2" x="{_ML}" y="42" font-size="12">{_esc(subtitle)}</text>',
    ]
    legend = (("pt", "candidate"), ("el", "eligible, not kept"), ("fi", "finalist"))
    lx = _ML
    for cls, label in legend:
        out.append(f'<circle class="{cls}" cx="{lx + 5}" cy="62" r="5"/>')
        out.append(f'<text class="t2" x="{lx + 15}" y="66" font-size="12">{_esc(label)}</text>')
        lx += 160
    out.append(f'<path class="spy" d="M{lx + 5},56 L{lx + 11},62 L{lx + 5},68 L{lx - 1},62 Z"/>')
    out.append(f'<text class="t2" x="{lx + 17}" y="66" font-size="12">SPY total-return</text>')
    for t in y_ticks:
        y = py(t)
        out.append(f'<line class="grid" x1="{_ML}" y1="{y:.1f}" x2="{_ML + pw}" y2="{y:.1f}"/>')
        out.append(
            f'<text class="t2" x="{_ML - 8}" y="{y + 4:.1f}" font-size="11" text-anchor="end">'
            f"{_esc(_pct_tick(t, y_step))}</text>"
        )
    for t in x_ticks:
        x = px(t)
        out.append(f'<line class="grid" x1="{x:.1f}" y1="{_MT}" x2="{x:.1f}" y2="{bottom}"/>')
        out.append(
            f'<text class="t2" x="{x:.1f}" y="{bottom + 18}" font-size="11" text-anchor="middle">'
            f"{_esc(_pct_tick(t, x_step))}</text>"
        )
    out.append(f'<line class="axis" x1="{_ML}" y1="{bottom}" x2="{_ML + pw}" y2="{bottom}"/>')
    out.append(f'<line class="axis" x1="{_ML}" y1="{_MT}" x2="{_ML}" y2="{bottom}"/>')
    if y_lo < 0 < y_hi:
        y0 = py(0.0)
        out.append(f'<line class="axis" x1="{_ML}" y1="{y0:.1f}" x2="{_ML + pw}" y2="{y0:.1f}"/>')
    lim = px(MAX_DRAWDOWN)
    out.append(f'<line class="lim" x1="{lim:.1f}" y1="{_MT}" x2="{lim:.1f}" y2="{bottom}"/>')
    out.append(
        f'<text class="t2" x="{lim + 4:.1f}" y="{_MT + 12}" font-size="11">'
        f"max drawdown {_esc(fmt_pct(MAX_DRAWDOWN, 0))} (design §1)</text>"
    )
    out.append(
        f'<text class="t2" x="{_ML + pw / 2:.1f}" y="{bottom + 40}" font-size="12" text-anchor="middle">'
        "Max drawdown</text>"
    )
    cy_mid = _MT + ph / 2
    out.append(
        f'<text class="t2" x="24" y="{cy_mid:.1f}" font-size="12" text-anchor="middle" '
        f'transform="rotate(-90 24 {cy_mid:.1f})">CAGR</text>'
    )

    def cls_of(row: DevRow) -> str:
        if row.candidate.id in finalist_ids:
            return "fi"
        return "el" if row.eligible else "pt"

    for layer in ("pt", "el", "fi"):
        for row, dd, cagr in points:
            if cls_of(row) != layer:
                continue
            tip = f"{row.candidate.id}: CAGR {fmt_signed_pct(cagr)}, max drawdown {fmt_pct(dd)}"
            out.append(
                f'<circle class="{layer}" cx="{px(dd):.1f}" cy="{py(cagr):.1f}" r="{6 if layer == "fi" else 4}">'
                f"<title>{_esc(tip)}</title></circle>"
            )
    for row, dd, cagr in points:
        if row.candidate.id in finalist_ids:
            out.append(
                f'<text class="t1" x="{px(dd) + 9:.1f}" y="{py(cagr) - 8:.1f}" font-size="11">'
                f"{_esc(row.candidate.id)}</text>"
            )
    if spy_point is not None:
        sx, sy = px(spy_point[0]), py(spy_point[1])
        tip = f"SPY total-return: CAGR {fmt_signed_pct(spy_point[1])}, max drawdown {fmt_pct(spy_point[0])}"
        out.append(
            f'<path class="spy" d="M{sx:.1f},{sy - 7:.1f} L{sx + 7:.1f},{sy:.1f} L{sx:.1f},{sy + 7:.1f} '
            f'L{sx - 7:.1f},{sy:.1f} Z"><title>{_esc(tip)}</title></path>'
        )
        out.append(
            f'<text class="t1" x="{sx + 10:.1f}" y="{sy + 4:.1f}" font-size="11">SPY total-return</text>'
        )
    out.append("</svg>")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- pre-registration


def _prereg_header(r: DevReport) -> list[str]:
    stem = report_stem(r.run_date)
    return [
        "# P7b pre-registration",
        "",
        f"Written by P7a from the development-window run [`{stem}.md`](../backtests/{stem}.md). "
        f"Registry source sha256 `{r.registry_digest}`; research store fingerprint `{r.store_fingerprint}`; "
        f"{len(r.rows)} trials.",
        "",
        "This file fixes what P7b runs before any test-window number exists (handover D1, D8, D10). "
        "Nothing below may change between this file and P7b. P7b runs each finalist **once** on the test "
        "window and applies the gate. It does not tune, swap or add finalists.",
        "",
    ]


def _fail_table(r: DevReport) -> list[str]:
    counts = _fail_counts(r.rows)
    if not counts:
        return []
    return [
        *_table(["D8 condition", "Candidates failing"], ["l", "r"], [[k, f"{v:,}"] for k, v in counts]),
        "",
    ]


def _d4_lines() -> list[str]:
    return [
        "**Survivorship (handover D4).** Development results on single stocks are optimistic: yfinance "
        "serves no delisted tickers, and a reused ticker can map a past member onto a different company's "
        "prices. ETF-only candidates have no survivorship bias. P7b's test window and forward paper "
        "trading do the proving.",
        "",
    ]


def _finalist_block(i: int, f: DevRow) -> list[str]:
    c = f.candidate
    held, read, members = _instruments(c)
    rules_rows = [[fld.name, _rule_value(getattr(c.rules, fld.name))] for fld in fields(c.rules)]
    out = [
        f"### {i}. `{c.id}`",
        "",
        f"- Family: {c.family}",
        f"- Allocator: `{c.allocator.id}`",
        f"- Rule set: `{c.rules.id}`",
        f"- Rationale (registry): {c.rationale}",
        f"- Added to the registry: {c.added.isoformat()}",
        f"- Instruments held: {_instrument_text(held, members)}",
        f"- Instruments read: {_instrument_text(read, members)}",
        f"- Owner inputs: {_owner_text(c)}",
        f"- Development result: {_result_sentence(f)}.",
        "",
        "Parameters (`params.as_dict()`, in its key order):",
        "",
        FENCE + "json",
        json.dumps(_params_dict(c.params), indent=2),
        FENCE,
        "",
        "Trade rules:",
        "",
        *_table(["Field", "Value"], ["l", "l"], rules_rows),
        "",
        FENCE + "python",
        _rules_literal(c.rules),
        FENCE,
        "",
    ]
    if members:
        out += [
            "This finalist trades index members, so its development result carries the survivorship "
            "caveat below.",
            "",
        ]
    return out


def _revision_section(r: DevReport) -> list[str]:
    out = [
        "## Proposed design-§5 revision (D10)",
        "",
        "P7a only proposes. The design document (`docs/plans/2026-10-03-seer-design.md`) is edited in "
        "P7b, and only for finalists that pass the gate. Design §5 becomes a parameter: each strategy "
        "names one rule set, and backtest and live use exactly that rule set.",
        "",
        "Unchanged: `design-v0`, the closed rules of Strategies A, A2 and B:",
        "",
    ]
    out += [f"- {text}" for text in describe_rules(DESIGN_V0)]
    out.append("")
    for rules, ids in _distinct_rules(r.finalists):
        names = ", ".join(f"`{cid}`" for cid in ids)
        out += [f"### Rule set `{rules.id}` (used by {names})", ""]
        out += [f"- {text}" for text in describe_rules(rules)]
        out.append("")
    out += [
        "What stays from §5 for every rule set: backtest and live use identical rules; 0 picks is always "
        "valid; the cost is 0.1% per side unless the owner verifies a better number.",
        "",
    ]
    return out


def render_preregistration(r: DevReport) -> str:
    """``docs/plans/<run date>-p7b-preregistration.md``: the finalists exactly as P7b must run
    them, the test window, the gate and the proposed design-§5 revision; or, with no finalist, a
    "none eligible" file saying P7b does not run and pointing at the frontier."""
    _validate(r)
    stem = report_stem(r.run_date)
    out = _prereg_header(r)
    if not r.finalists:
        top = _top_by_mar(r.rows)
        out += [
            "## None eligible",
            "",
            "No candidate met every D8 condition on the development window, so there are no finalists and "
            "**P7b does not run** (handover D8, §9).",
            "",
            f"The evidence is the frontier, [`{stem}-frontier.svg`](../backtests/{stem}-frontier.svg), with "
            f"every row in [`{stem}.md`](../backtests/{stem}.md). It shows what drawdown was reachable at a "
            "SPY-beating return on the development window. The owner decides next with it: (b) SPY "
            "buy-and-hold as the champion, (d) Strategy C as forward paper only, or another revision.",
            "",
            *_fail_table(r),
        ]
        if top:
            rows = [
                [
                    f"`{row.candidate.id}`",
                    row.candidate.family,
                    fmt_signed_pct(row.stats.metrics.total_return),
                    fmt_signed_pct(row.spy_tr.total_return),
                    fmt_pct(row.stats.metrics.max_drawdown),
                    fmt_pf(row.stats.metrics.profit_factor),
                    f"{row.stats.metrics.trades:,}",
                    fmt_num(row.mar),
                    "; ".join(row.failed),
                ]
                for row in top
            ]
            out += [
                "The five candidates with the highest MAR, and why each failed:",
                "",
                *_table(
                    ["Candidate", "Family", "Return", "SPY TR", "Max DD", "PF", "Trades", "MAR", "Failed"],
                    ["l", "l", "r", "r", "r", "r", "r", "r", "l"],
                    rows,
                ),
                "",
            ]
        out += _d4_lines()
        out += ["## The owner's date", "", *_owner_date_lines(), ""]
    else:
        out += ["## Finalists", ""]
        for i, f in enumerate(r.finalists, start=1):
            out += _finalist_block(i, f)
        out += [
            "## Test window",
            "",
            f"- Main: {TEST_START.isoformat()} → data end, design §1 item 5's 10-year backtest. The gate "
            "applies here.",
            f"- Reported beside it, information only: {TEST_SLICE_START.isoformat()} → data end, for "
            "comparison with A2 and B.",
            "- Data end is the last bar in Neon `bars` when P7b runs; P7b records it.",
            "- SPY price-only and total-return on the same windows and starting cash.",
            "",
            "## Gate (design §1, thresholds unchanged)",
            "",
            "- Beats total-return SPY over the main test window.",
            f"- Max drawdown ≤ {fmt_pct(MAX_DRAWDOWN, 0)}.",
            f"- Profit factor ≥ {to_fixed(MIN_PROFIT_FACTOR, 1)}.",
            f"- ≥ {MIN_TRADES} closed trades.",
            "- A pass leads to the design-§5 edit and P4 forward paper trading. Real money still needs at "
            f"least 3 months and at least {MIN_TRADES} closed trades of forward paper (design §1 items 1–4).",
            "",
        ]
        out += _revision_section(r)
        out += _d4_lines()
        out += ["## The owner's date", "", *_owner_date_lines(), ""]
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"
```
**Impact:** new pure module; `test_strategy_purity.py` picks it up by glob (no forbidden import,
attribute or call: verified by an AST scan of this exact text). Imports `dev` (phase 9) and through
it phases 1–3. Nothing imports it until phase 12.

### Step 2: The tests
**File:** `engine/tests/test_backtest_dev_report.py:1` (new)
**Change:** 32 tests. The fixture builds a `DevReport` the way phase 12's `execute` does (finalists
from `dev.finalists`, `top_years` finalists-first, month-end curves, `dsr` per finalist) from seven
fake `DevRow`s over 2014-01-02 → 2015-10-16: two eligible F1 rows (one-per-family drop), an
owner-input F2 row (`etf:IEF`), an eligible members F4 row, a failing F7 row, a high-MAR F3 row
that fails only on trades, and a REF row with no CAGR, PF or MAR. Fake allocators implement every
`Allocator` member; fake params have `as_dict()`.
**Code:**
```python
"""Dev report and pre-registration renderers (phase 10; handover §7.6, §7.7, §7.8): every §7.6
section, byte stability, no run date in content, the D8 sentences, the none-eligible files, the
CSVs, the frontier SVG and the report checks, all from fake DevRows on a small synthetic window.
The DevReport is built here the way phase 12's command builds it."""

from __future__ import annotations

import csv
import dataclasses
import io
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from seer_engine import dates
from seer_engine.backtest.benchmark import BenchmarkCurve
from seer_engine.backtest.book_runner import RunStats
from seer_engine.backtest.dev import DEV_END, Candidate, DevRow, finalists
from seer_engine.backtest.dev_report import (
    ROWS_CSV_HEADER,
    TEST_SLICE_START,
    TEST_START,
    DevReport,
    _month_end_points,
    _top_by_mar,
    curves_csv,
    frontier_svg,
    preregistration_name,
    render_markdown,
    render_preregistration,
    report_stem,
    rows_csv,
)
from seer_engine.backtest.metrics import Metrics
from seer_engine.backtest.runner import YearGap
from seer_engine.sim import Snapshot
from seer_engine.sim.rules import DAILY_SWITCH, DESIGN_V0, MONTHLY_HOLD, SWING_T20, describe_rules

D = date.fromisoformat
RUN_DATE = D("2026-10-20")
ADDED = D("2026-10-06")
SPY_START = D("2014-01-02")
LATE_START = D("2014-06-02")
FINGERPRINT = "f" * 64
DIGEST = "d" * 64
COUNTS = {"bar_rows": 1234567, "symbols_requested": 900, "symbols_served": 812, "dividend_rows": 40000, "fx_rows": 4300}
UNSERVED = ("ZZA", "ABK", "MMM1")


@dataclass(frozen=True)
class FakeParams:
    hold: str
    n: int = 20

    def as_dict(self) -> dict[str, str]:
        return {"hold": self.hold, "n": str(self.n)}


class FakeEtf:
    """An Allocator holding one fixed ETF (structurally satisfies strategies.allocator.Allocator)."""

    id = "FAKE"

    def lookback(self, params):
        return params.n

    def symbols(self, params):
        return tuple(sorted({params.hold, "SPY"}))

    def holds(self, params):
        return (params.hold,)

    def uses_members(self, params):
        return False

    def targets(self, history, members, data_date, held, params):
        return ()

    def prepare(self, history):
        return None

    def targets_prepared(self, prepared, members, data_date, held, params):
        return ()


class FakeMembers(FakeEtf):
    id = "FAKEM"

    def symbols(self, params):
        return ("SPY",)

    def holds(self, params):
        return ()

    def uses_members(self, params):
        return True


ETF = FakeEtf()
MEMBERS = FakeMembers()

# id, family, rules, allocator, hold, start, return, cagr, max dd, pf, trades, failed, owner inputs
SPECS = (
    ("F1-A", "F1", MONTHLY_HOLD, ETF, "SPY", SPY_START, 0.30, 0.12, 0.10, 1.6, 140, (), ()),
    ("F1-B", "F1", DAILY_SWITCH, ETF, "QQQ", LATE_START, 0.35, 0.13, 0.12, 1.5, 150, (), ()),
    ("F2-A", "F2", MONTHLY_HOLD, ETF, "IEF", LATE_START, 0.28, 0.11, 0.11, 1.4, 120, ("owner inputs",), ("etf:IEF",)),
    ("F4-A", "F4", MONTHLY_HOLD, MEMBERS, "SPY", LATE_START, 0.40, 0.15, 0.14, 1.35, 200, (), ()),
    (
        "F7-A",
        "F7",
        SWING_T20,
        MEMBERS,
        "SPY",
        LATE_START,
        0.05,
        0.02,
        0.25,
        1.1,
        300,
        ("beats SPY TR", "max DD <= 15%", "PF >= 1.3"),
        (),
    ),
    ("F3-A", "F3", MONTHLY_HOLD, ETF, "SPY", SPY_START, 0.26, 0.10, 0.08, 2.0, 40, (">= 100 trades",), ()),
    (
        "REF-Z",
        "REF",
        MONTHLY_HOLD,
        ETF,
        "SPY",
        SPY_START,
        0.0,
        None,
        0.0,
        None,
        0,
        ("beats SPY TR", "PF >= 1.3", ">= 100 trades"),
        (),
    ),
)
IDS = tuple(s[0] for s in SPECS)


def _equity(i: int, k: int) -> Decimal:
    return Decimal(10000 + i * (k + 1) + (i % (k + 3)) * 5).quantize(Decimal("0.0001"))


def _snapshots(start: date, k: int) -> tuple[Snapshot, ...]:
    days = [dates.prev_session(start), *dates.sessions(start, DEV_END)]
    return tuple(Snapshot(d, _equity(i, k), _equity(i, k)) for i, d in enumerate(days))


def _run(spec, k: int, *, all_fail: bool = False) -> tuple[tuple[Snapshot, ...], DevRow]:
    cid, family, rules, alloc, hold, start, ret, cagr, dd, pf, trades, failed, owner = spec
    if all_fail and not failed:
        failed = ("beats SPY TR",)
    cand = Candidate(
        id=cid,
        family=family,
        rules=rules,
        allocator=alloc,
        params=FakeParams(hold=hold),
        rationale=f"Rationale for {cid}, with a comma",
        added=ADDED,
        owner_inputs=owner,
    )
    stats = RunStats(
        metrics=Metrics(
            total_return=ret,
            win_rate=0.5,
            profit_factor=pf,
            max_drawdown=dd,
            trades=trades,
            months=20.0,
            cagr=cagr,
        ),
        exposure=0.5 + k / 100,
        turnover=2.0 + k,
        costs_usd=10.0 + k,
        gross_pnl_usd=100.0,
        cost_drag=(10.0 + k) / 100.0,
        dividends_usd=5.0,
        sharpe=0.25 * k - 0.5,
        daily_returns=(0.001 * k, -0.002, 0.003),
        year_returns=((2014, ret / 2), (2015, ret / 3)),
        worst_year=(2015, ret / 3),
    )
    spy_tr = Metrics(total_return=0.25, win_rate=None, profit_factor=None, max_drawdown=0.12, trades=0, months=20.0, cagr=0.1)
    spy_price = Metrics(total_return=0.22, win_rate=None, profit_factor=None, max_drawdown=0.13, trades=0, months=20.0, cagr=0.09)
    row = DevRow(
        candidate=cand,
        start=start,
        end=DEV_END,
        stats=stats,
        spy_tr=spy_tr,
        spy_price=spy_price,
        beats_spy=ret > 0.25,
        mar=None if cagr is None or dd == 0 else cagr / dd,
        eligible=not failed,
        failed=tuple(failed),
    )
    return _snapshots(start, k), row


def _spy(name: str, k: int) -> BenchmarkCurve:
    return BenchmarkCurve(
        name=name, snapshots=_snapshots(SPY_START, k), shares=10, cash=Decimal("1.0000"), dividends_usd=Decimal("12.3400")
    )


def _top_years(rows, finals, k=5):
    """Phase 12's rule: the finalists first, then the remaining rows by (-MAR, id), up to k."""
    chosen = [r.candidate.id for r in finals][:k]
    for r in sorted((r for r in rows if r.mar is not None), key=lambda r: (-r.mar, r.candidate.id)):
        if len(chosen) >= k:
            break
        if r.candidate.id not in chosen:
            chosen.append(r.candidate.id)
    by_id = {r.candidate.id: r for r in rows}
    return tuple((cid, tuple(by_id[cid].stats.year_returns)) for cid in chosen)


def _report(*, all_fail: bool = False, run_date: date = RUN_DATE) -> DevReport:
    runs = [_run(s, k, all_fail=all_fail) for k, s in enumerate(SPECS)]
    rows = tuple(row for _, row in runs)
    finals = finalists(rows)
    if finals:
        dsr = tuple((f.candidate.id, 0.5 + i / 10) for i, f in enumerate(finals))
    else:
        best = min(rows, key=lambda r: (-r.stats.sharpe, r.candidate.id))
        dsr = ((best.candidate.id, 0.123),)
    return DevReport(
        run_date=run_date,
        store_fingerprint=FINGERPRINT,
        store_counts=COUNTS,
        unserved=tuple(sorted(UNSERVED)),
        survivorship=(YearGap(2014, 1000, 50, 30, 20), YearGap(2015, 800, 40, 25, 15)),
        registry_digest=DIGEST,
        rows=rows,
        finalists=finals,
        spy_window=(SPY_START, DEV_END),
        spy_price=_spy("SPY price-only", 1),
        spy_tr=_spy("SPY total-return", 2),
        top_years=_top_years(rows, finals),
        curves=tuple((row.candidate.id, _month_end_points(snaps)) for snaps, row in runs),
        dsr=dsr,
    )


def _section(md: str, heading: str) -> str:
    start = md.index(f"\n## {heading}\n")
    end = md.find("\n## ", start + 1)
    return md[start : end if end != -1 else len(md)]


# --------------------------------------------------------------------------- names and windows


def test_report_stem_and_preregistration_name():
    assert report_stem(RUN_DATE) == "2026-10-20-p7a-dev-exploration"
    assert preregistration_name(RUN_DATE) == "2026-10-20-p7b-preregistration.md"
    with pytest.raises(TypeError):
        report_stem("2026-10-20")


def test_test_window_starts_the_session_after_dev_end():
    assert TEST_START == dates.next_session(DEV_END)
    assert dates.is_session(TEST_SLICE_START)


# --------------------------------------------------------------------------- helpers


def test_the_fixture_matches_d8():
    r = _report()
    assert [f.candidate.id for f in r.finalists] == ["F1-A", "F4-A"]  # F1-B loses to F1-A (one per family)
    assert [cid for cid, _ in r.top_years] == ["F1-A", "F4-A", "F3-A", "F1-B", "F2-A"]
    assert _report(all_fail=True).finalists == ()


def test_top_by_mar_skips_rows_without_mar_and_breaks_ties_by_id():
    r = _report()
    rows = [dataclasses.replace(row, mar=1.0) if row.candidate.id in ("F2-A", "F1-B") else row for row in r.rows]
    assert [row.candidate.id for row in _top_by_mar(rows, 10)] == ["F3-A", "F1-A", "F4-A", "F1-B", "F2-A", "F7-A"]


def test_month_end_points_keeps_the_last_snapshot_of_each_month():
    snaps = [
        Snapshot(D("2015-08-28"), Decimal("100"), Decimal("100")),
        Snapshot(D("2015-08-31"), Decimal("110"), Decimal("110")),
        Snapshot(D("2015-09-01"), Decimal("90"), Decimal("90")),
        Snapshot(D("2015-09-30"), Decimal("120"), Decimal("120")),
        Snapshot(D("2015-10-01"), Decimal("130"), Decimal("130")),
    ]
    assert _month_end_points(snaps) == ((D("2015-08-31"), 1.1), (D("2015-09-30"), 1.2), (D("2015-10-01"), 1.3))
    with pytest.raises(ValueError):
        _month_end_points([])


# --------------------------------------------------------------------------- validation


def _bad_reports():
    r = _report()
    late_row = dataclasses.replace(r.rows[0], end=D("2015-10-19"))
    return [
        ("after-dev-end", dataclasses.replace(r, rows=(late_row, *r.rows[1:]))),
        ("finalist-not-eligible", dataclasses.replace(r, finalists=(r.rows[4],))),
        ("duplicate-ids", dataclasses.replace(r, rows=(*r.rows, r.rows[0]))),
        ("curves-mismatch", dataclasses.replace(r, curves=r.curves[1:])),
        ("spy-window", dataclasses.replace(r, spy_window=(D("2014-01-03"), DEV_END))),
        ("store-counts", dataclasses.replace(r, store_counts={"bar_rows": 1})),
        ("unsorted-unserved", dataclasses.replace(r, unserved=("ZZA", "ABK"))),
        ("dsr-not-finalists", dataclasses.replace(r, dsr=(("F1-B", 0.5),))),
        ("top-years-unknown", dataclasses.replace(r, top_years=(("NOPE", ()),))),
        ("too-many-finalists", dataclasses.replace(r, finalists=(r.rows[0], r.rows[1], r.rows[3], r.rows[0]))),
    ]


@pytest.mark.parametrize("name,report", _bad_reports(), ids=[n for n, _ in _bad_reports()])
def test_every_renderer_rejects_an_invalid_report(name, report):
    for render in (render_markdown, rows_csv, curves_csv, frontier_svg, render_preregistration):
        with pytest.raises(ValueError):
            render(report)


def test_params_without_as_dict_is_a_type_error():
    r = _report()
    row = r.rows[0]
    bare = dataclasses.replace(row, candidate=dataclasses.replace(row.candidate, params=object()))
    with pytest.raises(TypeError, match="as_dict"):
        render_markdown(dataclasses.replace(r, rows=(bare, *r.rows[1:]), finalists=(), dsr=()))


@dataclass(frozen=True)
class FakePart:
    allocator: object
    params: object
    share: Decimal


@dataclass(frozen=True)
class FakeBlend:
    parts: tuple
    note: str | None = None
    on: bool = True


class FakeBlendAllocator(FakeEtf):
    id = "BLEND"

    def symbols(self, params):
        return ("QQQ", "SPY")

    def holds(self, params):
        return ("SPY",)

    def uses_members(self, params):
        return True


def test_params_without_as_dict_render_by_dataclass_fields():
    r = _report()
    row = r.rows[0]
    blend = FakeBlend(parts=(FakePart(ETF, FakeParams("SPY", 200), Decimal("0.7")), FakePart(MEMBERS, FakeParams("QQQ"), Decimal("0.3"))))
    cand = dataclasses.replace(row.candidate, allocator=FakeBlendAllocator(), params=blend)
    rows = (dataclasses.replace(row, candidate=cand), *r.rows[1:])
    text = render_preregistration(dataclasses.replace(r, rows=rows, finalists=(rows[0], r.finalists[1])))
    assert (
        '{"parts": [{"allocator": "<FAKE>", "params": {"hold": "SPY", "n": "200"}, "share": "0.7"}, '
        '{"allocator": "<FAKEM>", "params": {"hold": "QQQ", "n": "20"}, "share": "0.3"}], "note": null, "on": "true"}'
    ) in render_markdown(dataclasses.replace(r, rows=rows, finalists=(rows[0], r.finalists[1])))
    assert '"allocator": "<FAKE>"' in text


# --------------------------------------------------------------------------- markdown


def test_every_renderer_is_byte_stable():
    a, b = _report(), _report()
    for render in (render_markdown, rows_csv, curves_csv, frontier_svg, render_preregistration):
        first = render(a)
        assert first == render(b)
        assert first.endswith("\n") and not first.endswith("\n\n")


def test_no_run_date_in_content_outside_file_names():
    r = _report()
    other = _report(run_date=D("2026-10-21"))
    for render in (render_markdown, rows_csv, curves_csv, frontier_svg, render_preregistration):
        text = render(r).replace(report_stem(RUN_DATE), "<stem>")
        assert RUN_DATE.isoformat() not in text
        assert text == render(other).replace(report_stem(D("2026-10-21")), "<stem>")


def test_markdown_has_every_section_in_order():
    md = render_markdown(_report())
    headings = [line[3:] for line in md.splitlines() if line.startswith("## ")]
    assert headings == [
        "Data",
        "Method",
        "Candidates",
        "Results",
        "Frontier",
        "SPY on the development window",
        "Year by year, top 5",
        "Survivorship bias",
        "Multiple testing",
        "Finalists (D8)",
        "Plain statements",
    ]


def test_markdown_data_and_method_facts():
    md = render_markdown(_report())
    data = _section(md, "Data")
    assert f"`{FINGERPRINT}`" in data
    assert "- Bar rows: 1,234,567" in data and "- USD/IDR rows: 4,300" in data
    method = _section(md, "Method")
    assert f"`{DIGEST}`" in method
    assert "Trials: 7." in method
    for marker in ("**D1, split.**", "**D3, windows.**", "**D6, registry.**", "**D7, every try reported.**", "**D8, finalists.**", "**D9, test window untouched.**"):
        assert marker in method
    for rules in (MONTHLY_HOLD, DAILY_SWITCH, SWING_T20):
        assert f"- `{rules.id}`, used by" in method
        for text in describe_rules(rules):
            assert f"  - {text}" in method


def test_markdown_has_one_results_row_per_candidate():
    md = render_markdown(_report())
    results = _section(md, "Results")
    for cid in IDS:
        assert sum(1 for line in results.splitlines() if line.startswith(f"| `{cid}` |")) == 1
    f1a = next(line for line in results.splitlines() if line.startswith("| `F1-A` |"))
    assert "| +30.0% |" in f1a and "| 10.0% |" in f1a and "| 1.60 |" in f1a and "| 140 |" in f1a
    assert "| +25.0% |" in f1a and "| finalist |" in f1a
    f2a = next(line for line in results.splitlines() if line.startswith("| `F2-A` |"))
    assert "fail: owner inputs" in f2a and "etf:IEF" in f2a
    f1b = next(line for line in results.splitlines() if line.startswith("| `F1-B` |"))
    assert "| eligible |" in f1b
    assert "-rows.csv" in results


def test_markdown_spy_years_survivorship_and_frontier_link():
    r = _report()
    md = render_markdown(r)
    stem = report_stem(RUN_DATE)
    assert f"]({stem}-frontier.svg)" in _section(md, "Frontier")
    spy = _section(md, "SPY on the development window")
    assert "| SPY price-only |" in spy and "| SPY total-return |" in spy and f"]({stem}-curves.csv)" in spy
    years = _section(md, "Year by year, top 5")
    assert "| Year | `F1-A` | `F4-A` | `F3-A` | `F1-B` | `F2-A` | SPY TR |" in years
    assert "| 2014 | +15.0% | +20.0% | +13.0% | +17.5% | +14.0% |" in years
    surv = _section(md, "Survivorship bias")
    assert "optimistic" in surv and "ticker reuse" in surv
    assert "| All | 1,800 | 90 | 55 | 35 | 5.00% |" in surv
    assert "`F4-A`, `F7-A`" in surv
    assert "ABK, MMM1, ZZA." in surv


def test_markdown_multiple_testing_and_d8_sentences():
    md = render_markdown(_report())
    mt = _section(md, "Multiple testing")
    assert "Trials: 7 candidates" in mt and "Deflated Sharpe" in mt
    assert "| `F1-A` | -0.50 | 0.500 |" in mt and "| `F4-A` | 0.25 | 0.600 |" in mt
    fin = _section(md, "Finalists (D8)")
    assert "1. `F1-A` (F1, rules `monthly-hold`) is eligible:" in fin
    assert "2. `F4-A` (F4, rules `monthly-hold`) is eligible:" in fin
    assert "ranks 1 of 3 eligible" in fin and "ranks 3 of 3 eligible" in fin
    assert "- `F1-B`: family F1 already has `F1-A`." in fin
    assert "| >= 100 trades | 2 |" in fin


def test_markdown_plain_statements():
    md = render_markdown(_report())
    plain = _section(md, "Plain statements")
    assert "excludes low-turnover designs by construction" in plain
    assert "Candidates that failed on the trade count alone: 1." in plain
    assert "FX before 1999-01-04 only affects starting capital" in plain
    assert "2026-11-01" in plain and "February 2027" in plain and "into SPY directly" in plain


def test_markdown_none_eligible():
    r = _report(all_fail=True)
    md = render_markdown(r)
    assert "none of the 7 candidates is eligible" in md
    fin = _section(md, "Finalists (D8)")
    assert "**None eligible.**" in fin and "P7b does not run" in fin
    assert "No finalist; shown for the candidate with the highest Sharpe ratio:" in md


# --------------------------------------------------------------------------- CSV and SVG


def test_rows_csv():
    text = rows_csv(_report())
    rows = list(csv.reader(io.StringIO(text)))
    assert ",".join(rows[0]) == ROWS_CSV_HEADER
    assert [row[0] for row in rows[1:]] == list(IDS)
    by_id = {row[0]: dict(zip(rows[0], row)) for row in rows[1:]}
    assert by_id["F1-A"]["total_return"] == "0.300000"
    assert by_id["F1-A"]["finalist"] == "true" and by_id["F1-B"]["finalist"] == "false"
    assert by_id["F1-B"]["eligible"] == "true"
    assert by_id["F2-A"]["owner_inputs"] == "etf:IEF" and by_id["F2-A"]["failed"] == "owner inputs"
    assert by_id["REF-Z"]["cagr"] == "" and by_id["REF-Z"]["profit_factor"] == "" and by_id["REF-Z"]["mar"] == ""
    assert by_id["F7-A"]["failed"] == "beats SPY TR;max DD <= 15%;PF >= 1.3"
    assert by_id["F1-A"]["worst_year"] == "2015"
    assert by_id["F1-A"]["spy_tr_total_return"] == "0.250000" and by_id["F1-A"]["spy_tr_cagr"] == "0.100000"


def test_curves_csv():
    text = curves_csv(_report())
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0] == ["date", *IDS, "spy_price", "spy_tr"]
    first = dict(zip(rows[0], rows[1]))
    assert first["date"] == "2013-12-31"
    assert first["F1-A"] == "1.000000" and first["spy_tr"] == "1.000000" and first["F1-B"] == ""
    may = dict(zip(rows[0], next(r for r in rows if r[0] == "2014-05-30")))
    assert may["F1-B"] == "1.000000"
    assert rows[-1][0] == DEV_END.isoformat()
    assert [r[0] for r in rows[1:]] == sorted(r[0] for r in rows[1:])


def test_frontier_svg():
    r = _report()
    svg = frontier_svg(r)
    root = ET.fromstring(svg.encode("utf-8"))
    ns = "{http://www.w3.org/2000/svg}"
    dots = [c for c in root.iter(f"{ns}circle") if c.find(f"{ns}title") is not None]
    assert len(dots) == 6  # REF-Z has no CAGR
    classes = sorted(c.get("class") for c in dots)
    assert classes == ["el", "fi", "fi", "pt", "pt", "pt"]
    texts = [t.text for t in root.iter(f"{ns}text")]
    assert "F1-A" in texts and "F4-A" in texts and "F1-B" not in texts
    assert "SPY total-return" in texts
    assert any(t and t.startswith("max drawdown 15%") for t in texts)
    assert "Not plotted (no CAGR or drawdown): 1." in svg
    assert root.find(f"{ns}line[@class='lim']") is not None


def test_frontier_handles_negative_cagr():
    r = _report()
    row = r.rows[4]
    neg = dataclasses.replace(row, stats=dataclasses.replace(row.stats, metrics=dataclasses.replace(row.stats.metrics, cagr=-0.07)))
    svg = frontier_svg(dataclasses.replace(r, rows=(*r.rows[:4], neg, *r.rows[5:])))
    assert ">-10%<" in svg or ">-8%<" in svg or ">-7.5%<" in svg


# --------------------------------------------------------------------------- pre-registration


def test_preregistration_names_each_finalist_exactly():
    r = _report()
    text = render_preregistration(r)
    stem = report_stem(RUN_DATE)
    assert text.startswith("# P7b pre-registration\n")
    assert f"(../backtests/{stem}.md)" in text and f"`{DIGEST}`" in text and f"`{FINGERPRINT}`" in text
    assert "### 1. `F1-A`" in text and "### 2. `F4-A`" in text
    assert "`F1-B`" not in text.split("## Finalists")[1].split("## Test window")[0]
    assert '{\n  "hold": "SPY",\n  "n": "20"\n}' in text
    assert (
        "TradeRules(id='monthly-hold', engine='book', cadence='monthly', entry='open_limit', max_positions=None, "
        "time_stop=None, resize=True, fractional=False, dividends=True, idle_symbol=None, cost_rate=Decimal('0.001'))"
    ) in text
    assert "| cost_rate | 0.001 |" in text and "| idle_symbol | none |" in text
    assert "- Instruments held: SPY" in text
    assert "- Instruments held: S&P 500 ∪ Nasdaq-100 members (point in time)" in text
    assert "- Instruments read: SPY + S&P 500 ∪ Nasdaq-100 members (point in time)" in text
    assert "- Owner inputs: none" in text
    assert f"- Main: {TEST_START.isoformat()} → data end" in text
    assert f"{TEST_SLICE_START.isoformat()} → data end" in text
    assert "- Max drawdown ≤ 15%." in text and "- Profit factor ≥ 1.3." in text and "- ≥ 100 closed trades." in text
    assert "Beats total-return SPY" in text
    revision = text.split("## Proposed design-§5 revision (D10)")[1]
    for line in describe_rules(DESIGN_V0):
        assert f"- {line}" in revision
    assert "### Rule set `monthly-hold` (used by `F1-A`, `F4-A`)" in revision
    for line in describe_rules(MONTHLY_HOLD):
        assert f"- {line}" in revision
    assert "optimistic" in text and "2026-11-01" in text and "February 2027" in text


def test_preregistration_none_eligible():
    r = _report(all_fail=True)
    text = render_preregistration(r)
    stem = report_stem(RUN_DATE)
    assert "## None eligible" in text and "**P7b does not run**" in text
    assert f"(../backtests/{stem}-frontier.svg)" in text
    assert "## Finalists" not in text and "## Proposed design-§5 revision" not in text
    assert "| `F3-A` | F3 |" in text
    assert "2026-11-01" in text and "optimistic" in text
```
**Impact:** test-only. No database, no network, no files.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/trade-rules-dev-search && engine/.venv/bin/python -c "import seer_engine.backtest.dev_report"`
(the worktree's own venv; never `/home/miftah/seer/engine/.venv`)

**Tests:**
```sh
docker start seer-pg
cd /home/miftah/.worktrees/seer/trade-rules-dev-search
engine/.venv/bin/pytest engine/tests/test_backtest_dev_report.py -q          # 32 passed
engine/.venv/bin/pytest engine/tests/test_strategy_purity.py -q              # the glob now covers dev_report.py
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q   # 0 skipped
git diff --stat 2546a92 -- engine/src/seer_engine/sim/model.py engine/src/seer_engine/sim/lifecycle.py \
  engine/src/seer_engine/sim/sizing.py engine/src/seer_engine/sim/split_adjust.py \
  engine/src/seer_engine/backtest/runner.py engine/src/seer_engine/backtest/market.py \
  engine/src/seer_engine/backtest/benchmark.py engine/src/seer_engine/backtest/metrics.py \
  engine/src/seer_engine/backtest/walkforward.py engine/src/seer_engine/backtest/wf_report.py \
  engine/src/seer_engine/backtest/report.py engine/src/seer_engine/backtest/tuning.py \
  engine/src/seer_engine/backtest/labels.py engine/src/seer_engine/backtest/b_walkforward.py \
  engine/src/seer_engine/backtest/b_report.py engine/tests/test_strategy_purity.py   # prints nothing
```
The suite total is the count after phase 9 plus **32** (the 32 test ids are the `def test_` names
in Step 2; `test_every_renderer_rejects_an_invalid_report` is parametrized 10 ways). A different
number is a finding: name the missing or extra ids in the phase log.

**Prototype evidence:** the module and test in this plan were run (32 passed) against stubs that
implement the phase-1/2/3/9 contract names exactly as the index states them, with the worktree
venv. The stubs are not part of this plan. If a landed phase differs from its contract (a field
name, a `failed` label, `Candidate.__post_init__` rejecting the fake allocators), fix the
**test fixture** or this module, never the other phase.

**Manual check:** render the fixture once and read it:
```sh
cd /home/miftah/.worktrees/seer/trade-rules-dev-search/engine
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0, "tests")
import test_backtest_dev_report as t
from seer_engine.backtest import dev_report as d
r = t._report()
print(d.render_markdown(r)); print(d.render_preregistration(r)); print(d.render_preregistration(t._report(all_fail=True)))
open("/tmp/claude-frontier.svg", "w").write(d.frontier_svg(r))
PY
```
Every §7.6 item must be visible (Data, Method with D1/D3/D6/D7/D8/D9, rule presets, digest and
trial count; one row per candidate; frontier link; SPY price-only and total-return; year by year;
survivorship with both caveats; deflated Sharpe; D8 sentences; the three plain statements).

**Exit criteria:** `dev_report.py` exists, is pure (purity glob green), every renderer is
byte-stable and rejects an inconsistent `DevReport`, rendered content holds no run date outside
sibling-file names, the suite is green with 0 skipped, and the frozen set is unchanged.

## Assumptions

- Phase 9's `DevRow.failed` uses exactly the labels in `FAIL_ORDER` (index contract wording). An
  unknown label is still counted and rendered (after the known ones, sorted), so a mismatch only
  changes the order in the counts table.
- Phase 9's `Candidate` accepts any object with an `id` as `allocator` when `rules.engine == "book"`
  and the object is an `Allocator` (the fakes in Step 2 implement every protocol member).
- Phase 3's `RunStats.worst_year` is `(year, return)` or `None`; `year_returns` is a tuple of
  `(year, return)`; `sharpe` is annualized or `None`; `turnover` and `exposure` are floats.
- Phase 1's `describe_rules` returns plain text lines with no Markdown table pipes needed (they are
  rendered as bullets, not table cells).
- Phase 12 builds `DevReport` with `unserved` sorted and unique and `spy_window = (min start,
  DEV_END)` (both true in its plan as written).

## Handoffs

- **Phase 13 (R6, R8):** `p7a_dates.py`'s "the run date must not appear inside any file" check must
  first remove `report_stem(run_date)` and `preregistration_name(run_date)` from the text: the
  Markdown and the pre-registration link sibling files whose names carry the run date (Decision 3).
  The same check also fires if the registry's `added` date equals the run date (the Candidates table
  and each finalist block show `added`); either mask `| <date> |` cells of the Candidates table or
  run the dev run on a later day than the registry commit (phase 13's `p7a_dates.py` now masks
  the stems, the pre-registration name and the `added` cells). Phase 13's `COLS` map uses
  `ROWS_CSV_HEADER`'s names (`spy_tr_total_return`, `spy_tr_cagr`, `spy_price_total_return`
  exist; there is no rationale column: it is in the Markdown). This file adds **32** tests (the
  "(10)" next to it in phase 13's Bug-protocol list is the phase number).
- **Phase 13 (R6):** phase 11's note that swing presets apply `time_stop` to F9's SPY core belongs in
  the report's prose if wanted; this module has no candidate-specific text. Phase 13 can add it to
  the ROADMAP/readme, not to the renderer.
- **Phase 9 (R5/R8):** `dev.finalists` ranks eligible rows with `mar is None` after every row
  with a MAR, then by id; this module's `_eligible_ranked` uses the same order, so the "ranks k of
  n" sentence agrees with D8.
- **Phase 2 / 11 (R5):** phase 2 gives `BlendParams`/`VolTargetParams`/`PicksParams` an
  `as_dict()`, which this module uses; phase 11's digest walks dataclass fields independently.
- **Settled cross-phase points:** `top_years` order (D-G) and the run-date masking (Decision 3,
  applied in phase 13's `p7a_dates.py`).

## Rollback

`git revert` the phase-10 commit: it adds only `backtest/dev_report.py` and
`tests/test_backtest_dev_report.py`, and nothing imports `dev_report` until phase 12. If phase 12
has landed, revert it first (its `io.py` and command import this module).
