"""`backtest_dev`: run every candidate of the committed P7a registry on the development window
(each candidate's own start .. 2015-10-16) from the local research store, and write the dev
report set and the P7b pre-registration file. Never touches the database.

Flow:
  1. full run only: refuse (exit 2) unless backtest/registry.py is committed, because D6 commits
     every registry append before its dev run; the registry digest is the sha256 of that file
  2. load the research store (research.load_store verifies every file's sha256 and that no row
     is dated after DEV_END); read the unserved members
  3. run the candidates in registry order through dev.run_registry (one prepare per allocator
     id); every candidate is timed in the log through run_registry's on_result callback
  4. build the DevReport: survivorship over MEMBERSHIP_START..DEV_END, SPY price-only and
     total-return curves on the earliest candidate window, the D8 finalists, the top candidates
     year by year, month-end curves, deflated Sharpe
  5. full run: write <stem>.md, -rows.csv, -curves.csv, -frontier.svg to --out and the
     pre-registration to --plans. --only: render everything in memory, write nothing, and log
     an estimate of the full run's wall time (D13: parallelize only above 60 min)

There is no --end: the window always ends at DEV_END (D9). Wall times go to the log only, never
into a report file; the run date appears in file names only.

Exit 0 on success, whatever the finalists; 2 when the registry is uncommitted, the store is
missing or rejected, or an --only id is unknown; 1 on any other error (cli.main).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import math
import statistics
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from seer_engine import config, research
from seer_engine.backtest import dev
from seer_engine.backtest import io as backtest_io
from seer_engine.backtest import registry as registry_module
from seer_engine.backtest.benchmark import Dividend, spy_curves
from seer_engine.backtest.dev import Candidate, DevRow
from seer_engine.backtest.dev_report import DevReport
from seer_engine.backtest.market import Market
from seer_engine.backtest.metrics import fmt_num, fmt_pct, fmt_pf, fmt_signed_pct
from seer_engine.backtest.runner import INITIAL_IDR, survivorship
from seer_engine.sim import initial_cash_usd

log = logging.getLogger(__name__)

HELP = (
    "Run every committed P7a registry candidate on the development window (through 2015-10-16) "
    "from the local research store; write the dev report and the P7b pre-registration (read-only)"
)

DEFAULT_OUT = config.REPO_ROOT / "docs" / "backtests"
DEFAULT_PLANS = config.REPO_ROOT / "docs" / "plans"
REGISTRY_PATH = Path(registry_module.__file__).resolve()
TOP_YEARS = 5
STORE_COUNT_KEYS: tuple[str, ...] = (
    "bar_rows",
    "dividend_rows",
    "fx_rows",
    "symbols_requested",
    "symbols_served",
)
UNSERVED_FILE = "unserved.csv"

Curve = tuple[tuple[date, float], ...]


class BacktestDevError(RuntimeError):
    """The arguments cannot back a dev run (exit 2)."""


@dataclass(frozen=True)
class Timing:
    """Wall time of one candidate, from the previous candidate's end to this one's: it includes
    the allocator's ``prepare`` when this candidate was the first to use it. Log and estimate
    only, never in a report file."""

    candidate_id: str
    estimate_class: tuple[str, str, str]
    seconds: float


# --------------------------------------------------------------------------- arguments


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from e


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--store",
        type=Path,
        default=research.STORE_DIR,
        metavar="DIR",
        help="the research store built by `research_store` (default: engine/.research)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        metavar="DIR",
        help="directory for the dev report files (default: docs/backtests)",
    )
    p.add_argument(
        "--plans",
        type=Path,
        default=DEFAULT_PLANS,
        metavar="DIR",
        help="directory for the P7b pre-registration file (default: docs/plans)",
    )
    p.add_argument(
        "--run-date",
        type=_iso_date,
        default=None,
        metavar="YYYY-MM-DD",
        help="the date in the output file names (default: today); never inside a file",
    )
    p.add_argument(
        "--only",
        nargs="+",
        default=None,
        metavar="ID",
        help="smoke run: only these candidate ids, in registry order; writes nothing and "
        "skips the committed-registry check",
    )


# --------------------------------------------------------------------------- run


def run(args: argparse.Namespace) -> int:
    if getattr(args, "dry_run", False):
        log.info("dry-run: backtest_dev never touches the database; report files are written as usual")
    if research.DEV_END != dev.DEV_END:
        log.error(
            "research.DEV_END %s differs from dev.DEV_END %s; refusing to run",
            research.DEV_END.isoformat(),
            dev.DEV_END.isoformat(),
        )
        return 2
    full = args.only is None
    run_date = args.run_date if args.run_date is not None else date.today()

    if full:
        problem = registry_problem(REGISTRY_PATH)
        if problem is not None:
            log.error(
                "refusing a full dev run: %s. Commit the registry first (D6: every append is "
                "committed before its dev run), or pass --only for a smoke run that writes nothing",
                problem,
            )
            return 2

    registry = load_registry()
    try:
        candidates = select(registry, args.only)
    except BacktestDevError as e:
        log.error("%s", e)
        return 2
    digest = registry_digest(REGISTRY_PATH)
    log.info(
        "registry %s: %d candidate(s), sha256 %s; running %d%s",
        _repo_path(REGISTRY_PATH),
        len(registry),
        digest,
        len(candidates),
        "" if full else " (--only smoke run: nothing is written)",
    )

    t0 = time.perf_counter()
    try:
        data = research.load_store(Path(args.store))
        unserved = read_unserved(Path(args.store))
    except FileNotFoundError as e:
        log.error(
            "research store %s is missing %s; build it with `python -m seer_engine research_store`",
            args.store,
            e.filename or e,
        )
        return 2
    except ValueError as e:
        log.error("research store %s rejected: %s", args.store, e)
        return 2
    counts = store_counts(data.manifest)
    log.info(
        "research store %s: fingerprint %s, %d bar rows, %d of %d symbols served, %d dividend "
        "rows, %d fx rows, %d unserved (%.2fs)",
        args.store,
        data.fingerprint,
        counts["bar_rows"],
        counts["symbols_served"],
        counts["symbols_requested"],
        counts["dividend_rows"],
        counts["fx_rows"],
        len(unserved),
        _since(t0),
    )

    report, timings = execute(data, candidates, unserved=unserved, registry_digest=digest, run_date=run_date)

    if full:
        for path in backtest_io.write_dev_report(args.out, args.plans, report):
            log.info("wrote %s", path)
        return 0

    t0 = time.perf_counter()
    files = backtest_io.dev_report_files(args.out, args.plans, report)
    log.info(
        "--only: rendered %d file(s) in memory (%d characters); nothing written (%.2fs)",
        len(files),
        sum(len(text) for _, text in files),
        _since(t0),
    )
    estimate = estimate_full_run(registry, timings)
    log.info(
        "estimated full run: %.1f min for %d candidates from %d timed (D13: parallelize only above 60 min)",
        estimate / 60.0,
        len(registry),
        len(timings),
    )
    return 0


def load_registry() -> tuple[Candidate, ...]:
    """The committed registry. A function so tests can inject a fake one."""
    return tuple(registry_module.REGISTRY)


def execute(
    data: research.ResearchData,
    candidates: Sequence[Candidate],
    *,
    unserved: tuple[str, ...],
    registry_digest: str,
    run_date: date,
) -> tuple[DevReport, tuple[Timing, ...]]:
    """Everything between loading and writing. Pure except for logging and wall-time reads,
    so two calls on the same inputs return ``==`` reports; the timings are returned apart."""
    if not candidates:
        raise BacktestDevError("no candidates to run")
    t_all = time.perf_counter()
    market = data.market
    rows, curves, timings = run_candidates(market, data.dividends, data.spy_dividends, candidates)

    t0 = time.perf_counter()
    gaps = survivorship(market, dev.MEMBERSHIP_START, dev.DEV_END)
    log.info(
        "survivorship %s..%s: %d (member, session) pairs without a bar over %d year(s), %d never "
        "fetched (%.2fs)",
        dev.MEMBERSHIP_START.isoformat(),
        dev.DEV_END.isoformat(),
        sum(g.missing for g in gaps),
        len(gaps),
        sum(g.missing_never_fetched for g in gaps),
        _since(t0),
    )

    t0 = time.perf_counter()
    spy_start = min(r.start for r in rows)
    cash0 = initial_cash_usd(INITIAL_IDR, market.usd_idr_on(max(spy_start, dev.FX_START)))
    spy_price, spy_tr = spy_curves(market.spy(), spy_start, dev.DEV_END, cash0, data.spy_dividends)
    log.info(
        "SPY %s..%s from %s USD: price-only and total-return curves, %d sessions (%.2fs)",
        spy_start.isoformat(),
        dev.DEV_END.isoformat(),
        cash0,
        len(spy_tr.snapshots) - 1,
        _since(t0),
    )

    finals = dev.finalists(rows)
    if finals:
        for k, r in enumerate(finals, start=1):
            log.info("finalist %d: %s (%s), MAR %s", k, r.candidate.id, r.candidate.family, fmt_num(r.mar))
    else:
        log.info("finalists: none eligible under D8")

    report = DevReport(
        run_date=run_date,
        store_fingerprint=data.fingerprint,
        store_counts=store_counts(data.manifest),
        unserved=unserved,
        survivorship=gaps,
        registry_digest=registry_digest,
        rows=rows,
        finalists=finals,
        spy_window=(spy_start, dev.DEV_END),
        spy_price=spy_price,
        spy_tr=spy_tr,
        top_years=top_years(rows, finals),
        curves=curves,
        dsr=deflated_sharpes(rows, finals),
    )
    log.info("execute: %d candidate(s) done (%.2fs)", len(rows), _since(t_all))
    return report, timings


# --------------------------------------------------------------------------- candidates


def estimate_class(c: Candidate) -> tuple[str, str, str]:
    """Candidates expected to cost about the same per run: same allocator id, cadence, engine."""
    return (str(c.allocator.id), str(c.rules.cadence), str(c.rules.engine))


def run_candidates(
    market: Market,
    dividends: Mapping[str, Mapping[date, Decimal]],
    spy_dividends: Sequence[Dividend],
    candidates: Sequence[Candidate],
) -> tuple[tuple[DevRow, ...], tuple[tuple[str, Curve], ...], tuple[Timing, ...]]:
    """Run ``candidates`` through ``dev.run_registry`` (sequential, in the given registry order,
    one ``prepare`` per allocator id, every D9 check), collecting each result's month-end curve
    and wall time through its ``on_result`` callback. Returns the rows, the curves and the
    wall times."""
    selected = tuple(candidates)
    curves: list[tuple[str, Curve]] = []
    timings: list[Timing] = []
    n = len(selected)
    clock = [time.perf_counter()]

    def on_result(i: int, result: Any, row: DevRow) -> None:
        now = time.perf_counter()
        seconds = now - clock[0]
        clock[0] = now
        c = selected[i]
        curves.append((c.id, month_end_curve(result.snapshots)))
        timings.append(Timing(c.id, estimate_class(c), seconds))
        _log_row(i + 1, n, row, seconds)

    rows = dev.run_registry(market, dividends, spy_dividends, selected, on_result=on_result)
    return rows, tuple(curves), tuple(timings)


def _log_row(k: int, n: int, row: DevRow, seconds: float) -> None:
    m = row.stats.metrics
    log.info(
        "[%d/%d] %s (%s, %s) %s..%s: return %s vs SPY TR %s, CAGR %s, max DD %s, PF %s, "
        "trades %d, MAR %s, %s (%.2fs)",
        k,
        n,
        row.candidate.id,
        row.candidate.family,
        row.candidate.rules.id,
        row.start.isoformat(),
        row.end.isoformat(),
        fmt_signed_pct(m.total_return),
        fmt_signed_pct(row.spy_tr.total_return),
        fmt_signed_pct(m.cagr),
        fmt_pct(m.max_drawdown),
        fmt_pf(m.profit_factor),
        m.trades,
        fmt_num(row.mar),
        "eligible" if row.eligible else "failed: " + "; ".join(row.failed),
        seconds,
    )


def select(registry: Sequence[Candidate], only: Sequence[str] | None) -> tuple[Candidate, ...]:
    """The whole registry, or the ``only`` ids in registry order (duplicates collapse).
    BacktestDevError names every unknown id."""
    if only is None:
        return tuple(registry)
    wanted = set(only)
    unknown = sorted(wanted - {c.id for c in registry})
    if unknown:
        raise BacktestDevError(f"unknown candidate id(s) for --only: {', '.join(unknown)}")
    return tuple(c for c in registry if c.id in wanted)


# --------------------------------------------------------------------------- report pieces


def month_end_curve(snapshots: Sequence[Any]) -> Curve:
    """Equity normalized to the first snapshot (the starting cash), at the last snapshot of
    every calendar month, ascending. The first snapshot (prev_session(start)) closes its own
    month at 1.0 unless a later snapshot shares that month."""
    if not snapshots:
        raise ValueError("a curve needs at least one snapshot")
    base = snapshots[0].equity_usd
    if base <= 0:
        raise ValueError(f"the first snapshot's equity must be > 0, got {base}")
    last: dict[tuple[int, int], Any] = {}
    for s in snapshots:
        last[(s.date.year, s.date.month)] = s
    return tuple((s.date, float(s.equity_usd / base)) for _, s in sorted(last.items()))


def top_years(rows: Sequence[DevRow], finals: Sequence[DevRow], k: int = TOP_YEARS) -> tuple[
    tuple[str, tuple[tuple[int, float], ...]], ...
]:
    """Year-by-year returns for up to ``k`` candidates: the finalists first (in finalist order),
    then the remaining rows with a MAR, by (-MAR, id)."""
    chosen = [r.candidate.id for r in finals][:k]
    ranked = sorted((r for r in rows if r.mar is not None), key=lambda r: (-r.mar, r.candidate.id))
    for r in ranked:
        if len(chosen) >= k:
            break
        if r.candidate.id not in chosen:
            chosen.append(r.candidate.id)
    by_id = {r.candidate.id: r for r in rows}
    return tuple((cid, tuple(by_id[cid].stats.year_returns)) for cid in chosen)


def daily_moments(returns: Sequence[float]) -> tuple[float, float, float] | None:
    """(daily Sharpe = mean / pstdev, skewness m3 / m2^1.5, kurtosis m4 / m2^2 (not excess))
    over population moments; None with fewer than 2 returns or zero variance."""
    n = len(returns)
    if n < 2:
        return None
    mean = math.fsum(returns) / n
    dev_ = [x - mean for x in returns]
    m2 = math.fsum(d * d for d in dev_) / n
    if not m2 > 0.0:
        return None
    m3 = math.fsum(d * d * d for d in dev_) / n
    m4 = math.fsum(d * d * d * d for d in dev_) / n
    sd = math.sqrt(m2)
    return mean / sd, m3 / (m2 * sd), m4 / (m2 * m2)


def deflated_sharpes(rows: Sequence[DevRow], finals: Sequence[DevRow]) -> tuple[tuple[str, float | None], ...]:
    """The deflated Sharpe ratio per finalist, or for the best annualized-Sharpe row (ties by
    id) when there is none; () when no row has a Sharpe. Trials = every row run; the variance
    across trials is the sample variance of the daily Sharpe over the rows that have one."""
    moments = {r.candidate.id: daily_moments(r.stats.daily_returns) for r in rows}
    sharpes = [m[0] for m in moments.values() if m is not None]
    var_trials = statistics.variance(sharpes) if len(sharpes) >= 2 else None
    if finals:
        targets = list(finals)
    else:
        with_sharpe = [r for r in rows if r.stats.sharpe is not None]
        if not with_sharpe:
            return ()
        targets = [min(with_sharpe, key=lambda r: (-r.stats.sharpe, r.candidate.id))]
    out: list[tuple[str, float | None]] = []
    for r in targets:
        m = moments[r.candidate.id]
        if m is None or var_trials is None or len(rows) < 2:
            out.append((r.candidate.id, None))
            continue
        sr, skew, kurt = m
        value = dev.deflated_sharpe(sr, len(rows), var_trials, len(r.stats.daily_returns), skew, kurt)
        out.append((r.candidate.id, value))
    return tuple(out)


def store_counts(manifest: Mapping[str, Any]) -> dict[str, int]:
    """The manifest's counts in STORE_COUNT_KEYS order; a list value counts its items."""
    out: dict[str, int] = {}
    for key in STORE_COUNT_KEYS:
        if key not in manifest:
            raise ValueError(f"the store manifest has no {key!r}")
        value = manifest[key]
        out[key] = len(value) if isinstance(value, (list, tuple)) else int(value)
    return out


def read_unserved(store_dir: Path) -> tuple[str, ...]:
    """The member symbols yfinance served nothing for (``unserved.csv``), sorted, unique."""
    text = (Path(store_dir) / UNSERVED_FILE).read_text(encoding="utf-8")
    reader = csv.reader(text.splitlines())
    header = next(reader, None)
    if header is None or header[:1] != ["symbol"]:
        raise ValueError(f"{UNSERVED_FILE}: expected a header starting with 'symbol', got {header!r}")
    return tuple(sorted({row[0] for row in reader if row and row[0]}))


# --------------------------------------------------------------------------- registry state


def registry_problem(path: Path) -> str | None:
    """None when ``path`` is tracked by git with no uncommitted change (modified, staged or
    untracked); otherwise why a full dev run must not use it."""
    path = Path(path).resolve()
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain", "--", path.name],
            cwd=path.parent,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "git is not installed, so the registry's commit state cannot be checked"
    except NotADirectoryError:
        return f"{path.parent} is not a directory"
    if status.returncode != 0:
        return f"git status failed for {path} ({status.stderr.strip() or status.returncode})"
    if status.stdout.strip():
        return f"{path.name} has uncommitted changes ({status.stdout.strip()})"
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", path.name],
        cwd=path.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    if tracked.returncode != 0:
        return f"{path} is not tracked by git"
    return None


def registry_digest(path: Path) -> str:
    """sha256 hex of the registry source file's bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --------------------------------------------------------------------------- runtime estimate


def estimate_full_run(registry: Sequence[Candidate], timings: Sequence[Timing]) -> float:
    """Seconds a full run should take, from a smoke run's timings: each registry candidate
    costs the mean time of the timed candidates in its estimate_class, else the mean of every
    timed candidate. A timed candidate's time includes its allocator's prepare when it was the
    first to use it, so the estimate errs high (D13 then errs toward the pool)."""
    if not timings:
        return 0.0
    by_class: dict[tuple[str, str, str], list[float]] = {}
    for t in timings:
        by_class.setdefault(t.estimate_class, []).append(t.seconds)
    mean_all = math.fsum(t.seconds for t in timings) / len(timings)
    total = 0.0
    for c in registry:
        runs = by_class.get(estimate_class(c))
        total += math.fsum(runs) / len(runs) if runs else mean_all
    return total


# --------------------------------------------------------------------------- helpers


def _repo_path(path: Path) -> str:
    """``path`` relative to the repository root in POSIX form, or absolute when outside it."""
    p = Path(path).resolve()
    try:
        return p.relative_to(config.REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def _since(t0: float) -> float:
    return time.perf_counter() - t0
