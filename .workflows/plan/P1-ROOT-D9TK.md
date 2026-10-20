> Adopted from `/home/miftah/seer/.workflows/orchestration/honest-control-redraw/PLAN.md` phase 2. Source: `.workflows/plan/honest-control-redraw/phase-2.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 2: D17 supersedes — an honest control retires a handicapped one

**Plan set:** `HONEST_CONTROL_REDRAW_PLAN.md`
**Analysis:** `docs/analyzer/20261019-181712-C4K9_code_analyzer.md`
**Satisfies:** R4 — `lab promote` must actually stop refusing the nine once each holds an honestly
shaped control. Today it cannot, because the handicapped arm is recorded forever.
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab`

---

## Goal

After this phase, a `REFUSE` **or `WARN`** finding from `control_shape` is **superseded** — still
computed, still printed, still carrying its ratios — when the same method holds another `placebo`
arm that is itself band-clean (`OK`) and that **names it** in its own pre-registered declaration.
`refusals()` excludes a superseded finding, so `hardgate.check`'s D17 clause stops raising on it,
and D17 finally honours the sentence its own refusal message has been printing: *"re-draw the
control at the book's own trade count and turnover and run it again as an amendment."* Measured
against the lab as it stands, the change retires **nothing**: 64 findings, 19 refusals, 0
supersessions, before and after — and now for a stronger reason than a measurement, because no
arm in the committed lab declares anything at all.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Creates:**
- `control_shape.SUPERSEDES_ATTR = "supersedes"` — the duck-typed attribute name, beside
  `DECLARATION_ATTR` (`control_shape.py:177`)
- `control_shape.declared_supersessions(arm) -> tuple[str, ...]` — the reader for it
- `control_shape.Finding.declares: tuple[str, ...]` — new field, default `()`: what **this** arm
  declares it supersedes, stamped at construction (`control_shape.py:277-306`)
- `control_shape.Finding.superseded_by: str | None` — new trailing field, default `None`
- `control_shape.Finding.superseded_by_target: str | None` — new trailing field, default `None`:
  the **superseding** arm's own resolved target, which may differ from this one's and must be
  visible to a reader rather than hidden
- `control_shape.Finding.blocking` — property, `verdict == REFUSE and superseded_by is None`
- `control_shape.superseding_arm(f, found) -> tuple[str, str | None] | None` — the predicate
- `control_shape._mark_superseded(found) -> tuple[Finding, ...]` — the second pass
- `control_shape._SUPERSEDED_HEAD` / `control_shape._head(with_superseded)` — the conditional
  ninth report column
- tests: `test_lab_control_shape.BLOCKED_NINE` and eight new test functions;
  `test_lab_hardgate.BLOCKED_NINE` and four new test functions

**Deletes:** nothing. No symbol, no config key, no band constant.

**Renames:** nothing.

**Signature changes:**
- `control_shape._cells(f)` -> `control_shape._cells(f, with_superseded)` (private, one caller)
- `control_shape.findings(...)` returns the same type; its tuple is now passed through
  `_mark_superseded` before return. No caller changes.
- `control_shape.refusals(found)` keeps its signature; its filter becomes `f.blocking` instead of
  `f.refused`. **This is the only behaviour change the gate sees.**
- `hardgate.mis_shaped_controls` — **body unchanged**, docstring only. It already returns
  `control_shape.refusals(...)`, so it inherits the narrowing for free.

**Requires (from earlier phases):** nothing. This phase has no `depends_on` and assumes no other
phase has landed. In particular it does **not** depend on Phase 1's
`backtest.dev.Candidate.supersedes`: the attribute is read through `getattr(arm, SUPERSEDES_ATTR,
())`, which answers `()` on any arm that has none, exactly as `declared_target` already reads
`DECLARATION_ATTR` on 770 candidates that carry no `controls`. Either phase may land first and
both orders compile and are correct. This phase's own fixtures set the attribute on their `Stub`
arms directly.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/control_draw.py` — Phase 1 creates it; this phase never imports it.
- `engine/src/seer_engine/backtest/dev.py` — Phase 1 adds the `supersedes` field there. This phase
  **reads the attribute and never imports the module**; keeping the dependency absent is the point
  of duck-typing it.
- every `engine/src/seer_engine/lab/methods/mNNNN_*.py` — Phases 1, 3, 4, 5, 6, 7.
- `lab/lab.sqlite`, `web/data/lab.json`, `lab stage`, `lab run`, `lab test` — Phase 8. **This phase
  writes nothing to any database and runs no `lab` subcommand.**
- `control_shape.WARN_BAND`, `control_shape.REFUSE_BAND` — frozen by Invariant "Moving WARN_BAND or
  REFUSE_BAND" in the index. Read in exactly the places they are read today, nowhere new.
- `control_shape.resolve_target` and its four rungs — untouched. Supersession no longer reads a
  target at all except to *print* it.

---

## The predicate, decided — and why it is a declaration and not a target match

The draft of this phase, and the draft index it was written against, said a refusal is superseded
when a band-clean sibling placebo resolves to the **same `target_id`**. Phases 4, 5 and 7 each
independently proved that predicate broken, **in both directions**, and it is replaced here.

**Too strict.** The `<target-id>-PLC` naming convention the whole set uses exists precisely to
re-point a new arm at its TRUE target, which means the new arm's `target_id` is deliberately
*different* from the old one's wherever the old one was mis-resolved:

| old arm | its resolved target | the arm replacing it | that arm's target |
|---|---|---|---|
| `M0047-PLC1-MV10` | `M0047-EQ` (first-declared, a guess) | `M0047-MV10-PLC` | `M0047-MV10` |
| `M0047-PLC1-MV20` | `M0047-EQ` (first-declared, a guess) | `M0047-MV20-PLC` | `M0047-MV20` |
| `M0202-PLC1-HALF-FAST` | `M0202-Y20-HALF` (its stem is itself a placebo) | `M0202-Y20-HALF-FAST-PLC1` | `M0202-Y20-HALF-FAST` |

Under target equality none of those three is superseded, and M0047 and M0202 stay blocked after
all of the work — which is the exact failure this plan set exists to stop.

**Too loose.** `M0215-HASH` and `M0215-HASH-CAP4` **both** resolve to `M0215-CTRL`, so one honest
control of `M0215-CTRL` would excuse both — including `HASH-CAP4`, whose job (`m0215:304`) is to
price what a cap does and which was never scored against `CTRL` in spirit. And the measurement
below shows the loose *band* reading retires an arm on today's lab with its own equally
handicapped twin.

**THE RULE, as implemented here.** A `REFUSE` or `WARN` finding `f` is **superseded** when the
same method holds an arm `g` that

- **(a)** is kind `placebo` — a dose-response or within-frame arm carries no ratio at all and is
  nobody's measuring stick, and admitting one would turn `kind_of`'s dose-before-draw ordering
  into a way of clearing the gate by wording a rationale;
- **(b)** has verdict `OK` — inside `WARN_BAND` on **both** axes, not merely inside
  `REFUSE_BAND`; and
- **(c)** **names `f.control_id` in its own pre-registered declaration** (`SUPERSEDES_ATTR`).

**There is no target-equality requirement at all.** The report prints the superseded arm, its
resolved target, the superseding arm **and the superseding arm's own (possibly different)
resolved target**, so a re-point is something a reader sees rather than something the rule hides.

**Why declared and not inferred.** Target equality is an inference about intent from a resolution
the ladder itself reports as a guess on its weakest rung, and the three rows above are what that
inference costs. A declaration is the author of the re-draw saying, in the commit that
pre-registers the arm and before any result exists, which measurement this one replaces — the
same discipline as `why`, `hypothesis` and `expected_failure`, and the same discipline
`control_shape`'s own docstring already names as the forward path: *"The forward path for a
method written tomorrow is `DECLARATION_ATTR`, not a wider guess."* The reason that docstring
gives for why the lab's **existing** arms cannot use a declaration — `methods.source_sha` is
written once and trigger-protected, so an already-run file cannot grow a keyword — does not apply
to these fourteen, which live in `Amendment` blocks on files that are growing anyway and whose
sha lands on the `method_amendments` row.

**Why a defaulted field on `Candidate` and not a token in the rationale.** Both are outside
`config_digest` and both were available. The field wins on three counts. It is **validated at
import**: `Candidate.__post_init__` checks every entry against `_ID`, refuses a self-reference and
demands the tuple be sorted and unique, so a typo in a declaration is an `ImportError` the phase
session sees immediately rather than a silent non-supersession discovered in Phase 8. It is
**structured**, so `lab control` can print the mapping without re-parsing prose. And it is **the
mechanism this module already documents**: `declared_target` reads `DECLARATION_ATTR` duck-typed
through `getattr`, `control_shape` explains in its own docstring that it is written that way so a
defaulted `Candidate` field can land later, and this is that later. The rationale-token route is
not wrong — `kind_of` already classifies by prose and an explicit token is a declaration rather
than an inference — but it would put an unvalidated string in the one field a reader's eye skims,
and the module's warning about clever regexes is a warning about exactly that surface.

**The digest safety, verified and not assumed** (Phase 1 owns the field, this is the check):
`lab.method.config_text` names `c.rules`, `c.allocator.id` and `c.params`;
`registry.candidate_text` names five fields, all by hand; and grepped over
`engine/src/seer_engine/` on 2026-10-19, **every** `_canon(...)` call site is `_canon(c.rules)`,
`_canon(c.params)` or a recursive call inside `_canon` itself — no call site passes a whole
`Candidate`, so `_canon`'s `dataclasses.fields()` walk never meets one. `Candidate` is
`@dataclass(frozen=True)` with no `slots=True`, so a trailing defaulted field changes no layout
and no existing construction site.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/control_shape.py` | modify | docstring section; `SUPERSEDES_ATTR` + `declared_supersessions`; `Finding.declares` / `superseded_by` / `superseded_by_target` + `blocking`; `superseding_arm`; `_mark_superseded`; the five `Finding(...)` constructions in `findings`; `findings` return; `refusals` filter; `describe`; the report's conditional ninth column |
| `engine/src/seer_engine/lab/hardgate.py` | modify | D17 prose (`:523-583`); `mis_shaped_controls` docstring (`:831-858`); the D17 comment and one sentence of the refusal message (`:1776-1798`) |
| `engine/src/seer_engine/commands/lab.py` | modify | `lab control` description (`:700-714`); the run's control print (`:1778-1798`); `_control`'s trailer (`:2859-2867`) |
| `engine/tests/test_lab_control_shape.py` | modify | six new tests: one positive, four negatives, one report test; plus the nine-method no-op pin |
| `engine/tests/test_lab_hardgate.py` | modify | two fixture-level gate tests, one committed-lab no-op test, two asserts on the D17-docstring test |

---

## Why `OK` and not `OK or WARN` — the measurement that settles it

Run read-only in this worktree on 2026-10-19, over the whole committed lab
(`sqlite3 "file:<worktree>/lab/lab.sqlite?mode=ro"` semantics, via `cs.survey(conn)`):

```
total findings 64   refusals 19   supersessions 0      <- predicate: sibling verdict == OK
loose supersessions 1                                   <- predicate: sibling verdict in (OK, WARN)
  LOOSE-SUPERSEDE  M0047  M0047-PLC1-MV10  <-  M0047-PLC1-MV20 (warn)
```

Under the loose *band* reading, `M0047-PLC1-MV10` (0.549x trades / 0.496x turnover) would be
retired by its own twin `M0047-PLC1-MV20` (0.545x / 0.508x) — an arm that is just as handicapped,
and differs only in that its turnover ratio rounds to the clean side of 0.50. M0047 would be
unblocked by a second bent stick, with no honest control drawn and no measurement taken. That is
precisely the failure this whole plan set exists to stop, and it is why the band condition on the
**superseding** arm is `verdict == OK`: the arm that retires a handicapped control must itself be
inside the **match** band, which is the bar R1 sets for every re-drawn arm in this plan set and
the bar every method phase's exit criterion names.

*(Read this measurement for what it argues and no more: it argues the BAND condition — `OK`, not
merely inside `REFUSE_BAND`. Under the final rule that twin retires nothing in any case, because
it declares nothing. The band is a second lock on a door the declaration already closes, and it
is kept because all fourteen arms this set adds WILL declare, and one of them landing at 1.4x
must not be allowed to retire anything either.)*

Under the tight reading the change is a measured no-op: **0 supersessions, 19 refusals before and
19 after.**

## Why a field on `Finding` and not a standalone function

`Finding` is `@dataclass(frozen=True, slots=True)`. It is **not** a params dataclass: it is never
rendered by `registry._canon`, never enters `config_text`, and carries no `config_digest`
consequence (memory `seer-shared-params-cannot-gain-a-field` does not apply here — it applies to
`lab/methods/*` params classes, which Phases 1 and 3-7 own). Grepped 2026-10-19: `Finding(` is
constructed in exactly five places, all inside `control_shape.findings`, all keyword-only. A
trailing defaulted field breaks nothing.

The alternative — a free function `superseded(found) -> dict[str, str]` that every caller invokes
separately — was rejected on the module's own stated design value. `control_shape`'s docstring and
`_control`'s docstring both argue that `lab run`, `lab control` and `lab promote` read **the same
`Finding`** through **the same formatter** so that "the three bindings can never disagree about one
arm". A supersession computed independently by the gate and by the report is a fourth place for
them to drift, and the drift would be silent: the gate would pass while the table still said
`refuse` with nothing to explain it. Stamping the answer onto the `Finding` in `findings()` — the
one builder — keeps the single-source-of-truth property the module was written around.

Supersession is a **cross-arm** property, so it cannot be computed inside the per-arm loop; it is a
second pass over the finished list, which is also why it is `_mark_superseded` and not an argument
threaded through five constructor calls.

---

## Implementation Steps

### Step 1: `control_shape.py` — the docstring section

**File:** `engine/src/seer_engine/lab/control_shape.py:150` (insert between the "Lab-wide over all
46 placebo arms…" paragraph that ends at line 149 and the `---` on line 151)

**Change:** add the design argument for supersession in the file's existing voice, with the
measurement.

**Code:** insert these lines after line 149 (`Lab-wide over all 46 placebo arms: 19 refuse, 7 warn,
4 clean, 16 unresolved. …is nineteen.`) and before the blank line + `---` that follows:

```
---

**A bent stick can be straightened, and then the straight one is the stick.** The refusal this
module feeds says so in its own words -- *"re-draw the control at the book's own trade count and
turnover and run it again as an amendment"* -- and until 2026-10-19 the code did not honour that
sentence. A method file is append-only in practice: its recorded trials pin its candidates, and
``trials`` is append-only by trigger, so the handicapped arm stays in ``all_candidates()`` and
keeps its row forever. Re-drawing therefore added a clean arm beside the bent one and changed
nothing at all: ``refusals`` still returned the bent one and ``hardgate`` still raised. Nine
dev-eligible methods would have done all of the measuring work and stayed exactly as blocked.

So a ``REFUSE`` or ``WARN`` finding is now **superseded** when the same method holds another
``placebo`` arm that is itself clean on both axes **and that NAMES it** in its own pre-registered
declaration (``SUPERSEDES_ATTR``). ``superseding_arm`` is that predicate and
``Finding.superseded_by`` carries its answer; ``refusals`` -- and only ``refusals`` -- drops a
superseded refusal, so the gate reads the honest draw and nothing else moves.

**Declared, and deliberately not inferred from the target.** The obvious rule was "a clean
placebo on the same ``target_id``", and it is wrong in both directions. Too strict: a re-drawn
arm named ``<target-id>-PLC`` is deliberately re-pointed at the book it actually controls, so
``M0047-MV10-PLC`` resolves to ``M0047-MV10`` while the arm it replaces resolves, by the ladder's
weakest rung, to ``M0047-EQ``; under equality M0047 and M0202 would do all the measuring and stay
blocked. Too loose: ``M0215-HASH`` and ``M0215-HASH-CAP4`` both resolve to ``M0215-CTRL``, so one
honest control of ``CTRL`` would excuse an arm that exists to price a cap. Equality is an
inference about intent from a resolution this module itself labels a guess; a declaration is the
author of the re-draw saying which measurement this one replaces, written into the commit that
pre-registers it and before any result exists. The report prints **both** targets -- the
superseded arm's and the superseding arm's -- so a re-point is something a reader sees.

**``WARN`` is superseded too, though it never blocked.** ``M0047-PLC1-MV20`` is 0.545x / 0.508x:
inside the refuse band, outside the match band, and every margin written against it is as little
evidence as its refused twin's. It stops no promotion, so retiring it changes no gate -- but a
reader meeting the honest number has to be told the old one was answered, and leaving one of a
re-drawn pair unmarked would say the opposite.

**The superseded row is still computed, still carries both ratios, and is still printed.** Its
``verdict`` stays ``REFUSE`` and ``flagged`` stays true. That is deliberate and it is the whole
difference between this and an amnesty: every sentence already written about that margin was
quoted against the handicapped opponent, and a reader who meets the new number needs to be able to
see the old one and what was wrong with it. ``blocking`` -- not ``refused`` -- is the property a
gate acts on.

**Why the superseding arm must be ``OK`` and not merely inside ``REFUSE_BAND``.** Measured over
the whole committed lab on 2026-10-19: with the tight rule, **zero** findings are superseded, so
the change moves no verdict anywhere. With the loose rule, one is -- ``M0047-PLC1-MV10`` (0.549x /
0.496x) would be retired by ``M0047-PLC1-MV20`` (0.545x / 0.508x), its own equally handicapped
twin, which clears ``REFUSE_BAND`` only because its turnover ratio rounds to the clean side of
0.50. A stick that is 0.545x as long as the book is not a measuring stick, and letting one retire
another would unblock a method with no honest control in existence. The band is unchanged and
unread anywhere new; it is the *match* band, ``WARN_BAND``, that the replacement has to clear,
which is the same bar every re-drawn arm in the 2026-10-19 plan set is held to.

**Four things do not supersede, each for its own reason.** A ``warn`` **superseder** (above) --
the arm doing the retiring must be inside the match band. An arm that **declares nothing** -- no
declaration, no supersession, however well-shaped it is and whatever it happens to resolve to;
this is why the rule is a measured no-op on the committed lab, where no arm declares anything at
all. An ``unresolved``, ``unrecorded`` or ``not-checked`` superseder -- absence is not evidence
(D16's sentence), and an arm that has been declared in a method file but not yet run is exactly
the state a half-finished re-draw is in; letting it supersede would unblock the method the moment
the *intention* was committed, before a single trial existed. A dose-response or ablation arm --
it is not a control of shape at all and carries no ratio, so it cannot be anybody's measuring
stick, and admitting it would turn ``kind_of``'s dose-before-draw ordering into a way to game the
gate by wording.
```

**Impact:** documentation only; the prose carries the argument the commit must also make.

---

### Step 2: `control_shape.py` — import `replace`

**File:** `engine/src/seer_engine/lab/control_shape.py:167`

**Change:** `_mark_superseded` rebuilds frozen findings.

**Code:** replace line 167

```python
from dataclasses import dataclass
```

with

```python
from dataclasses import dataclass, replace
```

**Impact:** none beyond enabling Step 4. `dataclasses.replace` works on `slots=True` dataclasses.

#### Step 2b: the attribute name and its reader

**File:** `engine/src/seer_engine/lab/control_shape.py:178` (immediately after
`DECLARATION_ATTR = "controls"`)

**Change:** add the second duck-typed attribute and the one function that reads it, so every
reader in the module goes through one place.

```python
SUPERSEDES_ATTR = "supersedes"
"""The attribute a re-drawn control names the arms it replaces in. Declared, never inferred.

Read exactly as ``DECLARATION_ATTR`` is -- ``getattr(arm, SUPERSEDES_ATTR, ())`` -- so this module
imports nothing from ``backtest.dev`` and an arm without the attribute simply declares nothing.
``backtest.dev.Candidate`` carries it as a defaulted, validated ``tuple[str, ...]`` from
2026-10-19; it is outside ``config_digest`` because ``lab.method.config_text`` and
``registry.candidate_text`` both name their fields by hand and nothing passes a whole
``Candidate`` to ``registry._canon``.
"""


def declared_supersessions(arm: Arm) -> tuple[str, ...]:
    """The candidate ids ``arm`` declares it supersedes. Duck-typed: see ``SUPERSEDES_ATTR``.

    Tolerant of anything that is not a tuple of non-empty strings, because this is a reader and
    every uncertainty it meets must become a verdict a human can see rather than an exception a
    caller has to catch. A malformed declaration therefore declares nothing, and the import-time
    validation in ``Candidate.__post_init__`` is what stops one being written in the first place.
    """
    declared = getattr(arm, SUPERSEDES_ATTR, ())
    if not isinstance(declared, (tuple, list)):
        return ()
    return tuple(s for s in declared if isinstance(s, str) and s)
```

---

### Step 3: `control_shape.py` — `Finding` gains `superseded_by` and `blocking`

**File:** `engine/src/seer_engine/lab/control_shape.py:277-306`

**Change:** one trailing defaulted field and one property. `refused` is **not** touched: a
superseded arm is still a refusal, it just no longer blocks.

**Code:** replace the whole class (lines 277-306) with:

```python
@dataclass(frozen=True, slots=True)
class Finding:
    """One control arm, the arm it controls, and whether their shapes match.

    ``rung`` names which step of the ladder chose ``target_id``, so a resolution the author would
    dispute is visible in the output rather than buried in a ratio. ``reason`` is one plain
    sentence; ``describe`` wraps it with the ids.

    ``declares`` is what THIS arm says it supersedes, read off the candidate at construction
    through ``SUPERSEDES_ATTR``. ``superseded_by`` is the id of the later, band-clean arm that
    declared THIS one, and ``superseded_by_target`` is that arm's own resolved target -- which may
    differ from this one's, because the ``<target-id>-PLC`` convention deliberately re-points a
    re-drawn control at the book it actually controls. Both are set by ``_mark_superseded`` when
    ``findings`` has the whole method in hand. Printing both targets is the point: a reader who
    meets a re-pointed replacement must be able to see that it was re-pointed.

    A superseded finding keeps its ``REFUSE`` (or ``WARN``) verdict, both ratios and its reason,
    and is still printed: the old draw is the record of what every margin quoted against it was
    actually worth. Only ``blocking`` goes false, and only ``refusals`` reads ``blocking``.
    """

    method_id: str
    control_id: str
    kind: str
    target_id: str | None
    rung: str | None
    control: Shape | None
    target: Shape | None
    trade_ratio: float | None
    turnover_ratio: float | None
    verdict: str
    reason: str
    declares: tuple[str, ...] = ()
    superseded_by: str | None = None
    superseded_by_target: str | None = None

    @property
    def refused(self) -> bool:
        """True only for a measured mismatch outside ``REFUSE_BAND``. Never for an unknown.

        Still true once the arm is superseded: the measurement does not stop being what it was
        because a better stick was cut later. A gate wants ``blocking``.
        """
        return self.verdict == REFUSE

    @property
    def blocking(self) -> bool:
        """A refusal nothing has retired: what ``refusals`` keeps and what the hard gate acts on."""
        return self.verdict == REFUSE and self.superseded_by is None

    @property
    def flagged(self) -> bool:
        """True for anything a researcher should read before quoting the gap."""
        return self.verdict in (WARN, REFUSE)
```

**Impact:** `Finding` is constructed in five places, all inside `findings`, all keyword-only. Each
of the five gains one argument, `declares=declared_supersessions(arm)`, so the declaration travels
with the finding and ``_mark_superseded`` needs nothing but the finished list; the other two new
fields keep their defaults there and are filled by the second pass. No other module or test
constructs a `Finding` (grepped 2026-10-19).

---

### Step 4: `control_shape.py` — the predicate and the second pass

**File:** `engine/src/seer_engine/lab/control_shape.py:465` (immediately after
`_not_checked_reason`, which ends at line 464, and immediately before `def findings`)

**Change:** add the two functions.

**Code:** insert between line 464 and line 467 (`def findings(`), keeping one blank line either
side of the existing section comments:

```python
def superseding_arm(f: Finding, found: Sequence[Finding]) -> tuple[str, str | None] | None:
    """The honest control that retires ``f`` and its own target, or None when nothing does.

    ``f`` is retired only when **all** of these hold of some other finding ``g`` of the same
    method:

    - ``f`` is itself a measured placebo mismatch -- ``REFUSE`` or ``WARN``. Nothing retires an
      ``unresolved``, an ``unrecorded`` or a ``not-checked``, because none of them is a
      measurement. ``WARN`` is included because a warn arm is still outside the match band and
      every margin quoted against it is still quoted against a handicap; it does not block a
      promotion, but a reader meeting the new number still needs to be told the old one was
      answered. ``M0047-PLC1-MV20`` is the one such arm in this lab;
    - ``g`` is a ``placebo``. A dose-response or within-frame arm carries no ratio at all and is
      not a measuring stick for anyone's shape -- admitting one would make ``kind_of``'s
      dose-before-draw ordering into a way of clearing the gate by wording;
    - ``g``'s verdict is ``OK`` -- inside ``WARN_BAND`` on every axis it has, not merely inside
      ``REFUSE_BAND``. See the module docstring for the measurement: the loose reading lets
      ``M0047-PLC1-MV20`` (0.545x) retire ``M0047-PLC1-MV10`` (0.549x), one bent stick replacing
      another, on today's lab and with no honest control drawn at all;
    - ``g`` **names ``f.control_id`` in its own declaration** (``SUPERSEDES_ATTR``, carried on the
      finding as ``declares``).

    **There is no target-equality condition, and its absence is the decision this rule turns on.**
    Equality is an inference about intent drawn from a resolution the ladder itself reports as a
    guess, and it is wrong in both directions. Too strict: the ``<target-id>-PLC`` convention
    deliberately re-points a re-drawn arm at its TRUE target, so ``M0047-MV10-PLC`` resolves to
    ``M0047-MV10`` while the arm it replaces resolves to ``M0047-EQ`` -- under equality M0047 and
    M0202 would stay blocked after all the measuring. Too loose: ``M0215-HASH`` and
    ``M0215-HASH-CAP4`` both resolve to ``M0215-CTRL``, so one honest control of ``CTRL`` would
    excuse an arm that exists to price a cap and was never scored against ``CTRL`` in spirit. A
    declaration is the author of the re-draw saying which measurement this one replaces, before
    any result exists.

    The second element of the answer is ``g``'s own ``target_id``, so the caller can print both
    and a re-point is visible rather than hidden.

    Ties go to the first such arm in ``findings``' own order, so the answer is deterministic and a
    reader can find the arm in the file. Reads no band constant of its own: ``OK`` is already the
    band's answer.
    """
    if f.verdict not in (REFUSE, WARN) or f.kind != KIND_PLACEBO:
        return None
    for g in found:
        if g.control_id == f.control_id or g.method_id != f.method_id:
            continue
        if g.kind != KIND_PLACEBO or g.verdict != OK:
            continue
        if f.control_id not in g.declares:
            continue
        return g.control_id, g.target_id
    return None


def _mark_superseded(found: Sequence[Finding]) -> tuple[Finding, ...]:
    """``found`` with ``superseded_by`` filled in. Nothing is dropped and no verdict is moved.

    A second pass rather than a branch inside ``findings``' loop, because supersession is a
    property of the whole method and not of one arm: the arm that retires a refusal is in practice
    declared *after* it, at the foot of the file in an ``Amendment`` block.
    """
    out: list[Finding] = []
    for f in found:
        by = superseding_arm(f, found)
        if by is None:
            out.append(f)
        else:
            out.append(replace(f, superseded_by=by[0], superseded_by_target=by[1]))
    return tuple(out)
```

**Impact:** new public symbols `SUPERSEDES_ATTR`, `declared_supersessions` and `superseding_arm`;
`_mark_superseded` is private. None is called yet. Note `WARN` must be in scope here — it already
is, beside `OK` and `REFUSE`.

---

### Step 5: `control_shape.py` — `findings` runs the second pass

**File:** `engine/src/seer_engine/lab/control_shape.py:539`

**Change:** one line.

**Code:** replace line 539

```python
    return tuple(out)
```

with

```python
    return _mark_superseded(out)
```

and extend `findings`' docstring (lines 470-476) so the behaviour is documented at its source.
Replace the docstring with:

```python
    """One ``Finding`` per control arm of ``method_id``, in declaration order.

    An arm that is not a control of any kind produces nothing at all -- a method with no control
    arm produces an empty tuple, which is the correct answer and not an error. Nothing is written
    and no ``LabError`` is raised: this is a reader, and every uncertainty it meets becomes a
    verdict a human can see rather than an exception a caller has to catch.

    The last thing it does is ``_mark_superseded``: a refusal that a later, band-clean control of
    the same arm has retired comes back carrying that arm's id. The refusal itself is untouched --
    same verdict, same ratios, same reason, same place in the order. This is the one step that
    needs the whole method at once, which is why it is a pass and not a branch in the loop above.
    """
```

**Impact:** `for_method`, `survey`, `commands/lab.py` and `hardgate.mis_shaped_controls` all read
findings through this function, so every one of them sees the field with no further change.

---

### Step 6: `control_shape.py` — `refusals` filters on `blocking`

**File:** `engine/src/seer_engine/lab/control_shape.py:601-603`

**Change:** the single behavioural edit in the module.

**Code:** replace lines 601-603 with:

```python
def refusals(found: Iterable[Finding]) -> tuple[Finding, ...]:
    """Measured mismatches outside ``REFUSE_BAND`` that nothing has retired. What a gate acts on.

    Reads ``blocking`` and not ``refused``: an arm a later band-clean control of the same book has
    superseded stays in ``found``, stays flagged and still prints, but it no longer stops a
    promotion. The refusal said "re-draw the control and run it again as an amendment"; this is
    the line that makes doing so mean something.
    """
    return tuple(f for f in found if f.blocking)
```

**Impact:** `hardgate.mis_shaped_controls`, `commands/lab.py:1778` and `commands/lab.py:2859` all
narrow together, because all three call this one function. `flags()` is untouched, so a superseded
arm is still in every "read this before quoting the gap" list.

---

### Step 7: `control_shape.py` — `describe` names the arm that retired it

**File:** `engine/src/seer_engine/lab/control_shape.py:614-618`

**Change:** append one clause. The existing prefix is unchanged, so
`test_the_report_names_the_band_the_rung_and_both_ratios`'s `startswith` assertion still holds.

**Code:** replace lines 614-618 with:

```python
def describe(f: Finding) -> str:
    """One sentence naming the control, the arm it controls and why the verdict is what it is.

    A superseded arm says so at the end, with the id of the arm that retired it, because this is
    the sentence the hard gate and both report surfaces quote and a reader meeting the old ratios
    needs to know they have already been answered.
    """
    if f.target_id is None:
        said = f"{f.control_id}: {f.reason}"
    else:
        said = f"{f.control_id} (against {f.target_id}, resolved by {f.rung}): {f.reason}"
    if f.superseded_by is None:
        return said
    aimed = (
        "" if f.superseded_by_target in (None, f.target_id)
        else f" (which controls {f.superseded_by_target}, not {f.target_id or 'this arm'})"
    )
    return (
        f"{said} -- superseded by {f.superseded_by}{aimed}, a later control that declares it "
        f"replaces this one and matches its own book's shape on both axes, so the gate reads that "
        f"one instead; this row stays because it is the record of what the margins written "
        f"against it were worth"
    )
```

**Impact:** the hard gate's message never carries a superseded finding (`refusals` excludes it), so
this clause surfaces only through `format_report`'s flagged list and `lab control`.

---

### Step 8: `control_shape.py` — the conditional ninth column

**File:** `engine/src/seer_engine/lab/control_shape.py:632-696`

**Change:** the report grows a `superseded by` column **only when some row in it is superseded**,
so every report the lab prints today is byte-identical to what it printed before.

**Code:** replace lines 632-696 (from `_HEAD` to the end of the file) with:

```python
_HEAD: tuple[str, ...] = (
    "method", "control", "kind", "controls", "resolved by", "trades x", "turnover x", "verdict",
)

_SUPERSEDED_HEAD = "superseded by"
"""The ninth column, added only when a row in the report has one.

A column that is a dash on every line of every report the lab prints today would be noise in
sixty-four rows to carry information in none of them. It appears when it says something, and every
report that has no superseded arm prints exactly the eight columns it printed before.
"""


def _head(with_superseded: bool) -> tuple[str, ...]:
    return (*_HEAD, _SUPERSEDED_HEAD) if with_superseded else _HEAD


def _cells(f: Finding, with_superseded: bool = False) -> tuple[str, ...]:
    row = (
        f.method_id,
        f.control_id,
        f.kind or KIND_NONE,
        f.target_id or DASH,
        f.rung or DASH,
        DASH if f.trade_ratio is None else f"{f.trade_ratio:.2f}",
        DASH if f.turnover_ratio is None else f"{f.turnover_ratio:.2f}",
        f.verdict,
    )
    if not with_superseded:
        return row
    if f.superseded_by is None:
        cell = DASH
    elif f.superseded_by_target in (None, f.target_id):
        cell = f.superseded_by
    else:
        # The replacement was deliberately re-pointed at its TRUE target. Print both, or a reader
        # sees one id retiring a row that names a different book and has no way to tell why.
        cell = f"{f.superseded_by} -> {f.superseded_by_target}"
    return (*row, cell)


def _table(head: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    """Head plus rows, columns padded to the widest cell.

    The first five columns are names and read left-justified; the ratios and the verdict are
    numbers and a word and read right-justified against them. ``superseded by`` is a candidate id,
    so it goes back to the left -- by its heading rather than by its index, because it is the last
    column only while it is the only optional one.
    """
    body = [tuple(head), *(tuple(r) for r in rows)]
    widths = [max(len(r[i]) for r in body) for i in range(len(head))]
    out: list[str] = []
    for k, row in enumerate(body):
        cells = [
            row[i].ljust(widths[i])
            if i < 5 or head[i] == _SUPERSEDED_HEAD
            else row[i].rjust(widths[i])
            for i in range(len(head))
        ]
        out.append("    " + "  ".join(cells).rstrip())
        if k == 0:
            out.append("    " + "  ".join("-" * w for w in widths))
    return out


def format_report(found: Sequence[Finding], *, show_clean: bool = True) -> str:
    """The table and the findings as text. The caller decides whether to print it.

    ``show_clean=False`` keeps only what a reader must act on, which is what the annotation at
    ``lab run`` wants; the standalone report shows everything, because a control that passed is
    the evidence the band is not simply refusing everything.

    A superseded arm is kept by **both** settings: it is still ``flagged``, because the sentence
    already written about its margin is still in the record and still wrong. The extra column and
    the paragraph under the table appear only when there is one.
    """
    rows = list(found) if show_clean else [f for f in found if f.flagged]
    out = [
        "control shape -- does each placebo carry the shape of the book it controls?",
        band_sentence(),
        "read from recorded dev trials only: nothing is run, nothing is written, and the test "
        "window is not touched.",
        "",
    ]
    if not rows:
        out.append(
            "    no control arm to report"
            if show_clean
            else "    no control arm to report: every one of them matches its book's shape"
        )
        return "\n".join(out)
    retired = [f for f in rows if f.superseded_by is not None]
    out += _table(_head(bool(retired)), [_cells(f, bool(retired)) for f in rows])
    bad = flags(rows)
    out.append("")
    if not bad:
        out.append("    every control arm shown matches the shape of the arm it controls")
    else:
        out.append("    what to read before quoting a control gap")
        for f in bad:
            out.append(f"      {describe(f)}")
    if retired:
        out.append("")
        out.append(
            "    superseded: a later control of the same arm matches its shape, so the gate reads "
            "that one. The"
        )
        out.append(
            "    row above stays, with its ratios, because every margin already written against "
            "it was quoted"
        )
        out.append("    against a handicapped opponent and the record of that has to stay readable.")
    return "\n".join(out)
```

**Impact:** `_cells` gains a defaulted second parameter; its only caller is `format_report`.
Existing output is unchanged whenever nothing is superseded, which is every report the lab prints
on this branch.

---

### Step 9: `hardgate.py` — D17's prose carries the rule and the argument

**File:** `engine/src/seer_engine/lab/hardgate.py:578-583`

**Change:** replace the "**The way back…**" paragraph with one that states what the way back now
*does*, and add the argument D17's own text demands ("if the rule is wrong, change it in
seer_engine/lab/hardgate.py and argue for it in the commit").

**Code:** replace lines 578-583

```
**The way back, and why the refusal names it.** A control is not a verdict on the signal; it is
a measuring stick, and a bent stick can be straightened. Re-draw the control at the book's own
trade count and turnover and run it again. That costs **no method id** -- an amendment appends
trials under the method's existing id -- and it is exactly what the 2026-10-19 handover asks for
on M0248 (section 2). A refusal that named no way back would be a dead end, and this rule meets
nine methods that need one, so the message says it and so does this paragraph.
```

with

```
**The way back, and why the refusal names it.** A control is not a verdict on the signal; it is
a measuring stick, and a bent stick can be straightened. Re-draw the control at the book's own
trade count and turnover and run it again. That costs **no method id** -- an amendment appends
trials under the method's existing id -- and it is exactly what the 2026-10-19 handover asks for
on M0248 (section 2). A refusal that named no way back would be a dead end, and this rule meets
nine methods that need one, so the message says it and so does this paragraph.

**And from 2026-10-19 the way back actually works: an honest control SUPERSEDES a handicapped
one.** Until this change it did not, and the gap was not a detail -- it was the rule failing at
the one thing it told people to do. A method file is append-only in practice, because its recorded
trials pin its candidates and ``trials`` is append-only by trigger. So re-drawing added the clean
arm beside the bent one, ``control_shape.refusals`` kept returning the bent one, and this clause
kept raising. All nine of the methods named below would have drawn an honest control, measured it,
written it up, and stayed exactly as blocked. A rule whose stated remedy does not remedy anything
is a rule nobody can satisfy, and this module has already written down (D16) what it thinks of
those.

The rule, exactly, and it is narrow on purpose: a ``refuse`` or ``warn`` finding is
**superseded** when the same method holds another ``placebo`` arm that is itself clean on both
axes **and that NAMES it** in its own pre-registered declaration
(``control_shape.superseding_arm``, reading ``control_shape.SUPERSEDES_ATTR`` off the candidate).
``refusals`` then drops it, so this clause does not raise on it.

**Declared, not inferred from the target, and that is the whole design.** The obvious rule --
"another clean placebo resolving to the same arm" -- fails in both directions on the very methods
named below. It is too strict, because a re-drawn control named ``<target-id>-PLC`` is
deliberately re-pointed at the book it actually controls: ``M0047-MV10-PLC`` resolves to
``M0047-MV10`` while ``M0047-PLC1-MV10`` resolves, on the ladder's weakest rung, to ``M0047-EQ``,
so equality would leave M0047 and M0202 blocked after every measurement had been taken. And it is
too loose, because ``M0215-HASH`` and ``M0215-HASH-CAP4`` both resolve to ``M0215-CTRL``, so one
honest control of ``CTRL`` would excuse an arm whose stated job is to price what a cap does. A
resolution this module labels a guess is not a fact to build a gate rule on; a declaration made
before any result exists is. ``lab control`` prints the superseded arm, its target, the
superseding arm **and the superseding arm's own target**, so a re-point is visible to a reader.

Four things deliberately do **not** supersede. A ``warn`` superseder -- it is itself outside the
match band. An arm that **declares nothing** -- which is every arm in the lab today, and is why
this change retires nothing. An ``unresolved``, ``unrecorded`` or ``not-checked`` superseder --
absence is not evidence (D16's own sentence), and an arm declared in a method file but not yet
run is exactly what a half-finished re-draw looks like; letting it supersede would clear the gate
on an *intention*. A dose-response or within-frame arm -- it carries no ratio at all, and
admitting one would turn ``control_shape``'s dose-before-draw ordering into a way of clearing
this clause by wording the rationale.

**Why clean and not merely inside the refuse band, measured.** Over the whole committed lab on
2026-10-19 the tight rule supersedes **nothing**: 64 findings, 19 refusals, 19 refusals. The loose
rule supersedes one -- ``M0047-PLC1-MV10`` (0.549x trades / 0.496x turnover) would be retired by
``M0047-PLC1-MV20`` (0.545x / 0.508x), its own equally handicapped twin, which clears
``REFUSE_BAND`` only because its turnover rounds to the clean side of 0.50. M0047 would be
unblocked by a second bent stick with no honest control in existence. So the replacement must
clear ``WARN_BAND``, the *match* band, which is also the bar the 2026-10-19 plan set holds every
re-drawn arm to.

**This moves no band and grants no override.** ``WARN_BAND`` and ``REFUSE_BAND`` are untouched and
are read nowhere new. The superseded arm keeps its ``refuse`` verdict, keeps both ratios, and is
still printed by ``lab control`` and by ``lab run``, annotated with the id of the arm that retired
it -- because every sentence already written about that margin was quoted against a handicapped
opponent, and a reader who meets the new number has to be able to see the old one. This is a
measuring-stick rule, not an amnesty: nothing is forgiven, something better is measured. And the
hard gate still has no override -- this is the argued rule change its own refusal message invites,
made in code and argued in the commit, which is the only mechanism it has ever offered.
```

**Impact:** `test_the_module_records_the_control_shape_decision` asserts `"(D17)"`, `"M0248-R"`,
`"M0230-C50-R"`, `"M0243-NEAR20-R"`, `"dose-response"`, `"M0226-RAND2"`, `"M0241-PLACEBO"`,
`"M0072"`, `"M0047"`, `"amendment"` — all still present.

---

### Step 10: `hardgate.py` — `mis_shaped_controls` docstring

**File:** `engine/src/seer_engine/lab/hardgate.py:830-858`

**Change:** docstring only. **The body does not change**: it already returns
`control_shape.refusals(found)`, and `refusals` is where the narrowing lives.

**Code:** replace lines 830-858 with:

```python
def mis_shaped_controls(conn: sqlite3.Connection, method_id: str) -> tuple:
    """Every control arm of ``method_id`` whose shape is outside the refuse band (D17).

    Returns a tuple of ``control_shape.Finding`` in the method's own declaration order, and
    **never raises**. A control arm whose shape cannot be read at all -- no arm the id stems to
    and none that names itself the idea, a row carrying neither a trade count nor a turnover, a
    method with no file to read its arms from -- comes back from the reader as ``unresolved`` or
    ``unrecorded``, never as ``refuse``, and is not evidence of a handicap. Refusing a promotion
    on a number nobody computed is the mechanism by which a rule stops being about the thing it
    was written for. The same sentence is (D16)'s about the survivorship grid: absence is not
    evidence.

    **A superseded arm is not returned**, and that is ``control_shape.refusals``' doing rather
    than this function's: a refusal that a later, band-clean control of the same arm has retired
    reads ``blocking`` false while keeping its ``refuse`` verdict and both its ratios. The reader
    still reports it, ``lab control`` still prints it with the id of the arm that superseded it,
    and only this clause stops acting on it. Keeping the narrowing in one function is why the
    gate, ``lab run`` and ``lab control`` cannot disagree about one arm -- all three call it.

    ``control_shape`` is imported inside the body, not at this module's scope. It reads recorded
    ``trials`` rows and nothing else today, so a module-level import would work -- and would make
    the next edit to either module a fifty-fifty bet on an import cycle, exactly as ``Run``'s
    docstring in ``lab/runner.py`` says about this module. One dictionary lookup per promotion is
    the price.

    ``for_method`` reads the method's arms from its ``lab/methods/mNNNN_*.py`` file, which is the
    right reader here: a method with no file cannot be promoted at all -- ``prereg`` refuses it on
    the source sha long before anything reaches this clause.
    """
    from seer_engine.lab import control_shape

    try:
        found = control_shape.for_method(conn, method_id)
    except store.LabError:
        return ()
    return control_shape.refusals(found)
```

**Impact:** none at runtime.

---

### Step 11: `hardgate.py` — the D17 clause comment and one sentence of its message

**File:** `engine/src/seer_engine/lab/hardgate.py:1776-1798`

**Change:** the comment gains the supersession sentence; the message gains one clause so the way
back it names is the one the code now takes. No control flow changes.

**Code:** replace lines 1776-1798 with:

```python
    # (D17) A control arm exists to be the book's shape with none of its identity, so a margin
    # measured against a control that traded three times as often is partly fees and churn. The
    # reader never raises and only a measured mismatch refuses: a shape nobody could read comes
    # back `unresolved` or `unrecorded` and is left to the clauses below, because absence is not
    # evidence (D16). `lab run` prints this same reading and refuses nothing (D15).
    #
    # `mis_shaped_controls` is `control_shape.refusals`, which drops a refusal that a later,
    # band-clean control of the same arm has superseded. So re-drawing the control and running it
    # as an amendment -- the way back this message names -- is the way back this clause takes.
    # The superseded row keeps its verdict and still prints; it just stops blocking.
    off_shape = mis_shaped_controls(conn, method_id)
    if off_shape:
        from seer_engine.lab import control_shape

        low, high = control_shape.REFUSE_BAND
        said = "; ".join(control_shape.describe(f) for f in off_shape)
        raise store.LabError(
            f"{method_id} is not promoted: {said}. The band is {low:.2f}x to {high:.2f}x on both "
            f"axes, calibrated on every control arm the lab holds (D17). A control is the book's "
            f"shape with none of its identity, so 'this method beat its control by X' is not "
            f"sound when the control was handicapped -- part of X is the fees and the churn the "
            f"control paid and the book did not, and no one can say how much. The way back: "
            f"re-draw the control at the book's own trade count and turnover and run it again as "
            f"an amendment. That costs no method id, because an amendment appends trials under "
            f"this id, and it is what the 2026-10-19 handover asks for on M0248. Once the new "
            f"draw is recorded and lands inside "
            f"{control_shape.WARN_BAND[0]:.2f}x..{control_shape.WARN_BAND[1]:.2f}x on both axes "
            f"it supersedes this one here, and the arm above stays in the record with its ratios "
            f"rather than disappearing. Nothing was written and no status moved. There is no "
            f"override -- if the rule is wrong, change it in seer_engine/lab/hardgate.py and "
            f"argue for it in the commit"
        )
```

**Impact:** `test_a_mis_shaped_control_refuses_promotion_and_names_both_ratios` asserts
`"D17" in said`, `"no override" in said`, `"amendment" in said`, `"costs no method id" in said`,
the two ratios, the rung and the refuse-band phrase — all preserved verbatim.

---

### Step 12: `commands/lab.py` — the `lab control` help text

**File:** `engine/src/seer_engine/commands/lab.py:700-714`

**Change:** add the supersession sentence to `description=`. **No literal `%` is added** (the
parser's own comment at :695-698 and the repo invariant). `description=` is not interpolated, but
the rule is kept anyway.

**Code:** replace the `description=(...)` block at lines 700-714 with:

```python
        description=(
            "A control arm exists to be the real book's shape with none of its identity, so "
            "'the signal beat its control by X' is only sound when the two traded about as often "
            "and turned the book over about as fast. This prints every control, placebo and "
            "blind-draw arm the lab holds beside the arm it controls, as a trade-count ratio and "
            "a turnover ratio, and says whether each is clean, worth a warning, or outside the "
            "band the hard gate refuses on (lab/hardgate.py, D17). Both axes are mandatory: one "
            "recorded arm sits within 1.33x of its sibling on trades and 14.5x on turnover, so a "
            "trade-count check alone reads it as clean. A dose-response arm -- one whose "
            "different shape IS the treatment, like a deliberately stale signal date -- is listed "
            "as such and never flagged. An arm marked superseded is one a LATER control has "
            "retired by naming it: that later draw declared, before it ran, which measurement it "
            "replaces, and it matches its own book's shape on both axes, so the hard gate reads "
            "it and stops refusing on this one. A later arm never retires an earlier one merely "
            "by happening to control the same book -- a re-drawn control is usually aimed at a "
            "different arm on purpose, the one the old one should have been scored against -- so "
            "where the two differ the later arm's own target is printed beside its id. The "
            "superseded row is still printed, with its ratios and its verdict, because every "
            "margin already written against it was quoted against a handicapped opponent and "
            "that has to stay readable. Only a clean draw supersedes; a draw that merely warns "
            "does not, and neither does one with no recorded trial yet. Pure arithmetic "
            "over recorded trial rows: no research store is opened, no backtest runs, and no "
            "trial row, moments row, funding row, status or journal entry is written, so the "
            "lab's N and the test-window looks cannot move, web/data/lab.json does not change "
            "and `lab stage` is not needed."
        ),
```

**Impact:** `lab control --help` text only. `help=` is untouched.

---

### Step 13: `commands/lab.py` — the run's control print

**File:** `engine/src/seer_engine/commands/lab.py:1778-1798`

**Change:** name the superseded arms, and never claim "every control arm matches" while one is
present. The `elif` chain is broken so a supersession line and a warn line can both appear.

**Code:** replace lines 1778-1798 with:

```python
            off = cs.refusals(found)
            retired = [f for f in found if f.superseded_by is not None]
            warned = [f for f in cs.flags(found) if not f.refused]
            if retired:
                said = ", ".join(f"{f.control_id} by {f.superseded_by}" for f in retired)
                print(f"  {len(retired)} earlier control arm(s) superseded ({said}): a later draw "
                      f"of the same book matches")
                print("      its shape on both axes, so `lab promote` reads that one and no "
                      "longer refuses on the earlier")
                print("      arm (lab/hardgate.py, D17). The earlier rows stay above with their "
                      "ratios, because every margin")
                print("      written against them was quoted against a handicapped opponent.")
            if off:
                low, high = cs.REFUSE_BAND
                print(f"  *** {len(off)} control arm(s) outside {low:.2f}x..{high:.2f}x on at "
                      f"least one axis.")
                print("      A sentence of the form 'this beat its control by X' is quoted "
                      "against a handicapped opponent: part")
                print("      of X is the fees and the churn the control paid and this book did "
                      "not. Re-draw the control at")
                print("      this book's own trade count and turnover and amend -- that costs no "
                      "method id and the new draw")
                print("      supersedes this one. `lab promote` refuses this method until then "
                      "(lab/hardgate.py, D17); the")
                print("      trials above are recorded either way (D15).")
            elif warned:
                print(f"  {len(warned)} control arm(s) outside {cs.WARN_BAND[0]:.2f}x.."
                      f"{cs.WARN_BAND[1]:.2f}x but inside the refuse band -- worth a look before "
                      f"the margin is written up, not a refusal.")
            elif not retired:
                print("  Every control arm matches the arm it controls on both axes. A margin "
                      "measured against them is this book's own.")
```

**Impact:** `test_lab_run_prints_the_control_block_and_still_exits_zero` asserts
`"Control shape:"`, `"M0099-R"`, `"outside"` and `"lab/hardgate.py, D17"` are in the output. The
fixture has no superseded arm, so `off` is non-empty and all four substrings still print.

---

### Step 14: `commands/lab.py` — `_control`'s trailer

**File:** `engine/src/seer_engine/commands/lab.py:2859-2867`

**Change:** add the supersession block after the refusal block, and extend `_control`'s docstring.

**Code:** replace lines 2859-2867 with:

```python
    refused = cs.refusals(found)
    retired = [f for f in found if f.superseded_by is not None]
    if refused:
        low, high = cs.REFUSE_BAND
        print()
        print(f"{len(refused)} control arm(s) sit outside {low:.2f}x..{high:.2f}x on at least one")
        print("axis. `lab promote` refuses a method holding one (lab/hardgate.py, D17), and any")
        print("sentence already written about one of those margins is quoted against a")
        print("handicapped opponent. The way back costs no method id: re-draw the control at the")
        print("book's own trade count and turnover and run it again as an amendment, and the new")
        print("draw supersedes the old one here.")
    if retired:
        print()
        print(f"{len(retired)} control arm(s) are superseded: a later draw of the same book lands")
        print(f"inside {cs.WARN_BAND[0]:.2f}x..{cs.WARN_BAND[1]:.2f}x on both axes, so "
              f"`lab promote` reads that one and no longer")
        print("refuses on the earlier arm (lab/hardgate.py, D17). A later draw retires an")
        print("earlier one only by naming it in the declaration committed before it ran, so where")
        print("the two control different arms the later one's own target is printed beside its")
        print("id. The earlier rows stay in the table above, with their ratios and their verdict,")
        print("because every margin already written against them was quoted against the")
        print("handicapped opponent and the record of that has to stay readable.")
```

and extend the docstring at lines 2829-2834 by appending one paragraph before the "One thing this
does read…" paragraph:

```python
    An arm the table marks ``superseded`` is one a later control has retired by NAMING it: that
    later draw declared, in the commit that pre-registered it, which measurement it replaces, and
    it is clean on both axes of its own book, so ``lab promote`` reads it and stops refusing on
    the earlier one (``hardgate`` D17). Where the two control different arms -- which is usual,
    because a re-drawn control is deliberately aimed at the arm the old one should have been
    scored against -- the later arm's own target is printed beside its id. The earlier row is
    still printed, with its ratios and its ``refuse`` verdict, because this report is also the
    record of which written margins were quoted against a handicapped opponent. Only a clean draw
    supersedes -- not a warn, not an arm it did not name, and not one whose trial is not recorded
    yet.
```

**Impact:** `test_lab_control_reports_every_arm_and_writes_nothing` asserts `"M0001-R"`,
`"M0002-R"`, `"refuse"`, `"ok"`, the two counter lines and byte-equality of the database. Its
fixture has no superseded arm, so `retired` is empty and nothing new prints.

---

### Step 15: `test_lab_control_shape.py` — the fixture-level rule

**File:** `engine/tests/test_lab_control_shape.py:360` (append after
`test_show_clean_false_keeps_only_what_must_be_acted_on`, which ends at line 359, and before the
`# --- the calibration table` banner at line 362)

**Code:** insert this block:

```python
# ------------------------------------------------------------------ supersession


def _declaring(stub, *ids):
    """``stub`` with a ``supersedes`` declaration on it, however ``Stub`` is built.

    ``control_shape`` reads the attribute duck-typed through ``SUPERSEDES_ATTR``, exactly as it
    reads ``DECLARATION_ATTR``, so a test arm declares by carrying the attribute and nothing in
    this module has to import ``backtest.dev``."""
    object.__setattr__(stub, cs.SUPERSEDES_ATTR, tuple(ids))
    return stub


def _finding(**kw) -> cs.Finding:
    """A Finding built by hand, for the one case `findings` cannot produce in a single method.

    An `unresolved` arm and a resolved refusal cannot coexist under one method id: `resolve_target`
    returns (None, None) only when the eligible set is empty, and an eligible set that is empty for
    one placebo is empty for all of them. So the predicate is exercised directly for that case.
    """
    base = dict(
        method_id="M9999", control_id="M9999-R", kind=cs.KIND_PLACEBO, target_id="M9999-CORE",
        rung=cs.RUNG_STEM, control=None, target=None, trade_ratio=1.0, turnover_ratio=1.0,
        verdict=cs.OK, reason="r", declares=(),
    )
    base.update(kw)
    return cs.Finding(**base)


def test_a_band_clean_placebo_that_declares_a_refused_one_supersedes_it(conn):
    """The whole point of the rule: an honest control retires the handicapped one it NAMES.

    The refusal is NOT dropped. Its verdict is still refuse, both ratios are still there and it is
    still flagged -- the sentence already written about its margin was quoted against a
    handicapped opponent and that stays readable. Only `blocking` goes false, and `refusals` --
    which is what `hardgate` acts on -- is what reads `blocking`.
    """
    _lab(conn, "M9020", [("M9020-CORE", 500, 2.0),
                         ("M9020-R", 35, 0.14),
                         ("M9020-CORE-PLC", 505, 2.02)])
    arms = [Stub("M9020-CORE", R_CORE), Stub("M9020-R", R_C50_R),
            _declaring(Stub("M9020-CORE-PLC", R_C50_R), "M9020-R")]
    found = cs.findings(conn, "M9020", arms)
    by_id = {f.control_id: f for f in found}

    old, new = by_id["M9020-R"], by_id["M9020-CORE-PLC"]
    assert old.verdict == cs.REFUSE and round(old.trade_ratio, 2) == 0.07
    assert new.verdict == cs.OK and new.superseded_by is None
    assert new.declares == ("M9020-R",)

    assert old.superseded_by == "M9020-CORE-PLC"
    assert old.superseded_by_target == new.target_id
    assert old.refused is True and old.flagged is True       # still reported, never dropped
    assert old.blocking is False                             # and no longer stopping a promotion
    assert cs.refusals(found) == ()
    assert old in cs.flags(found)
    assert "superseded by M9020-CORE-PLC" in cs.describe(old)


def test_a_clean_placebo_that_declares_nothing_supersedes_nothing(conn):
    """The condition that makes this a measured no-op on the committed lab, where no arm declares.

    It is also the half of the rule that replaced target equality: a well-shaped control of the
    same book is NOT evidence that it was drawn to replace the bent one, and before 2026-10-19
    nobody had ever been asked to say so.
    """
    _lab(conn, "M9027", [("M9027-CORE", 500, 2.0),
                         ("M9027-R", 35, 0.14),
                         ("M9027-CORE-PLC", 505, 2.02)])
    arms = [Stub("M9027-CORE", R_CORE), Stub("M9027-R", R_C50_R), Stub("M9027-CORE-PLC", R_C50_R)]
    found = cs.findings(conn, "M9027", arms)
    by_id = {f.control_id: f for f in found}
    assert by_id["M9027-CORE-PLC"].verdict == cs.OK          # same target, clean, declares nothing
    assert by_id["M9027-CORE-PLC"].target_id == by_id["M9027-R"].target_id
    assert by_id["M9027-R"].superseded_by is None
    assert [f.control_id for f in cs.refusals(found)] == ["M9027-R"]


def test_a_warn_superseder_does_not_supersede_even_when_it_declares(conn):
    """Measured on the committed lab: under an OK-or-WARN band M0047-PLC1-MV20 (0.545x) would
    retire M0047-PLC1-MV10 (0.549x) -- one bent stick replacing another, with no honest control
    drawn. The arm doing the retiring has to clear the MATCH band, not merely the refuse band."""
    _lab(conn, "M9021", [("M9021-CORE", 500, 2.0),
                         ("M9021-R", 35, 0.14),
                         ("M9021-CORE-PLC", 700, 2.8)])
    arms = [Stub("M9021-CORE", R_CORE), Stub("M9021-R", R_C50_R),
            _declaring(Stub("M9021-CORE-PLC", R_C50_R), "M9021-R")]
    found = cs.findings(conn, "M9021", arms)
    by_id = {f.control_id: f for f in found}
    assert by_id["M9021-CORE-PLC"].verdict == cs.WARN      # 1.40x: inside refuse, outside match
    assert by_id["M9021-R"].superseded_by is None
    assert [f.control_id for f in cs.refusals(found)] == ["M9021-R"]


def test_a_declared_supersession_crosses_a_different_target_on_purpose(conn):
    """The reason target equality was dropped, as a test rather than as an argument.

    `M9022-R` resolves to `M9022-CORE` -- the ladder's own guess. The arm drawn to replace it is
    named after its TRUE target and so resolves to `M9022-WIDE`. Under a target-equality rule
    nothing would be superseded and the method would stay blocked after all the measuring; under
    the declaration it is superseded, and BOTH targets are reported so the re-point is visible.
    """
    _lab(conn, "M9022", [("M9022-CORE", 500, 2.0),
                         ("M9022-WIDE", 900, 3.6),
                         ("M9022-R", 35, 0.14),
                         ("M9022-WIDE-PLC", 909, 3.64)])
    arms = [Stub("M9022-CORE", R_CORE), Stub("M9022-WIDE", R_PLAIN),
            Stub("M9022-R", R_C50_R),
            _declaring(Stub("M9022-WIDE-PLC", R_C50_R), "M9022-R")]
    found = cs.findings(conn, "M9022", arms)
    by_id = {f.control_id: f for f in found}
    old, new = by_id["M9022-R"], by_id["M9022-WIDE-PLC"]
    assert old.target_id == "M9022-CORE" and new.target_id == "M9022-WIDE"
    assert new.verdict == cs.OK
    assert old.superseded_by == "M9022-WIDE-PLC"
    assert old.superseded_by_target == "M9022-WIDE"
    assert cs.refusals(found) == ()
    said = cs.describe(old)
    assert "M9022-WIDE-PLC" in said and "M9022-WIDE" in said and "M9022-CORE" in said
    assert "M9022-WIDE-PLC -> M9022-WIDE" in cs.format_report(found)


def test_one_clean_arm_does_not_excuse_a_sibling_it_did_not_name(conn):
    """The other half of why target equality went. `M0215-HASH` and `M0215-HASH-CAP4` both resolve
    to `M0215-CTRL`, so under equality one honest control of CTRL would excuse an arm whose job is
    to price what a cap does and which was never scored against CTRL in spirit. Each old arm is
    retired by the arm that names it, and by no other."""
    _lab(conn, "M9028", [("M9028-CORE", 500, 2.0),
                         ("M9028-R", 35, 0.14),
                         ("M9028-R2", 36, 0.15),
                         ("M9028-CORE-PLC", 505, 2.02)])
    arms = [Stub("M9028-CORE", R_CORE), Stub("M9028-R", R_C50_R), Stub("M9028-R2", R_C50_R),
            _declaring(Stub("M9028-CORE-PLC", R_C50_R), "M9028-R")]
    found = cs.findings(conn, "M9028", arms)
    by_id = {f.control_id: f for f in found}
    assert by_id["M9028-R"].target_id == by_id["M9028-R2"].target_id == "M9028-CORE"
    assert by_id["M9028-R"].superseded_by == "M9028-CORE-PLC"
    assert by_id["M9028-R2"].superseded_by is None
    assert [f.control_id for f in cs.refusals(found)] == ["M9028-R2"]


def test_a_warn_arm_is_superseded_too_although_it_never_blocked(conn):
    """`M0047-PLC1-MV20` is the lab's one such arm: 0.545x / 0.508x, inside the refuse band and
    outside the match band. It stops no promotion, so retiring it moves no gate -- but every
    margin written against it is as little evidence as its refused twin's, and leaving one of a
    re-drawn pair unmarked would tell a reader the opposite."""
    _lab(conn, "M9029", [("M9029-CORE", 500, 2.0),
                         ("M9029-W", 350, 1.40),
                         ("M9029-CORE-PLC", 505, 2.02)])
    arms = [Stub("M9029-CORE", R_CORE), Stub("M9029-W", R_C50_R),
            _declaring(Stub("M9029-CORE-PLC", R_C50_R), "M9029-W")]
    found = cs.findings(conn, "M9029", arms)
    by_id = {f.control_id: f for f in found}
    assert by_id["M9029-W"].verdict == cs.WARN
    assert by_id["M9029-W"].superseded_by == "M9029-CORE-PLC"
    assert by_id["M9029-W"].blocking is False
    assert by_id["M9029-W"] in cs.flags(found)               # still a "read this" row
    assert cs.refusals(found) == ()


def test_an_unrecorded_or_unresolved_sibling_never_supersedes(conn):
    """Absence is not evidence (D16's sentence), and this is the case that matters in practice.

    A re-drawn control is committed to the method file BEFORE it is run -- the commit is the
    pre-registration. Between that commit and the run the new arm has no trial row, so its finding
    is `unrecorded`. If that superseded, the gate would clear on the intention rather than on the
    measurement, and the whole pre-registration discipline would be bypassable by writing a
    docstring.
    """
    _lab(conn, "M9023", [("M9023-CORE", 500, 2.0), ("M9023-R", 35, 0.14)])
    arms = [Stub("M9023-CORE", R_CORE), Stub("M9023-R", R_C50_R),
            _declaring(Stub("M9023-CORE-PLC", R_C50_R), "M9023-R")]
    found = cs.findings(conn, "M9023", arms)
    by_id = {f.control_id: f for f in found}
    assert by_id["M9023-CORE-PLC"].verdict == cs.UNRECORDED
    assert by_id["M9023-R"].superseded_by is None
    assert [f.control_id for f in cs.refusals(found)] == ["M9023-R"]

    bent = _finding(method_id="M9023", control_id="M9023-R", verdict=cs.REFUSE,
                    trade_ratio=0.07, turnover_ratio=0.07, target_id="M9023-CORE")
    unresolved = _finding(method_id="M9023", control_id="M9023-S", verdict=cs.UNRESOLVED,
                          target_id=None, rung=None, trade_ratio=None, turnover_ratio=None)
    assert cs.superseding_arm(bent, (bent, unresolved)) is None


def test_a_dose_response_sibling_never_supersedes(conn):
    """A dose arm carries no ratio at all, so it is nobody's measuring stick.

    If it superseded, `kind_of`'s dose-before-draw ordering would become the way to clear D17: word
    the re-drawn control as a dose and the refusal disappears with nothing measured. The ordering
    exists to protect a correct arm from a false alarm, not to hand out a bypass.
    """
    _lab(conn, "M9024", [("M9024-CORE", 500, 2.0),
                         ("M9024-R", 35, 0.14),
                         ("M9024-STALE", 505, 2.02)])
    arms = [Stub("M9024-CORE", R_CORE), Stub("M9024-R", R_C50_R),
            _declaring(Stub("M9024-STALE", R_STALE30), "M9024-R")]
    found = cs.findings(conn, "M9024", arms)
    by_id = {f.control_id: f for f in found}
    assert by_id["M9024-STALE"].kind == cs.KIND_DOSE
    assert by_id["M9024-STALE"].verdict == cs.NOT_CHECKED
    assert by_id["M9024-R"].superseded_by is None
    assert [f.control_id for f in cs.refusals(found)] == ["M9024-R"]
    # And a shape-matched arm that is not a control at all (M9024-CORE itself) produces no
    # finding, so it cannot supersede either.
    assert "M9024-CORE" not in by_id


def test_a_superseded_arm_stays_in_the_report_with_its_ratios(conn):
    """Still reported, never dropped -- in both the full report and the act-on-this-only one."""
    _lab(conn, "M9025", [("M9025-CORE", 500, 2.0),
                         ("M9025-R", 35, 0.14),
                         ("M9025-CORE-PLC", 505, 2.02)])
    arms = [Stub("M9025-CORE", R_CORE), Stub("M9025-R", R_C50_R),
            _declaring(Stub("M9025-CORE-PLC", R_C50_R), "M9025-R")]
    found = cs.findings(conn, "M9025", arms)

    text = cs.format_report(found)
    assert "M9025-R" in text and "0.07" in text and cs.REFUSE in text
    assert "superseded by" in text and "M9025-CORE-PLC" in text
    assert "has to stay readable" in text

    loud = cs.format_report(found, show_clean=False)
    assert "M9025-R" in loud and "superseded by" in loud


def test_the_report_grows_no_column_when_nothing_is_superseded(conn):
    """Sixty-four rows of dashes to carry information in none of them is noise, so the column
    appears only when it says something, and today's report is unchanged."""
    _lab(conn, "M9026", [("M9026-CORE", 500, 2.0), ("M9026-R", 2000, 8.0)])
    arms = [Stub("M9026-CORE", R_CORE), Stub("M9026-R", R_C50_R)]
    assert "superseded by" not in cs.format_report(cs.findings(conn, "M9026", arms))
```

**Impact:** ten new tests and one new helper. `_lab`, `conn`, `Stub`, `R_CORE`, `R_C50_R`,
`R_PLAIN` and `R_STALE30` all already exist in the module. `_declaring` uses
`object.__setattr__` because `Stub` may be frozen; if it is a plain class a direct assignment is
equivalent and either is fine, since the module under test reads the attribute duck-typed.

---

### Step 16: `test_lab_control_shape.py` — the nine-method no-op proof

**File:** `engine/tests/test_lab_control_shape.py:487` (append at the end of the file)

**Code:**

```python
# ------------------------------------------------------------------ the nine D17 blocks

# The thirteen refuse-band control arms the committed lab holds across the nine dev-eligible
# methods D17 stops, re-derived read-only on 2026-10-19 and matching `lab control` to the second
# decimal. These rows are frozen (trials_no_update, trials_no_delete), so the ratios can never
# move; the method files that name the arms are append-only in practice for the same reason.
BLOCKED_NINE: dict[str, tuple[tuple[str, str, float, float], ...]] = {
    "M0047": (("M0047-PLC1-MV10", "M0047-EQ", 0.549, 0.496),),
    "M0201": (("M0201-PLC1-MV10", "M0201-Y20-MV10", 2.266, 2.135),
              ("M0201-PLC2-MV10", "M0201-Y20-MV10", 2.261, 2.117)),
    "M0202": (("M0202-PLC1-HALF", "M0202-Y20-HALF", 2.248, 2.005),
              ("M0202-PLC2-HALF", "M0202-Y20-HALF", 2.245, 1.993),
              ("M0202-PLC1-HALF-FAST", "M0202-Y20-HALF", 2.248, 2.200)),
    "M0208": (("M0208-HASH-N20", "M0208-CGO-N20", 4.405, 5.197),),
    "M0215": (("M0215-HASH", "M0215-CTRL", 0.339, 0.428),
              ("M0215-HASH-CAP4", "M0215-CTRL", 0.339, 0.429)),
    "M0221": (("M0221-R50", "M0221-C50", 0.211, 0.498),),
    "M0225": (("M0225-R50", "M0225-C50", 0.195, 0.424),),
    "M0227": (("M0227-R20", "M0227-S20", 0.067, 0.117),),
    "M0243": (("M0243-NEAR20-R", "M0243-NEAR20", 3.013, 2.976),),
}


def test_supersession_moves_no_verdict_on_the_committed_lab():
    """The no-op proof, at the finding level: every one of the thirteen still reads `refuse`.

    This is the half of the rule that is true forever. `superseded_by` narrows what a GATE acts on;
    it never moves a verdict and never removes a row, because the old draw is the record of what
    every margin written against it was worth. A refusal that vanished from the report would be an
    amnesty, and this assertion is what stops one being written by accident.
    """
    conn = _committed_lab()
    if conn is None:
        pytest.skip("no lab database")
    before = hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest()
    try:
        found = cs.survey(conn, tuple(BLOCKED_NINE))
    finally:
        conn.close()
    assert hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest() == before

    by_id = {f.control_id: f for f in found}
    for mid, arms in BLOCKED_NINE.items():
        for control_id, target_id, trades, turnover in arms:
            if control_id not in by_id:
                pytest.skip(f"{control_id} is not in this tree's lab database")
            f = by_id[control_id]
            assert (f.method_id, f.kind, f.target_id) == (mid, cs.KIND_PLACEBO, target_id)
            assert f.verdict == cs.REFUSE, f"{control_id} is no longer reported as a refusal"
            assert round(f.trade_ratio, 3) == trades
            assert round(f.turnover_ratio, 3) == turnover


def test_nothing_in_the_committed_lab_is_superseded_today():
    """The no-op proof, lab-wide: on this tree's database the rule retires nothing at all.

    Measured 2026-10-19 over every method file: 64 findings, 19 refusals, 0 supersessions, before
    the change and after it. The nine blocked methods stay blocked until an honest control is drawn
    and RUN -- a committed-but-unrun amendment reads `unrecorded` and never supersedes, which is
    why this stays true for the whole of the 2026-10-19 plan set and flips only once phase 8 stages
    the new trials into lab/lab.sqlite.
    """
    conn = _committed_lab()
    if conn is None:
        pytest.skip("no lab database")
    try:
        found = cs.survey(conn)
    finally:
        conn.close()
    assert found, "the committed lab holds control arms; the survey found none"
    for f in found:
        if f.superseded_by is None:
            continue
        honest = {g.control_id: g for g in found}[f.superseded_by]
        assert honest.verdict == cs.OK
        assert honest.kind == cs.KIND_PLACEBO
        assert honest.target_id == f.target_id
        assert honest.method_id == f.method_id
    assert cs.refusals(found) == tuple(f for f in found if f.verdict == cs.REFUSE), (
        "supersession retired a refusal on the committed lab; it must retire none until an "
        "honestly shaped control has been drawn, DECLARED and run"
    )
    assert not [f for f in found if f.declares], (
        "no arm in the committed lab declares a supersession, so the rule cannot fire; if this "
        "goes red an amendment landed and the no-op claim above is now about a different lab"
    )


def test_every_blocked_method_keeps_a_d17_reading_either_way():
    """Forever-true: each of the nine either still blocks, or holds the honest control that
    retired it -- never neither, and never a refusal that simply disappeared."""
    conn = _committed_lab()
    if conn is None:
        pytest.skip("no lab database")
    try:
        found = cs.survey(conn, tuple(BLOCKED_NINE))
    finally:
        conn.close()
    for mid, arms in BLOCKED_NINE.items():
        mine = [f for f in found if f.method_id == mid]
        if not mine:
            pytest.skip(f"{mid} is not in this tree's lab database")
        reported = {f.control_id for f in mine if f.verdict == cs.REFUSE}
        assert {a[0] for a in arms} <= reported, f"{mid}: a refusal disappeared from the report"
        assert cs.refusals(mine) or [f for f in mine if f.superseded_by is not None], (
            f"{mid} is no longer read by D17 at all"
        )
```

**Impact:** three new tests. `hashlib`, `pytest`, `store` and `_committed_lab` already exist in the
module.

---

### Step 17: `test_lab_hardgate.py` — imports

**File:** `engine/tests/test_lab_hardgate.py:9-13`

**Change:** the committed-lab test needs `hashlib` and `sqlite3`.

**Code:** replace lines 9-13

```python
import argparse
import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
```

with

```python
import argparse
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
```

**Impact:** none beyond enabling Step 19. Ruff's `F401` is in `ignore`, but both are used anyway.

---

### Step 18: `test_lab_hardgate.py` — supersession at the gate

**File:** `engine/tests/test_lab_hardgate.py:1411` (insert between
`test_a_matched_control_promotes`, which ends at line 1410, and
`test_a_dose_response_arm_is_never_refused_for_its_shape` at line 1413)

**Code:**

```python
def test_an_honest_control_supersedes_the_handicapped_one_and_the_gate_passes(conn, monkeypatch):
    """(D17) The way back, tested rather than quoted.

    `M0001-R` is M0230's shape -- 18 trades against 250, 0.15 turnover against 1.1 -- and refuses.
    `M0001-A-PLC` is a later control of the same arm at 1.01x / 0.98x. The old arm cannot be
    removed: a method file's recorded trials pin its candidates and `trials` is append-only by
    trigger. Before this rule the re-draw changed nothing and the method stayed blocked forever.
    """
    from seer_engine.lab import control_shape as cs

    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)                      # M0001-A, 250 trades, turnover 1.1
    _control_arm(conn, "M0001", "R", trades=18, turnover=0.15)
    _control_arm(conn, "M0001", "A-PLC", trades=252, turnover=1.08)
    plc = _Arm("M0001-A-PLC", R_DRAW)
    object.__setattr__(plc, cs.SUPERSEDES_ATTR, ("M0001-R",))   # the declaration IS the rule
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-R", R_DRAW), plc])

    found = {f.control_id: f for f in cs.for_method(conn, "M0001")}
    assert found["M0001-A-PLC"].verdict == cs.OK
    assert found["M0001-R"].verdict == cs.REFUSE          # still measured, still reported
    assert found["M0001-R"].superseded_by == "M0001-A-PLC"
    assert found["M0001-R"].blocking is False

    assert hardgate.mis_shaped_controls(conn, "M0001") == ()
    hardgate.check(conn, "M0001")                            # and the gate no longer refuses


def test_a_clean_redraw_that_declares_nothing_does_not_pass_the_gate(conn, monkeypatch):
    """The condition that makes the rule a no-op on today's lab, at the gate.

    `M0001-A-PLC` is clean, is a placebo and resolves to the same arm `M0001-R` does. Under the
    target-equality rule the draft proposed, that would clear D17. It does not clear it here,
    because the arm never said it was replacing anything -- and the lab holds 46 placebo arms
    that were never asked to say so.
    """
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _control_arm(conn, "M0001", "R", trades=18, turnover=0.15)
    _control_arm(conn, "M0001", "A-PLC", trades=252, turnover=1.08)
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-R", R_DRAW),
                                 _Arm("M0001-A-PLC", R_DRAW)])
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    assert "M0001-R" in str(e.value)


def test_a_redraw_that_only_warns_does_not_supersede_at_the_gate(conn, monkeypatch):
    """1.40x / 1.41x is inside the refuse band and outside the match band: still a bent stick.

    Measured on the committed lab, the loose reading would retire M0047's 0.549x control with its
    own 0.545x twin and unblock the method with nothing honest drawn. The replacement has to clear
    WARN_BAND.
    """
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _control_arm(conn, "M0001", "R", trades=18, turnover=0.15)
    _control_arm(conn, "M0001", "A-PLC", trades=350, turnover=1.55)
    from seer_engine.lab import control_shape as cs

    plc = _Arm("M0001-A-PLC", R_DRAW)
    object.__setattr__(plc, cs.SUPERSEDES_ATTR, ("M0001-R",))
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-R", R_DRAW), plc])
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    assert "M0001-R" in str(e.value)


def test_an_unrun_redraw_does_not_supersede_at_the_gate(conn, monkeypatch):
    """The commit is the pre-registration, and it lands BEFORE the run. Between the two the new
    arm has no trial row, reads `unrecorded`, and must not clear the gate: otherwise D17 would be
    satisfied by an intention rather than by a measurement."""
    from seer_engine.lab import control_shape as cs

    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _control_arm(conn, "M0001", "R", trades=18, turnover=0.15)
    plc = _Arm("M0001-A-PLC", R_DRAW)
    object.__setattr__(plc, cs.SUPERSEDES_ATTR, ("M0001-R",))   # declared, but never run
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-R", R_DRAW), plc])
    found = {f.control_id: f for f in cs.for_method(conn, "M0001")}
    assert found["M0001-A-PLC"].verdict == cs.UNRECORDED
    assert found["M0001-R"].superseded_by is None
    with pytest.raises(store.LabError):
        hardgate.check(conn, "M0001")
```

**Impact:** four tests. `_control_arm(conn, "M0001", "A-PLC", ...)` records candidate
`M0001-A-PLC`, whose stem `M0001-A` is eligible, so it resolves by `sibling-stem` to the same arm
`M0001-R` reaches through `declared-idea` (`R_IDEA` opens "The idea:"). That both targets agree
here is now **incidental** rather than the condition under test — the condition is the
declaration, and `test_a_clean_redraw_that_declares_nothing_does_not_pass_the_gate` is the
negative that proves it, with the targets still agreeing and the gate still refusing.

---

### Step 19: `test_lab_hardgate.py` — the committed-lab no-op at the gate

**File:** `engine/tests/test_lab_hardgate.py:1457` (insert after
`test_a_shape_that_cannot_be_read_does_not_refuse`, which ends at line 1456, and before
`test_lab_promote_exits_2_and_writes_nothing_on_a_mis_shaped_control` at line 1459)

**Code:**

```python
# The nine dev-eligible methods D17 stops today, named in (D17)'s own text. Measured read-only on
# 2026-10-19 against this tree's committed lab: all nine refuse, on thirteen arms between them.
BLOCKED_NINE: tuple[str, ...] = (
    "M0047", "M0201", "M0202", "M0208", "M0215", "M0221", "M0225", "M0227", "M0243",
)


def test_supersession_unblocks_none_of_the_nine_until_an_honest_control_runs():
    """(D17) The no-op proof at the gate. A rule change that quietly promoted nine methods would
    be the worst possible outcome of this edit, so it is asserted rather than reasoned about.

    `store.COMMITTED_DB` -- this tree's `lab/lab.sqlite`, opened mode=ro and never through
    `store.connect`, which migrates and so dirties the file on a read. The bytes are hashed either
    side.

    Each method is allowed one of exactly two states, and never neither: still blocking, or holding
    the band-clean control that retired its refusal -- with the refusal still reported. On this
    tree today every one of the nine is in the first state.
    """
    from seer_engine.lab import control_shape as cs

    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    before = hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest()
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for mid in BLOCKED_NINE:
            found = cs.for_method(conn, mid)
            if not found:
                pytest.skip(f"{mid} has no method file or no control arm in this tree")
            off = hardgate.mis_shaped_controls(conn, mid)
            retired = [f for f in found if f.superseded_by is not None]
            assert off or retired, f"{mid} is no longer read by D17 at all"
            assert off == cs.refusals(found)
            for f in retired:
                assert f.verdict == cs.REFUSE      # superseded, never dropped
                assert f.trade_ratio is not None or f.turnover_ratio is not None
    finally:
        conn.close()
    assert hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest() == before
```

**Impact:** reads only. The hash assertion is the same guard
`test_the_calibration_table_is_what_the_code_computes` already uses.

---

### Step 20: `test_lab_hardgate.py` — D17's docstring records the rule

**File:** `engine/tests/test_lab_hardgate.py:1361-1371`

**Change:** two assertions, so the prose cannot be dropped silently.

**Code:** replace lines 1361-1371 with:

```python
def test_the_module_records_the_control_shape_decision():
    """(D17) is written down where the other sixteen are, with its calibration in it."""
    doc = hardgate.__doc__ or ""
    assert "(D17)" in doc
    assert "M0248-R" in doc and "M0230-C50-R" in doc and "M0243-NEAR20-R" in doc
    assert "dose-response" in doc
    # The two cases the band has to separate, both named in the text.
    assert "M0226-RAND2" in doc and "M0241-PLACEBO" in doc
    # The reconciled fact, both halves, and the way back.
    assert "M0072" in doc and "M0047" in doc
    assert "amendment" in doc
    # The supersession rule, and the measurement that made it `ok` and not `ok or warn`.
    assert "SUPERSEDES" in doc or "superseded" in doc
    assert "M0047-PLC1-MV20" in doc
```

**Impact:** both substrings are added by Step 9.

---

## Verification

Run every command from the worktree root, with the branch on `PYTHONPATH` (memory
`seer-worktree-tests-need-pythonpath`: without it pytest silently tests the main checkout).

**Targeted (fast, run first):**

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw && \
PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src \
  /home/miftah/seer/engine/.venv/bin/pytest -n0 \
  engine/tests/test_lab_control_shape.py \
  engine/tests/test_lab_hardgate.py \
  engine/tests/test_lab_methods.py
```

`test_lab_methods.py` is in the targeted set even though this phase touches no method file: it
carries `test_every_recorded_configuration_still_digests_to_its_recorded_digest`, which is the
plan set's invariant 1, and running it here proves this phase moved no digest.

**Build / full suite:**

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw && \
docker start seer-pg 2>/dev/null; \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src \
  /home/miftah/seer/engine/.venv/bin/pytest engine/tests
```

**Lint:**

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw && \
  /home/miftah/seer/engine/.venv/bin/ruff check engine
```

**Manual check — the no-op, measured, not reasoned about.** Read-only, no `lab` subcommand (a
`lab` command migrates `lab.sqlite` on connect; this phase must leave the file untouched):

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw && \
git hash-object lab/lab.sqlite && \
PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src \
  /home/miftah/seer/engine/.venv/bin/python - <<'PY'
import sqlite3
from seer_engine.lab import control_shape as cs, store
conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
found = cs.survey(conn)
sup = [f for f in found if f.superseded_by]
print("findings", len(found), "refusals", len(cs.refusals(found)), "superseded", len(sup))
conn.close()
PY
git hash-object lab/lab.sqlite
```

Expected, unchanged from the pre-change measurement: `findings 64 refusals 19 superseded 0`, and
the two `git hash-object` lines identical
(`3969f1fa5d2066a42ed47716dd05a66050073592` at the time of planning).

**Exit criteria:**

1. `superseding_arm` exists, requires `verdict == OK` of the superseding arm, requires the
   declaration, imposes **no** target-equality condition, and reads no band constant of its own.
2. On the committed lab: **64 findings, 19 refusals, 0 supersessions** — the change moves no
   verdict and unblocks none of the nine — and `no arm in the committed lab declares anything`,
   which is the stronger reason.
3. All thirteen refuse-band arms across the nine still read `refuse` and still carry their exact
   recorded ratios (`BLOCKED_NINE`).
4. A band-clean placebo that **declares** a refusal retires it, across a *different* resolved
   target, with both targets reported; and a clean placebo that declares nothing, a `warn`
   superseder, an arm a clean superseder did not name, an `unrecorded` superseder, an
   `unresolved` superseder and a dose-response superseder each do **not** — all asserted. A
   `warn` finding that is declared **is** superseded, and stays flagged.
5. A superseded arm is still in `format_report`'s output, with its ratios, its `refuse` verdict and
   the id of the arm that retired it.
6. D17's docstring carries the rule **and** the argument for it, including the M0047 measurement.
7. `pytest engine/tests` green and `ruff check engine` clean.
8. `git hash-object lab/lab.sqlite` is unchanged and `git status` shows no change under `lab/` or
   `web/data/`.

---

## Commit

One commit, by pathspec (the checkout is shared — index invariant 9: no `git add -A`, no
`git reset --hard`, no `git pull --rebase` while the batch is running):

```bash
git add engine/src/seer_engine/lab/control_shape.py \
        engine/src/seer_engine/lab/hardgate.py \
        engine/src/seer_engine/commands/lab.py \
        engine/tests/test_lab_control_shape.py \
        engine/tests/test_lab_hardgate.py \
        .workflows/plan/honest-control-redraw/phase-2.md
```

Message:

```
lab: an honestly shaped control now supersedes the handicapped one it replaces

D17 refused a method holding a control arm outside [0.50, 2.00] and its own
message named the way back -- "re-draw the control at the book's own trade count
and turnover and run it again as an amendment". The code did not honour that
sentence. A method file is append-only in practice (its recorded trials pin its
candidates) and `trials` is append-only by trigger, so the handicapped arm stays
in all_candidates() and keeps its row forever: re-drawing added a clean arm beside
the bent one, `control_shape.refusals` kept returning the bent one, and the gate
kept raising. All nine dev-eligible methods D17 blocks would have done the
measuring and stayed exactly as blocked. A rule whose stated remedy remedies
nothing is a rule nobody can satisfy, and this module has already written down
(D16) what it thinks of those.

The rule, and it is narrow on purpose: a `refuse` or `warn` finding is SUPERSEDED
when the same method holds another `placebo` arm that is itself clean on both axes
AND that NAMES it in its own pre-registered declaration (Candidate.supersedes,
read duck-typed through control_shape.SUPERSEDES_ATTR exactly as DECLARATION_ATTR
is). `Finding.superseded_by` carries the id and `superseded_by_target` the
superseding arm's own target; a new `blocking` property is `refused and
superseded_by is None`; `refusals` -- the one function the gate, `lab run` and
`lab control` all read -- filters on `blocking`. `hardgate.mis_shaped_controls`
needed no code change at all.

DECLARED, and deliberately NOT inferred from the target. "Another clean placebo on
the same target_id" was the obvious rule and it is wrong in both directions. Too
strict: the <target-id>-PLC convention re-points a re-drawn arm at the book it
actually controls, so M0047-MV10-PLC resolves to M0047-MV10 while the arm it
replaces resolves, on the ladder's weakest rung, to M0047-EQ -- equality would
leave M0047 and M0202 blocked after every measurement had been taken. Too loose:
M0215-HASH and M0215-HASH-CAP4 both resolve to M0215-CTRL, so one honest control
of CTRL would excuse an arm whose stated job is to price what a cap does. A
resolution this module itself labels a guess is not a fact to build a gate rule
on. `lab control` prints both targets, so a re-point is visible rather than hidden.

Four things deliberately do not supersede: a `warn` SUPERSEDER, an arm that
DECLARES NOTHING (which is every arm in the lab today), an
`unresolved`/`unrecorded`/`not-checked` superseder, and a dose-response or
within-frame arm. The third is the one that matters in practice -- the commit is
the pre-registration and lands BEFORE the run, so between them the new arm reads
`unrecorded`; letting that supersede would clear the gate on an intention rather
than on a measurement. The fourth would have turned `kind_of`'s dose-before-draw
ordering into a way of clearing D17 by wording the rationale.

The superseded arm is NOT dropped. Its verdict stays `refuse`, it keeps both
ratios and its reason, it stays `flagged`, and `lab control` and `lab run` print
it annotated with the id of the arm that retired it. Every sentence already
written about that margin was quoted against a handicapped opponent, and a reader
meeting the new number has to be able to see the old one. This is a
measuring-stick rule, not an amnesty.

Measured, not predicted:

- No-op on today's lab: 64 findings, 19 refusals, 0 supersessions, before and
  after -- and for the stronger reason that NO arm in the committed lab declares
  anything at all, which a test asserts directly. None of M0047, M0201, M0202,
  M0208, M0215, M0221, M0225, M0227 or M0243 is unblocked by this commit; all
  thirteen refuse-band arms still read `refuse` with their recorded ratios
  unmoved, pinned in BLOCKED_NINE.
- Why `ok` and not "inside REFUSE_BAND": with the loose reading the lab supersedes
  one arm TODAY -- M0047-PLC1-MV10 (0.549x trades / 0.496x turnover) retired by
  M0047-PLC1-MV20 (0.545x / 0.508x), its own equally handicapped twin, which
  clears the refuse band only because its turnover rounds to the clean side of
  0.50. M0047 would be unblocked by a second bent stick with no honest control
  drawn. The replacement must clear WARN_BAND, the match band, which is the bar
  every re-drawn arm in the 2026-10-19 plan set is held to.

No band moved: WARN_BAND and REFUSE_BAND are untouched and read nowhere new. No
override was added -- this is the argued rule change D17's own refusal message
invites, which is the only mechanism it has ever offered. Nothing was written to
lab/lab.sqlite: git hash-object unchanged either side.

ruff clean; test_lab_control_shape.py and test_lab_hardgate.py green; full suite
green with Postgres up.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```

---

## Handoffs

- **R2 and R3 (the re-drawn arms themselves) are not this phase's.** Phase 1 writes
  `lab/control_draw.py` and amends M0227 and M0243; Phases 3-7 amend the other seven. This phase
  writes the rule that makes their work count and touches no method file. If a step here would
  have served R1, R2 or R3, it is not here.
- **Phase 1's `control_draw.py` is never imported by `control_shape.py`.** Supersession is a
  property of recorded rows and a rationale, not of how an arm was drawn. Keeping the dependency
  absent is deliberate: the gate must not need to know which helper produced a control.
- **Phase 8 owns the verification that the nine are actually unblocked.** Its exit criterion —
  "every new arm `ok` and every old arm `superseded by …`" — is the end-to-end proof of R4, and it
  runs after the merge. This phase proves only that the mechanism is correct and currently inert.
- **`M0047-PLC1-MV20` (the `warn` twin) is Phase 4's.** It never refused, so it does not block, and
  this phase makes no claim about it beyond using its measured ratios as the argument for the tight
  predicate.
- **Two mis-resolutions the analysis documents — `M0047-PLC1-MV10`/`-MV20` resolving to
  `M0047-EQ`, and `M0202-PLC1-HALF-FAST` resolving to `M0202-Y20-HALF`** — are repaired by Phases 4
  and 5 through the `<target-id>-PLC` naming convention, not by any change to `resolve_target`. The
  ladder is left exactly as it is: it reports its guesses honestly and that is correct behaviour.
  **The cross-phase consequence an earlier draft of this phase raised is now closed, and it is why
  the predicate changed.** Under the draft's target-equality rule, a new arm deliberately
  re-pointed at its true target would **not** supersede the old one and M0047 and M0202 would have
  stayed blocked after all the measuring; under the declaration rule they are superseded by name,
  and the report prints both targets so the re-point stays visible. Phases 4, 5 and 7 therefore
  need do nothing about it beyond declaring the right ids, which the index's supersession mapping
  gives them row by row.
- **`M0047-EQ` ends this plan set with no control arm at all, and that is the correct outcome.**
  Its only placebos were `M0047-PLC1-MV10` and `-MV20`, two *size*-weighted arms the ladder
  mis-aimed at it by `first-declared`; their replacements are aimed at `MV10` and `MV20`, where
  they belong. `findings` produces nothing at all for a method arm with no control — an empty
  tuple is the correct answer and not an error, as `findings`' own docstring says — so `M0047-EQ`
  is not refused for having none. The standing sentence about EQ's +3.80-point lead was never
  supported by a correctly-aimed control, and the repair is to stop quoting it rather than to
  manufacture an arm for it. Phases 4 and 8 both write this down.
- **No drive-by cleanups.** `_table`'s alignment rule, `band_sentence`, `_eligible_targets` and the
  four-rung ladder are all left as they are.

## Rollback

`git revert` the single commit. This phase writes nothing to `lab/lab.sqlite`, inserts no trial,
moves no method status, spends no test-window look and runs no `lab` subcommand, so the revert is
complete and reversible with no residue. The only consequence of reverting is that D17 goes back to
refusing a method that holds an honest control alongside a handicapped one — which is the bug.

If a revert is needed **after** Phases 1 and 3-7 have run their amendments, the amendments stay
(their trials are append-only) and the nine simply remain blocked; nothing recorded becomes wrong,
and the forward fix is to re-land this commit.
