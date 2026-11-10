"""M0551 — Faster trend memory: the Hurst exponent on 126 sessions, alone and inside the momentum book.

Source: a variation of M0547 (Auer 2018, J Econ Finance 42:66-88; doi 10.1007/s10436-023-00428-z).
Published 2018 and 2023, so the dev window is before the crowd, and 2009-2015 is the first filter.

M0547 ranked index members by the rescaled-range Hurst exponent of their trailing 252 daily
returns. Its high-H book beat five blind draws and kept its edge after H was stripped of momentum
and volatility, but missed the luck bar and lost both post-2009 folds. Two questions follow, and
this method asks both on the same chassis (``MONTHLY_HOLD_FRAC_GOTRADE``: 20 equal slots,
fractional shares, Gotrade's real fees, SPY-200 switch):

1. **Does a faster memory keep the edge after 2009?** H on the trailing 126 returns, block sizes
   7 to 63 (all divide 126). A shorter window reacts sooner but is noisier.
2. **Does trend memory add anything on top of the momentum book?** (The coordinator's open
   question from batch 20261110-0808.) The momentum book is the roster's residual-momentum book,
   M0032-N20-RAW-FRAC-GT (M0007-N20-RAW's configuration at real fees). Here: take the 40 names
   with the highest residual momentum and keep the 20 of them with the highest H. If memory
   adds nothing, the H-picked 20 do no better than 20 drawn blind from the same 40, and no better
   than the plain top 20.

Arms:

    H126-HIGH      20 highest H(126) of the whole screen, gated
    H126-LOW       20 lowest H(126), gated (mirror)
    H126-OPEN      H126-HIGH with no switch, always invested: the gate's habit, priced
    MOM-CTRL       Control: the plain top 20 by residual momentum = M0032-N20-RAW-FRAC-GT's book
    MOM-H126-HIGH  top 40 by residual momentum, the 20 with the highest H(126)
    MOM-H126-LOW   top 40 by residual momentum, the 20 with the lowest H(126) (mirror)

Amendment 1: RAND-A..E (five blind draws of 20 from the whole screen, gated; new seeds, so new
books next to M0547's five) and MOM-RAND-A (20 drawn blind from the residual top 40). Amendment 2:
MOM-RAND-B..E (the rest of that pool's five-draw bar) and MOM-H252-HIGH / -LOW (the same test at
M0547's 252-session window, so the open question is answered for the memory M0547 measured too).

The no-opinion arms are the draws: the mirror pairs prove whether the sort is a signal; the draws
from the same pool, at the same gate and churn, price what acting on it costs. The gate's habit
is priced by H126-OPEN against M0547-RAND-OPEN (recorded; same screen, no switch, a blind draw).

Pure: reads bars dated at or before the data date only.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    ResidParams,
    ResidPrepared,
    ReturnGrid,
    build_grid,
    resid_lookback,
    residual_scores,
)
from seer_engine.lab.methods.m0547_hurst_persistence_ranked import pick
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import as_day
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    factor_weights,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 10)
SIGNALS = ("high", "low", "rand", "resid")
# Block sizes per window: every size divides its window, the largest leaves at least two blocks.
BLOCKS = {126: (7, 9, 14, 18, 21, 42, 63), 252: (9, 14, 18, 28, 36, 42, 63, 84)}
MIN_FRAC = 0.9  # share of the window's returns that must be present
# The momentum book's ranking key, verbatim from M0032-N20-RAW-FRAC-GT.
RESID = ResidParams(N20, scaled=False)


def hurst_rs(window: np.ndarray, blocks: Sequence[int]) -> np.ndarray:
    """Rescaled-range H per row of ``window`` (names x n); M0547's estimator with ``blocks``.

    NaN where the row is too gappy or degenerate. A missing return counts as zero once at least
    ``MIN_FRAC`` of the row is present.
    """
    n = window.shape[1]
    finite = np.isfinite(window)
    ok = finite.sum(axis=1) >= MIN_FRAC * n
    x = np.where(finite, window, 0.0)
    logs, logn = [], []
    for s in blocks:
        k = n // s
        b = x[:, n - k * s :].reshape(x.shape[0], k, s)
        dev = b - b.mean(axis=2, keepdims=True)
        cum = np.cumsum(dev, axis=2)
        rng = cum.max(axis=2) - cum.min(axis=2)
        sd = b.std(axis=2)
        with np.errstate(divide="ignore", invalid="ignore"):
            rs = np.where(sd > 0.0, rng / np.where(sd > 0.0, sd, 1.0), np.nan)
            logs.append(np.log(np.nanmean(np.where(rs > 0.0, rs, np.nan), axis=1)))
        logn.append(np.log(float(s)))
    y = np.stack(logs, axis=1)  # names x blocks
    xs = np.asarray(logn)
    good = np.isfinite(y).all(axis=1) & ok
    xm = xs.mean()
    sxx = float(((xs - xm) ** 2).sum())
    with np.errstate(invalid="ignore"):
        slope = ((y - np.nanmean(y, axis=1, keepdims=True)) * (xs - xm)).sum(axis=1) / sxx
    return np.where(good, slope, np.nan)


@dataclass(frozen=True, slots=True)
class Hurst126Params:
    """``inner`` is F4's screen, gate and book size.

    ``pool`` 0 sorts the whole screen; ``pool`` k first narrows it to the k highest residual
    momentum scores (``RESID``). ``signal`` is the sort inside the pool: highest or lowest H, a
    seeded hash draw, or ``resid`` (the pool's top ``inner.top`` by residual momentum itself).
    """

    inner: FactorParams
    signal: str = "high"
    pool: int = 0
    seed: int = 0
    window: int = 126
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.signal not in SIGNALS:
            raise ValueError(f"signal must be one of {SIGNALS}, got {self.signal!r}")
        for name in ("pool", "seed", "window"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.window not in BLOCKS:
            raise ValueError(f"window must be one of {tuple(BLOCKS)}, got {self.window}")
        if self.pool < 0 or (self.pool and self.pool < self.inner.top):
            raise ValueError(f"pool must be 0 or >= top ({self.inner.top}), got {self.pool}")
        if self.signal == "resid" and not self.pool:
            raise ValueError("signal 'resid' needs a residual pool")

    def as_dict(self) -> dict[str, str]:
        out = {"signal": self.signal, "pool": str(self.pool), "seed": str(self.seed),
               "window": str(self.window), "market": self.market}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> Hurst126Params:
    if not isinstance(params, Hurst126Params):
        raise TypeError(f"params must be Hurst126Params, got {type(params).__name__}")
    return params


def _draw(symbol: str, data_date: date, seed: int) -> str:
    return hashlib.sha256(f"M0551|{seed}|{data_date.isoformat()}|{symbol}".encode()).hexdigest()


def hurst_scores(grid: ReturnGrid, symbols: Sequence[str], data_date: date,
                 window: int) -> dict[str, float]:
    """H per symbol on ``data_date`` from its last ``window`` grid returns; absent if too gappy."""
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day or j - window + 1 < 0:
        return {}
    names = [s for s in symbols if s in grid.row]
    if not names:
        return {}
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)
    h = hurst_rs(grid.rets[idx, j - window + 1 : j + 1], BLOCKS[window])
    return {n: float(v) for n, v in zip(names, h, strict=True) if np.isfinite(v)}


def targets_from(rows: Sequence[FactorRow], grid: ReturnGrid | None, data_date: date,
                 p: Hurst126Params) -> tuple[Target, ...]:
    rows = [r for r in rows if r.symbol not in EXCLUDED]
    if not rows:
        return ()
    by_symbol = {r.symbol: r for r in rows}
    pool = sorted(by_symbol)
    if p.pool:
        if grid is None:
            return ()
        resid = residual_scores(grid, pool, data_date, RESID)
        pool = sorted(resid, key=lambda s: (-resid[s], s))[: p.pool]
        if p.signal == "resid":
            names = pool[: p.inner.top]
    if p.signal == "rand":
        names = sorted(pool, key=lambda s: _draw(s, data_date, p.seed))[: p.inner.top]
    elif p.signal in ("high", "low"):
        if grid is None:
            return ()
        h = hurst_scores(grid, pool, data_date, p.window)
        names = pick(h, p.signal == "high", p.inner.top)
    chosen = [by_symbol[s] for s in names]
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, p.inner), strict=True):
        if weight is None:
            continue
        t = target_from_close(row.symbol, row.close, weight)
        if t is not None:
            out.append(t)
    return tuple(out)


class Hurst126Allocator:
    """20 screened names by Hurst exponent or a seeded draw, optionally inside the momentum top 40."""

    id = "M0551"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        n = max(factor_lookback(p.inner), p.window + 2)
        return max(n, resid_lookback(RESID)) if p.pool else n

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, Any], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return targets_from(rows, build_grid(history, p.market), data_date, p)

    def prepare(self, history: Mapping[str, Any]) -> ResidPrepared:
        return ResidPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return targets_from(rows, prepared.grid(p.market), data_date, p)


HURST126_ALLOC = Hurst126Allocator()

GATED = FactorParams(rank="momentum", top=20, trend=("SPY", 200))
OPEN = FactorParams(rank="momentum", top=20, trend=None)
POOL = 40


def _v(suffix: str, params: Hurst126Params, rationale: str) -> Candidate:
    return Candidate(id=f"M0551-{suffix}", family="M0551", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=HURST126_ALLOC, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0551",
    name="Faster trend memory: Hurst exponent on 126 sessions, alone and inside the momentum book",
    family="stock-hurst-persistence",
    source_kind="variation",
    source_ref="M0547 (Auer 2018, J Econ Finance 42:66-88; doi 10.1007/s10436-023-00428-z)",
    parent_id="M0547",
    hypothesis=(
        "Published 2018 and 2023, so the dev window is before the crowd. M0547's 252-session "
        "trend-memory book beat five blind draws but missed the luck bar and lost the 2009-2011 "
        "and 2012-2014 folds. (1) A 126-session Hurst exponent reacts faster and keeps the edge "
        "after 2009: H126-HIGH beats total-return SPY on the deposits, beats all five gated draws "
        "(RAND-A..E, amendment 1) and H126-LOW, with a positive 2009-2015 edge. H126-OPEN is the "
        "same book with no switch, compared with the recorded M0547-RAND-OPEN to price the gate. "
        "(2) Trend memory adds something on top of the momentum book: among the 40 names with the "
        "highest residual momentum, the 20 with the highest H (MOM-H126-HIGH; MOM-H252-HIGH in "
        "amendment 2) beat the plain top 20 (MOM-CTRL, a control that repeats "
        "the roster's residual-momentum book, M0032-N20-RAW-FRAC-GT; never a new book), beat all five blind draws from the same 40 (MOM-RAND-A..E) and "
        "beat their mirror (MOM-H126-LOW). If MOM-H-HIGH beats the draws but not MOM-CTRL, H only "
        "recovers part of what momentum's own ranking already knew: that is a no. Same chassis "
        "for every arm: 20 equal slots, fractional shares, Gotrade's real fees, SPY-200 switch, "
        "monthly hold, the owner's monthly deposits."
    ),
    expected_failure=(
        "126 returns is half M0547's sample, and rescaled-range H has a large small-sample bias "
        "and standard error, so the cross-sectional order of H126 is mostly noise: H126-HIGH and "
        "H126-LOW sit inside the five draws, and the 2009-2015 era stays negative. Inside the "
        "momentum top 40, the highest-H names are the smoothest risers, which are largely the "
        "same names residual momentum already ranks first; MOM-H-HIGH then tracks MOM-CTRL "
        "within the draw noise and adds nothing (M0432's trend-autocorrelation filter on momentum "
        "and M0480's staying-power filter both did worse than plain momentum). Picking 20 of 40 "
        "also trades rank for H, which costs momentum strength and adds turnover at real fees on "
        "$28 slots."
    ),
    candidates=(
        _v("H126-HIGH", Hurst126Params(GATED, "high"),
           "20 highest 126-session Hurst exponents of the screen, gated (trend persists)"),
        _v("H126-LOW", Hurst126Params(GATED, "low"),
           "20 lowest 126-session Hurst exponents, gated (mirror: reversion)"),
        _v("H126-OPEN", Hurst126Params(OPEN, "high"),
           "H126-HIGH with no switch, always invested: prices the gate"),
        _v("MOM-CTRL", Hurst126Params(GATED, "resid", pool=POOL),
           "Control: M0032-N20-RAW-FRAC-GT's book, the plain top 20 by residual momentum, gated"),
        _v("MOM-H126-HIGH", Hurst126Params(GATED, "high", pool=POOL),
           "Top 40 by residual momentum, the 20 with the highest 126-session Hurst exponent"),
        _v("MOM-H126-LOW", Hurst126Params(GATED, "low", pool=POOL),
           "Top 40 by residual momentum, the 20 with the lowest 126-session Hurst (mirror)"),
    ),
    seen_keys=("concept:hurst-exponent-persistence", "concept:hurst-on-momentum-pool",
               "concept:random-draw-error-bar"),
    amendments=(
        Amendment(
            added=ADDED,
            why="The noise band for both pools: five blind draws of the screen and the first of the momentum top 40",
            hypothesis=(
                "RAND-A..E are seeds 1-5 of a gated hash draw of 20 from the whole screen (new "
                "seeds: new books beside M0547's five). MOM-RAND-A is seed 1 of a draw of 20 from "
                "the residual-momentum top 40. H126-HIGH counts only if it beats all five screen "
                "draws (p = 1/6 by chance); MOM-H126-HIGH only if it beats every draw from its "
                "pool and MOM-CTRL."
            ),
            expected_failure=(
                "The draws span several points a year and H126-HIGH sits inside them; the momentum "
                "draws sit a little under MOM-CTRL and MOM-H126-HIGH sits among them."
            ),
            candidates=(
                *(_v(f"RAND-{c}", Hurst126Params(GATED, "rand", seed=s),
                     f"No opinion: hash draw seed {s} of the screen, same gate and monthly churn")
                  for s, c in enumerate("ABCDE", start=1)),
                _v("MOM-RAND-A", Hurst126Params(GATED, "rand", pool=POOL, seed=1),
                   "No opinion inside the momentum top 40: hash draw seed 1, same gate and churn"),
            ),
        ),
        Amendment(
            added=ADDED,
            why="The rest of the momentum pool's draw bar, and the same on-top-of-momentum test at M0547's 252-session memory",
            hypothesis=(
                "MOM-RAND-B..E are seeds 2-5 of the draw from the residual-momentum top 40, so "
                "that pool has five draws. MOM-H252-HIGH and MOM-H252-LOW repeat MOM-H126-HIGH and "
                "-LOW with M0547's 252-session window and block sizes, so the question 'does trend "
                "memory add anything on top of the momentum book' is answered for the memory M0547 "
                "measured as well as the faster one. Same success test as MOM-H126-HIGH."
            ),
            expected_failure=(
                "MOM-H252-HIGH and MOM-H252-LOW both sit inside the five momentum-pool draws and "
                "neither beats MOM-CTRL: trend memory is already priced by momentum's ranking."
            ),
            candidates=(
                *(_v(f"MOM-RAND-{c}", Hurst126Params(GATED, "rand", pool=POOL, seed=s),
                     f"No opinion inside the momentum top 40: hash draw seed {s}, same gate and churn")
                  for s, c in enumerate("BCDE", start=2)),
                _v("MOM-H252-HIGH", Hurst126Params(GATED, "high", pool=POOL, window=252),
                   "Top 40 by residual momentum, the 20 with the highest 252-session Hurst exponent"),
                _v("MOM-H252-LOW", Hurst126Params(GATED, "low", pool=POOL, window=252),
                   "Top 40 by residual momentum, the 20 with the lowest 252-session Hurst (mirror)"),
            ),
        ),
    ),
)
