"""A lab signal: one stock-ranking idea as a pure score function (stage one of the lab).

**Why signals exist beside methods.** A method is a whole book: a ranking, a width, a weighting, a
switch, a cadence and Gotrade's fees, run through the full simulator and judged on one equity
curve. Random twins of a book, holding the same dates and weights, spread wider than a typical
signal's effect (plan index ``SERA_SIGNAL_PANEL_PLAN.md``, "Why"), so a book cannot say whether
its ranking ordered anything. A signal is only the ranking: given what was knowable at a
month-end close, one number per pool member, higher is better. ``lab.panel`` measures it across
every member and every month at once -- the question a book could not answer -- and only a
signal that clears there goes on to a book.

**One file per signal, pre-registered by commit.** ``seer_engine/lab/signals/sNNNN_<slug>.py``
exports ``SIGNAL = Signal(...)``, exactly as a method file exports ``METHOD``. ``discover`` finds
them the way ``method.discover`` finds methods, and the commit that adds the file is the
pre-registration (``lab panel`` refuses an uncommitted or dirty file). ``source_sha`` *is*
``method.source_sha``, re-exported so nobody has to wonder whether the two hash differently.

**What a score function may read.** ``score(history, market, pool, data_date)``:

- ``history``: symbol -> ``History``. A signal reads only bars dated on or before ``data_date``,
  and at most ``lookback`` of them. ``Signal.scores`` hands it exactly that (``visible``), so
  through the panel the rule holds by construction. The book runner's prepared path, by contrast,
  relies on a contract test and not on a cut (``strategies/allocator.py``). Called directly with
  full histories, a signal must keep the rule itself. ``tests/test_lab_signals.py`` checks that
  both calls agree, and that changing or deleting every bar after ``data_date`` changes nothing.
- ``market``: the same cut applied to ``market.history``. Its other readers (``dividends``,
  ``series``, ``shares``, ``fundamentals``) are point in time through the date the signal passes
  them, and that date must be ``data_date``. A signal that reads one declares it in
  ``market_fields`` (the ``runner.market_fields`` vocabulary) so a store without it is refused.
- ``pool``: the members that pass ``tree_rank.SCREEN`` on ``data_date``, the names the signal is
  asked to rank. A symbol the signal leaves out, or scores NaN, has no opinion.

Pure, like a method file: no clock, randomness, files, network or printing (the AST walk in
``tests/test_lab_signals.py``). A deterministic draw hashes the symbol and the date, as S0002 does.

``MAX_LOOKBACK`` is 473: labkit's smoke market has 473 sessions, the same ceiling every lab
allocator is held to (``control_draw.FIXTURE_BARS``). The smoke contract test could not prove a
signal that needs more.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from collections.abc import Callable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

import numpy as np

from seer_engine.lab.method import METHOD_ID, SOURCE_KINDS, source_sha
from seer_engine.strategies.base import History, as_day

if TYPE_CHECKING:
    from seer_engine.backtest.market import Market

__all__ = [
    "MARKET_FIELDS",
    "MAX_LOOKBACK",
    "MODULE_NAME",
    "SIGNAL_ID",
    "ScoreFn",
    "Signal",
    "discover",
    "signals_package",
    "source_sha",
    "visible",
]

SIGNAL_ID = re.compile(r"S\d{4}")
MODULE_NAME = re.compile(r"s(\d{4})_[a-z0-9_]+")
MAX_LOOKBACK = 473  # labkit's smoke fixture, the same ceiling control_draw.FIXTURE_BARS names
MARKET_FIELDS: tuple[str, ...] = ("fundamentals", "dividends", "announcements", "series", "shares")
"""The ``Market`` readers a signal may declare: ``runner.market_fields``' vocabulary, verbatim."""

ScoreFn = Callable[[Mapping[str, History], "Market", AbstractSet[str], date], Mapping[str, float]]


def visible(market: Market, data_date: date, lookback: int) -> tuple[dict[str, History], Market]:
    """What a signal may see on ``data_date``: every symbol's last ``lookback`` bars dated on or
    before it, and ``market`` carrying only those.

    A symbol with no bar by ``data_date`` is left out. The cut histories are views of the
    originals, so this costs one ``searchsorted`` and one ``History`` per symbol. The ``Market``
    is rebuilt with ``dataclasses.replace``, so ``Market.bar`` and ``Market.last_bar_date`` agree
    with the cut too.
    """
    day = as_day(data_date)
    cut: dict[str, History] = {}
    for symbol, h in market.history.items():
        end = int(np.searchsorted(h.dates, day, side="right"))
        if end == 0:
            continue
        start = max(0, end - lookback)
        if start == 0 and end == len(h):
            cut[symbol] = h
            continue
        cut[symbol] = History(
            symbol,
            h.dates[start:end],
            h.open[start:end],
            h.high[start:end],
            h.low[start:end],
            h.close[start:end],
            h.volume[start:end],
        )
    return cut, replace(market, history=cut)


@dataclass(frozen=True)
class Signal:
    """One registered stock-ranking idea (module docstring).

    ``name`` says in plain words what it ranks on; ``family`` names that, as a method's family
    does. ``hypothesis`` is why the ranking should order next month's returns; ``expected_failure``
    is the way it most likely does not. Both are written before the panel runs and are frozen
    with the commit. ``lookback`` is how many bars through ``data_date`` the score reads, at most
    ``MAX_LOOKBACK``. ``idea_id`` is the queued idea row (a method id with status ``idea``) this
    signal answers, if any. ``seen_keys`` follow ``Method.seen_keys``' ``kind:value`` form.
    """

    id: str
    name: str
    family: str
    source_kind: str
    source_ref: str
    hypothesis: str
    expected_failure: str
    lookback: int
    score: ScoreFn
    market_fields: tuple[str, ...] = ()
    idea_id: str | None = None
    seen_keys: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or SIGNAL_ID.fullmatch(self.id) is None:
            raise ValueError(f"signal id must look like S0001, got {self.id!r}")
        for name in ("name", "family", "hypothesis", "expected_failure"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{self.id}: {name} must be a non-empty str")
        if self.source_kind not in SOURCE_KINDS:
            raise ValueError(f"{self.id}: source_kind must be one of {SOURCE_KINDS}, got {self.source_kind!r}")
        if not isinstance(self.source_ref, str):
            raise TypeError(f"{self.id}: source_ref must be a str")
        if self.source_kind != "knowledge" and not self.source_ref.strip():
            raise ValueError(f"{self.id}: a {self.source_kind} signal needs a source_ref (URL, citation or parent)")
        if isinstance(self.lookback, bool) or not isinstance(self.lookback, int):
            raise TypeError(f"{self.id}: lookback must be an int, got {type(self.lookback).__name__}")
        if not 1 <= self.lookback <= MAX_LOOKBACK:
            raise ValueError(f"{self.id}: lookback must be 1..{MAX_LOOKBACK}, got {self.lookback}")
        if not callable(self.score):
            raise TypeError(f"{self.id}: score must be callable")
        if not isinstance(self.market_fields, tuple):
            raise TypeError(f"{self.id}: market_fields must be a tuple")
        for name in self.market_fields:
            if name not in MARKET_FIELDS:
                raise ValueError(f"{self.id}: market field {name!r} is not one of {MARKET_FIELDS}")
        if self.idea_id is not None and (
            not isinstance(self.idea_id, str) or METHOD_ID.fullmatch(self.idea_id) is None
        ):
            raise ValueError(f"{self.id}: idea_id must be the queued idea's id, like M0001, got {self.idea_id!r}")
        if not isinstance(self.seen_keys, tuple):
            raise TypeError(f"{self.id}: seen_keys must be a tuple")
        for key in self.seen_keys:
            if not isinstance(key, str) or ":" not in key:
                raise ValueError(f"{self.id}: seen key {key!r} must look like kind:value")

    def scores(self, market: Market, pool: AbstractSet[str], data_date: date) -> dict[str, float]:
        """This signal's scores on ``data_date``, through the cut it may see (``visible``).

        The panel and the signal book both call this, never ``score`` directly, so the look-ahead
        rule is enforced in one place. TypeError when ``score`` returns anything but a Mapping.
        """
        history, view = visible(market, data_date, self.lookback)
        raw = self.score(history, view, frozenset(pool), data_date)
        if not isinstance(raw, Mapping):
            raise TypeError(f"{self.id}: score must return a Mapping of symbol -> float, got {type(raw).__name__}")
        return dict(raw)


def signals_package() -> ModuleType:
    return importlib.import_module("seer_engine.lab.signals")


def discover(package: ModuleType | None = None) -> dict[str, tuple[Signal, Path]]:
    """Signal id -> (SIGNAL, file path) for every ``sNNNN_*.py`` module, sorted by id.

    ``package`` defaults to ``seer_engine.lab.signals``; a test passes a throwaway one. TypeError
    when a module has no ``SIGNAL = Signal(...)``; ValueError when a module's number disagrees with
    its ``SIGNAL.id`` or two modules claim one id.
    """
    pkg = signals_package() if package is None else package
    out: dict[str, tuple[Signal, Path]] = {}
    for info in pkgutil.iter_modules(pkg.__path__):
        m = MODULE_NAME.fullmatch(info.name)
        if m is None:
            continue
        module = importlib.import_module(f"{pkg.__name__}.{info.name}")
        signal = getattr(module, "SIGNAL", None)
        if not isinstance(signal, Signal):
            raise TypeError(f"{module.__name__} has no SIGNAL = Signal(...)")
        if signal.id != f"S{m.group(1)}":
            raise ValueError(f"{module.__name__}: file number S{m.group(1)} != SIGNAL.id {signal.id}")
        if signal.id in out:
            raise ValueError(f"two signal files claim {signal.id}")
        out[signal.id] = (signal, Path(module.__file__).resolve())
    return dict(sorted(out.items()))
