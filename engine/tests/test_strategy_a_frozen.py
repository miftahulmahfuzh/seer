"""The parameters frozen in code are the ones the committed backtest report selected.

P3 (handover §3 "Frozen parameters"): Strategy A's parameters are tuned on the in-sample window
only, then frozen in ``seer_engine.strategies.a.STRATEGY_A_PARAMS`` with a comment naming the report
that froze them. ``report.render_markdown`` writes two machine-readable lines into that report:

    frozen-params: {"rsi_max": "...", ...}     # STRATEGY_A_PARAMS.as_dict() at run time
    selected-params: {"rsi_max": "...", ...}   # the in-sample selection's as_dict()

``report.parse_params_line`` reads them back. These tests read the newest committed
``docs/backtests/*-strategy-a.md`` and fail when the code, the report's frozen line and the
report's selection disagree, so the frozen strategy can never drift from the evidence without a
new report being committed.
"""

from __future__ import annotations

from pathlib import Path

import seer_engine.strategies.a as strategy_a
from seer_engine import config
from seer_engine.backtest.report import FROZEN_KEY, SELECTED_KEY, parse_params_line
from seer_engine.strategies.a import STRATEGY_A_PARAMS

BACKTESTS_DIR = config.REPO_ROOT / "docs" / "backtests"
REPORT_GLOB = "*-strategy-a.md"


def _latest_report() -> Path:
    reports = sorted(BACKTESTS_DIR.glob(REPORT_GLOB))
    assert reports, f"no committed Strategy A report matches {BACKTESTS_DIR / REPORT_GLOB}"
    return reports[-1]  # stems start with the ISO data-end date, so name order is date order


def test_code_params_equal_report_frozen_params() -> None:
    report = _latest_report()
    frozen = parse_params_line(report.read_text(encoding="utf-8"), FROZEN_KEY)
    expected = STRATEGY_A_PARAMS.as_dict()
    assert list(frozen.items()) == list(expected.items()), (
        f"STRATEGY_A_PARAMS {expected} differs from {report.name} {FROZEN_KEY} {frozen}; "
        "re-run `python -m seer_engine backtest` and commit its report, never edit either by hand"
    )


def test_report_froze_its_own_selection() -> None:
    report = _latest_report()
    text = report.read_text(encoding="utf-8")
    frozen = parse_params_line(text, FROZEN_KEY)
    selected = parse_params_line(text, SELECTED_KEY)
    assert list(frozen.items()) == list(selected.items()), (
        f"{report.name}: {FROZEN_KEY} {frozen} is not the in-sample selection {selected}; "
        "set STRATEGY_A_PARAMS to the selection and re-run the backtest"
    )


def test_frozen_params_comment_names_the_report() -> None:
    report = _latest_report()
    source = Path(strategy_a.__file__).read_text(encoding="utf-8")
    assert f"docs/backtests/{report.name}" in source, (
        f"the comment above STRATEGY_A_PARAMS in {Path(strategy_a.__file__).name} must name "
        f"docs/backtests/{report.name}"
    )
