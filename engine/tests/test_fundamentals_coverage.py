"""The dev-window coverage measure (``fundamentals/coverage.py``) and the bug it exists to prevent.

No store, no database, no network, no clock: every panel here is built from a handful of
synthetic ``us-gaap:Assets`` facts.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

import seer_engine
from seer_engine.fundamentals import EMPTY_PANEL, Fact, FundamentalPanel, coverage


def fact(symbol: str, filed: date, *, val: float = 1.0e9) -> Fact:
    """One ``us-gaap:Assets`` instant for ``symbol``, filed on (and dated) ``filed``."""
    return Fact(
        symbol=symbol,
        taxonomy="us-gaap",
        tag="Assets",
        unit="USD",
        period_start=None,
        period_end=filed,
        val=val,
        accn=f"0000000000-{filed.year % 100:02d}-{filed.toordinal():06d}",
        form="10-K",
        fy=filed.year,
        fp="FY",
        filed=filed,
    )


def panel_of(symbols, filings) -> FundamentalPanel:
    """A panel in which every symbol filed on every date in ``filings``."""
    return FundamentalPanel.from_facts([fact(s, d) for s in symbols for d in filings])


def names(n: int) -> list[str]:
    return [f"S{i:02d}" for i in range(n)]


ANNUAL = [date(1995, 1, 2) + timedelta(days=365 * k) for k in range(22)]
"""A filing roughly every year from 1995 to 2015: never more than 365 days apart, so a 400-day
staleness window is satisfied on every monthly sample of the dev window."""


# ---- the bug this module exists to prevent -------------------------------------------------


def test_a_snapshot_is_not_coverage():
    """Invariant 9: ``as_of(...) is not None`` is vacuous, and that is what spent M0005."""
    t = date(1996, 1, 2)
    panel = panel_of(names(30), [date(2015, 1, 5)])
    # The M0005 check, in one line. All thirty pass it, in 1996, against 2015 filings.
    assert all(panel.as_of(s, t) is not None for s in panel.names())
    # The honest test. All thirty fail it.
    assert all(panel.as_of(s, t).observations == {} for s in panel.names())
    assert coverage.rankable_symbols(panel, t) == ()
    assert coverage.rankable_count(panel, t) == 0


def test_an_empty_husk_is_not_rankable():
    t = date(1996, 1, 2)
    panel = panel_of(["AAA"], [date(2015, 1, 5)])
    assert coverage.is_rankable(panel.as_of("AAA", t), t, 400) is False
    assert coverage.is_rankable(None, t, 400) is False


# ---- the staleness gate ---------------------------------------------------------------------


def test_rankable_needs_a_filing_inside_the_staleness_window():
    t = date(2015, 6, 1)
    stale = coverage.default_max_stale_days()
    panel = FundamentalPanel.from_facts(
        [
            fact("FRESH", t - timedelta(days=stale)),
            fact("STALE", t - timedelta(days=stale + 1)),
            fact("FUTURE", t + timedelta(days=1)),
        ]
    )
    assert coverage.rankable_symbols(panel, t) == ("FRESH",)
    assert coverage.rankable_symbols(panel, t, max_stale_days=stale + 1) == ("FRESH", "STALE")


def test_the_staleness_window_is_f_fundamentals_own():
    from seer_engine.strategies.f_fundamental import FundamentalParams

    assert coverage.default_max_stale_days() == FundamentalParams(rank="value").max_stale_days


# ---- the window and the sample --------------------------------------------------------------


def test_the_sampled_window_is_the_dev_window():
    """``WINDOW_START``/``WINDOW_END`` are duplicated constants; this is what pins them."""
    from seer_engine import research
    from seer_engine.backtest import dev

    assert coverage.WINDOW_START == dev.MEMBERSHIP_START == research.MEMBERSHIP_START
    assert coverage.WINDOW_END == dev.DEV_END == research.DEV_END


def test_the_monthly_sample_is_one_date_per_calendar_month():
    sample = coverage.monthly_dates()
    assert len(sample) == 238
    assert sample[0] == date(1996, 1, 2)
    assert sample[-1] == date(2015, 10, 2)
    assert len({(d.year, d.month) for d in sample}) == len(sample)
    assert all(coverage.WINDOW_START <= d <= coverage.WINDOW_END for d in sample)


def test_a_short_month_contributes_its_last_day():
    assert coverage.monthly_dates(date(2015, 1, 31), date(2015, 4, 30)) == (
        date(2015, 1, 31),
        date(2015, 2, 28),
        date(2015, 3, 31),
        date(2015, 4, 30),
    )


def test_monthly_dates_refuses_a_backwards_window():
    with pytest.raises(coverage.CoverageError, match="before start"):
        coverage.monthly_dates(date(2015, 2, 1), date(2015, 1, 1))


# ---- the measure ----------------------------------------------------------------------------


def test_a_panel_whose_facts_all_postdate_the_window_covers_nothing():
    panel = panel_of(names(50), [date(2015, 11, 2)])
    cov = coverage.measure(panel)
    assert cov.symbols == 50
    assert cov.counts == (0,) * len(cov.dates)
    assert cov.covered_dates == 0
    assert cov.fraction == 0.0
    assert [r.most_rankable for r in cov.by_year()] == [0] * 20


def test_a_panel_filed_through_the_window_covers_all_of_it():
    panel = panel_of(names(25), ANNUAL)
    cov = coverage.measure(panel)
    assert min(cov.counts) == 25
    assert cov.covered_dates == len(cov.dates)
    assert cov.fraction == 1.0
    assert cov.start == date(1996, 1, 2) and cov.end == date(2015, 10, 2)


def test_covered_means_at_least_top_rankable():
    panel = panel_of(names(19), ANNUAL)
    assert coverage.measure(panel).fraction == 0.0  # 19 < DEFAULT_TOP
    assert coverage.measure(panel, top=19).fraction == 1.0


def test_an_empty_panel_measures_zero_and_does_not_raise():
    cov = coverage.measure(EMPTY_PANEL)
    assert cov.symbols == 0
    assert cov.fraction == 0.0
    assert len(cov.dates) == 238


def test_the_per_year_table_locates_the_coverage():
    panel = panel_of(names(50), [date(2015, 3, 2)])
    cov = coverage.measure(panel)
    rows = cov.by_year()
    assert [r.year for r in rows] == list(range(1996, 2016))
    assert all(r.sampled == 12 for r in rows if r.year < 2015)
    assert all(r.covered == 0 and r.most_rankable == 0 for r in rows if r.year < 2015)
    last = rows[-1]
    assert (last.year, last.sampled, last.covered, last.most_rankable) == (2015, 10, 8, 50)
    assert cov.covered_dates == 8


def test_an_explicit_sample_overrides_the_monthly_one():
    panel = panel_of(names(25), [date(2015, 3, 2)])
    cov = coverage.measure(panel, dates=(date(2015, 1, 2), date(2015, 4, 2)))
    assert cov.counts == (0, 25)
    assert cov.fraction == 0.5


def test_measure_refuses_what_it_cannot_measure():
    with pytest.raises(coverage.CoverageError, match="FundamentalPanel"):
        coverage.measure(object())
    with pytest.raises(coverage.CoverageError, match="top"):
        coverage.measure(EMPTY_PANEL, top=0)
    with pytest.raises(coverage.CoverageError, match="at least one sampled date"):
        coverage.measure(EMPTY_PANEL, dates=())
    with pytest.raises(coverage.CoverageError, match="dates\\[1\\]"):
        coverage.measure(EMPTY_PANEL, dates=(date(2015, 1, 2), "2015-02-02"))
    with pytest.raises(coverage.CoverageError, match="t must be a date"):
        coverage.rankable_symbols(EMPTY_PANEL, "2015-01-02")


# ---- the report ------------------------------------------------------------------------------


def test_the_report_names_the_number_and_the_floor():
    cov = coverage.measure(panel_of(names(50), [date(2015, 3, 2)]))
    text = coverage.format_report(cov)
    assert "BELOW" in text
    assert "0.80" in text
    assert f"{cov.fraction:.4f}" in text
    assert "upper bound" in text
    for year in (1996, 2005, 2015):
        assert f"  {year}  " in text


def test_a_covered_panel_reports_no_refusal():
    cov = coverage.measure(panel_of(names(25), ANNUAL))
    text = coverage.format_report(cov)
    assert "BELOW" not in text
    assert "at or above" in text


def test_a_lowered_floor_changes_only_the_verdict():
    cov = coverage.measure(panel_of(names(50), [date(2015, 3, 2)]))
    assert "BELOW" not in coverage.format_report(cov, floor=0.0)
    assert f"{cov.fraction:.4f}" in coverage.format_report(cov, floor=0.0)


# ---- purity and the import cycle --------------------------------------------------------------


def test_the_measure_is_covered_by_the_purity_glob():
    from test_strategy_purity import _module_name, _pure_sources

    assert "seer_engine.fundamentals.coverage" in {_module_name(p) for p in _pure_sources()}


def test_no_import_cycle_whichever_module_is_imported_first():
    """``coverage`` defers its ``f_fundamental`` import; ``f_fundamental`` imports this package
    at module scope. A module-scope import in ``coverage.py`` makes one of these orders fail."""
    env = dict(os.environ)
    root = Path(seer_engine.__file__).resolve().parent.parent
    env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
    expected = str(coverage.default_max_stale_days())
    for first in (
        "seer_engine.strategies.f_fundamental",
        "seer_engine.fundamentals",
        "seer_engine.fundamentals.coverage",
        "seer_engine.backtest.market",
        "seer_engine.backtest.dev",
    ):
        out = subprocess.run(
            [
                sys.executable,
                "-c",
                f"import {first}\n"
                "from seer_engine.fundamentals import coverage\n"
                "import sys; sys.stdout.write(str(coverage.default_max_stale_days()))\n",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert out.returncode == 0, f"{first} imported first: {out.stderr}"
        assert out.stdout.strip() == expected
