"""The sim core is pure (fill-simulator handover §6.2 and §6.4).

- Importing it in a fresh interpreter loads no psycopg, requests or yfinance, and never
  seer_engine.bars (which imports psycopg).
- Its source never reads the clock, draws random numbers, logs, prints or opens files.
- seer_engine.bars re-exports the moved price types as the very same objects.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import seer_engine
import seer_engine.sim

FORBIDDEN_MODULES = ("psycopg", "requests", "yfinance", "seer_engine.bars")
FORBIDDEN_IMPORT_ROOTS = {"psycopg", "requests", "yfinance", "time", "random", "logging", "urllib", "socket"}
FORBIDDEN_ATTRS = {"now", "utcnow", "today", "fromtimestamp"}
FORBIDDEN_CALLS = {"print", "open", "input"}


def _fresh_python(code: str) -> str:
    src = str(Path(seer_engine.__file__).resolve().parents[1])
    env = dict(os.environ)
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        check=True,
        timeout=120,
    )
    return out.stdout.strip()


def test_sim_import_loads_no_db_or_network_module():
    code = (
        "import sys\n"
        "import seer_engine.sim\n"
        "import seer_engine.prices\n"
        f"bad = [m for m in {FORBIDDEN_MODULES!r} if m in sys.modules]\n"
        "print(','.join(bad))\n"
    )
    assert _fresh_python(code) == ""


def test_fresh_python_does_see_a_bars_import():
    # Guards the test above against a check that can never fail.
    code = "import sys\nimport seer_engine.bars\nprint('psycopg' in sys.modules)\n"
    assert _fresh_python(code) == "True"


def _sim_sources() -> list[Path]:
    files = sorted(Path(seer_engine.sim.__file__).resolve().parent.glob("*.py"))
    assert files, "no sim sources found"
    return files


def test_sim_sources_have_no_clock_randomness_or_io():
    problems: list[str] = []
    for path in _sim_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            where = f"{path.name}:{getattr(node, 'lineno', '?')}"
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


def test_bars_reexports_the_same_objects_as_prices():
    from seer_engine import bars, prices

    assert bars.Bar is prices.Bar
    assert bars.to_decimal is prices.to_decimal
    assert bars.PRICE_QUANTUM is prices.PRICE_QUANTUM
    b = bars.make_bar("SPY", date(2026, 10, 2), "1", "2", "0.5", "1.5", 10)
    assert isinstance(b, prices.Bar)
