"""``lab names``: how many names a monthly momentum book should hold, measured. Report only.

The roster's RAW-FR entry trades lab ``M0007-N20-RAW`` -- the residual-momentum book ranked on
the raw cumulative residual, with no volatility brake -- and its ``20`` is a *parameter*
(``ResidParams.inner.top``), so other name counts cost nothing to express. This module runs that
one variant at several name counts over the lab's dev window and prints the grid.

**The fee argument is not the question, and must not be re-run as the finding.** An earlier
reading of Gotrade's $0.10 per-order floor said the floor stops binding near $50 an order, so an
account this size should hold about eleven names. Under the owner's funding plan that is a
two-month transient: measured at 17,841 IDR/USD, a twenty-name book pays 1.035% of each order in
month 0 and 0.614% by month 3, against 0.628% and 0.612% for an eleven-name book -- two
thousandths of one percent apart. Handover section 2b is marked CORRECTED on exactly this point,
and the owner's standing instruction is *"do not plan a name-count reduction on fee grounds; if
the lab tests concentration, test it on the merits."* So the question here is what concentration
does to the RETURNS.

**Both axes are on, because they interact.** The sweep runs at ``cost_model="gotrade"`` -- the fee
floor is size-dependent, so a sweep at the lab's old flat 0.1% would measure a world where name
count is nearly free -- and on the owner's real contribution schedule (10,000,000 IDR at the
start, +5,000,000 IDR on the 25th of every month), scored with the money-weighted return and
against the dollar-cost-averaged SPY, because a book that is fed money has no meaningful CAGR and
no meaningful "beats SPY TR". Two controls make each axis legible: ``--gotrade-only`` drops the
flat side, ``--lump`` drops the schedule.

**A report, not a trial.** Nothing here writes a ``trials`` row, a ``trial_moments`` row, an
``insights`` row or a status, so ``store.dev_trial_count`` (the lab's N) and ``store.test_looks``
are exactly what they were, and nothing this prints can make any configuration eligible. That is
also its limit: six free looks at six name counts is the kind of search the luck gate exists to
charge for, so this grid may *inform* a decision and may never *be* one. The only way another
name count is ever judged is a new method that pre-registers it -- which, from M0031 on,
``real_costs.real_cost_problem`` already forces to run at Gotrade's real fees -- and that method
pays its trials like any other. The rebuilt roster carries 20 regardless (GOTRADE_FEE_REBUILD_PLAN
Decision D3).

**M0007's file is not touched.** Its ``source_sha`` is frozen and its recorded config digests are
pinned, so ``RESIDMOM``, ``ResidParams`` and ``TREND`` are imported and the swept variants exist
only in memory for the length of one run -- the same thing ``paper.roster`` does with that file.
"""

from __future__ import annotations

import csv
import inspect
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.dev import Candidate, DevRow
from seer_engine.backtest.metrics import fmt_num, fmt_pct, fmt_pf, fmt_signed_pct
from seer_engine.lab import store
from seer_engine.lab.methods.m0007_residual_momentum import RESIDMOM, TREND, ResidParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC, MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.f_factor import FactorParams

# --------------------------------------------------------------------------- what is swept

#: The name counts, bracketing the roster's 20 on both sides and covering the eleven-name region
#: the (now settled) fee argument pointed at.
NS: tuple[int, ...] = (5, 10, 15, 20, 25, 30)

#: What the paper roster holds today, and what it keeps holding whatever this measures (D3).
ROSTER_NAMES = 20

#: The recorded variant whose ``top`` is being swept; ``paper.roster`` trades its params.
BASE_VARIANT = "M0007-N20-RAW"

FLAT = "flat"
REAL = "gotrade"
MODELS: tuple[str, ...] = (REAL, FLAT)

#: One rule set per cost model, identical but for ``cost_model``: fractional monthly-hold, which
#: is what Gotrade does and what the paper roster trades.
RULES: dict[str, Any] = {REAL: MONTHLY_HOLD_FRAC_GOTRADE, FLAT: MONTHLY_HOLD_FRAC}
SUFFIX: dict[str, str] = {REAL: "GT", FLAT: "FLAT"}

ADDED = date(2026, 10, 8)
MIN_NAMES, MAX_NAMES = 2, 60

# --------------------------------------------------------------------------- borrowed names
# The three identifiers this module takes from phases 5 and 7, each in one place so that a
# rename elsewhere is a one-line change here rather than a hunt.

#: Phase 5's ready-made schedule in ``seer_engine.sim.contributions``. Read off ``phase-5.md``
#: by the reconciler (2026-10-08): the draft of this module guessed ``OWNER_SCHEDULE``.
SCHEDULE_NAME = "OWNER_MONTHLY"

#: Phase 7's keyword on ``dev.run_registry`` that carries the schedule into the book and SPY.
SCHEDULE_KEYWORD = "contributions"

#: Phase 7's money-weighted return. Read off ``phase-7.md`` by the reconciler: it is the field
#: ``backtest.metrics.Metrics.mwr`` (the draft of this module guessed ``money_weighted_return``,
#: which is the name of the FUNCTION that computes it, not of the field that carries it). It is
#: ``None`` on a run with no deposits, by phase 7's Decision D7b -- so on the ``--lump`` control
#: the column correctly prints a dash. Soft: an absent name also prints a dash.
MWR_FIELD = "mwr"

LUMP = "lump"
FED = "contributions"


def check_names(ns: str | Iterable[int] | None = None) -> tuple[int, ...]:
    """The swept counts as a sorted, unique tuple. Accepts ``"5,10,20"`` or an iterable of ints."""
    if ns is None:
        return NS
    if isinstance(ns, str):
        parts = [p.strip() for p in ns.split(",") if p.strip()]
        if not parts:
            raise store.LabError("--ns is empty; give counts like 5,10,15,20,25,30")
        try:
            values = [int(p) for p in parts]
        except ValueError as e:
            raise store.LabError(f"--ns must be whole numbers separated by commas, got {ns!r}") from e
    else:
        values = [int(n) for n in ns]
    out = tuple(sorted(set(values)))
    if not out:
        raise store.LabError("no name counts to sweep")
    for n in out:
        if not MIN_NAMES <= n <= MAX_NAMES:
            raise store.LabError(
                f"a name count of {n} is outside {MIN_NAMES}..{MAX_NAMES}; this sweeps a book, "
                f"not a single stock or the whole index"
            )
    return out


def owner_schedule() -> Any:
    """Phase 5's contribution schedule: 10,000,000 IDR, then +5,000,000 IDR on the 25th monthly."""
    try:
        from seer_engine.sim import contributions
    except ImportError as e:  # pragma: no cover - only before phase 5 lands
        raise store.LabError(
            "seer_engine.sim.contributions does not exist. It is phase 5's new module -- the "
            "owner's funding as a pure value object -- and this sweep needs it, because the fee "
            "floor is size-dependent and a book that ramps from 10,000,000 IDR pays a different "
            "rate from one that starts full. Land phases 5 and 7, or run the lump-sum control "
            "with --lump (a control, not the answer)"
        ) from e
    schedule = getattr(contributions, SCHEDULE_NAME, None)
    if schedule is None:
        known = ", ".join(n for n in dir(contributions) if n.isupper()) or "(nothing public)"
        raise store.LabError(
            f"seer_engine.sim.contributions has no {SCHEDULE_NAME}; it holds {known}. This sweep "
            f"needs phase 5's ready-made schedule for the owner's real funding (10,000,000 IDR at "
            f"the start, +5,000,000 IDR on the 25th of every month). If phase 5 named it something "
            f"else, change SCHEDULE_NAME in lab/name_count.py -- it is one line"
        )
    return schedule


def check_schedule_support() -> None:
    """Refuse readably when ``dev.run_registry`` cannot be fed a schedule (phase 7's keyword)."""
    if SCHEDULE_KEYWORD not in inspect.signature(dev.run_registry).parameters:
        raise store.LabError(
            f"dev.run_registry takes no {SCHEDULE_KEYWORD!r} keyword, so this sweep cannot feed "
            f"the book the owner's contribution schedule, and cannot score it money-weighted "
            f"against a dollar-cost-averaged SPY. That keyword is phase 7's. Land phase 7, or run "
            f"the lump-sum control with --lump -- which measures a book that is never fed, and is "
            f"a control, not the answer"
        )


def variants(ns: Sequence[int], *, control: bool = True) -> tuple[Candidate, ...]:
    """One candidate per (cost model, name count): ``M0007-N<nn>-RAW-GT`` and ``-FLAT``.

    Everything but ``inner.top`` and ``rules.cost_model`` is ``M0007-N20-RAW``'s, read from the
    frozen method file. Nothing here is ever recorded, so these ids never reach the database.
    """
    models = MODELS if control else (REAL,)
    out: list[Candidate] = []
    for model in models:
        for n in ns:
            params = ResidParams(FactorParams(rank="momentum", top=int(n), trend=TREND), scaled=False)
            c = Candidate(
                id=f"M0007-N{int(n):02d}-RAW-{SUFFIX[model]}",
                family="M0007",
                rules=RULES[model],
                allocator=RESIDMOM,
                params=params,
                rationale=f"{BASE_VARIANT}'s book at {int(n)} names, {model} fees",
                added=ADDED,
                owner_inputs=(),
            )
            out.append(replace(c, owner_inputs=dev.candidate_owner_inputs(c)))
    return tuple(out)


# --------------------------------------------------------------------------- one measured point


@dataclass(frozen=True)
class Point:
    """One name count at one cost model: everything the grid and the CSV print."""

    model: str  # FLAT | REAL
    names: int
    candidate_id: str
    total_return: float | None
    cagr: float | None
    money_weighted: float | None
    max_drawdown: float | None
    profit_factor: float | None
    trades: int
    sharpe: float | None
    mar: float | None
    exposure: float
    turnover: float
    costs_usd: float
    cost_drag: float | None
    spy_tr_return: float | None
    spy_tr_cagr: float | None
    beats_spy: bool
    failed: tuple[str, ...]  # the go-live conditions it misses; the luck test is not run here


def money_weighted(row: DevRow) -> float | None:
    """Phase 7's money-weighted return, wherever it chose to publish it; None when absent.

    A book that is fed deposits has no honest CAGR -- the deposits raise ending equity without
    being a return -- so this is the number that means something once contributions are on. It is
    read by name, and softly, so this module runs either way.
    """
    for holder in (row.stats.metrics, row.stats, row):
        value = getattr(holder, MWR_FIELD, None)
        if value is not None:
            return float(value)
    return None


def point_of(model: str, names: int, row: DevRow) -> Point:
    m = row.stats.metrics
    return Point(
        model=model,
        names=int(names),
        candidate_id=row.candidate.id,
        total_return=m.total_return,
        cagr=m.cagr,
        money_weighted=money_weighted(row),
        max_drawdown=m.max_drawdown,
        profit_factor=m.profit_factor,
        trades=int(m.trades),
        sharpe=row.stats.sharpe,
        mar=row.mar,
        exposure=float(row.stats.exposure),
        turnover=float(row.stats.turnover),
        costs_usd=float(row.stats.costs_usd),
        cost_drag=row.stats.cost_drag,
        spy_tr_return=row.spy_tr.total_return,
        spy_tr_cagr=row.spy_tr.cagr,
        beats_spy=bool(row.beats_spy),
        failed=tuple(row.failed),
    )


# --------------------------------------------------------------------------- the whole grid


@dataclass(frozen=True)
class Sweep:
    """Every point, with enough provenance that the report can say what it measured."""

    base_variant: str
    names: tuple[int, ...]
    models: tuple[str, ...]
    funding: str  # FED | LUMP
    start: date
    end: date
    fingerprint: str
    points: tuple[Point, ...]

    def of(self, model: str) -> tuple[Point, ...]:
        """This cost model's points, in ascending name count."""
        return tuple(sorted((p for p in self.points if p.model == model), key=lambda p: p.names))

    def best(self, model: str) -> Point | None:
        """The highest MAR at this cost model; ties go to the smaller book. None with no MAR.

        MAR is the lab's own rank key -- ``lab costs`` picks its default variant by it and
        ``dev.finalists`` ranks by it -- so the sweep is read the way the lab reads everything
        else, rather than on a measure chosen after seeing the grid.
        """
        scored = [p for p in self.of(model) if p.mar is not None]
        if not scored:
            return None
        return sorted(scored, key=lambda p: (-(p.mar or 0.0), p.names))[0]

    def clean(self, model: str) -> tuple[Point, ...]:
        """The points that miss no go-live condition, in ascending name count."""
        return tuple(p for p in self.of(model) if not p.failed)

    def at(self, model: str, names: int) -> Point | None:
        for p in self.of(model):
            if p.names == names:
                return p
        return None

    @property
    def agrees(self) -> bool | None:
        """Do the two cost models choose the same name count? None when there is one model.

        True is the result that matters: it says the fee axis does not decide this, so the
        choice is a merits choice -- which is what handover section 2b asserts and what this
        sweep is here to measure rather than repeat.
        """
        if len(self.models) < 2:
            return None
        picks = [self.best(m) for m in self.models]
        if any(p is None for p in picks):
            return None
        return len({p.names for p in picks if p is not None}) == 1


def measure(
    data: research.ResearchData,
    *,
    ns: Sequence[int] | None = None,
    control: bool = True,
    lump: bool = False,
) -> Sweep:
    """Run the grid on the dev window. Writes nothing, anywhere.

    ``lump=True`` drops the contribution schedule and measures a book that is funded once and
    never fed. That is the control for the funding axis, not the answer: the owner adds money
    every month, and under Gotrade's floor a ramping book pays a different rate from a full one.
    """
    if data.window != research.DEV_WINDOW:
        w = data.window
        raise store.LabError(
            f"this research store was built for the {w.name!r} window ({w.start}..{w.end}); "
            f"`lab names` sweeps the dev window and nothing else, so a test-window store is "
            f"refused -- a name count has never been pre-registered and may not spend a look. "
            f"Build the dev store with `python -m seer_engine research_store`"
        )
    counts = check_names(ns)
    schedule = None
    if not lump:
        check_schedule_support()
        schedule = owner_schedule()
    registry = variants(counts, control=control)
    rows: dict[str, DevRow] = {}

    def on_result(i: int, result: Any, row: DevRow) -> None:
        rows[row.candidate.id] = row

    kwargs: dict[str, Any] = {"on_result": on_result}
    if schedule is not None:
        kwargs[SCHEDULE_KEYWORD] = schedule
    dev.run_registry(data.market, data.dividends, data.spy_dividends, registry, **kwargs)

    models = MODELS if control else (REAL,)
    points: list[Point] = []
    for model in models:
        for n in counts:
            cid = f"M0007-N{int(n):02d}-RAW-{SUFFIX[model]}"
            points.append(point_of(model, n, rows[cid]))
    any_row = rows[registry[0].id]
    return Sweep(
        base_variant=BASE_VARIANT,
        names=counts,
        models=tuple(models),
        funding=LUMP if lump else FED,
        start=any_row.start,
        end=any_row.end,
        fingerprint=str(data.fingerprint),
        points=tuple(points),
    )


# --------------------------------------------------------------------------- the report


MODEL_LABEL: dict[str, str] = {
    REAL: "Gotrade's real fees (cost_model='gotrade')",
    FLAT: "the lab's old flat 0.1% a trade -- the control, not the world",
}

FUNDING_LABEL: dict[str, str] = {
    FED: "the owner's real funding: 10,000,000 IDR at the start, +5,000,000 IDR on the 25th of "
         "every month, scored money-weighted against a SPY fed the same money",
    LUMP: "a LUMP SUM, never fed -- the control for the funding axis, not the owner's world",
}

_HEAD: tuple[str, ...] = (
    "names", "total", "a year", "money-wtd", "worst fall", "PF", "MAR",
    "trades", "fees", "fee drag", "beats SPY", "go-live misses",
)


def _usd(x: float) -> str:
    return f"${x:,.0f}"


def _cells(p: Point) -> tuple[str, ...]:
    return (
        str(p.names),
        fmt_signed_pct(p.total_return),
        fmt_signed_pct(p.cagr),
        fmt_signed_pct(p.money_weighted),  # the metrics formatters already render None as an em dash
        fmt_pct(p.max_drawdown),
        fmt_pf(p.profit_factor),
        fmt_num(p.mar),
        str(p.trades),
        _usd(p.costs_usd),
        fmt_pct(p.cost_drag),
        "yes" if p.beats_spy else "no",
        "; ".join(p.failed) or "none",
    )


def _table(rows: Sequence[tuple[str, ...]]) -> list[str]:
    body = [_HEAD, *rows]
    widths = [max(len(r[i]) for r in body) for i in range(len(_HEAD))]
    out: list[str] = []
    for k, row in enumerate(body):
        cells = [row[0].rjust(widths[0])]
        cells += [row[i].rjust(widths[i]) for i in range(1, len(_HEAD) - 1)]
        cells.append(row[-1].ljust(widths[-1]).rstrip())
        out.append("    " + "  ".join(cells))
        if k == 0:
            out.append("    " + "  ".join("-" * w for w in widths))
    return out


def _findings(sweep: Sweep) -> list[str]:
    """The mechanical readings. The prose a human reads is the write-up in docs/backtests/."""
    out = ["findings (mechanical; the write-up is docs/backtests/2026-10-08-how-many-names.md)"]
    for model in sweep.models:
        best = sweep.best(model)
        if best is None:
            out.append(f"  {model}: no MAR anywhere in the grid, so nothing ranks")
            continue
        clean = sweep.clean(model)
        out.append(
            f"  {model}: the highest MAR is {best.names} names ({fmt_num(best.mar)}); "
            f"{len(clean)} of {len(sweep.names)} counts miss no go-live condition"
            + (f" ({', '.join(str(p.names) for p in clean)})" if clean else "")
        )
    agrees = sweep.agrees
    if agrees is True:
        out.append(
            "  both cost models choose the same name count, so the fee axis does not decide this "
            "-- the choice is a merits choice, which is what the sweep was run to establish"
        )
    elif agrees is False:
        out.append(
            "  the two cost models choose DIFFERENT name counts: the fees do move this answer, "
            "which contradicts handover 2b and is the finding, not a footnote"
        )
    held = sweep.at(REAL, ROSTER_NAMES)
    if held is not None:
        out.append(f"  the roster holds {ROSTER_NAMES}; at Gotrade's fees that is:")
        for p in sweep.of(REAL):
            if p.names == ROSTER_NAMES:
                continue
            d_mar = None if p.mar is None or held.mar is None else p.mar - held.mar
            d_dd = (None if p.max_drawdown is None or held.max_drawdown is None
                    else p.max_drawdown - held.max_drawdown)
            out.append(
                f"    {p.names:>3} names: MAR {fmt_num(d_mar)} and worst fall "
                f"{fmt_signed_pct(d_dd)} against {ROSTER_NAMES}"
            )
    return out


def format_report(sweep: Sweep) -> str:
    """The terminal report. Ids and labels are fine here; the owner reads the docs page."""
    out = [
        f"lab names -- {sweep.base_variant}'s book at {len(sweep.names)} name counts "
        f"({', '.join(str(n) for n in sweep.names)}) on the dev window {sweep.start}..{sweep.end}, "
        f"research store {sweep.fingerprint[:12]}",
        f"funding: {FUNDING_LABEL[sweep.funding]}",
        "report only: no trial row, no moments, no journal entry, no status change; the lab's N "
        "and the test-window looks do not move. Six free looks at six name counts is the search "
        "the luck gate exists to charge for, so this grid informs a decision and is never one: "
        "acting on it means a new method that pre-registers the count and pays its trials.",
    ]
    for model in sweep.models:
        out += ["", f"  {MODEL_LABEL[model]}"]
        out += _table([_cells(p) for p in sweep.of(model)])
    out += [""] + _findings(sweep)
    return "\n".join(out)


# --------------------------------------------------------------------------- the grid as CSV


CSV_HEAD: tuple[str, ...] = (
    "cost_model", "names", "candidate_id", "total_return", "cagr", "money_weighted",
    "max_drawdown", "profit_factor", "trades", "sharpe", "mar", "exposure", "turnover",
    "costs_usd", "cost_drag", "spy_tr_return", "spy_tr_cagr", "beats_spy", "failed",
)


def _num(x: float | None) -> str:
    return "" if x is None else repr(float(x))


def csv_rows(sweep: Sweep) -> list[list[str]]:
    """The grid as text rows, header first: every number at full precision, nothing rounded."""
    rows: list[list[str]] = [list(CSV_HEAD)]
    for model in sweep.models:
        for p in sweep.of(model):
            rows.append([
                p.model, str(p.names), p.candidate_id, _num(p.total_return), _num(p.cagr),
                _num(p.money_weighted), _num(p.max_drawdown), _num(p.profit_factor),
                str(p.trades), _num(p.sharpe), _num(p.mar), _num(p.exposure), _num(p.turnover),
                _num(p.costs_usd), _num(p.cost_drag), _num(p.spy_tr_return), _num(p.spy_tr_cagr),
                "yes" if p.beats_spy else "no", "; ".join(p.failed),
            ])
    return rows


def write_csv(sweep: Sweep, path: Path) -> Path:
    """Write the grid to ``path`` (parents created). Returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(csv_rows(sweep))
    return path
