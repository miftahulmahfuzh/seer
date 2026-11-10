"""M0552 — Short-term distance from the 10-day average: buy the members whose month-end close sits
furthest below their own 10-day moving average.

Source: "Short-Term Moving Average Distance", Financial Analysts Journal (2025),
https://rpc.cfainstitute.org/research/financial-analysts-journal/2025/short-term-moving-average-distance.
Reserved by Sera batch 20261110-1011 as an ``idea`` row; this file refines it and keeps its id.

WHY. SMAD is the month-end close divided by the mean of the last ten closes. The paper reports that
it predicts next month's return NEGATIVELY -- the market over-reacts to the last two weeks -- and
that it subsumes plain one-month reversal (STR). Published 2025, so the whole dev window
(1996-2015) predates the crowd; that also means the only reason to expect it to last is the paper's
own word.

THE LAB'S CLOSEST RECORDS. M0282 ranked a 21-day over a 200-day average with the POSITIVE sign (a
trend signal; its top book was momentum renamed) and M0285 the 200-day distance. This method is the
opposite sign at a two-week horizon: a reversal signal, closest in spirit to the lab's one-month
loser books (M0028, M0490, M0538), every one of which was rejected at real fees. The plain
one-month-loser book on this exact chassis is already recorded as M0490-RAW (20 most negative
21-session returns, same F4 screen, same SPY 200-day switch, same real-fee fractional preset); it
is not re-run here, it is read from the record as the STR comparison. M0490-RAW drops a name with
too few usable daily returns in its 21+252-session windows, so its pool is a hair narrower.

THE POOL, ONE PER DECISION, SHARED BY EVERY ARM. F4's screen (``f_factor``): index members (S&P
500 union Nasdaq-100, point in time) with 253 bars through the day, 20-day mean dollar volume over
$20M and a close of at least $5; SPY itself excluded.

ARMS, 20 equal slots, re-ranked monthly, fully replaced each month (no keep band):

    SMAD        the 20 lowest close / SMA10, behind the SPY 200-day switch -- the idea
    SMAD-HIGH   mirror: the 20 highest, same switch -- proves the signal's sign
    SMAD-OPEN   SMAD with no switch, always invested: the habit-off half of the 2x2 that prices
                the switch
    SMAD-XSTR   the 20 lowest residuals of log(SMAD) after a cross-sectional fit on the 21-session
                return: what SMAD knows that plain one-month reversal does not
    DRAW-1/2    no opinion: ``control_draw.matched_book`` on the SMAD book, seeds 1-2 -- same pool,
                same switch, same book size and the same monthly entry count, names by hash

Rules ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees on the owner's
monthly top-up.

Pure: no clock, randomness, files or network; reads only bars dated on or before ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import ResidPrepared
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
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
SIGNALS = ("low", "high", "xstr", "draw")
SMA_N = 10
STR_N = 21


@dataclass(frozen=True, slots=True)
class SmadParams:
    """``inner`` is F4's screen, switch and book size; ``signal`` picks what is ranked.

    ``seed`` is read only by ``signal="draw"``.
    """

    inner: FactorParams
    signal: str = "low"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.signal not in SIGNALS:
            raise ValueError(f"signal must be one of {SIGNALS}, got {self.signal!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"signal": self.signal, "seed": str(self.seed), "sma_n": str(SMA_N),
               "str_n": str(STR_N)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> SmadParams:
    if not isinstance(params, SmadParams):
        raise TypeError(f"params must be SmadParams, got {type(params).__name__}")
    return params


def features(history: Mapping[str, History], rows: Sequence[FactorRow],
             data_date: date) -> dict[str, tuple[float, float]]:
    """(SMAD, 21-session return) per screened symbol on ``data_date``; closes dated <= the day."""
    out: dict[str, tuple[float, float]] = {}
    for r in rows:
        h = history.get(r.symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < STR_N:
            continue
        c = np.asarray(h.close[i - STR_N : i + 1], dtype=np.float64)
        sma = float(c[-SMA_N:].mean())
        if not (np.all(np.isfinite(c)) and sma > 0.0 and c[0] > 0.0):
            continue
        out[r.symbol] = (float(c[-1]) / sma, float(c[-1] / c[0] - 1.0))
    return out


def xstr_residual(feats: Mapping[str, tuple[float, float]]) -> dict[str, float]:
    """log(SMAD) less its cross-sectional least-squares fit on the 21-session return."""
    names = sorted(feats)
    if len(names) < 5:
        return {}
    y = np.log(np.asarray([feats[s][0] for s in names], dtype=np.float64))
    x = np.asarray([feats[s][1] for s in names], dtype=np.float64)
    xc = x - x.mean()
    var = float((xc * xc).sum())
    slope = float((xc * (y - y.mean())).sum()) / var if var > 0.0 else 0.0
    e = y - y.mean() - slope * xc
    return {s: float(v) for s, v in zip(names, e, strict=True)}


def ranked_book(history: Mapping[str, History], rows: Sequence[FactorRow], data_date: date,
                signal: str, top: int) -> tuple[list[str], list[str]]:
    """(the scored pool, the ``signal`` arm's book) on ``data_date``."""
    feats = features(history, rows, data_date)
    if signal == "xstr":
        scores = xstr_residual(feats)
    else:
        side = -1.0 if signal == "high" else 1.0
        scores = {s: side * f[0] for s, f in feats.items()}
    pool = sorted(scores)
    return pool, sorted(pool, key=lambda s: (scores[s], s))[:top]


class ShortMaDistanceAllocator:
    """The month's lowest (or highest) close-to-10-day-average ratios among screened names."""

    id = "M0552"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        base = max(factor_lookback(p.inner), STR_N + 1)
        return base + (control_draw.PREVIOUS_DECISION_BARS + 1 if p.signal == "draw" else 0)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return () if p.inner.trend is None else (p.inner.trend[0],)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, history: Mapping[str, History], rows_on: Any, members: AbstractSet[str],
             data_date: date, held: frozenset[str], p: SmadParams) -> tuple[Target, ...]:
        if not trend_on(history, data_date, p.inner):
            return ()

        def select(d: date) -> tuple[list[str], list[str]]:
            rows = [r for r in rows_on(members, d, p.inner) if r.symbol not in EXCLUDED]
            return ranked_book(history, rows, d, "low", p.inner.top)

        rows = [r for r in rows_on(members, data_date, p.inner) if r.symbol not in EXCLUDED]
        if p.signal == "draw":
            names = control_draw.matched_book(select, data_date, held, tag="M0552", seed=p.seed)
        else:
            names = ranked_book(history, rows, data_date, p.signal, p.inner.top)[1]
        by_symbol = {r.symbol: r for r in rows}
        chosen = [by_symbol[s] for s in names if s in by_symbol]
        out: list[Target] = []
        for row, weight in zip(chosen, factor_weights(chosen, p.inner), strict=True):
            if weight is None:
                continue
            t = target_from_close(row.symbol, row.close, weight)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)

        def rows_on(m: AbstractSet[str], d: date, inner: FactorParams) -> list[FactorRow]:
            return factor_rows(history, m, d, inner)

        return self._run(history, rows_on, members, data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return ResidPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        return self._run(prepared.history, prepared.factor.rows_on, members, data_date, held, p)


SMAD = ShortMaDistanceAllocator()

GATED = FactorParams(rank="momentum", top=20, trend=("SPY", 200))
OPEN = FactorParams(rank="momentum", top=20, trend=None)


def _v(suffix: str, params: SmadParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0552-{suffix}", family="M0552", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SMAD, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0552",
    name=("Short-term distance from the 10-day average: buy the members whose month-end close sits "
          "furthest below their own 10-day moving average"),
    family="stock-short-ma-distance",
    source_kind="paper",
    source_ref=("https://rpc.cfainstitute.org/research/financial-analysts-journal/2025/"
                "short-term-moving-average-distance"),
    hypothesis=(
        "FAJ 2025 (published 2025, so the 1996-2015 dev window predates the crowd): the gap between "
        "the month-end close and its own 10-day moving average (SMAD) predicts next month's return "
        "NEGATIVELY, because investors over-react to the last two weeks, and the paper says SMAD "
        "subsumes plain one-month reversal. The lab's closest records are M0282 (21-day vs 200-day "
        "average, a TREND signal with the positive sign, which turned out to be momentum renamed) "
        "and M0285 (distance below the 200-day average); this is the opposite sign at a two-week "
        "horizon, a reversal bet. Book: each month, among F4-screened index members (liquid, $5+), "
        "hold the 20 with the lowest close/SMA10, equal slots, behind the SPY 200-day switch, "
        "fractional shares at Gotrade's real fees on the owner's monthly top-up. Arms: SMAD (the "
        "idea); SMAD-HIGH the mirror; SMAD-OPEN the same book always invested (prices the switch); "
        "SMAD-XSTR the part of SMAD a cross-sectional fit on the 21-session return does not "
        "explain (does SMAD know anything plain reversal lacks?); DRAW-1/2 blind draws matched on "
        "SMAD's book size and monthly entry count, same pool and switch. The plain one-month-loser "
        "book on this chassis is already recorded as M0490-RAW and is compared from the record, "
        "not re-run. Success: beat total-return SPY with worst fall under 25%, profit factor >= "
        "1.3, a positive edge in 2009-2015, SMAD beating SMAD-HIGH, both draws and M0490-RAW, and "
        "SMAD-XSTR beating the draws."
    ),
    expected_failure=(
        "Like the lab's other short-horizon reversal books (M0028, M0490, M0538), it lands inside "
        "the blind-draw band after fees: a full monthly re-rank turns most of the book every month, "
        "about $28 slots pay Gotrade's minimums, and the reversal premium is a liquidity payment "
        "that shrank after decimal ticks in 2001. SMAD-XSTR ties the draws (SMAD is one-month "
        "reversal measured another way). Bought on two-week dips, the book loads on falling, jumpy "
        "names, so the 2008 fall behind a late 200-day switch may pass 25%, and 2009-2015 (a quiet "
        "rising market) gives a dip-buyer little to buy."
    ),
    candidates=(
        _v("SMAD", SmadParams(GATED, "low"), "20 lowest close / 10-day average, gated: the idea"),
        _v("SMAD-HIGH", SmadParams(GATED, "high"),
           "Mirror: 20 highest close / 10-day average, gated"),
        _v("SMAD-OPEN", SmadParams(OPEN, "low"),
           "SMAD with no switch, always invested: prices the switch"),
        _v("SMAD-XSTR", SmadParams(GATED, "xstr"),
           "20 lowest SMAD residuals after the 21-session return, gated: SMAD beyond plain reversal"),
        _v("DRAW-1", SmadParams(GATED, "draw", seed=1),
           "Control: blind draw seed 1 matched on SMAD's book size and entry count, same switch"),
        _v("DRAW-2", SmadParams(GATED, "draw", seed=2),
           "Control: blind draw seed 2 matched on SMAD's book size and entry count, same switch"),
    ),
    seen_keys=("concept:short-term-ma-distance", "concept:smad-10-day"),
)
