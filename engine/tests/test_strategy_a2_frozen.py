"""Strategy A2's frozen parameters agree with the newest committed walk-forward report.

P3b (docs/handover/2026-10-03-strategy-a-rework.md §3 "Deployed parameters" and "One round only"):
the walk-forward report decides, once, whether Strategy A2 may be deployed. ``wf_report.render_markdown``
writes three machine-readable lines into ``docs/backtests/<data end>-strategy-a2-walkforward.md``:

    p3b-gate: passed | failed
    last-fold-params: {"variant": "...", "rsi_max": "...", ...}   # the last fold's combined selection
    frozen-params: null | {"variant": "...", ...}                 # STRATEGY_A2_PARAMS at run time

``wf_report.parse_machine_line`` reads them back. These tests read the newest committed report and
assert whichever branch it took:

- passed: STRATEGY_A2_PARAMS == the report's frozen-params == its last-fold-params, and the comment
  above STRATEGY_A2_PARAMS in a2.py names the report;
- failed: STRATEGY_A2_PARAMS is None and the report's frozen-params is null.

So A2 can never be deployed without a passing report, and the deployed values can never drift from
the evidence without a new report being committed.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import seer_engine.strategies.a2 as strategy_a2
from seer_engine import config
from seer_engine.backtest.wf_report import (
    FROZEN_KEY,
    GATE_KEY,
    LAST_FOLD_KEY,
    parse_machine_line,
)
from seer_engine.strategies.a2 import STRATEGY_A2_PARAMS, VARIANTS, A2Params

BACKTESTS_DIR = config.REPO_ROOT / "docs" / "backtests"
REPORT_GLOB = "*-strategy-a2-walkforward.md"
PASSED = "passed"
FAILED = "failed"


def _latest_report() -> Path:
    reports = sorted(BACKTESTS_DIR.glob(REPORT_GLOB))
    assert reports, f"no committed walk-forward report matches {BACKTESTS_DIR / REPORT_GLOB}"
    return reports[-1]  # stems start with the ISO data-end date, so name order is date order


def _text(report: Path) -> str:
    return report.read_text(encoding="utf-8")


def _gate(text: str) -> str:
    gate = parse_machine_line(text, GATE_KEY)
    assert gate in (PASSED, FAILED), f"{GATE_KEY}: expected {PASSED!r} or {FAILED!r}, got {gate!r}"
    return gate


def _json_line(text: str, key: str) -> object:
    raw = parse_machine_line(text, key)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise AssertionError(f"'{key}:' is not JSON: {raw!r}") from e


def _params_from_dict(d: dict[str, str]) -> A2Params:
    return A2Params(
        variant=d["variant"],
        rsi_max=float(d["rsi_max"]),
        limit_atr=Decimal(d["limit_atr"]),
        tp_atr=Decimal(d["tp_atr"]),
        sl_atr=Decimal(d["sl_atr"]),
        min_dollar_volume=float(d["min_dollar_volume"]),
    )


def test_report_records_a_gate_outcome() -> None:
    report = _latest_report()
    assert _gate(_text(report)) in (PASSED, FAILED)


def test_last_fold_line_is_a_valid_a2_selection() -> None:
    report = _latest_report()
    last = _json_line(_text(report), LAST_FOLD_KEY)
    assert isinstance(last, dict), f"{report.name}: {LAST_FOLD_KEY} is not a JSON object: {last!r}"
    assert last.get("variant") in VARIANTS, f"{report.name}: unknown variant in {last!r}"
    rebuilt = _params_from_dict(last)
    assert list(rebuilt.as_dict().items()) == list(last.items()), (
        f"{report.name}: {LAST_FOLD_KEY} {last} does not round-trip through A2Params"
    )


def test_code_params_equal_report_frozen_params() -> None:
    report = _latest_report()
    frozen = _json_line(_text(report), FROZEN_KEY)
    expected = None if STRATEGY_A2_PARAMS is None else STRATEGY_A2_PARAMS.as_dict()
    if expected is None:
        assert frozen is None, (
            f"STRATEGY_A2_PARAMS is None but {report.name} {FROZEN_KEY} is {frozen}; "
            "re-run `python -m seer_engine backtest_wf` and commit its report, never edit either by hand"
        )
    else:
        assert isinstance(frozen, dict) and list(frozen.items()) == list(expected.items()), (
            f"STRATEGY_A2_PARAMS {expected} differs from {report.name} {FROZEN_KEY} {frozen}; "
            "re-run `python -m seer_engine backtest_wf` and commit its report, never edit either by hand"
        )


def test_freeze_follows_the_gate() -> None:
    report = _latest_report()
    text = _text(report)
    gate = _gate(text)
    if gate == FAILED:
        assert STRATEGY_A2_PARAMS is None, (
            f"{report.name} says the P3b gate failed, so STRATEGY_A2_PARAMS must stay None "
            f"(Strategy A's one rework failed); it is {STRATEGY_A2_PARAMS!r}"
        )
        assert parse_machine_line(text, FROZEN_KEY) == "null", (
            f"{report.name}: a failed gate must record {FROZEN_KEY}: null"
        )
        return
    last = _json_line(text, LAST_FOLD_KEY)
    frozen = _json_line(text, FROZEN_KEY)
    assert STRATEGY_A2_PARAMS is not None, (
        f"{report.name} says the P3b gate passed; freeze its {LAST_FOLD_KEY} in "
        "strategies/a2.py STRATEGY_A2_PARAMS and re-run backtest_wf"
    )
    code = STRATEGY_A2_PARAMS.as_dict()
    assert isinstance(last, dict) and list(code.items()) == list(last.items()), (
        f"STRATEGY_A2_PARAMS {code} is not the last fold's selection {last} in {report.name}"
    )
    assert isinstance(frozen, dict) and list(frozen.items()) == list(last.items()), (
        f"{report.name}: {FROZEN_KEY} {frozen} is not its {LAST_FOLD_KEY} {last}; "
        "re-run backtest_wf after freezing so the report records the frozen values"
    )
    source = Path(strategy_a2.__file__).read_text(encoding="utf-8")
    assert f"docs/backtests/{report.name}" in source, (
        f"the comment above STRATEGY_A2_PARAMS in {Path(strategy_a2.__file__).name} must name "
        f"docs/backtests/{report.name}"
    )
