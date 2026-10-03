"""Strategy B's frozen model agrees with the newest committed P6a report and its artifact.

P6a (docs/handover/2026-10-03-strategy-b-ranker.md §3 "Deployed model" and "One round only"): the
walk-forward report decides, once, whether Strategy B may be deployed. ``b_report.render_markdown``
writes four machine-readable lines into ``docs/backtests/<data end>-strategy-b-walkforward.md``:

    p6a-gate: passed | failed
    gated-model: B | B-linear                 # B-linear only by the pre-registered determinism switch
    last-fold-model: {"kind": ..., "digest": ..., "train_end": ..., "rows": ..., "label_sum": ...}
    frozen-model: null | {"report": ..., "artifact": ..., "train_end": ..., "sha256": ...}

``b_report.parse_machine_line`` reads them back. These tests read the newest committed report and
assert whichever branch it took:

- passed: STRATEGY_B_FROZEN == the report's frozen-model line; it names this report, the artifact
  engine/data/models/<data end>-strategy-b.pkl and the last fold's training cut-off; the artifact's
  sha256 is the constant's; b_model.loads(artifact) has the last-fold-model's kind and digest; and
  the comment above STRATEGY_B_FROZEN in b.py names the report;
- failed: STRATEGY_B_FROZEN is None, the report's frozen-model is null, and no
  *-strategy-b.pkl artifact is committed under engine/data/models/.

So B can never be deployed without a passing report, and the deployed model can never drift from
the evidence without a new report and artifact being committed.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date
from pathlib import Path

import seer_engine.strategies.b as strategy_b
from seer_engine import config
from seer_engine.backtest.b_report import (
    FROZEN_KEY,
    GATE_KEY,
    GATED_KEY,
    LAST_FOLD_KEY,
    parse_machine_line,
)
from seer_engine.backtest.b_walkforward import B, B_LINEAR
from seer_engine.strategies import b_model
from seer_engine.strategies.b import FEATURE_NAMES, FrozenModel

BACKTESTS_DIR = config.REPO_ROOT / "docs" / "backtests"
MODELS_DIR = config.REPO_ROOT / "engine" / "data" / "models"
REPORT_SUFFIX = "-strategy-b-walkforward.md"
REPORT_GLOB = "*" + REPORT_SUFFIX
ARTIFACT_SUFFIX = "-strategy-b.pkl"
ARTIFACT_GLOB = "*" + ARTIFACT_SUFFIX
PASSED = "passed"
FAILED = "failed"
KIND_OF_GATED = {B: b_model.TREE, B_LINEAR: b_model.RIDGE}
LAST_FOLD_FIELDS = {"kind", "digest", "train_end", "rows", "label_sum"}
HEX64 = re.compile(r"[0-9a-f]{64}")
RERUN = "re-run `python -m seer_engine backtest_b` and commit its report, never edit either by hand"


def _latest_report() -> Path:
    reports = sorted(BACKTESTS_DIR.glob(REPORT_GLOB))
    assert reports, f"no committed P6a report matches {BACKTESTS_DIR / REPORT_GLOB}"
    return reports[-1]  # stems start with the ISO data-end date, so name order is date order


def _text(report: Path) -> str:
    return report.read_text(encoding="utf-8")


def _data_end(report: Path) -> date:
    return date.fromisoformat(report.name[: -len(REPORT_SUFFIX)])


def _repo_relative(path: Path) -> str:
    return path.relative_to(config.REPO_ROOT).as_posix()


def _artifact_relative(data_end: date) -> str:
    return _repo_relative(MODELS_DIR / f"{data_end.isoformat()}{ARTIFACT_SUFFIX}")


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


def _last_fold(report: Path, text: str) -> dict[str, object]:
    last = _json_line(text, LAST_FOLD_KEY)
    assert isinstance(last, dict), f"{report.name}: {LAST_FOLD_KEY} is not a JSON object: {last!r}"
    return last


def _frozen_dict(frozen: FrozenModel) -> dict[str, str]:
    return {
        "report": frozen.report,
        "artifact": frozen.artifact,
        "train_end": frozen.train_end.isoformat(),
        "sha256": frozen.sha256,
    }


def test_report_records_a_gate_outcome() -> None:
    report = _latest_report()
    assert _gate(_text(report)) in (PASSED, FAILED)


def test_gated_model_line_names_b_or_b_linear() -> None:
    report = _latest_report()
    gated = parse_machine_line(_text(report), GATED_KEY)
    assert gated in KIND_OF_GATED, (
        f"{report.name}: {GATED_KEY} must be {B!r} or {B_LINEAR!r} (the pre-registered switch), got {gated!r}"
    )


def test_last_fold_line_is_a_valid_model_record() -> None:
    report = _latest_report()
    text = _text(report)
    gated = parse_machine_line(text, GATED_KEY)
    last = _last_fold(report, text)
    assert set(last) == LAST_FOLD_FIELDS, (
        f"{report.name}: {LAST_FOLD_KEY} has fields {sorted(last)}, expected {sorted(LAST_FOLD_FIELDS)}"
    )
    assert last["kind"] == KIND_OF_GATED.get(gated), (
        f"{report.name}: {GATED_KEY} is {gated!r} but the last fold's model kind is {last['kind']!r}"
    )
    digest = last["digest"]
    assert isinstance(digest, str) and HEX64.fullmatch(digest), (
        f"{report.name}: {LAST_FOLD_KEY} digest {digest!r} is not a lowercase sha256 hex digest"
    )
    train_end = last["train_end"]
    assert isinstance(train_end, str), f"{report.name}: train_end {train_end!r} is not an ISO date string"
    assert date.fromisoformat(train_end) < _data_end(report), (
        f"{report.name}: the last fold trained through {train_end}, not before the data end {_data_end(report)}"
    )
    rows = last["rows"]
    assert isinstance(rows, int) and not isinstance(rows, bool) and rows > 0, (
        f"{report.name}: {LAST_FOLD_KEY} rows {rows!r} is not a positive int"
    )
    raw_sum = last["label_sum"]
    assert isinstance(raw_sum, str), (
        f"{report.name}: {LAST_FOLD_KEY} label_sum {raw_sum!r} must be a JSON string holding repr(float)"
    )
    label_sum = float(raw_sum)
    assert math.isfinite(label_sum) and repr(label_sum) == raw_sum, (
        f"{report.name}: {LAST_FOLD_KEY} label_sum {raw_sum!r} is not the repr of a finite float"
    )


def test_code_constant_equals_report_frozen_line() -> None:
    STRATEGY_B_FROZEN = strategy_b.STRATEGY_B_FROZEN  # read at call time, never a stale import copy
    report = _latest_report()
    frozen = _json_line(_text(report), FROZEN_KEY)
    if STRATEGY_B_FROZEN is None:
        assert frozen is None, f"STRATEGY_B_FROZEN is None but {report.name} {FROZEN_KEY} is {frozen}; {RERUN}"
        return
    expected = _frozen_dict(STRATEGY_B_FROZEN)
    assert isinstance(frozen, dict) and frozen == expected, (
        f"STRATEGY_B_FROZEN {expected} differs from {report.name} {FROZEN_KEY} {frozen}; {RERUN}"
    )


def test_freeze_follows_the_gate() -> None:
    STRATEGY_B_FROZEN = strategy_b.STRATEGY_B_FROZEN  # read at call time, never a stale import copy
    report = _latest_report()
    text = _text(report)
    if _gate(text) == FAILED:
        assert STRATEGY_B_FROZEN is None, (
            f"{report.name} says the P6a gate failed, so STRATEGY_B_FROZEN must stay None "
            f"(B's one round failed on this data); it is {STRATEGY_B_FROZEN!r}"
        )
        assert parse_machine_line(text, FROZEN_KEY) == "null", (
            f"{report.name}: a failed gate must record {FROZEN_KEY}: null"
        )
        return
    assert STRATEGY_B_FROZEN is not None, (
        f"{report.name} says the P6a gate passed; set STRATEGY_B_FROZEN in strategies/b.py to the "
        "artifact backtest_b wrote, then re-run backtest_b so the report records it"
    )
    last = _last_fold(report, text)
    assert STRATEGY_B_FROZEN.report == _repo_relative(report), (
        f"STRATEGY_B_FROZEN.report {STRATEGY_B_FROZEN.report!r} is not {_repo_relative(report)!r}"
    )
    assert STRATEGY_B_FROZEN.artifact == _artifact_relative(_data_end(report)), (
        f"STRATEGY_B_FROZEN.artifact {STRATEGY_B_FROZEN.artifact!r} is not "
        f"{_artifact_relative(_data_end(report))!r}"
    )
    assert isinstance(STRATEGY_B_FROZEN.train_end, date), (
        f"STRATEGY_B_FROZEN.train_end {STRATEGY_B_FROZEN.train_end!r} is not a date"
    )
    assert STRATEGY_B_FROZEN.train_end.isoformat() == last["train_end"], (
        f"STRATEGY_B_FROZEN.train_end {STRATEGY_B_FROZEN.train_end} is not the last fold's "
        f"training cut-off {last['train_end']} in {report.name}"
    )
    source = Path(strategy_b.__file__).read_text(encoding="utf-8")
    assert f"docs/backtests/{report.name}" in source, (
        f"the comment above STRATEGY_B_FROZEN in {Path(strategy_b.__file__).name} must name "
        f"docs/backtests/{report.name}"
    )


def test_artifact_follows_the_gate() -> None:
    STRATEGY_B_FROZEN = strategy_b.STRATEGY_B_FROZEN  # read at call time, never a stale import copy
    report = _latest_report()
    text = _text(report)
    artifacts = sorted(MODELS_DIR.glob(ARTIFACT_GLOB))
    if _gate(text) == FAILED:
        assert artifacts == [], (
            f"{report.name} says the P6a gate failed, so no Strategy B model may be committed; "
            f"found {[_repo_relative(p) for p in artifacts]}"
        )
        return
    assert STRATEGY_B_FROZEN is not None, f"{report.name} says the P6a gate passed but STRATEGY_B_FROZEN is None"
    path = config.REPO_ROOT / STRATEGY_B_FROZEN.artifact
    assert path.is_file(), f"the frozen artifact {STRATEGY_B_FROZEN.artifact} is not committed"
    assert artifacts and artifacts[-1] == path, (
        f"the newest artifact {[_repo_relative(p) for p in artifacts][-1:]} is not the frozen one "
        f"{STRATEGY_B_FROZEN.artifact}"
    )
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    assert actual == STRATEGY_B_FROZEN.sha256, (
        f"{STRATEGY_B_FROZEN.artifact} has sha256 {actual}, but STRATEGY_B_FROZEN.sha256 is "
        f"{STRATEGY_B_FROZEN.sha256}; never edit the artifact by hand"
    )
    model = b_model.loads(data)
    last = _last_fold(report, text)
    assert model.kind == last["kind"], (
        f"{STRATEGY_B_FROZEN.artifact} holds a {model.kind!r} model; {report.name} says {last['kind']!r}"
    )
    assert model.digest == last["digest"], (
        f"{STRATEGY_B_FROZEN.artifact} loads to digest {model.digest}, but {report.name}'s "
        f"{LAST_FOLD_KEY} digest is {last['digest']}"
    )
    assert model.n_features == len(FEATURE_NAMES), (
        f"{STRATEGY_B_FROZEN.artifact} expects {model.n_features} features, Strategy B has {len(FEATURE_NAMES)}"
    )
