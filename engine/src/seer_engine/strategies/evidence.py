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


# --------------------------------------------------------------------------- RESIDVOL (lab M0011)


def residvol_evidence(market: Market, params: Any, data_date: date, symbols: Sequence[str]) -> dict[str, Facts]:
    """``RESIDVOL`` (lab M0011, braked residual momentum): the stock's rise beyond what the market's
    move explains, its place among the stocks checked on that, the market filter, and how much of
    the money the volatility brake lets the method hold tonight."""
    # Imported here, not at module level: the lab method modules import backtest.dev, and a
    # module-level import would close a strategies -> backtest cycle (see the module docstring).
    from seer_engine.lab.methods.m0001_momentum_own_vol_scaling import basket_scale
    from seer_engine.lab.methods.m0007_residual_momentum import RESIDMOM, build_grid, residual_scores
    from seer_engine.lab.methods.m0011_raw_residual_own_vol import ResidVolParams

    p: ResidVolParams = _typed("RESIDVOL", params, ResidVolParams)
    inner = p.inner
    wanted = _wanted(symbols)
    history = _cut(market, data_date)
    members = market.membership.members_on(data_date)
    rows = factor_rows(history, members, data_date, inner.inner)
    grid = build_grid(history, inner.market) if rows else None
    if grid is None:
        return {}
    scores = residual_scores(grid, [r.symbol for r in rows], data_date, inner)
    ranked = sorted((s for s in scores if math.isfinite(scores[s])), key=lambda s: (-scores[s], s))
    n = len(ranked)
    if n == 0:
        return {}
    picks = RESIDMOM.targets(history, members, data_date, frozenset(), inner)
    scale = basket_scale(history, picks, data_date, p.n, p.target_vol)
    held_share = 1.0 if scale is None else float(scale)
    months = _span(inner.mom_n)
    skip = _span(inner.skip)
    brake = (
        f"Over the last {_span(p.n)}, its picks together swung more than the {_pct(float(p.target_vol))} "
        f"a year the method allows, so it puts {_pct(held_share)} of its money in stocks and keeps the "
        "rest in cash."
        if scale is not None
        else f"Over the last {_span(p.n)}, its picks together swung less than the {_pct(float(p.target_vol))} "
        "a year the method allows, so it puts all its money in stocks."
    )
    on = factor_trend_on(history, data_date, inner.inner)
    out: dict[str, Facts] = {}
    for symbol in wanted:
        score = scores.get(symbol)
        if score is None or not math.isfinite(score) or symbol not in ranked:
            continue
        # The score is the sum of daily returns left after taking out the market's move: a
        # running total, not a compounded return, hence "added up to about".
        direction = "gains" if score > 0 else "losses"
        beyond = (
            f"Beyond what the market's own move explains, its daily {direction} from {months} ago to "
            f"{skip} ago added up to about {_pct(score)}."
        )
        facts = [
            beyond,
            f"It ranked {_ordinal(ranked.index(symbol) + 1)} of {n} stocks checked on that, strongest first.",
            brake,
        ]
        if inner.inner.trend is not None:
            facts.append(_trend_fact(history, data_date, inner.inner.trend, on))
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
    "RESIDVOL": residvol_evidence,
}


def evidence_for(
    object_name: str, market: Market, params: Any, data_date: date, symbols: Sequence[str]
) -> dict[str, Facts]:
    """``EVIDENCE[object_name](market, params, data_date, symbols)``; KeyError for an unknown name."""
    return EVIDENCE[object_name](market, params, data_date, symbols)


def has_evidence(object_name: str) -> bool:
    """True when ``object_name`` has an evidence function (what ``promote`` requires)."""
    return isinstance(object_name, str) and object_name in EVIDENCE
