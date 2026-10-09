"""The hard gate: ``lab promote`` refuses what the folds and the kin have already judged.

**The rule.** A method is promoted only when both hold:

- **(F) the folds.** It beat the recorded benchmark in a strict majority of the walk-forward
  folds (``walkforward.Record.majority``), and it was scoreable on *every* fold the geometry
  yields, and there were at least ``MIN_FOLDS`` of them.
- **(K) the kin.** No other method in its ``family``, and no transitive ancestor through
  ``parent_id``, reads ``test-failed``.

**Decided 2026-10-09 by the owner, after seeing what it costs.** It blocks every promotion in the
lab as of today, and that is the intended effect rather than a side effect: five out-of-sample
results, five failures, and the surviving ideas are all cousins of the methods that produced
them. A lab that keeps promoting cousins of disproven families is not learning.

**There is no override path, in any form** -- no flag, no variable in the shell, no "promote
anyway". If this proves too strict in practice the answer is a recorded, argued change to this
file, in git, because an escape hatch is precisely the mechanism that produced the 0-for-5
roster.

**Why here and not in ``prereg.promote_method``.** The brief requires that the existing promote
tests still pass. ``prereg.promote_method`` is the one function every one of them calls, and a
refusal inside it would refuse a fixture database rather than a method. The gate therefore sits
one layer out, in ``commands/lab.py:_promote``, which calls ``check`` before ``promote_method``.
``promote_method`` has exactly **one** production caller (``commands/lab.py:_promote``), so this
is not a hole in practice -- but **a second caller must call ``check`` too**, and whoever adds one
is the person who has to read this sentence.

**Why this is not a hole in the status machine either.** ``store.TRANSITIONS`` admits exactly one
edge into ``promoted``: ``dev-eligible -> promoted``. ``check`` acts on a ``dev-eligible`` method
and is silent for every other status, so gating ``dev-eligible`` gates *every* promotion the
database will accept. Silence for a non-promotable status is not a waiver: the caller is
``prereg.promote_method``, one line later, which refuses it with the better message it already
has. Silence for ``promoted`` is deliberate too -- that method already cleared this gate, its
pre-registration is a promise (see **(D3)** below), and ``promote_method``'s repair path for a
half-finished promotion must keep working.

**What it spends: nothing.** No research store, no backtest, no trial row, no counted look. It is
SQL plus arithmetic on ``trials.curve_json``, and a refusal happens *before* the pre-registration
file is written and before any status moves, so a refused ``lab promote`` leaves the repository
and the database byte-identical.

**A funded curve is de-funded before it is measured.** Every trial from M0032 on is funded, and a
raw funded curve counts the owner's deposits as growth while the benchmark it is measured against
receives none -- seventy to eighty points a year, until it was fixed (insights 72, 75).
``trial_deposits`` below reconstructs each trial's deposit series; ``walkforward.measure`` calls
``regime.defunded`` with it. Nothing here re-implements de-funding.

**Not ``backtest.walkforward``.** That is P3b's anchored walk-forward for Strategy A2 on the
bracket engine, a different module answering a different question. This gate reads
``lab.walkforward``, which slices curves the lab already recorded.

---

The four questions the brief left open, and the answer to each with its reason.

**(D2) How thin is too thin? -- scoreable on EVERY fold the geometry yields, and at least
``MIN_FOLDS = 4``.**

The fold geometry is cut from the *benchmark* curve, so it is global rather than per method:
``REF-SPY-HOLD`` spans 1993-02-01..2015-10-16 and yields exactly 4 folds. Every ``M*`` method in
the lab has a dev curve spanning 1996-01-03..2015-10-16 and is scoreable on all four, so this
minimum costs a real method nothing. ``H-P7A-F10``, whose curve starts 2007-04-10, scores only 2
-- the thin case is not hypothetical. And measured on a curve of that shape, it wins **both** of
the folds it can be scored on, so ``Record.majority`` reads True: the literal rule "wins a
majority of its walk-forward folds" would promote it on two looks at the post-crisis decade
alone. That is what the "every fold" clause is for, and why it is not redundant with
``majority``.

Why not "3 or more". Under a coin-flip null -- a **bound, not a p-value**: folds share training
data and may never be treated as independent observations, and nothing here may be fed into a
DSR -- the probability of a strict majority is:

====================  ===============================
scoreable folds       P(strict majority | coin flip)
====================  ===============================
1                     0.5000
2                     0.2500
**3**                 **0.5000**
**4**                 **0.3125**
5                     0.5000
6                     0.3438
====================  ===============================

A strict majority of an **odd** count is a coin flip at every odd count, because the null has no
tie to lose. A "minimum of 3" would therefore admit evidence strictly weaker than 4 and no
stronger than 1. The rule is the conjunction: the first clause refuses a method whose curve does
not cover the window; ``MIN_FOLDS`` is a tripwire that fires if ``MIN_TRAIN_YEARS``,
``EVAL_YEARS`` or the dev window ever changes the geometry, so a changed setting cannot silently
lower the bar.

**(D3) Is (K) re-checked at ``lab test``? -- No. The pre-registration is a promise.**

Three reasons, in the order they matter. ``promoted`` has only two exits and both are final, so a
refusal at ``lab test`` strands a method in a state it can never leave -- the exact failure the
brief's "refuse before the commitment, not after it" rejects. A pre-registration whose meaning
depends on events after it was written is not a pre-registration. And the family's state **is**
recorded in the file (``family_state``, written by ``prereg``), so a reader can see the promise's
basis without the code re-deriving it.

What ``lab test`` gets instead is one printed line and no new refusal: when the method's kin has
failed since promotion, it says so above the look. That is information the owner should have
before spending the one look; it changes no exit code and no transition.

**(D4) Does (K) walk ``parent_id`` as well as ``family``? -- Yes: ``family`` union transitive
ancestors. Not the full connected component.**

The brief gives the reason for yes: M0032 is M0007's realistic twin by ``parent_id``, not by
family string, and a method whose *parent* failed is as disproven as one whose sibling did.
Measured on the committed lab (63 methods, 4 reading ``test-failed``):

================================  =========  =====================================================
rule                              blocks     note
================================  =========  =====================================================
``family`` only                   26 of 63   the literal rule; **misses M0030**, whose family is
                                             clean but whose parent M0029 and grandparent M0021
                                             both read ``test-failed``
ancestors only                    10 of 63   misses M0007, M0019, M0020, M0033
**``family`` union ancestors**    29 of 63   catches all seven dev-eligible methods
full connected component          36 of 63   one **26-method blob**; would refuse M0019 on account
                                             of M0021, a multi-factor blend four hops away in an
                                             unrelated family
================================  =========  =====================================================

The component rule is rejected on that last line: "cousin of a disproven family" stretched to four
hops through unrelated families stops being a statement about the evidence. Descendants are left
to the ``family`` string, which by construction holds a variation twin (``lab idea
--source-kind variation --parent ...`` keeps the family), and the measurement shows ``family``
already catches every failed-descendant case the lab has.

**(D6) Is there a path back? -- None is built, and the need is recorded.**

The brief said not to invent one here, and to note whether it will be needed. **It will.**
``reevaluate`` exists for ``rejected -> dev-eligible`` when the bars move; nothing equivalent
exists for a method whose kin is blocked. Two shapes will eventually be wanted and neither is
built here:

1. a family whose failure is later attributed to something other than the idea -- a cost model, a
   fill assumption -- so the failure does not disprove the hypothesis;
2. a method whose ``parent_id`` links it to a failure it does not inherit.

Both are *arguments*, and the brief's own sentence says an argued change to the rule is the
mechanism: a commit, not a flag. Until then the gate is not a permanent stop -- M0034 and M0035
both win 3 of 4 folds with clean kin (their parent M0032 reads ``rejected``, not ``test-failed``),
they simply read ``rejected`` themselves today.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date

from seer_engine.backtest import regime
from seer_engine.lab import store
from seer_engine.lab import walkforward as wf

#: The fewest scoreable folds that count as evidence. See (D2) in the module docstring: the rule
#: is "every fold the geometry yields, AND at least this many". Four is what the recorded
#: benchmark's span yields today, so this is a tripwire on the geometry, not a quota on a method.
MIN_FOLDS = 4

#: P(strict majority | coin flip) for n folds -- the binomial tail P(X > n/2), X ~ Bin(n, 1/2).
#: A **bound on how impressed to be**, never a p-value: the folds share training data, so they are
#: not independent observations and nothing derived from this may enter a DSR. It is here as data
#: so a test can check it against the binomial rather than against a typed-in table, and so the
#: next person to argue for MIN_FOLDS = 3 has to argue with the 0.5000 on its row.
COIN_FLIP_NULL: tuple[tuple[int, float], ...] = (
    (1, 0.5000),
    (2, 0.2500),
    (3, 0.5000),
    (4, 0.3125),
    (5, 0.5000),
    (6, 0.3438),
)

#: The statuses the gate judges. Exactly the tail of ``store.TRANSITIONS``' only edge into
#: ``promoted``, so this set is the complete set of promotions the database will accept.
_GATED_STATUS = "dev-eligible"


def trial_deposits(
    conn: sqlite3.Connection, row: sqlite3.Row, curve: list[tuple[date, float]]
) -> dict[date, float]:
    """What a funded trial received inside each curve step, in the curve's own units.

    A recorded curve is normalised to the opening cash, so one deposit is
    ``amount_idr / INITIAL_IDR`` -- 0.5 for the owner's 5,000,000 against a 10,000,000 start --
    and no exchange rate is involved, because the run converted both at the same rate. (M0032's
    curve opens at 1.5 for exactly this reason: January's deposit is already in the first point.)

    ``{}`` for a lump-sum trial, which is every trial recorded before the contribution schedule
    existed. Without this, slicing a funded curve counts the owner's deposits as growth and
    compares the result against a benchmark that received none -- see ``regime.split``.

    This lived in ``commands/lab.py`` as ``_trial_deposits`` until the hard gate needed it too.
    It is here, not there, so that the gate, ``lab regime`` and ``lab walkforward`` share **one**
    de-funding path: a second reconstruction is a second chance to read a deposit as edge.
    """
    from seer_engine import dates as nyse
    from seer_engine.backtest.regime import bucket
    from seer_engine.backtest.runner import INITIAL_IDR
    from seer_engine.lab import runner as labrunner

    schedule = labrunner.recorded_contributions(conn, int(row["n"]))
    if schedule is None:
        return {}
    start, end = date.fromisoformat(row["start"]), date.fromisoformat(row["end"])
    unit = float(schedule.amount_idr / INITIAL_IDR)
    due = schedule.dates_in(start, end)
    credited: dict[date, float] = {}
    for d in due:
        session = d if nyse.is_session(d) else nyse.next_session(d)
        if session > end:
            continue
        credited[session] = credited.get(session, 0.0) + unit
    recorded = store.funding_of(conn, int(row["n"]))
    expected = int(recorded["deposits_n"])
    if len(due) != expected:
        raise store.LabError(
            f"{row['candidate_id']}: reconstructed {len(due)} deposits from "
            f"{recorded['schedule']!r} over {start}..{end}, but the trial records {expected}. "
            f"The schedule in sim.contributions has moved since this trial ran, so its curve "
            f"cannot be de-funded safely; `lab regime` will not guess"
        )
    return bucket(curve, credited)


@dataclass(frozen=True, slots=True)
class Geometry:
    """The benchmark curve and the folds cut from it -- the same split for every method.

    Global on purpose: the folds come from ``REF-SPY-HOLD``, not from the method under test, so
    two methods are never judged on different windows. Computed once per command and passed down,
    because ``lab status`` asks for a summary per dev-eligible method and re-cutting the folds
    each time would be the same arithmetic seven times over.
    """

    bench: tuple[tuple[date, float], ...]
    folds: tuple[wf.Fold, ...]


def _curve_of(row: sqlite3.Row) -> list[tuple[date, float]]:
    return [(date.fromisoformat(d), float(v)) for d, v in json.loads(row["curve_json"])]


def geometry(conn: sqlite3.Connection) -> Geometry:
    """The benchmark curve and its folds, or ``store.LabError`` saying what is missing.

    A missing benchmark **refuses**. The brief's open question 1 says a method with no scoreable
    folds must be refused and never waved through, and the same answer applies when it is the
    benchmark rather than the method that is absent: without it no fold can be scored at all. The
    message names ``REF-SPY-HOLD`` so the reader knows it is the lab's fixture that is wrong, not
    their method.
    """
    row = conn.execute(
        'SELECT n, candidate_id, start, "end", curve_json FROM trials '
        "WHERE window = 'dev' AND candidate_id = ? AND curve_json IS NOT NULL "
        "ORDER BY n LIMIT 1",
        (regime.BENCH_CANDIDATE,),
    ).fetchone()
    if row is None:
        raise store.LabError(
            f"no {regime.BENCH_CANDIDATE} dev trial, so no fold can be scored. The hard gate "
            f"measures every method against the lab's recorded SPY buy-and-hold curve; without "
            f"it there is no benchmark and nothing is promotable. This is the lab's fixture "
            f"missing, not your method failing"
        )
    bench = _curve_of(row)
    if len(bench) < 2:
        raise store.LabError(
            f"the recorded {regime.BENCH_CANDIDATE} dev curve has {len(bench)} point(s); the "
            f"hard gate cannot cut folds from it"
        )
    the_folds = wf.folds([d for d, _v in bench])
    if len(the_folds) < MIN_FOLDS:
        raise store.LabError(
            f"the recorded {regime.BENCH_CANDIDATE} curve yields {len(the_folds)} walk-forward "
            f"fold(s), below the minimum of {MIN_FOLDS}. Nothing is promotable on this geometry. "
            f"If walkforward.MIN_TRAIN_YEARS, walkforward.EVAL_YEARS or the dev window moved, "
            f"that is the change to argue with -- the gate will not lower its own bar to fit"
        )
    return Geometry(tuple(bench), the_folds)


def _dev_curves(conn: sqlite3.Connection, method_id: str) -> list[sqlite3.Row]:
    """Every dev trial of ``method_id`` that carries a non-empty curve.

    The empty filter is load-bearing: ``walkforward.evaluate`` takes ``min()`` over every curve's
    dates and raises ``ValueError`` -- not a ``LabError`` -- on a curve of ``[]``. Rows recorded
    with ``curve_json = '[]'`` exist (the lab's own test fixtures write them), so they are dropped
    here and a method with nothing left is refused below with a sentence instead of a traceback.

    Every variant is a candidate, eligible or not, exactly as ``lab walkforward`` does it: the
    fold's question is "which variant would the lab's own rule have named at this point in time",
    and that rule ranks the whole family of variants, not a pre-filtered subset.
    """
    rows = conn.execute(
        'SELECT n, candidate_id, start, "end", curve_json FROM trials '
        "WHERE window = 'dev' AND method_id = ? AND curve_json IS NOT NULL ORDER BY n",
        (method_id,),
    ).fetchall()
    return [r for r in rows if json.loads(r["curve_json"])]


def fold_record(
    conn: sqlite3.Connection, method_id: str, geo: Geometry | None = None
) -> wf.Record:
    """``method_id``'s whole walk-forward record, de-funded, on the shared geometry.

    The benchmark is measured without deposits: ``REF-SPY-HOLD`` is a seed buy-and-hold trial and
    was never fed. That is the same treatment ``lab walkforward`` gives it, deliberately -- the
    two must not disagree about what a fold says.
    """
    geo = geometry(conn) if geo is None else geo
    rows = _dev_curves(conn, method_id)
    if not rows:
        raise store.LabError(
            f"{method_id} has no dev trial carrying a monthly curve, so no fold can be scored "
            f"and it cannot be promoted. The hard gate fails closed on thin evidence: a method "
            f"with no out-of-sample record is not a method with a clean one"
        )
    curves = {r["candidate_id"]: _curve_of(r) for r in rows}
    deposits = {
        r["candidate_id"]: trial_deposits(conn, r, curves[r["candidate_id"]]) for r in rows
    }
    return wf.Record(method_id, wf.evaluate(curves, list(geo.bench), geo.folds, deposits))


def fold_summary(
    conn: sqlite3.Connection, method_id: str, geo: Geometry | None = None
) -> str:
    """One line: ``"3 of 4 folds"``, or ``"3 of 4 folds, pick changed"`` when unstable.

    Strict -- it raises ``store.LabError`` when the record cannot be computed -- because its
    caller is the pre-registration, and a pre-registration must never record a number it could
    not compute. Use ``summary`` for display.
    """
    return fold_record(conn, method_id, geo).summary()


def failed_kin(conn: sqlite3.Connection, method_id: str) -> tuple[str, ...]:
    """Every method in ``method_id``'s kin that reads ``test-failed``; ``()`` when clean.

    Kin is the ``family`` string **union** the transitive ancestors reached through
    ``parent_id``, excluding the method itself. See (D4) in the module docstring for why that
    union and not the full connected component, with the measurement that decided it.

    The ancestor walk carries a ``seen`` set: ``methods.parent_id`` is a self-referencing foreign
    key with no cycle constraint, so a cycle would otherwise hang the gate.
    """
    row = store.get_method(conn, method_id)
    if row is None:
        raise store.LabError(f"no method {method_id}")

    ancestors: set[str] = set()
    cur = row["parent_id"]
    while cur is not None and cur not in ancestors:
        ancestors.add(str(cur))
        parent = store.get_method(conn, str(cur))
        cur = None if parent is None else parent["parent_id"]

    kin = set(ancestors)
    for r in conn.execute("SELECT id FROM methods WHERE family = ?", (row["family"],)):
        kin.add(str(r["id"]))
    kin.discard(method_id)
    if not kin:
        return ()

    ids = sorted(kin)
    marks = ", ".join("?" for _ in ids)
    bad = conn.execute(
        f"SELECT id FROM methods WHERE id IN ({marks}) AND status = 'test-failed' ORDER BY id",
        tuple(ids),
    ).fetchall()
    return tuple(str(r["id"]) for r in bad)


def family_state(conn: sqlite3.Connection, method_id: str) -> str:
    """``"clean"``, or which kin read ``test-failed`` -- what the pre-registration records.

    Phrased as a state rather than a boolean because the pre-registration is read years later by
    someone asking what was true when the promise was made, and "clean" is a claim about the
    whole kin set, not about a flag.
    """
    bad = failed_kin(conn, method_id)
    if not bad:
        return "clean"
    return f"blocked: {', '.join(bad)} read test-failed"


def summary(conn: sqlite3.Connection, method_id: str, geo: Geometry | None = None) -> str:
    """One display line for ``method_id``: the fold record and the kin state.

    Lenient on purpose -- it catches ``store.LabError`` and returns the reason as text. Its
    caller is ``lab status``, which must keep printing on a lab whose benchmark is missing or
    whose method has no curve. A report that dies on one row is a worse report than one that says
    why that row is blank.
    """
    try:
        folds = fold_record(conn, method_id, geo).summary()
    except store.LabError as e:
        folds = f"not scoreable ({e})"
    try:
        kin = family_state(conn, method_id)
    except store.LabError as e:
        kin = f"kin unknown ({e})"
    return f"{folds}; kin {kin}"


def check(conn: sqlite3.Connection, method_id: str) -> None:
    """Refuse ``method_id``'s promotion, or return. Raises ``store.LabError``.

    Called by ``commands/lab.py:_promote`` **before** ``prereg.promote_method``, so a refusal
    happens before the pre-registration file is written and before any status moves: the
    repository and the database are byte-identical afterwards.

    Silent for any status but ``dev-eligible``. That is the only edge into ``promoted`` that
    ``store.TRANSITIONS`` admits, so every promotion is gated; and the caller one line later is
    ``promote_method``, which refuses a wrong status with the message it already has. See the
    module docstring.

    The folds are checked before the kin. (F) is a statement about *this* method's own evidence,
    which is what the researcher asked about; (K) is about the company it keeps, and reads better
    second. Both are cheap -- SQL and arithmetic on recorded curves -- so the order is about the
    message, not the cost.
    """
    row = store.get_method(conn, method_id)
    if row is None:
        raise store.LabError(f"no method {method_id}")
    if str(row["status"]) != _GATED_STATUS:
        return

    geo = geometry(conn)
    record = fold_record(conn, method_id, geo)
    scored, total = len(record.scored), len(geo.folds)

    if scored < total:
        raise store.LabError(
            f"{method_id} is scoreable on only {scored} of the {total} walk-forward folds, so "
            f"its out-of-sample record is thinner than the lab's own window. The hard gate fails "
            f"closed on thin evidence: a method must be scoreable on every fold the geometry "
            f"yields. Nothing was written and no status moved"
        )
    if scored < MIN_FOLDS:
        raise store.LabError(
            f"{method_id} has {scored} scoreable fold(s), below the minimum of {MIN_FOLDS}. A "
            f"strict majority of an odd number of folds is a coin flip under the null, so the "
            f"minimum is not negotiable from inside the code -- see hardgate.COIN_FLIP_NULL. "
            f"Nothing was written and no status moved"
        )
    if not record.majority:
        raise store.LabError(
            f"{method_id} wins {record.summary()} and is not promoted: the hard gate requires a "
            f"strict majority of the walk-forward folds. A method that wins its dev average but "
            f"loses the folds is a selection, not an edge. Nothing was written and no status "
            f"moved. There is no override -- if the rule is wrong, change it in "
            f"seer_engine/lab/hardgate.py and argue for it in the commit"
        )

    bad = failed_kin(conn, method_id)
    if bad:
        raise store.LabError(
            f"{method_id} is not promoted: {', '.join(bad)} already read test-failed, and "
            f"{'they are' if len(bad) > 1 else 'it is'} kin -- same family ({row['family']!r}) "
            f"or an ancestor through parent_id. A new variant of a family that has been disproven "
            f"out of sample is not a fresh candidate. Nothing was written and no status moved. "
            f"There is no override -- if this family deserves another look, that is an argued "
            f"change to the rule, in git"
        )
