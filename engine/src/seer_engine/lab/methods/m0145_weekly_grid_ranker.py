"""M0145 — Rows or years? The yearly-horizon ranker retrained on a weekly sample grid.

Source: variation of M0137 (the rolling-window ranker), whose expanding arm EXP this method keeps
field for field as its control. M0137 measured a straight-line penalty for forgetting (216 labelled
month-ends earn 10.9% a year, 108 earn 10.0%, 48 earn 9.1%), but its arms cut ROWS and distinct
MARKET CONDITIONS together. **One thing moves here: the spacing of the training sample dates, which
adds rows and holds the years exactly fixed.**

THE LEVER. ``TreeRankPrepared.training_dates`` reads ``month_ends(train_start, anchor)`` and has no
grid field. ``tree_rank.py``, ``m0130``, ``m0131`` and ``m0137`` have all run and are frozen, so
nothing in them is edited. Instead ``GridTreeParams`` is a ``TreeRankParams`` with one more field,
``grid``, which enters ``model_key`` (a weekly model is never served from a monthly model's cache)
and ``as_dict`` (so the config digest moves), and ``GridPrepared`` is a ``TreeRankPrepared`` that
overrides only ``training_dates``. ``GridBook`` is M0137's rolling book with ``train_years`` left at
None (the expanding window) and a prepared value that honours the grid. The label, the seven
features, the annual refit anchors, the tree, the top 20, the SPY 200-day switch, the readiness
rule (still read on the month-end calendar, so every arm starts trading the same session) and the
tape at Gotrade's real fees are all M0137's.

THE GRIDS. ``monthly``: the last NYSE session of each month, which must reproduce M0137-EXP and is
the correctness check as much as the control. ``weekly``: the last session of each ISO week.
``fortnightly``: every second one of those, counted from ``train_start``. The label is still
252 sessions, so the label end of each sample is still checked against the anchor: a sample whose
label is not yet readable on the refit date never trains.

THE BOOK DOES NOT TRADE THE GRID. Month-end is the decision calendar; a weekly training grid
trains on dates the book never trades. That is legitimate (the model learns a cross-sectional
ordering, not a trading rule), and it is why the monthly arm is kept in the batch.

DV20 is M0131's gated dollar-volume book under this method's id, as M0137 did, so the
what-does-the-model-add comparison stays inside one trial boundary.

Pure: no clock, randomness, files, network or printing. Reads only data dated <= data_date.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date
from typing import Any

from seer_engine import dates
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0130_tree_ranker import ControlParams, TreeBookPrepared
from seer_engine.lab.methods.m0131_slow_target_ranker import YEAR, GatedDollarVolumeBook
from seer_engine.lab.methods.m0137_rolling_window_ranker import BASE, RollingParams, RollingTreeBook
from seer_engine.lab.tree_rank import TreeRankParams, TreeRankPrepared, month_ends
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND

ADDED = date(2026, 10, 25)

GRIDS = ("monthly", "fortnightly", "weekly")


# --------------------------------------------------------------------------- the sample grid


def week_ends(start: date, end: date) -> tuple[date, ...]:
    """The last NYSE session of every ISO week, from ``start`` to ``end`` inclusive, ascending.

    A week that ends past ``end`` is not closed yet, so its last session is only kept when it is
    on or before ``end``: a sample is never dated after the anchor it is trained at.
    """
    if end < start:
        return ()
    days = dates.sessions(start, end)
    out: list[date] = []
    for a, b in zip(days, days[1:]):
        if a.isocalendar()[:2] != b.isocalendar()[:2]:
            out.append(a)
    if days and (not out or out[-1] != days[-1]):
        last = days[-1]
        nxt = dates.next_session(last)
        if last.isocalendar()[:2] != nxt.isocalendar()[:2]:
            out.append(last)
    return tuple(out)


def grid_dates(grid: str, start: date, end: date) -> tuple[date, ...]:
    """Training sample dates on ``grid`` between ``start`` and ``end``."""
    if grid == "monthly":
        return month_ends(start, end)
    weeks = week_ends(start, end)
    if grid == "weekly":
        return weeks
    if grid == "fortnightly":
        return weeks[::2]
    raise ValueError(f"grid must be one of {GRIDS}, got {grid!r}")


@dataclass(frozen=True, slots=True)
class GridTreeParams(TreeRankParams):
    """M0131-B20's tree params plus the spacing of the training sample dates."""

    grid: str = "monthly"

    def __post_init__(self) -> None:
        TreeRankParams.__post_init__(self)
        if self.grid not in GRIDS:
            raise ValueError(f"grid must be one of {GRIDS}, got {self.grid!r}")

    def model_key(self) -> tuple[Any, ...]:
        return (*TreeRankParams.model_key(self), self.grid)

    def as_dict(self) -> dict[str, str]:
        out = dict(TreeRankParams.as_dict(self))
        out["grid"] = self.grid
        return out


class GridPrepared(TreeRankPrepared):
    """The ranker's prepared value with the training dates drawn from the params' grid."""

    def training_dates(self, params: TreeRankParams, anchor: date) -> tuple[date, ...]:
        grid = getattr(params, "grid", "monthly")
        return tuple(
            t for t in grid_dates(grid, params.train_start, anchor)
            if self.end(t, params.horizon) <= anchor
        )


class GridBook(RollingTreeBook):
    """M0137's gated tree book, expanding window, with a prepared value that honours the grid."""

    id = "M0145"

    def _grid(self, prepared: TreeRankPrepared) -> GridPrepared:
        return GridPrepared(**{f.name: getattr(prepared, f.name) for f in fields(prepared)})

    def prepare(self, history: Any) -> TreeBookPrepared:
        base = super().prepare(history)
        return TreeBookPrepared(self._grid(base.inner), base.history)

    def prepare_market(self, market: Any) -> TreeBookPrepared:
        base = super().prepare_market(market)
        return TreeBookPrepared(self._grid(base.inner), base.history)


GRID_BOOK = GridBook()


class M0145Control(GatedDollarVolumeBook):
    """M0131's gated dollar-volume control under this method's own allocator id, behaviour untouched."""

    id = "M0145-DV"


DV_BOOK = M0145Control()


# --------------------------------------------------------------------------- the method


def _v(suffix: str, allocator: Any, params: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0145-{suffix}", family="M0145", rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


def _grid(grid: str) -> RollingParams:
    return RollingParams(GridTreeParams(**{f.name: getattr(BASE, f.name) for f in fields(BASE)},
                                        grid=grid))


METHOD = Method(
    id="M0145",
    name="Rows or years? The same ranker retrained on a weekly sample grid instead of month-ends",
    family="stock-ml-ranker",
    source_kind="variation",
    source_ref="variation of M0137 (the rolling-window ranker); Sera batch 20261025-2024",
    parent_id="M0137",
    hypothesis=(
        "M0137 measured a clean monotone penalty for forgetting: 216 labelled month-ends earn "
        "10.9% a year, 108 earn 10.0%, 48 earn 9.1%, with profit factor, Sharpe, DSR and the "
        "2009-2015 lead all ordered the same way. But the three arms differ in TWO things at once: "
        "a ten-year window has half the ROWS and half the distinct MARKET CONDITIONS. If the "
        "binding constraint is raw examples the fix is cheap and local; if it is distinct "
        "conditions no resampling will ever help and the direction is closed. This variation "
        "separates them with the one lever that adds rows while holding years fixed: sample the "
        "training grid weekly instead of monthly. Same 1996-2015 history, same seven features, same "
        "252-session forward-return-rank label, same annual refit anchors, same expanding window, "
        "same flexible tree, same top 20 behind the same SPY 200-day switch, fractional shares at "
        "Gotrade's real fees on the owner's monthly deposits. Only the sample dates change, from "
        "the last NYSE session of each month to the last session of each week, which takes the "
        "2014 refit from about 216 dates to about 940, a factor of 4.3, with no new year, feature "
        "or day of data. THE HONEST PRIOR, written now: weekly samples overlap far more (a "
        "252-session label shares 98% of its window between neighbouring weeks against 92% between "
        "neighbouring months), so the EFFECTIVE sample barely grows while the nominal one "
        "quadruples. The most likely outcome is no change, and no change is the informative "
        "answer: the model is short of distinct conditions, not raw rows, which closes the "
        "resampling route and sends the lab to new information. A clear improvement would say the "
        "learner is example-starved and would make a denser grid standard for every ranker. COST, "
        "SAID HONESTLY: month-end is the decision calendar, so a weekly grid trains on dates the "
        "book never trades; that is legitimate (a cross-sectional ordering is learned, not a "
        "trading rule) and is why the monthly grid stays in the batch as the in-batch control. "
        "FOUR ARMS, fixed in advance: MON is the monthly grid and MUST reproduce M0137-EXP "
        "(otherwise the grid wrapper has a bug and the batch is void); FORT is every second weekly "
        "date, the middle rung of the ladder; WEEK is the weekly grid; DV20 is the gated "
        "dollar-volume control. WHAT COUNTS AS AN IMPROVEMENT, fixed in advance: a denser arm beats "
        "MON over 2009-2015 de-funded AND wins at least 3 of its 4 walk-forward folds. A stock "
        "ranker is not a published anomaly, so no publication-decay prior applies; the 2009-2015 "
        "era is the first filter. No variant is promoted in this run and the test window is not "
        "touched."
    ),
    expected_failure=(
        "Most likely nothing changes. First, the effective sample: with a 252-session label, "
        "neighbouring weekly samples share 98% of their label window, so the 4.3x rows are "
        "almost copies and the trees see about the same information. Second, extra near-duplicate "
        "rows make the fixed min_samples_leaf of 1000 and the 300-iteration budget relatively "
        "looser, so the fit may overfit the 1996-2002 era harder, not less: a denser grid can make "
        "the tree more confident about the same few regimes. Third, the book is still a gate "
        "result underneath (exposure about 68%, the switch in cash through 2001, 2002 and 2008), "
        "so a training change moves only the invested time. Fourth, M0137 lost every arm to SPY "
        "over 2009-2015 already, so even a real gain needs to be large to flip that sign. Fifth, "
        "month-end training dates match the decision calendar (month-end features, month-end "
        "turn-of-month effects); the weekly grid trains on mid-month dates and may blur a month-end "
        "calendar effect. The most informative failure is WEEK, FORT and MON agreeing within noise: "
        "the model is short of distinct conditions, and the resampling route is closed."
    ),
    candidates=(
        _v("MON", GRID_BOOK, _grid("monthly"),
           "Control: month-end grid, must reproduce M0137-EXP exactly"),
        _v("FORT", GRID_BOOK, _grid("fortnightly"),
           "Every second weekly date: the middle rung, about 2.2x the rows"),
        _v("WEEK", GRID_BOOK, _grid("weekly"),
           "The weekly grid: about 4.3x the rows, the same years"),
        _v("DV20", DV_BOOK, ControlParams(top_n=20, horizon=YEAR),
           "Control: the same gated 20-name book picked by trading volume, no model"),
    ),
    seen_keys=(
        "concept:weekly-training-grid-ranker",
        "concept:rows-versus-conditions-sample-density",
    ),
)
