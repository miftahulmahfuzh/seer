"""``lab dressing``: what a timing rule KNOWS, apart from what its HABITS COST.

**The failure this exists to stop.** Every rule in this lab that steps out of the market mixes two
different things: an *opinion* about which months are bad, and a *habit* of holding cash -- or of
swapping funds -- to act on it. The lab scores the mixture and records the loss. Feature-wish 492
is the observation that the two can be separated exactly, for free, whenever a method ran a
reversed arm beside its straight one, and that the lab has been throwing away half of what it
measured by never printing them apart.

    direction  = (straight - reversed) / 2           what the opinion is worth, one-sided
    toll       = (straight + reversed) / 2 - endpoint  what the arrangement costs
    ratio      = direction / |toll|

``endpoint`` is the same book **never leaving the market**: for a cash ladder the always-invested
arm, for a two-fund switch a static half-and-half of the two funds. Averaging a straight arm with
its mirror cancels the opinion exactly -- the mirror says "cash" in precisely the months the
straight arm says "market", so the average holds a fixed amount that no longer depends on the
signal -- and what is left of it against the endpoint is everything the arrangement costs: the
fees, the churn, and the cash the arrangement sits in on average. That last term is a cost and
not an artefact. M0254's pair averages to 75% invested against an endpoint's 99%, and *being a
quarter in cash for twenty years* is exactly the habit the wish is asking the price of.

**What the two numbers answer**, in wish 492's own words: which of the rejected timing rules are
DEAD and which were only BADLY DRESSED. A ratio at or above 1 means the opinion is worth more than
the habits cost, and the rule deserves a cheaper chassis rather than the bin. A ratio below 1 at
every dose is dead by arithmetic: M0254 proved that dilution halves the direction and the toll
together, so the ratio is *invariant* down the dose ladder and no gentler setting can rescue a
rule whose full-strength ratio is under one.

---

**THE CHASSIS TOLL IS NOT A CONSTANT, and this report refuses to let it be quoted as one.**
M0265 priced the cost of swapping funds at 2.75 points a year and that figure immediately started
being used as a yardstick. It is a **per-flip price**. Measured here off the recorded rows: M0265
turns over 11.59 a year across 80 closed round trips and pays 2.85 points; M0267's gate turns over
1.57 across 13 and pays 0.53. Seven times the churn, five times the toll. (M0267's own commit
quotes the flip counts as 112 against 13 -- that is signal *changes*, a different count from
``trials.trades``, and it tells the same story at a different scale. Either count has to travel
with the number.)

So every toll this report prints carries the flip count beside it -- recorded ``trades`` **and**
recorded ``turnover``, because an arm that trims a single holding forever records ``trades 0``
without being inert (M0254's floor arms and M0267's half arms all do; see
``seer-partial-weight-book-records-zero-trades``), and a per-flip price divided by zero flips is
not a price. The per-unit figures are printed too, and they are **not** equal across habits:
sitting in cash cost M0254 0.91 points per unit of turnover and swapping funds cost M0265 0.25.
Two different habits, two different prices, one report that says so.

---

**Two return columns, and the report prints both.** The lab records a funded, money-weighted
return and a de-funded paper return, and they disagree in sign on thirty of its trials
(``seer-lab-has-two-return-columns``). A decomposition is only a comparison inside one column.
This matters for more than tidiness: M0267's ratio is **3.5 on the prices and 0.98 on the owner's
money**, because everything the gate was worth happened in the first three years of sixteen, when
a fifth of the deposits had arrived (insight 515). One column says "badly dressed, re-express it";
the other says "a wash". Both are true and the report says both.

It also resolves a figure the lab has been quoting. The hand decomposition recorded for M0265
(insight 511) reads ``0.9 / 2.75 = 0.33``. The 0.9 is the money column and the 2.75 is within
rounding of the paper column's 2.78 -- it is a ratio taken *across* two columns, which is the same
mistake ``seer-a-ratio-across-two-research-stores-is-not-a-comparison`` records in another guise.
Inside one column M0265 reads 0.32 (money) and 0.20 (paper). Dead either way; the verdict never
depended on it; the number should not be re-quoted.

---

**Finding the reversed arms: structure first, prose second.** ``control_shape.role_of`` exists
because id-name heuristics miss most control arms, and this module uses it -- but measured over
all 833 recorded candidates on 2026-10-21, ``role_of`` calls **every** mirror arm of M0251, M0254,
M0265 and M0267 a ``treatment``: they open ``Falsification:``, which is not in its vocabulary and
must not be added to it, because ``ROLE_CONTROL_OPENERS`` feeds D17 on nine dev-eligible methods.

So detection is structural and reads recorded rows, not names. ``trials.config_text`` is the
canonical text of what an arm *does* -- rules, allocator id, params -- and two arms of one method
that differ in **exactly one field** whose two values are a reversal are a mirror pair by
construction. That is strictly stronger than any prose rule: ``M0254-FLOOR50`` and
``M0254-MIRROR50`` differ in ``mirror: False -> True`` and in nothing else, so they are matched on
the weighting arrangement, the exposure distribution and the fee bill whatever their rationales
happen to say. ``role_of`` is then used for the job it is good at -- deciding **which of the two**
is the reversed one -- and it is the first rung of that ladder, not the detector.

---

**A report, not a trial.** No ``trials``, ``trial_moments``, ``trial_funding``,
``trial_provenance``, ``insights``, ``methods`` or ``method_folds`` row is written, no status
moves, and -- like ``lab timing`` and unlike ``lab survivorship`` and ``lab costs`` -- **no
journal entry on any path**, so running it twice costs nothing and leaves nothing to undo. Insight
500 is a permanent duplicate of 499 from exactly that mistake. The test window is never read: the
one query this module issues is pinned to ``window = 'dev'``.

Pure arithmetic over recorded rows: no research store, no backtest, no market, no clock, no
printing. ``format_report`` returns a string; whoever wants it on a terminal prints it.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from seer_engine.backtest import regime
from seer_engine.backtest.metrics import DASH, money_weighted_return, to_fixed
from seer_engine.lab import control_shape as cs
from seer_engine.lab import hardgate, shortfall, store
from seer_engine.lab import walkforward as wf
from seer_engine.lab.exposure import ERAS

log = logging.getLogger(__name__)

WINDOW = "dev"
"""The only window this module names. The test window is a budget, not a data source."""


# --------------------------------------------------------------------- (0) the vocabulary
#
# Measured 2026-10-21 over every pair of dev arms of one method whose recorded `config_text`
# differs in exactly one field -- 644 distinct (field, value, value) pairs across the committed
# lab. Only entries that actually fire are kept, each with the count it fires on, in the
# discipline `control_shape` set on 2026-10-19: a constant with no measurement behind it is a
# guess, and this lab writes down where its numbers came from.

REVERSAL_FLAGS: tuple[str, ...] = (
    "mirror",    # 4 ordered pairs: M0254-FLOOR50, M0265-ROTATE, M0267-GATE, M0267-GATE-HALF
    "invert",    # 1: M0118-D21-M252
    "positive",  # 6: M0179-N20-SW, M0184-T20, M0184-T20-SW, M0185-S20, M0185-S40-SW, M0191-N20
    "low",       # 2: M0188-A20, M0194-A20
)
"""Boolean params whose ``False -> True`` edge turns a book into its own opposite.

Measured, not guessed: these are every boolean field in the lab whose flip produces an arm the
method registered as the straight arm's opposite. ``declared_only``, ``always``, ``gate``,
``switch``, ``sample`` and ``positive``'s look-alikes were read and rejected -- they switch a
habit on, which is a different axis and the one :func:`endpoint_of` works on.
"""

REVERSAL_VALUES: tuple[str, ...] = ("mirror", "reverse", "inverse", "opposite")
"""Values a field moves *to* when the arm is the reversal. One fires: ``M0251`` runs
``mode='ladder'`` against ``mode='mirror'``, the only mirror in the lab expressed as a mode rather
than as a flag. The other three are the spellings a method written tomorrow would plausibly use
and cost nothing to carry; they are listed as unfired rather than silently absent."""

ANTONYMS: tuple[tuple[str, str], ...] = (
    ("high", "low"),        # 5: M0057, M0071, M0091, M0093, M0192 (and M0208 as `signal`)
    ("up", "down"),         # 2: M0083-A, M0083-X
    ("winners", "losers"),  # 1: M0069
    ("near", "far"),        # 1: M0243
    ("calm", "jumpy"),      # 1: M0088
    ("liquid", "illiquid"), # 1: M0058
    ("resid", "low"),       # 1: M0210
)
"""Opposite-sign value pairs: the same screen read from its other end.

Unordered -- ``('high', 'low')`` matches a pair in either direction, and :func:`orient` decides
which side is the reversal. Every entry was read off a real pair; ``('absolute', 'relative')``,
``('continuous', 'discrete')``, ``('announce', 'ex')`` and ``('equal', 'size')`` were met and
rejected, because a different *way* of reading a signal is not the same signal upside down.
"""


# --------------------------------------------------------------------------- (0) the bars

EXPOSURE_BAR = 0.97
"""An endpoint must be in the market this much of the time. Calibrated, not chosen: over all 887
recorded dev trials the opinion-free hold arms sit at 0.9850-0.9916 and the next arm down is
``M0193-S1`` at 0.9556, so the bar sits in a 3-point gap with room on both sides."""

TURNOVER_BAR = 0.15
"""An endpoint must trade this little. Same calibration: the hold arms sit at 0.034-0.114 and the
next arm up is ``M0038-SPY-WATCH`` at 0.192. Together the two bars select exactly ten arms out of
887 -- ``REF-SPY-HOLD`` and the hold arms of M0084, M0120, M0251, M0254, M0265 and M0267 -- which
is the correct answer: a lab of stock pickers has almost no always-invested arms, and that
scarcity is itself the sweep's finding."""

BLEND_TOLERANCE = 0.0005
"""How close a recorded arm must sit to the synthetic blend before it is used in its place, in
de-funded CAGR. Five hundredths of a point a year. Calibrated on the one case the lab has:
``M0265-BLEND`` reads 2.8220 against the synthetic 2.8235, a gap of 0.0015 points, so the
tolerance clears that by a factor of thirty, and the nearest single-fund arm it could be confused
with sits 1.09 points away (3.9147 against the blend's 2.8235), which is twenty-two times the
tolerance. There is room on both sides."""

RATIO_BAR = 1.0
"""At or above this the opinion is worth more than the habits cost. Not a tuned number: it is
wish 492's own sentence, *"a rule whose opinion is worth more than its habit costs is a rule worth
re-expressing rather than discarding"*, written as arithmetic."""

MIN_DIRECTION = 0.0005
"""Below five hundredths of a point a year the pair's two arms are the same book twice and the
ratio is noise over noise. Reported as ``no signal``, never as a verdict about dressing. A
fraction, like every other return in this module: ``0.0005`` is 0.05 points."""

MIN_MONTHS = 24
"""Fewest shared months before a pair is decomposed at all. Two years is the shortest window any
recorded dev trial has, so nothing real is excluded and a fixture pair of four months is."""

ERA_LABEL = "2009-2015"
"""The era wish 492 asks for beside the whole window -- *"across the whole window and across the
years since 2009"*. Taken from ``exposure.ERAS`` by label rather than restated, so this report
cannot drift away from what every other lab report means by it."""

PAPER = "paper"
MONEY = "money"
COLUMNS: tuple[str, ...] = (PAPER, MONEY)
"""The two return columns, named. ``paper`` is the de-funded CAGR ``walkforward.measure`` reads off
the recorded curve; ``money`` is the money-weighted return of the same curve with the owner's
deposits put back. A ratio may never be taken across them -- see the module docstring."""

# Verdicts.
DEAD = "dead"
BADLY_DRESSED = "badly dressed"
SPLIT = "split"
FREE = "free chassis"
NO_SIGNAL = "no signal"
BACKWARDS = "backwards"
UNPRICED = "unpriced"

# Orientation rungs, in the order :func:`orient` tries them.
BY_ROLE = "role"
BY_FLAG = "flag"
BY_VALUE = "value"
BY_PROSE = "prose"
UNRESOLVED = "unresolved"

# Endpoint rungs.
OWN_HOLD = "own-hold"
LINEAGE_HOLD = "lineage-hold"
BLEND = "blend"
NONE_FOUND = "none"

FALSIFICATION: tuple[str, ...] = ("falsification", "the mirror")
"""Rationale openers that name the reversed arm when nothing structural can. Measured 2026-10-21:
``falsification`` opens 4 arms (every mirror of M0251/M0254/M0265/M0267) and ``the mirror`` opens 3
(``M0036-DISC``, ``M0243-FAR20``, ``M0245-RISE21``). It is the LAST rung on purpose -- an arm whose
prose and whose structure disagree should be decided by the structure."""


# --------------------------------------------------------------------------- small helpers


def pts(v: float | None, digits: int = 2) -> str:
    """A points figure with an ASCII sign. ``shortfall.pts``, reused rather than restated."""
    return shortfall.pts(v, digits)


def num(v: float | None, digits: int = 2) -> str:
    """An unsigned figure, or the dash. For a ratio, which has no useful sign of its own.

    Three decimals wherever the ratio is printed, not two: the lab's recorded answers for this
    decomposition are 0.682 and 0.701 (insight 490), and a two-decimal report could not be
    checked against them.
    """
    return DASH if v is None else to_fixed(v, digits)


def _unquote(v: str) -> str:
    """``"'high'"`` -> ``"high"``. Params are canonicalised with ``repr``, so strings keep quotes."""
    s = v.strip()
    return s[1:-1] if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"" else s


def fields_of(config_text: object) -> dict[str, str]:
    """``trials.config_text`` as ``{field: value}``; ``{}`` for anything unreadable.

    ``config_text`` is three lines -- ``rules=``, ``allocator=`` and ``params=`` -- written by
    ``method.config_text`` through ``registry._canon``, and it is the text whose sha256 **is**
    ``config_digest``. Reading it moves nothing: this module never writes it back.

    The ``params=`` line is split into its top-level fields, tracking bracket depth so a nested
    ``inner=Params(a=1,b=2)`` stays one field rather than becoming two. The other two lines are
    kept whole under ``#rules`` and ``#allocator``, and the params class name under ``#params``,
    so a pair that differs in its allocator or its rules is never read as differing in nothing.
    Keys are therefore namespaced: a params field can never collide with one of those three.
    """
    out: dict[str, str] = {}
    for line in str(config_text).strip().splitlines():
        key, _, value = line.partition("=")
        if key != "params":
            out["#" + key] = value
            continue
        name, _, rest = value.partition("(")
        out["#params"] = name
        body = rest[:-1] if rest.endswith(")") else rest
        depth, cur = 0, ""
        for ch in body:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            if ch == "," and depth == 0:
                _put(out, cur)
                cur = ""
            else:
                cur += ch
        _put(out, cur)
    return out


def _put(out: dict[str, str], chunk: str) -> None:
    key, sep, value = chunk.strip().partition("=")
    if sep and key.strip():
        out[key.strip()] = value.strip()


def reversal_between(a: Mapping[str, str], b: Mapping[str, str]) -> tuple[str, str, str] | None:
    """``(field, a's value, b's value)`` when ``a`` and ``b`` differ in exactly one reversing field.

    ``None`` -- which is the answer for almost every pair in the lab -- when they carry different
    fields at all, when they differ in none or in more than one, or when the one field they differ
    in is a dose, a width, a date or any of the six hundred other things a method varies.

    Order-free: it says *these two are a mirror pair*, not which of them is the mirror.
    :func:`orient` answers that separately, so a wrong guess about the direction can never hide a
    pair that exists.
    """
    if set(a) != set(b):
        return None
    differ = [k for k in a if a[k] != b[k]]
    if len(differ) != 1:
        return None
    field = differ[0]
    va, vb = a[field], b[field]
    bare = field.lstrip("#").lower()
    if bare in REVERSAL_FLAGS and {va, vb} == {"False", "True"}:
        return field, va, vb
    if _unquote(va).lower() in REVERSAL_VALUES or _unquote(vb).lower() in REVERSAL_VALUES:
        return field, va, vb
    pair = (_unquote(va).lower(), _unquote(vb).lower())
    if pair in ANTONYMS or pair[::-1] in ANTONYMS:
        return field, va, vb
    return None


# --------------------------------------------------------------------------- reading the lab


@dataclass(frozen=True, slots=True)
class Leg:
    """One recorded arm, with everything the decomposition needs read off its row.

    ``curve`` is the recorded monthly equity curve as it was written; ``deposits`` is what the run
    received inside each step (``hardgate.trial_deposits``, the lab's one de-funding path). Both
    columns are read from this one pair, so the paper and money answers can never be computed off
    two different series.
    """

    n: int
    candidate_id: str
    method_id: str
    curve: tuple[tuple[date, float], ...]
    deposits: Mapping[date, float]
    trades: int
    turnover: float | None
    exposure: float | None

    @property
    def window(self) -> tuple[date, date]:
        return self.curve[0][0], self.curve[-1][0]


def leg_of(conn: sqlite3.Connection, row: sqlite3.Row) -> Leg:
    """A :class:`Leg` from a recorded ``trials`` row. Reads; never writes."""
    curve = shortfall.curve_of(row)
    return Leg(
        n=int(row["n"]),
        candidate_id=str(row["candidate_id"]),
        method_id=str(row["method_id"]),
        curve=tuple(curve),
        deposits=hardgate.trial_deposits(conn, row, curve),
        trades=int(row["trades"] or 0),
        turnover=None if row["turnover"] is None else float(row["turnover"]),
        exposure=None if row["exposure"] is None else float(row["exposure"]),
    )


def dev_rows(conn: sqlite3.Connection, method_id: str | None = None) -> list[sqlite3.Row]:
    """Every recorded dev trial, or one method's, in trial order. The only query this module has."""
    if method_id is None:
        return list(conn.execute(f"SELECT * FROM trials WHERE window = '{WINDOW}' ORDER BY n"))
    return list(conn.execute(
        f"SELECT * FROM trials WHERE window = '{WINDOW}' AND method_id = ? ORDER BY n", (method_id,)
    ))


def lineage(conn: sqlite3.Connection, method_id: str) -> tuple[str, ...]:
    """``method_id`` and every method joined to it by ``methods.parent_id``, ancestors and children.

    Both directions, and transitively, because the endpoint a pair needs is not always in its own
    method: M0254's docstring explains at length why it **re-ran** an always-invested arm rather
    than reading its parent M0251's -- M0251's HOLD ran on a different allocator with a different
    lookback and therefore started hundreds of sessions earlier, and *"a paired difference across
    two windows is not a paired difference"*. The consequence is that M0251's own mirror pair has
    no window-matched endpoint of its own and must reach into its **child** to find one. A parent
    walk alone would miss it, so the walk is undirected over the whole recorded family tree.
    """
    parents: dict[str, str | None] = {}
    for r in conn.execute("SELECT id, parent_id FROM methods"):
        parents[str(r["id"])] = None if r["parent_id"] is None else str(r["parent_id"])
    if method_id not in parents:
        return (method_id,)
    edges: dict[str, set[str]] = {k: set() for k in parents}
    for child, parent in parents.items():
        if parent is not None and parent in edges:
            edges[child].add(parent)
            edges[parent].add(child)
    seen, stack = {method_id}, [method_id]
    while stack:
        cur = stack.pop()
        for nxt in edges.get(cur, ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return tuple(sorted(seen))


# --------------------------------------------------------------------- (1) finding the pairs


@dataclass(frozen=True, slots=True)
class Pairing:
    """Two arms of one method that differ in exactly one reversing field, already oriented."""

    method_id: str
    straight_id: str
    reversed_id: str
    field: str
    straight_value: str
    reversed_value: str
    rung: str

    @property
    def label(self) -> str:
        return f"{self.field}: {self.straight_value} -> {self.reversed_value}"


def orient(
    a: str, b: str, field: str, va: str, vb: str, arms: Mapping[str, cs.Arm]
) -> tuple[str, str, str]:
    """``(straight_id, reversed_id, rung)``: which of ``a`` and ``b`` is the reversal, and how known.

    A four-rung ladder, strongest evidence first, and the rung is reported so a resolution a
    reader would dispute is visible in the output rather than buried in a sign.

    1. ``role`` -- ``control_shape.role_of`` calls exactly one of them ``control``: an arm the
       author registered to be beaten, which is what a reversed arm is. This is the rung wish 492
       means by "use ``role_of``", and it decides fourteen of the lab's pairs.
    2. ``flag`` -- the field is one of :data:`REVERSAL_FLAGS` and one arm has it ``True``. Four
       pairs, including every mirror of M0254, M0265 and M0267, whose prose ``role_of`` cannot
       read (they open ``Falsification:``).
    3. ``value`` -- the field moves to one of :data:`REVERSAL_VALUES`. One pair: M0251's
       ``mode='ladder'`` against ``mode='mirror'``.
    4. ``prose`` -- one rationale opens with :data:`FALSIFICATION`. Last, so that an arm whose
       prose and whose structure disagree is decided by the structure.

    When nothing decides, ``a`` is called straight and the rung is ``unresolved``. The report
    prints that word; it does not quietly pick a side. A wrong orientation only flips the sign of
    ``direction``, which is visible, and never changes the toll.
    """
    role_a = cs.role_of(arms[a]) if a in arms else cs.ROLE_TREATMENT
    role_b = cs.role_of(arms[b]) if b in arms else cs.ROLE_TREATMENT
    if (role_a == cs.ROLE_CONTROL) != (role_b == cs.ROLE_CONTROL):
        return (b, a, BY_ROLE) if role_a == cs.ROLE_CONTROL else (a, b, BY_ROLE)
    if field.lstrip("#").lower() in REVERSAL_FLAGS and {va, vb} == {"False", "True"}:
        return (b, a, BY_FLAG) if va == "True" else (a, b, BY_FLAG)
    on_a, on_b = _unquote(va).lower() in REVERSAL_VALUES, _unquote(vb).lower() in REVERSAL_VALUES
    if on_a != on_b:
        return (b, a, BY_VALUE) if on_a else (a, b, BY_VALUE)
    opens_a, opens_b = _opens(arms.get(a)), _opens(arms.get(b))
    if opens_a != opens_b:
        return (b, a, BY_PROSE) if opens_a else (a, b, BY_PROSE)
    return a, b, UNRESOLVED


def _opens(arm: cs.Arm | None) -> bool:
    if arm is None:
        return False
    text = str(arm.rationale).strip().lower()
    return any(text.startswith(p) for p in FALSIFICATION)


def pairings(
    rows: Sequence[sqlite3.Row], arms: Mapping[str, cs.Arm]
) -> tuple[Pairing, ...]:
    """Every mirror pair among ``rows`` -- recorded dev trials of ONE method -- oriented.

    Each unordered pair appears once. A method that ran a mirror at two doses yields two pairings
    (M0267 ran ``GATE``/``MIRROR`` and ``GATE-HALF``/``MIRROR-HALF``), which is right: the dose
    ladder is the evidence that the ratio is invariant, and collapsing it would throw that away.

    A method that ran ONE mirror beside several doses also yields several pairings, and those are
    approximations rather than exact reflections: M0251 ran ``LADDER``, ``BINARY`` and one
    ``MIRROR``, and ``BINARY``/``MIRROR`` is a binary book against a reflected *ladder*. They are
    reported rather than dropped -- the two read 0.617 and 0.682, which is itself the evidence
    that the ratio does not depend on the rung -- and the ``field`` column on every row says
    exactly which two settings were compared, so a reader can see which pairs are exact.
    """
    config = {str(r["candidate_id"]): fields_of(r["config_text"]) for r in rows}
    ids = [str(r["candidate_id"]) for r in rows]
    out: list[Pairing] = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            found = reversal_between(config[a], config[b])
            if found is None:
                continue
            field, va, vb = found
            values = {a: va, b: vb}
            straight, flipped, rung = orient(a, b, field, va, vb, arms)
            out.append(Pairing(
                method_id=str(rows[0]["method_id"]),
                straight_id=straight, reversed_id=flipped, field=field,
                straight_value=values[straight], reversed_value=values[flipped], rung=rung,
            ))
    return tuple(out)


# ----------------------------------------------------------------- (2) finding the endpoint


def holds(rows: Iterable[sqlite3.Row]) -> tuple[sqlite3.Row, ...]:
    """The always-invested, opinion-free arms among ``rows``, by :data:`EXPOSURE_BAR`/:data:`TURNOVER_BAR`.

    Behavioural, not nominal. An arm is an endpoint because it stayed in the market and barely
    traded, which is what "no opinion" *looks like* in the record -- not because its id ends in
    ``-HOLD``. ``M0005-ALL`` turns over 0.111 and would pass a turnover-only rule; it is in the
    market 1.8% of the time, and the exposure bar is what keeps it out. Both bars are mandatory
    for the same reason ``control_shape.verdict_of`` takes the worse of two numbers.
    """
    return tuple(
        r for r in rows
        if r["exposure"] is not None and r["turnover"] is not None
        and float(r["exposure"]) >= EXPOSURE_BAR and float(r["turnover"]) <= TURNOVER_BAR
    )


def blended(curves: Sequence[Sequence[tuple[date, float]]]) -> list[tuple[date, float]]:
    """An equal-weight book rebalanced at every month end the curves share.

    The always-invested endpoint of a *switch* between several funds is not any one of them: the
    average of a straight arm and its mirror holds each fund exactly half the months, so the
    opinion-free arrangement is a static half-and-half. This builds it from the de-funded curves
    the lab already recorded, and the construction is **checked against a recorded arm**: M0265
    registered ``BLEND``, a fixed 50/50 book with no opinion in it, and this function fed M0265's
    own SPY-HOLD and QQQ-HOLD curves reproduces its de-funded CAGR to 0.0015 points a year
    (2.8235 against the recorded 2.8220). That calibration is pinned in the tests.
    """
    shared = sorted(set.intersection(*[{d for d, _v in c} for c in curves]))
    maps = [dict(c) for c in curves]
    out: list[tuple[date, float]] = [(shared[0], 1.0)]
    value = 1.0
    for i in range(1, len(shared)):
        now, before = shared[i], shared[i - 1]
        value *= sum(m[now] / m[before] for m in maps) / len(maps)
        out.append((now, value))
    return out


def refunded(
    curve: Sequence[tuple[date, float]], deposits: Mapping[date, float]
) -> list[tuple[date, float]]:
    """The inverse of ``regime.defunded``: put a deposit schedule back into a de-funded curve.

    Needed only for a synthetic endpoint. A blend of two de-funded curves has no deposits of its
    own, and the money column asks what the owner's deposits would have become in it -- so they
    are fed in on the pair's own schedule, which is the comparison the column exists to make.
    """
    out = [(curve[0][0], float(curve[0][1]))]
    value = float(curve[0][1])
    for i in range(1, len(curve)):
        when, now = curve[i]
        before = curve[i - 1][1]
        value = value * (now / before) + deposits.get(when, 0.0) if before > 0 else value
        out.append((when, value))
    return out


@dataclass(frozen=True, slots=True)
class Endpoint:
    """The always-invested arrangement a pair is priced against, and how it was found."""

    label: str
    rung: str
    arms: tuple[str, ...]
    curve: tuple[tuple[date, float], ...]       # de-funded
    funded: tuple[tuple[date, float], ...]      # the same series with the pair's deposits in it


def endpoint_of(
    conn: sqlite3.Connection, pair: Pairing, straight: Leg, rows: Sequence[sqlite3.Row]
) -> Endpoint | None:
    """The endpoint for ``pair``, or ``None`` when the method never registered one.

    Candidates are every arm :func:`holds` accepts in the pair's own method and in its
    :func:`lineage`, cut down in this order:

    1. **it must cover the pair's window.** An endpoint that stops before the pair does cannot
       price it, and extrapolating one would be inventing a return.
    2. **an exactly-matching window beats a sliced one**, even when the sliced one is in the
       pair's own method. This is the preference M0254's own file argues for at length: it
       *re-ran* an always-invested arm rather than reading its parent M0251's, because M0251's
       HOLD ran on a different allocator with a different lookback, started thirteen months
       earlier and was therefore scored against a different benchmark -- *"a paired difference
       across two windows is not a paired difference"*. It is also the preference that reproduces
       the lab's published 0.682 for M0251's own pair, which was priced against **M0254-HOLD**.
       Against M0251-HOLD the same pair reads 0.657.
    3. **the pair's own method beats its lineage**, among what is left.
    4. **one arm is the endpoint; several are blended** (:func:`blended`), because several
       single-asset holds are the *extremes* of a switch and not its neutral point -- unless one
       of them already reproduces that blend to within :data:`BLEND_TOLERANCE`, in which case
       that recorded arm is used and the synthetic one is only its check. M0265 registered
       ``BLEND``, a fixed 50/50 book, beside its two single-fund holds; it is picked by this rule
       and the synthetic blend agrees with it to 0.0015 points a year.

    ``None`` when neither rung finds anything: the direction is still reported and the toll is
    not. For a stock picker that is the usual answer and it is the sweep's point, not a gap.
    """
    want = straight.window
    mine = {str(r["candidate_id"]) for r in rows}
    pool: list[tuple[Leg, str]] = [
        (leg_of(conn, r), OWN_HOLD) for r in holds(rows)
        if str(r["candidate_id"]) not in (pair.straight_id, pair.reversed_id)
    ]
    for mid in lineage(conn, pair.method_id):
        if mid == pair.method_id:
            continue
        pool.extend(
            (leg_of(conn, r), LINEAGE_HOLD) for r in holds(dev_rows(conn, mid))
            if str(r["candidate_id"]) not in mine
        )
    covering = [(lg, r) for lg, r in pool if lg.curve[0][0] <= want[0] and lg.curve[-1][0] >= want[1]]
    if not covering:
        return None
    exact = [(lg, r) for lg, r in covering if lg.window == want]
    chosen = exact or [(lg, r) for lg, r in covering if r == OWN_HOLD] or covering
    rung = min((r for _lg, r in chosen), key=(OWN_HOLD, LINEAGE_HOLD).index)

    legs = [lg for lg, _r in chosen]
    clean = [regime.defunded(list(lg.curve), lg.deposits) for lg in legs]
    if len(legs) == 1:
        return Endpoint(legs[0].candidate_id, rung, (legs[0].candidate_id,),
                        tuple(clean[0]), tuple(refunded(clean[0], straight.deposits)))

    synthetic = blended(clean)
    target = paper_return(synthetic, {}, want[0], want[1])
    for lg, curve in zip(legs, clean):
        got = paper_return(curve, {}, want[0], want[1])
        if target is not None and got is not None and abs(got - target) <= BLEND_TOLERANCE:
            return Endpoint(lg.candidate_id, rung, (lg.candidate_id,),
                            tuple(curve), tuple(refunded(curve, straight.deposits)))
    names = tuple(sorted(lg.candidate_id for lg in legs))
    return Endpoint(
        "a static equal-weight book of " + ", ".join(names), BLEND, names,
        tuple(synthetic), tuple(refunded(synthetic, straight.deposits)),
    )


# --------------------------------------------------------------------------- (3) the arithmetic


def paper_return(
    curve: Sequence[tuple[date, float]], deposits: Mapping[date, float], lo: date, hi: date
) -> float | None:
    """The de-funded CAGR over ``lo..hi``, as a fraction. ``walkforward.measure``, reused.

    A fraction and not a percentage, because every other number in the lab is a fraction and
    :func:`pts` is the one place that multiplies by a hundred.
    """
    got = wf.measure(list(curve), lo, hi, deposits)
    return None if got is None or got.cagr is None else got.cagr


def money_return(
    curve: Sequence[tuple[date, float]], deposits: Mapping[date, float], lo: date, hi: date
) -> float | None:
    """The money-weighted return over ``lo..hi``, as a fraction; ``None`` for a lump-sum run.

    The recorded ``trial_funding.mwr`` is the same quantity measured on the run's *daily* snaps
    and its real deposit sessions. This recomputes it from the recorded monthly curve so that a
    synthetic endpoint -- which has no ``trial_funding`` row and never will -- is measured by the
    identical path as the arms it is subtracted from. Measured 2026-10-21 over all 761 funded dev
    trials in the committed lab, the recomputation sits between -0.006 and +0.019 points a year of
    the recorded figure and is positive on 736 of them: a bucketing bias, from crediting each
    deposit at its month end rather than on its own session, and it is overwhelmingly the *same*
    bias on every leg of a subtraction rather than a random one that would add. A test pins both
    halves of that -- the bound and the one-sidedness -- over every funded dev trial.
    """
    seg = [(d, v) for d, v in curve if lo <= d <= hi]
    if len(seg) < 2:
        return None
    flows = sorted((d, a) for d, a in deposits.items() if a > 0 and seg[0][0] < d <= seg[-1][0])
    if not flows:
        return None
    return money_weighted_return(seg, flows)


@dataclass(frozen=True, slots=True)
class Split:
    """One column, over one span: what the opinion knows and what the arrangement costs."""

    column: str
    span: str
    lo: date
    hi: date
    straight: float | None
    reversed_: float | None
    endpoint: float | None

    @property
    def direction(self) -> float | None:
        """Half the gap between the two arms: what the opinion is worth, one-sided.

        One-sided because the gap between a rule and its own mirror counts the opinion **twice** --
        once as what obeying it earned and once as what disobeying it lost. The lab quotes its
        signals one-sided (M0267's "+2.38 pts/yr one-sided") and so does this.
        """
        if self.straight is None or self.reversed_ is None:
            return None
        return (self.straight - self.reversed_) / 2.0

    @property
    def toll(self) -> float | None:
        """The pair's midpoint less the endpoint: what the arrangement cost, opinion removed."""
        if self.straight is None or self.reversed_ is None or self.endpoint is None:
            return None
        return (self.straight + self.reversed_) / 2.0 - self.endpoint

    @property
    def ratio(self) -> float | None:
        """``direction / |toll|``. ``None`` when either is missing or the toll is zero."""
        d, t = self.direction, self.toll
        if d is None or t is None or t == 0.0:
            return None
        return d / abs(t)

    @property
    def verdict(self) -> str:
        """One of the verdict words. The whole report in one token, per column and per span."""
        d, t = self.direction, self.toll
        if d is None:
            return UNPRICED
        if d <= -MIN_DIRECTION:
            return BACKWARDS
        if abs(d) < MIN_DIRECTION:
            return NO_SIGNAL
        if t is None:
            return UNPRICED
        if t >= 0.0:
            return FREE
        return BADLY_DRESSED if (self.ratio or 0.0) >= RATIO_BAR else DEAD


@dataclass(frozen=True, slots=True)
class Decomposition:
    """One mirror pair, split into opinion and habit, in both columns over both spans."""

    pairing: Pairing
    straight_n: int
    reversed_n: int
    window: tuple[date, date]
    months: int
    endpoint: Endpoint | None
    splits: tuple[Split, ...]
    trades: tuple[int, int]
    turnover: tuple[float | None, float | None]
    exposure: tuple[float | None, float | None]
    deposits: int
    warnings: tuple[str, ...]

    def at(self, column: str, span: str) -> Split | None:
        for s in self.splits:
            if s.column == column and s.span == span:
                return s
        return None

    @property
    def flips(self) -> float:
        """The pair's mean recorded closed round trips. The number that must sit beside a toll."""
        return (self.trades[0] + self.trades[1]) / 2.0

    @property
    def churn(self) -> float | None:
        """The pair's mean recorded turnover: the flip count for a book that never closes out.

        M0254's floor arms trim one holding forever and record ``trades 0`` while turning over
        2.7-2.8 a year. Quoting a per-flip price off ``trades`` alone would divide by zero on
        exactly the method wish 492 was written about.
        """
        a, b = self.turnover
        return None if a is None or b is None else (a + b) / 2.0

    def per_flip(self, column: str) -> float | None:
        """The toll divided by the mean round-trip count: what one flip of the habit cost a year."""
        s = self.at(column, "whole")
        if s is None or s.toll is None or self.flips <= 0:
            return None
        return abs(s.toll) / self.flips

    def per_turnover(self, column: str) -> float | None:
        """The toll divided by the mean turnover: the price of the habit per unit of churn."""
        s = self.at(column, "whole")
        churn = self.churn
        if s is None or s.toll is None or not churn:
            return None
        return abs(s.toll) / churn

    @property
    def verdict(self) -> str:
        """The pair's single word, over the whole window, from both columns at once.

        The signal question is asked first and over both columns at once: a pair whose two
        columns do not agree that the straight arm beat its mirror is ``no signal``, and one
        where both say the mirror won is ``backwards``, whatever the toll says. Only a pair that
        agrees it carries an opinion is asked whether the opinion pays for the arrangement.

        Then: ``badly dressed`` only when the prices **and** the owner's money both say so, and
        ``dead`` only when both do. When they disagree the answer is :data:`SPLIT`, which is its own
        finding and not a tie to be broken: M0267 reads 3.47 on the prices and 0.98 on the money,
        because everything the gate was worth landed in the first three years of sixteen, before
        four fifths of the deposits existed (insight 515). Collapsing that to either word would
        throw away the only thing about M0267 worth knowing.
        """
        here = [s for s in self.splits if s.span == "whole"]
        ways = [s.direction for s in here if s.direction is not None]
        if not ways:
            return UNPRICED
        if all(d <= -MIN_DIRECTION for d in ways):
            return BACKWARDS
        if not all(d >= MIN_DIRECTION for d in ways):
            return NO_SIGNAL
        dressed = [s.verdict for s in here if s.toll is not None]
        if not dressed:
            return UNPRICED
        if len(set(dressed)) == 1:
            return dressed[0]
        if BADLY_DRESSED in dressed and DEAD in dressed:
            return SPLIT
        order = (DEAD, SPLIT, FREE, BADLY_DRESSED)
        return min((v for v in dressed if v in order), key=order.index, default=UNPRICED)


def measure(
    conn: sqlite3.Connection, pairing: Pairing, rows: Sequence[sqlite3.Row] | None = None
) -> Decomposition:
    """Split one mirror pair. Reads the lab; writes nothing; opens no store and runs no backtest.

    Both arms are read over the window they **share**, cut from the recorded curves, so a pair
    whose two arms started on different sessions is still a paired difference. Both are de-funded
    through ``hardgate.trial_deposits`` before any return is taken, each with its own schedule.

    Raises ``store.LabError`` for a pair that cannot be decomposed at all -- fewer than
    :data:`MIN_MONTHS` shared months, or two arms the hard gate says are not comparable at all
    (``hardgate.mismatches``, D10: different research stores). A missing endpoint is **not** an
    error; it is a ``None`` and a verdict of ``unpriced``.
    """
    if rows is None:
        rows = dev_rows(conn, pairing.method_id)
    by_id = {str(r["candidate_id"]): r for r in rows}
    for cid in (pairing.straight_id, pairing.reversed_id):
        if cid not in by_id:
            raise store.LabError(f"{cid} has no recorded dev trial in {pairing.method_id}")
    straight = leg_of(conn, by_id[pairing.straight_id])
    flipped = leg_of(conn, by_id[pairing.reversed_id])

    lo = max(straight.window[0], flipped.window[0])
    hi = min(straight.window[1], flipped.window[1])
    shared = [d for d, _v in straight.curve if lo <= d <= hi and d in dict(flipped.curve)]
    if len(shared) < MIN_MONTHS:
        raise store.LabError(
            f"{pairing.straight_id} and {pairing.reversed_id} share {len(shared)} month(s) "
            f"inside {lo}..{hi}; {MIN_MONTHS} are needed before a decomposition means anything"
        )

    warnings: list[str] = []
    problems = hardgate.mismatches(conn, flipped.n, [by_id[pairing.straight_id]])
    if problems:
        raise store.LabError(
            f"{pairing.straight_id} is not comparable with {pairing.reversed_id}: "
            f"{hardgate.describe(problems)} (lab/hardgate.py, D10)"
        )
    if pairing.rung == UNRESOLVED:
        warnings.append(
            f"NOTE nothing in {pairing.straight_id}'s or {pairing.reversed_id}'s role, "
            f"configuration or prose says which of them is the reversal, so the sign of "
            f"`what the opinion knows` below may be the wrong way round. The toll is unaffected"
        )

    end = endpoint_of(conn, pairing, straight, rows)
    if end is None:
        warnings.append(
            f"NOTE {pairing.method_id} registered no always-invested, opinion-free arm "
            f"(exposure >= {EXPOSURE_BAR}, turnover <= {TURNOVER_BAR}) in itself or its lineage, "
            f"so what the habit costs cannot be priced here -- only what the opinion knows"
        )

    spans: list[tuple[str, date, date]] = [("whole", lo, hi)]
    for label, start, end_ in ERAS:
        if label == ERA_LABEL:
            era_lo, era_hi = max(start, lo), min(end_, hi)
            if era_lo < era_hi:
                spans.append((label, era_lo, era_hi))

    splits: list[Split] = []
    for span, slo, shi in spans:
        for column in COLUMNS:
            read = paper_return if column == PAPER else money_return
            splits.append(Split(
                column=column, span=span, lo=slo, hi=shi,
                straight=read(straight.curve, straight.deposits, slo, shi),
                reversed_=read(flipped.curve, flipped.deposits, slo, shi),
                endpoint=None if end is None else read(
                    end.curve if column == PAPER else end.funded,
                    {} if column == PAPER else straight.deposits, slo, shi,
                ),
            ))

    return Decomposition(
        pairing=pairing,
        straight_n=straight.n, reversed_n=flipped.n,
        window=(lo, hi), months=len(shared), endpoint=end, splits=tuple(splits),
        trades=(straight.trades, flipped.trades),
        turnover=(straight.turnover, flipped.turnover),
        exposure=(straight.exposure, flipped.exposure),
        deposits=len(straight.deposits), warnings=tuple(warnings),
    )


# --------------------------------------------------------------------- (4) the back catalogue


@dataclass(frozen=True, slots=True)
class Skip:
    """A pair the survey could not decompose, and the plain reason why."""

    method_id: str
    straight_id: str
    reversed_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class Survey:
    """Every mirror pair the lab has recorded, decomposed."""

    found: tuple[Decomposition, ...]
    skipped: tuple[Skip, ...]
    methods: tuple[str, ...]

    @property
    def priced(self) -> tuple[Decomposition, ...]:
        """The pairs with an endpoint: the ones where dead and badly-dressed can be told apart."""
        return tuple(d for d in self.found if d.endpoint is not None)

    @property
    def unpriced(self) -> tuple[Decomposition, ...]:
        return tuple(d for d in self.found if d.endpoint is None)

    @property
    def badly_dressed(self) -> tuple[Decomposition, ...]:
        """Opinion worth more than habits cost, in BOTH columns. The wish's whole question."""
        return tuple(d for d in self.priced if d.verdict == BADLY_DRESSED)

    @property
    def split(self) -> tuple[Decomposition, ...]:
        """Badly dressed on the prices, dead on the owner's money -- or the other way round."""
        return tuple(d for d in self.priced if d.verdict == SPLIT)

    @property
    def dead(self) -> tuple[Decomposition, ...]:
        return tuple(d for d in self.priced if d.verdict == DEAD)

    @property
    def signal(self) -> tuple[Decomposition, ...]:
        """Pairs whose straight arm beats its own mirror -- the signal knows something, priced or not."""
        return tuple(
            d for d in self.found
            if (d.at(MONEY, "whole") or d.at(PAPER, "whole")) is not None
            and ((d.at(MONEY, "whole").direction if d.at(MONEY, "whole") else None) or
                 (d.at(PAPER, "whole").direction if d.at(PAPER, "whole") else None) or 0.0)
            >= MIN_DIRECTION
        )


def survey(conn: sqlite3.Connection, methods: Sequence[str] = ()) -> Survey:
    """Every recorded mirror pair in the lab, or in ``methods``, decomposed. Writes nothing.

    Method files are read only for the rationales ``orient`` needs. A method with no file on disk
    still yields its pairs -- detection is structural -- and only loses the ``role`` rung.
    """
    from seer_engine.lab.method import discover

    try:
        files = discover()
    except Exception as e:  # pragma: no cover - a broken method file is the file's problem
        log.warning("method files unreadable (%s); orientation falls back to structure", e)
        files = {}
    arms: dict[str, cs.Arm] = {}
    for method, _path in files.values():
        for arm in method.all_candidates():
            arms[arm.id] = arm

    rows = dev_rows(conn)
    by_method: dict[str, list[sqlite3.Row]] = {}
    for r in rows:
        by_method.setdefault(str(r["method_id"]), []).append(r)
    if methods:
        want = {str(m).upper() for m in methods}
        by_method = {k: v for k, v in by_method.items() if k.upper() in want}

    found: list[Decomposition] = []
    skipped: list[Skip] = []
    for mid in sorted(by_method):
        for pairing in pairings(by_method[mid], arms):
            try:
                found.append(measure(conn, pairing, by_method[mid]))
            except store.LabError as e:
                skipped.append(Skip(mid, pairing.straight_id, pairing.reversed_id, str(e)))
    return Survey(tuple(found), tuple(skipped), tuple(sorted(by_method)))


# --------------------------------------------------------------------------- what it prints


_VERDICT_SENTENCE: Mapping[str, str] = {
    BADLY_DRESSED: (
        "BADLY DRESSED. The opinion is worth more than the arrangement costs, so the rule is "
        "worth re-expressing on a cheaper chassis rather than discarding."
    ),
    DEAD: (
        "DEAD. The opinion is worth less than the arrangement costs. Dilution halves both halves "
        "together, so no gentler setting of the dial can close the gap -- only an arrangement "
        "that costs less can, and this one has already been measured."
    ),
    FREE: (
        "The arrangement costs nothing at all -- the pair's midpoint is at or above the "
        "always-invested endpoint. Whatever is wrong with this rule, it is not the chassis."
    ),
    NO_SIGNAL: (
        "NO SIGNAL. The straight arm and its mirror are within a rounding error of each other, so "
        "there is no opinion here to dress well or badly."
    ),
    BACKWARDS: (
        "BACKWARDS. The mirror beat the straight arm: the rule carries information and is being "
        "read upside down. Check the orientation rung before acting on that."
    ),
    UNPRICED: (
        "UNPRICED. What the opinion knows is measured; what the habit costs is not, because the "
        "method never registered an always-invested arm to price it against."
    ),
    SPLIT: (
        "SPLIT. The prices say the opinion is worth more than the arrangement costs and the "
        "owner's money says it is not. That gap is not noise: it means the edge was earned before "
        "the deposits arrived, so re-expressing this rule on a cheaper chassis would buy the "
        "prices something it could not buy him. Read `lab timing` on the same pair before acting."
    ),
}


def _span_table(d: Decomposition, span: str, title: str) -> list[str]:
    out = [title, f"  {'':14}{'what it knows':>16}{'what habits cost':>19}{'ratio':>9}{'verdict':>16}"]
    for column in COLUMNS:
        s = d.at(column, span)
        if s is None:
            continue
        label = "on the prices" if column == PAPER else "on the money"
        out.append(
            f"  {label:<14}{pts(s.direction):>14} pts{pts(s.toll):>17} pts"
            f"{num(s.ratio, 3):>9}{s.verdict:>16}"
        )
    return out


def format_report(d: Decomposition) -> str:
    """The whole report for one pair, in plain words. The owner reads lab output and is not a quant."""
    p = d.pairing
    out: list[str] = list(d.warnings)
    if d.warnings:
        out.append("")
    out.append(
        f"{p.method_id}: {p.straight_id} (trial #{d.straight_n}) against its reversed arm "
        f"{p.reversed_id} (trial #{d.reversed_n})."
    )
    out.append(
        f"They differ in exactly one recorded setting -- {p.label} -- and in nothing else, so "
        f"they are"
    )
    out.append(
        "matched on the book's shape, its exposure pattern and its fee bill. Which one is the "
        "reversal"
    )
    out.append(f"was decided by: {p.rung}.")
    out.append(f"Shared window {d.window[0]} to {d.window[1]}, {d.months} months.")
    if d.endpoint is None:
        out.append("No always-invested arm is recorded for this method, so the habit is unpriced.")
    else:
        out.append(
            f"Priced against {d.endpoint.label} ({d.endpoint.rung}): the always-invested "
            f"arrangement this"
        )
        out.append("pair averages to in holdings, with none of the habit.")
    out.append("")
    out.append(
        "`what it knows` is half the gap between the arm and its mirror: one-sided, because the "
        "gap"
    )
    out.append(
        "counts the opinion twice -- once as what obeying the rule earned and once as what "
        "disobeying"
    )
    out.append(
        "it lost. `what habits cost` is their midpoint less the always-invested endpoint. "
        "Averaging"
    )
    out.append(
        "the two arms cancels the opinion exactly, so the midpoint holds an amount that no "
        "longer"
    )
    out.append(
        "depends on the signal, and everything left in it is the arrangement: the fees, the "
        "churn,"
    )
    out.append("and the cash it sits in on average.")
    out.append("")
    out.extend(_span_table(d, "whole", "Whole window:"))
    era = d.at(PAPER, ERA_LABEL)
    if era is not None:
        out.append("")
        out.extend(_span_table(d, ERA_LABEL, f"{ERA_LABEL} only ({era.lo} to {era.hi}):"))
    out.append("")

    out.append("How often the habit was exercised -- a toll is a PER-FLIP price, never a constant:")
    out.append(
        f"  closed round trips      {d.trades[0]} and {d.trades[1]} over {d.months} months"
    )
    out.append(
        f"  turnover a year         {num(d.turnover[0])} and {num(d.turnover[1])}"
        + ("   (trades 0 means it trims one holding forever, not that it is inert)"
           if max(d.trades) == 0 else "")
    )
    for column in COLUMNS:
        flip, churn = d.per_flip(column), d.per_turnover(column)
        if flip is None and churn is None:
            continue
        label = "on the prices" if column == PAPER else "on the money"
        out.append(
            f"  price of the habit      {label}: {pts(flip, 3)} pts/yr per round trip, "
            f"{pts(churn, 3)} per unit of turnover"
        )
    out.append("")
    out.append(_VERDICT_SENTENCE[d.verdict])
    if d.verdict in (DEAD, BADLY_DRESSED):
        out.append(
            "Both columns agree, so the answer does not depend on whether the prices or the "
            "owner's"
        )
        out.append("own deposit schedule is read.")
    return "\n".join(out)


def _row(d: Decomposition) -> str:
    """One pair's line. Every toll on it carries the pair's flip count two columns later."""
    whole_p, whole_m = d.at(PAPER, "whole"), d.at(MONEY, "whole")
    return (
        f"  {d.pairing.method_id:<7}{d.pairing.straight_id:<22}"
        f"{pts(whole_p.direction if whole_p else None):>9}"
        f"{pts(whole_p.toll if whole_p else None):>9}"
        f"{num(whole_p.ratio if whole_p else None, 3):>8}"
        f"{pts(whole_m.direction if whole_m else None):>10}"
        f"{pts(whole_m.toll if whole_m else None):>9}"
        f"{num(whole_m.ratio if whole_m else None, 3):>8}"
        f"{d.flips:>8.0f}{num(d.churn):>8}"
        f"{d.verdict:>16}"
    )


def format_survey(s: Survey, *, limit: int = 40) -> str:
    """The whole catalogue: which rejected rules were badly dressed, and which were dead."""
    out: list[str] = []
    out.append(
        f"{len(s.found)} reversed-arm pair(s) across {len({d.pairing.method_id for d in s.found})} "
        f"method(s), out of {len(s.methods)} methods with"
    )
    out.append(
        "recorded dev trials. A pair is two arms of one method whose recorded configurations "
        "differ"
    )
    out.append(
        "in exactly one reversing setting and in nothing else -- structure, not names: "
        "control_shape's"
    )
    out.append(
        "role_of calls every Falsification: arm a treatment, so it decides which arm is the "
        "mirror and"
    )
    out.append("never which pairs exist.")
    out.append("")
    out.append(
        "Every toll below carries the pair's flip count beside it, because a chassis toll is a"
    )
    out.append(
        "PER-FLIP price and not a constant. `flips` is the mean recorded closed round trips and"
    )
    out.append(
        "`churn` the mean recorded turnover a year -- read churn when flips is 0, which means an"
    )
    out.append("arm trims one holding forever rather than that it never trades.")
    out.append("")
    out.append(
        f"  {'method':<7}{'straight arm':<22}{'--- on the prices ---':^26}"
        f"{'--- on the money ---':^27}{'flips':>8}{'churn':>8}{'verdict':>16}"
    )
    out.append(
        f"  {'':<7}{'':<22}{'knows':>9}{'costs':>9}{'ratio':>8}"
        f"{'knows':>10}{'costs':>9}{'ratio':>8}{'':>8}{'':>8}{'':>16}"
    )
    order = {BADLY_DRESSED: 0, SPLIT: 1, FREE: 2, DEAD: 3, UNPRICED: 4, NO_SIGNAL: 5,
             BACKWARDS: 6}
    ranked = sorted(s.found, key=lambda d: (order.get(d.verdict, 9), d.pairing.method_id))
    for d in ranked[:limit]:
        out.append(_row(d))
    if len(ranked) > limit:
        out.append(f"  ... and {len(ranked) - limit} more (raise --limit)")
    out.append("")

    out.append(
        f"Priced: {len(s.priced)} of {len(s.found)}. The other {len(s.unpriced)} name a method "
        f"that never registered an"
    )
    out.append(
        "always-invested, opinion-free arm, so what their habit costs cannot be read off the "
        "record at"
    )
    out.append(
        "all. That is the sweep's first finding and it is actionable: a reversed arm is only half"
    )
    out.append(
        "an experiment. Without a never-leave arm beside it the lab cannot tell a dead rule from "
        "a"
    )
    out.append("badly dressed one, and it has been recording the first half alone for years.")
    out.append("")
    if s.priced:
        out.append(
            f"The same pairs over {ERA_LABEL} alone, which is the half of the window the owner's"
        )
        out.append("money was actually in the account for:")
        out.append(
            f"  {'method':<7}{'straight arm':<22}{'knows':>9}{'costs':>9}{'ratio':>8}"
            f"{'  (on the money)':<18}"
        )
        for d in sorted(s.priced, key=lambda d: d.pairing.method_id):
            era = d.at(MONEY, ERA_LABEL)
            out.append(
                f"  {d.pairing.method_id:<7}{d.pairing.straight_id:<22}"
                f"{pts(era.direction if era else None):>9}{pts(era.toll if era else None):>9}"
                f"{num(era.ratio if era else None, 3):>8}{'':<18}"
            )
        out.append("")
    if s.split:
        out.append(
            "SPLIT -- the prices say re-express it and the owner's deposit schedule says it would"
        )
        out.append("never have reached him:")
        for d in s.split:
            out.append(f"  {d.pairing.method_id}  {d.pairing.straight_id} vs {d.pairing.reversed_id}")
        out.append("")
    if s.badly_dressed:
        out.append("BADLY DRESSED -- worth re-expressing on a cheaper chassis:")
        for d in s.badly_dressed:
            out.append(f"  {d.pairing.method_id}  {d.pairing.straight_id} vs {d.pairing.reversed_id}")
    else:
        out.append(
            "No priced pair is badly dressed in both columns. Every timing rule the lab can price "
            "is dead"
        )
        out.append("by arithmetic, not by bad luck.")
    out.append("")
    if s.dead:
        out.append("DEAD -- the opinion cannot pay for the arrangement at any dose:")
        for d in s.dead:
            out.append(f"  {d.pairing.method_id}  {d.pairing.straight_id} vs {d.pairing.reversed_id}")
    if s.skipped:
        out.append("")
        out.append(f"{len(s.skipped)} pair(s) could not be decomposed:")
        for k in s.skipped[:10]:
            out.append(f"  {k.method_id}  {k.straight_id} vs {k.reversed_id}: {k.reason}")
    return "\n".join(out)


def csv_rows(found: Sequence[Decomposition]) -> list[list[str]]:
    """Every split at full precision, one row per pair per column per span."""
    head = [
        "method_id", "straight_id", "reversed_id", "straight_n", "reversed_n", "field",
        "orientation_rung", "endpoint", "endpoint_rung", "column", "span", "lo", "hi",
        "straight", "reversed", "endpoint_return", "direction", "toll", "ratio", "verdict",
        "trades_straight", "trades_reversed", "turnover_straight", "turnover_reversed",
        "months", "pair_verdict",
    ]
    out = [head]
    for d in found:
        p = d.pairing
        for s in d.splits:
            out.append([
                p.method_id, p.straight_id, p.reversed_id, str(d.straight_n), str(d.reversed_n),
                p.label, p.rung,
                "" if d.endpoint is None else d.endpoint.label,
                "" if d.endpoint is None else d.endpoint.rung,
                s.column, s.span, s.lo.isoformat(), s.hi.isoformat(),
                _raw(s.straight), _raw(s.reversed_), _raw(s.endpoint),
                _raw(s.direction), _raw(s.toll), _raw(s.ratio), s.verdict,
                str(d.trades[0]), str(d.trades[1]), _raw(d.turnover[0]), _raw(d.turnover[1]),
                str(d.months), d.verdict,
            ])
    return out


def _raw(v: float | None) -> str:
    return "" if v is None else repr(v)


def write_csv(found: Sequence[Decomposition], path: Path) -> Path:
    """Write :func:`csv_rows` to ``path``. The one file this module may create, and only on ask."""
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(csv_rows(found))
    return path


def resolve_pairing(
    conn: sqlite3.Connection, token: object, against: object = None
) -> tuple[Pairing, list[sqlite3.Row]]:
    """The pairing ``token`` names, and its method's rows. Raises ``LabError`` with a usable message.

    ``token`` is a method id (``M0254``), a candidate id (``M0254-FLOOR50``) or a ``trials.n``.
    ``against`` names the other arm explicitly, for a pair the structural rule does not find --
    and such a pair is reported with the rung ``unresolved`` rather than pretended to be detected.
    """
    from seer_engine.lab.method import discover

    row = None
    method_id = str(token).strip().upper()
    if not (len(method_id) == 5 and method_id.startswith("M") and method_id[1:].isdigit()):
        row = shortfall.resolve_trial(conn, token)
        method_id = str(row["method_id"])
    rows = dev_rows(conn, method_id)
    if not rows:
        raise store.LabError(f"{method_id} has no recorded dev trial")

    arms: dict[str, cs.Arm] = {}
    entry = discover().get(method_id)
    if entry is not None:
        for arm in entry[0].all_candidates():
            arms[arm.id] = arm

    if against is not None:
        other = shortfall.resolve_trial(conn, against)
        if row is None:
            raise store.LabError("--against needs a named arm, not a method id, on the left")
        a, b = str(row["candidate_id"]), str(other["candidate_id"])
        config = {str(r["candidate_id"]): fields_of(r["config_text"]) for r in rows}
        found = reversal_between(config.get(a, {}), config.get(b, {}))
        field, va, vb = found or ("(declared by hand)", a, b)
        straight, flipped, rung = (
            orient(a, b, field, va, vb, arms) if found else (a, b, UNRESOLVED)
        )
        values = {a: va, b: vb}
        return Pairing(method_id, straight, flipped, field, values[straight], values[flipped],
                       rung), rows

    found = pairings(rows, arms)
    if not found:
        raise store.LabError(
            f"{method_id} recorded no reversed arm: no two of its arms differ in exactly one "
            f"reversing setting. Name both arms with --against to split a pair by hand"
        )
    if row is not None:
        mine = [p for p in found if str(row["candidate_id"]) in (p.straight_id, p.reversed_id)]
        if not mine:
            raise store.LabError(
                f"{row['candidate_id']} is not half of any reversed pair in {method_id}; "
                f"{method_id} has " + ", ".join(f"{p.straight_id}/{p.reversed_id}" for p in found)
            )
        return mine[0], rows
    return found[0], rows
