"""M0342 — Hold the index members a fitted model expects to be the least lottery-like next quarter.

Source: Boyer, Mitton & Vorkink (2010), "Expected idiosyncratic skewness", Review of Financial
Studies 23(1), 169-202. Idea: investors overpay for stocks with a chance of a huge payoff, so the
stocks whose *expected* idiosyncratic skewness is highest go on to trail and the lowest-expected
ones lead. The paper's point is that realized past skewness is a noisy guide to future skewness,
so it fits a cross-sectional forecast and ranks on that. Published 2010, so the dev window (to
2015-10-16) sees mostly the years before the crowd traded it.

The frame is the lab's usual book (M0091's): point-in-time members, the $5 price and 20M-dollar
volume screen, 20 equal slots, monthly, fractional shares at Gotrade's real fees, and the SPY
200-day switch on every arm but one. Only the ranking key differs.

The forecast, pure and refit every month from bars dated <= d. For each of the last 8 monthly
snapshots j (63, 84, ... 210 bars back) and each screened member, the features are read over the
63 bars ending at j and the target is the skewness of the market-model residual over the 63 bars
after j (so no target window reaches past d). Features: residual skewness, residual volatility,
the 63-bar return, and log average dollar volume (a turnover proxy; shares outstanding are not
read). Residual = daily return minus beta times SPY's, beta fitted on the same window. Each
snapshot's features are standardized across names, one pooled least-squares fit predicts the
target, and the book scores every name on its features over the 63 bars ending at d. Names with
any missing or non-positive bar in the 273-bar span are not scored, identically in every arm.

Arms (six, the lab's cap), all on one scored pool:
LOW holds the 20 lowest forecasts, HIGH the 20 highest (the mirror: same costs, opposite opinion),
PAST holds the 20 lowest *realized* residual skewness (the forecast's reason to exist: does the
fitted model add to the plain number?), R1 and R2 hash-rank the same pool (chance spreads behind
the switch), and R1-NOSW is R1's order with no switch, the always-invested no-opinion arm that
prices the habit of the switch against R1.
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

ADDED = date(2026, 10, 24)

MODES = ("model-low", "model-high", "past-low", "blind")
WIN = 63  # bars in a feature window and in a target window
MOM = 63
OFFSETS = tuple(WIN + 21 * k for k in range(8))  # snapshots, in bars before d
SPAN = max(OFFSETS) + MOM  # bars of history a name needs behind d (273)
MARKET = "SPY"
MIN_FIT = 40  # fewest (name, snapshot) pairs worth a fit

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class SkewParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "model-low"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "win": str(WIN), "snapshots": str(len(OFFSETS))}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> SkewParams:
    if not isinstance(params, SkewParams):
        raise TypeError(f"params must be SkewParams, got {type(params).__name__}")
    return params


def _resid_stats(r: np.ndarray, m: np.ndarray) -> tuple[float, float] | None:
    """(skewness, std) of the market-model residual of ``r`` on ``m`` over the window."""
    vm = float(np.var(m))
    if not vm > 0.0:
        return None
    beta = float(np.mean((r - r.mean()) * (m - m.mean())) / vm)
    e = r - beta * m
    e = e - e.mean()
    s = float(np.sqrt(np.mean(e * e)))
    if not s > 0.0:
        return None
    return float(np.mean(e ** 3) / s ** 3), s


def _spy_returns(spy: History, h: History, i: int) -> np.ndarray | None:
    """SPY's daily returns on the dates of the SPAN+1 bars of ``h`` ending at ``i``."""
    d = h.dates[i - SPAN : i + 1]
    k = np.searchsorted(spy.dates, d)
    if k.max(initial=0) >= len(spy.dates) or not np.array_equal(spy.dates[k], d):
        return None
    c = spy.close[k]
    if not (np.all(np.isfinite(c)) and np.all(c > 0.0)):
        return None
    return c[1:] / c[:-1] - 1.0


def _features(r: np.ndarray, m: np.ndarray, c: np.ndarray, dv: np.ndarray, j: int
              ) -> tuple[float, float, float, float] | None:
    """Features at position ``j`` of the span: residual skew and vol over the WIN returns ending
    at j, the MOM-bar return, log mean dollar volume. ``r``/``m`` index returns, ``c``/``dv`` bars."""
    st = _resid_stats(r[j - WIN : j], m[j - WIN : j])
    if st is None:
        return None
    mom = float(c[j] / c[j - MOM] - 1.0)
    ldv = float(np.log(max(float(np.mean(dv[j - WIN + 1 : j + 1])), 1.0)))
    return st[0], st[1], float(mom), ldv


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> tuple[dict[str, float], dict[str, float]]:
    """(expected skewness, realized skewness) per scorable name at ``data_date``."""
    spy = history.get(MARKET)
    if spy is None:
        return {}, {}
    xs: list[np.ndarray] = []
    ys: list[float] = []
    snap_ids: list[int] = []
    now: dict[str, tuple[float, float, float, float]] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < SPAN:
            continue
        c = h.close[i - SPAN : i + 1]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0)):
            continue
        m = _spy_returns(spy, h, i)
        if m is None:
            continue
        r = c[1:] / c[:-1] - 1.0
        dv = c * h.volume[i - SPAN : i + 1]
        if not np.all(np.isfinite(dv)):
            continue
        n = len(r)  # SPAN returns; return t covers bar t -> t+1, bar index j sits at position j
        f_now = _features(r, m, c, dv, n)
        if f_now is None:
            continue
        now[s] = f_now
        for k, off in enumerate(OFFSETS):
            j = n - off
            f = _features(r, m, c, dv, j)
            tgt = _resid_stats(r[j : j + WIN], m[j : j + WIN])
            if f is None or tgt is None:
                continue
            xs.append(np.array(f))
            ys.append(tgt[0])
            snap_ids.append(k)
    if len(now) < 8 or len(ys) < MIN_FIT:
        return {}, {}
    x = np.vstack(xs)
    y = np.array(ys)
    sid = np.array(snap_ids)
    for k in set(snap_ids):  # standardize within each snapshot, across names
        mk = sid == k
        mu, sd = x[mk].mean(axis=0), x[mk].std(axis=0)
        x[mk] = (x[mk] - mu) / np.where(sd > 0.0, sd, 1.0)
    design = np.column_stack([np.ones(len(y)), x])
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    names = sorted(now)
    fm = np.array([now[s] for s in names])
    mu, sd = fm.mean(axis=0), fm.std(axis=0)
    fz = (fm - mu) / np.where(sd > 0.0, sd, 1.0)
    pred = np.column_stack([np.ones(len(names)), fz]) @ coef
    return ({s: float(p) for s, p in zip(names, pred, strict=True)},
            {s: now[s][0] for s in names})


def choose(rows: list[FactorRow], expected: dict[str, float], realized: dict[str, float],
           params: SkewParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in expected]
    if params.mode == "model-low":
        key = {r.symbol: expected[r.symbol] for r in pool}
    elif params.mode == "model-high":
        key = {r.symbol: -expected[r.symbol] for r in pool}
    elif params.mode == "past-low":
        key = {r.symbol: realized[r.symbol] for r in pool}
    else:
        key = {r.symbol: float(draw(params.seed, r.symbol)) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: params.inner.top]


@dataclass
class SkewPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, tuple[dict[str, float], dict[str, float]]] = field(default_factory=dict, repr=False)


class ExpectedSkewAllocator:
    """The lab's index-member book ranked on a fitted forecast of next-quarter residual skewness."""

    id = "M0342"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), SPAN + 1)

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

    def _run(self, prepared: SkewPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: SkewParams) -> tuple[Target, ...]:
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

    def prepare(self, history: Mapping[str, History]) -> SkewPrepared:
        return SkewPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SkewPrepared):
            raise TypeError(f"prepared must be SkewPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


EXPSKEW = ExpectedSkewAllocator()


def _v(suffix: str, params: SkewParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0342-{suffix}", family="M0342",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=EXPSKEW, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0342",
    name="Expected idiosyncratic skewness: buy the stocks a cross-sectional model says are least lottery-like",
    family="stock-expected-skewness",
    source_kind="paper",
    source_ref=("Boyer, Mitton & Vorkink (2010), Expected idiosyncratic skewness, Review of "
                "Financial Studies 23(1), 169-202; QuantConnect strategy library 'expected "
                "idiosyncratic skewness'"),
    parent_id=None,
    hypothesis=(
        "Investors overpay for stocks with a small chance of a huge payoff, so the stocks whose "
        "expected idiosyncratic skewness is highest go on to trail and the lowest-expected ones "
        "lead (Boyer, Mitton & Vorkink 2010, a decile spread near 1% a month on 1988-2005; "
        "published 2010, so a dev edge is the pre-crowd kind). Past skewness is a noisy guide, "
        "so the book ranks on a forecast: every month, a pooled least-squares fit over the last "
        "8 monthly snapshots predicts the next 63 bars' market-model residual skewness from "
        "residual skewness, residual volatility, the 63-bar return and log dollar volume (a "
        "turnover proxy), then holds the 20 lowest forecasts equal weight among F4-screened "
        "index members, monthly, fractional shares at real fees, behind SPY's 200-day switch. "
        "Arms: LOW (the idea), HIGH (the mirror, same costs), PAST (the 20 lowest realized "
        "residual skewness, no model: does the forecast add anything), R1 and R2 (hash order on "
        "the same scored pool, same switch), R1-NOSW (R1's order, no switch: the no-opinion "
        "always-invested arm, so the switch's habit is priced apart from the opinion). "
        "Predictions, written now: LOW beats HIGH on funded CAGR; LOW beats the better of R1 and "
        "R2 by less than the chance spread between R1 and R2 plus 2 points a year; LOW's lead "
        "over PAST is under 2 points a year, because the model's forecast is mostly volatility "
        "and past skewness; LOW trails SPY in 2009-2015; LOW's worst fall is under 25% behind "
        "the switch; R1-NOSW falls over 40% so the switch, not the ranking, carries the fall."
    ),
    expected_failure=(
        "In large caps the forecast is mostly low residual volatility in disguise (volatility "
        "is the strongest predictor of future skew), so LOW is a calm-names book like M0091's: "
        "a smoother ride that trails SPY in the 2009-2015 growth run, and its edge over random "
        "order is the equal-weight book's shape plus a volatility tilt (the lab's pattern in "
        "M0184 and M0333). The fitted coefficients may flip sign between snapshots, making the "
        "ranking noisy; 63-bar skewness is itself noisy. A published anomaly fades, and this one "
        "was circulating from 2007. Two hash draws are a thin chance spread. Names without 273 "
        "clean bars are never scored, which thins the pool in the early years."
    ),
    candidates=(
        _v("LOW", SkewParams(N20, "model-low"),
           "The 20 lowest forecast skewness, behind the SPY switch: the idea"),
        _v("HIGH", SkewParams(N20, "model-high"),
           "The 20 highest forecast skewness, behind the switch: the mirror"),
        _v("PAST", SkewParams(N20, "past-low"),
           "The 20 lowest realized skewness, no model, behind the switch: does the forecast add"),
        _v("R1", SkewParams(N20, "blind", 342),
           "Control: hash-ranked scored pool, seed 342, behind the switch"),
        _v("R2", SkewParams(N20, "blind", 343),
           "Control: hash-ranked scored pool, seed 343, behind the switch"),
        _v("R1-NOSW", SkewParams(NOSW, "blind", 342),
           "No-opinion always-invested arm: R1's order with no switch, prices the switch's habit"),
    ),
    seen_keys=(
        "concept:expected-idiosyncratic-skewness",
        "doi:10.1093/rfs/hhp041",
    ),
)
