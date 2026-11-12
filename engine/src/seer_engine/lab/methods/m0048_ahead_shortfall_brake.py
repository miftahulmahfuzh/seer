"""M0048 — Trim toward the market when the book is furthest ahead of it, not when it is behind.

Source: a variation of M0035, from M0035's own note. M0035 parked part of the account in SPY
while M0032's book trailed SPY over the trailing year, and it found the brake backwards: the
binding 2006 dev fall began while the book was 11.8 points AHEAD of SPY over the trailing twelve
months, not behind -- so a brake watching for "behind" was off for the whole run-up and only
switched on ten days after the bottom.
Idea: invert the trigger. Keep M0032's book -- top-20 raw cumulative residual momentum, F4's
screen, the SPY-200 trend gate, monthly, equal weights, fractional shares at Gotrade's real fees
-- and the same shadow-book reconstruction M0035 built, but park part of the account in SPY while
the book LEADS SPY over the trailing year by more than a threshold, holding the rest in the book.
This is a profit-taking brake, not a loss-avoiding one: it tests whether a book that has recently
run far ahead of the market is the one about to give some of it back, which is the opposite bet
to M0035's and to ordinary momentum investing (a strong trailing year usually means the book
*continues* strong, per the book's own 1996-2015 record).

THE SHADOW BOOK is identical to M0035's: ``relative_gap`` from m0035 reconstructs the unbraked
book's trailing ``look_n``-session return against SPY's, a pure function of bars, gross of fees,
needing the inner allocator's lookback plus ``look_n`` plus a month of depth before it switches on
at all. Read that module's docstring for why it is the unbraked book, why its member-set proxy is
a small bounded distortion of the trigger universe only, and why it is gross. This method changes
nothing about the reconstruction; it only flips the sign the trigger fires on.

The trend gate stays supreme: when SPY is below its 200-day average the inner allocator targets
nothing, and this brake adds nothing either -- it can only move stock risk into SPY, never cash
into SPY, exactly like M0035.

Five variants: the control (the switch wired but parked at zero, reproducing M0032's book), three
thresholds (10, 15, 20 points ahead) at half the account, and the 10-point threshold again at a
quarter of the account, to see whether a gentler trim changes the picture the half-trims give.
A 5-point threshold is dropped: over 1996-2015 the book beat SPY by about seven points a year on
average, so a 12-month lead of 5 points would fire on almost every normal year and say nothing
about the one episode this method was built to study.

Every piece reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    RESIDMOM,
    ResidParams,
    ResidPrepared,
    build_grid,
    resid_lookback,
)
from seer_engine.lab.methods.m0035_relative_shortfall_brake import (
    MONTH_SESSIONS,
    PARK,
    relative_gap,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, scale_weight, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 11, 12)


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class AheadParams:
    """M0032's configuration (``inner``) plus the trim-into-strength switch.

    ``look_n`` and ``inner`` give this the same ``.look_n``/``.inner`` shape ``relative_gap`` and
    ``shadow_depth`` (both defined for any params with that shape, in m0035) read regardless of
    which direction the trigger fires.
    """

    inner: ResidParams
    look_n: int = 252  # sessions the book and SPY are compared over (12 months)
    ahead: Decimal = Decimal("0.10")  # park once the book leads SPY by more than this
    park: Decimal = Decimal("0.5")  # share of the account moved to SPY while ahead (0 = control)

    def __post_init__(self) -> None:
        if not isinstance(self.inner, ResidParams):
            raise TypeError(f"inner must be ResidParams, got {type(self.inner).__name__}")
        if isinstance(self.look_n, bool) or not isinstance(self.look_n, int) or self.look_n < 20:
            raise ValueError(f"look_n must be an int >= 20, got {self.look_n!r}")
        if not isinstance(self.ahead, Decimal) or not (0 < self.ahead < 1):
            raise ValueError(f"ahead must be a Decimal in (0, 1), got {self.ahead!r}")
        if not isinstance(self.park, Decimal) or not (0 <= self.park <= 1):
            raise ValueError(f"park must be a Decimal in [0, 1], got {self.park!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"look_n": str(self.look_n), "ahead": str(self.ahead), "park": str(self.park)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def ahead_lookback(params: AheadParams) -> int:
    """Bars the PICKS need. The brake reads deeper; see the module docstring."""
    return resid_lookback(params.inner)


def ahead_shadow_depth(params: AheadParams) -> int:
    """Bars the shadow book needs before the brake switches on at all."""
    return resid_lookback(params.inner) + params.look_n + MONTH_SESSIONS + 1


def braked_ahead(
    inner: tuple[Target, ...],
    gap: float | None,
    history: Mapping[str, History],
    data_date: date,
    params: AheadParams,
) -> tuple[Target, ...]:
    """``inner``, or ``park`` of the account in SPY with the stock legs scaled by the rest.

    The mirror image of M0035's ``braked``: that one parked while ``gap <= -behind`` (the book
    trailing); this parks while ``gap >= ahead`` (the book leading).
    """
    if not inner or params.park <= 0 or gap is None or gap < float(params.ahead):
        return inner
    close = last_close(history.get(PARK), data_date)
    if close is None:
        return inner
    leg = target_from_close(PARK, close, params.park)
    if leg is None:  # an unusable SPY price: stay in the book rather than half-brake
        return inner
    out = [leg]
    keep = Decimal(1) - params.park
    if keep > 0:
        for target in inner:
            weight = scale_weight(target.weight, keep)
            if weight is not None:
                out.append(replace(target, weight=weight))
    return tuple(out)


# --------------------------------------------------------------------------- the allocator


def _check(params: object) -> AheadParams:
    if not isinstance(params, AheadParams):
        raise TypeError(f"params must be AheadParams, got {type(params).__name__}")
    return params


class AheadShortfallBrake:
    """M0032's book, part of it parked in SPY while the book leads SPY over the trailing year.

    Held symbols get no special treatment: the stock legs are the inner allocator's fresh top
    set, as in M0007, and the SPY leg is sized by ``park`` alone.
    """

    id = "M0048"

    def lookback(self, params: Any) -> int:
        return ahead_lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return tuple(sorted({PARK, *RESIDMOM.symbols(p.inner)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (PARK,)

    def uses_members(self, params: Any) -> bool:
        return bool(RESIDMOM.uses_members(_check(params).inner))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        inner = RESIDMOM.targets(history, members, data_date, held, p.inner)
        if not inner or p.park <= 0:
            return inner

        def picks_at(d: date) -> tuple[str, ...]:
            return tuple(t.symbol for t in RESIDMOM.targets(history, members, d, frozenset(), p.inner))

        gap = relative_gap(build_grid(history, p.inner.market), picks_at, data_date, p)
        return braked_ahead(inner, gap, history, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return RESIDMOM.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        inner = RESIDMOM.targets_prepared(prepared, members, data_date, held, p.inner)
        if not inner or p.park <= 0:
            return inner

        def picks_at(d: date) -> tuple[str, ...]:
            return tuple(
                t.symbol
                for t in RESIDMOM.targets_prepared(prepared, members, d, frozenset(), p.inner)
            )

        gap = relative_gap(prepared.grid(p.inner.market), picks_at, data_date, p)
        return braked_ahead(inner, gap, prepared.history, data_date, p)


BRAKE = AheadShortfallBrake()
RAW20 = ResidParams(N20, scaled=False)  # M0007-N20-RAW / M0032's ranking, verbatim


def _v(suffix: str, ahead: str, park: str, rationale: str) -> Candidate:
    params = AheadParams(RAW20, ahead=Decimal(ahead), park=Decimal(park))
    return Candidate(id=f"M0048-{suffix}", family="M0048", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BRAKE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0048",
    name="Trim toward the market when the book is furthest ahead of it, not when it is behind",
    family="stock-relative-shortfall-brake",
    source_kind="variation",
    source_ref=(
        "M0035's own note: the book's worst 2006 dev fall began while it was 11.8 points ahead of "
        "SPY over the trailing year, so a brake watching for 'behind' was off throughout and only "
        "switched on ten days after the bottom"
    ),
    parent_id="M0035",
    hypothesis=(
        "M0035 parked part of the account in SPY while M0032's book trailed SPY over the trailing "
        "year, built to insure against the four failed test-window looks. It found the brake aimed "
        "the wrong way: the binding 2006 dev fall happened while the book was 11.8 points AHEAD of "
        "SPY, not behind, so the trailing-side switch missed it entirely. This method inverts the "
        "trigger and keeps everything else verbatim -- M0032's top-20 raw cumulative residual "
        "momentum, F4's screen, the SPY-200 trend gate, monthly, equal weights, fractional shares "
        "at Gotrade's real fees on monthly-hold-frac-gotrade. At each rebalance it compares the "
        "book's own trailing 12-month return with SPY's over the same sessions (the identical "
        "shadow-book reconstruction M0035 used), and while the book LEADS SPY by more than the "
        "threshold, it parks a fraction of the account in SPY, holding the rest in the book. I "
        "expect this to cost return on the dev window the same way M0035's did, and the point of "
        "the run is to learn whether trimming into strength, specifically, caps the 2006-style fall "
        "where trimming into weakness could not -- since that fall is the one concrete episode "
        "either brake was built against. CTRL (park = 0) is the in-method control: it should "
        "reproduce M0032's trade count and shape on the identical window and fee schedule, since a "
        "recorded trial's returns are not reproducible across store rebuilds and must be compared "
        "re-run to re-run."
    ),
    expected_failure=(
        "Trimming after a strong trailing year sells into the book's own momentum, and this exact "
        "book beat SPY by about seven points a year on average over 1996-2015 -- so parking money "
        "in SPY whenever the book is well ahead is betting against the thing the book is good at. "
        "I expect most of the dev window's AHEAD-ing to fire during ordinary strong years rather "
        "than right before a reversal, costing return in the same 1-3 points a year range M0035 "
        "lost, with no improvement to the worst fall: the 2006 episode is one data point, and a "
        "threshold tuned to catch it is as likely to be early (parking before the real top, giving "
        "back the lead it was trying to protect) or to fire so rarely across 20 years that every "
        "variant comes back a near-copy of CTRL. The quieter failure mode is the same as M0035's: "
        "if a 10-20 point trailing lead is rare on this book's record, the dev window has almost no "
        "episodes to learn from and says nothing about whether trimming into strength would have "
        "helped in 2016-2026."
    ),
    candidates=(
        _v("CTRL", "0.10", "0.00",
           "Control: M0032's book under this wrapper with the switch off (the same curve as "
           "M0035-CTRL, first recorded as a trial of M0035); the baseline the ahead-brake runs "
           "are read against"),
        _v("T10-QTR", "0.10", "0.25", "Ahead by more than 10 points over a year: a quarter of the account to SPY"),
        _v("T10-HALF", "0.10", "0.50", "Ahead by more than 10 points: half the account to SPY"),
        _v("T15-HALF", "0.15", "0.50", "Ahead by more than 15 points: half the account to SPY"),
        _v("T20-HALF", "0.20", "0.50", "Ahead by more than 20 points: half the account to SPY"),
    ),
    seen_keys=(
        "concept:ahead-shortfall-brake",
        "concept:trim-into-strength",
        "concept:park-in-spy-while-ahead",
    ),
)
