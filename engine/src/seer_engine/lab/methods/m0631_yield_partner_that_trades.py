"""M0631 — A small high-yield partner beside a large SPY core, built so the yield sleeve really trades.

Source: variation of M0164, itself a variation of M0163 (Novy-Marx & Velikov 2016, value survives
costs when traded slowly; Fama & French 1993, dividend yield as value); the core-tilt allocator of
M0096.
Why this exists: M0164 put M0163's yield book inside ``BLEND``. ``BLEND`` prepares its parts from
bars only, so the yield book saw an empty dividend calendar and targeted nothing: the 30% sleeve sat
in cash, the arms recorded zero trades, and the "switched" arm was byte-identical to the unswitched
one. M0164 measured SPY with a cash drag, not the idea. Same fix as M0096: an allocator that
prepares the yield book from the whole ``Market`` and scales its targets itself, the way
``BLEND._merge`` does:

    * sleeve = M0163's ``choose`` on ``data_date`` (its 1/20 slots and its own SPY park), each
      weight x (1 - core), floored to WEIGHT_QUANTUM (a zero drops);
    * core = SPY at weight ``core``, added to the sleeve's SPY park;
    * when the sleeve's own SPY-200 gate (``inner.trend``) is off the sleeve targets nothing and
      the core stays in SPY, so the switch never takes the core out of the market.

Assumptions, written before the run: the 60/40-80/20 drift band is not expressible (the engine's
bands are per holding), so as in M0164 the pair of presets brackets it: the 1%-of-account band
(close to a monthly rebalance) and the 20%-of-own-target band (lazier). Controls are cited, not
re-run: the sleeve alone is M0163-Y20-B40 (trial 512) and its switched twin (trial 513); SPY is the
lab's benchmark on the same deposits and fees; the 70/30 and 85/15 books M0164 recorded are void
as measurements of the idea (they hold cash, trial rows 2221-2224).

Pure: reads only bars and dividends dated <= ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import RaisePrepared
from seer_engine.lab.methods.m0163_banded_dividend_yield import YIELD, YieldParams, _screen, choose
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, MONTHLY_HOLD_FRAC_GOTRADE_TBAND
from seer_engine.strategies.allocator import last_close, scale_weight, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import factor_rows, trend_on

ADDED = date(2026, 11, 13)


@dataclass(frozen=True, slots=True)
class CoreParams:
    """``sleeve`` is M0163's yield book; ``core`` the fixed SPY share."""

    sleeve: YieldParams
    core: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.sleeve, YieldParams):
            raise TypeError(f"sleeve must be YieldParams, got {type(self.sleeve).__name__}")
        if not isinstance(self.core, Decimal) or not self.core.is_finite() or not 0 < self.core < 1:
            raise ValueError(f"core must be a Decimal in (0, 1), got {self.core!r}")
        if self.core % WEIGHT_QUANTUM != 0:
            raise ValueError(f"core must be a multiple of {WEIGHT_QUANTUM}, got {self.core}")

    def as_dict(self) -> dict[str, str]:
        out = {"core": format(self.core.normalize(), "f")}
        for k, v in self.sleeve.as_dict().items():
            out[f"sleeve.{k}"] = v
        return out


def _check(params: object) -> CoreParams:
    if not isinstance(params, CoreParams):
        raise TypeError(f"params must be CoreParams, got {type(params).__name__}")
    return params


class YieldCoreAllocator:
    """A fixed SPY core plus M0163's banded yield book on the rest of the money."""

    id = "M0631"
    market_fields = ("dividends",)

    def lookback(self, params: Any) -> int:
        return YIELD.lookback(_check(params).sleeve)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return YIELD.symbols(_check(params).sleeve)

    def holds(self, params: Any) -> tuple[str, ...]:
        return YIELD.holds(_check(params).sleeve)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: RaisePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: CoreParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
            return ()
        s = p.sleeve
        sleeve: tuple[Target, ...] = ()
        if trend_on(prepared.history, data_date, s.inner):
            if prepared.factor is None:
                rows = factor_rows(prepared.history, members, data_date, s.inner)
            else:
                rows = prepared.factor.rows_on(members, data_date, s.inner)
            sleeve = choose(prepared.history, members, rows, prepared.calendar, data_date, held, s)
        share = Decimal(1) - p.core
        order: list[str] = []
        first: dict[str, Target] = {}
        total: dict[str, Decimal] = {}
        for t in sleeve:
            w = scale_weight(t.weight, share)
            if w is None:
                continue
            order.append(t.symbol)
            first[t.symbol] = t
            total[t.symbol] = w
        mh = prepared.history.get(s.market)
        if mh is not None and mh.index_of(data_date) is not None:
            if s.market in first:
                total[s.market] = to_weight(total[s.market] + p.core)
            else:
                t = target_from_close(s.market, last_close(mh, data_date), p.core)
                if t is not None:
                    order.append(s.market)
                    first[s.market] = t
                    total[s.market] = t.weight
        return tuple(replace(first[k], weight=total[k]) for k in order)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar, so no yield and no target."""
        return self._run(RaisePrepared(history, None, EMPTY_DIVIDENDS), members, data_date, held,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> RaisePrepared:
        return YIELD.prepare(history)

    def prepare_market(self, market: Any) -> RaisePrepared:
        return YIELD.prepare_market(market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, RaisePrepared):
            raise TypeError(f"prepared must be RaisePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


CORE = YieldCoreAllocator()
Y20_B40 = YieldParams(_screen(20), pool=100, keep=40)  # M0163-Y20-B40's params, verbatim
Y20_B40_SW = YieldParams(_screen(20, ("SPY", 200)), pool=100, keep=40)  # M0163-Y20-B40-SW's, verbatim


def _v(suffix: str, rules, params: CoreParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0631-{suffix}", family="M0631", rules=rules, allocator=CORE,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0631",
    name="A small high-yield partner beside a large SPY core, built so the yield sleeve really trades: 70% SPY, 30% the yearly banded yield book",
    family="stock-core-satellite",
    source_kind="variation",
    source_ref=(
        "Variation of M0164 and M0163 (Novy-Marx & Velikov 2016, Rev. Financial Studies 29(1); Fama "
        "& French 1993); the core-tilt allocator of M0096"
    ),
    parent_id="M0164",
    hypothesis=(
        "M0164 held M0163's yield book inside BLEND, which prepares its parts from bars only, so "
        "the sleeve saw no dividends and targeted nothing: 30% idle cash, zero trades, and its "
        "switched arm byte-identical to the unswitched one. This redoes it with an allocator that "
        "reads the whole Market. Dividend yield is decades old and the low-turnover framing came "
        "in 2016, after the dev window. M0163's 20-in, 40-out yield book re-ranked each December "
        "beat SPY on the owner's deposits (+9.0% vs +7.2%, trial 512) but fell 62% in 2008 and "
        "lost all of 2009-2014. Held as a 30% slice beside a 70% always-SPY core it keeps SPY's "
        "drift for most of the money and takes about a third of the yield book's fall. Fractional "
        "shares at Gotrade's real fees on the owner's deposits. Arms: T70 (70% SPY, 30% "
        "M0163-Y20-B40's book, 1%-of-account band), T70-TBAND (the same on the 20%-of-own-target "
        "band, nearest to a drift-only rebalance), T85 (dose check: 15% yield book), T70-SW (the "
        "sleeve behind the SPY-200 switch, core stays in SPY). Controls cited, not re-run: the "
        "sleeve alone is M0163-Y20-B40 (trial 512) and its switched twin (trial 513); the 80/20 "
        "comparator is M0104-C80-UP (trial 522); the calm-raisers analogue is M0096. Success: T70 "
        "beats total-return SPY on the deposits with worst fall <= 25%, PF >= 1.3, a positive edge "
        "in 2009-2015 and a majority of walk-forward folds, and the dose check moves the same way."
    ),
    expected_failure=(
        "SPY alone fell about 55% from its 2007 peak, and a 70% SPY core with an unbraked 30% yield "
        "slice that fell 62% cannot fall less than SPY: every unswitched arm should break the 25% "
        "fall bar, and only T70-SW can pass it. The yield book lagged in 2009-2014 when big growth "
        "led, so the blends should trail SPY there, and 30% is probably too little to lift the "
        "whole-window result above SPY by more than a fraction of a point. Survivorship flatters "
        "the slice (yield traps that died are missing), and withholding tax on dividends is not "
        "modelled."
    ),
    candidates=(
        _v("T70", MONTHLY_HOLD_FRAC_GOTRADE, CoreParams(Y20_B40, Decimal("0.7")),
           "70% SPY, 30% the yearly banded yield book (M0163-Y20-B40's params), 1%-of-account resize band"),
        _v("T70-TBAND", MONTHLY_HOLD_FRAC_GOTRADE_TBAND, CoreParams(Y20_B40, Decimal("0.7")),
           "The same blend on the 20%-of-own-target band: a lazier rebalance, nearest to a drift-only rule"),
        _v("T85", MONTHLY_HOLD_FRAC_GOTRADE, CoreParams(Y20_B40, Decimal("0.85")),
           "Dose check: 85% SPY, 15% the yield book"),
        _v("T70-SW", MONTHLY_HOLD_FRAC_GOTRADE, CoreParams(Y20_B40_SW, Decimal("0.7")),
           "70% SPY, 30% the yield book behind the SPY-200 switch (M0163-Y20-B40-SW's params); the core stays in SPY"),
    ),
    seen_keys=(
        "concept:core-satellite-spy-yield-banded-trading",
        "concept:dividend-yield-value",
        "concept:core-satellite",
    ),
)
