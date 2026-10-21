"""M0267 — Pay the trend rule's premium in shares, not cash: above the line hold QQQ, below it SPY.

Variation of M0265 (reserved by Sera 20261020-1417, parent M0265, grandparent M0254).

M0265 did not find a signal, but it built and priced something the lab did not have: an
**always-invested monthly switch between the only two funds the owner may buy**
(``sim.rules.DEFAULT_ETFS`` is exactly {SPY, QQQ}). Exposure never leaves 0.975-0.987 on any of
its six arms, so the cash cost that defeated M0254 is absent by construction, and the whole bill
is Gotrade's. Its own opinion was worth about 1.4 points a year and the toll was 2.2 to 2.8, so it
lost -- and left behind a chassis with a price tag on it.

M0267 puts the lab's oldest and largest market opinion on that chassis. The 200-day trend rule's
premium has been swept over all 824 recorded trials at a constant 3.6 points a year, and it helped
22 of 22 variants whole-window. It has only ever been spent one way: **in cash**. Insight 462
decomposed a wide book's 8.2-point post-2009 shortfall and found ~3.6 of it was exactly that --
the gate standing in cash through a near-unbroken rise, eleven exits after 2009 and all eleven
false alarms, because that era held no bear market at all. So: same opinion, same chassis, never
cash. SPY above its own 200-day average holds QQQ; below it holds SPY.

**THE TRAP IN THIS METHOD'S OWN HYPOTHESIS, CONFRONTED BEFORE THE RUN AND NOT AFTER IT.**

The tempting arithmetic is: the gate is worth 3.6 points a year, the chassis costs 2.75, therefore
it pays. **That arithmetic is not portable, and neither half of it survives being moved.**

The 3.6 points was measured as CASH against INVESTED -- a gate opinion about whether to be in the
market at all, where the alternative instrument has a beta of zero. Here the same opinion is
expressed as QQQ against SPY, and M0265 measured QQQ's beta to SPY at 0.98 after 2002. *The value
of an opinion depends on the spread of the instruments available to express it*, and that spread
is the same narrow one that killed the parent. So the only honest way to pre-register a number is
to measure the opinion THROUGH THIS PAIR. That was done before this file was committed, on nothing
but the two funds' closes and the gate's own definition -- no backtest, no fees, no deposits, no
compounding -- over the 191 month-end decisions this method's own window yields (1999-12-31 to
2015-10-16, the start set by QQQ's 200th bar on 1999-12-21):

    mean next-month QQQ-minus-SPY log differential, gate ABOVE (126 months):   +0.2373%
    mean next-month QQQ-minus-SPY log differential, gate BELOW  (64 months):   -0.7120%
    the spread the switch is trading:                                          +0.9492%/month

    annualised, against buying SPY and leaving it:   GATE  +1.89 pts    MIRROR  -2.88 pts
    GATE minus MIRROR (the opinion, counted twice):  +4.77 pts   =>   one-sided:  +2.38 pts

**So the gate opinion is worth about 2.4 points a year through this pair, not 3.6.** That is the
first correction, and it is a third of the premium gone purely to the narrowness of the pair.

The second correction cuts the other way, and it is why this method is worth an id anyway. **The
2.75-point toll is not portable either, and it moves further than the premium does.** M0265's
signal changed its mind in 112 of 186 months; the gate changes its mind in **13 of 190**. The toll
M0265 measured was almost entirely fees on those rotations (2.33 points extrapolated to zero fees
against 2.20 measured churn), so it scales with the flip count, and 13/112 of 2.2 points is about
**0.25 points a year**. The chassis is 8.6 times cheaper to operate under this signal than under
the one it was priced with.

Pre-registered, therefore: opinion ~2.4 points, toll ~0.25 points, and on the whole window this
should pay. **It is the era split that says it will not matter.**

    era          n   above   GATE vs SPY   MIRROR vs SPY   GATE-MIRROR   QQQ-HOLD vs SPY
    2000-2002   36    0.22      -1.31         -25.91         +24.61          -27.22
    2003-2008   72    0.72      +1.19          +2.33          -1.14           +3.52
    2009-2015   81    0.80      +3.47          +2.69          +0.78           +6.16

Every point of the whole-window opinion is the dot-com unwind, when the gate was below the line
for 78% of the months and QQQ lost 27 points a year to SPY. In 2003-2008 the opinion is
**negative**. In 2009-2015 -- the lab's first filter, its best-covered era, and the one most like
today -- it is **+0.78 points gross, +0.39 one-sided**, against a toll of ~0.25. That is a coin
flip, and it is dwarfed by the thing sitting next to it in the same row: **QQQ bought once and
left alone beat SPY by 6.16 points a year in that era, and the gate, by stepping out of QQQ 20% of
the time, captured only 3.47 of them.** Post-2009 this method is pre-registered to LOSE to doing
nothing at all, by about 2.7 points a year, for the same structural reason the cash gate lost:
nine of its exits were false alarms in a decade with no bear market, and here a false alarm costs
the QQQ-minus-SPY gap instead of the whole market's rise.

**That is the priced negative this method exists to record, and it is stated before the run.** The
whole-window number will probably look like a win and the honest reading of it is one sentence:
the gate is a crash rule, it was paid once in this window, and a 2000-2002 payout does not make a
rule that was flat-to-negative for the next thirteen years. The run is worth its id because it
closes the shape -- after it, the lab will have spent the gate's opinion through cash (every book
it owns), through a volatility dimmer (M0254), through a fund tilt on a different signal (M0265)
and now through the fund pair itself, and can stop asking.

**Why there is no re-drawn placebo arm, which is a structural fact and not an omission.** D17
refuses a control whose shape does not match the book it controls, and it refused M0265-BLEND for
trading 0.00x and turning over 0.01x its arm. The obvious fix is a sticky placebo drawn to the
gate's own flip calendar. **On a two-state switch that control is degenerate: a sequence that
changes state on exactly the gate's dates is determined by its starting state, so it is either
GATE or MIRROR and nothing else exists.** MIRROR therefore *is* the flip-calendar-matched control
here -- identical months, identical funds, identical fee bill, identical exposure, opposite call --
and it is deterministic, so unlike a draw it carries no sampling noise. The remaining option, a
placebo matched on flip COUNT with re-drawn timing, was rejected on arithmetic rather than taste:
at 13 flips in 190 months a single draw is one sample from a distribution wide enough to swamp a
0.78-point era effect, so one arm of it would be worse than no arm. The distribution itself is
cheap to compute from the monthly differentials with no trial spent, and the analysis will do that
over many draws instead. The ladder is also a dose-response shape, which hardgate D17 exempts
("the rung IS the measurement").

**The ladder.** ``lean`` is the whole dose and the rungs are symmetric about the 50/50 midpoint,
so signed lean runs -1.0, -0.5, (0 implied), +0.5, +1.0 and the GATE-minus-MIRROR gap at half
lean should be half the gap at full lean. Two points on a line through the origin is the
falsification: a gap that does not halve is not the gate's opinion being spent, it is something
else. The implied zero rung -- a static 50/50 -- is deliberately not an arm: M0265 ran it, found
it drifts rather than rebalances (the resize band never fires on a two-name book) and found it
landing within 0.05 points of its two endpoints' average, which SPY-HOLD and QQQ-HOLD give here
for free.

**Why all six arms declare both symbols.** ``dev.candidate_window`` starts a candidate at the
latest date every symbol it reads has enough bars. QQQ's 200th bar is 1999-12-21, so every arm
here -- SPY-HOLD and QQQ-HOLD included, which read a fund they never buy purely to keep this true
-- starts there and is scored over the identical sessions against the identical SPY benchmark. A
difference taken across two windows is not a paired difference.

**This window is not M0265's.** The gate needs 200 bars where M0265's signal needed 274, so this
method starts 1999-12-21 against the parent's 2000-04-07 and sees three and a half extra months
containing the dot-com top. The 2.75-point toll quoted above is therefore a reference figure from
a neighbouring window, never a paired number; the toll of THIS chassis under THIS signal is read
from this method's own arms, where MIRROR holds the flip calendar fixed.

**No cadence dial, deliberately.** M0260, M0261 and M0262 closed reading frequency: the axis turns
at monthly, which month you read beats how often you read it, and the full month-end grid is the
only reliably best choice. This book decides monthly and reads the gate at its decision date, so
it is already on that grid. There is nothing here to tune and this file does not tune it.

History-only: the gate is SPY's own closes, so there is no market series and no
``market_fields``. ``above_sma`` is ``f_index``'s frozen reading, bit-identical to the
``trend_on`` every gated book in the lab already runs.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_index import above_sma

ADDED = date(2026, 10, 21)

#: The lab's gate, frozen: SPY's close strictly above the mean of its last 200 closes. ``TREND_N``
#: is NOT a dial of this method -- it is the number every gated book in the lab already carries,
#: and the number insight 494's 3.6-point sweep was measured on.
TREND_SYMBOL, TREND_N = "SPY", 200

#: The fund held when the gate is on, and the one held when it is off. Both are in
#: ``sim.rules.DEFAULT_ETFS``, so no arm here raises an owner input.
RISK_ON, RISK_OFF = "QQQ", "SPY"


@dataclass(frozen=True, slots=True)
class GateFundParams:
    """``lean`` is the whole dose. ``mirror`` reverses the call; ``fixed`` pins one fund forever."""

    lean: float = 1.0
    mirror: bool = False
    fixed: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.lean, bool) or not isinstance(self.lean, float):
            raise TypeError(f"lean must be a float, got {type(self.lean).__name__}")
        if not 0.0 <= self.lean <= 1.0:
            raise ValueError(f"lean must be in [0, 1], got {self.lean!r}")
        if not isinstance(self.mirror, bool):
            raise TypeError(f"mirror must be a bool, got {type(self.mirror).__name__}")
        if self.fixed is not None and self.fixed not in (RISK_ON, RISK_OFF):
            raise ValueError(f"fixed must be {RISK_ON!r}, {RISK_OFF!r} or None, got {self.fixed!r}")

    def as_dict(self) -> dict[str, str]:
        return {"lean": repr(self.lean), "mirror": repr(self.mirror), "fixed": repr(self.fixed)}


def _check(params: object) -> GateFundParams:
    if not isinstance(params, GateFundParams):
        raise TypeError(f"params must be GateFundParams, got {type(params).__name__}")
    return params


def risk_on_share(on: bool | None, p: GateFundParams) -> float:
    """The share of the account in QQQ; the rest is in SPY. Always sums to the whole account.

    ``on is None`` -- no SPY bar dated d, so the gate cannot be read -- is the neutral 50/50 and
    never an extreme, which keeps every leaning arm identical in any month the gate is unreadable
    so that a paired difference is the opinion and never a coverage artefact. ``above_sma``
    additionally returns False, not None, when fewer than 200 bars are on hand; over this
    method's window SPY always has them (its first bar is 1993-01-29 and the window opens
    1999-12-21), so that branch never fires here.
    """
    if p.fixed is not None:
        return 1.0 if p.fixed == RISK_ON else 0.0
    if on is None:
        return 0.5
    step = 1.0 if (on != p.mirror) else 0.0
    return 0.5 + p.lean * (step - 0.5)


class GateFundRotationAllocator:
    """100% invested at all times, split between QQQ and SPY by the 200-day gate, set monthly."""

    id = "M0267"

    def lookback(self, params: Any) -> int:
        _check(params)
        # The gate's, not the lean's: identical on every arm, which is what keeps all six scored
        # over the same sessions against the same benchmark.
        return TREND_N

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        # Both, on every arm, including the fixed endpoints: the symbol list sets the start date.
        return (RISK_OFF, RISK_ON)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (RISK_OFF, RISK_ON)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return False

    def _one(self, history: Mapping[str, History], symbol: str, data_date: date,
             held: frozenset[str], share: float) -> Target | None:
        if share <= 0.0:
            return None
        h = history.get(symbol)
        if h is None or (h.index_of(data_date) is None and symbol not in held):
            return None  # a symbol with no bar dated d is never a NEW target
        return target_from_close(symbol, last_close(h, data_date), to_weight(share))

    def _run(self, history: Mapping[str, History], data_date: date, held: frozenset[str],
             p: GateFundParams) -> tuple[Target, ...]:
        w = risk_on_share(above_sma(history.get(TREND_SYMBOL), data_date, TREND_N), p)
        # Rank order: the heavier side first, so a partial fill buys the conviction, not the ballast.
        pairs = ((RISK_ON, w), (RISK_OFF, 1.0 - w))
        out = [t for s, share in sorted(pairs, key=lambda x: -x[1])
               if (t := self._one(history, s, data_date, held, share)) is not None]
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(history, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> dict[str, History]:
        return dict(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, Mapping):
            raise TypeError(f"prepared must be a Mapping, got {type(prepared).__name__}")
        return self._run(prepared, data_date, held, _check(params))


GATE_FUND = GateFundRotationAllocator()


def _v(suffix: str, params: GateFundParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0267-{suffix}", family="M0267", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=GATE_FUND, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0267",
    name="Pay the trend rule's premium in shares, not cash: above the 200-day line hold QQQ, below it hold SPY",
    family="market-trend-switch",
    source_kind="variation",
    source_ref="variation of M0265 (the premium picks the fund), lab journal 2026-10-20",
    parent_id="M0265",
    hypothesis=(
        "M0265 found no signal but left a priced instrument: an always-invested monthly switch "
        "between the only two funds the owner may buy, exposure 0.975-0.987 on every arm, costing "
        "2.75 points a year of funded money-weighted return which lab costs showed was entirely "
        "Gotrade's fee bill. This method puts the lab's oldest and largest market opinion on it. "
        "The 200-day trend gate's premium is a constant 3.6 points a year swept over all 824 "
        "recorded trials and helped 22 of 22 variants whole-window, and it has only ever been "
        "spent in CASH -- which insight 462 priced as ~3.6 of a wide book's 8.2-point post-2009 "
        "shortfall, eleven exits after 2009 and eleven false alarms in a decade with no bear "
        "market. So: same opinion, same chassis, never cash. SPY strictly above the mean of its "
        "last 200 closes holds QQQ; below it holds SPY; decided once a month in fractional shares "
        "at Gotrade's real fees on the owner's 5,000,000 IDR monthly top-up. THE ARITHMETIC THAT "
        "MOTIVATES THIS IS NOT PORTABLE AND BOTH HALVES OF IT ARE CORRECTED HERE BEFORE THE RUN. "
        "The 3.6 points was measured as cash against invested, where the alternative instrument "
        "has beta zero; here the alternative is a fund whose beta to SPY M0265 measured at 0.98 "
        "after 2002. The worth of an opinion depends on the spread of the instruments available "
        "to express it, so it was measured through THIS pair before this file was committed, on "
        "nothing but the two funds' closes over the 191 month-end decisions this window yields "
        "(1999-12-31 to 2015-10-16; QQQ's 200th bar is 1999-12-21): the mean next-month "
        "QQQ-minus-SPY log differential is +0.2373%% in the 126 months the gate is above and "
        "-0.7120%% in the 64 below, a spread of +0.9492%% a month, which annualises to GATE "
        "+1.89 points against buying SPY and leaving it, MIRROR -2.88, so GATE minus MIRROR is "
        "+4.77 and the ONE-SIDED OPINION IS +2.38 POINTS A YEAR, NOT 3.6. A third of the premium "
        "is gone to the narrowness of the pair. The toll is corrected the other way and moves "
        "further: M0265's signal changed its mind in 112 of 186 months, this gate in 13 of 190, "
        "and the toll it measured was almost all fees on those rotations, so 13/112 of 2.2 points "
        "is about 0.25 points a year and the chassis is 8.6 times cheaper under this signal than "
        "under the one it was priced with. Opinion 2.4 against toll 0.25 says the whole window "
        "pays. The era split says it will not matter: GATE minus MIRROR is +24.61 points in "
        "2000-2002 when the gate was below for 78%% of months and QQQ lost 27 points a year, "
        "-1.14 in 2003-2008, and +0.78 in 2009-2015 -- so every point of the whole-window opinion "
        "is the dot-com unwind, and in the lab's first-filter era the opinion is +0.39 one-sided "
        "against a 0.25 toll, a coin flip. Beside it in the same row, QQQ bought once and left "
        "alone beat SPY by 6.16 points a year in 2009-2015 while the gate, stepping out of QQQ a "
        "fifth of the time, captured 3.47. Assumed: an unreadable gate is the neutral 50/50, "
        "never an extreme; the gate is read on day d's close and traded at the next open; idle "
        "cash earns nothing, which costs these arms nothing since none holds any. Success, stated "
        "so it can fail: GATE beats MIRROR by about 4.8 points whole-window and by about 0.8 in "
        "2009-2015, the gap halves at half lean so the dose is a line through the origin, and -- "
        "the only test that would make this a direction worth continuing -- GATE beats QQQ-HOLD "
        "in 2009-2015. Eligibility is not expected: these are two-name tilting books so closed "
        "round trips and the profit factor will be thin or undefined, and every arm is invested "
        "through 2000-2002 and 2008, so every worst fall should land near buy-and-hold's."
    ),
    expected_failure=(
        "The pre-registered expectation is that this LOSES, and the shape of the loss is named "
        "here so the result cannot be re-read favourably afterwards. The whole-window numbers "
        "will probably look like a win -- the measured differentials put GATE about 4.8 points a "
        "year above MIRROR and about 1.9 above buying SPY, against a fee toll near 0.25 -- and "
        "that win is one era. 2000-2002 contributes +24.61 points of the GATE-minus-MIRROR gap, "
        "2003-2008 contributes -1.14, and 2009-2015 contributes +0.78. A rule that was paid once, "
        "in the window's first three years, and was flat to negative for the thirteen years after "
        "it, is a crash rule that happened to catch its crash, and quoting its twenty-year average "
        "as an edge is precisely the mistake insight 462 corrected about the cash gate. The "
        "decisive comparison is therefore not GATE against SPY-HOLD but GATE against QQQ-HOLD, "
        "and in 2009-2015 the gate is pre-registered to lose it by about 2.7 points a year, "
        "because nine of its eleven post-2009 exits were false alarms and here a false alarm "
        "costs the QQQ-minus-SPY gap rather than the whole market's rise -- the identical failure "
        "to the cash gate's, merely cheaper. Second, the dose may not halve. The gate is binary "
        "and the rungs are symmetric, so a GATE-minus-MIRROR gap at lean 0.5 that is not close to "
        "half the gap at lean 1.0 means the difference is being made by fees or by the resize "
        "band rather than by the opinion, and the correct conclusion then is that the chassis is "
        "noisier than the signal and not that the lean should be retuned. Third, every arm is "
        "fully invested through two collapses, so SPY-HOLD should fall around 55%% and QQQ-HOLD "
        "far worse, which means any arm that wins on return will almost certainly breach the "
        "owner's 25%% depth rule -- the same way the parent's raised floors did. Fourth, the "
        "window is not the parent's: the gate needs 200 bars where M0265's signal needed 274, so "
        "this starts 1999-12-21 and sees three and a half extra months containing the dot-com "
        "top, which makes the 2.75-point toll a reference from a neighbouring window and never a "
        "paired number. Fifth, insight 479 says a control matched on trades and turnover is still "
        "not return-neutral and insight 481 says an under-shaped control's margin has unknown "
        "sign, so even MIRROR -- which here is matched on every axis the lab checks -- is a "
        "measurement and not a bound. Sixth, hardgate D14 reads this book's curve against kin, "
        "and the P7A f2 family already switches SPY against QQQ on relative momentum at MAR 0.50; "
        "a correlated-kin refusal is likely whatever the numbers say, and the market-trend-switch "
        "family this method is filed under already holds 42 trials whose best MAR is 0.58. "
        "Finally, this is a two-name always-invested book, so insight 495 applies: trade count "
        "will not describe it and the readable meters are exposure and turnover."
    ),
    candidates=(
        _v("GATE", GateFundParams(1.0),
           "The idea: 100%% QQQ while SPY is above its 200-day line, 100%% SPY below it, never cash"),
        _v("GATE-HALF", GateFundParams(0.5),
           "Half the dose: 75/25 either way, so the ladder has a second point on its line"),
        _v("MIRROR", GateFundParams(1.0, mirror=True),
           "Falsification, and the only non-degenerate shape control a two-state switch has"),
        _v("MIRROR-HALF", GateFundParams(0.5, mirror=True),
           "The mirror at half dose, so the gap can be checked for halving on both sides"),
        _v("SPY-HOLD", GateFundParams(0.0, fixed=RISK_OFF),
           "Endpoint: the broad market, bought once and left alone, on this window"),
        _v("QQQ-HOLD", GateFundParams(0.0, fixed=RISK_ON),
           "Endpoint: the tech-heavy fund, bought once and left alone -- the opponent that decides it"),
    ),
    seen_keys=(
        "concept:trend-gate-picks-which-fund-not-whether-invested",
        "concept:gate-premium-paid-in-shares-not-cash",
        "concept:spy-qqq-switch-on-200-day-trend",
    ),
)
