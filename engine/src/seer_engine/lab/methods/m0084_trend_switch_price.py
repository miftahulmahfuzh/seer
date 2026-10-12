"""M0084 — Price the safety switch on its own: SPY behind its 200-day average, read four ways.

Source: variation of M0078 (whose JOINT-EX arm was almost a pure SPY-behind-the-switch book);
Faber (2007), "A Quantitative Approach to Tactical Asset Allocation"; Brock, Lakonishok &
LeBaron (1992), "Simple technical trading rules and the stochastic properties of stock
returns", JF 47(5), for the banded moving-average rule; decades of trend-following lore.
Idea: half the lab's books sit behind the same safety switch -- all cash while SPY closes under
its 200-day average -- and every post-mortem since M0063 has blamed that switch rather than the
picks. The blame has always been inferred from a book that also held stocks, so the switch's
cost is entangled with whatever the stocks did. Strip the stocks out. Hold **only** SPY, at full
weight, behind the switch, and vary nothing except how the switch is read: the rank cadence
(weekly, as M0063/M0078 used; monthly, as M0063-M/M0070/M0088/M0101 used) crossed with the
reading rule (the strict close > SMA200, or M0101's 3% hysteresis band), plus Faber's month-end
10-month rule and a no-switch control. What comes out is a price list for the frame, in points a
year on the owner's deposits at Gotrade's real fees, that every future method can read off
before it spends an id.

Why this is a measurement and not a candidate: a 100%-SPY book cannot beat SPY by construction,
so the only variant with any chance of an edge is one whose switch sidesteps 2000-2002 and 2008
by more than it loses to whipsaw. Eligibility is not the point and is not expected; the paired
differences are.

On data date d the allocator targets SPY at weight 1 when the switch reads on, and nothing
(all cash, no idle symbol) when it reads off. The four readings, all of SPY's own closes:

    * ``switch="none"``: always on. The control -- buy SPY and hold it, through the identical
      fee, deposit and rounding path as the switched variants.
    * ``switch="sma"``: ``f_factor.trend_on`` unchanged -- SPY has a bar dated d, at least 200
      bars through it, and close > SMA(200) strictly. This is the exact gate F4, M0063, M0070,
      M0078, M0088 and M0096 run behind, reused rather than re-implemented.
    * ``switch="band"``: ``m0101.band_on`` unchanged -- hysteresis on SPY's daily close / SMA200.
      Scanning back from d, the newest session under 1 - band turns it off, the newest over
      1 + band turns it on, whichever is newer wins; no crossing within ``m0101.SCAN`` sessions
      falls back to the strict test. The state is read on daily closes; the book acts on it only
      at its own rank session, which is what the cadence pair is measuring.
    * ``switch="faber"``: ``m0101.faber_on`` unchanged -- the newest month-end close (d's own
      close standing for its month) strictly above the mean of the last 10 month-end closes.

``lookback`` is the same constant for every variant (253 bars, M0101's Faber run-up), so all six
are scored on exactly the same sessions and the paired differences are differences of the switch
alone. Reads only bars dated <= d; ``held`` is not read at all (the band's state lives in the
price path, not in the book, so a deposit can never move it). Pure: no clock, no I/O.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0063_earnings_day_jump import WEEKLY_HOLD_FRAC_GOTRADE
from seer_engine.lab.methods.m0101_calm_raisers_banded_switch import (
    FABER_MONTHS,
    band_on,
    faber_on,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, trend_on

ADDED = date(2026, 10, 12)
BENCH = "SPY"  # the only instrument this method ever holds, and the switch's own yardstick
SMA_N = 200  # the moving average every book in the lab switches on
LOOKBACK = max(SMA_N, 23 * (FABER_MONTHS + 1))  # one constant for all variants: one shared window
#: F4's gate value, so ``switch="sma"`` is the lab's switch and not a re-implementation of it.
SMA_GATE = FactorParams(rank="momentum", trend=(BENCH, SMA_N))

Switch = Literal["none", "sma", "band", "faber"]
_SWITCHES: tuple[str, ...] = ("none", "sma", "band", "faber")


@dataclass(frozen=True, slots=True)
class SwitchParams:
    """How SPY's trend is read. The cadence it is read at lives in the variant's ``rules``."""

    switch: Switch = "sma"
    band: Decimal = Decimal(0)  # hysteresis half-width, only with switch="band"

    def __post_init__(self) -> None:
        if not isinstance(self.switch, str) or self.switch not in _SWITCHES:
            raise ValueError(f"switch must be one of {_SWITCHES}, got {self.switch!r}")
        if not isinstance(self.band, Decimal) or not self.band.is_finite():
            raise ValueError(f"band must be a finite Decimal, got {self.band!r}")
        if self.switch == "band" and not Decimal(0) < self.band < Decimal("0.2"):
            raise ValueError(f"band must be in (0, 0.2) for switch='band', got {self.band}")
        if self.switch != "band" and self.band != 0:
            raise ValueError(f"band must be 0 unless switch='band', got {self.band}")

    def as_dict(self) -> dict[str, str]:
        return {"switch": self.switch, "band": format(self.band.normalize(), "f")}


def _check(params: object) -> SwitchParams:
    if not isinstance(params, SwitchParams):
        raise TypeError(f"params must be SwitchParams, got {type(params).__name__}")
    return params


class TrendSwitchAllocator:
    """100% SPY while the switch reads on, all cash while it reads off. Nothing else."""

    id = "M0084"

    def lookback(self, params: Any) -> int:
        _check(params)
        return LOOKBACK

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return False  # the switch reads SPY's own closes; index membership is never touched

    def _on(self, history: Mapping[str, History], data_date: date, p: SwitchParams) -> bool:
        if p.switch == "none":
            return True
        if p.switch == "sma":
            return trend_on(history, data_date, SMA_GATE)
        if p.switch == "band":
            return band_on(history.get(BENCH), data_date, SMA_N, float(p.band))
        return faber_on(history.get(BENCH), data_date, FABER_MONTHS)

    def _run(self, history: Mapping[str, History], data_date: date,
             p: SwitchParams) -> tuple[Target, ...]:
        h = history.get(BENCH)
        if h is None or h.index_of(data_date) is None:  # no bar dated d: no new target
            return ()
        if not self._on(history, data_date, p):
            return ()
        t = target_from_close(BENCH, last_close(h, data_date), equal_weight(1))
        return () if t is None else (t,)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(history, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)  # the readings are cheap and SPY-only: nothing to precompute

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, Mapping):
            raise TypeError(f"prepared must be a Mapping, got {type(prepared).__name__}")
        return self._run(prepared, data_date, _check(params))


SWITCH = TrendSwitchAllocator()
BAND3 = Decimal("0.03")


def _v(suffix: str, params: SwitchParams, rules: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0084-{suffix}", family="M0084", rules=rules, allocator=SWITCH,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0084",
    name="Price the safety switch on its own: SPY behind its 200-day average, read weekly, monthly, with a band or not at all",
    family="market-trend-switch",
    source_kind="variation",
    source_ref=(
        "variation of M0078 (its JOINT-EX arm was almost a pure SPY-behind-the-switch book); "
        "Faber (2007), A Quantitative Approach to Tactical Asset Allocation; Brock, Lakonishok & "
        "LeBaron (1992), Simple technical trading rules, JF 47(5)"
    ),
    parent_id="M0078",
    hypothesis=(
        "Published 1992 (the banded moving-average rule) and 2007 (Faber's 10-month average), on "
        "top of decades of trend-following lore, so the dev window sees every version of this "
        "switch long after the crowd knew it and the plain switch is expected to lag SPY in "
        "2009-2015. The point is to PRICE the frame, not to find an edge. Half the lab's books "
        "sit behind the same switch -- all cash while SPY closes under its 200-day average -- and "
        "every post-mortem since M0063 has blamed the switch rather than the picks, always by "
        "inference from a book that also held stocks. M0078's JOINT-EX arm held SPY behind a "
        "WEEKLY switch almost all the time and earned +3.9% a year on the owner's deposits "
        "against +7.2% for the same deposits in SPY, which puts the weekly switch at about 3 "
        "points a year at Gotrade's real fees; M0063 showed the same book at +5.0% weekly against "
        "+11.6% monthly; M0101 found that on a MONTHLY dividend book a 3% band deepened the worst "
        "fall from 18.7% to 20.4% and widened the 2009-2015 lag from -2.6 to -3.1 points. All "
        "three readings are confounded by the stocks those books held. This method removes them: "
        "hold ONLY SPY at full weight behind the switch, fractional shares at Gotrade's real fees "
        "on the owner's deposits, and vary nothing but the reading. Variants cross the rank "
        "cadence with the reading rule: ALWAYS (no switch, monthly -- buy SPY and hold, the "
        "yardstick through the identical fee, deposit and rounding path); WEEKLY and MONTHLY (the "
        "strict close > SMA200 gate, F4's trend_on unchanged, read at each cadence); BAND3-W and "
        "BAND3-M (M0101's band_on unchanged at 3%, off below 0.97 of the average and back on "
        "above 1.03, read at each cadence); FABER-M (M0101's faber_on unchanged, month-end close "
        "above its 10-month mean). Every variant shares one 253-bar lookback, so all six are "
        "scored on the same sessions and each paired difference is the switch alone. SUCCESS IS A "
        "MEASUREMENT, NOT ELIGIBILITY: a 100%-SPY book cannot beat SPY except by sidestepping "
        "2000-2002 and 2008 for more than whipsaw costs, so no variant is expected to pass the "
        "go-live bars, and none should be promoted. The hypothesis under test is that MONTHLY "
        "beats WEEKLY by 2 or more points a year on the owner's deposits with a similar worst "
        "fall. If it does, every weekly event book in the lab (M0063, M0066, M0072, M0078, M0092) "
        "lost to its frame rather than to its signal, and should be re-framed on the monthly "
        "switch before any of them is abandoned. The second question is whether the 3% band is "
        "worth anything once no stock-picking can mask it, at either cadence."
    ),
    expected_failure=(
        "The switch's whole value is the 2000-2002 and 2008 falls it sits out, and both land in "
        "the first two thirds of the dev window, so MONTHLY may look fine over 1996-2015 and "
        "still lose to SPY from 2009 -- which is exactly what M0096 and M0101 found on a book. "
        "Every variant then reads 'the switch costs money in the era most like today and earned "
        "its keep only in two crashes', and the lab learns a price without learning a frame to "
        "use. ALWAYS and the switched variants will not differ by much in worst fall if the 2008 "
        "exit comes late: SPY had already fallen well over 20% before its 200-day average was "
        "crossed convincingly in the 1998 and 2011 fast drops, so the switched variants may "
        "breach the 20% bar just as ALWAYS does (SPY's own 1996-2015 worst fall is about 55%). "
        "The cadence difference may also be smaller than the 3 points inferred from M0078: that "
        "book paid weekly fees on 20 stock slots as well as on the switch, so a SPY-only weekly "
        "book trades far less and the frame may price out nearer 1 point, which would mean the "
        "weekly event books lost to their signals after all. Trade counts will be tiny (a few "
        "dozen switch flips over 20 years), so profit factor and DSR are close to meaningless "
        "here and no variant will clear the luck bar; the funded return and the era split are the "
        "only readable numbers. Not modelled: interest on the cash held while the switch is off, "
        "which flatters SPY and penalises every switched variant -- in the 1996-2007 part of the "
        "window US cash paid 3-5% a year, so the true cost of sitting out is lower than measured "
        "and the gap this method reports is an upper bound on the switch's cost."
    ),
    candidates=(
        _v("ALWAYS", SwitchParams("none"), MONTHLY_HOLD_FRAC_GOTRADE,
           "Control: buy SPY and hold it, no switch, through the same fee and deposit path"),
        _v("WEEKLY", SwitchParams("sma"), WEEKLY_HOLD_FRAC_GOTRADE,
           "The strict 200-day switch read weekly: the frame M0063 and M0078 ran on"),
        _v("MONTHLY", SwitchParams("sma"), MONTHLY_HOLD_FRAC_GOTRADE,
           "The same strict switch read monthly: the frame M0070, M0088 and M0101 ran on"),
        _v("BAND3-W", SwitchParams("band", BAND3), WEEKLY_HOLD_FRAC_GOTRADE,
           "Leave below 97% of the average, return above 103%, read weekly"),
        _v("BAND3-M", SwitchParams("band", BAND3), MONTHLY_HOLD_FRAC_GOTRADE,
           "Leave below 97% of the average, return above 103%, read monthly (M0101's frame)"),
        _v("FABER-M", SwitchParams("faber"), MONTHLY_HOLD_FRAC_GOTRADE,
           "Faber's switch: SPY's month-end close above its 10-month average, read monthly"),
    ),
    seen_keys=(
        "concept:sma200-trend-switch",
        "concept:trend-switch-cadence",
        "concept:banded-trend-switch",
        "concept:faber-10-month-sma",
    ),
)
