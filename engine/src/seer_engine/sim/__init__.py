"""Seer fill simulator: pure, deterministic order lifecycle and portfolio accounting.

One code path for the backtest (P3) and nightly paper trading (P4). No database, no
network, no clock: importing this package must never load psycopg, requests or yfinance
(enforced by tests/test_sim_purity.py).

Per session S: ``apply_split`` (only if a split executes on S) -> ``step(S)`` -> persist
events and snapshot -> ``size_picks(..., next session)``. See engine/package_readme.md.
"""

from seer_engine.sim.lifecycle import close_unpriced, step
from seer_engine.sim.model import (
    COST_RATE,
    SLOTS,
    TIME_STOP_DAYS,
    Event,
    EventKind,
    ExitReason,
    Order,
    OrderStatus,
    Portfolio,
    Snapshot,
    StepResult,
    buy_cost,
    initial_cash_usd,
    new_portfolio,
    q,
    sell_proceeds,
)
from seer_engine.sim.sizing import Pick, RejectReason, Rejection, SizingResult, size_picks
from seer_engine.sim.split_adjust import apply_split

__all__ = [
    "COST_RATE",
    "SLOTS",
    "TIME_STOP_DAYS",
    "Event",
    "EventKind",
    "ExitReason",
    "Order",
    "OrderStatus",
    "Pick",
    "Portfolio",
    "RejectReason",
    "Rejection",
    "SizingResult",
    "Snapshot",
    "StepResult",
    "apply_split",
    "buy_cost",
    "close_unpriced",
    "initial_cash_usd",
    "new_portfolio",
    "q",
    "sell_proceeds",
    "size_picks",
    "step",
]
