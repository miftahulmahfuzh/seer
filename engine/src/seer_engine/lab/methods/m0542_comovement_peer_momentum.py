"""M0542 — Stocks whose statistically linked peers just rose: a co-movement peer momentum book.

Source: Yan & Yu (2023) cross-stock momentum; Li & Yan (2025); HKUST synchronized-stock-returns
note (2025/01). The idea is that information reaches a stock late through the stocks that move
with it, so a stock whose closest co-movers just rose is expected to follow. A statistical link,
not an industry label, which is what separates it from M0295 (the industry's biggest name leads).

Each decision, among the index members that have a full year of closes, a stock's peers are the
``k`` others whose daily returns over the last 252 sessions correlate most with its own. The score
is the equal-weight return of those peers over the last 21 sessions (the stock's own return is
never in it). The book holds the top 20 by score, equal slots, monthly, fractional shares at
Gotrade's real fees.

Arms (``signal``):
    peer      the rule: top 20 by peer score, k=10, always invested
    mirror    the 20 LOWEST peer scores: if the signal is real this must lose
    own1m     the same pool ranked on each stock's own last-21-session return (plain own-return,
              the same window the peers are read over: short-term reversal if it works at all)
    own121    classic 12-1 own momentum (return from 252 to 21 sessions ago), the kin check
    draw      a blind draw matched to the peer book's turnover and entry count
              (``control_draw.matched_book``), the no-opinion arm; the five seeds are the noise band

``switch`` puts the SPY 200-day filter in front (all cash while SPY closes at or below its
200-session average) so the habit's cost is priced against the same book without it.

Pure: reads only bars dated at or before ``data_date``. No share counts, so no size pool; the pool
is every index member with a clean 253-session close run, and one share class per company is not
deduplicated (a known simplification, written down here, applied equally to every arm).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0182_average_correlation_clock import EXCLUDED, Panel, build_panel
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 11, 10)
CORR_N = 252  # sessions of daily returns behind each correlation
PEER_N = 21  # sessions the peers' return is read over (the prior month)
BARS = CORR_N + 1  # closes needed
TREND = ("SPY", 200)
MIN_POOL = 60  # fewer clean names than this and the book falls back to SPY

_SIGNALS = ("peer", "mirror", "own1m", "own121", "draw")


@dataclass(frozen=True, slots=True)
class PeerParams:
    signal: str = "peer"
    k: int = 10
    top: int = 20
    switch: bool = False
    seed: int = 0

    def __post_init__(self) -> None:
        if self.signal not in _SIGNALS:
            raise ValueError(f"signal must be one of {_SIGNALS}, got {self.signal!r}")
        for name in ("k", "top", "seed"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.k < 1 or self.top < 1 or self.seed < 0:
            raise ValueError("k and top must be >= 1 and seed >= 0")
        if not isinstance(self.switch, bool):
            raise TypeError("switch must be a bool")

    def as_dict(self) -> dict[str, str]:
        return {"signal": self.signal, "k": str(self.k), "top": str(self.top),
                "switch": f"{TREND[0]}:{TREND[1]}" if self.switch else "none",
                "seed": str(self.seed), "corr_n": str(CORR_N), "peer_n": str(PEER_N)}


def _check(params: object) -> PeerParams:
    if not isinstance(params, PeerParams):
        raise TypeError(f"params must be PeerParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True, eq=False)
class PeerPrepared:
    history: Mapping[str, History] = field(repr=False)
    panel: Panel | None = field(repr=False)


def peer_scores(panel: Panel, members: AbstractSet[str], data_date: date,
                k: int) -> dict[str, tuple[float, float, float]]:
    """Per clean member: (peer return, own 21-session return, own 12-1 return) on ``data_date``.

    Clean means a finite close on each of the last 253 sessions of SPY's calendar. Peers are the
    ``k`` highest-correlated other clean members over the last 252 daily returns."""
    j = int(np.searchsorted(panel.dates, np.datetime64(data_date, "D"), side="right")) - 1
    if j + 1 < BARS:
        return {}
    names = sorted(s for s in members if s in panel.row and s not in EXCLUDED and s != "SPY")
    if len(names) < MIN_POOL:
        return {}
    rows = np.asarray([panel.row[s] for s in names])
    c = panel.close[rows, j + 1 - BARS : j + 1]
    ok = np.all(np.isfinite(c) & (c > 0.0), axis=1)
    if int(ok.sum()) < MIN_POOL:
        return {}
    names = [s for s, g in zip(names, ok.tolist(), strict=True) if g]
    c = c[ok]
    r = c[:, 1:] / c[:, :-1] - 1.0
    z = r - r.mean(axis=1, keepdims=True)
    sd = np.sqrt((z * z).sum(axis=1))
    good = sd > 0.0
    if int(good.sum()) < MIN_POOL:
        return {}
    names = [s for s, g in zip(names, good.tolist(), strict=True) if g]
    c, z, sd = c[good], z[good], sd[good]
    z = z / sd[:, None]
    corr = z @ z.T
    np.fill_diagonal(corr, -np.inf)
    kk = min(k, len(names) - 1)
    peers = np.argpartition(-corr, kk - 1, axis=1)[:, :kk]
    own = c[:, -1] / c[:, -1 - PEER_N] - 1.0
    mom = c[:, -1 - PEER_N] / c[:, 0] - 1.0
    peer = own[peers].mean(axis=1)
    return {s: (float(peer[i]), float(own[i]), float(mom[i])) for i, s in enumerate(names)
            if np.isfinite(peer[i]) and np.isfinite(own[i]) and np.isfinite(mom[i])}


def _rank(sc: Mapping[str, float], top: int, reverse: bool) -> list[str]:
    order = sorted(sc, key=lambda s: (sc[s] if reverse else -sc[s], s))
    return order[:top]


def _switch_on(history: Mapping[str, History], data_date: date) -> bool:
    h = history.get(TREND[0])
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None or i + 1 < TREND[1]:
        return False
    return bool(h.close[i] > float(np.mean(h.close[i + 1 - TREND[1] : i + 1])))


def _book(prepared: PeerPrepared, members: AbstractSet[str], d: date, p: PeerParams,
          signal: str) -> tuple[list[str], list[str]]:
    """(pool, the signal's top book) on ``d``; both empty when the pool is too thin."""
    if prepared.panel is None:
        return [], []
    sc = peer_scores(prepared.panel, members, d, p.k)
    if not sc:
        return [], []
    col = {"peer": 0, "mirror": 0, "own1m": 1, "own121": 2}[signal]
    return sorted(sc), _rank({s: v[col] for s, v in sc.items()}, p.top, signal == "mirror")


class PeerAllocator:
    id = "M0542"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return BARS + (control_draw.PREVIOUS_DECISION_BARS + 1 if p.signal == "draw" else 0)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: PeerPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: PeerParams) -> tuple[Target, ...]:
        if p.switch and not _switch_on(prepared.history, data_date):
            return ()
        if p.signal == "draw":
            def select(d: date) -> tuple[Sequence[str], Sequence[str]]:
                return _book(prepared, members, d, p, "peer")

            names = control_draw.matched_book(select, data_date, held, tag="M0542", seed=p.seed)
        else:
            names = _book(prepared, members, data_date, p, p.signal)[1]
        if not names:
            t = target_from_close("SPY", last_close(prepared.history.get("SPY"), data_date),
                                  equal_weight(1))
            return (t,) if t is not None else ()
        w = equal_weight(p.top)
        out: list[Target] = []
        for s in names:
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(PeerPrepared(history, build_panel(history, "SPY")), members, data_date,
                         held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> PeerPrepared:
        return PeerPrepared(history, build_panel(history, "SPY"))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, PeerPrepared):
            raise TypeError(f"prepared must be PeerPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


PEER = PeerAllocator()


def _v(suffix: str, params: PeerParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0542-{suffix}", family="M0542", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=PEER, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


def _draw(seed: int) -> Candidate:
    return _v(f"DRAW{seed}", PeerParams(signal="draw", seed=seed),
              f"Blind draw {seed} matched to the peer book's turnover and entry count, no gate")


METHOD = Method(
    id="M0542",
    name="Stocks whose statistically linked peers just rose: a co-movement peer momentum book",
    family="stock-peer-spillover",
    source_kind="paper",
    source_ref="Yan & Yu (2023) cross-stock momentum; Li & Yan (2025); HKUST bizinsight 2025/01 "
               "synchronized-stock-returns",
    parent_id=None,
    hypothesis=(
        "Each stock's peers are the k=10 index members whose daily returns over the last 252 "
        "sessions correlate most with its own (a statistical link, unlike M0295's industry "
        "labels). Score each stock on the equal-weight return of its peers over the last 21 "
        "sessions, never its own, and hold the top 20, equal slots, monthly, in fractional shares "
        "at Gotrade's real fees (a limit order takes fractions; 20 slots of the 20M IDR lab "
        "account are about $55 each). Published 2023-2025, so the dev window ends before the "
        "crowd and a dev lead is plausibly an edge that will not last. Run 1 (six arms): PEER10 "
        "(the rule, always invested, no cash months), PEER10-GATE (the same behind the SPY "
        "200-day switch, so the habit's cost is priced), PEER30 (k=30, a dose rung), MIRROR (the "
        "20 lowest peer scores; must lose), OWN1M (the same pool on each stock's own last-month "
        "return: plain own-return, the kin check) and OWN121 (own 12-1 momentum, the classic "
        "kin). Amendment, pre-registered in the same commit: five hash-seeded blind draws matched "
        "to PEER10's turnover and entry count, the noise band. Assumption: the owner's wording "
        "'gate on and off' is covered by PEER10 and PEER10-GATE; draws are gate-off only. "
        "SUCCESS needs all of: PEER10 beats SPY, beats its best draw by more than the draws' own "
        "spread, MIRROR loses, PEER10 is not the same curve as OWN1M or OWN121, and a positive "
        "2009-2015 edge. No one arm is read alone."
    ),
    expected_failure=(
        "Peer return is own momentum in disguise: the peers of a stock are mostly its own sector, "
        "so ranking on the peers' last month is sector momentum, and the book is kin of the "
        "failed momentum books and is refused at the hard gate whatever it earns. If not, the "
        "lead sits inside the draws' spread (the lab's blind draws span about 7.5 pts a year), "
        "or the book without a gate falls past the 15% / 20% bars in 2008 and 2020-style "
        "crashes, when everything moves together and peers carry no news. Also possible: the "
        "peer-last-month effect is short-term reversal in this large-cap pool, so MIRROR does "
        "not lose."
    ),
    candidates=(
        _v("PEER10", PeerParams(signal="peer", k=10), "The rule: top 20 by peer return, always invested"),
        _v("PEER10-GATE", PeerParams(signal="peer", k=10, switch=True),
           "The same book behind the SPY 200-day switch"),
        _v("PEER30", PeerParams(signal="peer", k=30), "More peers per stock: a dose rung"),
        _v("MIRROR", PeerParams(signal="mirror", k=10), "The 20 lowest peer scores: must lose"),
        _v("OWN1M", PeerParams(signal="own1m"), "Own last-month return on the same pool"),
        _v("OWN121", PeerParams(signal="own121"), "Own 12-1 momentum on the same pool"),
    ),
    amendments=(
        Amendment(
            added=ADDED,
            why="The noise band: five blind draws of the peer book, no opinion on names",
            hypothesis=(
                "Five seeds of control_draw.matched_book on the PEER10 book (same pool, same "
                "turnover and entry count, no gate). If PEER10's lead over SPY sits inside the "
                "spread of these five it is not readable as a signal."
            ),
            expected_failure=(
                "The draws land within a few points of PEER10 (the lab's draws span about 7.5 pts "
                "a year), so the peer rule cannot be told from picking names by hash."
            ),
            candidates=tuple(_draw(s) for s in range(1, 6)),
        ),
    ),
    seen_keys=("concept:comovement-peer-momentum", "concept:cross-stock-momentum-correlated-peers"),
)
