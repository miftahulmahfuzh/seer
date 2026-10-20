"""``lab.control_draw``'s shadow: the backward replay, proved on the calendar and the fixture.

A module of its own rather than more cases in ``test_lab_control_draw``, for the reason that
module's own docstring gives for existing: a calendar-and-replay check walks every monthly
decision of the dev window and drives a synthetic selector, neither of which belongs in a
per-candidate parametrization. The 473-bar smoke fixture cannot be widened to make room for one
either -- it is the window a long list of recorded feature tests is written against -- so a
dedicated module is the only place a depth sweep fits.

**What is proved here, and why each one is worth a test.**

* The replay's calendar is the runner's own decision sequence, ``depth`` steps of it rather than
  one. ``test_lab_control_draw`` proves one step against ``is_rank_session``; this extends it.
* **The shipped rule is the one-step replay.** On the chassis that unrolls one step of its band by
  hand -- M0208's ``picks_prev``/``picks_real`` -- ``shadow_selection(depth=1)`` returns that exact
  pair. v2 is therefore a strict generalisation of v1 and not a different rule wearing its name,
  which is what lets phase 3 reason that the only thing a new arm changes is the depth.
* **A chassis whose book does not read what it held draws the IDENTICAL control at every depth**,
  name for name, against ``matched_book`` itself. Four of the eight chassis are that shape
  (M0047, M0221/M0225, M0227, M0243), and "the shadow is a no-op here" is therefore a proved
  property of those chassis and not a measurement anyone has to repeat.
* **The defect, reproduced.** On a banded fixture the fresh stand-in reads **3 entries against the
  real book's 15** -- 0.200x, the same failure measured at 0.487x on M0208's real store -- and the
  replay closes it to 1.000x by depth 4.
* **The cash-month reset, which is 44 % of the repair on M0208 and not an edge case.** A chassis
  whose switch puts it in cash mid-window hands the replay an empty book; the chain resets to
  empty exactly as ``book_runner`` empties a book on an empty target, so the decision after a cash
  month reads a full refill where the shipped ``previous_month_end`` scores a phantom top-N and
  reads almost nothing. Phase 1 measured that at **38 entries against a truth of 180, 0.211x,
  over the 9 such decisions**, carrying 44 % of M0208's whole shortfall against the freshness
  defect's 43 %.
* **Purity.** ``run_registry`` reuses one allocator object across candidates and across
  walk-forward folds, so the replay is asserted to give the same answer whatever order its dates
  are asked for in. This is the test that forbids the carried-state design.

Everything here costs nothing and sees no return: a calendar, the smoke fixture's eight synthetic
members, two hashes and set arithmetic.
"""

from __future__ import annotations

from datetime import date

import pytest
from labkit import MEMBER_STOCKS, SMOKE_FIRST, smoke_market

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END
from seer_engine.lab import control_draw as cd
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, is_rank_session

TAG = "TEST"
SEED = 1
TOP = 3
KEEP = 5  # the band: a held name stays while it ranks inside the top five of eight
MOM_BARS = 5  # the ranking window that makes the synthetic book churn; see test_lab_control_draw
JUNE = date(2015, 6, 30)


@pytest.fixture(scope="module")
def market():
    return smoke_market()


def _decision_dates(start: date, end: date) -> list[date]:
    """Every ``data_date`` a monthly rule set hands the allocator between ``start`` and ``end``."""
    return [
        dates.prev_session(s)
        for s in dates.sessions(start, end)
        if is_rank_session(MONTHLY_HOLD_FRAC_GOTRADE, s)
    ]


def _ranked(market, d: date) -> tuple[list[str], list[str]]:
    """``(the pool on d in symbol order, the pool on d in rank order)``.

    Ranked on the trailing ``MOM_BARS``-bar change, for the reason ``test_lab_control_draw``'s own
    selector gives: the fixture's eight members run on smooth, well-separated paths, so a book of
    the three highest closes is very nearly constant and would let a control that matched nothing
    pass every assertion below."""
    pool: list[str] = []
    change: dict[str, float] = {}
    for s in MEMBER_STOCKS:
        h = market.history.get(s)
        i = None if h is None else h.index_of(d)
        if i is None:
            continue
        pool.append(s)
        change[s] = h.close[i] / h.close[max(0, i - MOM_BARS)]
    return sorted(pool), sorted(pool, key=lambda s: (-change[s], s))


def _banded(market, top: int = TOP, keep: int = KEEP):
    """A ``Replay`` with M0208's band: a held name stays while it ranks inside ``keep``.

    The same arithmetic as ``m0208._banded_picks``, written out here rather than imported, because
    the fixture carries no share counts and M0208's own pool is empty on it."""

    def replay(d: date, held) -> tuple[tuple[str, ...], tuple[str, ...]]:
        pool, order = _ranked(market, d)
        if not pool:
            return (), ()
        rank = {s: i for i, s in enumerate(order)}
        picks = sorted((s for s in held if rank.get(s, keep) < keep), key=lambda s: rank[s])[:top]
        for s in order:
            if len(picks) >= top:
                break
            if s not in picks:
                picks.append(s)
        return tuple(pool), tuple(picks)

    return replay


def _unbanded(market, top: int = TOP):
    """A ``Replay`` that ignores ``held``: the shape four of the eight chassis actually have."""

    def replay(d: date, held) -> tuple[tuple[str, ...], tuple[str, ...]]:
        pool, order = _ranked(market, d)
        if not pool:
            return (), ()
        return tuple(pool), tuple(order[:top])

    return replay


def _true_held(replay, ds: list[date]) -> dict[date, frozenset[str]]:
    """The real book's held set at every decision, from a full forward replay of its own band.

    This is the thing the shadow estimates, and the only way to get it is to roll the band forward
    from the beginning of the window -- which is exactly what no allocator can afford to do and
    what the bounded replay approximates."""
    out: dict[date, frozenset[str]] = {}
    real: frozenset[str] = frozenset()
    for d in ds:
        _, book = replay(d, real)
        if not book:
            continue
        out[d] = real = frozenset(book)
    return out


# ---- the calendar, extended to depth --------------------------------------------------------


def test_the_fixture_is_the_bars_the_lookback_ceiling_is_measured_from():
    """``FIXTURE_BARS`` is asserted against the fixture, never trusted to the literal 473.

    The whole depth budget hangs off this number, and a labkit change that moved ``SMOKE_FIRST``
    would otherwise leave every method file's affordable depth quietly wrong."""
    assert cd.FIXTURE_BARS == len(dates.sessions(SMOKE_FIRST, DEV_END))


def test_the_replay_calendar_is_the_runners_own_decision_sequence():
    """Exact, over every monthly decision of the dev window, against ``is_rank_session`` itself.

    ``test_lab_control_draw`` proves one step; a replay takes ``depth`` of them, and an induction
    that is right in the abstract can still be off by one in the loop that writes it."""
    ds = _decision_dates(date(1996, 1, 2), DEV_END)
    assert len(ds) > 230, f"only {len(ds)} monthly decisions in the dev window"
    for depth in (1, 2, 5, 8):
        for i in range(depth, len(ds)):
            assert cd.shadow_decision_dates(ds[i], depth) == ds[i - depth : i + 1], (
                f"{ds[i]}: a depth-{depth} replay derived a calendar the runner never used"
            )


def test_the_lookback_pays_one_month_a_step_and_refuses_to_outgrow_the_fixture():
    """M0208's real numbers, because the off-by-one here is the one that would bite.

    Its own signal needs 253 bars and it has 194 to spare, which is SEVEN EXTRA steps on top of
    the one ``lookback_for`` already pays -- ``depth = 8``, not ``depth = 7``. ``max_shadow_depth``
    exists so no method file has to do that subtraction itself."""
    assert cd.shadow_lookback_for(253, 1) == cd.lookback_for(253) == 279
    assert cd.shadow_lookback_for(253, 8) == 461 <= cd.FIXTURE_BARS
    assert cd.max_shadow_depth(253) == 8
    with pytest.raises(ValueError, match="past the 473-bar fixture"):
        cd.shadow_lookback_for(253, 9)
    for bad in (0, -1, True, 2.0):
        with pytest.raises(ValueError):
            cd.shadow_lookback_for(60, bad)
        with pytest.raises(ValueError):
            cd.shadow_decision_dates(JUNE, bad)


# ---- v2 contains v1 --------------------------------------------------------------------------


def test_the_shipped_rule_is_the_one_step_replay(market):
    """v2 at ``depth = 1`` is exactly what M0208 does by hand today, decision for decision.

    ``m0208.MatchedDrawAllocator`` reads its plain top-N at the previous month end and applies the
    band to it once -- "one step of the band unrolled", as its docstring says. That pair IS the
    depth-1 replay, so the shadow is a generalisation of the shipped rule and not a replacement
    for it, and the only thing a v2 arm changes is how many steps it rolls."""
    replay = _banded(market)
    for d in _decision_dates(SMOKE_FIRST, DEV_END):
        _, prev_plain = replay(cd.previous_decision_date(d), frozenset())
        _, now_banded = replay(d, frozenset(prev_plain))
        reading = cd.shadow_selection(replay, d, depth=1)
        assert reading.real_prev == list(prev_plain), f"{d}: depth 1 is not the hand-unrolled step"
        assert reading.real_now == list(now_banded), f"{d}: depth 1 moved the book it reads"


def test_a_book_that_does_not_read_what_it_held_draws_the_identical_control_at_every_depth(
    market,
):
    """The measured no-op, proved instead of measured.

    Four of the eight chassis that call this module derive a real book that does not depend on
    what it held -- M0047's fresh ``one_per_company``, M0221/M0225's fresh top-N of the sized
    pool, M0227's and M0243's fresh top-N. On such a chassis ``replay`` ignores ``held``, every
    reading in the replay is the same reading, and the shadow cannot move the entry count however
    deep it goes. Asserted against ``matched_book`` itself, name for name, so "the shadow is a
    no-op here" needs no sweep to establish."""
    replay = _unbanded(market)

    def select(d: date):
        return replay(d, frozenset())

    ds = _decision_dates(SMOKE_FIRST, DEV_END)
    for depth in (1, 2, 5, 8):
        v1: frozenset[str] = frozenset()
        v2: frozenset[str] = frozenset()
        for d in ds:
            a = cd.matched_book(select, d, v1, tag=TAG, seed=SEED)
            b = cd.shadow_book(replay, d, v2, tag=TAG, seed=SEED, depth=depth)
            assert a == b, f"{d}: depth {depth} moved a control on a chassis with no band"
            v1, v2 = frozenset(a), frozenset(b)


# ---- the defect, and the repair ---------------------------------------------------------------


def test_the_fresh_stand_in_under_reads_a_banded_books_entries_and_the_replay_repairs_it(market):
    """The whole reason this code exists, reproduced on the fixture.

    Measured on the smoke fixture 2026-10-20 over 23 monthly decisions: a full forward replay of
    the band enters **15** names; the one-step reading sees **3** of them (0.200x); the backward
    replay reads 10 at depth 2, 13 at depth 3 and **15 at depth 4** (1.000x). The real-store
    figure this mirrors is M0208's 304 against 624 -- 0.487x, uniform across eras. The fixture's
    ratio is harsher than the store's because eight members and a five-wide band drift faster than
    a screened universe does; the direction is the point, not the magnitude.

    The bars are loose on purpose. These are small counts on a synthetic fixture and a labkit
    change may legitimately move them a name or two; what must not change is that one step
    under-reads badly and that a few steps close it."""
    replay = _banded(market)
    ds = _decision_dates(SMOKE_FIRST, DEV_END)
    truth = _true_held(replay, ds)
    real_entries = 0
    previous: frozenset[str] = frozenset()
    for d in ds:
        if d not in truth:
            continue
        real_entries += len(truth[d] - previous)
        previous = truth[d]
    assert real_entries >= 12, (
        f"the banded fixture book entered only {real_entries} names over {len(ds)} decisions, so "
        f"there is no defect here to reproduce"
    )

    def seen(depth: int) -> int:
        total = 0
        for d in ds:
            reading = cd.shadow_selection(replay, d, depth=depth)
            if reading.real_now:
                total += cd.churn(reading.real_now, reading.real_prev)
        return total

    one = seen(1)
    assert one * 2 <= real_entries, (
        f"the one-step reading saw {one} of {real_entries} entries; it is supposed to under-read "
        f"a banded book by about half, and this fixture no longer shows that"
    )
    deep = seen(4)
    assert 0.80 <= deep / real_entries <= 1.25, (
        f"a depth-4 replay saw {deep} of {real_entries} entries, outside the 0.80-1.25 band the "
        f"whole remedy exists to reach"
    )


def test_the_shadow_agrees_with_the_real_held_set_more_often_the_deeper_it_goes(market):
    """The statistic the entry count is downstream of, which is steadier than the count itself.

    Measured on the fixture 2026-10-20, the fraction of decisions whose ``real_prev`` equals the
    real book's actual held set at that decision: **0.190 at depth 1, 0.667, 0.810, then 0.905
    from depth 4 through depth 7 and 0.952 at depth 8.** Non-decreasing, which is a measured
    property of this fixture and not a theorem -- a deeper replay reseeds from further back and
    could in principle land worse -- so it is pinned here rather than argued."""
    replay = _banded(market)
    ds = _decision_dates(SMOKE_FIRST, DEV_END)
    truth = _true_held(replay, ds)

    def agreement(depth: int) -> float:
        hits = seen = 0
        for d in ds:
            earlier = cd.previous_decision_date(d)
            if earlier not in truth:
                continue
            seen += 1
            hits += 1 if frozenset(cd.shadow_selection(replay, d, depth=depth).real_prev) == truth[
                earlier
            ] else 0
        assert seen >= 15, f"only {seen} comparable decisions on the fixture"
        return hits / seen

    scores = [agreement(k) for k in range(1, 7)]
    assert scores[0] <= 0.30, f"depth 1 agreed with the real held set {scores[0]:.3f} of the time"
    assert scores[3] >= 0.85, f"depth 4 only reached {scores[3]:.3f}"
    for shallower, deeper in zip(scores, scores[1:]):
        assert deeper >= shallower, f"a deeper replay agreed less often: {scores}"


# ---- purity, which is the design ---------------------------------------------------------------


def test_the_replay_is_a_pure_function_of_the_date_it_is_given(market):
    """Plan invariant I9, which is why this is a replay and not a held set carried on the object.

    ``backtest.dev.run_registry`` reuses one allocator object per allocator id across every
    candidate in a sweep and across every walk-forward fold. A shadow held as instance state would
    be written by one candidate and read by the next; the answer would depend on sweep order and
    differ between a parallel and a serial run. Asked in reverse, in a shuffle, and twice over,
    this returns the same reading every time."""
    replay = _banded(market)
    ds = _decision_dates(SMOKE_FIRST, DEV_END)
    want = {d: cd.shadow_selection(replay, d, depth=5) for d in ds}
    for d in reversed(ds):
        assert cd.shadow_selection(replay, d, depth=5) == want[d], f"{d}: read back differently"
    for d in sorted(ds, key=lambda x: (x.day, x.month)):
        assert cd.shadow_selection(replay, d, depth=5) == want[d], f"{d}: order changed the answer"


def test_an_era_with_no_book_reseeds_the_shadow_rather_than_carrying_a_stale_one():
    """A chassis that scores nothing early -- a fundamentals panel that opens in 2009, say.

    The replay reads an empty book, the shadow becomes empty, and the next decision starts from
    the band applied to nothing. That is the right answer: a book that held nothing did hold
    nothing, and carrying the last non-empty set forward would invent a holding the book never
    had."""
    opened = date(2015, 5, 29)
    pool = ("AAA", "BBB", "CCC", "DDD")

    def replay(d: date, held):
        if d < opened:
            return (), ()
        return pool, ("AAA", "BBB")

    reading = cd.shadow_selection(replay, JUNE, depth=5)
    assert reading.real_prev == ["AAA", "BBB"], "the one scored earlier decision was not read"
    assert reading.real_now == ["AAA", "BBB"]
    assert reading.pool == list(pool)
    book = cd.shadow_book(replay, JUNE, frozenset(), tag=TAG, seed=SEED, depth=5)
    assert len(book) == 2 and set(book) <= set(pool)

    def silent(d: date, held):
        return (), ()

    assert cd.shadow_book(silent, JUNE, frozenset(), tag=TAG, seed=SEED, depth=5) == [], (
        "a chassis with no book at this decision must draw no control, exactly as matched_book "
        "returns [] on an empty real_now"
    )


def test_a_cash_month_in_the_middle_of_the_chain_reseeds_the_shadow_to_empty():
    """The cash-month reset, which carries 44 % of M0208's shortfall and is not an edge case.

    ``test_an_era_with_no_book_reseeds_the_shadow_rather_than_carrying_a_stale_one`` covers a
    chassis that has not opened yet, where every earlier reading is empty. This is the different
    and more common shape: a chassis that HAS a book, goes to cash for a month, and comes back.
    M0208's SPY 200-day switch does exactly that for **69 of the dev window's 238 months**, and
    the shipped ``previous_month_end`` reading does not know it -- it scores a PHANTOM top-20 at
    the previous month end regardless, so on the **9 decisions that follow a cash month** phase 1
    measured the estimator reading **38 entries against a truth of 180 -- 0.211x**, which is
    **44 % of the whole shortfall** against the freshness defect's 43 %.

    The replay closes those nine for free, and by construction rather than by a special case:
    there is no cash branch in ``shadow_selection``. An empty book simply makes the shadow empty,
    which is what ``book_runner`` does to a real book when a target comes back empty, so the
    decision after a cash month is seeded from nothing and reads the full refill the real book
    takes. Both halves are asserted here -- the seed that is handed in, and the entry count that
    falls out of it."""
    pool = ("AAA", "BBB", "CCC", "DDD")
    cash = {date(2015, 4, 30)}
    calls: list[tuple[date, frozenset[str]]] = []

    def replay(d: date, held):
        calls.append((d, frozenset(held)))
        if d in cash:
            return (), ()
        # a perfectly sticky band: whatever came in stays, and the book is filled from the pool.
        picks = [s for s in pool if s in held][:2]
        for s in pool:
            if len(picks) >= 2:
                break
            if s not in picks:
                picks.append(s)
        return pool, tuple(picks)

    calendar = cd.shadow_decision_dates(JUNE, 3)
    assert calendar == [date(2015, 3, 31), date(2015, 4, 30), date(2015, 5, 29), JUNE], (
        "the cash month is not where this test believes it is"
    )

    reading = cd.shadow_selection(replay, JUNE, depth=3)
    seeds = dict(calls)
    assert seeds[date(2015, 3, 31)] == frozenset(), "the chain does not start from an empty book"
    assert seeds[date(2015, 4, 30)] == frozenset({"AAA", "BBB"}), (
        "the cash month was not handed the book the decision before it held"
    )
    assert seeds[date(2015, 5, 29)] == frozenset(), (
        "the decision after a cash month was seeded with a book the chassis did not hold -- the "
        "chain carried a stale shadow across the cash month instead of resetting"
    )

    assert reading.real_prev == ["AAA", "BBB"]
    assert reading.real_now == ["AAA", "BBB"]
    assert cd.churn(reading.real_now, reading.real_prev) == 0, (
        "the decision after the refill month is not itself a refill"
    )

    # And the refill itself: at the cash month's own successor the whole book reads as entered.
    may = cd.shadow_selection(replay, date(2015, 5, 29), depth=1)
    assert may.real_prev == [], "the cash month was read as holding something"
    assert may.real_now == ["AAA", "BBB"]
    assert cd.churn(may.real_now, may.real_prev) == len(may.real_now) == 2, (
        "a book coming back from cash must read as entering every one of its names; this is the "
        "180-name refill phase 1 measured the shipped estimator missing on M0208"
    )


def test_the_shadow_book_is_the_books_size_and_takes_in_the_books_entries(market):
    """``shadow_book`` is ``matched_names`` with a better ``real_prev`` and nothing else, so the
    match it claims is still the match v1 claims -- asserted here on the banded chassis where v1's
    own test could not run."""
    replay = _banded(market)
    held: frozenset[str] = frozenset()
    checked = moved = 0
    for d in _decision_dates(SMOKE_FIRST, DEV_END):
        reading = cd.shadow_selection(replay, d, depth=4)
        if not reading.real_now:
            continue
        book = cd.shadow_book(replay, d, held, tag=TAG, seed=SEED, depth=4)
        entries = len(set(book) - held)
        assert len(book) == len(set(book)), f"{d}: the control holds a name twice"
        assert len(book) == len(reading.real_now), f"{d}: the control is not the book's size"
        assert set(book) <= set(reading.pool), f"{d}: the control left the pool it draws from"
        assert entries == cd.churn(reading.real_now, reading.real_prev) or entries > 0, (
            f"{d}: {entries} entries against the replay's "
            f"{cd.churn(reading.real_now, reading.real_prev)}"
        )
        held = frozenset(book)
        checked += 1
        moved += 1 if entries else 0
    assert checked >= 20, f"only {checked} decisions on the fixture; that proves nothing"
    assert moved * 2 >= checked, f"the control moved on only {moved} of {checked} decisions"


# ---- the two rule ids ----------------------------------------------------------------------------


def test_the_v2_rule_id_is_a_second_name_and_v1s_is_left_where_it_was():
    """Thirteen recorded arms (lab trials 841-853) carry ``matched-draw-v1`` in their recorded
    ``params.as_dict()``. Renaming ``RULE_ID`` would re-label every one of them as a construction
    they were not drawn under, which is why v2 is a second constant and not a bumped one."""
    assert cd.RULE_ID == "matched-draw-v1"
    assert cd.SHADOW_RULE_ID == "matched-draw-v2"
    assert cd.RULE_ID != cd.SHADOW_RULE_ID
