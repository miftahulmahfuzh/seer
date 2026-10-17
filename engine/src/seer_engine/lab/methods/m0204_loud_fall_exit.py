"""M0204 — Sell a momentum holding that falls on heavy trading: residual momentum with a loud-fall exit.

Source: a variation of M0161 (the quiet/loud split of last fortnight's fallers), applied as an
exit on the roster's residual-momentum book (M0007-N20-RAW, at real fees as M0032-N20-RAW-FRAC-GT).
Literature: Conrad, Hameed & Niden (1994) and Da, Liu & Schaumburg (2014) on volume-conditioned
short-horizon returns; Lee & Swaminathan (2000) on volume and momentum.
Idea: M0161 found that big index members falling on above-normal volume keep falling -- its
loud-fall book's worst fall was 37% against 24% for the quiet one. That is a poor entry and may be
a useful exit. The momentum book's ranking skips the last month by construction, so a holding that
starts collapsing on news is invisible to it until the next month's re-pick. This method holds the
same twenty picks and, at each weekly check, lets go of any holding whose two-week standardised
residual is in the bottom tenth of the screened pool AND (for the main arm) whose two-week share
volume is above its prior-year normal. The slot stays in cash until the next monthly re-pick.

**THE CLOCK.** The book engine's split cadence (monthly rank, weekly resize) keeps the rank
session's basket and only rescales its TOTAL weight on a resize session, so a per-name mid-month
exit cannot ride it. This method therefore runs on a weekly rank cadence (fractional, Gotrade's
real fees -- the ``weekly-hold-frac-gotrade`` rule set M0063, M0064 and M0076 already use) and
rebuilds the monthly pick as a pure function of bars on every weekly decision:

    * S = the session after data date d; A = the first NYSE session of S's calendar month; the
      ANCHOR is a = prev_session(A), the data date a month-start monthly-hold run would rank on;
    * the basket is M0007-N20-RAW's top twenty at a, the SPY-200 gate read at a too, so the
      market switch flips monthly exactly as in the parent and only the exit is new;
    * the CHECK dates are a, the data date before every ISO-week-opening session in (A, S], and d;
    * a basket name that fires the exit on ANY check date is out for the rest of the month (the
      "no refill until the re-pick" rule, kept without state by re-reading every check date);
    * survivors keep F4's equal 1/20 weight, re-priced at d's close; a freed slot is cash.

The check at a itself means a pick already in a loud fall at the re-pick is not bought that month.
That is the same rule read once more, not an entry filter of its own.

**THE EXIT SIGNAL** is M0161's, unchanged: M0158's ten-session market-model residual divided by
the stock's own residual swing (fit on the 252 sessions before the window), and M0161's volume
ratio (mean share volume over the same ten sessions against the same 252). "Bottom tenth" is the
pool's 10th percentile of that score among the screened members at the check date; "loud" is a
ratio above 1.0, "quiet" at or below it.

**MEMBERS.** The allocator sees the members of d only, so the anchor pick is ranked on d's members.
An index deletion inside the month therefore drops the name a few days early; it is a handful of
names a year, no look-ahead (d's list is known at d), and the NONE arm carries it identically.

Every piece reads only bars dated at or before d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine import dates
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    RESIDMOM,
    ResidParams,
    ResidPrepared,
    build_grid,
    resid_lookback,
    residual_scores,
)
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20
from seer_engine.lab.methods.m0063_earnings_day_jump import WEEKLY_HOLD_FRAC_GOTRADE
from seer_engine.lab.methods.m0158_standardised_residual_reversal import (
    ZRevParams,
    zrev_lookback,
    zrev_scores,
)
from seer_engine.lab.methods.m0161_quiet_fall_reversal import (
    QuietPrepared,
    Z10,
    build_volume_grid,
    volume_ratios,
)
from seer_engine.sim.book import Target
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorRow,
    factor_rows,
    factor_weights,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 17)

Exit = Literal["none", "any", "loud", "quiet"]
_EXITS: tuple[str, ...] = ("none", "any", "loud", "quiet")
DECILE = 0.10  # the pool's bottom tenth by standardised two-week residual
VOL_CUT = 1.0  # two-week mean share volume over prior-year mean
#: Sessions between the month's anchor and the last data date of that month, at most (23 sessions
#: in the longest month), plus slack. Added to the lookback so the anchor's own windows are loaded.
ANCHOR_SLACK = 25


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class LoudExitParams:
    """``host`` is the momentum book, ``signal`` the exit's score windows, ``exit`` which fallers go."""

    host: ResidParams
    signal: ZRevParams
    exit: Exit = "loud"

    def __post_init__(self) -> None:
        if not isinstance(self.host, ResidParams):
            raise TypeError(f"host must be ResidParams, got {type(self.host).__name__}")
        if not isinstance(self.signal, ZRevParams):
            raise TypeError(f"signal must be ZRevParams, got {type(self.signal).__name__}")
        if self.exit not in _EXITS:
            raise ValueError(f"exit must be one of {_EXITS}, got {self.exit!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"exit": self.exit, "decile": str(DECILE), "vol_cut": str(VOL_CUT)}
        for k, v in self.host.as_dict().items():
            out[f"host.{k}"] = v
        for k, v in self.signal.as_dict().items():
            out[f"signal.{k}"] = v
        return out


def _check(params: object) -> LoudExitParams:
    if not isinstance(params, LoudExitParams):
        raise TypeError(f"params must be LoudExitParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the clock


def anchor_and_checks(data_date: date) -> tuple[date, tuple[date, ...]]:
    """The month's anchor data date and every check date from it through ``data_date``."""
    session = dates.next_session(data_date)
    month = dates.sessions(date(session.year, session.month, 1), session)
    first = month[0]
    anchor = dates.prev_session(first)
    checks = {anchor, data_date}
    for s in month[1:]:
        if s.isocalendar()[:2] != dates.prev_session(s).isocalendar()[:2]:
            checks.add(dates.prev_session(s))
    return anchor, tuple(sorted(c for c in checks if c <= data_date))


# --------------------------------------------------------------------------- the exit


def fired(scores: Mapping[str, float], ratios: Mapping[str, float], basket: AbstractSet[str],
          exit: Exit) -> frozenset[str]:
    """The basket names the exit acts on, given one check date's pool scores and volume ratios."""
    if exit == "none" or not scores:
        return frozenset()
    cut = float(np.quantile(np.fromiter(scores.values(), dtype=np.float64), DECILE))
    low = {s for s in basket if s in scores and scores[s] <= cut}
    if exit == "any":
        return frozenset(low)
    if exit == "loud":
        return frozenset(s for s in low if s in ratios and ratios[s] > VOL_CUT)
    return frozenset(s for s in low if s in ratios and ratios[s] <= VOL_CUT)


def _close_at(h: History | None, data_date: date) -> float | None:
    """The last close dated at or before ``data_date``."""
    if h is None or len(h) == 0:
        return None
    k = int(np.searchsorted(h.dates, as_day(data_date), side="right")) - 1
    if k < 0:
        return None
    c = float(h.close[k])
    return c if np.isfinite(c) and c > 0.0 else None


# --------------------------------------------------------------------------- the allocator


class LoudFallExitAllocator:
    """M0007-N20-RAW's monthly picks, re-read weekly, minus the holdings in a (loud) fall.

    Held symbols get no special treatment and nothing is remembered: each weekly decision rebuilds
    the month's basket and every check since the anchor from bars alone.
    """

    id = "M0204"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(resid_lookback(p.host), zrev_lookback(p.signal)) + ANCHOR_SLACK

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return tuple(sorted({*RESIDMOM.symbols(p.host), p.signal.market}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _basket(self, rows: list[FactorRow], scores: Mapping[str, float],
                p: LoudExitParams) -> list[FactorRow]:
        scorable = [r for r in rows if r.symbol in scores and r.symbol not in EXCLUDED]
        return sorted(scorable, key=lambda r: (-scores[r.symbol], r.symbol))[: p.host.inner.top]

    def _decide(self, history: Mapping[str, History], rows_at, grid, vols, data_date: date,
                p: LoudExitParams) -> tuple[Target, ...]:
        anchor, checks = anchor_and_checks(data_date)
        if grid is None or not trend_on(history, anchor, p.host.inner):
            return ()
        rows = rows_at(anchor, p.host.inner)
        if not rows:
            return ()
        chosen = self._basket(rows, residual_scores(grid, [r.symbol for r in rows], anchor, p.host), p)
        if not chosen:
            return ()
        weights = factor_weights(chosen, p.host.inner)
        names = frozenset(r.symbol for r in chosen)
        out_names: set[str] = set()
        if p.exit != "none" and vols is not None:
            for w in checks:
                pool = [r.symbol for r in rows_at(w, p.signal.inner)]
                if not pool:
                    continue
                scores = zrev_scores(grid, pool, w, p.signal)
                ratios = {} if p.exit == "any" else volume_ratios(grid, vols, pool, w, p.signal)
                out_names |= fired(scores, ratios, names - out_names, p.exit)
        out: list[Target] = []
        for row, weight in zip(chosen, weights, strict=True):
            if weight is None or row.symbol in out_names:
                continue
            close = _close_at(history.get(row.symbol), data_date)
            if close is None:
                continue
            target = target_from_close(row.symbol, close, weight)
            if target is not None:
                out.append(target)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        grid = build_grid(history, p.host.market)
        vols = None if grid is None else build_volume_grid(history, grid)

        def rows_at(day: date, inner) -> list[FactorRow]:
            return factor_rows({s: h.upto(day) for s, h in history.items()}, members, day, inner)

        return self._decide(history, rows_at, grid, vols, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> QuietPrepared:
        return QuietPrepared(ResidPrepared(history, prepare_factor(history)))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, QuietPrepared):
            raise TypeError(f"prepared must be QuietPrepared, got {type(prepared).__name__}")
        p = _check(params)
        resid = prepared.resid

        def rows_at(day: date, inner) -> list[FactorRow]:
            return resid.factor.rows_on(members, day, inner)

        return self._decide(resid.history, rows_at, resid.grid(p.host.market),
                            prepared.volumes(p.host.market), data_date, p)


LOUDEXIT = LoudFallExitAllocator()


def _v(suffix: str, exit: Exit, rationale: str) -> Candidate:
    return Candidate(id=f"M0204-{suffix}", family="M0204", rules=WEEKLY_HOLD_FRAC_GOTRADE,
                     allocator=LOUDEXIT, params=LoudExitParams(RAW20, Z10, exit),
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0204",
    name=("Sell a momentum holding that falls on heavy trading: the residual-momentum book with a "
          "weekly loud-fall exit"),
    family="stock-single-name-brake",
    source_kind="variation",
    parent_id="M0161",
    source_ref=(
        "M0161 (quiet vs loud fallers) for the signal; M0007-N20-RAW / M0032-N20-RAW-FRAC-GT for the "
        "host book; Conrad, Hameed & Niden 1994, J. Finance 49(4); Da, Liu & Schaumburg 2014, "
        "Management Science 60(3); Lee & Swaminathan 2000, J. Finance 55(5) 'Price momentum and "
        "trading volume'"
    ),
    hypothesis=(
        "Published 1994-2014, so the volume-conditioned continuation of news-driven falls was public "
        "for most of the dev window. M0161 found big index members falling on above-normal share "
        "volume keep falling (its loud-fall book's worst fall 37% vs 24% for the quiet one). The "
        "residual-momentum book (M0007-N20-RAW at real fees and fractional shares, M0032: 13.7% a "
        "year on the owner's deposits vs SPY's 7.2%, worst fall 20.6%) skips the last month in its "
        "ranking, so a holding collapsing on news is invisible to it until the next re-pick. RULE: "
        "hold the same top-20 raw residual-momentum picks, ranked at the month's start with the "
        "SPY-200 switch read monthly, and at every weekly check drop to cash any holding whose "
        "ten-session standardised market-model residual is in the bottom tenth of the screened pool "
        "AND whose ten-session mean share volume is above its prior-year mean; no refill until the "
        "next monthly re-pick. Clock: weekly rank cadence, fractional, Gotrade's real fees "
        "(weekly-hold-frac-gotrade), because the split monthly/weekly preset only rescales total "
        "weight. Arms: LOUD (main), ANY (the bottom-tenth exit with no volume condition: the "
        "control for the volume split), QUIET (the other half: falls on below-normal volume, which "
        "M0161 says bounce, so it should do worst), NONE (the parent's picks on this weekly clock "
        "with no exit: the clean control). Predicted: the exit fires on roughly one holding a month; "
        "LOUD keeps NONE's return within a point a year and trims its worst fall by 2-4 points to "
        "under 20%; LOUD beats QUIET by at least a point a year (otherwise volume says nothing). "
        "Success: LOUD beats NONE on worst fall without losing more than a point a year, beats SPY "
        "on the deposits, and has a positive edge in 2009-2015. Assumptions: d's member list used "
        "for the anchor pick; decile and volume cut fixed at 10% and 1.0 from M0161, not tuned."
    ),
    expected_failure=(
        "Short-horizon losers bounce on average, so selling a two-week loser is a reversal bet with "
        "the sign wrong; the volume condition is meant to keep only the news-driven falls, but if it "
        "does not separate them every exit arm trails NONE by 1-3 points a year, and QUIET and LOUD "
        "look alike. Fees: each exit is an extra sale of a $30-200 slot plus the cash drag until the "
        "re-pick. The brake will sell bottoms in V-shaped recoveries (spring 2009, autumn 1998) where "
        "the whole tape falls on heavy volume, though the residual and pool-relative cut should "
        "spare most market-wide falls. The momentum book already lagged SPY in 2009-2015 on dev, and "
        "an exit cannot add return there. Promotion is not available: this line runs through M0007, "
        "test-failed, and the book moves with the test-failed momentum books (hard gate kin), so any "
        "dev-eligible arm is a by-product and not a candidate."
    ),
    candidates=(
        _v("LOUD", "loud",
           "Weekly exit of holdings in the pool's bottom-tenth two-week residual on above-normal volume"),
        _v("ANY", "any",
           "Same exit with no volume condition: does the volume split add anything?"),
        _v("QUIET", "quiet",
           "Exit only the bottom-tenth fallers on below-normal volume: the side that should bounce"),
        _v("NONE", "none",
           "The parent's monthly picks on this weekly clock with no exit: the clean control"),
    ),
    seen_keys=(
        "concept:loud-fall-exit",
        "concept:volume-conditioned-exit",
        "concept:momentum-news-fall-exit",
    ),
)
