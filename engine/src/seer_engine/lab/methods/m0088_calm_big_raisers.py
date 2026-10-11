"""M0088 — Calm big raisers: the big-dividend-raise book keeping only the steadier half of its raisers.

Source: variation of M0070 (its book as M0076-X-M, the ex-date timing); Michaely, Thaler & Womack
(1995), JF 50(2) for the drift; Ang, Hodrick, Xing & Zhang (2006), JF 61(1) and Baker, Bradley &
Wurgler (2011) for "calm stocks fall less".
Idea: the big-raise book beats SPY on the deposits but fails only on its worst fall (21.9%, the
1998-2002 fast falls before the SPY-200 switch turns). Keep its event, hold and ranking, and on each
re-pick drop the raisers whose recent daily swing is above a median, parking their 5% slots in SPY.

M0076's event logic (``events`` / ``live_event``) runs unchanged with ``timing="ex"``. The filter
reads one number per symbol on ``data_date``:

    * ``vol`` = population stdev of the last ``vol_n`` one-bar close-to-close returns, closes
      dated <= ``data_date`` (split-adjusted, not dividend-adjusted, as the store holds them);
      a symbol with fewer than ``vol_n + 1`` bars, or a non-finite value, has no vol and is
      never admitted by a filtered variant.
    * ``cut`` = the median vol of the pool: ``pool="live"`` the raisers live on ``data_date``
      (after the declared-only test, before the 20-name cap), ``pool="all"`` every F4-screened
      member on ``data_date`` (SPY excluded). Members without a vol do not enter the pool.
    * ``side="calm"`` admits vol <= cut, ``side="jumpy"`` vol > cut (the control that asks
      whether the swing matters at all); ``side="none"`` admits every raiser (the host).

The filter applies to held names too, so a holding that turns jumpy is sold at the next re-pick.
Everything else is M0070's: F4's member screen and SPY-200 switch, up to 20 names at 5% while the
event is under 182 days old, held names first then the newest event, rest in SPY, monthly,
fractional shares at Gotrade's real fees.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import RaisePrepared, _first_bar, live_event
from seer_engine.lab.methods.m0076_dividend_raise_on_announcement import R25, AnnParams, events
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 11)

Side = Literal["none", "calm", "jumpy"]
Pool = Literal["live", "all"]
_SIDES: tuple[str, ...] = ("none", "calm", "jumpy")
_POOLS: tuple[str, ...] = ("live", "all")


@dataclass(frozen=True, slots=True)
class CalmParams:
    """``ann`` is M0076's book and timing; the rest is the swing filter."""

    ann: AnnParams
    side: Side = "calm"
    pool: Pool = "live"
    vol_n: int = 126

    def __post_init__(self) -> None:
        if not isinstance(self.ann, AnnParams):
            raise TypeError(f"ann must be AnnParams, got {type(self.ann).__name__}")
        if not isinstance(self.side, str) or self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")
        if not isinstance(self.pool, str) or self.pool not in _POOLS:
            raise ValueError(f"pool must be one of {_POOLS}, got {self.pool!r}")
        if isinstance(self.vol_n, bool) or not isinstance(self.vol_n, int) or self.vol_n < 20:
            raise ValueError(f"vol_n must be an int >= 20, got {self.vol_n!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "pool": self.pool, "vol_n": str(self.vol_n)}
        for k, v in self.ann.as_dict().items():
            out[f"ann.{k}"] = v
        return out


def _check(params: object) -> CalmParams:
    if not isinstance(params, CalmParams):
        raise TypeError(f"params must be CalmParams, got {type(params).__name__}")
    return params


def swing(h: History | None, data_date: date, n: int) -> float | None:
    """Population stdev of the last ``n`` one-bar returns of ``h`` through ``data_date``, or None."""
    if h is None:
        return None
    k = int(np.searchsorted(h.dates, as_day(data_date), side="right"))
    if k < n + 1:
        return None
    c = np.asarray(h.close[k - n - 1:k], dtype=float)
    if not np.all(np.isfinite(c)) or np.any(c <= 0):
        return None
    out = float(np.std(c[1:] / c[:-1] - 1.0))
    return out if np.isfinite(out) else None


def admits(v: float | None, cut: float | None, side: str) -> bool:
    if side == "none":
        return True
    if v is None or cut is None:
        return False
    return v <= cut if side == "calm" else v > cut


def choose(history: Mapping[str, History], rows: list[FactorRow], calendar: DividendCalendar,
           data_date: date, held: frozenset[str], p: CalmParams) -> tuple[Target, ...]:
    a = p.ann
    b = a.base
    live: list[tuple[int, int, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED or r.symbol == b.market:
            continue
        paid, declared = events(calendar, r.symbol, data_date, a.timing)
        if a.declared_only and not declared:
            continue
        e = live_event(paid, _first_bar(history.get(r.symbol)), data_date, b)
        if e is None:
            continue
        live.append((0 if r.symbol in held else 1, -e.toordinal(), r.symbol, r))
    if p.side != "none":
        vols = {t[2]: swing(history.get(t[2]), data_date, p.vol_n) for t in live}
        if p.pool == "live":
            swings = list(vols.values())
        else:
            swings = [vols[r.symbol] if r.symbol in vols else swing(history.get(r.symbol), data_date, p.vol_n)
                      for r in rows if r.symbol not in EXCLUDED and r.symbol != b.market]
        pool = [v for v in swings if v is not None]
        cut = float(np.median(pool)) if pool else None
        live = [t for t in live if admits(vols[t[2]], cut, p.side)]
    live.sort(key=lambda t: (t[0], t[1], t[2]))
    w = equal_weight(b.inner.top)
    out: list[Target] = []
    for _, _, _, r in live[: b.inner.top]:
        t = target_from_close(r.symbol, r.close, w)
        if t is not None:
            out.append(t)
    if b.park:
        rest = Decimal(1) - w * len(out)
        mh = history.get(b.market)
        if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
            t = target_from_close(b.market, last_close(mh, data_date), rest)
            if t is not None:
                out.append(t)
    return tuple(out)


class CalmRaiseAllocator:
    """M0070's big-raise book, keeping only the raisers on one side of a median daily swing."""

    id = "M0088"
    market_fields = ("dividends",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(factor_lookback(p.ann.base.inner), p.vol_n + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        b = _check(params).ann.base
        fixed = {b.market}
        if b.inner.trend is not None:
            fixed.add(b.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        b = _check(params).ann.base
        return (b.market,) if b.park else ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: RaisePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: CalmParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
            return ()
        inner = p.ann.base.inner
        if not trend_on(prepared.history, data_date, inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, inner)
        return choose(prepared.history, rows, prepared.calendar, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar, so no event and no target."""
        return self._run(RaisePrepared(history, None, EMPTY_DIVIDENDS), members, data_date, held,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> RaisePrepared:
        return RaisePrepared(history, prepare_factor(history), EMPTY_DIVIDENDS)

    def prepare_market(self, market: Any) -> RaisePrepared:
        calendar = getattr(market, "dividends", EMPTY_DIVIDENDS)
        if not isinstance(calendar, DividendCalendar):
            raise TypeError(f"market.dividends must be a DividendCalendar, got {type(calendar).__name__}")
        return RaisePrepared(market.history, prepare_factor(market.history), calendar)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, RaisePrepared):
            raise TypeError(f"prepared must be RaisePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


CALM = CalmRaiseAllocator()
X = AnnParams(R25, "ex")  # M0076-X-M's event, timing and book (= M0070-R25-H6-T)


def _v(suffix: str, params: CalmParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0088-{suffix}", family="M0088", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CALM, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0088",
    name="Calm big raisers: the big-dividend-raise book keeping only the steadier half of the raisers, to pull its worst fall under 20%",
    family="stock-dividend-change-drift",
    source_kind="variation",
    source_ref=(
        "variation of M0070 (R25-H6-T, re-run as M0076-X-M); Michaely, Thaler & Womack (1995), "
        "JF 50(2); low-volatility anomaly: Ang, Hodrick, Xing & Zhang (2006), JF 61(1); Baker, "
        "Bradley & Wurgler (2011), FAJ 67(1)"
    ),
    parent_id="M0070",
    hypothesis=(
        "Published 1995 (dividend-change drift) and 2006 (low volatility), so most of the dev "
        "window is after the crowd knew the drift and half of it before the calm-stock idea was "
        "widely traded. M0070's big-raise book (latest dividend >= 25% over the median of up to "
        "four prior payments in 400 days and at most double, or a first payment, seen on its "
        "ex-date; up to 20 F4-screened members at 5% while the event is under 182 days old, held "
        "names first then the newest event, rest in SPY, monthly, behind the SPY-200 switch, "
        "fractional at Gotrade's real fees) beats SPY by about 3.7 points a year on the deposits "
        "(+10.9% vs +7.2%) and fails only on its worst fall (21.9%), with a weak 2009-2015. The "
        "raisers that swing most are the ones that dragged the 1998-2002 falls; a raiser that is "
        "also calm should keep the drift and lose less. On each monthly re-pick, measure every "
        "live raiser's daily swing (population stdev of its last 126 close-to-close returns) and "
        "keep only those at or below a median, held names included; the freed 5% slots go to "
        "SPY. Variants: X-M the host unchanged (paired control; must reproduce M0076-X-M: 540 "
        "trades, 21.9% worst fall); C-LIVE calm half of the live raisers (the idea); J-LIVE the "
        "jumpy half (control: if it matches C-LIVE, the swing does not matter); C-ALL raisers "
        "calmer than the median F4-screened member, a fixed market-wide bar so the filter "
        "tightens when the raisers as a group are jumpy; C-LIVE-63 the calm half on a 63-session "
        "swing, which reacts faster into a fall. It ranks on dividend raises, filtered by "
        "swing, so the family stays dividend-change-drift. Success: C-LIVE's worst fall under "
        "20% with funded CAGR still above SPY's, and C-LIVE beats J-LIVE on worst fall."
    ),
    expected_failure=(
        "The calm half is mostly utilities, staples and old industrials; they lagged in "
        "2009-2015 when big-company growth led, so the worst fall shrinks but the 2009-2015 gap "
        "to SPY widens. Halving the live raisers leaves more of the book in SPY, so the result "
        "may simply converge on SPY: a smaller fall and a smaller edge, and the fall that is "
        "left is SPY's own fall before the 200-day switch turns (the switch, not the picks, "
        "sets the floor). Monthly re-checking held names against a moving median adds turnover "
        "at Gotrade's fees on 5% slots. The 1998-2002 falls may have come from the SPY part of "
        "the book rather than the jumpy raisers. A widely published anomaly from the 1990s: "
        "even a real dev edge is likely to fade after 2015. Withholding tax on dividends is not "
        "modelled."
    ),
    candidates=(
        _v("X-M", CalmParams(X, "none"),
           "Paired control: the big-raise book unchanged (should reproduce M0076-X-M)"),
        _v("C-LIVE", CalmParams(X, "calm", "live"),
           "Keep the raisers whose 126-session daily swing is at or below the live raisers' median"),
        _v("J-LIVE", CalmParams(X, "jumpy", "live"),
           "Control: keep only the jumpier half of the live raisers"),
        _v("C-ALL", CalmParams(X, "calm", "all"),
           "Keep the raisers calmer than the median screened index member"),
        _v("C-LIVE-63", CalmParams(X, "calm", "live", 63),
           "Calm half of the live raisers on a faster 63-session swing"),
    ),
    seen_keys=(
        "concept:dividend-increase-drift",
        "concept:dividend-change",
        "concept:low-volatility-filter",
        "nber:w4778",
    ),
)
