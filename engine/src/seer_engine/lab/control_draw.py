"""The matched draw: a control arm shaped like the book it controls, derived and not tuned.

A lab method proves its signal by beating a control -- a blind draw from the same pool, in the
same frame, at the same fees -- and the sentence "it beat the blind draw by N points" is worth
exactly as much as that match. ``lab.control_shape`` made the match measurable on 2026-10-19 and
the first reading was bad: thirteen control arms across nine dev-eligible methods sit outside
D17's 0.50-2.00 refuse band, and they fail in two opposite directions.

**The two poles, and why they are one error.** ``M0227-R20`` draws its twenty names in a hash
order of (seed, symbol) with no date in the key, so its book changes only when the scored pool
does: it traded **41 times in nineteen years**, 0.07x the arm it controls, and under-paid almost
the whole fee bill. ``M0243-NEAR20-R`` is the overcorrection, and M0243's own file says so out
loud: *"M0227's own placebo used a sticky hash order and traded 41 times in twenty years, failing
the trade-count condition; this one is redrawn each month, so it turns over like the book it
controls for."* It is redrawn every month and traded **3872 times**, 3.01x its arm, over-paying
by three. The same author, reading the same failure, corrected it by hand and shot past the
target. The hand-chosen re-key period is the bug; the direction of the correction never was.

**Why the lab's existing best is still not a match.** ``M0241``'s ``placebo_book`` has the right
instinct -- count how many eligible members really entered in each trailing month, then draw that
many names in a hash order seeded on that month -- and its docstring claims the turnover matches
too. Measured, it lands at **1.372x trades and 1.131x turnover**: outside the 0.80-1.25 band this
module exists to hit. It reconstructs *cohorts*, which is a model of how the real book enters.
This module reads the real book's entries directly instead, which needs no model.

**The rule, in one sentence.** At each decision the control recomputes the arm it controls, today
and at the previous decision, counts the names that arm is adding (``e``), keeps all but ``e`` of
its own names in a date-free hash order, and draws ``e`` fresh ones from the same eligible pool in
a hash order seeded on this month. Its book is the real book's size; its entries are the real
book's entries; its names are a hash.

**Why that is matched by construction rather than by calibration.** There is no constant to turn.
``e`` and the book size are read off the real arm's own calendar at run time. A book of fixed size
that takes in ``e`` names must let ``e`` go, so the trade ratio is ~1.00 arithmetically. The
turnover ratio follows from the trade ratio because the control is weighted exactly as the arm it
controls is: equal slots of the same count move the same fraction of the book per name.

**The two hashes, one for each job.** A date-free hash of (tag, seed, symbol) -- M0227's, which
got persistence right and freshness wrong -- decides **who stays**. A month-keyed hash of (tag,
seed, symbol, month) -- M0187's, which M0243 imports, and which got freshness right and
persistence wrong -- decides **who enters**. Neither pole was wrong about its own half.

**The one residual, stated rather than assumed.** A control name can leave the eligible pool, and
then it must go whatever ``e`` says. The control's entries are ``max(e, a)`` where ``a`` is its own
pool attrition, while the real arm's ``e`` already contains the real arm's attrition. A ranked book
and a blind one hold different names and so shed them at slightly different rates, and that
difference is the whole gap between this rule and a ratio of exactly 1.00. It is measured by
``lab control`` after every application, never asserted here.

**Why the fresh names sort ahead of the dropped ones, and why that is a guarantee and not a
detail.** ``matched_partition`` returns ``(keep, tail)``, and ``tail`` is every pool name the
control did not keep -- the names it does **not** hold first, in the month-keyed entry order,
and only then the holdings it is letting go. Put the dropped holdings anywhere earlier and the
first thing the draw does with its ``e`` free slots is take back a name it just released: the
realised entry count falls below ``e``, the trade ratio sags under 1.00, and the rule quietly
stops matching while every test about *sizes* still passes. Only when the fresh half of the pool
is exhausted does a dropped holding come back, which is the pool-attrition residual above and not
a different failure. ``matched_names`` fills its book from this same partition, so the book and
the partition can never disagree about who is fresh.

**What was considered and is the named fallback.** A fixed symbol-to-symbol permutation sigma over
the universe, scoring X by the real score of sigma(X), inherits a real name's entry and exit
behaviour exactly and costs one selection instead of two. It is the fallback and not the rule
because its pool thins wherever sigma(X) is unscorable that day, which is a different frame, and
because its match is statistical rather than constructive. A date-free permutation applied by rank
POSITION inside the day's pool is not that fallback: it collapses straight back to the sticky draw.

**What this module may never be used for.** It shapes a control; it never phrases one. A re-drawn
arm's ``rationale`` carries a ``control_shape.DRAW_MARKERS`` phrase ("placebo", "hash-drawn",
"hash order") and none of ``DOSE_MARKERS``. ``control_shape.kind_of`` tests dose BEFORE draw, so
calling a control a dose-response arm makes D17's refusal vanish while leaving the handicap in
place. That is gaming the check, not passing it, and it is forbidden outright.

**The shadow (v2, 2026-10-20), and the half of the match this rule was shipped without.** The
reading above is honest about where the entry count comes from and quietly wrong about what it
measures. ``matched_book`` asks ``select`` for the controlled arm twice, and on a chassis whose
real book has a KEEP BAND -- a held name stays while it still ranks inside a wider threshold --
the earlier reading is a FRESHLY DERIVED top-N, because no allocator holds a record of what the
arm it controls actually held. A fresh top-20 is ranked 1 through 20 and M0208's band only drops
a name past rank 40, so almost nothing falls out of it. A real held set has been drifting toward
that edge for months and falls out far faster. Measured over all 169 of M0208's decisions on the
real store: the fresh stand-in reads **304 entries against the real book's 624 -- 0.487x, uniform
across eras** (0.444 / 0.509 / 0.500); the 624 is the figure the close-out recorded, and the RATIO
is the finding -- an entry count and a trade count are not the same quantity and the recorded
``trials.trades`` is also 624, so phase 1's forward replay is what settles the absolute. The
control then enters half as many names as the book it controls, pool attrition drags the realised
figure back to 0.73x trades and 0.76x turnover, and
the sentence M0208 publishes about its own margin is quoted against an opponent paying three
quarters of the fee bill. It is a floor, not a measurement, and its own verdict says so.

**The repair is a bounded backward replay, and the module keeps both rules.** ``shadow_selection``
starts ``depth`` decisions back with the band applied to an EMPTY book -- which is the plain
top-N, exactly the fresh stand-in -- and rolls the chassis's own band forward one decision at a
time. After ``depth - 1`` rolls the shadow carries ``depth - 1`` months of accumulated drift and
stands at the previous decision, which is what ``real_prev`` wanted all along; one more
application gives ``real_now``, and ``matched_names`` does v1's arithmetic on the pair unchanged.
At ``depth = 1`` the replay IS the shipped rule, decision for decision, so v2 contains v1 rather
than competing with it. On a chassis whose book does not read what it held -- M0047's fresh
``one_per_company``, M0221/M0225's and M0227's and M0243's fresh top-N, four of the eight -- every
reading in the replay is the same reading and the shadow is provably a no-op at any depth.

**And it is not only a freshness fix: it closes the CASH-MONTH convention for free.** Measured by
phase 1 on the real store, 2026-10-20. M0208's SPY 200-day switch holds the real book in cash for
**69 of the dev window's 238 months**, and ``previous_month_end`` does not know that -- it scores
a PHANTOM top-20 at the previous month end regardless, so on the **9 decisions that follow a cash
month** the shipped estimator measures churn against a book that never existed and reads **38
entries where the truth is a full 180-name refill, 0.211x**. Those nine decisions carry **44 % of
M0208's whole shortfall**, against 43 % for the freshness defect the shadow was proposed for and
13 % for the membership convention no depth closes. The replay fixes the cash months at no extra
cost and by construction rather than by a special case: ``replay`` hands back an empty book, the
shadow becomes empty, and the next decision starts from the band applied to nothing -- which is
exactly what the book engine does when a target comes back empty.

**Why a replay and not a held set carried forward on the allocator**, which is the obvious design
and the wrong one. ``backtest.dev.run_registry`` reuses ONE allocator object per allocator id
across every candidate in a sweep and across every walk-forward fold. An attribute holding "what
the real book held last month" would be written by one candidate and read by the next, and by fold
3 while fold 1 was still being scored: the answer would depend on sweep order, differ between a
sweep and a single run, and differ between a parallel pytest and a serial one. The replay holds
its shadow in a local and nowhere else, so it is a pure function of the dates it is given and can
be asked for any decision in any order. It costs ``depth + 1`` passes of the controlled arm's own
ranking per decision where the shipped rule pays 2, and ``depth * PREVIOUS_DECISION_BARS`` of
lookback -- bounded by ``FIXTURE_BARS``, which ``shadow_lookback_for`` refuses to exceed rather
than handing back a number no test can drive.

**What the shadow is NOT, stated because the next reader will assume it is.** It is a NAME rule
and it moves the entry count only. Turnover on a chassis that weights its names by anything other
than equal slots is a property of the weight VECTOR and is not in name space at all:
``M0221-E50`` holds ``M0221-C50``'s exact fifty names and records its exact 360 trades and still
turns over 1.60x. No depth of replay reaches that, and a deeper one will not either. The weight
axis is a second rule on a second axis, it lives in ``control_weight``, and nothing in this module
ever touches a weight.

**Both constructions stay, and the recorded arms keep theirs.** v1's functions are not edited --
not refactored, not shared, not re-blessed. Thirteen recorded arms (lab trials 841-853) ran under
them and a module body is outside ``config_digest``, so an edit here would move all thirteen
without failing a single digest test. ``test_lab_control_draw``'s golden vector is what makes such
an edit go red; it pins a fixed input to a fixed output and it is the only test in the tree that
would catch one.

Pure: a calendar, two hashes, set arithmetic and a bounded replay of a band the caller owns. No
clock, no randomness, no store, no database, and no state held anywhere between calls.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from collections.abc import Set as AbstractSet
from datetime import date, datetime
from typing import NamedTuple

from seer_engine import dates

RULE_ID = "matched-draw-v1"
"""Stamped into a matched-draw arm's ``params.as_dict()`` so a reader of a recorded trial can tell
which construction drew it. It is reporting only: ``as_dict`` is not part of ``config_digest``
(``registry._canon`` enumerates ``dataclasses.fields()``), so bumping it moves no recorded digest
-- but it names a different control, so a bump belongs with a new arm, never with an edit."""

CADENCES: tuple[str, ...] = ("monthly",)
"""The rank cadences ``previous_decision_date`` can derive. Every method this rule was built for
runs ``monthly-hold-frac-gotrade``. A weekly or daily book needs its own derivation and must add
it here with its own test rather than passing the monthly one a date it does not fit."""

PREVIOUS_DECISION_BARS = 26
"""Extra bars a matched-draw allocator's lookback needs on top of its own.

The draw reads the arm it controls at the previous decision as well as at this one, so the history
it is handed must reach its own lookback back from THERE. The widest calendar month the NYSE has
is 23 sessions; one more covers the bar at the previous decision itself, and two spare mean a
holiday-calendar revision cannot silently shorten a lookback years after a trial was recorded.
``test_lab_control_draw`` measures the real maximum over the whole dev window rather than trusting
the 23. Widening costs nothing: ``backtest.dev.candidate_window`` floors a member-reading
candidate's start at ``MEMBERSHIP_START`` (1996-01-02) and these allocators declare only SPY,
whose store history opens in 1993, so the trial's window does not move."""

Select = Callable[[date], tuple[Sequence[str], Sequence[str]]]
"""``select(d) -> (the eligible pool on d, the controlled arm's own book on d)``.

Both come from the arm being controlled, computed the way that arm computes them, from the same
prepared data. The caller closes over ``prepared`` and ``members``; see ``matched_book``."""


def _as_plain_date(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    return d


def keep_key(tag: str, seed: int, symbol: str) -> int:
    """Who stays: a date-free 64-bit hash of (tag, seed, symbol).

    M0227's own ``draw``, generalised by ``tag``. Date-free on purpose -- the order a name is kept
    in must not change between decisions, or the control would churn for a reason the book it
    controls never has. ``tag`` is the book's method id, so two twins of one book (M0221 and
    M0225) can be given the SAME tag and draw the same names, which is the only way a
    before-and-after on a data repair measures the repair."""
    key = f"{tag}|keep|{seed}|{symbol}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")


def entry_key(tag: str, seed: int, symbol: str, data_date: date) -> int:
    """Who enters: a 64-bit hash of (tag, seed, symbol, the decision's calendar month).

    M0187's ``draw``, generalised by ``tag``. Keyed on the month rather than the day so two
    decisions inside one month -- which a monthly rule set does not make, but a kickoff session
    can -- draw the same entrants and do not churn on the calendar alone."""
    d = _as_plain_date("data_date", data_date)
    key = f"{tag}|enter|{seed}|{symbol}|{d.year:04d}-{d.month:02d}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")


def churn(now: Sequence[str], prev: Sequence[str]) -> int:
    """How many names the controlled arm ENTERED at this decision: ``len(set(now) - set(prev))``.

    One line, in one place, because three method files need the number and nothing else of the
    rule, and a count computed two ways is a count that will eventually disagree with itself."""
    return len(set(now) - set(prev))


def previous_decision_date(data_date: date, cadence: str = "monthly") -> date:
    """The ``data_date`` of the decision before the one being made at ``data_date``.

    ``book_runner`` ranks on a rank session S and hands the allocator ``prev_session(S)``
    (``sim.rules.is_rank_session``; ``backtest/book_runner.py:368,393-403``). Under a monthly
    cadence S is the first NYSE session of a calendar month, so ``data_date`` is the last session
    of the month before it, and the previous decision read the last session of the month before
    THAT -- which is exactly the last session strictly before the first calendar day of
    ``data_date``'s own month. That is what this returns, off the published NYSE calendar and
    nothing else. ``test_lab_control_draw`` checks it against ``is_rank_session`` itself on every
    monthly decision of the dev window, 1996-2015.

    **It is the previous MONTHLY decision, and that is the right answer for a chassis whose
    basket actually moves every month.** M0047's residual arms are such a chassis, and the brief
    that set this plan set going got them wrong: ``REPICK_MONTHS`` and ``KEEP_PCT`` appear in
    ``m0047`` only inside ``placebo_order`` (:189-202), and the residual arms take a fresh
    ``one_per_company(order, 20)`` at every monthly decision (:244-248). The quarterly band there
    is the handicap being removed, not a property to reproduce, so M0047's control matches the
    monthly churn and this function is what it calls.

    **It is the wrong answer for a chassis whose basket only moves on a slower clock, and such a
    chassis must not call this.** M0201 and M0202 share M0197's book: ``_run`` sets
    ``repick = not stocks or data_date.month in REPICK_MONTHS`` and passes an empty ``frac`` on
    every other month, so the allocator is *called* monthly but the basket only *moves*
    quarterly, behind a 40% keep band. There is no monthly entry count on that chassis to match.
    Phase 5 therefore derives its own previous re-pick in its own method files, and measured
    0.955 of the real book's entries over the dev window's 79 re-picks doing so. That derivation
    is chassis-specific and stays out of this module on purpose; ``CADENCES`` is the list of
    cadences this function will answer for, and a quarterly basket is not one of them.

    The one session this is approximate on is the kickoff, which ``book_runner`` ranks whether or
    not it opens a month: there ``data_date`` can sit mid-month and this answers the previous
    month-end, a few sessions early. It costs nothing, because at the kickoff the control holds
    nothing and fills its whole book however large ``e`` turns out to be."""
    if cadence not in CADENCES:
        raise ValueError(f"cadence must be one of {CADENCES}, got {cadence!r}")
    d = _as_plain_date("data_date", data_date)
    return dates.prev_session(date(d.year, d.month, 1))


def lookback_for(inner: int) -> int:
    """``inner`` bars widened by ``PREVIOUS_DECISION_BARS``, for an allocator that reads twice.

    The number an allocator returns from ``lookback`` when its own signal needs ``inner`` bars and
    it also recomputes that signal at ``previous_decision_date(data_date)``."""
    if isinstance(inner, bool) or not isinstance(inner, int) or inner < 1:
        raise ValueError(f"inner must be an int >= 1, got {inner!r}")
    return inner + PREVIOUS_DECISION_BARS


def matched_partition(
    *,
    pool: Sequence[str],
    held: AbstractSet[str],
    keep_n: int,
    tag: str,
    seed: int,
    data_date: date,
) -> tuple[list[str], list[str]]:
    """``(keep, tail)``: who the control holds on to, then everyone else in take order.

    ``keep`` is at most ``keep_n`` of ``held & pool`` in the **date-free** keep order, so a name
    the control already holds carries the same key from decision to decision and the keep set
    never churns on the calendar alone. ``tail`` is every remaining pool name: first the ones the
    control does **not** hold, in the **month-keyed** entry order, and last the holdings it is
    dropping, in the same order. Together they cover ``set(pool)`` exactly once.

    **The ordering of ``tail`` is the contract, not an implementation detail.** The caller fills
    its free slots from the front of ``tail``, so a dropped holding sorted anywhere earlier would
    be taken straight back and the realised entry count would fall below the number the rule was
    asked for -- silently, with every size assertion still passing. A dropped holding returns only
    when the fresh half of the pool is exhausted, which is the pool-attrition residual the module
    docstring names and nothing else.

    A caller that wants a finished book of a known size wants ``matched_names``; this is for the
    chassis that must apply its own slot count, its own sector cap or its own keep band to an
    ordering -- M0047's ``one_per_company``, M0197's ``choose``, M0215's ``_fill``."""
    eligible = sorted(set(pool))
    holding = [s for s in eligible if s in held]
    keep = sorted(holding, key=lambda s: (keep_key(tag, seed, s), s))[: max(0, keep_n)]
    kept = set(keep)
    fresh = sorted(
        (s for s in eligible if s not in held),
        key=lambda s: (entry_key(tag, seed, s, data_date), s),
    )
    dropped = sorted(
        (s for s in holding if s not in kept),
        key=lambda s: (entry_key(tag, seed, s, data_date), s),
    )
    return keep, fresh + dropped


def matched_names(
    *,
    pool: Sequence[str],
    held: AbstractSet[str],
    real_now: Sequence[str],
    real_prev: Sequence[str],
    tag: str,
    seed: int,
    data_date: date,
) -> list[str]:
    """``real_now``'s size and ``real_now``'s entry count, with none of its names.

    ``pool`` is the eligible pool today -- the same pool the arm being controlled draws from.
    ``held`` is what the control itself holds coming into this decision. ``real_now`` and
    ``real_prev`` are that arm's own book at this decision and at the previous one; only their
    SIZE and their set difference are read, never a name and never an order, which is what makes
    this blind to the signal.

    Built from ``matched_partition`` rather than beside it, so the book and the partition can
    never disagree about who counts as a fresh name. Returned in a month-keyed, signal-blind rank
    order. Rank carries no weight here -- every slot is the same size -- but it decides which name
    is filled last if a session's cash runs short, and a stable order would put the same names at
    the back of the book for nineteen years."""
    size = len(real_now)
    if size == 0:
        return []
    eligible = sorted(set(pool))
    if not eligible:
        return []
    keep, tail = matched_partition(
        pool=eligible, held=held, keep_n=max(0, size - churn(real_now, real_prev)),
        tag=tag, seed=seed, data_date=data_date,
    )
    book = keep + tail[: max(0, size - len(keep))]
    return sorted(book, key=lambda s: (entry_key(tag, seed, s, data_date), s))


def matched_book(
    select: Select,
    data_date: date,
    held: AbstractSet[str],
    *,
    tag: str,
    seed: int,
    cadence: str = "monthly",
) -> list[str]:
    """``matched_names`` with the two selections taken for you: the call a method file makes.

    ``select`` is asked for the pool and the controlled arm's book twice, at ``data_date`` and at
    ``previous_decision_date(data_date, cadence)``. Both readings use TODAY's membership, which is
    point in time correct: a decision made at ``data_date`` knows who is in the index at
    ``data_date``, and the earlier reading uses only prices and filings dated on or before the
    earlier date.

    The second selection is the rule's whole cost: one extra pass of the controlled arm's own
    ranking per decision. On a monthly book over the dev window that is about 238 extra passes."""
    pool_now, real_now = select(data_date)
    if not real_now:
        return []
    _, real_prev = select(previous_decision_date(data_date, cadence))
    return matched_names(
        pool=pool_now, held=held, real_now=real_now, real_prev=real_prev,
        tag=tag, seed=seed, data_date=data_date,
    )


# ============================================================================================
# The shadow (v2, 2026-10-20): the same rule, with the real book's own drift under it.
# Added BESIDE v1. Nothing above this line changes.
# ============================================================================================

SHADOW_RULE_ID = "matched-draw-v2"
"""``RULE_ID``'s sibling, stamped by an arm drawn through ``shadow_book``/``shadow_selection``.

``RULE_ID`` is NOT bumped to "matched-draw-v2", and that is the point of having two names.
``RULE_ID``'s own docstring sets the rule: "it names a different control, so a bump belongs with
a new arm, never with an edit." Thirteen recorded arms (lab trials 841-853) were drawn under
``RULE_ID``; renaming it would re-label every one of them as something they were not. A v2 arm
carries this constant and a v1 arm keeps that one, and a reader of either trial can tell from the
recorded ``params.as_dict()`` which construction drew it."""

FIXTURE_BARS = 473
"""The hard ceiling on any lab allocator's ``lookback``, in sessions.

``labkit.smoke_market`` generates exactly this many NYSE sessions (``labkit.SMOKE_FIRST``
2013-12-02 through ``backtest.dev.DEV_END`` 2015-10-16), and ``test_lab_methods``' allocator
contract drives every lab allocator over that fixture. An allocator asking for more bars than the
fixture carries is not testable there, and the fixture cannot be widened -- it is the window a
long list of recorded feature tests is written against. The number is therefore absolute and it
is what bounds how deep a backward replay may go. ``test_lab_control_draw_shadow`` asserts this
constant against the fixture's own session count rather than trusting the 473."""

Replay = Callable[[date, AbstractSet[str]], tuple[Sequence[str], Sequence[str]]]
"""``replay(d, held) -> (the eligible pool on d, the controlled arm's book on d given ``held``)``.

``Select``'s sibling, and a strict generalisation of it: ``Select(d)`` is the reading of a book
that does not depend on what it held, which is ``Replay(d, anything)`` on such a chassis. A
chassis whose real book has a KEEP BAND -- a held name stays while it still ranks inside a wider
threshold -- cannot be read by ``Select`` at all without knowing what it held, and that is the
whole defect the shadow exists to repair.

**One callable and not two.** The obvious alternative was to keep ``Select`` and add a separate
band callable beside it. It is rejected: two callables can disagree about the pool, and then the
entry count is counted against one pool and the draw made from another, silently. ``Replay``
hands back the pool it actually ranked, every time it is asked.

The caller closes over ``prepared`` and ``members`` exactly as it does for ``Select``; see
``shadow_selection``."""


class ShadowReading(NamedTuple):
    """What a replay reads: today's pool, today's book, and the book at the previous decision.

    A named tuple rather than a bare triple because the two book fields are the same type and the
    same length and nothing but the name tells them apart -- and swapping them would silently
    invert the entry count rather than raising anything."""

    pool: list[str]
    real_now: list[str]
    real_prev: list[str]


def max_shadow_depth(inner: int) -> int:
    """The deepest replay an allocator whose own signal needs ``inner`` bars can afford.

    ``(FIXTURE_BARS - inner) // PREVIOUS_DECISION_BARS``, floored at 0. One place, because the
    arithmetic has an off-by-one in it that is easy to get wrong in a method file: a chassis with
    194 bars of headroom can afford SEVEN EXTRA steps on top of the one ``lookback_for`` already
    pays, which is ``depth = 8`` and not ``depth = 7``. M0208 measures 253 inner bars, so this
    returns 8 and ``shadow_lookback_for(253, 8)`` is 461."""
    if isinstance(inner, bool) or not isinstance(inner, int) or inner < 1:
        raise ValueError(f"inner must be an int >= 1, got {inner!r}")
    return max(0, (FIXTURE_BARS - inner) // PREVIOUS_DECISION_BARS)


def shadow_lookback_for(inner: int, depth: int) -> int:
    """``lookback_for``'s sibling: ``inner`` bars widened by ``depth`` monthly steps.

    An allocator replaying ``depth`` decisions back reads its own signal at the oldest of them, so
    the history it is handed must reach ``inner`` bars back from THERE. ``depth = 1`` returns
    exactly ``lookback_for(inner)``, which is not a coincidence: a one-step replay reads the same
    two decisions the shipped rule reads, and it is the same number of bars because it is the same
    calendar.

    **It refuses to outgrow the fixture rather than returning a number that cannot be tested.**
    ``FIXTURE_BARS`` is absolute, the failure it prevents is an allocator that no test can drive,
    and the alternative -- returning 487 and finding out in ``test_lab_methods`` -- hides which
    method file asked for it."""
    if isinstance(inner, bool) or not isinstance(inner, int) or inner < 1:
        raise ValueError(f"inner must be an int >= 1, got {inner!r}")
    if isinstance(depth, bool) or not isinstance(depth, int) or depth < 1:
        raise ValueError(f"depth must be an int >= 1, got {depth!r}")
    bars = inner + depth * PREVIOUS_DECISION_BARS
    if bars > FIXTURE_BARS:
        raise ValueError(
            f"a depth-{depth} replay over {inner} inner bars needs {bars} bars, past the "
            f"{FIXTURE_BARS}-bar fixture; max_shadow_depth({inner}) is "
            f"{max_shadow_depth(inner)}"
        )
    return bars


def shadow_decision_dates(data_date: date, depth: int, cadence: str = "monthly") -> list[date]:
    """The replay's calendar, OLDEST FIRST, ``depth + 1`` dates ending at ``data_date``.

    ``[d_depth, ..., d_1, d_0]`` where ``d_0`` is ``data_date`` and each earlier one is
    ``previous_decision_date`` of the one after it. Built by iterating the shipped derivation
    rather than stepping back a fixed number of sessions, so a short month and a holiday both land
    on the date the runner actually used -- the property
    ``test_previous_decision_date_is_the_previous_decisions_own_data_date`` already proves one
    step at a time, extended by induction to ``depth`` of them and asserted again here over the
    whole dev window.

    It raises where ``previous_decision_date`` raises: an unsupported cadence, or a calendar that
    runs out. Neither happens inside the dev window -- the earliest decision is 1995-12-29 and the
    deepest affordable replay is eight months, which lands in 1995."""
    d = _as_plain_date("data_date", data_date)
    if isinstance(depth, bool) or not isinstance(depth, int) or depth < 1:
        raise ValueError(f"depth must be an int >= 1, got {depth!r}")
    out = [d]
    for _ in range(depth):
        out.append(previous_decision_date(out[-1], cadence))
    out.reverse()
    return out


def shadow_selection(
    replay: Replay,
    data_date: date,
    *,
    depth: int,
    cadence: str = "monthly",
) -> ShadowReading:
    """The controlled arm's book at this decision and at the previous one, with its drift in it.

    **The defect this repairs, measured.** ``matched_book`` reads the controlled arm twice with
    ``Select``, and on a keep-band chassis the earlier reading is a FRESHLY DERIVED top-N. A fresh
    top-20 is ranked 1 through 20 and the band only drops a name past rank 40, so almost nothing
    falls out of it; a real held set has been drifting toward the edge for months and falls out far
    faster. Over all 169 of M0208's decisions the fresh stand-in reads **304 entries against the
    real book's 624 -- 0.487x, uniform across eras** (0.444 / 0.509 / 0.500). The 624 is as the
    close-out recorded it and the RATIO is the finding: the recorded ``trials.trades`` is also 624
    and the two are different quantities, so the absolute is a cross-check and not a load-bearing
    number here. The control then enters half as many names as the book it controls, and the
    sentence the method publishes about its own margin is quoted against an opponent paying half
    the fee bill.

    **The repair: a bounded backward replay, and not a carried held set.** Start ``depth``
    decisions back with the band applied to an EMPTY book -- which is the plain top-N, the same
    thing the fresh stand-in was -- and roll the chassis's own band forward one decision at a time.
    After ``depth - 1`` rolls the shadow has accumulated ``depth - 1`` months of drift and stands
    at the previous decision, which is what ``real_prev`` wanted all along. One more application
    gives ``real_now``.

    **Why a replay and not state carried on the allocator**, which is the obvious and wrong design.
    ``backtest.dev.run_registry`` reuses ONE allocator object per allocator id across every
    candidate in a sweep and across every walk-forward fold, so an attribute holding "what the real
    book held last month" would be written by one candidate and read by the next, and by fold 3
    while fold 1 was still being scored. The numbers would depend on sweep order, be irreproducible
    between a sweep and a single run, and differ between a parallel and a serial pytest. This
    function holds the shadow in a local and nowhere else: it is a pure function of ``(replay,
    data_date, depth, cadence)``, it can be called in any order on any date, and
    ``test_the_replay_is_a_pure_function_of_the_date_it_is_given`` asserts exactly that.

    **What it costs.** ``depth + 1`` passes of the controlled arm's own ranking per decision, where
    the shipped rule pays 2. At M0208's affordable maximum that is eight passes over 169 decisions
    instead of two. The lookback it costs is ``shadow_lookback_for(inner, depth)``, and the ceiling
    on ``depth`` is ``max_shadow_depth(inner)``.

    **What it does NOT touch, stated because the next reader will assume it does.** This is a NAME
    rule and it moves the entry count only. Turnover on a chassis that weights its names by
    anything other than equal slots is a property of the weight VECTOR, not of the names:
    ``M0221-E50`` holds ``M0221-C50``'s exact fifty names and records its exact 360 trades and
    still turns over 1.60x. No depth of replay reaches that. The weight axis is ``control_weight``
    and a separate rule; this module never touches a weight.

    **An era where the chassis scores nothing simply reseeds the shadow -- and that is 44 % of the
    repair on M0208, not an edge case.** ``replay`` returns an empty book, the shadow becomes
    empty, and the next decision starts fresh from the band applied to nothing -- which is the
    correct reading, because a book that held nothing did hold nothing, and it is exactly what the
    book engine does when a target comes back empty. Phase 1 measured what that is worth,
    2026-10-20: M0208's SPY 200-day switch holds its real book in cash for **69 of the window's
    238 months**, and ``previous_month_end`` scores a phantom top-20 at the previous month end
    regardless, so on the **9 decisions following a cash month** the shipped estimator reads **38
    entries against a truth of 180 -- 0.211x**. Those nine decisions carry **44 % of M0208's whole
    shortfall**; the freshness defect this rule was proposed for carries 43 %, and the membership
    convention no depth closes carries 13 %. The chain's reset is what buys the first of those, and
    it costs nothing extra because it falls out of the loop rather than being a case in it.
    """
    calendar = shadow_decision_dates(data_date, depth, cadence)
    shadow: frozenset[str] = frozenset()
    pool_now: list[str] = []
    real_now: list[str] = []
    real_prev: list[str] = []
    last = len(calendar) - 1
    for i, d in enumerate(calendar):
        pool, book = replay(d, shadow)
        if i == last:
            pool_now, real_now = list(pool), list(book)
        else:
            real_prev = list(book)
            shadow = frozenset(book)
    return ShadowReading(pool_now, real_now, real_prev)


def shadow_book(
    replay: Replay,
    data_date: date,
    held: AbstractSet[str],
    *,
    tag: str,
    seed: int,
    depth: int,
    cadence: str = "monthly",
) -> list[str]:
    """``matched_book`` with the replay in front of it: the call a v2 method file makes.

    The draw itself is v1's, byte for byte -- this hands ``matched_names`` a better ``real_prev``
    and changes nothing else. The partition, the two hashes, the tail ordering and the
    pool-attrition residual are all the shipped rule, which is why a v2 arm needs no new argument
    about any of them and why the only thing that can differ between a v1 arm and a v2 arm of the
    same chassis is how many names the controlled book is seen to have entered.

    ``depth`` is keyword-only and has NO DEFAULT on purpose. It is the one number this rule cannot
    derive -- how far back a chassis's band has to be rolled before the shadow has stopped moving
    is a property of that chassis's band and its ranking, measured per chassis and not guessed
    here. A default would be a guess wearing a constant's clothes."""
    reading = shadow_selection(replay, data_date, depth=depth, cadence=cadence)
    if not reading.real_now:
        return []
    return matched_names(
        pool=reading.pool, held=held, real_now=reading.real_now, real_prev=reading.real_prev,
        tag=tag, seed=seed, data_date=data_date,
    )
