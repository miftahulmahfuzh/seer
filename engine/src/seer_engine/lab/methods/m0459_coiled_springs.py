"""M0459 — Hold the index members whose daily range has shrunk to the bottom of their own year.

Source: the practitioner "volatility squeeze" / NR7 range-contraction lore (Crabel's narrow-range
days, Bollinger-band squeezes; blogs and trading books, decades old). Published long before the
dev window ends, so a crowd had time to trade it: the dev result is more likely a fading edge
than a fresh one, and the 2009-2015 era is the first filter.

The frame is the lab's usual book (M0348's): point-in-time members, the $5 price and 20M-dollar
volume screen, 20 equal slots (a slot with no qualifying name stays cash), monthly, fractional
shares at Gotrade's real fees, and the SPY 200-day switch on every arm but one. Only the ranking
key and the pool differ. The key is the 20-bar average true range as a share of close, ranked
against the same name's own last 250 daily readings (today's reading included): its percentile,
0 = the quietest day of the year. A name is *coiled* at percentile <= 0.10 and *wide* at >= 0.90.
"Above trend" is close above the mean of the last 50 closes. Names with a missing or invalid bar
in the span are not scored, identically in every arm.

Arms (six, the lab's cap), each on the pool of scored names:
COIL holds the coiled names that are above trend, quietest first (the idea). WIDE holds the wide
names above trend, widest first (the mirror: same costs, opposite opinion). SQZ-ALL holds the
coiled names with no trend condition (does the 50-day condition carry the result). R1 and R2
hash-rank the above-trend scored pool (chance spreads, priced on the same trend condition,
behind the switch), and R1-NOSW is R1's order with no switch: the always-invested no-opinion arm
that prices the switch's habit so the COIL/WIDE reversal splits into signal and dressing.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import draw
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 1)

MODES = ("coil", "wide", "sqzall", "blind")
ATR_WIN = 20  # bars in the average true range
HIST = 250  # daily ATR readings the percentile ranks against
TREND_WIN = 50  # bars in the above-trend mean
COIL_AT = 0.10
WIDE_AT = 0.90
NEED = HIST + ATR_WIN  # bars of history ending on data_date, plus one prior close
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class CoilParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "coil"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "atr_win": str(ATR_WIN),
               "hist": str(HIST), "trend_win": str(TREND_WIN), "coil_at": str(COIL_AT),
               "wide_at": str(WIDE_AT)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> CoilParams:
    if not isinstance(params, CoilParams):
        raise TypeError(f"params must be CoilParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> dict[str, tuple[float, bool]]:
    """(percentile of today's ATR20/close in its own last 250 readings, close above 50-bar mean)."""
    out: dict[str, tuple[float, bool]] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < NEED:
            continue
        hi = h.high[i - NEED + 1 : i + 1]
        lo = h.low[i - NEED + 1 : i + 1]
        c = h.close[i - NEED : i + 1]
        if not (np.all(np.isfinite(hi)) and np.all(np.isfinite(lo)) and np.all(np.isfinite(c))):
            continue
        if not (np.all(lo > 0.0) and np.all(hi >= lo) and np.all(c > 0.0)):
            continue
        pc = c[:-1]
        tr = np.maximum(hi - lo, np.maximum(np.abs(hi - pc), np.abs(lo - pc))) / c[1:]
        csum = np.concatenate(([0.0], np.cumsum(tr)))
        atr = (csum[ATR_WIN:] - csum[:-ATR_WIN]) / ATR_WIN  # HIST readings, last = today
        pct = float(np.mean(atr <= atr[-1]))
        above = bool(c[-1] > float(np.mean(c[-TREND_WIN:])))
        out[s] = (pct, above)
    return out


def choose(rows: list[FactorRow], scores: dict[str, tuple[float, bool]],
           params: CoilParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in scores]
    mode = params.mode
    if mode == "coil":
        pool = [r for r in pool if scores[r.symbol][0] <= COIL_AT and scores[r.symbol][1]]
        key = {r.symbol: scores[r.symbol][0] for r in pool}
    elif mode == "wide":
        pool = [r for r in pool if scores[r.symbol][0] >= WIDE_AT and scores[r.symbol][1]]
        key = {r.symbol: -scores[r.symbol][0] for r in pool}
    elif mode == "sqzall":
        pool = [r for r in pool if scores[r.symbol][0] <= COIL_AT]
        key = {r.symbol: scores[r.symbol][0] for r in pool}
    else:
        pool = [r for r in pool if scores[r.symbol][1]]
        key = {r.symbol: float(draw(params.seed, r.symbol)) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: params.inner.top]


@dataclass
class CoilPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, tuple[float, bool]]] = field(default_factory=dict, repr=False)


class CoiledSpringsAllocator:
    """The lab's index-member book ranked on how quiet a name's range is against its own year."""

    id = "M0459"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), NEED + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {MARKET}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: CoilPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: CoilParams) -> tuple[Target, ...]:
        if not trend_on(history, data_date, p.inner):
            return ()
        if prepared is None:
            rows = factor_rows(history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        syms = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED)
        if prepared is None:
            scores = scored_names(history, syms, data_date)
        else:
            scores = prepared.cache.get(data_date) or scored_names(history, syms, data_date)
            prepared.cache[data_date] = scores
        return targets_from_rows(choose(rows, scores, p), p)  # type: ignore[arg-type]

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> CoilPrepared:
        return CoilPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CoilPrepared):
            raise TypeError(f"prepared must be CoilPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


COILED = CoiledSpringsAllocator()


def _v(suffix: str, params: CoilParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0459-{suffix}", family="M0459",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=COILED, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0459",
    name=("Coiled springs: stocks whose daily range has shrunk to the bottom of their own year, "
          "then break out"),
    family="stock-volatility-compression",
    source_kind="blog",
    source_ref="volatility squeeze / NR7 range contraction (practitioner literature)",
    parent_id=None,
    hypothesis=(
        "A stock whose 20-day average true range (as a share of close) sits in the lowest tenth "
        "of its own last 250 daily readings, and that closes above its 50-day average, is a "
        "coiled spring: quiet ranges give way to a move, and above-trend names move up "
        "(practitioner squeeze / NR7 lore, decades old, so likely crowded and faded by the end of "
        "the dev window). Every month the book scores each F4-screened index member and holds the "
        "coiled above-trend names, quietest first, up to 20 equal slots (an unfilled slot stays "
        "cash), monthly, fractional shares at Gotrade's real fees, behind SPY's 200-day switch. "
        "Arms: COIL (the idea), WIDE (the mirror: widest-range tenth, above trend, same costs), "
        "SQZ-ALL (coiled with no trend condition: does the 50-day rule carry it), R1 and R2 (hash "
        "order on the above-trend scored pool behind the same switch), R1-NOSW (R1's order, no "
        "switch: the no-opinion always-invested arm that prices the switch's habit apart from the "
        "opinion). Predictions, written now: COIL beats WIDE on funded CAGR; COIL beats the better "
        "of R1 and R2 by less than their spread plus 2 points a year; COIL trails SPY in "
        "2009-2015; COIL often holds fewer than 20 names and sits partly in cash; COIL's worst "
        "fall is under 25% behind the switch; R1-NOSW falls over 40%, so the switch and not the "
        "ranking carries the fall."
    ),
    expected_failure=(
        "Compression is just low volatility again: the coiled names are calm large caps and the "
        "book earns the lab's known calm-tilt-behind-the-switch result (M0348, M0350, M0358: random "
        "picks behind the switch matched the range books). The coiled tenth is rare in index "
        "members, so slots sit in cash and the cash drag in a rising decade costs several points a "
        "year. Coiling is not direction: the 50-day condition may be the only live part, which "
        "SQZ-ALL tests. After a calm spell the break can go down as easily as up. Highs and lows on "
        "back-adjusted early prices can carry errors; names failing the high >= low > 0 check are "
        "dropped from every arm alike."
    ),
    candidates=(
        _v("COIL", CoilParams(N20, "coil"),
           "Coiled (ATR percentile <= 0.10) and above the 50-day mean, quietest first, behind the switch: the idea"),
        _v("WIDE", CoilParams(N20, "wide"),
           "Widest-range tenth (>= 0.90) above the 50-day mean, behind the switch: the mirror"),
        _v("SQZ-ALL", CoilParams(N20, "sqzall"),
           "Coiled with no trend condition, behind the switch: does the 50-day rule matter"),
        _v("R1", CoilParams(N20, "blind", 459),
           "Control: hash-ranked above-trend scored pool, seed 459, behind the switch"),
        _v("R2", CoilParams(N20, "blind", 460),
           "Control: hash-ranked above-trend scored pool, seed 460, behind the switch"),
        _v("R1-NOSW", CoilParams(NOSW, "blind", 459),
           "No-opinion always-invested arm: R1's order with no switch, prices the switch's habit"),
    ),
    seen_keys=(
        "concept:volatility-squeeze",
        "concept:range-contraction-breakout",
    ),
)
