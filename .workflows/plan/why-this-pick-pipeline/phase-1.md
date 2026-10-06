# Phase 1: Pure evidence module

**Plan set:** `WHY_THIS_PICK_PIPELINE_PLAN.md`
**Analysis:** `20261006-213425-W7P3_code_analyzer.md`
**Satisfies:** R1, R8 — every method that recommends stocks can say, in plain words with numbers, what its formula saw on each stock it picked
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/strategies`

---

## Goal

A new pure module, `seer_engine.strategies.evidence`, turns "the formula picked this stock" into
2–6 short plain-English facts per stock, built from the same numbers the decision used that night
(close vs its average, the 2-day strength score, the 12-to-1-month price move and its rank, the
signal vs its average, the filing measures and their rank). Every `paper.roster.RESOLVER` object
except the benchmark has an evidence function, keyed by its resolver name, and a test pins that.
Nothing that exists today changes: no strategy, params, roster, paper or explain file is edited.

The whole module and its test file were prototyped against this worktree's own `engine/.venv`
(at `3dd43e3`) before this plan was written: the test file below passes in full (34 + 1 tests),
`ruff check` is clean, the module passes the purity scan's AST rules, and importing it loads
neither `seer_engine.paper.roster`, `psycopg` nor `seer_engine.backtest.market`.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** nothing.
**Renames:** nothing.
**Creates** (all in `engine/src/seer_engine/strategies/evidence.py`, contract K1):
- `Facts = tuple[str, ...]`
- `EvidenceFn = Callable[["Market", Any, date, Sequence[str]], dict[str, Facts]]`
- `MAX_FACTS = 6`, `TRADING_DAYS_PER_MONTH = 21`
- `EVIDENCE: dict[str, EvidenceFn]` with exactly the keys `"STRATEGY_A"`, `"STRATEGY_C"`, `"FACTOR"`, `"TIMING"`, `"FUNDAMENTAL"` (= `set(roster.RESOLVER) - {roster.BENCHMARK_OBJECT}`)
- `def evidence_for(object_name: str, market: Market, params: Any, data_date: date, symbols: Sequence[str]) -> dict[str, Facts]` — `EVIDENCE[object_name](...)`, `KeyError` for an unknown name
- `def has_evidence(object_name: str) -> bool` — `False` for the benchmark, an unknown name, or a non-str
- `strategy_a_evidence`, `strategy_c_evidence`, `factor_evidence`, `timing_evidence`, `fundamental_evidence` (the five `EvidenceFn`s; public so a later method can reuse one)
- private formatting helpers `_num`, `_pct`, `_money`, `_big_money`, `_ordinal`, `_moved`, `_versus`, `_span` (tested directly; phase 3 must NOT import them — it parses the fact strings, see "Fact strings" below)
- `engine/tests/test_evidence.py` (new test module)

**Signature changes:** none.
**Requires (from earlier phases):** nothing (no dependencies).
**Behaviour every caller can rely on:**
- Return value: `{symbol: facts}` only for symbols it can explain; an unexplainable symbol (not a member, no bar dated `data_date`, not eligible, the rule is off, numbers not finite) is **absent**, never mapped to `()`. Every present value is a `tuple` of 2–6 `str` (exact `str`, JSON-ready), each one sentence ending in ".", no newline.
- Raises `TypeError` for wrong params type for that object, a bare `str` (or non-sequence) as `symbols`, or a `datetime` as `data_date`. `KeyError` for an unknown object name. Phase 2 catches everything (Invariant 5).
- `symbols` may contain the idle instrument or anything else; the function just leaves out what it cannot explain. Duplicates are fine.
- Reads only `market.history` (cut with `History.upto(data_date)`), `market.membership.members_on(data_date)` and, for FUNDAMENTAL, `market.fundamentals` via `FUNDAMENTAL.prepare_market(market).panel` (`as_of(symbol, data_date)` only). Never reads `market.fx`.
- STRATEGY_C's facts are exactly STRATEGY_A's facts under `params.a` (no news text; the news reason stays in `news_vetoes`, shown separately — R5 is phase 5's).
- `evidence_for` and `has_evidence` look `EVIDENCE` up **at call time** (`EVIDENCE[object_name]`, `object_name in EVIDENCE`); nothing caches the key set. Phase 2's tests `monkeypatch.setitem(evidence.EVIDENCE, "FACTOR", …)` and phase 4's tests `monkeypatch.delitem(evidence.EVIDENCE, "FUNDAMENTAL")` rely on this.
- No fact contains an advice or prediction word that phase 3's `BANNED` rejects (see "Fact strings").
**Leaves alone (owned by others):** `strategies/a.py`, `c.py`, `f_factor.py`, `f_index.py`, `f_fundamental.py`, `allocator.py`, `indicators.py`, `base.py`, `strategies/__init__.py` (evidence is NOT re-exported there), `paper/*` incl. `roster.py` (frozen roster, Invariant 2), `commands/paper.py` + `paper/store.py` + migration 009 (Phase 2), `commands/explain.py` (Phase 3), `commands/promote.py` (Phase 4), `web/**` (Phase 5), `tests/test_strategy_purity.py` (unchanged — its glob already picks up the new file).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/strategies/evidence.py` | create (new file, line 1) | the pure evidence module, contract K1 |
| `engine/tests/test_evidence.py` | create (new file, line 1) | key set pin, no roster import, per-object facts, distinct per symbol, plain words, no look-ahead, formatting |
| `engine/tests/test_strategy_purity.py` | none (confirm only) | `_pure_sources()` (line 33) globs `strategies/*.py`, so `evidence.py` is imported in a fresh interpreter (no psycopg/requests/yfinance) and AST-scanned (no time/random/logging imports, no `.now/.today/.random`, no `print/open/input`) without any edit |

## Fact strings (exact wording, for Phase 3's numbers check and Phase 5's fallback list)

Every number a fact states is written literally in that fact's string. Shapes, and only these:

| Shape | Format | Examples |
|---|---|---|
| money | `$` + two decimals + thousands commas (`f"${x:,.2f}"`) | `$231.40`, `$1,231.40` |
| percent | one decimal, trailing `.0` dropped, then `%`; never signed (direction is a word: rose/fell, above/below, earned/lost, beat/fell short of) | `6.1%`, `31%`, `623.4%` |
| plain number | one decimal, trailing `.0` dropped | `3.6`, `10`, `2.8` |
| ordinal | `{k}st/nd/rd/th` | `1st`, `22nd`, `413th` |
| integer count | bare int, inside words | `200-day`, `2-day`, `out of 100`, `last 2 trading days`, `last 20 trading days`, `12 months`, `1 month`, `60 trading days`, `of 412`, `4 measures`, `252 days old`, `the 5 companies` |
| big money | `$` + one decimal + ` billion` (≥ 1e9), `$` + integer + ` million` (≥ 1e6), else `$` + integer with commas | `$1.2 billion`, `$124 million`, `$950,000` |
| percent-of-others | integer percent | `higher than 92% of the other companies checked` |

No dates, no scientific notation, no `nan`/`inf`, no `-`/`+` signs, no codes. A number that would
not be finite makes the symbol absent instead. Phase 3's normalizer (strip `$`, `,`, `%`, `+`,
trailing `.0`; ordinals reduce to their digits) therefore finds every number of every fact.

**No advice or prediction words (reconciled).** No fact contains a word phase 3's `BANNED` list
rejects: `buy`/`buys`/`buying`, `sell…`, `recommend…`, `should`, `will`, `going to`, `expect…`,
`guarantee…` (case-insensitive, word-bounded). A fact that used one would get every faithful note
that repeats it rejected, and the site shows the facts verbatim when there is no note (invariant 6).
`FORBIDDEN` in the tests enforces this. The market-filter effect therefore reads "so the method is
allowed to **hold** stocks", never "buy". Checked by running phase 3's `numbers_in` / `vet` on every
prototype fact (each fact, and the first two facts joined, pass `vet` against their own facts).

Exact templates (`{…}` = a formatted value of the shape above; text outside braces is literal):

**STRATEGY_A** and **STRATEGY_C** (C uses `params.a`) — 4 facts, +1 when the stock passed the rule:
1. `It closed at {money close}, {versus} its 200-day average of {money sma}.` — `{versus}` is `{pct} above` / `{pct} below` / `level with`
2. `Its 2-day strength score was {plain rsi} out of 100; below {plain rsi_max} counts as a sharp short drop.`
3. `Over the last 2 trading days it {moved 2-day}, and over the last 5 it {moved 5-day}.` — `{moved}` is `rose {pct}` / `fell {pct}` / `was flat`
4. `On an average day over the last 20 trading days, {big money dollar volume} of its shares changed hands.`
5. (only if among A's ranked picks that night) `It ranked {ordinal} of {count} stocks that passed the rule that day, lowest strength score first.`

Real output (prototype, synthetic market):
```
It closed at $219.00, 1.9% above its 200-day average of $215.00.
Its 2-day strength score was 1.1 out of 100; below 10 counts as a sharp short drop.
Over the last 2 trading days it fell 2.6%, and over the last 5 it fell 2.4%.
On an average day over the last 20 trading days, $224 million of its shares changed hands.
It ranked 1st of 3 stocks that passed the rule that day, lowest strength score first.
```

**FACTOR** (F4 = `rank="momentum"`, `mom_n=252`, `mom_skip=21`, `trend=("SPY", 200)`) — 2 to 4 facts:
1. `Its price {moved} from {span mom_n} ago to {span mom_skip} ago.` (when `mom_skip > 0`) or `Its price {moved} over the last {span mom_n}.` — `{span}` is `{m} months`/`1 month` when the bar count is a multiple of 21, else `{n} trading days`
2. rank, one of:
   - momentum: `It ranked {ordinal} of {count eligible} stocks checked on that move, strongest first.`
   - lowvol: `It ranked {ordinal} of {count eligible} stocks checked on how calmly its price moves, calmest first.`
   - mom_lowvol (symbol in the pool): `It was among the {pool} stocks with the strongest move out of {count eligible} checked, and ranked {ordinal} of those on how calmly its price moves, calmest first.`
3. (lowvol / mom_lowvol only) `Its price typically moved {pct daily stdev} a day over the last {vol_n} trading days.`
4. (when `trend` is set) `{symbol} closed {versus} its {n}-day average, so the method is allowed to hold stocks.` / `…, so the method stays in cash.` (degenerate: `{symbol} does not have {n} days of prices yet, …` / `{symbol} has no usable {n}-day average, …`)

Real output:
```
Its price rose 60% from 12 months ago to 1 month ago.
It ranked 1st of 5 stocks checked on that move, strongest first.
SPY closed 9.8% above its 200-day average, so the method is allowed to hold stocks.
```

**TIMING** (F1 = hold SPY, signal SPY, `sma`, n 200) — exactly 2 facts, only for `params.hold`, only when the rule is on (`timing_state(...) is True`; off or unknown → `{}`):
- sma: `{signal} closed at {money}, {versus} its {n}-day average of {money}.` + `The rule holds {hold} while {signal} closes above its {n}-day average, so it holds {hold}.`
- month_sma: `{signal} closed at {money}, {versus} the average of its last {n} month-end closes, {money}.` + `The rule holds {hold} while {signal} closes above that average, so it holds {hold}.`
- abs_mom: `{signal} closed at {money}, {versus} its close of {money} {span n} earlier.` + `The rule holds {hold} while {signal} is higher than it was {span n} earlier, so it holds {hold}.`
- always: `This method holds {hold} at all times.` + `{hold} closed at {money}.`

Real output:
```
SPY closed at $555.00, 9.8% above its 200-day average of $505.25.
The rule holds SPY while SPY closes above its 200-day average, so it holds SPY.
```

**FUNDAMENTAL** (FND = `rank="composite"`, top 20, no trend) — 1 rank fact + one per factor read + trend (if set) + filing age, capped at 6 (composite + trend drops the age fact):
1. composite: `It ranked {ordinal} of {count eligible} companies checked on a combined score of {count weights > 0} measures from its financial filings.`; single factor: `It ranked {ordinal} of {count eligible} companies checked on {label}, highest first.` with labels value → `how much the company owns for its stock price`, quality → `how much it earns on its shareholders' money`, profitability → `how much gross profit it makes for its size`, sue → `how far its latest earnings beat the year before`
2. per factor read, each followed by a comparison clause `, the highest of the {count} companies checked` / `, the lowest of the {count} companies checked` / `, higher than {int pct}% of the other companies checked` (omitted when only one company was eligible):
   - value: `Its net worth on its books is {pct} of its stock-market value{clause}.`
   - quality: `It earned {pct} on its shareholders' money in its last fiscal year{clause}.` (`lost` when negative)
   - profitability: `Its gross profit in its last fiscal year was {pct} of everything it owns{clause}.`
   - sue: `Its latest quarterly earnings beat the same quarter a year earlier by {plain} times the usual size of its earnings surprises{clause}.` (`fell short of` when negative)
3. (when `trend` is set) the same market-filter fact as FACTOR
4. `Its latest financial filing used here is {days} days old.` (`1 day old`)

Real output:
```
It ranked 1st of 5 companies checked on a combined score of 4 measures from its financial filings.
Its net worth on its books is 623.4% of its stock-market value, the highest of the 5 companies checked.
It earned 12.5% on its shareholders' money in its last fiscal year, the lowest of the 5 companies checked.
Its gross profit in its last fiscal year was 40% of everything it owns, the highest of the 5 companies checked.
Its latest quarterly earnings beat the same quarter a year earlier by 2.8 times the usual size of its earnings surprises, higher than 25% of the other companies checked.
Its latest financial filing used here is 252 days old.
```

## Implementation Steps

### Step 1: Create the evidence module
**File:** `engine/src/seer_engine/strategies/evidence.py:1` (new file)
**Change:** Write the module below verbatim. Design points the code relies on:
- **Same inputs as the decision.** A/C: `features_at` over member histories cut at `data_date`, ranked with `picks_from_features` (the exact `STRATEGY_A.picks` path, `strategies/a.py:299-309`). FACTOR: `factor_rows` (`f_factor.py:194`) + `rank_rows` (`:256`) + `trend_on` (`:234`). TIMING: `timing_state` (`f_index.py:217`), `month_end_closes` (`allocator.py:202`). FUNDAMENTAL: `FUNDAMENTAL.prepare_market(market).panel` (`f_fundamental.py:602`, the MarketAware path `decide_book` uses) + `fundamental_rows` (`:374`) + `rank_rows` (`:484`) + `trend_on` (`:422`) + `factors_read` (`:297`).
- **Full ranking, not just the top.** The rank of every eligible stock comes from the module's own `rank_rows` called with `dataclasses.replace(p, top=min(n, MAX_TOP))` (and `rank="momentum"`/`"lowvol"`/`"mom_lowvol"` for FACTOR), so ties and ordering are the allocator's own, not a re-implementation. `replace` builds a new params value; the frozen roster params object is never mutated, and no digest is touched (Invariant 2).
- **No look-ahead.** Every function calls `_cut` (`History.upto(data_date)`) before reading bars; the panel answers `as_of(symbol, data_date)` from facts filed on or before it.
- **No roster import** (would cycle: `paper/roster.py:94-100` imports `strategies.*`; phases 2 and 4 import both). `Market` is a `TYPE_CHECKING`-only import, exactly as `allocator.py:49-50`.
- **Pure:** imports are `math`, `collections.abc`, `dataclasses`, `datetime`, `typing`, `numpy`, and `seer_engine.strategies.*` only.
**Code:**
```python
"""Per-pick evidence: the numbers each paper method's formula read on one stock, in plain words.

"Why this pick" needs, for every stock a method picked, the facts its formula actually used on
that stock that night. This module computes them, one function per ``paper.roster.RESOLVER`` key
(the benchmark has none: it is not a pick). Each function returns ``{symbol: facts}``: 2 to 6
short plain-English sentences, every number already formatted for a reader ("$231.40", "6.1%",
"3rd of 412"). The owner is not a trader, so no fact ever names an indicator code ("RSI(2)",
"SMA200", "12-1"), an object name, a registry id or a parameter key.

THE NUMBER RULE (consumed by the Explain step's numbers check). Every number a fact states is
written literally inside that fact's string, in one of these shapes and no other:
    money        "$1,231.40"      always two decimals, thousands commas
    percent      "6.1%", "31%"    one decimal, a trailing ".0" dropped; a sign is a word
                                  ("rose"/"fell", "above"/"below"), never "-" or "+"
    plain        "4.2", "10"      one decimal, a trailing ".0" dropped
    ordinal      "3rd of 412"
    count        "200-day", "12 months", "5 trading days", "45 days old", "4 measures"
    big money    "$45 million", "$1.2 billion"
No dates, no scientific notation, no "nan"/"inf" (a symbol whose numbers are not finite is left
out instead).

Reads only bars dated on or before ``data_date`` (every function cuts ``market.history`` with
``History.upto``) and fundamental facts filed on or before it (``panel.as_of``). Members are
``market.membership.members_on(data_date)``, exactly what the decision used. A symbol the
function cannot explain (not eligible, no bar that day) is absent from the result, never an
empty tuple.

Pure: no database, network, clock, randomness, logging or I/O (tests/test_strategy_purity.py
scans this file). It must never import ``seer_engine.paper.roster`` -- the roster imports
``strategies``, and the paper and promote commands import this module next to the roster;
``tests/test_evidence.py`` pins both the key set and the absent import. ``backtest.market`` is
imported for typing only, as ``strategies.allocator`` does, so no strategies -> backtest cycle.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import date
from typing import TYPE_CHECKING, Any

import numpy as np

from seer_engine.strategies.a import DV_N as A_DV_N
from seer_engine.strategies.a import RSI_N, SMA_N, AParams, features_at, picks_from_features
from seer_engine.strategies.allocator import month_end_closes
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.c import CParams
from seer_engine.strategies.f_factor import MAX_TOP as FACTOR_MAX_TOP
from seer_engine.strategies.f_factor import FactorParams, factor_rows
from seer_engine.strategies.f_factor import rank_rows as factor_rank_rows
from seer_engine.strategies.f_factor import trend_on as factor_trend_on
from seer_engine.strategies.f_fundamental import FUNDAMENTAL, FundamentalParams, FundamentalRow, factors_read, fundamental_rows
from seer_engine.strategies.f_fundamental import MAX_TOP as FUNDAMENTAL_MAX_TOP
from seer_engine.strategies.f_fundamental import rank_rows as fundamental_rank_rows
from seer_engine.strategies.f_fundamental import trend_on as fundamental_trend_on
from seer_engine.strategies.f_index import TimingParams, timing_state
from seer_engine.strategies.indicators import sma_window

if TYPE_CHECKING:  # typing only: no runtime import, so no strategies -> backtest import cycle
    from seer_engine.backtest.market import Market

Facts = tuple[str, ...]
"""One pick's evidence: 2-6 short plain-English statements, each with its numbers already
formatted for a reader ("$231.40", "6.1%", "3rd of 412"). No ids, no indicator codes."""

EvidenceFn = Callable[["Market", Any, date, Sequence[str]], dict[str, Facts]]
"""(market, params, data_date, symbols) -> {symbol: facts} for every symbol it can explain
(a symbol it cannot explain is absent). Reads only bars dated <= data_date and panel facts
filed <= data_date. Pure; may raise on bad input (the caller catches)."""

MAX_FACTS = 6
TRADING_DAYS_PER_MONTH = 21  # mom_n = 252 reads as "12 months", mom_skip = 21 as "1 month"

_FUNDAMENTAL_RANK_LABEL: dict[str, str] = {
    "value": "how much the company owns for its stock price",
    "quality": "how much it earns on its shareholders' money",
    "profitability": "how much gross profit it makes for its size",
    "sue": "how far its latest earnings beat the year before",
}


# --------------------------------------------------------------------------- formatting


def _num(x: float, places: int = 1) -> str:
    """``|x|`` with ``places`` decimals and thousands commas, a trailing ".0" dropped: 6.1, 31, 1,204.5."""
    text = f"{abs(x):,.{places}f}"
    zeros = "." + "0" * places
    if places and text.endswith(zeros):
        text = text[: -len(zeros)]
    return text


def _pct(fraction: float) -> str:
    """A fraction as a percent without a sign: 0.0614 -> "6.1%", -0.31 -> "31%"."""
    return _num(fraction * 100.0) + "%"


def _money(x: float) -> str:
    """A price: "$1,231.40"."""
    return f"${x:,.2f}"


def _big_money(x: float) -> str:
    """A daily trading value: "$1.2 billion", "$45 million", or "$950,000" below a million."""
    if x >= 1e9:
        return f"${_num(x / 1e9)} billion"
    if x >= 1e6:
        return f"${_num(x / 1e6, 0)} million"
    return f"${x:,.0f}"


def _ordinal(k: int) -> str:
    """1 -> "1st", 2 -> "2nd", 3 -> "3rd", 11 -> "11th", 22 -> "22nd"."""
    if 10 <= k % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(k % 10, "th")
    return f"{k}{suffix}"


def _moved(change: float) -> str:
    """A fractional change as words: "rose 3.2%", "fell 1.1%", "was flat"."""
    text = _pct(change)
    if text == "0%":
        return "was flat"
    return f"{'rose' if change > 0 else 'fell'} {text}"


def _versus(x: float, ref: float) -> str:
    """Where ``x`` sits against ``ref``: "6.1% above", "2.3% below", "level with"."""
    change = x / ref - 1.0
    text = _pct(change)
    if text == "0%":
        return "level with"
    return f"{text} {'above' if change > 0 else 'below'}"


def _span(bars: int) -> str:
    """A bar count as a reader says it: 252 -> "12 months", 21 -> "1 month", 5 -> "5 trading days"."""
    if bars % TRADING_DAYS_PER_MONTH == 0:
        months = bars // TRADING_DAYS_PER_MONTH
        return f"{months} month" if months == 1 else f"{months} months"
    return f"{bars} trading day" if bars == 1 else f"{bars} trading days"


def _finite(*xs: float) -> bool:
    return all(math.isfinite(float(x)) for x in xs)


# --------------------------------------------------------------------------- shared input handling


def _wanted(symbols: object) -> tuple[str, ...]:
    """``symbols`` as a de-duplicated tuple, in the order given. A bare str is a programming error."""
    if isinstance(symbols, str) or not isinstance(symbols, Sequence):
        raise TypeError(f"symbols must be a sequence of symbols, got {type(symbols).__name__}")
    for s in symbols:
        if not isinstance(s, str) or not s:
            raise TypeError(f"symbols holds a non-symbol {s!r}")
    return tuple(dict.fromkeys(symbols))


def _typed(name: str, params: object, cls: type) -> Any:
    if not isinstance(params, cls):
        raise TypeError(f"{name} evidence needs {cls.__name__} params, got {type(params).__name__}")
    return params


def _cut(market: Market, data_date: date) -> dict[str, History]:
    """Every history cut to its bars dated on or before ``data_date`` (no look-ahead)."""
    as_day(data_date)
    return {s: h.upto(data_date) for s, h in market.history.items()}


def _trend_fact(history: Mapping[str, History], data_date: date, trend: tuple[str, int], on: bool) -> str:
    """The market filter in words: where its symbol closed against its n-day average, and the effect."""
    symbol, n = trend
    effect = "so the method is allowed to hold stocks" if on else "so the method stays in cash"
    h = history.get(symbol)
    i = None if h is None else h.index_of(data_date)
    if h is None or i is None or i + 1 < n:
        return f"{symbol} does not have {n} days of prices yet, {effect}."
    window = h.close[i + 1 - n : i + 1].reshape(1, n)
    average = float(sma_window(window, n)[0])
    close = float(h.close[i])
    if not _finite(average, close) or average <= 0.0:
        return f"{symbol} has no usable {n}-day average, {effect}."
    return f"{symbol} closed {_versus(close, average)} its {n}-day average, {effect}."


# --------------------------------------------------------------------------- Strategy A and C


def _a_facts(market: Market, a: AParams, data_date: date, symbols: Sequence[str]) -> dict[str, Facts]:
    """Strategy A's evidence under ``a`` (also C's, with ``CParams.a``)."""
    wanted = _wanted(symbols)
    members = market.membership.members_on(data_date)
    history = {s: h for s, h in _cut(market, data_date).items() if s in members}
    features = features_at(history, data_date)
    by_symbol = {f.symbol: f for f in features}
    ranked = [p.symbol for p in picks_from_features(features, members, a)]
    out: dict[str, Facts] = {}
    for symbol in wanted:
        f = by_symbol.get(symbol)
        if f is None:
            continue
        h = history[symbol]
        i = h.index_of(data_date)
        if i is None or i < 5:
            continue
        close = float(h.close[i])
        two = close / float(h.close[i - 2]) - 1.0
        five = close / float(h.close[i - 5]) - 1.0
        if not _finite(f.close, f.sma, f.rsi, f.dollar_volume, two, five) or f.sma <= 0.0:
            continue
        facts = [
            f"It closed at {_money(f.close)}, {_versus(f.close, f.sma)} its {SMA_N}-day average of {_money(f.sma)}.",
            f"Its {RSI_N}-day strength score was {_num(f.rsi)} out of 100; below {_num(a.rsi_max)} counts as a sharp short drop.",
            f"Over the last 2 trading days it {_moved(two)}, and over the last 5 it {_moved(five)}.",
            f"On an average day over the last {A_DV_N} trading days, {_big_money(f.dollar_volume)} of its shares changed hands.",
        ]
        if symbol in ranked:
            facts.append(
                f"It ranked {_ordinal(ranked.index(symbol) + 1)} of {len(ranked)} stocks that passed the rule "
                "that day, lowest strength score first."
            )
        out[symbol] = tuple(facts[:MAX_FACTS])
    return out


def strategy_a_evidence(market: Market, params: Any, data_date: date, symbols: Sequence[str]) -> dict[str, Facts]:
    """``STRATEGY_A``: close vs its 200-day average, the 2-day strength score, the 2- and 5-day
    moves, average daily trading value, and its place among the stocks that passed the rule."""
    return _a_facts(market, _typed("STRATEGY_A", params, AParams), data_date, symbols)


def strategy_c_evidence(market: Market, params: Any, data_date: date, symbols: Sequence[str]) -> dict[str, Facts]:
    """``STRATEGY_C``: Strategy A's facts under ``params.a`` (the news check's reason is stored
    separately, in ``news_vetoes``, and shown as its own line)."""
    return _a_facts(market, _typed("STRATEGY_C", params, CParams).a, data_date, symbols)


# --------------------------------------------------------------------------- FACTOR (F4/F5/F6)


def _momentum_fact(momentum: float, p: FactorParams) -> str:
    if p.mom_skip:
        return f"Its price {_moved(momentum)} from {_span(p.mom_n)} ago to {_span(p.mom_skip)} ago."
    return f"Its price {_moved(momentum)} over the last {_span(p.mom_n)}."


def factor_evidence(market: Market, params: Any, data_date: date, symbols: Sequence[str]) -> dict[str, Facts]:
    """``FACTOR``: the price move the ranking reads, the stock's place among the eligible ones,
    the market filter when ``params.trend`` is set, and its daily swings when the ranking reads them."""
    p: FactorParams = _typed("FACTOR", params, FactorParams)
    wanted = _wanted(symbols)
    history = _cut(market, data_date)
    members = market.membership.members_on(data_date)
    rows = factor_rows(history, members, data_date, p)
    if not rows:
        return {}
    n = len(rows)
    top = min(n, FACTOR_MAX_TOP)
    by_momentum = [r.symbol for r in factor_rank_rows(rows, replace(p, rank="momentum", top=top))]
    by_calm = [r.symbol for r in factor_rank_rows(rows, replace(p, rank="lowvol", top=top))]
    pool_size = min(p.pool, n, FACTOR_MAX_TOP)
    pool_by_calm = [r.symbol for r in factor_rank_rows(rows, replace(p, rank="mom_lowvol", top=pool_size))]
    on = factor_trend_on(history, data_date, p)
    by_symbol = {r.symbol: r for r in rows}
    out: dict[str, Facts] = {}
    for symbol in wanted:
        r = by_symbol.get(symbol)
        if r is None or not _finite(r.momentum, r.vol):
            continue
        facts = [_momentum_fact(r.momentum, p)]
        if p.rank == "lowvol" and symbol in by_calm:
            facts.append(
                f"It ranked {_ordinal(by_calm.index(symbol) + 1)} of {n} stocks checked on how calmly "
                "its price moves, calmest first."
            )
        elif p.rank == "mom_lowvol" and symbol in pool_by_calm:
            facts.append(
                f"It was among the {pool_size} stocks with the strongest move out of {n} checked, and "
                f"ranked {_ordinal(pool_by_calm.index(symbol) + 1)} of those on how calmly its price "
                "moves, calmest first."
            )
        elif symbol in by_momentum:
            facts.append(
                f"It ranked {_ordinal(by_momentum.index(symbol) + 1)} of {n} stocks checked on that "
                "move, strongest first."
            )
        if p.rank in ("lowvol", "mom_lowvol"):
            facts.append(f"Its price typically moved {_pct(r.vol)} a day over the last {p.vol_n} trading days.")
        if p.trend is not None:
            facts.append(_trend_fact(history, data_date, p.trend, on))
        if len(facts) >= 2:
            out[symbol] = tuple(facts[:MAX_FACTS])
    return out


# --------------------------------------------------------------------------- TIMING (F1/F10)


def timing_evidence(market: Market, params: Any, data_date: date, symbols: Sequence[str]) -> dict[str, Facts]:
    """``TIMING``: the signal instrument's close against what the rule compares it to, and what
    that means. Only the held instrument (``params.hold``) is explained, and only on a night the
    rule says hold: on any other night the method picks nothing, so there is nothing to explain."""
    p: TimingParams = _typed("TIMING", params, TimingParams)
    wanted = _wanted(symbols)
    if p.hold not in wanted:
        return {}
    history = _cut(market, data_date)
    if timing_state(history, data_date, p) is not True:
        return {}
    hold, signal, n = p.hold, p.signal, p.n
    if p.rule == "always":
        h = history.get(hold)
        i = None if h is None else h.index_of(data_date)
        if h is None or i is None or not _finite(float(h.close[i])):
            return {}
        return {hold: (f"This method holds {hold} at all times.", f"{hold} closed at {_money(float(h.close[i]))}.")}
    h = history.get(signal)
    i = None if h is None else h.index_of(data_date)
    if h is None or i is None:
        return {}
    close = float(h.close[i])
    if p.rule == "sma":
        average = float(sma_window(h.close[i + 1 - n : i + 1].reshape(1, n), n)[0])
        if not _finite(close, average) or average <= 0.0:
            return {}
        first = f"{signal} closed at {_money(close)}, {_versus(close, average)} its {n}-day average of {_money(average)}."
        rule = f"The rule holds {hold} while {signal} closes above its {n}-day average, so it holds {hold}."
    elif p.rule == "month_sma":
        closes = month_end_closes(h, data_date)
        window = np.ascontiguousarray(closes[-n:], dtype=np.float64).reshape(1, n)
        average = float(sma_window(window, n)[0])
        if not _finite(close, average) or average <= 0.0:
            return {}
        first = (
            f"{signal} closed at {_money(close)}, {_versus(close, average)} the average of its last {n} "
            f"month-end closes, {_money(average)}."
        )
        rule = f"The rule holds {hold} while {signal} closes above that average, so it holds {hold}."
    else:  # abs_mom
        base = float(h.close[i - n])
        if not _finite(close, base) or base <= 0.0:
            return {}
        first = (
            f"{signal} closed at {_money(close)}, {_versus(close, base)} its close of {_money(base)} "
            f"{_span(n)} earlier."
        )
        rule = f"The rule holds {hold} while {signal} is higher than it was {_span(n)} earlier, so it holds {hold}."
    return {hold: (first, rule)}


# --------------------------------------------------------------------------- FUNDAMENTAL (FND)


def _share_below(rows: Sequence[FundamentalRow], name: str, x: float) -> str:
    """How ``x`` compares with the other eligible companies on ``name``, as a trailing clause.

    ", the highest of the 5 companies checked", ", the lowest of ...", or ", higher than 92% of
    the other companies checked" (strictly lower values over the others). Empty when fewer than
    two rows were eligible.
    """
    if len(rows) < 2:
        return ""
    below = sum(1 for r in rows if float(getattr(r, name)) < x)
    if below == len(rows) - 1:
        return f", the highest of the {len(rows)} companies checked"
    if below == 0:
        return f", the lowest of the {len(rows)} companies checked"
    share = round(100.0 * below / (len(rows) - 1))
    return f", higher than {share}% of the other companies checked"


def _factor_sentence(name: str, x: float, rows: Sequence[FundamentalRow]) -> str:
    compare = _share_below(rows, name, x)
    if name == "value":
        return f"Its net worth on its books is {_pct(x)} of its stock-market value{compare}."
    if name == "quality":
        verb = "earned" if x >= 0 else "lost"
        return f"It {verb} {_pct(x)} on its shareholders' money in its last fiscal year{compare}."
    if name == "profitability":
        return f"Its gross profit in its last fiscal year was {_pct(x)} of everything it owns{compare}."
    verb = "beat" if x >= 0 else "fell short of"
    return (
        f"Its latest quarterly earnings {verb} the same quarter a year earlier by {_num(x)} times the "
        f"usual size of its earnings surprises{compare}."
    )


def fundamental_evidence(market: Market, params: Any, data_date: date, symbols: Sequence[str]) -> dict[str, Facts]:
    """``FUNDAMENTAL``: the company's place among the eligible ones, each filing measure the
    ranking reads (with how it compares), the market filter when set, and how old its latest
    filing is. The panel comes through ``FUNDAMENTAL.prepare_market`` (the decision's own path)."""
    p: FundamentalParams = _typed("FUNDAMENTAL", params, FundamentalParams)
    wanted = _wanted(symbols)
    history = _cut(market, data_date)
    panel = FUNDAMENTAL.prepare_market(market).panel
    members = market.membership.members_on(data_date)
    rows = fundamental_rows(history, panel, members, data_date, p)
    if not rows:
        return {}
    n = len(rows)
    order = [r.symbol for r in fundamental_rank_rows(rows, replace(p, top=min(n, FUNDAMENTAL_MAX_TOP)))]
    on = fundamental_trend_on(history, data_date, p)
    read = factors_read(p)
    by_symbol = {r.symbol: r for r in rows}
    out: dict[str, Facts] = {}
    for symbol in wanted:
        r = by_symbol.get(symbol)
        if r is None or symbol not in order:
            continue
        place = _ordinal(order.index(symbol) + 1)
        if p.rank == "composite":
            measures = sum(1 for w in p.weights if w > 0.0)
            facts = [f"It ranked {place} of {n} companies checked on a combined score of {measures} measures from its financial filings."]
        else:
            facts = [f"It ranked {place} of {n} companies checked on {_FUNDAMENTAL_RANK_LABEL[p.rank]}, highest first."]
        facts += [_factor_sentence(name, float(getattr(r, name)), rows) for name in read]
        if p.trend is not None:
            facts.append(_trend_fact(history, data_date, p.trend, on))
        snap = panel.as_of(symbol, data_date)
        filed = None if snap is None else snap.filed
        if filed is not None and filed <= data_date:
            age = (data_date - filed).days
            facts.append(f"Its latest financial filing used here is {age} day{'' if age == 1 else 's'} old.")
        out[symbol] = tuple(facts[:MAX_FACTS])
    return out


# --------------------------------------------------------------------------- the table


#: Keyed by ``paper.roster.RESOLVER`` keys; the benchmark key (``buy_and_hold``) has no entry.
#: ``tests/test_evidence.py`` pins ``set(EVIDENCE) == set(RESOLVER) - {BENCHMARK_OBJECT}``, so a
#: new resolver entry without evidence fails the suite, and ``promote`` refuses it (phase 4).
EVIDENCE: dict[str, EvidenceFn] = {
    "STRATEGY_A": strategy_a_evidence,
    "STRATEGY_C": strategy_c_evidence,
    "FACTOR": factor_evidence,
    "TIMING": timing_evidence,
    "FUNDAMENTAL": fundamental_evidence,
}


def evidence_for(
    object_name: str, market: Market, params: Any, data_date: date, symbols: Sequence[str]
) -> dict[str, Facts]:
    """``EVIDENCE[object_name](market, params, data_date, symbols)``; KeyError for an unknown name."""
    return EVIDENCE[object_name](market, params, data_date, symbols)


def has_evidence(object_name: str) -> bool:
    """True when ``object_name`` has an evidence function (what ``promote`` requires)."""
    return isinstance(object_name, str) and object_name in EVIDENCE
```
**Impact:** new module only; nothing imports it yet (Phase 2 imports `evidence_for`, Phase 4 imports `has_evidence`). `tests/test_strategy_purity.py` now also imports and scans it.

### Step 2: Create the test module
**File:** `engine/tests/test_evidence.py:1` (new file)
**Change:** Write the tests below verbatim. Fixtures reuse `tests/stratkit.py` (`hist`, `session_days`, `uptrend`, `dip`, `mutate_from`); markets are built with `backtest.market.Market`/`Membership` like `tests/test_paper_fnd.py:135`; the FND panel is a real `fundamentals.FundamentalPanel` built from `Fact`s with a 10-quarter diluted-EPS run so SUE is finite, copied in shape from `tests/test_paper_fnd.py:96-132` (a `FakePanel` cannot be used: `Market.__post_init__` type-checks `fundamentals`, `backtest/market.py:284`). Params are the live roster's (`roster.entry(F4_ID).params`, `roster.entry(F1_ID).params`, `roster.FUNDAMENTAL_PARAMS`, `STRATEGY_A_PARAMS`, `STRATEGY_C_PARAMS`) so the tests exercise exactly what paper will call. The test may import `seer_engine.paper.roster`; the module may not, which `test_the_module_does_not_import_the_roster` checks in a fresh interpreter (the pattern of `test_strategy_purity.py:45-56`).

What the tests pin:
- `set(EVIDENCE) == set(roster.RESOLVER) - {roster.BENCHMARK_OBJECT}`; `has_evidence` true for each key, false for `buy_and_hold`, an unknown name and `None`; unknown name → `KeyError`.
- Importing `seer_engine.strategies.evidence` alone does not load `seer_engine.paper.roster`.
- Wrong params type per object, and a bare `str` as `symbols` → `TypeError`.
- Per object: the expected keys (unexplainable symbols absent, SPY never a FACTOR stock, the idle-like `BIL` absent for TIMING), the exact fact shapes/wording, 2–6 facts each, distinct facts per symbol, no `RSI`/`SMA`/`ATR`/`12-1`/`z-score`/`SUE`/object names/`F\d+`/`nan`/`inf`/`None`/`_` anywhere, and no advice or prediction word from phase 3's `BANNED` list (buy, sell, recommend, should, will, going to, expect, guarantee).
- No look-ahead for every object: facts are identical for a market cut at `data_date`, a market whose later bars are replaced by wild values (`mutate_from`), and (FND) a panel with a restatement filed after `data_date`.
- C == A under `STRATEGY_C_PARAMS.a`; a non-member is absent and does not count in "of N".
- TIMING explains nothing when the rule is off; month_sma, abs_mom and always rules produce facts.
- Formatting helpers, determinism, and that facts are exact `str`.
**Code:**
```python
"""Per-pick evidence (why-this-pick-pipeline phase 1; requirements R1, R8).

Every roster object except the benchmark has an evidence function; each one returns distinct,
plain-English facts per symbol, built only from bars dated on or before the data date (and
filings filed on or before it), with no indicator codes or ids. The purity scan in
tests/test_strategy_purity.py covers ``strategies/evidence.py`` through its glob.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import date, timedelta
from itertools import combinations
from pathlib import Path

import pytest
from stratkit import dip, hist, mutate_from, session_days, uptrend

import seer_engine
from seer_engine import dates
from seer_engine.backtest.market import Market, Membership
from seer_engine.fundamentals import Fact, FundamentalPanel
from seer_engine.paper import roster
from seer_engine.strategies import evidence
from seer_engine.strategies.a import STRATEGY_A_PARAMS
from seer_engine.strategies.base import History
from seer_engine.strategies.c import STRATEGY_C_PARAMS
from seer_engine.strategies.f_factor import FactorParams
from seer_engine.strategies.f_fundamental import FundamentalParams
from seer_engine.strategies.f_index import TimingParams

F4 = roster.entry(roster.F4_ID).params
F1 = roster.entry(roster.F1_ID).params
FND = roster.FUNDAMENTAL_PARAMS

# Indicator codes, object names, ids and non-numbers the owner must never see (R8).
FORBIDDEN = re.compile(
    r"RSI|SMA|ATR|12-1|z-score|\bsue\b|SUE|STRATEGY|FACTOR|TIMING|FUNDAMENTAL|\bFAC\b|\bFND\b|"
    r"\bF\d+\b|C-news-veto|buy_and_hold|\bnan\b|\binf\b|None|_|"
    # advice or prediction words: Explain (phase 3) rejects a note that repeats one (its BANNED list),
    # and the site shows facts verbatim when there is no note (design §1, plan invariant 6)
    r"(?i:\bbuy(?:s|ing)?\b|\bsell(?:s|ing)?\b|\brecommend|\bshould|\bwill\b|\bgoing\s+to\b|\bexpect|\bguarantee)"
)


def market_of(history: dict[str, History], start: date, panel: FundamentalPanel | None = None) -> Market:
    """A Market where every symbol is a member from ``start`` on."""
    m = Market(
        history=history,
        membership=Membership(intervals=tuple((s, start, None) for s in sorted(history))),
        fx=(),
    )
    return m if panel is None else m.with_fundamentals(panel)


def assert_plain(out: dict[str, tuple[str, ...]]) -> None:
    """Every result is 2-6 one-line sentences with no code, id or non-number in them."""
    assert out, "the check must not be vacuous"
    for symbol, facts in out.items():
        assert isinstance(facts, tuple) and 2 <= len(facts) <= evidence.MAX_FACTS, (symbol, facts)
        for fact in facts:
            assert isinstance(fact, str) and fact.endswith("."), fact
            assert "\n" not in fact
            assert not FORBIDDEN.search(fact), fact


def assert_distinct(out: dict[str, tuple[str, ...]]) -> None:
    assert len(out) >= 2
    for a, b in combinations(out, 2):
        assert out[a] != out[b], (a, b)


def later_bars_changed(history: dict[str, History], data_date: date) -> dict[str, History]:
    """Every bar dated after ``data_date`` replaced by wild values (as if the future were different)."""
    return {s: mutate_from(h, dates.next_session(data_date)) for s, h in history.items()}


def cut_at(history: dict[str, History], data_date: date) -> dict[str, History]:
    return {s: h.upto(data_date) for s, h in history.items()}


# --------------------------------------------------------------------------- the table


def test_every_roster_object_but_the_benchmark_has_evidence():
    assert set(evidence.EVIDENCE) == set(roster.RESOLVER) - {roster.BENCHMARK_OBJECT}
    for name in evidence.EVIDENCE:
        assert evidence.has_evidence(name)
    assert not evidence.has_evidence(roster.BENCHMARK_OBJECT)
    assert not evidence.has_evidence("NO_SUCH_OBJECT")
    assert not evidence.has_evidence(None)  # type: ignore[arg-type]


def test_an_unknown_object_is_a_key_error():
    with pytest.raises(KeyError):
        evidence.evidence_for("NO_SUCH_OBJECT", None, None, date(2026, 10, 6), ["AAA"])  # type: ignore[arg-type]


def test_the_module_does_not_import_the_roster():
    """paper/roster.py imports strategies; evidence must load without it (no import cycle)."""
    pkg = Path(seer_engine.__file__).resolve().parent.parent
    env = dict(os.environ)
    env["PYTHONPATH"] = str(pkg) + os.pathsep + env.get("PYTHONPATH", "")
    code = (
        "import sys\n"
        "import seer_engine.strategies.evidence\n"
        "print('seer_engine.paper.roster' in sys.modules)\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, check=True, timeout=120)
    assert out.stdout.strip() == "False"


def test_bad_inputs_raise():
    m = market_of({"AAA": hist("AAA", uptrend(10))}, session_days(1)[0])
    d = session_days(10)[-1]
    with pytest.raises(TypeError):
        evidence.evidence_for("STRATEGY_A", m, F4, d, ["AAA"])
    with pytest.raises(TypeError):
        evidence.evidence_for("STRATEGY_C", m, STRATEGY_A_PARAMS, d, ["AAA"])
    with pytest.raises(TypeError):
        evidence.evidence_for("FACTOR", m, F1, d, ["AAA"])
    with pytest.raises(TypeError):
        evidence.evidence_for("TIMING", m, F4, d, ["AAA"])
    with pytest.raises(TypeError):
        evidence.evidence_for("FUNDAMENTAL", m, F4, d, ["AAA"])
    with pytest.raises(TypeError):
        evidence.evidence_for("STRATEGY_A", m, STRATEGY_A_PARAMS, d, "AAA")


# --------------------------------------------------------------------------- Strategy A and C

A_DAYS = session_days(260)
A_DATE = A_DAYS[250]  # 9 sessions of later bars follow it


def a_history() -> dict[str, History]:
    """Three steady risers that dip sharply on A_DATE (they pass A's rule), one that does not."""
    out: dict[str, History] = {}
    for k, (symbol, drop) in enumerate((("AAA", 1.0), ("BBB", 2.0), ("CCC", 3.0))):
        closes = dip(uptrend(len(A_DAYS), first=100.0 + 50.0 * k), at=250, drop=drop)
        out[symbol] = hist(symbol, closes, days=A_DAYS)
    out["DDD"] = hist("DDD", uptrend(len(A_DAYS), first=80.0), days=A_DAYS)
    out["SPY"] = hist("SPY", uptrend(len(A_DAYS), first=400.0), days=A_DAYS, volume=50_000_000.0)
    return out


@pytest.fixture(scope="module")
def a_market() -> Market:
    return market_of(a_history(), A_DAYS[0])


def test_strategy_a_facts(a_market):
    out = evidence.evidence_for("STRATEGY_A", a_market, STRATEGY_A_PARAMS, A_DATE, ["AAA", "BBB", "CCC", "DDD", "ZZZ"])
    assert set(out) == {"AAA", "BBB", "CCC", "DDD"}  # ZZZ has no bars: absent, not empty
    assert_plain(out)
    assert_distinct(out)
    for symbol in ("AAA", "BBB", "CCC"):
        facts = out[symbol]
        assert len(facts) == 5
        assert facts[0].startswith("It closed at $") and "above its 200-day average of $" in facts[0]
        assert "2-day strength score was" in facts[1] and "below 10 counts as a sharp short drop" in facts[1]
        assert "Over the last 2 trading days it fell" in facts[2]
        assert "changed hands" in facts[3] and "million" in facts[3]
        assert " of 3 stocks that passed the rule" in facts[4]
    ranks = sorted(out[s][4].split()[2] for s in ("AAA", "BBB", "CCC"))
    assert ranks == ["1st", "2nd", "3rd"]
    assert len(out["DDD"]) == 4  # eligible but did not pass: no place in the ranking


def test_strategy_c_is_a_under_its_own_a_params(a_market):
    symbols = ["AAA", "BBB", "CCC"]
    c = evidence.evidence_for("STRATEGY_C", a_market, STRATEGY_C_PARAMS, A_DATE, symbols)
    a = evidence.evidence_for("STRATEGY_A", a_market, STRATEGY_C_PARAMS.a, A_DATE, symbols)
    assert c == a and c


def test_strategy_a_reads_nothing_after_the_data_date():
    h = a_history()
    symbols = sorted(h)
    base = evidence.evidence_for("STRATEGY_A", market_of(cut_at(h, A_DATE), A_DAYS[0]), STRATEGY_A_PARAMS, A_DATE, symbols)
    wild = evidence.evidence_for("STRATEGY_A", market_of(later_bars_changed(h, A_DATE), A_DAYS[0]), STRATEGY_A_PARAMS, A_DATE, symbols)
    full = evidence.evidence_for("STRATEGY_A", market_of(h, A_DAYS[0]), STRATEGY_A_PARAMS, A_DATE, symbols)
    assert base == wild == full and base


def test_a_non_member_is_absent():
    h = a_history()
    m = Market(
        history=h,
        membership=Membership(intervals=tuple((s, A_DAYS[0], None) for s in sorted(h) if s != "BBB")),
        fx=(),
    )
    out = evidence.evidence_for("STRATEGY_A", m, STRATEGY_A_PARAMS, A_DATE, ["AAA", "BBB"])
    assert set(out) == {"AAA"}
    assert " of 2 stocks that passed the rule" in out["AAA"][4]


# --------------------------------------------------------------------------- FACTOR (F4)

F_DAYS = session_days(320)
F_DATE = F_DAYS[310]


def factor_history() -> dict[str, History]:
    """Five liquid names rising at different speeds, plus SPY above its 200-day average."""
    out: dict[str, History] = {}
    for k, symbol in enumerate(("AAA", "BBB", "CCC", "DDD", "EEE")):
        closes = [50.0 * (1.0 + 0.0004 * (k + 1)) ** t + (0.3 if t % 2 else -0.3) for t in range(len(F_DAYS))]
        out[symbol] = hist(symbol, closes, days=F_DAYS, volume=2_000_000.0)
    out["SPY"] = hist("SPY", uptrend(len(F_DAYS), first=400.0, step=0.5), days=F_DAYS, volume=50_000_000.0)
    return out


@pytest.fixture(scope="module")
def f_market() -> Market:
    return market_of(factor_history(), F_DAYS[0])


def test_factor_facts_for_f4(f_market):
    out = evidence.evidence_for("FACTOR", f_market, F4, F_DATE, ["EEE", "DDD", "AAA", "SPY"])
    assert set(out) == {"EEE", "DDD", "AAA"}  # SPY is never a factor stock
    assert_plain(out)
    assert_distinct(out)
    assert out["EEE"][0].startswith("Its price rose ") and out["EEE"][0].endswith("from 12 months ago to 1 month ago.")
    assert out["EEE"][1] == "It ranked 1st of 5 stocks checked on that move, strongest first."
    assert out["AAA"][1] == "It ranked 5th of 5 stocks checked on that move, strongest first."
    assert out["EEE"][2].startswith("SPY closed ") and "above its 200-day average" in out["EEE"][2]
    assert out["EEE"][2].endswith("so the method is allowed to hold stocks.")
    assert len(out["EEE"]) == 3  # momentum ranking: no volatility fact


def test_factor_volatility_is_stated_only_when_the_ranking_reads_it(f_market):
    calm = FactorParams("lowvol", top=2, trend=None, min_dollar_volume=0.0)
    out = evidence.evidence_for("FACTOR", f_market, calm, F_DATE, ["AAA", "EEE"])
    assert_plain(out)
    for facts in out.values():
        assert "calmest first" in facts[1]
        assert "a day over the last 60 trading days" in facts[2]
        assert len(facts) == 3  # no trend: no market-filter fact


def test_factor_reads_nothing_after_the_data_date():
    h = factor_history()
    symbols = sorted(h)
    base = evidence.evidence_for("FACTOR", market_of(cut_at(h, F_DATE), F_DAYS[0]), F4, F_DATE, symbols)
    wild = evidence.evidence_for("FACTOR", market_of(later_bars_changed(h, F_DATE), F_DAYS[0]), F4, F_DATE, symbols)
    assert base == wild and base


# --------------------------------------------------------------------------- TIMING (F1)


def test_timing_facts_for_f1(f_market):
    out = evidence.evidence_for("TIMING", f_market, F1, F_DATE, ["SPY", "BIL"])
    assert set(out) == {"SPY"}
    assert_plain(out)
    first, rule = out["SPY"]
    assert first.startswith("SPY closed at $") and "above its 200-day average of $" in first
    assert rule == "The rule holds SPY while SPY closes above its 200-day average, so it holds SPY."


def test_timing_explains_nothing_when_the_rule_is_off():
    falling = {"SPY": hist("SPY", [500.0 - 0.5 * t for t in range(len(F_DAYS))], days=F_DAYS)}
    assert evidence.evidence_for("TIMING", market_of(falling, F_DAYS[0]), F1, F_DATE, ["SPY"]) == {}


@pytest.mark.parametrize(
    "params, needle",
    [
        (TimingParams(hold="SSO", signal="SPY", rule="month_sma", n=10), "month-end closes"),
        (TimingParams(hold="SSO", signal="SPY", rule="abs_mom", n=252), "12 months earlier"),
        (TimingParams(hold="SSO", signal="SPY", rule="always", n=1), "at all times"),
    ],
)
def test_timing_other_rules(f_market, params, needle):
    h = dict(factor_history())
    h["SSO"] = hist("SSO", uptrend(len(F_DAYS), first=60.0), days=F_DAYS)
    out = evidence.evidence_for("TIMING", market_of(h, F_DAYS[0]), params, F_DATE, ["SSO"])
    assert_plain(out)
    assert any(needle in fact for fact in out["SSO"])


def test_timing_reads_nothing_after_the_data_date():
    h = factor_history()
    base = evidence.evidence_for("TIMING", market_of(cut_at(h, F_DATE), F_DAYS[0]), F1, F_DATE, ["SPY"])
    wild = evidence.evidence_for("TIMING", market_of(later_bars_changed(h, F_DATE), F_DAYS[0]), F1, F_DATE, ["SPY"])
    assert base == wild and base


# --------------------------------------------------------------------------- FUNDAMENTAL (FND)

FND_SYMBOLS = ("AAA", "BBB", "CCC", "DDD", "EEE")
FND_DAYS = session_days(230, date(2026, 1, 2))
FND_DATE = date(2026, 10, 30)


def fnd_history() -> dict[str, History]:
    return {
        s: hist(s, [6.0 + 2.0 * k + 0.002 * i for i in range(len(FND_DAYS))], days=FND_DAYS, volume=5_000_000.0)
        for k, s in enumerate(FND_SYMBOLS)
    }


def _fact(symbol: str, tag: str, unit: str, start: date | None, end: date, val: float, filed: date,
          taxonomy: str = "us-gaap", form: str = "10-K") -> Fact:
    return Fact(symbol=symbol, taxonomy=taxonomy, tag=tag, unit=unit, period_start=start, period_end=end,
                val=float(val), accn=f"{symbol}-{tag}-{end:%Y%m%d}", form=form, fy=end.year,
                fp="FY" if form == "10-K" else "Q", filed=filed)


_QUARTERS = [
    (date(y, m0, 1), date(y, m1, d1))
    for y in (2024, 2025, 2026)
    for m0, m1, d1 in ((1, 3, 31), (4, 6, 30), (7, 9, 30), (10, 12, 31))
][:10]
_EPS = (1.00, 1.10, 1.20, 1.30, 1.45, 1.70, 1.55, 1.80, 2.10, 2.00)


def fnd_panel(extra: tuple[Fact, ...] = ()) -> FundamentalPanel:
    """A real panel with every factor finite (the quarterly EPS run gives SUE), as test_paper_fnd builds it."""
    year_start, year_end, filed = date(2025, 1, 1), date(2025, 12, 31), date(2026, 2, 20)
    facts: list[Fact] = []
    for k, s in enumerate(FND_SYMBOLS):
        facts.append(_fact(s, "Assets", "USD", None, year_end, 1_000_000_000.0 + 1e8 * k, filed))
        facts.append(_fact(s, "StockholdersEquity", "USD", None, year_end, 400_000_000.0 + 2e7 * k, filed))
        facts.append(_fact(s, "EntityCommonStockSharesOutstanding", "shares", None, year_end,
                           10_000_000.0 + 1e6 * k, filed, taxonomy="dei"))
        facts.append(_fact(s, "NetIncomeLoss", "USD", year_start, year_end, 50_000_000.0 + 5e6 * k, filed))
        facts.append(_fact(s, "GrossProfit", "USD", year_start, year_end, 400_000_000.0 + 3e7 * k, filed))
        for i, (q_start, q_end) in enumerate(_QUARTERS):
            facts.append(_fact(s, "EarningsPerShareDiluted", "USD/shares", q_start, q_end, _EPS[i] + 0.07 * k,
                               q_end + timedelta(days=40), form="10-Q"))
    return FundamentalPanel.from_facts(tuple(facts) + extra)


@pytest.fixture(scope="module")
def fnd_market() -> Market:
    return market_of(fnd_history(), FND_DAYS[0], fnd_panel())


def test_fundamental_facts_for_fnd(fnd_market):
    out = evidence.evidence_for("FUNDAMENTAL", fnd_market, FND, FND_DATE, list(FND_SYMBOLS))
    assert set(out) == set(FND_SYMBOLS)
    assert_plain(out)
    assert_distinct(out)
    places = sorted(facts[0].split()[2] for facts in out.values())
    assert places == ["1st", "2nd", "3rd", "4th", "5th"]
    for facts in out.values():
        assert len(facts) == 6
        assert "of 5 companies checked on a combined score of 4 measures" in facts[0]
        assert "of its stock-market value" in facts[1]
        assert "on its shareholders' money" in facts[2]
        assert "of everything it owns" in facts[3]
        assert "the same quarter a year earlier" in facts[4]
        assert facts[5] == "Its latest financial filing used here is 252 days old."  # 2026-02-20 -> 2026-10-30
        assert re.search(r"(the highest of the 5|the lowest of the 5|higher than \d+% of the other) companies checked\.$", facts[1])


def test_fundamental_single_factor(fnd_market):
    out = evidence.evidence_for("FUNDAMENTAL", fnd_market, FundamentalParams(rank="quality", top=2), FND_DATE, ["AAA", "EEE"])
    assert_plain(out)
    for facts in out.values():
        assert "how much it earns on its shareholders' money, highest first" in facts[0]
        assert len(facts) == 3


def test_fundamental_without_a_panel_explains_nothing():
    assert evidence.evidence_for("FUNDAMENTAL", market_of(fnd_history(), FND_DAYS[0]), FND, FND_DATE, ["AAA"]) == {}


def test_fundamental_reads_nothing_after_the_data_date():
    h = fnd_history()
    later = date(2026, 11, 3)
    assert later > FND_DATE
    restated = tuple(
        _fact(s, "StockholdersEquity", "USD", None, date(2026, 9, 30), 9e9, later) for s in FND_SYMBOLS
    )
    base = evidence.evidence_for("FUNDAMENTAL", market_of(cut_at(h, FND_DATE), FND_DAYS[0], fnd_panel()), FND, FND_DATE, list(FND_SYMBOLS))
    wild = evidence.evidence_for(
        "FUNDAMENTAL", market_of(later_bars_changed(h, FND_DATE), FND_DAYS[0], fnd_panel(restated)), FND, FND_DATE, list(FND_SYMBOLS)
    )
    assert base == wild and base


# --------------------------------------------------------------------------- formatting


@pytest.mark.parametrize(
    "fn, x, expected",
    [
        (evidence._pct, 0.0614, "6.1%"),
        (evidence._pct, -0.31, "31%"),
        (evidence._money, 1231.4, "$1,231.40"),
        (evidence._big_money, 45_200_000.0, "$45 million"),
        (evidence._big_money, 1_230_000_000.0, "$1.2 billion"),
        (evidence._ordinal, 1, "1st"),
        (evidence._ordinal, 12, "12th"),
        (evidence._ordinal, 22, "22nd"),
        (evidence._ordinal, 413, "413th"),
        (evidence._span, 252, "12 months"),
        (evidence._span, 21, "1 month"),
        (evidence._span, 5, "5 trading days"),
    ],
)
def test_formatting(fn, x, expected):
    assert fn(x) == expected


def test_every_function_is_deterministic(a_market, f_market, fnd_market):
    for name, m, p, d, symbols in (
        ("STRATEGY_A", a_market, STRATEGY_A_PARAMS, A_DATE, ["AAA", "BBB"]),
        ("FACTOR", f_market, F4, F_DATE, ["AAA", "EEE"]),
        ("TIMING", f_market, F1, F_DATE, ["SPY"]),
        ("FUNDAMENTAL", fnd_market, FND, FND_DATE, ["AAA", "EEE"]),
    ):
        assert evidence.evidence_for(name, m, p, d, symbols) == evidence.evidence_for(name, m, p, d, symbols)


def test_facts_are_plain_str(a_market, fnd_market):
    """Facts are exact ``str`` values (JSON-ready for phase 2's jsonb column), never numpy strings."""
    for out in (
        evidence.evidence_for("STRATEGY_A", a_market, STRATEGY_A_PARAMS, A_DATE, ["AAA"]),
        evidence.evidence_for("FUNDAMENTAL", fnd_market, FND, FND_DATE, ["AAA"]),
    ):
        assert out and all(type(f) is str for facts in out.values() for f in facts)
```
**Impact:** adds 35 tests (34 + the fresh-interpreter import test). No fixture or helper module is edited.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/why-this-pick-pipeline && engine/.venv/bin/ruff check engine` (clean) and `engine/.venv/bin/python -c "import seer_engine.strategies.evidence as e; print(sorted(e.EVIDENCE))"`
**Tests:**
- `cd /home/miftah/.worktrees/seer/why-this-pick-pipeline/engine && .venv/bin/pytest tests/test_evidence.py tests/test_strategy_purity.py -q` (all pass)
- Invariant 1, full suite: `docker start seer-pg` then `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q` — passes except the two known Python-3.12-only failures (`test_f_fundamental.py::test_allocator_shape`, `test_market_fundamentals.py::test_adding_the_hook_does_not_change_the_allocator_check`). Use the worktree's own `engine/.venv`, never main's. Then `cd web && npx vitest run && npx tsc --noEmit` (unaffected by this phase, still part of invariant 1).
- `tests/test_paper_roster.py` stays green with unchanged `PINS` (no roster/params file touched).
**Manual check:** none required; optionally print one object's facts on a synthetic market (the "Real output" blocks above came from exactly that).
**Exit criteria:** `strategies/evidence.py` exists with `EVIDENCE` keyed by the five non-benchmark `RESOLVER` names; `tests/test_evidence.py` passes, showing distinct plain-word facts per symbol, no look-ahead, no codes or ids; `test_strategy_purity.py` passes with the new module in its glob; no existing file changed (`git diff --stat` shows only the two new files).

## Handoffs

- **Phase 2 (R1, R6):** call `evidence.evidence_for(e.object_name, tonight.view(s), e.params, s, symbols)` inside a catch-all helper. Store each present value as a JSON array (`list(facts)`); a symbol absent from the result stores NULL. Do not pass the idle symbol (it would simply be absent anyway). For C, `e.params` is `CParams` — supported. For the would-pick-now preview, pass the preview targets' symbols with the same `s`. TIMING returns `{}` on a night its rule is off, which is also a night it targets nothing.
- **Phase 3 (R2, R3):** the numbers check should parse the fact strings using the shapes in "Fact strings" above; do not import the private `_`-helpers. No fact holds a `BANNED` word (reconciled: the trend fact says "allowed to hold stocks"). Note the integers embedded in words ("2-day", "200-day", "out of 100", "last 5", "of 412", "4 measures", "252 days") are numbers too and are all present in the facts. Prompt should include all facts of a pick; FUNDAMENTAL picks carry 6.
- **Phase 4 (R7):** gate on `evidence.has_evidence(object_name)`. Any new `RESOLVER` key added by a later promotion must also get an `EVIDENCE` entry or `test_every_roster_object_but_the_benchmark_has_evidence` fails — that is intended and should be named in the explore skill's promotion step.
- **Phase 5 (R5, R8):** the facts are already owner-safe plain English; render them as a list when the explanation is NULL. C's news-check line is not in these facts and must stay as its own line.
- Not done here (no requirement in this phase): evidence for lab-only allocators (`BLEND`, `VOLTARGET`, `PICKS`, `CALENDAR`, `F_ROTATION`, `F_SWING`, `A2`, `B`) — none is a `RESOLVER` key today; a future promotion adds its function together with its resolver entry.

## Rollback

Delete `engine/src/seer_engine/strategies/evidence.py` and `engine/tests/test_evidence.py` (or revert this phase's commit). Nothing else references them until Phase 2 lands; if Phase 2/4 have landed, revert those first.
