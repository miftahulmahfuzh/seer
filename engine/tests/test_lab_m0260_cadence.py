"""M0260's anchored gate: the claims the generic kit cannot check.

``test_lab_methods`` already drives every lab allocator through ``allocatorkit`` -- valid targets,
the P4 identity, no look-ahead -- and runs every candidate on a smoke window. These are the
properties specific to reading somebody else's gate at a date earlier than the data date:

1. **The native rung IS the host book**, target for target, on both the history-only and the
   prepared path. That is what earns the right to call M-NATIVE a reproduction of M0258-M-B0 (and
   so of M0072-Z2-RAWRANK) rather than an approximation, and it is why the decomposition's A end is
   a recorded row the lab can be held to.
2. **The overlay declares the host's shape** -- symbols, holds and membership unchanged, and a
   lookback that is the SAME at every rung. Equal lookbacks are what keep every arm scored over the
   same sessions; an arm with its own lookback would be a different window wearing a rung's name.
3. **The anchor grid is the one the method file defines**: never later than the data date, and
   always a calendar month end whose ``month_index % k == k - 1`` unless the documented fallback
   fired.
4. **On a monthly book the k = 1 anchor IS the data date.** This identity is why the ladder's
   fastest rung is the native arm and costs no trial. If it ever broke, the ladder would have a
   silent hole at its fast end.
5. **The decomposition identity.** On a weekly rule set, the k = 1 anchor is the same month-end
   session a monthly rule set read in that month. This is what makes ``A - C`` pure re-pick
   frequency instead of an approximation of it.
6. **The params round-trip and every arm digests apart.** ``config_text`` reads the rules, the
   allocator id and the params only, so a dropped field would make two arms share one digest and
   the second would be refused as already run.
7. **Every rung is actually wired in.** Each k must move the gate's reading somewhere on the tape,
   or an arm that looks like a rung is running the native gate under another name.
8. **The fallback never fires silently.** The smoke fixture's 473 sessions are about two years, so
   a twelve-month anchor genuinely cannot resolve at the start of it. Its exact shape is asserted
   here; that it never fires inside the DEV window is phase 1's measurement on the real store
   (k = 12 unresolvable on the first 233 sessions, all before 1993-12-31, against a window that
   opens on 1996-01-03).

A dedicated module rather than more cases inside the shared lab tests: the smoke fixture's 473
sessions are a fixed budget every lab method is measured against, and a new method must fit it
rather than stretch it.
"""

from __future__ import annotations

from datetime import date

import pytest
from labkit import MEMBER_STOCKS, SMOKE_FIRST, smoke_market

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END, Candidate
from seer_engine.lab.method import config_digest
from seer_engine.lab.methods.m0063_earnings_day_jump import WEEKLY_HOLD_FRAC_GOTRADE
from seer_engine.lab.methods.m0072_standardised_earnings_jump import ZJUMP
from seer_engine.lab.methods.m0260_gate_reading_cadence import (
    ADDED,
    G1,
    G3,
    G6,
    G12,
    LADDER,
    MAX_ANCHOR_GAP,
    MAX_GATE_MONTHS,
    SLOWGATE,
    BOOK,
    CadenceParams,
    gate_anchor,
    month_index,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, is_rank_session
from seer_engine.strategies.f_factor import trend_on

BENCH = "SPY"
SMA_N = 200
MEMBERS = frozenset(MEMBER_STOCKS)
PROBES = dates.sessions(date(2014, 12, 1), DEV_END)[::40]
NATIVE = CadenceParams(BOOK)
KS = (G1, 2, G3, G6, G12)


@pytest.fixture(scope="module")
def market():
    return smoke_market((BENCH,))


def _spy_sessions(market):
    """Every smoke session SPY has a bar for, which on this fixture is all 473 of them."""
    h = market.history[BENCH]
    return [d for d in dates.sessions(SMOKE_FIRST, DEV_END) if h.index_of(d) is not None]


def _is_month_end(h, d):
    """True when the bar dated ``d`` is the last bar of its calendar month in ``h``."""
    i = h.index_of(d)
    assert i is not None, d
    if i + 1 < len(h):
        nxt = h.dates[i + 1].item()
    else:
        nxt = dates.next_session(d)
    return (nxt.year, nxt.month) != (d.year, d.month)


def _decision_data_dates(rules):
    """``prev_session(S)`` for every rank session S of ``rules`` inside the smoke window."""
    return [dates.prev_session(s) for s in dates.sessions(SMOKE_FIRST, DEV_END)
            if is_rank_session(rules, s)]


def test_the_native_rung_is_the_host_book_target_for_target(market):
    """At ``gate_months = None`` M0260 equals M0072-Z2-RAWRANK, on both paths, at every probe.

    The generic kit checks each allocator against ITSELF -- the P4 identity and look-ahead -- and
    never against another allocator, so nothing in it can tell a reproduction from a near miss.
    This is what earns M-NATIVE the right to be read as M0258-M-B0's row run again, which is the A
    end of the decomposition the whole method reports.
    """
    prepared_host = ZJUMP.prepare(market.history)
    prepared_slow = SLOWGATE.prepare(market.history)
    seen = 0
    for session in PROBES:
        d = dates.prev_session(session)
        for held in (frozenset(), frozenset(MEMBER_STOCKS[:2]) & frozenset(market.history)):
            host = ZJUMP.targets(market.history, MEMBERS, d, held, BOOK)
            slow = SLOWGATE.targets(market.history, MEMBERS, d, held, NATIVE)
            host_p = ZJUMP.targets_prepared(prepared_host, MEMBERS, d, held, BOOK)
            slow_p = SLOWGATE.targets_prepared(prepared_slow, MEMBERS, d, held, NATIVE)
            assert slow == host, (d, sorted(held))
            assert slow_p == host_p == host, (d, sorted(held))
            seen += len(host)
    assert seen > 0, "every probe was empty, so the comparison proved nothing"


def test_the_overlay_declares_the_host_books_shape(market):
    """Symbols, holds and membership are M0072's at every rung, and the lookback is one number.

    The generic kit calls ``lookback`` but never compares one params value's against another's, and
    a ladder whose rungs had different lookbacks would be scored over different windows -- every
    paired difference the method reports would then be partly a window difference. The lookback is
    deliberately NOT the host's 253: it must cover a twelve-month anchor plus its 200-bar average,
    which is measured in the method file's docstring.
    """
    want = SLOWGATE.lookback(NATIVE)
    assert want == max(ZJUMP.lookback(BOOK), SMA_N + MAX_ANCHOR_GAP)
    assert want > ZJUMP.lookback(BOOK), "a 12-month anchor needs more than the host's lookback"
    for k in (None,) + KS:
        p = CadenceParams(BOOK, k)
        assert SLOWGATE.lookback(p) == want, k
        assert SLOWGATE.symbols(p) == ZJUMP.symbols(BOOK), k
        assert SLOWGATE.holds(p) == ZJUMP.holds(BOOK), k
        assert SLOWGATE.uses_members(p) is ZJUMP.uses_members(BOOK), k


def test_the_anchor_grid_is_a_phased_month_end_grid(market):
    """Every resolved anchor is a month end on the k-grid, and never later than the data date.

    Nothing in ``allocatorkit`` knows this method has an anchor at all; it perturbs bars and checks
    targets. This walks the grid directly, on every session of the tape and every rung, because the
    grid's phase (``% k == k - 1``) is the whole reason k = 3 means calendar quarters rather than
    whichever month the tape happened to start in.
    """
    h = market.history[BENCH]
    sessions = _spy_sessions(market)
    assert len(sessions) > 400, "the smoke fixture shrank; this check needs a tape to walk"
    for k in KS:
        resolved = 0
        for d in sessions:
            a = gate_anchor(h, d, k)
            assert a <= d, (k, d, a)
            if a == d and not (_is_month_end(h, d) and month_index(d) % k == k - 1):
                continue  # the documented fallback; its shape is asserted separately
            assert _is_month_end(h, a), (k, d, a)
            assert month_index(a) % k == k - 1, (k, d, a)
            resolved += 1
        assert resolved > len(sessions) // 2, f"k={k}: the anchor almost never resolved"


def test_on_a_monthly_book_the_k1_anchor_is_the_data_date(market):
    """``gate_anchor(h, data_date, 1) == data_date`` on every monthly decision session.

    This identity is why the ladder's fastest rung is the NATIVE arm and costs no trial: a monthly
    book's ``data_date`` is ``prev_session(first session of the month)``, which is always the last
    session of the previous month. Nothing in the generic kit checks a relationship between the
    allocator and the rule set it will be run under, and this one is load-bearing.
    """
    h = market.history[BENCH]
    checked = 0
    for d in _decision_data_dates(MONTHLY_HOLD_FRAC_GOTRADE):
        assert gate_anchor(h, d, G1) == d, d
        checked += 1
    assert checked >= 20, "too few monthly decision sessions on the fixture to prove the identity"


def test_the_weekly_k1_anchor_is_the_monthly_books_own_reading(market):
    """On a weekly rule set the k = 1 anchor is the month-end session a monthly book read.

    This is the whole claim behind ``(A - C)`` being pure re-pick frequency: arm C does not
    approximate arm A's gate reading, it reuses the identical session. Asserted against the set of
    data dates a MONTHLY rule set actually produces, so the two arms are compared through the
    simulator's own calendar rather than through a restatement of it.
    """
    h = market.history[BENCH]
    monthly = _decision_data_dates(MONTHLY_HOLD_FRAC_GOTRADE)
    monthly_set = set(monthly)
    checked = 0
    for d in _decision_data_dates(WEEKLY_HOLD_FRAC_GOTRADE):
        a = gate_anchor(h, d, G1)
        if a == d and d not in monthly_set:
            continue  # the fallback, before the tape's first month end
        assert a in monthly_set, (d, a)
        newest = max(m for m in monthly if m <= d)
        assert a == newest, (d, a, newest)
        checked += 1
    assert checked >= 40, "too few weekly decision sessions resolved to prove the identity"


def test_the_params_round_trip_and_every_arm_digests_apart():
    """``as_dict`` carries every field, and each of the six arms is its own configuration."""
    p = CadenceParams(BOOK, G3)
    rendered = p.as_dict()
    assert set(rendered) == {"gate_months"} | {f"book.{k}" for k in BOOK.as_dict()}
    assert rendered["gate_months"] == "3"
    assert all(isinstance(v, str) for v in rendered.values())
    for k, v in BOOK.as_dict().items():
        assert rendered[f"book.{k}"] == v
    assert CadenceParams(BOOK).as_dict()["gate_months"] == "native"
    assert CadenceParams(BOOK, G12).as_dict()["gate_months"] == "12"

    def candidate(suffix, gate_months, rules):
        return Candidate(id=f"M0260-{suffix}", family="M0260", rules=rules, allocator=SLOWGATE,
                         params=CadenceParams(BOOK, gate_months), rationale="a rung", added=ADDED,
                         owner_inputs=())

    digests = {
        config_digest(candidate("M-NATIVE", None, MONTHLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("M-G3", G3, MONTHLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("M-G6", G6, MONTHLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("M-G12", G12, MONTHLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("W-NATIVE", None, WEEKLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("W-G1", G1, WEEKLY_HOLD_FRAC_GOTRADE)),
    }
    assert len(digests) == 6, "two arms share a configuration digest"
    assert LADDER == (None, G3, G6, G12)


def test_every_rung_actually_moves_the_gate(market):
    """Each k changes the gate's reading somewhere on the tape, or it is the native gate renamed.

    A rung whose anchor always landed on the data date would record a trial that looks like a dose
    and is the control. The gate is compared through ``trend_on`` at the anchor against ``trend_on``
    at the data date, which is exactly the one line the allocator replaces.
    """
    h = market.history[BENCH]
    inner = BOOK.jump.inner
    sessions = _spy_sessions(market)
    for k in KS:
        moved = sum(
            1 for d in sessions
            if trend_on(market.history, gate_anchor(h, d, k), inner)
            != trend_on(market.history, d, inner)
        )
        assert moved > 0, f"k={k} never differs from the native reading on the smoke tape"


def test_the_fallback_fires_only_before_the_first_qualifying_month_end(market):
    """The fallback's shape is asserted, not assumed: it fires only where no anchor can exist.

    The smoke fixture is 473 sessions, about two years, so a twelve-month grid genuinely has no
    qualifying bar at the start of it. That is a property of a two-year fixture and not of the dev
    window: on the real store the k = 12 anchor is unresolvable on the first 233 sessions only,
    every one of them before 1993-12-31, against a dev window that opens on 1996-01-03 -- phase 1's
    probe. The lookback is NOT widened further to make this go away: the smoke fixture's 473
    sessions are a fixed budget every lab method is measured against.
    """
    h = market.history[BENCH]
    sessions = _spy_sessions(market)
    for k in KS:
        qualifying = [d for d in sessions if _is_month_end(h, d) and month_index(d) % k == k - 1]
        assert qualifying, f"k={k}: the fixture holds no qualifying month end at all"
        first = qualifying[0]
        for d in sessions:
            a = gate_anchor(h, d, k)
            if d < first:
                assert a == d, f"k={k}: expected the fallback on {d}, got {a}"
            else:
                assert a <= d and a >= first, (k, d, a)
                assert _is_month_end(h, a) and month_index(a) % k == k - 1, (k, d, a)
    # k = 12 is the rung that genuinely falls back on this fixture; k = 1 never does.
    assert all(gate_anchor(h, d, G1) <= d for d in sessions)
    assert any(gate_anchor(h, d, G12) == d and not _is_month_end(h, d) for d in sessions)
    # No history at all, and a data date the symbol has no bar for, both fall back to the date.
    probe = sessions[len(sessions) // 2]
    assert gate_anchor(None, probe, G12) == probe


def test_the_params_refuse_what_they_say_they_refuse():
    """The validator is part of the pre-registration: a reading outside [1, 12] is not this method."""
    with pytest.raises(ValueError):
        CadenceParams(BOOK, 0)
    with pytest.raises(ValueError):
        CadenceParams(BOOK, MAX_GATE_MONTHS + 1)
    with pytest.raises(ValueError):
        CadenceParams(BOOK, -1)
    with pytest.raises(ValueError):
        CadenceParams(BOOK, True)  # a bool is an int in Python and is not a reading interval
    with pytest.raises(ValueError):
        CadenceParams(BOOK, 3.0)  # a float, not an int
    with pytest.raises(TypeError):
        CadenceParams(object(), G3)
    with pytest.raises(TypeError):
        SLOWGATE.lookback(BOOK)
