"""The window value object (``backtest.window.Window``) and the two dev-window constants.

``backtest.dev.DEV_WINDOW`` and ``research.DEV_WINDOW`` are duplicates, like the two
``DEV_END``s they are built from; this file is what pins them equal. The test window has no
constant: it is ``DEV_WINDOW.following("test", <the store's last session>)``.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date, datetime

import pytest

from seer_engine import research
from seer_engine.backtest import dev, dev_report
from seer_engine.backtest.window import WINDOW_NAMES, Window


def test_window_validates_its_fields():
    w = Window(name="test", start=date(2015, 10, 19), end=date(2026, 8, 18))
    assert (w.name, w.start, w.end) == ("test", date(2015, 10, 19), date(2026, 8, 18))
    assert WINDOW_NAMES == ("dev", "test")
    with pytest.raises(ValueError, match="window name must be one of"):
        Window(name="prod", start=date(2015, 10, 19), end=date(2026, 8, 18))
    with pytest.raises(ValueError, match="starts on 2026-08-19, after its end"):
        Window(name="test", start=date(2026, 8, 19), end=date(2026, 8, 18))
    with pytest.raises(TypeError):
        Window(name="test", start=datetime(2015, 10, 19), end=date(2026, 8, 18))
    with pytest.raises(TypeError):
        Window(name="test", start="2015-10-19", end=date(2026, 8, 18))


def test_a_window_is_a_frozen_value():
    a = Window(name="dev", start=date.min, end=date(2015, 10, 16))
    b = Window(name="dev", start=date.min, end=date(2015, 10, 16))
    assert a == b and hash(a) == hash(b)
    with pytest.raises(FrozenInstanceError):
        a.end = date(2026, 1, 1)


def test_covers():
    w = Window(name="test", start=date(2015, 10, 19), end=date(2015, 11, 30))
    assert w.covers(date(2015, 10, 19)) and w.covers(date(2015, 11, 30))
    assert not w.covers(date(2015, 10, 16)) and not w.covers(date(2015, 12, 1))
    assert dev.DEV_WINDOW.covers(date(1993, 1, 29))  # date.min: no lower bound
    assert not dev.DEV_WINDOW.covers(date(2015, 10, 19))
    with pytest.raises(TypeError):
        w.covers(datetime(2015, 10, 19))


def test_the_two_dev_windows_are_equal_and_end_on_dev_end():
    assert dev.DEV_WINDOW == research.DEV_WINDOW
    assert dev.DEV_WINDOW.name == "dev"
    assert dev.DEV_WINDOW.start == date.min
    assert dev.DEV_WINDOW.end == dev.DEV_END == research.DEV_END == date(2015, 10, 16)


def test_the_test_window_follows_the_dev_window():
    w = dev.DEV_WINDOW.following("test", date(2026, 8, 18))
    assert w == Window(name="test", start=date(2015, 10, 19), end=date(2026, 8, 18))
    assert w.start == dev_report.TEST_START  # the P7b constant, unchanged
    assert dev.DEV_WINDOW.following("test", date(2015, 10, 19)).end == date(2015, 10, 19)
    with pytest.raises(ValueError, match="ends on or after 2015-10-19"):
        dev.DEV_WINDOW.following("test", dev.DEV_END)
