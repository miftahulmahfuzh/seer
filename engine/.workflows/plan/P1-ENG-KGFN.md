> Adopted from `/home/miftah/seer/.workflows/orchestration/sera-signal-panel/PLAN.md` phase 5. Source: `.workflows/plan/sera-signal-panel/phase-5.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 5: The panel gate in `lab run` and the one-chassis signal book

**Plan set:** `SERA_SIGNAL_PANEL_PLAN.md`
**Analysis:** `.workflows/analyze/20261113-200537-K7P2_code_analyzer.md`
**Satisfies:** R4 — stage two (the book lab) runs only signals that clear the panel, on one fixed chassis, and the refusal is enforced at `lab run` with exit 2
**Criteria:** R4.1, R4.2
**Depends on:** Phase 1, 2
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab`

---

## Goal

After this phase `lab run` (and `lab run --amend`) refuses, in `runner.preflight` and before any
research store is loaded or any backtest runs, a method that has an arm choosing among index
members unless the method either names a signal whose published panel verdict clears on the dev
store the run is about to load, with every non-control arm equal to that signal's standard book,
or declares a panel exemption. The standard book exists as `lab/signal_book.py`: twenty equal
slots from F4's pool, ranked by the signal, monthly at Gotrade's fees, one arm behind the SPY
200-day switch and one that never steps aside. A refusal records nothing and spends no N.

## Interface Contract

**Deletes:** nothing.

**Renames:** nothing.

**Creates:**
- `seer_engine.lab.method.SIGNAL_ID` (`re.compile(r"S\d{4}")`), `method.PANEL_EXEMPT_KINDS`
  (`("chassis", "control-study", "market")`) (`lab/method.py`)
- `Method.signal: str | None = None`, `Method.panel_exempt: str = ""` (`lab/method.py`), validated
  in `Method.__post_init__`
- `seer_engine.lab.signal_book` (new file): `WIDTH = 20`, `SWITCH = ("SPY", 200)`,
  `ID_PREFIX = "SB-"`, `GATED_SUFFIX = "N20"`, `NOGATE_SUFFIX = "N20-NOGATE"`,
  `RULES = MONTHLY_HOLD_FRAC_GOTRADE`, `BookParams` (frozen, `trend`, `as_dict`),
  `SignalPrepared`, `SignalBook`, `MarketSignalBook`,
  `book_allocator(signal) -> SignalBook` (allocator id `"SB-" + signal.id`),
  `standard_candidates(signal, method_id, added) -> tuple[Candidate, Candidate]`
- `seer_engine.lab.hardgate`: `picks_members(c) -> bool`, `dev_store_dir() -> Path`,
  `dev_store_fingerprint(store_dir=None) -> str`,
  `panel_refusal(conn, method, candidates, *, dev_fingerprint=None) -> str | None`,
  `panel_gate(conn, method, candidates, *, dev_fingerprint=None) -> None` (raises
  `store.LabError`), and the module docstring section **(D21)**
- `engine/tests/test_lab_panel_gate.py`, `engine/tests/test_lab_signal_book.py`

**Signature changes:**
- `runner.preflight(conn, method, path, *, require_commit=True, amend=False)` ->
  `runner.preflight(conn, method, path, *, require_commit=True, amend=False, dev_fingerprint: str | None = None)`.
  Every existing caller keeps working unchanged (keyword with a default).
- `runner.run_method` keeps its signature; it now passes `dev_fingerprint=data.fingerprint` to both
  of its `preflight` calls.

**Requires (from earlier phases):**
- Phase 1, `seer_engine.lab.signal`: `Signal` with fields `id, name, family, source_kind,
  source_ref, hypothesis, expected_failure, lookback, score, market_fields=()` (keyword
  construction outside the `signals` package must be allowed, because the tests build their own),
  `SIGNAL_ID` (pattern `S\d{4}`), `MAX_LOOKBACK = 473`, `discover() -> dict[str, tuple[Signal, Path]]`,
  `source_sha(path) -> str`, and the method `Signal.scores(market, pool, data_date) -> dict[str, float]`
  (reconciled: the name phase 1 actually exports). `Signal.scores` applies `signal.visible`: it
  hands `score` each symbol's last `lookback` bars dated on or before `data_date` and a `Market`
  rebuilt (`dataclasses.replace`) on those bars, so it accepts a `Market` whose membership is empty
  and whose `fx` is `()` (the book builds one from bars alone on the history-only path). A
  bar-only signal (`market_fields == ()`) reads nothing from the market but what it is handed.
  `panel.signal_scorer(signal)` returns this same bound method; the book calls `signal.scores`
  directly, as phase 1's handoff asks.
- Phase 1, `seer_engine.lab.panel`: `RULE_ID` (the gate's `has_panel` key).
- Phase 2, `seer_engine.lab.store`: `PanelSignalRow` and `PanelResultRow` built by keyword with
  exactly the table columns of the index's Shared contracts; `insert_panel_signal(conn, row)`,
  `insert_panel_results(conn, rows)`, `panel_signals(conn)` (rows with `id`, `source_sha`),
  `has_panel(conn, signal_id, rule_id, store_fingerprint) -> bool`. Every reader answers empty
  when the tables are absent.
- Phase 2, `seer_engine.lab.panel_verdict.published(conn, *, dev_fingerprint) -> dict[str, Verdict]`
  with `Verdict.clears: bool` and `Verdict.reasons: tuple[str, ...]` in plain words; a signal with
  no rows on that dev fingerprint is absent from the dict (or present with `clears=False`); the
  survivorship reading it pairs with the dev fingerprint is found without the caller naming a
  survivorship fingerprint.
- Phase 2 and 3 agree that `panel_results.store_fingerprint` for `store_role='dev'` is the dev
  store's `ResearchData.fingerprint`, which equals the `"fingerprint"` key of its `manifest.json`
  (`research.load_store` refuses a store whose files do not hash to it). This phase compares
  against exactly that value.

**Leaves alone (owned by others):** `engine/src/seer_engine/commands/lab.py` (phase 3, phase 4),
`engine/src/seer_engine/lab/store.py` and `lab/panel_verdict.py` (phase 2),
`lab/panel.py`, `lab/signal.py`, `lab/signals/*` (phase 1), `lab/panel_replay.py` (phase 4),
everything under `web/` (phases 2, 6), every `SKILL.md`, `CLAUDE.md`, `README.md` (phase 7),
every file under `engine/src/seer_engine/lab/methods/` (frozen records; no phase edits them).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/method.py` | modify | `SIGNAL_ID`, `PANEL_EXEMPT_KINDS`, `_exemption_ok` after `MAX_VARIANTS` (`:40`); `Method` gains `signal` and `panel_exempt` (`:117-205`, whole class replaced) |
| `engine/src/seer_engine/lab/signal_book.py` | create | the one chassis: `BookParams`, `SignalBook`, `MarketSignalBook`, `book_allocator`, `standard_candidates` |
| `engine/src/seer_engine/lab/hardgate.py` | modify | (D21) section appended to the module docstring before its closing quotes (`:935-936`); imports (`:938-952`); five functions after `pin_dev_store` (`:1406-1456`) |
| `engine/src/seer_engine/lab/runner.py` | modify | `preflight` (`:283-360`, whole function replaced) calls `hardgate.panel_gate` last; `run_method` passes `dev_fingerprint=data.fingerprint` at `:875` and `:903` |
| `.claude/skills/explore-and-experiment-new-method/method_template.py` | modify | whole file replaced: the signal form first, the own-allocator form with `panel_exempt` second |
| `engine/tests/test_lab_panel_gate.py` | create | the gate: binding, exemption, signal path, standard-book shape, amendment, CLI exit 2 |
| `engine/tests/test_lab_signal_book.py` | create | the chassis: allocator contract, ranking, switch, pool, the two standard arms |
| `engine/tests/test_lab_exposure.py` | modify | fixture `_method` (`:64-69`) declares `panel_exempt` |
| `engine/tests/test_lab_gate_probe.py` | modify | fixture `_method` (`:67-72`) declares `panel_exempt` |
| `engine/tests/test_lab_survivorship.py` | modify | fixture `_method` (`:48-53`) declares `panel_exempt` |
| `engine/tests/test_lab_yardstick_gate.py` | modify | fixture `_method` (`:89-94`) declares `panel_exempt` |
| `.claude/skills/verify-seer/features/lab-cli.md` | modify | the refusal in "Refused" (`:7`) and a Gotcha on how to drive it (after `:46`) |

## Implementation Steps

### Step 1: `Method.signal` and `Method.panel_exempt`
**File:** `engine/src/seer_engine/lab/method.py:37-40` and `:117-205`
**Change:** Add the two module constants and the exemption checker directly after
`MAX_VARIANTS = 6` (line 40), then replace the whole `Method` class (lines 117-205) with the class
below. The two new fields go last, with defaults, so every committed method file constructs
unchanged and its bytes (and therefore its `source_sha`) never move. `config_text` reads
`c.rules`, `c.allocator.id` and `c.params` only, never the `Method`, so no config digest moves
either (the same argument `test_adding_the_amendments_field_moves_no_config_digest` makes for
`amendments`). `SIGNAL_ID` is restated here rather than imported from `lab/signal.py` because
`signal.py` imports `method.SOURCE_KINDS`; a test pins the two patterns equal.

Insert after line 40 (`MAX_VARIANTS = 6`):

```python

#: A signal id, ``S0001``: the same pattern as ``signal.SIGNAL_ID``. Restated, not imported,
#: because ``lab/signal.py`` imports this module (``SOURCE_KINDS``) and an import back would be a
#: cycle; ``test_lab_panel_gate`` pins the two patterns equal.
SIGNAL_ID = re.compile(r"S\d{4}")

#: The three reasons a method whose arms choose among index members may skip the panel
#: (lab/hardgate.py, D21). ``panel_exempt`` must begin with one of them and a colon, then say why.
PANEL_EXEMPT_KINDS: tuple[str, ...] = ("chassis", "control-study", "market")


def _exemption_ok(text: str) -> bool:
    """True when ``text`` begins ``<kind>:`` for a kind in ``PANEL_EXEMPT_KINDS`` and gives a reason."""
    for kind in PANEL_EXEMPT_KINDS:
        prefix = f"{kind}:"
        if text.startswith(prefix) and text[len(prefix):].strip():
            return True
    return False
```

Replace lines 117-205 (the whole `Method` class) with:

```python
@dataclass(frozen=True)
class Method:
    """One lab idea and its pre-registered variants.

    ``hypothesis``: why it should beat SPY under design §1; ``expected_failure``: the way it
    most likely fails. Both are written before the run and frozen with the commit.
    Candidate ids are ``<id>-<suffix>`` and every candidate's family is the method id.

    ``amendments`` are the later, separately pre-registered batches of variants of this same idea
    (``Amendment``). They are a tuple in declaration order and the lab records them in that order,
    one ``method_amendments`` row each, so the record is always a prefix of the file. Every reader
    that asks "what variants does this method have" wants ``all_candidates()``, not ``candidates``:
    ``candidates`` is the original batch and nothing else.

    ``signal`` and ``panel_exempt`` are how a method answers the panel gate (lab/hardgate.py,
    D21), which ``lab run`` applies to any method with an arm that chooses among index members.
    ``signal`` names a registered signal (``S0001``, a file under ``lab/signals/``) whose
    published panel verdict must clear on the dev store the run loads; the method's non-control
    arms must then be that signal's standard book (``signal_book.standard_candidates``).
    ``panel_exempt`` says why the panel does not apply -- ``"chassis: ..."`` (a brake, a width, a
    cadence measured on a book), ``"control-study: ..."`` (how controls behave) or
    ``"market: ..."`` (a market-level rule that still holds members) -- followed by the reason.
    A method carries one or neither, never both. Both default to "not given", which is every
    method file committed before 2026-11-13, so adding them moved no file, no sha and no digest.
    Construction only checks their shape; whether they satisfy the gate is decided at ``lab run``,
    never at import or discovery.
    """

    id: str
    name: str
    family: str
    source_kind: str
    source_ref: str
    hypothesis: str
    expected_failure: str
    candidates: tuple[Candidate, ...]
    parent_id: str | None = None
    seen_keys: tuple[str, ...] = field(default=())
    amendments: tuple[Amendment, ...] = field(default=())
    signal: str | None = None
    panel_exempt: str = ""

    def all_candidates(self) -> tuple[Candidate, ...]:
        """Every variant this method has ever pre-registered: the originals, then each amendment's.

        In declaration order, which is the order the lab recorded them in, so a reader can map a
        recorded trial back onto the block that pre-registered it by position as well as by id.
        Identical to ``candidates`` for a method with no amendment, which is every method file
        committed before 2026-10-12.
        """
        out: list[Candidate] = list(self.candidates)
        for a in self.amendments:
            out.extend(a.candidates)
        return tuple(out)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or METHOD_ID.fullmatch(self.id) is None:
            raise ValueError(f"method id must look like M0001, got {self.id!r}")
        for name in ("name", "family", "hypothesis", "expected_failure"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{self.id}: {name} must be a non-empty str")
        if self.source_kind not in SOURCE_KINDS:
            raise ValueError(f"{self.id}: source_kind must be one of {SOURCE_KINDS}, got {self.source_kind!r}")
        if self.source_kind != "knowledge" and not self.source_ref.strip():
            raise ValueError(f"{self.id}: a {self.source_kind} method needs a source_ref (URL, citation or parent)")
        if self.source_kind == "variation" and not self.parent_id:
            raise ValueError(f"{self.id}: a variation needs parent_id")
        if not isinstance(self.candidates, tuple) or not 1 <= len(self.candidates) <= MAX_VARIANTS:
            raise ValueError(f"{self.id}: 1..{MAX_VARIANTS} candidates, got {len(self.candidates)}")
        if not isinstance(self.amendments, tuple):
            raise TypeError(f"{self.id}: amendments must be a tuple of Amendment values")
        for a in self.amendments:
            if not isinstance(a, Amendment):
                raise TypeError(f"{self.id}: amendments must be Amendment values, got {type(a).__name__}")
        # One pass over the originals and then each amendment, sharing the id and digest sets: a
        # candidate may not repeat an id or a configuration that any *other* batch of this same
        # method already used, or `has_trial` would refuse the run after the backtest was paid for.
        # The empty `where` for the originals keeps their messages byte-identical to the ones this
        # validation gave before amendments existed.
        ids: set[str] = set()
        digests: set[str] = set()
        batches: list[tuple[str, tuple[Candidate, ...]]] = [("", self.candidates)]
        for i, a in enumerate(self.amendments, start=1):
            batches.append((f" amendment {i} ({a.added.isoformat()})", a.candidates))
        for where, cands in batches:
            for c in cands:
                if not isinstance(c, Candidate):
                    raise TypeError(f"{self.id}{where}: candidates must be Candidate values")
                if not c.id.startswith(self.id + "-"):
                    raise ValueError(f"{self.id}{where}: candidate id {c.id} must start with {self.id}-")
                if c.family != self.id:
                    raise ValueError(f"{self.id}{where}: candidate {c.id} must have family {self.id}, got {c.family}")
                if c.id in ids:
                    raise ValueError(f"{self.id}{where}: candidate id {c.id} appears twice")
                digest = config_digest(c)
                if digest in digests:
                    raise ValueError(f"{self.id}{where}: candidate {c.id} repeats another variant's configuration")
                ids.add(c.id)
                digests.add(digest)
        for key in self.seen_keys:
            if not isinstance(key, str) or ":" not in key:
                raise ValueError(f"{self.id}: seen key {key!r} must look like kind:value")
        # The panel gate's two answers (D21). Shape only: this runs on import, for every committed
        # method file, and the gate itself runs at `lab run`.
        if self.signal is not None and (
            not isinstance(self.signal, str) or SIGNAL_ID.fullmatch(self.signal) is None
        ):
            raise ValueError(f"{self.id}: signal must look like S0001, got {self.signal!r}")
        if not isinstance(self.panel_exempt, str):
            raise TypeError(f"{self.id}: panel_exempt must be a str, got {type(self.panel_exempt).__name__}")
        if self.panel_exempt and not _exemption_ok(self.panel_exempt):
            kinds = ", ".join(f"'{k}:'" for k in PANEL_EXEMPT_KINDS)
            raise ValueError(
                f"{self.id}: panel_exempt must begin with one of {kinds} and then say why, "
                f"got {self.panel_exempt!r}"
            )
        if self.signal is not None and self.panel_exempt:
            raise ValueError(
                f"{self.id}: a method names a signal or declares a panel exemption, never both"
            )
```

**Impact:** No behaviour change on its own. Every committed method file still constructs
(both fields default). Nothing reads the fields until Step 3.

### Step 2: the one chassis, `lab/signal_book.py`
**File:** `engine/src/seer_engine/lab/signal_book.py` (new)
**Change:** The standard book. It reuses F4's screen (`tree_rank.SCREEN` through
`f_factor.factor_rows` / `FactorPrepared.rows_on`), F4's switch (`f_factor.trend_on`) and the
panel's own cut (`Signal.scores`, the method phase 1's `panel.signal_scorer` returns), so the book holds exactly the names the panel ranked
first. It satisfies `allocatorkit`'s P4 identity and no-look-ahead checks (Step 6 proves it) and
its lookback stays at or under `signal.MAX_LOOKBACK`.
**Code:**

```python
"""The one chassis a panelled signal is booked on (SERA_SIGNAL_PANEL_PLAN.md phase 5, R4).

Stage two of the lab books a stock-picking idea only after its signal has cleared the panel
(``lab panel``; ``panel_verdict.published``), and only on this chassis. One chassis, because the
panel has already measured the idea as a ranking across the whole pool: what the book stage adds
is a reading of that ranking as a portfolio a person could hold at Gotrade's fees. Every degree of
freedom left in the book -- a width, a cadence, a brake, a weighting -- would be a second idea the
panel never screened and another chance to fit the dev window. ``hardgate.panel_refusal`` (D21)
refuses a signal method whose non-control arms are anything but the two built here.

**The book.** On each monthly decision date ``d`` (``MONTHLY_HOLD_FRAC_GOTRADE``: fractional
shares at Gotrade's fees; the book engine asks the allocator on decision sessions only):

1. the pool is the members that pass ``tree_rank.SCREEN`` on ``d`` -- F4's screen with no trend
   switch, the pool the panel ranks (``f_factor.factor_rows`` / ``FactorPrepared.rows_on``);
2. every pool name is scored by the signal on bars cut at ``d`` (``Signal.scores``, the cut
   the panel measured with: ``panel.signal_scorer`` returns this same method); a missing or non-finite score has no opinion and the name is
   skipped;
3. the ``WIDTH`` highest scores are the targets, ties broken by symbol, each at
   ``equal_weight(WIDTH)``. A held name is kept only while it is still among them and is sold at
   the rebalance otherwise, so the book is the signal's top twenty and nothing else;
4. the gated arm (``<method>-N20``) holds nothing on a ``d`` when SPY closes at or below its
   200-day average (``f_factor.trend_on``, the switch every F4 book uses); the other arm
   (``<method>-N20-NOGATE``) never steps aside. Both are recorded because in most of the lab's
   books the switch, not the picking, did the work (the plan's Why), and a signal is worth booking
   only if its book is worth holding without the switch's help as well.

**Why the allocator is built per signal and not looked up.** ``book_allocator(signal)`` returns a
new object whose id is ``"SB-" + signal.id``. A config digest names an allocator by its id
(``method.config_text``), so a standard arm's digest is a function of the signal id, the rule set
and the switch setting alone: two methods that book one signal produce the same digests, and the
second is refused by ``runner.preflight``'s repeat check. One signal, one book. The signal's file
is frozen by its commit, and D21 compares its sha with the one its panel was measured on, so the
id is a sufficient name. ``test_lab_methods`` still holds a method file to one allocator object per
id: ``standard_candidates`` gives both arms the same object.

**A market-aware signal.** A signal that declares ``market_fields`` gets a ``MarketAware`` book
(``prepare_market``), so ``lab run``'s coverage and series checks read it exactly as they read any
other allocator (``runner.market_fields``). Its history-only path targets nothing, the convention
``test_lab_methods`` holds every market-aware allocator to: without the market there is nothing to
rank on. A bar-only signal's history-only path builds a ``Market`` from the bars it was given and
nothing else, so the scorer always receives a ``Market`` and the P4 identity holds on both paths.

Pure: no database, clock, files or randomness.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import Market, Membership
from seer_engine.lab.signal import Signal
from seer_engine.lab.tree_rank import SCREEN
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

#: The book's width: the signal's twenty highest-scored pool names.
WIDTH = 20

#: The market switch of the gated arm, F4's: SPY's close above its 200-session average.
SWITCH: tuple[str, int] = ("SPY", 200)

#: A signal book's allocator id is this prefix and the signal id: ``SB-S0001``.
ID_PREFIX = "SB-"

#: The two standard arms' candidate-id suffixes.
GATED_SUFFIX = "N20"
NOGATE_SUFFIX = "N20-NOGATE"

#: The chassis's rule set: monthly hold, fractional shares, Gotrade's real fees.
RULES = MONTHLY_HOLD_FRAC_GOTRADE

_NO_MEMBERS = Membership(intervals=())


@dataclass(frozen=True, slots=True)
class BookParams:
    """The chassis's one setting: the gated arm's switch, or none.

    Not a width, a cadence or a weighting: those are fixed (module docstring), and a field for
    them would be a dial a method could turn without the panel ever seeing it.
    """

    trend: tuple[str, int] | None = SWITCH

    def __post_init__(self) -> None:
        if self.trend is not None and self.trend != SWITCH:
            raise ValueError(
                f"the signal chassis has two settings, the SPY 200-day switch or none; "
                f"got trend={self.trend!r}"
            )

    def as_dict(self) -> dict[str, str]:
        """Every parameter as a plain string, in a fixed key order (report and pre-registration)."""
        trend = "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}"
        return {"width": str(WIDTH), "trend": trend}


def _check(params: object) -> BookParams:
    if not isinstance(params, BookParams):
        raise TypeError(f"params must be BookParams, got {type(params).__name__}")
    return params


def _screen(p: BookParams) -> FactorParams:
    """F4's screen (``tree_rank.SCREEN``) carrying this arm's switch: the pool and the switch."""
    return replace(SCREEN, trend=p.trend)


def _bars_market(history: Mapping[str, History]) -> Market:
    """A ``Market`` holding only ``history``: what a bar-only signal is handed off the full store."""
    return Market(history=history, membership=_NO_MEMBERS, fx=())


@dataclass(frozen=True, eq=False)
class SignalPrepared:
    """F4's prepared columns for the pool, and the market the signal reads.

    ``market`` is None only on a market-aware book's history-only path, where the book targets
    nothing (module docstring).
    """

    factor: FactorPrepared
    market: Market | None


class SignalBook:
    """A panelled signal's standard book behind the ``Allocator`` protocol (module docstring)."""

    def __init__(self, signal: Signal) -> None:
        if not isinstance(signal, Signal):
            raise TypeError(f"signal must be a Signal, got {type(signal).__name__}")
        self.signal = signal
        self.id = ID_PREFIX + signal.id
        self.market_fields: tuple[str, ...] = tuple(signal.market_fields)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(factor_lookback(_screen(p)), self.signal.lookback)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return () if p.trend is None else (p.trend[0],)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _check(params)
        screen = _screen(p)
        if not trend_on(history, data_date, screen):
            return ()
        rows = factor_rows(history, members, data_date, screen)
        return self._pick(rows, self._market_of(history), data_date)

    def prepare(self, history: Mapping[str, History]) -> SignalPrepared:
        return SignalPrepared(prepare_factor(history), self._market_of(history))

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        if not isinstance(prepared, SignalPrepared):
            raise TypeError(f"prepared must be SignalPrepared, got {type(prepared).__name__}")
        p = _check(params)
        screen = _screen(p)
        if not trend_on(prepared.factor.history, data_date, screen):
            return ()
        rows = prepared.factor.rows_on(members, data_date, screen)
        return self._pick(rows, prepared.market, data_date)

    def _market_of(self, history: Mapping[str, History]) -> Market | None:
        """The market a bar-only signal reads on the history-only path: the bars, nothing else."""
        return _bars_market(history)

    def _pick(
        self, rows: Sequence[FactorRow], market: Market | None, data_date: date
    ) -> tuple[Target, ...]:
        """The ``WIDTH`` highest-scored pool rows, ties by symbol, at ``equal_weight(WIDTH)``."""
        if market is None or not rows:
            return ()
        pool = frozenset(r.symbol for r in rows)
        scores = self.signal.scores(market, pool, data_date)  # applies signal.visible's cut
        ranked: list[tuple[float, str, float]] = []
        for r in rows:
            value = scores.get(r.symbol)
            if value is None:
                continue
            x = float(value)
            if math.isfinite(x):
                ranked.append((-x, r.symbol, r.close))
        ranked.sort()
        weight = equal_weight(WIDTH)
        out: list[Target] = []
        for _, symbol, close in ranked[:WIDTH]:
            target = target_from_close(symbol, close, weight)
            if target is not None:
                out.append(target)
        return tuple(out)


class MarketSignalBook(SignalBook):
    """The book of a signal that declares ``market_fields``: ``MarketAware``, history path empty."""

    def _market_of(self, history: Mapping[str, History]) -> Market | None:
        return None

    def prepare_market(self, market: Market) -> SignalPrepared:
        return SignalPrepared(prepare_factor(market.history), market)


def book_allocator(signal: Signal) -> SignalBook:
    """``signal``'s standard book, id ``"SB-" + signal.id``; market-aware when the signal is."""
    return MarketSignalBook(signal) if signal.market_fields else SignalBook(signal)


def standard_candidates(signal: Signal, method_id: str, added: date) -> tuple[Candidate, Candidate]:
    """The two arms a signal method books, in order: behind the switch, then never stepping aside.

    Both share one allocator object. Neither rationale names the signal (a signal's name can hold
    a phrase ``control_shape.role_of`` reads as a control, which would make an arm ineligible), and
    neither reads as a control: the gated arm opens ``The idea:`` and the other is a treatment.
    ``added`` reaches ``Candidate.added`` only, which no digest reads.
    """
    book = book_allocator(signal)
    gated = Candidate(
        id=f"{method_id}-{GATED_SUFFIX}",
        family=method_id,
        rules=RULES,
        allocator=book,
        params=BookParams(trend=SWITCH),
        rationale=(
            "The idea: the signal's twenty highest-scored members of F4's pool, equal weight, "
            "rebalanced monthly at Gotrade's fees, holding nothing while SPY is at or below its "
            "200-day average. The lab's one signal chassis."
        ),
        added=added,
        owner_inputs=(),
    )
    never = Candidate(
        id=f"{method_id}-{NOGATE_SUFFIX}",
        family=method_id,
        rules=RULES,
        allocator=book,
        params=BookParams(trend=None),
        rationale=(
            "The same twenty names with the market switch removed, never stepping aside, so the "
            "signal's book is read without the timing that did most of the work in most of the "
            "lab's books."
        ),
        added=added,
        owner_inputs=(),
    )
    return gated, never
```

**Impact:** New module, no caller yet. Importing it imports `tree_rank` (scikit-learn) and
`lab.signal`; nothing imports it at module scope except Step 3's lazy import and the tests.

### Step 3: the gate rule (D21) in `hardgate.py`
**File:** `engine/src/seer_engine/lab/hardgate.py:935-936`, `:938-952`, after `:1456`
**Change (a): the docstring.** Insert this block immediately before the module docstring's
closing `"""` at line 936 (after the (D20) paragraph that ends "It does not touch the §1
real-money bar."), with one blank line before it:

```text

**(D21) Does `lab run` book a stock-picking idea the panel never screened? -- No. From 2026-11-13
``runner.preflight`` REFUSES a method with an arm that chooses among index members unless it
names a signal that cleared the panel on the dev store about to be loaded and books only that
signal's standard chassis, or declares why the panel does not apply.**

Every clause above judges a book. A book is one concentrated portfolio through the full simulator,
and on that instrument the luck of which twenty names were drawn is as large as most signal
effects (SERA_SIGNAL_PANEL_PLAN.md, Why). The panel (``lab/panel.py``, ``lab panel``) asks the
prior question across the whole pool, stock by month, on both stores and three eras, with its own
false-discovery correction (``panel_verdict.published``), and writes no trial and moves no N. This
clause is the seam between the two stages: the book lab runs only signals that cleared.

**Who it binds.** A method binds when any arm about to run -- ``all_candidates()`` on a plain run,
the pending amendment's candidates on ``--amend`` -- chooses among index members: a bracket
``Strategy`` (it trades members), or an ``Allocator`` whose ``uses_members(params)`` is True.
That is ``backtest.dev._reads``'s own rule (``picks_members``). A method of market switches and
ETF rotations does not bind and never meets this clause.

**The three ways through, and nothing else.**

- ``panel_exempt`` set (``method.PANEL_EXEMPT_KINDS``: ``chassis:``, ``control-study:``,
  ``market:``, then the reason, checked at construction): passes. The reason is in the committed
  file, which is the pre-registration, so the exemption is argued in git like every other choice.
- ``signal`` set: the signal must be discoverable (``signal.discover()``); every arm about to run
  that is not a declared control (``control_shape.role_of``, the reader D17, D19 and the runner
  already use) must have the config digest of one of ``signal_book.standard_candidates``; the
  signal must have a panel on the dev store's fingerprint (``store.has_panel`` with
  ``panel.RULE_ID``) recorded from the file as it is on disk now (``panel_signals.source_sha`` ==
  ``signal.source_sha``); and its published verdict on that fingerprint must clear. The arm shape
  is checked first because it needs no store.
- neither: refused.

**Why ``lab run`` and not ``lab promote``.** (D15)'s argument runs the other way here. A run
spends a method id, and under ``store.DSR_POLICY = 'methods'`` every method id deflates every
other method's DSR. A screen that waits until promotion lets every unscreened idea raise the bar
for the ones that were screened. ``lab idea`` stays free: an idea row costs nothing and is how a
queued idea waits for its signal.

**Which store.** The fingerprint is ``ResearchData.fingerprint`` of the store the run loads.
``runner.run_method`` passes ``data.fingerprint``, and its first ``preflight`` comes before any
simulation, so that check is the authoritative one. ``commands/lab.py:_run`` calls ``preflight``
before the load and passes nothing, so the clause reads the manifest of the default store
(``dev_store_fingerprint``: ``$SEER_RESEARCH_STORE`` or ``research.STORE_DIR``) without loading
it. ``research.load_store`` refuses a store whose files do not hash to its manifest's fingerprint,
so the manifest's value is the one a successful load would carry.

**Fails closed.** No discoverable signal, no panel on this store, a signal file changed since its
panel, no published verdict, or an unreadable manifest: each refuses. There is no flag.

**What it does not reach.** Nothing that does not go through ``runner.preflight``: ``lab
remeasure`` (``remeasure.preflight``), ``lab costs``, ``lab reevaluate``, ``lab yardstick``, the
seeded ``H-*`` rows (``lab/seed.py``), and ``method.discover()``, which constructs every committed
file and checks only the two fields' shape. Measured on the committed lab at ``b0652d2`` (this
phase's planning, read-only): 387 of the 412 method files have an arm that chooses members; 411 of
the 412 have dev trials, so a plain ``lab run`` already refuses them as having run; the one without
(M0111) is ``rejected`` and refused by the same status check before this clause. No committed file
became unrunnable. An ``--amend`` of one of the 387 declares ``panel_exempt`` in the commit that
adds the amendment.

**Where it sits.** Last in ``preflight``, after the repeat check, so every older refusal keeps its
message and its order, and before ``research.load_store``, so a refusal loads nothing, records
nothing and spends no method id.
```

**Change (b): imports.** Replace lines 938-952 (from `from __future__ import annotations` through
`from seer_engine.lab import walkforward as wf`) with:

```python
from __future__ import annotations

import json
import math
import os
import re
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from seer_engine.backtest import regime, tuning
from seer_engine.lab import store, survivorship_record
from seer_engine.lab import walkforward as wf
from seer_engine.sim.rules import is_bracket

if TYPE_CHECKING:  # typing only: the panel modules are imported inside the functions that use them
    from seer_engine.backtest.dev import Candidate
    from seer_engine.lab.method import Method
```

**Change (c): the functions.** Insert after `pin_dev_store` (it ends at line 1456, before
`def fold_record(` at line 1459), keeping two blank lines on each side:

```python
def picks_members(c: Candidate) -> bool:
    """Whether ``c`` chooses among index members: the rule ``backtest.dev._reads`` applies.

    A bracket ``Strategy`` trades members and nothing else; an ``Allocator`` says so through
    ``uses_members(params)``. Restated rather than imported because ``_reads`` also validates the
    lookback and symbols and raises on a bad candidate, which is not this question.
    """
    if is_bracket(c.rules):
        return True
    return bool(c.allocator.uses_members(c.params))


def dev_store_dir() -> Path:
    """The store ``lab run`` loads when ``--store`` is not given: ``commands/lab.py``'s default."""
    from seer_engine import research

    return Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR)


def dev_store_fingerprint(store_dir: Path | None = None) -> str:
    """The fingerprint of the dev store at ``store_dir`` (default ``dev_store_dir()``), unloaded.

    Read from ``manifest.json`` alone: ``research.load_store`` refuses a store whose files do not
    hash to its manifest's fingerprint, so this is the ``ResearchData.fingerprint`` a successful
    load would carry, without the full load. ValueError when the manifest is missing, unreadable
    or names no fingerprint.
    """
    from seer_engine import research

    where = dev_store_dir() if store_dir is None else Path(store_dir)
    path, manifest = research._manifest_json(where)
    fingerprint = manifest.get("fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint:
        raise ValueError(f"{path}: names no fingerprint")
    return fingerprint


def panel_refusal(
    conn: sqlite3.Connection,
    method: Method,
    candidates: Sequence[Candidate],
    *,
    dev_fingerprint: str | None = None,
) -> str | None:
    """Why (D21) will not let ``method`` run ``candidates``; None when it will.

    ``candidates`` are the arms about to run (``runner.preflight`` passes ``all_candidates()``,
    or the pending amendment's). ``dev_fingerprint`` is the dev store's fingerprint; None reads it
    from the default store's manifest, and only when the method names a signal and its arms have
    the standard shape. The sentence, without the "Nothing ran" tail ``panel_gate`` adds. Reads
    the panel tables and the signal files; writes nothing.
    """
    pickers = [c.id for c in candidates if picks_members(c)]
    if not pickers or method.panel_exempt:
        return None
    if method.signal is None:
        return (
            f"{method.id} picks index members ({describe(pickers)}) and names neither a panelled "
            f"signal (`signal=`) nor a panel exemption (`panel_exempt=`). A stock-picking idea is "
            f"screened on the stock-by-month panel before it is ever booked: write it as a signal "
            f"file (`lab next-signal-id`, then seer_engine/lab/signals/sNNNN_<slug>.py, "
            f"committed), run `lab panel SNNNN`, and once it clears name it here with "
            f"`signal=\"SNNNN\"` and build the arms with `signal_book.standard_candidates`. A "
            f"method that picks members to measure a chassis, a control or the market itself "
            f"declares `panel_exempt=\"chassis: <why>\"`, `\"control-study: <why>\"` or "
            f"`\"market: <why>\"` instead"
        )
    from seer_engine.lab import control_shape, panel, panel_verdict, signal_book
    from seer_engine.lab import signal as signals
    from seer_engine.lab.method import config_digest

    found = signals.discover().get(method.signal)
    if found is None:
        return (
            f"{method.id} names signal {method.signal}, and no seer_engine/lab/signals/"
            f"s{method.signal[1:]}_*.py exports it. Write and commit the signal file, run "
            f"`lab panel {method.signal}`, and run this method once the signal clears"
        )
    sig, path = found
    standard = {
        config_digest(c) for c in signal_book.standard_candidates(sig, method.id, candidates[0].added)
    }
    hand = [
        c.id
        for c in candidates
        if control_shape.role_of(c) != control_shape.ROLE_CONTROL and config_digest(c) not in standard
    ]
    if hand:
        return (
            f"{method.id} names signal {sig.id}, so its arms are that signal's standard book -- "
            f"`signal_book.standard_candidates`: the twenty highest-scored members of F4's pool, "
            f"equal weight, monthly at Gotrade's fees, one arm behind the SPY 200-day switch and "
            f"one never stepping aside -- plus any declared controls. {describe(hand)} is neither: "
            f"a hand-built treatment beside a panelled signal is a second idea the panel never "
            f"screened. Build the arms with `standard_candidates`, and open a foil's rationale "
            f"with \"Control:\""
        )
    if dev_fingerprint is None:
        try:
            dev_fingerprint = dev_store_fingerprint()
        except ValueError as e:
            return (
                f"{method.id} names signal {sig.id}, and the fingerprint of the dev store this run "
                f"would load cannot be read from its manifest ({e}). Point SEER_RESEARCH_STORE at "
                f"the store `lab run` loads"
            )
    recorded = next((r for r in store.panel_signals(conn) if str(r["id"]) == sig.id), None)
    if recorded is None or not store.has_panel(conn, sig.id, panel.RULE_ID, dev_fingerprint):
        return (
            f"{method.id} names signal {sig.id}, which has no panel on the dev store this run "
            f"would load (fingerprint {dev_fingerprint[:12]}). Run `lab panel {sig.id}` -- it "
            f"measures both stores, writes no trial and moves no N -- and run this method once "
            f"the signal clears"
        )
    on_disk = signals.source_sha(path)
    if str(recorded["source_sha"]) != on_disk:
        return (
            f"{method.id} names signal {sig.id}, whose file no longer hashes to the sha its panel "
            f"was measured on ({str(recorded['source_sha'])[:12]} recorded, {on_disk[:12]} on "
            f"disk). The panel judged the committed file, not this one: restore it from git. A "
            f"changed idea is a new signal id"
        )
    verdict = panel_verdict.published(conn, dev_fingerprint=dev_fingerprint).get(sig.id)
    if verdict is None or not verdict.clears:
        why = (
            "; ".join(verdict.reasons)
            if verdict is not None and verdict.reasons
            else "it has no published verdict on this store"
        )
        return (
            f"{method.id} names signal {sig.id}, which did not clear the panel on this dev store: "
            f"{why}. A signal that does not order next-month returns across the pool is not "
            f"booked, and the panel's no is the finding; nothing in the method file changes it"
        )
    return None


def panel_gate(
    conn: sqlite3.Connection,
    method: Method,
    candidates: Sequence[Candidate],
    *,
    dev_fingerprint: str | None = None,
) -> None:
    """Refuse ``method`` under (D21). Raises ``store.LabError``; silent when it may run.

    Called by ``runner.preflight`` last, before any store is loaded, so a refusal records nothing
    and spends no method id.
    """
    why = panel_refusal(conn, method, candidates, dev_fingerprint=dev_fingerprint)
    if why is not None:
        raise store.LabError(
            f"{why}. Nothing ran and nothing was recorded, and no method id was spent: the luck "
            f"gate's N is what it was (lab/hardgate.py, D21)"
        )
```

**Impact:** New functions, no caller until Step 4. `research._manifest_json` is the same private
reader `research.declared_purpose` uses; reusing it keeps one manifest parser.

### Step 4: call the gate from `runner.preflight`, and pass the loaded store from `run_method`
**File:** `engine/src/seer_engine/lab/runner.py:283-360`, `:875`, `:903`
**Change (a):** Replace the whole `preflight` function (lines 283-360) with:

```python
def preflight(
    conn: sqlite3.Connection,
    method: Method,
    path: Path,
    *,
    require_commit: bool = True,
    amend: bool = False,
    dev_fingerprint: str | None = None,
) -> Amendment | None:
    """Every refusal ``lab run`` makes before loading data (``store.LabError``).

    From M0031 on that includes a variant not priced at Gotrade's real fees
    (``real_costs.real_cost_problem``, which reads ``all_candidates()`` so an amendment is held to
    the same rule); methods up to M0030 are unaffected.

    ``amend`` switches the one refusal that used to be unconditional. Without it a method that has
    run is refused outright -- a method runs once. With it, the method **must** have run, must not
    have reached the test window, and the amendment that runs is the next one its file declares
    that the lab has not recorded (``pending_amendment``). Returns that ``Amendment``, so the
    caller runs its candidates and records its metadata, and None on the ordinary path.

    Either way the "this configuration already ran" check is made only against the candidates this
    run is about to execute: on an amendment the originals have dev trials by definition, and
    checking them would refuse every amendment that ever existed.

    Last, the panel gate (``hardgate.panel_gate``, D21): a method with an arm that chooses among
    index members runs only behind a signal whose published panel verdict clears on the dev store
    being loaded, on that signal's standard book, or under a declared ``panel_exempt``. It reads
    ``all_candidates()`` on a plain run and the pending amendment's candidates on ``--amend``.
    ``dev_fingerprint`` is the fingerprint of the store the run loads: ``run_method`` passes
    ``data.fingerprint``; a caller that has not loaded the store passes None and the gate reads the
    default store's manifest, and only for a method that names a signal. It is last so every older
    refusal keeps its message and its order.
    """
    if require_commit:
        problem = registry_problem(path)
        if problem is not None:
            raise store.LabError(
                f"{method.id}: {problem}. Commit the method file first: the commit is its pre-registration"
            )
    cost_problem = real_cost_problem(method)
    if cost_problem is not None:
        raise store.LabError(f"{method.id}: {cost_problem}")
    row = store.get_method(conn, method.id)
    amendment: Amendment | None = None
    if amend:
        if row is None or row["source_sha"] is None:
            raise store.LabError(
                f"{method.id} has not run, so there is nothing to amend. `lab run {method.id}` "
                f"records its first batch; `--amend` adds a later, separately pre-registered one"
            )
        status = str(row["status"])
        if status in AMEND_CLOSED:
            raise store.LabError(
                f"{method.id} is {status!r}: a method that has reached the test window is not "
                f"amended. The look is spent once and never given back, and growing more variants "
                f"under the same id afterwards is exactly the fishing the pre-registration exists "
                f"to stop. A new question about this book is a new variation method "
                f"(source_kind='variation', parent_id={method.id})"
            )
        if conn.execute(
            "SELECT 1 FROM trials WHERE method_id = ? AND window = 'test' LIMIT 1", (method.id,)
        ).fetchone() is not None:
            raise store.LabError(
                f"{method.id} has a test trial: its one look is spent, so it is not amended"
            )
        amendment = pending_amendment(conn, method)
        running = amendment.candidates
    else:
        if row is not None and row["status"] not in ("idea", "registered"):
            raise store.LabError(
                f"{method.id} is already {row['status']}: a method runs once. More variants of "
                "this same idea are an Amendment in its method file, pre-registered by the commit "
                "that adds it and run with `lab run --amend` -- they record under this method id, "
                "so the luck gate's N does not move. A different idea is a new variation method "
                "(source_kind='variation', parent_id=...)"
            )
        running = method.candidates
    if method.parent_id is not None and store.get_method(conn, method.parent_id) is None:
        raise store.LabError(f"{method.id}: parent {method.parent_id} is not in the lab")
    for c in running:
        if store.has_trial(conn, config_digest(c), "dev"):
            hit = conn.execute(
                "SELECT candidate_id FROM trials WHERE config_digest = ? AND window = 'dev'",
                (config_digest(c),),
            ).fetchone()
            raise store.LabError(f"{c.id} repeats {hit[0]}, which already ran on the dev window")
    # Decision D21 (lab/hardgate.py). A local import for the reason `Run`'s docstring gives:
    # `hardgate.trial_deposits` imports this module inside its body, and the import graph stays
    # acyclic only while neither imports the other at module scope.
    from seer_engine.lab import hardgate

    hardgate.panel_gate(
        conn,
        method,
        method.all_candidates() if amendment is None else amendment.candidates,
        dev_fingerprint=dev_fingerprint,
    )
    return amendment
```

**Change (b):** In `run_method`, replace line 875 exactly:

old:
```python
    amendment = preflight(conn, method, path, require_commit=require_commit, amend=amend)
```
new:
```python
    amendment = preflight(
        conn, method, path, require_commit=require_commit, amend=amend,
        dev_fingerprint=data.fingerprint,
    )
```

**Change (c):** In `run_method`, replace line 903 exactly:

old:
```python
        again = preflight(conn, method, path, require_commit=False, amend=amend)
```
new:
```python
        again = preflight(
            conn, method, path, require_commit=False, amend=amend,
            dev_fingerprint=data.fingerprint,
        )
```

**Impact:** `lab run` and `lab run --amend` now refuse an unpanelled member-picking method with
exit 2 (`commands/lab.py:run` maps `LabError` to 2). `run_method`'s first `preflight` is before
`dev.run_registry`, so the refusal costs no simulation; its second, under the write lock, re-reads
the panel the same way the other refusals are re-read there. Four existing test files drive
`run_method` with member-picking fixture methods and go red until Step 5 (measured below).

### Step 5: existing fixtures that run a member-picking method declare `panel_exempt`
**Files:** `engine/tests/test_lab_exposure.py:64-69`, `engine/tests/test_lab_gate_probe.py:67-72`,
`engine/tests/test_lab_survivorship.py:48-53`, `engine/tests/test_lab_yardstick_gate.py:89-94`
**Change:** Measured during planning (2026-11-13, worktree at `b0652d2`): a pytest plugin wrapped
`runner.preflight` and logged every call that returned (so the gate, placed last, would have fired)
on a method with a member-picking arm, across every test file that calls `run_method`,
`runner.preflight` or `lab_cmd._run`: `test_lab_costs`, `test_lab_runner`, `test_lab_yardstick_gate`,
`test_lab_hardgate`, `test_lab_amendments`, `test_lab_roles`, `test_lab_gate_probe`,
`test_lab_m0030_amendment`, `test_lab_survivorship`, `test_market_series`, `test_lab_exposure`,
`test_lab_test_window`, `test_lab_fold_verdict`, `test_lab_remeasure`, `test_lab_repeat_refusal`,
`test_shares_store`, `test_survivorship_store`, `test_m0053_amendment`, `test_lab_m0262_sessions`.
104 binding calls came from exactly four fixtures: the module-scoped `run_method` seeding in
`test_lab_exposure` (BLEND with a FACTOR part, and FACTOR), `test_lab_gate_probe` (FACTOR),
`test_lab_survivorship` (FACTOR), and `test_lab_yardstick_gate`'s real-engine test (FACTOR,
`M0001-LV`). Every other runner fixture uses `TIMING` or `ROTATION`, whose `uses_members` is
False, so it never binds. `test_lab_hardgate`'s `lab run` CLI tests stub `runner.preflight`
(`_stub_run`), `test_survivorship_store` is refused by the survivorship purpose before the
preflight, `lab/seed.py` writes the `H-*` rows directly, and `lab remeasure` uses its own
`remeasure.preflight`: none reaches the gate. Each of the four fixtures gains a `panel_exempt`;
no assertion changes.

`engine/tests/test_lab_exposure.py`, replace lines 64-69:
```python
def _method(cands=None) -> Method:
    return Method(
        id="M0001", name="Half the market, half quiet stocks", family="factor",
        source_kind="knowledge", source_ref="", hypothesis="h", expected_failure="f",
        candidates=cands or (_cand("M0001-A", PARAMS_A), _cand("M0001-B", PARAMS_B)),
        panel_exempt="chassis: a fixture book for the exposure report, not a stock-picking idea",
    )
```

`engine/tests/test_lab_gate_probe.py`, replace lines 67-72:
```python
def _method(cands=None) -> Method:
    return Method(
        id="M0001", name="Fast movers, bought only in a rising market", family="factor",
        source_kind="knowledge", source_ref="", hypothesis="h", expected_failure="f",
        candidates=cands or (_cand("M0001-A", GATED_PARAMS), _cand("M0001-B", OPEN_PARAMS)),
        panel_exempt="chassis: a fixture book for the gate probe, not a stock-picking idea",
    )
```

`engine/tests/test_lab_survivorship.py`, replace lines 48-53:
```python
def _method(cands=None) -> Method:
    return Method(
        id="M0001", name="Quiet stocks held equally", family="factor", source_kind="knowledge",
        source_ref="", hypothesis="h", expected_failure="f",
        candidates=cands or (_cand("M0001-A", PARAMS_A), _cand("M0001-B", PARAMS_B)),
        panel_exempt="chassis: a fixture book for the survivorship re-run, not a stock-picking idea",
    )
```

`engine/tests/test_lab_yardstick_gate.py`, replace lines 89-94:
```python
def _method(*cands: Candidate) -> Method:
    return Method(
        id="M0001", name="yardstick test", family="trend", source_kind="knowledge",
        source_ref="", hypothesis="h", expected_failure="f",
        candidates=tuple(cands) if cands else (_cand("M0001-A"),),
        panel_exempt="chassis: a fixture book for the random-twin yardstick, not a stock-picking idea",
    )
```

**Impact:** These four files are green again with Step 4 in place. `panel_exempt` is outside every
digest and every recorded row, so nothing they assert moves.

### Step 6: `engine/tests/test_lab_signal_book.py`
**File:** `engine/tests/test_lab_signal_book.py` (new)
**Change:** The chassis's behaviour on a thirty-name synthetic market (`labkit.smoke_history`,
473 sessions, SPY built with `k=4`, which closes under its 200-day average at the March-June 2015
month ends and above it at the others: measured during planning).
**Code:**

```python
"""The one chassis a panelled signal is booked on (lab/signal_book.py; SERA_SIGNAL_PANEL_PLAN.md
phase 5, R4).

Thirty synthetic members over labkit's 473 smoke sessions, so twenty of them is a real choice, and
a SPY whose 200-day switch is off at the March to June 2015 month ends and on at the rest, so both
arms are exercised. The book is held to the allocator contract (P4 identity, no look-ahead, the
lab's lookback cap) and to what it promises: the twenty best scores of F4's screened pool, equal
weight, ties by symbol, a held name kept only while it is still among them, the gated arm empty
exactly when the switch is off.
"""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from allocatorkit import assert_no_lookahead, assert_p4_identity, everyone
from labkit import SMOKE_FIRST, SPY_EX_DATE, smoke_history, smoke_market

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.dev import DEV_END, run_candidate
from seer_engine.backtest.market import Market, Membership
from seer_engine.lab import control_shape, runner, signal_book, tree_rank
from seer_engine.lab import signal as signals
from seer_engine.lab.method import Method, config_digest, config_text
from seer_engine.lab.real_costs import real_cost_problem
from seer_engine.sim.book import equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import Allocator, MarketAware
from seer_engine.strategies.f_factor import trend_on

DAYS = dates.sessions(SMOKE_FIRST, DEV_END)
NAMES = tuple(f"S{i:02d}" for i in range(30))
HISTORY = {s: smoke_history(s, i, DAYS) for i, s in enumerate(NAMES)}
HISTORY["SPY"] = smoke_history("SPY", 4, DAYS)
MEMBERS = everyone({s: HISTORY[s] for s in NAMES})
MONTH_ENDS = tree_rank.month_ends(date(2014, 12, 1), DEV_END)
ADDED = date(2026, 11, 13)
GATED = signal_book.BookParams()
OPEN = signal_book.BookParams(trend=None)
ON_DAY = date(2015, 1, 30)  # a month end with the switch on
TOP_BY_NAME = [f"S{i:02d}" for i in range(29, 9, -1)]


def _ret21(history, market, pool, data_date):
    """Twenty-one-session return: reads only the bars it was handed, which end at data_date."""
    out = {}
    for s in pool:
        h = history.get(s)
        if h is not None and len(h) >= 22:
            out[s] = float(h.close[-1] / h.close[-22] - 1.0)
    return out


def _by_name(history, market, pool, data_date):
    """S29 best, S00 worst: a ranking whose top twenty is known in advance."""
    return {s: float(int(s[1:])) for s in pool if s[0] == "S" and s[1:].isdigit()}


def _flat(history, market, pool, data_date):
    return {s: 1.0 for s in pool}


def _signal(score, sid="S9001", lookback=22, market_fields=()):
    return signals.Signal(
        id=sid, name="test ranking", family="test", source_kind="knowledge", source_ref="",
        hypothesis="h", expected_failure="f", lookback=lookback, score=score,
        market_fields=market_fields,
    )


def _symbols(targets):
    return [t.symbol for t in targets]


# ---- the allocator ---------------------------------------------------------------------------


def test_the_book_is_an_allocator_that_reads_members_and_holds_no_fixed_instrument():
    book = signal_book.book_allocator(_signal(_ret21))
    assert isinstance(book, Allocator)
    assert not isinstance(book, MarketAware)
    assert book.id == "SB-S9001"
    assert book.uses_members(GATED) and book.uses_members(OPEN)
    assert book.holds(GATED) == () and book.holds(OPEN) == ()
    assert book.symbols(GATED) == ("SPY",) and book.symbols(OPEN) == ()


def test_p4_identity_and_no_look_ahead_on_both_arms():
    book = signal_book.book_allocator(_signal(_ret21))
    held = [frozenset(), frozenset({"S00", "S29"})]
    nonempty = assert_p4_identity(book, HISTORY, MEMBERS, MONTH_ENDS, held, [GATED, OPEN])
    nonempty += assert_no_lookahead(
        book, HISTORY, MEMBERS, [date(2015, 4, 1), date(2015, 8, 3)], held, [GATED, OPEN]
    )
    assert nonempty > 0


def test_the_lookback_stays_inside_the_lab_cap():
    assert signal_book.book_allocator(_signal(_ret21)).lookback(GATED) == 253  # F4's 12-1 momentum screen
    longest = signal_book.book_allocator(_signal(_ret21, lookback=signals.MAX_LOOKBACK))
    assert longest.lookback(GATED) == signals.MAX_LOOKBACK


def test_the_top_twenty_by_score_at_equal_weight():
    book = signal_book.book_allocator(_signal(_by_name))
    got = book.targets(HISTORY, MEMBERS(ON_DAY), ON_DAY, frozenset(), GATED)
    assert _symbols(got) == TOP_BY_NAME
    assert {t.weight for t in got} == {equal_weight(signal_book.WIDTH)}


def test_ties_are_broken_by_symbol():
    book = signal_book.book_allocator(_signal(_flat))
    got = book.targets(HISTORY, MEMBERS(ON_DAY), ON_DAY, frozenset(), OPEN)
    assert _symbols(got) == list(NAMES[:20])


def test_a_held_name_is_kept_only_while_it_is_still_top_twenty():
    book = signal_book.book_allocator(_signal(_by_name))
    got = set(_symbols(book.targets(HISTORY, MEMBERS(ON_DAY), ON_DAY, frozenset({"S00", "S29"}), GATED)))
    assert "S29" in got
    assert "S00" not in got


def test_a_name_with_no_opinion_is_skipped():
    def gappy(history, market, pool, data_date):
        out = _by_name(history, market, pool, data_date)
        out["S29"] = math.nan
        del out["S28"]
        return out

    book = signal_book.book_allocator(_signal(gappy))
    got = book.targets(HISTORY, MEMBERS(ON_DAY), ON_DAY, frozenset(), GATED)
    assert _symbols(got) == [f"S{i:02d}" for i in range(27, 7, -1)]


def test_only_f4s_screened_pool_is_ranked():
    thin = smoke_history("THIN", 31, DAYS)
    thin = replace(thin, volume=thin.volume * 1e-4)  # 20-day dollar volume far under F4's 20M floor
    history = {**HISTORY, "THIN": thin}
    members = everyone({s: history[s] for s in (*NAMES, "THIN")})

    def loves_thin(h, market, pool, data_date):
        out = _by_name(h, market, pool, data_date)
        if "THIN" in pool:
            out["THIN"] = 1e9
        return out

    book = signal_book.book_allocator(_signal(loves_thin))
    got = _symbols(book.targets(history, members(ON_DAY), ON_DAY, frozenset(), OPEN))
    assert "THIN" not in got
    assert got == TOP_BY_NAME


def test_the_gated_arm_steps_aside_exactly_when_spy_is_under_its_200_day_average():
    book = signal_book.book_allocator(_signal(_ret21))
    switch = replace(tree_rank.SCREEN, trend=signal_book.SWITCH)
    seen = set()
    for d in MONTH_ENDS:
        on = trend_on(HISTORY, d, switch)
        seen.add(on)
        gated = book.targets(HISTORY, MEMBERS(d), d, frozenset(), GATED)
        never = book.targets(HISTORY, MEMBERS(d), d, frozenset(), OPEN)
        assert len(never) == signal_book.WIDTH
        assert gated == (never if on else ())
    assert seen == {True, False}


def test_the_chassis_has_two_settings_only():
    with pytest.raises(ValueError, match="two settings"):
        signal_book.BookParams(trend=("SPY", 100))
    assert GATED.as_dict() == {"width": "20", "trend": "SPY:200"}
    assert OPEN.as_dict() == {"width": "20", "trend": "none"}


def test_a_market_aware_signal_gets_a_market_aware_book():
    book = signal_book.book_allocator(_signal(_by_name, market_fields=("series",)))
    assert isinstance(book, MarketAware)
    assert runner.market_fields(book) == ("series",)
    assert book.targets(HISTORY, MEMBERS(ON_DAY), ON_DAY, frozenset(), OPEN) == ()
    assert book.targets_prepared(book.prepare(HISTORY), MEMBERS(ON_DAY), ON_DAY, frozenset(), OPEN) == ()
    market = Market(history=HISTORY, membership=Membership(intervals=()), fx=())
    got = book.targets_prepared(book.prepare_market(market), MEMBERS(ON_DAY), ON_DAY, frozenset(), OPEN)
    assert _symbols(got) == TOP_BY_NAME


# ---- the two standard arms -------------------------------------------------------------------


def test_standard_candidates_are_the_two_arms_of_the_one_chassis():
    gated, never = signal_book.standard_candidates(_signal(_ret21), "M0001", ADDED)
    assert (gated.id, never.id) == ("M0001-N20", "M0001-N20-NOGATE")
    assert gated.family == never.family == "M0001"
    assert gated.rules is MONTHLY_HOLD_FRAC_GOTRADE and never.rules is MONTHLY_HOLD_FRAC_GOTRADE
    assert gated.allocator is never.allocator
    assert gated.allocator.id == "SB-S9001"
    assert gated.params == GATED and never.params == OPEN
    assert gated.owner_inputs == never.owner_inputs == ()
    assert "allocator=<SB-S9001>" in config_text(gated)
    assert config_digest(gated) != config_digest(never)


def test_neither_standard_arm_reads_as_a_control():
    for c in signal_book.standard_candidates(_signal(_ret21), "M0001", ADDED):
        assert control_shape.role_of(c) != control_shape.ROLE_CONTROL


def test_the_digest_names_the_signal_not_the_method_or_the_day():
    sig = _signal(_ret21)
    first = signal_book.standard_candidates(sig, "M0001", ADDED)
    again = signal_book.standard_candidates(sig, "M0002", date(2027, 1, 1))
    assert [config_digest(c) for c in first] == [config_digest(c) for c in again]
    other = signal_book.standard_candidates(_signal(_ret21, sid="S9002"), "M0001", ADDED)
    assert not {config_digest(c) for c in first} & {config_digest(c) for c in other}


def test_a_signal_method_built_from_them_validates_at_real_fees():
    m = Method(
        id="M0901", name="t", family="test", source_kind="knowledge", source_ref="",
        hypothesis="h", expected_failure="f", signal="S9001",
        candidates=signal_book.standard_candidates(_signal(_ret21), "M0901", ADDED),
    )
    assert real_cost_problem(m) is None


def test_both_arms_run_a_smoke_window():
    market = smoke_market()
    amount = Decimal("1.0300")
    for c in signal_book.standard_candidates(_signal(_ret21), "M0001", ADDED):
        result, row = run_candidate(
            market, {"SPY": {SPY_EX_DATE: amount}}, (Dividend(SPY_EX_DATE, amount),), c
        )
        assert row.end == DEV_END
        assert len(result.snapshots) >= 2
```

**Impact:** New tests only.

### Step 7: `engine/tests/test_lab_panel_gate.py`
**File:** `engine/tests/test_lab_panel_gate.py` (new)
**Change:** The gate's behaviour through the callers that apply it (`runner.preflight`,
`runner.run_method`, `commands.lab.run`), observed as refusals, exit codes and row counts. A test
signal `S9001` is registered by replacing `signal.discover` (the gate looks it up through the
module at call time); its panel rows are written with phase 2's own insert functions.
**Code:**

```python
"""``lab run``'s panel gate (lab/hardgate.py, D21; SERA_SIGNAL_PANEL_PLAN.md phase 5, R4.1 and R4.2).

A method with an arm that chooses among index members runs only when it names a signal whose
published panel verdict clears on the dev store the run loads -- and then only on that signal's
standard book, beside declared controls -- or when it declares a panel exemption. Every refusal is
a ``store.LabError`` raised in ``runner.preflight`` before any store is loaded or any backtest
runs, so it records nothing and spends no N. ``lab run`` turns it into exit 2.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from labkit import smoke_data

from seer_engine import research
from seer_engine.backtest.dev import Candidate
from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import hardgate, panel, runner, signal_book, store, tree_rank
from seer_engine.lab import method as method_mod
from seer_engine.lab import signal as signals
from seer_engine.lab.method import Amendment, Method, config_digest
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import DESIGN_V0, MONTHLY_HOLD
from seer_engine.strategies.a import DESIGN_PARAMS, STRATEGY_A
from seer_engine.strategies.f_factor import FACTOR, FactorParams
from seer_engine.strategies.f_index import TIMING, TimingParams

HERE = Path(__file__)
COMMITTED = Path(tree_rank.__file__)  # tracked and clean, as a committed method file is
ADDED = date(2026, 11, 13)
SID = "S9001"
EXEMPT = "chassis: a test fixture's book, not a stock-picking idea"


def _score(history, market, pool, data_date):
    return {s: float(len(history[s])) for s in pool if s in history}


SIGNAL = signals.Signal(
    id=SID, name="test ranking", family="test", source_kind="knowledge", source_ref="",
    hypothesis="h", expected_failure="f", lookback=1, score=_score,
)


class _Reached(Exception):
    """Raised by a stubbed step to prove the run got past the gate to it."""


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    seed(c)
    yield c
    c.close()


@pytest.fixture(scope="module")
def data():
    return smoke_data()


@pytest.fixture()
def registered(monkeypatch):
    monkeypatch.setattr(signals, "discover", lambda: {SID: (SIGNAL, HERE)})


def _timing(cid: str, n: int = 50) -> Candidate:
    return Candidate(
        id=cid, family=cid.split("-")[0], rules=MONTHLY_HOLD, allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
        rationale="test", added=ADDED, owner_inputs=(),
    )


def _picker(cid: str, rationale: str = "a hand-built momentum book") -> Candidate:
    return Candidate(
        id=cid, family=cid.split("-")[0], rules=MONTHLY_HOLD, allocator=FACTOR,
        params=FactorParams(rank="momentum", top=5, trend=None),
        rationale=rationale, added=ADDED, owner_inputs=(),
    )


def _method(*cands: Candidate, mid: str = "M0001", **kw) -> Method:
    return Method(
        id=mid, name="panel gate test", family="test", source_kind="knowledge", source_ref="",
        hypothesis="h", expected_failure="f", candidates=tuple(cands), **kw,
    )


def _signal_method(*extra: Candidate, sig=SIGNAL, mid: str = "M0001") -> Method:
    return _method(*signal_book.standard_candidates(sig, mid, ADDED), *extra, mid=mid, signal=SID)


def _seed_panel(conn, *, sha: str | None = None, dev_fp: str = "smoke", clears: bool = True) -> None:
    """One recorded panel for S9001: every era on the dev and the survivorship store.

    A clearing reading is plainly clear (controlled slope t = 5, positive recent spread, positive
    survivorship slope); a failing one is the same numbers with the sign flipped.
    """
    sign = 1.0 if clears else -1.0
    with conn:
        store.insert_panel_signal(conn, store.PanelSignalRow(
            id=SID, kind="signal", name="test ranking", family="test", hypothesis="h",
            expected_failure="f", source_kind="knowledge", source_ref="", method_id=None,
            source_sha=signals.source_sha(HERE) if sha is None else sha,
            created="2026-11-13T00:00:00+00:00",
        ))
        store.insert_panel_results(conn, [
            store.PanelResultRow(
                signal_id=SID, rule_id=panel.RULE_ID, store_role=role, store_fingerprint=fp,
                era=era, months=120, mean_pool=400.0, mean_scored=380.0,
                ic_mean=0.03 * sign, ic_t=4.0 * sign, spread_top=0.06 * sign, spread_t=4.0 * sign,
                fm_slope=0.004 * sign, fm_t=5.0 * sign, top_turnover=0.3,
                picks_hash=f"test-{SID}", git_sha="test", measured="2026-11-13T00:00:00+00:00",
            )
            for role, fp in (("dev", dev_fp), ("survivorship", f"{dev_fp}-sv"))
            for era in panel.ERAS
        ])


def _recorded(conn, mid: str = "M0001") -> tuple[int, int, bool]:
    """(dev trials, methods with a dev trial -- what the luck gate's N counts, whether ``mid`` has a row)."""
    trials, methods = conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT method_id) FROM trials WHERE window = 'dev'"
    ).fetchone()
    return int(trials), int(methods), store.get_method(conn, mid) is not None


def _no_backtest(*_a, **_k):
    raise AssertionError("the panel gate must refuse before any backtest")


def _reached(*_a, **_k):
    raise _Reached()


# ---- which methods the gate binds ---------------------------------------------------------


def test_a_member_picking_arm_binds_and_a_market_arm_does_not():
    assert hardgate.picks_members(_picker("M0001-A"))
    assert not hardgate.picks_members(_timing("M0001-B"))
    bracket = Candidate(
        id="M0001-C", family="M0001", rules=DESIGN_V0, allocator=STRATEGY_A,
        params=DESIGN_PARAMS, rationale="t", added=ADDED, owner_inputs=(),
    )
    assert hardgate.picks_members(bracket)


def test_a_method_that_picks_no_member_is_not_bound(conn):
    assert runner.preflight(conn, _method(_timing("M0001-A")), HERE, require_commit=False) is None


# ---- R4.1: neither a cleared signal nor an exemption ----------------------------------------


def test_an_unpanelled_member_picker_is_refused_in_preflight(conn):
    before = _recorded(conn)
    with pytest.raises(store.LabError, match="D21") as refused:
        runner.preflight(
            conn, _method(_picker("M0001-A"), _timing("M0001-B")), HERE, require_commit=False
        )
    text = str(refused.value)
    assert "M0001-A" in text and "M0001-B" not in text
    assert "lab panel" in text and "panel_exempt" in text
    assert "Nothing ran and nothing was recorded" in text
    assert _recorded(conn) == before


def test_run_method_refuses_before_any_backtest(conn, data, monkeypatch):
    monkeypatch.setattr(runner.dev, "run_registry", _no_backtest)
    before = _recorded(conn)
    with pytest.raises(store.LabError, match="D21"):
        runner.run_method(conn, _method(_picker("M0001-A")), HERE, data, git_sha="x", require_commit=False)
    assert _recorded(conn) == before


def test_lab_run_exits_2_before_loading_a_store(tmp_path, monkeypatch):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    seed(c)
    before = _recorded(c)
    c.close()
    m = _method(_picker("M0001-A"))
    monkeypatch.setattr(method_mod, "discover", lambda: {"M0001": (m, COMMITTED)})
    monkeypatch.setattr(research, "load_store", _no_backtest)
    rc = lab_cmd.run(argparse.Namespace(
        db=db, lab_command="run", method="M0001", store=tmp_path / "store", allow_coverage=0.8,
    ))
    assert rc == 2
    c = store.connect(db)
    assert _recorded(c) == before
    c.close()


def test_the_gate_holds_for_an_amendment(conn, data):
    runner.run_method(conn, _method(_timing("M0001-A")), HERE, data, git_sha="x", require_commit=False)
    amendment = Amendment(
        added=ADDED, why="w", hypothesis="h", expected_failure="f",
        candidates=(_picker("M0001-P"),),
    )
    before = _recorded(conn)
    with pytest.raises(store.LabError, match="D21"):
        runner.preflight(
            conn, _method(_timing("M0001-A"), amendments=(amendment,)), HERE,
            require_commit=False, amend=True,
        )
    assert _recorded(conn) == before
    exempt = _method(_timing("M0001-A"), amendments=(amendment,), panel_exempt=EXEMPT)
    assert runner.preflight(conn, exempt, HERE, require_commit=False, amend=True) is amendment


# ---- the exemption --------------------------------------------------------------------------


@pytest.mark.parametrize("why", ["chassis: a brake on a recorded book", "control-study: twin spread", "market: breadth"])
def test_a_declared_exemption_lets_a_member_picker_through(conn, why):
    m = _method(_picker("M0001-A"), panel_exempt=why)
    assert runner.preflight(conn, m, HERE, require_commit=False) is None


# ---- the signal path (R4.1) -----------------------------------------------------------------


def test_an_unknown_signal_is_refused(conn, monkeypatch):
    monkeypatch.setattr(signals, "discover", lambda: {})
    with pytest.raises(store.LabError, match="names signal S9001, and no"):
        runner.preflight(conn, _signal_method(), HERE, require_commit=False, dev_fingerprint="smoke")


def test_a_signal_with_no_panel_on_this_store_is_refused(conn, registered):
    with pytest.raises(store.LabError, match="lab panel S9001"):
        runner.preflight(conn, _signal_method(), HERE, require_commit=False, dev_fingerprint="smoke")


def test_a_panel_on_another_dev_store_does_not_count(conn, registered):
    _seed_panel(conn, dev_fp="another-store")
    with pytest.raises(store.LabError, match="lab panel S9001"):
        runner.preflight(conn, _signal_method(), HERE, require_commit=False, dev_fingerprint="smoke")


def test_a_signal_that_did_not_clear_is_refused(conn, registered):
    _seed_panel(conn, clears=False)
    before = _recorded(conn)
    with pytest.raises(store.LabError, match="did not clear the panel"):
        runner.preflight(conn, _signal_method(), HERE, require_commit=False, dev_fingerprint="smoke")
    assert _recorded(conn) == before


def test_a_signal_file_changed_since_its_panel_is_refused(conn, registered):
    _seed_panel(conn, sha="0" * 64)
    with pytest.raises(store.LabError, match="no longer hashes"):
        runner.preflight(conn, _signal_method(), HERE, require_commit=False, dev_fingerprint="smoke")


def test_a_cleared_signal_on_its_standard_book_passes(conn, registered):
    _seed_panel(conn)
    assert runner.preflight(conn, _signal_method(), HERE, require_commit=False, dev_fingerprint="smoke") is None


def test_run_method_judges_the_panel_of_the_store_it_loaded(conn, data, registered, monkeypatch):
    """run_method hands preflight data.fingerprint ('smoke' for labkit's store), not a default."""
    _seed_panel(conn)  # recorded on "smoke"
    monkeypatch.setattr(runner.dev, "run_registry", _reached)
    with pytest.raises(_Reached):
        runner.run_method(conn, _signal_method(), HERE, data, git_sha="x", require_commit=False)


def test_run_method_refuses_a_panel_on_another_store(conn, data, registered, monkeypatch):
    _seed_panel(conn, dev_fp="another-store")
    monkeypatch.setattr(runner.dev, "run_registry", _no_backtest)
    with pytest.raises(store.LabError, match="lab panel S9001"):
        runner.run_method(conn, _signal_method(), HERE, data, git_sha="x", require_commit=False)


def test_the_fingerprint_defaults_to_the_store_lab_run_would_load(conn, registered, tmp_path, monkeypatch):
    where = tmp_path / "store"
    where.mkdir()
    (where / "manifest.json").write_text(json.dumps({"fingerprint": "fp-from-manifest"}), encoding="utf-8")
    monkeypatch.setenv("SEER_RESEARCH_STORE", str(where))
    assert hardgate.dev_store_fingerprint() == "fp-from-manifest"
    _seed_panel(conn, dev_fp="fp-from-manifest")
    assert runner.preflight(conn, _signal_method(), HERE, require_commit=False) is None


def test_an_unreadable_dev_store_refuses_a_signal_method(conn, registered, tmp_path, monkeypatch):
    monkeypatch.setenv("SEER_RESEARCH_STORE", str(tmp_path / "missing"))
    with pytest.raises(store.LabError, match="SEER_RESEARCH_STORE"):
        runner.preflight(conn, _signal_method(), HERE, require_commit=False)


# ---- R4.2: a signal method books the standard chassis and nothing else ------------------------


def test_a_hand_built_treatment_beside_a_signal_is_refused(conn, registered):
    _seed_panel(conn)  # the signal clears: the extra arm is the only thing wrong
    before = _recorded(conn)
    with pytest.raises(store.LabError, match="M0001-HAND") as refused:
        runner.preflight(
            conn, _signal_method(_picker("M0001-HAND")), HERE, require_commit=False,
            dev_fingerprint="smoke",
        )
    assert "standard book" in str(refused.value)
    assert _recorded(conn) == before


def test_the_arm_shape_is_refused_before_any_store_is_read(conn, registered, tmp_path, monkeypatch):
    monkeypatch.setenv("SEER_RESEARCH_STORE", str(tmp_path / "missing"))
    with pytest.raises(store.LabError, match="M0001-HAND"):
        runner.preflight(conn, _signal_method(_timing("M0001-HAND")), HERE, require_commit=False)


def test_a_standard_book_of_another_signal_is_refused(conn, registered):
    _seed_panel(conn)
    other = replace(SIGNAL, id="S9002")
    m = _method(*signal_book.standard_candidates(other, "M0001", ADDED), signal=SID)
    with pytest.raises(store.LabError, match="standard book"):
        runner.preflight(conn, m, HERE, require_commit=False, dev_fingerprint="smoke")


def test_a_declared_control_beside_the_standard_book_is_allowed(conn, registered):
    _seed_panel(conn)
    foil = _picker("M0001-CTRL", rationale="Control: twenty names in hash order, registered to be beaten.")
    assert runner.preflight(
        conn, _signal_method(foil), HERE, require_commit=False, dev_fingerprint="smoke"
    ) is None


# ---- the two fields ---------------------------------------------------------------------------


def test_signal_and_exemption_are_validated_at_construction():
    with pytest.raises(ValueError, match="S0001"):
        _method(_timing("M0001-A"), signal="0001")
    with pytest.raises(ValueError, match="panel_exempt"):
        _method(_timing("M0001-A"), panel_exempt="because")
    with pytest.raises(ValueError, match="panel_exempt"):
        _method(_timing("M0001-A"), panel_exempt="chassis:   ")
    with pytest.raises(ValueError, match="never both"):
        _method(_timing("M0001-A"), signal="S0001", panel_exempt=EXEMPT)
    with pytest.raises(TypeError, match="panel_exempt"):
        _method(_timing("M0001-A"), panel_exempt=None)


def test_the_method_and_signal_id_patterns_agree():
    assert method_mod.SIGNAL_ID.pattern == signals.SIGNAL_ID.pattern


def test_the_two_fields_move_no_config_digest():
    plain = _method(_picker("M0001-A"))
    exempt = _method(_picker("M0001-A"), panel_exempt=EXEMPT)
    assert [config_digest(c) for c in plain.candidates] == [config_digest(c) for c in exempt.candidates]


def test_discovering_the_method_files_never_consults_the_gate(monkeypatch):
    def tripwire(*_a, **_k):
        raise AssertionError("the panel gate fired outside lab run")

    monkeypatch.setattr(hardgate, "panel_refusal", tripwire)
    monkeypatch.setattr(hardgate, "panel_gate", tripwire)
    assert method_mod.discover()
```

**Impact:** New tests only.

### Step 8: the method template shows both shapes
**File:** `.claude/skills/explore-and-experiment-new-method/method_template.py` (whole file)
**Change:** With the gate in place the old template, a member-picking allocator with no
exemption, would be refused at `lab run` as written. The new file leads with the signal form and
keeps the own-allocator form for an idea that is not a stock-picking signal, declaring
`panel_exempt`. Phase 7 rewrites the skill prose around it.
**Code:**

```python
"""MNNNN — <one-line name>.

Source: <URL / citation / "variation of M00xx" / general knowledge>.
Idea: <two or three sentences: the mechanism and why it should beat SPY under design §1>.

Copy to engine/src/seer_engine/lab/methods/mNNNN_<slug>.py, replace every MNNNN, keep ONE of the
two shapes below and delete the other.

A. A stock-picking idea (it ranks index members) is a SIGNAL first: write
   seer_engine/lab/signals/sNNNN_<slug>.py from signal_template.py, commit it, run
   `lab panel SNNNN`. Only once it clears does it become a method, and the method is shape A:
   `signal="SNNNN"` and the two standard arms, nothing hand-built. `lab run` refuses anything
   else (lab/hardgate.py, D21). A foil beside them is allowed when its rationale opens "Control:".

B. Anything else -- a market switch, an ETF rotation, a brake or width or cadence measured on a
   book, a control study -- is your own allocator. Reusing an existing one (FACTOR, TIMING,
   ROTATION, SWING, VOLTARGET, BLEND) with new params needs no class at all: write only METHOD.
   If any arm chooses among index members, declare why the panel does not apply:
   `panel_exempt="chassis: <why>"`, `"control-study: <why>"` or `"market: <why>"`.

Pure: no clock, randomness, files, network, printing. Read only bars dated <= data_date.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.signal_book import standard_candidates
from seer_engine.lab.signals.sNNNN_slug import SIGNAL  # shape A: the committed, cleared signal
from seer_engine.sim.book import Target, equal_weight
# Fractional and at Gotrade's real fees by default: paper trades books in fractional shares, a 20M
# IDR book cannot fill whole-share slots at 2016+ prices (M0021), and from M0031 on `lab run`
# refuses a variant at the old flat 0.1%. Other real-fee preset: MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE.
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 11, 13)  # today


# ---- Shape A: a panelled signal on the one chassis ---------------------------------------------
# No allocator, no params: the arms are the signal's standard book -- the twenty highest-scored
# members of F4's pool, equal weight, monthly at Gotrade's fees, one arm behind the SPY 200-day
# switch (MNNNN-N20) and one never stepping aside (MNNNN-N20-NOGATE).

METHOD = Method(
    id="MNNNN",
    name="<name>",
    family=SIGNAL.family,
    source_kind="knowledge",  # paper | blog | github | knowledge | variation
    source_ref="",            # URL / citation / parent id (required unless knowledge)
    parent_id=None,           # set for a variation
    hypothesis="<why the signal's book beats total-return SPY under design §1>",
    expected_failure="<the way it most likely fails, written before the run>",
    signal="SNNNN",
    candidates=standard_candidates(SIGNAL, "MNNNN", ADDED),
    seen_keys=("concept:<short-concept>",),
)


# ---- Shape B: your own allocator -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Params:
    top: int = 10
    lookback_n: int = 126

    def as_dict(self) -> dict[str, str]:  # every field, as plain strings
        return {"top": str(self.top), "lookback_n": str(self.lookback_n)}


class Alloc:
    """<What it targets on data_date d, in one paragraph. Held symbols: keep or drop?>"""

    id = "MNNNN"  # unique across the lab: the method id

    def lookback(self, params: Params) -> int:
        return params.lookback_n + 1  # bars through d the decision needs

    def symbols(self, params: Params) -> tuple[str, ...]:
        return ("SPY",)  # fixed instruments read (not index members)

    def holds(self, params: Params) -> tuple[str, ...]:
        return ()  # fixed instruments it may hold (ETFs); () when it holds members only

    def uses_members(self, params: Params) -> bool:
        return True  # reads index members (point-in-time S&P 500 ∪ Nasdaq-100): needs panel_exempt

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Params) -> tuple[Target, ...]:
        scored: list[tuple[float, str]] = []
        for s in sorted(members):
            h = history.get(s)
            if h is None or h.index_of(data_date) is None:  # a new target needs a bar dated d
                continue
            i = h.index_of(data_date)
            if i < params.lookback_n:
                continue
            score = float(h.close[i] / h.close[i - params.lookback_n] - 1.0)  # <your rule>
            scored.append((-score, s))
        w = equal_weight(params.top)
        out: list[Target] = []
        for _, s in sorted(scored)[: params.top]:
            t = target_from_close(s, last_close(history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)  # rank order, unique symbols, Σ weight <= 1

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)  # precompute here only if targets_prepared stays == targets

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Params) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


ALLOC = Alloc()


def _v(suffix: str, params: Params, rationale: str, rules=MONTHLY_HOLD_FRAC_GOTRADE) -> Candidate:
    return Candidate(id=f"MNNNN-{suffix}", family="MNNNN", rules=rules, allocator=ALLOC,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="MNNNN",
    name="<name>",
    family="<free-text family, e.g. trend-switch>",
    source_kind="knowledge",
    source_ref="",
    parent_id=None,
    hypothesis="<why this beats total-return SPY under design §1>",
    expected_failure="<the way it most likely fails, written before the run>",
    candidates=(
        _v("V1", Params(), "<one line>"),
    ),
    # Required here because Alloc.uses_members is True; delete it for an allocator that reads no
    # member. Begin with chassis:, control-study: or market:, then say why.
    panel_exempt="chassis: <why this member-picking book is not a new stock-picking idea>",
    seen_keys=("concept:<short-concept>",),
)
```

**Impact:** Documentation template only; it is not importable as written (it names
`sNNNN_slug`) and nothing imports it.

### Step 9: the feature map
**File:** `.claude/skills/verify-seer/features/lab-cli.md:7` and after `:46`
**Change (a):** In the `- Refused:` bullet (line 7), insert this sentence directly after the
first sentence (after "... (exit 2, nothing written, no arm metric printed);"):

```text
 `lab run` (and `--amend`) on a method with an arm that chooses among index members unless it names a signal whose published panel verdict clears on the dev store being loaded and its non-control arms are exactly that signal's standard book (`signal_book.standard_candidates`), or it declares `panel_exempt` (`chassis:`, `control-study:` or `market:` and a reason): exit 2 before the store loads, nothing written, the dev trial and method counts unchanged (hardgate D21);
```

**Change (b):** Append this bullet at the end of `## Gotchas` (after the last bullet, line 46):

```text
- The panel gate (D21) cannot be driven through `$V lab RUN run`: that needs a committed method file. Drive `commands.lab.run` with `method.discover` replaced by a throwaway method whose path is a tracked, clean file (any engine module), against the run's lab copy (`SEER_LAB_DB=~/.local/state/seer-verify/RUN/lab.sqlite`) with `SEER_RESEARCH_STORE` at the main checkout's dev store and `research.load_store` replaced by a tripwire, so a method the gate lets through stops at the load instead of spending minutes. The phase-5 plan of `sera-signal-panel` carries such a script (`panel_gate_drive.py`). A cleared signal needs panel rows on the store's manifest fingerprint: on a copy, `lab panel SNNNN` writes them, or the script seeds a plainly clearing reading.
```

**Impact:** Feature map only.

## Principles applied

- Laziness protocol: the gate is one more refusal at the end of the existing `runner.preflight`, not a new pass or a new command; the chassis reuses F4's screen (`factor_rows`/`rows_on`), F4's switch (`trend_on`), the panel's own cut (`Signal.scores`), the runner's control reader (`control_shape.role_of`) and `research._manifest_json`, so `signal_book.py` and the gate contain no second copy of any of them.
- Make illegal states unrepresentable: `signal` and `panel_exempt` together, a malformed signal id and an exemption without a kind or a reason are refused at `Method` construction; `BookParams` accepts only the two chassis settings (`SWITCH` or `None`) and carries no width, cadence or weighting field at all, so a hand-tuned chassis cannot be expressed through `standard_candidates`.
- Boundary discipline: the fields are validated once, in `Method.__post_init__`, and the gate trusts their shape; the dev fingerprint enters once per `preflight` (`data.fingerprint` from `run_method`, or the manifest read lazily, only for a method that names a signal).
- Encode lessons in structure: `SIGNAL_ID` is restated in `method.py` (an import would be a cycle), so a test pins it equal to `signal.SIGNAL_ID`; the gate sits last in `preflight` so no existing refusal changes its message or order; the probe measurement of which fixtures bind is recorded in Step 5 so the fixture edits are evidence-led, not guessed.
- Test behavior, not implementation: the tests drive `runner.preflight`, `runner.run_method` and `commands.lab.run`, and assert refusals, exit codes and the trial/method counts; nothing mocks the gate. Only the expensive edges (the backtest, the store load) are replaced, by tripwires that prove the gate fired before them.
- Prove it works: J1-J3 drive the real `lab run` handler against a verify-seer lab copy and the real dev store manifest, and read the counts back.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/sera-signal-panel && /home/miftah/seer/engine/.venv/bin/ruff check engine`

**Tests:**
```sh
cd /home/miftah/.worktrees/seer/sera-signal-panel
PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest -n 2 \
  engine/tests/test_lab_panel_gate.py engine/tests/test_lab_signal_book.py \
  engine/tests/test_lab_runner.py engine/tests/test_lab_amendments.py \
  engine/tests/test_lab_repeat_refusal.py engine/tests/test_lab_yardstick_gate.py \
  engine/tests/test_lab_exposure.py engine/tests/test_lab_gate_probe.py \
  engine/tests/test_lab_survivorship.py engine/tests/test_lab_methods.py \
  engine/tests/test_lab_costs.py engine/tests/test_lab_roles.py \
  engine/tests/test_lab_fold_verdict.py engine/tests/test_lab_remeasure.py
# then the whole engine suite (DB tests need Postgres; CI fails if they skip):
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest -n 2 engine/tests
```
Known baseline failure (index invariant 11), reported by this phase's planner on `b0652d2`
(2026-11-13, re-run alone, no plugin loaded):
`engine/tests/test_lab_hardgate.py::test_the_buy_signal_fires_on_the_promoted_arm_and_the_set_moved_both_ways`
fails before this phase. Re-run that test file alone on the untouched base before blaming this
phase, and do not "fix" it.

**Proof:** the real `lab run` handler (`commands.lab.run`) refuses and admits methods on a
verify-seer copy of the lab, before the dev store is loaded, and the copy's counts do not move.
- Harness: `.claude/skills/verify-seer` (lab copy via `up --no-web --empty`; `labsql` reads it back)
- Feature-map entries: `.claude/skills/verify-seer/features/lab-cli.md`
- Setup, from the worktree root, run once before the journeys:
  ```sh
  cd /home/miftah/.worktrees/seer/sera-signal-panel
  V=.claude/skills/verify-seer/scripts/verify.sh
  $V up --no-web --empty                 # note the printed RUN=<id>
  RUN=<id>
  export SEER_ENV_FILE=$HOME/.local/state/seer-verify/$RUN/engine.env
  export SEER_LAB_DB=$HOME/.local/state/seer-verify/$RUN/lab.sqlite
  export SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research
  export PYTHONPATH=$PWD/engine/src
  PY=/home/miftah/seer/engine/.venv/bin/python
  SCRATCH=<your scratch directory>      # write panel_gate_drive.py (below) there
  ```
  `panel_gate_drive.py`:
  ```python
  """Drive `lab run`'s panel gate (lab/hardgate.py D21) on a verify-seer lab copy.

  Usage: panel_gate_drive.py unpanelled|handbuilt|cleared   (run them in that order)
  SEER_LAB_DB must be the verify run's copy; the committed database is refused. Nothing here
  commits, and the store is never loaded: `research.load_store` is replaced by a tripwire, so a
  method the gate lets through stops at the load and prints REACHED.
  """

  from __future__ import annotations

  import argparse
  import os
  import sys
  from datetime import date, datetime, timezone
  from pathlib import Path

  from seer_engine import research
  from seer_engine.backtest.dev import Candidate
  from seer_engine.commands import lab as lab_cmd
  from seer_engine.lab import hardgate, panel, signal_book, store, tree_rank
  from seer_engine.lab import method as method_mod
  from seer_engine.lab import signal as signals
  from seer_engine.lab.method import Method
  from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
  from seer_engine.strategies.f_factor import FACTOR, FactorParams

  DB = Path(os.environ["SEER_LAB_DB"]).resolve()
  if DB == store.COMMITTED_DB.resolve():
      sys.exit("refusing: SEER_LAB_DB is the committed lab")
  STORE = Path(os.environ["SEER_RESEARCH_STORE"])
  COMMITTED = Path(tree_rank.__file__)  # tracked and clean, as a committed method file is
  MID, SID, ADDED = "M9901", "S0001", date(2026, 11, 13)


  class Reached(Exception):
      pass


  def picker(cid: str) -> Candidate:
      return Candidate(id=cid, family=MID, rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=FACTOR,
                       params=FactorParams(rank="momentum", top=20),
                       rationale="A hand-built momentum book.", added=ADDED, owner_inputs=())


  def meth(cands, **kw) -> Method:
      return Method(id=MID, name="panel gate drive", family="verify-panel-gate",
                    source_kind="knowledge", source_ref="", hypothesis="harness check, never recorded",
                    expected_failure="refused", candidates=tuple(cands), **kw)


  def recorded() -> tuple[int, int, bool]:
      c = store.connect(DB)
      try:
          trials, methods = c.execute(
              "SELECT COUNT(*), COUNT(DISTINCT method_id) FROM trials WHERE window = 'dev'"
          ).fetchone()
          return int(trials), int(methods), store.get_method(c, MID) is not None
      finally:
          c.close()


  def refusal(m: Method) -> str | None:
      c = store.connect(DB)
      try:
          return hardgate.panel_refusal(c, m, m.all_candidates(),
                                        dev_fingerprint=hardgate.dev_store_fingerprint(STORE))
      finally:
          c.close()


  def lab_run(m: Method) -> str:
      method_mod.discover = lambda: {MID: (m, COMMITTED)}

      def tripwire(_path):
          raise Reached

      research.load_store = tripwire
      try:
          return str(lab_cmd.run(argparse.Namespace(
              db=DB, lab_command="run", method=MID, store=STORE, allow_coverage=0.8)))
      except Reached:
          return "REACHED"


  def seed_cleared_panel() -> str:
      sig, path = signals.discover()[SID]
      fp = hardgate.dev_store_fingerprint(STORE)
      now = datetime.now(timezone.utc).isoformat(timespec="seconds")
      c = store.connect(DB)
      try:
          with c:
              store.insert_panel_signal(c, store.PanelSignalRow(
                  id=SID, kind="signal", name=sig.name, family=sig.family,
                  hypothesis=sig.hypothesis, expected_failure=sig.expected_failure,
                  source_kind=sig.source_kind, source_ref=sig.source_ref, method_id=None,
                  source_sha=signals.source_sha(path), created=now))
              store.insert_panel_results(c, [
                  store.PanelResultRow(
                      signal_id=SID, rule_id=panel.RULE_ID, store_role=role, store_fingerprint=f,
                      era=era, months=120, mean_pool=400.0, mean_scored=380.0, ic_mean=0.03,
                      ic_t=4.0, spread_top=0.06, spread_t=4.0, fm_slope=0.004, fm_t=5.0,
                      top_turnover=0.3, picks_hash="verify-" + SID, git_sha="verify", measured=now)
                  for role, f in (("dev", fp), ("survivorship", "verify-sv"))
                  for era in panel.ERAS
              ])
      finally:
          c.close()
      return fp


  def main(mode: str) -> None:
      sig = signals.discover()[SID][0]
      standard = signal_book.standard_candidates(sig, MID, ADDED)
      before = recorded()
      print(f"mode: {mode}")
      if mode == "unpanelled":
          m = meth([picker(f"{MID}-A")])
          print(f"refusal: {refusal(m)}")
          print(f"lab run exit: {lab_run(m)}")
      elif mode == "handbuilt":
          m = meth([*standard, picker(f"{MID}-HAND")], signal=SID)
          print(f"refusal: {refusal(m)}")
          print(f"lab run exit: {lab_run(m)}")
      elif mode == "cleared":
          print(f"seeded a clearing panel on dev store {seed_cleared_panel()[:12]}")
          before = recorded()  # panel rows are not trials; the counts are taken after seeding
          print(f"signal method: {lab_run(meth(standard, signal=SID))}")
          exempt = meth([picker(f"{MID}-A")], panel_exempt="chassis: verify drive")
          print(f"exempt method: {lab_run(exempt)}")
      else:
          sys.exit(f"unknown mode {mode!r}")
      print(f"before: {before}")
      print(f"after: {recorded()}")


  if __name__ == "__main__":
      main(sys.argv[1])
  ```
- Journeys:
  - **J1** · traces R4.1 — `$V labsql $RUN "select count(*), count(distinct method_id) from trials where window='dev'"`, then `$PY $SCRATCH/panel_gate_drive.py unpanelled`, then the same `labsql` again → passes when the drive prints `lab run exit: 2`, a `refusal:` line containing `picks index members (M9901-A)` and `panel_exempt`, `before:` and `after:` print the identical tuple ending in `False` (no `M9901` method row), and both `labsql` reads return the same two numbers.
  - **J2** · traces R4.2 — `$PY $SCRATCH/panel_gate_drive.py handbuilt` → passes when it prints `lab run exit: 2`, a `refusal:` line containing `M9901-HAND` and `standard book`, and `before:` equals `after:` (ending in `False`). The method's signal S0001 has no panel in the copy, so the refusal proves the arm shape is judged first and on its own.
  - **J3** · traces R4.1, R4.2 — `$PY $SCRATCH/panel_gate_drive.py cleared`, then `$V labsql $RUN "select count(*) from trials where window='dev'"` → passes when it prints `signal method: REACHED` (a method naming S0001 with exactly its two standard arms got past every `preflight` refusal to the store load, through the real `lab run` handler and the real dev store's manifest fingerprint), `exempt method: REACHED`, and `before:` equals `after:`; the `labsql` count equals the one J1 read.
  - **J4** · traces R4.1, R4.2 — `PYTHONPATH=$PWD/engine/src $PY -m pytest -n 2 engine/tests/test_lab_panel_gate.py engine/tests/test_lab_signal_book.py` → passes when every test passes, including `test_lab_run_exits_2_before_loading_a_store`, `test_run_method_refuses_before_any_backtest`, `test_the_gate_holds_for_an_amendment`, `test_a_signal_that_did_not_clear_is_refused` and `test_a_hand_built_treatment_beside_a_signal_is_refused`.
- Neighbor check: the existing runner flows most likely to break are a plain run and an amendment of a non-member method, and the four fixtures that run member-picking books. `PYTHONPATH=$PWD/engine/src $PY -m pytest -n 2 engine/tests/test_lab_runner.py engine/tests/test_lab_amendments.py engine/tests/test_lab_repeat_refusal.py engine/tests/test_lab_exposure.py engine/tests/test_lab_gate_probe.py engine/tests/test_lab_survivorship.py engine/tests/test_lab_yardstick_gate.py engine/tests/test_lab_methods.py` passes with no failure; `test_lab_methods.py::test_every_recorded_configuration_still_digests_to_its_recorded_digest` and `::test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` pass untouched.
- After the journeys: `$V down $RUN`.
- Cost: none. Offline, no LLM drive, and no journey loads the dev store (J3 stops at the load).

**Exit criteria:** on a verify-seer lab copy, `lab run` exits 2 with a D21 refusal and unchanged
trial and method counts for an unpanelled member-picking method (J1) and for a signal method with
a hand-built treatment (J2); it lets through a cleared signal on its standard book and an exempt
chassis method (J3); both new test files and the full engine suite pass apart from the one
baseline failure named above.

## Handoffs

- **Phase 7 (skills and docs):** document `signal=` / `standard_candidates` and `panel_exempt` in
  `.claude/skills/explore-and-experiment-new-method/SKILL.md` and `sera-the-explorer/SKILL.md`
  (the template in Step 8 already shows both shapes); state that `lab run --amend` of a recorded
  member-picking method (387 of the 412 method files, measured at `b0652d2`) needs
  `panel_exempt` added in the same commit that adds the `Amendment`; and in
  `.claude/skills/redo-sera-experiments/SKILL.md` the minted twin carries `panel_exempt`
  (the index already assigns that paragraph to phase 7).
- **Phase 3 (owner of `commands/lab.py`), optional:** `commands/lab.py:2078` calls
  `runner.preflight` with no `dev_fingerprint`, so the first check reads the default store's
  manifest (`$SEER_RESEARCH_STORE` or `research.STORE_DIR`). When `--store` names a different
  store, that early check judges the default store; the authoritative check in `run_method`
  (with `data.fingerprint`, before any simulation) still judges the right one. Passing
  `dev_fingerprint=hardgate.dev_store_fingerprint(Path(args.store))` there, inside a
  `try/except ValueError` that leaves it None, makes the early check exact. Correctness does not
  depend on it. **Reconciler: not adopted in this set** (phase 3's plan touches only additive
  blocks of `commands/lab.py`; `_run` stays unchanged and `run_method`'s check is authoritative).
- **Phases 2 and 3 (confirmed by the reconciler, Decisions):** the dev rows of `panel_results`
  carry the dev store's full `ResearchData.fingerprint` (the manifest's `"fingerprint"`), not its
  `price_fingerprint`; this phase compares against exactly that value.
- **Out of scope for this set (index Scope, Decisions):** `lab promote` and the paper roster resolve
  a promoted variant's allocator by id; an `SB-*` signal book is built per signal and is not a
  preset or a registry entry, so promoting a signal method will need the resolver to rebuild it
  from the signal id (the memory notes "a roster entry can only name a preset" and "`promote`
  breaks on a second resolver key"). Nothing can reach promotion until a signal clears the panel
  and the hard gate; it is the first follow-up when one does. Phase 7's skill text tells Sera to
  record a `feature-wish` insight and report it first if a signal book ever turns dev-eligible
  and promotable.

## Rollback

Revert this phase's commit. It writes no data, changes no table and moves no digest: `lab run`
returns to accepting any method, `signal_book.py` and the two test files disappear, the four
fixtures lose a field nothing else reads. A method file committed after landing that uses
`signal=` or `panel_exempt` would then fail to construct (unknown keyword) and must be reverted
with it; before any such file exists, the revert is clean.
