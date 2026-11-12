"""M0467 — Price-volume correlation on a 120-session window, against four blind draws.

M0461 ranked the F4-screened index members on the 20-day correlation of log volume change with
daily return and found the rank statistically indistinguishable from a coin flip: its own two
blind draws (seeds 461, 462) differed by 2.1 points a year, almost as much as NEG beat POS by
(2.8). A 20-session Pearson correlation of two noisy daily series has a standard error near 0.22;
this variation keeps the idea (Alpha191-style price-volume disagreement) but computes it over the
last 120 sessions instead, where the same formula's standard error falls to roughly 0.09, and
measures the draw spread with four blind draws instead of two so the spread is read, not guessed.
The six-variant cap rules out also re-measuring the switch's cost here: M0461 already measured it
(R1-NOSW vs R1: about 1 point a year, worst fall 64% vs 24%), so every arm here keeps the switch.

Frame is otherwise M0461's: point-in-time members, the F4 screen, 20 equal slots, monthly,
fractional shares at Gotrade's real fees. Names with a missing bar, a non-positive price or
volume, or a flat series over the window are not scored, in every arm alike.

Arms (six): NEG120 holds the 20 most negative 120-day correlations, POS120 the 20 most positive
(the mirror), R1-R4 draw 20 of the same pool by hash (seeds distinct from M0461's 461/462, so
these are new books, not a repeat of M0461's blind arms).
"""
from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import draw
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
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

ADDED = date(2026, 11, 12)
MODES = ("neg", "pos", "blind")
WIN = 120  # sessions in the correlation window
MARKET = "SPY"


@dataclass(frozen=True, slots=True)
class PV120Params:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "neg"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "win": str(WIN)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> PV120Params:
    if not isinstance(params, PV120Params):
        raise TypeError(f"params must be PV120Params, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> dict[str, float]:
    """Correlation of daily log volume change with daily return over the last WIN returns.

    Needs WIN + 1 bars ending on data_date. Names with a missing bar, non-positive price or
    volume, or zero variance in either series are not scored."""
    out: dict[str, float] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < WIN:
            continue
        c = h.close[i - WIN : i + 1]
        v = h.volume[i - WIN : i + 1]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0)
                and np.all(np.isfinite(v)) and np.all(v > 0.0)):
            continue
        r = c[1:] / c[:-1] - 1.0
        dv = np.diff(np.log(v))
        if float(np.std(r)) <= 0.0 or float(np.std(dv)) <= 0.0:
            continue
        out[s] = float(np.corrcoef(dv, r)[0, 1])
    return out


def choose(rows: list[FactorRow], score: dict[str, float], params: PV120Params) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in score]
    if params.mode == "neg":
        key = {r.symbol: score[r.symbol] for r in pool}
    elif params.mode == "pos":
        key = {r.symbol: -score[r.symbol] for r in pool}
    else:
        key = {r.symbol: float(draw(params.seed, r.symbol)) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: params.inner.top]


@dataclass
class PV120Prepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, float]] = field(default_factory=dict, repr=False)


class PV120Allocator:
    """The lab's index-member book ranked on its 120-day price-volume correlation."""

    id = "M0467"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), WIN + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {MARKET}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: PV120Prepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: PV120Params) -> tuple[Target, ...]:
        if not trend_on(history, data_date, p.inner):
            return ()
        if prepared is None:
            rows = factor_rows(history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        syms = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED)
        if prepared is None:
            scores = scored_names(history, syms, data_date)
        else:
            scores = prepared.cache.get(data_date) or scored_names(history, syms, data_date)
            prepared.cache[data_date] = scores
        return targets_from_rows(choose(rows, scores, p), p)  # type: ignore[arg-type]

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> PV120Prepared:
        return PV120Prepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, PV120Prepared):
            raise TypeError(f"prepared must be PV120Prepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


PV120 = PV120Allocator()


def _v(suffix: str, params: PV120Params, rationale: str) -> Candidate:
    return Candidate(id=f"M0467-{suffix}", family="M0467",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=PV120, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0467",
    name="Price-volume correlation on a 120-day window against four blind draws",
    family="stock-price-volume-correlation",
    source_kind="variation",
    source_ref="variation of M0461 (arXiv 2601.06499, Alpha191 price-volume signals)",
    parent_id="M0461",
    hypothesis=(
        "M0461's 20-day correlation of log volume change with return was too noisy to rank on: "
        "its own two blind draws differed by 2.1 points a year, almost as much as NEG beat POS "
        "by (2.8). Lengthen the window to 120 sessions, where the same correlation's standard "
        "error falls from about 0.22 to about 0.09, and read the draw spread off four blind "
        "draws instead of two. Arms: NEG120 (most negative 120-day correlation, the long leg), "
        "POS120 (most positive, the mirror), R1-R4 (four hash draws of 20 from the same pool, "
        "new seeds so these are not a repeat of M0461's R1/R2). All four behind SPY's 200-day "
        "switch, whose cost was already measured in M0461 (about 1 point a year, worst fall cut "
        "from 64% to 24%) and is not re-measured here. SUCCESS: NEG120 beats the best of R1-R4 by "
        "more than the full R1-R4 spread, POS120 loses to the blind draws, with a positive "
        "2009-2015 edge vs SPY. Predictions, written now: the longer window narrows the R1-R4 "
        "spread versus M0461's 2.1-point pair, but NEG120 still does not clear it, because the "
        "underlying anomaly (if real) is already traded away by the dev window's end."
    ),
    expected_failure=(
        "A 120-day correlation is less noisy than a 20-day one but still a single linear-"
        "correlation statistic on daily data; four draws from the same ~500-name pool can still "
        "span several points a year by chance, and NEG120 is likely to fall inside that spread "
        "rather than clear it, repeating M0461's result with a tighter confidence interval "
        "instead of a different answer. Published price-volume anomalies fade (M0050's overnight "
        "momentum is the lab's clearest case), so any 2009-2015 edge is likely to be small or "
        "negative."
    ),
    candidates=(
        _v("NEG120", PV120Params(N20, "neg"),
           "Most negative 120-day price-volume correlation among screened members, behind the switch"),
        _v("POS120", PV120Params(N20, "pos"),
           "Most positive 120-day correlation: the reversed arm"),
        _v("R1", PV120Params(N20, "blind", 467001),
           "Control: hash draw of 20 from the same pool, seed 467001, behind the switch"),
        _v("R2", PV120Params(N20, "blind", 467002),
           "Control: hash draw of 20 from the same pool, seed 467002, behind the switch"),
        _v("R3", PV120Params(N20, "blind", 467003),
           "Control: hash draw of 20 from the same pool, seed 467003, behind the switch"),
        _v("R4", PV120Params(N20, "blind", 467004),
           "Control: hash draw of 20 from the same pool, seed 467004, behind the switch"),
    ),
    seen_keys=(
        "concept:price-volume-correlation-120d",
    ),
)
