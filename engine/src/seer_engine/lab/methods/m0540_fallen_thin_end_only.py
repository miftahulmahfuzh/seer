"""M0540 — The fallen after the storm, thin end only: beaten-down members restricted to the
least-traded part of the pool, bought only while SPY is above its own 200-day average.

Variation of M0535 (a variation of M0285, a variation of M0282; moving-average distance, Avramov,
Kaplanski & Subrahmanyam, working paper 2018; long-term reversal after De Bondt & Thaler 1985).
Reserved by Sera batch 20261112-1241 as an ``idea`` row; this file refines it and keeps its id.

WHY. M0535 put a trading-volume floor on M0285's beaten-down-members book: it dropped the
least-traded 20% or 40% of the day's pool and found the floored book worse than its own blind
draw, while the unfloored book earned more once the dead companies the dev store cannot price
were put back (M0330). One reading of that result, not measured by M0535 itself, is the mirror
one: the bounce M0285 captured lived disproportionately in the names the floor removed. This
tests that directly by keeping only the thin end of the pool instead of dropping it — the least-
traded 40% of the day's sized members, ranked the same way M0535 ranked them (20-session mean
close x volume), just inverted.

REUSE, NAMED. The picking is M0282's, imported unchanged: ``MadParams`` (hold 20, keep while
inside 40, equal slots, monthly, the SPY 200-day switch), ``MadAllocator``, fractional shares at
Gotrade's real fees. M0535's own ``dollar_volume`` and ``DEPTH`` are reused unchanged; the only
new code is ``ThinMadParams.thin_pct`` and a pool step, the mirror of M0535's ``floored_pool``:
after M0282's pool is built, only the least-traded ``thin_pct`` percent of it by 20-day mean
dollar volume is kept, ranked cross-sectionally on the day (a fixed dollar bar would be a date
filter, since dollar volumes grew by an order of magnitude over the dev window). A pool this
leaves under M0282's 50-name minimum holds SPY, as M0282's own guard does.

ARMS. One rung, the one named in the pre-registered hypothesis: the least-traded 40% kept.
    BOT20-SW-THIN40       the fallen book behind the switch, restricted to the pool's least-traded
                          40% by 20-day mean dollar volume
    BOT20-SW-THIN40-PLC   its no-opinion arm: a blind hash-order draw with the same thin pool, book
                          size and entry count, behind the same switch
The unfloored book is not re-run here: it is already recorded twice (M0285-BOT20-SW, and again as
M0535-BOT20-SW-DV00, declared there as M0285-BOT20-SW's twin). It is the reference rung for this
method's analysis, read from its existing trial, not a new arm.

Pure: no clock, randomness, files or network; reads only bars dated on or before ``data_date`` and
share counts filed by it.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0282_moving_average_distance import (
    DEPTH,
    Features,
    MadAllocator,
    MadParams,
    MadPrepared,
    banded,
    pool_on,
    scores,
)
from seer_engine.lab.methods.m0535_fallen_kept_to_live_names import DV_BARS, dollar_volume
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 11, 12)


@dataclass(frozen=True, slots=True)
class ThinMadParams(MadParams):
    """M0282's parameters plus ``thin_pct``, the percent of the day's pool kept, its thin end."""

    thin_pct: int = 40

    def __post_init__(self) -> None:
        MadParams.__post_init__(self)
        if isinstance(self.thin_pct, bool) or not isinstance(self.thin_pct, int):
            raise TypeError(f"thin_pct must be an int, got {type(self.thin_pct).__name__}")
        if not 0 < self.thin_pct < 100:
            raise ValueError(f"thin_pct must be in (0, 100), got {self.thin_pct}")

    def as_dict(self) -> dict[str, str]:
        out = MadParams.as_dict(self)
        out["thin_pct"] = str(self.thin_pct)
        out["dv_bars"] = str(DV_BARS)
        return out


def _check(params: object) -> ThinMadParams:
    if not isinstance(params, ThinMadParams):
        raise TypeError(f"params must be ThinMadParams, got {type(params).__name__}")
    return params


def thin_pool(prepared: MadPrepared, members: AbstractSet[str], data_date: date,
             thin_pct: int) -> dict[str, Features]:
    """M0282's pool restricted to its least-traded ``thin_pct`` percent, or empty when too few
    names remain. The mirror of M0535's ``floored_pool``: same ranking, kept end reversed."""
    pool = pool_on(prepared, members, data_date)
    if thin_pct >= 100 or not pool:
        return pool
    dv = {s: dollar_volume(prepared, s, data_date) for s in pool}
    ranked = sorted((s for s in pool if dv[s] is not None), key=lambda s: (dv[s], s))  # type: ignore[operator]
    keep = math.floor(len(pool) * thin_pct / 100)
    kept = ranked[:keep]
    out = {s: pool[s] for s in sorted(kept)}
    return out if len(out) >= 50 else {}


class ThinMadAllocator(MadAllocator):
    """M0282's picks from a pool restricted to its least-traded names; everything else is
    M0282's."""

    id = "M0540"

    def _names(self, prepared: MadPrepared, members: AbstractSet[str], data_date: date,
               held: frozenset[str], p: Any) -> Sequence[str]:
        p = _check(p)
        if p.signal == "control":
            def replay(d: date, shadow: AbstractSet[str]) -> tuple[list[str], list[str]]:
                pool = thin_pool(prepared, members, d, p.thin_pct)
                if not pool:
                    return [], []
                return sorted(pool), banded(scores(pool, "top"), shadow, p.top, p.keep)

            return control_draw.shadow_book(replay, data_date, held, tag="M0540", seed=p.seed,
                                            depth=DEPTH)
        pool = thin_pool(prepared, members, data_date, p.thin_pct)
        if not pool:
            return []
        return banded(scores(pool, p.signal), held, p.top, p.keep)


THIN = ThinMadAllocator()


def _v(suffix: str, params: ThinMadParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0540-{suffix}", family="M0540", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=THIN, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0540",
    name=("The fallen after the storm, thin end only: beaten-down members restricted to the "
          "least-traded part of the pool behind the 200-day switch"),
    family="stock-moving-average-distance",
    source_kind="variation",
    source_ref=(
        "Variation of M0535 (a variation of M0285, a variation of M0282); long-term reversal "
        "after De Bondt & Thaler (1985); moving-average distance, Avramov, Kaplanski & "
        "Subrahmanyam (2018 working paper); the floor direction is M0535's, mirrored."
    ),
    parent_id="M0535",
    hypothesis=(
        "M0535 found that dropping the least-traded 20% or 40% of the pool made the beaten-down "
        "book worse than a blind draw from the same pool, while the unfloored book earned more "
        "with the dead companies put back. One reading, not measured there, is that the thin "
        "names carried the bounce. This tests it directly by running the mirror of the floor: "
        "keep only the least-traded 40% of the sized members, with a blind draw from the same "
        "thin pool as the no-opinion arm and the unfloored book (already recorded as "
        "M0535-BOT20-SW-DV00, itself M0285-BOT20-SW's twin) as the reference rung, read from its "
        "existing trial rather than re-run. Predictions written before any result: if the thin "
        "end carries the edge, THIN40 should lead its own blind draw by more than the unfloored "
        "book led its draw in M0285/M0535; if it does not, THIN40 should trail its draw the way "
        "the floored (opposite) rungs did in M0535. Read the survivorship-check store first."
    ),
    expected_failure=(
        "In order of likelihood. (1) The thin names are where data errors and collapses sit, so "
        "the lead over the blind draw is noise rather than signal, and it falls to or below the "
        "draw's the way M0535's floored rungs did. (2) Restricting to thin names makes the pool "
        "small and unstable session to session, inflating turnover and fees past any edge they "
        "carry. (3) A collapsing company trades heavily on the way down before it goes thin, so "
        "a dollar-volume ranking is a poor way to isolate 'dying' names in either direction, and "
        "this arm's fall on the survivorship-check store deepens the same way M0535's did. Any "
        "of these is a rejection, not a reason to tune thin_pct afterwards."
    ),
    candidates=(
        _v("BOT20-SW-THIN40", ThinMadParams(signal="bottom", switch=True, thin_pct=40),
           "The fallen book behind the 200-day switch, restricted to the least-traded 40% of "
           "the pool"),
        _v("BOT20-SW-THIN40-PLC",
           ThinMadParams(signal="control", switch=True, seed=1, thin_pct=40),
           "Blind draw from the same thin-restricted pool behind the same switch: no opinion on "
           "names"),
    ),
    seen_keys=(
        "concept:thin-pool-restriction-on-fallen-stocks",
        "concept:long-term-reversal-trend-switch-liveness-floor",
    ),
)
