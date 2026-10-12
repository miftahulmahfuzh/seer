"""Every lab method file (``seer_engine/lab/methods/mNNNN_*.py``) gets these checks for free
(method lab design §2):

- it is pure (no clock, randomness, network, files or printing), like the strategy modules;
- each of its allocators passes the ``allocatorkit`` contract: valid targets, the P4 identity
  and no look-ahead, on a synthetic market;
- each candidate runs a smoke window through ``dev.run_candidate``;
- allocator ids are unique across methods (a config digest names the allocator by id);
- a method that has run is frozen against the sha the lab last ran it under: its file's sha256
  equals ``store.latest_source_sha`` (the newest ``method_amendments`` row, else the
  ``methods.source_sha`` recorded when it first ran), **and** every configuration the committed
  lab has a trial for still digests to the ``config_digest`` that trial recorded. The two together
  replaced the old whole-file freeze when amendments arrived (``method.Amendment``).
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
from seer_engine.lab import runner, store
from seer_engine.lab.method import config_digest, discover, source_sha
from seer_engine.strategies.allocator import Allocator, MarketAware

METHODS = discover()
CANDIDATES = [(mid, c) for mid, (m, _) in METHODS.items() for c in m.all_candidates()]

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


def _committed_lab():
    """A read-only connection to the committed lab, or None when this tree has no database.

    The committed database, not ``SEER_LAB_DB``: in a sera worktree the shared database already
    holds sibling methods whose files this tree does not have yet. Raw ``sqlite3`` rather than
    ``store.connect``, because connecting migrates -- and a test must never rewrite the committed
    file (``store.connect_readonly`` would do, but this predates it and the explicit URI says what
    it does).
    """
    if not store.COMMITTED_DB.exists():
        return None
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha():
    """Half one of the freeze: the file on disk is the file the lab last ran, or the one it is
    about to run next.

    Not ``methods.source_sha`` directly but ``store.latest_source_sha``, which is that column
    until the method gains an amendment and the newest ``method_amendments`` row afterwards. The
    column is still written once and never rewritten, so for a method with no amendment -- which
    is every method recorded before 2026-10-12 -- this asserts exactly what it asserted before.

    **The pre-registration window, and why it is tolerated.** An amendment is pre-registered by
    the commit that writes it and recorded only by the ``lab run --amend`` that executes it, so
    between those two moments the file legitimately hashes to something no row holds. That window
    is the mechanism, not a hole in it: the commit has to land first, because the commit *is* the
    pre-registration. So a sha mismatch is accepted on exactly one condition --
    ``runner.pending_amendment`` resolves, which means the file declares an ``Amendment`` the lab
    has not recorded **and** every amendment it *has* recorded still matches the block it was
    written from, field for field. Any other mismatch is the old failure, unchanged.

    What is never tolerated is the thing the freeze exists to protect, and it is checked
    separately and unconditionally by
    ``test_every_recorded_configuration_still_digests_to_its_recorded_digest``: a recorded trial's
    configuration may not move, amendment or no amendment. That test has no window.
    """
    conn = _committed_lab()
    if conn is None:
        pytest.skip("no lab database")
    try:
        ran = conn.execute(
            "SELECT id FROM methods WHERE id GLOB 'M*' AND source_sha IS NOT NULL"
        ).fetchall()
        for row in ran:
            mid = str(row["id"])
            assert mid in METHODS, f"{mid} ran but its method file is gone"
            method, path = METHODS[mid]
            expected = store.latest_source_sha(conn, mid)
            actual = source_sha(path)
            if actual == expected:
                continue
            try:
                runner.pending_amendment(conn, method)
            except store.LabError as e:
                raise AssertionError(
                    f"{mid} changed after the lab last ran it (file {actual[:12]}, recorded "
                    f"{str(expected)[:12]}) and it has no committed, unrecorded Amendment to "
                    f"explain the difference: {e}. A method file is frozen against its latest "
                    "recorded sha: a further question about the same idea is an Amendment "
                    "(committed first, run with `lab run --amend`), a different idea is a new "
                    "variation method"
                ) from e
    finally:
        conn.close()


def test_every_recorded_configuration_still_digests_to_its_recorded_digest():
    """Half two of the freeze, and the one an amendment cannot loosen.

    ``config_digest`` canonicalizes ``TradeRules`` and allocator params defined in *other* files,
    so a method file's own sha does not pin what its candidates do. This is the check that does,
    and it is also the proof of plan invariant 3: ``Method`` gained an ``amendments`` field, and
    ``registry._canon`` renders a dataclass by enumerating every ``compare=True`` field -- but
    ``config_text`` never passes a ``Method`` to ``_canon``, only ``c.rules``, ``c.allocator.id``
    and ``c.params``. Measured on the committed lab 2026-10-12, before the field existed: 63
    method files, 0 digests drifted. This test keeps that at 0.
    """
    conn = _committed_lab()
    if conn is None:
        pytest.skip("no lab database")
    try:
        drifted: list[str] = []
        for row in conn.execute(
            "SELECT id FROM methods WHERE id GLOB 'M*' AND source_sha IS NOT NULL"
        ).fetchall():
            mid = str(row["id"])
            method, _ = METHODS[mid]
            have = {config_digest(c) for c in method.all_candidates()}
            for t in conn.execute(
                "SELECT candidate_id, config_digest FROM trials WHERE method_id = ?", (mid,)
            ):
                if str(t["config_digest"]) not in have:
                    drifted.append(f"{mid}/{t['candidate_id']}")
        assert drifted == [], (
            f"{', '.join(drifted)}: a recorded trial's configuration is no longer one the method "
            "file produces. Its rules, allocator or params changed after it ran, which rewrites "
            "history the lab has already published"
        )
    finally:
        conn.close()
