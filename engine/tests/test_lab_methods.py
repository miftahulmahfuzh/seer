"""Every lab method file (``seer_engine/lab/methods/mNNNN_*.py``) gets these checks for free
(method lab design §2):

- it is pure (no clock, randomness, network, files or printing), like the strategy modules;
- each of its allocators passes the ``allocatorkit`` contract: valid targets, the P4 identity
  and no look-ahead, on a synthetic market;
- each candidate runs a smoke window through ``dev.run_candidate``;
- allocator ids are unique across methods (a config digest names the allocator by id);
- a method that has run is frozen: its file's sha256 equals the ``source_sha`` the committed
  lab database recorded when it ran.
"""

from __future__ import annotations

import ast
import sqlite3
from datetime import date
from decimal import Decimal

import pytest
from allocatorkit import assert_no_lookahead, assert_p4_identity, everyone
from labkit import MEMBER_STOCKS, SPY_EX_DATE, smoke_market

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.dev import DEV_END, run_candidate
from seer_engine.backtest.registry import REGISTRY
from seer_engine.lab import store
from seer_engine.lab.method import discover, source_sha
from seer_engine.strategies.allocator import Allocator, MarketAware

METHODS = discover()
CANDIDATES = [(mid, c) for mid, (m, _) in METHODS.items() for c in m.candidates]

FORBIDDEN_IMPORT_ROOTS = {"psycopg", "requests", "yfinance", "time", "random", "logging", "urllib",
                          "socket", "subprocess", "sqlite3", "os"}
FORBIDDEN_ATTRS = {"now", "utcnow", "today", "fromtimestamp", "random"}
FORBIDDEN_CALLS = {"print", "open", "input", "eval", "exec"}


def _needed(c) -> set[str]:
    if not isinstance(c.allocator, Allocator):
        return set()
    out = set(c.allocator.symbols(c.params)) | set(c.allocator.holds(c.params))
    if c.rules.idle_symbol is not None:
        out.add(c.rules.idle_symbol)
    return out


@pytest.fixture(scope="module")
def market():
    extra: set[str] = set()
    for _, c in CANDIDATES:
        extra |= _needed(c)
    return smoke_market(extra)


@pytest.mark.parametrize("mid", list(METHODS))
def test_method_source_is_pure(mid):
    _, path = METHODS[mid]
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = {a.name.split(".")[0] for a in node.names}
            assert not roots & FORBIDDEN_IMPORT_ROOTS, (mid, roots)
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in FORBIDDEN_IMPORT_ROOTS, (mid, node.module)
            assert node.module not in ("seer_engine.research", "seer_engine.lab.store"), (mid, node.module)
        elif isinstance(node, ast.Attribute):
            assert node.attr not in FORBIDDEN_ATTRS, (mid, node.attr)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in FORBIDDEN_CALLS, (mid, node.func.id)


@pytest.mark.parametrize("mid,c", CANDIDATES, ids=[c.id for _, c in CANDIDATES])
def test_candidate_runs_a_smoke_window(market, mid, c):
    amount = Decimal("1.0300")
    result, row = run_candidate(market, {"SPY": {SPY_EX_DATE: amount}}, (Dividend(SPY_EX_DATE, amount),), c)
    assert row.end == DEV_END
    assert len(result.snapshots) >= 2


@pytest.mark.parametrize("mid,c", [x for x in CANDIDATES if isinstance(x[1].allocator, Allocator)],
                         ids=[c.id for _, c in CANDIDATES if isinstance(c.allocator, Allocator)])
def test_allocator_contract(market, mid, c):
    sessions = dates.sessions(date(2014, 12, 1), DEV_END)
    probe = sessions[::40]
    held_sets = [frozenset(), frozenset(MEMBER_STOCKS[:2]) & frozenset(market.history)]
    members = everyone({s: market.history[s] for s in MEMBER_STOCKS})
    nonempty = assert_p4_identity(c.allocator, market.history, members, [dates.prev_session(s) for s in probe],
                       held_sets, [c.params])
    nonempty += assert_no_lookahead(c.allocator, market.history, members, probe, held_sets, [c.params])
    if isinstance(c.allocator, MarketAware):
        # A market-aware allocator reads its panel through prepare_market(market); the kit only
        # drives prepare(history), so by contract it must target nothing here. The checks above
        # still prove the history-only path never crashes and never looks ahead; the live path
        # is covered by the allocator's own test module.
        assert nonempty == 0, f"{c.id}: a market-aware allocator must target nothing with no panel"
        return
    assert nonempty > 0, f"{c.id}: every probe returned no targets, so the contract check proved nothing"


def test_allocator_ids_are_unique_across_methods():
    owner: dict[str, object] = {}
    for c in REGISTRY:
        owner.setdefault(str(c.allocator.id), c.allocator)
    for mid, c in CANDIDATES:
        key = str(c.allocator.id)
        seen = owner.setdefault(key, c.allocator)
        assert seen is c.allocator, f"{c.id}: allocator id {key!r} is already used by another object"


def test_a_method_that_ran_is_frozen():
    # The committed database, not SEER_LAB_DB: in a sera worktree the shared database already
    # holds sibling methods whose files this tree does not have yet.
    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        ran = conn.execute("SELECT id, source_sha FROM methods WHERE id GLOB 'M*' AND source_sha IS NOT NULL").fetchall()
    finally:
        conn.close()
    for row in ran:
        assert row["id"] in METHODS, f"{row['id']} ran but its method file is gone"
        _, path = METHODS[row["id"]]
        assert source_sha(path) == row["source_sha"], (
            f"{row['id']} changed after it ran; a method file is frozen once it has trials "
            "(a change is a new variation method)"
        )
