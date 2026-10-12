"""``lab gate M0030 [M0053 ...]``: what the shared SPY 200-day gate is worth, book by book.

Four of the five live books go to cash on **the same 28.3% of their decision days** -- 67 of 237
monthly decisions, bit-identical across them -- because they sit behind the same rule: SPY's close
against its own 200-day average, read on the same monthly dates (measured 2026-10-12,
``docs/backtests/2026-10-12-exposure-diagnostic.md``). That one shared rule produced the identical
**+34.8 point lead in 2008** in every one of them. It is not five discoveries; it is one trade,
shared five ways.

The lab already holds a recorded control that prices it on one book -- ``M0024-SAME-N20`` against
``M0024-SAME-N20-NOTREND`` -- and the control is damning: **+2.7 a year whole-window gated against
+1.0 ungated, but after 2009 the gated version trails by 5.4 while the ungated one leads by 1.5**
(same measurement, same date). Nearly all of the gate's whole-window value is one year, and it has
been a drag for six. One control on one book cannot settle that for a shared component, and the
gate is shared: changing it moves every book at once. So this command prices it **everywhere the
lab has a record of it**, on the dev window, as a report.

**Two arms, one allocator.** For each recorded dev variant this runs the *same* allocator on the
*same* window at the *same* recorded capital and funding, twice, differing only in its params:

==============  =======================================================================
arm             what it prices
==============  =======================================================================
``gated``       the candidate used unchanged: the reference, and the reproduction check
                against the number the lab recorded
``-NOGATE``     the same candidate with the shared SPY 200-day gate switched off and
                **nothing else moved**: the counterfactual the lab has never had for
                most of its books
==============  =======================================================================

**The gate is found generically, and refused when it cannot be.** ``gate_off`` is a recursive
``dataclasses.replace`` walk over the params tree with exactly two rewrites, both pinned to the
shared gate and to nothing else:

* a ``compare=True`` field named ``trend`` holding ``("SPY", 200)`` becomes ``None`` -- the form
  ``f_factor.trend_on`` reads, which is the single read every gated stock book shares;
* a ``TimingParams(signal="SPY", rule="sma", n=200)`` becomes ``rule="always"`` -- the blend-core
  form of the same gate (``m0030_spy_core_momentum_satellite``'s ``TIMED_SPY`` -> ``ALWAYS_SPY``).

Everything else **raises**. A ``trend`` that is not ``("SPY", 200)``, a ``TimingParams`` on another
signal, rule or length, a params value whose ``__post_init__`` rejects the gateless version -- each
is a ``GateOffRefused``, and the variant is listed as *not transformable* and **never run**. Six
recorded variants are exactly that case today (measured 2026-10-12): ``M0054``'s park arms, whose
``ParkParams`` says *"inner must have a trend switch; without one there is nothing to park"*, and
``M0101``'s four, whose ``SwitchParams`` says the same of its band switch. Guessing at those would
produce a number that looks like a gate-off counterfactual and is not one, which is worse than no
number.

**The transform checks itself against the lab's own record before it measures anything.**
``control_problems()`` runs ``gate_off`` over five recorded pairs (``M0007-N20`` ->
``M0007-N20-NOTREND`` and four more) plus ``M0030-C50T``'s core leg against ``M0030-C50A``'s, and
demands they match the recorded sibling exactly. ``lab gate`` refuses (exit 2) if any fails. The
transform is not trusted because it reads right; it is trusted because the lab already contains six
configurations it must reproduce and does.

``M0001-TV10`` / ``M0001-TV10-NOTREND`` is deliberately **not** in that set: measured 2026-10-12,
the recorded "no trend filter" sibling also moves the own-vol window from 63 to 126 sessions, so it
was never a clean gate control. It is listed in ``IMPURE_CONTROLS`` with that reason, and the probe
is the clean control M0001 never had.

**A variant with no gate is not asserted to be ungated.** When the walk finds no site, the probe
still runs the single recorded arm through its counting wrapper and reads ``Tally.empty_share`` --
the share of decision sessions on which the allocator returned no targets at all. A book that holds
nothing on a meaningful share of its decision days while declaring no SPY-200 gate has a brake this
transform does not reach (``M0012``'s weekly SPY-200 read lives in ``GateParams.smas``, not in a
``trend`` field; ``M0039``'s lives in a VIX term-structure signal). The report flags those loudly
instead of printing "ungated" beside them. That flag is a **measurement**, not a word list.

**A report, not a trial.** Nothing is written but, unless ``--no-journal``, one ``observation`` per
method: no ``trials``, ``trial_moments``, ``trial_funding`` or ``trial_provenance`` row, no status,
no pre-registration, and no method id is minted -- which matters here more than convenience,
because ``N`` for the deflated Sharpe counts distinct **methods** and every new one raises the luck
hurdle for the whole lab retroactively (``lab/npolicy.py``; N = 74 under the ``methods`` policy,
measured 2026-10-12). ``store.dev_trial_count`` and ``store.test_looks`` are read before and after
and printed, so the invariant is visible rather than merely asserted. ``dev.run_registry`` is
called with **no** ``window=`` keyword, so D9's dev default binds and nothing here can name the
test window.

**The arms are compared with each other, never with the recorded trial.** The gated arm's total
return is checked against the recorded one at ``real_costs.REPRO_TOL`` and printed as information,
the way ``lab costs`` prints it. A store or an engine that moved since a trial ran makes that check
fail without making the two arms any less comparable, and no conclusion here rests on a recorded
number beside a re-run one.
"""

from __future__ import annotations

import csv
import gc
import logging
import math
import sqlite3
import time
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, fields, is_dataclass, replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.dev import Candidate, DevRow
from seer_engine.backtest.metrics import fmt_num, fmt_pct, fmt_pf, fmt_signed_pct
from seer_engine.commands.backtest_dev import month_end_curve
from seer_engine.lab import hardgate, runner, store
from seer_engine.lab import method as method_module
from seer_engine.lab import walkforward as wf
from seer_engine.lab.exposure import ERA_LABELS, ERAS, WHOLE, Arm, StoreRun, Tally, load_dev_store
from seer_engine.lab.method import METHOD_ID, Method, discover
from seer_engine.lab.real_costs import REPRO_TOL
from seer_engine.sim.book import Target
from seer_engine.sim.contributions import ContributionSchedule
from seer_engine.sim.rules import is_bracket
from seer_engine.strategies.allocator import Allocator, prepare_for
from seer_engine.strategies.base import History
from seer_engine.strategies.f_index import TimingParams

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- the gate

#: The shared gate, in the one form every gated book in this lab expresses it:
#: ``f_factor.FactorParams.trend == ("SPY", 200)``, read by ``f_factor.trend_on``.
GATE_SYMBOL = "SPY"
GATE_N = 200
GATE: tuple[str, int] = (GATE_SYMBOL, GATE_N)
#: The one ``compare=True`` field name that carries it as a tuple.
TREND_FIELD = "trend"
#: The ``TimingParams.rule`` that *is* the gate, and the one that is the gate switched off.
GATE_RULE = "sma"
OFF_RULE = "always"

# --------------------------------------------------------------------------- the two arms

GATED = "gated"
UNGATED = "ungated"
MODES: tuple[str, ...] = (GATED, UNGATED)

#: Appended to the recorded candidate id for the gate-off arm. Candidate ids must match
#: ``dev._ID`` (``[A-Z0-9]+(-[A-Z0-9]+)*``), which this keeps -- and so do its numbered fallbacks.
ARM_SUFFIX = "-NOGATE"
ARM_LABEL: Mapping[str, str] = {
    GATED: "as recorded, with its SPY 200-day gate",
    UNGATED: "the same book with the shared SPY 200-day gate switched off",
}
ARM_HEAD: Mapping[str, str] = {GATED: "as recorded", UNGATED: "gate off"}

# --------------------------------------------------------------------------- classification

CARRIES = "carries"   # the shared gate was found and can be switched off
NO_GATE = "no-gate"   # no site found: one arm only, and the empty-day cross-check
REFUSED = "refused"   # a site was found but the gateless configuration is rejected

#: Below this share of decision sessions, "held nothing" is unfilled slots rather than a brake.
NOGATE_SUSPECT = 0.01


class GateOffRefused(ValueError):
    """The gate in this params tree cannot be switched off without guessing.

    Raised rather than returned, and never swallowed into a silent "no gate here": a variant whose
    gate this walk cannot identify is reported as not transformable and does not get a gate-off
    arm. The alternative -- running it unchanged and labelling the column "gate off" -- would put a
    number in the grid that is not the thing the column claims to measure.
    """


# --------------------------------------------------------------------------- the transform


def _is_trend_pair(value: object) -> bool:
    """``("SPY", 200)``'s shape: a 2-tuple of a str and a non-bool int."""
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
        and not isinstance(value[1], bool)
    )


def _walk(value: Any, path: str, sites: list[str]) -> Any:
    """``value`` with every shared-gate site switched off, appending each site to ``sites``.

    Returns the **same object** when nothing in its subtree changed, so a caller can test identity
    to know whether a rewrite happened anywhere.

    An ``Allocator`` is returned untouched: ``BlendPart.allocator`` holds one, allocators are
    module singletons the registry prepares by identity, and some are dataclasses that this walk
    would otherwise descend into and rebuild.
    """
    if isinstance(value, Allocator):
        return value
    if isinstance(value, TimingParams):
        if value.rule == OFF_RULE:
            return value  # already off: M0030's ALWAYS_SPY core
        if (value.signal, value.rule, value.n) == (GATE_SYMBOL, GATE_RULE, GATE_N):
            sites.append(f"{path}: timing rule {GATE_RULE!r} -> {OFF_RULE!r}")
            return replace(value, rule=OFF_RULE)
        raise GateOffRefused(
            f"{path} is TimingParams(signal={value.signal!r}, rule={value.rule!r}, n={value.n}), "
            f"which is a timing gate but not the shared {GATE_SYMBOL} {GATE_N}-day one; this "
            f"probe will not guess what switching it off means"
        )
    if is_dataclass(value) and not isinstance(value, type):
        changes: dict[str, Any] = {}
        for f in fields(value):
            if not f.compare:
                continue  # a compare=False field is not part of the configuration
            current = getattr(value, f.name)
            if f.name == TREND_FIELD:
                if current is None:
                    continue
                if not _is_trend_pair(current):
                    raise GateOffRefused(
                        f"{path}.{TREND_FIELD} is {current!r}, not a (symbol, n) pair; this probe "
                        f"only knows the {GATE!r} form of the gate"
                    )
                if tuple(current) != GATE:
                    raise GateOffRefused(
                        f"{path}.{TREND_FIELD} is {tuple(current)!r}, not the shared {GATE!r} "
                        f"gate; switching off a different gate is a different question"
                    )
                sites.append(f"{path}.{TREND_FIELD} -> None")
                changes[f.name] = None
                continue
            rewritten = _walk(current, f"{path}.{f.name}", sites)
            if rewritten is not current:
                changes[f.name] = rewritten
        if not changes:
            return value
        try:
            return replace(value, **changes)
        except (TypeError, ValueError) as e:
            raise GateOffRefused(
                f"{type(value).__name__} refuses the gate off: {e}. This method is built around "
                f"the gate being on, so there is no 'same book without it' to measure"
            ) from e
    if isinstance(value, tuple):
        out = tuple(_walk(v, f"{path}[{i}]", sites) for i, v in enumerate(value))
        if any(a is not b for a, b in zip(out, value)):
            return out
        return value
    return value


def gate_off(params: Any) -> tuple[Any, tuple[str, ...]]:
    """``params`` with the shared SPY 200-day gate switched off, and the sites that were switched.

    ``(params, ())`` when the walk reaches no site -- which means *this probe saw no shared gate*,
    not *this book has no brake*. ``GateOffRefused`` when a gate-shaped thing is found that is not
    the shared gate, or when the gateless configuration is rejected by the params type itself.

    The rewrite goes through ``dataclasses.replace``, so every ``__post_init__`` on the way back up
    runs: a method that validates "this book must carry a trend switch" refuses here rather than
    producing a mis-labelled column. Only ``compare=True`` fields are visited, which is the same
    set ``backtest/registry._canon`` renders into a ``config_digest``, so a site this walk can
    change is by construction a site that is part of the recorded configuration.
    """
    sites: list[str] = []
    return _walk(params, "params", sites), tuple(sites)


# --------------------------------------------------------------------------- the self-check

#: ``(gated id, the recorded sibling that is the same book with the gate off)``. Every pair is a
#: configuration the lab already holds, so the transform is checked against the record rather than
#: against this module's own opinion. All five matched when measured 2026-10-12.
CONTROLS: tuple[tuple[str, str], ...] = (
    ("M0002-MED-TV12", "M0002-MED-TV12-NOTREND"),
    ("M0007-N20", "M0007-N20-NOTREND"),
    ("M0008-C10", "M0008-C10-NOTREND"),
    ("M0024-SAME-N20", "M0024-SAME-N20-NOTREND"),
    ("M0064-P50", "M0064-P50-NOGATE"),
)

#: ``(gated id, sibling id, the index of the blend part that must match)``. ``M0030-C50A`` is the
#: recorded always-on core with the satellite still gated, so only its core leg is a control for
#: the ``TimingParams`` half of the transform. Matched when measured 2026-10-12.
CORE_CONTROLS: tuple[tuple[str, str, int], ...] = (("M0030-C50T", "M0030-C50A", 0),)

#: Recorded pairs that *look* like gate controls and are not, with why. Listed so a reader who
#: finds them does not conclude the transform is broken, and so nobody adds them to ``CONTROLS``.
#: Measured 2026-10-12: M0001-TV10 runs the own-vol window at 63 sessions and its "no trend filter"
#: sibling at 126, so the recorded pair moves two things at once and was never a clean control.
IMPURE_CONTROLS: Mapping[tuple[str, str], str] = {
    ("M0001-TV10", "M0001-TV10-NOTREND"):
        "the recorded sibling also moves the own-vol window from 63 to 126 sessions",
}


def _candidate_in(methods: Mapping[str, Any], cid: str) -> Candidate | None:
    method = methods.get(cid.split("-")[0])
    if method is None:
        return None
    return next((c for c in method[0].candidates if c.id == cid), None)


def control_problems() -> tuple[tuple[str, ...], int]:
    """``(problems, checked)``: where the transform disagrees with the lab's own recorded controls.

    A control whose method file no longer carries either side is **skipped**, not failed -- a
    method file is allowed to change and that is not this probe's business -- and ``checked`` says
    how many were actually compared, so a silently empty check cannot pass for a green one. The
    test suite pins ``checked`` at the full set against the committed files.

    It reads the committed method files through ``method_module.discover`` rather than this
    module's own ``discover`` name, deliberately: the controls are a self-check of the *transform*
    against what the lab already holds, and they must stay that check whatever set of methods a
    caller happens to be planning.
    """
    methods = method_module.discover()
    problems: list[str] = []
    checked = 0
    for gated_id, off_id in CONTROLS:
        a, b = _candidate_in(methods, gated_id), _candidate_in(methods, off_id)
        if a is None or b is None:
            continue
        checked += 1
        try:
            got, sites = gate_off(a.params)
        except GateOffRefused as e:
            problems.append(f"{gated_id}: the transform refuses its own control ({e})")
            continue
        if not sites:
            problems.append(f"{gated_id}: the transform found no gate, but {off_id} is recorded")
        elif got != b.params:
            problems.append(
                f"{gated_id}: the transform gives {got!r}, but the recorded {off_id} is {b.params!r}"
            )
    for gated_id, off_id, part in CORE_CONTROLS:
        a, b = _candidate_in(methods, gated_id), _candidate_in(methods, off_id)
        if a is None or b is None:
            continue
        checked += 1
        try:
            got, _sites = gate_off(a.params)
        except GateOffRefused as e:
            problems.append(f"{gated_id}: the transform refuses its own control ({e})")
            continue
        try:
            mine, theirs = got.parts[part], b.params.parts[part]
        except (AttributeError, IndexError):
            problems.append(f"{gated_id}: part {part} is not a blend leg on both sides any more")
            continue
        if mine != theirs:
            problems.append(
                f"{gated_id}: leg {part} transforms to {mine!r}, but {off_id}'s is {theirs!r}"
            )
    return tuple(problems), checked


# --------------------------------------------------------------------------- the wrapper


@dataclass(frozen=True)
class GateParams:
    """One arm's params: the allocator's own params, plus the arm's own counter.

    The wrapper changes nothing about the allocation; it exists only so both arms report the share
    of decision sessions on which the allocator returned no targets at all. That number is how the
    gated arm proves the gate fired, how the gate-off arm proves it stopped firing, and how a
    variant the transform calls ungated is cross-examined (see the module docstring).

    ``tally`` is ``compare=False`` so the params value stays a value; ``as_dict`` follows every
    other params class in the repo and is never read on the run path.
    """

    inner_params: Any
    tally: Tally = field(default_factory=Tally, compare=False, repr=False)

    def as_dict(self) -> dict[str, str]:
        inner = getattr(self.inner_params, "as_dict", None)
        rendered = dict(inner()) if callable(inner) else {"repr": repr(self.inner_params)}
        return {f"inner.{k}": v for k, v in rendered.items()}


def _params(params: object) -> GateParams:
    if not isinstance(params, GateParams):
        raise TypeError(f"params must be GateParams, got {type(params).__name__}")
    return params


class GateAllocator:
    """A pass-through over its inner allocator that counts its empty decisions.

    Every member delegates and nothing is re-weighted: ``targets`` returns exactly what the inner
    returned. That is deliberate and is itself checked -- the gated arm must reproduce the recorded
    trial's total return, which it cannot do if the wrapper perturbs anything.

    Preparation goes through ``strategies.allocator.prepare_for`` rather than ``LazyPrepared``,
    for the same reason ``exposure.ExposureAllocator`` does: ``LazyPrepared`` calls
    ``inner.prepare(history)`` and so silently loses ``prepare_market``, and twenty method files
    implement ``prepare_market`` to read the point-in-time fundamentals or dividend panel. A
    wrapper built the other way would quietly measure a bar-only version of each of them and report
    the difference as a finding about the gate.

    ``market_fields`` is forwarded so a future caller that consults it -- ``runner.market_fields``
    does -- sees the inner's declaration rather than the default.
    """

    __slots__ = ("id", "inner")

    def __init__(self, inner: Allocator) -> None:
        if not isinstance(inner, Allocator):
            raise TypeError(f"inner must be an Allocator, got {type(inner).__name__}")
        self.inner = inner
        self.id = f"NOGATE-{inner.id}"

    @property
    def market_fields(self) -> tuple[str, ...]:
        return tuple(getattr(self.inner, "market_fields", ("fundamentals",)))

    def lookback(self, params: Any) -> int:
        return self.inner.lookback(_params(params).inner_params)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return self.inner.symbols(_params(params).inner_params)

    def uses_members(self, params: Any) -> bool:
        return self.inner.uses_members(_params(params).inner_params)

    def holds(self, params: Any) -> tuple[str, ...]:
        return self.inner.holds(_params(params).inner_params)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return self.inner.prepare(history)

    def prepare_market(self, market: Any) -> Any:
        return prepare_for(self.inner, market)

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _params(params)
        out = self.inner.targets(history, members, data_date, held, p.inner_params)
        p.tally.saw(len(out), len(out))
        return out

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _params(params)
        out = self.inner.targets_prepared(prepared, members, data_date, held, p.inner_params)
        p.tally.saw(len(out), len(out))
        return out


#: One wrapper per inner allocator **object**, memoized by identity -- ``dev.run_registry`` refuses
#: two different allocator objects that share an ``allocator.id``, and every wrapper's id is
#: derived from its inner's. Module-level because the inner allocators are module singletons and
#: the memo must survive across the chunks of one command. ``lab/`` is not globbed by
#: ``tests/test_strategy_purity.py``, so a lab module may hold state, as ``exposure.py`` already
#: does.
_WRAPPERS: list[tuple[Any, GateAllocator]] = []


def wrapper_for(inner: Allocator) -> GateAllocator:
    """The one ``GateAllocator`` over ``inner``, created on first ask. Keyed by identity."""
    for obj, wrapped in _WRAPPERS:
        if obj is inner:
            return wrapped
    wrapped = GateAllocator(inner)
    _WRAPPERS.append((inner, wrapped))
    return wrapped


# --------------------------------------------------------------------------- building the arms


def arm_id_for(cid: str, suffix: str, taken: AbstractSet[str]) -> str:
    """``cid + suffix``, or the first free numbered form, so an arm never shadows a recorded id.

    ``M0064`` really does hold both ``M0064-P50`` and a recorded ``M0064-P50-NOGATE``, and
    ``dev.run_registry`` is given both the recorded variants and their arms in one call. Two
    candidates sharing an id in one registry call is a measurement that quietly answers about the
    wrong book, so the collision is resolved here and the chosen id is printed in the report.
    ``-NOGATE-2`` still matches ``dev._ID``.
    """
    base = f"{cid}{suffix}"
    if base not in taken:
        return base
    for k in range(2, 100):
        numbered = f"{base}-{k}"
        if numbered not in taken:
            return numbered
    raise store.LabError(f"cannot find a free arm id for {cid}; 98 variants of {base} are taken")


def arm_candidate(c: Candidate, mode: str, inner_params: Any, arm_id: str) -> Candidate:
    """One arm of ``c``: the same allocator wrapped, at ``inner_params``, under ``arm_id``.

    ``rules`` are kept **exactly** as recorded -- unlike ``lab exposure``, which strips the idle
    instrument, because there the parked money is the subject and here only the gate is. ``family``
    stays the method id so an arm can never be mistaken for another family's row.
    ``owner_inputs`` is recomputed, because the ungated arm of a blend stops reading the trend
    symbol and so may declare fewer ETFs.
    """
    arm = Candidate(
        id=arm_id,
        family=c.family,
        rules=c.rules,
        allocator=wrapper_for(c.allocator),
        params=GateParams(inner_params=inner_params),
        rationale=f"{ARM_LABEL[mode]} -- {c.rationale}",
        added=c.added,
        owner_inputs=(),
    )
    return replace(arm, owner_inputs=dev.candidate_owner_inputs(arm))


def arms_for(v: Variant) -> tuple[tuple[str, Candidate], ...]:
    """``(mode, candidate)`` for every arm of one variant, the recorded one first.

    Fresh ``GateParams`` -- and so a fresh ``Tally`` -- on every call: an arm is measured once.
    A variant whose gate the transform refuses, or in which it found none, contributes the gated
    arm only; its ``-NOGATE`` column is the reason it has none, printed in words.
    """
    out: list[tuple[str, Candidate]] = [
        (GATED, arm_candidate(v.candidate, GATED, v.candidate.params, v.gated_arm_id))
    ]
    if v.status == CARRIES:
        out.append((UNGATED, arm_candidate(v.candidate, UNGATED, v.off_params, v.ungated_arm_id)))
    return tuple(out)


# --------------------------------------------------------------------------- what to re-run


@dataclass(frozen=True)
class Variant:
    """One recorded dev variant, classified against the transform before any store loads."""

    candidate: Candidate
    trial_n: int
    trial: sqlite3.Row = field(compare=False, repr=False)
    capital: Decimal
    contributions: ContributionSchedule | None
    status: str                 # CARRIES | NO_GATE | REFUSED
    sites: tuple[str, ...]      # the gate sites the walk switched off (empty unless CARRIES)
    off_params: Any             # the gateless params (None unless CARRIES)
    why: str                    # why it is not transformable (empty unless REFUSED)
    gated_arm_id: str
    ungated_arm_id: str
    recorded_total_return: float | None
    recorded_mar: float | None
    recorded_eligible: bool

    @property
    def funded(self) -> bool:
        return self.contributions is not None


@dataclass(frozen=True)
class MethodPlan:
    method: Method
    variants: tuple[Variant, ...]
    missing: tuple[str, ...]  # recorded candidate ids that are no longer in the method file


def resolve_method(method_id: str) -> Method:
    """The committed ``METHOD`` for a lab method id (``store.LabError`` otherwise)."""
    if not isinstance(method_id, str) or METHOD_ID.fullmatch(method_id) is None:
        raise store.LabError(
            f"{method_id!r} is not a lab method id; `lab gate` takes methods like M0030"
        )
    methods = discover()
    if method_id not in methods:
        raise store.LabError(
            f"no method file for {method_id} in seer_engine/lab/methods/. `lab gate` re-runs the "
            f"committed method file, not a database row"
        )
    return methods[method_id][0]


def recorded_method_ids(conn: sqlite3.Connection) -> tuple[str, ...]:
    """Every method id with a recorded dev trial that still has a method file, in id order.

    ``--all``'s scope. A method whose file is gone is left out here rather than refused, because
    the whole point of ``--all`` is to sweep what the lab can still re-run.
    """
    files = discover()
    rows = conn.execute(
        "SELECT DISTINCT method_id FROM trials WHERE window = 'dev' ORDER BY method_id"
    ).fetchall()
    return tuple(str(r["method_id"]) for r in rows if str(r["method_id"]) in files)


def _f(x: object) -> float | None:
    return None if x is None else float(x)


def _classify(c: Candidate) -> tuple[str, tuple[str, ...], Any, str]:
    """``(status, sites, off_params, why)`` for one candidate, with no store and no bars.

    The allocator is asked to accept the gateless params through its own cheap members
    (``lookback`` / ``symbols`` / ``holds`` / ``uses_members``) before the variant is called
    transformable: a params type can validate while the allocator that reads it cannot, and the
    cost of finding that out at the start of a four-hundred-backtest run is a refusal, not a
    wasted hour.
    """
    try:
        off, sites = gate_off(c.params)
    except GateOffRefused as e:
        return REFUSED, (), None, str(e)
    if not sites:
        return NO_GATE, (), None, ""
    try:
        c.allocator.lookback(off)
        c.allocator.symbols(off)
        c.allocator.holds(off)
        c.allocator.uses_members(off)
    except Exception as e:  # noqa: BLE001 -- an allocator may raise anything about its own params
        return REFUSED, (), None, f"{c.allocator.id} refuses the gateless params: {e}"
    return CARRIES, sites, off, ""


def plan_method(conn: sqlite3.Connection, method_id: str) -> MethodPlan:
    """Every recorded dev variant of ``method_id`` that is still in its method file, classified.

    Resolves recorded capital, funding and the gate classification now, so a trial that cannot be
    re-run as the measurement it was is refused before a store is opened, and so the scope of the
    run is knowable (``--dry-run``) for free. A funded trial's schedule is checked against its
    recorded deposit count here too (``hardgate.trial_deposits`` with an empty curve buckets
    nothing but still raises on a moved schedule).
    """
    method = resolve_method(method_id)
    trials = [t for t in store.trials_of(conn, method.id) if t["window"] == "dev"]
    if not trials:
        raise store.LabError(
            f"{method.id} has no dev trial; `lab gate` re-runs what the lab recorded. Run it with "
            f"`lab run {method.id}` first"
        )
    by_id = {c.id: c for c in method.candidates}
    taken: set[str] = set(by_id) | {str(t["candidate_id"]) for t in trials}
    seen: set[str] = set()
    variants: list[Variant] = []
    missing: list[str] = []
    for t in trials:  # trials_of orders by n: the first recording of a variant wins
        cid = str(t["candidate_id"])
        if cid in seen:
            continue
        seen.add(cid)
        candidate = by_id.get(cid)
        if candidate is None:
            missing.append(cid)
            continue
        if is_bracket(candidate.rules):
            raise store.LabError(
                f"{cid} runs the bracket engine ({candidate.rules.id}), whose strategies are not "
                f"allocators and carry no params the trend gate lives in. `lab gate` measures book "
                f"methods; there is no SPY 200-day gate here to switch off"
            )
        n = int(t["n"])
        capital = runner.recorded_capital(conn, n)
        contributions = runner.recorded_contributions(conn, n)
        if contributions is not None:
            hardgate.trial_deposits(conn, t, [])
        status, sites, off, why = _classify(candidate)
        ungated_id = arm_id_for(cid, ARM_SUFFIX, taken)
        taken.add(ungated_id)
        variants.append(
            Variant(
                candidate=candidate,
                trial_n=n,
                trial=t,
                capital=capital,
                contributions=contributions,
                status=status,
                sites=sites,
                off_params=off,
                why=why,
                gated_arm_id=cid,
                ungated_arm_id=ungated_id,
                recorded_total_return=_f(t["total_return"]),
                recorded_mar=_f(t["mar"]),
                recorded_eligible=bool(t["eligible"]),
            )
        )
    if not variants:
        raise store.LabError(
            f"{method.id}: none of its recorded variants ({', '.join(missing)}) is in its method "
            f"file any more; there is nothing to re-run"
        )
    return MethodPlan(method, tuple(variants), tuple(missing))


def plan_methods(
    conn: sqlite3.Connection,
    ids: Sequence[str],
    only: str | None = None,
    *,
    gated_only: bool = False,
) -> tuple[MethodPlan, ...]:
    """``plan_method`` for each id, upper-cased and de-duplicated in the order given.

    ``only`` is a comma-separated list of recorded candidate ids; an id that matches no planned
    variant is a refusal rather than a silently empty run. ``gated_only`` drops the variants the
    transform found no gate in, which is the fast path for a targeted question -- at the cost of
    the empty-day cross-check that keeps "no gate found" honest, so the report says when it is on.
    """
    out: list[MethodPlan] = []
    done: set[str] = set()
    for raw in ids:
        mid = str(raw).strip().upper()
        if mid in done:
            continue
        done.add(mid)
        out.append(plan_method(conn, mid))
    if not out:
        raise store.LabError("name at least one method, e.g. `lab gate M0030`, or pass --all")
    if only is not None:
        wanted = {part.strip().upper() for part in str(only).split(",") if part.strip()}
        if not wanted:
            raise store.LabError("--only was given but names no candidate id")
        narrowed: list[MethodPlan] = []
        kept: set[str] = set()
        for plan in out:
            keep = tuple(v for v in plan.variants if v.candidate.id in wanted)
            kept.update(v.candidate.id for v in keep)
            if keep:
                narrowed.append(replace(plan, variants=keep))
        unknown = sorted(wanted - kept)
        if unknown:
            raise store.LabError(
                f"--only names {', '.join(unknown)}, which is not a recorded dev variant of "
                f"{', '.join(p.method.id for p in out)}"
            )
        out = narrowed
    if gated_only:
        trimmed = [
            replace(p, variants=tuple(v for v in p.variants if v.status == CARRIES)) for p in out
        ]
        out = [p for p in trimmed if p.variants]
        if not out:
            raise store.LabError(
                "--gated-only was given, and none of the named variants carries the shared "
                f"{GATE_SYMBOL} {GATE_N}-day gate; drop the flag to see why"
            )
    return tuple(out)


# --------------------------------------------------------------------------- one arm's numbers


def arm_of(
    mode: str,
    v: Variant,
    row: DevRow,
    curve: Sequence[tuple[date, float]],
    deposits: Mapping[date, float],
    bench: Sequence[tuple[date, float]],
) -> Arm:
    """One arm's ``exposure.Arm`` from its ``DevRow``, its monthly curve and the benchmark's.

    The shape and the per-era path are ``exposure.arm_of``'s, deliberately: the two commands must
    produce the same kind of number or their write-ups cannot be read beside each other. It is
    re-stated here rather than called because ``exposure.arm_of`` reads the tally off an
    ``ExposureParams`` by type, and ``exposure.py`` is owned by a landing this phase must not edit.

    **Whole window** comes from the ``DevRow``: the money-weighted return when the run was funded
    and the CAGR otherwise, against ``row.spy_tr``'s same measure -- which ``dev._run`` already
    makes deposit-matched. **Per era** goes through ``wf.measure``, which de-funds the whole curve
    with ``regime.defunded`` *before* it cuts it, against the recorded ``REF-SPY-HOLD`` curve
    sliced the same way; a second reconstruction would be a second chance to read the owner's
    deposits as edge.
    """
    m = row.stats.metrics
    yearly = m.mwr if m.mwr is not None else m.cagr
    spy_yearly = row.spy_tr.mwr if row.spy_tr.mwr is not None else row.spy_tr.cagr
    params = row.candidate.params
    tally = params.tally if isinstance(params, GateParams) else None
    mine: dict[str, float | None] = {WHOLE: yearly}
    theirs: dict[str, float | None] = {WHOLE: spy_yearly}
    for label, start, end in ERAS:
        got = wf.measure(curve, start, end, deposits)
        ref = wf.measure(bench, start, end)
        mine[label] = None if got is None else got.cagr
        theirs[label] = None if ref is None else ref.cagr
    lead = {
        label: (
            None
            if mine[label] is None or theirs[label] is None
            else mine[label] - theirs[label]
        )
        for label in ERA_LABELS
    }
    return Arm(
        mode=mode,
        candidate_id=row.candidate.id,
        start=row.start,
        end=row.end,
        funded=v.funded,
        exposure=float(row.stats.exposure),
        total_return=m.total_return,
        yearly=yearly,
        spy_yearly=spy_yearly,
        max_drawdown=m.max_drawdown,
        profit_factor=m.profit_factor,
        trades=int(m.trades),
        sharpe=row.stats.sharpe,
        empty_share=None if tally is None else tally.empty_share,
        mean_names=None if tally is None else tally.mean_names,
        era_yearly=mine,
        era_spy_yearly=theirs,
        era_lead=lead,
        curve=tuple(curve),
    )


def measure(
    conn: sqlite3.Connection,
    plans: Sequence[MethodPlan],
    data: research.ResearchData,
    bench: Sequence[tuple[date, float]],
) -> dict[tuple[str, str], dict[str, Arm]]:
    """Every arm of every variant of every plan: ``{(method id, candidate id): {mode: Arm}}``.

    One ``dev.run_registry`` call per (method, recorded capital, recorded schedule), chunked so no
    call exceeds ``dev.MAX_CANDIDATES`` arms -- a variant contributes at most two, so at most
    ``MAX_CANDIDATES // 2`` variants go into a call and a variant's arms are never split across
    calls. Never across methods: two method files may define different allocator objects under one
    allocator id, which ``run_registry`` refuses within a call.

    Called with **no** ``window=`` keyword, so D9's ``DEV_WINDOW`` default binds and no code path
    here can name the test window. Both arms of one variant run at that variant's recorded capital
    and funding, or they stop being a comparison.
    """
    if data.window != research.DEV_WINDOW:
        raise store.LabError(
            f"the loaded store declares the {data.window.name!r} window; `lab gate` measures the "
            f"dev window and nothing else"
        )
    out: dict[tuple[str, str], dict[str, Arm]] = {}
    per_chunk = max(1, dev.MAX_CANDIDATES // len(MODES))
    for plan in plans:
        mid = plan.method.id
        groups: dict[tuple[Decimal, ContributionSchedule | None], list[Variant]] = {}
        for v in plan.variants:
            groups.setdefault((v.capital, v.contributions), []).append(v)
        for (capital, contributions), group in groups.items():
            for i in range(0, len(group), per_chunk):
                chunk = group[i : i + per_chunk]
                registry: list[Candidate] = []
                owner: dict[str, tuple[str, Variant]] = {}
                for v in chunk:
                    for mode, cand in arms_for(v):
                        registry.append(cand)
                        owner[cand.id] = (mode, v)

                def on_result(
                    _i: int, result: Any, row: DevRow, *, _mid: str = mid,
                    _owner: Mapping[str, tuple[str, Variant]] = owner,
                ) -> None:
                    mode, v = _owner[row.candidate.id]
                    curve = month_end_curve(result.snapshots)
                    deposits = hardgate.trial_deposits(conn, v.trial, list(curve))
                    arm = arm_of(mode, v, row, curve, deposits, bench)
                    out.setdefault((_mid, v.candidate.id), {})[mode] = arm
                    log.info(
                        "%s [%s]: no pick on %s of its decision days, yearly %s vs SPY %s, max DD %s",
                        v.candidate.id, mode, fmt_pct(arm.empty_share),
                        fmt_signed_pct(arm.yearly), fmt_signed_pct(arm.spy_yearly),
                        fmt_pct(arm.max_drawdown),
                    )

                dev.run_registry(
                    data.market, data.dividends, data.spy_dividends, tuple(registry),
                    on_result=on_result, contributions=contributions, initial_idr=capital,
                )
    return out


def measure_store(
    conn: sqlite3.Connection,
    plans: Sequence[MethodPlan],
    store_dir: Path,
    bench: Sequence[tuple[date, float]],
) -> tuple[StoreRun, dict[tuple[str, str], dict[str, Arm]]]:
    """Load the dev store, measure every arm on it, free it, return the numbers.

    The store is about 2.5M bar rows; only small ``Arm`` records survive the call, so a sweep over
    many methods does not hold two copies of it.
    """
    t0 = time.perf_counter()
    data = load_dev_store(Path(store_dir))
    run = StoreRun(
        store_dir=str(store_dir),
        fingerprint=str(data.fingerprint),
        price_fingerprint=data.price_fingerprint,
        purpose=data.purpose,
    )
    log.info("dev store %s loaded (%.1fs)", run.fingerprint[:12], time.perf_counter() - t0)
    try:
        return run, measure(conn, plans, data, bench)
    finally:
        del data  # the only reference: the store is freed before the caller formats anything
        gc.collect()
        log.info("dev store released (%.1fs)", time.perf_counter() - t0)


# --------------------------------------------------------------------------- the comparison


@dataclass(frozen=True)
class VariantRow:
    method_id: str
    variant: Variant
    arms: Mapping[str, Arm]

    @property
    def gated(self) -> Arm:
        return self.arms[GATED]

    @property
    def ungated(self) -> Arm | None:
        return self.arms.get(UNGATED)

    @property
    def modes(self) -> tuple[str, ...]:
        return tuple(m for m in MODES if m in self.arms)

    @property
    def reproduced(self) -> bool | None:
        """Did the gated arm land on the recorded total return? None when either is missing."""
        recorded, measured = self.variant.recorded_total_return, self.gated.total_return
        if recorded is None or measured is None:
            return None
        return abs(measured - recorded) <= REPRO_TOL * max(1.0, abs(recorded))

    @property
    def suspect(self) -> bool:
        """``no gate found`` and yet it holds nothing on a real share of its decision days.

        The cross-examination of a "no gate" verdict, measured rather than guessed: the transform
        only knows two spellings of the gate, and a book braked some other way (``M0012``'s weekly
        SPY-200 read lives in a tuple of SMA lengths, ``M0039``'s in a VIX term structure) would
        otherwise be printed as ungated.
        """
        if self.variant.status != NO_GATE:
            return False
        share = self.gated.empty_share
        return share is not None and share > NOGATE_SUSPECT

    def gate_cost(self, label: str) -> float | None:
        """The gate's contribution in ``label``: the gated lead minus the ungated one, in points.

        Positive means the gate helped that era; negative means it was a drag. ``None`` when either
        arm is missing or either lead is undefined.
        """
        other = self.ungated
        if other is None:
            return None
        mine, theirs = self.gated.era_lead[label], other.era_lead[label]
        if mine is None or theirs is None:
            return None
        return mine - theirs


@dataclass(frozen=True)
class MethodReport:
    method_id: str
    method_name: str
    missing: tuple[str, ...]
    rows: tuple[VariantRow, ...]

    @property
    def headline(self) -> VariantRow:
        """The best recorded **eligible** variant that carries the gate, else the best by MAR.

        Ties break on the trial number, so the choice is reproducible rather than dict-ordered.
        A row that carries the gate is preferred over one that does not, because this report is
        about the gate and a headline with no gate-off column says nothing.
        """
        return sorted(
            self.rows,
            key=lambda r: (
                r.variant.status != CARRIES,
                not r.variant.recorded_eligible,
                r.variant.recorded_mar is None,
                -(r.variant.recorded_mar or 0.0),
                r.variant.trial_n,
            ),
        )[0]

    @property
    def reproduced(self) -> bool:
        return all(r.reproduced is not False for r in self.rows)

    @property
    def gated_rows(self) -> tuple[VariantRow, ...]:
        return tuple(r for r in self.rows if r.variant.status == CARRIES)


def compare(
    plans: Sequence[MethodPlan], arms: Mapping[tuple[str, str], Mapping[str, Arm]]
) -> tuple[MethodReport, ...]:
    out: list[MethodReport] = []
    for plan in plans:
        mid = plan.method.id
        rows: list[VariantRow] = []
        for v in plan.variants:
            measured = arms.get((mid, v.candidate.id))
            want = tuple(mode for mode, _c in arms_for(v))
            if measured is None or any(mode not in measured for mode in want):
                got = () if measured is None else tuple(sorted(measured))
                raise store.LabError(
                    f"{v.candidate.id}: expected arms {want}, measured {got}. The registry run did "
                    f"not produce a row for every arm, so there is nothing to compare"
                )
            rows.append(VariantRow(mid, v, dict(measured)))
        out.append(MethodReport(mid, plan.method.name, plan.missing, tuple(rows)))
    return tuple(out)


# --------------------------------------------------------------------------- the terminal report


def _finite(x: float | None) -> bool:
    return x is not None and math.isfinite(x)


def format_plan(plans: Sequence[MethodPlan], *, gated_only: bool = False) -> str:
    """What a run would measure, with no store opened and no bar read (``--dry-run``).

    This is also how the scope of a sweep is known before an hour is spent on it, and how the six
    variants the transform refuses are read without running anything.
    """
    carries = [v for p in plans for v in p.variants if v.status == CARRIES]
    nogate = [v for p in plans for v in p.variants if v.status == NO_GATE]
    refused = [v for p in plans for v in p.variants if v.status == REFUSED]
    arms = 2 * len(carries) + len(nogate)
    out = [
        f"lab gate: {len(plans)} method(s), "
        f"{sum(len(p.variants) for p in plans)} recorded dev variant(s), {arms} backtest(s)",
        f"the gate this prices: {GATE_SYMBOL} close against its own {GATE_N}-day average "
        f"(f_factor.trend_on), and the blend-core spelling of the same rule",
    ]
    if gated_only:
        out.append(
            "--gated-only: the variants with no gate site are dropped, and with them the "
            "empty-decision cross-check that keeps a 'no gate' verdict honest"
        )
    out.append("")
    out.append(f"carries the shared gate and can switch it off ({len(carries)}):")
    for v in carries:
        out.append(f"  {v.candidate.id:<30} -> {v.ungated_arm_id}   {'; '.join(v.sites)}")
    out.append("")
    out.append(f"no {GATE_SYMBOL} {GATE_N}-day gate this probe can see ({len(nogate)}):")
    for v in nogate:
        out.append(f"  {v.candidate.id}")
    out.append(
        "  these run the recorded arm only; the report flags any that still hold nothing on a "
        "real share of their decision days, because their brake is somewhere this probe does not "
        "reach"
    )
    out.append("")
    out.append(
        f"gate found, but the method refuses it off -- NOT MEASURED with the gate off "
        f"({len(refused)}):"
    )
    for v in refused:
        out.append(f"  {v.candidate.id}: {v.why}")
    if not refused:
        out.append("  (none)")
    missing = [cid for p in plans for cid in p.missing]
    if missing:
        out.append("")
        out.append(f"recorded, but no longer in a method file: {', '.join(missing)}")
    return "\n".join(out)


def _variant_block(row: VariantRow) -> list[str]:
    v = row.variant
    modes = row.modes
    measure_name = "money-weighted" if v.funded else "CAGR"
    out = [
        f"  {v.candidate.id}  (trial #{v.trial_n}, {'funded' if v.funded else 'lump sum'}, "
        f"capital {v.capital:,.0f} IDR, {row.gated.start}..{row.gated.end})",
    ]
    if v.status == CARRIES:
        out.append(f"    gate switched off at: {'; '.join(v.sites)}  [{v.ungated_arm_id}]")
    elif v.status == REFUSED:
        out.append(f"    NOT MEASURED with the gate off: {v.why}")
    else:
        out.append(
            f"    no {GATE_SYMBOL} {GATE_N}-day gate in its params: there is nothing for this "
            f"probe to switch off, and the recorded column is the only one"
        )
    if row.suspect:
        out.append(
            f"    *** it holds nothing on {fmt_pct(row.gated.empty_share)} of its decision days "
            f"while declaring no {GATE_SYMBOL} {GATE_N}-day gate: its brake is somewhere this "
            f"probe does not reach. Do not read this row as ungated ***"
        )
    grid: list[tuple[str, tuple[str, ...]]] = [
        ("decision days with no pick", tuple(fmt_pct(row.arms[m].empty_share) for m in modes)),
        ("names it asked for (mean)", tuple(fmt_num(row.arms[m].mean_names, 1) for m in modes)),
        ("money in the market", tuple(fmt_pct(row.arms[m].exposure) for m in modes)),
        ("total return", tuple(fmt_signed_pct(row.arms[m].total_return) for m in modes)),
        (f"yearly return ({measure_name})", tuple(fmt_signed_pct(row.arms[m].yearly) for m in modes)),
        (f"SPY TR yearly ({measure_name})", tuple(fmt_signed_pct(row.arms[m].spy_yearly) for m in modes)),
        ("max drawdown", tuple(fmt_pct(row.arms[m].max_drawdown) for m in modes)),
        ("profit factor", tuple(fmt_pf(row.arms[m].profit_factor) for m in modes)),
        ("trades", tuple(str(row.arms[m].trades) for m in modes)),
        ("Sharpe (annualized)", tuple(fmt_num(row.arms[m].sharpe) for m in modes)),
        ("lead over SPY a year, by era:", tuple("" for _m in modes)),
    ]
    for label in ERA_LABELS:
        grid.append(
            (f"  {label}", tuple(fmt_signed_pct(row.arms[m].era_lead[label]) for m in modes))
        )
    if row.ungated is not None:
        grid.append(("what the gate was worth, by era:", tuple("" for _m in modes)))
        for label in ERA_LABELS:
            grid.append((f"  {label}", (fmt_signed_pct(row.gate_cost(label)), "")))
    width = max(len(label) for label, _cells in grid)
    out.append(f"    {'':<{width}}" + "".join(f"  {ARM_HEAD[m]:>14}" for m in modes))
    for label, cells in grid:
        out.append(f"    {label:<{width}}" + "".join(f"  {c:>14}" for c in cells))
    head = (
        f"    recorded dev trial #{v.trial_n}: total return "
        f"{fmt_signed_pct(v.recorded_total_return)}"
    )
    rep = row.reproduced
    if rep is None:
        out.append(f"{head}; there is no number to check the recorded column against")
    elif rep:
        out.append(f"{head}; the recorded column reproduces it")
    else:
        out.append(
            f"{head}; the recorded column measured {fmt_signed_pct(row.gated.total_return)} -- the "
            f"store or the engine changed since it ran, so compare the two columns with each "
            f"other, not with the recorded trial"
        )
    return out


def format_report(rep: MethodReport, run: StoreRun) -> str:
    """One method's terminal grid. Ids, arm names and symbols are fine here."""
    out = [
        f"lab gate {rep.method_id} -- {rep.method_name}: {len(rep.rows)} recorded variant(s) "
        f"on dev store {run.fingerprint[:12]}"
        + (f" (purpose {run.purpose!r})" if run.purpose else ""),
        "report only: no trial row, no moments, no funding, no status change; no method file "
        "changed and no method id was minted, so the lab's N and the test-window looks do not move",
        f"columns: as recorded = the variant as the lab ran it; gate off = the same variant with "
        f"{GATE_SYMBOL}'s {GATE_N}-day trend gate removed and nothing else moved",
    ]
    if rep.missing:
        out.append(
            f"not measured (recorded, but no longer in the method file): {', '.join(rep.missing)}"
        )
    for row in rep.rows:
        out.append("")
        out += _variant_block(row)
    return "\n".join(out)


def summary_line(rep: MethodReport) -> str:
    h = rep.headline
    gated, off = h.gated, h.ungated
    if off is None:
        return (
            f"{rep.method_id} ({h.variant.candidate.id}): no {GATE_SYMBOL} {GATE_N}-day gate to "
            f"remove; it led SPY by {fmt_signed_pct(gated.lead)} a year, "
            f"{fmt_signed_pct(gated.era_lead['2009-2015'])} after 2009"
            + ("  *** but it holds nothing on "
               f"{fmt_pct(gated.empty_share)} of its decision days ***" if h.suspect else "")
        )
    bits = [
        f"{rep.method_id} ({h.variant.candidate.id}): lead over SPY a year "
        f"{fmt_signed_pct(gated.lead)} gated, {fmt_signed_pct(off.lead)} with the gate off",
        f"2009-2015 {fmt_signed_pct(gated.era_lead['2009-2015'])} -> "
        f"{fmt_signed_pct(off.era_lead['2009-2015'])}",
        f"2008 {fmt_signed_pct(gated.era_lead['2008'])} -> {fmt_signed_pct(off.era_lead['2008'])}",
        f"worst fall {fmt_pct(gated.max_drawdown)} -> {fmt_pct(off.max_drawdown)}",
        f"no pick on {fmt_pct(gated.empty_share)} of its decision days -> "
        f"{fmt_pct(off.empty_share)}",
    ]
    if not rep.reproduced:
        bits.append("WARNING: a recorded column did not reproduce its trial")
    return "; ".join(bits)


def lab_summary(reports: Sequence[MethodReport]) -> list[str]:
    """The roll-up the whole question turns on: where the gate paid, across everything measured.

    Counting variants rather than methods on purpose -- this is a statement about configurations,
    not a second N -- and saying so, because the lab has exactly one number called N and it is the
    luck gate's distinct-method count.
    """
    rows = [r for rep in reports for r in rep.gated_rows]
    out = [
        f"what the shared {GATE_SYMBOL} {GATE_N}-day gate was worth, over "
        f"{len(rows)} recorded variant(s) that carry it "
        f"(a count of configurations, not the luck gate's N):",
    ]
    for label in ERA_LABELS:
        costs = [r.gate_cost(label) for r in rows]
        judged = [c for c in costs if _finite(c)]
        if not judged:
            out.append(f"  {label:<12} not enough years to judge")
            continue
        helped = [c for c in judged if c is not None and c > 0]
        mean = sum(c for c in judged if c is not None) / len(judged)
        out.append(
            f"  {label:<12} mean {fmt_signed_pct(mean):>9} a year; it helped "
            f"{len(helped)} of {len(judged)}"
        )
    suspects = [r for rep in reports for r in rep.rows if r.suspect]
    if suspects:
        out.append("")
        out.append(
            f"{len(suspects)} variant(s) declare no {GATE_SYMBOL} {GATE_N}-day gate and still hold "
            f"nothing on more than {NOGATE_SUSPECT:.0%} of their decision days -- their brake is "
            f"somewhere this probe does not reach: "
            + ", ".join(r.variant.candidate.id for r in suspects)
        )
    refused = [
        r for rep in reports for r in rep.rows if r.variant.status == REFUSED
    ]
    if refused:
        out.append("")
        out.append(
            f"{len(refused)} variant(s) carry the gate and refuse to run without it: "
            + ", ".join(r.variant.candidate.id for r in refused)
        )
    return out


# --------------------------------------------------------------------------- the journal


def _verdict(rows: Sequence[VariantRow]) -> str:
    """Across the versions that have both columns, did removing the gate help or hurt, and when?"""
    pairs = [r for r in rows if r.ungated is not None]
    if not pairs:
        return (
            "None of this method's versions carries the market safety rule this measurement "
            "removes, so there was nothing here to price."
        )
    whole = [r.gate_cost(WHOLE) for r in pairs]
    recent = [r.gate_cost("2009-2015") for r in pairs]
    crash = [r.gate_cost("2008") for r in pairs]
    whole_j = [x for x in whole if _finite(x)]
    recent_j = [x for x in recent if _finite(x)]
    crash_j = [x for x in crash if _finite(x)]
    if not whole_j:
        return "There were not enough years to say what the safety rule was worth."
    mean_whole = sum(x for x in whole_j if x is not None) / len(whole_j)
    parts = [
        f"Over the whole history the safety rule was worth "
        f"{fmt_signed_pct(mean_whole)} a year on average across this method's versions."
    ]
    if crash_j:
        mean_crash = sum(x for x in crash_j if x is not None) / len(crash_j)
        parts.append(f"In the 2008 crash alone it was worth {fmt_signed_pct(mean_crash)}.")
    if recent_j:
        mean_recent = sum(x for x in recent_j if x is not None) / len(recent_j)
        verb = "earned" if mean_recent > 0 else "cost"
        parts.append(
            f"From 2009 to the end of the history it {verb} "
            f"{fmt_signed_pct(abs(mean_recent))} a year."
        )
    return " ".join(parts)


def insight_text(rep: MethodReport) -> tuple[str, str]:
    """``(title, body)`` in plain words for a non-trader: no ids, no code, no column names."""
    h = rep.headline
    gated, off = h.gated, h.ungated
    years = f"{gated.start.year}-{gated.end.year}"
    money = (
        "the same starting money and the same monthly top-ups"
        if h.variant.funded else "the same starting money"
    )
    intro = (
        f"Most of the methods this lab still holds stop buying whenever the market is below its "
        f"own long-term average, and they all read that same rule on the same dates. The lab took "
        f"the {len(rep.rows)} version(s) of this method it had already tested and ran each of them "
        f"again over the same {years} history, with {money}, once as it stands and once with that "
        f"one rule switched off and nothing else changed. The numbers below are for its best "
        f"version."
    )
    if off is None:
        bullets = [
            "- This version does not use that rule, so there was nothing to switch off.",
            f"- It earned {fmt_signed_pct(gated.yearly)} a year against the market's "
            f"{fmt_signed_pct(gated.spy_yearly)}.",
        ]
        if h.suspect:
            bullets.append(
                f"- It still held nothing at all on {fmt_pct(gated.empty_share)} of the days it "
                f"chose what to hold, so it has a brake of its own that this measurement did not "
                f"reach."
            )
    else:
        bullets = [
            f"- As it stands it earned {fmt_signed_pct(gated.yearly)} a year against the market's "
            f"{fmt_signed_pct(gated.spy_yearly)}; with the rule off, "
            f"{fmt_signed_pct(off.yearly)}.",
            f"- Its worst fall was {fmt_pct(gated.max_drawdown)} with the rule and "
            f"{fmt_pct(off.max_drawdown)} without it.",
            f"- With the rule it held nothing at all on {fmt_pct(gated.empty_share)} of the days "
            f"it chose what to hold; without it, {fmt_pct(off.empty_share)}.",
        ]
    eras = "\n".join(
        f"- {label}: {fmt_signed_pct(gated.era_lead[label])} a year against the market as it "
        f"stands"
        + (
            f", {fmt_signed_pct(off.era_lead[label])} with the rule off"
            if off is not None else ""
        )
        + "."
        for label in ERA_LABELS
    )
    body = "\n\n".join(
        (
            intro,
            "\n".join(bullets),
            "Period by period, ahead of or behind the market:",
            eras,
            _verdict(rep.rows),
            "This was a measurement, not a new try: nothing was recorded, the lab's count of "
            "tries did not move, and no verdict changed.",
        )
    )
    title = f"{rep.method_name}: what its market safety rule was worth"
    return title, body


def journal(conn: sqlite3.Connection, rep: MethodReport) -> int:
    """One ``observation`` on the method. The caller owns the transaction. Returns its id."""
    title, body = insight_text(rep)
    return store.add_insight(
        conn, kind="observation", title=title, body=body, method_id=rep.method_id
    )


# --------------------------------------------------------------------------- the CSV grid


def _slug(label: str) -> str:
    return label.replace(" ", "_").replace("-", "_")


CSV_HEADER: tuple[str, ...] = (
    "method_id", "candidate_id", "arm", "arm_candidate_id", "gate_status", "gate_sites",
    "gate_refusal", "suspect", "store_fingerprint", "price_fingerprint", "store_purpose",
    "trial_n", "funded", "capital_idr", "start", "end", "exposure", "mean_names", "empty_share",
    "total_return", "recorded_total_return", "reproduced", "yearly_return", "spy_yearly_return",
    "lead", "max_drawdown", "profit_factor", "trades", "sharpe",
    *(f"lead_{_slug(label)}" for label in ERA_LABELS),
    *(f"yearly_{_slug(label)}" for label in ERA_LABELS),
    *(f"spy_yearly_{_slug(label)}" for label in ERA_LABELS),
    *(f"gate_worth_{_slug(label)}" for label in ERA_LABELS),
)


def _cell(x: object) -> str:
    if x is None:
        return ""
    if isinstance(x, bool):
        return "1" if x else "0"
    if isinstance(x, float):
        return repr(x)  # full precision; inf stays "inf"
    if isinstance(x, date):
        return x.isoformat()
    return str(x)


def csv_rows(reports: Sequence[MethodReport], run: StoreRun) -> list[list[str]]:
    out: list[list[str]] = [list(CSV_HEADER)]
    for rep in reports:
        for row in rep.rows:
            v = row.variant
            for mode in row.modes:
                arm = row.arms[mode]
                out.append([
                    _cell(x) for x in (
                        rep.method_id, v.candidate.id, mode, arm.candidate_id, v.status,
                        "; ".join(v.sites), v.why, row.suspect, run.fingerprint,
                        run.price_fingerprint, run.purpose, v.trial_n, v.funded, v.capital,
                        arm.start, arm.end, arm.exposure, arm.mean_names, arm.empty_share,
                        arm.total_return, v.recorded_total_return,
                        row.reproduced if mode == GATED else None,
                        arm.yearly, arm.spy_yearly, arm.lead, arm.max_drawdown,
                        arm.profit_factor, arm.trades, arm.sharpe,
                        *(arm.era_lead[label] for label in ERA_LABELS),
                        *(arm.era_yearly[label] for label in ERA_LABELS),
                        *(arm.era_spy_yearly[label] for label in ERA_LABELS),
                        *(
                            (row.gate_cost(label) if mode == GATED else None)
                            for label in ERA_LABELS
                        ),
                    )
                ])
    return out


def write_csv(reports: Sequence[MethodReport], run: StoreRun, path: Path) -> Path:
    """Write the full variant x arm grid to ``path`` (parents created). Returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(csv_rows(reports, run))
    return path
