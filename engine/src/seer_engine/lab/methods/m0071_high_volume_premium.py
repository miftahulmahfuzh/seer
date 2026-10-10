"""M0071 — The high-volume premium: buy big stocks after unusually heavy trading that did NOT move the price much.

Source: Gervais, Kaniel & Mingelgrin (2001), The High-Volume Return Premium, Journal of Finance
56(3), 877-919; https://rodneywhitecenter.wharton.upenn.edu/wp-content/uploads/2014/04/9901.pdf
Idea: a burst of trading makes a stock visible to more investors, which raises demand for it and
its price over the following month, whatever direction the burst came with. The earnings-day book
(M0063) found an edge in heavy trading *with* a jump; this asks whether volume alone carries it,
so the price move during the burst is capped to keep it apart from the news-jump book.

On data date d (bar index i of stock s), with window ``k`` (1 = the last day, 5 = the last week):

    * volume ratio   v = mean(volume[i-k+1 .. i]) / median(volume[i-k-base+1 .. i-k]),
                     ``base`` = 49 sessions before the window (GKM's 50-day formation interval);
    * excess return  x = close[i]/close[i-k] - SPY's close ratio on the same two dates.

Inside F4's liquidity and membership screen (and behind its SPY-200 trend switch when
``inner.trend`` is set: all cash while it is off), the scored names are ranked by v. ``side="high"``
keeps the top ``frac`` of them, ``"low"`` the bottom ``frac`` (the control GKM say trails). Among
those, names with |x| < ``move_cap`` (None = no cap) are held, the most extreme v first, up to
``inner.top`` at equal weight 1/top. ``park`` puts the weight the empty slots leave into SPY.
Held names get no special treatment: each month is a fresh pick.

Every piece reads only bars dated <= d.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, N20_NOTREND
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
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

ADDED = date(2026, 10, 10)

Side = Literal["high", "low"]
_SIDES: tuple[str, ...] = ("high", "low")


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class HvpParams:
    """``inner`` is F4's screen, trend switch and book size; the rest defines the volume burst."""

    inner: FactorParams
    side: Side = "high"
    k: int = 5  # sessions in the burst window ending at d
    base: int = 49  # sessions in the normal-volume median, ending the session before the window
    frac: Decimal = Decimal("0.1")  # share of the scored names in the high (or low) volume bucket
    move_cap: Decimal | None = Decimal("0.05")  # |excess return over the window| strictly below this
    park: bool = True  # empty slots hold SPY (while the trend switch, if any, is on)
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not isinstance(self.side, str) or self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")
        for name, low in (("k", 1), ("base", 5)):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < low:
                raise ValueError(f"{name} must be an int >= {low}, got {v!r}")
        if not isinstance(self.frac, Decimal) or not self.frac.is_finite() or not 0 < self.frac <= 1:
            raise ValueError(f"frac must be a Decimal in (0, 1], got {self.frac!r}")
        mc = self.move_cap
        if mc is not None and (not isinstance(mc, Decimal) or not mc.is_finite() or mc <= 0):
            raise ValueError(f"move_cap must be None or a positive Decimal, got {mc!r}")
        if not isinstance(self.park, bool):
            raise TypeError(f"park must be a bool, got {type(self.park).__name__}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "side": self.side,
            "k": str(self.k),
            "base": str(self.base),
            "frac": str(self.frac),
            "move_cap": "none" if self.move_cap is None else str(self.move_cap),
            "park": str(self.park).lower(),
            "market": self.market,
        }
        for key, v in self.inner.as_dict().items():
            out[f"inner.{key}"] = v
        return out


def _check(params: object) -> HvpParams:
    if not isinstance(params, HvpParams):
        raise TypeError(f"params must be HvpParams, got {type(params).__name__}")
    return params


def hvp_lookback(params: HvpParams) -> int:
    return max(factor_lookback(params.inner), params.k + params.base + 1)


# --------------------------------------------------------------------------- the signal


def burst(h: History, market: History | None, data_date: date, p: HvpParams) -> tuple[float, float] | None:
    """(volume ratio, excess return) over the ``k`` sessions ending at ``data_date``, or None."""
    if market is None:
        return None
    i = h.index_of(data_date)
    j = market.index_of(data_date)
    if i is None or j is None or i < p.k + p.base:
        return None
    vol = h.volume
    recent = vol[i - p.k + 1 : i + 1]
    before = vol[i - p.k - p.base + 1 : i - p.k + 1]
    if not (np.all(np.isfinite(recent)) and np.all(np.isfinite(before))):
        return None
    med = float(np.median(before))
    if med <= 0.0:
        return None
    ratio = float(np.mean(recent)) / med
    d0 = h.dates[i - p.k]
    j0 = int(np.searchsorted(market.dates, d0, side="left"))  # the market's bar on the start date
    if j0 >= len(market) or market.dates[j0] != d0:
        return None
    c0, c1 = float(h.close[i - p.k]), float(h.close[i])
    m0, m1 = float(market.close[j0]), float(market.close[j])
    if not (c0 > 0.0 and m0 > 0.0 and math.isfinite(c1) and math.isfinite(m1)):
        return None
    excess = (c1 / c0) - (m1 / m0)
    if not (math.isfinite(ratio) and math.isfinite(excess)):
        return None
    return ratio, excess


def choose(rows: list[FactorRow], history: Mapping[str, History], data_date: date,
           p: HvpParams) -> list[str]:
    market = history.get(p.market)
    scored: list[tuple[float, str, float]] = []
    for r in rows:
        if r.symbol in EXCLUDED or r.symbol == p.market:
            continue
        h = history.get(r.symbol)
        if h is None:
            continue
        b = burst(h, market, data_date, p)
        if b is None:
            continue
        ratio, excess = b
        key = -ratio if p.side == "high" else ratio
        scored.append((key, r.symbol, excess))
    scored.sort(key=lambda t: (t[0], t[1]))
    bucket = scored[: math.ceil(float(p.frac) * len(scored))]
    cap = None if p.move_cap is None else float(p.move_cap)
    kept = [s for _, s, x in bucket if cap is None or abs(x) < cap]
    return kept[: p.inner.top]


def build(chosen: list[str], history: Mapping[str, History], data_date: date,
          p: HvpParams) -> tuple[Target, ...]:
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for s in chosen:
        t = target_from_close(s, last_close(history[s], data_date), w)
        if t is not None:
            out.append(t)
    if p.park:
        rest = Decimal(1) - w * len(out)
        mh = history.get(p.market)
        if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
            t = target_from_close(p.market, last_close(mh, data_date), rest)
            if t is not None:
                out.append(t)
    return tuple(out)


# --------------------------------------------------------------------------- the allocator


@dataclass
class HvpPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)


class HighVolumePremiumAllocator:
    """The members with the most unusual volume burst and a small price move, held for a month."""

    id = "M0071"

    def lookback(self, params: Any) -> int:
        return hvp_lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.market,) if p.park else ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return build(choose(rows, history, data_date, p), history, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> HvpPrepared:
        return HvpPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, HvpPrepared):
            raise TypeError(f"prepared must be HvpPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return build(choose(rows, prepared.history, data_date, p), prepared.history, data_date, p)


HVP = HighVolumePremiumAllocator()


def _v(suffix: str, params: HvpParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0071-{suffix}", family="M0071", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=HVP, params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0071",
    name="The high-volume premium: buy big stocks after a week of unusually heavy trading that did NOT come with a big price move",
    family="stock-volume-visibility",
    source_kind="paper",
    source_ref=(
        "Gervais, Kaniel & Mingelgrin (2001), The High-Volume Return Premium, Journal of Finance "
        "56(3), 877-919; https://rodneywhitecenter.wharton.upenn.edu/wp-content/uploads/2014/04/9901.pdf"
    ),
    parent_id=None,
    hypothesis=(
        "Published 2001 (working paper 1999), so most of the dev window is after the crowd could "
        "trade it; 2009-2015 is judged first. Gervais, Kaniel and Mingelgrin find that a stock "
        "whose trading volume is unusually high against its own last 50 days earns more over the "
        "next month, whatever its return in the burst: the burst makes it visible to more "
        "investors, which raises demand. The earnings-day book found an edge in heavy volume WITH "
        "an up jump; this tests whether volume alone carries it. Each month, inside F4's liquidity "
        "and membership screen, score every member by its mean volume over the last week (or last "
        "day) divided by the median of the 49 sessions before it, keep the top tenth, drop names "
        "whose return over the same window was more than 5 points (3 points for the one-day "
        "window) away from SPY's, and hold the 20 most extreme bursts at 5% each for a month, the "
        "rest in SPY. The ranking is on volume and a near-zero move, not on past returns, so it "
        "should not move like the failed momentum books. Fractional shares at Gotrade's real fees "
        "on monthly-hold-frac-gotrade, the owner's monthly deposits. Variants: WEEK-T (week "
        "window, behind the SPY-200 switch: all cash while SPY is below its 200-day average), "
        "DAY-T (last day only, GKM's own window), WEEK-ALWAYS (no switch: the picking alone), "
        "WEEK-ANYMOVE-T (no move cap: high volume whatever the price did) and LOW-WEEK-T (control: "
        "the LOWEST-volume tenth with the same cap, which GKM say trails). Success: WEEK-T beats "
        "total-return SPY on dev with a worst fall under 20%, beats SPY in 2009-2015, and LOW is "
        "clearly worse."
    ),
    expected_failure=(
        "The premium is small, well under a point a month, and smaller in big stocks; the book "
        "turns over almost completely every month, and at Gotrade's real fees on 5% slots the "
        "round trip may eat most of it. A heavy-volume week with no price move is often a "
        "quarterly index rebalance, an options expiry or a block trade, not new attention, which "
        "would dilute the signal. The SPY-200 switch carries the crash years as it did for every "
        "trend-switched book, so summer 1998 may again push the worst fall past 20%, and "
        "WEEK-ALWAYS should take most of SPY's 2008 fall. If the no-cap version wins clearly and "
        "the capped one doesn't, the edge was the jump, i.e. the earnings-day book again. Equal "
        "weight among index members leans small next to SPY, and SPY's big-company drift beat "
        "every such book after 2018."
    ),
    candidates=(
        _v("WEEK-T", HvpParams(N20),
           "Top tenth by last-week volume burst, |move vs SPY| under 5 points, 20 names, rest SPY, "
           "behind the SPY-200 switch"),
        _v("DAY-T", HvpParams(N20, k=1, move_cap=Decimal("0.03")),
           "GKM's own one-day window: last day's volume vs the 49 before, |move| under 3 points"),
        _v("WEEK-ALWAYS", HvpParams(N20_NOTREND),
           "No switch: the picking alone on top of SPY, always invested"),
        _v("WEEK-ANYMOVE-T", HvpParams(N20, move_cap=None),
           "No move cap: the biggest volume bursts whatever the price did"),
        _v("LOW-WEEK-T", HvpParams(N20, side="low"),
           "Control: the quietest tenth with the same cap, which should trail"),
    ),
    seen_keys=(
        "concept:high-volume-return-premium",
        "concept:volume-visibility",
        "concept:abnormal-volume-no-price-move",
    ),
)
