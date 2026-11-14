"""Every lab signal file (``seer_engine/lab/signals/sNNNN_*.py``) gets these checks for free, as a
method file does in test_lab_methods.py:

- it is pure (no clock, randomness, network, files or printing): the same AST walk;
- its id is unique and matches its file number (``signal.discover`` refuses otherwise);
- it scores labkit's smoke market: pool symbols to numbers, the same answer twice;
- it does not look ahead: its score on a data date is unchanged when every bar dated after it is
  changed or deleted, and it equals the score through ``Signal.scores``' cut, so it reads no
  more bars than its lookback.

The negative tests at the bottom prove each check fails on the signal it exists to catch, so a
green run means something (acceptance criterion R1.1).
"""

from __future__ import annotations

import ast
import importlib
import math
import textwrap
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from labkit import MEMBER_STOCKS, smoke_market
from stratkit import mutate_from, truncate_before

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END
from seer_engine.lab.signal import MAX_LOOKBACK, Signal, discover, signals_package
from seer_engine.lab.tree_rank import month_ends

SIGNALS = discover()
TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / ".claude" / "skills" / "explore-and-experiment-new-method" / "signal_template.py"
)
PROBES = month_ends(date(2014, 12, 1), DEV_END)  # month-ends with 253+ smoke bars behind them
POOL = frozenset(MEMBER_STOCKS)

# test_lab_methods.py's lists, word for word: a signal is held to exactly what a method is.
FORBIDDEN_IMPORT_ROOTS = {"psycopg", "requests", "yfinance", "time", "random", "logging", "urllib",
                          "socket", "subprocess", "sqlite3", "os"}
FORBIDDEN_ATTRS = {"now", "utcnow", "today", "fromtimestamp", "random"}
FORBIDDEN_CALLS = {"print", "open", "input", "eval", "exec"}


def assert_pure(source: str, where: str) -> None:
    """AssertionError when ``source`` imports, reads or calls anything a signal may not."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = {a.name.split(".")[0] for a in node.names}
            assert not roots & FORBIDDEN_IMPORT_ROOTS, (where, roots)
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in FORBIDDEN_IMPORT_ROOTS, (where, node.module)
            assert node.module not in ("seer_engine.research", "seer_engine.lab.store"), (where, node.module)
        elif isinstance(node, ast.Attribute):
            assert node.attr not in FORBIDDEN_ATTRS, (where, node.attr)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in FORBIDDEN_CALLS, (where, node.func.id)


def _clean(scores) -> dict[str, float]:
    """Scores as plain floats, NaN (no opinion) left out, so two readings compare with ==."""
    out: dict[str, float] = {}
    for symbol, value in scores.items():
        v = float(value)
        if math.isfinite(v):
            out[str(symbol)] = v
    return out


def assert_no_lookahead(sig: Signal, market, pool, probes) -> int:
    """For each probe date d: the score read with full histories is unchanged when every bar dated
    after d is changed or deleted, and equals the score through ``Signal.scores``' cut. Returns how
    many probes scored at least one name.
    """
    nonempty = 0
    for d in probes:
        after = dates.next_session(d)
        direct = _clean(sig.score(market.history, market, pool, d))
        for name, cut in (("changed", mutate_from), ("deleted", truncate_before)):
            future = {s: cut(h, after) for s, h in market.history.items()}
            got = _clean(sig.score(future, replace(market, history=future), pool, d))
            assert got == direct, f"{sig.id} on {d}: look-ahead ({name} bars after the data date moved its score)"
        through_cut = _clean(sig.scores(market, pool, d))
        assert through_cut == direct, f"{sig.id} on {d}: reads more than its {sig.lookback}-bar lookback"
        nonempty += bool(direct)
    return nonempty


@pytest.fixture(scope="module")
def market():
    return smoke_market()


@pytest.mark.parametrize("sid", list(SIGNALS))
def test_signal_source_is_pure(sid):
    _, path = SIGNALS[sid]
    assert_pure(path.read_text(encoding="utf-8"), sid)


def test_the_seed_signals_are_registered():
    assert {"S0001", "S0002"} <= set(SIGNALS)


def test_signal_ids_are_unique_and_match_their_files():
    folder = Path(signals_package().__path__[0])
    files = sorted(p.name for p in folder.glob("s[0-9][0-9][0-9][0-9]_*.py"))
    assert len(files) == len(SIGNALS), (files, list(SIGNALS))
    for sid, (sig, path) in SIGNALS.items():
        assert sig.id == sid
        assert path.name.startswith(f"s{sid[1:]}_"), (sid, path.name)


@pytest.mark.parametrize("sid", list(SIGNALS))
def test_signal_scores_the_smoke_market(market, sid):
    sig, _ = SIGNALS[sid]
    nonempty = 0
    for d in PROBES:
        first = sig.scores(market, POOL, d)
        assert _clean(first) == _clean(sig.scores(market, POOL, d)), f"{sid} on {d}: not deterministic"
        for symbol, value in first.items():
            assert symbol in POOL, f"{sid} on {d}: scored {symbol!r}, which is not in the pool"
            assert not isinstance(value, bool) and isinstance(value, (int, float, np.integer, np.floating)), (
                f"{sid} on {d}: the score for {symbol} is a {type(value).__name__}"
            )
        nonempty += bool(_clean(first))
    assert nonempty > 0, f"{sid}: no probe scored any name, so the smoke run proved nothing"


@pytest.mark.parametrize("sid", list(SIGNALS))
def test_signal_does_not_look_ahead(market, sid):
    sig, _ = SIGNALS[sid]
    assert assert_no_lookahead(sig, market, POOL, PROBES) > 0


def test_the_signal_template_is_pure():
    assert TEMPLATE.is_file(), TEMPLATE
    assert_pure(TEMPLATE.read_text(encoding="utf-8"), TEMPLATE.name)


# ---- the checks catch what they exist to catch ---------------------------------------------


def _bad(sid: str, score, lookback: int) -> Signal:
    return Signal(
        id=sid, name="a broken signal", family="test-broken", source_kind="knowledge", source_ref="",
        hypothesis="exists to be caught", expected_failure="caught", lookback=lookback, score=score,
    )


def _peek(history, market, pool, data_date):
    """Scores each name on tomorrow's return: the look-ahead the check exists to catch."""
    out = {}
    for symbol in sorted(pool):
        h = history.get(symbol)
        i = None if h is None else h.index_of(data_date)
        if i is not None and i + 1 < len(h):
            out[symbol] = float(h.close[i + 1] / h.close[i] - 1.0)
    return out


def _long_reach(history, market, pool, data_date):
    """Declares five bars and reads sixty."""
    out = {}
    for symbol in sorted(pool):
        h = history.get(symbol)
        i = None if h is None else h.index_of(data_date)
        if i is not None and i >= 60:
            out[symbol] = float(h.close[i] / h.close[i - 60] - 1.0)
    return out


@pytest.mark.parametrize("source", [
    "import time\n",
    "import os.path\n",
    "from random import random\n",
    "import datetime\nx = datetime.date.today()\n",
    "print('hello')\n",
    "f = open('prices.csv')\n",
    "from seer_engine.lab.store import connect\n",
    "from seer_engine.research import load_store\n",
])
def test_the_purity_walk_catches_each_forbidden_reach(source):
    with pytest.raises(AssertionError):
        assert_pure(source, "bad")


def test_the_lookahead_check_catches_a_signal_that_reads_tomorrow(market):
    with pytest.raises(AssertionError, match="look-ahead"):
        assert_no_lookahead(_bad("S9101", _peek, 2), market, POOL, PROBES)


def test_the_lookahead_check_catches_a_signal_that_reads_past_its_lookback(market):
    with pytest.raises(AssertionError, match="lookback"):
        assert_no_lookahead(_bad("S9102", _long_reach, 5), market, POOL, PROBES)


_BODY = textwrap.dedent('''
    from seer_engine.lab.signal import Signal

    def score(history, market, pool, data_date):
        return {}

    SIGNAL = Signal(id="{sid}", name="n", family="test", source_kind="knowledge", source_ref="",
                    hypothesis="h", expected_failure="f", lookback=1, score=score)
''')


def _package(tmp_path, monkeypatch, name: str, files: dict[str, str]):
    pkg = tmp_path / name
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    for filename, sid in files.items():
        (pkg / filename).write_text(_BODY.replace("{sid}", sid), encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    return importlib.import_module(name)


def test_discover_refuses_two_files_with_one_id(tmp_path, monkeypatch):
    pkg = _package(tmp_path, monkeypatch, "dup_signal_pkg", {"s0001_one.py": "S0001", "s0001_two.py": "S0001"})
    with pytest.raises(ValueError, match="two signal files claim S0001"):
        discover(pkg)


def test_discover_refuses_a_file_number_that_disagrees_with_its_id(tmp_path, monkeypatch):
    pkg = _package(tmp_path, monkeypatch, "misnumbered_signal_pkg", {"s0003_x.py": "S0004"})
    with pytest.raises(ValueError, match="file number S0003"):
        discover(pkg)


@pytest.mark.parametrize("change,match", [
    ({"id": "M0001"}, "look like S0001"),
    ({"lookback": MAX_LOOKBACK + 1}, "lookback must be"),
    ({"lookback": 0}, "lookback must be"),
    ({"market_fields": ("bogus",)}, "market field"),
    ({"idea_id": "idea-7"}, "idea_id"),
    ({"source_kind": "paper", "source_ref": ""}, "needs a source_ref"),
    ({"seen_keys": ("nocolon",)}, "kind:value"),
])
def test_a_malformed_signal_declaration_is_refused(change, match):
    fields = dict(
        id="S9200", name="n", family="test", source_kind="knowledge", source_ref="",
        hypothesis="h", expected_failure="f", lookback=1, score=lambda h, m, p, d: {},
    )
    fields.update(change)
    with pytest.raises(ValueError, match=match):
        Signal(**fields)
