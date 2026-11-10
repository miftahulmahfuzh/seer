"""M0547 — Trend persistence of a stock's own daily returns, ranked by the Hurst exponent.

Source: Auer 2018, J Econ Finance 42:66-88 ("Hurst exponent and the cross-section of stock
returns"), and the 2023 follow-up (Ann Finance, doi 10.1007/s10436-023-00428-z). The idea is
published, so a dev edge can only be from before the crowd traded it, and 2009-2015 is the first
filter.

The Hurst exponent H measures memory in a return series: H > 0.5 means a rise tends to be
followed by more rise (a trend), H < 0.5 means a rise tends to be followed by a fall. Here it is
the classical rescaled-range estimate on the trailing 252 daily returns: for block sizes from 9
to 84 sessions, the average of (range of the block's cumulated, demeaned returns) / (the block's
standard deviation), then the slope of log(R/S) on log(block size). No bias correction: only the
cross-sectional order matters.

Arms, all on ``MONTHLY_HOLD_FRAC_GOTRADE``, 20 equal slots, fractional shares at real fees:

    HIGH       the 20 highest H, behind the SPY-200 switch
    LOW        the 20 lowest H, same gate (the mirror: if HIGH works and LOW does not, or the
               reverse, the sort is not noise)
    HN-HIGH    the 20 highest H after H's rank is stripped of its fit on the 12-1 return rank and
               the volatility rank (cross-sectionally, each rebalance)
    HN-LOW     the 20 lowest of the same neutralised score
    HIGH-OPEN  the HIGH book with no switch, always invested: the gate premium, priced
    RAND-A     no opinion: a date-and-seed hash draw of 20 on the gated chassis

Six is the variant cap. RAND-B..E (the rest of the five-draw error bar) and a random always-on
book are pre-registered as an amendment before ``lab run --amend``. Draws and the open arm may
repeat earlier recorded books: those are book twins, not new books.

Whether H is only 12-1 momentum or volatility in disguise is reported after the run from the
allocator's own score function (rank correlation at every rebalance); it is not a pre-registered
pass condition, because HN-HIGH / HN-LOW are the arms that test it.

Pure: reads bars dated at or before the data date only.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import ResidPrepared, ReturnGrid, build_grid
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import as_day
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    factor_weights,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 10)
SIGNALS = ("high", "low", "hn_high", "hn_low", "rand")
BLOCKS = (9, 14, 18, 28, 36, 42, 63, 84)  # all divide 252 exactly
MIN_FRAC = 0.9  # share of the window's returns that must be present


def hurst_rs(window: np.ndarray) -> np.ndarray:
    """Rescaled-range H per row of ``window`` (names x n), n a multiple of every block size.

    NaN where the row is too gappy or degenerate. A missing return counts as zero once at least
    ``MIN_FRAC`` of the row is present.
    """
    n = window.shape[1]
    finite = np.isfinite(window)
    ok = finite.sum(axis=1) >= MIN_FRAC * n
    x = np.where(finite, window, 0.0)
    logs, logn = [], []
    for s in BLOCKS:
        k = n // s
        b = x[:, n - k * s :].reshape(x.shape[0], k, s)
        dev = b - b.mean(axis=2, keepdims=True)
        cum = np.cumsum(dev, axis=2)
        rng = cum.max(axis=2) - cum.min(axis=2)
        sd = b.std(axis=2)
        with np.errstate(divide="ignore", invalid="ignore"):
            rs = np.where(sd > 0.0, rng / np.where(sd > 0.0, sd, 1.0), np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            logs.append(np.log(np.nanmean(np.where(rs > 0.0, rs, np.nan), axis=1)))
        logn.append(np.log(float(s)))
    y = np.stack(logs, axis=1)  # names x blocks
    xs = np.asarray(logn)
    good = np.isfinite(y).all(axis=1) & ok
    xm = xs.mean()
    sxx = float(((xs - xm) ** 2).sum())
    slope = np.where(good, ((y - np.nanmean(y, axis=1, keepdims=True)) * (xs - xm)).sum(axis=1) / sxx,
                     np.nan) if y.size else np.full(x.shape[0], np.nan)
    return np.where(good, slope, np.nan)


def _ranks(v: np.ndarray) -> np.ndarray:
    """Average-free ordinal ranks scaled to [-0.5, 0.5]; stable on ties."""
    order = np.argsort(v, kind="stable")
    r = np.empty(len(v), dtype=np.float64)
    r[order] = np.arange(len(v), dtype=np.float64)
    return r / max(len(v) - 1, 1) - 0.5


def neutralise(h: np.ndarray, mom: np.ndarray, vol: np.ndarray) -> np.ndarray:
    """Residual of H's rank on the 12-1 return rank and the volatility rank (OLS with intercept)."""
    if len(h) < 8:
        return np.full(len(h), np.nan)
    a = np.column_stack([np.ones(len(h)), _ranks(mom), _ranks(vol)])
    y = _ranks(h)
    coef, *_ = np.linalg.lstsq(a, y, rcond=None)
    return y - a @ coef


def pick(scores: Mapping[str, float], high: bool, k: int) -> list[str]:
    """The ``k`` symbols with the highest (``high``) or lowest score; ties break on the symbol."""
    sign = -1.0 if high else 1.0
    return sorted(scores, key=lambda s: (sign * scores[s], s))[:k]


@dataclass(frozen=True, slots=True)
class HurstParams:
    """``inner`` is F4's screen, gate and book size; ``signal`` is the sort or a hash draw."""

    inner: FactorParams
    signal: str = "high"
    seed: int = 0
    window: int = 252
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.signal not in SIGNALS:
            raise ValueError(f"signal must be one of {SIGNALS}, got {self.signal!r}")
        for name in ("seed", "window"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.window != 252:
            raise ValueError("window must be 252 (the block sizes divide it)")

    def as_dict(self) -> dict[str, str]:
        out = {"signal": self.signal, "seed": str(self.seed), "window": str(self.window),
               "market": self.market}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> HurstParams:
    if not isinstance(params, HurstParams):
        raise TypeError(f"params must be HurstParams, got {type(params).__name__}")
    return params


def _draw(symbol: str, data_date: date, seed: int) -> str:
    return hashlib.sha256(f"M0547|{seed}|{data_date.isoformat()}|{symbol}".encode()).hexdigest()


def hurst_scores(grid: ReturnGrid, symbols: Sequence[str], data_date: date,
                 window: int) -> dict[str, float]:
    """H per symbol on ``data_date`` from its last ``window`` grid returns; absent if too gappy."""
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day or j - window + 1 < 0:
        return {}
    names = [s for s in symbols if s in grid.row]
    if not names:
        return {}
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)
    h = hurst_rs(grid.rets[idx, j - window + 1 : j + 1])
    return {n: float(v) for n, v in zip(names, h, strict=True) if np.isfinite(v)}


def targets_from(rows: Sequence[FactorRow], grid: ReturnGrid | None, data_date: date,
                 p: HurstParams) -> tuple[Target, ...]:
    rows = [r for r in rows if r.symbol not in EXCLUDED]
    if not rows:
        return ()
    by_symbol = {r.symbol: r for r in rows}
    if p.signal == "rand":
        names = sorted(by_symbol, key=lambda s: _draw(s, data_date, p.seed))[: p.inner.top]
    else:
        if grid is None:
            return ()
        h = hurst_scores(grid, list(by_symbol), data_date, p.window)
        if p.signal in ("hn_high", "hn_low"):
            syms = sorted(h)
            res = neutralise(np.asarray([h[s] for s in syms]),
                             np.asarray([by_symbol[s].momentum for s in syms]),
                             np.asarray([by_symbol[s].vol for s in syms]))
            h = {s: float(v) for s, v in zip(syms, res, strict=True) if np.isfinite(v)}
        names = pick(h, p.signal.endswith("high"), p.inner.top)
    chosen = [by_symbol[s] for s in names]
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, p.inner), strict=True):
        if weight is None:
            continue
        t = target_from_close(row.symbol, row.close, weight)
        if t is not None:
            out.append(t)
    return tuple(out)


class HurstAllocator:
    """The 20 screened names with the highest or lowest Hurst exponent, or a seeded draw."""

    id = "M0547"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(factor_lookback(p.inner), p.window + 2)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, Any], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return targets_from(rows, build_grid(history, p.market), data_date, p)

    def prepare(self, history: Mapping[str, Any]) -> ResidPrepared:
        return ResidPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return targets_from(rows, prepared.grid(p.market), data_date, p)


HURST_ALLOC = HurstAllocator()

GATED = FactorParams(rank="momentum", top=20, trend=("SPY", 200))
OPEN = FactorParams(rank="momentum", top=20, trend=None)


def _v(suffix: str, params: HurstParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0547-{suffix}", family="M0547", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=HURST_ALLOC, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0547",
    name="Trend persistence of a stock's own daily returns: rank by the Hurst exponent",
    family="stock-hurst-persistence",
    source_kind="paper",
    source_ref="Auer 2018, J Econ Finance 42:66-88; doi 10.1007/s10436-023-00428-z",
    hypothesis=(
        "Published 2018 and 2023, so the dev window is before the crowd. Long memory in a stock's "
        "own daily returns (rescaled-range Hurst exponent on the trailing 252 sessions) predicts "
        "next month: high-H names keep trending, low-H names mean-revert. Book: each month, among "
        "liquid index members behind the SPY-200 switch, hold the 20 highest H (HIGH) or the 20 "
        "lowest (LOW), equal slots, fractional shares at Gotrade's real fees on the owner's "
        "monthly deposits. HN-HIGH and HN-LOW sort on H after its rank is stripped of its fit on "
        "the 12-1 return rank and the volatility rank, to test that H is not momentum or risk in "
        "disguise. HIGH-OPEN is HIGH with no switch, always invested, to price the gate. RAND-A "
        "is a date-and-seed hash draw on the same gate; RAND-B..E and a random always-on book "
        "follow as a pre-registered amendment (the variant cap is six) and are book twins of "
        "earlier random draws where they repeat one. Success: HIGH or LOW beats total-return SPY "
        "on the deposits, worst fall under 25%, profit factor >= 1.3, a positive edge in "
        "2009-2015, funded return above ALL five draws (p = 1/6 by chance alone), and the "
        "neutralised arm keeps at least half the edge. Sort direction is not assumed: whichever "
        "of HIGH or LOW leads is reported, the other is its mirror."
    ),
    expected_failure=(
        "Daily-return persistence is weak and noisy at 252 sessions: R/S has a large small-sample "
        "bias and a standard error that swamps the cross-sectional spread of H among large caps, "
        "so HIGH and LOW may be indistinguishable from the random draws. If H has an edge it is "
        "probably 12-1 momentum or low volatility under another name (M0432's autocorrelation "
        "filter and M0480's rank persistence both added nothing over plain momentum), and "
        "HN-HIGH / HN-LOW will lose it. 16 turns a year on $28 slots at real fees, the 2008 fall "
        "behind a late gate, and a 2009-2015 era with no bear market all work against it."
    ),
    candidates=(
        _v("HIGH", HurstParams(GATED, "high"), "20 highest Hurst exponents, gated (trend persists)"),
        _v("LOW", HurstParams(GATED, "low"), "20 lowest Hurst exponents, gated (mirror: reversion)"),
        _v("HN-HIGH", HurstParams(GATED, "hn_high"),
           "Highest H after stripping momentum and volatility rank, gated"),
        _v("HN-LOW", HurstParams(GATED, "hn_low"),
           "Lowest H after stripping momentum and volatility rank, gated"),
        _v("HIGH-OPEN", HurstParams(OPEN, "high"),
           "HIGH with no switch, always invested: prices the gate"),
        _v("RAND-A", HurstParams(GATED, "rand", seed=1),
           "No opinion: hash draw seed 1, same gate and monthly churn"),
    ),
    seen_keys=("concept:hurst-exponent-persistence", "concept:random-draw-error-bar"),
)
