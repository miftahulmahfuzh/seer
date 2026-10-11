"""M0096 — Calm big raisers as a small tilt beside a large SPY core.

Source: variation of M0088 (its C-LIVE-63 book as the sleeve); Michaely, Thaler & Womack (1995),
JF 50(2) for the drift; Ang, Hodrick, Xing & Zhang (2006), JF 61(1) for "calm stocks fall less";
the core-plus-satellite shape of P7a F9 and M0030.
Idea: M0088-C-LIVE-63 passed every dev condition but won only 2 of 4 walk-forward folds, because
it lagged SPY by 2.6 points a year in 2009-2015, the years the giants led. Its worst fall (18.7%)
is now small enough to carry, so hold a fixed SPY core that owns the giants by construction and
run the calm raisers in what is left.

Why a new allocator and not ``BLEND``: ``BLEND`` prepares its parts from bars only
(``LazyPrepared.of`` calls ``prepare(history)``), so M0088's allocator inside it would see an empty
dividend calendar and target nothing. ``CoreTilt`` instead prepares M0088's ``RaisePrepared`` from
the whole ``Market`` and scales its targets itself, the way ``BLEND._merge`` does:

    * sleeve = M0088's ``choose`` on ``data_date`` (its 5% slots and its own SPY park), each
      weight × ``1 - core``, floored to WEIGHT_QUANTUM (a zero drops);
    * core = SPY at weight ``core``, added to the sleeve's SPY park;
    * ``switch="book"``: when F4's SPY-200 gate is off the whole book targets nothing (cash),
      exactly as M0088 alone does; ``switch="sleeve"``: the gate empties only the sleeve and the
      core stays in SPY (evidence for what the switch buys on a mostly-SPY book).

The sleeve's slots are therefore 1.5% at a 70% core, 2.5% at 50%, 0.75% at 85%. Everything else
is M0088-C-LIVE-63: the ex-date big-raise event, calm half of the live raisers on a 63-session
swing, up to 20 names while the event is under 182 days old, monthly, fractional shares at
Gotrade's real fees. Reads only bars and dividends dated <= ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import RaisePrepared
from seer_engine.lab.methods.m0088_calm_big_raisers import CALM, X, CalmParams, choose
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, scale_weight, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import factor_rows, trend_on

ADDED = date(2026, 10, 11)

Switch = Literal["book", "sleeve"]
_SWITCHES: tuple[str, ...] = ("book", "sleeve")


@dataclass(frozen=True, slots=True)
class CoreParams:
    """``sleeve`` is M0088's book; ``core`` the fixed SPY share; ``switch`` what the 200-day gate empties."""

    sleeve: CalmParams
    core: Decimal
    switch: Switch = "book"

    def __post_init__(self) -> None:
        if not isinstance(self.sleeve, CalmParams):
            raise TypeError(f"sleeve must be CalmParams, got {type(self.sleeve).__name__}")
        if not isinstance(self.core, Decimal) or not self.core.is_finite() or not 0 < self.core < 1:
            raise ValueError(f"core must be a Decimal in (0, 1), got {self.core!r}")
        if self.core % WEIGHT_QUANTUM != 0:
            raise ValueError(f"core must be a multiple of {WEIGHT_QUANTUM}, got {self.core}")
        if not isinstance(self.switch, str) or self.switch not in _SWITCHES:
            raise ValueError(f"switch must be one of {_SWITCHES}, got {self.switch!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"core": format(self.core.normalize(), "f"), "switch": self.switch}
        for k, v in self.sleeve.as_dict().items():
            out[f"sleeve.{k}"] = v
        return out


def _check(params: object) -> CoreParams:
    if not isinstance(params, CoreParams):
        raise TypeError(f"params must be CoreParams, got {type(params).__name__}")
    return params


class CoreTiltAllocator:
    """A fixed SPY core plus M0088's calm big-raise book on the rest of the money."""

    id = "M0096"
    market_fields = ("dividends",)

    def lookback(self, params: Any) -> int:
        return CALM.lookback(_check(params).sleeve)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return CALM.symbols(_check(params).sleeve)

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return tuple(sorted(set(CALM.holds(p.sleeve)) | {p.sleeve.ann.base.market}))

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: RaisePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: CoreParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
            return ()
        b = p.sleeve.ann.base
        inner = b.inner
        on = trend_on(prepared.history, data_date, inner)
        if not on and p.switch == "book":
            return ()
        sleeve: tuple[Target, ...] = ()
        if on:
            if prepared.factor is None:
                rows = factor_rows(prepared.history, members, data_date, inner)
            else:
                rows = prepared.factor.rows_on(members, data_date, inner)
            sleeve = choose(prepared.history, rows, prepared.calendar, data_date, held, p.sleeve)
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
        mh = prepared.history.get(b.market)
        if mh is not None and mh.index_of(data_date) is not None:
            if b.market in first:
                total[b.market] = to_weight(total[b.market] + p.core)
            else:
                t = target_from_close(b.market, last_close(mh, data_date), p.core)
                if t is not None:
                    order.append(b.market)
                    first[b.market] = t
                    total[b.market] = t.weight
        return tuple(replace(first[s], weight=total[s]) for s in order)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar, so no event and no target."""
        return self._run(RaisePrepared(history, None, EMPTY_DIVIDENDS), members, data_date, held,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> RaisePrepared:
        return CALM.prepare(history)

    def prepare_market(self, market: Any) -> RaisePrepared:
        return CALM.prepare_market(market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, RaisePrepared):
            raise TypeError(f"prepared must be RaisePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


CORE = CoreTiltAllocator()
SLEEVE = CalmParams(X, "calm", "live", 63)  # M0088-C-LIVE-63, verbatim


def _v(suffix: str, params: CoreParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0096-{suffix}", family="M0096", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CORE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0096",
    name="Calm big raisers as a small tilt beside a large SPY core: 70% SPY, 30% in the calm half of the big dividend raisers",
    family="stock-dividend-change-drift",
    source_kind="variation",
    source_ref=(
        "variation of M0088 (C-LIVE-63 as the sleeve); Michaely, Thaler & Womack (1995), JF 50(2); "
        "Ang, Hodrick, Xing & Zhang (2006), JF 61(1); core-satellite shape of P7a F9 and M0030"
    ),
    parent_id="M0088",
    hypothesis=(
        "Published 1995 (dividend-change drift) and 2006 (low volatility). M0088-C-LIVE-63 (big "
        "dividend raisers seen on the ex-date, calm half of the live raisers on a 63-session "
        "daily swing, up to 20 F4-screened members at 5% while the event is under 182 days old, "
        "rest in SPY, monthly, behind the SPY-200 switch, fractional at Gotrade's real fees) "
        "passed every dev condition (+10.6% vs +7.2% a year on the deposits, worst fall 18.7%, "
        "DSR 0.945) but won only 2 of 4 walk-forward folds, lagging SPY by 2.6 points a year in "
        "2009-2015. Hold a fixed SPY core and run that book on the rest, its slots scaled down "
        "(1.5% at a 70% core): the core owns the giants that led 2009-2015, so the sleeve's "
        "lag there is diluted while some of its 1996-2008 edge survives. Variants: T70 70% core, "
        "the 200-day switch on the whole book (the idea); T50 50% core; T85 85% core; S70 70% "
        "core always held, the switch on the sleeve only (evidence: what the switch buys on a "
        "mostly-SPY book). It ranks on dividend raises, so the family stays "
        "dividend-change-drift. Success: T70 beats SPY on the deposits, a worst fall under 20%, "
        "a 2009-2015 gap under 1 point a year, and a majority of walk-forward folds."
    ),
    expected_failure=(
        "The core simply dilutes the edge toward SPY: a 70% core keeps about 30% of the sleeve's "
        "edge over SPY (roughly 1 point a year), the 2009-2015 lag shrinks in proportion but stays "
        "negative, so the fold record does not move. With the switch on the whole book the "
        "result is mostly the 200-day rule on SPY, whose dev record is a fraction of a point "
        "ahead of SPY, plus whipsaw exits; the DSR may fall under 0.90 as the edge shrinks while "
        "the swings stay SPY-sized. S70 breaks the 20% limit in 2008 (70% of SPY's 55% fall is "
        "about 38%). The family is a widely published 1990s anomaly, so even a dev edge is "
        "likely to fade after 2015. Withholding tax on dividends is not modelled."
    ),
    candidates=(
        _v("T70", CoreParams(SLEEVE, Decimal("0.7"), "book"),
           "70% SPY core + 30% calm big raisers, the 200-day switch on the whole book"),
        _v("T50", CoreParams(SLEEVE, Decimal("0.5"), "book"),
           "50% SPY core + 50% calm big raisers, the 200-day switch on the whole book"),
        _v("T85", CoreParams(SLEEVE, Decimal("0.85"), "book"),
           "85% SPY core + 15% calm big raisers, the 200-day switch on the whole book"),
        _v("S70", CoreParams(SLEEVE, Decimal("0.7"), "sleeve"),
           "70% SPY always held + 30% calm big raisers, the switch on the sleeve only"),
    ),
    seen_keys=(
        "concept:dividend-increase-drift",
        "concept:low-volatility-filter",
        "concept:core-satellite",
        "concept:spy-core-dividend-raise-satellite",
    ),
)
