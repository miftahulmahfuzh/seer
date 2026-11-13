"""The random-twin yardstick: what a no-skill book of exactly this arm's shape would have earned.

WHY A TWIN AND NOT A RANDOM BOOK PER "SETUP". The request was a distribution of random books per
setup -- pool, book size, cadence, weighting, safety switch. The lab has no machine-readable setup:
every method file defines its own allocator and its own params dataclass, so nothing can enumerate
those five for an arbitrary arm. What every book-engine arm does expose, uniformly, is its sequence
of decisions: ``book_runner.run_book`` asks the allocator for targets on each rank or resize
session and gets ``Target(symbol, weight, last, limit, stop, take)`` values back. A twin replays
those decisions with every *picked* name swapped for a random index member of similar trading size.
It therefore has the arm's decision dates, weights, entries, exits, cash months and safety switch
by construction, for any allocator and with no per-method code: the setup is matched because it is
copied, not described. The code analysis of 2026-11-13 (session 20261113-125454-Y7RT) measured the
premise on M0562-W60-B100: recording the allocator and replaying the record reproduced the plain run
exactly. ``test_lab_yardstick`` re-proves it on every run, on a synthetic market.

This is not ``lab.twins``. That module finds *repeated* books among recorded arms; this one builds
random ones.

WHAT IS PICKED AND WHAT IS FIXED. A target is fixed -- copied into the twin unchanged -- when its
symbol is one the allocator declares it may hold or read (``holds(params)``, ``symbols(params)``),
SPY, or the rules' idle instrument. Everything else is a name the arm *picked* from the pool, and
only picks are what the yardstick asks about: an ETF-only or cash-only arm has no picks, reads
``not-applicable`` and simulates no twin. So does a bracket (``DESIGN_V0``) arm: it has no book
decisions to replay.

RESIZE DECISIONS PASS THROUGH. On a resize-only session ``run_book`` keeps the last rank session's
basket and uses only the *total weight* of the allocator's fresh answer (``_rescaled``). The
symbols of that answer are never traded, so the twin keeps them exactly as recorded, and holding
spells are tracked across *rank* decisions only. Treating a resize answer as a re-pick would end a
spell whenever the fresh ranking dropped a held name and trade a twin the real book never traded.

THE DRAW. At the rank decision where a picked name X enters the book (it was not in the previous
rank decision's targets) X gets a twin: the decision's index members with at least
``LIQUIDITY_BARS`` bars on or before the data date are ranked by the median of close x volume over
their trailing ``LIQUIDITY_BARS`` bars (most traded first, ties by symbol); the candidates are the
members within ``NEIGHBOUR_RANKS`` ranks of X's own rank (X's rank where its own trailing dollar
volume would sit when X is not a rankable member; the whole ranked list when X has no bars at all);
names the twin book already holds, names the arm picks at this decision and fixed symbols are
excluded; and the candidate with the smallest blake2b hash of (``RULE_ID``, seed, X, the decision's
month, candidate) that has a bar on the data date wins. When the neighbourhood has no usable
candidate the whole ranked list is used; when that has none either it is a ValueError, never a
silent fallback to X. When no member at all has ``LIQUIDITY_BARS`` bars (a window that opens right
at the start of the store) the members are ranked on the bars they have.

The twin keeps its name for the whole spell -- every later rank decision that still targets X --
and is redrawn only at a decision where it has no bar on the data date (or its scaled prices cannot
form a valid ``Target``). Each twin target copies X's weight; its ``last`` is the twin's own close on
the data date, and ``limit``, ``stop`` and ``take``, when present, are scaled by twin last / X's
last, so a limit 2% under X's close is a limit 2% under the twin's.

WHAT "NONE OF ITS NAMES" CAN AND CANNOT GUARANTEE. The neighbour pool is the same index the arm
picks from, so it overlaps the real book by design. What holds by construction:

- at the rank decision where a twin is drawn, it is none of the names the arm picks at that same
  decision, and never X itself;
- at every rank decision, the twin's targets have unique symbols, none of them a fixed symbol, and
  every substituted name is an index member of that decision with a bar on its data date.

What cannot be guaranteed: a twin kept for a spell can later coincide with a name the arm newly
picks (the arm buys T while the twin book still holds T as X's stand-in; T's own twin is then
drawn elsewhere), and across the whole run twins can and do hold names the arm held at other
times. Forbidding either would shrink the pool exactly where the arm is concentrated and make the
"random" book systematically avoid what the arm likes.

THE STATISTIC. Each twin is run through ``dev.run_candidate`` at the arm's capital and
contributions, and judged on the rate ``dev.make_row`` ranks on: the money-weighted return when
funded, else CAGR. ``beaten`` counts twins strictly below the arm; ties and twins with no rate count
against the arm. The twins' median trade count and turnover are compared with the arm's; outside
``control_shape.REFUSE_BAND`` the reading is ``unmatched``, because a twin that trades twice as
often is paying a different cost and the comparison stops being about the picks.

DETERMINISM. Seeds are ``seed_for(config_digest(candidate), i)``: no clock, no global random state,
no dependence on which trial row asked. With ``jobs > 1`` the twins run in forked processes (the
market is already in memory, so nothing large is pickled) and results are collected by seed index,
never by completion order, so every ``jobs`` value gives the identical ``Measurement``.

PURE. No database, no ``lab.store``, no clock, no network. The caller loads the market and decides
what to do with the result.
"""

from __future__ import annotations

import hashlib
import math
import multiprocessing
import statistics
from bisect import bisect_left, bisect_right
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any, NamedTuple

import numpy as np

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.book_runner import DividendMap
from seer_engine.backtest.dev import Candidate, DevRow, run_candidate
from seer_engine.backtest.market import SPY, Market
from seer_engine.lab import method as lab_method
from seer_engine.lab.control_shape import REFUSE_BAND
from seer_engine.sim import q
from seer_engine.sim.book import Target
from seer_engine.sim.contributions import ContributionSchedule
from seer_engine.sim.rules import TradeRules, is_bracket, is_rank_session
from seer_engine.strategies.allocator import Allocator, prepare_for
from seer_engine.strategies.base import History, as_day

RULE_ID = "yardstick-v1"
"""The draw rule's name. Phase 3 keys stored readings on it: any change to the draw, the ranking or
the statistic is a new id, never an edit, so an old reading is never compared with a new one."""

DRAWS = 200
"""Twins per measurement: "a few hundred random books". One twin moves the percentile by 0.005."""

LIQUIDITY_BARS = 63
"""Trading size is the median dollar volume over this many trailing bars (a quarter of sessions)."""

NEIGHBOUR_RANKS = 25
"""A twin is drawn from the members within this many liquidity ranks of the real pick."""

REPRODUCE_TOLERANCE = 1e-9
"""How far a re-run's total return may sit from the recorded one and still be the same run."""

STATUS_MEASURED = "measured"
STATUS_NOT_APPLICABLE = "not-applicable"
STATUS_UNMATCHED = "unmatched"
STATUSES: tuple[str, ...] = (STATUS_MEASURED, STATUS_NOT_APPLICABLE, STATUS_UNMATCHED)


class Unreproducible(Exception):
    """Re-running the arm did not give its recorded trade count and total return.

    A twin replays the decisions of *this* run. If this run is not the recorded one -- a different
    store, capital or funding -- the yardstick would measure a book nobody recorded, so the caller
    is refused instead of being handed a number about something else.
    """


@dataclass(frozen=True)
class Decision:
    """One allocator call the arm made: its data date, the index members it was shown, its answer.

    ``rank`` is False for a resize-only session, whose answer the runner reads for its total weight
    alone (see the module docstring).
    """

    data_date: date
    members: frozenset[str]
    targets: tuple[Target, ...]
    rank: bool = True


@dataclass(frozen=True)
class Measurement:
    """One yardstick reading of one arm. See the module docstring for every field's meaning.

    The constructor refuses contradictory readings: a not-applicable reading carries no twin
    figures, and a measured or unmatched one has at least one twin and a percentile that is exactly
    ``beaten / draws``.
    """

    status: str
    draws: int
    arm_rate: float | None
    beaten: int
    percentile: float | None
    rates: tuple[float, ...]
    trade_ratio: float | None
    turnover_ratio: float | None
    reproduced: bool | None

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}, got {self.status!r}")
        if self.status == STATUS_NOT_APPLICABLE:
            if (
                self.draws != 0
                or self.beaten != 0
                or self.percentile is not None
                or self.rates
                or self.trade_ratio is not None
                or self.turnover_ratio is not None
            ):
                raise ValueError("a not-applicable reading simulates no twin and carries no twin figures")
            return
        if self.draws < 1:
            raise ValueError(f"a {self.status} reading needs at least one twin, got draws={self.draws}")
        if not 0 <= self.beaten <= self.draws:
            raise ValueError(f"beaten must be in [0, {self.draws}], got {self.beaten}")
        if self.percentile != self.beaten / self.draws:
            raise ValueError(f"percentile must be beaten / draws, got {self.percentile!r}")
        if len(self.rates) > self.draws:
            raise ValueError(f"{len(self.rates)} rates for {self.draws} twins")


# --------------------------------------------------------------------------- record and replay


class Recorder:
    """An ``Allocator`` that answers exactly as ``inner`` does and logs every answer as a ``Decision``.

    Every protocol member is delegated, so the run it sits in is the arm's own run, byte for byte.
    It always defines ``prepare_market`` and forwards it to ``prepare_for(inner, market)``: a plain
    inner allocator still gets ``prepare(market.history)``, a ``MarketAware`` one gets
    ``prepare_market(market)``. ``id`` is the inner id, so the result carries the arm's own id.
    """

    def __init__(self, inner: Allocator, rules: TradeRules) -> None:
        if not isinstance(inner, Allocator):
            raise TypeError(f"inner must be an Allocator, got {type(inner).__name__}")
        if not isinstance(rules, TradeRules):
            raise TypeError(f"rules must be a TradeRules, got {type(rules).__name__}")
        self.id = inner.id
        self._inner = inner
        self._rules = rules
        self._log: list[Decision] = []

    @property
    def decisions(self) -> tuple[Decision, ...]:
        return tuple(self._log)

    def lookback(self, params: Any) -> int:
        return self._inner.lookback(params)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return self._inner.symbols(params)

    def holds(self, params: Any) -> tuple[str, ...]:
        return self._inner.holds(params)

    def uses_members(self, params: Any) -> bool:
        return self._inner.uses_members(params)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return self._inner.prepare(history)

    def prepare_market(self, market: Market) -> Any:
        return prepare_for(self._inner, market)

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        return self._note(data_date, members, self._inner.targets(history, members, data_date, held, params))

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        return self._note(
            data_date, members, self._inner.targets_prepared(prepared, members, data_date, held, params)
        )

    def _note(self, data_date: date, members: AbstractSet[str], wanted: Sequence[Target]) -> tuple[Target, ...]:
        out = tuple(wanted)
        rank = is_rank_session(self._rules, dates.next_session(data_date))
        self._log.append(Decision(data_date=data_date, members=frozenset(members), targets=out, rank=rank))
        return out


class Replay:
    """An ``Allocator`` that answers every call with the schedule entry dated on or before it.

    ``lookback``, ``symbols``, ``holds`` and ``uses_members`` are the real allocator's, so
    ``dev.candidate_window`` gives the replay the arm's own window. ``prepare`` returns the schedule
    itself -- never None -- so ``run_book`` takes the prepared path and never re-cuts every history
    on every decision. ``id`` is unique per seed because ``dev.run_registry`` refuses two different
    objects that share one.
    """

    def __init__(
        self, inner: Allocator, schedule: Mapping[date, Sequence[Target]], seed: int | None = None
    ) -> None:
        if not isinstance(inner, Allocator):
            raise TypeError(f"inner must be an Allocator, got {type(inner).__name__}")
        self.id = f"{RULE_ID}-replay" if seed is None else f"{RULE_ID}-twin-{seed:016x}"
        self._inner = inner
        days = sorted(schedule)
        self._days: tuple[date, ...] = tuple(days)
        self._answers: tuple[tuple[Target, ...], ...] = tuple(tuple(schedule[d]) for d in days)

    def lookback(self, params: Any) -> int:
        return self._inner.lookback(params)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return self._inner.symbols(params)

    def holds(self, params: Any) -> tuple[str, ...]:
        return self._inner.holds(params)

    def uses_members(self, params: Any) -> bool:
        return self._inner.uses_members(params)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return self._answers

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        return self._at(data_date)

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        return self._at(data_date)

    def _at(self, data_date: date) -> tuple[Target, ...]:
        i = bisect_right(self._days, data_date) - 1
        return () if i < 0 else self._answers[i]


def record(
    market: Market,
    dividends: DividendMap,
    spy_dividends: Sequence[Dividend],
    candidate: Candidate,
    *,
    initial_idr: Decimal,
    contributions: ContributionSchedule | None,
) -> tuple[tuple[Decision, ...], DevRow]:
    """Run ``candidate`` once, as ``lab run`` does, and return its decisions and its ``DevRow``.

    The allocator is wrapped in a ``Recorder`` and prepared through ``prepare_for``, which is what
    ``dev.run_registry`` does for a recorded trial; the run is therefore the recorded run.
    """
    recorder = Recorder(candidate.allocator, candidate.rules)
    arm = replace(candidate, allocator=recorder)
    _, row = run_candidate(
        market,
        dividends,
        spy_dividends,
        arm,
        prepared=prepare_for(recorder, market),
        initial_idr=initial_idr,
        contributions=contributions,
    )
    return recorder.decisions, row


# --------------------------------------------------------------------------- the draw


def _hash(*parts: str) -> int:
    digest = hashlib.blake2b("|".join((RULE_ID, *parts)).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def seed_for(config_digest: str, i: int) -> int:
    """The ``i``-th twin's seed for the arm whose ``lab.method.config_digest`` is ``config_digest``.

    A pure function of the arm's configuration, so two runs of the same arm on the same store draw
    the same twins, whoever asks and whenever.
    """
    if not isinstance(config_digest, str) or not config_digest:
        raise ValueError("config_digest must be a non-empty str")
    if isinstance(i, bool) or not isinstance(i, int) or i < 0:
        raise ValueError(f"i must be an int >= 0, got {i!r}")
    return _hash("seed", config_digest, str(i))


def _draw_order(seed: int, real: str, month: str, pool: Sequence[str]) -> list[str]:
    """``pool`` in draw order for ``real``'s twin: ascending hash, ties by symbol."""
    return sorted(pool, key=lambda name: (_hash("draw", str(seed), real, month, name), name))


def fixed_symbols(candidate: Candidate) -> frozenset[str]:
    """The symbols a twin never substitutes: what the allocator declares, SPY and the idle instrument."""
    if is_bracket(candidate.rules):
        raise ValueError(f"{candidate.id}: a bracket arm has no book decisions to replay")
    allocator, params = candidate.allocator, candidate.params
    out = set(allocator.holds(params)) | set(allocator.symbols(params)) | {SPY}
    if candidate.rules.idle_symbol is not None:
        out.add(candidate.rules.idle_symbol)
    return frozenset(out)


def _dollar_volume(h: History | None, day: np.datetime64, need: int) -> float | None:
    """Median close x volume over the trailing ``LIQUIDITY_BARS`` bars dated on or before ``day``.

    None when the symbol has fewer than ``need`` such bars or the median is not finite.
    """
    if h is None:
        return None
    end = int(np.searchsorted(h.dates, day, side="right"))
    if end < need:
        return None
    start = max(0, end - LIQUIDITY_BARS)
    value = float(np.median(h.close[start:end] * h.volume[start:end]))
    return value if math.isfinite(value) else None


def _ranked(market: Market, members: AbstractSet[str], d: date) -> tuple[tuple[str, float], ...]:
    """``members`` by trailing median dollar volume on ``d``, most traded first, ties by symbol.

    Only members with ``LIQUIDITY_BARS`` bars count; when none has that many, every member with at
    least one bar does (a window that opens at the very start of the store).
    """
    day = as_day(d)
    for need in (LIQUIDITY_BARS, 1):
        rows: list[tuple[float, str]] = []
        for symbol in members:
            dv = _dollar_volume(market.history.get(symbol), day, need)
            if dv is not None:
                rows.append((-dv, symbol))
        if rows:
            rows.sort()
            return tuple((symbol, -neg) for neg, symbol in rows)
    return ()


def _position(market: Market, ranked: tuple[tuple[str, float], ...], real: str, d: date) -> int | None:
    """``real``'s rank in ``ranked``, or where its own dollar volume would sit, or None without bars."""
    for i, (symbol, _) in enumerate(ranked):
        if symbol == real:
            return i
    own = _dollar_volume(market.history.get(real), as_day(d), 1)
    if own is None:
        return None
    return bisect_left([(-dv, symbol) for symbol, dv in ranked], (-own, real))


def _scaled(price: Decimal | None, ratio: Decimal) -> Decimal | None:
    return None if price is None else q(price * ratio)


def _twin_target(market: Market, real: Target, twin: str, d: date) -> Target | None:
    """``real`` re-pointed at ``twin``: same weight, the twin's own close, prices scaled; or None.

    None when ``twin`` has no bar on ``d`` or the scaled prices cannot form a valid ``Target``
    (a price that rounds to zero, a stop or take that no longer brackets the reference).
    """
    bar = market.bar(twin, d)
    if bar is None:
        return None
    last = q(bar.close)
    ratio = last / real.last
    try:
        return Target(
            symbol=twin,
            weight=real.weight,
            last=last,
            limit=_scaled(real.limit, ratio),
            stop=_scaled(real.stop, ratio),
            take=_scaled(real.take, ratio),
        )
    except ValueError:
        return None


def _draw(
    market: Market,
    decision: Decision,
    real: Target,
    seed: int,
    excluded: AbstractSet[str],
    ranks: dict[date, tuple[tuple[str, float], ...]],
) -> Target:
    """A fresh twin target for ``real`` at ``decision`` (see THE DRAW in the module docstring)."""
    d = decision.data_date
    ranked = ranks.get(d)
    if ranked is None:
        ranked = _ranked(market, decision.members, d)
        ranks[d] = ranked
    everyone = [symbol for symbol, _ in ranked]
    pos = _position(market, ranked, real.symbol, d)
    near = everyone if pos is None else everyone[max(0, pos - NEIGHBOUR_RANKS) : pos + NEIGHBOUR_RANKS + 1]
    month = f"{d.year:04d}-{d.month:02d}"
    for pool in (near, everyone):
        for name in _draw_order(seed, real.symbol, month, [s for s in pool if s not in excluded]):
            built = _twin_target(market, real, name, d)
            if built is not None:
                return built
    raise ValueError(
        f"no index member on {d} can stand in for {real.symbol}: every ranked member is excluded "
        "or has no usable bar that day"
    )


def twin_schedule(
    market: Market,
    decisions: Sequence[Decision],
    fixed: AbstractSet[str],
    seed: int,
    *,
    ranks: dict[date, tuple[tuple[str, float], ...]] | None = None,
) -> dict[date, tuple[Target, ...]]:
    """The twin's answer for every recorded decision date, for one seed.

    Same dates, same weights in the same rank order; on every rank decision each picked target is
    replaced by its twin, and resize decisions are copied unchanged (see the module docstring for the
    spell rule and exactly what the substitution guarantees). ``ranks`` caches the liquidity ranking
    per date; it depends on the market and the members only, so one cache serves every seed.
    """
    if ranks is None:
        ranks = {}
    fixed = frozenset(fixed)
    ordered = sorted(decisions, key=lambda x: x.data_date)
    if len({x.data_date for x in ordered}) != len(ordered):
        raise ValueError("two decisions share a data date; a run asks its allocator once per session")
    out: dict[date, tuple[Target, ...]] = {}
    spells: dict[str, str] = {}  # real picked name -> its twin, as of the last rank decision
    for decision in ordered:
        d = decision.data_date
        if not decision.rank:
            out[d] = decision.targets
            continue
        picked = [t for t in decision.targets if t.symbol not in fixed]
        real_names = frozenset(t.symbol for t in picked)
        twins: dict[str, Target] = {}
        taken: set[str] = set()
        for t in picked:  # continuing spells keep their twin while it still trades
            name = spells.get(t.symbol)
            if name is None or name in taken:
                continue
            kept = _twin_target(market, t, name, d)
            if kept is not None:
                twins[t.symbol] = kept
                taken.add(name)
        for t in picked:  # new spells, and spells whose twin stopped trading, draw in rank order
            if t.symbol in twins:
                continue
            drawn = _draw(market, decision, t, seed, fixed | real_names | taken, ranks)
            twins[t.symbol] = drawn
            taken.add(drawn.symbol)
        spells = {real: twin.symbol for real, twin in twins.items()}
        out[d] = tuple(t if t.symbol in fixed else twins[t.symbol] for t in decision.targets)
    return out


def _draw_decisions(decisions: Sequence[Decision], fixed: AbstractSet[str]) -> list[Decision]:
    """The rank decisions at which a picked name enters the book: where twins are certainly drawn.

    Empty exactly when no rank decision holds a picked name, which is what not-applicable means.
    """
    out: list[Decision] = []
    previous: frozenset[str] = frozenset()
    for decision in sorted(decisions, key=lambda x: x.data_date):
        if not decision.rank:
            continue
        picked = frozenset(t.symbol for t in decision.targets if t.symbol not in fixed)
        if picked - previous:
            out.append(decision)
        previous = picked
    return out


# --------------------------------------------------------------------------- measuring


class _Outcome(NamedTuple):
    rate: float | None
    trades: int
    turnover: float | None


@dataclass(frozen=True, eq=False)
class _Work:
    """Everything one twin run needs. Inherited by forked workers, never pickled."""

    market: Market
    dividends: DividendMap
    spy_dividends: tuple[Dividend, ...]
    candidate: Candidate
    initial_idr: Decimal
    contributions: ContributionSchedule | None
    decisions: tuple[Decision, ...]
    fixed: frozenset[str]
    ranks: dict[date, tuple[tuple[str, float], ...]]


def _float(x: Any) -> float | None:
    return None if x is None else float(x)


def _rate(row: DevRow) -> float | None:
    """The rate ``dev.make_row`` ranks on: money-weighted return when funded, else CAGR."""
    m = row.stats.metrics
    return _float(m.cagr if m.mwr is None else m.mwr)


def _outcome(row: DevRow) -> _Outcome:
    return _Outcome(rate=_rate(row), trades=int(row.stats.metrics.trades), turnover=_float(row.stats.turnover))


def _twin_outcome(work: _Work, seed: int) -> _Outcome:
    """Build seed's twin schedule, run it at the arm's capital and funding, and read it."""
    schedule = twin_schedule(work.market, work.decisions, work.fixed, seed, ranks=work.ranks)
    replay = Replay(work.candidate.allocator, schedule, seed=seed)
    twin = replace(work.candidate, allocator=replay)
    _, row = run_candidate(
        work.market,
        work.dividends,
        work.spy_dividends,
        twin,
        prepared=prepare_for(replay, work.market),
        initial_idr=work.initial_idr,
        contributions=work.contributions,
    )
    return _outcome(row)


_CHILD_WORK: _Work | None = None  # set only inside a forked worker, by _adopt


def _adopt(work: _Work) -> None:
    global _CHILD_WORK
    _CHILD_WORK = work


def _twin_in_child(seed: int) -> _Outcome:
    if _CHILD_WORK is None:
        raise RuntimeError("a yardstick worker ran before it was handed its work")
    return _twin_outcome(_CHILD_WORK, seed)


def _outcomes(work: _Work, seeds: Sequence[int], jobs: int) -> list[_Outcome]:
    """One outcome per seed, in seed order, whatever ``jobs`` is.

    ``jobs > 1`` forks workers after the market is in memory (copy-on-write; the work is passed as
    the pool initializer's argument, which a fork does not pickle). ``Pool.map`` returns results in
    input order, so completion order can never reach the result.
    """
    if jobs == 1 or len(seeds) == 1:
        return [_twin_outcome(work, seed) for seed in seeds]
    procs = min(jobs, len(seeds))
    ctx = multiprocessing.get_context("fork")
    with ctx.Pool(processes=procs, initializer=_adopt, initargs=(work,)) as pool:
        return pool.map(_twin_in_child, list(seeds), chunksize=max(1, len(seeds) // (procs * 4)))


def _ratio(mine: float | None, theirs: float | None) -> float | None:
    """``mine / theirs``; None when either is unknown or ``theirs`` is zero (undefined, not large)."""
    if mine is None or theirs is None or float(theirs) == 0.0:
        return None
    return float(mine) / float(theirs)


def _in_band(ratio: float | None) -> bool:
    """True unless ``ratio`` is known and outside ``REFUSE_BAND`` (edges inclusive)."""
    low, high = REFUSE_BAND
    return ratio is None or low <= ratio <= high


def _check(row: DevRow, expect: tuple[int, float | None] | None, candidate_id: str) -> bool | None:
    """None without an expectation; True when the run matches it; ``Unreproducible`` otherwise."""
    if expect is None:
        return None
    trades, total_return = expect
    m = row.stats.metrics
    same_trades = int(m.trades) == int(trades)
    if m.total_return is None or total_return is None:
        same_return = m.total_return is None and total_return is None
    else:
        same_return = abs(float(m.total_return) - float(total_return)) <= REPRODUCE_TOLERANCE
    if not (same_trades and same_return):
        raise Unreproducible(
            f"{candidate_id}: the re-run made {m.trades} trades and returned {m.total_return!r}; the "
            f"record says {trades} trades and {total_return!r}"
        )
    return True


def _summarise(arm: _Outcome, outcomes: Sequence[_Outcome], reproduced: bool | None) -> Measurement:
    draws = len(outcomes)
    beaten = sum(1 for o in outcomes if arm.rate is not None and o.rate is not None and o.rate < arm.rate)
    trade_ratio = _ratio(statistics.median([o.trades for o in outcomes]), arm.trades)
    turnovers = [o.turnover for o in outcomes if o.turnover is not None]
    turnover_ratio = _ratio(statistics.median(turnovers), arm.turnover) if turnovers else None
    matched = _in_band(trade_ratio) and _in_band(turnover_ratio)
    return Measurement(
        status=STATUS_MEASURED if matched else STATUS_UNMATCHED,
        draws=draws,
        arm_rate=arm.rate,
        beaten=beaten,
        percentile=beaten / draws,
        rates=tuple(sorted(o.rate for o in outcomes if o.rate is not None)),
        trade_ratio=trade_ratio,
        turnover_ratio=turnover_ratio,
        reproduced=reproduced,
    )


def _not_applicable(arm_rate: float | None, reproduced: bool | None) -> Measurement:
    return Measurement(
        status=STATUS_NOT_APPLICABLE,
        draws=0,
        arm_rate=arm_rate,
        beaten=0,
        percentile=None,
        rates=(),
        trade_ratio=None,
        turnover_ratio=None,
        reproduced=reproduced,
    )


def measure(
    market: Market,
    dividends: DividendMap,
    spy_dividends: Sequence[Dividend],
    candidate: Candidate,
    *,
    initial_idr: Decimal,
    contributions: ContributionSchedule | None,
    draws: int = DRAWS,
    jobs: int = 1,
    expect: tuple[int, float | None] | None = None,
) -> Measurement:
    """The yardstick reading of ``candidate`` on ``market`` at this capital and funding.

    Runs the arm once (recorded), checks it against ``expect`` -- the recorded trial's
    ``(trades, total_return)`` -- when one is given (``Unreproducible`` on a mismatch), then runs
    ``draws`` twins and summarises them. A bracket arm, or one whose rank decisions hold no picked
    name, is ``not-applicable`` and simulates no twin. ``jobs`` is the number of worker processes;
    the result does not depend on it. The caller passes the trial's own capital and contributions
    (``runner.recorded_capital``, ``runner.recorded_contributions``) for a recorded arm.
    """
    if not isinstance(candidate, Candidate):
        raise TypeError(f"expected a Candidate, got {type(candidate).__name__}")
    if isinstance(draws, bool) or not isinstance(draws, int) or draws < 1:
        raise ValueError(f"draws must be an int >= 1, got {draws!r}")
    if isinstance(jobs, bool) or not isinstance(jobs, int) or jobs < 1:
        raise ValueError(f"jobs must be an int >= 1, got {jobs!r}")
    if expect is not None and (not isinstance(expect, tuple) or len(expect) != 2):
        raise TypeError(f"expect must be a (trades, total_return) pair or None, got {expect!r}")
    if is_bracket(candidate.rules):
        return _not_applicable(None, None)
    decisions, row = record(
        market, dividends, spy_dividends, candidate, initial_idr=initial_idr, contributions=contributions
    )
    reproduced = _check(row, expect, candidate.id)
    arm = _outcome(row)
    fixed = fixed_symbols(candidate)
    draw_at = _draw_decisions(decisions, fixed)
    if not draw_at:
        return _not_applicable(arm.rate, reproduced)
    work = _Work(
        market=market,
        dividends=dividends,
        spy_dividends=tuple(spy_dividends),
        candidate=candidate,
        initial_idr=initial_idr,
        contributions=contributions,
        decisions=decisions,
        fixed=fixed,
        ranks={x.data_date: _ranked(market, x.members, x.data_date) for x in draw_at},
    )
    digest = lab_method.config_digest(candidate)
    seeds = [seed_for(digest, i) for i in range(draws)]
    return _summarise(arm, _outcomes(work, seeds, jobs), reproduced)
