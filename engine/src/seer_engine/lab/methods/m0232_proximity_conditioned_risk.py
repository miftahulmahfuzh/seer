"""M0232 — Risk pays only near the high: volatility sorted inside nearness-to-the-52-week-high bands.

Source: Chen, Chen, Tu, Wang & Wang (2026), "Proximity to the 52-week high and the risk-return
trade-off", Journal of Economic Dynamics and Control (S0165188926000321); reserved by Sera
20261019-0720 as a variation of M0015.

The paper's claim is not that risk pays, and not that it does not. It is that the SIGN of the
risk-return relation depends on where a stock sits relative to its own 52-week high. Investors
anchor on that high: a price far below it puts them in the domain of losses, where they turn
risk-seeking and overpay for volatile names, so volatility is punished there; a price near the
high puts them in the domain of gains, where they turn risk-averse and underpay for volatile
names, so volatility is rewarded there. Both halves are cross-sectional, so the honest test is a
conditional double sort -- proximity first, risk second -- with the tilt flipping between groups.

This lab already knows the two unconditional halves and both lost. Plain nearness to the high
(M0015) earned about what SPY earned, MAR 0.58 at best: a good brake, a poor engine. Buying the
most volatile names outright (the lottery-avoidance family) tops out at MAR 0.45. So the whole
question here is whether CONDITIONING turns a losing signal into a winning one, and the arms are
built so that one comparison answers it.

The frame, identical in every arm: F4's member screen (close >= $5, 20-day mean dollar volume >
$20M), the SPY 200-day trend switch (all cash under it), twenty equal slots, asked monthly, in
fractional shares at Gotrade's real fees on the owner's monthly top-up. Only the choosing differs.

    * NEARNESS. ``close[d] / max(close over the last 252 sessions)``, in (0, 1], M0015's
      ``nearness`` function verbatim -- closes, not intraday highs, because a close-to-close high
      cannot be set by one stray print.
    * THE BANDS. Each month the screened, nearness-scorable members are sorted ascending by
      (nearness, 12-1 momentum, symbol) and cut into five bands of equal count by rank. Band 4 is
      the fifth nearest their high, band 0 the fifth furthest below it. Ties at nearness 1.0 are
      common in a strong market, and the momentum tiebreak decides them; that is a choice, written
      down before any result, and it means the "near" band leans to the stronger of the tied names.
    * THE RISK SORT. Inside the chosen band, the twenty highest (``hivol``) or lowest (``lovol``)
      60-session return volatility, F4's own ``vol`` column, ties by symbol.
    * THE WITHIN-FRAME CONTROLS. ``near`` holds the twenty highest-nearness names across the whole
      pool, which is M0015-N20's ranking re-measured in fractional shares at real fees so the
      comparison with plain proximity needs no cost translation. ``placebo`` holds twenty names
      drawn from the same pool in a fixed hash order (M0187's ``draw``) redrawn each month, so it
      pays the same fees and runs under the same switch while knowing nothing about prices.

A band is a fifth of the screened pool, which was measured on the dev store before this file was
written: 64-97 names in 1996 and 392-401 by 2015, so a band holds its full twenty slots from 1997
on and 12-19 of them in 1996. Thin bands leave the unfilled slots in cash rather than reaching
outside the band, so exposure stays honest about what the band could offer; the two whole-pool
controls are never thin, which flatters them slightly in 1996 alone.

Pure: every read is of bars dated <= ``data_date``, and the hash is a function of its inputs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0015_52week_high import HIGH_N, nearness
from seer_engine.lab.methods.m0187_placebo_hash_order import draw
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 19)

NBANDS = 5  # quintiles of nearness; band 4 is nearest the high, band 0 furthest below it
PICKS: tuple[str, ...] = ("hivol", "lovol", "near", "placebo")


@dataclass(frozen=True, slots=True)
class ProxRiskParams:
    """``inner`` is F4's screen, book size, weighting and switch; ``band`` the nearness fifth an
    arm may pick from (None = the whole screened pool); ``pick`` how it chooses inside it."""

    inner: FactorParams
    high_n: int = HIGH_N
    band: int | None = NBANDS - 1
    pick: str = "hivol"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if isinstance(self.high_n, bool) or not isinstance(self.high_n, int) or self.high_n < 20:
            raise ValueError(f"high_n must be an int >= 20, got {self.high_n!r}")
        if self.band is not None:
            if isinstance(self.band, bool) or not isinstance(self.band, int):
                raise TypeError(f"band must be None or an int, got {type(self.band).__name__}")
            if not 0 <= self.band < NBANDS:
                raise ValueError(f"band must be in [0, {NBANDS}), got {self.band}")
        if self.pick not in PICKS:
            raise ValueError(f"pick must be one of {PICKS}, got {self.pick!r}")
        if self.pick in ("near", "placebo") and self.band is not None:
            raise ValueError(f"{self.pick!r} draws from the whole pool; leave band None")
        if self.pick not in ("near", "placebo") and self.band is None:
            raise ValueError("a risk sort needs a nearness band")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")
        if self.pick != "placebo" and self.seed != 0:
            raise ValueError("seed is for the placebo arm only")

    def as_dict(self) -> dict[str, str]:
        out = {"high_n": str(self.high_n), "nbands": str(NBANDS),
               "band": "all" if self.band is None else str(self.band),
               "pick": self.pick, "seed": str(self.seed),
               "band_order": "nearness,momentum,symbol", "thin_band": "cash"}
        if self.pick == "placebo":
            out["hash"] = "blake2b-8"
            out["redraw"] = "monthly"
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> ProxRiskParams:
    if not isinstance(params, ProxRiskParams):
        raise TypeError(f"params must be ProxRiskParams, got {type(params).__name__}")
    return params


def prox_lookback(params: ProxRiskParams) -> int:
    return max(factor_lookback(params.inner), params.high_n)


def nearness_order(rows: Sequence[FactorRow], near: Mapping[str, float]) -> list[FactorRow]:
    """The scorable rows, nearest the high LAST: ascending nearness, then momentum, then symbol."""
    pool = [r for r in rows if r.symbol in near and r.symbol not in EXCLUDED]
    return sorted(pool, key=lambda r: (near[r.symbol], r.momentum, r.symbol))


def band_of(order: Sequence[FactorRow]) -> dict[str, int]:
    """Each symbol's nearness fifth by rank in ``order``; band 0 furthest below its high."""
    n = len(order)
    return {r.symbol: k * NBANDS // n for k, r in enumerate(order)}


def choose(order: Sequence[FactorRow], near: Mapping[str, float], p: ProxRiskParams,
           data_date: date) -> list[FactorRow]:
    """The arm's rows, in the order it wants them. Fewer than ``top`` means cash in the rest."""
    top = p.inner.top
    if p.pick == "near":
        return list(reversed(order))[:top]
    if p.pick == "placebo":
        return sorted(order, key=lambda r: (draw(p.seed, r.symbol, data_date), r.symbol))[:top]
    band = band_of(order)
    inside = [r for r in order if band[r.symbol] == p.band]
    inside.sort(key=lambda r: (-r.vol if p.pick == "hivol" else r.vol, r.symbol))
    return inside[:top]


def _near_map(history: Mapping[str, History], rows: Sequence[FactorRow], data_date: date,
              n: int) -> dict[str, float]:
    out: dict[str, float] = {}
    for r in rows:
        v = nearness(history, r.symbol, data_date, n)
        if v is not None:
            out[r.symbol] = v
    return out


def _targets(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
             p: ProxRiskParams) -> tuple[Target, ...]:
    near = _near_map(history, rows, data_date, p.high_n)
    order = nearness_order(rows, near)
    if len(order) < NBANDS:  # too few names to cut into bands at all
        return ()
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for row in choose(order, near, p, data_date):
        t = target_from_close(row.symbol, row.close, w)
        if t is not None:
            out.append(t)
    return tuple(out)


@dataclass(frozen=True, slots=True)
class ProxPrepared:
    """The whole history (nearness is read from it) plus F4's rolling columns."""

    history: Mapping[str, History]
    factor: FactorPrepared


class ProxRiskAllocator:
    """Twenty names chosen by 60-session volatility inside a nearness-to-the-52-week-high fifth,
    or one of the two whole-pool controls. Held symbols get no special treatment: the targets are
    exactly the new set, so a name that leaves the band is sold at the monthly rebalance."""

    id = "M0232"

    def lookback(self, params: Any) -> int:
        return prox_lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return () if p.inner.trend is None else (p.inner.trend[0],)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        if not rows:
            return ()
        return _targets(history, rows, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> ProxPrepared:
        return ProxPrepared(dict(history), prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ProxPrepared):
            raise TypeError(f"prepared must be ProxPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        if not rows:
            return ()
        return _targets(prepared.history, rows, data_date, p)


PROX = ProxRiskAllocator()

N20 = FactorParams(rank="momentum", top=20, trend=("SPY", 200))  # screen, book size and switch only


def _v(suffix: str, params: ProxRiskParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0232-{suffix}", family="M0232", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=PROX, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0232",
    name="Risk pays only near the high: the most volatile stocks among those closest to their 52-week high",
    family="stock-52week-high",
    source_kind="paper",
    source_ref=(
        "Chen, Chen, Tu, Wang & Wang (2026), 'Proximity to the 52-week high and the risk-return "
        "trade-off', Journal of Economic Dynamics and Control, S0165188926000321; "
        "reserved by Sera 20261019-0720; frame of M0015, placebo of M0187"
    ),
    parent_id="M0015",
    hypothesis=(
        "The paper finds a POSITIVE risk-return relation among stocks near their 52-week high and "
        "a NEGATIVE one among stocks far below it: investors anchor on the high, turning "
        "risk-seeking when the price is far below it (overpaying for volatile losers) and "
        "risk-averse when it is near (underpaying for volatile winners). That implies a "
        "conditional double sort this lab has never run: proximity first, risk second, with the "
        "sign of the risk tilt flipping between the two groups. Arms, all twenty equal slots, "
        "monthly, behind the shared SPY 200-day switch, in fractional shares at Gotrade's real "
        "fees on the owner's monthly top-up, drawn from the index members that pass F4's "
        "liquidity screen: NEAR-HIVOL, the twenty highest 60-session volatility names inside the "
        "top fifth by price-to-52-week-high ratio; NEAR-LOVOL, the same group's calmest twenty, "
        "the within-group control the paper says should lose; FAR-LOVOL, the calmest twenty "
        "inside the bottom fifth by proximity, the other side of the paper's claim; FAR-HIVOL, "
        "its control; NEAR-ALL, the twenty nearest their high across the whole pool, which is "
        "M0015-N20's ranking re-measured at real fees; and PLC1, a same-frame fixed-random-order "
        "placebo. The lab already knows plain 52-week-high proximity (M0015, MAR 0.58) and "
        "already knows that high-volatility picks lose outright (stock-lottery-avoidance, best "
        "MAR 0.45), so the whole question is whether CONDITIONING the risk tilt on proximity "
        "turns a losing signal into a winning one. SUCCESS: NEAR-HIVOL beats NEAR-LOVOL by 3 or "
        "more points a year, beats the placebo by 2, keeps a positive lead over SPY in 2009-2015, "
        "and its worst fall stays under the dev screen; FAR-LOVOL beating FAR-HIVOL confirms the "
        "sign flip rather than a plain volatility effect."
    ),
    expected_failure=(
        "NEAR-HIVOL only matches the placebo and FAR-LOVOL beats everything, which would mean the "
        "paper's effect is a small-cap long-short result that does not survive a large-cap "
        "long-only book at real fees, and the 52-week-high family should be closed. The "
        "mechanisms behind that: the high-volatility half of any cross-section in this universe "
        "is the lab's lottery-avoidance finding in disguise, and twenty of the most volatile "
        "names in any fifth is the deepest-falling book the frame can build, so NEAR-HIVOL most "
        "likely clears the dev screen on return and breaks it on the worst fall; and nearness "
        "ties at 1.0 in a strong market push the momentum tiebreak into the band definition, so "
        "the near band may quietly become a momentum band. The paper is dated 2026 but the "
        "anchoring effect it rests on has been published since 2004, so expect the dev window to "
        "flatter it and 2009-2015 to be the honest read. Check the survivorship-check store "
        "before concluding: the most volatile names are exactly where the dead companies the dev "
        "store cannot price are hiding, so NEAR-HIVOL and FAR-HIVOL should lose the most there."
    ),
    candidates=(
        _v("NEAR-HIVOL", ProxRiskParams(N20, band=4, pick="hivol"),
           "The twenty most volatile names among the fifth closest to their 52-week high"),
        _v("NEAR-LOVOL", ProxRiskParams(N20, band=4, pick="lovol"),
           "The calmest twenty in the same fifth: the paper says this side should lose"),
        _v("FAR-LOVOL", ProxRiskParams(N20, band=0, pick="lovol"),
           "The calmest twenty among the fifth furthest below their high: the sign flip"),
        _v("FAR-HIVOL", ProxRiskParams(N20, band=0, pick="hivol"),
           "The most volatile twenty in that same far fifth: its control"),
        _v("NEAR-ALL", ProxRiskParams(N20, band=None, pick="near"),
           "Plain proximity, no risk sort: M0015-N20's ranking at Gotrade's real fees"),
        _v("PLC1", ProxRiskParams(N20, band=None, pick="placebo", seed=1),
           "Placebo: twenty names from the same pool in a fixed hash order, redrawn monthly"),
    ),
    seen_keys=(
        "concept:proximity-conditioned-risk-return",
        "concept:nearness-volatility-double-sort",
        "pii:S0165188926000321",
    ),
)
