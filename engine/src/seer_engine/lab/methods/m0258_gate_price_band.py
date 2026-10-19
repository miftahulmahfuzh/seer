"""M0258 -- A price band on the SPY 200-day gate, on a book that actually holds stocks.

Source: variation of M0072-Z2-RAWRANK, whose book is carried here unchanged; the band is
``m0101.band_on``, imported verbatim, as M0084 already imports it; Brock, Lakonishok & LeBaron
(1992), "Simple technical trading rules and the stochastic properties of stock returns", JF 47(5),
for the banded moving-average rule. The rule is thirty-four years old and nothing in it is a new
anomaly, so no fade argument applies to the band itself. What is new is the question.

WHY THIS METHOD EXISTS. On 2026-10-19 a study of the SPY 200-day gate found that a price band --
leave only once SPY closes b% UNDER its 200-day average, return only once it closes b% OVER --
beat the bare gate on every axis measured, and the handover written from it asked for a method.
Two things about that request are already answered in the lab's own record, and a third is not.

Every figure below is the MONEY-WEIGHTED return on the owner's own deposits -- what `lab show`
calls "your money earned" -- because these books are funded with a monthly top-up and the
curve-shape columns beside it, as `backtest/metrics.py` says outright, "are not returns at all".
SPY's figure is the SAME deposits into SPY over the same window.

    * Does a band help a book that holds stocks? The lab ran it. M0101-BAND-3 against M0101-CTRL,
      the same calm-big-raisers book either side, SPY taking the same deposits at 7.19%/yr: the
      band earned 10.44%/yr against 10.62% and fell 20.39% against 18.71%, on 525 trades against
      528. M0101-BAND-5 was worse again, 10.10%/yr and 20.39%. The band cost 0.18 points a year
      at 3% and 0.52 at 5%, and fell 1.68 points deeper at both.
    * Does a band help SPY alone, read monthly? The lab ran that too. M0084-BAND3-M earned
      8.73%/yr and fell 20.69%; M0084-MONTHLY, the bare gate, earned 9.13%/yr and fell 18.89%,
      against 7.69%/yr for the same deposits in SPY. The band cost 0.40 points a year and fell
      1.80 points deeper. Again it earned less and fell further.
    * And then the pair nobody has read in this light. M0084-WEEKLY, the SAME bare gate read
      WEEKLY, earned 4.35%/yr and fell 33.13% -- it lost to its own deposits in SPY by more than
      three points. M0084-BAND3-W, the same band read weekly, earned 7.78%/yr and fell 18.92%.
      Read weekly the band is worth +3.42 points a year and 14.22 points of worst fall. Read
      monthly it is worth -0.40 and 1.80 points WORSE.

So the lab has already recorded a 3.82-POINT SWING in what the band is worth, in money, between
two reading cadences on one instrument -- and it has never named it. That is this method's
question: **is the band's worth a function of how often the gate is READ, and does that hold on a
book that holds stocks?**

THE CADENCE GRID (measured on the dev store before this file was written, by
``docs/backtests/2026-10-19-gate-band-cadence.py``; this is a FEASIBILITY TABLE and a PRIOR, not a
result, in the same spirit as M0245's episode ledger and M0241's split-count table). SPY alone,
200-bar warmup, one-session lag, the signal held as read at each rank session:

    signal        gate read   whole CAGR   worst fall   2009-2015   invested   flips
    bare gate     daily           6.05%       -28.7%        6.96%      71.6%     152
    bare gate     weekly          5.51%       -34.6%        5.82%      70.8%      80
    bare gate     monthly         9.08%       -19.0%       10.07%      71.9%      22
    band 1.5%     daily           7.35%       -19.5%        9.44%      70.8%      46
    band 1.5%     weekly          6.95%       -24.5%        8.42%      70.9%      46
    band 1.5%     monthly         7.94%       -19.0%       10.07%      70.4%      32
    band 3%       daily           7.87%       -20.3%        8.83%      72.4%      20
    band 3%       weekly          8.03%       -19.0%        8.84%      72.4%      20
    band 3%       monthly         8.96%       -20.7%        9.46%      72.4%      18
    band 6%       daily           7.91%       -20.4%        7.02%      70.3%      12
    band 6%       weekly          8.15%       -21.8%        6.91%      70.4%      12
    band 6%       monthly         7.86%       -20.7%        6.72%      69.7%      12

    gate read    band 3% minus bare gate, return    the same, worst fall
    daily                       +1.82 pts/yr            8.4 pts better
    weekly                      +2.53 pts/yr           15.5 pts better
    monthly                     -0.12 pts/yr            1.7 pts WORSE

(Those three pairs are at full precision, which is what the script prints. Differencing its
printed two-decimal grid instead gives the weekly pair as +2.52 and 15.6 -- the same facts, one
hundredth and one tenth apart.)

The grid reproduces the four recorded M0084 trials above in both sign and magnitude, which is why
it is trusted here; it shares no code with the simulator that produced them. And the monthly bare
gate beats the daily 3% band on every axis in the original study's own table.

THE MECHANISM IS NOT NEW, IT IS THE SAME ONE. A band suppresses flips shorter than the band is
wide. A monthly reading suppresses flips shorter than a month. They are substitutes, and the lab
already owns the second one. The study's own numbers said so and were read the other way round:
its band left "exactly 11 episodes -- the number insight 452 reports", and insight 452 counted the
gate at its MONTHLY checks. The monthly reading is not a coarser version of the gate the lab
reasons about; it IS the gate the lab reasons about, and it is already cleaner than the band.

WHAT IS ALREADY DEAD, AND WHY A BAND IS NOT ONE OF THEM. The handover lists every modification of
this gate the lab has measured and buried, and none of them is re-tested here: turning the gate
off (helped 22 of 22 variants whole-window, 0 of 22 after 2009, and every gate-off arm was worse
on return AND drawdown at once); a TIME lock on the switch (costs return and deepens the fall from
20% to 32%, because the flips it suppressed included the 2008-05-21 exit, one day after the
previous episode ended); an account-reading drawdown brake (pays 10 points a year of 2009-2015 to
save 40 of 2008); a learned fall-sizing brake (M0132, beaten by the plain gate on both axes);
VIX-level confirmation of the exit (worse on both axes at 20, 25 and 30, and VIX3M only begins
2006-07-17 so it cannot be checked against the dot-com at all); and exit-buffer-only,
confirm-N-days, partial exposure and fast re-entry on the 50-day, all in the committed grid and
all worse than the symmetric band. The standing rule after the time lock reads "stop hunting
hysteresis here". A band in PRICE is not that lock: the lock suppressed an exit because of WHEN
the previous one ended, and the band has no memory of time at all -- it reads only where price
stands against the average. The handover says this explicitly, and the lab's own weekly pair above
is the evidence that the two are different animals.

THE HOST BOOK, AND WHY IT IS THIS ONE. M0072-Z2-RAWRANK, carried verbatim: M0063's earnings-day
jump event kept only when the jump is at least two of the stock's own daily swings and ranked by
the raw jump, F4's five-dollar and twenty-million-dollar screen, 20 slots at 5%, SPY in the empty
ones, re-picked at the rule set's cadence, fractional shares at Gotrade's real fees on the owner's
monthly top-ups. It is one of only three books the lab reads as promotable and kin-clean, and the
only one of the three whose engine is cadence-robust: its event hold is counted in SESSIONS, not
calendar months, and its parent M0063 ran the identical book weekly and monthly. The other two
cannot carry a cadence axis -- M0197's chooser keys its re-pick on the calendar month itself.
Its recorded trial earned 12.33%/yr on the owner's deposits against 7.19% for the same deposits in
SPY, fell 23.80% at worst, and made gains 1.98 times its losses on 1208 trades and 6.53 turns a
year.

WHY A NEW ALLOCATOR ID AND NOT A WIDER PARAMETER. ``f_factor.FactorParams.trend`` is
``tuple[str, int] | None`` and ``config_text`` renders it "SPY:200". Widening it to carry a band
would move every recorded config digest in the lab. The band therefore lives in a new dataclass
behind a new allocator id. That costs one method id, and that is the correct price.

HOW THE OVERLAY WORKS, AND THE ONE LINE IT REPLACES. ``BandedGateAllocator`` delegates lookback,
symbols, holds, uses_members and prepare to ``ZJUMP`` and runs M0072's own target builder on
M0072's own prepared panel. Exactly one line differs: the gate reading.

    * ``band = 0``: ``f_factor.trend_on`` unchanged. Not ``band_on`` at zero -- although the two
      are provably the same thing on this tape (``test_lab_m0258_band.py`` asserts it session by
      session), the zero rung's job is to REPRODUCE the host's recorded trial, and a reproduction
      should run the host's own code.
    * ``band > 0``: ``m0101.band_on(history.get(symbol), data_date, n, float(band))`` with
      ``(symbol, n)`` taken from the book's own ``jump.inner.trend``, so the band is read on the
      same symbol and the same average the bare gate reads. Scanning back from the data date, the
      newest session under 1-band turns it off and the newest over 1+band turns it on, whichever
      is newer; with no crossing inside ``m0101.SCAN`` sessions it falls back to the strict test.
      The state is read on DAILY closes and the book acts on it only at its own rank session,
      which is exactly the thing the cadence pair is measuring.

``lookback`` is ``ZJUMP.lookback(p.book)`` and nothing else -- 253 bars. ``SCAN`` is deliberately
NOT added, for M0101's recorded reason: it would move the dev window's first scored session off
the host's and break the paired comparison. On the dev store SPY has years of run-up before
1996-01-03, so a crossing older than the bars on hand cannot arise.

THE SIX ARMS. All six hold M0072-Z2-RAWRANK's book, unchanged. Only the band and the cadence move.

    * M-B0  monthly, band 0     the paired bare gate and the ladder's zero dose; must reproduce
                                the host's recorded trial through a new digest
    * M-B15 monthly, band 1.5%  the measured plateau's lower edge
    * M-B30 monthly, band 3%    the band arm, at the handover's own value
    * M-B60 monthly, band 6%    the plateau's upper edge
    * W-B0  weekly,  band 0     the same book and the same bare gate, read weekly
    * W-B30 weekly,  band 3%    the same band, read weekly

Arms one to four are a dose-response ladder in the band, and the ladder with its zero rung IS the
control: the lab's own standing finding is that a dose-response beats a drawn control, because
more of the treatment giving more of the effect excludes a frame effect by construction. No arm is
a drawn control, and hard gate D17 refuses only drawn arms and never refuses a method that has
none. Arms five and six turn a predicted null into a difference-in-differences with a sign written
down before the run.

THE WEEKLY ARMS CAN NEVER BE PROMOTED, AND THAT IS DELIBERATE. ``WEEKLY_HOLD_FRAC_GOTRADE`` is
M0063's one-off rule set and is not a member of ``sim.rules.PRESETS``, which ``lab promote``
requires. It differs from the monthly preset in exactly two fields, ``id`` and ``cadence``, so the
cadence axis is clean. The promotable arms are the four monthly ones; the weekly pair is
diagnostic. Minting a preset to make them promotable would be scope nobody asked for, and the
honest thing is to say so here rather than work around it.

Pure: no clock, no randomness, no network, no file, no printing. Reads only bars dated on or
before ``data_date``. ``held`` is read only where M0072 reads it -- to let a name keep its slot --
and the band's state lives in the price path, never in the book, so a deposit cannot move it.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0063_earnings_day_jump import WEEKLY_HOLD_FRAC_GOTRADE
from seer_engine.lab.methods.m0072_standardised_earnings_jump import (
    JUMP20,
    ZJUMP,
    ZParams,
    ZPrepared,
)
from seer_engine.lab.methods.m0101_calm_raisers_banded_switch import band_on
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import factor_rows, trend_on

ADDED = date(2026, 10, 19)

#: The widest half-band this method will accept. M0101 and M0084 both use 0.2 and both forbid 0;
#: here 0 is the ladder's zero dose and must be allowed, so the bound is half-open at the bottom.
MAX_BAND = Decimal("0.2")


@dataclass(frozen=True, slots=True)
class BandParams:
    """``book`` is M0072's book, carried whole; ``band`` is the gate's hysteresis half-width.

    ``band = 0`` is the bare gate and is legal here, unlike in M0101's ``SwitchParams``, because
    this method's ladder needs a zero dose that runs through the same allocator id as its rungs.
    """

    book: ZParams
    band: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        if not isinstance(self.book, ZParams):
            raise TypeError(f"book must be ZParams, got {type(self.book).__name__}")
        if self.book.jump.inner.trend is None:
            raise ValueError("book must carry a trend symbol and length for the band to read")
        if not isinstance(self.band, Decimal) or not self.band.is_finite():
            raise ValueError(f"band must be a finite Decimal, got {self.band!r}")
        if not Decimal(0) <= self.band < MAX_BAND:
            raise ValueError(f"band must lie in [0, {MAX_BAND}), got {self.band}")

    def as_dict(self) -> dict[str, str]:
        """Every field as a plain string, the book's prefixed ``book.`` -- M0101's shape exactly."""
        out = {"band": format(self.band.normalize(), "f")}
        for k, v in self.book.as_dict().items():
            out[f"book.{k}"] = v
        return out


def _check(params: object) -> BandParams:
    if not isinstance(params, BandParams):
        raise TypeError(f"params must be BandParams, got {type(params).__name__}")
    return params


class BandedGateAllocator:
    """M0072's standardised-jump book, with a price band around the gate it already runs behind."""

    id = "M0258"

    def lookback(self, params: Any) -> int:
        """The host's lookback and nothing else -- 253 bars. ``m0101.SCAN`` is never added.

        Widening this would move the dev window's first scored session off M0072's 1996-01-03 and
        turn the ``band = 0`` arm from a reproduction into an approximation, which is the one
        thing this method cannot afford: every claim it makes is a paired difference.
        """
        return ZJUMP.lookback(_check(params).book)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ZJUMP.symbols(_check(params).book)

    def holds(self, params: Any) -> tuple[str, ...]:
        return ZJUMP.holds(_check(params).book)

    def uses_members(self, params: Any) -> bool:
        return ZJUMP.uses_members(_check(params).book)

    def _on(self, history: Mapping[str, History], data_date: date, p: BandParams) -> bool:
        """The single line this allocator exists to replace: how the gate reads SPY.

        At ``band = 0`` this is the lab's gate, run through the lab's own function rather than
        through ``band_on`` at zero. The two agree on every session of the dev tape -- the test
        module asserts it -- but the zero rung's job is to reproduce the host, and a reproduction
        runs the host's code.
        """
        inner = p.book.jump.inner
        if p.band == 0:
            return trend_on(history, data_date, inner)
        symbol, n = inner.trend
        return band_on(history.get(symbol), data_date, n, float(p.band))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path, kept target-for-target identical to M0072's at ``band = 0``.

        ``ZJUMP._targets`` is reached directly because M0072 exposes no seam between its gate test
        and its target builder, and the obvious alternative is wrong: handing ``ZJUMP`` a
        gate-free twin of its params (``trend=None``) runs -- its lookback and symbols are
        identical, measured -- but it would make the recorded row a lie: ``config_text`` digests
        ``BandParams``, which holds the book UNMODIFIED, so the row would say ``trend=SPY:200``
        while the allocator ran something else. Calling the builder with the host's own params
        keeps the book provably identical and replaces exactly the gate. The private call is safe
        because ``m0072.py`` is frozen against its recorded source sha.
        """
        p = _check(params)
        if not self._on(history, data_date, p):
            return ()
        rows = factor_rows(history, members, data_date, p.book.jump.inner)
        return ZJUMP._targets(ZPrepared(history, None), rows, data_date, held, p.book)

    def prepare(self, history: Mapping[str, History]) -> ZPrepared:
        return ZJUMP.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ZPrepared) or prepared.factor is None:
            raise TypeError(f"prepared must be a prepared ZPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not self._on(prepared.history, data_date, p):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.book.jump.inner)
        return ZJUMP._targets(prepared, rows, data_date, held, p.book)


BANDED = BandedGateAllocator()

#: M0072-Z2-RAWRANK's configuration, verbatim: the Z2 filter ranked by the raw jump.
BOOK = ZParams(JUMP20, z_min=Decimal("2"), rank="raw")

B15 = Decimal("0.015")
B30 = Decimal("0.03")
B60 = Decimal("0.06")


def _v(suffix: str, band: Decimal, rules: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0258-{suffix}", family="M0258", rules=rules, allocator=BANDED,
                     params=BandParams(BOOK, band), rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0258",
    name="A price band on the 200-day safety gate, on a book that holds stocks: is the band worth "
         "anything once the gate is only read once a month?",
    family="stock-event-drift",
    source_kind="variation",
    source_ref=(
        "variation of M0072-Z2-RAWRANK (its book unchanged); the band is m0101.band_on verbatim, "
        "as M0084 already reuses it; Brock, Lakonishok & LeBaron (1992), Simple technical trading "
        "rules and the stochastic properties of stock returns, JF 47(5), for the banded "
        "moving-average rule"
    ),
    parent_id="M0072",
    hypothesis=(
        "Published 1992 (the banded moving-average rule), so nothing in the band is a new anomaly "
        "and no fade argument applies to it; what is new is the question. A study on 2026-10-19 "
        "found that a price band around the SPY 200-day gate -- leave only once SPY closes b "
        "percent under its 200-day average, return only once it closes b percent over -- beat the "
        "bare gate on every axis, and asked for a method. The lab has already answered half of "
        "that twice and recorded the answers, and every figure here is the MONEY-WEIGHTED return "
        "on the owner's own monthly deposits, which is the only honest headline for a funded "
        "book -- what the lab prints as 'your money earned', against the SAME deposits put into "
        "SPY, which earned 7.19% a year over M0101's and M0072's window and 7.69% over M0084's. "
        "On a book that holds stocks, M0101-BAND-3 earned 10.44% a year against M0101-CTRL's "
        "10.62% and fell 20.39% against 18.71%, on 525 trades against 528 and turnover 4.727 "
        "against 4.780; M0101-BAND-5 earned 10.10%. So on a stock book the band COST 0.18 points "
        "a year at 3% and 0.52 at 5%, fell 1.68 points deeper at both, and barely changed how "
        "much the book traded. On SPY alone read monthly, M0084-BAND3-M earned 8.73% against "
        "M0084-MONTHLY's 9.13% and fell 20.69% against 18.89%: the band cost 0.40 points and fell "
        "1.80 deeper. But the lab also recorded, and never read, the other half. On SPY alone "
        "read WEEKLY the bare gate earned just 4.35% a year -- more than three points BELOW its "
        "own deposits in SPY -- and fell 33.13%, while the same band read weekly earned 7.78% and "
        "fell 18.92%, on turnover 0.861 against 3.383. Read weekly the band is worth +3.42 points "
        "a year and 14.22 points of worst fall; read monthly it is worth -0.40 and 1.80 points "
        "worse. That is a 3.82-point swing in the band's worth, in money, from the reading "
        "cadence alone, already recorded. (Every difference in this paragraph is taken at full "
        "precision from the recorded money-weighted returns, so it can be re-derived exactly; "
        "differencing their two-decimal printed forms instead gives +3.43, 14.21 and 3.83.) The "
        "cadence grid measured for this file (SPY alone, dev store, "
        "one-session lag, signal held as read at each rank session) says the same thing as a "
        "smooth function: band 3% minus bare gate is +1.82 points a year and 8.4 points of worst "
        "fall better when the gate is read daily, +2.53 and 15.5 better read weekly, and -0.12 "
        "and 1.7 points WORSE read monthly. The monthly bare gate beats the daily 3% band on "
        "every axis in the original study's own table. The mechanism is not new: a band "
        "suppresses flips shorter than the band is wide, a monthly reading suppresses flips "
        "shorter than a month, and they are substitutes -- which is why the study's band left "
        "exactly the eleven episodes insight 452 counted AT ITS MONTHLY CHECKS. So the question "
        "worth one method id is not 'does the band win', which the lab has answered twice, but "
        "'IS THE BAND'S WORTH A FUNCTION OF HOW OFTEN THE GATE IS READ, ON A BOOK THAT HOLDS "
        "STOCKS'. Six arms hold M0072-Z2-RAWRANK's book verbatim -- the standardised earnings-day "
        "jump kept at two of the stock's own daily swings and ranked by the raw jump, F4's "
        "five-dollar and twenty-million screen, 20 slots at 5%, SPY in the empty ones, fractional "
        "at Gotrade's real fees on the owner's monthly top-ups -- and move only the band and the "
        "cadence: M-B0 (monthly, no band: the paired bare gate and the ladder's zero dose, which "
        "must reproduce the host's recorded trial), M-B15, M-B30 and M-B60 (monthly, 1.5%, 3% and "
        "6%: the dose-response ladder across the measured plateau), W-B0 and W-B30 (the same book "
        "and the same two signals read weekly). The lookback is M0072's 253 bars exactly, so "
        "every arm is scored from 1996-01-03 on the same sessions and each paired difference is "
        "the gate alone. THE PRE-REGISTERED PREDICTION, written before the run: (W-B30 minus "
        "W-B0) much greater than (M-B30 minus M-B0), which is itself about zero, on return AND on "
        "worst fall; and the monthly ladder flat or gently downward in the band across 0, 1.5, 3 "
        "and 6 percent rather than humped. SUCCESS IS A MEASUREMENT, NOT ELIGIBILITY. This method "
        "is bought to settle a cadence question the lab has been reasoning past, and a null on "
        "the monthly pair is a result that corrects a standing document. If instead the monthly "
        "pair shows a real gap on a book of stocks, then the handover's finding survived contact "
        "with stock selection and the lab has a genuinely better gate, which would be worth far "
        "more than one id. Assumed without asking: that M0072 is the right host because it is one "
        "of three promotable, kin-clean books and the only one whose engine counts its hold in "
        "sessions rather than calendar months, so it can carry a weekly arm honestly."
    ),
    expected_failure=(
        "The most likely outcome is simply NOTHING on the monthly pair -- M-B30 within a few "
        "tenths of a point of M-B0 on return and within a point or two on worst fall, and the "
        "ladder across 0, 1.5, 3 and 6 percent flat or drifting down rather than rising. That is "
        "what the cadence grid predicts and what M0101 already recorded on a different book, and "
        "if it happens this method has bought a null. The null is still worth the id, because the "
        "lab is currently carrying a committed study and a journalled insight whose headline "
        "compares the band against a baseline no book in the lab runs, and nothing short of a "
        "pre-registered paired measurement on a real book corrects that. Second, the walk-forward "
        "folds pick each fold's variant by MAR, so they will favour whichever arm trades least -- "
        "M0245's folds picked its slowest rung in three of four, and the lab has written that "
        "down. A fold majority won by M-B60 is therefore weak evidence for the band and should be "
        "read as evidence about turnover; read the folds arm by arm, not just the headline. "
        "Third, the weekly arms run on a rule set that is not in the promotion presets, so they "
        "can never be promoted no matter what they show; they are diagnostic, and a result that "
        "lives only in them is a measurement the lab cannot act on. Fourth, even if the weekly "
        "band does win, it may be a FEE story rather than a signal story: the band cuts the "
        "gate's own flips by about a factor of four, a weekly book pays Gotrade on every re-pick, "
        "and the fee term was the second-largest container in the 824-trial shortfall sweep. The "
        "ladder is the only defence against that reading -- a fee story should keep improving "
        "monotonically as the band widens and trading falls, while a signal story should peak and "
        "turn. But note what is already measured about that: the band cut turnover only at the "
        "WEEKLY cadence, 0.861 against 3.383 on the weekly SPY book, a 75% cut. On both recorded "
        "MONTHLY books it cut essentially nothing -- 4.727 against 4.780 on M0101's stock book, a "
        "1.1% difference on 525 trades against 528, and 0.826 against 0.826 on SPY. So the "
        "brief's premise that the band cuts turnover sharply is a weekly-cadence fact and not a "
        "monthly one, the four monthly arms here are expected to differ from each other in shape "
        "by well under 1%, and any difference between them is therefore the gate's TIMING rather "
        "than its cost. If instead the monthly arms do separate on turnover, something in this "
        "book interacts with the band that SPY alone and M0101's book did not, and that itself is "
        "the finding. Fifth, the dev window holds exactly TWO crashes, and the whole of the band's "
        "measured advantage comes from holding each of them as one exit instead of fragmenting it "
        "and buying back inside the fall. Two is not a sample; both of this window's crashes "
        "happened to be slow, and a fast crash is what 1987 and 2020 were. Nothing measured on "
        "dev can settle that, the folds are the only within-window check, and no test-window look "
        "is spent here. Sixth, the host book's own recorded worst fall is 23.80%, over the "
        "real-money bar already, so no arm is expected to clear every go-live condition and the "
        "band is not being asked to fix that. Finally, as in every switch method the lab has run: "
        "interest on the cash held while the gate is off is not modelled, which flatters SPY and "
        "penalises every gated arm equally, so each gap reported is an upper bound on the gate's "
        "cost and the paired differences are unaffected."
    ),
    candidates=(
        _v("M-B0", Decimal(0), MONTHLY_HOLD_FRAC_GOTRADE,
           "The dose-response ladder's zero rung and the paired bare gate: M0072-Z2-RAWRANK's own "
           "book behind its own unchanged 200-day switch, read monthly"),
        _v("M-B15", B15, MONTHLY_HOLD_FRAC_GOTRADE,
           "First rung of the dose-response ladder: leave 1.5% under the 200-day average, return "
           "1.5% over, read monthly"),
        _v("M-B30", B30, MONTHLY_HOLD_FRAC_GOTRADE,
           "Middle rung of the dose-response ladder and the idea itself: leave 3% under the "
           "average, return 3% over, read monthly"),
        _v("M-B60", B60, MONTHLY_HOLD_FRAC_GOTRADE,
           "Top rung of the dose-response ladder: leave 6% under the average, return 6% over, "
           "read monthly"),
        _v("W-B0", Decimal(0), WEEKLY_HOLD_FRAC_GOTRADE,
           "The same book and the same bare 200-day switch read WEEKLY: the cadence axis, and the "
           "weekly pair's own zero dose"),
        _v("W-B30", B30, WEEKLY_HOLD_FRAC_GOTRADE,
           "The same 3% band read WEEKLY: with the three arms above, the difference-in-differences "
           "whose sign was written down before the run"),
    ),
    seen_keys=(
        "concept:gate-cadence-dose-response",
        "concept:banded-gate-on-an-event-book",
    ),
)
