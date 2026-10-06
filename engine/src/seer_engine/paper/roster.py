"""The paper roster (handover D1, D2, D4; plan contract C2; roster-promotion-pipeline R2, D2, D3).

Pure: no database, no clock, no I/O. Every portfolio paper-trades every night on its own paper
clock; this module is the single place that says what each one *is*, given the row that says it
exists.

**The roster is data; the objects are code (D2).** A ``strategies`` row carries everything about
an entry except the live Python object: its display fields, its ``engine``, its ``rules_id``, its
``registry_id``, its gate note, its lifecycle (``status``, ``paper_end``) -- and ``object_name``,
a stable name. :data:`RESOLVER` maps that name to the object, and :func:`from_row` turns one row
plus the resolver into a :class:`RosterEntry`. A database cannot hold an ``Allocator``, and
``eval``-ing an import path out of a row would make the table a code-execution surface, so the
resolver is the smallest thing that must stay in code. **Adding a strategy is a row plus, at
most, one resolver entry** -- never an edit to this builder.

A row whose ``object_name`` is not in :data:`RESOLVER` raises :class:`UnknownObject`; an unknown
``rules_id`` raises :class:`UnknownRules`; anything else malformed raises :class:`BadRosterRow`.
All three are :class:`RosterError`, all three stop the night, and all three name **the strategy id
and the offending value**. A typo must never quietly drop a portfolio and leave a hole in its
equity curve, and the message must say which portfolio.

:data:`SEED_ROWS` is the six rows ``db/migrations/003_paper.sql``, ``004_news_veto.sql``,
``006_roster.sql`` and ``007_fnd.sql`` write, as data; :data:`ROSTER` is ``from_rows(SEED_ROWS)``. The compiled roster
and the stored roster therefore travel the *same* builder, and
``tests/test_paper_roster.py`` checks both against a migrated database.

- ``SPY``: buy-and-hold SPY with dividends reinvested (``backtest.benchmark.buy_and_hold``
  rules), the champion and the yardstick (D2).
- ``A``: Strategy A with ``STRATEGY_A_PARAMS`` under ``DESIGN_V0`` (the bracket engine).
- ``F4-MOM12-N20-TREND`` and ``F1-SPY-SMA200-M``: the P7a registry entries of those ids,
  taken from ``backtest.registry.REGISTRY`` as they are (the registry is read, never edited,
  and never appended to -- it is the dev run's fixed candidate set), under their own
  ``MONTHLY_HOLD`` rules (the book engine).
- ``C``: Strategy C (``strategies.c.STRATEGY_C`` with ``STRATEGY_C_PARAMS``) under
  ``DESIGN_V0``: A's ranked candidates minus every symbol the stored news check did not
  allow (strategy-c-news-veto handover D1, D5). The roster object carries no verdicts, so
  it never buys on its own; ``paper`` and ``paper_check`` hand the engine a copy carrying
  the stored verdicts.
- ``FND``: point-in-time SEC fundamental factors (``strategies.f_fundamental.FUNDAMENTAL`` with
  ``FUNDAMENTAL_PARAMS``) under ``MONTHLY_HOLD``, the book engine. It is the one roster object
  that reads more of the ``Market`` than its bars: it satisfies ``allocator.MarketAware``, so
  ``paper.book.decide_book`` prepares it from the whole ``Market`` and it ranks on
  ``market.fundamentals``. On a ``Market`` with no panel it targets nothing -- the honest reading
  of "no filing is known", and the reason a database without ``005_fundamentals.sql`` applied
  gives an all-cash FND rather than a wrong one.

**The frozen spec (D4).** :func:`spec` is the entry's trial-defining parts as a JSON-ready
dict of strings: engine, the strategy/allocator object (module-level name and its ``id``),
the registry id and the registry's own ``candidate_digest`` (book entries), every
``TradeRules`` field, every parameter (``as_dict``), and the starting capital in IDR.
:func:`spec_text` is its canonical text (sorted keys, no whitespace, ASCII) and
:func:`spec_digest` the sha256 hex of that text. Both take a plain mapping, so a spec read
back from ``strategies.params->'spec'`` recomputes to the same digest -- which is exactly what
makes a database-stored roster *checkable*. The digests are pinned in
``tests/test_paper_roster.py``: a changed strategy needs a **new id** with its own paper clock,
never an edited entry (``paper`` refuses a started id whose stored digest differs). ``status``,
``paper_end``, ``gate_note`` and ``gate_applicable`` are **not** in the spec, deliberately:
retiring a strategy or correcting a note must not move a live digest.

``backtest_gate`` is a display fact for the go-live checklist (D12), not part of the spec:
correcting its note does not reset a paper clock. Every entry is ``passed: false`` today.
``FND`` is on the roster having failed its gate too (six M0005 dev-window trials, all six failed,
all six recorded in ``lab/lab.sqlite``): passing a gate has never been this roster's admission
criterion, and the gates bind the real-money decision, not paper membership.
An entry with ``gate_applicable=False`` (C, an LLM strategy: design §1 item 5, handover D9)
also says ``applicable: false``; the four quant/benchmark entries' gate dicts are unchanged.

``status`` is lifecycle, not definition (D3, invariants 3 and 4): a retired entry keeps every
row it ever wrote and stays on the leaderboard: it only stops trading. :func:`active` is the
filter the paper night uses.

:data:`MAX_LOOKBACK_BARS` is the most bars through a data date any object on the **seeded** roster
reads (FACTOR's ``factor_lookback`` = 253); the paper store's windowed history load must cover it.
It is a property of :data:`SEED_ROWS`, not of whatever a live database holds, and the paper night
does not read it: ``commands.paper._check_window`` recomputes the max over the entries that trade
tonight. The guard against admitting a strategy whose lookback the night's bar window cannot feed
belongs to ``commands.promote`` at promotion time, not here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, fields, replace
from datetime import date
from decimal import Decimal
from typing import Any, Literal, Protocol

from seer_engine.backtest.registry import REGISTRY, candidate_digest
from seer_engine.backtest.runner import INITIAL_IDR
from seer_engine.sim import COST_RATE
from seer_engine.sim.rules import PRESETS, TradeRules, is_pinned_default
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS
from seer_engine.strategies.allocator import Allocator
from seer_engine.strategies.base import Strategy
from seer_engine.strategies.c import STRATEGY_C, STRATEGY_C_PARAMS
from seer_engine.strategies.f_factor import FACTOR
from seer_engine.strategies.f_fundamental import FUNDAMENTAL, FundamentalParams
from seer_engine.strategies.f_index import TIMING

Engine = Literal["bracket", "book", "benchmark"]
Status = Literal["active", "retired"]

BENCHMARK_ID = "SPY"
F4_ID = "F4-MOM12-N20-TREND"
F1_ID = "F1-SPY-SMA200-M"
FND_ID = "FND"
# The fractional-share versions (2026-10-07): the same methods under monthly-hold-frac. A changed
# rule set is a new id (frozen roster); the whole-share three above are retired by 010.
F4_FR_ID = "F4-MOM12-N20-TREND-FR"
F1_FR_ID = "F1-SPY-SMA200-M-FR"
FND_FR_ID = "FND-FR"

#: ``object_name`` of the benchmark: ``backtest.benchmark.buy_and_hold``, which is rules, not an object.
BENCHMARK_OBJECT = "buy_and_hold"

#: ``strategies.engine``'s CHECK, as a Python value.
ENGINES: tuple[Engine, ...] = ("bracket", "book", "benchmark")

#: ``strategies.status``'s CHECK, as a Python value.
STATUSES: tuple[Status, ...] = ("active", "retired")


# --------------------------------------------------------------------------- errors


class RosterError(LookupError):
    """A ``strategies`` row cannot be turned into a roster entry.

    Always raised, never swallowed: ``paper`` turns it into a failed paper step for the whole
    night. A roster entry that cannot be built must stop the run, because the alternative --
    skipping it -- leaves a gap in that portfolio's equity curve that nothing later can fill.
    """


class UnknownObject(RosterError):
    """``object_name`` is not a key of :data:`RESOLVER` (a typo, or a strategy not deployed here)."""


class UnknownRules(RosterError):
    """``rules_id`` is not the id of a ``sim.rules`` preset."""


class BadRosterRow(RosterError):
    """The row is internally inconsistent (bad engine or status, missing or surplus fields)."""


# --------------------------------------------------------------------------- the entry


@dataclass(frozen=True, slots=True)
class RosterEntry:
    """One paper portfolio.

    ``obj`` is the ``Strategy`` (bracket), the ``Allocator`` (book) or ``None`` (benchmark);
    ``object_name`` is its :data:`RESOLVER` key -- its module-level name (``STRATEGY_A``,
    ``FACTOR``, ``TIMING``) or ``buy_and_hold`` for the benchmark. ``rules`` is ``None`` only
    for the benchmark. ``lookback`` is the bars through a data date ``obj`` reads (1 for the
    benchmark, which reads only the session's own bar). ``gate_applicable`` is ``False`` only
    for an entry the quant backtest gate does not apply to (C); it changes ``backtest_gate``,
    never the spec.

    ``status`` and ``paper_end`` are lifecycle, carried here so one value answers "what is this
    portfolio and is it still trading?". Neither is in :func:`spec`: retiring a strategy must
    not move its frozen digest.
    """

    id: str
    name: str
    sub: str
    icon: str
    is_champion: bool
    is_benchmark: bool
    sort: int
    engine: Engine
    rules: TradeRules | None
    obj: Strategy | Allocator | None
    object_name: str
    params: Any
    registry_id: str | None
    lookback: int
    gate_note: str
    gate_applicable: bool = True
    status: Status = "active"
    paper_end: date | None = None

    @property
    def rules_id(self) -> str | None:
        """``strategies.rules_id``: the rules preset id, ``None`` for the benchmark."""
        return None if self.rules is None else self.rules.id


# --------------------------------------------------------------------------- the resolver (D2)


@dataclass(frozen=True, slots=True)
class Binding:
    """What a ``object_name`` resolves to: the live object and where its params come from.

    ``params`` is the object's own frozen params value, or ``None`` when ``from_registry`` --
    then the row's ``registry_id`` names the ``backtest.registry`` candidate the params (and
    the identity check) come from, exactly as F4 and F1 have always worked.
    """

    obj: Strategy | Allocator | None
    params: Any = None
    from_registry: bool = False


# FND's parameters, written out here rather than imported from
# ``lab.methods.m0005_fundamental_factors``. They are that module's ``COMPOSITE`` value for value
# -- the four-factor blend, equal weights, top 20, the shipped liquidity floors, no trend gate --
# but the lab module must not become an input to a paper spec digest: its ``source_sha`` is frozen
# in ``lab/lab.sqlite`` and editing it for a lab reason would silently re-digest a started paper
# strategy. The roster says what it runs, in its own file, as it does for every other entry.
#
# WHY composite AND NOT the best of the six. M0005 recorded six dev-window trials; all six failed
# and M0005-VAL had the highest total return of them. Picking it would be choosing on the
# multiple-testing noise the lab's ``trials`` table exists to count. ``composite`` is the a-priori
# blend of the four factor families the method's sources name (Fama-French value, Novy-Marx gross
# profitability, Bernard-Thomas SUE, return on equity), chosen before the numbers and not by them.
#
# It is VALUE-EQUAL to m0005's ``COMPOSITE``, which is what `promote --candidate M0005-ALL` writes
# the spec from. That equality is pinned by a test (tests/test_paper_fnd.py), because if the two
# ever drift the promoted row's stored digest and the roster's recomputed digest differ and
# `store.check_digest` refuses FND's second night with a SpecMismatch. The test is in the test
# file, where importing the lab module is free; this file must never import it.
FUNDAMENTAL_PARAMS = FundamentalParams(rank="composite", top=20)


#: The one code-side table (D2). **This is the extension point**: a new strategy is a row in
#: ``strategies`` plus, if its object is not already here, one entry here. Nothing else in this
#: module changes to add a strategy. Keys are stable forever -- a stored spec names one, so
#: renaming a key would move a live digest. Append; never rename, never remove a key a started
#: strategy's spec still names.
RESOLVER: dict[str, Binding] = {
    BENCHMARK_OBJECT: Binding(obj=None),
    "STRATEGY_A": Binding(obj=STRATEGY_A, params=STRATEGY_A_PARAMS),
    "STRATEGY_C": Binding(obj=STRATEGY_C, params=STRATEGY_C_PARAMS),
    "FACTOR": Binding(obj=FACTOR, from_registry=True),
    "TIMING": Binding(obj=TIMING, from_registry=True),
    "FUNDAMENTAL": Binding(obj=FUNDAMENTAL, params=FUNDAMENTAL_PARAMS),
}


def resolver_names() -> tuple[str, ...]:
    """Every ``object_name`` this build knows, sorted (what ``promote`` validates against)."""
    return tuple(sorted(RESOLVER))


def resolve(object_name: object) -> Binding:
    """The :class:`Binding` for ``object_name``; :class:`UnknownObject` when there is none.

    Never returns a default and never returns ``None``: an unresolvable name is a hard error
    (invariant 9), because a skipped portfolio is a silent hole in a track record.
    """
    if isinstance(object_name, str):
        found = RESOLVER.get(object_name)
        if found is not None:
            return found
    raise UnknownObject(
        f"roster object name {object_name!r} is not in paper.roster.RESOLVER; "
        f"known names: {', '.join(resolver_names())}"
    )


_PRESETS: dict[str, TradeRules] = {r.id: r for r in PRESETS}


def rules_for(rules_id: str | None) -> TradeRules | None:
    """The ``sim.rules`` preset ``rules_id`` (the same object, so ``is DESIGN_V0`` holds).

    ``None`` maps to ``None`` (the benchmark trades under no rule set). An id that is not a
    preset raises :class:`UnknownRules`.
    """
    if rules_id is None:
        return None
    found = _PRESETS.get(rules_id) if isinstance(rules_id, str) else None
    if found is None:
        raise UnknownRules(
            f"rules_id {rules_id!r} is not a sim.rules preset; known ids: {', '.join(sorted(_PRESETS))}"
        )
    return found


# --------------------------------------------------------------------------- the row


class Row(Protocol):
    """What :func:`from_row` reads off a ``strategies`` row.

    ``paper.store.StrategyRow`` satisfies this structurally, which is why this module imports
    nothing from ``store`` (and stays pure: ``tests/test_strategy_purity.py``). Types are the
    column types, nullables included -- validating them is :func:`from_row`'s job.
    """

    id: str
    name: str
    sub: str
    icon: str
    is_champion: bool
    is_benchmark: bool
    sort: int
    engine: str | None
    rules_id: str | None
    object_name: str | None
    registry_id: str | None
    gate_note: str | None
    gate_applicable: bool
    status: str
    paper_end: date | None


@dataclass(frozen=True, slots=True)
class RosterRow:
    """One ``strategies`` row as plain data: the :class:`Row` the seeds and the tests use."""

    id: str
    name: str
    sub: str
    icon: str
    is_champion: bool
    is_benchmark: bool
    sort: int
    engine: str | None
    rules_id: str | None
    object_name: str | None
    registry_id: str | None
    gate_note: str | None
    gate_applicable: bool = True
    status: str = "active"
    paper_end: date | None = None


def _registered(registry_id: str, expected_obj: Allocator, rules: TradeRules) -> tuple[Allocator, Any]:
    """(allocator, params) of the registry entry ``registry_id``, checked against what the
    roster expects (the registry is a closed record; a mismatch is a programming error)."""
    found = [c for c in REGISTRY if c.id == registry_id]
    if len(found) != 1:
        raise LookupError(f"registry has {len(found)} entries with id {registry_id!r}, expected 1")
    c = found[0]
    if c.allocator is not expected_obj:
        raise LookupError(f"{registry_id}: registry allocator is <{c.allocator.id}>, expected <{expected_obj.id}>")
    # A roster entry may trade a registry candidate in fractional shares (010: Gotrade takes
    # fractional limit orders): its rules may differ from the candidate's in the share granularity
    # and the id that names it, and in nothing else.
    if replace(rules, id=c.rules.id, fractional=c.rules.fractional) != c.rules:
        raise LookupError(f"{registry_id}: registry rules are {c.rules.id!r}, expected {rules.id!r}")
    return c.allocator, c.params


def from_row(row: Row) -> RosterEntry:
    """One ``strategies`` row as a :class:`RosterEntry`, through :data:`RESOLVER`.

    Every failure is a :class:`RosterError` naming the row and what is wrong with it: there is
    no path through this function that returns a usable-looking entry for a row it did not fully
    understand, and no path that returns ``None``.
    """
    sid = row.id
    if not isinstance(sid, str) or not sid:
        raise BadRosterRow(f"a roster row needs a non-empty id, got {sid!r}")
    engine = row.engine
    if engine not in ENGINES:
        raise BadRosterRow(f"{sid!r}: engine {engine!r} is not one of {ENGINES}")
    # Every RosterError out of this function names the ROW, not just the bad value: `paper`'s
    # failed-step message is the only place an operator sees it, and "NO_SUCH_OBJECT is not in
    # RESOLVER" without an id does not say which portfolio stopped the night (invariant 9).
    try:
        binding = resolve(row.object_name)
    except UnknownObject as exc:
        raise UnknownObject(f"{sid!r}: {exc}") from exc
    object_name: str = row.object_name  # resolve() accepted it, so it is a str
    try:
        rules = rules_for(row.rules_id)
    except UnknownRules as exc:
        raise UnknownRules(f"{sid!r}: {exc}") from exc
    registry_id = row.registry_id
    if engine == "benchmark":
        if binding.obj is not None or rules is not None or registry_id is not None:
            raise BadRosterRow(
                f"{sid!r}: a benchmark row carries no object, rules_id or registry_id "
                f"(object_name {object_name!r}, rules_id {row.rules_id!r}, registry_id {registry_id!r})"
            )
        obj: Strategy | Allocator | None = None
        params: Any = None
        lookback = 1
    else:
        if rules is None:
            raise BadRosterRow(f"{sid!r}: a {engine} row needs a rules_id")
        if binding.obj is None:
            raise BadRosterRow(
                f"{sid!r}: object {object_name!r} has no object; it can only run the benchmark engine"
            )
        if binding.from_registry:
            if not isinstance(registry_id, str) or not registry_id:
                raise BadRosterRow(
                    f"{sid!r}: object {object_name!r} takes its params from backtest.registry; "
                    f"registry_id is {registry_id!r}"
                )
            obj, params = _registered(registry_id, binding.obj, rules)
        else:
            if registry_id is not None:
                raise BadRosterRow(
                    f"{sid!r}: object {object_name!r} carries its own params; registry_id must be "
                    f"NULL, got {registry_id!r}"
                )
            obj, params = binding.obj, binding.params
        # Strategy.lookback is an int attribute; Allocator.lookback is a method of its params.
        lookback = obj.lookback(params) if engine == "book" else obj.lookback
    gate_note = row.gate_note
    if not isinstance(gate_note, str) or not gate_note:
        raise BadRosterRow(
            f"{sid!r}: gate_note is {gate_note!r}; every roster row states its backtest gate, "
            f"and 'failed' or 'not applicable' is a complete answer"
        )
    status = row.status
    if status not in STATUSES:
        raise BadRosterRow(f"{sid!r}: status {status!r} is not one of {STATUSES}")
    paper_end = row.paper_end
    if paper_end is not None and not isinstance(paper_end, date):
        raise BadRosterRow(f"{sid!r}: paper_end must be a date or None, got {paper_end!r}")
    return RosterEntry(
        id=sid,
        name=row.name,
        sub=row.sub,
        icon=row.icon,
        is_champion=bool(row.is_champion),
        is_benchmark=bool(row.is_benchmark),
        sort=int(row.sort),
        engine=engine,
        rules=rules,
        obj=obj,
        object_name=object_name,
        params=params,
        registry_id=registry_id,
        lookback=int(lookback),
        gate_note=gate_note,
        gate_applicable=bool(row.gate_applicable),
        status=status,
        paper_end=paper_end,
    )


def from_rows(rows: Iterable[Row]) -> tuple[RosterEntry, ...]:
    """Every row as an entry, by ``(sort, id)``. Raises on the FIRST row it cannot build.

    No row is ever dropped: either every row given becomes an entry, or nothing is returned.
    """
    entries = tuple(sorted((from_row(r) for r in rows), key=lambda e: (e.sort, e.id)))
    ids = [e.id for e in entries]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise BadRosterRow(f"the roster rows carry duplicate ids: {dupes}")
    return entries


# --------------------------------------------------------------------------- the seeded roster

#: The rows ``003_paper.sql``, ``004_news_veto.sql`` and ``006_roster.sql`` write, as data.
#: ``tests/test_paper_roster.py`` checks this equals a migrated database's ``strategies`` rows.
SEED_ROWS: tuple[RosterRow, ...] = (
    RosterRow(
        id=BENCHMARK_ID,
        name="SPY",
        sub="S&P 500, buy and hold",
        icon="landmark",
        is_champion=True,
        is_benchmark=True,
        sort=1,
        engine="benchmark",
        rules_id=None,
        object_name=BENCHMARK_OBJECT,
        registry_id=None,
        gate_note="Benchmark, not a strategy: it has no backtest gate and is never a Seer pick",
    ),
    RosterRow(
        id="A",
        name="A · Quant",
        sub="Mean reversion, 5-day brackets",
        icon="sigma",
        is_champion=False,
        is_benchmark=False,
        sort=2,
        engine="bracket",
        rules_id="design-v0",
        object_name="STRATEGY_A",
        registry_id=None,
        gate_note=(
            "P3 gate failed out of sample (2022-01-03..2026-10-02): -15.0% vs SPY TR +71.9%, "
            "PF 0.92, max DD 33.3%"
        ),
    ),
    RosterRow(
        id=F4_ID,
        name="F4 · Momentum",
        sub="Top 20 by 12-1 momentum, monthly",
        icon="trending-up",
        is_champion=False,
        is_benchmark=False,
        sort=3,
        engine="book",
        rules_id="monthly-hold",
        object_name="FACTOR",
        registry_id=F4_ID,
        gate_note="P7a dev window only; failed max DD <= 15% (22.2%)",
        status="retired",
    ),
    RosterRow(
        id=F1_ID,
        name="F1 · Trend",
        sub="SPY above its 200-day average, monthly",
        icon="shield",
        is_champion=False,
        is_benchmark=False,
        sort=4,
        engine="book",
        rules_id="monthly-hold",
        object_name="TIMING",
        registry_id=F1_ID,
        gate_note="P7a dev window only; failed max DD <= 15% (18.7%) and >= 100 trades (11)",
        status="retired",
    ),
    RosterRow(
        id="C",
        name="C · News veto",
        sub="A's picks, LLM can veto on news",
        icon="gavel",
        is_champion=False,
        is_benchmark=False,
        sort=5,
        engine="bracket",
        rules_id="design-v0",
        object_name="STRATEGY_C",
        registry_id=None,
        gate_note="Backtest gate: not applicable (LLM strategy, design §1 item 5)",
        gate_applicable=False,
    ),
    RosterRow(
        id=FND_ID,
        name="FND · Fundamentals",
        sub="Top 20 by SEC filing factors, monthly",
        icon="book-open",
        is_champion=False,
        is_benchmark=False,
        sort=6,
        engine="book",
        rules_id="monthly-hold",
        object_name="FUNDAMENTAL",
        registry_id=None,
        gate_note=(
            "M0005 dev window only (1996-01-03..2015-10-16, fundamental coverage 0.3151); failed "
            "beats SPY TR (+1.8% vs +351.4%), >= 100 trades (15) and DSR >= 0.95 (0.006)"
        ),
        status="retired",
    ),
    # 010: the same three methods in fractional shares (Gotrade takes fractional limit orders).
    RosterRow(
        id=F4_FR_ID,
        name="F4 · Momentum",
        sub="Top 20 by last year's rise, monthly, fractional shares",
        icon="trending-up",
        is_champion=False,
        is_benchmark=False,
        sort=7,
        engine="book",
        rules_id="monthly-hold-frac",
        object_name="FACTOR",
        registry_id=F4_ID,
        gate_note=(
            "Same method as the whole-share F4: P7a dev window only; failed max DD <= 15% (22.2%). "
            "Backtested in whole shares; this version trades fractional shares"
        ),
    ),
    RosterRow(
        id=F1_FR_ID,
        name="F1 · Trend",
        sub="SPY above its 200-day average, monthly, fractional shares",
        icon="shield",
        is_champion=False,
        is_benchmark=False,
        sort=8,
        engine="book",
        rules_id="monthly-hold-frac",
        object_name="TIMING",
        registry_id=F1_ID,
        gate_note=(
            "Same method as the whole-share F1: P7a dev window only; failed max DD <= 15% (18.7%) "
            "and >= 100 trades (11). Backtested in whole shares; this version trades fractional shares"
        ),
    ),
    RosterRow(
        id=FND_FR_ID,
        name="FND · Fundamentals",
        sub="Top 20 by company filings, monthly, fractional shares",
        icon="book-open",
        is_champion=False,
        is_benchmark=False,
        sort=9,
        engine="book",
        rules_id="monthly-hold-frac",
        object_name="FUNDAMENTAL",
        registry_id=None,
        gate_note=(
            "Same method as the whole-share FND: M0005 dev window only; failed beats SPY TR "
            "(+1.8% vs +351.4%), >= 100 trades (15) and DSR >= 0.95 (0.006). Backtested in whole "
            "shares; this version trades fractional shares"
        ),
    ),
)

#: The seeded roster, sorted by ``sort``. Built through :func:`from_rows`, the SAME path a
#: database-read roster takes, so the pinned digests prove the data path and not just this tuple.
#: Callers that have not moved to ``store.read_roster_rows`` + :func:`from_rows` keep using it.
ROSTER: tuple[RosterEntry, ...] = from_rows(SEED_ROWS)

ROSTER_IDS: tuple[str, ...] = tuple(e.id for e in ROSTER)

MAX_LOOKBACK_BARS: int = max(e.lookback for e in ROSTER)


def active(entries: Sequence[RosterEntry] = ROSTER) -> tuple[RosterEntry, ...]:
    """``entries`` that are still trading, in order. A retired entry keeps every row it wrote."""
    return tuple(e for e in entries if e.status == "active")


def entry(strategy_id: str) -> RosterEntry:
    """The roster entry ``strategy_id``; ``KeyError`` when it is not on the roster."""
    for e in ROSTER:
        if e.id == strategy_id:
            return e
    raise KeyError(f"{strategy_id!r} is not on the paper roster {ROSTER_IDS}")


# --------------------------------------------------------------------------- the frozen spec (D4)


def _rule_value(value: object) -> str | None:
    """One ``TradeRules`` field as a plain string (``None`` stays ``None``)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, str, Decimal)):
        return str(value)
    raise TypeError(f"no spec text for a {type(value).__name__}: {value!r}")


def rules_dict(rules: TradeRules) -> dict[str, str | None]:
    """Every ``TradeRules`` field, in field order, as plain strings.

    A lever added after this roster's spec digests were pinned is left out while it holds its
    no-op value (``sim.rules.LEVERS_SINCE_PINS``), so a roster strategy that does not use the
    lever keeps the digest already written to its live ``strategies.params`` row. One that uses
    it needs a new roster id anyway (its own paper clock), and then digests differently.
    """
    return {
        f.name: _rule_value(getattr(rules, f.name))
        for f in fields(rules)
        if not is_pinned_default(f.name, getattr(rules, f.name))
    }


def spec(e: RosterEntry) -> dict[str, Any]:
    """The frozen spec of ``e`` (contract C2 ``params.spec``): JSON-ready, strings and nulls only."""
    if e.engine == "benchmark":
        params: dict[str, str] = {
            "symbol": BENCHMARK_ID,
            "entry": "open",
            "shares": "whole",
            "dividends": "reinvest",
            "cost_rate": str(COST_RATE),
        }
        object_id = None
    else:
        params = dict(e.params.as_dict())
        object_id = e.obj.id
    registry_digest = None
    if e.registry_id is not None:
        registry_digest = candidate_digest(next(c for c in REGISTRY if c.id == e.registry_id))
    return {
        "id": e.id,
        "engine": e.engine,
        "object": e.object_name,
        "object_id": object_id,
        "registry_id": e.registry_id,
        "registry_digest": registry_digest,
        "rules_id": e.rules_id,
        "rules": None if e.rules is None else rules_dict(e.rules),
        "params": params,
        "initial_idr": str(INITIAL_IDR),
    }


def spec_text(s: Mapping[str, Any]) -> str:
    """The canonical text of a spec: JSON with sorted keys, no whitespace, ASCII only."""
    return json.dumps(s, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def spec_digest(s: Mapping[str, Any]) -> str:
    """sha256 (hex) of ``spec_text(s)`` in UTF-8."""
    return hashlib.sha256(spec_text(s).encode("utf-8")).hexdigest()


def backtest_gate(e: RosterEntry) -> dict[str, Any]:
    """Contract C2 ``params.backtest_gate``: no roster entry has passed a backtest gate.

    An entry the gate does not apply to (C: design §1 item 5, handover D9) also says
    ``"applicable": False``; it still counts as not passed. The applicable entries' dict is
    exactly ``{"passed": False, "note": ...}``, as before C existed.
    """
    if not e.gate_applicable:
        return {"passed": False, "applicable": False, "note": e.gate_note}
    return {"passed": False, "note": e.gate_note}


def strategy_params(e: RosterEntry) -> dict[str, Any]:
    """The whole ``strategies.params`` jsonb for ``e`` (contract C2), as ``paper`` writes it."""
    s = spec(e)
    return {"spec": s, "digest": spec_digest(s), "backtest_gate": backtest_gate(e)}
