"""lab.panel: the stock-by-month signal panel, on a synthetic market built for it.

labkit's smoke market has 473 sessions and eight member stocks: too few names for a cross-section
of MIN_SCORED and too few months for an era. So this module builds its own market: sixty members
plus SPY, from 2005 to DEV_END, with two hidden signals planted in next month's returns and made
readable on the decision date's bar. One is in the bar's volume, in every month; the other is
in its open, from 2009 only. There is also a dividend, a name whose bars stop on a decision date
and a name whose bars stop mid-month. Randomness lives in this fixture, under a fixed seed. The
signals under test stay pure.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import replace
from datetime import date
from decimal import Decimal

import numpy as np
import pytest
from labkit import smoke_data, smoke_test_data

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END
from seer_engine.backtest.market import Market, Membership
from seer_engine.lab import panel
from seer_engine.lab.signal import Signal
from seer_engine.lab.signals.s0002_hash_draw import SIGNAL as HASH_DRAW
from seer_engine.lab.tree_rank import month_ends
from seer_engine.research import ResearchData
from seer_engine.strategies.base import History

FIRST = date(2005, 1, 3)
DAYS = dates.sessions(FIRST, DEV_END)
ENDS = month_ends(FIRST, DEV_END)
STOCKS = tuple(f"N{k:03d}" for k in range(60))
GONE = "GONE"  # last bar dated on a decision date: no bar after it, so dropped and counted
HALF = "HALF"  # last bar mid-month: that close is its exit
NAMES = STOCKS + (GONE, HALF)
GONE_DAY = date(2010, 6, 30)  # the last session of June 2010, a decision date
HALF_DAY = date(2011, 3, 15)  # mid-month, inside the forward month of 2011-02-28
PAYER = "N000"
EX_DAY = date(2012, 5, 15)  # inside the forward month of 2012-04-30 (entry 05-01, exit 06-01)
DIVIDEND = Decimal("1.50")
BETAS = {s: 0.5 + k / len(NAMES) for k, s in enumerate(NAMES)}
SEED = 20261113


def _history(symbol: str, days, open_, close, volume) -> History:
    open_ = np.asarray(open_, dtype=np.float64)
    close = np.asarray(close, dtype=np.float64)
    high = np.maximum(open_, close) * 1.01
    low = np.minimum(open_, close) * 0.99
    return History(symbol, np.array(days, dtype="datetime64[D]"), open_, high, low, close,
                   np.asarray(volume, dtype=np.float64))


def _forward_windows() -> np.ndarray:
    """For each session, the decision whose forward month it closes in (entry, exit]; -1 for none."""
    pos = {d: t for t, d in enumerate(DAYS)}
    out = np.full(len(DAYS), -1)
    for q in range(len(ENDS) - 1):
        lo = pos[dates.next_session(ENDS[q])]
        hi = pos.get(dates.next_session(ENDS[q + 1]))
        if hi is None:
            break
        out[lo + 1 : hi + 1] = q
    return out


def _build() -> ResearchData:
    rng = np.random.default_rng(SEED)
    n = len(DAYS)
    win = _forward_windows()
    live = win >= 0
    length = np.bincount(win[live], minlength=len(ENDS))
    recent = np.array([d >= panel.ERA_SPLIT for d in ENDS])
    row_of = {d: t for t, d in enumerate(DAYS)}
    end_rows = np.array([row_of[d] for d in ENDS])
    z_volume = rng.standard_normal((len(NAMES), len(ENDS)))
    z_open = rng.standard_normal((len(NAMES), len(ENDS)))
    market_ret = 0.0003 + 0.009 * rng.standard_normal(n)
    history: dict[str, History] = {}
    for k, symbol in enumerate(NAMES):
        q = win[live]
        planted = np.zeros(n)
        planted[live] = (0.02 * z_volume[k, q] + 0.02 * z_open[k, q] * recent[q]) / length[q]
        logret = BETAS[symbol] * market_ret + 0.012 * rng.standard_normal(n) + planted
        close = 100.0 * np.exp(np.cumsum(logret))
        open_ = np.concatenate((close[:1], close[:-1]))
        open_[end_rows] = close[end_rows] * (1.0 + 0.01 * z_open[k])
        volume = np.full(n, 1_000_000.0)
        volume[end_rows] = 1_000_000.0 * np.exp(0.5 * z_volume[k])
        stop = n
        if symbol == GONE:
            stop = row_of[GONE_DAY] + 1
        elif symbol == HALF:
            stop = row_of[HALF_DAY] + 1
        history[symbol] = _history(symbol, DAYS[:stop], open_[:stop], close[:stop], volume[:stop])
    spy_close = 100.0 * np.exp(np.cumsum(market_ret))
    history["SPY"] = _history("SPY", DAYS, np.concatenate((spy_close[:1], spy_close[:-1])), spy_close,
                              np.full(n, 50_000_000.0))
    market = Market(
        history=history,
        membership=Membership(intervals=tuple((s, DAYS[0], None) for s in NAMES)),
        fx=((DAYS[0], Decimal("2000")),),
    )
    return ResearchData(
        market=market,
        dividends={PAYER: {EX_DAY: DIVIDEND}},
        spy_dividends=(),
        fingerprint="panel-fixture",
        manifest={},
        price_fingerprint="panel-fixture",
    )


def _planted_signal(sid: str, score, lookback: int = 1) -> Signal:
    return Signal(
        id=sid, name="planted in the fixture", family="test-planted", source_kind="knowledge",
        source_ref="", hypothesis="planted", expected_failure="none: it is planted",
        lookback=lookback, score=score,
    )


def _volume_score(history, market, pool, data_date):
    out = {}
    for symbol in sorted(pool):
        h = history.get(symbol)
        i = None if h is None else h.index_of(data_date)
        if i is not None:
            out[symbol] = float(np.log(h.volume[i]))
    return out


def _open_score(history, market, pool, data_date):
    out = {}
    for symbol in sorted(pool):
        h = history.get(symbol)
        i = None if h is None else h.index_of(data_date)
        if i is not None:
            out[symbol] = float(h.open[i] / h.close[i] - 1.0)
    return out


PLANTED = _planted_signal("S9001", _volume_score)  # every month
RECENT = _planted_signal("S9002", _open_score)  # 2009 on only


def _top10_picks(market, pool, data_date):
    scores = PLANTED.scores(market, pool, data_date)
    ranked = sorted((s for s in scores if s in pool), key=lambda s: (-scores[s], s))[:10]
    return {s: 1.0 for s in ranked}


@pytest.fixture(scope="module")
def data() -> ResearchData:
    return _build()


@pytest.fixture(scope="module")
def frame(data) -> panel.PanelFrame:
    return panel.build_frame(data)


@pytest.fixture(scope="module")
def planted(frame) -> panel.PanelReading:
    return panel.measure(frame, panel.signal_scorer(PLANTED))


def _month(frame, day: date) -> panel.PanelMonth:
    return next(m for m in frame.months if m.day == day)


def _close_on(h: History, d: date) -> float:
    i = h.index_of(d)
    assert i is not None, (h.symbol, d)
    return float(h.close[i])


# ---- the frame ------------------------------------------------------------------------------


def test_frame_months_run_month_end_to_month_end_inside_the_dev_window(frame):
    months = frame.months
    first = next(e for e in ENDS if DAYS.index(e) >= 252)  # SCREEN needs 253 bars through d
    assert months[0].day == first
    assert [m.day for m in months] == sorted(m.day for m in months)
    for m, following in zip(months, months[1:]):
        assert m.day in ENDS
        assert m.entry == dates.next_session(m.day)
        assert m.exit == dates.next_session(following.day)
    assert months[-1].exit <= DEV_END
    # ENDS[-1] (2015-09-30) has no forward month inside the window, so the last decision is ENDS[-2].
    assert months[-1].day == ENDS[-2]


def test_the_forward_return_is_a_total_return_with_the_dividend(frame, data):
    m = _month(frame, date(2012, 4, 30))
    entry, exit_ = date(2012, 5, 1), date(2012, 6, 1)
    payer = data.market.history[PAYER]
    expected = (_close_on(payer, exit_) + float(DIVIDEND)) / _close_on(payer, entry) - 1.0
    assert m.ret[m.row[PAYER]] == pytest.approx(expected, rel=1e-12)
    other = data.market.history["N001"]
    assert m.ret[m.row["N001"]] == pytest.approx(_close_on(other, exit_) / _close_on(other, entry) - 1.0, rel=1e-12)


def test_a_name_whose_bars_stop_on_the_decision_date_is_dropped_and_counted(frame):
    m = _month(frame, GONE_DAY)
    assert GONE in m.pool
    assert math.isnan(m.ret[m.row[GONE]])
    later = frame.months[frame.months.index(m) + 1]
    assert GONE not in later.symbols
    assert panel.measure(frame, panel.signal_scorer(HASH_DRAW)).dropped_exits == 1


def test_a_name_whose_bars_stop_mid_month_exits_at_its_last_close(frame, data):
    m = _month(frame, date(2011, 2, 28))
    half = data.market.history[HALF]
    expected = _close_on(half, HALF_DAY) / _close_on(half, date(2011, 3, 1)) - 1.0
    assert m.ret[m.row[HALF]] == pytest.approx(expected, rel=1e-12)


def test_every_pool_name_has_all_four_controls_and_beta_tracks_the_planted_beta(frame):
    for m in frame.months:
        assert np.isfinite(m.controls[m.in_pool]).all(), m.day
    m = _month(frame, date(2012, 4, 30))
    names = [s for s in STOCKS if s in m.row]
    measured = np.array([m.controls[m.row[s], panel.CONTROLS.index("beta")] for s in names])
    planted = np.array([BETAS[s] for s in names])
    assert np.corrcoef(measured, planted)[0, 1] > 0.8


def test_build_frame_refuses_a_test_window_store():
    with pytest.raises(ValueError, match="dev window only"):
        panel.build_frame(smoke_test_data())


def test_build_frame_refuses_a_store_without_spy():
    d = smoke_data()
    market = replace(d.market, history={s: h for s, h in d.market.history.items() if s != "SPY"})
    with pytest.raises(ValueError, match="SPY"):
        panel.build_frame(replace(d, market=market))


# ---- the readings ---------------------------------------------------------------------------


def test_a_planted_signal_is_recovered_in_every_era(planted):
    assert [s.era for s in planted.stats] == list(panel.ERAS)
    for s in planted.stats:
        assert s.months >= panel.MIN_ERA_MONTHS, s
        assert s.ic_mean is not None and s.ic_mean > 0.0 and s.ic_t > 5.0, s
        assert s.spread_top > 0.0 and s.spread_t > 5.0, s
        assert s.fm_slope > 0.0 and s.fm_t > 5.0, s
        assert s.mean_scored >= panel.MIN_SCORED, s
        assert 0.5 < s.top_turnover <= 1.0, s  # drawn again every month, so the bucket churns


def test_a_null_signal_reads_as_null(frame):
    reading = panel.measure(frame, panel.signal_scorer(HASH_DRAW))
    s = reading.era("all")
    assert s is not None and s.months >= panel.MIN_ERA_MONTHS
    assert abs(s.ic_t) < 4.0, s
    assert abs(s.spread_t) < 4.0, s
    assert abs(s.fm_t) < 4.0, s


def test_the_era_split_puts_each_month_in_exactly_one_era(frame):
    reading = panel.measure(frame, panel.signal_scorer(RECENT))
    whole, before, after = (reading.era(e) for e in panel.ERAS)
    assert whole.months == before.months + after.months
    assert after.fm_t > 5.0, after  # planted from 2009 on
    assert abs(before.fm_t) < 4.0, before  # and not before


def test_picks_mode_reads_a_pick_set_and_shares_its_hash_with_the_matching_score(frame, planted):
    picks = panel.measure(frame, _top10_picks, mode="picks")
    s = picks.era("all")
    assert s.ic_mean is None and s.ic_t is None
    assert s.spread_top > 0.0 and s.spread_t > 5.0, s
    assert s.fm_slope > 0.0 and s.fm_t > 5.0, s
    assert picks.picks_hash == planted.picks_hash


def test_picks_mode_skips_a_month_with_too_few_picks(frame):
    def three(market, pool, data_date):
        return {s: 1.0 for s in sorted(pool)[:3]}

    reading = panel.measure(frame, three, mode="picks")
    assert reading.stats == ()
    assert reading.picks_hash == hashlib.sha256(b"").hexdigest()
    assert reading.dropped_exits == 0


def test_the_picks_hash_is_stable_and_names_the_pick_set(frame, planted):
    assert panel.measure(frame, panel.signal_scorer(PLANTED)) == planted

    def stretched(market, pool, data_date):
        return {s: 2.0 * v + 1.0 for s, v in PLANTED.scores(market, pool, data_date).items()}

    assert panel.measure(frame, stretched).picks_hash == planted.picks_hash
    assert panel.measure(frame, panel.signal_scorer(HASH_DRAW)).picks_hash != planted.picks_hash


def test_the_scorer_sees_only_bars_through_the_data_date_and_within_its_lookback(frame):
    seen: list[tuple[date, date, date, int]] = []

    def probe(history, market, pool, data_date):
        seen.append((
            data_date,
            max(h.dates[-1].item() for h in history.values()),
            max(h.dates[-1].item() for h in market.history.values()),
            max(len(h) for h in history.values()),
        ))
        return {}

    panel.measure(frame, panel.signal_scorer(_planted_signal("S9003", probe, lookback=40)))
    assert len(seen) == len(frame.months)
    for d, last, market_last, longest in seen:
        assert last <= d and market_last <= d and longest <= 40, (d, last, market_last, longest)


def test_scores_outside_the_pool_are_ignored_and_a_non_number_is_refused(frame, planted):
    def noisy(market, pool, data_date):
        out = PLANTED.scores(market, pool, data_date)
        out.update({"SPY": 1e9, "NOT-A-MEMBER": 1e9})
        return out

    assert panel.measure(frame, noisy) == planted

    with pytest.raises(TypeError, match="must be a number"):
        panel.measure(frame, lambda market, pool, data_date: {"N001": "high"})


def test_measure_refuses_an_unknown_mode(frame):
    with pytest.raises(ValueError, match="mode"):
        panel.measure(frame, panel.signal_scorer(HASH_DRAW), mode="ranks")


@pytest.mark.parametrize("scored,size", [(30, 10), (99, 10), (101, 11), (110, 11), (500, 50)])
def test_top_size(scored, size):
    assert panel.top_size(scored) == size
