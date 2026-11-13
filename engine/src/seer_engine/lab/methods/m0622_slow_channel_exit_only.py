"""M0622 -- Slow channel exit only: hold the 20 most traded index members until they close under
their 100-day low, with no breakout trigger, behind the 200-day switch.

Source: variation of M0618 (Donchian channel stocks). M0618's slow 200-in/100-out channel was the
only arm that came near SPY (+7.0% vs +7.2% a year on deposits, profit factor 2.12) while the
100/50 breakout lost to its own random-entry control and to a calendar exit. That points at the
slow exit, not the breakout. Donchian exits are old and widely published, so dev may overstate them.

Idea. Strip the entry trigger. A free slot is filled with the most traded index member (F4's screen,
ranked by 20-day dollar volume) that is not already held; a held name is sold only when its close
falls below its lowest close of the prior ``exit_n`` sessions, or when the SPY 200-day switch goes
to cash. A held name stays even if it drops out of the top 20. This reuses M0618's daily, no-resize,
fractional, real-fee chassis (the preset is imported from M0618; a winner still needs it registered
before ``promote``).

Arms (four run):
  SLOW100       treatment: 20 most traded, exit under the 100-day low.
  SLOW50        the faster exit (50-day low): prices how slow the exit has to be.
  SLOW100-NOSW  the treatment never switching to cash: the no-opinion arm for the switch.
  SLOW100-RAND  Control: same slots, exit and daily entry count, but entered names are a hash draw
                (seed 6221) from the 100 most traded, so the 'most traded' pick is priced apart
                from the exit rule.
Calendar twin: not run. M0491-EW-SW (trial 1728) is the 20 most traded behind the same switch,
re-picked monthly, at the same real fees and fractional shares; it is cited, not repeated.
Pure: reads only bars dated <= data_date.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.control_draw import entry_key
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0618_turtle_breakout_stocks import (
    DAILY_HOLD_FRAC_GOTRADE_NORESIZE,
    DonchianAllocator,
    DonchianParams,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED, trend_on

ADDED = date(2026, 11, 13)
NOSW = replace(N20, trend=None)


class SlowExitAllocator(DonchianAllocator):
    """M0618's keep-until-exit book with the breakout trigger replaced by 'fill from the pool'.

    ``mode="brk"`` fills free slots from the ``universe`` most traded by dollar volume;
    ``mode="blind"`` draws the same count by hash from that pool. ``entry_n`` is unused except for
    the lookback. Exit is always the ``exit_n``-session low (exit_kind "low")."""

    id = "M0622"

    def _run(self, history: Mapping[str, History], rows: Any, data_date: date, held: frozenset[str],
             p: DonchianParams) -> tuple[Target, ...]:
        if not trend_on(history, data_date, p.inner):
            return ()
        kept = self._kept(history, held, data_date, p)
        free = p.slots - len(kept)
        if free <= 0:
            return tuple(kept)
        have = {t.symbol for t in kept}
        pool = sorted(
            (r for r in rows if r.symbol not in EXCLUDED),
            key=lambda r: (-r.dollar_volume, r.symbol),
        )[: p.universe]
        names = [r.symbol for r in pool if r.symbol not in have and r.symbol in history]
        if p.mode == "blind":
            names.sort(key=lambda s: (entry_key("M0622", p.seed, s, data_date), s))
        out = list(kept)
        w = equal_weight(p.slots)
        for s in names:
            if len(out) == p.slots:
                break
            px = last_close(history[s], data_date)
            t = None if px is None else target_from_close(s, px, w)
            if t is not None:
                out.append(t)
        return tuple(out)


ALLOC = SlowExitAllocator()


def _v(suffix: str, params: DonchianParams, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0622-{suffix}",
        family="M0622",
        rules=DAILY_HOLD_FRAC_GOTRADE_NORESIZE,
        allocator=ALLOC,
        params=params,
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0622",
    name="Slow channel exit only: hold the biggest names until they close under their 100-day low, no breakout trigger",
    family="stock-slow-trend-hold",
    source_kind="variation",
    source_ref="M0618 (the slow 200/100 arm nearly matched SPY; the breakout entry did not help)",
    parent_id="M0618",
    hypothesis=(
        "M0618's slow 200-in/100-out channel nearly matched SPY (+7.0% vs +7.2% a year on deposits, "
        "profit factor 2.12, 1,002 trades) while the 100/50 breakout lost to its own random-entry "
        "control and to a calendar exit, so the benefit may be holding longer, not the breakout. "
        "Test: fill free slots (20, equal, fractional, real fees, daily no-resize chassis from M0618) "
        "with the most traded index members by 20-day dollar volume, no breakout condition, and sell "
        "a name only when it closes under its 100-day low or the SPY 200-day switch goes to cash. "
        "Arms: SLOW100 (treatment), SLOW50 (faster exit), SLOW100-NOSW (no switch, the no-opinion "
        "arm for the switch), SLOW100-RAND (Control: same exit and entry count, names drawn blind "
        "from the 100 most traded, pricing the most-traded pick). The calendar-hold twin is cited, "
        "not run: M0491-EW-SW (trial 1728, 20 most traded behind the same switch, re-picked monthly) "
        "is that book on the current store at real fees. Closest recorded: M0618-BRK200-100 "
        "(trial 2187, still has the breakout entry). Channel exits date from the 1980s turtle rules "
        "and are widely published, so dev may overstate them. SUCCESS: SLOW100 beats SPY on "
        "deposit-matched money, beats SLOW100-RAND and M0491-EW-SW, has a positive 2009-2015 edge "
        "and a worst fall under 25%."
    ),
    expected_failure=(
        "Every M0618 arm and M0491's most-traded switch book trailed SPY by 4-8 points a year in "
        "2009-2015, so any edge is likely pre-2009. The random-draw control lands within 2 points of "
        "the treatment (the switch and the slow exit do the work, the biggest-names pick adds "
        "nothing), and the book matches M0491-EW-SW's results with different turnover."
    ),
    candidates=(
        _v("SLOW100", DonchianParams(N20, 100, 100, mode="brk", universe=20),
           "20 most traded, hold until a close under the 100-day low, behind the 200-day switch"),
        _v("SLOW50", DonchianParams(N20, 100, 50, mode="brk", universe=20),
           "the same book with the faster 50-day-low exit"),
        _v("SLOW100-NOSW", DonchianParams(NOSW, 100, 100, mode="brk", universe=20),
           "the treatment never switching to cash: the no-opinion arm for the 200-day switch"),
        _v("SLOW100-RAND", DonchianParams(N20, 100, 100, mode="blind", universe=100, seed=6221),
           "Control: same exit and entry count as SLOW100, entered names a blind draw from the 100 most traded"),
    ),
    seen_keys=("concept:slow-channel-exit-only",),
)
