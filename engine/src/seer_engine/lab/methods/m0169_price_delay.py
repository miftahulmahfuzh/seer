"""M0169 — Slow-to-react big companies: the index members whose price catches up with the market late.

Source: Hou & Moskowitz (2005), "Market Frictions, Price Delay, and the Cross-Section of Expected
Returns", Review of Financial Studies 18(3), doi:10.1093/rfs/hhi023. The yearly, banded frame is
M0163's (F4's member screen, a keep band, December re-pick).
Idea: a stock whose weekly return still answers to last week's (or last month's) market move is a
stock investors are slow to look at. Hou and Moskowitz find the most delayed firms earn a premium
that absorbs much of the size and liquidity effects. Inside the S&P 500 / Nasdaq-100 the effect
should be weaker, but it needs only daily closes and SPY, and nothing in this lab ranks on it.

The signal. On a re-pick date d, take 57 sampling dates: SPY's own bar dates every fifth session
back from d (d, d-5, ..., d-280). That gives 56 "weekly" returns for SPY and, from each member's
last close on or before each sampling date, 56 for the member. A member needs a bar dated d and
bars back past the earliest sampling date. Regress the member's last 52 weekly returns on SPY's
same-week return alone (R2 restricted) and on SPY's same-week return plus its four previous weeks
(R2 full), both with an intercept. Delay = 1 - R2 restricted / R2 full: 0 when the lags add nothing,
near 1 when the stock answers mostly to old market news. A member whose R2 full is not positive
has no delay. Every member's regression shares the same design matrix (SPY's returns), so all of
them are one least-squares solve. Why every fifth session rather than calendar Fridays: SPY's bars
are the trading calendar, so five sessions is a trading week without a holiday rule, and the
sampling is the same on both paths.

The universe and the band are M0163's: F4's screen ($5, $20M 20-day dollar volume, a year of bars),
optionally cut to the ``pool`` most traded (``pool == 0`` keeps all of them). On the last close of
``repick_month`` the eligible rows are ranked by delay (``least`` flips the order: the control); a
held name ranked inside ``keep`` stays, the rest are sold, free slots filled from the top. Between
re-picks a holding leaves only when it stops being a member or loses its bar, its slot sitting in
SPY. A book holding no stock picks in full at once. With ``inner.trend`` set the whole book is cash
while SPY is under its 200-day average.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees, asked monthly.
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
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
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

ADDED = date(2026, 10, 17)
STEP = 5  # sessions per "week"
WEEKS = 52  # regression sample
LAGS = 4  # lagged market weeks in the full regression
SPAN = STEP * (WEEKS + LAGS)  # sessions back from d to the earliest sampling date


@dataclass(frozen=True, slots=True)
class DelayParams:
    """``inner`` is F4's screen, book size and optional switch; ``pool`` the most-traded cut (0 =
    all); ``keep`` the rank a holding must stay inside; ``least`` ranks the least delayed first
    (the control); ``repick_month`` the data month of the re-pick (0 means every month)."""

    inner: FactorParams
    pool: int = 0
    keep: int = 40
    least: bool = False
    repick_month: int = 12
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name in ("pool", "keep", "repick_month"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if not isinstance(self.least, bool):
            raise TypeError(f"least must be a bool, got {type(self.least).__name__}")
        if self.keep < self.inner.top or (self.pool and self.pool < self.keep):
            raise ValueError(f"need top <= keep <= pool, got {self.inner.top}, {self.keep}, {self.pool}")
        if not 0 <= self.repick_month <= 12:
            raise ValueError(f"repick_month must be in [0, 12], got {self.repick_month}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"pool": str(self.pool), "keep": str(self.keep), "least": str(self.least).lower(),
               "repick_month": str(self.repick_month), "market": self.market,
               "step": str(STEP), "weeks": str(WEEKS), "lags": str(LAGS)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> DelayParams:
    if not isinstance(params, DelayParams):
        raise TypeError(f"params must be DelayParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True, eq=False)
class DelayPrepared:
    history: Mapping[str, History]
    factor: FactorPrepared | None


def _r2(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """R2 of each column of ``y`` regressed on ``x`` (which carries the intercept)."""
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    dev = y - y.mean(axis=0)
    sst = (dev * dev).sum(axis=0)
    ssr = (resid * resid).sum(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return 1.0 - ssr / sst


def delays(history: Mapping[str, History], symbols: list[str], data_date: date,
           market: str) -> dict[str, float]:
    """Each symbol's price delay on ``data_date`` (symbols it cannot score are left out)."""
    mh = history.get(market)
    if mh is None:
        return {}
    i = mh.index_of(data_date)
    if i is None or i < SPAN:
        return {}
    idx = np.arange(i - SPAN, i + 1, STEP)
    when = mh.dates[idx]
    m = mh.close[idx]
    mret = m[1:] / m[:-1] - 1.0  # WEEKS + LAGS returns, oldest first
    cur = mret[LAGS:]
    x1 = np.column_stack([np.ones(WEEKS), cur])
    x5 = np.column_stack([np.ones(WEEKS), cur] + [mret[LAGS - k: LAGS - k + WEEKS] for k in range(1, LAGS + 1)])
    names: list[str] = []
    cols: list[np.ndarray] = []
    for s in symbols:
        h = history.get(s)
        j = None if h is None else h.index_of(data_date)
        if j is None or h.dates[0] > when[0]:
            continue
        pos = np.searchsorted(h.dates[: j + 1], when, side="right") - 1
        c = h.close[pos]
        if not bool(np.all(np.isfinite(c))) or bool(np.any(c <= 0.0)):
            continue
        names.append(s)
        cols.append((c[1:] / c[:-1] - 1.0)[LAGS:])
    if not names:
        return {}
    y = np.column_stack(cols)
    r1 = _r2(x1, y)
    r5 = _r2(x5, y)
    out: dict[str, float] = {}
    for k, s in enumerate(names):
        a, b = float(r1[k]), float(r5[k])
        if np.isfinite(a) and np.isfinite(b) and b > 0.0:
            out[s] = 1.0 - a / b
    return out


def ranked(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
           p: DelayParams) -> list[str]:
    """Eligible symbols ranked most delayed first (least delayed first with ``least``)."""
    pool = sorted((r for r in rows if r.symbol not in EXCLUDED and r.symbol != p.market),
                  key=lambda r: (-r.dollar_volume, r.symbol))
    if p.pool:
        pool = pool[: p.pool]
    score = delays(history, sorted(r.symbol for r in pool), data_date, p.market)
    sign = 1.0 if p.least else -1.0
    return [s for _, s in sorted((sign * v, s) for s, v in score.items())]


def choose(history: Mapping[str, History], members: AbstractSet[str], rows: list[FactorRow],
           data_date: date, held: frozenset[str], p: DelayParams) -> tuple[Target, ...]:
    stocks = sorted(s for s in held if s != p.market and s not in EXCLUDED)
    repick = not stocks or p.repick_month == 0 or data_date.month == p.repick_month
    if repick:
        order = ranked(history, rows, data_date, p)
        rank = {s: i for i, s in enumerate(order)}
        kept = [s for s in stocks if rank.get(s, p.keep) < p.keep]
        kept.sort(key=lambda s: rank[s])
        picks = kept[: p.inner.top]
        for s in order:
            if len(picks) >= p.inner.top:
                break
            if s not in picks:
                picks.append(s)
    else:  # between re-picks: keep every holding that is still a member with a bar today
        picks = [s for s in stocks if s in members][: p.inner.top]
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for s in picks:
        h = history.get(s)
        if h is None or h.index_of(data_date) is None:
            continue
        t = target_from_close(s, last_close(h, data_date), w)
        if t is not None:
            out.append(t)
    rest = Decimal(1) - w * len(out)
    mh = history.get(p.market)
    if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
        t = target_from_close(p.market, last_close(mh, data_date), rest)
        if t is not None:
            out.append(t)
    return tuple(out)


class DelayAllocator:
    """The screened members whose weekly price answers to the market latest, re-ranked yearly."""

    id = "M0169"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), SPAN + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_check(params).market,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: DelayPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: DelayParams) -> tuple[Target, ...]:
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        return choose(prepared.history, members, rows, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(DelayPrepared(history, None), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> DelayPrepared:
        return DelayPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, DelayPrepared):
            raise TypeError(f"prepared must be DelayPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


DELAY = DelayAllocator()


def _screen(top: int, trend: tuple[str, int] | None = None) -> FactorParams:
    return FactorParams(rank="momentum", top=top, trend=trend)  # the rank is unused: only the screen


def _v(suffix: str, params: DelayParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0169-{suffix}", family="M0169", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=DELAY, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


SW = ("SPY", 200)

METHOD = Method(
    id="M0169",
    name="Slow-to-react big companies: rank index members by how late their price catches up with the market",
    family="stock-price-delay",
    source_kind="paper",
    source_ref=(
        "Hou & Moskowitz (2005), Market Frictions, Price Delay, and the Cross-Section of Expected "
        "Returns, Rev. Financial Studies 18(3), doi:10.1093/rfs/hhi023"
    ),
    parent_id=None,
    hypothesis=(
        "Hou and Moskowitz (published 2005, so the dev window is half before and half after the "
        "paper) show that stocks whose weekly returns answer to market news with a lag earn a "
        "premium that absorbs much of the size and liquidity effects: investors neglect them. "
        "Among point-in-time S&P 500 / Nasdaq-100 members passing F4's $5 / $20M screen, on the "
        "last close of December regress each member's last 52 weekly returns (every fifth SPY "
        "session) on SPY's same-week return, and on that plus SPY's four previous weeks; delay = "
        "1 - R2(same week only) / R2(with lags). Hold the 20 most delayed at 1/20 each, keep a "
        "holding while it ranks inside the top 40 at the next December, a name leaving early "
        "only when it stops being a member (its slot in SPY); a book with no stock picks in full "
        "at once. Fractional shares at Gotrade's real fees on the owner's deposits. Variants: "
        "D20 (the idea, no switch), D20-SW (behind F4's SPY-200 switch), D40-SW (a 40-name rung, "
        "kept inside the top 80), L20-SW (control: the 20 least delayed, same band and switch), "
        "D20-BIG-SW (the most delayed within the 200 most traded only, to check the effect is "
        "not just small index members). Success: D20-SW beats total-return SPY with worst fall "
        "<= 25%, PF >= 1.3, a positive 2009-2015 edge and a majority of walk-forward folds, and "
        "L20-SW clearly trails it."
    ),
    expected_failure=(
        "Among liquid giants a 52-week delay estimate is mostly noise: the R2 ratio of a stock "
        "that barely tracks the market jumps around year to year, so the book is a random draw "
        "of low-correlation names. Where it is not noise, the most delayed index members are the "
        "smaller, thinner, less followed ones (and low-beta defensives), so the book quietly "
        "favours small companies and loses to SPY's big-company drift after 2009 (insight 91), "
        "and the dev store prices exactly those members worst, so survivorship flatters it "
        "(check lab survivorship). The published effect is a small-cap, pre-2000 effect, and it "
        "should fade after 2005. The BIG variant should then show nothing."
    ),
    candidates=(
        _v("D20", DelayParams(_screen(20), keep=40),
           "The 20 most delayed screened members, re-ranked each December, kept inside the top 40, no switch"),
        _v("D20-SW", DelayParams(_screen(20, SW), keep=40),
           "The same yearly banded delay book behind the SPY 200-day switch"),
        _v("D40-SW", DelayParams(_screen(40, SW), keep=80),
           "A 40-name rung: the 40 most delayed, kept inside the top 80, behind the switch"),
        _v("L20-SW", DelayParams(_screen(20, SW), keep=40, least=True),
           "Control: the 20 least delayed (the quickest to react), same band and switch"),
        _v("D20-BIG-SW", DelayParams(_screen(20, SW), pool=200, keep=40),
           "The 20 most delayed among only the 200 most traded members, behind the switch"),
    ),
    seen_keys=(
        "concept:price-delay",
        "concept:lagged-market-response",
        "concept:investor-neglect",
    ),
)
