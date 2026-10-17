"""M0208 — Paper gains and paper losses: hold the stocks whose holders sit on the biggest gains.

Source: Grinblatt & Han (2005), Prospect theory, mental accounting, and momentum, Journal of
Financial Economics 78(2), 311-339.
Idea: holders sell winners too early and keep losers too long (the disposition effect). Selling
pressure on stocks with paper gains holds their price below value, and reluctance to sell stocks
with paper losses holds theirs above it, so as the gap closes a stock with a large *capital-gains
overhang* (price far above what its holders paid) drifts up and one with a large paper loss drifts
down. The paper finds the overhang predicts returns and that, once it is in the regression, past
returns (momentum) lose most of their power: momentum is a proxy for the overhang.

The overhang, on data date d (column ``j`` of SPY's session calendar):

    * weeks are five-session blocks ending at j, j-5, j-10, ...; week n's price is the close at
      its last column and its volume the sum over its five columns. Every number read is dated at
      or before d;
    * a name's weeks run back from the most recent until the first week with a missing close or
      volume, at most ``WEEKS`` (260, the paper's five years); fewer than ``MIN_WEEKS`` (156) and
      the name is not scored;
    * the reference price is the paper's: R = sum_n w_n P_n / sum_n w_n with
      w_n = tau_n * prod_(i<n) (1 - tau_i), week 0 the most recent. A share bought in week n still
      held today was bought then and not traded in any later week;
    * overhang = 1 - R / P_0.

Turnover. The paper's tau is weekly volume over shares outstanding; the store has no share counts.
Assumption, written before the run: tau_n = ``RATE`` x V_n / mean(V) over the name's own scored
weeks, clipped to [0, 0.99], with ``RATE`` = 2% a week (about 100% a year, the order of NYSE
turnover over 1996-2015). This keeps the paper's *timing* -- heavy weeks carry more of the cost
basis, later trading erases older purchases -- but gives every name the same average turnover, so
a stock that truly trades its float faster than another is not seen as having a younger basis. The
store's volume is split-adjusted (checked on AAPL's 7-for-1 in June 2014), so a split does not
fake a burst of turnover.

Which names. F4's screened members on d (the names the book may buy), exactly as M0203; a name
added to the index recently is in the pool only once it has three years of weekly history.

The book (``choose``), as M0203's frame: rank highest first, keep a held name while it ranks inside
``keep``, fill free slots from the top, ``top`` slots of 1/top each, unfilled slots in SPY, cash
while SPY is under its 200-day average when ``inner.trend`` is set.

``signal``: ``"high"`` holds the largest overhangs (the paper's long side); ``"low"`` the largest
paper losses (its short side, as a contrast -- it should lose); ``"hash"`` is the same-frame placebo
of M0187: the identical pool (only names with an overhang score on d), band, slots, fill and
switch, ordered by blake2b(seed | symbol | year-month).

Assumption, written before the run: the reserved idea also named a plain 12-1 momentum book in the
same frame as a contrast. It is left out on purpose, as M0203 left it out: the hard gate's
behaviour test (hardgate D14) reads every dev variant, and a plain momentum variant would move
with the test-failed momentum books and tie the whole method to them. The comparison with
momentum is made in the analysis against the lab's recorded real-fee momentum books.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees on the owner's
monthly deposits. Pure: no clock, randomness, files or network; reads only columns at or before d.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History, as_day
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
WEEK = 5  # sessions in a week
WEEKS = 260  # the paper's five years of weekly prices
MIN_WEEKS = 156  # three years: fewer and the name is not scored
RATE = 0.02  # assumed average weekly turnover (about 100% a year)
TAU_MAX = 0.99
SIGNALS = ("high", "low", "hash")


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class OverhangParams:
    """``inner`` is F4's screen, switch and book size; the rest is the signal and the band.

    ``inner.rank`` never selects here; ``"momentum"`` keeps the screened universe identical to
    M0007's, M0187's and M0203's, name for name.
    """

    inner: FactorParams
    keep: int = 40
    signal: str = "high"
    seed: int = 1
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name in ("keep", "seed"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.keep < self.inner.top:
            raise ValueError(f"keep must be >= top, got {self.keep} < {self.inner.top}")
        if self.signal not in SIGNALS:
            raise ValueError(f"signal must be one of {SIGNALS}, got {self.signal!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"keep": str(self.keep), "signal": self.signal, "seed": str(self.seed),
               "market": self.market, "week": str(WEEK), "weeks": str(WEEKS),
               "min_weeks": str(MIN_WEEKS), "rate": repr(RATE), "tau_max": repr(TAU_MAX)}
        if self.signal == "hash":
            out["hash"] = "blake2b-8"
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> OverhangParams:
    if not isinstance(params, OverhangParams):
        raise TypeError(f"params must be OverhangParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the weekly grid


@dataclass(frozen=True, slots=True, eq=False)
class WeekGrid:
    """Every symbol's closes and volumes on the market symbol's calendar, volume as prefix sums.

    ``vsum[k, t]`` is the sum of the finite volumes in columns < t and ``vcnt[k, t]`` their count,
    so week (e - 5, e] has volume vsum[e + 1] - vsum[e - 4] when its count is 5. A prefix sum
    through t reads columns <= t only, so the weeks are identical on history cut at d and on the
    whole history.
    """

    row: Mapping[str, int]
    dates: np.ndarray  # datetime64[D]
    close: np.ndarray  # (n_symbols, n_dates), NaN where the symbol has no bar that session
    vsum: np.ndarray  # (n_symbols, n_dates + 1)
    vcnt: np.ndarray  # (n_symbols, n_dates + 1) int64


def build_week_grid(history: Mapping[str, History], market: str) -> WeekGrid | None:
    m = history.get(market)
    if m is None or len(m) < 2:
        return None
    cal = m.dates
    ncal = len(cal)
    symbols = tuple(sorted(history))
    close = np.full((len(symbols), ncal), np.nan, dtype=np.float64)
    vol = np.full((len(symbols), ncal), np.nan, dtype=np.float64)
    for k, symbol in enumerate(symbols):
        h = history[symbol]
        if len(h) == 0:
            continue
        pos = np.searchsorted(cal, h.dates)
        inside = pos < ncal
        safe = np.where(inside, pos, 0)
        on_cal = inside & (cal[safe] == h.dates)
        c = np.asarray(h.close, dtype=np.float64)
        v = np.asarray(h.volume, dtype=np.float64)
        good = on_cal & np.isfinite(c) & (c > 0.0)
        close[k, safe[good]] = c[good]
        vgood = good & np.isfinite(v) & (v >= 0.0)
        vol[k, safe[vgood]] = v[vgood]
    ok = np.isfinite(vol)
    vsum = np.zeros((len(symbols), ncal + 1), dtype=np.float64)
    vsum[:, 1:] = np.cumsum(np.where(ok, vol, 0.0), axis=1)
    vcnt = np.zeros((len(symbols), ncal + 1), dtype=np.int64)
    vcnt[:, 1:] = np.cumsum(ok, axis=1)
    for a in (close, vsum, vcnt):
        a.setflags(write=False)
    return WeekGrid({s: k for k, s in enumerate(symbols)}, cal, close, vsum, vcnt)


# --------------------------------------------------------------------------- the signal


def overhangs(grid: WeekGrid, symbols: list[str], data_date: date) -> dict[str, float]:
    """Each symbol's capital-gains overhang on ``data_date``; a name short of history is left out."""
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day:
        return {}
    names = [s for s in symbols if s in grid.row]
    nweeks = min(WEEKS, (j + 1) // WEEK)
    if not names or nweeks < MIN_WEEKS:
        return {}
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)
    ends = j - WEEK * np.arange(nweeks)  # week 0 is the most recent
    price = grid.close[idx[:, None], ends[None, :]]
    vsum = grid.vsum[idx[:, None], ends[None, :] + 1] - grid.vsum[idx[:, None], ends[None, :] + 1 - WEEK]
    vcnt = grid.vcnt[idx[:, None], ends[None, :] + 1] - grid.vcnt[idx[:, None], ends[None, :] + 1 - WEEK]
    valid = np.isfinite(price) & (vcnt == WEEK)
    run = np.cumprod(valid, axis=1).astype(bool)  # weeks before the first gap
    m = run.sum(axis=1)
    out: dict[str, float] = {}
    for k in np.flatnonzero(m >= MIN_WEEKS):
        n = int(m[k])
        p = price[k, :n]
        v = vsum[k, :n]
        mean = float(v.mean())
        if not mean > 0.0:
            continue
        tau = np.clip(RATE * v / mean, 0.0, TAU_MAX)
        survive = np.concatenate(([1.0], np.cumprod(1.0 - tau)[:-1]))
        w = tau * survive
        total = float(w.sum())
        if not total > 0.0:
            continue
        ref = float((w * p).sum()) / total
        out[names[int(k)]] = 1.0 - ref / float(p[0])
    return out


def draw(seed: int, symbol: str, data_date: date) -> int:
    """The placebo's score: a fixed 64-bit hash of seed, symbol and the decision's month (M0187)."""
    key = f"{seed}|{symbol}|{data_date.year:04d}-{data_date.month:02d}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")


def scored(grid: WeekGrid, rows: list[FactorRow], data_date: date, p: OverhangParams) -> dict[str, float]:
    """Higher is better. The contrast flips the order; the placebo keeps the pool, not the order."""
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != p.market)
    g = overhangs(grid, pool, data_date)
    if p.signal == "high":
        return g
    if p.signal == "low":
        return {s: -v for s, v in g.items()}
    return {s: -float(draw(p.seed, s, data_date)) for s in g}


def choose(history: Mapping[str, History], rows: list[FactorRow], sc: Mapping[str, float],
           data_date: date, held: frozenset[str], p: OverhangParams) -> tuple[Target, ...]:
    """The band: held names ranked inside ``keep`` stay, the rest of ``top`` filled from the top."""
    order = sorted(sc, key=lambda s: (-sc[s], s))
    rank = {s: i for i, s in enumerate(order)}
    kept = sorted((s for s in held if rank.get(s, p.keep) < p.keep), key=lambda s: rank[s])
    picks = kept[: p.inner.top]
    for s in order:
        if len(picks) >= p.inner.top:
            break
        if s not in picks:
            picks.append(s)
    close = {r.symbol: r.close for r in rows}
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for s in picks:
        t = target_from_close(s, close[s], w)
        if t is not None:
            out.append(t)
    rest = Decimal(1) - w * len(out)
    mh = history.get(p.market)
    if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
        t = target_from_close(p.market, last_close(mh, data_date), rest)
        if t is not None:
            out.append(t)
    return tuple(out)


# --------------------------------------------------------------------------- the allocator


@dataclass(frozen=True, slots=True, eq=False)
class OverhangPrepared:
    """F4's rolling columns plus one weekly grid per market symbol, built on first use."""

    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    grids: dict[str, WeekGrid | None] = field(default_factory=dict, repr=False)

    def grid(self, market: str) -> WeekGrid | None:
        if market not in self.grids:
            self.grids[market] = build_week_grid(self.history, market)
        return self.grids[market]


class OverhangAllocator:
    """The ``top`` largest (or smallest) capital-gains overhangs among screened members, banded."""

    id = "M0208"

    def lookback(self, params: Any) -> int:
        # The screen's and the switch's need, as M0203: a name without three years of weekly
        # history is not scored yet and its slot holds SPY.
        return factor_lookback(_check(params).inner)

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

    def _targets(self, history: Mapping[str, History], rows: list[FactorRow],
                 grid: WeekGrid | None, data_date: date, held: frozenset[str],
                 p: OverhangParams) -> tuple[Target, ...]:
        if not rows or grid is None:
            return ()
        sc = scored(grid, rows, data_date, p)
        return choose(history, rows, sc, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return self._targets(history, rows, build_week_grid(history, p.market), data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> OverhangPrepared:
        return OverhangPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, OverhangPrepared):
            raise TypeError(f"prepared must be OverhangPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return self._targets(prepared.history, rows, prepared.grid(p.market), data_date, held, p)


OVERHANG = OverhangAllocator()

TREND = ("SPY", 200)
N20 = FactorParams(rank="momentum", top=20, trend=TREND)
N40 = FactorParams(rank="momentum", top=40, trend=TREND)


def _v(suffix: str, params: OverhangParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0208-{suffix}", family="M0208", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=OVERHANG, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0208",
    name=("Paper gains and paper losses: buy the stocks whose recent holders sit on the biggest "
          "unrealised gains"),
    family="stock-capital-gains-overhang",
    source_kind="paper",
    source_ref=("Grinblatt and Han (2005), Prospect theory, mental accounting, and momentum, "
                "Journal of Financial Economics 78(2)"),
    hypothesis=(
        "Holders who sell winners too early and keep losers too long (the disposition effect) hold "
        "prices below value after gains and above value after losses, so stocks with a large "
        "capital-gains overhang drift up. Each month-end, estimate each screened member's "
        "reference price as the turnover-weighted average of its past weekly closes (up to 260 "
        "weeks, at least 156; week n weighs its turnover times the share of it not traded in any "
        "later week), compute overhang = 1 - reference/price, and hold the 20 highest in equal 5% "
        "slots, monthly, keeping a holding while it ranks inside the top 40, unfilled slots in "
        "SPY, behind the SPY 200-day switch (F4's screen and switch, M0203's band). Turnover is "
        "proxied, as the store has no share counts: weekly volume over the name's own average "
        "weekly volume times 2% (about 100% a year), so the timing of trading is the paper's but "
        "every name gets the same average turnover. Grinblatt and Han published in 2005 (working "
        "paper 2001); about half the dev window predates it. Arms: CGO-N40 (40 names, band 80) and "
        "CGO-LOW-N20 (the 20 largest paper losses, the paper's losing side, which should trail). "
        "Control: HASH-N20, the same pool, band, slots, fill and switch in a fixed hash order "
        "(M0187's placebo). The plain 12-1 momentum contrast named when the idea was reserved is "
        "dropped, as in M0203: a momentum variant would tie the method to the test-failed momentum "
        "books through the behaviour test (hardgate D14); momentum is compared against the "
        "recorded real-fee momentum books instead. Fractional shares at Gotrade's real fees "
        "(monthly-hold-frac-gotrade) on the owner's monthly top-up. Success: beats SPY TR on dev "
        "with worst fall <= 25%, PF >= 1.3, a majority of walk-forward folds, a positive lead "
        "over SPY in 2009-2015, beats the placebo by at least 2 points a year, and the high side "
        "beats the low side."
    ),
    expected_failure=(
        "A large overhang mostly means the price rose a lot over the last one to three years, so "
        "the book is a slow momentum book under another name: it inherits momentum's 2009 crash "
        "(which the 200-day switch meets late) and, by the behaviour test, likely moves with the "
        "test-failed momentum books, which would make it unpromotable however it scores. The "
        "turnover proxy gives every stock the same average turnover, so it loses the part of the "
        "paper's signal that comes from heavily traded names refreshing their cost basis faster. "
        "The paper's spread is long-short across all US stocks, and much of the losing side's "
        "drift is in small, hard-to-short names the screen excludes; the long side alone in big "
        "index members may be close to the market. A published anomaly fades (insight on M0050), "
        "and equal slots lean small against SPY's big-company drift (insight 91), so 2009-2015 is "
        "likely to lag SPY even if the twenty-year average wins. The low-overhang contrast may "
        "not trail at all: deep paper losers in the index are also long-term losers, which "
        "reverse."
    ),
    candidates=(
        _v("CGO-N20", OverhangParams(N20, keep=40),
           "20 largest capital-gains overhangs, held while inside the top 40, behind the SPY "
           "200-day switch"),
        _v("CGO-N40", OverhangParams(N40, keep=80),
           "Same signal, 40 names, band 80: does width help a slow, crowded signal?"),
        _v("CGO-LOW-N20", OverhangParams(N20, keep=40, signal="low"),
           "Contrast: the 20 largest paper losses in the same frame; the paper says these trail"),
        _v("HASH-N20", OverhangParams(N20, keep=40, signal="hash"),
           "Placebo: the same pool, band, slots and switch in a fixed hash order"),
    ),
    seen_keys=(
        "concept:capital-gains-overhang",
        "concept:disposition-effect",
        "concept:turnover-weighted-reference-price",
    ),
)
