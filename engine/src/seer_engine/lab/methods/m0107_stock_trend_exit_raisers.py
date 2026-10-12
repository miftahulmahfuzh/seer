"""M0107 — Calm big raisers that leave one at a time: a per-stock trend exit instead of the market switch.

Source: variation of M0088 (C-LIVE-63, the best calm big-raiser book); Michaely, Thaler & Womack
(1995), JF 50(2) for the raise drift; Ang, Hodrick, Xing & Zhang (2006), JF 61(1) for the calm
filter; Faber (2007), JWM 9(4) for the 200-day frame, here moved off the index and onto each holding.
Idea: three batches now agree that the market-wide SPY-200 switch, not the dividend raisers, is
what loses to SPY after 2009 — it sold the 2010, 2011 and 2015 dips whole and bought back higher —
and M0101 showed that no gentler, banded or slower reading of the same switch repairs it. The
switch cannot simply be deleted either: sitting out 2008 is what earned the family its 2002-2008
edge. So this keeps M0088's calm big-raiser book and swaps the machine, not the job: no market
gate at all, and instead a holding is refused whenever it trades below its own 200-day average.

Why that should behave differently. The market switch is one binary decision applied to the whole
book, so a six-week dip that most raisers ride through costs 100% of the exposure and the re-entry
is late by construction. A per-stock rule is twenty small decisions: exposure falls gradually as
names drop out and rebuilds name by name as each recovers, so an ordinary dip costs the fraction
of the book that actually broke down, while a 2008 in which nearly every raiser breaks still
empties it. The cost is whipsaw, paid twenty times over at Gotrade's real fees on 5% slots.

The book is M0088-C-LIVE-63 verbatim (M0076's event logic with ``timing="ex"``, M0070's F4 screen
and 182-day hold clock, up to 20 names at 5%, held names first then the newest event, monthly,
fractional at Gotrade's real fees), with two new dials and one changed default:

    * ``stock_n`` — a holding is admitted only when its close on ``data_date`` is strictly above
      the mean of its last ``stock_n`` closes (the same arithmetic ``f_factor.trend_on`` applies
      to SPY, via ``indicators.sma_window``). ``None`` turns the per-stock gate off.
    * ``spread`` — False leaves the dropped names' 5% slots in cash, so the per-stock gate lowers
      exposure. True hands their weight to the survivors instead, so total exposure is whatever
      the unfiltered book would have held and only the *names* change. The pair separates the two
      things a trend exit does: de-risking, and avoiding the weak names.
    * ``park=False`` on every gate-free variant. M0088 parked the slack in SPY, which only made
      sense because the SPY-200 switch sold that SPY too; without the switch, parking in SPY would
      make this a SPY-core book that is long the market through every fall. Slack is cash here.

Pure: reads only bars and dividends dated <= ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import (
    NOT20,
    RaisePrepared,
    _first_bar,
    live_event,
)
from seer_engine.lab.methods.m0076_dividend_raise_on_announcement import R25, AnnParams, events
from seer_engine.lab.methods.m0088_calm_big_raisers import CalmParams, admits, swing
from seer_engine.sim.book import Target, equal_weight, to_weight
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
from seer_engine.strategies.indicators import sma_window

ADDED = date(2026, 10, 12)


@dataclass(frozen=True, slots=True)
class StockTrendParams:
    """``calm`` is M0088's book and swing filter; ``stock_n`` and ``spread`` are the new exit."""

    calm: CalmParams
    stock_n: int | None = 200
    spread: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.calm, CalmParams):
            raise TypeError(f"calm must be CalmParams, got {type(self.calm).__name__}")
        if self.stock_n is not None:
            if isinstance(self.stock_n, bool) or not isinstance(self.stock_n, int):
                raise TypeError(f"stock_n must be None or an int, got {type(self.stock_n).__name__}")
            if self.stock_n < 2:
                raise ValueError(f"stock_n must be >= 2, got {self.stock_n}")
        if not isinstance(self.spread, bool):
            raise TypeError(f"spread must be a bool, got {type(self.spread).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "stock_n": "none" if self.stock_n is None else str(self.stock_n),
            "spread": str(self.spread).lower(),
        }
        for k, v in self.calm.as_dict().items():
            out[f"calm.{k}"] = v
        return out


def _check(params: object) -> StockTrendParams:
    if not isinstance(params, StockTrendParams):
        raise TypeError(f"params must be StockTrendParams, got {type(params).__name__}")
    return params


def above_own_trend(h: History | None, data_date: date, n: int) -> bool:
    """True when ``h``'s close on ``data_date`` is strictly above the mean of its last ``n`` closes.

    False when the symbol is absent, has no bar dated ``data_date``, has fewer than ``n`` bars
    through it, or the window is not finite. Same arithmetic as ``f_factor.trend_on`` applies to
    SPY, so the per-stock gate and the market gate agree on what "below the 200-day" means.
    """
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None or i + 1 < n:
        return False
    window = np.asarray(h.close[i + 1 - n : i + 1], dtype=float).reshape(1, n)
    if not np.all(np.isfinite(window)):
        return False
    return bool(window[0, -1] > sma_window(window, n)[0])


def choose(history: Mapping[str, History], rows: list[FactorRow], calendar: DividendCalendar,
           data_date: date, held: frozenset[str], p: StockTrendParams) -> tuple[Target, ...]:
    """M0088's pick, then the per-stock trend exit, then the weighting ``spread`` asks for."""
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
    if c.side != "none":
        vols = {t[2]: swing(history.get(t[2]), data_date, c.vol_n) for t in live}
        if c.pool == "live":
            swings = list(vols.values())
        else:
            swings = [vols[r.symbol] if r.symbol in vols
                      else swing(history.get(r.symbol), data_date, c.vol_n)
                      for r in rows if r.symbol not in EXCLUDED and r.symbol != b.market]
        pool = [v for v in swings if v is not None]
        cut = float(np.median(pool)) if pool else None
        live = [t for t in live if admits(vols[t[2]], cut, c.side)]
    live.sort(key=lambda t: (t[0], t[1], t[2]))
    chosen = live[: b.inner.top]  # the slot set the unfiltered book would have held
    slot = equal_weight(b.inner.top)
    if p.stock_n is None:
        kept = chosen
    else:
        kept = [t for t in chosen if above_own_trend(history.get(t[2]), data_date, p.stock_n)]
    w = slot
    if p.spread and kept and len(kept) < len(chosen):
        # The dropped names' slots go to the survivors: same total exposure, fewer names.
        w = to_weight(slot * Decimal(len(chosen)) / Decimal(len(kept)))
    out: list[Target] = []
    for _, _, _, r in kept:
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


class StockTrendRaiseAllocator:
    """The calm big-raise book that drops each raiser trading below its own moving average."""

    id = "M0107"
    market_fields = ("dividends",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        need = [factor_lookback(p.calm.ann.base.inner), p.calm.vol_n + 1]
        if p.stock_n is not None:
            need.append(p.stock_n)
        return max(need)

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
             held: frozenset[str], p: StockTrendParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
            return ()
        inner = p.calm.ann.base.inner
        if not trend_on(prepared.history, data_date, inner):  # None for the gate-free variants
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
            raise TypeError(
                f"market.dividends must be a DividendCalendar, got {type(calendar).__name__}")
        return RaisePrepared(market.history, prepare_factor(market.history), calendar)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, RaisePrepared):
            raise TypeError(f"prepared must be RaisePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


STOCKTREND = StockTrendRaiseAllocator()

# M0088-C-LIVE-63's book, verbatim: the SPY-200 switch on, slack parked in SPY.
HOST = CalmParams(AnnParams(R25, "ex"), "calm", "live", 63)
# The same book with the market switch deleted and the slack in cash, not SPY.
FREE = CalmParams(AnnParams(replace(R25, inner=NOT20, park=False), "ex"), "calm", "live", 63)
# The market switch kept, slack in cash: the arm that asks whether the two gates are complements.
GATED = CalmParams(AnnParams(replace(R25, park=False), "ex"), "calm", "live", 63)


def _v(suffix: str, params: StockTrendParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0107-{suffix}", family="M0107", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=STOCKTREND, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0107",
    name="Calm big raisers that leave one at a time: each holding sold when it falls under its own 200-day average, instead of selling the whole book when the market does",
    family="stock-dividend-change-drift",
    source_kind="variation",
    source_ref=(
        "variation of M0088 (C-LIVE-63); Michaely, Thaler & Womack (1995), JF 50(2); Ang, "
        "Hodrick, Xing & Zhang (2006), JF 61(1); Faber (2007), JWM 9(4) for the 200-day frame"
    ),
    parent_id="M0088",
    hypothesis=(
        "Three batches agree that the market-wide SPY-200 switch, not the dividend raisers, is "
        "what loses to SPY after 2009: it sold the 2010, 2011 and 2015 dips whole and bought back "
        "higher, and M0101 showed that no gentler, banded or slower reading of the same switch "
        "fixes it, because those dips were real falls that bounced before any market-wide rule "
        "could get back in. The switch is also what earned the family its 2002-2008 edge by "
        "sitting out 2008, so it cannot simply be deleted. This tests a different machine for the "
        "same job. Keep M0088-C-LIVE-63's calm big-raiser book exactly as it is (big raise seen "
        "on its ex-date, up to 20 F4-screened members at 5% while the event is under 182 days "
        "old, held names first then the newest event, calm half of the live raisers on a "
        "63-session swing, monthly, fractional at Gotrade's real fees), delete the SPY-200 gate "
        "entirely, park the slack in cash rather than SPY, and refuse to hold any individual "
        "raiser whose close is at or below the mean of its own last 200 closes. Exposure then "
        "falls gradually as names drop out one by one rather than all at once, and rebuilds name "
        "by name as each stock recovers, so a six-week dip that most holdings ride through costs "
        "a fraction of the book rather than all of it, while a 2008 in which almost every name "
        "breaks down still empties the book. Variants: HOST, the paired control, is M0088-C-LIVE-63 "
        "unchanged and must reproduce its numbers (+10.6% a year, 18.7% worst fall) at the same "
        "fees in the same run; NONE is the naked book with no gate of any kind and cash for the "
        "empty slots, the yardstick the per-stock exit is measured against; STOCK200 adds the "
        "per-stock exit with the freed 5% slots in cash, which is the idea; STOCK200-SPREAD hands "
        "the freed weight to the surviving names instead, holding total exposure at what the "
        "unfiltered book would have held so that only the choice of names changes — the pair "
        "separates de-risking from name selection; BOTH runs the per-stock exit behind the old "
        "SPY-200 switch, to see whether the two are substitutes or complements. It still ranks on "
        "dividend raises, so the family stays dividend-change-drift. Success: STOCK200 beats SPY "
        "total return on deposit-matched money over the dev window with a worst fall under 20%, "
        "and — the thing that matters — a smaller 2009-2015 gap to SPY than M0088's -2.6 points a "
        "year, with a majority of the walk-forward folds won."
    ),
    expected_failure=(
        "A per-stock trend exit is slower than the market switch in a fast crash and is paid for "
        "in whipsaw on every individual name, so it may give back more in trading costs and late "
        "exits than the market switch cost in whipsaw; on 5% slots at Gotrade's real fees a $28 "
        "order pays about 0.47%, and twenty names churning in and out of their own averages is "
        "several times the host's turnover. 2008 may still breach 20% because calm dividend "
        "raisers break down together and the per-stock rule only sells after each one is already "
        "well down. The calm raisers are mostly utilities, staples and old industrials, which "
        "lagged big-company growth after 2009, so removing the market switch may fix the dip "
        "whipsaw and still leave the 2009-2015 gap, which would mean the picks, not the gate, are "
        "the problem and the family should close. STOCK200-SPREAD may simply be a more "
        "concentrated version of NONE and fall further. Dividend drift was published in 1995 and "
        "low volatility in 2006, so even a real dev edge earned mostly before 2009 is likely to "
        "fade after 2015. Withholding tax on dividends is not modelled."
    ),
    candidates=(
        _v("HOST", StockTrendParams(HOST, None, False),
           "Paired control: M0088-C-LIVE-63 unchanged (SPY-200 switch, slack in SPY)"),
        _v("NONE", StockTrendParams(FREE, None, False),
           "Yardstick: the same book with no gate at all and cash for the empty slots"),
        _v("STOCK200", StockTrendParams(FREE, 200, False),
           "The idea: drop each raiser under its own 200-day average, freed slots in cash"),
        _v("STOCK200-SPREAD", StockTrendParams(FREE, 200, True),
           "Same exit, freed weight handed to the survivors instead of held in cash"),
        _v("BOTH", StockTrendParams(GATED, 200, False),
           "Per-stock exit behind the old SPY-200 switch: substitutes or complements?"),
    ),
    seen_keys=(
        "concept:dividend-increase-drift",
        "concept:dividend-change",
        "concept:low-volatility-filter",
        "concept:per-stock-trend-exit",
        "concept:stock-200-day-average",
    ),
)
