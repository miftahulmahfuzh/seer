# Phase 1: The matched-draw rule, proven on both poles (M0227, M0243)

**Plan set:** `HONEST_CONTROL_REDRAW_PLAN.md`
**Analysis:** `docs/analyzer/20261019-181712-C4K9_code_analyzer.md`
**Satisfies:** R1 (settle ONE reusable matched-draw rule and prove it inside the [0.80, 1.25] band
before anything else is pre-registered), R2 (two of the fourteen arms, as amendments under two
existing ids), R3 (two margins re-stated in `trial_funding.mwr`), R4 (the `Candidate.supersedes`
field phase 2's D17 rule reads, and the two declarations that use it)
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab`

---

## Goal

After this phase the lab holds **one** written, tested, reusable rule for deriving a
shape-matched control — `engine/src/seer_engine/lab/control_draw.py` — and that rule has been
measured on both poles of the failure: `M0227-R20`, which traded 0.07x the arm it controls, and
`M0243-NEAR20-R`, which traded 3.01x. Two honest control arms are recorded as amendments under
`M0227` and `M0243`, and the two margins those methods have been quoting (+5.22 pts and +6.07 pts
in `mwr`) are re-stated against an opponent carrying the same fee bill. Phases 3–7 then apply the
settled rule to the other twelve arms without re-deciding anything, or — if either pilot arm lands
outside `WARN_BAND` — they do not start at all.

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Creates:**

- module `seer_engine.lab.control_draw` (`engine/src/seer_engine/lab/control_draw.py`) — the
  phase's whole deliverable to phases 3–7. Public surface, frozen by this phase:
  - `control_draw.RULE_ID: str` = `"matched-draw-v1"`
  - `control_draw.CADENCES: tuple[str, ...]` = `("monthly",)`
  - `control_draw.PREVIOUS_DECISION_BARS: int` = `26`
  - `control_draw.Select` (type alias: `Callable[[date], tuple[Sequence[str], Sequence[str]]]`)
  - `control_draw.keep_key(tag, seed, symbol) -> int`
  - `control_draw.entry_key(tag, seed, symbol, data_date) -> int`
  - `control_draw.churn(now, prev) -> int`
  - `control_draw.previous_decision_date(data_date, cadence="monthly") -> date`
  - `control_draw.lookback_for(inner: int) -> int`
  - `control_draw.matched_partition(*, pool, held, keep_n, tag, seed, data_date) -> tuple[list[str], list[str]]`
  - `control_draw.matched_names(*, pool, held, real_now, real_prev, tag, seed, data_date) -> list[str]`
  - `control_draw.matched_book(select, data_date, held, *, tag, seed, cadence="monthly") -> list[str]`
- `backtest.dev.Candidate.supersedes: tuple[str, ...] = ()` — one trailing **defaulted** field on
  the shared `Candidate` dataclass (`engine/src/seer_engine/backtest/dev.py`), plus its validation
  in `Candidate.__post_init__`. It names the candidate ids this arm declares it supersedes, and it
  is what Phase 2's D17 rule reads (duck-typed, through `control_shape.SUPERSEDES_ATTR`, exactly as
  `DECLARATION_ATTR` is read today). **This phase creates the field and Phase 2 reads it; neither
  phase blocks the other, because `getattr(arm, "supersedes", ())` answers `()` on any arm without
  it, so either order compiles and either order is correct.** See the digest argument in Step 2b.
- `m0227_net_share_shrinkers.MatchedDrawAllocator`, instance `m0227_net_share_shrinkers.MATCHED`,
  **allocator id `"M0227-A1"`** (new, unique lab-wide)
- `m0227_net_share_shrinkers._check_control` — a params guard
- `m0227_net_share_shrinkers.MATCHED_DRAW_AMENDMENT` — `Amendment` seq **1**, one candidate
  `M0227-S20-PLC`
- `m0243_shrinkers_near_high.MatchedNearAllocator`, instance
  `m0243_shrinkers_near_high.MATCHED_NEAR`, **allocator id `"M0243-A1"`** (new, unique lab-wide)
- `m0243_shrinkers_near_high._check_control` — a params guard
- `m0243_shrinkers_near_high.MATCHED_DRAW_AMENDMENT` — `Amendment` seq **1**, one candidate
  `M0243-NEAR20-PLC`
- `engine/tests/test_lab_control_draw.py` — new test module
- `.workflows/plan/honest-control-redraw/phase-1-results.md` — the GO/STOP gate file phases 3–7
  read, and the first of the seven `phase-N-results.md` files Phase 8 collects

**Creates NO new params dataclass.** Reconciled 2026-10-19 across all seven method phases: the
re-drawn arm reuses, byte for byte, the **params value of the arm it replaces**, and is made a
configuration the lab has not run by its **new allocator id alone**. `M0227-S20-PLC` takes
`IssuanceParams(20, side="random", seed=1, trend=None)` — `M0227-R20`'s own value — and
`M0243-NEAR20-PLC` takes `NearShrinkParams(20, cut=2, side="near", pick="random", seed=1)` —
`M0243-NEAR20-R`'s own value. Both are verified to carry every input the matched allocator needs
(`top`, `seed`, `trend`; plus `cut` and `side`, which are the only two fields `band` reads). See
the index invariant "One params value, one new allocator id" for the rule and its one exception.

**Deletes:** nothing. No symbol, no file, no config key, no recorded row.

**Renames:** nothing.

**Signature changes:** none. Every existing function, class, params dataclass and allocator in
`m0227_net_share_shrinkers.py` and `m0243_shrinkers_near_high.py` is left **byte-identical**,
including `IssuanceParams`, `IssuanceAllocator` (`id = "M0227"`), `draw(seed, symbol)`,
`scored_pool`, `NearShrinkParams`, `NearShrinkAllocator` (`id = "M0243"`) and `band`. The only
edits to the two files are: three added import lines, one appended amendment block, and one
added `amendments=(...)` keyword on the existing `Method(...)` call. `backtest/dev.py` gains one
trailing defaulted field and the three lines that validate it; nothing else in it moves.

**Requires (from earlier phases):** nothing. This phase is a wave-1 root.

**Leaves alone (owned by others):**

- `engine/src/seer_engine/lab/control_shape.py`, `engine/src/seer_engine/lab/hardgate.py`,
  `engine/src/seer_engine/commands/lab.py`, `engine/tests/test_lab_control_shape.py`,
  `engine/tests/test_lab_hardgate.py` — Phase 2. This phase **imports** `control_shape` in a test
  (read-only: `kind_of`, `resolve_target`, `DOSE_MARKERS`, `KIND_PLACEBO`, `RUNG_STEM`) and edits
  none of it.
- `m0221_cap_weighted_top_n.py`, `m0225_cap_weighted_top_n_repaired.py` — Phase 3
- `m0047_market_value_residual.py` — Phase 4
- `m0201_treasury_beta_size_weighted.py`, `m0202_treasury_beta_half_guard.py` — Phase 5
- `m0208_capital_gains_overhang.py` — Phase 6
- `m0215_sector_capped_calm_raisers.py` — Phase 7
- `lab stage`, `web/data/lab.json`, `lab/lab.sqlite` **as a committed artefact**, the merge to
  `main`, `docs/plans/HANDOVER_20261019-the-honest-control.md`, `lab insight` — Phase 8. This
  phase *writes rows into* `lab.sqlite` through `lab run --amend` (that is its job) but **never
  commits the database**.

**Contract notes phases 3–7 must honour when they consume `control_draw`:**

1. `tag` is an explicit argument and is the **book's** method id, not the allocator id. Phase 3's
   twins (`M0221` / `M0225`) must both pass `tag="M0221"` so the two controls draw the identical
   names wherever both stores price them — exactly as `M0225-R50` already keys on `"M0221"`.
2. The new allocator id is `<METHOD>-A<amendment seq>`. Phase 3's M0225 amendment is **seq 2**, so
   its allocator id is `"M0225-A2"`.
3. **Never add a field to an existing params dataclass, and never write a new one either.** Reuse
   the params **value** of the arm being replaced and let the new allocator id be the whole of the
   difference. The reason a new field is fatal is in `_canon` (below); the reason a new *dataclass*
   is unnecessary is that all nine chassis' existing params already carry every input the matched
   draw reads, which was checked field by field on 2026-10-19. The one exception the set allows is
   named in the index invariant and belongs to Phase 6.
4. Candidate ids are `<target-id>-PLC`, so `control_shape.resolve_target` lands on `RUNG_STEM`.
5. Every re-drawn rationale carries a `DRAW_MARKERS` phrase and none of `DOSE_MARKERS`.
6. **Every re-drawn arm declares what it supersedes**, in the same commit that pre-registers it:
   `supersedes=("<the mis-shaped arm's id>",)` on the `Candidate`. Phase 2's D17 rule is an
   *explicit declaration* and never an inference from target equality, so an arm that declares
   nothing retires nothing and the method stays blocked. The whole fourteen-row mapping is
   enumerated once in the index, under **The supersession mapping**; copy the row, do not invent
   one.
7. **Which function to call.** A chassis that fills a fixed book of names calls `matched_book`
   (or `matched_names` when it already has both selections in hand) and gets the book. A chassis
   that must apply its **own** slot count, cap or keep band to an ordering calls
   `matched_partition` and gets `(keep, tail)` — the names it holds on to, then every other pool
   name in the order it would take them, **fresh names first and the holdings it is dropping
   last**. That ordering is a guarantee of this module, not of the caller: see
   `matched_partition`'s docstring and
   `test_a_dropped_holding_is_never_re_taken_ahead_of_a_fresh_name`. Phases 4, 5 and 7 take the
   partition; phases 3 and 6 and this phase take the book.
8. **`previous_decision_date` answers the previous *monthly* decision and nothing else.** It is
   the right clock for every chassis whose allocator re-picks its basket on every monthly decision
   — which includes M0047's residual arms (checked: `REPICK_MONTHS` and `KEEP_PCT` live only
   inside `m0047.placebo_order`, and `:244-248` takes a fresh `one_per_company(order, 20)` every
   month). It is the **wrong** clock for a chassis whose basket only moves on a slower clock —
   M0201's and M0202's shared quarterly re-pick behind M0197's 40% keep band — and such a chassis
   derives its own previous re-pick in its own method file. Phase 5 does, and measured 0.955 doing
   it. Do not force the monthly answer onto a quarterly basket, and do not reach for the previous
   quarter on a monthly one.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/control_draw.py` | create | the matched-draw rule, in one place, with the prose that says why its shape is what it is |
| `engine/src/seer_engine/backtest/dev.py` | modify | one trailing defaulted field `supersedes: tuple[str, ...] = ()` on `Candidate`, and its validation in `__post_init__`. Nothing else |
| `engine/src/seer_engine/lab/methods/m0227_net_share_shrinkers.py` | modify | imports at `:60-61`; guard + allocator + `Amendment` inserted between `:250` and `:253`; `amendments=` added inside the `Method(...)` call before its close at `:319` |
| `engine/src/seer_engine/lab/methods/m0243_shrinkers_near_high.py` | modify | imports at `:80-81`; guard + allocator + `Amendment` inserted between `:257` and `:260`; `amendments=` added before the `Method(...)` close at `:358` |
| `engine/tests/test_lab_control_draw.py` | create | the calendar derivation, the churn match and the tail ordering, asserted session by session, before any backtest |
| `.workflows/plan/honest-control-redraw/phase-1-results.md` | create | the GO/STOP gate the fan-out reads, and Phase 8's first results file |

The plan index is **not** edited by this phase. Its Reconciliation Log belongs to the reconciler
and its **Status** line to Phase 8; this phase's record is `phase-1-results.md`, which is where
both the fan-out and Phase 8 look for it.

---

## The rule, decided

**Rule A — churn-matched draw.** Chosen. **Rule C (persistence-inherited permutation) is the
named fallback**, and it fires only on the trigger stated below. Rule B (M0241's cohort mirror)
is excluded on evidence: it measures 1.372x trades / 1.131x turnover, outside the match band.

**Why A and not C, in one line each.** A matches the entry count *by construction* — the control
is told how many names the real arm is adding this month and adds exactly that many, so the
trade ratio is ~1.00 analytically, not empirically. C matches it only *statistically*, and its
pool thins wherever σ(X) is unscorable that day, which silently changes the frame the control is
supposed to share.

**The fallback trigger, stated so nobody has to judge it.** Rule C is reached if and only if
**Step 4's real-store shape probe** (which computes no return) reports a basket-change ratio
outside `[0.70, 1.40]` for either pilot arm. That is wider than `WARN_BAND` on purpose: the probe
counts basket changes, not `trials.trades`, so it is a proxy and must not be read as if it were
the recorded number. Below 0.70 or above 1.40 the derivation itself is wrong and no amendment is
committed; inside it, the amendments are committed and run, and `lab control` is the verdict.

**Why the keep hash and the entry hash are different hashes.** The two poles each used one hash
for both jobs and each got half of it right. `M0227`'s `draw(seed, symbol)` has no date term, so
it is the right order for deciding **who stays** (stable: a name kept this month is likely kept
next month). `M0187`'s `draw(seed, symbol, data_date)` re-keys on the month, so it is the right
order for deciding **who enters** (fresh: the entrants are not the same twenty names forever).
The matched draw uses both and derives the split between them from the real book's own calendar.
That is the whole idea, and it is the sentence the module docstring has to carry.

**The one residual, named up front.** A control name can leave the eligible pool, and then it
must go whatever `e` says. The control's entries are therefore `max(e, a)` where `a` is its own
pool attrition, and the real arm's `e` already contains the real arm's attrition. The two
attrition rates are not identical. That difference is the only thing between the rule and a
ratio of exactly 1.00, and it is measured in Step 4 and again by `lab control`, never assumed.

---

## Implementation Steps

### Step 1: `control_draw.py` — the rule, in one place

**File:** `engine/src/seer_engine/lab/control_draw.py` (new)
**Change:** create the module. Nothing else in the repo imports it yet.
**Code:**

```python
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
```

**Impact:** nothing imports it yet, so the tree stays green on its own. `ruff check engine` must
pass (E9, F minus F401): every import above is used.

---

### Step 2: M0227 — the 0.07x pole

**File:** `engine/src/seer_engine/lab/methods/m0227_net_share_shrinkers.py`

#### 2a. Imports

**File:** `m0227_net_share_shrinkers.py:60-61` (replace the two lines)
**Change:** add `control_draw`, and `Amendment` beside `Method`.
**Code:** replace

```python
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
```

with

```python
from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Amendment, Method
```

**Impact:** `seer_engine.lab.control_draw` imports only `seer_engine.dates` and the standard
library, so no import cycle with `seer_engine.lab.method`.

#### 2b. The amendment block

**File:** `m0227_net_share_shrinkers.py` — insert between `:250` (the last line of `_v`) and
`:253` (`METHOD = Method(`), i.e. after the blank lines that follow `_v`.
**Change:** add the params guard, the new allocator, the amendment's candidate constructor and the
`Amendment` itself. **No new params dataclass:** the arm reuses `IssuanceParams`, with
`M0227-R20`'s own value.
**Code:**

```python
# ---- amendment 1 (2026-10-19): the honest control ---------------------------------------------
#
# R20's hash order keys on (seed, symbol) and carries no date, so its book changes only when the
# scored pool does: 41 trades in nineteen years against S20's 608, which is 0.07x, and a control
# that does not trade does not pay Gotrade's fees. This block replaces it with the lab's one
# matched-draw rule (`lab.control_draw`) under a NEW allocator id, so not one byte of what the
# five recorded M0227 trials read is touched.
#
# The params are R20's own, reused verbatim. `IssuanceParams` already carries every input the
# matched draw reads -- `top`, `seed`, `trend` -- so there is nothing a new dataclass could hold.
# A field added to `IssuanceParams` would move all five recorded M0227 digests and all five
# M0243 ones (`registry._canon` renders a dataclass by `dataclasses.fields()`, not by `as_dict`),
# and a new dataclass would be a second way of saying the same thing in nine files. The new
# allocator id is the whole of the difference, and it is enough: `config_text` is rules, allocator
# id and params, so `<M0227-A1>` against R20's `<M0227>` is a configuration the lab has not run.


def _check_control(params: object) -> IssuanceParams:
    """``IssuanceParams``, plus the one thing a control's params may not say.

    The matched draw differs from ``R20`` in its allocator id and in nothing else, so the params
    must still read ``side="random"``. Saying ``"shrink"`` would record a configuration whose text
    claims a buyback ranking this allocator never performs -- the config text is the public record
    of what an arm did, and a blind book must not describe itself as a ranked one.
    """
    if not isinstance(params, IssuanceParams):
        raise TypeError(f"params must be IssuanceParams, got {type(params).__name__}")
    if params.side != "random":
        raise ValueError(f"the matched draw is a control: side must be 'random', got {params.side!r}")
    return params


class MatchedDrawAllocator:
    """S20's shape with none of its identity: ``lab.control_draw``'s matched draw on M0227's pool.

    Each month it recomputes S20's own selection at this decision and at the previous one, keeps
    all but ``e`` of its names in a date-free hash order and draws ``e`` fresh ones from the same
    scored pool in a hash order keyed on the month, where ``e`` is how many names S20 itself is
    adding. Equal slots, fully invested, same switch, same fees.

    Its own allocator id, ``M0227-A1``: a trial's identity is its rules, its allocator id and its
    params, so a new id is what makes this a configuration the lab has not run without touching
    anything the five recorded ones read. ``hardgate._INGREDIENT`` is ``<(M\\d{4})>``, so
    ``<M0227-A1>`` names no ingredient and D12 reads exactly what it read before.
    """

    id = "M0227-A1"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check_control(params)
        inner = max(DV_N, 0 if p.trend is None else p.trend[1])
        return control_draw.lookback_for(inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check_control(params)
        return ("SPY",) if p.trend is None else tuple(sorted({"SPY", p.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check_control(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check_control(params)
        return True

    def _select(self, prepared: IssuancePrepared, members: AbstractSet[str], data_date: date,
                p: IssuanceParams) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """(the eligible pool, S20's own book) on ``data_date`` -- the shrink arm's own two."""
        pool = scored_pool(prepared, members, data_date)
        if not pool:
            return (), ()
        order = sorted(pool, key=lambda s: (pool[s], s))
        return tuple(sorted(pool)), tuple(order[: p.top])

    def _run(self, prepared: IssuancePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: IssuanceParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        gate = FactorParams(rank="momentum", top=p.top, trend=p.trend)
        if not trend_on(prepared.history, data_date, gate):
            return ()
        names = control_draw.matched_book(
            lambda d: self._select(prepared, members, d, p),
            data_date, held, tag="M0227", seed=p.seed,
        )
        w = equal_weight(p.top)
        out: list[Target] = []
        for s in names:
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no pool and no target."""
        return self._run(IssuancePrepared(history, None), members, data_date, held,
                         _check_control(params))

    def prepare(self, history: Mapping[str, History]) -> IssuancePrepared:
        return IssuancePrepared(history, None)

    def prepare_market(self, market: Any) -> IssuancePrepared:
        if not hasattr(market, "shares") or len(market.shares) == 0:
            return IssuancePrepared(market.history, None)
        return IssuancePrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, IssuancePrepared):
            raise TypeError(f"prepared must be IssuancePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check_control(params))


MATCHED = MatchedDrawAllocator()


def _vm(suffix: str, params: IssuanceParams, rationale: str, supersedes: tuple[str, ...]) -> Candidate:
    return Candidate(id=f"M0227-{suffix}", family="M0227", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MATCHED, params=params, rationale=rationale,
                     added=date(2026, 10, 19), owner_inputs=(), supersedes=supersedes)


MATCHED_DRAW_AMENDMENT = Amendment(
    added=date(2026, 10, 19),
    why=(
        "R20's hash order has no date in it, so the control traded 0.07x S20 and the +5.22 point "
        "lead was quoted against a book that barely paid a fee"
    ),
    hypothesis=(
        "Written before any result and frozen by the commit that adds this block. `lab control` "
        "on 2026-10-19 reports M0227-R20 trading 41 times against M0227-S20's 608 -- 0.07x, with "
        "0.12x the turnover -- because its hash order keys on (seed, symbol) and carries no date, "
        "so its book changes only when the scored pool does. A control that does not trade does "
        "not pay Gotrade's fees, and S20's recorded lead of +5.22 points a year on the owner's "
        "deposits (12.95% against R20's 7.73%, total-return SPY on the same deposits 7.19%) was "
        "therefore quoted against a handicapped opponent. S20-PLC replaces it with the lab's one "
        "matched-draw rule (seer_engine/lab/control_draw.py): the same scored pool, the same "
        "twenty equal slots, the same monthly clock, the same fees, but each month it keeps all "
        "but e of its names in a date-free hash order and draws e fresh ones in a hash order "
        "keyed on that month, where e is how many names S20 itself is adding -- read off S20's "
        "own selection at this decision and at the one before it, never chosen. Two falsifiable "
        "predictions. SHAPE: S20-PLC lands inside 0.80-1.25 of S20 on BOTH recorded trades and "
        "recorded turnover, not merely inside D17's 0.50-2.00 refuse band, because its entries "
        "per rebalance are matched by construction and not calibrated. MARGIN, and its DIRECTION "
        "is the pre-registration: an honest control trades roughly fifteen times as often as R20 "
        "did, so it pays roughly fifteen times R20's fee bill, EARNS LESS than R20's 7.73%, and "
        "S20's quoted lead WIDENS beyond +5.22 points a year. The widening is the cost of about "
        "570 extra trades on a twenty-name book over nineteen years at Gotrade's minimums on a "
        "20M IDR account, which is one to three points a year. If S20-PLC instead earns MORE than "
        "R20, the difference is the draw and not the fees, and that is the finding -- it is "
        "reported, not redrawn. Nothing about S20 moves: its trial is recorded and this adds one "
        "arm beside it. No test-window look is spent."
    ),
    expected_failure=(
        "Four ways, in order of likelihood. (1) SHAPE, the one that stops the fan-out: the "
        "control's own pool attrition exceeds S20's churn. S20 adds only about 1.3 names a month "
        "(608 trades over roughly 228 monthly decisions on a twenty-name book), which is a very "
        "sticky book, and a blindly drawn twenty leaves the scored pool at its own rate; where "
        "that rate is higher, the control's entries are its attrition rather than e and the trade "
        "ratio lands above 1.25. That is a miss on the rule, not on the method, and it stops the "
        "re-draw of the other twelve arms rather than being tuned away. (2) The margin reverses: "
        "twenty names drawn from a pool of 250-400 is a wide distribution and one seed is one "
        "draw, so S20-PLC may earn more than S20 for reasons that have nothing to do with "
        "buybacks. One seed is what this amendment pre-registers; a second seed would be a second "
        "look and is not taken here. (3) The widening is smaller than the fee arithmetic says, "
        "because Gotrade's minimum bites hardest on the smallest slots and the smallest slots are "
        "in the early years of a 20M IDR account, so most of the extra trading costs less than it "
        "would at the end of the window. (4) The band is cleared and the margin is unchanged to "
        "within a tenth of a point, which would say the fee handicap was never material on this "
        "book -- D17's refusal still correct, and this re-draw having bought nothing but an "
        "honest number. Any of these is reported as it lands. None is a reason to redraw: a "
        "second amendment on this arm is admissible only under (1), and only because the SHAPE "
        "missed."
    ),
    candidates=(
        _vm("S20-PLC", IssuanceParams(20, side="random", seed=1, trend=None),
            "Placebo, shape-matched: 20 names from S20's own scored pool, kept in a date-free "
            "hash order and entered in a monthly hash order, as many each month as S20 enters",
            supersedes=("M0227-R20",)),
    ),
)
```

**Impact:** `M0227.all_candidates()` grows from 5 to 6. `config_digest` of the five recorded arms
is untouched: `config_text` reads `c.rules`, `c.allocator.id` and `c.params` only, and none of the
three moved for any of them. `Method.__post_init__` accepts the new arm because its `config_text`
differs from `M0227-R20`'s on the `allocator=` line — `<M0227-A1>` against `<M0227>` — and because
`M0227-S20-PLC` is a new id.

**The `config_digest` safety argument, spelled out once for the whole plan set:**

1. `method.config_text(c)` = `rules=<_canon(c.rules)>` + `allocator=<c.allocator.id>` +
   `params=<_canon(c.params)>`. Nothing else — not the id, not the family, not the rationale, not
   `added`, not `supersedes`, not `owner_inputs`, not `Method.amendments`.
2. `registry._canon` on a dataclass is
   `f"{type(value).__name__}({','.join(f'{f.name}={_canon(...)}' for f in fields(value) if f.compare)})"`
   (`backtest/registry.py:323-332`). It reads `dataclasses.fields()`, **never** the hand-written
   `as_dict()`.
3. Therefore: (a) adding a `compare=True` field to `IssuanceParams` would rewrite all five
   recorded M0227 digests **and** all five M0243 ones; (b) adding a `compare=False` field would
   leave them alone but make the new arm's configuration byte-identical to R20's, which
   `Method.__post_init__` refuses; (c) **reusing R20's params value under a new allocator id moves
   nothing and repeats nothing**, because the `allocator=` line alone makes the text new. This
   phase does (c), and so does every other method phase in the set.
4. **`Candidate.supersedes` is outside the digest by construction, which is what makes the
   declaration free.** `method.config_text` names three attributes and `registry.candidate_text`
   names five, both by hand; grepped 2026-10-19, **no call site anywhere passes a whole
   `Candidate` to `registry._canon`** — every call is `_canon(c.rules)` or `_canon(c.params)` or a
   recursive one — so `_canon`'s `dataclasses.fields()` walk never meets a `Candidate` and a
   trailing defaulted field on it cannot move a recorded digest. That grep is the check Phase 2's
   whole mechanism rests on, and Step 5a re-runs it.
5. `test_every_recorded_configuration_still_digests_to_its_recorded_digest`
   (`engine/tests/test_lab_methods.py:187`) is the proof, and it runs in Step 5 before any commit.

#### 2b. `Candidate` gains the declaration field

**File:** `engine/src/seer_engine/backtest/dev.py` — one field after `owner_inputs` (`:197`), and
its validation appended to `__post_init__` (after `:222`).

**Change:** add the trailing defaulted field Phase 2's D17 rule reads.

```python
    owner_inputs: tuple[str, ...]
    supersedes: tuple[str, ...] = ()
```

with this paragraph added to `Candidate`'s own docstring:

```
``supersedes`` names the candidate ids this arm declares it replaces, for ``lab.control_shape``'s
D17 supersession (2026-10-19). Declared and never inferred. A control arm whose shape D17 refuses
is recorded forever -- ``trials`` is append-only by trigger -- so the only way a re-drawn control
can retire the bent one is to say which one it retires, in the commit that pre-registers it.
Target equality was the obvious alternative and is wrong in both directions: it misses a re-drawn
arm that deliberately re-points at its TRUE target (``M0047-MV10-PLC`` resolves to ``M0047-MV10``
while the arm it replaces resolves to ``M0047-EQ``), and it over-reaches when two
differently-aimed placebos happen to resolve to one arm (``M0215-HASH`` and ``M0215-HASH-CAP4``
both land on ``M0215-CTRL``). It is read duck-typed, through ``control_shape.SUPERSEDES_ATTR``,
exactly as ``DECLARATION_ATTR`` is, so no lab module imports this one. It is outside
``config_digest`` by construction: ``lab.method.config_text`` and ``registry.candidate_text`` both
name their fields by hand and nothing passes a whole ``Candidate`` to ``registry._canon``.
```

and this appended to `__post_init__`:

```python
        if not isinstance(self.supersedes, tuple):
            raise TypeError(f"{self.id}: supersedes must be a tuple of candidate ids")
        for item in self.supersedes:
            if not isinstance(item, str) or _ID.fullmatch(item) is None:
                raise ValueError(f"{self.id}: supersedes holds {item!r}, not a candidate id")
            if item == self.id:
                raise ValueError(f"{self.id}: an arm cannot supersede itself")
        if self.supersedes != tuple(sorted(set(self.supersedes))):
            raise ValueError(
                f"{self.id}: supersedes must be sorted and unique, got {self.supersedes!r}"
            )
```

**Impact:** the field is defaulted and trailing, so every `Candidate(...)` call in
`backtest/registry.py` and in 271 method files is unchanged, and `@dataclass(frozen=True)` on
`Candidate` carries no `slots=True`, so nothing about the layout is pinned. A typo in a
declaration becomes an import-time error instead of a silent non-supersession, which is the whole
reason this is a validated field and not a phrase in prose. **Phase 2 does not depend on this
step and this step does not depend on Phase 2:** `getattr(arm, "supersedes", ())` answers `()` on
an arm that has none, so either order of landing compiles and either order is correct.

#### 2c. Attach the amendment

**File:** `m0227_net_share_shrinkers.py:318` (the `seen_keys=(...)` close), before `:319`
**Change:** add one keyword to the existing `Method(...)` call.
**Code:** replace

```python
    seen_keys=(
        "concept:net-share-issuance",
        "concept:buyback-shrinkers",
    ),
)
```

with

```python
    seen_keys=(
        "concept:net-share-issuance",
        "concept:buyback-shrinkers",
    ),
    amendments=(MATCHED_DRAW_AMENDMENT,),
)
```

**Impact:** `Method` gains an `amendments` tuple. `config_text` never passes a `Method` to
`_canon`, so no digest moves (this is exactly what `test_lab_amendments.py:111` already pins).

---

### Step 3: M0243 — the 3.01x pole

**File:** `engine/src/seer_engine/lab/methods/m0243_shrinkers_near_high.py`

#### 3a. Imports

**File:** `m0243_shrinkers_near_high.py:80-81` (replace the two lines)
**Code:** replace

```python
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
```

with

```python
from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Amendment, Method
```

Everything else the new block needs is already imported by this file: `dataclass` (`:76`),
`AbstractSet` (`:75`), `Any` (`:78`), `date` (`:77`), `HIGH_N` / `nearness` (`:82`), `DV_N` /
`IssuancePrepared` / `scored_pool` (`:84-90`), `Target` / `equal_weight` (`:91`),
`MONTHLY_HOLD_FRAC_GOTRADE` (`:92`), `last_close` / `target_from_close` (`:93`), `History`
(`:94`), `FactorParams` / `trend_on` (`:95`).

#### 3b. The amendment block

**File:** `m0243_shrinkers_near_high.py` — insert between `:257` (the last line of `_v`) and
`:260` (`METHOD = Method(`).
**Code:**

```python
# ---- amendment 1 (2026-10-19): the honest control ---------------------------------------------
#
# NEAR20-R is this file's own overcorrection of M0227's sticky draw -- see the PICK paragraph at
# the top -- and it overshot: redrawn in full every month, it traded 3872 times against NEAR20's
# 1285, which is 3.01x, and paid three fee bills for one book. This block replaces it with the
# lab's one matched-draw rule under a NEW allocator id, leaving every recorded configuration
# byte-identical.


def _check_control(params: object) -> NearShrinkParams:
    """``NearShrinkParams``, plus the one thing a control's params may not say.

    The matched draw differs from ``NEAR20-R`` in its allocator id and in nothing else, so the
    params must still read ``pick="random"``. Saying ``"shrink"`` would record a configuration
    whose text claims a buyback ranking this allocator never performs.

    Reused and not replaced: ``NearShrinkParams`` already carries ``top``, ``cut``, ``side``,
    ``seed`` and ``trend``, which is every input the matched draw reads, and ``band`` reads only
    ``cut`` and ``side`` (`m0243:161-178`) so the real arm's own band is reproduced by handing it
    this same object. A field added here would move the recorded ``config_digest`` of all five
    M0243 trials, and a new dataclass beside it would buy nothing.
    """
    if not isinstance(params, NearShrinkParams):
        raise TypeError(f"params must be NearShrinkParams, got {type(params).__name__}")
    if params.pick != "random":
        raise ValueError(f"the matched draw is a control: pick must be 'random', got {params.pick!r}")
    return params


class MatchedNearAllocator:
    """NEAR20's shape with none of its identity: the matched draw inside NEAR20's own near band.

    Each month it recomputes NEAR20's selection at this decision and at the previous one, keeps
    all but ``e`` of its names in a date-free hash order and draws ``e`` fresh ones from the
    IDENTICAL nearness band in a hash order keyed on that month, where ``e`` is how many names
    NEAR20 itself is adding. The filter is held constant and only the pick is blind, which is what
    NEAR20-R was always for; what moves is that the draw now turns over like the book instead of
    three times as fast.

    Its own allocator id, ``M0243-A1``, for the reason ``MatchedDrawAllocator`` gives in M0227.
    """

    id = "M0243-A1"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check_control(params)
        inner = max(DV_N, HIGH_N, 0 if p.trend is None else p.trend[1])
        return control_draw.lookback_for(inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check_control(params)
        return ("SPY",) if p.trend is None else tuple(sorted({"SPY", p.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check_control(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check_control(params)
        return True

    def _select(self, prepared: IssuancePrepared, members: AbstractSet[str], data_date: date,
                p: NearShrinkParams) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """(the kept nearness band, NEAR20's own book inside it) on ``data_date``."""
        pool = scored_pool(prepared, members, data_date)
        if not pool:
            return (), ()
        kept = band(pool, prepared.history, data_date, p)
        if not kept:
            return (), ()
        order = sorted(kept, key=lambda s: (pool[s], s))
        return tuple(sorted(kept)), tuple(order[: p.top])

    def _run(self, prepared: IssuancePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: NearShrinkParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        gate = FactorParams(rank="momentum", top=p.top, trend=p.trend)
        if not trend_on(prepared.history, data_date, gate):
            return ()
        names = control_draw.matched_book(
            lambda d: self._select(prepared, members, d, p),
            data_date, held, tag="M0243", seed=p.seed,
        )
        w = equal_weight(p.top)
        out: list[Target] = []
        for s in names:
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no pool and no target."""
        return self._run(IssuancePrepared(history, None), members, data_date, held,
                         _check_control(params))

    def prepare(self, history: Mapping[str, History]) -> IssuancePrepared:
        return IssuancePrepared(history, None)

    def prepare_market(self, market: Any) -> IssuancePrepared:
        if not hasattr(market, "shares") or len(market.shares) == 0:
            return IssuancePrepared(market.history, None)
        return IssuancePrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, IssuancePrepared):
            raise TypeError(f"prepared must be IssuancePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check_control(params))


MATCHED_NEAR = MatchedNearAllocator()


def _vm(suffix: str, params: NearShrinkParams, rationale: str,
        supersedes: tuple[str, ...]) -> Candidate:
    return Candidate(id=f"M0243-{suffix}", family="M0243", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MATCHED_NEAR, params=params, rationale=rationale,
                     added=date(2026, 10, 19), owner_inputs=(), supersedes=supersedes)


MATCHED_DRAW_AMENDMENT = Amendment(
    added=date(2026, 10, 19),
    why=(
        "NEAR20-R is redrawn in full every month, so the control traded 3.01x NEAR20 and the "
        "+6.07 point lead was quoted against a book paying three fee bills"
    ),
    hypothesis=(
        "Written before any result and frozen by the commit that adds this block. This file's own "
        "PICK paragraph says why NEAR20-R is redrawn each month: M0227's placebo used a sticky "
        "hash order and traded 41 times in nineteen years, so this one was redrawn monthly 'so it "
        "turns over like the book it controls for'. Measured, it does not: `lab control` on "
        "2026-10-19 reports 3872 trades against NEAR20's 1285 -- 3.01x, with 2.98x the turnover. "
        "The correction was made by hand and overshot, which is the argument for deriving the "
        "re-key period from the book instead of choosing one. NEAR20's recorded lead of +6.07 "
        "points a year on the owner's deposits (10.45% against NEAR20-R's 4.38%, total-return SPY "
        "on the same deposits 7.19%) is therefore quoted against an opponent paying about three "
        "times its fee bill. NEAR20-PLC replaces it with the lab's one matched-draw rule "
        "(seer_engine/lab/control_draw.py): the IDENTICAL nearness band, the same twenty equal "
        "slots, the same monthly clock, the same fees, but each month it keeps all but e of its "
        "names in a date-free hash order and draws e fresh ones in a hash order keyed on that "
        "month, where e is how many names NEAR20 itself is adding -- read off NEAR20's own "
        "selection at this decision and at the one before it, never chosen. Two falsifiable "
        "predictions. SHAPE: NEAR20-PLC lands inside 0.80-1.25 of NEAR20 on BOTH recorded trades "
        "and recorded turnover, not merely inside D17's 0.50-2.00 refuse band. MARGIN, and its "
        "DIRECTION is the pre-registration: an honest control trades about a third as often as "
        "NEAR20-R did, pays about a third of its fee bill, EARNS MORE than NEAR20-R's 4.38%, and "
        "NEAR20's quoted lead NARROWS from +6.07 points or REVERSES. Reversal is a live outcome "
        "and this method's own hypothesis already names it: prediction (2) there is that NEAR20 "
        "must beat its placebo by 2 or more points a year, and 'if it does not, the nearness "
        "filter is doing all the work and this is M0015 in disguise, which already lost'. That "
        "sentence is now read against an honest opponent for the first time. Nothing about NEAR20 "
        "moves: its trial is recorded and this adds one arm beside it. No test-window look is "
        "spent."
    ),
    expected_failure=(
        "Four ways, in order of likelihood. (1) The lead does not merely narrow, it vanishes: "
        "NEAR20-R's 4.38% was dragged down by 2587 trades it should never have made, and a third "
        "of that fee bill back could be worth several points a year on a twenty-name book at "
        "Gotrade's minimums. If NEAR20-PLC lands within 2 points of NEAR20's 10.45%, this "
        "method's own success condition (2) fails and the finding is that the near-high filter, "
        "not the buyback signal, was carrying the book -- which closes the direction rather than "
        "opening a tuning exercise, exactly as this file's expected_failure (1) already said. "
        "(2) SHAPE, the one that stops the fan-out: the control's own attrition from the nearness "
        "band differs from NEAR20's. The band is recomputed every month from the whole scored "
        "pool's nearness ranking, so a blindly drawn name can fall out of the near half for a "
        "reason a top-twenty shrinker would not, and the trade ratio lands above 1.25. That is a "
        "miss on the rule, not on the method, and it stops the re-draw of the other twelve arms. "
        "(3) The opposite shape failure: the near band is the churniest pool in this set (NEAR20 "
        "itself changes about 5.6 names a month), so if a matched draw over-keeps -- the keep "
        "hash being stable while the band membership is not -- the ratio could land below 0.80 "
        "instead. (4) The band is cleared, the lead narrows by a point or two and survives, and "
        "the finding is the narrow one: part of the +6.07 was fees and the rest is signal. Any of "
        "these is reported as it lands. None is a reason to redraw: a second amendment on this "
        "arm is admissible only under (2) or (3), and only because the SHAPE missed."
    ),
    candidates=(
        _vm("NEAR20-PLC",
            NearShrinkParams(20, cut=2, side="near", pick="random", seed=1, trend=None),
            "Placebo, shape-matched: 20 names from NEAR20's identical near half, kept in a "
            "date-free hash order and entered in a monthly hash order, as many each month as "
            "NEAR20 enters",
            supersedes=("M0243-NEAR20-R",)),
    ),
)
```

**Impact:** `M0243.all_candidates()` grows from 5 to 6. Note the rationale of
`M0243-NEAR20-T3` contains `"dose:"`, a `DOSE_MARKER` — that arm is correctly `not-checked` and
this phase does not touch it. The new arm's rationale contains `"placebo"` and `"hash order"`
(both `DRAW_MARKERS`) and none of `DOSE_MARKERS`; the test in Step 4 pins that.

#### 3c. Attach the amendment

**File:** `m0243_shrinkers_near_high.py:354-358`
**Code:** replace

```python
    seen_keys=(
        "concept:buyback-shrinkers-near-high",
        "concept:net-share-issuance-nearness-filter",
    ),
)
```

with

```python
    seen_keys=(
        "concept:buyback-shrinkers-near-high",
        "concept:net-share-issuance-nearness-filter",
    ),
    amendments=(MATCHED_DRAW_AMENDMENT,),
)
```

---

### Step 4: `test_lab_control_draw.py` — the verification that sees no return

**File:** `engine/tests/test_lab_control_draw.py` (new)
**Change:** create the module. Everything in it is free: no store, no database, no backtest.
**Code:**

```python
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
from seer_engine.strategies.allocator import last_close

TAG = "TEST"
SEED = 1
TOP = 3
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
    of them with the highest close that day. The smoke prices cross each other often, so the book
    genuinely churns and the match is not asserted against a book that never moves."""

    def select(d: date) -> tuple[tuple[str, ...], tuple[str, ...]]:
        pool = [
            s for s in MEMBER_STOCKS
            if s in market.history and market.history[s].index_of(d) is not None
        ]
        if not pool:
            return (), ()
        ranked = sorted(pool, key=lambda s: (-last_close(market.history[s], d), s))
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
    assert checked >= 20, f"only {checked} decisions on the fixture; that proves nothing"
    assert churn > checked, "the synthetic book never churned, so the match came for free"


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
    """``hardgate._INGREDIENT`` is ``<(M\\d{4})>``, so ``<M0227-A1>`` matches nothing and D12's
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
```

**Impact:** adds one test module. `test_lab_methods.py` picks the two new candidates up
automatically through its registry walk, so the allocator contract, the allocator-id uniqueness
check and the digest freeze all run against them with no edit to that file.

---

### Step 5: Green the tree, then the real-store shape probe

Nothing is committed and no lab command is run until both of these pass.

**5a. Tests and lint** (free):

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
export PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src
/home/miftah/seer/engine/.venv/bin/ruff check engine
/home/miftah/seer/engine/.venv/bin/pytest engine/tests/test_lab_control_draw.py \
    engine/tests/test_lab_methods.py engine/tests/test_lab_amendments.py \
    engine/tests/test_backtest_dev.py -q

# The grep the whole supersession mechanism rests on: no call site passes a WHOLE Candidate to
# registry._canon, so _canon's dataclasses.fields() walk never meets one and a trailing
# defaulted field on Candidate cannot move a recorded digest. Every hit must be `_canon(c.rules)`,
# `_canon(c.params)`, a recursive `_canon(v)` inside _canon itself, or a docstring.
grep -rn '_canon(' engine/src/seer_engine/ | grep -v 'def _canon'
```

`test_every_recorded_configuration_still_digests_to_its_recorded_digest` is the one that must be
green here: it is the proof that nothing recorded moved. `test_backtest_dev.py` joins the set
because this phase adds a field to `Candidate`; if that module pins the constructor's signature
or its field list, this is where it says so, and the fix is to extend that pin rather than to drop
the field.

**5b. The shape probe on the real store** — computes no return, writes nothing, never opens the
lab database. Write it to the scratchpad, not the repo.

**File:** `/tmp/claude-1000/-home-miftah-seer/<session>/scratchpad/churn_probe.py`

```python
"""Shape only: how many basket changes does the matched draw make against the arm it controls?

No return is computed, no fee is modelled, nothing is written and the lab database is never
opened. It walks the monthly decision dates of the dev window, asks each pilot allocator for its
targets exactly as book_runner would, and counts basket changes on both sides. The ratio it prints
is a PROXY for `trials.trades` -- real trades include fills and resizes this does not model -- so
it is read as a go/no-go on the derivation, never as the recorded number.
"""

from __future__ import annotations

import os
from pathlib import Path

from seer_engine import dates, research
from seer_engine.backtest.dev import DEV_END, MEMBERSHIP_START
from seer_engine.lab.methods import m0227_net_share_shrinkers as m0227
from seer_engine.lab.methods import m0243_shrinkers_near_high as m0243
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, is_rank_session

STORE = Path(os.environ["SEER_RESEARCH_STORE"])


def decision_dates():
    return [
        dates.prev_session(s)
        for s in dates.sessions(MEMBERSHIP_START, DEV_END)
        if is_rank_session(MONTHLY_HOLD_FRAC_GOTRADE, s)
    ]


def probe(market, allocator, params, label):
    prepared = allocator.prepare_market(market)
    held = frozenset()
    real_held = frozenset()
    real_changes = 0
    ctl_changes = 0
    months = 0
    for d in decision_dates():
        members = market.membership.members_on(d)
        _, real_now = allocator._select(prepared, members, d, params)
        if not real_now:
            continue
        book = [t.symbol for t in allocator.targets_prepared(prepared, members, d, held, params)]
        real_changes += len(set(real_now) - real_held) + len(real_held - set(real_now))
        ctl_changes += len(set(book) - held) + len(held - set(book))
        held, real_held = frozenset(book), frozenset(real_now)
        months += 1
    ratio = ctl_changes / real_changes if real_changes else float("nan")
    print(f"{label}: {months} decisions; book {real_changes} basket changes, "
          f"control {ctl_changes}; ratio {ratio:.3f}")
    return ratio


def main():
    data = research.load_store(STORE)
    market = data.market
    a = probe(market, m0227.MATCHED, m0227.IssuanceParams(20, side="random", seed=1),
              "M0227-S20-PLC vs M0227-S20")
    b = probe(market, m0243.MATCHED_NEAR,
              m0243.NearShrinkParams(20, pick="random", seed=1),
              "M0243-NEAR20-PLC vs M0243-NEAR20")
    for label, r in (("M0227", a), ("M0243", b)):
        verdict = "GO" if 0.70 <= r <= 1.40 else "FALLBACK (rule C)"
        print(f"{label}: {r:.3f} -> {verdict}")


if __name__ == "__main__":
    main()
```

Run it:

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src \
/home/miftah/seer/engine/.venv/bin/python \
    /tmp/claude-1000/-home-miftah-seer/<session>/scratchpad/churn_probe.py \
    > /tmp/claude-1000/-home-miftah-seer/<session>/scratchpad/churn_probe.log 2>&1
echo "exit=$?"
cat /tmp/claude-1000/-home-miftah-seer/<session>/scratchpad/churn_probe.log
```

Redirection, never a pipe: a pipe would hand the exit code to the last stage.

**If either ratio is outside [0.70, 1.40]:** stop. Do not commit either method file. Write
`phase-1-results.md` with verdict `STOP`, the two measured ratios and the reason, and either
implement Rule C in `control_draw.py` (a second function beside `matched_names`, not a tuned
constant inside it) and re-probe, or hand the fan-out a STOP. Nothing is pre-registered and
nothing is recorded, so this costs no method id, no trial and no N.

**Expected cost:** loading the dev store is one to two minutes; the two probes are about a minute
each (238 decisions x two `scored_pool` passes).

---

### Step 6: Commit the pre-registration, one file at a time

The checkout is shared with the other phase sessions. Commit by pathspec; never `git add -A`,
never `git reset --hard`, never `git pull --rebase` while the batch is running.

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw

# the rule and its test first: they are not a pre-registration, they are the mechanism
git add engine/src/seer_engine/lab/control_draw.py engine/tests/test_lab_control_draw.py
git commit -m "lab: the matched draw -- one rule for a shape-matched control

Thirteen control arms across nine dev-eligible methods sit outside D17's refuse band, in
two opposite directions: M0227-R20 traded 0.07x the arm it controls because its hash order
carries no date, and M0243-NEAR20-R traded 3.01x because it is redrawn in full every month.
M0243's own file says it was written to fix M0227's miss; it overshot. The hand-chosen
re-key period is the bug.

control_draw derives it instead. At each decision the control recomputes the arm it
controls at this decision and the one before, keeps all but e of its own names in a
date-free hash order and draws e fresh ones in a month-keyed hash order, where e is how
many names the real arm is adding. Entries match by construction, so the trade ratio is
~1.00 arithmetically rather than by calibration; M0241's cohort mirror, the lab's previous
best, measures 1.372x/1.131x.

test_lab_control_draw asserts the derived previous-decision date against
sim.rules.is_rank_session on every monthly decision of the dev window, and the entry and
exit counts session by session on the smoke fixture. No backtest, no store, no database.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  -- engine/src/seer_engine/lab/control_draw.py engine/tests/test_lab_control_draw.py

# M0227's pre-registration: this commit IS the pre-registration, and it precedes the run
git add engine/src/seer_engine/lab/methods/m0227_net_share_shrinkers.py
git commit -m "lab: M0227 amendment 1 pre-registered -- an honest control for S20

R20 draws in a hash order of (seed, symbol) with no date term, so it traded 41 times in
nineteen years against S20's 608: 0.07x, and a control that does not trade does not pay
Gotrade's fees. S20's recorded +5.22 point lead (12.95% against 7.73% on the owner's
deposits, SPY TR 7.19%) was quoted against a handicapped opponent.

S20-PLC is the same scored pool, the same twenty equal slots, the same monthly clock and
the same fees, drawn by lab/control_draw.py's matched rule. Pre-registered direction: the
honest control pays about fifteen times R20's fee bill, earns LESS than 7.73%, and S20's
lead WIDENS.

New allocator id M0227-A1 over R20's own IssuanceParams value, reused byte for byte:
registry._canon renders a dataclass by dataclasses.fields(), so a field on IssuanceParams
would move all five recorded M0227 digests and all five M0243 ones, while the allocator
line alone makes this a configuration the lab has not run.

Candidate gains a defaulted supersedes field, outside config_digest by construction
(config_text and candidate_text name their fields by hand; nothing passes a Candidate to
_canon). S20-PLC declares it supersedes M0227-R20, which is what D17 will read.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  -- engine/src/seer_engine/lab/methods/m0227_net_share_shrinkers.py

git status --porcelain -- engine/src/seer_engine/lab/methods/m0227_net_share_shrinkers.py
# must print nothing: runner.registry_problem refuses a dirty or untracked method file
```

Commit `m0243_shrinkers_near_high.py` the same way, with the message
`lab: M0243 amendment 1 pre-registered -- an honest control for NEAR20` and the mirrored body
(3.01x, over-paid, pre-registered direction: earns MORE, the +6.07 lead NARROWS or REVERSES).

**Impact:** the method files now hash to something no `method_amendments` row holds. That window
is the mechanism, not a hole:
`test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` tolerates exactly this when
`runner.pending_amendment` resolves, so the suite stays green between the commit and the run.

---

### Step 7: The two runs

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
export SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite
export SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research
export PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src
PY=/home/miftah/seer/engine/.venv/bin/python
LOG=/tmp/claude-1000/-home-miftah-seer/<session>/scratchpad

git -C /home/miftah/seer hash-object lab/lab.sqlite      # record: before M0227

$PY -m seer_engine lab run M0227 --amend > "$LOG/m0227_amend.log" 2>&1
echo "exit=$?"            # 0 ok, 2 the lab refused, 1 an error. Never judged through a pipe.
tail -60 "$LOG/m0227_amend.log"

git -C /home/miftah/seer hash-object lab/lab.sqlite      # record: after M0227, before M0243

$PY -m seer_engine lab run M0243 --amend > "$LOG/m0243_amend.log" 2>&1
echo "exit=$?"
tail -60 "$LOG/m0243_amend.log"

git -C /home/miftah/seer hash-object lab/lab.sqlite      # record: after M0243
```

Each run prints its own control-shape reading at `commands/lab.py:1751-1798` and refuses nothing
(D15). The method's status is not moved — an amendment appends trials.

**Then the verdict:**

```bash
$PY -m seer_engine lab control M0227 M0243 > "$LOG/control_after.log" 2>&1
echo "exit=$?"
cat "$LOG/control_after.log"
```

`lab control` writes no row but it is a `lab` command, so it migrates on connect; that is why the
hashes above are recorded around every step and why **this phase never commits `lab.sqlite`**
(invariant 8: `lab stage` runs once, in phase 8).

**The margins, read without a `lab` command** (a read-only URI never migrates):

```bash
sqlite3 "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" <<'SQL'
.mode column
.headers on
SELECT t.method_id, t.candidate_id, t.n, t.trades, t.turnover,
       round(f.mwr, 2) AS mwr, round(f.spy_tr_mwr, 2) AS spy_tr
FROM trials t JOIN trial_funding f ON f.trial_n = t.n
WHERE t.window = 'dev'
  AND t.candidate_id IN ('M0227-S20','M0227-R20','M0227-S20-PLC',
                         'M0243-NEAR20','M0243-NEAR20-R','M0243-NEAR20-PLC')
ORDER BY t.method_id, t.n;
SQL
```

**Exit codes:** 0 ok, 2 the lab's rules refused the request, 1 an error. A 2 on `lab run --amend`
is almost always `registry_problem` (a dirty or untracked method file) or `pending_amendment`
(the file's block does not match the record field for field). Fix the cause; never force.

---

### Step 8: Write the gate the fan-out reads

**File:** `.workflows/plan/honest-control-redraw/phase-1-results.md` (new)

This is the **authoritative** GO/STOP file. Phases 3–7 read it before they write a line of code,
and so does the swarm coordinator. It is written in **both** outcomes, never skipped.

```markdown
# Phase 1 result: the matched draw, measured on both poles

**Written:** 2026-10-19
**Verdict:** GO | STOP          <- one word, and it is the first thing a reader needs
**Rule:** `seer_engine.lab.control_draw`, `RULE_ID = "matched-draw-v1"` (Rule A, churn-matched)

## The shape, measured by `lab control M0227 M0243`

| method | new control | controls | trades x | turnover x | verdict |
|---|---|---|---|---|---|
| M0227 | `M0227-S20-PLC` | `M0227-S20` | _ | _ | ok / warn / refuse |
| M0243 | `M0243-NEAR20-PLC` | `M0243-NEAR20` | _ | _ | ok / warn / refuse |

Band: `WARN_BAND = (0.80, 1.25)` on BOTH axes is the bar. `REFUSE_BAND = (0.50, 2.00)` is not.

## The margins, in `trial_funding.mwr` (SPY TR on the same deposits: 7.19%/yr)

| arm | old control | old mwr | old margin | new control | new mwr | new margin |
|---|---|---|---|---|---|---|
| `M0227-S20` 12.95 | `M0227-R20` | 7.73 | +5.22 | `M0227-S20-PLC` | _ | _ |
| `M0243-NEAR20` 10.45 | `M0243-NEAR20-R` | 4.38 | +6.07 | `M0243-NEAR20-PLC` | _ | _ |

Pre-registered directions: M0227's lead WIDENS, M0243's lead NARROWS or REVERSES. State for each
whether the direction held, and say so plainly if it did not.

## What phases 3-7 do now

- **GO:** apply `control_draw.matched_book` exactly as `m0227_net_share_shrinkers.py` and
  `m0243_shrinkers_near_high.py` do. Decide nothing: new params dataclass, new allocator id
  `<METHOD>-A<seq>`, candidate id `<target>-PLC`, `tag` = the book's method id, `seed=1`,
  `lookback_for(inner)`. Copy the two guard tests at the foot of `test_lab_control_draw.py`.
- **STOP:** do not start. The reason and the measured ratios are above. The fix is a new rule in
  `control_draw.py` (the named fallback is Rule C, the persistence-inherited permutation), never
  a tuned seed and never a second draw of the same arm because a margin came out wrong.

## Database

`git hash-object lab/lab.sqlite`: before _, after M0227 _, after M0243 _. Trials added: 2.
Amendments added: 2 (`M0227` seq 1, `M0243` seq 1). Test-window looks spent: 0 — still 4 lifetime.
```

Commit it by pathspec. **The plan index is not touched** — its Reconciliation Log is the
reconciler's and its **Status** line is Phase 8's, and the index already points at this file as
the gate, so a reader who only has the index finds it:

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
git add .workflows/plan/honest-control-redraw/phase-1-results.md
git commit -m "lab: phase 1 result -- the matched draw's measured shape on M0227 and M0243

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  -- .workflows/plan/honest-control-redraw/phase-1-results.md
```

If this session is running under the `swarm` skill, the same one-line verdict goes in the report
back to the coordinator. The gate file is the record; the report is the notification.

---

## The stop condition, as a hard rule

> **If either `M0227-S20-PLC` or `M0243-NEAR20-PLC` lands outside `WARN_BAND` (0.80–1.25) on
> either the trades axis or the turnover axis, phase 1 writes
> `.workflows/plan/honest-control-redraw/phase-1-results.md` with verdict `STOP`, the two measured
> ratios and the reason, and the fan-out (phases 3, 4, 5, 6, 7) DOES NOT START.**

Clarifications, so nobody has to interpret it:

- Inside `REFUSE_BAND` but outside `WARN_BAND` is a **STOP**. R1's bar is the match band, not the
  refuse band; a `warn` arm would unblock `lab promote` while leaving the quoted margin only
  partly honest, and the rule would be carried into twelve more arms untested.
- The stop is on **shape only**. A margin that worsens, vanishes or reverses is a GO and is the
  finding (invariant 4, design §4). Re-drawing until a margin survives is forbidden outright.
- A STOP is cheap afterwards and expensive beforehand, which is why Step 5b's probe exists: it
  catches a broken derivation before any trial is recorded, for the price of three minutes of
  compute and no method id.
- Phase 2 is **not** gated by this. It owns `control_shape.py` / `hardgate.py` / `commands/lab.py`,
  depends on nothing, and is correct whether or not a single honest control ever exists — its own
  exit criteria require it to prove it is a no-op on today's lab.

---

## Verification

**Build / lint:**
```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
/home/miftah/seer/engine/.venv/bin/ruff check engine
```

**Tests:**
```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src \
  /home/miftah/seer/engine/.venv/bin/pytest engine/tests
```
Without `PYTHONPATH` pytest silently tests the main checkout instead of this branch. The DB tests
need `PG_TEST_URL`; CI fails if they skip. `test_lab_snapshot` is red mid-batch by design
(invariant 8) — it reads the working tree and `lab stage` does not run until phase 8.

Must be green, specifically:
- `test_lab_methods.py::test_every_recorded_configuration_still_digests_to_its_recorded_digest`
- `test_lab_methods.py::test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha`
- `test_lab_methods.py::test_allocator_ids_are_unique_across_methods`
- `test_lab_methods.py::test_allocator_contract[M0227-S20-PLC]` and `[M0243-NEAR20-PLC]`
- the whole of `test_lab_control_draw.py`

**Manual check:**
- `lab control M0227 M0243` shows both new arms, both resolved by `sibling-stem` to
  `M0227-S20` and `M0243-NEAR20`, both with a measured ratio on both axes.
- The old arms `M0227-R20` and `M0243-NEAR20-R` still appear and still read `refuse`. That is
  correct and is phase 2's problem, not this one's.
- `git hash-object lab/lab.sqlite` recorded three times (before, between, after) and written
  into the gate file.
- The test-window look count is still 4. `lab test` was never invoked and
  `SEER_RESEARCH_TEST_STORE` was never read.

**Exit criteria:**
1. `engine/src/seer_engine/lab/control_draw.py` exists, holds the rule in one place, and its
   docstring names the 0.07x pole, the 3.01x pole, M0241's 1.372x, the chosen rule (A), the
   fallback (C) and the one residual.
2. `engine/tests/test_lab_control_draw.py` asserts the derived previous-decision date against
   `is_rank_session` over the whole dev window, and the per-decision entry and exit counts on the
   smoke fixture — all before any backtest.
3. Both amendment blocks were committed **before** their `lab run --amend`; both runs recorded one
   trial each and one `method_amendments` row each (`M0227` seq 1, `M0243` seq 1).
4. `lab control M0227 M0243` reports both new arms inside `WARN_BAND` on both axes — or
   `phase-1-results.md` says `STOP` with the measured ratios.
5. Both margins are written down in `trial_funding.mwr` against SPY TR 7.19%/yr, with the
   pre-registered direction and whether it held.
6. `pytest engine/tests` and `ruff check engine` green; no recorded `config_digest` moved; no
   `lab.sqlite` committed.

---

## Handoffs

- **Phase 2 (R4)** — the whole supersession problem. `mis_shaped_controls` returns every recorded
  arm outside the band and `hardgate.check` raises on a non-empty tuple, so `M0227-R20` and
  `M0243-NEAR20-R` keep refusing `lab promote` forever no matter how honest their replacements
  are. This phase deliberately does not touch `control_shape.py`, `hardgate.py` or
  `commands/lab.py`. R4 is not in this phase's `satisfies` list and nothing here serves it.
- **Phases 3–7 (R2, R3)** — the other twelve arms. They consume `control_draw` as a settled
  contract; the five rules they must not re-decide are listed under **Interface Contract**.
- **Phase 3 specifically** — pass `tag="M0221"` for *both* twins. `test_one_tag_draws_one_book_so_
  a_twin_pair_can_share_it` is the test that explains why. M0225's amendment is **seq 2** and its
  allocator id is `M0225-A2`; leave the E100 block byte-identical or `pending_amendment` refuses.
- **Phase 4 — M0047 is a MONTHLY chassis and the brief was wrong about it.** `REPICK_MONTHS` and
  `KEEP_PCT` appear in `m0047` only inside `placebo_order` (`:189-202`); the residual arms take a
  fresh `one_per_company(order, 20)` at every monthly decision (`:244-248`). The quarterly band is
  the handicap being removed, not a property to reproduce, so M0047 calls
  `previous_decision_date` and matches the monthly churn. Phase 4 states this correction in its
  own plan and it is the reconciled reading.
- **Phase 5 — M0201 and M0202 are NOT, and must not call `previous_decision_date`.** Their shared
  `_run` passes an empty `frac` on every non-`REPICK_MONTHS` month, so the basket moves only
  quarterly, behind M0197's 40% keep band, and there is no monthly entry count to match. Phase 5
  derives its own previous re-pick in its own two files and measured 0.955 of the real book's
  entries over the dev window's 79 re-picks. It consumes `matched_partition`, `churn`, `keep_key`
  and `entry_key` from this module and nothing else. That split is the reconciled reading and the
  docstring of `previous_decision_date` carries it.
- **Phases 4 and 5** — the two mis-resolutions the ladder currently guesses at
  (`M0047-PLC1-MV10`/`-MV20` resolve to `M0047-EQ` by `first-declared`;
  `M0202-PLC1-HALF-FAST` resolves to `M0202-Y20-HALF`). Naming the new arms `<true target>-PLC`
  fixes both, and the margin is re-stated against the **true** target. Not this phase's arms.
- **Phase 8** — the close-out table, `lab insight`, the merge, the single `lab stage`, the push.
  This phase commits no database and no `web/data/lab.json`.
- **Deliberately not done here (no scope creep):**
  - `lab gate`'s `gate_probe.gate_off` introspects params for a gate site. The reused
    `IssuanceParams` and `NearShrinkParams` carry a `trend` field so a future `lab gate M0227`
    finds one, but no `lab gate` run is part of this phase and none was verified.
  - **`RULE_ID` is stamped nowhere.** An earlier draft of this phase minted a params dataclass per
    method so its `as_dict` could carry `"draw": control_draw.RULE_ID`; the reconciled rule reuses
    the replaced arm's params value instead, so that stamp is gone. The construction that drew a
    control is identified by its **allocator id** (`<M0227-A1>`), which *is* in `config_digest`,
    and `RULE_ID` stays in the module as the name of the rule for the close-out and the commit
    messages to cite. Surfacing a draw-construction column in `lab show` or on `/sera` is not this
    phase's work.
  - `control_draw.CADENCES` holds `("monthly",)` only. A weekly or daily matched draw needs its
    own derivation and its own test; nothing in the nine needs one.

---

## Rollback

**Before either run** (nothing is recorded yet): `git revert` the three commits, or simply delete
`control_draw.py` and `test_lab_control_draw.py` and `git checkout --` the two method files. The
`Amendment` block is pre-registration only until `lab run --amend` executes it. Cost: zero.

**After a run** (that run's trial is recorded): **not reversible.** `trials`, `trial_funding` and
`method_amendments` all carry append-only triggers on update *and* delete. The `Amendment` block
must therefore stay in the method file forever — removing it would break
`store.latest_source_sha` and `pending_amendment` for that method. The correct rollback is a
journalled note saying the arm ran and what it showed, which phase 8 writes as a `lab insight`
either way. **This is exactly why Step 6 puts the whole pre-registration in the commit that
precedes the run, and why Step 5b's probe is paid for before the commit.**

**Partial state** (M0227 ran, M0243 did not): legal and self-consistent. Revert only the M0243
commit, leave M0227's amendment in place and recorded, and write `phase-1-results.md` with the one
pole that was measured and the reason the other was not. One pole proves half of R1 and the gate
file must say which half.

**`control_draw.py` after a run:** frozen in behaviour, not in file. Every recorded trial's
`config_digest` names `<M0227-A1>` and the reused params value, and the digest does not cover this
module's code — so an edit here would silently change what a recorded arm means.
`matched_names`, `keep_key`, `entry_key` and `previous_decision_date` are closed records from the
moment the first trial lands. A different rule is a new function beside them and a new `RULE_ID`,
never an edit to these.
