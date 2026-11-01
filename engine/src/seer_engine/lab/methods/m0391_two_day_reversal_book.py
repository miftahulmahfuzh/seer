"""M0391 — A two-day reversal book: the one horizon M0356's frozen fit picked out for itself.

Source: variation of M0356. Short-term reversal is published (Jegadeesh 1990, Lehmann 1990, one
week to one month), so this is a *known* anomaly and is registered as one that has probably faded.

Idea: M0356 fitted 42 weights on 1993-1995 and the fit was noise except at one end: the two most
recent daily returns carried the two largest negative weights (-0.169 and -0.215), ahead of the
largest mid-month weight (-0.149). This book ranks F4-screened point-in-time index members on
their last **two** daily returns alone (the two-day return, weakest first) and holds the 20 weakest
at 5% each. The lab has tested one-month reversal (M0028), residual reversal (M0158), quiet-fall
reversal (M0161) and turnover-conditioned reversal (M0057), but never a horizon of a few days.

**A cadence test as much as a signal test.** A two-day signal is stale within a week, so the same
rank is registered at monthly re-pick and at weekly re-pick. The weekly book pays the fees of a
much busier account, and its coin arm is registered beside it so what that churn costs is priced
instead of argued.

**The idle arm, and why it is not the coin arm.** M0356 registered its whole gate-on/gate-off
square and still could not price its habit, because a book that re-picks monthly turns over about
20 times a year even with the gate off. The idle arm here is the same frame, always invested, with
the names drawn in a date-free hash order: a name stays until it leaves the screened pool, so the
book hardly trades. It is the opinion-free, habit-free control: what the frame earns when nobody
is picking and nobody is churning. The coin arms are redrawn every decision (M0353's hash formula,
verbatim) so they churn like the books they control.

Frame is M0356's, unchanged: F4's point-in-time members with the $5 and 20-million-dollar screen,
20 names equally weighted, the SPY 200-day trend switch (except the idle arm), fractional shares
at Gotrade's real fees. Bars are split- and dividend-adjusted. Reads only bars dated <= d.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, N20_NOTREND
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, WEEKLY_HOLD
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

ADDED = date(2026, 11, 1)

# The weekly twin of the monthly preset, at Gotrade's real fees. Not a preset in sim/rules.py
# (M0063 and four others defined theirs inline too); it runs on dev, and a winner would need a
# feature-wish for a promotable preset.
WEEKLY_HOLD_FRAC_GOTRADE = replace(WEEKLY_HOLD, id="weekly-hold-frac-gotrade", fractional=True,
                                   cost_model="gotrade")

Score = Literal["rev", "coin", "sticky"]
_SCORES: tuple[str, ...] = ("rev", "coin", "sticky")


@dataclass(frozen=True, slots=True)
class ReversalParams:
    """``inner`` is F4's screen, trend gate and book size. ``horizon`` is the number of daily
    returns summed into the signal. ``score`` picks the ranking; ``strongest_first`` flips it."""

    inner: FactorParams
    score: Score = "rev"
    horizon: int = 2
    strongest_first: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.score not in _SCORES:
            raise ValueError(f"score must be one of {_SCORES}, got {self.score!r}")
        if self.horizon < 1:
            raise ValueError(f"horizon must be >= 1, got {self.horizon}")

    def as_dict(self) -> dict[str, str]:
        out = {"score": self.score, "horizon": str(self.horizon),
               "strongest_first": str(self.strongest_first)}
        for key, v in self.inner.as_dict().items():
            out[f"inner.{key}"] = v
        return out


def _check(params: object) -> ReversalParams:
    if not isinstance(params, ReversalParams):
        raise TypeError(f"params must be ReversalParams, got {type(params).__name__}")
    return params


def _score(h: History, data_date: date, p: ReversalParams) -> float | None:
    """Ascending key: the weakest recent return, or a hash draw; None when unusable."""
    i = h.index_of(data_date)
    if i is None:
        return None
    if p.score == "rev":
        if i < p.horizon:
            return None
        base = float(h.close[i - p.horizon])
        if base <= 0.0:
            return None
        r = float(h.close[i]) / base - 1.0
        return -r if p.strongest_first else r
    # "coin" is M0353's formula verbatim (redrawn every date, so it churns like a ranked book);
    # "sticky" drops the date from the key, so a name stays until it leaves the screened pool.
    key = (f"{h.symbol}|{data_date.isoformat()}" if p.score == "coin" else f"{h.symbol}|sticky")
    digest = hashlib.sha256(key.encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2.0**64


@dataclass
class ReversalPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)


def choose(rows: list[FactorRow], prepared: ReversalPrepared, data_date: date,
           p: ReversalParams) -> list[FactorRow]:
    kept: list[tuple[FactorRow, float]] = []
    for r in rows:
        h = prepared.history.get(r.symbol)
        if r.symbol in EXCLUDED or h is None:
            continue
        s = _score(h, data_date, p)
        if s is not None:
            kept.append((r, s))
    kept.sort(key=lambda t: (t[1], t[0].symbol))
    return [r for r, _ in kept[: p.inner.top]]


class ReversalAllocator:
    """F4's book ranked on the last ``horizon`` daily returns, weakest first.

    Held symbols get no special treatment: a name that leaves the chosen set is signal-exited
    (the idle arm stays put only because its hash order never changes).
    """

    id = "M0391"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(factor_lookback(p.inner), p.horizon + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.inner.trend[0],) if p.inner.trend is not None else ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def prepare(self, history: Mapping[str, History]) -> ReversalPrepared:
        return ReversalPrepared(history, prepare_factor(history))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        prepared = ReversalPrepared(history, prepare_factor(history))
        return targets_from_rows(choose(rows, prepared, data_date, p), p)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ReversalPrepared):
            raise TypeError(f"prepared must be ReversalPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return targets_from_rows(choose(rows, prepared, data_date, p), p)


REVERSAL = ReversalAllocator()


def _v(suffix: str, params: ReversalParams, rationale: str,
       rules=MONTHLY_HOLD_FRAC_GOTRADE) -> Candidate:
    return Candidate(id=f"M0391-{suffix}", family="M0391", rules=rules, allocator=REVERSAL,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0391",
    name="Two-day reversal book: buy the 20 index members that fell most over the last two days",
    family="stock-short-term-reversal",
    source_kind="variation",
    source_ref="M0356 (its frozen fit's only non-noise structure sat at the two-day horizon)",
    parent_id="M0356",
    hypothesis=(
        "M0356's frozen 42-weight fit, learned on 1993-1995 before the dev window, was noise "
        "except at the recent end: the two most recent daily returns carried the two largest "
        "negative weights (-0.169 and -0.215), ahead of the largest mid-month weight (-0.149). "
        "The fit picked that horizon out on its own. This method ranks F4-screened point-in-time "
        "index members on their last two daily returns alone (the two-day return, weakest first) "
        "and holds the 20 weakest at 5% each behind the SPY 200-day switch, fractional shares at "
        "Gotrade's real fees, M0356's chassis unchanged. Short-term reversal was published in "
        "1990, so it is an old anomaly and the dev window ends long after the crowd found it. "
        "Because the signal's horizon is far shorter than a monthly hold, this is also a "
        "cadence test: the same rank is registered at monthly and at weekly re-pick (assumption: "
        "the horizon is fixed at two days, the one the fit named, because the 6-variant cap "
        "leaves room for one horizon and the controls that make it readable). Six arms: the "
        "book monthly, the book weekly, the mirror (the 20 strongest) monthly, a coin arm "
        "(M0353's hash redrawn every decision, so it churns like a ranked book) at each cadence, "
        "and an idle arm: always invested, no switch, names in a date-free hash order so a name "
        "stays until it leaves the screened pool. The idle arm is expected to trade very little, "
        "which prices what the habit of re-picking costs; its exposure and turnover are measured "
        "after the run, not assumed. To count, the book must beat SPY TR on dev within the 20% "
        "limit, clear the luck bar, beat its coin arm by more than the lab's draw noise, trail "
        "its mirror, and be positive in 2009-2015."
    ),
    expected_failure=(
        "A two-day signal acted on monthly is stale before it is traded, and short-horizon "
        "reversal in large caps is among the most heavily arbitraged effects there is. Expect "
        "the book to pay in the 1990s half and vanish or invert after 2009, which is the half "
        "that decides. The weekly arm should pay the most in fees: at roughly 20 names a week "
        "and $22-70 slots, Gotrade's per-order minimum may eat a gross edge whole, so the weekly "
        "book is the most likely to lose to its own idle arm. M0028's one-month reversal tied SPY "
        "at best (+7.5% on deposits, a 27% fall) and M0353's plain reversal arm was its worst, "
        "so the prior for this family is a coin-flip result and a worst fall above 20% on the "
        "gated arms. Buying yesterday's losers also leans toward the smaller and more distressed "
        "members, the opposite of SPY's big-company drift."
    ),
    candidates=(
        _v("REV2-M-T", ReversalParams(N20, "rev", 2),
           "The two-day losers, behind the switch, re-picked monthly: the book"),
        _v("REV2-W-T", ReversalParams(N20, "rev", 2),
           "The same book re-picked weekly: the cadence arm, expected to pay the most in fees",
           rules=WEEKLY_HOLD_FRAC_GOTRADE),
        _v("REV2-HI-M-T", ReversalParams(N20, "rev", 2, strongest_first=True),
           "The mirror: the 20 strongest two-day winners, behind the switch, monthly; expected "
           "to trail"),
        _v("COIN-M-T", ReversalParams(N20, "coin"),
           "Hash-drawn 20 redrawn every month, behind the switch: the draw-noise yardstick that "
           "churns like the book"),
        _v("COIN-W-T", ReversalParams(N20, "coin"),
           "Hash-drawn 20 redrawn every week, behind the switch: prices the weekly churn",
           rules=WEEKLY_HOLD_FRAC_GOTRADE),
        _v("IDLE-N20", ReversalParams(N20_NOTREND, "sticky"),
           "Hash order, date-free, always invested, no switch: the idle arm that hardly trades"),
    ),
    seen_keys=(
        "concept:two-day-reversal",
        "concept:short-horizon-reversal",
        "concept:reversal-cadence",
    ),
)
