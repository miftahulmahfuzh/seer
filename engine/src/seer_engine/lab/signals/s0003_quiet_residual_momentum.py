"""S0003 — residual momentum, marked down when it was earned on unusually heavy trading.

Source: variation of M0034 (the queued idea M0046); Blitz, Huij & Martens (2011), "Residual
momentum", for the momentum half. Idea: M0034 found that the level of a name's trading value acts
like a crowding measure inside a momentum book, but the level mixes company size with excitement.
The change cancels size: a name's 20-day mean trading value over its own one-year mean. Between
two names with the same market-stripped momentum, the one that earned it quietly is preferred.

The score is the cross-sectional z-score of residual momentum minus ``PENALTY`` times the z-score
of log relative trading value. Residual momentum: the market model is fitted by least squares on
the ``BETA_N`` SPY sessions ending ``SKIP`` sessions before the data date, and its residuals over
the last ``MOM_N`` of them are summed, unscaled. The lab's own residual books fit over a longer
window than a signal's 473-bar ceiling allows, so this is a shorter-memory cousin of M0007's key,
not a copy of it. A name needs 80% of the fit window. Pure; reads bars dated <= data_date only.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from typing import Any

import numpy as np

from seer_engine.lab.signal import Signal
from seer_engine.strategies.base import History

MARKET = "SPY"
BETA_N = 420  # one-session returns in the market-model fit, ending SKIP sessions before data_date
MOM_N = 231  # the residuals summed: the newest MOM_N of the fit window (twelve months less one)
SKIP = 21
DV_N = 20  # recent trading value
DV_LONG = 252  # the name's own normal trading value
PENALTY = 0.5  # z-score points of residual momentum given up per z-score point of crowding
MIN_FRAC = 0.8


def _on_calendar(h: History, cal: np.ndarray) -> np.ndarray:
    """``h``'s closes on the sessions ``cal``; NaN where it has no bar that day."""
    pos = np.searchsorted(h.dates, cal)
    ok = pos < len(h)
    pos = np.where(ok, pos, 0)
    ok &= h.dates[pos] == cal
    return np.where(ok, h.close[pos], np.nan)


def _z(values: np.ndarray) -> np.ndarray:
    sd = float(values.std())
    return (values - values.mean()) / sd if sd > 0.0 else np.zeros_like(values)


def score(history: Mapping[str, History], market: Any, pool: AbstractSet[str], data_date: date) -> dict[str, float]:
    spy = history.get(MARKET)
    if spy is None:
        return {}
    j = spy.index_of(data_date)
    if j is None or j < BETA_N + SKIP:
        return {}
    cal = spy.dates[j - SKIP - BETA_N : j - SKIP + 1]
    mc = spy.close[j - SKIP - BETA_N : j - SKIP + 1]
    mr = mc[1:] / mc[:-1] - 1.0
    names: list[str] = []
    resid: list[float] = []
    crowd: list[float] = []
    for symbol in sorted(pool):
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i + 1 < DV_LONG:
            continue
        c = _on_calendar(h, cal)
        r = c[1:] / c[:-1] - 1.0
        ok = np.isfinite(r) & np.isfinite(mr)
        if int(ok.sum()) < MIN_FRAC * BETA_N or int(ok[-MOM_N:].sum()) < MIN_FRAC * MOM_N:
            continue
        x, y = mr[ok], r[ok]
        var = float(x.var())
        if var <= 0.0:
            continue
        beta = float(np.mean((x - x.mean()) * (y - y.mean()))) / var
        e = np.where(ok, r - (y.mean() - beta * x.mean()) - beta * mr, 0.0)
        dv = h.close[i + 1 - DV_LONG : i + 1] * h.volume[i + 1 - DV_LONG : i + 1]
        recent, normal = float(dv[-DV_N:].mean()), float(dv.mean())
        if not (recent > 0.0 and normal > 0.0):
            continue
        names.append(symbol)
        resid.append(float(e[-MOM_N:].sum()))
        crowd.append(float(np.log(recent / normal)))
    if len(names) < 2:
        return {}
    out = _z(np.asarray(resid)) - PENALTY * _z(np.asarray(crowd))
    return {s: float(v) for s, v in zip(names, out) if np.isfinite(v)}


SIGNAL = Signal(
    id="S0003",
    name="Market-stripped momentum, marked down when it was earned on unusually heavy trading",
    family="stock-momentum-attention",
    source_kind="variation",
    source_ref="variation of M0034 (queued as M0046); Blitz, Huij & Martens (2011), Residual momentum, J. Empirical Finance 18(3)",
    hypothesis=(
        "Among names with the same market-stripped momentum, the ones whose recent trading value is "
        "normal for them earn more next month than the ones the crowd has just arrived at, so the "
        "penalised score orders next month's returns beyond what plain momentum, beta, size and "
        "volatility explain: a positive controlled slope on both stores and a positive 2009-2015 "
        "spread."
    ),
    expected_failure=(
        "The score is mostly momentum, which is one of the panel's controls, so the controlled slope "
        "is near zero; and heavy recent trading often marks an earnings day, which the lab's "
        "news-day books found to be good news, so the penalty may cut the wrong names."
    ),
    lookback=BETA_N + SKIP + 1,
    score=score,
    idea_id="M0046",
    seen_keys=("concept:crowding-rank-penalty", "concept:relative-trading-value-penalised-residual-momentum"),
)
