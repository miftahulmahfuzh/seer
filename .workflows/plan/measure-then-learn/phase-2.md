# Phase 2: Interest on idle cash (cash_yield lever)

**Plan set:** `MEASURE_THEN_LEARN_PLAN.md`
**Analysis:** `20261012-205553-M7T1_code_analyzer.md`
**Satisfies:** R2 — idle cash can earn the cached 13-week T-bill yield, as a versioned, explicit simulator input
**Depends on:** Phase 1
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/sim` (plus `backtest/book_runner.py`, `backtest/dev.py`, `paper/book.py`, `commands/promote.py`, `lab/runner.py`)

---

## Goal

`TradeRules` gains a `cash_yield` lever (default `None`, a true no-op held in
`LEVERS_SINCE_PINS`). With `cash_yield="T13W"`, cash held at the previous close earns
`q(cash × rate × calendar days / 36500)` at the open of each session, before dividends, with the
rate read point in time from the research store's `T13W` series on the previous session.
Every existing preset, digest and recorded result stays byte-identical, a store without the series
is refused before anything is spent, and paper trading refuses such rules with a plain message.

## Interface Contract

**Deletes:** nothing.

**Renames:** nothing.

**Creates:**
- `sim.rules.CASH_YIELD_SERIES: tuple[str, ...] = ("T13W",)` (`sim/rules.py`), re-exported from `seer_engine.sim`.
- `TradeRules.cash_yield: str | None = None` — the LAST field, after Phase 1's `resize_basis`.
- `LEVERS_SINCE_PINS["cash_yield"] = None`.
- owner-input label `"cash-yield"` from `rule_owner_inputs` when `cash_yield` is set.
- `sim.book.accrued_interest(cash: Decimal, annual_pct: Decimal, days: int) -> Decimal` (`sim/book.py`).
- `BookStep.interest: Decimal = Decimal(0)` — new LAST field, defaulted.
- `BookResult.interest_usd: Decimal = Decimal("0.0000")` — new LAST field, defaulted (`backtest/book_runner.py`).
- `backtest.book_runner.cash_rate_on(market, name, data_date) -> Decimal`.
- `lab.runner.missing_cash_yield(candidates, market) -> tuple[str, ...]`.
- `paper.book._lab_only(rules)` (private refusal helper).
- `engine/tests/test_cash_yield.py` (new test module).
- `labkit.SMOKE_T13W` (test fixture): a one-row `T13W` series (4.0 from 1993-01-29), which the lab
  smoke test attaches to the market of every candidate whose rules set `cash_yield`.

**Signature changes:**
- `step_book(book, session, bars, targets, rules, dividends=..., idle_symbol_ok=False)` ->
  `step_book(book, session, bars, targets, rules, dividends=..., idle_symbol_ok=False, *, cash_rate: Decimal | None = None, deposited: Decimal = Decimal(0))`.
  Existing positional/keyword call shapes are unchanged. `run_book` passes the two new keywords
  **only** when `rules.cash_yield` is set, so every existing call (and the `steps` spy fixture in
  `tests/test_book_runner.py`, whose signature has no `**kw`) sees exactly today's call shape.

**Behaviour changes (only for rules with `cash_yield` set):**
- `TradeRules(...)` raises `ValueError` for an unknown series, a non-book engine, or `cash_yield` together with `idle_symbol`; `TypeError` for a non-str.
- `describe_rules`: the "Idle cash" line (index 10) has a new text for the set case; the `None` line and the `idle_symbol` line are byte-identical; still 12 lines.
- `step_book` raises `ValueError` when `rules.cash_yield` is set and `cash_rate` is None, or `cash_rate` is given while `rules.cash_yield` is None.
- `run_book` raises `ValueError` up front when `market.series` lacks the named series.
- `lab.runner.preflight_data` and `lab.runner.run_test` raise `store.LabError` for a candidate whose `cash_yield` series is absent from the store.
- `paper.book.decide_book` / `settle_book` raise `ValueError` for `cash_yield` rules.
- `commands.promote._check_rules` raises `NotPromotable` for `cash_yield` rules.

**Requires (from earlier phases):**
- Phase 1 appended `resize_basis: Literal["equity", "target"] = "equity"` after `cost_model` in `TradeRules`, appended `"equity"` to `_V0_LEVERS`, added `LEVERS_SINCE_PINS["resize_basis"] = "equity"`, added `TARGET_RESIZE_BAND`, and updated the two golden tests this phase touches again (`tests/test_sim_rules.py::test_a_lever_added_after_the_pins_is_left_out_of_canonical_text_at_its_default`, `tests/test_backtest_dev_report.py::test_preregistration_names_each_finalist_exactly`) to name `resize_basis`.
- Phase 1 created `engine/.venv` in the worktree.
- Phase 1 did not change `step_book`'s signature, `BookStep`, `BookResult`, or the `repr` of `Fill`/`Trade`/`Position`/`BookSnapshot` (the preset pins below depend on those reprs).

**Leaves alone (owned by others):**
- `PRESETS` and every preset constant (Phase 3 adds the `-tband`, `-tband-cash` presets).
- `web/**`, `engine/tests/test_sean_mirrors.py` (Phase 3).
- The resize band logic and `TARGET_RESIZE_BAND` in `sim/book.py` / `sim/rules.py` (Phase 1).
- `paper/roster.py` `SEED_ROWS` and every pinned spec digest.
- `commands/lab.py`, survivorship code, skills (Phase 4).
- Lab methods, `lab/lab.sqlite`, `web/data/lab.json` (Phases 5, 7).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/sim/rules.py` | modify | module docstring paragraph; `CASH_YIELD_SERIES`; field `cash_yield`; validation; `_V0_LEVERS`; `LEVERS_SINCE_PINS`; `rule_owner_inputs`; `describe_rules` Idle-cash line; `_CASH_YIELD_NAMES` |
| `engine/src/seer_engine/sim/__init__.py` | modify | import/export `CASH_YIELD_SERIES` |
| `engine/src/seer_engine/sim/book.py` | modify | docstring step 0; `accrued_interest`; `_check_cash_rate`; `BookStep.interest`; `step_book` keywords + accrual |
| `engine/src/seer_engine/backtest/book_runner.py` | modify | docstring step 3; `BookResult.interest_usd`; `cash_rate_on`; `run_book` reads the rate, passes it, sums interest |
| `engine/src/seer_engine/backtest/dev.py` | modify | `candidate_window` docstring sentence at :269 |
| `engine/src/seer_engine/paper/book.py` | modify | `_lab_only` refusal in `decide_book` and `settle_book` |
| `engine/src/seer_engine/commands/promote.py` | modify | `_check_rules` refuses `cash_yield` rules first |
| `engine/src/seer_engine/lab/runner.py` | modify | `missing_cash_yield`; refusal in `preflight_data` and `run_test` |
| `engine/tests/test_cash_yield.py` | create | lever, accrual, runner, paper/promote refusal, preset pins |
| `engine/tests/test_lab_runner.py` | modify | two preflight tests |
| `engine/tests/test_sim_rules.py` | modify | `LEVERS_SINCE_PINS` equality gains `cash_yield` |
| `engine/tests/test_backtest_dev_report.py` | modify | `TradeRules(...)` literal gains `cash_yield=None` |
| `engine/tests/labkit.py` | modify | `SMOKE_T13W`: a flat T-bill series a cash-yield candidate's smoke market is given (Step 11) |
| `engine/tests/test_lab_methods.py` | modify | `test_candidate_runs_a_smoke_window` attaches `SMOKE_T13W` for a candidate whose rules set `cash_yield` (Step 11) |

## Implementation Steps

Line numbers are today's (base `5faa3cb`). Phase 1 inserts a few lines in `sim/rules.py` and
`sim/book.py` before most of these anchors; find each anchor by the quoted text, not the number.

### Step 0: Set up and confirm the preset pins before touching code
**File:** none (worktree shell)
**Change:** Make sure `engine/.venv` exists (Phase 1 creates it; otherwise
`python3.11 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'`). Start
Postgres for DB tests and export `PG_TEST_URL` (see CLAUDE.md). Then, on the tree as Phase 1 left
it and BEFORE any Phase 2 edit, run the pin script below and check that it prints exactly the
digests in `PRESET_RUN_PINS` (Step 9). They were computed on `5faa3cb` by the planner. If Phase 1
changed one of them, stop: Phase 1 moved an existing preset's run, and that breaks invariant 2.
Do not just paste the new value.
**Code:** (save as a scratch file outside the repo, run with `cd engine && PYTHONPATH=src .venv/bin/python <file>`)
```python
import hashlib
import sys
from decimal import Decimal

sys.path.insert(0, "tests")
from allocatorkit import FIXED, FixedParams
from simkit import D
from stratkit import hist

from seer_engine import dates
from seer_engine.backtest.book_runner import run_book
from seer_engine.backtest.market import Market, Membership
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine.sim.rules import PRESETS, V0_BOOK

PIN_DAYS = dates.sessions(D("2024-12-02"), D("2025-05-30"))
PIN_START, PIN_END = D("2025-01-15"), D("2025-05-30")
PIN_PARAMS = FixedParams((("AAA", Decimal("0.45")), ("BBB", Decimal("0.35"))))
PIN_DIVIDENDS = {
    "AAA": {D("2025-02-20"): Decimal("0.10"), D("2025-05-15"): Decimal("0.12")},
    "BBB": {D("2025-03-03"): Decimal("0.20")},
}


def pin_market() -> Market:
    n = len(PIN_DAYS)
    aaa = hist("AAA", [round(10.0 + 0.05 * t + (1.5 if (t // 7) % 2 else 0.0), 2) for t in range(n)], days=PIN_DAYS)
    bbb = hist("BBB", [round(40.0 - 0.04 * t + (2.0 if (t // 11) % 2 else 0.0), 2) for t in range(n)], days=PIN_DAYS)
    bil = hist("BIL", [100.0] * n, days=PIN_DAYS, spread=0.05)
    return Market(
        history={"AAA": aaa, "BBB": bbb, "BIL": bil},
        membership=Membership((("AAA", D("2020-01-02"), None), ("BBB", D("2020-01-02"), None))),
        fx=((D("2024-11-29"), Decimal("16000")),),
    )


def run_digest(r) -> str:
    text = repr((r.snapshots, r.fills, r.trades, r.open_at_end, r.dividends_usd, r.costs_usd, r.rejections, r.cashflows))
    return hashlib.sha256(text.encode()).hexdigest()


m = pin_market()
for rules in (V0_BOOK,) + tuple(p for p in PRESETS if p.engine == "book"):
    r = run_book(m, FIXED, PIN_PARAMS, rules, PIN_START, PIN_END, dividends=PIN_DIVIDENDS, contributions=OWNER_MONTHLY)
    print(f'    "{rules.id}": "{run_digest(r)}",')
```
**Impact:** none (read-only). It records the "before" state that the pin test checks.

### Step 1: The lever in `TradeRules`
**File:** `engine/src/seer_engine/sim/rules.py`

**1a. Module docstring.** At :22 (after the `resize_cadence` paragraph ending
"``is_resize_session``."), insert this paragraph before the blank line that precedes "Pure:":
```python

``cash_yield`` names a market series (``CASH_YIELD_SERIES``: only ``"T13W"``, the 13-week Treasury
bill yield the research store caches from EODHD) whose annual percent idle cash is credited at,
by ``sim.book.step_book`` at each open, read point in time by ``backtest.book_runner.run_book``.
``None`` (every rule set before 2026-10-12) credits nothing, and is a ``LEVERS_SINCE_PINS`` no-op.
It is a book-engine lever, it excludes ``idle_symbol`` (two answers to one question), and it raises
the owner input ``cash-yield``: nobody has verified that Gotrade pays interest on idle dollars.
```

**1b. Constant.** Directly after Phase 1's `TARGET_RESIZE_BAND = Decimal("0.20")` line (Phase 1
puts it, with its three-line comment, right after `RESIZE_BAND = Decimal("0.01")` at :43) and
before `SHARE_QUANTUM`, add:
```python
#: The market series ``TradeRules.cash_yield`` may name: an annual yield in percent that idle cash
#: is credited at. Only the 13-week US Treasury bill (EODHD ``IRX.INDX``), which the research store
#: already holds (``research.MARKET_SERIES_NAMES``); a test keeps the two in step.
CASH_YIELD_SERIES: tuple[str, ...] = ("T13W",)
```

**1c. Field.** At :93, after `cost_model: CostModel = "flat"` and AFTER Phase 1's
`resize_basis` line (it must be the last field), add:
```python
    cash_yield: str | None = None
```

**1d. Validation.** In `__post_init__`, directly before `is_v0 = _lever_values(self) == _V0_LEVERS`
(:141; after Phase 1's `resize_basis` validation), insert:
```python
        if self.cash_yield is not None:
            if not isinstance(self.cash_yield, str):
                raise TypeError(f"cash_yield must be a str or None, got {type(self.cash_yield).__name__}")
            if self.cash_yield not in CASH_YIELD_SERIES:
                raise ValueError(f"unknown cash_yield {self.cash_yield!r}; expected one of {CASH_YIELD_SERIES}")
            if self.engine != "book":
                raise ValueError(
                    f"cash_yield is a book-engine lever; the {self.engine} simulator credits idle cash nothing"
                )
            if self.idle_symbol is not None:
                raise ValueError(
                    f"cash_yield {self.cash_yield!r} and idle_symbol {self.idle_symbol!r} are two answers to "
                    "one question (what idle money earns); use one"
                )
```

**1e. `_V0_LEVERS`.** At :153-167 the tuple (after Phase 1) ends `_DEFAULT_COST, "flat", "equity",`.
Append `None` as the last element. Full tuple after this phase:
```python
_V0_LEVERS: tuple[object, ...] = (
    _V0_ID,
    "bracket_v0",
    "daily",
    None,
    "limit",
    4,
    5,
    False,
    False,
    False,
    None,
    _DEFAULT_COST,
    "flat",
    "equity",
    None,
)
```
(Phase 1's 14th element is exactly `"equity"`; this phase only appends `None`.)

**1f. `LEVERS_SINCE_PINS`.** At :247-250, append one entry after Phase 1's `resize_basis`:
```python
LEVERS_SINCE_PINS: dict[str, object] = {
    "resize_cadence": None,  # the rank/resize cadence split, 2026-10-05
    "cost_model": "flat",  # Gotrade's measured fee schedule (sim.costs), 2026-10-07
    "resize_basis": "equity",  # the band measured against the holding's own target, 2026-10-12
    "cash_yield": None,  # interest on idle cash at a T-bill yield, 2026-10-12
}
```
(The `resize_basis` line is Phase 1's, quoted verbatim.)

**1g. `rule_owner_inputs`.** Replace the function at :335-354 with:
```python
def rule_owner_inputs(rules: TradeRules) -> tuple[str, ...]:
    """The Gotrade features ``rules`` needs that the owner has not verified, sorted and unique.

    ``market-on-open`` (entry "open"), ``etf:<symbol>`` (an idle instrument outside
    ``DEFAULT_ETFS``), ``fee`` (a flat cost rate other than 0.1% per side) and ``cash-yield``
    (idle cash credited a T-bill yield: nobody has verified that Gotrade pays interest on idle
    dollars, or that the owner sweeps them into a T-bill fund). Empty means executable under the
    conservative owner-input defaults. Fractional shares are not on the list: the owner verified
    that Gotrade takes fractional limit buys and sells (2026-10-07), and the paper roster already
    trades its lab winners that way. Neither is ``cost_model="gotrade"``: its schedule is fitted
    to the owner's own Gotrade receipts (``sim.costs``), and it requires the default
    ``cost_rate``, so it never raises ``fee`` either.
    """
    _rules(rules)
    out: set[str] = set()
    if rules.entry == "open":
        out.add("market-on-open")
    if rules.idle_symbol is not None and rules.idle_symbol not in DEFAULT_ETFS:
        out.add(f"etf:{rules.idle_symbol}")
    if rules.cost_model == "flat" and rules.cost_rate != _DEFAULT_COST:
        out.add("fee")
    if rules.cash_yield is not None:
        out.add("cash-yield")
    return tuple(sorted(out))
```

**1h. `describe_rules` Idle-cash line.** Replace :439-442:
```python
    if rules.idle_symbol is None:
        lines.append("Idle cash: held as cash, earning nothing.")
    else:
        lines.append(f"Idle cash: the unallocated weight is held in {rules.idle_symbol} on decision sessions.")
```
with:
```python
    if rules.idle_symbol is not None:
        lines.append(f"Idle cash: the unallocated weight is held in {rules.idle_symbol} on decision sessions.")
    elif rules.cash_yield is None:
        lines.append("Idle cash: held as cash, earning nothing.")
    else:
        lines.append(
            f"Idle cash: held as cash and credited {_CASH_YIELD_NAMES[rules.cash_yield]}, read at the "
            "previous session's close, for the calendar days since the last session, at each open "
            "(needs owner verification: cash-yield)."
        )
```
and add this module-level mapping directly after the `_pct` function (:357-359):
```python
# The plain-English name of each CASH_YIELD_SERIES entry, for describe_rules.
_CASH_YIELD_NAMES: dict[str, str] = {"T13W": "the 13-week US Treasury bill yield"}
```
**Impact:** default rules unchanged (`cash_yield` omitted from `registry._canon` and
`roster.rules_dict` at `None`), so every lab config digest and paper spec digest is unchanged.
`dev_report._rules_literal` and the per-finalist rules table now list `cash_yield` (Step 10 updates
the one golden test). `promote.fractional_twin` compares every field except `id`/`fractional`,
so `cash_yield` simply has to match. That is correct.

### Step 2: Export from `seer_engine.sim`
**File:** `engine/src/seer_engine/sim/__init__.py:55-85` and `:89-162`
**Change:** add `CASH_YIELD_SERIES` to the `from seer_engine.sim.rules import (...)` list
(alphabetically, before `DAILY_SWITCH`) and `"CASH_YIELD_SERIES",` to `__all__` (after
`"BRACKET_ENGINES",`). Leave Phase 1's `TARGET_RESIZE_BAND` entries as they are.
**Code:**
```python
from seer_engine.sim.rules import (
    BRACKET_ENGINES,
    CASH_YIELD_SERIES,
    DAILY_SWITCH,
```
```python
__all__ = [
    "BRACKET_ENGINES",
    "CASH_YIELD_SERIES",
    "COST_RATE",
```
**Impact:** none.

### Step 3: Accrual in `step_book`
**File:** `engine/src/seer_engine/sim/book.py`

**3a. Module docstring.** At :13-14, replace
```
1. dividends (``rules.dividends``): each position held before S with an ex-date on S is
   credited ``q(shares × amount)``;
```
with
```
0. interest (``rules.cash_yield`` only): the cash held at the previous close, less any
   ``deposited`` the caller credited at this open, earns ``accrued_interest(cash, cash_rate,
   (S − last_session).days)`` -- simple ACT/365 at the annual percent the caller read for the
   previous session -- credited to cash. A book never stepped (``last_session`` None) earns
   nothing. Like dividends, interest is not in the night-before buy budget (``book.cash`` plus
   planned sells); it reaches sizing through the next snapshot's equity;
1. dividends (``rules.dividends``): each position held before S with an ex-date on S is
   credited ``q(shares × amount)``;
```

**3b. Constant + helpers.** After `_NO_DIVIDENDS: Mapping[str, Decimal] = MappingProxyType({})`
(:70), add:
```python
_PERCENT_YEAR = Decimal(36500)  # 100 (a percent) x 365 (ACT/365 calendar days)
```
After `_int` (:107-110, end of the validation section), add:
```python
def accrued_interest(cash: Decimal, annual_pct: Decimal, days: int) -> Decimal:
    """Simple ACT/365 interest on ``cash`` for ``days`` calendar days at ``annual_pct`` percent a year.

    ``q(cash × annual_pct × days / 36500)``, so ``Decimal("4.057")`` is 4.057% a year, the unit
    the market series carries. 0 when ``cash``, ``days`` or the rate is not positive: an empty
    or overdrawn balance is neither paid nor charged. A negative rate is a ValueError (the
    runner floors the series at 0 before it gets here); a float anywhere is a TypeError.
    """
    _decimal("cash", cash)
    rate = _decimal("annual_pct", annual_pct)
    if rate < 0:
        raise ValueError(f"annual_pct must be >= 0, got {rate}")
    _int("days", days)
    if cash <= 0 or days <= 0 or rate == 0:
        return _ZERO
    return q(cash * rate * days / _PERCENT_YEAR)


def _check_cash_rate(
    book: Book, rules: TradeRules, cash_rate: object, deposited: object
) -> tuple[Decimal | None, Decimal]:
    """``(cash_rate, deposited)`` checked against ``rules.cash_yield`` (see ``step_book``)."""
    if rules.cash_yield is None:
        if cash_rate is not None:
            raise ValueError(
                f"rules {rules.id!r} credit idle cash nothing (cash_yield is None); cash_rate must be None"
            )
    elif cash_rate is None:
        raise ValueError(
            f"rules {rules.id!r} credit idle cash at the {rules.cash_yield} yield; pass that yield's "
            "annual percent for the previous session as cash_rate"
        )
    rate: Decimal | None = None
    if cash_rate is not None:
        rate = _decimal("cash_rate", cash_rate)
        if rate < 0:
            raise ValueError(f"cash_rate must be >= 0, got {rate}")
    fresh = _decimal("deposited", deposited)
    if fresh < 0 or fresh > book.cash:
        raise ValueError(f"deposited must be in [0, book.cash = {book.cash}], got {fresh}")
    if fresh != 0 and rate is None:
        raise ValueError("deposited only shapes the interest base; it needs a cash_rate")
    return rate, fresh
```
(`_check_cash_rate` refers to `Book`, which is defined later in the module. That is fine because
it is only a name lookup at call time, and `from __future__ import annotations` is already at the
top of the file.)

**3c. `BookStep`.** Replace :299-306 with:
```python
@dataclass(frozen=True, slots=True)
class BookStep:
    """One stepped session. ``interest``: the cash interest credited at the open (``rules.cash_yield``
    only; 0 otherwise), already in ``book.cash`` and the snapshot."""

    book: Book
    fills: tuple[Fill, ...]
    trades: tuple[Trade, ...]
    dividends: tuple[tuple[str, Decimal], ...]
    rejected: tuple[tuple[str, RejectReason], ...]
    snapshot: BookSnapshot
    interest: Decimal = _ZERO
```

**3d. `step_book` signature, docstring and checks.** Replace the head of `step_book` (:486-528,
from `def step_book(` through `if not isinstance(idle_symbol_ok, bool): raise TypeError(...)`) with:
```python
def step_book(
    book: Book,
    session: date,
    bars: Mapping[str, Bar],
    targets: tuple[Target, ...] | None,
    rules: TradeRules,
    dividends: Mapping[str, Decimal] = _NO_DIVIDENDS,
    idle_symbol_ok: bool = False,
    *,
    cash_rate: Decimal | None = None,
    deposited: Decimal = _ZERO,
) -> BookStep:
    """Advance ``book`` through the NYSE session ``session`` (see the module docstring).

    ``targets`` None: not a decision session (no signal exits, entries, trims or adds).
    ``targets`` (): a decision session that wants nothing (every position is signal-exited).
    ``dividends``: {symbol: cash amount per share} for ex-dates ON ``session``.
    ``idle_symbol_ok``: True when the caller appended the ``rules.idle_symbol`` target itself
    (the runner); otherwise a target for the idle instrument is a ValueError.
    ``cash_rate``: with ``rules.cash_yield`` set, required: the yield's annual percent as known
    at the previous session's close (``Decimal("4.057")`` = 4.057%), >= 0; with it None, must be
    None. ``deposited``: cash the caller added to ``book.cash`` at this open (the owner's
    deposit), which was not there overnight and so earns no interest for the gap; in
    ``[0, book.cash]``, and non-zero only with a ``cash_rate``.

    TypeError on a wrong type (a float anywhere included). ValueError when ``rules.engine`` is
    not "book", ``session`` is not an NYSE session after ``book.last_session``, the targets
    repeat a symbol, they weigh more than 1 while ``rules.max_positions`` is None, or
    ``cash_rate``/``deposited`` disagree with ``rules.cash_yield``. A new entry under entry
    "limit" with no limit price is bought like "open_limit" (never an error).
    """
    if not isinstance(book, Book):
        raise TypeError(f"book must be a Book, got {type(book).__name__}")
    if not isinstance(rules, TradeRules):
        raise TypeError(f"rules must be a TradeRules, got {type(rules).__name__}")
    if rules.engine != "book":
        raise ValueError(f"step_book runs engine 'book' rules only, got {rules.engine!r} ({rules.id})")
    _date("session", session)
    if not dates.is_session(session):
        raise ValueError(f"{session} is not an NYSE session")
    if book.last_session is not None and session <= book.last_session:
        raise ValueError(f"{session} is not after the last session stepped ({book.last_session})")
    if not isinstance(bars, Mapping):
        raise TypeError(f"bars must be a Mapping, got {type(bars).__name__}")
    if not isinstance(dividends, Mapping):
        raise TypeError(f"dividends must be a Mapping, got {type(dividends).__name__}")
    if not isinstance(idle_symbol_ok, bool):
        raise TypeError("idle_symbol_ok must be a bool")
    rate, fresh = _check_cash_rate(book, rules, cash_rate, deposited)
```
Everything after that line (`held_at_night = book.held()` onward) stays as Phase 1 left it,
except for 3e and 3f.

**3e. The accrual.** Directly before the comment
`    # (1) dividends on the ex-date, to positions held at the previous close.` (:565), insert:
```python
    # (0) interest on the cash held at the previous close (rules.cash_yield), before anything moves.
    interest = _ZERO
    if rate is not None and book.last_session is not None:
        interest = accrued_interest(book.cash - fresh, rate, (session - book.last_session).days)
        cash += interest

```

**3f. The return.** Replace the final `return BookStep(...)` (:749-756) with:
```python
    return BookStep(
        book=Book(cash=cash, equity=equity_now, positions=positions, last_session=session),
        fills=tuple(fills_open + fills_trim + fills_buy + fills_intraday),
        trades=tuple(trades),
        dividends=tuple(credited),
        rejected=tuple(rejected),
        snapshot=BookSnapshot(date=session, cash_usd=cash, equity_usd=equity_now, invested_usd=invested),
        interest=interest,
    )
```
**Impact:** with `cash_rate=None` (every existing caller), `rate is None` and `interest = 0`, so
the session is unchanged. The night plan (`available = book.cash + planned`) does not see
interest, the same way it does not see same-day dividends.

### Step 4: The runner reads the rate point in time
**File:** `engine/src/seer_engine/backtest/book_runner.py`

**4a. Module docstring.** At :21-22, replace
```
3. ``step_book`` gets S's bars for every held or targeted symbol, and (``rules.dividends`` only)
   the cash dividends whose ex-date is S for the symbols held at night;
```
with
```
3. ``step_book`` gets S's bars for every held or targeted symbol, (``rules.dividends`` only)
   the cash dividends whose ex-date is S for the symbols held at night, and (``rules.cash_yield``
   only) ``cash_rate_on(market, rules.cash_yield, data_date)`` -- the yield as published by the
   previous session, never S's -- plus the deposit credited at S's open, which earns nothing for
   the gap;
```

**4b. `BookResult`.** Replace the class (:104-131) with:
```python
@dataclass(frozen=True)
class BookResult:
    """One book-engine run.

    ``snapshots[0]`` is ``BookSnapshot(prev_session(start), cash0, cash0, 0)``, then one per
    session (after any forced close). ``fills`` is every fill in execution order, forced closes
    included; ``trades`` every closed holding episode in exit order; ``open_at_end`` the
    positions still held after ``end`` (marked, never liquidated). ``dividends_usd`` is the cash
    credited by dividends, ``costs_usd`` the sum of ``Fill.cost_usd``. ``rejections`` counts
    ``step_book`` rejections by reason, sorted by reason.

    ``contributions`` is the schedule the run was funded on, or None (the default, and every
    closed record). ``cashflows`` is ``(session, usd)`` per credited contribution in session
    order -- the dated series a money-weighted return is computed from.

    ``interest_usd`` is the idle-cash interest credited over the run (``rules.cash_yield`` only;
    0 for every other rule set, so every closed record compares equal). It is not an external
    cashflow: it is return the book earned, and it is in the snapshots' cash and equity.
    """

    allocator_id: str
    params: Any
    rules: TradeRules
    start: date
    end: date
    usd_idr: Decimal
    initial_cash: Decimal
    snapshots: tuple[BookSnapshot, ...]
    fills: tuple[Fill, ...]
    trades: tuple[Trade, ...]
    open_at_end: tuple[Position, ...]
    dividends_usd: Decimal
    costs_usd: Decimal
    rejections: tuple[tuple[str, int], ...]
    contributions: Contributions | None = None
    cashflows: tuple[tuple[date, Decimal], ...] = ()
    interest_usd: Decimal = _ZERO
```
(`_ZERO = Decimal("0.0000")` is defined at :102, above the class.)

**4c. `cash_rate_on`.** Insert after `_invested` (:240-246), before `def run_book(`:
```python
def cash_rate_on(market: Market, name: str, data_date: date) -> Decimal:
    """The annual percent idle cash earns over the night after ``data_date``.

    ``name``'s latest value on or before ``data_date`` (``MarketSeries.value_on``: point in time,
    so a Treasury holiday reuses the last published yield, as a trader would), as the exact
    Decimal of its shortest float repr (``4.057`` -> ``Decimal("4.057")``). A negative print is
    floored at 0: an idle balance is never charged for being held. ValueError when the series has
    no value yet on ``data_date``.
    """
    value = market.series.value_on(name, data_date)
    if value is None:
        raise ValueError(
            f"the {name} series has no value on or before {data_date} (it starts "
            f"{market.series.first_date(name)}); idle cash cannot be credited a rate nobody had "
            "published yet"
        )
    rate = Decimal(repr(value))
    return rate if rate > 0 else Decimal(0)
```

**4d. `run_book`.** Replace the whole function (:246-417) with:
```python
def run_book(
    market: Market,
    allocator: Allocator,
    params: Any,
    rules: TradeRules,
    start: date,
    end: date,
    *,
    prepared: Any = None,
    dividends: DividendMap = _NO_DIVIDENDS,
    initial_idr: Decimal = INITIAL_IDR,
    usd_idr: Decimal | None = None,
    kickoff: date | None = None,
    contributions: Contributions | None = None,
    contribution_fx: Callable[[date], Decimal] | None = None,
) -> BookResult:
    """Run ``allocator`` with ``params`` under the book rules ``rules`` over every session in ``[start, end]``.

    ``start`` and ``end`` are NYSE sessions, ``start <= end``. Starting cash is
    ``initial_cash_usd(initial_idr, usd_idr)``, with ``usd_idr`` defaulting to
    ``market.usd_idr_on(start)``. With ``prepared`` (``allocator.prepare(market.history)``) the
    targets come from ``targets_prepared``; without it, from ``targets`` on every history cut at
    ``data_date``. The allocator contract makes both give the same result. ``dividends`` maps
    symbol -> {ex_date: cash per share}; only the held symbols' entries for the session being
    stepped are passed on, and only when ``rules.dividends``.

    ``rules.engine`` must be ``"book"``: ``DESIGN_V0`` (``"bracket_v0"``) is a ValueError, run it
    with ``run_rules``.

    ``kickoff``: one extra rank session, off the cadence (paper trading's first decision, see
    ``paper.book.needs_kickoff``). None, the default and every backtest, ranks on the cadence only.

    ``contributions``: the owner's recurring deposit (``sim.contributions``), or None for a lump
    sum -- the default, so every closed record is unchanged. A contribution dated ``d`` is
    credited at the OPEN of the first session on or after ``d``, before ``step_book`` sizes
    anything, so a deposit that lands between rotations sits as idle cash until the next rank
    session -- which is the point: the owner's 25th is a mean of 4.2 sessions before a month-start
    rotation. It raises cash AND equity, because ``step_book`` sizes every target from
    ``book.equity``. It is converted at this run's single rate.

    ``contribution_fx``: None, the default and every recorded run -- each deposit converts at this
    run's single ``usd_idr``, so the result is about the strategy and not about the rupiah. Given a
    callable (``market.usd_idr_on`` is the real one), each deposit instead converts at the rate on
    the session it is CREDITED, so a weakening rupiah buys fewer dollars a month as it really
    would. The opening cash converts at ``usd_idr`` either way -- on the start date those are the
    same rate -- so the two runs differ in the deposits alone. Pass None to reproduce a record:
    this argument is the only thing that can make a funded re-run differ from its trial.

    ``rules.cash_yield`` (2026-10-12): None, every rule set before it, passes ``step_book`` no
    rate at all, so the call is exactly the one it always was. Set, the market must carry that
    series (``market.series``, the research store's ``market_series.csv``; a ValueError up front
    otherwise), and each session's ``step_book`` gets ``cash_rate_on(market, rules.cash_yield,
    data_date)`` -- the yield published by the PREVIOUS session -- and the deposit credited at
    this open as ``deposited``, which was not in the account overnight and earns nothing for it.
    The interest credited is summed into ``BookResult.interest_usd``.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    if not isinstance(rules, TradeRules):
        raise TypeError(f"rules must be TradeRules, got {type(rules).__name__}")
    if rules.engine != "book":
        raise ValueError(f"rules {rules.id!r} use the {rules.engine} engine; run them with run_rules")
    if not isinstance(allocator, Allocator):
        raise TypeError(f"allocator must be an Allocator, got {type(allocator).__name__}")
    if not isinstance(dividends, Mapping):
        raise TypeError(f"dividends must be a Mapping, got {type(dividends).__name__}")
    if contributions is not None and (
        isinstance(contributions, (str, Mapping))
        or not isinstance(contributions, (ContributionSchedule, Sequence))
    ):
        raise TypeError(
            "contributions must be a ContributionSchedule, a sequence of (date, Decimal) "
            f"pairs or None, got {type(contributions).__name__}"
        )
    if contribution_fx is not None and not callable(contribution_fx):
        raise TypeError(
            f"contribution_fx must be callable or None, got {type(contribution_fx).__name__}"
        )
    if contribution_fx is not None and contributions is None:
        raise ValueError("contribution_fx converts deposits; it needs contributions, not None")
    if rules.cash_yield is not None and rules.cash_yield not in market.series.names():
        raise ValueError(
            f"rules {rules.id!r} credit idle cash at the {rules.cash_yield} yield, and this market "
            f"carries no {rules.cash_yield} series (the research store's market_series.csv); write "
            "it with `python -m seer_engine market_series --refresh --store <store>`"
        )
    _session("start", start)
    _session("end", end)
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    rate = market.usd_idr_on(start) if usd_idr is None else usd_idr
    cash0 = initial_cash_usd(initial_idr, rate)

    book = new_book(cash0)
    data_date = dates.prev_session(start)
    last_rank: tuple[Target, ...] | None = None  # the last rank session's targets, pre-idle; None = none yet
    snapshots: list[BookSnapshot] = [
        BookSnapshot(date=data_date, cash_usd=book.cash, equity_usd=book.equity, invested_usd=_ZERO)
    ]
    fills: list[Fill] = []
    trades: list[Trade] = []
    rejections: Counter[str] = Counter()
    dividends_usd = _ZERO
    costs_usd = _ZERO
    interest_usd = _ZERO
    cashflows: list[tuple[date, Decimal]] = []

    for session in dates.sessions(start, end):
        deposited = _ZERO
        if contributions is not None:
            credit_rate = rate if contribution_fx is None else contribution_fx(session)
            credit = credit_for(contributions, data_date, session, credit_rate)
            if credit > 0:
                book = replace(book, cash=book.cash + credit, equity=book.equity + credit)
                cashflows.append((session, credit))
                deposited = credit
        held = book.held()
        targets: tuple[Target, ...] | None = None
        idle_added = False
        rank = is_rank_session(rules, session) or session == kickoff
        # A resize session before the first rank has no basket to re-scale: it is not a decision.
        if rank or (last_rank is not None and is_resize_session(rules, session)):
            members = market.membership.members_on(data_date)
            # The idle position is the runner's residual, never a family's (plan index D-J).
            mine = held - {rules.idle_symbol} if rules.idle_symbol is not None else held
            if prepared is None:
                history = {s: h.upto(data_date) for s, h in market.history.items()}
                wanted = allocator.targets(history, members, data_date, mine, params)
            else:
                wanted = allocator.targets_prepared(prepared, members, data_date, mine, params)
            if rank:
                last_rank = tuple(wanted)
                basket = last_rank
            else:
                marks = {p.symbol: p.mark for p in book.positions}
                basket = _rescaled(market, last_rank, tuple(wanted), mine, data_date, marks)
            targets, idle_added = _with_idle(market, rules, basket, data_date)

        symbols = set(held)
        if targets is not None:
            symbols.update(t.symbol for t in targets)
        bars = market.bars_on(session, sorted(symbols))
        divs = _dividends_on(dividends, held, session) if rules.dividends else {}

        if rules.cash_yield is None:
            stepped = step_book(book, session, bars, targets, rules, divs, idle_symbol_ok=idle_added)
        else:
            stepped = step_book(
                book,
                session,
                bars,
                targets,
                rules,
                divs,
                idle_symbol_ok=idle_added,
                cash_rate=cash_rate_on(market, rules.cash_yield, data_date),
                deposited=deposited,
            )
            interest_usd += stepped.interest
        book = stepped.book
        fills.extend(stepped.fills)
        trades.extend(stepped.trades)
        for _, amount in stepped.dividends:
            dividends_usd += amount
        for _, reason in stepped.rejected:
            rejections[reason] += 1
        snapshot = stepped.snapshot

        gone = [p.symbol for p in book.positions if _gone(market, p.symbol, session)]
        if gone:
            book, forced_fills, forced_trades = close_book_unpriced(book, gone, rules)
            fills.extend(forced_fills)
            trades.extend(forced_trades)
            snapshot = BookSnapshot(
                date=session,
                cash_usd=book.cash,
                equity_usd=book.equity,
                invested_usd=_invested(book, rules),
            )
        snapshots.append(snapshot)
        data_date = session

    for f in fills:
        costs_usd += f.cost_usd

    return BookResult(
        allocator_id=allocator.id,
        params=params,
        rules=rules,
        start=start,
        end=end,
        usd_idr=rate,
        initial_cash=cash0,
        snapshots=tuple(snapshots),
        fills=tuple(fills),
        trades=tuple(trades),
        open_at_end=book.positions,
        dividends_usd=dividends_usd,
        costs_usd=costs_usd,
        rejections=tuple(sorted(rejections.items())),
        contributions=contributions,
        cashflows=tuple(cashflows),
        interest_usd=interest_usd,
    )
```
**Impact:** the only differences for `cash_yield=None` are the up-front check (skipped), a local
`deposited` that is never passed on, and `interest_usd` staying `Decimal("0.0000")`. The call to
`step_book` is byte-identical to today's, so the `steps` spy in `tests/test_book_runner.py` keeps
working. `run_rules` already forwards everything to `run_book`, so it needs no change. `run_stats` is
unchanged: interest shows up in equity, Sharpe and the money-weighted return, and is not a closed
trade, so the profit factor counts trades only, as it does for idle cash today.

### Step 5: `backtest/dev.py` docstring
**File:** `engine/src/seer_engine/backtest/dev.py:268-269`
**Change:** in `candidate_window`'s docstring replace
```
    strategies read SPY and members with ``strategy.lookback``. The idle instrument is not part
    of the rule (idle cash earns nothing until it has a bar).
```
with
```
    strategies read SPY and members with ``strategy.lookback``. The idle instrument is not part
    of the rule (idle cash earns nothing until it has a bar). Neither is ``rules.cash_yield``:
    under that lever idle cash is credited the named T-bill yield from ``Market.series`` by
    ``book_runner.run_book``, which refuses a market without the series, and ``lab run`` refuses
    such a store before anything is spent (``lab.runner.preflight_data``).
```
**Impact:** docstring only.

### Step 6: Paper refuses cash-yield rules
**File:** `engine/src/seer_engine/paper/book.py`
**Change:** add a helper after `_book_rules` (:113-118) and call it in `decide_book` (after
`_book_rules(rules)` at :250) and in `settle_book` (after `_book_rules(rules)` at :394). Do NOT
put it inside `_book_rules`: `needs_kickoff` and `last_rank_session` also call `_book_rules`, and
`tests/test_paper_kickoff.py` loops them over every preset, including the cash presets Phase 3
adds. Those two functions are pure calendar logic and stay valid for any rule set.
**Code:**
```python
def _lab_only(rules: TradeRules) -> None:
    """Refuse a rule set paper trading cannot run yet: one that credits idle cash interest.

    ``rules.cash_yield`` needs the T-bill yield every night, and the paper night has no feed of
    it. Nobody has verified that Gotrade pays interest on idle dollars either (``cash-yield`` is
    an owner input), so such a rule set is a lab measurement, not something to paper-trade.
    """
    if rules.cash_yield is not None:
        raise ValueError(
            f"rules {rules.id!r} pay interest on idle cash; paper trading cannot run them yet "
            "(there is no nightly feed of that rate, and nobody has checked that Gotrade pays it), "
            "so they are for the lab only"
        )
```
In `decide_book`:
```python
    _book_rules(rules)
    _lab_only(rules)
    _session("data_date", data_date)
```
In `settle_book`:
```python
    _book_rules(rules)
    _lab_only(rules)
```
(Keep every line after these as it is.)
**Impact:** no roster entry carries `cash_yield` (invariant 3), so the live paper night is unchanged.

### Step 7: Promote refuses cash-yield rules
**File:** `engine/src/seer_engine/commands/promote.py:154-169`
**Change:** replace `_check_rules` with:
```python
def _check_rules(rules: TradeRules) -> None:
    """NotPromotable when ``rules`` cannot be a roster entry's rules.

    Two reasons. ``rules.cash_yield`` credits idle cash a T-bill yield, which the paper night has
    no feed of (``paper.book`` refuses such rules), so the strategy could never trade a night.
    Otherwise ``rules`` must be the ``sim.rules`` preset of its own id: ``roster.from_row``
    rebuilds a roster entry's rules with ``roster.rules_for(row.rules_id)``, which answers out of
    ``PRESETS``. A candidate carrying a one-off ``TradeRules`` would be frozen under its own rules
    and read back under the preset's, and the difference would surface as a
    ``store.SpecMismatch`` on the strategy's first paper night rather than here.
    """
    if rules.cash_yield is not None:
        raise NotPromotable(
            f"this variant's rules ({rules.id!r}) pay interest on idle cash, which paper trading "
            f"cannot do yet: there is no nightly feed of the {rules.cash_yield} rate and nobody has "
            f"checked that Gotrade pays it. Promote its twin without the interest instead"
        )
    preset = roster.rules_for(rules.id)  # raises roster.UnknownRules for an unknown id
    if preset != rules:
        raise NotPromotable(
            f"this variant's rules are id {rules.id!r} but are not the sim.rules preset of that "
            f"id; a roster row carries only the id, so the spec would be frozen under one rule "
            f"set and read back under another. Promote a variant that uses a preset, or add this "
            f"rule set to sim.rules.PRESETS first"
        )
```
**Impact:** `promote` of a cash-yield variant exits 2 (NotPromotable is a PromoteError) before any database is opened.

### Step 8: Lab refuses a store without the series
**File:** `engine/src/seer_engine/lab/runner.py`

**8a. Helper.** Insert after `market_aware_candidates` (:319-333), before `def preflight_data(`:
```python
def missing_cash_yield(candidates: Sequence[Candidate], market: Market) -> tuple[str, ...]:
    """The ids of ``candidates`` whose ``rules.cash_yield`` names a series ``market`` lacks, in order.

    Such a candidate credits idle cash from ``Market.series`` (``book_runner.run_book``), so on a
    store without that series it cannot run at all; the lab refuses it before spending anything.
    """
    have = set(market.series.names())
    return tuple(
        c.id for c in candidates if c.rules.cash_yield is not None and c.rules.cash_yield not in have
    )
```
Imports: `Sequence` (:64) and `Candidate` (:73) are already imported. `Market` is not, so add
`from seer_engine.backtest.market import Market` after line :75
(`from seer_engine.backtest.runner import INITIAL_IDR`). The module has
`from __future__ import annotations`, so placing it inside the module's existing
`if TYPE_CHECKING:` block instead is equally fine.

**8b. `preflight_data`.** Add one sentence to the docstring, after "...are refused outright.":
`A candidate whose rules credit idle cash at a T-bill yield (``rules.cash_yield``) on a store
without that series is refused outright too.` Then, directly before
`    aware = market_aware_candidates(method)` (:374), insert:
```python
    no_rate = missing_cash_yield(method.all_candidates(), data.market)
    if no_rate:
        raise store.LabError(
            f"{method.id}: {', '.join(no_rate)} credit idle cash at a Treasury bill yield, and this "
            f"store carries no such series ({research.MARKET_SERIES_FILE}); running it would crash "
            "partway, measuring nothing. Nothing has been spent. Write the series with "
            "`python -m seer_engine market_series --refresh --store <store>`"
        )
```

**8c. `run_test`.** Directly before `    pre = preflight_test(conn, method, path, candidate, require_commit=require_commit)`
(:1037), insert:
```python
    if missing_cash_yield((candidate,), data.market):
        raise store.LabError(
            f"{candidate.id} credits idle cash at the {candidate.rules.cash_yield} yield and this "
            f"test store carries no such series ({research.MARKET_SERIES_FILE}); the look would "
            f"crash, not measure. Nothing has been spent"
        )
```
**Impact:** existing methods have no `cash_yield`, so `no_rate` is empty and both paths are
unchanged. `lab survivorship` reruns on the sv store, which already carries
`market_series.csv` (checked: `/home/miftah/seer/engine/.research-sv/market_series.csv`).

### Step 9: New test module
**File:** `engine/tests/test_cash_yield.py` (create)
**Code:**
```python
"""Interest on idle cash (measure-then-learn phase 2, R2): the ``cash_yield`` lever.

``TradeRules.cash_yield`` names a market series (only ``T13W``, the 13-week T-bill yield, percent)
whose rate idle cash earns: ``q(cash x rate x calendar days / 36500)`` at each open, on the cash
held at the previous close, before dividends, the rate as published by the previous session.
Every rule set without it must run exactly as before -- the preset pins below were taken on the
tree before the lever existed. No database needed.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from decimal import Decimal

import pytest
from allocatorkit import FIXED, FixedParams
from simkit import D, P, bar
from stratkit import hist
from test_book_runner import FIXTURE_IDR, W_END, W_START, Scripted, wiring_market

from seer_engine import dates, research, sim
from seer_engine.backtest import registry
from seer_engine.backtest.book_runner import BookResult, cash_rate_on, run_book, run_rules
from seer_engine.backtest.market import Market, MarketSeries, Membership
from seer_engine.commands import promote
from seer_engine.paper import roster
from seer_engine.paper.book import decide_book, settle_book
from seer_engine.sim.book import Book, BookStep, Position, accrued_interest, new_book, step_book
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine.sim.rules import (
    CASH_YIELD_SERIES,
    DAILY_SWITCH,
    DESIGN_V0,
    DESIGN_V0_GOTRADE,
    LEVERS_SINCE_PINS,
    MONTHLY_HOLD,
    MONTHLY_HOLD_FRAC_GOTRADE,
    PRESETS,
    V0_BOOK,
    TradeRules,
    describe_rules,
    is_pinned_default,
    rule_owner_inputs,
)

CASH = replace(DAILY_SWITCH, id="daily-switch-cash", cash_yield="T13W")
SERIES = MarketSeries({"T13W": [(D("2025-02-13"), 4.0), (D("2025-02-28"), 5.0)]})


# ============================================================== the lever


def test_cash_yield_defaults_to_none_and_is_a_pinned_no_op():
    assert TradeRules(id="x", engine="book").cash_yield is None
    # Every preset that predates the lever (the first 16). Phase 3 appends cash-yield presets after
    # them; asserting over all of PRESETS would turn red the moment it does.
    assert len(PRESETS) >= 16
    assert all(r.cash_yield is None for r in PRESETS[:16])
    assert DESIGN_V0.cash_yield is None and V0_BOOK.cash_yield is None
    assert LEVERS_SINCE_PINS["cash_yield"] is None
    assert list(LEVERS_SINCE_PINS)[-1] == "cash_yield"
    assert is_pinned_default("cash_yield", None) is True
    assert is_pinned_default("cash_yield", "T13W") is False


def test_cash_yield_series_are_series_the_research_store_holds():
    assert CASH_YIELD_SERIES == ("T13W",)
    assert set(CASH_YIELD_SERIES) <= set(research.MARKET_SERIES_NAMES)
    assert sim.CASH_YIELD_SERIES is CASH_YIELD_SERIES and "CASH_YIELD_SERIES" in sim.__all__


def test_cash_yield_validation():
    with pytest.raises(ValueError, match="unknown cash_yield"):
        replace(DAILY_SWITCH, id="x", cash_yield="T10Y")
    with pytest.raises(TypeError, match="cash_yield"):
        replace(DAILY_SWITCH, id="x", cash_yield=4)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="book-engine"):
        replace(DESIGN_V0_GOTRADE, id="x", cash_yield="T13W")
    with pytest.raises(ValueError, match="book-engine"):
        replace(DESIGN_V0, cash_yield="T13W")
    with pytest.raises(ValueError, match="idle_symbol"):
        replace(DAILY_SWITCH, id="x", idle_symbol="BIL", cash_yield="T13W")
    assert CASH.cash_yield == "T13W"


def test_canonical_text_leaves_the_lever_out_at_none_and_names_it_when_set():
    assert "cash_yield" not in registry._canon(DAILY_SWITCH)
    assert "cash_yield='T13W'" in registry._canon(CASH)
    assert "cash_yield" not in roster.rules_dict(DAILY_SWITCH)
    assert roster.rules_dict(CASH)["cash_yield"] == "T13W"


def test_cash_yield_is_an_owner_input():
    assert rule_owner_inputs(CASH) == ("cash-yield",)
    assert rule_owner_inputs(replace(CASH, entry="open")) == ("cash-yield", "market-on-open")
    assert rule_owner_inputs(DAILY_SWITCH) == ()


def test_describe_rules_idle_cash_line():
    base = replace(MONTHLY_HOLD_FRAC_GOTRADE, id="cash-test")
    lines = describe_rules(replace(base, cash_yield="T13W"))
    plain = describe_rules(base)
    assert len(lines) == 12
    assert plain[10] == "Idle cash: held as cash, earning nothing."
    assert lines[10] == (
        "Idle cash: held as cash and credited the 13-week US Treasury bill yield, read at the "
        "previous session's close, for the calendar days since the last session, at each open "
        "(needs owner verification: cash-yield)."
    )
    assert lines[:10] == plain[:10] and lines[11:] == plain[11:]


# ============================================================== the accrual


def test_accrued_interest_is_simple_act_365():
    assert accrued_interest(P("1000"), Decimal("5"), 1) == P("0.1370")  # 1000 x 5 / 36500 = 0.136986
    assert accrued_interest(P("1000"), Decimal("5"), 3) == P("0.4110")  # a weekend: 0.410959
    assert accrued_interest(P("1000"), Decimal("4.057"), 1) == P("0.1112")  # 0.111150
    assert accrued_interest(P("0"), Decimal("5"), 3) == 0
    assert accrued_interest(P("-10"), Decimal("5"), 3) == 0
    assert accrued_interest(P("1000"), Decimal("0"), 3) == 0
    with pytest.raises(ValueError, match=">= 0"):
        accrued_interest(P("1000"), Decimal("-0.1"), 1)
    with pytest.raises(TypeError):
        accrued_interest(P("1000"), 5.0, 1)  # type: ignore[arg-type]


def _cash_book(cash: str, last: str) -> Book:
    return Book(cash=P(cash), equity=P(cash), positions=(), last_session=D(last))


def test_step_book_credits_interest_on_overnight_cash_at_the_open():
    # Fri 2026-10-09 -> Mon 2026-10-12: three calendar days at 5%.
    got = step_book(_cash_book("1000", "2026-10-09"), D("2026-10-12"), {}, None, CASH, cash_rate=Decimal("5"))
    assert got.interest == P("0.4110")
    assert got.book.cash == P("1000.4110") and got.snapshot.cash_usd == P("1000.4110")
    assert got.snapshot.equity_usd == P("1000.4110")


def test_a_deposit_credited_at_this_open_earns_nothing_for_the_gap():
    b = _cash_book("1312.5", "2026-10-09")  # 1000 overnight + 312.5 deposited at Monday's open
    got = step_book(b, D("2026-10-12"), {}, None, CASH, cash_rate=Decimal("5"), deposited=P("312.5"))
    assert got.interest == P("0.4110")
    assert got.book.cash == P("1312.9110")


def test_a_book_never_stepped_earns_nothing():
    got = step_book(new_book(P("1000")), D("2026-10-12"), {}, None, CASH, cash_rate=Decimal("5"))
    assert got.interest == 0 and got.book.cash == P("1000")


def test_interest_is_on_cash_only_and_dividends_do_not_earn_it():
    p = Position("AAA", Decimal(10), P("50"), D("2026-10-01"), P("50"), 3, P("500.5"), P("0"), None, None)
    b = Book(cash=P("1000"), equity=P("1500"), positions=(p,), last_session=D("2026-10-09"))
    bars = {"AAA": bar("AAA", "2026-10-12", 50, 51, 49, 50)}
    got = step_book(b, D("2026-10-12"), bars, None, CASH, {"AAA": Decimal("1")}, cash_rate=Decimal("5"))
    assert got.interest == P("0.4110")  # on the 1000 of cash, not on the 500 of stock or the dividend
    assert got.dividends == (("AAA", P("10")),)
    assert got.book.cash == P("1010.4110")


def test_rules_and_rate_must_agree():
    b = _cash_book("1000", "2026-10-09")
    with pytest.raises(ValueError, match="pass that yield"):
        step_book(b, D("2026-10-12"), {}, None, CASH)
    with pytest.raises(ValueError, match="cash_rate must be None"):
        step_book(b, D("2026-10-12"), {}, None, DAILY_SWITCH, cash_rate=Decimal("5"))
    with pytest.raises(ValueError, match="needs a cash_rate"):
        step_book(b, D("2026-10-12"), {}, None, DAILY_SWITCH, deposited=P("1"))
    with pytest.raises(ValueError, match=">= 0"):
        step_book(b, D("2026-10-12"), {}, None, CASH, cash_rate=Decimal("-1"))
    with pytest.raises(ValueError, match="deposited must be in"):
        step_book(b, D("2026-10-12"), {}, None, CASH, cash_rate=Decimal("5"), deposited=P("1000.0001"))
    with pytest.raises(TypeError):
        step_book(b, D("2026-10-12"), {}, None, CASH, cash_rate=5.0)  # type: ignore[arg-type]


def test_without_the_lever_a_step_credits_nothing():
    got = step_book(_cash_book("1000", "2026-10-09"), D("2026-10-12"), {}, None, DAILY_SWITCH)
    assert isinstance(got, BookStep) and got.interest == 0
    assert got.book.cash == P("1000")


# ============================================================== the runner


def _cash_market() -> Market:
    return wiring_market().with_series(SERIES)


def test_cash_rate_on_reads_the_series_point_in_time():
    m = _cash_market()
    assert cash_rate_on(m, "T13W", D("2025-02-27")) == Decimal("4.0")
    assert cash_rate_on(m, "T13W", D("2025-02-28")) == Decimal("5.0")
    assert cash_rate_on(m, "T13W", D("2025-03-03")) == Decimal("5.0")  # latest on or before
    with pytest.raises(ValueError, match="no value on or before"):
        cash_rate_on(m, "T13W", D("2025-02-12"))
    negative = wiring_market().with_series(MarketSeries({"T13W": [(D("2025-02-13"), -0.02)]}))
    assert cash_rate_on(negative, "T13W", D("2025-02-20")) == 0


def test_run_book_credits_idle_cash_from_the_previous_sessions_yield():
    """Nothing is targeted, so the book is pure cash. 2025-02-24 is the first session (no night
    before it in the book: no interest). 02-25: q(1250 x 4 / 36500) = 0.1370, then the 312.50
    deposit lands at that open and earns nothing for the gap. 02-26: q(1562.6370 x 4 / 36500) =
    0.1712. From 03-03 (data_date 02-28) the rate is 5%, and 02-28 -> 03-03 is three days."""
    r = run_book(
        _cash_market(), Scripted(), None, CASH, W_START, W_END,
        initial_idr=FIXTURE_IDR, contributions=OWNER_MONTHLY,
    )
    by_date = {s.date: s for s in r.snapshots}
    assert by_date[D("2025-02-24")].cash_usd == P("1250")
    assert by_date[D("2025-02-25")].cash_usd == P("1562.6370")
    assert by_date[D("2025-02-26")].cash_usd == P("1562.8082")
    expected = P("1250")
    prev = None
    total = Decimal(0)
    for s in dates.sessions(W_START, W_END):
        if prev is not None:
            rate = Decimal(5) if prev >= D("2025-02-28") else Decimal(4)
            gain = accrued_interest(expected, rate, (s - prev).days)
            expected += gain
            total += gain
        if s == D("2025-02-25"):
            expected += P("312.5")
        assert by_date[s].cash_usd == expected == by_date[s].equity_usd, s
        prev = s
    assert r.interest_usd == total > 0
    assert r.cashflows == ((D("2025-02-25"), P("312.5")),)  # interest is not a cashflow
    assert run_rules(
        _cash_market(), Scripted(), None, CASH, W_START, W_END,
        initial_idr=FIXTURE_IDR, contributions=OWNER_MONTHLY,
    ) == r


def test_run_book_refuses_a_market_without_the_series():
    with pytest.raises(ValueError, match="carries no T13W series"):
        run_book(wiring_market(), Scripted(), None, CASH, W_START, W_END, initial_idr=FIXTURE_IDR)


def test_a_rule_set_without_the_lever_ignores_the_series():
    plain = run_book(wiring_market(), Scripted(), None, DAILY_SWITCH, W_START, W_END, initial_idr=FIXTURE_IDR)
    seen = run_book(_cash_market(), Scripted(), None, DAILY_SWITCH, W_START, W_END, initial_idr=FIXTURE_IDR)
    assert plain == seen
    assert plain.interest_usd == 0
    assert BookResult.__dataclass_fields__["interest_usd"].default == 0


# ============================================================== every existing preset, unchanged

PIN_DAYS = dates.sessions(D("2024-12-02"), D("2025-05-30"))
PIN_START, PIN_END = D("2025-01-15"), D("2025-05-30")
PIN_PARAMS = FixedParams((("AAA", Decimal("0.45")), ("BBB", Decimal("0.35"))))
PIN_DIVIDENDS = {
    "AAA": {D("2025-02-20"): Decimal("0.10"), D("2025-05-15"): Decimal("0.12")},
    "BBB": {D("2025-03-03"): Decimal("0.20")},
}

# sha256 of each run's (snapshots, fills, trades, open_at_end, dividends, costs, rejections,
# cashflows) repr, taken on 5faa3cb, before the lever existed. A mismatch means an existing rule
# set's results moved: invariant 2 broken. Never re-pin to make this pass.
PRESET_RUN_PINS: dict[str, str] = {
    "v0-book": "7a3eeb8ae05944df3d78306114aac53201367f2a9c8054ffd1b94b6dd6d5a897",
    "monthly-hold": "008e8c6aeaf46ae553b79c377fe9b58972b380429a63d5895ad82c5bce75d6f0",
    "monthly-hold-tbill": "7ab3042f57019626dc02b24f92c58371fc07ec847b2b9a9fa8b7c6d44399a830",
    "weekly-hold": "60b1231fd8667e7a7efa594e1ed242d1bd93bd8fdc30265b960ab94aa705a50c",
    "daily-switch": "ef06b49ff7dc58939df6b101b295455dfd9003144d1d27231c16ca396420b708",
    "daily-switch-tbill": "b85aa67de685edbcfeafa7a5a7022ce7112fd19ee1fd9eb82a40a7cb8cf173ed",
    "swing-t10": "618019963efa2addb9742ab72d51020a1008d96f51641c05307780a654caefcb",
    "swing-t20": "bbc4f51f296b26bf368458e18e5f94b791a8d37fdad0022b0eaa87d1feea12fe",
    "swing-t20-open": "bbc4f51f296b26bf368458e18e5f94b791a8d37fdad0022b0eaa87d1feea12fe",
    "monthly-rank-weekly-resize": "8724812a6257a282a4339420802fd50be41d61beea0ea40a982b70e3dd5d391b",
    "monthly-rank-weekly-resize-tbill": "7ee7b496e7e4919efd28835fa26aa843bf87035d4f0a12141fbc1453b95d4475",
    "monthly-hold-frac": "7d345b779e67b46e78ef9799b67c35912d19e7a0d521046031e95c7f6ccffca8",
    "monthly-rank-weekly-resize-frac": "abc3dad0631fa93c79ee5c22f09b234f58eb32f256b96d4246cc537195204c10",
    "monthly-hold-frac-gotrade": "a9ea0460115f6aaf0c94ac8587331b541f08cecced150f4b8a12059fc411abed",
    "monthly-rank-weekly-resize-frac-gotrade": "b5a7ea5dd15653acd7db73237c8a2df22610bd1a267752ce2112f84b77ef4c2f",
}


def pin_market() -> Market:
    n = len(PIN_DAYS)
    aaa = hist("AAA", [round(10.0 + 0.05 * t + (1.5 if (t // 7) % 2 else 0.0), 2) for t in range(n)], days=PIN_DAYS)
    bbb = hist("BBB", [round(40.0 - 0.04 * t + (2.0 if (t // 11) % 2 else 0.0), 2) for t in range(n)], days=PIN_DAYS)
    bil = hist("BIL", [100.0] * n, days=PIN_DAYS, spread=0.05)
    return Market(
        history={"AAA": aaa, "BBB": bbb, "BIL": bil},
        membership=Membership((("AAA", D("2020-01-02"), None), ("BBB", D("2020-01-02"), None))),
        fx=((D("2024-11-29"), Decimal("16000")),),
    )


def run_digest(r: BookResult) -> str:
    text = repr((r.snapshots, r.fills, r.trades, r.open_at_end, r.dividends_usd, r.costs_usd, r.rejections, r.cashflows))
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.mark.parametrize("rules_id", sorted(PRESET_RUN_PINS))
@pytest.mark.parametrize("with_series", [False, True], ids=["no-series", "series"])
def test_every_existing_book_preset_runs_exactly_as_before(rules_id, with_series):
    by_id = {r.id: r for r in (V0_BOOK, *PRESETS)}
    market = pin_market().with_series(SERIES) if with_series else pin_market()
    r = run_book(
        market, FIXED, PIN_PARAMS, by_id[rules_id], PIN_START, PIN_END,
        dividends=PIN_DIVIDENDS, contributions=OWNER_MONTHLY,
    )
    assert run_digest(r) == PRESET_RUN_PINS[rules_id]
    assert r.interest_usd == 0


def test_the_pins_cover_every_book_preset_that_predates_the_lever():
    # Presets added after this phase (phase 3's fixed-tape presets) are not pinned here; every
    # one that existed before the lever is.
    before = {"v0-book"} | {r.id for r in PRESETS if r.engine == "book"} - {
        r.id for r in PRESETS if r.cash_yield is not None or getattr(r, "resize_basis", "equity") != "equity"
    }
    assert before == set(PRESET_RUN_PINS)


# ============================================================== paper and promote refuse it


def test_paper_refuses_cash_yield_rules():
    with pytest.raises(ValueError, match="lab only"):
        decide_book(_cash_market(), Scripted(), None, CASH, D("2025-02-24"), frozenset())
    with pytest.raises(ValueError, match="lab only"):
        settle_book(
            _cash_book("1000", "2025-02-24"), D("2025-02-25"), {}, None, False, CASH, {}, (), lambda s: None
        )


def test_promote_refuses_cash_yield_rules():
    with pytest.raises(promote.NotPromotable, match="interest on idle cash"):
        promote._check_rules(CASH)
    promote._check_rules(MONTHLY_HOLD)  # an ordinary preset still passes
```
**Impact:** new tests only. About `test_the_pins_cover_every_book_preset_that_predates_the_lever`:
Phase 3 adds presets that use `resize_basis="target"` and/or `cash_yield`, and the set expression
leaves those out, so Phase 3 does not break this test. If Phase 3 ever adds a preset with neither
lever set, this test fails on purpose: that preset must then be pinned here too, and that is
Phase 3's call.

### Step 10: Update the existing golden tests
**File:** `engine/tests/test_sim_rules.py:416`
**Change:** the equality (as Phase 1 leaves it) gains `cash_yield`:
```python
    assert LEVERS_SINCE_PINS == {
        "resize_cadence": None,
        "cost_model": "flat",
        "resize_basis": "equity",
        "cash_yield": None,
    }
```
(Keep Phase 1's `resize_basis` value as Phase 1 wrote it.)

**File:** `engine/tests/test_backtest_dev_report.py:567-571`
**Change:** the `TradeRules(...)` literal (which Phase 1 extended with `resize_basis='equity'`) gains
`cash_yield=None` as its last field:
```python
    assert (
        "TradeRules(id='monthly-hold', engine='book', cadence='monthly', resize_cadence=None, "
        "entry='open_limit', max_positions=None, "
        "time_stop=None, resize=True, fractional=False, dividends=True, idle_symbol=None, cost_rate=Decimal('0.001'), "
        "cost_model='flat', resize_basis='equity', cash_yield=None)"
    ) in text
```
**Impact:** test text only. The rendered pre-registration is generated fresh in the test; no
committed report file is touched (closed records stay frozen).

**File:** `engine/tests/test_lab_runner.py`, append after
`test_a_dividend_calendar_method_is_refused_without_a_calendar` (:451-453):
```python
# ---- a cash-yield candidate needs the yield series ---------------------------------------------


def test_a_cash_yield_method_is_refused_on_a_store_without_the_series(data):
    from seer_engine.backtest.market import MarketSeries

    cash = dataclasses.replace(MONTHLY_HOLD, id="monthly-hold-cash-test", cash_yield="T13W")
    m = _method("M0015", cands=(_cand("M0015-A", "M0015", rules=cash), _cand("M0015-B", "M0015")))
    assert "T13W" not in data.market.series.names()
    assert runner.missing_cash_yield(m.all_candidates(), data.market) == ("M0015-A",)
    with pytest.raises(store.LabError, match="M0015-A credit idle cash"):
        runner.preflight_data(data, m)
    series = MarketSeries({"T13W": [(date(1993, 1, 29), 2.9)]})
    with_series = dataclasses.replace(data, market=data.market.with_series(series))
    assert runner.missing_cash_yield(m.all_candidates(), with_series.market) == ()
    assert runner.preflight_data(with_series, m) is None


def test_a_method_without_the_lever_never_needs_the_series(data):
    assert runner.missing_cash_yield(_method().all_candidates(), data.market) == ()
```
**Impact:** test-only.

### Step 11: The lab smoke market can run a cash-yield candidate
**Why here (reconciled):** `run_book` now refuses a market without the named series, and
`tests/labkit.smoke_market` carries `EMPTY_SERIES`. Without this step the first lab method on a
`-cash` preset (phase 5) would fail `test_lab_methods.test_candidate_runs_a_smoke_window` for every
cash variant. The fixture fix lands with the lever that needs it. It is **opt-in**: the smoke
markets themselves keep `EMPTY_SERIES`, because
`test_market_series.py::test_a_market_carries_the_shared_empty_series_unless_given_one` pins that,
and this phase's own `test_a_cash_yield_method_is_refused_on_a_store_without_the_series` (Step 10)
asserts that the `data` fixture (built on `labkit.smoke_data`) has no `T13W`.

**File:** `engine/tests/labkit.py`
**Change:** the import line `from seer_engine.backtest.market import Market, Membership` becomes
```python
from seer_engine.backtest.market import Market, MarketSeries, Membership
```
and, directly after `SPY_EX_DATE = date(2015, 6, 19)`, add:
```python
SMOKE_T13W = MarketSeries({"T13W": [(date(1993, 1, 29), 4.0)]})
"""A flat 4% 13-week T-bill, dated before both smoke windows, so ``value_on`` answers 4.0 on any
dev or test session. Opt-in: a candidate whose rules credit idle cash (``rules.cash_yield``) runs
on ``smoke_market(...).with_series(SMOKE_T13W)``; the smoke markets themselves keep
``EMPTY_SERIES``."""
```

**File:** `engine/tests/test_lab_methods.py:25` (the labkit import) and `:78-83`
(`test_candidate_runs_a_smoke_window`)
**Change:** the labkit import gains `SMOKE_T13W`:
```python
from labkit import MEMBER_STOCKS, SMOKE_T13W, SPY_EX_DATE, smoke_market
```
and the test becomes:
```python
@pytest.mark.parametrize("mid,c", CANDIDATES, ids=[c.id for _, c in CANDIDATES])
def test_candidate_runs_a_smoke_window(market, mid, c):
    amount = Decimal("1.0300")
    # A rule set that credits idle cash reads the T-bill series; run_book refuses a market without it.
    m = market.with_series(SMOKE_T13W) if c.rules.cash_yield is not None else market
    result, row = run_candidate(m, {"SPY": {SPY_EX_DATE: amount}}, (Dividend(SPY_EX_DATE, amount),), c)
    assert row.end == DEV_END
    assert len(result.snapshots) >= 2
```
(Every candidate's `rules` is a `TradeRules`, which has `cash_yield` after Step 1. No existing
candidate sets it, so every existing parametrised case runs exactly as before.)

**File:** `engine/tests/test_cash_yield.py`. Append at the end:
```python
# ============================================================== the lab smoke market


def test_a_cash_yield_rule_set_runs_on_the_lab_smoke_market_given_its_series():
    from labkit import SMOKE_T13W, smoke_market

    from seer_engine.backtest.dev import DEV_END

    cash = replace(MONTHLY_HOLD_FRAC_GOTRADE, id="monthly-hold-frac-gotrade-cash-test", cash_yield="T13W")
    params = FixedParams((("AAA", Decimal("0.45")), ("BBB", Decimal("0.35"))))
    start = D("2015-01-02")
    with pytest.raises(ValueError, match="carries no T13W series"):
        run_book(smoke_market(), FIXED, params, cash, start, DEV_END)
    r = run_book(smoke_market().with_series(SMOKE_T13W), FIXED, params, cash, start, DEV_END)
    assert r.interest_usd > 0  # a fifth of the book waits in cash at 4% a year
    assert smoke_market().series.names() == ()  # opt-in: the shared fixture is unchanged
```
**Impact:** test fixture and tests only. Phase 5's cash variants pass the lab smoke test with no
fixture change of their own.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/measure-then-learn && engine/.venv/bin/ruff check engine`
**Tests:**
```bash
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
engine/.venv/bin/pytest engine/tests/test_cash_yield.py engine/tests/test_sim_rules.py \
  engine/tests/test_sim_book.py engine/tests/test_book_runner.py engine/tests/test_paper_book.py \
  engine/tests/test_lab_runner.py engine/tests/test_promote_command.py engine/tests/test_backtest_dev_report.py \
  engine/tests/test_lab_methods.py engine/tests/test_market_series.py -n0
engine/.venv/bin/pytest engine/tests            # full suite; DB tests must not skip
```
**Manual check:** from the worktree, against the dev store, run one existing book preset and one
cash-yield variant of it over the dev window, and compare `interest_usd` and final equity. Use a
scratch script that calls `research.load_store(<dev store>)` and `run_book(...)`. It must not run
`lab run`, and it writes nothing. The plain run's final equity must equal its recorded dev trial,
and the cash run's must be higher by roughly the interest.
**Exit criteria:**
- `test_every_recorded_configuration_still_digests_to_its_recorded_digest`, the paper `PINS`, the
  registry pins and `test_every_existing_book_preset_runs_exactly_as_before` pass with no pin edited.
- With `cash_yield="T13W"`, positive cash at the previous close earns `q(cash × rate × days / 36500)`
  at the open, the rate read at the previous session (hand-checked tests green).
- A store without `T13W` is refused by `lab run` before anything is spent. Paper (`decide_book`,
  `settle_book`) and `promote` refuse cash-yield rules with a plain message.
- A cash-yield rule set runs on the lab smoke market given `labkit.SMOKE_T13W`, and
  `test_lab_methods.test_candidate_runs_a_smoke_window` attaches it for any such candidate.
- `ruff check engine` is clean and the full engine suite is green with `PG_TEST_URL` set.

## Handoffs

- **Phase 3 (R2 presets):** add `monthly-hold-frac-gotrade-tband-cash` and
  `weekly-hold-frac-gotrade-tband-cash` with `cash_yield="T13W"` (`idle_symbol` must stay `None`;
  this phase refuses the combination). Existing tests that iterate `PRESETS` need Phase 3's
  attention when those presets land:
  - `tests/test_sim_rules.py::test_owner_inputs_of_the_presets` expects `()` for every non-BIL preset, but cash presets give `("cash-yield",)`.
  - `tests/test_lab_costs.py::test_the_real_fee_presets_are_promotable_fractional_books` asserts `PRESETS[-2:]` are the two gotrade presets.
  - `tests/test_sim_rules.py::test_preset_ids_are_unique_and_in_order` lists every id.
  - `tests/test_paper_kickoff.py` loops `needs_kickoff` over `PRESETS`. It stays green because the paper refusal is deliberately NOT in `_book_rules`.
- **Phase 3 / web:** the cash presets are lab-only (no paper, no promote), so `web/` needs no
  idle-cash mirror (phase 3 adds none). Phase 3's `test_sim_rules_fixed_tape.py` asserts that
  `promote._check_rules` refuses the real `monthly-hold-frac-gotrade-tband-cash` preset.
- **Phase 5 (smoke fixture):** Step 11 owns the `labkit.SMOKE_T13W` fixture and the
  `test_lab_methods` smoke-window change, so phase 5's `-CASH` variants pass the smoke test with no
  fixture change of their own (reconciled: moved here from phase 5's contingency).
- **Phases 5 and 7 (lab runs):** a variant using a `-cash` preset carries the owner input
  `cash-yield`, so it is not gate-eligible, by design (plan Decisions). `BookResult.interest_usd` is
  available if a lab note wants to say how much the interest added. The near-miss twins should
  compare `-tband` against `-tband-cash` to isolate the interest effect.
- **Future (out of this plan set):** the test-window store (`engine/.research-test/`) has no
  `market_series.csv`, so a cash-yield method cannot be `lab test`-ed, and `/calculate-assets`
  cannot run it on that store, until someone runs `market_series --refresh` for the test store.
  `run_test` now refuses cleanly instead of crashing. Paper support for `cash_yield` would also
  need a nightly T-bill feed and the owner's confirmation that Gotrade pays interest.

## Rollback

Revert this phase's commit. The lever defaults to a no-op, and nothing recorded before Phase 5
uses it. If a Phase 5/7 lab row already used a cash-yield variant, those rows are append-only:
leave them, and explain the revert in a lab note.
