"""M0170 — Calm big raisers among only the largest companies.

Source: variation of M0088 (its C-LIVE-63 book); reserved by Sera 20261106-1411. The size gate is
the lab's own diagnosis (insight 91: an equal 5% slot per raiser quietly favours mid-sized index
members, and SPY's big-company drift beat every equal-weight book from 2018).
Idea: keep M0088-C-LIVE-63 exactly, and admit a raiser only if its company is among the ``top``
biggest screened index members that day. The picks then come from the same names SPY is heavy in.

The idea row proposed trading value as the size proxy because the store had no market cap. It has
one now (``Market.market_value``, 2026-10-17), so size is real point-in-time market value, and one
arm keeps the trading-value proxy so the two can be told apart:

    * ``measure="value"``: the screened members (F4's ``factor_rows``, SPY and EXCLUDED out) with
      a known market value, one class per company -- members answering the identical share count
      are one company and the class with the larger 20-day dollar volume stands for it, as M0222
      does -- ranked by market value, largest first, ties by symbol. A member with no value is
      not ranked, so it is never "big" and never "small".
    * ``measure="dollar_volume"``: the same screened members ranked by their 20-day mean
      close x volume (``FactorRow.dollar_volume``), largest first, ties by symbol. No dedupe:
      every row has a dollar volume.
    * ``side="in"`` admits a raiser ranked within the first ``top``; ``side="out"`` admits a raiser
      that is ranked but outside the first ``top`` (the mirror: if it matches "in", size does not
      matter); ``top=None`` is no gate at all and takes M0088's ``choose`` verbatim, so the control
      is M0088-C-LIVE-63 bit for bit.

The gate runs **after** M0088's calm filter, whose median is still taken over every live raiser,
so a gated book is always a subset of the control's eligible list and the only thing that differs
is which raisers are let in. It applies to held names too: a holding that falls out of the top is
sold at the next re-pick. Held names first, then the newest event, up to 20 at 5%, rest in SPY,
monthly, fractional at Gotrade's real fees, behind F4's SPY-200 switch.
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
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.lab.method import Method
from seer_engine.lab.methods import m0088_calm_big_raisers as m0088
from seer_engine.lab.methods.m0070_dividend_raise_drift import _first_bar, live_event
from seer_engine.lab.methods.m0076_dividend_raise_on_announcement import events
from seer_engine.lab.methods.m0088_calm_big_raisers import X, CalmParams, admits, swing
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 6)

Measure = Literal["value", "dollar_volume"]
Side = Literal["in", "out"]
_MEASURES: tuple[str, ...] = ("value", "dollar_volume")
_SIDES: tuple[str, ...] = ("in", "out")


@dataclass(frozen=True, slots=True)
class SizeParams:
    """``calm`` is M0088's book and filter; ``top``/``measure``/``side`` the size gate."""

    calm: CalmParams
    top: int | None = None
    measure: Measure = "value"
    side: Side = "in"

    def __post_init__(self) -> None:
        if not isinstance(self.calm, CalmParams):
            raise TypeError(f"calm must be CalmParams, got {type(self.calm).__name__}")
        if self.top is not None and (isinstance(self.top, bool) or not isinstance(self.top, int)
                                     or self.top < 1):
            raise ValueError(f"top must be a positive int or None, got {self.top!r}")
        if not isinstance(self.measure, str) or self.measure not in _MEASURES:
            raise ValueError(f"measure must be one of {_MEASURES}, got {self.measure!r}")
        if not isinstance(self.side, str) or self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"top": "none" if self.top is None else str(self.top), "measure": self.measure,
               "side": self.side}
        for k, v in self.calm.as_dict().items():
            out[f"calm.{k}"] = v
        return out


def _check(params: object) -> SizeParams:
    if not isinstance(params, SizeParams):
        raise TypeError(f"params must be SizeParams, got {type(params).__name__}")
    return params


@dataclass
class SizePrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared | None = field(repr=False)
    calendar: DividendCalendar = field(repr=False)
    market: Any = field(repr=False, default=None)


def ranked(rows: list[FactorRow], market: Any, data_date: date, measure: str,
           exclude: str) -> list[str]:
    """The screened members largest first by ``measure``; unranked members are left out."""
    if measure == "dollar_volume":
        keyed = [(r.dollar_volume, r.symbol) for r in rows
                 if r.symbol not in EXCLUDED and r.symbol != exclude and math.isfinite(r.dollar_volume)]
        return [s for _, s in sorted(keyed, key=lambda t: (-t[0], t[1]))]
    if market is None:
        return []
    best: dict[float, tuple[float, str, float]] = {}
    for r in rows:
        if r.symbol in EXCLUDED or r.symbol == exclude:
            continue
        shares = market.shares_on(r.symbol, data_date)
        value = market.market_value(r.symbol, data_date)
        if shares is None or value is None or not (value > 0 and math.isfinite(value)):
            continue
        row = (r.dollar_volume, r.symbol, value)
        seen = best.get(shares)
        if seen is None or (row[0], row[1]) > (seen[0], seen[1]):
            best[shares] = row
    return [s for _, s, _ in sorted(best.values(), key=lambda t: (-t[2], t[1]))]


def choose(history: Mapping[str, History], rows: list[FactorRow], calendar: DividendCalendar,
           market: Any, data_date: date, held: frozenset[str], p: SizeParams) -> tuple[Target, ...]:
    c = p.calm
    if p.top is None:
        return m0088.choose(history, rows, calendar, data_date, held, c)
    a = c.ann
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
    if c.side != "none":  # M0088's calm filter, its cut over every live raiser
        vols = {t[2]: swing(history.get(t[2]), data_date, c.vol_n) for t in live}
        if c.pool == "live":
            swings = list(vols.values())
        else:
            swings = [vols[r.symbol] if r.symbol in vols else swing(history.get(r.symbol), data_date, c.vol_n)
                      for r in rows if r.symbol not in EXCLUDED and r.symbol != b.market]
        pool = [v for v in swings if v is not None]
        cut = float(np.median(pool)) if pool else None
        live = [t for t in live if admits(vols[t[2]], cut, c.side)]
    order = ranked(rows, market, data_date, p.measure, b.market)
    big = set(order[: p.top])
    if p.side == "in":
        live = [t for t in live if t[2] in big]
    else:
        small = set(order[p.top:])
        live = [t for t in live if t[2] in small]
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


class LargestRaiseAllocator:
    """M0088's calm big raisers, admitted only from the biggest screened index members."""

    id = "M0170"
    market_fields = ("dividends", "shares")

    def lookback(self, params: Any) -> int:
        c = _check(params).calm
        return max(factor_lookback(c.ann.base.inner), c.vol_n + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        b = _check(params).calm.ann.base
        fixed = {b.market}
        if b.inner.trend is not None:
            fixed.add(b.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        b = _check(params).calm.ann.base
        return (b.market,) if b.park else ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: SizePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SizeParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
            return ()
        inner = p.calm.ann.base.inner
        if not trend_on(prepared.history, data_date, inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, inner)
        return choose(prepared.history, rows, prepared.calendar, prepared.market, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar, so no event and no target."""
        return self._run(SizePrepared(history, None, EMPTY_DIVIDENDS), members, data_date, held,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> SizePrepared:
        return SizePrepared(history, prepare_factor(history), EMPTY_DIVIDENDS)

    def prepare_market(self, market: Any) -> SizePrepared:
        calendar = getattr(market, "dividends", EMPTY_DIVIDENDS)
        if not isinstance(calendar, DividendCalendar):
            raise TypeError(f"market.dividends must be a DividendCalendar, got {type(calendar).__name__}")
        return SizePrepared(market.history, prepare_factor(market.history), calendar, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SizePrepared):
            raise TypeError(f"prepared must be SizePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


LARGEST = LargestRaiseAllocator()
C63 = CalmParams(X, "calm", "live", 63)  # M0088-C-LIVE-63's book and filter


def _v(suffix: str, params: SizeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0170-{suffix}", family="M0170", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=LARGEST, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0170",
    name="Big dividend raisers among only the largest companies: the raise signal without the small-company tilt",
    family="stock-dividend-change-drift",
    source_kind="variation",
    source_ref=(
        "variation of M0088 (C-LIVE-63); Michaely, Thaler & Womack (1995), JF 50(2) for the "
        "dividend-change drift; the lab's insight 91 (equal slots favour mid-sized members) and "
        "M0222 for point-in-time market value with one class per company"
    ),
    parent_id="M0088",
    hypothesis=(
        "Published 1995 (dividend-change drift), so the dev window is after the crowd knew it. "
        "M0088-C-LIVE-63 (big dividend raisers seen on the ex-date, held while the raise is under "
        "182 days old, only those whose 63-session daily swing is at or below the live raisers' "
        "median, up to 20 F4-screened members at 5%, held names first then the newest event, rest "
        "in SPY, monthly, behind the SPY-200 switch, fractional at Gotrade's real fees on the "
        "owner's deposits) beats SPY on dev but every tune of it left a lag behind SPY in "
        "2009-2015 and won only 2 of 4 walk-forward folds. The lab's money runs say SPY's "
        "big-company drift beat every equal-weight book from 2018 (insight 91), and a 5% slot per "
        "raiser favours mid-sized members over the giants SPY is heavy in. Admit a raiser only if "
        "its company is among the biggest screened index members that day; the gate runs after "
        "the calm filter (whose median is unchanged), applies to held names too, and the freed "
        "slots go to SPY as before. Size is real point-in-time market value (shares as filed x "
        "the close as printed, one class per company), which the idea row did not have; one arm "
        "keeps its trading-value proxy. Market value exists only from 1996, so the value arms sit "
        "in SPY before then; that is assumed harmless because the switch and SPY park dominate "
        "1993-1995 in every arm. Variants: CTRL no gate (must reproduce M0088-C-LIVE-63 bit for "
        "bit); V50, V100, V150 the 50, 100, 150 largest by market value; V100-OUT raisers ranked "
        "outside the 100 largest (the mirror: if it matches V100, size does not matter; CTRL is "
        "the arm with no size opinion); D100 the 100 largest by 20-day trading value (the idea "
        "row's proxy). Success: a gated arm at or above CTRL's funded return with a worst fall at "
        "or under the bar, a positive or smaller 2009-2015 gap to SPY, a majority of walk-forward "
        "folds, and V100 beating V100-OUT in 2009-2015."
    ),
    expected_failure=(
        "The largest companies seldom raise their dividend by 25% or more, so a gated book holds "
        "a handful of names and sits mostly in SPY: it converges on SPY behind the switch, the "
        "edge shrinks with the gap, and the trade count may fall toward the 100-trade floor at "
        "V50. The 2009-2015 lag was diagnosed as the switch selling into the 2010, 2011 and 2015 "
        "dips (M0096), which no pick filter touches, so the fold record likely stays 2 of 4. The "
        "raise drift may live in the mid-sized names (smaller firms' raises carry more news), so "
        "V100-OUT could beat V100 on the twenty-year average while V100 merely ties SPY. A widely "
        "published anomaly from the 1990s: even a real dev edge is likely to fade after 2015. "
        "Survivorship flatters dividend books, less so among the largest; withholding tax on "
        "dividends is not modelled."
    ),
    candidates=(
        _v("CTRL", SizeParams(C63), "Paired control: no size gate (= M0088-C-LIVE-63)"),
        _v("V50", SizeParams(C63, 50), "Raisers among the 50 largest screened companies by market value"),
        _v("V100", SizeParams(C63, 100), "Raisers among the 100 largest by market value"),
        _v("V150", SizeParams(C63, 150), "Raisers among the 150 largest by market value"),
        _v("V100-OUT", SizeParams(C63, 100, "value", "out"),
           "Mirror: raisers ranked outside the 100 largest by market value"),
        _v("D100", SizeParams(C63, 100, "dollar_volume"),
           "Raisers among the 100 most-traded screened members (the trading-value proxy)"),
    ),
    seen_keys=(
        "concept:dividend-increase-drift",
        "concept:dividend-change",
        "concept:low-volatility-filter",
        "concept:largest-companies-only",
    ),
)
