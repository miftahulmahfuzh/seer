# Phase 1: Resize band relative to the holding's target (`resize_basis` lever)

**Plan set:** `MEASURE_THEN_LEARN_PLAN.md`
**Analysis:** `20261012-205553-M7T1_code_analyzer.md`
**Satisfies:** R1 — the resize band can be measured against the holding's own target, with no past result moved
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/sim`

---

## Goal

`TradeRules` gains a lever `resize_basis` ("equity" default, "target" new). At "equity" every rule
set behaves, describes and digests exactly as today. At "target" the book engine trims and adds a
held target once its share gap is worth at least `TARGET_RESIZE_BAND` (20%) of that holding's own
target value, instead of 1% of the whole account. No preset uses it yet (phase 3 adds them), so
paper, web and every recorded digest are untouched.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `sim.rules.ResizeBasis = Literal["equity", "target"]` (`sim/rules.py`)
- `sim.rules.TARGET_RESIZE_BAND = Decimal("0.20")` (`sim/rules.py`, next to `RESIZE_BAND`)
- `sim.rules._RESIZE_BASES = ("equity", "target")` (private)
- field `TradeRules.resize_basis: ResizeBasis = "equity"` — **the last field after this phase,
  appended directly after `cost_model`**. Phase 2 appends `cash_yield` after it.
- `LEVERS_SINCE_PINS["resize_basis"] = "equity"` (third entry, after `cost_model`)
- `_V0_LEVERS` gains a 14th element `"equity"` (last)
- `sim.book._beyond_band(gap, last, weight, equity, rules) -> bool` (private helper, `sim/book.py`)
- `sim.TARGET_RESIZE_BAND` re-export (`sim/__init__.py`)
- new test file `engine/tests/test_resize_basis_pins.py`
**Signature changes:** none (`step_book` signature untouched; phase 2 adds `cash_rate`).
**Behaviour contract (for phase 3's web mirror and phases 5/7):** under `resize_basis="target"` a
held target trades (trim or add) iff `gap > 0 and gap × t.last >= TARGET_RESIZE_BAND × t.weight × equity`,
where `equity` is the last snapshot's equity (`book.equity`), `gap` is the share excess (trim) or
shortfall (add) against `_desired_shares`. The idle instrument uses the same basis as every other
held target. Under "equity" the rule is the old `gap × t.last >= RESIZE_BAND × equity`, unchanged.
**Validation contract:** `resize_basis` must be a str in `("equity", "target")` (TypeError /
ValueError "unknown resize_basis"); `"target"` requires `engine == "book"` and `resize=True`
(ValueError otherwise).
**describe_rules contract:** still exactly 12 lines for every rule set. Only the Rebalance line
(index 7) changes, and only when `resize and resize_basis == "target"`:
`"Rebalance: on decision sessions, a held position is traded back to its target weight at the open when it is off by at least 20% of its own target value."`
**Requires (from earlier phases):** none.
**Leaves alone (owned by others):** `PRESETS` and every existing preset value (phase 3);
`web/` and `engine/tests/test_sean_mirrors.py` (phase 3); `RESIZE_BAND` value `0.01` (frozen);
cash interest / `cash_yield` / `step_book` keyword args (phase 2); `paper/roster.py` (no change
needed — `rules_dict` already omits pinned defaults); `backtest/registry.py` (no change needed —
`_canon` already omits pinned defaults); `commands/lab.py`, survivorship (phase 4); lab methods
(phases 5, 7); strategies (phase 6).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/sim/rules.py` | modify | module docstring note; `ResizeBasis`, `_RESIZE_BASES`, `TARGET_RESIZE_BAND`; field `resize_basis`; validation; `_V0_LEVERS`; `LEVERS_SINCE_PINS`; `describe_rules` Rebalance line |
| `engine/src/seer_engine/sim/book.py` | modify | import `TARGET_RESIZE_BAND`; docstring steps 3/4; new `_beyond_band`; the three band checks (:561, :617, :654) call it |
| `engine/src/seer_engine/sim/__init__.py` | modify | import and `__all__` entry for `TARGET_RESIZE_BAND` |
| `engine/tests/test_sim_rules.py` | modify | `LEVERS_SINCE_PINS` equality (:416); new resize_basis tests appended at end |
| `engine/tests/test_sim_book.py` | modify | three new behaviour tests + helper test appended at end |
| `engine/tests/test_backtest_dev_report.py` | modify | the `TradeRules(...)` literal (:568-571) gains `, resize_basis='equity'` |
| `engine/tests/test_resize_basis_pins.py` | create | canonical-form absence at "equity", presence and different digests at "target" |

## Implementation Steps

### Step 0: Worktree venv and the test database

The worktree has no `engine/.venv` (memory note: main's venv tests the wrong tree).

```bash
cd /home/miftah/.worktrees/seer/measure-then-learn
python3.11 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'
docker start seer-pg 2>/dev/null || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
engine/.venv/bin/pytest engine/tests -q   # baseline: must be green before any edit
```

### Step 1: The type, the constant and the field
**File:** `engine/src/seer_engine/sim/rules.py:38-58` (type aliases and constants) and `:77-93` (the dataclass fields)

**Change:** add the `ResizeBasis` alias after `Entry` (line 40), `TARGET_RESIZE_BAND` after
`RESIZE_BAND` (line 43), `_RESIZE_BASES` after `_ENTRIES` (line 54), and append the field after
`cost_model` (line 93).

**Code** (lines 38-58 become):
```python
Engine = Literal["bracket_v0", "bracket", "book"]
Cadence = Literal["daily", "weekly", "monthly"]
Entry = Literal["limit", "open_limit", "open"]
ResizeBasis = Literal["equity", "target"]

OPEN_LIMIT_BAND = Decimal("0.02")
RESIZE_BAND = Decimal("0.01")
# The band under resize_basis="target": a held position is traded back once it is off by at least
# this fraction of its OWN target value (2026-10-12, measure-then-learn). RESIZE_BAND stays the
# band of every rule set that predates the lever, so no recorded result moves.
TARGET_RESIZE_BAND = Decimal("0.20")
SHARE_QUANTUM = Decimal("0.0001")
DEFAULT_ETFS: frozenset[str] = frozenset({"SPY", "QQQ"})
LEVERAGED_ETFS: frozenset[str] = frozenset({"SSO", "QLD", "UPRO", "TQQQ"})

_ENGINES: tuple[str, ...] = ("bracket_v0", "bracket", "book")
#: The engines run by ``sim.size_picks`` + ``sim.step`` + ``sim.apply_split`` (not the book).
BRACKET_ENGINES: tuple[str, ...] = ("bracket_v0", "bracket")
_CADENCES: tuple[str, ...] = ("daily", "weekly", "monthly")
# Slower cadences sort higher: a resize cadence must be strictly below its rank cadence.
_CADENCE_ORDER: dict[str, int] = {"daily": 0, "weekly": 1, "monthly": 2}
_ENTRIES: tuple[str, ...] = ("limit", "open_limit", "open")
_RESIZE_BASES: tuple[str, ...] = ("equity", "target")
_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_DEFAULT_COST = Decimal("0.001")
_MAX_COST = Decimal("0.05")
_V0_ID = "design-v0"
```

The field block (lines 81-93) becomes:
```python
    id: str
    engine: Engine
    cadence: Cadence = "daily"
    resize_cadence: Cadence | None = None
    entry: Entry = "limit"
    max_positions: int | None = None
    time_stop: int | None = None
    resize: bool = False
    fractional: bool = False
    dividends: bool = True
    idle_symbol: str | None = None
    cost_rate: Decimal = _DEFAULT_COST
    cost_model: CostModel = "flat"
    resize_basis: ResizeBasis = "equity"
```

**Impact:** a new field at the end — positional construction and every keyword construction still
work. `fields(rules)` now has 14 entries; see Steps 3, 4 and 9 for every consumer that iterates it.

### Step 2: Validation
**File:** `engine/src/seer_engine/sim/rules.py:141` (inside `__post_init__`, immediately before `is_v0 = _lever_values(self) == _V0_LEVERS`)

**Change:** insert the resize_basis checks after the cost_model checks (after line 140).

**Code:**
```python
        if not isinstance(self.resize_basis, str):
            raise TypeError(f"resize_basis must be a str, got {type(self.resize_basis).__name__}")
        if self.resize_basis not in _RESIZE_BASES:
            raise ValueError(f"unknown resize_basis {self.resize_basis!r}; expected one of {_RESIZE_BASES}")
        if self.resize_basis == "target":
            if self.engine != "book":
                raise ValueError(
                    "resize_basis 'target' is a book-engine lever; the bracket simulator never resizes"
                )
            if not self.resize:
                raise ValueError("resize_basis 'target' needs resize=True: a band with nothing to resize is a no-op")
```

**Impact:** only rule sets that set the new field can fail; every existing construction passes
(`"equity"` is the default).

### Step 3: `_V0_LEVERS` and `LEVERS_SINCE_PINS`
**File:** `engine/src/seer_engine/sim/rules.py:153-167` and `:247-250`

**Change:** `_V0_LEVERS` compares against *every* field in order, so without a 14th element
`DESIGN_V0` would fail its own `bracket_v0` reservation at import. Add the lever to the pins map.

**Code** (lines 153-167 become):
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
)
```

Lines 247-250 become:
```python
LEVERS_SINCE_PINS: dict[str, object] = {
    "resize_cadence": None,  # the rank/resize cadence split, 2026-10-05
    "cost_model": "flat",  # Gotrade's measured fee schedule (sim.costs), 2026-10-07
    "resize_basis": "equity",  # the band measured against the holding's own target, 2026-10-12
}
```

**Impact:** `backtest.registry._canon` (`registry.py:325-331`) and `paper.roster.rules_dict`
(`roster.py:1392-1404`) already drop any field for which `is_pinned_default` is True, so every
registry digest, every closed lab `config_digest` and every live paper spec digest stays
byte-identical. No edit to either file. Verified by Step 10 and the existing pin tests.

### Step 4: `describe_rules` Rebalance line
**File:** `engine/src/seer_engine/sim/rules.py:424-430`

**Change:** add a target-basis branch before the existing equity branch. The equity-basis text is
untouched (golden-tested in `test_describe_monthly_hold_tbill_golden`), and the line count stays 12.

**Code** (lines 424-430 become):
```python
    if rules.resize and rules.resize_basis == "target":
        lines.append(
            f"Rebalance: on decision sessions, a held position is traded back to its target weight "
            f"at the open when it is off by at least {_pct(TARGET_RESIZE_BAND)} of its own target value."
        )
    elif rules.resize:
        lines.append(
            f"Rebalance: on decision sessions, a held position is traded back to its target weight "
            f"at the open when it is off by at least {_pct(RESIZE_BAND)} of equity."
        )
    else:
        lines.append("Rebalance: none; a held position keeps its shares until it exits.")
```

(`_pct(Decimal("0.20"))` renders `"20%"`: `(Decimal("20.00")).normalize()` is `2E+1`, formatted `'f'` → `"20"`.)

### Step 5: Module docstring note
**File:** `engine/src/seer_engine/sim/rules.py:19-22`

**Change:** add one paragraph after the cadence paragraph (after line 22, before "Pure: ..." at 24).

**Code:**
```python
"""
``resize_basis`` chooses what the rebalance band is measured against. "equity" (every rule set
before 2026-10-12) trades a held target only once it is off by ``RESIZE_BAND`` (1%) of the whole
account, which in a 20-50 name book means a holding must drift 50-100% of its own size first, so
"resize" rules barely resized. "target" trades it once it is off by ``TARGET_RESIZE_BAND`` (20%)
of its own target value. The default is a pinned no-op (``LEVERS_SINCE_PINS``), so no recorded
result, digest or live paper strategy moves.
"""
```
(Insert as plain docstring prose — the triple quotes above only delimit the snippet; the
paragraph goes inside the existing module docstring with a blank line on each side.)

### Step 6: The single band helper in the book engine
**File:** `engine/src/seer_engine/sim/book.py:60` (import), `:385` (new helper after `_desired_shares`, which ends at line 384)

**Change:** import the new constant; add `_beyond_band`.

**Code** (line 60 becomes):
```python
from seer_engine.sim.rules import OPEN_LIMIT_BAND, RESIZE_BAND, SHARE_QUANTUM, TARGET_RESIZE_BAND, TradeRules
```

New function, inserted between `_desired_shares` and `_sizing_price`:
```python
def _beyond_band(gap: Decimal, last: Decimal, weight: Decimal, equity: Decimal, rules: TradeRules) -> bool:
    """True when a held target is far enough off its weight to trade: ``gap`` shares (a trim's
    excess or an add's shortfall; <= 0 is never beyond) worth at ``last`` at least the band.

    The one place trims, adds and the night's planned trims decide "big enough", so the three
    can never disagree. ``rules.resize_basis``:

    - "equity" (every rule set before the lever): ``gap × last >= RESIZE_BAND × equity``, 1% of
      the whole account -- byte-for-byte the comparison the engine always made;
    - "target": ``gap × last >= TARGET_RESIZE_BAND × weight × equity``, 20% of the holding's own
      target value, so a 2% holding in a 50-name book is resized as readily as a 50% one.

    ``equity`` is the last snapshot's (``book.equity``), the same equity the sizing uses.
    """
    if gap <= 0:
        return False
    if rules.resize_basis == "target":
        return gap * last >= TARGET_RESIZE_BAND * weight * equity
    return gap * last >= RESIZE_BAND * equity
```

### Step 7: The three call sites
**File:** `engine/src/seer_engine/sim/book.py:561`, `:617`, `:654`

**Change:** replace each inline comparison with the helper. Each replacement is logically identical
under "equity": `excess > 0 and excess*last >= B` ⇔ `_beyond_band(...)`; `excess <= 0 or excess*last < B`
⇔ `not _beyond_band(...)`.

**Code** — night plan, lines 559-562 become:
```python
            desired = _desired_shares(equity, t.weight, t.last, rules)
            excess = p.shares - desired
            if _beyond_band(excess, t.last, t.weight, equity, rules):
                planned += _sell_cash(t.last, excess, rules)
```

Trims, lines 615-618 become:
```python
            desired = _desired_shares(equity, t.weight, t.last, rules)
            excess = p.shares - desired
            if not _beyond_band(excess, t.last, t.weight, equity, rules):
                continue
```

Adds, lines 652-655 become:
```python
                desired = _desired_shares(equity, t.weight, t.last, rules)
                gap = desired - p.shares
                if not _beyond_band(gap, t.last, t.weight, equity, rules):
                    continue
```

**Impact:** `RESIZE_BAND` is now referenced in `book.py` only by `_beyond_band` and the docstring.

### Step 8: Book docstring steps 3 and 4
**File:** `engine/src/seer_engine/sim/book.py:19-24`

**Code** (lines 19-24 become):
```python
3. trims (decision sessions; ``rules.resize`` or the idle instrument): a held target worth
   more than its target weight by at least the band (``_beyond_band``: ``RESIZE_BAND × equity``
   under ``rules.resize_basis == "equity"``, ``TARGET_RESIZE_BAND × weight × equity`` under
   "target") is sold down at the open;
4. buys, targets in rank order with the idle instrument last: new entries (``max_positions``
   counted as the night before, exactly as ``sim.size_picks``) and adds (same band as trims,
   upward), sized the night before from the last snapshot's equity and the cash the night's
```
(The rest of item 4, from `planned sells will bring, then filled at the open ...` on line 24, is unchanged.)

### Step 9: Re-export
**File:** `engine/src/seer_engine/sim/__init__.py:75` (import list) and `:112` (`__all__`)

**Change:** add `TARGET_RESIZE_BAND` to the `from seer_engine.sim.rules import (...)` list between
`SWING_T20_OPEN,` (line 75) and `V0_BOOK,` (line 76), and to `__all__` between `"SWING_T20_OPEN",`
(line 111) and `"TIME_STOP_DAYS",` (line 112).

**Code:**
```python
    SWING_T20_OPEN,
    TARGET_RESIZE_BAND,
    V0_BOOK,
```
```python
    "SWING_T20_OPEN",
    "TARGET_RESIZE_BAND",
    "TIME_STOP_DAYS",
```

### Step 10: Existing tests that enumerate fields
**File:** `engine/tests/test_sim_rules.py:416`

**Code:**
```python
    assert LEVERS_SINCE_PINS == {"resize_cadence": None, "cost_model": "flat", "resize_basis": "equity"}
```
Also add to the same test function (after line 415):
```python
    assert is_pinned_default("resize_basis", "equity") is True
    assert is_pinned_default("resize_basis", "target") is False
```

**File:** `engine/tests/test_backtest_dev_report.py:568-571` — `dev_report._rules_literal` prints
every field (precedent: `cost_model='flat'` was added here when that lever landed).

**Code:**
```python
    assert (
        "TradeRules(id='monthly-hold', engine='book', cadence='monthly', resize_cadence=None, "
        "entry='open_limit', max_positions=None, "
        "time_stop=None, resize=True, fractional=False, dividends=True, idle_symbol=None, cost_rate=Decimal('0.001'), "
        "cost_model='flat', resize_basis='equity')"
    ) in text
```
(The rules table at `dev_report.py:1095` gains a `| resize_basis | equity |` row for new reports;
no test pins the full table and past reports in `docs/backtests/` are committed files, never
re-rendered.)

### Step 11: New rules tests
**File:** `engine/tests/test_sim_rules.py` — append at end of file (after line 515). Add
`TARGET_RESIZE_BAND` is reached as `rules.TARGET_RESIZE_BAND` (the module is already imported as
`rules`), so no import change.

**Code:**
```python
# ============================================================== the resize basis


def test_resize_basis_defaults_to_equity_everywhere():
    assert rules.TARGET_RESIZE_BAND == Decimal("0.20")
    assert rules.RESIZE_BAND == Decimal("0.01")  # frozen: every recorded result used it
    assert sim.TARGET_RESIZE_BAND is rules.TARGET_RESIZE_BAND
    assert TradeRules(id="x", engine="book").resize_basis == "equity"
    assert DESIGN_V0.resize_basis == "equity" and V0_BOOK.resize_basis == "equity"
    # Every preset that predates the lever (the first 16). Phase 3 appends target-basis presets
    # after them; asserting over all of PRESETS would turn red the moment it does.
    assert len(PRESETS) >= 16
    assert all(r.resize_basis == "equity" for r in PRESETS[:16])


def test_resize_basis_validation():
    target = replace(MONTHLY_HOLD, id="x", resize_basis="target")
    assert target.resize_basis == "target"
    with pytest.raises(ValueError, match="unknown resize_basis"):
        replace(MONTHLY_HOLD, id="x", resize_basis="position")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="resize_basis"):
        replace(MONTHLY_HOLD, id="x", resize_basis=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="needs resize=True"):
        replace(DAILY_SWITCH, id="x", resize_basis="target")
    with pytest.raises(ValueError, match="book-engine lever"):
        replace(DESIGN_V0_GOTRADE, id="x", resize=True, resize_basis="target")
    with pytest.raises(ValueError, match="book-engine lever"):
        replace(DESIGN_V0, resize_basis="target")


def test_describe_target_basis_changes_only_the_rebalance_line():
    target = replace(MONTHLY_HOLD_TBILL, id="monthly-hold-tbill", resize_basis="target")
    lines = describe_rules(target)
    assert len(lines) == 12
    assert lines[7] == (
        "Rebalance: on decision sessions, a held position is traded back to its target weight at "
        "the open when it is off by at least 20% of its own target value."
    )
    before = describe_rules(MONTHLY_HOLD_TBILL)
    assert lines[:7] == before[:7] and lines[8:] == before[8:]
    assert before[7].endswith("off by at least 1% of equity.")


def test_resize_basis_is_not_an_owner_input():
    assert rule_owner_inputs(replace(MONTHLY_HOLD, id="x", resize_basis="target")) == ()
```

### Step 12: New book tests
**File:** `engine/tests/test_sim_book.py` — append at end of file (after line 870). Every name used
(`RESIZE`, `T`, `pos`, `book`, `go`, `day`, `bar`, `P`, `W`, `TUE`, `replace`) is already imported
or defined in this file.

**Code:**
```python
# ============================================================== the resize basis


RESIZE_TARGET = replace(RESIZE, id="resize-target", resize_basis="target")


def test_target_basis_trims_a_small_holding_the_equity_band_ignores():
    # equity 0 + 25 × 10 + 975 × 10 = 10,000.
    b = book("0", pos("AAA", 25, "10"), pos("BBB", 975, "10"))
    bars = day(bar("AAA", TUE, "10", "10", "10", "10"), bar("BBB", TUE, "10", "10", "10", "10"))
    targets = (T("AAA", "0.02", "10"), T("BBB", "0.975", "10"))
    # AAA desired floor(200 / 10.01) = 19, excess 6 × 10 = 60: < 1% × 10,000 = 100 (equity basis
    # holds), >= 20% × 0.02 × 10,000 = 40 (target basis trims). BBB desired floor(9750 / 10.01)
    # = 974, excess 1 × 10 = 10: below both bands.
    assert go(b, TUE, bars, targets, RESIZE).fills == ()
    out = go(b, TUE, bars, targets, RESIZE_TARGET)
    # trim 6 at the open 10: q(60 × 0.999) = 59.94
    assert [(f.symbol, f.side, f.shares, f.price, f.cash_usd, f.reason) for f in out.fills] == [
        ("AAA", "sell", W(6), P("10"), P("59.94"), "trim"),
    ]
    assert out.book.position("AAA").shares == W(19)
    assert out.book.position("BBB").shares == W(975)


def test_target_basis_adds_to_a_small_holding_the_equity_band_ignores():
    # equity 100 + 10 × 10 + 980 × 10 = 10,000.
    b = book("100", pos("AAA", 10, "10"), pos("BBB", 980, "10"))
    bars = day(bar("AAA", TUE, "10", "10", "9.9", "10"), bar("BBB", TUE, "10", "10", "10", "10"))
    targets = (T("AAA", "0.02", "10"), T("BBB", "0.98", "10"))
    # AAA desired 19, gap 9 × 10 = 90: < 100 (equity basis holds), >= 40 (target basis adds).
    # BBB desired floor(9800 / 10.01) = 979, excess 1 × 10 = 10: below both bands.
    assert go(b, TUE, bars, targets, RESIZE).fills == ()
    out = go(b, TUE, bars, targets, RESIZE_TARGET)
    # limit q(10 × 1.02) = 10.2; min(9, floor(100 / 10.2102) = 9) = 9; low 9.9 < 10.2 fills at
    # min(open 10, 10.2) = 10: q(10 × 9 × 1.001) = 90.09.
    assert [(f.symbol, f.side, f.shares, f.price, f.cash_usd, f.reason) for f in out.fills] == [
        ("AAA", "buy", W(9), P("10"), P("-90.09"), "add"),
    ]
    assert out.snapshot.cash_usd == P("9.91")


def test_target_basis_leaves_a_large_holding_the_equity_band_would_trade():
    # equity 0 + 52 × 100 + 48 × 100 = 10,000.
    b = book("0", pos("AAA", 52, "100"), pos("BBB", 48, "100"))
    bars = day(bar("AAA", TUE, "100", "100", "99", "100"), bar("BBB", TUE, "100", "100", "99", "100"))
    targets = (T("AAA", "0.5", "100"), T("BBB", "0.5", "100"))
    # desired floor(5000 / 100.1) = 49 both. AAA excess 3 × 100 = 300, BBB gap 1 × 100 = 100:
    # both >= 1% × 10,000 = 100 (equity basis trades both), both < 20% × 0.5 × 10,000 = 1,000.
    assert [(f.symbol, f.reason) for f in go(b, TUE, bars, targets, RESIZE).fills] == [
        ("AAA", "trim"),
        ("BBB", "add"),
    ]
    out = go(b, TUE, bars, targets, RESIZE_TARGET)
    assert out.fills == () and out.rejected == ()


def test_beyond_band_is_the_old_comparison_under_the_equity_basis():
    from seer_engine.sim.book import _beyond_band

    e = W("10000")
    for gap in (W(-1), W(0), W(1), W(2)):
        for last in (W("49.99"), W("50"), W("100")):
            old = gap > 0 and gap * last >= W("0.01") * e
            assert _beyond_band(gap, last, W("0.5"), e, RESIZE) is old
    assert _beyond_band(W(0), W(100), W("0.02"), e, RESIZE_TARGET) is False
    assert _beyond_band(W(4), W(10), W("0.02"), e, RESIZE_TARGET) is True  # 40 >= 0.2 × 200
    assert _beyond_band(W("3.9999"), W(10), W("0.02"), e, RESIZE_TARGET) is False
```

Hand-checks behind the numbers (all whole shares, flat 0.1% cost, `entry="open_limit"`):
- Trim test: night plan adds AAA's planned sale under "target" only; buys: AAA now held at 19 =
  desired (no add), BBB gap −1 (no add). No rejections.
- Add test: `available = book.cash + planned = 100 + 0`; the add's `_shares_for(100, 10.2)` with
  unit `10.2 × 1.001 = 10.2102` floors to 9 (9 × 10.2102 = 91.8918 ≤ 100). Cash guard: 90.09 ≤ 100.
- Large-holding test, equity basis: AAA trim 3 at open 100 funds BBB's add of 1 at min(100, 102)
  = 100 (low 99 < 102); the test only asserts the reasons.

### Step 13: The pins test
**File:** `engine/tests/test_resize_basis_pins.py` (new)

**Code:**
```python
"""Invariant 2 of the measure-then-learn plan: adding ``TradeRules.resize_basis`` moves no
pinned digest.

``resize_basis`` is a lever added after the pins (``sim.rules.LEVERS_SINCE_PINS``), so at its
no-op value "equity" it is left out of every canonical form: the registry's ``candidate_text``,
the lab's ``config_text`` (every closed trial's ``config_digest``) and the paper roster's
``rules_dict`` (every live spec digest). A rule set that USES "target" canonicalizes differently,
which is the point. ``tests/test_cost_model_pins.py`` already recomputes every committed lab
trial's digest byte for byte; ``tests/test_registry.py`` and ``tests/test_paper_roster.py`` pin
theirs. This file asserts the lever's own absence and presence.
"""

from __future__ import annotations

from dataclasses import replace

from seer_engine.backtest.registry import REGISTRY, candidate_digest, candidate_text
from seer_engine.lab.method import config_digest, config_text, discover
from seer_engine.paper import roster
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, PRESETS


def _all_candidates():
    out = list(REGISTRY)
    for m, _ in discover().values():
        out += list(m.candidates)
    return out


def _asserts_resize_basis(text: str, c) -> None:
    """"equity" is left out of a canonical form; "target" names itself, so it digests apart.

    Conditional on purpose: later methods built on a target-basis preset must name the lever,
    and asserting absence unconditionally would pin the lab to the old band.
    """
    if c.rules.resize_basis == "equity":
        assert "resize_basis" not in text, c.id
    else:
        assert f"resize_basis='{c.rules.resize_basis}'" in text, c.id


def test_equity_is_absent_from_every_canonical_form():
    for c in REGISTRY:
        _asserts_resize_basis(candidate_text(c), c)
    for c in _all_candidates():
        _asserts_resize_basis(config_text(c), c)
    for r in PRESETS:
        if r.resize_basis == "equity":
            assert "resize_basis" not in roster.rules_dict(r), r.id
        else:
            assert roster.rules_dict(r)["resize_basis"] == r.resize_basis, r.id


def test_target_digests_differently():
    resizing = [c for c in _all_candidates() if c.rules.engine == "book" and c.rules.resize]
    assert resizing
    for c in resizing[:25]:
        if c.rules.resize_basis == "target":
            continue
        t = replace(c, rules=replace(c.rules, resize_basis="target"))
        assert "resize_basis='target'" in config_text(t), c.id
        assert config_digest(t) != config_digest(c), c.id
        assert candidate_digest(t) != candidate_digest(c), c.id
    g = replace(MONTHLY_HOLD_FRAC_GOTRADE, id="monthly-hold-frac-gotrade-tband", resize_basis="target")
    assert roster.rules_dict(g)["resize_basis"] == "target"
    assert "resize_basis" not in roster.rules_dict(MONTHLY_HOLD_FRAC_GOTRADE)
```

Note: `Candidate` must be a dataclass for `replace(c, rules=...)` — it is
(`test_cost_model_pins._gotrade` does the same). If `discover()` contains a method whose candidate
type differs, the `[:25]` slice matches the existing pattern in `test_cost_model_pins`.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/measure-then-learn && engine/.venv/bin/ruff check engine`
**Tests:** with `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres`:
- focused: `engine/.venv/bin/pytest engine/tests/test_sim_rules.py engine/tests/test_sim_book.py engine/tests/test_sim_book_split.py engine/tests/test_resize_basis_pins.py engine/tests/test_cost_model_pins.py engine/tests/test_registry.py engine/tests/test_paper_roster.py engine/tests/test_lab_methods.py engine/tests/test_backtest_dev_report.py engine/tests/test_book_runner.py -n0`
- full: `engine/.venv/bin/pytest engine/tests` (no DB test may skip: check the summary for `skipped`)
**Manual check:** `git diff --stat` touches only the seven files in the Files table; `git diff engine/src/seer_engine/sim/rules.py` shows no change to any `PRESETS` entry or preset definition.
**Exit criteria:**
- With `resize_basis="equity"` (every existing rule set) every existing test passes unchanged
  except the two field-enumerating assertions updated in Step 10; every registry digest
  (`test_registry.py`), lab config digest (`test_cost_model_pins.py`,
  `test_lab_methods.py::test_every_recorded_configuration_still_digests_to_its_recorded_digest`)
  and paper spec digest (`test_paper_roster.py` PINS) is unchanged.
- With `resize_basis="target"` a holding trades iff `gap × last ≥ TARGET_RESIZE_BAND × weight × equity`
  (Step 12 tests).
- `ruff check engine` clean; full engine suite green with DB tests running.

## Handoffs

- **Phase 2 (R2):** `cash_yield` is appended *after* `resize_basis`. Phase 2 must therefore also
  (a) append its no-op default as the 15th element of `_V0_LEVERS` (after `"equity"`),
  (b) add `"cash_yield": None` as the fourth `LEVERS_SINCE_PINS` entry and extend the equality
  assertion at `test_sim_rules.py:416` (which after this phase reads
  `{"resize_cadence": None, "cost_model": "flat", "resize_basis": "equity"}`), and
  (c) extend the `TradeRules(...)` literal at `test_backtest_dev_report.py:568-571` to end
  `..., cost_model='flat', resize_basis='equity', cash_yield=None)`.
  Phase 2 quotes `sim/book.py` with the `_beyond_band` helper in place (Steps 6-8).
- **Phase 3 (R1, R2):** the target-basis presets (`monthly-hold-frac-gotrade-tband`, etc.) are
  built with `replace(MONTHLY_HOLD_FRAC_GOTRADE, id=..., resize_basis="target")`. Phase 3 owns
  `PRESETS`, `test_preset_ids_are_unique_and_in_order`, the non-flat preset list in
  `test_cost_model_pins.py`, the web mirror `TARGET_RESIZE_BAND = 0.2` and `sizeChange`
  (`web/lib/cadence.ts`), whose rule must match the behaviour contract above:
  trade iff `|gap| × last ≥ 0.20 × weight × equity`. Phase 3 should also check
  `commands/promote.fractional_twin` (`promote.py:144`), which compares every field but `id` and
  `fractional`: a target-basis preset's fractional twin must also be target-basis.
  `test_resize_basis_defaults_to_equity_everywhere` asserts only over `PRESETS[:16]` (the presets
  that predate the lever), so phase 3's appended presets do not turn it red and phase 3 does not
  edit it (reconciled).
  `test_resize_basis_pins.test_equity_is_absent_from_every_canonical_form` already handles
  target-basis presets (it asserts `rules_dict` names the lever), so it needs no edit there.
- **Paper (R1 explicit decision):** no roster entry changes rules in this phase or any phase of
  this set (index Decision "Does live paper change? No").
- No drive-by cleanups were found that need another phase.

## Rollback

Revert this phase's commit. The lever defaults to a pinned no-op and no preset, lab method or
roster entry uses it at this point, so nothing recorded depends on it. If phase 2 has already
landed on top, revert phase 2 first (it appends after this field and extends `_V0_LEVERS` past it).
