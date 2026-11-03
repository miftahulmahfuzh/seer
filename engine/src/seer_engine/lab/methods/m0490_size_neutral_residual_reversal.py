"""M0490 — Short-term residual reversal with the market and company size taken out.

Source: Blitz, Huij, Lansdorp & Verbeek (2013), Short-term residual reversal, Journal of Financial
and Quantitative Analysis / Journal of Financial Markets 16(3) (the sera batch recorded the first
name; the paper is the same). Published 2013, so the dev window (to 2015) is mostly before the crowd.
Idea: plain one-month reversal buys the month's losers, and losers are small, jumpy, high-beta
names, so it is partly a bet on factors. Strip the market's share (a daily market-model fit on the
252 sessions before the window, as M0158 does) and then the size share, and rank what is left.

What is different from M0158 and M0028: M0158 divides the market residual by the stock's own swing;
M0028 filters by calm and trend. Here the score is the plain market residual with a *size
regression* on top: across the screened names that day, the residual is regressed on log 20-day
dollar volume and the leftover is ranked. Assumption (no human to ask): company size is a proxy,
dollar volume, because ``market_value`` covers only ~60% of dev member-days and would need a
market-aware allocator; dollar volume is on every screened row. Value exposure (the paper's third
factor) needs fundamentals the store does not have and is left out; say so in the verdict.

Arms, all on ``MONTHLY_HOLD_FRAC_GOTRADE`` (fractional shares, real fees), 20 equal slots, F4's
liquidity and membership screen:

    RESID      20 most negative size-neutral residuals, behind the SPY-200 gate (the idea)
    RAW        20 most negative plain 21-session returns, same gate (does stripping help?)
    RESID-REV  the 20 most positive size-neutral residuals: the mirror, same gate
    CTRL-GATE  the 20 most liquid screened names, no opinion, same gate and monthly churn
    CTRL-ALWAYS the same names with no gate: always invested, nothing stepping aside
    RESID-OPEN RESID with no gate: the 2x2 pair that prices the gate's habit

RESID versus RESID-REV proves the signal; CTRL-ALWAYS prices what acting costs (insight 523).
Pure: reads calendar columns at or before the data date only.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
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
from seer_engine.strategies.base import History, as_day
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

ADDED = date(2026, 11, 3)
MIN_FRAC = 0.8  # a window needs this share of usable daily returns before a name is scored
SIGNALS = ("resid", "raw", "ctrl")


@dataclass(frozen=True, slots=True)
class SnrParams:
    """``inner`` is F4's screen, gate and book size; ``signal`` picks what is ranked.

    ``side`` = -1 holds the losers (the reversal), +1 holds the winners (the mirror).
    """

    inner: FactorParams
    signal: str = "resid"
    side: int = -1
    rev_n: int = 21
    beta_n: int = 252
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.signal not in SIGNALS:
            raise ValueError(f"signal must be one of {SIGNALS}, got {self.signal!r}")
        if self.side not in (-1, 1):
            raise ValueError(f"side must be -1 or 1, got {self.side!r}")
        for name in ("rev_n", "beta_n"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.rev_n < 5 or self.beta_n < 60:
            raise ValueError("rev_n must be >= 5 and beta_n >= 60")

    def as_dict(self) -> dict[str, str]:
        out = {"signal": self.signal, "side": str(self.side), "rev_n": str(self.rev_n),
               "beta_n": str(self.beta_n), "market": self.market}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> SnrParams:
    if not isinstance(params, SnrParams):
        raise TypeError(f"params must be SnrParams, got {type(params).__name__}")
    return params


def snr_lookback(p: SnrParams) -> int:
    return max(factor_lookback(p.inner), p.beta_n + p.rev_n + 2)


def formation_returns(grid: ReturnGrid, symbols: list[str], data_date: date,
                      p: SnrParams) -> tuple[dict[str, float], dict[str, float]]:
    """(raw, market residual) formation-window returns per symbol on ``data_date``.

    The residual is the window's summed daily return less beta times the market's, beta from the
    ``beta_n`` sessions before the window, no alpha. Absent = too little of a window.
    """
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day:
        return {}, {}
    f0 = j - p.rev_n + 1
    b_end = f0 - 1
    b0 = b_end - p.beta_n + 1
    mrow = grid.row.get(p.market)
    if b0 < 0 or mrow is None:
        return {}, {}
    names = [s for s in symbols if s in grid.row]
    if not names:
        return {}, {}
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)
    rw, mw = grid.rets[idx, f0 : j + 1], grid.rets[mrow, f0 : j + 1]
    ok_w = np.isfinite(rw) & np.isfinite(mw)[None, :]
    rb, mb = grid.rets[idx, b0 : b_end + 1], grid.rets[mrow, b0 : b_end + 1]
    ok_b = np.isfinite(rb) & np.isfinite(mb)[None, :]
    n = ok_b.sum(axis=1).astype(np.float64)
    enough = (ok_w.sum(axis=1) >= max(3, math.ceil(MIN_FRAC * p.rev_n))) & (
        n >= max(3, math.ceil(MIN_FRAC * p.beta_n)))
    xz = np.where(ok_b, np.broadcast_to(mb, rb.shape), 0.0)
    yz = np.where(ok_b, rb, 0.0)
    sx, sy = xz.sum(axis=1), yz.sum(axis=1)
    den = n * (xz * xz).sum(axis=1) - sx * sx
    with np.errstate(divide="ignore", invalid="ignore"):
        beta = np.where(den != 0.0, (n * (xz * yz).sum(axis=1) - sx * sy) / np.where(den != 0.0, den, 1.0),
                        np.nan)
        raw = np.where(ok_w, rw, 0.0).sum(axis=1)
        resid = np.where(ok_w, rw - beta[:, None] * mw[None, :], 0.0).sum(axis=1)
    live = enough & np.isfinite(resid)
    ks = [int(v) for v in np.flatnonzero(live)]
    return ({names[k]: float(raw[k]) for k in ks}, {names[k]: float(resid[k]) for k in ks})


def size_neutral(resid: Mapping[str, float], dv: Mapping[str, float]) -> dict[str, float]:
    """Each residual less its fit on log dollar volume across the names scored that day."""
    names = sorted(s for s in resid if dv.get(s, 0.0) > 0.0)
    if len(names) < 5:
        return {}
    x = np.log(np.asarray([dv[s] for s in names], dtype=np.float64))
    y = np.asarray([resid[s] for s in names], dtype=np.float64)
    xc = x - x.mean()
    var = float((xc * xc).sum())
    slope = float((xc * (y - y.mean())).sum()) / var if var > 0.0 else 0.0
    e = y - y.mean() - slope * xc
    return {s: float(v) for s, v in zip(names, e, strict=True)}


def targets_from(rows: list[FactorRow], grid: ReturnGrid | None, data_date: date,
                 p: SnrParams) -> tuple[Target, ...]:
    rows = [r for r in rows if r.symbol not in EXCLUDED]
    if not rows:
        return ()
    if p.signal == "ctrl":  # no opinion: the most liquid names, which is the market's own shape
        chosen = sorted(rows, key=lambda r: (-r.dollar_volume, r.symbol))[: p.inner.top]
    else:
        if grid is None:
            return ()
        raw, resid = formation_returns(grid, [r.symbol for r in rows], data_date, p)
        if p.signal == "raw":
            scores = raw
        else:
            scores = size_neutral(resid, {r.symbol: r.dollar_volume for r in rows})
        scorable = [r for r in rows if r.symbol in scores]
        chosen = sorted(scorable, key=lambda r: (p.side * scores[r.symbol], r.symbol))[: p.inner.top]
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, p.inner), strict=True):
        if weight is None:
            continue
        t = target_from_close(row.symbol, row.close, weight)
        if t is not None:
            out.append(t)
    return tuple(out)


class SizeNeutralResidualReversalAllocator:
    """The month's biggest size-neutral residual fallers (or a control) among screened names."""

    id = "M0490"

    def lookback(self, params: Any) -> int:
        return snr_lookback(_check(params))

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

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return targets_from(rows, build_grid(history, p.market), data_date, p)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
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


SNR = SizeNeutralResidualReversalAllocator()

GATED = FactorParams(rank="momentum", top=20, trend=("SPY", 200))
OPEN = FactorParams(rank="momentum", top=20, trend=None)


def _v(suffix: str, params: SnrParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0490-{suffix}", family="M0490", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SNR, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0490",
    name=("Short-term residual reversal: last month's losers after the market and company size "
          "are taken out"),
    family="stock-residual-reversal",
    source_kind="paper",
    source_ref=("Blitz, Huij, Lansdorp & Verbeek 2013, 'Short-term residual reversal', "
                "Journal of Financial Markets 16(3) 477-504"),
    hypothesis=(
        "Published 2013 on US data to 2010; the dev window to 2015 sits mostly before the crowd, "
        "and 2009-2015 will be read on its own. Plain one-month reversal is partly a bet on the "
        "factors the losers load on (small, jumpy, high beta). Blitz et al. rank on the month's "
        "return left after the factors, claiming about twice the premium with less crash exposure "
        "and lower turnover. Book: each month, among liquid index members behind the SPY-200 "
        "switch, hold the 20 with the most negative residual after a daily market-model fit (252 "
        "sessions before the 21-session window) and a cross-sectional fit on log dollar volume "
        "(size proxy; value needs fundamentals the store lacks, so it is omitted), equal slots, "
        "fractional shares at Gotrade's real fees on the owner's monthly deposits. Arms: RESID "
        "(the idea); RAW plain one-month losers; RESID-REV the mirror (winners) to prove the "
        "signal; CTRL-GATE and CTRL-ALWAYS, the 20 most liquid names with no opinion, gated and "
        "always invested, so what acting costs is separable from what the signal earns; RESID-OPEN "
        "RESID without the gate, the 2x2 pair that prices the gate. Success: beat total-return "
        "SPY on the deposits with worst fall under 25%, profit factor >= 1.3, a positive edge in "
        "2009-2015, and RESID beating both RESID-REV and CTRL-ALWAYS."
    ),
    expected_failure=(
        "M0028's plain bounce book and M0158's standardised one both died at real fees: about 16 "
        "turns a year on $28 slots, and the premium is a liquidity-provision payment that shrank "
        "after decimal ticks (2001) and is widely published. Size-neutralising on dollar volume may "
        "only re-weight toward big names and reproduce a low-beta tilt that lags SPY in bull "
        "years. The 200-day gate reacts late in crashes (autumn 2008), so the fall may pass 25%. "
        "If RESID does not beat CTRL-ALWAYS the signal is worth less than the habit costs."
    ),
    candidates=(
        _v("RESID", SnrParams(GATED), "20 most negative size-neutral residuals, gated"),
        _v("RAW", SnrParams(GATED, signal="raw"), "20 most negative plain 21-session returns, gated"),
        _v("RESID-REV", SnrParams(GATED, side=1), "Mirror: 20 most positive size-neutral residuals"),
        _v("CTRL-GATE", SnrParams(GATED, signal="ctrl"),
           "No opinion: 20 most liquid names, same gate and monthly churn"),
        _v("CTRL-ALWAYS", SnrParams(OPEN, signal="ctrl"),
           "No opinion, no gate: always invested; prices what acting costs"),
        _v("RESID-OPEN", SnrParams(OPEN), "RESID with no gate: the pair that prices the gate's habit"),
    ),
    seen_keys=(
        "concept:residual-reversal-size-neutral",
        "concept:reversal-always-invested-control",
    ),
)
