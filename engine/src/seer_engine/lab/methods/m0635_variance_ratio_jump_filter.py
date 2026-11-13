"""M0635 — Only take an earnings-day jump when the stock's own price path reads as trending.

Source: Lo & MacKinlay (1988), "Stock Market Prices Do Not Follow Random Walks: Evidence from a
Simple Specification Test", Review of Financial Studies 1(1), 41-66; a variation of M0072.
Idea: the variance ratio VR(k) = Var(k-day return) / (k * Var(1-day return)) is 1 for a random
walk, above 1 when a stock's moves tend to continue (trending) and below 1 when they tend to
reverse (mean-reverting). M0072's book takes news days that were large for the stock; this adds
one admission test on top of that: the stock's own recent VR must read the way the arm says.
It has never been used in this lab as a per-stock filter on a news-day pool. The nearest
recorded ideas (M0432 return autocorrelation, M0547/M0551 Hurst persistence) ranked or gated a
momentum pool, not an event pool.

VR at data date d reads the stock's closes up to and including d: ``win`` overlapping k-day
returns and ``win`` one-day returns, each window ending on d, so nothing later is read. Everything
else is M0072's (its event, z filter, ranking, SPY-200 switch, 20 slots of 5%, SPY in empty slots,
fractional shares at Gotrade's real fees); the host book is M0072-Z2-RAWRANK and is cited, not
re-run.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0072_standardised_earnings_jump import (
    JUMP20,
    ZParams,
    ZPrepared,
    live_event,
)
from seer_engine.lab.methods.m0063_earnings_day_jump import jump_lookback
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import factor_rows, prepare_factor, trend_on

ADDED = date(2026, 11, 13)


@dataclass(frozen=True, slots=True)
class VRParams:
    """``z`` is M0072's book; ``k``/``win``/``mode``/``vr_cut`` are the variance-ratio admission test."""

    z: ZParams
    k: int = 5  # days in the multi-day return
    win: int = 120  # sessions in the variance window (ending on the data date)
    mode: str = "trend"  # "trend" admits VR >= vr_cut, "revert" admits VR < vr_cut
    vr_cut: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        if not isinstance(self.z, ZParams):
            raise TypeError(f"z must be ZParams, got {type(self.z).__name__}")
        if isinstance(self.k, bool) or not isinstance(self.k, int) or self.k < 2:
            raise ValueError(f"k must be an int >= 2, got {self.k!r}")
        if isinstance(self.win, bool) or not isinstance(self.win, int) or self.win < 20:
            raise ValueError(f"win must be an int >= 20, got {self.win!r}")
        if self.mode not in ("trend", "revert"):
            raise ValueError(f"mode must be 'trend' or 'revert', got {self.mode!r}")
        if not isinstance(self.vr_cut, Decimal) or not self.vr_cut.is_finite() or self.vr_cut <= 0:
            raise ValueError(f"vr_cut must be a finite Decimal > 0, got {self.vr_cut!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"k": str(self.k), "win": str(self.win), "mode": self.mode, "vr_cut": str(self.vr_cut)}
        for key, v in self.z.as_dict().items():
            out[f"z.{key}"] = v
        return out


def _check(params: object) -> VRParams:
    if not isinstance(params, VRParams):
        raise TypeError(f"params must be VRParams, got {type(params).__name__}")
    return params


def _roll_var(x: np.ndarray, win: int) -> np.ndarray:
    """Population variance of the ``win`` values ending at each index; NaN until a full window."""
    out = np.full(len(x), np.nan)
    if len(x) < win:
        return out
    c1 = np.concatenate(([0.0], np.cumsum(x)))
    c2 = np.concatenate(([0.0], np.cumsum(x * x)))
    s1 = c1[win:] - c1[:-win]
    s2 = c2[win:] - c2[:-win]
    out[win - 1 :] = np.maximum(s2 / win - (s1 / win) ** 2, 0.0)
    return out


def vr_col(h: History, k: int, win: int) -> np.ndarray:
    """vr[t] reads closes up to and including bar t only; NaN when unknown."""
    n = len(h)
    vr = np.full(n, np.nan)
    if n < win + k + 1:
        return vr
    with np.errstate(divide="ignore", invalid="ignore"):
        r1 = np.full(n, np.nan)
        r1[1:] = np.log(h.close[1:] / h.close[:-1])
        rk = np.full(n, np.nan)
        rk[k:] = np.log(h.close[k:] / h.close[:-k])
    if not np.all(np.isfinite(r1[1:])) or not np.all(np.isfinite(rk[k:])):
        r1 = np.nan_to_num(r1, nan=0.0, posinf=0.0, neginf=0.0)
        rk = np.nan_to_num(rk, nan=0.0, posinf=0.0, neginf=0.0)
    r1 = np.nan_to_num(r1)
    rk = np.nan_to_num(rk)
    v1 = _roll_var(r1, win)
    vk = _roll_var(rk, win)
    with np.errstate(divide="ignore", invalid="ignore"):
        vr = vk / (k * v1)
    vr[~np.isfinite(vr) | (v1 <= 0)] = np.nan
    vr[: win + k] = np.nan
    return vr


class VRPrepared(ZPrepared):
    """ZPrepared plus each symbol's variance-ratio column, computed on first use."""

    def __init__(self, history: Mapping[str, History], factor: Any) -> None:
        super().__init__(history, factor)
        self._vr: dict[tuple[str, int, int], np.ndarray] = {}

    def vr(self, symbol: str, k: int, win: int) -> np.ndarray | None:
        key = (symbol, k, win)
        if key not in self._vr:
            h = self.history.get(symbol)
            if h is None:
                return None
            self._vr[key] = vr_col(h, k, win)
        return self._vr[key]


class VRJumpAllocator:
    """M0072's news-day book, admitting a pick only when its own variance ratio reads as asked."""

    id = "M0635"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(jump_lookback(p.z.jump), p.z.jump.hold + p.z.sd_base + 2, p.win + p.k + 2)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params).z.jump
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params).z.jump
        return (p.market,) if p.park else ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _targets(self, prepared: VRPrepared, rows: list[Any], data_date: date,
                 held: frozenset[str], p: VRParams) -> tuple[Target, ...]:
        jp = p.z.jump
        cut = float(p.vr_cut)
        live: list[tuple[int, float, str]] = []
        for r in rows:
            h = prepared.history.get(r.symbol)
            if h is None or r.symbol == jp.market:
                continue
            i = h.index_of(data_date)
            got = prepared.cols(r.symbol, jp.market, jp.vol_base, p.z.sd_base)
            if i is None or got is None:
                continue
            ev = live_event(got[0], got[1], i, p.z)
            if ev is None:
                continue
            col = prepared.vr(r.symbol, p.k, p.win)
            v = float(col[i]) if col is not None else float("nan")
            if not np.isfinite(v):
                continue
            if (v < cut) if p.mode == "trend" else (v >= cut):
                continue
            score = ev[0] if p.z.rank == "z" else ev[1]
            live.append((0 if r.symbol in held else 1, -score, r.symbol))
        w = equal_weight(jp.inner.top)
        out: list[Target] = []
        for _, _, s in sorted(live)[: jp.inner.top]:
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        if jp.park:
            rest = Decimal(1) - w * len(out)
            mh = prepared.history.get(jp.market)
            if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
                t = target_from_close(jp.market, last_close(mh, data_date), rest)
                if t is not None:
                    out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.z.jump.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.z.jump.inner)
        return self._targets(VRPrepared(history, None), rows, data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> VRPrepared:
        return VRPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, VRPrepared) or prepared.factor is None:
            raise TypeError(f"prepared must be a prepared VRPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.z.jump.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.z.jump.inner)
        return self._targets(prepared, rows, data_date, held, p)


VRJUMP = VRJumpAllocator()

HOST = ZParams(JUMP20, z_min=Decimal("2"), rank="raw")  # M0072-Z2-RAWRANK's book


def _v(suffix: str, params: VRParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0635-{suffix}", family="M0635",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=VRJUMP, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0635",
    name="Per-stock variance-ratio regime filter on the earnings-day jump book: only rank a pick "
         "when its own recent return series reads as trending (VR>1), not mean-reverting (VR<1)",
    family="stock-variance-ratio-regime",
    source_kind="paper",
    source_ref="Lo, A.W. & MacKinlay, A.C. (1988), Stock Market Prices Do Not Follow Random Walks: "
               "Evidence from a Simple Specification Test, Review of Financial Studies 1(1), 41-66",
    parent_id="M0072",
    hypothesis=(
        "Published 1988, so the dev window shows only a long-known test; 2009-2015 is judged first. "
        "Host book is M0072-Z2-RAWRANK (earnings-day jump book, z >= 2, ranked by raw jump; "
        "+12.3% a year vs SPY +7.2% on dev, luck score 0.914, but a 1998 fall of 22-24% over the "
        "20% limit). That recorded trial is the no-opinion control and is cited, not re-run: same "
        "preset (monthly-hold-frac-gotrade), same fees, same funding, same store. Hypothesis: a "
        "stock whose own variance ratio reads above 1 (moves tend to continue) keeps its news-day "
        "jump, while a stock reading below 1 (moves tend to reverse) gives it back, so admitting "
        "only trending names should lift picks and shrink the 1998 fall. Arms: TREND-K5-W120 "
        "(VR of 5-day returns over 120 sessions >= 1), TREND-K10-W250 (10-day over 250 sessions, "
        "slower and steadier), TREND-K5-W120-C115 (VR >= 1.15: a stricter trend bar), REVERT-K5-W120 "
        "(the mirror, VR < 1: if the signal is real this must do worse than the host, and it prices "
        "the filter's churn against the always-invested host). The host control is M0072-Z2-RAWRANK "
        "by its recorded trial. Success: a trending arm with worst fall under 20% that beats "
        "total-return SPY at DSR >= 0.90 and in 2009-2015, and a mirror that does worse."
    ),
    expected_failure=(
        "M0072's own analysis said pick-side changes stopped helping, and the 1998 fall was "
        "market-wide, so a filter on picks may not shrink it. A 120-day variance ratio is a noisy "
        "estimate (its sampling error is roughly 20-30% at this length), so VR >= 1 is close to a "
        "coin flip per stock and the filter may only thin the pool and leave more slots in SPY. "
        "The news-day itself raises VR, so the filter may select on the jump rather than on the "
        "regime. Related ideas (return autocorrelation, Hurst persistence) were rejected. Likely "
        "result: a result not distinguishable from the host."
    ),
    candidates=(
        _v("TREND-K5-W120", VRParams(HOST, k=5, win=120, mode="trend"),
           "Admit only picks whose 5-day variance ratio over 120 sessions is at least 1"),
        _v("TREND-K10-W250", VRParams(HOST, k=10, win=250, mode="trend"),
           "Slower regime read: 10-day variance ratio over 250 sessions at least 1"),
        _v("TREND-K5-W120-C115", VRParams(HOST, k=5, win=120, mode="trend", vr_cut=Decimal("1.15")),
           "Stricter trend bar: variance ratio at least 1.15"),
        _v("REVERT-K5-W120", VRParams(HOST, k=5, win=120, mode="revert"),
           "Mirror: only mean-reverting picks (VR below 1); must do worse than the trend arm if the signal is real"),
    ),
    seen_keys=(
        "concept:variance-ratio-filter",
        "concept:lo-mackinlay-random-walk-test",
        "concept:per-stock-regime-filter",
    ),
)
