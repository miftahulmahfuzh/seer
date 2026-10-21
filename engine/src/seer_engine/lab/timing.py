"""``lab timing``: *when* in a window a lead was earned, not just how big it was.

**The failure this exists to stop.** Every method in this lab is scored on an average over its
whole window. M0267 was worth 4.84 points a year on the prices and delivered 1.03 points to the
owner's money, because all of its value happened in the first three years of sixteen, when a fifth
of his money had been paid in (insight 515). Nothing the lab printed would have shown that: the
headline read like a comfortable win. The wish that followed (insight 517) is this module.

**What it prints.** For one recorded trial against one control, two things nothing else reports:

1. **Where the lead was earned.** The window is cut into the eras the lab already reasons in
   (``exposure.ERAS``), and each era's own months' contribution to the cumulative lead is printed
   as a share of the whole. Beside it, the share of the owner's money that had arrived by that
   era's last day. A lead spread evenly across the eras is a different animal from one earned in
   a single crash, and today those two print identically.
2. **The half-lead line.** The date by which half the lead had been earned, and how much of the
   money had arrived by then. That is insight 517's "second, cheaper version of the same idea",
   and on M0267 it is one line: *half the lead was earned by 2001-02-28, when 8.9% of the money
   had arrived.*

**The attribution is exact, not modelled.** Each month's contribution is the difference of the two
de-funded curves' log returns over that month, and every month of the window is assigned to
exactly one era by the date it **ends** on -- so January 2009's return belongs to 2009-2015, and
the shares add to the whole by construction. This is why the stepwise sum is used rather than
slicing each era with :func:`walkforward.measure` and differencing: a slice begins at the first
curve point *inside* the era, so the month that straddles each boundary falls into neither slice
and is silently dropped. On M0267 that one month is worth 6.2 points of the 2009-2015 figure.

The familiar per-era ``lead a year`` is printed beside the share anyway, and it **is**
:func:`walkforward.measure`'s own slice, so this report reconciles line for line with
``lab exposure``, ``lab gate`` and ``lab survivorship`` rather than quietly disagreeing with them.
The two columns answer different questions -- "how fast, inside this era" and "how much of the
whole lead came from here" -- and the report says so.

**The delivered lead is recorded, not reconstructed.** ``trial_funding`` already holds the
money-weighted return of the funded run and of SPY total return fed the same deposits on the same
days. Their difference is what the owner's money actually received, to the lab's own numbers, with
no model in between. The paper lead is the de-funded whole-window figure. Their ratio is the
headline M0267 would have failed on, and it is two recorded columns and a subtraction.

**The era table is imported, never restated.** ``exposure.ERAS`` is the lab's one era table and a
fifth definition here would make two reports of the same trial disagree about what "2009-2015"
means. One era in that table is deliberately nested inside another (2008 sits inside 2003-2008,
because the crash is the year a parked holding earns its keep). A nested era cannot be part of a
partition, so :data:`PARTITION` drops it generically -- any era contained in another -- and the
nested ones are printed as detail beneath the total, labelled as not added in.

**A report, not a trial.** Nothing is written: no ``trials``, ``trial_moments``, ``trial_funding``,
``trial_provenance``, ``insights`` or ``method_folds`` row, no status, and -- unlike
``lab survivorship`` and ``lab costs`` -- no journal entry on any path, so running it twice costs
nothing and leaves no record to undo. The test window is never read and a ``window = 'test'`` row
is refused by name at the door, through ``shortfall.resolve_trial``.

Pure arithmetic over recorded rows: no research store, no backtest, no market, no method file.
"""

from __future__ import annotations

import csv
import json
import logging
import math
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from seer_engine.backtest import regime
from seer_engine.backtest.metrics import DASH, to_fixed
from seer_engine.lab import hardgate, shortfall, store
from seer_engine.lab import walkforward as wf
from seer_engine.lab.exposure import ERAS

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- the knobs

#: The eras that partition a window: ``exposure.ERAS`` minus any era wholly inside another. The
#: test is generic rather than a hardcoded "skip 2008", so a sixth era added to the table one day
#: lands here correctly without this module being edited.
PARTITION: tuple[tuple[str, date, date], ...] = tuple(
    era for era in ERAS
    if not any(o is not era and o[1] <= era[1] and era[2] <= o[2] for o in ERAS)
)

#: The eras of ``ERAS`` that :data:`PARTITION` dropped, printed as detail and never added in.
NESTED: tuple[tuple[str, date, date], ...] = tuple(e for e in ERAS if e not in PARTITION)

#: Steps whose end date falls in no era of the table at all. A dev trial has none, but printing
#: the bucket when it is non-empty is what makes "the shares add to 100%" a checkable claim
#: rather than a hope.
OUTSIDE = "outside the era table"

#: Fewest common months before a trial is scored at all. Two eras of three months each would give
#: shares that mean nothing; two years is the shortest window any recorded dev trial has.
MIN_MONTHS = 24

#: Below this much total lead there is no lead to attribute, and a share of it is noise divided by
#: noise. In log points of cumulative relative gain over the whole window.
MIN_EDGE = 0.01

#: The smallest whole-window lead the sweep will attribute, in points a year. Below half a point
#: a year nobody would call the gap a lead, and the half-way point of a lead that small is noise
#: crossing a line: at no floor at all the sweep's worst offenders are trials leading SPY by 0.05
#: pts/yr. Measured, the stable half of the answer does not depend on this number (the median
#: holds at 33.9% across every floor in :data:`FLOORS`) and the tail does -- which is why the
#: report prints both and says which is which.
MIN_LEAD = 0.005

#: Floors the sweep re-counts itself at, so the floor above is visibly not what the answer rests
#: on. Same discipline as ``lab shortfall``'s name-count sensitivity band.
FLOORS: tuple[float, ...] = (0.0, 0.005, 0.01, 0.02)

#: The sweep's ladder. A trial is "front-loaded" at a bar when half its lead was earned before
#: that share of the owner's money had arrived. 50% is the neutral point -- a lead earned at a
#: steady rate per dollar held reaches its half-way mark when about half the money is in -- so the
#: bars below it are the ones that say the average is flattering the method.
LADDER: tuple[float, ...] = (0.10, 0.25, 0.50)

#: The bar the sweep's headline count is quoted at. A reporting threshold, not a gate: nothing
#: refuses on it, and the ladder beside it is there so a reader can move it.
BAR = 0.25


# --------------------------------------------------------------------------- small helpers


def pts(v: float | None, digits: int = 2) -> str:
    """A points figure with an ASCII sign. ``shortfall.pts``, reused rather than restated."""
    return shortfall.pts(v, digits)


def share(v: float | None, digits: int = 1) -> str:
    """A share of the lead, as a signed percentage. A share above 100% is real and is printed."""
    if v is None:
        return DASH
    return ("+" if v >= 0 else "-") + to_fixed(abs(v * 100.0), digits) + "%"


def plain(v: float | None, digits: int = 1) -> str:
    """An unsigned percentage -- a share of money paid in, which is never negative."""
    return DASH if v is None else to_fixed(v * 100.0, digits) + "%"


# --------------------------------------------------------------------------- reading the lab


def benchmark_row(conn: sqlite3.Connection) -> sqlite3.Row:
    """The recorded ``REF-SPY-HOLD`` dev trial, in full. Raises ``LabError``.

    Found through :func:`shortfall.benchmark`, which is itself ``hardgate.benchmark_n``'s rule, so
    this report, ``lab shortfall`` and the promotion gate can never be talking about three
    different benchmarks. A test asserts all three agree.
    """
    _curve, n = shortfall.benchmark(conn)
    row = conn.execute("SELECT * FROM trials WHERE n = ?", (n,)).fetchone()
    if row is None:  # pragma: no cover - benchmark() just read this row by this n
        raise store.LabError(f"the benchmark trial #{n} vanished between two reads")
    return row


def funding_lead(
    conn: sqlite3.Connection, row: sqlite3.Row, control: sqlite3.Row
) -> tuple[float | None, str]:
    """What the owner's money actually received, from recorded columns alone, and how.

    Against ``REF-SPY-HOLD`` the answer is the trial's **own** ``trial_funding`` row: ``mwr`` is
    the money-weighted return of the funded run and ``spy_tr_mwr`` is SPY total return fed the
    same cashflows on the same sessions, so their difference is already deposit-matched and no
    second curve is touched. Against a sibling arm it is the two arms' own ``mwr`` figures, which
    were fed the same schedule over the same window.

    ``None`` with a reason when either side records no funding -- the 128 trials recorded before
    the contribution schedule existed ran lump-sum, and for those "what the money received" and
    "what the prices did" are the same question.
    """
    mine = store.funding_of(conn, int(row["n"]))
    if mine is None or mine["mwr"] is None:
        return None, f"{row['candidate_id']} records no money-weighted return (it ran lump-sum)"
    if str(control["candidate_id"]) == regime.BENCH_CANDIDATE:
        theirs = mine["spy_tr_mwr"]
        if theirs is None:
            return None, f"{row['candidate_id']} records no deposit-matched SPY return"
        return float(mine["mwr"]) - float(theirs), (
            "the trial's own recorded money-weighted return minus SPY total return fed the same "
            "deposits on the same days"
        )
    other = store.funding_of(conn, int(control["n"]))
    if other is None or other["mwr"] is None:
        return None, f"{control['candidate_id']} records no money-weighted return"
    if int(mine["deposits_n"]) != int(other["deposits_n"]):
        return None, (
            f"{row['candidate_id']} received {mine['deposits_n']} deposits and "
            f"{control['candidate_id']} received {other['deposits_n']}, so their money-weighted "
            f"returns are not comparable"
        )
    return float(mine["mwr"]) - float(other["mwr"]), (
        "both arms' recorded money-weighted returns, over the same schedule and window"
    )


# --------------------------------------------------------------------------- the arithmetic


def steps(
    mine: Sequence[tuple[date, float]],
    theirs: Sequence[tuple[date, float]],
    lo: date,
    hi: date,
) -> list[tuple[date, float]]:
    """``(month end, this month's lead in log points)`` for every month both curves share.

    Both curves must already be de-funded. Months are matched by date and the pair is cut to
    ``lo..hi`` *before* the differences are taken, so a benchmark that starts years earlier
    contributes nothing but the opening mark. A month present on one curve and not the other is
    dropped rather than interpolated: this module measures, it does not fill in.
    """
    other = dict(theirs)
    pairs = [(d, v, other[d]) for d, v in mine if lo <= d <= hi and d in other and v > 0 and other[d] > 0]
    out: list[tuple[date, float]] = []
    for i in range(1, len(pairs)):
        d, v, w = pairs[i]
        _pd, pv, pw = pairs[i - 1]
        out.append((d, math.log(v / pv) - math.log(w / pw)))
    return out


def paid_in(
    curve: Sequence[tuple[date, float]], deposits: Mapping[date, float]
) -> dict[date, float]:
    """Everything the owner had paid in by each month end, as a share of what he ever pays in.

    The opening mark is money too: a recorded funded curve opens at 1.5 because the starting
    capital and January's deposit are both already in it (``hardgate.trial_deposits``). So the
    running total starts at ``curve[0]``'s value rather than at zero, and the last month reads
    1.0 by construction. For a lump-sum trial every month reads 1.0, which is the truth: all of
    the money was there from the first day.
    """
    if not curve:
        return {}
    running = float(curve[0][1])
    total = running + sum(deposits.values())
    out: dict[date, float] = {}
    for d, _v in curve:
        running += deposits.get(d, 0.0)
        out[d] = running / total if total > 0 else 1.0
    return out


@dataclass(frozen=True, slots=True)
class EraShare:
    """One era's own months: what they contributed, and how much money was in by their end."""

    label: str
    start: date
    end: date
    months: int
    edge: float            # log points of cumulative lead earned inside this era
    share: float | None    # that, over the whole window's lead; None when there is no lead
    lead: float | None     # walkforward.measure's own annualised lead over this era's slice
    funded: float | None   # share of everything ever paid in, by this era's last day
    nested: bool           # inside another era of the table, so printed but never added in


@dataclass(frozen=True, slots=True)
class Timing:
    """When one trial's lead over one control was earned."""

    trial_n: int
    candidate_id: str
    method_id: str
    control_id: str
    control_n: int
    window: tuple[date, date]
    months: int
    deposits: int
    schedule: str | None
    paper_lead: float | None       # de-funded whole-window lead a year
    delivered_lead: float | None   # recorded money-weighted lead a year
    delivered_how: str
    total_edge: float              # log points of cumulative lead over the whole window
    eras: tuple[EraShare, ...]
    outside: float                 # log points whose month fell in no era of the table
    half_date: date | None
    half_funded: float | None
    weighted: float | None         # capital-weighted share of the lead: modelled, see measure()
    warnings: tuple[str, ...]

    @property
    def delivered_fraction(self) -> float | None:
        """Delivered lead over paper lead. None unless both are recorded and the paper lead is up."""
        if self.delivered_lead is None or self.paper_lead is None or self.paper_lead <= 0:
            return None
        return self.delivered_lead / self.paper_lead

    @property
    def front_loaded(self) -> bool | None:
        """Was half the lead earned before :data:`BAR` of the money had arrived?

        ``None`` when the question does not arise: a lump-sum trial (the money was all there from
        the first day), or a trial with no lead to attribute.
        """
        return None if self.half_funded is None or not self.deposits else self.half_funded < BAR

    def at(self, bar: float) -> bool | None:
        """:attr:`front_loaded` at an arbitrary bar, for the ladder."""
        return None if self.half_funded is None or not self.deposits else self.half_funded < bar


def measure(
    conn: sqlite3.Connection, row: sqlite3.Row, control: sqlite3.Row | None = None
) -> Timing:
    """When ``row``'s lead over ``control`` was earned. Reads the lab; writes nothing; no store.

    ``control`` defaults to the recorded ``REF-SPY-HOLD`` curve, which every dev trial can be read
    against. A sibling arm of the same method is the sharper comparison when one exists -- M0267's
    whole finding is gate against mirror, not gate against SPY -- and is passed in by the caller.

    Both curves are de-funded through :func:`hardgate.trial_deposits` before anything is read from
    them, each with **its own** schedule: a funded book compared against a funded control on raw
    curves would credit one side's deposits as edge and not the other's.

    ``weighted`` is the one modelled number here and is labelled as such everywhere it is printed:
    each month's lead re-weighted by the share of the owner's money that was in the account during
    it, over the unweighted total. It answers "how much of this paper lead could have reached the
    money" on the assumption that a month's lead scales with what was in the account -- which is
    the assumption insight 515 states in words. :attr:`delivered_fraction` is the same quantity
    measured rather than modelled, and the report prints them side by side so the model is visibly
    checked against the record on every run.
    """
    control = benchmark_row(conn) if control is None else control
    if int(control["n"]) == int(row["n"]):
        raise store.LabError(
            f"{row['candidate_id']} cannot be its own control: a trial's lead over itself is "
            f"zero in every era and the shares of zero mean nothing"
        )
    window = shortfall.trial_window(row)
    curve = shortfall.curve_of(row)
    other = shortfall.curve_of(control)
    deposits = hardgate.trial_deposits(conn, row, curve)
    their_deposits = hardgate.trial_deposits(conn, control, other)
    clean = regime.defunded(curve, deposits)
    their_clean = regime.defunded(other, their_deposits)

    months = steps(clean, their_clean, window[0], window[1])
    if len(months) < MIN_MONTHS:
        raise store.LabError(
            f"trial #{row['n']} ({row['candidate_id']}) and {control['candidate_id']} share "
            f"{len(months)} month(s) inside {window[0]}..{window[1]}; {MIN_MONTHS} are needed "
            f"before a share of the lead means anything"
        )
    total = sum(e for _d, e in months)

    funded = paid_in(curve, deposits)
    mine = wf.measure(curve, window[0], window[1], deposits)
    theirs = wf.measure(other, window[0], window[1], their_deposits)
    paper = (
        None
        if mine is None or theirs is None or mine.cagr is None or theirs.cagr is None
        else mine.cagr - theirs.cagr
    )
    delivered, how = funding_lead(conn, row, control)

    eras: list[EraShare] = []
    seen: set[date] = set()
    for label, start, end in ERAS:
        lo, hi = max(start, window[0]), min(end, window[1])
        inside = [(d, e) for d, e in months if lo <= d <= hi]
        if not inside:
            continue
        nested = (label, start, end) in NESTED
        if not nested:
            seen.update(d for d, _e in inside)
        got = wf.measure(curve, lo, hi, deposits)
        ref = wf.measure(other, lo, hi, their_deposits)
        lead = (
            None
            if got is None or ref is None or got.cagr is None or ref.cagr is None
            else got.cagr - ref.cagr
        )
        edge = sum(e for _d, e in inside)
        eras.append(EraShare(
            label=label, start=lo, end=hi, months=len(inside), edge=edge,
            share=None if abs(total) < MIN_EDGE else edge / total,
            lead=lead,
            funded=max((funded[d] for d in funded if d <= hi), default=None),
            nested=nested,
        ))
    outside = sum(e for d, e in months if d not in seen)

    half_date, half_funded = None, None
    if abs(total) >= MIN_EDGE:
        running = 0.0
        for d, e in months:
            running += e
            if (total > 0 and running >= total / 2) or (total < 0 and running <= total / 2):
                half_date, half_funded = d, funded.get(d)
                break

    weighted = None
    if abs(total) >= MIN_EDGE:
        before = dict(zip([d for d, _v in curve][:-1], [d for d, _v in curve][1:]))
        held = {nxt: funded.get(prev) for prev, nxt in before.items()}
        wsum = sum(e * held[d] for d, e in months if held.get(d) is not None)
        weighted = wsum / total

    warnings: list[str] = []
    problems = hardgate.mismatches(conn, int(control["n"]), [row])
    if problems:
        warnings.append(
            f"WARNING {row['candidate_id']} is not comparable with {control['candidate_id']}: "
            f"{hardgate.describe(problems)}. Every number below is cross-store arithmetic, and "
            f"`lab promote` refuses it (lab/hardgate.py, D10)"
        )
    if outside and abs(total) >= MIN_EDGE:
        warnings.append(
            f"NOTE {share(outside / total)} of the lead was earned in months the era table does "
            f"not cover; it is printed as its own line and is counted in the total"
        )

    record = store.funding_of(conn, int(row["n"]))
    return Timing(
        trial_n=int(row["n"]),
        candidate_id=str(row["candidate_id"]),
        method_id=str(row["method_id"]),
        control_id=str(control["candidate_id"]),
        control_n=int(control["n"]),
        window=window,
        months=len(months),
        deposits=len(deposits),
        schedule=None if record is None else str(record["schedule"]),
        paper_lead=paper,
        delivered_lead=delivered,
        delivered_how=how,
        total_edge=total,
        eras=tuple(eras),
        outside=outside,
        half_date=half_date,
        half_funded=half_funded,
        weighted=weighted,
        warnings=tuple(warnings),
    )


# --------------------------------------------------------------------------- what it prints


def format_report(t: Timing) -> str:
    """The whole report, in plain words. The owner reads lab output and is not a quant."""
    out: list[str] = list(t.warnings)
    if t.warnings:
        out.append("")

    out.append(
        f"Trial #{t.trial_n}  {t.candidate_id}  (method {t.method_id}), dev window "
        f"{t.window[0]} to {t.window[1]}."
    )
    out.append(
        f"Measured against {t.control_id} (trial #{t.control_n}) over {t.months} shared months."
    )
    if t.deposits:
        out.append(
            f"The owner's deposits ({t.schedule}) are removed from both curves before any return"
        )
        out.append(
            f"is read, so a deposit is never counted as a gain on either side. {t.deposits} of "
            f"them land"
        )
        out.append("inside the curve; the first is already in its opening mark.")
    else:
        out.append(
            "This trial ran lump-sum: all of its money was there on the first day, so the "
            "question this"
        )
        out.append("report exists to ask does not arise for it.")
    out.append("")

    out.append(f"  the lead on paper, deposits removed          {pts(t.paper_lead):>10} pts/yr")
    out.append(f"  the lead the owner's money received          {pts(t.delivered_lead):>10} pts/yr")
    frac = t.delivered_fraction
    if frac is not None:
        out.append(f"  delivered                                    {plain(frac):>10} of the paper lead")
    out.append(f"  ({t.delivered_how})")
    out.append("")

    out.append(
        "When the lead was earned. A month belongs to the era it ENDS in, so every month of the"
    )
    out.append(
        "window is counted once and the shares add to the whole. `lead a year` beside it is the"
    )
    out.append(
        "familiar per-era figure `lab exposure` and `lab gate` print -- how fast the lead came "
        "inside"
    )
    out.append(
        "that era -- and it does not add up, because an annual rate never does. `money in` is "
        "the"
    )
    out.append("share of everything the owner ever pays in that had arrived by the era's last day.")
    clipped = [
        e for e in t.eras
        if not e.nested and (e.start, e.end) != next(
            ((s_, e_) for lab, s_, e_ in ERAS if lab == e.label), (e.start, e.end)
        )
    ]
    for e in clipped:
        out.append(
            f"An era is clipped to the trial's own window: {e.label} here is {e.start} to "
            f"{e.end}."
        )
    out.append("")
    out.append(f"  {'era':<14}{'months':>7}{'share of lead':>15}{'lead a year':>14}{'money in':>11}")
    for e in t.eras:
        if e.nested:
            continue
        out.append(
            f"  {e.label:<14}{e.months:>7}{share(e.share):>15}"
            f"{pts(e.lead):>12} pts{plain(e.funded):>11}"
        )
    if t.outside:
        out.append(
            f"  {OUTSIDE:<14}{'':>7}{share(None if abs(t.total_edge) < MIN_EDGE else t.outside / t.total_edge):>15}"
        )
    out.append("  " + "-" * 59)
    out.append(
        f"  {'whole window':<14}{t.months:>7}{'100.0%' if abs(t.total_edge) >= MIN_EDGE else DASH:>15}"
        f"{pts(t.paper_lead):>12} pts{plain(1.0):>11}"
    )
    for e in t.eras:
        if e.nested:
            out.append(
                f"    of which {e.label:<6}{e.months:>5}{share(e.share):>15}"
                f"{pts(e.lead):>12} pts   (inside another era, not added in)"
            )
    out.append("")

    if t.half_date is not None:
        out.append(
            f"Half of the lead had been earned by {t.half_date}, when {plain(t.half_funded)} of "
            f"the money had arrived."
        )
        if t.deposits and t.half_funded is not None:
            if t.half_funded < BAR:
                out.append(
                    "That is the shape insight 515 is about: the rule did its work on an account "
                    "that was"
                )
                out.append(
                    "still mostly empty, and the whole-window average is flattering it. Read the "
                    "delivered"
                )
                out.append("lead above, not the paper one.")
            else:
                out.append(
                    "The lead is not front-loaded: it was still being earned once most of the "
                    "money had"
                )
                out.append("arrived, so the whole-window average is not flattering it on timing.")
    else:
        out.append(
            f"There is no lead to attribute: the whole window's lead is {share(t.total_edge)} of "
            f"cumulative"
        )
        out.append("gain, under the floor at which a share of it would mean anything.")
    out.append("")

    if t.weighted is not None:
        out.append(
            "Modelled check. Re-weighting each month's lead by the money that was in the account"
        )
        out.append(
            f"during it leaves {plain(t.weighted)} of the paper lead -- against the "
            f"{plain(frac) if frac is not None else DASH} the recorded"
        )
        out.append(
            "money-weighted returns actually delivered. The first is a model and the second is "
            "the"
        )
        out.append(
            "lab's own record; they are printed together so the model is checked on every run "
            "rather"
        )
        out.append("than trusted.")
        out.append("")

    out.append(
        "Why this is a separate report. A twenty-year average assumes twenty years of equally "
        "sized"
    )
    out.append(
        "money. The owner's account grows every month for as long as he keeps saving, so a rule "
        "whose"
    )
    out.append(
        "value is concentrated early is worth a fraction of what its average says -- and one that "
        "earns"
    )
    out.append("steadily, or late, is worth more. Nothing else the lab prints can tell those apart.")
    return "\n".join(out)


# --------------------------------------------------------------------------- the back catalogue


@dataclass(frozen=True, slots=True)
class Skip:
    """A trial the sweep could not score, and the plain reason why."""

    trial_n: int
    candidate_id: str
    method_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class Band:
    """The sweep's answer re-counted at one lead floor, so the floor is visibly not the answer."""

    trials: int
    median: float | None   # money paid in at the half-lead date, median over the trials
    under_bar: int         # trials whose half-lead came before BAR of the money arrived
    under_half: int        # ... before half of it, which is the neutral point
    reversed_sign: int     # a positive paper lead and a negative delivered lead

    @classmethod
    def of(cls, ts: Sequence[Timing]) -> Band:
        """One band over ``ts``. Every number is a count or a median; nothing is modelled."""
        half = sorted(t.half_funded for t in ts if t.half_funded is not None)
        mid = None if not half else (
            half[len(half) // 2] if len(half) % 2
            else (half[len(half) // 2 - 1] + half[len(half) // 2]) / 2
        )
        return cls(
            trials=len(ts),
            median=mid,
            under_bar=sum(1 for t in ts if t.at(BAR)),
            under_half=sum(1 for t in ts if t.at(0.5)),
            reversed_sign=sum(
                1 for t in ts
                if t.delivered_lead is not None and t.delivered_lead < 0 < (t.paper_lead or 0.0)
            ),
        )


@dataclass(frozen=True, slots=True)
class Sweep:
    """The whole back catalogue, scored against one control each."""

    scored: tuple[Timing, ...]
    skipped: tuple[Skip, ...]
    ladder: tuple[tuple[float, int], ...]
    methods: tuple[tuple[str, Timing], ...]  # one headline arm per method, best MAR first
    floors: tuple[tuple[float, Band], ...]   # the same answer re-counted at each of FLOORS

    @property
    def head(self) -> tuple[Timing, ...]:
        """The scored trials whose lead clears :data:`MIN_LEAD` -- the ones the counts are over."""
        return tuple(t for t in self.scored if (t.paper_lead or 0.0) >= MIN_LEAD)

    @property
    def band(self) -> Band:
        """:attr:`head` as a :class:`Band`: the sweep's own headline numbers."""
        return Band.of(self.head)

    @property
    def flagged(self) -> tuple[Timing, ...]:
        """The scored trials whose lead was earned before :data:`BAR` of the money arrived."""
        return tuple(t for t in self.head if t.front_loaded)

    @property
    def flagged_methods(self) -> tuple[tuple[str, Timing], ...]:
        """The methods whose own headline arm is front-loaded."""
        return tuple((m, t) for m, t in self.methods if t.front_loaded)

    @property
    def reversed_sign(self) -> tuple[Timing, ...]:
        """Leads the prices earned and the owner's money did not: paper up, delivered down.

        The sharpest form of the M0267 finding and the only one with no threshold in it at all --
        two recorded ``trial_funding`` columns and a subtraction.
        """
        return tuple(
            t for t in self.head
            if t.delivered_lead is not None and t.delivered_lead < 0 < (t.paper_lead or 0.0)
        )


def sweep(conn: sqlite3.Connection, *, methods: Sequence[str] = ()) -> Sweep:
    """Every funded dev trial with a lead over ``REF-SPY-HOLD``, scored for when it was earned.

    Only funded trials are scored. A lump-sum trial's money was all there on the first day, so its
    half-lead funding share is 100% by construction and counting it as "not front-loaded" would
    pad the clean half of the answer with trials that were never asked the question. They are
    skipped by name and counted in the skips.

    A trial with no lead over the benchmark is skipped too: a share of a lead that does not exist
    is noise divided by noise, and the sweep is a count of how many *winners* won early.

    The headline arm of a method is its highest recorded MAR among the arms the sweep could score
    -- the arm whose whole-window average a reader would quote. ``lab promote``'s own choice is
    deliberately not reused: ``best_dev_eligible`` can name a control arm (memory
    ``seer-promoted-variant-can-be-a-control-arm``), and a report should describe the method's
    best-looking arm rather than the one the gate happens to pick.
    """
    control = benchmark_row(conn)
    sql = "SELECT * FROM trials WHERE window = 'dev' AND n <> ? ORDER BY n"
    rows = [r for r in conn.execute(sql, (int(control["n"]),))]
    if methods:
        want = {str(m).upper() for m in methods}
        rows = [r for r in rows if str(r["method_id"]).upper() in want]

    scored: list[Timing] = []
    skipped: list[Skip] = []
    for row in rows:
        skip = lambda why: skipped.append(  # noqa: E731 - one use, reads better inline
            Skip(int(row["n"]), str(row["candidate_id"]), str(row["method_id"]), why)
        )
        if not row["curve_json"] or not json.loads(row["curve_json"]):
            skip("records no equity curve")
            continue
        if store.funding_of(conn, int(row["n"])) is None:
            skip("ran lump-sum, so all of its money was there on the first day")
            continue
        try:
            t = measure(conn, row, control)
        except store.LabError as e:
            skip(str(e).split(";")[0])
            continue
        if t.paper_lead is None or t.paper_lead <= 0 or abs(t.total_edge) < MIN_EDGE:
            skip("has no lead over the benchmark to attribute")
            continue
        scored.append(t)

    head = [t for t in scored if (t.paper_lead or 0.0) >= MIN_LEAD]
    ladder = tuple((bar, sum(1 for t in head if t.at(bar))) for bar in LADDER)
    floors = tuple(
        (floor, Band.of([t for t in scored if (t.paper_lead or 0.0) >= floor]))
        for floor in FLOORS
    )

    mar = {int(r["n"]): r["mar"] for r in rows}
    best: dict[str, Timing] = {}
    for t in head:
        cur = best.get(t.method_id)
        if cur is None or (mar.get(t.trial_n) or -math.inf) > (mar.get(cur.trial_n) or -math.inf):
            best[t.method_id] = t
    heads = tuple(sorted(best.items(), key=lambda kv: kv[0]))
    return Sweep(tuple(scored), tuple(skipped), ladder, heads, floors)


def format_sweep(s: Sweep, *, limit: int = 25) -> str:
    """The back catalogue in plain words: what holds, what moves with the floor, and the tail."""
    head, band = s.head, s.band
    out: list[str] = []
    out.append(
        f"Scored {len(head)} funded dev trial(s) across {len(s.methods)} method(s), each against "
        f"the recorded"
    )
    out.append(
        f"{regime.BENCH_CANDIDATE} curve. A trial is counted when it leads that curve by at least "
        f"{plain(MIN_LEAD, 1)} a year;"
    )
    out.append(
        f"{len(s.scored) - len(head)} lead(s) under that floor and {len(s.skipped)} other trial(s) "
        f"were not counted, for the reasons below."
    )
    out.append("")
    out.append(
        "When the lab's leads were earned. A trial is counted at a bar when half its whole-window"
    )
    out.append(
        "lead had been earned before that share of the owner's money had arrived. Half the money "
        "is"
    )
    out.append(
        "the neutral point: a lead earned at a steady rate per dollar held reaches its half-way "
        "mark"
    )
    out.append(
        "there, because the owner's deposits are level and his money-in line is therefore "
        "straight."
    )
    out.append("So everything under 50% says the whole-window average is flattering the method.")
    out.append("")
    for bar, n in s.ladder:
        pc = n / len(head) if head else 0.0
        out.append(
            f"  half the lead earned on under {plain(bar, 0):>4} of the money   "
            f"{n:>4} of {len(head):<5} ({plain(pc)})"
        )
    out.append("")
    out.append(
        f"  the median trial had half its lead by the time {plain(band.median)} of the money had "
        f"arrived"
    )
    out.append(
        f"  {band.reversed_sign} trial(s) lead on paper and LOSE on the owner's money: a positive "
        f"paper lead"
    )
    out.append(
        "    and a negative delivered one, from two recorded columns and a subtraction"
    )
    out.append("")
    out.append(
        "Counting one headline arm per method -- its highest recorded MAR among the arms counted "
        "--"
    )
    out.append(
        f"{len(s.flagged_methods)} of {len(s.methods)} method(s) show M0267's shape at the "
        f"{plain(BAR, 0)} bar."
    )
    out.append("")

    out.append(
        "Does the floor make the answer? Re-counted at four floors. The median and the 50% count "
        "hold;"
    )
    out.append(
        "the tail at the tight bars does not, because the half-way point of a lead worth a "
        "twentieth"
    )
    out.append("of a point a year is noise crossing a line. Quote the stable two.")
    out.append("")
    out.append(
        f"  {'floor':>8}{'trials':>8}{'median':>9}{'under ' + plain(BAR, 0):>11}"
        f"{'under 50%':>11}{'reversed':>10}"
    )
    for floor, b in s.floors:
        out.append(
            f"  {plain(floor, 1):>8}{b.trials:>8}{plain(b.median):>9}{b.under_bar:>11}"
            f"{b.under_half:>11}{b.reversed_sign:>10}"
        )
    out.append("")

    worst = sorted(
        (t for t in head if t.half_funded is not None),
        key=lambda t: (t.half_funded, -(t.paper_lead or 0.0)),
    )
    out.append("The tail, earliest half-lead first. `paper` is the de-funded lead over SPY TR a")
    out.append("year; `delivered` is what the owner's money received, from the recorded")
    out.append("money-weighted returns.")
    out.append("")
    out.append(
        f"  {'trial':>6}  {'candidate':<24}{'paper':>8}{'delivered':>11}{'half by':>12}"
        f"{'money in':>10}"
    )
    for t in worst[:limit]:
        out.append(
            f"  {t.trial_n:>6}  {t.candidate_id:<24}{pts(t.paper_lead):>8}"
            f"{pts(t.delivered_lead):>11}{str(t.half_date):>12}{plain(t.half_funded):>10}"
        )
    if len(worst) > limit:
        out.append(f"  ... and {len(worst) - limit} more, in --csv")
    out.append("")

    why: dict[str, int] = {}
    for sk in s.skipped:
        why[sk.reason] = why.get(sk.reason, 0) + 1
    out.append("Not scored:")
    for reason, n in sorted(why.items(), key=lambda kv: -kv[1]):
        out.append(f"  {n:>4}  {reason}")
    out.append(
        f"  {len(s.scored) - len(head):>4}  lead the benchmark by under {plain(MIN_LEAD, 1)} a "
        f"year, which is not a lead"
    )
    return "\n".join(out)


# --------------------------------------------------------------------------- csv


def csv_rows(ts: Sequence[Timing]) -> list[list[str]]:
    """Every scored trial's era shares at full precision, one row per era."""
    head = [
        "trial", "candidate", "method", "control", "era", "months", "edge_log_pts",
        "share_of_lead", "lead_per_year", "money_in_by_end", "nested",
        "paper_lead", "delivered_lead", "half_lead_date", "money_in_at_half",
    ]
    rows = [head]
    for t in ts:
        for e in t.eras:
            rows.append([
                str(t.trial_n), t.candidate_id, t.method_id, t.control_id, e.label,
                str(e.months), repr(e.edge), repr(e.share), repr(e.lead), repr(e.funded),
                "1" if e.nested else "0",
                repr(t.paper_lead), repr(t.delivered_lead),
                "" if t.half_date is None else t.half_date.isoformat(), repr(t.half_funded),
            ])
    return rows


def write_csv(ts: Sequence[Timing], path: Path) -> Path:
    """Write :func:`csv_rows` to ``path``. The one file this module touches."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(csv_rows(ts))
    return path


__all__ = [
    "BAR", "LADDER", "MIN_EDGE", "MIN_MONTHS", "NESTED", "OUTSIDE", "PARTITION",
    "EraShare", "Skip", "Sweep", "Timing",
    "benchmark_row", "csv_rows", "format_report", "format_sweep", "funding_lead", "measure",
    "paid_in", "steps", "sweep", "write_csv",
]
