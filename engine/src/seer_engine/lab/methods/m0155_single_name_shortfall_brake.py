"""M0155 — Let go of the one holding that is falling apart on its own, while the market is fine.

Source: a variation of M0152, which dated this account's damage for the first time.
Idea: the roster's book has exactly two defences against a fall, and M0152 measured both. The
SPY 200-day gate handles MARKET falls and handles them well -- the dot-com collapse cost this
book 4-9% and the 2008 crisis 9%, its two mildest stretches in twenty years. Width handles the
SINGLE-HOLDING blowup, and it does so by dilution: own more names and any one of them matters
less. What neither does is notice that one holding has stopped behaving like the others while
nothing at all is wrong with the market. That is spring 2006, and spring 2006 is the whole of
the roster's width problem.

**THE HOLE, dated and measured, and not re-derived here** (M0152, trial #388 and the paired
curve in ``docs/lab/survivorship/roster-width-curve-2026-10-14.csv``). On the
survivorship-check store -- the price history that keeps the companies that went bankrupt, were
bought or were renamed -- this exact book's worst fall is **2006-03-31 to 2006-07-31, 21.82%
month-end and 25.05% daily**, against an owner bar of 25%. Over that window the benchmark went
3.71 to 3.62: the market dipped about 2% and made a new high by September. The 200-day gate
never fired and was right not to. And 2006 is the ONLY width-sensitive episode in the window:

===== ===== ===== ===== ===== ===== ===== =====
names  20    25    30    35    45    50    70
===== ===== ===== ===== ===== ===== ===== =====
2006   21.8  18.9  18.8  16.2  15.1  14.8  12.9
1998   21.6  19.2  19.9  19.7  19.4  18.7  18.0
===== ===== ===== ===== ===== ===== ===== =====

Nearly nine points across the 2006 row against 3.6 across the 1998 one, and none at all in the
crisis years. For a narrow book the single-holding blowup is therefore the LARGER of the two
remaining risks, and the lab has spent most of its ids on market timing and almost none on this.

**WHAT THIS METHOD ASKS.** Width is one answer and M0152 priced it: 35 names, five points of
fall for no return cost on the honest tape. This asks whether a cheaper and more direct answer
exists -- a per-holding brake that lets go of a name which has fallen hard RELATIVE TO THE
MARKET while the market itself is fine. The deliverable is a POINT PLOTTED ON M0152'S CURVE:
the braked twenty-name book's 2006 fall and its funded return, read against the seven recorded
widths, on both stores. If the point sits inside the curve -- a gentler 2006 than 35 names at a
return no worse -- the brake buys something width cannot. If it lands on the curve, it is width
in disguise and the honest answer stays 35 names, which is the result this method expects.

**WHY THIS IS NOT A STOP-LOSS, and the lab has the receipts.** M0019 put a 20% protective stop
under each holding: the worst fall did not shrink and return dropped 0.7-2.4 points a year,
because the stops fired together in market-wide falls, sold near the bottom and missed the
rebound. M0020 added weekly re-entry and still trailed. M0035 read the whole BOOK against the
market and was switched off throughout the fall it was built to cap, because the book was
eleven points AHEAD when that fall began. Three differences, each aimed at one of those
failures:

  * **It is relative, not absolute.** The trigger is the holding's return against the index's
    over the same sessions. When the whole market drops, the index drops with the holding and
    the shortfall barely moves -- so the brake does not fire, which is exactly what killed
    M0019's stop.
  * **It is per holding, not per book.** M0035's switch read an aggregate, and an aggregate was
    healthy while one name inside it was dying. This reads the names one at a time.
  * **It is gated on the market being fine, twice over.** The host book is already all-cash
    while SPY closes under its 200-day average, so the brake can only ever act on a session the
    gate has judged calm -- the 2006 signature, enforced by construction rather than by a
    parameter. The ``market_up`` arm tightens that further and insists the index's own
    ``look_n``-session return is not negative, so the brake is silent even in the stretches
    where the slow average lags a fall that has already begun.

**THE SIGNAL, in full, and it reads only bars dated <= the data date.** On a decision session
``d`` at calendar index ``j``, take the ``look_n`` sessions ``j - look_n + 1 .. j`` of the
market symbol's calendar. For each candidate name, over the sessions in that window on which
BOTH it and the index have a usable daily return:

  * ``cum_r`` is the name's compounded return and ``cum_m`` the index's, each compounded over
    exactly those shared sessions;
  * ``sd_window`` is the standard deviation of the name's daily EXCESS return over the index,
    scaled by the square root of the number of shared sessions -- the natural yardstick for how
    far apart two series that move together normally drift over a window of that length;
  * ``z = (cum_r - cum_m) / sd_window``, and the name is braked when ``z <= -k``.

Three things about that are worth stating plainly, because they are what could fool us:

  * **The index's return is recomputed per name.** Two names with different gaps in their bars
    see slightly different ``cum_m``, because each is compared with the index over the days it
    actually traded. The alternative -- one index number for everyone -- would charge a name
    for days it was not listed.
  * **A name with less than ``MIN_FRAC`` of the window usable is NEVER braked.** The brake acts
    on evidence or it stands down; it never guesses. This matters most for a name that has just
    joined the index, which is precisely the one whose history is thin.
  * **The yardstick is the name's own drift, not a fixed percentage.** A quiet utility and a
    volatile biotech reach ``-2`` standard deviations at very different losses, which is the
    point: the question is "has this stopped behaving like itself", not "has it fallen x%".

**WHAT THE BRAKE DOES, and the two shapes that are not the same question.** ``fill=False``
drops the braked name (or cuts it to ``cut`` of its weight) and **leaves the slot in cash**: the
book holds less. ``fill=True`` removes the braked names from the ranking BEFORE the top
``top`` are taken, so the book still holds ``top`` names and stays fully invested -- the
nineteenth collapsing name is replaced by the twenty-first ranked one. These separate two
answers that would otherwise be confounded: "holding less is safer" is not a finding about
single-name risk, it is a finding about exposure, and M0109 already prices that. Only the
``fill=True`` arms can answer whether swapping the bad name out, at constant exposure and
constant width, closes the 2006 hole.

**A FILTER ON THE RANKING, NOT ON WHAT IS HELD.** The brake is applied to every ranked
candidate, not only to the names the book already owns. The alternative would buy on one rank
session the very name it would sell at the next, which is not a rule anyone would follow with
real money; and keeping it a function of bars and membership alone leaves the P4 identity
trivially true. A braked name re-enters as soon as its shortfall recovers: there is no cooling
period and no memory, deliberately, because memory is where a brake quietly becomes a strategy.

**THE CLOCK, and the limitation this method accepts rather than hides.** The book engine reads
an allocator on rank sessions and resize sessions only. ``monthly-hold-frac-gotrade-tband`` is
the tape M0152's whole curve is measured on and it has no resize cadence, so the brake here is
read ONCE A MONTH. The idea that spawned this asked for a mid-month exit; that is not available
without leaving the curve, because the only preset with a faster resize
(``monthly-rank-weekly-resize-frac-gotrade``) measures its band against whole-account equity, a
band the lab has since measured as barely firing, and no result on it would be comparable to the
seven recorded widths. Staying on M0152's tape was judged worth more than reading the brake
sooner. A feature wish is journalled for a monthly-rank / weekly-resize preset on the fixed
tape, and the monthly clock is written into the hypothesis as a known ceiling on what this can
measure, not discovered afterwards.

**WHAT THE RANKING CANNOT SEE, and why a 63-session window is not redundant with it.** The host
ranks on twelve months of cumulative market-model residual, SKIPPING the most recent 21
sessions. A name that collapsed inside the last month is invisible to the ranking by
construction, and a name that collapsed inside the last quarter is still outvoted by the nine
good months behind it. ``look_n = 63`` is one quarter: the window the ranking skips, plus the
two months it dilutes. It was fixed before the run from that construction and not from any
result.

**CALIBRATION, stated before the run.** Nothing here was tuned on an outcome. ``k`` takes 1.5,
2.0 and 2.5 because two standard deviations is the conventional line and the two neighbours
bracket it, so "did we pick a lucky threshold" is answerable from the batch itself rather than
from a second method id. ``look_n = 63`` is the skip-plus-dilution argument above. ``cut = 0.5``
is a half position, the idea's own second shape. ``MIN_FRAC`` is M0007's, unchanged, so the
evidence bar for braking a name is the evidence bar for scoring one.

**PROMOTION IS NOT AVAILABLE AND IS NOT SOUGHT.** This line runs through M0007, which is
test-failed, so the hard gate refuses it on kin whatever it scores, and the kin bar refuses the
family. Promotion would only be available for a brake built on a book whose ancestry is clean,
which this is not. Accepted before the run; any arm that reads eligible against the dev screen
is a by-product and must not be reported as a candidate.

Every piece reads only bars dated <= ``data_date``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    MIN_FRAC,
    RESIDMOM,
    ResidParams,
    ResidPrepared,
    ReturnGrid,
    build_grid,
    resid_lookback,
    residual_scores,
    targets_from_scores,
)
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20
from seer_engine.lab.methods.m0128_near_miss_fixed_tape import MONTHLY_TBAND
from seer_engine.sim.book import Target
from seer_engine.sim.rules import rule_owner_inputs
from seer_engine.strategies.allocator import scale_weight, target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_rows,
    factor_weights,
    trend_on,
)

ADDED = date(2026, 10, 14)

ZERO = Decimal(0)


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class ShortfallBrakeParams:
    """M0007-N20-RAW's picks, plus one per-holding relative-shortfall brake on top of them.

    ``inner`` is the host book verbatim and is never varied: the whole point of the measurement
    is that an arm here and a rung of M0152's width curve differ in the brake and in nothing
    else. Every field below is the brake.
    """

    inner: ResidParams
    k: Decimal | None = None  # brake at z <= -k standard deviations; None = no brake at all
    look_n: int = 63  # sessions the shortfall is measured over (one quarter)
    cut: Decimal = ZERO  # the share of its weight a braked name keeps; 0 = let it go entirely
    fill: bool = False  # True: drop braked names from the ranking, so the book still holds `top`
    market_up: bool = False  # True: act only while the index's own look_n return is not negative

    def __post_init__(self) -> None:
        if not isinstance(self.inner, ResidParams):
            raise TypeError(f"inner must be ResidParams, got {type(self.inner).__name__}")
        if self.k is not None:
            if not isinstance(self.k, Decimal) or not self.k.is_finite():
                raise TypeError(f"k must be None or a finite Decimal, got {self.k!r}")
            if self.k <= 0:
                raise ValueError(f"k must be > 0, got {self.k}")
        if isinstance(self.look_n, bool) or not isinstance(self.look_n, int):
            raise TypeError(f"look_n must be an int, got {type(self.look_n).__name__}")
        if self.look_n < 20:
            raise ValueError(f"look_n must be >= 20, got {self.look_n}")
        if not isinstance(self.cut, Decimal) or not self.cut.is_finite():
            raise TypeError(f"cut must be a Decimal, got {self.cut!r}")
        if not 0 <= self.cut < 1:
            raise ValueError(f"cut must be a Decimal in [0, 1), got {self.cut}")
        for name in ("fill", "market_up"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool, got {type(getattr(self, name)).__name__}")
        # One spelling per behaviour. A configuration that does nothing, or whose fields
        # contradict each other, would otherwise get its own config_digest and could be run
        # twice under two names as though it were two measurements.
        if self.fill and self.cut != ZERO:
            raise ValueError(
                "fill=True removes the braked name from the ranking, so there is no weight left "
                f"to cut: cut must be 0, got {self.cut}"
            )
        if self.k is None and (self.cut != ZERO or self.fill or self.market_up):
            raise ValueError(
                "with k None there is no brake, so cut, fill and market_up must be at their "
                "defaults: that configuration is the host book and has exactly one spelling"
            )

    def as_dict(self) -> dict[str, str]:
        out = {
            "k": "none" if self.k is None else str(self.k),
            "look_n": str(self.look_n),
            "cut": str(self.cut),
            "fill": "yes" if self.fill else "no",
            "market_up": "yes" if self.market_up else "no",
        }
        for key, value in self.inner.as_dict().items():
            out[f"inner.{key}"] = value
        return out


def _check(params: object) -> ShortfallBrakeParams:
    if not isinstance(params, ShortfallBrakeParams):
        raise TypeError(f"params must be ShortfallBrakeParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the signal


def _window(grid: ReturnGrid, data_date: date, look_n: int) -> tuple[int, int] | None:
    """``(w0, j)`` -- the ``look_n`` calendar columns ending at ``data_date``, or None.

    None means "not measurable here": ``data_date`` is not a session of the market symbol's
    calendar, or the calendar does not reach back ``look_n`` sessions from it. The caller then
    leaves the book unbraked, which is the control.
    """
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day:
        return None
    w0 = j - look_n + 1
    if w0 < 0:
        return None
    return w0, j


def shortfall_z(
    grid: ReturnGrid, symbols: list[str], data_date: date, p: ShortfallBrakeParams
) -> dict[str, float]:
    """Each symbol's shortfall against the index over the window, in its own standard deviations.

    Negative means the name trailed the index. A symbol is absent when it is not measurable: no
    row in the grid, fewer than ``MIN_FRAC`` of the window's sessions shared with the index, or
    a zero excess-return spread. Reads only calendar columns at or before ``data_date``.
    """
    bounds = _window(grid, data_date, p.look_n)
    if bounds is None:
        return {}
    w0, j = bounds
    mrow = grid.row.get(p.inner.market)
    if mrow is None:
        return {}
    names = [s for s in symbols if s in grid.row]
    if not names:
        return {}
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)

    m = grid.rets[mrow, w0 : j + 1]
    r = grid.rets[idx, w0 : j + 1]
    ok = np.isfinite(r) & np.isfinite(m)[None, :]
    count = ok.sum(axis=1)
    enough = count >= max(3, math.ceil(MIN_FRAC * p.look_n))
    safe = np.where(count > 0, count, 1).astype(np.float64)

    with np.errstate(divide="ignore", invalid="ignore"):
        cum_r = np.prod(1.0 + np.where(ok, r, 0.0), axis=1) - 1.0
        cum_m = np.prod(1.0 + np.where(ok, np.broadcast_to(m, r.shape), 0.0), axis=1) - 1.0
        excess = np.where(ok, r - m[None, :], 0.0)
        mean = excess.sum(axis=1) / safe
        spread = np.where(ok, excess - mean[:, None], 0.0)
        sd_window = np.sqrt((spread * spread).sum(axis=1) / safe) * np.sqrt(safe)
        usable = enough & np.isfinite(sd_window) & (sd_window > 0.0)
        z = np.where(usable, (cum_r - cum_m) / np.where(usable, sd_window, 1.0), np.nan)

    live = usable & np.isfinite(z)
    return {names[k]: float(z[k]) for k in (int(v) for v in np.flatnonzero(live))}


def market_calm(grid: ReturnGrid, data_date: date, p: ShortfallBrakeParams) -> bool:
    """Is the index's own ``look_n``-session return not negative? True always when ``market_up`` is off.

    False whenever the answer cannot be established from bars at or before ``data_date``: the
    brake stands down rather than guessing, so an unmeasurable session is a session the variant
    behaves as its control.
    """
    if not p.market_up:
        return True
    bounds = _window(grid, data_date, p.look_n)
    if bounds is None:
        return False
    w0, j = bounds
    mrow = grid.row.get(p.inner.market)
    if mrow is None:
        return False
    m = grid.rets[mrow, w0 : j + 1]
    ok = np.isfinite(m)
    if int(ok.sum()) < max(3, math.ceil(MIN_FRAC * p.look_n)):
        return False
    with np.errstate(divide="ignore", invalid="ignore"):
        cum = float(np.prod(1.0 + np.where(ok, m, 0.0)) - 1.0)
    return math.isfinite(cum) and cum >= 0.0


def braked_names(
    grid: ReturnGrid, symbols: list[str], data_date: date, p: ShortfallBrakeParams
) -> frozenset[str]:
    """The symbols the brake acts on at ``data_date``; empty when the brake is off or stood down."""
    if p.k is None or not market_calm(grid, data_date, p):
        return frozenset()
    limit = -float(p.k)
    return frozenset(s for s, z in shortfall_z(grid, symbols, data_date, p).items() if z <= limit)


# --------------------------------------------------------------------------- the book


def _priced(
    chosen: list[FactorRow], inner: FactorParams, braked: frozenset[str], cut: Decimal
) -> tuple[Target, ...]:
    """``chosen`` at F4's weights, with each braked name cut to ``cut`` of its weight (0 = dropped).

    The weight of a dropped or trimmed name is NOT redistributed: under ``sizing="equal"``
    ``factor_weights`` gives every row ``1/top`` whatever the list length, so the freed slot is
    cash and the survivors keep the size they would have had. That is deliberate -- a brake that
    re-concentrated into the names it kept would be measuring concentration, not braking.
    """
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, inner), strict=True):
        if weight is None:
            continue
        if row.symbol in braked:
            if cut <= ZERO:
                continue
            scaled = scale_weight(weight, cut)
            if scaled is None:
                continue
            weight = scaled
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


def brake_targets(
    rows: list[FactorRow],
    scores: Mapping[str, float],
    grid: ReturnGrid,
    data_date: date,
    p: ShortfallBrakeParams,
) -> tuple[Target, ...]:
    """The host book's targets with the brake applied; exactly the host's when nothing is braked.

    The fall-through to ``targets_from_scores`` is not an optimisation: it is the guarantee that
    a session on which no name is braked trades identically to the recorded control, so any
    difference between an arm and M0152's rung is a session the brake acted on and nothing else.
    """
    if p.k is None:
        return targets_from_scores(rows, scores, p.inner)
    scorable = [r for r in rows if r.symbol in scores and r.symbol not in EXCLUDED]
    ranked = sorted(scorable, key=lambda r: (-scores[r.symbol], r.symbol))
    braked = braked_names(grid, [r.symbol for r in ranked], data_date, p)
    if not braked:
        return targets_from_scores(rows, scores, p.inner)
    inner = p.inner.inner
    if p.fill:
        kept = [r for r in ranked if r.symbol not in braked][: inner.top]
        return _priced(kept, inner, frozenset(), ZERO)
    return _priced(ranked[: inner.top], inner, braked, p.cut)


class ShortfallBrakeAllocator:
    """M0007-N20-RAW's book, with each holding read against the index over the last quarter.

    Held symbols get no special treatment and the brake keeps no state: every decision session
    re-ranks, re-measures and re-decides from bars alone, so a braked name returns the moment
    its shortfall does.
    """

    id = "M0155"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        # The picks need `resid_lookback` (401 bars for the host's params) and the brake needs
        # `look_n + 1` (64). The max is the honest figure and, for every variant this method
        # declares, it is exactly the host's -- so the dev window opens on the same session as
        # M0128-RAW20's and the two are comparable trade for trade.
        return max(resid_lookback(p.inner), p.look_n + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return RESIDMOM.symbols(_check(params).inner)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        inner = p.inner
        if not trend_on(history, data_date, inner.inner):
            return ()
        rows = factor_rows(history, members, data_date, inner.inner)
        if not rows:
            return ()
        grid = build_grid(history, inner.market)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, inner)
        return brake_targets(rows, scores, grid, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return RESIDMOM.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        inner = p.inner
        if not trend_on(prepared.history, data_date, inner.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, inner.inner)
        if not rows:
            return ()
        grid = prepared.grid(inner.market)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, inner)
        return brake_targets(rows, scores, grid, data_date, p)


SHORTFALL = ShortfallBrakeAllocator()

#: The host book, imported and never rebuilt: M0007-N20-RAW's params exactly as M0128-RAW20,
#: M0139 and M0152 use them, so an arm here and a rung of the width curve differ only in the brake.
HOST = RAW20


def _v(suffix: str, params: ShortfallBrakeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0155-{suffix}", family="M0155", rules=MONTHLY_TBAND,
                     allocator=SHORTFALL, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=rule_owner_inputs(MONTHLY_TBAND))


K15 = Decimal("1.5")
K20 = Decimal("2.0")
K25 = Decimal("2.5")

METHOD = Method(
    id="M0155",
    name="Let go of the one holding that is falling apart on its own, while the market is fine",
    family="stock-single-name-brake",
    source_kind="variation",
    source_ref=(
        "M0152 for the dated hole this attacks, its seven-rung paired width curve and the 2006 "
        "episode (docs/lab/survivorship/roster-width-curve-2026-10-14.csv); M0128-RAW20 (trial "
        "#388) for the unbraked twenty-name control, which is the roster's own book at real fees "
        "on the fixed tape and is quoted here rather than re-run; M0019, M0020 and M0035 for the "
        "three per-stock and per-book exits that already failed, and which this is shaped to "
        "differ from; M0109 for the shadow-reconstruction and stand-down conventions"
    ),
    parent_id="M0152",
    hypothesis=(
        "M0152 dated this account's damage for the first time and found that the SPY 200-day "
        "market gate already handles market falls well -- the dot-com collapse cost this book "
        "4-9 percent and the 2008 crisis 9 percent, its two mildest stretches in twenty years. "
        "Its two real holes are 1998, a crash too fast for a 200-day average and essentially "
        "unfixable by width (about 19-21 percent at every width from 20 to 70 names), and SPRING "
        "2006, where the market index dipped 2 percent and recovered to a new high by September "
        "while the twenty-name book lost 21.8 percent on the survivorship-check store and 16.3 "
        "on dev. 2006 is the ONLY width-sensitive episode in the window: 21.8 / 18.9 / 18.8 / "
        "16.2 / 15.1 / 14.8 / 12.9 across 20/25/30/35/45/50/70 names on the check store, nearly "
        "nine points, against 3.6 points in 1998 and none at all in the crisis years. So for a "
        "narrow book the single-holding blowup is now the LARGER of the two risks by a wide "
        "margin, and the lab has spent most of its ids on market timing and almost none on this. "
        "Width is one answer and M0152 priced it (35 names, five points of fall for no return "
        "cost on the check store). This asks whether a cheaper and more direct answer exists: a "
        "per-holding brake that lets go of a position which has fallen hard RELATIVE TO THE "
        "MARKET while the market itself is fine -- precisely the 2006 signature, and deliberately "
        "not a stop-loss, which M0020 already showed fires on the market falls the gate has "
        "handled. THE RULE, fixed before the run. On each monthly decision, for every ranked "
        "candidate, measure its compounded return over the last 63 sessions against the index's "
        "over the sessions they share, divide by the standard deviation of its own daily excess "
        "return over that window scaled by the square root of the window length, and act when "
        "that z-score is at or below minus k. A name with less than 80 percent of the window "
        "usable is never braked. Six arms, all on M0007-N20-RAW's picks verbatim at twenty names "
        "on monthly-hold-frac-gotrade-tband, the tape M0152's whole curve is measured on, so an "
        "arm here and a rung there differ in the brake and in nothing else: Z2 and Z2-HALF let "
        "the braked name go or cut it to half weight and leave the slot IN CASH; Z15-FILL, "
        "Z2-FILL and Z25-FILL remove the braked names from the ranking before the top twenty are "
        "taken, so the book still holds twenty names and stays fully invested; Z2-FILL-UP is "
        "Z2-FILL with the further condition that the index's own 63-session return is not "
        "negative. The unbraked control is NOT re-run: M0128-RAW20 (trial #388) is that book, "
        "recorded, funded identically at 10,000,000 IDR opening and 5,000,000 IDR on the 25th "
        "across 237 deposits, and a dedicated test module proves this allocator with the brake "
        "off is target-for-target identical to it rather than spending a trial to show the same "
        "thing. WHAT IS PREDICTED, in numbers, before any result. (1) THE BRAKE FIRES RARELY AND "
        "THE BOOK BARELY MOVES. Predicted trade count 1,650 to 1,900 against the control's 1,607 "
        "-- a handful of extra round trips a year, not dozens -- and a whole-window funded return "
        "within 1.0 point a year of the control's 13.68 percent on dev and 11.98 on the check "
        "store. If an arm trades more than 2,300 times it has become a short-horizon strategy "
        "wearing a brake's name and must be reported as one. (2) THE FILL ARMS CLOSE MORE OF 2006 "
        "THAN THE CASH ARMS, AT LESS COST. Predicted check-store 2006 fall: 16 to 19 percent for "
        "Z2-FILL against the control's 21.8 and the 35-name book's 16.2. (3) THE THRESHOLD CURVE "
        "IS MONOTONE AND SHALLOW. Z15-FILL should fire most and cost most, Z25-FILL least of "
        "both, with under 2 points of 2006 fall and under 0.5 of a point a year separating 1.5 "
        "from 2.5. A steep or non-monotone threshold curve means the result is a threshold "
        "accident and the verdict says so instead of naming a k. (4) THE DECISION RULE, FIXED NOW "
        "SO THE RESULT CANNOT CHOOSE IT. The brake is worth something only if it beats WIDTH, not "
        "only the control. An arm SUCCEEDS when, on the check store at twenty names, its 2006 "
        "fall is at or below 17.8 percent -- the control's 21.8 less the 4 points the idea asked "
        "for -- AND its funded return is within 1.0 point a year of the control's 11.98 percent. "
        "An arm is WIDTH IN DISGUISE when it reaches that 2006 number but sits on or outside the "
        "line M0152's seven rungs trace through (2006 fall, funded return) -- that is, when 35 "
        "names already gives the same pair -- and then the honest answer is 35 names and the "
        "verdict leads with it. An arm FAILS when it trades the fall away for more than a point a "
        "year, or when its 1998, 2000-02, 2008-09 and 2010-15 era falls get worse by more than "
        "they gain in 2006. (5) BOTH STORES OR IT DOES NOT COUNT. The dev store cannot price "
        "roughly 4 in 10 of the days companies spent in the index, and the ones it cannot price "
        "are overwhelmingly the companies that went bankrupt or were bought -- which is the exact "
        "event this brake exists to catch. Predicted dev-store 2006 falls: 14 to 16 percent for "
        "every arm against the control's 16.3, a difference too small to read. A dev-only result "
        "here is not weak evidence, it is no evidence, and the run on dev exists to record the "
        "trials and price the return cost, not to answer the question. (6) THE CLOCK IS A CEILING "
        "AND IS ACCEPTED BEFORE THE RUN. monthly-hold-frac-gotrade-tband has no resize cadence, "
        "so this brake is read once a month; the mid-month exit the idea also named is not "
        "available without leaving the curve every number here is measured against, and a feature "
        "wish is journalled for a monthly-rank weekly-resize preset on the fixed tape. "
        "PROMOTION IS NOT AVAILABLE AND IS NOT SOUGHT. This line runs through M0007, which is "
        "test-failed, so the hard gate refuses it on kin whatever it scores and the kin bar "
        "refuses the family; promotion would only be open to a brake built on a book whose "
        "ancestry is clean. Accepted before the run. Any arm that reads eligible against the dev "
        "screen is a by-product and must not be reported as a candidate or as a near miss."
    ),
    expected_failure=(
        "The likely failure, and the idea named it in advance: the brake sells into noise, fires "
        "dozens of times a year at Gotrade's real fees, and gives back more in whipsaw than one "
        "episode in twenty years was worth; or it is simply width in disguise, and the honest "
        "answer stays 35 names. Four specific shapes, written now. (1) THE BRAKE IS SHORT-TERM "
        "REVERSAL WITH THE SIGN WRONG. 'Sell what has fallen most against the market over the "
        "last quarter' is the inverse of the best-documented anomaly at this horizon: short-horizon "
        "losers bounce. If that dominates, every arm trails the control by 1 to 3 points a year "
        "with a 2006 fall barely better, and the brake is a reversal bet nobody pre-registered. "
        "This is the single most likely way the method dies and it is checked first: the 2010-15 "
        "era column, where there is no episode for the brake to catch, prices the drag alone. "
        "(2) IT IS WIDTH IN DISGUISE. Dropping a name from a twenty-name book and leaving the "
        "slot in cash is holding nineteen names, and the fill arms exist precisely so that "
        "'safer because it holds less' cannot be mistaken for 'safer because it let go of the "
        "right name'. If Z2 improves 2006 and Z2-FILL does not, the finding is about exposure, "
        "M0109 already owns that question, and this id bought nothing new. (3) ONE EPISODE IS "
        "DOING ALL THE WORK, AND IT IS THE EPISODE THE BRAKE WAS DESIGNED AGAINST. Spring 2006 is "
        "a single five-month stretch in a twenty-year window, and a rule aimed at it will improve "
        "it by construction. The result is only evidence if 1998, 2000-02, 2008-09 and 2010-15 do "
        "not get worse to pay for it, and if the dev store -- a genuinely different tape -- moves "
        "in the same direction even though it cannot see the episode. If 2006 improves and "
        "everything else degrades, the honest reading is overfitting to one spring and the verdict "
        "must lead with that rather than with the headline. (4) THE MONTHLY CLOCK MAY BE TOO SLOW "
        "TO MATTER. A name can collapse and be gone inside one month, and this brake reads once a "
        "month. If the braked names turn out to be ones the ranking would have dropped at the same "
        "session anyway, the brake changes nothing and the correct report is a null result with "
        "the overlap counted, not a thin improvement dressed up. (5) THE CHECK STORE IS A "
        "CROSS-CHECK, NOT TRUTH. It adds most of the members the dev store cannot price and not "
        "all of them, and real collapses were kept while data errors were cleaned, which is a "
        "judgement call. A 4-point claim that rests on half a point of margin is not a claim, and "
        "the verdict says so rather than rounding in its own favour. (6) DEPOSITS SOFTEN EVERY "
        "FALL IN THIS FILE ALIKE, so every figure lines up against M0128's, M0139's and M0152's, "
        "which are funded identically, and against no unfunded trial anywhere."
    ),
    candidates=(
        _v("Z2", ShortfallBrakeParams(HOST, k=K20),
           "Let a holding go once it is two standard deviations behind the index over a quarter, "
           "and leave its slot in cash"),
        _v("Z2-FILL", ShortfallBrakeParams(HOST, k=K20, fill=True),
           "The same trigger with the slot refilled from the ranking: twenty names and fully "
           "invested, so only the swap is being priced"),
        _v("Z15-FILL", ShortfallBrakeParams(HOST, k=K15, fill=True),
           "The sensitive rung of the threshold curve: one and a half standard deviations, "
           "refilled"),
        _v("Z25-FILL", ShortfallBrakeParams(HOST, k=K25, fill=True),
           "The patient rung of the threshold curve: two and a half standard deviations, "
           "refilled"),
        _v("Z2-HALF", ShortfallBrakeParams(HOST, k=K20, cut=Decimal("0.5")),
           "A half position rather than an exit: prices the gentler shape of the same trigger"),
        _v("Z2-FILL-UP", ShortfallBrakeParams(HOST, k=K20, fill=True, market_up=True),
           "Z2-FILL that acts only while the index's own quarter is not negative: insists the "
           "market is really fine, not merely above a slow average"),
    ),
    seen_keys=(
        "concept:per-holding-relative-shortfall-brake",
        "concept:single-name-exit-gated-on-a-rising-market",
        "concept:brake-reading-the-window-the-momentum-skip-hides",
    ),
)
