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
from seer_engine.backtest.window import Window
from seer_engine.lab import store
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
        price_fingerprint="smoke",
    )


# ---- the test window (build-promotion-path phase 4) ------------------------------------------

TEST_FIRST = date(2015, 10, 19)  # the first session after DEV_END: the test window opens here
TEST_LAST = date(2018, 12, 31)  # a fixture end; the real store's end is whatever its manifest says
TEST_SPY_EX_DATE = date(2016, 6, 17)


def smoke_test_window() -> Window:
    """The fixture's test window, shaped like the one a built ``engine/.research-test`` carries."""
    return Window(name="test", start=TEST_FIRST, end=TEST_LAST)


def smoke_test_market(extra: Iterable[str] = ()) -> Market:
    """``smoke_market``'s shape over test-window sessions only: no bar on or before ``DEV_END``.

    The symbols, the price generator and the membership are the dev fixture's, so a candidate that
    runs on one runs on the other and only the window differs.
    """
    days = dates.sessions(TEST_FIRST, TEST_LAST)
    assert days[0] > DEV_END  # a test fixture that straddles DEV_END would prove nothing
    symbols = tuple(sorted(set(BASE_ETFS) | set(extra) - set(MEMBER_STOCKS))) + MEMBER_STOCKS
    history = {s: smoke_history(s, k, days) for k, s in enumerate(symbols)}
    membership = Membership(intervals=tuple((s, days[0], None) for s in MEMBER_STOCKS))
    return Market(history=history, membership=membership, fx=((days[0], Decimal("2000")),))


def smoke_test_data(extra: Iterable[str] = ()) -> ResearchData:
    """A loaded *test*-window store, as ``research.load_store(d, window=declared_window(d))``
    returns one (phase 2's idiom: ask the store which window it is for, then ask for that one)."""
    spy_div = Decimal("1.1000")
    return ResearchData(
        market=smoke_test_market(extra),
        dividends={"SPY": {TEST_SPY_EX_DATE: spy_div}},
        spy_dividends=(Dividend(TEST_SPY_EX_DATE, spy_div),),
        fingerprint="smoke-test",
        # Phase 2's three optional manifest keys, spelled as it spells them. Nothing in
        # `run_test` reads the manifest -- the window travels on `ResearchData.window` -- but a
        # fixture that invents key names is a fixture that teaches the wrong ones.
        manifest={
            "window_name": "test",
            "window_start": TEST_FIRST.isoformat(),
            "window_end": TEST_LAST.isoformat(),
        },
        window=smoke_test_window(),
        price_fingerprint="smoke-test",
    )


# ---- per-trial provenance (trial-reproducibility) --------------------------------------------

#: The price fingerprint every dev trial in the committed lab carries (analysis M1): the P7a
#: store's, which is also the current dev store's with ``fundamentals.csv`` left out.
LAB_PRICE_FINGERPRINT = store.P7A_PRICE_FINGERPRINT


def stamp_provenance(
    conn,
    trial_ns: Iterable[int],
    *,
    price_fingerprint: str | None = LAB_PRICE_FINGERPRINT,
    initial_idr: Decimal = Decimal("10000000"),
) -> None:
    """Record provenance for fixture trials, the way ``lab run`` does for real ones.

    Every reader of a trial's provenance -- ``runner.recorded_capital``, the hard gate's
    de-funding -- refuses a trial with no row, so a fixture that inserts trials with
    ``store.insert_trials`` and then asks one of them anything stamps them here. ``initial_idr``
    defaults to today's ``INITIAL_IDR``, 10,000,000, so a funded fixture's de-funding unit stays
    ``5,000,000 / 10,000,000 = 0.5``; it is a ``Decimal`` because ``insert_provenance`` refuses
    anything else. The caller holds the transaction, as with every ``store.insert_*``.

    **Idempotent.** ``trial_provenance`` is append-only and refuses a second row for a trial, so
    a trial that already has one -- from ``run_method``, ``seed``, the v4 -> v5 backfill or an
    earlier stamp -- is skipped. Two fixture helpers that both stamp the same trial therefore
    never collide, and the first stamp wins.
    """
    store.insert_provenance(conn, [
        store.ProvenanceRow(
            trial_n=int(n), initial_idr=initial_idr, price_fingerprint=price_fingerprint,
            source="recorded", measured="test fixture",
        )
        for n in trial_ns
        if store.provenance_of(conn, int(n)) is None
    ])
