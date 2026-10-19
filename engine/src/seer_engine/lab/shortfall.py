"""``lab shortfall``: where one trial's gap to SPY went, with the residual left a residual.

**The failure this exists to stop.** The lab measures a trial's shortfall to SPY total return over
an era and prints one number. Whoever writes the analysis then names that number after whichever
ingredient they happened to be thinking about. For trial 828 (``M0244-PLACEBO30``) the name was
"equal-weight handicap", and it was promoted from one matched pair's shortfall to a universal
constant -- insight 461, a memory note, and the ``/sera`` synthesis page all carry it. The arm that
produced the number is a gated, fifteen-turns-a-year book drawn from the fifty strongest momentum
names. Three ingredients the name does not mention are inside the 8.2 points, and two of them can
be priced from rows the lab already has.

**What this module does.** It splits the era gap into two separately-computed named terms and one
residual::

    gap  =  -(gate premium)  -(fee drag)  +(pool + weighting residual)

and the residual is the term the other two do not explain. It is never named after a cause. That
is the whole discipline: a residual small enough to ignore says the named terms account for the
gap; it does not say the residual's own ingredients are zero, and this module's output says so in
words rather than leaving a reader to infer it.

**An attribution under stated assumptions, not an identity.** The three terms do not come from one
decomposition of one quantity. The gap is measured; the gate premium and the fee drag are each
modelled from a different source; the residual absorbs the error of both. The report says this on
screen every time, because an attribution that forgets it is how the 8.2 became a constant.

**Rule 1: the gap is not recomputed.** It comes from :func:`walkforward.measure` over the recorded
``curve_json``, de-funded by :func:`hardgate.trial_deposits`, against the recorded
``REF-SPY-HOLD`` curve sliced the same way -- the identical path ``lab exposure``, ``lab gate``,
``lab survivorship`` and ``lab walkforward`` already take. ``trial_deposits``'s own docstring says
why: *a second reconstruction is a second chance to read a deposit as edge.* A trial whose curves
were measured on prices other than the benchmark's gets a WARNING line and its numbers anyway --
a report warns where the promotion gate refuses (hardgate D10) -- except under ``--against``,
where a split across two price fingerprints would be cross-store arithmetic and is refused.

**Rule 2: era exposure is era-resolved when it can be, and labelled when it cannot.**
``trials.exposure`` is a whole-window scalar and there is no per-era exposure anywhere in the
schema. Measured on the dev store, the shared SPY 200-day gate was on 71.2% of the whole window's
sessions and 80.6% of 2009-2015's. Trial 828 records exposure 0.692, so the book was about 97%
invested whenever the gate let it in, and its 2009-2015 exposure is ``0.692 x (0.806 / 0.712) =
0.784``. Pricing the gate at the recorded 0.692 instead gives 5.11 pts/yr where the era-resolved
figure gives 3.60 -- a 1.5 point error on an 8.2 point headline, and the residual flips sign with
it. The ratio carries the gate's era shape; the recorded exposure carries the book's own slot-fill
drag. When no store is given, when the book carries no shared gate, or when the recorded exposure
is *above* the gate's own on-share (so the book held money while the gate was off and the gate
does not govern all of it), the whole-window figure is used and the output says so, every time.

**Rule 3: the fee drag is modelled, not recovered.** The fees a run really paid live in
``RunStats.costs_usd``, which is not a ``trials`` column and cannot be recovered from one.
``trials.turnover`` is defined in ``book_runner._turnover`` as the sum of fill notionals -- buys
**and** sells -- over mean session equity over years, so it is a per-dollar-of-notional quantity
and composes directly with a per-dollar fee rate. That rate is one round trip of one slot through
:func:`turnover.round_trip`, divided by the two dollars of notional a round trip moves, averaged
over the era's own month offsets into the dev window so the ``$0.10`` floor's shrinking bite is
carried rather than averaged away. The book's name count is not in the row; it is read from the
recorded configuration when that is unambiguous and defaulted otherwise, the output always says
which, and a sensitivity band at 10, 20, 30 and 50 names is printed beside it -- measured, the
2009-2015 drag moves from 3.71 to 3.85 pts/yr across that whole range, so the guess is bounded and
visibly not what the answer rests on.

**Rule 4: the pool cannot be separated from one row, and this refuses to pretend.** Nothing in a
trials row names the pool the book was drawn from, so by default the two ingredients nobody can
price are reported as **one** ``pool + weighting`` residual. ``--against`` splits it by subtraction
against a sibling arm of the same method that shares the pool, the gate and the frame: that arm's
own residual is what the two have in common and goes to pool and frame, and only the remainder is
this arm's own weighting and selection. An ``--against`` from another method, or across a price
fingerprint the benchmark does not share, is refused rather than printed.

**Cash earns nothing -- after 2008.** The gate premium assumes money out of the market earned zero.
Memory (``seer-idle-cash-credit-worth-08-before-2008-only``) measured that this is right for
2009-2015 and wrong before 2008, when T-bills paid a real rate. So the caveat is carried **per
era** in :data:`CASH_NOTE` rather than one model being applied silently to all of them.

**A report, not a trial.** Nothing is written: no ``trials``, ``trial_moments``, ``trial_funding``,
``trial_provenance``, ``insights`` or ``method_folds`` row, no status, no journal. The test window
is never named and ``window = 'test'`` is refused at the door. The command prints
``store.dev_trial_count`` and ``store.test_looks`` before and after, the way ``lab turnover`` and
``lab regime`` do, so the invariant is visible on the terminal rather than merely asserted in a
test.

Pure but for one optional read: with ``--store`` it streams the gate symbol's rows out of the
store's own ``bars.csv`` and asks :func:`f_factor.trend_on` -- the lab's own definition of the
gate -- whether it was on, session by session. It opens no database but the lab's, runs no
backtest, and loads no market.
"""

from __future__ import annotations

import csv
import json
import logging
import re
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import numpy as np

from seer_engine import research
from seer_engine.backtest import regime
from seer_engine.backtest.metrics import DASH, to_fixed
from seer_engine.lab import hardgate, store, turnover
from seer_engine.lab import walkforward as wf
from seer_engine.lab.exposure import ERA_LABELS, ERAS, WHOLE
from seer_engine.lab.gate_probe import GATE_N, GATE_RULE, GATE_SYMBOL
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, trend_on

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- the knobs

#: The era this answers when the caller names none. It is the era the lab quotes its modern-era
#: verdicts over, and the era the published 8.2 was measured on.
DEFAULT_ERA = "2009-2015"

#: The book size the fee model assumes when the recorded configuration does not name one
#: unambiguously. The roster's own count, imported rather than restated.
DEFAULT_NAMES = turnover.ROSTER_NAMES

#: The band the report prints beside the fee drag, so a wrong book size is visibly bounded.
#: Measured 2026-10-19 at turnover 15.05 over 2009-2015: 3.71, 3.74, 3.78, 3.85 pts/yr.
SENSITIVITY_NAMES: tuple[int, ...] = (10, 20, 30, 50)

#: ``recorded exposure / the gate's own whole-window on-share``. Above 1 the book held money while
#: the gate was off -- a blend with an ungated leg, say -- so the gate does not govern the whole
#: book and scaling its exposure by the gate's era shape would be a different book's arithmetic.
MAX_GATE_FILL = 1.0

ERA_BASIS = "era-resolved"
WHOLE_BASIS = "whole-window"

#: Eight decimals, the precision ``lab turnover`` reports its own rates at.
RATE_Q = Decimal("0.00000001")

#: What the gate premium's "money out of the market earned nothing" assumption is worth, per era.
#: From the measurement in ``seer-idle-cash-credit-worth-08-before-2008-only``: T-bills paid a real
#: rate before 2008 and about nothing after it, so the assumption is right for one era and
#: generous to the book in the others. Keyed by the labels in ``exposure.ERA_LABELS``.
CASH_NOTE: Mapping[str, str] = {
    WHOLE: (
        "this era spans both: before 2008 the money the gate held back earned a real rate in "
        "T-bills, and after 2008 it earned about nothing. So the gate premium here is somewhat "
        "larger than the truth"
    ),
    "1996-2002": (
        "money out of the market really did earn something in these years -- T-bills paid a real "
        "rate -- so the gate premium below is LARGER than the truth and the residual beside it "
        "is correspondingly more negative"
    ),
    "2003-2008": (
        "T-bills still paid a real rate for most of these years, so the gate premium below is "
        "somewhat larger than the truth"
    ),
    "2008": (
        "T-bills still paid something through most of 2008, so the gate premium below is "
        "somewhat larger than the truth"
    ),
    "2009-2015": (
        "the assumption holds here: T-bills paid about nothing after 2008, so money out of the "
        "market really did earn nothing and the gate premium below is the right size"
    ),
}

#: The shared gate as a recorded configuration renders it. ``method.config_text`` writes a params
#: tree through ``registry._canon``, so the gate appears either as a ``trend`` pair on a
#: ``FactorParams`` or as the ``TimingParams`` that *is* the gate. Both patterns are built from
#: ``gate_probe``'s own constants so they cannot drift from the thing they detect. Whitespace is
#: tolerated because the renderer's spacing is not part of this module's contract with it.
_TREND_SITE = re.compile(
    r"\btrend=\(\s*'" + re.escape(GATE_SYMBOL) + r"'\s*,\s*" + str(GATE_N) + r"\s*\)"
)
_TIMING_SITE = re.compile(
    r"signal='" + re.escape(GATE_SYMBOL) + r"'\s*,\s*rule='" + re.escape(GATE_RULE)
    + r"'\s*,\s*n=" + str(GATE_N) + r"\b"
)

#: ``top=<n>`` in a rendered params tree. The book size is read from the SHALLOWEST bracket depth
#: that carries one, because a screen's own ``top`` (``FactorParams(top=1000)``) is always nested
#: inside the allocator's.
_TOP = re.compile(r"\btop=(\d+)\b")


# --------------------------------------------------------------------------- small helpers


def pts(v: float | None, digits: int = 2) -> str:
    """A points-a-year figure with an ASCII sign: ``-8.24``, ``+0.65``; the dash for None.

    ``metrics.fmt_signed_pct`` renders the web's U+2212 minus, which is right on a page and wrong
    in a line the owner may paste into a note or a commit message. Two decimals because the whole
    argument of this report is about tenths of a point.
    """
    if v is None:
        return DASH
    return ("+" if v >= 0 else "-") + to_fixed(abs(v * 100.0), digits)


def curve_of(row: sqlite3.Row) -> list[tuple[date, float]]:
    """One recorded trial's monthly equity curve, as ``walkforward.measure`` wants it."""
    return [(date.fromisoformat(d), float(v)) for d, v in json.loads(row["curve_json"])]


def trial_window(row: sqlite3.Row) -> tuple[date, date]:
    """The dates the trial ran between, from its own recorded columns."""
    return date.fromisoformat(row["start"]), date.fromisoformat(row["end"])


def month_offset(window_start: date, when: date) -> int:
    """Whole months from the window's first month to ``when``'s, never negative.

    The fee model walks the owner's funding plan by month offset, and the dev window's first month
    is month 0 of that plan: ``turnover.equity_usd(0)`` is the opening 10,000,000 IDR.
    """
    months = (when.year - window_start.year) * 12 + (when.month - window_start.month)
    return max(0, months)


# --------------------------------------------------------------------------- reading the lab


def resolve_trial(conn: sqlite3.Connection, token: object) -> sqlite3.Row:
    """The dev trial ``token`` names: a ``trials.n``, or a candidate id. Raises ``LabError``.

    A ``window = 'test'`` row is refused by name rather than quietly reported on. This command
    reads recorded rows, so reading one would spend no new look -- but the lab's rule is that
    nothing in a report path may so much as name the test window, and a refusal here is cheaper
    than a reader who learns that it can.
    """
    text = str(token).strip()
    if not text:
        raise store.LabError("name a trial: its number (`lab shortfall 828`) or its candidate id")
    if text.isdigit():
        row = conn.execute("SELECT * FROM trials WHERE n = ?", (int(text),)).fetchone()
        if row is None:
            raise store.LabError(f"no trial #{text} in this lab")
    else:
        cid = text.upper()
        rows = conn.execute(
            "SELECT * FROM trials WHERE candidate_id = ? ORDER BY n", (cid,)
        ).fetchall()
        if not rows:
            raise store.LabError(
                f"no trial for candidate {cid}; `lab show <method>` lists a method's variants"
            )
        dev = [r for r in rows if r["window"] == "dev"]
        if not dev:
            raise store.LabError(
                f"{cid} has only a test-window trial; `lab shortfall` reads the dev window "
                f"and nothing else"
            )
        row = dev[0]
    if row["window"] != "dev":
        raise store.LabError(
            f"trial #{row['n']} ({row['candidate_id']}) is a {row['window']}-window trial. "
            f"`lab shortfall` reads the dev window and nothing else: the one counted look is "
            f"never spent on a report, and never re-read by one"
        )
    if not row["curve_json"] or not json.loads(row["curve_json"]):
        raise store.LabError(
            f"trial #{row['n']} ({row['candidate_id']}) records no equity curve, so no era can "
            f"be sliced out of it"
        )
    return row


def benchmark(conn: sqlite3.Connection) -> tuple[list[tuple[date, float]], int]:
    """The recorded ``REF-SPY-HOLD`` dev curve and its ``trials.n``. Raises ``LabError``.

    The same row by the same rule as ``hardgate.benchmark_n`` -- the first ``REF-SPY-HOLD`` dev
    trial carrying a curve -- so this report and the promotion gate can never be talking about
    two different benchmarks. A test asserts the two agree.
    """
    row = conn.execute(
        'SELECT n, start, "end", curve_json FROM trials '
        "WHERE window = 'dev' AND candidate_id = ? AND curve_json IS NOT NULL ORDER BY n LIMIT 1",
        (regime.BENCH_CANDIDATE,),
    ).fetchone()
    if row is None:
        raise store.LabError(
            f"no {regime.BENCH_CANDIDATE} dev trial, so there is no gap to decompose. This is "
            f"the lab's fixture missing, not your trial failing"
        )
    curve = curve_of(row)
    if len(curve) < 2:
        raise store.LabError(
            f"the recorded {regime.BENCH_CANDIDATE} dev curve has {len(curve)} point(s); no era "
            f"can be sliced from it"
        )
    return curve, int(row["n"])


def era_bounds(label: object, window: tuple[date, date]) -> tuple[str, date, date]:
    """``(canonical label, start, end)`` for ``label``, clipped to the trial's own window.

    The era table is ``exposure.ERAS`` and is imported, never restated: ``lab exposure``,
    ``lab gate`` and ``lab survivorship`` all cut the same four eras, and a fifth definition here
    would make two reports of the same trial disagree about what "2009-2015" means. ``whole`` (or
    ``whole window``) is the trial's own window.
    """
    text = str(label).strip().lower()
    if text in ("whole", WHOLE):
        return WHOLE, window[0], window[1]
    for name, start, end in ERAS:
        if text == name.lower():
            lo, hi = max(start, window[0]), min(end, window[1])
            if lo >= hi:
                raise store.LabError(
                    f"era {name} ({start}..{end}) does not overlap this trial's window "
                    f"({window[0]}..{window[1]})"
                )
            return name, lo, hi
    known = ", ".join(ERA_LABELS)
    raise store.LabError(
        f"unknown era {label!r}; this lab knows {known} (say 'whole' for the whole window). The "
        f"era table is lab/exposure.py's ERAS and is not redefined here"
    )


def carries_shared_gate(config_text: object) -> bool:
    """Does this recorded configuration carry the shared SPY 200-day gate, anywhere in it?

    Generic, from the recorded text rather than from the candidate's name: a recorded row holds no
    params object, so ``gate_probe.gate_off``'s walk cannot be run on it, but ``config_text`` is
    exactly ``registry._canon``'s rendering of the same ``compare=True`` fields that walk visits.
    Both of the gate's two forms are matched -- a ``trend`` pair and the ``TimingParams`` that is
    the gate -- using ``gate_probe``'s own constants.

    True means *the gate is present somewhere in this book*, which is not the same as *the gate
    governs all of this book*: a blend with one gated leg answers True. :func:`era_exposure` makes
    that distinction separately, from the recorded exposure against the gate's own on-share.
    """
    text = str(config_text or "")
    return bool(_TREND_SITE.search(text) or _TIMING_SITE.search(text))


def names_in(config_text: object) -> int | None:
    """The book's name count read from a recorded configuration, or None when it is ambiguous.

    The shallowest bracket depth that carries a ``top=`` wins, because an allocator's own book
    size sits outside the screen it wraps: ``GestureParams(top=30, screen=FactorParams(top=1000))``
    reads 30. None when the params name no ``top`` at all, or when two different ones sit at that
    same shallowest depth.

    **Measured across the committed lab (824 dev rows, 2026-10-19): 686 resolve and 138 do not,
    and at least two that resolve are wrong** -- ``M0241-STALE`` reads 1000 and ``M0226-CORE``
    reads 1000, because those allocators carry no book size of their own. So this is a suggestion
    the report labels as a guess and never a fact: the caller can override it, the output always
    says where the number came from, and the fee drag is printed with a sensitivity band across
    :data:`SENSITIVITY_NAMES` so a wrong guess is visibly bounded. Measured, the 2009-2015 drag
    moves by 0.14 pts/yr across 10 to 50 names, so it is bounded very tightly indeed.
    """
    text = str(config_text or "")
    line = next((ln for ln in text.splitlines() if ln.startswith("params=")), None)
    if line is None:
        return None
    found: dict[int, set[int]] = {}
    depth, i = 0, 0
    while i < len(line):
        ch = line[i]
        if ch in "([":
            depth += 1
            i += 1
            continue
        if ch in ")]":
            depth -= 1
            i += 1
            continue
        m = _TOP.match(line, i)
        if m is not None:
            found.setdefault(depth, set()).add(int(m.group(1)))
            i = m.end()
            continue
        i += 1
    if not found:
        return None
    shallowest = found[min(found)]
    return next(iter(shallowest)) if len(shallowest) == 1 else None


# --------------------------------------------------------------------------- the gate's shape


@dataclass(frozen=True, slots=True)
class GateShare:
    """How often the shared gate was on, over the whole window and over one era."""

    symbol: str
    n: int
    whole: float
    era: float
    whole_sessions: int
    era_sessions: int
    store_dir: str


def gate_history(store_dir: Path, symbol: str = GATE_SYMBOL) -> History:
    """``symbol``'s bars, streamed out of a research store's own ``bars.csv``.

    ``research.load_store`` would answer the same question and costs roughly a gigabyte of memory
    and half a minute, because it builds the whole market. This report needs one symbol's closes,
    so it reads the one file and keeps the one symbol. The store is still checked -- see
    :func:`gate_on_share` -- through ``research.declared_window`` and ``research.declared_purpose``,
    which read the manifest and nothing else.
    """
    path = Path(store_dir) / research.BARS_FILE
    if not path.is_file():
        raise store.LabError(
            f"{store_dir}: no {research.BARS_FILE}. The research stores are gitignored, so a "
            f"worktree has none -- point --store at a checkout that does rather than rebuilding "
            f"one"
        )
    days: list[np.datetime64] = []
    cols: tuple[list[float], ...] = ([], [], [], [], [])
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if header is None or ",".join(header) != research.BARS_HEADER:
            raise store.LabError(
                f"{path}: header is {header!r}, expected {research.BARS_HEADER!r}"
            )
        for rec in reader:
            if not rec or rec[0] != symbol:
                continue
            days.append(np.datetime64(rec[1]))
            for k in range(5):
                cols[k].append(float(rec[2 + k]))
    if len(days) < GATE_N:
        raise store.LabError(
            f"{path}: {symbol} has {len(days)} bar(s), fewer than the {GATE_N} the gate needs "
            f"before it can be read at all"
        )
    arrays = [np.array(c, dtype=np.float64) for c in cols]
    return History(symbol, np.array(days, dtype="datetime64[D]"), *arrays)


def gate_shares(
    history: History,
    window: tuple[date, date],
    era: tuple[date, date],
    store_dir: str = "",
) -> GateShare:
    """The share of sessions the shared gate was on, over ``window`` and over ``era``.

    The gate is read by :func:`f_factor.trend_on`, the lab's own definition of it -- strictly
    ``close > SMA(n)``, with the first ``n-1`` bars counting as off -- rather than by a rolling
    mean written out again here. A second definition of the gate is how two reports of the same
    book end up disagreeing about when it was in the market.

    Pure: no I/O. :func:`gate_on_share` is the one that opens a store.
    """
    params = FactorParams(rank="momentum", trend=(history.symbol, GATE_N))
    hist = {history.symbol: history}
    days = [d.astype(object) for d in history.dates]
    on = np.array([trend_on(hist, d, params) for d in days], dtype=bool)

    def share(lo: date, hi: date) -> tuple[float, int]:
        idx = [i for i, d in enumerate(days) if lo <= d <= hi]
        if not idx:
            raise store.LabError(
                f"{history.symbol} has no bar between {lo} and {hi}, so the gate's share of that "
                f"span cannot be measured"
            )
        return float(on[idx].mean()), len(idx)

    whole, whole_n = share(*window)
    era_share, era_n = share(*era)
    return GateShare(
        symbol=history.symbol,
        n=GATE_N,
        whole=whole,
        era=era_share,
        whole_sessions=whole_n,
        era_sessions=era_n,
        store_dir=str(store_dir),
    )


def gate_on_share(
    store_dir: Path, window: tuple[date, date], era: tuple[date, date]
) -> GateShare:
    """:func:`gate_shares` over the gate symbol's bars in the store at ``store_dir``.

    The store is refused unless it declares the dev window and no special purpose. The era shape
    has to be measured on the prices the trial was recorded against (hardgate D10's reasoning),
    and a survivorship-check or test-window store is a different tape.
    """
    path = Path(store_dir)
    try:
        declared = research.declared_window(path)
        purpose = research.declared_purpose(path)
    except (ValueError, FileNotFoundError) as e:
        raise store.LabError(f"{path}: {e}") from e
    if declared.name != research.DEV_WINDOW.name:
        raise store.LabError(
            f"{path} declares the {declared.name!r} window; `lab shortfall` measures the gate's "
            f"era shape on the dev window and nothing else, and never opens the test window"
        )
    if purpose is not None:
        raise store.LabError(
            f"{path} declares purpose {purpose!r}; the gate's era shape must come from the same "
            f"prices the trial was recorded on, not from another tape"
        )
    return gate_shares(gate_history(path), window, era, store_dir=str(path))


# --------------------------------------------------------------------------- the three terms


@dataclass(frozen=True, slots=True)
class Exposure:
    """The exposure the gate premium is priced at, and why it is that one."""

    value: float
    recorded: float
    basis: str  # ERA_BASIS or WHOLE_BASIS
    why: str
    fill: float | None  # recorded / the gate's whole-window on-share, when it was computed


def era_exposure(
    recorded: float,
    gate: GateShare | None,
    carries_gate: bool,
    store_given: bool,
) -> Exposure:
    """The era's exposure, era-resolved when it can be and the recorded figure when it cannot.

    Four ways it cannot be, each with its own sentence in the output: no store was given, the book
    carries no shared gate, the gate was never on over the window, or the book held money while
    the gate was off -- the recorded exposure above the gate's own on-share -- which means the gate
    does not govern all of it and the ratio would be a different book's arithmetic.
    """
    if not store_given:
        return Exposure(
            recorded, recorded, WHOLE_BASIS,
            "no --store was given, so the gate's era shape could not be measured and the "
            "recorded whole-window exposure is used as it stands",
            None,
        )
    if gate is None or not carries_gate:
        return Exposure(
            recorded, recorded, WHOLE_BASIS,
            f"this book carries no shared {GATE_SYMBOL} {GATE_N}-day gate, so there is no gate "
            f"shape to resolve per era and the recorded whole-window exposure stands",
            None,
        )
    if gate.whole <= 0.0:
        return Exposure(
            recorded, recorded, WHOLE_BASIS,
            f"the {GATE_SYMBOL} {GATE_N}-day gate was never on over this trial's window, so its "
            f"era shape cannot be scaled and the recorded whole-window exposure stands",
            None,
        )
    fill = recorded / gate.whole
    if fill > MAX_GATE_FILL:
        return Exposure(
            recorded, recorded, WHOLE_BASIS,
            f"the recorded exposure {recorded:.3f} is above the gate's own whole-window on-share "
            f"{gate.whole:.3f}, so this book held money while the gate was off and the gate does "
            f"not govern all of it; the recorded whole-window exposure stands",
            fill,
        )
    value = min(1.0, fill * gate.era)
    return Exposure(
        value, recorded, ERA_BASIS,
        f"the gate was on {gate.era * 100:.1f}% of this era's sessions against "
        f"{gate.whole * 100:.1f}% of the whole window's, and the book was about "
        f"{fill * 100:.1f}% invested whenever the gate let it in",
        fill,
    )


def round_trip_rate(month: int, names: int) -> Decimal:
    """Gotrade's cost of one round trip, as a share of the two dollars of notional it moves.

    ``book_runner._turnover`` sums buy **and** sell notionals, so one unit of recorded turnover is
    one dollar of notional, and the rate that composes with it divides the round trip's fees by
    ``2 x slot`` rather than by the slot. The slot is the owner's funded equity at ``month``
    months of his real plan, split ``names`` ways. Every fee comes from
    :func:`turnover.round_trip`, which calls ``sim.costs.fee_parts``; none is re-derived here.
    """
    slot = turnover.slot_usd(turnover.equity_usd(month), names)
    buy, sell = turnover.round_trip(slot)
    return ((buy.total + sell.total) / (2 * slot)).quantize(RATE_Q)


def mean_round_trip_rate(first_month: int, last_month: int, names: int) -> Decimal:
    """:func:`round_trip_rate` averaged over every month of an era, inclusive.

    An average rather than one month's figure because the ``$0.10`` per-order floor's bite shrinks
    as the owner's deposits arrive: the rate is 0.7226% in month 0 and 0.2498% in month 236, and a
    single endpoint would be wrong in one direction or the other. Measured over months 156..237 --
    2009-2015 of the dev window -- it is 0.251041%.
    """
    if last_month < first_month:
        raise ValueError(f"last_month {last_month} is before first_month {first_month}")
    rates = [round_trip_rate(m, names) for m in range(first_month, last_month + 1)]
    return (sum(rates) / len(rates)).quantize(RATE_Q)


@dataclass(frozen=True, slots=True)
class Fees:
    """The modelled fee drag, and everything a reader needs to argue with it."""

    names: int
    names_from: str
    first_month: int
    last_month: int
    rate: Decimal
    drag: float  # a fraction of equity a year, positive
    sensitivity: tuple[tuple[int, float], ...]


def fee_model(
    turnover_per_year: float,
    window_start: date,
    era: tuple[date, date],
    names: int,
    names_from: str,
) -> Fees:
    """``turnover x the era's mean round-trip rate``, with its own sensitivity band.

    Modelled, never recovered: the fees a run really paid are ``RunStats.costs_usd`` and are not a
    ``trials`` column. The band across :data:`SENSITIVITY_NAMES` is printed beside the answer so a
    guessed book size is visibly bounded rather than quietly load-bearing.
    """
    first = month_offset(window_start, era[0])
    last = month_offset(window_start, era[1])
    rate = mean_round_trip_rate(first, last, names)
    band = tuple(
        (n, turnover_per_year * float(mean_round_trip_rate(first, last, n)))
        for n in SENSITIVITY_NAMES
    )
    return Fees(
        names=int(names),
        names_from=names_from,
        first_month=first,
        last_month=last,
        rate=rate,
        drag=turnover_per_year * float(rate),
        sensitivity=band,
    )


# --------------------------------------------------------------------------- the whole report


@dataclass(frozen=True, slots=True)
class Split:
    """The residual split against a sibling arm that shares the pool, the gate and the frame."""

    candidate_id: str
    trial_n: int
    shared: float  # pool and frame: what the sibling's own residual also carries
    own: float  # this arm's own weighting and selection: the remainder


@dataclass(frozen=True, slots=True)
class Shortfall:
    """One trial's era gap, and where it went. ``gap == -gate_premium - fees.drag + residual``."""

    trial_n: int
    candidate_id: str
    method_id: str
    window: tuple[date, date]
    era_label: str
    era: tuple[date, date]
    months: int
    deposits: int
    mine: float
    theirs: float
    gap: float
    exposure: Exposure
    gate: GateShare | None
    gate_premium: float  # positive: what the gate cost
    fees: Fees
    residual: float  # signed, and never named after a cause
    against: Split | None
    warnings: tuple[str, ...]


def check_against(conn: sqlite3.Connection, row: sqlite3.Row, other: sqlite3.Row) -> None:
    """Refuse an ``--against`` arm the split would be meaningless across. Raises ``LabError``.

    The split only says anything when the two arms share a pool, a gate and a frame, and the only
    evidence of that this module has is that they are two arms of one method. Across methods, or
    across two price fingerprints the benchmark does not share, the subtraction is a number nobody
    can trust -- so it is refused rather than printed with a caveat. That is the one place this
    report refuses rather than warns, and it is deliberate: a warning on the main row still leaves
    a reader a measured number, where a bad split leaves them a fabricated one.
    """
    if int(other["n"]) == int(row["n"]):
        raise store.LabError(
            f"--against {other['candidate_id']} is the trial itself; an arm cannot be its own "
            f"control"
        )
    if str(other["method_id"]) != str(row["method_id"]):
        raise store.LabError(
            f"--against {other['candidate_id']} belongs to {other['method_id']} and "
            f"{row['candidate_id']} belongs to {row['method_id']}. The split attributes what two "
            f"arms have in common to their shared pool and frame, and two different methods share "
            f"neither; this will not print a number nobody can trust"
        )
    bench_n = hardgate.benchmark_n(conn)
    if bench_n is None:
        raise store.LabError(
            f"no {regime.BENCH_CANDIDATE} dev trial, so neither arm can be compared with anything"
        )
    problems = hardgate.mismatches(conn, bench_n, [row, other])
    if problems:
        raise store.LabError(
            f"{row['candidate_id']} and {other['candidate_id']} cannot be compared with "
            f"{regime.BENCH_CANDIDATE}: {hardgate.describe(problems)}. That is the promotion "
            f"gate's own rule (lab/hardgate.py, D10), and a residual split across two price "
            f"fingerprints is cross-store arithmetic"
        )


def measure(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    era_label: object = DEFAULT_ERA,
    *,
    gate: GateShare | None = None,
    names: int | None = None,
    against: sqlite3.Row | None = None,
    store_given: bool = False,
) -> Shortfall:
    """One trial's era gap and its decomposition. Reads the lab; writes nothing; no store.

    ``gate`` is :func:`gate_on_share`'s answer when the caller opened a store, and None otherwise;
    ``store_given`` distinguishes "no store" from "a store, but this book has no shared gate", so
    the output can say which. The residual is computed last, as ``gap + gate premium + fee drag``,
    which makes the three terms sum back to the gap by construction rather than by luck.
    """
    bench, bench_n = benchmark(conn)
    window = trial_window(row)
    label, lo, hi = era_bounds(era_label, window)
    curve = curve_of(row)
    deposits = hardgate.trial_deposits(conn, row, curve)
    mine = wf.measure(curve, lo, hi, deposits)
    theirs = wf.measure(bench, lo, hi)
    if mine is None or mine.cagr is None:
        raise store.LabError(
            f"trial #{row['n']} ({row['candidate_id']}) has too little curve between {lo} and "
            f"{hi} to measure a return over"
        )
    if theirs is None or theirs.cagr is None:
        raise store.LabError(
            f"the recorded {regime.BENCH_CANDIDATE} curve has too little between {lo} and {hi} "
            f"to measure a return over"
        )
    gap = mine.cagr - theirs.cagr

    carries = carries_shared_gate(row["config_text"])
    exposure = era_exposure(float(row["exposure"]), gate, carries, store_given)
    gate_premium = (1.0 - exposure.value) * theirs.cagr

    if names is not None:
        book, how = int(names), "given on the command line"
    else:
        guessed = names_in(row["config_text"])
        if guessed is None:
            book = DEFAULT_NAMES
            how = (
                f"the roster's {DEFAULT_NAMES}, because the recorded configuration names no book "
                f"size this report can read"
            )
        else:
            book = guessed
            how = "read from the recorded configuration's outermost `top=`, which is a guess"
    fees = fee_model(float(row["turnover"]), window[0], (lo, hi), book, how)

    residual = gap + gate_premium + fees.drag

    split: Split | None = None
    if against is not None:
        check_against(conn, row, against)
        peer = measure(
            conn, against, label, gate=gate, names=names, against=None, store_given=store_given
        )
        split = Split(
            candidate_id=str(against["candidate_id"]),
            trial_n=int(against["n"]),
            shared=peer.residual,
            own=residual - peer.residual,
        )

    warnings: list[str] = []
    problems = hardgate.mismatches(conn, bench_n, [row])
    if problems:
        warnings.append(
            f"WARNING {row['candidate_id']} is not comparable with {regime.BENCH_CANDIDATE}: "
            f"{hardgate.describe(problems)}. Every number below is cross-store arithmetic, and "
            f"`lab promote` refuses it (lab/hardgate.py, D10)"
        )

    return Shortfall(
        trial_n=int(row["n"]),
        candidate_id=str(row["candidate_id"]),
        method_id=str(row["method_id"]),
        window=window,
        era_label=label,
        era=(lo, hi),
        months=int(mine.months),
        deposits=len(deposits),
        mine=float(mine.cagr),
        theirs=float(theirs.cagr),
        gap=gap,
        exposure=exposure,
        gate=gate,
        gate_premium=gate_premium,
        fees=fees,
        residual=residual,
        against=split,
        warnings=tuple(warnings),
    )


# --------------------------------------------------------------------------- what it prints


def format_report(sf: Shortfall) -> str:
    """The whole report, in plain words. The owner reads lab output and is not a quant."""
    out: list[str] = []
    for line in sf.warnings:
        out.append(line)
    if sf.warnings:
        out.append("")

    out.append(
        f"Trial #{sf.trial_n}  {sf.candidate_id}  (method {sf.method_id}), dev window "
        f"{sf.window[0]} to {sf.window[1]}."
    )
    out.append(
        f"Era {sf.era_label}: {sf.era[0]} to {sf.era[1]}, {sf.months} months of the recorded "
        f"monthly curve."
    )
    if sf.deposits:
        out.append(
            f"The owner's {sf.deposits} deposits are removed from the curve before it is cut, so "
            f"a deposit is never read as a gain."
        )
    out.append("")
    out.append(f"  what this book earned a year                 {pts(sf.mine):>10}%")
    out.append(f"  what SPY total return earned a year          {pts(sf.theirs):>10}%")
    out.append(f"  gap to SPY TR                                {pts(sf.gap):>10} pts/yr")
    out.append("")
    out.append(
        "Where the gap went. Each line below is computed on its own -- one from the recorded "
        "exposure,"
    )
    out.append(
        "one from the recorded turnover and the fee schedule -- and the residual is whatever "
        "those two"
    )
    out.append("do not explain. It is a residual and is never named after a cause.")
    out.append("")
    out.append(
        f"  gate premium    (1 - {sf.exposure.value:.3f}) x {sf.theirs * 100:.2f}%"
        f"{pts(-sf.gate_premium):>13} pts/yr"
    )
    out.append(
        f"  fee drag        {sf.fees.drag / float(sf.fees.rate):.2f} turns x "
        f"{float(sf.fees.rate) * 100:.4f}%{pts(-sf.fees.drag):>12} pts/yr"
    )
    if sf.against is None:
        out.append(f"  pool + weighting residual                  {pts(sf.residual):>10} pts/yr")
    else:
        out.append(
            f"  pool + frame (shared with {sf.against.candidate_id})"
            f"{pts(sf.against.shared):>10} pts/yr"
        )
        out.append(
            f"  this arm's own weighting and selection     {pts(sf.against.own):>11} pts/yr"
        )
    out.append("  " + "-" * 58)
    out.append(f"  these add back to the gap                  {pts(sf.gap):>10} pts/yr")
    out.append("")

    out.append(
        f"Exposure. The row records {sf.exposure.recorded:.3f} for the whole window, and this "
        f"report prices the"
    )
    out.append(f"gate at {sf.exposure.value:.3f} for this era -- {sf.exposure.basis}, because")
    out.append(f"{sf.exposure.why}.")
    if sf.exposure.basis == ERA_BASIS:
        flat = (1.0 - sf.exposure.recorded) * sf.theirs
        out.append(
            f"Using the whole-window {sf.exposure.recorded:.3f} instead would price the gate at "
            f"{pts(-flat)} pts/yr"
        )
        out.append(
            f"and leave a residual of {pts(sf.gap + flat + sf.fees.drag)} -- which is why this "
            f"distinction is made at all."
        )
    out.append("")

    band = ", ".join(f"{n}: {pts(-d)}" for n, d in sf.fees.sensitivity)
    out.append(
        "Fees. Modelled, not recovered: what the run really paid is not a column in the trials"
    )
    out.append(
        f"table. The model takes {sf.fees.names} names ({sf.fees.names_from}), the owner's real "
        f"funding plan at"
    )
    out.append(
        f"months {sf.fees.first_month} to {sf.fees.last_month} of the dev window, and prices one "
        f"round trip of one slot through"
    )
    out.append(
        f"Gotrade's schedule. At {', '.join(str(n) for n in SENSITIVITY_NAMES)} names the drag "
        f"would be {band} pts/yr,"
    )
    out.append("so the book size is not what this answer rests on.")
    out.append("")

    out.append("Cash. The gate premium assumes money out of the market earned nothing. For")
    out.append(f"{sf.era_label}, {CASH_NOTE.get(sf.era_label, 'this caveat is not recorded')}.")
    out.append("")

    out.append(
        "Read this as an attribution under stated assumptions, not an identity. The two named "
        "terms"
    )
    out.append(
        "are worked out independently and the residual absorbs the error of both, so a small "
        "residual"
    )
    out.append(
        "means the two named causes account for the gap -- not that the residual's own "
        "ingredients are"
    )
    out.append("zero.")
    return "\n".join(out)


def csv_rows(sf: Shortfall) -> list[list[str]]:
    """The report's terms at full precision, for ``--csv``."""
    head = ["trial", "candidate", "method", "era", "term", "value_per_year", "how"]
    rows = [
        head,
        [str(sf.trial_n), sf.candidate_id, sf.method_id, sf.era_label, "book_cagr",
         repr(sf.mine), f"{sf.months} months, de-funded"],
        [str(sf.trial_n), sf.candidate_id, sf.method_id, sf.era_label, "spy_tr_cagr",
         repr(sf.theirs), f"{regime.BENCH_CANDIDATE}, same slice"],
        [str(sf.trial_n), sf.candidate_id, sf.method_id, sf.era_label, "gap",
         repr(sf.gap), "book minus SPY TR"],
        [str(sf.trial_n), sf.candidate_id, sf.method_id, sf.era_label, "gate_premium",
         repr(-sf.gate_premium),
         f"(1 - {sf.exposure.value!r}) x spy, exposure {sf.exposure.basis}"],
        [str(sf.trial_n), sf.candidate_id, sf.method_id, sf.era_label, "fee_drag",
         repr(-sf.fees.drag),
         f"turnover x {sf.fees.rate}, {sf.fees.names} names ({sf.fees.names_from})"],
    ]
    if sf.against is None:
        rows.append([str(sf.trial_n), sf.candidate_id, sf.method_id, sf.era_label,
                     "pool_weighting_residual", repr(sf.residual), "the term the two above "
                     "do not explain"])
    else:
        rows.append([str(sf.trial_n), sf.candidate_id, sf.method_id, sf.era_label,
                     "pool_frame_shared", repr(sf.against.shared),
                     f"also carried by {sf.against.candidate_id} (trial #{sf.against.trial_n})"])
        rows.append([str(sf.trial_n), sf.candidate_id, sf.method_id, sf.era_label,
                     "own_weighting_selection", repr(sf.against.own),
                     f"the remainder over {sf.against.candidate_id}"])
    return rows


def write_csv(sf: Shortfall, path: Path) -> Path:
    """Write :func:`csv_rows` to ``path``. The one file this module touches."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(csv_rows(sf))
    return path
