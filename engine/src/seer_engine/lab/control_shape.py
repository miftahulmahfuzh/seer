"""``lab control``'s engine: is a placebo actually shaped like the book it controls?

A lab method that wants to prove its signal is real declares a control arm -- a placebo, a blind
draw, names pulled out of a hash in the same frame -- and then quotes the gap between the two as
the signal's worth. That claim is only as good as the match. If the control trades three times as
often, it pays three times the fees, and the "signal beats the blind draw by N points" sentence is
quoted against an opponent running with weights on. The lab has written this rule down twice, in
its own memory, after being bitten by it twice:

- *match the placebo to the book's exact shape* -- derive the control's name count from the real
  book's own calendar. On M0241 that split a 3.8 point lead into 1.9 points of shape and 1.9
  points of signal, which is to say half the finding was never there.
- *two things are both called "the placebo"* -- a sticky draw and a monthly re-drawn draw differ by
  fourteen times in turnover, so "grep the draw for a date term before trusting an inherited
  control". The turnover axis below is exactly that grep, made mechanical.

Nothing in the lab checked either rule. ``M0248-R``, the blind draw whose gap carries the claim
*"all six arms beat the blind draw by 3.6-13.5 points, so the buyback signal itself is real"*,
trades **3.18x** and turns over **3.08x** the arm it controls. ``M0230-C50-R`` is the mirror
failure: it trades **0.067x** -- it barely trades at all -- so the book it controls is being asked
to beat a stone. Both were caught by a human reading a table, months apart, and the second human
had already written the memory note from the first.

**What this module does, and what it refuses to do.** It answers three questions over rows the lab
has already recorded, and it answers each of them as a value rather than as a decision:

1. *Which arms are shape-matched controls?* -- from the candidate's one-line ``rationale``.
2. *Which arm does each one control?* -- a four-rung ladder, and the rung is reported.
3. *Is the shape matched?* -- recorded ``trials.trades`` and ``trials.turnover``, as ratios
   against the resolved arm, read through a calibrated band.

It decides nothing. ``commands/lab.py`` owns where a ``warn`` is printed and where a ``refuse``
stops a promotion; this file owns only what is true. That split is the lab's own (D15): a run-time
gate "would only spend method ids to say what the first one already says", so the loud flag lives
at ``lab run`` and the refusal at ``lab promote``, and both read the same ``Finding``.

---

**Why the rationale and not the candidate id.** Every control arm in the lab carries a suffix that
looks diagnostic -- ``-R``, ``-RAND1``, ``-PLACEBO``, ``-HASH`` -- and the suffix is a trap.
``M0005-ALL-R``'s rationale is *"The same composite with linear rank weights: does conviction in
the top names pay"*: a rank-weighting variant, not a control at all. An id-suffix rule calls it a
control, compares it to ``M0005-ALL``, happens to find 1.00x / 1.07x, and passes -- so the error
never surfaces and the next ``-R`` that is a real variant is judged the same wrong way. The
``rationale`` is one line, non-empty, enforced at construction (``backtest.dev.Candidate``), and
**outside** ``config_digest`` (``lab.method.config_text`` reads rules, allocator id and params
only), so reading it moves no recorded digest and costs nothing.

**Why the markers are a measured list and not a clever regex.** ``DOSE_MARKERS``,
``DRAW_MARKERS``, ``ABLATION_MARKERS`` and ``IDEA_MARKERS`` below were derived by scanning all 770
candidates in the lab's 271 method files on 2026-10-19 and keeping only phrases that actually
fire. Each entry's hit count is recorded beside it. Five phrases that sound like they belong --
"blind draw", "randomly drawn", "coin-flip", "drawn at random", "random draw" -- hit **nothing**
and are deliberately absent: a constant with no measurement behind it is a guess, and this lab
writes down where its numbers came from. The forward path for a method written tomorrow is
``DECLARATION_ATTR``, not a wider guess.

**Why existing method files are reached by detection alone.** ``methods.source_sha`` is written
once and trigger-protected, and ``store.latest_source_sha`` demands the file on disk still hash to
it. Adding a ``controls=`` keyword to M0230's or M0248's file would break that check for a method
whose trials are already recorded. So the twelve arms the lab already holds are reached by reading
what they already say, and a declaration is for methods that have not run yet.

---

**The three kinds, and why only one of them is checked.**

===================  ======  =============  =================================================
kind                 arms    shape-checked  why
===================  ======  =============  =================================================
``placebo``          46      **yes**        its entire job is the book's shape with none of
                                            the book's identity; a mismatch is a handicap
``dose-response``    6       no             the arm is *supposed* to differ -- the different
                                            date, or the different mix, **is** the dose.
                                            ``M0244-STALE30`` sits at 0.28x trades against
                                            ``M0244-HARD30`` and that is the experiment
                                            working, not failing
``within-frame       2       no             an ablation (``M0248-B100``, pure buyback) is a
control``                                   signal arm in its own right; its trade count is
                                            a property of the signal being measured
===================  ======  =============  =================================================

``kind_of`` tests dose **before** draw, and the order is load-bearing. ``M0241-STALE``'s rationale
is *"...the dose-response control on the date itself"* -- it contains the word "control". A future
rationale reading "the placebo at a one-to-two-year dose" would, under the reverse order, be
shape-flagged forever on a correct arm. That permanent false alarm on a correct arm is the single
worst outcome available to this module, because a check nobody believes is worse than no check.

---

**The resolution ladder, and the thing that had to be excluded from it.**

1. ``declared`` -- the arm names its target outright, through ``DECLARATION_ATTR``. No method file
   does today (see above); this rung is for the ones written after the field lands.
2. ``sibling-stem`` -- the control's id with its last ``-`` segment removed, when that names a real
   arm: ``M0230-C50-R`` -> ``M0230-C50``, ``M0243-NEAR20-R`` -> ``M0243-NEAR20``. The strongest
   signal available, because the author chose to write the target's whole name into the control's.
3. ``declared-idea`` -- the arm whose rationale opens with "The idea:" or "The yardstick:":
   ``M0248-EQ`` (which is candidate **[2]**, not [0] -- do not assume the first), ``M0222-CORE``,
   ``M0226-CORE``.
4. ``first-declared`` -- the first eligible arm. A guess, and it is reported as one.

**Every rung draws only from arms that are not themselves placebo or dose-response.** Measured
2026-10-19: without that exclusion the ladder produced sixteen nonsense resolutions, all in the
three methods whose every arm is a placebo -- ``M0187`` (placebo hash order), ``M0193`` (sticky
placebo), ``M0207`` (busiest pool placebo). It reported ``M0193-S1-SW`` as a 13.7x refusal against
``M0193-S1``; both are placebos and neither controls the other. When no eligible arm exists the
verdict is ``UNRESOLVED``, which carries no ratio and **never refuses**. Fail open on "I cannot
tell who this controls", fail loud only on "I can tell, and it does not match" -- for the same
reason the dose arms are excluded.

The exclusion also moved two correct answers: ``M0215-HASH-CAP4``'s stem ``M0215-HASH`` is itself a
placebo, so it resolves past it to ``M0215-CTRL``; likewise ``M0202-PLC1-HALF-FAST``.

---

**The band is calibrated, not chosen.** Measured over every control arm the committed lab holds,
each against the arm this ladder resolves for it:

=====================  =========  ===========  ========
control                trades x   turnover x   verdict
=====================  =========  ===========  ========
M0244-PLACEBO30            1.015        0.984  ok
M0226-RAND1                0.979        6.934  refuse
M0222-RAND1                0.984        4.451  refuse
M0222-RAND2                1.063        8.856  refuse
M0226-RAND2                1.330       14.528  refuse
M0241-PLACEBO              1.372        1.131  warn
M0243-NEAR20-R             3.013        2.976  refuse
M0248-R                    3.180        3.078  refuse
M0230-C50-R                0.067        0.138  refuse
=====================  =========  ===========  ========

Clean arms sit at 0.98-1.02 on both axes. Every mis-shaped arm is at 2.98x or worse, or 0.14x or
less, on at least one axis. The widest gap in the evidence is between 1.372 and 2.976, and
``REFUSE_BAND = (0.5, 2.0)`` sits inside it with room on both sides. ``WARN_BAND = (0.8, 1.25)`` is
the tightest band that still passes the one genuinely clean arm. Both are log-symmetric --
``1.25 = 1/0.8``, ``2.0 = 1/0.5`` -- because trading twice as much and half as much are the same
sin, and an asymmetric band would say otherwise. ``M0241-PLACEBO`` is the single warn-only case,
and it warns against every plausible target (1.372/1.131 vs ``SPLIT12``, 1.520/1.088 vs
``FRESH20``, 1.779/0.762 vs ``SPLIT6``), so the band separates the evidence on the verdict and not
on a third decimal.

**Both axes are mandatory.** ``M0226-RAND2`` is at 1.330 on trades -- a warn, not a refusal -- and
14.528 on turnover. A trades-only check passes it outright. That single row is why
``verdict_of`` takes the worse of two numbers and never one.

Lab-wide over all 46 placebo arms: 19 refuse, 7 warn, 4 clean, 16 unresolved. The handover that
asked for this check knew of two mis-shaped controls. The measured answer is nineteen.

---

**A bent stick can be straightened, and then the straight one is the stick.** The refusal this
module feeds says so in its own words -- *"re-draw the control at the book's own trade count and
turnover and run it again as an amendment"* -- and until 2026-10-19 the code did not honour that
sentence. A method file is append-only in practice: its recorded trials pin its candidates, and
``trials`` is append-only by trigger, so the handicapped arm stays in ``all_candidates()`` and
keeps its row forever. Re-drawing therefore added a clean arm beside the bent one and changed
nothing at all: ``refusals`` still returned the bent one and ``hardgate`` still raised. Nine
dev-eligible methods would have done all of the measuring work and stayed exactly as blocked.

So a ``REFUSE`` or ``WARN`` finding is now **superseded** when the same method holds another
``placebo`` arm that is itself clean on both axes **and that NAMES it** in its own pre-registered
declaration (``SUPERSEDES_ATTR``). ``superseding_arm`` is that predicate and
``Finding.superseded_by`` carries its answer; ``refusals`` -- and only ``refusals`` -- drops a
superseded refusal, so the gate reads the honest draw and nothing else moves.

**Declared, and deliberately not inferred from the target.** The obvious rule was "a clean
placebo on the same ``target_id``", and it is wrong in both directions. Too strict: a re-drawn
arm named ``<target-id>-PLC`` is deliberately re-pointed at the book it actually controls, so
``M0047-MV10-PLC`` resolves to ``M0047-MV10`` while the arm it replaces resolves, by the ladder's
weakest rung, to ``M0047-EQ``; under equality M0047 and M0202 would do all the measuring and stay
blocked. Too loose: ``M0215-HASH`` and ``M0215-HASH-CAP4`` both resolve to ``M0215-CTRL``, so one
honest control of ``CTRL`` would excuse an arm that exists to price a cap. Equality is an
inference about intent from a resolution this module itself labels a guess; a declaration is the
author of the re-draw saying which measurement this one replaces, written into the commit that
pre-registers it and before any result exists. The report prints **both** targets -- the
superseded arm's and the superseding arm's -- so a re-point is something a reader sees.

**``WARN`` is superseded too, though it never blocked.** ``M0047-PLC1-MV20`` is 0.545x / 0.508x:
inside the refuse band, outside the match band, and every margin written against it is as little
evidence as its refused twin's. It stops no promotion, so retiring it changes no gate -- but a
reader meeting the honest number has to be told the old one was answered, and leaving one of a
re-drawn pair unmarked would say the opposite.

**The superseded row is still computed, still carries both ratios, and is still printed.** Its
``verdict`` stays ``REFUSE`` and ``flagged`` stays true. That is deliberate and it is the whole
difference between this and an amnesty: every sentence already written about that margin was
quoted against the handicapped opponent, and a reader who meets the new number needs to be able to
see the old one and what was wrong with it. ``blocking`` -- not ``refused`` -- is the property a
gate acts on.

**Why the superseding arm must be ``OK`` and not merely inside ``REFUSE_BAND``.** Measured over
the whole committed lab on 2026-10-19: with the tight rule, **zero** findings are superseded, so
the change moves no verdict anywhere. With the loose rule, one is -- ``M0047-PLC1-MV10`` (0.549x /
0.496x) would be retired by ``M0047-PLC1-MV20`` (0.545x / 0.508x), its own equally handicapped
twin, which clears ``REFUSE_BAND`` only because its turnover ratio rounds to the clean side of
0.50. A stick that is 0.545x as long as the book is not a measuring stick, and letting one retire
another would unblock a method with no honest control in existence. The band is unchanged and
unread anywhere new; it is the *match* band, ``WARN_BAND``, that the replacement has to clear,
which is the same bar every re-drawn arm in the 2026-10-19 plan set is held to.

**Four things do not supersede, each for its own reason.** A ``warn`` **superseder** (above) --
the arm doing the retiring must be inside the match band. An arm that **declares nothing** -- no
declaration, no supersession, however well-shaped it is and whatever it happens to resolve to;
this is why the rule is a measured no-op on the committed lab, where no arm declares anything at
all. An ``unresolved``, ``unrecorded`` or ``not-checked`` superseder -- absence is not evidence
(D16's sentence), and an arm that has been declared in a method file but not yet run is exactly
the state a half-finished re-draw is in; letting it supersede would unblock the method the moment
the *intention* was committed, before a single trial existed. A dose-response or ablation arm --
it is not a control of shape at all and carries no ratio, so it cannot be anybody's measuring
stick, and admitting it would turn ``kind_of``'s dose-before-draw ordering into a way to game the
gate by wording.

---

**A reader, not a writer.** No ``trials``, ``trial_moments``, ``insights`` or ``method_folds`` row
is inserted, no method status moves, no file is written. ``store.dev_trial_count`` and
``store.test_looks`` cannot change because nothing here executes anything but ``SELECT``. The one
query this module issues is pinned to ``window = 'dev'`` (``WINDOW``): the test window is a budget
spent once per method and no report may touch it, not even to count.

Pure: no clock, no randomness, no network, no research store, no printing. ``format_report``
returns a string; whoever wants it on a terminal prints it.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from seer_engine.backtest.metrics import DASH

# --------------------------------------------------------------------------- what we read

WINDOW = "dev"
"""The only window this module ever names. The test window is a budget, not a data source."""

DECLARATION_ATTR = "controls"
"""The attribute a candidate may carry to name the arm it controls, read with ``getattr``.

No candidate in the lab carries it today, and none can be made to: ``methods.source_sha`` is
written once and trigger-protected, so editing a method file whose trials are recorded breaks
``store.latest_source_sha`` for that method. Reading the attribute duck-typed rather than
importing a field costs nothing, keeps this module free of a ``backtest.dev`` dependency, and
works unchanged on the day a defaulted ``Candidate.controls`` field lands.
"""

SUPERSEDES_ATTR = "supersedes"
"""The attribute a re-drawn control names the arms it replaces in. Declared, never inferred.

Read exactly as ``DECLARATION_ATTR`` is -- ``getattr(arm, SUPERSEDES_ATTR, ())`` -- so this module
imports nothing from ``backtest.dev`` and an arm without the attribute simply declares nothing.
``backtest.dev.Candidate`` carries it as a defaulted, validated ``tuple[str, ...]`` from
2026-10-19; it is outside ``config_digest`` because ``lab.method.config_text`` and
``registry.candidate_text`` both name their fields by hand and nothing passes a whole
``Candidate`` to ``registry._canon``.
"""


def declared_supersessions(arm: Arm) -> tuple[str, ...]:
    """The candidate ids ``arm`` declares it supersedes. Duck-typed: see ``SUPERSEDES_ATTR``.

    Tolerant of anything that is not a tuple of non-empty strings, because this is a reader and
    every uncertainty it meets must become a verdict a human can see rather than an exception a
    caller has to catch. A malformed declaration therefore declares nothing, and the import-time
    validation in ``Candidate.__post_init__`` is what stops one being written in the first place.
    """
    declared = getattr(arm, SUPERSEDES_ATTR, ())
    if not isinstance(declared, (tuple, list)):
        return ()
    return tuple(s for s in declared if isinstance(s, str) and s)


# --------------------------------------------------------------------------- the markers
#
# Measured 2026-10-19 over all 770 candidates in the lab's 271 method files. The number beside
# each phrase is how many candidates it matches today. A phrase that matches nothing is not here.

DOSE_MARKERS: tuple[str, ...] = (
    "dose-response",             # 4: M0230-C70, M0230-C30, M0241-STALE, M0245-FALL63
    "dose:",                     # 1: M0243-NEAR20-T3 ("A stricter dose:")
    "and not since",             # 1: M0241-STALE
    "and none since",            # 1: M0244-STALE30
    "does the date do any work",  # 1: M0244-STALE30
    "on the date itself",        # 1: M0241-STALE
)
"""An arm whose difference in shape IS the measurement. Never shape-checked."""

DRAW_MARKERS: tuple[str, ...] = (
    "placebo",      # 18
    "hash-drawn",   # 7: M0222-RAND1/2, M0226-RAND1/2, M0230-C50-R, M0241-PLACEBO, M0244-PLACEBO30
    "hash order",   # 34
)
"""An arm whose names carry no information: the book's shape with none of its identity."""

ABLATION_MARKERS: tuple[str, ...] = (
    "within-frame control",  # 2: M0248-B100, M0248-D100
)
"""A signal arm with one ingredient removed. Reported, never shape-checked: its trade count is a
property of the ingredient under test, not a handicap."""

IDEA_MARKERS: tuple[str, ...] = (
    "the idea:",       # 3: M0107-STOCK200, M0230-C50, M0248-EQ
    "the yardstick:",  # 2: M0222-CORE, M0226-CORE
)
"""How a method names the arm its controls exist to be compared with."""

# --------------------------------------------------------------------------- the vocabulary

KIND_PLACEBO = "placebo"
KIND_DOSE = "dose-response"
KIND_ABLATION = "within-frame control"
KIND_NONE = ""

OK = "ok"
WARN = "warn"
REFUSE = "refuse"
UNRESOLVED = "unresolved"
UNRECORDED = "unrecorded"
NOT_CHECKED = "not-checked"

RUNG_DECLARED = "declared"
RUNG_STEM = "sibling-stem"
RUNG_IDEA = "declared-idea"
RUNG_FIRST = "first-declared"

WARN_BAND: tuple[float, float] = (0.8, 1.25)
"""Outside this, say so loudly. ``1.25 == 1/0.8``: the band is log-symmetric on purpose."""

REFUSE_BAND: tuple[float, float] = (0.5, 2.0)
"""Outside this, the control is handicapped and the gap it was quoted for is not evidence.
``2.0 == 1/0.5``. See the module docstring for the table these two pairs were cut from."""

_SEVERITY: Mapping[str, int] = {OK: 0, WARN: 1, REFUSE: 2}


class Arm(Protocol):
    """What this module needs from a candidate: its id and its one-line rationale.

    A ``backtest.dev.Candidate`` satisfies it. Stating it as a protocol rather than importing the
    class keeps a pure reader of recorded rows free of the registry's dataclass, and lets a test
    exercise the detection rules on three lines of prose instead of a whole runnable candidate.
    """

    id: str
    rationale: str


@dataclass(frozen=True, slots=True)
class Shape:
    """One arm's recorded shape: how often it traded and how much of the book it turned over.

    ``turnover`` is ``trials.turnover`` -- sum of fill notionals, both sides, over mean session
    equity, over years (``backtest.book_runner._turnover``). It is ``None`` only for a row that
    recorded none; no dev row in the committed lab does, but a fixture may.
    """

    candidate_id: str
    n: int
    trades: int
    turnover: float | None


@dataclass(frozen=True, slots=True)
class Finding:
    """One control arm, the arm it controls, and whether their shapes match.

    ``rung`` names which step of the ladder chose ``target_id``, so a resolution the author would
    dispute is visible in the output rather than buried in a ratio. ``reason`` is one plain
    sentence; ``describe`` wraps it with the ids.

    ``declares`` is what THIS arm says it supersedes, read off the candidate at construction
    through ``SUPERSEDES_ATTR``. ``superseded_by`` is the id of the later, band-clean arm that
    declared THIS one, and ``superseded_by_target`` is that arm's own resolved target -- which may
    differ from this one's, because the ``<target-id>-PLC`` convention deliberately re-points a
    re-drawn control at the book it actually controls. Both are set by ``_mark_superseded`` when
    ``findings`` has the whole method in hand. Printing both targets is the point: a reader who
    meets a re-pointed replacement must be able to see that it was re-pointed.

    A superseded finding keeps its ``REFUSE`` (or ``WARN``) verdict, both ratios and its reason,
    and is still printed: the old draw is the record of what every margin quoted against it was
    actually worth. Only ``blocking`` goes false, and only ``refusals`` reads ``blocking``.
    """

    method_id: str
    control_id: str
    kind: str
    target_id: str | None
    rung: str | None
    control: Shape | None
    target: Shape | None
    trade_ratio: float | None
    turnover_ratio: float | None
    verdict: str
    reason: str
    declares: tuple[str, ...] = ()
    superseded_by: str | None = None
    superseded_by_target: str | None = None

    @property
    def refused(self) -> bool:
        """True only for a measured mismatch outside ``REFUSE_BAND``. Never for an unknown.

        Still true once the arm is superseded: the measurement does not stop being what it was
        because a better stick was cut later. A gate wants ``blocking``.
        """
        return self.verdict == REFUSE

    @property
    def blocking(self) -> bool:
        """A refusal nothing has retired: what ``refusals`` keeps and what the hard gate acts on."""
        return self.verdict == REFUSE and self.superseded_by is None

    @property
    def flagged(self) -> bool:
        """True for anything a researcher should read before quoting the gap."""
        return self.verdict in (WARN, REFUSE)


# --------------------------------------------------------------------------- (1) detection


def kind_of(arm: Arm) -> str:
    """Which kind of control ``arm`` is, from its rationale; ``KIND_NONE`` when it is not one.

    Dose first. ``M0241-STALE`` says "the dose-response control on the date itself" and a
    draw-first order would one day catch an arm that calls itself a placebo at a given dose and
    flag a correct arm forever. See the module docstring.
    """
    text = str(arm.rationale).lower()
    if any(m in text for m in DOSE_MARKERS):
        return KIND_DOSE
    if any(m in text for m in DRAW_MARKERS):
        return KIND_PLACEBO
    if any(m in text for m in ABLATION_MARKERS):
        return KIND_ABLATION
    return KIND_NONE


def declared_target(arm: Arm) -> str | None:
    """The arm ``arm`` says it controls, or None. Duck-typed: see ``DECLARATION_ATTR``."""
    declared = getattr(arm, DECLARATION_ATTR, None)
    if declared is None:
        return None
    text = str(declared).strip()
    return text or None


# --------------------------------------------------------------------------- (2) resolution


def _eligible_targets(control: Arm, arms: Sequence[Arm]) -> list[Arm]:
    """The arms a control may be measured against: not itself, and not another control.

    Excluding other placebo and dose arms is what stops the ladder resolving ``M0193-S1-SW``
    against ``M0193-S1`` -- both placebos, neither controlling the other -- and reporting a 13.7x
    refusal. Measured: it turned sixteen false refusals into sixteen honest ``UNRESOLVED``.
    An ablation stays eligible: ``M0248-B100`` is a signal arm and a legitimate comparison.
    """
    out: list[Arm] = []
    for a in arms:
        if a.id == control.id:
            continue
        if kind_of(a) in (KIND_PLACEBO, KIND_DOSE):
            continue
        out.append(a)
    return out


def resolve_target(control: Arm, arms: Sequence[Arm]) -> tuple[str | None, str | None]:
    """``(target id, rung)`` for ``control``, or ``(None, None)`` when nothing is eligible.

    A declared target is returned even when no arm of that name exists: naming an arm that is not
    there is an author's mistake, and ``findings`` surfaces it as ``UNRECORDED`` rather than
    silently falling through to a guess that hides it.
    """
    declared = declared_target(control)
    if declared is not None:
        return declared, RUNG_DECLARED
    eligible = _eligible_targets(control, arms)
    stem = control.id.rsplit("-", 1)[0]
    if stem != control.id:
        for a in eligible:
            if a.id == stem:
                return stem, RUNG_STEM
    for a in eligible:
        text = str(a.rationale).lower()
        if any(m in text for m in IDEA_MARKERS):
            return a.id, RUNG_IDEA
    if eligible:
        return eligible[0].id, RUNG_FIRST
    return None, None


# --------------------------------------------------------------------------- (3) the band


def band_verdict(ratio: float) -> str:
    """``OK``, ``WARN`` or ``REFUSE`` for one ratio. The bands are inclusive at their edges."""
    low, high = REFUSE_BAND
    if ratio < low or ratio > high:
        return REFUSE
    low, high = WARN_BAND
    if ratio < low or ratio > high:
        return WARN
    return OK


def worst(verdicts: Iterable[str]) -> str:
    """The most severe of ``verdicts``; ``OK`` when none of them is a band verdict.

    Both axes go through here, and that is the whole reason both axes exist: ``M0226-RAND2`` is
    1.330x on trades -- a warn -- and 14.528x on turnover. Taking the worse of the two is what
    turns a pass into the refusal the evidence supports.
    """
    seen = [v for v in verdicts if v in _SEVERITY]
    if not seen:
        return OK
    return max(seen, key=lambda v: _SEVERITY[v])


def _ratio(mine: float | int | None, theirs: float | int | None) -> float | None:
    """``mine / theirs``, or None when either is missing or the denominator is zero.

    A zero denominator is real: five recorded dev rows have ``trades = 0`` (a partial-weight book
    records no trades even while its exposure moves). A ratio against zero is not large, it is
    undefined, and saying so is the honest answer.
    """
    if mine is None or theirs is None:
        return None
    theirs = float(theirs)
    if theirs == 0.0:
        return None
    return float(mine) / theirs


# --------------------------------------------------------------------------- recorded shapes


def shapes(conn: sqlite3.Connection, method_id: str) -> dict[str, Shape]:
    """Every dev arm of ``method_id`` by candidate id. Read-only; ``window = 'dev'`` always.

    ``trials`` carries ``UNIQUE (candidate_id, window)``, so one row per arm is guaranteed by the
    schema rather than by this query's ``ORDER BY``.
    """
    rows = conn.execute(
        "SELECT n, candidate_id, trades, turnover FROM trials "
        "WHERE window = ? AND method_id = ? ORDER BY n",
        (WINDOW, method_id),
    ).fetchall()
    out: dict[str, Shape] = {}
    for r in rows:
        turnover = r["turnover"]
        out[str(r["candidate_id"])] = Shape(
            candidate_id=str(r["candidate_id"]),
            n=int(r["n"]),
            trades=int(r["trades"]),
            turnover=None if turnover is None else float(turnover),
        )
    return out


# --------------------------------------------------------------------------- the findings


def _not_checked_reason(kind: str) -> str:
    if kind == KIND_DOSE:
        return (
            "a dose-response arm is supposed to differ in shape -- the different date or mix is "
            "the dose -- so its shape is the measurement and not a match to be checked"
        )
    return (
        "a within-frame control is a signal arm with one ingredient removed, so its trade count "
        "is a property of the ingredient under test and not a handicap"
    )


def superseding_arm(f: Finding, found: Sequence[Finding]) -> tuple[str, str | None] | None:
    """The honest control that retires ``f`` and its own target, or None when nothing does.

    ``f`` is retired only when **all** of these hold of some other finding ``g`` of the same
    method:

    - ``f`` is itself a measured placebo mismatch -- ``REFUSE`` or ``WARN``. Nothing retires an
      ``unresolved``, an ``unrecorded`` or a ``not-checked``, because none of them is a
      measurement. ``WARN`` is included because a warn arm is still outside the match band and
      every margin quoted against it is still quoted against a handicap; it does not block a
      promotion, but a reader meeting the new number still needs to be told the old one was
      answered. ``M0047-PLC1-MV20`` is the one such arm in this lab;
    - ``g`` is a ``placebo``. A dose-response or within-frame arm carries no ratio at all and is
      not a measuring stick for anyone's shape -- admitting one would make ``kind_of``'s
      dose-before-draw ordering into a way of clearing the gate by wording;
    - ``g``'s verdict is ``OK`` -- inside ``WARN_BAND`` on every axis it has, not merely inside
      ``REFUSE_BAND``. See the module docstring for the measurement: the loose reading lets
      ``M0047-PLC1-MV20`` (0.545x) retire ``M0047-PLC1-MV10`` (0.549x), one bent stick replacing
      another, on today's lab and with no honest control drawn at all;
    - ``g`` **names ``f.control_id`` in its own declaration** (``SUPERSEDES_ATTR``, carried on the
      finding as ``declares``).

    **There is no target-equality condition, and its absence is the decision this rule turns on.**
    Equality is an inference about intent drawn from a resolution the ladder itself reports as a
    guess, and it is wrong in both directions. Too strict: the ``<target-id>-PLC`` convention
    deliberately re-points a re-drawn arm at its TRUE target, so ``M0047-MV10-PLC`` resolves to
    ``M0047-MV10`` while the arm it replaces resolves to ``M0047-EQ`` -- under equality M0047 and
    M0202 would stay blocked after all the measuring. Too loose: ``M0215-HASH`` and
    ``M0215-HASH-CAP4`` both resolve to ``M0215-CTRL``, so one honest control of ``CTRL`` would
    excuse an arm that exists to price a cap and was never scored against ``CTRL`` in spirit. A
    declaration is the author of the re-draw saying which measurement this one replaces, before
    any result exists.

    The second element of the answer is ``g``'s own ``target_id``, so the caller can print both
    and a re-point is visible rather than hidden.

    Ties go to the first such arm in ``findings``' own order, so the answer is deterministic and a
    reader can find the arm in the file. Reads no band constant of its own: ``OK`` is already the
    band's answer.
    """
    if f.verdict not in (REFUSE, WARN) or f.kind != KIND_PLACEBO:
        return None
    for g in found:
        if g.control_id == f.control_id or g.method_id != f.method_id:
            continue
        if g.kind != KIND_PLACEBO or g.verdict != OK:
            continue
        if f.control_id not in g.declares:
            continue
        return g.control_id, g.target_id
    return None


def _mark_superseded(found: Sequence[Finding]) -> tuple[Finding, ...]:
    """``found`` with ``superseded_by`` filled in. Nothing is dropped and no verdict is moved.

    A second pass rather than a branch inside ``findings``' loop, because supersession is a
    property of the whole method and not of one arm: the arm that retires a refusal is in practice
    declared *after* it, at the foot of the file in an ``Amendment`` block.
    """
    out: list[Finding] = []
    for f in found:
        by = superseding_arm(f, found)
        if by is None:
            out.append(f)
        else:
            out.append(replace(f, superseded_by=by[0], superseded_by_target=by[1]))
    return tuple(out)


def findings(
    conn: sqlite3.Connection, method_id: str, arms: Sequence[Arm]
) -> tuple[Finding, ...]:
    """One ``Finding`` per control arm of ``method_id``, in declaration order.

    An arm that is not a control of any kind produces nothing at all -- a method with no control
    arm produces an empty tuple, which is the correct answer and not an error. Nothing is written
    and no ``LabError`` is raised: this is a reader, and every uncertainty it meets becomes a
    verdict a human can see rather than an exception a caller has to catch.

    The last thing it does is ``_mark_superseded``: a refusal that a later, band-clean control of
    the same arm has retired comes back carrying that arm's id. The refusal itself is untouched --
    same verdict, same ratios, same reason, same place in the order. This is the one step that
    needs the whole method at once, which is why it is a pass and not a branch in the loop above.
    """
    arms = tuple(arms)
    recorded = shapes(conn, method_id)
    out: list[Finding] = []
    for arm in arms:
        kind = kind_of(arm)
        if kind == KIND_NONE:
            continue
        mine = recorded.get(arm.id)
        if kind != KIND_PLACEBO:
            out.append(Finding(
                method_id=method_id, control_id=arm.id, kind=kind,
                target_id=None, rung=None, control=mine, target=None,
                trade_ratio=None, turnover_ratio=None,
                verdict=NOT_CHECKED, reason=_not_checked_reason(kind),
                declares=declared_supersessions(arm),
            ))
            continue
        target_id, rung = resolve_target(arm, arms)
        if target_id is None:
            out.append(Finding(
                method_id=method_id, control_id=arm.id, kind=kind,
                target_id=None, rung=None, control=mine, target=None,
                trade_ratio=None, turnover_ratio=None,
                verdict=UNRESOLVED,
                reason=(
                    "every other arm of this method is itself a control, so there is no book "
                    "whose shape this one was meant to match and nothing to compare it with"
                ),
                declares=declared_supersessions(arm),
            ))
            continue
        theirs = recorded.get(target_id)
        if mine is None or theirs is None:
            missing = arm.id if mine is None else target_id
            out.append(Finding(
                method_id=method_id, control_id=arm.id, kind=kind,
                target_id=target_id, rung=rung, control=mine, target=theirs,
                trade_ratio=None, turnover_ratio=None,
                verdict=UNRECORDED,
                reason=f"{missing} has no recorded dev trial, so there is no shape to compare",
                declares=declared_supersessions(arm),
            ))
            continue
        trade_ratio = _ratio(mine.trades, theirs.trades)
        turnover_ratio = _ratio(mine.turnover, theirs.turnover)
        axes = [band_verdict(r) for r in (trade_ratio, turnover_ratio) if r is not None]
        if not axes:
            out.append(Finding(
                method_id=method_id, control_id=arm.id, kind=kind,
                target_id=target_id, rung=rung, control=mine, target=theirs,
                trade_ratio=trade_ratio, turnover_ratio=turnover_ratio,
                verdict=UNRECORDED,
                reason=(
                    f"{target_id} recorded no trades and no turnover, so neither axis has a "
                    f"denominator and the shapes cannot be compared"
                ),
                declares=declared_supersessions(arm),
            ))
            continue
        verdict = worst(axes)
        out.append(Finding(
            method_id=method_id, control_id=arm.id, kind=kind,
            target_id=target_id, rung=rung, control=mine, target=theirs,
            trade_ratio=trade_ratio, turnover_ratio=turnover_ratio,
            verdict=verdict, reason=_shape_reason(verdict, trade_ratio, turnover_ratio),
            declares=declared_supersessions(arm),
        ))
    return _mark_superseded(out)


def _shape_reason(verdict: str, trade_ratio: float | None, turnover_ratio: float | None) -> str:
    trades = DASH if trade_ratio is None else f"{trade_ratio:.2f}x"
    turnover = DASH if turnover_ratio is None else f"{turnover_ratio:.2f}x"
    if verdict == OK:
        return f"trades {trades} and turns over {turnover} the arm it controls: a clean match"
    if verdict == WARN:
        return (
            f"trades {trades} and turns over {turnover} the arm it controls, outside the "
            f"{WARN_BAND[0]:.2f}-{WARN_BAND[1]:.2f} match band: read the gap with that in mind"
        )
    return (
        f"trades {trades} and turns over {turnover} the arm it controls, outside the "
        f"{REFUSE_BAND[0]:.2f}-{REFUSE_BAND[1]:.2f} band: the control carries a different cost "
        f"and a different cadence, so the gap between them is not evidence about the signal"
    )


def for_method(conn: sqlite3.Connection, method_id: str) -> tuple[Finding, ...]:
    """``findings`` for one method, reading its arms from its method file.

    ``()`` when no file declares ``method_id``. A method with no file cannot be promoted anyway --
    ``prereg`` refuses it on the source sha long before any caller reaches here -- so an empty
    answer is the absence of a control arm to judge, not a waiver.

    ``discover`` is imported inside the function, the way ``prereg`` and ``runner`` do it:
    importing it at module scope would import all 271 method modules on any import of this one.
    """
    from seer_engine.lab.method import discover

    found = discover()
    entry = found.get(method_id)
    if entry is None:
        return ()
    method, _path = entry
    return findings(conn, method_id, method.all_candidates())


def survey(
    conn: sqlite3.Connection, method_ids: Sequence[str] | None = None
) -> tuple[Finding, ...]:
    """Every control arm of ``method_ids``, or of every method file, by method id then declaration.

    This is the twelve-row table the handover asked for, except that measured over the whole lab
    it is forty-six rows: nineteen of them refuse.
    """
    from seer_engine.lab.method import discover

    found = discover()
    wanted = sorted(found) if method_ids is None else list(method_ids)
    out: list[Finding] = []
    for mid in wanted:
        entry = found.get(mid)
        if entry is None:
            continue
        method, _path = entry
        out.extend(findings(conn, mid, method.all_candidates()))
    return tuple(out)


def refusals(found: Iterable[Finding]) -> tuple[Finding, ...]:
    """Measured mismatches outside ``REFUSE_BAND`` that nothing has retired. What a gate acts on.

    Reads ``blocking`` and not ``refused``: an arm a later band-clean control of the same book has
    superseded stays in ``found``, stays flagged and still prints, but it no longer stops a
    promotion. The refusal said "re-draw the control and run it again as an amendment"; this is
    the line that makes doing so mean something.
    """
    return tuple(f for f in found if f.blocking)


def flags(found: Iterable[Finding]) -> tuple[Finding, ...]:
    """Everything a researcher should read before quoting a control gap: warns and refusals."""
    return tuple(f for f in found if f.flagged)


# --------------------------------------------------------------------------- saying it


def describe(f: Finding) -> str:
    """One sentence naming the control, the arm it controls and why the verdict is what it is.

    A superseded arm says so at the end, with the id of the arm that retired it, because this is
    the sentence the hard gate and both report surfaces quote and a reader meeting the old ratios
    needs to know they have already been answered.
    """
    if f.target_id is None:
        said = f"{f.control_id}: {f.reason}"
    else:
        said = f"{f.control_id} (against {f.target_id}, resolved by {f.rung}): {f.reason}"
    if f.superseded_by is None:
        return said
    aimed = (
        "" if f.superseded_by_target in (None, f.target_id)
        else f" (which controls {f.superseded_by_target}, not {f.target_id or 'this arm'})"
    )
    return (
        f"{said} -- superseded by {f.superseded_by}{aimed}, a later control that declares it "
        f"replaces this one and matches its own book's shape on both axes, so the gate reads that "
        f"one instead; this row stays because it is the record of what the margins written "
        f"against it were worth"
    )


def band_sentence() -> str:
    """The band and where it came from, in one line, for any report that prints a verdict."""
    return (
        f"a control is clean inside {WARN_BAND[0]:.2f}-{WARN_BAND[1]:.2f} on both trades and "
        f"turnover, flagged outside that, and refused outside "
        f"{REFUSE_BAND[0]:.2f}-{REFUSE_BAND[1]:.2f}; the band was cut from the lab's own control "
        f"arms, where clean ones sit at 0.98-1.02 and every mis-shaped one is past 2.9x or under "
        f"0.14x on at least one axis"
    )


_HEAD: tuple[str, ...] = (
    "method", "control", "kind", "controls", "resolved by", "trades x", "turnover x", "verdict",
)

_SUPERSEDED_HEAD = "superseded by"
"""The ninth column, added only when a row in the report has one.

A column that is a dash on every line of every report the lab prints today would be noise in
sixty-four rows to carry information in none of them. It appears when it says something, and every
report that has no superseded arm prints exactly the eight columns it printed before.
"""


def _head(with_superseded: bool) -> tuple[str, ...]:
    return (*_HEAD, _SUPERSEDED_HEAD) if with_superseded else _HEAD


def _cells(f: Finding, with_superseded: bool = False) -> tuple[str, ...]:
    row = (
        f.method_id,
        f.control_id,
        f.kind or KIND_NONE,
        f.target_id or DASH,
        f.rung or DASH,
        DASH if f.trade_ratio is None else f"{f.trade_ratio:.2f}",
        DASH if f.turnover_ratio is None else f"{f.turnover_ratio:.2f}",
        f.verdict,
    )
    if not with_superseded:
        return row
    if f.superseded_by is None:
        cell = DASH
    elif f.superseded_by_target in (None, f.target_id):
        cell = f.superseded_by
    else:
        # The replacement was deliberately re-pointed at its TRUE target. Print both, or a reader
        # sees one id retiring a row that names a different book and has no way to tell why.
        cell = f"{f.superseded_by} -> {f.superseded_by_target}"
    return (*row, cell)


def _table(head: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    """Head plus rows, columns padded to the widest cell.

    The first five columns are names and read left-justified; the ratios and the verdict are
    numbers and a word and read right-justified against them. ``superseded by`` is a candidate id,
    so it goes back to the left -- by its heading rather than by its index, because it is the last
    column only while it is the only optional one.
    """
    body = [tuple(head), *(tuple(r) for r in rows)]
    widths = [max(len(r[i]) for r in body) for i in range(len(head))]
    out: list[str] = []
    for k, row in enumerate(body):
        cells = [
            row[i].ljust(widths[i])
            if i < 5 or head[i] == _SUPERSEDED_HEAD
            else row[i].rjust(widths[i])
            for i in range(len(head))
        ]
        out.append("    " + "  ".join(cells).rstrip())
        if k == 0:
            out.append("    " + "  ".join("-" * w for w in widths))
    return out


def format_report(found: Sequence[Finding], *, show_clean: bool = True) -> str:
    """The table and the findings as text. The caller decides whether to print it.

    ``show_clean=False`` keeps only what a reader must act on, which is what the annotation at
    ``lab run`` wants; the standalone report shows everything, because a control that passed is
    the evidence the band is not simply refusing everything.

    A superseded arm is kept by **both** settings: it is still ``flagged``, because the sentence
    already written about its margin is still in the record and still wrong. The extra column and
    the paragraph under the table appear only when there is one.
    """
    rows = list(found) if show_clean else [f for f in found if f.flagged]
    out = [
        "control shape -- does each placebo carry the shape of the book it controls?",
        band_sentence(),
        "read from recorded dev trials only: nothing is run, nothing is written, and the test "
        "window is not touched.",
        "",
    ]
    if not rows:
        out.append(
            "    no control arm to report"
            if show_clean
            else "    no control arm to report: every one of them matches its book's shape"
        )
        return "\n".join(out)
    retired = [f for f in rows if f.superseded_by is not None]
    out += _table(_head(bool(retired)), [_cells(f, bool(retired)) for f in rows])
    bad = flags(rows)
    out.append("")
    if not bad:
        out.append("    every control arm shown matches the shape of the arm it controls")
    else:
        out.append("    what to read before quoting a control gap")
        for f in bad:
            out.append(f"      {describe(f)}")
    if retired:
        out.append("")
        out.append(
            "    superseded: a later control of the same arm matches its shape, so the gate reads "
            "that one. The"
        )
        out.append(
            "    row above stays, with its ratios, because every margin already written against "
            "it was quoted"
        )
        out.append("    against a handicapped opponent and the record of that has to stay readable.")
    return "\n".join(out)
