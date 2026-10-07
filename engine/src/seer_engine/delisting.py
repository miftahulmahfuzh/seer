"""The delisting stress harness: the hazard the store records, and a Market with deaths injected.

Handover section 5 Q1; plan `DELISTING_STRESS_ROSTER_RULES_PLAN.md` phase 1. This module is the
measuring and perturbing half. `engine/scripts/delisting_stress.py` is the driver that runs a
Monte Carlo over it and solves for the break-even delisting return.

**Read-only, and structurally unable to be anything else.** It imports neither
``seer_engine.lab.store`` nor ``seer_engine.lab.runner``, so it cannot record a trial or move the
lab's N -- tests/test_delisting.py asserts that in the source and again in a fresh interpreter. It
opens no file, no database and no socket, and it writes nothing to ``engine/.research``: every
perturbation is a new in-memory ``Market``, so no ``config_digest`` moves and none of the 110
recorded trials is disturbed.

WHY THIS EXISTS. ``engine/scripts/survivorship_coverage.py`` measured how much of the index the
store can price -- 522 of 1,041 ever-members have no bars at all -- and compared the edge over
total-return SPY across eras of rising coverage. That contrast is confounded with market regime,
so it is evidence against the simple survivorship story and never proof the hole is harmless. The
test that isolates the mechanism injects the deaths the store is missing and asks how bad the
assumed loss has to be before the edge disappears.

WHY THE INJECTION NEEDS NO ENGINE CHANGE. Three facts, each verified in the running tree:

1. ``book_runner`` forms the ranking universe from ``membership.members_on(data_date)``, and the
   allocator keeps only the members with a bar on that date. A symbol whose bars stop is silently
   absent from every later ranking.
2. ``book_runner`` force-closes a held position whose bars have stopped, at its mark, reason
   "forced" (``sim.book.close_book_unpriced``). **The engine therefore already models a delisting,
   at a delisting return of exactly 0%**: the holder is paid the last price anyone saw. That
   assumption is invisible today only because no symbol in the store disappears mid-window.
3. ``Market`` is frozen and ``dataclasses.replace`` already swaps one of its fields inside
   ``backtest.dev._run`` (``fx``, for a window that opens before the first FX row). :func:`kill`
   swaps two: ``history`` and ``membership``.

So the whole perturbation is: truncate a symbol's ``History`` at its death date, rewrite that last
bar to ``close x (1 + r)``, and retire the symbol from the index the day after. The unchanged
engine does the rest.

TWO DELIBERATE CHOICES, both in the conservative direction (plan Decisions):

- **Who dies.** The priced survivors, at the measured hazard -- not the 404 missing names brought
  back with invented price paths. Fabricating 404 price histories would make up the one thing no
  free source can supply, and the invented prices, not the data, would drive the answer.
- **How they die.** Abruptly. The final bar is flat (open = high = low = close), so no stop, limit
  or intraday exit can fill above the death price and the book gets no chance to leave. That makes
  the resulting break-even return an upper bound on the damage, which is the honest direction for
  a test whose purpose is reassurance. ``decline_sessions > 1`` spreads the same loss over the
  last few bars as a visible decline -- the forewarned sensitivity, supported but not the default.

WHAT THE HAZARD IS, AND WHAT IT IS NOT. :func:`measure_hazard` counts the symbols whose last
membership interval ends inside the window and divides by the window's member-years. The hole
decomposes into two populations and only one of them is simulable: the names that left the index
inside the window and have no bars (the survivorship case proper, what this harness injects), and
the names that were still members at the window's end and have no bars at all (a thinner ranking
pool for twenty years, which no delisting injection can model, because the missing thing there is
a price path and not a death).

RANDOMNESS IS PASSED IN, NEVER MODULE-GLOBAL. Every entry point that draws takes a
``random.Random``, so a (seed, r) pair is reproducible on any machine, and the same seed kills the
same names on the same days at every assumed return -- which is what makes a grid of returns a
paired comparison rather than a pile of unrelated runs.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from random import Random

import numpy as np

from seer_engine.backtest.dev import DEV_END, MEMBERSHIP_START
from seer_engine.backtest.market import SPY, Market, Membership
from seer_engine.strategies.base import History

__all__ = [
    "Death",
    "Exposure",
    "Hazard",
    "MIN_PRICE",
    "WINDOW_END",
    "WINDOW_START",
    "YEAR_DAYS",
    "draw_deaths",
    "kill",
    "measure_hazard",
    "stressed",
    "survivors",
]

YEAR_DAYS = 365.25
"""Days in a year, Actual/365.25 -- the same convention as ``backtest.metrics.YEAR_DAYS``."""

MIN_PRICE = 1e-4
"""The floor every perturbed price is held at: one 4-dp price quantum.

``r = -1`` would otherwise produce a zero close, and the simulator divides by prices. A total loss
is therefore modelled as a hundredth of a cent, not as nothing, which costs four decimal places of
realism and buys an engine that cannot divide by zero.
"""

WINDOW_START = MEMBERSHIP_START
"""The first membership snapshot, 1996-01-02. Imported, never duplicated."""

WINDOW_END = DEV_END
"""The last dev session, 2015-10-16. Imported, never duplicated -- this harness never looks past it."""

ONE_DAY = timedelta(days=1)


def _as_date(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    return d


def _frozen(arr: np.ndarray) -> np.ndarray:
    """``arr`` made read-only, as ``strategies.base.history_from_bars`` makes its columns."""
    arr.setflags(write=False)
    return arr


# --------------------------------------------------------------------------- the hazard


@dataclass(frozen=True)
class Hazard:
    """What the store's own membership says about how often a member stops being priceable.

    Counted over ``[window_start, window_end]``. ``exits`` is the number of symbols whose LAST
    membership interval ends inside the window; ``unserved_exits`` is the subset with no bars at
    all, which is the population a free price feed drops and the one this harness re-injects.
    ``member_years`` is ``round(mean_members x window_years)``, with ``mean_members`` the mean
    membership count on 30 June of every year the window spans -- that is the arithmetic that
    reproduces the analysis's M2 measurement exactly.

    ``unrecorded_unserved`` and ``unserved_but_priced`` are cross-checks against the store's own
    ``unserved.csv``: the first lists ever-members with no bars that the file does not mention,
    the second lists symbols the file calls unserved that nevertheless have bars. Both are empty
    for the store on disk today. ``unrecorded_unserved`` is empty when no list was passed in,
    because silence is not a disagreement.
    """

    window_start: date
    window_end: date
    ever_members: int
    served: int
    unserved: int
    exits: int
    served_exits: int
    unserved_exits: int
    mean_members: float
    member_years: int
    exits_by_year: tuple[tuple[int, int], ...]
    unrecorded_unserved: tuple[str, ...] = ()
    unserved_but_priced: tuple[str, ...] = ()

    @property
    def window_years(self) -> float:
        """The window's length, Actual/365.25."""
        return (self.window_end - self.window_start).days / YEAR_DAYS

    @property
    def exit_rate(self) -> float:
        """Exits per member-year, counting every exit (the upper sensitivity, 5.1%/yr today)."""
        return self.exits / self.member_years

    @property
    def unserved_exit_rate(self) -> float:
        """Exits per member-year counting only the names with no bars (the base case, 4.0%/yr)."""
        return self.unserved_exits / self.member_years


def _last_end(
    intervals: Sequence[tuple[str, date, date | None]],
) -> dict[str, date | None]:
    """Symbol -> the latest end over its intervals; None when any one of them is still open.

    ``Membership`` holds one row per ``universe`` row, so a symbol in both indices appears twice
    and its intervals may overlap. A symbol has left the index only when every interval has closed.
    """
    out: dict[str, date | None] = {}
    for symbol, _start, end in intervals:
        if symbol not in out:
            out[symbol] = end
            continue
        seen = out[symbol]
        out[symbol] = None if (seen is None or end is None) else max(seen, end)
    return out


def measure_hazard(
    market: Market,
    *,
    unserved: Iterable[str] = (),
    window_start: date = WINDOW_START,
    window_end: date = WINDOW_END,
) -> Hazard:
    """How often an index member stopped being priceable, from ``market``'s own membership.

    ``unserved`` is the store's recorded ``unserved.csv`` list (``ResearchData.unserved``), used
    only for the two cross-check fields: the counting itself is done from
    ``market.membership.intervals`` and ``market.history``, so the result holds for any market,
    including a synthetic one in a test.

    Nothing here is hardcoded. Against the research store on disk it returns
    ``exit_rate == 5.091%`` and ``unserved_exit_rate == 4.002%`` over 10,096 member-years, which
    is the analysis's M2 measurement.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    _as_date("window_start", window_start)
    _as_date("window_end", window_end)
    if window_end <= window_start:
        raise ValueError(f"window_end {window_end} must be after window_start {window_start}")
    recorded = frozenset(unserved)
    ends = _last_end(market.membership.intervals)
    priced = frozenset(market.history)
    served = frozenset(s for s in ends if s in priced)
    missing = frozenset(ends) - served
    exits = {s: e for s, e in ends.items() if e is not None and window_start <= e <= window_end}
    by_year: Counter[int] = Counter(e.year for e in exits.values())
    counts = [
        len(market.membership.members_on(d))
        for d in (date(y, 6, 30) for y in range(window_start.year, window_end.year + 1))
        if window_start <= d <= window_end
    ]
    if not counts:
        raise ValueError(
            f"[{window_start}, {window_end}] spans no 30 June; the hazard needs at least one "
            "mid-year membership count"
        )
    mean_members = sum(counts) / len(counts)
    member_years = round(mean_members * ((window_end - window_start).days / YEAR_DAYS))
    if member_years <= 0:
        raise ValueError("the window holds no member-years; nothing can be measured over it")
    return Hazard(
        window_start=window_start,
        window_end=window_end,
        ever_members=len(ends),
        served=len(served),
        unserved=len(missing),
        exits=len(exits),
        served_exits=sum(1 for s in exits if s in served),
        unserved_exits=sum(1 for s in exits if s in missing),
        mean_members=mean_members,
        member_years=member_years,
        exits_by_year=tuple(sorted(by_year.items())),
        unrecorded_unserved=tuple(sorted(missing - recorded)) if recorded else (),
        unserved_but_priced=tuple(sorted(recorded & priced)),
    )


# --------------------------------------------------------------------------- who can die


@dataclass(frozen=True)
class Exposure:
    """One priced survivor's member-time: when it was both an index member and priceable.

    ``spans`` are inclusive ``[first, last]`` day ranges, ascending and disjoint, clipped to the
    measuring window and to the symbol's own bars. A hazard applies to ``years``; a death date is
    drawn uniformly over ``days``.
    """

    symbol: str
    spans: tuple[tuple[date, date], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol:
            raise ValueError(f"symbol must be a non-empty str, got {self.symbol!r}")
        if not isinstance(self.spans, tuple) or not self.spans:
            raise ValueError(f"{self.symbol}: spans must be a non-empty tuple")
        previous: date | None = None
        for item in self.spans:
            if not (isinstance(item, tuple) and len(item) == 2):
                raise TypeError(f"{self.symbol}: a span is (first, last), got {item!r}")
            first, last = item
            _as_date("span first", first)
            _as_date("span last", last)
            if last <= first:
                raise ValueError(f"{self.symbol}: span last {last} must be after first {first}")
            if previous is not None and first <= previous:
                raise ValueError(f"{self.symbol}: spans must be ascending and disjoint")
            previous = last

    @property
    def days(self) -> int:
        """Total member-days over every span."""
        return sum((last - first).days for first, last in self.spans)

    @property
    def years(self) -> float:
        """``days`` over 365.25 -- what a per-year hazard is applied to."""
        return self.days / YEAR_DAYS


def survivors(
    market: Market,
    *,
    window_start: date = WINDOW_START,
    window_end: date = WINDOW_END,
) -> tuple[Exposure, ...]:
    """The priced index members that never left the index inside the window, sorted by symbol.

    These are the names a synthetic delisting can be given to. Excluded, each for its own reason:

    - a member with no bars -- it is already absent from every ranking, so killing it changes
      nothing;
    - a member whose last interval ends inside the window -- it already left, and injecting a
      second exit would double-count the historical rate;
    - a member with fewer than two bars inside its member-time -- there is no bar to truncate at
      that still leaves the symbol priced beforehand.

    ETFs are never index members, so SPY and the idle instrument can never appear here. Exposure
    is clipped to the window and then to the symbol's own first and last bar, because a member we
    could not price was never in the ranking pool and must not contribute member-years.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    _as_date("window_start", window_start)
    _as_date("window_end", window_end)
    if window_end <= window_start:
        raise ValueError(f"window_end {window_end} must be after window_start {window_start}")
    ends = _last_end(market.membership.intervals)
    raw: dict[str, list[tuple[date, date]]] = {}
    for symbol, start, end in market.membership.intervals:
        first = max(start, window_start)
        last = min(window_end if end is None else end - ONE_DAY, window_end)
        if last >= first:
            raw.setdefault(symbol, []).append((first, last))
    out: list[Exposure] = []
    for symbol in sorted(raw):
        end = ends[symbol]
        if end is not None and window_start <= end <= window_end:
            continue  # it already left the index inside the window
        h = market.history.get(symbol)
        if h is None or len(h) < 2:
            continue  # unserved: already absent from every ranking
        bars_first, bars_last = h.dates[0].item(), h.dates[-1].item()
        spans: list[tuple[date, date]] = []
        for first, last in sorted(raw[symbol]):
            first, last = max(first, bars_first), min(last, bars_last)
            if last <= first:
                continue
            if spans and first <= spans[-1][1] + ONE_DAY:
                spans[-1] = (spans[-1][0], max(spans[-1][1], last))
            else:
                spans.append((first, last))
        if not spans:
            continue
        out.append(Exposure(symbol, tuple(spans)))
    return tuple(out)


# --------------------------------------------------------------------------- who does die


@dataclass(frozen=True)
class Death:
    """One injected delisting: ``symbol``'s last bar is ``last_bar``; it is gone the next session."""

    symbol: str
    last_bar: date

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol:
            raise ValueError(f"symbol must be a non-empty str, got {self.symbol!r}")
        _as_date("last_bar", self.last_bar)


def _uniform_day(exposure: Exposure, rng: Random) -> date:
    """A day drawn uniformly over ``exposure``'s member-days, strictly before its last day."""
    u = rng.random() * exposure.days
    for first, last in exposure.spans:
        width = (last - first).days
        if u < width:
            return first + timedelta(days=int(u))
        u -= width
    return exposure.spans[-1][1] - ONE_DAY


def _death_bar(h: History, when: date) -> date | None:
    """The last bar on or before ``when`` that still leaves a later bar, or None when there is none.

    A death on a symbol's very last bar would be a no-op -- the symbol never becomes "gone" inside
    the window and no position is ever force-closed -- so the index is pulled back by one.
    """
    i = int(np.searchsorted(h.dates, np.datetime64(when), side="right")) - 1
    i = min(i, len(h) - 2)
    if i < 0:
        return None
    return h.dates[i].item()


def draw_deaths(
    market: Market,
    exposures: Sequence[Exposure],
    hazard_per_year: float,
    rng: Random,
) -> tuple[Death, ...]:
    """Who dies and when, under a constant annual hazard: ``P(death) = 1 - exp(-hazard x years)``.

    One ``rng`` draw per exposure for the Bernoulli, and one more for each death's date, taken in
    ``exposures`` order. So the draw is reproducible from the seed alone, and -- because no part of
    it looks at the assumed delisting return -- the same seed kills the same names on the same days
    at every ``r`` on a grid. That is what makes a grid of returns a paired comparison.

    The death date is uniform over the symbol's member-days, then snapped back to the last bar on
    or before it. A symbol can die at most once: its hazard is integrated over its whole exposure
    rather than resampled, so the realised count is below ``hazard x total member-years`` by the
    usual competing-risk amount, and the driver prints both numbers.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    if not isinstance(rng, Random):
        raise TypeError(f"rng must be a random.Random, got {type(rng).__name__}")
    if isinstance(hazard_per_year, bool) or not isinstance(hazard_per_year, (int, float)):
        raise TypeError(f"hazard_per_year must be a number, got {type(hazard_per_year).__name__}")
    rate = float(hazard_per_year)
    if not 0.0 <= rate <= 1.0:
        raise ValueError(f"hazard_per_year must be in [0, 1] per year, got {rate}")
    out: list[Death] = []
    for exposure in exposures:
        if not isinstance(exposure, Exposure):
            raise TypeError(f"expected an Exposure, got {type(exposure).__name__}")
        h = market.history.get(exposure.symbol)
        if h is None:
            raise ValueError(f"{exposure.symbol} has no bars in this market")
        if rng.random() >= 1.0 - math.exp(-rate * exposure.years):
            continue
        when = _death_bar(h, _uniform_day(exposure, rng))
        if when is not None:
            out.append(Death(exposure.symbol, when))
    return tuple(out)


# --------------------------------------------------------------------------- the perturbation


def _decline(h: History, delisting_return: float, sessions: int) -> History:
    """``h`` with its last ``sessions`` bars marked down so the final close is ``close x (1 + r)``.

    The final bar is flat -- open = high = low = close -- so nothing can fill above the death
    price: a stop placed the day before gets the gap-down open, which is the death price, and the
    force-close the next session gets the same mark. That is what "abrupt" means here. With
    ``sessions > 1`` the earlier decline bars keep their own shape, scaled by the running factor,
    so a forewarned death is visible and tradable in the days before it.

    Every price is floored at :data:`MIN_PRICE`; ``r = -1`` would otherwise write a zero close.
    """
    n = len(h)
    k = min(sessions, n)
    step = (1.0 + delisting_return) ** (1.0 / k)
    factors = np.ones(n, dtype=np.float64)
    for j in range(k):
        factors[n - k + j] = step ** (j + 1)
    columns: list[np.ndarray] = []
    for name in ("open", "high", "low", "close"):
        scaled = np.asarray(getattr(h, name), dtype=np.float64) * factors
        columns.append(np.maximum(scaled, MIN_PRICE))
    open_, high, low, close = columns
    open_[-1] = high[-1] = low[-1] = close[-1]
    return History(
        h.symbol,
        _frozen(np.array(h.dates, dtype="datetime64[D]")),
        _frozen(open_),
        _frozen(high),
        _frozen(low),
        _frozen(close),
        _frozen(np.array(h.volume, dtype=np.float64)),
    )


def _retired(membership: Membership, cuts: Mapping[str, date]) -> Membership:
    """``membership`` with every dead symbol leaving the index the day after its last bar.

    ``Membership`` ends are exclusive, so a symbol whose last bar is ``d`` is a member through
    ``d`` and gone from ``d + 1``. An interval that opens on or after the death never happens and
    is dropped; one that had already closed before it is left exactly as it was.

    This is belt and braces over the truncation: a ranking allocator drops a symbol with no bar on
    the data date anyway (``f_factor.FactorPrepared.rows_on`` selects the rows dated exactly
    ``data_date``), but retiring the symbol from the index makes the harness correct for any
    allocator, present or future, rather than only for the ones whose internals were read. It cost
    0.011 s per rebuild when measured over the store's 1,084 intervals.
    """
    out: list[tuple[str, date, date | None]] = []
    for symbol, start, end in membership.intervals:
        cut = cuts.get(symbol)
        if cut is None:
            out.append((symbol, start, end))
            continue
        stop = cut + ONE_DAY
        if start >= stop:
            continue
        out.append((symbol, start, stop if end is None or end > stop else end))
    return Membership(tuple(out))


def kill(
    market: Market,
    deaths: Iterable[Death],
    delisting_return: float,
    *,
    decline_sessions: int = 1,
) -> Market:
    """A NEW ``Market`` in which every named symbol is delisted on its death date at return ``r``.

    For each death: the symbol's ``History`` is truncated at ``death.last_bar``, that bar is
    rewritten to ``close x (1 + delisting_return)`` (flat, see :func:`_decline`), and the symbol
    leaves the index the next day. ``market`` is untouched -- ``Market`` is frozen and this is
    ``dataclasses.replace``, the same move ``backtest.dev._run`` already makes on ``fx``.

    The engine does the rest with no change: the name is absent from every later ranking, and any
    position still held is force-closed at the rewritten mark, reason "forced"
    (``book_runner.py`` steps 1 and 4, ``sim.book.close_book_unpriced``).

    ``delisting_return`` is in ``[-1, 0]``: 0 is the assumption every recorded backtest already
    makes (sold whole at the last price anyone saw) and -1 is a total loss. ``decline_sessions``
    is 1 for an abrupt death, the conservative base case, and larger for the forewarned
    sensitivity, which spreads the same total loss geometrically over the last that many bars.

    ValueError for a symbol with no bars, a repeated symbol, SPY, or a return outside ``[-1, 0]``.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    if isinstance(delisting_return, bool) or not isinstance(delisting_return, (int, float)):
        raise TypeError(f"delisting_return must be a number, got {type(delisting_return).__name__}")
    r = float(delisting_return)
    if not -1.0 <= r <= 0.0:
        raise ValueError(f"delisting_return must be in [-1, 0], got {r}")
    if isinstance(decline_sessions, bool) or not isinstance(decline_sessions, int):
        raise TypeError(f"decline_sessions must be an int, got {type(decline_sessions).__name__}")
    if decline_sessions < 1:
        raise ValueError(f"decline_sessions must be >= 1, got {decline_sessions}")
    history = dict(market.history)
    cuts: dict[str, date] = {}
    for death in deaths:
        if not isinstance(death, Death):
            raise TypeError(f"expected a Death, got {type(death).__name__}")
        if death.symbol in cuts:
            raise ValueError(f"{death.symbol} is given two death dates")
        if death.symbol == SPY:
            raise ValueError("SPY cannot be delisted; it is the benchmark every run is scored against")
        h = market.history.get(death.symbol)
        if h is None:
            raise ValueError(f"{death.symbol} has no bars in this market, so it cannot be delisted")
        cut = h.upto(death.last_bar)
        if len(cut) == 0:
            raise ValueError(f"{death.symbol} has no bar on or before {death.last_bar}")
        history[death.symbol] = _decline(cut, r, decline_sessions)
        cuts[death.symbol] = death.last_bar
    if not cuts:
        return market
    return replace(market, history=history, membership=_retired(market.membership, cuts))


def stressed(
    market: Market,
    exposures: Sequence[Exposure],
    *,
    hazard_per_year: float,
    delisting_return: float,
    rng: Random,
    decline_sessions: int = 1,
) -> tuple[Market, tuple[Death, ...]]:
    """One Monte Carlo draw: ``(the perturbed market, who died)``.

    :func:`draw_deaths` then :func:`kill`. The deaths are returned as well as applied because the
    driver reports how many names a seed killed, and because two calls with equal seeds must be
    checkable for equal deaths at different assumed returns.
    """
    deaths = draw_deaths(market, exposures, hazard_per_year, rng)
    return kill(market, deaths, delisting_return, decline_sessions=decline_sessions), deaths
