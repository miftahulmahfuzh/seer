"""The book runner, the trade-rules dispatch, run statistics and the §5 parity (plan phase 3; R1, R8).

Four groups:

1. ``run_rules(..., DESIGN_V0)`` IS ``run_backtest``: ``==`` results for Strategy A, A2 and B (a
   fake linear Predictor) on seeded synthetic markets, prepared and plain.
2. The V0 parity: ``run_book(PICKS, PicksParams(strategy, params), V0_BOOK)`` replays
   ``run_backtest(strategy, params)`` exactly: the same (date, cash, equity) snapshots, the same
   closed-trade multiset, the same fill multiset and the same positions left open. Seed 39's
   market is checked to exercise every simulator path (TP, SL, gap, time stop, forced close
   when bars end, lt_one_share, no_slot, unfilled limits); the hand-checked FixedPicks scenario
   of tests/test_backtest_runner.py adds a halt while held and a member leaving while held.
3. ``run_book`` wiring with a scripted fake allocator and a recording ``step_book``: cadence,
   no look-ahead, members and held, the idle residual target, bar and dividend routing, forced
   closes, rejection and cost accounting, determinism.
4. ``run_stats`` hand-checked on a small RunResult and a small BookResult, and equal on the two
   sides of the parity.

Simulator arithmetic (``seer_engine.sim``): buy cash ``q(p x n x 1.001)``, sell proceeds
``q(p x n x 0.999)``, fee ``q(p x n x 0.001)``, ``q`` = 4 dp half-up.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from typing import Any

import numpy as np
import pytest
from simkit import D, P, opened
from stratkit import drop_days, hist, session_days, truncate_before
from test_backtest_runner import END as V0_END
from test_backtest_runner import START as V0_START
from test_backtest_runner import TABLE as V0_TABLE
from test_backtest_runner import FixedPicks, scenario_market

from seer_engine import dates
from seer_engine.backtest import book_runner
from seer_engine.backtest.book_runner import (
    BOOK_EXIT_REASONS,
    BookResult,
    run_book,
    run_rules,
    run_stats,
)
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.metrics import run_metrics, strategy_metrics
from seer_engine.backtest.runner import RunResult, run_backtest
from seer_engine.prices import to_decimal
from seer_engine.sim import Event, Snapshot, q
from seer_engine.sim.book import BookSnapshot, Fill, Target, Trade
from seer_engine.sim.book import step_book as real_step_book
from seer_engine.sim.rules import (
    MONTHLY_RANK_WEEKLY_RESIZE,
    DAILY_SWITCH,
    DAILY_SWITCH_TBILL,
    DESIGN_V0,
    MONTHLY_HOLD,
    V0_BOOK,
    WEEKLY_HOLD,
    is_decision_session,
)
from seer_engine.strategies.a import DESIGN_PARAMS, STRATEGY_A
from seer_engine.strategies.a2 import STRATEGY_A2, A2Params
from seer_engine.strategies.allocator import PICKS, PicksParams
from seer_engine.strategies.b import FEATURE_NAMES, STRATEGY_B, BParams
from seer_engine.strategies.base import History

# =========================================================================== seeded markets
#
# 16 member stocks S00..S15 plus SPY (never a member) on 380 sessions from 2019-01-02. The first
# 200 are warm-up (Strategy A/A2/B lookback); the window is the last 180 sessions,
# 2019-10-17 .. 2020-07-06. Prices span 12 .. 700, so with 20,000,000 IDR at 16000 (1250 USD,
# a 312.5 slot) the dear names are rejected lt_one_share. Seven names stop trading inside the
# window (forced closes when held); two have short halts. Gaps of 3-6 % on ~4 % of opens.

N_SESSIONS = 380
WARMUP = 200
SEED_DAYS = session_days(N_SESSIONS)
START_PRICES = (12.0, 18.0, 25.0, 31.0, 40.0, 48.0, 60.0, 75.0, 90.0, 120.0, 150.0, 200.0, 250.0, 420.0, 700.0, 33.0)
SEED_SYMBOLS = tuple(f"S{i:02d}" for i in range(len(START_PRICES)))
DELIST = {"S01": 240, "S03": 262, "S05": 281, "S07": 301, "S09": 322, "S10": 341, "S12": 360}  # first missing index
HALT = {"S04": (250, 251, 252), "S08": (300, 301)}
SEED_START, SEED_END = SEED_DAYS[WARMUP], SEED_DAYS[-1]
SEED_FX = ((date(2018, 12, 31), Decimal("16000")),)


def _series(rng: np.random.Generator, p0: float, n: int, drift: float, vol: float) -> tuple[np.ndarray, ...]:
    """(open, high, low, close, volume), 2 dp. Draw order is fixed: changing it changes every seed."""
    rets = rng.normal(drift, vol, n)
    close = p0 * np.exp(np.cumsum(rets))
    gaps = rng.normal(0.0, 0.006, n)
    big = rng.random(n) < 0.04
    gaps = np.where(big, rng.choice([-1.0, 1.0], n) * rng.uniform(0.03, 0.06, n), gaps)
    prev = np.concatenate([[p0], close[:-1]])
    open_ = prev * np.exp(gaps)
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.008, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.008, n)))
    volume = np.full(n, 3_000_000.0)
    return np.round(open_, 2), np.round(high, 2), np.round(low, 2), np.round(close, 2), volume


def _history(symbol: str, cols: tuple[np.ndarray, ...], keep: np.ndarray) -> History:
    o, h, lo, c, v = cols
    days = np.array(SEED_DAYS, dtype="datetime64[D]")[keep]
    return History(
        symbol,
        days,
        o[keep].astype(np.float64),
        h[keep].astype(np.float64),
        lo[keep].astype(np.float64),
        c[keep].astype(np.float64),
        v[keep].astype(np.float64),
    )


@lru_cache(maxsize=None)
def seeded_market(seed: int) -> Market:
    rng = np.random.default_rng(seed)
    histories: dict[str, History] = {}
    for symbol, p0 in zip(SEED_SYMBOLS, START_PRICES):
        cols = _series(rng, p0, N_SESSIONS, 0.0015, 0.022)
        keep = np.ones(N_SESSIONS, dtype=bool)
        if symbol in DELIST:
            keep[DELIST[symbol]:] = False
        for k in HALT.get(symbol, ()):
            keep[k] = False
        histories[symbol] = _history(symbol, cols, keep)
    histories["SPY"] = _history("SPY", _series(rng, 300.0, N_SESSIONS, 0.0006, 0.009), np.ones(N_SESSIONS, dtype=bool))
    intervals = tuple((s, date(2010, 1, 4), None) for s in SEED_SYMBOLS)
    return Market(history=dict(sorted(histories.items())), membership=Membership(intervals), fx=SEED_FX)


@dataclass(frozen=True)
class Linear:
    """A fake fitted B model: ``bias + sum_j X[:, j] x weights[j]``, row by row."""

    weights: tuple[float, ...]
    bias: float = 0.0

    def predict(self, X: np.ndarray) -> np.ndarray:
        acc = np.full(X.shape[0], self.bias, dtype=np.float64)
        for j, w in enumerate(self.weights):
            acc = acc + X[:, j] * w
        return acc


B_PARAMS = BParams(Linear(tuple({"ret_1": -1.0, "rsi_2": -0.01}.get(n, 0.0) for n in FEATURE_NAMES), bias=0.3))
STRATEGIES: dict[str, tuple[Any, Any]] = {
    "A": (STRATEGY_A, DESIGN_PARAMS),
    "A2": (STRATEGY_A2, A2Params(variant="regime_calm")),
    "B": (STRATEGY_B, B_PARAMS),
}


@lru_cache(maxsize=None)
def strategy_prepared(seed: int, key: str) -> Any:
    return STRATEGIES[key][0].prepare(seeded_market(seed).history)


@lru_cache(maxsize=None)
def picks_prepared(seed: int) -> Any:
    return PICKS.prepare(seeded_market(seed).history)


@lru_cache(maxsize=None)
def sim_run(seed: int, key: str) -> RunResult:
    strategy, params = STRATEGIES[key]
    return run_backtest(
        seeded_market(seed), strategy, params, SEED_START, SEED_END, prepared=strategy_prepared(seed, key)
    )


@lru_cache(maxsize=None)
def book_run(seed: int, key: str) -> BookResult:
    strategy, params = STRATEGIES[key]
    return run_book(
        seeded_market(seed),
        PICKS,
        PicksParams(strategy, params),
        V0_BOOK,
        SEED_START,
        SEED_END,
        prepared=picks_prepared(seed),
    )


# --------------------------------------------------------------------------- comparison keys

SIM_REASON = {
    "tp": ("tp", False),
    "sl": ("sl", False),
    "gap": ("gap", False),
    "time": ("time", False),
    "forced": ("time", True),
}


def sim_snaps(r: RunResult) -> list[tuple[date, Decimal, Decimal]]:
    return [(s.date, s.cash_usd, s.equity_usd) for s in r.snapshots]


def book_snaps(r: BookResult) -> list[tuple[date, Decimal, Decimal]]:
    return [(s.date, s.cash_usd, s.equity_usd) for s in r.snapshots]


def sim_trades(r: RunResult) -> Counter[tuple[Any, ...]]:
    return Counter(
        (
            e.order.symbol,
            e.order.fill_date,
            e.order.fill_price,
            e.order.exit_date,
            e.order.exit_price,
            e.order.exit_reason,
            e.forced,
            e.order.pnl_usd,
            e.order.days_held,
        )
        for e in r.events
        if e.kind == "exit"
    )


def book_trades(r: BookResult) -> Counter[tuple[Any, ...]]:
    out: Counter[tuple[Any, ...]] = Counter()
    for t in r.trades:
        reason, forced = SIM_REASON.get(t.exit_reason, (t.exit_reason, None))
        out[(t.symbol, t.entry_date, t.entry_price, t.exit_date, t.exit_price, reason, forced, t.pnl_usd, t.days_held)] += 1
    return out


def sim_fills(r: RunResult) -> Counter[tuple[Any, ...]]:
    out: Counter[tuple[Any, ...]] = Counter()
    for e in r.events:
        if e.kind == "fill":
            out[(e.session_date, e.order.symbol, "buy", Decimal(e.order.shares), e.order.fill_price, e.cash_usd)] += 1
        elif e.kind == "exit":
            out[(e.session_date, e.order.symbol, "sell", Decimal(e.order.shares), e.order.exit_price, e.cash_usd)] += 1
    return out


def book_fills(r: BookResult) -> Counter[tuple[Any, ...]]:
    return Counter((f.session_date, f.symbol, f.side, f.shares, f.price, f.cash_usd) for f in r.fills)


def sim_open(r: RunResult) -> list[tuple[Any, ...]]:
    return sorted((o.symbol, Decimal(o.shares), o.fill_date, o.fill_price, o.days_held) for o in r.open_at_end)


def book_open(r: BookResult) -> list[tuple[Any, ...]]:
    return sorted((p.symbol, p.shares, p.entry_date, p.entry_price, p.days_held) for p in r.open_at_end)


def sim_paths(r: RunResult) -> tuple[Counter[tuple[Any, bool]], dict[str, int], int]:
    exits = Counter((e.order.exit_reason, e.forced) for e in r.events if e.kind == "exit")
    expired = sum(1 for e in r.events if e.kind == "expire")
    return exits, dict(r.rejections), expired


# =========================================================================== 1. DESIGN_V0 dispatch


@pytest.mark.parametrize("key", ["A", "A2", "B"])
def test_run_rules_design_v0_is_run_backtest(key):
    market = seeded_market(39)
    strategy, params = STRATEGIES[key]
    prepared = strategy_prepared(39, key)
    got = run_rules(market, strategy, params, DESIGN_V0, SEED_START, SEED_END, prepared=prepared)
    assert isinstance(got, RunResult)
    assert got == run_backtest(market, strategy, params, SEED_START, SEED_END, prepared=prepared)
    assert got == sim_run(39, key)


def test_run_rules_design_v0_plain_path_is_run_backtest():
    market = seeded_market(39)
    got = run_rules(market, STRATEGY_A, DESIGN_PARAMS, DESIGN_V0, SEED_START, SEED_END)
    assert got == run_backtest(market, STRATEGY_A, DESIGN_PARAMS, SEED_START, SEED_END)
    assert got == sim_run(39, "A")  # and the prepared path agrees (the Strategy contract)


def test_run_rules_design_v0_ignores_dividends_and_checks_usd_idr():
    market = seeded_market(39)
    prepared = strategy_prepared(39, "A")
    divs = {s: {SEED_DAYS[WARMUP + k]: Decimal("0.5") for k in range(0, 180, 7)} for s in SEED_SYMBOLS}
    got = run_rules(
        market, STRATEGY_A, DESIGN_PARAMS, DESIGN_V0, SEED_START, SEED_END,
        prepared=prepared, dividends=divs, usd_idr=Decimal("16000"),
    )
    assert got == sim_run(39, "A")
    with pytest.raises(ValueError, match="usd_idr_on"):
        run_rules(market, STRATEGY_A, DESIGN_PARAMS, DESIGN_V0, SEED_START, SEED_END, usd_idr=Decimal("15000"))


def test_run_rules_rejects_mismatched_pairings():
    market = wiring_market()
    with pytest.raises(TypeError, match="Strategy"):
        run_rules(market, PICKS, PicksParams(STRATEGY_A, DESIGN_PARAMS), DESIGN_V0, W_START, W_END)
    with pytest.raises(TypeError, match="Allocator"):
        run_rules(market, STRATEGY_A, DESIGN_PARAMS, V0_BOOK, W_START, W_END)
    with pytest.raises(TypeError, match="Allocator"):
        run_rules(market, STRATEGY_A, DESIGN_PARAMS, DAILY_SWITCH, W_START, W_END)
    with pytest.raises(TypeError, match="TradeRules"):
        run_rules(market, STRATEGY_A, DESIGN_PARAMS, "design-v0", W_START, W_END)


def test_run_rules_book_engine_is_run_book():
    market = wiring_market()
    divs = {"AAA": {D("2025-02-27"): Decimal("0.25")}}
    spec = (("AAA", "0.5"),)
    got = run_rules(market, Scripted(spec), None, DAILY_SWITCH, W_START, W_END, dividends=divs, usd_idr=Decimal("8000"))
    want = run_book(market, Scripted(spec), None, DAILY_SWITCH, W_START, W_END, dividends=divs, usd_idr=Decimal("8000"))
    assert isinstance(got, BookResult)
    assert got == want
    assert got.initial_cash == P("2500")


# =========================================================================== 2. the V0 parity


@pytest.mark.parametrize("key", ["A", "A2", "B"])
def test_seeded_market_exercises_every_v0_path(key):
    exits, rejections, expired = sim_paths(sim_run(39, key))
    for path in (("tp", False), ("sl", False), ("gap", False), ("time", False), ("time", True)):
        assert exits[path] >= 1, f"seed 39 / {key} never exits by {path}"
    assert rejections.get("no_slot", 0) >= 1
    assert rejections.get("lt_one_share", 0) >= 1
    assert expired >= 1


@pytest.mark.parametrize("seed", [39, 4])
@pytest.mark.parametrize("key", ["A", "A2", "B"])
def test_v0_book_replays_run_backtest(key, seed):
    sim, book = sim_run(seed, key), book_run(seed, key)
    assert book.allocator_id == "PICKS"
    assert book.rules == V0_BOOK
    assert (book.start, book.end) == (sim.start, sim.end)
    assert (book.usd_idr, book.initial_cash) == (sim.usd_idr, sim.initial_cash)
    assert book_snaps(book) == sim_snaps(sim)
    assert book_trades(book) == sim_trades(sim)
    assert book_fills(book) == sim_fills(sim)
    assert book_open(book) == sim_open(sim)
    assert book.dividends_usd == 0
    assert all(not t.idle for t in book.trades)


@pytest.mark.parametrize("key", ["A", "A2", "B"])
def test_v0_book_rejections_map_to_the_simulators(key):
    sim, book = sim_run(39, key), book_run(39, key)
    _, sim_rej, expired = sim_paths(sim)
    got = dict(book.rejections)
    assert set(got) <= {"no_slot", "too_small", "unfilled", "no_bar"}
    assert got.get("no_slot", 0) == sim_rej.get("no_slot", 0)
    assert got.get("too_small", 0) == sim_rej.get("lt_one_share", 0)
    assert got.get("unfilled", 0) + got.get("no_bar", 0) == expired
    # Strategy picks for a held symbol are dropped by PICKS, never placed: the simulator's
    # "held" rejections have no book counterpart.
    assert "held" not in got


def test_v0_book_hand_checked_scenario():
    """tests/test_backtest_runner.py's hand-checked scenario, replayed by the book engine.

    It adds what seed 39 lacks: a halt while held (DDD, 03-11..03-13), a member leaving the
    index while held (CCC), a pick of a held symbol (BBB on 03-06) and a forced close at the
    mark (BBB on 03-06). Every number below is the hand-checked one from that file.
    """
    market = scenario_market()
    sim = run_backtest(market, FixedPicks(V0_TABLE), None, V0_START, V0_END)
    book = run_book(market, PICKS, PicksParams(FixedPicks(V0_TABLE), None), V0_BOOK, V0_START, V0_END)
    assert book_snaps(book) == sim_snaps(sim)
    assert book.snapshots[0] == BookSnapshot(D("2025-03-03"), P("1250"), P("1250"), P("0"))
    assert book.snapshots[-1] == BookSnapshot(D("2025-03-14"), P("940.5647"), P("1286.1647"), P("345.6"))  # 64 x 5.4
    want = Counter({
        ("AAA", D("2025-03-04"), P("10"), D("2025-03-05"), P("11"), "tp", False, P("30.3490"), 2): 1,
        ("BBB", D("2025-03-04"), P("19.5"), D("2025-03-06"), P("20.2"), "time", True, P("9.9045"), 3): 1,
        ("CCC", D("2025-03-06"), P("49.8"), D("2025-03-10"), P("45"), "sl", False, P("-29.3688"), 3): 1,
    })
    assert book_trades(book) == want == sim_trades(sim)
    assert book_fills(book) == sim_fills(sim)
    assert book_open(book) == [("DDD", Decimal(64), D("2025-03-10"), P("5"), 5)] == sim_open(sim)
    got = dict(book.rejections)
    assert got.get("unfilled") == 1  # DDD on 03-07: low 5.05 is not < 5
    # EEE (no bars at all, too dear for one share) is "too_small" if PICKS offers it, or never
    # offered if PICKS drops symbols without a bar on data_date (the Allocator contract).
    assert set(got) <= {"too_small", "unfilled"}


def test_v0_book_prepared_equals_plain():
    strategy, params = STRATEGIES["A"]
    plain = run_book(seeded_market(39), PICKS, PicksParams(strategy, params), V0_BOOK, SEED_START, SEED_END)
    assert plain == book_run(39, "A")


@pytest.mark.parametrize("key", ["A", "B"])
def test_run_stats_agree_on_the_parity_runs(key):
    rs, bs = run_stats(sim_run(39, key)), run_stats(book_run(39, key))
    rm, bm = rs.metrics, bs.metrics
    assert (bm.total_return, bm.max_drawdown, bm.months, bm.cagr) == (rm.total_return, rm.max_drawdown, rm.months, rm.cagr)
    assert (bm.trades, bm.win_rate, bm.avg_days_held) == (rm.trades, rm.win_rate, rm.avg_days_held)
    # P/L sums run in each engine's exit order (slot vs symbol within a session): equal to rounding.
    assert bm.profit_factor == pytest.approx(rm.profit_factor, rel=1e-12)
    sim_reasons, book_reasons = dict(rm.exit_reasons), dict(bm.exit_reasons)
    forced = sim_paths(sim_run(39, key))[0][("time", True)]
    assert [r for r, _ in bm.exit_reasons] == list(BOOK_EXIT_REASONS)
    assert book_reasons["forced"] == forced
    assert book_reasons["time"] == sim_reasons["time"] - forced
    assert book_reasons["signal"] == 0
    assert all(book_reasons[r] == sim_reasons[r] for r in ("tp", "sl", "gap"))
    for name in ("exposure", "turnover", "costs_usd", "gross_pnl_usd", "cost_drag", "dividends_usd",
                 "sharpe", "daily_returns", "year_returns", "worst_year"):
        assert getattr(bs, name) == getattr(rs, name), name
    assert [y for y, _ in rs.year_returns] == [2019, 2020]


# =========================================================================== 3. run_book wiring
#
# Sessions 2025-02-14 .. 2025-03-14 (02-17 is a holiday); the window is 02-24 .. 03-14, 15
# sessions. AAA closes 10.0 + 0.1 t, BBB 20.0 + 0.2 t, BIL 100 flat (spread 0.05), CCC 30 flat;
# open = close, high/low = close +/- spread (stratkit.hist). USD/IDR 16000 -> 1250.0000 USD.
# AAA, BBB and CCC are members; BIL is not.

W_DAYS = dates.sessions(D("2025-02-14"), D("2025-03-14"))
W_START, W_END = D("2025-02-24"), D("2025-03-14")
W_FX = ((D("2025-02-13"), Decimal("16000")),)
W_MEMBERS = (
    ("AAA", D("2020-01-02"), None),
    ("BBB", D("2020-01-02"), None),
    ("CCC", D("2020-01-02"), None),
)


def wiring_market(
    *, bil_from: date | None = None, aaa_until: date | None = None, ccc_missing: tuple[date, ...] = ()
) -> Market:
    n = len(W_DAYS)
    aaa = hist("AAA", [round(10.0 + 0.1 * t, 2) for t in range(n)], days=W_DAYS)
    bbb = hist("BBB", [round(20.0 + 0.2 * t, 2) for t in range(n)], days=W_DAYS)
    bil = hist("BIL", [100.0] * n, days=W_DAYS, spread=0.05)
    ccc = hist("CCC", [30.0] * n, days=W_DAYS)
    if aaa_until is not None:
        aaa = truncate_before(aaa, dates.next_session(aaa_until))
    if bil_from is not None:
        bil = drop_days(bil, [d for d in W_DAYS if d < bil_from])
    if ccc_missing:
        ccc = drop_days(ccc, ccc_missing)
    return Market(
        history={"AAA": aaa, "BBB": bbb, "BIL": bil, "CCC": ccc},
        membership=Membership(W_MEMBERS),
        fx=W_FX,
    )


Spec = tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Call:
    path: str
    data_date: date
    members: frozenset[str]
    held: frozenset[str]
    seen: date | None  # latest bar date in the histories handed over (plain path only)


class Scripted:
    """A fake Allocator: fixed ``(symbol, weight)`` targets per data_date (``default`` otherwise),
    each priced at its close on data_date. A symbol without a bar dated data_date is skipped
    (never a new target). Records every call."""

    id = "SCRIPTED"

    def __init__(self, default: Spec = (), table: Mapping[date, Spec] | None = None):
        self.default = default
        self.table = dict(table or {})
        self.calls: list[Call] = []

    def lookback(self, params: Any) -> int:
        return 1

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ()

    def holds(self, params: Any) -> tuple[str, ...]:
        return ()

    def uses_members(self, params: Any) -> bool:
        return True

    def _targets(self, closes: Mapping[str, float], data_date: date) -> tuple[Target, ...]:
        out = []
        for symbol, weight in self.table.get(data_date, self.default):
            if symbol in closes:
                out.append(Target(symbol=symbol, weight=Decimal(weight), last=to_decimal(closes[symbol])))
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        seen = max(h.last_date() for h in history.values() if len(h))
        self.calls.append(Call("plain", data_date, frozenset(members), held, seen))
        closes = {s: float(h.close[-1]) for s, h in history.items() if len(h) and h.last_date() == data_date}
        return self._targets(closes, data_date)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        self.calls.append(Call("prepared", data_date, frozenset(members), held, None))
        closes: dict[str, float] = {}
        for s, h in prepared.items():
            i = h.index_of(data_date)
            if i is not None:
                closes[s] = float(h.close[i])
        return self._targets(closes, data_date)


@dataclass(frozen=True)
class StepCall:
    session: date
    bar_symbols: tuple[str, ...]
    targets: tuple[Target, ...] | None
    dividends: dict[str, Decimal]
    idle_symbol_ok: bool


@pytest.fixture
def steps(monkeypatch):
    """Every ``step_book`` call ``run_book`` makes, recorded, then run for real."""
    calls: list[StepCall] = []

    def spy(book, session, bars, targets, rules, dividends, *, idle_symbol_ok):
        calls.append(StepCall(session, tuple(sorted(bars)), targets, dict(dividends), idle_symbol_ok))
        return real_step_book(book, session, bars, targets, rules, dividends, idle_symbol_ok=idle_symbol_ok)

    monkeypatch.setattr(book_runner, "step_book", spy)
    return calls


def _held_shares(r: BookResult, symbol: str, before: date) -> Decimal:
    total = Decimal(0)
    for f in r.fills:
        if f.symbol == symbol and f.session_date < before:
            total += f.shares if f.side == "buy" else -f.shares
    return total


def test_run_book_rejects_the_bracket_engine():
    with pytest.raises(ValueError, match="run_rules"):
        run_book(wiring_market(), Scripted(), None, DESIGN_V0, W_START, W_END)


def test_run_book_type_and_window_checks():
    market = wiring_market()
    with pytest.raises(TypeError, match="Market"):
        run_book("market", Scripted(), None, DAILY_SWITCH, W_START, W_END)
    with pytest.raises(TypeError, match="Allocator"):
        run_book(market, STRATEGY_A, DESIGN_PARAMS, DAILY_SWITCH, W_START, W_END)
    with pytest.raises(TypeError, match="TradeRules"):
        run_book(market, Scripted(), None, "daily-switch", W_START, W_END)
    with pytest.raises(TypeError, match="Mapping"):
        run_book(market, Scripted(), None, DAILY_SWITCH, W_START, W_END, dividends=[("AAA", 1)])
    with pytest.raises(TypeError, match="date"):
        run_book(market, Scripted(), None, DAILY_SWITCH, datetime(2025, 2, 24), W_END)
    with pytest.raises(ValueError, match="NYSE session"):
        run_book(market, Scripted(), None, DAILY_SWITCH, D("2025-02-23"), W_END)
    with pytest.raises(ValueError, match="before start"):
        run_book(market, Scripted(), None, DAILY_SWITCH, W_END, W_START)


def test_run_book_first_snapshot_and_cash():
    market = wiring_market()
    r = run_book(market, Scripted(), None, DAILY_SWITCH, W_START, W_END)
    assert (r.allocator_id, r.params, r.rules, r.start, r.end) == ("SCRIPTED", None, DAILY_SWITCH, W_START, W_END)
    assert (r.usd_idr, r.initial_cash) == (Decimal("16000"), P("1250"))
    assert r.snapshots[0] == BookSnapshot(D("2025-02-21"), P("1250"), P("1250"), P("0"))
    assert [s.date for s in r.snapshots[1:]] == dates.sessions(W_START, W_END)
    assert len(r.snapshots) == 16
    # Nothing targeted: nothing traded, cash flat.
    assert r.fills == () and r.trades == () and r.open_at_end == () and r.rejections == ()
    assert all(s == BookSnapshot(s.date, P("1250"), P("1250"), P("0")) for s in r.snapshots)
    other = run_book(market, Scripted(), None, DAILY_SWITCH, W_START, W_END, usd_idr=Decimal("8000"))
    assert (other.usd_idr, other.initial_cash) == (Decimal("8000"), P("2500"))
    assert other.snapshots[0] == BookSnapshot(D("2025-02-21"), P("2500"), P("2500"), P("0"))


@pytest.mark.parametrize(
    ("rules", "data_dates"),
    [
        (DAILY_SWITCH, [dates.prev_session(s) for s in dates.sessions(W_START, W_END)]),
        (WEEKLY_HOLD, [D("2025-02-21"), D("2025-02-28"), D("2025-03-07")]),   # Mondays 02-24, 03-03, 03-10
        (MONTHLY_HOLD, [D("2025-02-28")]),                                     # 03-03, first session of March
    ],
    ids=["daily", "weekly", "monthly"],
)
def test_cadence_follows_is_decision_session(steps, rules, data_dates):
    alloc = Scripted((("AAA", "0.5"),))
    run_book(wiring_market(), alloc, None, rules, W_START, W_END)
    decision = [s for s in dates.sessions(W_START, W_END) if is_decision_session(rules, s)]
    assert [c.data_date for c in alloc.calls] == data_dates == [dates.prev_session(s) for s in decision]
    assert [c.session for c in steps] == dates.sessions(W_START, W_END)
    for c in steps:
        assert (c.targets is not None) == (c.session in decision), c.session


def test_allocator_sees_history_through_data_date_members_and_held():
    market = wiring_market()
    alloc = Scripted((("AAA", "0.5"),))
    r = run_book(market, alloc, None, DAILY_SWITCH, W_START, W_END)
    assert [c.path for c in alloc.calls] == ["plain"] * 15
    for c in alloc.calls:
        assert c.seen == c.data_date  # no bar after data_date reaches the allocator
        assert c.members == market.membership.members_on(c.data_date) == frozenset({"AAA", "BBB", "CCC"})
    # AAA is bought at 02-24's open (open_limit at last x 1.02 fills) and kept: held from then on.
    assert alloc.calls[0].held == frozenset()
    assert all(c.held == frozenset({"AAA"}) for c in alloc.calls[1:])
    assert [p.symbol for p in r.open_at_end] == ["AAA"]


def test_prepared_and_plain_book_runs_agree():
    market = wiring_market()
    spec = (("AAA", "0.4"), ("BBB", "0.4"))
    plain_alloc, prep_alloc = Scripted(spec), Scripted(spec)
    plain = run_book(market, plain_alloc, None, DAILY_SWITCH_TBILL, W_START, W_END)
    prepared = run_book(
        market, prep_alloc, None, DAILY_SWITCH_TBILL, W_START, W_END, prepared=prep_alloc.prepare(market.history)
    )
    assert plain == prepared
    assert {c.path for c in plain_alloc.calls} == {"plain"}
    assert {c.path for c in prep_alloc.calls} == {"prepared"}
    assert [c.data_date for c in plain_alloc.calls] == [c.data_date for c in prep_alloc.calls]


@pytest.mark.parametrize(
    ("spec", "idle_weight"),
    [((("AAA", "0.6"),), "0.4"), ((), "1"), ((("AAA", "0.5"), ("BBB", "0.5")), None)],
    ids=["residual", "all-idle", "fully-invested"],
)
def test_idle_residual_target(steps, spec, idle_weight):
    run_book(wiring_market(), Scripted(spec), None, DAILY_SWITCH_TBILL, W_START, D("2025-02-28"))
    assert len(steps) == 5
    for c in steps:
        assert c.targets is not None
        assert [(t.symbol, t.weight) for t in c.targets[: len(spec)]] == [(s, Decimal(w)) for s, w in spec]
        if idle_weight is None:
            assert len(c.targets) == len(spec)
            assert c.idle_symbol_ok is False
        else:
            assert len(c.targets) == len(spec) + 1
            assert c.targets[-1] == Target(symbol="BIL", weight=Decimal(idle_weight), last=P("100"))
            assert c.idle_symbol_ok is True
            assert "BIL" in c.bar_symbols


def test_idle_needs_a_bar_on_data_date(steps):
    # BIL trades from 02-26: data dates 02-21, 02-24, 02-25 have no BIL bar, 02-26 and 02-27 do.
    run_book(wiring_market(bil_from=D("2025-02-26")), Scripted((("AAA", "0.5"),)), None, DAILY_SWITCH_TBILL,
             W_START, D("2025-02-28"))
    with_idle = [c.session for c in steps if c.targets and c.targets[-1].symbol == "BIL"]
    assert with_idle == [D("2025-02-27"), D("2025-02-28")]
    assert [c.idle_symbol_ok for c in steps] == [False, False, False, True, True]


def test_allocator_may_not_target_the_idle_symbol():
    with pytest.raises(ValueError, match="idle symbol BIL"):
        run_book(wiring_market(), Scripted((("BIL", "0.5"),)), None, DAILY_SWITCH_TBILL, W_START, W_END)


def test_allocator_never_sees_the_idle_position_as_held():
    # D-J: BIL (the idle instrument) is really held from 02-24, yet no allocator call sees it.
    alloc = Scripted((("AAA", "0.5"),))
    r = run_book(wiring_market(), alloc, None, DAILY_SWITCH_TBILL, W_START, W_END)
    assert "BIL" in {p.symbol for p in r.open_at_end}
    assert all("BIL" not in c.held for c in alloc.calls)
    assert all(c.held == frozenset({"AAA"}) for c in alloc.calls[1:])


def test_idle_never_added_on_non_decision_sessions(steps):
    weekly_tbill = replace(WEEKLY_HOLD, id="weekly-hold-tbill", idle_symbol="BIL")
    run_book(wiring_market(), Scripted((("AAA", "0.5"),)), None, weekly_tbill, W_START, D("2025-03-07"))
    for c in steps:
        if c.session in (D("2025-02-24"), D("2025-03-03")):
            assert c.targets is not None and c.targets[-1].symbol == "BIL" and c.idle_symbol_ok is True
        else:
            assert c.targets is None and c.idle_symbol_ok is False


def test_bars_routing_and_rejection_accounting(steps):
    # CCC is targeted for 03-04 only and has no bar that day: "no_bar", never held.
    market = wiring_market(ccc_missing=(D("2025-03-04"),))
    alloc = Scripted((("AAA", "0.5"),), table={D("2025-03-03"): (("AAA", "0.5"), ("CCC", "0.2"))})
    r = run_book(market, alloc, None, DAILY_SWITCH, W_START, W_END)
    on_0304 = next(c for c in steps if c.session == D("2025-03-04"))
    assert [t.symbol for t in on_0304.targets] == ["AAA", "CCC"]
    assert all(c.bar_symbols == ("AAA",) for c in steps)  # held or targeted, with a bar on S
    assert r.rejections == (("no_bar", 1),)
    assert r.costs_usd == sum((f.cost_usd for f in r.fills), Decimal(0))
    assert r.dividends_usd == 0


def test_dividends_routed_from_dividend_map(steps):
    divs = {
        "AAA": {D("2025-02-24"): Decimal("0.75"), D("2025-02-27"): Decimal("0.25")},  # 02-24: not held at night
        "BBB": {D("2025-02-27"): Decimal("1")},                                     # never held
        "ZZZ": {D("2025-02-26"): Decimal("2")},                                     # not in the market
    }
    r = run_book(wiring_market(), Scripted((("AAA", "0.5"),)), None, DAILY_SWITCH, W_START, D("2025-03-03"),
                 dividends=divs)
    for c in steps:
        assert c.dividends == ({"AAA": Decimal("0.25")} if c.session == D("2025-02-27") else {}), c.session
    shares = _held_shares(r, "AAA", D("2025-02-27"))
    assert shares > 0
    assert r.dividends_usd == q(shares * Decimal("0.25"))


def test_dividends_off_routes_nothing(steps):
    no_divs = replace(DAILY_SWITCH, id="daily-switch-nodiv", dividends=False)
    divs = {"AAA": {D("2025-02-27"): Decimal("0.25")}}
    r = run_book(wiring_market(), Scripted((("AAA", "0.5"),)), None, no_divs, W_START, D("2025-03-03"),
                 dividends=divs)
    assert all(c.dividends == {} for c in steps)
    assert r.dividends_usd == 0


def test_forced_close_when_bars_end(steps):
    # AAA's last bar is 03-05; it is held (and still targeted) on 03-06, so it is force-closed at
    # its 03-05 close right after 03-06's step, and 03-06's snapshot is replaced.
    market = wiring_market(aaa_until=D("2025-03-05"))
    end = D("2025-03-06")
    r = run_book(market, Scripted((("AAA", "0.3"), ("BBB", "0.3"))), None, DAILY_SWITCH_TBILL, W_START, end)
    assert [t.symbol for t in steps[-1].targets] == ["AAA", "BBB", "BIL"]
    assert "AAA" not in steps[-1].bar_symbols
    forced = [t for t in r.trades if t.exit_reason == "forced"]
    assert len(forced) == 1
    aaa = forced[0]
    mark = market.bar("AAA", D("2025-03-05")).close
    assert (aaa.symbol, aaa.exit_date, aaa.exit_price, aaa.idle) == ("AAA", end, mark, False)
    sells = [f for f in r.fills if f.symbol == "AAA" and f.side == "sell"]
    assert [(f.session_date, f.price, f.reason) for f in sells] == [(end, mark, "forced")]
    assert sorted(p.symbol for p in r.open_at_end) == ["BBB", "BIL"]
    last = r.snapshots[-1]
    assert last.date == end
    held_value = sum((p.shares * p.mark for p in r.open_at_end), Decimal(0))
    assert last.equity_usd == q(last.cash_usd + held_value)
    bbb = next(p for p in r.open_at_end if p.symbol == "BBB")
    assert last.invested_usd == q(bbb.shares * bbb.mark)  # BIL is idle: excluded


def test_run_book_is_deterministic():
    divs = {"AAA": {D("2025-02-27"): Decimal("0.25")}, "BIL": {D("2025-03-03"): Decimal("0.1")}}
    spec = (("AAA", "0.4"), ("BBB", "0.3"))
    one = run_book(wiring_market(), Scripted(spec), None, DAILY_SWITCH_TBILL, W_START, W_END, dividends=divs)
    two = run_book(wiring_market(), Scripted(spec), None, DAILY_SWITCH_TBILL, W_START, W_END, dividends=divs)
    assert one == two


# =========================================================================== 4. run_stats


def _snap(d: str, cash: str, equity: str) -> Snapshot:
    return Snapshot(D(d), P(cash), P(equity))


def hand_run_result() -> RunResult:
    """50 AAA bought at 10 on 2024-12-31 (cash 500.5, fee 0.5), marked 10.5; sold at TP 12 on
    2025-01-02 (proceeds 599.4, fee 0.6, pnl 98.9); flat on 2025-01-03."""
    filled = opened("AAA", "2024-12-31", "10", "12", "9", 50, 1)
    closed = replace(
        filled, status="closed", days_held=2, exit_date=D("2025-01-02"), exit_price=P("12"),
        exit_reason="tp", pnl_usd=P("98.9"),
    )
    return RunResult(
        strategy_id="HAND",
        params=None,
        start=D("2024-12-31"),
        end=D("2025-01-03"),
        usd_idr=Decimal("16000"),
        initial_cash=P("1000"),
        snapshots=(
            _snap("2024-12-30", "1000", "1000"),
            _snap("2024-12-31", "499.5", "1024.5"),
            _snap("2025-01-02", "1098.9", "1098.9"),
            _snap("2025-01-03", "1098.9", "1098.9"),
        ),
        events=(
            Event(D("2024-12-31"), "fill", filled, cash_usd=P("-500.5")),
            Event(D("2025-01-02"), "exit", closed, cash_usd=P("599.4")),
        ),
        closed=(closed,),
        open_at_end=(),
        rejections=(),
    )


def hand_book_result() -> BookResult:
    """2024-12-31: buy 40 AAA at 10 (400.4, fee 0.4) and 5 BIL (idle) at 100 (500.5, fee 0.5);
    marks AAA 11, BIL 100 -> cash 99.1, invested 440, equity 1039.1.
    2025-01-02: AAA dividend 0.5 x 40 = 20; AAA signal-sold at 12 (479.52, fee 0.48): episode
    pnl 479.52 + 20 - 400.4 = 99.12 -> cash 598.62, equity 1098.62.
    2025-01-03: BIL sold at 90 (449.55, fee 0.45): idle episode pnl -50.95 -> cash = equity 1048.17."""
    d0, d1, d2, d3 = D("2024-12-30"), D("2024-12-31"), D("2025-01-02"), D("2025-01-03")
    fills = (
        Fill(session_date=d1, symbol="AAA", side="buy", shares=Decimal("40"), price=P("10"),
             cash_usd=P("-400.4"), cost_usd=P("0.4"), reason="entry"),
        Fill(session_date=d1, symbol="BIL", side="buy", shares=Decimal("5"), price=P("100"),
             cash_usd=P("-500.5"), cost_usd=P("0.5"), reason="entry"),
        Fill(session_date=d2, symbol="AAA", side="sell", shares=Decimal("40"), price=P("12"),
             cash_usd=P("479.52"), cost_usd=P("0.48"), reason="signal"),
        Fill(session_date=d3, symbol="BIL", side="sell", shares=Decimal("5"), price=P("90"),
             cash_usd=P("449.55"), cost_usd=P("0.45"), reason="signal"),
    )
    trades = (
        Trade(symbol="AAA", entry_date=d1, exit_date=d2, entry_price=P("10"), exit_price=P("12"), days_held=1,
              cost_usd=P("400.4"), income_usd=P("499.52"), pnl_usd=P("99.12"), exit_reason="signal", idle=False),
        Trade(symbol="BIL", entry_date=d1, exit_date=d3, entry_price=P("100"), exit_price=P("90"), days_held=2,
              cost_usd=P("500.5"), income_usd=P("449.55"), pnl_usd=P("-50.95"), exit_reason="signal", idle=True),
    )
    return BookResult(
        allocator_id="SCRIPTED",
        params=None,
        rules=DAILY_SWITCH_TBILL,
        start=d1,
        end=d3,
        usd_idr=Decimal("16000"),
        initial_cash=P("1000"),
        snapshots=(
            BookSnapshot(d0, P("1000"), P("1000"), P("0")),
            BookSnapshot(d1, P("99.1"), P("1039.1"), P("440")),
            BookSnapshot(d2, P("598.62"), P("1098.62"), P("0")),
            BookSnapshot(d3, P("1048.17"), P("1048.17"), P("0")),
        ),
        fills=fills,
        trades=trades,
        open_at_end=(),
        dividends_usd=P("20"),
        costs_usd=P("1.83"),
        rejections=(),
    )


def _hand_sharpe(rets: list[float]) -> float:
    m = (rets[0] + rets[1] + rets[2]) / 3
    var = ((rets[0] - m) ** 2 + (rets[1] - m) ** 2 + (rets[2] - m) ** 2) / 3
    return m / math.sqrt(var) * math.sqrt(252)


def test_run_stats_run_result_hand_checked():
    r = hand_run_result()
    s = run_stats(r)
    assert s.metrics == run_metrics(r)
    assert s.exposure == pytest.approx((525.0 / 1024.5 + 0.0 + 0.0) / 3)              # (equity - cash) / equity
    assert s.turnover == pytest.approx(1100.0 / ((1024.5 + 1098.9 + 1098.9) / 3) / (4 / 365.25))  # 500 + 600
    assert s.costs_usd == pytest.approx(1.1)
    assert s.gross_pnl_usd == pytest.approx(100.0)                                    # 98.9 + 0.5 + 0.6
    assert s.cost_drag == pytest.approx(0.011)
    assert s.dividends_usd == 0.0
    rets = [1024.5 / 1000.0 - 1.0, 1098.9 / 1024.5 - 1.0, 0.0]
    assert list(s.daily_returns) == pytest.approx(rets)
    assert s.sharpe == pytest.approx(_hand_sharpe(rets))
    assert [y for y, _ in s.year_returns] == [2024, 2025]
    assert [v for _, v in s.year_returns] == pytest.approx([0.0245, 1098.9 / 1024.5 - 1.0])
    assert s.worst_year[0] == 2024 and s.worst_year[1] == pytest.approx(0.0245)


def test_run_stats_book_result_hand_checked():
    r = hand_book_result()
    s = run_stats(r)
    snaps = [(D("2024-12-30"), 1000.0), (D("2024-12-31"), 1039.1), (D("2025-01-02"), 1098.62), (D("2025-01-03"), 1048.17)]
    assert s.metrics == replace(
        strategy_metrics(snaps, [99.12]),                                             # the idle BIL episode is not a trade
        avg_days_held=1.0,
        exit_reasons=(("tp", 0), ("sl", 0), ("time", 0), ("gap", 0), ("signal", 1), ("forced", 0)),
    )
    assert s.exposure == pytest.approx((440.0 / 1039.1 + 0.0 + 0.0) / 3)               # BIL excluded
    assert s.turnover == pytest.approx(1830.0 / ((1039.1 + 1098.62 + 1048.17) / 3) / (4 / 365.25))  # idle fills count
    assert s.costs_usd == pytest.approx(1.83)
    assert s.gross_pnl_usd == pytest.approx(100.0)                                    # 99.12 + 0.4 + 0.48
    assert s.cost_drag == pytest.approx(0.0088)
    assert s.dividends_usd == pytest.approx(20.0)
    rets = [1039.1 / 1000.0 - 1.0, 1098.62 / 1039.1 - 1.0, 1048.17 / 1098.62 - 1.0]
    assert list(s.daily_returns) == pytest.approx(rets)
    assert s.sharpe == pytest.approx(_hand_sharpe(rets))
    assert [y for y, _ in s.year_returns] == [2024, 2025]
    assert [v for _, v in s.year_returns] == pytest.approx([0.0391, 1048.17 / 1039.1 - 1.0])
    assert s.worst_year[0] == 2025 and s.worst_year[1] == pytest.approx(1048.17 / 1039.1 - 1.0)


def test_run_stats_degenerate_curves():
    flat = RunResult(
        strategy_id="FLAT", params=None, start=D("2025-01-02"), end=D("2025-01-03"), usd_idr=Decimal("16000"),
        initial_cash=P("1000"),
        snapshots=(_snap("2024-12-31", "1000", "1000"), _snap("2025-01-02", "1000", "1000"),
                   _snap("2025-01-03", "1000", "1000")),
        events=(), closed=(), open_at_end=(), rejections=(),
    )
    s = run_stats(flat)
    assert s.daily_returns == (0.0, 0.0)
    assert s.sharpe is None                                                           # zero stdev
    assert (s.exposure, s.turnover, s.costs_usd, s.gross_pnl_usd, s.dividends_usd) == (0.0, 0.0, 0.0, 0.0, 0.0)
    assert s.cost_drag is None                                                        # no gross profit
    assert s.year_returns == ((2025, 0.0),) and s.worst_year == (2025, 0.0)
    assert s.metrics.trades == 0
    one = replace(flat, end=D("2025-01-02"), snapshots=flat.snapshots[:2])
    assert run_stats(one).daily_returns == (0.0,)
    assert run_stats(one).sharpe is None                                              # fewer than 2 returns


def test_run_stats_type_check():
    with pytest.raises(TypeError, match="RunResult or a BookResult"):
        run_stats(object())


# =========================================================================== 3b. the cadence split
#
# MONTHLY_RANK_WEEKLY_RESIZE over the wiring window (02-24 .. 03-14): the only month start is
# 03-03, the week starts are 02-24, 03-03 and 03-10. So 03-03 ranks, 03-10 re-scales, and 02-24
# is a week start with no basket behind it yet.

M_RANK_W_RESIZE = MONTHLY_RANK_WEEKLY_RESIZE
M_RANK_D_RESIZE = replace(MONTHLY_HOLD, id="monthly-rank-daily-resize", resize_cadence="daily")


def test_split_cadence_ranks_monthly_and_rescales_weekly(steps):
    alloc = Scripted((("AAA", "0.5"),))
    run_book(wiring_market(), alloc, None, M_RANK_W_RESIZE, W_START, W_END)
    # 02-24 is a week start, but nothing has ranked yet: not a decision, the allocator is not called.
    assert [c.data_date for c in alloc.calls] == [D("2025-02-28"), D("2025-03-07")]
    assert [c.session for c in steps if c.targets is not None] == [D("2025-03-03"), D("2025-03-10")]
    assert [c.session for c in steps] == dates.sessions(W_START, W_END)


def test_a_resize_session_keeps_the_last_rank_basket_at_todays_exposure(steps):
    market = wiring_market()
    alloc = Scripted(table={
        D("2025-02-28"): (("AAA", "0.4"), ("BBB", "0.4")),  # the rank, total 0.8
        D("2025-03-07"): (("CCC", "0.2"),),                 # a different basket, total 0.2
    })
    run_book(market, alloc, None, M_RANK_W_RESIZE, W_START, W_END)
    ranked, resized = (c for c in steps if c.targets is not None)
    assert ranked.session == D("2025-03-03")
    assert [(t.symbol, t.weight) for t in ranked.targets] == [("AAA", Decimal("0.4")), ("BBB", Decimal("0.4"))]
    # CCC is NOT ranked in; AAA and BBB are kept and scaled by k = 0.2 / 0.8.
    assert resized.session == D("2025-03-10")
    assert [(t.symbol, t.weight) for t in resized.targets] == [("AAA", Decimal("0.1")), ("BBB", Decimal("0.1"))]
    # Σ after the re-scale is exactly what the allocator wants today, and `last` is today's close.
    assert sum(t.weight for t in resized.targets) == Decimal("0.2")
    for t in resized.targets:
        assert t.last == q(market.bar(t.symbol, D("2025-03-07")).close)
        assert (t.limit, t.stop, t.take) == (None, None, None)


def test_a_resize_session_moves_the_idle_weight_but_never_the_names(steps):
    alloc = Scripted(table={
        D("2025-02-28"): (("AAA", "0.4"), ("BBB", "0.4")),
        D("2025-03-07"): (("AAA", "0.2"), ("BBB", "0.2")),  # the same basket at half the exposure
    })
    r = run_book(wiring_market(), alloc, None,
                 replace(M_RANK_W_RESIZE, id="x", idle_symbol="BIL"), W_START, W_END)
    ranked, resized = (c for c in steps if c.targets is not None)
    assert [(t.symbol, t.weight) for t in ranked.targets] == [
        ("AAA", Decimal("0.4")), ("BBB", Decimal("0.4")), ("BIL", Decimal("0.2"))
    ]
    # Exposure halves; the freed weight goes to BIL, which is the point of the split.
    assert [(t.symbol, t.weight) for t in resized.targets] == [
        ("AAA", Decimal("0.2")), ("BBB", Decimal("0.2")), ("BIL", Decimal("0.6"))
    ]
    assert {f.symbol for f in r.fills if f.session_date == D("2025-03-10") and f.side == "buy"} == {"BIL"}


def test_a_resize_session_to_zero_exposure_leaves_the_book(steps):
    alloc = Scripted(table={D("2025-02-28"): (("AAA", "0.5"),)})  # every later date wants nothing
    r = run_book(wiring_market(), alloc, None, M_RANK_W_RESIZE, W_START, W_END)
    resized = [c for c in steps if c.targets is not None][1]
    assert resized.targets == ()  # k = 0: an exposure cut to nothing is a re-scale, not a re-rank
    assert [(f.symbol, f.reason) for f in r.fills if f.session_date == D("2025-03-10")] == [("AAA", "signal")]


def test_a_split_rule_set_with_no_rank_yet_never_decides(steps):
    # Daily re-scaling under a monthly rank: still nothing before 03-03, then every session.
    alloc = Scripted((("AAA", "0.5"),))
    run_book(wiring_market(), alloc, None, M_RANK_D_RESIZE, W_START, W_END)
    after_first_rank = [s for s in dates.sessions(W_START, W_END) if s >= D("2025-03-03")]
    assert [c.session for c in steps if c.targets is not None] == after_first_rank
    assert [c.data_date for c in alloc.calls] == [dates.prev_session(s) for s in after_first_rank]


def test_an_unsplit_rule_set_runs_exactly_as_before():
    market = wiring_market()
    spec = (("AAA", "0.4"), ("BBB", "0.4"))
    before = run_book(market, Scripted(spec), None, MONTHLY_HOLD, W_START, W_END)
    # The split lever at its default must not perturb the engine at all.
    assert before == replace(run_book(market, Scripted(spec), None, MONTHLY_HOLD, W_START, W_END), rules=MONTHLY_HOLD)
    assert before.rules.resize_cadence is None


# --------------------------------------------------------------------------- _rescaled, directly

RANK = (
    Target(symbol="AAA", weight=Decimal("0.4"), last=P("12"), limit=P("12.1"), stop=P("11"), take=P("13")),
    Target(symbol="BBB", weight=Decimal("0.4"), last=P("24")),
)
FRESH_HALF = (Target(symbol="CCC", weight=Decimal("0.4"), last=P("30")),)


def test_rescaled_keeps_only_what_is_still_held():
    market = wiring_market()
    out = book_runner._rescaled(market, RANK, FRESH_HALF, frozenset({"BBB"}), D("2025-03-07"), {})
    assert [(t.symbol, t.weight) for t in out] == [("BBB", Decimal("0.2"))]
    assert book_runner._rescaled(market, RANK, FRESH_HALF, frozenset(), D("2025-03-07"), {}) == ()
    assert book_runner._rescaled(market, (), FRESH_HALF, frozenset({"AAA"}), D("2025-03-07"), {}) == ()


def test_rescaled_drops_the_entry_prices_and_refreshes_last():
    market = wiring_market()
    day = D("2025-03-07")
    out = book_runner._rescaled(market, RANK, RANK, frozenset({"AAA", "BBB"}), day, {})
    assert [(t.symbol, t.weight) for t in out] == [("AAA", Decimal("0.4")), ("BBB", Decimal("0.4"))]  # k = 1
    for t in out:
        assert (t.limit, t.stop, t.take) == (None, None, None)
        assert t.last == q(market.bar(t.symbol, day).close)


def test_rescaled_falls_back_to_the_books_mark_when_a_symbol_has_no_bar_that_day():
    market = wiring_market(ccc_missing=(D("2025-03-07"),))
    rank = (Target(symbol="CCC", weight=Decimal("0.5"), last=P("30")),)
    fresh = (Target(symbol="CCC", weight=Decimal("0.5"), last=P("30")),)
    held, day = frozenset({"CCC"}), D("2025-03-07")
    assert book_runner._rescaled(market, rank, fresh, held, day, {"CCC": P("29.5")})[0].last == P("29.5")
    assert book_runner._rescaled(market, rank, fresh, held, day, {})[0].last == P("30")  # the stale last


def test_rescaled_never_weighs_more_than_the_allocator_wants():
    market, day = wiring_market(), D("2025-03-07")
    for fresh_total in ("0.1", "0.4", "0.8", "1"):
        fresh = (Target(symbol="CCC", weight=Decimal(fresh_total), last=P("30")),)
        out = book_runner._rescaled(market, RANK, fresh, frozenset({"AAA", "BBB"}), day, {})
        assert sum(t.weight for t in out) == Decimal(fresh_total)
    # A basket only half still held keeps half the exposure: nothing is re-entered to make it up.
    out = book_runner._rescaled(market, RANK, (Target(symbol="CCC", weight=Decimal("0.8"), last=P("30")),),
                                frozenset({"AAA"}), day, {})
    assert sum(t.weight for t in out) == Decimal("0.4")
