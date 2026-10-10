"""M0086 — A free head start for the momentum book: prefer picks whose dividend is still ahead of them.

Source: variation of M0079 (announcement-to-ex window, which fees ate); Hartzmark & Solomon
(2013), "The dividend month premium", JFE 109(3); Kalay & Loewenstein (1985), JFE 14(3).
Idea: keep the fee bill of a monthly book we already have and use the dividend calendar only to
re-order its ranking, so the tilt costs no extra trades. The batch question (sera-20261010-1742):
do the board's declaration dates make an existing method better than the ex-dates the lab
already had? Answered as a paired difference on one host.

Host: F4-MOM12-N20-TREND -- point-in-time S&P 500 / Nasdaq-100 members, the $5 price and $20M
daily dollar-volume screen, the 20 highest 12-1 momentum names at 5% each, all cash while SPY is
at or below its 200-day average (checked when the book re-picks, monthly), empty slots in cash.
``timing="off"`` reproduces it exactly: the same rows (``factor_rows`` / ``rows_on``), the same
order (momentum descending, symbol ascending), the same equal weights (``targets_from_rows``).

The tilt, on data date d with n eligible rows in host order (position k = 0 for the best):

    score = (1 - k / n) + tilt x (ahead - recent)

ranked by score descending, then k; the first ``top`` are held at ``equal_weight(top)``.

    * ``recent`` = 1 when one of the symbol's dividends went ex in its last ``recent_n`` sessions
      through d (ex-date on or after its bar ``recent_n - 1`` sessions back, and <= d). Ex-dates
      <= d are known in every timing, so this half is identical in both arms.
    * ``ahead`` = 1 when a dividend is expected to go ex after the next session and within
      ``ahead_days`` calendar days of it -- bought at the next open, it is held into its ex-date:
        - ``timing="announce"``: a dividend with a declaration date, declared on or before d
          (``announced_on``), whose ex-date is in that window -- known for certain;
        - ``timing="ex"`` (the paired control): the next ex-date *guessed* from the ex-dates
          already passed (``known_on``, ex <= d): the last one plus the median gap of the up to
          ``GAP_N`` latest ex-dates within ``GAP_DAYS`` of it (at least three, median gap >=
          ``MIN_GAP`` days) -- the best the lab could do before it had declaration dates (M0051).
    * ``declared_only``: in both timings, only dividends that carry a declaration date count, for
      ``ahead``, ``recent`` and the guess alike, so the pair reads the same dividends.

A tilt of 0.05 is about 20 places in a 400-name ranking whose top 20 are held: an ``ahead`` name
from the top ~10% displaces an un-tilted name near the bottom of the held 20, and a ``recent``
name needs the top of the list to stay (in practice it is skipped that month).

Without the market's calendar (the history-only path) nothing is targeted, in every timing, the
market-aware allocator contract.
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Literal

import numpy as np

from seer_engine import dates
from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    targets_from_rows,
    trend_on,
)

ADDED = date(2026, 10, 10)
GAP_DAYS = 730  # the ex-date rhythm: ex-dates within two years of the last one
GAP_N = 5  # the latest ex-dates whose gaps set the rhythm
MIN_GAP = 20  # a rhythm under 20 days is noise, not a schedule

Timing = Literal["off", "announce", "ex"]
_TIMINGS: tuple[str, ...] = ("off", "announce", "ex")


@dataclass(frozen=True, slots=True)
class TiltParams:
    """``inner`` is the host (F4's momentum book); the rest defines the dividend tilt."""

    inner: FactorParams
    timing: Timing = "off"
    tilt: float = 0.05
    ahead_days: int = 35
    recent_n: int = 10
    declared_only: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.inner.rank != "momentum" or self.inner.sizing != "equal":
            raise ValueError("the host is the equal-weight momentum book")
        if not isinstance(self.timing, str) or self.timing not in _TIMINGS:
            raise ValueError(f"timing must be one of {_TIMINGS}, got {self.timing!r}")
        if isinstance(self.tilt, bool) or not isinstance(self.tilt, float) or not 0.0 < self.tilt <= 1.0:
            raise ValueError(f"tilt must be a float in (0, 1], got {self.tilt!r}")
        for name in ("ahead_days", "recent_n"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise ValueError(f"{name} must be an int >= 1, got {v!r}")
        if not isinstance(self.declared_only, bool):
            raise TypeError(f"declared_only must be a bool, got {type(self.declared_only).__name__}")
        if self.timing == "off" and self.declared_only:
            raise ValueError("declared_only has no meaning without a tilt")

    def as_dict(self) -> dict[str, str]:
        out = {
            "timing": self.timing,
            "tilt": repr(self.tilt),
            "ahead_days": str(self.ahead_days),
            "recent_n": str(self.recent_n),
            "declared_only": str(self.declared_only).lower(),
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> TiltParams:
    if not isinstance(params, TiltParams):
        raise TypeError(f"params must be TiltParams, got {type(params).__name__}")
    return params


def passed_ex(calendar: DividendCalendar, symbol: str, data_date: date, declared_only: bool) -> list[date]:
    """``symbol``'s ex-dates on or before ``data_date``, ascending (dated dividends only if asked)."""
    if not declared_only:
        return [d for d, _ in calendar.known_on(symbol, data_date)]
    return sorted(a.ex_date for a in calendar.announced_on(symbol, data_date)
                  if a.declared and a.ex_date <= data_date)


def guess_next_ex(ex: list[date]) -> date | None:
    """The last ex-date plus the median gap of the latest ones, or None without a rhythm."""
    if not ex:
        return None
    last = ex[-1]
    since = last - timedelta(days=GAP_DAYS)
    recent = [d for d in ex if d >= since][-GAP_N:]
    if len(recent) < 3:
        return None
    gap = statistics.median((b - a).days for a, b in zip(recent, recent[1:]))
    if gap < MIN_GAP:
        return None
    return last + timedelta(days=round(gap))


def ahead(calendar: DividendCalendar, symbol: str, data_date: date, next_session: date,
          p: TiltParams) -> bool:
    """A dividend expected to go ex in ``(next_session, next_session + ahead_days]``."""
    end = next_session + timedelta(days=p.ahead_days)
    if p.timing == "announce":
        return any(a.declared and next_session < a.ex_date <= end
                   for a in calendar.announced_on(symbol, data_date))
    g = guess_next_ex(passed_ex(calendar, symbol, data_date, p.declared_only))
    return g is not None and next_session < g <= end


def recent(h: History, calendar: DividendCalendar, data_date: date, p: TiltParams) -> bool:
    """One of ``h``'s dividends went ex in its last ``recent_n`` sessions through ``data_date``."""
    i = h.index_of(data_date)
    if i is None:
        return False
    since: date = h.dates[max(0, i - p.recent_n + 1)].item()
    ex = passed_ex(calendar, h.symbol, data_date, p.declared_only)
    return any(since <= d <= data_date for d in ex[-3:])


def tilted(history: Mapping[str, History], rows: list[FactorRow], calendar: DividendCalendar,
           data_date: date, p: TiltParams) -> list[FactorRow]:
    """``rows`` re-ordered by the tilted score (host order when the tilt is off)."""
    order = sorted((r for r in rows if r.symbol not in EXCLUDED), key=lambda r: (-r.momentum, r.symbol))
    if p.timing == "off" or not order:
        return order
    n = len(order)
    nxt = dates.next_session(data_date)
    scored: list[tuple[float, int, FactorRow]] = []
    for k, r in enumerate(order):
        s = 1.0 - k / n
        h = history.get(r.symbol)
        if ahead(calendar, r.symbol, data_date, nxt, p):
            s += p.tilt
        if h is not None and recent(h, calendar, data_date, p):
            s -= p.tilt
        scored.append((s, k, r))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [r for _, _, r in scored]


@dataclass
class TiltPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared | None = field(repr=False)
    calendar: DividendCalendar = field(repr=False)


class DividendAheadTilt:
    """F4's momentum book, its ranking nudged toward dividends ahead and away from ones just paid."""

    id = "M0086"
    market_fields = ("dividends",)  # reads Market.dividends, never Market.fundamentals

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return () if p.inner.trend is None else (p.inner.trend[0],)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: TiltPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: TiltParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no calendar: target nothing (market-aware contract)
            return ()
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        top = tilted(prepared.history, rows, prepared.calendar, data_date, p)[: p.inner.top]
        # targets_from_rows re-ranks by momentum; with the tilt off that is the host's own pick,
        # with it on the chosen set is already fixed, so only the order of the targets changes.
        return targets_from_rows(top, p.inner)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar, so no target."""
        return self._run(TiltPrepared(history, None, EMPTY_DIVIDENDS), members, data_date, held,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> TiltPrepared:
        return TiltPrepared(history, prepare_factor(history), EMPTY_DIVIDENDS)

    def prepare_market(self, market: Any) -> TiltPrepared:
        calendar = getattr(market, "dividends", EMPTY_DIVIDENDS)
        if not isinstance(calendar, DividendCalendar):
            raise TypeError(f"market.dividends must be a DividendCalendar, got {type(calendar).__name__}")
        return TiltPrepared(market.history, prepare_factor(market.history), calendar)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, TiltPrepared):
            raise TypeError(f"prepared must be TiltPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


TILT = DividendAheadTilt()


def _v(suffix: str, params: TiltParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0086-{suffix}", family="M0086", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=TILT, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0086",
    name="A free head start for the momentum book: prefer picks whose dividend is still ahead of them",
    family="stock-dividend-announcement-window",
    source_kind="variation",
    source_ref=(
        "variation of M0079 (announcement-to-ex window); Hartzmark & Solomon (2013), The dividend "
        "month premium, JFE 109(3); Kalay & Loewenstein (1985), JFE 14(3); host F4-MOM12-N20-TREND; "
        "declaration dates from the one-month EODHD pull (2026-10-10)"
    ),
    parent_id="M0079",
    hypothesis=(
        "Published 1985 (announcement-to-ex drift) and 2013 (dividend month premium), so both were "
        "public for all or most of the dev window. M0079 showed a daily announcement-to-ex book "
        "cannot pay Gotrade's fees; its ex-date control fell hardest because it held stocks right "
        "after they went ex. So keep an existing monthly book's fee bill and use the calendar only "
        "to re-order its ranking. Host: the plain 12-month momentum book (F4-MOM12-N20-TREND: "
        "F4's members and liquidity screen, top 20 by 12-1 momentum at 5% each, cash while SPY is "
        "at or below its 200-day average, checked monthly, never weekly -- the weekly switch cost "
        "3-5 points a year in M0076/M0078), monthly, fractional, Gotrade's real fees. Tilt: score "
        "= momentum percentile + 0.05 when a dividend goes ex after the next session and within "
        "35 days of it, - 0.05 when one went ex in the last 10 sessions (about 20 places in a "
        "400-name ranking). Variants: HOST (no tilt; reproduces the host exactly, checked against "
        "FACTOR's own targets before the run); TILT-ANN (the ahead half from declared dividends, "
        "known for certain); TILT-EX (the paired control: the ahead half guessed from past "
        "ex-dates, last ex plus the median gap -- all the lab had before); TILT-ANN-D / TILT-EX-D "
        "(the same pair counting only dividends that carry a declaration date, so coverage cannot "
        "blur it). The recently-ex half reads only passed ex-dates, identical in both arms, so "
        "ANN minus EX isolates what the declaration date adds. Reported: paired ANN minus EX on "
        "funded CAGR, worst fall, DSR, 2009-2015 and the walk-forward folds, with a t-stat on the "
        "de-funded monthly differences. A definite yes for the data: TILT-ANN beats TILT-EX by a "
        "point a year or more with monthly t >= 2, and the dated pair agrees in sign. A definite "
        "no: |t| < 2, or the sign flips between the pairs or in 2009-2015."
    ),
    expected_failure=(
        "A tilt of 20 places swaps perhaps 3-6 of 20 names a month, and a dividend's run-up is a "
        "fraction of a percent, so ANN minus EX is likely well under a point a year and |t| < 1: "
        "the ex-date guess already gets most quarterly payers' next date right within a week or "
        "two, so the arms pick mostly the same names. Momentum winners are often non-payers or "
        "low payers, so the tilt bites on fewer names than in a calm-stock book. M0076, M0078, "
        "M0079 and M0083 all found the declaration date added nothing or a little negative, and "
        "M0079 found announcement timing slightly negative in 2009-2015, so the most likely answer "
        "is no. The host's own weaknesses carry over: the plain momentum book fell about 22% at "
        "its worst (over the 20% limit) and lagged SPY in 2009-2015 when big-company growth led; "
        "a tilt toward payers moves it toward value-ish names, which hurts in 1998-2000 and from "
        "2009. Withholding tax on the dividends the tilt collects is not modelled."
    ),
    candidates=(
        _v("HOST", TiltParams(N20, timing="off"),
           "The plain 12-month momentum book (F4-MOM12-N20-TREND) at real fees, no tilt"),
        _v("TILT-ANN", TiltParams(N20, timing="announce"),
           "Up 0.05 when a declared dividend goes ex within 35 days; down 0.05 if ex in the last 10 sessions"),
        _v("TILT-EX", TiltParams(N20, timing="ex"),
           "Paired control: the next ex-date guessed from past ex-dates; same down-tilt"),
        _v("TILT-ANN-D", TiltParams(N20, timing="announce", declared_only=True),
           "TILT-ANN counting only dividends that carry a declaration date"),
        _v("TILT-EX-D", TiltParams(N20, timing="ex", declared_only=True),
           "TILT-EX counting only dividends that carry a declaration date"),
    ),
    seen_keys=(
        "concept:dividend-ahead-tilt",
        "concept:dividend-month-premium-tilt",
        "concept:dividend-announcement-timing",
    ),
)
