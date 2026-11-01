"""M0425 — Up-volume accumulation: buy index members whose trading volume piles up on up days.

Source: knowledge. On-balance volume (Granville, 1963) and the accumulation/distribution family
that grew out of it; the academic cousin is Lee & Swaminathan (2000, "Price Momentum and Trading
Volume") and Gervais, Kaniel & Mingelgrin (2001). Reserved by Sera batch 20261101-0859 as an
``idea`` row; this file refines it and keeps its id. Technical volume indicators have been public
for sixty years, so the dev window can only show an edge the crowd has long since traded; expect it
to be small, and say so in ``expected_failure``.

THE SIGNAL. For each pool member, over the last ``n`` sessions (60 or 120), the share of dollar
volume (close x volume) traded on days that closed above the previous close:
``sum(dv on up days) / sum(dv)``. Above one half means buyers did the heavy trading; below it means
sellers did. Read only from bars dated on or before ``data_date``.

THE DANGER, NAMED BEFORE THE RUN. A stock that has been rising has more up days, and heavy volume on
them is partly just that. The lab has spent test looks on momentum books that failed, and the hard
gate's behaviour test calls a method kin of them when its monthly returns move with theirs. So the
method carries a matched control: each month, for every name the up-volume book would pick, the
not-picked pool member whose 12-1 month return is closest (greedy, one-to-one, no volume read).
That book holds price strength alone. If UP60-SW does not beat it, volume added nothing.

ARMS, equal 1/20 slots, fractional shares, Gotrade's real fees, monthly (``MONTHLY_HOLD_FRAC_GOTRADE``).
Held names stay while they rank inside the top 40 (the signal arms only):

    UP60-SW     top 20 by 60-day up-volume share, behind the SPY 200-day switch
    UP120-SW    the same on a 120-day window
    DN60-SW     reversed: the 20 lowest up-volume share (heaviest distribution)
    MATCH-SW    return-matched control for UP60-SW, no volume read, same switch
    PLC-SW      blind draw of UP60-SW's size and entry count (``control_draw`` shadow, depth 6):
                the no-opinion arm that prices the switch plus the monthly habit
    UP60        UP60-SW with no switch, so the switch's cost is priced and not assumed (the 2x2)

ASSUMPTIONS made without asking. (1) The idea row also listed volume-weighted slots; dropped to keep
one allocation dial (equal) so every arm differs in the signal only. (2) The pool is index members
with 253 bars; no company-size filter (market_fields empty), and the pre-2014 double listing of
Google's one class is not deduplicated (it can only hold one extra slot of one company). (3) The
matched control is unbanded (it re-matches each month), so it trades somewhat more than the banded
signal arms; its fees are slightly higher. (4) Fewer than 50 scored names holds SPY.

Pure: no clock, randomness, files or network; reads only bars dated on or before ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0130_tree_ranker import _bench
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED

ADDED = date(2026, 11, 1)
MOM_N, MOM_SKIP = 252, 21  # 12-1 momentum, used only by the matched control
BARS = MOM_N + 1  # bars every pool member needs through data_date
MIN_NAMES = 50
TREND = ("SPY", 200)
DEPTH = 6
SIGNALS = ("up", "down", "match", "control")


@dataclass(frozen=True, slots=True)
class UpVolParams:
    top: int = 20
    keep: int = 40
    window: int = 60
    signal: str = "up"
    switch: bool = True
    seed: int = 0

    def __post_init__(self) -> None:
        for name in ("top", "keep", "window", "seed"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise ValueError(f"{name} must be a non-negative int, got {v!r}")
        if not 1 <= self.top <= 200 or self.keep < self.top:
            raise ValueError(f"need 1 <= top <= 200 and keep >= top, got {self.top}, {self.keep}")
        if not 5 <= self.window < BARS:
            raise ValueError(f"window must be in [5, {BARS}), got {self.window}")
        if self.signal not in SIGNALS:
            raise ValueError(f"signal must be one of {SIGNALS}, got {self.signal!r}")
        if not isinstance(self.switch, bool):
            raise TypeError(f"switch must be a bool, got {type(self.switch).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"top": str(self.top), "keep": str(self.keep), "window": str(self.window),
               "signal": self.signal,
               "switch": f"{TREND[0]}:{TREND[1]}" if self.switch else "none",
               "seed": str(self.seed), "bars": str(BARS), "min_names": str(MIN_NAMES),
               "measure": "up-close-dollar-volume-share", "pool": "index-members",
               "mom": f"{MOM_N}-{MOM_SKIP}", "fallback": "SPY"}
        if self.signal == "control":
            out["control_rule"] = control_draw.SHADOW_RULE_ID
            out["control_of"] = "up"
            out["depth"] = str(DEPTH)
        return out


def _check(params: object) -> UpVolParams:
    if not isinstance(params, UpVolParams):
        raise TypeError(f"params must be UpVolParams, got {type(params).__name__}")
    return params


def up_share(h: History, data_date: date, window: int) -> float | None:
    """Share of the last ``window`` sessions' dollar volume that traded on up-close days."""
    i = h.index_of(data_date)
    if i is None or i + 1 < BARS:
        return None
    c = h.close[i - window : i + 1]
    v = h.volume[i + 1 - window : i + 1]
    dv = c[1:] * v
    total = float(np.sum(dv))
    if not (total > 0.0 and np.isfinite(total)):
        return None
    return float(np.sum(dv[c[1:] > c[:-1]])) / total


def momentum(h: History, data_date: date) -> float | None:
    i = h.index_of(data_date)
    if i is None or i + 1 < BARS:
        return None
    c = h.close[i + 1 - BARS : i + 1]
    if not (c[-1 - MOM_N] > 0.0):
        return None
    m = float(c[-1 - MOM_SKIP] / c[-1 - MOM_N]) - 1.0
    return m if np.isfinite(m) else None


def pool_scores(history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                window: int) -> dict[str, float]:
    """Up-volume share for every scoreable member; empty when fewer than MIN_NAMES."""
    out: dict[str, float] = {}
    for s in sorted(members):
        if s in EXCLUDED or s == "SPY":
            continue
        h = history.get(s)
        if h is None:
            continue
        u = up_share(h, data_date, window)
        if u is not None:
            out[s] = u
    return out if len(out) >= MIN_NAMES else {}


def banded(sc: Mapping[str, float], held: AbstractSet[str], top: int, keep: int) -> list[str]:
    order = sorted(sc, key=lambda s: (-sc[s], s))
    rank = {s: i for i, s in enumerate(order)}
    picks = sorted((s for s in held if rank.get(s, keep) < keep), key=lambda s: rank[s])[:top]
    for s in order:
        if len(picks) >= top:
            break
        if s not in picks:
            picks.append(s)
    return picks


def matched(history: Mapping[str, History], sc: Mapping[str, float], data_date: date,
            top: int) -> list[str]:
    """For each of the top-``top`` up-volume names, the other pool member nearest in 12-1 return."""
    mom: dict[str, float] = {}
    for s in sc:
        m = momentum(history[s], data_date)
        if m is not None:
            mom[s] = m
    order = sorted((s for s in sc if s in mom), key=lambda s: (-sc[s], s))
    picks = order[:top]
    rest = sorted((s for s in mom if s not in set(picks)), key=lambda s: (mom[s], s))
    out: list[str] = []
    for s in picks:
        if not rest:
            break
        j = min(range(len(rest)), key=lambda k: (abs(mom[rest[k]] - mom[s]), rest[k]))
        out.append(rest.pop(j))
    return out


def _switch_on(history: Mapping[str, History], data_date: date) -> bool:
    h = history.get(TREND[0])
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None or i + 1 < TREND[1]:
        return False
    return bool(h.close[i] > float(np.mean(h.close[i + 1 - TREND[1] : i + 1])))


class UpVolAllocator:
    """The ``top`` index members by share of dollar volume on up days (or its mirror, a
    return-matched control, or a blind draw of the up book), equal slots, fully invested."""

    id = "M0425"
    market_fields: tuple[str, ...] = ()

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return control_draw.shadow_lookback_for(BARS, DEPTH) if p.signal == "control" else BARS

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _names(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
               held: frozenset[str], p: UpVolParams) -> Sequence[str]:
        if p.signal == "control":
            def replay(d: date, shadow: AbstractSet[str]) -> tuple[list[str], list[str]]:
                pool = pool_scores(history, members, d, p.window)
                if not pool:
                    return [], []
                return sorted(pool), banded(pool, shadow, p.top, p.keep)

            return control_draw.shadow_book(replay, data_date, held, tag="M0425", seed=p.seed,
                                            depth=DEPTH)
        sc = pool_scores(history, members, data_date, p.window)
        if not sc:
            return []
        if p.signal == "match":
            return matched(history, sc, data_date, p.top)
        if p.signal == "down":
            sc = {s: -v for s, v in sc.items()}
        return banded(sc, held, p.top, p.keep)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if p.switch and not _switch_on(history, data_date):
            return ()
        names = self._names(history, members, data_date, held, p)
        if not names:
            return _bench(history, data_date)
        w = equal_weight(p.top)
        out: list[Target] = []
        for s in names:
            t = target_from_close(s, last_close(history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def prepare(self, history: Mapping[str, History]) -> Mapping[str, History]:
        return history

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


UPVOL = UpVolAllocator()


def _v(suffix: str, params: UpVolParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0425-{suffix}", family="M0425",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=UPVOL, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0425",
    name="Up-volume accumulation: stocks whose volume is concentrated on up days",
    family="stock-volume-accumulation",
    source_kind="knowledge",
    source_ref="",
    parent_id=None,
    hypothesis=(
        "Accumulation: when most of a stock's dollar volume trades on days it closes up, informed "
        "buyers are absorbing supply before the price shows it (on-balance volume, Granville 1963; "
        "Lee & Swaminathan 2000 on volume and momentum). Published sixty years ago, so the 1996-2015 "
        "dev window predates nothing: expect a small edge at best. Test: each month, among index "
        "members with 253 bars (fewer than 50 scored holds SPY), rank by the share of the last 60 "
        "sessions' dollar volume (close x volume) traded on up-close days and hold 20 in equal "
        "slots, a held name kept inside the top 40, fractional shares at Gotrade's real fees, behind "
        "the SPY 200-day switch. Arms: UP60-SW; UP120-SW (longer window); DN60-SW (the mirror, "
        "distribution); MATCH-SW (for each UP60 pick, the unpicked member nearest in 12-1 month "
        "return: price strength with no volume read); PLC-SW (UP60's size and entry count drawn "
        "blind: the no-opinion arm pricing the switch and habit); UP60 (no switch: the 2x2). "
        "Predictions written before any result: UP60-SW beats the matched control and the placebo "
        "by 1.5 or more points a year over the dev window, DN60-SW lags both, and UP60-SW leads "
        "SPY in 2009-2015."
    ),
    expected_failure=(
        "(1) Volume adds nothing beyond price strength: UP60-SW ties MATCH-SW because up days and "
        "up-day volume share are mostly a restatement of 12-month return, so the book is momentum "
        "kin of the failed momentum books and cannot be promoted. (2) The switch plus the monthly "
        "habit does the work, as it did for M0285: PLC-SW lands within a point of UP60-SW. (3) The "
        "signal is crowded out: dollar volume rewards large names, so it herds into mega-caps like "
        "the dollar-volume floor M0288 did, and trails SPY in 2009-2015. (4) The mirror DN60-SW "
        "does as well as the signal, because the quantity measured is liquidity, not direction. "
        "Any of these is a rejection, not a reason to tune the 60 and 120."
    ),
    candidates=(
        _v("UP60-SW", UpVolParams(window=60, signal="up", switch=True),
           "Top 20 by 60-day up-day dollar-volume share, behind the SPY 200-day switch"),
        _v("UP120-SW", UpVolParams(window=120, signal="up", switch=True),
           "The same on a 120-day window"),
        _v("DN60-SW", UpVolParams(window=60, signal="down", switch=True),
           "Mirror: the 20 with the lowest up-day share, heaviest distribution"),
        _v("MATCH-SW", UpVolParams(window=60, signal="match", switch=True),
           "Control: unpicked members nearest each UP60 pick in 12-1 return, no volume read"),
        _v("PLC-SW", UpVolParams(window=60, signal="control", switch=True, seed=1),
           "Placebo: UP60's book size and entries drawn blind, behind the same switch"),
        _v("UP60", UpVolParams(window=60, signal="up", switch=False),
           "UP60-SW without the switch: prices what the switch costs and earns"),
    ),
    seen_keys=("concept:up-volume-accumulation", "concept:on-balance-volume"),
)
