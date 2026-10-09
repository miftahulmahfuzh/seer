"""``lab costs MNNNN``: a recorded method, re-measured at Gotrade's real fees. Report only.

Every lab method up to M0030 was measured at the lab's flat assumption of 0.1% of each trade
(``TradeRules.cost_rate``). The owner's own Gotrade receipts, stored by Sean, show the real
schedule -- a trading fee with a $0.10 minimum, a small regulatory fee and 11% VAT on both -- and
Sean phase 6 put it in ``sim/costs.py`` behind ``TradeRules.cost_model = "gotrade"``. This module
answers one question for a recorded method: what would its dev-window result have been at those
fees?

**A report, not a trial.** ``measure`` re-runs the method's best recorded dev variant twice
through ``dev.run_registry`` -- once at the flat cost, once at Gotrade's -- and ``journal`` appends
one ``observation`` to the lab journal. No ``trials`` row and no ``trial_moments`` row is written,
no status moves, no pre-registration is touched, so ``store.dev_trial_count`` (the lab's N) and
``store.test_looks`` are exactly what they were. A re-measured result can therefore never make a
method eligible: the only way a real-fee configuration is judged is a new method that
pre-registers it, which ``real_cost_problem`` makes the rule from M0031 on.

**The test window is unreachable.** ``measure`` refuses a store that is not
``research.DEV_WINDOW`` and calls ``dev.run_registry`` with no ``window`` keyword.

**Old methods keep their digests (plan invariant 2).** Nothing here edits a method file or a
recorded configuration; the real-fee twin exists only in memory for the length of one run.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass, fields, replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.dev import FAILURE_LABELS, Candidate, DevRow
from seer_engine.backtest.runner import INITIAL_IDR
from seer_engine.backtest.metrics import fmt_num, fmt_pct, fmt_pf, fmt_signed_pct
from seer_engine.lab import store
from seer_engine.lab.method import METHOD_ID, Method, discover
from seer_engine.sim.rules import TradeRules

REAL_COST_SINCE = 31  # M0031: the first method that must be measured at Gotrade's real fees
FLAT = "flat"
REAL = "gotrade"
REPRO_TOL = 1e-9  # relative: the flat re-run against the recorded trial's total return
_DEFAULT_COST_RATE: Decimal = next(f.default for f in fields(TradeRules) if f.name == "cost_rate")


# --------------------------------------------------------------------------- the M0031 rule


def requires_real_cost(method_id: str) -> bool:
    """True for a lab method id numbered ``REAL_COST_SINCE`` or later (M0031, M0032, ...)."""
    if not isinstance(method_id, str) or METHOD_ID.fullmatch(method_id) is None:
        return False
    return int(method_id[1:]) >= REAL_COST_SINCE


def real_cost_problem(method: Method) -> str | None:
    """Why ``method`` may not run, or None. ``runner.preflight`` raises it as a ``LabError``.

    From M0031 on, every variant must be a book rule set at ``cost_model="gotrade"``: the lab
    measures what the owner would really pay. Methods up to M0030 ran at the flat cost and keep
    it -- their digests are pinned -- and are compared through ``lab costs`` instead.
    """
    if not requires_real_cost(method.id):
        return None
    flat = [
        c.id
        for c in method.candidates
        if c.rules.engine != "book" or getattr(c.rules, "cost_model", FLAT) != REAL
    ]
    if not flat:
        return None
    return (
        f"{', '.join(flat)} would run at the lab's old flat cost of 0.1% a trade. From "
        f"M{REAL_COST_SINCE:04d} on, every variant is measured at Gotrade's real fees "
        f"(cost_model='gotrade'): build it on sim.rules.MONTHLY_HOLD_FRAC_GOTRADE or "
        f"MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE, or on replace(<book preset>, "
        f"cost_model='gotrade') for a rule set with no real-fee preset yet (it runs on dev, but "
        f"`promote` needs a preset of its id). The design-v0 bracket engine has no real-fee model"
    )


# --------------------------------------------------------------------------- what to re-run


def resolve_method(method_id: str) -> tuple[Method, Path]:
    """``(METHOD, its file)`` for a lab method id (``store.LabError`` otherwise)."""
    if not isinstance(method_id, str) or METHOD_ID.fullmatch(method_id) is None:
        raise store.LabError(
            f"{method_id!r} is not a lab method id; `lab costs` takes a method like M0007"
        )
    methods = discover()
    if method_id not in methods:
        raise store.LabError(
            f"no method file for {method_id} in seer_engine/lab/methods/. `lab costs` re-runs the "
            f"committed method file, not a database row. Known: {', '.join(methods) or '(none)'}"
        )
    return methods[method_id]


def pick_candidate(
    conn: sqlite3.Connection, method: Method, candidate_id: str | None = None
) -> tuple[Candidate, sqlite3.Row]:
    """The variant to re-measure and its recorded dev trial.

    Default: the method's best recorded dev trial by MAR (ties: the lower trial number; a trial
    with no MAR ranks last), eligible or not -- the question is what the fees do to the result the
    lab already holds, so the best result is the one worth asking about. ``candidate_id`` names
    another recorded variant.
    """
    trials = [t for t in store.trials_of(conn, method.id) if t["window"] == "dev"]
    if not trials:
        raise store.LabError(
            f"{method.id} has no dev trial; `lab costs` re-measures a method the lab has run. "
            f"Run it with `lab run {method.id}` first"
        )
    if candidate_id is None:
        trial = sorted(
            trials, key=lambda t: (t["mar"] is None, -(t["mar"] or 0.0), int(t["n"]))
        )[0]
    else:
        found = [t for t in trials if t["candidate_id"] == candidate_id]
        if not found:
            known = ", ".join(str(t["candidate_id"]) for t in trials)
            raise store.LabError(
                f"{method.id} has no dev trial for {candidate_id!r}; its dev trials are {known}"
            )
        trial = found[0]
    by_id = {c.id: c for c in method.candidates}
    candidate = by_id.get(str(trial["candidate_id"]))
    if candidate is None:
        raise store.LabError(
            f"{trial['candidate_id']} has a recorded dev trial but is not a variant in "
            f"{method.id}'s method file; the file and the database disagree"
        )
    return candidate, trial


def twins(candidate: Candidate) -> tuple[Candidate, Candidate]:
    """``(flat, real)``: ``candidate`` at the flat 0.1% and at Gotrade's real fees.

    The side the lab recorded is ``candidate`` itself; the other side differs only in
    ``rules.cost_model`` and carries a suffixed id (``-GT`` or ``-FLAT``) so the two rows of one
    ``run_registry`` call can be told apart. Neither is ever recorded.
    """
    rules = candidate.rules
    if rules.engine != "book":
        raise store.LabError(
            f"{candidate.id} runs on the {rules.engine} engine (design §5's bracket simulator), "
            f"which has no real-fee model; `lab costs` measures book methods only"
        )
    if rules.cost_rate != _DEFAULT_COST_RATE:
        raise store.LabError(
            f"{candidate.id} runs at its own cost rate ({rules.cost_rate}), not the lab's flat "
            f"{_DEFAULT_COST_RATE}; there is no flat baseline to compare Gotrade's fees with"
        )
    recorded = getattr(rules, "cost_model", FLAT)
    if recorded == REAL:
        flat = replace(candidate, id=f"{candidate.id}-FLAT", rules=replace(rules, cost_model=FLAT))
        return flat, candidate
    real = replace(candidate, id=f"{candidate.id}-GT", rules=replace(rules, cost_model=REAL))
    return candidate, real


# --------------------------------------------------------------------------- the measurement


@dataclass(frozen=True)
class Side:
    """One run's numbers: the variant at one cost model."""

    model: str  # FLAT | REAL
    candidate_id: str
    total_return: float | None
    cagr: float | None
    max_drawdown: float | None
    profit_factor: float | None
    trades: int
    sharpe: float | None
    mar: float | None
    exposure: float
    costs_usd: float
    cost_drag: float | None
    spy_tr_return: float | None
    spy_tr_cagr: float | None
    beats_spy: bool
    failed: tuple[str, ...]  # dev.FAILURE_LABELS the run misses (the luck test is not re-run)


def side_of(model: str, row: DevRow) -> Side:
    m = row.stats.metrics
    return Side(
        model=model,
        candidate_id=row.candidate.id,
        total_return=m.total_return,
        cagr=m.cagr,
        max_drawdown=m.max_drawdown,
        profit_factor=m.profit_factor,
        trades=int(m.trades),
        sharpe=row.stats.sharpe,
        mar=row.mar,
        exposure=float(row.stats.exposure),
        costs_usd=float(row.stats.costs_usd),
        cost_drag=row.stats.cost_drag,
        spy_tr_return=row.spy_tr.total_return,
        spy_tr_cagr=row.spy_tr.cagr,
        beats_spy=bool(row.beats_spy),
        failed=tuple(row.failed),
    )


@dataclass(frozen=True)
class Comparison:
    """One variant at both cost models, beside the dev trial the lab recorded for it."""

    method_id: str
    method_name: str
    candidate_id: str
    recorded_model: str
    trial_n: int
    recorded_total_return: float | None
    start: date
    end: date
    fingerprint: str
    flat: Side
    real: Side

    @property
    def recorded_side(self) -> Side:
        return self.flat if self.recorded_model == FLAT else self.real

    @property
    def reproduced(self) -> bool | None:
        """Did the re-run at the recorded cost land on the recorded total return? None when either
        number is missing. False means the store or the engine changed since the trial ran: the
        two re-runs still compare with each other, just not with the recorded row."""
        recorded = self.recorded_total_return
        measured = self.recorded_side.total_return
        if recorded is None or measured is None:
            return None
        return abs(measured - recorded) <= REPRO_TOL * max(1.0, abs(recorded))


def measure(
    method: Method,
    candidate: Candidate,
    trial: Mapping[str, Any],
    data: research.ResearchData,
    *,
    contributions: Any = None,
    initial_idr: Decimal = INITIAL_IDR,
) -> Comparison:
    """Run ``candidate`` at both cost models on the dev window. Writes nothing anywhere.

    ``contributions`` is the funding the **recorded** trial ran on -- resolve it with
    ``lab.runner.recorded_contributions(conn, trial["n"])`` and pass it through, so the re-run is
    the same measurement and ``Comparison.reproduced`` means what it says. Measured: re-running a
    funded trial unfunded lands on a different total return, and the report then announces that
    the store or the engine changed when neither did. None -- the default -- is right for every
    trial recorded before the lab was funded, which is all 128 of them.

    ``initial_idr`` is the starting capital the recorded trial ran on, for the same reason --
    resolve it with ``lab.runner.recorded_capital(conn, trial["n"])``. Measured 2026-10-09: the
    flat side of ``lab costs M0011`` read +545.3% at the live 10,000,000 IDR where trial #90
    records +660.2%, because the trial ran at 20,000,000 IDR and whole-share rounding makes the
    capital result-moving (trial-reproducibility analysis M2). The default is the live constant
    only so a caller re-measuring something that is not a recorded trial need not invent one;
    ``commands/lab.py:_costs`` always passes the recorded value.

    Both sides are fed the same schedule and the same capital, so the flat/Gotrade comparison is
    still a comparison of one variant at two fee models and nothing else.
    """
    if data.window != research.DEV_WINDOW:
        w = data.window
        raise store.LabError(
            f"{method.id}: this research store was built for the {w.name!r} window "
            f"({w.start}..{w.end}); `lab costs` re-runs the dev window and nothing else. "
            f"Build it with `python -m seer_engine research_store`"
        )
    flat, real = twins(candidate)
    rows: dict[str, DevRow] = {}

    def on_result(i: int, result: Any, row: DevRow) -> None:
        rows[row.candidate.id] = row

    dev.run_registry(
        data.market, data.dividends, data.spy_dividends, (flat, real),
        on_result=on_result, contributions=contributions, initial_idr=initial_idr,
    )
    f, g = rows[flat.id], rows[real.id]
    return Comparison(
        method_id=method.id,
        method_name=method.name,
        candidate_id=candidate.id,
        recorded_model=getattr(candidate.rules, "cost_model", FLAT),
        trial_n=int(trial["n"]),
        recorded_total_return=None if trial["total_return"] is None else float(trial["total_return"]),
        start=f.start,
        end=f.end,
        fingerprint=str(data.fingerprint),
        flat=side_of(FLAT, f),
        real=side_of(REAL, g),
    )


# --------------------------------------------------------------------------- the two reports


def _usd(x: float) -> str:
    return f"{x:,.2f}"


def format_report(cmp: Comparison) -> str:
    """The terminal report: both runs side by side. Ids and labels are fine here."""
    f, g = cmp.flat, cmp.real
    rows: list[tuple[str, str, str]] = [
        ("total return", fmt_signed_pct(f.total_return), fmt_signed_pct(g.total_return)),
        ("CAGR", fmt_signed_pct(f.cagr), fmt_signed_pct(g.cagr)),
        ("SPY TR return (same fees)", fmt_signed_pct(f.spy_tr_return), fmt_signed_pct(g.spy_tr_return)),
        ("SPY TR CAGR (same fees)", fmt_signed_pct(f.spy_tr_cagr), fmt_signed_pct(g.spy_tr_cagr)),
        ("max drawdown", fmt_pct(f.max_drawdown), fmt_pct(g.max_drawdown)),
        ("profit factor", fmt_pf(f.profit_factor), fmt_pf(g.profit_factor)),
        ("trades", str(f.trades), str(g.trades)),
        ("Sharpe", fmt_num(f.sharpe), fmt_num(g.sharpe)),
        ("MAR", fmt_num(f.mar), fmt_num(g.mar)),
        ("exposure", fmt_pct(f.exposure), fmt_pct(g.exposure)),
        ("fees paid (USD)", _usd(f.costs_usd), _usd(g.costs_usd)),
        ("fee drag (of gross trade P&L)", fmt_pct(f.cost_drag), fmt_pct(g.cost_drag)),
        ("go-live misses (DSR aside)", "; ".join(f.failed) or "none", "; ".join(g.failed) or "none"),
    ]
    width = max(len(r[0]) for r in rows)
    out = [
        f"lab costs {cmp.method_id} -- {cmp.candidate_id} on the dev window {cmp.start}..{cmp.end}, "
        f"research store {cmp.fingerprint[:12]}",
        "report only: no trial row, no moments, no status change; the lab's N and the test-window "
        "looks do not move",
        "",
        f"  {'':<{width}}  {'flat 0.1%/side':>16}  {'Gotrade real fees':>18}",
    ]
    out += [f"  {a:<{width}}  {b:>16}  {c:>18}" for a, b, c in rows]
    out.append("")
    rep = cmp.reproduced
    head = (
        f"recorded dev trial #{cmp.trial_n} ({cmp.recorded_model}): total return "
        f"{fmt_signed_pct(cmp.recorded_total_return)}"
    )
    if rep is None:
        out.append(f"{head}; there is no number to check the re-run against")
    elif rep:
        out.append(f"{head}; the {cmp.recorded_model} re-run reproduces it")
    else:
        out.append(
            f"{head}; the {cmp.recorded_model} re-run measured "
            f"{fmt_signed_pct(cmp.recorded_side.total_return)} -- the store or the engine changed "
            f"since it ran, so compare the two re-runs with each other, not with the recorded trial"
        )
    return "\n".join(out)


def _plain_miss(label: str) -> str:
    """One go-live label in everyday words (journal entries carry no labels or symbols)."""
    if label == FAILURE_LABELS[0]:
        return "beating SPY"
    if label.startswith("max DD <= "):
        return "the limit on its worst fall"
    if label.startswith("PF >= "):
        return "making at least $1.30 for every $1 it lost"
    if label.startswith(">= ") and label.endswith("trades"):
        return "trading at least 100 times"
    if label == "owner inputs":
        return "trading only what Gotrade can do"
    return label


def insight_text(cmp: Comparison) -> tuple[str, str]:
    """``(title, body)`` for the journal: plain words for a non-trader, no ids or code."""
    f, g = cmp.flat, cmp.real
    if f.beats_spy and not g.beats_spy:
        verdict = (
            "At the real fees it no longer beats SPY: the edge it showed was smaller than the fees "
            "it would have paid."
        )
    elif f.beats_spy and g.beats_spy:
        verdict = "It still beats SPY at the real fees: the fees shrink its edge without erasing it."
    elif g.beats_spy:
        verdict = (
            "It beats SPY only at the real fees, because SPY pays them too and they cost SPY more "
            "than they cost this method."
        )
    else:
        verdict = "It did not beat SPY at either fee, so the fees are not what holds it back."
    misses = [_plain_miss(label) for label in g.failed]
    gate = (
        "At the real fees it would still pass every go-live check this re-run can see (the luck "
        "test is not repeated here)."
        if not misses
        else f"At the real fees it falls short on {', '.join(misses)}."
    )
    title = f"{cmp.method_name}: what Gotrade's real fees do to it"
    body = "\n\n".join(
        (
            f"The lab re-ran this method over its {cmp.start.year}–{cmp.end.year} history twice, "
            f"with the same picks on the same days: once at the flat 0.1% a trade the lab has "
            f"always assumed, and once at the fees Gotrade actually charged on the owner's own "
            f"orders, read from the order receipts. SPY paid the same fees as the method in each "
            f"run, so the comparison stays fair.",
            "\n".join(
                (
                    f"- Return a year: {fmt_signed_pct(f.cagr)} at the assumed fee, "
                    f"{fmt_signed_pct(g.cagr)} at the real fees (SPY: {fmt_signed_pct(f.spy_tr_cagr)} "
                    f"and {fmt_signed_pct(g.spy_tr_cagr)}).",
                    f"- Worst fall from a peak: {fmt_pct(f.max_drawdown)} and {fmt_pct(g.max_drawdown)}.",
                    f"- Dollars made for every dollar lost: {fmt_pf(f.profit_factor)} and "
                    f"{fmt_pf(g.profit_factor)}.",
                    f"- Fees paid over the whole run: ${f.costs_usd:,.0f} and ${g.costs_usd:,.0f}.",
                )
            ),
            f"{verdict} {gate}",
            "This was a check, not a new try: the lab's count of tries did not move and no "
            "verdict changed.",
        )
    )
    return title, body


def journal(conn: sqlite3.Connection, cmp: Comparison) -> int:
    """Append the comparison to the lab journal as one ``observation`` on the method. The caller
    owns the transaction (``with conn:``). Returns the insight id."""
    title, body = insight_text(cmp)
    return store.add_insight(conn, kind="observation", title=title, body=body, method_id=cmp.method_id)
