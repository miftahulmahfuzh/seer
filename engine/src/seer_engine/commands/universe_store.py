"""``universe_store --build``: a research store whose universe is a dollar-volume rank band.

**Why a second kind of store.** Every lab method so far ranks the twenty most-traded members of
the S&P 500 or the Nasdaq-100. That universe is large caps by construction, and after 81 methods
the lab has shown what it can produce: the books it would actually test correlate 0.93-0.96 with
books that already spent a test look and failed. The constraint is the universe, not the rules
guarding it -- so this builds the other universe, from EODHD history for every US common stock
that ever held a dollar-volume rank inside the band, the dead ones included.

**Where each piece comes from, and why almost nothing here is new.**

* membership -- ``universe_rank``: point-in-time intervals from 214 month-end rank cross-sections.
  There is no index to read for a liquidity band, which is the one thing the index store's
  machinery cannot supply.
* cleaning -- ``survivorship.clean_symbol``, unchanged: split-adjust, drop zero-volume filler
  rows, repair or trim absurd prices, keep real collapses. Those rules were calibrated on a real
  EODHD cache and are the reason this command is short.
* sealing -- ``research._seal`` with ``UNIVERSE_PURPOSE``, so ``lab run``/``lab test`` refuse the
  store outright and a trial measured here can never join a method whose other trials were
  measured on the index store.

**What this store does NOT have: fundamentals.** The EDGAR panel is keyed to the index universe
and starts in 2009 regardless, so a method built here is a price-and-volume method. That is a
constraint on what may be asked of it, not a defect -- and it is why ``fundamentals.csv`` is
absent rather than empty.

**The benchmark and the research ETFs are pulled from EODHD too**, not carried over from the dev
store, so every price in this store comes from one vendor and the price fingerprint means what it
says.
"""

from __future__ import annotations

import argparse
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

from seer_engine import dates, research, survivorship as sv, universe_rank as ur

log = logging.getLogger(__name__)

#: First sample of the month-end sweep; membership cannot begin before the lab can see a rank.
UNIVERSE_START = date(1998, 1, 31)

DEFAULT_CACHE = "engine/.cache/eodhd-universe"
DEFAULT_RANKS = "engine/.cache/eodhd-bulk/monthend_dollar_volume.csv"
DEFAULT_OUT = "engine/.research-dv"


class UniverseStoreError(RuntimeError):
    """A refusal this command makes before writing anything."""


@dataclass(frozen=True, slots=True)
class BuildPlan:
    intervals: list[tuple[str, str, date, date | None]]
    symbols: list[str]
    etfs: tuple[str, ...]
    sessions: list[date]
    band: tuple[int, int] = (1, 2000)
    cleaned: list[sv.Cleaned] = field(default_factory=list)


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--build", action="store_true", help="write the store at --out")
    p.add_argument("--out", default=DEFAULT_OUT, help=f"store to write (default {DEFAULT_OUT})")
    p.add_argument("--cache", default=DEFAULT_CACHE, help=f"EODHD cache (default {DEFAULT_CACHE})")
    p.add_argument("--ranks", default=DEFAULT_RANKS, help=f"month-end rank CSV (default {DEFAULT_RANKS})")
    p.add_argument("--band", default="1-2000", help="dollar-volume rank band, inclusive (default 1-2000)")
    p.add_argument("--limit", type=int, default=0, help="build only the first N symbols (a smoke build)")


def _band(text: str) -> tuple[int, int]:
    lo, _, hi = text.partition("-")
    return int(lo), int(hi)


def plan_build(cache: Path, ranks: Path, band: tuple[int, int], limit: int = 0) -> BuildPlan:
    """Everything that needs no writing: membership, the symbol set, the session calendar."""
    if not ranks.is_file():
        raise UniverseStoreError(f"{ranks}: no month-end rank CSV; run the sweep first")
    if not (cache / "eod").is_dir():
        raise UniverseStoreError(f"{cache}: no eod/ directory; run the universe pull first")

    rows = ur.intervals(ur.read_samples(ranks), band=band)
    cached = {p.stem for p in (cache / "eod").glob("*.json")}
    ranked = sorted({sym for _i, sym, _s, _e in rows} & cached)
    missing_etfs = [e for e in research.RESEARCH_ETFS if e not in cached]
    if missing_etfs:
        raise UniverseStoreError(
            f"{cache}: the benchmark and research ETFs are not cached: {', '.join(missing_etfs)}. "
            f"A store without SPY has no benchmark and the lab cannot score anything on it"
        )
    if limit:
        # Trim RANKED names only. The ETFs are the benchmark and the regime series, not
        # candidates, and a smoke build of 40 that turned out to be 21 ETFs and 19 stocks would
        # exercise almost none of the cleaning this command exists to run.
        ranked = [s for s in ranked if s not in research.RESEARCH_ETFS][:limit]
    symbols = sorted(set(ranked) | set(research.RESEARCH_ETFS))
    sessions = dates.sessions(research.STORE_START, research.DEV_END)
    return BuildPlan(intervals=rows, symbols=symbols, etfs=research.RESEARCH_ETFS,
                     sessions=sessions, band=band)


def _member_days(plan: BuildPlan, symbol: str, window: Sequence[date]) -> tuple[date, ...]:
    """The sessions ``symbol`` was in the band. An ETF is a member whenever it is listed.

    The ETFs carry no rank membership -- they are the benchmark and the regime series, present so
    the store can be scored, not candidates to pick. Giving them the whole window would be wrong
    only if something ranked them, and nothing does.
    """
    if symbol in plan.etfs:
        return tuple(window)
    triples = [(s, start, end) for _i, s, start, end in plan.intervals if s == symbol]
    return sv.member_sessions(triples, symbol, window)


def clean_all(plan: BuildPlan, cache: Path) -> list[sv.Cleaned]:
    """Clean every symbol against its own membership. Never raises on bad vendor data."""
    window = [d for d in plan.sessions if d >= UNIVERSE_START]
    out: list[sv.Cleaned] = []
    for i, symbol in enumerate(plan.symbols, 1):
        series = sv.read_series(cache, symbol)
        if series is None:
            continue
        out.append(sv.clean_symbol(series, _member_days(plan, symbol, window), plan.sessions))
        if i % 500 == 0:
            log.info("universe: cleaned %d/%d symbols", i, len(plan.symbols))
    return out


def coverage_report(plan: BuildPlan, cleaned: Sequence[sv.Cleaned]) -> str:
    kept = [c for c in cleaned if c.action != sv.DROPPED]
    by_action: dict[str, int] = defaultdict(int)
    for c in cleaned:
        by_action[c.action] += 1
    bars = sum(len(c.bars) for c in kept)
    lines = [
        "Dollar-volume universe store",
        "",
        f"band             rank {plan.band[0]}-{plan.band[1]}",
        f"symbols offered  {len(plan.symbols)}",
        f"symbols served   {len(kept)}",
        f"bar rows         {bars}",
        "",
        "cleaning actions:",
        *(f"  {a:<10} {by_action[a]}" for a in (sv.KEPT, sv.REPAIRED, sv.TRIMMED, sv.DROPPED)),
        "",
        "Membership is point-in-time: a symbol is a member on the sessions following a month-end",
        "at which its dollar volume ranked inside the band, and leaves at the first month-end it",
        "does not. No persistence filter is applied, so the universe carries no information from",
        "the future.",
        "",
        "This store has NO fundamentals: the EDGAR panel is keyed to the index universe and starts",
        "in 2009, so a method built here is a price-and-volume method.",
    ]
    return "\n".join(lines) + "\n"


def write_store(plan: BuildPlan, cleaned: Sequence[sv.Cleaned], out: Path, source: Path) -> Mapping[str, Any]:
    """Write the store at ``out`` and return its manifest. Built in ``<out>.tmp``, then swapped."""
    kept = [c for c in cleaned if c.action != sv.DROPPED]
    tmp = out.with_suffix(out.suffix + ".tmp")
    if tmp.exists():
        raise UniverseStoreError(f"{tmp} exists; remove it or let the previous build finish")
    tmp.mkdir(parents=True)

    bar_lines = sorted(sv.bar_line(c.symbol, b) for c in kept for b in c.bars)
    div_lines = sorted(
        f"{c.symbol},{ex.isoformat()},{sv.amount_text(amount)}"
        for c in kept for ex, amount in c.dividends
    )
    research._write_text(tmp / research.BARS_FILE, research.BARS_HEADER, bar_lines)
    research._write_text(tmp / research.DIVIDENDS_FILE, research.DIVIDENDS_HEADER, div_lines)

    # fx and the market series describe the world, not the universe, so they are copied verbatim
    # from the dev store rather than re-derived -- re-deriving them would change their bytes for
    # no reason and make two stores disagree about the same dollar.
    fx_src = source / research.FX_FILE
    if not fx_src.is_file():
        raise UniverseStoreError(f"{fx_src}: the dev store has no fx.csv to copy")
    (tmp / research.FX_FILE).write_text(fx_src.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    fx_rows = max(sum(1 for _ in fx_src.open(encoding="utf-8")) - 1, 0)

    extra: list[str] = []
    ms_src = source / research.MARKET_SERIES_FILE
    if ms_src.is_file():
        (tmp / research.MARKET_SERIES_FILE).write_text(
            ms_src.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        extra.append(research.MARKET_SERIES_FILE)

    dropped = [c for c in cleaned if c.action == sv.DROPPED]
    research._write_text(
        tmp / research.UNSERVED_FILE, research.UNSERVED_HEADER,
        sorted(f"{c.symbol},{sv.report_text(c.reason)}" for c in dropped),
    )

    manifest = research._seal(
        tmp,
        {
            "bar_rows": len(bar_lines),
            "dividend_rows": len(div_lines),
            "fx_rows": fx_rows,
            "symbols_requested": len(plan.symbols),
            "symbols_served": len(kept),
        },
        extra_files=tuple(extra),
        purpose=research.UNIVERSE_PURPOSE,
    )
    (tmp / "coverage_report.txt").write_text(coverage_report(plan, cleaned), encoding="utf-8")

    built = research.load_store(tmp)
    if built.purpose != research.UNIVERSE_PURPOSE:
        raise UniverseStoreError("the built store lost its purpose mark")
    tmp.rename(out)
    return manifest


def run(args: argparse.Namespace) -> int:
    root = Path(__file__).resolve().parents[4]
    cache, ranks = root / args.cache, root / args.ranks
    out, source = root / args.out, root / "engine/.research"
    band = _band(args.band)
    plan = plan_build(cache, ranks, band, limit=args.limit)
    print(f"universe: band {band[0]}-{band[1]}, {len(plan.symbols)} symbols "
          f"({len(plan.intervals)} membership intervals)")
    if not args.build:
        print("dry plan only; pass --build to write the store")
        return 0
    cleaned = clean_all(plan, cache)
    manifest = write_store(plan, cleaned, out, source)
    print(f"wrote {out}: {manifest['symbols_served']} of {manifest['symbols_requested']} served, "
          f"{manifest['bar_rows']} bar rows, fingerprint {manifest['fingerprint']}")
    return 0
