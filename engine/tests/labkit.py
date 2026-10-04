"""A synthetic dev-window market for lab tests (the test_registry smoke market, any symbol set)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

import numpy as np

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.dev import DEV_END
from seer_engine.backtest.market import Market, Membership
from seer_engine.research import ResearchData
from seer_engine.strategies.base import History

SMOKE_FIRST = date(2013, 12, 2)  # 473 NYSE sessions through DEV_END
MEMBER_STOCKS: tuple[str, ...] = ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH")
BASE_ETFS: tuple[str, ...] = ("BIL", "EFA", "IEF", "QQQ", "SPY", "TLT", "GLD",
                              "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")
SPY_EX_DATE = date(2015, 6, 19)


def smoke_history(symbol: str, k: int, days: list[date]) -> History:
    """Deterministic positive prices: drift, a slow wave, a down day in three, a ~25% dip."""
    n = len(days)
    t = np.arange(n, dtype=np.float64)
    base = 40.0 + 7.0 * k
    drift = 0.0009 - 0.0004 * (k % 4)
    wave = 1.0 + 0.07 * np.sin(2.0 * np.pi * t / (60.0 + 11.0 * k) + k)
    zig = np.where(t % 3 == 0, 0.985, 1.006)
    shock = 1.0 - 0.25 * np.exp(-(((t - 380.0) / 25.0) ** 2))
    close = np.round(base * (1.0 + drift * t) * wave * zig * shock, 2)
    open_ = np.round(np.concatenate((close[:1], close[:-1])), 2)
    high = np.round(np.maximum(open_, close) * 1.01, 2)
    low = np.round(np.minimum(open_, close) * 0.99, 2)
    volume = np.full(n, 2_000_000.0, dtype=np.float64)
    return History(symbol, np.array(days, dtype="datetime64[D]"), open_, high, low, close, volume)


def smoke_market(extra: Iterable[str] = ()) -> Market:
    days = dates.sessions(SMOKE_FIRST, DEV_END)
    symbols = tuple(sorted(set(BASE_ETFS) | set(extra) - set(MEMBER_STOCKS))) + MEMBER_STOCKS
    history = {s: smoke_history(s, k, days) for k, s in enumerate(symbols)}
    membership = Membership(intervals=tuple((s, days[0], None) for s in MEMBER_STOCKS))
    return Market(history=history, membership=membership, fx=((days[0], Decimal("2000")),))


def smoke_data(extra: Iterable[str] = ()) -> ResearchData:
    spy_div = Decimal("1.0300")
    return ResearchData(
        market=smoke_market(extra),
        dividends={"SPY": {SPY_EX_DATE: spy_div}},
        spy_dividends=(Dividend(SPY_EX_DATE, spy_div),),
        fingerprint="smoke",
        manifest={},
    )
