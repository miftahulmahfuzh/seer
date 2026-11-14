"""S0002 — a coin toss: a fresh hash-order draw every month.

Source: general knowledge. Idea: none, on purpose; this is the panel's known-null check. Each
month every pool member gets a number drawn from a hash of its symbol and the month, drawn again
every month (the re-drawn placebo, not the sticky one). Nothing about a company enters it, so a
panel that finds an edge here is measuring itself: its controls, its correction or a leak. It
should read as null in every era on every store.
Pure: hashlib only. No clock, randomness, files, network or printing.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from typing import Any

from seer_engine.lab.signal import Signal
from seer_engine.strategies.base import History

SALT = "S0002"


def draw(symbol: str, data_date: date) -> float:
    """A number in [0, 1) fixed by ``symbol`` and ``data_date``'s calendar month alone."""
    key = f"{SALT}:{symbol}:{data_date.year:04d}-{data_date.month:02d}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(key).digest()[:8], "big") / float(1 << 64)


def score(history: Mapping[str, History], market: Any, pool: AbstractSet[str], data_date: date) -> dict[str, float]:
    return {symbol: draw(symbol, data_date) for symbol in sorted(pool) if symbol in history}


SIGNAL = Signal(
    id="S0002",
    name="A coin toss: a fresh hash-order draw every month",
    family="stock-random-draw",
    source_kind="knowledge",
    source_ref="",
    hypothesis=(
        "None, on purpose. A ranking that knows nothing about a company should show no rank "
        "correlation, no spread and no controlled slope in any era; the panel's known-null check."
    ),
    expected_failure=(
        "A non-null reading here means the panel itself leaks or is miscalibrated, not that the "
        "coin knows something."
    ),
    lookback=1,
    score=score,
)
