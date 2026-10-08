> Adopted from `GOTRADE_FEE_REBUILD_PLAN.md` phase 3. Source: `.workflows/plan/gotrade-fee-rebuild/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: The live SPY benchmark pays what the methods pay

**Plan set:** `GOTRADE_FEE_REBUILD_PLAN.md`
**Analysis:** `20261008-091321-H3M8_code_analyzer.md`
**Satisfies:** R1 — every roster entry pays Gotrade's measured fees, SPY included
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/paper`

---

## Goal

After this phase the live SPY benchmark can be told which fee schedule to pay, and it pays it at
all three places money moves: the entry buy, every dividend reinvestment, and the fee each `Fill`
records. The model rides in `BenchmarkState`, so it survives between paper nights. Nothing changes
for the SPY entry that exists today — it keeps the flat 0.1% default, bit for bit — and no new
roster entry is created here; phase 12 creates the Gotrade SPY entry on top of this.

This is **resume condition 1** of the three written above `PAPER_PAUSED` in
`.github/workflows/nightly.yml`.

### Why it is worth doing

Measured in this session, with the real schedule (`sim/costs.py`, untouched):

| | flat (today) | gotrade | ratio |
|---|---|---|---|
| Fee on a $600 SPY entry (0.9352 sh @ $640) | $0.5985 | **$1.45** | 2.42x |
| Fee on a $1,000 SPY entry (9.9766 sh @ $100) | $0.9990 | **$2.34** | 2.34x |
| Total fees over the test window below (7 buys) | $1.3840 | **$3.67** | 2.65x |
| Ending equity over that window, from $1,250 | $1,250.5694 | **$1,248.2768** | −$2.29 |

Commands behind those numbers are in **Verification → Manual check**. SPY is what every method is
judged against, and "beats SPY TR" is a gate condition; if the methods pay Gotrade and the
benchmark pays 0.1%, the gate is biased in the benchmark's favour by roughly 2.5x of the fee bill.

## Interface Contract

**Deletes:** nothing.

**Renames:** nothing.

**Creates:**
- `seer_engine.paper.benchmark._buy(price, shares, cost_model) -> (cash, fee)` (`paper/benchmark.py`,
  lands at the current `:161`, just above `_buy_fill`) — private.

**Signature changes:**
- `paper.benchmark.BenchmarkState` gains a sixth field, **last and defaulted**:
  `cost_model: CostModel = "flat"` (`paper/benchmark.py:83-87`). Every existing construction site
  uses keywords (`paper/store.py:1139`, `tests/test_paper_store.py:444,446,454`,
  `tests/test_paper_benchmark.py:142,194,210-220`) and keeps working unchanged, at `"flat"`.
- `start_benchmark(cash0, start)` -> `start_benchmark(cash0, start, *, cost_model: CostModel = "flat")`
  (`paper/benchmark.py:130`). Keyword-only, defaulted: no caller changes.
- `_buy_fill(session, price, shares, cost, reason)` -> `_buy_fill(session, price, shares, cost, fee, reason)`
  (`paper/benchmark.py:161`) — private, both call sites are inside `step_benchmark`.
- `step_benchmark` and `split_benchmark` signatures are **unchanged**; they read
  `state.cost_model` and carry it forward.

**Requires (from earlier phases):** none. This phase has no dependencies and can land in wave 1.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/backtest/benchmark.py` — it already carries the `cost_model` lever on
  `_whole_shares:109`, `_fractional_shares:121`, `fractional_buy_cost:135`, `_whole_buy_cost:143`,
  each with a working `"gotrade"` branch. This phase *passes* the lever. (Phase 7 edits this file.)
- `engine/src/seer_engine/sim/*` — `costs.py` is invariant 5; `book.py`, `rules.py`, `sizing.py`,
  `lifecycle.py` belong to phase 4.
- `engine/src/seer_engine/paper/store.py` and `book.py` (phase 6), `paper/bracket.py` (phase 4),
  `paper/roster.py` (phase 12), `db/migrations/*`, `.github/workflows/nightly.yml`.
- `engine/src/seer_engine/commands/paper.py` — see **Handoffs**; nothing in this phase edits it.

**Published to phase 12 (what the Gotrade SPY entry must carry):** see **Handoffs**, items H1–H3.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/paper/benchmark.py` | modify | module docstring (`:1-32`); import `sim.costs` (`:44-47`); `BenchmarkState.cost_model` field + validation (`:69-113`); `start_benchmark` keyword (`:130-142`); new `_buy` + `_buy_fill` takes the fee (`:161-172`); the three flat sites threaded and the new state carries the model (`:245-303`) |
| `engine/tests/test_paper_benchmark.py` | modify | `run_nights` takes a cost model (`:71-81`); six new tests appended after the by-hand section (`:186`) and after the validation section (`:240`) |

Two files. No new file, no deletion.

## Implementation Steps

Every code block below was executed against a patched copy of the module in a scratch directory
before being written down: `engine/tests/test_paper_benchmark.py` passes 16/16 unchanged with it,
and `python -m ruff check` passes. The numbers in the new tests are that run's output, not
arithmetic done by hand.

### Step 1: Say in the docstring that the benchmark has a fee model

**File:** `engine/src/seer_engine/paper/benchmark.py:16-18`
**Change:** insert one paragraph between the last rule bullet ("Every session is marked at its
close…") and the paragraph that begins "The holding is a ``sim.book.Position``". The surrounding
text is unchanged; only the paragraph below is new.

**Code:**

```python
``cost_model`` ("flat", the default, or "gotrade") says what a buy pays and rides in
:class:`BenchmarkState`, so it survives between nights. "flat" is 0.1% of the notional, every
rule above unchanged. "gotrade" is Gotrade's measured schedule (``sim.costs``, fitted to the
owner's receipts): the share count is the most whose rounded cash fits
(``sim.costs.gotrade_shares_for``) and the cash paid is ``q(price x n)`` plus the printed fee,
exactly as ``backtest.benchmark.buy_and_hold(..., cost_model="gotrade")`` prices it. A method
measured against this benchmark and the benchmark itself then pay alike -- without it SPY pays
0.1% while the methods pay Gotrade, and "beats SPY TR" is an asymmetric gate.
```

**Impact:** documentation only. The owner reads this file's docstring; it now states the fee rule
in plain words.

### Step 2: Import the cost model vocabulary

**File:** `engine/src/seer_engine/paper/benchmark.py:44-47`
**Change:** add one import line after `from seer_engine.sim.book import _split_position_shares`.
The block becomes, in full:

**Code:**

```python
from seer_engine.sim import COST_RATE, Fill, Position, Snapshot, q
from seer_engine.sim.book import _split_position_shares
from seer_engine.sim.costs import COST_MODELS, CostModel, gotrade_cash
from seer_engine.sim.rules import SHARE_QUANTUM
from seer_engine.sim.split_adjust import _q_exact, _rescale_price, _split_ratio
```

**Impact:** `COST_RATE` stays imported and stays used (Step 4's flat branch), so ruff's `F401` is
not provoked. `sim.costs` is already a dependency of `backtest/benchmark.py`, which this module
already imports — no new edge in the import graph.

### Step 3: `BenchmarkState` carries the model

**File:** `engine/src/seer_engine/paper/benchmark.py:69-113`
**Change:** add the field (last, defaulted) and validate it as the first check in `__post_init__`;
extend the class docstring by one bullet. The complete class head and `__post_init__`:

**Code:**

```python
@dataclass(frozen=True, slots=True)
class BenchmarkState:
    """The SPY benchmark between nights.

    - ``start``: the first paper session (``strategies.paper_start``); the open of ``start`` buys.
    - ``cash``: idle cash, 4 dp, never negative.
    - ``equity``: equity at ``last_session``'s close (``cash0`` before the first session).
    - ``position``: the SPY holding, or None (before ``start``, or when cash never bought a share).
    - ``last_session``: the last session stepped; ``prev_session(start)`` before the first.
    - ``cost_model``: what a buy pays -- "flat" (0.1%) or "gotrade" (``sim.costs``). It is part of
      the state because the benchmark is stepped one night at a time: an entry that pays Gotrade
      must still be paying Gotrade on its thousandth night.

    Persisted as ``paper_state`` (``last_session``, ``cash_usd``, ``equity_usd``) plus one
    ``book_positions`` row from ``position``; ``start`` comes back from ``paper_start``, and
    ``cost_model`` from the entry's frozen spec (``paper.roster.spec``'s ``params``).
    """

    start: date
    cash: Decimal
    equity: Decimal
    position: Position | None
    last_session: date
    cost_model: CostModel = "flat"

    def __post_init__(self) -> None:
        _session("start", self.start)
        if self.cost_model not in COST_MODELS:
            raise ValueError(f"unknown cost_model {self.cost_model!r}; expected one of {COST_MODELS}")
        if _money("cash", self.cash) < 0:
            raise ValueError(f"cash must be >= 0, got {self.cash}")
        _money("equity", self.equity)
        _session("last_session", self.last_session)
        day0 = dates.prev_session(self.start)
        if self.last_session < day0:
            raise ValueError(f"last_session {self.last_session} is before {day0}, the day before start")
        p = self.position
        if p is not None:
            if not isinstance(p, Position):
                raise TypeError(f"position must be a Position, got {type(p).__name__}")
            if p.symbol != SPY:
                raise ValueError(f"the benchmark holds {SPY}, got {p.symbol}")
            if p.shares <= 0 or p.shares.quantize(SHARE_QUANTUM) != p.shares:
                raise ValueError(f"the benchmark holds a positive multiple of {SHARE_QUANTUM} shares, got {p.shares}")
            if p.stop is not None or p.take is not None or p.exit_pending:
                raise ValueError("the benchmark position has no stop, take or pending exit")
            if not self.start <= p.entry_date <= self.last_session:
                raise ValueError(
                    f"position entry {p.entry_date} is outside [{self.start}, {self.last_session}]"
                )
        if self.last_session == day0 and (p is not None or self.cash != self.equity):
            raise ValueError("before the first session the benchmark holds cash only")
```

**Impact:** the field is last and defaulted, so every keyword construction in the tree still
compiles and still means `"flat"` — verified: `paper/store.py:1139`, `tests/test_paper_store.py`
(three sites) and `tests/test_paper_benchmark.py` (six sites) all pass untouched.
`split_benchmark` uses `dataclasses.replace`, which carries the field without an edit.
`slots=True` + a defaulted last field is legal (no mutable default).

### Step 4: One place that prices a buy, and the fee it records

**File:** `engine/src/seer_engine/paper/benchmark.py:161-172`
**Change:** replace `_buy_fill` entirely with a pricing helper plus a thinner `_buy_fill` that is
*handed* the fee instead of recomputing it from the quantized price. The whole replaced region:

**Code:**

```python
def _buy(price: Decimal, shares: Decimal, cost_model: CostModel) -> tuple[Decimal, Decimal]:
    """``(cash out, fee)`` of one benchmark buy of ``shares`` at ``price``, both priced by
    ``cost_model`` on the same unrounded ``price``, so the recorded fee is the fee inside the
    cash that moved. The fee rule is ``sim.book._fee``'s: ``q(price x n x 0.001)`` under
    "flat", Gotrade's printed fee under "gotrade"."""
    cost = fractional_buy_cost(price, shares, cost_model)
    if cost_model == "gotrade":
        return cost, gotrade_cash("buy", price, shares)[1]
    return cost, q(price * shares * COST_RATE)


def _buy_fill(
    session: date, price: Decimal, shares: Decimal, cost: Decimal, fee: Decimal, reason: str
) -> Fill:
    return Fill(
        session_date=session,
        symbol=SPY,
        side="buy",
        shares=shares,
        price=price,
        cash_usd=-cost,
        cost_usd=fee,
        reason=reason,  # type: ignore[arg-type]
    )
```

**Impact.** This is the site the handover does not name, and the reason it matters: today
`cost_usd=q(price * n * COST_RATE)` is computed **unconditionally**, so a benchmark paying
Gotrade would move Gotrade's cash and record a 0.1% fee beside it — a recorded fee 2.3-2.4x
smaller than the money that actually left. Under `"gotrade"` the recorded fee is now the fee
inside the cash: `-cash_usd - cost_usd == q(price x shares)` exactly, asserted by the new test.

Two deliberate details:

- **The flat branch keeps `sim.book._fee`'s rule**, `q(price x n x 0.001)`, rather than
  `cost - q(price x n)`. Measured: over 200,000 random (price, share) pairs the two differ by
  0.0001 — a hundredth of a cent — in 49,846 of them. Paper's benchmark and the book engine
  therefore keep recording fees by one rule, and the flat SPY entry's behaviour is bit-identical
  to today's. Under `"gotrade"` the two definitions coincide by construction.
- **The fee is priced on the same `price` the cash was priced on** (the bar's own `open`/`close`,
  not `q(open)`), which is what makes the equality above exact. Bars are already 4 dp
  (`prices.to_decimal`), so for the flat model this changes nothing: the 16 existing tests pass
  unchanged.

### Step 5: `start_benchmark` takes the model

**File:** `engine/src/seer_engine/paper/benchmark.py:130-142`
**Change:** add a keyword-only parameter and pass it into the state. The complete function:

**Code:**

```python
def start_benchmark(cash0: Decimal, start: date, *, cost_model: CostModel = "flat") -> BenchmarkState:
    """The benchmark the night before ``start``: ``q(cash0)`` in cash, nothing held, paying
    ``cost_model`` ("flat", 0.1%, or "gotrade", ``sim.costs``) on every buy from then on.

    Raises TypeError when ``cash0`` is not a Decimal and ValueError when it is not > 0,
    ``start`` is not an NYSE session (``buy_and_hold``'s checks), or ``cost_model`` is neither
    "flat" nor "gotrade".
    """
    cash = q(_money("cash0", cash0))
    if cash <= 0:
        raise ValueError(f"cash0 must be > 0, got {cash0}")
    _session("start", start)
    return BenchmarkState(
        start=start,
        cash=cash,
        equity=cash,
        position=None,
        last_session=dates.prev_session(start),
        cost_model=cost_model,
    )
```

**Impact:** keyword-only and defaulted, so the existing calls (tests only — there is no production
caller; the live benchmark's day-0 row is written by the freeze path and read back by
`store.load_benchmark`) are unaffected. The `cost_model` check happens in `__post_init__`, so a
bad value raises from `start_benchmark` too.

### Step 6: Thread the model through all three money sites in `step_benchmark`

**File:** `engine/src/seer_engine/paper/benchmark.py:245-304`
**Change:** replace the body from `cash = state.cash` to the `return`. The complete replacement
(everything above `cash = state.cash` — the type checks, the `split` application — is untouched):

**Code:**

```python
    model = state.cost_model
    cash = state.cash
    pos = state.position
    fills: list[Fill] = []
    if session == state.start:
        shares = _fractional_shares(cash, b.open, model)
        cost, fee = _buy(b.open, shares, model)
        cash -= cost
        if shares > 0:
            price = q(b.open)
            pos = Position(
                symbol=SPY,
                shares=shares,
                mark=b.close,
                entry_date=session,
                entry_price=price,
                days_held=1,
                cost_usd=cost,
                income_usd=_ZERO,
                stop=None,
                take=None,
            )
            fills.append(_buy_fill(session, price, shares, cost, fee, "entry"))
    else:
        if pos is not None:
            pos = replace(pos, days_held=pos.days_held + 1)
        if dividend is not None:
            held = Decimal(0) if pos is None else pos.shares
            income = q(held * dividend)
            cash += income
            if pos is not None:
                pos = replace(pos, income_usd=pos.income_usd + income)
            more = _fractional_shares(cash, b.close, model)
            if more > 0:
                cost, fee = _buy(b.close, more, model)
                cash -= cost
                price = q(b.close)
                if pos is None:
                    pos = Position(
                        symbol=SPY,
                        shares=more,
                        mark=b.close,
                        entry_date=session,
                        entry_price=price,
                        days_held=1,
                        cost_usd=cost,
                        income_usd=_ZERO,
                        stop=None,
                        take=None,
                    )
                    fills.append(_buy_fill(session, price, more, cost, fee, "entry"))
                else:
                    pos = replace(pos, shares=pos.shares + more, cost_usd=pos.cost_usd + cost)
                    fills.append(_buy_fill(session, price, more, cost, fee, "add"))

    if pos is not None:
        pos = replace(pos, mark=b.close)
    held = Decimal(0) if pos is None else pos.shares
    equity = q(cash + held * b.close)
    new = BenchmarkState(
        start=state.start,
        cash=cash,
        equity=equity,
        position=pos,
        last_session=session,
        cost_model=model,
    )
    return new, Snapshot(date=session, cash_usd=cash, equity_usd=equity), tuple(fills)
```

**Impact.** All three flat sites are gone: the entry share count and cash (`:249-250`), the
reinvestment share count and cash (`:276-278`), and the recorded fee (`:170`, via `_buy`). The
`new = BenchmarkState(...)` at `:303` is the one place the state is rebuilt from scratch rather
than through `replace`, so it is the one place the model could have been silently dropped — it
carries `cost_model=model` explicitly.

`cash -= cost` still runs when `shares == 0` on the entry session. That is safe under both models:
measured, `gotrade_cash("buy", price, 0)` is `(0.0000, 0.00)` — `sim.costs.fee_parts` charges
nothing for an amount of exactly zero, because there is no order.

### Step 7: Let the test loop choose a model

**File:** `engine/tests/test_paper_benchmark.py:71-81`
**Change:** replace `run_nights` whole. The default keeps all six existing callers on "flat".

**Code:**

```python
def run_nights(
    spy: dict[date, Bar],
    start: date,
    end: date,
    cash0: Decimal,
    paid: dict[date, Decimal],
    cost_model: str = "flat",
):
    state = start_benchmark(cash0, start, cost_model=cost_model)
    snaps = [state.snapshot()]
    fills: list[Fill] = []
    states = [state]
    for d in dates.sessions(start, end):
        state, snap, night_fills = step_benchmark(state, d, spy[d], paid.get(d))
        snaps.append(snap)
        fills.extend(night_fills)
        states.append(state)
    return state, tuple(snaps), fills, states
```

**Impact:** none on the existing tests (verified: 16/16 pass).

### Step 8: The new tests

**File:** `engine/tests/test_paper_benchmark.py` — append the first four after
`test_reinvestment_can_open_the_holding` (`:186`), and the last two after `test_step_validation`
(`:240`). Also extend the module docstring's arithmetic note.

**Code (module docstring, `test_paper_benchmark.py:5-8`, replacing that paragraph):**

```python
Arithmetic: ``fractional_buy_cost(p, n) = q(p x n x 1.001)``; shares ``cash / (price x 1.001)``
floored to 0.0001 (``backtest.benchmark._fractional_shares``: the paper benchmark is fractional
since 2026-10-07, when the paper books went to 10,000,000 IDR); dividend credit ``q(shares x amount)``.
The loops compare against ``buy_and_hold(..., fractional=True)``.

Under ``cost_model="gotrade"`` the same loops compare against
``buy_and_hold(..., fractional=True, cost_model="gotrade")``: the share count is
``sim.costs.gotrade_shares_for`` and the cash is ``q(p x n)`` plus Gotrade's printed fee. The
benchmark pays what a ``cost_model="gotrade"`` method pays, which is what makes "beats SPY TR"
a fair gate.
```

**Code (the six tests):**

```python
# --------------------------------------------------------------------------- Gotrade's fees


def test_gotrade_nights_equal_buy_and_hold_at_the_same_cost_model():
    curve = buy_and_hold(
        SPY_BARS, START, END, CASH0, dividends=DIVIDENDS, name="spy_tr",
        fractional=True, cost_model="gotrade",
    )
    state, snaps, fills, _ = run_nights(SPY_BARS, START, END, CASH0, PAID, "gotrade")
    assert snaps == curve.snapshots
    assert state.shares == curve.shares
    assert state.cash == curve.cash
    assert state.income_usd == curve.dividends_usd
    assert state.equity == curve.snapshots[-1].equity_usd
    # Not vacuous: 7 buys either way, and Gotrade's bill is 2.65x the flat one.
    flat_state, _, flat_fills, _ = run_nights(SPY_BARS, START, END, CASH0, PAID)
    assert len(fills) == len(flat_fills) == 7
    assert sum(f.cost_usd for f in fills) == Decimal("3.67")
    assert sum(f.cost_usd for f in flat_fills) == P("1.384")
    assert state.equity == P("1248.2768") < flat_state.equity == P("1250.5694")


def test_gotrade_position_and_fills_by_hand():
    # MON open 100: 1000 buys 9.9766 sh -- amount q(997.66) = 997.66, fee $2.34 (trading
    #   0.2% = $2.00, regulatory capped $0.11, PPN 11% of $2.11 = $0.23), cash out exactly
    #   1000.0000; cash 0, equity 9.9766 x 101 = 1007.6366. Flat buys 9.99 sh for a $0.999 fee.
    # WED dividend 2.5: cash + q(24.9415) = 24.9415; that buys 0.2531 sh at the close 98 --
    #   amount q(24.8038) = 24.8038, fee $0.13, cash out 24.9338; cash 0.0077, 10.2297 sh,
    #   equity 0.0077 + 10.2297 x 98 = 1002.5183.
    s = start_benchmark(P("1000"), MON, cost_model="gotrade")
    s, snap, fills = step_benchmark(s, MON, WEEK_BARS[MON], None)
    assert snap == Snapshot(MON, P("0"), P("1007.6366"))
    assert fills == (Fill(MON, SPY, "buy", P("9.9766"), P("100"), P("-1000"), Decimal("2.34"), "entry"),)
    assert s.position == Position(SPY, P("9.9766"), P("101"), MON, P("100"), 1, P("1000"), P("0"), None, None)
    s, snap, fills = step_benchmark(s, TUE, WEEK_BARS[TUE], None)
    assert fills == () and s.position.days_held == 2 and s.position.mark == P("102")
    s, snap, fills = step_benchmark(s, WED, WEEK_BARS[WED], Decimal("2.5"))
    assert snap == Snapshot(WED, P("0.0077"), P("1002.5183"))
    assert fills == (Fill(WED, SPY, "buy", P("0.2531"), P("98"), P("-24.9338"), Decimal("0.13"), "add"),)
    assert s.position == Position(SPY, P("10.2297"), P("98"), MON, P("100"), 3, P("1024.9338"), P("24.9415"), None, None)
    assert s.income_usd == P("24.9415")


def test_the_recorded_fee_is_the_fee_inside_the_cash_that_moved():
    # The site the handover does not name: Fill.cost_usd. Under "gotrade" the notional plus the
    # recorded fee is exactly the cash that left, so a fill can be reconciled against a receipt.
    _, _, fills, _ = run_nights(SPY_BARS, START, END, CASH0, PAID, "gotrade")
    assert fills
    for f in fills:
        assert -f.cash_usd - f.cost_usd == q(f.price * f.shares), f


def test_the_fee_floor_makes_dust_unbuyable():
    # The flat model buys 0.0001 sh with a penny (test_reinvestment_can_open_the_holding).
    # Gotrade's $0.10 per-order minimum costs 11 cents to spend one, so nothing is ever bought.
    curve = buy_and_hold(
        WEEK_BARS, MON, FRI, P("0.01"), dividends=[Dividend(WED, Decimal("2.5"))], name="x",
        fractional=True, cost_model="gotrade",
    )
    state, snaps, fills, _ = run_nights(WEEK_BARS, MON, FRI, P("0.01"), {WED: Decimal("2.5")}, "gotrade")
    assert snaps == curve.snapshots
    assert (state.shares, state.cash) == (curve.shares, curve.cash) == (P("0"), P("0.01"))
    assert fills == [] and state.position is None


def test_cost_model_survives_the_night():
    # The store rebuilds the state from paper_state + one book_positions row + paper_start +
    # the entry's frozen spec; the model must come back with it or night 2 pays 0.1%.
    s = start_benchmark(P("1000"), MON, cost_model="gotrade")
    for d in (MON, TUE, WED):
        s, _, _ = step_benchmark(s, d, WEEK_BARS[d], Decimal("2.5") if d == WED else None)
    assert s.cost_model == "gotrade"
    p = s.position
    loaded = BenchmarkState(
        start=MON,
        cash=s.cash,
        equity=s.equity,
        position=Position(p.symbol, p.shares, p.mark, p.entry_date, p.entry_price,
                          p.days_held, p.cost_usd, p.income_usd, None, None),
        last_session=WED,
        cost_model="gotrade",
    )
    assert loaded == s
    assert step_benchmark(loaded, THU, WEEK_BARS[THU], None) == step_benchmark(s, THU, WEEK_BARS[THU], None)
    # Dropping the model on the way back in is not silently equivalent: it is a different book.
    flat = BenchmarkState(start=MON, cash=s.cash, equity=s.equity, position=loaded.position, last_session=WED)
    assert flat.cost_model == "flat" and flat != s


def test_cost_model_validation():
    assert start_benchmark(P("1000"), MON).cost_model == "flat"
    with pytest.raises(ValueError, match="unknown cost_model"):
        start_benchmark(P("1000"), MON, cost_model="percent")
    with pytest.raises(ValueError, match="unknown cost_model"):
        BenchmarkState(start=MON, cash=P("1000"), equity=P("1000"), position=None,
                       last_session=D("2026-02-27"), cost_model="gotrade2")
```

The new tests need two names the file does not import yet. Extend the existing import lines:

```python
from seer_engine.sim import Fill, Position, Snapshot, q
```

(`q` is added to the `seer_engine.sim` import at `:29`; `Dividend` and `buy_and_hold` are already
imported at `:20`, and `D`, `P`, `bar` at `:17`.)

**Impact:** `test_paper_benchmark.py` goes from 16 tests to 22. Every number asserted above is
this session's measured output from the patched module, not hand arithmetic.

## Verification

**Build (lint — this is what engine CI runs):**

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild && python -m ruff check engine
```

**Tests (the phase's own file first, then the suite):**

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild
PYTHONPATH=engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  python -m pytest engine/tests/test_paper_benchmark.py -q -n auto
PYTHONPATH=engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  python -m pytest engine/tests -q -n auto
```

`PYTHONPATH` is required — without it pytest silently tests the main checkout, not this branch.
Never pass `-o addopts`. `main` is red for two known reasons (handover §6a, §6b, fixed by phases 1
and 2); neither is in `engine/tests/test_paper_benchmark.py`, `test_paper_store.py` or
`test_paper_command*.py`. Those three must be green.

**Manual check** — the commands behind the numbers in **Goal**, runnable from the worktree root:

```
PYTHONPATH=engine/src python -c "
from decimal import Decimal as D
from seer_engine.sim.costs import gotrade_cash, gotrade_shares_for
from seer_engine.sim import q, COST_RATE
for cash, price in ((D('600.0000'), D('640.0000')), (D('1000.0000'), D('100.0000'))):
    n = gotrade_shares_for(cash, price, D('0.0001'))
    cost, fee = gotrade_cash('buy', price, n)
    flat = q(price * n * COST_RATE)
    print(f'{cash} at {price}: {n} sh, gotrade fee {fee}, flat fee {flat}, ratio {fee/flat:.2f}')
"
```

Prints `0.9352 sh, gotrade fee 1.45, flat fee 0.5985, ratio 2.42` and
`9.9766 sh, gotrade fee 2.34, flat fee 0.9990, ratio 2.34`.

The window totals ($3.67 vs $1.3840 of fees, $1,248.2768 vs $1,250.5694 of ending equity) are
asserted directly by `test_gotrade_nights_equal_buy_and_hold_at_the_same_cost_model`, so running
that test is the command behind them.

**Exit criteria:**

1. `step_benchmark(state, ...)` with `state.cost_model == "gotrade"` buys the share count and
   pays the cash that `buy_and_hold(..., fractional=True, cost_model="gotrade")` does, over a
   300+ session window with seven dividends — snapshots, shares, cash and dividends all equal.
2. Every `Fill` it emits satisfies `-cash_usd - cost_usd == q(price x shares)`: the recorded fee
   is the fee inside the cash that moved. None of the three flat sites survives.
3. `BenchmarkState` carries `cost_model`, `step_benchmark` carries it forward, and a state
   rebuilt from its persisted fields plus the model steps identically.
4. The default is `"flat"` and the existing SPY entry's arithmetic is bit-identical: the 16
   pre-existing tests in `test_paper_benchmark.py` pass unchanged.
5. `PAPER_PAUSED` is untouched; no roster entry is added, edited or retired; `sim/costs.py` is
   unmodified (`git diff --stat` shows exactly two files).

## Handoffs

**H1 — the load path must read the model. OWNER: PHASE 12 (settled, index Decision D10).**
This phase makes the benchmark *capable* of paying Gotrade; one wire is still open. `BenchmarkState`
is rebuilt each night by `store.load_benchmark` (`paper/store.py:1127-1145`), which constructs it
from `paper_state` + `book_positions` + `paper_start` and will therefore take the `"flat"` default
until someone passes the model. The minimal wiring, for whoever owns it:

```python
# paper/store.py:1127 -- signature and the final construction
def load_benchmark(
    conn: psycopg.Connection, strategy_id: str = BENCHMARK_ID, *, cost_model: CostModel = "flat"
) -> BenchmarkState:
    ...
    return BenchmarkState(
        start=row.paper_start,
        cash=state.cash_usd,
        equity=state.equity_usd,
        position=positions[0] if positions else None,
        last_session=state.last_session,
        cost_model=cost_model,
    )
```

```python
# commands/paper.py:867 -- _step_benchmark's first line
bench = store.load_benchmark(conn, e.id, cost_model=roster.benchmark_cost_model(e.id))
```

`roster.benchmark_cost_model` takes the **entry id, a string** — not the entry — and answers from
`roster.BENCHMARK_COST_MODEL`, the roster's own per-id statement, raising `BadRosterRow` rather than
defaulting when an id is not named there. That same statement is what `roster.spec` writes into the
frozen spec (H2), so what is pinned and what is charged are one fact. Phase 12 defines both
(`phase-12.md` Step 2) and calls it (Step 7b); this signature is quoted here as phase 12 lands it,
so the two halves cannot drift.

**Assigned by the reconciler, 2026-10-08: BOTH edits are phase 12's**, and they are written out as
explicit steps in `phase-12.md` (Step 7b). The rung is 1 — the stated invariant that the tree builds
and both suites pass at the end of *each* phase — applied through index Decision **D10**:

- `engine/src/seer_engine/commands/paper.py` — D10 gives the whole file to phase 12. This phase does
  **not** edit it.
- `engine/src/seer_engine/paper/store.py:1127-1145` (`load_benchmark`'s keyword-only `cost_model`)
  — also phase 12's, **not** phase 6's, even though phase 6 owns the rest of that file. Phase 6's
  region is the deposit path at `:417`/`:449`; `:1127` is line-disjoint from it, phase 12 depends on
  phase 6 so the two edits are sequential and never concurrent, and keeping every wire in one phase
  is the whole point of D10. Phase 6's plan records that it must not touch `:1127`.

The capability this phase ships is complete and **inert** until then: the new parameter is
keyword-only with a `"flat"` default, so the tree builds and all 22 tests pass at the end of this
phase with the wiring absent. Without H1 the Gotrade SPY entry would step at 0.1% and R1 would be
only half satisfied — which is why phase 12's exit criteria now assert it.

**H2 — what the benchmark's spec must carry (phase 12).** `roster.spec` (`paper/roster.py:1045-1056`)
writes the benchmark's params as a dict of strings with `rules_id = None` — the benchmark has no
`TradeRules`, so it has nowhere else to put a fee model. Today:

```python
params: dict[str, str] = {
    "symbol": BENCHMARK_ID,
    "entry": "open",
    "shares": "whole",
    "dividends": "reinvest",
    "cost_rate": str(COST_RATE),
}
```

The successor entry needs `"cost_model": "gotrade"` in that dict, and `"cost_rate"` only means
something under `"flat"`. Two further observations for phase 12, neither acted on here:
`"shares": "whole"` has been wrong since 2026-10-07 — the paper benchmark is fractional
(`_fractional_shares`, `SHARE_QUANTUM`); and the spec of the *started* SPY entry must not be
touched (invariants 3 and 8) — the correction rides on the new id with its own fresh clock.

**H3 — the successor entry itself (phase 12, R1).** Creating the Gotrade SPY roster row, its
migration (`017`), marking the predecessor retired, and the `docs/runbooks/paper-trading.md`
update all belong to phase 12. This phase deliberately adds no roster entry.

**H4 — the sell side is not reachable here, by design.** `sim.costs` prices sells too
(`gotrade_cash("sell", ...)`, validated against the owner's $72.51 receipt), but the benchmark
never sells: it buys at `start`, reinvests dividends and is marked, never liquidated. The only
cash that ever leaves a SPY holding is split cash in lieu, which is a payment received, not an
order. No sell path is added.

**H5 — not done, deliberately (no phase).** `backtest/benchmark.py`'s flat `_fee` convention and
`sim/book.py:350`'s differ from `cost - q(price x n)` by 0.0001 on about a quarter of buys
(measured above). It is a hundredth of a cent, it is consistent across the two engines, and
changing it would rewrite the recorded fee of every flat fill in the system for no gain. Left
alone.

## Rollback

`git revert` the phase's single commit on `feature/gotrade-fee-rebuild`. It touches two files,
both additive and both defaulted to today's behaviour, so nothing else in the tree depends on it
*until* phase 12 lands H1/H2 — after that, reverting this phase also requires reverting phase 12
(the Gotrade SPY entry would reference a `cost_model` keyword that no longer exists). No
migration, no database row, no state: the paper clock stays at zero stepped sessions throughout,
so there is no history to unwind.
