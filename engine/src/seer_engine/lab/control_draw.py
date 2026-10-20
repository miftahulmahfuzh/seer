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

Pure: a calendar, two hashes and set arithmetic. No clock, no randomness, no store, no database.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from collections.abc import Set as AbstractSet
from datetime import date, datetime

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
