"""Walk-forward (P3b) report rendering: Markdown, two CSVs and two self-contained SVGs.

Pure: takes a ``WalkForwardReport`` value and returns text. Phase 5's ``io.write_wf_report``
writes the files ``<stem>.md``, ``<stem>-equity.csv``, ``<stem>-equity.svg``,
``<stem>-variants.svg`` and ``<stem>-grid.csv``. Everything is deterministic (invariant 5):
- numbers go through ``metrics.to_fixed`` (via ``fmt_*``), ``str(int)``, ``format`` of a
  ``Decimal``, or ``repr`` of a float (grid CSV only);
- SVG coordinates are ``f"{x:.1f}"`` of floats computed the same way every time;
- iteration is in tuple order or in sorted order.

The Markdown ends with three machine-readable lines inside a ``text`` fence, each exactly once:
``p3b-gate: passed|failed``, ``last-fold-params: <json>`` and ``frozen-params: null|<json>``.
Phase 6's ``test_strategy_a2_frozen.py`` reads them with :func:`parse_machine_line`.

Diagnostics and the "seen before" slice explain the result. Nothing here feeds any selection.
The v1 report module (``report.py``) is reused read-only for its helpers and is never edited.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from seer_engine import dates
from seer_engine.backtest.benchmark import BenchmarkCurve
from seer_engine.backtest.metrics import (
    DASH,
    EXIT_REASONS,
    MINUS,
    Metrics,
    checklist,
    curve_metrics,
    fmt_num,
    fmt_pct,
    fmt_pf,
    fmt_signed_pct,
    forced_closes,
    gate_checks,
    run_metrics,
)
from seer_engine.backtest.report import (
    _CHECK_NOTES,
    _EXIT_LABELS,
    _LABEL_GAP,
    _MB,
    _ML,
    _MR,
    _MT,
    _SVG_H,
    _SVG_W,
    FENCE,
    _check_aligned,
    _esc,
    _nice_ticks,
    _order_row,
    _pass,
    _plain,
    _sessions,
    _span,
    _table,
    _tick_label,
    _usd,
)
from seer_engine.backtest.runner import INITIAL_IDR, RunResult, YearGap
from seer_engine.backtest.tuning import (
    MAX_DRAWDOWN,
    GRID_LIMIT,
    GRID_RSI,
    GRID_SL,
    GRID_TP,
    GridRow,
    Selection,
    Verdict,
    grid,
    qualifies,
)
from seer_engine.backtest.walkforward import (
    COMBINED,
    SEEN_BEFORE_START,
    Diagnostics,
    Fold,
    WalkForward,
    curve_window_metrics,
    diagnostics,
    gate_p3b,
    schedule,
    window_metrics,
)
from seer_engine.sim import Snapshot
from seer_engine.strategies.a import ATR_N, SMA_N
from seer_engine.strategies.a2 import A2_DESIGN_PARAMS, FLOOR_PRICE, REGIME_SYMBOL, VARIANTS, A2Params

GATE_KEY = "p3b-gate"
LAST_FOLD_KEY = "last-fold-params"
FROZEN_KEY = "frozen-params"
TOP_N = 10

_PARAM_COLUMNS: tuple[str, ...] = tuple(A2_DESIGN_PARAMS.as_dict())
GRID_CSV_HEADER: tuple[str, ...] = (
    "fold",
    "tune_start",
    "tune_end",
    "combo",
    *_PARAM_COLUMNS,
    "total_return",
    "cagr",
    "win_rate",
    "profit_factor",
    "max_drawdown",
    "trades",
    "months",
    "avg_days_held",
    "qualifies",
    "selected",
)
EQUITY_CSV_HEADER = ",".join(("date", "walk_forward", *VARIANTS, "spy_price", "spy_tr"))

_WF_LABEL = "Walk-forward"
_VARIANT_CLASSES = ("v0", "v1", "v2", "v3")
# v1's palette for s1..s3 (walk-forward, SPY price-only dashed, SPY total-return), plus four
# variant classes. SPY total-return is green (s3) in both charts. Light and dark palettes,
# switched by prefers-color-scheme, with an opaque background.
_STYLE = (
    ".bg{fill:#fcfcfb}.t1{fill:#0b0b0b}.t2{fill:#52514e}"
    ".grid{stroke:#e6e5e0;stroke-width:1}.axis{stroke:#a3a29c;stroke-width:1}"
    ".line{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}"
    ".s1{stroke:#2a78d6}.s2{stroke:#eb6834;stroke-dasharray:6 4}.s3{stroke:#1baf7a}"
    ".v0{stroke:#8a8984;stroke-dasharray:3 3}.v1{stroke:#eb6834}.v2{stroke:#8a5cd1}.v3{stroke:#2a78d6}"
    "@media (prefers-color-scheme: dark){"
    ".bg{fill:#1a1a19}.t1{fill:#ffffff}.t2{fill:#c3c2b7}"
    ".grid{stroke:#33322f}.axis{stroke:#6b6a64}"
    ".s1{stroke:#3987e5}.s2{stroke:#d95926}.s3{stroke:#199e70}"
    ".v0{stroke:#8f8e88}.v1{stroke:#d95926}.v2{stroke:#a07ee0}.v3{stroke:#3987e5}}"
)


# --------------------------------------------------------------------------- values


@dataclass(frozen=True)
class WalkForwardReport:
    data_end: date
    bars_rows: int
    symbols_with_bars: int
    never_fetched_members: int
    survivorship: tuple[YearGap, ...]  # runner.survivorship(market, is_start, data_end)
    is_start: date
    folds: tuple[Fold, ...]
    fold_rows: tuple[tuple[GridRow, ...], ...]  # walkforward.tune() output, one tuple per fold
    combined: WalkForward  # name COMBINED
    variants: tuple[WalkForward, ...]  # VARIANTS order
    spy_price: BenchmarkCurve
    spy_tr: BenchmarkCurve
    verdict: Verdict  # gate_p3b(run_metrics(combined.run), curve_metrics(spy_tr), run.start, run.end)
    frozen_params: A2Params | None  # STRATEGY_A2_PARAMS at run time

    def curves(self) -> tuple[WalkForward, ...]:
        return (self.combined, *self.variants)


def report_stem(data_end: date) -> str:
    """File stem for one data end date: ``<data_end>-strategy-a2-walkforward``."""
    return f"{data_end.isoformat()}-strategy-a2-walkforward"


# --------------------------------------------------------------------------- machine lines


def _json(p: A2Params) -> str:
    return json.dumps(p.as_dict())  # as_dict order (variant first), never sorted


def machine_lines(report: WalkForwardReport) -> list[str]:
    """The three machine-readable lines: gate, last fold's selection, frozen params."""
    frozen = "null" if report.frozen_params is None else _json(report.frozen_params)
    return [
        f"{GATE_KEY}: {'passed' if report.verdict.passed else 'failed'}",
        f"{LAST_FOLD_KEY}: {_json(report.combined.selections[-1].params)}",
        f"{FROZEN_KEY}: {frozen}",
    ]


def parse_machine_line(markdown: str, key: str) -> str:
    """The raw value of the single ``<key>: <value>`` line; ValueError unless exactly one exists."""
    found = re.findall(rf"^{re.escape(key)}: (.*)$", markdown, flags=re.MULTILINE)
    if len(found) != 1:
        raise ValueError(f"expected exactly one '{key}:' line, found {len(found)}")
    return found[0]


# --------------------------------------------------------------------------- validation


def _validate(r: WalkForwardReport) -> None:
    if not r.folds:
        raise ValueError("the report has no folds")
    if r.is_start != r.folds[0].tune_start:
        raise ValueError(f"is_start {r.is_start} is not the first fold's tune_start {r.folds[0].tune_start}")
    if len(r.fold_rows) != len(r.folds):
        raise ValueError(f"{len(r.fold_rows)} fold row sets for {len(r.folds)} folds")
    combos = tuple(row.params for row in r.fold_rows[0])
    if not combos:
        raise ValueError(f"fold {r.folds[0].year} has no tuning rows")
    for f, rows in zip(r.folds, r.fold_rows):
        if tuple(row.params for row in rows) != combos:
            raise ValueError(
                f"fold {f.year}: tuning rows are not the same {len(combos)} combinations, "
                f"in the same order, as fold {r.folds[0].year}"
            )
    for p in combos:
        if not isinstance(p, A2Params):
            raise TypeError(f"tuning rows must hold A2Params, got {type(p).__name__}")
    if r.combined.name != COMBINED:
        raise ValueError(f"the combined curve is named {r.combined.name!r}, not {COMBINED!r}")
    if tuple(w.name for w in r.variants) != VARIANTS:
        raise ValueError(f"variant curves {[w.name for w in r.variants]} are not {list(VARIANTS)}")
    if len(VARIANTS) > len(_VARIANT_CLASSES):
        raise ValueError(f"{len(VARIANTS)} variants but only {len(_VARIANT_CLASSES)} chart colours")
    for wf in r.curves():
        if wf.folds != r.folds:
            raise ValueError(f"{wf.name}: folds differ from the report's folds")
        if len(wf.selections) != len(r.folds):
            raise ValueError(f"{wf.name}: {len(wf.selections)} selections for {len(r.folds)} folds")
        if wf.run.params != schedule(r.folds, wf.selections):
            raise ValueError(f"{wf.name}: the run did not use its fold selections' schedule")
        if wf.run.start != r.folds[0].trade_start or wf.run.end != r.folds[-1].trade_end:
            raise ValueError(
                f"{wf.name}: run {_span(wf.run)} is not "
                f"{r.folds[0].trade_start.isoformat()} → {r.folds[-1].trade_end.isoformat()}"
            )
    if r.combined.run.end > r.data_end:
        raise ValueError(f"the run ends {r.combined.run.end}, after the data end {r.data_end}")
    _check_aligned(
        "walk-forward curves",
        [wf.run.snapshots for wf in r.curves()] + [r.spy_price.snapshots, r.spy_tr.snapshots],
    )
    if r.frozen_params is not None and not isinstance(r.frozen_params, A2Params):
        raise TypeError(f"frozen_params must be A2Params or None, got {type(r.frozen_params).__name__}")
    expected = gate_p3b(
        run_metrics(r.combined.run), curve_metrics(r.spy_tr), r.combined.run.start, r.combined.run.end
    )
    if r.verdict != expected:
        raise ValueError("the verdict is not gate_p3b of the walk-forward curve and total-return SPY")


# --------------------------------------------------------------------------- small helpers


def _md_name(wf: WalkForward) -> str:
    return _WF_LABEL if wf.name == COMBINED else f"`{wf.name}`"


def _plain_name(wf: WalkForward) -> str:
    return _WF_LABEL if wf.name == COMBINED else wf.name


def _signed_usd(d: Decimal) -> str:
    """``+1,234.56`` / ``−1,234.56`` (the web's minus sign); exactly zero prints ``0.00``."""
    text = format(abs(d), ",.2f")
    if text == "0.00":
        return text
    return ("+" if d > 0 else MINUS) + text


def _dates(a: date, b: date) -> str:
    return f"{a.isoformat()} → {b.isoformat()}"


def _param_cells(p: A2Params) -> list[str]:
    d = p.as_dict()
    return [f"`{d['variant']}`", d["rsi_max"], d["limit_atr"], d["tp_atr"], d["sl_atr"]]


def _params_text(p: A2Params) -> str:
    d = p.as_dict()
    return (
        f"`{d['variant']}`, RSI(2) < {d['rsi_max']}, limit {d['limit_atr']} × ATR, "
        f"TP {d['tp_atr']} × ATR, SL {d['sl_atr']} × ATR, "
        f"20-session dollar volume > ${d['min_dollar_volume']}"
    )


def _short(p: A2Params) -> str:
    d = p.as_dict()
    return f"RSI {d['rsi_max']}, limit {d['limit_atr']}, TP {d['tp_atr']}, SL {d['sl_atr']}"


def _selection_cell(sel: Selection, with_variant: bool) -> str:
    text = _short(sel.params)
    if with_variant:
        text = f"`{sel.params.variant}`, {text}"
    return text if sel.qualified else text + " (fallback)"


def _selected_index(rows: Sequence[GridRow], sel: Selection) -> int | None:
    return next((i for i, row in enumerate(rows) if row.params == sel.params), None)


def _mark(sel: Selection) -> str:
    return "selected" if sel.qualified else "kept (fallback)"


def top_rows(rows: Sequence[GridRow]) -> list[int]:
    """0-based indices of the top ``TOP_N`` rows (Decision D11).

    Qualifying rows come first, ordered by the selection key (−total return, max drawdown, index).
    The rest follow in the same order.
    """

    def key(i: int) -> tuple[int, float, float, int]:
        m = rows[i].metrics
        return (
            0 if qualifies(m) else 1,
            -m.total_return if m.total_return is not None else math.inf,
            m.max_drawdown if m.max_drawdown is not None else math.inf,
            i,
        )

    return sorted(range(len(rows)), key=key)[:TOP_N]


def _segment_return(snaps: Sequence[Snapshot], f: Fold) -> float:
    """Return over one traded year: the close of its last session over the close before it."""
    before = [s for s in snaps if s.date < f.trade_start]
    through = [s for s in snaps if s.date <= f.trade_end]
    first, last = before[-1], through[-1]
    return float(last.equity_usd) / float(first.equity_usd) - 1


def _seen_covered(r: WalkForwardReport) -> bool:
    return r.combined.run.start <= SEEN_BEFORE_START <= r.combined.run.end


def _slice_sessions(run: RunResult) -> int:
    return sum(1 for s in run.snapshots if s.date >= SEEN_BEFORE_START)


def _gate_cell(m: Metrics, spy_return: float | None) -> str:
    beats, pf, dd = gate_checks(m, spy_return)
    failed = [c.label for c in (beats, pf, dd) if not c.ok]
    return "yes" if not failed else "no: " + ", ".join(failed)


# --------------------------------------------------------------------------- sections


def _data_section(r: WalkForwardReport) -> list[str]:
    run = r.combined.run
    tune_end = r.folds[-1].tune_end
    rows = [
        [
            "Tuning data (anchored, longest window)",
            _dates(r.is_start, tune_end),
            f"{len(dates.sessions(r.is_start, tune_end)):,}",
            DASH,
            DASH,
        ],
        [
            "Walk-forward (traded)",
            _span(run),
            f"{_sessions(run):,}",
            format(run.usd_idr, ",.4f"),
            _usd(run.initial_cash),
        ],
    ]
    if _seen_covered(r):
        rows.append(
            [
                "Seen before (a slice of the walk-forward)",
                _dates(SEEN_BEFORE_START, run.end),
                f"{_slice_sessions(run):,}",
                DASH,
                DASH,
            ]
        )
    return [
        "## Data",
        "",
        f"- Data end (last bar loaded): {r.data_end.isoformat()}",
        f"- Bar rows loaded: {r.bars_rows:,}",
        f"- Symbols with bars: {r.symbols_with_bars:,}",
        f"- Index members in the window with no bars at all: {r.never_fetched_members:,}",
        "",
        *_table(
            ["Window", "Dates", "Sessions", "USD/IDR at start", "Starting cash (USD)"],
            ["l", "l", "r", "r", "r"],
            rows,
        ),
        "",
    ]


def _method_section(r: WalkForwardReport) -> list[str]:
    design = A2_DESIGN_PARAMS.as_dict()
    stem = report_stem(r.data_end)
    n = len(r.fold_rows[0])
    years = ", ".join(str(f.year) for f in r.folds)
    first = r.folds[0].trade_start.isoformat()
    return [
        "## Method",
        "",
        "- **Strategy A2** is Strategy A (design §4) with one variant rule on top. The base rules "
        "do not change: a setup needs close > SMA(200), Wilder RSI(2) < `rsi_max` and 20-session "
        "mean close × volume > `min_dollar_volume` "
        f"(design: RSI < {design['rsi_max']}, ${design['min_dollar_volume']}). "
        "Limit = close − `limit_atr` × ATR(14), TP = limit + `tp_atr` × ATR(14), "
        "SL = limit − `sl_atr` × ATR(14), each to 4 dp.",
        "- **Everything tried.** These four variants were fixed before any result was seen, and "
        "none was added after:",
        "  - `control` (V0): Strategy A v1 exactly. Candidates are ranked by RSI(2) ascending, "
        "with the symbol breaking ties.",
        f"  - `regime` (V1): V0, plus no new picks on a data date where {REGIME_SYMBOL}'s close ≤ "
        f"{REGIME_SYMBOL}'s SMA({SMA_N}). The regime is on only when the close is strictly above "
        f"it. Too little {REGIME_SYMBOL} history also means no new picks. {REGIME_SYMBOL} itself "
        "is never a pick.",
        f"  - `regime_calm` (V2): V1, but candidates are ranked by ATR({ATR_N}) / close ascending, "
        "then RSI(2), then the symbol.",
        f"  - `regime_calm_floor` (V3): V2, plus a candidate's close must be ≥ ${FLOOR_PRICE:.2f}. "
        "The floor is fixed, not tuned.",
        f"  - Each variant runs on the P3 grid: RSI {{{_plain(GRID_RSI)}}} × limit "
        f"{{{_plain(GRID_LIMIT)}}} × TP {{{_plain(GRID_TP)}}} × SL {{{_plain(GRID_SL)}}} ATR "
        f"({len(grid())} sets). Every fold searched the same {n:,} combinations, ordered by "
        f"variant and then by grid order. Every run is in [`{stem}-grid.csv`]({stem}-grid.csv).",
        f"- **Anchored yearly walk-forward.** For each trade year Y, the fold tunes on "
        f"{r.is_start.isoformat()} → the last session of Y − 1, then trades from the first session "
        f"of Y to the last session of Y (or the data end). Folds: {years}. The traded years form "
        f"one continuous portfolio from {first}. Parameters switch at each year boundary, and an "
        "order already placed keeps the bracket it was placed with.",
        "- **Selection, per fold.** The fold takes the highest tuning-window total return among "
        f"combinations with max drawdown ≤ {fmt_pct(MAX_DRAWDOWN, 0)} and profit factor ≥ 1.3. "
        "Ties go to the lower max "
        "drawdown, then to combination order. If none qualifies, the fold trades `control` with "
        "the design values. Nothing is ever selected on traded data. The selection reasons below "
        "say \"in-sample\" and mean the fold's tuning window.",
        "- **Per-variant curves.** Each variant also gets its own walk-forward, with the variant "
        "fixed and the grid tuned per fold. A fold where none of its runs qualifies trades that "
        "variant with the design values. These curves show how fragile the result is. They are "
        "not the gate, and picking the best of them now would be selecting on traded data.",
        "- **Tuning runs.** Each combination runs once over the longest tuning window, and each "
        "fold reads its metrics at its own tuning end. The simulator never looks ahead, so this "
        "equals a fresh run on each fold's window.",
        f"- **No look-ahead.** Picks for session S use bars through the previous session only, "
        f"{REGIME_SYMBOL}'s included. The universe is S&P 500 ∪ Nasdaq-100 members on that data "
        "date (point in time).",
        "- **One simulator.** Every size, fill, exit and cost (0.1% per side, whole shares, 4 slots) "
        f"comes from `seer_engine.sim`, unchanged. The walk-forward is one fresh portfolio of "
        f"{INITIAL_IDR:,} IDR, converted at the USD/IDR rate of its first session. A held symbol "
        "whose bars end for good is closed at its last close (a forced `time` exit).",
        "- **SPY benchmarks.** They start with the same cash on the session before the first traded "
        "session. They buy whole shares at the first session's open after the 0.1% cost, hold, "
        "and mark at each close. Price-only ignores dividends. Total-return reinvests each dividend "
        "at the ex-date close (whole shares, with cost). At the end, open positions and the SPY "
        "holding are both marked at the last close and never sold.",
        "- **Metrics** follow `web/lib/metrics.ts`:",
        "  - Total return = last / first equity − 1. Every curve starts at the starting cash on "
        "the session before its window.",
        "  - A win is P/L > 0 and a loss is P/L ≤ 0. Profit factor = gross win / gross loss "
        "(∞ with no loss).",
        "  - Max drawdown is measured on per-session equity. Months = calendar days / 30.44.",
        "  - CAGR = (last / first)^(1 / years) − 1, with years = calendar days between the first "
        "and last snapshot / 365.25 (Actual/365.25).",
        "  - Avg days held is the mean of the simulator's `days_held` over closed trades.",
        "- **Diagnostics** explain the result and never feed any selection. They are P/L by exit "
        "reason and by exit year (net of costs), the trades with fewer than 3 shares, and cost "
        "drag = Σ costs ÷ Σ gross P/L (both 0.1% sides).",
        "- **Gate (P3b).** A2 passes only if the walk-forward curve beats total-return SPY over the "
        f"same span, with profit factor ≥ 1.3 and max drawdown ≤ {fmt_pct(MAX_DRAWDOWN, 0)}. "
        "Nothing else decides it.",
        f"- **Seen before.** P3 already judged Strategy A v1 on the window from "
        f"{SEEN_BEFORE_START.isoformat()} on, so that window is not out-of-sample any more. It is "
        "shown below only as a slice of the continuous curves, for information.",
        "- **One round only.** This rework runs once. If A2 fails the gate, Strategy A is not "
        "reworked again on this data.",
        "",
    ]


def _fold_table(rows: Sequence[GridRow], sel: Selection) -> list[str]:
    selected = _selected_index(rows, sel)
    out_rows: list[list[str]] = []
    for rank, i in enumerate(top_rows(rows), start=1):
        m = rows[i].metrics
        out_rows.append(
            [
                str(rank),
                str(i + 1),
                *_param_cells(rows[i].params),
                fmt_signed_pct(m.total_return),
                fmt_signed_pct(m.cagr),
                fmt_pct(m.win_rate),
                fmt_pf(m.profit_factor),
                fmt_pct(m.max_drawdown),
                str(m.trades),
                "yes" if qualifies(m) else "no",
                _mark(sel) if i == selected else "",
            ]
        )
    return _table(
        [
            "Rank",
            "#",
            "Variant",
            "RSI(2) <",
            "Limit ×ATR",
            "TP ×ATR",
            "SL ×ATR",
            "Total return",
            "CAGR",
            "Win rate",
            "Profit factor",
            "Max drawdown",
            "Trades",
            "Qualifies",
            "Selected",
        ],
        ["r", "r", "l"] + ["r"] * 10 + ["l", "l"],
        out_rows,
    )


def _folds_section(r: WalkForwardReport) -> list[str]:
    stem = report_stem(r.data_end)
    summary: list[list[str]] = []
    for f, rows, sel in zip(r.folds, r.fold_rows, r.combined.selections):
        q = sum(1 for row in rows if qualifies(row.metrics))
        summary.append(
            [
                str(f.year),
                _dates(f.tune_start, f.tune_end),
                _dates(f.trade_start, f.trade_end),
                f"{q:,} of {len(rows):,}",
                *_param_cells(sel.params),
                "qualified" if sel.qualified else "fallback",
            ]
        )
    out = [
        "## Folds",
        "",
        "Each fold tunes on everything from the anchored start to the end of the year before, then "
        "trades one year with the combination it selected. The selection reads the tuning window "
        "and nothing else.",
        "",
        *_table(
            ["Year", "Tuning window", "Traded", "Qualifying", "Variant", "RSI(2) <", "Limit ×ATR", "TP ×ATR", "SL ×ATR", "Selection"],
            ["l", "l", "l", "r", "l", "r", "r", "r", "r", "l"],
            summary,
        ),
        "",
    ]
    for f, rows, sel in zip(r.folds, r.fold_rows, r.combined.selections):
        top = top_rows(rows)
        selected = _selected_index(rows, sel)
        out += [
            f"### {f.year}",
            "",
            f"- Tuning window: {_dates(f.tune_start, f.tune_end)} "
            f"({len(dates.sessions(f.tune_start, f.tune_end)):,} sessions)",
            f"- Traded: {_dates(f.trade_start, f.trade_end)} "
            f"({len(dates.sessions(f.trade_start, f.trade_end)):,} sessions)",
            f"- Selected: {_params_text(sel.params)} ({'qualified' if sel.qualified else 'fallback'})",
            "",
            sel.reason,
            "",
            f"Top {len(top)} of {len(rows):,} combinations. Qualifying runs come first, by "
            "tuning-window total return, then the lower max drawdown, then combination order. "
            "The rest follow in the same order. \"#\" is the combination's position in the grid "
            "CSV.",
            "",
            *_fold_table(rows, sel),
            "",
        ]
        if selected is None:
            out += ["The selected parameters are not among the combinations this fold ran.", ""]
        elif selected not in top:
            out += [
                f"The selected combination (#{selected + 1}) is outside the top {len(top)}. Its row "
                f"is in [`{stem}-grid.csv`]({stem}-grid.csv).",
                "",
            ]
    return out


def _results_rows(run: RunResult, spy_price: BenchmarkCurve, spy_tr: BenchmarkCurve) -> list[list[str]]:
    sm = run_metrics(run)
    pm = curve_metrics(spy_price)
    tm = curve_metrics(spy_tr)
    reasons = dict(sm.exit_reasons)
    rows: list[list[str]] = [
        [
            "Ending equity (USD)",
            _usd(run.snapshots[-1].equity_usd),
            _usd(spy_price.snapshots[-1].equity_usd),
            _usd(spy_tr.snapshots[-1].equity_usd),
        ],
        ["Total return", fmt_signed_pct(sm.total_return), fmt_signed_pct(pm.total_return), fmt_signed_pct(tm.total_return)],
        ["CAGR", fmt_signed_pct(sm.cagr), fmt_signed_pct(pm.cagr), fmt_signed_pct(tm.cagr)],
        ["Win rate", fmt_pct(sm.win_rate), DASH, DASH],
        ["Profit factor", fmt_pf(sm.profit_factor), DASH, DASH],
        ["Max drawdown", fmt_pct(sm.max_drawdown), fmt_pct(pm.max_drawdown), fmt_pct(tm.max_drawdown)],
        ["Trades (closed)", str(sm.trades), DASH, DASH],
        ["Avg days held", fmt_num(sm.avg_days_held), DASH, DASH],
    ]
    for reason in EXIT_REASONS:
        rows.append([_EXIT_LABELS[reason], str(reasons.get(reason, 0)), DASH, DASH])
    rows += [
        ["Forced closes (bars ended; inside time stop)", str(forced_closes(run)), DASH, DASH],
        ["Open at end", str(len(run.open_at_end)), DASH, DASH],
        ["Months", fmt_num(sm.months, 1), fmt_num(pm.months, 1), fmt_num(tm.months, 1)],
        ["SPY shares at end", DASH, str(spy_price.shares), str(spy_tr.shares)],
        ["SPY dividends credited (USD)", DASH, DASH, _usd(spy_tr.dividends_usd)],
    ]
    return rows


def _results_section(r: WalkForwardReport) -> list[str]:
    run = r.combined.run
    rejected = ", ".join(f"{reason} {count:,}" for reason, count in run.rejections) or "none"
    years: list[list[str]] = []
    for f, sel in zip(r.folds, r.combined.selections):
        years.append(
            [
                str(f.year),
                _dates(f.trade_start, f.trade_end),
                _selection_cell(sel, with_variant=True),
                fmt_signed_pct(_segment_return(run.snapshots, f)),
                fmt_signed_pct(_segment_return(r.spy_price.snapshots, f)),
                fmt_signed_pct(_segment_return(r.spy_tr.snapshots, f)),
            ]
        )
    return [
        "## Walk-forward results",
        "",
        "One continuous portfolio over every traded year. Each year traded the combination its "
        "fold selected, and no year's numbers fed any selection. This is the evidence the gate "
        "reads.",
        "",
        f"### Walk-forward vs SPY ({_span(run)}, {_sessions(run):,} sessions)",
        "",
        *_table(
            ["Metric", "Strategy A2 walk-forward", "SPY price-only", "SPY total-return"],
            ["l", "r", "r", "r"],
            _results_rows(run, r.spy_price, r.spy_tr),
        ),
        "",
        f"Picks the simulator rejected: {rejected}.",
        "",
        "### Year by year",
        "",
        "Each traded year's return, from the close before its first session to its last close.",
        "",
        *_table(
            ["Year", "Traded", "Parameters", "Walk-forward", "SPY price-only", "SPY total-return"],
            ["l", "l", "l", "r", "r", "r"],
            years,
        ),
        "",
    ]


def _variants_section(r: WalkForwardReport) -> list[str]:
    spy_ret = curve_metrics(r.spy_tr).total_return
    rows: list[list[str]] = []
    for wf in r.curves():
        m = run_metrics(wf.run)
        rows.append(
            [
                _md_name(wf),
                _usd(wf.run.snapshots[-1].equity_usd),
                fmt_signed_pct(m.total_return),
                fmt_signed_pct(m.cagr),
                fmt_pct(m.win_rate),
                fmt_pf(m.profit_factor),
                fmt_pct(m.max_drawdown),
                str(m.trades),
                _gate_cell(m, spy_ret),
            ]
        )
    for label, c in (("SPY price-only", r.spy_price), ("SPY total-return", r.spy_tr)):
        m = curve_metrics(c)
        rows.append(
            [
                label,
                _usd(c.snapshots[-1].equity_usd),
                fmt_signed_pct(m.total_return),
                fmt_signed_pct(m.cagr),
                DASH,
                DASH,
                fmt_pct(m.max_drawdown),
                DASH,
                DASH,
            ]
        )
    header = ["Year", _WF_LABEL, *(f"`{v}`" for v in VARIANTS)]
    sels: list[list[str]] = []
    for k, f in enumerate(r.folds):
        sels.append(
            [str(f.year)]
            + [_selection_cell(wf.selections[k], with_variant=wf.name == COMBINED) for wf in r.curves()]
        )
    return [
        "## Per-variant walk-forward",
        "",
        "Each variant's own walk-forward, with the variant fixed and its grid tuned per fold, next "
        "to the walk-forward that chose the variant per fold. These show how fragile the result "
        "is. Only the walk-forward row is gated, and choosing the best row here would be selecting "
        "on traded data.",
        "",
        *_table(
            ["Curve", "Ending equity (USD)", "Total return", "CAGR", "Win rate", "Profit factor", "Max drawdown", "Trades", "Meets the gate's rules"],
            ["l", "r", "r", "r", "r", "r", "r", "r", "l"],
            rows,
        ),
        "",
        "### Fold selections per curve",
        "",
        "\"(fallback)\" marks a fold where no run qualified, so the design values were traded.",
        "",
        *_table(header, ["l"] * len(header), sels),
        "",
    ]


def _diagnostics_section(r: WalkForwardReport) -> list[str]:
    curves = r.curves()
    diags: list[Diagnostics] = [diagnostics(wf.run) for wf in curves]
    names = [_md_name(wf) for wf in curves]
    align = ["l"] + ["r"] * len(curves)

    summary: list[list[str]] = [
        ["Trades (closed)", *(str(d.trades) for d in diags)],
        [
            "Trades with < 3 shares",
            *(f"{d.small_trades} ({fmt_pct(d.small_trades / d.trades)})" if d.trades else "0" for d in diags),
        ],
        ["Gross P/L (USD)", *(_signed_usd(d.gross_pnl_usd) for d in diags)],
        ["Costs (USD)", *(_usd(d.costs_usd) for d in diags)],
        ["Net P/L (USD)", *(_signed_usd(d.gross_pnl_usd - d.costs_usd) for d in diags)],
        ["Cost drag (costs ÷ gross P/L)", *(fmt_pct(d.cost_drag) for d in diags)],
    ]

    by_reason: list[list[str]] = []
    reason_maps = [{reason: (n, pnl) for reason, n, pnl in d.pnl_by_reason} for d in diags]
    for reason in EXIT_REASONS:
        cells: list[str] = []
        for mp in reason_maps:
            n, pnl = mp.get(reason, (0, Decimal("0")))
            cells.append(f"{n} · {_signed_usd(pnl)}")
        by_reason.append([_EXIT_LABELS[reason], *cells])

    year_maps = [{year: (n, pnl) for year, n, pnl in d.pnl_by_year} for d in diags]
    years = sorted({year for mp in year_maps for year in mp})
    by_year: list[list[str]] = []
    for year in years:
        cells = []
        for mp in year_maps:
            item = mp.get(year)
            cells.append(DASH if item is None else f"{item[0]} · {_signed_usd(item[1])}")
        by_year.append([str(year), *cells])

    return [
        "## Diagnostics",
        "",
        "These numbers explain the result. They never feed a selection. P/L is net of both 0.1% "
        "costs. Gross P/L is (exit − fill) × shares. Cost drag is \"—\" when gross P/L is zero or "
        "negative.",
        "",
        *_table(["Measure", *names], align, summary),
        "",
        "### P/L by exit reason (trades · USD)",
        "",
        *_table(["Exit", *names], align, by_reason),
        "",
        "### P/L by exit year (trades · USD)",
        "",
        *(_table(["Year", *names], align, by_year) if by_year else ["No closed trades."]),
        "",
    ]


def _seen_before_section(r: WalkForwardReport) -> list[str]:
    out = ["## Seen before (information only, not out-of-sample)", ""]
    if not _seen_covered(r):
        out += [
            f"The walk-forward window does not include {SEEN_BEFORE_START.isoformat()}, so there "
            "is no slice to show.",
            "",
        ]
        return out
    rows: list[list[str]] = []
    for wf in r.curves():
        m = window_metrics(wf.run, SEEN_BEFORE_START)
        rows.append(
            [
                _md_name(wf),
                fmt_signed_pct(m.total_return),
                fmt_signed_pct(m.cagr),
                fmt_pct(m.win_rate),
                fmt_pf(m.profit_factor),
                fmt_pct(m.max_drawdown),
                str(m.trades),
            ]
        )
    for label, c in (("SPY price-only", r.spy_price), ("SPY total-return", r.spy_tr)):
        m = curve_window_metrics(c, SEEN_BEFORE_START)
        rows.append([label, fmt_signed_pct(m.total_return), fmt_signed_pct(m.cagr), DASH, DASH, fmt_pct(m.max_drawdown), DASH])
    out += [
        f"P3 judged Strategy A v1 on the window from {SEEN_BEFORE_START.isoformat()} on. Because that "
        "window has been looked at, it is not out-of-sample any more. These rows are a slice of the "
        f"same continuous curves ({_dates(SEEN_BEFORE_START, r.combined.run.end)}, "
        f"{_slice_sessions(r.combined.run):,} sessions, measured from the close before), not a fresh "
        "portfolio. They are information only and never feed the gate.",
        "",
        *_table(
            ["Curve", "Total return", "CAGR", "Win rate", "Profit factor", "Max drawdown", "Trades"],
            ["l", "r", "r", "r", "r", "r", "r"],
            rows,
        ),
        "",
    ]
    return out


def _checklist_section(r: WalkForwardReport) -> list[str]:
    wf_items = checklist(run_metrics(r.combined.run), curve_metrics(r.spy_tr).total_return)
    seen_items = None
    if _seen_covered(r):
        seen_items = checklist(
            window_metrics(r.combined.run, SEEN_BEFORE_START),
            curve_window_metrics(r.spy_tr, SEEN_BEFORE_START).total_return,
        )
    rows: list[list[str]] = []
    for k, note in enumerate(_CHECK_NOTES):
        rows.append(
            [
                wf_items[k].label,
                note,
                f"{_pass(wf_items[k].ok)}: {wf_items[k].val}",
                DASH if seen_items is None else f"{_pass(seen_items[k].ok)}: {seen_items[k].val}",
            ]
        )
    rows.append(
        [
            "Passed a 10-year backtest under identical rules",
            "#5, decided by the P3b gate",
            f"{_pass(r.verdict.passed)}: P3b gate verdict",
            DASH,
        ]
    )
    return [
        "## Go-live checklist (what a backtest can evaluate)",
        "",
        "These are design §1's fixed rules, computed exactly as the web computes them. The "
        "\"months forward\" item needs forward paper trading, so here it is "
        "information only. \"Beats SPY\" compares with total-return SPY. Only the walk-forward "
        "column is evidence; the seen-before column is information.",
        "",
        *_table(
            ["Item", "Design §1", f"Walk-forward ({_span(r.combined.run)})", "Seen before (information)"],
            ["l", "l", "l", "l"],
            rows,
        ),
        "",
    ]


def _survivorship_section(r: WalkForwardReport) -> list[str]:
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
    return [
        "## Survivorship bias",
        "",
        "This walk-forward can only tune on and trade stocks that still have price data. "
        f"{r.never_fetched_members:,} stocks were in the S&P 500 or the Nasdaq-100 at some point "
        f"from {r.is_start.isoformat()} to {r.data_end.isoformat()}, but they have no price data at "
        "all. They were delisted or bought out, and the free data source no longer serves them.",
        "",
        "On the days they were index members, Strategy A2 could not see them, in tuning or in "
        "trading. So it never had the chance to buy one of them on the way down. A dip-buying "
        "strategy is exactly the kind that such collapses would have hurt. **These results are "
        "therefore probably better than reality**, by an amount this data cannot measure.",
        "",
        "The table counts, per year, the (member, session) pairs with no bar:",
        "",
        "- \"Never fetched\" are members with no bars at all.",
        "- \"Other\" are members that have bars elsewhere but none on that session, such as "
        "halts or the days before a listing.",
        "",
        *_table(
            ["Year", "Member-sessions", "Missing", "Never fetched", "Other", "Missing share"],
            ["l", "r", "r", "r", "r", "r"],
            rows,
        ),
        "",
    ]


def _open_positions_section(r: WalkForwardReport) -> list[str]:
    out = [
        "## Open positions at end",
        "",
        "Positions still live after the last session are marked at that close and never sold, the "
        "same treatment as the SPY holding.",
        "",
    ]
    for wf in r.curves():
        out += [f"### {_md_name(wf)}", ""]
        if not wf.run.open_at_end:
            out += ["None.", ""]
            continue
        out += _table(
            ["Symbol", "Status", "Slot", "Session", "Filled", "Fill price", "Shares", "Limit", "TP", "SL", "Days held"],
            ["l", "l", "r", "l", "l", "r", "r", "r", "r", "r", "r"],
            [_order_row(o) for o in wf.run.open_at_end],
        )
        out.append("")
    return out


def _curves_section(r: WalkForwardReport) -> list[str]:
    stem = report_stem(r.data_end)
    return [
        "## Equity curves",
        "",
        f"![Strategy A2 walk-forward vs SPY price-only and SPY total-return]({stem}-equity.svg)",
        "",
        f"![The four per-variant walk-forward curves vs SPY total-return]({stem}-variants.svg)",
        "",
        f"The daily values of every curve are in [`{stem}-equity.csv`]({stem}-equity.csv). Every "
        f"tuning run of every fold is in [`{stem}-grid.csv`]({stem}-grid.csv).",
        "",
    ]


def _verdict_section(r: WalkForwardReport) -> list[str]:
    out = ["## Gate verdict", "", r.verdict.sentence, ""]
    for c in r.verdict.checks:
        out.append(f"- {c.label}: {_pass(c.ok)} ({c.val})")
    out.append("")
    return out


def _next_section(r: WalkForwardReport) -> list[str]:
    """Only on a failed gate: the owner's options from handover §8, named plainly."""
    if r.verdict.passed:
        return []
    return [
        "## If the gate failed: what the owner decides next",
        "",
        "Strategy A had one rework, and it failed. It is not reworked again on this data, and P4 "
        "stays blocked. What happens next is the owner's decision, not this report's. The options "
        "are:",
        "",
        "- **(a)** Go to P6's Strategy B, an ML ranker validated by walk-forward with the same "
        "machinery as this report.",
        "- **(b)** Accept that SPY buy-and-hold is the honest champion for now. Seer can still "
        "paper-trade research strategies, but it recommends no real-money picks.",
        "- **(c)** Revisit a design §5 trade rule, for example the 5-day time stop or the 4 slots. "
        "That is a design change, so it needs the owner's explicit decision and a new handover. "
        "It is never done inside a rework.",
        "",
    ]


def _machine_section(r: WalkForwardReport) -> list[str]:
    last = r.combined.selections[-1].params
    frozen = r.frozen_params
    if frozen is None and not r.verdict.passed:
        note = "Frozen in code (`STRATEGY_A2_PARAMS`): none. The gate failed, so nothing is deployed."
    elif frozen is None:
        note = (
            "Frozen in code (`STRATEGY_A2_PARAMS`): none yet. The gate passed, so set it to the last "
            "fold's selection, with a comment naming this report, and re-run."
        )
    elif not r.verdict.passed:
        note = "Frozen in code (`STRATEGY_A2_PARAMS`): set, but the gate failed. Set it back to None."
    elif frozen == last:
        note = "Frozen in code (`STRATEGY_A2_PARAMS`): matches the last fold's selection."
    else:
        note = (
            "Frozen in code (`STRATEGY_A2_PARAMS`): differs from the last fold's selection. Set it "
            "to the selection and re-run."
        )
    return [
        "## Machine-readable lines",
        "",
        f"The last fold ({r.folds[-1].year}) selected {_params_text(last)}. If the gate passes, "
        "those are the parameters to deploy.",
        "",
        note,
        "",
        "`tests/test_strategy_a2_frozen.py` reads these three lines.",
        "",
        FENCE + "text",
        *machine_lines(r),
        FENCE,
        "",
    ]


def render_markdown(report: WalkForwardReport) -> str:
    """The full report as Markdown, ending in exactly one newline."""
    _validate(report)
    out: list[str] = [
        f"# Strategy A2 walk-forward (P3b), data through {report.data_end.isoformat()}",
        "",
        f"**P3b gate verdict:** {report.verdict.sentence}",
        "",
    ]
    out += _data_section(report)
    out += _method_section(report)
    out += _folds_section(report)
    out += _results_section(report)
    out += _variants_section(report)
    out += _diagnostics_section(report)
    out += _seen_before_section(report)
    out += _checklist_section(report)
    out += _survivorship_section(report)
    out += _open_positions_section(report)
    out += _curves_section(report)
    out += _verdict_section(report)
    out += _next_section(report)
    out += _machine_section(report)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- CSV


def equity_csv(report: WalkForwardReport) -> str:
    """Wide daily CSV of every curve (USD, 4 dp), header ``EQUITY_CSV_HEADER``."""
    _validate(report)
    curves = [wf.run.snapshots for wf in report.curves()] + [report.spy_price.snapshots, report.spy_tr.snapshots]
    lines = [EQUITY_CSV_HEADER]
    for snaps in zip(*curves):
        lines.append(",".join([snaps[0].date.isoformat(), *(f"{s.equity_usd:f}" for s in snaps)]))
    return "\n".join(lines) + "\n"


def _csv_num(v: float | int | None) -> str:
    if v is None:
        return ""
    if isinstance(v, int) and not isinstance(v, bool):
        return str(v)
    if v == math.inf:
        return "inf"
    return repr(float(v))


def grid_csv(report: WalkForwardReport) -> str:
    """Every tuning run of every fold: one row per (fold, combination), header ``GRID_CSV_HEADER``.

    ``selected`` marks the combined walk-forward's selection only: ``selected`` when it
    qualified, ``fallback`` when no run qualified and the fallback params are among the rows.
    """
    _validate(report)
    lines = [",".join(GRID_CSV_HEADER)]
    for f, rows, sel in zip(report.folds, report.fold_rows, report.combined.selections):
        selected = _selected_index(rows, sel)
        for i, row in enumerate(rows):
            p = row.params.as_dict()
            m = row.metrics
            mark = ""
            if i == selected:
                mark = "selected" if sel.qualified else "fallback"
            lines.append(
                ",".join(
                    [
                        str(f.year),
                        f.tune_start.isoformat(),
                        f.tune_end.isoformat(),
                        str(i + 1),
                        *(p[k] for k in _PARAM_COLUMNS),
                        _csv_num(m.total_return),
                        _csv_num(m.cagr),
                        _csv_num(m.win_rate),
                        _csv_num(m.profit_factor),
                        _csv_num(m.max_drawdown),
                        str(m.trades),
                        _csv_num(m.months),
                        _csv_num(m.avg_days_held),
                        "yes" if qualifies(m) else "no",
                        mark,
                    ]
                )
            )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- SVG


def _chart(
    title: str,
    subtitle: str,
    desc: str,
    series: Sequence[tuple[str, str, Sequence[Snapshot], float | None]],
) -> str:
    """One self-contained line chart: ``series`` is ``(css class, label, snapshots, total return)``.

    The chart has light and dark palettes through ``prefers-color-scheme``, an opaque
    background, a legend, year ticks, direct end labels and no script. Every series has the
    same snapshot dates, which ``_validate`` guarantees.
    """
    dts = [s.date for s in series[0][2]]
    span = (dts[-1] - dts[0]).days
    if span <= 0:
        raise ValueError("a chart needs snapshots on at least two different dates")
    values = [[float(s.equity_usd) for s in snaps] for _, _, snaps, _ in series]
    ticks, step = _nice_ticks(min(min(v) for v in values), max(max(v) for v in values))
    lo, hi = ticks[0], ticks[-1]
    pw = _SVG_W - _ML - _MR
    ph = _SVG_H - _MT - _MB
    bottom = _MT + ph

    def px(d: date) -> float:
        return _ML + (d - dts[0]).days / span * pw

    def py(v: float) -> float:
        return _MT + (hi - v) / (hi - lo) * ph

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_SVG_W} {_SVG_H}" '
        f'width="{_SVG_W}" height="{_SVG_H}" role="img" aria-labelledby="title desc" '
        'font-family="system-ui, -apple-system, Segoe UI, Helvetica, Arial, sans-serif">',
        f'<title id="title">{_esc(title)}</title>',
        f'<desc id="desc">{_esc(desc)}</desc>',
        f"<style>{_STYLE}</style>",
        f'<rect class="bg" x="0" y="0" width="{_SVG_W}" height="{_SVG_H}"/>',
        f'<text class="t1" x="{_ML}" y="24" font-size="16" font-weight="600">{_esc(title)}</text>',
        f'<text class="t2" x="{_ML}" y="42" font-size="12">{_esc(subtitle)}</text>',
    ]
    legend_x = _ML
    for cls, label, _, _ in series:
        out.append(f'<line class="line {cls}" x1="{legend_x}" y1="60" x2="{legend_x + 22}" y2="60"/>')
        out.append(f'<text class="t2" x="{legend_x + 28}" y="64" font-size="12">{_esc(label)}</text>')
        legend_x += 170
    for t in ticks:
        y = py(t)
        out.append(f'<line class="grid" x1="{_ML}" y1="{y:.1f}" x2="{_ML + pw}" y2="{y:.1f}"/>')
        out.append(
            f'<text class="t2" x="{_ML - 8}" y="{y + 4:.1f}" font-size="11" text-anchor="end">'
            f"{_esc(_tick_label(t, step))}</text>"
        )
    out.append(f'<line class="axis" x1="{_ML}" y1="{bottom}" x2="{_ML + pw}" y2="{bottom}"/>')
    for year in range(dts[0].year + 1, dts[-1].year + 1):
        d = date(year, 1, 1)
        if not dts[0] < d <= dts[-1]:
            continue
        x = px(d)
        out.append(f'<line class="axis" x1="{x:.1f}" y1="{bottom}" x2="{x:.1f}" y2="{bottom + 5}"/>')
        out.append(
            f'<text class="t2" x="{x:.1f}" y="{bottom + 20}" font-size="11" text-anchor="middle">{year}</text>'
        )
    for (cls, label, _, _), vals in zip(series, values):
        points = " ".join(f"{px(d):.1f},{py(v):.1f}" for d, v in zip(dts, vals))
        out.append(f'<polyline class="line {cls}" points="{points}"><title>{_esc(label)}</title></polyline>')
    ends = sorted((py(vals[-1]), i) for i, vals in enumerate(values))
    placed: list[tuple[int, float]] = []
    prev = -math.inf
    for y, i in ends:
        y = max(y, prev + _LABEL_GAP)
        placed.append((i, y))
        prev = y
    overflow = prev - (_SVG_H - 6)
    if overflow > 0:
        placed = [(i, y - overflow) for i, y in placed]
    x0 = _ML + pw + 8
    for i, y in sorted(placed):
        cls, label, _, ret = series[i]
        out.append(f'<line class="line {cls}" x1="{x0}" y1="{y:.1f}" x2="{x0 + 14}" y2="{y:.1f}"/>')
        out.append(
            f'<text class="t1" x="{x0 + 18}" y="{y + 4:.1f}" font-size="11">'
            f"{_esc(label)} {_esc(fmt_signed_pct(ret))}</text>"
        )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def _subtitle(run: RunResult) -> str:
    return (
        f"Equity in USD from {_usd(run.snapshots[0].equity_usd)} on {run.snapshots[0].date.isoformat()}; "
        "0.1% cost per side; marked at each close."
    )


def equity_svg(report: WalkForwardReport) -> str:
    """The walk-forward curve vs SPY price-only and SPY total-return."""
    _validate(report)
    run = report.combined.run
    series = (
        ("s1", "A2 walk-forward", run.snapshots, run_metrics(run).total_return),
        ("s2", "SPY price-only", report.spy_price.snapshots, curve_metrics(report.spy_price).total_return),
        ("s3", "SPY total-return", report.spy_tr.snapshots, curve_metrics(report.spy_tr).total_return),
    )
    return _chart(
        f"Strategy A2 walk-forward vs SPY, {_span(run)}",
        _subtitle(run),
        "Line chart of daily equity in USD for the Strategy A2 walk-forward, SPY price-only and SPY "
        "total-return. The values are in the CSV next to this file.",
        series,
    )


def variants_svg(report: WalkForwardReport) -> str:
    """The four per-variant walk-forward curves vs SPY total-return."""
    _validate(report)
    run = report.combined.run
    series = [
        (_VARIANT_CLASSES[k], wf.name, wf.run.snapshots, run_metrics(wf.run).total_return)
        for k, wf in enumerate(report.variants)
    ]
    series.append(("s3", "SPY total-return", report.spy_tr.snapshots, curve_metrics(report.spy_tr).total_return))
    return _chart(
        f"Strategy A2 per-variant walk-forward vs SPY total-return, {_span(run)}",
        _subtitle(run),
        "Line chart of daily equity in USD for each Strategy A2 variant's own walk-forward and SPY "
        "total-return. The values are in the CSV next to this file.",
        series,
    )
