"""``lab survivorship M0069 [M0007 ...]``: recorded methods re-run on the survivorship-check store.

Every lab result so far was measured on ``engine/.research``, which prices about 59% of the
index-member days of 1996-2015, mostly the survivors: the companies that went bankrupt, were bought
or renamed are the ones yfinance could not serve. Phase 1 of the EODHD plan built a second
dev-window store, ``engine/.research-sv``, that adds most of them back from EODHD and is marked
``purpose: "survivorship-check"`` in its manifest. This module answers one question per method: how
much did the missing companies flatter the result the lab recorded?

**A report, not a trial.** For each named method, every variant with a recorded dev trial that is
still in the method file is re-run through ``dev.run_registry`` at the trial's recorded capital
(``runner.recorded_capital``) and funding (``runner.recorded_contributions``) -- once on the dev
store, then once on the survivorship-check store -- and the two are printed side by side. Nothing is
written but, unless ``--no-journal``, one ``observation`` per method: no ``trials``,
``trial_moments``, ``trial_funding`` or ``trial_provenance`` row, no status, no pre-registration. So
``store.dev_trial_count`` (the lab's N) and ``store.test_looks`` cannot move, and a survivorship-check
result can never be recorded as a dev trial of the original method -- mixing price fingerprints
inside one method's trial set is exactly what ``lab/hardgate.py`` exists to refuse.

**Refusals before any store loads.** Everything that needs no bars is checked first: the method ids,
their files, their recorded trials, capital and funding, the benchmark geometry, and both stores'
manifest ``purpose`` (the dev store must have none, the check store must read
``"survivorship-check"``). ``load_checked`` repeats the purpose check on the loaded
``ResearchData.purpose`` -- the authoritative one -- and ``research.load_store`` refuses a
test-window store on its own.

**Memory.** Each store is about 2.5M bar rows. ``measure_store`` loads one, runs every variant,
keeps only small ``Side`` records, and drops the store before returning, so the dev store is freed
before the survivorship-check store is loaded. The two are never alive together.
"""

from __future__ import annotations

import csv
import gc
import logging
import math
import sqlite3
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.dev import Candidate, DevRow
from seer_engine.backtest.metrics import DASH, fmt_num, fmt_pct, fmt_pf, fmt_signed_pct
from seer_engine.commands.backtest_dev import daily_moments, month_end_curve
from seer_engine.lab import hardgate, runner, store
from seer_engine.lab import walkforward as wf
from seer_engine.lab.method import METHOD_ID, Method, discover
from seer_engine.lab.real_costs import REPRO_TOL
from seer_engine.sim.contributions import ContributionSchedule

log = logging.getLogger(__name__)

SV_PURPOSE = research.SURVIVORSHIP_PURPOSE  # the manifest marker phase 1 writes on engine/.research-sv
DEV_LABEL = "dev"
SV_LABEL = "survivorship"
#: The era in which the dev store prices the most of the index -- ``commands/lab.py``'s
#: ``HIGH_COVERAGE``, repeated here because a ``lab`` module does not import a command module.
#: ``test_lab_survivorship`` pins the two equal.
HIGH_COVERAGE = (date(2009, 1, 1), date(2015, 10, 16))


# --------------------------------------------------------------------------- what to re-run


@dataclass(frozen=True)
class Variant:
    """One recorded dev variant, resolved against the database before any store loads."""

    candidate: Candidate
    trial_n: int
    trial: sqlite3.Row = field(compare=False, repr=False)
    capital: Decimal
    contributions: ContributionSchedule | None
    recorded_total_return: float | None
    recorded_dsr: float | None
    recorded_mar: float | None
    n_at_run: int | None
    var_trials: float | None  # trial_moments.var_trials; None when no moments row was recorded

    @property
    def funded(self) -> bool:
        return self.contributions is not None


@dataclass(frozen=True)
class MethodPlan:
    method: Method
    variants: tuple[Variant, ...]
    missing: tuple[str, ...]  # recorded candidate ids that are no longer in the method file


def resolve_method(method_id: str) -> Method:
    """The committed ``METHOD`` for a lab method id (``store.LabError`` otherwise)."""
    if not isinstance(method_id, str) or METHOD_ID.fullmatch(method_id) is None:
        raise store.LabError(
            f"{method_id!r} is not a lab method id; `lab survivorship` takes methods like M0069"
        )
    methods = discover()
    if method_id not in methods:
        raise store.LabError(
            f"no method file for {method_id} in seer_engine/lab/methods/. `lab survivorship` "
            f"re-runs the committed method file, not a database row"
        )
    return methods[method_id][0]


def _f(x: object) -> float | None:
    return None if x is None else float(x)


def plan_method(conn: sqlite3.Connection, method_id: str) -> MethodPlan:
    """Every recorded dev variant of ``method_id`` that is still in its method file.

    Resolves each variant's recorded capital, funding, N and ``var_trials`` now, so a trial that
    cannot be re-run as the measurement it was is refused before a store is opened. A funded
    trial's schedule is checked against its recorded deposit count here too
    (``hardgate.trial_deposits`` with an empty curve buckets nothing but still raises on a moved
    schedule).
    """
    method = resolve_method(method_id)
    trials = [t for t in store.trials_of(conn, method.id) if t["window"] == "dev"]
    if not trials:
        raise store.LabError(
            f"{method.id} has no dev trial; `lab survivorship` re-runs what the lab recorded. "
            f"Run it with `lab run {method.id}` first"
        )
    by_id = {c.id: c for c in method.candidates}
    seen: set[str] = set()
    variants: list[Variant] = []
    missing: list[str] = []
    for t in trials:  # trials_of orders by n: the first recording of a variant wins
        cid = str(t["candidate_id"])
        if cid in seen:
            continue
        seen.add(cid)
        candidate = by_id.get(cid)
        if candidate is None:
            missing.append(cid)
            continue
        n = int(t["n"])
        capital = runner.recorded_capital(conn, n)
        contributions = runner.recorded_contributions(conn, n)
        if contributions is not None:
            hardgate.trial_deposits(conn, t, [])
        moments = store.moments_of(conn, n)
        variants.append(
            Variant(
                candidate=candidate,
                trial_n=n,
                trial=t,
                capital=capital,
                contributions=contributions,
                recorded_total_return=_f(t["total_return"]),
                recorded_dsr=_f(t["dsr"]),
                recorded_mar=_f(t["mar"]),
                n_at_run=None if t["n_trials_at_run"] is None else int(t["n_trials_at_run"]),
                var_trials=None if moments is None else float(moments["var_trials"]),
            )
        )
    if not variants:
        raise store.LabError(
            f"{method.id}: none of its recorded variants ({', '.join(missing)}) is in its method "
            f"file any more; there is nothing to re-run"
        )
    return MethodPlan(method, tuple(variants), tuple(missing))


def plan_methods(conn: sqlite3.Connection, ids: Sequence[str]) -> tuple[MethodPlan, ...]:
    """``plan_method`` for each id, upper-cased and de-duplicated in the order given."""
    out: list[MethodPlan] = []
    done: set[str] = set()
    for raw in ids:
        mid = str(raw).strip().upper()
        if mid in done:
            continue
        done.add(mid)
        out.append(plan_method(conn, mid))
    if not out:
        raise store.LabError("name at least one method, e.g. `lab survivorship M0069`")
    return tuple(out)


# --------------------------------------------------------------------------- the two stores


def peek_purpose(store_dir: Path) -> str | None:
    """The manifest's ``purpose`` without loading a bar: ``research.declared_purpose``, with its
    refusals (no manifest, not JSON, an unknown purpose) as ``store.LabError``."""
    try:
        return research.declared_purpose(Path(store_dir))
    except OSError as e:
        raise store.LabError(f"{store_dir}: cannot read the manifest ({e})") from e
    except ValueError as e:
        raise store.LabError(
            f"{e}. Point the flag at a built store (the dev store and engine/.research-sv live in "
            f"the main checkout)"
        ) from e


def check_stores(dev_dir: Path, sv_dir: Path) -> None:
    """Refuse a wrong pair of stores before either is loaded (``store.LabError``)."""
    if Path(dev_dir).resolve() == Path(sv_dir).resolve():
        raise store.LabError(
            f"--store and --sv-store both name {Path(dev_dir).resolve()}; the report compares the "
            f"dev store with the survivorship-check store, so it needs two different stores"
        )
    dev_purpose = peek_purpose(dev_dir)
    if dev_purpose is not None:
        raise store.LabError(
            f"{dev_dir} is a {dev_purpose!r} store, not the dev store. --store must be the store "
            f"the lab's trials were recorded on"
        )
    sv_purpose = peek_purpose(sv_dir)
    if sv_purpose != SV_PURPOSE:
        raise store.LabError(
            f"{sv_dir} is not a survivorship-check store (its manifest's purpose is "
            f"{sv_purpose!r}, not {SV_PURPOSE!r}). Build one with "
            f"`python -m seer_engine survivorship_store --build`"
        )


def load_checked(store_dir: Path, *, survivorship: bool) -> research.ResearchData:
    """Load one store on the dev window and check its purpose (``store.LabError`` otherwise)."""
    try:
        data = research.load_store(Path(store_dir))
    except FileNotFoundError as e:
        raise store.LabError(f"research store {store_dir} is missing {e.filename or e}") from e
    except ValueError as e:
        raise store.LabError(
            f"{store_dir}: {e}. `lab survivorship` re-runs the dev window and nothing else, so a "
            f"test-window store is refused here"
        ) from e
    if data.window != research.DEV_WINDOW:
        raise store.LabError(
            f"{store_dir} was built for the {data.window.name!r} window; `lab survivorship` "
            f"re-runs the dev window and nothing else"
        )
    if survivorship and data.purpose != SV_PURPOSE:
        raise store.LabError(
            f"{store_dir} loaded with purpose {data.purpose!r}, not {SV_PURPOSE!r}; it is not the "
            f"survivorship-check store"
        )
    if not survivorship and data.purpose is not None:
        raise store.LabError(
            f"{store_dir} loaded with purpose {data.purpose!r}; the dev side must be the store the "
            f"lab's trials were recorded on, which carries none"
        )
    return data


# --------------------------------------------------------------------------- one run's numbers


@dataclass(frozen=True)
class Side:
    """One variant's numbers on one store. Holds no market, result or DevRow."""

    store: str  # DEV_LABEL | SV_LABEL
    candidate_id: str
    start: date
    end: date
    funded: bool
    total_return: float | None
    yearly: float | None  # money-weighted when the run was fed deposits, else CAGR
    spy_yearly: float | None  # SPY TR's same measure, same money on the same days
    beats_spy: bool
    max_drawdown: float | None
    profit_factor: float | None
    trades: int
    sharpe: float | None  # annualized
    sr_daily: float | None
    t: int
    skew: float | None
    kurt: float | None  # not excess
    dsr: float | None  # at the recorded N and var_trials; None when either is missing
    era_yearly: float | None  # de-funded CAGR over HIGH_COVERAGE
    era_spy_yearly: float | None  # the recorded REF-SPY-HOLD curve's, same slice
    curve: tuple[tuple[date, float], ...] = field(compare=False, repr=False)
    deposits: Mapping[date, float] = field(compare=False, repr=False)

    @property
    def lead(self) -> float | None:
        """Yearly return minus SPY TR's, in the same measure."""
        if self.yearly is None or self.spy_yearly is None:
            return None
        return self.yearly - self.spy_yearly

    @property
    def era_edge(self) -> float | None:
        if self.era_yearly is None or self.era_spy_yearly is None:
            return None
        return self.era_yearly - self.era_spy_yearly


def side_of(
    label: str,
    v: Variant,
    row: DevRow,
    curve: Sequence[tuple[date, float]],
    deposits: Mapping[date, float],
    bench: Sequence[tuple[date, float]],
) -> Side:
    m = row.stats.metrics
    yearly = m.mwr if m.mwr is not None else m.cagr
    spy_yearly = row.spy_tr.mwr if row.spy_tr.mwr is not None else row.spy_tr.cagr
    returns = row.stats.daily_returns
    t = len(returns)
    moments = daily_moments(returns)
    if moments is None:
        sr = skew = kurt = dsr = None
    else:
        sr, skew, kurt = moments
        dsr = (
            None
            if v.var_trials is None or v.n_at_run is None
            else dev.deflated_sharpe(sr, v.n_at_run, v.var_trials, t, skew, kurt)
        )
    mine = wf.measure(curve, HIGH_COVERAGE[0], HIGH_COVERAGE[1], deposits)
    theirs = wf.measure(bench, HIGH_COVERAGE[0], HIGH_COVERAGE[1])
    return Side(
        store=label,
        candidate_id=row.candidate.id,
        start=row.start,
        end=row.end,
        funded=v.funded,
        total_return=m.total_return,
        yearly=yearly,
        spy_yearly=spy_yearly,
        beats_spy=bool(row.beats_spy),
        max_drawdown=m.max_drawdown,
        profit_factor=m.profit_factor,
        trades=int(m.trades),
        sharpe=row.stats.sharpe,
        sr_daily=sr,
        t=t,
        skew=skew,
        kurt=kurt,
        dsr=dsr,
        era_yearly=None if mine is None else mine.cagr,
        era_spy_yearly=None if theirs is None else theirs.cagr,
        curve=tuple(curve),
        deposits=dict(deposits),
    )


def run_store(
    conn: sqlite3.Connection,
    plans: Sequence[MethodPlan],
    data: research.ResearchData,
    label: str,
    bench: Sequence[tuple[date, float]],
) -> dict[tuple[str, str], Side]:
    """Every variant of every plan on ``data``: ``{(method id, candidate id): Side}``.

    One ``dev.run_registry`` call per (method, recorded capital, recorded schedule), chunked at
    ``dev.MAX_CANDIDATES``. Never across methods: two method files may define different allocator
    objects under one id, which ``run_registry`` refuses within a call.
    """
    out: dict[tuple[str, str], Side] = {}
    for plan in plans:
        mid = plan.method.id
        groups: dict[tuple[Decimal, ContributionSchedule | None], list[Variant]] = {}
        for v in plan.variants:
            groups.setdefault((v.capital, v.contributions), []).append(v)
        for (capital, contributions), group in groups.items():
            by_id = {v.candidate.id: v for v in group}
            for i in range(0, len(group), dev.MAX_CANDIDATES):
                chunk = group[i : i + dev.MAX_CANDIDATES]

                def on_result(_i: int, result: object, row: DevRow, *, _mid: str = mid,
                              _by_id: Mapping[str, Variant] = by_id) -> None:
                    v = _by_id[row.candidate.id]
                    curve = month_end_curve(result.snapshots)
                    deposits = hardgate.trial_deposits(conn, v.trial, list(curve))
                    side = side_of(label, v, row, curve, deposits, bench)
                    out[(_mid, v.candidate.id)] = side
                    log.info(
                        "[%s] %s: total return %s, yearly %s vs SPY %s, max DD %s, trades %d",
                        label, row.candidate.id, fmt_signed_pct(side.total_return),
                        fmt_signed_pct(side.yearly), fmt_signed_pct(side.spy_yearly),
                        fmt_pct(side.max_drawdown), side.trades,
                    )

                dev.run_registry(
                    data.market, data.dividends, data.spy_dividends,
                    tuple(v.candidate for v in chunk),
                    on_result=on_result, contributions=contributions, initial_idr=capital,
                )
    return out


@dataclass(frozen=True)
class StoreRun:
    """What one store produced. Strings and Sides only: the store itself is gone."""

    label: str
    store_dir: str
    fingerprint: str
    price_fingerprint: str | None
    sides: Mapping[tuple[str, str], Side] = field(compare=False, repr=False)


def measure_store(
    conn: sqlite3.Connection,
    plans: Sequence[MethodPlan],
    store_dir: Path,
    *,
    survivorship: bool,
    bench: Sequence[tuple[date, float]],
) -> StoreRun:
    """Load one store, run every variant on it, free it, return the numbers."""
    label = SV_LABEL if survivorship else DEV_LABEL
    t0 = time.perf_counter()
    data = load_checked(store_dir, survivorship=survivorship)
    log.info("%s store %s loaded (%.1fs)", label, str(data.fingerprint)[:12], time.perf_counter() - t0)
    try:
        sides = run_store(conn, plans, data, label, bench)
        return StoreRun(
            label=label,
            store_dir=str(store_dir),
            fingerprint=str(data.fingerprint),
            price_fingerprint=data.price_fingerprint,
            sides=sides,
        )
    finally:
        del data  # the only reference: the store is freed before the caller loads the next one
        gc.collect()
        log.info("%s store released (%.1fs)", label, time.perf_counter() - t0)


# --------------------------------------------------------------------------- the comparison


@dataclass(frozen=True)
class VariantRow:
    method_id: str
    variant: Variant
    dev: Side
    sv: Side

    @property
    def reproduced(self) -> bool | None:
        """Did the dev re-run land on the recorded total return? None when either is missing."""
        recorded, measured = self.variant.recorded_total_return, self.dev.total_return
        if recorded is None or measured is None:
            return None
        return abs(measured - recorded) <= REPRO_TOL * max(1.0, abs(recorded))


@dataclass(frozen=True)
class MethodReport:
    method_id: str
    method_name: str
    missing: tuple[str, ...]
    rows: tuple[VariantRow, ...]
    dev_record: wf.Record
    sv_record: wf.Record

    @property
    def headline(self) -> VariantRow:
        """The best recorded variant by MAR (ties: lower trial number; no MAR ranks last)."""
        return sorted(
            self.rows,
            key=lambda r: (
                r.variant.recorded_mar is None,
                -(r.variant.recorded_mar or 0.0),
                r.variant.trial_n,
            ),
        )[0]

    @property
    def worse(self) -> int:
        """Variants that earn less a year on the survivorship-check store."""
        return sum(
            1 for r in self.rows
            if r.dev.yearly is not None and r.sv.yearly is not None and r.sv.yearly < r.dev.yearly
        )

    @property
    def reproduced(self) -> bool:
        return all(r.reproduced is not False for r in self.rows)


def _record(
    method_id: str, sides: Sequence[Side], geo: hardgate.Geometry
) -> wf.Record:
    curves = {s.candidate_id: list(s.curve) for s in sides}
    deps = {s.candidate_id: dict(s.deposits) for s in sides}
    return wf.Record(method_id, wf.evaluate(curves, list(geo.bench), geo.folds, deps))


def compare(
    plans: Sequence[MethodPlan], dev_run: StoreRun, sv_run: StoreRun, geo: hardgate.Geometry
) -> tuple[MethodReport, ...]:
    out: list[MethodReport] = []
    for plan in plans:
        mid = plan.method.id
        rows = tuple(
            VariantRow(
                mid, v, dev_run.sides[(mid, v.candidate.id)], sv_run.sides[(mid, v.candidate.id)]
            )
            for v in plan.variants
        )
        out.append(
            MethodReport(
                method_id=mid,
                method_name=plan.method.name,
                missing=plan.missing,
                rows=rows,
                dev_record=_record(mid, [r.dev for r in rows], geo),
                sv_record=_record(mid, [r.sv for r in rows], geo),
            )
        )
    return tuple(out)


# --------------------------------------------------------------------------- the terminal report


def _finite(x: float | None) -> bool:
    return x is not None and math.isfinite(x)


def _pts(a: float | None, b: float | None) -> str:
    """``b - a`` as percentage points, signed."""
    if not (_finite(a) and _finite(b)):
        return DASH
    return f"{(b - a) * 100:+.1f} pts"


def _diff(a: float | None, b: float | None, digits: int = 2) -> str:
    if not (_finite(a) and _finite(b)):
        return DASH
    return f"{b - a:+.{digits}f}"


def _folds(rec: wf.Record) -> str:
    return rec.summary() + (", majority" if rec.majority else "")


def _variant_block(row: VariantRow) -> list[str]:
    v, d, s = row.variant, row.dev, row.sv
    measure = "money-weighted" if v.funded else "CAGR"
    if v.var_trials is None:
        dsr_row = ("DSR", "no recorded var_trials", "no recorded var_trials", DASH)
    elif v.n_at_run is None:
        dsr_row = ("DSR", "no recorded N", "no recorded N", DASH)
    else:
        dsr_row = (
            f"DSR at recorded N={v.n_at_run}",
            fmt_num(d.dsr, 3), fmt_num(s.dsr, 3), _diff(d.dsr, s.dsr, 3),
        )
    rows: list[tuple[str, str, str, str]] = [
        ("total return", fmt_signed_pct(d.total_return), fmt_signed_pct(s.total_return),
         _pts(d.total_return, s.total_return)),
        (f"yearly return ({measure})", fmt_signed_pct(d.yearly), fmt_signed_pct(s.yearly),
         _pts(d.yearly, s.yearly)),
        (f"SPY TR yearly ({measure})", fmt_signed_pct(d.spy_yearly), fmt_signed_pct(s.spy_yearly),
         _pts(d.spy_yearly, s.spy_yearly)),
        ("lead over SPY a year", fmt_signed_pct(d.lead), fmt_signed_pct(s.lead), _pts(d.lead, s.lead)),
        ("max drawdown", fmt_pct(d.max_drawdown), fmt_pct(s.max_drawdown),
         _pts(d.max_drawdown, s.max_drawdown)),
        ("profit factor", fmt_pf(d.profit_factor), fmt_pf(s.profit_factor),
         _diff(d.profit_factor, s.profit_factor)),
        ("trades", str(d.trades), str(s.trades), f"{s.trades - d.trades:+d}"),
        ("Sharpe (annualized)", fmt_num(d.sharpe), fmt_num(s.sharpe), _diff(d.sharpe, s.sharpe)),
        ("daily Sharpe", fmt_num(d.sr_daily, 4), fmt_num(s.sr_daily, 4), _diff(d.sr_daily, s.sr_daily, 4)),
        ("T (daily returns)", str(d.t), str(s.t), f"{s.t - d.t:+d}"),
        ("skew", fmt_num(d.skew, 3), fmt_num(s.skew, 3), _diff(d.skew, s.skew, 3)),
        ("kurtosis", fmt_num(d.kurt, 3), fmt_num(s.kurt, 3), _diff(d.kurt, s.kurt, 3)),
        dsr_row,
        ("2009-2015 lead over SPY a year", fmt_signed_pct(d.era_edge), fmt_signed_pct(s.era_edge),
         _pts(d.era_edge, s.era_edge)),
    ]
    width = max(len(r[0]) for r in rows)
    out = [
        f"  {d.candidate_id}  (trial #{v.trial_n}, {'funded' if v.funded else 'lump sum'}, "
        f"capital {v.capital:,.0f} IDR, {d.start}..{d.end})",
        f"    {'':<{width}}  {'dev':>14}  {'survivorship':>14}  {'change':>12}",
    ]
    out += [f"    {a:<{width}}  {b:>14}  {c:>14}  {e:>12}" for a, b, c, e in rows]
    head = f"    recorded dev trial #{v.trial_n}: total return {fmt_signed_pct(v.recorded_total_return)}"
    rep = row.reproduced
    if rep is None:
        out.append(f"{head}; there is no number to check the dev re-run against")
    elif rep:
        out.append(f"{head}; the dev re-run reproduces it")
    else:
        out.append(
            f"{head}; the dev re-run measured {fmt_signed_pct(d.total_return)} -- the store or the "
            f"engine changed since it ran, so compare the two re-runs with each other, not with "
            f"the recorded trial"
        )
    return out


def format_report(rep: MethodReport, dev_run: StoreRun, sv_run: StoreRun, n_folds: int) -> str:
    """One method's terminal table. Ids and labels are fine here."""
    out = [
        f"lab survivorship {rep.method_id} -- {rep.method_name}: {len(rep.rows)} recorded "
        f"variant(s), dev store {dev_run.fingerprint[:12]} vs survivorship-check store "
        f"{sv_run.fingerprint[:12]}",
        "report only: no trial row, no moments, no funding, no status change; the lab's N and "
        "the test-window looks do not move",
    ]
    if rep.missing:
        out.append(
            f"not re-run (recorded, but no longer in the method file): {', '.join(rep.missing)}"
        )
    for row in rep.rows:
        out.append("")
        out += _variant_block(row)
    out.append("")
    changed = (rep.dev_record.won, len(rep.dev_record.scored), rep.dev_record.majority) != (
        rep.sv_record.won, len(rep.sv_record.scored), rep.sv_record.majority
    )
    out.append(
        f"  walk-forward vs the recorded SPY hold ({n_folds} folds): dev {_folds(rep.dev_record)}; "
        f"survivorship {_folds(rep.sv_record)} -- {'changed' if changed else 'unchanged'}"
    )
    return "\n".join(out)


def summary_line(rep: MethodReport) -> str:
    h = rep.headline
    d, s = h.dev, h.sv
    return (
        f"{rep.method_id} ({h.variant.candidate.id}): yearly {fmt_signed_pct(d.yearly)} -> "
        f"{fmt_signed_pct(s.yearly)} (SPY {fmt_signed_pct(d.spy_yearly)} -> "
        f"{fmt_signed_pct(s.spy_yearly)}), max DD {fmt_pct(d.max_drawdown)} -> "
        f"{fmt_pct(s.max_drawdown)}, 2009-2015 lead {fmt_signed_pct(d.era_edge)} -> "
        f"{fmt_signed_pct(s.era_edge)}, folds {rep.dev_record.summary()} -> "
        f"{rep.sv_record.summary()}; {rep.worse} of {len(rep.rows)} variants earn less a year"
        + ("" if rep.reproduced else "; WARNING: a dev re-run did not reproduce its trial")
    )


# --------------------------------------------------------------------------- the journal


def _say_folds(rec: wf.Record) -> str:
    n = len(rec.scored)
    if n == 0:
        return "no period it could be judged on"
    return f"{rec.won} of {n} periods won"


def insight_text(rep: MethodReport) -> tuple[str, str]:
    """``(title, body)`` in plain words for a non-trader: no ids, no code, no symbols."""
    h = rep.headline
    d, s = h.dev, h.sv
    years = f"{d.start.year}–{d.end.year}"
    money = (
        "the same starting money and the same monthly top-ups"
        if h.variant.funded else "the same starting money"
    )
    intro = (
        f"The lab re-ran the {len(rep.rows)} version(s) of this method it had already tested, over "
        f"the same {years} history, twice: once on the usual price history, and once on a check "
        f"history that adds back most of the companies the usual one is missing -- companies "
        f"that left the index by failing, being bought out or changing their name. Same rules, "
        f"{money}. The numbers below are for its best version."
    )
    bullets = "\n".join(
        (
            f"- Return a year: {fmt_signed_pct(d.yearly)} on the usual history, "
            f"{fmt_signed_pct(s.yearly)} with the missing companies added (SPY: "
            f"{fmt_signed_pct(d.spy_yearly)} and {fmt_signed_pct(s.spy_yearly)}).",
            f"- Worst fall from a peak: {fmt_pct(d.max_drawdown)} and {fmt_pct(s.max_drawdown)}.",
            f"- In 2009–2015, the years the usual history covers best, its lead over SPY was "
            f"{fmt_signed_pct(d.era_edge)} a year before and {fmt_signed_pct(s.era_edge)} after.",
        )
    )
    head = (
        "The check that picks a version on earlier years and then judges it on later years it "
        "had not seen"
    )
    if (rep.dev_record.won, len(rep.dev_record.scored)) == (
        rep.sv_record.won, len(rep.sv_record.scored)
    ):
        folds = f"{head} did not change: {_say_folds(rep.dev_record)} on both histories."
    else:
        folds = (
            f"{head} moved from {_say_folds(rep.dev_record)} to {_say_folds(rep.sv_record)}."
        )
    if d.yearly is None or s.yearly is None:
        verdict = "Its yearly return could not be measured on both histories."
    else:
        gap = s.yearly - d.yearly
        if abs(gap) < 0.005:
            verdict = (
                "The missing companies barely move it: its yearly return changed by less than "
                "half a point."
            )
        elif gap < 0:
            verdict = (
                f"The missing companies flattered it: with them added it earns "
                f"{abs(gap) * 100:.1f} points a year less."
            )
        else:
            verdict = (
                f"The missing companies did not flatter it: with them added it earns "
                f"{gap * 100:.1f} points a year more."
            )
    verdict += f" {rep.worse} of its {len(rep.rows)} version(s) earn less a year with them added."
    if not rep.reproduced:
        verdict += (
            " The re-run on the usual history did not land exactly on the number the lab "
            "recorded, so the two re-runs are compared with each other, not with the record."
        )
    title = f"{rep.method_name}: what the missing companies did to it"
    body = "\n\n".join(
        (
            intro,
            bullets,
            folds,
            verdict,
            "This was a check, not a new try: the lab's count of tries did not move and no "
            "verdict changed.",
        )
    )
    return title, body


def journal(conn: sqlite3.Connection, rep: MethodReport) -> int:
    """One ``observation`` on the method. The caller owns the transaction. Returns its id."""
    title, body = insight_text(rep)
    return store.add_insight(conn, kind="observation", title=title, body=body, method_id=rep.method_id)


# --------------------------------------------------------------------------- the CSV grid

CSV_HEADER: tuple[str, ...] = (
    "method_id", "candidate_id", "store", "store_fingerprint", "price_fingerprint", "trial_n",
    "funded", "capital_idr", "start", "end", "total_return", "recorded_total_return",
    "reproduced", "yearly_return", "spy_yearly_return", "lead", "beats_spy", "max_drawdown",
    "profit_factor", "trades", "sharpe", "sr_daily", "t", "skew", "kurt", "n_at_run",
    "var_trials", "dsr", "recorded_dsr", "era_yearly", "era_spy_yearly", "era_edge",
    "wf_won", "wf_scored", "wf_majority", "wf_stable",
)


def _cell(x: object) -> str:
    if x is None:
        return ""
    if isinstance(x, bool):
        return "1" if x else "0"
    if isinstance(x, float):
        return repr(x)  # full precision; inf stays "inf"
    if isinstance(x, date):
        return x.isoformat()
    return str(x)


def csv_rows(
    reports: Sequence[MethodReport], dev_run: StoreRun, sv_run: StoreRun
) -> list[list[str]]:
    out: list[list[str]] = [list(CSV_HEADER)]
    for rep in reports:
        for row in rep.rows:
            v = row.variant
            for run, side, rec in ((dev_run, row.dev, rep.dev_record), (sv_run, row.sv, rep.sv_record)):
                out.append([
                    _cell(x) for x in (
                        rep.method_id, side.candidate_id, side.store, run.fingerprint,
                        run.price_fingerprint, v.trial_n, v.funded, v.capital, side.start,
                        side.end, side.total_return, v.recorded_total_return,
                        row.reproduced if side.store == DEV_LABEL else None,
                        side.yearly, side.spy_yearly, side.lead, side.beats_spy,
                        side.max_drawdown, side.profit_factor, side.trades, side.sharpe,
                        side.sr_daily, side.t, side.skew, side.kurt, v.n_at_run, v.var_trials,
                        side.dsr, v.recorded_dsr, side.era_yearly, side.era_spy_yearly,
                        side.era_edge, rec.won, len(rec.scored), rec.majority, rec.stable,
                    )
                ])
    return out


def write_csv(
    reports: Sequence[MethodReport], dev_run: StoreRun, sv_run: StoreRun, path: Path
) -> Path:
    """Write the full grid to ``path`` (parents created). Returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(csv_rows(reports, dev_run, sv_run))
    return path
