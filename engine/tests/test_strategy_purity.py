"""Strategy, backtest and paper core modules are pure (handover §6.8, plan invariant 2;
paper-trading-ship invariant 4).

Globs ``seer_engine/strategies/*.py``, ``seer_engine/backtest/*.py`` and
``seer_engine/paper/*.py`` (every module except the impure edges ``backtest/io.py`` and
``paper/store.py``), so modules added later are covered without editing this file.

- Importing them in a fresh interpreter loads no psycopg, requests or yfinance, and never
  seer_engine.bars (which imports psycopg).
- Their source never reads the clock, draws random numbers, logs, prints or opens files.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import seer_engine

FORBIDDEN_MODULES = ("psycopg", "requests", "yfinance", "seer_engine.bars")
FORBIDDEN_IMPORT_ROOTS = {"psycopg", "requests", "yfinance", "time", "random", "logging", "urllib", "socket"}
FORBIDDEN_ATTRS = {"now", "utcnow", "today", "fromtimestamp", "random"}  # "random" catches numpy.random
FORBIDDEN_CALLS = {"print", "open", "input"}
IMPURE = {("backtest", "io.py"), ("paper", "store.py")}

PKG = Path(seer_engine.__file__).resolve().parent


def _pure_sources() -> list[Path]:
    files = []
    for package in ("strategies", "backtest", "paper"):
        files += [p for p in sorted((PKG / package).glob("*.py")) if (package, p.name) not in IMPURE]
    return files


def _module_name(path: Path) -> str:
    parts = ["seer_engine", path.parent.name]
    if path.stem != "__init__":
        parts.append(path.stem)
    return ".".join(parts)


def _fresh_python(code: str) -> str:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PKG.parent) + os.pathsep + env.get("PYTHONPATH", "")
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        check=True,
        timeout=120,
    )
    return out.stdout.strip()


def test_the_glob_finds_the_strategy_modules():
    names = {_module_name(p) for p in _pure_sources()}
    assert {
        "seer_engine.strategies",
        "seer_engine.strategies.base",
        "seer_engine.strategies.indicators",
        "seer_engine.strategies.a",
        "seer_engine.backtest",
        "seer_engine.paper",
        "seer_engine.paper.roster",
    } <= names
    assert "seer_engine.backtest.io" not in names
    assert "seer_engine.paper.store" not in names


def test_pure_modules_load_no_db_or_network_module():
    modules = sorted(_module_name(p) for p in _pure_sources())
    code = (
        "import importlib, sys\n"
        f"for m in {modules!r}:\n"
        "    importlib.import_module(m)\n"
        f"bad = [m for m in {FORBIDDEN_MODULES!r} if m in sys.modules]\n"
        "print(','.join(bad))\n"
    )
    assert _fresh_python(code) == ""


def test_pure_sources_have_no_clock_randomness_or_io():
    problems: list[str] = []
    for path in _pure_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            where = f"{path.parent.name}/{path.name}:{getattr(node, 'lineno', '?')}"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in FORBIDDEN_IMPORT_ROOTS or alias.name == "seer_engine.bars":
                        problems.append(f"{where} import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root in FORBIDDEN_IMPORT_ROOTS or node.module == "seer_engine.bars":
                    problems.append(f"{where} from {node.module} import ...")
                if node.module == "seer_engine" and any(a.name == "bars" for a in node.names):
                    problems.append(f"{where} from seer_engine import bars")
            elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
                problems.append(f"{where} .{node.attr}")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                problems.append(f"{where} {node.func.id}()")
    assert problems == []
