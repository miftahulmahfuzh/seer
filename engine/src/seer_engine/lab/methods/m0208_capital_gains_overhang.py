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

Amendment 1 (2026-10-19). ``HASH-N20`` above is the placebo this method quoted its margin
against, and it is mis-shaped: it trades 4.41 times and turns over 5.20 times ``CGO-N20``, the
widest miss of the fourteen D17 refuses. The cause is in ``draw`` below -- M0187's hash is re-keyed
on the decision's month, so the placebo's whole ordering is independent from one month to the
next, while the overhang score it stands in for moves by four weekly blocks out of 260 and
scarcely changes. The ``keep`` band is then hysteresis for the real book and a one-in-ten lottery
for the placebo, and the placebo rebuilds itself every month. ``CGO-N20-PLC`` replaces it with the
same pool, the same twenty 1/20 slots, the same band and the same switch, drawing each month only
as many fresh names as ``CGO-N20``'s own banded selection replaced that month
(``lab.control_draw``). Nothing above this paragraph changes: ``HASH-N20``'s trial is recorded and
stays exactly as it was measured.

Amendment 2 (2026-10-20). ``CGO-N20-PLC`` above is an honest draw and it is still not a match: it
trades 455 times against ``CGO-N20``'s 624 and turns over 2.313 against 3.061, 0.73x and 0.76x,
inside D17's refuse band and outside its match band. The cause is in the stand-in, not in the
draw. ``MatchedDrawAllocator`` has no record of what ``CGO-N20`` actually held -- no allocator
does -- so it reconstructs the previous held set from the plain top twenty at the previous month
end. A freshly taken top twenty is ranked 1-20 and the band drops a name only past rank 40, so
almost nothing falls out of it; the real held set has accumulated names that entered near the top
and have since drifted toward the edge, and those fall out far faster. Measured over all 169
decisions with the switch on and a scored pool: 304 estimated entries against 624 real, 0.487x,
uniform across 1996-2002, 2003-2008 and 2009-2015 (0.444 / 0.509 / 0.500). ``CGO-N20-PLC2``
replaces the stand-in with a bounded replay: start from an empty book a fixed number of decisions
back and apply ``CGO-N20``'s own band, its own switch and its own ranking forward, one decision at
a time, to reconstruct the drifted set the book is actually coming into this decision with. The
draw itself, the pool, the twenty 1/20 slots, the band, the switch and the SPY fill are all
unchanged. Nothing above this paragraph changes: ``HASH-N20``'s and ``CGO-N20-PLC``'s trials are
recorded and stay exactly as they were measured.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees on the owner's
monthly deposits. Pure: no clock, randomness, files or network; reads only columns at or before d.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.control_draw import (
    lookback_for,
    matched_names,
    shadow_lookback_for,
    shadow_selection,
)
from seer_engine.lab.method import Amendment, Method
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


# ------------------------------------------------------------- amendment 1: the matched draw
#
# Why a copy of the band and not a refactor of ``choose``. ``choose`` above is the rule four
# recorded trials (677-680) ran under. Its body is outside ``config_digest`` -- a digest is rules,
# allocator id and params -- so Python would let it be refactored and nothing would complain, and
# that is exactly the trap: a recorded arm's behaviour would have moved because a later amendment
# wanted to share its lines. The band is therefore written out again here, used only by the
# matched draw, and ``choose`` is left byte-identical.

A1_ADDED = date(2026, 10, 19)


def _banded_picks(order: Sequence[str], held: AbstractSet[str], top: int, keep: int) -> list[str]:
    """``choose``'s band as a plain symbol list: who the real book would hold, given ``held``.

    Identical rule, written out rather than shared (see the note above): a held name ranked inside
    ``keep`` stays, in rank order, at most ``top`` of them, and the free slots are filled from the
    top of ``order``. A name ``order`` does not score is not held (``rank.get(s, keep)``).
    """
    rank = {s: i for i, s in enumerate(order)}
    kept = sorted((s for s in held if rank.get(s, keep) < keep), key=lambda s: rank[s])
    picks = kept[:top]
    for s in order:
        if len(picks) >= top:
            break
        if s not in picks:
            picks.append(s)
    return picks


def _book(history: Mapping[str, History], rows: list[FactorRow], picks: Sequence[str],
          data_date: date, p: OverhangParams) -> tuple[Target, ...]:
    """``choose``'s tail for an already-chosen list: 1/``top`` each, the remainder in the market.

    The same slots, the same SPY fill and the same unfilled-slot behaviour as the arm this draw
    controls, so the only thing that differs between the two books is which names are in them.
    """
    close = {r.symbol: r.close for r in rows}
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for s in picks:
        c = close.get(s)
        if c is None:
            continue
        t = target_from_close(s, c, w)
        if t is not None:
            out.append(t)
    rest = Decimal(1) - w * len(out)
    mh = history.get(p.market)
    if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
        t = target_from_close(p.market, last_close(mh, data_date), rest)
        if t is not None:
            out.append(t)
    return tuple(out)


def previous_month_end(grid: WeekGrid, data_date: date) -> date | None:
    """The last session before ``data_date``'s calendar month, on the market symbol's calendar.

    A monthly rank session is the first NYSE session of a calendar month (``sim.rules._first_of``)
    and the allocator is handed the session before it, so on this chassis every decision's
    ``data_date`` is a month's last session and the previous decision's is the last session of the
    month before. Derived from the calendar rather than stepped back a fixed 21 sessions, so a
    short month and a holiday both land right.

    Only columns strictly before the first of ``data_date``'s month are read, so the answer is the
    same on a history cut at ``data_date`` as on the whole history (the P4 identity), and it can
    see nothing ``data_date`` could not. None before the calendar starts.
    """
    first = np.datetime64(date(data_date.year, data_date.month, 1))
    i = int(np.searchsorted(grid.dates, first, side="left")) - 1
    if i < 0:
        return None
    out = grid.dates[i].astype(object)  # datetime64[D] -> datetime.date
    return out if isinstance(out, date) else None


class MatchedDrawAllocator(OverhangAllocator):
    """``CGO-N20``'s shape with none of its identity: the honest placebo (D17, 2026-10-19).

    Everything but the names is the arm it controls, and it inherits that literally:
    ``OverhangAllocator``'s own ``symbols``, ``holds``, ``uses_members``, ``prepare`` and both
    target entry points, so the screen, the SPY 200-day switch, the weekly grid and the
    SPY-remainder fill are the same code and not a re-implementation of it. Only ``_targets``,
    ``lookback`` and ``id`` differ, and ``_targets`` only in which twenty names come out.

    The draw, each decision session:

        * the pool is ``scored``'s -- the screened members with an overhang value on ``data_date``,
          exactly the pool ``CGO-N20`` picks from;
        * ``picks_prev`` is the real signal's plain top ``top`` at the previous decision session
          (``previous_month_end``), and ``picks_real`` is the real band applied to it, so
          ``len(set(picks_real) - set(picks_prev))`` is how many names ``CGO-N20``'s own hysteresis
          lets through this month. One step of the band unrolled: enough to carry the hysteresis,
          and it needs no record of what the real book actually held, which no allocator has;
        * ``control_draw.matched_names`` keeps that many fewer of its own ``held`` names in a
          date-free hash order and draws the rest blind in a month-keyed one, taking names it
          does not hold ahead of the ones it is dropping so a just-released name is not
          immediately taken back.

    The pool goes to the helper in **symbol** order, never in score order, so no part of the real
    ranking can reach the draw through a tie-break.

    Membership is ``data_date``'s at both dates: ``rows`` is read once, at ``data_date``, and used
    for the previous session's score too. Deliberate, and it looks ahead at nothing -- today's
    member list is known today. It means the entry count measures the *signal's* churn and not the
    index's, which is the right thing, because the control draws from today's pool either way.

    ``lookback`` is the inherited one widened by ``control_draw.PREVIOUS_DECISION_BARS``, because
    this allocator reads its signal at the previous decision as well as at this one (plan
    invariant 11: the slack is the module's constant, never a number guessed per file). It costs
    nothing here -- this arm declares only SPY, whose store history opens in 1993, and
    ``backtest.dev.candidate_window`` floors a member-reading candidate at ``MEMBERSHIP_START``
    -- so the trial's window is ``CGO-N20``'s own.

    ``signal`` must be ``"high"``: this arm shadows the paper's long side, and the params say which
    arm it shadows. A ``"hash"`` or ``"low"`` params value would be a placebo of a placebo or of
    the contrast, which is not what was pre-registered.
    """

    id = "M0208-A1"

    def lookback(self, params: Any) -> int:
        return lookback_for(factor_lookback(_check(params).inner))

    def _targets(self, history: Mapping[str, History], rows: list[FactorRow],
                 grid: WeekGrid | None, data_date: date, held: frozenset[str],
                 p: OverhangParams) -> tuple[Target, ...]:
        if not rows or grid is None:
            return ()
        if p.signal != "high":
            raise ValueError(
                f"the matched draw shadows the high-overhang book, so signal must be 'high', "
                f"got {p.signal!r}"
            )
        sc = scored(grid, rows, data_date, p)
        if not sc:
            return _book(history, rows, (), data_date, p)
        order = sorted(sc, key=lambda s: (-sc[s], s))
        picks_prev: tuple[str, ...] = ()
        before_date = previous_month_end(grid, data_date)
        if before_date is not None:
            before = scored(grid, rows, before_date, p)
            picks_prev = tuple(sorted(before, key=lambda s: (-before[s], s))[: p.inner.top])
        picks_real = _banded_picks(order, frozenset(picks_prev), p.inner.top, p.keep)
        drawn = matched_names(
            pool=tuple(sorted(sc)),
            held=held,
            real_now=picks_real,
            real_prev=picks_prev,
            tag="M0208",
            seed=p.seed,
            data_date=data_date,
        )
        return _book(history, rows, drawn, data_date, p)


MATCHED = MatchedDrawAllocator()


def _a1(suffix: str, params: OverhangParams, rationale: str,
        supersedes: tuple[str, ...]) -> Candidate:
    """An amendment candidate, with the declaration of which recorded arm it replaces.

    ``supersedes`` is what D17 reads (``control_shape.SUPERSEDES_ATTR``): declared, never
    inferred from the target, and outside ``config_digest`` because ``config_text`` names its
    three attributes by hand. An arm that declares nothing retires nothing, so omitting it would
    leave M0208 blocked on HASH-N20 after the measurement had been taken."""
    return Candidate(id=f"M0208-{suffix}", family="M0208", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MATCHED, params=params, rationale=rationale, added=A1_ADDED,
                     owner_inputs=(), supersedes=supersedes)


MATCHED_DRAW = Amendment(
    added=A1_ADDED,
    why=(
        "HASH-N20 trades 4.41 times and turns over 5.20 times the book it controls, so the margin "
        "quoted against it is not evidence; draw the same book blind at CGO-N20's own monthly "
        "entry count instead"
    ),
    hypothesis=(
        "Written before the run, and before any result for this arm was seen. The standing "
        "sentence about this method is that CGO-N20 beats its placebo by +5.87 points a year on "
        "the owner's deposits -- 13.88% against HASH-N20's 8.01%, where SPY TR on the same "
        "deposits earned 7.19% -- and the method's own success condition asks for at least 2 "
        "points. That margin was quoted against an opponent carrying a different fee bill: "
        "HASH-N20's hash order is re-keyed every month, so its whole book is redrawn at each "
        "decision while the overhang ranking it stands in for scarcely moves, and it recorded "
        "2749 trades and 15.910 turnover against 624 and 3.061. CGO-N20-PLC is the same pool, the "
        "same twenty 1/20 slots, the same keep-40 band and the same SPY 200-day switch, drawing "
        "each month only as many fresh names as CGO-N20's own band let through. Predicted "
        "direction, which is the whole point of writing this first: the honest placebo trades "
        "about a quarter as often, pays about a quarter of the fees, holds its names long enough "
        "to collect the market's own drift, and therefore EARNS MORE. Its money return rises from "
        "8.01% to somewhere in 10-13% a year and the +5.87 point margin NARROWS to under 3 "
        "points -- below the 2-point bar this method set itself as often as not. A reversal, the "
        "blind draw beating CGO-N20 outright, is an admissible outcome of this prediction and "
        "would say the overhang adds nothing to a twenty-name equal-slot book behind the SPY "
        "switch. Whatever the number is, it is reported and the arm is not drawn again: this is "
        "one re-draw of one book, and a second one would only ever be justified by the shape "
        "missing its band, never by the margin coming out wrong."
    ),
    expected_failure=(
        "The way this prediction is wrong, stated so it can be recognised: CGO-N20-PLC lands near "
        "8% again and the margin stays above 5 points. That would mean the overhang signal "
        "carries the whole gap and the fee bill was a side-show -- that HASH-N20's five times "
        "turnover was costing it almost nothing a quarter-speed draw recovers, and the "
        "handicap was cosmetic rather than real. The second way to fail is on shape rather than "
        "on money: CGO-N20's churn is read through one unrolled step of its own band, with the "
        "previous month's plain top twenty standing in for what the real book actually held, and "
        "if the real hysteresis is stronger than that unroll says, the new arm lands above 1.25x "
        "on trades and the match is not clean. The band is also weaker early in the window, when "
        "the pool is small and 156 weeks of history exclude many members, so the first years may "
        "churn harder than the last. A shape miss is reported as a shape miss and the quoted "
        "margin stays provisional; it is not a reason to try another seed."
    ),
    candidates=(
        _a1("CGO-N20-PLC", OverhangParams(N20, keep=40),
            "Placebo for CGO-N20: the same pool, slots, band and switch, filled in a hash order "
            "at the real book's own monthly entry count",
            supersedes=("M0208-HASH-N20",)),
    ),
)


# --------------------------------------------- amendment 2: the matched draw, under the shadow
#
# Why a second allocator id and not a widened A1. ``MatchedDrawAllocator`` drew trial 853 and is
# part of the record. Its body is outside ``config_digest`` -- a digest is rules, allocator id and
# params -- so Python would let it be widened and nothing would complain, and the recorded arm's
# behaviour would have moved because a later amendment wanted its lines. So the shadow gets its
# own id, exactly as the matched draw copied ``choose``'s band rather than refactoring it, and A1
# is left byte-identical.
#
# ``_banded_picks``, ``_book`` and ``previous_month_end`` are now read by TWO recorded allocators
# instead of one. They were already frozen; this makes them doubly so.

A2_ADDED = date(2026, 10, 20)

SHADOW_DEPTH = 2
"""How many decisions back the shadow starts from an empty book before replaying forward.

The number is a measurement, not a taste: it is the smallest depth whose replayed entry count
reaches 0.90 of ``CGO-N20``'s real entry count, read off the dev store before this amendment was
committed. Two steps read 592 entries against the real 624, 0.949x, where one step reads 446,
0.715x; and the ladder is flat above two -- 0.941, 0.950, 0.947, 0.950, 0.955, 0.954 at three
through eight -- so no deeper replay buys accuracy and every one of them costs lookback and run
time. The mechanism behind the step from one to two is the band itself: this book holds the top
twenty and drops a name only once it falls past rank forty, and a replay seeded one decision back
hands the band a fresh top twenty ranked one to twenty, from which almost nothing falls past
forty in a single month. The second step is what gives the intermediate book a month to drift
toward the edge, which is all the band needs to start evicting at the real book's rate.

It is also capped from above and the cap is absolute. ``lookback`` below is
``control_draw.shadow_lookback_for(factor_lookback(inner), SHADOW_DEPTH)`` = 253 + 26K, and
``labkit.smoke_market``'s fixture is 473 sessions, so K = 8 (461) fits and K = 9 (487) cannot run
at all -- ``shadow_lookback_for`` raises rather than returning a number no test can drive. At
K = 2 the arm asks for 305 bars and leaves 168 of headroom, so the cap is nowhere near binding
here. It costs this arm no window either: it declares only SPY, whose store history opens in
1993, and ``backtest.dev.candidate_window`` floors a member-reading candidate at
``MEMBERSHIP_START``, so the trial's window is ``CGO-N20``'s own and the number is comparable to
trials 677 and 853.

It lives HERE and not in ``control_draw`` on purpose. ``shadow_selection`` takes ``depth`` as a
required keyword-only argument with no default, because how far back a chassis's band has to be
rolled before its shadow stops moving is a property of that band and that ranking. The shared
module owns the mechanism; the method file owns the number.

It is deliberately a module constant and NOT a params field. ``OverhangParams`` is the dataclass
all five recorded M0208 arms are digested through, and ``registry._canon`` renders a dataclass by
``dataclasses.fields()``: one more field would move every one of those five recorded digests. The
record of this number is therefore the pre-registering commit's source sha, which
``method_amendments`` holds, plus this docstring -- which is the same record ``RATE`` and
``TAU_MAX`` have had since the method's first run.
"""


class ShadowDrawAllocator(OverhangAllocator):
    """``CGO-N20``'s shape with none of its identity, drawn against a REPLAYED held set.

    Everything but the stand-in is ``MatchedDrawAllocator``'s rule and most of it is literally
    ``OverhangAllocator``'s: this class inherits ``symbols``, ``holds``, ``uses_members``,
    ``prepare`` and both target entry points, so the screen, the SPY 200-day switch, the weekly
    grid and the SPY-remainder fill are the same code and not a re-implementation of it. Only
    ``_targets``, ``lookback`` and ``id`` differ, and ``_targets`` differs from A1's in exactly
    one place: where A1 reads a fresh top twenty at the previous month end, this reads a replay.

    **The replay, and why it is a fold and not carried state.** At each decision
    ``control_draw.shadow_selection`` walks ``SHADOW_DEPTH`` decisions back, starts from an empty
    book there, and applies ``CGO-N20``'s own band forward one decision at a time. The result is
    what the real book would hold coming into the previous decision, given that it had been
    running for ``SHADOW_DEPTH`` months. It is a PURE FUNCTION of the dates it is handed:
    ``backtest.dev.run_registry`` reuses one allocator object per id across candidates and across
    walk-forward folds, so any per-instance memory of a previous decision would leak between them
    and the arm would not be reproducible. Nothing is stored on ``self``.

    **The switch is part of the band, and that is the half A1 was missing.** On a decision where
    ``trend_on`` is false the real book holds nothing of the pool -- ``targets_prepared`` returns
    no targets and the book sells out -- so the replay resets the shadow to the empty set there,
    and the month the switch comes back on the real book re-enters its whole twenty. A1's fresh
    top twenty cannot see that: it hands the draw a full book at a date the real book was in cash,
    and reads two or three entries where the truth is twenty. Measured on the dev store before
    this block was committed: closing the switch inside a one-step replay carries the estimate
    from 304 entries to 446 on its own, before any extra depth is paid for.

    **The ``Replay`` seam.** ``shadow_selection`` wants a ``(date, held) -> (pool, book)``
    callable and derives its own calendar from ``control_draw.previous_decision_date``, which on
    this chassis is the same session ``previous_month_end`` returns -- the last session before the
    first of the month, read off the NYSE calendar instead of off SPY's own grid. The phase's
    pre-registration probe asserted that agreement over every one of the dev window's 238
    decisions, with no mismatch, before this file was committed.

    **The pool goes back through ``Replay`` in symbol order, never in score order**, so no part of
    the real ranking can reach the draw through a tie-break, and the entry count and the draw are
    counted against the SAME pool because one callable hands back both. ``rows`` is read once, at
    ``data_date``, and used for every replayed date too -- deliberate, and it looks ahead at
    nothing, because today's member list is known today and every earlier reading uses only prices
    dated at or before that earlier date. It means the entry count measures the SIGNAL's churn and
    not the index's, which is right: the control draws from today's pool either way.

    **No memo.** Consecutive decisions replay overlapping dates and a cache would pay for itself
    several times over. It is not written, because the only places to hang one are the allocator
    (forbidden -- see above) or ``OverhangPrepared`` (which ``targets`` does not have), and a draw
    that is cheap and reproducible beats a draw that is cheaper and conditionally reproducible.
    The cost is about ``SHADOW_DEPTH / 2`` times A1's, paid once.

    ``signal`` must be ``"high"``: this arm shadows the paper's long side, and the params say
    which arm it shadows. A ``"hash"`` or ``"low"`` value would be a placebo of a placebo or of
    the contrast, which is not what was pre-registered.
    """

    id = "M0208-A2"

    def lookback(self, params: Any) -> int:
        return shadow_lookback_for(factor_lookback(_check(params).inner), SHADOW_DEPTH)

    def _targets(self, history: Mapping[str, History], rows: list[FactorRow],
                 grid: WeekGrid | None, data_date: date, held: frozenset[str],
                 p: OverhangParams) -> tuple[Target, ...]:
        if not rows or grid is None:
            return ()
        if p.signal != "high":
            raise ValueError(
                f"the matched draw shadows the high-overhang book, so signal must be 'high', "
                f"got {p.signal!r}"
            )

        def replay(d: date, carried: AbstractSet[str]) -> tuple[Sequence[str], Sequence[str]]:
            """``CGO-N20``'s own decision at ``d``, given what the replay says it held before it.

            ``control_draw.Replay``: it hands back the pool it actually ranked AND the book it
            ranked out of it, so the entry count and the draw can never be counted against two
            different pools. The pool goes back in SYMBOL order so no part of the real ranking can
            reach the draw through a tie-break.

            The SPY 200-day switch is part of the band here and that is the half amendment 1 was
            missing: on a month where ``trend_on`` is false the real book held nothing of the
            pool, so this returns an empty book and ``shadow_selection`` reseeds the shadow to
            empty. A1's fresh top twenty cannot see that -- it hands the draw a full book at a
            date the real book was in cash, and reads two or three entries where the truth is
            twenty.
            """
            if not trend_on(history, d, p.inner):
                return (), ()
            at_d = scored(grid, rows, d, p)
            if not at_d:
                return (), ()
            back = sorted(at_d, key=lambda s: (-at_d[s], s))
            return tuple(sorted(at_d)), _banded_picks(back, carried, p.inner.top, p.keep)

        reading = shadow_selection(replay, data_date, depth=SHADOW_DEPTH)
        if not reading.real_now:
            return _book(history, rows, (), data_date, p)
        drawn = matched_names(
            pool=reading.pool,
            held=held,
            real_now=reading.real_now,
            real_prev=reading.real_prev,
            tag="M0208",
            seed=p.seed,
            data_date=data_date,
        )
        return _book(history, rows, drawn, data_date, p)


SHADOW = ShadowDrawAllocator()


def _a2(suffix: str, params: OverhangParams, rationale: str,
        supersedes: tuple[str, ...]) -> Candidate:
    """An amendment-2 candidate, with the declaration of which recorded arms it replaces.

    **This arm does NOT declare ``controls=`` (Decision D9), and the reason is measured.**
    ``control_shape.DECLARATION_ATTR = "controls"`` exists but no method file in the lab sets it,
    so the ``declared`` resolver rung never fires today. On M0208 it does not need to: a third
    placebo cannot become anybody's target, because ``_eligible_targets`` excludes placebo arms,
    and this amendment's tests assert the arm still resolves to ``M0208-CGO-N20`` on the ``stem``
    rung while neither earlier control's resolution moves. A ``controls=`` declaration here would
    be a new ``Candidate`` field exercised for the first time inside a recorded trial, which is a
    strictly worse place to find out it is wrong. *(It would be SAFE to add -- ``Candidate``
    already carries ``supersedes``, added the same way, and ``lab.method.config_text`` renders
    only rules + allocator id + params, so a new ``Candidate`` field is outside ``config_digest``
    by construction. It is simply not needed here.)*

    ``supersedes`` is what D17 reads (``control_shape.SUPERSEDES_ATTR``): declared, never inferred
    from the target, and outside ``config_digest`` because ``config_text`` names its three
    attributes by hand. It names BOTH earlier controls, because D17 supersedes a ``warn`` finding
    as well as a ``refuse`` one -- every margin written against either was quoted against an
    opponent of the wrong shape, and leaving one of a re-drawn pair unmarked would say the
    opposite. It retires neither unless this arm reads ``OK`` on both axes."""
    return Candidate(id=f"M0208-{suffix}", family="M0208", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SHADOW, params=params, rationale=rationale, added=A2_ADDED,
                     owner_inputs=(), supersedes=supersedes)


SHADOW_DRAW = Amendment(
    added=A2_ADDED,
    why=(
        "CGO-N20-PLC is an honest draw that is still not a match -- 455 trades against 624 and "
        "2.313 turnover against 3.061, 0.73x and 0.76x -- because it reconstructs the book's "
        "previous holdings from a fresh top twenty instead of the drifted set the book actually "
        "holds; replay the band forward from an empty book instead and draw against that"
    ),
    hypothesis=(
        "Written before the run, and before any result for this arm was seen. The standing "
        "sentence about this method is that CGO-N20 beat a meaningless book by AT LEAST 4.3 "
        "points a year - 13.879% against CGO-N20-PLC's 9.532% on the owner's deposits, where SPY "
        "TR on the same deposits earned 7.188% - published as a floor rather than a measurement, "
        "because even the fairest control the lab could draw still traded a quarter less than the "
        "book. This arm exists to turn that floor into a number, and the bar it has to clear is "
        "arithmetic and is written here before it runs: D17's match band is 0.80-1.25 inclusive "
        "on BOTH axes, so against 624 trades and 3.0614 turnover the arm must record AT LEAST "
        "500 trades and 2.4492 turnover, and at most 780 trades and 3.8268 turnover. On an "
        "equal-slot chassis turnover follows trades arithmetically - the recorded pair gives "
        "1.0362 turnover per trade against the book's - so the low side is set by the trade count "
        "and the high side by turnover, and the clean window is 500 to 752 trades. A warn arm "
        "retires nothing, so anything outside that window leaves the published sentence a floor. "
        "Predicted direction. The estimator was measured at 304 entries against the real book's "
        "624 - 0.487x, uniform across 1996-2002, 2003-2008 and 2009-2015 - and the two-step "
        "replay reads 592 against the same 624, 0.949x, on the dev store before this block was "
        "committed. The realised trade count will NOT rise in proportion, and that is the "
        "prediction's most falsifiable part: the draw keeps at most as many of its own names as "
        "are still in the pool, so a control name that leaves the index is forced out whatever "
        "the entry count says, and the realised figure is the sum over decisions of the larger of "
        "the two. That attrition already did half the work at 304 entries, lifting the recorded "
        "arm from 0.49 to 0.73, and it stops binding as the entry count rises. So the predicted "
        "landing is a RANGE and not a point: 560 to 700 trades, 0.90x to 1.12x, and 2.85 to 3.55 "
        "turnover, 0.93x to 1.16x - band-clean on both axes, with the high side the live risk and "
        "not the low one. Money: the arm trades more than CGO-N20-PLC did, pays more of Gotrade's "
        "fees for it, and therefore EARNS LESS than its 9.532%, somewhere in 8.5% to 9.5%, so the "
        "margin WIDENS from +4.346 to between 4.4 and 5.4 points and the word 'at least' comes "
        "out of the published sentence. A reversal - the control earning MORE than 9.532% - is an "
        "admissible outcome of this prediction and would say that the extra churn bought more of "
        "the dev store's survivorship lottery than it paid in fees, which is a mechanism this lab "
        "has already measured and declined to assign a sign to. Whatever the number is, it is "
        "reported and the arm is not drawn again: this is one re-draw of one book at one replay "
        "depth, and a second one would only ever be justified by the shape missing its band, "
        "never by the margin coming out wrong. And none of it promotes anything: hardgate.check "
        "tests the walk-forward folds, the promoted variant's own folds and the survivorship "
        "drawdown before D17, and immediately behind D17 stands the kin rule, where M0208's kin "
        "is M0002, which has already spent and failed its test-window look. A clean arm here "
        "changes the refusal message and not the answer."
    ),
    expected_failure=(
        "The ways this is wrong, stated so each can be recognised. First, on shape and high: the "
        "replay recovers the drift AND pool attrition stacks on top of it, so the arm lands above "
        "752 trades or above 3.8268 turnover and misses the band from the other side - the "
        "mirror of amendment 1's miss, and it would say the two effects are additive where this "
        "hypothesis says the larger of the two binds. Second, on shape and low: the replay depth "
        "is too shallow for a book whose names drift toward the band's edge over more months than "
        "the lookback can pay for, the arm lands under 500 trades again, and the honest reading "
        "is that a bounded replay is not the remedy on this chassis at all - at which point the "
        "published sentence stays a floor and the right next move is a different mechanism, not a "
        "deeper replay, because the ladder measured before this block was committed is flat from "
        "two steps to the eight-step lookback cap and buys nothing further. Third, on money: "
        "the margin barely moves, which would say the fee bill between 455 and 620 trades is "
        "worth well under a point a year and the whole 'floor' caveat was about a quantity too "
        "small to matter - a useful and slightly embarrassing result that should be written down "
        "as such. Fourth, the direction reverses and the honest control earns more rather than "
        "less; the lab has measured that an honest control's effect on a margin is not a bias of "
        "known sign but an arbitrary one, so this is the outcome the prediction is least "
        "entitled to be surprised by. A shape miss is reported as a shape miss and the quoted "
        "margin stays provisional; it is not a reason to try another seed, another depth, or "
        "another draw."
    ),
    candidates=(
        _a2("CGO-N20-PLC2", OverhangParams(N20, keep=40),
            "Placebo for CGO-N20, re-drawn: the same pool, slots, band and switch, filled in a "
            "hash order at the entry count of a replayed shadow of the real book's own holdings",
            supersedes=("M0208-CGO-N20-PLC", "M0208-HASH-N20")),
    ),
)


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
    amendments=(MATCHED_DRAW, SHADOW_DRAW),
    seen_keys=(
        "concept:capital-gains-overhang",
        "concept:disposition-effect",
        "concept:turnover-weighted-reference-price",
    ),
)
