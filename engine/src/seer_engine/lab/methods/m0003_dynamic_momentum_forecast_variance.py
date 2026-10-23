"""M0003 — Dynamic momentum (Daniel-Moskowitz): weight by forecast mean over forecast variance.

Source: Daniel & Moskowitz (2016), "Momentum crashes", Journal of Financial Economics 122(2).
Published 2016, after the dev window closes, so an edge here is one the crowd had not yet traded.

Idea: the paper's optimal momentum weight is (forecast mean return) / (forecast variance). The
forecast variance is the book's own recent variance. The forecast mean is the part M0001 lacks:
it is low after a bear market, when the losers rebound hard and momentum crashes, and ordinary
otherwise. M0001 scaled by volatility alone (target / sigma) and held the book near half
exposure all the time; M0002 braked only in high-vol spells but its falls came in calm markets.
This one divides a state-dependent mean by variance, so it is meant to hold full size in calm
bull markets, shrink fast when the book is volatile, and shrink further in a bear state.

The allocator wraps FACTOR. On data date d it takes the inner targets and forms their weighted
basket (weights renormalized to 1 over symbols with at least ``n`` + 1 bars through d). Then:

  sigma  = annualized stdev of the basket's last ``n`` daily returns through d;
  bear   = SPY's close on d is below its close ``bear_n`` bars earlier (a negative trailing
           18-month market return; the paper uses 24 months, shortened because an allocator's
           lookback must fit the lab's 473-session smoke market, as in M0002);
  mean   = 1 when not bear, ``bear_mult`` when bear (the low forecast mean, as a fraction of normal);
  scale  = min(1, mean x (sigma_ref / sigma)^2).

Variance-scaling is quadratic in sigma where M0001's vol-scaling is linear: that is what
mean / variance means, and it de-risks harder in the spells that matter. ``sigma_ref`` is the
volatility at which a normal-state book is full size, 22%, about the unscaled book's usual level.
Freed weight is cash, no leverage. When SPY or the basket lacks the history the state is unknown
and the book stays fully invested (the M0002 default).

Six arms, 2 x 3: the SPY 200-day trend filter on or off, against three treatments that share one
book and one fee schedule. DM is the opinion (state-dependent mean over variance); VAR keeps
only the variance term (``bear_mult`` = 1); CTRL has no opinion at all and never scales. DM vs
VAR prices the mean forecast; VAR vs CTRL prices the variance habit; and CTRL is the
always-invested book the lab needs to tell a dead rule from a badly dressed one.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import LazyPrepared, scale_weight
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import FACTOR, FactorParams

ADDED = date(2026, 10, 23)
TRADING_DAYS = 252
MARKET = "SPY"


@dataclass(frozen=True, slots=True)
class DMParams:
    """FACTOR params plus the mean / variance rule. ``sigma_ref`` None means never scale (control)."""

    inner_params: FactorParams
    sigma_ref: Decimal | None = Decimal("0.22")
    bear_mult: Decimal = Decimal("0.25")
    n: int = 126  # variance window (about six months, as in the paper)
    bear_n: int = 378  # bear-state window (about eighteen months)

    def __post_init__(self) -> None:
        if self.sigma_ref is not None and (not isinstance(self.sigma_ref, Decimal) or self.sigma_ref <= 0):
            raise ValueError(f"sigma_ref must be a positive Decimal or None, got {self.sigma_ref!r}")
        if not isinstance(self.bear_mult, Decimal) or not (0 < self.bear_mult <= 1):
            raise ValueError(f"bear_mult must be a Decimal in (0, 1], got {self.bear_mult!r}")
        for name in ("n", "bear_n"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 2:
                raise ValueError(f"{name} must be an int >= 2, got {value!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"sigma_ref": "none" if self.sigma_ref is None else str(self.sigma_ref),
               "bear_mult": str(self.bear_mult), "n": str(self.n), "bear_n": str(self.bear_n)}
        for k, v in self.inner_params.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _closes(h: History | None, data_date: date) -> np.ndarray | None:
    if h is None:
        return None
    end = int(np.searchsorted(h.dates, as_day(data_date), side="right"))
    return None if end == 0 else h.close[:end]


def basket_sigma(history: Mapping[str, History], targets: tuple[Target, ...], data_date: date,
                 n: int) -> float | None:
    """Annualized stdev of the weight-normalized basket's last ``n`` returns, or None."""
    parts: list[tuple[float, np.ndarray]] = []
    total = 0.0
    for t in sorted(targets, key=lambda t: t.symbol):
        c = _closes(history.get(t.symbol), data_date)
        if c is None or len(c) < n + 1:
            continue
        window = c[len(c) - n - 1 :]
        if not np.all(np.isfinite(window)) or np.any(window <= 0.0):
            continue
        parts.append((float(t.weight), window[1:] / window[:-1] - 1.0))
        total += float(t.weight)
    if not parts or total <= 0.0:
        return None
    basket = np.zeros(n, dtype=np.float64)
    for w, r in parts:
        basket = basket + (w / total) * r
    mean = 0.0
    for x in basket:
        mean += float(x)
    mean /= n
    var = 0.0
    for x in basket:
        var += (float(x) - mean) ** 2
    sd = math.sqrt(var / n) * math.sqrt(TRADING_DAYS)
    return sd if math.isfinite(sd) and sd > 0.0 else None


def is_bear(history: Mapping[str, History], data_date: date, bear_n: int) -> bool:
    """True when SPY closed below its close ``bear_n`` bars earlier; False when unknown."""
    c = _closes(history.get(MARKET), data_date)
    if c is None or len(c) < bear_n + 1:
        return False
    return bool(np.isfinite(c[-1]) and np.isfinite(c[-1 - bear_n]) and c[-1] < c[-1 - bear_n])


def dm_scale(history: Mapping[str, History], targets: tuple[Target, ...], data_date: date,
             params: DMParams) -> Decimal | None:
    """min(1, mean x (sigma_ref / sigma)^2), or None for "do not scale"."""
    if params.sigma_ref is None:
        return None
    sigma = basket_sigma(history, targets, data_date, params.n)
    if sigma is None:
        return None
    mean = float(params.bear_mult) if is_bear(history, data_date, params.bear_n) else 1.0
    scale = mean * (float(params.sigma_ref) / sigma) ** 2
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


class DynamicMomentumAllocator:
    """FACTOR's targets scaled by state-dependent forecast mean over the book's own variance."""

    id = "M0003"

    def lookback(self, params: DMParams) -> int:
        return max(FACTOR.lookback(params.inner_params), params.n + 1, params.bear_n + 1)

    def symbols(self, params: DMParams) -> tuple[str, ...]:
        base = tuple(FACTOR.symbols(params.inner_params))
        return base if MARKET in base else base + (MARKET,)

    def holds(self, params: DMParams) -> tuple[str, ...]:
        return tuple(FACTOR.holds(params.inner_params))

    def uses_members(self, params: DMParams) -> bool:
        return bool(FACTOR.uses_members(params.inner_params))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: DMParams) -> tuple[Target, ...]:
        inner = FACTOR.targets(history, members, data_date, held, params.inner_params)
        return _scaled(inner, dm_scale(history, inner, data_date, params))

    def prepare(self, history: Mapping[str, History]) -> LazyPrepared:
        return LazyPrepared(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: DMParams) -> tuple[Target, ...]:
        inner = FACTOR.targets_prepared(prepared.of(FACTOR), members, data_date, held, params.inner_params)
        return _scaled(inner, dm_scale(prepared.history, inner, data_date, params))


DM = DynamicMomentumAllocator()
MOM20_TREND = FactorParams(rank="momentum", top=20)  # F4-MOM12-N20-TREND's inner params
MOM20_FREE = FactorParams(rank="momentum", top=20, trend=None)
SIGMA_REF = Decimal("0.22")


def _v(suffix: str, params: DMParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0003-{suffix}", family="M0003", rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=DM,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0003",
    name="Dynamic momentum: forecast mean over forecast variance",
    family="stock-momentum-risk-managed",
    source_kind="paper",
    source_ref="Daniel & Moskowitz (2016), Momentum crashes, JFE 122(2)",
    hypothesis=(
        "Momentum crashes in bear-market rebounds when volatility is high. Weighting the top-20 "
        "12-1 momentum book by a state-dependent forecast mean (a quarter of normal after a "
        "negative 18-month SPY return) over the book's own six-month variance, capped at full "
        "size, de-risks only in the dangerous state and keeps full exposure elsewhere. The bar "
        "is to beat total-return SPY with max DD <= 15% (the lab screen), PF >= 1.3 and >= 100 "
        "trades, at real Gotrade fees in fractional shares, and to stay ahead of SPY in 2009-2015. "
        "Published 2016, so the dev window should show it before the crowd traded it."
    ),
    expected_failure=(
        "The SPY 200-day trend filter already puts the book in cash in bear rebounds, so the "
        "mean term adds nothing over CTRL-TREND, and the variance term costs return in calm "
        "bulls like M0001 did. Without the trend filter the 18-month bear flag reacts too late "
        "to the fast crashes (M0002 found falls in calm markets, before volatility rises), "
        "leaving max DD above 15%. Published anomalies also fade after 2015."
    ),
    candidates=(
        _v("DM-TREND", DMParams(MOM20_TREND, SIGMA_REF, Decimal("0.25")),
           "Trend filter on, mean x (22% / sigma)^2 with a quarter mean in bear state"),
        _v("VAR-TREND", DMParams(MOM20_TREND, SIGMA_REF, Decimal("1")),
           "Trend filter on, variance term only: prices the mean forecast against DM-TREND"),
        _v("CTRL-TREND", DMParams(MOM20_TREND, None),
           "Trend filter on, never scales: the always-invested book with no opinion"),
        _v("DM-FREE", DMParams(MOM20_FREE, SIGMA_REF, Decimal("0.25")),
           "No trend filter, DM state as the only crash guard (the paper's own setup)"),
        _v("VAR-FREE", DMParams(MOM20_FREE, SIGMA_REF, Decimal("1")),
           "No trend filter, variance term only"),
        _v("CTRL-FREE", DMParams(MOM20_FREE, None),
           "No trend filter, never scales: raw top-20 momentum at real fees"),
    ),
    seen_keys=(
        "concept:momentum-dynamic-forecast-mean-over-variance",
        "url:https://doi.org/10.1016/j.jfineco.2015.12.002",
    ),
)
