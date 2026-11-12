"""M0601 -- Volume shocks and the overnight leg: rank on the volume spike, hold the book a month.

Source: Cartea, Cucuringu, Jin & Wilson (2025), volume shocks and overnight returns (summarised at
cxoadvisory.com/equity-premium/exploit-stock-volume-spikes-overnight). The claim: a stock whose
daytime volume spikes against its own trailing 20-day median earns more over the NEXT overnight
(close to open) session. Published 2025, so the dev window (ends 2015) can only show an edge from
before the crowd knew it, and the paper's own sample is mostly 2000s-2020s.

What this method can and cannot test, written before any result. Gotrade is long only and trades
the regular session; a position held only overnight needs a close-in, open-out round trip every
day, and the lab's simulator has no such trade (its daily cadence enters at the open). Nothing
here is held overnight only. The ranking key is the paper's -- today's volume against the median
of the 20 sessions before it, in logs -- and the book is the lab's executable one: monthly, 20
equal slots, fractional shares at Gotrade's real fees (``monthly-hold-frac-gotrade``), behind the
SPY 200-day switch whose cost M0461 already priced on this chassis (about 1 point a year). If the
signal is a one-day overnight effect it will mostly be gone by the time a monthly book has held it
for 20 sessions; the test is whether any of it survives that dilution, which is the only form the
owner could trade.

New against M0591 (volume surprise scaled by move size, mean not median, sign-agnostic) and
M0461 / M0467 (volume-return correlation): the key here is volume alone, against the median, and
it is read over one day and over five. Against the overnight family (M0050-M0059): those ranked on
overnight RETURNS, this ranks on volume.

Arms (six): SHOCK1 holds the 20 largest one-day shocks on the decision date, SHOCK5 the 20 largest
five-day mean shocks, QUIET5 the 20 smallest five-day mean shocks (the mirror), R1-R3 draw 20 of
the same pool by hash (seeds 601001-601003). The blind draws are the no-opinion arms: the same
book, switch and fees, with no volume opinion in them. Names missing a bar, with non-positive
price or volume in the window, or too little history are not scored, in every arm alike.
"""
from __future__ import annotations

import math
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

ADDED = date(2026, 11, 13)
MODES = ("shock1", "shock5", "quiet5", "blind")
WIN = 20  # trailing sessions the volume median is measured over
SPAN = 5  # sessions averaged by the five-day arms
MARKET = "SPY"


@dataclass(frozen=True, slots=True)
class VSMParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "shock1"
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


def _check(params: object) -> VSMParams:
    if not isinstance(params, VSMParams):
        raise TypeError(f"params must be VSMParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> dict[str, tuple[float, float]]:
    """(one-day shock, five-day mean shock) per name, both in logs.

    A day's shock is log(volume / median of the WIN sessions before it). Needs WIN + SPAN bars
    ending on data_date. Names with a missing bar, non-positive price or non-positive volume
    anywhere in that stretch are not scored."""
    out: dict[str, tuple[float, float]] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < WIN + SPAN - 1:
            continue
        v = h.volume[i - WIN - SPAN + 1 : i + 1]
        c = h.close[i - WIN - SPAN + 1 : i + 1]
        if not (np.all(np.isfinite(v)) and np.all(v > 0.0)
                and np.all(np.isfinite(c)) and np.all(c > 0.0)):
            continue
        shocks = []
        for j in range(WIN, WIN + SPAN):
            med = float(np.median(v[j - WIN : j]))
            shocks.append(math.log(float(v[j]) / med))
        out[s] = (shocks[-1], float(np.mean(shocks)))
    return out


def choose(rows: list[FactorRow], score: dict[str, tuple[float, float]], params: VSMParams
           ) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in score]
    if params.mode == "shock1":
        key = {r.symbol: -score[r.symbol][0] for r in pool}
    elif params.mode == "shock5":
        key = {r.symbol: -score[r.symbol][1] for r in pool}
    elif params.mode == "quiet5":
        key = {r.symbol: score[r.symbol][1] for r in pool}
    else:
        key = {r.symbol: float(draw(params.seed, r.symbol)) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: params.inner.top]


@dataclass
class VSMPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, tuple[float, float]]] = field(default_factory=dict, repr=False)


class VSMAllocator:
    """The lab's index-member book ranked on the volume shock against the 20-day median."""

    id = "M0601"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), WIN + SPAN)

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

    def _run(self, prepared: VSMPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: VSMParams) -> tuple[Target, ...]:
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

    def prepare(self, history: Mapping[str, History]) -> VSMPrepared:
        return VSMPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, VSMPrepared):
            raise TypeError(f"prepared must be VSMPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


VSM = VSMAllocator()


def _v(suffix: str, params: VSMParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0601-{suffix}", family="M0601",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=VSM, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0601",
    name="Yesterday's volume shock and tonight's gap: buy the names whose daytime volume spiked, "
         "to hold only the overnight session",
    family="stock-volume-shock-overnight",
    source_kind="paper",
    source_ref="Cartea, Cucuringu, Jin, Wilson 2025 (volume shocks and overnight returns); "
               "cxoadvisory.com/equity-premium/exploit-stock-volume-spikes-overnight",
    parent_id=None,
    hypothesis=(
        "Daytime volume shocks (volume against the stock's own trailing 20-day median) are "
        "claimed to predict the next overnight (close to open) return; published 2025, so the "
        "dev window can only show a pre-crowd edge. Gotrade is long only, regular session, and "
        "the lab's simulator has no close-in open-out daily trade, so nothing here is held "
        "overnight only: the key is the paper's, the book is the executable one (20 equal "
        "slots, monthly, fractional shares at Gotrade's real fees, behind SPY's 200-day switch "
        "that M0461 priced at about 1 point a year). The test is whether any of a one-day "
        "overnight effect survives a 20-session hold. Closest recorded: M0591 (volume surprise "
        "scaled by move size, against the mean) and the overnight family M0050-M0059 (ranked on "
        "overnight returns); new here is volume alone, against the median, read over one day "
        "and over five. Arms: SHOCK1 (largest one-day shock), SHOCK5 (largest five-day mean), "
        "QUIET5 (smallest five-day mean, the mirror), R1-R3 blind draws of 20 from the same "
        "pool (seeds 601001-601003) as the no-opinion arms. SUCCESS: SHOCK1 or SHOCK5 beats the "
        "best blind draw by more than the draws' own spread, QUIET5 does not, and the 2009-2015 "
        "edge against SPY is positive."
    ),
    expected_failure=(
        "A one-day volume spike is a one-night effect; a monthly book holds it for about twenty "
        "sessions, so the premium is diluted to nothing and the shock arms land inside the blind "
        "draws' spread, as M0461, M0467 and M0591 did. Volume spikes also cluster in news, "
        "earnings and index-event names, which a monthly equal-weight book will carry as noise. "
        "A 2025-published anomaly has also had little time to be arbitraged in the dev window, "
        "so a null here says the monthly form is untradeable, not that the paper is wrong."
    ),
    candidates=(
        _v("SHOCK1", VSMParams(N20, "shock1"),
           "Largest one-day volume shock against the 20-day median, behind the switch"),
        _v("SHOCK5", VSMParams(N20, "shock5"),
           "Largest five-day mean volume shock, behind the switch"),
        _v("QUIET5", VSMParams(N20, "quiet5"),
           "Smallest five-day mean volume shock, the mirror arm, behind the switch"),
        _v("R1", VSMParams(N20, "blind", 601001),
           "Control: hash draw of 20 from the same pool, seed 601001, behind the switch"),
        _v("R2", VSMParams(N20, "blind", 601002),
           "Control: hash draw of 20 from the same pool, seed 601002, behind the switch"),
        _v("R3", VSMParams(N20, "blind", 601003),
           "Control: hash draw of 20 from the same pool, seed 601003, behind the switch"),
    ),
    seen_keys=(
        "concept:volume-shock-overnight-return-monthly-rank",
    ),
)
