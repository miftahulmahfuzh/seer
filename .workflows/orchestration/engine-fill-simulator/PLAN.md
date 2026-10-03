# Plan: Seer fill simulator (P2) — `engine/src/seer_engine/sim/`

**Slug:** engine-fill-simulator
**Date:** 2026-10-03 13:44 WIB
**Analysis:** `20261003-134417-F7S2_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/engine-fill-simulator`
**Branch:** `feature/engine-fill-simulator` (base: `HEAD` @ `b9780b8`)
**Phases:** 4
**Status:** 2/4 phases complete (1, 3)
**Coordinator:** —

---

## Why

The specification is `docs/handover/2026-10-03-fill-simulator.md` (committed at `b9780b8`).
Its §2 goal, verbatim:

> Build the order-lifecycle and portfolio simulator in `engine/` as **pure, deterministic Python**:
> no database and no network in the core. **One code path** must serve both the 10-year backtest
> (P3) and nightly forward paper trading (P4). The ROADMAP calls this the critical path, and design
> §9 calls it "the highest-priority code in the repo".
>
> It must:
> 1. Take pending bracket orders through `pending → open → closed` or `pending → expired`, exactly
>    as in design §5 plus the decisions in §3 below.
> 2. Size orders with whole shares across 4 slots, using equity ÷ 4 recomputed daily.
> 3. Keep cash and equity per strategy portfolio, with 0.1% costs per side, and produce a
>    per-session equity snapshot.
> 4. Give P3/P4 a small API: advance a portfolio through one session's bars, report the events
>    (fill, expire, exit), and size new picks for the next session.
>
> **Out of scope, don't build:** strategies and signals (P3), the backtest runner and report (P3),
> the SPY buy-and-hold benchmark curve (P3), writing to `orders`/`equity_snapshots` and wiring into
> `nightly` (P4), LLM explanations (P4), any web change.

The handover's §3 tables are law, design §5 included ("do not reopen"). §6 is the acceptance list.
§7's open questions are settled under **Decisions** below.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Order lifecycle `pending → open → closed` / `pending → expired` exactly as design §5 + handover §3 | 1 |
| R2 | Whole-share sizing, 4 slots, equity ÷ 4 recomputed daily, cash cap, ineligible < 1 share, no adding, 0 picks valid | 2 |
| R3 | Cash/equity per portfolio, 0.1% cost per side, `pnl_usd`, per-session equity snapshot | 1 |
| R4 | Small pure deterministic API for P3/P4, import-purity test, ≥10-session hand-checked scenario, documented in `engine/package_readme.md` | 1, 4 |
| R5 | Pure split-recompute function for live orders (forward and reverse) | 3 |

## Scope

**In scope:** new package `engine/src/seer_engine/sim/`, new pure module `engine/src/seer_engine/prices.py`
(with `bars.py` re-exporting from it), new tests `engine/tests/simkit.py` and `engine/tests/test_sim_*.py`,
the `sim` section of `engine/package_readme.md`, and the P2 status line in `docs/ROADMAP.md`.

**Out of scope:** everything in the handover's "Out of scope" list. That also means no CLI command
(nothing to run yet), no migration, no web change, and no edits to `commands/*`, `splits.py`,
`dates.py` or any DB module other than the `bars.py` re-export.

## Invariants

1. The tree builds and `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q` passes with **0 skipped** at the end of every phase (`docker start seer-pg` first). The baseline is 216 passed; after phase 1 it is 292, after phases 2 and 3 it is 363, and after phase 4 it is 374. `engine/.venv` is the **worktree's own** venv. The worktree has none at first, and phase 1 Step 0 creates it with `cd /home/miftah/.worktrees/seer/engine-fill-simulator && python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'` (`python3` is pyenv's 3.11.0). Never run tests with `/home/miftah/seer/engine/.venv`: it is an editable install of `/home/miftah/seer` and tests main's tree.
2. Every existing `from seer_engine.bars import Bar, to_decimal, PRICE_QUANTUM, make_bar, …` keeps working unchanged.
3. `seer_engine.sim` and everything it imports load no `psycopg`, `requests` or `yfinance`, measured in a fresh subprocess by `sys.modules`. The core may import `seer_engine.dates` (measured clean) and `seer_engine.prices`, and must **never** import `seer_engine.bars`.
4. Pure and deterministic: no wall-clock reads (`datetime.now`, `date.today`, `time.*`), no randomness, no I/O, no logging side effects in the core. Every output tuple is in a defined order. Iterating over a `set`, or over a dict built from a set, is not allowed in output paths.
5. `Decimal` everywhere for money and prices. Prices and money are quantized to 4 dp with `ROUND_HALF_UP` (`PRICE_QUANTUM`). Shares are `int`. No `float` ever enters the core: inputs that are not `Decimal` raise `TypeError`.
6. Every handover §3 rule holds exactly, and so does every row under **Decisions** below.

## Shared API contract (all phases plan against this; phase 1 creates it)

```python
# seer_engine/prices.py   (pure; bars.py does `from seer_engine.prices import PRICE_QUANTUM, Bar, to_decimal`)
PRICE_QUANTUM = Decimal("0.0001")
@dataclass(frozen=True, slots=True) class Bar: symbol, date, open, high, low, close: Decimal, volume: int
def to_decimal(x) -> Decimal

# seer_engine/sim/model.py
SLOTS = 4
TIME_STOP_DAYS = 5
COST_RATE = Decimal("0.001")
OrderStatus = Literal["pending", "open", "closed", "expired"]
ExitReason  = Literal["tp", "sl", "time", "gap"]
EventKind   = Literal["fill", "expire", "exit", "split"]

def q(x: Decimal) -> Decimal                      # quantize to PRICE_QUANTUM, ROUND_HALF_UP
def buy_cost(price: Decimal, shares: int) -> Decimal     # q(price * shares * (1 + COST_RATE))
def sell_proceeds(price: Decimal, shares: int) -> Decimal # q(price * shares * (1 - COST_RATE))
def initial_cash_usd(idr: Decimal, usd_idr: Decimal) -> Decimal  # q(idr / usd_idr)

@dataclass(frozen=True, slots=True)
class Order:                       # mirrors `orders` columns (minus strategy_id/company/explanation/id/created_at)
    session_date: date             # the session the bracket is placed for
    slot: int                      # 1..4
    symbol: str
    last_price: Decimal
    limit_price: Decimal
    tp_price: Decimal
    sl_price: Decimal
    shares: int                    # > 0
    status: OrderStatus = "pending"
    fill_date: date | None = None
    fill_price: Decimal | None = None
    days_held: int = 0
    exit_date: date | None = None
    exit_price: Decimal | None = None
    exit_reason: ExitReason | None = None
    pnl_usd: Decimal | None = None

@dataclass(frozen=True, slots=True)
class Portfolio:
    cash: Decimal                                   # real cash, 4 dp
    equity: Decimal                                 # equity at the last snapshot (or initial cash)
    orders: tuple[Order, ...] = ()                  # LIVE only (pending + open), sorted by slot; <= 1 per slot
    marks: tuple[tuple[str, Decimal], ...] = ()     # last known close per OPEN symbol, sorted by symbol
    last_session: date | None = None                # last session stepped
    # helpers (methods): open_orders(), pending_orders(), free_slots() -> tuple[int, ...] ascending,
    #                    held_symbols() -> tuple[str, ...] sorted, mark(symbol) -> Decimal | None

def new_portfolio(cash_usd: Decimal) -> Portfolio   # equity = cash = q(cash_usd)

@dataclass(frozen=True, slots=True)
class Event:
    session_date: date
    kind: EventKind
    order: Order                   # order state AFTER the event
    forced: bool = False           # exit at the last known close without a bar: close_unpriced, or a split flooring an open position to 0
    cash_usd: Decimal | None = None  # cash moved: -buy_cost on fill, +proceeds on exit, +cash-in-lieu on split

@dataclass(frozen=True, slots=True)
class Snapshot: date: date; cash_usd: Decimal; equity_usd: Decimal

@dataclass(frozen=True, slots=True)
class StepResult: portfolio: Portfolio; events: tuple[Event, ...]; snapshot: Snapshot

# seer_engine/sim/lifecycle.py   (phase 1)
def step(portfolio: Portfolio, session_date: date, bars: Mapping[str, Bar]) -> StepResult
def close_unpriced(portfolio: Portfolio, symbols: Iterable[str]) -> tuple[Portfolio, tuple[Event, ...]]

# seer_engine/sim/sizing.py      (phase 2)
@dataclass(frozen=True, slots=True) class Pick: symbol, last_price, limit_price, tp_price, sl_price: Decimal
RejectReason = Literal["no_slot", "held", "lt_one_share"]
@dataclass(frozen=True, slots=True) class Rejection: symbol: str; reason: RejectReason
@dataclass(frozen=True, slots=True) class SizingResult: portfolio: Portfolio; placed: tuple[Order, ...]; rejected: tuple[Rejection, ...]
def size_picks(portfolio: Portfolio, picks: Sequence[Pick], session_date: date) -> SizingResult

# seer_engine/sim/split_adjust.py (phase 3)
def apply_split(portfolio: Portfolio, symbol: str, factor: Decimal, session_date: date) -> tuple[Portfolio, tuple[Event, ...]]
#   ValueError (input untouched) when a rescaled price or mark rounds to 0 at 4 dp, or SL rounds up to TP

# seer_engine/sim/__init__.py — phase 1 exports model + lifecycle (18 names); phase 4 adds sizing + split_adjust (24 names).
#   __all__ is isort-style sorted (ruff RUF022: constants, types, functions), not sorted() order.
```

Test helpers (`engine/tests/simkit.py`, phase 1; phases 2–4 import it and do not edit it):
`D("2026-10-05") -> date` (a `date` passes through), `P("12.5") -> Decimal` (quantized; str/int/Decimal, float refused),
`bar(symbol, d, o, h, l, c, volume=1_000_000) -> Bar`, `day(*bars) -> dict[str, Bar]`,
`pending(symbol, session_date, limit, tp, sl, shares, slot=1, last=None) -> Order` (`last` defaults to `limit`),
`opened(symbol, fill_date, fill_price, tp, sl, shares, days_held, slot=1, limit=None) -> Order`,
`portfolio(cash, *orders, marks=None, last_session=None, equity=None) -> Portfolio` (`marks` default to each open
order's fill price; `equity` defaults to `q(cash + Σ shares × mark)`).

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Pure price types, sim model and session lifecycle | R1, R3, R4 | `seer_engine`, `seer_engine.sim` | 8 | — | HARD | `.workflows/plan/engine-fill-simulator/phase-1.md` | P1-ENG-DQFG ✓ done | — |
| 2 | Whole-share sizing of picks into slots | R2 | `seer_engine.sim` | 2 | 1 | NORMAL | `.workflows/plan/engine-fill-simulator/phase-2.md` | P1-ENG-2PWS | — |
| 3 | Split recompute for live orders | R5 | `seer_engine.sim` | 2 | 1 | NORMAL | `.workflows/plan/engine-fill-simulator/phase-3.md` | P1-ENG-56QL ✓ done | — |
| 4 | Public API, scenario, determinism, benchmark, docs | R4 | `seer_engine.sim`, docs | 4 | 2, 3 | NORMAL | `.workflows/plan/engine-fill-simulator/phase-4.md` | P1-ENG-SEZ7 | — |

Phases 2 and 3 share no file and can run concurrently.

### Phase 1 — Pure price types, sim model and session lifecycle
**Satisfies:** R1, R3, R4 (purity test only)
**Owns:** `engine/src/seer_engine/prices.py` (new), `engine/src/seer_engine/bars.py` (move `Bar`/`PRICE_QUANTUM`/`to_decimal` out, re-export), `engine/src/seer_engine/sim/__init__.py`, `sim/model.py`, `sim/lifecycle.py`, `engine/tests/simkit.py`, `engine/tests/test_sim_lifecycle.py`, `engine/tests/test_sim_purity.py`.
**Does not touch:** sizing, splits, readme, ROADMAP.
**Exit criteria:** `step` and `close_unpriced` implement every lifecycle rule and decision. A test exists for each lifecycle edge case in handover §6.1: touch vs penetrate for entry/TP/SL, open < limit, gap SL → `gap`, gap TP → `tp`, same-bar SL first, no check on the fill session, time stop at the day-6 open across a holiday and a half day, expiry, costs and `pnl_usd` to the cent, slot freed after an exit, a missing bar for a held symbol, a missing bar for a pending order, and `close_unpriced`. The purity subprocess test passes. The full suite is green with 0 skipped.

### Phase 2 — Whole-share sizing of picks into slots
**Satisfies:** R2
**Owns:** `engine/src/seer_engine/sim/sizing.py` (new), `engine/tests/test_sim_sizing.py` (new).
**Does not touch:** `sim/__init__.py` (phase 4 exports it), `model.py`, `lifecycle.py`.
**Exit criteria:** tests for whole-share sizing, equity ÷ 4 from the last snapshot, the cash cap with earlier placements that night, `lt_one_share`, `held` (no adding, including a symbol already pending and a duplicate pick), `no_slot`, 0 picks, the lowest free slot first in pick order, slot reuse after an exit or expiry on the same session (driven through `step`), and validation errors. Suite green.

### Phase 3 — Split recompute for live orders
**Satisfies:** R5
**Owns:** `engine/src/seer_engine/sim/split_adjust.py` (new), `engine/tests/test_sim_split.py` (new).
**Does not touch:** `sim/__init__.py`, `model.py`, `lifecycle.py`, `seer_engine/splits.py`.
**Exit criteria:** tests for a forward split (10:1, 3:2) and a reverse split (1:32, 1:3 with a fractional remainder → cash in lieu) on an open position and on a pending order, a pending order flooring to 0 → `expire` event, an open position flooring to 0 → forced `exit` paid in lieu, prices that 4 dp cannot hold → `ValueError` with the input untouched, symbols not affected, `marks` rescaled, and a split followed by `step` on adjusted bars giving the same economic P/L. Suite green.

### Phase 4 — Public API, scenario, determinism, benchmark, docs
**Satisfies:** R4
**Owns:** `engine/src/seer_engine/sim/__init__.py` (add the sizing and split exports), `engine/tests/test_sim_scenario.py` (new), `engine/package_readme.md` (`sim` + `prices` sections, layout, performance, P3/P4 usage loop), `docs/ROADMAP.md` (P2 status line).
**Does not touch:** behavior in `model.py`, `lifecycle.py`, `sizing.py`, `split_adjust.py`. If the scenario exposes a bug in them, the fix is allowed and is recorded in the phase's commit message.
**Exit criteria:** a ≥10-session, 4-slot, mixed-outcome scenario with hand-checked final cash, every snapshot's equity, and every closed trade's `pnl_usd` (12 sessions; final cash 985.0996, final equity 1340.5996, Σ pnl 84.6604). Running the scenario twice gives identical outputs. A benchmark of 2,950 sessions × 4 slots finishes under a generous bound, and the measured time is written in the readme. The readme documents the API for P3 and P4. Suite green with 0 skipped.

## Reconciliation Log

Round 1. All four plans' code blocks were applied to a scratch copy of `engine/` and run: before the edits, 157 sim
tests passed and the full suite gave 373 passed, 0 skipped. After the edits, 158 sim tests passed (phase 1: 72 + 4,
phase 2: 36, phase 3: 35, phase 4: 11), the full suite gave **374 passed, 0 skipped**, and phases 2 and 3 each
passed on phase 1 alone (112 and 111 sim tests), so they can run concurrently.

| # | Conflict | Class | Resolution |
|---|---|---|---|
| 1 | Phase 3 closes an open position that floors to 0 with a forced `exit` (reason `time`). Phase 1's `Event.forced` docstring named only `close_unpriced`, and no Decisions row covered the case | Contract drift | Checked that the closed order passes phase 1's `Order` validation (shares ≥ 1, sl < tp, fill and exit fields, days_held ≥ 1, pnl set; the test runs green). Widened phase 1's `forced` docstring and the index contract comment to "exit at the last known close without a bar", which covers both. Recorded as a Decision |
| 2 | A forward split of a sub-cent bracket can round SL and TP to equal values, or a price or mark to 0. No plan said what happens; phase 1's `Order` would raise an incidental ValueError partway through | Gap / fork | Phase 3 now checks the rescaled prices and the mark up front and raises `ValueError` naming the symbol and slot, so the input is untouched. Added `test_split_that_leaves_prices_unrepresentable_at_4dp_is_a_value_error` (phase 3: 34 → 35 tests). Phase 1's handoff, phase 4's readme and the contract say so. Decision row |
| 3 | Phase 4's Build/Check asserted `sorted(__all__) == __all__`, but phase 1's `__all__` (which phase 4 extends) is isort-style (constants, types, functions). Measured: the check returns False | Broken-build phase (verification) | Phase 4's check now uses the isort-style key and asserts all 24 names resolve. Phase 1 and the index say what "sorted" means |
| 4 | A phase 4 test comment and its "Ordering robustness" paragraph described events in stage order (time, gap, intraday, fill, expire). Phase 1 emits exits of any reason by slot, then fills by slot, then expiries by slot | Contract drift | The comment and paragraph now state phase 1's order. The expected tuples were already in that order and pass |
| 5 | Phase 4's `_ev` compared `days_held` on exits only, saying "the contract does not pin" it on fills. Phase 1 pins a fill to 1 and an expiry to 0 | Contract drift (weak assertion) | `_ev` compares `days_held` on every event. `_fill` expects 1 and `_expire` expects 0. Passes |
| 6 | The venv instructions diverged: phase 1 offered the main checkout's venv with `PYTHONPATH`, phase 3 said `python -m venv`, phase 4 said `python3.11 -m venv`, and Invariant 1 said nothing | Contract drift | Every plan and Invariant 1 now give the same command (`python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'` from the worktree root) and forbid the main checkout's venv |
| 7 | Phase 2 computed "held" from its own set over `portfolio.orders`, alongside phase 1's `held_symbols()` | Duplicate work | Phase 2 now uses `set(portfolio.held_symbols())`, so there is one definition (pending included). Behaviour is unchanged |
| 8 | Phase 4's readme module graph said `split_adjust` imports only `dates` and `sim.model`. It also imports `prices` | Contract drift | Corrected in phase 4 Step 3d |
| 9 | Phase 4's P4 nightly sketch loads `marks` as "last close per open symbol" and then calls `apply_split`. If the marks come from history that `splits.apply` already rescaled, the mark is rescaled twice | Gap (doc) | Added a comment to the sketch: marks must be in the orders' pre-split units. The wiring itself stays P4's |
| 10 | Phase 1 added the `simkit.day()` helper and the `portfolio()` mark and equity defaults, which the draft index list lacked | Unmet assumption (doc) | The index's simkit list now matches phase 1. Phases 2-4 call the helpers exactly as phase 1 defines them (checked by running them) |

Checked with no conflict: `close_unpriced` recomputes `equity` (phase 1) and phase 4's readme says to persist the
snapshot after it. Phase 4's `sim/__init__.py` quotes phase 1's 18 names exactly and adds 6. `size_picks` raising on a
stale pending order is never tripped by phase 4's scenario or benchmark, because each night sizes after `step` has
resolved that session's pending orders. Phase 2's `held` (live orders including pending, plus duplicates even after
an `lt_one_share` first copy) matches phase 1's `held_symbols()` and phase 4's night-1 `AAA` rejection. Every hand-worked
number in phase 4's scenario (days_held, gap precedence, time stop at the day-6 open across Thanksgiving 2025, fill at
the open when open < limit, the cash cap for III) matches the real `step` and `size_picks`. No symbol is deleted, so
there is no deleted-then-used. Phases 2 and 3 share no file. Every impact point and requirement has an owner.

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| API shape (handover §7) | Immutable frozen dataclasses plus pure functions in `seer_engine/sim/`. The portfolio holds only live orders; a terminal order is emitted once, in its event | 5: handover §7 recommendation + §6.2 determinism |
| Where `Bar` comes from without `psycopg` (§6.4 vs `bars.py:15`) | Move `Bar`, `PRICE_QUANTUM`, `to_decimal` to new `seer_engine/prices.py`, re-exported by `bars.py` | 1: invariants 2 + 3 |
| `days_held` counting | The fill session is day 1. An open position surviving a session gets +1, missing bar or not. An intraday exit (SL/TP) on session k records `days_held = k`. An exit **at the open** of session k (time, gap, gap-TP) records `days_held = k − 1`, because the position never traded in session k, so a time exit records 5 | 5: handover §3 "fill session is day 1", UI `day >= 5`, history label "Time exit, day 5" |
| Time stop condition | At the start of a session, an open position with `days_held >= 5` and a bar exits at that bar's open, reason `time`, before the gap/TP/SL checks | 5: handover §3 session order |
| Gap at open precedence | Time stop first, then `open <= SL` → exit at open reason `gap`, then `open >= TP` → exit at open reason `tp`, then intraday `low <= SL` → SL, then `high > TP` → TP | 5: handover §3 |
| Cash and `pnl_usd` rounding | Fill: `cash -= buy_cost(fill, sh)`. Exit: `cash += sell_proceeds(exit, sh)`. `pnl_usd = sell_proceeds − buy_cost`, so Σ pnl reconciles to cash exactly. This equals handover §3's formula up to ≤ 0.0001 rounding | 1: invariant 5, consistent with the §3 formula |
| Pending order whose `session_date` ≠ the stepped session | `step` raises `ValueError`. `step` also raises on a non-NYSE `session_date` (`dates.is_session`) and on `session_date <= portfolio.last_session` | 4: Why ("exactly as design §5"; holidays: no session) |
| Delisted/halted while held (§7) | No bar → no event, the day counts, marked at `marks`. A due time stop waits for the next bar's open. `close_unpriced(portfolio, symbols)` (called by P3/P4) exits at the mark, reason `time`, `forced=True`, `exit_date = portfolio.last_session`. A pending order with no bar expires | 5: handover §7 recommendation |
| Reverse-split rounding (§7) | `shares = floor(shares × factor)`. Cash in lieu = `q(fraction × adjusted mark)`, no cost, not in `pnl_usd`, amount on the `split` event. Prices `q(p / factor)`. A pending order flooring to 0 → `expire` event | 5: handover §7 recommendation |
| Split factor convention | `factor = split_to / split_from`, identical to `seer_engine.splits.Split.factor`. `apply_split` is called after session S−1's step and before stepping the split's execution session S | 6: convention (`splits.py:47`) |
| Sizing equity source | `portfolio.equity` (the last snapshot = the data_date close); `budget = min(q(equity / 4), cash − Σ buy_cost(limit, shares) of pending orders)`; `shares = floor(budget / (limit × 1.001))` | 5: handover §3 sizing row |
| Sizing order and slot choice | Picks are handled in the given order (the strategy's rank). Each placed pick takes the lowest free slot. Once slots run out, remaining picks are rejected `no_slot` | 6: convention; design §4 "fill free slots" |
| Performance (§7) | Keep `Decimal`. Benchmark test bound 20 s (CI-safe), measured time recorded in the readme | 5: handover §7 |
| Equity when a mark is missing at snapshot | Uses `marks` (the last known close). A position filled today is marked at today's close | 5: handover §3 equity row |
| Phase count | 4 phases. Phases 2 and 3 run in parallel after 1; 4 closes | — |
| Open position whose shares floor to 0 in a split (phase 3; e.g. a 1-for-32 reverse split on 20 shares) | The whole position is paid in lieu (`q(fraction × adjusted mark)`), removed, and reported as `Event(kind="exit", forced=True, cash_usd=in_lieu)`. The order stays in pre-split units: `status="closed"`, `exit_date` = the split session, `exit_price` = the pre-split mark, `exit_reason="time"`, `days_held` unchanged, `pnl_usd = in_lieu − buy_cost(fill, shares)`. The mark is dropped and `equity` is left at the last snapshot | 3: plan code blocks (phase 3's code + test; it passes phase 1's `Order` validation) plus 5: handover §7 (cash in lieu as brokers pay it; a forced close reads like `close_unpriced`) |
| Meaning of `Event.forced` and `pnl_usd` on a forced exit | `forced=True` means an exit at the last known close made without a bar, from `close_unpriced` or a split flooring an open position to 0. On every exit, `pnl_usd = event cash_usd − buy_cost(fill, shares)`, so Σ `pnl_usd` reconciles with cash. `close_unpriced` pays `sell_proceeds` (0.1% cost); the split payout is cash in lieu with no cost | 1: invariant 5 + the "Cash and `pnl_usd` rounding" row (Σ pnl reconciles to cash) |
| A split leaves prices 4 dp cannot hold (a rescaled price or mark rounds to 0, or SL rounds up to TP) | `apply_split` raises `ValueError` naming the symbol and slot before building anything, so the input portfolio is untouched. It does not expire a pending order or invent prices. This is unreachable for real listed stocks (the bracket would have to be narrower than 0.0001 × factor) | 3: plan code blocks (phase 1's `Order` validation already forbids those states; failing loudly keeps invariant 5's 4-dp rule) |
| `close_unpriced` and `equity` | `close_unpriced` recomputes `equity = q(cash + Σ shares × mark)` over what is still open. The caller persists a snapshot after it. `apply_split` leaves `equity` alone until the next `step` | 3: plan code blocks (phase 1 `close_unpriced`, phase 3 `apply_split`) |
| `step` event order | All exits (any reason) by slot, then all fills by slot, then all expiries by slot. Phase 4's scenario and readme assert and document exactly this | 2: phase 1 exit criteria / behavioural contract |
| "Held" for sizing | A pick is `held` when its symbol is in `Portfolio.held_symbols()` (every live order, pending included) or repeats an earlier pick in the same call, even when that earlier copy was rejected `lt_one_share`. `held` is checked before `no_slot`, and `no_slot` before `lt_one_share` | 3: plan code blocks (phase 1 `held_symbols`, phase 2 `size_picks` + tests) |
| `sim/__init__.py` `__all__` order | isort-style (ruff RUF022): UPPER_CASE constants, then CamelCase types, then functions, each alphabetical. Phase 4 checks it with that key | 3: plan code blocks (phase 1 writes it that way) |
| Test venv | The worktree's own `engine/.venv`, created by phase 1 Step 0 with `python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'`. Never the main checkout's venv | 1: invariant 1 (the suite must test this tree) + 5: handover §5 environment |

## Open Questions

(none)

## Rollback

Each phase is a commit on `feature/engine-fill-simulator`. Revert a phase with `git revert <sha>`.
Phases 2 and 3 are independent of each other, and phase 4 depends on both. Back the whole set out
by dropping the branch (`git worktree remove`, `git branch -D feature/engine-fill-simulator`).
Nothing touches the database, so there is no data rollback.

## Next

Run the whole set as a swarm (phases 2 and 3 run concurrently):

    /analyze-orchestrator -f ENGINE_FILL_SIMULATOR_PLAN.md

Or execute the phases one at a time, starting at phase 1:

    /implement -f ENGINE_FILL_SIMULATOR_PLAN.md --phase 1
