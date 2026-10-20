"""M0262's session-count gate: the claims the generic kit cannot check.

``test_lab_methods`` already drives every lab allocator through ``allocatorkit`` -- valid targets,
the P4 identity, no look-ahead -- and runs every candidate on a smoke window. A market-aware
allocator is driven there WITHOUT its panel, so the kit never sees this book pick a single name.
These are the properties specific to reading somebody else's gate at a session-count grid:

1. **The session coordinate is the NYSE session count.** Consecutive sessions differ by exactly
   one, and ``session_index`` agrees bar for bar with ``dates.sessions`` over a long span. The
   whole grid is this one integer, so if it is not the session count then every arm reads a date
   nobody intended.
2. **The anchor is PATH-INDEPENDENT.** The anchor computed from a full history equals the anchor
   computed from a lookback-cut history, on every probe date. This is the property that forced the
   grid onto a fixed calendar epoch rather than the idea row's "the symbol's first bar", and it is
   the one claim whose failure would make the same configuration score differently depending on
   which code path ran it. M0261's month-end anchor had to buy this with a two-branch definition;
   this one should get it for free, so it is asserted rather than assumed.
3. **The locked/free split is arithmetic, not a label.** Over the dev window, a 126-session grid
   touches at most a handful of calendar months and a 131-session grid touches all twelve. The
   method's whole design rests on that, and it reads the published exchange calendar only -- no
   store, no price -- so it can be asserted here rather than taken on the prior's word.
4. **The native rung IS the host book**, target for target, on the prepared path with a real
   dividend panel. That is what earns M0262-NATIVE the right to be called a reproduction of
   M0088-C-LIVE-63's recorded row rather than an approximation.
5. **The market-aware contract holds**: driven with no panel, every arm targets nothing.
6. **The overlay declares the host's shape** -- symbols, holds and membership unchanged, and a
   lookback that is the SAME at every rung. Equal lookbacks are what keep every arm scored over
   the same sessions; an arm with its own lookback would be a different window wearing a rung's
   name.
7. **The anchor grid is the one the method file defines**: never later than the data date, and
   always a bar whose ``session_index % period == offset`` unless the documented fallback fired.
8. **At period 1 the anchor IS the data date**, which is why the ladder's fastest rung is the
   native arm and costs no trial.
9. **The lookback covers the worst gap the grid can produce.** ``MAX_GATE_PERIOD`` is derived
   from ``MAX_ANCHOR_GAP`` rather than chosen, and a period that could outrun the lookback is
   refused by the params rather than discovered in a run.
10. **The params round-trip, every arm digests apart, and the period and offset are validated.**
    ``config_text`` reads the rules, the allocator id and the params only, so a dropped field
    would make two arms share one digest and the second would be refused as already run.
11. **Every rung is actually wired in**, and the two maximally-separated pairs really differ: an
    arm that read the same dates as its twin would be a duplicate trial wearing a rung's name.
12. **The fallback never fires silently.** Its exact shape on the smoke fixture is asserted here;
    that it never fires inside the DEV window is the prior's measurement on the real store (zero
    fallbacks at all five anchored arms over all 237 scored sessions).

A dedicated module rather than more cases inside the shared lab tests: the smoke fixture's 473
sessions are a fixed budget every lab method is measured against, and a new method must fit it
rather than stretch it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from labkit import MEMBER_STOCKS, SMOKE_FIRST, smoke_market

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END
from seer_engine.backtest.market import DividendCalendar
from seer_engine.lab.method import config_digest
from seer_engine.lab.methods.m0088_calm_big_raisers import CALM
from seer_engine.lab.methods.m0262_gate_reading_sessions import (
    ADDED,
    BOOK,
    EPOCH_YEAR,
    FREE_PERIOD,
    LADDER,
    LOCKED_PERIOD,
    MAX_ANCHOR_GAP,
    MAX_GATE_PERIOD,
    METHOD,
    SESSIONGATE,
    TREND_N,
    SessionParams,
    offset_anchor,
    session_index,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, is_rank_session

BENCH = "SPY"
MEMBERS = frozenset(MEMBER_STOCKS)
NATIVE = SessionParams(BOOK)

#: A dividend history per member stock that is a LIVE RAISE across the probe window. Carried
#: verbatim from M0261's module, because the two methods share a host and the fixture's job is to
#: make that host pick names rather than to test anything of its own.
RAISES: tuple[tuple[date, str], ...] = (
    (date(2013, 2, 15), "0.10"),
    (date(2013, 7, 15), "0.10"),
    (date(2013, 12, 16), "0.10"),
    (date(2014, 5, 15), "0.10"),
    (date(2014, 10, 15), "0.15"),
    (date(2015, 4, 1), "0.22"),
    (date(2015, 9, 15), "0.33"),
)


@pytest.fixture(scope="module")
def market():
    """The smoke market with a dividend panel, so the calm-raisers book actually picks names."""
    base = smoke_market((BENCH,))
    rows = {s: [(d, Decimal(a)) for d, a in RAISES] for s in MEMBER_STOCKS}
    return base.with_dividends(DividendCalendar(rows))


@pytest.fixture(scope="module")
def bare_market():
    """The smoke market with no dividend panel at all: the market-aware contract's own case."""
    return smoke_market((BENCH,))


def _spy_sessions(market):
    h = market.history[BENCH]
    return [d for d in dates.sessions(SMOKE_FIRST, DEV_END) if h.index_of(d) is not None]


def _decision_data_dates(rules):
    return [dates.prev_session(s) for s in dates.sessions(SMOKE_FIRST, DEV_END)
            if is_rank_session(rules, s)]


def _probe_dates():
    """Dense probe data dates across the fixture's live-raise stretch."""
    lo = date(2014, 10, 20)
    return [dates.prev_session(s) for s in dates.sessions(lo, DEV_END)][::5]


def _anchored():
    """Every arm of the ladder that actually anchors, as (period, offset)."""
    return [(p, o) for _, p, o in LADDER if p is not None]


# ------------------------------------------------------------------ 1. the coordinate
def test_the_session_index_is_the_nyse_session_count():
    """Consecutive sessions differ by one, and the count matches ``dates.sessions`` over 25 years.

    The grid is this integer and nothing else. An off-by-one here would silently relabel every
    offset, which would not break a single assertion about shape and would make the method's rows
    incomparable with the prior whose numbers its hypothesis quotes.
    """
    span = dates.sessions(date(EPOCH_YEAR, 1, 1), date(2015, 10, 16))
    assert session_index(span[0]) == 0
    assert session_index(span[-1]) == len(span) - 1
    for i, d in enumerate(span[::97]):  # a prime stride, so the sample is not a calendar pattern
        assert session_index(d) == span.index(d), d
    idx = [session_index(d) for d in span]
    assert all(b - a == 1 for a, b in zip(idx, idx[1:]))


def test_the_session_index_is_defined_before_the_epoch_rather_than_raising():
    """A pre-epoch bar gets a negative index, and ``%`` still lands it on a rung of the grid.

    No store the lab runs has bars before 1990, but an allocator that raises on a date fails a run
    for a reason that looks like the method, and the method file pays one branch to avoid it.
    """
    before = dates.sessions(date(EPOCH_YEAR - 2, 1, 1), date(EPOCH_YEAR - 1, 12, 31))
    assert session_index(before[-1]) < 0
    assert 0 <= session_index(before[0]) % FREE_PERIOD < FREE_PERIOD


# ------------------------------------------------------------------ 2. path independence
def test_the_anchor_is_the_same_from_a_full_history_and_from_a_lookback_cut(market):
    """The claim that forced the grid onto a fixed epoch rather than "the symbol's first bar".

    The lab hands an allocator a lookback window on the single-symbol path and a full history on
    the prepared one. A grid counted from the first bar of whatever arrived would put the same
    configuration on two different schedules; this grid is counted from the exchange calendar, so
    it cannot. Checked against a cut at the method's own lookback and at a far shorter one.
    """
    h = market.history[BENCH]
    full = h
    for cut in (SESSIONGATE.lookback(NATIVE), 260):
        for d in _probe_dates():
            i = full.index_of(d)
            assert i is not None, d
            window = full.upto(d)
            if len(window) > cut:
                window = type(full)(window.symbol, window.dates[-cut:], window.open[-cut:],
                                    window.high[-cut:], window.low[-cut:], window.close[-cut:],
                                    window.volume[-cut:])
            for period, offset in _anchored():
                a_full = offset_anchor(full, d, period, offset)
                a_cut = offset_anchor(window, d, period, offset)
                if a_full in [x.item() for x in window.dates]:
                    assert a_full == a_cut, (d, period, offset, cut)


# ------------------------------------------------------------------ 3. locked versus free
def test_a_126_session_grid_is_calendar_locked_and_a_131_session_one_is_not():
    """The method's whole design in one assertion, read off the published calendar alone.

    126 is half the dev window's 251.8 sessions a year to within a fifth of a session, so a
    126-session grid does not drift and its readings never leave a handful of months. 131 is
    coprime enough with the trading year to sweep all twelve. No store and no price is read here,
    which is exactly why this is a test and not a measurement.
    """
    span = dates.sessions(date(1994, 1, 1), date(2015, 10, 16))
    for period, want in ((LOCKED_PERIOD, "locked"), (FREE_PERIOD, "free")):
        widest = max(len({d.month for d in span if session_index(d) % period == o})
                     for o in range(period))
        if want == "locked":
            assert widest <= 6, f"period {period} spread over {widest} months: not locked"
        else:
            assert widest == 12, f"period {period} spread over only {widest} months: not free"

    # and the two arms the method actually runs on the locked grid stay inside their own seasons
    for offset in (0, 63):
        months = {d.month for d in span if session_index(d) % LOCKED_PERIOD == offset}
        assert len(months) <= 4, (offset, sorted(months))


# ------------------------------------------------------------------ 4. the reproduction
def test_the_native_rung_is_the_host_book_target_for_target(market):
    """M0262-NATIVE runs M0088's code path, so its targets must be M0088's, date for date."""
    prepared_host = CALM.prepare_market(market)
    prepared_ours = SESSIONGATE.prepare_market(market)
    picked = 0
    for d in _probe_dates():
        want = CALM.targets_prepared(prepared_host, MEMBERS, d, frozenset(), BOOK)
        got = SESSIONGATE.targets_prepared(prepared_ours, MEMBERS, d, frozenset(), NATIVE)
        assert got == want, d
        picked += len(got)
    assert picked > 0, "the fixture never populated the book: the reproduction check is vacuous"


# ------------------------------------------------------------------ 5. the market-aware contract
def test_every_arm_targets_nothing_without_a_dividend_panel(bare_market):
    """Driven with no panel, a market-aware allocator must target nothing -- on every rung."""
    prepared = SESSIONGATE.prepare_market(bare_market)
    for _, period, offset in LADDER:
        params = SessionParams(BOOK, period, offset)
        for d in _probe_dates()[::4]:
            assert SESSIONGATE.targets_prepared(prepared, MEMBERS, d, frozenset(), params) == ()
            assert SESSIONGATE.targets(bare_market.history, MEMBERS, d, frozenset(), params) == ()


# ------------------------------------------------------------------ 6. the declared shape
def test_the_overlay_declares_the_host_books_shape():
    """Symbols, holds and membership are the host's, and the lookback is equal at every rung."""
    looks = set()
    for _, period, offset in LADDER:
        params = SessionParams(BOOK, period, offset)
        assert SESSIONGATE.symbols(params) == CALM.symbols(BOOK)
        assert SESSIONGATE.holds(params) == CALM.holds(BOOK)
        assert SESSIONGATE.uses_members(params) == CALM.uses_members(BOOK)
        looks.add(SESSIONGATE.lookback(params))
    assert len(looks) == 1, f"the rungs are scored over different windows: {sorted(looks)}"
    assert looks == {max(CALM.lookback(BOOK), TREND_N + MAX_ANCHOR_GAP)}
    assert SESSIONGATE.market_fields == CALM.market_fields


# ------------------------------------------------------------------ 7. the grid itself
def test_the_anchor_lands_on_the_grid_and_never_after_the_data_date(market):
    """Every anchor is a bar at or before the data date whose session index is on the grid."""
    h = market.history[BENCH]
    for d in _spy_sessions(market)[::7]:
        for period, offset in _anchored():
            a = offset_anchor(h, d, period, offset)
            assert a <= d, (d, period, offset)
            assert h.index_of(a) is not None, (d, period, offset)
            if a != d or session_index(d) % period == offset:
                assert session_index(a) % period == offset, (d, period, offset, a)


def test_the_anchor_is_never_staler_than_the_period(market):
    """A grid of period p cannot leave an anchor more than p-1 sessions behind, once it resolves.

    This is what ``MAX_GATE_PERIOD`` is derived from, and it is the reason the lookback can be
    stated once rather than measured per arm.
    """
    h = market.history[BENCH]
    for d in _spy_sessions(market)[::7]:
        for period, offset in _anchored():
            a = offset_anchor(h, d, period, offset)
            i, j = h.index_of(a), h.index_of(d)
            assert j is not None and i is not None
            first = session_index(h.dates[0].item())
            resolved = session_index(a) % period == offset
            if resolved:
                assert j - i <= period - 1, (d, period, offset, j - i)
            else:  # the documented fallback, only before the grid's first qualifying session
                assert all(session_index(h.dates[k].item()) % period != offset
                           for k in range(j + 1)), (d, period, offset)
                assert first % period != offset or j == 0


# ------------------------------------------------------------------ 8. the period-1 identity
def test_at_period_one_the_anchor_is_the_data_date(market):
    """Every bar is a grid bar at period 1, so the ladder's fastest rung IS the native arm."""
    h = market.history[BENCH]
    for d in _spy_sessions(market)[::5]:
        assert offset_anchor(h, d, 1, 0) == d


# ------------------------------------------------------------------ 9. the lookback bound
def test_the_slowest_legal_period_still_fits_inside_the_lookback():
    """``MAX_GATE_PERIOD`` is derived from ``MAX_ANCHOR_GAP``, not chosen beside it."""
    assert MAX_GATE_PERIOD == MAX_ANCHOR_GAP + 1
    worst = SessionParams(BOOK, MAX_GATE_PERIOD, MAX_GATE_PERIOD - 1)
    assert SESSIONGATE.lookback(worst) >= TREND_N + (MAX_GATE_PERIOD - 1)
    with pytest.raises(ValueError, match="gate_period must lie"):
        SessionParams(BOOK, MAX_GATE_PERIOD + 1, 0)
    for period, _ in _anchored():
        assert period <= MAX_GATE_PERIOD


# ------------------------------------------------------------------ 10. params and digests
def test_the_params_round_trip_and_validate():
    """Both fields reach ``as_dict``, and every illegal shape is refused at construction."""
    d = SessionParams(BOOK, FREE_PERIOD, 65).as_dict()
    assert d["gate_period"] == str(FREE_PERIOD)
    assert d["gate_offset"] == "65"
    assert d["gate_reads"] == f"every {FREE_PERIOD} sessions, from offset 65"
    assert d["book.vol_n"] == "63" and d["book.side"] == "calm"
    n = NATIVE.as_dict()
    assert n["gate_period"] == n["gate_offset"] == "native"
    assert n["gate_reads"] == "every month end"

    with pytest.raises(ValueError, match="gate_offset must be None"):
        SessionParams(BOOK, None, 3)
    with pytest.raises(ValueError, match="gate_offset must be an int"):
        SessionParams(BOOK, FREE_PERIOD, None)
    with pytest.raises(ValueError, match="gate_offset must lie"):
        SessionParams(BOOK, FREE_PERIOD, FREE_PERIOD)
    with pytest.raises(ValueError, match="gate_offset must lie"):
        SessionParams(BOOK, FREE_PERIOD, -1)
    with pytest.raises(ValueError, match="gate_period must lie"):
        SessionParams(BOOK, 0, 0)
    with pytest.raises(ValueError, match="gate_period must be an int"):
        SessionParams(BOOK, True, 0)
    with pytest.raises(TypeError, match="book must be CalmParams"):
        SessionParams(BOOK.ann, FREE_PERIOD, 0)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="params must be SessionParams"):
        SESSIONGATE.lookback(BOOK)


def test_every_arm_digests_apart_and_the_ladder_matches_the_arms():
    """Six rungs, six digests, and the candidate table is the ladder it says it is."""
    cands = METHOD.candidates
    assert len(cands) == len(LADDER) == 6
    assert len({config_digest(c) for c in cands}) == 6
    for c, (suffix, period, offset) in zip(cands, LADDER):
        assert c.id == f"M0262-{suffix}"
        assert c.rules is MONTHLY_HOLD_FRAC_GOTRADE
        assert c.allocator is SESSIONGATE
        assert c.added == ADDED and c.owner_inputs == ()
        assert c.params == SessionParams(BOOK, period, offset)
        assert c.params.book == BOOK
    assert METHOD.parent_id == "M0261"
    assert {p for _, p, _ in LADDER if p} == {LOCKED_PERIOD, FREE_PERIOD}


# ------------------------------------------------------------------ 11. the rungs really differ
def test_every_rung_moves_the_reading_and_the_two_pairs_differ(market):
    """Each anchored arm reads dates the native arm does not, and each pair's halves disagree."""
    h = market.history[BENCH]
    probe = _decision_data_dates(MONTHLY_HOLD_FRAC_GOTRADE)
    assert probe, "no monthly decision sessions in the smoke window"
    for period, offset in _anchored():
        moved = [d for d in probe if offset_anchor(h, d, period, offset) != d]
        assert moved, (period, offset, "this rung never moves the reading off the data date")
    for period, a, b in ((LOCKED_PERIOD, 0, 63), (FREE_PERIOD, 0, 65)):
        differ = [d for d in probe
                  if offset_anchor(h, d, period, a) != offset_anchor(h, d, period, b)]
        assert differ, (period, a, b, "the pair's halves read identical dates")


# ------------------------------------------------------------------ 12. the fallback
def test_the_fallback_fires_only_before_the_grids_first_qualifying_session(market):
    """The smoke fixture is 473 sessions, so some grids genuinely cannot resolve at its start.

    The fallback returning the data date is documented behaviour, not a silent failure, and this
    pins its exact shape: it fires on the sessions before the grid's first qualifying bar and on
    no others. That it never fires inside the DEV window is the prior's measurement on the real
    store -- zero fallbacks at all five anchored arms over all 237 scored sessions.
    """
    h = market.history[BENCH]
    sess = _spy_sessions(market)
    for period, offset in _anchored():
        first = next((d for d in sess if session_index(d) % period == offset), None)
        fell_back = [d for d in sess
                     if session_index(offset_anchor(h, d, period, offset)) % period != offset]
        if first is None:
            assert fell_back == sess, (period, offset)
        else:
            assert fell_back == [d for d in sess if d < first], (period, offset)
    assert offset_anchor(None, sess[-1], FREE_PERIOD, 0) == sess[-1]
    assert offset_anchor(h, date(1999, 1, 4), FREE_PERIOD, 0) == date(1999, 1, 4)
