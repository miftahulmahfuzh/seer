"""M0627 — Stocks that often don't trade: the share of zero-return days in the past year as a pick score.

Source: Lesmond, Ogden & Trzcinka (1999), "A New Estimate of Transaction Costs", Review of
Financial Studies 12(5), 1113-1141. Their price-only liquidity proxy is the share of trading days
on which the close did not move: a stock whose cost of trading exceeds what news is worth does
not trade at all that day, so its price stands still. Bekaert, Harvey & Lundblad (2007) use the
same count as a liquidity-premium variable.

The frame is M0058's -- point-in-time S&P 500 / Nasdaq-100 members, the $5 price floor, the
20M-dollar volume floor removed, the SPY 200-day gate, monthly, equal weight, fractional shares
at Gotrade's real fees on ``monthly-hold-frac-gotrade`` -- so the only new thing is the ranking key:

    zr(s) = (bar pairs in the last ``n`` with an unchanged close) / (usable bar pairs)

a usable pair has finite positive closes and positive volume (a day nothing traded is not a
"traded but unmoved" day), and a name needs ``MIN_FRAC`` of the window usable. What this sees
that M0058 / M0309 did not: Amihud divides the move by dollars, so it needs volume to be right
and rewards big moves; a zero count reads only whether the price moved at all, and is blind to
size. A name with zero or one still days a year is scored the same as another, so ties are
broken by a hash of symbol and date, which holds no opinion (never alphabetical).

Measured before writing (store bars, 1993 -> 2015-10-16, all symbols): the median stock-year
share of unchanged closes is 12% in 1993, 10% in 1996, 3% in 1999 and about 0.8% from 2002 on,
the 90th percentile 2% from 2002; a handful of stock-years read 60-100% (stale or broken
prices, the M0309 trap). So for index members the zero share is a pre-decimalization (before
April 2001) low-price artefact more than a liquidity reading, and thereafter a thin tail of a
few names. ``max_share`` drops names above 50% as broken data. Reads only bars <= d.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
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
    trend_on,
)

ADDED = date(2026, 11, 13)
MIN_FRAC = 0.8  # share of the window that must be usable bar pairs
FLAT_EPS = 1e-9  # |close/prev - 1| below this is an unchanged close

Side = Literal["most", "fewest", "random"]
_SIDES: tuple[str, ...] = ("most", "fewest", "random")


@dataclass(frozen=True, slots=True)
class ZeroParams:
    """``inner`` is F4's screen, gate, book size and weights; the rest is the ranking."""

    inner: FactorParams
    side: Side = "most"
    n: int = 250
    max_share: float = 0.5

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not isinstance(self.side, str) or self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")
        if isinstance(self.n, bool) or not isinstance(self.n, int):
            raise TypeError(f"n must be an int, got {type(self.n).__name__}")
        if self.n < 20:
            raise ValueError(f"n must be >= 20, got {self.n}")
        if not 0.0 < self.max_share <= 1.0:
            raise ValueError(f"max_share must be in (0, 1], got {self.max_share}")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "n": str(self.n), "max_share": repr(self.max_share)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> ZeroParams:
    if not isinstance(params, ZeroParams):
        raise TypeError(f"params must be ZeroParams, got {type(params).__name__}")
    return params


def zero_lookback(params: ZeroParams) -> int:
    return max(factor_lookback(params.inner), params.n + 1)


def zero_share(h: History, data_date: date, n: int) -> float | None:
    """Share of usable bar pairs in the ``n`` ending at ``data_date`` whose close did not move."""
    i = h.index_of(data_date)
    if i is None or i < n:
        return None
    c = h.close[i - n : i + 1]
    v = h.volume[i - n + 1 : i + 1]
    prev, cur = c[:-1], c[1:]
    ok = np.isfinite(prev) & np.isfinite(cur) & np.isfinite(v) & (prev > 0.0) & (cur > 0.0) & (v > 0.0)
    m = int(ok.sum())
    if m < max(3, math.ceil(MIN_FRAC * n)):
        return None
    flat = np.abs(cur[ok] / prev[ok] - 1.0) < FLAT_EPS
    return float(flat.sum()) / m


def _coin(symbol: str, data_date: date) -> float:
    """A reproducible no-opinion number in [0, 1) from the symbol and the date."""
    digest = hashlib.blake2b(f"{symbol}|{data_date.isoformat()}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") / 2**64


def choose(rows: list[FactorRow], history: Mapping[str, History], data_date: date,
           params: ZeroParams) -> list[FactorRow]:
    scored: list[tuple[float, float, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED:
            continue
        h = history.get(r.symbol)
        if h is None:
            continue
        x = zero_share(h, data_date, params.n)
        if x is None or x > params.max_share:
            continue
        coin = _coin(r.symbol, data_date)
        if params.side == "most":
            key = -x
        elif params.side == "fewest":
            key = x
        else:
            key = 0.0  # the control ranks on the hash alone
        scored.append((key, coin, r.symbol, r))
    scored.sort(key=lambda t: (t[0], t[1], t[2]))
    return [r for _, _, _, r in scored[: params.inner.top]]


def targets_from_rows(chosen: list[FactorRow], params: ZeroParams) -> tuple[Target, ...]:
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, params.inner), strict=True):
        if weight is None:
            continue
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


@dataclass
class ZeroPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)


class ZeroReturnAllocator:
    """F4's book without the volume floor, ranked on the share of unchanged closes.

    Held symbols get no special treatment: a name that leaves the top set is signal-exited.
    """

    id = "M0627"

    def lookback(self, params: Any) -> int:
        return zero_lookback(_check(params))

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
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return targets_from_rows(choose(rows, history, data_date, p), p)

    def prepare(self, history: Mapping[str, History]) -> ZeroPrepared:
        return ZeroPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ZeroPrepared):
            raise TypeError(f"prepared must be ZeroPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return targets_from_rows(choose(rows, prepared.history, data_date, p), p)


ZERO = ZeroReturnAllocator()

OPEN20 = replace(N20, min_dollar_volume=0.0)  # F4's screen without the volume floor
OPEN20_NOTREND = replace(OPEN20, trend=None)


def _v(suffix: str, params: ZeroParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0627-{suffix}", family="M0627", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=ZERO, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0627",
    name="Stocks that often don't trade: the share of zero-return days in the past year as a pick score",
    family="stock-zero-return-days",
    source_kind="paper",
    source_ref=(
        "Lesmond, Ogden & Trzcinka (1999), A New Estimate of Transaction Costs, "
        "Review of Financial Studies 12(5), 1113-1141"
    ),
    parent_id=None,
    hypothesis=(
        "A day with an unchanged close is the classic price-only sign that a stock is too thin or "
        "too costly to trade (Lesmond-Ogden-Trzcinka 1999; Bekaert-Harvey-Lundblad 2007 use it as a "
        "liquidity-premium variable), so stocks with many such days should earn a premium the owner "
        "never pays. Each month, among point-in-time S&P 500 / Nasdaq-100 members priced at $5 or "
        "more (M0058's frame: no volume floor), rank on the share of the last 250 usable bar pairs "
        "whose close did not move (volume positive; names above 50% dropped as broken data) and hold "
        "20, equal weight, fractional shares at Gotrade's real fees on monthly-hold-frac-gotrade. "
        "What a zero count sees that the Amihud books (M0058, M0309) did not: it reads whether the "
        "price moved at all, not how far per dollar, so it needs no trustworthy volume and does not "
        "reward big movers. Measured first: index members have almost no zero days after 2001 "
        "(median stock-year about 0.8%), 10-12% in 1993-1996 (fractional ticks), so the score may "
        "mostly sort by price level and era; ties are broken by a symbol-date hash, never "
        "alphabetically. Six arms, a 2x2 per side with the gate as the habit: MOST20-T and "
        "FEW20-T (the mirror pair behind the SPY 200-day gate), RAND20-T (control: the same book, "
        "hash-picked, no opinion, behind the gate), and MOST20, FEW20, RAND20 (the same three "
        "never stepping aside). The random arms are fresh hash draws, not repeats of a recorded "
        "book, and are run, not cited. Success: MOST beats SPY TR on dev inside the drawdown limit, "
        "FEW and RAND do worse, and the edge holds in 2009-2015."
    ),
    expected_failure=(
        "Zero-return share is a 1993-2000 artefact (fractional ticks, low-priced stocks), so MOST "
        "picks cheap stocks of the pre-decimal era and nothing in 2002-2015, where the 20 'most' "
        "names are a few days apart from the rest and the ranking is near noise. Then MOST, FEW "
        "and RAND land together after 2001 and the verdict is that the idea is blind in the era "
        "that matters. If MOST does win it is likely the small-company bet M0058 turned out to be, "
        "and the survivorship gap flatters it. Published 1999: the anomaly has had time to fade."
    ),
    candidates=(
        _v("MOST20-T", ZeroParams(OPEN20, side="most"),
           "The 20 members with the largest share of unchanged closes, behind the SPY 200-day gate"),
        _v("FEW20-T", ZeroParams(OPEN20, side="fewest"),
           "Mirror: the 20 with the fewest unchanged closes, behind the gate (hash tie-break)"),
        _v("RAND20-T", ZeroParams(OPEN20, side="random"),
           "Control: 20 hash-picked members, no opinion, behind the gate; a fresh draw, not a recorded book"),
        _v("MOST20", ZeroParams(OPEN20_NOTREND, side="most"),
           "The 20 most-unchanged-close names, always invested: prices the gate"),
        _v("FEW20", ZeroParams(OPEN20_NOTREND, side="fewest"),
           "The 20 fewest-unchanged-close names, always invested"),
        _v("RAND20", ZeroParams(OPEN20_NOTREND, side="random"),
           "Control: 20 hash-picked members never stepping aside: the no-opinion book, fresh draw"),
    ),
    seen_keys=(
        "concept:zero-return-days",
        "concept:lesmond-liquidity-proxy",
        "paper:lesmond-ogden-trzcinka-1999",
    ),
)
