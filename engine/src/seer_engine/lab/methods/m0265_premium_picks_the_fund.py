"""M0265 — Lean without leaving: the price of risk picks WHICH fund, never how much is invested.

Variation of M0254 (reserved by Sera 20261020-1417, parent M0254, grandparent M0251).

M0251 established that the signal carries information: the price of risk -- the fear index
squared, less the realised variance just past, ranked inside its own trailing year -- had its
upside-down arm lose money where the right-way-up arm made it. M0254 then established, and this
is arithmetic rather than a measurement, that the information cannot be spent as an *exposure*
dial. Splitting each arm against its own mirror gives (what the opinion is worth) divided by
(what sitting out costs) = 0.682 at floor 0 and 0.701 at floor 50. Dilution halves the numerator
and the denominator together, so the ratio is a constant below one and NO floor rescues it.

The ratio is fixed only because the cost is proportional to the lean. Make the cost zero and any
positive opinion wins. So M0265 spends the same reading on a different question: not HOW MUCH is
invested -- that is always 100% -- but WHICH of the two funds the owner can already buy holds it::

    premium in the top third of its own trailing 252 sessions   -> tilt towards QQQ
    premium in the middle third                                 -> half and half
    premium in the bottom third                                 -> tilt towards SPY

``lean`` is how far each tilt goes, and it is a true dose because the rungs are symmetric about
the 50/50 midpoint::

    ROTATE       lean 1.00   rungs 100% QQQ / 50-50 / 100% SPY
    ROTATE-HALF  lean 0.50   rungs  75% QQQ / 50-50 /  75% SPY
    BLEND        lean 0.00   always 50-50 -- the ladder's zero rung AND the no-opinion placebo
    MIRROR       lean 1.00, reversed: the same months, the same two funds, the opposite call

Every one of those four is 100% invested on every session, trades on the same month-end dates and
pays the same Gotrade schedule, so the cost that defeated M0254 is not reduced here, it is absent
by construction. SPY-HOLD and QQQ-HOLD are the two endpoints of the same chassis, so the ladder is
bracketed at both ends by something the owner could simply have bought and left alone.

**Why all six arms declare both symbols.** An allocator's lookback and symbol list set its start
date (``dev.candidate_window`` takes the latest date at which every symbol it reads has enough
bars). QQQ's first bar is 1999-03-10, so the 274th is 2000-04-06 and every arm here starts
2000-04-07 against the same SPY benchmark. SPY-HOLD reads QQQ it does not use purely so that its
window cannot differ: a difference taken across two windows is not a paired difference, which is
the mistake M0254's docstring records about its own parent.

**Two measurements taken before this file was committed, and the reason they are written down
here rather than discovered afterwards.** Neither is a backtest; both are facts about the tape.

1. *The beta spread the idea assumed is not there after 2002.* QQQ's beta to SPY on daily log
   returns is 1.177 over 2000-04 to 2015-10 -- but that whole number is the dot-com unwind. By
   era: 1.775 in 2000-2002, 0.996 in 2003-2008, 0.981 in 2009-2015, with volatility ratios 2.13,
   1.13 and 1.06. So in the lab's first-filter era the two funds carry the SAME market risk, and
   switching between them is not a risk dial at all -- it is a bet on technology against the broad
   market, guided by a market-wide volatility reading. That is a weaker claim than the one the
   idea row reserved, and it is stated before the run rather than after it.

2. *The rung distribution and the raw differential.* Over the 187 month-end decisions in this
   window the rungs split 71 bottom, 50 middle, 66 top, and the rung changed in 112 of 186 steps,
   so this is a busy switch that will pay Gotrade often. The mean next-month QQQ-minus-SPY log
   differential by rung is +0.125% in the top third, -0.289% in the middle and -0.204% in the
   bottom -- the ordering is NOT monotone, the middle rung is the worst of the three. Carrying
   that arithmetic to the ladder (ignoring compounding, fees, deposits and the band) puts
   ROTATE's edge over BLEND at roughly 0.7 points a year before costs, which is exactly the
   0.5-0.9 the idea row predicted from the beta spread, arrived at a different way.

Nothing in this file was tuned on either measurement. The signal, its 22-session realised-variance
window, its 252-session reference window and its one-third cut-offs are imported from M0251's
frozen module; the ladder's rungs are symmetric by construction; and the lean values 1.00, 0.50
and 0.00 are a dose ladder, not a search.

**Prior art the lab already owns.** The P7A registry's f2 family switches between SPY and QQQ on
relative momentum (``concept:f2-spyqqq-12m``, best MAR 0.50). Same two instruments, different
signal entirely: that one reads the funds' own prices against each other, this one reads a
market-wide volatility premium that knows nothing about either fund. SPY and QQQ are also the
*only* pair available: ``sim.rules.DEFAULT_ETFS`` is exactly {SPY, QQQ}, so any other fund would
raise an ``etf:`` owner input and could never be eligible. The expression tested here is therefore
the only exposure-neutral one the owner can actually trade today, which is why it is worth an id
even though the beta measurement above has already weakened it.

Market-aware: ``prepare_market`` carries the series. The history-only path has no series and
targets nothing, per the lab's market-aware contract.
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

# The signal itself, imported from M0251's module rather than restated, exactly as M0254 does.
# That module has run and is frozen against its recorded sha, so "only the expression changes"
# is literally true rather than a claim about two pieces of arithmetic that look alike.
from seer_engine.lab.methods.m0251_variance_risk_premium_timing import VrpParams, premium_rank
from seer_engine.sim.book import Target, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 21)

#: M0251's reading, frozen. rv_n, rank_n, lo and hi are NOT dials of this method. ``mode="ladder"``
#: is unused (this module maps the rungs itself) and is present only because ``premium_rank``
#: takes a whole ``VrpParams``.
SIGNAL = VrpParams(mode="ladder", rv_n=22, rank_n=252, lo=1.0 / 3.0, hi=2.0 / 3.0)

#: The aggressive fund and the broad one. Both are in ``sim.rules.DEFAULT_ETFS``, so no arm here
#: raises an owner input.
RISK_ON, RISK_OFF = "QQQ", "SPY"


@dataclass(frozen=True, slots=True)
class RotateParams:
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


def _check(params: object) -> RotateParams:
    if not isinstance(params, RotateParams):
        raise TypeError(f"params must be RotateParams, got {type(params).__name__}")
    return params


def risk_on_share(q: float | None, p: RotateParams) -> float:
    """The share of the account in QQQ; the rest is in SPY. Always sums to the whole account.

    ``q is None`` -- too little history, or no fresh fear index -- is the neutral 50/50, never an
    extreme. That keeps every leaning arm identical in the months the signal cannot be read, so a
    paired difference is the opinion and never a coverage artefact.
    """
    if p.fixed is not None:
        return 1.0 if p.fixed == RISK_ON else 0.0
    if q is None:
        return 0.5
    step = 2 if q >= SIGNAL.hi else (1 if q >= SIGNAL.lo else 0)
    if p.mirror:
        step = 2 - step
    return 0.5 + p.lean * ((0.0, 0.5, 1.0)[step] - 0.5)


@dataclass(frozen=True, slots=True, eq=False)
class RotatePrepared:
    history: Mapping[str, History]
    series: MarketSeries


class PremiumFundRotationAllocator:
    """100% invested at all times, split between QQQ and SPY by the price of risk, set monthly."""

    id = "M0265"
    market_fields = ("series",)

    def lookback(self, params: Any) -> int:
        _check(params)
        # The signal's, not the lean's: identical at every arm, which is what keeps all six
        # scored over the same sessions against the same benchmark.
        return SIGNAL.rank_n + SIGNAL.rv_n

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

    def _one(self, prepared: RotatePrepared, symbol: str, data_date: date, held: frozenset[str],
             share: float) -> Target | None:
        if share <= 0.0:
            return None
        h = prepared.history.get(symbol)
        if h is None or (h.index_of(data_date) is None and symbol not in held):
            return None  # a symbol with no bar dated d is never a NEW target
        return target_from_close(symbol, last_close(h, data_date), to_weight(share))

    def _run(self, prepared: RotatePrepared, data_date: date, held: frozenset[str],
             p: RotateParams) -> tuple[Target, ...]:
        if len(prepared.series) == 0:  # no series: target nothing (market-aware contract)
            return ()
        w = risk_on_share(premium_rank(prepared.history, prepared.series, data_date, SIGNAL), p)
        # Rank order: the heavier side first, so a partial fill buys the conviction, not the ballast.
        pairs = ((RISK_ON, w), (RISK_OFF, 1.0 - w))
        out = [t for s, share in sorted(pairs, key=lambda x: -x[1])
               if (t := self._one(prepared, s, data_date, held, share)) is not None]
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no series, so no reading and no target."""
        return self._run(RotatePrepared(history, EMPTY_SERIES), data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> RotatePrepared:
        return RotatePrepared(history, EMPTY_SERIES)

    def prepare_market(self, market: Any) -> RotatePrepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        return RotatePrepared(market.history, series)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, RotatePrepared):
            raise TypeError(f"prepared must be RotatePrepared, got {type(prepared).__name__}")
        return self._run(prepared, data_date, held, _check(params))


FUND_ROTATION = PremiumFundRotationAllocator()


def _v(suffix: str, params: RotateParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0265-{suffix}", family="M0265", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=FUND_ROTATION, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0265",
    name="Lean without leaving: the price of risk picks WHICH fund, never how much is invested",
    family="volatility-risk-premium",
    source_kind="variation",
    source_ref="variation of M0254 (the premium floor ladder), lab journal 2026-10-20",
    parent_id="M0254",
    hypothesis=(
        "M0254 proved by arithmetic, not by measurement, that the price of risk cannot be spent "
        "as an exposure dial: splitting each arm against its own mirror, the opinion's worth "
        "divided by the cost of sitting out is 0.682 at floor 0 and 0.701 at floor 50, because "
        "dilution halves both halves together, so the ratio is a constant below one at every "
        "floor. The only escape is to make the cost ZERO. So this method spends the same frozen "
        "reading -- the fear index squared less the realised variance just past, ranked in its own "
        "trailing 252 sessions, imported from M0251's module so it cannot drift -- on WHICH fund "
        "holds the money rather than HOW MUCH is invested. The account is 100% invested on every "
        "session of every arm. Premium in the top third tilts towards QQQ, bottom third towards "
        "SPY, middle third is half and half, decided once a month in fractional shares at "
        "Gotrade's real fees on the owner's 5,000,000 IDR monthly top-up. The tilt width is a true "
        "dose because the rungs are symmetric about the 50/50 midpoint: ROTATE (lean 1.00, rungs "
        "100% QQQ / 50-50 / 100% SPY), ROTATE-HALF (lean 0.50, rungs 75/25 / 50-50 / 25/75) and "
        "BLEND (lean 0.00, always 50-50), which is simultaneously the ladder's zero rung and the "
        "no-opinion shape placebo ROTATE must beat. MIRROR is lean 1.00 reversed: the same two "
        "funds in the same months with the opposite call, matched on exposure (both always 1.00), "
        "on the weighting arrangement and, to within the order of the flips, on the fee bill. "
        "SPY-HOLD and QQQ-HOLD bracket the ladder with the two things the owner could have bought "
        "and left alone. All six arms declare both symbols, so all six start 2000-04-07 (QQQ's "
        "274th bar is 2000-04-06) and are scored against the identical SPY benchmark; SPY-HOLD "
        "reads a fund it never buys purely to keep that true. Two facts were measured before this "
        "file was committed and are recorded here rather than discovered afterwards. First, the "
        "beta spread the idea assumed is not there after 2002: QQQ's beta to SPY is 1.775 in "
        "2000-2002 but 0.996 in 2003-2008 and 0.981 in 2009-2015, so in the lab's first-filter era "
        "the two funds carry the same market risk and this is a technology-against-the-broad-market "
        "bet, not a risk dial. Second, over the 187 month-end decisions the rungs split 71 bottom, "
        "50 middle, 66 top and the rung changed in 112 of 186 steps, and the mean next-month "
        "QQQ-minus-SPY differential by rung is +0.125%%, -0.289%% and -0.204%% from top to bottom "
        "-- not monotone, the middle rung being the worst -- which carried to the ladder without "
        "compounding, fees or deposits puts ROTATE's edge over BLEND near 0.7 points a year before "
        "costs. Nothing here was tuned on either: the signal's windows and cut-offs are M0251's "
        "frozen values and the leans 1.00 / 0.50 / 0.00 are a ladder, not a search. Assumed: an "
        "unreadable signal is the neutral 50/50, never an extreme; the premium is read on day d's "
        "close and traded at the next open; idle cash earns nothing, which costs these arms "
        "nothing since none of them holds any. Success: ROTATE beats BLEND on the funded "
        "money-weighted return without a deeper worst fall, AND the curve is monotone in the lean, "
        "so ROTATE-HALF lands between them and MIRROR lands below BLEND. Eligibility is not "
        "expected: these are two-name books that tilt rather than close, so the closed-round-trip "
        "count and the profit factor will be thin or undefined, and the 2000-2002 collapse sits "
        "inside a 15-year window. The readable result is the dose curve and the ROTATE-MIRROR gap."
    ),
    expected_failure=(
        "The most likely outcome is that the escape works mechanically and still does not pay, "
        "because the opinion is simply too small. Roughly 0.7 points a year before costs is the "
        "pre-registered estimate, and a switch that changes its mind in 112 of 186 months on a "
        "two-name book at Gotrade's real schedule can plausibly spend most or all of that on fees. "
        "If ROTATE beats MIRROR by about 1.4 points -- twice the one-sided estimate -- while "
        "beating BLEND by near zero, the honest reading is that the signal is real, the expression "
        "is free, and the instrument pair is too narrow to carry it. That is the decidable answer "
        "this method exists to give, and it would close the exposure-neutral route rather than "
        "invite another tuning pass. The second and more likely-looking failure is that ROTATE "
        "wins on the 15-year average purely because QQQ fell about twice as far as SPY in "
        "2000-2002 and the premium goes deeply negative during a crash already under way (October "
        "2008 is the window's lowest reading, because trailing realised variance explodes above "
        "the fear index once the fall has started). An arm that merely avoids holding QQQ in 2001 "
        "will look like a signal over this window; BLEND and MIRROR are what separate those, and "
        "the 2009-2015 era column is what decides it, since the measured beta spread in that era "
        "is 0.02 and a rotation with no beta spread has almost no channel left to pay through. "
        "Third, the middle rung's raw differential is the worst of the three, so the ladder is not "
        "monotone in the signal even before any strategy is run; if the dose curve comes out "
        "non-monotone too, the correct conclusion is that the thirds are the wrong shape for this "
        "expression and not that the lean should be retuned. Fourth, every arm is invested through "
        "2008, so every worst fall should land near buy-and-hold's -- SPY-HOLD around 55%% and "
        "QQQ-HOLD worse -- far outside the owner's 25%% real-money limit, which means an arm that "
        "wins on return will almost certainly breach the depth rule, exactly as the raised floors "
        "did in the parent. Fifth, BLEND trades only to rebalance while ROTATE trades to switch, "
        "so part of any ROTATE-minus-BLEND gap is a fee bill and not an opinion; only the "
        "ROTATE-MIRROR pair holds the trade rate fixed, and insight 479 says even a control matched "
        "on trades and turnover is not return-neutral, so the BLEND margin is an estimate of "
        "unknown sign rather than a bound. Sixth, the lab already owns a SPY-against-QQQ switch on "
        "relative momentum in the P7A f2 family at MAR 0.50, so if this one lands near there the "
        "likely explanation is the instrument pair's own ceiling rather than either signal. "
        "Finally, the whole family is post-2009 published work in its second half, so the era that "
        "matters most is the faded one."
    ),
    candidates=(
        _v("ROTATE", RotateParams(1.0),
           "The idea: 100% QQQ when insurance is dear, 100% SPY when it is cheap, never cash"),
        _v("ROTATE-HALF", RotateParams(0.5),
           "Half the tilt: 75/25 at the extremes, so the ladder has a middle dose"),
        _v("BLEND", RotateParams(0.0),
           "Zero rung and shape placebo: always half and half, the same chassis with no opinion"),
        _v("MIRROR", RotateParams(1.0, mirror=True),
           "Falsification: the same months and funds, the call reversed"),
        _v("SPY-HOLD", RotateParams(0.0, fixed=RISK_OFF),
           "Endpoint: the broad market, bought once and left alone, on this window"),
        _v("QQQ-HOLD", RotateParams(0.0, fixed=RISK_ON),
           "Endpoint: the tech-heavy fund, bought once and left alone, on this window"),
    ),
    seen_keys=(
        "concept:premium-picks-which-fund-not-how-much",
        "concept:exposure-neutral-signal-expression",
        "concept:vrp-spy-qqq-rotation",
    ),
)
