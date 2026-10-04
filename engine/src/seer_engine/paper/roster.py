"""The frozen paper roster (handover D1, D2, D4; plan contract C2).

Pure: no database, no clock, no I/O. Five portfolios paper-trade every night, each on its own
paper clock; this module is the single place that says what each one is.

- ``SPY``: buy-and-hold SPY with dividends reinvested (``backtest.benchmark.buy_and_hold``
  rules), the champion and the yardstick (D2).
- ``A``: Strategy A with ``STRATEGY_A_PARAMS`` under ``DESIGN_V0`` (the bracket engine).
- ``F4-MOM12-N20-TREND`` and ``F1-SPY-SMA200-M``: the P7a registry entries of those ids,
  taken from ``backtest.registry.REGISTRY`` as they are (the registry is read, never edited),
  under their own ``MONTHLY_HOLD`` rules (the book engine).
- ``C``: Strategy C (``strategies.c.STRATEGY_C`` with ``STRATEGY_C_PARAMS``) under
  ``DESIGN_V0``: A's ranked candidates minus every symbol the stored news check did not
  allow (strategy-c-news-veto handover D1, D5). The roster object carries no verdicts, so
  it never buys on its own; ``paper`` and ``paper_check`` hand the engine a copy carrying
  the stored verdicts.

Each entry's display fields (``name`` .. ``sort``, ``engine``, ``rules_id``) equal the row that
``db/migrations/003_paper.sql`` (``C``: ``004_news_veto.sql``) inserts;
``tests/test_paper_roster.py`` checks that against a migrated database.

**The frozen spec (D4).** :func:`spec` is the entry's trial-defining parts as a JSON-ready
dict of strings: engine, the strategy/allocator object (module-level name and its ``id``),
the registry id and the registry's own ``candidate_digest`` (book entries), every
``TradeRules`` field, every parameter (``as_dict``), and the starting capital in IDR.
:func:`spec_text` is its canonical text (sorted keys, no whitespace, ASCII) and
:func:`spec_digest` the sha256 hex of that text. Both take a plain mapping, so a spec read
back from ``strategies.params->'spec'`` recomputes to the same digest. The digests are
pinned in ``tests/test_paper_roster.py``: a changed strategy needs a **new id** with its own
paper clock, never an edited entry (``paper`` refuses a started id whose stored digest
differs).

``backtest_gate`` is a display fact for the go-live checklist (D12), not part of the spec:
correcting its note does not reset a paper clock. Every entry is ``passed: false`` today.
An entry with ``gate_applicable=False`` (C, an LLM strategy: design §1 item 5, handover D9)
also says ``applicable: false``; the four quant/benchmark entries' gate dicts are unchanged.

:data:`MAX_LOOKBACK_BARS` is the most bars through a data date any roster object reads
(FACTOR's ``factor_lookback`` = 253); the paper store's windowed history load must cover it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, fields
from decimal import Decimal
from typing import Any, Literal

from seer_engine.backtest.registry import REGISTRY, candidate_digest
from seer_engine.backtest.runner import INITIAL_IDR
from seer_engine.sim import COST_RATE
from seer_engine.sim.rules import DESIGN_V0, MONTHLY_HOLD, TradeRules
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS
from seer_engine.strategies.allocator import Allocator
from seer_engine.strategies.base import Strategy
from seer_engine.strategies.c import STRATEGY_C, STRATEGY_C_PARAMS
from seer_engine.strategies.f_factor import FACTOR
from seer_engine.strategies.f_index import TIMING

Engine = Literal["bracket", "book", "benchmark"]

BENCHMARK_ID = "SPY"
F4_ID = "F4-MOM12-N20-TREND"
F1_ID = "F1-SPY-SMA200-M"


@dataclass(frozen=True, slots=True)
class RosterEntry:
    """One paper portfolio.

    ``obj`` is the ``Strategy`` (bracket), the ``Allocator`` (book) or ``None`` (benchmark);
    ``object_name`` is its module-level name (``STRATEGY_A``, ``FACTOR``, ``TIMING``) or
    ``buy_and_hold`` for the benchmark. ``rules`` is ``None`` only for the benchmark.
    ``lookback`` is the bars through a data date ``obj`` reads (1 for the benchmark, which
    reads only the session's own bar). ``gate_applicable`` is ``False`` only for an entry the
    quant backtest gate does not apply to (C); it changes ``backtest_gate``, never the spec.
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

    @property
    def rules_id(self) -> str | None:
        """``strategies.rules_id``: the rules preset id, ``None`` for the benchmark."""
        return None if self.rules is None else self.rules.id


def _registered(registry_id: str, expected_obj: Allocator, rules: TradeRules) -> tuple[Allocator, Any]:
    """(allocator, params) of the registry entry ``registry_id``, checked against what the
    roster expects (the registry is a closed record; a mismatch is a programming error)."""
    found = [c for c in REGISTRY if c.id == registry_id]
    if len(found) != 1:
        raise LookupError(f"registry has {len(found)} entries with id {registry_id!r}, expected 1")
    c = found[0]
    if c.allocator is not expected_obj:
        raise LookupError(f"{registry_id}: registry allocator is <{c.allocator.id}>, expected <{expected_obj.id}>")
    if c.rules != rules:
        raise LookupError(f"{registry_id}: registry rules are {c.rules.id!r}, expected {rules.id!r}")
    return c.allocator, c.params


_F4_OBJ, _F4_PARAMS = _registered(F4_ID, FACTOR, MONTHLY_HOLD)
_F1_OBJ, _F1_PARAMS = _registered(F1_ID, TIMING, MONTHLY_HOLD)

# Sorted by ``sort``; every value is the 003 (C: 004) migration's INSERT row for the same id.
ROSTER: tuple[RosterEntry, ...] = (
    RosterEntry(
        id=BENCHMARK_ID,
        name="SPY",
        sub="S&P 500, buy and hold",
        icon="landmark",
        is_champion=True,
        is_benchmark=True,
        sort=1,
        engine="benchmark",
        rules=None,
        obj=None,
        object_name="buy_and_hold",
        params=None,
        registry_id=None,
        lookback=1,
        gate_note="Benchmark, not a strategy: it has no backtest gate and is never a Seer pick",
    ),
    RosterEntry(
        id="A",
        name="A · Quant",
        sub="Mean reversion, 5-day brackets",
        icon="sigma",
        is_champion=False,
        is_benchmark=False,
        sort=2,
        engine="bracket",
        rules=DESIGN_V0,
        obj=STRATEGY_A,
        object_name="STRATEGY_A",
        params=STRATEGY_A_PARAMS,
        registry_id=None,
        lookback=STRATEGY_A.lookback,
        gate_note=(
            "P3 gate failed out of sample (2022-01-03..2026-10-02): -15.0% vs SPY TR +71.9%, "
            "PF 0.92, max DD 33.3%"
        ),
    ),
    RosterEntry(
        id=F4_ID,
        name="F4 · Momentum",
        sub="Top 20 by 12-1 momentum, monthly",
        icon="trending-up",
        is_champion=False,
        is_benchmark=False,
        sort=3,
        engine="book",
        rules=MONTHLY_HOLD,
        obj=_F4_OBJ,
        object_name="FACTOR",
        params=_F4_PARAMS,
        registry_id=F4_ID,
        lookback=_F4_OBJ.lookback(_F4_PARAMS),
        gate_note="P7a dev window only; failed max DD <= 15% (22.2%)",
    ),
    RosterEntry(
        id=F1_ID,
        name="F1 · Trend",
        sub="SPY above its 200-day average, monthly",
        icon="shield",
        is_champion=False,
        is_benchmark=False,
        sort=4,
        engine="book",
        rules=MONTHLY_HOLD,
        obj=_F1_OBJ,
        object_name="TIMING",
        params=_F1_PARAMS,
        registry_id=F1_ID,
        lookback=_F1_OBJ.lookback(_F1_PARAMS),
        gate_note="P7a dev window only; failed max DD <= 15% (18.7%) and >= 100 trades (11)",
    ),
    RosterEntry(
        id="C",
        name="C · News veto",
        sub="A's picks, LLM can veto on news",
        icon="gavel",
        is_champion=False,
        is_benchmark=False,
        sort=5,
        engine="bracket",
        rules=DESIGN_V0,
        obj=STRATEGY_C,
        object_name="STRATEGY_C",
        params=STRATEGY_C_PARAMS,
        registry_id=None,
        lookback=STRATEGY_C.lookback,
        gate_note="Backtest gate: not applicable (LLM strategy, design §1 item 5)",
        gate_applicable=False,
    ),
)

ROSTER_IDS: tuple[str, ...] = tuple(e.id for e in ROSTER)

MAX_LOOKBACK_BARS: int = max(e.lookback for e in ROSTER)


def entry(strategy_id: str) -> RosterEntry:
    """The roster entry ``strategy_id``; ``KeyError`` when it is not on the roster."""
    for e in ROSTER:
        if e.id == strategy_id:
            return e
    raise KeyError(f"{strategy_id!r} is not on the paper roster {ROSTER_IDS}")


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
    """Every ``TradeRules`` field, in field order, as plain strings."""
    return {f.name: _rule_value(getattr(rules, f.name)) for f in fields(rules)}


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
