"""M0350 — Hold the stocks whose daily swing is small (or large) for their ordinary volatility.

Variation of M0348, which found that the mean daily high-low range ranks nothing that plain
close-to-close volatility does not (its narrow and wide books both sat inside the chance spread
of random picks behind the switch). The range minus the volatility is the only part left that
plain volatility cannot see, so this ranks on their ratio: mean of (high - low) / close over the
last 21 bars divided by the standard deviation of the daily close-to-close return over the same
bars. A high ratio means much of the swing happened inside the day and was undone by the close
(intraday noise, reversal); a low ratio means the day's travel ended where it went.
Idea published as a range-based-volatility literature theme (Parkinson 1980 onward); the ratio
itself is not a published anomaly the lab knows of, so decay is not the risk, emptiness is.

Same frame as M0348: point-in-time members, F4 screen, 20 equal slots, monthly, fractional
shares at Gotrade's real fees, SPY 200-day switch. Only the ranking key differs.

Arms (six, the lab's cap): LOW and HIGH ratio (the idea and its mirror), VM-LOW and VM-HIGH
(volatility-matched random controls: the pool is cut into five volatility quintiles, and the
control holds as many hash-drawn names from each quintile as its treatment arm holds, so it has
the treatment's volatility profile and none of its ratio opinion), R1 (hash order on the pool,
behind the switch) and R1-NOSW (same order, no switch: the no-opinion always-invested arm).
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import draw
from seer_engine.lab.methods.m0348_price_range_competition import WIN, scored_names
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

MODES = ("low", "high", "vm-low", "vm-high", "blind")
MARKET = "SPY"
BUCKETS = 5

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class RatioParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "low"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "win": str(WIN), "buckets": str(BUCKETS)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> RatioParams:
    if not isinstance(params, RatioParams):
        raise TypeError(f"params must be RatioParams, got {type(params).__name__}")
    return params


def choose(rows: list[FactorRow], rng: dict[str, float], vol: dict[str, float],
           params: RatioParams) -> list[FactorRow]:
    """Pick ``top`` names. Names with zero volatility have no ratio and are dropped from every arm."""
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in rng and vol[r.symbol] > 0.0]
    top = params.inner.top
    ratio = {r.symbol: rng[r.symbol] / vol[r.symbol] for r in pool}
    if params.mode == "blind":
        pool.sort(key=lambda r: (float(draw(params.seed, r.symbol)), r.symbol))
        return pool[:top]
    sign = 1.0 if params.mode in ("low", "vm-low") else -1.0
    ranked = sorted(pool, key=lambda r: (sign * ratio[r.symbol], r.symbol))
    treat = ranked[:top]
    if params.mode in ("low", "high"):
        return treat
    # volatility-matched control: same count per volatility quintile as the treatment holds
    by_vol = sorted(pool, key=lambda r: (vol[r.symbol], r.symbol))
    n = len(by_vol)
    bucket = {r.symbol: min(BUCKETS - 1, i * BUCKETS // n) for i, r in enumerate(by_vol)}
    need: dict[int, int] = {}
    for r in treat:
        need[bucket[r.symbol]] = need.get(bucket[r.symbol], 0) + 1
    out: list[FactorRow] = []
    for b in sorted(need):
        cand = [r for r in pool if bucket[r.symbol] == b]
        cand.sort(key=lambda r: (float(draw(params.seed, r.symbol)), r.symbol))
        out.extend(cand[: need[b]])
    return out


@dataclass
class RatioPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, tuple[dict[str, float], dict[str, float]]] = field(default_factory=dict, repr=False)


class RangeToVolAllocator:
    """The lab's index-member book ranked on mean daily range over close-to-close volatility."""

    id = "M0350"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), WIN + 1)

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

    def _run(self, prepared: RatioPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: RatioParams) -> tuple[Target, ...]:
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
        return targets_from_rows(choose(rows, scores[0], scores[1], p), p)  # type: ignore[arg-type]

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> RatioPrepared:
        return RatioPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, RatioPrepared):
            raise TypeError(f"prepared must be RatioPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


RANGEVOL = RangeToVolAllocator()


def _v(suffix: str, params: RatioParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0350-{suffix}", family="M0350",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=RANGEVOL, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0350",
    name="Range versus volatility: hold the stocks whose daily swing is small for their ordinary volatility",
    family="stock-range-to-volatility-ratio",
    source_kind="variation",
    source_ref="M0348 (range adds nothing over close-to-close volatility; this ranks on what is left)",
    parent_id="M0348",
    hypothesis=(
        "M0348 found the daily high-low range adds nothing over close-to-close volatility. The part "
        "plain volatility cannot see is the ratio: the mean of (high - low) / close over 21 bars "
        "divided by the standard deviation of daily close-to-close returns over the same bars. "
        "A low ratio means days ended near where they travelled; a high ratio means much of the "
        "swing was intraday and reversed by the close. Every month the book scores each F4-screened "
        "index member on that ratio and holds the 20 lowest (LOW) equal weight, monthly, fractional "
        "shares at Gotrade's real fees, behind SPY's 200-day switch. Arms: LOW (idea), HIGH (mirror, "
        "same costs), VM-LOW and VM-HIGH (volatility-matched random controls: same count per "
        "volatility quintile as the treatment arm, hash-drawn within the quintile, so the ratio "
        "opinion is removed and the volatility profile kept), R1 (hash order on the pool, switch) "
        "and R1-NOSW (same order, no switch: the always-invested no-opinion arm). Predictions, "
        "written now: LOW and HIGH both land within 2 points a year of their own volatility-matched "
        "control (the ratio is noise); LOW and HIGH differ by under 2 points a year; neither beats "
        "SPY in 2009-2015; R1-NOSW falls over 40% so the switch carries the fall. Source is a "
        "variation: no publication year to fade, the ratio is not a known anomaly."
    ),
    expected_failure=(
        "The ratio is an almost constant number (range over volatility is about 1.6 to 2 for any "
        "stock with ordinary tails), so the ranking is dominated by estimation noise, the 20 picks "
        "are close to a random draw, and every arm behind the switch lands where random picks "
        "behind the switch land. Any apparent edge is the switch plus the quintile tilt in the "
        "control. Ratio extremes may also flag bad prints (stale or gapped bars) rather than "
        "behaviour. Controls draw once per seed, a thin chance spread."
    ),
    candidates=(
        _v("LOW", RatioParams(N20, "low"),
           "The 20 lowest range-to-volatility ratio over 21 bars, behind the SPY switch: the idea"),
        _v("HIGH", RatioParams(N20, "high"),
           "The 20 highest ratio, behind the switch: the mirror"),
        _v("VM-LOW", RatioParams(N20, "vm-low", 350),
           "Volatility-matched random control for LOW: same count per volatility quintile, hash-drawn"),
        _v("VM-HIGH", RatioParams(N20, "vm-high", 351),
           "Volatility-matched random control for HIGH: same count per volatility quintile, hash-drawn"),
        _v("R1", RatioParams(N20, "blind", 348),
           "Control: hash-ranked scored pool, seed 348, behind the switch"),
        _v("R1-NOSW", RatioParams(NOSW, "blind", 348),
           "No-opinion always-invested arm: R1's order with no switch, prices the switch's habit"),
    ),
    seen_keys=("concept:range-to-volatility-ratio",),
)
