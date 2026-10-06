"""The window a backtest or a research store is bound to (method lab design §3).

One frozen value object and nothing else. The dev window is a module constant in each of the
two modules that own a ``DEV_END`` -- ``backtest.dev.DEV_WINDOW`` and ``research.DEV_WINDOW``,
duplicates pinned equal by ``tests/test_backtest_window.py``, exactly as the two ``DEV_END``
constants are duplicates pinned equal by ``tests/test_fundamentals_coverage.py``. This module
holds no date of its own, so no third copy of ``DEV_END`` exists.

The test window has no constant: its end is whichever session the test store was built to, so
it is made from the dev window with :meth:`Window.following` once that session is known.

``start`` is the first session the window covers, and ``date.min`` means *no lower bound* --
that is the dev window, whose backtests open as early as the data allows (SPY's first session,
1993-01-29) and whose membership lower bound belongs to the vendored CSVs
(``MEMBERSHIP_START``), not to the window. ``end`` is the hard bound: nothing dated after it
may be read. For the dev window that is D9, the guard that keeps the test window unreachable
by accident; for the test window it is the store's own edge.

Pure (``tests/test_strategy_purity.py`` globs ``backtest/*.py``): no clock, no files, no
randomness. ``seer_engine.dates`` is the NYSE calendar, which ``backtest.dev`` already uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from seer_engine import dates

WINDOW_NAMES: tuple[str, ...] = ("dev", "test")
"""The two windows a trial can run on; ``lab.store.WINDOWS`` is the same pair."""


def _as_date(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    return d


@dataclass(frozen=True)
class Window:
    """A named session range: ``name`` ("dev" or "test"), its first session and its last.

    Compared by value, so the dev window built in ``backtest.dev`` and the one built in
    ``research`` are the same window and either may be passed to either module.

    ``start`` is ``date.min`` for the dev window: it has no lower bound, and a candidate's
    window opens wherever its lookback is satisfied (1993 for a long-lookback SPY candidate,
    which is before ``MEMBERSHIP_START``). For the test window ``start`` is a real session and
    is a floor: ``dev.candidate_window`` never opens a candidate before it.
    """

    name: str
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.name not in WINDOW_NAMES:
            raise ValueError(f"window name must be one of {WINDOW_NAMES}, got {self.name!r}")
        _as_date("start", self.start)
        _as_date("end", self.end)
        if self.start > self.end:
            raise ValueError(f"the {self.name} window starts on {self.start}, after its end {self.end}")

    def covers(self, d: date) -> bool:
        """``start <= d <= end``; ``TypeError`` for a non-date (a ``datetime`` included)."""
        return self.start <= _as_date("session", d) <= self.end

    def following(self, name: str, end: date) -> Window:
        """The window opening on the first session after this one and ending on ``end``.

        ``DEV_WINDOW.following("test", last_session)`` is the P7b test window: it starts on
        2015-10-19, the session after ``DEV_END``, and ends wherever the test store's data
        ends (method lab design §3: "2015-10-19 → data end"). ``ValueError`` when ``end``
        falls before that first session.
        """
        start = dates.next_session(self.end)
        if _as_date("end", end) < start:
            raise ValueError(
                f"a {name} window following the {self.name} window ends on or after {start}, got {end}"
            )
        return Window(name=name, start=start, end=end)
