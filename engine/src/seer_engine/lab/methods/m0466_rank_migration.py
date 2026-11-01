"""M0466 — Hold the index members whose size rank has climbed the most in a year.

Source: knowledge. The idea that arrival into prominence draws index and institutional demand
while decline loses it echoes the attention and index-inclusion literature (Barber-Odean attention,
Shleifer 1986 index demand), published decades before the dev window ends, so a crowd had time
to trade it: the dev result is more likely a fading edge than a fresh one, and 2009-2015 is the
first filter.

The frame is the lab's usual book (M0459's): point-in-time members, the $5 price and 20M-dollar
volume screen, 20 equal slots (a slot with no qualifying name stays cash), monthly, fractional
shares at Gotrade's real fees, and the SPY 200-day switch on every arm but two. The store has no
company size before the shares file, so the size proxy is the trailing 60-day mean of close times
volume. Each month the screened members that have both readings are ranked by it today and again
252 sessions earlier, each as a percentile (0 = smallest) within that same set of names; the key
is today's percentile minus last year's. RISE holds the tenth of the set with the largest climb,
FALL the tenth with the largest drop (each capped at the 20 slots, at least one name).

Arms (six, the lab's cap): RISE (the idea), FALL (the mirror: same costs, opposite opinion), R1
and R2 (hash order on the whole scored set behind the same switch: chance spreads), R1-NOSW (R1's
order, no switch: the always-invested no-opinion arm that prices the switch's habit) and
RISE-NOSW (the idea with no switch: the 2x2 pair, so the switch's habit and the opinion separate).
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

MODES = ("rise", "fall", "blind")
DV_WIN = 60  # bars in the dollar-volume (size proxy) mean
LAG = 252  # sessions back for the earlier rank
NEED = LAG + DV_WIN - 1  # index of the first bar that can be scored
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class MigParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "rise"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "dv_win": str(DV_WIN),
               "lag": str(LAG)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> MigParams:
    if not isinstance(params, MigParams):
        raise TypeError(f"params must be MigParams, got {type(params).__name__}")
    return params


def _dv(h: History, end: int) -> float | None:
    """Mean close x volume over the DV_WIN bars ending at index ``end`` inclusive."""
    c = h.close[end - DV_WIN + 1 : end + 1]
    v = h.volume[end - DV_WIN + 1 : end + 1]
    if not (np.all(np.isfinite(c)) and np.all(np.isfinite(v))):
        return None
    if not (np.all(c > 0.0) and np.all(v >= 0.0)):
        return None
    m = float(np.mean(c * v))
    return m if m > 0.0 else None


def _pct(vals: dict[str, float]) -> dict[str, float]:
    """Percentile within the set, 0 = smallest; ties share the mean-free lower-rank rule."""
    n = len(vals)
    order = sorted(vals, key=lambda s: (vals[s], s))
    return {s: i / (n - 1) for i, s in enumerate(order)} if n > 1 else {s: 0.5 for s in order}


def rank_change(history: Mapping[str, History], symbols: list[str], data_date: date
                ) -> dict[str, float]:
    """Today's size percentile minus the one LAG sessions earlier, both within the same names."""
    now: dict[str, float] = {}
    then: dict[str, float] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < NEED:
            continue
        a = _dv(h, i)
        b = _dv(h, i - LAG)
        if a is None or b is None:
            continue
        now[s] = a
        then[s] = b
    if len(now) < 5:
        return {}
    pn, pt = _pct(now), _pct(then)
    return {s: pn[s] - pt[s] for s in now}


def choose(rows: list[FactorRow], change: dict[str, float], params: MigParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in change]
    if not pool:
        return []
    mode = params.mode
    if mode == "rise":
        key = {r.symbol: -change[r.symbol] for r in pool}
        n = max(1, -(-len(pool) // 10))
    elif mode == "fall":
        key = {r.symbol: change[r.symbol] for r in pool}
        n = max(1, -(-len(pool) // 10))
    else:
        key = {r.symbol: float(draw(params.seed, r.symbol)) for r in pool}
        n = params.inner.top
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: min(n, params.inner.top)]


@dataclass
class MigPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, float]] = field(default_factory=dict, repr=False)


class RankMigrationAllocator:
    """The lab's index-member book ranked on the 12-month change in a name's size rank."""

    id = "M0466"

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

    def _run(self, prepared: MigPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: MigParams) -> tuple[Target, ...]:
        if not trend_on(history, data_date, p.inner):
            return ()
        if prepared is None:
            rows = factor_rows(history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        syms = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED)
        if prepared is None:
            change = rank_change(history, syms, data_date)
        else:
            change = prepared.cache.get(data_date) or rank_change(history, syms, data_date)
            prepared.cache[data_date] = change
        return targets_from_rows(choose(rows, change, p), p)  # type: ignore[arg-type]

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> MigPrepared:
        return MigPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, MigPrepared):
            raise TypeError(f"prepared must be MigPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


MIGRATE = RankMigrationAllocator()


def _v(suffix: str, params: MigParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0466-{suffix}", family="M0466",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=MIGRATE, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0466",
    name="Climbing the ranks: members whose size rank rose the most over 12 months, against those that fell the most",
    family="stock-size-rank-migration",
    source_kind="knowledge",
    source_ref="",
    parent_id=None,
    hypothesis=(
        "A company whose size rank among index members has risen over the last year is arriving "
        "in prominence: index and institutional demand follows, and the arrival keeps drawing "
        "buyers; a company sliding down the ranks loses that demand (attention and index-demand "
        "ideas, published in the 1980s-2000s, so likely crowded and faded by the end of the dev "
        "window). The store has no size before the shares file, so the proxy is the 60-day mean of "
        "close times volume. Every month the F4-screened members with both readings are ranked "
        "today and 252 sessions earlier, each as a percentile within that same set; RISE holds the "
        "tenth with the largest climb, FALL the tenth with the largest fall, up to 20 equal slots, "
        "monthly, fractional shares at Gotrade's real fees, behind SPY's 200-day switch. Arms: RISE "
        "(the idea), FALL (the mirror), R1 and R2 (hash order on the whole scored set behind the "
        "same switch), R1-NOSW (R1 with no switch: the always-invested no-opinion arm pricing the "
        "switch's habit), RISE-NOSW (the idea with no switch: the 2x2 pair). SPY is the benchmark "
        "column. Predictions, written now: RISE beats FALL on funded CAGR; RISE beats the better "
        "of R1 and R2 by less than their spread plus 2 points a year; RISE trails SPY in "
        "2009-2015; RISE-NOSW falls over 40%, so the switch and not the ranking carries the fall."
    ),
    expected_failure=(
        "Rising dollar volume is mostly a price spike or a news burst, so RISE is a short-term "
        "momentum and attention book that the lab's momentum kin already say fades behind the "
        "switch; a hash draw of the same pool does as well (M0333, M0425, M0459 pattern). Dollar "
        "volume is not size: a volume surge in a falling stock reads as a climb, and a 252-session "
        "gap spans earnings regimes. The percentile is taken over today's screened names, so a "
        "name that was thin a year ago and passes the screen now is favoured, a survivorship tilt "
        "toward winners that the dev store cannot see past. The switch's time in cash in a rising "
        "decade, not the ranking, decides the result against SPY."
    ),
    candidates=(
        _v("RISE", MigParams(N20, "rise"),
           "Tenth with the largest 12-month climb in size-rank percentile, behind the switch: the idea"),
        _v("FALL", MigParams(N20, "fall"),
           "Tenth with the largest 12-month fall in size-rank percentile, behind the switch: the mirror"),
        _v("R1", MigParams(N20, "blind", 466),
           "Control: hash-ranked scored set, seed 466, behind the switch"),
        _v("R2", MigParams(N20, "blind", 467),
           "Control: hash-ranked scored set, seed 467, behind the switch"),
        _v("R1-NOSW", MigParams(NOSW, "blind", 466),
           "No-opinion always-invested arm: R1's order with no switch, prices the switch's habit"),
        _v("RISE-NOSW", MigParams(NOSW, "rise"),
           "The idea with no switch: the 2x2 pair beside RISE and R1-NOSW"),
    ),
    seen_keys=(
        "concept:size-rank-migration",
        "concept:dollar-volume-rank-change",
    ),
)
