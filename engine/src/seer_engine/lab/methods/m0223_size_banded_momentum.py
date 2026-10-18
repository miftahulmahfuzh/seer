"""M0223 — Momentum picked inside each size band: four names from each fifth of the index by size.

Source: variation of M0047, reserved by Sera 20261018-2051. M0047 sized M0032's twenty
residual-momentum picks by real market value and found it cost 2.5-3.3 points a year and turned
the 2009-2015 lead over SPY negative. Sizing moves money between the same names; it does not say
*where* in the size range the ranking earns. This method asks that directly by choosing the
names inside size bands, all at equal slots, so the arms differ only in which part of the index
the ranking is allowed to pick from.

What is the same as M0047-EQ: the SPY 200-day trend gate, F4's screen, M0032's raw cumulative
residual-momentum score, one share class per company (M0047's map), twenty equal slots, monthly,
fractional shares at Gotrade's real fees on the owner's monthly top-up. What this method adds:

    * SIZE BANDS. Each month the screened, scorable members whose point-in-time market value is
      known (one class per company, the higher-ranked class kept) are cut into five bands of equal
      count by ``market.market_value(symbol, data_date)``; band 0 is the smallest fifth. A member
      whose size is unknown that day takes part in no arm, the plain top-20 control included, so
      every arm draws from one universe. Assumption, written before any result: unknown sizes are
      dropped rather than guessed, because a guessed size would put a name in a guessed band.
    * HOW MANY FROM WHERE. ``bands`` names the bands an arm may pick from and ``per_band`` how
      many from each; ``per_band = 0`` means the top 20 from the union of the named bands,
      whatever band they sit in. A band with fewer scorable names than its quota leaves its
      unfilled slots in cash, so exposure is honest about thin bands.
    * THE MEANINGLESS CONTROL. The same bands and quota, with the names in each band drawn in a
      fixed hash order (M0187's ``draw``) keyed by the quarter (January, April, July, October
      draws), so a placebo book holds its names for a quarter unless they leave their band or the
      screen. If it matches the banded momentum book, the lead is the banding's, not the
      ranking's.

Market-aware (``market_fields = ("shares",)``): with no share counts it targets nothing, so ``lab
run`` refuses it on a store without company size. Pure: every read is of bars and filings dated
<= ``data_date`` and the hash is a function of its inputs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    FACTOR_SYMBOLS,
    ResidParams,
    resid_lookback,
    residual_scores,
)
from seer_engine.lab.methods.m0047_market_value_residual import (
    RANKING,
    MarketValueAllocator,
    SizePrepared,
    one_per_company,
)
from seer_engine.lab.methods.m0187_placebo_hash_order import draw
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED, trend_on

ADDED = date(2026, 10, 18)

NBANDS = 5
PICKS = ("residual", "placebo")


@dataclass(frozen=True, slots=True)
class BandParams:
    """M0032's ranking (``inner``), the size bands an arm may pick from, the quota per band
    (0 = the top ``inner.inner.top`` across the named bands), and the picker."""

    inner: ResidParams
    bands: tuple[int, ...] = tuple(range(NBANDS))
    per_band: int = 4
    picks: str = "residual"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, ResidParams):
            raise TypeError(f"inner must be ResidParams, got {type(self.inner).__name__}")
        if not isinstance(self.bands, tuple) or not self.bands:
            raise ValueError("bands must be a non-empty tuple")
        if any(isinstance(b, bool) or not isinstance(b, int) or not 0 <= b < NBANDS for b in self.bands):
            raise ValueError(f"bands must be ints in [0, {NBANDS}), got {self.bands!r}")
        if tuple(sorted(set(self.bands))) != self.bands:
            raise ValueError("bands must be sorted and distinct")
        if isinstance(self.per_band, bool) or not isinstance(self.per_band, int) or self.per_band < 0:
            raise ValueError(f"per_band must be a non-negative int, got {self.per_band!r}")
        if self.per_band and self.per_band * len(self.bands) != self.inner.inner.top:
            raise ValueError("per_band times the number of bands must equal the book size")
        if self.picks not in PICKS:
            raise ValueError(f"picks must be one of {PICKS}, got {self.picks!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")
        if self.picks == "residual" and self.seed != 0:
            raise ValueError("seed is for the placebo picks only")
        if self.picks == "placebo" and not self.per_band:
            raise ValueError("the placebo draws per band; give it a quota")

    def as_dict(self) -> dict[str, str]:
        out = {"nbands": str(NBANDS), "bands": ",".join(str(b) for b in self.bands),
               "per_band": str(self.per_band), "picks": self.picks, "seed": str(self.seed),
               "size": "market_value", "unknown_size": "excluded", "weighting": "equal",
               "one_class_per_company": "M0047"}
        if self.picks == "placebo":
            out["hash"] = "blake2b-8"
            out["redraw"] = "quarterly-jan-apr-jul-oct"
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> BandParams:
    if not isinstance(params, BandParams):
        raise TypeError(f"params must be BandParams, got {type(params).__name__}")
    return params


def size_bands(sizes: Mapping[str, float]) -> dict[str, int]:
    """Each symbol's band, 0 the smallest fifth, by rank of size (ties broken by symbol)."""
    order = sorted(sizes, key=lambda s: (sizes[s], s))
    n = len(order)
    return {s: k * NBANDS // n for k, s in enumerate(order)}


def quarter_anchor(d: date) -> date:
    """The first day of ``d``'s calendar quarter: the placebo's draw is fixed within it."""
    return date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)


def choose(order: Sequence[str], band: Mapping[str, int], p: BandParams,
           data_date: date) -> list[str]:
    """The arm's names: ``order`` is the residual ranking (best first) over the sized universe."""
    top = p.inner.inner.top
    allowed = set(p.bands)
    if not p.per_band:
        return [s for s in order if band[s] in allowed][:top]
    out: list[str] = []
    anchor = quarter_anchor(data_date)
    for b in p.bands:
        members = [s for s in order if band[s] == b]
        if p.picks == "placebo":
            members.sort(key=lambda s: (draw(p.seed, s, anchor), s))
        out.extend(members[: p.per_band])
    return out


class SizeBandAllocator(MarketValueAllocator):
    """Residual-momentum (or hash-order placebo) picks chosen inside point-in-time size bands,
    equal slots. Shares M0047's preparation; no share counts: no targets."""

    id = "M0223"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        return resid_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params).inner
        return tuple(sorted({p.market, *FACTOR_SYMBOLS(p.inner)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: SizePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: Any) -> tuple[Target, ...]:
        p = _check(p)
        market = prepared.market
        if market is None or len(market.shares) == 0:  # no company size: target nothing
            return ()
        resid = prepared.resid
        if not trend_on(resid.history, data_date, p.inner.inner):
            return ()
        rows = resid.factor.rows_on(members, data_date, p.inner.inner)
        if not rows:
            return ()
        grid = resid.grid(p.inner.market)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, p.inner)
        by_symbol = {r.symbol: r for r in rows if r.symbol in scores and r.symbol not in EXCLUDED}
        ranked = one_per_company(sorted(by_symbol, key=lambda s: (-scores[s], s)), len(by_symbol))
        sizes: dict[str, float] = {}
        for s in ranked:
            mv = market.market_value(s, data_date)
            if mv is not None and mv > 0.0:
                sizes[s] = float(mv)
        if len(sizes) < NBANDS:
            return ()
        order = [s for s in ranked if s in sizes]
        chosen = choose(order, size_bands(sizes), p, data_date)
        w = equal_weight(p.inner.inner.top)
        out: list[Target] = []
        for s in chosen:
            t = target_from_close(s, by_symbol[s].close, w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no targets."""
        return self._run(self.prepare(history), members, data_date, held, _check(params))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SizePrepared):
            raise TypeError(f"prepared must be SizePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


SIZEBAND = SizeBandAllocator()


def _v(suffix: str, params: BandParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0223-{suffix}", family="M0223", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SIZEBAND, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0223",
    name="Momentum picked inside each size band: four names from each fifth of the index by company size",
    family="stock-size-banded-momentum",
    source_kind="variation",
    source_ref=(
        "variation of M0047's finding that size weighting starves the mid-size picks; "
        "point-in-time market value from 2026-10-17; Sera 20261018-2051; placebo frame of M0187"
    ),
    parent_id="M0047",
    hypothesis=(
        "M0047 found that sizing the residual-momentum picks by company size cost 2.5-3.3 points a "
        "year and turned the 2009-2015 lead negative, which suggests the ranking's edge lives in "
        "the smaller and mid-sized names. Each month, split the screened members whose "
        "point-in-time market value is known (one class per company) into five equal-count bands "
        "by size and hold the top four raw residual-momentum names in each band (B5X4), equal "
        "slots, SPY 200-day gate, fractional shares at Gotrade's real fees on the monthly top-up. "
        "Controls on the same sized universe: the plain top 20 (TOP20), the top 20 from the two "
        "smallest bands (SMALL2), the top 20 from the two biggest bands (BIG2), and a hash-order "
        "placebo with four names per band redrawn quarterly (PLC1-B5X4). Unknown sizes are "
        "dropped from every arm (assumption). Predictions, written now: SMALL2 earns the most and "
        "falls the deepest; BIG2 earns the least and lags SPY in 2009-2015; B5X4 sits between "
        "TOP20 and BIG2 on return with a shallower fall than TOP20; the momentum arms beat the "
        "placebo by 2+ points a year. If the small bands carry the whole edge, the honest "
        "construction is SPY as the core with a small-band momentum sleeve, not a size-bent book. "
        "Residual momentum was published in 2011 (Blitz, Huij and Martens) and the size effect in "
        "1981 (Banz); expect fade after 2015."
    ),
    expected_failure=(
        "The edge in this lab's dev store leans small partly because the store is missing about "
        "half the index members in the 1990s, mostly companies that later died, and those were "
        "mostly small: the small bands read the survivors, so SMALL2's lead may be a hole in the "
        "data (the survivorship-check store should shrink it most). Forcing four names from the "
        "biggest fifth means holding big companies with merely the best of a slow group's "
        "momentum, so B5X4 probably gives up a point or two a year against TOP20 without a much "
        "shallower fall, and in 2009-2015, when the giants led, BIG2 may track SPY but not beat "
        "it once fees are paid. The placebo will likely beat SPY on dev too, because the gate and "
        "the screen do most of the work (M0187). Every arm descends from the residual-momentum "
        "family, which has a test-failed method, so the hard gate is expected to refuse promotion "
        "whatever dev says; the value is the answer to where the edge lives."
    ),
    candidates=(
        _v("B5X4", BandParams(RANKING),
           "Top four residual-momentum names from each fifth of the sized index, equal slots"),
        _v("TOP20", BandParams(RANKING, per_band=0),
           "Plain top 20 residual momentum on the same sized universe: the control"),
        _v("SMALL2", BandParams(RANKING, bands=(0, 1), per_band=0),
           "Top 20 residual momentum from the two smallest fifths only"),
        _v("BIG2", BandParams(RANKING, bands=(3, 4), per_band=0),
           "Top 20 residual momentum from the two biggest fifths only"),
        _v("PLC1-B5X4", BandParams(RANKING, picks="placebo", seed=1),
           "Placebo: four hash-order names per size fifth, redrawn each quarter"),
    ),
    seen_keys=(
        "concept:size-banded-momentum-book",
        "concept:size-band-placebo-control",
    ),
)
