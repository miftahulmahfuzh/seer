"""Claude twins: an original's own method, minus what Claude objected to in time (Seer Adversarial).

Plan seer-adversarial phase 2; contracts C2 (twin rows) and C3 (verdict application); owner
decisions 1, 4 and 6 of docs/plans/2026-11-05-seer-adversarial-design.md (mcp-notes repo).

A twin is a roster row ``<ORIGINAL>-CX`` that runs its original's method with exactly one change:
a symbol Claude objected to, before the session it was picked for opened, is not bought. This
module is that change, as two wrappers -- one around a bracket ``Strategy``, one around a book
``Allocator`` -- plus the pure rule that turns stored verdict rows into "what was objected to,
per session".

**Why wrappers and not a new strategy.** Wherever Claude said nothing the twin must be its
original to the last decimal: the same ranking, sizing, fees, deposits and evidence. Wrapping the
original's own object keeps every one of those on the original's code path; the wrapper only ever
removes symbols from what that object returned.

**The cutoff (C3, honesty rule "information cutoff").** A verdict counts for session S only when
its ``decided_at`` is strictly before ``dates.session_open_utc(S)``. Per symbol the latest such row
wins, a tie on ``decided_at`` going to the higher id (the later insert). ``superseded_by`` is
history for people and is never read here: "the latest review before the open" already says which
one stood when the market opened. Only ``object`` drops a symbol. ``agree``, ``unsure``, a late
row and no row at all keep it -- the twin copies the original, which is what "absent" and
"paused" mean (owner decision 4).

**Bracket (TwinStrategy).** ``picks`` is the inner strategy's ranked list minus the symbols
objected to for ``next_session(data_date)``. ``sim.size_picks`` walks that list into the free
slots, so the next-ranked pick takes an objected pick's slot exactly as it does for C (owner
decision 1).

**Book (TwinBook).** On a rank session (a kickoff included) the inner targets minus the objected
symbols, each kept weight scaled by ``total / kept_total`` and rounded DOWN to ``WEIGHT_QUANTUM``,
so the twin is as invested as the original chose to be and never more (pro rata, no
up-weighting: owner decision 1). Every target objected gives ``()``, which is what the original's
own empty decision is, so ``_with_idle`` and the step treat it exactly the same way (plan Decision
D6). A resize-only session (split cadence) ignores objections: its targets only set the exposure
the frozen basket is re-scaled to, and that basket was filtered when it was ranked (Decision D3).
A kickoff that lands on a resize-only session is therefore not filtered -- conservative: it copies
the original, as an absent review would. An objected name the book holds drops out of the targets,
so ``sim.book.step_book`` sells it and the fees count against Claude (owner decision 6).

``TwinBook`` forwards ``prepare_market`` only when its inner allocator is ``MarketAware``
(``MarketAwareTwinBook``): ``isinstance(x, MarketAware)`` is attribute presence, so a wrapper that
always had it would send every plain allocator down the prepared branch and the twin would no
longer be its original's code path.

**The lag (Decision D1)** is not here: ``commands.paper`` steps a twin as if tonight's data date
were the previous session, so every verdict it reads has a cutoff already in the past and a replay
on any later night reads the same set (``paper_check`` stays stable).

Pure, like every ``strategies`` module (tests/test_strategy_purity.py).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import ROUND_DOWN, Decimal
from types import MappingProxyType
from typing import Any

from seer_engine import dates
from seer_engine.sim import Pick
from seer_engine.sim.book import WEIGHT_QUANTUM, Target
from seer_engine.sim.rules import TradeRules, is_resize_session
from seer_engine.strategies.allocator import Allocator, MarketAware
from seer_engine.strategies.base import History, Strategy

#: The rule this module implements, frozen into every twin's spec (``paper.roster.spec``). A change
#: to what a twin does with a verdict is a change to the strategy: it moves the twin's digest, and
#: ``store.check_digest`` then refuses the twin's next night (a changed strategy needs a new id).
FILTER_VERSION = "adversary-v1"

#: ``adversary_verdicts.verdict``'s CHECK (migration 027), as a Python value.
VERDICTS: tuple[str, ...] = ("agree", "object", "unsure")

Objected = Mapping[date, frozenset[str]]

#: One ``adversary_verdicts`` row as ``store.objected_between`` reads it:
#: ``(session_date, symbol, verdict, decided_at, id)``.
VerdictRow = tuple[date, str, str, datetime, int]


def _day(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    return d


def _objected(objected: Mapping[date, Iterable[str]]) -> Objected:
    """``objected`` as a read-only ``{session: frozenset(symbols)}``; empty sessions dropped."""
    if not isinstance(objected, Mapping):
        raise TypeError(f"objected must be a Mapping, got {type(objected).__name__}")
    out: dict[date, frozenset[str]] = {}
    for session, symbols in objected.items():
        _day("objected session", session)
        if isinstance(symbols, str):
            raise TypeError(f"objected[{session}] must be a set of symbols, got a str")
        frozen = frozenset(symbols)
        for s in frozen:
            if not isinstance(s, str) or not s:
                raise TypeError(f"objected[{session}] holds a non-symbol {s!r}")
        if frozen:
            out[session] = frozen
    return MappingProxyType(out)


def objected_map(rows: Iterable[VerdictRow]) -> dict[date, frozenset[str]]:
    """``{session: symbols whose standing verdict at the session's open is 'object'}`` (C3).

    For each ``(session, symbol)``, among the rows with ``decided_at < session_open_utc(session)``,
    the one with the greatest ``(decided_at, id)`` stands; the symbol is in the result when that
    row says ``object``. A session nobody objected in is absent: look up with
    ``.get(session, frozenset())``.

    ValueError on a verdict outside :data:`VERDICTS` or a naive ``decided_at``; TypeError on a
    ``session_date`` that is not a date. These are database rows, validated once here, at the edge.
    """
    standing: dict[tuple[date, str], tuple[datetime, int, str]] = {}
    for session, symbol, verdict, decided_at, row_id in rows:
        _day("session_date", session)
        if verdict not in VERDICTS:
            raise ValueError(f"{session} {symbol}: verdict {verdict!r} is not one of {VERDICTS}")
        if not isinstance(decided_at, datetime) or decided_at.utcoffset() is None:
            raise ValueError(f"{session} {symbol}: decided_at must be a tz-aware datetime, got {decided_at!r}")
        if decided_at >= dates.session_open_utc(session):
            continue  # decided at or after the open: late, the twin copies the original
        key = (session, symbol)
        seen = standing.get(key)
        if seen is None or (decided_at, row_id) > (seen[0], seen[1]):
            standing[key] = (decided_at, row_id, verdict)
    out: dict[date, set[str]] = {}
    for (session, symbol), (_, _, verdict) in standing.items():
        if verdict == "object":
            out.setdefault(session, set()).add(symbol)
    return {session: frozenset(symbols) for session, symbols in sorted(out.items())}


def renormalised(wanted: Sequence[Target], drop: AbstractSet[str]) -> tuple[Target, ...]:
    """``wanted`` without the ``drop`` symbols, the rest scaled pro rata to the same total weight.

    Each kept weight is ``weight * total / kept_total`` rounded DOWN to ``WEIGHT_QUANTUM``, so the
    result never weighs more than ``wanted`` did. ``wanted`` itself when nothing is dropped; ``()``
    when everything is. Prices, limits, stops and takes are kept as the allocator set them.
    """
    targets = tuple(wanted)
    kept = tuple(t for t in targets if t.symbol not in drop)
    if len(kept) == len(targets):
        return targets
    if not kept:
        return ()
    total = sum((t.weight for t in targets), Decimal(0))
    kept_total = sum((t.weight for t in kept), Decimal(0))
    out: list[Target] = []
    for t in kept:
        weight = min((t.weight * total / kept_total).quantize(WEIGHT_QUANTUM, rounding=ROUND_DOWN), Decimal(1))
        if weight > 0:
            out.append(replace(t, weight=weight))
    return tuple(out)


@dataclass(frozen=True, eq=False)
class TwinStrategy:
    """A bracket ``Strategy``'s Claude twin: ``inner``'s ranked picks minus the objected symbols.

    ``objected`` maps the session being bought for to the symbols dropped for it; picks for
    ``data_date`` are for ``next_session(data_date)``, so that is the key looked up. The roster
    object carries no objections (it buys exactly what ``inner`` buys); ``commands.paper`` and
    ``paper_check`` hand the engine a copy carrying them (``with_objected``).
    """

    inner: Strategy
    objected: Objected = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.inner, Strategy):
            raise TypeError(f"inner must be a Strategy, got {type(self.inner).__name__}")
        if isinstance(self.inner, TwinStrategy):
            raise TypeError("a Claude twin wraps an original, never another twin")
        object.__setattr__(self, "objected", _objected(self.objected))

    @property
    def id(self) -> str:
        return self.inner.id

    @property
    def lookback(self) -> int:
        return self.inner.lookback

    def _dropped(self, data_date: date) -> frozenset[str]:
        if not self.objected:
            return frozenset()
        return self.objected.get(dates.next_session(data_date), frozenset())

    def picks(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        params: Any,
    ) -> list[Pick]:
        drop = self._dropped(data_date)
        return [p for p in self.inner.picks(history, members, data_date, params) if p.symbol not in drop]

    def prepare(self, history: Mapping[str, History]) -> Any:
        return self.inner.prepare(history)

    def picks_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        params: Any,
    ) -> list[Pick]:
        drop = self._dropped(data_date)
        return [p for p in self.inner.picks_prepared(prepared, members, data_date, params) if p.symbol not in drop]

    def with_objected(self, objected: Mapping[date, Iterable[str]]) -> TwinStrategy:
        """This twin carrying ``objected`` (same inner strategy)."""
        return replace(self, objected=objected)


@dataclass(frozen=True, eq=False)
class TwinBook:
    """A book ``Allocator``'s Claude twin: ``inner``'s targets minus the objected symbols, pro rata.

    ``rules`` are the twin's (= its original's) book rules, read only to tell a resize-only session
    from a rank session. ``objected`` is keyed by the session decided, ``next_session(data_date)``.
    """

    inner: Allocator
    rules: TradeRules
    objected: Objected = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.inner, Allocator):
            raise TypeError(f"inner must be an Allocator, got {type(self.inner).__name__}")
        if isinstance(self.inner, TwinBook):
            raise TypeError("a Claude twin wraps an original, never another twin")
        if not isinstance(self.rules, TradeRules) or self.rules.engine != "book":
            raise ValueError(f"a book twin needs book rules, got {self.rules!r}")
        object.__setattr__(self, "objected", _objected(self.objected))

    @property
    def id(self) -> str:
        return self.inner.id

    def lookback(self, params: Any) -> int:
        return self.inner.lookback(params)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return self.inner.symbols(params)

    def holds(self, params: Any) -> tuple[str, ...]:
        return self.inner.holds(params)

    def uses_members(self, params: Any) -> bool:
        return self.inner.uses_members(params)

    def _filter(self, data_date: date, wanted: Iterable[Target]) -> tuple[Target, ...]:
        targets = tuple(wanted)
        if not self.objected:
            return targets
        session = dates.next_session(data_date)
        drop = self.objected.get(session)
        if not drop or is_resize_session(self.rules, session):
            return targets
        return renormalised(targets, drop)

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        return self._filter(data_date, self.inner.targets(history, members, data_date, held, params))

    def prepare(self, history: Mapping[str, History]) -> Any:
        return self.inner.prepare(history)

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        return self._filter(data_date, self.inner.targets_prepared(prepared, members, data_date, held, params))

    def with_objected(self, objected: Mapping[date, Iterable[str]]) -> TwinBook:
        """This twin carrying ``objected`` (same inner allocator and rules, same class)."""
        return replace(self, objected=objected)


@dataclass(frozen=True, eq=False)
class MarketAwareTwinBook(TwinBook):
    """``TwinBook`` around a ``MarketAware`` allocator (FUNDAMENTAL): forwards ``prepare_market``."""

    def prepare_market(self, market: Any) -> Any:
        return self.inner.prepare_market(market)  # type: ignore[attr-defined]


def twin_book(inner: Allocator, rules: TradeRules) -> TwinBook:
    """The book twin of ``inner`` under ``rules``, MarketAware exactly when ``inner`` is."""
    if isinstance(inner, MarketAware):
        return MarketAwareTwinBook(inner=inner, rules=rules)
    return TwinBook(inner=inner, rules=rules)
