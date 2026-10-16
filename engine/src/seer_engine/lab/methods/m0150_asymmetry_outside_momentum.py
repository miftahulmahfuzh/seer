"""M0150 — Rank on temperament, but only among companies momentum is NOT buying.

Source: a variation of M0133 (the up/down participation spread behind the 200-day market switch),
reserved as a backlog idea by Sera batch 20261016-2004.

M0133-G40 is the best-shaped book the lab holds -- +13.5% a year on the owner's deposits against
SPY TR's +7.2%, a 21.6% worst fall, gains 2.63 times losses -- and it is refused promotion on
behaviour alone: its monthly returns, less their fit on SPY's, move with the test-failed
M0002-REL-85 at 0.8964 against the 0.85 bar (hardgate D14). M0146's measurement found the two
books share only 18.7% of their names month by month, against 15.3% if the rankings were
unrelated. Two readings of that fit the facts:

* **overlap**: the resemblance is carried by the minority of names both books hold -- the
  high-momentum, high-participation companies that dominate both curves in the months that
  matter;
* **temperament**: the resemblance is carried by the *kind* of company the spread rank selects,
  which behaves like a momentum stock whether or not it is one.

This method separates them by construction. Each month it takes F4's screened rows -- the very
rows both F4 momentum and M0133 already rank -- removes every company inside momentum's own top
``exclude_top`` (12-1 momentum descending, ties by symbol, exactly F4's ``rank_rows`` order), and
only then ranks what is left on the up-minus-down spread. The exclusion reads the same
point-in-time momentum column F4 computes, so it adds no data and no look-ahead. Everything else
is M0133's code, imported: the participation math, the gate, the asymmetric buy-back, the
weighting and the pricing. A difference from M0133 can only be the exclusion.

The four arms, every one gated, so the comparison against M0133 is the exclusion alone:

* ``X40-G40`` -- exclude momentum's top 40, hold 40, 200-day switch. The headline, paired with
  M0133-G40.
* ``X20-G40`` -- exclude only momentum's top 20 (the size of M0002-REL-85's own book), hold 40.
  The narrow exclusion: drops exactly the names the failed book could have held.
* ``X80-G40`` -- exclude momentum's top 80, about the top third of the ~262-name pool, hold 40.
  The dose-response arm. If the correlation is still at or above 0.85 here, the overlap reading
  is dead: nothing left in the book is a momentum name by any generous definition.
* ``X40-G20-UP63`` -- exclude top 40, hold 20, sell on the 200-day cross and buy back on a
  positive quarter: the exclusion applied to M0133's best arm, M0133-G20-UP63.

Assumptions, written before the run:

- "Momentum's top N" is taken over the screened rows that are ranked, not only over rows the
  spread can score. A name momentum would buy is excluded whether or not the participation
  estimate could read it.
- The excluded set is recomputed every check from that day's rows, never carried; a name that
  leaves momentum's top N becomes eligible again on the next re-pick.
- The momentum yardstick is F4's 12-1 (252 sessions, skip 21) because M0002-REL-85 ranks on it;
  the kin rule compares against that book.
- The exclusion never bars more than half the screened rows (``len(rows) // 2``). On the
  ~262-name pool that cap is ~131 and never binds even on the 80-name arm; it exists so a thin
  screen -- the early 1990s lookback, or the eight-name contract kit -- leaves the spread a pool
  to rank instead of an empty book. With ~262 screened names, excluding 80 still leaves ~180, so
  every arm can fill its slots; the recorded exposure will say if it ever could not.
- Reads only bars dated <= ``data_date``. Pure: no clock, no I/O, no randomness.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import build_grid
from seer_engine.lab.methods.m0110_downside_participation import CapturePrepared, targets_from_scores
from seer_engine.lab.methods.m0133_gated_updown_asymmetry import ASYM, N20, N40, AsymParams, asym_scores
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorRow, factor_rows

ADDED = date(2026, 10, 16)


@dataclass(frozen=True, slots=True)
class ExclParams:
    """M0133's whole configuration, plus how many of momentum's top names are barred from it."""

    asym: AsymParams
    exclude_top: int = 40

    def __post_init__(self) -> None:
        if not isinstance(self.asym, AsymParams):
            raise TypeError(f"asym must be AsymParams, got {type(self.asym).__name__}")
        if isinstance(self.exclude_top, bool) or not isinstance(self.exclude_top, int):
            raise TypeError(f"exclude_top must be an int, got {type(self.exclude_top).__name__}")
        if self.exclude_top < 1:
            raise ValueError(f"exclude_top must be >= 1, got {self.exclude_top}")

    def as_dict(self) -> dict[str, str]:
        out = {"exclude_top": str(self.exclude_top)}
        for key, v in self.asym.as_dict().items():
            out[f"asym.{key}"] = v
        return out


def _check(params: object) -> ExclParams:
    if not isinstance(params, ExclParams):
        raise TypeError(f"params must be ExclParams, got {type(params).__name__}")
    return params


def outside_momentum(rows: list[FactorRow], exclude_top: int) -> list[FactorRow]:
    """``rows`` less momentum's top ``exclude_top`` (F4's order: momentum desc, symbol asc).

    Never bars more than half the screened rows, so the spread always has a pool to rank.
    """
    k = min(exclude_top, len(rows) // 2)
    barred = {r.symbol for r in sorted(rows, key=lambda r: (-r.momentum, r.symbol))[:k]}
    return [r for r in rows if r.symbol not in barred]


class AsymmetryOutsideMomentumAllocator:
    """M0133's gated asymmetry book, ranked only over names outside momentum's top ``exclude_top``.

    The gate decision is M0133's and reads the full screened universe's existence (an empty screen
    holds nothing), then the exclusion narrows the rows the spread may pick from.
    """

    id = "M0150"

    def lookback(self, params: Any) -> int:
        return ASYM.lookback(_check(params).asym)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ASYM.symbols(_check(params).asym)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _pick(self, rows: list[FactorRow], grid: Any, data_date: date, p: ExclParams) -> tuple[Target, ...]:
        pool = outside_momentum(rows, p.exclude_top)
        if not pool:
            return ()
        return targets_from_scores(pool, asym_scores(grid, [r.symbol for r in pool], data_date, p.asym), p.asym)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        rows = factor_rows(history, members, data_date, p.asym.inner)
        if not rows or not ASYM._invested(history, data_date, held, p.asym):
            return ()
        grid = build_grid(history, p.asym.market)
        if grid is None:
            return ()
        return self._pick(rows, grid, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> CapturePrepared:
        return ASYM.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CapturePrepared):
            raise TypeError(f"prepared must be CapturePrepared, got {type(prepared).__name__}")
        p = _check(params)
        rows = prepared.factor.rows_on(members, data_date, p.asym.inner)
        if not rows or not ASYM._invested(prepared.history, data_date, held, p.asym):
            return ()
        grid = prepared.grid(p.asym.market)
        if grid is None:
            return ()
        return self._pick(rows, grid, data_date, p)


EXCL = AsymmetryOutsideMomentumAllocator()


def _v(suffix: str, params: ExclParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0150-{suffix}", family="M0150", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=EXCL, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0150",
    name="Rank on temperament, but only among companies momentum is NOT buying",
    family="stock-updown-asymmetry",
    source_kind="variation",
    source_ref=(
        "variation of M0133 (gated up/down participation spread), barring momentum's own top "
        "names from the pool before ranking; reserved by Sera batch 20261016-2004"
    ),
    parent_id="M0133",
    hypothesis=(
        "Measured 2026-10-14: the asymmetry rank and the plain 12-month momentum rank share only "
        "18.7% of their 40 names month by month, against 15.3% expected if the two rankings were "
        "unrelated -- they already pick almost entirely different companies out of the same "
        "~262-name screened pool. Yet the two books move together at 0.90 after the market's own "
        "move is taken out, which is what refuses the whole line. If the resemblance is carried "
        "by a minority of shared names rather than by the ranking itself, explicitly excluding "
        "them should break it at little cost. This method ranks on the same up-minus-down "
        "participation spread (M0133's code, imported) but first drops, each month, every company "
        "inside momentum's own top N on F4's 12-1 column: N=40 (headline, 40 names, paired with "
        "M0133-G40), N=20 (the failed M0002-REL-85's own book size), N=80 (about a third of the "
        "pool, the dose-response arm), and N=40 on M0133's best arm (20 names, positive-quarter "
        "buy-back). The exclusion is point-in-time from the same rows the book already builds. "
        "Every variant is gated, so the comparison against M0133 is the exclusion alone. Success: "
        "return and fall stay close to M0133-G40's (+13.5% a year funded, 21.6% fall) while the "
        "residual correlation against M0002-REL-85 drops under 0.85. The up/down capture measure "
        "is an old practitioner tool, not a dated academic publication; publication risk is low."
    ),
    expected_failure=(
        "The likeliest outcome is that the correlation barely moves. M0146 already showed the "
        "overlap is only 3.4 points above chance and that random 40-name books behind the same "
        "gate read at most 0.70 against the failed book, so the resemblance is probably carried "
        "by the temperament of the companies -- high-participation names that run with the "
        "market and give it back -- not by which ones. If X80-G40 still reads at or above 0.85, "
        "that is proven: nothing left is a momentum name, and no selection rule of this shape "
        "can be behaviourally free behind a market switch; the asymmetry-behind-a-switch line "
        "should then close for good. The second failure is cost: momentum's top names carry "
        "much of any trending book's return, so barring them may lower return and, if the "
        "remaining high-participation names are the laggards with high beta, deepen the fall. "
        "Third, survivorship: M0110's asymmetry arm lost 2.0 points a year on the fuller price "
        "history, so any dev pass is provisional. Fourth, the 2009-2015 stretch: the gate itself "
        "loses 6-11 points a year to SPY there, and removing the strongest names makes the book "
        "lean on the recovery even harder."
    ),
    candidates=(
        _v("X40-G40", ExclParams(AsymParams(N40, gate="sma200"), exclude_top=40),
           "Gated 40-name asymmetry book, momentum's top 40 barred: paired with M0133-G40"),
        _v("X20-G40", ExclParams(AsymParams(N40, gate="sma200"), exclude_top=20),
           "Gated 40, only momentum's top 20 barred: the failed book's own size"),
        _v("X80-G40", ExclParams(AsymParams(N40, gate="sma200"), exclude_top=80),
           "Gated 40, momentum's top 80 barred: dose response; nothing left is a momentum name"),
        _v("X40-G20-UP63", ExclParams(AsymParams(N20, gate="sma200-up63"), exclude_top=40),
           "M0133's best arm (20 names, positive-quarter buy-back) with momentum's top 40 barred"),
    ),
    seen_keys=(
        "concept:asymmetry-rank-excluding-momentum-top",
        "concept:overlap-vs-temperament-kin-test",
    ),
)
