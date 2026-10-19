# Phase 4: M0047 — the size-weighted residual's two placebos

**Plan set:** `HONEST_CONTROL_REDRAW_PLAN.md`
**Analysis:** `docs/analyzer/20261019-181712-C4K9_code_analyzer.md`
**Satisfies:** R2 (re-draw the mis-shaped arms as an amendment under the existing id), R3 (re-state
the margins in `trial_funding.mwr`, including ones that worsen), R4 (the arm's own `supersedes` declaration — without it phase 2's D17 rule fires on nothing and the method stays blocked after the measurement)
**Depends on:** Phase 1 — `engine/src/seer_engine/lab/control_draw.py` must exist and export the
matched-draw rule before this phase's file compiles.
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab/methods`

---

## Goal

After this phase `M0047` carries one `Amendment` (seq 1, 2026-10-19) with two arms,
`M0047-MV10-PLC` and `M0047-MV20-PLC`, recorded as dev trials. Each is the same book, the same
gate, the same screen, the same one-class-per-company rule and the same market-value weights
under the same ceiling as the arm it controls, filled with hash-drawn names whose **entry count
at every decision session is the real arm's own**. Two defects are repaired at once: the shape
(the old placebos re-drew quarterly behind a keep band and traded 0.55x as often as the books
they were quoted against) and the resolution (`control_shape.resolve_target` lands the old pair
on `M0047-EQ` by the `first-declared` guess; the new names make `sibling-stem` land them on
`M0047-MV10` and `M0047-MV20`, which is what they actually control).

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** nothing. `placebo_order` (`m0047_market_value_residual.py:189-202`), `SizeParams`
(`:99-140`), `MarketValueAllocator` (`:205-277`) and all six original candidates stay byte-identical.
Their recorded `config_digest`s must not move and this phase removes nothing that could move them.

**Renames:** none.

**Creates (all inside `engine/src/seer_engine/lab/methods/m0047_market_value_residual.py`):**
- `AMEND_1 = date(2026, 10, 19)` — module constant
- `_checkm(params) -> SizeParams` — a params guard that also refuses a non-placebo value
- `MatchedDrawAllocator` with `id = "M0047-A1"`, `market_fields = ("shares",)`
- `MATCHED = MatchedDrawAllocator()`
- `_a1(suffix, params, rationale, supersedes) -> Candidate` — candidate builder on `MATCHED`
- `MATCHED_DRAW_AMENDMENT` — the `Amendment` value
- candidate `M0047-MV10-PLC`
  (`SizeParams(RANKING, picks="placebo", weighting="size", cap=0.10, seed=1)`, declaring
  `supersedes=("M0047-PLC1-MV10",)`)
- candidate `M0047-MV20-PLC`
  (`SizeParams(RANKING, picks="placebo", weighting="size", cap=0.20, seed=1)`, declaring
  `supersedes=("M0047-PLC1-MV20",)`)
- one `method_amendments` row `(M0047, seq 1)` and two `trials` + `trial_funding` rows, written
  by `lab run M0047 --amend`
- `.workflows/plan/honest-control-redraw/phase-4-results.md` — the numbers Phase 8 collects

**Creates NO new params dataclass, and no `MATCHED_PREV_BARS`.** Reconciled 2026-10-19: the two
new arms reuse, byte for byte, the params **values** of the two arms they replace —
`SizeParams(RANKING, picks="placebo", weighting="size", cap=0.10, seed=1)` is `M0047-PLC1-MV10`'s
own value — and the new allocator id is the whole of the difference. `SizeParams` already carries
`inner`, `picks`, `weighting`, `cap` and `seed`, which is every input the matched allocator reads
(verified field by field against `m0047:104-108`), so a `MatchedParams` of its own would have been
a second way of saying the same thing in each of nine files. The previous-decision lookback slack
belongs to `control_draw.lookback_for` (`PREVIOUS_DECISION_BARS = 26`, measured by Phase 1 over
the whole dev calendar), not to a `46` guessed here.

**Signature changes:** **none.** The earlier draft widened `size_weights`'s annotation to
`SizeParams | MatchedParams`; with the params reused there is no second type and `size_weights`
(`:172`) is left byte-identical along with everything else above `:289`.

**New allocator id claimed lab-wide:** `M0047-A1`. Checked against
`test_allocator_ids_are_unique_across_methods` (`engine/tests/test_lab_methods.py:108`): no other
method uses a hyphenated `MNNNN-A<n>` id today. Phases 1, 3, 5, 6 and 7 are expected to claim
`M0227-A1`, `M0243-A1`, `M0221-A1`, `M0225-A2`, `M0201-A1`, `M0202-A1`, `M0208-A1`, `M0215-A1`
by the same convention (plan index, Decisions, "candidate and allocator naming"). No collision.

**Requires (from earlier phases):** Phase 1's `engine/src/seer_engine/lab/control_draw.py` and
Phase 1's `backtest.dev.Candidate.supersedes` field. Reconciled 2026-10-19 against Phase 1's
actual module; these are the real signatures, and the call sites in Step 3 already use them.

```python
def previous_decision_date(data_date: date, cadence: str = "monthly") -> date:
    """The ``data_date`` of the decision before the one being made at ``data_date``.

    Off the published NYSE calendar: takes no History, never returns None, and under a monthly
    cadence answers the last session strictly before the first calendar day of ``data_date``'s
    own month. ``test_lab_control_draw`` checks it against ``sim.rules.is_rank_session`` on every
    monthly decision of the dev window, 1996-2015. Look-ahead-free by construction.

    **It is the right clock for THIS chassis**, and the correction below is why: M0047's residual
    arms re-pick a fresh top twenty every month, so the previous monthly decision is exactly the
    churn the control has to match.
    """


def matched_partition(*, pool: Sequence[str], held: AbstractSet[str], keep_n: int, tag: str,
                      seed: int, data_date: date) -> tuple[list[str], list[str]]:
    """``(keep, tail)``: at most ``keep_n`` of ``held & pool`` in the DATE-FREE keep order, then
    every remaining pool name in take order -- the names the control does NOT hold first, in the
    month-keyed entry order, and the holdings it is dropping LAST. The caller truncates
    ``keep + tail`` to its own book size, exactly as ``m0047.placebo_order``'s result is
    truncated by ``one_per_company``. Ties broken by symbol, so the order is total.

    The tail ordering is a guarantee of the module: put the dropped holdings any earlier and the
    control takes one straight back into a free slot, the realised entry count falls below the
    number asked for, and the trade ratio sags under 1.00 with every size assertion still green.
    """


def churn(now: Sequence[str], prev: Sequence[str]) -> int:
    """``len(set(now) - set(prev))`` -- how many names the controlled arm entered."""
```

**Three differences from this phase's first draft, all mechanical and all applied below.** The
calendar helper is `previous_decision_date`, not `previous_rank_session`, and it returns a `date`
rather than `date | None`, so the `prev_date is not None` branch goes. The order helper is
`matched_partition`, which returns `(keep, tail)` rather than one flat list, and takes `tag` and
`keep_n` rather than `keeps`; the caller concatenates. And `MATCHED_PREV_BARS = 46` is replaced
by `control_draw.lookback_for`, so the lookback is `resid_lookback(RANKING) + 26 = 427`, not 447 —
still far inside the 473-bar smoke fixture, and now a number one module measured rather than nine
files each guessing.

**Leaves alone (owned by others):** `lab/control_draw.py` (Phase 1 — consumed unchanged, never
edited here), `lab/control_shape.py` and `lab/hardgate.py` and `commands/lab.py` (Phase 2),
`m0221`/`m0225` (Phase 3), `m0201`/`m0202` (Phase 5), `m0208` (Phase 6), `m0215` (Phase 7),
`lab stage` and `web/data/lab.json` and `lab/lab.sqlite`'s commit (Phase 8).

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/methods/m0047_market_value_residual.py` | modify | one docstring paragraph (`:46`), two import lines (`:62`), one constant (`:79`), the guard + allocator + builder + `Amendment` block (inserted at `:290`), one `amendments=` kwarg on `METHOD` (`:357`). **No annotation change and no new params dataclass** |
| `.workflows/plan/honest-control-redraw/phase-4-results.md` | create | the numbers in **What to record for phase 8**, filled in, in the set's one results-file convention |

One committed source file, plus the results file every phase in the set writes and Phase 8
collects. The shape verification (Step 6d) runs from a throwaway script in the scratchpad and is
**not** committed — see **Handoffs** for why a permanent regression test belongs with phase 1's
`engine/tests/test_lab_control_draw.py`.

---

## The measured state this phase starts from

Read-only from `lab/lab.sqlite` on 2026-10-19 (`trials` joined `trial_funding`, `window='dev'`).
SPY TR on the same deposits is **7.19%/yr** for every row.

| arm | trial | trades | turnover | `mwr` % | worst fall % |
|---|---|---|---|---|---|
| `M0047-EQ` | 719 | 1606 | 8.899 | 13.67 | 20.6 |
| `M0047-MV10` | 720 | 1600 | 9.345 | 11.15 | 20.0 |
| `M0047-MV20` | 721 | 1591 | 9.853 | 10.42 | 24.0 |
| `M0047-MV` | 722 | 1585 | 10.073 | 11.12 | 23.6 |
| `M0047-PLC1-MV10` | 723 | **881** | **4.415** | 9.87 | 22.9 |
| `M0047-PLC1-MV20` | 724 | **876** | **4.522** | 9.88 | 25.8 |

`lab control M0047` today:

```
M0047   M0047-PLC1-MV10   controls M0047-EQ   0.55 trades  0.50 turnover  refuse   (first-declared)
M0047   M0047-PLC1-MV20   controls M0047-EQ   0.55 trades  0.51 turnover  warn     (first-declared)
```

### The two defects, stated separately because they are independent

**(a) Shape.** `placebo_order` (`:189-202`) re-draws only when `data_date.month in REPICK_MONTHS`
(`(3, 6, 9, 12)`, `:83`) and otherwise keeps every holding still in the screen, filling only the
slots a holding vacated; at a re-draw it keeps everything inside `KEEP_PCT = 40` of the hash
order. The arms it controls do none of that: for `p.picks == "residual"` the allocator recomputes
`sorted(by_symbol, key=lambda s: (-scores[s], s))` and takes a fresh `one_per_company(order, 20)`
**at every monthly decision session** (`:244-248`), with no keep band and no quarterly gate. So
the control trades 0.55x as often, pays roughly half the fee bill, and the gap it was quoted for
is not evidence.

> **Correction to the brief — reconciled 2026-10-19 and now the set's authoritative reading.**
> The task brief, the analysis document and Phase 1's first draft all described M0047's real arms
> as "quarterly/banded". They are not. On this chassis that describes the **placebo only**. `REPICK_MONTHS` and `KEEP_PCT` appear nowhere
> except inside `placebo_order`; the residual arms are plain monthly re-picks. "The previous
> decision session" is therefore unambiguous here: the previous monthly rank session, which
> `sim.rules.is_rank_session(MONTHLY_HOLD_FRAC_GOTRADE, s)` defines as the first NYSE session of
> each calendar month (`sim/rules.py:390`, `_first_of`). No between-quarter band fill exists on
> the arm being matched. The quarterly band is the handicap being removed, not a property to
> reproduce. So this phase calls `control_draw.previous_decision_date`, the monthly helper, and
> that is correct.
>
> **The one chassis in the set where that is not true is M0201/M0202's.** Their shared `_run`
> passes an empty `frac` on every non-`REPICK_MONTHS` month, so the basket really does move only
> quarterly, behind M0197's 40% keep band, and Phase 5 derives its own previous re-pick rather
> than calling the monthly helper. Phase 1's `previous_decision_date` docstring carries the
> split. Do not generalise either half.
>
> Step 6d verifies this phase's claim session by session against the real store before anything
> is committed.

**(b) Resolution.** `resolve_target` (`control_shape.py:359-385`) walks `declared` ->
`sibling-stem` -> `declared-idea` -> `first-declared`. `Candidate` has no `controls` field
(`backtest/dev.py`; fields are `id, family, rules, allocator, params, rationale, added,
owner_inputs`), so `declared` never fires. The stem of `M0047-PLC1-MV10` is `M0047-PLC1`, which
names no arm. No eligible arm's rationale opens "the idea:" or "the yardstick:"
(`IDEA_MARKERS`). So both land on `first-declared` = the first eligible arm = `M0047-EQ`. But
these are **size-weighted** placebos: their true targets are `M0047-MV10` and `M0047-MV20`.

The quoted margin depends on which:

| comparison | margin, `mwr` pts/yr |
|---|---|
| `MV10` 11.15 − `PLC1-MV10` 9.87 (**true target**) | **+1.28** |
| `EQ` 13.67 − `PLC1-MV10` 9.87 (what the ladder reports) | +3.80 |
| `MV20` 10.42 − `PLC1-MV20` 9.88 (**true target**) | **+0.54** |
| `EQ` 13.67 − `PLC1-MV20` 9.88 (what the ladder reports) | +3.79 |

M0047's own success condition says the method must "beat its own size-weighted placebo by at
least 2 points a year" (`:320-321`). Against the wrong arm it reads as a comfortable pass;
against the true target it already **fails on both arms**, before any shape repair. That is a
finding this phase must report whatever the re-draw produces (R3).

---

## Implementation Steps

### Step 1: Add the imports and the amendment date

**File:** `engine/src/seer_engine/lab/methods/m0047_market_value_residual.py:62` and `:79`

**Change:** `Amendment` joins the `lab.method` import; `control_draw` is imported above it
(isort: `seer_engine.lab.control_draw` sorts before `seer_engine.lab.method`). Add the amendment
date beside `ADDED`.

Replace line 62:

```python
from seer_engine.lab.method import Method
```

with:

```python
from seer_engine.lab import control_draw
from seer_engine.lab.method import Amendment, Method
```

(the module, not its members: three names are used and `control_draw.` at each call site is what
tells a reader of the method file that the rule lives in one shared place)

Replace line 79:

```python
ADDED = date(2026, 10, 18)
```

with:

```python
ADDED = date(2026, 10, 18)
AMEND_1 = date(2026, 10, 19)
```

**Impact:** none on any digest. `config_text` is `rules` + `allocator.id` + `params`
(`lab/method.py:44-52`); imports are not in it. The file's sha256 changes, which is exactly what
an amendment is allowed to do — `runner.preflight(amend=True)` does not compare the file's sha to
anything, and `test_lab_methods.py`'s sha freeze falls back to `runner.pending_amendment` for a
committed-but-unrun block.

---

### Step 2: *(withdrawn in reconciliation — nothing to widen)*

The first draft of this phase minted a `MatchedParams` dataclass and therefore had to widen
`size_weights`'s annotation to `SizeParams | MatchedParams`. The reconciled rule reuses
`SizeParams` itself, so **`size_weights` (`:172`) is left byte-identical** along with everything
else above `:289`, and this step is empty. It is kept as a numbered placeholder so the step
numbers below still match the commit sequence a reader of the commits will see.

The reason the reuse works is worth one line: `size_weights` reads only `p.weighting` and
`p.cap`, and the new arms' params *are* `SizeParams`, so the real arms and the matched control
are weighted by the same function with the same values and the only difference between the two
books is which names fill the slots.

---

### Step 3: The churn-matched allocator (no new params dataclass)

**File:** `engine/src/seer_engine/lab/methods/m0047_market_value_residual.py` — inserted between
line 289 (the closing paren of `_v`) and line 292 (`METHOD = Method(`).

**Change:** a new allocator class with a new `id`, and nothing else. The params are the two
replaced arms' own values, reused byte for byte. Both safety arguments must be stated:

- **`config_digest` safety.** `registry._canon` renders a dataclass by `dataclasses.fields()`,
  **not** by its hand-written `as_dict()` (`backtest/registry.py:323-332`). Adding any
  `compare=True` field to `SizeParams` — even one defaulted, even one local to this file — would
  rewrite `SizeParams(...)` in every recorded M0047 trial's `config_text` and move all six
  digests. Adding a `compare=False` field would leave the digests alone but make the new arm's
  rendered configuration **identical** to the old one's. **Reusing the old arm's params value
  under a new allocator id does neither**: `SizeParams` is not touched at all, so no recorded
  digest can move, and `config_text`'s `allocator=` line carries `<M0047-A1>` where the recorded
  arm carries `<M0047>`, so the text is new.
- **`Method.__post_init__` uniqueness.** It walks the originals and then each amendment through
  one shared `ids` set and one shared `digests` set (`lab/method.py:216-240`) and refuses a
  repeated id **or** a repeated configuration. `M0047-MV10-PLC` and `M0047-MV20-PLC` are new ids.
  Their configurations are `rules=<monthly-hold-frac-gotrade>` + `allocator=<M0047-A1>` +
  `params=SizeParams(inner=...,picks='placebo',weighting='size',cap=0.1,seed=1)`; every recorded
  M0047 arm carries `allocator=<M0047>`, so the `allocator=` line alone separates the new pair
  from the recorded six — including from `M0047-PLC1-MV10` and `-MV20`, whose params they share
  exactly. The two new arms differ from each other in `cap` (0.10 vs 0.20), so they differ from
  each other too. **Step 6b checks all eight digests are distinct rather than arguing it.**
- **Why reuse rather than mint.** `SizeParams` already carries `inner`, `picks`, `weighting`,
  `cap` and `seed` (`m0047:104-108`), which is every input this allocator reads, so a new
  dataclass would hold nothing new. And `picks="placebo"` is the honest value: the config text is
  the public record of what an arm did, and a blind book must not describe itself as a ranked
  one. `_checkm` enforces it.

**Code** (complete, inserted verbatim):

```python
# --------------------------------------------------------------------------- amendment 1 (2026-10-19)
#
# The churn-matched placebo. Everything below is new; nothing above it moved, so every recorded
# config_digest of the six originals is byte-identical to the one its trial holds.
#
# The params are the replaced arms' own values, reused: SizeParams already carries inner, picks,
# weighting, cap and seed, which is everything this allocator reads, so a dataclass of its own
# would hold nothing new and would be a second way of saying the same thing in each of nine
# method files. A field added to SizeParams would move all six recorded M0047 digests
# (registry._canon renders a dataclass by dataclasses.fields(), not by as_dict), and a
# compare=False field would make the new arm's configuration identical to the old one's, which
# Method.__post_init__ refuses. The new allocator id is the whole of the difference, and the
# allocator= line of config_text is enough to make it a configuration the lab has not run.


def _checkm(params: object) -> SizeParams:
    """``SizeParams``, plus the one thing a control's params may not say.

    The matched draw differs from ``PLC1-MV10`` in its allocator id and in nothing else, so the
    params must still read ``picks="placebo"``. Saying ``"residual"`` would record a configuration
    whose text claims the residual ranking this allocator never performs on its own names -- it
    recomputes that ranking to count the real book's entries, and then draws blind.
    """
    if not isinstance(params, SizeParams):
        raise TypeError(f"params must be SizeParams, got {type(params).__name__}")
    if params.picks != "placebo":
        raise ValueError(
            f"the matched draw is a control: picks must be 'placebo', got {params.picks!r}"
        )
    if params.seed == 0:
        raise ValueError("seed 0 belongs to the real book; a placebo draws on a non-zero seed")
    return params


class MatchedDrawAllocator:
    """M0047's book with none of its identity: hash-drawn names, the real book's own churn.

    Same SPY 200-day gate, same F4 screen, same scorable pool, same one class per company, same
    point-in-time market-value weights under the same ceiling as ``MarketValueAllocator``. The
    one difference is which names fill the slots, and that is the placebo's whole content.

    **Why the draw it replaces was not honest.** ``placebo_order`` re-drew on the first session of
    March, June, September and December and otherwise kept everything still in the screen. The
    arms it was quoted against re-pick a fresh top twenty every single month. Measured: 881 trades
    against 1600 (0.55x) and 4.415 turnover against 9.345 (0.50x), outside D17's refuse band. Half
    the fee bill is not the same book, so the gap it reported was not evidence. The author of that
    draw chose a re-draw period by hand; M0243's author saw the same failure on another chassis,
    corrected by hand in the other direction, and overshot to 3.01x. Choosing the period by hand
    is the error, in both signs.

    **What this one does instead.** At every decision session it recomputes the controlled arm's
    own selection twice -- at this session and at the previous decision session -- and counts the
    names the real book would have entered. It then keeps exactly ``size - entries`` of its own
    holdings, in a date-free hash order so the keep set is stable, and draws the rest from the
    same scorable pool in a hash order keyed on this month. The entry count matches by
    construction rather than by luck, so the fee bill matches, so the gap is signal.

    **The previous decision session is a calendar fact, not a bar.** ``monthly-hold-frac-gotrade``
    lets the basket move on the first NYSE session of each calendar month
    (``sim.rules.is_rank_session`` -> ``_first_of``), and ``control_draw.previous_decision_date``
    walks the NYSE calendar to it without reading a single price. Nothing about it can look ahead.
    The extra bars the second scoring pass reaches back for cost
    ``control_draw.PREVIOUS_DECISION_BARS`` (26) of lookback.

    **And the monthly clock is the right one for THIS chassis, which the brief got wrong.**
    ``REPICK_MONTHS`` and ``KEEP_PCT`` appear in this file only inside ``placebo_order``
    (:189-202); the residual arms take a fresh ``one_per_company(order, 20)`` at every monthly
    decision (:244-248). The quarterly band is the handicap being removed, not a property to
    reproduce. (M0201's and M0202's shared chassis is genuinely quarterly and derives its own
    previous re-pick in its own files -- that is Phase 5's, and it is the only place in the set
    where the monthly helper is the wrong answer.)

    **One assumption, written before the run.** The member set is point-in-time and the allocator
    is handed only *this* session's. Recomputing the real book at the previous session therefore
    screens the previous date's bars against today's members, so a name that joined the index this
    month and would have entered the real book is counted as already present, and the entry count
    comes out at most a name or two low. The bias is one-signed and toward stickiness, so it can
    only push the measured trade ratio **below** 1.00 -- it cannot manufacture a match. If the
    ratio lands inside the match band, the assumption did no harm; if it lands under 0.80, this is
    the first thing to look at. The real arms' own recorded trials used the true point-in-time
    members, so the comparison is honest in the direction that matters.

    Market-aware exactly as ``MarketValueAllocator`` is (``market_fields = ("shares",)``): no
    share counts, no targets, so ``lab run`` refuses this on a store without company size and the
    history-only contract kit sees an empty book.
    """

    id = "M0047-A1"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        return control_draw.lookback_for(resid_lookback(_checkm(params).inner))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _checkm(params).inner
        return tuple(sorted({p.market, *FACTOR_SYMBOLS(p.inner)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _checkm(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _checkm(params)
        return True

    def _real_book(self, prepared: SizePrepared, members: AbstractSet[str], data_date: date,
                   p: SizeParams) -> tuple[tuple[str, ...], dict[str, FactorRow]]:
        """The controlled arm's own names on ``data_date``, and the pool they were picked from.

        Byte-for-byte ``MarketValueAllocator._run``'s residual path up to ``chosen``: the same
        gate, the same screen, the same scores, the same one-class rule. Empty when the gate is
        off, which is how the control sits in cash on exactly the days the real book does.
        """
        resid = prepared.resid
        if not trend_on(resid.history, data_date, p.inner.inner):
            return (), {}
        rows = resid.factor.rows_on(members, data_date, p.inner.inner)
        if not rows:
            return (), {}
        grid = resid.grid(p.inner.market)
        if grid is None:
            return (), {}
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, p.inner)
        by_symbol = {r.symbol: r for r in rows if r.symbol in scores and r.symbol not in EXCLUDED}
        order = sorted(by_symbol, key=lambda s: (-scores[s], s))
        return tuple(one_per_company(order, p.inner.inner.top)), by_symbol

    def _run(self, prepared: SizePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SizeParams) -> tuple[Target, ...]:
        market = prepared.market
        if market is None or len(market.shares) == 0:  # no company size: target nothing
            return ()
        now, by_symbol = self._real_book(prepared, members, data_date, p)
        if not now:
            return ()
        before, _ = self._real_book(
            prepared, members, control_draw.previous_decision_date(data_date), p
        )
        size = len(now)
        keep, tail = control_draw.matched_partition(
            pool=sorted(by_symbol), held=held,
            keep_n=max(size - control_draw.churn(now, before), 0),
            tag="M0047", seed=p.seed, data_date=data_date,
        )
        chosen = one_per_company(keep + tail, size)
        top = p.inner.inner.top
        sizes = [market.market_value(s, data_date) for s in chosen]
        out: list[Target] = []
        for s, w in zip(chosen, size_weights(sizes, top, p), strict=True):
            if w is None:
                continue
            t = target_from_close(s, by_symbol[s].close, w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no targets."""
        p = _checkm(params)
        return self._run(self.prepare(history), members, data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> SizePrepared:
        return SizePrepared(ResidPrepared(history, prepare_factor(history)), None)

    def prepare_market(self, market: Any) -> SizePrepared:
        if not isinstance(market, Market):
            raise TypeError(f"market must be a Market, got {type(market).__name__}")
        return SizePrepared(ResidPrepared(market.history, prepare_factor(market.history)), market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SizePrepared):
            raise TypeError(f"prepared must be SizePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _checkm(params))


MATCHED = MatchedDrawAllocator()


def _a1(suffix: str, params: SizeParams, rationale: str,
        supersedes: tuple[str, ...]) -> Candidate:
    """An amendment candidate, with the declaration of which recorded arm it replaces.

    ``supersedes`` is what D17 reads (``control_shape.SUPERSEDES_ATTR``); it is declared, never
    inferred, and it is outside ``config_digest`` because ``config_text`` names its three
    attributes by hand. It matters more here than anywhere: these two arms are deliberately
    re-pointed at their TRUE targets, so the old arms' ``target_id`` (``M0047-EQ``) and the new
    ones' (``M0047-MV10`` / ``-MV20``) differ, and a rule that matched targets would retire
    nothing at all."""
    return Candidate(id=f"M0047-{suffix}", family="M0047", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MATCHED, params=params, rationale=rationale, added=AMEND_1,
                     owner_inputs=(), supersedes=supersedes)
```

**Impact:**
- Claims the allocator id `M0047-A1` lab-wide.
- `lookback` is `control_draw.lookback_for(401)` = 401 + 26 = **427**, inside the 473-bar cap
  (plan invariant 11). The slack is `control_draw.PREVIOUS_DECISION_BARS`, measured by Phase 1
  against every monthly decision of the dev window rather than estimated per file.
- **`one_per_company(keep + tail, size)` is where the tail ordering earns its keep.** The
  concatenation is truncated to `size`, so a dropped holding sorted ahead of a fresh name would
  be taken straight back into a free slot and the realised entry count would fall below the real
  book's. `matched_partition` guarantees fresh-before-dropped; this phase relies on it and does
  not re-implement it.
- `test_allocator_contract` drives only `prepare(history)`, so this market-aware allocator targets
  nothing there and the kit's `nonempty == 0` assertion for market-aware allocators holds — the
  same way `MarketValueAllocator` already satisfies it.
- Nothing above line 289 changed except the three edits in Steps 1 and 2, none of which feed
  `_canon`.

---

### Step 4: The `Amendment` block and the `METHOD` wiring

**File:** `engine/src/seer_engine/lab/methods/m0047_market_value_residual.py` — immediately after
the `_a1` builder from Step 3 and before `METHOD = Method(` (line 292 as the file stands).

**Change:** the pre-registration. Every word of `why`, `hypothesis` and `expected_failure` is
written now and frozen by the commit that precedes the run.

Marker discipline, checked phrase by phrase before committing:
- Both rationales contain **"Placebo"** and **"hash order"** — two of
  `control_shape.DRAW_MARKERS` — so `kind_of` returns `KIND_PLACEBO` and the arms **are**
  shape-checked. That is the point: the arms must stay inside D17's reach.
- Neither rationale (nor `why`, `hypothesis` or `expected_failure`, which `kind_of` never reads,
  but keep them clean anyway) contains any of `DOSE_MARKERS`: `"dose-response"`, `"dose:"`,
  `"and not since"`, `"and none since"`, `"does the date do any work"`, `"on the date itself"`.
  Dressing a control as a dose-response arm would make `kind_of` return `KIND_DOSE`, skip the
  shape check entirely and report `not-checked`. That is gaming the gate and it is forbidden
  (plan invariant 3).
- Neither rationale contains `"within-frame control"` (`ABLATION_MARKERS`), which is tested after
  the draw markers and would never be reached anyway.

**Code** (complete):

```python
MATCHED_DRAW_AMENDMENT = Amendment(
    added=AMEND_1,
    why=(
        "The two size-weighted placebos traded about half as often as the books they control and "
        "were being read against the wrong arm; re-draw them churn-matched and name them after "
        "their true targets"
    ),
    hypothesis=(
        "Written before any result. Two independent defects sit on the same pair of arms and this "
        "block repairs both. FIRST, SHAPE. PLC1-MV10 and PLC1-MV20 are re-drawn only in March, "
        "June, September and December and otherwise keep whatever is still in the screen, while "
        "MV10 and MV20 re-pick a fresh top twenty every month. Measured: 881 and 876 trades "
        "against 1600 and 1591, 0.55x, and turnover 4.415 and 4.522 against 9.345 and 9.853, "
        "0.50x and 0.51x -- outside the 0.50-2.00 band the lab refuses a control at. MV10-PLC and "
        "MV20-PLC take their entry count each month from the arm they control instead of from a "
        "re-draw month chosen by hand, so they trade about 1.8x as often as the arms they replace "
        "and pay a fee bill the size of MV10's and MV20's. SECOND, RESOLUTION. The stem "
        "'M0047-PLC1' names no arm, so the ladder falls through to its weakest rung and reports "
        "both placebos against M0047-EQ, the equal-weight arm -- but these are size-weighted "
        "books and their true opponents are MV10 and MV20. The names MV10-PLC and MV20-PLC make "
        "the sibling-stem rung resolve each one onto the book it actually controls. "
        "PRE-REGISTERED DIRECTION. A hash order carries no information, so the extra trading buys "
        "nothing and costs Gotrade's fees: each re-drawn control earns LESS than the arm it "
        "replaces (under 9.87% and under 9.88% money-weighted), and each book's lead over its own "
        "honest placebo therefore WIDENS. Against the true targets the standing leads are MV10 "
        "11.15 - 9.87 = +1.28 points a year and MV20 10.42 - 9.88 = +0.54; the prediction is that "
        "both grow, MV10's to somewhere between +1.3 and +3.0 and MV20's to between +0.6 and "
        "+2.5. Both re-drawn arms should land inside 0.80-1.25 on trades and on turnover against "
        "their own targets. The SPY 200-day gate is in both books and is worth a constant 3.6 "
        "points a year to either, so it nets out of every number here. The re-stated verdict on "
        "M0047's own success clause -- 'beats its own size-weighted placebo by at least 2 points "
        "a year' -- is reported against the true target whatever it says: against EQ it looked "
        "like +3.80 and a comfortable pass, against MV10 it is +1.28 and already a failure before "
        "this amendment runs a single session."
    ),
    expected_failure=(
        "The direction can come out backwards and the measurement is what decides. The quarterly "
        "keep band held names that kept passing the screen quarter after quarter, which is a "
        "quiet survivor tilt the honest monthly draw throws away; if that tilt was worth more "
        "than the fees it saved, MV10-PLC and MV20-PLC earn MORE than 9.87% and 9.88%, both leads "
        "narrow instead of widening, and M0047's two-point clause fails by a wider margin. The "
        "lead can even go negative, as M0221's and M0225's blind draws already do on their own "
        "books; that is the finding and it is reported, never re-drawn away. The shape can also "
        "miss: the control is matched on entries, and exits follow entries only while its own "
        "holdings stay inside the screen -- when a drawn name leaves the pool the control must "
        "replace it whether or not the real book entered anyone, which pushes the trade ratio "
        "above 1.00; the opposite push comes from reading the previous session's book against "
        "this session's member set, which can hide an index joiner and pull the ratio under 1.00. "
        "If either arm lands outside 0.80-1.25 the result is recorded and the phase stops; a "
        "second draw is admissible only for a missed shape and never for a disliked margin "
        "(design section 4). Finally, market value is unknown for many picks before about 2000 "
        "and both books fall back to the median known size there, so the early years of the "
        "comparison are close to equal weight on both sides and the real test lives in 2001-2015."
    ),
    candidates=(
        _a1("MV10-PLC",
            SizeParams(RANKING, picks="placebo", weighting="size", cap=0.10, seed=1),
            "Placebo for MV10: names in a hash order over the same scorable set, entering as "
            "often as MV10 itself enters, sized by market value, 10% ceiling",
            supersedes=("M0047-PLC1-MV10",)),
        _a1("MV20-PLC",
            SizeParams(RANKING, picks="placebo", weighting="size", cap=0.20, seed=1),
            "Placebo for MV20: the same hash order and the same matched churn, sized by market "
            "value, 20% ceiling",
            supersedes=("M0047-PLC1-MV20",)),
    ),
)
```

Then add the `amendments` kwarg to `METHOD`. Replace the current tail (lines 354-358):

```python
    seen_keys=(
        "concept:market-value-weighted-momentum-book",
        "concept:size-weighted-placebo-control",
    ),
)
```

with:

```python
    seen_keys=(
        "concept:market-value-weighted-momentum-book",
        "concept:size-weighted-placebo-control",
    ),
    amendments=(MATCHED_DRAW_AMENDMENT,),
)
```

**Impact:** `METHOD.all_candidates()` becomes eight arms. `seen_keys` and the original
`candidates` tuple are untouched. `Method.__post_init__` now validates the amendment batch
against the originals' id and digest sets and must pass (Step 6 proves it).

---

### Step 5: Add the amendment paragraph to the module docstring

**File:** `engine/src/seer_engine/lab/methods/m0047_market_value_residual.py:46` — a new paragraph
inserted after the "Market-aware" paragraph and before the closing `"""` on line 47.

**Change:**

```
Amendment 1 (2026-10-19). The two size-weighted placebos above were re-drawn only in March, June,
September and December and otherwise kept whatever was still in the screen, so they traded 881
and 876 times against the 1600 and 1591 of the books they were quoted against -- 0.55x, with half
the fee bill, which is not the same book. MV10-PLC and MV20-PLC replace a re-draw period chosen by
hand with the churn of the arm each one controls: at every monthly decision the control recomputes
the real book at this session and at the previous one, counts the names it would have entered, and
replaces exactly that many of its own. Their names also repair a second thing. The stem
"M0047-PLC1" names no arm, so the control-shape ladder fell through to its weakest rung and read
both placebos against M0047-EQ -- the equal-weight arm -- when these are size-weighted books whose
opponents are MV10 and MV20. Against EQ the quoted lead was +3.80 points a year; against the true
target it is +1.28. Both numbers belong in any sentence written about this method. The originals
stay recorded and are not withdrawn: a trial is a measurement and the lab keeps its measurements.
```

**Impact:** prose only. The sha changes, which Step 1's note already covers.

---

### Step 6: Prove the tree and the shape before committing anything

**File:** none — commands only. Nothing here writes to the lab database.

**6a. Lint and the digest freeze.**

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
/home/miftah/seer/engine/.venv/bin/ruff check engine
PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src \
  /home/miftah/seer/engine/.venv/bin/pytest engine/tests/test_lab_methods.py -q
```

`test_every_recorded_configuration_still_digests_to_its_recorded_digest` is the one that must be
green: it is the proof that Steps 1-5 moved no recorded digest.

**6b. The digest argument, checked rather than asserted.**

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python - <<'PY'
from seer_engine.lab.method import config_digest, config_text
from seer_engine.lab.methods.m0047_market_value_residual import METHOD
seen = {}
for c in METHOD.all_candidates():
    d = config_digest(c)
    assert d not in seen, f"{c.id} repeats {seen[d]}"
    seen[d] = c.id
    print(f"{c.id:20s} {d[:16]}  allocator={c.allocator.id}")
print()
print(config_text(METHOD.all_candidates()[-1]))
PY
```

Expected: eight distinct digests; the six originals print `allocator=M0047`, the two new ones
`allocator=M0047-A1`; the six originals' digests must equal the ones recorded in `trials` (6a
already proves this, this just shows them).

**6c. The resolution walk, both new ids.**

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python - <<'PY'
from seer_engine.lab import control_shape as cs
from seer_engine.lab.methods.m0047_market_value_residual import METHOD
arms = METHOD.all_candidates()
for a in arms:
    print(f"{a.id:20s} kind={cs.kind_of(a)!r:12s} target={cs.resolve_target(a, arms)}")
PY
```

Expected, and this is the acceptance criterion for defect (b):

```
M0047-EQ             kind=''          target=('M0047-MV10', 'sibling-stem')   <- not a control; irrelevant
M0047-MV10           kind=''          target=(...)                            <- not a control; irrelevant
M0047-MV20           kind=''          target=(...)
M0047-MV             kind=''          target=(...)
M0047-PLC1-MV10      kind='placebo'   target=('M0047-EQ', 'first-declared')
M0047-PLC1-MV20      kind='placebo'   target=('M0047-EQ', 'first-declared')
M0047-MV10-PLC       kind='placebo'   target=('M0047-MV10', 'sibling-stem')
M0047-MV20-PLC       kind='placebo'   target=('M0047-MV20', 'sibling-stem')
```

The three things this must show, each of which the walk establishes:

1. `kind_of(M0047-MV10-PLC) == 'placebo'` and the same for `MV20-PLC`. Their rationales open
   "Placebo for MV…" and carry "hash order"; neither carries a dose marker. If either came back
   `'dose-response'` or `''` the arm would escape the shape check and the commit must not happen.
2. `resolve_target` returns `('M0047-MV10', 'sibling-stem')` and `('M0047-MV20', 'sibling-stem')`.
   The stem of `M0047-MV10-PLC` is `M0047-MV10` (`rsplit("-", 1)[0]`), which names a real arm,
   and `_eligible_targets` keeps it because **`M0047-MV10` is not itself a placebo or a dose
   arm** — its rationale is "Sized by real market value, no name above 10% (twice an equal
   slot)", which matches no `DRAW_MARKERS`, no `DOSE_MARKERS` and no `ABLATION_MARKERS`, so
   `kind_of` is `KIND_NONE`. Same for `M0047-MV20`: "Sized by real market value, no name above
   20% (four times an equal slot)". `sibling-stem` is the strongest rung the ladder can reach
   without a `controls` attribute, and `Candidate` has no such field.
3. The two **old** arms' resolution is unchanged: still `('M0047-EQ', 'first-declared')`. The new
   arms are placebos, so `_eligible_targets` excludes them and the `first-declared` fallback still
   picks `M0047-EQ`, which remains the first eligible arm in declaration order. Adding this
   amendment must not silently restate an already-published number for a different arm.

**6d. The shape proof — the entry count, session by session, on the real store.**

This is the verification the care point asks for, and it costs no lab write, no trial and no
method id. It is run **before** the commit, from the scratchpad, read-only against the research
store. Write it to
`/tmp/claude-1000/-home-miftah-seer/<session>/scratchpad/m0047_churn_probe.py`:

```python
"""Does MV10-PLC enter exactly as many names as MV10, at every decision session?

Read-only. Loads the dev research store, walks every monthly rank session of the dev window, and
compares the real book's entries with the matched control's, rolling the control's own holdings
forward the way the book engine does. Prints a per-year table and the totals. Writes nothing.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

from seer_engine import dates, research
from seer_engine.lab.methods.m0047_market_value_residual import (
    MATCHED,
    MARKETVALUE,
    RANKING,
    SizeParams,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, is_rank_session

STORE = Path("/home/miftah/seer/engine/.research")

data = research.load_store(STORE)
market = data.market
real_p = SizeParams(RANKING, picks="residual", weighting="size", cap=0.10)
ctrl_p = SizeParams(RANKING, picks="placebo", weighting="size", cap=0.10, seed=1)
real_prepared = MARKETVALUE.prepare_market(market)
ctrl_prepared = MATCHED.prepare_market(market)

# History has no first_date(); its `dates` is a datetime64[D] array, ascending. Start the walk
# once the ranking's own window is warm (427 = resid_lookback 401 + control_draw's measured
# PREVIOUS_DECISION_BARS 26), so an empty early book never reads as a matched zero.
spy_days = market.history["SPY"].dates
all_sessions = dates.sessions(spy_days[0].item(), date(2015, 10, 16))
sessions = [s for s in all_sessions[427:]
            if is_rank_session(MONTHLY_HOLD_FRAC_GOTRADE, s)]

real_held: frozenset[str] = frozenset()
ctrl_held: frozenset[str] = frozenset()
per_year: Counter[tuple[int, str]] = Counter()
mismatch = 0
rows = 0
for s in sessions:
    members = market.members_on(s)
    real = {t.symbol for t in MARKETVALUE.targets_prepared(real_prepared, members, s, real_held, real_p)}
    ctrl = {t.symbol for t in MATCHED.targets_prepared(ctrl_prepared, members, s, ctrl_held, ctrl_p)}
    re_, ce = len(real - real_held), len(ctrl - ctrl_held)
    rx, cx = len(real_held - real), len(ctrl_held - ctrl)
    per_year[(s.year, "real_in")] += re_
    per_year[(s.year, "ctrl_in")] += ce
    per_year[(s.year, "real_out")] += rx
    per_year[(s.year, "ctrl_out")] += cx
    rows += 1
    if re_ != ce:
        mismatch += 1
        if mismatch <= 25:
            print(f"  mismatch {s}: real in {re_} out {rx} n {len(real)} | "
                  f"ctrl in {ce} out {cx} n {len(ctrl)}")
    real_held, ctrl_held = frozenset(real), frozenset(ctrl)

ri = sum(v for (_, k), v in per_year.items() if k == "real_in")
ci = sum(v for (_, k), v in per_year.items() if k == "ctrl_in")
ro = sum(v for (_, k), v in per_year.items() if k == "real_out")
co = sum(v for (_, k), v in per_year.items() if k == "ctrl_out")
print(f"\nsessions {rows}   entry-count mismatches {mismatch} ({mismatch / rows:.1%})")
print(f"entries  real {ri}  control {ci}   ratio {ci / ri:.3f}")
print(f"exits    real {ro}  control {co}   ratio {co / ro:.3f}")
print("\nyear  real_in ctrl_in real_out ctrl_out")
for y in sorted({y for y, _ in per_year}):
    print(f"{y}  {per_year[(y,'real_in')]:7d} {per_year[(y,'ctrl_in')]:7d} "
          f"{per_year[(y,'real_out')]:8d} {per_year[(y,'ctrl_out')]:8d}")
```

Run it:

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src \
/home/miftah/seer/engine/.venv/bin/python \
  "$SCRATCH/m0047_churn_probe.py" > "$SCRATCH/m0047_churn_probe.out" 2>&1
echo "exit=$?"
cat "$SCRATCH/m0047_churn_probe.out"
```

**What makes it the right check, and what to do with the answer.** The real arm's realized entry
count at session `s` is `|book(s) \ book(prev)|` where `prev` is the previous session the
allocator was called on — and on this chassis the allocator is called on, and only on, the first
NYSE session of each month, because `MONTHLY_HOLD_FRAC_GOTRADE` has `cadence="monthly"` and no
`resize_cadence` (`sim/rules.py:261, 237`; `is_decision_session` collapses to `is_rank_session`
without a resize cadence). The probe iterates exactly that set with `is_rank_session`, so
"previous decision session" in the allocator and "previous iteration" in the probe are the same
date by construction, and any disagreement is a real defect rather than a calendar artifact. The
probe also rolls the control's `held` forward from its own targets, which is what the book engine
does, so the keep set it sees is the one the backtest will see.

- `entry-count mismatches` near 0% and `entries ratio` within a couple of percent of 1.000: the
  rule is matched by construction and the run may proceed.
- A ratio under 1.00 by more than ~3%: suspect the point-in-time member assumption documented in
  the allocator docstring. Record it; it biases toward stickiness, which is the defect being
  repaired, so a 0.97 is a weaker repair and not a wrong one.
- A ratio over 1.05: the control's own drawn names are leaving the scorable pool faster than the
  real book's picks do. Record it. Proceed only if the projected trade ratio still lands inside
  0.80-1.25; a projection outside the band means **stop before committing**, because the
  pre-registration would then be predicting a shape it cannot deliver.

The probe is deliberately not a committed test: the smoke fixture carries no `ShareCounts`
(`engine/tests/labkit.py:49-54` builds a `Market` with no `shares`), so a market-value allocator
targets nothing on it and a fixture-based assertion would prove nothing about this chassis. See
**Handoffs**.

---

### Step 7: Commit the pre-registration, then run it

**File:** none — commands only. This is the step that writes to the shared lab database.

The checkout is shared with eight other phases, so every git operation names its path and nothing
is staged (memory `seer-swarm-shared-worktree`). No `git add -A`, no `git reset`, no
`git pull --rebase` while the batch runs.

**7a. Record the database's hash before touching it.**

```bash
git -C /home/miftah/seer hash-object lab/lab.sqlite
```

Record the value. The analysis recorded `3969f1fa5d2066a42ed47716dd05a66050073592` on 2026-10-19
before any phase ran; a different value here just means a sibling phase landed first, which is
expected and fine.

**7b. Commit the method file by pathspec, and only it.**

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
git commit -m "lab: M0047 amendment 1 pre-registered -- the size-weighted placebos, churn-matched and renamed

The two size-weighted placebos traded 0.55x as often as the books they control (881 and 876
trades against 1600 and 1591) because they were re-drawn only in March, June, September and
December behind a 40% keep band, while MV10 and MV20 re-pick a fresh top twenty every month. Half
the fee bill is not the same book. MV10-PLC and MV20-PLC take their entry count each month from
the arm they control.

The names fix a second thing: the stem M0047-PLC1 names no arm, so the control-shape ladder read
both size-weighted placebos against M0047-EQ, the equal-weight arm. Against EQ the quoted lead was
+3.80 points a year; against the true target MV10 it is +1.28. The new names resolve on
sibling-stem, the strongest rung.

New allocator id M0047-A1 over the two replaced arms' own SizeParams values, reused byte for
byte: SizeParams may not gain a field, because registry._canon renders a dataclass by fields()
and every recorded M0047 digest would move, and a new dataclass would buy nothing SizeParams
does not already carry. The allocator= line of config_text is the whole of the difference.

Each new arm declares the recorded arm it supersedes (Candidate.supersedes, outside
config_digest). It matters here more than anywhere: the old pair resolves to M0047-EQ and the
new pair to M0047-MV10 and -MV20, so a supersession rule that matched targets would retire
neither and M0047 would stay blocked after the measurement.

Pre-registration only. No result has been seen.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  -- engine/src/seer_engine/lab/methods/m0047_market_value_residual.py
```

**7c. Prove the file is clean and tracked**, which is what `registry_problem` will check with
`cwd` set to the file's own directory (`backtest_dev.py:486-515`; it inspects **one** file, which
is why nine sessions can run in one checkout):

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw/engine/src/seer_engine/lab/methods
git status --porcelain -- m0047_market_value_residual.py   # must print nothing
git ls-files --error-unmatch m0047_market_value_residual.py
```

**7d. Run the amendment.** Never judge a `lab` command through a pipe — redirect, then read `$?`
directly (memory `seer-lab-note-double-append-from-grep-exit-code`).

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab run M0047 --amend \
  > "$SCRATCH/m0047_amend.log" 2>&1
echo "exit=$?"
cat "$SCRATCH/m0047_amend.log"
```

Exit 0 is ok, 2 is the lab refusing the request (read the message — it is not an error), 1 is an
error. `lab test` is never invoked and `SEER_RESEARCH_TEST_STORE` is never set: the test-window
look count stays at 4.

**7e. Record the database's hash after the run.** It must differ — the run appended one
`method_amendments` row and two `trials` + `trial_funding` rows.

```bash
git -C /home/miftah/seer hash-object lab/lab.sqlite
```

Do **not** commit `lab/lab.sqlite` and do **not** run `lab stage`. Phase 8 owns both (plan
invariant 8).

**Impact:** `M0047` gains `method_amendments` seq 1 and two dev trials. `methods.source_sha` is
not moved (its trigger refuses that); the new sha lands on the amendment row, and
`store.latest_source_sha` reads it from there afterwards. All three tables are append-only, so
this step is not reversible — which is exactly why the whole pre-registration is in 7b.

---

### Step 8: Measure, and decide whether to stop

**File:** none — commands only.

**8a. The official verdict line.** `lab control` is a `lab` command and migrates on connect; it
writes no rows.

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab control M0047 \
  > "$SCRATCH/m0047_control.out" 2>&1
echo "exit=$?"
cat "$SCRATCH/m0047_control.out"
```

**8b. Re-derive the numbers read-only**, so the report never depends on a formatted table:

```bash
sqlite3 "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" <<'SQL'
.mode column
.headers on
SELECT t.candidate_id, t.n, t.trades, ROUND(t.turnover, 3) AS turnover,
       ROUND(f.mwr * 100, 2) AS mwr_pct, ROUND(f.spy_tr_mwr * 100, 2) AS spy_pct
  FROM trials t JOIN trial_funding f ON f.trial_n = t.n
 WHERE t.method_id = 'M0047' AND t.window = 'dev'
 ORDER BY t.n;
SQL
```

**8c. The stop condition, and it is absolute.** Compute, for each new arm against its true target:

```
trade_ratio    = trades(X-PLC)   / trades(X)
turnover_ratio = turnover(X-PLC) / turnover(X)
```

- **Both arms inside `WARN_BAND` = [0.80, 1.25] on both axes** -> the shape is repaired. Write the
  numbers down, hand them to phase 8, and this phase is done.
- **Either arm outside [0.80, 1.25] on either axis** -> **record and stop.** Write the measured
  ratios and the reason into the handoff and leave the amendment exactly as it ran. No seed
  change, no second draw, no re-run. An arm outside `REFUSE_BAND = [0.50, 2.00]` additionally
  means phase 2's supersession rule will not excuse `M0047-PLC1-MV10`, so M0047 stays blocked on
  D17 — that is the reported outcome, not a problem to be fixed by drawing again.
- **In no case** is the *margin* a reason to touch anything. A lead that narrows, vanishes or
  reverses is the finding (plan invariant 4, design §4). Re-drawing until a margin survives is
  precisely what the design forbids, and it is forbidden here whichever way the number lands.

**8d. Re-run the tree.**

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
/home/miftah/seer/engine/.venv/bin/ruff check engine
PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src \
  /home/miftah/seer/engine/.venv/bin/pytest engine/tests -q
```

The `web/data/lab.json` snapshot test is red mid-batch by design and phase 8 makes it green; no
step here may try to.

---

## Verification

**Build:** `/home/miftah/seer/engine/.venv/bin/ruff check engine` (CI lint is E9 and F minus F401)

**Tests:**
```bash
PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src \
  /home/miftah/seer/engine/.venv/bin/pytest engine/tests -q
```
with `engine/tests/test_lab_methods.py` the one that must be green before the commit —
`test_every_recorded_configuration_still_digests_to_its_recorded_digest`,
`test_allocator_ids_are_unique_across_methods` and `test_allocator_contract` in particular.

**Manual checks:**
1. Step 6c's walk prints `('M0047-MV10', 'sibling-stem')` and `('M0047-MV20', 'sibling-stem')`,
   `kind='placebo'` on both new arms, and the two old arms still at
   `('M0047-EQ', 'first-declared')`.
2. Step 6d's probe prints an entry ratio within a couple of percent of 1.000 and near-zero
   per-session mismatches, before the commit.
3. `git status --porcelain -- m0047_market_value_residual.py` is empty before `lab run --amend`.
4. `lab control M0047` reports `M0047-MV10-PLC` -> `M0047-MV10` and `M0047-MV20-PLC` ->
   `M0047-MV20`, `ok` on both axes.
5. `git hash-object lab/lab.sqlite` recorded before and after the run; the test-window look count
   in the database is still 4.

**Exit criteria:** `M0047` carries `method_amendments` seq 1 with two recorded dev trials;
`lab control M0047` shows both new arms resolving by `sibling-stem` onto `M0047-MV10` and
`M0047-MV20` and inside `[0.80, 1.25]` on trades and on turnover; both margins are written down in
`trial_funding.mwr` against the true targets **and** against `M0047-EQ`; no recorded
`config_digest` moved; `pytest engine/tests` and `ruff check engine` are green; `lab stage` was
not run and `lab/lab.sqlite` was not committed.

---

## What to record for phase 8

**Write it to `.workflows/plan/honest-control-redraw/phase-4-results.md` and commit it by
pathspec.** That path is the set's one results-file convention (`phase-N-results.md`, N in 1..7),
it is the only place Phase 8 collects this phase's numbers from, and nothing else in this phase
writes a number anywhere a later reader will look: no `lab note`, no `lab insight`, no edit to
the plan index, no `lab stage`.

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
git add -- .workflows/plan/honest-control-redraw/phase-4-results.md
git commit -m "lab: M0047's two re-drawn controls recorded -- the measured shapes and margins" \
           -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
           -- .workflows/plan/honest-control-redraw/phase-4-results.md
```

The file carries this table, filled from Step 8b, with every number from `trial_funding.mwr` and
SPY TR at 7.19%/yr:

| | `M0047-MV10-PLC` | `M0047-MV20-PLC` |
|---|---|---|
| resolves to (rung) | `M0047-MV10` (sibling-stem) | `M0047-MV20` (sibling-stem) |
| trades, and the ratio to its target | _n_ / 1600 = _x_ | _n_ / 1591 = _x_ |
| turnover, and the ratio | _t_ / 9.345 = _x_ | _t_ / 9.853 = _x_ |
| verdict | `ok` / `warn` / `refuse` | `ok` / `warn` / `refuse` |
| `mwr` % | _m_ | _m_ |
| worst fall % | _f_ | _f_ |

and these five sentences:

1. **The new margin against the true target.** `MV10` 11.15 − `MV10-PLC` _m_ = _x_ pts/yr;
   `MV20` 10.42 − `MV20-PLC` _m_ = _x_ pts/yr.
2. **The old margin against the true target**, which no published sentence used: `MV10` +1.28,
   `MV20` +0.54.
3. **The old margin as it was published**, against `M0047-EQ`, which is the arm the ladder's
   `first-declared` guess supplied: `EQ` 13.67 − `PLC1-MV10` 9.87 = **+3.80**; `EQ` 13.67 −
   `PLC1-MV20` 9.88 = **+3.79**. Both numbers go in the close-out, because the published sentence
   was quoted against the wrong arm *and* against a handicapped one, and the close-out must say
   which part of the correction came from which.
4. **Whether the pre-registered direction held.** Predicted: both honest controls earn less than
   9.87% / 9.88% and both leads widen. Report the sign plainly either way.
5. **M0047's own success clause**, "beats its own size-weighted placebo by at least 2 points a
   year": against `EQ` it read as a pass at +3.80; against the true target it was already a
   failure at +1.28 before this amendment; state whether the honest control moves it back over
   2.0 on either arm. This is the sentence the owner would otherwise read wrong.
6. **That `M0047-EQ` now has no control arm at all, in those words.** Both of its placebos were
   size-weighted arms the ladder mis-aimed at it, and both are replaced by arms aimed at `MV10`
   and `MV20`. The correct consequence is that EQ's +3.80-point sentence is **withdrawn, not
   re-measured**: it was never supported by a correctly-aimed control. A method arm with no
   placebo produces an empty findings tuple and is not refused, so this is consistent with D17
   and is not a gap to be filled with a third arm.
7. **The two `supersedes` declarations**, verbatim, so Phase 8 can check them against the index's
   mapping: `M0047-MV10-PLC` -> `M0047-PLC1-MV10`, `M0047-MV20-PLC` -> `M0047-PLC1-MV20`. The
   second retires a `warn` arm rather than a `refuse` one, which blocks nothing but keeps the
   pair's record consistent.

Also hand over: the two `git hash-object lab/lab.sqlite` values from 7a and 7e, the
`method_amendments` seq this run wrote (expected 1), and the two trial `n` values.

---

## Handoffs

- **A committed regression test for the matched draw.** The smoke fixture carries no
  `ShareCounts` (`engine/tests/labkit.py:49-54`), so every market-value allocator targets nothing
  on it and a fixture-based assertion about M0047's churn would prove nothing. The session-by-
  session entry-count assertion therefore belongs in **phase 1's**
  `engine/tests/test_lab_control_draw.py`, against a chassis whose allocator runs on the
  history-only path — `M0227` or `M0243`, both of which phase 1 owns. This phase's probe (Step
  6d) proves the rule on M0047's real chassis but is deliberately not committed, so the plan
  index's "Files: 1" for phase 4 holds.
- **Unblocking `lab promote` for M0047 (R4) is Phase 2's, and this phase's half of it is the
  declaration.** `mis_shaped_controls` returns every recorded arm outside the band, and
  `M0047-PLC1-MV10` is recorded forever. **The cross-phase hazard this phase raised in planning
  is now closed, and closing it is why Phase 2's predicate changed.** Under the draft's "same
  `target_id`" rule neither new arm would have superseded anything here — the old pair resolves
  to `M0047-EQ` and the new pair to `M0047-MV10` and `-MV20` — and M0047 would have stayed
  blocked after every measurement had been taken. Phase 2's rule is now an **explicit
  declaration**: `M0047-MV10-PLC` carries `supersedes=("M0047-PLC1-MV10",)` and `M0047-MV20-PLC`
  carries `supersedes=("M0047-PLC1-MV20",)`, and `lab control` prints both the superseded arm's
  target and the superseding arm's, so the re-point is visible to a reader rather than hidden.
  Getting those two tuples right is this phase's whole contribution to R4; R4 is still not in
  this phase's `satisfies`.
- **After this phase, `M0047-EQ` has NO control arm at all, and that is the correct outcome —
  write it down.** Its only placebos were `M0047-PLC1-MV10` and `-MV20`, two *size*-weighted arms
  the ladder mis-aimed at it on the `first-declared` rung; their replacements are aimed at `MV10`
  and `MV20`, where they belong. The standing sentence about EQ's **+3.80-point lead over its
  placebo was never supported** — it was quoted against an arm that controls a different book and
  was handicapped besides — and the repair is to **stop quoting it**, not to manufacture a control
  for it. A method arm with no placebo produces an empty findings tuple, which
  `control_shape.findings` documents as the correct answer and not an error, so `M0047-EQ` is not
  refused for having none and this is consistent with D17 rather than an exception to it. Say so
  plainly in `phase-4-results.md`; Phase 8's handover carries it into the close-out.
- **`M0047-MV` has no control at all either**, and for a duller reason. The uncapped size-weighted
  arm (trial 722, 11.12% mwr) never had a placebo of its own and never had one quoted against it,
  so nothing has to be withdrawn. Adding `M0047-MV-PLC` is a third arm this amendment could have
  carried and deliberately does not: the phase's scope is the two arms D17 flags, and a third arm
  is a new question, not a repair.
- **The turnover axis is the live risk on this chassis, and the policy is settled set-wide.**
  M0047's arms weight by market value under a ceiling, so like M0221/M0225's and M0201's their
  turnover is a property of the weight vector and not only of the names — Phase 3 measured
  `M0221-E50` holding C50's exact names and recording C50's exact 360 trades while turning over
  1.60x. Index invariant 12 settles it: **match names and churn only; a turnover miss is a
  recorded STOP.** Do not reach for the real arm's own weight vector here. It would be a second
  mechanism applying to three of the nine chassis and leaving them running a different rule from
  the other six, which fails R1's "ONE reusable rule" rather than rescuing it.
- **`lab stage`, `web/data/lab.json` and the `lab/lab.sqlite` commit** are phase 8's, in that
  order and after the merge to `main`.
- **Nothing in `web/`.** Grepped in the analysis: nothing under `web/` references `control_shape`,
  `controlShape` or `mis_shaped`, so no TS mirror moves with this.

---

## Rollback

**Before Step 7d (the run).** `git revert` the Step 7b commit, or
`git checkout HEAD~1 -- engine/src/seer_engine/lab/methods/m0047_market_value_residual.py` and
commit that single path. Nothing has been written to the lab database; the `Amendment` block is
pre-registration and nothing else, and reverting it costs nothing.

**After Step 7d.** Not reversible, and it must not be made to look reversible. `trials`,
`trial_funding` and `method_amendments` all carry append-only triggers on `UPDATE` **and**
`DELETE` (`lab/store.py`). The two trials exist; the amendment row exists. The `Amendment` block
must therefore stay in the method file for good — deleting it would leave the database holding
rows for a block the file no longer declares, and `runner.pending_amendment` compares every
recorded row field by field against the file, so the next `lab run --amend` on M0047 would refuse.
The correct rollback after the run is a journalled `lab insight` saying the arms ran and what they
showed. This is the whole reason the pre-registration sits in the commit that precedes the run.

**If the run fails partway.** `runner.record` takes `BEGIN IMMEDIATE` at record time only
(`lab/store.py:896-901`), so a failure during the backtest writes nothing and the step may simply
be re-run. A failure after the record is a recorded run: do not re-run, read 8b and report.
