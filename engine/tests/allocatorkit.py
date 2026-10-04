"""Contract checks for every ``Allocator`` (P7a phases 2, 5–8) and two small fake allocators.

Every allocator test module runs the same three checks on its own synthetic histories:

- ``assert_valid_targets``: the shape of one ``targets`` result (types, unique symbols,
  Σ weight, ``last`` = the 4-dp close of the last bar on or before d, no new symbol without a
  bar dated d);
- ``assert_p4_identity``: ``targets_prepared(prepare(H), ...) == targets(H.upto(d), ...)`` and
  ``targets(H, ...) == targets(H.upto(d), ...)`` for every date, held set and params value, and
  (by default) the same result from histories cut to ``lookback(params)`` bars;
- ``assert_no_lookahead``: changing, or deleting, every bar dated on or after session S leaves
  S's targets (read at ``prev_session(S)``) unchanged, on both the single-window and the
  prepared path.

Each check returns how many cases produced a non-empty target tuple, so a caller can assert
the check was not vacuous. ``params`` is always a non-empty list or tuple of params values.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
from stratkit import mutate_from, truncate_before

from seer_engine.dates import prev_session
from seer_engine.prices import to_decimal
from seer_engine.sim.book import Target, equal_weight
from seer_engine.strategies.allocator import Allocator, last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.indicators import return_window, rolling

MembersFn = Callable[[date], AbstractSet[str]]


def everyone(history: Mapping[str, History]) -> MembersFn:
    """A members function: every symbol of ``history`` is a member on every date."""
    members = frozenset(history)
    return lambda d: members


def upto(history: Mapping[str, History], d: date) -> dict[str, History]:
    """Every history cut to its bars dated on or before ``d`` (the single-window input)."""
    return {s: h.upto(d) for s, h in history.items()}


def tail(history: Mapping[str, History], d: date, bars: int) -> dict[str, History]:
    """Every history cut to its last ``bars`` bars dated on or before ``d``."""
    out = {}
    for s, h in history.items():
        cut = h.upto(d)
        start = max(len(cut) - bars, 0)
        out[s] = History(
            s,
            cut.dates[start:],
            cut.open[start:],
            cut.high[start:],
            cut.low[start:],
            cut.close[start:],
            cut.volume[start:],
        )
    return out


def _params_list(params: object) -> tuple[Any, ...]:
    if not isinstance(params, (list, tuple)) or not params:
        raise TypeError("params must be a non-empty list or tuple of params values")
    return tuple(params)


def _held_list(held_sets: object) -> tuple[frozenset[str], ...]:
    if not isinstance(held_sets, (list, tuple)) or not held_sets:
        raise TypeError("held_sets must be a non-empty list or tuple of sets of symbols")
    return tuple(frozenset(h) for h in held_sets)


def assert_valid_targets(
    targets: object,
    history: Mapping[str, History],
    data_date: date,
    held: AbstractSet[str],
    *,
    max_weight_sum: Decimal | None = Decimal(1),
) -> None:
    """One ``targets`` result obeys the Allocator contract (``max_weight_sum=None`` skips Σ weight)."""
    assert isinstance(targets, tuple), f"targets must be a tuple, got {type(targets).__name__}"
    for t in targets:
        assert isinstance(t, Target), f"not a Target: {t!r}"
    symbols = [t.symbol for t in targets]
    assert len(set(symbols)) == len(symbols), f"duplicate symbols on {data_date}: {symbols}"
    if max_weight_sum is not None:
        total = sum((t.weight for t in targets), Decimal(0))
        assert total <= max_weight_sum, f"Σ weight {total} > {max_weight_sum} on {data_date}"
    for t in targets:
        h = history.get(t.symbol)
        assert h is not None, f"{t.symbol} targeted on {data_date} but has no history"
        if h.index_of(data_date) is None:
            assert t.symbol in held, f"{t.symbol} is a new target on {data_date} without a bar that day"
        close = last_close(h, data_date)
        assert close is not None, f"{t.symbol} has no bar on or before {data_date}"
        assert t.last == to_decimal(close), f"{t.symbol} last {t.last} != close {close} on {data_date}"


def assert_p4_identity(
    allocator: Allocator,
    history: Mapping[str, History],
    members_fn: MembersFn,
    dates: Sequence[date],
    held_sets: Sequence[AbstractSet[str]],
    params: Sequence[Any],
    *,
    max_weight_sum: Decimal | None = Decimal(1),
    check_lookback: bool = True,
) -> int:
    """The P4 identity on every (date, held set, params value); returns the non-empty count.

    For each case: the single-window result is valid (``assert_valid_targets``); ``targets`` on
    the full histories equals it (later bars are never read); ``targets_prepared`` on one
    ``prepare(history)`` equals it; and, with ``check_lookback``, ``targets`` on histories cut
    to their last ``lookback(params)`` bars through d equals it.
    """
    assert isinstance(allocator, Allocator), f"{allocator!r} is not an Allocator"
    params_list = _params_list(params)
    held_list = _held_list(held_sets)
    prepared = allocator.prepare(history)
    nonempty = 0
    for d in dates:
        members = frozenset(members_fn(d))
        window = upto(history, d)
        for held in held_list:
            for p in params_list:
                case = f"{allocator.id} on {d}, held={sorted(held)}, params={p!r}"
                single = allocator.targets(window, members, d, held, p)
                assert_valid_targets(single, history, d, held, max_weight_sum=max_weight_sum)
                assert allocator.targets(history, members, d, held, p) == single, f"reads bars after d: {case}"
                assert allocator.targets_prepared(prepared, members, d, held, p) == single, f"P4 identity: {case}"
                if check_lookback:
                    short = tail(history, d, allocator.lookback(p))
                    assert allocator.targets(short, members, d, held, p) == single, f"lookback too short: {case}"
                nonempty += bool(single)
    return nonempty


def assert_no_lookahead(
    allocator: Allocator,
    history: Mapping[str, History],
    members_fn: MembersFn,
    sessions: Sequence[date],
    held_sets: Sequence[AbstractSet[str]],
    params: Sequence[Any],
) -> int:
    """For each session S: targets read at ``prev_session(S)`` ignore every bar dated >= S.

    Two futures per S: every bar dated on or after S changed (``stratkit.mutate_from``) and
    deleted (``stratkit.truncate_before``). Both paths (``targets`` and ``targets_prepared`` on
    a fresh ``prepare``) must equal the result on the untouched history. Returns the non-empty count.
    """
    assert isinstance(allocator, Allocator), f"{allocator!r} is not an Allocator"
    params_list = _params_list(params)
    held_list = _held_list(held_sets)
    prepared = allocator.prepare(history)
    nonempty = 0
    for s in sessions:
        d = prev_session(s)
        members = frozenset(members_fn(d))
        futures = {
            "changed": {k: mutate_from(h, s) for k, h in history.items()},
            "deleted": {k: truncate_before(h, s) for k, h in history.items()},
        }
        prepared_futures = {name: allocator.prepare(f) for name, f in futures.items()}
        for held in held_list:
            for p in params_list:
                case = f"{allocator.id} for session {s}, held={sorted(held)}, params={p!r}"
                before = allocator.targets(history, members, d, held, p)
                assert allocator.targets_prepared(prepared, members, d, held, p) == before, f"P4 identity: {case}"
                for name, future in futures.items():
                    assert allocator.targets(future, members, d, held, p) == before, f"look-ahead ({name}): {case}"
                    got = allocator.targets_prepared(prepared_futures[name], members, d, held, p)
                    assert got == before, f"look-ahead, prepared ({name}): {case}"
                nonempty += bool(before)
    return nonempty


# --------------------------------------------------------------------------- fake allocators


def _plain(w: Decimal) -> str:
    return format(w.normalize(), "f")


@dataclass(frozen=True, slots=True)
class FixedParams:
    weights: tuple[tuple[str, Decimal], ...]  # (symbol, weight) in rank order

    def as_dict(self) -> dict[str, str]:
        return {s: _plain(w) for s, w in self.weights}


class FixedAllocator:
    """Fixed symbols at fixed weights, each while it has a bar on d; a held one without a bar is kept."""

    id = "FAKE_FIXED"

    def lookback(self, params: Any) -> int:
        return 1

    def symbols(self, params: Any) -> tuple[str, ...]:
        return tuple(sorted({s for s, _ in params.weights}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return self.symbols(params)

    def uses_members(self, params: Any) -> bool:
        return False

    def targets(self, history, members, data_date, held, params) -> tuple[Target, ...]:
        out = []
        for symbol, w in params.weights:
            h = history.get(symbol)
            close = last_close(h, data_date)
            if close is None or (h.index_of(data_date) is None and symbol not in held):
                continue
            t = target_from_close(symbol, close, w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def prepare(self, history):
        return dict(history)

    def targets_prepared(self, prepared, members, data_date, held, params) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


FIXED = FixedAllocator()


@dataclass(frozen=True, slots=True)
class MomentumParams:
    top: int = 2

    def as_dict(self) -> dict[str, str]:
        return {"top": str(self.top)}


class MomentumFake:
    """Members with a bar on d ranked by ``n``-bar return (desc, then symbol); the top K with a
    positive return at ``equal_weight(top)``. ``prepare`` precomputes the returns with
    ``rolling``, so its path really differs from the single-window one."""

    id = "FAKE_MOM"

    def __init__(self, n: int = 5) -> None:
        self.n = n

    def lookback(self, params: Any) -> int:
        return self.n + 1

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ()

    def holds(self, params: Any) -> tuple[str, ...]:
        return ()

    def uses_members(self, params: Any) -> bool:
        return True

    def _ranked(self, rows: list[tuple[str, float, float]], params: MomentumParams) -> tuple[Target, ...]:
        rows = sorted((r for r in rows if np.isfinite(r[1]) and r[1] > 0.0), key=lambda r: (-r[1], r[0]))
        w = equal_weight(params.top)
        out = []
        for symbol, _, close in rows[: params.top]:
            t = target_from_close(symbol, close, w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history, members, data_date, held, params) -> tuple[Target, ...]:
        rows = []
        for s in sorted(history):
            h = history[s]
            i = h.index_of(data_date)
            if s not in members or i is None or i < self.n:
                continue
            mom = float(return_window(h.close[None, i - self.n : i + 1], self.n)[0])
            rows.append((s, mom, float(h.close[i])))
        return self._ranked(rows, params)

    def prepare(self, history):
        return {s: (h, rolling(return_window, h.close, window=self.n + 1, n=self.n)) for s, h in history.items()}

    def targets_prepared(self, prepared, members, data_date, held, params) -> tuple[Target, ...]:
        rows = []
        for s in sorted(prepared):
            h, mom = prepared[s]
            i = h.index_of(data_date)
            if s not in members or i is None or i < self.n:
                continue
            rows.append((s, float(mom[i]), float(h.close[i])))
        return self._ranked(rows, params)


MOMENTUM = MomentumFake()
