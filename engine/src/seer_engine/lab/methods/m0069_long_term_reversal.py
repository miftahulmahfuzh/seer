"""M0069 — Buy the long-term losers: big index members that fell furthest over the past three to five years, skipping the last year.

Source: De Bondt & Thaler (1985), "Does the Stock Market Overreact?", Journal of Finance 40(3),
793-805; see also https://faculty.georgetown.edu/qw50/LTR.pdf.
Idea: investors overreact over several years, so the stocks that lost most over months -60..-13
rebound over the next one to three years. Skipping the latest 12 months keeps clear of momentum,
which runs the other way over that horizon.

The frame is F4's -- point-in-time members, the $5 price and 20M-dollar volume screen (it keeps the
book to big, easily traded names), monthly, equal weights, fractional shares at Gotrade's real fees
on ``monthly-hold-frac-gotrade`` -- with the ranking turned upside down:

    formation(s) = return_window(close, mom_n, 252)    (c[-253] / c[-1-mom_n] - 1)

``side="losers"`` holds the ``top`` names with the LOWEST formation return; ``side="winners"`` the
highest (the control: plain long-horizon momentum, which the paper says should trail). A name needs
``mom_n + 1`` bars through d, so the store's 1993 start leaves few eligible names before 1996-1998.
Slots the screen cannot fill go to SPY (``fill``), so an empty book is the market, not cash.
``lookback`` declares only what the fixed instruments need; members carry their own longer need
through F4's eligibility screen. If this ever reaches paper, the paper loader must fetch at least
``mom_n + 1`` member bars (it sizes its fetch from ``lookback``): a promotion-time fix, not a
dev-time one. When
``inner.trend`` is set and SPY is below its 200-day average, the whole book is cash.

Assumptions, written before the run: the reserved idea also named a quarterly re-pick, but the lab
has no quarterly real-fee preset; a three-to-five-year signal barely changes month to month, so the
monthly re-pick trades little more than a quarterly one would, and the fees decide that, not the
cadence. Reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, equal_weight, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    DV_N,
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 10)

Side = Literal["losers", "winners"]
_SIDES: tuple[str, ...] = ("losers", "winners")


@dataclass(frozen=True, slots=True)
class LtrParams:
    """``inner`` is F4's screen, formation window (mom_n, mom_skip), book size and trend gate."""

    inner: FactorParams
    side: Side = "losers"
    fill: str | None = "SPY"  # unfilled slots go here; None leaves them in cash

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.inner.rank != "momentum":
            raise ValueError("inner.rank must be 'momentum' (the formation return)")
        if not isinstance(self.side, str) or self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")
        if self.fill is not None and (not isinstance(self.fill, str) or not self.fill):
            raise ValueError(f"fill must be None or a non-empty str, got {self.fill!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "fill": self.fill or ""}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> LtrParams:
    if not isinstance(params, LtrParams):
        raise TypeError(f"params must be LtrParams, got {type(params).__name__}")
    return params


def choose(rows: list[FactorRow], params: LtrParams) -> list[FactorRow]:
    sign = 1.0 if params.side == "losers" else -1.0
    scored = [(sign * r.momentum, r.symbol, r) for r in rows if r.symbol not in EXCLUDED]
    scored.sort(key=lambda t: (t[0], t[1]))
    return [r for _, _, r in scored[: params.inner.top]]


def build(chosen: list[FactorRow], history: Mapping[str, History], data_date: date,
          params: LtrParams) -> tuple[Target, ...]:
    w = equal_weight(params.inner.top)
    out: list[Target] = []
    for row in chosen:
        t = target_from_close(row.symbol, row.close, w)
        if t is not None:
            out.append(t)
    empty = params.inner.top - len(out)
    if params.fill is not None and empty > 0:
        rest = w * empty
        h = history.get(params.fill)
        if rest >= WEIGHT_QUANTUM and h is not None and h.index_of(data_date) is not None:
            t = target_from_close(params.fill, last_close(h, data_date), to_weight(rest))
            if t is not None:
                out.append(t)
    return tuple(out)


@dataclass
class LtrPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)


class LongTermReversalAllocator:
    """F4's book ranked on the multi-year return that skips the last year, losers first.

    Held symbols get no special treatment: a name that leaves the chosen set is signal-exited.
    """

    id = "M0069"

    def lookback(self, params: Any) -> int:
        # What the fixed instruments need (SPY's trend average, the 20-day volume window), not
        # the members' formation window: a member with fewer than factor_lookback bars is simply
        # not eligible yet and its slot holds SPY. Declaring the 1261-bar formation here would
        # push the run's start from 1996 to 1998 for the whole book.
        p = _check(params)
        return max(DV_N, p.inner.vol_n + 1, p.inner.trend[1] if p.inner.trend is not None else 0)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        out = {p.inner.trend[0]} if p.inner.trend is not None else set()
        if p.fill is not None:
            out.add(p.fill)
        return tuple(sorted(out))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.fill,) if p.fill is not None else ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return build(choose(rows, p), history, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> LtrPrepared:
        return LtrPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, LtrPrepared):
            raise TypeError(f"prepared must be LtrPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return build(choose(rows, p), prepared.history, data_date, p)


LTR = LongTermReversalAllocator()

F60 = FactorParams(rank="momentum", top=20, mom_n=1260, mom_skip=252, trend=None)  # months -60..-13
F36 = replace(F60, mom_n=756)  # months -36..-13
F60_N30 = replace(F60, top=30)
F60_T = replace(F60, trend=("SPY", 200))


def _v(suffix: str, params: LtrParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0069-{suffix}", family="M0069", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=LTR, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0069",
    name="Buy the long-term losers: big index members that fell furthest over the past three to five years, skipping the last year",
    family="stock-long-term-reversal",
    source_kind="paper",
    source_ref=(
        "De Bondt & Thaler (1985), Does the Stock Market Overreact?, Journal of Finance 40(3), "
        "793-805; see also https://faculty.georgetown.edu/qw50/LTR.pdf"
    ),
    parent_id=None,
    hypothesis=(
        "Published 1985, so the dev window 1996-2015 is already after the crowd knew it. Investors "
        "overreact over several years, so the index members that lost most over months -60..-13 "
        "(skipping the latest 12 months, to keep clear of momentum) rebound over the next one to "
        "three years. Each month, among point-in-time S&P 500 / Nasdaq-100 members priced at $5 or "
        "more with over 20M dollars traded a day (F4's screen, which keeps the book to big names), "
        "rank on that formation return and hold the 20 lowest equal weight, in fractional shares at "
        "Gotrade's real fees on monthly-hold-frac-gotrade; slots the screen cannot fill (names need "
        "five years of bars, so before about 1998 few qualify) hold SPY. Variants: L60-N20 (60-month "
        "formation, 20 names), L36-N20 (36-month formation), L60-N30 (30 names), L60-N20-T (the "
        "SPY 200-day switch: cash while SPY is below its average), and W60-N20 (the 20 long-term "
        "WINNERS: the control, which should trail the losers). The reserved idea's quarterly re-pick "
        "is not run: the lab has no quarterly real-fee preset, and a five-year signal barely moves "
        "month to month. Success: a losers variant beats SPY TR on dev with the worst fall at or "
        "under 20%, the winners control does worse, and the edge holds in 2009-2015. Its monthly "
        "result should NOT move with the failed momentum books -- it is close to their opposite."
    ),
    expected_failure=(
        "The published evidence says long-term reversal lives in small and equal-weighted stocks "
        "and does not survive risk adjustment after about 2003; among big index members the losers "
        "are mostly the riskiest, most beaten-down companies, so the book may be nothing but extra "
        "market risk: deep falls in 2001-2002 and 2008 (a worst fall well over 20% without the "
        "switch), and a strong 2003 and 2009 rebound that makes the average look better than the "
        "ride. The store has no delisted names, so the losers that went on to die are missing and "
        "the ones that survived are exactly the rebounders: survivorship flatters this method more "
        "than almost any other, most of all in the low-coverage late 1990s. Expect L60-N20 to trail "
        "SPY in 2009-2015 once the 2009 bounce is past, and the switch variant to cut the fall but "
        "also the rebound the idea lives on."
    ),
    candidates=(
        _v("L60-N20", LtrParams(F60, side="losers"),
           "The 20 members that lost most over months -60..-13, always invested, SPY in empty slots"),
        _v("L36-N20", LtrParams(F36, side="losers"),
           "The 20 biggest losers over months -36..-13: the shorter formation, fills sooner"),
        _v("L60-N30", LtrParams(F60_N30, side="losers"),
           "The 30 biggest five-year losers: more names, less single-stock risk"),
        _v("L60-N20-T", LtrParams(F60_T, side="losers"),
           "The 20 biggest five-year losers while SPY is above its 200-day average, cash below"),
        _v("W60-N20", LtrParams(F60, side="winners"),
           "The 20 biggest five-year WINNERS: the control, expected to trail the losers"),
    ),
    seen_keys=(
        "concept:long-term-reversal",
        "concept:de-bondt-thaler-overreaction",
        "doi:10.1111/j.1540-6261.1985.tb05004.x",
    ),
)
