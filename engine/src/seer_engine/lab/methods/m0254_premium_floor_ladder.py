"""M0254 — Lean, never leave: the price of risk as a weight dial with a floor that never reaches cash.

Variation of M0251 (reserved by Sera 20261020-1417, parent M0251).

M0251 established the thing worth keeping. Its three-rung ladder on the variance risk premium --
the fear index squared, less the realised variance just past, ranked inside its own trailing year --
earned +6.0% a year unfunded where its upside-down arm earned -1.2%, a 7.2-point gap on the same
book shape and the same trade rate, widening to 12 points over 2009-2015. A mirror that loses money
outright is the strongest evidence this lab has that a timing signal carries information.

What wasted the information was the bottom rung. The ladder sat entirely in cash in 35% of months
(recorded exposure 0.512 against buy-and-hold's 0.992) and the US market rises in roughly six months
out of ten, so a modest advantage in WHICH months cannot pay for sitting out a third of them. Per
unit of time invested the ladder earned about 46% more than buy-and-hold. That arithmetic is the
whole argument for raising the floor rather than tuning the signal.

So this method moves ONE dial and nothing else: the floor. The signal, its reference window, its
cut-offs, the cadence, the rules and the fees are M0251's, imported from M0251's own frozen module
rather than copied, so there is no chance of a transcription drift making this a different signal
wearing the same name::

    floor f in [0, 1],  mid = (1 + f) / 2

    premium in the top third of its own trailing 252 sessions   -> SPY at 1.0
    premium in the middle third                                 -> SPY at (1 + f) / 2
    premium in the bottom third                                 -> SPY at f

Every rung is evenly spaced by construction, so f is a true dose and the three arms plus the
recorded shape lie on one line:

    FLOOR70  f = 0.70   rungs 1.00 / 0.850 / 0.70   the lean is 30 points wide
    FLOOR50  f = 0.50   rungs 1.00 / 0.750 / 0.50   50 points
    FLOOR25  f = 0.25   rungs 1.00 / 0.625 / 0.25   75 points
    FLOOR00  f = 0.00   rungs 1.00 / 0.500 / 0.00   100 points -- M0251-LADDER's shape
    HOLD     f = 1.00   rungs 1.00 / 1.000 / 1.00   no lean at all: the always-invested control

``mirror`` reverses the ladder: the bottom third gets 1.0 and the top third gets f. At f = 0.5 the
reflection is exact -- the same three weights in the same months, assigned the opposite way round --
so MIRROR50 is a shape control matched on the weighting arrangement, the exposure distribution and
(to within the order of the flips) the fee bill. It is the only pair in this method where all three
are matched; every floor-against-HOLD difference deliberately moves exposure, because exposure IS
the treatment.

**Why HOLD is re-run here rather than read off M0251's row.** An allocator's lookback sets its
start date (``dev.candidate_window``), and M0251's HOLD arm ran on the TIMING allocator, whose
"always" rule needs one bar. It therefore started hundreds of sessions earlier than the ladder and
was scored against a different SPY benchmark: 367.6% against the ladder's 323.7%. A paired
difference across two windows is not a paired difference. HOLD here is f = 1.0 on this same
chassis, so it carries the identical 274-bar lookback, the identical start date and the identical
benchmark as every other arm, and the subtraction is clean.

**What cannot be judged here, stated before the run.** An arm with a floor above zero never closes
its position: it trims and tops up one holding forever. ``trades`` counts closed round trips, so
FLOOR70, FLOOR50, FLOOR25 and MIRROR50 will record ``trades 0`` and an undefined profit factor and
will be scored ``failed`` on both (measured on M0182-HI-HALF, 2026-10-19). That is a property of the
shape, not a result. The readable numbers are the funded money-weighted return against the same-window
SPY, the worst fall, the exposure and the 2009-2015 era -- and above all the SHAPE of those numbers
across the four floors, which is what a dose-response ladder buys that a single arm cannot.

Market-aware: ``prepare_market`` carries the series. The history-only path has no series and targets
nothing, per the lab's market-aware contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Method

# The signal itself, imported from M0251's module rather than restated. That module has run and is
# frozen against its recorded sha, so this import is a fixed quantity: FLOOR00 reproduces
# M0251-LADDER's reading bar for bar, and "only the floor moves" is literally true rather than a
# claim about two pieces of arithmetic that look alike.
from seer_engine.lab.methods.m0251_variance_risk_premium_timing import VrpParams, premium_rank
from seer_engine.sim.book import Target, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 20)

#: M0251's reading, frozen. rv_n, rank_n, lo and hi are NOT dials of this method: moving them would
#: make this a search over the signal instead of a dose curve over the floor, and the lab counts
#: every such try against every future result. ``mode="ladder"`` is unused here (this module maps
#: the rungs itself) and is present only because ``premium_rank`` takes a whole ``VrpParams``.
SIGNAL = VrpParams(mode="ladder", rv_n=22, rank_n=252, lo=1.0 / 3.0, hi=2.0 / 3.0)


@dataclass(frozen=True, slots=True)
class FloorParams:
    """``floor`` is the whole method. ``mirror`` reverses which third gets which rung."""

    floor: float = 0.0
    mirror: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.floor, bool) or not isinstance(self.floor, float):
            raise TypeError(f"floor must be a float, got {type(self.floor).__name__}")
        if not 0.0 <= self.floor <= 1.0:
            raise ValueError(f"floor must be in [0, 1], got {self.floor!r}")
        if not isinstance(self.mirror, bool):
            raise TypeError(f"mirror must be a bool, got {type(self.mirror).__name__}")

    @property
    def mid(self) -> float:
        """The middle rung: always the midpoint, so the three rungs are evenly spaced."""
        return (1.0 + self.floor) / 2.0

    def as_dict(self) -> dict[str, str]:
        return {"floor": repr(self.floor), "mirror": repr(self.mirror)}


def _check(params: object) -> FloorParams:
    if not isinstance(params, FloorParams):
        raise TypeError(f"params must be FloorParams, got {type(params).__name__}")
    return params


def weight_for(q: float | None, p: FloorParams) -> float:
    """The share of the account in SPY, from ``q`` (the premium's rank in its trailing year).

    ``q is None`` -- too little history, or no fresh fear index -- is full weight, never the floor,
    exactly as in M0251: that keeps every arm's early window identical, so a paired difference is
    the floor and never a coverage artefact.
    """
    if q is None:
        return 1.0
    step = 2 if q >= SIGNAL.hi else (1 if q >= SIGNAL.lo else 0)
    if p.mirror:
        step = 2 - step
    return (p.floor, p.mid, 1.0)[step]


@dataclass(frozen=True, slots=True, eq=False)
class FloorPrepared:
    history: Mapping[str, History]
    series: MarketSeries


class FloorLadderAllocator:
    """SPY at a weight between ``floor`` and 1.0, set once a month by the price of risk."""

    id = "M0254"
    market_fields = ("series",)

    def lookback(self, params: Any) -> int:
        _check(params)
        # The signal's, not the floor's: identical at every arm, which is what keeps all six
        # scored over the same sessions against the same benchmark.
        return SIGNAL.rank_n + SIGNAL.rv_n

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return False

    def _run(self, prepared: FloorPrepared, data_date: date, held: frozenset[str],
             p: FloorParams) -> tuple[Target, ...]:
        if len(prepared.series) == 0:  # no series: target nothing (market-aware contract)
            return ()
        w = weight_for(premium_rank(prepared.history, prepared.series, data_date, SIGNAL), p)
        if w <= 0.0:  # only reachable at floor 0.0, and only in the bottom third
            return ()
        h = prepared.history.get("SPY")
        if h is None or (h.index_of(data_date) is None and "SPY" not in held):
            return ()  # a symbol with no bar dated d is never a NEW target
        t = target_from_close("SPY", last_close(h, data_date), to_weight(w))
        return () if t is None else (t,)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no series, so no reading and no target."""
        return self._run(FloorPrepared(history, EMPTY_SERIES), data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> FloorPrepared:
        return FloorPrepared(history, EMPTY_SERIES)

    def prepare_market(self, market: Any) -> FloorPrepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        return FloorPrepared(market.history, series)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, FloorPrepared):
            raise TypeError(f"prepared must be FloorPrepared, got {type(prepared).__name__}")
        return self._run(prepared, data_date, held, _check(params))


FLOOR_LADDER = FloorLadderAllocator()


def _v(suffix: str, params: FloorParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0254-{suffix}", family="M0254", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=FLOOR_LADDER, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0254",
    name=("Lean, never leave: the price of risk as a weight dial with a floor that never "
          "reaches cash"),
    family="volatility-risk-premium",
    source_kind="variation",
    source_ref="variation of M0251 (the variance risk premium ladder), lab journal 2026-10-19",
    parent_id="M0251",
    hypothesis=(
        "M0251 showed that the price of risk -- the fear index squared, less the realised variance "
        "just past, ranked inside its own trailing 252 sessions -- carries real information: its "
        "upside-down arm earned -1.2% a year where the ladder earned +6.0%, a 7.2-point gap on the "
        "same book shape and the same trade rate, widening to 12 points over 2009-2015. What wasted "
        "that information was the bottom rung. The ladder sat entirely in cash in 35% of months "
        "(recorded exposure 0.512 against buy-and-hold's 0.992) and the US market rises in roughly "
        "six months out of ten, so a modest advantage in WHICH months cannot pay for sitting out a "
        "third of them; measured per unit of time invested the ladder earned about 46% more than "
        "buy-and-hold. So this method moves ONE dial, the floor, and imports M0251's signal from "
        "M0251's own frozen module so the reading cannot drift: floor f gives rungs 1.0 in the top "
        "third, (1+f)/2 in the middle third and f in the bottom third, evenly spaced by "
        "construction, decided once a month in fractional shares at Gotrade's real fees on the "
        "owner's 5,000,000 IDR monthly top-up. Arms: FLOOR70 (f=0.70, the lean 30 points wide), "
        "FLOOR50 (f=0.50, 50 points), FLOOR25 (f=0.25, 75 points), FLOOR00 (f=0.00, 100 points -- "
        "M0251-LADDER's shape re-run on this chassis so the ladder is internally comparable), HOLD "
        "(f=1.00, always fully invested) and MIRROR50 (f=0.50 reversed). HOLD is re-run rather than "
        "read off M0251's row because an allocator's lookback sets its start date: M0251's HOLD ran "
        "on the TIMING allocator, which needs one bar, so it started hundreds of sessions earlier "
        "and was scored against a different SPY benchmark (367.6% against the ladder's 323.7%), and "
        "a difference taken across two windows is not a paired difference. Every arm here carries "
        "the same 274-bar lookback, the same start date and the same benchmark. MIRROR50 is the one "
        "pair matched on all three of weighting arrangement, exposure distribution and fee bill: at "
        "f=0.5 the reflection is exact, the same three weights in the same months assigned the "
        "opposite way round. Every floor-against-HOLD difference deliberately moves exposure, "
        "because exposure is the treatment, and is therefore an estimate of unknown sign rather "
        "than a bound. Assumed: no fresh fear index or too little history is full weight, not the "
        "floor; the premium is read on day d's close and traded at the next open; idle cash earns "
        "nothing (M0251 priced that at 0.8 points a year before 2008 and nothing after). Success: a "
        "raised-floor arm beats HOLD on the funded money-weighted return, since it keeps the "
        "market's drift and merely leans, AND the curve is monotone in f, so more lean means more "
        "lead. Eligibility is not expected and is not the point: an arm with a floor above zero "
        "never closes its position, so it will record zero closed round trips and an undefined "
        "profit factor and be scored failed on both, which is a property of the shape and not a "
        "result (measured on M0182-HI-HALF). The readable result is the dose curve."
    ),
    expected_failure=(
        "The most likely outcome is that the information is too weak to survive dilution. At a 70% "
        "floor the lean is only 30 points wide, so whatever edge the full ladder had is cut to "
        "roughly a third of it while the market's drift is restored in full; if the premium's "
        "advantage is of the order of a point or two a year, the raised-floor arms will land within "
        "noise of HOLD and the dose curve will be FLAT. A flat curve is the decidable answer the "
        "parent asked for: it would say the signal cannot be used at any dose on this chassis, and "
        "the family should be closed rather than tuned. A second, more interesting failure is that "
        "the curve is monotone the WRONG way -- more lean, less return -- which would mean M0251's "
        "7.2-point gap to its mirror was bought entirely by being out of the market during the two "
        "crashes and not by picking months at all, and that the lab has been crediting a crash "
        "hedge to a signal. Third, the raised floors keep the book invested through 2008, so every "
        "arm's worst fall climbs back towards buy-and-hold's 55%: FLOOR70 should fall about 70% as "
        "far as buy-and-hold does at the worst, around 40%, which is far outside the owner's 25% "
        "real-money limit, so an arm that finally beats SPY on return may breach the depth rule "
        "instead. Fourth, and the reason this may be a risk dial rather than an engine, the return "
        "benefit and the drawdown benefit may sit at opposite ends of the floor curve, in which "
        "case no single floor does both and the honest verdict is that the premium buys shallower "
        "falls at a price in return -- which is what M0251's own numbers already hint at, since its "
        "SPY-200 control beat the ladder on return AND depth at once. Fifth, the comparison itself "
        "is weaker than it looks: HOLD trades almost nothing, so it banks the owner's deposits only "
        "through the rebalance band, while the leaning arms trade every few months and pay Gotrade "
        "for it; part of any gap will be the fee bill and part the deposit channel, and only the "
        "MIRROR50 pair holds those fixed. Sixth, this is a post-2009 anomaly in its second half: "
        "the paper is from 2009, so the 2009-2015 era is the faded one, and that era is the first "
        "filter this lab applies. Finally, at f=1.0 HOLD should reproduce a plain buy-and-hold "
        "almost exactly; if it does not, the chassis itself is doing something and every other "
        "number here is suspect."
    ),
    candidates=(
        _v("FLOOR70", FloorParams(0.70),
           "Floor 70%: rungs 1.00 / 0.85 / 0.70, the gentlest lean the premium can express"),
        _v("FLOOR50", FloorParams(0.50),
           "Floor 50%: rungs 1.00 / 0.75 / 0.50, half the money never leaves the market"),
        _v("FLOOR25", FloorParams(0.25),
           "Floor 25%: rungs 1.00 / 0.625 / 0.25, a deep lean that still never reaches cash"),
        _v("FLOOR00", FloorParams(0.00),
           "Floor 0%: M0251-LADDER's shape re-run here, so the dose curve has a fourth rung"),
        _v("HOLD", FloorParams(1.00),
           "Control: always fully invested, same lookback and same window as every leaning arm"),
        _v("MIRROR50", FloorParams(0.50, mirror=True),
           "Falsification: floor 50% reversed -- the same weights in the same months, flipped"),
    ),
    seen_keys=(
        "concept:variance-risk-premium-floor-ladder",
        "concept:exposure-floor-dose-response",
        "concept:never-fully-in-cash-timing",
    ),
)
