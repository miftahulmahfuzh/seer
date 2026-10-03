"""Parameter grid, in-sample selection and the P3 gate (handover §3 "Tuning", "Gate verdict").

Pure. The grid was fixed before any result was seen and never changes. ``select`` reads
in-sample metrics only. ``gate`` reads out-of-sample metrics only. No function here can see both
windows at once, so nothing out of sample can feed back into selection (invariant 6).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from seer_engine.backtest.metrics import CheckItem, Metrics, checklist, fmt_pct, fmt_signed_pct
from seer_engine.strategies.a import DESIGN_PARAMS, AParams

IS_START = date(2015, 10, 19)  # first session whose data_date has 200 bars of history
OOS_START = date(2022, 1, 3)  # in-sample ends at prev_session(OOS_START) = 2021-12-31

GRID_RSI: tuple[float, ...] = (5.0, 10.0, 15.0)
GRID_LIMIT: tuple[Decimal, ...] = (Decimal("0.25"), Decimal("0.5"), Decimal("0.75"))
GRID_TP: tuple[Decimal, ...] = (Decimal("0.75"), Decimal("1.0"), Decimal("1.5"))
GRID_SL: tuple[Decimal, ...] = (Decimal("1.0"), Decimal("1.5"), Decimal("2.0"))

MAX_DRAWDOWN = 0.15  # go-live #4; equals the threshold in metrics.checklist
MIN_PROFIT_FACTOR = 1.3  # go-live #3; equals the threshold in metrics.checklist

_GATE_NAMES = ("beating total-return SPY", "profit factor ≥ 1.3", "max drawdown ≤ 15%")


def grid() -> tuple[AParams, ...]:
    """The 81 parameter sets: RSI → limit → TP → SL, each ascending (SL varies fastest).

    ``min_dollar_volume`` stays at the design value. ``DESIGN_PARAMS`` is entry 40 (0-based).
    """
    return tuple(
        AParams(rsi_max=rsi, limit_atr=limit, tp_atr=tp, sl_atr=sl)
        for rsi in GRID_RSI
        for limit in GRID_LIMIT
        for tp in GRID_TP
        for sl in GRID_SL
    )


@dataclass(frozen=True)
class GridRow:
    params: AParams
    metrics: Metrics  # in-sample


@dataclass(frozen=True)
class Selection:
    params: AParams
    qualified: bool  # False: no run qualified and the design values were kept
    reason: str


@dataclass(frozen=True)
class Verdict:
    passed: bool
    checks: tuple[CheckItem, ...]  # checklist items "Beats SPY", "Profit factor ≥ 1.3", "Max drawdown ≤ 15%"
    sentence: str


def qualifies(m: Metrics) -> bool:
    """A grid run may be selected only if max DD ≤ 15% and PF ≥ 1.3 (infinite PF qualifies)."""
    return (
        m.total_return is not None
        and m.max_drawdown is not None
        and m.max_drawdown <= MAX_DRAWDOWN
        and m.profit_factor is not None
        and m.profit_factor >= MIN_PROFIT_FACTOR
    )


def select(rows: Sequence[GridRow]) -> Selection:
    """The qualifying row with the highest in-sample total return.

    Ties go to the lower max drawdown, then to the earlier grid index. When no row qualifies,
    ``DESIGN_PARAMS`` is kept with ``qualified=False``.
    """
    n = len(rows)
    candidates = [(i, row) for i, row in enumerate(rows) if qualifies(row.metrics)]
    if not candidates:
        return Selection(
            params=DESIGN_PARAMS,
            qualified=False,
            reason=(
                f"No in-sample grid run had max drawdown ≤ 15% and profit factor ≥ 1.3 (0 of {n}), "
                "so the design values are kept."
            ),
        )
    best_i, best = min(
        candidates,
        key=lambda c: (-c[1].metrics.total_return, c[1].metrics.max_drawdown, c[0]),
    )
    tied = 0
    for _, row in candidates:
        if row.metrics.total_return == best.metrics.total_return:
            tied += 1
    reason = (
        f"Grid run #{best_i + 1} has the highest in-sample total return "
        f"({fmt_signed_pct(best.metrics.total_return)}, max drawdown {fmt_pct(best.metrics.max_drawdown)}) "
        f"among the {len(candidates)} of {n} runs with max drawdown ≤ 15% and profit factor ≥ 1.3"
    )
    if tied > 1:
        reason += f"; {tied} runs tied on return, broken by the lower max drawdown, then grid order"
    return Selection(params=best.params, qualified=True, reason=reason + ".")


def _join(items: Sequence[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def gate(oos: Metrics, spy_tr_oos: Metrics) -> Verdict:
    """The P3 gate, decided by out-of-sample results only.

    It passes when total return > total-return SPY (strict), profit factor ≥ 1.3 and max
    drawdown ≤ 15%. The checks are ``checklist`` items 3–5, so the labels and value strings
    match the web.
    """
    beats, pf, dd = checklist(oos, spy_tr_oos.total_return)[2:5]
    checks = (beats, pf, dd)
    passed = beats.ok and pf.ok and dd.ok
    said = (
        f"out of sample it returned {fmt_signed_pct(oos.total_return)} against "
        f"{fmt_signed_pct(spy_tr_oos.total_return)} for total-return SPY, with profit factor "
        f"{pf.val} and max drawdown {dd.val}"
    )
    if passed:
        sentence = f"Strategy A passes the P3 gate: {said}."
    else:
        failed = [name for name, item in zip(_GATE_NAMES, checks) if not item.ok]
        sentence = (
            f"Strategy A fails the P3 gate: {said}, so it fails on {_join(failed)}; "
            "P4 must not start until Strategy A is reworked."
        )
    return Verdict(passed=passed, checks=checks, sentence=sentence)
