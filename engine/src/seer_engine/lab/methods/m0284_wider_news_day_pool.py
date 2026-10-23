"""M0284 — Is the news-day book short of selectivity, or short of jumps? Turn the volume bar.

Source: variation of M0279 / M0277, both of which sit on M0072-Z2-RAWRANK (Brandt, Kishore,
Santa-Clara & Venkatachalam 2008, SSRN 909563, the earnings-day jump; the jump standardised by
the stock's own swing as in Foster, Olsen & Shevlin 1984 and Bernard & Thomas 1989).

Idea: M0277 and M0279 between them tried six ways of keeping only *part* of the news-day book's
jumps -- by the sign of the earnings surprise, by whether an SEC filing explained the jump, by
the stock's own reporting calendar -- and all six lost to the unfiltered book, by 2 to 6 points
a year in 2009-2015. The exposure report said why: the unfiltered book asks for about 13.6 names
of its 20 slots and every filter cut that to 2-5, parking the difference in SPY during a decade
SPY spent rising. So the book is plausibly short of *jumps*, not short of selectivity. The dial
that controls how many jumps exist is the one filter nobody has turned: the event's volume bar,
fixed at 3x the stock's 60-day median volume since M0063 and never varied.

This method turns that one dial and nothing else. Everything else is M0072-Z2-RAWRANK term for
term: F4's liquidity and membership screen, the SPY-200 monthly trend switch, 20 slots of 5%
with the rest in SPY, a 60-session hold, the up gap, the 4-point market-adjusted three-day jump,
the own-swing filter (z >= 2 of the stock's 60-day daily standard deviation), ranked by the raw
jump, re-picked monthly, fractional shares at Gotrade's real fees on ``monthly-hold-frac-gotrade``,
the owner's monthly deposits.

Five rungs, a dose-response ladder rather than a pair (two points cannot read a slope, and the
lab has been wrong that way before):

    ===========  =========  ==================================================================
    arm          vol_min    what it asks
    ===========  =========  ==================================================================
    ``NOVOL``    none       every up gap with a 4-point jump large for the stock, volume ignored
    ``VOL20``    2x         a day at twice normal volume
    ``VOL25``    2.5x       half way to the parent's bar
    ``VOL30``    3x         **the parent's bar, unchanged: the no-opinion reference rung**
    ``VOL40``    4x         stricter than the parent, the other direction of the same dial
    ===========  =========  ==================================================================

``VOL30`` is the reference arm, not a mirror: it is the whole book with no opinion about volume
expressed, so the cost of every other rung is read against it directly, and it must reproduce
M0072-Z2-RAWRANK's recorded trial bar for bar (same return, same trade count). The ladder is
monotone by construction -- each rung's event set contains the next one's -- so "more jumps"
and "weaker jumps" move together and the shape of the response, not one gap, is the evidence.

A new allocator id is needed (not ``ZJUMP`` itself) because ``config_digest`` reads the allocator
id and the ``VOL30`` rung's params are the parent's exactly; without it the reference rung would
collide with M0072's recorded configuration and could never run. The allocator forwards every
call to M0072's, so the two are the same code and any difference in the numbers is the dial.

Pure: the event columns read bars t-max(vol_base, sd_base)..t+1 and the book reads only events
with t+1 <= i, so nothing dated after the data date is read.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0072_standardised_earnings_jump import ZJUMP, ZParams
from seer_engine.lab.methods.m0277_earnings_confirmed_jump import RAWRANK
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 23)


def _check(params: object) -> ZParams:
    if not isinstance(params, ZParams):
        raise TypeError(f"params must be ZParams, got {type(params).__name__}")
    return params


class VolumeBarAllocator:
    """M0072-Z2-RAWRANK's monthly news-day book with the event volume bar as the dial.

    Every method forwards to ``ZJUMP``. The class exists only to give the ladder its own
    allocator id, so the rung that restates the parent's configuration gets its own
    ``config_digest`` and can be recorded beside the rungs it is the reference for.
    """

    id = "M0284"

    def lookback(self, params: Any) -> int:
        return ZJUMP.lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ZJUMP.symbols(_check(params))

    def holds(self, params: Any) -> tuple[str, ...]:
        return ZJUMP.holds(_check(params))

    def uses_members(self, params: Any) -> bool:
        return ZJUMP.uses_members(_check(params))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return ZJUMP.targets(history, members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> Any:
        return ZJUMP.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return ZJUMP.targets_prepared(prepared, members, data_date, held, _check(params))


VOLBAR = VolumeBarAllocator()


def _rung(vol_min: Decimal | None) -> ZParams:
    """RAWRANK with one field moved: the event's volume bar."""
    return replace(RAWRANK, jump=replace(RAWRANK.jump, vol_min=vol_min))


def _v(suffix: str, vol_min: Decimal | None, rationale: str) -> Candidate:
    return Candidate(id=f"M0284-{suffix}", family="M0284", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=VOLBAR, params=_rung(vol_min), rationale=rationale,
                     added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0284",
    name="Wider news-day pool: take large-for-the-stock jumps on 2x normal volume, not only 3x",
    family="stock-event-drift",
    source_kind="variation",
    source_ref="variation of M0279 / M0277 on M0072-Z2-RAWRANK's frame (Brandt, Kishore, "
               "Santa-Clara & Venkatachalam 2008, SSRN 909563); the 3x volume bar is M0063's "
               "and has never been varied",
    parent_id="M0279",
    hypothesis=(
        "Published 2008, so the dev window can only show an edge from before and just after the "
        "crowd traded it, and a strong dev result is likely to have faded; 2009-2015 is judged "
        "first. M0277 and M0279 tried six ways of keeping only part of the news-day book's jumps "
        "(by the sign of the earnings surprise, by an SEC filing explaining the jump, by the "
        "stock's own reporting calendar) and all six lost to the unfiltered book, by 2 to 6 "
        "points a year in 2009-2015, because they held 2 to 5 names where the unfiltered book "
        "held about 13.6 of its 20 and parked the difference in SPY. So the book may be short of "
        "jumps, not short of selectivity. On M0072-Z2-RAWRANK's frame exactly (monthly, 20 slots "
        "of 5%, rest SPY, SPY-200 switch, 60-session hold, up gap, 4-point market-adjusted "
        "three-day jump, own-swing filter z >= 2, ranked by the raw jump, fractional at Gotrade's "
        "real fees on monthly-hold-frac-gotrade, the owner's monthly deposits), turn the one "
        "filter nobody has varied -- the event's volume bar, 3x the 60-day median since M0063 -- "
        "and nothing else. Five rungs, a ladder and not a pair: NOVOL (no volume bar at all), "
        "VOL20 (2x), VOL25 (2.5x), VOL30 (3x, the parent's bar unchanged, the no-opinion "
        "reference rung every other rung is read against) and VOL40 (4x, stricter, the other "
        "direction of the same dial). The rungs nest, so names held rises monotonically as the "
        "bar falls. I expect the book return to rise as the bar falls from 3x toward 2x, because "
        "the 20 slots fill closer to full and the slots the parent leaves empty earn SPY's return "
        "rather than the picks' -- and if the drift is about any big news rather than about the "
        "volume of the news day, the extra jumps should drift about as well. Success for the "
        "idea: average names held rises above 16 at 2x and the 2009-2015 book return at 2x or "
        "2.5x beats VOL30's by at least 1 point a year, with the response monotone in the bar "
        "across at least four of the five rungs. Success for the gate: a variant with a worst "
        "fall under the screen that beats total-return SPY with DSR >= 0.90."
    ),
    expected_failure=(
        "Lower-volume gaps are weaker news: a 4-point three-day move on ordinary volume is as "
        "likely to be a drifting sector or a thin tape as a real announcement, so the extra "
        "jumps may drift less and dilute the book instead of filling it, making the response "
        "flat or the wrong way round. The parent's own worst fall (23.8%, summer 1998) is "
        "untouched by this dial and is mostly the market's fall behind a late monthly switch, so "
        "every rung probably breaks the worst-fall screen and the gate may reject all five. A "
        "wider pool also means more competition for 20 slots and more turnover, and turnover is "
        "the expensive dial at Gotrade's real fees on a $22-70 slot, so a fuller book can earn "
        "less after costs even when its picks are no worse. NOVOL may reproduce M0071's finding "
        "that volume carries no edge of its own, in which case the whole dial is inert and the "
        "ladder is flat -- which is still the answer to the question. And because the rungs nest, "
        "the five arms are heavily overlapping rather than independent, so a monotone-looking "
        "response can come from a handful of shared names."
    ),
    candidates=(
        _v("NOVOL", None,
           "No volume bar at all: every up gap with a 4-point jump large for the stock"),
        _v("VOL20", Decimal("2"),
           "Twice normal volume: the widest pool the idea asks for"),
        _v("VOL25", Decimal("2.5"),
           "Half way between the widest rung and the parent's bar"),
        _v("VOL30", Decimal("3"),
           "The parent's bar unchanged: the no-opinion reference rung, must reproduce M0072-Z2-RAWRANK"),
        _v("VOL40", Decimal("4"),
           "Stricter than the parent: fewer, heavier news days, the other direction of the dial"),
    ),
    seen_keys=(
        "concept:news-day-volume-bar-dose-response",
        "concept:event-pool-width-vs-selectivity",
    ),
)
