"""M0067 — Dodge the dividend on purpose: calm dividend payers, each benched in the month it goes ex.

Source: variation of M0051 (Hartzmark & Solomon 2013, the dividend-month premium, run backwards).
Idea: M0051's off-month control -- high-yield payers NOT due to pay next month -- beat every
dividend-month book and SPY. For a long-only Indonesian account that loses 15-30% of each US
dividend to withholding, never holding a stock on its ex-date should be worth something. Here the
avoidance is the whole strategy: among members with a trailing dividend yield, keep the calmest
(lowest 60-day volatility) that are not predicted to go ex-dividend next month.

The frame is M0051's -- F4's screened point-in-time members, the SPY 200-day gate, monthly,
fractional shares at Gotrade's real fees. ``predicted`` and ``trailing_yield`` are M0051's, read
only through ``DividendCalendar.known_on(symbol, data_date)``, so no future ex-date leaks in.

``bench="off"`` drops every member predicted to pay in the coming month; ``bench="any"`` benches
nobody (the control: the same calm payers, never stepping aside for the ex-date).
``rank="lowvol"`` takes the ``top`` lowest 60-day volatilities, ``rank="yield"`` the ``top``
highest trailing yields.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, N20_NOTREND
from seer_engine.lab.methods.m0051_dividend_month_premium import holding_month, predicted, trailing_yield
from seer_engine.sim.book import Target, equal_weight
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
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 13)

Bench = Literal["off", "any"]
Rank = Literal["lowvol", "yield"]


@dataclass(frozen=True, slots=True)
class DodgeParams:
    """``inner`` is F4's screen and trend gate; its ``top`` sizes the book."""

    inner: FactorParams
    rank: Rank = "lowvol"
    bench: Bench = "off"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.rank not in ("lowvol", "yield"):
            raise ValueError(f"rank must be 'lowvol' or 'yield', got {self.rank!r}")
        if self.bench not in ("off", "any"):
            raise ValueError(f"bench must be 'off' or 'any', got {self.bench!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"rank": self.rank, "bench": self.bench}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> DodgeParams:
    if not isinstance(params, DodgeParams):
        raise TypeError(f"params must be DodgeParams, got {type(params).__name__}")
    return params


def choose(rows: list[FactorRow], calendar: DividendCalendar, data_date: date,
           params: DodgeParams) -> list[FactorRow]:
    month = holding_month(data_date)
    scored: list[tuple[float, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED:
            continue
        paid = calendar.known_on(r.symbol, data_date)
        if not paid:
            continue
        y = trailing_yield(paid, r.close, data_date)
        if y <= 0.0:
            continue
        if params.bench == "off" and predicted(paid, month):
            continue
        scored.append((-y if params.rank == "yield" else r.vol, r.symbol, r))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [r for _, _, r in scored[: params.inner.top]]


def targets_from_rows(chosen: list[FactorRow], params: DodgeParams) -> tuple[Target, ...]:
    w = equal_weight(params.inner.top)
    out: list[Target] = []
    for row in chosen:
        target = target_from_close(row.symbol, row.close, w)
        if target is not None:
            out.append(target)
    return tuple(out)


@dataclass
class DodgePrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    calendar: DividendCalendar = field(repr=False)


class DodgeDividendAllocator:
    """Calm (or high-yield) dividend payers not predicted to go ex-dividend in the coming month.

    Held symbols get no special treatment: a name that becomes due next month is signal-exited.
    """

    id = "M0067"
    market_fields = ("dividends",)

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).inner)

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
        """The history-only path: no calendar, so no payer and no target."""
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return targets_from_rows(choose(rows, EMPTY_DIVIDENDS, data_date, p), p)

    def prepare(self, history: Mapping[str, History]) -> DodgePrepared:
        return DodgePrepared(history, prepare_factor(history), EMPTY_DIVIDENDS)

    def prepare_market(self, market: Any) -> DodgePrepared:
        calendar = getattr(market, "dividends", EMPTY_DIVIDENDS)
        if not isinstance(calendar, DividendCalendar):
            raise TypeError(f"market.dividends must be a DividendCalendar, got {type(calendar).__name__}")
        return DodgePrepared(market.history, prepare_factor(market.history), calendar)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, DodgePrepared):
            raise TypeError(f"prepared must be DodgePrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return targets_from_rows(choose(rows, prepared.calendar, data_date, p), p)


DODGE = DodgeDividendAllocator()

T20 = replace(N20, rank="lowvol")
T30 = replace(N20, rank="lowvol", top=30)
NOT30 = replace(N20_NOTREND, rank="lowvol", top=30)


def _v(suffix: str, params: DodgeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0067-{suffix}", family="M0067", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=DODGE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0067",
    name="Dodge the dividend on purpose: calm dividend payers, each benched in the month it goes ex",
    family="stock-dividend-calendar",
    source_kind="variation",
    source_ref="M0051",
    parent_id="M0051",
    hypothesis=(
        "M0051's off-month control (the 20 highest-yield payers not due to pay next month) beat "
        "every dividend-month book and SPY by about a point a year (its funded +8.3% a year vs "
        "+7.2%, trial 208), because it never held a stock on its ex-date. Hartzmark and Solomon "
        "(published 2013, circulated 2011) is the anomaly it runs backwards, so the dev window is "
        "pre-publication. For a long-only Indonesian account losing 15-30% of each US dividend to "
        "withholding (not modelled by the lab), avoiding ex-dates is worth something. That control "
        "fell 33% at its worst, mostly at the 2000 bubble peak, and lagged SPY in 2009-2015, so "
        "this tests the avoidance on its own: among members with a trailing dividend yield, keep "
        "the calmest by 60-day volatility (30 names; 20 as a sibling), dropping any predicted to "
        "go ex next month (M0051's rule: ex in calendar month M-12 or M-3, read point in time), "
        "behind the SPY 200-day gate, monthly, fractional, Gotrade fees. Variants: CALM30-OFF-T "
        "(headline), CALM20-OFF-T, CALM30-ANY-T (control: the same calm payers never stepping "
        "aside, so CALM30-OFF-T minus it is the value of the avoidance alone), CALM30-OFF (no "
        "gate, so the gate's cost is priced), YLD30-OFF-T (yield-ranked twin; M0051-OFF20-T, "
        "trial 208, is the recorded 20-name yield-ranked book and is cited, not re-run). Success: "
        "CALM30-OFF-T beats SPY TR on dev within the 20% drawdown limit, beats CALM30-ANY-T, and "
        "keeps a positive edge in 2009-2015."
    ),
    expected_failure=(
        "The calm, high-yield tilt still falls with value stocks in 2000 and lags big-company "
        "growth after 2009, so it beats SPY on average but breaks the 20% limit; the 2009-2015 "
        "era edge is likely negative (the parent control was). Calm payers are utilities, staples "
        "and tobacco, a defensive bet that may simply be low beta in disguise, and the avoidance "
        "itself may add nothing over CALM30-ANY-T: with a quarter of payers due each month, the "
        "benched set is a random fraction of the pool, so it may only add turnover at Gotrade's "
        "$0.10 minimum. A published anomaly (2011-13) run backwards cannot be expected to keep "
        "paying. Withholding tax is not modelled, so any edge from dodging it is invisible here "
        "and the analysis can only argue it."
    ),
    candidates=(
        _v("CALM30-OFF-T", DodgeParams(T30, "lowvol", "off"),
           "The 30 calmest dividend payers not predicted to go ex next month, behind the SPY 200-day gate"),
        _v("CALM20-OFF-T", DodgeParams(T20, "lowvol", "off"),
           "The 20 calmest payers not predicted to go ex next month, behind the gate: the tighter book"),
        _v("CALM30-ANY-T", DodgeParams(T30, "lowvol", "any"),
           "Control: the same 30 calmest payers with no bench for the ex-date, behind the gate, so "
           "CALM30-OFF-T minus this is the avoidance alone"),
        _v("CALM30-OFF", DodgeParams(NOT30, "lowvol", "off"),
           "The 30 calmest benched payers, always invested: prices the SPY gate's cost and protection"),
        _v("YLD30-OFF-T", DodgeParams(T30, "yield", "off"),
           "The 30 highest-yield payers not predicted to go ex next month, behind the gate: the "
           "yield-ranked twin at 30 names (M0051-OFF20-T, trial 208, is the 20-name book)"),
    ),
    seen_keys=(
        "concept:dividend-avoidance",
        "concept:ex-dividend-bench",
        "concept:calm-dividend-payers",
    ),
)
