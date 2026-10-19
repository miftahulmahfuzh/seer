"""``lab.control_draw``: the matched draw, proved on the calendar and on the smoke fixture.

Everything here costs nothing and sees no return. It asserts the two things the rule claims --
that the previous decision date it derives is the one ``book_runner`` actually used, and that the
control it builds enters and exits exactly as many names as the book it controls -- session by
session, before a single backtest is paid for.

A dedicated module rather than more cases inside ``test_lab_methods``: the calendar check walks
every monthly decision of the dev window and the churn check drives a synthetic selector, neither
of which belongs in a per-candidate parametrization.

**Why a synthetic selector and not M0227's real pool.** ``labkit.smoke_market`` carries no share
counts, so ``scored_pool`` is empty on it and both pilot allocators correctly target nothing
there (the market-aware contract: no panel, no targets -- ``test_lab_methods.test_allocator_
contract`` already pins that). The rule's arithmetic does not live in the pool, it lives in the
entry count, so it is driven here through a deliberately churny selector over the smoke fixture's
own symbols. The two method files' own wiring is covered by the allocator contract above and by
the real-store shape probe the phase runs before either ``lab run --amend``.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import date

import pytest
from labkit import MEMBER_STOCKS, SMOKE_FIRST, smoke_market

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END
from seer_engine.lab import control_draw as cd
from seer_engine.lab import control_shape as cs
from seer_engine.lab.hardgate import _INGREDIENT
from seer_engine.lab.method import config_digest
from seer_engine.lab.methods import m0227_net_share_shrinkers as m0227
from seer_engine.lab.methods import m0243_shrinkers_near_high as m0243
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, is_rank_session

TAG = "TEST"
SEED = 1
TOP = 3
MOM_BARS = 5  # the ranking window that makes the synthetic book actually churn; see _selector
SMOKE_BARS = 473  # labkit.SMOKE_FIRST through DEV_END; the lookback cut every lab method clears
POOL = ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF")
JUNE = date(2015, 6, 30)


def _decision_dates(start: date, end: date) -> list[date]:
    """Every ``data_date`` a monthly rule set hands the allocator between ``start`` and ``end``.

    ``book_runner`` ranks on a rank session and calls the allocator with ``prev_session`` of it,
    so this is the real sequence and not a model of one."""
    return [
        dates.prev_session(s)
        for s in dates.sessions(start, end)
        if is_rank_session(MONTHLY_HOLD_FRAC_GOTRADE, s)
    ]


@pytest.fixture(scope="module")
def market():
    return smoke_market()


def _selector(market, top: int = TOP):
    """``select(d)``: the pool is every smoke member with a bar on ``d``; the book is the ``top``
    of them by ``MOM_BARS``-bar price change.

    It ranks on a CHANGE and not on the close itself, and that is the whole point of the fixture.
    ``labkit.smoke_market``'s eight members are generated on smooth, well-separated price paths,
    so a book of the three highest closes is very nearly constant: measured 2026-10-19 it entered
    **8 names over 22 monthly decisions** and moved on a minority of them, which would have let a
    control that matched nothing at all pass every assertion below. Ranking by the trailing
    five-bar change makes the paths cross: **17 entries over the same 22 decisions, moving on 15
    of them, several of those by more than one name.** The guards at the foot of
    ``test_the_control_enters_and_exits_exactly_as_often_as_the_book_it_controls`` pin that, so a
    future fixture change that quietly smooths the book out fails there rather than silently
    making the match free."""

    def select(d: date) -> tuple[tuple[str, ...], tuple[str, ...]]:
        pool = []
        change: dict[str, float] = {}
        for s in MEMBER_STOCKS:
            h = market.history.get(s)
            i = None if h is None else h.index_of(d)
            if i is None:
                continue
            pool.append(s)
            change[s] = h.close[i] / h.close[max(0, i - MOM_BARS)]
        if not pool:
            return (), ()
        ranked = sorted(pool, key=lambda s: (-change[s], s))
        return tuple(sorted(pool)), tuple(ranked[:top])

    return select


# ---- the calendar derivation -------------------------------------------------------------------


def test_previous_decision_date_is_the_previous_decisions_own_data_date():
    """Exact, over every monthly decision of the dev window, against ``is_rank_session`` itself.

    This is the half of the rule that is pure arithmetic on the published NYSE calendar: if it is
    right here it is right in the backtest, because the backtest builds the same sequence."""
    ds = _decision_dates(date(1996, 1, 2), DEV_END)
    assert len(ds) > 230, f"only {len(ds)} monthly decisions in the dev window"
    for earlier, later in zip(ds, ds[1:]):
        assert cd.previous_decision_date(later) == earlier, (
            f"{later}: derived {cd.previous_decision_date(later)}, the runner used {earlier}"
        )


def test_the_previous_decision_is_never_further_back_than_the_lookback_allows():
    """``PREVIOUS_DECISION_BARS`` is measured here, not trusted to the 23-session month."""
    ds = _decision_dates(date(1996, 1, 2), DEV_END)
    widest = max(len(dates.sessions(cd.previous_decision_date(d), d)) for d in ds)
    assert widest <= cd.PREVIOUS_DECISION_BARS, (
        f"a matched draw reaches back {widest} sessions, past PREVIOUS_DECISION_BARS "
        f"{cd.PREVIOUS_DECISION_BARS}"
    )
    assert cd.lookback_for(60) == 60 + cd.PREVIOUS_DECISION_BARS
    with pytest.raises(ValueError):
        cd.lookback_for(0)


def test_only_the_monthly_cadence_is_derived():
    with pytest.raises(ValueError):
        cd.previous_decision_date(JUNE, "weekly")


# ---- the churn match, session by session ---------------------------------------------------------


def test_the_control_enters_and_exits_exactly_as_often_as_the_book_it_controls(market):
    """The rule's whole claim, asserted on every monthly decision the smoke fixture carries."""
    select = _selector(market)
    held: frozenset[str] = frozenset()
    real_held: frozenset[str] = frozenset()
    checked = 0
    churn = 0
    moved = 0
    for d in _decision_dates(SMOKE_FIRST, DEV_END):
        pool, real_now = select(d)
        if not real_now:
            continue
        book = cd.matched_book(select, d, held, tag=TAG, seed=SEED)
        real_entries = len(set(real_now) - real_held)
        real_exits = len(real_held - set(real_now))
        entries = len(set(book) - held)
        exits = len(held - set(book))
        assert len(book) == len(set(book)), f"{d}: the control holds a name twice"
        assert len(book) == len(real_now), f"{d}: the control is not the book's size"
        assert set(book) <= set(pool), f"{d}: the control left the pool it draws from"
        assert entries == real_entries, f"{d}: {entries} entries against the book's {real_entries}"
        assert exits == real_exits, f"{d}: {exits} exits against the book's {real_exits}"
        held, real_held = frozenset(book), frozenset(real_now)
        checked += 1
        churn += real_entries
        moved += 1 if real_entries else 0
    assert checked >= 20, f"only {checked} decisions on the fixture; that proves nothing"
    # The anti-vacuity guards. A control that matched nothing would still pass every assertion
    # above if the book it controls never moved, so the fixture itself has to be shown to churn.
    # Measured on the smoke fixture 2026-10-19: 22 decisions, 17 entries, 16 of them on 15 moving
    # decisions. The eight-member universe caps entries below one per decision whatever the
    # ranking, so the bar is a moving MAJORITY of decisions plus at least one multi-name move --
    # not a count per decision, which this fixture cannot reach.
    assert moved * 2 >= checked, (
        f"the synthetic book moved on only {moved} of {checked} decisions, so the match came "
        f"close to free"
    )
    assert churn > moved, (
        f"{churn} entries over {moved} moving decisions: every move was a single name, so the "
        f"multi-entry arithmetic was never exercised"
    )


def test_an_empty_held_set_fills_the_whole_book(market):
    """The kickoff: the control holds nothing, so it enters as many names as the real book does
    on its own first decision, whatever ``e`` happens to be."""
    select = _selector(market)
    d = _decision_dates(SMOKE_FIRST, DEV_END)[6]
    book = cd.matched_book(select, d, frozenset(), tag=TAG, seed=SEED)
    assert len(book) == len(select(d)[1]) == TOP


# ---- the arithmetic, stated as cases --------------------------------------------------------------


def test_entries_are_the_real_books_entries_when_nothing_leaves_the_pool():
    held = frozenset({"AAA", "BBB", "CCC"})
    book = cd.matched_names(pool=POOL, held=held, real_now=("X1", "X2", "X3"),
                            real_prev=("X1", "X4", "X5"), tag=TAG, seed=SEED, data_date=JUNE)
    assert len(book) == 3
    assert len(set(book) - held) == 2  # the real book entered two, so the control enters two
    assert len(held - set(book)) == 2


def test_a_still_book_moves_the_control_not_at_all():
    held = frozenset({"AAA", "BBB", "CCC"})
    book = cd.matched_names(pool=POOL, held=held, real_now=("X1", "X2", "X3"),
                            real_prev=("X1", "X2", "X3"), tag=TAG, seed=SEED, data_date=JUNE)
    assert set(book) == held


def test_a_held_name_that_left_the_pool_forces_one_more_entry():
    """``entries == max(e, a)``: the one residual the module docstring names, pinned as a case."""
    held = frozenset({"AAA", "BBB", "CCC"})
    thinner = tuple(s for s in POOL if s != "AAA")
    book = cd.matched_names(pool=thinner, held=held, real_now=("X1", "X2", "X3"),
                            real_prev=("X1", "X2", "X3"), tag=TAG, seed=SEED, data_date=JUNE)
    assert "AAA" not in book and len(book) == 3
    assert len(set(book) - held) == 1  # e is 0, attrition is 1, so entries is 1


def test_a_dropped_holding_is_never_re_taken_ahead_of_a_fresh_name():
    """The tail ordering, which is a contract and not a detail (phase 5 depends on it).

    The control drops ``held`` names it is not keeping. Those names are still in the pool, so a
    naive fill would take the one with the lowest entry key straight back -- and then the realised
    entry count is below ``e``, the trade ratio sags under 1.00, and every assertion about book
    SIZE still passes. ``matched_partition`` puts every name the control does not hold ahead of
    every name it is dropping, so this cannot happen while the pool has a fresh name left."""
    held = frozenset({"AAA", "BBB", "CCC"})
    keep, tail = cd.matched_partition(pool=POOL, held=held, keep_n=1,
                                      tag=TAG, seed=SEED, data_date=JUNE)
    assert len(keep) == 1 and set(keep) <= held
    assert sorted(keep + tail) == sorted(POOL)                  # a partition, exactly once each
    dropped = held - set(keep)
    fresh = set(POOL) - held
    assert set(tail[: len(fresh)]) == fresh, "a dropped holding sorted ahead of a fresh name"
    assert set(tail[len(fresh):]) == dropped
    assert tail[: len(fresh)] == sorted(
        fresh, key=lambda s: (cd.entry_key(TAG, SEED, s, JUNE), s)
    )


def test_the_book_drawn_from_the_partition_takes_no_dropped_name_back():
    """``matched_names`` is built from ``matched_partition``, so it inherits the guarantee."""
    held = frozenset({"AAA", "BBB", "CCC"})
    book = cd.matched_names(pool=POOL, held=held, real_now=("X1", "X2", "X3"),
                            real_prev=("X1",), tag=TAG, seed=SEED, data_date=JUNE)
    assert len(book) == 3
    assert len(set(book) - held) == 2, "the real book entered two, so the control enters two"
    assert len(set(book) & held) == 1


def test_churn_is_the_entry_count_and_nothing_else():
    assert cd.churn(("X1", "X2", "X3"), ("X1", "X4")) == 2
    assert cd.churn(("X1",), ("X1",)) == 0
    assert cd.churn((), ("X1",)) == 0
    assert cd.churn(("X1", "X2"), ()) == 2


def test_the_control_reads_only_the_size_and_the_entry_count_of_the_book_it_controls():
    """Signal-blind by construction: two completely different real books with the same size and
    the same entry count produce the identical control."""
    common = dict(pool=POOL, held=frozenset({"AAA"}), tag=TAG, seed=SEED, data_date=JUNE)
    a = cd.matched_names(real_now=("X1", "X2", "X3"), real_prev=("X1", "X9"), **common)
    b = cd.matched_names(real_now=("Y7", "Y8", "Y9"), real_prev=("Y7", "Y4"), **common)
    assert a == b and len(a) == 3


def test_an_empty_book_or_an_empty_pool_draws_nothing():
    assert cd.matched_names(pool=POOL, held=frozenset(), real_now=(), real_prev=("X1",),
                            tag=TAG, seed=SEED, data_date=JUNE) == []
    assert cd.matched_names(pool=(), held=frozenset({"AAA"}), real_now=("X1",), real_prev=(),
                            tag=TAG, seed=SEED, data_date=JUNE) == []


# ---- the two hashes ------------------------------------------------------------------------------


def test_the_keep_hash_is_date_free_and_the_entry_hash_turns_with_the_month():
    """The two poles each used one hash for both jobs. These are the two jobs."""
    keep = cd.keep_key(TAG, SEED, "AAA")
    assert keep == cd.keep_key(TAG, SEED, "AAA")
    assert keep != cd.keep_key(TAG, SEED, "BBB")
    assert keep != cd.keep_key("OTHER", SEED, "AAA")
    assert keep != cd.keep_key(TAG, SEED + 1, "AAA")
    jun_a, jun_b, jul = date(2015, 6, 1), JUNE, date(2015, 7, 31)
    assert cd.entry_key(TAG, SEED, "AAA", jun_a) == cd.entry_key(TAG, SEED, "AAA", jun_b)
    assert cd.entry_key(TAG, SEED, "AAA", jun_a) != cd.entry_key(TAG, SEED, "AAA", jul)
    assert cd.entry_key(TAG, SEED, "AAA", jun_a) != keep


def test_one_tag_draws_one_book_so_a_twin_pair_can_share_it():
    """Phase 3's M0221/M0225 twins pass the same tag on purpose; this is why that works."""
    assert cd.keep_key("M0221", 1, "AAA") == cd.keep_key("M0221", 1, "AAA")
    assert cd.keep_key("M0221", 1, "AAA") != cd.keep_key("M0225", 1, "AAA")


# ---- the two pilot arms ---------------------------------------------------------------------------


def _arm(method, cid):
    return next(c for c in method.all_candidates() if c.id == cid)


@pytest.mark.parametrize("module,control_id,target_id", [
    (m0227, "M0227-S20-PLC", "M0227-S20"),
    (m0243, "M0243-NEAR20-PLC", "M0243-NEAR20"),
])
def test_each_redrawn_control_reads_as_a_placebo_on_the_arm_it_means_to_control(
    module, control_id, target_id
):
    """D17 classifies by prose, and it tests dose BEFORE draw. A re-drawn control that read as a
    dose-response arm would carry no ratio at all and its refusal would vanish without the
    handicap going anywhere; that is gaming the check and this is the test that forbids it."""
    arms = list(module.METHOD.all_candidates())
    control = _arm(module.METHOD, control_id)
    text = control.rationale.lower()
    assert cs.kind_of(control) == cs.KIND_PLACEBO
    assert any(m in text for m in cs.DRAW_MARKERS)
    assert not any(m in text for m in cs.DOSE_MARKERS)
    assert cs.resolve_target(control, arms) == (target_id, cs.RUNG_STEM)


def test_the_two_new_allocators_are_new_ids_and_name_no_ingredient():
    r"""``hardgate._INGREDIENT`` is ``<(M\d{4})>``, so ``<M0227-A1>`` matches nothing and D12's
    ingredient map is exactly what it was. A four-digit id would have made every matched-draw arm
    declare its own method an ingredient of itself."""
    assert m0227.MATCHED.id == "M0227-A1"
    assert m0243.MATCHED_NEAR.id == "M0243-A1"
    assert m0227.ISSUANCE.id == "M0227" and m0243.NEAR_SHRINK.id == "M0243"
    for text in ("allocator=<M0227-A1>", "allocator=<M0243-A1>"):
        assert _INGREDIENT.findall(text) == []


def test_the_matched_draw_allocators_reach_back_one_extra_month_and_still_fit_the_fixture():
    cases = (
        (m0227.MATCHED, m0227.IssuanceParams(20, side="random", seed=1), m0227.DV_N),
        (m0243.MATCHED_NEAR, m0243.NearShrinkParams(20, pick="random", seed=1), m0243.HIGH_N),
    )
    for allocator, params, inner in cases:
        assert allocator.lookback(params) == cd.lookback_for(inner)
        assert allocator.lookback(params) <= SMOKE_BARS


def test_the_amendment_added_no_field_to_the_params_the_recorded_arms_use():
    """Plan invariant 1, pinned where a sibling phase will copy it. ``registry._canon`` renders a
    dataclass by ``dataclasses.fields()``, so one more field on either of these moves every
    recorded ``config_digest`` that used it."""
    assert [f.name for f in fields(m0227.IssuanceParams)] == ["top", "side", "seed", "trend"]
    assert [f.name for f in fields(m0243.NearShrinkParams)] == [
        "top", "cut", "side", "pick", "seed", "trend"
    ]
    assert m0227.SIDES == ("shrink", "issue", "random")
    assert m0243.PICKS == ("shrink", "random")


def test_each_new_arm_reuses_the_params_value_of_the_arm_it_replaces():
    """The set's one params rule: no new dataclass anywhere, the allocator id is the difference.

    A new arm whose params value equals the replaced arm's is the cheapest thing that can possibly
    be a new configuration, and it keeps nine method files from inventing nine ways to say the
    same thing. ``config_text`` differs on the ``allocator=`` line alone, which is enough for both
    ``Method.__post_init__`` and ``trials``' ``UNIQUE(config_digest, window)``."""
    for module, new_id, old_id in ((m0227, "M0227-S20-PLC", "M0227-R20"),
                                   (m0243, "M0243-NEAR20-PLC", "M0243-NEAR20-R")):
        new = _arm(module.METHOD, new_id)
        old = _arm(module.METHOD, old_id)
        assert type(new.params) is type(old.params)
        assert new.params == old.params, f"{new_id} must reuse {old_id}'s params value"
        assert new.allocator.id != old.allocator.id
        assert config_digest(new) != config_digest(old)
    assert not hasattr(m0227, "MatchedParams"), "no new params dataclass: reuse, do not mint"
    assert not hasattr(m0243, "MatchedNearParams")


def test_each_new_arm_declares_the_arm_it_supersedes():
    """D17's supersession is DECLARED, never inferred from target equality, so an arm that
    declares nothing retires nothing and the method stays blocked. The ids come from the plan
    index's supersession mapping; a typo here is an import-time error, which is the reason this
    is a validated field on ``Candidate`` and not a phrase in prose."""
    assert _arm(m0227.METHOD, "M0227-S20-PLC").supersedes == ("M0227-R20",)
    assert _arm(m0243.METHOD, "M0243-NEAR20-PLC").supersedes == ("M0243-NEAR20-R",)
    for module in (m0227, m0243):
        for c in module.METHOD.candidates:
            assert c.supersedes == (), f"{c.id}: an original arm declares nothing"


def test_the_supersedes_field_is_outside_every_recorded_digest():
    """The whole mechanism rests on this: ``config_text`` and ``candidate_text`` name their fields
    by hand and nothing passes a whole ``Candidate`` to ``registry._canon``, so a declaration can
    never move a recorded ``config_digest``. Asserted rather than argued."""
    from dataclasses import replace as dc_replace

    from seer_engine.lab.method import config_text

    c = _arm(m0227.METHOD, "M0227-S20-PLC")
    assert config_text(dc_replace(c, supersedes=())) == config_text(c)
    assert config_digest(dc_replace(c, supersedes=("M0227-S20",))) == config_digest(c)
    assert "supersedes" not in config_text(c)


def test_each_pilot_method_carries_exactly_one_amendment_of_one_arm():
    for module, cid in ((m0227, "M0227-S20-PLC"), (m0243, "M0243-NEAR20-PLC")):
        amendments = module.METHOD.amendments
        assert len(amendments) == 1
        assert amendments[0].added == date(2026, 10, 19)
        assert [c.id for c in amendments[0].candidates] == [cid]
        assert len(module.METHOD.candidates) == 5
        assert len(module.METHOD.all_candidates()) == 6
