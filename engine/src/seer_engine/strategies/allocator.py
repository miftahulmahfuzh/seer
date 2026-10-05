"""Allocators: the strategy interface of the book engine (P7a), its shared helpers, one adapter and two overlays.

An allocator maps per-symbol bar history at a ``data_date`` close, plus the symbols the book
holds, to ranked ``sim.book.Target`` weights for the next session. ``sim.step_book`` turns
them into trades under a ``TradeRules`` value. Pure: no database, network, clock or randomness
(tests/test_strategy_purity.py globs this module).

CONTRACT (P4 identity), for every data date d, held set and params p::

    targets_prepared(prepare(H), M, d, held, p) == targets({s: h.upto(d) for s, h in H.items()}, M, d, held, p)

and ``targets`` reads only bars dated on or before d, however long the histories it is given.
Targets are in rank order with unique symbols, and every ``Target.last`` is the 4-dp close of
the symbol's last bar dated on or before d. A symbol with no bar dated d is never a new target
(only a held one may be kept). Σ weight <= 1, except for ``PICKS`` (see ``PicksAllocator``).
tests/allocatorkit.py checks all of this for every allocator.

``prepare(history)`` takes no params, so the adapter and overlays, whose inner objects live in
their params, prepare lazily: their prepared value is a ``LazyPrepared`` that runs each inner
object's ``prepare`` on first use and keeps the result, keyed by object identity.

An allocator that needs more than bars -- the point-in-time fundamentals panel, say -- declares
``prepare_market(market)`` instead and gets the whole ``Market``. ``prepare`` is unchanged and
stays the interface every existing allocator implements; the two are dispatched by
``prepare_for(obj, market)``, which the dev/lab runner calls.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_DOWN, Decimal
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import numpy as np

from seer_engine import dates
from seer_engine.prices import to_decimal
from seer_engine.sim import Pick, q
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, equal_weight, to_weight
from seer_engine.strategies.base import History, Strategy, as_day
from seer_engine.strategies.indicators import stdev_return_window

TRADING_DAYS = 252  # vol annualization: daily stdev × sqrt(252)

if TYPE_CHECKING:  # typing only: no runtime import, so no strategies -> backtest import cycle
    from seer_engine.backtest.market import Market


# --------------------------------------------------------------------------- the protocol


@runtime_checkable
class Allocator(Protocol):
    """Maps history at data_date's close (plus what is held) to target weights for the next session.

    ``prepare_market`` is NOT a member of this protocol, deliberately: this protocol is
    ``runtime_checkable`` and eight production sites test ``isinstance(x, Allocator)``, so adding
    a member -- even one with a default body -- would make every existing allocator fail the
    check. An allocator that wants the whole ``Market`` implements ``MarketAware`` alongside this
    protocol instead, and ``prepare_for`` picks the right one.
    """

    id: str

    def lookback(self, params: Any) -> int: ...

    def symbols(self, params: Any) -> tuple[str, ...]: ...

    def holds(self, params: Any) -> tuple[str, ...]: ...

    def uses_members(self, params: Any) -> bool: ...

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]: ...

    def prepare(self, history: Mapping[str, History]) -> Any: ...

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]: ...


@runtime_checkable
class MarketAware(Protocol):
    """An allocator that prepares from the whole ``Market``, not only its bars.

    Optional and additive: an allocator implements this *in addition to* ``Allocator``, and
    ``prepare_for`` routes to ``prepare_market`` when it is present and to ``prepare`` when it is
    not. An implementer still needs ``prepare`` -- it is an ``Allocator`` member, and
    ``allocatorkit``'s P4 identity check drives the plain path.

    ``runtime_checkable`` tests attribute presence only. ``isinstance(x, MarketAware)`` is
    therefore exactly "``x`` has an attribute called ``prepare_market``": it does not check the
    arity, the annotations, the return type, or even that the attribute is callable. That is
    enough for dispatch and no more, which is why ``prepare_for`` checks callability itself.
    """

    def prepare_market(self, market: Market) -> Any: ...


def prepare_for(obj: Any, market: Market) -> Any:
    """``obj``'s prepared value for ``market``: the ``MarketAware`` path when it has one.

    ``obj.prepare_market(market)`` when ``obj`` defines ``prepare_market``, otherwise
    ``obj.prepare(market.history)`` -- which is what every call site did before the hook existed,
    so an allocator that does not define it sees no change at all. ``obj`` may be an
    ``Allocator`` or a bracket ``Strategy``; both have ``prepare``.

    Raises TypeError when ``prepare_market`` is present but not callable, because
    ``runtime_checkable`` cannot tell a method from a data attribute and a silent fallback there
    would hide a typo as a quietly bar-only allocator.
    """
    if not isinstance(obj, MarketAware):
        return obj.prepare(market.history)
    fn = obj.prepare_market
    if not callable(fn):
        raise TypeError(
            f"{type(obj).__name__}.prepare_market must be callable, got {type(fn).__name__}"
        )
    return fn(market)


# --------------------------------------------------------------------------- shared helpers


def _plain(x: Decimal | int) -> str:
    """``x`` as a plain decimal string without trailing zeros: Decimal("0.120") -> "0.12"."""
    d = Decimal(x) if isinstance(x, int) else x
    return format(d.normalize(), "f")


def _price(name: str, x: object) -> Decimal | None:
    """``x`` as a 4-dp Decimal, or None when it is not finite. TypeError for a non-number."""
    if isinstance(x, bool) or not isinstance(x, (int, float, Decimal)):
        raise TypeError(f"{name} must be a float, int or Decimal, got {type(x).__name__}")
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, Decimal) and not x.is_finite():
        return None
    return q(to_decimal(x))


def target_from_close(
    symbol: str,
    close: float | Decimal,
    weight: Decimal,
    *,
    limit: float | Decimal | None = None,
    stop: float | Decimal | None = None,
    take: float | Decimal | None = None,
) -> Target | None:
    """A ``Target`` from float features, or None when its prices are unusable.

    Every price goes through ``prices.to_decimal`` (floats via their shortest repr) and
    ``sim.q``. None when any given price is not finite or is <= 0 after rounding, or when the
    ordering ``stop < ref < take`` fails, where ``ref`` is ``limit`` when given and the close
    otherwise (the ``a._bracket`` convention: an unusable bracket drops the candidate). A bad
    ``weight`` is a programming error and raises (``Target`` validates it).
    """
    last = _price("close", close)
    if last is None or last <= 0:
        return None
    given: dict[str, Decimal | None] = {}
    for name, x in (("limit", limit), ("stop", stop), ("take", take)):
        if x is None:
            given[name] = None
            continue
        p = _price(name, x)
        if p is None or p <= 0:
            return None
        given[name] = p
    ref = given["limit"] if given["limit"] is not None else last
    if given["stop"] is not None and not given["stop"] < ref:
        return None
    if given["take"] is not None and not given["take"] > ref:
        return None
    return Target(
        symbol=symbol,
        weight=weight,
        last=last,
        limit=given["limit"],
        stop=given["stop"],
        take=given["take"],
    )


def month_end_closes(h: History, data_date: date) -> np.ndarray:
    """Closes of the last bar of each completed calendar month, on or before ``data_date``, ascending.

    A month is completed when a later month has begun by ``data_date``: every month before
    ``data_date``'s, and ``data_date``'s own month when ``data_date`` is its last NYSE session
    (``dates.next_session`` falls in a later month). Each completed month contributes the close
    of the symbol's last bar dated in it (a month the symbol has no bar in contributes nothing).
    Reads only bars dated on or before ``data_date``. float64, a new array.
    """
    if not isinstance(h, History):
        raise TypeError(f"h must be a History, got {type(h).__name__}")
    day = as_day(data_date)
    end = int(np.searchsorted(h.dates, day, side="right"))
    if end == 0:
        return np.empty(0, dtype=np.float64)
    months = h.dates[:end].astype("datetime64[M]")
    ends = np.flatnonzero(months[1:] != months[:-1])
    after = dates.next_session(data_date)
    month_done = (after.year, after.month) != (data_date.year, data_date.month)
    if months[-1] < day.astype("datetime64[M]") or month_done:
        ends = np.append(ends, end - 1)
    return np.array(h.close[ends], dtype=np.float64)


def last_close(h: History | None, data_date: date) -> float | None:
    """The close of ``h``'s last bar dated on or before ``data_date``, or None when there is none."""
    if h is None:
        return None
    end = int(np.searchsorted(h.dates, as_day(data_date), side="right"))
    if end == 0:
        return None
    return float(h.close[end - 1])


def scale_weight(weight: Decimal, factor: Decimal) -> Decimal | None:
    """``to_weight(weight × factor)``, or None when the product floors to zero (the target is dropped)."""
    product = weight * factor
    if product.quantize(WEIGHT_QUANTUM, rounding=ROUND_DOWN) <= 0:
        return None
    return to_weight(product)


class LazyPrepared:
    """A history plus each inner object's ``prepare(history)``, computed on first use and kept.

    Inner objects (strategies, allocators) are keyed by identity, so one ``LazyPrepared`` serves
    every params value of an adapter or overlay, whichever inner objects those params name.
    """

    __slots__ = ("_cache", "history")

    def __init__(self, history: Mapping[str, History]) -> None:
        self.history: dict[str, History] = dict(history)
        self._cache: list[tuple[Any, Any]] = []

    def of(self, inner: Any) -> Any:
        for obj, value in self._cache:
            if obj is inner:
                return value
        value = inner.prepare(self.history)
        self._cache.append((inner, value))
        return value


def _lazy(prepared: object) -> LazyPrepared:
    if not isinstance(prepared, LazyPrepared):
        raise TypeError(f"prepared must be LazyPrepared, got {type(prepared).__name__}")
    return prepared


def _check_call(members: object, data_date: object, held: object) -> None:
    if not isinstance(members, AbstractSet):
        raise TypeError(f"members must be a set, got {type(members).__name__}")
    as_day(data_date)
    if not isinstance(held, frozenset):
        raise TypeError(f"held must be a frozenset, got {type(held).__name__}")


def _params_dict(name: str, params: Any) -> dict[str, str]:
    as_dict = getattr(params, "as_dict", None)
    if as_dict is None:
        raise TypeError(f"{name} ({type(params).__name__}) has no as_dict()")
    return dict(as_dict())


# --------------------------------------------------------------------------- PICKS: bracket strategies as targets


@dataclass(frozen=True, slots=True)
class PicksParams:
    """A bracket ``Strategy`` (A, A2, B), its params, and the slot count that sets each weight."""

    strategy: Strategy
    params: Any
    slots: int = 4  # weight = equal_weight(slots)

    def __post_init__(self) -> None:
        if not isinstance(self.strategy, Strategy):
            raise TypeError(f"strategy must be a Strategy, got {type(self.strategy).__name__}")
        if isinstance(self.slots, bool) or not isinstance(self.slots, int):
            raise TypeError(f"slots must be an int, got {type(self.slots).__name__}")
        if self.slots < 1:
            raise ValueError(f"slots must be >= 1, got {self.slots}")

    def as_dict(self) -> dict[str, str]:
        out = {"strategy": self.strategy.id, "slots": str(self.slots)}
        for k, v in _params_dict("params", self.params).items():
            out[f"params.{k}"] = v
        return out


def _picks_params(params: object) -> PicksParams:
    if not isinstance(params, PicksParams):
        raise TypeError(f"params must be PicksParams, got {type(params).__name__}")
    return params


def _picks_targets(
    history: Mapping[str, History],
    picks: list[Pick],
    data_date: date,
    held: frozenset[str],
    params: PicksParams,
) -> tuple[Target, ...]:
    w = equal_weight(params.slots)
    out: list[Target] = []
    for symbol in sorted(held):
        close = last_close(history.get(symbol), data_date)
        if close is None:
            raise ValueError(f"held symbol {symbol} has no bar on or before {data_date}")
        out.append(Target(symbol=symbol, weight=w, last=q(to_decimal(close))))
    seen = set(held)
    for pick in picks:
        if pick.symbol in seen:
            continue
        seen.add(pick.symbol)
        out.append(
            Target(
                symbol=pick.symbol,
                weight=w,
                last=pick.last_price,
                limit=pick.limit_price,
                stop=pick.sl_price,
                take=pick.tp_price,
            )
        )
    return tuple(out)


class PicksAllocator:
    """A bracket ``Strategy`` behind the ``Allocator`` protocol (the V0_BOOK parity adapter).

    Targets: every held symbol first, in symbol order, at weight ``equal_weight(slots)`` with
    ``last`` = its last close on or before d and no limit, stop or take (so the engine keeps it
    and never resizes it); then each pick, in rank order, whose symbol is neither held nor seen
    before, as ``Target(symbol, w, last, limit, stop=sl, take=tp)``.

    Every pick is returned, not just ``slots`` of them: under §5 a pick rejected at sizing (too
    small, no cash) lets the next one in, so the engine's ``max_positions`` cap, not this
    adapter, must decide which picks get the free slots. Σ weight may therefore exceed 1. PICKS
    is valid only with rules whose ``max_positions`` equals ``params.slots`` (``V0_BOOK``).
    """

    id = "PICKS"

    def lookback(self, params: Any) -> int:
        return int(_picks_params(params).strategy.lookback)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _picks_params(params)
        return ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _picks_params(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _picks_params(params)
        return True

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _picks_params(params)
        _check_call(members, data_date, held)
        picks = p.strategy.picks(history, members, data_date, p.params)
        return _picks_targets(history, picks, data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> LazyPrepared:
        return LazyPrepared(history)

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _picks_params(params)
        lazy = _lazy(prepared)
        _check_call(members, data_date, held)
        picks = p.strategy.picks_prepared(lazy.of(p.strategy), members, data_date, p.params)
        return _picks_targets(lazy.history, picks, data_date, held, p)


PICKS = PicksAllocator()


# --------------------------------------------------------------------------- BLEND: core + satellite (F9)


@dataclass(frozen=True, slots=True)
class BlendPart:
    """One sleeve of a blend: an allocator, its params, and the share of equity it runs."""

    allocator: Allocator
    params: Any
    share: Decimal  # (0, 1], a multiple of WEIGHT_QUANTUM

    def __post_init__(self) -> None:
        if not isinstance(self.allocator, Allocator):
            raise TypeError(f"allocator must be an Allocator, got {type(self.allocator).__name__}")
        if not isinstance(self.share, Decimal):
            raise TypeError(f"share must be a Decimal, got {type(self.share).__name__}")
        if not self.share.is_finite() or not 0 < self.share <= 1:
            raise ValueError(f"share must be in (0, 1], got {self.share}")
        if self.share % WEIGHT_QUANTUM != 0:
            raise ValueError(f"share must be a multiple of {WEIGHT_QUANTUM}, got {self.share}")


@dataclass(frozen=True, slots=True)
class BlendParams:
    parts: tuple[BlendPart, ...]  # >= 2 parts, Σ share <= 1

    def __post_init__(self) -> None:
        if not isinstance(self.parts, tuple):
            raise TypeError(f"parts must be a tuple, got {type(self.parts).__name__}")
        for part in self.parts:
            if not isinstance(part, BlendPart):
                raise TypeError(f"parts must be BlendPart values, got {type(part).__name__}")
        if len(self.parts) < 2:
            raise ValueError(f"a blend needs >= 2 parts, got {len(self.parts)}")
        total = sum((part.share for part in self.parts), Decimal(0))
        if total > 1:
            raise ValueError(f"part shares sum to {total} > 1")

    def as_dict(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for i, part in enumerate(self.parts, start=1):
            out[f"part{i}.allocator"] = part.allocator.id
            out[f"part{i}.share"] = _plain(part.share)
            for k, v in _params_dict(f"part{i}.params", part.params).items():
                out[f"part{i}.{k}"] = v
        return out


def _blend_params(params: object) -> BlendParams:
    if not isinstance(params, BlendParams):
        raise TypeError(f"params must be BlendParams, got {type(params).__name__}")
    return params


def _part_held(params: BlendParams, held: frozenset[str]) -> list[frozenset[str]]:
    """held_i = held − ∪_{j≠i} holds(part j): a sleeve never sees another sleeve's fixed holdings."""
    holds = [frozenset(part.allocator.holds(part.params)) for part in params.parts]
    out = []
    for i in range(len(params.parts)):
        others: frozenset[str] = frozenset().union(*(h for j, h in enumerate(holds) if j != i))
        out.append(held - others)
    return out


def _merge(scaled: list[tuple[Decimal, tuple[Target, ...]]]) -> tuple[Target, ...]:
    """Weights × share (floored; zero drops), summed per symbol, ranked by first appearance.

    A symbol several sleeves target keeps the first sleeve's prices (last, limit, stop, take).
    """
    order: list[str] = []
    first: dict[str, Target] = {}
    total: dict[str, Decimal] = {}
    for share, targets in scaled:
        for t in targets:
            w = scale_weight(t.weight, share)
            if w is None:
                continue
            if t.symbol in first:
                total[t.symbol] += w
            else:
                order.append(t.symbol)
                first[t.symbol] = t
                total[t.symbol] = w
    return tuple(replace(first[s], weight=total[s]) for s in order)


class BlendAllocator:
    """Several allocators, each running a fixed share of equity (F9 core + satellite).

    Part i is called with ``held_i = held − ∪_{j≠i} holds(part j)``; its weights are scaled by
    its share and floored to WEIGHT_QUANTUM (targets that floor to zero are dropped). A symbol
    targeted by several parts gets the sum of its scaled weights, at the rank of its first
    appearance (part order, then rank within the part), with the first part's prices.
    """

    id = "BLEND"

    def lookback(self, params: Any) -> int:
        p = _blend_params(params)
        return max(part.allocator.lookback(part.params) for part in p.parts)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _blend_params(params)
        return tuple(sorted({s for part in p.parts for s in part.allocator.symbols(part.params)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _blend_params(params)
        return tuple(sorted({s for part in p.parts for s in part.allocator.holds(part.params)}))

    def uses_members(self, params: Any) -> bool:
        p = _blend_params(params)
        return any(part.allocator.uses_members(part.params) for part in p.parts)

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _blend_params(params)
        _check_call(members, data_date, held)
        scaled = [
            (part.share, part.allocator.targets(history, members, data_date, part_held, part.params))
            for part, part_held in zip(p.parts, _part_held(p, held), strict=True)
        ]
        return _merge(scaled)

    def prepare(self, history: Mapping[str, History]) -> LazyPrepared:
        return LazyPrepared(history)

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _blend_params(params)
        lazy = _lazy(prepared)
        _check_call(members, data_date, held)
        scaled = [
            (
                part.share,
                part.allocator.targets_prepared(lazy.of(part.allocator), members, data_date, part_held, part.params),
            )
            for part, part_held in zip(p.parts, _part_held(p, held), strict=True)
        ]
        return _merge(scaled)


BLEND = BlendAllocator()


# --------------------------------------------------------------------------- VOLTARGET: volatility targeting (L11)


@dataclass(frozen=True, slots=True)
class VolTargetParams:
    inner: Allocator
    inner_params: Any
    signal: str = "SPY"  # whose daily returns measure volatility
    target_vol: Decimal = Decimal("0.12")  # annualized
    n: int = 20  # returns in the stdev window

    def __post_init__(self) -> None:
        if not isinstance(self.inner, Allocator):
            raise TypeError(f"inner must be an Allocator, got {type(self.inner).__name__}")
        if not isinstance(self.signal, str) or not self.signal:
            raise ValueError("signal must be a non-empty str")
        if not isinstance(self.target_vol, Decimal):
            raise TypeError(f"target_vol must be a Decimal, got {type(self.target_vol).__name__}")
        if not self.target_vol.is_finite() or self.target_vol <= 0:
            raise ValueError(f"target_vol must be > 0, got {self.target_vol}")
        if isinstance(self.n, bool) or not isinstance(self.n, int):
            raise TypeError(f"n must be an int, got {type(self.n).__name__}")
        if self.n < 2:
            raise ValueError(f"n must be >= 2, got {self.n}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "inner": self.inner.id,
            "signal": self.signal,
            "target_vol": _plain(self.target_vol),
            "n": str(self.n),
        }
        for k, v in _params_dict("inner_params", self.inner_params).items():
            out[f"inner.{k}"] = v
        return out


def _vol_params(params: object) -> VolTargetParams:
    if not isinstance(params, VolTargetParams):
        raise TypeError(f"params must be VolTargetParams, got {type(params).__name__}")
    return params


def vol_scale(signal: History | None, data_date: date, n: int, target_vol: Decimal) -> Decimal | None:
    """min(1, target_vol / (stdev_return_window(last n+1 closes through data_date, n) × sqrt(252))).

    Computed in float, returned as ``Decimal(repr(scale))``. None means "do not scale" (1): no
    signal history, fewer than n + 1 bars through ``data_date``, a zero or non-finite stdev, or a
    scale >= 1. Reads only bars dated on or before ``data_date``.
    """
    if signal is None:
        return None
    end = int(np.searchsorted(signal.dates, as_day(data_date), side="right"))
    if end < n + 1:
        return None
    window = signal.close[end - n - 1 : end][None, :]
    sd = float(stdev_return_window(window, n)[0])
    if not math.isfinite(sd) or sd <= 0.0:
        return None
    scale = float(target_vol) / (sd * math.sqrt(TRADING_DAYS))
    if not math.isfinite(scale) or scale >= 1.0:
        return None
    return Decimal(repr(scale))


def _scaled(targets: tuple[Target, ...], scale: Decimal | None) -> tuple[Target, ...]:
    if scale is None:
        return targets
    out: list[Target] = []
    for t in targets:
        w = scale_weight(t.weight, scale)
        if w is not None:
            out.append(replace(t, weight=w))
    return tuple(out)


class VolTargetAllocator:
    """Scales an inner allocator's weights down when the signal's recent volatility is high (L11).

    scale = min(1, target_vol / (stdev of the signal's last n daily returns × sqrt(252))); every
    inner weight × scale is floored to WEIGHT_QUANTUM and targets that floor to zero are dropped.
    Without n + 1 signal bars through d, or with a zero stdev, the inner targets pass unchanged.
    The freed weight is cash (or ``rules.idle_symbol``).
    """

    id = "VOLTARGET"

    def lookback(self, params: Any) -> int:
        p = _vol_params(params)
        return max(p.inner.lookback(p.inner_params), p.n + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _vol_params(params)
        return tuple(sorted(set(p.inner.symbols(p.inner_params)) | {p.signal}))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _vol_params(params)
        return tuple(p.inner.holds(p.inner_params))

    def uses_members(self, params: Any) -> bool:
        p = _vol_params(params)
        return bool(p.inner.uses_members(p.inner_params))

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _vol_params(params)
        _check_call(members, data_date, held)
        inner = p.inner.targets(history, members, data_date, held, p.inner_params)
        return _scaled(inner, vol_scale(history.get(p.signal), data_date, p.n, p.target_vol))

    def prepare(self, history: Mapping[str, History]) -> LazyPrepared:
        return LazyPrepared(history)

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _vol_params(params)
        lazy = _lazy(prepared)
        _check_call(members, data_date, held)
        inner = p.inner.targets_prepared(lazy.of(p.inner), members, data_date, held, p.inner_params)
        return _scaled(inner, vol_scale(lazy.history.get(p.signal), data_date, p.n, p.target_vol))


VOLTARGET = VolTargetAllocator()
