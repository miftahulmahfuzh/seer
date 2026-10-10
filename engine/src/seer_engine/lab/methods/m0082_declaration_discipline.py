"""M0082 — Disciplined payers: big companies whose board declares the dividend on the same schedule every time.

Source: general knowledge (dividend smoothing, Lintner 1956; regular, predictable payout policy as
a sign of a board's confidence and governance). Batch sera-20261010-1742: M0076, M0077, M0078 and
M0081 found the declaration date worthless as an *earlier trigger*. This asks whether it is worth
something as a *quality filter* the ex-date alone cannot give.

On data date d, an F4-screened point-in-time member qualifies when it has at least ``count``
dividends in the last ``window_days`` and none of the last ``count`` is a cut (an amount below
``CUT`` times the one before it, in the bars' split-adjusted units). It is then scored by
``rank``:

    * ``"lead"``: the spread (population standard deviation, days) of the declaration-to-ex lead
      time over its last ``count`` dividends known on d (``announced_on``), every one of which
      must carry a declaration date. Low spread first.
    * ``"gap"``: the paired control, which reads no declaration data: the spread of the gaps
      between its last ``count`` ex-dates on or before d (``count - 1`` gaps). Low spread first.
    * ``"early"``: among ``"lead"``-qualified names whose lead spread is at most ``EARLY_SD``
      days, the longest median lead first (the boards that announce furthest ahead).

Ties go to held names, then the symbol. The first ``inner.top`` are held at equal weight
1/top, the rest of the book sits in SPY, and behind the SPY-200 switch the book is all cash while
SPY is below its 200-day average. Without the market's calendar nothing is targeted (the
market-aware allocator contract).
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from statistics import median, pstdev
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import T20, RaisePrepared
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 10)
CUT = Decimal("0.99")  # a payment below 99% of the one before it is a cut (rounding is not)
EARLY_SD = 3.0  # "early" ranks only boards whose lead spread is at most 3 days

Rank = Literal["lead", "gap", "early"]
_RANKS: tuple[str, ...] = ("lead", "gap", "early")


@dataclass(frozen=True, slots=True)
class DisciplineParams:
    """``inner`` is F4's screen, trend switch and book size; the rest defines the regularity score."""

    inner: FactorParams
    rank: Rank = "lead"
    count: int = 8
    window_days: int = 1095
    park: bool = True
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not isinstance(self.rank, str) or self.rank not in _RANKS:
            raise ValueError(f"rank must be one of {_RANKS}, got {self.rank!r}")
        if isinstance(self.count, bool) or not isinstance(self.count, int) or self.count < 4:
            raise ValueError(f"count must be an int >= 4, got {self.count!r}")
        if isinstance(self.window_days, bool) or not isinstance(self.window_days, int) or self.window_days < 365:
            raise ValueError(f"window_days must be an int >= 365, got {self.window_days!r}")
        if not isinstance(self.park, bool):
            raise TypeError(f"park must be a bool, got {type(self.park).__name__}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "rank": self.rank,
            "count": str(self.count),
            "window_days": str(self.window_days),
            "park": str(self.park).lower(),
            "market": self.market,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> DisciplineParams:
    if not isinstance(params, DisciplineParams):
        raise TypeError(f"params must be DisciplineParams, got {type(params).__name__}")
    return params


def _cut(amounts: list[Decimal]) -> bool:
    return any(b < a * CUT for a, b in zip(amounts, amounts[1:], strict=False))


def score(calendar: DividendCalendar, symbol: str, data_date: date, p: DisciplineParams) -> float | None:
    """The member's regularity score on ``data_date`` (lower ranks first), or None if it does not qualify."""
    since = data_date - timedelta(days=p.window_days)
    ann = calendar.announced_on(symbol, data_date)
    if p.rank == "gap":
        paid = sorted((a.ex_date, a.amount) for a in ann if since < a.ex_date <= data_date)
        if len(paid) < p.count:
            return None
        last = paid[-p.count:]
        if _cut([a for _, a in last]):
            return None
        return pstdev([(b[0] - a[0]).days for a, b in zip(last, last[1:], strict=False)])
    recent = [a for a in ann if a.known > since]
    if len(recent) < p.count:
        return None
    last = recent[-p.count:]
    if not all(a.declared for a in last) or _cut([a.amount for a in last]):
        return None
    leads = [(a.ex_date - a.known).days for a in last]
    spread = pstdev(leads)
    if p.rank == "lead":
        return spread
    if spread > EARLY_SD:
        return None
    return -float(median(leads))


def choose(history: Mapping[str, History], rows: list[FactorRow], calendar: DividendCalendar,
           data_date: date, held: frozenset[str], p: DisciplineParams) -> tuple[Target, ...]:
    scored: list[tuple[float, int, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED or r.symbol == p.market:
            continue
        s = score(calendar, r.symbol, data_date, p)
        if s is None:
            continue
        scored.append((s, 0 if r.symbol in held else 1, r.symbol, r))
    scored.sort(key=lambda t: (t[0], t[1], t[2]))
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for _, _, _, r in scored[: p.inner.top]:
        t = target_from_close(r.symbol, r.close, w)
        if t is not None:
            out.append(t)
    if p.park:
        rest = Decimal(1) - w * len(out)
        mh = history.get(p.market)
        if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
            t = target_from_close(p.market, last_close(mh, data_date), rest)
            if t is not None:
                out.append(t)
    return tuple(out)


class DeclarationDisciplineAllocator:
    """Members whose dividends arrive on the most regular schedule, never cut; rest SPY."""

    id = "M0082"
    market_fields = ("dividends",)

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.market,) if p.park else ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: RaisePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: DisciplineParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
            return ()
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        return choose(prepared.history, rows, prepared.calendar, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar, so no score and no target."""
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


DISCIPLINE = DeclarationDisciplineAllocator()

T40 = replace(T20, top=40)  # F4's screen and SPY-200 switch, 40 slots at 2.5%


def _v(suffix: str, params: DisciplineParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0082-{suffix}", family="M0082", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=DISCIPLINE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0082",
    name="Disciplined payers: big companies whose board declares the dividend on the same schedule every time",
    family="stock-dividend-declaration-discipline",
    source_kind="knowledge",
    source_ref=(
        "General knowledge: Lintner (1956) dividend smoothing; regular payout policy as a governance "
        "signal. Declaration dates from the one-month EODHD pull (2026-10-10). Batch sera-20261010-1742."
    ),
    parent_id=None,
    hypothesis=(
        "Not a published anomaly as such (dividend smoothing is from 1956; the declaration-schedule "
        "regularity score is this lab's), so there is no crowd date to fade from, but it sits close "
        "to the well-known low-volatility and dividend-quality tilts, which are crowded since ~2012. "
        "Four batch tests found the declaration date worthless as an earlier trigger. Use it instead "
        "as a quality filter: a board that declares on the same calendar every time, and never cuts, "
        "is a company whose cash flow is planned and safe. Among point-in-time S&P 500 / Nasdaq-100 "
        "members passing F4's $5 price and $20M dollar-volume screen with 8+ dividends in the last "
        "3 years, none of the last 8 cut (below 99% of the one before): rank on the spread (days) "
        "of the declaration-to-ex lead time over the last 8 payments, all 8 dated. Hold the 20 most "
        "regular at 5% (D-N20) or 40 at 2.5% (D-N40), monthly, fractional at Gotrade's real fees, "
        "the rest in SPY, behind the SPY-200 switch. Paired control, pre-registered: X-N20 / X-N40 "
        "rank on the spread of the gaps between the last 8 ex-dates and read no declaration data, "
        "so D minus X is the value of the data as a filter. D-EARLY-N20 asks a second question: "
        "among boards with lead spread of 3 days or less, the ones that announce furthest ahead. "
        "Success for the data: D beats X by half a point a year or more on funded CAGR at equal or "
        "lower worst fall, and holds up in 2009-2015. A pre-run data count (no returns): at "
        "mid-2000/2005/2012 about 205-280 qualifying members had all 8 payments dated; the lead "
        "spread's 10th percentile is 1.3-2.3 days and median 8-10 days, the ex-gap spread's 10th "
        "percentile 0.5 days, with 10-17 exact ties at 0 (ties go to held names, then the symbol). "
        "Assumed: a special dividend inside the window counts as a payment and can read as a cut "
        "after it (it disqualifies, which is the conservative side); split-adjusted amounts are "
        "comparable across a split."
    ),
    expected_failure=(
        "Regularity mostly marks big, steady, low-volatility payers (utilities, staples, REITs, "
        "old industrials): the filter may just re-create the calm-stock book under a new name, and "
        "lag SPY in 2009-2015 when growth led. D and X may pick largely the same companies, so the "
        "paired difference may be noise. The 20-name book is concentrated in a few sectors, so its "
        "worst fall may track utilities/financials (2008 banks were regular payers until they cut). "
        "A book of index members equal-weighted leans small next to SPY, the shape every strategy "
        "has lost on since 2018. Withholding tax on dividends is not modelled."
    ),
    candidates=(
        _v("D-N20", DisciplineParams(T20, "lead"),
           "20 members with the steadiest declaration-to-ex lead time, never cut; rest SPY"),
        _v("X-N20", DisciplineParams(T20, "gap"),
           "Paired control: 20 members with the steadiest ex-date spacing, no declaration data"),
        _v("D-N40", DisciplineParams(T40, "lead"),
           "40 steadiest declaration lead times at 2.5%: closer to the market's shape"),
        _v("X-N40", DisciplineParams(T40, "gap"),
           "Paired control: 40 steadiest ex-date spacings at 2.5%"),
        _v("D-EARLY-N20", DisciplineParams(T20, "early"),
           "Among boards with lead spread <= 3 days, the 20 that announce furthest ahead"),
    ),
    seen_keys=(
        "concept:dividend-declaration-regularity",
        "concept:dividend-payment-regularity",
        "concept:dividend-quality-filter",
    ),
)
