"""How bad an assumed delisting would have to be before the lab's edge disappears.

Handover section 5 Q1. Injects synthetic delistings into the dev-window ranking universe at the
hazard the store's own membership records, re-runs each roster entry's backtest against the
perturbed market, and solves for the **break-even delisting return** -- the assumed loss at which
the entry stops beating total-return SPY.

    engine/.venv/bin/python engine/scripts/delisting_stress.py --smoke
    engine/.venv/bin/python engine/scripts/delisting_stress.py --seeds 100 --jobs 6

Read-only, exactly like `survivorship_coverage.py`: it loads the research store, writes nothing,
records no trial, does not move the lab's N and spends no test-window look. `backtest.dev` is
pure -- a trial is written by `lab.runner.run_method`, never by `dev` -- so calling
`dev.run_candidate` here costs nothing and changes nothing. The only lab module this script
touches is `lab.method.discover`, which reads the method files and opens no database; neither it
nor `seer_engine.delisting` imports `lab.store` or `lab.runner`, and a test asserts the second half
of that.

WHY THE BACKTEST IS RE-RUN RATHER THAN THE RECORDED CURVE RE-SLICED. `trials.curve_json` is a
month-end equity curve and carries no positions, no symbols and no trades. An injection changes
WHICH names are held, so a perturbed path cannot be derived from an unperturbed one.
`survivorship_coverage.py` could slice; this cannot. One full dev-window run measures at 2-3 s on
an idle machine and 5-11 s under concurrent load, so four entries x eight assumed returns x a
hundred seeds is hours, not days -- budget against the loaded number.

WHAT THE BREAK-EVEN NUMBER MEANS. The edge is strategy CAGR minus total-return SPY CAGR, in points
a year -- the handover's own unit. For each assumed return r the harness runs every seed, takes the
mean edge, and reports the r at which that mean first reaches zero, interpolated linearly between
the two grid points that straddle it. When the mean edge is still positive at the most negative r
on the grid there is no break-even inside it, and the harness says so rather than extrapolating.
It also reports the per-seed distribution of the same crossing, because a mean of a hundred
Monte Carlo paths hides how many of them disagree with it.

WHAT IT CANNOT ANSWER. Two things, both worth saying out loud wherever the number is quoted:

1. The r = 0 row is not the unstressed row. Removing names from the ranking pool at the historical
   rate costs something all by itself, even when every delisted holder is paid the last price
   anyone saw. The table prints the unstressed run and the r = 0 run as separate lines so that
   universe-thinning cost and delisting-loss cost are never read as one number.
2. 118 of the store's 522 unserved ever-members were still index members at the window's end. They
   did not die inside the window; a free feed dropped them afterwards. No delisting injection can
   model them, because what is missing there is a price path and not a death.
"""

from __future__ import annotations

import argparse
import csv
import multiprocessing
import os
import sys
import time
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from random import Random

import numpy as np

from seer_engine import config, research
from seer_engine.backtest.dev import Candidate, run_candidate
from seer_engine.backtest.market import Market
from seer_engine.delisting import Exposure, Hazard, measure_hazard, stressed, survivors
from seer_engine.lab.method import discover
from seer_engine.research import ResearchData, load_store
from seer_engine.strategies.allocator import prepare_for

#: The quant roster entries, by the lab variant each was promoted from (== survivorship_coverage).
ROSTER: tuple[tuple[str, str], ...] = (
    ("RMW-FR", "M0022-W-TV16"),
    ("RAW-FR", "M0007-N20-RAW"),
    ("MOM-FR", "M0002-REL-85"),
    ("MVW-FR", "M0008-N30-C07"),
)

#: The default grid of assumed delisting returns: 0 is what every recorded backtest already
#: assumes (sold whole at the last price seen), -1 is a total loss.
RETURNS: tuple[float, ...] = (0.0, -0.10, -0.20, -0.30, -0.50, -0.70, -0.90, -1.00)

BANNER = (
    "delisting stress -- read-only. No lab trial is recorded, the lab's N does not move, no "
    "test-window look is spent, and nothing is written to the research store."
)


@dataclass(frozen=True)
class Outcome:
    """One run's result: a roster entry at one assumed delisting return under one seed.

    ``delisting_return`` and ``seed`` are None for the unstressed reference run. ``edge`` is in
    points of CAGR a year over total-return SPY, which is the unit the handover's era table uses.
    """

    entry: str
    candidate: str
    delisting_return: float | None
    seed: int | None
    deaths: int
    start: date
    cagr: float | None
    max_drawdown: float | None
    total_return: float | None
    trades: int
    spy_cagr: float | None
    beats_spy: bool

    @property
    def edge(self) -> float | None:
        if self.cagr is None or self.spy_cagr is None:
            return None
        return (self.cagr - self.spy_cagr) * 100.0


@dataclass(frozen=True)
class _Shared:
    """Everything a worker needs, set once in the parent and inherited across ``fork``."""

    data: ResearchData
    exposures: tuple[Exposure, ...]
    candidates: dict[str, Candidate]
    hazard: float
    decline: int


_SHARED: _Shared | None = None


# --------------------------------------------------------------------------- running


def _run_one(
    entry: str,
    market: Market,
    delisting_return: float | None,
    seed: int | None,
    deaths: int,
) -> Outcome:
    """Run one candidate against one market and fold the result into an :class:`Outcome`."""
    assert _SHARED is not None, "_SHARED must be set before any run"
    candidate = _SHARED.candidates[entry]
    prepared = prepare_for(candidate.allocator, market)
    _result, row = run_candidate(
        market, _SHARED.data.dividends, _SHARED.data.spy_dividends, candidate, prepared=prepared
    )
    m = row.stats.metrics
    return Outcome(
        entry=entry,
        candidate=candidate.id,
        delisting_return=delisting_return,
        seed=seed,
        deaths=deaths,
        start=row.start,
        cagr=m.cagr,
        max_drawdown=m.max_drawdown,
        total_return=m.total_return,
        trades=m.trades,
        spy_cagr=row.spy_tr.cagr,
        beats_spy=row.beats_spy,
    )


def _base(entry: str) -> Outcome:
    """The unstressed reference run for ``entry``."""
    assert _SHARED is not None, "_SHARED must be set before any run"
    return _run_one(entry, _SHARED.data.market, None, None, 0)


def _stressed_one(job: tuple[str, float, int]) -> Outcome:
    """One (entry, assumed return, seed) cell. The Pool's work unit; must be module level."""
    assert _SHARED is not None, "_SHARED must be set before any run"
    entry, delisting_return, seed = job
    market, deaths = stressed(
        _SHARED.data.market,
        _SHARED.exposures,
        hazard_per_year=_SHARED.hazard,
        delisting_return=delisting_return,
        rng=Random(seed),
        decline_sessions=_SHARED.decline,
    )
    return _run_one(entry, market, delisting_return, seed, len(deaths))


def _progress(results: Iterable[Outcome], total: int) -> Iterator[Outcome]:
    """Pass results through, printing a one-line counter to stderr (stdout stays a clean table)."""
    started = time.perf_counter()
    for i, outcome in enumerate(results, start=1):
        elapsed = time.perf_counter() - started
        left = elapsed / i * (total - i)
        print(
            f"\r  {i}/{total} runs  {elapsed / 60:.1f} min elapsed, ~{left / 60:.1f} min left   ",
            end="",
            file=sys.stderr,
            flush=True,
        )
        yield outcome
    print("", file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- the solver


def break_even(points: Sequence[tuple[float, float]]) -> float | None:
    """The assumed delisting return at which ``edge`` first reaches zero, or None.

    ``points`` is ``(assumed return, edge in points a year)``, in any order. Searched from the
    least negative return downwards; the crossing is linear between the two grid points that
    straddle it. None when the edge is still positive at the most negative point -- there is no
    break-even inside the grid, and the harness refuses to extrapolate past the data it has.
    """
    ordered = sorted(points, key=lambda p: -p[0])
    if not ordered:
        return None
    if ordered[0][1] <= 0.0:
        return ordered[0][0]
    for (r0, e0), (r1, e1) in zip(ordered, ordered[1:]):
        if e1 <= 0.0:
            return r0 + (r1 - r0) * (e0 / (e0 - e1))
    return None


def _per_seed_break_even(by_seed: dict[int, list[tuple[float, float]]]) -> tuple[list[float], int]:
    """Each seed's own break-even, and how many seeds never break even on the grid."""
    found: list[float] = []
    never = 0
    for seed in sorted(by_seed):
        value = break_even(by_seed[seed])
        if value is None:
            never += 1
        else:
            found.append(value)
    return found, never


# --------------------------------------------------------------------------- printing


def _pct(x: float | None) -> str:
    """A signed percentage -- a return, which may go either way."""
    return "       -" if x is None else f"{x * 100:+7.2f}%"


def _fall(x: float | None) -> str:
    """An unsigned percentage -- a drawdown, which only ever goes one way."""
    return "      -" if x is None else f"{x * 100:6.2f}%"


def _print_hazard(hazard: Hazard, exposures: Sequence[Exposure], rate: float, label: str) -> None:
    print("=== 1. the delisting hazard the store's own membership records ===")
    print(f"window {hazard.window_start} .. {hazard.window_end}  ({hazard.window_years:.2f} years)")
    print(f"ever-members {hazard.ever_members}   priced {hazard.served}   unpriced {hazard.unserved}")
    print(f"left the index inside the window: {hazard.exits}"
          f"   of those unpriced {hazard.unserved_exits}, priced {hazard.served_exits}")
    print(f"mean members on a mid-year date {hazard.mean_members:.2f}"
          f"   member-years {hazard.member_years}")
    print(f"  annual exit hazard, every exit:        {hazard.exit_rate:.3%}")
    print(f"  annual exit hazard, the unpriced ones: {hazard.unserved_exit_rate:.3%}")
    if hazard.unrecorded_unserved or hazard.unserved_but_priced:
        print(f"  NOTE unserved.csv disagrees with the bars: missing from the file "
              f"{hazard.unrecorded_unserved}, listed but priced {hazard.unserved_but_priced}")
    years = sum(e.years for e in exposures)
    print(f"\neligible to be killed: {len(exposures)} priced survivors over {years:,.0f} member-years")
    print(f"injecting at {rate:.3%}/yr ({label})")
    print(f"  expected deaths, competing risks included: "
          f"{sum(1.0 - np.exp(-rate * e.years) for e in exposures):.1f}")
    print(f"  (a memoryless process over the same member-years would give {rate * years:.1f})")
    print("\nNOT modelled, and no injection can model it: the unpriced names that were STILL index\n"
          "members at the window's end. They did not die inside the window; a free feed dropped\n"
          "them afterwards, and what is missing for them is a price path, not a death.\n")


def _print_entry(entry: str, candidate: str, base: Outcome, outcomes: Sequence[Outcome],
                 returns: Sequence[float], seeds: int) -> None:
    print(f"=== {entry}  ({candidate}) ===")
    print(f"unstressed:   CAGR {_pct(base.cagr)}/yr   worst fall {_fall(base.max_drawdown)}"
          f"   trades {base.trades:5}   edge over SPY TR {base.edge:+6.2f} pts/yr")
    print("\n  assumed r   deaths     CAGR/yr    worst fall    trades"
          "      edge pts/yr  (p10 .. p90)    beats SPY")
    mean_points: list[tuple[float, float]] = []
    by_seed: dict[int, list[tuple[float, float]]] = {}
    for r in returns:
        rows = [o for o in outcomes if o.delisting_return == r]
        if not rows:
            continue
        edges = [o.edge for o in rows if o.edge is not None]
        cagrs = [o.cagr for o in rows if o.cagr is not None]
        falls = [o.max_drawdown for o in rows if o.max_drawdown is not None]
        mean_edge = float(np.mean(edges)) if edges else 0.0
        mean_points.append((r, mean_edge))
        for o in rows:
            if o.seed is not None and o.edge is not None:
                by_seed.setdefault(o.seed, []).append((r, o.edge))
        beats = sum(1 for o in rows if o.beats_spy)
        print(f"   {r * 100:+6.0f}%   {float(np.mean([o.deaths for o in rows])):6.1f}"
              f"    {float(np.mean(cagrs)) * 100 if cagrs else float('nan'):+7.2f}%"
              f"      {float(np.mean(falls)) * 100 if falls else float('nan'):6.2f}%"
              f"     {float(np.mean([o.trades for o in rows])):6.0f}"
              f"      {mean_edge:+6.2f}"
              f"  ({float(np.percentile(edges, 10)):+6.2f} .. {float(np.percentile(edges, 90)):+6.2f})"
              f"      {beats:4}/{len(rows)}")
    crossing = break_even(mean_points)
    print()
    if crossing is None:
        worst_r, worst_edge = min(mean_points, key=lambda p: p[0])
        print(f"break-even delisting return: NONE on this grid. The mean edge is still "
              f"{worst_edge:+.2f} pts/yr at r = {worst_r * 100:.0f}%, so even a total loss on every "
              f"injected delisting leaves {entry} ahead of total-return SPY.")
    else:
        print(f"break-even delisting return: {crossing * 100:.1f}%  "
              f"(the mean edge over {seeds} seeds crosses zero there)")
    found, never = _per_seed_break_even(by_seed)
    if found:
        tail = "" if not never else f", and {never} of {len(by_seed)} seeds never break even on this grid"
        print(f"  per seed: median {float(np.median(found)) * 100:.1f}%, "
              f"p10 {float(np.percentile(found, 10)) * 100:.1f}%, "
              f"p90 {float(np.percentile(found, 90)) * 100:.1f}%{tail}")
    elif by_seed:
        print(f"  per seed: none of the {len(by_seed)} seeds breaks even anywhere on this grid")
    print()


def _write_csv(path: Path, outcomes: Sequence[Outcome]) -> None:
    """One row per run, for whoever has to quote these numbers later."""
    resolved = path.resolve()
    for forbidden in (config.REPO_ROOT / "engine" / ".research", config.REPO_ROOT / "lab"):
        if resolved == forbidden or forbidden in resolved.parents:
            raise SystemExit(f"--csv must not write inside {forbidden}; this harness writes nothing there")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8", newline="\n") as fh:
        writer = csv.writer(fh)
        writer.writerow(("entry", "candidate", "delisting_return", "seed", "deaths", "start",
                         "cagr", "max_drawdown", "total_return", "trades", "spy_cagr",
                         "edge_points_per_year", "beats_spy"))
        for o in outcomes:
            writer.writerow((o.entry, o.candidate,
                             "" if o.delisting_return is None else f"{o.delisting_return:.4f}",
                             "" if o.seed is None else o.seed, o.deaths, o.start.isoformat(),
                             "" if o.cagr is None else f"{o.cagr:.6f}",
                             "" if o.max_drawdown is None else f"{o.max_drawdown:.6f}",
                             "" if o.total_return is None else f"{o.total_return:.6f}",
                             o.trades,
                             "" if o.spy_cagr is None else f"{o.spy_cagr:.6f}",
                             "" if o.edge is None else f"{o.edge:.4f}",
                             "yes" if o.beats_spy else "no"))
    print(f"wrote {len(outcomes)} rows to {resolved}")


# --------------------------------------------------------------------------- the command line


def _parse(argv: Sequence[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="delisting_stress.py",
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--entry", action="append", default=None, metavar="NAME",
                   help="a roster name (RMW-FR) or a lab candidate id (M0022-W-TV16); repeatable. "
                        "Default: all four quant roster entries.")
    p.add_argument("--returns", default=None, metavar="LIST",
                   help="comma-separated assumed delisting returns in [-1, 0], e.g. "
                        "'0,-0.25,-0.5,-1'. Default: " + ",".join(f"{r:g}" for r in RETURNS))
    p.add_argument("--seeds", type=int, default=100, metavar="N",
                   help="Monte Carlo seeds per (entry, return) cell (default 100)")
    p.add_argument("--seed0", type=int, default=0, metavar="N",
                   help="the first seed; seeds are seed0 .. seed0 + seeds - 1 (default 0)")
    p.add_argument("--hazard", default="unserved", metavar="RATE",
                   help="the annual hazard to inject: 'unserved' (the measured unpriced-exit "
                        "rate, ~4.0%%/yr, the base case), 'all' (every exit, ~5.1%%/yr, the upper "
                        "sensitivity), or a number such as 0.04 (default: unserved)")
    p.add_argument("--decline-sessions", type=int, default=1, metavar="N",
                   help="1 = abrupt death, the conservative base case; N > 1 spreads the same "
                        "total loss over the last N bars as a visible decline (the forewarned "
                        "sensitivity)")
    p.add_argument("--jobs", type=int, default=1, metavar="N",
                   help="worker processes (fork; Linux only). The store is ~940 MB shared and "
                        "each worker adds roughly 150 MB. Default 1.")
    p.add_argument("--store", type=Path,
                   default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR),
                   help="the research store directory ($SEER_RESEARCH_STORE). In a worktree this "
                        "must point at the MAIN checkout: the store is gitignored and is not "
                        "copied into a worktree.")
    p.add_argument("--csv", type=Path, default=None, metavar="PATH",
                   help="also write one row per run to this file (never inside engine/.research "
                        "or lab/)")
    p.add_argument("--smoke", action="store_true",
                   help="one entry, two returns, two seeds: proves the harness runs end to end. "
                        "About 30-45 s on an idle machine, 60-90 s under swarm load; almost all "
                        "of it load_store.")
    args = p.parse_args(argv)
    if args.smoke:
        args.entry = args.entry or ["RMW-FR"]
        args.returns = args.returns or "0,-1"
        args.seeds = min(args.seeds, 2)
        args.jobs = 1
    return args


def _entries(chosen: Sequence[str] | None) -> tuple[tuple[str, str], ...]:
    if not chosen:
        return ROSTER
    by_name = {name: cid for name, cid in ROSTER}
    by_id = {cid: name for name, cid in ROSTER}
    out: list[tuple[str, str]] = []
    for item in chosen:
        if item in by_name:
            out.append((item, by_name[item]))
        elif item in by_id:
            out.append((by_id[item], item))
        else:
            out.append((item, item))  # any lab candidate id, named after itself
    return tuple(out)


def _returns(text: str | None) -> tuple[float, ...]:
    if text is None:
        return RETURNS
    out: list[float] = []
    for piece in text.split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            value = float(piece)
        except ValueError:
            raise SystemExit(f"--returns: {piece!r} is not a number") from None
        if not -1.0 <= value <= 0.0:
            raise SystemExit(f"--returns: {value} is outside [-1, 0]")
        out.append(value)
    if not out:
        raise SystemExit("--returns must name at least one assumed delisting return")
    return tuple(sorted(set(out), reverse=True))


def _rate(choice: str, measured: Hazard) -> tuple[float, str]:
    if choice == "unserved":
        return measured.unserved_exit_rate, "the measured unpriced-exit rate"
    if choice == "all":
        return measured.exit_rate, "the measured all-exit rate, the upper sensitivity"
    try:
        value = float(choice)
    except ValueError:
        raise SystemExit(f"--hazard must be 'unserved', 'all' or a number, got {choice!r}") from None
    if not 0.0 <= value <= 1.0:
        raise SystemExit(f"--hazard must be in [0, 1] per year, got {value}")
    return value, "given on the command line"


def _candidates(wanted: Iterable[tuple[str, str]]) -> dict[str, Candidate]:
    """Roster name -> the lab Candidate it was promoted from, via lab.method.discover()."""
    by_id: dict[str, Candidate] = {}
    for method, _path in discover().values():
        for c in method.candidates:
            by_id[c.id] = c
    out: dict[str, Candidate] = {}
    for name, candidate_id in wanted:
        if candidate_id not in by_id:
            raise SystemExit(f"no lab candidate {candidate_id!r}; run `python -m seer_engine lab list`")
        out[name] = by_id[candidate_id]
    return out


def main(argv: Sequence[str] | None = None) -> int:
    global _SHARED
    args = _parse(argv)
    entries = _entries(args.entry)
    returns = _returns(args.returns)
    seeds = tuple(range(args.seed0, args.seed0 + max(args.seeds, 1)))
    if args.jobs < 1:
        raise SystemExit(f"--jobs must be >= 1, got {args.jobs}")
    if args.decline_sessions < 1:
        raise SystemExit(f"--decline-sessions must be >= 1, got {args.decline_sessions}")

    print(BANNER)
    print(f"store {args.store}\n")
    started = time.perf_counter()
    data = load_store(args.store)
    print(f"loaded {len(data.market.history)} symbols in {time.perf_counter() - started:.1f}s"
          f"   fingerprint {data.fingerprint[:12]}\n")

    hazard = measure_hazard(data.market, unserved=data.unserved)
    exposures = survivors(data.market)
    rate, label = _rate(args.hazard, hazard)
    _print_hazard(hazard, exposures, rate, label)

    _SHARED = _Shared(
        data=data,
        exposures=exposures,
        candidates=_candidates(entries),
        hazard=rate,
        decline=args.decline_sessions,
    )

    print("=== 2. the stressed runs ===")
    print(f"{len(entries)} entries x {len(returns)} assumed returns x {len(seeds)} seeds "
          f"= {len(entries) * len(returns) * len(seeds)} runs"
          f"   ({'abrupt death' if args.decline_sessions == 1 else f'decline over {args.decline_sessions} sessions'})\n")

    bases = {name: _base(name) for name, _cid in entries}
    jobs = [(name, r, seed) for name, _cid in entries for r in returns for seed in seeds]
    if args.jobs == 1:
        outcomes = list(_progress((_stressed_one(j) for j in jobs), len(jobs)))
    else:
        ctx = multiprocessing.get_context("fork")
        with ctx.Pool(args.jobs) as pool:
            outcomes = list(_progress(pool.imap_unordered(_stressed_one, jobs, chunksize=1), len(jobs)))

    for name, _cid in entries:
        base = bases[name]
        wrong = [o for o in outcomes if o.entry == name and o.start != base.start]
        if wrong:
            raise SystemExit(
                f"{name}: a stressed run opened on {wrong[0].start} but the unstressed run opens on "
                f"{base.start}; the comparison is not like for like. No ETF or SPY should ever be "
                "killed -- check survivors()."
            )

    print()
    for name, _cid in entries:
        _print_entry(name, _SHARED.candidates[name].id, bases[name],
                     [o for o in outcomes if o.entry == name], returns, len(seeds))

    if args.csv is not None:
        _write_csv(args.csv, [bases[name] for name, _cid in entries] + outcomes)
    print(f"total {(time.perf_counter() - started) / 60:.1f} min. {BANNER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
