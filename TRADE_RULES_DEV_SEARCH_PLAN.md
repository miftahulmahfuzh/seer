# Plan: Trade rules as a value, a research store, and a pre-registered dev-window strategy search (P7a)

**Slug:** trade-rules-dev-search
**Date:** 2026-10-03 19:56 WIB
**Analysis:** `20261003-195606-T7R2_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/trade-rules-dev-search`
**Branch:** `feature/trade-rules-dev-search` (base: `origin/main` @ `2546a92`)
**Phases:** 13
**Status:** 6/13 phases complete (1, 2, 4, 5, 6, 7)
**Coordinator:** —

---

## Why

The specification is `docs/handover/2026-10-03-trade-rules-revision.md`, committed at `2546a92`.
Read all of it:
- the §3 tables ("Law", "What (c) opens", D1–D13, "Owner inputs" and "Owner facts") are binding;
- §7 is the acceptance list;
- §8's open questions are settled under **Decisions** below.

Its core, verbatim:

> The owner chose option **(c)**: revisit the design-§5 trade rules. The owner's words: *"open all
> options and approaches and possibilities and strategies … do not give up … let's take our time.
> slowly, but sure. there is no rush."*

> So yes, we are still trying to beat SPY buy-and-hold. Nothing in this handover lowers that bar.

> | D1 | **Split the work in two** | **P7a (this handover)** builds the machinery and explores **only on a development window**. It ends with a committed **pre-registration file** naming at most 3 finalists, each exactly specified. **P7b (a later handover)** runs those finalists **once** on the test window and applies the gate. P7a never runs a candidate on the test window |

> | D6 | **The search is wide but finite** | Before any dev run, P7a commits a **candidate registry** … **Size cap: 60 candidates.** Parameters are fixed per candidate … The registry may grow during P7a, but only by appending, and each append is committed **before** its dev run, with its own timestamp | … Appending is allowed; editing a candidate after seeing its result is not |

> | D8 | **How finalists are chosen** | … **Eligible:** beats SPY total-return over the dev window **and** max DD ≤ 15% **and** PF ≥ 1.3 **and** ≥ 100 closed trades **and** Gotrade-executable under the owner's verified answers. **Rank:** CAGR ÷ max DD (MAR), highest first. **Keep the top 3, at most one per strategy family** … **None eligible:** P7a's report says so, shows the frontier, and P7b does not run |

> **It does not move §1** to fit the date. **It does not hurry P7a.**

## Requirements

| ID | What the user asked for (handover §7) | Phases |
|---|---|---|
| R1 | `TradeRules`: `DESIGN_V0` reproduces §5, and A, A2 and B re-render byte-identically (synthetic test plus a real-data `cmp`). Each new lever has its own synthetic-bar tests | 1, 3, 13 |
| R2 | A research store command: pre-2015 member bars, the L9 ETFs, dividends from the start, unserved members per year, no Neon writes, deterministic, with a fingerprint | 4 |
| R3 | No look-ahead and P4 identity for every new family; the prepared and single-window paths agree | 2, 5, 6, 7, 8 |
| R4 | The dev window is enforced in code (no session after 2015-10-16), and a test proves it | 4, 9, 12 |
| R5 | The candidate registry is committed before the dev run: ≤ 60 entries, append-only, each with a family, rules, fixed params, a rationale and an owner-verification flag | 9, 11 |
| R6 | One dev run over every candidate, with the committed report holding every §7.6 section | 10, 12, 13 |
| R7 | The pre-registration file (≤ 3 finalists exactly specified, or "none eligible"), with the proposed §5 revision | 10, 13 |
| R8 | Determinism and purity: `==` results, byte-identical files, and the purity globs pass | 1, 2, 3, 9, 10, 12 |
| R9 | Docs (package readme, ROADMAP P7a and P7b). The suite is green with 0 skipped, and CI is green | 13 (each phase keeps the suite green) |

## Scope

**In scope:**
- New pure modules:
  - `sim/rules.py`, `sim/book.py`;
  - `strategies/allocator.py`, `strategies/f_index.py`, `strategies/f_rotation.py`,
    `strategies/f_factor.py`, `strategies/f_swing.py`;
  - `backtest/book_runner.py`, `backtest/dev.py`, `backtest/dev_report.py`, `backtest/registry.py`.
- New impure modules: `seer_engine/research.py`, `commands/research_store.py` and
  `commands/backtest_dev.py`.
- Their tests.
- Additive edits:
  - `sim/__init__.py` (exports);
  - `strategies/indicators.py` (new functions only);
  - `yahoo.py` (a dividends-aware downloader);
  - `backtest/io.py` (`dev_report_files`, `write_dev_report`, phase 12 only);
  - `.gitignore` (`engine/.research/`).
- The local, gitignored research store `engine/.research/`.
- The committed outputs:
  - `docs/backtests/<run date>-p7a-dev-exploration.md`, `-rows.csv`, `-curves.csv` and
    `-frontier.svg`;
  - `docs/plans/<run date>-p7b-preregistration.md`.
- `engine/package_readme.md` and `docs/ROADMAP.md`.

**Out of scope (handover §3 Law):**
- No edit to any of these (the frozen set):
  - `sim/model.py`, `sim/lifecycle.py`, `sim/sizing.py`, `sim/split_adjust.py`;
  - `backtest/runner.py`, `market.py`, `benchmark.py`, `metrics.py`, `walkforward.py`,
    `wf_report.py`, `report.py`, `tuning.py`, `labels.py`, `b_walkforward.py`, `b_report.py`;
  - `strategies/base.py`, `a.py`, `a2.py`, `b.py`, `b_model.py`;
  - `commands/backtest.py`, `backtest_wf.py`, `backtest_b.py`, `cli.py`;
  - `membership.py`, `fx.py`;
  - any existing test file;
  - `docs/backtests/2026-10-02-*`;
  - `docs/plans/2026-10-03-seer-design.md` (D10: the design edit happens in P7b).
- No Neon write and no migration. No change to `web/` or `.github/workflows/`.
- No test-window run of any candidate. No P7b, no P4 and no Strategy C.
- F8 (a learned ranker at a longer horizon) and F12 (earnings drift) are not in the first registry.
  See Decisions.

## Invariants

1. **The suite stays green.** At the end of every phase,
   `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
   passes with **0 skipped**. Run `docker start seer-pg` first.
   - Baseline on `2546a92`: **970 collected** (measured 2026-10-03 in a fresh worktree venv).
   - Each phase states the tests it adds and logs the passed count. A count that differs from
     its plan's number is a finding: name the missing or extra tests in the phase log. The
     reconciled count table (each plan's test functions and parametrizations recounted):

     | Phase | Adds | Test file(s) | Passed on 970 + its own adds | Cumulative (canonical landing order) |
     |---|---|---|---|---|
     | 1 | +91 | `test_sim_rules.py` (35), `test_sim_book.py` (56) | 1061 | 1061 |
     | 4 | +34 | `test_research_store.py` (29 functions, 34 items) | 1004 | 1095 (1 + 4) |
     | 2 | +55 | `test_allocator.py` | — | 1150 |
     | 3 | +47 | `test_book_runner.py` | — | 1197 |
     | 5 | +109 | `test_f_index.py` | — | 1306 |
     | 6 | +39 | `test_f_rotation.py` | — | 1345 |
     | 7 | +78 | `test_f_factor.py` | — | 1423 |
     | 8 | +87 | `test_f_swing.py` | — | 1510 |
     | 9 | +50 | `test_backtest_dev.py` | — | 1560 |
     | 10 | +32 | `test_backtest_dev_report.py` | — | 1592 |
     | 11 | +74 | `test_registry.py` (20 + 54 smoke cases) | — | 1666 |
     | 12 | +28 | `test_backtest_dev_command.py` (+2 more, 30, only if its Step 8 pool lands) | — | **1694** (1696 with the pool) |
     | 13 | +0 | (+ any Bug-protocol regression tests, each named) | — | **1694** |

     Phases 1 and 4 run concurrently; after phase 2, phases 3, 5, 6, 7 and 8 run concurrently. A
     session sees 970 plus whichever phases have merged into the branch when it starts, plus its
     own adds: compute the expected number from the "Adds" column, never from the cumulative
     column alone.
   - `engine/.venv` must be the **worktree's own** venv. The worktree already has one (built by
     `/analyze`). A session that finds it missing runs
     `python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'` from the
     worktree root.
   - Never use `/home/miftah/seer/engine/.venv`: it tests main's tree and lacks scikit-learn.
2. **Purity.**
   - Every module in `sim/`, `strategies/` and `backtest/` except `backtest/io.py` is pure.
     `tests/test_sim_purity.py` and `tests/test_strategy_purity.py` glob those directories, so
     new modules are covered without editing those tests.
   - Pure means: no psycopg, requests, yfinance, `seer_engine.bars`, `logging`, `time` or
     `random`, no `.now`/`.today`/`.random`, and no `print`/`open`.
   - New modules go **flat** in those directories, never in a sub-package (sub-packages are not
     globbed).
   - `seer_engine/research.py` and the commands are the impure edges.
3. **The closed records are untouched.** Every file in the frozen set above is byte-identical
   to `2546a92` at the end of every phase. Check with
   `git diff --stat 2546a92 -- <frozen paths>`, which must print nothing.
   - `DESIGN_V0` runs go through the **unchanged** `run_backtest`/`sim.step` path.
   - Byte-identity of A, A2 and B therefore holds by construction, and phase 13 proves it on
     real data.
4. **Read-only on Neon.** Nothing in P7a writes any Neon table. The research store is local
   files only.
5. **The test window stays fresh** (D1, D9).
   - The research store never contains a bar, dividend or FX row dated after
     `DEV_END = 2015-10-16`.
   - Every dev entry point rejects a later session.
   - No P7a artefact contains a number computed on a later session.
   - The single exception is phase 13's real-data `cmp` of the **closed** A, A2 and B reports.
     That re-renders existing records and runs no candidate.
6. **Determinism.**
   - The same inputs give `==` results and byte-identical files.
   - No unsorted set iteration reaches an output.
   - No wall-clock value appears inside a rendered file. The run date appears only in file
     names.
   - Candidates run sequentially, in registry order.
7. **No look-ahead.**
   - Targets for session S read bars through `prev_session(S)` only.
   - Signal exits and rebalances are decided at `prev_session(S)`'s close and executed at S's
     open.
   - Stops and take-profits are fixed at entry and never edited (the owner-input default).
8. **Decimal at the sim boundary.**
   - `Target` prices and weights, shares, cash and every money value in `sim/book.py` are
     `Decimal`.
   - Floats exist only in strategy features and metrics.
   - A float reaching a `Target` or the book is a `TypeError`.
9. **USD only.** No per-trade FX cost (handover "Owner facts"). Starting cash is
   `initial_cash_usd(20,000,000 IDR, usd_idr)` once, and everything after is USD.
10. Every handover §3 rule holds, and so does every row under **Decisions**.

## Shared interface contract (all phases plan against this)

```python
# ======================================================================================
# ---- seer_engine/sim/rules.py  (phase 1; pure; imports seer_engine.dates, re, decimal, dataclasses;
# ---- NOT sim.model: DESIGN_V0's agreement with the model constants is a test)
# ======================================================================================
Engine  = Literal["bracket_v0", "book"]
Cadence = Literal["daily", "weekly", "monthly"]
Entry   = Literal["limit", "open_limit", "open"]
OPEN_LIMIT_BAND = Decimal("0.02")    # open_limit buy limit = q(last × (1 + band)); also the sizing price for "open"
RESIZE_BAND     = Decimal("0.01")    # a held target is resized only when |Δ value| >= band × equity
SHARE_QUANTUM   = Decimal("0.0001")  # fractional share step (rules.fractional)
DEFAULT_ETFS: frozenset[str] = frozenset({"SPY", "QQQ"})   # owner-input conservative default: tradable ETFs
LEVERAGED_ETFS: frozenset[str] = frozenset({"SSO", "QLD", "UPRO", "TQQQ"})

@dataclass(frozen=True, slots=True)
class TradeRules:
    id: str                          # kebab-case, unique per preset, e.g. "design-v0", "monthly-hold"
    engine: Engine                   # "bracket_v0" ONLY for DESIGN_V0 (ValueError otherwise, both ways)
    cadence: Cadence = "daily"       # decision sessions: daily = every session; weekly = first session of each
                                     # ISO week; monthly = first session of each calendar month
    entry: Entry = "limit"           # limit: Target.limit; an UNHELD target with limit=None is bought exactly like
                                     # open_limit (D-B), a HELD one is never added to; never a ValueError;
                                     # open_limit: q(last × (1+OPEN_LIMIT_BAND)); open: market at the open (owner input)
    max_positions: int | None = None # cap on non-idle positions (parity with §5's 4 slots); None = targets decide
    time_stop: int | None = None     # exit at the next open once days_held >= time_stop (None = never)
    resize: bool = False             # on decision sessions, trade HELD non-idle targets back to weight (RESIZE_BAND)
    fractional: bool = False         # shares quantized DOWN to SHARE_QUANTUM instead of whole shares (owner input)
    dividends: bool = True           # credit cash dividends on the ex-date (D11)
    idle_symbol: str | None = None   # residual weight (1 − Σ targets) held in this instrument on decision sessions
    cost_rate: Decimal = Decimal("0.001")   # per side; != 0.001 is an owner input
    # __post_init__: types (TypeError), ints >= 1, cost_rate in [0, 0.05), id matches ^[a-z0-9]+(-[a-z0-9]+)*$ (ValueError);
    # engine "bracket_v0" only with every field equal to DESIGN_V0's, and id "design-v0" only with engine "bracket_v0"

DESIGN_V0 = TradeRules(id="design-v0", engine="bracket_v0", cadence="daily", entry="limit", max_positions=4,
                       time_stop=5, resize=False, fractional=False, dividends=False, idle_symbol=None,
                       cost_rate=Decimal("0.001"))
# DESIGN_V0.max_positions == model.SLOTS, .time_stop == model.TIME_STOP_DAYS, .cost_rate == model.COST_RATE (tested)
V0_BOOK = replace(DESIGN_V0, id="v0-book", engine="book")   # §5 replayed by the book engine: parity tests ONLY, never in the registry

# Presets used by the registry (phase 11 imports these names; values are fixed here):
MONTHLY_HOLD        = TradeRules(id="monthly-hold",  engine="book", cadence="monthly", entry="open_limit", resize=True)
MONTHLY_HOLD_TBILL  = replace(MONTHLY_HOLD, id="monthly-hold-tbill", idle_symbol="BIL")
WEEKLY_HOLD         = TradeRules(id="weekly-hold",   engine="book", cadence="weekly",  entry="open_limit", resize=True)
DAILY_SWITCH        = TradeRules(id="daily-switch",  engine="book", cadence="daily",   entry="open_limit", resize=False)
DAILY_SWITCH_TBILL  = replace(DAILY_SWITCH, id="daily-switch-tbill", idle_symbol="BIL")
SWING_T10           = TradeRules(id="swing-t10",     engine="book", cadence="daily",   entry="limit", time_stop=10)
SWING_T20           = replace(SWING_T10, id="swing-t20", time_stop=20)
SWING_T20_OPEN      = replace(SWING_T20, id="swing-t20-open", entry="open_limit")
PRESETS: tuple[TradeRules, ...] = (DESIGN_V0, MONTHLY_HOLD, MONTHLY_HOLD_TBILL, WEEKLY_HOLD, DAILY_SWITCH,
                                   DAILY_SWITCH_TBILL, SWING_T10, SWING_T20, SWING_T20_OPEN)   # ids unique (tested)

def is_decision_session(rules: TradeRules, session: date) -> bool
    # daily: True; weekly: session is the first NYSE session of its ISO (year, week); monthly: first NYSE session
    # of its (year, month). Uses seer_engine.dates (prev_session). ValueError if session is not an NYSE session.
def rule_owner_inputs(rules: TradeRules) -> tuple[str, ...]
    # sorted, unique: "market-on-open" if entry == "open"; "fractional" if fractional;
    # f"etf:{idle_symbol}" if idle_symbol not in DEFAULT_ETFS; "fee" if cost_rate != Decimal("0.001")
def describe_rules(rules: TradeRules) -> tuple[str, ...]
    # 11 fixed plain-English lines, one per field, in field order (reports and the pre-registration §5 text).
    # Exact wording is phase 1's; it is deterministic and covered by golden tests. A book rule set with
    # entry "limit" also states the D-B fallback (a new position with no limit price: last close + 2%).

# ======================================================================================
# ---- seer_engine/sim/book.py  (phase 1; pure; Decimal only; imports sim.model, sim.rules, prices, dates)
# ======================================================================================
WEIGHT_QUANTUM = Decimal("0.000001")

@dataclass(frozen=True, slots=True)
class Target:
    """One instrument the strategy wants held after the next session's open, in rank order."""
    symbol: str
    weight: Decimal                  # 0 < weight <= 1, a multiple of WEIGHT_QUANTUM (ValueError otherwise)
    last: Decimal                    # data_date close, 4 dp (q), > 0 — sizing and open_limit price
    limit: Decimal | None = None     # entry limit (rules.entry == "limit"), 4 dp, > 0
    stop: Decimal | None = None      # SL fixed at entry, 4 dp, > 0, < limit (or < last when limit is None)
    take: Decimal | None = None      # TP fixed at entry, 4 dp, > limit (or > last)
    # float anywhere -> TypeError; Decimal prices are quantized to 4 dp half-up (as sim.Pick). step_book checks
    # Σ weight <= 1 (ValueError) ONLY when rules.max_positions is None (D-A): with a slot cap, §5-style ranked
    # targets (PICKS: held + every pick at equal_weight(4)) may sum past 1 and the cap rejects the excess no_slot.

def to_weight(x: float | Decimal | int) -> Decimal   # quantize DOWN to WEIGHT_QUANTUM; floats via repr; ValueError if <= 0 after
def equal_weight(n: int) -> Decimal            # to_weight(Decimal(1) / n)

ExitReason = Literal["signal", "time", "gap", "tp", "sl", "forced"]
FillReason = Literal["entry", "add", "trim", "signal", "time", "gap", "tp", "sl", "forced"]
RejectReason = Literal["no_slot", "too_small", "unfilled", "no_bar", "cash"]

@dataclass(frozen=True, slots=True)
class Position:
    symbol: str
    shares: Decimal                  # > 0; integral unless rules.fractional
    mark: Decimal                    # last known close, 4 dp
    entry_date: date                 # first fill of this holding episode
    entry_price: Decimal             # first fill price
    days_held: int                   # sessions since the first fill (fill session = 1), exactly as sim.Order.days_held
    cost_usd: Decimal                # Σ buy cash paid in this episode (fees included)
    income_usd: Decimal              # Σ sell proceeds (partial trims) + dividends received in this episode
    stop: Decimal | None             # fixed at entry
    take: Decimal | None
    exit_pending: bool = False       # a signal exit decided on a session the symbol had no bar; sold at its next bar's open

@dataclass(frozen=True, slots=True)
class Book:
    cash: Decimal
    equity: Decimal                  # at the last snapshot (initial cash before the first session)
    positions: tuple[Position, ...] = ()   # sorted by symbol, one per symbol
    last_session: date | None = None
    def held(self) -> frozenset[str]
    def position(self, symbol: str) -> Position | None

@dataclass(frozen=True, slots=True)
class Fill:
    session_date: date
    symbol: str
    side: Literal["buy", "sell"]
    shares: Decimal
    price: Decimal                   # 4 dp
    cash_usd: Decimal                # signed: −buy cash, +sell proceeds (cost included)
    cost_usd: Decimal                # the fee part: q(price × shares × cost_rate)
    reason: FillReason

@dataclass(frozen=True, slots=True)
class Trade:
    """One closed holding episode: shares went 0 -> > 0 -> 0."""
    symbol: str
    entry_date: date
    exit_date: date
    entry_price: Decimal
    exit_price: Decimal              # the final sell's price
    days_held: int
    cost_usd: Decimal
    income_usd: Decimal              # sells + dividends
    pnl_usd: Decimal                 # income_usd − cost_usd (reconciles with cash exactly)
    exit_reason: ExitReason
    idle: bool                       # True for rules.idle_symbol episodes (excluded from trade statistics)

@dataclass(frozen=True, slots=True)
class BookSnapshot:
    date: date
    cash_usd: Decimal
    equity_usd: Decimal              # q(cash + Σ shares × mark)
    invested_usd: Decimal            # q(Σ shares × mark) over NON-idle positions (exposure numerator)

@dataclass(frozen=True, slots=True)
class BookStep:
    book: Book
    fills: tuple[Fill, ...]          # in execution order (below)
    trades: tuple[Trade, ...]        # episodes closed this session, in execution order
    dividends: tuple[tuple[str, Decimal], ...]   # (symbol, cash credited), by symbol
    rejected: tuple[tuple[str, RejectReason], ...]
    snapshot: BookSnapshot

def new_book(cash_usd: Decimal) -> Book        # cash = equity = q(cash_usd) > 0
def step_book(book: Book, session: date, bars: Mapping[str, Bar], targets: tuple[Target, ...] | None,
              rules: TradeRules, dividends: Mapping[str, Decimal] = <empty MappingProxyType>,
              idle_symbol_ok: bool = False) -> BookStep
    # rules.engine must be "book" (ValueError). session an NYSE session after book.last_session.
    # targets None  = not a decision session: no signal exits, no entries, no resizes.
    # targets ()    = decision session with nothing wanted: every non-idle position is signal-exited.
    # targets: a tuple (TypeError otherwise), unique symbols (ValueError), Σ weight <= 1 only without a cap (D-A).
    # idle_symbol_ok: False -> a target for rules.idle_symbol is a ValueError; the runner passes True exactly
    #   when it appended the residual idle target itself (6th positional = dividends, idle_symbol_ok keyword).
    # dividends: {symbol: amount per share} for ex-dates ON this session (the runner filters); validated
    #   (Decimal > 0) only when rules.dividends; symbols not held are ignored.
    # EXACT ORDER (all money Decimal, q() at every product, buy cash = q(p×n×(1+c)), sell = q(p×n×(1−c))):
    #  1. dividends (rules.dividends): each position held before S with an entry in `dividends`:
    #     cash += q(shares × amount); position.income_usd += that.
    #  2. open exits, positions in symbol order, only those with a bar on S:
    #       a. time_stop and days_held >= time_stop          -> sell all at open, "time", days_held unchanged
    #       b. stop and open <= stop                         -> sell all at open, "gap"
    #          take and open >= take                         -> sell all at open, "tp"
    #       c. (exit_pending) or (targets is not None and symbol not in targets) -> sell all at open, "signal"
    #     Sold this way -> no re-entry on S. A position with no bar on S that targets drop -> exit_pending=True.
    #  3. trims (targets not None and (rules.resize or symbol == rules.idle_symbol)), held targets with a bar,
    #     symbol order: desired = shares_for(book.equity × weight, last=target.last) (whole or fractional);
    #     if current > desired and (current − desired) × target.last >= RESIZE_BAND × book.equity:
    #     sell the difference at open, "trim". A trim to 0 shares closes the episode: Fill "trim",
    #     Trade.exit_reason "signal".
    #  4. buys, targets in RANK order (idle target last), for targets not held after step 2, plus held
    #     targets needing an "add" (same band rule as trims, upward; gated like trims: rules.resize or the idle
    #     symbol; a held target with no limit under entry "limit" is never added to). A target sold at S's
    #     open is skipped silently:
    #       - non-idle new entries beyond rules.max_positions -> rejected "no_slot" BEFORE sizing; the count is
    #         (positions held at the night before S) − (signal exits decided at night) + (entries sized > 0 so
    #         far, filled or not); a too_small entry takes no slot; exits at the open by rule (a/b) do NOT free a
    #         slot on S (exactly as sim: sizing happens the night before).
    #       - sizing price p = target.limit (entry "limit" with a limit), else q(last × (1+OPEN_LIMIT_BAND))
    #         (open_limit, open, and an unheld limit-less target under "limit": D-B).
    #       - budget = min(q(book.equity × weight), available − committed), where
    #           available = book.cash + Σ planned night sells (signal exits + trims decided at night, valued at
    #           q(last × shares × (1 − cost_rate)) with last = that target's or position's mark) and
    #           committed = Σ q(p × n × (1+c)) of buys placed earlier this session.
    #       - shares = whole: floor(budget / (p × (1+c))) with the sizing.py step-back loop;
    #                  fractional: quantize down to SHARE_QUANTUM. shares <= 0 -> "too_small".
    #       - fill: no bar on S -> "no_bar"; entry "open": at open; "limit"/"open_limit": fill when low < limit
    #         (STRICT) at min(open, limit), else "unfilled". At fill, if buy cash > current cash, reduce shares to
    #         what cash affords (same rounding); <= 0 -> "cash".
    #       - a new position: days_held = 1, stop/take from the target, entry_date = S, marked at the close;
    #         it is NOT checked against stop/take on S.
    #  5. intraday exits for positions held before S, not sold at the open, with a bar: low <= stop -> sell at stop
    #     "sl" (days_held + 1); else high > take -> sell at take "tp" (days_held + 1).
    #  6. survivors: days_held + 1 (bar or not), mark = close when there is a bar.
    #  7. snapshot. Fills in order: step-2 sells (symbol order), step-3 trims, step-4 buys (rank order), step-5 sells.
def close_book_unpriced(book: Book, symbols: Iterable[str], rules: TradeRules) -> tuple[Book, tuple[Fill, ...], tuple[Trade, ...]]
    # sell each named position at its mark, reason "forced", exit_date = book.last_session, days_held unchanged
    # (mirrors sim.close_unpriced); the returned Book's equity is recomputed q(cash + Σ shares × mark) and its
    # last_session is unchanged; every symbol must be held (ValueError); ValueError before any session stepped.
# PARITY (phase 3 test): run_book(PicksAllocator(STRATEGY_A …), V0_BOOK) reproduces run_backtest(STRATEGY_A, DESIGN_V0):
#   equal snapshot (date, cash, equity) sequences and equal closed-trade multisets (symbol, fill date, fill price,
#   exit date, exit price, sim reason, pnl). Sim reason map: tp->tp, sl->sl, gap->gap, time->time, forced->time+forced.

# sim/__init__.py (phase 1): additionally exports TradeRules, DESIGN_V0, V0_BOOK, the presets, PRESETS, Target,
# Book, Position, Fill, Trade, BookSnapshot, BookStep, new_book, step_book, close_book_unpriced, to_weight,
# equal_weight, is_decision_session, rule_owner_inputs, describe_rules, OPEN_LIMIT_BAND, RESIZE_BAND,
# SHARE_QUANTUM, DEFAULT_ETFS, LEVERAGED_ETFS, WEIGHT_QUANTUM. NOT re-exported: book.ExitReason/FillReason/
# RejectReason (sim.ExitReason and sim.RejectReason keep their model/sizing meaning). Nothing existing is
# removed or renamed.

# ======================================================================================
# ---- seer_engine/strategies/allocator.py  (phase 2; pure)
# ======================================================================================
@runtime_checkable
class Allocator(Protocol):
    """Maps history at data_date's close (plus what is held) to target weights for the next session."""
    id: str                                          # family id: "F1", "F2", …, "PICKS", "BLEND", "VOLTARGET"
    def lookback(self, params: Any) -> int           # bars of history each read symbol needs through data_date
    def symbols(self, params: Any) -> tuple[str, ...]   # fixed (non-member) symbols it READS, sorted, unique
    def holds(self, params: Any) -> tuple[str, ...]     # fixed symbols it may HOLD (⊆ symbols), sorted
    def uses_members(self, params: Any) -> bool         # True if it reads/holds index members
    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]
    def prepare(self, history: Mapping[str, History]) -> Any
    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]
# CONTRACT (P4 identity): targets_prepared(prepare(H), M, d, held, p) == targets({s: h.upto(d)}, M, d, held, p)
#   for every d, held and p, and reads only bars dated <= d. Targets are in rank order, unique symbols,
#   Σ weight <= 1 (except PICKS, D-A), every Target.last == q(to_decimal(last close <= d)). A symbol with no bar
#   dated d is never a NEW target (only a held one may be kept at its last close).
#   `held` (a frozenset; TypeError otherwise) lets a family keep a position it still wants (no signal exit);
#   held symbols the family does not return are signal-exited by the engine. The runner never includes
#   rules.idle_symbol in `held` (D-J). `members` is a collections.abc.Set.
#   prepare(history) takes no params and its value never depends on params (D-D): one prepared value per
#   allocator id serves every candidate using that allocator.

TRADING_DAYS = 252
def target_from_close(symbol: str, close: float | Decimal, weight: Decimal, *, limit: float | Decimal | None = None,
                      stop: float | Decimal | None = None, take: float | Decimal | None = None) -> Target | None
    # prices through prices.to_decimal then sim.q; None when any price is non-finite or <= 0 after rounding, or the
    # ordering stop < (limit or last) < take fails (the A._bracket convention); TypeError for a non-number; a bad
    # weight raises (through Target). Shared by every family.
def month_end_closes(h: History, data_date: date) -> np.ndarray
    # closes of the symbol's own last bar in each completed calendar month on or before data_date (every month
    # before data_date's; data_date's own month when next_session(data_date) is in a later month), ascending, float64.
def last_close(h: History | None, data_date: date) -> float | None   # close of the last bar dated <= data_date
def scale_weight(weight: Decimal, factor: Decimal) -> Decimal | None  # to_weight(w × f), None when it floors to 0
def vol_scale(signal: History | None, data_date: date, n: int, target_vol: Decimal) -> Decimal | None
    # min(1, target_vol / (stdev_return_window(last n+1 closes <= d) × sqrt(252))) as Decimal(repr(float));
    # None = do not scale (no history, < n+1 bars, zero/non-finite stdev, scale >= 1)
class LazyPrepared:   # .history, .of(inner): inner.prepare(history) on first use, cached by object identity
    ...               # the prepare() value of PICKS, BLEND and VOLTARGET (param-independent)

@dataclass(frozen=True, slots=True)
class PicksParams:
    strategy: Strategy           # a bracket Strategy (A, A2, B)
    params: Any                  # its params
    slots: int = 4               # weight = equal_weight(slots)
    def as_dict(self) -> dict[str, str]   # {"strategy", "slots", "params.<k>"…}
# isinstance(PICKS, Strategy) is False and isinstance(STRATEGY_A, Allocator) is False (run_rules dispatches on it).
class PicksAllocator:            # id "PICKS": adapter used by the V0_BOOK parity test only
    # targets: every held symbol (weight w, last = its close on d, no limit/stop/take) in symbol order, then EVERY
    # Pick in rank order whose symbol is not held (first occurrence only; never truncated to the free slots, D-A),
    # as Target(symbol, w, last=pick.last_price, limit=pick.limit_price, stop=pick.sl_price, take=pick.tp_price).
    # Σ weight may exceed 1: valid only with rules whose max_positions == slots (V0_BOOK). Held symbols without a
    # bar on d use last = their most recent close <= d (ValueError when there is none).
    # lookback = strategy.lookback; symbols/holds = (); uses_members True; prepare = LazyPrepared(history).
PICKS = PicksAllocator()

@dataclass(frozen=True, slots=True)
class BlendPart:
    allocator: Allocator
    params: Any
    share: Decimal               # (0, 1], multiple of WEIGHT_QUANTUM
@dataclass(frozen=True, slots=True)
class BlendParams:
    parts: tuple[BlendPart, ...] # >= 2 parts, Σ share <= 1
    def as_dict(self) -> dict[str, str]   # {"part<i>.allocator", "part<i>.share", "part<i>.<k>"…}
class BlendAllocator:            # id "BLEND" (F9 core + satellite)
    # each part i sees held_i = held − (∪_{j≠i} holds(part j)); its targets' weights × share, floored (zeros
    # dropped, never passed to to_weight); a symbol targeted by several parts gets the sum, ranked by first
    # appearance (part order, then rank), with the FIRST part's prices.
    # lookback = max; symbols = ∪ sorted; holds = ∪; uses_members = any. prepare = LazyPrepared(history).
BLEND = BlendAllocator()

@dataclass(frozen=True, slots=True)
class VolTargetParams:
    inner: Allocator
    inner_params: Any
    signal: str = "SPY"
    target_vol: Decimal = Decimal("0.12")   # annualized, > 0
    n: int = 20                             # >= 2
    def as_dict(self) -> dict[str, str]   # {"inner", "signal", "target_vol", "n", "inner.<k>"…}
class VolTargetAllocator:        # id "VOLTARGET" (L11)
    # scale = vol_scale(signal, d, n, target_vol); every inner weight × scale floored (targets that floor to 0
    # are dropped). No scale -> the inner tuple unchanged. lookback = max(inner, n + 1); symbols = inner ∪ {signal};
    # holds = inner's; prepare = LazyPrepared(history).
VOLTARGET = VolTargetAllocator()

# tests/allocatorkit.py (phase 2; THE kit, D-E; phases 5–8 call exactly these):
#   MembersFn = Callable[[date], AbstractSet[str]]; everyone(history); upto(history, d); tail(history, d, bars)
#   assert_valid_targets(targets, history, data_date, held, *, max_weight_sum=Decimal(1)) -> None
#   assert_p4_identity(allocator, history, members_fn, dates, held_sets, params, *,
#                      max_weight_sum=Decimal(1), check_lookback=True) -> int      # dates = data dates
#   assert_no_lookahead(allocator, history, members_fn, sessions, held_sets, params) -> int   # sessions S
#   held_sets and params: non-empty lists/tuples (a bare params value is a TypeError); both return the
#   non-empty-result count. Fakes: FIXED/FixedParams (id "FAKE_FIXED"), MOMENTUM/MomentumFake/MomentumParams
#   (id "FAKE_MOM").

# strategies/indicators.py (phase 2, additive only, same bit-identity conventions as the existing functions):
def return_window(close: np.ndarray, n: int, skip: int = 0) -> np.ndarray
    # (rows,) c[:, -1-skip] / c[:, -1-n] − 1 for (rows, W) windows; NaN rows when W < n + 1; requires 0 <= skip < n
# existing sma_window, wilder_rsi_window, wilder_atr_window, mean_dollar_volume_window, stdev_return_window are reused.

# ======================================================================================
# ---- seer_engine/backtest/book_runner.py  (phase 3; pure)
# ======================================================================================
DividendMap = Mapping[str, Mapping[date, Decimal]]   # symbol -> {ex_date: amount per share}
BOOK_EXIT_REASONS: tuple[str, ...] = ("tp", "sl", "time", "gap", "signal", "forced")   # RunStats.metrics.exit_reasons order
TRADING_DAYS = 252                                    # Sharpe annualization

@dataclass(frozen=True)
class BookResult:
    allocator_id: str
    params: Any
    rules: TradeRules
    start: date
    end: date
    usd_idr: Decimal
    initial_cash: Decimal
    snapshots: tuple[BookSnapshot, ...]   # [0] = BookSnapshot(prev_session(start), cash0, cash0, 0); then one per session
    fills: tuple[Fill, ...]
    trades: tuple[Trade, ...]             # exit order
    open_at_end: tuple[Position, ...]
    dividends_usd: Decimal
    costs_usd: Decimal                    # Σ Fill.cost_usd
    rejections: tuple[tuple[str, int], ...]   # by reason, sorted

def run_book(market: Market, allocator: Allocator, params: Any, rules: TradeRules, start: date, end: date, *,
             prepared: Any = None, dividends: DividendMap = <empty MappingProxyType>, initial_idr: Decimal = INITIAL_IDR,
             usd_idr: Decimal | None = None) -> BookResult
    # usd_idr None -> market.usd_idr_on(start). Per session S, data_date = prev_session(S):
    #   decision = is_decision_session(rules, S); if decision: members = membership.members_on(d);
    #   the allocator's held = book.held() − {rules.idle_symbol} (D-J: the idle position is the runner's);
    #   targets = allocator.targets_prepared(...) or allocator.targets({s: h.upto(d)}, ...);
    #   an allocator target for rules.idle_symbol -> ValueError (the idle weight is the runner's residual);
    #   rules.idle_symbol with a bar on d -> append Target(idle, to_weight(1 − Σw), last=its close) when > 0,
    #   and step_book(..., idle_symbol_ok=True) exactly then;
    #   bars = market.bars_on(S, book.held() ∪ target symbols); divs = {s: dividends[s][S]} for held symbols
    #   (only when rules.dividends); step_book; then close_book_unpriced for positions whose
    #   market.last_bar_date < S (snapshot replaced from the returned book).
    # rules.engine == "bracket_v0" -> ValueError (use run_rules).
def run_rules(market, strategy_or_allocator, params, rules, start, end, *, prepared=None, dividends={},
              usd_idr=None) -> RunResult | BookResult
    # rules == DESIGN_V0 and a strategies.base.Strategy -> run_backtest(market, strategy, params, start, end,
    #   prepared=prepared) UNCHANGED (usd_idr must be None or equal market.usd_idr_on(start), else ValueError;
    #   dividends are ignored); rules.engine == "book" and an Allocator -> run_book; any other pairing -> TypeError.

@dataclass(frozen=True)
class RunStats:
    """What the dev report needs from either result type."""
    metrics: Metrics              # RunResult: metrics.run_metrics unchanged; BookResult: strategy_metrics(snapshots,
                                  # pnls of NON-idle trades) + avg_days_held + exit_reasons in BOOK_EXIT_REASONS order
    exposure: float               # mean over sessions (snapshots[1:]) of invested / equity  (RunResult: (equity − cash)/equity)
    turnover: float               # Σ |fill notional| / mean equity / years (Actual/365.25); RunResult: Σ fill+exit notional
    costs_usd: float
    gross_pnl_usd: float          # Σ non-idle trade pnl + their costs
    cost_drag: float | None       # costs / gross when gross > 0 else None
    dividends_usd: float
    sharpe: float | None          # daily equity returns: mean / pstdev × sqrt(252); None when stdev == 0 or < 2 returns
    daily_returns: tuple[float, ...]
    year_returns: tuple[tuple[int, float], ...]   # calendar years, last-snapshot-to-last-snapshot
    worst_year: tuple[int, float] | None
def run_stats(r: RunResult | BookResult) -> RunStats

# ======================================================================================
# ---- seer_engine/research.py  (phase 4; IMPURE edge: yfinance, Frankfurter, files) + commands/research_store.py
# ======================================================================================
DEV_END = date(2015, 10, 16)               # == backtest.dev.DEV_END (tested in phase 12, D-I)
STORE_START = date(1993, 1, 29)            # SPY's first session
MEMBERSHIP_START = date(1996, 1, 2)        # == backtest.dev.MEMBERSHIP_START (duplicated: dev.py may not import research)
FX_START = date(1999, 1, 4)                # == backtest.dev.FX_START (tested in phase 12, D-I)
STORE_DIR = config.REPO_ROOT / "engine" / ".research"    # gitignored
RESEARCH_ETFS: tuple[str, ...] = ("BIL", "DIA", "EFA", "GLD", "IEF", "IWM", "QLD", "QQQ", "SHY", "SPY", "SSO",
    "TLT", "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")   # sorted; launch-limited by yfinance
SECTOR_ETFS: tuple[str, ...] = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")
# Store files (all text, LF, sorted, deterministic; prices at 4 dp exactly like `bars`):
#   bars.csv       symbol,date,open,high,low,close,volume   ORDER BY symbol, date; dates <= DEV_END
#   dividends.csv  symbol,ex_date,amount                    ORDER BY symbol, ex_date; amount Decimal as yfinance gives,
#                                                           normalized to at most 6 dp; ex_date <= DEV_END
#   fx.csv         date,usd_idr                             Frankfurter USD->IDR from 1999-01-04, <= DEV_END
#   unserved.csv   symbol,reason                            members (overlapping [1996-01-02, DEV_END]) yfinance returned nothing for
#   manifest.json  {"dev_end", "store_start", "symbols_requested", "symbols_served", "bar_rows", "dividend_rows",
#                   "fx_rows", "files": {name: sha256}, "fingerprint": sha256 of the sorted "name:sha" lines}
#                   json.dumps(sort_keys=True, indent=2) + "\n"; no timestamps.
@dataclass(frozen=True)
class ResearchData:
    market: Market                 # history from bars.csv (histories_from_frame), membership from
                                   # membership.compute_universe() via io.merge_intervals, fx from fx.csv
    dividends: dict[str, dict[date, Decimal]]   # symbol -> ex_date -> amount
    spy_dividends: tuple[Dividend, ...]         # SPY's, as benchmark.Dividend, ascending
    fingerprint: str
    manifest: Mapping[str, Any]
    unserved: tuple[str, ...] = ()              # additive (D-J): requested members with no bars, sorted
# (membership is clipped to the dev window: intervals overlapping [MEMBERSHIP_START, DEV_END], an end after
#  DEV_END becomes None, merged with io.merge_intervals)
def build_store(store_dir: Path, *, downloader=None, fetch_fx=None, sleep=time.sleep, batch_size=40,
                data_dir: Path | None = None) -> dict[str, Any]     # data_dir: additive (D-J), membership CSV dir
    # symbols = RESEARCH_ETFS ∪ every compute_universe() symbol whose interval overlaps [1996-01-02, DEV_END];
    # yfinance with auto_adjust=False AND actions=True (split-adjusted OHLC, cash dividends), end_exclusive =
    # DEV_END + 1 day; rows dated > DEV_END dropped defensively; throttled batches + rate-limit backoff like backfill;
    # an empty symbol gets one individual retry, then unserved.csv; an UNSERVED research ETF aborts the build
    # (ResearchStoreError); any download error or a rate-limit exhaustion aborts it; writes every file to a temp
    # dir then renames (all-or-nothing); returns the manifest.
def load_store(store_dir: Path, *, data_dir: Path | None = None) -> ResearchData
    # verifies the manifest, every file's sha256 and the fingerprint (ValueError on mismatch), that no row is
    # dated after DEV_END (ValueError) — the second, data-level guard of D9 — and the counts. A missing store is a
    # ValueError ("no research store").
# Also: ResearchStoreError(RuntimeError), Check(name, ok, detail), requested_symbols, research_membership,
# file_sha256, fingerprint_of, unserved_by_year, check_spy_sessions, check_spy_dividends, check_dividend_scale,
# run_checks; yahoo.py (additive): TickerHistory, EMPTY_HISTORY, yf_download_actions, download_actions,
# parse_frame_actions, frame_to_dividends, DIVIDENDS_COLUMN, DIVIDEND_QUANTUM.
# python -m seer_engine research_store [--store DIR] [--batch-size N] [--verify]   (honours the global --dry-run)
#   --verify: load_store only, run the three checks, print the fingerprint, counts and unserved-by-year (no network).
#   exit 0 ok; 1 build failed or a check failed; 2 store missing or invalid.

# ======================================================================================
# ---- families (phases 5–8; pure; each implements Allocator; each module exports ONE allocator singleton
# ---- per class and its params dataclass). Params are frozen dataclasses with __post_init__ validation and
# ---- an as_dict() -> dict[str, str] in fixed key order (report + pre-registration). ENCODING (D-F), every
# ---- family: a (symbol, n) pair -> "SYM:n"; None -> "none"; a tuple of symbols -> comma-joined sorted symbols;
# ---- numbers as plain decimals without trailing zeros; bools "true"/"false".
# ======================================================================================
# strategies/f_index.py (phase 5): F1 trend-timed index, F10 leveraged trend, F11 calendar
@dataclass(frozen=True, slots=True)
class TimingParams:
    hold: str                                  # the instrument held while "on" (SPY, QQQ, SSO, QLD)
    signal: str                                # the instrument whose own bars decide
    rule: Literal["sma", "month_sma", "abs_mom", "always"]
    n: int = 200                               # sma: signal close > SMA(n) of daily closes (strict);
                                               # month_sma: signal close > mean of the last n month_end_closes;
                                               # abs_mom: signal return over n sessions > 0 (strict); always: ignored
class TimingAllocator: id = "F1"               # on -> (Target(hold, weight 1), ) else (); hold needs a bar on d
    # signal without a bar on d = unknown: a HELD hold is kept at its latest close, else (); too little history
    # = off. lookback: sma n; abs_mom n+1; month_sma 23·n; always 1. symbols sorted({hold, signal}); holds (hold,).
TIMING = TimingAllocator()
@dataclass(frozen=True, slots=True)
class CalendarParams:
    hold: str
    days_before: int = 1                       # hold for the last k sessions of a month …
    days_after: int = 3                        # … and the first m sessions of the next month
    trend: tuple[str, int] | None = None       # also require trend[0] close > SMA(trend[1]) on d
class CalendarAllocator: id = "F11"            # the traded session is next_session(d); on iff it is one of those
    # the NYSE calendar is treated as known in advance (calendar data, not price data)
CALENDAR = CalendarAllocator()
# also public: IndexPrepared, above_sma, above_month_sma, positive_momentum, timing_state, turn_of_month,
# TIMING_RULES, MAX_SESSIONS_PER_MONTH = 23, MAX_CALENDAR_DAYS = 10, FULL_WEIGHT

# strategies/f_rotation.py (phase 6): F2 dual momentum, F3 sector rotation
@dataclass(frozen=True, slots=True)
class RotationParams:
    universe: tuple[str, ...]                  # sorted, >= 2 ETFs
    lookback: int                              # momentum = c[-1]/c[-1-lookback] − 1 (return_window, skip 0)
    top: int                                   # keep the top K by momentum (ties by symbol), weight equal_weight(top)
    absolute: bool = True                      # True: a slot is used only when that ETF's momentum > 0
    fallback: str | None = None                # unused slots go to this ETF (if it has a bar on d), else cash
    trend: tuple[str, int] | None = None       # all slots to fallback/cash unless trend[0] close > SMA(trend[1])
class RotationAllocator: id = "ROT"           # Candidate.family carries F2/F3
    # lookback = max(lookback + 1, trend n); symbols = universe ∪ fallback ∪ trend symbol; holds = universe ∪
    # fallback; held and members ignored; fallback gets equal_weight(top) × unused slots, ranked last
ROTATION = RotationAllocator()
# also public: RotationPrepared, rotation_targets, momentum_at, trend_on, NONE_TEXT

# strategies/f_factor.py (phase 7): F4 momentum, F5 low volatility, F6 momentum + low vol (members)
@dataclass(frozen=True, slots=True)
class FactorParams:
    rank: Literal["momentum", "lowvol", "mom_lowvol"]
    top: int = 10                              # holdings
    mom_n: int = 252
    mom_skip: int = 21                         # 12-1 momentum = return_window(c, mom_n, mom_skip)
    vol_n: int = 60                            # stdev_return_window(c, vol_n)
    pool: int = 50                             # mom_lowvol: the `pool` highest-momentum names, then the `top` lowest vol
    sizing: Literal["equal", "inverse_vol"] = "equal"   # inverse_vol: w_i ∝ 1/vol_i, to_weight-floored
    min_dollar_volume: float = 20_000_000.0    # 20-day mean close×volume > this (strict), as A
    min_price: float = 5.0                     # close >= min_price
    trend: tuple[str, int] | None = ("SPY", 200)   # all cash unless trend[0] close > SMA(trend[1]) on d
    # eligible on d: member on d, symbol not "SPY", a bar dated d, >= lookback bars through d, finite features.
    # ranking ties broken by symbol ascending. Held symbols are kept only if they rank in the new top (rebalance).
class FactorAllocator: id = "FAC"; FACTOR = FactorAllocator()
# lookback = max(mom_n + 1, vol_n + 1, 20, trend n); symbols = (trend[0],) or (); holds = (); prepare is
# param-independent (FactorPrepared builds each (mom_n, skip) / vol_n column lazily, cached).
# also public: DV_N, EXCLUDED, MAX_TOP, FactorRow, FactorPrepared, prepare_factor, factor_lookback, factor_rows,
# trend_on, rank_rows, factor_weights, targets_from_rows

# strategies/f_swing.py (phase 8): F7 longer-horizon mean reversion (members)
@dataclass(frozen=True, slots=True)
class SwingParams:
    slots: int = 4                             # weight equal_weight(slots); keep + new <= slots (self-capped)
    rsi_n: int = 2
    rsi_max: float = 10.0                      # entry setup: RSI(rsi_n) < rsi_max (strict) and close > SMA(sma_n)
    sma_n: int = 200
    entry: Literal["dip", "close"] = "dip"     # Target.limit: dip = close − limit_atr × ATR14; close = close
    limit_atr: Decimal = Decimal("0.5")
    stop_atr: Decimal | None = Decimal("2.5")  # Target.stop = limit − stop_atr × ATR14 (None: no stop)
    take_atr: Decimal | None = None            # Target.take = limit + take_atr × ATR14 (None: no TP)
    exit_sma: int | None = 5                   # signal exit when close > SMA(exit_sma) (strict)
    exit_rsi: float | None = None              # … or when RSI(rsi_n) > exit_rsi
    min_dollar_volume: float = 20_000_000.0
    market_trend: tuple[str, int] | None = None   # no NEW entries unless market_trend[0] close > SMA(n); held kept
    # targets = kept held (no exit signal, or no bar on d) in symbol order with no prices, then new candidates by
    # (RSI asc, symbol) until slots are full. Held symbols that left the index are still kept until they exit.
class SwingAllocator: id = "F7"; SWING = SwingAllocator()
# lookback = max(member_window = max(200, sma_n, rsi_n + 1, exit_sma), market_trend n); symbols = (trend[0],) or ();
# holds = (); kept targets capped at `slots`; prepare is param-independent (default periods vectorized, other
# periods served by the single-window path on prepared.history).
# also public: WINDOW, ATR_N, DV_N, MAX_SLOTS, PREPARED_*, SwingFeatures, features_at, SwingPrepared, prepare_swing,
# member_window, swing_lookback, has_setup, has_exit_signal, entry_target, rank_entries, trend_on

# ======================================================================================
# ---- seer_engine/backtest/dev.py  (phase 9; pure)
# ======================================================================================
DEV_END = date(2015, 10, 16)
MEMBERSHIP_START = date(1996, 1, 2)            # first sp500_history.csv row
FX_START = date(1999, 1, 4)                    # first Frankfurter USD/IDR row (verified 2026-10-03)
MAX_CANDIDATES = 60
FAILURE_LABELS = ("beats SPY TR", "max DD <= 15%", "PF >= 1.3", ">= 100 trades", "owner inputs")   # additive
class DevWindowError(ValueError): ...
def check_dev_session(d: date) -> None         # DevWindowError when d > DEV_END
# D9, data level too: candidate_window, run_candidate and run_registry raise DevWindowError for a market holding
# any bar or FX row after DEV_END; run_candidate/run_registry also for any dividend after it. dev.py never
# imports seer_engine.research (tested).
@dataclass(frozen=True)
class Candidate:
    id: str                                    # unique, ^[A-Z0-9]+(-[A-Z0-9]+)*$
    family: str                                # "F1".."F11", "REF"
    rules: TradeRules
    allocator: Allocator | Strategy            # Strategy only with DESIGN_V0
    params: Any
    rationale: str                             # one line
    added: date                                # the registry append date (D6 timestamp)
    owner_inputs: tuple[str, ...]              # declared, sorted unique; must equal candidate_owner_inputs(self)
                                               # (registry test); D8 always uses the COMPUTED value
    # __post_init__: id/family patterns, DESIGN_V0 <-> Strategy (not an Allocator), book rules <-> Allocator
    # (TypeError), one-line rationale, `added` a date
def candidate_owner_inputs(c: Candidate) -> tuple[str, ...]
    # sorted unique: rule_owner_inputs(c.rules) ∪ {f"etf:{s}" for s in holds(params) if s not in DEFAULT_ETFS}
    # ∪ {"leverage" if holds ∩ LEVERAGED_ETFS}. Empty tuple = executable under the conservative defaults.
def candidate_window(market: Market, c: Candidate) -> tuple[date, date]
    # (start, DEV_END): start = first NYSE session S such that every symbol in symbols(params) ∪ {"SPY"} has
    # >= lookback(params) bars through prev_session(S); if uses_members(params) also prev_session(S) >= MEMBERSHIP_START.
    # DESIGN_V0 Strategy candidates: symbols = {"SPY"}, lookback = strategy.lookback, uses_members True.
    # rules.idle_symbol is NOT part of the rule (idle cash earns 0% until it has a bar). A missing or short symbol
    # -> ValueError; a start after DEV_END -> DevWindowError.
@dataclass(frozen=True)
class DevRow:
    candidate: Candidate
    start: date; end: date
    stats: RunStats
    spy_tr: Metrics; spy_price: Metrics          # benchmark.spy_curves on the SAME window and cash, store SPY dividends
    beats_spy: bool                              # stats.metrics.total_return > spy_tr.total_return
    mar: float | None                            # cagr / max_drawdown (None when DD == 0 or cagr None)
    eligible: bool
    failed: tuple[str, ...]                      # subset, in this order: "beats SPY TR", "max DD <= 15%", "PF >= 1.3",
                                                 # ">= 100 trades", "owner inputs" (thresholds = tuning.MAX_DRAWDOWN/MIN_PROFIT_FACTOR)
def make_row(candidate, start, end, stats, *, spy_tr, spy_price) -> DevRow   # additive: the one place D8 lives
def run_candidate(market, dividends, spy_dividends, c, *, prepared=None) -> tuple[RunResult | BookResult, DevRow]
    # D9 checks before anything; run_rules on candidate_window with rate = market.usd_idr_on(max(start, FX_START));
    # a window starting before FX_START runs on a COPY of the market whose fx is the single row (start, rate)
    # (D-C; windows are never clamped), so run_backtest's usd_idr_on(start) == rate; DESIGN_V0 gets dividends={}.
def run_registry(market, dividends, spy_dividends, registry: Sequence[Candidate], *,
                 on_result: Callable[[int, RunResult | BookResult, DevRow], None] | None = None) -> tuple[DevRow, ...]
    # sequential, registry order, <= MAX_CANDIDATES, unique ids; prepare(market.history) once per allocator.id
    # (a strategy's id for DESIGN_V0), dropped after its last use; two DIFFERENT objects sharing an id ->
    # ValueError before anything runs (D-D). on_result (additive) is called after each candidate: phase 12 takes
    # the result's snapshots and times each candidate from it.
def finalists(rows: Sequence[DevRow]) -> tuple[DevRow, ...]
    # D8: eligible rows ranked by (−mar, candidate.id), rows with mar None after every row with a MAR (then by id);
    # keep the first row of each family until 3 rows.
def deflated_sharpe(sharpe_daily: float, n_trials: int, var_trials: float, t: int, skew: float, kurt: float) -> float | None
    # Bailey & López de Prado (2014): SR* = sqrt(var_trials) × ((1−γ)·Φ⁻¹(1−1/N) + γ·Φ⁻¹(1−1/(N·e))), γ = 0.5772156649;
    # DSR = Φ((SR − SR*)·sqrt(t−1) / sqrt(1 − skew·SR + (kurt−1)/4·SR²)); statistics.NormalDist; None when undefined
    # (n_trials < 2, t < 2, var < 0, a non-finite input, a non-positive radicand). SR and var_trials are DAILY
    # (per-period); kurt is non-excess.

# ======================================================================================
# ---- seer_engine/backtest/dev_report.py  (phase 10; pure)
# ======================================================================================
@dataclass(frozen=True)
class DevReport:
    run_date: date                     # appears in FILE NAMES only, never in rendered content
    store_fingerprint: str
    store_counts: Mapping[str, int]    # bar_rows, symbols_served, symbols_requested, dividend_rows, fx_rows
    unserved: tuple[str, ...]
    survivorship: tuple[YearGap, ...]  # runner.survivorship(market, MEMBERSHIP_START, DEV_END)
    registry_digest: str               # sha256 of backtest/registry.py's source bytes
    rows: tuple[DevRow, ...]           # registry order
    finalists: tuple[DevRow, ...]
    spy_window: tuple[date, date]      # the earliest candidate start .. DEV_END, for the SPY curves section
    spy_price: BenchmarkCurve
    spy_tr: BenchmarkCurve
    top_years: tuple[tuple[str, tuple[tuple[int, float], ...]], ...]   # up to 5 rows: the finalists first (finalist
                                                                       # order), then the highest MAR by (−MAR, id) (D-G)
    curves: tuple[tuple[str, tuple[tuple[date, float], ...]], ...]     # month-end equity per candidate (normalized to 1.0)
    dsr: tuple[tuple[str, float | None], ...]                          # per finalist (or for the best-Sharpe row if none)
# no extra field, no default; phase 12 builds it; every renderer validates it first (_validate: ValueError).
TEST_START = date(2015, 10, 19); TEST_SLICE_START = date(2018, 1, 2); MIN_TRADES = 100; MAX_FINALISTS = 3; TOP_YEARS = 5
STORE_COUNT_KEYS = ("bar_rows", "symbols_requested", "symbols_served", "dividend_rows", "fx_rows")
FAIL_ORDER = FAILURE_LABELS (verbatim)
ROWS_CSV_HEADER = "id,family,allocator,rules,start,end,total_return,cagr,max_drawdown,profit_factor,trades,exposure,
                   turnover,cost_drag,costs_usd,dividends_usd,sharpe,worst_year,worst_year_return,spy_tr_total_return,
                   spy_tr_cagr,spy_price_total_return,mar,beats_spy,eligible,finalist,failed,owner_inputs"
                   # floats at 6 dp, "inf" for an infinite PF, "" for None, lists ";"-joined, CSV-quoted when needed
def report_stem(run_date: date) -> str                       # f"{run_date.isoformat()}-p7a-dev-exploration"
def preregistration_name(run_date: date) -> str              # f"{run_date.isoformat()}-p7b-preregistration.md"
# The run date appears only inside sibling-file NAMES (links); the registry's `added` dates are rendered as data.
def render_markdown(r: DevReport) -> str
def rows_csv(r: DevReport) -> str                            # one line per candidate, fixed columns
def curves_csv(r: DevReport) -> str                          # month-end, one column per candidate + spy_price + spy_tr
def frontier_svg(r: DevReport) -> str                        # CAGR (y) vs max DD (x); SPY TR marked; 15% DD line;
                                                             # finalists labelled; deterministic SVG text
def render_preregistration(r: DevReport) -> str              # exact finalist specs or "none eligible" (see phase 10)

# ======================================================================================
# ---- seer_engine/backtest/registry.py  (phase 11; pure)
# ======================================================================================
SECTOR_ETFS: tuple[str, ...]           # == research.SECTOR_ETFS (tested in phase 12, D-I; registry.py may not import research)
FIRST_APPEND: date                     # the `added` date of entries 1–54 (the phase-11 commit date)
REGISTRY: tuple[Candidate, ...]        # the table under "Registry" below, in that order, len <= 60
def candidate_text(c: Candidate) -> str     # canonical "key=value" lines: id, family, EVERY TradeRules field,
                                            # allocator id, params walked recursively over dataclass fields
                                            # (compare=True, declaration order; allocators/strategies as <id>)
def candidate_digest(c: Candidate) -> str   # sha256 of candidate_text (NOT of params.as_dict(); rationale, added and
                                            # owner_inputs excluded)
# tests/test_registry.py pins (id, digest) for every entry; the tuple may only grow (append + pin in one commit).

# ======================================================================================
# ---- seer_engine/backtest/io.py (phase 12; additive) + commands/backtest_dev.py (phase 12)
# ======================================================================================
def dev_report_files(out_dir: Path, plans_dir: Path, report: DevReport) -> tuple[tuple[Path, str], ...]   # additive
    # every file rendered, nothing written (the --only path)
def write_dev_report(out_dir: Path, plans_dir: Path, report: DevReport) -> list[Path]
    # <stem>.md, <stem>-rows.csv, <stem>-curves.csv, <stem>-frontier.svg into out_dir and the pre-registration into
    # plans_dir; everything rendered before anything is written; LF.
# python -m seer_engine backtest_dev [--store DIR] [--out DIR] [--plans DIR] [--run-date YYYY-MM-DD] [--only ID ...]
#   refuses (exit 2) when backtest/registry.py has uncommitted changes (git status --porcelain on that path; an
#   untracked file or a git failure also refuses) unless --only is given (a smoke run: renders in memory, writes
#   nothing, logs the full-run estimate); exit 2 also for a missing/rejected store or an unknown --only id;
#   never takes an --end (argparse rejects it). Runs the registry through dev.run_registry(on_result=...) (D-D)
#   and times every candidate from the callback; wall times go to the log only.
#   Public: HELP, add_arguments, run, DEFAULT_OUT, DEFAULT_PLANS, REGISTRY_PATH, TOP_YEARS, STORE_COUNT_KEYS,
#   BacktestDevError, Timing(candidate_id, estimate_class, seconds), load_registry, registry_problem,
#   registry_digest, select, read_unserved, store_counts, estimate_class, month_end_curve, top_years,
#   daily_moments, deflated_sharpes, run_candidates, execute, estimate_full_run. --workers N and a fixed-order
#   process pool exist only if phase 12's measured estimate exceeds 60 min (D13).
```

**Allocator ids are `F1`, `F11`, `ROT`, `FAC`, `F7`, `PICKS`, `BLEND` and `VOLTARGET`.** The
catalogue family (F1–F11, REF) lives on `Candidate.family`.

## Registry (phase 11 encodes exactly this; `added` = the phase-11 commit date)

Notation:
- `T(h,s,rule,n)` = `TimingParams(hold=h, signal=s, rule=rule, n=n)`.
- `ROT(u,lb,top,abs,fb,trend)` = `RotationParams`.
- `FAC(...)` = `FactorParams` (only the fields that differ from the defaults are listed).
- `SW(...)` = `SwingParams` (only the fields that differ from the defaults are listed).
- `SEC` = `SECTOR_ETFS`.

Owner inputs are computed by `candidate_owner_inputs`. A non-empty set cannot become a finalist
(D8).

| # | ID | Family | Allocator(params) | Rules | Rationale (one line) |
|---|---|---|---|---|---|
| 1 | REF-SPY-HOLD | REF | TIMING T(SPY,SPY,always,1) | MONTHLY_HOLD | Sanity reference: SPY held with dividends should track SPY TR minus whole-share cash drag |
| 2 | REF-A-V0 | REF | STRATEGY_A, a.DESIGN_PARAMS | DESIGN_V0 | A's idea under the closed §5 rules on fresh data: is A's failure specific to 2015–2026? |
| 3 | F1-SPY-SMA200-D | F1 | TIMING T(SPY,SPY,sma,200) | DAILY_SWITCH | The classic drawdown cutter, checked nightly |
| 4 | F1-SPY-SMA200-M | F1 | TIMING T(SPY,SPY,sma,200) | MONTHLY_HOLD | Same signal, monthly: fewer whipsaws |
| 5 | F1-SPY-SMA100-D | F1 | TIMING T(SPY,SPY,sma,100) | DAILY_SWITCH | A faster filter cuts crashes sooner |
| 6 | F1-SPY-SMA50-D | F1 | TIMING T(SPY,SPY,sma,50) | DAILY_SWITCH | Fastest filter; more trades, more whipsaw |
| 7 | F1-SPY-10MSMA-M | F1 | TIMING T(SPY,SPY,month_sma,10) | MONTHLY_HOLD | Faber's 10-month rule |
| 8 | F1-SPY-ABS12-M | F1 | TIMING T(SPY,SPY,abs_mom,252) | MONTHLY_HOLD | 12-month absolute momentum (vs 0, T-bills unavailable by default) |
| 9 | F1-SPY-SMA200-D-TBILL | F1 | TIMING T(SPY,SPY,sma,200) | DAILY_SWITCH_TBILL | Idle cash in T-bills (BIL from 2007) |
| 10 | F1-QQQ-SMA200-D | F1 | TIMING T(QQQ,QQQ,sma,200) | DAILY_SWITCH | Tech-led index adds return in bull eras |
| 11 | F1-QQQ-SMA200-M | F1 | TIMING T(QQQ,QQQ,sma,200) | MONTHLY_HOLD | Monthly variant |
| 12 | F1-QQQ-SMA100-D | F1 | TIMING T(QQQ,QQQ,sma,100) | DAILY_SWITCH | QQQ's faster crashes need a faster filter |
| 13 | F1-QQQ-SPYSIG-D | F1 | TIMING T(QQQ,SPY,sma,200) | DAILY_SWITCH | Hold QQQ, time on the broader market |
| 14 | F1-QQQ-10MSMA-M | F1 | TIMING T(QQQ,QQQ,month_sma,10) | MONTHLY_HOLD | 10-month rule on QQQ |
| 15 | F1-SPY-VT12-W | F1 | VOLTARGET(TIMING T(SPY,SPY,sma,200), SPY, 0.12, 20) | WEEKLY_HOLD | Trend filter plus 12% vol targeting |
| 16 | F1-QQQ-VT15-W | F1 | VOLTARGET(TIMING T(QQQ,QQQ,sma,200), QQQ, 0.15, 20) | WEEKLY_HOLD | QQQ with 15% vol targeting |
| 17 | F10-SSO-SMA200-D | F10 | TIMING T(SSO,SPY,sma,200) | DAILY_SWITCH | 2× S&P only above trend (owner: leverage) |
| 18 | F10-QLD-SMA200-D | F10 | TIMING T(QLD,QQQ,sma,200) | DAILY_SWITCH | 2× Nasdaq only above trend (owner: leverage) |
| 19 | F10-SSO-10MSMA-M | F10 | TIMING T(SSO,SPY,month_sma,10) | MONTHLY_HOLD | Leveraged 10-month rule |
| 20 | F11-SPY-TOM | F11 | CALENDAR CalendarParams(SPY,1,3,None) | DAILY_SWITCH | Turn-of-month effect: low exposure, low DD |
| 21 | F11-SPY-TOM-TREND | F11 | CALENDAR CalendarParams(SPY,1,3,(SPY,200)) | DAILY_SWITCH | Turn of month, only above trend |
| 22 | F11-QQQ-TOM-TREND | F11 | CALENDAR CalendarParams(QQQ,1,3,(QQQ,200)) | DAILY_SWITCH | Turn of month on QQQ above trend |
| 23 | F2-SPYQQQ-12M | F2 | ROTATION ROT((QQQ,SPY),252,1,True,None,None) | MONTHLY_HOLD | Dual momentum with default ETFs only |
| 24 | F2-SPYQQQ-6M | F2 | ROTATION ROT((QQQ,SPY),126,1,True,None,None) | MONTHLY_HOLD | Faster lookback |
| 25 | F2-SPYQQQ-3M | F2 | ROTATION ROT((QQQ,SPY),63,1,True,None,None) | MONTHLY_HOLD | Fastest lookback |
| 26 | F2-SPYQQQ-12M-IEF | F2 | ROTATION ROT((QQQ,SPY),252,1,True,IEF,None) | MONTHLY_HOLD | Bonds instead of cash when risk-off (owner: IEF) |
| 27 | F2-GEM-SPYEFA-IEF | F2 | ROTATION ROT((EFA,SPY),252,1,True,IEF,None) | MONTHLY_HOLD | Classic GEM: US vs international, else bonds (owner: EFA, IEF) |
| 28 | F3-SEC-TOP3-6M | F3 | ROTATION ROT(SEC,126,3,True,None,None) | MONTHLY_HOLD | Sector leadership with an absolute filter (owner: sector ETFs) |
| 29 | F3-SEC-TOP3-12M | F3 | ROTATION ROT(SEC,252,3,True,None,None) | MONTHLY_HOLD | 12-month lookback |
| 30 | F3-SEC-TOP2-3M | F3 | ROTATION ROT(SEC,63,2,True,None,None) | MONTHLY_HOLD | Short lookback, concentrated |
| 31 | F3-SEC-TOP3-6M-TREND | F3 | ROTATION ROT(SEC,126,3,True,None,(SPY,200)) | MONTHLY_HOLD | Plus a market trend filter |
| 32 | F3-SEC-TOP3-6M-IEF | F3 | ROTATION ROT(SEC,126,3,True,IEF,None) | MONTHLY_HOLD | Unused slots in bonds |
| 33 | F4-MOM12-N10 | F4 | FACTOR FAC(momentum, top=10, trend=None) | MONTHLY_HOLD | Plain 12-1 momentum, no filter |
| 34 | F4-MOM12-N10-TREND | F4 | FACTOR FAC(momentum, top=10) | MONTHLY_HOLD | Momentum with a SPY 200-day filter |
| 35 | F4-MOM12-N20-TREND | F4 | FACTOR FAC(momentum, top=20) | MONTHLY_HOLD | More names, lower DD |
| 36 | F4-MOM12-N5-TREND | F4 | FACTOR FAC(momentum, top=5) | MONTHLY_HOLD | Concentrated |
| 37 | F4-MOM6-N10-TREND | F4 | FACTOR FAC(momentum, top=10, mom_n=126) | MONTHLY_HOLD | 6-1 momentum |
| 38 | F4-MOM12-N10-TREND-IVOL | F4 | FACTOR FAC(momentum, top=10, sizing=inverse_vol) | MONTHLY_HOLD | Vol-scaled sizing (L3) |
| 39 | F4-MOM12-N10-TREND-W | F4 | FACTOR FAC(momentum, top=10) | WEEKLY_HOLD | Weekly re-ranking |
| 40 | F5-LV60-N20 | F5 | FACTOR FAC(lowvol, top=20, trend=None) | MONTHLY_HOLD | Least-volatile large caps |
| 41 | F5-LV60-N20-TREND | F5 | FACTOR FAC(lowvol, top=20) | MONTHLY_HOLD | Plus the trend filter |
| 42 | F5-LV252-N20-TREND | F5 | FACTOR FAC(lowvol, top=20, vol_n=252) | MONTHLY_HOLD | Year-long volatility |
| 43 | F6-ML-P50-N10-TREND | F6 | FACTOR FAC(mom_lowvol, top=10, pool=50) | MONTHLY_HOLD | Momentum among calmer names |
| 44 | F6-ML-P50-N20-TREND | F6 | FACTOR FAC(mom_lowvol, top=20, pool=50) | MONTHLY_HOLD | Broader |
| 45 | F6-ML-P50-N10-VT12 | F6 | VOLTARGET(FACTOR FAC(mom_lowvol, top=10, pool=50), SPY, 0.12, 20) | WEEKLY_HOLD | Plus vol targeting |
| 46 | F7-RSI2-T20-DIP | F7 | SWING SW() | SWING_T20 | A's idea, longer horizon, no TP, signal exit |
| 47 | F7-RSI2-T10-DIP | F7 | SWING SW() | SWING_T10 | Shorter horizon |
| 48 | F7-RSI2-T20-CLOSE | F7 | SWING SW(entry=close) | SWING_T20 | Limit at the close: less adverse selection |
| 49 | F7-RSI2-T20-OPEN | F7 | SWING SW() | SWING_T20_OPEN | Enter at the open (marketable limit) |
| 50 | F7-RSI2-T20-N8 | F7 | SWING SW(slots=8) | SWING_T20 | More, smaller positions |
| 51 | F7-RSI2-T20-TREND | F7 | SWING SW(market_trend=(SPY,200)) | SWING_T20 | No new entries in a down market |
| 52 | F7-RSI2-T20-NOSTOP | F7 | SWING SW(stop_atr=None) | SWING_T20 | No stop: exits by signal or time only |
| 53 | F9-SPY200M70-MOM30 | F9 | BLEND((TIMING T(SPY,SPY,sma,200), 0.7), (FACTOR FAC(momentum, top=10), 0.3)) | MONTHLY_HOLD | Timed SPY core, momentum satellite |
| 54 | F9-SPY200D50-SWING50 | F9 | BLEND((TIMING T(SPY,SPY,sma,200), 0.5), (SWING SW(), 0.5)) | SWING_T20 | Timed SPY core, swing satellite in the idle half |

That makes 54 candidates. 6 more may be appended during P7a (D6), each committed before its run.

Row 54 runs under `SWING_T20` (entry `limit`) as written: its TIMING core's SPY target carries no
limit price, and the book engine buys an unheld limit-less target exactly like `open_limit` (D-B).
The swing preset's 20-session time stop applies to the SPY core too (it is sold and re-bought); that
is the registered behaviour and the docs report it.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 ✓ | `TradeRules` + the book engine | R1, R8 | `sim` | 5 | — | HARD | `.workflows/plan/trade-rules-dev-search/phase-1.md` | P1-ENG-OY9Z | — |
| 2 ✓ | Allocator protocol, adapters, overlays, `return_window` | R3, R8 | `strategies` | 4 | 1 | NORMAL | `.workflows/plan/trade-rules-dev-search/phase-2.md` | P1-ENG-XORE | — |
| 3 | Book runner, `run_rules` dispatch, run stats, V0 parity | R1, R8 | `backtest` | 2 | 1, 2 | HARD | `.workflows/plan/trade-rules-dev-search/phase-3.md` | P1-ENG-CPHN | — |
| 4 ✓ | Research store: build, load, verify, command, real build | R2, R4 | root, `commands` | 5 (+ the gitignored store) | — | HARD | `.workflows/plan/trade-rules-dev-search/phase-4.md` | P1-ENG-CQ5M | — |
| 5 ✓ | Families F1/F10/F11: index timing and calendar | R3 | `strategies` | 2 | 2 | NORMAL | `.workflows/plan/trade-rules-dev-search/phase-5.md` | P1-ENG-ZNTC | — |
| 6 ✓ | Families F2/F3: ETF rotation | R3 | `strategies` | 2 | 2 | NORMAL | `.workflows/plan/trade-rules-dev-search/phase-6.md` | P1-ENG-76SL | — |
| 7 ✓ | Families F4/F5/F6: stock factors | R3 | `strategies` | 2 | 2 | HARD | `.workflows/plan/trade-rules-dev-search/phase-7.md` | P1-ENG-SB1Q | — |
| 8 | Family F7: longer-horizon mean reversion | R3 | `strategies` | 2 | 2 | NORMAL | `.workflows/plan/trade-rules-dev-search/phase-8.md` | P1-ENG-5U7B | — |
| 9 | Dev runner: window guard, candidate windows, D8, deflated Sharpe | R4, R5, R8 | `backtest` | 2 | 3 | HARD | `.workflows/plan/trade-rules-dev-search/phase-9.md` | P1-ENG-2E01 | — |
| 10 | Dev report and pre-registration renderers | R6, R7, R8 | `backtest` | 2 | 9 | HARD | `.workflows/plan/trade-rules-dev-search/phase-10.md` | P1-ENG-PLRV | — |
| 11 | The candidate registry (54 entries, append-only test) | R5 | `backtest` | 2 | 5, 6, 7, 8, 9 | NORMAL | `.workflows/plan/trade-rules-dev-search/phase-11.md` | P1-ENG-078U | — |
| 12 | `backtest_dev` command, io writer, runtime on the real store | R4, R6, R8 | `commands`, `backtest` | 3 | 4, 10, 11 | NORMAL | `.workflows/plan/trade-rules-dev-search/phase-12.md` | P1-ENG-ZWP9 | — |
| 13 | The real dev run, report, pre-registration, V0 `cmp`, docs | R1, R6, R7, R9 | `docs` | 8 | 12 | NORMAL | `.workflows/plan/trade-rules-dev-search/phase-13.md` | P1-ENG-904W | — |

Concurrency: phases 1 and 4 start together; after phase 2, phases 3, 5, 6, 7 and 8 run
concurrently; 9 follows 3; 10 follows 9; 11 waits for 5–9; 12 for 4, 10 and 11; 13 for 12. Every
dependency points backward.

### Phase 1 — `TradeRules` + the book engine
**Satisfies:** R1 (rules as a value; the lever tests at engine level), R8.
**Owns:** `sim/rules.py` and `sim/book.py` (new, exactly as contracted); additive exports in
`sim/__init__.py`; `tests/test_sim_rules.py` (35) and `tests/test_sim_book.py` (56) (new). There is
one synthetic-bar test (or more) per lever:
- signal exit at the next open, including a missing bar (`exit_pending`);
- rebalance with trims and adds under `RESIZE_BAND`;
- dividends on the ex-date;
- fractional shares;
- `open` and `open_limit` entries (including an open gapping above the band, which goes unfilled);
- the `limit` entry, and its D-B fallback for an unheld target with no limit price (bought like
  `open_limit`; a held limit-less target is never added to);
- `max_positions` ≠ 4, and Σ weight > 1 accepted only under a slot cap (D-A);
- time stop 10/20/None;
- vol-scaled weights (unequal weights sized correctly);
- the idle T-bill target;
- the cash guard;
- `close_book_unpriced`;
- episode P&L reconciling with cash exactly;
- a session-by-session replay of `size_picks` + `step` under `V0_BOOK`.

**Does not touch:** `sim/model.py`, `lifecycle.py`, `sizing.py`, `split_adjust.py`, and anything
outside `sim/`.
**Exit criteria:** the suite is green with 0 skipped (+91). `test_sim_purity.py` covers both new
modules. `DESIGN_V0` agrees with the `model` constants (tested). The V0 replay passes for 3 seeds.

### Phase 2 — Allocator protocol, adapters, overlays, `return_window`
**Satisfies:** R3 (the contract and its test kit), R8.
**Owns:**
- `strategies/allocator.py` (new): `Allocator`, `target_from_close`, `month_end_closes`,
  `last_close`, `scale_weight`, `vol_scale`, `LazyPrepared`, `PicksAllocator`, `BlendAllocator`
  and `VolTargetAllocator`.
- `strategies/indicators.py`: additive `return_window`.
- `tests/test_allocator.py` (new, 55), with the reusable P4-identity/no-look-ahead kit that
  phases 5–8 import: `tests/allocatorkit.py` (new; its API is the contract's, D-E).

**Does not touch:** existing indicator functions, `base.py`, `a.py`, `a2.py`, `b.py`,
`strategies/__init__.py`.
**Exit criteria:** the suite is green. The purity glob covers `allocator.py`. The P4 identity of
`PicksAllocator`, `BlendAllocator` and `VolTargetAllocator` is tested with fake inner allocators;
the kit rejects a look-ahead fake, a broken prepared path and a too-short lookback.

### Phase 3 — Book runner, `run_rules` dispatch, run stats, V0 parity
**Satisfies:** R1 (the `DESIGN_V0` dispatch is identical to `run_backtest` for A, A2 and B on
synthetic markets; the V0_BOOK parity), R8.
**Owns:** `backtest/book_runner.py` (new) and `tests/test_book_runner.py` (new, 47).
**Does not touch:** `runner.py`, `metrics.py` and `benchmark.py` (imported read-only).
**Exit criteria:** the suite is green. These are proven on seeded synthetic markets:
- `run_rules(..., DESIGN_V0) == run_backtest(...)`, for A, A2 and B (with a fake predictor);
- `run_book(PICKS(A), V0_BOOK)` matches the `run_backtest` snapshots, trades, fills and open
  positions exactly (seeds 39 and 4, plus the hand-checked FixedPicks scenario);
- the allocator never sees the idle position in `held` (D-J);
- `run_stats` is hand-checked on small books.

### Phase 4 — Research store
**Satisfies:** R2, R4 (the data-level guard).
**Owns:**
- `seer_engine/research.py` (new);
- `commands/research_store.py` (new);
- additive `yahoo.py` (a dividends-aware download/parse);
- `.gitignore` (`engine/.research/`, `.research.tmp/`, `.research.old/`);
- `tests/test_research_store.py` (new, 34 items, with a fake downloader and a fake FX fetcher).

It also does **the real build** into the worktree's `engine/.research/` (a 30–60 min background
task), with the counts and the fingerprint logged in the phase log. It verifies:
- SPY has a bar on every NYSE session from 1993-02-01 to `DEV_END`;
- yfinance SPY dividends equal `engine/data/spy_dividends.csv` on the overlap
  2015-03-20 → 2015-10-16;
- one split-adjusted dividend (AAPL 2012) is consistent with the split-adjusted price scale.

**Does not touch:** `membership.py`, `fx.py`, `backfill.py`, Neon. The equality of its duplicated
constants with `backtest.dev`'s is tested in phase 12 (D-I).
**Exit criteria:** the suite is green. A re-run of `build_store` on the same fake downloads
gives byte-identical files and the same fingerprint. `load_store` rejects a tampered file and a
row after `DEV_END`. `research_store --verify` exits 0 on the real store.

### Phase 5 — Families F1/F10/F11
**Satisfies:** R3. **Owns:** `strategies/f_index.py` (new) and `tests/test_f_index.py` (new, 109).
The tests cover hand-checked signals (SMA, month-end SMA, absolute momentum, always, the
turn-of-month calendar around month ends and holidays), P4 identity, and no look-ahead, locally and
through the phase-2 kit (D-E).
**Depends on:** 2. **Exit criteria:** the suite is green and the purity glob covers the module.

### Phase 6 — Families F2/F3
**Satisfies:** R3. **Owns:** `strategies/f_rotation.py` (new) and `tests/test_f_rotation.py`
(new, 39). The tests cover the momentum ranking with ties, the absolute filter, the fallback, the
trend filter, ETFs that are missing or short, P4 identity, and no look-ahead (locally and through
the kit).
**Depends on:** 2. **Exit criteria:** the suite is green.

### Phase 7 — Families F4/F5/F6
**Satisfies:** R3. **Owns:** `strategies/f_factor.py` (new; vectorized, param-independent
`prepare` like `prepare_a`) and `tests/test_f_factor.py` (new, 78). The tests cover:
- 12-1 momentum, vol and dollar-volume eligibility, hand-computed;
- mom_lowvol pool selection;
- inverse-vol weights summing to ≤ 1;
- the trend filter;
- members only, and SPY excluded;
- P4 identity with bit-identity between the prepared and single-window features;
- no look-ahead (locally and through the kit).

**Depends on:** 2. **Exit criteria:** the suite is green.

### Phase 8 — Family F7
**Satisfies:** R3. **Owns:** `strategies/f_swing.py` (new) and `tests/test_f_swing.py` (new, 87).
The tests cover:
- the setup and the dip/close limits;
- stop and take from ATR;
- the signal exits (SMA and RSI);
- the self-capped slots with keep-first ordering;
- held symbols that left the index;
- the market-trend gate for new entries only;
- P4 identity and no look-ahead (locally and through the kit).

**Depends on:** 2. **Exit criteria:** the suite is green.

### Phase 9 — Dev runner
**Satisfies:** R4 (the code guard and its test), R5 (the `Candidate` type and its owner inputs),
R8.
**Owns:** `backtest/dev.py` (new) and `tests/test_backtest_dev.py` (new, 50). The tests cover:
- `DevWindowError` on any end, session, bar, FX row or dividend after 2015-10-16, from every
  public entry point;
- `candidate_window` across ETF launches and the membership start;
- a window starting before 1999-01-04 converting at the `FX_START` rate (D-C);
- D8 selection, including the one-per-family rule, ties and `mar is None` ranked last;
- deflated Sharpe against hand-computed cases;
- `run_registry` order, determinism, one prepare per allocator id and the `on_result` callback.

**Depends on:** 3. **Exit criteria:** the suite is green.

### Phase 10 — Dev report and pre-registration renderers
**Satisfies:** R6 (content), R7 (the file's content), R8.
**Owns:** `backtest/dev_report.py` (new) and `tests/test_backtest_dev_report.py` (new, 32). The
tests use structural checks and byte-stability.
**Depends on:** 9. **Exit criteria:** the suite is green. Two renders are byte-identical.
Rendered content contains no run date outside sibling-file names. `top_years` lists the finalists
first (D-G).

### Phase 11 — The candidate registry
**Satisfies:** R5. **Owns:** `backtest/registry.py` (new) and `tests/test_registry.py` (new, 74).
The tests cover:
- the ids are unique and the first 54 are the table above, in order (row 54 under `SWING_T20`);
- there are ≤ 60 entries;
- the (id, digest) pins are append-only;
- the declared owner inputs equal `candidate_owner_inputs`;
- every rules preset is valid for its allocator;
- every candidate runs one short smoke window on a synthetic market (every fixed symbol, BIL and
  the leveraged ETFs included) through `run_candidate`.

**Depends on:** 5, 6, 7, 8, 9. **Exit criteria:** the suite is green, and the registry is
committed (the commit precedes any real dev run). Its agreement with `research` is phase 12's test.

### Phase 12 — `backtest_dev` command, io writer, runtime
**Satisfies:** R4 (the `research` ↔ `dev` constant-equality test, D-I), R6 (the pipeline), R8.
**Owns:**
- `commands/backtest_dev.py` (new), running the registry through `dev.run_registry(on_result=…)`
  (D-D);
- additive `backtest/io.py` (`dev_report_files`, `write_dev_report`);
- `tests/test_backtest_dev_command.py` (new, 28): includes the D-I tests (`research.DEV_END`,
  `MEMBERSHIP_START`, `FX_START` equal `dev`'s; `registry.SECTOR_ETFS == research.SECTOR_ETFS`;
  registry fixed symbols ⊆ `research.RESEARCH_ETFS`), on a synthetic store whose fake downloader
  serves every research ETF.

It also does **a timed `--only` smoke run** on the real store, with no docs written. If the
estimated whole-run time exceeds 60 min, it adds a fixed-order process pool (D13; +2 tests).
**Depends on:** 4, 10, 11. **Exit criteria:** the suite is green at 1694 (1696 with the pool), and
the command's dirty-registry refusal is tested.

### Phase 13 — The real dev run, report, pre-registration, V0 `cmp`, docs
**Satisfies:** R1 (the real-data `cmp`), R6, R7, R9.
**Owns:**
- the committed report set and pre-registration file;
- an identical re-run (`cmp`);
- the real-data `cmp` of `docs/backtests/2026-10-02-*` (see Decisions for the condition);
- `engine/package_readme.md`;
- `docs/ROADMAP.md` (the P7a entry with the result, and the P7b entry);
- one appended Decisions row here (the R1 outcome).

It never stops to ask (D-H): a missing store is rebuilt, a differing fingerprint is recorded and
the run proceeds, and a defect fixable only in `registry.py` or a frozen file ends the phase with the
run not committed and a note in the phase log and the completion summary.
**Depends on:** 12. **Exit criteria:** every handover §7 item is checked off in the phase log. The
suite is green with 0 skipped (1694, plus only Bug-protocol tests). CI is green.

## Reconciliation Log

| # | Conflict | Class | Phases | Resolution |
|---|---|---|---|---|
| 1 | Σ weight ≤ 1 in `step_book` (contract) vs. `PICKS` emitting held + every pick at `equal_weight(4)` (needed for §5 parity) | Contract drift / behavioral fork | 1, 2, 3, index | D-A: Σ ≤ 1 checked only when `max_positions is None`; PICKS uncapped. Phase 1 already did it; index contract line, phase 2 Decision 2/H1 and phase 3 N1/H5 rewritten as settled |
| 2 | Registry row 54 (`SWING_T20`, entry `limit`) cannot run: the TIMING core's SPY target has no limit, and phase 1 raised `ValueError`; phase 11 had moved the row to `SWING_T20_OPEN` | Behavioral fork | 1, 3, 8, 11, index | D-B: the engine buys an unheld limit-less target under `limit` exactly like `open_limit`; held ones are never added to. Phase 1's `_check_targets` limit check removed, `_sizing_price` falls back, `describe_rules` states the fallback, one new test (`test_sim_book.py` 55 → 56). Phase 11 row 54 back to `SWING_T20`, comment dropped, `PRICED_ENTRY_LEAVES` gains `F1` |
| 3 | REF-A-V0 (`DESIGN_V0`) starts ~1996, before the first FX row; phase 3 H1 and phase 12 told phase 9 to clamp or patch; phase 9 already used a single-row FX market copy | Unmet assumption | 3, 9, 12 | D-C: phase 9's approach stands (no clamping); phase 3 H1 and phase 12's handoff and Step 7 rewritten to it; phase 12's smoke still includes REF-A-V0 |
| 4 | Prepare-cache keying: phase 11 claimed `allocator.id` is wrong for BLEND/VOLTARGET; phase 12 re-implemented the loop with its own `(module, qualname, id)` key | Duplicate work / contract drift | 2, 9, 11, 12 | D-D: `LazyPrepared` makes every `prepare` param-independent, so `allocator.id` is correct; phase 12 now calls `dev.run_registry(on_result=…)` (one keying rule), times candidates from the callback (`Timing(candidate_id, estimate_class, seconds)`), drops `prepare_key`/separate prepare timings; estimate and log tests rewritten; Step 8 pool keyed by `allocator.id` |
| 5 | Phases 5, 6, 7, 8 called assumed kit APIs (`check_allocator`, `assert_contract`, `assert_no_look_ahead`, `check_identity`/`check_no_look_ahead`) that phase 2 does not ship | Unmet assumption | 2, 5, 6, 7, 8 | D-E: phase 2's kit is canonical; the kit-using tests rewritten to `assert_p4_identity` / `assert_no_lookahead` with list `held_sets` and `params` (test counts unchanged) |
| 6 | `as_dict` encodings of `(symbol, n)`, `None` and symbol tuples left open across families; phase 11's digest vs. the index's "digest over `params.as_dict()`" | Contract drift | 2, 5–8, 10, 11, index | D-F: `"SYM:n"`, `"none"`, comma-joined sorted symbols (all plans already conform); the digest walks dataclass fields (phase 11 kept); index contract updated |
| 7 | `top_years`: index "top 5 by MAR" vs. phase 12 "finalists first, then MAR" | Contract drift | 10, 12, 13, index | D-G: finalists first, then highest MAR, up to 5; index contract, phase 10 Decision 2 and phase 13 Step 4a aligned |
| 8 | Phase 13 told the session to "stop and ask the caller" (missing store, fingerprint differs, no phase-4 fingerprint, registry/frozen-file bug, worktree ≠ 2546a92) | Gap (unattended launch) | 13 | D-H: each replaced by a decision (rebuild / proceed and log both / adopt `--verify`'s value / end the phase with the run not committed and a note); phase 12's Step 7 fingerprint precondition made non-blocking the same way |
| 9 | Equality tests of `research` vs. `dev` constants: phase 4 assigned them to phase 9 (which does not depend on 4); phase 9 handed them to 12; registry ↔ research ETF agreement handed to 12 by phase 11 but not written there | Gap / duplicate assignment | 4, 9, 11, 12 | D-I: all in phase 12's test file (`test_research_and_dev_constants_agree`, new `test_registry_reads_only_research_etfs`; 27 → 28); phase 4's note and handoff corrected; phase 12 `Satisfies` gains R4 (the step serves it; the index Requirements table updated) |
| 10 | `ResearchData.unserved` and the `data_dir` keyword are additions to the index contract | Contract drift (additive) | 4, 12, index | D-J: accepted and folded into the index contract |
| 11 | `run_book` handed allocators `held = book.held()`, which includes the idle BIL position; F7/PICKS keep every held symbol, so they would re-target BIL beside the runner's residual (a duplicate symbol) | Contract drift | 3, 8, index | D-J: `run_book` passes `held − {rules.idle_symbol}`; one new test (`test_book_runner.py` 46 → 47); phase 8 handoff marked settled |
| 12 | Phase 12's synthetic store served only SPY and QQQ, but phase 4 aborts a build that leaves any research ETF unserved; phase 12 also expected `FileNotFoundError` for a missing store (phase 4 raises `ValueError`) | Unmet assumption / broken-build test | 4, 12 | The fixture serves all 21 research ETFs (the other 19 from 2010-01-04); phase 12's Requires corrected (the command already maps both exceptions to exit 2) |
| 13 | Phase 13's run-date scan would flag the sibling-file links and a registry `added` date equal to the run date; phase 10 asked for masking | Gap | 10, 13 | `p7a_dates.py` masks the two stems and the `added` cells/lines before the run-date check |
| 14 | Phase 13 expected a separate preparation time and wrote readme text that disagrees with the plans (`sim.rules` importing `sim.model`, no fallback, Σ ≤ 1 for PICKS, research_store exit codes, `build_store`/`load_store` signatures) | Contract drift | 1, 4, 12, 13 | `{{PREPARE_S}}` dropped (per-candidate times include the first prepare); readme blocks corrected to the plans |
| 15 | Phase 3 notes N2–N14 (adds gated like trims, `no_slot` before sizing, forced reasons, `Book.equity` recomputed after a forced close, positional/keyword args, `idle_symbol_ok`) | Verification | 1, 3 | All checked against phase 1's plan code and hold; N1/N4/N7 reworded to the settled D-A/D-B/D-J semantics |
| 16 | `finalists` with `mar is None` (phase 10 feared a crash) | Verification | 9, 10 | Phase 9 already ranks `None` last, then by id; phase 10's ranking matches; phase 10's handoff rewritten |
| 17 | Phase 10's `_validate` vs. phase 12's `DevReport` construction (spy curves span, curves order, dsr per finalist, `top_years` ≤ 5, sorted `unserved`) | Verification | 10, 12 | Holds as written: `spy_curves` snapshot 0 is `prev_session(start)`, snapshot 1 is `start` |
| 18 | Phase 13's expected filenames and CSV columns vs. phase 10 | Verification | 10, 13 | Stems and `ROWS_CSV_HEADER` names match `p7a_facts.py`'s `COLS`; phase 10's "(10) tests" note was a misread of the phase number and is corrected |
| 19 | Phase 11's smoke market vs. every fixed symbol | Verification | 11 | Covers BIL, EFA, IEF, QLD, SSO, QQQ, SPY and the 9 sector SPDRs (every symbol the registry reads or holds) |
| 20 | Test counts per phase unreconciled; phases 1/4 and 3/5–8 concurrent | Gap | all | Count table under Invariant 1: +91, +55, +47, +35, +109, +39, +78, +87, +50, +32, +74, +28, +0; final 1695 (1697 with the conditional pool). Phases 1, 3, 12 and 13 state absolute counts |
| 21 | Phase table: phase 4 "6 files" (5 committed + the gitignored store), phase 13 "6–8" | Contract drift | index | Phase 4: 5 (+ the gitignored store); phase 13: 8 (5 generated + readme + ROADMAP + this index) |
| 22 | Stale cross-phase notes ("the reconciler may align …", phase 7's "FAC prepared twice", phase 10's "overlays have no `as_dict`") | Contract drift | 2, 5, 6, 7, 8, 10, 11 | Rewritten to the settled state |
| 23 | Round 2: phase 4's test file holds 29 functions (27 plain, one ×4 over `DATA_FILES`, one ×3) = **34** items, not 30/35 (AST recount of every plan's test blocks; all other phases match their stated adds) | Contract drift (count) | 1, 3, 4, 12, 13, index | Phase 4 → +34 (1004 alone); every cumulative count −1: 1095, 1150, 1197, 1306, 1345, 1423, 1510, 1560, 1592, 1666, final **1694** (1696 with the pool). Phase 1 (1095 with phase 4), phase 3 (1197), phase 12 and 13 (1694/1696) and the index table, phase 4/12/13 sections updated. Row 20 above is the round-1 state |
| 24 | Round 2: phase 6 text said 21 test functions; its code has 22 (21 plain + one ×18 = 39 items, unchanged) | Contract drift (text) | 6 | Text corrected to 22; the +39 count stands |
| 25 | Round 2: phase 4's frozen-set check diffed the whole `backtest/` directory, which prints phase 3's new `book_runner.py` whenever phase 4 runs after phase 3 (sequential `/implement` order) | Broken-build phase (false failure) | 4 | The check now names the frozen `backtest/` files (plus `io.py`, untouched until phase 12) instead of the directory |
| 26 | Round 2 verification: every cross-phase import (228 names/attributes) exists in its producer's plan code or the repo; `step_book`, `close_book_unpriced`, `run_candidate`, `run_registry(on_result=…)`, `DevReport` fields and the CLI flags agree between producer and callers; no plan keeps the losing side of D-A…D-J or the five extra forks; Open Questions empty; Status planned | Verification | all | Holds as written |

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| One generalized simulator vs. the existing one plus a new path (handover §8) | Keep `sim.step`/`run_backtest` **untouched** for `DESIGN_V0`. One new pure engine, `sim/book.py`, serves every non-default rule set (bracket-style and rebalance alike). `run_rules` dispatches. A V0_BOOK parity test proves the new engine replays §5 exactly | 1: invariant "closed records" (D2 byte-identity is then true by construction); handover §8 recommendation |
| Where each §4.A lever lives | Execution levers (L1 time stop, L4 entry, L5 exit structure via `Target` stop/take plus signal exits, L6 cadence, L7 idle, L8 dividends, L12 cost, fractional) are in `TradeRules`. Selection levers (L2 slot count, L3 sizing, L9 universe, L10 exposure switch, L11 vol targeting) are in allocator params or overlays, because they are functions of history. `max_positions` exists only for §5 parity | 4: the handover's Why (the rules must be executable and identical live); 6: convention (`Strategy` already owns selection) |
| Strategy interface for the new engine | `Allocator.targets(history, members, data_date, held, params)`. `held` is added to the handover's sketch so that a family can keep a position without the engine resizing or exiting it | 6: convention (P4 knows the holdings at night); needed for F7 and F9 |
| What counts as a "closed trade" | A holding episode (shares 0 → > 0 → 0), with dividends inside its P&L. Idle-instrument episodes are not trades. Trims and adds do not create trades; a trim to 0 shares closes the episode with exit reason `signal` | 1: Law (thresholds unchanged, so trades cannot be inflated by counting partial lots) |
| Monthly single-ETF switchers and the ≥ 100-trade rule | Not bent. Such candidates are likely ineligible on trades. The dev report states plainly that §1's trade count excludes low-turnover designs by construction, as owner evidence | 1: Law (§1 thresholds unchanged) |
| Market-on-open under the "limit orders only" default | `open_limit` = a buy limit at last close + 2%. It is a limit order, so it is executable by default. True `open` entries are flagged `market-on-open` | 1: owner-input defaults table |
| Sale proceeds at an open funding buys at the same open | Allowed, sized at night from the planned sells at last close. A fill-time cash guard shrinks any buy cash does not cover | 6: convention (US cash accounts allow buying with unsettled proceeds; holds are long) |
| "No TP" in Gotrade | Executed as a bracket with a far TP. Modelled as `take=None`, with no owner flag | 6: design §2 (Gotrade brackets exist; a far TP is a valid bracket) |
| Signal exits and trims | At the next open, as a sell. Never an intraday or nightly stop edit | 1: owner-input default ("signal exits and rebalances happen at most once a day, as a market or limit sell at the next open") |
| Research store format | Plain sorted CSV at 4 dp (the `bars` convention) plus `manifest.json` with per-file sha256 and a fingerprint, in `engine/.research/` (gitignored). No parquet (no pyarrow dependency) | 1: acceptance R2 (deterministic, fingerprinted); D5 (local, not Neon) |
| Test-window freshness, data-level | The store never holds a row after `DEV_END`, and `load_store` rejects one. The dev runner also rejects later sessions, bars, FX rows and dividends (code-level, D9) | 1: D9, invariant 5 |
| Store start | 1993-01-29 for every symbol. Member families start at `MEMBERSHIP_START` = 1996-01-02 | 4: handover D3 ("stocks: around 1997") |
| FX before 1999-01-04 | Starting cash uses `usd_idr_on(max(start, 1999-01-04))`. A window starting earlier runs on a copy of the market whose `fx` is the single row `(start, that rate)`, so the frozen `run_backtest` converts at it too (D-C); windows are never clamped. It affects only the starting-capital conversion, never a decision, and the report says so | 6: convention (FX is display and initial capital only; "Owner facts") |
| T-bill proxy before BIL (2007) | Idle cash earns 0% while BIL has no bar. Never a made-up yield. The idle symbol is not part of a candidate's window rule | 4: handover §8 recommendation |
| Benchmark on the dev window | `benchmark.spy_curves`, unchanged, on each candidate's own window and cash, with SPY dividends from the research store (vendored file overlap verified in phase 4) | 4: handover §8 ("the comparison with SPY uses that same window") |
| Registry format | `backtest/registry.py`: a tuple of frozen `Candidate`, with an append-only (id, digest) pin test | 4: handover §8 recommendation |
| First registry contents | The 54 entries above. F8 (learned ranker) and F12 (earnings drift) are excluded. F8's dev training data is survivor-biased, and §2.5 shows its signal was market timing, which F1/F2/L10 capture with no fitted parameters. F12 has no free pre-2015 history. Either may be appended later under D6 | 4: handover §4.B watch-outs and §8 ("about 6–10 families") |
| Reference candidates | REF-SPY-HOLD (a sanity check of the engine against the benchmark) and REF-A-V0 (A's idea under the closed rules on fresh data, D12). Both count as trials | 4: D12, D7 |
| Real-data `cmp` of A, A2 and B (R1) | Run in phase 13 only if Neon's bars fingerprint still equals (1,817,429 rows, 2026-10-02), with `--cache-dir` pointing at main's `engine/.cache`. Otherwise the phase log records the current fingerprint and the empty `git diff 2546a92` over the frozen set, and the synthetic `run_rules == run_backtest` test carries R1 | 1: acceptance R1 says "on the same data" |
| Report file names | The run date appears in file names only (and so in the links between the sibling files). Rendered content holds no wall-clock, so a same-day re-run is byte-identical. The registry's `added` dates are data and are rendered | 1: invariant 6 |
| Allocator ids vs. families | Allocator ids are `F1`, `F11`, `ROT`, `FAC`, `F7`, `PICKS`, `BLEND` and `VOLTARGET`. `Candidate.family` carries the catalogue label (F1–F11, REF) | 6: convention |
| D-A · `step_book`'s Σ weight check vs. `PICKS` (phase 1 interface note, phase 2 H1, phase 3 N1) | Σ weight ≤ 1 is validated **only when `rules.max_positions is None`**. `PICKS` emits held + every non-held pick at `equal_weight(slots)`, uncapped; the slot cap rejects the excess `no_slot`, exactly as `size_picks` | 2: phase 3's exit criteria (V0_BOOK parity with `size_picks` semantics) |
| D-B · Registry row 54 under `SWING_T20` with a limit-less TIMING core | The **engine** gets a fallback and the registry keeps `SWING_T20`: an unheld target with `limit=None` under `entry == "limit"` is bought exactly like `open_limit` (limit `q(last × 1.02)`, strict `low < limit`, fill at `min(open, limit)`). Held limit-less targets are never bought unless resized (unchanged). `describe_rules` states it for book limit-entry rule sets | 4: the index Registry table and its rationale ("Timed SPY core, swing satellite") |
| D-C · REF-A-V0 and FX before 1999-01-04 (phase 3 H1, phase 12) | Phase 9's approach: `DESIGN_V0` (and any) run whose window starts before `FX_START` runs on a market copy whose `fx` is the single row `(start, usd_idr_on(FX_START))`; windows are not clamped; phase 12's smoke keeps REF-A-V0 | 6: Decisions row "FX before 1999-01-04" (affects starting capital only) |
| D-D · Prepare reuse across candidates | Phase 2's `LazyPrepared` for PICKS/BLEND/VOLTARGET; every allocator's `prepare(history)` is param-independent; one prepared value per `allocator.id` (two different objects sharing an id are refused). Phase 12 calls `dev.run_registry(on_result=…)` instead of re-implementing the loop; per-candidate times come from the callback and include the first prepare, so the D13 estimate errs high. Nothing phase 12 needs breaks (curves come from the callback's result; the only casualty is a separate prepare time, which D13 does not need) | 6: convention (one code path; phase 9's contract "keyed by allocator.id") |
| D-E · The allocator test kit API | Phase 2's kit is canonical: `assert_valid_targets`, `assert_p4_identity(allocator, history, members_fn, dates, held_sets, params, *, max_weight_sum=Decimal(1), check_lookback=True) -> int`, `assert_no_lookahead(allocator, history, members_fn, sessions, held_sets, params) -> int`, `everyone`, `upto`, `tail`, `FIXED`/`FixedParams`, `MOMENTUM`/`MomentumFake`/`MomentumParams`. Phases 5–8 call exactly these, with list `held_sets` and `params` | 3: the plans' code blocks (phase 2's kit, verified by its own tests) |
| D-F · `as_dict` encodings | Every params `as_dict` renders a `(symbol, n)` pair as `"SYM:n"`, `None` as `"none"`, a tuple of symbols comma-joined and sorted. Phase 10 renders `as_dict()`; phase 11's `candidate_digest` walks dataclass fields (kept) | 3: the plans' code blocks (phases 5–8 already agree) |
| D-G · `top_years` | The finalists first (finalist order), then the highest MAR by `(−MAR, id)`, up to 5 | 3: the plans' code blocks (phase 12's derivation; phase 10's text and tests) |
| D-H · Phase 13 never stops to ask | Store missing → run `research_store`, record the new fingerprint, proceed. Fingerprint differs from phase 4's log → proceed with the store as it is and log both. Phase 4 fingerprint not found → use `research_store --verify`'s value and log it. A bug fixable only in `registry.py` or a frozen file → the phase ends with the run **not** committed and a note in the phase log and the completion summary (a stop, not a question). The same non-blocking rule applies to phase 12's Step 7 precondition | 6: the plan's autonomy rule (an unattended launch must never wait on an answer) |
| D-I · Where the `research` ↔ `dev`/`registry` agreement tests live | All in phase 12's `tests/test_backtest_dev_command.py` (phase 12 depends on 4, 9 and 11): `research.DEV_END`, `MEMBERSHIP_START`, `FX_START` equal `dev`'s; `registry.SECTOR_ETFS == research.SECTOR_ETFS`; every registry fixed symbol ⊆ `research.RESEARCH_ETFS`. No duplicate elsewhere | 6: convention (a test lives with the first phase that can import both sides) |
| Unknown signal (no bar on d) in F1/F11 | The state is unknown: a held `hold` is kept at its latest close, otherwise nothing; too little history is "off". A data gap never creates a round trip | 6: convention (no information means no trade; phase 5's decision, the same rule as PICKS's held passthrough) |
| The NYSE calendar in F11 | Treated as known in advance (calendar data, not price data); no bar after d is read | 6: convention (phase 5's decision; `seer_engine.dates`) |
| Rotation fallback and the candidate window | The fallback ETF (IEF) is part of `symbols(params)`, so a fallback candidate starts only when IEF has its lookback (conservative); before that the unused slots would sit in cash anyway | 3: the plans' code blocks (phase 9's window rule as contracted; phase 6's handoff) |
| F7 prepared path for non-default periods | `targets_prepared` uses the vectorized columns only for the default periods (every registry row); other periods run the single-window path on `prepared.history`, so P4 identity holds for every params value | 3: the plans' code blocks (phase 8; `prepare` takes no params) |
| Phase 12's run-time estimate (D13) | A class mean of per-candidate wall times (each including its allocator's first prepare) over the `--only` smoke; a pool only above 60 min, and then fixed-order with rows pinned equal to the sequential path | 4: handover D13 |
| Idle position passed to allocators (D-J) | `run_book` hands allocators `held = book.held() − {rules.idle_symbol}`: the idle position is the runner's residual, never a family's. `ResearchData.unserved` and the `data_dir` keyword on `build_store`/`load_store` are accepted additions to the contract | 6: convention (phase 8's handoff; the runner owns the residual weight) |

## Open Questions

(none)

## Rollback

- **Per phase:** `git revert` the phase's commits. Phases 1–12 add new modules and tests, with
  additive-only edits to `sim/__init__.py`, `indicators.py`, `yahoo.py`, `io.py` and
  `.gitignore`, so reverting removes them cleanly.
- **The research store:** delete `engine/.research/`. It is rebuilt by
  `python -m seer_engine research_store`.
- **As a whole:** drop the branch `feature/trade-rules-dev-search`. Nothing reaches Neon, and no
  closed record is edited.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f TRADE_RULES_DEV_SEARCH_PLAN.md --phase 1

Or run the whole set as a swarm: a session per phase, concurrent wherever `Depends on` allows,
and resumable on any machine:

    /analyze-orchestrator -f TRADE_RULES_DEV_SEARCH_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan TRADE_RULES_DEV_SEARCH_PLAN.md
