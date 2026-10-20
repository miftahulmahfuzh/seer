"""The matched weight: a control arm weighted like the book it controls, assigned and not computed.

``lab.control_draw`` made a control hold the same number of names as the book it controls and take
in the same number of new names each decision. On a book whose slots are all the same size that is
the whole match: equal slots of the same count move the same fraction of the book per name, so the
turnover ratio follows the trade ratio arithmetically. On a book that weights its names by
anything else, it is half of it.

**The number that says so, and it was measured before this module existed.** ``M0221-E50`` holds
``M0221-C50``'s **identical fifty names** and records its **identical 360 trades** -- and turns
over **0.7126 against 0.4450, 1.60x**. Not one name differs and not one basket change differs. The
whole 0.60 of excess is the weight vector: ``C50`` is cap-weighted and nearly drift-neutral,
because a name's target weight is its own market-value share and moves with its own price, so the
realised weight tracks the target and the book engine's 1%-of-equity resize band (``sim.rules.
RESIZE_BAND``) rarely fires; ``E50`` pays fifty equal slots and every relative price move pushes
one of them across the band. ``M0221-C50-PLC``, the matched draw on the same chassis, lands at
1.03x trades and **1.95x** turnover -- so about two-thirds of its excess was never a name rule's to
close.

**So this is a SECOND rule on a SECOND axis, and the file layout says so rather than hiding it
behind one module name.** The honest-control set's R1 asked for *one reusable rule*. Read
literally -- one rule, no per-chassis patch -- that requirement **cannot be met, and no further
work will make it meetable**, for two structural reasons:

1. turnover on a weight-varying book is not in name space at all (``E50``, above). The matched
   draw is a name rule by construction and cannot reach it;
2. **a shared module cannot produce a weight vector.** Each chassis computes its own with its own
   code -- ``m0221.weights`` (market value, normalised, a 10% ceiling), ``m0047.size_weights``
   (size under a ceiling), ``m0201.sized_weights`` and ``resize`` (per-company market value, a 10%
   ceiling, a company's weight split over its held classes). Nothing shared can produce any of
   them, and a module that invented a fourth sizing would be building a different book instead of
   matching one.

What *can* be shared is the **assignment** of a vector the chassis hands over, and that is all this
module owns. It is the same shape ``matched_partition`` already has -- the module owns an ordering
contract, each chassis applies its own slot count, ceiling or band to it -- and by the standard
already in force in this lab that is one reusable rule. It is the most R2 can honestly aim at and
the docstring says so here rather than in a plan file nobody reads at 3am.

**The ladder is the open question, not the vector, and four were measured before a line of this
module was written.** ``matched_names`` returns its book in a month-keyed order that re-shuffles
every month, so paying the k-th largest weight to the k-th name of *that* order would re-assign
every rung every month -- a turnover generator in its own right, and a worse one than the problem.
All four ladders of ``ORDERS`` were swept on M0221 inside one ``dev.run_registry`` call against a
book turning over 0.4568, and the spread between them is a factor of fifteen:

- ``"bottom-entry"`` -- ``bottom_entry_order`` below, and the one this lab ships: keeps first in
  the keep order, this decision's entrants last, down the sorted vector. **0.4620, 1.011x the
  book.** On a cap-weighted top-N the name that enters IS the new number ``top``, so it enters at
  the smallest weight in the book and the name that left, left from there too; a blind entrant
  handed an average rung instead takes an entry trade three or four times too large, and taken 371
  times that is the whole excess. This rule reproduces WHERE the churn happens as well as how much
  of it there is;
- ``"ladder"`` -- ``rung_order`` below: the date-free keep order alone, so a name that stays in the
  book keeps its rung for as long as its neighbours do. **0.4612, 1.010x** -- indistinguishable
  from ``"bottom-entry"`` on this chassis, and it gets there by accident: ``matched_partition``
  keeps the holdings with the SMALLEST ``keep_key``, so the names it drops are the ones already
  near the bottom of this ladder and an entrant lands low without being put there. A chassis with a
  different keep band inherits none of that, and M0201 is the measured evidence -- ``"ladder"``
  degrades to 0.6865 there where ``"bottom-entry"`` holds 0.7352;
- ``"own-size"`` -- the control's own sizes, descending, re-shaped to the real book's
  concentration. The rung then moves with the drawn name's own price, which is the most
  drift-neutral of the four, and it reads one number off the real arm where the others read fifty.
  **0.8054, 1.763x**: it closes 15% of the excess and misses;
- ``"entry"`` -- the month-keyed order ``matched_names`` already returns. This is the literal
  reading of the sentence the remedy was briefed in, and it is the worst of the four by an order
  of magnitude: **6.8341, 14.96x the book.** It is kept in ``ORDERS`` as the record that the
  brief's own wording was measured and lost.

**An allocator cannot recover its own rung from state.** ``book_runner`` hands it ``held``, a
``frozenset[str]`` of symbols, and nothing else about the book
(``backtest/book_runner.py:393-403``): there are no weights in the call and never will be. A rung
is therefore **derived** on every decision from something stable, never carried -- and never
stored on the allocator, because ``backtest.dev.run_registry`` reuses one allocator object per id
across candidates and across walk-forward folds, so per-instance state leaks between them.
``rung_order`` takes no date and keeps nothing; ``bottom_entry_order`` takes a date and keeps
nothing, and reads only the ``held`` set the runner handed in; ``assigned`` and ``rescaled`` take
no date and keep nothing.

**What this module may never be used for.** It shapes a control; it never phrases one, and it never
decides *which* names a control holds -- that is ``control_draw``'s job and the two must not grow
into each other. Nothing a chassis reads about a name may decide that name's rung: under
``"ladder"`` the rung is a hash of the symbol, under ``"bottom-entry"`` it is that hash plus
whether the control itself already held the name, under ``"own-size"`` it is the drawn name's own
size -- and the names themselves were drawn blind. A control whose rung came from the real book's
*identity* would not be a control at all. What crosses from the real book is its vector's multiset
of VALUES: a shape, exactly as ``control_draw.matched_names`` takes its size and entry count and
nothing else.

Pure: two hashes, a sort, a rescale and a zip. No clock, no randomness, no store, no database, no
prices.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from seer_engine.lab.control_draw import entry_key, keep_key

RULE_ID = "matched-weight-v1"
"""Names the construction, for a reader of a recorded trial. Reporting only, exactly as
``control_draw.RULE_ID`` is: ``registry._canon`` enumerates ``dataclasses.fields()`` of a
candidate's params and a module constant is in none of them, so bumping this moves no recorded
digest -- but it names a different control, so a bump belongs with a new arm, never with an edit."""

ORDERS: tuple[str, ...] = ("bottom-entry", "ladder", "own-size", "entry")
"""The four ladders a chassis may pay the vector onto, as the module docstring describes them,
with the one this lab ships first.

This module builds two of them: ``"bottom-entry"`` (``bottom_entry_order``) and ``"ladder"``
(``rung_order``), because they are the two a chassis cannot produce for itself. ``"own-size"`` is
the chassis's own size dict sorted, and ``"entry"`` is what ``control_draw.matched_names`` already
returns. The tuple is here so that a method file naming its choice is naming something this module
recognises, and so that a reader meeting one wiring knows three others were measured and lost."""


def rung_order(names: Sequence[str], *, tag: str, seed: int) -> list[str]:
    """``names`` on the date-free ladder: the rung a name holds for as long as it is held.

    ``control_draw.keep_key(tag, seed, symbol)`` is imported rather than re-derived -- it is the
    lab's one date-free hash of a name, it is on the frozen-v1 list, and a key computed two ways is
    a key that will eventually disagree with itself (``control_draw.churn`` says the same about a
    count). Using the keep order rather than a fresh hash is deliberate: it is already the order
    the control decides *who stays* in, so a name that survives a decision keeps the same
    neighbours above it and its rung moves only when one of them leaves.

    ``tag`` is the book's method id, not the allocator id, for the same reason ``keep_key``'s is:
    two twins of one book (M0221 and M0225) given the same tag draw the same names AND pay them the
    same rungs, which is the only way a before-and-after on a data repair measures the repair.

    Refuses a duplicate rather than quietly collapsing it: a book that names one symbol twice has
    already gone wrong upstream, and a silent ``set()`` here would pay one rung to two names and
    leave the last rung unpaid, which every size assertion downstream would still pass.
    """
    out = _checked(names, "names")
    return sorted(out, key=lambda s: (keep_key(tag, seed, s), s))


def bottom_entry_order(
    names: Sequence[str], *, held: frozenset[str] | Sequence[str], tag: str, seed: int,
    data_date: date,
) -> list[str]:
    """``names`` with the ones the control already held first, and this decision's entrants last.

    The shipped ladder, and the mechanism it is built from was written down before it was measured.
    On a cap-weighted top-N the name that ENTERS the real book is its new number ``top``: it comes
    in at the smallest weight the book holds, and the name it replaced left from there too. A
    control that hands its entrant an average rung instead buys three or four times too much of it
    on the one session that name changes hands -- and on M0221 that single error, taken 371 times,
    *is* the whole 1.90x turnover excess the shipped matched draw carries.

    So: the keeps (``names`` the control already holds) come first, in ``rung_order``'s date-free
    keep order so a surviving name's rung moves only when a neighbour above it leaves; the entrants
    (``names - held``) come last, among themselves in ``control_draw.entry_key``'s month-keyed
    order, which is the same order ``matched_names`` drew them in. Paid down a descending vector by
    ``assigned``, an entrant therefore always lands on a bottom rung, as a real top-N's entrant
    does.

    **This is the one function in the module that reads the control's own past**, and it reads the
    only thing an allocator is given: ``held``, the ``frozenset[str]`` ``book_runner`` passes in.
    Nothing is carried between calls and nothing is stored -- ``picks - held`` is the entrant set by
    definition, at no cost and with no state, which is what keeps the rule pure under
    ``dev.run_registry``'s reuse of one allocator object across candidates and folds.

    ``data_date`` keys the entrants' order on the decision's calendar month, exactly as
    ``matched_names`` keys its draw, so two decisions inside one month order them identically and
    the control does not churn on the calendar alone.
    """
    out = _checked(names, "names")
    kept = frozenset(held)
    keeps = sorted((s for s in out if s in kept), key=lambda s: (keep_key(tag, seed, s), s))
    fresh = sorted(
        (s for s in out if s not in kept),
        key=lambda s: (entry_key(tag, seed, s, data_date), s),
    )
    return keeps + fresh


def rescaled(
    vector: Sequence[Decimal | None], *, slots: int, total: Decimal
) -> list[Decimal]:
    """The real book's vector, trimmed or padded to ``slots`` rungs and renormalised to ``total``.

    The real book and the control it controls need not be the same length -- the eligible pool
    thins, a ceiling floors a name to nothing -- and ``control_draw.matched_names`` already handles
    that on the name axis. This handles it on the weight axis, and it is the second half of what
    this module owns: the chassis hands over a vector and a target exposure, and the module shapes
    it to the book that will be paid.

    Three rules, each with its reason:

    - **Padding repeats the smallest rung**, which is what a real top-N would do with one more
      name: the extra name joins at the bottom, not at the average.
    - **``total`` is the SHIPPED control's own weight sum**, never the real book's, so this rule
      changes the SHAPE of the control's vector and never how much of the book is invested. A rule
      that moved exposure would be measuring two things at once and D17 bands on neither.
    - **Nothing positive is invented from nothing.** With no usable rung at all the answer is
      ``slots`` equal shares of ``total`` -- the chassis's own fallback shape, not a refusal, since
      raising here would turn a thin month years into a recorded trial into a crash.

    ``None`` entries are not rungs and neither are non-positive ones: ``m0221.weights`` and
    ``m0201.sized_weights`` both return ``Decimal | None`` per pick, ``None`` where the weight
    floored to zero at ``sim.book.WEIGHT_QUANTUM``, and a name the real book could not hold is not
    a rung the control should pay. The result is sorted descending, which is the order ``assigned``
    reads it in anyway; sorting here as well as there is deliberate, so each function is correct on
    its own.

    The weights are not quantized here. ``sim.book.to_weight`` is the chassis's step and the
    chassis takes it, because the floor it applies (and what it does with a name that floors to
    zero) is the chassis's own convention and not this module's to assume.
    """
    if not isinstance(slots, int) or isinstance(slots, bool):
        raise TypeError(f"slots must be an int, got {type(slots).__name__}")
    if not isinstance(total, Decimal):
        raise TypeError(f"total must be a Decimal, got {type(total).__name__}")
    if slots <= 0 or not total.is_finite() or total <= 0:
        return []
    rungs = _positive(vector)
    if not rungs:
        return [total / slots] * slots
    out = rungs[:slots] if slots <= len(rungs) else rungs + [rungs[-1]] * (slots - len(rungs))
    s = sum(out, Decimal(0))
    if not s.is_finite() or s <= 0:
        return [total / slots] * slots
    return [w / s * total for w in out]


def assigned(
    order: Sequence[str], vector: Sequence[Decimal | None]
) -> dict[str, Decimal]:
    """The k-th name of ``order`` takes the k-th largest weight in ``vector``.

    ``order`` is the ladder -- whichever of ``ORDERS`` the chassis chose -- and ``vector`` is the
    weight vector the chassis computed for the arm being controlled, in that arm's own order, with
    its own ceiling already applied (and, on a chassis whose lengths can differ, through
    ``rescaled``). Only the vector's **multiset of values** is read: never a name, never the real
    book's own ordering, and nothing about which real name held which weight. That is what keeps
    the control blind. It takes the real book's *shape*, exactly as ``control_draw.matched_names``
    takes the real book's *size and entry count* and nothing else.

    ``None`` entries are not rungs and neither are non-positive ones: ``m0221.weights`` and
    ``m0201.sized_weights`` both return ``Decimal | None`` per pick, ``None`` where the weight
    floored to zero at ``sim.book.WEIGHT_QUANTUM``, and a name the real book could not hold is not
    a rung the control should pay.

    The two lengths are allowed to differ and the answer is the honest one in both directions:
    with fewer rungs than names the tail of ``order`` is **absent from the result**, and a caller
    that walks its book and skips a missing key drops exactly those names -- which is what the real
    book did with them. With more rungs than names the surplus is unspent. Neither is an error,
    because a pool thins and a ceiling floors names, and raising here would turn a data fact into a
    crash years into a recorded trial.

    Returns a plain dict, so a caller may fill its book in **its own** order (rank order decides
    who is filled last when a session's cash runs short) while paying each name the rung this
    module assigned it.
    """
    names = _checked(order, "order")
    return dict(zip(names, _positive(vector), strict=False))


def _checked(names: Sequence[str], what: str) -> list[str]:
    """``names`` as a list, refusing an empty string, a non-string and a duplicate.

    A duplicate is refused rather than quietly collapsed: a silent ``set()`` would pay one rung to
    two names and leave the last rung unpaid, and every size assertion downstream would still pass.
    """
    out = list(names)
    for s in out:
        if not isinstance(s, str) or not s:
            raise ValueError(f"every name must be a non-empty str, got {s!r}")
    if len(set(out)) != len(out):
        raise ValueError(f"{what} carries a duplicate, so one rung would be paid twice")
    return out


def _positive(vector: Sequence[Decimal | None]) -> list[Decimal]:
    """The usable rungs of ``vector``, biggest first. A float is a TypeError, as it is in
    ``sim.book.Target.weight``: the vector that feeds a target is held to the same rule rather than
    silently quantized here."""
    rungs: list[Decimal] = []
    for w in vector:
        if w is None:
            continue
        if not isinstance(w, Decimal):
            raise TypeError(f"a weight must be a Decimal or None, got {type(w).__name__}")
        if w > 0:
            rungs.append(w)
    rungs.sort(reverse=True)
    return rungs
