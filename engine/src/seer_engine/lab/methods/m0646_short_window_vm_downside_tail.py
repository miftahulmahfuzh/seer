"""M0646 — Shorter-window, volatility-matched crash-avoidance: is M0512's downside-tail edge an
event or just calm?

Source: variation on M0512. M0512-LOW-DOWN (avoid the 20 names with the fattest downside tail over
126 sessions) cleared the lab's luck bar (DSR 0.923) and its random-twin check (beat 200/200
twins), but a forward-looking walk-forward pick never chose it over a random draw -- the arm that
would have been picked ahead of time (R2) won only 2 of 4 out-of-sample folds -- and its 2009-2015
edge flipped from +1.0%/yr to -1.5%/yr on the survivorship-check store. Two open questions, both
answered in the same N20 frame as the parent (F4-screened, point-in-time index members, 20 equal
fractional monthly slots at Gotrade real fees, behind SPY's 200-day switch):

(1) Does shortening the downside-tail lookback from 126 sessions to 21 or 42 sharpen the score
into "had one specific bad event recently" rather than "has been generally choppy for six
months"? A shorter window is dominated even more by one or two days, so if LOW-DOWN's edge really
is event-avoidance, a shorter window should show the same or a cleaner version of it; if the edge
instead depends on averaging a half-year of behaviour, a short window should land within the
draws' noise.

(2) Is LOW-DOWN itself M0510's calm-stocks-in-disguise trap (M0505's lesson: a "steady risk"
filter is just calm stocks renamed, and random picks beat it)? A volatility-matched arm --
five lowest downside-tail-fatness names from each of four volatility bands, at the parent's own
126-session window, the exact construction M0510's LOWK-VM used -- forces the book to carry the
pool's own risk mix instead of quietly favouring the calmest names, and isolates whatever is left
of the ranking once volatility is held constant.

Same N20 host as the parent: 20-name, F4-screened, point-in-time index members, monthly, equal
fractional slots at Gotrade real fees, behind SPY's 200-day switch. A name needs a minimum of
observations on the downside of its own mean return to be scored -- scaled down from the parent's
20-of-126 (~16%) because a 3-return minimum on a 21-session window would make the score almost
entirely about one or two extreme days: SHORT21 requires at least 5 of 21 returns below the mean
(~24%), SHORT42 at least 10 of 42 (~24%); DOWN-VM reuses the parent's own 20-of-126 threshold
since it runs at the same 126-session window.

Arms (six): SHORT21 and SHORT42 (lowest downside-tail fatness over 21 and 42 sessions -- the
single-event test), DOWN-VM (volatility matched at the parent's 126-session window -- the
calm-stocks test), R1 and R2 (blind draws, seeds 646/647, behind the switch -- different seeds
from every prior method in this family so the drawn books are not duplicates), and R1-NOSW
(always invested, no opinion, seed 646: prices the switch and acting, same convention as the
parent and M0510).
SUCCESS: at least one of SHORT21/SHORT42 beats the better of R1/R2 by more than 2 points a year
funded and keeps a positive edge in 2009-2015 (evidence the "one event" framing resolves
differently from the 126-session version, or that a short-horizon distress signal is itself
durable); DOWN-VM clearing the luck bar the way LOW-DOWN did would rule out the calm-stocks
explanation, while DOWN-VM landing within the draws' spread would mean LOW-DOWN's edge was
substantially calm-name selection.
"""
from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
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
MODES = ("short_down", "down_vm", "blind")
BANDS = 4
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class TimeParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking.

    ``need`` is closes needed (one more than the return window); ``min_side`` is the minimum
    count of below-mean returns required to score a name at all."""

    inner: FactorParams
    mode: str = "short_down"
    need: int = 127
    min_side: int = 20
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.need, bool) or not isinstance(self.need, int) or self.need < 3:
            raise TypeError(f"need must be an int >= 3, got {self.need!r}")
        if isinstance(self.min_side, bool) or not isinstance(self.min_side, int) or self.min_side < 1:
            raise TypeError(f"min_side must be a positive int, got {self.min_side!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "need": str(self.need), "min_side": str(self.min_side),
               "seed": str(self.seed)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> TimeParams:
    if not isinstance(params, TimeParams):
        raise TypeError(f"params must be TimeParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date,
                  need: int, min_side: int) -> dict[str, tuple[float, float]]:
    """(downside-tail fatness, daily volatility) of the last ``need - 1`` returns.

    Downside-tail fatness is the mean fourth power of the standardised returns that land below
    their own mean. Unscored on a gap, a non-positive price, zero volatility, or fewer than
    ``min_side`` below-mean returns."""
    out: dict[str, tuple[float, float]] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < need - 1:
            continue
        c = h.close[i - need + 1 : i + 1]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0)):
            continue
        r = c[1:] / c[:-1] - 1.0
        sd = float(np.std(r))
        if sd <= 0.0:
            continue
        z = (r - float(np.mean(r))) / sd
        down = z[z < 0.0]
        if len(down) < min_side:
            continue
        out[s] = (float(np.mean(down**4)), float(np.std(r, ddof=1)))
    return out


def choose(rows: list[FactorRow], score: dict[str, tuple[float, float]], params: TimeParams
           ) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in score]
    n = params.inner.top
    if params.mode == "down_vm":
        # four equal-sized volatility bands, the lowest downside-tail-fatness names from each:
        # the book keeps the pool's own risk mix, so the ranking cannot be calm names again.
        by_vol = sorted(pool, key=lambda r: (score[r.symbol][1], r.symbol))
        size = len(by_vol) / BANDS
        take = n // BANDS
        out: list[FactorRow] = []
        for b in range(BANDS):
            band = by_vol[round(b * size) : round((b + 1) * size)]
            band.sort(key=lambda r: (score[r.symbol][0], r.symbol))
            out.extend(band[:take])
        return out
    if params.mode == "short_down":
        key = {r.symbol: (score[r.symbol][0], 0.0) for r in pool}
    else:
        key = {r.symbol: (float(draw(params.seed, r.symbol)), 0.0) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[:n]


@dataclass
class TimePrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, tuple[float, float]]] = field(default_factory=dict, repr=False)


class ShortWindowVMAllocator:
    """The lab's index-member book ranked on downside-tail fatness, window and banding varied."""

    id = "M0646"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(factor_lookback(p.inner), p.need)

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

    def _run(self, prepared: TimePrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: TimeParams) -> tuple[Target, ...]:
        if not trend_on(history, data_date, p.inner):
            return ()
        if prepared is None:
            rows = factor_rows(history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        syms = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED)
        if prepared is None:
            scores = scored_names(history, syms, data_date, p.need, p.min_side)
        else:
            cache_key = (data_date, p.need, p.min_side)
            scores = prepared.cache.get(cache_key)  # type: ignore[call-overload]
            if scores is None:
                scores = scored_names(history, syms, data_date, p.need, p.min_side)
                prepared.cache[cache_key] = scores  # type: ignore[index]
        return targets_from_rows(choose(rows, scores, p), p)  # type: ignore[arg-type]

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> TimePrepared:
        return TimePrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, TimePrepared):
            raise TypeError(f"prepared must be TimePrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


SHORTVM = ShortWindowVMAllocator()


def _v(suffix: str, params: TimeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0646-{suffix}", family="M0646",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=SHORTVM, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0646",
    name="Shorter-window, volatility-matched crash-avoidance: is M0512's downside-tail edge an event or just calm?",
    family="stock-realized-kurtosis",
    source_kind="variation",
    source_ref="M0512",
    parent_id="M0512",
    hypothesis=(
        "M0512-LOW-DOWN (avoid the 20 names with the fattest downside tail over 126 sessions) "
        "cleared the lab's luck bar (DSR 0.923) and its random-twin check (beat 200/200 twins), "
        "but a forward-looking walk-forward pick never chose it over a random draw -- the arm "
        "that would have been picked ahead of time (R2) won only 2 of 4 out-of-sample folds -- "
        "and its 2009-2015 edge flipped from +1.0%/yr to -1.5%/yr on the survivorship-check "
        "store. Two open questions, both answered in the same N20 frame as the parent "
        "(F4-screened, point-in-time index members, 20 equal fractional monthly slots at Gotrade "
        "real fees, behind SPY's 200-day switch): (1) does shortening the downside-tail lookback "
        "from 126 to 21 or 42 sessions sharpen the score into 'had one specific bad event "
        "recently' rather than 'has been generally choppy for six months'; (2) is LOW-DOWN itself "
        "M0510's calm-stocks-in-disguise trap (M0505's lesson) -- a volatility-matched arm (five "
        "lowest downside-tail-fatness names from each of four volatility bands, at the parent's "
        "own 126-session window, the same construction as M0510's LOWK-VM) forces the book to "
        "carry the pool's own risk mix instead of quietly favouring the calmest names. SUCCESS: "
        "at least one of SHORT21/SHORT42 beats the better of R1/R2 by more than 2 points a year "
        "funded and keeps a positive edge in 2009-2015; DOWN-VM clearing the luck bar the way "
        "LOW-DOWN did would rule out the calm-stocks explanation, while DOWN-VM landing within "
        "the draws' spread would mean LOW-DOWN's edge was substantially calm-name selection. "
        "Prediction, written now: downside-tail fatness is dominated by one or two crash days "
        "regardless of window length, so SHORT21 and SHORT42 are expected to be noisier versions "
        "of the same 'had a recent event' signal rather than a cleaner one, and to land within "
        "the draws' spread in 2009-2015 the same way the 126-session version's own survivorship "
        "check already did; DOWN-VM is expected to lose most of LOW-DOWN's apparent edge once "
        "volatility is held constant across bands, confirming LOW-DOWN was substantially "
        "M0510's calm-stocks trap rather than a genuine crash-avoidance effect."
    ),
    expected_failure=(
        "Both short-window arms reduce to noisier versions of LOW-DOWN: still dominated by a "
        "single recent event, landing within the draws' spread in 2009-2015 (as the 126-session "
        "version's own survivorship check already showed) rather than resolving into either a "
        "cleaner or a visibly decayed signal. DOWN-VM loses most of LOW-DOWN's apparent edge once "
        "volatility is held constant across bands, confirming the calm-stocks explanation."
    ),
    candidates=(
        _v("SHORT21", TimeParams(N20, "short_down", need=22, min_side=5),
           "Lowest 21-session downside-tail fatness: tests whether a short window sharpens "
           "LOW-DOWN into a single-event detector"),
        _v("SHORT42", TimeParams(N20, "short_down", need=43, min_side=10),
           "Lowest 42-session downside-tail fatness: a slower single-event window between "
           "LOW-DOWN's 126 sessions and SHORT21's 21"),
        _v("DOWN-VM", TimeParams(N20, "down_vm", need=127, min_side=20),
           "Volatility matched at LOW-DOWN's own 126-session window: five lowest "
           "downside-tail-fatness names from each of four volatility bands, M0510's LOWK-VM "
           "construction, to rule out the calm-stocks trap"),
        _v("R1", TimeParams(N20, "blind", need=127, min_side=20, seed=646),
           "Control: hash draw of 20, seed 646, behind the switch"),
        _v("R2", TimeParams(N20, "blind", need=127, min_side=20, seed=647),
           "Control: hash draw of 20, seed 647, measures draw noise"),
        _v("R1-NOSW", TimeParams(NOSW, "blind", need=127, min_side=20, seed=646),
           "Always invested, no opinion: prices the switch and acting on either split"),
    ),
    seen_keys=(
        "concept:realized-kurtosis",
        "concept:tail-split-kurtosis",
        "concept:short-window-downside-tail",
        "concept:volatility-matched-downside-tail",
    ),
)
