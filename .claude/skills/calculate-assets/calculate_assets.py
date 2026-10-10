#!/usr/bin/env python3
"""What the owner's money would have done, had he started on a given date.

    python3 calculate_assets.py M0007-N20-RAW 16-4-2018 [31-12-2025]

Runs one lab method the way the owner really trades -- fractional shares at Gotrade's measured
fee schedule, 10,000,000 IDR to open and 5,000,000 IDR on the 25th of every month -- over an
arbitrary window inside the test-window research store, and reports what the money did.

Three things this deliberately does NOT do:

1. **It never connects to the lab database.** ``lab`` commands migrate ``lab.sqlite`` on connect,
   so even a read dirties the file. Methods and candidates come from ``lab.method.discover()``,
   which reads the committed method files on disk, and nothing here opens the database at all.
2. **It records nothing.** No trial, no observation, no status move, no pre-registration. This is
   a report, in the sense ``lab costs`` is a report.
3. **It prints no gate numbers.** No DSR, no eligibility, no owner conditions, no failure labels.
   The window it reads is the held-out one; the owner chose to see what the money did without the
   diagnostics that would let him tune a method against it.

The headline is the MONEY-WEIGHTED return, never CAGR. ``dev._funded_stats`` says why in so many
words: on a book fed monthly deposits, CAGR "counts the owner's own deposits as growth, which is
the +600.9% lie". ``Metrics.mwr`` is the rate a savings account would have had to pay to turn the
same deposits, paid in on the same days, into the same final balance -- which is the question.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import numpy as np
from seer_engine import dates, research
from seer_engine.backtest import dev
from seer_engine.backtest.benchmark import spy_curves
from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import Market
from seer_engine.backtest.metrics import money_weighted_return
from seer_engine.lab import runner
from seer_engine.lab import store as lab_store
from seer_engine.lab.method import discover
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine.sim.rules import (
    MONTHLY_HOLD_FRAC_GOTRADE,
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
)
from seer_engine.strategies.allocator import prepare_for
from seer_engine.strategies.base import History

OPENING_IDR = Decimal(10000000)  # == backtest.runner.INITIAL_IDR, the run's default

# A cadence's realistic twin: fractional shares at Gotrade's real fees. Keyed by the rule-set id
# a recorded variant might carry, so a flat whole-share variant maps onto the book the owner
# actually trades. A rule set already in this table's values is left alone.
REALISTIC: dict[str, object] = {
    "monthly-hold": MONTHLY_HOLD_FRAC_GOTRADE,
    "monthly-hold-frac": MONTHLY_HOLD_FRAC_GOTRADE,
    "monthly-hold-frac-gotrade": MONTHLY_HOLD_FRAC_GOTRADE,
    "monthly-rank-weekly-resize": MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
    "monthly-rank-weekly-resize-frac": MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
    "monthly-rank-weekly-resize-frac-gotrade": MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
}


class Refused(Exception):
    """A reason this cannot be answered, in words the owner can act on."""


# --------------------------------------------------------------------------- arguments


def parse_dmy(text: str, what: str) -> date:
    """``16-4-2018`` -> ``date(2018, 4, 16)``. Day first: it is how the owner writes a date."""
    parts = text.replace("/", "-").split("-")
    if len(parts) != 3:
        raise Refused(f"{what} {text!r} is not a date; write it day-month-year, like 16-4-2018")
    try:
        day, month, year = (int(p) for p in parts)
    except ValueError:
        raise Refused(f"{what} {text!r} is not a date; write it day-month-year, like 16-4-2018")
    if year < 100:
        raise Refused(f"{what} {text!r} needs a four-digit year, like 16-4-2018")
    try:
        return date(year, month, day)
    except ValueError as e:
        raise Refused(f"{what} {text!r} is not a real date ({e})")


def parse_target(text: str) -> str:
    """A candidate id, a bare method id, or a seertrade.site method URL -> the id to resolve."""
    text = text.strip()
    if "seertrade.site" in text or text.startswith("http"):
        tail = text.rstrip("/").rsplit("/", 1)[-1]
        if not tail:
            raise Refused(f"{text!r} has no method id at the end of it")
        return tail.upper()
    return text.upper()


# --------------------------------------------------------------------------- what to run


def resolve(target: str) -> tuple[str, Candidate]:
    """``(method id, the Candidate to run)``, from the committed method files only."""
    methods = discover()
    if "-" in target:
        try:
            method, _path, candidate = runner.resolve_candidate(target)
        except lab_store.LabError as e:
            raise Refused(str(e))
        return method.id, candidate
    if target not in methods:
        raise Refused(
            f"no method file for {target} in seer_engine/lab/methods/. Known: "
            f"{', '.join(sorted(methods)) or '(none)'}"
        )
    method, _path = methods[target]
    if not method.candidates:
        raise Refused(f"{target} has no variants to run")
    if len(method.candidates) > 1:
        names = ", ".join(c.id for c in method.candidates)
        raise Refused(
            f"{target} has {len(method.candidates)} variants and this asks about one book of "
            f"money, not a family. Name the one you mean: {names}"
        )
    return method.id, method.candidates[0]


def registered_twin(candidate: Candidate) -> tuple[str, Candidate] | None:
    """A committed method whose variant IS ``candidate`` run realistically, if one exists.

    M0032 is exactly this for M0007-N20-RAW: the same allocator and the same parameters on
    ``monthly-hold-frac-gotrade``. Using it by name beats building a lookalike, because the twin
    was pre-registered -- somebody wrote down in advance what it was expected to do.
    """
    want = (candidate.allocator.id, candidate.params)
    for method_id, (method, _path) in sorted(discover().items()):
        for c in method.candidates:
            if c.id == candidate.id:
                continue
            if (c.allocator.id, c.params) != want:
                continue
            if getattr(c.rules, "cost_model", "flat") == "gotrade" and c.rules.fractional:
                return method_id, c
    return None


def realistic(candidate: Candidate) -> tuple[Candidate, str]:
    """``candidate`` with fractional shares and Gotrade's real fees, and a line saying what moved."""
    rules = candidate.rules
    if rules.engine != "book":
        raise Refused(
            f"{candidate.id} runs on the {rules.engine} engine, which has no real-fee model. "
            f"This asks what the owner would really have paid, so there is no honest answer for it"
        )
    want = REALISTIC.get(rules.id)
    if want is None:
        raise Refused(
            f"{candidate.id} runs on {rules.id!r}, which has no fractional Gotrade preset. "
            f"Known: {', '.join(sorted(REALISTIC))}"
        )
    if rules.id == want.id:
        return candidate, f"{candidate.id} already trades the way the owner does ({rules.id})."
    twin = registered_twin(replace(candidate, rules=want))
    if twin is not None:
        method_id, c = twin
        return c, (
            f"{candidate.id} is the lab's flat-fee, whole-share record. Its realistic twin is "
            f"already registered as {c.id} ({method_id}) -- the same allocator and the same "
            f"parameters on {c.rules.id} -- so that is what runs."
        )
    return replace(candidate, id=f"{candidate.id}-REAL", rules=want), (
        f"{candidate.id} recorded at {rules.id}; run here at {want.id} "
        f"(fractional shares, Gotrade's real fees). No registered twin exists, so this is "
        f"{candidate.id}'s configuration with the rule set swapped, and nothing else."
    )


# --------------------------------------------------------------------------- the data


def load(store_dir: Path) -> research.ResearchData:
    """The test-window store, loaded the way ``lab test`` loads it."""
    if not store_dir.exists():
        raise Refused(
            f"the test-window research store {store_dir} does not exist. Build it with\n"
            f"    python -m seer_engine research_store --test-window --with-fundamentals\n"
            f"It takes about half an hour and a yfinance crawl, and it is also what `lab test` "
            f"needs, so it is not throwaway work."
        )
    try:
        declared = research.declared_window(store_dir)
    except (ValueError, FileNotFoundError) as e:
        raise Refused(f"{store_dir}: {e}")
    if declared.name != "test":
        raise Refused(
            f"{store_dir} declares the {declared.name} window, which stops at "
            f"{declared.end}. A question about 2018 needs the test-window store: build it with "
            f"`python -m seer_engine research_store --test-window --with-fundamentals`"
        )
    try:
        return research.load_store(store_dir, window=declared)
    except (ValueError, FileNotFoundError) as e:
        raise Refused(f"{store_dir}: {e}")


def _truncate_history(h: History, end: date) -> History:
    """``h`` without its bars dated after ``end`` (as if they had not happened yet)."""
    cut = int(np.searchsorted(h.dates, np.datetime64(end, "D"), side="right"))
    return History(h.symbol, h.dates[:cut], h.open[:cut], h.high[:cut], h.low[:cut],
                   h.close[:cut], h.volume[:cut])


def truncate(data: research.ResearchData, end: date) -> tuple[Market, dict, tuple]:
    """``data``'s market, dividends and SPY dividends with nothing dated after ``end``.

    ``dev._check_market`` refuses a market holding data after the window's end -- the D9 rule that
    keeps a run from seeing its own future -- so an end date earlier than the store's last session
    has to be cut here rather than merely asked for.
    """
    if end >= data.window.end:
        return data.market, data.dividends, data.spy_dividends
    market = replace(
        data.market,
        history={s: _truncate_history(h, end) for s, h in data.market.history.items()},
        fx=tuple((d, r) for d, r in data.market.fx if d <= end),
    )
    dividends = {
        s: {d: a for d, a in per.items() if d <= end} for s, per in data.dividends.items()
    }
    spy_divs = tuple(d for d in data.spy_dividends if d.ex_date <= end)
    return market, dividends, spy_divs


# --------------------------------------------------------------------------- the runs


def run_once(market, dividends, spy_divs, candidate, window, *, real_fx: bool):
    """One funded run. ``real_fx`` converts each deposit at the rate of the day it is credited.

    ``prepared`` is what ``dev.run_registry`` hands every candidate -- ``prepare_for``, the
    ``MarketAware`` path. Without it the book runner falls back to ``targets``, the history-only
    path, where a dividend-calendar or fundamentals allocator sees no calendar and no panel and
    targets nothing: the run completes, 0 trades, and the deposits sit in cash, silently.
    """
    return dev.run_candidate(
        market,
        dividends,
        spy_divs,
        candidate,
        prepared=prepare_for(candidate.allocator, market),
        window=window,
        contributions=OWNER_MONTHLY,
        contribution_fx=market.usd_idr_on if real_fx else None,
    )


# --------------------------------------------------------------------------- the money


def credited_idr(start: date, end: date) -> tuple[tuple[date, float], ...]:
    """``(session, rupiah)`` per credited deposit -- ``book_runner``'s own crediting loop.

    Mirrors the runner rather than guessing: a contribution dated ``d`` is credited at the first
    NYSE session on or after ``d``, which the runner gets by asking ``due(previous session, this
    session)`` once per session. Reproducing that here is what makes the rupiah IRR below measure
    the same deposits, on the same days, that the book actually received.
    """
    per: dict[date, Decimal] = {}
    data_date = dates.prev_session(start)
    for session in dates.sessions(start, end):
        due = OWNER_MONTHLY.due(data_date, session)
        if due:
            per[session] = per.get(session, Decimal(0)) + OWNER_MONTHLY.amount_idr * len(due)
        data_date = session
    return tuple((d, float(a)) for d, a in sorted(per.items()))


def rupiah_return(curve, flows) -> float | None:
    """The money-weighted return of an IDR curve fed IDR deposits.

    The engine's own ``mwr`` is measured on the USD book, so it cannot see the rupiah: it would
    read a return in dollars beside a balance in rupiah, and the two would disagree by however
    far USD/IDR moved. The owner deposits rupiah and ends with rupiah, so the rate that answers
    his question is the one taken over the rupiah.
    """
    return money_weighted_return(curve, flows)


def deposits_idr(start: date, end: date) -> tuple[int, Decimal]:
    """``(how many deposits, total rupiah in)`` -- the opening sum plus every 25th in the window."""
    paid = OWNER_MONTHLY.dates_in(start, end)
    return len(paid), OPENING_IDR + OWNER_MONTHLY.amount_idr * len(paid)


def rupiah(amount: Decimal | float) -> str:
    """``1234567890`` -> ``Rp 1,234,567,890``."""
    return f"Rp {round(float(amount)):,}"


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:+.1f}%"


def fall(x: float | None) -> str:
    """A drawdown, unsigned. It is a fall, and ``+32.7%`` reads like a gain."""
    return "n/a" if x is None else f"{abs(x) * 100:.1f}%"


def curve_idr(points, rate_on, fixed: Decimal | None):
    """``[(date, rupiah)]`` from ``[(date, usd)]``, at the day's rate or at one fixed rate."""
    return [
        (d, float(Decimal(str(usd)) * (fixed if fixed is not None else rate_on(d))))
        for d, usd in points
    ]


def pin_open(points):
    """``points`` with its opening mark set to the rupiah that actually opened the account.

    Snapshot zero is dated the session BEFORE the window, so converting it at that day's rate
    prices the opening sum at a rate the money never saw -- it was converted at
    ``usd_idr_on(start)``. Left alone it read 10,049,936 where 10,000,000 went in, and that half
    a percent lands in the IRR as a return nobody earned.
    """
    return [(points[0][0], float(OPENING_IDR)), *points[1:]] if points else points


def monthly(points):
    """One point per calendar month (its last), plus the final point: enough for a chart."""
    out, seen = [], None
    for i, (d, v) in enumerate(points):
        key = (d.year, d.month)
        if seen is not None and key != seen:
            out.append(points[i - 1])
        seen = key
    if points:
        out.append(points[-1])
    return out


# --------------------------------------------------------------------------- the report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("method", help="a candidate id (M0007-N20-RAW), a method id, or a method URL")
    p.add_argument("start", help="the day the money started, day-month-year (16-4-2018)")
    p.add_argument("end", nargs="?", default=None, help="day-month-year; default: the store's last session")
    p.add_argument("--store", type=Path, default=research.TEST_STORE_DIR)
    p.add_argument("--out", type=Path, default=None, help="write the chart's data here as JSON")
    args = p.parse_args(argv)

    try:
        start = parse_dmy(args.start, "the start date")
        end_asked = parse_dmy(args.end, "the end date") if args.end else None
        method_id, recorded = resolve(parse_target(args.method))
        candidate, swap = realistic(recorded)

        data = load(args.store)
        end = end_asked or data.window.end
        if end > data.window.end:
            raise Refused(
                f"the store's last session is {data.window.end}; it cannot answer for {end}. "
                f"Rebuild it to extend the data: "
                f"`python -m seer_engine research_store --test-window --with-fundamentals`"
            )
        if start < data.window.start:
            raise Refused(
                f"the test window opens on {data.window.start} and this asks from {start}. "
                f"Earlier than that is the dev window, which every method here was BUILT on -- "
                f"a result there would be the method marking its own homework."
            )
        if end <= start:
            raise Refused(f"the end date {end} is not after the start date {start}")

        market, dividends, spy_divs = truncate(data, end)
        window = replace(data.window, start=start, end=end)

        print(f"{swap}\n", file=sys.stderr)
        print(f"Running {candidate.id} from {start} to {end} ...", file=sys.stderr)
        real_res, real_row = run_once(market, dividends, spy_divs, candidate, window, real_fx=True)
        print("  real-rupiah run done; now the fixed-rate one ...", file=sys.stderr)
        fixed_res, _fixed_row = run_once(market, dividends, spy_divs, candidate, window, real_fx=False)
        print("  done.\n", file=sys.stderr)
    except Refused as e:
        print(f"\n{e}\n", file=sys.stderr)
        return 2

    ran_from, ran_to = real_row.start, real_row.end
    n_deposits, total_in = deposits_idr(ran_from, ran_to)
    open_rate = real_res.usd_idr
    end_rate = market.usd_idr_on(ran_to)

    # The book, in rupiah, two ways; and the SPY fed the identical dollars on the identical days.
    real_curve = [(s.date, float(s.equity_usd)) for s in real_res.snapshots]
    fixed_curve = [(s.date, float(s.equity_usd)) for s in fixed_res.snapshots]
    _price, spy_total = spy_curves(
        market.spy(), ran_from, ran_to, real_res.initial_cash, spy_divs,
        cost_model=candidate.rules.cost_model, contributions=real_res.cashflows,
    )
    spy_curve = [(s.date, float(s.equity_usd)) for s in spy_total.snapshots]

    book_real = pin_open(curve_idr(real_curve, market.usd_idr_on, None))
    book_fixed = pin_open(curve_idr(fixed_curve, None, open_rate))
    spy_real = pin_open(curve_idr(spy_curve, market.usd_idr_on, None))
    paid_in = OWNER_MONTHLY.dates_in(ran_from, ran_to)
    deposited = [
        (d, float(OPENING_IDR + OWNER_MONTHLY.amount_idr * sum(1 for x in paid_in if x <= d)))
        for d, _ in real_curve
    ]

    end_book_real = book_real[-1][1]
    end_book_fixed = book_fixed[-1][1]
    end_spy = spy_real[-1][1]
    years = (ran_to - ran_from).days / 365.25

    # Every rate below is taken over the rupiah, against the rupiah that left the owner's bank.
    flows = credited_idr(ran_from, ran_to)
    r_book_real = rupiah_return(book_real, flows)
    r_book_fixed = rupiah_return(book_fixed, flows)
    r_spy = rupiah_return(spy_real, flows)

    print(f"  {candidate.id}   {ran_from} to {ran_to}   ({years:.1f} years)")
    print(f"  10,000,000 to open, then 5,000,000 on the 25th: {n_deposits} deposits\n")
    print(f"  {'you paid in':<34}{rupiah(total_in):>22}")
    print(f"  {'your book, at real rupiah rates':<34}{rupiah(end_book_real):>22}   "
          f"{pct(r_book_real)} a year")
    print(f"  {'the same deposits into SPY':<34}{rupiah(end_spy):>22}   "
          f"{pct(r_spy)} a year")
    print(f"  {'your book, at a frozen rupiah':<34}{rupiah(end_book_fixed):>22}   "
          f"{pct(r_book_fixed)} a year")
    print(f"\n  {'what the rupiah added':<34}{rupiah(end_book_real - end_book_fixed):>22}   "
          f"(USD/IDR {open_rate:,.0f} -> {end_rate:,.0f})")
    print(f"  {'what the strategy added over SPY':<34}{rupiah(end_book_real - end_spy):>22}")
    print(f"  {'what you earned over what you paid':<34}{rupiah(end_book_real - float(total_in)):>22}")
    print(f"\n  deepest fall along the way: {fall(real_row.stats.metrics.max_drawdown)} "
          f"-- read it gently: monthly deposits keep topping the account up, so a fall\n"
          f"  reads shallower here than the same fall would on money that just sat there.")
    print(f"  {real_row.stats.metrics.trades} trades. Returns are money-weighted: the rate a "
          f"savings account would have\n  had to pay on the same deposits, on the same days, to "
          f"reach the same balance -- taken over\n  the rupiah, which is the currency you "
          f"actually deposit and actually end with.")

    if args.out:
        args.out.write_text(json.dumps({
            "candidate": candidate.id,
            "method": method_id,
            "swap": swap,
            "start": ran_from.isoformat(),
            "end": ran_to.isoformat(),
            "years": years,
            "deposits": n_deposits,
            "total_in_idr": float(total_in),
            "open_rate": float(open_rate),
            "end_rate": float(end_rate),
            "end_book_real_idr": end_book_real,
            "end_book_fixed_idr": end_book_fixed,
            "end_spy_idr": end_spy,
            "mwr_book_real": r_book_real,
            "mwr_book_fixed": r_book_fixed,
            "mwr_spy": r_spy,
            "mwr_book_usd": real_row.stats.metrics.mwr,
            "mwr_spy_usd": real_row.spy_tr.mwr,
            "max_drawdown": real_row.stats.metrics.max_drawdown,
            "trades": real_row.stats.metrics.trades,
            "series": {
                "book_real": [(d.isoformat(), v) for d, v in monthly(book_real)],
                "book_fixed": [(d.isoformat(), v) for d, v in monthly(book_fixed)],
                "spy": [(d.isoformat(), v) for d, v in monthly(spy_real)],
                "deposited": [(d.isoformat(), v) for d, v in monthly(deposited)],
            },
        }, indent=2))
        print(f"\n  chart data: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
