"""The N the luck gate deflates by: the named policies and the effective-N estimator.

``deflated_sharpe`` (``backtest/dev.py``) assumes ``n_trials`` **independent** trial Sharpes.
The lab feeds it one per trial *row*, and the rows are not independent: measured over the
month-end equity curves the database already stores, the mean pairwise correlation across the
dev trials is ~0.60 and the participation ratio of their correlation matrix is ~2.4. Deflating
by the row count therefore asserts an independence the data contradicts and overstates the
hurdle (lab-luck-gate analysis, "The trials are not independent, and this is measurable").

This module names the three candidate answers and measures the evidence behind them. It
decides nothing: it is pure (reads, never writes; no clock, no filesystem, no network) and
nothing in the lab calls it until the gate is wired to it.

The policies:

- ``all-trials`` -- one look per dev trial row. The literal reading of design §3 and what the
  lab did before this module existed. 126 on the committed database.
- ``methods`` -- one look per distinct method with a dev trial, floored at the measured
  participation ratio: ``N = max(distinct_methods, ceil(participation_ratio))``. Counts a
  family of variants as the one idea it is, and the floor guarantees the policy can never
  assert fewer independent looks than the curves themselves show. 28 on the committed database.
- ``effective`` -- the measured participation ratio alone, rounded, floored at 2 (below 2 the
  deflated Sharpe is undefined). 2 on the committed database. The honest measure of how many
  independent *return streams* exist, and for that reason not a count of how many times the
  search looked: every strategy in the lab holds US large-cap equities, so the streams collapse
  onto the market factor. Kept live so the gate's sensitivity is inspectable.

The participation ratio is ``(Σλ)² / Σλ²`` over the eigenvalues of the correlation matrix of
the trials' monthly returns -- 1 when every curve is the same curve, N when they are mutually
uncorrelated.
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from typing import Literal

import numpy as np

Policy = Literal["all-trials", "methods", "effective"]

POLICIES: tuple[Policy, ...] = ("all-trials", "methods", "effective")

# The policy a caller that does not name one gets. It is deliberately the same policy the lab
# actually ships -- ``store.DSR_POLICY = "methods"`` (lab-realistic-gate R1; it was
# ``"all-trials"`` until 2026-10-08) -- so that no code path can ever be deflated by an N the gate
# does not use. ``store`` sets its own constant explicitly and passes it to ``effective_n`` on
# every call, so this default is a belt beside that brace rather than the thing the gate relies
# on; the two agreeing is what makes a mistaken inheritance harmless instead of silent.
#
# **This constant moves whenever ``store.DSR_POLICY`` moves, and only then.**
# ``test_the_policy_names_are_a_closed_set`` pins the equality from this side and
# ``test_the_shipped_defaults_reproduce_todays_n`` from the other.
DEFAULT_POLICY: Policy = "methods"

# A curve needs this many month-ends to yield a variance, and the aligned grid this many to
# yield one return per trial that is worth correlating.
_MIN_POINTS = 3
# deflated_sharpe returns None below two trials, so no policy may resolve lower than this --
# except ``all-trials``, which is the literal row count and keeps reading 0 on an empty lab.
DSR_MIN_N = 2


class UnknownPolicy(ValueError):
    """A policy name that is not one of ``POLICIES``."""


@dataclass(frozen=True)
class Correlation:
    """What the dev curves say about how many independent looks the lab actually took.

    ``mean_pairwise`` is None when fewer than two curves survived alignment, which is also the
    case in which ``participation_ratio`` falls back to 1.0 rather than being measured.
    """

    participation_ratio: float
    mean_pairwise: float | None
    curves_used: int
    month_ends: int


@dataclass(frozen=True)
class NCount:
    """The N one policy resolves to, and the evidence a caller can print to say why."""

    n: int
    policy: Policy
    trial_rows: int
    distinct_methods: int
    participation_ratio: float
    mean_pairwise_corr: float | None
    curves_used: int
    month_ends: int

    @property
    def floored(self) -> bool:
        """True when the ``methods`` policy's participation-ratio floor is what decided ``n``.

        The floor is the policy's justification: it cannot assert fewer independent looks than
        the curves measurably have. On the committed database it does not bind (ceil(2.34) = 3
        against 28 methods); a lab of one method with many uncorrelated variants is where it does.
        """
        return self.policy == "methods" and math.ceil(self.participation_ratio) > self.distinct_methods

    @property
    def basis(self) -> str:
        """One line saying *what was counted* to get ``n``, in plain words. Never empty.

        Written verbatim into every committed ``docs/lab/prereg/MNNNN.md`` and into
        ``web/data/lab.json``'s ``gate.dsrNBasis``, both of which are one-line fields, so this
        must never contain a newline and must be stable for a given database. It says only what
        was counted; the caller already prints ``n`` and ``policy`` beside it, which is why this
        does not repeat them the way ``evidence()`` does.
        """
        rho = "" if self.mean_pairwise_corr is None else (
            f", mean pairwise correlation {self.mean_pairwise_corr:.3f}"
        )
        if self.policy == "all-trials":
            return (
                f"{self.trial_rows} dev trials, every variant run counted as one independent look"
            )
        if self.policy == "methods":
            floored = " (the participation-ratio floor binds)" if self.floored else ""
            return (
                f"{self.distinct_methods} distinct methods with a dev trial across "
                f"{self.trial_rows} trial rows, floored at ceil(participation ratio "
                f"{self.participation_ratio:.2f}){floored}"
            )
        return (
            f"participation ratio {self.participation_ratio:.2f} over {self.curves_used} dev "
            f"curves on {self.month_ends} common month-ends{rho}"
        )

    def evidence(self) -> str:
        rho = "n/a" if self.mean_pairwise_corr is None else f"{self.mean_pairwise_corr:.3f}"
        floor = " (the participation-ratio floor binds)" if self.floored else ""
        return (
            f"N = {self.n} under policy {self.policy!r}{floor}: "
            f"{self.trial_rows} dev trial rows, {self.distinct_methods} distinct methods, "
            f"participation ratio {self.participation_ratio:.2f} and mean pairwise correlation "
            f"{rho} over {self.curves_used} curves on {self.month_ends} common month-ends"
        )


def check_policy(policy: str) -> Policy:
    """``policy`` itself when it names a policy; raise ``UnknownPolicy`` otherwise."""
    if policy not in POLICIES:
        known = ", ".join(POLICIES)
        raise UnknownPolicy(f"unknown N policy {policy!r}; known policies: {known}")
    return policy  # type: ignore[return-value]


def dev_method_count(conn: sqlite3.Connection) -> int:
    """How many distinct methods have at least one dev trial."""
    return int(
        conn.execute("SELECT count(DISTINCT method_id) FROM trials WHERE window = 'dev'").fetchone()[0]
    )


def _dev_curves(conn: sqlite3.Connection) -> list[dict[str, float]]:
    """Every dev trial's month-end equity curve as {month-end: level}, skipping unusable ones.

    ``curve_json`` is NOT NULL on the table, but a curve can still be empty or short (a trial
    with almost no history), and this module must never raise on data it only reads.
    """
    out: list[dict[str, float]] = []
    for row in conn.execute("SELECT curve_json FROM trials WHERE window = 'dev' ORDER BY n"):
        text = row[0]
        if not text:
            continue
        try:
            points = json.loads(text)
        except (TypeError, ValueError):
            continue
        if not isinstance(points, list):
            continue
        curve: dict[str, float] = {}
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                continue
            day, value = point
            try:
                level = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(level):
                curve[str(day)] = level
        if len(curve) >= _MIN_POINTS:
            out.append(curve)
    return out


def _return_matrix(curves: list[dict[str, float]]) -> tuple[np.ndarray, int]:
    """(one row of monthly returns per usable curve, number of common month-ends).

    The curves are aligned on the month-ends common to *every* one of them, so each row is the
    same months measured the same way. A row whose levels are not all positive, whose returns
    are not all finite, or whose returns have no variance at all (a flat curve carries no
    information about independence) is dropped rather than correlated.
    """
    if len(curves) < 2:
        return np.zeros((0, 0)), 0
    common: set[str] = set(curves[0])
    for curve in curves[1:]:
        common &= set(curve)
    days = sorted(common)
    if len(days) < _MIN_POINTS:
        return np.zeros((0, 0)), len(days)
    rows: list[np.ndarray] = []
    for curve in curves:
        levels = np.asarray([curve[d] for d in days], dtype=float)
        if not np.all(levels > 0.0):
            continue
        rets = levels[1:] / levels[:-1] - 1.0
        if not np.all(np.isfinite(rets)):
            continue
        if float(np.std(rets)) <= 0.0:
            continue
        rows.append(rets)
    if len(rows) < 2:
        return np.zeros((0, 0)), len(days)
    return np.vstack(rows), len(days)


def correlation(conn: sqlite3.Connection) -> Correlation:
    """Measure the dev trials' co-movement from the curves already in ``trials.curve_json``.

    Reads only; spends no test-window look and runs no backtest. 1.0 with no measurement when
    fewer than two curves survive alignment -- one look is still one look.
    """
    curves = _dev_curves(conn)
    matrix, month_ends = _return_matrix(curves)
    count = int(matrix.shape[0])
    if count < 2:
        return Correlation(
            participation_ratio=1.0, mean_pairwise=None, curves_used=count, month_ends=month_ends
        )
    corr = np.corrcoef(matrix)
    corr = np.nan_to_num(np.asarray(corr, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
    eigenvalues = np.linalg.eigvalsh(corr)
    denominator = float(np.sum(eigenvalues**2))
    ratio = (float(np.sum(eigenvalues)) ** 2) / denominator if denominator > 0.0 else 1.0
    # The ratio is 1 for one shared factor and `count` for mutual independence; clamp, because
    # floating point on a near-singular matrix can step a hair outside either end.
    ratio = min(max(ratio, 1.0), float(count))
    upper = np.triu_indices(count, k=1)
    return Correlation(
        participation_ratio=ratio,
        mean_pairwise=float(np.mean(corr[upper])),
        curves_used=count,
        month_ends=month_ends,
    )


def participation_ratio(conn: sqlite3.Connection) -> float:
    """How many independent return streams the dev trials amount to: ``(Σλ)² / Σλ²``."""
    return correlation(conn).participation_ratio


def effective_n(conn: sqlite3.Connection, policy: str = DEFAULT_POLICY) -> NCount:
    """The multiple-testing N under ``policy``, with the evidence that produced it.

    ``NCount.n`` is the int to hand ``dev.deflated_sharpe``; the rest is why. Raises
    ``UnknownPolicy`` for a name outside ``POLICIES``.
    """
    # Deferred: ``store`` is the lab's own module and will import this one once the gate reads
    # the policy, so importing it at module scope would close a cycle.
    from seer_engine.lab import store

    name = check_policy(policy)
    evidence = correlation(conn)
    rows = store.dev_trial_count(conn)
    methods = dev_method_count(conn)
    ratio = evidence.participation_ratio
    if name == "all-trials":
        n = rows
    elif name == "methods":
        n = max(methods, math.ceil(ratio))
    else:
        # round() is half-to-even, which is deterministic and does not matter: a ratio landing
        # exactly on .5 is measurement noise either way.
        n = max(DSR_MIN_N, round(ratio))
    return NCount(
        n=int(n),
        policy=name,
        trial_rows=rows,
        distinct_methods=methods,
        participation_ratio=ratio,
        mean_pairwise_corr=evidence.mean_pairwise,
        curves_used=evidence.curves_used,
        month_ends=evidence.month_ends,
    )
