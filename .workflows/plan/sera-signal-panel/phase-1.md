# Phase 1: Signal registry and the pure panel evaluator

**Plan set:** `SERA_SIGNAL_PANEL_PLAN.md`
**Analysis:** `.workflows/analyze/20261113-200537-K7P2_code_analyzer.md`
**Satisfies:** R1, R2 — a stock-picking idea can be written as a pure signal file, and its panel figures can be computed per era
**Criteria:** R1.1, R2.1
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab`

---

## Goal

After this phase a stock-ranking idea can be written as one committed file
`engine/src/seer_engine/lab/signals/sNNNN_<slug>.py` exporting `SIGNAL = Signal(...)`, found by
`signal.discover()` and held to a contract test (pure, unique id, no look-ahead, within its
lookback). `lab.panel` can turn a loaded research store into a stock-by-month frame once
(`build_frame`) and measure any signal, or any pick set, on it (`measure`). For each era it
returns months, mean rank correlation and its t, the annualised top-minus-pool spread and its t,
the slope controlled for momentum, beta, size and volatility and its t, plus top-bucket turnover
and a pick-set hash. The module is pure: no database, clock or files. Nothing records anything
yet. Phase 3 does the recording.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `seer_engine.lab.signal` (`engine/src/seer_engine/lab/signal.py`): `SIGNAL_ID`, `MODULE_NAME`,
  `MAX_LOOKBACK = 473`, `MARKET_FIELDS = ("fundamentals", "dividends", "announcements", "series", "shares")`,
  `ScoreFn`, `Signal` (frozen dataclass, fields exactly as the index's shared contract, plus the
  method `Signal.scores(market, pool, data_date) -> dict[str, float]` that applies the cut),
  `visible(market, data_date, lookback) -> tuple[dict[str, History], Market]`,
  `signals_package() -> ModuleType`, `discover(package: ModuleType | None = None) -> dict[str, tuple[Signal, Path]]`,
  `source_sha` (re-export of `lab.method.source_sha`, same function object).
- `seer_engine.lab.signals` package (`engine/src/seer_engine/lab/signals/__init__.py`).
- `seer_engine.lab.signals.s0001_twelve_minus_one_momentum.SIGNAL` (id `S0001`, family `stock-momentum`, lookback 253).
- `seer_engine.lab.signals.s0002_hash_draw.SIGNAL` (id `S0002`, family `stock-random-draw`, lookback 1), plus `draw(symbol, data_date) -> float`.
- `seer_engine.lab.panel` (`engine/src/seer_engine/lab/panel.py`): `RULE_ID = "panel-v1"`,
  `ERAS = ("all", "pre2009", "2009-2015")`, `ERA_SPLIT = date(2009, 1, 1)`, `TOP_FRACTION = 0.10`,
  `TOP_MIN = 10`, `MIN_SCORED = 30`, `MIN_PICKS = 5`, `MIN_ERA_MONTHS = 12`, `MARKET = "SPY"`,
  `CONTROLS = ("momentum", "beta", "volatility", "size")`, `MODES = ("score", "picks")`, `Scorer`,
  `Mode`, `PanelMonth`, `PanelFrame`, `EraStats`, `PanelReading` (with `.era(name) -> EraStats | None`),
  `top_size(scored) -> int`, `build_frame(data) -> PanelFrame`, `signal_scorer(signal) -> Scorer`,
  `measure(frame, scorer, *, mode="score") -> PanelReading`.
- `.claude/skills/explore-and-experiment-new-method/signal_template.py`.
- `engine/tests/test_lab_signals.py`, `engine/tests/test_lab_panel.py`.

**Signature changes:** none to existing code.
**Requires (from earlier phases):** none.
**Leaves alone (owned by others):** `lab/store.py`, `lab/panel_verdict.py` (Phase 2);
`commands/lab.py`, `features/signal-panel.md` (Phase 3); `lab/panel_replay.py` (Phase 4);
`lab/method.py`, `lab/runner.py`, `lab/hardgate.py`, `lab/signal_book.py`, `method_template.py`
(Phase 5); everything under `web/` (Phases 2, 6); every `SKILL.md`, `CLAUDE.md`, `README.md`
(Phase 7).

**Where this differs from the index's shared contract (the reconciler should carry these into the index):**
1. The pool is `strategies.f_factor.factor_rows(history, members, d, tree_rank.SCREEN)` (the
   single-window path), not `prepare_factor(...).rows_on(...)`. f_factor's own contract makes the
   two equal (`f_factor.py` module docstring: "`targets_prepared` equals `targets` on `upto(d)` bit
   for bit"). `prepare_factor` holds every symbol's every-bar columns in memory next to the store,
   and the panel reads only month-ends.
2. `EraStats.fm_slope` is the **mean monthly** controlled slope (next-month return per one standard
   deviation of the score's cross-sectional rank, or per pick in picks mode). Only `spread_top` is
   annualised (× 12), as the index says.
3. An era with fewer than `MIN_ERA_MONTHS = 12` measured months is **left out** of `stats`. Every
   float field of an `EraStats` that is present is finite. A t-statistic whose standard deviation
   is zero, or that has fewer than two months, is `0.0`. `top_turnover` is `0.0` when the era has
   no two consecutive measured months. `ic_mean` and `ic_t` are `None` in picks mode and never
   `None` in score mode.
4. `picks_hash` is `sha256` over the lines `"{decision date ISO}:{comma-joined sorted top-bucket symbols}\n"`
   of every measured month, in date order. The top bucket is chosen before names without a forward
   return are dropped, so the hash names what the signal picked, not what survived. In score mode
   a monotone transform of the scores keeps the hash. A pick set equal to a score's top bucket in
   every measured month has the same hash as that score.
5. `measure` never raises for a scorer that yields no measurable month: it returns a reading
   with empty `stats` (Decisions: picks mode with too few picks; `test_picks_mode_skips_a_month_with_too_few_picks`).
6. Additions not in the index: `Signal.scores`, `signal.visible`, `signal.MARKET_FIELDS`,
   `signal.signals_package`, `discover`'s optional `package` argument (for the duplicate-id
   test), `panel.PanelMonth`, `panel.PanelFrame`'s fields (`market`, `months`), `PanelReading.era`,
   `panel.top_size`, `panel.MIN_ERA_MONTHS`, `panel.CONTROLS`, `panel.MODES`, `panel.MARKET`.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/signal.py` | create (line 1) | `Signal`, `visible`, `discover`, constants |
| `engine/src/seer_engine/lab/signals/__init__.py` | create (line 1) | package docstring |
| `engine/src/seer_engine/lab/signals/s0001_twelve_minus_one_momentum.py` | create (line 1) | seed signal S0001, a known-positive check |
| `engine/src/seer_engine/lab/signals/s0002_hash_draw.py` | create (line 1) | seed signal S0002, a known-null check |
| `engine/src/seer_engine/lab/panel.py` | create (line 1) | frame builder, month reading, era statistics |
| `.claude/skills/explore-and-experiment-new-method/signal_template.py` | create (line 1) | the copy-me signal file, beside `method_template.py` |
| `engine/tests/test_lab_signals.py` | create (line 1) | signal contract tests and negative tests |
| `engine/tests/test_lab_panel.py` | create (line 1) | panel behaviour on a purpose-built synthetic market |

## Implementation Steps

Steps 1–4 make the registry exist and get it tested. Step 4 is the first check that can fail.
Steps 5–6 add the panel and its tests. Step 7 is the template. Run each step's tests before
starting the next one.

### Step 1: The signal registry
**File:** `engine/src/seer_engine/lab/signal.py:1` (new)
**Change:** New module. It reuses `METHOD_ID`, `SOURCE_KINDS` and `source_sha` from `lab.method`
and copies nothing. The cut a signal may see (`visible`) is a function here, so the panel
(phase 1) and the signal book (phase 5) apply one rule.
**Code:**
```python
"""A lab signal: one stock-ranking idea as a pure score function (stage one of the lab).

**Why signals exist beside methods.** A method is a whole book: a ranking, a width, a weighting, a
switch, a cadence and Gotrade's fees, run through the full simulator and judged on one equity
curve. Random twins of a book, holding the same dates and weights, spread wider than a typical
signal's effect (plan index ``SERA_SIGNAL_PANEL_PLAN.md``, "Why"), so a book cannot say whether
its ranking ordered anything. A signal is only the ranking: given what was knowable at a
month-end close, one number per pool member, higher is better. ``lab.panel`` measures it across
every member and every month at once -- the question a book could not answer -- and only a
signal that clears there goes on to a book.

**One file per signal, pre-registered by commit.** ``seer_engine/lab/signals/sNNNN_<slug>.py``
exports ``SIGNAL = Signal(...)``, exactly as a method file exports ``METHOD``. ``discover`` finds
them the way ``method.discover`` finds methods, and the commit that adds the file is the
pre-registration (``lab panel`` refuses an uncommitted or dirty file). ``source_sha`` *is*
``method.source_sha``, re-exported so nobody has to wonder whether the two hash differently.

**What a score function may read.** ``score(history, market, pool, data_date)``:

- ``history``: symbol -> ``History``. A signal reads only bars dated on or before ``data_date``,
  and at most ``lookback`` of them. ``Signal.scores`` hands it exactly that (``visible``), so
  through the panel the rule holds by construction. The book runner's prepared path, by contrast,
  relies on a contract test and not on a cut (``strategies/allocator.py``). Called directly with
  full histories, a signal must keep the rule itself. ``tests/test_lab_signals.py`` checks that
  both calls agree, and that changing or deleting every bar after ``data_date`` changes nothing.
- ``market``: the same cut applied to ``market.history``. Its other readers (``dividends``,
  ``series``, ``shares``, ``fundamentals``) are point in time through the date the signal passes
  them, and that date must be ``data_date``. A signal that reads one declares it in
  ``market_fields`` (the ``runner.market_fields`` vocabulary) so a store without it is refused.
- ``pool``: the members that pass ``tree_rank.SCREEN`` on ``data_date``, the names the signal is
  asked to rank. A symbol the signal leaves out, or scores NaN, has no opinion.

Pure, like a method file: no clock, randomness, files, network or printing (the AST walk in
``tests/test_lab_signals.py``). A deterministic draw hashes the symbol and the date, as S0002 does.

``MAX_LOOKBACK`` is 473: labkit's smoke market has 473 sessions, the same ceiling every lab
allocator is held to (``control_draw.FIXTURE_BARS``). The smoke contract test could not prove a
signal that needs more.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from collections.abc import Callable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

import numpy as np

from seer_engine.lab.method import METHOD_ID, SOURCE_KINDS, source_sha
from seer_engine.strategies.base import History, as_day

if TYPE_CHECKING:
    from seer_engine.backtest.market import Market

__all__ = [
    "MARKET_FIELDS",
    "MAX_LOOKBACK",
    "MODULE_NAME",
    "SIGNAL_ID",
    "ScoreFn",
    "Signal",
    "discover",
    "signals_package",
    "source_sha",
    "visible",
]

SIGNAL_ID = re.compile(r"S\d{4}")
MODULE_NAME = re.compile(r"s(\d{4})_[a-z0-9_]+")
MAX_LOOKBACK = 473  # labkit's smoke fixture, the same ceiling control_draw.FIXTURE_BARS names
MARKET_FIELDS: tuple[str, ...] = ("fundamentals", "dividends", "announcements", "series", "shares")
"""The ``Market`` readers a signal may declare: ``runner.market_fields``' vocabulary, verbatim."""

ScoreFn = Callable[[Mapping[str, History], "Market", AbstractSet[str], date], Mapping[str, float]]


def visible(market: Market, data_date: date, lookback: int) -> tuple[dict[str, History], Market]:
    """What a signal may see on ``data_date``: every symbol's last ``lookback`` bars dated on or
    before it, and ``market`` carrying only those.

    A symbol with no bar by ``data_date`` is left out. The cut histories are views of the
    originals, so this costs one ``searchsorted`` and one ``History`` per symbol. The ``Market``
    is rebuilt with ``dataclasses.replace``, so ``Market.bar`` and ``Market.last_bar_date`` agree
    with the cut too.
    """
    day = as_day(data_date)
    cut: dict[str, History] = {}
    for symbol, h in market.history.items():
        end = int(np.searchsorted(h.dates, day, side="right"))
        if end == 0:
            continue
        start = max(0, end - lookback)
        if start == 0 and end == len(h):
            cut[symbol] = h
            continue
        cut[symbol] = History(
            symbol,
            h.dates[start:end],
            h.open[start:end],
            h.high[start:end],
            h.low[start:end],
            h.close[start:end],
            h.volume[start:end],
        )
    return cut, replace(market, history=cut)


@dataclass(frozen=True)
class Signal:
    """One registered stock-ranking idea (module docstring).

    ``name`` says in plain words what it ranks on; ``family`` names that, as a method's family
    does. ``hypothesis`` is why the ranking should order next month's returns; ``expected_failure``
    is the way it most likely does not. Both are written before the panel runs and are frozen
    with the commit. ``lookback`` is how many bars through ``data_date`` the score reads, at most
    ``MAX_LOOKBACK``. ``idea_id`` is the queued idea row (a method id with status ``idea``) this
    signal answers, if any. ``seen_keys`` follow ``Method.seen_keys``' ``kind:value`` form.
    """

    id: str
    name: str
    family: str
    source_kind: str
    source_ref: str
    hypothesis: str
    expected_failure: str
    lookback: int
    score: ScoreFn
    market_fields: tuple[str, ...] = ()
    idea_id: str | None = None
    seen_keys: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or SIGNAL_ID.fullmatch(self.id) is None:
            raise ValueError(f"signal id must look like S0001, got {self.id!r}")
        for name in ("name", "family", "hypothesis", "expected_failure"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{self.id}: {name} must be a non-empty str")
        if self.source_kind not in SOURCE_KINDS:
            raise ValueError(f"{self.id}: source_kind must be one of {SOURCE_KINDS}, got {self.source_kind!r}")
        if not isinstance(self.source_ref, str):
            raise TypeError(f"{self.id}: source_ref must be a str")
        if self.source_kind != "knowledge" and not self.source_ref.strip():
            raise ValueError(f"{self.id}: a {self.source_kind} signal needs a source_ref (URL, citation or parent)")
        if isinstance(self.lookback, bool) or not isinstance(self.lookback, int):
            raise TypeError(f"{self.id}: lookback must be an int, got {type(self.lookback).__name__}")
        if not 1 <= self.lookback <= MAX_LOOKBACK:
            raise ValueError(f"{self.id}: lookback must be 1..{MAX_LOOKBACK}, got {self.lookback}")
        if not callable(self.score):
            raise TypeError(f"{self.id}: score must be callable")
        if not isinstance(self.market_fields, tuple):
            raise TypeError(f"{self.id}: market_fields must be a tuple")
        for name in self.market_fields:
            if name not in MARKET_FIELDS:
                raise ValueError(f"{self.id}: market field {name!r} is not one of {MARKET_FIELDS}")
        if self.idea_id is not None and (
            not isinstance(self.idea_id, str) or METHOD_ID.fullmatch(self.idea_id) is None
        ):
            raise ValueError(f"{self.id}: idea_id must be the queued idea's id, like M0001, got {self.idea_id!r}")
        if not isinstance(self.seen_keys, tuple):
            raise TypeError(f"{self.id}: seen_keys must be a tuple")
        for key in self.seen_keys:
            if not isinstance(key, str) or ":" not in key:
                raise ValueError(f"{self.id}: seen key {key!r} must look like kind:value")

    def scores(self, market: Market, pool: AbstractSet[str], data_date: date) -> dict[str, float]:
        """This signal's scores on ``data_date``, through the cut it may see (``visible``).

        The panel and the signal book both call this, never ``score`` directly, so the look-ahead
        rule is enforced in one place. TypeError when ``score`` returns anything but a Mapping.
        """
        history, view = visible(market, data_date, self.lookback)
        raw = self.score(history, view, frozenset(pool), data_date)
        if not isinstance(raw, Mapping):
            raise TypeError(f"{self.id}: score must return a Mapping of symbol -> float, got {type(raw).__name__}")
        return dict(raw)


def signals_package() -> ModuleType:
    return importlib.import_module("seer_engine.lab.signals")


def discover(package: ModuleType | None = None) -> dict[str, tuple[Signal, Path]]:
    """Signal id -> (SIGNAL, file path) for every ``sNNNN_*.py`` module, sorted by id.

    ``package`` defaults to ``seer_engine.lab.signals``; a test passes a throwaway one. TypeError
    when a module has no ``SIGNAL = Signal(...)``; ValueError when a module's number disagrees with
    its ``SIGNAL.id`` or two modules claim one id.
    """
    pkg = signals_package() if package is None else package
    out: dict[str, tuple[Signal, Path]] = {}
    for info in pkgutil.iter_modules(pkg.__path__):
        m = MODULE_NAME.fullmatch(info.name)
        if m is None:
            continue
        module = importlib.import_module(f"{pkg.__name__}.{info.name}")
        signal = getattr(module, "SIGNAL", None)
        if not isinstance(signal, Signal):
            raise TypeError(f"{module.__name__} has no SIGNAL = Signal(...)")
        if signal.id != f"S{m.group(1)}":
            raise ValueError(f"{module.__name__}: file number S{m.group(1)} != SIGNAL.id {signal.id}")
        if signal.id in out:
            raise ValueError(f"two signal files claim {signal.id}")
        out[signal.id] = (signal, Path(module.__file__).resolve())
    return dict(sorted(out.items()))
```
**Impact:** New module. Importing it imports `lab.method` (and through it `backtest.dev`), which
every lab command already imports.

### Step 2: The signals package
**File:** `engine/src/seer_engine/lab/signals/__init__.py:1` (new)
**Code:**
```python
"""Lab signals: one file per stock-ranking idea, ``sNNNN_<slug>.py`` exporting ``SIGNAL`` (see ``lab.signal``)."""
```
**Impact:** none.

### Step 3: The two seed signals
**File:** `engine/src/seer_engine/lab/signals/s0001_twelve_minus_one_momentum.py:1` (new)
**Change:** The known-positive check. It finds `data_date` with `index_of`, so it returns the same
scores on a full history as on the cut.
**Code:**
```python
"""S0001 — twelve-month price momentum, skipping the most recent month.

Source: Jegadeesh and Titman (1993), "Returns to Buying Winners and Selling Losers", Journal of
Finance 48(1). Idea: the panel's known-positive check, the ranking behind F4-MOM12 and the
lab's longest-running family. Over a broad pool, names that rose most over the last year
(excluding the last month, where short-term reversal lives) have tended to keep outperforming
over the next month. Its controlled slope is close to zero **by construction**: twelve-minus-one
momentum is one of the panel's four controls, so the check is on its raw rank correlation and
spread, never on its controlled slope.
Pure: no clock, randomness, files, network, printing. Reads bars dated <= data_date only.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from typing import Any

from seer_engine.lab.signal import Signal
from seer_engine.strategies.base import History

MOM_N = 252  # the window: the close 252 bars before data_date ...
SKIP = 21  # ... to the close 21 bars before it (f_factor's 12-1: c[-22] / c[-253] - 1)


def score(history: Mapping[str, History], market: Any, pool: AbstractSet[str], data_date: date) -> dict[str, float]:
    out: dict[str, float] = {}
    for symbol in sorted(pool):
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < MOM_N:
            continue
        base = float(h.close[i - MOM_N])
        if base > 0.0:
            out[symbol] = float(h.close[i - SKIP]) / base - 1.0
    return out


SIGNAL = Signal(
    id="S0001",
    name="Twelve-month price momentum, skipping the most recent month",
    family="stock-momentum",
    source_kind="paper",
    source_ref="Jegadeesh and Titman (1993), Returns to Buying Winners and Selling Losers, Journal of Finance 48(1)",
    hypothesis=(
        "Across the screened pool, last year's winners (the most recent month left out) earn more "
        "over the next month than the pool does: a positive mean rank correlation and a positive "
        "top-minus-pool spread on the dev store, the panel's known-positive check."
    ),
    expected_failure=(
        "Momentum crashes after market bottoms (2009) turn the 2009-2015 era flat or negative, and "
        "its controlled slope is near zero because momentum is itself one of the controls."
    ),
    lookback=MOM_N + 1,
    score=score,
)
```

**File:** `engine/src/seer_engine/lab/signals/s0002_hash_draw.py:1` (new)
**Change:** The known-null check. It is drawn again every month from a hash of the symbol and the
month, so it is the re-drawn placebo, not the sticky one.
**Code:**
```python
"""S0002 — a coin toss: a fresh hash-order draw every month.

Source: general knowledge. Idea: none, on purpose; this is the panel's known-null check. Each
month every pool member gets a number drawn from a hash of its symbol and the month, drawn again
every month (the re-drawn placebo, not the sticky one). Nothing about a company enters it, so a
panel that finds an edge here is measuring itself: its controls, its correction or a leak. It
should read as null in every era on every store.
Pure: hashlib only. No clock, randomness, files, network or printing.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from typing import Any

from seer_engine.lab.signal import Signal
from seer_engine.strategies.base import History

SALT = "S0002"


def draw(symbol: str, data_date: date) -> float:
    """A number in [0, 1) fixed by ``symbol`` and ``data_date``'s calendar month alone."""
    key = f"{SALT}:{symbol}:{data_date.year:04d}-{data_date.month:02d}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(key).digest()[:8], "big") / float(1 << 64)


def score(history: Mapping[str, History], market: Any, pool: AbstractSet[str], data_date: date) -> dict[str, float]:
    return {symbol: draw(symbol, data_date) for symbol in sorted(pool) if symbol in history}


SIGNAL = Signal(
    id="S0002",
    name="A coin toss: a fresh hash-order draw every month",
    family="stock-random-draw",
    source_kind="knowledge",
    source_ref="",
    hypothesis=(
        "None, on purpose. A ranking that knows nothing about a company should show no rank "
        "correlation, no spread and no controlled slope in any era; the panel's known-null check."
    ),
    expected_failure=(
        "A non-null reading here means the panel itself leaks or is miscalibrated, not that the "
        "coin knows something."
    ),
    lookback=1,
    score=score,
)
```
**Impact:** `discover()` now returns `S0001` and `S0002`.

### Step 4: Signal contract tests
**File:** `engine/tests/test_lab_signals.py:1` (new)
**Change:** The contract every signal file gets automatically (R1.1). The checks are module-level
functions, and negative tests prove each one fails on the signal it exists to catch. The
forbidden lists repeat `test_lab_methods.py:39-42` word for word. They are copied, not imported:
importing that module would import all 412 method files.
**Code:**
```python
"""Every lab signal file (``seer_engine/lab/signals/sNNNN_*.py``) gets these checks for free, as a
method file does in test_lab_methods.py:

- it is pure (no clock, randomness, network, files or printing): the same AST walk;
- its id is unique and matches its file number (``signal.discover`` refuses otherwise);
- it scores labkit's smoke market: pool symbols to numbers, the same answer twice;
- it does not look ahead: its score on a data date is unchanged when every bar dated after it is
  changed or deleted, and it equals the score through ``Signal.scores``' cut, so it reads no
  more bars than its lookback.

The negative tests at the bottom prove each check fails on the signal it exists to catch, so a
green run means something (acceptance criterion R1.1).
"""

from __future__ import annotations

import ast
import importlib
import math
import textwrap
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from labkit import MEMBER_STOCKS, smoke_market
from stratkit import mutate_from, truncate_before

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END
from seer_engine.lab.signal import MAX_LOOKBACK, Signal, discover, signals_package
from seer_engine.lab.tree_rank import month_ends

SIGNALS = discover()
TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / ".claude" / "skills" / "explore-and-experiment-new-method" / "signal_template.py"
)
PROBES = month_ends(date(2014, 12, 1), DEV_END)  # month-ends with 253+ smoke bars behind them
POOL = frozenset(MEMBER_STOCKS)

# test_lab_methods.py's lists, word for word: a signal is held to exactly what a method is.
FORBIDDEN_IMPORT_ROOTS = {"psycopg", "requests", "yfinance", "time", "random", "logging", "urllib",
                          "socket", "subprocess", "sqlite3", "os"}
FORBIDDEN_ATTRS = {"now", "utcnow", "today", "fromtimestamp", "random"}
FORBIDDEN_CALLS = {"print", "open", "input", "eval", "exec"}


def assert_pure(source: str, where: str) -> None:
    """AssertionError when ``source`` imports, reads or calls anything a signal may not."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = {a.name.split(".")[0] for a in node.names}
            assert not roots & FORBIDDEN_IMPORT_ROOTS, (where, roots)
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in FORBIDDEN_IMPORT_ROOTS, (where, node.module)
            assert node.module not in ("seer_engine.research", "seer_engine.lab.store"), (where, node.module)
        elif isinstance(node, ast.Attribute):
            assert node.attr not in FORBIDDEN_ATTRS, (where, node.attr)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in FORBIDDEN_CALLS, (where, node.func.id)


def _clean(scores) -> dict[str, float]:
    """Scores as plain floats, NaN (no opinion) left out, so two readings compare with ==."""
    out: dict[str, float] = {}
    for symbol, value in scores.items():
        v = float(value)
        if math.isfinite(v):
            out[str(symbol)] = v
    return out


def assert_no_lookahead(sig: Signal, market, pool, probes) -> int:
    """For each probe date d: the score read with full histories is unchanged when every bar dated
    after d is changed or deleted, and equals the score through ``Signal.scores``' cut. Returns how
    many probes scored at least one name.
    """
    nonempty = 0
    for d in probes:
        after = dates.next_session(d)
        direct = _clean(sig.score(market.history, market, pool, d))
        for name, cut in (("changed", mutate_from), ("deleted", truncate_before)):
            future = {s: cut(h, after) for s, h in market.history.items()}
            got = _clean(sig.score(future, replace(market, history=future), pool, d))
            assert got == direct, f"{sig.id} on {d}: look-ahead ({name} bars after the data date moved its score)"
        through_cut = _clean(sig.scores(market, pool, d))
        assert through_cut == direct, f"{sig.id} on {d}: reads more than its {sig.lookback}-bar lookback"
        nonempty += bool(direct)
    return nonempty


@pytest.fixture(scope="module")
def market():
    return smoke_market()


@pytest.mark.parametrize("sid", list(SIGNALS))
def test_signal_source_is_pure(sid):
    _, path = SIGNALS[sid]
    assert_pure(path.read_text(encoding="utf-8"), sid)


def test_the_seed_signals_are_registered():
    assert {"S0001", "S0002"} <= set(SIGNALS)


def test_signal_ids_are_unique_and_match_their_files():
    folder = Path(signals_package().__path__[0])
    files = sorted(p.name for p in folder.glob("s[0-9][0-9][0-9][0-9]_*.py"))
    assert len(files) == len(SIGNALS), (files, list(SIGNALS))
    for sid, (sig, path) in SIGNALS.items():
        assert sig.id == sid
        assert path.name.startswith(f"s{sid[1:]}_"), (sid, path.name)


@pytest.mark.parametrize("sid", list(SIGNALS))
def test_signal_scores_the_smoke_market(market, sid):
    sig, _ = SIGNALS[sid]
    nonempty = 0
    for d in PROBES:
        first = sig.scores(market, POOL, d)
        assert _clean(first) == _clean(sig.scores(market, POOL, d)), f"{sid} on {d}: not deterministic"
        for symbol, value in first.items():
            assert symbol in POOL, f"{sid} on {d}: scored {symbol!r}, which is not in the pool"
            assert not isinstance(value, bool) and isinstance(value, (int, float, np.integer, np.floating)), (
                f"{sid} on {d}: the score for {symbol} is a {type(value).__name__}"
            )
        nonempty += bool(_clean(first))
    assert nonempty > 0, f"{sid}: no probe scored any name, so the smoke run proved nothing"


@pytest.mark.parametrize("sid", list(SIGNALS))
def test_signal_does_not_look_ahead(market, sid):
    sig, _ = SIGNALS[sid]
    assert assert_no_lookahead(sig, market, POOL, PROBES) > 0


def test_the_signal_template_is_pure():
    assert TEMPLATE.is_file(), TEMPLATE
    assert_pure(TEMPLATE.read_text(encoding="utf-8"), TEMPLATE.name)


# ---- the checks catch what they exist to catch ---------------------------------------------


def _bad(sid: str, score, lookback: int) -> Signal:
    return Signal(
        id=sid, name="a broken signal", family="test-broken", source_kind="knowledge", source_ref="",
        hypothesis="exists to be caught", expected_failure="caught", lookback=lookback, score=score,
    )


def _peek(history, market, pool, data_date):
    """Scores each name on tomorrow's return: the look-ahead the check exists to catch."""
    out = {}
    for symbol in sorted(pool):
        h = history.get(symbol)
        i = None if h is None else h.index_of(data_date)
        if i is not None and i + 1 < len(h):
            out[symbol] = float(h.close[i + 1] / h.close[i] - 1.0)
    return out


def _long_reach(history, market, pool, data_date):
    """Declares five bars and reads sixty."""
    out = {}
    for symbol in sorted(pool):
        h = history.get(symbol)
        i = None if h is None else h.index_of(data_date)
        if i is not None and i >= 60:
            out[symbol] = float(h.close[i] / h.close[i - 60] - 1.0)
    return out


@pytest.mark.parametrize("source", [
    "import time\n",
    "import os.path\n",
    "from random import random\n",
    "import datetime\nx = datetime.date.today()\n",
    "print('hello')\n",
    "f = open('prices.csv')\n",
    "from seer_engine.lab.store import connect\n",
    "from seer_engine.research import load_store\n",
])
def test_the_purity_walk_catches_each_forbidden_reach(source):
    with pytest.raises(AssertionError):
        assert_pure(source, "bad")


def test_the_lookahead_check_catches_a_signal_that_reads_tomorrow(market):
    with pytest.raises(AssertionError, match="look-ahead"):
        assert_no_lookahead(_bad("S9101", _peek, 2), market, POOL, PROBES)


def test_the_lookahead_check_catches_a_signal_that_reads_past_its_lookback(market):
    with pytest.raises(AssertionError, match="lookback"):
        assert_no_lookahead(_bad("S9102", _long_reach, 5), market, POOL, PROBES)


_BODY = textwrap.dedent('''
    from seer_engine.lab.signal import Signal

    def score(history, market, pool, data_date):
        return {}

    SIGNAL = Signal(id="{sid}", name="n", family="test", source_kind="knowledge", source_ref="",
                    hypothesis="h", expected_failure="f", lookback=1, score=score)
''')


def _package(tmp_path, monkeypatch, name: str, files: dict[str, str]):
    pkg = tmp_path / name
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    for filename, sid in files.items():
        (pkg / filename).write_text(_BODY.replace("{sid}", sid), encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    return importlib.import_module(name)


def test_discover_refuses_two_files_with_one_id(tmp_path, monkeypatch):
    pkg = _package(tmp_path, monkeypatch, "dup_signal_pkg", {"s0001_one.py": "S0001", "s0001_two.py": "S0001"})
    with pytest.raises(ValueError, match="two signal files claim S0001"):
        discover(pkg)


def test_discover_refuses_a_file_number_that_disagrees_with_its_id(tmp_path, monkeypatch):
    pkg = _package(tmp_path, monkeypatch, "misnumbered_signal_pkg", {"s0003_x.py": "S0004"})
    with pytest.raises(ValueError, match="file number S0003"):
        discover(pkg)


@pytest.mark.parametrize("change,match", [
    ({"id": "M0001"}, "look like S0001"),
    ({"lookback": MAX_LOOKBACK + 1}, "lookback must be"),
    ({"lookback": 0}, "lookback must be"),
    ({"market_fields": ("bogus",)}, "market field"),
    ({"idea_id": "idea-7"}, "idea_id"),
    ({"source_kind": "paper", "source_ref": ""}, "needs a source_ref"),
    ({"seen_keys": ("nocolon",)}, "kind:value"),
])
def test_a_malformed_signal_declaration_is_refused(change, match):
    fields = dict(
        id="S9200", name="n", family="test", source_kind="knowledge", source_ref="",
        hypothesis="h", expected_failure="f", lookback=1, score=lambda h, m, p, d: {},
    )
    fields.update(change)
    with pytest.raises(ValueError, match=match):
        Signal(**fields)
```
**Impact:** Run `pytest tests/test_lab_signals.py -n 2` (see Verification). It must pass before
Step 5.

### Step 5: The panel
**File:** `engine/src/seer_engine/lab/panel.py:1` (new)
**Change:** New pure module. It reuses `tree_rank.month_ends` and `tree_rank.SCREEN` (whose
`mom_n`, `mom_skip` and `vol_n` become the control windows, so control and screen cannot drift
apart), `f_factor.factor_rows`, `f_factor.EXCLUDED`, `f_factor.DV_N`, the `indicators` window
functions, and `strategies.b.rank01`. It adds no dependency beyond numpy.
**Code:**
```python
"""The signal panel: does a ranking order next month's returns across the whole pool? (stage one)

A book backtest asks whether one concentrated portfolio beat SPY. Random twins of a book with the
same dates and weights spread wider than a typical signal's effect, so a book cannot tell whether
its ranking did anything (plan index ``SERA_SIGNAL_PANEL_PLAN.md``, "Why"). The panel asks the
earlier question, on every pool member and every month at once: across the screened pool, do
higher scores go with higher next-month returns, beyond what momentum, beta, size and volatility
already explain? It is pure: no database, no clock, no files. ``lab panel`` (phase 3) loads the
stores, calls this module and records what it returns.

**The frame** (``build_frame``, built once per research store and shared by every signal):

- *Decision dates*: the last NYSE session of each month (``tree_rank.month_ends``), from the first
  month with a pool, through the last whose forward month ends on or before ``DEV_END``. A store
  whose window ends after ``DEV_END`` is refused: the panel never reads the test window.
- *Universe*: the members on the decision date d (``Market.membership``, so point in time), SPY
  excluded, that have a bar dated d.
- *Pool*: the universe names that pass ``tree_rank.SCREEN``, which is F4's screen with no trend
  switch. It is computed with ``f_factor.factor_rows``, the single-window twin of
  ``FactorPrepared.rows_on`` (equal by f_factor's contract), because ``prepare_factor`` would hold
  every symbol's every-bar columns in memory beside the store when the panel reads only
  month-ends.
- *Forward return*: a total return, from the close of the name's first bar after d to its last
  close on or before the session after the next decision date, plus the cash dividends gone ex
  after the entry bar and on or before the exit bar (``ResearchData.dividends``, split-adjusted
  like the closes). A name with no bar at the exit takes its last close. A name with no bar after
  d by the exit is dropped from that month's statistics and counted (``dropped_exits``). That is
  the survivorship store's dead name whose last bar fell on the decision date.
- *Controls*, from bars dated <= d: 12-1 momentum and 60-session volatility, F4's own windows;
  252-session beta to SPY on SPY's sessions, a name's close carried forward over its own gaps;
  size as log 20-session mean dollar volume. ``Market.market_value`` covers only part of the dev
  member-days, so it is not used.

**One month's reading.** In *score* mode the scorer's numbers for pool names are the signal.
A month is measured when at least ``MIN_SCORED`` pool names are scored, the rank correlation is
defined, and the regression below has full rank. Each measured month gives:

- *rank correlation*: Spearman's (Pearson's on ``rank01`` ranks) between score and forward return,
  over scored pool names with a return;
- *top-minus-pool spread*: the mean return of the top bucket (``top_size``: the higher of
  ``TOP_MIN`` and a ``TOP_FRACTION`` share of the scored names, ties broken by symbol) minus the
  mean return of every pool name with a return. The bucket is chosen before dropped names leave
  it, so it is what the signal picked;
- *controlled slope*: a Fama-MacBeth cross-section, forward return on an intercept, the score's
  rank standardised to one standard deviation, and the four controls (each clipped at its 1st and
  99th percentile, then standardised). The slope is next-month return per one standard deviation
  of score.

In *picks* mode (``panel_replay``, phase 4) the scorer names a pick set: any universe name it
gives a finite value. A month needs ``MIN_PICKS`` picks. The spread is picks minus pool, the
slope is on a 0/1 pick dummy over the pool plus the picks, and there is no rank correlation.

**Eras.** A month belongs to ``pre2009`` or ``2009-2015`` by its decision date (``ERA_SPLIT``),
and every month belongs to ``all``. Per era, from the monthly series: the mean of each reading
and its t-statistic, mean / (sd / sqrt(months)), the spread annualised as twelve times its
monthly mean, and the mean share of the top bucket replaced between consecutive measured months.
An era with fewer than ``MIN_ERA_MONTHS`` measured months is left out, so a reading never
carries a t-statistic computed from a handful of months.

**What this module does not do.** No false-discovery correction and no verdict (``panel_verdict``,
phase 2). Nothing here counts toward the luck gate's N. No store loading and no recording
(``lab panel``, phase 3).
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

import numpy as np

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END
from seer_engine.lab.signal import Signal
from seer_engine.lab.tree_rank import SCREEN, month_ends
from seer_engine.strategies.b import rank01
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import DV_N, EXCLUDED, factor_rows
from seer_engine.strategies.indicators import mean_dollar_volume_window, return_window, stdev_return_window

if TYPE_CHECKING:
    from seer_engine.backtest.market import Market
    from seer_engine.research import ResearchData

RULE_ID = "panel-v1"
ERAS: tuple[str, ...] = ("all", "pre2009", "2009-2015")
ERA_SPLIT = date(2009, 1, 1)
TOP_FRACTION = 0.10  # top bucket = max(TOP_MIN, ceil(TOP_FRACTION * scored))
TOP_MIN = 10
MIN_SCORED = 30  # a month with fewer scored pool names is skipped ("score" mode)
MIN_PICKS = 5  # a month with fewer picks is skipped ("picks" mode)
MIN_ERA_MONTHS = 12  # an era with fewer measured months is left out of a reading
MARKET = "SPY"  # the beta control's market
MOM_N = SCREEN.mom_n  # 252: F4's 12-1 momentum, read off the screen so the two cannot drift
MOM_SKIP = SCREEN.mom_skip  # 21
VOL_N = SCREEN.vol_n  # 60
BETA_N = 252  # one-session returns in the beta window
WINDOW = max(MOM_N, BETA_N) + 1  # bars through d the controls read
CLIP_PCT = (1.0, 99.0)  # each control is clipped to these percentiles before it is standardised
CONTROLS: tuple[str, ...] = ("momentum", "beta", "volatility", "size")
MONTHS_PER_YEAR = 12
MODES: tuple[str, ...] = ("score", "picks")

Scorer = Callable[["Market", AbstractSet[str], date], Mapping[str, float]]
Mode = Literal["score", "picks"]


@dataclass(frozen=True, eq=False)
class PanelMonth:
    """One decision date's cross-section (module docstring, "The frame").

    ``symbols`` is the universe, sorted. ``in_pool``, ``ret`` and the rows of ``controls`` (one
    column per ``CONTROLS`` entry) are aligned with it. ``ret`` is NaN for a dropped name and a
    control is NaN where it cannot be read. ``pool`` is what a scorer is handed. ``row`` maps a
    symbol to its position. Every array is read-only.
    """

    day: date
    entry: date
    exit: date
    symbols: tuple[str, ...]
    in_pool: np.ndarray
    ret: np.ndarray
    controls: np.ndarray
    pool: frozenset[str]
    row: Mapping[str, int]


@dataclass(frozen=True, eq=False)
class PanelFrame:
    """A store's decision months, ascending, and the market every scorer reads through."""

    market: Market
    months: tuple[PanelMonth, ...]


@dataclass(frozen=True)
class EraStats:
    """One era's reading (module docstring, "Eras"). Every float is finite.

    ``spread_top`` is annualised; ``fm_slope`` is the mean *monthly* slope. ``ic_mean`` and
    ``ic_t`` are None in picks mode and only there. A t-statistic over fewer than two months, or
    over a series with no spread, is 0.0; ``top_turnover`` is 0.0 when no two measured months of
    the era are consecutive.
    """

    era: str
    months: int
    mean_pool: float
    mean_scored: float
    ic_mean: float | None
    ic_t: float | None
    spread_top: float
    spread_t: float
    fm_slope: float
    fm_t: float
    top_turnover: float


@dataclass(frozen=True)
class PanelReading:
    """What ``measure`` returns: one ``EraStats`` per era that has enough months, in ``ERAS`` order.

    ``picks_hash`` is sha256 over ``"{decision date}:{sorted top-bucket symbols, comma-joined}\\n"``
    for every measured month, ascending. Two panels with one pick set in every month share it.
    ``dropped_exits`` counts, over measured months, the names in the measured set with no bar
    after the decision date by the exit.
    """

    stats: tuple[EraStats, ...]
    picks_hash: str
    dropped_exits: int

    def era(self, name: str) -> EraStats | None:
        for s in self.stats:
            if s.era == name:
                return s
        return None


@dataclass(frozen=True)
class _MonthReading:
    index: int  # position in PanelFrame.months, so consecutive months can be told apart
    day: date
    pool: int  # pool names with a forward return
    scored: int  # pool names scored (score mode) or picks (picks mode)
    ic: float | None
    spread: float
    slope: float
    top: frozenset[str]
    dropped: int


def top_size(scored: int) -> int:
    """The top bucket for ``scored`` names: ``max(TOP_MIN, ceil(TOP_FRACTION * scored))``.

    The product is rounded before the ceiling so binary float noise cannot add a name.
    """
    return max(TOP_MIN, math.ceil(round(TOP_FRACTION * scored, 9)))


# --------------------------------------------------------------------------- the frame


def build_frame(data: ResearchData) -> PanelFrame:
    """The stock-by-month frame of ``data`` (module docstring). Built once per store.

    ValueError when the store's window ends after ``DEV_END`` (the panel reads the dev window
    only) or the store has too few SPY bars for the beta control.
    """
    window = data.window
    if window.end > DEV_END:
        raise ValueError(
            f"the panel reads the dev window only, which ends {DEV_END}; this store's "
            f"{window.name} window ends {window.end}"
        )
    market = data.market
    spy = market.history.get(MARKET)
    if spy is None or len(spy) <= BETA_N:
        raise ValueError(f"the panel needs {BETA_N + 1} or more {MARKET} bars for the beta control")
    calendar = month_ends(spy.dates[0].item(), window.end)
    paid = _dividend_index(data.dividends)
    months: list[PanelMonth] = []
    for day, following in zip(calendar, calendar[1:]):
        exit_ = dates.next_session(following)
        if exit_ > window.end:
            break
        month = _month(market, spy, paid, day, dates.next_session(day), exit_)
        if month is not None:
            months.append(month)
    return PanelFrame(market, tuple(months))


def _dividend_index(dividends: Mapping[str, Mapping[date, Decimal]]) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """symbol -> (ex-dates ascending, cumulative cash with a leading 0): a range sum is two lookups."""
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for symbol, by_date in dividends.items():
        items = sorted(by_date.items())
        if not items:
            continue
        days = np.array([d for d, _ in items], dtype="datetime64[D]")
        cum = np.concatenate(([0.0], np.cumsum([float(amount) for _, amount in items])))
        out[symbol] = (days, cum)
    return out


def _paid(index: Mapping[str, tuple[np.ndarray, np.ndarray]], symbol: str, after: np.datetime64,
          through: np.datetime64) -> float:
    """Cash per share gone ex in (``after``, ``through``]."""
    entry = index.get(symbol)
    if entry is None:
        return 0.0
    days, cum = entry
    lo = int(np.searchsorted(days, after, side="right"))
    hi = int(np.searchsorted(days, through, side="right"))
    return float(cum[hi] - cum[lo])


def _forward(h: History, index: Mapping[str, tuple[np.ndarray, np.ndarray]], day: date, exit_: date) -> float:
    """Total return from the first close after ``day`` to the last close on or before ``exit_``; NaN
    when there is no bar in between (the name is dropped) or a close is unusable."""
    i = int(np.searchsorted(h.dates, as_day(day), side="right"))
    stop = as_day(exit_)
    if i >= len(h) or h.dates[i] > stop:
        return math.nan
    j = int(np.searchsorted(h.dates, stop, side="right")) - 1
    c0 = float(h.close[i])
    c1 = float(h.close[j])
    if not (math.isfinite(c0) and math.isfinite(c1) and c0 > 0.0):
        return math.nan
    return (c1 + _paid(index, h.symbol, h.dates[i], h.dates[j])) / c0 - 1.0


def _beta(stock: np.ndarray, spy_close: np.ndarray) -> np.ndarray:
    """Each row's beta to SPY over aligned closes (rows x BETA_N + 1); NaN where a close is missing."""
    with np.errstate(divide="ignore", invalid="ignore"):
        r = stock[:, 1:] / stock[:, :-1] - 1.0
        m = spy_close[1:] / spy_close[:-1] - 1.0
        mc = m - m.mean()
        var = float(mc @ mc)
        if not (math.isfinite(var) and var > 0.0):
            return np.full(stock.shape[0], np.nan)
        rc = r - r.mean(axis=1, keepdims=True)
        out = (rc @ mc) / var
    out[~np.isfinite(out)] = np.nan
    return out


def _month(market: Market, spy: History, paid: Mapping[str, tuple[np.ndarray, np.ndarray]], day: date,
           entry: date, exit_: date) -> PanelMonth | None:
    """``day``'s cross-section, or None when no member passes the screen that day."""
    history = market.history
    members = market.membership.members_on(day)
    pool = frozenset(r.symbol for r in factor_rows(history, members, day, SCREEN))
    if not pool:
        return None
    symbols = tuple(sorted(
        s for s in members if s not in EXCLUDED and s in history and history[s].index_of(day) is not None
    ))
    k = len(symbols)
    close = np.full((k, WINDOW), np.nan)
    volume = np.full((k, WINDOW), np.nan)
    aligned = np.full((k, BETA_N + 1), np.nan)
    j = spy.index_of(day)
    spy_days = spy.dates[j - BETA_N : j + 1] if j is not None and j >= BETA_N else None
    ret = np.full(k, np.nan)
    for row, symbol in enumerate(symbols):
        h = history[symbol]
        i = h.index_of(day)
        lo = max(0, i + 1 - WINDOW)
        n = i + 1 - lo
        close[row, WINDOW - n :] = h.close[lo : i + 1]
        volume[row, WINDOW - n :] = h.volume[lo : i + 1]
        if spy_days is not None:
            idx = np.searchsorted(h.dates, spy_days, side="right") - 1
            if idx[0] >= 0:
                aligned[row] = h.close[idx]
        ret[row] = _forward(h, paid, day, exit_)
    with np.errstate(divide="ignore", invalid="ignore"):
        momentum = return_window(close, MOM_N, MOM_SKIP)
        volatility = stdev_return_window(close, VOL_N)
        dollar_volume = mean_dollar_volume_window(close, volume, DV_N)
        size = np.log(np.where(dollar_volume > 0.0, dollar_volume, np.nan))
    beta = _beta(aligned, spy.close[j - BETA_N : j + 1]) if spy_days is not None else np.full(k, np.nan)
    controls = np.column_stack((momentum, beta, volatility, size))
    controls[~np.isfinite(controls)] = np.nan
    in_pool = np.array([s in pool for s in symbols], dtype=bool)
    for arr in (in_pool, ret, controls):
        arr.setflags(write=False)
    return PanelMonth(day, entry, exit_, symbols, in_pool, ret, controls, pool,
                      {s: r for r, s in enumerate(symbols)})


# --------------------------------------------------------------------------- measuring


def signal_scorer(signal: Signal) -> Scorer:
    """A registered signal as a scorer. ``Signal.scores`` applies the look-ahead cut itself."""
    return signal.scores


def measure(frame: PanelFrame, scorer: Scorer, *, mode: Mode = "score") -> PanelReading:
    """``scorer`` read on every month of ``frame`` (module docstring, "One month's reading", "Eras").

    ``scorer(market, pool, d)`` returns symbol -> number. Symbols outside the month's universe are
    ignored, and in score mode so are those outside the pool. A NaN means no opinion. TypeError
    when it returns anything but a Mapping of numbers; ValueError for an unknown ``mode``.

    A scorer that never yields a measurable month (in picks mode: never ``MIN_PICKS`` picks, e.g.
    an arm whose switch is always off) is not an error: ``measure`` returns a reading with empty
    ``stats`` and never raises for it. Phase 4 reports such an arm as skipped (too few picks) and
    records nothing for it; phase 3 records nothing for a signal with no whole-window era.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    readings: list[_MonthReading] = []
    for index, month in enumerate(frame.months):
        values = _aligned(scorer(frame.market, month.pool, month.day), month)
        reading = _read(month, index, values, mode)
        if reading is not None:
            readings.append(reading)
    stats = tuple(s for s in (_era_stats(era, readings) for era in ERAS) if s is not None)
    return PanelReading(stats, _picks_hash(readings), sum(r.dropped for r in readings))


def _aligned(raw: object, month: PanelMonth) -> np.ndarray:
    if not isinstance(raw, Mapping):
        raise TypeError(f"a scorer returns a Mapping of symbol -> number, got {type(raw).__name__}")
    out = np.full(len(month.symbols), np.nan)
    for symbol, value in raw.items():
        j = month.row.get(symbol)
        if j is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
            raise TypeError(f"the score for {symbol} on {month.day} must be a number, got {type(value).__name__}")
        out[j] = float(value)
    out[~np.isfinite(out)] = np.nan
    return out


def _read(month: PanelMonth, index: int, values: np.ndarray, mode: str) -> _MonthReading | None:
    """One month's reading, or None when the month cannot be measured."""
    has_ret = np.isfinite(month.ret)
    base = month.in_pool & has_ret
    if not base.any():
        return None
    known = np.isfinite(month.controls).all(axis=1)
    if mode == "score":
        opinion = month.in_pool & np.isfinite(values)
        scored = int(opinion.sum())
        if scored < MIN_SCORED:
            return None
        selected = _top(month, values, opinion, top_size(scored))
        valid = opinion & has_ret
        if int(valid.sum()) < 3:
            return None
        ic = _corr(rank01(values[valid]), rank01(month.ret[valid]))
        if ic is None:
            return None
        sample = valid & known
        x = _rank_z(values[sample])
        dropped = int((month.in_pool & ~has_ret).sum())
    else:
        opinion = np.isfinite(values)
        scored = int(opinion.sum())
        if scored < MIN_PICKS:
            return None
        selected = opinion
        ic = None
        sample = (base | (opinion & has_ret)) & known
        x = opinion[sample].astype(np.float64)
        dropped = int(((month.in_pool | opinion) & ~has_ret).sum())
    held = selected & has_ret
    if x is None or not held.any():
        return None
    slope = _slope(month.ret[sample], x, month.controls[sample])
    if slope is None:
        return None
    spread = float(month.ret[held].mean() - month.ret[base].mean())
    top = frozenset(month.symbols[j] for j in np.flatnonzero(selected))
    return _MonthReading(index, month.day, int(base.sum()), scored, ic, spread, slope, top, dropped)


def _top(month: PanelMonth, values: np.ndarray, opinion: np.ndarray, k: int) -> np.ndarray:
    """The ``k`` highest-scored names among ``opinion``, ties broken by symbol ascending."""
    order = sorted((int(j) for j in np.flatnonzero(opinion)), key=lambda j: (-values[j], month.symbols[j]))[:k]
    out = np.zeros(len(month.symbols), dtype=bool)
    out[order] = True
    return out


def _corr(a: np.ndarray, b: np.ndarray) -> float | None:
    """Pearson's correlation, or None when either side has no spread."""
    if a.shape[0] < 3:
        return None
    a = a - a.mean()
    b = b - b.mean()
    den = math.sqrt(float(a @ a) * float(b @ b))
    if not den > 0.0:
        return None
    return float(a @ b) / den


def _rank_z(v: np.ndarray) -> np.ndarray | None:
    """``v``'s ranks standardised to mean 0, sd 1; None when there is no spread."""
    if v.shape[0] < 2:
        return None
    r = rank01(np.ascontiguousarray(v, dtype=np.float64))
    sd = float(r.std())
    if not sd > 0.0:
        return None
    return (r - r.mean()) / sd


def _clip_z(c: np.ndarray) -> np.ndarray | None:
    """A control clipped to its ``CLIP_PCT`` percentiles, then standardised; None when constant."""
    lo, hi = np.percentile(c, CLIP_PCT)
    c = np.clip(c, lo, hi)
    sd = float(c.std())
    if not sd > 0.0:
        return None
    return (c - c.mean()) / sd


def _slope(y: np.ndarray, x: np.ndarray, controls: np.ndarray) -> float | None:
    """The coefficient on ``x`` in y ~ 1 + x + controls, or None when the cross-section is too small
    or the design is rank-deficient (a constant control, or ``x`` collinear with the rest)."""
    n = y.shape[0]
    if n < MIN_SCORED:
        return None
    columns = [np.ones(n), x]
    for c in controls.T:
        z = _clip_z(c)
        if z is None:
            return None
        columns.append(z)
    design = np.column_stack(columns)
    if np.linalg.matrix_rank(design) < design.shape[1]:
        return None
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    return float(coef[1])


def _in_era(era: str, day: date) -> bool:
    if era == "all":
        return True
    if era == "pre2009":
        return day < ERA_SPLIT
    return day >= ERA_SPLIT


def _t(x: np.ndarray) -> float:
    n = x.shape[0]
    if n < 2:
        return 0.0
    sd = float(np.std(x, ddof=1))
    if not sd > 0.0:
        return 0.0
    return float(np.mean(x)) / (sd / math.sqrt(n))


def _turnover(rows: list[_MonthReading]) -> float:
    """Mean share of the top bucket replaced between consecutive measured months; 0.0 with no pair."""
    shares = [
        1.0 - len(a.top & b.top) / len(b.top)
        for a, b in zip(rows, rows[1:])
        if b.index == a.index + 1 and b.top
    ]
    return float(np.mean(shares)) if shares else 0.0


def _era_stats(era: str, readings: list[_MonthReading]) -> EraStats | None:
    rows = [r for r in readings if _in_era(era, r.day)]
    if len(rows) < MIN_ERA_MONTHS:
        return None
    spreads = np.array([r.spread for r in rows])
    slopes = np.array([r.slope for r in rows])
    if any(r.ic is None for r in rows):
        ic_mean: float | None = None
        ic_t: float | None = None
    else:
        ics = np.array([r.ic for r in rows])
        ic_mean = float(ics.mean())
        ic_t = _t(ics)
    return EraStats(
        era=era,
        months=len(rows),
        mean_pool=float(np.mean([r.pool for r in rows])),
        mean_scored=float(np.mean([r.scored for r in rows])),
        ic_mean=ic_mean,
        ic_t=ic_t,
        spread_top=float(spreads.mean()) * MONTHS_PER_YEAR,
        spread_t=_t(spreads),
        fm_slope=float(slopes.mean()),
        fm_t=_t(slopes),
        top_turnover=_turnover(rows),
    )


def _picks_hash(readings: list[_MonthReading]) -> str:
    digest = hashlib.sha256()
    for r in readings:
        digest.update(f"{r.day.isoformat()}:{','.join(sorted(r.top))}\n".encode("utf-8"))
    return digest.hexdigest()
```
**Impact:** New module. Importing it imports `tree_rank`, and through that scikit-learn, which
every lab command already imports. Nothing calls it yet.

### Step 6: Panel tests on a purpose-built synthetic market
**File:** `engine/tests/test_lab_panel.py:1` (new)
**Change:** labkit's smoke market (473 sessions, 8 members) cannot fill a cross-section of 30 or an
era of 12 months, so this module builds its own market. It plants two hidden signals in
next-month returns: one readable in the decision date's volume in every month, one in its open
from 2009 only. It adds a dividend, a name whose bars stop on a decision date, and a name whose
bars stop mid-month. The tests assert what a caller can observe: the statistics, the frame's
returns and the hash. They do not touch private helpers.
**Code:**
```python
"""lab.panel: the stock-by-month signal panel, on a synthetic market built for it.

labkit's smoke market has 473 sessions and eight member stocks: too few names for a cross-section
of MIN_SCORED and too few months for an era. So this module builds its own market: sixty members
plus SPY, from 2005 to DEV_END, with two hidden signals planted in next month's returns and made
readable on the decision date's bar. One is in the bar's volume, in every month; the other is
in its open, from 2009 only. There is also a dividend, a name whose bars stop on a decision date
and a name whose bars stop mid-month. Randomness lives in this fixture, under a fixed seed. The
signals under test stay pure.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import replace
from datetime import date
from decimal import Decimal

import numpy as np
import pytest
from labkit import smoke_data, smoke_test_data

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END
from seer_engine.backtest.market import Market, Membership
from seer_engine.lab import panel
from seer_engine.lab.signal import Signal
from seer_engine.lab.signals.s0002_hash_draw import SIGNAL as HASH_DRAW
from seer_engine.lab.tree_rank import month_ends
from seer_engine.research import ResearchData
from seer_engine.strategies.base import History

FIRST = date(2005, 1, 3)
DAYS = dates.sessions(FIRST, DEV_END)
ENDS = month_ends(FIRST, DEV_END)
STOCKS = tuple(f"N{k:03d}" for k in range(60))
GONE = "GONE"  # last bar dated on a decision date: no bar after it, so dropped and counted
HALF = "HALF"  # last bar mid-month: that close is its exit
NAMES = STOCKS + (GONE, HALF)
GONE_DAY = date(2010, 6, 30)  # the last session of June 2010, a decision date
HALF_DAY = date(2011, 3, 15)  # mid-month, inside the forward month of 2011-02-28
PAYER = "N000"
EX_DAY = date(2012, 5, 15)  # inside the forward month of 2012-04-30 (entry 05-01, exit 06-01)
DIVIDEND = Decimal("1.50")
BETAS = {s: 0.5 + k / len(NAMES) for k, s in enumerate(NAMES)}
SEED = 20261113


def _history(symbol: str, days, open_, close, volume) -> History:
    open_ = np.asarray(open_, dtype=np.float64)
    close = np.asarray(close, dtype=np.float64)
    high = np.maximum(open_, close) * 1.01
    low = np.minimum(open_, close) * 0.99
    return History(symbol, np.array(days, dtype="datetime64[D]"), open_, high, low, close,
                   np.asarray(volume, dtype=np.float64))


def _forward_windows() -> np.ndarray:
    """For each session, the decision whose forward month it closes in (entry, exit]; -1 for none."""
    pos = {d: t for t, d in enumerate(DAYS)}
    out = np.full(len(DAYS), -1)
    for q in range(len(ENDS) - 1):
        lo = pos[dates.next_session(ENDS[q])]
        hi = pos.get(dates.next_session(ENDS[q + 1]))
        if hi is None:
            break
        out[lo + 1 : hi + 1] = q
    return out


def _build() -> ResearchData:
    rng = np.random.default_rng(SEED)
    n = len(DAYS)
    win = _forward_windows()
    live = win >= 0
    length = np.bincount(win[live], minlength=len(ENDS))
    recent = np.array([d >= panel.ERA_SPLIT for d in ENDS])
    row_of = {d: t for t, d in enumerate(DAYS)}
    end_rows = np.array([row_of[d] for d in ENDS])
    z_volume = rng.standard_normal((len(NAMES), len(ENDS)))
    z_open = rng.standard_normal((len(NAMES), len(ENDS)))
    market_ret = 0.0003 + 0.009 * rng.standard_normal(n)
    history: dict[str, History] = {}
    for k, symbol in enumerate(NAMES):
        q = win[live]
        planted = np.zeros(n)
        planted[live] = (0.02 * z_volume[k, q] + 0.02 * z_open[k, q] * recent[q]) / length[q]
        logret = BETAS[symbol] * market_ret + 0.012 * rng.standard_normal(n) + planted
        close = 100.0 * np.exp(np.cumsum(logret))
        open_ = np.concatenate((close[:1], close[:-1]))
        open_[end_rows] = close[end_rows] * (1.0 + 0.01 * z_open[k])
        volume = np.full(n, 1_000_000.0)
        volume[end_rows] = 1_000_000.0 * np.exp(0.5 * z_volume[k])
        stop = n
        if symbol == GONE:
            stop = row_of[GONE_DAY] + 1
        elif symbol == HALF:
            stop = row_of[HALF_DAY] + 1
        history[symbol] = _history(symbol, DAYS[:stop], open_[:stop], close[:stop], volume[:stop])
    spy_close = 100.0 * np.exp(np.cumsum(market_ret))
    history["SPY"] = _history("SPY", DAYS, np.concatenate((spy_close[:1], spy_close[:-1])), spy_close,
                              np.full(n, 50_000_000.0))
    market = Market(
        history=history,
        membership=Membership(intervals=tuple((s, DAYS[0], None) for s in NAMES)),
        fx=((DAYS[0], Decimal("2000")),),
    )
    return ResearchData(
        market=market,
        dividends={PAYER: {EX_DAY: DIVIDEND}},
        spy_dividends=(),
        fingerprint="panel-fixture",
        manifest={},
        price_fingerprint="panel-fixture",
    )


def _planted_signal(sid: str, score, lookback: int = 1) -> Signal:
    return Signal(
        id=sid, name="planted in the fixture", family="test-planted", source_kind="knowledge",
        source_ref="", hypothesis="planted", expected_failure="none: it is planted",
        lookback=lookback, score=score,
    )


def _volume_score(history, market, pool, data_date):
    out = {}
    for symbol in sorted(pool):
        h = history.get(symbol)
        i = None if h is None else h.index_of(data_date)
        if i is not None:
            out[symbol] = float(np.log(h.volume[i]))
    return out


def _open_score(history, market, pool, data_date):
    out = {}
    for symbol in sorted(pool):
        h = history.get(symbol)
        i = None if h is None else h.index_of(data_date)
        if i is not None:
            out[symbol] = float(h.open[i] / h.close[i] - 1.0)
    return out


PLANTED = _planted_signal("S9001", _volume_score)  # every month
RECENT = _planted_signal("S9002", _open_score)  # 2009 on only


def _top10_picks(market, pool, data_date):
    scores = PLANTED.scores(market, pool, data_date)
    ranked = sorted((s for s in scores if s in pool), key=lambda s: (-scores[s], s))[:10]
    return {s: 1.0 for s in ranked}


@pytest.fixture(scope="module")
def data() -> ResearchData:
    return _build()


@pytest.fixture(scope="module")
def frame(data) -> panel.PanelFrame:
    return panel.build_frame(data)


@pytest.fixture(scope="module")
def planted(frame) -> panel.PanelReading:
    return panel.measure(frame, panel.signal_scorer(PLANTED))


def _month(frame, day: date) -> panel.PanelMonth:
    return next(m for m in frame.months if m.day == day)


def _close_on(h: History, d: date) -> float:
    i = h.index_of(d)
    assert i is not None, (h.symbol, d)
    return float(h.close[i])


# ---- the frame ------------------------------------------------------------------------------


def test_frame_months_run_month_end_to_month_end_inside_the_dev_window(frame):
    months = frame.months
    first = next(e for e in ENDS if DAYS.index(e) >= 252)  # SCREEN needs 253 bars through d
    assert months[0].day == first
    assert [m.day for m in months] == sorted(m.day for m in months)
    for m, following in zip(months, months[1:]):
        assert m.day in ENDS
        assert m.entry == dates.next_session(m.day)
        assert m.exit == dates.next_session(following.day)
    assert months[-1].exit <= DEV_END
    # ENDS[-1] (2015-09-30) has no forward month inside the window, so the last decision is ENDS[-2].
    assert months[-1].day == ENDS[-2]


def test_the_forward_return_is_a_total_return_with_the_dividend(frame, data):
    m = _month(frame, date(2012, 4, 30))
    entry, exit_ = date(2012, 5, 1), date(2012, 6, 1)
    payer = data.market.history[PAYER]
    expected = (_close_on(payer, exit_) + float(DIVIDEND)) / _close_on(payer, entry) - 1.0
    assert m.ret[m.row[PAYER]] == pytest.approx(expected, rel=1e-12)
    other = data.market.history["N001"]
    assert m.ret[m.row["N001"]] == pytest.approx(_close_on(other, exit_) / _close_on(other, entry) - 1.0, rel=1e-12)


def test_a_name_whose_bars_stop_on_the_decision_date_is_dropped_and_counted(frame):
    m = _month(frame, GONE_DAY)
    assert GONE in m.pool
    assert math.isnan(m.ret[m.row[GONE]])
    later = frame.months[frame.months.index(m) + 1]
    assert GONE not in later.symbols
    assert panel.measure(frame, panel.signal_scorer(HASH_DRAW)).dropped_exits == 1


def test_a_name_whose_bars_stop_mid_month_exits_at_its_last_close(frame, data):
    m = _month(frame, date(2011, 2, 28))
    half = data.market.history[HALF]
    expected = _close_on(half, HALF_DAY) / _close_on(half, date(2011, 3, 1)) - 1.0
    assert m.ret[m.row[HALF]] == pytest.approx(expected, rel=1e-12)


def test_every_pool_name_has_all_four_controls_and_beta_tracks_the_planted_beta(frame):
    for m in frame.months:
        assert np.isfinite(m.controls[m.in_pool]).all(), m.day
    m = _month(frame, date(2012, 4, 30))
    names = [s for s in STOCKS if s in m.row]
    measured = np.array([m.controls[m.row[s], panel.CONTROLS.index("beta")] for s in names])
    planted = np.array([BETAS[s] for s in names])
    assert np.corrcoef(measured, planted)[0, 1] > 0.8


def test_build_frame_refuses_a_test_window_store():
    with pytest.raises(ValueError, match="dev window only"):
        panel.build_frame(smoke_test_data())


def test_build_frame_refuses_a_store_without_spy():
    d = smoke_data()
    market = replace(d.market, history={s: h for s, h in d.market.history.items() if s != "SPY"})
    with pytest.raises(ValueError, match="SPY"):
        panel.build_frame(replace(d, market=market))


# ---- the readings ---------------------------------------------------------------------------


def test_a_planted_signal_is_recovered_in_every_era(planted):
    assert [s.era for s in planted.stats] == list(panel.ERAS)
    for s in planted.stats:
        assert s.months >= panel.MIN_ERA_MONTHS, s
        assert s.ic_mean is not None and s.ic_mean > 0.0 and s.ic_t > 5.0, s
        assert s.spread_top > 0.0 and s.spread_t > 5.0, s
        assert s.fm_slope > 0.0 and s.fm_t > 5.0, s
        assert s.mean_scored >= panel.MIN_SCORED, s
        assert 0.5 < s.top_turnover <= 1.0, s  # drawn again every month, so the bucket churns


def test_a_null_signal_reads_as_null(frame):
    reading = panel.measure(frame, panel.signal_scorer(HASH_DRAW))
    s = reading.era("all")
    assert s is not None and s.months >= panel.MIN_ERA_MONTHS
    assert abs(s.ic_t) < 4.0, s
    assert abs(s.spread_t) < 4.0, s
    assert abs(s.fm_t) < 4.0, s


def test_the_era_split_puts_each_month_in_exactly_one_era(frame):
    reading = panel.measure(frame, panel.signal_scorer(RECENT))
    whole, before, after = (reading.era(e) for e in panel.ERAS)
    assert whole.months == before.months + after.months
    assert after.fm_t > 5.0, after  # planted from 2009 on
    assert abs(before.fm_t) < 4.0, before  # and not before


def test_picks_mode_reads_a_pick_set_and_shares_its_hash_with_the_matching_score(frame, planted):
    picks = panel.measure(frame, _top10_picks, mode="picks")
    s = picks.era("all")
    assert s.ic_mean is None and s.ic_t is None
    assert s.spread_top > 0.0 and s.spread_t > 5.0, s
    assert s.fm_slope > 0.0 and s.fm_t > 5.0, s
    assert picks.picks_hash == planted.picks_hash


def test_picks_mode_skips_a_month_with_too_few_picks(frame):
    def three(market, pool, data_date):
        return {s: 1.0 for s in sorted(pool)[:3]}

    reading = panel.measure(frame, three, mode="picks")
    assert reading.stats == ()
    assert reading.picks_hash == hashlib.sha256(b"").hexdigest()
    assert reading.dropped_exits == 0


def test_the_picks_hash_is_stable_and_names_the_pick_set(frame, planted):
    assert panel.measure(frame, panel.signal_scorer(PLANTED)) == planted

    def stretched(market, pool, data_date):
        return {s: 2.0 * v + 1.0 for s, v in PLANTED.scores(market, pool, data_date).items()}

    assert panel.measure(frame, stretched).picks_hash == planted.picks_hash
    assert panel.measure(frame, panel.signal_scorer(HASH_DRAW)).picks_hash != planted.picks_hash


def test_the_scorer_sees_only_bars_through_the_data_date_and_within_its_lookback(frame):
    seen: list[tuple[date, date, date, int]] = []

    def probe(history, market, pool, data_date):
        seen.append((
            data_date,
            max(h.dates[-1].item() for h in history.values()),
            max(h.dates[-1].item() for h in market.history.values()),
            max(len(h) for h in history.values()),
        ))
        return {}

    panel.measure(frame, panel.signal_scorer(_planted_signal("S9003", probe, lookback=40)))
    assert len(seen) == len(frame.months)
    for d, last, market_last, longest in seen:
        assert last <= d and market_last <= d and longest <= 40, (d, last, market_last, longest)


def test_scores_outside_the_pool_are_ignored_and_a_non_number_is_refused(frame, planted):
    def noisy(market, pool, data_date):
        out = PLANTED.scores(market, pool, data_date)
        out.update({"SPY": 1e9, "NOT-A-MEMBER": 1e9})
        return out

    assert panel.measure(frame, noisy) == planted

    with pytest.raises(TypeError, match="must be a number"):
        panel.measure(frame, lambda market, pool, data_date: {"N001": "high"})


def test_measure_refuses_an_unknown_mode(frame):
    with pytest.raises(ValueError, match="mode"):
        panel.measure(frame, panel.signal_scorer(HASH_DRAW), mode="ranks")


@pytest.mark.parametrize("scored,size", [(30, 10), (99, 10), (101, 11), (110, 11), (500, 50)])
def test_top_size(scored, size):
    assert panel.top_size(scored) == size
```
**Impact:** Run `pytest tests/test_lab_panel.py -n 2`. It must pass. If the null test ever reads
`|t| >= 4` on this fixed seed, do not change the seed: investigate the panel. A null reading
that large is the leak this test exists to catch.

Note on `test_scores_outside_the_pool_are_ignored...`: `"SPY"` is in the market but not in
any month's universe (`EXCLUDED`), so `_aligned` drops it before scoring.

### Step 7: The signal template
**File:** `.claude/skills/explore-and-experiment-new-method/signal_template.py:1` (new)
**Change:** The copy-me file beside `method_template.py`. Step 4's
`test_the_signal_template_is_pure` keeps it pure. Phase 7 owns the SKILL.md text that points to it.
**Code:**
```python
"""SNNNN — <one-line name: what it ranks on, in plain words>.

Source: <URL / citation / "variation of S00xx" / general knowledge>.
Idea: <two or three sentences: why a higher score should mean a higher next-month return>.

Copy to engine/src/seer_engine/lab/signals/sNNNN_<slug>.py (the next free id comes from
`lab next-signal-id`), replace every SNNNN, then commit it: the commit is the pre-registration.
Then run `lab panel SNNNN`.
A signal is only the ranking: no width, weights, switch or cadence. Those belong to the one
standard chassis a signal is booked on once it clears the panel.
Pure: no clock, randomness, files, network or printing. Read only bars dated <= data_date, and
no more than `lookback` of them. Find data_date with `h.index_of` so the score is the same on a
full history as on the cut `lab panel` hands you (tests/test_lab_signals.py checks both).
Higher is better. Leave a name out, or score it NaN, when you have no opinion.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from typing import Any

from seer_engine.lab.signal import Signal
from seer_engine.strategies.base import History

LOOKBACK_N = 126  # bars back the score compares against


def score(history: Mapping[str, History], market: Any, pool: AbstractSet[str], data_date: date) -> dict[str, float]:
    out: dict[str, float] = {}
    for symbol in sorted(pool):
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)  # every pool name has a bar dated data_date
        if i is None or i < LOOKBACK_N:
            continue
        base = float(h.close[i - LOOKBACK_N])
        if base > 0.0:
            out[symbol] = float(h.close[i]) / base - 1.0  # <your score>
    return out


SIGNAL = Signal(
    id="SNNNN",
    name="<what it ranks on, in plain words>",
    family="stock-<what it ranks on>",
    source_kind="knowledge",  # paper | blog | github | knowledge | variation
    source_ref="",  # required unless source_kind is "knowledge"
    hypothesis="<why a higher score means a higher next-month return, written before the panel runs>",
    expected_failure="<the way it most likely fails: an era, a control that explains it, a dead-name effect>",
    lookback=LOOKBACK_N + 1,  # bars through data_date the score reads, at most 473
    score=score,
    market_fields=(),  # e.g. ("dividends",) when the score reads market.dividends
    idea_id=None,  # "M0xxx" when this answers a queued idea row
)
```
**Impact:** none on code. It is AST-parsed by one test.

## Principles applied

- Laziness protocol: `signal.py` reuses `method.SOURCE_KINDS`, `METHOD_ID` and `source_sha`.
  `panel.py` reuses `tree_rank.month_ends`/`SCREEN`, `f_factor.factor_rows`/`EXCLUDED`/`DV_N`, the
  `indicators` window functions and `b.rank01`. Nothing is copied, and the control windows are
  read off `SCREEN` so they cannot drift from the screen.
- Laziness protocol: the pool comes from `factor_rows` (single window, equal to `rows_on` by
  f_factor's contract), not `prepare_factor` (whole-history columns held beside the store), because
  the panel reads only month-ends. Recorded as contract deviation 1.
- Encode lessons in structure: the book runner's no-look-ahead guarantee rests on a contract test
  (`strategies/allocator.py:8-12`). For signals the cut is a function (`signal.visible`, applied
  by `Signal.scores`) that both the panel and phase 5's book call. The scorer's market is rebuilt
  on the cut histories too, so `market.history` cannot leak. Test
  `test_the_scorer_sees_only_bars_through_the_data_date_and_within_its_lookback` holds it.
- Make illegal states unrepresentable: `Signal.__post_init__` refuses a lookback above 473, an
  unknown market field, an idea id that is not a method id, and a non-knowledge source with no
  reference. `EraStats` never carries NaN (an undefined t is 0.0, a thin era is left out). Phase
  2's `NOT NULL REAL` columns therefore never meet a NaN, which SQLite would store as NULL.
- Boundary discipline: the window check lives once, at the top of `build_frame`, and the scorer's
  output is validated once, in `_aligned`. The month logic below trusts both.
- Test behavior, not implementation: every test asserts on `measure`'s statistics, the frame's
  returns or `discover`'s result. The contract checks are proved by negative tests that feed each
  one the broken signal it exists to catch (Step 4).
- Prove it works: Proof runs the panel on the real dev and survivorship stores (J4, J5), as well
  as the synthetic market.

## Verification

All commands run from the worktree, `W=/home/miftah/.worktrees/seer/sera-signal-panel`, with
`PY=/home/miftah/seer/engine/.venv/bin/python`. No command in this phase writes to any lab database.

**Build:** `cd $W && /home/miftah/seer/engine/.venv/bin/ruff check engine`
**Tests:** `cd $W/engine && PYTHONPATH=$W/engine/src $PY -m pytest tests/test_lab_signals.py tests/test_lab_panel.py -n 2`
**Proof:** the registry discovers the seed signals and its contract test fails on each kind of
broken signal. The panel computes every R2.1 figure for every era, on a market where the right
answer is planted and on the two real research stores.
- Harness: `.claude/skills/verify-seer` exists. This phase adds no CLI, page or row, so none of
  `verify.sh`'s surfaces (`api`, `ui`, `lab`, `labsql`) reach it. The journeys run pytest and
  Python drives against the live worktree code and the main checkout's research stores, read-only.
- Feature-map entries: none. Phase 1 adds nothing a user can do; phase 3 adds `features/signal-panel.md`.
- Journeys:
  - **J1** · traces R1.1 — `cd $W/engine && PYTHONPATH=$W/engine/src $PY -m pytest tests/test_lab_signals.py -n 2 -q` → passes when pytest reports 0 failed and 0 errors, and the passed tests include `test_the_seed_signals_are_registered`, `test_signal_source_is_pure[S0001]`, `test_signal_does_not_look_ahead[S0002]`, every `test_the_purity_walk_catches_each_forbidden_reach[...]`, `test_the_lookahead_check_catches_a_signal_that_reads_tomorrow`, `test_the_lookahead_check_catches_a_signal_that_reads_past_its_lookback` and `test_discover_refuses_two_files_with_one_id` (check with `-v | grep PASSED`)
  - **J2** · traces R1.1 — run this mutation drive (it copies `engine/src` to a temp dir, drops one broken signal file at a time into the copy's `lab/signals/`, and runs the real contract test against the copy):
    ```bash
    W=/home/miftah/.worktrees/seer/sera-signal-panel; PY=/home/miftah/seer/engine/.venv/bin/python
    S=$(mktemp -d); cp -r "$W/engine/src" "$S/src"; find "$S/src" -name __pycache__ -prune -exec rm -rf {} +
    SIG="$S/src/seer_engine/lab/signals"
    run() { (cd "$W/engine" && PYTHONPATH="$S/src" "$PY" -m pytest tests/test_lab_signals.py -n 0 -q -p no:cacheprovider 2>&1 | tail -n 25); }
    echo "== baseline"; run
    cat > "$SIG/s0901_clock.py" <<'EOF'
    import time
    from seer_engine.lab.signal import Signal
    def score(history, market, pool, data_date):
        return {s: float(time.time() % 1.0) for s in sorted(pool)}
    SIGNAL = Signal(id="S0901", name="reads the clock", family="test-bad", source_kind="knowledge", source_ref="",
                    hypothesis="h", expected_failure="impure", lookback=1, score=score)
    EOF
    echo "== impure"; run; rm "$SIG/s0901_clock.py"
    cp "$SIG/s0001_twelve_minus_one_momentum.py" "$SIG/s0001_again.py"
    echo "== repeated id"; run; rm "$SIG/s0001_again.py"
    cat > "$SIG/s0902_peek.py" <<'EOF'
    from seer_engine.lab.signal import Signal
    def score(history, market, pool, data_date):
        out = {}
        for s in sorted(pool):
            h = history.get(s)
            i = None if h is None else h.index_of(data_date)
            if i is not None and i + 1 < len(h):
                out[s] = float(h.close[i + 1] / h.close[i] - 1.0)
        return out
    SIGNAL = Signal(id="S0902", name="reads tomorrow", family="test-bad", source_kind="knowledge", source_ref="",
                    hypothesis="h", expected_failure="look-ahead", lookback=2, score=score)
    EOF
    echo "== look-ahead"; run; rm "$SIG/s0902_peek.py"; rm -rf "$S"
    ```
    → passes when the `baseline` block ends with `passed` and no `failed`; the `impure` block lists `FAILED tests/test_lab_signals.py::test_signal_source_is_pure[S0901]`; the `repeated id` block shows `two signal files claim S0001` and an error during collection; and the `look-ahead` block lists `FAILED tests/test_lab_signals.py::test_signal_does_not_look_ahead[S0902]` with `look-ahead` in its message
  - **J3** · traces R2.1 — `cd $W/engine && PYTHONPATH=$W/engine/src $PY -m pytest tests/test_lab_panel.py -n 2 -v` → passes when 0 failed, and `test_a_planted_signal_is_recovered_in_every_era`, `test_a_null_signal_reads_as_null`, `test_the_era_split_puts_each_month_in_exactly_one_era`, `test_the_forward_return_is_a_total_return_with_the_dividend`, `test_a_name_whose_bars_stop_on_the_decision_date_is_dropped_and_counted`, `test_picks_mode_reads_a_pick_set_and_shares_its_hash_with_the_matching_score` and `test_the_picks_hash_is_stable_and_names_the_pick_set` are each `PASSED`
  - **J4** · traces R2.1 — the real dev store (read-only, about 1 GB of memory):
    ```bash
    cd /home/miftah/.worktrees/seer/sera-signal-panel
    PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python - /home/miftah/seer/engine/.research <<'PY'
    import math, sys, time
    from pathlib import Path
    from seer_engine import research
    from seer_engine.lab import panel
    from seer_engine.lab.signal import discover
    t0 = time.time()
    data = research.load_store(Path(sys.argv[1]))
    frame = panel.build_frame(data)
    print(f"store {data.fingerprint[:12]} window {data.window.name} purpose {data.purpose}: "
          f"{len(frame.months)} months {frame.months[0].day}..{frame.months[-1].day}, frame in {time.time() - t0:.0f}s")
    ok = True
    for sid in ("S0001", "S0002"):
        t1 = time.time()
        r = panel.measure(frame, panel.signal_scorer(discover()[sid][0]))
        print(f"{sid}: dropped_exits={r.dropped_exits} picks_hash={r.picks_hash[:12]} ({time.time() - t1:.0f}s)")
        for s in r.stats:
            print(f"  {s.era:9} months={s.months:3d} pool={s.mean_pool:5.0f} scored={s.mean_scored:5.0f} "
                  f"ic={s.ic_mean:+.4f} t={s.ic_t:+.2f} spread={s.spread_top:+.4f}/yr t={s.spread_t:+.2f} "
                  f"slope={s.fm_slope:+.5f}/mo t={s.fm_t:+.2f} turnover={s.top_turnover:.2f}")
        values = [v for s in r.stats for v in (s.ic_mean, s.ic_t, s.spread_top, s.spread_t, s.fm_slope, s.fm_t, s.top_turnover)]
        ok &= [s.era for s in r.stats] == list(panel.ERAS)
        ok &= all(s.months >= panel.MIN_ERA_MONTHS for s in r.stats)
        ok &= all(v is not None and math.isfinite(v) for v in values)
        if sid == "S0002":
            ok &= abs(r.era("all").ic_t) < 4.0 and abs(r.era("all").fm_t) < 4.0
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
    PY
    ```
    → passes when it exits 0 and prints `PASS`, with three era lines each for S0001 and S0002 (`all`, `pre2009`, `2009-2015`), every figure a number (no `nan`), and the coin toss S0002's whole-window |ic t| and |slope t| both under 4
  - **J5** · traces R2.1 — the same drive with the survivorship store as its argument: replace the path after `-` with `/home/miftah/seer/engine/.research-sv` → passes when it exits 0 and prints `PASS`, the header shows `purpose survivorship-check`, three era lines each for S0001 and S0002, every figure a number; `dropped_exits` is printed (the count of dead names whose last bar fell on a decision date — recorded, not asserted)
- Neighbor check: method discovery and the method contract sit next to the new `signals` package and share `lab.method`. Run `cd $W/engine && PYTHONPATH=$W/engine/src $PY -m pytest tests/test_lab_methods.py -n 2 -q -k "pure or unique or frozen or digest"` → passes when 0 failed. If `test_a_method_that_ran_is_frozen...` or the digest test goes red, re-run that file alone before blaming this phase (a concurrent `lab run` on the shared DB reddens it; memory note "A concurrent lab run reddens three tests").
- Cost: no paid drives. J4 and J5 each load one research store (about 12 s and about 1 GB each, per the analysis); run them one after the other, not at once.
**Exit criteria:** `discover()` returns S0001 and S0002; `test_lab_signals.py` and `test_lab_panel.py`
pass; the J2 mutations each turn the contract test red; `measure` recovers the planted signal and
reads the coin toss as null on the synthetic market; J4 and J5 print all three eras with finite
figures for both seed signals on both real stores.

## Handoffs

- **Phase 2 (record):** column semantics from this phase. `spread_top` is annualised and
  `fm_slope` is monthly. `ic_mean`/`ic_t` are NULL only for picks-mode (replay) panels. Every
  other REAL is finite. An era with under 12 measured months produces **no row** for that era, so
  `published` must treat a missing dev `2009-2015` row as the spread condition failing and a
  missing survivorship `all` row as the slope condition failing. The snapshot's era objects may be
  missing for the same reason. `picks_hash` is defined in contract deviation 4; twins are
  `picks_hash` equality on the same dev fingerprint. Persist `panel.RULE_ID` as `rule_id`.
- **Phase 3 (`lab panel`):** R2.1's *recording*, and its journey, are yours. Phase 1 only
  computes. Map `EraStats` fields one to one onto `panel_results` columns. Before measuring, refuse
  (exit 2) a store whose declared window is not dev, and a missing survivorship store (R2.2).
  `build_frame` also raises `ValueError` for a window ending after `DEV_END`; catch it as a
  `LabError`. Refuse a signal whose `market_fields` the store lacks, as
  `runner.preflight_data` does for methods. Refuse an uncommitted or dirty signal file through
  `registry_problem(path)` (R1.2). Build the frame **once per store** and measure every requested
  signal on it. Use `signal.source_sha` for `panel_signals.source_sha`. `lab next-signal-id`
  should take the max over both `discover()` and the DB, so an uncommitted file's id is not
  handed out twice.
- **Phase 4 (replay):** call `measure(frame, scorer, mode="picks")`. The scorer is called as
  `scorer(frame.market, pool, d)` with the **full** market. It must read members itself
  (`market.membership.members_on(d)`), call the allocator with `held=frozenset()`, and return
  `{symbol: 1.0}` for the picks. A pick is counted only if it is in the month's universe (a member
  with a bar dated d, not SPY), so a fixed ETF holding is ignored automatically. Months with
  fewer than `MIN_PICKS` picks are skipped by `measure`, so the replay need not count them.
  Months in which the allocator's switch is off return `{}` and are skipped the same way.
- **Phase 5 (signal book):** the book allocator should call `signal.scores(market, pool, d)`
  (which applies `visible`), never `signal.score` directly. That needs a `Market`, so the
  allocator is `MarketAware` (`prepare_market`). `signal.market_fields` feeds
  `runner.market_fields` for the store checks.
- **Phase 7 (docs):** point the explore skill at
  `.claude/skills/explore-and-experiment-new-method/signal_template.py`. State that S0001's
  controlled slope is near zero by construction (momentum is a control), so it is a raw-IC check.
- No criterion is untraced.

## Rollback

Delete the eight files this phase creates (`git rm` them by explicit path) and commit. Nothing
else imports them until phases 3–5 land. If those phases have landed, revert them first.
