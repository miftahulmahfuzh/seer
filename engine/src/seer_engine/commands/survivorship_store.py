"""survivorship_store -- build the survivorship-check store from the EODHD cache. No network.

    python -m seer_engine survivorship_store            # clean every cached series, print the coverage report; writes nothing
    python -m seer_engine survivorship_store --build    # write the store at --out (default engine/.research-sv)
    python -m seer_engine survivorship_store --report   # print the reports of the store already at --out

The store is ``--source`` (default the dev store, ``engine/.research``, read only) plus a cleaned
EODHD series for every member the dev store could not serve, read from ``--cache`` (default
``engine/.cache/eodhd``: ``eod/``, ``splits/``, ``dividends/``). ``seer_engine.survivorship`` holds
the cleaning rules; this module only reads, merges and writes.

What lands in ``--out``, built in ``<out>.tmp`` and swapped in whole or not at all:

- ``bars.csv`` / ``dividends.csv``: the source's lines, byte for byte, with the added symbols'
  lines inserted at their sorted place; ``fx.csv`` and every optional file (``fundamentals.csv``
  and whatever else the source lists) copied byte for byte and sha-checked;
- ``unserved.csv``: the members still without a bar, each with the reason the cleaning gave;
- ``dividend_announcements.csv``: re-matched with ``dividend_announcements.match`` over the merged
  dividends from the cached ``dividends/`` files (carried from the source when the cache has none);
- ``manifest.json``: sealed for the dev window with ``"purpose": "survivorship-check"``, so its
  price fingerprint is its own and ``lab run`` / ``lab test`` / ``lab remeasure`` refuse it;
- ``cleaning_report.csv`` (one row per symbol the dev store could not serve: action, reason,
  counts) and ``coverage_report.txt`` (member-days per year before and after, and the members still
  missing). Both sit inside the store but outside the manifest: the loader ignores unlisted files,
  so the reports can be read without touching the fingerprint.

``--out`` must not be the source, a symlink, or the dev or test store's directory: ``_swap_in``
would replace the directory a symlink names. The source is verified with ``research.load_store``
first, and the built store is loaded once more before it is swapped in.

Exit codes: 0 ok; 2 refused (paths, a source that does not verify or is itself a
survivorship-check store, a store at ``--out`` that is not one, for ``--report``).
"""

from __future__ import annotations

import argparse
import logging
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from seer_engine import config, dates, research
from seer_engine import dividend_announcements as da
from seer_engine import survivorship as sv
from seer_engine.commands.dividend_announcements import read_cache

log = logging.getLogger(__name__)

HELP = (
    "Build the survivorship-check store (engine/.research-sv): the dev store plus cleaned EODHD "
    "bars for the members it never served, from the local cache, with a cleaning and a coverage "
    "report inside it."
)

CACHE_DIR = config.REPO_ROOT / "engine" / ".cache" / "eodhd"
CLEANING_REPORT = "cleaning_report.csv"
COVERAGE_REPORT = "coverage_report.txt"
REPORT_FILES: tuple[str, ...] = (CLEANING_REPORT, COVERAGE_REPORT)


class SurvivorshipStoreError(RuntimeError):
    """The build was refused or could not finish; nothing was written."""


@dataclass(frozen=True)
class BuildPlan:
    """Everything a build writes, computed in memory from the source store and the cache."""

    source_dir: Path
    source_manifest: Mapping[str, Any]
    source_price_fingerprint: str | None
    cleaned: Mapping[str, sv.Cleaned]  # one per symbol the source could not serve
    source_dividends: Mapping[str, Mapping[date, Any]]
    coverage: tuple[sv.YearCoverage, ...]
    missing: tuple[tuple[str, int, str], ...]  # (symbol, member days, why), members still without a bar

    @property
    def added(self) -> dict[str, sv.Cleaned]:
        return {s: c for s, c in sorted(self.cleaned.items()) if c.action != sv.DROPPED}

    @property
    def still_unserved(self) -> dict[str, sv.Cleaned]:
        return {s: c for s, c in sorted(self.cleaned.items()) if c.action == sv.DROPPED}


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--build", action="store_true", help="write the store at --out")
    p.add_argument("--report", action="store_true", help="print the reports of the store at --out")
    p.add_argument("--out", type=Path, default=research.SV_STORE_DIR, help=f"store to write (default {research.SV_STORE_DIR})")
    p.add_argument("--source", type=Path, default=research.STORE_DIR, help=f"dev store to start from, read only (default {research.STORE_DIR})")
    p.add_argument("--cache", type=Path, default=CACHE_DIR, help=f"EODHD cache (default {CACHE_DIR})")


# ---- planning ------------------------------------------------------------------------------


def plan_build(
    source_dir: Path,
    cache: Path,
    *,
    data_dir: Path | None = None,
    extra_sources: Mapping[str, Sequence[sv.SourceSeries]] | None = None,
) -> BuildPlan:
    """Clean every symbol the source store could not serve; nothing is written.

    ``extra_sources`` maps a store symbol to further candidate series (phase 2's alias fill);
    each is cleaned like the cache's own and :func:`survivorship.best_of` keeps the one covering
    the most member days. SurvivorshipStoreError when the source does not verify or is itself a
    survivorship-check store.
    """
    source_dir = Path(source_dir)
    try:
        data = research.load_store(source_dir, data_dir=data_dir)
    except ValueError as exc:
        raise SurvivorshipStoreError(f"{source_dir}: the source store does not verify: {exc}") from exc
    if data.purpose is not None:
        raise SurvivorshipStoreError(
            f"{source_dir}: the source is itself a {data.purpose!r} store; build from the dev store"
        )
    sessions = dates.sessions(research.STORE_START, research.DEV_END)
    member_window = [d for d in sessions if d >= research.MEMBERSHIP_START]
    intervals = data.market.membership.intervals
    extra = extra_sources or {}
    cleaned: dict[str, sv.Cleaned] = {}
    for symbol in sorted(data.unserved):
        days = sv.member_sessions(intervals, symbol, member_window)
        candidates: list[sv.Cleaned] = []
        primary = sv.read_series(cache, symbol)
        if primary is not None:
            candidates.append(sv.clean_symbol(primary, days, sessions))
        for series in extra.get(symbol, ()):
            candidates.append(sv.clean_symbol(series, days, sessions))
        cleaned[symbol] = (
            sv.best_of(candidates)
            if candidates
            else sv.Cleaned(
                symbol=symbol, source=sv.EODHD_SOURCE, code=sv.eodhd_code(symbol),
                action=sv.DROPPED, reason="never fetched into the EODHD cache",
                member_days=len(days),
            )
        )
        log.debug("survivorship: %s %s %s", symbol, cleaned[symbol].action, cleaned[symbol].reason)

    members = sorted({s for s, _, _ in intervals} - set(research.RESEARCH_ETFS))
    member_days = {s: sv.member_sessions(intervals, s, member_window) for s in members}
    before = {s: h.dates for s, h in data.market.history.items()}
    after = dict(before)
    for s, c in cleaned.items():
        if c.bars:
            after[s] = np.array([b.date for b in c.bars], dtype="datetime64[D]")
    coverage = sv.coverage_by_year(member_days, before, after)
    missing: list[tuple[str, int, str]] = []
    for s in members:
        days = member_days[s]
        if not days:
            continue
        have = after.get(s)
        if have is not None and bool(np.isin(np.array(days, dtype="datetime64[D]"), have).any()):
            continue
        why = cleaned[s].reason if s in cleaned else "the source store has bars but none on a member day"
        missing.append((s, len(days), why))
    return BuildPlan(
        source_dir=source_dir,
        source_manifest=dict(data.manifest),
        source_price_fingerprint=data.price_fingerprint,
        cleaned=cleaned,
        source_dividends=data.dividends,
        coverage=coverage,
        missing=tuple(missing),
    )


# ---- reports -------------------------------------------------------------------------------


def cleaning_report(plan: BuildPlan) -> str:
    """``cleaning_report.csv``: one row per symbol the source could not serve, sorted."""
    lines = [sv.REPORT_HEADER, *(plan.cleaned[s].report_line() for s in sorted(plan.cleaned))]
    return "\n".join(lines) + "\n"


def coverage_report(plan: BuildPlan) -> str:
    """``coverage_report.txt``: plain text, deterministic (no timestamps), LF."""
    lines = [
        "Survivorship-check store: member-day coverage over the dev window",
        f"source store: price fingerprint {plan.source_price_fingerprint}",
        "member-days: sessions 1996-01-02..2015-10-16 on which a symbol was an S&P 500 or "
        "Nasdaq-100 member (ETFs excluded)",
        "before: the dev store has a bar that day; after: this store has one",
        "",
        f"{'year':>4}  {'member-days':>11}  {'before':>7}  {'after':>7}",
    ]
    total = [0, 0, 0]
    for y in plan.coverage:
        lines.append(
            f"{y.year:>4}  {y.member_days:>11}  {y.before / y.member_days:>7.1%}  {y.after / y.member_days:>7.1%}"
        )
        total[0] += y.member_days
        total[1] += y.before
        total[2] += y.after
    if total[0]:
        lines.append(f"{'all':>4}  {total[0]:>11}  {total[1] / total[0]:>7.1%}  {total[2] / total[0]:>7.1%}")
    lines += ["", f"Cleaning of the {len(plan.cleaned)} symbols the dev store could not serve:"]
    for action in sv.ACTIONS:
        group = [c for c in plan.cleaned.values() if c.action == action]
        lines.append(
            f"  {action:<9} {len(group):>4} symbols, {sum(c.covered_days for c in group):>8} member-days covered, "
            f"{sum(len(c.bars) for c in group):>8} bars, {sum(len(c.dividends) for c in group):>6} dividends"
        )
    lines += [
        "",
        f"Members still missing (no bar on any member day): {len(plan.missing)}, "
        f"{sum(n for _, n, _ in plan.missing)} member-days",
    ]
    lines += [f"  {s:<8} {n:>5}  {why}" for s, n, why in plan.missing]
    return "\n".join(lines) + "\n"


# ---- writing -------------------------------------------------------------------------------


def _refuse_out(out: Path, source_dir: Path) -> None:
    out = Path(out)
    if out.is_symlink():
        raise SurvivorshipStoreError(f"{out} is a symlink; pass the real directory (os.replace would move the link)")
    resolved = out.resolve()
    forbidden = {Path(source_dir).resolve(), research.STORE_DIR.resolve(), research.TEST_STORE_DIR.resolve()}
    if resolved in forbidden:
        raise SurvivorshipStoreError(f"{out} is the source, dev or test store; the survivorship-check store needs its own directory")
    if out.exists() and (out / research.MANIFEST_FILE).is_file():
        try:
            purpose = research.declared_purpose(out)
        except ValueError:
            purpose = None
        if purpose != research.SURVIVORSHIP_PURPOSE:
            raise SurvivorshipStoreError(
                f"{out} already holds a store that is not a survivorship-check store; refusing to replace it"
            )


def _copy_checked(src: Path, dst: Path, digest: str) -> None:
    shutil.copyfile(src, dst)
    copied = research.file_sha256(dst)
    if copied != digest:
        raise SurvivorshipStoreError(f"{src.name}: the copy hashes {copied}, the verified source {digest}")


def _data_lines(path: Path):
    with path.open(encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            yield line.rstrip("\n")


def write_store(
    plan: BuildPlan,
    out: Path,
    cache: Path,
    *,
    data_dir: Path | None = None,
    extra_reports: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Write the store ``plan`` describes at ``out``; return its manifest.

    ``extra_reports`` are further ``name -> text`` files written inside the store and outside the
    manifest (phase 2's ``alias_report.csv``). Built in ``<out>.tmp``, verified with
    ``research.load_store``, then swapped in; on any failure nothing at ``out`` changes.
    """
    out = Path(out)
    source = plan.source_dir
    _refuse_out(out, source)
    files = plan.source_manifest["files"]
    added = plan.added
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    try:
        bar_rows = 0
        with (tmp / research.BARS_FILE).open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(research.BARS_HEADER + "\n")
            new = {s: [sv.bar_line(s, b) for b in c.bars] for s, c in added.items()}
            for line in sv.merge_sorted_lines(_data_lines(source / research.BARS_FILE), new):
                fh.write(line + "\n")
                bar_rows += 1
        new_divs = {
            s: [f"{s},{d.isoformat()},{sv.amount_text(a)}" for d, a in c.dividends]
            for s, c in added.items() if c.dividends
        }
        dividend_lines = list(sv.merge_sorted_lines(_data_lines(source / research.DIVIDENDS_FILE), new_divs))
        research._write_text(tmp / research.DIVIDENDS_FILE, research.DIVIDENDS_HEADER, dividend_lines)
        _copy_checked(source / research.FX_FILE, tmp / research.FX_FILE, files[research.FX_FILE])
        unserved = plan.still_unserved
        research._write_text(
            tmp / research.UNSERVED_FILE,
            research.UNSERVED_HEADER,
            [f"{s},no usable EODHD series: {sv.report_text(c.reason)}" for s, c in unserved.items()],
        )
        extra_files: list[str] = []
        for name in research.OPTIONAL_DATA_FILES:
            if name == research.ANNOUNCEMENTS_FILE or name not in files:
                continue
            _copy_checked(source / name, tmp / name, files[name])
            extra_files.append(name)
        merged: dict[str, dict[date, Any]] = {s: dict(v) for s, v in plan.source_dividends.items()}
        for s, c in added.items():
            if c.dividends:
                merged[s] = dict(c.dividends)
        dividends_cache = Path(cache) / "dividends"
        if dividends_cache.is_dir():
            vendor = read_cache(dividends_cache, sorted(merged))
            match = da.match(merged, vendor, skip=research.RESEARCH_ETFS, years=(1996, research.DEV_END.year))
            research._write_text(
                tmp / research.ANNOUNCEMENTS_FILE,
                research.ANNOUNCEMENTS_HEADER,
                research.announcement_lines(match.rows, merged),
            )
            extra_files.append(research.ANNOUNCEMENTS_FILE)
        elif research.ANNOUNCEMENTS_FILE in files:
            _copy_checked(source / research.ANNOUNCEMENTS_FILE, tmp / research.ANNOUNCEMENTS_FILE, files[research.ANNOUNCEMENTS_FILE])
            extra_files.append(research.ANNOUNCEMENTS_FILE)
        counts = {
            "bar_rows": bar_rows,
            "dividend_rows": len(dividend_lines),
            "fx_rows": int(plan.source_manifest["fx_rows"]),
            "symbols_requested": int(plan.source_manifest["symbols_requested"]),
            "symbols_served": int(plan.source_manifest["symbols_served"]) + len(added),
        }
        manifest = research._seal(
            tmp, counts,
            extra_files=tuple(n for n in research.OPTIONAL_DATA_FILES if n in extra_files),
            window=research.DEV_WINDOW,
            purpose=research.SURVIVORSHIP_PURPOSE,
        )
        reports = {CLEANING_REPORT: cleaning_report(plan), COVERAGE_REPORT: coverage_report(plan), **(extra_reports or {})}
        for name, text in reports.items():
            if name in manifest["files"] or name == research.MANIFEST_FILE:
                raise SurvivorshipStoreError(f"{name} is a store file, not a report")
            (tmp / name).write_text(text, encoding="utf-8", newline="\n")
        try:
            built = research.load_store(tmp, data_dir=data_dir)
        except ValueError as exc:
            raise SurvivorshipStoreError(f"the built store does not load: {exc}") from exc
        if built.purpose != research.SURVIVORSHIP_PURPOSE:
            raise SurvivorshipStoreError("the built store lost its purpose mark")
        if added and built.price_fingerprint == plan.source_price_fingerprint:
            raise SurvivorshipStoreError("the built store has the source's price fingerprint although bars were added")
        del built
        research._swap_in(tmp, out)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    log.info(
        "survivorship: store %s built: %d symbols added, %d still unserved, %d bar rows, price fingerprint %s",
        out, len(added), len(plan.still_unserved), bar_rows, research.price_fingerprint_of(manifest["files"]),
    )
    return manifest


# ---- the command ---------------------------------------------------------------------------


def _print_store_reports(out: Path) -> int:
    try:
        purpose = research.declared_purpose(out)
    except ValueError as exc:
        print(f"survivorship_store: {exc}")
        return 2
    if purpose != research.SURVIVORSHIP_PURPOSE:
        print(f"survivorship_store: {out} is not a survivorship-check store")
        return 2
    report = out / COVERAGE_REPORT
    if not report.is_file():
        print(f"survivorship_store: {out} has no {COVERAGE_REPORT}")
        return 2
    print(report.read_text(encoding="utf-8"), end="")
    return 0


def run(args: argparse.Namespace) -> int:
    out = Path(args.out)
    if args.report:
        return _print_store_reports(out)
    try:
        plan = plan_build(Path(args.source), Path(args.cache))
    except SurvivorshipStoreError as exc:
        print(f"survivorship_store: {exc}")
        return 2
    print(coverage_report(plan), end="")
    if not args.build:
        print(f"\nnothing written; pass --build to write {out}")
        return 0
    if getattr(args, "dry_run", False):
        print(f"\ndry run: would write {len(plan.added)} added symbols into {out}")
        return 0
    try:
        manifest = write_store(plan, out, Path(args.cache))
    except SurvivorshipStoreError as exc:
        print(f"survivorship_store: {exc}")
        return 2
    print(
        f"\nwrote {out}: {manifest['symbols_served']} of {manifest['symbols_requested']} symbols served, "
        f"{manifest['bar_rows']} bar rows, price fingerprint {research.price_fingerprint_of(manifest['files'])}, "
        f"purpose {manifest[research.PURPOSE_KEY]!r}"
    )
    return 0
