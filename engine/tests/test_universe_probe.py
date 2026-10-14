"""The universe probe: a report that cannot touch the lab."""

from __future__ import annotations

import pytest

from seer_engine.commands import universe_probe as up


def _row(**kw):
    base = dict(store="index", method="M0001", candidate="M0001-A", yearly=0.10,
                drawdown=0.15, profit_factor=1.5, trades=10, beats_spy=True, spy_yearly=0.08)
    return up.Row(**{**base, **kw})


def test_the_report_says_in_words_that_it_writes_nothing():
    """The one claim a reader must be able to trust without reading the code."""
    text = up.format_report([_row()], [_row(store="band")], "index", "band")
    assert "no trial" in text and "no method id" in text and "test-window look" in text


def test_a_deeper_fall_on_the_other_store_is_counted():
    base = [_row(candidate="A", drawdown=0.15), _row(candidate="B", drawdown=0.20)]
    other = [_row(store="band", candidate="A", drawdown=0.18),
             _row(store="band", candidate="B", drawdown=0.19)]
    text = up.format_report(base, other, "index", "band")
    assert "DEEPER on band: 1 of 2" in text


def test_a_candidate_missing_from_the_base_does_not_crash_the_report():
    """A method may define a variant the other store cannot run; the row still prints."""
    text = up.format_report([], [_row(store="band")], "index", "band")
    assert "M0001-A" in text and "-" in text


def test_none_metrics_render_as_a_dash_not_a_zero():
    """A missing number must never read as 0.00%, which is a result."""
    assert up._pct(None).strip() == "-"
    assert up._pct(0.0).strip() == "0.00"


def test_an_unknown_method_id_is_refused_by_name():
    with pytest.raises(SystemExit) as e:
        up.load_methods(["M9999"])
    assert "M9999" in str(e.value)


def test_the_default_methods_all_exist_as_files():
    found = {m.id for m in up.load_methods(up.DEFAULT_METHODS)}
    assert found == set(up.DEFAULT_METHODS)
