"""M0195 — Stand-out losers among the 100 busiest members, with a fast way back in after the switch.

Source: variation of M0192 (Cosemans & Frehen 2021, JFE 140, after Bordalo, Gennaioli & Shleifer).
Idea: M0192's low-salience book (buy the members whose loudest days last month were losses) beat
plain one-month reversal by about 5 points a year and SPY by 2.8 on dev, but trailed SPY by 3-4
points a year over 2009-2015. Its analysis named two frame problems, not signal problems: equal
slots across every screened member lean small against SPY's big-company drift (insight 91), and
the 200-day switch held the book in cash through the spring-2009 rebound that the no-switch arm
used to lead SPY in 2009-2015. This method changes the frame and leaves the signal alone.

The pool. On a re-pick date d, F4's screen ($5 / $20M) gives the eligible members; of those, the
100 with the highest 20-day mean close x volume on d (ties by symbol) are the pool (M0178's
``busiest``). The salience score is M0192's ``scores`` unchanged -- 21 sessions, theta 0.1,
delta 0.7, and the "market" each day is the equal-weighted average of the names being scored, so
in the pooled variants it is the average of the 100 busiest. That is an assumption written now:
the paper's market is the whole equal-weighted cross-section, and salience is measured against
what investors in these stocks saw beside them. The band (keep 80 of 40), the SPY slots and the
equal weights are M0192's ``choose``.

The switch, one of three, always explicit (``FactorParams.trend`` is None in every variant and the
switch lives here, so F4's default 200-day gate can never sneak in):

    * ``"none"``: always invested.
    * ``"slow"``: F4's own gate, cash unless SPY closes above its 200-day average.
    * ``"fast"``: cash only while SPY closes below BOTH its 200-day and its 50-day averages.
      Stateless reading of "out under the 200-day, back in as soon as it closes over the 50-day":
      in a rising market the 50-day sits above the 200-day, so a close under the 200-day is under
      both and the book goes to cash exactly when ``"slow"`` would; after a fall the 50-day drops
      under the 200-day, and the first close back over the 50-day re-opens the book months before
      the 200-day would. No latch, no state: the gate is a function of SPY's closes up to d.

Controls on the same frame, so the idea is judged against more than SPY (Sera's note, batch
20261017-1808): ``signal="reversal"`` is plain one-month reversal (lowest 21-day return), and
``signal="placebo"`` fills the same pool, band and slots in a fixed hash order of (seed, symbol,
month) -- M0187's ``draw`` -- over exactly the names the salience score could rank, so it is the
frame with no information. The placebo is re-drawn each month, so a held name stays with
probability about 80% (keep 80 of a pool of 100), close to the band's turnover on a noisy signal.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees on the owner's
monthly deposits. Every piece reads bars dated at or before d only.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import ResidPrepared, ReturnGrid, build_grid
from seer_engine.lab.methods.m0178_busiest_low_correlation import busiest
from seer_engine.lab.methods.m0187_placebo_hash_order import draw
from seer_engine.lab.methods.m0192_salience import SalienceParams, choose, salience_lookback, scores
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    FactorRow,
    factor_rows,
    prepare_factor,
)
from seer_engine.strategies.indicators import sma_window

ADDED = date(2026, 10, 17)
SWITCHES = ("none", "slow", "fast")
SLOW_N = 200
FAST_N = 50


@dataclass(frozen=True, slots=True)
class BusySalienceParams:
    """``sal`` is M0192's book (its ``inner.trend`` must be None); ``pool`` the busiest-member cut,
    0 for every screened member; ``switch`` the market gate; ``placebo`` replaces the score with
    the hash order of ``seed`` over the names ``sal`` could score."""

    sal: SalienceParams
    pool: int = 100
    switch: str = "fast"
    placebo: bool = False
    seed: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.sal, SalienceParams):
            raise TypeError(f"sal must be SalienceParams, got {type(self.sal).__name__}")
        if self.sal.inner.trend is not None:
            raise ValueError("sal.inner.trend must be None; the switch is set by `switch`")
        for name in ("pool", "seed"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.pool != 0 and self.pool < self.sal.keep:
            raise ValueError(f"pool must be 0 or >= keep, got {self.pool} < {self.sal.keep}")
        if self.switch not in SWITCHES:
            raise ValueError(f"switch must be one of {SWITCHES}, got {self.switch!r}")
        if not isinstance(self.placebo, bool):
            raise TypeError(f"placebo must be a bool, got {type(self.placebo).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"pool": str(self.pool), "switch": self.switch, "placebo": str(self.placebo),
               "seed": str(self.seed)}
        for k, v in self.sal.as_dict().items():
            out[f"sal.{k}"] = v
        return out


def _check(params: object) -> BusySalienceParams:
    if not isinstance(params, BusySalienceParams):
        raise TypeError(f"params must be BusySalienceParams, got {type(params).__name__}")
    return params


def _sma(h: History, i: int, n: int) -> float | None:
    if i + 1 < n:
        return None
    return float(sma_window(h.close[i + 1 - n : i + 1].reshape(1, n), n)[0])


def switch_on(history: Mapping[str, History], data_date: date, p: BusySalienceParams) -> bool:
    """The market gate on ``data_date``; False when SPY has no bar dated d or too few bars."""
    if p.switch == "none":
        return True
    h = history.get(p.sal.market)
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None:
        return False
    close = float(h.close[i])
    slow = _sma(h, i, SLOW_N)
    if slow is None:
        return False
    if p.switch == "slow":
        return close > slow
    fast = _sma(h, i, FAST_N)
    return fast is not None and (close > slow or close > fast)


def ranked(grid: ReturnGrid, rows: list[FactorRow], data_date: date,
           p: BusySalienceParams) -> dict[str, float]:
    """The score ``choose`` ranks on (lowest first): salience, reversal, or the placebo's hash."""
    sc = scores(grid, [r.symbol for r in rows], data_date, p.sal)
    if not p.placebo:
        return sc
    order = sorted(sc, key=lambda s: (draw(p.seed, s, data_date), s))
    return {s: float(k) for k, s in enumerate(order)}


class BusySalienceAllocator:
    """M0192's salience book inside the busiest members, behind a chosen market switch."""

    id = "M0195"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(salience_lookback(p.sal), SLOW_N if p.switch != "none" else 0)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return (_check(params).sal.market,)

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_check(params).sal.market,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _targets(self, history: Mapping[str, History], rows: list[FactorRow],
                 grid: ReturnGrid | None, data_date: date, held: frozenset[str],
                 p: BusySalienceParams) -> tuple[Target, ...]:
        if p.pool:
            rows = busiest(rows, p.pool)
        if not rows or grid is None:
            return ()
        return choose(history, rows, ranked(grid, rows, data_date, p), data_date, held, p.sal)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not switch_on(history, data_date, p):
            return ()
        rows = factor_rows(history, members, data_date, p.sal.inner)
        return self._targets(history, rows, build_grid(history, p.sal.market), data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return ResidPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not switch_on(prepared.history, data_date, p):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.sal.inner)
        return self._targets(prepared.history, rows, prepared.grid(p.sal.market), data_date,
                             held, p)


BUSY_SALIENCE = BusySalienceAllocator()

# the rank is unused: only F4's screen and the book size; trend None, the switch is ours
N40 = FactorParams(rank="momentum", top=40, trend=None)


def _p(switch: str, pool: int = 100, signal: str = "salience",
       placebo: bool = False) -> BusySalienceParams:
    return BusySalienceParams(SalienceParams(N40, keep=80, signal=signal), pool=pool,
                              switch=switch, placebo=placebo)


def _v(suffix: str, params: BusySalienceParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0195-{suffix}", family="M0195", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BUSY_SALIENCE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0195",
    name=("Stand-out losers among the big companies, with a fast way back in: salience in the 100 "
          "most traded members, out under SPY's 200-day average, back above its 50-day"),
    family="stock-salience",
    source_kind="variation",
    source_ref="variation of M0192 (Cosemans & Frehen 2021, JFE 140, 460-483)",
    parent_id="M0192",
    hypothesis=(
        "M0192's salience book (buy the members whose stand-out days last month were losses) beat "
        "plain reversal by about 5 points a year and SPY by 2.8 on dev, but trailed SPY by 3-4 "
        "points a year over 2009-2015 and fell 29-34%. Two frame problems, not signal problems: "
        "equal slots across all screened members lean small against SPY's big-company drift "
        "(insight 91), and the 200-day switch kept the book in cash through the spring-2009 "
        "rebound that the no-switch arm used to lead SPY by 4.4 points a year in 2009-2015. "
        "Published 2021, so the dev window is pre-publication but inside the paper's sample. "
        "Variation: the same salience score (theta 0.1, delta 0.7, 21 sessions, measured against "
        "the equal-weighted average of the names scored), ranked only inside the 100 screened "
        "members with the highest 20-day dollar volume, 40 names at 2.5% with a keep band of 80, "
        "unfilled slots in SPY, monthly, fractional shares at Gotrade's real fees on the owner's "
        "monthly top-up. Switch 'fast': cash only while SPY closes under both its 200-day and its "
        "50-day average (out under the 200-day, back in on the first close over the 50-day). "
        "Variants, every one with its switch set explicitly: B100-FAST (the idea), B100-SLOW "
        "(plain 200-day switch), B100-NONE (no switch), ALL-FAST (no busiest cut, every screened "
        "member), and two controls on the B100-FAST frame: REV-B100-FAST (plain one-month "
        "reversal) and PLC-B100-FAST (the same pool filled in a fixed hash order, a placebo). "
        "Judged against SPY TR and against the placebo and the equal-weight placebo book M0187 "
        "(+10.3-11.0% a year funded with its switch). Success: B100-FAST beats SPY TR on the "
        "deposits with worst fall <= 25%, PF >= 1.3, DSR >= 0.90, a majority of walk-forward "
        "folds, a positive 2009-2015 edge, and a clear gap over both its reversal and placebo "
        "controls; its beta to SPY is reported."
    ),
    expected_failure=(
        "The big-company pool shrinks the salience spread: salience effects are larger in small, "
        "attention-poor stocks, and the 100 busiest names are the most watched in the market, so "
        "the gap over the placebo may close to nothing. Narrowing to 100 names also leaves 40 "
        "slots drawn from a pool of 100, so the book is 40% of a near-index basket and its "
        "return sits close to an equal-weight big-company book (RSP-like), which still lags SPY's "
        "cap-weighted drift in 2013-2015. The fast re-entry whipsaws: a first close over the "
        "50-day average in a bear market (late 2001, spring 2002, mid and late 2008) buys a "
        "bear-market rally, and the 200-day exit fires again only after the next leg down, so "
        "B100-FAST may fall more than B100-SLOW and past 25%. The no-switch arm falls past 50% "
        "in 2008 as M0192's did. Monthly turnover on 40 small slots at Gotrade's minimum fees "
        "eats a one-month effect. If B100-FAST does not lead SPY in 2009-2015 and beat its "
        "placebo, the salience family is a pre-2009, small-company effect and should be left."
    ),
    candidates=(
        _v("B100-FAST", _p("fast"),
           "Lowest salience in the 100 busiest members, 40 names, band 80, out under SPY's 200-day "
           "and back over its 50-day"),
        _v("B100-SLOW", _p("slow"),
           "The same book behind the plain SPY 200-day switch"),
        _v("B100-NONE", _p("none"),
           "The same book with no switch at all"),
        _v("ALL-FAST", _p("fast", pool=0),
           "No busiest cut: every screened member, fast switch (M0192-S-N40 with the fast switch)"),
        _v("REV-B100-FAST", _p("fast", signal="reversal"),
           "Control: plain one-month reversal on the identical pool, band, slots and switch"),
        _v("PLC-B100-FAST", _p("fast", placebo=True),
           "Control: the same pool, band, slots and switch filled in a fixed hash order"),
    ),
    seen_keys=(
        "concept:salience-in-busiest-members",
        "concept:fast-reentry-switch-200-out-50-in",
    ),
)
