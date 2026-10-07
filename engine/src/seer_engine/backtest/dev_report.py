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
    FAILURE_LABELS,
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
FAIL_ORDER: tuple[str, ...] = FAILURE_LABELS  # the engine's own labels; entry [1] follows MAX_DRAWDOWN (D13)
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
        f"Each dot is one candidate on its own window. Dots right of the dashed "
        f"{fmt_pct(MAX_DRAWDOWN, 0)} line fail D8 on "
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
    ``spy_window`` as a diamond, the ``MAX_DRAWDOWN`` limit dashed, finalists labelled. Self-contained,
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
        f"development window, with total-return SPY and the {fmt_pct(MAX_DRAWDOWN, 0)} drawdown "
        "limit marked. The values "
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
            "## Gate (design §1)",
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
