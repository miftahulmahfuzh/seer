"""``universe_probe``: the same lab strategies, a different universe. A report, never a trial.

**The question this answers, and why it is asked before anything is pre-registered.** After 81
methods the index lab has nothing promotable, and the kin measurement says why: the books it would
actually test correlate 0.93-0.96 with books that already spent a test look and failed. The
universe -- twenty of the most-traded large caps -- is the binding constraint, not the rules. So
the obvious next move is to send the method lab at a different universe. The obvious next move is
also expensive: every setting tried counts toward N, and N is the denominator every DSR in the lab
is scored against.

This runs the *existing* methods, unchanged, on a store whose membership is a dollar-volume rank
band, and prints what happens. **No trial, no method id, no status, no journal row, no test
look.** It cannot move ``store.dev_trial_count`` or ``store.test_looks`` because it never opens
the lab for writing at all.

**Why drawdown is the column to read first.** Return was never the lab's problem: 65% of dev
trials beat SPY TR, and all four spent test looks failed on return. The *screen* drowns in
drawdown -- 77% of recorded dev trials already breach the 20% bar, and of the 28 variants that
clear it, 11 stop clearing it on survivorship-free prices. A universe worth pre-registering
against has to show a different **fall**, not merely a different return.

**What the band does, and why the store is built at 500-2000 rather than 1-2000.** The lab's
methods pick the top N by dollar volume of whatever is a member. On a 1-2000 store that is ranks
1-20 -- the same mega caps the lab already trades, so the probe would compare a universe with
itself. Restricting membership to 500-2000 makes the identical rule pick ranks ~500-520: the next
tier down, still liquid enough for a retail book at Gotrade's real fees, which rank 2000+ would
not be.
"""

from __future__ import annotations

import argparse
import importlib
import logging
import pkgutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from seer_engine import research
from seer_engine.backtest import dev

log = logging.getLogger(__name__)

#: Methods worth asking the question of first: the lab's plain dollar-volume book, its residual
#: momentum, its weekly-brake variant and the core-satellite blend. Between them they cover the
#: shapes the lab has actually found edge in.
DEFAULT_METHODS = ("M0007", "M0022", "M0030")

DEFAULT_BASE = "engine/.research"
DEFAULT_OTHER = "engine/.research-dv500"


@dataclass(frozen=True, slots=True)
class Row:
    store: str
    method: str
    candidate: str
    yearly: float | None
    drawdown: float | None
    profit_factor: float | None
    trades: int
    beats_spy: bool
    spy_yearly: float | None


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("methods", nargs="*", default=list(DEFAULT_METHODS),
                   help=f"method ids (default {' '.join(DEFAULT_METHODS)})")
    p.add_argument("--base", default=DEFAULT_BASE, help=f"store to compare against (default {DEFAULT_BASE})")
    p.add_argument("--other", default=DEFAULT_OTHER, help=f"store to probe (default {DEFAULT_OTHER})")
    p.add_argument("--csv", default="", help="also write the rows to this path")


def load_methods(ids: Sequence[str]) -> list[object]:
    """Every ``METHOD`` whose id is in ``ids``, discovered the way the lab discovers them."""
    import seer_engine.lab.methods as pkg
    want = {i.upper() for i in ids}
    out = []
    for info in pkgutil.iter_modules(pkg.__path__):
        mod = importlib.import_module(f"{pkg.__name__}.{info.name}")
        method = getattr(mod, "METHOD", None)
        if method is not None and getattr(method, "id", None) in want:
            out.append(method)
    found = {getattr(m, "id", None) for m in out}
    missing = sorted(want - found)
    if missing:
        raise SystemExit(f"no method file for: {', '.join(missing)}")
    return sorted(out, key=lambda m: m.id)


def measure(store_dir: Path, methods: Sequence[object], label: str) -> list[Row]:
    """Run every candidate of every method on one store. Loads it, measures, frees it."""
    t0 = time.perf_counter()
    data = research.load_store(store_dir)
    log.info("%s: loaded %s (%s, %.1fs)", label, str(data.fingerprint)[:12],
             data.purpose or "no purpose", time.perf_counter() - t0)
    rows: list[Row] = []
    try:
        for method in methods:
            cands = method.candidates() if callable(getattr(method, "candidates", None)) else method.candidates
            out = dev.run_registry(data.market, data.dividends, data.spy_dividends, list(cands))
            for r in out:
                m = r.stats.metrics
                rows.append(Row(
                    store=label, method=method.id, candidate=r.candidate.id,
                    yearly=m.cagr, drawdown=m.max_drawdown, profit_factor=m.profit_factor,
                    trades=m.trades, beats_spy=r.beats_spy, spy_yearly=r.spy_tr.cagr,
                ))
            log.info("%s: %s done (%d candidates)", label, method.id, len(out))
    finally:
        del data
    return rows


def _pct(x: float | None) -> str:
    return "     -" if x is None else f"{x * 100:6.2f}"


def format_report(base: list[Row], other: list[Row], base_label: str, other_label: str) -> str:
    by = {(r.method, r.candidate): r for r in base}
    lines = [
        f"Same strategies, two universes.  {base_label} vs {other_label}",
        "",
        "A REPORT: no trial, no method id, no status, no journal row, no test-window look.",
        "",
        f"{'candidate':26} {'yearly':>14} {'worst fall':>16} {'beats SPY':>12}",
        f"{'':26} {base_label:>6}{other_label:>8} {base_label:>7}{other_label:>9} "
        f"{base_label:>5}{other_label:>7}",
        "-" * 74,
    ]
    for r in other:
        b = by.get((r.method, r.candidate))
        lines.append(
            f"{r.candidate:26} {_pct(b.yearly if b else None)}{_pct(r.yearly)} "
            f"{_pct(b.drawdown if b else None)}{_pct(r.drawdown)} "
            f"{('yes' if b and b.beats_spy else 'no'):>5}{('yes' if r.beats_spy else 'no'):>7}"
        )
    spy_b = next((r.spy_yearly for r in base if r.spy_yearly is not None), None)
    spy_o = next((r.spy_yearly for r in other if r.spy_yearly is not None), None)
    lines += ["", f"SPY total return on the same window: {_pct(spy_b)} / {_pct(spy_o)} %/yr"]
    worse = sum(1 for r in other if (b := by.get((r.method, r.candidate)))
                and r.drawdown is not None and b.drawdown is not None and r.drawdown > b.drawdown)
    lines.append(f"variants whose worst fall is DEEPER on {other_label}: {worse} of {len(other)}")
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> int:
    root = Path(__file__).resolve().parents[4]
    methods = load_methods(args.methods)
    base_rows = measure(root / args.base, methods, "index")
    other_rows = measure(root / args.other, methods, "band")
    report = format_report(base_rows, other_rows, "index", "band")
    print(report)
    if args.csv:
        import csv as _csv
        p = root / args.csv
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = _csv.writer(fh)
            w.writerow(["store", "method", "candidate", "yearly", "max_drawdown",
                        "profit_factor", "trades", "beats_spy", "spy_yearly"])
            for r in [*base_rows, *other_rows]:
                w.writerow([r.store, r.method, r.candidate, r.yearly, r.drawdown,
                            r.profit_factor, r.trades, r.beats_spy, r.spy_yearly])
        print(f"wrote {p}")
    return 0
