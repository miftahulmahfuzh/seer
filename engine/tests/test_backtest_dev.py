"""The P7a dev-window runner (plan phase 9; handover D3, D6-D9, §7.4).

Fake allocators (``HoldOne``) and a fake bracket strategy (``DipPicks``) keep every number here
independent of the strategy families (phases 5-8). Every market ends on or before DEV_END,
except the ones built to prove the D9 guard.
"""

from __future__ import annotations

import ast
import math
from collections.abc import Mapping, Set as AbstractSet
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from stratkit import hist, sawtooth

import seer_engine.backtest.dev as dev_module
from seer_engine import dates
from seer_engine.backtest import tuning
from seer_engine.backtest.tuning import MAX_DRAWDOWN
from seer_engine.backtest.benchmark import Dividend, spy_curves
from seer_engine.backtest.book_runner import BookResult, RunStats, run_stats
from seer_engine.backtest.dev import (
    DEV_END,
    DEV_WINDOW,
    FAILURE_LABELS,
    FX_START,
    MAX_CANDIDATES,
    MEMBERSHIP_START,
    Candidate,
    DevRow,
    DevWindowError,
    candidate_owner_inputs,
    candidate_window,
    check_dev_session,
    deflated_sharpe,
    finalists,
    make_row,
    run_candidate,
    run_registry,
)
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.metrics import Metrics, curve_metrics
from seer_engine.backtest.runner import INITIAL_IDR, RunResult, run_backtest
from seer_engine.backtest.window import Window
from seer_engine.prices import to_decimal
from seer_engine.sim import Pick, initial_cash_usd, q
from seer_engine.sim.book import Target
from seer_engine.sim.rules import DAILY_SWITCH, DAILY_SWITCH_TBILL, DESIGN_V0, MONTHLY_HOLD
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 3)


# --------------------------------------------------------------------------- fakes


class HoldOne:
    """A fake ``Allocator``: weight 1 in ``hold`` whenever it has a bar on data_date.

    ``flip``: only on data dates at an even row of ``hold``'s history (so a daily rule set
    trades in and out). Counts ``prepare`` calls and records which prepared object it was given.
    """

    def __init__(self, id: str, hold: str, *, reads: tuple[str, ...] = (), lookback: int = 5,
                 members: bool = False, flip: bool = False) -> None:
        self.id = id
        self.hold = hold
        self.reads = reads
        self._lookback = lookback
        self.members = members
        self.flip = flip
        self.prepare_calls = 0
        self.prepared_seen: list[int] = []

    def lookback(self, params: Any) -> int:
        return self._lookback

    def symbols(self, params: Any) -> tuple[str, ...]:
        return tuple(sorted({self.hold, *self.reads}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (self.hold,)

    def uses_members(self, params: Any) -> bool:
        return self.members

    def _targets(self, history: Mapping[str, History], data_date: date) -> tuple[Target, ...]:
        h = history.get(self.hold)
        if h is None:
            return ()
        i = h.index_of(data_date)
        if i is None or (self.flip and i % 2 == 1):
            return ()
        return (Target(self.hold, Decimal("1"), q(to_decimal(float(h.close[i])))),)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._targets(history, data_date)

    def prepare(self, history: Mapping[str, History]) -> Any:
        self.prepare_calls += 1
        return {"history": dict(history)}

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        self.prepared_seen.append(id(prepared))
        return self._targets(prepared["history"], data_date)


class DipPicks:
    """A fake bracket ``Strategy``: every member with a bar on data_date, limit 1% under its close."""

    id = "DIPFAKE"
    lookback = 3

    def __init__(self) -> None:
        self.prepare_calls = 0

    def _picks(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date) -> list[Pick]:
        out: list[Pick] = []
        for symbol in sorted(members):
            h = history.get(symbol)
            if h is None:
                continue
            i = h.index_of(data_date)
            if i is None:
                continue
            close = to_decimal(float(h.close[i]))
            out.append(Pick(symbol, close, q(close * Decimal("0.99")), q(close * Decimal("1.02")),
                            q(close * Decimal("0.95"))))
        return out

    def picks(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
              params: Any) -> list[Pick]:
        return self._picks(history, members, data_date)

    def prepare(self, history: Mapping[str, History]) -> Any:
        self.prepare_calls += 1
        return dict(history)

    def picks_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                       params: Any) -> list[Pick]:
        return self._picks(prepared, members, data_date)


SPY_HOLD = HoldOne("FAKE", "SPY")


def cand(id: str, family: str = "F1", *, allocator: Any = None, rules: Any = MONTHLY_HOLD,
         owner_inputs: tuple[str, ...] | None = None) -> Candidate:
    """A candidate whose declared owner inputs are the computed ones unless given."""
    c = Candidate(id=id, family=family, rules=rules, allocator=SPY_HOLD if allocator is None else allocator,
                  params=None, rationale="a test candidate", added=ADDED, owner_inputs=())
    return replace(c, owner_inputs=candidate_owner_inputs(c) if owner_inputs is None else owner_inputs)


# --------------------------------------------------------------------------- markets

W_DAYS = dates.sessions(date(2015, 6, 1), DEV_END)  # 98 sessions, 2015-06-01 .. 2015-10-16
XLK_DAYS = dates.sessions(date(2015, 7, 1), DEV_END)  # "launches" 2015-07-01
DIV_DAY = date(2015, 9, 18)
SPY_DIVS = (Dividend(DIV_DAY, Decimal("1.0335")),)
DIVS = {"SPY": {DIV_DAY: Decimal("1.0335")}}
FX_SHORT = ((date(2015, 1, 2), Decimal("12500")),)


def short_market(*, extra_day: date | None = None, fx: tuple = FX_SHORT) -> Market:
    spy_days = W_DAYS + ([extra_day] if extra_day is not None else [])
    return Market(
        history={
            "AAA": hist("AAA", sawtooth(len(W_DAYS), 50.0, 1.0, 0.9), days=W_DAYS),
            "SPY": hist("SPY", sawtooth(len(spy_days), 200.0, 2.0, 1.5), days=spy_days),
            "XLK": hist("XLK", sawtooth(len(XLK_DAYS), 40.0, 0.5, 0.4), days=XLK_DAYS),
        },
        membership=Membership((("AAA", date(1990, 1, 2), None),)),
        fx=fx,
    )


def long_market() -> Market:
    """SPY from 1998-11-02 (before FX_START) to DEV_END: 4,267 sessions; USD/IDR from FX_START."""
    days = dates.sessions(date(1998, 11, 2), DEV_END)
    return Market(
        history={"SPY": hist("SPY", sawtooth(len(days), 100.0, 1.2, 0.8), days=days)},
        membership=Membership(()),
        fx=((FX_START, Decimal("8002")), (date(2015, 1, 2), Decimal("12500"))),
    )


# --------------------------------------------------------------------------- constants and D9


def test_constants():
    assert DEV_END == date(2015, 10, 16)
    assert dates.is_session(DEV_END) and dates.next_session(DEV_END) == date(2015, 10, 19)
    assert FX_START == date(1999, 1, 4)
    assert MAX_CANDIDATES == 60
    csv = Path(__file__).resolve().parents[1] / "data" / "sp500_history.csv"
    first_row = csv.read_text(encoding="utf-8").splitlines()[1]
    assert MEMBERSHIP_START == date.fromisoformat(first_row.split(",", 1)[0])
    assert FAILURE_LABELS == (
        "beats SPY TR", f"max DD <= {tuning.MAX_DRAWDOWN:.0%}", "PF >= 1.3", ">= 100 trades", "owner inputs",
    )


def test_check_dev_session():
    check_dev_session(DEV_END)
    check_dev_session(date(1996, 1, 2))
    for late in (date(2015, 10, 17), date(2015, 10, 19), date(2026, 10, 2)):
        with pytest.raises(DevWindowError, match="after the dev window end"):
            check_dev_session(late)
    assert issubclass(DevWindowError, ValueError)
    with pytest.raises(TypeError):
        check_dev_session(datetime(2015, 10, 16))
    with pytest.raises(TypeError):
        check_dev_session("2015-10-16")


def test_entry_points_reject_a_bar_after_dev_end():
    market = short_market(extra_day=date(2015, 10, 19))
    c = cand("C-LATE", allocator=SPY_HOLD)
    with pytest.raises(DevWindowError, match="SPY has a bar on 2015-10-19"):
        candidate_window(market, c)
    with pytest.raises(DevWindowError, match="SPY has a bar on 2015-10-19"):
        run_candidate(market, {}, (), c)
    with pytest.raises(DevWindowError, match="SPY has a bar on 2015-10-19"):
        run_registry(market, {}, (), (c,))


def test_entry_points_reject_fx_after_dev_end():
    market = short_market(fx=FX_SHORT + ((date(2015, 10, 19), Decimal("13500")),))
    c = cand("C-FX", allocator=SPY_HOLD)
    for call in (lambda: candidate_window(market, c),
                 lambda: run_candidate(market, {}, (), c),
                 lambda: run_registry(market, {}, (), (c,))):
        with pytest.raises(DevWindowError, match="usd_idr row on 2015-10-19"):
            call()


def test_run_entry_points_reject_dividends_after_dev_end():
    market = short_market()
    c = cand("C-DIV", allocator=SPY_HOLD)
    late_map = {"AAA": {date(2015, 10, 20): Decimal("0.25")}}
    late_spy = (Dividend(date(2015, 12, 18), Decimal("1.2")),)
    with pytest.raises(DevWindowError, match="AAA has a dividend on 2015-10-20"):
        run_candidate(market, late_map, SPY_DIVS, c)
    with pytest.raises(DevWindowError, match="SPY has a dividend on 2015-12-18"):
        run_candidate(market, DIVS, late_spy, c)
    with pytest.raises(DevWindowError, match="AAA has a dividend"):
        run_registry(market, late_map, SPY_DIVS, (c,))
    with pytest.raises(DevWindowError, match="SPY has a dividend"):
        run_registry(market, DIVS, late_spy, (c,))


def test_rows_reject_an_end_after_dev_end():
    s = stats(metrics())
    with pytest.raises(DevWindowError):
        make_row(cand("C-ROW"), date(2015, 6, 8), date(2015, 10, 19), s, spy_tr=SPY_TR, spy_price=SPY_TR)
    good = make_row(cand("C-ROW"), date(2015, 6, 8), DEV_END, s, spy_tr=SPY_TR, spy_price=SPY_TR)
    with pytest.raises(DevWindowError):
        replace(good, end=date(2016, 1, 4))


def test_dev_does_not_import_research():
    tree = ast.parse(Path(dev_module.__file__).read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
            imported += [f"{node.module}.{a.name}" for a in node.names]
    assert not [m for m in imported if m.startswith("seer_engine.research")]


# --------------------------------------------------------------------------- candidates


def test_candidate_validation():
    base = cand("F1-OK-1")
    assert base.owner_inputs == ()
    for bad in ("f1-lower", "F1_UNDERSCORE", "-F1", "F1-", ""):
        with pytest.raises(ValueError):
            replace(base, id=bad)
    for bad in ("F0", "F12", "f1", "REFX", "C"):
        with pytest.raises(ValueError):
            replace(base, family=bad)
    replace(base, family="F11")
    replace(base, family="REF")
    with pytest.raises(TypeError):
        replace(base, rules=DESIGN_V0)  # an Allocator under the bracket rules
    with pytest.raises(TypeError):
        replace(base, allocator=DipPicks())  # a Strategy under book rules
    with pytest.raises(TypeError):
        replace(base, rules="monthly-hold")
    replace(base, rules=DESIGN_V0, allocator=DipPicks())
    with pytest.raises(ValueError):
        replace(base, rationale="two\nlines")
    with pytest.raises(ValueError):
        replace(base, rationale="   ")
    with pytest.raises(TypeError):
        replace(base, added=datetime(2026, 10, 3))
    with pytest.raises(ValueError):
        replace(base, owner_inputs=("leverage", "etf:SSO"))  # unsorted
    with pytest.raises(ValueError):
        replace(base, owner_inputs=("etf:SSO", "etf:SSO"))
    with pytest.raises(TypeError):
        replace(base, owner_inputs=["etf:SSO"])
    # Declared owner inputs are not checked against the computed ones here (registry test does).
    assert replace(base, owner_inputs=("fee",)).owner_inputs == ("fee",)


def test_candidate_owner_inputs():
    assert candidate_owner_inputs(cand("A-1", allocator=HoldOne("Q", "QQQ"))) == ()
    assert candidate_owner_inputs(cand("A-2", allocator=HoldOne("S", "SSO"))) == ("etf:SSO", "leverage")
    assert candidate_owner_inputs(cand("A-3", allocator=HoldOne("I", "IEF"))) == ("etf:IEF",)
    assert candidate_owner_inputs(cand("A-4", rules=DAILY_SWITCH_TBILL)) == ("etf:BIL",)
    assert candidate_owner_inputs(cand("A-5", allocator=HoldOne("B", "BIL"), rules=DAILY_SWITCH_TBILL)) == ("etf:BIL",)
    frac = replace(MONTHLY_HOLD, id="monthly-frac", fractional=True)
    assert candidate_owner_inputs(cand("A-6", allocator=HoldOne("L", "QLD"), rules=frac)) == (
        "etf:QLD", "fractional", "leverage")
    assert candidate_owner_inputs(cand("A-7", "REF", allocator=DipPicks(), rules=DESIGN_V0)) == ()
    with pytest.raises(TypeError):
        candidate_owner_inputs("A-1")


# --------------------------------------------------------------------------- windows


def test_window_waits_for_the_latest_launch():
    market = short_market()
    assert candidate_window(market, cand("W-SPY", allocator=HoldOne("S5", "SPY", lookback=5))) == (
        date(2015, 6, 8), DEV_END)  # SPY's 5th bar is 06-05
    # XLK launches 07-01; its 5th bar is 07-08 (07-03 is a holiday), so the window opens 07-09.
    assert candidate_window(market, cand("W-XLK", allocator=HoldOne("X5", "XLK", reads=("SPY",), lookback=5))) == (
        date(2015, 7, 9), DEV_END)
    # SPY is always part of the rule, even when the allocator does not read it.
    assert candidate_window(market, cand("W-AAA", allocator=HoldOne("A1", "AAA", lookback=1))) == (
        date(2015, 6, 2), DEV_END)
    # The idle instrument is not part of the rule: BIL is absent from this market.
    assert candidate_window(market, cand("W-IDLE", allocator=HoldOne("S5B", "SPY", lookback=5),
                                         rules=DAILY_SWITCH_TBILL)) == (date(2015, 6, 8), DEV_END)


def test_window_respects_the_membership_start():
    days = dates.sessions(date(1995, 12, 1), date(1996, 1, 31))
    market = Market(history={"SPY": hist("SPY", sawtooth(len(days), 60.0, 0.5, 0.3), days=days)},
                    membership=Membership(()), fx=())
    # SPY's 3rd bar is 1995-12-05.
    assert candidate_window(market, cand("M-NO", allocator=HoldOne("N3", "SPY", lookback=3))) == (
        date(1995, 12, 6), DEV_END)
    assert candidate_window(market, cand("M-YES", allocator=HoldOne("Y3", "SPY", lookback=3, members=True))) == (
        date(1996, 1, 3), DEV_END)
    assert candidate_window(market, cand("M-V0", "REF", allocator=DipPicks(), rules=DESIGN_V0)) == (
        date(1996, 1, 3), DEV_END)


def test_window_errors():
    market = short_market()
    with pytest.raises(ValueError, match="QQQ has 0 bars"):
        candidate_window(market, cand("E-MISSING", allocator=HoldOne("MQ", "QQQ")))
    # SPY (98 bars) is checked first and has enough; XLK (76 bars) does not.
    with pytest.raises(ValueError, match="XLK has 76 bars in the market, the candidate needs 80"):
        candidate_window(market, cand("E-SHORT", allocator=HoldOne("SX", "XLK", lookback=80)))
    # SPY's 98th bar is DEV_END itself: the window would open on 2015-10-19.
    with pytest.raises(DevWindowError, match="would start on 2015-10-19"):
        candidate_window(market, cand("E-LATE", allocator=HoldOne("LS", "SPY", lookback=len(W_DAYS))))
    with pytest.raises(ValueError, match="lookback must be an int >= 1"):
        candidate_window(market, cand("E-ZERO", allocator=HoldOne("Z", "SPY", lookback=0)))


# --------------------------------------------------------------------------- runs


def test_design_v0_candidate_runs_through_run_backtest():
    market = short_market()
    strategy = DipPicks()
    c = cand("REF-DIP-V0", "REF", allocator=strategy, rules=DESIGN_V0)
    result, row = run_candidate(market, DIVS, SPY_DIVS, c)
    assert isinstance(result, RunResult)
    assert (row.start, row.end) == (date(2015, 6, 4), DEV_END)  # AAA/SPY 3rd bar 06-03
    assert result == run_backtest(market, strategy, None, row.start, row.end)
    assert result.usd_idr == Decimal("12500")
    assert row.stats == run_stats(result)
    assert len(result.closed) > 0  # the fake strategy really trades


def test_book_candidate_and_spy_curves():
    market = short_market()
    c = cand("F1-FLIP-D", allocator=HoldOne("FLIP", "SPY", flip=True), rules=DAILY_SWITCH)
    result, row = run_candidate(market, DIVS, SPY_DIVS, c)
    assert isinstance(result, BookResult)
    assert (row.start, row.end) == (date(2015, 6, 8), DEV_END)
    assert result.usd_idr == Decimal("12500")
    assert result.initial_cash == initial_cash_usd(INITIAL_IDR, Decimal("12500"))
    assert row.stats == run_stats(result)
    assert row.stats.metrics.trades > 0
    price, total = spy_curves(market.spy(), row.start, row.end, result.initial_cash, SPY_DIVS)
    assert row.spy_price == curve_metrics(price)
    assert row.spy_tr == curve_metrics(total)
    assert row.spy_tr.total_return > row.spy_price.total_return  # the 09-18 dividend is credited
    assert row == make_row(c, row.start, row.end, row.stats, spy_tr=row.spy_tr, spy_price=row.spy_price)
    assert row.candidate is c


def test_window_before_fx_start_converts_at_the_fx_start_rate():
    market = long_market()
    cash = initial_cash_usd(INITIAL_IDR, Decimal("8002"))
    book, book_row = run_candidate(market, {}, (), cand("F1-LONG", allocator=HoldOne("LONG", "SPY", lookback=1)))
    assert book_row.start == date(1998, 11, 3)
    assert isinstance(book, BookResult)
    assert (book.usd_idr, book.initial_cash) == (Decimal("8002"), cash)
    strategy = DipPicks()
    v0, v0_row = run_candidate(market, {}, (), cand("REF-LONG-V0", "REF", allocator=strategy, rules=DESIGN_V0))
    assert v0_row.start == date(1998, 11, 5)  # SPY's 3rd bar is 1998-11-04
    assert isinstance(v0, RunResult)
    assert (v0.usd_idr, v0.initial_cash) == (Decimal("8002"), cash)
    expected = run_backtest(
        Market(history=market.history, membership=market.membership, fx=((v0_row.start, Decimal("8002")),)),
        strategy, None, v0_row.start, DEV_END,
    )
    assert v0 == expected
    price, _ = spy_curves(market.spy(), v0_row.start, DEV_END, cash, ())
    assert v0_row.spy_price == curve_metrics(price)


# --------------------------------------------------------------------------- D8 rows


def metrics(*, total_return: float | None = 0.5, dd: float | None = 0.10, pf: float | None = 1.5,
            trades: int = 150, cagr: float | None = 0.08) -> Metrics:
    return Metrics(total_return=total_return, win_rate=0.5, profit_factor=pf, max_drawdown=dd,
                   trades=trades, months=230.0, cagr=cagr)


def stats(m: Metrics) -> RunStats:
    return RunStats(metrics=m, exposure=0.6, turnover=2.0, costs_usd=10.0, gross_pnl_usd=100.0,
                    cost_drag=0.1, dividends_usd=0.0, sharpe=0.8, daily_returns=(0.01, -0.005),
                    year_returns=((2010, 0.1),), worst_year=(2010, 0.1))


SPY_TR = Metrics(total_return=0.4, win_rate=None, profit_factor=None, max_drawdown=0.5, trades=0,
                 months=230.0, cagr=0.06)


def row(id: str, family: str = "F1", *, allocator: Any = None, **kw: Any) -> DevRow:
    return make_row(cand(id, family, allocator=allocator), date(2001, 1, 2), DEV_END, stats(metrics(**kw)),
                    spy_tr=SPY_TR, spy_price=SPY_TR)


# The drawdown-miss label, taken from the engine rather than spelled: entry [1] follows
# tuning.MAX_DRAWDOWN (D13), so a literal here would pin the test to one value of the bar.
_DD_MISS = FAILURE_LABELS[1]


@pytest.mark.parametrize("kw, failed", [
    (dict(), ()),
    (dict(dd=MAX_DRAWDOWN), ()),
    (dict(dd=math.nextafter(MAX_DRAWDOWN, 1)), (_DD_MISS,)),
    (dict(dd=None), (_DD_MISS,)),
    (dict(pf=1.3), ()),
    (dict(pf=1.2999), ("PF >= 1.3",)),
    (dict(pf=math.inf), ()),
    (dict(pf=None), ("PF >= 1.3",)),
    (dict(trades=100), ()),
    (dict(trades=99), (">= 100 trades",)),
    (dict(total_return=0.4), ("beats SPY TR",)),  # equal is not beating
    (dict(total_return=0.4000001), ()),
    (dict(total_return=None), ("beats SPY TR",)),
    (dict(dd=0.25, trades=10), (_DD_MISS, ">= 100 trades")),
])
def test_eligibility_boundaries(kw, failed):
    r = row("B-1", **kw)
    assert r.failed == failed
    assert r.eligible is (failed == ())
    assert r.beats_spy is ("beats SPY TR" not in failed)


def test_every_failure_in_order():
    r = row("B-ALL", allocator=HoldOne("SSOH", "SSO"), total_return=0.3, dd=0.3, pf=1.0, trades=5)
    assert r.failed == FAILURE_LABELS
    assert r.eligible is False and r.beats_spy is False
    only_owner = row("B-OWN", allocator=HoldOne("IEFH", "IEF"))
    assert only_owner.failed == ("owner inputs",)
    # D8 reads the computed owner inputs, not the declared ones.
    lying = make_row(cand("B-LIE", allocator=HoldOne("SSOL", "SSO"), owner_inputs=()), date(2001, 1, 2), DEV_END,
                     stats(metrics()), spy_tr=SPY_TR, spy_price=SPY_TR)
    assert lying.failed == ("owner inputs",)


def test_thresholds_come_from_tuning(monkeypatch):
    real_max_dd = tuning.MAX_DRAWDOWN
    assert row("T-1").eligible
    monkeypatch.setattr(tuning, "MAX_DRAWDOWN", 0.05)
    assert row("T-1").failed == (_DD_MISS,)
    monkeypatch.setattr(tuning, "MAX_DRAWDOWN", real_max_dd)
    monkeypatch.setattr(tuning, "MIN_PROFIT_FACTOR", 2.0)
    assert row("T-1").failed == ("PF >= 1.3",)


def test_mar():
    assert row("R-1", cagr=0.12, dd=0.10).mar == 0.12 / 0.10
    assert row("R-2", cagr=-0.03, dd=0.10).mar == -0.03 / 0.10
    assert row("R-3", dd=0.0).mar is None
    assert row("R-4", cagr=None).mar is None
    assert row("R-5", dd=None).mar is None


def test_dev_row_consistency():
    good = row("K-1")
    with pytest.raises(ValueError):
        replace(good, eligible=False)
    with pytest.raises(ValueError):
        replace(good, failed=(">= 100 trades", "PF >= 1.3"), eligible=False)  # out of order
    with pytest.raises(ValueError):
        replace(good, failed=("made up",), eligible=False)
    with pytest.raises(ValueError):
        replace(good, beats_spy=False)
    with pytest.raises(ValueError):
        replace(good, start=date(2016, 1, 4), end=DEV_END)
    with pytest.raises(TypeError):
        replace(good, mar=1)


# --------------------------------------------------------------------------- finalists


def test_finalists_d8():
    rows = [
        row("F5-X", "F5", cagr=0.05, dd=0.10),  # MAR 0.5: fourth family, cut by the cap of 3
        row("F1-B", "F1", cagr=0.12, dd=0.10),  # MAR 1.2, tied with F1-A, loses on id
        row("F4-X", "F4", cagr=0.30, dd=0.25),  # MAR 1.2 but DD over the bar: not eligible
        row("F3-X", "F3", cagr=0.09, dd=0.10),  # MAR 0.9
        row("F1-A", "F1", cagr=0.12, dd=0.10),  # MAR 1.2
        row("F2-X", "F2", cagr=0.10, dd=0.10),  # MAR 1.0
    ]
    assert [r.candidate.id for r in finalists(rows)] == ["F1-A", "F2-X", "F3-X"]
    assert finalists(rows) == finalists(list(reversed(rows)))
    # One per family: with only F1 rows eligible, one finalist.
    assert [r.candidate.id for r in finalists([rows[1], rows[4]])] == ["F1-A"]


def test_finalists_none_eligible():
    assert finalists([]) == ()
    assert finalists([row("N-1", trades=10), row("N-2", "F2", pf=1.0)]) == ()
    with pytest.raises(TypeError):
        finalists(["F1-A"])


def test_finalists_rank_rows_without_mar_last():
    flat = row("Z-FLAT", "F6", dd=0.0)
    assert flat.eligible and flat.mar is None
    ranked = finalists([flat, row("Z-LOW", "F2", cagr=0.01, dd=0.10)])
    assert [r.candidate.id for r in ranked] == ["Z-LOW", "Z-FLAT"]


# --------------------------------------------------------------------------- deflated Sharpe


def test_deflated_sharpe_hand_case():
    # SR = 0.1, N = 10, V = 0.001, T = 1000, skew 0, kurtosis 3:
    #   Φ⁻¹(0.9) = 1.2815516, Φ⁻¹(1 − 1/(10e)) = 1.7892418
    #   SR* = sqrt(0.001) × (0.4227843 × 1.2815516 + 0.5772157 × 1.7892418) = 0.0497932
    #   z = (0.1 − 0.0497932) × sqrt(999) / sqrt(1 + 0.5 × 0.01) = 1.5829329
    #   DSR = Φ(1.5829329) = 0.9432816
    assert deflated_sharpe(0.1, 10, 0.001, 1000, 0.0, 3.0) == pytest.approx(0.9432816, abs=1e-7)


def test_deflated_sharpe_second_case():
    # SR 0.05, N 54, V 0.0004, T 5000, skew −0.5, kurtosis 8: SR* = 0.0461129,
    # z = 0.0038871 × sqrt(4999) / sqrt(1 + 0.025 + 1.75 × 0.0025) = 0.2708825, DSR = 0.6067593.
    assert deflated_sharpe(0.05, 54, 0.0004, 5000, -0.5, 8.0) == pytest.approx(0.6067593, abs=1e-7)


def test_deflated_sharpe_at_the_threshold_is_one_half():
    assert deflated_sharpe(0.0, 20, 0.0, 300, 0.0, 3.0) == 0.5


@pytest.mark.parametrize("args", [
    (0.1, 1, 0.001, 1000, 0.0, 3.0),  # one trial: Φ⁻¹(0) undefined
    (0.1, 10, 0.001, 1, 0.0, 3.0),  # t < 2
    (0.1, 10, -0.001, 1000, 0.0, 3.0),  # negative variance
    (math.nan, 10, 0.001, 1000, 0.0, 3.0),
    (0.1, 10, 0.001, 1000, math.inf, 3.0),
    (0.1, 10, 0.001, 1000, 20.0, 3.0),  # 1 − 20 × 0.1 + 0.005 < 0
])
def test_deflated_sharpe_undefined(args):
    assert deflated_sharpe(*args) is None


def test_deflated_sharpe_types():
    with pytest.raises(TypeError):
        deflated_sharpe(0.1, 10.0, 0.001, 1000, 0.0, 3.0)
    with pytest.raises(TypeError):
        deflated_sharpe(0.1, 10, 0.001, True, 0.0, 3.0)
    with pytest.raises(TypeError):
        deflated_sharpe("0.1", 10, 0.001, 1000, 0.0, 3.0)
    assert deflated_sharpe(1, 10, 0, 1000, 0, 3) is not None  # ints are numbers


# --------------------------------------------------------------------------- run_registry


def short_registry() -> tuple[tuple[Candidate, ...], HoldOne, HoldOne, DipPicks]:
    flip = HoldOne("FLIP", "SPY", flip=True)
    xlk = HoldOne("XLKH", "XLK", reads=("SPY",))
    strategy = DipPicks()
    registry = (
        cand("C-ONE", "F1", allocator=flip, rules=DAILY_SWITCH),
        cand("C-TWO", "REF", allocator=strategy, rules=DESIGN_V0),
        cand("C-THREE", "F2", allocator=xlk, rules=MONTHLY_HOLD),
        cand("C-FOUR", "F1", allocator=flip, rules=MONTHLY_HOLD),
    )
    return registry, flip, xlk, strategy


def test_registry_runs_in_order_and_repeats_equal():
    market = short_market()
    registry, _, _, _ = short_registry()
    seen: list[tuple[int, str, str]] = []
    rows = run_registry(market, DIVS, SPY_DIVS, registry,
                        on_result=lambda i, result, r: seen.append((i, type(result).__name__, r.candidate.id)))
    assert [r.candidate.id for r in rows] == ["C-ONE", "C-TWO", "C-THREE", "C-FOUR"]
    assert seen == [(0, "BookResult", "C-ONE"), (1, "RunResult", "C-TWO"),
                    (2, "BookResult", "C-THREE"), (3, "BookResult", "C-FOUR")]
    assert [(r.start, r.end) for r in rows] == [
        (date(2015, 6, 8), DEV_END), (date(2015, 6, 4), DEV_END), (date(2015, 7, 9), DEV_END), (date(2015, 6, 8), DEV_END),
    ]
    assert run_registry(market, DIVS, SPY_DIVS, registry) == rows
    assert run_registry(market, DIVS, SPY_DIVS, ()) == ()


def test_registry_prepares_once_per_allocator_id_per_call():
    market = short_market()
    registry, flip, xlk, strategy = short_registry()
    run_registry(market, DIVS, SPY_DIVS, registry)
    assert (flip.prepare_calls, xlk.prepare_calls, strategy.prepare_calls) == (1, 1, 1)
    assert len(flip.prepared_seen) > 0 and len(set(flip.prepared_seen)) == 1  # C-ONE and C-FOUR share it
    run_registry(market, DIVS, SPY_DIVS, registry)
    assert (flip.prepare_calls, xlk.prepare_calls, strategy.prepare_calls) == (2, 2, 2)


def test_registry_refuses_shared_ids_duplicates_and_oversize():
    market = short_market()
    twin_a, twin_b = HoldOne("TWIN", "SPY"), HoldOne("TWIN", "XLK", reads=("SPY",))
    with pytest.raises(ValueError, match="share the id 'TWIN'"):
        run_registry(market, DIVS, SPY_DIVS, (cand("D-A", allocator=twin_a), cand("D-B", allocator=twin_b)))
    assert twin_a.prepare_calls == twin_b.prepare_calls == 0  # refused before anything ran
    with pytest.raises(ValueError, match="appears twice"):
        run_registry(market, DIVS, SPY_DIVS, (cand("D-SAME", allocator=twin_a), cand("D-SAME", allocator=twin_a)))
    big = tuple(cand(f"D-{i}", allocator=twin_a) for i in range(MAX_CANDIDATES + 1))
    with pytest.raises(ValueError, match="the cap is 60"):
        run_registry(market, DIVS, SPY_DIVS, big)
    with pytest.raises(TypeError):
        run_registry(market, DIVS, SPY_DIVS, ("C-ONE",))


def test_registry_rows_equal_unprepared_single_runs():
    market = short_market()
    registry, _, _, _ = short_registry()
    rows = run_registry(market, DIVS, SPY_DIVS, registry)
    assert rows == tuple(run_candidate(market, DIVS, SPY_DIVS, c)[1] for c in registry)


# --------------------------------------------------------------------------- the test window

ACROSS_DAYS = dates.sessions(date(2015, 6, 1), date(2015, 11, 30))  # spans DEV_END
TEST_WINDOW = Window(name="test", start=date(2015, 10, 19), end=date(2015, 11, 30))


def across_market() -> Market:
    """SPY and AAA from 2015-06-01 to 2015-11-30: a market that runs past DEV_END."""
    return Market(
        history={
            "AAA": hist("AAA", sawtooth(len(ACROSS_DAYS), 50.0, 1.0, 0.9), days=ACROSS_DAYS),
            "SPY": hist("SPY", sawtooth(len(ACROSS_DAYS), 200.0, 2.0, 1.5), days=ACROSS_DAYS),
        },
        membership=Membership((("AAA", date(1990, 1, 2), None),)),
        fx=FX_SHORT,
    )


def test_the_default_window_is_the_dev_window():
    assert DEV_WINDOW == Window(name="dev", start=date.min, end=DEV_END)
    assert DEV_WINDOW.end == DEV_END


def test_a_caller_that_passes_nothing_is_still_refused_past_dev_end():
    """The D9 refusal is absolute by default: the window argument does not weaken it."""
    market = across_market()
    c = cand("T-DEFAULT", allocator=HoldOne("TD", "SPY", lookback=5))
    for call in (lambda: candidate_window(market, c),
                 lambda: run_candidate(market, {}, (), c),
                 lambda: run_registry(market, {}, (), (c,))):
        with pytest.raises(DevWindowError, match="after the dev window end 2015-10-16"):
            call()


def test_an_explicit_test_window_runs_past_dev_end():
    market = across_market()
    c = cand("T-RUN", allocator=HoldOne("TR", "SPY", lookback=5))
    assert candidate_window(market, c, window=TEST_WINDOW) == (date(2015, 10, 19), date(2015, 11, 30))
    result, row = run_candidate(market, {}, (), c, window=TEST_WINDOW)
    assert (row.start, row.end) == (date(2015, 10, 19), date(2015, 11, 30))
    assert row.window == TEST_WINDOW and row.window.name == "test"
    assert run_registry(market, {}, (), (c,), window=TEST_WINDOW) == (row,)


def test_a_test_window_opens_no_earlier_than_its_own_start():
    """The floor: the lookback may be satisfied long before the window, the run may not start there."""
    c = cand("T-FLOOR", allocator=HoldOne("TF", "SPY", lookback=1))
    assert candidate_window(short_market(), c)[0] == date(2015, 6, 2)  # dev: as early as the data allows
    assert candidate_window(across_market(), c, window=TEST_WINDOW)[0] == TEST_WINDOW.start


def test_a_test_window_still_waits_for_the_lookback():
    market = across_market()
    n = ACROSS_DAYS.index(date(2015, 11, 2)) + 1  # SPY's n-th bar is 2015-11-02
    c = cand("T-LOOK", allocator=HoldOne("TL", "SPY", lookback=n))
    assert candidate_window(market, c, window=TEST_WINDOW) == (
        dates.next_session(date(2015, 11, 2)), date(2015, 11, 30))


def test_the_dividend_guard_follows_the_window_too():
    market = across_market()
    c = cand("T-DIV", allocator=HoldOne("TV", "SPY", lookback=5))
    late = date(2015, 11, 20)
    divs = {"SPY": {late: Decimal("1.03")}}
    spy_divs = (Dividend(late, Decimal("1.03")),)
    with pytest.raises(DevWindowError, match="after the dev window end"):
        run_candidate(market, divs, spy_divs, c)
    _, row = run_candidate(market, divs, spy_divs, c, window=TEST_WINDOW)
    assert row.end == date(2015, 11, 30)
    beyond = (Dividend(date(2015, 12, 18), Decimal("1.03")),)
    with pytest.raises(DevWindowError, match="after the test window end 2015-11-30"):
        run_candidate(market, divs, beyond, c, window=TEST_WINDOW)


def test_rows_carry_their_window():
    s = stats(metrics())
    with pytest.raises(DevWindowError, match="after the dev window end"):
        make_row(cand("T-ROW"), date(2015, 10, 19), date(2015, 11, 30), s, spy_tr=SPY_TR, spy_price=SPY_TR)
    row = make_row(cand("T-ROW"), date(2015, 10, 19), date(2015, 11, 30), s,
                   spy_tr=SPY_TR, spy_price=SPY_TR, window=TEST_WINDOW)
    assert row.window == TEST_WINDOW
    with pytest.raises(ValueError, match="is before the test window start"):
        make_row(cand("T-EARLY"), date(2015, 6, 8), date(2015, 11, 30), s,
                 spy_tr=SPY_TR, spy_price=SPY_TR, window=TEST_WINDOW)
    assert make_row(cand("T-DEV"), date(2015, 6, 8), DEV_END, s,
                    spy_tr=SPY_TR, spy_price=SPY_TR).window == DEV_WINDOW
    with pytest.raises(TypeError, match="window must be a Window"):
        make_row(cand("T-BAD"), date(2015, 6, 8), DEV_END, s,
                 spy_tr=SPY_TR, spy_price=SPY_TR, window="test")


def test_the_drawdown_label_follows_the_bar_and_keeps_its_prefix() -> None:
    """D13: the label names the bar it enforces, and the prefix is the part that is stable.

    `trials.failed` is append-only, so the 30 committed rows judged at 15% keep that text for
    ever while rows judged from now on carry 20%. Both must read as a drawdown miss, which is why
    every reader matches the prefix and never the whole string.
    """
    assert len(FAILURE_LABELS) == 5
    assert FAILURE_LABELS[1] == f"max DD <= {tuning.MAX_DRAWDOWN:.0%}" == "max DD <= 20%"
    assert FAILURE_LABELS[1].startswith("max DD <= ")
    assert "max DD <= 15%".startswith("max DD <= "), "the historical rows share the prefix"
    assert FAILURE_LABELS[0] == "beats SPY TR" and FAILURE_LABELS[-1] == "owner inputs"
