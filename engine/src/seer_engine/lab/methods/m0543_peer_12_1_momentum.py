"""M0543 — Do the look-alikes' twelve-month returns lead where their one-month returns did not?

Source: variation of M0542. M0542 found that a stock's peers (the k=10 index members whose daily
returns over the last 252 sessions correlate most with its own) carry no signal in their own last
21 sessions: PEER10 lost to blind draws and tied its own mirror. But M0542-OWN121 -- the same
pool, ranked on each stock's OWN 12-1 momentum (return from 252 to 21 sessions ago) -- was the one
arm in that family with a real edge. This method asks whether that edge survives being read off
the peers instead of the stock itself: score each stock on the equal-weight 12-1 momentum of its
k=10 nearest-correlated peers, never its own.

Arms (``signal``):
    peer121   the rule: top 20 by the peers' average 12-1 momentum, k=10, always invested
    mirror    the 20 LOWEST peer-12-1 scores: if the signal is real this must lose
    draw      a blind draw matched to the peer-12-1 book's turnover and entry count
              (``control_draw.matched_book``), the no-opinion arm; the five seeds are the noise band

``switch`` puts the SPY 200-day filter in front (all cash while SPY closes at or below its
200-session average), priced against PEER121 (``switch=False``) itself, which already is the
always-invested baseline -- no separate arm is needed for that.

This file does not call ``M0542``'s ``peer_scores``: that function returns, per stock, the peers'
AVERAGE OWN-21-SESSION return and the stock's OWN 12-1 return, but not the peers' individual 12-1
returns, and averaging those needs each stock's peer INDICES, which ``peer_scores`` does not
expose. ``peer121_scores`` below re-derives the same correlation and clean-pool steps (``CORR_N``,
``PEER_N``, ``MIN_POOL``, imported from M0542 so the two methods' pools and correlation windows
never drift apart) and reads one different column off the same peer set.

M0542-OWN121's own book is never re-run here: it is already recorded (M0542 trial, kin check), and
the comparison in the analysis reads that trial back rather than repeating its book under a new id.

Pure: reads only bars dated at or before ``data_date``. Same simplification as M0542, written down
there and inherited here: no share counts, so no size pool, and one share class per company is not
deduplicated.
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
from seer_engine.lab.methods.m0542_comovement_peer_momentum import BARS, CORR_N, MIN_POOL, PEER_N, TREND, _switch_on
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 11, 12)

_SIGNALS = ("peer121", "mirror", "draw")


@dataclass(frozen=True, slots=True)
class Peer121Params:
    signal: str = "peer121"
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


def _check(params: object) -> Peer121Params:
    if not isinstance(params, Peer121Params):
        raise TypeError(f"params must be Peer121Params, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True, eq=False)
class Peer121Prepared:
    history: Mapping[str, History] = field(repr=False)
    panel: Panel | None = field(repr=False)


def peer121_scores(panel: Panel, members: AbstractSet[str], data_date: date,
                   k: int) -> dict[str, float]:
    """Per clean member: the equal-weight 12-1 momentum of its ``k`` nearest-correlated peers,
    never its own. Clean and correlated exactly as M0542's ``peer_scores`` defines them; the only
    change is which column is read off each peer once they are found."""
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
    mom = c[:, -1 - PEER_N] / c[:, 0] - 1.0  # each stock's own 12-1 momentum
    peer_mom = mom[peers].mean(axis=1)  # the k peers' average 12-1 momentum, never its own
    return {s: float(peer_mom[i]) for i, s in enumerate(names) if np.isfinite(peer_mom[i])}


def _rank(sc: Mapping[str, float], top: int, reverse: bool) -> list[str]:
    order = sorted(sc, key=lambda s: (sc[s] if reverse else -sc[s], s))
    return order[:top]


def _book(prepared: "Peer121Prepared", members: AbstractSet[str], d: date,
         p: Peer121Params) -> tuple[list[str], list[str]]:
    """(pool, the signal's top book) on ``d``; both empty when the pool is too thin."""
    if prepared.panel is None:
        return [], []
    sc = peer121_scores(prepared.panel, members, d, p.k)
    if not sc:
        return [], []
    return sorted(sc), _rank(sc, p.top, p.signal == "mirror")


class Peer121Allocator:
    id = "M0543"

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

    def _run(self, prepared: Peer121Prepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: Peer121Params) -> tuple[Target, ...]:
        if p.switch and not _switch_on(prepared.history, data_date):
            return ()
        if p.signal == "draw":
            book_params = Peer121Params(signal="peer121", k=p.k, top=p.top)

            def select(d: date) -> tuple[Sequence[str], Sequence[str]]:
                return _book(prepared, members, d, book_params)

            names = control_draw.matched_book(select, data_date, held, tag="M0543", seed=p.seed)
        else:
            names = _book(prepared, members, data_date, p)[1]
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
        return self._run(Peer121Prepared(history, build_panel(history, "SPY")), members, data_date,
                         held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> Peer121Prepared:
        return Peer121Prepared(history, build_panel(history, "SPY"))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, Peer121Prepared):
            raise TypeError(f"prepared must be Peer121Prepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


PEER121 = Peer121Allocator()


def _v(suffix: str, params: Peer121Params, rationale: str) -> Candidate:
    return Candidate(id=f"M0543-{suffix}", family="M0543", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=PEER121, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


def _draw(seed: int) -> Candidate:
    return _v(f"DRAW{seed}", Peer121Params(signal="draw", seed=seed),
              f"Blind draw {seed} matched to the peer-12-1 book's turnover and entry count, no gate")


METHOD = Method(
    id="M0543",
    name="Do the look-alikes' twelve-month returns lead where their one-month returns did not?",
    family="stock-peer-spillover",
    source_kind="variation",
    source_ref="M0542",
    parent_id="M0542",
    hypothesis=(
        "M0542 found that a stock's peers (the k=10 index members most correlated with it over "
        "the last 252 sessions) predicted nothing from their own last-21-session return: PEER10 "
        "lost to blind draws and tied its own mirror. But M0542-OWN121 (own 12-1 momentum, the "
        "same pool's kin check, not a peer signal) was the one arm in that family with a real "
        "edge: DSR 0.529 at N=353, PF 1.40, +9.6%/yr money-weighted, failing only on worst-case "
        "drawdown (60.7%) and the luck bar. This variation asks whether that edge travels through "
        "the peer link: score each stock on the equal-weight 12-1 momentum (return from 252 to 21 "
        "sessions ago) of its k=10 nearest-correlated peers, never its own -- same correlation "
        "window and clean-pool rules as M0542, fractional shares at Gotrade's real fees, 20-name "
        "book, monthly. Run (3 arms): PEER121 (the rule, always invested), PEER121-GATE (behind "
        "the SPY 200-day switch, so the habit's cost is priced against the same book without it), "
        "MIRROR (the 20 LOWEST peer-12-1 scores; if the signal is real this must lose). "
        "Amendment, pre-registered in the same commit: five hash-seeded blind draws matched to "
        "PEER121's book (turnover and entry count), the noise band. SUCCESS needs all of: PEER121 "
        "beats total-return SPY, beats its best draw by more than the draws' own measured spread "
        "(about 7.5 pts/yr), clears the dev screen (max drawdown <= 50%, profit factor >= 1.3, >= "
        "100 closed trades), MIRROR loses, and a positive 2009-2015 edge (the highest-coverage, "
        "least survivorship-biased era). No one arm is read alone, and PEER121's curve is compared "
        "in the analysis against M0542-OWN121's own recorded trial -- never re-run here."
    ),
    expected_failure=(
        "Peers' 12-1 momentum is still mostly sector or market beta in disguise, the same failure "
        "mode M0542 found for peers' last-month return: the book is kin of the lab's failed "
        "momentum books whatever this family is called, and is refused at the hard gate on kin "
        "however well it scores on dev. Or the lead sits inside the draws' noise band, as PEER10's "
        "did. Or PEER121 turns out to be the same curve as M0542-OWN121 (correlated peers tend to "
        "share the same 12-1 winners, so averaging across them may just re-derive the stock's own "
        "signal with extra steps), in which case the peer link adds nothing new and this method is "
        "a repeat, not a finding. Or, like PEER10's mirror tying the rule, MIRROR does not lose "
        "because a 252-to-21-session window is long enough that reversal effects wash out either "
        "way."
    ),
    candidates=(
        _v("PEER121", Peer121Params(signal="peer121", k=10),
           "The rule: top 20 by the peers' average 12-1 momentum, always invested"),
        _v("PEER121-GATE", Peer121Params(signal="peer121", k=10, switch=True),
           "The same book behind the SPY 200-day switch"),
        _v("MIRROR", Peer121Params(signal="mirror", k=10),
           "The 20 lowest peer-12-1 scores: must lose if the signal is real"),
    ),
    amendments=(
        Amendment(
            added=ADDED,
            why="The noise band: five blind draws of the peer-12-1 book, no opinion on names",
            hypothesis=(
                "Five seeds of control_draw.matched_book on the PEER121 book (same pool, same "
                "turnover and entry count, no gate). If PEER121's lead over SPY sits inside the "
                "spread of these five it is not readable as a signal."
            ),
            expected_failure=(
                "The draws land within a few points of PEER121 (the lab's draws span about 7.5 "
                "pts a year), so the peer-12-1 rule cannot be told from picking names by hash."
            ),
            candidates=tuple(_draw(s) for s in range(1, 6)),
        ),
    ),
    seen_keys=("concept:peer-12-1-momentum", "concept:cross-stock-12-1-momentum-peers"),
)
