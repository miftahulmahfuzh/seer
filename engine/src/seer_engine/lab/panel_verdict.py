"""The signal panel's published verdict: which recorded panels clear stage one of the lab.

A panel **clears** when all three of these hold, and the three are exactly the readings the owner
asked the panel for (SERA_SIGNAL_PANEL_PLAN.md, Decisions: "The panel bar"):

1. on the current dev store, over the whole window, its controlled slope -- next month's return
   on the signal once momentum, beta, size and volatility are allowed for -- is positive, and its
   one-sided p-value survives a Benjamini-Hochberg correction at ``FDR`` across **every distinct
   pick set ever recorded on that store**, replays of already-run methods included;
2. on the same store, its top bucket beat the pool from 2009 to 2015 (the era the lab's dev
   window says least about and the owner's real money says most about);
3. on the survivorship store, with the delisted companies put back, its whole-window controlled
   slope is still positive.

**Computed on read, never stored.** The correction is a statement about the whole population of
panels, so it moves every time a panel is recorded -- a q-value written into a row would be wrong
the next day. ``store.snapshot`` and ``lab panel-map`` call ``published`` at export or print
time, as the luck gate's N is resolved at export time rather than stored.

**Twins.** Two panels whose top buckets are identical in every month (equal ``picks_hash``) are
one experiment run twice. The correction counts the pick set **once**, carried by the panel
recorded first (``panel_signals.created``, ties broken by id); every later one reads as a twin of
it, never clears in its own name, and shows its first's q-value. Without this, re-recording one
idea under ten names would buy ten tickets in the correction, and replaying a family of methods
that pick the same names would dilute every other signal's q-value with copies.

**Why Student's t, and why here.** ``fm_t`` is the t-statistic of a mean of ``months`` monthly
slopes, so its null distribution is Student's t on ``months - 1`` degrees of freedom. The lab
declares no scipy (invariant 8: no new runtime dependency), so the tail is the regularised
incomplete beta function evaluated by its continued fraction -- about thirty lines, checked
against scipy in the tests where scipy happens to be installed.

``RULE_ID`` names the panel rule whose readings are judged together; readings under any other
rule are ignored, because a correction across two different measurements is not a correction.
It must equal ``panel.RULE_ID`` (phase 1).

The reasons are sentences the owner reads on ``/sera/signals``: plain words, no ids, no numbers.
"""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from seer_engine.lab import store

RULE_ID = "panel-v1"
FDR = 0.10

WHOLE = "all"
RECENT = "2009-2015"

UNMEASURED_REASON = "it has not been measured on the current price history"
TWIN_REASON = (
    "it picks exactly the same stocks every month as an earlier signal, so it is counted once, "
    "as that one"
)
SLOPE_REASON = (
    "once momentum, market sensitivity, size and volatility are allowed for, the stocks it ranks "
    "highest did no better than the rest"
)
CHANCE_REASON = "its edge is no bigger than luck produces when this many ideas have been tried"
# A missing era row means phase 1 measured fewer than ``panel.MIN_ERA_MONTHS`` (12) months there,
# or never measured that store: either way the condition fails, in words (reconciled, Decisions).
RECENT_MISSING_REASON = "there are not enough months from 2009 to 2015 to say whether it worked then"
RECENT_REASON = "its top picks did not beat the rest of the index from 2009 to 2015"
SURVIVORSHIP_MISSING_REASON = (
    "it has not been measured over enough months with the companies that later disappeared put back"
)
SURVIVORSHIP_REASON = "with the companies that later disappeared put back, its edge goes away"

_MAX_ITER = 10_000
_TINY = 1e-300


@dataclass(frozen=True)
class Verdict:
    """One recorded panel, judged against every other one as the lab stands now.

    ``q`` is the Benjamini-Hochberg q-value of its pick set (a twin shows its first's), None when
    it has no whole-window reading on the dev store being judged. ``reasons`` names every failed
    condition in plain words and is empty exactly when ``clears``. ``twin_of`` is the id of the
    earlier panel with the identical pick set, or None.
    """

    signal_id: str
    clears: bool
    q: float | None
    reasons: tuple[str, ...]
    twin_of: str | None


@dataclass(frozen=True)
class Readings:
    """One panel's rows by era: on the dev store being judged, and on the newest survivorship
    store it was measured on. An era with no row is absent from its mapping."""

    dev: Mapping[str, Mapping[str, Any]]
    survivorship: Mapping[str, Mapping[str, Any]]


def _beta_fraction(a: float, b: float, x: float) -> float:
    """The continued fraction of the incomplete beta function (modified Lentz)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > _TINY else _TINY)
    h = d
    for m in range(1, _MAX_ITER + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > _TINY else _TINY)
        c = 1.0 + aa / c
        c = c if abs(c) > _TINY else _TINY
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > _TINY else _TINY)
        c = 1.0 + aa / c
        c = c if abs(c) > _TINY else _TINY
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def _regularized_beta(a: float, b: float, x: float) -> float:
    """I_x(a, b), the regularised incomplete beta function, for a, b > 0."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_fraction(a, b, x) / a
    return 1.0 - front * _beta_fraction(b, a, 1.0 - x) / b


def one_sided_p(t: float, months: int) -> float:
    """P(T > t) for Student's t on ``months - 1`` degrees of freedom: the chance of a slope at
    least this far above zero if the signal does nothing.

    1.0 -- never significant -- when there are fewer than two months (no spread to divide by) or
    the statistic is not finite.
    """
    df = int(months) - 1
    t = float(t)
    if df < 1 or not math.isfinite(t):
        return 1.0
    tail = 0.5 * _regularized_beta(0.5 * df, 0.5, df / (df + t * t))
    return tail if t > 0 else 1.0 - tail


def bh_qvalues(pvalues: Sequence[float]) -> list[float]:
    """Benjamini-Hochberg q-values, in the input's order, capped at 1.

    The q-value of the k-th smallest of m p-values is the smallest ``p_(j) * m / j`` over every
    j >= k: the lowest false-discovery rate at which that hypothesis would still be rejected.
    """
    m = len(pvalues)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: (float(pvalues[i]), i))
    q = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, float(pvalues[i]) * m / rank)
        q[i] = running
    return q


def current_dev_fingerprint(conn: sqlite3.Connection) -> str | None:
    """The dev store the newest dev reading under ``RULE_ID`` was taken on, or None.

    What "the current dev store" means to a reader that has not loaded one -- the snapshot and
    ``lab panel-map``. A caller that has loaded the store passes its fingerprint to ``published``
    instead, and that wins.
    """
    newest: str | None = None
    for r in store.panel_results(conn):  # oldest first: the last match is the newest
        if r["store_role"] == "dev" and r["rule_id"] == RULE_ID:
            newest = str(r["store_fingerprint"])
    return newest


def readings(
    conn: sqlite3.Connection, *, dev_fingerprint: str | None = None
) -> dict[str, Readings]:
    """Every recorded panel's rows under ``RULE_ID``, by era, keyed by signal id.

    ``dev`` holds the rows on ``dev_fingerprint`` (``current_dev_fingerprint`` when None);
    ``survivorship`` holds the rows on the newest survivorship store that panel was measured on.
    Empty when the tables are absent.
    """
    fp = dev_fingerprint if dev_fingerprint is not None else current_dev_fingerprint(conn)
    dev: dict[str, dict[str, Mapping[str, Any]]] = {}
    sv_rows: dict[str, list[Mapping[str, Any]]] = {}
    for r in store.panel_results(conn):
        if r["rule_id"] != RULE_ID:
            continue
        sid = str(r["signal_id"])
        if r["store_role"] == "dev":
            if fp is not None and str(r["store_fingerprint"]) == fp:
                dev.setdefault(sid, {})[str(r["era"])] = r
        else:
            sv_rows.setdefault(sid, []).append(r)
    out: dict[str, Readings] = {}
    for s in store.panel_signals(conn):
        sid = str(s["id"])
        rows = sv_rows.get(sid, [])
        newest_fp = str(rows[-1]["store_fingerprint"]) if rows else None
        sv = {str(r["era"]): r for r in rows if str(r["store_fingerprint"]) == newest_fp}
        out[sid] = Readings(dev=dev.get(sid, {}), survivorship=sv)
    return out


def published(
    conn: sqlite3.Connection, *, dev_fingerprint: str | None = None
) -> dict[str, Verdict]:
    """Every recorded panel's verdict, keyed by signal id, judged on ``dev_fingerprint``
    (``current_dev_fingerprint`` when None). Empty when no panel is recorded or the tables are
    absent. See the module docstring for the three conditions and the twin rule.
    """
    signals = store.panel_signals(conn)
    if not signals:
        return {}
    fp = dev_fingerprint if dev_fingerprint is not None else current_dev_fingerprint(conn)
    reads = readings(conn, dev_fingerprint=fp)

    first_of_picks: dict[str, str] = {}
    twin_of: dict[str, str] = {}
    pvalue: dict[str, float] = {}  # one entry per distinct pick set, keyed by its first panel
    for s in sorted(signals, key=lambda s: (str(s["created"]), str(s["id"]))):
        sid = str(s["id"])
        whole = reads[sid].dev.get(WHOLE)
        if whole is None:
            continue
        picks = str(whole["picks_hash"])
        if picks in first_of_picks:
            twin_of[sid] = first_of_picks[picks]
            continue
        first_of_picks[picks] = sid
        pvalue[sid] = one_sided_p(float(whole["fm_t"]), int(whole["months"]))
    firsts = list(pvalue)
    q_of = dict(zip(firsts, bh_qvalues([pvalue[f] for f in firsts])))

    out: dict[str, Verdict] = {}
    for s in signals:
        sid = str(s["id"])
        r = reads[sid]
        whole = r.dev.get(WHOLE)
        if whole is None:
            out[sid] = Verdict(sid, False, None, (UNMEASURED_REASON,), None)
            continue
        if sid in twin_of:
            first = twin_of[sid]
            out[sid] = Verdict(sid, False, q_of[first], (TWIN_REASON,), first)
            continue
        q = q_of[sid]
        reasons: list[str] = []
        if not float(whole["fm_slope"]) > 0:
            reasons.append(SLOPE_REASON)
        elif q > FDR:
            reasons.append(CHANCE_REASON)
        recent = r.dev.get(RECENT)
        if recent is None:
            reasons.append(RECENT_MISSING_REASON)
        elif not float(recent["spread_top"]) > 0:
            reasons.append(RECENT_REASON)
        sv_whole = r.survivorship.get(WHOLE)
        if sv_whole is None:
            reasons.append(SURVIVORSHIP_MISSING_REASON)
        elif not float(sv_whole["fm_slope"]) > 0:
            reasons.append(SURVIVORSHIP_REASON)
        out[sid] = Verdict(sid, not reasons, q, tuple(reasons), None)
    return out
