"""The paper books' starting cash (pure; shared by the roster spec, the paper night and the replay)."""

from __future__ import annotations

from decimal import Decimal

#: The owner's own Gotrade money (2026-10-07), so the dollar amounts Positions shows are the ones
#: the owner types into Gotrade. Part of every paper spec (``roster.spec``'s ``initial_idr``).
#: The backtests keep ``backtest.runner.INITIAL_IDR`` (20,000,000 IDR; closed records, where only
#: percentages matter).
PAPER_INITIAL_IDR = Decimal("10000000")
