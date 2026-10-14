"""M0149 — The asymmetry book kept invested, braked by its own falling account instead of the
market's trend.

Source: a variation of M0133. Its ungated arm, ``M0133-N40``, is the one book this lab holds that
is both *profitable* and *behaviourally free*: the up/down participation spread over 40 equal
slots with the market switch OFF earns +9.6% a year on the owner's deposits against SPY TR's
+7.2%, and its residual correlation against the four test-failed books reads 0.5717
(M0002-REL-85), 0.3524 (M0021-B70-RAW), 0.3625 (M0022-W-TV14) and 0.3341 (M0029-B70-RAW-FRAC),
measured on its own curve 2026-10-14 -- far under the 0.85 kin bar, where its gated sibling
``M0133-G40`` reads 0.8964 and is refused. Its only defect is the size of the fall: 69.1% peak to
trough, 2008 at -51.4%, against a 50% dev screen and the owner's 25% real-money bar.

WHY THE GATE CANNOT BE THE ANSWER. The obvious fix -- put the SPY 200-day switch back in front of
it -- is the fix that closed M0133. The lab's own measurement of that switch is that it earns its
whole twenty-year advantage in 2001, 2002 and 2008: it puts a book in cash in the same handful of
months every *other* book in this lab is in cash, because every other book reads the same market.
Hard-gate rule (D14) measures exactly that -- a method's monthly returns, de-funded and less its
own fit on SPY's, correlated against a test-failed book's -- and refuses on it. A market-reading
brake therefore buys a smaller fall with a refusal. This method asks whether a brake that reads
the BOOK can buy the same fall without one.

THE TWO BRAKES, both already implemented in this lab and imported rather than re-derived:

* **the own-drawdown brake** (M0109). Exposure is ``1 - dd / taper``, clipped into
  ``[floor, 1]`` and rounded to the nearest 0.05, where ``dd`` is how far the book sits below its
  own trailing 252-session high: full exposure at the high, all cash by the time it is down
  ``taper``, a straight line between. ``M0109.exposure`` and ``M0109.braked`` are imported whole.
* **the own-volatility target** (M0001/M0002). Every weight is multiplied by
  ``min(1, target_vol / the basket's own annualized 63-day volatility)``. ``M0001.basket_scale``
  is imported whole. It is one-sided: it de-risks and never levers.

Neither reads a price of SPY's, a breadth count or a term structure. Both de-risk on a schedule
set by this book's own path, which is the schedule the failed books do not share -- that is the
whole hypothesis, and D14 is what will judge it.

THE SHADOW, and the ratchet it exists to avoid. An allocator sees bars, members, the data date and
what the book holds; it never sees the account's equity curve, so "how far is this book below its
own high" must be rebuilt from bars. ``shadow_of`` rebuilds it the way M0109 does: re-pick THIS
book -- the ungated 40-name asymmetry rank -- at every month-end mark of SPY's calendar and chain
the equal-weight baskets day by day. Four things about that reconstruction, because they are what
could fool us:

  * It is the UNBRAKED book, deliberately, and this is the single most important decision in the
    method. A brake that reads its own BRAKED account is a ratchet: once trimmed, the account
    stops falling, so its drawdown stops recovering and the exposure never comes back. Here that
    failure would be total -- the brake would cut in 2008 and then hold a cash account, which has
    no drawdown to recover from, straight through 2009-2015, which is the stretch this ranking
    exists to capture. Reading the unbraked shadow asks the question the brake actually wants
    answered -- "how far is this kind of book below its high" -- and re-enters when the book's
    own kind of names recover rather than when the trimmed account does.
  * It is MEMBERSHIP-FREE. Point-in-time membership reaches an allocator only through
    ``prepare_market``, which this method does not use, so the shadow ranks every symbol in the
    store's price history except ``f_factor.EXCLUDED``. Those symbols ARE the index members, past
    and present; where the shadow and the book differ, the shadow is slightly broader. It is a
    signal, not an accounting.
  * It is GROSS: no fees, no deposits, no cash drag, no dividends. A deposit-funded account's own
    high is lifted by every top-up, which would make a brake read off the real account bite more
    often than any backtest suggests. A gross index removes that entirely and means the same brake
    reads the same way at any account size.
  * The running high is TRAILING over ``peak_n`` sessions, never since inception, and it needs
    ``WARM`` sessions of calendar before the brake may act at all. Both numbers are M0109's,
    imported and NOT re-calibrated here: M0109 measured on this store that a three-year high holds
    the 2000 top against a book all through 2003-2007 and the 2007 top through 2010-2015, so a
    longer window would be guaranteed to lose the best-covered years before the run began. Where
    the ``WARM`` depth is absent the brake stands down and the variant IS its control -- a hard
    on/off on a fixed session count, never a shortened window, so the P4 identity holds either way.

THE TAPE, and why it is not the parent's. ``M0133-N40`` ran on ``monthly-hold-frac-gotrade``, where
the rebalance band is 1% of the WHOLE account. At 40 names a slot is 2.5% of equity, so a trim is
executed only once exposure falls to 0.60 or below and every exposure between 0.65 and 1.00 is
computed and then never traded -- the dial would silently become a switch, and a null result would
not be readable. This method runs on ``monthly-hold-frac-gotrade-tband``, where the band is 20% of
the holding's OWN target, so the dial executes as a dial with a declared 20% deadband. Everything
else about the tape is the parent's: monthly, fractional shares, Gotrade's real fees, the owner's
real deposits. ``N40-RAW`` is the paired in-lab control on that same tape with both brakes off, so
the five braked arms are read against a yardstick that pays the same trading costs; it also prices
the tape change on this book, which ``M0133-N40``'s recorded turnover of 5.66 and exposure of 0.972
say should be small.

IDLE CASH EARNS NOTHING here. The cash-crediting tape raises the owner input ``cash-yield`` (that
Gotrade pays interest on idle dollars is not verified) and paper refuses it. A braked book holds a
great deal of cash, so every braked return below is a FLOOR, not an estimate.

Assumptions, written before the run:

- The idea named five arms (drawdown cuts at 15% and 25%, own vol at 14% and 16%, and both). The
  sixth slot goes to the in-lab control rather than to a sixth dial, for the tape reason above.
  Under ``DSR_POLICY = "methods"`` a sixth variant costs the lab nothing in N, so the control is
  free and the comparison is airtight instead of nearly so.
- The combined arm pairs the GENTLER drawdown taper with the TIGHTER vol target (``DD25-TV14``)
  rather than stacking two aggressive dials. The arm's question is whether the two brakes de-risk
  on different occasions or the same ones; two maximal dials would answer only "yes, a book held
  mostly in cash falls less".
- The drawdown dial is stepped to the nearest 0.05 because M0109's ``exposure`` is and it is
  imported unchanged; the volatility dial is not stepped because M0001's ``basket_scale`` is not.
  Both are the lab's existing implementations, run as they stand. The tape's 20% deadband is the
  anti-churn device here, and adding a second, undeclared one would be a dial invented after the
  fact.
- ``book.gate`` must be ``"none"``: the method's whole claim is that it reads no market switch, so
  a gated configuration is refused by the params type rather than left to care.
- ``M0109.exposure`` and ``M0109.shadow_drawdown`` read only ``taper``, ``floor`` and ``peak_n``
  from the params they are handed. ``AccountBrakeParams`` carries those three under exactly those
  names, so M0109's implementations run on it unchanged and there is one definition of the dial in
  the lab rather than two. M0109's file is frozen against its recorded sha, so the coupling cannot
  drift.
- Only free functions are imported from the brake and vol-scaling methods; no other method's
  allocator object is ever nested in these params. A nested allocator is written into
  ``config_text`` as ``<MNNNN>`` and makes that method an INGREDIENT (hard gate D12), dragging in
  its family and ancestors -- and M0001's family, ``stock-momentum-risk-managed``, is the
  test-failed M0002's family. Composing it would have refused this method on kin before a single
  number was measured.
- Participation, screen, weighting and pricing are the parent's exactly: ``ASYM.targets`` is
  called with ``AsymParams(N40, gate="none")``, the literal params of ``M0133-N40``, so the brake
  is the only difference between this method and its parent by construction.
- Reads only bars dated <= ``data_date``. Pure: no clock, no I/O, no randomness.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0001_momentum_own_vol_scaling import (
    basket_scale,  # M0001's own-vol dial, the free function only: never its allocator (D12)
)
from seer_engine.lab.methods.m0007_residual_momentum import ReturnGrid, build_grid
from seer_engine.lab.methods.m0109_book_drawdown_brake import (
    braked,
    exposure,
    shadow_drawdown,
    shadow_wealth,
)
from seer_engine.lab.methods.m0110_downside_participation import targets_from_scores
from seer_engine.lab.methods.m0133_gated_updown_asymmetry import (
    ASYM,
    N40,
    AsymParams,
    asym_scores,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorRow, factor_rows

ADDED = date(2026, 10, 14)

#: The book every variant brakes: M0133-N40's params exactly -- the up/down participation spread
#: over 40 equal slots, F4's screen, and NO market switch.
BOOK = AsymParams(N40, gate="none")


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class AccountBrakeParams:
    """``book`` is the unbraked book; the rest is the two brakes that read it and nothing else.

    ``taper``/``floor``/``peak_n`` carry M0109's names because M0109's ``exposure`` and
    ``shadow_drawdown`` are handed this object and read exactly those three attributes.
    ``taper=None`` and ``target_vol=None`` together are the control: full exposure, always.
    """

    book: AsymParams
    taper: Decimal | None = None  # shadow drawdown at which exposure reaches `floor`; None = off
    floor: Decimal = Decimal("0")  # the least exposure the taper reaches
    peak_n: int = 252  # sessions the shadow's running high is taken over (about one year)
    target_vol: Decimal | None = None  # annualized own-vol target; None = off
    vol_n: int = 63  # daily returns in the volatility estimate (63 = one quarter)

    def __post_init__(self) -> None:
        if not isinstance(self.book, AsymParams):
            raise TypeError(f"book must be AsymParams, got {type(self.book).__name__}")
        if self.book.gate != "none":
            raise ValueError(
                f"book.gate must be 'none': M0149 brakes on the account, never on the market, "
                f"got {self.book.gate!r}"
            )
        if self.taper is not None:
            if not isinstance(self.taper, Decimal) or not self.taper.is_finite():
                raise TypeError(f"taper must be None or a Decimal, got {self.taper!r}")
            if not 0 < self.taper <= 1:
                raise ValueError(f"taper must be in (0, 1], got {self.taper}")
        if not isinstance(self.floor, Decimal) or not self.floor.is_finite():
            raise TypeError(f"floor must be a Decimal, got {self.floor!r}")
        if not 0 <= self.floor < 1:
            raise ValueError(f"floor must be a Decimal in [0, 1), got {self.floor}")
        if isinstance(self.peak_n, bool) or not isinstance(self.peak_n, int) or self.peak_n < 20:
            raise ValueError(f"peak_n must be an int >= 20, got {self.peak_n!r}")
        if self.target_vol is not None:
            if not isinstance(self.target_vol, Decimal) or not self.target_vol.is_finite():
                raise TypeError(f"target_vol must be None or a Decimal, got {self.target_vol!r}")
            if self.target_vol <= 0:
                raise ValueError(f"target_vol must be > 0, got {self.target_vol}")
        if isinstance(self.vol_n, bool) or not isinstance(self.vol_n, int) or self.vol_n < 20:
            raise ValueError(f"vol_n must be an int >= 20, got {self.vol_n!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "taper": "none" if self.taper is None else str(self.taper),
            "floor": str(self.floor),
            "peak_n": str(self.peak_n),
            "target_vol": "none" if self.target_vol is None else str(self.target_vol),
            "vol_n": str(self.vol_n),
        }
        for key, v in self.book.as_dict().items():
            out[f"book.{key}"] = v
        return out


def _check(params: object) -> AccountBrakeParams:
    if not isinstance(params, AccountBrakeParams):
        raise TypeError(f"params must be AccountBrakeParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the shadow


def shadow_of(
    rows_at: Callable[[date], list[FactorRow]], grid: ReturnGrid, book: AsymParams
) -> np.ndarray:
    """The UNBRAKED asymmetry book's gross wealth index over ``grid.dates``, starting at 1.0.

    ``rows_at`` yields the screened rows at a date (``factor_rows`` on the single-window path,
    ``FactorPrepared.rows_on`` on the prepared one), so both paths share this one function and
    cannot disagree. The picks are taken through ``targets_from_scores`` -- M0110's selection, the
    same call the real book makes -- rather than by re-sorting the scores here, so the shadow's
    basket and the book's basket can never drift apart on a tie-break or a coverage floor.

    ``shadow_wealth`` is M0109's: it re-picks at every month-end mark and chains the equal-weight
    baskets. Entry t depends only on marks before t and returns at or before t, so the entries at
    or before any date d are the same whether the grid was built from the whole history or from
    history cut at d -- which is what makes the P4 identity hold with the brake live.
    """

    def picks_at(d: date) -> tuple[str, ...]:
        rows = rows_at(d)
        if not rows:
            return ()
        scores = asym_scores(grid, [r.symbol for r in rows], d, book)
        return tuple(t.symbol for t in targets_from_scores(rows, scores, book))

    return shadow_wealth(grid, picks_at)


def account_share(
    history: Mapping[str, History],
    grid: ReturnGrid | None,
    wealth: np.ndarray | None,
    base: tuple[Target, ...],
    data_date: date,
    p: AccountBrakeParams,
) -> Decimal:
    """The share of the account both brakes together allow at ``data_date``.

    The drawdown dial is M0109's ``exposure`` of M0109's ``shadow_drawdown`` (1 when ``taper`` is
    None, when the shadow is unmeasurable, or when the calendar is shallower than ``WARM``). The
    volatility dial is M0001's ``basket_scale``, which returns None when it would not cut -- it
    de-risks and never levers. They multiply, and the order does not matter: ``basket_scale``
    normalizes the basket's weights to 1 before measuring it, so the vol reading is the same
    whether it sees the braked targets or the unbraked ones, and it is handed the unbraked ones so
    the two dials stay independently readable.
    """
    share = exposure(shadow_drawdown(grid, wealth, data_date, p), p)
    if p.target_vol is None:
        return share
    vol = basket_scale(history, base, data_date, p.vol_n, p.target_vol)
    return share if vol is None else share * vol


# --------------------------------------------------------------------------- the allocator


@dataclass
class BrakedBookPrepared:
    """M0133's prepared columns, plus one unbraked shadow index per distinct book shape.

    The shadow is keyed on the whole ``AsymParams`` -- the screen, the window, the market and the
    book size -- and NOT on the brake, because the shadow is the unbraked book and must read the
    same for every taper. The dedicated test asserts that directly.
    """

    book: Any = field(repr=False)  # m0110.CapturePrepared, as M0133's prepare() returns it
    shadows: dict[AsymParams, np.ndarray | None] = field(default_factory=dict, repr=False)

    @property
    def history(self) -> Mapping[str, History]:
        return self.book.history

    def shadow(self, p: AsymParams) -> np.ndarray | None:
        if p not in self.shadows:
            grid = self.book.grid(p.market)
            if grid is None:
                self.shadows[p] = None
            else:
                universe = frozenset(self.book.history)
                self.shadows[p] = shadow_of(
                    lambda d: self.book.factor.rows_on(universe, d, p.inner), grid, p
                )
        return self.shadows[p]


class OwnAccountBrake:
    """M0133's ungated asymmetry book, trimmed by how far that book is below its own high.

    Held symbols get no special treatment: every rank session is a fresh top set and every resize
    session re-reads both dials, so a name that leaves the chosen set is signal-exited by the book
    engine. ``held`` is passed through to M0133's allocator unchanged and, with ``gate="none"``,
    is not read by it.
    """

    id = "M0149"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        # What the PICKS need, from the parent, plus the volatility estimate's own depth. The
        # shadow's depth is WARM and it stands down below it, exactly as M0109's does, so it adds
        # nothing here and the smoke fixture's 473-bar cap is not approached.
        return max(ASYM.lookback(p.book), p.vol_n + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return tuple(ASYM.symbols(_check(params).book))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        base = ASYM.targets(history, members, data_date, held, p.book)
        if not base or (p.taper is None and p.target_vol is None):
            return base
        grid = build_grid(history, p.book.market)
        wealth = None
        if grid is not None and p.taper is not None:
            universe = frozenset(history)
            wealth = shadow_of(
                lambda d: factor_rows(history, universe, d, p.book.inner), grid, p.book
            )
        return braked(base, account_share(history, grid, wealth, base, data_date, p))

    def prepare(self, history: Mapping[str, History]) -> BrakedBookPrepared:
        return BrakedBookPrepared(ASYM.prepare(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, BrakedBookPrepared):
            raise TypeError(f"prepared must be BrakedBookPrepared, got {type(prepared).__name__}")
        p = _check(params)
        base = ASYM.targets_prepared(prepared.book, members, data_date, held, p.book)
        if not base or (p.taper is None and p.target_vol is None):
            return base
        grid = prepared.book.grid(p.book.market)
        wealth = prepared.shadow(p.book) if p.taper is not None else None
        return braked(
            base, account_share(prepared.history, grid, wealth, base, data_date, p)
        )


BRAKED = OwnAccountBrake()


def _v(suffix: str, params: AccountBrakeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0149-{suffix}", family="M0149",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND, allocator=BRAKED, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0149",
    name=("The asymmetry book kept invested, braked by its own falling account instead of the "
          "market's trend"),
    family="stock-updown-asymmetry",
    source_kind="variation",
    source_ref=(
        "variation of M0133's ungated arm M0133-N40, with M0109's own-drawdown brake and "
        "M0001/M0002's own-volatility target put on it in place of the market switch; the brake "
        "and the vol dial are M0109's and M0001's implementations, imported unchanged"
    ),
    parent_id="M0133",
    hypothesis=(
        "M0133 closed on behaviour, not numbers: M0133-G40 reads 0.8964 against the test-failed "
        "M0002-REL-85, above the 0.85 bar, and the refusal is sound -- 24 random 40-name books "
        "behind the same gate read at most 0.70 against it, so the resemblance is real and not an "
        "artefact of the switch. The measurement that opens the door is M0133-N40, the SAME "
        "asymmetry rank with the gate OFF: measured on its own curve 2026-10-14 it reads 0.5717 "
        "against M0002-REL-85, 0.3524 against M0021-B70-RAW, 0.3625 against M0022-W-TV14 and "
        "0.3341 against M0029-B70-RAW-FRAC -- behaviourally free of every failed book by "
        "a wide margin -- and still earns +9.6% a year funded against SPY TR's +7.2%. Its only "
        "defect is the fall: 69.1% peak to trough, 2008 at -51.4%, against a 50% dev screen and "
        "the owner's 25% real-money bar. The hypothesis is that the fall can be cut WITHOUT the "
        "market switch, and that doing so is the only way this ranking stays promotable. Every "
        "brake that reads the MARKET -- the 200-day cross, the breadth gate, the term-structure "
        "gate -- puts a book in cash in the same months as every other book in this lab, which is "
        "precisely what the kin rule measures and refuses. A brake that reads the BOOK -- its own "
        "drawdown from its own high water mark, or its own trailing volatility applied to an "
        "ungated book -- de-risks on a schedule the failed books do not share. Variants: the "
        "ungated 40-name asymmetry book under a drawdown brake that cuts exposure to cash by 15% "
        "and by 25% below its own trailing one-year peak; under its own 63-day volatility "
        "targeted at 14% and 16%; under both; and a paired in-lab control with neither brake. "
        "Two mechanical decisions were fixed before the run and neither was calibrated on a "
        "result. First, the brake reads an UNBRAKED gross shadow of this same book rebuilt from "
        "bars, never the funded account: a brake that reads its own braked account is a ratchet "
        "that would cut in 2008 and then hold cash straight through the 2009-2015 stretch this "
        "ranking exists to capture, and a deposit-fed account's high is lifted by every top-up. "
        "Second, the tape is the target-band one, because under the old whole-account band a "
        "40-name book executes no trim until exposure has already fallen to 0.60, which would "
        "turn a proportional dial into a switch and make a null result unreadable; the control "
        "arm runs on the same tape so the five braked arms are read against a yardstick that pays "
        "the same costs. Idle cash earns nothing here, so every braked return is a floor. "
        "Success: the fall lands under 50% on dev and ideally near 25%, the funded return keeps "
        "at least half of the ungated book's +2.4 point lead, AND the residual correlation "
        "against all four test-failed books stays under 0.85 -- which would be the first book in "
        "this lab that is dev-eligible, survives the dead companies and is behaviourally free at "
        "the same time. The kin reading is taken first, off the recorded curves, before any "
        "analysis is written, and per variant rather than on the best twin alone."
    ),
    expected_failure=(
        "The likeliest failure is that a book-reading brake is a market-reading brake wearing "
        "different clothes. This book's own worst fall IS 2008, and 2008 is when every other book "
        "in this lab was falling too, so a drawdown brake will go to cash in 2008 and 2001-2002 "
        "and sit out the same months the 200-day switch sits out -- and the kin rule compares "
        "monthly returns less their own fit on SPY, which is exactly where that shows up. The "
        "honest shape of that outcome is a braked arm that passes the drawdown screen and then "
        "reads 0.85 or higher against M0002-REL-85 anyway, which would say something sharper than "
        "this method set out to ask: that the kin bar is a bar on de-risking in crashes rather "
        "than on reading the market, and that no brake of any kind can rescue this ranking. The "
        "volatility arms are the better bet on that axis, because a 63-day volatility target "
        "scales continuously and in both small and large moves rather than switching around the "
        "famous falls -- but they are the worse bet on the fall, because the 2008 drawdown "
        "arrived with a volatility rise the estimate sees only after the first leg. The second "
        "failure is the one M0109 measured and named: a drawdown brake sells after the fall has "
        "happened and buys back after the recovery has happened, so on this lab's measured "
        "pattern it should cost 1 to 3 points a year while improving the fall by less, and a "
        "V-shaped drop -- 1998, 2010, 2011, the second half of 2008's rebound -- trims on the way "
        "down and is still trimmed on the way up. On a book whose whole claim is a +7.7 point "
        "lead over 2009-2015, paying that in the recovery is how the edge dies. The third is "
        "survivorship: M0110's asymmetry arm lost 2.0 points a year on the fuller price history, "
        "more than any arm except the control, so part of this edge is companies the dev store "
        "cannot price, and a dev-only verdict here is provisional whatever it says."
    ),
    candidates=(
        _v("N40-RAW", AccountBrakeParams(BOOK),
           "The ungated 40-name asymmetry book with neither brake: the paired in-lab control"),
        _v("DD15", AccountBrakeParams(BOOK, taper=Decimal("0.15")),
           "All cash by the time the book is 15% below its own one-year high: the hard brake"),
        _v("DD25", AccountBrakeParams(BOOK, taper=Decimal("0.25")),
           "The same brake with a gentler slope: all cash only once the book is down 25%"),
        _v("TV14", AccountBrakeParams(BOOK, target_vol=Decimal("0.14")),
           "No drawdown brake: the book scaled to its own 14% three-month volatility"),
        _v("TV16", AccountBrakeParams(BOOK, target_vol=Decimal("0.16")),
           "The same volatility dial set looser, at 16%: less cash, more of the ranking"),
        _v("DD25-TV14", AccountBrakeParams(BOOK, taper=Decimal("0.25"),
                                           target_vol=Decimal("0.14")),
           "Both brakes at once: do they step aside on different occasions, or the same ones"),
    ),
    seen_keys=(
        "concept:own-account-drawdown-brake-on-a-picked-book",
        "concept:ungated-asymmetry-book-own-vol-target",
        "concept:book-reading-brake-as-a-kin-escape",
    ),
)
