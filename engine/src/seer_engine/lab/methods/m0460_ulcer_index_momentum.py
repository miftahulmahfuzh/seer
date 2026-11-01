"""M0460 — Rank winners by the pain of the ride: 12-month return divided by the ulcer index.

Source: Peter Martin and Byron McCann, "The Investor's Guide to Fidelity Funds" (1989), which
introduced the Ulcer Performance Index (the Martin ratio): return per unit of the ulcer index, the
root-mean-square of every day's fall below its running high. Unlike a single worst fall (M0108) it
counts how deep *and how long* a stock sat under water. Published 1989 and used by fund raters
since; the dev window therefore sees a form of it that crowds have long known.

Idea: plain 12-1 momentum picks winners however bumpy the road. Dividing the same return by the
ulcer index prefers winners that got there smoothly. M0443 found smooth-path winners did not beat
plain momentum, and M0108 found a stock's own worst fall says nothing about a market-wide crash,
so the honest prior is a modest result; the lab has never priced this particular ratio.

Formation window: the 252 closes ending 21 closes before d (the usual skip month). Return =
close at the end / close at the start - 1. Ulcer index = sqrt(mean over the window of
(1 - close / running high)^2), floored at 0.005 so a near-flat series cannot divide by zero.

Arms, all in F4's frame (point-in-time index members, $5 price and 20M-dollar volume screen,
monthly re-picks, equal weights, fractional shares at Gotrade's real fees, no trend gate):

- UPI20 / UPI40: highest return / ulcer index; 20 or 40 names.
- ANTI20: the mirror, the 20 *lowest* ratios. A reversal proves the signal, not the cost of acting.
- MOM20: plain 12-1 return, same frame, same book size: the twin that says what dividing by
  pain adds.
- CALM20: the 20 lowest ulcer index, return ignored: separates the pain half from the return half.
- EW40-DV: the 40 most-traded members, equal weighted, no opinion of any kind: the always-invested
  control that prices the habit of monthly re-picking and equal weighting (the third arm for the
  mirror pair).

Reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20_NOTREND
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    factor_weights,
    prepare_factor,
)

ADDED = date(2026, 11, 1)

Rank = Literal["upi", "anti", "mom", "calm", "traded"]
_RANKS: tuple[str, ...] = ("upi", "anti", "mom", "calm", "traded")
SKIP = 21
UI_FLOOR = 0.005


@dataclass(frozen=True, slots=True)
class PainParams:
    """``inner`` is F4's screen, book size and weighting; the rest is the ranking."""

    inner: FactorParams
    side: Rank = "upi"
    window: int = 252  # formation closes, ending SKIP closes before d

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not isinstance(self.side, str) or self.side not in _RANKS:
            raise ValueError(f"side must be one of {_RANKS}, got {self.side!r}")
        if isinstance(self.window, bool) or not isinstance(self.window, int):
            raise TypeError(f"window must be an int, got {type(self.window).__name__}")
        if self.window < 21:
            raise ValueError(f"window must be >= 21, got {self.window}")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "window": str(self.window)}
        for key, v in self.inner.as_dict().items():
            out[f"inner.{key}"] = v
        return out


def _check(params: object) -> PainParams:
    if not isinstance(params, PainParams):
        raise TypeError(f"params must be PainParams, got {type(params).__name__}")
    return params


def pain_lookback(params: PainParams) -> int:
    """Bars each read symbol needs through d: F4's screen, or the drawdown window if longer.

    Declared truthfully, because ``choose`` really reads ``window`` closes. M0069 declares only
    its screen and lets the members' longer formation window gate eligibility instead, which
    keeps its run start early; here that would be a false declaration the allocator contract
    catches, so DD20-L18 simply starts about six months later than the 252-bar variants. The
    cost is that its first months are not directly comparable with theirs; the analysis says so.
    """
    return max(factor_lookback(params.inner), params.window + SKIP + 1)


def pain_stats(h: History, data_date: date, window: int) -> tuple[float, float] | None:
    """(return, ulcer index) over the ``window`` closes ending SKIP closes before ``data_date``."""
    i = h.index_of(data_date)
    end = None if i is None else i - SKIP
    if end is None or end + 1 < window:
        return None
    c = h.close[end + 1 - window : end + 1]
    if not (np.all(np.isfinite(c)) and np.all(c > 0.0)):
        return None
    dd = 1.0 - c / np.maximum.accumulate(c)
    ui = max(float(np.sqrt(np.mean(dd * dd))), UI_FLOOR)
    ret = float(c[-1] / c[0] - 1.0)
    return (ret, ui) if np.isfinite(ret) else None


def choose(rows: list[FactorRow], history: Mapping[str, History], data_date: date,
           params: PainParams) -> list[FactorRow]:
    """The chosen rows in rank order; ties by symbol ascending."""
    scored: list[tuple[float, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED:
            continue
        if params.side == "traded":  # the equal-weight yardstick: most-traded first
            scored.append((-r.dollar_volume, r.symbol, r))
            continue
        h = history.get(r.symbol)
        if h is None:
            continue
        s = pain_stats(h, data_date, params.window)
        if s is None:
            continue
        ret, ui = s
        key = {"upi": -ret / ui, "anti": ret / ui, "mom": -ret, "calm": ui}[params.side]
        scored.append((key, r.symbol, r))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [r for _, _, r in scored[: params.inner.top]]


def targets_from_rows(chosen: list[FactorRow], params: PainParams) -> tuple[Target, ...]:
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, params.inner), strict=True):
        if weight is None:
            continue
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


@dataclass
class PainPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)


class PainAllocator:
    """F4's screen, ranked on return per unit of ulcer index (or one of its control keys).

    No trend gate: the book is always invested. Held symbols get no special treatment -- a name
    that leaves the chosen set is signal-exited by the book engine.
    """

    id = "M0460"

    def lookback(self, params: Any) -> int:
        return pain_lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.inner.trend[0],) if p.inner.trend is not None else ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        rows = factor_rows(history, members, data_date, p.inner)
        return targets_from_rows(choose(rows, history, data_date, p), p)

    def prepare(self, history: Mapping[str, History]) -> PainPrepared:
        return PainPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, PainPrepared):
            raise TypeError(f"prepared must be PainPrepared, got {type(prepared).__name__}")
        p = _check(params)
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return targets_from_rows(choose(rows, prepared.history, data_date, p), p)


PAIN = PainAllocator()

N20 = N20_NOTREND  # F4's screen, 20 equal slots, always invested
N40 = replace(N20_NOTREND, top=40)


def _v(suffix: str, params: PainParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0460-{suffix}", family="M0460", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=PAIN, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0460",
    name="Rank winners by the pain of the ride: 12-month return divided by the ulcer index",
    family="stock-pain-adjusted-momentum",
    source_kind="paper",
    source_ref=(
        "Martin and McCann, The Investor's Guide to Fidelity Funds (1989): the Ulcer Performance "
        "Index (Martin ratio)"
    ),
    parent_id=None,
    hypothesis=(
        "Plain 12-1 momentum picks winners however bumpy their road. Dividing the same 12-1 return "
        "by the ulcer index (root-mean-square of every day's fall below the running high, so it "
        "counts depth and time under water) prefers winners that got there smoothly. Each month, "
        "among F4-screened point-in-time S&P 500 / Nasdaq-100 members ($5 price, 20M-dollar volume), "
        "hold the top 20 by that ratio at 5% each, fractional shares at Gotrade's real fees "
        "(monthly-hold-frac-gotrade), no market switch. Published 1989, so the dev window sees an "
        "edge crowds have long known. Arms: UPI20 and UPI40; ANTI20 (the 20 lowest ratios, the "
        "mirror); MOM20 (plain 12-1, the same-frame twin); CALM20 (lowest ulcer index, return "
        "ignored, separates the pain half from the return half); EW40-DV (40 most-traded members "
        "equal weighted, no opinion: the third arm that prices what acting on the signal costs, so "
        "a mirror reversal can be told from a badly dressed rule). Success: UPI20 beats SPY TR on "
        "deposit-matched money with a worst fall under 20%, clears a majority of walk-forward "
        "folds, beats MOM20 and EW40-DV, is positive in 2009-2015, and ANTI20 trails clearly."
    ),
    expected_failure=(
        "M0443 found smooth-path winners did not beat plain momentum, and M0108 found a stock's "
        "own fall says nothing about the day every stock falls together: an always-invested "
        "long-only book has nowhere to hide in 2008, so the 20% bar is likely out of reach "
        "whatever it holds. The ratio may collapse onto low-volatility large caps (CALM20 will "
        "show it), trailing SPY through the 2009-2015 growth run and no better than EW40-DV. "
        "Dividing by a floor-limited ulcer index also rewards stocks with flat, rising paths, "
        "which may be the survivors of a data set with no delisted names."
    ),
    candidates=(
        _v("UPI20", PainParams(N20, side="upi"),
           "Top 20 by 12-1 return per unit of ulcer index, always invested: the book"),
        _v("UPI40", PainParams(N40, side="upi"),
           "Top 40 by the same ratio: broader, less single-stock risk"),
        _v("ANTI20", PainParams(N20, side="anti"),
           "The 20 lowest ratios: the mirror, expected to trail"),
        _v("MOM20", PainParams(N20, side="mom"),
           "Plain 12-1 momentum, same frame and size: what dividing by pain adds"),
        _v("CALM20", PainParams(N20, side="calm"),
           "The 20 lowest ulcer index, return ignored: the pain half alone"),
        _v("EW40-DV", PainParams(N40, side="traded"),
           "The 40 most-traded members equal weighted: the no-opinion always-invested control"),
    ),
    seen_keys=(
        "concept:ulcer-index-momentum",
        "concept:martin-ratio-cross-section",
    ),
)
