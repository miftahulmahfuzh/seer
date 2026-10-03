"""Pure price value types: the daily ``Bar`` and 4-decimal price rounding.

No database and no network. ``seer_engine.bars`` re-exports everything here so existing
imports keep working; code that must stay free of ``psycopg`` (the ``sim`` core) imports
from this module instead.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

PRICE_QUANTUM = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class Bar:
    symbol: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


def to_decimal(x: Decimal | float | int | str) -> Decimal:
    """``x`` as a Decimal rounded half-up to 4 decimals (Postgres numeric rounding).

    Floats go through their shortest repr, so 0.1 becomes Decimal('0.1000'), not the
    binary expansion.
    """
    if isinstance(x, bool):
        raise TypeError("bool is not a price")
    if isinstance(x, float):
        if not math.isfinite(x):
            raise ValueError(f"non-finite value: {x!r}")
        d = Decimal(repr(x))
    else:
        d = Decimal(x)
    if not d.is_finite():
        raise ValueError(f"non-finite value: {x!r}")
    return d.quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)
