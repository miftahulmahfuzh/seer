"""Backtest report rendering: Markdown, a wide CSV and a self-contained SVG.

Pure: takes a ``BacktestReport`` value and returns text. Phase 5's ``io.write_report`` writes
the files. Everything is deterministic (invariant 5):
- numbers go through ``metrics.to_fixed`` (exact decimal rounding), ``str(int)`` or ``format``
  of a ``Decimal``
- SVG coordinates are ``f"{x:.1f}"`` of floats computed the same way every time
- iteration is in tuple order or in sorted order

Two lines are machine-readable, each exactly once, on its own line:
``frozen-params: <json.dumps(report.frozen_params.as_dict())>`` and
``selected-params: <json.dumps(report.selection.params.as_dict())>``. Phase 6's
test_strategy_a_frozen.py reads them back. Only those two lines and the one "Frozen in code"
sentence depend on ``frozen_params``. Every number comes from the runs, which must all have used
``selection.params``.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from seer_engine.backtest.benchmark import BenchmarkCurve
from seer_engine.backtest.metrics import (
    DASH,
    EXIT_REASONS,
    Metrics,
    checklist,
    curve_metrics,
    fmt_num,
    fmt_pct,
    fmt_pf,
    fmt_signed_pct,
    forced_closes,
    run_metrics,
    to_fixed,
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
    qualifies,
)
from seer_engine.sim import Order, Snapshot
from seer_engine.strategies.a import DESIGN_PARAMS, AParams

FROZEN_KEY = "frozen-params"
SELECTED_KEY = "selected-params"
FENCE = "`" * 3

_EXIT_LABELS = {
    "tp": "Exits: take profit",
    "sl": "Exits: stop loss",
    "time": "Exits: time stop",
    "gap": "Exits: gap at the open",
}


# --------------------------------------------------------------------------- values


@dataclass(frozen=True)
class WindowResult:
    name: str  # "In-sample" | "Out-of-sample" | "Full window"
    run: RunResult
    spy_price: BenchmarkCurve
    spy_tr: BenchmarkCurve


@dataclass(frozen=True)
class BacktestReport:
    data_end: date
    bars_rows: int
    symbols_with_bars: int
    grid_rows: tuple[GridRow, ...]
    selection: Selection
    frozen_params: AParams  # STRATEGY_A_PARAMS at run time; rendered only in its own two lines
    in_sample: WindowResult
    out_of_sample: WindowResult
    full: WindowResult
    survivorship: tuple[YearGap, ...]
    never_fetched_members: int
    verdict: Verdict

    def windows(self) -> tuple[WindowResult, WindowResult, WindowResult]:
        return (self.in_sample, self.out_of_sample, self.full)


def report_stem(data_end: date) -> str:
    """File stem for one data end date: ``<data_end>-strategy-a``."""
    return f"{data_end.isoformat()}-strategy-a"


# --------------------------------------------------------------------------- machine lines


def params_line(key: str, params: AParams) -> str:
    """``<key>: <json.dumps(params.as_dict())>``, keys in ``as_dict`` order (never sorted)."""
    return f"{key}: {json.dumps(params.as_dict())}"


def parse_params_line(markdown: str, key: str) -> dict[str, str]:
    """The JSON object on the single ``<key>: {...}`` line; ValueError unless exactly one exists."""
    found = re.findall(rf"^{re.escape(key)}: (\{{.*\}})$", markdown, flags=re.MULTILINE)
    if len(found) != 1:
        raise ValueError(f"expected exactly one '{key}:' line, found {len(found)}")
    value = json.loads(found[0])
    if not isinstance(value, dict):
        raise ValueError(f"'{key}:' is not a JSON object: {found[0]!r}")
    return value


# --------------------------------------------------------------------------- validation


def _check_aligned(name: str, curves: Sequence[Sequence[Snapshot]]) -> None:
    lengths = {len(c) for c in curves}
    if len(lengths) != 1:
        raise ValueError(f"{name}: curves have different lengths {[len(c) for c in curves]}")
    if not curves[0]:
        raise ValueError(f"{name}: curves are empty")
    for i, snaps in enumerate(zip(*curves)):
        dates = [s.date for s in snaps]
        if any(d != dates[0] for d in dates):
            raise ValueError(f"{name}: snapshot {i} dates differ {dates}")


def _validate(report: BacktestReport) -> None:
    for w in report.windows():
        if w.run.params != report.selection.params:
            raise ValueError(
                f"{w.name}: run used {w.run.params!r}, not the selection {report.selection.params!r}"
            )
        _check_aligned(w.name, (w.run.snapshots, w.spy_price.snapshots, w.spy_tr.snapshots))


# --------------------------------------------------------------------------- markdown helpers


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _table(header: Sequence[str], align: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    """A GitHub table; ``align`` is ``"l"`` or ``"r"`` per column."""
    lines = [
        "| " + " | ".join(_cell(h) for h in header) + " |",
        "|" + "|".join("---:" if a == "r" else ":---" for a in align) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_cell(c) for c in row) + " |")
    return lines


def _usd(d: Decimal) -> str:
    return format(d, ",.2f")


def _span(run: RunResult) -> str:
    return f"{run.start.isoformat()} → {run.end.isoformat()}"


def _sessions(run: RunResult) -> int:
    return len(run.snapshots) - 1  # snapshots[0] is the starting cash on the session before


def _plain(values: Sequence[float | Decimal]) -> str:
    return ", ".join(format(v, "g") if isinstance(v, float) else str(v) for v in values)


def _pass(ok: bool) -> str:
    return "pass" if ok else "fail"


# --------------------------------------------------------------------------- sections


def _data_section(report: BacktestReport) -> list[str]:
    rows = [
        [
            w.name,
            _span(w.run),
            f"{_sessions(w.run):,}",
            format(w.run.usd_idr, ",.4f"),
            _usd(w.run.initial_cash),
        ]
        for w in report.windows()
    ]
    return [
        "## Data",
        "",
        f"- Data end (last bar loaded): {report.data_end.isoformat()}",
        f"- Bar rows loaded: {report.bars_rows:,}",
        f"- Symbols with bars: {report.symbols_with_bars:,}",
        f"- Index members in the window with no bars at all: {report.never_fetched_members:,}",
        "",
        *_table(
            ["Window", "Dates", "Sessions", "USD/IDR at start", "Starting cash (USD)"],
            ["l", "l", "r", "r", "r"],
            rows,
        ),
        "",
    ]


def _method_section(report: BacktestReport) -> list[str]:
    design = DESIGN_PARAMS.as_dict()
    return [
        "## Method",
        "",
        "- **Strategy A** (design §4): a setup needs close > SMA(200), Wilder RSI(2) < `rsi_max` and "
        "20-session mean close × volume > `min_dollar_volume` "
        f"(design: RSI < {design['rsi_max']}, ${design['min_dollar_volume']}). "
        "Limit = close − `limit_atr` × ATR(14), TP = limit + `tp_atr` × ATR(14), "
        "SL = limit − `sl_atr` × ATR(14), each to 4 dp. Candidates are ranked by RSI(2) ascending, "
        "with the symbol breaking ties.",
        "- **No look-ahead.** Picks for session S use bars through the previous session only. "
        "The universe is S&P 500 ∪ Nasdaq-100 members on that data date (point in time).",
        "- **One simulator.** Every size, fill, exit and cost (0.1% per side, whole shares, 4 slots) "
        f"comes from `seer_engine.sim`, unchanged. Each window is a fresh portfolio of "
        f"{INITIAL_IDR:,} IDR converted at the start date's USD/IDR rate. A held symbol whose bars "
        "end for good is closed at its last close (a forced `time` exit).",
        "- **SPY benchmarks.** Buy whole shares at the first session's open after the 0.1% cost, "
        "hold, and mark at each close. Price-only ignores dividends. Total-return reinvests each "
        "dividend at the ex-date close (whole shares, with cost). At the end of a window, open "
        "positions and the SPY holding are both marked at the last close and never sold.",
        "- **Metrics** follow `web/lib/metrics.ts`:",
        "  - Total return = last / first equity − 1. Every curve starts at the starting cash on "
        "the session before the window.",
        "  - A win is P/L > 0 and a loss is P/L ≤ 0. Profit factor = gross win / gross loss "
        "(∞ with no loss).",
        "  - Max drawdown is measured on per-session equity. Months = calendar days / 30.44.",
        "  - CAGR = (last / first)^(1 / years) − 1, with years = calendar days between the first "
        "and last snapshot / 365.25 (Actual/365.25).",
        "  - Avg days held is the mean of the simulator's `days_held` over closed trades.",
        f"- **Tuning.** The grid is RSI {{{_plain(GRID_RSI)}}} × limit {{{_plain(GRID_LIMIT)}}} × "
        f"TP {{{_plain(GRID_TP)}}} × SL {{{_plain(GRID_SL)}}} ATR, and it runs on the in-sample "
        "window only.",
        f"  - Selection takes the highest in-sample total return among runs with max drawdown "
        f"≤ {fmt_pct(MAX_DRAWDOWN, 0)} "
        "and profit factor ≥ 1.3. Ties go to the lower max drawdown, then to grid order. If no "
        "run qualifies, the design values are kept.",
        "  - The out-of-sample window runs once, with the selected parameters, and its numbers "
        "never feed back into the selection.",
        "- **Gate.** Passes only if, out of sample, total return > total-return SPY, profit "
        f"factor ≥ 1.3 and max drawdown ≤ {fmt_pct(MAX_DRAWDOWN, 0)}. In-sample numbers never "
        "decide it.",
        "",
    ]


def _grid_section(report: BacktestReport) -> list[str]:
    sel = report.selection
    selected_index = next((i for i, r in enumerate(report.grid_rows) if r.params == sel.params), None)
    rows: list[list[str]] = []
    for i, row in enumerate(report.grid_rows):
        p = row.params.as_dict()
        m = row.metrics
        mark = ""
        if i == selected_index:
            mark = "selected" if sel.qualified else "kept (fallback)"
        rows.append(
            [
                str(i + 1),
                p["rsi_max"],
                p["limit_atr"],
                p["tp_atr"],
                p["sl_atr"],
                fmt_signed_pct(m.total_return),
                fmt_signed_pct(m.cagr),
                fmt_pct(m.win_rate),
                fmt_pf(m.profit_factor),
                fmt_pct(m.max_drawdown),
                str(m.trades),
                "yes" if qualifies(m) else "no",
                mark,
            ]
        )
    return [
        f"## In-sample grid ({len(report.grid_rows)} runs, {_span(report.in_sample.run)})",
        "",
        "Every grid run, in grid order, on the in-sample window. A run qualifies when max "
        f"drawdown ≤ {fmt_pct(MAX_DRAWDOWN, 0)} and profit factor ≥ 1.3. Selection reads these "
        "numbers and nothing else.",
        "",
        *_table(
            [
                "#",
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
            ["r"] * 11 + ["l", "l"],
            rows,
        ),
        "",
    ]


def _selection_section(report: BacktestReport) -> list[str]:
    design = DESIGN_PARAMS.as_dict()
    selected = report.selection.params.as_dict()
    frozen = report.frozen_params.as_dict()
    rows = [[k, design[k], selected[k], frozen.get(k, DASH)] for k in selected]
    if report.frozen_params == report.selection.params:
        frozen_note = "Frozen in code (`STRATEGY_A_PARAMS`): matches the selection."
    else:
        frozen_note = (
            "Frozen in code (`STRATEGY_A_PARAMS`): differs from the selection. Set it to the "
            "selection and re-run the backtest."
        )
    return [
        "## Selection",
        "",
        report.selection.reason,
        "",
        *_table(["Parameter", "Design", "Selected", "Frozen in code"], ["l", "r", "r", "r"], rows),
        "",
        frozen_note,
        "",
        FENCE + "text",
        params_line(FROZEN_KEY, report.frozen_params),
        params_line(SELECTED_KEY, report.selection.params),
        FENCE,
        "",
    ]


def _results_table(w: WindowResult) -> list[str]:
    sm = run_metrics(w.run)
    pm = curve_metrics(w.spy_price)
    tm = curve_metrics(w.spy_tr)
    reasons = dict(sm.exit_reasons)
    rows: list[list[str]] = [
        [
            "Ending equity (USD)",
            _usd(w.run.snapshots[-1].equity_usd),
            _usd(w.spy_price.snapshots[-1].equity_usd),
            _usd(w.spy_tr.snapshots[-1].equity_usd),
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
        ["Forced closes (bars ended; inside time stop)", str(forced_closes(w.run)), DASH, DASH],
        ["Open at end", str(len(w.run.open_at_end)), DASH, DASH],
        ["Months", fmt_num(sm.months, 1), fmt_num(pm.months, 1), fmt_num(tm.months, 1)],
        ["SPY shares at end", DASH, str(w.spy_price.shares), str(w.spy_tr.shares)],
        ["SPY dividends credited (USD)", DASH, DASH, _usd(w.spy_tr.dividends_usd)],
    ]
    rejected = ", ".join(f"{reason} {count:,}" for reason, count in w.run.rejections) or "none"
    return [
        f"### {w.name} ({_span(w.run)}, {_sessions(w.run):,} sessions)",
        "",
        *_table(["Metric", "Strategy A", "SPY price-only", "SPY total-return"], ["l", "r", "r", "r"], rows),
        "",
        f"Picks the simulator rejected: {rejected}.",
        "",
    ]


def _results_section(report: BacktestReport) -> list[str]:
    out = [
        "## Results",
        "",
        "In-sample shows the tuned parameters on the data they were tuned on, which is not "
        "evidence. Out-of-sample is the honest test. The full window is one continuous "
        "portfolio over both.",
        "",
    ]
    for w in report.windows():
        out += _results_table(w)
    return out


_CHECK_NOTES = (
    "#1, forward-only: information",
    "#1, forward-only: information",
    "#2, in the gate (vs total-return SPY)",
    "#3, in the gate",
    "#4, in the gate",
)


def _checklist_section(report: BacktestReport) -> list[str]:
    per_window = [
        checklist(run_metrics(w.run), curve_metrics(w.spy_tr).total_return) for w in report.windows()
    ]
    rows: list[list[str]] = []
    for k, note in enumerate(_CHECK_NOTES):
        label = per_window[0][k].label
        rows.append([label, note] + [f"{_pass(items[k].ok)}: {items[k].val}" for items in per_window])
    rows.append(
        [
            "Passed a 10-year backtest under identical rules",
            "#5, decided by the gate",
            DASH,
            f"{_pass(report.verdict.passed)}: gate verdict",
            DASH,
        ]
    )
    names = [w.name for w in report.windows()]
    return [
        "## Go-live checklist (what a backtest can evaluate)",
        "",
        "These are design §1's fixed rules, computed exactly as the web computes them. The "
        "\"months forward\" and \"100 trades\" items need forward paper trading, so here they are "
        "information only. \"Beats SPY\" compares with total-return SPY.",
        "",
        *_table(["Item", "Design §1", *names], ["l", "l", "l", "l", "l"], rows),
        "",
    ]


def _survivorship_section(report: BacktestReport) -> list[str]:
    rows: list[list[str]] = []
    tot_member = tot_missing = tot_never = tot_other = 0
    for g in report.survivorship:
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
        "This backtest can only trade stocks that still have price data. "
        f"{report.never_fetched_members:,} stocks were in the S&P 500 or the Nasdaq-100 at some "
        "point in the window, but they have no price data at all. They were delisted or bought "
        "out, and the free data source no longer serves them.",
        "",
        "On the days they were index members, Strategy A could not see them. So it never had the "
        "chance to buy one of them on the way down. A dip-buying strategy is exactly the kind "
        "that such collapses would have hurt. **These results are therefore probably better than "
        "reality**, by an amount this data cannot measure.",
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


def _order_row(o: Order) -> list[str]:
    return [
        o.symbol,
        o.status,
        str(o.slot),
        o.session_date.isoformat(),
        o.fill_date.isoformat() if o.fill_date is not None else DASH,
        str(o.fill_price) if o.fill_price is not None else DASH,
        str(o.shares),
        str(o.limit_price),
        str(o.tp_price),
        str(o.sl_price),
        str(o.days_held),
    ]


def _open_positions_section(report: BacktestReport) -> list[str]:
    out = [
        "## Open positions at end",
        "",
        "Positions still live after a window's last session are marked at that close and never "
        "sold, the same treatment as the SPY holding.",
        "",
    ]
    for w in report.windows():
        out += [f"### {w.name}", ""]
        if not w.run.open_at_end:
            out += ["None.", ""]
            continue
        out += _table(
            ["Symbol", "Status", "Slot", "Session", "Filled", "Fill price", "Shares", "Limit", "TP", "SL", "Days held"],
            ["l", "l", "r", "l", "l", "r", "r", "r", "r", "r", "r"],
            [_order_row(o) for o in w.run.open_at_end],
        )
        out.append("")
    return out


def _curves_section(report: BacktestReport) -> list[str]:
    stem = report_stem(report.data_end)
    return [
        "## Equity curves",
        "",
        f"![Strategy A vs SPY price-only and SPY total-return, full window]({stem}-equity.svg)",
        "",
        f"The daily values for the full window are in [`{stem}-equity.csv`]({stem}-equity.csv).",
        "",
    ]


def _verdict_section(report: BacktestReport) -> list[str]:
    out = ["## Gate verdict", "", report.verdict.sentence, ""]
    for c in report.verdict.checks:
        out.append(f"- {c.label}: {_pass(c.ok)} ({c.val})")
    out.append("")
    return out


def render_markdown(report: BacktestReport) -> str:
    """The full report as Markdown, ending in exactly one newline."""
    _validate(report)
    out: list[str] = [
        f"# Strategy A backtest, data through {report.data_end.isoformat()}",
        "",
        f"**Gate verdict:** {report.verdict.sentence}",
        "",
    ]
    out += _data_section(report)
    out += _method_section(report)
    out += _grid_section(report)
    out += _selection_section(report)
    out += _results_section(report)
    out += _checklist_section(report)
    out += _survivorship_section(report)
    out += _open_positions_section(report)
    out += _curves_section(report)
    out += _verdict_section(report)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- CSV


def equity_csv(report: BacktestReport) -> str:
    """Wide daily CSV of the full window: ``date,strategy_a,spy_price,spy_tr`` (USD, 4 dp)."""
    _validate(report)
    w = report.full
    lines = ["date,strategy_a,spy_price,spy_tr"]
    for a, p, t in zip(w.run.snapshots, w.spy_price.snapshots, w.spy_tr.snapshots):
        lines.append(f"{a.date.isoformat()},{a.equity_usd:f},{p.equity_usd:f},{t.equity_usd:f}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- SVG

_SVG_W = 960
_SVG_H = 460
_ML, _MR, _MT, _MB = 80, 190, 80, 40
_LABEL_GAP = 15.0
_SERIES = (("s1", "Strategy A"), ("s2", "SPY price-only"), ("s3", "SPY total-return"))
_SVG_STYLE = (
    ".bg{fill:#fcfcfb}.t1{fill:#0b0b0b}.t2{fill:#52514e}"
    ".grid{stroke:#e6e5e0;stroke-width:1}.axis{stroke:#a3a29c;stroke-width:1}"
    ".line{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}"
    ".s1{stroke:#2a78d6}.s2{stroke:#eb6834;stroke-dasharray:6 4}.s3{stroke:#1baf7a}"
    "@media (prefers-color-scheme: dark){"
    ".bg{fill:#1a1a19}.t1{fill:#ffffff}.t2{fill:#c3c2b7}"
    ".grid{stroke:#33322f}.axis{stroke:#6b6a64}"
    ".s1{stroke:#3987e5}.s2{stroke:#d95926}.s3{stroke:#199e70}}"
)


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _nice_ticks(lo: float, hi: float, target: int = 5) -> tuple[list[float], float]:
    """Round y ticks covering ``[lo, hi]``, with a step of 1, 2, 2.5 or 5 × 10^k."""
    if hi <= lo:
        hi = lo + 1.0
    raw = (hi - lo) / target
    mag = 10.0 ** math.floor(math.log10(raw))
    step = 10.0 * mag
    for m in (1.0, 2.0, 2.5, 5.0, 10.0):
        if m * mag >= raw:
            step = m * mag
            break
    first = math.floor(lo / step)
    last = math.ceil(hi / step)
    return [k * step for k in range(first, last + 1)], step


def _tick_label(v: float, step: float) -> str:
    decimals = 0 if step >= 1 and float(step).is_integer() else 2
    return f"${v:,.{decimals}f}"


def equity_svg(report: BacktestReport) -> str:
    """The full window's three equity curves as one self-contained SVG.

    It has light and dark palettes through ``prefers-color-scheme``, an opaque background,
    a legend, direct end labels and no script.
    """
    _validate(report)
    w = report.full
    curves = (w.run.snapshots, w.spy_price.snapshots, w.spy_tr.snapshots)
    dates = [s.date for s in curves[0]]
    span = (dates[-1] - dates[0]).days
    if span <= 0:
        raise ValueError("the full window needs snapshots on at least two different dates")
    values = [[float(s.equity_usd) for s in c] for c in curves]
    ticks, step = _nice_ticks(min(min(v) for v in values), max(max(v) for v in values))
    lo, hi = ticks[0], ticks[-1]
    pw = _SVG_W - _ML - _MR
    ph = _SVG_H - _MT - _MB
    bottom = _MT + ph

    def px(d: date) -> float:
        return _ML + (d - dates[0]).days / span * pw

    def py(v: float) -> float:
        return _MT + (hi - v) / (hi - lo) * ph

    returns = (
        run_metrics(w.run).total_return,
        curve_metrics(w.spy_price).total_return,
        curve_metrics(w.spy_tr).total_return,
    )
    title = f"Strategy A vs SPY, full window {_span(w.run)}"
    subtitle = (
        f"Equity in USD from {_usd(curves[0][0].equity_usd)} on {dates[0].isoformat()}; "
        "0.1% cost per side; marked at each close."
    )
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_SVG_W} {_SVG_H}" '
        f'width="{_SVG_W}" height="{_SVG_H}" role="img" aria-labelledby="title desc" '
        'font-family="system-ui, -apple-system, Segoe UI, Helvetica, Arial, sans-serif">',
        f'<title id="title">{_esc(title)}</title>',
        '<desc id="desc">Line chart of daily equity in USD for Strategy A, SPY price-only and '
        "SPY total-return over the full window. The values are in the CSV next to this file.</desc>",
        f"<style>{_SVG_STYLE}</style>",
        f'<rect class="bg" x="0" y="0" width="{_SVG_W}" height="{_SVG_H}"/>',
        f'<text class="t1" x="{_ML}" y="24" font-size="16" font-weight="600">{_esc(title)}</text>',
        f'<text class="t2" x="{_ML}" y="42" font-size="12">{_esc(subtitle)}</text>',
    ]
    legend_x = _ML
    for cls, label in _SERIES:
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
    for year in range(dates[0].year + 1, dates[-1].year + 1):
        d = date(year, 1, 1)
        if not dates[0] < d <= dates[-1]:
            continue
        x = px(d)
        out.append(f'<line class="axis" x1="{x:.1f}" y1="{bottom}" x2="{x:.1f}" y2="{bottom + 5}"/>')
        out.append(
            f'<text class="t2" x="{x:.1f}" y="{bottom + 20}" font-size="11" text-anchor="middle">{year}</text>'
        )
    for (cls, label), vals in zip(_SERIES, values):
        points = " ".join(f"{px(d):.1f},{py(v):.1f}" for d, v in zip(dates, vals))
        out.append(f'<polyline class="line {cls}" points="{points}"><title>{_esc(label)}</title></polyline>')
    ends = sorted((py(vals[-1]), i) for i, vals in enumerate(values))
    placed: list[tuple[int, float]] = []
    prev = -math.inf
    for y, i in ends:
        y = max(y, prev + _LABEL_GAP)
        placed.append((i, y))
        prev = y
    x0 = _ML + pw + 8
    for i, y in sorted(placed):
        cls, label = _SERIES[i]
        out.append(f'<line class="line {cls}" x1="{x0}" y1="{y:.1f}" x2="{x0 + 14}" y2="{y:.1f}"/>')
        out.append(
            f'<text class="t1" x="{x0 + 18}" y="{y + 4:.1f}" font-size="11">'
            f"{_esc(label)} {_esc(fmt_signed_pct(returns[i]))}</text>"
        )
    out.append("</svg>")
    return "\n".join(out) + "\n"
