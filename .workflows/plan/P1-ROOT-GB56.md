> Adopted from `SEAN_GOTRADE_TRACKER_PLAN.md` phase 7. Source: `.workflows/plan/sean-gotrade-tracker/phase-7.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 7: Lab: calibrate from real orders, measure methods at real cost

**Plan set:** `SEAN_GOTRADE_TRACKER_PLAN.md`
**Analysis:** `20261007-222658-S3AN_code_analyzer.md`
**Satisfies:** R5 — the owner's real Gotrade orders feed how new methods are explored and how the Sera lab computes profit and loss, because they show what every buy and sell really cost
**Depends on:** Phase 4 (`commands/sean.py` dispatch, `sean/` package), Phase 6 (`sim/costs.py`, `TradeRules.cost_model`)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab` (+ `engine/src/seer_engine/sean`, `.claude/skills`, `docs/plans`, and the two-string web mirror `web/lib/cadence.ts`)

---

## Goal

After this phase the real receipts drive the lab three ways. `python -m seer_engine sean calibrate` replays Phase 6's fee schedule over every order Sean has stored and exits 1 when an order since the current fee regime is off by more than a cent — the signal to refit `sim/costs.py`. `python -m seer_engine lab costs MNNNN` re-runs a recorded method's best dev variant at the flat 0.1% and at Gotrade's real fees, prints both side by side and journals the difference as a plain-words observation, without writing a trial (N unchanged, no look spent). From M0031 on, `lab run` refuses a variant that is not priced at real fees, two real-fee presets exist for new methods to build on (and to be promotable), and both lab skills and the design doc say so.

## Interface Contract

**Deletes:** nothing
**Renames:** nothing
**Creates:**
- `seer_engine.sean.calibrate` (`engine/src/seer_engine/sean/calibrate.py`): `TOLERANCE`, `WIB`, `SIDES`, `Fees` (Protocol), `PaidFees`, `Residual`, `Calibration`, `current_since()`, `check(paid, *, since, fee=costs.fee_parts)`, `format_report(cal)`, `wib_date(at)`, `rows_from_db(conn)`
- `seer_engine.commands.sean`: subcommand `calibrate` — `_calibrate(conn, args) -> int`, one `sub.add_parser("calibrate", ...)` block, `"calibrate": _calibrate` in `_HANDLERS`. CLI: `python -m seer_engine sean calibrate` (exit 0 = every current-regime order matches; 1 = refit needed)
- `seer_engine.lab.real_costs` (`engine/src/seer_engine/lab/real_costs.py`): `REAL_COST_SINCE = 31`, `FLAT`, `REAL`, `REPRO_TOL`, `requires_real_cost(method_id)`, `real_cost_problem(method)`, `resolve_method(method_id)`, `pick_candidate(conn, method, candidate_id)`, `twins(candidate)`, `Side`, `side_of(model, row)`, `Comparison`, `measure(method, candidate, trial, data)`, `format_report(cmp)`, `insight_text(cmp)`, `journal(conn, cmp)`
- `seer_engine.commands.lab`: subcommand `costs` — `_costs(conn, args)`, `"costs": _costs` in `_HANDLERS`. CLI: `python -m seer_engine lab costs M0007 [--candidate ID] [--store DIR]`
- `seer_engine.sim.rules.MONTHLY_HOLD_FRAC_GOTRADE` (id `monthly-hold-frac-gotrade`) and `MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE` (id `monthly-rank-weekly-resize-frac-gotrade`), appended to `PRESETS` (last two entries)
- tests `engine/tests/test_sean_calibrate.py`, `engine/tests/test_lab_costs.py`

**Signature changes:** none. `runner.preflight` keeps its signature and gains one refusal (a method numbered M0031+ with a variant not at `cost_model="gotrade"`).

**Writes (DB):** `lab costs` appends one `insights` row (`kind='observation'`, `method_id` set) to the lab SQLite. **Never** a `trials`, `trial_moments` or `methods` write. `sean calibrate` reads `sean_orders` only.

**Requires (from earlier phases):**
- Phase 4: `engine/src/seer_engine/commands/sean.py` exactly as its plan Step 5 writes it — `add_arguments` builds `sub = p.add_subparsers(dest="sean_command", ...)`; `run(args)` opens `db.connect()`, calls `_HANDLERS[args.sean_command](conn, args)` and closes the connection; `_HANDLERS = {"marks": _marks}`; the module imports `argparse`, `psycopg` and `from seer_engine import dates, db`. Package `seer_engine.sean` exists (`sean/__init__.py`).
- Phase 1: `sean_orders` per contract A (`id, side, symbol, executed_at timestamptz, amount_usd, trading_fee_usd, regulatory_fee_usd, ppn_usd` read here; fee columns are non-negative magnitudes).
- Phase 6, **bound to its real names** (Phase 6's code was executed and tested; it wins on signatures):
  1. `TradeRules.cost_model: CostModel = "flat"` (`CostModel = Literal["flat", "gotrade"]`, `sim/costs.py`), the last field of `TradeRules`, registered as `LEVERS_SINCE_PINS["cost_model"] = "flat"`; `replace(<flat book preset>, cost_model="gotrade")` validates only at the default `cost_rate` (else `ValueError` "cost_rate must stay at its default"); `replace(DESIGN_V0, cost_model="gotrade")` raises "reserved for DESIGN_V0".
  2. `seer_engine.sim.costs.fee_parts(side, amount: Decimal, on: date | None = None) -> FeeParts`; `FeeParts(trading, regulatory, ppn, total)` is a frozen dataclass of cent-rounded `Decimal` magnitudes. `on=None` = the current regime; `on` before the first regime (2025-06-10) raises `ValueError` ("no Gotrade fee schedule is known before …"), which `sean calibrate` lets propagate (exit 1 through `cli.main`: an order older than any receipt the schedule was fitted to cannot be checked).
  3. `seer_engine.sim.costs.GOTRADE: GotradeSchedule`; **`GOTRADE.current.since`** (2026-06-16) is the first day of the regime in force now (`current` is Phase 6's own property for `regimes[-1]`). Read in exactly one place, `calibrate.current_since()`.
  4. A backtest prices **every** fill at the current regime: `sim.book` calls `costs.gotrade_cash(side, price, shares)`, which calls `fee_parts(side, amount)` with `on=None`, whatever the session date. Pinned one way by Phase 6 ("Which regime a backtest uses"); §15 of the design doc (Step 13) says so.
  5. `rule_owner_inputs` raises `fee` only for `cost_model == "flat"` with a non-default rate, so the two new presets have no owner inputs; `backtest.dev._run` passes `cost_model=c.rules.cost_model` to `spy_curves`, so method and SPY pay alike in one run.
  6. `engine/tests/fixtures/gotrade_fees.json` is `{"about": ..., "rows": [{"date", "side", "amount", "trading", "regulatory", "ppn"}, ...]}` (30 rows, every value a string, dates are the receipts' WIB dates); the loader in Step 8 reads `data["rows"]`.
  7. Phase 6 edits `engine/tests/test_sim_rules.py` (the preset-values loop gains a `PRESETS[:13]` flat pin, `LEVERS_SINCE_PINS` pin, four Gotrade tests appended) and creates `engine/tests/test_cost_model_pins.py`, whose `test_flat_is_absent_from_every_canonical_form` loops over **every** preset. This phase's presets are the first non-flat ones, so Step 7 edits both files on top of Phase 6's versions.
  8. Phase 6 does **not** add any `-gotrade` preset (plan Decisions): Steps 6–7 here are the only place they are added.

**Leaves alone (owned by others):** `sim/costs.py` and every fee number (Phase 6); `sim/book.py`, `backtest/*` (Phase 6); `sean/{ledger,marks,equity}.py`, `execute_marks`, `_marks`, `run` in `commands/sean.py` (Phase 4); `db/migrations/*`, `web/**` except `web/lib/cadence.ts` + its test (Phases 1, 2, 3, 5; no other phase edits `cadence.ts`); every existing lab method file, trial row, pre-registration and paper roster row; `lab/lab.sqlite` and `web/data/lab.json` (not committed by this phase).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/sean/calibrate.py` | create | pure fee replay + `sean_orders` reader |
| `engine/src/seer_engine/commands/sean.py` | modify (Phase 4's file: docstring line ~3–12, imports ~line 23, after the `marks` parser in `add_arguments` ~line 60, before `_HANDLERS` ~line 120) | `calibrate` subcommand |
| `engine/src/seer_engine/lab/real_costs.py` | create | `lab costs` core + the M0031 real-fee rule |
| `engine/src/seer_engine/commands/lab.py` | modify (docstring after line 44; parser after line 226; handler after line 1447; `_HANDLERS` line 1568) | `lab costs` subcommand |
| `engine/src/seer_engine/lab/runner.py` | modify (import after line 55; `preflight` after line 92) | refuse flat-cost variants from M0031 |
| `engine/src/seer_engine/sim/rules.py` | modify (after `MONTHLY_RANK_WEEKLY_RESIZE_FRAC`, today line 181–183; `PRESETS` tuple, today line 185–199) | two real-fee presets |
| `engine/tests/test_sim_rules.py` | modify (the preset id list; `PRESETS[-1]` -> `PRESETS[12]`), on top of Phase 6 | preset pins follow the two new presets |
| `engine/tests/test_cost_model_pins.py` | modify (Phase 6's file: the `PRESETS` loop of `test_flat_is_absent_from_every_canonical_form`) | the two real-fee presets carry `cost_model` on purpose |
| `web/lib/cadence.ts` | modify (lines 8–12) | `SPLIT_CADENCE_RULES` gains `monthly-rank-weekly-resize-frac-gotrade` |
| `web/lib/cadence.test.ts` | modify (lines 7–15) | pins follow |
| `engine/tests/test_sean_calibrate.py` | create | calibrate unit + fixture + CLI + Postgres tests |
| `engine/tests/test_lab_costs.py` | create | `lab costs`, the M0031 rule, presets, live check (opt-in) |
| `.claude/skills/explore-and-experiment-new-method/SKILL.md` | modify (lines 69–70, 85, 105, 161–167, 197, 208) | real fees for new methods; `lab costs` for old ones; fix "whole shares" |
| `.claude/skills/explore-and-experiment-new-method/method_template.py` | modify (lines 23–25, 89) | template builds on the real-fee preset |
| `.claude/skills/sera-the-explorer/SKILL.md` | modify (lines 51–52, 57, 79–82, 98, 118) | slates and promotions at real fees |
| `docs/plans/2026-10-03-seer-design.md` | modify (line 29; append §15 after line 417) | costs measured, not assumed |

## Implementation Steps

### Step 1: The fee replay
**File:** `engine/src/seer_engine/sean/calibrate.py:1` (new)
**Change:** a pure check (`check`, `format_report`) with the schedule injected, so tests do not depend on Phase 6's fitted numbers, plus one database reader. Receipt dates are read in WIB (`+07:00`) because Gotrade prints them in WIB and Phase 6 fitted its regime boundaries to those printed dates.
**Code:**
```python
"""``sean calibrate``: does ``sim/costs.py`` still charge what Gotrade charged?

The Gotrade fee schedule the lab prices trades with (``sim.costs``, Sean phase 6) was fitted to
the owner's own order receipts. Every receipt Sean stores in ``sean_orders`` is a fresh
measurement of that schedule, so this module replays it: for each stored order it asks
``costs.fee_parts`` what the schedule says the order should have paid on the order's own date, and
compares the three parts -- trading fee, regulatory fee, PPN (VAT) -- with what the receipt says.

An order dated on or after the first day of the regime in force now that is off by more than a
cent in any part means Gotrade changed its fees, or the fit was wrong: ``sean calibrate`` exits 1
and ``sim/costs.py`` needs a new dated regime. An order under an older regime is printed with its
residual and never fails the check -- a past regime cannot change any more, and its fit is Phase
6's own test.

Receipt dates are WIB calendar dates (Gotrade prints "October 07, 2026" + "21:55 WIB"), which is
what the regime boundaries were fitted to. This is deliberately not the New York trade date the
ledger uses (``sean.ledger``): a fee regime starts on the day Gotrade's app started charging it.

Pure except ``rows_from_db``. No clock, no network.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Protocol

from seer_engine.sim import costs

TOLERANCE = Decimal("0.01")  # a cent: PPN is rounded on Gotrade's side, 29 of 30 receipts exact
WIB = timezone(timedelta(hours=7), "WIB")
SIDES: tuple[str, ...] = ("buy", "sell")


class Fees(Protocol):
    """What a fee schedule says one order pays, part by part (``costs.FeeParts`` satisfies it)."""

    trading: Decimal
    regulatory: Decimal
    ppn: Decimal


FeeFn = Callable[..., Fees]  # fee(side, amount, on=date) -> Fees


@dataclass(frozen=True)
class PaidFees:
    """What one receipt says the order paid. Every money field is a non-negative ``Decimal``."""

    ref: str  # "order 12": how the report names the row
    on: date  # the receipt's WIB date
    side: str
    symbol: str  # "" when the source has none
    amount: Decimal
    trading: Decimal
    regulatory: Decimal
    ppn: Decimal

    def __post_init__(self) -> None:
        if self.side not in SIDES:
            raise ValueError(f"{self.ref}: side must be one of {SIDES}, got {self.side!r}")
        if isinstance(self.on, datetime) or not isinstance(self.on, date):
            raise TypeError(f"{self.ref}: on must be a date, got {type(self.on).__name__}")
        for name in ("amount", "trading", "regulatory", "ppn"):
            value = getattr(self, name)
            if not isinstance(value, Decimal):
                raise TypeError(f"{self.ref}: {name} must be a Decimal, got {type(value).__name__}")
            if not value.is_finite() or value < 0:
                raise ValueError(f"{self.ref}: {name} must be a non-negative amount, got {value}")

    @property
    def total(self) -> Decimal:
        return self.trading + self.regulatory + self.ppn


@dataclass(frozen=True)
class Residual:
    """One order: what it paid, what the schedule says, and whether the order is in the current
    regime (and so able to fail the check)."""

    paid: PaidFees
    expected: Any  # Fees
    current: bool

    @property
    def gaps(self) -> tuple[Decimal, Decimal, Decimal]:
        """Paid minus expected for trading, regulatory and PPN, in that order."""
        e = self.expected
        return (
            self.paid.trading - Decimal(e.trading),
            self.paid.regulatory - Decimal(e.regulatory),
            self.paid.ppn - Decimal(e.ppn),
        )

    @property
    def gap(self) -> Decimal:
        """The largest absolute difference across the three parts."""
        return max(abs(g) for g in self.gaps)

    @property
    def ok(self) -> bool:
        return self.gap <= TOLERANCE

    @property
    def expected_total(self) -> Decimal:
        e = self.expected
        return Decimal(e.trading) + Decimal(e.regulatory) + Decimal(e.ppn)


@dataclass(frozen=True)
class Calibration:
    since: date  # first day of the regime in force now
    residuals: tuple[Residual, ...]

    @property
    def current(self) -> tuple[Residual, ...]:
        return tuple(r for r in self.residuals if r.current)

    @property
    def misses(self) -> tuple[Residual, ...]:
        return tuple(r for r in self.current if not r.ok)

    @property
    def passed(self) -> bool:
        return not self.misses


def current_since() -> date:
    """The first day of the fee regime in force now (Phase 6's ``GOTRADE.current``)."""
    return costs.GOTRADE.current.since


def check(paid: Iterable[PaidFees], *, since: date, fee: FeeFn = costs.fee_parts) -> Calibration:
    """Replay ``fee`` over every order, each on its own date. Order is preserved."""
    out = tuple(
        Residual(paid=p, expected=fee(p.side, p.amount, on=p.on), current=p.on >= since)
        for p in paid
    )
    return Calibration(since=since, residuals=out)


def _usd(x: Decimal) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.2f}"


def format_report(cal: Calibration) -> str:
    """One line per order, then one sentence that says whether the schedule still holds."""
    rows = cal.residuals
    if not rows:
        return "Gotrade fee check: no orders stored yet, so there is nothing to check."
    since = cal.since.isoformat()
    current = cal.current
    lines = [
        f"Gotrade fee check: {len(rows)} order(s); {len(current)} since the current fee schedule "
        f"began on {since}.",
        "",
    ]
    for r in rows:
        p = r.paid
        e = r.expected
        if r.ok:
            verdict = "matches"
        elif r.current:
            verdict = f"OFF by up to {_usd(r.gap)}"
        else:
            verdict = f"older schedule, off by up to {_usd(r.gap)} (not checked)"
        lines.append(
            f"  {p.on.isoformat()}  {p.side:<4}  {(p.symbol or '-'):<6} {_usd(p.amount):>11}  "
            f"paid {_usd(p.total)} (trading {_usd(p.trading)}, regulatory {_usd(p.regulatory)}, "
            f"VAT {_usd(p.ppn)})  schedule {_usd(r.expected_total)} (trading "
            f"{_usd(Decimal(e.trading))}, regulatory {_usd(Decimal(e.regulatory))}, VAT "
            f"{_usd(Decimal(e.ppn))})  {verdict}"
        )
    lines.append("")
    if not current:
        lines.append(
            f"No order is dated on or after {since}, so the current fee schedule has nothing to be "
            f"checked against yet."
        )
    elif cal.passed:
        lines.append(
            f"All {len(current)} order(s) since {since} match the schedule to within a cent in "
            f"every part."
        )
    else:
        lines.append(
            f"{len(cal.misses)} of {len(current)} order(s) since {since} are off by more than a "
            f"cent. Gotrade's fees have changed or the fit was wrong: refit the schedule in "
            f"engine/src/seer_engine/sim/costs.py (add a new dated regime; never edit a past one) "
            f"and run this check again."
        )
    return "\n".join(lines)


def wib_date(at: datetime) -> date:
    """The WIB calendar date of a timezone-aware ``executed_at``."""
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError(f"executed_at must be a timezone-aware datetime, got {at!r}")
    return at.astimezone(WIB).date()


_ORDERS_SQL = """
SELECT id, side, symbol, executed_at, amount_usd, trading_fee_usd, regulatory_fee_usd, ppn_usd
FROM sean_orders
ORDER BY executed_at, id
"""


def rows_from_db(conn: Any) -> tuple[PaidFees, ...]:
    """Every stored order's fees, oldest first (contract A columns; read only)."""
    out: list[PaidFees] = []
    for oid, side, symbol, at, amount, trading, regulatory, ppn in conn.execute(_ORDERS_SQL).fetchall():
        out.append(
            PaidFees(
                ref=f"order {oid}",
                on=wib_date(at),
                side=str(side),
                symbol=str(symbol),
                amount=Decimal(amount),
                trading=Decimal(trading),
                regulatory=Decimal(regulatory),
                ppn=Decimal(ppn),
            )
        )
    return tuple(out)
```
**Impact:** new module; nothing imports it but the command and the tests.

### Step 2: `sean calibrate`
**File:** `engine/src/seer_engine/commands/sean.py` (Phase 4's file, as its plan Step 5 writes it)
**Change:** four insertions; nothing of Phase 4's is edited.

2a. In the module docstring, directly after the `sean marks [--now ISO8601] ...` entry (Phase 4 line ~3–7), add:
```text
    sean calibrate               replay Gotrade's fee schedule (sim/costs.py) over every stored
                                 order and print what each paid against what the schedule says;
                                 exit 1 when an order since the current fee regime is off by more
                                 than a cent (Gotrade changed its fees: refit the schedule)
```

2b. Imports: after Phase 4's `from seer_engine.sean import equity, marks`, add:
```python
from seer_engine.sean import calibrate as fee_check
```

2c. In `add_arguments`, after the `marks` parser's `s.add_argument("--now", ...)` call (the end of the function), add:
```python
    sub.add_parser(
        "calibrate",
        help="replay Gotrade's fee schedule over every stored order; exit 1 when it needs a refit",
        description=(
            "Read every order in sean_orders, ask sim/costs.py what each should have paid on its "
            "own date (trading fee, regulatory fee, PPN), and print both. Exit 1 when any order "
            "dated on or after the first day of the current fee regime is off by more than a cent "
            "in any part. Reads only; writes nothing."
        ),
    )
```

2d. Directly above `_HANDLERS = {`, add the handler, and add one entry to the map:
```python
def _calibrate(conn: psycopg.Connection, args: argparse.Namespace) -> int:
    """Read-only: every stored order's fees against the schedule. ``run`` owns the connection."""
    paid = fee_check.rows_from_db(conn)
    conn.rollback()  # close the read transaction; nothing was written
    result = fee_check.check(paid, since=fee_check.current_since())
    print(fee_check.format_report(result))
    log.info(
        "sean calibrate: %d order(s), %d in the current regime, %d off by more than a cent",
        len(result.residuals), len(result.current), len(result.misses),
    )
    return 0 if result.passed else 1
```
```python
_HANDLERS = {
    "marks": _marks,
    "calibrate": _calibrate,
}
```
**Impact:** `python -m seer_engine sean --help` lists `calibrate`. `--dry-run` is irrelevant (it writes nothing). No change to `run` or `marks`.

### Step 3: The real-fee lab module
**File:** `engine/src/seer_engine/lab/real_costs.py:1` (new)
**Change:** everything `lab costs` does except loading the store and printing, plus the M0031 rule `runner.preflight` applies. Named `real_costs` (not `costs`) so it never shadows `sim.costs` in a reader's head or an import line.
**Code:**
```python
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
) -> Comparison:
    """Run ``candidate`` at both cost models on the dev window. Writes nothing anywhere."""
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

    dev.run_registry(data.market, data.dividends, data.spy_dividends, (flat, real), on_result=on_result)
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
```
**Impact:** new module. Imports `research`, `backtest.dev`, `lab.store`, `lab.method` — none of which imports `lab.runner`, so `runner` may import this module at top level (Step 5) without a cycle.

### Step 4: `lab costs`
**File:** `engine/src/seer_engine/commands/lab.py`
**Change:** four insertions.

4a. Module docstring — insert after line 44 (the last line of the `lab remeasure` entry, "... reported and not written (exit 1)"):
```text
    lab costs M0007 [--candidate M0007-N20-RAW] [--store DIR]
                                    report only: re-run a recorded method's best dev variant (by
                                    MAR, or --candidate) at the flat 0.1% and at Gotrade's real
                                    fees (sim/costs.py, measured from the owner's receipts), print
                                    both and journal the difference as an observation. No trial
                                    row, no moments, no status change: N and the looks do not move
```

4b. Parser — insert after line 226 (the end of the `remeasure` parser, before `s = sub.add_parser("idea", ...)`):
```python
    s = sub.add_parser(
        "costs",
        help="report only: a recorded method at Gotrade's real fees vs the flat 0.1%, journaled",
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
```

4c. Handler — insert after line 1447 (the end of `_remeasure_seed`, before `def _idea`):
```python
def _costs(conn, args) -> int:
    """``lab costs M0007``: a recorded method at Gotrade's real fees. Report only.

    Every refusal that needs no data -- not a method id, no method file, no dev trial, no such
    variant, a bracket or custom-rate variant with no real-fee twin -- is made before the research
    store is loaded. Then ``real_costs.measure`` runs the variant at both cost models on the dev
    window and ``real_costs.journal`` appends one observation. Nothing else is written: N and the
    test-window looks are printed before and after so the invariant is visible, not just tested.
    """
    from seer_engine.lab import real_costs

    method, _path = real_costs.resolve_method(args.method)
    candidate, trial = real_costs.pick_candidate(conn, method, args.candidate)
    real_costs.twins(candidate)  # refuses a variant with no real-fee twin before the store loads
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
    cmp = real_costs.measure(method, candidate, trial, data)
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
```

4d. `_HANDLERS` — after line 1568 (`"remeasure": _remeasure,`) add:
```python
    "costs": _costs,
```
**Impact:** `lab --help` lists `costs`. No existing subcommand changes. Exit 2 for every `LabError` refusal (unchanged `run` wrapper).

### Step 5: `lab run` refuses a flat-cost variant from M0031
**File:** `engine/src/seer_engine/lab/runner.py`
**Change:** 5a, after line 55 (`from seer_engine.lab.method import ...`) add:
```python
from seer_engine.lab.real_costs import real_cost_problem
```
5b, in `preflight`, insert after line 92 (the end of the `if require_commit:` block, before `row = store.get_method(conn, method.id)`):
```python
    cost_problem = real_cost_problem(method)
    if cost_problem is not None:
        raise store.LabError(f"{method.id}: {cost_problem}")
```
And add one sentence to `preflight`'s docstring (line 86) so it reads:
```python
    """Every refusal ``lab run`` makes before loading data (``store.LabError``).

    From M0031 on that includes a variant not priced at Gotrade's real fees
    (``real_costs.real_cost_problem``); methods up to M0030 are unaffected.
    """
```
**Impact:** every committed method is M0001–M0030, so nothing that exists is refused (`test_every_committed_method_from_m0031_runs_at_real_fees` keeps it that way). Existing runner tests use M0001–M0003 and are unaffected. `run_method` calls `preflight` twice; both apply the rule.

### Step 6: Two real-fee presets
**File:** `engine/src/seer_engine/sim/rules.py` (as Phase 6 leaves it: `TradeRules` ends with `cost_rate: Decimal = _DEFAULT_COST` then `cost_model: CostModel = "flat"`; `from seer_engine.sim.costs import COST_MODELS, GOTRADE, CostModel` is imported; the preset block is unchanged by Phase 6)
**Change:** `promote._check_rules` only promotes a variant whose rules are the `sim.rules` preset of their own id, so a real-fee lab winner needs presets. Phase 6 adds none (plan Decisions); this phase does. Insert directly after the `MONTHLY_RANK_WEEKLY_RESIZE_FRAC = replace(...)` definition (lines 181–183 before Phase 6, which adds one import line above them):
```python
# The two fractional book presets at Gotrade's real fees (sim/costs.py, fitted to the owner's
# receipts; Sean, 2026-10-07). Lab methods from M0031 on are built on these (lab/real_costs.py),
# and `promote` needs a preset of the variant's own id, so a real-fee winner can reach paper.
MONTHLY_HOLD_FRAC_GOTRADE = replace(MONTHLY_HOLD_FRAC, id="monthly-hold-frac-gotrade", cost_model="gotrade")
MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE = replace(
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC, id="monthly-rank-weekly-resize-frac-gotrade", cost_model="gotrade"
)
```
and append both to the end of `PRESETS` so it reads:
```python
PRESETS: tuple[TradeRules, ...] = (
    DESIGN_V0,
    MONTHLY_HOLD,
    MONTHLY_HOLD_TBILL,
    WEEKLY_HOLD,
    DAILY_SWITCH,
    DAILY_SWITCH_TBILL,
    SWING_T10,
    SWING_T20,
    SWING_T20_OPEN,
    MONTHLY_RANK_WEEKLY_RESIZE,
    MONTHLY_RANK_WEEKLY_RESIZE_TBILL,
    MONTHLY_HOLD_FRAC,
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC,
    MONTHLY_HOLD_FRAC_GOTRADE,
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
)
```
**Impact:** no existing preset, candidate, digest or roster row changes (appending to a tuple moves nothing that is pinned by value). `paper.roster.rules_for` now resolves the two ids; `promote.fractional_twin(MONTHLY_HOLD)` still returns `MONTHLY_HOLD_FRAC` because `cost_model` differs on the new presets (tested in Step 9). Existing loops over `PRESETS` that keep holding: `test_preset_values_are_pinned` (book, dividends, `cost_rate == 0.001`; Phase 6's flat pin covers `PRESETS[:13]` only), `test_rules_are_frozen_and_hashable`, `test_owner_inputs_of_the_presets` (`()`), `describe_rules` length 12, `test_resize_cadence_defaults_to_none_and_every_old_preset_keeps_one_cadence`, `test_paper_kickoff`, `test_registry`. The one that does not is Phase 6's `test_flat_is_absent_from_every_canonical_form` (Step 7c).

### Step 7: Preset pins follow
**File:** `engine/tests/test_sim_rules.py` (on top of Phase 6's edits, which add two lines inside `test_preset_values_are_pinned` above this test and append the Gotrade tests at the end; locate by function name, not line)
**Change:** 7a, `test_preset_ids_are_unique_and_in_order` (lines 89–105 before Phase 6, 91–107 after) — the expected list gains the two ids at its end:
```python
def test_preset_ids_are_unique_and_in_order():
    ids = [r.id for r in PRESETS]
    assert ids == [
        "design-v0",
        "monthly-hold",
        "monthly-hold-tbill",
        "weekly-hold",
        "daily-switch",
        "daily-switch-tbill",
        "swing-t10",
        "swing-t20",
        "swing-t20-open",
        "monthly-rank-weekly-resize",
        "monthly-rank-weekly-resize-tbill",
        "monthly-hold-frac",
        "monthly-rank-weekly-resize-frac",
        "monthly-hold-frac-gotrade",
        "monthly-rank-weekly-resize-frac-gotrade",
    ]
    assert len(set(ids)) == len(ids)
```
7b, in `test_monthly_rank_weekly_resize_frac_is_the_split_cadence_in_fractional_shares` (line 348 before Phase 6, 350 after), the line
```python
    assert PRESETS[-1] is r and sim.MONTHLY_RANK_WEEKLY_RESIZE_FRAC is r
```
becomes
```python
    assert PRESETS[12] is r and sim.MONTHLY_RANK_WEEKLY_RESIZE_FRAC is r
```
Everything else in the file already holds for the new presets: book engine, dividends on, `cost_rate == 0.001`, owner inputs `()` (binding 5), the same `describe_rules` length as every other preset, single cadence where `resize_cadence is None`.

7c. **File:** `engine/tests/test_cost_model_pins.py` (Phase 6's new file). Its
`test_flat_is_absent_from_every_canonical_form` asserts `"cost_model" not in roster.rules_dict(r)`
for every preset; the two presets of Step 6 are the first at `cost_model="gotrade"`, so their
canonical form carries it on purpose and the build would go red. Replace the trailing loop
```python
    for r in PRESETS:
        assert "cost_model" not in roster.rules_dict(r), r.id
```
with
```python
    for r in PRESETS:
        if r.cost_model == "flat":
            assert "cost_model" not in roster.rules_dict(r), r.id
        else:  # the real-fee presets (Sean phase 7) name their model, so they digest apart
            assert roster.rules_dict(r)["cost_model"] == "gotrade", r.id
    assert [r.id for r in PRESETS if r.cost_model != "flat"] == [
        "monthly-hold-frac-gotrade",
        "monthly-rank-weekly-resize-frac-gotrade",
    ]
```
The lab-candidate loops above it stay as they are: every committed method is M0001–M0030 and
flat. (When an M0031+ method lands on a `-gotrade` preset, that test's `discover()` loop will
need the same `cost_model == "flat"` guard; the method's own pre-registration digest is pinned by
`test_lab_methods`, not here.)
**Impact:** test-only.

### Step 7d: The web's split-cadence mirror learns the real-fee preset
**File:** `web/lib/cadence.ts:8-12` and `web/lib/cadence.test.ts:7-12`
**Change:** `SPLIT_CADENCE_RULES` hand-mirrors the engine's monthly-rank/weekly-resize presets
for the site (Today page, Plan reminders' "picks again" words). `monthly-rank-weekly-resize-frac-gotrade`
from Step 6 is one of them; without it a promoted real-fee RMW winner would read as monthly-only
on the site. (Phase 5's `RESIZING_RULES` already lists both real-fee ids; it owns that file.)
**Code (`cadence.ts`, the list):**
```ts
/** `strategies.rules_id` values whose basket is picked monthly and resized weekly. */
export const SPLIT_CADENCE_RULES: readonly string[] = [
  'monthly-rank-weekly-resize',
  'monthly-rank-weekly-resize-tbill',
  'monthly-rank-weekly-resize-frac',
  'monthly-rank-weekly-resize-frac-gotrade',
];
```
**Code (`cadence.test.ts`, the first test):**
```ts
  it('knows the four split-cadence rule sets', () => {
    expect(picksMonthlySizesWeekly('monthly-rank-weekly-resize')).toBe(true);
    expect(picksMonthlySizesWeekly('monthly-rank-weekly-resize-tbill')).toBe(true);
    expect(picksMonthlySizesWeekly('monthly-rank-weekly-resize-frac')).toBe(true);
    expect(picksMonthlySizesWeekly('monthly-rank-weekly-resize-frac-gotrade')).toBe(true);
    expect(SPLIT_CADENCE_RULES).toHaveLength(4);
  });
```
and add `'monthly-hold-frac-gotrade'` to the id list of the second test (`is false for every other rule set and for none`).
**Impact:** web only, two strings; `cd web && npx vitest run lib/cadence.test.ts` is part of this phase's verification.

### Step 8: Calibrate tests
**File:** `engine/tests/test_sean_calibrate.py:1` (new)
**Change:** unit tests with a stand-in schedule (independent of Phase 6's fitted numbers); the fixture check against Phase 6's real schedule; the CLI with a stub connection (no Postgres needed); one end-to-end test on the `pg` fixture.
**Code:**
```python
"""``sean calibrate`` (Sean phase 7): Gotrade's fee schedule replayed over the owner's receipts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import psycopg
import pytest

from seer_engine import cli, db
from seer_engine.sean import calibrate
from seer_engine.sim import costs

FIXTURE = Path(__file__).parent / "fixtures" / "gotrade_fees.json"
CENT = Decimal("0.01")
SINCE = date(2026, 6, 16)
WIB = timezone(timedelta(hours=7))


@dataclass(frozen=True)
class F:
    trading: Decimal
    regulatory: Decimal
    ppn: Decimal


def stand_in(side, amount, on=None):
    """A stand-in schedule: 0.2% with a $0.10 floor, $0.02 regulatory, 11% PPN, to the cent."""
    trading = max(Decimal("0.10"), (amount * Decimal("0.002")).quantize(CENT, ROUND_HALF_UP))
    regulatory = Decimal("0.02")
    ppn = ((trading + regulatory) * Decimal("0.11")).quantize(CENT, ROUND_HALF_UP)
    return F(trading, regulatory, ppn)


def paid(on, *, amount="27.90", trading="0.10", reg="0.02", ppn="0.01", side="buy",
         ref="order 1", symbol="MU"):
    return calibrate.PaidFees(
        ref=ref, on=on, side=side, symbol=symbol, amount=Decimal(amount),
        trading=Decimal(trading), regulatory=Decimal(reg), ppn=Decimal(ppn),
    )


# ---- the check, against a stand-in schedule ----------------------------------------------------


def test_an_order_that_matches_the_schedule_passes():
    cal = calibrate.check([paid(date(2026, 10, 7))], since=SINCE, fee=stand_in)
    assert cal.passed
    assert len(cal.current) == 1
    assert cal.residuals[0].gap == 0
    assert cal.residuals[0].expected_total == Decimal("0.13")


def test_a_cent_is_tolerated_and_two_cents_are_not():
    one = paid(date(2026, 10, 7), ppn="0.02")
    two = paid(date(2026, 10, 7), trading="0.12", ref="order 2")
    cal = calibrate.check([one, two], since=SINCE, fee=stand_in)
    assert cal.residuals[0].ok and cal.residuals[0].gap == CENT
    assert not cal.residuals[1].ok
    assert cal.misses == (cal.residuals[1],)
    assert not cal.passed


def test_an_older_regime_is_reported_but_never_fails():
    old = paid(date(2025, 6, 10), amount="1429.00", trading="0.00", reg="4.29", ppn="0.00")
    cal = calibrate.check([old], since=SINCE, fee=stand_in)
    r = cal.residuals[0]
    assert not r.ok and not r.current
    assert cal.passed
    assert "older schedule" in calibrate.format_report(cal)


def test_each_order_is_priced_on_its_own_date():
    seen = []

    def spy(side, amount, on=None):
        seen.append((side, amount, on))
        return stand_in(side, amount, on)

    calibrate.check([paid(date(2025, 7, 22), side="sell", amount="72.51")], since=SINCE, fee=spy)
    assert seen == [("sell", Decimal("72.51"), date(2025, 7, 22))]


def test_the_report_says_refit_when_a_current_order_is_off():
    cal = calibrate.check([paid(date(2026, 10, 7), trading="0.15")], since=SINCE, fee=stand_in)
    text = calibrate.format_report(cal)
    assert "OFF by up to $0.05" in text
    assert "refit the schedule" in text and "sim/costs.py" in text


def test_the_report_says_so_when_everything_matches():
    text = calibrate.format_report(calibrate.check([paid(date(2026, 10, 7))], since=SINCE, fee=stand_in))
    assert "All 1 order(s) since 2026-06-16 match the schedule" in text


def test_no_orders_is_a_pass():
    cal = calibrate.check([], since=SINCE, fee=stand_in)
    assert cal.passed
    assert "nothing to check" in calibrate.format_report(cal)


def test_a_receipt_time_is_read_as_a_wib_date():
    assert calibrate.wib_date(datetime(2026, 10, 7, 17, 30, tzinfo=timezone.utc)) == date(2026, 10, 8)
    assert calibrate.wib_date(datetime(2026, 10, 7, 21, 55, tzinfo=WIB)) == date(2026, 10, 7)
    with pytest.raises(ValueError, match="timezone-aware"):
        calibrate.wib_date(datetime(2026, 10, 7, 21, 55))


def test_paid_fees_refuse_signed_floats_and_unknown_sides():
    with pytest.raises(ValueError, match="non-negative"):
        paid(date(2026, 10, 7), trading="-0.10")
    with pytest.raises(ValueError, match="side"):
        paid(date(2026, 10, 7), side="short")
    with pytest.raises(TypeError, match="Decimal"):
        calibrate.PaidFees(ref="x", on=date(2026, 10, 7), side="buy", symbol="", amount=27.9,
                           trading=Decimal("0.10"), regulatory=Decimal("0.02"), ppn=Decimal("0.01"))


# ---- the real schedule, against Phase 6's fee fixture -------------------------------------------


def _fixture_rows(path: Path) -> list[calibrate.PaidFees]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data["rows"] if isinstance(data, dict) else data
    return [
        calibrate.PaidFees(
            ref=f"row {i}", on=date.fromisoformat(str(r["date"])), side=str(r["side"]),
            symbol=str(r.get("symbol") or ""), amount=Decimal(str(r["amount"])).copy_abs(),
            trading=Decimal(str(r["trading"])).copy_abs(),
            regulatory=Decimal(str(r["regulatory"])).copy_abs(),
            ppn=Decimal(str(r["ppn"])).copy_abs(),
        )
        for i, r in enumerate(items, start=1)
    ]


def test_the_schedule_reproduces_every_current_receipt_in_the_fixture():
    cal = calibrate.check(_fixture_rows(FIXTURE), since=calibrate.current_since())
    assert cal.current, "the fee fixture holds receipts from the current regime"
    assert cal.passed, calibrate.format_report(cal)


def test_current_since_is_a_date_no_later_than_the_newest_receipt():
    since = calibrate.current_since()
    assert isinstance(since, date)
    assert since <= max(r.on for r in _fixture_rows(FIXTURE))


# ---- the command, with a stub connection --------------------------------------------------------


class StubConn:
    def __init__(self, rows):
        self.rows = rows
        self.closed = False
        self.rolled_back = False

    def execute(self, sql, params=None):
        assert "FROM sean_orders" in sql
        return self

    def fetchall(self):
        return self.rows

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _row(oid, at, amount, *, nudge=Decimal("0")):
    e = costs.fee_parts("buy", amount, on=calibrate.wib_date(at))
    return (oid, "buy", f"S{oid}", at, amount, e.trading + nudge, e.regulatory, e.ppn)


def _at(day):
    return datetime(day.year, day.month, day.day, 21, 55, tzinfo=WIB)


def test_cli_exits_0_when_every_current_order_matches(monkeypatch, capsys):
    day = calibrate.current_since()
    stub = StubConn([_row(1, _at(day), Decimal("27.90")), _row(2, _at(day), Decimal("1673.14"))])
    monkeypatch.setattr(db, "connect", lambda url=None: stub)
    assert cli.main(["sean", "calibrate"]) == 0
    assert "match the schedule" in capsys.readouterr().out
    assert stub.closed and stub.rolled_back


def test_cli_exits_1_when_a_current_order_drifted(monkeypatch, capsys):
    day = calibrate.current_since()
    stub = StubConn([_row(1, _at(day), Decimal("27.90"), nudge=Decimal("0.05"))])
    monkeypatch.setattr(db, "connect", lambda url=None: stub)
    assert cli.main(["sean", "calibrate"]) == 1
    out = capsys.readouterr().out
    assert "OFF by up to $0.05" in out and "refit" in out


def test_cli_parses_calibrate():
    args = cli.build_parser().parse_args(["sean", "calibrate"])
    assert args.sean_command == "calibrate"


# ---- end to end on Postgres ----------------------------------------------------------------------


def _insert(conn, symbol, at, amount, fees):
    total = amount + fees.trading + fees.regulatory + fees.ppn
    conn.execute(
        """
        INSERT INTO sean_orders (side, order_type, status, symbol, executed_at, price, shares,
                                 amount_usd, trading_fee_usd, regulatory_fee_usd, ppn_usd, total_usd)
        VALUES ('buy', 'Market Buy', 'Filled', %s, %s, %s, 1, %s, %s, %s, %s, %s)
        """,
        (symbol, at, amount, amount, fees.trading, fees.regulatory, fees.ppn, total),
    )
    conn.commit()


def test_calibrate_reads_sean_orders(pg, pg_schema, monkeypatch, capsys):
    day = calibrate.current_since()
    at = _at(day)
    amount = Decimal("27.90")
    _insert(pg, "MU", at, amount, costs.fee_parts("buy", amount, on=day))
    monkeypatch.setattr(db, "connect", lambda url=None: psycopg.connect(pg_schema.url, autocommit=False))
    assert cli.main(["sean", "calibrate"]) == 0
    assert "1 since the current fee schedule" in capsys.readouterr().out

    e = costs.fee_parts("buy", amount, on=day)
    _insert(pg, "CNC", at, amount, F(e.trading + Decimal("0.05"), e.regulatory, e.ppn))
    assert cli.main(["sean", "calibrate"]) == 1
    assert "1 of 2 order(s)" in capsys.readouterr().out
```
**Impact:** the fixture tests fail if Phase 6's schedule stops reproducing its own receipts — the same signal Phase 6's test gives, read through this module. `test_calibrate_reads_sean_orders` skips without `PG_TEST_URL` like every other DB test.

### Step 9: `lab costs` tests
**File:** `engine/tests/test_lab_costs.py:1` (new)
**Change:** a two-variant method on the synthetic dev market (`labkit.smoke_data`), recorded with `runner.run_method`, then measured; the CLI end to end with the store and the method file stubbed; the M0031 rule; the presets; one opt-in test against the real research store.
**Code:**
```python
"""``lab costs`` and the M0031 real-fee rule (Sean phase 7): report only, N never moves."""

from __future__ import annotations

import os
import shutil
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from labkit import smoke_data, smoke_test_data

from seer_engine import cli, research
from seer_engine.backtest.dev import Candidate
from seer_engine.commands import promote
from seer_engine.lab import real_costs, runner, store
from seer_engine.lab.method import Method, discover
from seer_engine.lab.seed import seed
from seer_engine.paper import roster
from seer_engine.sim.rules import (
    MONTHLY_HOLD,
    MONTHLY_HOLD_FRAC,
    MONTHLY_HOLD_FRAC_GOTRADE,
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC,
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
    PRESETS,
    rule_owner_inputs,
)
from seer_engine.strategies.f_index import TIMING, TimingParams

HERE = Path(__file__)


def _cand(cid, family, rules=MONTHLY_HOLD_FRAC, n=50) -> Candidate:
    return Candidate(
        id=cid, family=family, rules=rules, allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
        rationale="test", added=date(2026, 10, 7), owner_inputs=(),
    )


def _method(mid="M0001", cands=None) -> Method:
    cands = cands or (_cand(f"{mid}-A", mid), _cand(f"{mid}-B", mid, n=20))
    return Method(id=mid, name="SPY above its average", family="trend", source_kind="knowledge",
                  source_ref="", hypothesis="h", expected_failure="f", candidates=tuple(cands))


@pytest.fixture()
def lab(tmp_path):
    path = tmp_path / "lab.sqlite"
    c = store.connect(path)
    seed(c)
    yield c, path
    c.close()


@pytest.fixture(scope="module")
def data():
    return smoke_data()


@pytest.fixture()
def recorded(lab, data):
    conn, _ = lab
    m = _method()
    runner.run_method(conn, m, HERE, data, git_sha="x", require_commit=False)
    return m


def _untouched(conn):
    """Everything `lab costs` must leave as it found it (insights excepted)."""
    return (
        store.dev_trial_count(conn),
        store.test_looks(conn),
        conn.execute("SELECT count(*) FROM trials").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0],
        tuple(tuple(r) for r in conn.execute("SELECT id, status, verdict, source_sha FROM methods ORDER BY id")),
    )


def _insights(conn):
    return conn.execute("SELECT count(*) FROM insights").fetchone()[0]


# ---- measure ---------------------------------------------------------------------------------


def test_measure_runs_the_variant_at_both_fees_and_writes_nothing(lab, data, recorded):
    conn, _ = lab
    before, notes = _untouched(conn), _insights(conn)
    c, trial = real_costs.pick_candidate(conn, recorded, None)
    cmp = real_costs.measure(recorded, c, trial, data)
    assert (cmp.flat.model, cmp.real.model) == ("flat", "gotrade")
    assert cmp.recorded_model == "flat" and cmp.reproduced is True
    assert cmp.real.candidate_id == f"{c.id}-GT"
    assert cmp.real.costs_usd > cmp.flat.costs_usd
    assert cmp.real.total_return < cmp.flat.total_return
    assert _untouched(conn) == before and _insights(conn) == notes


def test_the_default_variant_is_the_best_recorded_by_mar(lab, recorded):
    conn, _ = lab
    rows = [t for t in store.trials_of(conn, "M0001") if t["window"] == "dev"]
    best = sorted(rows, key=lambda t: (t["mar"] is None, -(t["mar"] or 0.0), t["n"]))[0]
    c, trial = real_costs.pick_candidate(conn, recorded, None)
    assert c.id == best["candidate_id"] == trial["candidate_id"]
    other, _ = real_costs.pick_candidate(conn, recorded, "M0001-B")
    assert other.id == "M0001-B"
    with pytest.raises(store.LabError, match="no dev trial for 'M0001-Z'"):
        real_costs.pick_candidate(conn, recorded, "M0001-Z")


def test_a_method_that_never_ran_is_refused(lab):
    conn, _ = lab
    with pytest.raises(store.LabError, match="has no dev trial"):
        real_costs.pick_candidate(conn, _method("M0002"), None)


def test_twins_name_the_side_the_lab_did_not_record():
    flat_c = _cand("M0001-A", "M0001")
    f, g = real_costs.twins(flat_c)
    assert f is flat_c and g.id == "M0001-A-GT"
    assert g.rules == replace(flat_c.rules, cost_model="gotrade")
    real_c = _cand("M0031-A", "M0031", rules=MONTHLY_HOLD_FRAC_GOTRADE)
    f, g = real_costs.twins(real_c)
    assert g is real_c and f.id == "M0031-A-FLAT" and f.rules.cost_model == "flat"


def test_a_variant_with_its_own_cost_rate_has_no_twin():
    odd = _cand("M0001-A", "M0001", rules=replace(MONTHLY_HOLD, id="odd-fee", cost_rate=Decimal("0.002")))
    with pytest.raises(store.LabError, match="its own cost rate"):
        real_costs.twins(odd)


def test_measure_refuses_a_test_window_store(lab, recorded):
    conn, _ = lab
    c, trial = real_costs.pick_candidate(conn, recorded, None)
    with pytest.raises(store.LabError, match="dev window"):
        real_costs.measure(recorded, c, trial, smoke_test_data())


# ---- the journal -----------------------------------------------------------------------------


def test_the_journal_entry_is_one_plain_observation(lab, data, recorded):
    conn, _ = lab
    c, trial = real_costs.pick_candidate(conn, recorded, None)
    cmp = real_costs.measure(recorded, c, trial, data)
    before = _untouched(conn)
    with conn:
        entry = real_costs.journal(conn, cmp)
    row = conn.execute("SELECT * FROM insights WHERE id = ?", (entry,)).fetchone()
    assert row["kind"] == "observation" and row["method_id"] == "M0001"
    assert row["title"] == "SPY above its average: what Gotrade's real fees do to it"
    for text in (row["title"], row["body"]):
        assert "M0001" not in text and "`" not in text and "cost_model" not in text
    assert "count of tries did not move" in row["body"]
    assert _untouched(conn) == before


def _side(model, beats, failed=()):
    return real_costs.Side(
        model=model, candidate_id="M0001-A", total_return=0.5, cagr=0.1, max_drawdown=0.15,
        profit_factor=1.5, trades=120, sharpe=0.8, mar=0.6, exposure=0.9, costs_usd=10.0,
        cost_drag=0.02, spy_tr_return=0.4, spy_tr_cagr=0.08, beats_spy=beats, failed=failed,
    )


@pytest.mark.parametrize(
    ("flat_beats", "real_beats", "phrase"),
    [
        (True, False, "no longer beats SPY"),
        (True, True, "still beats SPY"),
        (False, False, "did not beat SPY at either fee"),
        (False, True, "beats SPY only at the real fees"),
    ],
)
def test_the_verdict_sentence(flat_beats, real_beats, phrase):
    cmp = real_costs.Comparison(
        method_id="M0001", method_name="x", candidate_id="M0001-A", recorded_model="flat",
        trial_n=55, recorded_total_return=0.5, start=date(1996, 1, 2), end=date(2015, 10, 16),
        fingerprint="smoke", flat=_side("flat", flat_beats),
        real=_side("gotrade", real_beats, () if real_beats else ("beats SPY TR",)),
    )
    _, body = real_costs.insight_text(cmp)
    assert phrase in body
    assert ("falls short on beating SPY" in body) is (not real_beats)


# ---- the command -----------------------------------------------------------------------------


def test_cli_lab_costs_reports_and_journals_without_moving_n(lab, data, recorded, monkeypatch, capsys, tmp_path):
    conn, path = lab
    before, notes = _untouched(conn), _insights(conn)
    monkeypatch.setattr(research, "load_store", lambda *a, **k: data)
    monkeypatch.setattr(real_costs, "discover", lambda: {"M0001": (recorded, HERE)})
    assert cli.main(["lab", "--db", str(path), "costs", "M0001", "--store", str(tmp_path / "store")]) == 0
    out = capsys.readouterr().out
    assert "report only" in out and "Gotrade real fees" in out and "reproduces it" in out
    assert _untouched(conn) == before
    assert _insights(conn) == notes + 1


def test_cli_refuses_an_unknown_method_with_exit_2_before_any_store(lab, tmp_path, monkeypatch):
    _, path = lab

    def boom(*a, **k):
        raise AssertionError("the store must not be loaded for a refusal")

    monkeypatch.setattr(research, "load_store", boom)
    assert cli.main(["lab", "--db", str(path), "costs", "M9999", "--store", str(tmp_path)]) == 2
    assert cli.main(["lab", "--db", str(path), "costs", "H-P7A", "--store", str(tmp_path)]) == 2


# ---- the M0031 rule --------------------------------------------------------------------------


def test_requires_real_cost_starts_at_m0031():
    assert not real_costs.requires_real_cost("M0030")
    assert real_costs.requires_real_cost("M0031") and real_costs.requires_real_cost("M1000")
    assert not real_costs.requires_real_cost("H-P7A")


def test_lab_run_refuses_a_flat_cost_variant_from_m0031(lab):
    conn, _ = lab
    flat = _method("M0031", cands=(_cand("M0031-A", "M0031"),))
    with pytest.raises(store.LabError, match="Gotrade's real fees"):
        runner.preflight(conn, flat, HERE, require_commit=False)
    real = _method("M0031", cands=(_cand("M0031-A", "M0031", rules=MONTHLY_HOLD_FRAC_GOTRADE),))
    runner.preflight(conn, real, HERE, require_commit=False)
    old = _method("M0030", cands=(_cand("M0030-A", "M0030"),))
    runner.preflight(conn, old, HERE, require_commit=False)


def test_every_committed_method_from_m0031_runs_at_real_fees():
    for mid, (method, _path) in discover().items():
        assert real_costs.real_cost_problem(method) is None, mid


# ---- the presets -----------------------------------------------------------------------------


def test_the_real_fee_presets_are_promotable_fractional_books():
    pairs = (
        (MONTHLY_HOLD_FRAC_GOTRADE, MONTHLY_HOLD_FRAC),
        (MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE, MONTHLY_RANK_WEEKLY_RESIZE_FRAC),
    )
    for preset, base in pairs:
        assert preset == replace(base, id=f"{base.id}-gotrade", cost_model="gotrade")
        assert preset in PRESETS
        assert roster.rules_for(preset.id) is preset
        assert rule_owner_inputs(preset) == ()
        assert preset.fractional and preset.engine == "book"
    assert PRESETS[-2:] == (MONTHLY_HOLD_FRAC_GOTRADE, MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE)
    # the whole-share flat preset's fractional twin is still the flat one
    assert promote.fractional_twin(MONTHLY_HOLD) is MONTHLY_HOLD_FRAC


# ---- opt-in: the real research store ---------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("SEER_LAB_COSTS_LIVE"),
    reason="set SEER_LAB_COSTS_LIVE=1 (and SEER_RESEARCH_STORE) to run lab costs M0007 on the real store",
)
def test_lab_costs_m0007_on_the_research_store(tmp_path, capsys):
    live_store = Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR)
    db = tmp_path / "lab.sqlite"
    shutil.copy(store.COMMITTED_DB, db)  # a copy: the committed database is never written
    assert cli.main(["lab", "--db", str(db), "costs", "M0007", "--store", str(live_store)]) == 0
    out = capsys.readouterr().out
    assert "lab costs M0007 -- M0007-" in out and "Gotrade real fees" in out
```
**Impact:** test-only. The fixture `recorded` runs two smoke-market backtests (the same cost as `test_lab_runner.py`); each `measure` runs two more.

### Step 10: Explore skill — real fees for new methods, `lab costs` for old ones
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md`
**Change:** six edits; the iron rules, the honesty rules and every other line stay.

10a. Lines 69–70, replace
```markdown
   - **Executable?** Gotrade means long only, whole shares, regular session. Leverage, shorting
     and non-default ETFs need owner inputs and are never eligible. Test them only as evidence.
```
with
```markdown
   - **Executable?** Gotrade means long only and the regular session. Limit orders take
     fractional shares; a take-profit/stop-loss bracket needs whole shares. Leverage, shorting
     and non-default ETFs need owner inputs and are never eligible. Test them only as evidence.
```

10b. After line 85 (the end of the "Trade it the way paper would: fractional shares" bullet), insert:
```markdown
   - **Pay what Gotrade really charges.** From M0031 on, every variant runs at Gotrade's real
     fees: build it on `MONTHLY_HOLD_FRAC_GOTRADE` or `MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE`
     (`sim/rules.py`). They are the fractional presets with `cost_model="gotrade"`: the fee
     schedule fitted to the owner's own order receipts (`sim/costs.py`;
     `python -m seer_engine sean calibrate` checks it against every stored order). `lab run`
     refuses a flat-cost variant. The fees bite hardest on small slots: a $28 order pays $0.13
     (0.47%) where the lab used to assume 0.1%, so a 20–40-way book pays several times what the
     old trials paid to trade. SPY pays the same fees in the same run, so the comparison stays
     fair. Another cadence at real fees is `replace(<book preset>, cost_model="gotrade")`: it
     runs on dev, but `promote` needs a preset of its id, so queue a `feature-wish` insight for
     one if it wins.
```

10c. Line 105, replace
```markdown
   - comparison with the parent or near misses
```
with
```markdown
   - comparison with the parent or near misses. A method from M0030 or earlier was measured at
     the flat 0.1%; compare against its numbers from `lab costs <id>` (both fees side by side),
     never against its recorded trial, or the fees decide the comparison instead of the idea
```

10d. Promotion step 0 (lines 161–167): after "...and the analysis must say so." append, as the rest of step 0:
```markdown
   **And at real fees.** A method from M0030 or earlier ran at the flat 0.1%. Before promoting
   it, run `lab costs MNNNN` (report only: no trial, N unchanged; it journals what the fees did).
   If its best variant stops beating SPY, or breaks a go-live condition at real fees, do not
   promote it. If it still passes, register its real-fee twin as a one-variant variation method
   on the `-gotrade` preset, run it on dev, and promote that one if it is still eligible. Paper
   pays real fees, so the look is spent on the configuration paper would trade, or not at all.
```

10e. Never table, after line 197 (the "It's eligible on dev, promote it as is" row), insert:
```markdown
| "My new method looks better at the flat 0.1%" | From M0031 `lab run` refuses it. The owner pays real fees; a method that only wins at the old assumption does not win. |
| "Compare my numbers with that old trial's" | An old trial paid 0.1% a trade. Use `lab costs <old id>` and compare real fees with real fees. |
| "`lab costs` showed it survives, call it eligible" | Never. `lab costs` is a report, not a trial. Only a new variation method on the `-gotrade` preset can be judged at real fees. |
```

10f. Quick reference, after line 208 (`lab run M0007 ...`), insert:
```text
lab costs M0007                   # report only: best variant at the flat 0.1% vs Gotrade's real fees; journals it, N unchanged
```
**Impact:** guidance only.

### Step 11: Method template on the real-fee preset
**File:** `.claude/skills/explore-and-experiment-new-method/method_template.py`
**Change:** lines 23–25 become
```python
# Fractional and at Gotrade's real fees by default: paper trades books in fractional shares, a 20M
# IDR book cannot fill whole-share slots at 2016+ prices (M0021), and from M0031 on `lab run`
# refuses a variant at the old flat 0.1%. Other real-fee preset: MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE.
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
```
and line 89 becomes
```python
def _v(suffix: str, params: Params, rationale: str, rules=MONTHLY_HOLD_FRAC_GOTRADE) -> Candidate:
```
**Impact:** a copied template passes the M0031 rule out of the box.

### Step 12: Sera skill — slates and promotions at real fees
**File:** `.claude/skills/sera-the-explorer/SKILL.md`
**Change:** five edits.

12a. Lines 51–52, replace
```markdown
3. **Choose the first slate** (and when you reserve a book idea, write in its hypothesis that it
   runs in fractional shares, so the child builds it that way) of `min(4, num-methods)` ideas from `lab status`, recent insights
```
with
```markdown
3. **Choose the first slate** (and when you reserve a book idea, write in its hypothesis that it
   runs in fractional shares at Gotrade's real fees, a `-frac-gotrade` preset, so the child builds
   it that way) of `min(4, num-methods)` ideas from `lab status`, recent insights
```

12b. After line 57 (the "Testable on the store's data" bullet), insert:
```markdown
   - **Survives real fees?** Before reserving a variation of a near miss from M0030 or earlier,
     run `lab costs <near miss>` (a minute or less, report only, N unchanged). A near miss whose
     edge the real fees erase is not worth a variation; journal that and pick another.
```

12c. Lines 79–82, replace
```markdown
   - **dev-eligible:** run the explore skill's **Promotion** yourself, now, in `$REPO`, one at a time.
     Start with its step 0, the fit check. If the eligible variant trades whole shares, first run
     its fractional twin as a one-variant variation method. Promote the twin, never the whole-share
     original. The look is spent on the configuration paper would trade, or not at all.
```
with
```markdown
   - **dev-eligible:** run the explore skill's **Promotion** yourself, now, in `$REPO`, one at a time.
     Start with its step 0, the fit check. If the eligible variant trades whole shares, or is a
     method from M0030 or earlier measured at the flat 0.1%, first run `lab costs` on it and then
     its fractional, real-fee twin as a one-variant variation method. Promote the twin, never the
     original. The look is spent on the configuration paper would trade, or not at all.
```

12d. Synthesis list, after line 98 (`- what data or features would unlock the most`), insert:
```markdown
   - what Gotrade's real fees did to the batch, when any `lab costs` ran or a method lost its
     edge to them
```

12e. Never table, after line 118, insert:
```markdown
| "Promote that old flat-fee winner, it passed dev" | Never as is. Run `lab costs` first, then its real-fee twin as a one-variant variation method; promote the twin. |
```
**Impact:** guidance only.

### Step 13: The design doc — costs measured, not assumed
**File:** `docs/plans/2026-10-03-seer-design.md`
**Change:** 13a, line 29, replace
```markdown
- Unverified, **assumed** (user, 2026-10-03): unfilled limit orders expire end of day; fees + slippage = 0.1% per side.
```
with
```markdown
- Unverified, **assumed** (user, 2026-10-03): unfilled limit orders expire end of day.
- Fees, **measured** 2026-10-07 from the owner's own order receipts (§15): a trading fee (0.2% of the order since 2026-06-16, at least $0.10), a small regulatory fee, and 11% VAT on both. The original assumption, preserved: *"fees + slippage = 0.1% per side"* — still what every lab trial up to M0030 and every paper strategy on the roster that day was measured with.
```
§5's table row (line 102) is left as it is: the explore skill forbids editing §1/§5, and §15 states that the §5 simulator keeps 0.1%.

13b. Append after line 417 (the end of §14):
```markdown

## 15. Measured 2026-10-07: what Gotrade really charges

§2 assumed 0.1% of every trade for fees and slippage together. The owner's own order receipts —
30 Gotrade "Order Summary" screens from 2025-06-10 to 2026-10-07, now stored by Sean in
`sean_orders` — show what an order actually pays. Every receipt itemises three fees, and every
total reconciles to the cent (a buy pays the amount plus the fees; a sell receives the amount
minus the fees):

| Dates | Orders | Trading fee | Regulatory fee | PPN (VAT) |
|---|---|---|---|---|
| 2025-06-10 | 2 buys ($707, $1,429) | none | 0.3% of the amount ($2.13, $4.29) | none |
| 2025-06-26 → 2026-03-25 | 5 buys ($105 – $1,833) | 0.3% of the amount | $0.06 – $0.11 | 11% of the two fees |
| 2026-06-16 → 2026-10-07 | 22 buys, 1 sell ($27.90 – $1,673) | 0.2% of the amount, at least $0.10 | $0.02 on $27.90, $0.07 on a $72.51 sell, $0.11 on the two orders over $1,000 | 11% of the two fees |

What that means at the sizes the owner trades:

| Order | Fees paid | Share of the order | The old assumption |
|---|---|---|---|
| $27.90 buy (one slot of a 20-way book) | $0.13 | 0.47% | $0.03 (0.1%) |
| $72.51 sell | $0.24 | 0.33% | $0.07 |
| $1,673.14 buy | $3.84 | 0.23% | $1.67 |

A round trip on a $28 slot costs about 0.9% instead of 0.2%. Small orders pay several times the
assumption because of the $0.10 minimum and the near-flat regulatory fee.

**What changed.**
- `engine/src/seer_engine/sim/costs.py` holds the schedule, dated by regime, and the book engine
  prices a trade with it when the rule set says `cost_model="gotrade"`. The SPY benchmark in the
  same run pays the same fees. A backtest prices every trade at the regime in force today: the lab
  asks what a method would cost to run now, not what it cost in 1998.
- Lab methods from M0031 on are measured at these fees; `lab run` refuses a flat-cost variant.
  `MONTHLY_HOLD_FRAC_GOTRADE` and `MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE` are the presets.
- `python -m seer_engine sean calibrate` replays the schedule over every order Sean has stored and
  exits 1 when an order since the current regime is off by more than a cent — the signal that
  Gotrade changed its fees and the schedule needs a new dated regime.
- `python -m seer_engine lab costs MNNNN` re-runs a recorded method at both costs and journals the
  difference. It records no trial, so the lab's N does not move and no verdict changes.

**What did not change.** Every lab trial up to M0030, every pre-registration and every paper
strategy on the roster keeps the flat 0.1% it was measured and frozen under, so no recorded number
and no pinned digest moves. The §5 bracket simulator keeps 0.1% too. Slippage is not modelled
separately: fills still happen at the open or the limit, as before.
```
**Impact:** documentation only. Receipt figures are from `.workflows/plan/sean-gotrade-tracker/screenshots_truth.json` (the repo is public by the owner's choice; receipts carry no account data).

## Verification

**Build:** worktree venv first (memory: worktree needs its own venv):
```bash
cd /home/miftah/.worktrees/seer/sean-gotrade-tracker
python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'
cd engine && .venv/bin/ruff check .
```
**Tests:**
```bash
cd /home/miftah/.worktrees/seer/sean-gotrade-tracker/engine
.venv/bin/pytest -q tests/test_sean_calibrate.py tests/test_lab_costs.py tests/test_sim_rules.py \
  tests/test_cost_model_pins.py tests/test_paper_kickoff.py \
  tests/test_lab_runner.py tests/test_lab_methods.py tests/test_registry.py tests/test_paper_roster.py \
  tests/test_promote_command.py tests/test_cli.py
cd ../web && npm ci && npx vitest run lib/cadence.test.ts
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres .venv/bin/pytest -q   # the full suite, DB tests included
```
**Manual check** (main checkout's store; a scratch copy of the lab database so the committed one is not written):
```bash
cd /home/miftah/.worktrees/seer/sean-gotrade-tracker
SCRATCH=$(mktemp -d); cp lab/lab.sqlite "$SCRATCH/lab.sqlite"
engine/.venv/bin/python -m seer_engine lab --db "$SCRATCH/lab.sqlite" costs M0007 --store /home/miftah/seer/engine/.research
SEER_LAB_COSTS_LIVE=1 SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
  engine/.venv/bin/pytest -q engine/tests/test_lab_costs.py -k research_store
engine/.venv/bin/python -m seer_engine sean calibrate   # against Neon, once Phase 2's uploads have stored orders
```
Read the `lab costs` table: the flat column's total return must equal M0007-N20-RAW's recorded trial ("reproduces it"); the real-fee column must show more fees paid. `git status` must show `lab/lab.sqlite` unmodified.

**Exit criteria:** ruff + the full pytest suite green (DB tests with `PG_TEST_URL`), including Phase 6's `test_cost_model_pins.py` with the two real-fee presets in `PRESETS`; `web/lib/cadence.test.ts` green; `sean calibrate` exits 0 on Phase 6's fee fixture and 1 on a drifted receipt; `lab costs` writes exactly one insight and leaves `trials`, `trial_moments`, `methods`, N and the look count byte-for-byte unchanged; `lab run` refuses a flat-cost M0031 and accepts one on `MONTHLY_HOLD_FRAC_GOTRADE`; `lab costs M0007` runs locally against the research store (`SEER_LAB_COSTS_LIVE=1`; skipped in CI).

## Handoffs

- **Phase 6:** reconciled — bound to `GOTRADE.current.since`, `fee_parts(side, amount, on)`, `FeeParts.trading/.regulatory/.ppn`, current-regime pricing in backtests; Phase 6 adds no preset, so Steps 6–7 here add both, and Step 7 edits Phase 6's `test_sim_rules.py` and `test_cost_model_pins.py` on top of Phase 6.
- **Phase 4:** reconciled — Step 2 matches Phase 4's Step 5 file as written (`add_arguments` with `sub = p.add_subparsers(dest="sean_command", ...)`, `_HANDLERS = {"marks": _marks}` of `(conn, args) -> int` handlers, `run` owning the connection through `db.connect()`, module-level `log`, `argparse`/`psycopg`/`db` imported). The command tests stub `seer_engine.db.connect`, which works because `run` calls it through the module.
- **After merge, in the main checkout (completion handler or the next Sera run, not this phase):** run `lab costs` on every lab method on the paper roster (RAW is M0007-N20-RAW; also each `promoted_from` lab method), then `lab stage`, commit and push, so the owner sees on seertrade.site/sera what the real fees do to the methods he follows. That writes the shared `lab/lab.sqlite`, which this phase must not commit.
- **Paper (future, unowned):** `paper/benchmark.py` still prices the paper SPY benchmark at `COST_RATE`; a real-fee strategy promoted to the roster would be compared with a flat-fee SPY on the paper page. Phase 6 owns the lab benchmark only.
- **Web (future, unowned):** the Sera site does not show which trials were measured at real fees; once M0031+ trials exist, a small "real fees" mark on method pages would stop a reader comparing across the boundary.
- **Docs drive-bys left alone:** design §2's "Whole shares only for limit orders" is stale (fractional limit orders verified 2026-10-07; only the TP/SL bracket is whole-share); `method_template.py`'s hypothesis placeholder still says "max DD <= 15%" (the bar is 20% since 2026-10-07). Neither is R5; the owner's next doc pass.

## Rollback

Revert this phase's commit. Nothing persistent is created by the code: no migration, no trial row. Insights that someone appended by running `lab costs` and staging stay in `lab/lab.sqlite` (append-only by design) and are harmless without the command. Reverting the presets is safe while no method file uses them; after an M0031+ method has run on one, revert only the `lab costs` / calibrate parts and keep Steps 5–6.
