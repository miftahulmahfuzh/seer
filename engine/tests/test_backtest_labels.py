"""The vectorized bracket labeler (handover §6.1 "Labels", plan phase 3, requirement R1).

Two halves:

- hand-built bars for every label path, each checked against numbers worked out from design §5
  (``sim.step`` + the runner's forced close) and netted at 0.1% per side;
- sim parity: on a seeded synthetic market, every row's label agrees with ``run_backtest``
  trading that one order alone through a one-pick fake strategy.

Sessions used by the hand-built cases (March 2025, no holidays): data_date 03-03, then
S1 = 03-04, S2 = 03-05, S3 = 03-06, S4 = 03-07, S5 = 03-10, S6 = 03-11, S7 = 03-12,
S8 = 03-13, S9 = 03-14. The bracket is limit 10, tp 11, sl 9 unless a case says otherwise.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Set as AbstractSet
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
import pytest
from stratkit import mutate_from

from seer_engine import dates
from seer_engine.backtest import labels as labels_mod
from seer_engine.backtest.labels import COST, REASONS, Labels, label_orders
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.runner import run_backtest
from seer_engine.prices import to_decimal
from seer_engine.sim import COST_RATE, Pick, buy_cost
from seer_engine.strategies.base import History

D0 = date(2025, 3, 3)  # data_date
S = [date(2025, 3, d) for d in (4, 5, 6, 7, 10, 11, 12, 13, 14)]  # S[0] = S1 ... S[8] = S9
END = S[-1]

FLAT = (10.5, 10.8, 10.2, 10.5)  # a bar that neither fills (low > 10) nor exits a 10/11/9 bracket
HOLD = (10.2, 10.8, 9.5, 10.5)  # inside the bracket once filled: low > 9, high < 11


def net(fill: float, exit_: float) -> float:
    return exit_ * (1 - 0.001) / (fill * (1 + 0.001)) - 1


def history(symbol: str, bars: Mapping[date, tuple[float, float, float, float]]) -> History:
    days = sorted(bars)
    rows = [bars[d] for d in days]
    return History(
        symbol,
        np.array(days, dtype="datetime64[D]"),
        np.array([r[0] for r in rows], dtype=np.float64),
        np.array([r[1] for r in rows], dtype=np.float64),
        np.array([r[2] for r in rows], dtype=np.float64),
        np.array([r[3] for r in rows], dtype=np.float64),
        np.full(len(rows), 1_000_000.0),
    )


def one(
    bars: Mapping[date, tuple[float, float, float, float]],
    *,
    limit: float = 10.0,
    tp: float = 11.0,
    sl: float = 9.0,
    data_date: date = D0,
    end: date = END,
) -> tuple[str, date | None, float, float, float]:
    """(reason name or "unresolved", resolved date, label, fill, exit) of one order on symbol X."""
    out = label_orders(
        {"X": history("X", bars)},
        ["X"],
        np.array([data_date], dtype="datetime64[D]"),
        np.array([limit]),
        np.array([tp]),
        np.array([sl]),
        end,
    )
    code = int(out.reason[0])
    when = None if np.isnat(out.resolved[0]) else out.resolved[0].item()
    name = "unresolved" if code < 0 else REASONS[code]
    return name, when, float(out.label[0]), float(out.fill[0]), float(out.exit[0])


def filled_on_s1(**later: tuple[float, float, float, float]) -> dict[date, tuple[float, float, float, float]]:
    """D0 flat, S1 fills at the limit 10 (open 10.2, low 9.8, no exit check), then HOLD bars on
    every later session unless ``later`` names it: keys "s2".."s9" set a bar, value None drops it."""
    bars: dict[date, tuple[float, float, float, float]] = {D0: FLAT, S[0]: (10.2, 10.6, 9.8, 10.3)}
    for i in range(1, 9):
        bars[S[i]] = HOLD
    for key, value in later.items():
        d = S[int(key[1:]) - 1]
        if value is None:
            del bars[d]
        else:
            bars[d] = value
    return bars


# --------------------------------------------------------------------------- constants


def test_cost_and_reasons_match_the_simulator():
    assert COST == float(COST_RATE)
    assert REASONS == ("expire", "tp", "sl", "gap", "time", "forced")


def test_the_purity_glob_covers_the_labeler():
    from test_strategy_purity import _module_name, _pure_sources

    assert "seer_engine.backtest.labels" in {_module_name(p) for p in _pure_sources()}
    assert labels_mod.TIME_STOP_DAYS == 5


# --------------------------------------------------------------------------- no fill


def test_no_bar_on_the_order_session_expires():
    name, when, lab, fill, ex = one({D0: FLAT, S[1]: (9.0, 9.5, 8.0, 9.2)})
    assert (name, when, lab) == ("expire", S[0], 0.0)
    assert math.isnan(fill) and math.isnan(ex)


def test_low_at_the_limit_does_not_fill():
    name, when, lab, fill, _ = one({D0: FLAT, S[0]: (10.5, 10.8, 10.0, 10.4)})  # low == limit: strict
    assert (name, when, lab) == ("expire", S[0], 0.0)
    assert math.isnan(fill)


def test_a_symbol_without_history_expires():
    out = label_orders(
        {},
        ["GONE"],
        np.array([D0], dtype="datetime64[D]"),
        np.array([10.0]),
        np.array([11.0]),
        np.array([9.0]),
        END,
    )
    assert REASONS[int(out.reason[0])] == "expire"
    assert out.resolved[0].item() == S[0]
    assert out.label[0] == 0.0


# --------------------------------------------------------------------------- fills


def test_fill_at_the_limit_when_the_open_is_above_it():
    name, when, lab, fill, ex = one(filled_on_s1(s2=(10.4, 11.5, 10.1, 11.2)))
    assert fill == 10.0
    assert (name, when, ex) == ("tp", S[1], 11.0)
    assert lab == net(10.0, 11.0)


def test_fill_at_the_open_when_the_open_is_below_the_limit():
    bars = filled_on_s1(s2=(10.4, 11.5, 10.1, 11.2))
    bars[S[0]] = (9.9, 10.2, 9.6, 10.0)
    name, when, lab, fill, ex = one(bars)
    assert fill == 9.9
    assert (name, when, ex) == ("tp", S[1], 11.0)
    assert lab == net(9.9, 11.0)


def test_no_exit_check_on_the_fill_session():
    bars = filled_on_s1(s2=(10.4, 11.5, 10.1, 11.2))
    bars[S[0]] = (10.2, 12.0, 8.5, 10.0)  # crosses both tp and sl on S1: ignored
    name, when, _, fill, ex = one(bars)
    assert fill == 10.0
    assert (name, when, ex) == ("tp", S[1], 11.0)


# --------------------------------------------------------------------------- exits


def test_take_profit_intraday():
    name, when, lab, _, ex = one(filled_on_s1(s3=(10.5, 11.3, 10.1, 11.0)))
    assert (name, when, ex) == ("tp", S[2], 11.0)
    assert lab == pytest.approx(0.0978021978021978, abs=1e-15)


def test_high_equal_to_tp_does_not_exit_but_low_equal_to_sl_does():
    hold = one(filled_on_s1(s2=(10.5, 11.0, 10.1, 10.9), s3=(10.5, 10.9, 9.0, 9.5)))
    assert hold[:2] == ("sl", S[2])  # high == tp on S2 is no exit (strict >); low == sl on S3 is
    assert hold[4] == 9.0


def test_stop_loss_intraday():
    name, when, lab, _, ex = one(filled_on_s1(s2=(10.0, 10.4, 8.8, 9.1)))
    assert (name, when, ex) == ("sl", S[1], 9.0)
    assert lab == pytest.approx(9.0 * 0.999 / (10.0 * 1.001) - 1, abs=1e-15)
    assert lab == pytest.approx(-0.1017982, abs=1e-7)


def test_both_in_range_takes_the_stop_first():
    name, when, _, _, ex = one(filled_on_s1(s2=(10.0, 11.5, 8.8, 10.0)))
    assert (name, when, ex) == ("sl", S[1], 9.0)


def test_gap_through_the_stop_exits_at_the_open():
    name, when, lab, _, ex = one(filled_on_s1(s2=(8.5, 8.9, 8.2, 8.6)))
    assert (name, when, ex) == ("gap", S[1], 8.5)
    assert lab == net(10.0, 8.5)


def test_open_at_the_stop_is_a_gap():
    name, when, _, _, ex = one(filled_on_s1(s2=(9.0, 9.4, 8.9, 9.2)))
    assert (name, when, ex) == ("gap", S[1], 9.0)


def test_gap_through_the_target_exits_at_the_open():
    name, when, lab, _, ex = one(filled_on_s1(s2=(11.3, 11.6, 11.1, 11.4)))
    assert (name, when, ex) == ("tp", S[1], 11.3)
    assert lab == net(10.0, 11.3)


def test_time_stop_on_day_five_exits_at_the_open_of_s6():
    name, when, lab, _, ex = one(filled_on_s1())
    assert (name, when, ex) == ("time", S[5], 10.2)
    assert lab == net(10.0, 10.2)


def test_time_stop_beats_a_gap_and_a_target_on_the_same_bar():
    name, when, _, _, ex = one(filled_on_s1(s6=(8.0, 12.0, 7.5, 8.5)))
    assert (name, when, ex) == ("time", S[5], 8.0)


def test_a_missing_bar_still_counts_toward_the_time_stop():
    name, when, _, _, ex = one(filled_on_s1(s3=None))  # no bar on S3: days_held still grows
    assert (name, when, ex) == ("time", S[5], 10.2)


def test_time_stop_is_delayed_by_a_missing_bar_on_s6():
    name, when, _, _, ex = one(filled_on_s1(s6=None, s7=(10.3, 10.8, 9.5, 10.5)))
    assert (name, when, ex) == ("time", S[6], 10.3)


def test_forced_close_after_the_last_bar():
    bars = filled_on_s1()
    for i in range(3, 9):  # last bar on S3 (03-06)
        del bars[S[i]]
    bars[S[2]] = (10.2, 10.8, 9.5, 10.4)
    name, when, lab, _, ex = one(bars)
    assert (name, when, ex) == ("forced", S[3], 10.4)  # the session after the last bar, at its close
    assert lab == net(10.0, 10.4)


def test_a_halt_that_resumes_is_not_a_forced_close():
    bars = filled_on_s1(s3=None, s4=None, s5=None)  # bars resume on S6
    name, when, _, _, ex = one(bars)
    assert (name, when, ex) == ("time", S[5], 10.2)


def test_still_open_at_the_end_is_unresolved():
    name, when, lab, fill, ex = one(filled_on_s1(), end=S[3])
    assert (name, when) == ("unresolved", None)
    assert fill == 10.0
    assert math.isnan(lab) and math.isnan(ex)


def test_order_session_after_the_end_is_unresolved():
    name, when, lab, fill, _ = one(filled_on_s1(), data_date=S[3], end=S[3])
    assert (name, when) == ("unresolved", None)
    assert math.isnan(lab) and math.isnan(fill)


def test_bars_after_the_end_are_never_read():
    bars = filled_on_s1()
    for i in range(3, 9):
        del bars[S[i]]
    bars[S[7]] = (20.0, 21.0, 19.0, 20.0)  # a later bar exists, but after end
    name, when, _, _, ex = one(bars, end=S[6])
    assert (name, when, ex) == ("forced", S[3], 10.5)  # the last bar <= end is S3 (HOLD close 10.5)
    assert one(bars, end=S[2])[:2] == ("unresolved", None)


# --------------------------------------------------------------------------- shape and validation


def test_rows_are_independent_and_keep_input_order():
    bars_x = filled_on_s1(s2=(10.4, 11.5, 10.1, 11.2))
    bars_y = filled_on_s1(s2=(10.0, 10.4, 8.8, 9.1))
    h = {"X": history("X", bars_x), "Y": history("Y", bars_y)}
    out = label_orders(
        h,
        ["Y", "X", "Y"],
        np.array([D0, D0, S[3]], dtype="datetime64[D]"),
        np.array([10.0, 10.0, 9.4]),  # row 3: S1 = S5, a HOLD bar whose low 9.5 >= 9.4
        np.array([11.0, 11.0, 11.0]),
        np.array([9.0, 9.0, 8.0]),
        END,
    )
    assert [REASONS[int(r)] for r in out.reason] == ["sl", "tp", "expire"]
    assert out.resolved.tolist() == [S[1], S[1], S[4]]
    assert out.reason.dtype == np.int8 and out.resolved.dtype == np.dtype("datetime64[D]")
    for arr in (out.label, out.resolved, out.reason, out.fill, out.exit):
        assert arr.shape == (3,) and not arr.flags.writeable


def test_empty_input_gives_empty_labels():
    out = label_orders(
        {}, [], np.array([], dtype="datetime64[D]"), np.array([]), np.array([]), np.array([]), END
    )
    assert isinstance(out, Labels)
    assert [a.shape for a in (out.label, out.resolved, out.reason, out.fill, out.exit)] == [(0,)] * 5


def test_malformed_input_is_rejected():
    h = {"X": history("X", filled_on_s1())}
    d = np.array([D0], dtype="datetime64[D]")
    good = (np.array([10.0]), np.array([11.0]), np.array([9.0]))
    with pytest.raises(TypeError):
        label_orders(h, ["X"], d, *good, END.isoformat())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        label_orders(h, ["X"], np.array(["2025-03-03"], dtype="datetime64[s]"), *good, END)
    with pytest.raises(ValueError):
        label_orders(h, ["X", "X"], d, *good, END)
    with pytest.raises(ValueError):
        label_orders(h, ["X"], np.array(["NaT"], dtype="datetime64[D]"), *good, END)
    with pytest.raises(TypeError):
        label_orders(h, ["X"], d, np.array([10], dtype=np.int64), good[1], good[2], END)
    with pytest.raises(ValueError):
        label_orders(h, ["X"], d, np.array([np.nan]), good[1], good[2], END)
    with pytest.raises(ValueError):
        label_orders(h, ["X"], d, np.array([10.0]), np.array([11.0]), np.array([10.0]), END)  # sl == limit
    with pytest.raises(ValueError):
        label_orders(h, ["X"], d, np.array([10.0]), np.array([10.0]), np.array([9.0]), END)  # tp == limit


# --------------------------------------------------------------------------- sim parity

PARITY_SEED = 20261003
PARITY_DAYS = dates.sessions(date(2024, 1, 2), date(2024, 6, 28))
PARITY_SYMBOLS = tuple(f"S{i:02d}" for i in range(40))
RUN_SESSIONS = 14  # each sim run covers S1 and the next 13 sessions; later resolutions are skipped


def _ticks(x: np.ndarray) -> np.ndarray:
    """Prices as exact 4-dp floats (integer ten-thousandths / 1e4: the float's repr is the 4-dp value)."""
    return np.maximum(np.round(x * 10_000.0), 10_000.0) / 10_000.0


def _parity_market(seed: int = PARITY_SEED) -> Market:
    rng = np.random.default_rng(seed)
    n = len(PARITY_DAYS)
    hist: dict[str, History] = {}
    for i, s in enumerate(PARITY_SYMBOLS):
        gap = np.where(rng.random(n) < 0.06, rng.normal(0.0, 0.06, n), 0.0)
        body = rng.normal(0.0, 0.025, n)
        close = np.empty(n)
        open_ = np.empty(n)
        prev = rng.uniform(20.0, 80.0)
        for t in range(n):
            open_[t] = prev * (1.0 + gap[t])
            close[t] = open_[t] * (1.0 + body[t])
            prev = close[t]
        high = np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0.0, 0.012, n)))
        low = np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0.0, 0.012, n)))
        keep = rng.random(n) > 0.05  # scattered missing bars
        if i % 4 == 0:  # a quarter of the symbols stop trading before the data end
            keep[int(rng.integers(n // 3, n - 5)):] = False
        if i % 7 == 3:  # a few start late
            keep[: int(rng.integers(5, 30))] = False
        days = np.array(PARITY_DAYS, dtype="datetime64[D]")[keep]
        o, h, lo, c = _ticks(open_[keep]), _ticks(high[keep]), _ticks(low[keep]), _ticks(close[keep])
        h = np.maximum(h, np.maximum(o, c))
        lo = np.minimum(lo, np.minimum(o, c))
        hist[s] = History(s, days, o, h, lo, c, np.full(days.shape[0], 1_000_000.0))
    return Market(history=hist, membership=Membership(()), fx=((date(2023, 12, 1), Decimal("16000")),))


def _parity_rows(market: Market, seed: int = PARITY_SEED) -> list[tuple[str, date, Pick]]:
    """One row per (symbol, bar date) except the data end: a 4-dp bracket off that close."""
    rng = np.random.default_rng(seed + 1)
    rows: list[tuple[str, date, Pick]] = []
    for s in PARITY_SYMBOLS:
        h = market.history[s]
        for d, c in zip(h.dates.tolist(), h.close.tolist()):
            if d >= PARITY_DAYS[-1]:
                continue
            atr = c * float(rng.uniform(0.01, 0.06))
            last = to_decimal(c)
            lim = to_decimal(c - 0.5 * atr)
            rows.append((s, d, Pick(s, last, lim, to_decimal(float(lim) + atr), to_decimal(float(lim) - 1.5 * atr))))
    return rows


class OnePick:
    """A fake ``Strategy`` that places one pick for one data_date and nothing else."""

    id = "ONE"
    lookback = 1

    def __init__(self, data_date: date, pick: Pick):
        self.data_date = data_date
        self.pick = pick

    def picks(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
              params: Any) -> list[Pick]:
        return [self.pick] if data_date == self.data_date else []

    def prepare(self, history: Mapping[str, History]) -> Any:
        return ()

    def picks_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                       params: Any) -> list[Pick]:
        return [self.pick] if data_date == self.data_date else []


def _label_rows(market: Market, rows: list[tuple[str, date, Pick]]) -> Labels:
    return label_orders(
        market.history,
        [s for s, _, _ in rows],
        np.array([d for _, d, _ in rows], dtype="datetime64[D]"),
        np.array([float(p.limit_price) for _, _, p in rows]),
        np.array([float(p.tp_price) for _, _, p in rows]),
        np.array([float(p.sl_price) for _, _, p in rows]),
        PARITY_DAYS[-1],
    )


def test_sim_parity_on_a_seeded_market():
    market = _parity_market()
    rows = _parity_rows(market)
    assert len(rows) >= 3000
    out = _label_rows(market, rows)
    data_end = PARITY_DAYS[-1]
    seen: set[str] = set()
    compared = 0
    for i, (s, d, p) in enumerate(rows):
        s1 = dates.next_session(d)
        stop = PARITY_DAYS[min(PARITY_DAYS.index(s1) + RUN_SESSIONS - 1, len(PARITY_DAYS) - 1)]
        run = run_backtest(market, OnePick(d, p), None, s1, stop, prepared=())
        assert run.rejections == ()
        code = int(out.reason[i])
        terminal = [e for e in run.events if e.kind in ("expire", "exit")]
        if not terminal:
            # still open after the run window: the labeler resolves it later or never
            assert code == -1 or out.resolved[i].item() > stop, (s, d)
            if stop == data_end:
                assert code == -1, (s, d)
            continue
        compared += 1
        (event,) = terminal
        if event.kind == "expire":
            assert (REASONS[code], out.resolved[i].item(), float(out.label[i])) == ("expire", s1, 0.0), (s, d)
            assert math.isnan(out.fill[i]), (s, d)
            seen.add("expire")
            continue
        order = event.order
        want = "forced" if event.forced else order.exit_reason
        if event.forced:
            assert order.exit_reason == "time", (s, d)
        assert REASONS[code] == want, (s, d, REASONS[code], want)
        assert out.resolved[i].item() == order.exit_date, (s, d)
        assert float(out.fill[i]) == float(order.fill_price), (s, d)
        assert float(out.exit[i]) == float(order.exit_price), (s, d)
        by_price = float(order.exit_price) * (1 - COST) / (float(order.fill_price) * (1 + COST)) - 1
        by_cash = float(order.pnl_usd / buy_cost(order.fill_price, order.shares))
        assert abs(float(out.label[i]) - by_price) <= 1e-12, (s, d)
        assert abs(float(out.label[i]) - by_cash) <= 1e-6, (s, d)
        seen.add(want)
    assert compared >= 3000
    assert seen == set(REASONS)  # the sample exercises every path


def test_vectorized_equals_one_row_at_a_time():
    market = _parity_market()
    rows = _parity_rows(market)[::37]
    together = _label_rows(market, rows)
    for i, row in enumerate(rows):
        alone = _label_rows(market, [row])
        assert alone.reason[0] == together.reason[i]
        assert alone.resolved[0] == together.resolved[i] or (np.isnat(alone.resolved[0]) and np.isnat(together.resolved[i]))
        for name in ("label", "fill", "exit"):
            a, b = getattr(alone, name)[0], getattr(together, name)[i]
            assert a == b or (math.isnan(a) and math.isnan(b)), (row[0], row[1], name)


def test_changing_bars_after_resolution_leaves_the_label_unchanged():
    market = _parity_market()
    rows = _parity_rows(market)
    before = _label_rows(market, rows)
    cut = date(2024, 4, 1)
    mutated = Market(
        history={s: mutate_from(h, cut, lambda x: x * 1.7 + 3.0) for s, h in market.history.items()},
        membership=market.membership,
        fx=market.fx,
    )
    after = _label_rows(mutated, rows)
    early = ~np.isnat(before.resolved) & (before.resolved < np.datetime64(cut, "D"))
    assert int(early.sum()) > 1000
    assert np.array_equal(before.reason[early], after.reason[early])
    assert np.array_equal(before.resolved[early], after.resolved[early])
    for name in ("label", "fill", "exit"):
        b, a = getattr(before, name)[early], getattr(after, name)[early]
        assert np.array_equal(b, a, equal_nan=True), name
    late = ~early & (before.reason >= 0)
    assert not np.array_equal(before.label[late], after.label[late], equal_nan=True)  # the cut does bite later
