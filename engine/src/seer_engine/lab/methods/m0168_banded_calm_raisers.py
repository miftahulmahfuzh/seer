"""M0168 — Calm big raisers held until they fall well out of the calm band.

Source: variation of M0088 (its C-LIVE-63 picks); the buy/hold band as a cost cure is Novy-Marx &
Velikov (2016), RFS 29(1), and M0163 priced it in this lab at +1.7 points a year on a yearly
yield book.
Idea: M0088-C-LIVE-63 re-checks every held raiser against the live raisers' median 63-session swing
each month and sells the ones that drifted above it. A name a hair either side of a moving median
churns in and out at Gotrade's fees on a 5% slot, with no change in the signal. Keep the entry bar
exactly (swing at or below the median), but let a held name stay until its swing passes a higher
quantile of the same pool, or never re-check it at all.

Everything is M0088's ``choose`` except the bar a held name is judged against:

    * ``cut_in``   = the median swing of the pool (M0088's ``cut``, computed with ``np.median``);
      a name not held is admitted at swing <= cut_in, exactly as in M0088.
    * ``keep_q``   = the quantile of the same pool a held name must stay at or below
      (``np.quantile``, linear). ``keep_q=None`` admits every held raiser whatever its swing, so
      a holding leaves only when its raise is 182 days old, it stops being a screened member, or
      the SPY-200 switch empties the book.
    * ``keep_q=0.5`` is not computed through ``np.quantile``: it takes the M0088 path verbatim
      (one cut for everyone), so the control is M0088-C-LIVE-63 bit for bit.

Held names first, then the newest event, up to 20 at 5%, rest in SPY, monthly, fractional at
Gotrade's real fees, behind F4's SPY-200 switch.
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
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import RaisePrepared, _first_bar, live_event
from seer_engine.lab.methods.m0076_dividend_raise_on_announcement import events
from seer_engine.lab.methods.m0088_calm_big_raisers import X, CalmParams, admits, swing
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 17)


@dataclass(frozen=True, slots=True)
class BandParams:
    """``calm`` is M0088's book and filter (calm side, live pool); ``keep_q`` the held names' bar."""

    calm: CalmParams
    keep_q: float | None = 0.5

    def __post_init__(self) -> None:
        if not isinstance(self.calm, CalmParams):
            raise TypeError(f"calm must be CalmParams, got {type(self.calm).__name__}")
        if self.calm.side != "calm" or self.calm.pool != "live":
            raise ValueError("M0168 bands the calm half of the live raisers only")
        if self.keep_q is not None:
            if isinstance(self.keep_q, bool) or not isinstance(self.keep_q, float):
                raise TypeError(f"keep_q must be a float or None, got {self.keep_q!r}")
            if not 0.5 <= self.keep_q <= 1.0:
                raise ValueError(f"keep_q must be in [0.5, 1.0], got {self.keep_q!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"keep_q": "none" if self.keep_q is None else repr(self.keep_q)}
        for k, v in self.calm.as_dict().items():
            out[f"calm.{k}"] = v
        return out


def _check(params: object) -> BandParams:
    if not isinstance(params, BandParams):
        raise TypeError(f"params must be BandParams, got {type(params).__name__}")
    return params


def choose(history: Mapping[str, History], rows: list[FactorRow], calendar: DividendCalendar,
           data_date: date, held: frozenset[str], p: BandParams) -> tuple[Target, ...]:
    c = p.calm
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
    vols = {t[2]: swing(history.get(t[2]), data_date, c.vol_n) for t in live}
    pool = [v for v in vols.values() if v is not None]
    cut_in = float(np.median(pool)) if pool else None
    if p.keep_q == 0.5:
        live = [t for t in live if admits(vols[t[2]], cut_in, "calm")]
    else:
        cut_keep = float(np.quantile(pool, p.keep_q)) if pool and p.keep_q is not None else None
        kept: list[tuple[int, int, str, FactorRow]] = []
        for t in live:
            if t[0] == 0:
                ok = p.keep_q is None or admits(vols[t[2]], cut_keep, "calm")
            else:
                ok = admits(vols[t[2]], cut_in, "calm")
            if ok:
                kept.append(t)
        live = kept
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


class BandedCalmRaiseAllocator:
    """M0088's calm big raisers, with a wider swing bar for names already held."""

    id = "M0168"
    market_fields = ("dividends",)

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

    def _run(self, prepared: RaisePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: BandParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
            return ()
        inner = p.calm.ann.base.inner
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


BANDED = BandedCalmRaiseAllocator()
C63 = CalmParams(X, "calm", "live", 63)  # M0088-C-LIVE-63's book and filter


def _v(suffix: str, keep_q: float | None, rationale: str) -> Candidate:
    return Candidate(id=f"M0168-{suffix}", family="M0168", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BANDED, params=BandParams(C63, keep_q), rationale=rationale,
                     added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0168",
    name="Calm big dividend raisers held until they fall well out of the book: the stay-in-the-band rule on the lab's cleanest monthly book",
    family="stock-dividend-change-drift",
    source_kind="variation",
    source_ref=(
        "variation of M0088 (C-LIVE-63); buy/hold band as a cost cure: Novy-Marx & Velikov (2016), "
        "A Taxonomy of Anomalies and Their Trading Costs, RFS 29(1); priced in this lab by M0163; "
        "Michaely, Thaler & Womack (1995), JF 50(2)"
    ),
    parent_id="M0088",
    hypothesis=(
        "Published 1995 (dividend-change drift), 2006 (low volatility) and 2016 (the band as a cost "
        "cure), so the band itself is after the dev window and the signal is not. M0088-C-LIVE-63 "
        "(big dividend raisers seen on the ex-date, held while the raise is under 182 days old, "
        "only those whose 63-session daily swing is at or below the live raisers' median, up to 20 "
        "F4-screened members at 5%, held names first then the newest event, rest in SPY, monthly, "
        "behind the SPY-200 switch, fractional at Gotrade's real fees on the owner's deposits) is "
        "dev-eligible, kin clean and beats SPY (+10.6% vs +7.2% funded, 18.7% worst fall, 528 "
        "trades), but wins only 2 of 4 walk-forward folds and lags SPY in 2009-2015 by 2.6 points. "
        "It re-checks every held name against a moving median each month, so a name near the "
        "median is sold and bought back on noise, paying Gotrade's fees on a 5% slot each time. "
        "M0163 measured a keep-until-well-out band worth +1.7 points a year on a yield book. Keep "
        "the entry bar exactly and widen only the bar a held name must stay under: the same pool's "
        "65th, 75th or 90th percentile swing, or no re-check at all (a holding leaves only on raise "
        "expiry, leaving the index screen, or the switch). The idea row spoke of top-20-in, "
        "top-30/40-out ranks; this book has no rank, only a swing cut and a raise clock, so the "
        "band is expressed as a swing quantile, and that is the assumption made here. Variants: "
        "CTRL keep at the median (must reproduce M0088-C-LIVE-63: 528 trades, 18.7% worst fall, "
        "+35.1% CAGR); K65, K75, K90; HOLD (no re-check). Success: a band variant beats CTRL by "
        "at least half a point a year funded with the worst fall at or under 20%, fewer trades, "
        "a positive or less negative 2009-2015 edge and a majority of walk-forward folds."
    ),
    expected_failure=(
        "The calm filter is what cut the worst fall from 21.9% to 18.7%; loosening it for held "
        "names lets a raiser that turned jumpy into a falling market stay in, so the wider bands "
        "slide back toward M0088-X-M's 21.9% and HOLD may break the 20% bar. The churn may be small "
        "anyway: a name's 63-session swing moves slowly and most exits are the 182-day raise clock "
        "and the switch, not the swing re-check, so the band binds on few names and the result is "
        "a null that the analysis must report as one. 2009-2015 lag is the switch selling in the "
        "2010, 2011 and 2015 dips (M0096's diagnosis), which no band on the picks touches, so the "
        "fold record likely stays 2 of 4. A widely published anomaly from the 1990s: even a real "
        "dev edge is likely to fade after 2015. Survivorship flatters dividend books; withholding "
        "tax on dividends is not modelled."
    ),
    candidates=(
        _v("CTRL", 0.5, "Paired control: held names judged at the median like new ones (= M0088-C-LIVE-63)"),
        _v("K65", 0.65, "A held raiser stays while its swing is at or below the live raisers' 65th percentile"),
        _v("K75", 0.75, "A held raiser stays while its swing is at or below the 75th percentile"),
        _v("K90", 0.9, "A held raiser stays unless it is among the jumpiest tenth of the live raisers"),
        _v("HOLD", None, "No swing re-check once bought: out only on raise expiry, leaving the screen, or the switch"),
    ),
    seen_keys=(
        "concept:dividend-increase-drift",
        "concept:dividend-change",
        "concept:low-volatility-filter",
        "concept:buy-hold-band",
    ),
)
