"""M0266 — Split the drift trigger's gain: is it the cash it releases, or the trimming itself?

Source: variation of M0127, which measured the gain and said plainly that it could not split it.
M0109 supplies the deliberately neutral 50-name base book. Insight 479 prices the other channel
(how the money is arranged, on identical names and identical trades) at about 1.25 points a year.
Insight 481 forbids calling an unsplit margin a floor in either direction, which is why this file
exists rather than a sentence in someone's analysis.

WHAT M0127 FOUND AND WHAT IT COULD NOT SAY. Moving the rebalance band from 1% of the whole account
to a share of the holding's own target was worth +0.49 points a year of the owner's money-weighted
return on a book whose picks are byte-identical across every arm (+0.9 points a year over
2009-2015), for +0.11 points a year in fees and 2.4 points of deeper worst fall. But the ladder
moved TWO things at once and they are welded together by construction:

  * THE CASH CHANNEL. Under the old band a deposit could buy a brand-new holding but could never
    top up an existing one, so the account carried cash it never chose to hold. Average exposure
    rose 88.65% -> 93.38% -> 96.21% -> 97.82% -> 98.57% across the five rungs. More of the money
    was in the market, and over a window in which the market rose, that alone pays.
  * THE TRIMMING CHANNEL. The same tightening is what first lets the book genuinely trim a winner
    back to its slot and feed the proceeds to a laggard. That is a different thing from being
    more invested, and insight 479 says it is worth real money on its own.

A rung that releases cash is a rung that starts trimming. M0127's verdict quoted the joint number
and refused to attribute it, and this method is the attribution.

THE DESIGN, AND THE ONE THING THAT MAKES IT MEAN ANYTHING. Hold EXPOSURE FIXED on both sides of
the comparison, so the only surviving difference is the trimming. The allocator is M0127's --
M0109's unbraked base book, the 50 most-traded index members at equal weight, no gate, no brake,
no stock picking of any kind -- with exactly one field added: a ``scale`` that multiplies every
target weight. A scaled-down book deliberately holds cash, which is how a tight-band arm is
brought back down to the loose-band arm's exposure.

  THE CALIBRATION IS PRE-REGISTERED AND READS NO RETURN. The scale for a band is

      scale(band) = exposure(M0127-E1) / exposure(M0127's arm at that band, unscaled)

  and nothing else. Both inputs are AVERAGE EXPOSURE figures recorded in the lab on 2026-10-20 by
  M0127's own five trials (rows 875-879), on the same store, on the same book, before this method
  existed. No return, no CAGR, no drawdown and no fee bill enters the formula. With
  ``exposure(E1) = 0.8864578387709499``:

      band 0   (full monthly rebalance): 0.8864578387709499 / 0.9856884609713539 = 0.899329
      band 20% of the holding's target:  0.8864578387709499 / 0.9620748336905275 = 0.921402

  Those two numbers are frozen here, in the file, before the run. The weight each name is held at
  is ``scale / 50`` FLOORED to the engine's millionth (0.017986 and 0.018428), so the realised
  target sums are 0.899300 and 0.921400 and the PREDICTED average exposures are 0.886430 and
  0.886456 against the control's 0.886458 -- agreement to three thousandths of a point on paper. The analysis must verify the
  REALISED exposures agree to within half a point and, if they do not, must report the residual
  gap and REFUSE to publish a split rather than quote one. Tuning the scale after seeing a return
  would fit the experiment and make the whole method worthless; that is why it is written down
  here, in the pre-registration commit, and why no arm's scale may move afterwards.

THE SIX ARMS. Two matched pairs, two unmatched reproductions and one ruler.

  * ``L``     -- loose band (``resize_basis="equity"``, 1% of the whole account, which at fifty
                 equal slots is half a holding and fires in one holding-month in a thousand),
                 scale 1. The control, and economically M0127-E1. Its numbers should reproduce
                 trial 875's; that reproduction is the proof the added ``scale`` field changed
                 nothing when it is 1, and it is re-run here rather than cited because a ratio
                 drawn across two sweeps is not a comparison (insight 482).
  * ``T00``   -- band 0, every holding traded back to its slot on every month start, scale 1.
                 Economically M0127-T00. The UNSPLIT margin, re-measured inside this sweep so
                 that both halves of every ratio below come from one run on one store.
  * ``T00M``  -- band 0, scale 0.899329. THE TREATMENT: trims exactly as ``T00`` does, but holds
                 the same share of its money in the market as ``L``. ``T00M`` minus ``L`` is the
                 trimming channel with the cash channel closed.
  * ``T20``   -- band 20% of the holding's own target (the tape the lab adopted on 2026-10-12),
                 scale 1. Economically M0127-T20.
  * ``T20M``  -- band 20% of target, scale 0.921402. THE SECOND TREATMENT, matched the same way,
                 on the rule the lab actually runs rather than on the textbook extreme.
  * ``LS``    -- loose band, scale 0.899329. THE RULER, and the reason this method can check its
                 own arithmetic. It trims exactly as little as ``L`` does -- the equity-basis band
                 is 1% of the account whatever the slot is scaled to, and it already fires in one
                 holding-month in a thousand -- while sitting about 8.9 points lower in the
                 market. ``L`` minus ``LS``, divided by the exposure gap between them, is the
                 price of a point of exposure ON THIS BOOK with the trimming held still. Multiply
                 that slope by the 9.92-point exposure gap M0127's ladder spanned and you get an
                 INDEPENDENT estimate of the cash channel; subtract it from +0.49 and you get an
                 independent estimate of the trimming. Two routes to one split, and they are
                 allowed to disagree. If they do, the analysis says so.

WHAT THE ARMS DO NOT SEPARATE, stated now so it cannot be claimed later. The two matched arms
agree on AVERAGE exposure, not on the PATH of their cash. ``L``'s idle money is drifting cash that
accumulates from deposits it cannot deploy and is spent whenever the dollar-volume ranking hands
it a new name; ``T00M``'s is a deliberate, near-constant 10% buffer re-set every month. Two books
can average the same exposure and still have been differently invested in 2008. That residual is
a caveat on the number, not a flaw in it, and the analysis must carry it.

WHAT IS PREDICTED, IN NUMBERS, BEFORE ANY RESULT.

 1. THE MATCH HOLDS. ``L``, ``T00M`` and ``T20M`` all land within half a point of 88.6% average
    exposure. This is the precondition; if it fails, there is no split to report.
 2. THE REPRODUCTIONS ARE EXACT. ``L`` reproduces trial 875 and ``T00`` trial 879 to the digit
    (same store fingerprint, same book, same rules, scale 1 is a no-op). A mismatch is a bug in
    the scaling, not a finding, and must be chased before anything else is read.
 3. THE SPLIT. The honest prior is that MOST of M0127's +0.49 was cash. A book that is 9.92 points
    more invested over a window in which the equal-weight most-traded book compounded at 32% a
    year is getting paid for being invested, and that is not a subtle effect. The pre-registered
    expectation is that ``T00M`` beats ``L`` by somewhere between 0.0 and +0.2 points a year of
    money-weighted return -- that is, the trimming is worth a fraction of the joint number and
    possibly nothing at all. If ``T00M`` LOSES to ``L``, that is also a result and it is a clean
    one: trimming winners to feed laggards costs money on a book of large momentum-heavy names,
    and the whole of M0127's gain was cash plus a bit.
 4. INSIGHT 479 IS NOT EXPECTED TO BE CONFIRMED AT 1.25 POINTS. That number came from two books
    with DIFFERENT target weights (equal-weight against size-weighted) on identical names; this
    one holds the target weights identical and moves only whether the book is pushed back to them.
    They are different questions wearing the same word, and if ``T00M`` minus ``L`` comes out near
    zero, the correct reading is NOT that 479 was wrong but that re-imposing a slot you already
    chose is a much smaller thing than choosing a different slot.
 5. FEES EAT INTO IT. ``T00M`` trades about 18% more money a year than ``L`` and pays Gotrade's
    per-order minimum on every drift trade. At a $26 slot a 20% drift is a $5 order. So the
    trimming channel's GROSS worth is larger than whatever ``T00M`` minus ``L`` shows, and the
    analysis must quote turnover beside return so the two can be told apart.
 6. THE FALL GETS DEEPER, NOT SHALLOWER. M0127 found trimming cost 2.4 points of worst fall
    because rebalancing keeps buying whatever is falling. With exposure matched, ``T00M`` should
    still fall further than ``L`` and the gap should now be attributable to the buying-the-faller
    behaviour alone rather than to being more invested. That is the single most useful by-product
    of closing the cash channel.
 7. NO ARM IS A CANDIDATE AND NONE IS BEING PURSUED AS ONE. The base book loses to a
    deposit-matched SPY and falls 57%, more than twice the owner's 25% limit. Eligibility here
    would be a surprise, would be reported, and would still not be promoted: the ``scale`` field
    and the band rungs are one-off rule sets and params with no preset, so they are unpromotable
    by construction. This is a ruler.

TRAPS ON THIS HOST, ALL PREVIOUSLY MEASURED, AND HOW THIS FILE AVOIDS THEM.

  * TRADE COUNT IS A DEAD METER HERE. M0127's five arms recorded an IDENTICAL 1338 trades while
    their idle cash moved from 11.4% to 1.4%. The resize legs are folded into the ranking's own
    orders, so the trade counter cannot see them. Read EXPOSURE and TURNOVER; a partial-weight arm
    can record trades 0 and still be acting.
  * A CONTROL MATCHED ON TRADES AND TURNOVER IS STILL NOT RETURN-NEUTRAL (479). Matching exposure
    is one more axis, not a guarantee of neutrality, and the claim made here is narrow by design:
    "the same book, the same names, the same dates, the same average exposure, differing only in
    whether holdings are pushed back to their slots".
  * EVERY WIDE-VERSUS-NARROW COMPARISON DRAWN BEFORE 2026-10-12 WAS PARTLY MEASURING THE TRIGGER,
    so none is cited as a prior here.
  * THE BAND LEVER IS ``TradeRules.resize_band`` (added 2026-10-20 through the post-pins
    ``LEVERS_SINCE_PINS`` path, ``None`` meaning the basis's own constant). It is reused, not
    duplicated, and the two band rungs below are M0127's own rule-set objects imported rather than
    re-declared, so the two methods can never drift apart.
  * SURVIVORSHIP. The dev store prices no delisted names, and a rebalancing rule buys fallers, so
    the trimming arms are structurally flattered by the dead companies' absence. The widest arm is
    to be survivorship-checked and the result quoted beside the dev column.

Every piece reads only bars dated <= d.
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
from seer_engine.lab.methods.m0109_book_drawdown_brake import (
    BrakeParams,
    book_rows,
    book_targets,
    prepared_rows,
)
from seer_engine.lab.methods.m0127_slot_relative_resize_band import E1, T00, T20
from seer_engine.sim.book import Target
from seer_engine.sim.rules import TradeRules
from seer_engine.strategies.allocator import scale_weight
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import DV_N, FactorPrepared, prepare_factor

ADDED = date(2026, 10, 21)

# --------------------------------------------------------------------------- the calibration
#
# Average exposure as M0127's trials recorded it on 2026-10-20 (lab rows 875, 877, 879), on this
# store, on this book. These are the ONLY inputs to the scales below: no return, no drawdown, no
# fee bill. They are copied here verbatim so the arithmetic is auditable from the file alone.
EXPOSURE_E1 = Decimal("0.8864578387709499")  # row 875, the loose equity-basis band
EXPOSURE_T20 = Decimal("0.9620748336905275")  # row 877, band 20% of the holding's own target
EXPOSURE_T00 = Decimal("0.9856884609713539")  # row 879, band 0, the full monthly rebalance

#: The scale that brings a tight-band arm back down to the loose arm's average exposure.
#: ``EXPOSURE_E1 / EXPOSURE_T00``, rounded to the engine's millionth: 0.899329.
SCALE_T00 = Decimal("0.899329")
#: ``EXPOSURE_E1 / EXPOSURE_T20``, rounded the same way: 0.921402.
SCALE_T20 = Decimal("0.921402")
#: The ruler's scale. Deliberately the SAME number as ``SCALE_T00`` rather than a third value, so
#: that ``L`` -> ``LS`` and ``T00`` -> ``T00M`` are the identical downward step applied to two
#: different bands, and the two differences can be read against each other.
SCALE_RULER = SCALE_T00


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class ScaledBandParams:
    """M0127's screen and size, plus the one field this method adds: a target-weight ``scale``.

    The band itself is a rule-set lever and never a param, exactly as in M0127: that is what keeps
    the two axes orthogonal, so an arm's band and its scale can be varied independently and the
    allocator cannot possibly behave differently between two arms that share a params value.

    ``scale`` multiplies every target weight. At 1 the book asks to be fully invested and the
    allocator is M0127's byte for byte; below 1 the book deliberately holds ``1 - scale`` of its
    equity in cash, which is the only mechanism available for lowering a tight-band arm's exposure
    without touching its band, its names, its dates or its cadence.
    """

    top: int = 50
    min_dollar_volume: float = 20_000_000.0  # 20-session mean close x volume > this (strict)
    min_price: float = 5.0  # close >= this
    scale: Decimal = Decimal(1)  # every target weight is multiplied by this; (0, 1]

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 200:
            raise ValueError(f"top must be an int in 1..200, got {self.top!r}")
        for name in ("min_dollar_volume", "min_price"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise TypeError(f"{name} must be a float, got {type(v).__name__}")
            v = float(v)
            if v != v or v in (float("inf"), float("-inf")) or v < 0.0:
                raise ValueError(f"{name} must be finite and >= 0, got {v!r}")
            object.__setattr__(self, name, v)
        if not isinstance(self.scale, Decimal) or not self.scale.is_finite():
            raise TypeError(f"scale must be a Decimal, got {self.scale!r}")
        if not 0 < self.scale <= 1:
            raise ValueError(f"scale must be a Decimal in (0, 1], got {self.scale}")

    def as_dict(self) -> dict[str, str]:
        return {
            "top": str(self.top),
            "min_dollar_volume": format(Decimal(repr(self.min_dollar_volume)).normalize(), "f"),
            "min_price": format(Decimal(repr(self.min_price)).normalize(), "f"),
            "scale": str(self.scale),
        }

    def as_brake(self) -> BrakeParams:
        """The same screen as M0109's params with its brake switched off (``taper=None``).

        Reused rather than re-typed, exactly as M0127 does it: one definition of the base book, so
        the three methods that measure on it cannot drift apart.
        """
        return BrakeParams(
            top=self.top,
            min_dollar_volume=self.min_dollar_volume,
            min_price=self.min_price,
            taper=None,
        )


def _check(params: object) -> ScaledBandParams:
    if not isinstance(params, ScaledBandParams):
        raise TypeError(f"params must be ScaledBandParams, got {type(params).__name__}")
    return params


def _scaled(targets: tuple[Target, ...], scale: Decimal) -> tuple[Target, ...]:
    """Every target's weight multiplied by ``scale``; a weight that floors to zero is dropped.

    ``scale_weight`` is the engine's own helper (the drawdown brake in M0109 uses it), so the
    rounding here is the rounding every other partial-weight book in the lab uses: floored to the
    weight quantum, a millionth. At ``scale = 1`` it is the identity on every weight that is
    already a legal weight, which is what makes the control arms exact reproductions.
    """
    if scale == 1:
        return targets
    out: list[Target] = []
    for t in targets:
        w = scale_weight(t.weight, scale)
        if w is None:
            continue
        out.append(Target(symbol=t.symbol, weight=w, last=t.last))
    return tuple(out)


# --------------------------------------------------------------------------- the allocator


class ScaledMostTradedEqualWeight:
    """The ``top`` most-traded index members at ``scale``/``top`` each. No gate, no brake, no memory.

    ``held`` is ignored on purpose, exactly as in M0127: every rank session is a fresh top set, so
    two arms on the same date receive identical symbols at identical weights whenever they share a
    ``scale``, whatever either of them is holding. That is what leaves the band -- and only the
    band -- as the difference inside a matched pair.
    """

    id = "M0266"

    def lookback(self, params: Any) -> int:
        _check(params)
        return DV_N  # the screen's 20-session mean dollar volume is the deepest thing it reads

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        q = _check(params)
        p = q.as_brake()
        return _scaled(book_targets(book_rows(history, members, data_date, p), p), q.scale)

    def prepare(self, history: Mapping[str, History]) -> FactorPrepared:
        return prepare_factor(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, FactorPrepared):
            raise TypeError(f"prepared must be FactorPrepared, got {type(prepared).__name__}")
        q = _check(params)
        p = q.as_brake()
        return _scaled(book_targets(prepared_rows(prepared, members, data_date, p), p), q.scale)


BOOK = ScaledMostTradedEqualWeight()


# --------------------------------------------------------------------------- the arms

#: M0127's own rule-set objects, imported rather than re-declared so the band rungs of the two
#: methods can never drift apart. ``E1`` is the loose equity-basis band (1% of the whole account),
#: ``T20`` the adopted 20%-of-target tape, ``T00`` the band of 0 that rebalances every month start.
LOOSE: TradeRules = E1
TIGHT20: TradeRules = T20
TIGHT00: TradeRules = T00


def _v(suffix: str, rules: TradeRules, scale: Decimal, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0266-{suffix}",
        family="M0266",
        rules=rules,
        allocator=BOOK,
        params=ScaledBandParams(scale=scale),
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0266",
    name="Split the drift trigger's gain: is it the cash it releases, or the trimming itself?",
    family="portfolio-rebalancing",
    source_kind="variation",
    source_ref=(
        "M0127, which measured +0.49 points a year of money-weighted return from moving the "
        "rebalance band off the account and onto the holding and said plainly that it could not "
        "split that gain between the cash it released and the trimming it enabled; M0109 for the "
        "neutral 50-name base book; insight 479 for the 1.25 points a year the weighting "
        "arrangement was worth on identical names and identical trades; insight 481 for the rule "
        "that an unsplit margin may not be called a floor in either direction"
    ),
    parent_id="M0127",
    hypothesis=(
        "M0127 measured that moving the rebalance band from 1 percent of the account to a share "
        "of the holding is worth +0.49 points a year of money-weighted return on a 50-name book "
        "whose picks are identical across every arm, and it could NOT say how much of that was "
        "which of two channels, because they move together: average exposure rose 88.65 to 98.57 "
        "percent across the ladder AND the book began genuinely trimming winners to feed laggards "
        "at the same time. This method separates them by holding exposure FIXED on both sides. On "
        "M0127's own allocator -- M0109's unbraked 50 most-traded index members at equal weight, "
        "no gate, no brake, no stock picking -- with one field added, a scale that multiplies "
        "every target weight so that a book may deliberately hold cash, six arms run in ONE sweep "
        "on ONE store: the loose equity-basis band at scale 1 (the control, economically "
        "M0127-E1), the band of 0 at scale 1 (economically M0127-T00, the unsplit margin "
        "re-measured inside this sweep), the band of 0 at the calibrated scale (the treatment), "
        "the 20-percent-of-target band at scale 1 and at its own calibrated scale (the second "
        "matched pair, on the rule the lab actually runs), and the loose band at the same "
        "calibrated scale as the treatment (the ruler, which moves exposure about 8.9 points with "
        "the trimming held still and so prices a point of exposure on this book directly). THE "
        "CALIBRATION IS PRE-REGISTERED AND READS NO RETURN: scale equals the recorded average "
        "exposure of M0127-E1 divided by the recorded average exposure of M0127's arm at that "
        "band, both from trials run on 2026-10-20 on this store, giving 0.899329 at band 0 and "
        "0.921402 at the 20-percent band, which after the engine floors each name's weight to a "
        "millionth predict average exposures of 0.886430 and 0.886456 against the control's "
        "0.886458. PREDICTIONS, written now. (1) The match holds: "
        "the control and both matched arms land within half a point of 88.6 percent average "
        "exposure. (2) The two scale-1 arms reproduce M0127's rows 875 and 879 to the digit; a "
        "mismatch is a bug in the scaling and must be chased before anything is read. (3) Most of "
        "the +0.49 was cash: the matched treatment is expected to beat the control by between 0.0 "
        "and +0.2 points a year, and a LOSS is an equally clean result meaning trimming winners "
        "to feed laggards costs money on a book of large momentum-heavy names. (4) Insight 479's "
        "1.25 points is not expected to be confirmed here, because that number compared two "
        "DIFFERENT target weightings while this holds the target weights identical and moves only "
        "whether the book is pushed back to them. (5) The trimming arm trades about 18 percent "
        "more money a year and pays Gotrade's per-order minimum on every drift trade, so its "
        "gross worth exceeds whatever the net difference shows and turnover must be quoted beside "
        "return. (6) With exposure matched the trimming arm should still fall further than the "
        "control, and that gap is now attributable to buying the faller rather than to being more "
        "invested. (7) No arm is a candidate: the base book loses to a deposit-matched SPY and "
        "falls 57 percent, and the scale field and band rungs have no preset, so every arm is "
        "unpromotable by construction. Fractional shares, Gotrade's real fees, the owner's "
        "funding plan. Success is a measurement, not a candidate."
    ),
    expected_failure=(
        "The likeliest failure is that the exposure match does not hold. A band and a weight scale "
        "both move exposure and they interact, so the calibration may land an arm a point or two "
        "off the control, in which case the analysis must report the residual exposure gap and "
        "REFUSE to publish a split rather than quote one. The second is that the two arms earn "
        "the same within noise. That is not a failure of the method but it IS the outcome being "
        "pre-registered as acceptable: if the matched treatment and the control land on top of "
        "each other, the whole of M0127's gain was cash and the trimming is worth nothing on this "
        "book, which is a real and publishable result and must be stated as such rather than "
        "dressed up as a near miss. The third is that the two routes to the split disagree -- the "
        "direct matched difference and the ruler's exposure slope multiplied by M0127's 9.92-point "
        "exposure gap -- in which case neither number may be quoted as the answer and the "
        "disagreement itself is the finding, because it would mean the return is not linear in "
        "exposure on this book and every exposure-matched control the lab draws in future needs a "
        "wider tolerance. The fourth is paths: the two matched arms agree on AVERAGE exposure but "
        "not on the shape of their cash -- the control's idle money is drifting cash it cannot "
        "deploy, the treatment's is a deliberate near-constant buffer re-set monthly -- so two "
        "books can average the same exposure and still have been differently invested in 2008, "
        "and that residual is a caveat the analysis must carry rather than hide. The fifth is "
        "survivorship: the dev store prices no delisted names and a rebalancing rule buys "
        "fallers, so the trimming arms are structurally flattered by the dead companies' absence "
        "and the widest arm must be survivorship-checked with the result quoted beside the dev "
        "column. The sixth is that the whole difference turns out to be the per-order minimum fee "
        "on tiny drift trades, in which case this is a measurement of a 20,000,000 IDR account's "
        "order economics rather than of rebalancing, and the verdict must say so."
    ),
    candidates=(
        _v("L", LOOSE, Decimal(1),
           "Control: the loose 1%-of-account band at full weight, economically M0127-E1"),
        _v("T00", TIGHT00, Decimal(1),
           "The unsplit margin re-measured in this sweep: full monthly rebalance at full weight"),
        _v("T00M", TIGHT00, SCALE_T00,
           "THE TREATMENT: full monthly rebalance, scaled to the control's own average exposure"),
        _v("T20", TIGHT20, Decimal(1),
           "The adopted 20%-of-target tape at full weight, economically M0127-T20"),
        _v("T20M", TIGHT20, SCALE_T20,
           "THE SECOND TREATMENT: the adopted tape, scaled to the control's average exposure"),
        _v("LS", LOOSE, SCALE_RULER,
           "THE RULER: the control's band at the treatment's scale, pricing a point of exposure"),
    ),
    seen_keys=(
        "concept:exposure-matched-rebalance-split",
        "concept:price-of-a-point-of-exposure",
    ),
)
