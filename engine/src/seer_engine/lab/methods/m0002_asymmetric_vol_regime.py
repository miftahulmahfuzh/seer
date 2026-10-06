"""M0002 — Momentum de-risked only in high-volatility regimes (asymmetric own-vol scaling).

Source: variation of M0001 (Barroso & Santa-Clara 2015, "Momentum has its moments"), driven by
M0001's own result: own-vol scaling to a fixed 10-12% target fixed the drawdown (22.2% -> 11-13%)
but cut CAGR from +16.2% to +6.1-7.6%, below SPY TR's +7.9%.

Idea: a top-20 momentum book runs at roughly 20-25% annualized volatility, so a fixed 10-12%
target holds it near half exposure *all the time*, not only in the crash spells it was meant to
guard against. The crash risk is concentrated where the book's volatility is unusually high for
itself. So measure the book's volatility against its own long-run level and de-risk only above
it, staying fully invested otherwise.

The allocator wraps FACTOR. On data date d it takes the inner targets, forms their weighted
basket (weights renormalized to 1 over the symbols with enough history), and from that one
basket return series computes both numbers it needs:

  short vol = the annualized volatility of the last ``n`` basket returns through d;
  reference = the median of the rolling ``n``-day annualized volatility across the whole ``m``
              basket returns through d (the book's own normal level).

Both come from the same series and the same window length, so the ratio is apples to apples.
Then:

  mode "absolute": de-risk to ``target_vol`` only when short vol > ``ref_mult`` x reference;
                   otherwise the weights are untouched (full exposure).
  mode "relative": scale by min(1, ``ref_mult`` x reference / short vol) — target the book's own
                   normal volatility instead of an absolute number. Asymmetric by construction:
                   at or below its normal level the scale is 1, above it the book shrinks.

Freed weight is cash. No leverage: the scale is never above 1. The basket is built from the
targeted symbols that have at least ``m`` + 1 bars through d, at their inner weights renormalized
to 1; when none has that much history nothing is scaled, which is the "stay invested" default.

``m`` is 378 sessions, about eighteen months, and not the three years that would describe a
"long-run" level better: an allocator's ``lookback`` has to cover every bar its decision reads,
and the lab's smoke market is 473 sessions long, so a three-year reference could not be tested.
Eighteen months still spans 316 rolling three-month readings, enough for a stable median.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies.allocator import LazyPrepared, scale_weight
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import FACTOR, FactorParams

ADDED = date(2026, 10, 6)
TRADING_DAYS = 252

Mode = Literal["absolute", "relative"]
_MODES: tuple[str, ...] = ("absolute", "relative")


@dataclass(frozen=True, slots=True)
class RegimeParams:
    """FACTOR params plus the regime scaling rule. ``target_vol`` is unused in "relative" mode."""

    inner_params: FactorParams
    mode: Mode = "absolute"
    target_vol: Decimal = Decimal("0.12")
    ref_mult: Decimal = Decimal("1")
    n: int = 63  # short volatility window (about three months)
    m: int = 378  # reference window (about eighteen months)

    def __post_init__(self) -> None:
        if self.mode not in _MODES:
            raise ValueError(f"mode must be one of {_MODES}, got {self.mode!r}")
        for name in ("n", "m"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 2:
                raise ValueError(f"{name} must be an int >= 2, got {value!r}")
        if self.m < self.n + 1:
            raise ValueError(f"m must be > n, got m={self.m} n={self.n}")
        for name in ("target_vol", "ref_mult"):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or value <= 0:
                raise ValueError(f"{name} must be a positive Decimal, got {value!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "target_vol": str(self.target_vol), "ref_mult": str(self.ref_mult),
               "n": str(self.n), "m": str(self.m)}
        for k, v in self.inner_params.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _closes(h: History | None, data_date: date) -> np.ndarray | None:
    """``h``'s closes through ``data_date``, or None when there are none."""
    if h is None:
        return None
    end = int(np.searchsorted(h.dates, as_day(data_date), side="right"))
    return None if end == 0 else h.close[:end]


def _basket(history: Mapping[str, History], targets: tuple[Target, ...], data_date: date,
            m: int) -> np.ndarray | None:
    """The weighted basket's ``m`` daily returns through ``data_date``, or None."""
    parts: list[tuple[float, np.ndarray]] = []
    total = 0.0
    for t in sorted(targets, key=lambda t: t.symbol):
        c = _closes(history.get(t.symbol), data_date)
        if c is None or len(c) < m + 1:
            continue
        window = c[len(c) - m - 1 :]
        if not np.all(np.isfinite(window)) or np.any(window <= 0.0):
            return None
        parts.append((float(t.weight), window))
        total += float(t.weight)
    if not parts or total <= 0.0:
        return None
    basket = np.zeros(m, dtype=np.float64)
    for w, window in parts:
        basket = basket + (w / total) * (window[1:] / window[:-1] - 1.0)
    return basket if np.all(np.isfinite(basket)) else None


def _rolling_vol(basket: np.ndarray, n: int) -> np.ndarray:
    """Annualized population volatility of every ``n``-return window of ``basket``."""
    cs = np.concatenate((np.zeros(1), np.cumsum(basket)))
    cs2 = np.concatenate((np.zeros(1), np.cumsum(basket * basket)))
    total = cs[n:] - cs[:-n]
    total2 = cs2[n:] - cs2[:-n]
    var = np.maximum(total2 / n - (total / n) ** 2, 0.0)
    return np.sqrt(var) * math.sqrt(TRADING_DAYS)


def regime_scale(history: Mapping[str, History], targets: tuple[Target, ...], data_date: date,
                 params: RegimeParams) -> Decimal | None:
    """The weight multiplier below 1, or None when the book stays fully invested."""
    basket = _basket(history, targets, data_date, params.m)
    if basket is None:
        return None
    vols = _rolling_vol(basket, params.n)
    short = float(vols[-1])
    reference = float(np.median(vols))
    if not math.isfinite(short) or short <= 0.0 or not math.isfinite(reference) or reference <= 0.0:
        return None
    if params.mode == "absolute":
        if short <= float(params.ref_mult) * reference:
            return None
        scale = float(params.target_vol) / short
    else:
        scale = float(params.ref_mult) * reference / short
    if not math.isfinite(scale) or scale >= 1.0:
        return None
    return Decimal(repr(scale))


def _scaled(targets: tuple[Target, ...], scale: Decimal | None) -> tuple[Target, ...]:
    if scale is None:
        return targets
    out: list[Target] = []
    for t in targets:
        w = scale_weight(t.weight, scale)
        if w is not None:
            out.append(replace(t, weight=w))
    return tuple(out)


class RegimeVolAllocator:
    """FACTOR's targets, de-risked only when the basket's own volatility is above its normal level."""

    id = "M0002"

    def lookback(self, params: RegimeParams) -> int:
        return max(FACTOR.lookback(params.inner_params), params.m + 1)

    def symbols(self, params: RegimeParams) -> tuple[str, ...]:
        return tuple(FACTOR.symbols(params.inner_params))

    def holds(self, params: RegimeParams) -> tuple[str, ...]:
        return tuple(FACTOR.holds(params.inner_params))

    def uses_members(self, params: RegimeParams) -> bool:
        return bool(FACTOR.uses_members(params.inner_params))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: RegimeParams) -> tuple[Target, ...]:
        inner = FACTOR.targets(history, members, data_date, held, params.inner_params)
        return _scaled(inner, regime_scale(history, inner, data_date, params))

    def prepare(self, history: Mapping[str, History]) -> LazyPrepared:
        return LazyPrepared(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: RegimeParams) -> tuple[Target, ...]:
        inner = FACTOR.targets_prepared(prepared.of(FACTOR), members, data_date, held,
                                        params.inner_params)
        return _scaled(inner, regime_scale(prepared.history, inner, data_date, params))


REGIME = RegimeVolAllocator()
MOM20_TREND = FactorParams(rank="momentum", top=20)  # F4-MOM12-N20-TREND's inner params
MOM20_NOTREND = FactorParams(rank="momentum", top=20, trend=None)


def _v(suffix: str, params: RegimeParams, rationale: str, rules=MONTHLY_HOLD) -> Candidate:
    return Candidate(id=f"M0002-{suffix}", family="M0002", rules=rules, allocator=REGIME,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0002",
    name="Momentum, own-vol scaling only in high-vol regimes (asymmetric scale)",
    family="stock-momentum-risk-managed",
    source_kind="variation",
    source_ref="M0001",
    parent_id="M0001",
    hypothesis=(
        "M0001 de-risked all the time (a 10-12% target on a ~22% vol book means about half "
        "exposure always). Scaling down only when the book's own 3-month vol is above its "
        "long-run median, and staying fully invested otherwise, should keep F4's +16% CAGR in "
        "calm spells and still cut the crash spells, landing at DD <= 15% with CAGR above SPY TR."
    ),
    expected_failure=(
        "The drawdown is not made in the high-vol spells the median picks out: F4-MOM12-N20-TREND's "
        "22.2% is built in a slow grind (2000-2002, or the 2008 whipsaw around the trend filter) "
        "where the book's own vol sits near its median, so the gate is shut when it matters and "
        "max DD lands at 18-22%. Or the gate fires so often that the result collapses back onto "
        "M0001's: CAGR near 7% and DD near 13%."
    ),
    candidates=(
        _v("MED-TV12", RegimeParams(MOM20_TREND, "absolute", Decimal("0.12"), Decimal("1")),
           "Full exposure below its median vol; above it, de-risk to a 12% target"),
        _v("MED-TV14", RegimeParams(MOM20_TREND, "absolute", Decimal("0.14"), Decimal("1")),
           "Same gate, 14% target: M0001's trade curve says DD ~15% at CAGR ~SPY"),
        _v("MED-TV12-H", RegimeParams(MOM20_TREND, "absolute", Decimal("0.12"), Decimal("1.25")),
           "Gate only at 1.25x its median vol: de-risk in real spikes, not ordinary ones"),
        _v("REL", RegimeParams(MOM20_TREND, "relative", Decimal("0.12"), Decimal("1")),
           "Target its own normal vol: scale = min(1, median vol / current vol)"),
        _v("REL-85", RegimeParams(MOM20_TREND, "relative", Decimal("0.12"), Decimal("0.85")),
           "Target 85% of its normal vol: the same shape, a touch more cautious"),
        _v("MED-TV12-NOTREND", RegimeParams(MOM20_NOTREND, "absolute", Decimal("0.12"), Decimal("1")),
           "No SPY trend filter: the regime gate alone as the crash guard"),
    ),
    seen_keys=(
        "concept:momentum-asymmetric-vol-regime-scaling",
        "concept:own-vol-relative-to-its-own-median",
    ),
)
