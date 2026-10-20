"""M0261's phased gate: the claims the generic kit cannot check.

``test_lab_methods`` already drives every lab allocator through ``allocatorkit`` -- valid targets,
the P4 identity, no look-ahead -- and runs every candidate on a smoke window. A market-aware
allocator is driven there WITHOUT its panel, so the kit never sees this book pick a single name.
These are the properties specific to reading somebody else's gate at a phased month-end grid:

1. **The generalisation agrees with the original.** ``phase_anchor(h, d, k, k - 1)`` is M0260's
   frozen ``gate_anchor(h, d, k)`` on every session of the tape at every rung. M0260's ladder is
   this method's four phase-``k-1`` arms, and if the two anchors ever disagreed those arms would
   be lookalikes rather than rungs, and the generalisation test would be comparing two different
   things across two different books.
2. **The native rung IS the host book**, target for target, on the prepared path with a real
   dividend panel. That is what earns M0261-NATIVE the right to be called a reproduction of
   M0088-C-LIVE-63's recorded row rather than an approximation.
3. **The market-aware contract holds**: driven with no panel, every arm targets nothing. The kit
   asserts this for the registry; asserting it here too keeps the overlay honest if the host's
   empty-calendar guard ever moves.
4. **The overlay declares the host's shape** -- symbols, holds and membership unchanged, and a
   lookback that is the SAME at every rung. Equal lookbacks are what keep every arm scored over
   the same sessions; an arm with its own lookback would be a different window wearing a rung's
   name.
5. **The anchor grid is the one the method file defines**: never later than the data date, and
   always a calendar month end whose ``month_index % k == phase`` unless the documented fallback
   fired.
6. **On a monthly book the one-month anchor IS the data date**, at phase 0. This is why the
   ladder's zero rung is the native arm and costs no trial.
7. **The nesting identity.** The quarterly grid is exactly the union of the two half-yearly
   grids, so the quarterly arm's anchor is always whichever half-yearly anchor is NEWER. The
   method's fourth prediction -- a quarterly reading losing to BOTH of its own halves -- is only
   a paradox if this holds, so it is asserted rather than argued.
8. **The params round-trip, every arm digests apart, and the phase is validated.** ``config_text``
   reads the rules, the allocator id and the params only, so a dropped field would make two arms
   share one digest and the second would be refused as already run.
9. **Every rung is actually wired in**, and the two phase pairs really differ: an arm that read
   the same dates as its twin would be a duplicate trial wearing a rung's name.
10. **The fallback never fires silently.** The smoke fixture's 473 sessions are about two years,
    so a twelve-month anchor genuinely cannot resolve at the start of it. Its exact shape is
    asserted here; that it never fires inside the DEV window is the prior grid's measurement on
    the real store (zero fallbacks at all 21 (k, phase) pairs over all 237 scored sessions).

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
from seer_engine.lab.methods.m0260_gate_reading_cadence import gate_anchor
from seer_engine.lab.methods.m0260_gate_reading_cadence import month_index as m0260_month_index
from seer_engine.lab.methods.m0261_gate_reading_phase import (
    ADDED,
    BOOK,
    LADDER,
    MAX_ANCHOR_GAP,
    MAX_GATE_MONTHS,
    METHOD,
    PHASEGATE,
    TREND_N,
    PhaseParams,
    month_index,
    months_read,
    phase_anchor,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, is_rank_session

BENCH = "SPY"
MEMBERS = frozenset(MEMBER_STOCKS)
NATIVE = PhaseParams(BOOK)
KS = (1, 3, 6, 12)

#: A dividend history per member stock that is a LIVE RAISE across the probe window.
#:
#: ``live_event`` reads only the newest payment on or before the data date, and ``classify`` calls
#: it a raise when it is 25% to 100% above the median of the up-to-four payments that went ex in
#: the 400 days before it. The flat 0.10 run sets that median; each later payment is a raise over
#: the two that precede it inside its own 400-day window, and the 182-day hold then keeps the book
#: populated from 2014-10-15 to the end of the fixture. Without this the whole book is empty and
#: the reproduction check below would compare two empty tuples and prove nothing.
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
    """Every smoke session SPY has a bar for, which on this fixture is all 473 of them."""
    h = market.history[BENCH]
    return [d for d in dates.sessions(SMOKE_FIRST, DEV_END) if h.index_of(d) is not None]


def _is_month_end(h, d):
    """True when the bar dated ``d`` is the last bar of its calendar month in ``h``."""
    i = h.index_of(d)
    assert i is not None, d
    nxt = h.dates[i + 1].item() if i + 1 < len(h) else dates.next_session(d)
    return (nxt.year, nxt.month) != (d.year, d.month)


def _decision_data_dates(rules):
    """``prev_session(S)`` for every rank session S of ``rules`` inside the smoke window."""
    return [dates.prev_session(s) for s in dates.sessions(SMOKE_FIRST, DEV_END)
            if is_rank_session(rules, s)]


def _probe_dates():
    """Dense probe data dates across the fixture's live-raise stretch.

    Dense rather than M0260's every-fortieth-session sample because this book is only populated
    once an event is live AND the gate is open, and a sparse sample can land entirely on sessions
    where both arms are empty -- which would make the reproduction check vacuous.
    """
    lo = date(2014, 10, 20)
    return [dates.prev_session(s) for s in dates.sessions(lo, DEV_END)][::5]


# ------------------------------------------------------------------ 1. the generalisation
def test_the_phase_anchor_generalises_m0260s_frozen_anchor(market):
    """``phase_anchor(h, d, k, k - 1)`` IS M0260's ``gate_anchor(h, d, k)``, bar for bar.

    M0260's four monthly rungs are this method's four phase-``k-1`` arms, and the whole
    generalisation test rests on them being the same reading on a different book. Asserted against
    the frozen original rather than restated, so the claim cannot drift as this file is edited.
    An import would prove only that the names resolve; this proves the arithmetic agrees.
    """
    h = market.history[BENCH]
    sessions = _spy_sessions(market)
    assert len(sessions) > 400, "the smoke fixture shrank; this check needs a tape to walk"
    for k in (1, 2, 3, 6, 12):
        for d in sessions:
            assert phase_anchor(h, d, k, k - 1) == gate_anchor(h, d, k), (k, d)


def test_the_month_index_is_m0260s(market):
    """The grid's month index is the same integer M0260 counts in, on a long span of dates."""
    d = date(1970, 1, 1)
    while d <= date(2026, 12, 1):
        assert month_index(d) == m0260_month_index(d), d
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)


# ------------------------------------------------------------------ 2. the reproduction
def test_the_native_rung_is_the_host_book_target_for_target(market):
    """At ``gate_months = None`` M0261 equals M0088-C-LIVE-63, on the panel-fed path.

    The generic kit checks each allocator against ITSELF and never against another allocator, so
    nothing in it can tell a reproduction from a near miss -- and for a market-aware allocator the
    kit never even sees a non-empty target. This is what earns M0261-NATIVE the right to be read
    as trial 289's row run again, which is the zero rung every paired difference is measured from.
    """
    host = CALM.prepare_market(market)
    mine = PHASEGATE.prepare_market(market)
    seen = 0
    for d in _probe_dates():
        for held in (frozenset(), frozenset(MEMBER_STOCKS[:3])):
            want = CALM.targets_prepared(host, MEMBERS, d, held, BOOK)
            got = PHASEGATE.targets_prepared(mine, MEMBERS, d, held, NATIVE)
            assert got == want, (d, sorted(held))
            seen += len(want)
    assert seen > 0, "every probe was empty, so the reproduction check proved nothing"


# ------------------------------------------------------------------ 3. the market-aware contract
def test_every_arm_targets_nothing_without_a_dividend_panel(bare_market):
    """Driven with no panel, every arm targets nothing -- the market-aware allocator's contract.

    ``test_lab_methods`` asserts this for the registry at large. Asserting it here as well keeps
    the overlay honest if the host's empty-calendar guard, which this file copies line for line,
    ever moves: a rung that started picking names off a missing panel would be reading nothing at
    all and calling it a book.
    """
    prepared = PHASEGATE.prepare(bare_market.history)
    for k, phase in LADDER:
        p = PhaseParams(BOOK, k, phase)
        for d in _probe_dates()[::4]:
            assert PHASEGATE.targets(bare_market.history, MEMBERS, d, frozenset(), p) == ()
            assert PHASEGATE.targets_prepared(prepared, MEMBERS, d, frozenset(), p) == ()


# ------------------------------------------------------------------ 4. the declared shape
def test_the_overlay_declares_the_host_books_shape(market):
    """Symbols, holds and membership are M0088's at every rung, and the lookback is one number.

    The generic kit calls ``lookback`` but never compares one params value's against another's,
    and a ladder whose rungs had different lookbacks would be scored over different windows --
    every paired difference the method reports would then be partly a window difference. The
    lookback is deliberately NOT the host's 253: it must cover a twelve-month anchor plus its
    200-bar average, which the method file's prior measured at 234 sessions of gap.
    """
    want = PHASEGATE.lookback(NATIVE)
    assert want == max(CALM.lookback(BOOK), TREND_N + MAX_ANCHOR_GAP)
    assert want > CALM.lookback(BOOK), "a 12-month anchor needs more than the host's lookback"
    assert want <= 473, "the smoke fixture is 473 sessions; a wider lookback cannot be scored"
    for k, phase in LADDER:
        p = PhaseParams(BOOK, k, phase)
        assert PHASEGATE.lookback(p) == want, (k, phase)
        assert PHASEGATE.symbols(p) == CALM.symbols(BOOK), (k, phase)
        assert PHASEGATE.holds(p) == CALM.holds(BOOK), (k, phase)
        assert PHASEGATE.uses_members(p) is CALM.uses_members(BOOK), (k, phase)


# ------------------------------------------------------------------ 5. the grid
def test_the_anchor_grid_is_a_phased_month_end_grid(market):
    """Every resolved anchor is a month end on the (k, phase) grid, never later than the date.

    Nothing in ``allocatorkit`` knows this method has an anchor at all; it perturbs bars and
    checks targets. This walks the grid directly, on every session of the tape and at every phase
    of every rung the method runs, because the phase is the whole instrument.
    """
    h = market.history[BENCH]
    sessions = _spy_sessions(market)
    for k in (3, 6, 12):
        for phase in range(k):
            resolved = 0
            for d in sessions:
                a = phase_anchor(h, d, k, phase)
                assert a <= d, (k, phase, d, a)
                if a == d and not (_is_month_end(h, d) and month_index(d) % k == phase):
                    continue  # the documented fallback; its shape is asserted separately
                assert _is_month_end(h, a), (k, phase, d, a)
                assert month_index(a) % k == phase, (k, phase, d, a)
                resolved += 1
            assert resolved > 0, f"k={k} phase={phase}: the anchor never resolved"


# ------------------------------------------------------------------ 6. the zero rung
def test_on_a_monthly_book_the_one_month_anchor_is_the_data_date(market):
    """``phase_anchor(h, data_date, 1, 0) == data_date`` on every monthly decision session.

    This identity is why the ladder's zero rung is the NATIVE arm and costs no trial: a monthly
    book's ``data_date`` is ``prev_session(first session of month M)``, which is always the last
    session of month M-1. Nothing in the generic kit checks a relationship between the allocator
    and the rule set it will be run under, and this one is load-bearing.
    """
    h = market.history[BENCH]
    checked = 0
    for d in _decision_data_dates(MONTHLY_HOLD_FRAC_GOTRADE):
        assert phase_anchor(h, d, 1, 0) == d, d
        checked += 1
    assert checked >= 20, "too few monthly decision sessions on the fixture to prove the identity"


# ------------------------------------------------------------------ 7. the nesting identity
def test_the_quarterly_grid_is_the_union_of_the_two_half_yearly_grids(market):
    """``Q-MJSD``'s anchor is always the NEWER of ``H-JD``'s and ``H-MS``'s.

    The months 2, 5, 8, 11 split exactly into {5, 11} = Jun/Dec and {2, 8} = Mar/Sep, so the
    quarterly arm reads both half-yearly phases and nothing else. The method's fourth prediction
    -- a quarterly reading losing to BOTH of its own halves despite being the fresher reading at
    every moment -- is a paradox only if this holds, so it is asserted rather than argued.

    Sessions where either half-yearly anchor fell back are skipped and counted: the fallback
    genuinely fires at the head of a 473-session fixture, and the prior grid is what establishes
    that it never fires inside the dev window.
    """
    h = market.history[BENCH]
    checked = 0
    for d in _spy_sessions(market):
        a_jd = phase_anchor(h, d, 6, 5)
        a_ms = phase_anchor(h, d, 6, 2)
        if a_jd == d or a_ms == d:
            continue  # a fallback: the identity is about resolved anchors
        assert phase_anchor(h, d, 3, 2) == max(a_jd, a_ms), d
        checked += 1
    assert checked > 300, "too few resolved sessions to call the nesting identity proved"


# ------------------------------------------------------------------ 8. params and digests
def test_the_params_round_trip_and_validate():
    """``as_dict`` renders the rung a human reads, and an illegal phase is refused outright."""
    assert NATIVE.as_dict()["gate_months"] == "native"
    assert NATIVE.as_dict()["gate_phase"] == "native"
    assert NATIVE.as_dict()["gate_reads"] == "every month end"
    d = PhaseParams(BOOK, 6, 5).as_dict()
    assert (d["gate_months"], d["gate_phase"], d["gate_reads"]) == ("6", "5", "Jun/Dec")
    assert PhaseParams(BOOK, 6, 2).as_dict()["gate_reads"] == "Mar/Sep"
    assert PhaseParams(BOOK, 12, 11).as_dict()["gate_reads"] == "Dec"
    assert PhaseParams(BOOK, 3, 2).as_dict()["gate_reads"] == "Mar/Jun/Sep/Dec"
    assert months_read(1, 0).count("/") == 11
    for bad in (
        dict(gate_months=None, gate_phase=0),   # a phase with no interval
        dict(gate_months=6, gate_phase=None),   # an interval with no phase
        dict(gate_months=6, gate_phase=6),      # out of the residue class
        dict(gate_months=6, gate_phase=-1),
        dict(gate_months=0, gate_phase=0),
        dict(gate_months=MAX_GATE_MONTHS + 1, gate_phase=0),
        dict(gate_months=True, gate_phase=0),   # a bool is not an interval
        dict(gate_months=6, gate_phase=True),
    ):
        with pytest.raises((ValueError, TypeError)):
            PhaseParams(BOOK, **bad)


def test_every_arm_digests_apart_and_the_ladder_matches_the_arms():
    """Six arms, six digests, and the committed ladder is exactly what the arms run."""
    digests = {config_digest(c) for c in METHOD.candidates}
    assert len(digests) == len(METHOD.candidates) == 6
    assert tuple((c.params.gate_months, c.params.gate_phase) for c in METHOD.candidates) == LADDER
    for c in METHOD.candidates:
        assert c.rules is MONTHLY_HOLD_FRAC_GOTRADE, c.id
        assert c.params.book == BOOK, c.id
        assert c.added == ADDED, c.id
        assert "dose-response" in c.rationale, c.id  # D17 reads the arm's own prose


# ------------------------------------------------------------------ 9. the rungs are real
def test_every_rung_moves_the_reading_and_the_phase_pairs_differ(market):
    """Each anchored rung reads somewhere the native one does not, and twins read apart.

    Without this an arm could be wired to the data date through a silent fallback and look like a
    rung while running the native gate under another name -- and, worse for this method, the two
    arms of a phase pair could read identical dates and record a duplicate trial wearing two
    names. The pair check is the one that matters: the phase IS the experiment.
    """
    h = market.history[BENCH]
    sessions = _spy_sessions(market)
    for k, phase in LADDER:
        if k is None:
            continue
        moved = sum(1 for d in sessions if phase_anchor(h, d, k, phase) != d)
        assert moved > len(sessions) // 2, (k, phase, moved)
    for k, a, b in ((6, 5, 2), (12, 11, 5)):
        apart = sum(1 for d in sessions
                    if phase_anchor(h, d, k, a) != phase_anchor(h, d, k, b))
        assert apart > len(sessions) // 2, (k, a, b, apart)


# ------------------------------------------------------------------ 10. the fallback
def test_the_fallback_fires_only_before_the_grids_first_qualifying_month_end(market):
    """On the smoke fixture the fallback fires, and only where the grid cannot yet resolve.

    The fixture opens 2013-12-02, so a December-only grid resolves almost at once while a June-only
    grid cannot resolve until 2014-06-30. Asserting the exact shape here is what lets the method
    file claim, on the prior grid's authority, that it never fires inside the dev window: the two
    statements are about the same code and only the tape differs.
    """
    h = market.history[BENCH]
    sessions = _spy_sessions(market)
    for k, phase in LADDER:
        if k is None:
            continue
        fell_back = [d for d in sessions if phase_anchor(h, d, k, phase) == d
                     and not (_is_month_end(h, d) and month_index(d) % k == phase)]
        if not fell_back:
            continue
        first_ok = min((d for d in sessions
                        if _is_month_end(h, d) and month_index(d) % k == phase), default=None)
        assert first_ok is not None, (k, phase)
        assert max(fell_back) < first_ok, (k, phase, max(fell_back), first_ok)
    jun_only = [d for d in sessions if phase_anchor(h, d, 12, 5) == d
                and not (_is_month_end(h, d) and month_index(d) % 12 == 5)]
    assert jun_only, "a June-only grid must fall back at the head of a fixture opening in December"
    assert max(jun_only) < date(2014, 7, 1), max(jun_only)
