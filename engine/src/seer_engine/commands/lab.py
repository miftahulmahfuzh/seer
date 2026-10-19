"""`lab`: the method lab (docs/plans/2026-10-04-method-lab-design.md).

    lab status                      N, the promotion path and what is promotable now, the
                                    test-window look budget, a warning when the luck bar is about
                                    to re-close, near misses, backlog, blocked ideas
    lab luck [--at N ...] [--limit K]
                                    read-only: the dev leaderboard under every N policy side by
                                    side, the N each resolves to, the evidence behind it and how
                                    many candidates clear the luck bar there. Writes nothing,
                                    loads no research store, spends no look. --at N adds a column
                                    at a literal N (repeatable)
    lab show M0007                  one method and its trials
    lab run M0007 [--store DIR] [--allow-coverage F]
                                    run a committed method on the dev window, record its trials;
                                    a method with a MarketAware allocator is refused when the
                                    store's fundamental panel covers less than 80% of the window,
                                    and every method is refused, before any backtest, when the
                                    store's prices are not the ones the lab's benchmark was
                                    measured on (lab/hardgate.py, D10)
    lab promote M0007               pre-register the best dev-eligible variant by MAR in
                                    docs/lab/prereg/M0007.md and move the method to promoted;
                                    commit that file before `lab test` will spend the one look.
                                    REFUSES a method that does not win a majority of its
                                    walk-forward folds, or that is scoreable on fewer than the
                                    folds the benchmark yields, or whose curves were measured on
                                    prices other than the benchmark's, or whose kin -- family,
                                    ancestry, blend ingredient or behaviour -- already reads
                                    test-failed (lab/hardgate.py). The refusal
                                    comes before anything is written, and there is no override
    lab reevaluate [M0022 ...]      re-judge recorded dev trials against the bars in force now
                                    (store.DSR_MIN, store.DSR_POLICY, tuning.MAX_DRAWDOWN) and
                                    move a method they unblock from rejected to dev-eligible.
                                    Reads only: no store, no backtest, no trial row, no look. A
                                    trial whose DSR cannot be evaluated at the gate's N fails the
                                    luck test and is reported as such
    lab test M0007-A [--store DIR] [--roster-id ID] [--dry-run]
                                    the one counted look: run a promoted method's pre-registered
                                    variant once on the test window, record a `test` trial and set
                                    test-passed / test-failed (both final). Refuses without a
                                    committed pre-registration, refuses a method that is not
                                    promoted, and the database refuses a second look. --dry-run
                                    prints what would run and spends nothing
    lab remeasure M0022 | H-P7A | H-P7A-F9 [--store DIR] [--only IDS] [--chunk N]
                                    re-run a recorded method's variants on the dev window and
                                    write back the DSR inputs (trial_moments) its trials predate.
                                    Writes nothing else: no trials row, no status, no
                                    pre-registration. Idempotent, and refuses a method that has
                                    already had its test-window look
                                    H-P7A re-measures all 54 P7a seed trials out of the frozen
                                    registry and reports the DSR each now computes at the current
                                    gate N; H-P7A-F9 does one family. A seed trial has no recorded
                                    DSR, so the re-run is verified against the six metrics the lab
                                    did record, and a trial that does not reproduce them is
                                    reported and not written (exit 1)
    lab costs M0007 [--candidate M0007-N20-RAW] [--store DIR]
                                    report only: re-run a recorded method's best dev variant (by
                                    MAR, or --candidate) at the flat 0.1% and at Gotrade's real
                                    fees (sim/costs.py, measured from the owner's receipts), print
                                    both and journal the difference as an observation. No trial
                                    row, no moments, no status change: N and the looks do not move
    lab turnover [--cadence daily,weekly,monthly] [--names 10,20,30] [--churn 0.25,0.5,1.0]
                 [--years 10] [--usd-idr 17841] [--growth 0] [--csv PATH]
                                    report only: what Gotrade's measured schedule charges a book
                                    for re-picking itself at each cadence, on the owner's real
                                    funding plan. Arithmetic over sim/costs.py's fee_parts: no
                                    backtest, no research store, no model. Prints the annual
                                    return a strategy must add just to be level with doing
                                    nothing, and the month the $0.10 per-order floor stops
                                    binding. No trial row, no moments, no status change: N and
                                    the looks do not move
    lab shortfall 828 | M0244-PLACEBO30 [--era 2009-2015] [--store DIR] [--against CID]
                  [--names N] [--csv PATH]
                                    report only: where one recorded trial's gap to SPY TR over one
                                    era went -- the gate premium it paid for being out of the
                                    market, the fee drag its turnover bought, and ONE residual for
                                    the pool and the weighting, which is labelled a residual and
                                    never named after a cause. The gap itself is not recomputed:
                                    it comes from the same de-funded walk-forward slice against
                                    REF-SPY-HOLD that lab exposure and lab gate use. With --store
                                    the era's exposure is resolved from the shared SPY 200-day
                                    gate's own on-share per era; without one the recorded
                                    whole-window figure is used and the output says so.
                                    --against names a sibling arm of the same method and splits
                                    the residual into what the two share and what this arm owns.
                                    No trial row, no moments, no status change: N and the looks do
                                    not move
    lab survivorship M0069 [M0007 ...] [--store DIR] [--sv-store DIR] [--csv PATH] [--no-journal]
                                    report only: re-run every recorded dev variant of each method
                                    at its recorded capital and funding on the dev store and on
                                    the survivorship-check store (engine/.research-sv), side by
                                    side; journal one observation per method. No trial row, no
                                    moments, no status change: N and the looks do not move
    lab exposure M0030 [M0024 ...] [--only IDS] [--store DIR] [--csv PATH] [--no-journal]
                                    report only: what share of a method's money was ever in its
                                    own picks rather than parked in the market, and what those
                                    picks did alone against SPY per era, with the parked holding
                                    removed and the brakes off. Four columns per recorded variant,
                                    no method file changed and no new method id. No trial row, no
                                    moments, no status change: N and the looks do not move
    lab gate [M0030 ...] [--all] [--only IDS] [--store DIR] [--csv PATH] [--gated-only]
             [--no-journal] [--dry-run]
                                    report only: what the shared SPY 200-day trend gate is worth,
                                    book by book. Re-runs every recorded dev variant twice -- as
                                    recorded, and with that one gate switched off and nothing else
                                    moved -- and prints the lead over SPY whole-window and per era
                                    beside what the gate was worth in each. The gate is found by a
                                    generic walk over the params, checked first against the
                                    recorded controls the lab already holds; a variant whose gate
                                    cannot be identified is listed, never run as if it were off.
                                    No method file changes and no new method id. No trial row, no
                                    moments, no status change: N and the looks do not move
    lab idea --name ... --hypothesis ...   queue an idea (prints its id)
    lab note M0007 --file F [--verdict V]  append analysis / set the verdict
    lab block M0007 --on "what data"       an idea the store cannot test
    lab unblock M0007 --note "..."         the missing data arrived: blocked-data -> idea, the
                                           note (what arrived, how much of the window it covers)
                                           appended to the analysis
    lab drop M0007 --why "..."             an idea dropped before running
    lab seen KEY [--method M] [--note N] | lab seen --find TEXT
    lab insight --kind K --title T (--body B | --file F) [--method M]   the lab journal
    lab stage                       under the write lock: write web/data/lab.json, git-add it and the database
    lab next-id                     the next free method id
    lab export [--out F]            the lab as an xlsx workbook (gitignored)
    lab export-json [--out F]       the web snapshot (default: web/data/lab.json beside the database's repo)
    lab seed                        one-time import of the pre-lab record

Parallel sessions (sera-the-explorer) share one database: SEER_LAB_DB sets --db,
SEER_RESEARCH_STORE sets --store, and SEER_SV_STORE sets lab survivorship's --sv-store. A
worktree has none of the three stores of its own, so a child exports all three to the main
checkout's.

Exit 0 on success; 2 when the lab's rules refuse the request; 1 on any other error.
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import math
import os
import statistics
import time
from datetime import date
from collections.abc import Sequence
from pathlib import Path

from seer_engine import config, research
from seer_engine.backtest import dev, tuning
from seer_engine.backtest.metrics import fmt_num, fmt_pct, fmt_pf, fmt_signed_pct
from seer_engine.fundamentals import coverage
from seer_engine.lab import store

log = logging.getLogger(__name__)

HELP = "The method lab: run, record and review strategy experiments (lab/lab.sqlite)"


def _coverage_floor(text: str) -> float:
    try:
        value = float(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from exc
    if not 0.0 <= value <= 1.0:
        raise argparse.ArgumentTypeError(f"must be a fraction between 0 and 1, got {value}")
    return value


def _positive_n(text: str) -> int:
    """An ``--at N`` column: an integer the deflated Sharpe is defined at.

    ``dev.deflated_sharpe`` returns None below two looks, so ``--at 1`` would silently add a
    column of dashes. argparse says so instead.
    """
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not an integer: {text!r}") from exc
    if value < 2:
        raise argparse.ArgumentTypeError(
            f"the deflated Sharpe is undefined below N = 2 trials, got {value}"
        )
    return value


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--db", type=Path, default=store.DB_PATH, help="lab database (default: lab/lab.sqlite)")
    sub = p.add_subparsers(dest="lab_command", metavar="<lab command>", required=True)

    sub.add_parser("status", help="the lab at a glance")

    s = sub.add_parser(
        "luck",
        help="read-only: the dev leaderboard under every N policy, side by side",
        description=(
            "Re-evaluate every recorded dev DSR at the N each named policy resolves to, and at "
            "any literal N given with --at, and say how many candidates clear the luck bar at "
            "each. Reads the lab, writes nothing, loads no research store and spends no "
            "test-window look: safe against the committed database. The gate itself is one "
            "constant, store.DSR_POLICY; this command is how you decide whether to touch it."
        ),
    )
    s.add_argument(
        "--at",
        type=_positive_n,
        action="append",
        default=None,
        metavar="N",
        help="add a column at this literal N, on top of the named policies (repeatable)",
    )
    s.add_argument(
        "--limit",
        type=int,
        default=12,
        metavar="K",
        help="how many dev trials to list, ranked by the live policy (default 12; 0 for all)",
    )
    s = sub.add_parser("show", help="one method and its trials")
    s.add_argument("method")

    s = sub.add_parser("run", help="run a committed method on the dev window")
    s.add_argument("method")
    s.add_argument("--store", type=Path, default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR))
    s.add_argument(
        "--allow-coverage",
        type=_coverage_floor,
        default=coverage.MIN_DEV_COVERAGE,
        metavar="F",
        help=(
            f"lower the dev-window panel-coverage floor from {coverage.MIN_DEV_COVERAGE:.2f} to F "
            "(0..1) for this run. An acknowledgement, not a silencer: the measured fraction and "
            "the per-year table are printed either way. Only methods with a MarketAware "
            "allocator are gated at all"
        ),
    )
    s.add_argument(
        "--amend",
        action="store_true",
        help=(
            "run the next pre-registered Amendment this method file declares, instead of its "
            "original candidates. The trials land under the same method id, so the luck gate's N "
            "does not move and no method id is spent; `methods.source_sha` is left alone and the "
            "file's current sha is appended to `method_amendments`. The method must have run, "
            "must not have reached the test window, and the amendment must be committed -- the "
            "commit is its pre-registration. The method's status is not moved: use `lab "
            "reevaluate` if an amendment's trial clears every condition"
        ),
    )

    s = sub.add_parser(
        "promote", help="pre-register a dev-eligible method's best variant for the test window"
    )
    s.add_argument("method")
    s.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="where the pre-registration file goes (default: docs/lab/prereg/ in this checkout)",
    )

    s = sub.add_parser(
        "reevaluate",
        help="re-judge recorded dev trials against the current luck bar; moves a method "
             "rejected -> dev-eligible when the bars in force today clear every condition",
    )
    s.add_argument(
        "method", nargs="*", metavar="M0022",
        help="methods to re-evaluate (default: every method that reads rejected)",
    )

    s = sub.add_parser("test", help="the one counted look at the test window (design §3)")
    s.add_argument("candidate", metavar="M0007-A",
                   help="the pre-registered variant, not the method: one variant per method "
                        "is pre-registered and it is the one that gets the look")
    s.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("SEER_RESEARCH_TEST_STORE") or research.TEST_STORE_DIR),
        help=f"test-window research store (default: {research.TEST_STORE_DIR}, or "
             "$SEER_RESEARCH_TEST_STORE); a dev store here is refused",
    )
    s.add_argument("--roster-id", default=None, metavar="ID",
                   help="the paper-roster id to propose in the promote command printed on a pass "
                        "(default: the method id)")
    s.add_argument("--dry-run", action="store_true",
                   help="print what would run -- the window, the store, the pre-registration and "
                        "the conditions that decide the verdict -- and stop. Loads nothing, runs "
                        "nothing, records nothing; the look is not spent")

    s = sub.add_parser(
        "remeasure",
        help="recover the DSR inputs (trial_moments) of a method whose trials predate them",
    )
    s.add_argument("method", metavar="M0022|H-P7A",
                   help="the lab method whose recorded dev trials get their moments back, or "
                        "H-P7A for all 54 P7a seed trials / H-P7A-F9 for one seed family")
    s.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR),
        help=f"dev-window research store (default: {research.STORE_DIR}, or "
             "$SEER_RESEARCH_STORE). A test store is refused by research.load_store before a "
             "byte is read: this command never names a test window and never spends a look",
    )
    s.add_argument("--only", default=None, metavar="IDS",
                   help="seed path only: a comma-separated list of candidate ids to re-measure "
                        "instead of the whole set, for re-trying a handful after a divergence")
    s.add_argument("--chunk", type=int, default=dev.MAX_CANDIDATES, metavar="N",
                   help="seed path only: commit after every N backtests, so an interrupted job "
                        f"loses at most N (default: {dev.MAX_CANDIDATES}, i.e. one call). "
                        "Chunking is bit-identical to one call and costs only allocator "
                        "re-preparation; the whole 54-trial batch takes about a minute")

    s = sub.add_parser(
        "costs",
        # `0.1%%`, not `0.1%`: argparse runs every `help=` string through %-interpolation
        # (`HelpFormatter._expand_help`), so a bare `%` is read as a format spec and
        # `lab --help` died with "unsupported format character ','". A doubled `%%` renders as
        # one `%`. `description=` below is NOT interpolated and must stay single.
        help="report only: a recorded method at Gotrade's real fees vs the flat 0.1%%, journaled",
        description=(
            "Re-run a recorded method's best dev variant (by MAR) twice on the dev window -- at "
            "the lab's flat 0.1% a trade and at Gotrade's real fees -- print both side by side and "
            "append one observation to the lab journal. Records no trial, so the lab's N and the "
            "test-window looks do not move; the test window is never read."
        ),
    )
    s.add_argument("method", metavar="M0007")
    s.add_argument("--candidate", default=None, metavar="M0007-N20-RAW",
                   help="re-measure this recorded variant instead of the best one by MAR")
    s.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR),
        help=f"dev-window research store (default: {research.STORE_DIR}, or $SEER_RESEARCH_STORE); "
             "a test-window store is refused",
    )

    s = sub.add_parser(
        "names",
        help="report only: how many names the book should hold, swept at Gotrade's real fees",
        description=(
            "Run lab M0007-N20-RAW's book -- what the roster's RAW-FR entry trades -- at several "
            "name counts over the dev window, at Gotrade's measured fees and on the owner's real "
            "contribution schedule, and print the grid. Records no trial, so the lab's N and the "
            "test-window looks do not move; the test window is never read. The fee case for "
            "holding fewer names is settled (handover 2b, CORRECTED) and is not what this "
            "measures: by month three of the funding plan twenty names cost 0.614% an order and "
            "eleven cost 0.612%. This measures what concentration does to the returns."
        ),
    )
    s.add_argument(
        "--ns", default=None, metavar="5,10,15,20,25,30",
        help="the name counts to sweep (default: 5,10,15,20,25,30)",
    )
    s.add_argument(
        "--gotrade-only", action="store_true",
        help="drop the flat-fee control column and run Gotrade's fees alone (half the runs)",
    )
    s.add_argument(
        "--lump", action="store_true",
        help="fund the book once and never feed it, instead of the owner's real schedule. The "
             "control for the funding axis, not the answer: under Gotrade's $0.10 floor a book "
             "that ramps from 10,000,000 IDR pays a different rate from one that starts full",
    )
    s.add_argument(
        "--csv", type=Path, default=None, metavar="PATH",
        help="also write the grid to PATH as CSV, at full precision",
    )
    s.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR),
        help=f"dev-window research store (default: {research.STORE_DIR}, or $SEER_RESEARCH_STORE); "
             "a test-window store is refused. The store is gitignored, so a fresh worktree has "
             "none -- point this at a checkout that does rather than rebuilding it",
    )

    s = sub.add_parser(
        "turnover",
        # `$0.10` is safe but every `%` below is doubled: argparse runs each `help=` through
        # %-interpolation (HelpFormatter._expand_help), so a bare `%` is read as a format spec
        # and `lab --help` dies. `description=` is NOT interpolated and must stay single. Same
        # rule as the `costs` and `exposure` parsers above.
        help="report only: what Gotrade charges a book for re-picking itself, by cadence",
        description=(
            "Price a book shape -- how many names, how often it is re-picked, what share of it "
            "turns over each time -- against sim/costs.py's measured Gotrade schedule, over the "
            "owner's real funding plan (10,000,000 IDR at the start, +5,000,000 IDR on the 25th "
            "of every month). Arithmetic, not a backtest: it builds no model, opens no research "
            "store and runs no simulator, and every order goes through sim.costs.fee_parts with "
            "a re-pick counted as one sell plus one buy. Prints, per cell, the fees paid, the "
            "share of orders that paid the $0.10 trading-fee floor rather than the 0.2% rate, "
            "the round-trip cost as a share of a slot, and the annual return the strategy must "
            "add just to be level with doing nothing. Also prints the floor month by month as "
            "the owner's deposits arrive, because the floor's bite shrinks as the book grows and "
            "a single average would hide that. Records no trial, so the lab's N and the "
            "test-window looks do not move; the test window is never read. This prices a "
            "CADENCE, not a name count: the owner's standing instruction is that a name count is "
            "tested on the merits and never on fee grounds."
        ),
    )
    s.add_argument(
        "--cadence", default=None, metavar="daily,weekly,monthly",
        help="the re-pick cadences to price (default: all three). sim.rules offers these and no "
             "others, so these are the only horizons there are",
    )
    s.add_argument(
        "--names", default=None, metavar="10,20,30",
        help="the book sizes to price (default: 10,20,30). This axis is here because the "
             "per-order floor depends on slot size, NOT because a name count is being chosen",
    )
    s.add_argument(
        "--churn", default=None, metavar="0.25,0.5,1.0",
        help="the share of the book replaced at each re-pick, in (0, 1] (default: 0.25,0.5,1.0). "
             "1.0 means the whole book is swapped every time",
    )
    s.add_argument(
        "--years", type=int, default=None, metavar="N",
        help="how many years of the funding plan to price (default: 10, the design's own bar)",
    )
    s.add_argument(
        "--usd-idr", default=None, metavar="17841",
        help="rupiah per dollar for the owner's deposits (default: 17841, the rate the frozen "
             "production book started at and the rate `lab names` was measured at)",
    )
    s.add_argument(
        "--growth", default=None, metavar="0.10",
        help="compound the deposit path at this annual rate (default: 0). Zero is the "
             "conservative reading -- a book that earns nothing keeps the smallest slots and so "
             "pays the floor the longest. The knob is for checking the answer does not hinge on "
             "it; measured, it does not",
    )
    s.add_argument(
        "--csv", type=Path, default=None, metavar="PATH",
        help="also write the grid and the floor ramp to PATH as CSV, at full precision",
    )

    s = sub.add_parser(
        "regime",
        help="split recorded dev results by market breadth (report only; no trial, no look)",
    )
    s.add_argument("method", nargs="*", metavar="M0007",
                   help="methods to report (default: every method with a dev trial)")
    s.add_argument("--store", type=Path,
                   default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR))
    s.add_argument("--min-months", type=int, default=12, metavar="N",
                   help="skip a regime with fewer than N months of evidence (default 12)")

    s = sub.add_parser(
        "walkforward",
        help="score each method's selection out of sample, many folds (report only; no store)",
    )
    s.add_argument("method", nargs="*", metavar="M0007")
    s.add_argument("--min-train-years", type=int, default=None, metavar="N")
    s.add_argument("--eval-years", type=int, default=None, metavar="N")

    s = sub.add_parser(
        "shortfall",
        # Every `%` in a `help=` below is doubled: argparse runs each one through
        # %-interpolation (HelpFormatter._expand_help), so a bare `%` is read as a format spec
        # and `lab --help` dies with "unsupported format character". A doubled `%%` renders as
        # one `%`. `description=` is NOT interpolated and must stay single. Same rule as the
        # `costs`, `exposure`, `gate` and `turnover` parsers above.
        help="report only: where one trial's gap to SPY TR over an era went (gate, fees, residual)",
        description=(
            "Split one recorded dev trial's gap to SPY total return over one era into a gate "
            "premium, a modelled fee drag and one residual for the pool and the weighting. The "
            "gap is not recomputed: it comes from walkforward.measure over the recorded monthly "
            "curve, de-funded through hardgate.trial_deposits, against the recorded REF-SPY-HOLD "
            "curve sliced the same way -- the path lab exposure, lab gate and lab survivorship "
            "already take. With --store the era's exposure is resolved by scaling the recorded "
            "whole-window figure by the shared SPY 200-day gate's own on-share in that era "
            "against its on-share over the whole window; without --store, for a book that "
            "carries no shared gate, or for a book that held money while the gate was off, the "
            "recorded whole-window exposure is used and the report says so. The fee drag is a "
            "MODEL -- what a run really paid is not a trials column -- and is printed with a "
            "sensitivity band across book sizes so a guessed name count is visibly bounded. The "
            "residual is a residual: it is the term the two named ones do not explain and it is "
            "never named after a cause. This is an attribution under stated assumptions, not an "
            "identity. Records no trial, no moments, no funding, no provenance, no insight and "
            "no status, so the lab's N and the test-window looks do not move; the test window is "
            "never read, and a test-window trial is refused by name."
        ),
    )
    s.add_argument(
        "trial", metavar="828",
        help="the trial to decompose: a trials.n, or a candidate id like M0244-PLACEBO30",
    )
    s.add_argument(
        "--era", default=None, metavar="2009-2015",
        help="the era to decompose over (default: 2009-2015). One of the eras in "
             "lab/exposure.py's ERAS, or `whole` for the trial's whole window",
    )
    s.add_argument(
        "--store", type=Path,
        default=(Path(os.environ["SEER_RESEARCH_STORE"])
                 if os.environ.get("SEER_RESEARCH_STORE") else None),
        help="a dev-window research store, read for the shared SPY 200-day gate's on-share per "
             "era (default: $SEER_RESEARCH_STORE, else none). Without it the recorded "
             "whole-window exposure is used instead, which measured 5.11 against 3.60 pts/yr of "
             "gate premium on trial 828 -- so pass it when you have one. The stores are "
             "gitignored, so a worktree has none: point this at a checkout that does rather "
             "than rebuilding one. Only the gate symbol's rows of bars.csv are read; no market "
             "is loaded and no backtest is run",
    )
    s.add_argument(
        "--against", default=None, metavar="M0244-FRESH30",
        help="split the pool+weighting residual against this sibling arm of the SAME method: "
             "what that arm's own residual also carries is attributed to the shared pool and "
             "frame, and only the remainder to this arm's own weighting and selection. An arm "
             "of another method, or one whose prices are not the benchmark's (hardgate D10), is "
             "refused rather than reported",
    )
    s.add_argument(
        "--names", type=int, default=None, metavar="30",
        help="the book's name count for the fee model (default: read from the recorded "
             "configuration's outermost `top=`, else the roster's 20). The slot size sets how "
             "hard Gotrade's $0.10 per-order floor bites; measured, the 2009-2015 drag moves "
             "only from 3.71 to 3.85 pts/yr across 10 to 50 names, and the report prints that "
             "band beside its answer",
    )
    s.add_argument(
        "--csv", type=Path, default=None, metavar="PATH",
        help="also write the terms to PATH as CSV, at full precision",
    )

    s = sub.add_parser(
        "survivorship",
        help="report only: recorded methods re-run on the survivorship-check store beside the dev store",
        description=(
            "Re-run every recorded dev variant of each named method at its recorded capital and "
            "funding, first on the dev store and then on the survivorship-check store (the dev "
            "store plus the bars of members it could not price), never holding both in memory. "
            "Prints them side by side: yearly return against SPY in the same measure, max "
            "drawdown, profit factor, trades, the DSR inputs at the recorded N and var_trials, "
            "the 2009-2015 lead over SPY and the walk-forward record. Records no trial, no "
            "moments, no funding and no status, so the lab's N and the test-window looks do not "
            "move; one plain-words observation per method is journaled unless --no-journal."
        ),
    )
    s.add_argument("method", nargs="+", metavar="M0069", help="the methods to re-run")
    s.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR),
        help=f"the dev store the trials were recorded on (default: {research.STORE_DIR}, or "
             "$SEER_RESEARCH_STORE); a store with a purpose marker or a test window is refused",
    )
    s.add_argument(
        "--sv-store",
        type=Path,
        default=Path(os.environ.get("SEER_SV_STORE") or research.SV_STORE_DIR),
        help=f"the survivorship-check store (default: {research.SV_STORE_DIR}, or "
             "$SEER_SV_STORE); refused unless its manifest says purpose survivorship-check. From a "
             "worktree, export SEER_SV_STORE to the main checkout's engine/.research-sv",
    )
    s.add_argument("--no-journal", action="store_true",
                   help="print the report and write nothing at all, not even the observation")
    s.add_argument("--csv", type=Path, default=None, metavar="PATH",
                   help="also write the full grid (variant x store) to PATH as CSV, full precision")

    s = sub.add_parser(
        "kin",
        # No literal `%` in any `help=` string below: argparse %-interpolates every `help=`.
        help="report only: how alike a method is to every book that has already failed its look",
        description=(
            "Print EVERY correlation between this method's recorded dev variants and the tested "
            "variant of every method that reads test-failed, instead of only the single best one "
            "the hard gate reports. The gate keeps one twin per failed method because that is all "
            "it needs in order to refuse; the consequence is that any variant which is not the "
            "best correlator never has its own number computed, so the only way to read it was to "
            "register that configuration alone and spend a method id re-deriving a number the "
            "recorded curves already contain. This command reads it instead. Same path as the "
            "gate, pair for pair -- monthly returns, de-funded, less each series' own fit on the "
            "benchmark's, correlated over the months they share -- and it fails closed on a price "
            "fingerprint mismatch exactly as the gate does, so a number printed here is the number "
            "the gate would read. Writes nothing, opens no research store, mints no method id: "
            "the lab's N and the test-window looks cannot move."
        ),
    )
    s.add_argument("method", nargs="+", metavar="M0133", help="the methods to measure")
    s.add_argument("--all", action="store_true",
                   help="print every pair, not only each variant's strongest match")

    s = sub.add_parser(
        "exposure",
        # No literal `%` in any `help=` string below, and none may be added: argparse runs every
        # `help=` through %-interpolation (HelpFormatter._expand_help), so a bare `%` is read as a
        # format spec and `lab --help` dies. A doubled `%%` renders as one `%`. `description=` is
        # NOT interpolated and must stay single. See the `costs` parser above.
        help="report only: how much of a method's money was in its own picks, and what they did alone",
        description=(
            "Re-run every recorded dev variant of each named method at its recorded capital and "
            "funding, four times on the dev window: the candidate as the lab recorded it; its own "
            "picks with the parked instruments dropped at the weights it gave the rest; those "
            "picks rescaled to fill the whole book with every brake off; and the parked money "
            "alone. Prints the share of the book that was ever in its own picks, the share of "
            "decision days it had no pick to make, and the lead over SPY whole-window and per era "
            "(1996-2002, 2003-2008, 2008 alone, 2009-2015). Parked is read generically from the "
            "allocator's own holds(), so no method file changes and no method id is minted. "
            "Records no trial, no moments, no funding and no status, so the lab's N and the "
            "test-window looks do not move and the test window is never read; one plain-words "
            "observation per method is journaled unless --no-journal."
        ),
    )
    s.add_argument("method", nargs="+", metavar="M0030", help="the methods to measure")
    s.add_argument(
        "--only", "--candidate", default=None, metavar="IDS",
        help="measure only these recorded variants (comma-separated candidate ids, e.g. "
             "M0030-C50T) instead of every recorded dev variant of each method",
    )
    s.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR),
        help=f"the dev store the trials were recorded on (default: {research.STORE_DIR}, or "
             "$SEER_RESEARCH_STORE); a test-window store is refused. The store is gitignored, so "
             "a fresh worktree has none -- point this at a checkout that does",
    )
    s.add_argument("--no-journal", action="store_true",
                   help="print the report and write nothing at all, not even the observation")
    s.add_argument("--csv", type=Path, default=None, metavar="PATH",
                   help="also write the full grid (variant x column) to PATH as CSV, full precision")

    s = sub.add_parser(
        "gate",
        # No literal `%` in any `help=` string below, and none may be added: argparse runs every
        # `help=` through %-interpolation (HelpFormatter._expand_help), so a bare `%` is read as a
        # format spec and `lab --help` dies. A doubled `%%` renders as one `%`. `description=` is
        # NOT interpolated and must stay single. See the `exposure` parser above.
        help="report only: what the shared SPY 200-day trend gate was worth, book by book",
        description=(
            "Re-run every recorded dev variant of each named method at its recorded capital and "
            "funding, twice on the dev window: the candidate as the lab recorded it, and the same "
            "candidate with SPY's 200-day trend gate switched off and nothing else moved. Prints "
            "the lead over SPY whole-window and per era (1996-2002, 2003-2008, 2008 alone, "
            "2009-2015), what the gate was worth in each era, the share of decision days each arm "
            "held nothing, and a roll-up over everything measured. The gate is found by a generic "
            "walk over the candidate's params -- the trend pair f_factor.trend_on reads, and the "
            "blend-core spelling of the same rule -- so no method file changes and no method id is "
            "minted; the walk is checked against the gate-off controls the lab already holds "
            "before anything runs, and a variant whose gate it cannot identify is listed as not "
            "transformable and never run as though the gate were off. Records no trial, no "
            "moments, no funding and no status, so the lab's N and the test-window looks do not "
            "move and the test window is never read; one plain-words observation per method is "
            "journaled unless --no-journal."
        ),
    )
    s.add_argument("method", nargs="*", metavar="M0030",
                   help="the methods to measure; omit and pass --all for every method with a "
                        "recorded dev trial")
    s.add_argument("--all", action="store_true",
                   help="measure every method that has a recorded dev trial and still has a "
                        "method file, instead of naming them. Hundreds of backtests: use --dry-run "
                        "first to see the scope")
    s.add_argument(
        "--only", "--candidate", default=None, metavar="IDS",
        help="measure only these recorded variants (comma-separated candidate ids, e.g. "
             "M0030-C50T) instead of every recorded dev variant of each method",
    )
    s.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR),
        help=f"the dev store the trials were recorded on (default: {research.STORE_DIR}, or "
             "$SEER_RESEARCH_STORE); a test-window store is refused. The store is gitignored, so "
             "a fresh worktree has none -- point this at a checkout that does",
    )
    s.add_argument("--gated-only", action="store_true",
                   help="skip the recorded variants the walk finds no gate in. Faster, and it "
                        "gives up the empty-decision cross-check that keeps a no-gate verdict "
                        "honest")
    s.add_argument("--dry-run", action="store_true",
                   help="classify every recorded variant and print what would run -- which carry "
                        "the gate, which do not, and which refuse it off -- then stop. Opens no "
                        "store, reads no bar, writes nothing")
    s.add_argument("--no-journal", action="store_true",
                   help="print the report and write nothing at all, not even the observation")
    s.add_argument("--csv", type=Path, default=None, metavar="PATH",
                   help="also write the full grid (variant x column) to PATH as CSV, full precision")

    s = sub.add_parser("idea", help="queue an idea in the backlog")
    s.add_argument("--name", required=True)
    s.add_argument("--family", required=True)
    s.add_argument("--hypothesis", required=True)
    s.add_argument("--source-kind", required=True, choices=[k for k in store.SOURCE_KINDS if k != "seed"])
    s.add_argument("--source-ref", default="")
    s.add_argument("--parent", default=None)

    s = sub.add_parser("note", help="append analysis and/or set the verdict")
    s.add_argument("method")
    s.add_argument("--file", type=Path, default=None)
    s.add_argument("--verdict", default=None)

    s = sub.add_parser("block", help="mark an idea blocked on missing data")
    s.add_argument("method")
    s.add_argument("--on", required=True)
    s = sub.add_parser("unblock", help="the missing data arrived: move a blocked idea back to idea")
    s.add_argument("method")
    s.add_argument("--note", required=True,
                   help="what arrived and how much of the dev window it covers (appended to the analysis)")

    s = sub.add_parser("drop", help="drop an idea before it runs")
    s.add_argument("method")
    s.add_argument("--why", required=True)

    s = sub.add_parser("seen", help="record or find a dedupe key")
    s.add_argument("key", nargs="?")
    s.add_argument("--method", default=None)
    s.add_argument("--note", default="")
    s.add_argument("--find", default=None)

    s = sub.add_parser("insight", help="append to the lab journal (food for thought)")
    s.add_argument("--kind", required=True, choices=store.INSIGHT_KINDS)
    s.add_argument("--title", required=True)
    s.add_argument("--body", default=None)
    s.add_argument("--file", type=Path, default=None)
    s.add_argument("--method", default=None)

    sub.add_parser("stage", help="write the web snapshot and git-add it with the database, under the write lock")
    sub.add_parser("next-id", help="the next free method id")
    s = sub.add_parser("export", help="write the lab as an xlsx workbook")
    s.add_argument("--out", type=Path, default=store.XLSX_PATH)
    s = sub.add_parser("export-json", help="write the web snapshot (seertrade.site/sera)")
    s.add_argument("--out", type=Path, default=None,
                   help="output file (default: web/data/lab.json in the database's repo)")
    sub.add_parser("seed", help="one-time import of the pre-lab record")


def run(args: argparse.Namespace) -> int:
    conn = store.connect(args.db)
    try:
        return _HANDLERS[args.lab_command](conn, args)
    except store.LabError as e:
        log.error("%s", e)
        return 2
    finally:
        conn.close()


# --------------------------------------------------------------------------- handlers


def _status(conn, args) -> int:
    out: list[str] = []
    for label, value in store.summary_rows(conn):
        out.append(f"{label}: {value}")
    # The N the luck gate actually judges at, printed beside the trial count rather than left to
    # the promotion heading far below: the two differ by several times under the ``methods``
    # policy, and a reader who meets only the larger number up here misreads every DSR on screen.
    live_n = _live_n(conn, store.DSR_POLICY)
    if live_n is not None:
        out.append(f"N the luck gate judges at (policy {store.DSR_POLICY}): {live_n}")
    out.append("")
    out.append("Families (best dev MAR):")
    for r in conn.execute(
        "SELECT m.family, count(t.n) AS trials, max(t.mar) AS best, group_concat(DISTINCT m.id) AS ids "
        "FROM methods m LEFT JOIN trials t ON t.method_id = m.id AND t.window = 'dev' "
        "WHERE m.status NOT IN ('idea', 'blocked-data') GROUP BY m.family ORDER BY best IS NULL, best DESC"
    ):
        out.append(f"  {r['family']:<28} trials {r['trials']:>3}  best MAR {fmt_num(r['best'])}  ({r['ids']})")
    out.append("")
    out.append("Near misses (beat SPY TR on dev, by MAR):")
    for r in conn.execute(
        "SELECT * FROM trials WHERE window = 'dev' AND total_return > spy_tr_return AND mar IS NOT NULL "
        "ORDER BY mar DESC LIMIT 12"
    ):
        out.append(
            f"  {r['candidate_id']:<28} MAR {fmt_num(r['mar'])}  CAGR {fmt_signed_pct(r['cagr'])} vs "
            f"{fmt_signed_pct(r['spy_tr_cagr'])}  maxDD {fmt_pct(r['max_drawdown'])}  PF {fmt_pf(r['profit_factor'])}  "
            f"trades {r['trades']}  DSR {fmt_num(r['dsr'], 3)}  failed: {r['failed'] or '-'}"
        )
    out.append("")
    out.append("Closest to eligible (fewest failed go-live conditions, DSR aside, then MAR):")
    rows = conn.execute("SELECT * FROM trials WHERE window = 'dev' AND mar IS NOT NULL").fetchall()

    for r in sorted(rows, key=lambda r: (len(_owner_misses(r)), -r["mar"], r["n"]))[:8]:
        out.append(
            f"  {r['candidate_id']:<28} misses {len(_owner_misses(r))}: "
            f"{'; '.join(_owner_misses(r)) or '-'}  "
            f"CAGR {fmt_signed_pct(r['cagr'])} vs {fmt_signed_pct(r['spy_tr_cagr'])}  maxDD "
            f"{fmt_pct(r['max_drawdown'])}  PF {fmt_pf(r['profit_factor'])}  trades {r['trades']}  DSR {fmt_num(r['dsr'], 3)}"
        )
    for title, status in (("Backlog (idea)", "idea"), ("Blocked on data", "blocked-data")):
        rows = conn.execute("SELECT * FROM methods WHERE status = ? ORDER BY id", (status,)).fetchall()
        if rows:
            out.append("")
            out.append(f"{title}:")
            for m in rows:
                extra = f" [needs: {m['blocked_on']}]" if m["blocked_on"] else ""
                out.append(f"  {m['id']} {m['name']} ({m['family']}, {m['source_kind']}){extra}")
    out.append("")
    out += _promotion_path(conn)
    out.append("")
    out.append("Latest insights:")
    for i in conn.execute("SELECT * FROM insights ORDER BY id DESC LIMIT 8"):
        out.append(f"  [{i['kind']}] {i['title']}" + (f" ({i['method_id']})" if i["method_id"] else ""))
    out.append("")
    out.append("Latest verdicts:")
    for m in conn.execute(
        "SELECT * FROM methods WHERE verdict <> '' AND id GLOB 'M*' ORDER BY updated DESC LIMIT 8"
    ):
        out.append(f"  {m['id']} {m['name']}: {m['verdict']}")
    print("\n".join(out))
    return 0


# --------------------------------------------------------------------------- the luck bar at another N
#
# `lab luck` and the ratchet warning answer one question: what would the recorded verdicts be
# if the deflated Sharpe had deflated by a different number of looks? They answer it without
# re-running anything, from the columns `trials` already carries, and they write nothing.
#
#     DSR = Phi((SR - SR*(N)) * k),  k = sqrt(t - 1) / sqrt(1 - g3*SR + (g4-1)/4 * SR^2)
#
# `k` does not depend on N. `t`, `g3` and `g4` are not in `trials` -- that is exactly what phase
# 2's `trial_moments` exists to fix for trials run from now on -- so `k` is recovered by
# inverting a known DSR at the N it belongs to, and the answer is the same Phi with a different
# `SR*`. See the analysis document, "What each N would do to the recorded verdicts".


def _owner_misses(row) -> list[str]:
    """The five go-live conditions ``row`` misses **at the bars in force now**. One line, by rule.

    ``store.owner_failures`` is the single definition of that question and it lives in
    ``lab/store.py`` (phase 4). This is a thin alias so the call sites below read as English;
    it must never grow a rule of its own.

    **It takes the trial row, not ``row["failed"]``.** That distinction is the whole point.
    ``trials`` is append-only, so a recorded ``failed`` string names the bars in force on the
    trial's **run date** -- all 110 recorded rows say ``"DSR >= 0.95"`` and ``"max DD <= 15%"``,
    and the owner moved both on 2026-10-07 (0.90 and 20%). Reading conditions back out of that
    string would show ``M0022`` as failing a luck bar nobody applies and ``M0020-W-NOSTOP`` as
    failing a drawdown bar nobody applies -- the two candidates this plan set exists to unblock,
    both rendered permanently ineligible by a sentence about the past.

    ``store.owner_failures`` re-derives the four *threshold* conditions from the row's recorded
    numeric columns against the live constants, and carries ``owner inputs`` -- the one condition
    that is not a threshold and has no column -- from the recorded string. See phase 4.
    """
    return list(store.owner_failures(row))


# ``sr_star`` and ``recover_dsr`` are **phase 4's**, defined in ``lab/store.py`` beside the gate
# that uses them, and re-exported here so this module's call sites and tests read as English.
# (Reconciled: this phase drafted them locally because ``store.py`` belonged to phases 2 and 4;
# phase 4 then needed the same inversion for ``store.dsr_at``, and the lab must not carry two
# implementations of the deflated Sharpe's inversion.)
#
#   sr_star(n_trials, var_trials)        -- the daily hurdle SR* at n_trials looks
#   recover_dsr(*, sharpe_daily, dsr_at_run, n_at_run, var_trials, n_trials)
#                                        -- a recorded DSR re-evaluated at another N; returns
#                                           dsr_at_run exactly at n_trials == n_at_run
from seer_engine.lab.store import recover_dsr, sr_star  # noqa: E402, F401  (re-exported for the CLI)


def _dev_var(conn) -> float | None:
    """The variance of the dev trials' daily Sharpes. **Phase 4's ``store.dev_sharpe_variance``.**

    An alias, kept so the call sites below read locally; it must not grow a rule of its own. It
    is the same expression ``runner.trial_rows`` deflates by **and** the one ``store.dsr_at``
    uses on both of its routes, so the hurdle this module prints is the hurdle the gate applies.
    """
    return store.dev_sharpe_variance(conn)


def _policies() -> tuple[str, ...]:
    """The named N policies, in ``npolicy``'s own order."""
    from seer_engine.lab import npolicy

    return tuple(getattr(npolicy, "POLICIES", ("all-trials", "methods", "effective")))


def _n_counts(conn) -> list[tuple[str, object | None, str]]:
    """``(policy, NCount | None, why-not)`` for every named policy.

    A policy that cannot be resolved on this database -- too few trials to estimate a
    participation ratio, no stored curves -- keeps its row with ``None`` and the reason, instead
    of being dropped. ``lab luck`` is the command you run when the gate is behaving oddly; a
    policy that silently vanished from its table would be the worst possible answer.
    """
    from seer_engine.lab import npolicy

    out: list[tuple[str, object | None, str]] = []
    for name in _policies():
        try:
            out.append((name, npolicy.effective_n(conn, name), ""))
        except Exception as e:  # noqa: BLE001 - a diagnostic never dies on one unresolvable policy
            out.append((name, None, str(e) or type(e).__name__))
    return out


def _evidence(count: object) -> str:
    """Every field of an ``npolicy.NCount`` except ``n`` and ``policy``, which the caller prints.

    Read generically rather than by name: phase 1 owns the field names, and the evidence behind a
    policy is exactly the thing that must not go stale in this output.
    """
    try:
        data = dataclasses.asdict(count)  # type: ignore[arg-type]
    except TypeError:
        data = {
            k: getattr(count, k)
            for k in dir(count)
            if not k.startswith("_") and not callable(getattr(count, k, None))
        }
    parts = []
    for key, value in data.items():
        if key in ("n", "policy") or value is None:
            continue
        shown = fmt_num(value, 3) if isinstance(value, float) else value
        parts.append(f"{key.replace('_', ' ')} {shown}")
    return ", ".join(parts)


def _live_n(conn, policy: str) -> int | None:
    """The N the live policy resolves to, or None when it cannot be resolved here.

    ``lab status`` must print on any database, a fresh one with no trials included, so an
    unresolvable policy costs the N in the heading and nothing else.
    """
    from seer_engine.lab import npolicy

    try:
        return int(npolicy.effective_n(conn, policy).n)
    except Exception:  # noqa: BLE001 - see the docstring; status prints either way
        return None


def _labels(failed: object) -> list[str]:
    """``Verdict.failed`` (phase 4) as a list of labels, whichever shape it carries.

    ``trials.failed`` is a ``"; "``-joined string; ``DevRow.failed`` is a sequence. Phase 4's
    ``Verdict.failed`` mirrors one of the two. Both are read here, so the sentences this file
    exists to print are not the thing that breaks when that is pinned.
    """
    if failed is None:
        return []
    if isinstance(failed, str):
        return [f for f in failed.split("; ") if f]
    return [str(f) for f in failed]  # type: ignore[union-attr]


def _eligible_at(conn, n_trials: int, var_trials: float) -> list[str]:
    """The candidates that would clear the luck bar at ``n_trials`` looks, missing nothing else.

    D1's evidence, recomputed rather than quoted: on the committed database this returns three
    candidates at N = 110 (M0022-W-TV14, M0022-W-TV16 and M0020-W-NOSTOP, the live policy) and
    seven at N = 23. That contrast is why the owner can move the threshold and leave the N alone
    with confidence, and it belongs in `lab luck`'s output rather than in a commit message.

    Owner conditions come from the row's own columns through ``_owner_misses``; only the luck
    test moves with N.
    """
    out: list[str] = []
    for r in conn.execute(
        "SELECT * FROM trials WHERE window = 'dev' AND dsr IS NOT NULL AND sharpe IS NOT NULL "
        "ORDER BY n"
    ).fetchall():
        if _owner_misses(r):
            continue
        v = recover_dsr(
            sharpe_daily=float(r["sharpe"]) / math.sqrt(252),
            dsr_at_run=float(r["dsr"]),
            n_at_run=int(r["n_trials_at_run"]),
            var_trials=var_trials,
            n_trials=n_trials,
        )
        if v is not None and v >= store.DSR_MIN:
            out.append(str(r["candidate_id"]))
    return out


# --------------------------------------------------------------------------- the promotion path
#
# design §3's path is dev-eligible -> promoted -> test-passed -> paper, and every step refuses a
# method that has not taken the one before it. A lab where nothing is dev-eligible therefore has
# an unreachable `lab promote` and an unreachable `lab test`. Until this block existed, `lab
# status` listed these sections only when they had rows -- so that state printed nothing at all
# about the promotion path, and the one condition that most needed saying was the one condition
# that was silent. 110 dev trials went by that way.
#
# Here every section prints, an empty one prints the reason it is empty built from the trials,
# and `_ratchet_warning` says so *before* it happens again (Decision D1b).

_PROMOTION_STATUSES: tuple[tuple[str, str, str], ...] = (
    ("Dev-eligible", "dev-eligible", "the hard gate decides which of these `lab promote` takes"),
    ("Promoted (pre-registered)", "promoted", "`lab test` spends the one look on these"),
    ("Test-passed", "test-passed", "the owner's call: a paper roster entry with its own clock"),
    ("Test-failed", "test-failed", "final; there is no second look at the configuration"),
    ("Paper", "paper", "trading on the paper roster"),
)

# D1b. 0.03 of DSR is roughly 30 more dev trials at the margins this lab runs at, which is under
# a run day of Sera -- close enough that the owner wants to hear about it before the batch, not
# after. The warning is a sentence, not a gate: nothing refuses to run because of it.
_WARN_MARGIN = 0.03
_N_CEILING = 100_000  # beyond this the ratchet is not a near-term concern; say "never" instead


def _best_luck_only(conn):
    """The dev trial with the highest derived DSR among those missing no owner condition.

    The pre-filter is on the row's own columns (``_owner_misses``), because phase 4's derived
    verdict re-derives the owner conditions from exactly those columns -- so filtering first
    keeps `lab status` to a handful of ``store.verdict`` calls instead of one per dev trial,
    without applying a second rule.

    ``(row, verdict)``, or None when no dev trial passes all five owner conditions.
    """
    best = None
    for r in conn.execute(
        "SELECT * FROM trials WHERE window = 'dev' AND mar IS NOT NULL ORDER BY n"
    ).fetchall():
        if _owner_misses(r):
            continue
        v = store.verdict(conn, r)
        key = (-1.0 if v.dsr is None else float(v.dsr), -int(r["n"]))
        if best is None or key > best[0]:
            best = (key, r, v)
    return None if best is None else (best[1], best[2])


def _sinks_at(conn, trial, verdict, var_trials: float | None) -> int | None:
    """The smallest N at which this trial's DSR falls below the bar. D1b's number.

    Seeded from the verdict (phase 4), not from the recorded columns: the warning has to be about
    the gate as it actually stands. ``recover_dsr`` anchored at ``(verdict.dsr, verdict.n)``
    returns ``verdict.dsr`` exactly at ``verdict.n`` and falls monotonically from there, so this
    is the gate's own curve and the bisection on it is exact.

    None when it never falls below within ``_N_CEILING`` looks, or when the recovery is
    undefined, or when the verdict is already under the bar -- in which case the empty
    ``Dev-eligible`` section is already saying so and a second sentence would be noise.
    """
    if var_trials is None or var_trials <= 0 or verdict.dsr is None:
        return None
    if trial["sharpe"] is None or int(verdict.n) < 2:
        return None
    if float(verdict.dsr) <= 0.5 or float(verdict.dsr) < store.DSR_MIN:
        return None
    common = dict(
        sharpe_daily=float(trial["sharpe"]) / math.sqrt(252),
        dsr_at_run=float(verdict.dsr),
        n_at_run=int(verdict.n),
        var_trials=var_trials,
    )
    lo, hi = int(verdict.n), _N_CEILING
    far = recover_dsr(n_trials=hi, **common)
    if far is None or far >= store.DSR_MIN:
        return None
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        v = recover_dsr(n_trials=mid, **common)
        if v is None:
            return None
        if v >= store.DSR_MIN:
            lo = mid
        else:
            hi = mid
    return hi


def _dev_trials_per_run_day(conn) -> float | None:
    """The lab's recent rate: the median dev trials recorded per distinct run day.

    Measured from ``trials.run_at``, never assumed -- a hardcoded "a Sera night is 25 trials"
    would be exactly the kind of stale constant this plan set exists to remove. None below three
    run days, where a median is not a rate.
    """
    counts = [
        int(r[0])
        for r in conn.execute(
            "SELECT count(*) FROM trials WHERE window = 'dev' "
            "GROUP BY substr(run_at, 1, 10) ORDER BY substr(run_at, 1, 10) DESC LIMIT 10"
        ).fetchall()
    ]
    return statistics.median(counts) if len(counts) >= 3 else None


def _ratchet_warning(conn, var_trials: float | None) -> list[str]:
    """Decision D1b: say it *before* the luck bar re-closes, not 110 trials after.

    The gate admits a candidate today because the threshold moved, not because the N did. The N
    still rises with every exploration, so the margin the threshold bought is spent by the search
    itself -- which is the complaint R1 names, deferred rather than removed. This prints the
    margin, the N at which the best candidate falls back below the bar, and, when the lab has
    enough run days to have a rate, how many run days of exploration that is.

    Nothing here is a constant lifted from the analysis document: the candidate and its DSR come
    from ``store.verdict``, its N from ``npolicy`` through that, the bar from ``store.DSR_MIN``
    and the rate from ``trials.run_at``. It is silent when there is no candidate above the bar,
    and silent when the margin is comfortable.
    """
    found = _best_luck_only(conn)
    if found is None:
        return []
    trial, v = found
    if v.dsr is None or float(v.dsr) < store.DSR_MIN:
        return []  # the empty Dev-eligible section already explains this one
    margin = float(v.dsr) - store.DSR_MIN
    if margin > _WARN_MARGIN:
        return []
    sinks = _sinks_at(conn, trial, v, var_trials)
    head = (
        f"  !! The luck bar is close. {trial['candidate_id']} is the best candidate that passes "
        f"all five go-live"
    )
    second = (
        f"     conditions, and its DSR is {fmt_num(v.dsr, 3)} against a {store.DSR_MIN} bar -- "
        f"{fmt_num(margin, 3)} of margin at N = {v.n} ({v.policy})."
    )
    if sinks is None:
        return [head, second, "     It does not fall below the bar at any N worth worrying about."]
    more = sinks - int(v.n)
    rate = _dev_trials_per_run_day(conn)
    pace = ""
    if rate and rate > 0:
        days = more / float(rate)
        pace = (
            f" -- about {fmt_num(days, 1)} run day(s) at this lab's recent rate of "
            f"{fmt_num(rate, 0)} dev trials a run day"
        )
    return [
        head,
        second,
        f"     It falls below the bar at N = {sinks}: {more} more dev trials{pace}.",
        "     More exploration re-closes this gate. `lab luck` shows what each N policy would do.",
    ]


def _no_dev_eligible_reason(conn) -> str:
    """Why no method is dev-eligible, in one sentence built from the trials.

    Three shapes, in the order a reader needs them:

    1. nothing has run, so nothing has been judged;
    2. something has run, and every candidate misses an owner condition -- which no change to the
       luck bar's N or threshold can rescue, and the sentence says so;
    3. candidates pass all five owner conditions and the luck bar alone is holding them, in which
       case the closest one, its derived DSR and its distance from the bar *is* the sentence.
    """
    methods = int(
        conn.execute(
            "SELECT count(DISTINCT method_id) FROM trials WHERE window = 'dev'"
        ).fetchone()[0]
    )
    if methods == 0:
        return "no method has run on the dev window yet, so nothing has been judged"
    ran = "1 method has run" if methods == 1 else f"{methods} methods have run"
    found = _best_luck_only(conn)
    if found is not None:
        r, v = found
        return (
            f"no method is dev-eligible: {ran}, and every candidate that passes all five go-live "
            f"conditions is held by the luck bar alone -- the closest is {r['candidate_id']} at "
            f"DSR {fmt_num(v.dsr, 3)} against a {store.DSR_MIN} bar, N = {v.n} under policy "
            f"{v.policy}. `lab luck` shows what another N would do"
        )
    rows = conn.execute(
        "SELECT * FROM trials WHERE window = 'dev' AND mar IS NOT NULL ORDER BY n"
    ).fetchall()
    if rows:
        r = min(
            rows,
            key=lambda x: (len(_owner_misses(x)), -(x["mar"] or 0.0), int(x["n"])),
        )
        misses = _owner_misses(r)
        return (
            f"no method is dev-eligible: {ran} and none passes the five go-live conditions -- the "
            f"closest is {r['candidate_id']}, missing {len(misses)}: {'; '.join(misses)}. No luck "
            f"bar, at any N or any threshold, can rescue a candidate that misses one of these"
        )
    return f"no method is dev-eligible: {ran} but no dev trial carries a MAR, so nothing can rank"


def _hard_gate_states(conn) -> dict[str, tuple[str, str | None]]:
    """The hard gate's answer for every ``dev-eligible`` method, run once per ``lab status``.

    ``{method_id: (the gate's one-line summary, why `lab promote` would refuse)}``. The first
    element is ``hardgate.summary`` verbatim -- the fold record **and** the kin state, in the shape
    ``"4 of 4 folds; kin clean"`` -- so a caller prints it whole and never re-states the kin. The
    second is ``None`` when the gate would take the method, and otherwise the refusal's own
    sentence collapsed to one line, so it drops straight into an indented status line however the
    gate chose to wrap it.

    The fold geometry is cut **once** here and passed to every ``summary`` (``hardgate.geometry``),
    which is what phase 1's handoff asks for: the folds come from the benchmark curve, not from the
    method, so re-cutting them per method is the same arithmetic seven times over. A lab with no
    benchmark has no geometry, and ``geo`` stays ``None`` -- ``summary`` then says so, per method,
    in its own words.

    **Only ``dev-eligible`` methods are asked.** A ``promoted`` method is not re-judged here, and
    that is Decision D3 showing through rather than an oversight: the pre-registration is a
    promise, ``lab test`` honours it as written, and a status block that re-opened it would be
    announcing a refusal the lab has already decided not to make. A promoted method whose kin
    failed *after* the promise is ``lab test``'s note to print, not this one's.

    **It never raises.** ``lab status`` runs on every lab there is, including one with no
    ``REF-SPY-HOLD`` dev trial and one whose recorded curves are empty -- the shape every fixture
    in ``test_lab_status.py`` builds, and the shape a lab has on its first day. The gate refuses
    such a lab and is right to, because the folds are cut from the benchmark curve; but that
    refusal is information to print, not a reason for ``lab status`` to stop printing. So every
    ``store.LabError`` is caught and becomes the sentence.

    Cost: at most one ``summary`` and one ``check`` per dev-eligible method -- seven on the
    committed database. Neither opens a research store, runs a backtest or writes anything.
    """
    from seer_engine.lab import hardgate

    def one_line(text: object) -> str:
        return " ".join(str(text).split())

    try:
        geo = hardgate.geometry(conn)
    except store.LabError:
        geo = None  # `summary` is lenient and says why, per method, in its own words

    states: dict[str, tuple[str, str | None]] = {}
    for m in conn.execute(
        "SELECT id FROM methods WHERE status = 'dev-eligible' ORDER BY id"
    ).fetchall():
        mid = str(m["id"])
        record = one_line(hardgate.summary(conn, mid, geo))
        try:
            hardgate.check(conn, mid)
        except store.LabError as e:
            states[mid] = (record, one_line(e))
        else:
            states[mid] = (record, None)
    return states


def _empty_reason(
    conn, status: str, gates: dict[str, tuple[str, str | None]] | None = None
) -> str:
    """Why one promotion-path section is empty.

    Every step but the first is empty for exactly one reason worth printing -- the step before it
    -- and naming the command that would move it is the whole value of the sentence. The first
    step, ``dev-eligible``, is empty because of the gate, and that is the sentence this block
    exists for.

    **The ``promoted`` section has a second reason since 2026-10-09.** "N methods are
    dev-eligible; `lab promote` has not been run on them yet" is false in the way that costs
    somebody an hour when ``lab promote`` would exit 2 on every one of them: it names a command as
    waiting to be run when running it does nothing. So when the hard gate refuses some or all of
    the dev-eligible methods, this says that instead and points at the block above that carries
    each one's fold record and kin.

    ``gates`` is ``_hard_gate_states``'s answer, passed in by ``_promotion_path`` so the gate runs
    once per ``lab status`` rather than once per section; ``None`` means compute it here.
    """
    if status == "dev-eligible":
        return _no_dev_eligible_reason(conn)
    prior = {
        "promoted": "dev-eligible",
        "test-passed": "promoted",
        "test-failed": "promoted",
        "paper": "test-passed",
    }[status]
    cmd = {
        "promoted": "lab promote",
        "test-passed": "lab test",
        "test-failed": "lab test",
        "paper": "python -m seer_engine promote",
    }[status]
    n = int(conn.execute("SELECT count(*) FROM methods WHERE status = ?", (prior,)).fetchone()[0])
    if n == 0:
        return f"nothing is {prior}, so `{cmd}` has nothing to take"
    noun = "1 method is" if n == 1 else f"{n} methods are"
    it = "it" if n == 1 else "them"
    if status == "promoted":
        if gates is None:
            gates = _hard_gate_states(conn)
        refused = sum(1 for _record, why in gates.values() if why is not None)
        if refused >= n:
            return (
                f"{noun} dev-eligible, and the hard gate refuses every one of {it} -- "
                f"`lab promote` would exit 2, not pre-register. Read \"Refused by the hard gate\" "
                f"above for each one's fold record and kin; there is no override, and the only "
                f"way through is a method the folds and its kin have not already judged"
            )
        if refused:
            return (
                f"{noun} dev-eligible, {refused} of which the hard gate refuses (see \"Refused by "
                f"the hard gate\" above); `lab promote` has not been run on the rest yet"
            )
    return f"{noun} {prior}; `{cmd}` has not been run on {it} yet"


def _promotable_now(
    conn, gates: dict[str, tuple[str, str | None]] | None = None
) -> list[str]:
    """What ``lab promote`` would take today, and what is holding the rest back.

    ``prereg.promote_method`` wants two things: a method at ``dev-eligible`` (or already
    ``promoted``), and a best dev trial the verdict calls eligible. ``store.best_dev_eligible``
    answers the second under ``store.DSR_POLICY`` (phase 4), so this section says what the gate
    says and cannot drift from it -- which is the point of reading the derived verdict here
    rather than the recorded ``eligible`` column, which was frozen at a 0.95 bar and an N of
    whatever day the trial ran.

    A method whose best trial *is* derived-eligible but whose status still reads ``rejected`` is
    listed separately and by name: it is not promotable now, and the one command that moves it is
    ``lab reevaluate <id>`` (phase 4), which takes the ``rejected -> dev-eligible`` edge. **Not
    ``lab run``** -- that refuses a method whose variants already have dev trials, so telling the
    reader to run it would send them into a refusal.

    Only methods that have a dev trial are asked, so the derivation runs 23 times on the
    committed database rather than 37.

    **Since 2026-10-09 the dev gate is not the last word, and this section says so.**
    ``lab promote`` also refuses a method that lost a majority of its walk-forward folds, or whose
    variant that would be pre-registered lost them on its own curve, or whose kin has already
    failed the test window (``lab/hardgate.py``). Listing such a method under
    "Promotable now (`lab promote` would take these)" would be a lie about exactly the methods
    this section exists to explain. So each dev-eligible method appears in one of two places and
    never both: **taken**, with its fold record and its kin state on the same line; or **refused**,
    with the gate's own sentence on the line beneath it. That is the whole of R7 -- "why can
    nothing be promoted" becomes answerable from ``lab status`` alone, with no second command and
    no reading of the source.
    """
    if gates is None:
        gates = _hard_gate_states(conn)
    ready: list[str] = []
    refused: list[str] = []
    held: list[str] = []
    for m in conn.execute(
        "SELECT * FROM methods m WHERE EXISTS "
        "(SELECT 1 FROM trials t WHERE t.method_id = m.id AND t.window = 'dev') ORDER BY m.id"
    ).fetchall():
        best = store.best_dev_eligible(conn, m["id"])
        if best is None:
            continue
        if m["status"] in ("dev-eligible", "promoted"):
            v = store.verdict(conn, best)
            head = (
                f"    {m['id']:<6} {best['candidate_id']:<28} MAR {fmt_num(best['mar'])}  "
                f"DSR {fmt_num(v.dsr, 3)} at N={v.n} ({v.policy})"
            )
            if m["status"] == "promoted":
                # Already pre-registered: the promise is written and is not re-opened (D3).
                ready.append(f"{head}  (already pre-registered)")
                continue
            record, why = gates.get(m["id"], ("hard gate not evaluated", None))
            if why is None:
                # `record` is `hardgate.summary` whole -- "4 of 4 folds; kin clean" -- so the kin
                # state is already in it. Appending ", kin clean" here would print it twice.
                ready.append(f"{head}  {record}")
            else:
                detail = why if record == why else f"{record}; {why}"
                refused.append(head)
                refused.append(f"           {detail}")
        else:
            # `lab reevaluate` takes exactly one edge, `rejected -> dev-eligible`
            # (store.reevaluate_method; TRANSITIONS has no edge out of `test-failed` at all).
            # Offering it for a test-failed method advertised a way back that does not exist --
            # and in the one direction that would matter, since un-failing a method would
            # unblock the kin check on everything related to it.
            if m["status"] == "rejected":
                nudge = f"`lab reevaluate {m['id']}` re-judges it and moves it to dev-eligible"
            else:
                nudge = (
                    "final -- the lab has no edge out of this status, so nothing re-judges it. "
                    "A disproven configuration never gets a second look, on any window"
                )
            held.append(
                f"    {m['id']:<6} {best['candidate_id']:<28} status {m['status']!r}: {nudge}"
            )
    out = ["  Promotable now (`lab promote` would take these):"]
    out += ready or ["    (none)"]
    if refused:
        out.append(
            "  Refused by the hard gate (dev-eligible, but `lab promote` exits 2 on these -- it "
            "wants a majority of walk-forward folds, won by the picks and by the variant it would "
            "pre-register, and no kin -- family, ancestry, blend ingredient or behaviour -- that "
            "has test-failed; there is no override):"
        )
        out += refused
    if held:
        out.append("  Eligible on the evidence, held by the status machine:")
        out += held
    return out


def _promotion_path(conn) -> list[str]:
    """The whole promotion-path block: always printed, empty sections included.

    The hard gate runs **once** here, not once per section: ``_promotable_now`` needs it to decide
    what to list, and ``_empty_reason`` needs it to say why the Promoted section is empty, and
    both would otherwise re-derive the same seven answers.
    """
    policy = store.DSR_POLICY
    n = _live_n(conn, policy)
    at = f" at N = {n}" if n is not None else ""
    out = [
        f"Promotion path (dev-eligible -> promoted -> test-passed -> paper), luck bar "
        f"DSR >= {store.DSR_MIN} under policy {policy}{at}:"
    ]
    gates = _hard_gate_states(conn)
    out += _ratchet_warning(conn, _dev_var(conn))
    out += _promotable_now(conn, gates)
    for title, status, why in _PROMOTION_STATUSES:
        rows = conn.execute(
            "SELECT * FROM methods WHERE status = ? ORDER BY id", (status,)
        ).fetchall()
        if rows:
            out.append(f"  {title} ({len(rows)}) -- {why}:")
            for m in rows:
                out.append(f"    {m['id']} {m['name']} ({m['family']}, {m['source_kind']})")
        else:
            out.append(f"  {title}: (none) -- {_empty_reason(conn, status, gates)}")
    out.append(
        f"  Test-window looks used: {store.test_looks(conn)}. One look per configuration, "
        f"pre-registered before it is spent, and never given back (design §3)."
    )
    return out


def _luck_rows(
    conn,
    ns: Sequence[int],
    *,
    var_trials: float,
    rank_at: int,
    limit: int,
) -> list[tuple[object, list[float | None]]]:
    """Every dev trial with a recorded DSR, re-evaluated at each N in ``ns``.

    Ranked by the DSR at ``rank_at`` -- the live policy's N -- highest first, ties by trial
    number, so the order is a property of this function and not of the insertion order.

    The 54 P7a seed trials carry ``dsr IS NULL`` by construction (``seed.py``: "P7a reported it
    for one row only") and are skipped. There is nothing to re-evaluate for them, and putting a
    number where the record has none is the opposite of what this command is for.
    """
    scored: list[tuple[object, list[float | None], float]] = []
    for r in conn.execute(
        "SELECT * FROM trials WHERE window = 'dev' AND dsr IS NOT NULL AND sharpe IS NOT NULL "
        "ORDER BY n"
    ).fetchall():
        common = dict(
            sharpe_daily=float(r["sharpe"]) / math.sqrt(252),
            dsr_at_run=float(r["dsr"]),
            n_at_run=int(r["n_trials_at_run"]),
            var_trials=var_trials,
        )
        at = [recover_dsr(n_trials=n, **common) for n in ns]
        rank = recover_dsr(n_trials=rank_at, **common)
        scored.append((r, at, -1.0 if rank is None else rank))
    scored.sort(key=lambda x: (-x[2], int(x[0]["n"])))  # type: ignore[index]
    rows = [(r, at) for r, at, _ in scored]
    return rows if limit <= 0 else rows[:limit]


def _luck(conn, args) -> int:
    """``lab luck``: the dev leaderboard under every N policy, side by side. Read-only.

    It opens no research store, runs no backtest, inserts no row and spends no test-window look.
    That is the point. Decision D1 moved the threshold and deliberately left the N where it was,
    so the second lever is built, measured and *not pulled* -- and this is the instrument that
    shows what pulling it would do, against the committed database, without editing
    ``store.DSR_POLICY`` and re-running anything.

    What it is not: a verdict. The verdict is ``store.verdict``, which recomputes exactly from
    ``trial_moments``. The columns here are recovered from the recorded columns by inverting each
    trial's own per-trial constant at the N it ran at -- so the ``recorded`` column reproduces the
    database exactly and the other columns move only the multiple-testing count.
    """
    live = store.DSR_POLICY
    counts = _n_counts(conn)
    var = _dev_var(conn)
    out: list[str] = [
        "lab luck -- the dev leaderboard under each N policy (read-only: nothing is written)",
        "",
        f"dev trials {store.dev_trial_count(conn)}  ·  test-window looks used "
        f"{store.test_looks(conn)}  ·  luck bar {store.DSR_LABEL}",
        f"live policy: {live}  (store.DSR_POLICY -- changing the N is this one constant)",
        "",
        "The N each policy resolves to, and what clears the bar there:",
    ]
    ns: list[int] = []
    labels: list[str] = []
    for name, count, why in counts:
        mark = "   <- live" if name == live else ""
        if count is None:
            out.append(f"  {name:<12} N = ?      unavailable here: {why}{mark}")
            continue
        n = int(count.n)  # type: ignore[attr-defined]
        if var is None:
            out.append(f"  {name:<12} N = {n:<6d}{mark}")
        else:
            clears = _eligible_at(conn, n, var)
            out.append(
                f"  {name:<12} N = {n:<6d} SR* {sr_star(n, var):.6f}/day   {len(clears)} "
                f"candidate(s) clear {store.DSR_LABEL}{mark}"
            )
            if clears:
                out.append(f"  {'':<12} {', '.join(clears)}")
        out.append(f"  {'':<12} evidence: {_evidence(count)}")
        ns.append(n)
        labels.append(name)
    # --at columns are never deduplicated against a policy that happens to resolve to the same N:
    # the reader asked for a column at a literal N and gets one, labelled by the N.
    extra = [int(n) for n in (args.at or ())]
    for n in extra:
        ns.append(n)
        labels.append(f"N={n}")
    if extra and var is not None:
        out.append("")
        out.append(
            "  at a literal N:  "
            + "  ·  ".join(f"N={n} -> {len(_eligible_at(conn, n, var))} clear" for n in extra)
        )

    if var is None or not ns:
        out += [
            "",
            "No leaderboard: "
            + (
                "fewer than two dev trials carry a Sharpe, so there is no trial-Sharpe variance "
                "to deflate by."
                if var is None
                else "no policy resolved to an N on this database and no --at N was given."
            ),
        ]
        print("\n".join(out))
        return 0

    rank_at = next(
        (int(c.n) for name, c, _ in counts if name == live and c is not None),  # type: ignore[attr-defined]
        ns[0],
    )
    sharpes = len(store.dev_daily_sharpes(conn))
    out += [
        "",
        f"Trial-Sharpe variance now: {var:.6e} (sd {math.sqrt(var):.6f}) over {sharpes} dev "
        f"trials carrying a Sharpe.",
        "",
        f"Dev leaderboard, each recorded DSR re-evaluated at each N, ranked by {live} "
        f"(N={rank_at}).",
        "Trials with no recorded DSR (the P7a seed import) are not listed: there is nothing to "
        "re-evaluate.",
        "",
        "  "
        + f"{'candidate':<28}{'N@run':>7}{'recorded':>10}"
        + "".join(f"{lab:>12}" for lab in labels)
        + "   other failed conditions",
    ]
    for r, at in _luck_rows(conn, ns, var_trials=var, rank_at=rank_at, limit=int(args.limit)):
        others = "; ".join(_owner_misses(r))  # type: ignore[index]
        out.append(
            "  "
            + f"{r['candidate_id']:<28}{int(r['n_trials_at_run']):>7}"  # type: ignore[index]
            + f"{fmt_num(r['dsr'], 3):>10}"  # type: ignore[index]
            + "".join(f"{fmt_num(v, 3):>12}" for v in at)
            + f"   {others or 'none'}"
        )
    out += [
        "",
        f"A cell at or above {store.DSR_MIN} with 'none' in the last column is a candidate that N "
        f"would admit.",
        "The `recorded` column is this same recovery evaluated at each trial's own N@run, so it "
        "reproduces the",
        "database exactly; the other columns move nothing but the multiple-testing count. The "
        "verdict the gate",
        "uses is store.verdict, which recomputes from trial_moments where `lab remeasure` has "
        "recovered them.",
        "",
        "Nothing was written and no test-window look was spent.",
    ]
    print("\n".join(out))
    return 0


def _show(conn, args) -> int:
    m = store.get_method(conn, args.method)
    if m is None:
        raise store.LabError(f"no method {args.method}")
    print(f"{m['id']} {m['name']}  [{m['status']}]  family {m['family']}  source {m['source_kind']} {m['source_ref']}")
    if m["parent_id"]:
        print(f"parent: {m['parent_id']}")
    print(f"\nHypothesis:\n{m['hypothesis']}\n")
    if m["blocked_on"]:
        print(f"Blocked on: {m['blocked_on']}\n")
    print("Trials:")
    for t in store.trials_of(conn, m["id"]):
        print(
            f"  #{t['n']} {t['candidate_id']} [{t['window']}] {t['start']}..{t['end']}: return "
            f"{fmt_signed_pct(t['total_return'])} vs SPY TR {fmt_signed_pct(t['spy_tr_return'])}, CAGR "
            f"{fmt_signed_pct(t['cagr'])}, maxDD {fmt_pct(t['max_drawdown'])}, PF {fmt_pf(t['profit_factor'])}, "
            f"trades {t['trades']}, Sharpe {fmt_num(t['sharpe'])}, MAR {fmt_num(t['mar'])}, DSR "
            f"{fmt_num(t['dsr'], 3)} (N={t['n_trials_at_run']}), worst year {t['worst_year']} "
            f"{fmt_signed_pct(t['worst_year_return'])}; {'ELIGIBLE' if t['eligible'] else 'failed: ' + t['failed']}"
        )
        # A funded trial needs a second line, because the first one is not a return. Once money
        # goes in after the start, `total_return` and `cagr` count the owner's own deposits as
        # gains -- 10.7821 beside an `mwr` of 0.0764 on one measured run. `mwr` is what the money
        # actually earned, and `spy_tr_mwr` is the only honest thing to read it against: the same
        # dollars, on the same days, put into SPY TR instead. None for every unfunded trial, which
        # is the normal and definite answer for all 128 recorded ones -- so no line is printed.
        f = store.funding_of(conn, t["n"])
        if f is not None:
            print(
                f"      funded: your money earned {fmt_signed_pct(f['mwr'])} a year vs "
                f"{fmt_signed_pct(f['spy_tr_mwr'])} for the same deposits put into SPY TR "
                f"({f['deposits_n']} deposits, {f['schedule']}); the return and CAGR above count "
                f"those deposits as gains"
            )
    # The walk-forward record this method's last `lab run` recorded (store.method_folds, schema
    # v7). None -- so no line -- for a method that has not run, and for every method that ran
    # before the table existed: the migration backfills nothing, because a past run's record
    # cannot be recomputed as it read (store._v6_to_v7).
    #
    # Printed through `hardgate.FoldVerdict.from_row`, which is the exact inverse of what the run
    # wrote, so this line and the one `lab run` printed are the same sentence from the same code.
    folds_row = store.latest_folds(conn, m["id"])
    if folds_row is not None:
        from seer_engine.lab import hardgate

        v = hardgate.FoldVerdict.from_row(folds_row)
        print(f"\nWalk-forward, recorded at the run of {folds_row['run_at']}: {v.line()}")
    if m["verdict"]:
        print(f"\nVerdict: {m['verdict']}")
    if m["analysis"]:
        print(f"\nAnalysis:\n{m['analysis']}")
    return 0


def _run(conn, args) -> int:
    import json

    from seer_engine.lab import hardgate, runner
    from seer_engine.lab.method import discover

    # A survivorship-check store says so in its manifest; refuse it before discovering the method
    # or paying for a full load. runner.run_method refuses it again on the loaded data.
    try:
        purpose = research.declared_purpose(Path(args.store))
    except ValueError:
        purpose = None  # missing or unreadable: research.load_store below names the problem
    if purpose is not None:
        raise runner.survivorship_refusal(f"lab run {args.method}", purpose)
    methods = discover()
    if args.method not in methods:
        raise store.LabError(f"no method file for {args.method} in seer_engine/lab/methods/")
    method, path = methods[args.method]
    # getattr, not args.amend: `_run` is also called with a hand-built Namespace (the hard-gate
    # tests do), exactly as `allow_coverage` is read below. The flag defaults to False either way.
    amend = bool(getattr(args, "amend", False))
    amendment = runner.preflight(conn, method, path, amend=amend)
    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    t0 = time.perf_counter()
    try:
        data = research.load_store(Path(args.store))
    except FileNotFoundError as e:
        raise store.LabError(
            f"research store {args.store} is missing {e.filename or e}; build it with "
            "`python -m seer_engine research_store`"
        ) from e
    log.info("research store %s loaded (%.1fs)", data.fingerprint[:12], time.perf_counter() - t0)
    # Decision D10 (lab/hardgate.py): the dev store is pinned to the prices the lab's benchmark
    # was measured on. A store whose price fingerprint differs is refused here, before any
    # backtest, so a rebuilt store cannot slip into the record unannounced -- every trial it
    # produced would be one the hard gate refuses as incomparable. No flag skips this.
    hardgate.pin_dev_store(conn, data.price_fingerprint)
    # The second checkpoint: runner.preflight ran before the store existed and could not see the
    # panel. Nothing here is reached for a price-only method.
    floor = float(getattr(args, "allow_coverage", coverage.MIN_DEV_COVERAGE))
    cov = runner.preflight_data(data, method, min_coverage=floor)
    if cov is not None:
        print(coverage.format_report(cov, floor=floor))
        if floor < coverage.MIN_DEV_COVERAGE:
            print(
                f"--allow-coverage {floor:.2f}: {method.id} runs against a panel that can rank on "
                f"{cov.fraction:.1%} of the dev window, below the "
                f"{coverage.MIN_DEV_COVERAGE:.0%} floor. These trials measure the panel, not the "
                "hypothesis, and the method id is spent either way."
            )
    done = runner.run_method(
        conn, method, path, data, git_sha=runner.git_head(config.REPO_ROOT), amend=amend
    )
    ran = done.ran
    status = store.get_method(conn, method.id)["status"]
    log.info("%s: %d trial(s) recorded, status %s (%.1fs)", method.id, len(ran), status, time.perf_counter() - t0)
    _show(conn, argparse.Namespace(method=method.id))
    print(f"\nLab N (dev trials) is now {store.dev_trial_count(conn)}; test-window looks used: {store.test_looks(conn)}")
    # The run's walk-forward verdict, printed from the value that was just recorded (R1). This is
    # the part a researcher never used to see until `lab promote`, by which time the method id was
    # spent and the dev write-up was already written.
    #
    # It ANNOTATES; it does not gate (hardgate D15, store._FOLDS_TABLE). `done.verdict.note()` is
    # the single source of that sentence, and `lab show` prints the same one back off the row, so
    # the two can never drift. Nothing below refuses anything: a lost majority is a warning here
    # and a refusal at `lab promote`.
    v = done.verdict
    print(f"\nWalk-forward on the lab's shared folds: {v.line()}")
    print(f"  {v.note()}")
    for p in json.loads(v.picks_json):
        got = fmt_signed_pct(p["got"]) if p["got"] is not None else "-"
        bench = fmt_signed_pct(p["bench"]) if p["bench"] is not None else "-"
        mark = "-" if p["beat"] is None else ("won" if p["beat"] else "lost")
        print(
            f"  fold {p['fold']}  train to {p['train_end']}, score {p['eval_start']}.."
            f"{p['eval_end']}: {p['picked'] or '(no variant had enough history)'} "
            f"{got} vs SPY TR {bench}  {mark}"
        )
    print(
        "  Folds share training data, so they are a sanity check, never a significance test, and "
        "nothing here enters a DSR."
    )
    if amendment is not None:
        g = store.gate(conn)
        seq = len(store.amendments_of(conn, method.id))
        print(
            f"\n{method.id} amendment {seq} recorded: {len(ran)} trial(s) under {method.id}'s own "
            f"id, so no method id was spent."
        )
        print(f"  added           {amendment.added.isoformat()}")
        print(f"  why             {amendment.why.strip()}")
        print(f"  file sha        {store.latest_source_sha(conn, method.id)}")
        print(f"  luck gate       N = {g.n} (policy {g.policy})")
        print(
            f"  status          {status} (unchanged -- an amendment appends trials, it never moves "
            f"a verdict; `lab reevaluate {method.id}` is the one door on rejected -> dev-eligible)"
        )
    return 0


def _promote(conn, args) -> int:
    """`lab promote M0007`: pre-register the best dev-eligible variant and move it to promoted.

    Writes one markdown file and one status transition. It loads no research store, runs no
    backtest and inserts no trial, so the test-window look count it prints is the one it found.

    **The hard gate runs first.** `hardgate.check` refuses a method that lost a majority of its
    walk-forward folds, that is scoreable on fewer folds than the geometry yields, or whose
    kin -- family, ancestry, blend ingredients or behaviour (hardgate D4, D12, D14) -- already
    reads `test-failed`. It raises `store.LabError`, which `run` turns
    into exit 2, and it raises *before* `prereg.promote_method` writes the file or moves the
    status -- so a refused promote leaves the repository and the database byte-identical. There
    is no flag that skips it.

    `prereg.promote_method` has exactly one production caller, and this is it. A second caller
    must call `hardgate.check` too.

    Like every other `lab` subcommand, the global `--dry-run` is ignored: there is no roll-back
    half of this to show, and a dry run that printed a pre-registration without writing it would
    be exactly the artefact design §3 exists to prevent.
    """
    from seer_engine.lab import hardgate, prereg
    from seer_engine.lab.runner import git_head

    hardgate.check(conn, args.method)

    done = prereg.promote_method(
        conn,
        args.method,
        git_sha=git_head(config.REPO_ROOT),
        directory=None if args.dir is None else Path(args.dir),
    )
    p = done.prereg
    rel = prereg.repo_path(done.path)
    print(f"wrote {rel}" if done.wrote_file else f"{rel} already pre-registers {p.candidate}")
    print(f"{p.method} is {done.status}" + ("" if done.moved_status else " (already)"))
    print(f"  candidate      {p.candidate}  (dev trial #{p.dev_trial})")
    print(f"  config digest  {p.config_digest}")
    print(f"  dev window     {p.dev_window}  MAR {p.mar}  DSR {p.dsr} at N = {p.n_trials_at_run}")
    print(f"  test window    {p.test_window}")
    print(f"  gate           {p.gate}")
    print(f"  folds          {p.folds}")
    print(f"  family         {p.family_state}")
    print()
    print(f"Commit and push {rel} before the look is spent (design §3):")
    print(f"    git add {rel}")
    print(f"    git commit -m 'lab: pre-register {p.candidate} for the test window'")
    print(f"    python -m seer_engine lab test {p.candidate}")
    print(f"\ntest-window looks used: {store.test_looks(conn)}")
    return 0


def _reevaluate(conn, args) -> int:
    """`lab reevaluate [M0022 ...]`: re-judge recorded dev trials against the current luck bar
    and move anything the moved bars were blocking to dev-eligible.

    No research store is loaded, no backtest runs, no trial row is inserted: this reads the dev
    trials the lab already has, re-decides every condition for each, and takes at most the one
    edge `rejected -> dev-eligible`. The test window is not touched and the look count it prints
    is the one it found.

    Every trial with a recorded DSR is re-judged **at the gate's current N**, either exactly from
    `trial_moments` or by re-evaluating the recorded DSR there (`store.dsr_at`). A trial whose
    DSR cannot be evaluated at all -- the 54 P7a seed rows, whose `dsr` is NULL by construction --
    fails the luck test, exactly as a new trial with no computable DSR does, and is counted and
    named per method rather than passed over in silence.

    Neither the threshold nor the policy is a flag: the write path always uses `store.DSR_MIN`
    and `store.DSR_POLICY`, so the gate cannot be loosened per invocation. To see what another
    policy would say without changing anything, use the read-only `lab luck`.

    The pairing is deliberate and the names are deliberately not neighbours: **`lab reevaluate`
    writes** (it can move a method across `rejected -> dev-eligible`) and **`lab luck` reads**
    (it prints the gate's state and its sensitivity to N, and touches nothing).

    Like every other `lab` subcommand, the global `--dry-run` is ignored. The whole sweep is one
    transaction: either every method it unblocks moves, or none does.
    """
    store.begin_immediate(conn)
    with conn:
        results = store.reevaluate(conn, args.method or None)
    if not results:
        print("nothing to re-evaluate: no method reads rejected")
        return 0
    g = results[0].gate
    print(f"luck bar: {store.DSR_LABEL}   N policy: {g.policy}, N = {g.n}   "
          f"({store.dev_trial_count(conn)} dev trial rows on the books)")
    print()
    moved = 0
    for r in results:
        if r.moved:
            moved += 1
            print(f"  {r.method_id}: {r.status_before} -> {r.status_after}  "
                  f"({', '.join(r.unblocked)})")
        elif r.dev_trials == 0:
            print(f"  {r.method_id}: no dev trial (dropped before running); unchanged")
        elif r.derived == 0:
            print(f"  {r.method_id}: none of its {r.dev_trials} dev trial(s) has an evaluable "
                  f"DSR (the P7a seed recorded none), so each fails the luck test and the "
                  f"verdict is unchanged ({r.status_before})")
        else:
            extra = (
                "" if r.unjudgeable == 0
                else f" ({r.unjudgeable} have no recorded DSR and so fail the luck test)"
            )
            print(f"  {r.method_id}: re-judged {r.derived} of {r.dev_trials} dev trial(s) at "
                  f"N = {r.gate.n} against {store.DSR_LABEL}{extra}; still {r.status_before}")
    print()
    print(f"{moved} method(s) moved rejected -> dev-eligible; "
          f"test-window looks used: {store.test_looks(conn)}")
    if moved:
        # `export-json`, not `stage`: `lab stage` also `git add`s, and the swarm shares one
        # worktree, so this phase stages its own path allowlist by hand (Decision D10).
        print("Re-export the web snapshot with "
              "`python -m seer_engine lab export-json`, and commit it with lab/lab.sqlite.")
    return 0


def _test_plan(method, candidate, pre, store_dir: Path) -> str:
    """What ``lab test`` would do, printed by ``--dry-run``. Nothing is loaded or run.

    ``pre`` is a ``lab.prereg.Prereg`` (phase 3): every field is a ``str`` and it carries no
    path, so the file is named with ``prereg.path_for(pre.method)``.
    """
    from seer_engine.lab.method import config_digest
    from seer_engine.lab.prereg import path_for, repo_path

    return "\n".join((
        f"lab test {candidate.id}  (dry run: nothing is loaded, run or recorded)",
        "",
        f"  method            {method.id} {method.name}  [promoted]",
        f"  variant           {candidate.id}  rules {candidate.rules.id}  allocator "
        f"<{candidate.allocator.id}>",
        f"  config digest     {config_digest(candidate)}",
        f"  pre-registration  {repo_path(path_for(pre.method))}  (committed; digest "
        f"{pre.config_digest[:12]})",
        f"  pre-registered    {pre.candidate} on {pre.date}, for the test window {pre.test_window}",
        f"  test store        {store_dir}",
        "",
        "  the verdict is the five design §1 go-live conditions on the test window:",
        "    " + ", ".join(dev.FAILURE_LABELS),
        "  DSR is recorded, not a condition: the look is pre-registered, so there is nothing to",
        "  deflate. The lab's N does not move -- a test trial is a look, not a search.",
        "",
        "  on a pass  -> test-passed (final), and the promote command is printed",
        "  on a fail  -> test-failed (final)",
        "",
        "  Run it for real without --dry-run. There is exactly one look per configuration and the",
        "  database refuses a second.",
    ))


def _gate_note(conn, tested) -> str:
    """The honest backtest-gate sentence for ``promote --gate-note``.

    Every roster entry's gate note says what the backtest gate actually did; no entry has ever
    passed one. A method that reaches here is the first kind that can say otherwise, and the
    sentence says exactly what it passed and what it still has not: forward paper time.
    """
    t = tested.trial
    d = conn.execute(
        "SELECT * FROM trials WHERE config_digest = ? AND window = 'dev'", (t.config_digest,)
    ).fetchone()
    dev_part = (
        "no recorded dev trial"
        if d is None
        else (f"dev window {d['start']}..{d['end']}: MAR {fmt_num(d['mar'])}, DSR "
              f"{fmt_num(d['dsr'], 3)} at N={d['n_trials_at_run']}, all five conditions met")
    )
    test_part = (
        f"test window {t.start}..{t.end}, one pre-registered look: return "
        f"{fmt_signed_pct(t.total_return)} vs SPY TR {fmt_signed_pct(t.spy_tr_return)}, max DD "
        f"{fmt_pct(t.max_drawdown)}, PF {fmt_pf(t.profit_factor)}, {t.trades} trades, MAR "
        f"{fmt_num(t.mar)} -- all five conditions met"
    )
    return (
        f"Passed the quant backtest gate. {dev_part}; {test_part}. No forward paper record yet: "
        f"design §1 still needs >= {tuning.MIN_PAPER_MONTHS} months of forward paper before real money."
    )


def _promote_argv(method, tested, *, roster_id: str, gate_note: str, lab_db: Path) -> list[str]:
    """The exact ``promote`` command for a passed method. Pure: builds argv, runs nothing.

    ``lab test`` does not call ``commands/promote.py`` in-process. It reads a research store and a
    SQLite file and must stay offline; ``promote`` opens Neon, and the two writes cannot share a
    transaction (``promote.py`` module docstring). Design §6's "never ask" is satisfied by the
    skill running this line immediately, which is what it does.
    """
    sub = method.hypothesis.strip().splitlines()[0].strip()
    if len(sub) > 80:
        sub = sub[:77].rstrip() + "..."
    return [
        "python", "-m", "seer_engine", "promote",
        "--method", method.id,
        "--candidate", tested.trial.candidate_id,
        "--id", roster_id,
        "--name", f"{roster_id} · {method.name}",
        "--sub", sub,
        "--gate-note", gate_note,
        "--lab-db", str(lab_db),
    ]


def _verdict_report(conn, method, tested, *, roster_id: str, lab_db: Path) -> str:
    """What the owner (or the skill) reads after the look: the verdict and the one next step."""
    import shlex

    t = tested.trial
    head = [
        "",
        f"{t.candidate_id} on the test window {t.start}..{t.end}: {tested.status.upper()}",
        f"  return {fmt_signed_pct(t.total_return)} vs SPY TR {fmt_signed_pct(t.spy_tr_return)}, "
        f"CAGR {fmt_signed_pct(t.cagr)}, maxDD {fmt_pct(t.max_drawdown)}, "
        f"PF {fmt_pf(t.profit_factor)}, trades {t.trades}, MAR {fmt_num(t.mar)}",
        f"  DSR {fmt_num(t.dsr, 3)} at N={t.n_trials_at_run} (recorded, not a condition)",
    ]
    if tested.status == "test-failed":
        return "\n".join(head + [
            f"  failed: {t.failed}",
            "",
            "test-failed is final. There is no second look at this configuration, on any window.",
            "Queue a variation (lab idea --source-kind variation --parent "
            f"{method.id} ...) if the evidence supports one, and journal what the test window said",
            "that the dev window did not.",
        ])
    argv = _promote_argv(method, tested, roster_id=roster_id,
                         gate_note=_gate_note(conn, tested), lab_db=lab_db)
    return "\n".join(head + [
        "",
        "test-passed. Next, without asking anyone (design §6): put it on the paper roster under a",
        "new id with its own clock, then stage and commit the lab.",
        "",
        f"  {shlex.join(argv)}",
        "",
        "  lab stage      # writes web/data/lab.json and git-adds it with the database",
        "",
        "promote writes the roster row with no paper_start, so the next paper night freezes the",
        "spec and starts the clock there: the paper record begins at the promotion and claims",
        "nothing earlier. Real money still needs all of design §1.",
    ])


def _test(conn, args) -> int:
    """``lab test <candidate>``: the one counted look at the test window (design §3)."""
    from seer_engine.lab import runner

    method, path, candidate = runner.resolve_candidate(args.candidate)
    store_dir = Path(args.store)
    pre = runner.preflight_test(conn, method, path, candidate)
    if args.dry_run:
        print(_test_plan(method, candidate, pre, store_dir))
        return 0
    t0 = time.perf_counter()
    # Phase 2's idiom: ask the store which window it is for, then ask load_store for exactly
    # that one. load_store compares the two before it reads a single data file, so a dev store
    # here is refused by name; the `window.name != "test"` test below is the second of the two
    # independent noes `run_test` wants, and it names the fix.
    try:
        window = research.declared_window(store_dir)
        if window.name != "test":
            raise store.LabError(
                f"{store_dir} declares the {window.name} window; `lab test` needs the test-window "
                f"store. Build it with `python -m seer_engine research_store --test-window` and "
                f"point --store at {research.TEST_STORE_DIR}"
            )
        data = research.load_store(store_dir, window=window)
    except FileNotFoundError as e:
        raise store.LabError(
            f"test-window research store {store_dir} is missing {e.filename or e}; build it with "
            f"`python -m seer_engine research_store --test-window --store {store_dir}`"
        ) from e
    except ValueError as e:
        raise store.LabError(f"{store_dir}: {e}") from e
    log.info("test store %s loaded, window %s..%s (%.1fs)", data.fingerprint[:12],
             data.window.start, data.window.end, time.perf_counter() - t0)
    tested = runner.run_test(conn, method, path, candidate, data,
                             git_sha=runner.git_head(config.REPO_ROOT))
    _show(conn, argparse.Namespace(method=method.id))
    print(_verdict_report(conn, method, tested,
                          roster_id=args.roster_id or method.id, lab_db=Path(args.db)))
    print(f"\nLab N (dev trials) is still {store.dev_trial_count(conn)}; "
          f"test-window looks used: {store.test_looks(conn)}")
    return 0


def _remeasure(conn, args) -> int:
    """``lab remeasure M0022``: recover the DSR inputs of trials recorded before they were kept.

    Re-runs the method's recorded variants on the **dev** window through the same
    ``dev.run_registry`` path ``lab run`` uses, proves the re-run reproduces each trial's recorded
    Sharpe and DSR, and appends ``trial_moments`` rows -- nothing else. No ``trials`` row is
    inserted, updated or deleted; no status moves; no pre-registration is written.

    The test window is unreachable from here by construction, not by care: a method with a
    ``window='test'`` trial is refused by ``remeasure.preflight`` before this function opens
    anything, ``research.load_store`` is called with no ``window`` so it defaults to ``DEV_WINDOW``
    and refuses a test store by name, and ``remeasure.measure`` refuses a loaded store that is not
    the dev window and calls ``dev.run_registry`` with no window argument at all.

    When every dev trial already has its moments, this prints what it skipped and returns without
    loading a research store: re-loading a 135 MB store and re-running backtests to write nothing
    is not idempotence. (For scale, measured: the store load is ~11s and all 54 P7a seed
    candidates re-run in ~52s. A method's two to five variants are seconds. Nothing here is an
    hours-long job, and no doc in this set may say it is.)
    """
    from seer_engine.lab import remeasure as rm

    if rm.is_seed_id(args.method):
        return _remeasure_seed(conn, args)
    method, path = rm.resolve_method(args.method)
    plan = rm.preflight(conn, method, path)
    if plan.nothing_to_do:
        print(f"{method.id}: every dev trial already has its moments; nothing to do.")
        print("  already recorded: " + ", ".join(f"#{n}" for n in plan.present))
        print(f"\nLab N (dev trials) is still {store.dev_trial_count(conn)}; "
              f"test-window looks used: {store.test_looks(conn)}")
        return 0
    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    t0 = time.perf_counter()
    try:
        data = research.load_store(Path(args.store))
    except FileNotFoundError as e:
        raise store.LabError(
            f"research store {args.store} is missing {e.filename or e}; build it with "
            "`python -m seer_engine research_store`"
        ) from e
    except ValueError as e:
        raise store.LabError(
            f"{args.store}: {e}. `lab remeasure` asks load_store for the dev window and nothing "
            f"else, so a test-window store is refused here rather than re-measured"
        ) from e
    log.info("research store %s loaded (%.1fs)", data.fingerprint[:12], time.perf_counter() - t0)
    report = rm.remeasure(conn, method, path, data)
    print(rm.format_report(report))
    print(f"\nLab N (dev trials) is still {store.dev_trial_count(conn)}; "
          f"test-window looks used: {store.test_looks(conn)}")
    return 0


def _remeasure_seed(conn, args) -> int:
    """``lab remeasure H-P7A``: give the 54 P7a seed trials their DSR inputs, and say what follows.

    The lab's first 54 dev trials were imported from P7a's report files as summary rows, so their
    daily moments were never captured and ``trials.dsr`` is NULL for every one. They count toward
    N all the same -- 54 of the lab's 110 dev trials -- so they pay the full multiple-testing
    penalty and, under the rule that a DSR which cannot be evaluated fails the luck test, can
    never pass it. This re-runs them out of the frozen registry so the luck test they pay for is
    one they actually receive.

    **It writes ``trial_moments`` rows and nothing else.** No ``trials`` row is inserted, updated
    or deleted; ``trials.dsr`` stays NULL on these rows forever; no ``methods.status`` moves; no
    pre-registration is written. The verdict is not recorded here -- it is phase 4's
    ``store.verdict`` computing it from the moments at the current gate N, which is why there is
    no DSR backfill and why re-running this command can never change a recorded number.

    **N does not move.** Adding ``trial_moments`` rows adds no ``trials`` row, so
    ``store.dev_trial_count`` and ``npolicy.effective_n(conn, "all-trials")`` read the same before
    and after; and ``store.dev_daily_sharpes`` reads ``trials.sharpe``, which these rows already
    carry, so the trial-Sharpe variance does not move either. Both are printed at the end, before
    and after, so the invariant is visible rather than merely asserted in a test.

    The test window is unreachable from here by construction, not by care: ``seed_preflight``
    refuses before anything is opened if any seed family has a test trial, ``research.load_store``
    is called with no ``window`` so it defaults to ``DEV_WINDOW`` and refuses a test store by name,
    and ``remeasure_seed`` refuses a loaded store that is not the dev window and reaches
    ``dev.run_registry`` through ``run_chunk``, which has no window argument at all.

    Exit 0 when every re-run reproduced; **1 when any trial diverged** and was therefore not
    written -- the run is not a failure (the rest were written and the finding is printed per
    trial), but it is not a clean success either and an unattended caller should notice.
    """
    from seer_engine.lab import npolicy, remeasure as rm

    only = tuple(x for x in (args.only or "").split(",") if x.strip())
    plan = rm.seed_preflight(conn, args.method, only=only)
    n_before = store.dev_trial_count(conn)
    var_before = store.dev_sharpe_variance(conn)
    if plan.nothing_to_do:
        print(f"{plan.method_id}: every seed trial already has its moments; nothing to do.")
        print("  already recorded: " + ", ".join(f"#{n}" for n in plan.present))
        print(f"\nLab N (dev trials) is still {n_before}; test-window looks used: "
              f"{store.test_looks(conn)}")
        return 0
    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    t0 = time.perf_counter()
    try:
        data = research.load_store(Path(args.store))
    except FileNotFoundError as e:
        raise store.LabError(
            f"research store {args.store} is missing {e.filename or e}; build it with "
            "`python -m seer_engine research_store`"
        ) from e
    except ValueError as e:
        raise store.LabError(
            f"{args.store}: {e}. `lab remeasure` asks load_store for the dev window and nothing "
            f"else, so a test-window store is refused here rather than re-measured"
        ) from e
    log.info("research store %s loaded (%.1fs)", data.fingerprint[:12], time.perf_counter() - t0)
    log.info(
        "re-measuring %d seed trial(s); the P7a trials recorded store %s, this store is %s",
        len(plan.todo), "5451195f", data.fingerprint[:8],
    )

    def progress(index: int, total: int, written: int, blocked: int) -> None:
        log.info("chunk %d/%d committed: %d written, %d blocked", index, total, written, blocked)

    report = rm.remeasure_seed(conn, plan, data, chunk=args.chunk, on_chunk=progress)
    print(rm.format_seed_report(conn, report, rm.seed_verdicts(conn, report)))
    n_after = store.dev_trial_count(conn)
    var_after = store.dev_sharpe_variance(conn)
    print(
        f"\nLab N (dev trials): {n_before} before, {n_after} after "
        f"({npolicy.effective_n(conn, 'all-trials').n} under the all-trials policy); "
        f"trial-Sharpe variance: {var_before!r} before, {var_after!r} after; "
        f"test-window looks used: {store.test_looks(conn)}"
    )
    return 1 if report.blocked else 0


def _costs(conn, args) -> int:
    """``lab costs M0007``: a recorded method at Gotrade's real fees. Report only.

    Every refusal that needs no data -- not a method id, no method file, no dev trial, no such
    variant, a bracket or custom-rate variant with no real-fee twin -- is made before the research
    store is loaded. Then ``real_costs.measure`` runs the variant at both cost models on the dev
    window and ``real_costs.journal`` appends one observation. Nothing else is written: N and the
    test-window looks are printed before and after so the invariant is visible, not just tested.
    """
    from seer_engine.lab import real_costs, runner

    method, _path = real_costs.resolve_method(args.method)
    candidate, trial = real_costs.pick_candidate(conn, method, args.candidate)
    real_costs.twins(candidate)  # refuses a variant with no real-fee twin before the store loads
    # The capital the recorded trial ran on, resolved before the store loads: a trial with none
    # recorded is refused here, and a re-run at the live INITIAL_IDR would not be the trial
    # (trial #90: +545.3% at 10M against +660.2% recorded at 20M).
    capital = runner.recorded_capital(conn, int(trial["n"]))
    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    n_before = store.dev_trial_count(conn)
    looks_before = store.test_looks(conn)
    t0 = time.perf_counter()
    try:
        data = research.load_store(Path(args.store))
    except FileNotFoundError as e:
        raise store.LabError(
            f"research store {args.store} is missing {e.filename or e}; build it with "
            "`python -m seer_engine research_store`"
        ) from e
    except ValueError as e:
        raise store.LabError(
            f"{args.store}: {e}. `lab costs` re-runs the dev window and nothing else, so a "
            f"test-window store is refused here"
        ) from e
    log.info("research store %s loaded (%.1fs)", data.fingerprint[:12], time.perf_counter() - t0)
    cmp = real_costs.measure(
        method, candidate, trial, data,
        contributions=runner.recorded_contributions(conn, int(trial["n"])),
        initial_idr=capital,
    )
    print(real_costs.format_report(cmp))
    with conn:
        entry = real_costs.journal(conn, cmp)
    print(
        f"\njournal entry #{entry} written (an observation on {method.id}). Lab N (dev trials): "
        f"{n_before} before, {store.dev_trial_count(conn)} after; test-window looks used: "
        f"{looks_before} before, {store.test_looks(conn)} after."
    )
    print("Solo: `python -m seer_engine lab stage` so seertrade.site/sera shows it. "
          "A Sera child leaves staging to the coordinator.")
    log.info("%s: lab costs done (%.1fs)", method.id, time.perf_counter() - t0)
    return 0


def _names(conn, args) -> int:
    """``lab names``: how many names the book should hold, swept. Report only.

    Every refusal that needs no data -- a bad ``--ns``, a missing contribution schedule, a
    ``dev.run_registry`` that cannot be fed one -- is made before the research store is loaded.
    Then ``name_count.measure`` runs the grid on the dev window and prints it. Nothing is
    written to the lab database: N and the test-window looks are printed before and after so the
    invariant is visible, not just asserted in a test.
    """
    from seer_engine.lab import name_count

    counts = name_count.check_names(args.ns)
    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    if not args.lump:
        name_count.check_schedule_support()
        name_count.owner_schedule()  # refuse a missing schedule before the store loads
    n_before = store.dev_trial_count(conn)
    looks_before = store.test_looks(conn)
    t0 = time.perf_counter()
    try:
        data = research.load_store(Path(args.store))
    except FileNotFoundError as e:
        raise store.LabError(
            f"research store {args.store} is missing {e.filename or e}. Build it with "
            f"`python -m seer_engine research_store` (about 30 minutes plus a yfinance crawl), "
            f"or point --store at a checkout that already has one -- `.research/` is gitignored, "
            f"so a fresh worktree never does"
        ) from e
    except ValueError as e:
        raise store.LabError(
            f"{args.store}: {e}. `lab names` sweeps the dev window and nothing else, so a "
            f"test-window store is refused here"
        ) from e
    log.info("research store %s loaded (%.1fs)", data.fingerprint[:12], time.perf_counter() - t0)
    sweep = name_count.measure(
        data, ns=counts, control=not args.gotrade_only, lump=args.lump
    )
    print(name_count.format_report(sweep))
    if args.csv is not None:
        written = name_count.write_csv(sweep, Path(args.csv))
        print(f"\ngrid written to {written}")
    print(
        f"\nnothing was recorded. Lab N (dev trials): {n_before} before, "
        f"{store.dev_trial_count(conn)} after; test-window looks used: {looks_before} before, "
        f"{store.test_looks(conn)} after. No journal entry, so seertrade.site/sera is unchanged "
        f"and `lab stage` is not needed."
    )
    log.info("lab names: %d runs done (%.1fs)", len(sweep.points), time.perf_counter() - t0)
    return 0


def _turnover(conn, args) -> int:
    """``lab turnover``: what Gotrade charges a book for trading often. Report only.

    Every refusal that needs no arithmetic -- a bad cadence, a turnover outside (0, 1], a
    nonsensical horizon or rate -- is made first, so a typo costs nothing. Then
    ``turnover.measure`` prices the grid, which is pure arithmetic over ``sim.costs.fee_parts``:
    no research store is opened and no simulator runs, which is the whole point of the item this
    answers -- the number arrives before the model is built, not after.

    Nothing is written to the lab database. N and the test-window looks are printed before and
    after so the invariant is visible on the terminal, not merely asserted in a test.
    """
    from seer_engine.lab import turnover

    cadences = turnover.check_cadences(args.cadence)
    names = turnover.check_names(args.names)
    churns = turnover.check_churns(args.churn)
    years = turnover.check_years(args.years)
    usd_idr = turnover.check_usd_idr(args.usd_idr)
    growth = turnover.check_growth(args.growth)
    n_before = store.dev_trial_count(conn)
    looks_before = store.test_looks(conn)
    t0 = time.perf_counter()
    sweep = turnover.measure(
        cadences=cadences, names=names, churns=churns,
        years=years, usd_idr=usd_idr, growth=growth,
    )
    print(turnover.format_report(sweep))
    if args.csv is not None:
        written = turnover.write_csv(sweep, Path(args.csv))
        print(f"\ngrid written to {written}")
    print(
        f"\nnothing was recorded. Lab N (dev trials): {n_before} before, "
        f"{store.dev_trial_count(conn)} after; test-window looks used: {looks_before} before, "
        f"{store.test_looks(conn)} after. No journal entry, so seertrade.site/sera is unchanged "
        f"and `lab stage` is not needed."
    )
    log.info("lab turnover: %d cells priced (%.1fs)", len(sweep.points), time.perf_counter() - t0)
    return 0


def _comparability_warnings(conn, bench_n: int, rows, wanted: set[str]) -> list[str]:
    """One line per method whose recorded curves cannot be compared with the benchmark's (D10).

    ``lab regime`` and ``lab walkforward`` are reports: they decide nothing, so on the condition
    the hard gate refuses they **warn** and keep printing. A report that refused would hide the
    very record its reader came to look at. The test is the gate's own
    (``hardgate.mismatches``), against the benchmark row the report itself is using, over the
    rows the report itself will print -- so a warning and a refusal can never disagree about
    which method is incomparable.

    ``rows`` need ``n``, ``method_id`` and ``candidate_id``; the benchmark's own row is skipped,
    and so is every method outside ``wanted`` when ``wanted`` is non-empty.
    """
    from seer_engine.backtest import regime
    from seer_engine.lab import hardgate

    by_method: dict[str, list] = {}
    for r in rows:
        if r["candidate_id"] == regime.BENCH_CANDIDATE:
            continue
        if wanted and r["method_id"] not in wanted:
            continue
        by_method.setdefault(str(r["method_id"]), []).append(r)
    out: list[str] = []
    for mid, trials in sorted(by_method.items()):
        problems = hardgate.mismatches(conn, bench_n, trials)
        if problems:
            out.append(
                f"WARNING {mid} is not comparable with {regime.BENCH_CANDIDATE}: "
                f"{hardgate.describe(problems)}. Its row below is cross-store arithmetic, and "
                f"`lab promote` refuses it (lab/hardgate.py, D10)"
            )
    return out


def _regime(conn, args) -> int:
    """``lab regime``: every recorded dev result, split by whether the market was narrow or broad.

    A report, in the sense ``lab costs`` is a report: it re-runs nothing, inserts no trial, moves
    no status and spends no look. Recorded curves (``trials.curve_json``) are monthly, so the
    split is arithmetic on rows the lab already has; the research store is opened only to measure
    breadth, which needs member bars.

    A method whose curves were measured on prices other than the benchmark's -- or on prices
    nobody recorded -- gets one ``WARNING`` line above the table and its row anyway (D10 in
    ``lab/hardgate.py``): a report warns, the gate refuses.
    """
    import json

    from seer_engine.backtest import regime
    from seer_engine.lab import hardgate

    rows = [
        r for r in conn.execute(
            "SELECT n, method_id, candidate_id, start, end, curve_json FROM trials "
            "WHERE window = 'dev' AND curve_json IS NOT NULL ORDER BY method_id, n"
        )
    ]
    bench = next((r for r in rows if r["candidate_id"] == regime.BENCH_CANDIDATE), None)
    if bench is None:
        raise store.LabError(
            f"no {regime.BENCH_CANDIDATE} dev trial to compare against; the breadth panel needs "
            f"the recorded SPY buy-and-hold curve as its benchmark"
        )
    wanted = {m.upper() for m in args.method}
    if wanted:
        known = {r["method_id"] for r in rows}
        missing = sorted(wanted - known)
        if missing:
            raise store.LabError(f"no dev trial for {', '.join(missing)}")

    t0 = time.perf_counter()
    try:
        data = research.load_store(Path(args.store))
    except (ValueError, FileNotFoundError) as e:
        raise store.LabError(f"{args.store}: {e}") from e
    bench_curve = [(date.fromisoformat(d), float(v)) for d, v in json.loads(bench["curve_json"])]
    spread = regime.breadth(data.market, [d for d, _ in bench_curve])
    label = regime.labels(spread)
    counts = {r: sum(1 for x in label.values() if x == r) for r in regime.REGIMES}
    runs = regime.persistence(spread)
    log.info("breadth measured over %d months (%.1fs)", len(label), time.perf_counter() - t0)

    funded = sum(1 for r in rows if store.funding_of(conn, int(r["n"])) is not None)
    if funded:
        print(f"{funded} of these trials were funded with the owner's monthly deposits; their "
              f"curves\nhave the deposits removed before slicing, so a deposit is never read as "
              f"a gain.\n")
    print(f"Market breadth on the dev window, {len(label)} months labelled: "
          f"{counts[regime.NARROW]} narrow, {counts[regime.BROAD]} broad.")
    print("A month is NARROW when the index beat the equal-weighted average of its own members")
    print("-- a few big names carried it -- and BROAD otherwise. Returns are annualised within")
    print("each regime's months alone, so they describe where a result came from, not a return")
    print("anyone could have earned.\n")
    warnings = _comparability_warnings(conn, int(bench["n"]), rows, wanted)
    for line in warnings:
        print(line)
    if warnings:
        print()
    head = f"  {'candidate':<26}{'narrow vs SPY':>15}{'broad vs SPY':>15}   {'verdict':<22}"
    print(head)
    print("  " + "-" * (len(head) - 2))
    for r in rows:
        if r["candidate_id"] == regime.BENCH_CANDIDATE:
            continue
        if wanted and r["method_id"] not in wanted:
            continue
        curve = [(date.fromisoformat(d), float(v)) for d, v in json.loads(r["curve_json"])]
        pan = regime.panel(curve, bench_curve, label, hardgate.trial_deposits(conn, r, curve))
        cells, gaps = [], {}
        for name in regime.REGIMES:
            mine, theirs, gap = pan[name]
            if gap is None or mine.months < args.min_months:
                cells.append(f"{'-':>15}")
            else:
                cells.append(f"{fmt_signed_pct(gap):>15}")
                gaps[name] = gap
        print(f"  {r['candidate_id']:<26}{cells[0]}{cells[1]}   {regime.read(gaps):<22}")
    if runs:
        peak_at, peak = max(runs, key=lambda x: x[1])
        pos = sum(1 for _d, v in runs if v > 0)
        print(f"\nPersistence ({regime.PERSIST_MONTHS}-month trailing mean spread): "
              f"{pos} of {len(runs)} windows positive, peak {fmt_signed_pct(peak)} a month "
              f"ending {peak_at}.")
        print("A sustained positive reading is a standing headwind for an equal-weighted or")
        print("beta-stripped book. THIS is the measure that separates eras; the narrow/broad")
        print("month counts above do not -- on them almost every method reads 'pays in both'.")
    print(f"\n{len(label)} months, store {data.fingerprint[:12]}. Nothing was recorded.")
    return 0


#: The era in which the store can price the most of the index -- the buy signal's condition (c).
HIGH_COVERAGE = (date(2009, 1, 1), date(2015, 10, 16))


def _walkforward(conn, args) -> int:
    """``lab walkforward``: the lab's selection rule, scored out of sample many times.

    Report only, and unlike ``lab regime`` it needs no research store at all: recorded trials carry
    monthly curves, so every fold is a date slice of rows already in the database. Nothing is
    written, no status moves, no look is spent.

    A method whose curves were measured on prices other than the benchmark's -- or on prices
    nobody recorded -- gets one ``WARNING`` line above the table and its row anyway (D10 in
    ``lab/hardgate.py``): a report warns, the gate refuses.
    """
    import json

    from seer_engine.backtest import regime
    from seer_engine.lab import hardgate
    from seer_engine.lab import walkforward as wf

    rows = list(conn.execute(
        "SELECT n, method_id, candidate_id, start, end, curve_json FROM trials "
        "WHERE window = 'dev' AND curve_json IS NOT NULL ORDER BY method_id, n"
    ))
    bench_row = next((r for r in rows if r["candidate_id"] == regime.BENCH_CANDIDATE), None)
    if bench_row is None:
        raise store.LabError(
            f"no {regime.BENCH_CANDIDATE} dev trial; walk-forward needs the recorded SPY "
            f"buy-and-hold curve as its benchmark"
        )

    def curve_of(row):
        return [(date.fromisoformat(d), float(v)) for d, v in json.loads(row["curve_json"])]

    bench = curve_of(bench_row)
    kw = {}
    if args.min_train_years is not None:
        kw["min_train_years"] = args.min_train_years
    if args.eval_years is not None:
        kw["eval_years"] = args.eval_years
    the_folds = wf.folds([d for d, _v in bench], **kw)
    if not the_folds:
        raise store.LabError("the recorded benchmark curve is too short to split into folds")

    wanted = {m.upper() for m in args.method}
    by_method: dict[str, list] = {}
    for r in rows:
        if r["candidate_id"] == regime.BENCH_CANDIDATE:
            continue
        if wanted and r["method_id"] not in wanted:
            continue
        by_method.setdefault(r["method_id"], []).append(r)
    if wanted and not by_method:
        raise store.LabError(f"no dev trial for {', '.join(sorted(wanted))}")

    print(f"Walk-forward over {len(the_folds)} folds, {the_folds[0].eval_start} to "
          f"{the_folds[-1].eval_end}. Each fold picks the variant the lab's own rule would have")
    print("named knowing nothing past the train end, then scores it on months it has never seen.")
    print("Folds share training data, so they are a sanity check and never a significance test.\n")
    warnings = _comparability_warnings(conn, int(bench_row["n"]), rows, wanted)
    for line in warnings:
        print(line)
    if warnings:
        print()
    head = f"  {'method':<8}{'folds won':>11}{'stable':>9}{'2009-15 edge':>15}   verdict"
    print(head)
    print("  " + "-" * (len(head) + 16))

    fired: list[str] = []
    majorities = 0
    for mid, trials in sorted(by_method.items()):
        curves = {r["candidate_id"]: curve_of(r) for r in trials}
        deps = {
            r["candidate_id"]: hardgate.trial_deposits(conn, r, curves[r["candidate_id"]])
            for r in trials
        }
        rec = wf.Record(mid, wf.evaluate(curves, bench, the_folds, deps))
        best = max(
            (c for c in curves),
            key=lambda c: (wf.measure(curves[c], HIGH_COVERAGE[0], HIGH_COVERAGE[1], deps[c])
                           or wf.Slice(0, None, None, None, None)).mar or -1e9,
        )
        mine = wf.measure(curves[best], *HIGH_COVERAGE, deps[best])
        theirs = wf.measure(bench, *HIGH_COVERAGE)
        edge = (
            None if mine is None or theirs is None or mine.cagr is None or theirs.cagr is None
            else mine.cagr - theirs.cagr
        )
        row = store.get_method(conn, mid)
        eligible = row is not None and row["status"] == "dev-eligible"
        # The SAME kin rule the promote gate uses (hardgate.failed_kin: family union transitive
        # ancestors union blend ingredients and theirs, hardgate D12, union the tested books one
        # of its variants moves with, hardgate D14), not a second query beside it. Decision D9 is
        # what happens when these two disagree: the signal said M0030's family was clean while
        # the gate refused it on ancestry, which is a worse answer than either one alone. That
        # the signal widens with D12 and D14 is recorded as hardgate Decision D13. When the kin
        # cannot be read -- D14 compares curves, and refuses on other or unknown prices (D10) --
        # the reason goes in as the failed kin, so the signal cannot fire on a kin nobody could
        # check, and the report still prints the row.
        if row is None:
            family_failed = None
        else:
            try:
                kin = hardgate.failed_kin(conn, mid)
            except store.LabError as e:
                family_failed = f"kin unknown ({e})"
            else:
                family_failed = ", ".join(kin) if kin else None
        signal, why = wf.buy_signal(eligible, rec, edge, family_failed)
        if signal:
            fired.append(f"{mid}: {why}")
        if rec.majority:
            majorities += 1
        print(f"  {mid:<8}{rec.won:>6} of {len(rec.scored):<3}"
              f"{('yes' if rec.stable else 'no'):>9}"
              f"{(fmt_signed_pct(edge) if edge is not None else '-'):>15}   {why}")

    print(f"\n{majorities} of {len(by_method)} methods beat the benchmark in a majority of folds.")
    if fired:
        print("\n  *** BUY SIGNAL ***")
        for line in fired:
            print(f"  {line}")
        print("  This is the moment survivorship-free price history is worth buying: the free")
        print("  evidence is used up, and the next two things that happen are a counted look and")
        print("  real money. See the explore skill's Promotion step 0b.")
    else:
        print("No buy signal. Survivorship-free price history is not worth buying yet.")
    print("\nNothing was recorded. No research store was opened.")
    return 0


def _shortfall(conn, args) -> int:
    """``lab shortfall``: where one recorded trial's gap to SPY TR over one era went.

    A report in the sense ``lab regime`` and ``lab turnover`` are reports: it re-runs nothing,
    inserts no trial, moves no status and spends no look, and it prints the lab's N and the
    test-window looks before and after so the invariant is visible on the terminal rather than
    merely asserted in a test.

    The one optional read is ``--store``, and it is narrow: the gate symbol's rows out of the
    store's own ``bars.csv``, so the shared SPY 200-day gate's on-share can be measured per era.
    No market is built and no backtest runs. The store is opened only when the recorded
    configuration actually carries that gate, because for a book that does not there is nothing
    for it to say.

    A trial whose curves were measured on prices other than the benchmark's gets a ``WARNING``
    line and its numbers anyway (D10 in ``lab/hardgate.py``): a report warns, the gate refuses.
    ``--against`` is the exception and refuses, because a residual split across two price
    fingerprints is a fabricated number rather than a caveated one.
    """
    from seer_engine.lab import shortfall

    row = shortfall.resolve_trial(conn, args.trial)
    against = None if args.against is None else shortfall.resolve_trial(conn, args.against)
    era = shortfall.DEFAULT_ERA if args.era is None else args.era
    window = shortfall.trial_window(row)
    _label, lo, hi = shortfall.era_bounds(era, window)

    n_before = store.dev_trial_count(conn)
    looks_before = store.test_looks(conn)

    gate = None
    store_given = args.store is not None
    if store_given:
        if shortfall.carries_shared_gate(row["config_text"]):
            t0 = time.perf_counter()
            gate = shortfall.gate_on_share(Path(args.store), window, (lo, hi))
            log.info(
                "gate on-share measured from %s: %.4f whole, %.4f era (%.1fs)",
                args.store, gate.whole, gate.era, time.perf_counter() - t0,
            )
        else:
            log.info(
                "%s carries no shared %s %d-day gate; the store is not read",
                row["candidate_id"], shortfall.GATE_SYMBOL, shortfall.GATE_N,
            )

    report = shortfall.measure(
        conn, row, era, gate=gate, names=args.names, against=against, store_given=store_given
    )
    print(shortfall.format_report(report))
    if args.csv is not None:
        print(f"\nterms written to {shortfall.write_csv(report, Path(args.csv))}")
    print(
        f"\nNothing was recorded. Lab N (dev trials): {n_before} before, "
        f"{store.dev_trial_count(conn)} after; test-window looks used: {looks_before} before, "
        f"{store.test_looks(conn)} after. No journal entry, so seertrade.site/sera is unchanged "
        f"and `lab stage` is not needed."
    )
    return 0


def _survivorship(conn, args) -> int:
    """``lab survivorship M0069 [M0007 ...]``: recorded methods on the survivorship-check store.

    Report only. Every refusal that needs no bars -- method ids, files, recorded trials, capital,
    funding, the benchmark geometry, the two stores' manifest purpose -- is made before either
    store loads. The dev store is loaded, run and freed before the survivorship-check store is
    loaded. Nothing is written except one observation per method (none with --no-journal); N and
    the test-window looks are printed before and after so the invariant is visible.
    """
    from seer_engine.lab import hardgate
    from seer_engine.lab import survivorship_check as svc

    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    dev_dir, sv_dir = Path(args.store), Path(args.sv_store)
    plans = svc.plan_methods(conn, args.method)
    geo = hardgate.geometry(conn)
    svc.check_stores(dev_dir, sv_dir)
    n_before = store.dev_trial_count(conn)
    looks_before = store.test_looks(conn)
    t0 = time.perf_counter()
    dev_run = svc.measure_store(conn, plans, dev_dir, survivorship=False, bench=geo.bench)
    sv_run = svc.measure_store(conn, plans, sv_dir, survivorship=True, bench=geo.bench)
    reports = svc.compare(plans, dev_run, sv_run, geo)
    for rep in reports:
        print(svc.format_report(rep, dev_run, sv_run, len(geo.folds)))
        print()
    print("summary (best recorded variant by MAR; dev -> survivorship-check):")
    for rep in reports:
        print(f"  {svc.summary_line(rep)}")
    if args.csv is not None:
        written = svc.write_csv(reports, dev_run, sv_run, Path(args.csv))
        print(f"\ngrid written to {written}")
    if args.no_journal:
        tail = "No journal entry (--no-journal), so `lab stage` is not needed."
    else:
        with conn:
            entries = [svc.journal(conn, rep) for rep in reports]
        tail = (
            f"journal entries {', '.join(f'#{e}' for e in entries)} written (one observation per "
            f"method). Solo: `python -m seer_engine lab stage` so seertrade.site/sera shows them."
        )
    print(
        f"\nNo trial was recorded. Lab N (dev trials): {n_before} before, "
        f"{store.dev_trial_count(conn)} after; test-window looks used: {looks_before} before, "
        f"{store.test_looks(conn)} after. {tail}"
    )
    log.info("lab survivorship: %d method(s) done (%.1fs)", len(reports), time.perf_counter() - t0)
    return 0


def _kin(conn, args) -> int:
    """``lab kin M0133 [M0007 ...]``: every variant's own resemblance to the failed books.

    Report only, and the reason it exists is in ``hardgate.kin_matrix``'s docstring: the gate
    reports one twin per failed method, so a variant that is not the strongest correlator has no
    readable number and a method id was once spent to obtain one. Nothing is written, no store is
    opened, and N and the test-window looks are printed either side so the invariant is visible
    rather than merely asserted.
    """
    from seer_engine.lab import hardgate

    n_before = store.dev_trial_count(conn)
    looks_before = store.test_looks(conn)
    bar = hardgate.KIN_CORRELATION
    geo = hardgate.geometry(conn)
    for mid in args.method:
        pairs = hardgate.kin_matrix(conn, mid, geo)
        print()
        if not pairs:
            print(f"{mid}: nothing to compare -- no dev curve, or no test-failed book has one.")
            continue
        failed = sorted({p.failed_id for p in pairs})
        variants = list(dict.fromkeys(p.candidate_id for p in pairs))
        width = max(len(v) for v in variants)
        print(f"{mid}: residual correlation against every test-failed book (the bar is {bar:.2f})")
        print("  " + "variant".ljust(width) + "".join(f"{f:>10}" for f in failed))
        for v in variants:
            cells = ""
            for f in failed:
                rho = next((p.correlation for p in pairs
                            if p.candidate_id == v and p.failed_id == f), None)
                cells += f"{'--' if rho is None else format(rho, '.4f'):>10}"
            print("  " + v.ljust(width) + cells)
        crossing = [p for p in pairs if p.crosses]
        if crossing:
            worst = max(crossing, key=lambda p: p.correlation or 0.0)
            print(f"  KIN: {len(crossing)} pair(s) at or above {bar:.2f}; strongest is "
                  f"{worst.candidate_id} with {worst.failed_id}'s {worst.failed_candidate_id} "
                  f"at {worst.correlation:.4f}.")
            clean = [v for v in variants
                     if not any(p.crosses for p in pairs if p.candidate_id == v)]
            if clean:
                print(f"  Clean variants, measured on their own curve: {', '.join(clean)}.")
        else:
            print(f"  CLEAN: no pair reaches {bar:.2f}.")
        if args.all:
            print("  every pair:")
            for p in sorted(pairs, key=lambda q: -(q.correlation or -1.0)):
                rho = "--" if p.correlation is None else f"{p.correlation:.4f}"
                mark = "  <- kin" if p.crosses else ""
                print(f"    {p.candidate_id} vs {p.failed_id}'s {p.failed_candidate_id}: "
                      f"{rho}{mark}")
    print()
    print(f"recorded dev trials {n_before} -> {store.dev_trial_count(conn)}; "
          f"test-window looks {looks_before} -> {store.test_looks(conn)}. "
          f"Nothing was written and no method id was minted.")
    return 0


def _exposure(conn, args) -> int:
    """``lab exposure M0030 [M0024 ...]``: a method's own picks, apart from what it parks.

    Report only. Every refusal that needs no bars -- the method ids, their files, their recorded
    trials, a bracket-engine variant with no targets to re-weight, the recorded capital and
    funding, an unknown --only id, the benchmark geometry -- is made before the research store is
    loaded. Then four arms per recorded variant run on the dev window and the grid is printed.
    Nothing is written except one observation per method (none with --no-journal); N and the
    test-window looks are printed before and after so the invariant is visible, not just tested.
    """
    from seer_engine.lab import exposure as exp
    from seer_engine.lab import hardgate

    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    plans = exp.plan_methods(conn, args.method, args.only)
    geo = hardgate.geometry(conn)  # the recorded SPY hold: the per-era benchmark, before any load
    n_before = store.dev_trial_count(conn)
    looks_before = store.test_looks(conn)
    t0 = time.perf_counter()
    run, arms = exp.measure_store(conn, plans, Path(args.store), geo.bench)
    reports = exp.compare(plans, arms)
    for rep in reports:
        print(exp.format_report(rep, run))
        print()
    print("summary (best recorded eligible variant by MAR, else the best by MAR):")
    for rep in reports:
        print(f"  {exp.summary_line(rep)}")
    if args.csv is not None:
        written = exp.write_csv(reports, run, Path(args.csv))
        print(f"\ngrid written to {written}")
    if args.no_journal:
        tail = "No journal entry (--no-journal), so `lab stage` is not needed."
    else:
        with conn:
            entries = [exp.journal(conn, rep) for rep in reports]
        tail = (
            f"journal entries {', '.join(f'#{e}' for e in entries)} written (one observation per "
            f"method). Solo: `python -m seer_engine lab stage` so seertrade.site/sera shows them."
        )
    print(
        f"\nNo trial was recorded and no method id was minted. Lab N (dev trials): {n_before} "
        f"before, {store.dev_trial_count(conn)} after; test-window looks used: {looks_before} "
        f"before, {store.test_looks(conn)} after. {tail}"
    )
    log.info("lab exposure: %d method(s) done (%.1fs)", len(reports), time.perf_counter() - t0)
    return 0


def _gate(conn, args) -> int:
    """``lab gate M0030 [M0053 ...]``: what the shared SPY 200-day gate was worth.

    Report only. Every refusal that needs no bars -- the method ids, their files, their recorded
    trials, a bracket-engine variant with no params to walk, the recorded capital and funding, an
    unknown --only id, the benchmark geometry, and the transform's own disagreement with the lab's
    recorded gate-off controls -- is made before the research store is loaded. --dry-run stops
    there. Then one or two arms per recorded variant run on the dev window and the grid is
    printed. Nothing is written except one observation per method (none with --no-journal); N and
    the test-window looks are printed before and after so the invariant is visible, not just
    tested.
    """
    from seer_engine.lab import gate_probe as gp
    from seer_engine.lab import hardgate

    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    if bool(args.method) == bool(args.all):
        raise store.LabError(
            "name at least one method (e.g. `lab gate M0030`) or pass --all, not both and not "
            "neither"
        )
    problems, checked = gp.control_problems()
    if problems:
        raise store.LabError(
            "the gate transform disagrees with the lab's own recorded gate-off controls, so it "
            "cannot be trusted to switch the gate off anywhere else:\n  "
            + "\n  ".join(problems)
        )
    ids = gp.recorded_method_ids(conn) if args.all else args.method
    plans = gp.plan_methods(conn, ids, args.only, gated_only=args.gated_only)
    print(
        f"the gate transform reproduced all {checked} of the lab's recorded gate-off controls "
        f"({', '.join(a for a, _b in gp.CONTROLS)}, and M0030-C50T's core leg against M0030-C50A)"
    )
    print()
    print(gp.format_plan(plans, gated_only=args.gated_only))
    if args.dry_run:
        print("\n--dry-run: no store was opened, no backtest ran and nothing was written.")
        return 0
    geo = hardgate.geometry(conn)  # the recorded SPY hold: the per-era benchmark, before any load
    n_before = store.dev_trial_count(conn)
    looks_before = store.test_looks(conn)
    t0 = time.perf_counter()
    run, arms = gp.measure_store(conn, plans, Path(args.store), geo.bench)
    reports = gp.compare(plans, arms)
    for rep in reports:
        print()
        print(gp.format_report(rep, run))
    print()
    print("summary (best recorded gated variant by MAR, else the best by MAR):")
    for rep in reports:
        print(f"  {gp.summary_line(rep)}")
    print()
    for line in gp.lab_summary(reports):
        print(line)
    if args.csv is not None:
        written = gp.write_csv(reports, run, Path(args.csv))
        print(f"\ngrid written to {written}")
    if args.no_journal:
        tail = "No journal entry (--no-journal), so `lab stage` is not needed."
    else:
        with conn:
            entries = [gp.journal(conn, rep) for rep in reports]
        tail = (
            f"journal entries {', '.join(f'#{e}' for e in entries)} written (one observation per "
            f"method). Solo: `python -m seer_engine lab stage` so seertrade.site/sera shows them."
        )
    # Two numbers, two labels, and neither of them called "Lab N". The ten strings §5.1 puts to
    # the owner print the lab's N as `Lab N` qualified by `(dev trials)`, set to
    # `<dev_trial_count>`. (That label is spelt in two pieces here on purpose: the set's invariant
    # 9 is checked by a `grep -c` for the exact phrase, and this comment must not be an eleventh
    # hit.) The wording names the trial ROW
    # count as the lab's N when the gate actually applies `store.gate(conn).n` -- 354 against 74,
    # measured 2026-10-12. This command is new today, so it is under no obligation to repeat that;
    # it prints the hurdle as the hurdle and the row count as rows. The ten are untouched (plan
    # invariant 9) and this adds no eleventh, so a grep for the misleading wording still returns
    # exactly ten and phase 6's count stays right.
    g_after = store.gate(conn)
    print(
        f"\nNo trial was recorded and no method id was minted. "
        f"Luck hurdle N: {g_after.n} (policy {g_after.policy}) -- unchanged, because this command "
        f"records no trial and mints no method id. "
        f"Dev trial rows: {n_before} before, {store.dev_trial_count(conn)} after. "
        f"Test-window looks used: {looks_before} before, {store.test_looks(conn)} after. {tail}"
    )
    log.info("lab gate: %d method(s) done (%.1fs)", len(reports), time.perf_counter() - t0)
    return 0


def _idea(conn, args) -> int:
    store.begin_immediate(conn)  # the next id and its insert, atomic against parallel sessions
    with conn:
        mid = store.next_method_id(conn)
        store.add_method(
            conn, id=mid, name=args.name, family=args.family, source_kind=args.source_kind,
            source_ref=args.source_ref, hypothesis=args.hypothesis, parent_id=args.parent,
        )
    print(mid)
    return 0


def _note(conn, args) -> int:
    if args.file is None and args.verdict is None:
        raise store.LabError("give --file and/or --verdict")
    with conn:
        if args.file is not None:
            store.append_analysis(conn, args.method, Path(args.file).read_text(encoding="utf-8"))
        if args.verdict is not None:
            store.update_method(conn, args.method, verdict=args.verdict.strip())
    return 0


def _block(conn, args) -> int:
    with conn:
        store.update_method(conn, args.method, status="blocked-data", blocked_on=args.on.strip())
    return 0


def _unblock(conn, args) -> int:
    """``blocked-data -> idea`` (``store.TRANSITIONS``: "the missing data arrived").

    The note is appended to the method's analysis with ``store.append_analysis``, the way
    ``lab note`` records one, together with what the method was blocked on. ``blocked_on`` is
    then cleared, so the analysis is the only place that history survives.
    """
    note = args.note.strip()
    if not note:
        raise store.LabError("give --note: what data arrived and how much of the dev window it covers")
    row = store.get_method(conn, args.method)
    if row is None:
        raise store.LabError(f"no method {args.method}")
    if row["status"] != "blocked-data":
        raise store.LabError(
            f"{args.method} is {row['status']}, not blocked-data; only an idea blocked on data "
            "can be unblocked"
        )
    text = f"Unblocked: the missing data arrived. {note}"
    if row["blocked_on"]:
        text += f"\n\nIt was blocked on: {row['blocked_on']}"
    with conn:
        store.append_analysis(conn, args.method, text)
        store.update_method(conn, args.method, status="idea", blocked_on="")
    print(f"{args.method}: blocked-data -> idea")
    return 0


def _drop(conn, args) -> int:
    with conn:
        store.update_method(conn, args.method, status="rejected", verdict=f"dropped before running: {args.why.strip()}")
    return 0


def _seen(conn, args) -> int:
    if args.find is not None:
        for r in store.seen(conn, args.find):
            print(f"{r['key']}\t{r['method_id'] or '-'}\t{r['note']}")
        return 0
    if not args.key:
        raise store.LabError("give a KEY to record, or --find TEXT")
    with conn:
        added = store.mark_seen(conn, args.key, args.method, args.note)
    print("added" if added else "already seen")
    return 0


def _insight(conn, args) -> int:
    if (args.body is None) == (args.file is None):
        raise store.LabError("give exactly one of --body or --file")
    body = args.body if args.body is not None else Path(args.file).read_text(encoding="utf-8")
    with conn:
        n = store.add_insight(conn, kind=args.kind, title=args.title, body=body, method_id=args.method)
    print(n)
    return 0


def _stage(conn, args) -> int:
    """Write the web snapshot and ``git add`` it with the database, both while holding an
    exclusive lock: a parallel session's half-written transaction can never be what gets
    committed, and the staged ``web/data/lab.json`` is always the export of the staged database.
    The snapshot goes beside the database's own repo (``store.snapshot_path``), so a worktree
    session with ``SEER_LAB_DB`` stages both files in the checkout that owns the database."""
    import subprocess

    path = Path(args.db).resolve()
    snap = store.snapshot_path(path)
    conn.execute("BEGIN EXCLUSIVE")
    try:
        store.write_snapshot(conn, snap)
        out = subprocess.run(
            ["git", "add", "--", str(path), str(snap)], cwd=path.parent, capture_output=True, text=True
        )
    finally:
        conn.rollback()
    if out.returncode != 0:
        raise store.LabError(f"git add {path} {snap} failed: {out.stderr.strip()}")
    print(f"staged {path}")
    print(f"staged {snap}")
    return 0


def _next_id(conn, args) -> int:
    print(store.next_method_id(conn))
    return 0


def _export(conn, args) -> int:
    path = store.export_xlsx(conn, args.out)
    print(path)
    return 0


def _export_json(conn, args) -> int:
    path = Path(args.out) if args.out is not None else store.snapshot_path(args.db)
    if not store.write_snapshot(conn, path):
        log.info("%s already up to date", path)
    print(path)
    return 0


def _seed(conn, args) -> int:
    from seer_engine.lab.seed import seed

    n = seed(conn)
    print(f"seeded {n} trials; N = {store.dev_trial_count(conn)}")
    return 0


_HANDLERS = {
    "status": _status,
    "regime": _regime,
    "walkforward": _walkforward,
    "shortfall": _shortfall,
    "luck": _luck,
    "show": _show,
    "run": _run,
    "promote": _promote,
    "reevaluate": _reevaluate,
    "test": _test,
    "remeasure": _remeasure,
    "costs": _costs,
    "names": _names,
    "turnover": _turnover,
    "survivorship": _survivorship,
    "exposure": _exposure,
    "kin": _kin,
    "gate": _gate,
    "idea": _idea,
    "note": _note,
    "block": _block,
    "unblock": _unblock,
    "drop": _drop,
    "seen": _seen,
    "insight": _insight,
    "stage": _stage,
    "next-id": _next_id,
    "export": _export,
    "export-json": _export_json,
    "seed": _seed,
}
