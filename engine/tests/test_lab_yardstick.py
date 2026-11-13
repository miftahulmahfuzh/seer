"""``lab.yardstick``: the random-twin engine, on synthetic dev-window markets only.

Every market here is built in memory from ``labkit.smoke_history``: no research store, no network,
no database. The allocators are small stand-ins written for this file, so a test fails because the
yardstick broke, never because a method file moved.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal

import numpy as np
import pytest
from labkit import BASE_ETFS, SMOKE_FIRST, SPY_EX_DATE, smoke_history

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.dev import DEV_END, Candidate, run_candidate
from seer_engine.backtest.market import Market, Membership
from seer_engine.lab import yardstick as ys
from seer_engine.lab.control_shape import REFUSE_BAND
from seer_engine.prices import to_decimal
from seer_engine.sim import q
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine.sim.rules import (
    DESIGN_V0,
    MONTHLY_HOLD,
    MONTHLY_HOLD_FRAC_GOTRADE,
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
)
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS
from seer_engine.strategies.allocator import prepare_for
from seer_engine.strategies.base import History
from seer_engine.strategies.f_index import TIMING, TimingParams

CAPITAL = Decimal("10000000")
SPY_DIV = Decimal("1.0300")
DIVIDENDS = {"SPY": {SPY_EX_DATE: SPY_DIV}}
SPY_DIVIDENDS = (Dividend(SPY_EX_DATE, SPY_DIV),)
LOOKBACK = ys.LIQUIDITY_BARS + 1  # every member is rankable at the arm's first decision
ZERO_DIGEST = "0" * 64


# --------------------------------------------------------------------------- synthetic markets


def _member(i: int) -> str:
    return f"S{i:02d}"


def _drop(h: History, days: Iterable[date]) -> History:
    gone = np.array(sorted(days), dtype="datetime64[D]")
    if gone.size == 0:
        return h
    keep = ~np.isin(h.dates, gone)
    return History(h.symbol, h.dates[keep], h.open[keep], h.high[keep], h.low[keep], h.close[keep], h.volume[keep])


def _market(members: int = 40, gaps: Mapping[str, Iterable[date]] | None = None) -> Market:
    """The labkit ETFs plus ``members`` index members S00, S01, ... with ``gaps`` bars removed."""
    days = dates.sessions(SMOKE_FIRST, DEV_END)
    history = {s: smoke_history(s, k, days) for k, s in enumerate(BASE_ETFS)}
    names = tuple(_member(i) for i in range(members))
    for j, name in enumerate(names):
        history[name] = _drop(smoke_history(name, len(BASE_ETFS) + j, days), (gaps or {}).get(name, ()))
    membership = Membership(intervals=tuple((s, days[0], None) for s in names))
    return Market(history=history, membership=membership, fx=((days[0], Decimal("2000")),))


def _close_target(h: History, d: date, weight: Decimal) -> Target | None:
    i = h.index_of(d)
    if i is None:
        return None
    return Target(symbol=h.symbol, weight=weight, last=q(to_decimal(float(h.close[i]))))


# --------------------------------------------------------------------------- stand-in allocators


@dataclasses.dataclass(frozen=True)
class TopParams:
    k: int


class TopMomentum:
    """Equal-weight top ``k`` members by 20-session return on the data date: a stand-in picker."""

    id = "test-top-momentum"

    def lookback(self, params):
        return LOOKBACK

    def symbols(self, params):
        return ()

    def holds(self, params):
        return ()

    def uses_members(self, params):
        return True

    def prepare(self, history):
        return history

    def targets(self, history, members, data_date, held, params):
        return self.targets_prepared(history, members, data_date, held, params)

    def targets_prepared(self, prepared, members, data_date, held, params):
        scored = []
        for s in sorted(members):
            h = prepared.get(s)
            i = None if h is None else h.index_of(data_date)
            if i is None or i < 20:
                continue
            scored.append((-(float(h.close[i]) / float(h.close[i - 20])), s))
        scored.sort()
        w = equal_weight(params.k)
        return tuple(_close_target(prepared[s], data_date, w) for _, s in scored[: params.k])


class AwareTopMomentum(TopMomentum):
    """The same picker, prepared from the whole market (the ``MarketAware`` path)."""

    id = "test-aware-top-momentum"

    def __init__(self):
        self.market_prepares = 0

    def prepare_market(self, market):
        self.market_prepares += 1
        return market.history


class HoldTwo:
    """Holds S00 and S01, half each, at every decision: two picked names in one endless spell."""

    id = "test-hold-two"

    def lookback(self, params):
        return LOOKBACK

    def symbols(self, params):
        return ()

    def holds(self, params):
        return ()

    def uses_members(self, params):
        return True

    def prepare(self, history):
        return history

    def targets(self, history, members, data_date, held, params):
        return self.targets_prepared(history, members, data_date, held, params)

    def targets_prepared(self, prepared, members, data_date, held, params):
        w = equal_weight(2)
        out = (_close_target(prepared[s], data_date, w) for s in (_member(0), _member(1)))
        return tuple(t for t in out if t is not None)


def _cand(cid, allocator, params, rules=MONTHLY_HOLD_FRAC_GOTRADE) -> Candidate:
    return Candidate(
        id=cid, family="M0001", rules=rules, allocator=allocator, params=params,
        rationale="yardstick test arm", added=date(2026, 11, 13), owner_inputs=(),
    )


def _plain(market, c):
    return run_candidate(
        market, DIVIDENDS, SPY_DIVIDENDS, c,
        prepared=prepare_for(c.allocator, market), initial_idr=CAPITAL, contributions=OWNER_MONTHLY,
    )


def _record(market, c):
    return ys.record(market, DIVIDENDS, SPY_DIVIDENDS, c, initial_idr=CAPITAL, contributions=OWNER_MONTHLY)


def _measure(market, c, **kw):
    return ys.measure(market, DIVIDENDS, SPY_DIVIDENDS, c, initial_idr=CAPITAL, contributions=OWNER_MONTHLY, **kw)


def _same_run(a, b):
    ma, mb = a.stats.metrics, b.stats.metrics
    assert (ma.trades, ma.total_return, ma.mwr, ma.cagr, ma.max_drawdown) == (
        mb.trades, mb.total_return, mb.mwr, mb.cagr, mb.max_drawdown
    )
    assert a.stats.turnover == b.stats.turnover
    assert (a.start, a.end) == (b.start, b.end)


@pytest.fixture(scope="module")
def market():
    return _market(40)


@pytest.fixture(scope="module")
def top3():
    return _cand("T-TOP3", TopMomentum(), TopParams(3))


def _gapped_hold_two():
    """``HoldTwo`` on a 20-member market where, from the second rank decision on, every other
    member misses its bar on alternate rank data dates (even members on one, odd on the next).

    A twin drawn on one rank date belongs to the half that trades that day, so it misses the next
    rank date's bar and is redrawn there: from the third decision on, every decision redraws.
    """
    c = _cand("T-HOLD2", HoldTwo(), None)
    decisions, _ = _record(_market(20), c)
    rank_days = [d.data_date for d in decisions if d.rank]
    gaps: dict[str, list[date]] = {}
    for j, d in enumerate(rank_days[1:]):
        for i in range(2, 20):
            if i % 2 == j % 2:
                gaps.setdefault(_member(i), []).append(d)
    return _market(20, gaps), c


# --------------------------------------------------------------------------- R1.1: the twin


@pytest.mark.parametrize("rules", [MONTHLY_HOLD_FRAC_GOTRADE, MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE])
def test_recording_and_replaying_an_arm_reproduces_it_exactly(market, rules):
    """The premise of the whole yardstick: a recorded run IS the arm's run, and replaying the
    record through a second allocator gives the identical book, resize sessions included."""
    c = _cand("T-TOP3", TopMomentum(), TopParams(3), rules)
    plain_result, plain = _plain(market, c)
    decisions, recorded = _record(market, c)
    replay = ys.Replay(c.allocator, {d.data_date: d.targets for d in decisions})
    replay_result, replayed = run_candidate(
        market, DIVIDENDS, SPY_DIVIDENDS, dataclasses.replace(c, allocator=replay),
        prepared=prepare_for(replay, market), initial_idr=CAPITAL, contributions=OWNER_MONTHLY,
    )
    assert plain.stats.metrics.trades > 0
    _same_run(recorded, plain)
    _same_run(replayed, plain)
    assert replay_result.snapshots == plain_result.snapshots
    assert len({d.data_date for d in decisions}) == len(decisions)
    if rules is MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE:
        assert any(not d.rank for d in decisions) and any(d.rank for d in decisions)
    else:
        assert all(d.rank for d in decisions)
    assert ys.Replay(c.allocator, {}, seed=1).id != ys.Replay(c.allocator, {}, seed=2).id


def test_a_market_aware_allocator_is_recorded_through_prepare_market(market):
    aware = AwareTopMomentum()
    c = _cand("T-AWARE", aware, TopParams(3))
    _, plain = _plain(market, c)
    before = aware.market_prepares
    decisions, recorded = _record(market, c)
    assert aware.market_prepares == before + 1
    assert decisions
    _same_run(recorded, plain)


def test_a_twin_keeps_every_decision_date_and_weight_and_swaps_every_picked_name(market, top3):
    decisions, _ = _record(market, top3)
    fixed = ys.fixed_symbols(top3)
    schedule = ys.twin_schedule(market, decisions, fixed, ys.seed_for(ZERO_DIGEST, 0))
    assert sorted(schedule) == sorted(d.data_date for d in decisions)
    previous: dict[str, str] = {}  # real name -> its twin at the previous rank decision
    swapped = 0
    for d in sorted(decisions, key=lambda x: x.data_date):
        twin = schedule[d.data_date]
        assert len(twin) == len(d.targets)
        assert sorted(t.weight for t in twin) == sorted(t.weight for t in d.targets)
        assert len({t.symbol for t in twin}) == len(twin)
        real_names = {t.symbol for t in d.targets if t.symbol not in fixed}
        now: dict[str, str] = {}
        for r, t in zip(d.targets, twin):
            if r.symbol in fixed:
                assert t == r
                continue
            swapped += 1
            assert t.weight == r.weight
            assert t.symbol in d.members and t.symbol not in fixed
            assert t.last == q(market.bar(t.symbol, d.data_date).close)
            if previous.get(r.symbol) != t.symbol:  # drawn at this decision
                assert t.symbol not in real_names
            now[r.symbol] = t.symbol
        previous = now
    assert swapped > 0


def test_a_resize_decision_is_copied_unchanged(market):
    c = _cand("T-TOP3R", TopMomentum(), TopParams(3), MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE)
    decisions, _ = _record(market, c)
    schedule = ys.twin_schedule(market, decisions, ys.fixed_symbols(c), ys.seed_for(ZERO_DIGEST, 0))
    resizes = [d for d in decisions if not d.rank]
    assert resizes
    for d in resizes:
        assert schedule[d.data_date] == d.targets


def _dollar_volume_ranks(market, members, d):
    """The test's own ranking: median close x volume over the 63 bars on or before d."""
    day = np.datetime64(d, "D")
    rows = []
    for s in members:
        h = market.history[s]
        end = int(np.searchsorted(h.dates, day, side="right"))
        if end >= ys.LIQUIDITY_BARS:
            rows.append((-float(np.median(h.close[end - 63 : end] * h.volume[end - 63 : end])), s))
    return [s for _, s in sorted(rows)]


def test_a_twin_is_drawn_from_the_real_picks_trading_size_neighbourhood():
    wide = _market(60)
    c = _cand("T-TOP3W", TopMomentum(), TopParams(3))
    decisions, _ = _record(wide, c)
    schedule = ys.twin_schedule(wide, decisions, ys.fixed_symbols(c), ys.seed_for(ZERO_DIGEST, 3))
    checked = 0
    previous: frozenset[str] = frozenset()
    for d in sorted(decisions, key=lambda x: x.data_date):
        order = _dollar_volume_ranks(wide, d.members, d.data_date)
        for r, t in zip(d.targets, schedule[d.data_date]):
            if r.symbol not in previous:  # a new spell: its twin was drawn here
                assert abs(order.index(t.symbol) - order.index(r.symbol)) <= ys.NEIGHBOUR_RANKS
                checked += 1
        previous = frozenset(t.symbol for t in d.targets)
    assert checked > 0


def test_a_twin_keeps_its_name_for_the_whole_holding_spell(market):
    c = _cand("T-HOLD2", HoldTwo(), None)
    decisions, _ = _record(market, c)
    schedule = ys.twin_schedule(market, decisions, ys.fixed_symbols(c), ys.seed_for(ZERO_DIGEST, 0))
    firsts = {tuple(t.symbol for t in schedule[d.data_date]) for d in decisions}
    assert len(decisions) > 3
    assert len(firsts) == 1, "one spell, one pair of twins, from the first decision to the last"
    (pair,) = firsts
    assert len(set(pair)) == 2 and not set(pair) & {_member(0), _member(1)}


def test_a_twin_that_stops_trading_is_redrawn_at_that_decision():
    gapped, c = _gapped_hold_two()
    decisions, _ = _record(gapped, c)
    schedule = ys.twin_schedule(gapped, decisions, ys.fixed_symbols(c), ys.seed_for(ZERO_DIGEST, 0))
    days = sorted(d.data_date for d in decisions if d.rank)
    assert len(days) > 4
    for before, after in zip(days[1:], days[2:]):
        assert schedule[before][0].symbol != schedule[after][0].symbol
        for t in schedule[after]:
            assert gapped.bar(t.symbol, after) is not None


def test_the_measurement_counts_the_twins_the_arm_out_earned(market, top3):
    _, plain = _plain(market, top3)
    m = _measure(market, top3, draws=6)
    assert m.status == ys.STATUS_MEASURED
    assert m.draws == 6 and len(m.rates) == 6 and list(m.rates) == sorted(m.rates)
    assert m.arm_rate == plain.stats.metrics.mwr  # funded: the money-weighted return
    assert m.beaten == sum(1 for r in m.rates if r < m.arm_rate)
    assert m.percentile == m.beaten / 6
    assert REFUSE_BAND[0] <= m.turnover_ratio <= REFUSE_BAND[1]
    assert m.reproduced is None


# --------------------------------------------------------------------------- R1.3: unmatched


def test_twins_whose_shape_leaves_the_band_are_unmatched():
    gapped, c = _gapped_hold_two()
    m = _measure(gapped, c, draws=4)
    assert m.status == ys.STATUS_UNMATCHED
    assert m.turnover_ratio is not None and m.turnover_ratio > REFUSE_BAND[1]
    assert m.draws == 4 and m.percentile == m.beaten / 4  # the reading is kept, it just never clears


# --------------------------------------------------------------------------- R1.4: not applicable


def test_an_etf_only_arm_is_not_applicable_and_simulates_no_twin(market, monkeypatch):
    def no_twin(work, seed):
        raise AssertionError("a not-applicable arm must not simulate a twin")

    monkeypatch.setattr(ys, "_twin_outcome", no_twin)
    c = _cand("T-SPY", TIMING, TimingParams(hold="SPY", signal="SPY", rule="sma", n=50), MONTHLY_HOLD)
    m = _measure(market, c)
    assert m.status == ys.STATUS_NOT_APPLICABLE
    assert (m.draws, m.beaten, m.percentile, m.rates) == (0, 0, None, ())
    assert m.arm_rate is not None


def test_a_bracket_arm_is_not_applicable(market):
    c = _cand("T-BRACKET", STRATEGY_A, STRATEGY_A_PARAMS, DESIGN_V0)
    m = _measure(market, c)
    assert m.status == ys.STATUS_NOT_APPLICABLE and m.draws == 0 and m.reproduced is None


# --------------------------------------------------------------------------- R1.5: determinism


def test_the_result_is_identical_for_any_number_of_jobs(market, top3):
    one = _measure(market, top3, draws=4, jobs=1)
    two = _measure(market, top3, draws=4, jobs=2)
    again = _measure(market, top3, draws=4, jobs=1)
    assert one == two == again
    assert one.draws == 4


def test_the_draw_rule_is_pinned():
    """Golden vector: any edit to the seed or the draw hash goes red here, and must become a new
    ``RULE_ID`` instead of a quiet change to what every stored reading meant."""
    assert ys.RULE_ID == "yardstick-v1"
    assert (ys.DRAWS, ys.LIQUIDITY_BARS, ys.NEIGHBOUR_RANKS) == (200, 63, 25)
    s0, s1 = ys.seed_for(ZERO_DIGEST, 0), ys.seed_for(ZERO_DIGEST, 1)
    assert s0 == 11146197528017810122
    assert s1 == 1086165951305291315
    pool = ("BBB", "CCC", "DDD", "EEE", "FFF")
    assert ys._draw_order(s0, "AAA", "2014-01", pool)[0] == "FFF"
    assert ys._draw_order(s0, "AAA", "2014-02", pool)[0] == "CCC"
    assert ys._draw_order(s1, "AAA", "2014-02", pool)[0] == "DDD"


# --------------------------------------------------------------------------- the reproduce check


def test_a_wrong_expectation_is_refused_and_a_right_one_is_reported(market, top3):
    _, plain = _plain(market, top3)
    trades, total = plain.stats.metrics.trades, plain.stats.metrics.total_return
    with pytest.raises(ys.Unreproducible):
        _measure(market, top3, draws=1, expect=(trades + 1, total))
    with pytest.raises(ys.Unreproducible):
        _measure(market, top3, draws=1, expect=(trades, total + 1e-6))
    assert _measure(market, top3, draws=1, expect=(trades, total)).reproduced is True
