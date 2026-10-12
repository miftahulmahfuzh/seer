"""M0119 — Where the monthly top-up goes: buy the laggard instead of topping everything up evenly.

Source: the owner's own funding plan (10,000,000 IDR to start and 5,000,000 IDR more on the 25th
of every month, ``sim.contributions``), read against the lab's finding that a funded book's CAGR
is a lie and the money-weighted return is the answer. The idea is mechanical rather than
predictive and has no published parent: no anomaly is being harvested, so there is no publication
year for it to fade from.

Idea: every method this lab has run differs in WHICH stocks it picks. None has ever varied WHERE
the owner's new money goes. The deposit is arriving anyway, so steering it costs no extra round
trip and almost no fee -- it is the one free lever in the whole pipeline. Buying the holdings
that have fallen furthest below their slot rebalances the book without ever selling, which avoids
the sell-side fee and holds the book at its target weights through a fall; spreading the deposit
pro-rata instead quietly lets the winners run. This method prices that choice on one fixed book,
with the picker held constant so that the deployment rule is the only thing that varies.

WHAT IS BEING MEASURED, and why this is a measurement and not a candidate. Like M0109, this
method exists to produce a number that transfers. The host book has no stock picking in it, and
on the dev window it trails SPY (M0109 measured the 50-name version at +7.0% a year on the
owner's deposits against SPY's +7.2%). No arm here is expected to be eligible and none is meant
to be. The finding is the SPREAD between the arms: if steering the deposit is worth something, it
is worth the same something bolted onto whatever book eventually wins, and if it is worth nothing
that is a lever the lab can stop thinking about.

THE HOST BOOK, in full, and it is M0109's base. On a rank session d, among the point-in-time
index members that are not ETFs, have at least ``DV_N`` bars through d, a close of at least
``min_price`` and a 20-session mean close x volume above ``min_dollar_volume``, take the ``top``
names with the HIGHEST dollar volume. Nothing is ranked on returns, volatility, fundamentals or
calendar; the only sort key is how much money changes hands. The screen, the exclusions and the
helper code are imported from M0109 rather than copied, so the two methods cannot drift apart.
What differs is the SIZING, which is this method's whole subject.

WHAT WAS MEASURED BEFORE THE VARIANTS WERE FIXED, and it changed the design. The book engine only
trims or adds when the gap between a holding and its target exceeds ``RESIZE_BAND`` x equity,
which is 1% of the account. With ``top`` equal slots, a holding must therefore drift ``top``% in
relative terms before any deployment rule can move a single dollar. Measured on the dev store,
re-picking this book monthly and asking how often a name's gap from its target clears that band:

    top=50   slot 2.00% of equity    0.1% of name-months trade    0.05% of equity moved a month
    top=30   slot 3.33%              0.8%                         0.28%
    top=20   slot 5.00%              4.2%                         1.12%
    top=12   slot 8.33%             16.2%                         2.82%

and with the tilts below applied, the share of name-months the band actually trades is 0.1-0.4%
at 50 names, 0.8-1.3% at 30, 3.1-4.1% at 20 and 11.8-13.6% at 12. The lab's own recorded trials
agree: M0109-EW-ALL and M0109-EW-ALL-W are the same 50-name book on the monthly and the weekly
resize clock and they made the IDENTICAL 1,338 trades, because at 50 names there is nothing for
the resize machinery to do. **At the book sizes this lab normally runs, every deployment rule in
this file is the same rule.** That is a finding about the simulator, it was established before
any variant was fixed, and it is why the host here holds 20 names and not 50: 20 is the largest
book on which the lever fires at all, an order of magnitude more often than at 30 or 50, while
staying closer to M0109's argued-neutral shape than the 12-name book would. The cost of that
choice is stated in ``expected_failure`` and is real: 20 of the most-traded names in March 2000
were the dot-coms, so this host falls further than SPY in 2000-2002, and no arm can clear the 20%
drawdown bar. A 20M IDR book split 20 ways is an $83 slot, comfortably above where Gotrade's fee
schedule was fitted.

THE DEPOSIT IS A YOUNG-ACCOUNT LEVER, and the twenty-year average will hide that. The owner's
schedule deposits 5,000,000 IDR a month into an account that starts at 10,000,000. Equity is at
least the deposits paid in, so the month's deposit is about a third of the account in month one,
7% at one year, 1.5% at five years and 0.4% at twenty. Per holding at 20 slots that is 1.7%,
0.36%, 0.08% and 0.02% of equity -- which is above the 1% band only for the first three months or
so. **After the first quarter the deposit alone can never top up an existing holding**; it can
only fund new entries when names rotate, or ride along with a gap that drift has already opened.
So the deposit-steering question is worth most in an account's first two or three years, which is
exactly where the owner is now and exactly what a twenty-year dev average understates. The
analysis splits the result by era with that in mind rather than reading the average.

THE DEPLOYMENT RULE, which is the only thing that varies. On a rank session d, let r be the
holding's own return over the last ``drift_n`` sessions, so ``ratio = close(d) / close(d - 21)``.
A book that was set to equal slots a month ago sits today at weights proportional to ``ratio``.
Target weights are then proportional to ``clip(ratio, 0.5, 2.0) ** tilt``, normalised to sum to
one, which makes ``tilt`` a signed dial through the three rules the idea reserved:

    tilt =  0   equal slots again        buys the laggards, sells the leaders   (rule b)
    tilt =  1   reproduces the drift     nothing to trade; the deposit spreads pro-rata  (rule a)
    tilt =  2   overshoots upward        the deposit buys last month's leaders  (rule c)
    tilt = -1   overshoots downward      the deposit buys last month's laggards harder than equal

The clip keeps one collapsing name from swallowing the book and is a fixed property of the
method, not a dial. A name with fewer than ``drift_n`` bars through d -- a fresh entry -- gets
ratio 1.0, which is right: a pick bought this month has no drift to correct.

One honest imprecision in ``tilt = 1``. It reproduces the drift exactly only if last month's
targets were equal slots, and under this rule they were not; the book therefore mean-reverts
weakly across two months instead of never trading at all. The measurement above shows the
difference is small (3.8% of name-months trade at tilt 1 against 4.1% at tilt 0), and the true
never-touch-anything floor is run separately as the HOLD arm below, which turns the resize
machinery off entirely so that the deposit can only ever fund a new entry.

THE ARMS. EQ (tilt 0) is the control and is what every other book in this lab already does.
PRORATA (tilt 1) is rule (a). LEAD (tilt 2) is rule (c), the mirror that proves the effect has a
sign rather than being an artefact of trading less. LAG (tilt -1) is rule (b) pushed past equal.
HOLD is EQ's weights with ``resize=False``, the floor: nothing is ever trimmed or topped up and
the deposit waits in cash for the next rotation. All five are fractional at Gotrade's real fees
on the owner's real monthly top-up, because a deposit rule measured at a flat 0.1% on whole
shares is measuring nothing.

Every piece reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0109_book_drawdown_brake import (
    BrakeParams,
    Row,
    book_rows,
    chosen,
    prepared_rows,
)
from seer_engine.sim.book import Target, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import DV_N, FactorPrepared, prepare_factor

ADDED = date(2026, 10, 12)

#: A holding's one-month drift is clipped into this band before the tilt is applied, so a single
#: collapsing or doubling name cannot swallow the book. A fixed property of the method, not a dial.
CLIP_LO = 0.5
CLIP_HI = 2.0


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class DeployParams:
    """The host book's screen and size, plus the one dial this method is about: ``tilt``."""

    top: int = 20  # names held; 20 is the largest book on which the 1% resize band ever trades
    tilt: int = 0  # 0 equal slots, 1 leave the drift, 2 buy the leaders, -1 buy the laggards
    drift_n: int = 21  # sessions the holding's own drift is read over (about one month)
    min_dollar_volume: float = 20_000_000.0  # 20-session mean close x volume > this (strict)
    min_price: float = 5.0  # close >= this

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 200:
            raise ValueError(f"top must be an int in 1..200, got {self.top!r}")
        if isinstance(self.tilt, bool) or not isinstance(self.tilt, int) or not -3 <= self.tilt <= 3:
            raise ValueError(f"tilt must be an int in -3..3, got {self.tilt!r}")
        if isinstance(self.drift_n, bool) or not isinstance(self.drift_n, int) or not 2 <= self.drift_n <= 252:
            raise ValueError(f"drift_n must be an int in 2..252, got {self.drift_n!r}")
        for name in ("min_dollar_volume", "min_price"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise TypeError(f"{name} must be a float, got {type(v).__name__}")
            if not np.isfinite(float(v)) or float(v) < 0.0:
                raise ValueError(f"{name} must be finite and >= 0, got {v!r}")
            object.__setattr__(self, name, float(v))

    def as_dict(self) -> dict[str, str]:
        return {
            "top": str(self.top),
            "tilt": str(self.tilt),
            "drift_n": str(self.drift_n),
            "min_dollar_volume": format(Decimal(repr(self.min_dollar_volume)).normalize(), "f"),
            "min_price": format(Decimal(repr(self.min_price)).normalize(), "f"),
        }

    def as_brake(self) -> BrakeParams:
        """The M0109 params value its screen helpers expect, carrying this method's screen."""
        return BrakeParams(
            top=self.top,
            min_dollar_volume=self.min_dollar_volume,
            min_price=self.min_price,
        )


def _check(params: object) -> DeployParams:
    if not isinstance(params, DeployParams):
        raise TypeError(f"params must be DeployParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the deployment rule


def drift_ratio(h: History | None, data_date: date, drift_n: int) -> float:
    """``close(d) / close(d - drift_n)`` for the holding, or 1.0 when it cannot be read.

    1.0 is the neutral answer and is what a name with too little history gets: a pick bought this
    month has no drift to correct, so every tilt leaves it at an equal slot.
    """
    if h is None:
        return 1.0
    i = h.index_of(data_date)
    if i is None or i < drift_n:
        return 1.0
    then = float(h.close[i - drift_n])
    now = float(h.close[i])
    if not (np.isfinite(then) and np.isfinite(now)) or then <= 0.0 or now <= 0.0:
        return 1.0
    return now / then


def deployment_weights(ratios: list[float], tilt: int) -> list[float]:
    """Target weights proportional to ``clip(ratio) ** tilt``, summing to one.

    ``tilt`` 0 is equal slots. A degenerate total (every weight zero, which the clip makes
    impossible but which is checked rather than assumed) falls back to equal slots.
    """
    if not ratios:
        return []
    raw = [min(CLIP_HI, max(CLIP_LO, r)) ** tilt for r in ratios]
    total = sum(raw)
    if not np.isfinite(total) or total <= 0.0:
        return [1.0 / len(ratios)] * len(ratios)
    return [x / total for x in raw]


def deploy_targets(rows: list[Row], history: Mapping[str, History], data_date: date,
                   p: DeployParams) -> tuple[Target, ...]:
    """The chosen names weighted by the deployment rule, in rank order (most traded first).

    Weights are quantized DOWN by ``to_weight``, so the total is never above one and the small
    remainder stays in cash -- the same rounding every other book in the lab takes.
    """
    picks = chosen(rows, p.as_brake())
    if not picks:
        return ()
    ratios = [drift_ratio(history.get(row.symbol), data_date, p.drift_n) for row in picks]
    weights = deployment_weights(ratios, p.tilt)
    out: list[Target] = []
    for row, weight in zip(picks, weights, strict=True):
        if weight <= 0.0:
            continue
        t = target_from_close(row.symbol, row.close, to_weight(weight))
        if t is not None:
            out.append(t)
    return tuple(out)


# --------------------------------------------------------------------------- the allocator


@dataclass
class DeployPrepared:
    """The history and the dollar-volume columns M0109's screen reads."""

    history: Mapping[str, History]
    factor: FactorPrepared


class DepositDeployment:
    """The most-traded index members, sized by where the month's new money is sent.

    Held symbols get no special treatment: every rank session is a fresh top set, so a held name
    that falls out of the most-traded list is exited whatever the deployment rule says. The rule
    decides only how the names that remain are weighted, and therefore what the deposit buys.
    """

    id = "M0119"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(DV_N, p.drift_n + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        as_day(data_date)
        return deploy_targets(book_rows(history, members, data_date, p.as_brake()), history, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> DeployPrepared:
        return DeployPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, DeployPrepared):
            raise TypeError(f"prepared must be DeployPrepared, got {type(prepared).__name__}")
        p = _check(params)
        as_day(data_date)
        rows = prepared_rows(prepared.factor, members, data_date, p.as_brake())
        return deploy_targets(rows, prepared.history, data_date, p)


DEPLOY = DepositDeployment()


# --------------------------------------------------------------------------- the variants

#: The floor arm's rule set: the promotable fractional real-fee monthly preset with the resize
#: machinery switched off, so an existing holding is never trimmed and never topped up and the
#: deposit can only ever fund a new entry. It runs on dev; `promote` would need a preset of its
#: own id, and a feature wish is journalled for one if this arm turns out to matter.
MONTHLY = MONTHLY_HOLD_FRAC_GOTRADE
MONTHLY_NO_RESIZE = replace(MONTHLY_HOLD_FRAC_GOTRADE, id="monthly-hold-frac-gotrade-noresize", resize=False)


def _v(suffix: str, params: DeployParams, rules, rationale: str) -> Candidate:
    return Candidate(id=f"M0119-{suffix}", family="M0119", rules=rules, allocator=DEPLOY,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0119",
    name="Where the monthly top-up goes: buy the laggard instead of topping everything up evenly",
    family="deposit-deployment",
    source_kind="knowledge",
    source_ref="",
    parent_id="M0109",
    hypothesis=(
        "Every method this lab has run differs in which stocks it picks. None has ever varied "
        "where the owner's new money goes, and that is the one free lever left: the monthly "
        "top-up is being deposited anyway, so steering it costs no extra round trip and almost no "
        "fee. Five deployment rules run on one fixed book with no stock picking in it -- the 20 "
        "most-traded index members, M0109's screen -- so that the deployment rule is the only "
        "thing that varies and the picker cannot be the thing that fails. A holding's weight is "
        "set to its one-month drift raised to a signed power: EQ puts every name back on an equal "
        "slot, which buys the laggards and sells the leaders; PRORATA reproduces the drift, so "
        "nothing is traded and the deposit spreads across the book in proportion to what is "
        "already there; LEAD overshoots upward so the deposit buys last month's winners; LAG "
        "overshoots downward so it buys last month's losers harder than equal; and HOLD turns the "
        "resize machinery off altogether, so nothing is ever trimmed or topped up and the deposit "
        "waits in cash for the next rotation. The reason this might matter is mechanical rather "
        "than predictive: buying the laggard rebalances without ever selling, so it avoids the "
        "sell-side fee and holds the book at its weights through a fall, where a pro-rata top-up "
        "quietly lets the winners run. Success is a measurement, not a candidate: the host book "
        "has no edge and M0109 already measured its 50-name version at 7.0% a year on the owner's "
        "deposits against SPY's 7.2%, so no arm here is expected to be eligible. What is wanted is "
        "the spread between the arms, stated in money-weighted return against deposit-matched SPY "
        "and never in CAGR, with the fees each rule paid reported separately from what it earned, "
        "and the worst fall of each reported too, since buying the laggard should bend the fall "
        "and buying the leader should worsen it. Two things were measured on the dev window before "
        "the variants were fixed, on the book's drift statistics alone and never on a return. "
        "First, the book engine only trades when a holding's gap from its target exceeds 1% of "
        "equity, so at 50 equal slots the gap clears that band in 0.1% of name-months and at 20 "
        "slots in 4.2%; the lab's own record agrees, since M0109's monthly and weekly 50-name "
        "controls made the identical 1,338 trades. At the sizes this lab normally runs, every "
        "rule in this file is the same rule -- which is itself the finding -- and the host "
        "therefore holds 20 names, the largest book on which the lever fires at all. Second, the "
        "month's deposit is about a third of the account in month one, 7% at one year and 0.4% at "
        "twenty, so per holding it clears that 1% band only for the first three months or so: "
        "after that the deposit can fund a new entry but can never top up an existing holding. "
        "Steering the deposit is therefore a young-account lever, worth most in the first two or "
        "three years, which is exactly where the owner is now and exactly what a twenty-year "
        "average understates, so the analysis reads the eras and not the average. Fractional "
        "shares at Gotrade's real fees on the owner's real monthly top-up throughout, because a "
        "deposit rule measured at a flat 0.1% on whole shares is measuring nothing."
    ),
    expected_failure=(
        "The most likely result is that the five arms land within a few tenths of a point a year "
        "of each other and the whole lever is worth less than the fees it costs to pull, because "
        "the 1% resize band swallows it: even at 20 names only about 4% of name-months ever trade, "
        "which is roughly three quarters of one holding a month. If that happens the honest answer "
        "is that deposit steering is not a lever at this lab's book sizes at all, and the next "
        "question is whether the band should scale with the slot rather than with the account. "
        "The second way this fails is the host. Twenty of the most-traded names in March 2000 were "
        "the dot-coms, and M0109 measured the 30-name version of this book falling 70% against "
        "SPY's 56%; a 20-name version will fall further still, so every arm breaks the 20% "
        "drawdown bar and the 2000-2002 crash may dominate the spread between the arms instead of "
        "the deployment rule doing it. The analysis therefore has to read the arms era by era and "
        "say plainly if one crash is carrying the answer. The third way is subtler and would "
        "invert the finding: buying the laggard every month inside a fixed universe is a "
        "short-term reversal bet wearing a bookkeeping costume, and the lab has found short-term "
        "reversal to be weak in big liquid names, so LAG may simply lose to LEAD for a reason that "
        "has nothing to do with deposits. If LEAD beats LAG, the mechanical story is dead and the "
        "right reading is that letting winners run inside a liquid large-cap book pays, which is "
        "the same lesson insight 91 drew about SPY's big-company drift. The fourth is that HOLD "
        "wins on fees by trading least and the lab mistakes cheapness for an edge; the fee column "
        "is reported separately for exactly that reason."
    ),
    candidates=(
        _v("EQ", DeployParams(top=20, tilt=0), MONTHLY,
           "Control: every holding back to an equal 1/20 slot, so the deposit and the trims buy the laggards"),
        _v("PRORATA", DeployParams(top=20, tilt=1), MONTHLY,
           "Rule (a): weights reproduce the one-month drift, so nothing is rebalanced and the deposit spreads pro-rata"),
        _v("LEAD", DeployParams(top=20, tilt=2), MONTHLY,
           "Rule (c): weights overshoot toward last month's winners, so the deposit buys the leaders"),
        _v("LAG", DeployParams(top=20, tilt=-1), MONTHLY,
           "Rule (b) past equal: weights overshoot toward last month's losers, so the deposit buys the laggards hardest"),
        _v("HOLD", DeployParams(top=20, tilt=0), MONTHLY_NO_RESIZE,
           "The floor: resize off, so no holding is ever trimmed or topped up and the deposit waits for the next rotation"),
    ),
    seen_keys=("concept:deposit-deployment-rule",),
)
