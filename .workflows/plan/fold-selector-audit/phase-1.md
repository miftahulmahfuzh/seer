# Phase 1: Widen `control_shape`'s role vocabulary

**Plan set:** `FOLD_SELECTOR_AUDIT_PLAN.md`
**Analysis:** `docs/analyzer/20261020-162754-F0LD_code_analyzer.md`
**Satisfies:** R3 — a recommendation on `hardgate.py` with the argument. Phase 1 builds the one
instrument the recommendation needs: a reader that can say, of any arm, whether it is an arm that
exists to be beaten. It changes no gate and refuses nothing.
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab/`

---

## Goal

After this phase `control_shape` can answer *"what role does this arm play in its method's
experiment?"* in four words — `control`, `dose`, `idea`, `treatment` — read off the candidate's
one-line `rationale` and never off its id. Today the module can only answer the narrower question
`kind_of` asks (*is this arm shape-checkable?*), and that answer under-counts controls by a factor
of three: over the 821 arms the lab's 157 method files declare, `kind_of` finds **62** placebo
arms while the rationales contain **189** control arms, because the markers cover `placebo` /
`hash order` / `hash-drawn` but not the `Control:` / `Paired control:` / `Yardstick:` /
`Reaction-negative control:` prefixes most of the lab's controls actually use.

Nothing reads `role_of` when this phase lands. D17's population, every `Finding`, every verdict,
every refusal and every byte `lab control` prints are exactly what they were. Phases 2 and 3 are
the readers.

## Interface Contract

**Creates:**

- `control_shape.role_of(arm: Arm) -> str` (`lab/control_shape.py`, immediately after `kind_of`).
  Returns exactly one of four values, never `None`, never raises:

  | constant | value | means |
  |---|---|---|
  | `ROLE_CONTROL` | `"control"` | an arm registered to be beaten: a paired/reproduction baseline, an opposite-sign mirror, a placebo, a yardstick |
  | `ROLE_DOSE` | `"dose"` | a rung of a dose-response ladder — the rung **is** the measurement, not a foil |
  | `ROLE_IDEA` | `"idea"` | the arm a method's controls exist to be compared with |
  | `ROLE_TREATMENT` | `"treatment"` | everything else |

- `control_shape.ROLES: tuple[str, ...]` — the four, in that order, so a caller can validate.
- `control_shape.ROLE_CONTROL`, `ROLE_DOSE`, `ROLE_IDEA`, `ROLE_TREATMENT` (str constants).
- `control_shape.ROLE_CONTROL_OPENERS: tuple[str, ...]` — phrases a rationale may **open** with.
- `control_shape.ROLE_CONTROL_PHRASES: tuple[str, ...]` — phrases matched **anywhere**, on word
  boundaries.
- `control_shape.ROLE_DOSE_MARKERS: tuple[str, ...]` — `DOSE_MARKERS` plus one wider phrase.
- `control_shape._is_word_char`, `_opens_with`, `_holds` — private helpers; not part of the
  contract, do not import them from another module.

**Guarantee phases 2 and 3 may rely on** (structural, not merely measured): `role_of` calls
`kind_of` first and honours its answer, so

- `kind_of(a) == KIND_DOSE` ⟹ `role_of(a) == ROLE_DOSE`
- `kind_of(a) == KIND_PLACEBO` ⟹ `role_of(a) == ROLE_CONTROL`

`role_of` can therefore never disagree with the arm-kind D17 already acts on.

**Deletes:** nothing.
**Renames:** nothing.
**Signature changes:** none.
**Requires (from earlier phases):** none — this is the root of the set.
**Leaves alone (owned by others):** `hardgate.py` entirely (phase 2); `commands/lab.py` and
`walkforward.py` entirely (phase 3). Inside `control_shape.py` this phase does not touch
`kind_of`, `declared_target`, `declared_supersessions`, `_eligible_targets`, `resolve_target`,
`band_verdict`, `worst`, `_ratio`, `shapes`, `findings`, `superseding_arm`, `_mark_superseded`,
`for_method`, `survey`, `refusals`, `flags`, `describe`, `band_sentence`, `format_report`,
`DOSE_MARKERS`, `DRAW_MARKERS`, `ABLATION_MARKERS`, `IDEA_MARKERS`, `KIND_*`, `WARN_BAND` or
`REFUSE_BAND`. The 2026-10-19 marker measurements and their comments are a frozen record and are
not re-numbered, re-worded or re-dated.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/control_shape.py` | modify | a new docstring section before `**A reader, not a writer.**` (currently line 217); a `ROLE_*` marker block after `IDEA_MARKERS` (line 309); four role constants plus `ROLES` after `KIND_NONE` (line 316); `_is_word_char`, `_opens_with`, `_holds`, `role_of` after `kind_of` (line 441) |
| `engine/tests/test_lab_control_shape.py` | modify | a new section appended at the end of the file (after line 864): nine tests for the role reader |

Two files. Nothing else in the tree is touched.

---

## Step 0 (do this first): measure, do not copy

This module's convention — stated in its own docstring — is that *"a constant with no measurement
behind it is a guess, and this lab writes down where its numbers came from."* Every number in the
code blocks below was measured on **2026-10-20** against `main` @ `89b4220`. **Re-measure before
you write them.** If the lab has grown since, the counts in the comments must be the numbers your
run prints, not the numbers printed here.

Write the measurement script to the scratchpad (it is a measuring tool, not a source file — do
not add it to the package):

```bash
mkdir -p /tmp/claude-1000/-home-miftah-seer/role-measure
cat > /tmp/claude-1000/-home-miftah-seer/role-measure/measure_roles.py <<'PY'
"""Measure every role marker's hit count over the lab's method files, and the four-way split.

Reads method FILES through `method.discover()` -- never the lab database -- so it opens nothing,
migrates nothing and spends no look. The population it reports is the population `role_of` is
called on: `hardgate` and `control_shape.for_method` both read a method's arms from its file.
"""
import collections
import sys

from seer_engine.lab import control_shape as cs
from seer_engine.lab.method import discover

ROLE_CONTROL_OPENERS = ("control", "paired control", "reaction-negative control", "yardstick")
ROLE_CONTROL_PHRASES = ("the control", "the paired control")
ROLE_DOSE_MARKERS = cs.DOSE_MARKERS + ("rung of the",)


def is_word_char(ch):
    return ch.isalnum() or ch == "_"


def opens_with(text, phrase):
    if not text.startswith(phrase):
        return False
    return not is_word_char(text[len(phrase):len(phrase) + 1])


def holds(text, phrase):
    start = text.find(phrase)
    while start != -1:
        before = text[start - 1:start] if start else ""
        after = text[start + len(phrase):start + len(phrase) + 1]
        if not is_word_char(before) and not is_word_char(after):
            return True
        start = text.find(phrase, start + 1)
    return False


def role_of(arm):
    kind = cs.kind_of(arm)
    if kind == cs.KIND_DOSE:
        return "dose"
    if kind == cs.KIND_PLACEBO:
        return "control"
    text = str(arm.rationale).strip().lower()
    if any(m in text for m in cs.IDEA_MARKERS):
        return "idea"
    if any(m in text for m in ROLE_DOSE_MARKERS):
        return "dose"
    if any(opens_with(text, p) for p in ROLE_CONTROL_OPENERS):
        return "control"
    if any(holds(text, p) for p in ROLE_CONTROL_PHRASES):
        return "control"
    return "treatment"


files = discover()
arms = [(mid, c) for mid, (method, _p) in sorted(files.items()) for c in method.all_candidates()]
print(f"{len(arms)} arms across {len(files)} method files")

print("\nROLE_CONTROL_OPENERS -- an arm whose rationale OPENS with the phrase")
for p in ROLE_CONTROL_OPENERS:
    hit = [c.id for _m, c in arms if opens_with(str(c.rationale).strip().lower(), p)]
    print(f"  {p!r:<30} {len(hit):>4}   {', '.join(hit[:4])}")

print("\nROLE_CONTROL_PHRASES -- anywhere, on word boundaries")
for p in ROLE_CONTROL_PHRASES:
    hit = [c.id for _m, c in arms if holds(str(c.rationale).strip().lower(), p)]
    print(f"  {p!r:<30} {len(hit):>4}   {', '.join(hit[:4])}")

print("\nthe one new dose marker -- plain substring, as DOSE_MARKERS are read")
for p in ("rung of the",):
    hit = [c.id for _m, c in arms if p in str(c.rationale).strip().lower()]
    print(f"  {p!r:<30} {len(hit):>4}   {', '.join(hit[:4])}")

print("\nthe four-way split")
counts = collections.Counter(role_of(c) for _m, c in arms)
print(" ", dict(sorted(counts.items())))

bad = [
    (c.id, cs.kind_of(c), role_of(c))
    for _m, c in arms
    if (cs.kind_of(c) == cs.KIND_PLACEBO and role_of(c) != "control")
    or (cs.kind_of(c) == cs.KIND_DOSE and role_of(c) != "dose")
]
print("\nkind_of contradictions:", bad or "none")
sys.exit(0)
PY
cd /home/miftah/seer && PYTHONPATH=engine/src engine/.venv/bin/python \
    /tmp/claude-1000/-home-miftah-seer/role-measure/measure_roles.py
```

**What it printed on 2026-10-20** (`main` @ `89b4220`) — this is the output the code blocks below
were written from:

```
821 arms across 157 method files

ROLE_CONTROL_OPENERS -- an arm whose rationale OPENS with the phrase
  'control'                        98   M0013-TGT-D8-MW, M0038-DIV-OPEN, M0039-SPY-200, M0039-DIV
  'paired control'                 18   M0076-X-M, M0076-X-W, M0076-X-M-D, M0081-X-W12
  'reaction-negative control'       2   M0083-A-DN, M0083-X-DN
  'yardstick'                       1   M0107-NONE

ROLE_CONTROL_PHRASES -- anywhere, on word boundaries
  'the control'                    14   M0033-TV22-N21, M0035-CTRL, M0036-DISC, M0047-EQ
  'the paired control'              3   M0108-WORST20, M0133-N40, M0143-CALM-UP63

the one new dose marker -- plain substring, as DOSE_MARKERS are read
  'rung of the'                    21   M0155-Z15-FILL, M0155-Z25-FILL, M0174-C40-SW, M0178-L40-SW

the four-way split
  {'control': 189, 'dose': 33, 'idea': 5, 'treatment': 594}

kind_of contradictions: none
```

**189 controls — the audit's number, reproduced.** The audit prototype
(`scratchpad/audit/role.py`) read 595 treatment / 189 control / 32 dose / 5 idea. This phase's
classifier agrees on all 821 arms but one: `M0244-STALE30` (*"newest gesture one to two years old
and none since: does the date do any work?"*), which the prototype called **treatment** and this
calls **dose**. The production answer is the right one — `kind_of` has called that arm
`KIND_DOSE` since 2026-10-19 via its own `and none since` / `does the date do any work` markers,
and a role reader that contradicted the kind reader on a recorded arm would be a defect in the
instrument before it was ever a defect in a gate. **The control count, which is the only number
phases 2 and 3 act on, is identical.** Record this one-arm difference in the commit message.

Also note, and do **not** silently fix: the module's 2026-10-19 block says *"770 candidates in the
lab's 271 method files"*. `discover()` returns **157** files today and the lab database holds 280
`methods` rows — so the 271 was almost certainly a count of recorded methods, not of files. That
sentence is a frozen record of someone else's measurement. Leave it exactly as written and date
and scope your own block separately, which is what the code below does.

---

## Implementation Steps

### Step 1: a new docstring section explaining the role reader

**File:** `engine/src/seer_engine/lab/control_shape.py`, insert immediately **before** the line
`**A reader, not a writer.** No ``trials``, ``trial_moments``...` (currently line 217), keeping the
`---` separator that precedes it at line 215 where it is and adding a new one at the end of the
inserted block.

**Change:** the module explains at length why every constant in it was measured and why ids are a
trap. A second vocabulary with a second population and a second date needs the same treatment, and
it needs to say out loud that it reads but never decides, because the next person to open this
file will be phase 2's author looking for a gate.

**Code** (insert verbatim, as part of the module docstring):

```python
**The second question, and why it needed a second vocabulary.** ``kind_of`` answers *"is this arm
shape-checkable?"* and its three kinds are cut for that job: a ``placebo`` gets a ratio, a
``dose-response`` arm and a ``within-frame control`` are reported and never flagged. The hard gate
asks a different question one clause downstream -- *"is the arm that gets the counted look and the
owner's money an arm that exists to be beaten?"* -- and ``kind_of``'s vocabulary cannot answer it.
Measured 2026-10-20 over the 821 candidates in the lab's 157 method files: ``kind_of`` finds 62
placebo arms, and the rationales contain **189** control arms. The 127 it cannot see are not
placebos. They are the lab's ordinary controls, and they announce themselves in prose --
``Control: M0036-BLEND re-stated under this allocator, no brake`` (``M0044-NOBRAKE``),
``Paired control: no sector cap`` (``M0215-CTRL``), ``Reaction-negative control: raises that
lagged SPY from the declaration day`` (``M0083-A-DN``), ``Yardstick: the same book with no gate at
all`` (``M0107-NONE``), ``...the control, expected to trail`` (``M0058-LIQ20-T``). Widening
``DRAW_MARKERS`` to reach them is not available: ``DRAW_MARKERS`` decides which arms get a shape
ratio and which arms are excluded from the resolution ladder, so one phrase added there moves D17
on nine dev-eligible methods and silently re-points the ladder. ``role_of`` is therefore a reader
beside ``kind_of``, not a replacement of it, and it is wired to nothing in this file.

**``role_of`` honours ``kind_of`` first, structurally.** It asks ``kind_of`` before it reads a
marker of its own, so a ``KIND_DOSE`` arm is always ``dose`` and a ``KIND_PLACEBO`` arm is always
``control``, whatever else its prose happens to contain. The alternative -- two independent marker
sweeps over the same sentence -- can disagree about one arm the day somebody writes a rationale
carrying both an idea marker and a draw marker, and a role reader that contradicts the kind reader
on a recorded arm is a broken instrument before it is ever a broken gate. Measured 2026-10-20:
zero arms disagree, and the ordering is what keeps that true rather than the luck of today's prose.

**Why the control markers are anchored and ``kind_of``'s are not.** ``DRAW_MARKERS`` are
substrings because "placebo" anywhere in a sentence means the same thing. "Control" does not: an
arm that says *"the brake that controls the fall"* is the idea, and an arm that opens ``Control:``
is the foil. So ``ROLE_CONTROL_OPENERS`` matches only at the start of the rationale and only on a
word boundary -- ``Controlled exposure...`` is not a control -- and
``ROLE_CONTROL_PHRASES`` carries the two phrases that are unambiguous wherever they appear, ``the
control`` and ``the paired control``, again on word boundaries so ``the controlling idea`` is
untouched. Both lists were derived the same way the 2026-10-19 lists were: by reading every arm
that fires and keeping only phrases that actually do.

**An ablation stays a treatment arm, on purpose.** ``M0248-B100`` opens ``Within-frame control:``
and ``kind_of`` calls it ``KIND_ABLATION``, but ``role_of`` calls it ``treatment``, because this
file already says why: *"an ablation is a signal arm in its own right; its trade count is a
property of the signal being measured"*. An arm nobody registered to be beaten must not be refused
as one.

**A width rung reads as ``dose``, and that is the coarse edge of this reader.** ``rung of the`` is
a measured dose marker -- 21 arms on 2026-10-20, from ``M0258-M-B30``'s *"Middle rung of the
dose-response ladder"* to ``M0174-C40-SW``'s *"A 40-name rung of the low-correlation book behind
the switch"*. A 40-name rung beside a 20-name rung **is** a width dose, so the answer is defensible
and it is the audit's own prototype answer. But it means ``dose`` and ``treatment`` are not a sharp
pair, and no caller should read ``treatment`` as "this is the method's idea". The split this reader
is calibrated for, and the only one the lab acts on, is ``control`` against everything else.

---
```

**Impact:** documentation only. No behaviour.

---

### Step 2: the role markers, each with its measured hit count

**File:** `engine/src/seer_engine/lab/control_shape.py`, insert after line 309 — the closing
docstring of `IDEA_MARKERS`, `"""How a method names the arm its controls exist to be compared
with."""` — and before the `# ----- the vocabulary` banner at line 311.

**Change:** a second measured marker block, with its own date, its own population and its own
counts, so neither block can be read as evidence for the other.

**Code:**

```python
# ----------------------------------------------------------------------- the role markers
#
# Measured 2026-10-20 over all 821 candidates in the lab's 157 method files -- the population
# `method.discover()` returns, which is the population `role_of` is called on. A separate sweep
# from the 2026-10-19 one above, with its own date and its own denominator: the two blocks are
# two measurements and neither is evidence for the other. The number beside each phrase is how
# many of the 821 that phrase matches on its own, under this block's own matching rule.

ROLE_CONTROL_OPENERS: tuple[str, ...] = (
    "control",                    # 98: M0013-TGT-D8-MW, M0038-DIV-OPEN, M0039-SPY-200, M0044-NOBRAKE
    "paired control",             # 18: M0076-X-M, M0076-X-W, M0076-X-M-D, M0081-X-W12, M0215-CTRL
    "reaction-negative control",  # 2: M0083-A-DN, M0083-X-DN
    "yardstick",                  # 1: M0107-NONE
)
"""Phrases a control arm's rationale OPENS with, matched on a word boundary and nowhere else.

Anchored because "control" is a word the lab also uses about what a brake does to a fall, and a
substring rule would call the brake a foil. ``M0005-ALL-R`` is the standing reminder that a
confident-looking rule applied to the wrong field quietly mis-reads a real variant forever.
"""

ROLE_CONTROL_PHRASES: tuple[str, ...] = (
    "the control",         # 14: M0033-TV22-N21, M0035-CTRL, M0036-DISC, M0047-EQ, M0262-LOCK-0
    "the paired control",  # 3: M0108-WORST20, M0133-N40, M0143-CALM-UP63
)
"""Phrases that mean a foil wherever they sit in the sentence, matched on both word boundaries.

The lab's second-commonest way of saying it is a trailing clause -- ``M0058-LIQ20-T``'s "the 20
most liquid members, behind the gate: the control, expected to trail". The boundaries are what
keep "the controlling idea" out, and they are why this is a phrase list and not a substring list.
``the paired control`` is carried separately because it does not contain ``the control``.
"""

ROLE_DOSE_MARKERS: tuple[str, ...] = DOSE_MARKERS + (
    "rung of the",  # 21: M0155-Z15-FILL, M0174-C40-SW, M0179-N40-SW, M0258-M-B30, M0260-M-G3
)
"""``DOSE_MARKERS`` plus the one wider phrase a role reader needs and a shape checker must not have.

``rung of the`` reaches 21 arms, of which `kind_of` sees 4. Adding it to ``DOSE_MARKERS`` itself
would be a different and much larger change: ``DOSE_MARKERS`` decides what is excluded from
``_eligible_targets`` and what is reported ``NOT_CHECKED``, so seventeen more dose arms there would
re-point the resolution ladder and move D17. Here it only sorts an arm into a bucket nobody
refuses on, which is why the wider phrase is safe in this list and not in that one.
"""
```

**Impact:** three new module-level constants. `DOSE_MARKERS` is read, never rebound, so `kind_of`,
`_eligible_targets` and every D17 verdict are untouched.

---

### Step 3: the four role names

**File:** `engine/src/seer_engine/lab/control_shape.py`, insert after line 316 (`KIND_NONE = ""`)
and before the blank line preceding `OK = "ok"` at line 318.

**Change:** name the four roles beside the three kinds, and publish the tuple so a caller can
validate rather than hard-code strings.

**Code:**

```python
ROLE_CONTROL = "control"
ROLE_DOSE = "dose"
ROLE_IDEA = "idea"
ROLE_TREATMENT = "treatment"

ROLES: tuple[str, ...] = (ROLE_CONTROL, ROLE_DOSE, ROLE_IDEA, ROLE_TREATMENT)
"""Every value ``role_of`` can return. Published so a caller validates against this and not a
literal, because the one thing a reader of an arm's role must never do is quietly fall through to
"not a control" on a spelling it did not recognise."""
```

**Impact:** five new constants. Nothing reads them yet.

---

### Step 4: `role_of` and its two matchers

**File:** `engine/src/seer_engine/lab/control_shape.py`, insert after `kind_of` ends (line 440,
`    return KIND_NONE`) and before `def declared_target` at line 443 — inside the
`# ----- (1) detection` section, because that is what this is.

**Change:** the reader itself. Pure, total, raises nothing, reads no database and no file.

**Code:**

```python
def _is_word_char(ch: str) -> bool:
    """True for a character that would continue a word. The empty string is not one.

    Taking ``""`` as "not a word character" is what lets the two matchers below treat the start
    and the end of a rationale as boundaries without a special case at either edge.
    """
    return ch.isalnum() or ch == "_"


def _opens_with(text: str, phrase: str) -> bool:
    """True when ``text`` begins with ``phrase`` as a whole word.

    ``text`` is expected lowercased and stripped. ``Controlled exposure...`` must not read as a
    control arm, and a bare ``startswith`` says it does; one character of look-ahead is the whole
    difference between a rule and a guess.
    """
    if not text.startswith(phrase):
        return False
    return not _is_word_char(text[len(phrase):len(phrase) + 1])


def _holds(text: str, phrase: str) -> bool:
    """True when ``phrase`` occurs anywhere in ``text`` with a word boundary on both sides.

    Every occurrence is tried, not just the first: a sentence may say "the controlling idea" and
    then "the control" later, and stopping at the first near-miss would lose the real one.
    """
    start = text.find(phrase)
    while start != -1:
        before = text[start - 1:start] if start else ""
        after = text[start + len(phrase):start + len(phrase) + 1]
        if not _is_word_char(before) and not _is_word_char(after):
            return True
        start = text.find(phrase, start + 1)
    return False


def role_of(arm: Arm) -> str:
    """What part ``arm`` plays in its method's experiment, from its rationale. One of ``ROLES``.

    ``control`` is the answer that matters and the only one anything is allowed to refuse on: an
    arm registered to be beaten -- a paired or reproduction baseline, an opposite-sign mirror, a
    placebo, a yardstick. ``dose`` is a rung of a ladder, where differing IS the measurement.
    ``idea`` is the arm a method's controls exist to be compared with. ``treatment`` is everything
    else, and it is a residue rather than a claim: see the module docstring on why a width rung
    reads as ``dose`` and why no caller should read ``treatment`` as "this is the method's idea".

    ``kind_of`` is asked first and its answer is final for the two kinds it is sure about, so this
    function can never contradict the arm-kind D17 already acts on. A ``KIND_ABLATION`` arm falls
    through on purpose: an ablation is a signal arm in its own right and nobody registered it to
    be beaten.

    Then, in order: the idea markers, because an author who wrote "The idea:" has named the arm
    outright and no looser bucket may swallow it; the wider dose markers, because a rung that also
    says "control" is still a rung, which is the same ordering and the same reason ``kind_of``
    tests dose before draw; the anchored control openers; the unanchored control phrases; and
    finally the draw markers, so a placebo that reached here through prose rather than through
    ``kind_of`` still lands on ``control``.

    Total and pure. Never raises, never returns ``None``, opens nothing, writes nothing. An arm
    whose ``rationale`` is not a string is read through ``str`` exactly as ``kind_of`` reads it.
    """
    kind = kind_of(arm)
    if kind == KIND_DOSE:
        return ROLE_DOSE
    if kind == KIND_PLACEBO:
        return ROLE_CONTROL
    text = str(arm.rationale).strip().lower()
    if any(m in text for m in IDEA_MARKERS):
        return ROLE_IDEA
    if any(m in text for m in ROLE_DOSE_MARKERS):
        return ROLE_DOSE
    if any(_opens_with(text, p) for p in ROLE_CONTROL_OPENERS):
        return ROLE_CONTROL
    if any(_holds(text, p) for p in ROLE_CONTROL_PHRASES):
        return ROLE_CONTROL
    if any(m in text for m in DRAW_MARKERS):
        return ROLE_CONTROL
    return ROLE_TREATMENT
```

The final `DRAW_MARKERS` check is unreachable today — `kind_of` already returns `KIND_PLACEBO` for
every arm that matches one. It is kept because it is the rule the audit prototype stated and
because it is the line that keeps `role_of` correct if `kind_of`'s dose-before-draw ordering ever
sends a placebo-worded arm down this path. Do not delete it as dead code; it is a floor.

**Impact:** one new public function plus three private helpers. No existing symbol is read
differently, so `kind_of`, `findings`, `refusals`, `survey`, `format_report` and `lab control` are
bit-for-bit what they were.

---

### Step 5: the tests

**File:** `engine/tests/test_lab_control_shape.py`, **appended at the end** (after line 864,
`            f"{mid} is no longer read by D17 at all"` / `        )`).

Append at the end rather than inserting into the detection section at line 65 so no existing test
moves and the diff is readable. `discover()` is imported **inside** each test that needs it, the
way `control_shape` itself imports it, because a module-scope import would import all 157 method
modules at collection time for every test in this file.

**Code:**

```python
# ------------------------------------------------------------------ the role reader

# Real rationales, quoted from the method files on 2026-10-20. Like the block at the top of this
# file they are frozen records: an arm with a recorded trial cannot have its rationale edited
# without breaking `store.latest_source_sha` for its method, so a literal here cannot drift.
R_CTRL_OPEN = "Control: M0036-BLEND re-stated under this allocator, no brake"
R_PAIRED = "Paired control: no sector cap (= M0168-CTRL = M0088-C-LIVE-63)"
R_REACTION = "Reaction-negative control: raises that lagged SPY from the declaration day"
R_YARDSTICK = "Yardstick: the same book with no gate at all and cash for the empty slots"
R_TRAILING = "The 20 most liquid members, behind the gate: the control, expected to trail"
R_PAIRED_TRAILING = (
    "The 40 worst by the same score, behind the switch: the paired control, expected to trail"
)
R_POSITIVE = "Control: the 20 most positive-coskewness members, same band and switch"
R_PLC1_HALF = "Placebo: the same scoreable names in a fixed hash order (seed 1), same guard"
R_RUNG = "A 40-name rung of the low-correlation book behind the switch"
R_IDEA = "The idea: equal parts buyback intensity and discount from the yearly high"


def test_role_of_answers_with_one_of_the_four_published_roles():
    """A role is a closed vocabulary, and `ROLES` is what a caller validates against.

    Nothing outside this module may test a literal, because a caller that compared against a
    misspelled string would silently read every arm as "not a control" and refuse nothing.
    """
    assert cs.ROLES == (cs.ROLE_CONTROL, cs.ROLE_DOSE, cs.ROLE_IDEA, cs.ROLE_TREATMENT)
    assert len(set(cs.ROLES)) == 4
    for rationale in (R_CTRL_OPEN, R_RUNG, R_IDEA, R_PLAIN, R_B100, R_ALL_R):
        assert cs.role_of(Stub("M9999-X", rationale)) in cs.ROLES


def test_every_role_marker_is_lowercase_so_it_can_actually_fire():
    """role_of lowercases the rationale; a mixed-case marker would match nothing, ever."""
    groups = (cs.ROLE_CONTROL_OPENERS, cs.ROLE_CONTROL_PHRASES, cs.ROLE_DOSE_MARKERS)
    for group in groups:
        for marker in group:
            assert marker == marker.lower(), f"{marker!r} can never match a lowercased rationale"
            assert marker.strip() == marker and marker, f"{marker!r} is padded or empty"


def test_the_prefixes_the_lab_actually_writes_all_read_as_controls():
    """The 127 arms kind_of cannot see, one per phrasing the lab uses.

    This is the whole reason the phase exists: kind_of finds 62 placebo arms and the rationales
    contain 189 control arms, because most of the lab's controls announce themselves in prose
    rather than by being a draw.
    """
    for rationale in (
        R_CTRL_OPEN, R_PAIRED, R_REACTION, R_YARDSTICK, R_TRAILING, R_PAIRED_TRAILING, R_POSITIVE,
        "Control for the fee drag alone: the same book with no signal at all",
        "Control paired with the switch arm: the same names, switch off",
        "Control and correctness check: should reproduce M0032-N20 exactly",
    ):
        arm = Stub("M9999-X", rationale)
        assert cs.role_of(arm) == cs.ROLE_CONTROL, rationale
        # and not one of them is visible to the shape checker at all, which is the whole gap
        assert cs.kind_of(arm) == cs.KIND_NONE, rationale


def test_a_word_that_merely_begins_with_control_is_not_a_control():
    """The anchored marker's whole job: one character of look-ahead instead of a startswith.

    The lab writes about what a brake controls as often as it writes about a control arm, so a
    substring rule would mark the idea as its own foil -- the same class of error as reading the
    id suffix, which this module exists to refuse.
    """
    assert cs.role_of(Stub("M9999-A", "Controlled exposure: half the book, half the time")) == (
        cs.ROLE_TREATMENT
    )
    assert cs.role_of(Stub("M9999-B", "Controls the fall by stepping down one rung at a time")) == (
        cs.ROLE_TREATMENT
    )
    assert cs.role_of(Stub("M9999-C", "The brake that governs the controlling idea here")) == (
        cs.ROLE_TREATMENT
    )
    # ...while the same words, used as the lab uses them about a foil, still fire
    assert cs.role_of(Stub("M9999-D", "Control- the same book, no brake")) == cs.ROLE_CONTROL
    assert cs.role_of(Stub("M9999-E", "the same book, no brake: the control")) == cs.ROLE_CONTROL


def test_role_of_can_never_contradict_kind_of():
    """The structural guarantee phases 2 and 3 import.

    role_of asks kind_of first, so a dose arm is `dose` and a placebo arm is `control` whatever
    else the prose contains. Asserted on the one sentence that carries two marks at once -- the
    same sentence test_dose_is_tested_before_draw_so_a_dose_arm_is_never_a_placebo uses -- so the
    two orderings are pinned against each other and not merely each against itself.
    """
    both = Stub("M9999-X", "Placebo: the same names at a one-to-two-year dose-response spacing")
    assert cs.kind_of(both) == cs.KIND_DOSE
    assert cs.role_of(both) == cs.ROLE_DOSE
    assert cs.role_of(Stub("M0202-PLC1-HALF", R_PLC1_HALF)) == cs.ROLE_CONTROL
    assert cs.kind_of(Stub("M0202-PLC1-HALF", R_PLC1_HALF)) == cs.KIND_PLACEBO
    assert cs.role_of(Stub("M0241-STALE", R_STALE)) == cs.ROLE_DOSE
    assert cs.role_of(Stub("M0244-STALE30", R_STALE30)) == cs.ROLE_DOSE


def test_an_ablation_is_a_treatment_arm_although_it_says_control():
    """M0248-B100 opens `Within-frame control:` and is a signal arm in its own right.

    This module already says so about its shape -- "its trade count is a property of the
    ingredient under test" -- and the role must agree: nobody registered it to be beaten, so
    nothing downstream may refuse a promotion for landing on it.
    """
    arm = Stub("M0248-B100", R_B100)
    assert cs.kind_of(arm) == cs.KIND_ABLATION
    assert cs.role_of(arm) == cs.ROLE_TREATMENT


def test_the_idea_markers_outrank_every_looser_bucket():
    """An author who wrote `The idea:` has named the arm; no wider marker may swallow it.

    M0222-CORE says `The yardstick: ...` and the control openers carry the bare word `yardstick`
    for M0107-NONE's `Yardstick: ...`. The order is what keeps the two apart, and the two arms
    are one word different, so it is pinned here rather than left to the next reader to notice.
    """
    assert cs.role_of(Stub("M0248-EQ", R_IDEA)) == cs.ROLE_IDEA
    assert cs.role_of(Stub("M0222-CORE", R_CORE)) == cs.ROLE_IDEA
    assert cs.role_of(Stub("M0107-NONE", R_YARDSTICK)) == cs.ROLE_CONTROL


def test_a_rank_weighting_variant_is_not_a_control_in_this_vocabulary_either():
    """M0005-ALL-R again, through the wider reader: the id trap must stay shut.

    The point of widening the vocabulary is to find the controls kind_of misses, not to start
    reading suffixes. If this ever goes red the widening has gone wrong in the one direction the
    module warns about, and the next -R that is a real variant will be judged the same wrong way.
    """
    assert cs.role_of(Stub("M0005-ALL-R", R_ALL_R)) == cs.ROLE_TREATMENT
    assert cs.role_of(Stub("M9999-RAND1", R_PLAIN)) == cs.ROLE_TREATMENT
    assert cs.role_of(Stub("M9999-PLACEBO", R_PLAIN)) == cs.ROLE_TREATMENT


# The audit of 2026-10-20 classified all 821 arms in the lab's 157 method files as
# 594 treatment / 189 control / 33 dose / 5 idea. These sixteen are the arms the plan's argument
# names, pinned by id so a rationale edit or a marker change is caught on the arm it would move
# rather than on a total. They are frozen rows: each has a recorded dev trial, so its method file
# cannot be edited without breaking store.latest_source_sha for that method.
ROLE_SPOT_CHECK: dict[str, str] = {
    "M0179-P20-SW": cs.ROLE_CONTROL,       # "Control: the 20 most positive-coskewness members"
    "M0202-PLC1-HALF": cs.ROLE_CONTROL,    # the placebo lab promote would pre-register
    "M0044-NOBRAKE": cs.ROLE_CONTROL,      # "Control: M0036-BLEND re-stated ... no brake"
    "M0035-CTRL": cs.ROLE_CONTROL,         # "The control: M0032's book ... switch off"
    "M0215-CTRL": cs.ROLE_CONTROL,         # "Paired control: no sector cap"
    "M0107-NONE": cs.ROLE_CONTROL,         # "Yardstick: the same book with no gate at all"
    "M0083-A-DN": cs.ROLE_CONTROL,         # "Reaction-negative control: ..."
    "M0058-LIQ20-T": cs.ROLE_CONTROL,      # "...: the control, expected to trail"
    "M0262-LOCK-0": cs.ROLE_CONTROL,       # "The control, and the bridge back to M0261's arm"
    "M0248-B100": cs.ROLE_TREATMENT,       # an ablation is a signal arm
    "M0005-ALL-R": cs.ROLE_TREATMENT,      # the id trap
    "M0241-STALE": cs.ROLE_DOSE,
    "M0244-STALE30": cs.ROLE_DOSE,         # the one arm the audit prototype read as treatment
    "M0258-M-B30": cs.ROLE_DOSE,
    "M0174-C40-SW": cs.ROLE_DOSE,          # a width rung: the coarse edge, pinned deliberately
    "M0248-EQ": cs.ROLE_IDEA,
    "M0222-CORE": cs.ROLE_IDEA,
}


def test_the_named_arms_read_the_way_the_audit_read_them():
    """Every arm the plan's argument quotes, re-derived from the method files themselves."""
    from seer_engine.lab.method import discover

    files = discover()
    arms = {
        c.id: c for _mid, (method, _p) in files.items() for c in method.all_candidates()
    }
    for candidate_id, role in ROLE_SPOT_CHECK.items():
        arm = arms.get(candidate_id)
        if arm is None:
            pytest.skip(f"{candidate_id} is not in this tree's method files")
        assert cs.role_of(arm) == role, (
            f"{candidate_id} now reads as {cs.role_of(arm)}: {arm.rationale}"
        )


def test_the_lab_holds_at_least_the_one_hundred_and_eighty_nine_controls_the_audit_counted():
    """The audit's count, pinned as a floor rather than as an equality.

    Measured 2026-10-20: 821 arms across 157 method files, 189 of them controls. An equality here
    would go red the next time a method lands, which is a test that fails when the lab works; a
    floor goes red only when the vocabulary NARROWS, which is the regression worth catching --
    phase 2 refuses a promotion on this answer, and a marker quietly stopping firing would unblock
    methods nobody argued for.

    A tree with fewer method files than the measurement had is skipped rather than failed: a
    trimmed worktree is not evidence that a marker broke.
    """
    from seer_engine.lab.method import discover

    files = discover()
    if len(files) < 157:
        pytest.skip(f"this tree holds {len(files)} method files, fewer than the 157 measured")
    arms = [c for _mid, (method, _p) in files.items() for c in method.all_candidates()]
    assert len(arms) >= 821
    roles = [cs.role_of(a) for a in arms]
    assert all(r in cs.ROLES for r in roles)
    assert roles.count(cs.ROLE_CONTROL) >= 189, (
        "the role vocabulary has narrowed: fewer control arms are visible than the 2026-10-20 "
        "audit counted, and anything that refuses on this answer has quietly stopped refusing"
    )
    # and the structural guarantee, over every arm the lab holds rather than over three stubs
    for arm in arms:
        kind = cs.kind_of(arm)
        if kind == cs.KIND_PLACEBO:
            assert cs.role_of(arm) == cs.ROLE_CONTROL, arm.id
        elif kind == cs.KIND_DOSE:
            assert cs.role_of(arm) == cs.ROLE_DOSE, arm.id


def test_asking_for_a_role_opens_no_database_and_moves_no_file():
    """role_of is pure: it reads one string off one object and nothing else.

    The committed lab is hashed around a full sweep of every arm, which is the same guarantee the
    calibration test makes about `survey` and the same one `lab control`'s docstring makes about
    the whole report path.
    """
    from seer_engine.lab.method import discover

    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    before = hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest()
    files = discover()
    for _mid, (method, _p) in files.items():
        for arm in method.all_candidates():
            cs.role_of(arm)
    assert hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest() == before
```

**Impact:** eleven new tests, 44 → 55 in this file. No existing test is edited or moved.

---

## Verification

Run from `/home/miftah/seer`.

**Lint:**

```bash
engine/.venv/bin/ruff check engine
```

**Tests — this file first, then the suite:**

```bash
PYTHONPATH=engine/src engine/.venv/bin/pytest engine/tests/test_lab_control_shape.py -q -n0
PYTHONPATH=engine/src engine/.venv/bin/pytest engine/tests -q
```

Baseline before the change: `44 passed`. After: `55 passed`. The full suite must be green; the DB
tests need Postgres per `CLAUDE.md` and must not skip.

**The gate did not move** — run the hard gate's and the shape check's own suites explicitly, since
D17's population is the thing this phase promises not to touch:

```bash
PYTHONPATH=engine/src engine/.venv/bin/pytest \
    engine/tests/test_lab_hardgate.py engine/tests/test_lab_control_draw.py \
    engine/tests/test_lab_control_draw_twins.py engine/tests/test_lab_gate_policy.py \
    engine/tests/test_lab_fold_verdict.py engine/tests/test_lab_m0208_matched_draw.py -q
```

**`lab control` is byte-identical.** Run it against a scratchpad COPY of the lab, never the
committed file — a lab command migrates `lab.sqlite` on connect and dirties it even on a read:

```bash
mkdir -p /tmp/claude-1000/-home-miftah-seer/role-measure
cp /home/miftah/seer/lab/lab.sqlite /tmp/claude-1000/-home-miftah-seer/role-measure/before.sqlite
cp /home/miftah/seer/lab/lab.sqlite /tmp/claude-1000/-home-miftah-seer/role-measure/after.sqlite

# BEFORE you edit control_shape.py (git stash your work if you already have):
cd /home/miftah/seer && SEER_LAB_DB=/tmp/claude-1000/-home-miftah-seer/role-measure/before.sqlite \
  PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab control \
  > /tmp/claude-1000/-home-miftah-seer/role-measure/control_before.txt

# AFTER:
cd /home/miftah/seer && SEER_LAB_DB=/tmp/claude-1000/-home-miftah-seer/role-measure/after.sqlite \
  PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab control \
  > /tmp/claude-1000/-home-miftah-seer/role-measure/control_after.txt

diff /tmp/claude-1000/-home-miftah-seer/role-measure/control_{before,after}.txt && echo IDENTICAL
```

`diff` must print nothing and the line must read `IDENTICAL`. Then confirm the committed lab never
moved:

```bash
cd /home/miftah/seer && git status --porcelain lab/lab.sqlite
```

Must be empty. If it is not, restore it by path (`git checkout -- lab/lab.sqlite`) — a migrated
database is not a result.

**The measurement reproduces:** re-run Step 0's script against the finished module, with
`role_of` imported from `control_shape` instead of defined locally:

```bash
cd /home/miftah/seer && PYTHONPATH=engine/src engine/.venv/bin/python -c "
import collections
from seer_engine.lab import control_shape as cs
from seer_engine.lab.method import discover
files = discover()
arms = [c for _m, (meth, _p) in files.items() for c in meth.all_candidates()]
print(len(arms), 'arms across', len(files), 'method files')
print(dict(sorted(collections.Counter(cs.role_of(a) for a in arms).items())))
"
```

Expected on `main` @ `89b4220`: `821 arms across 157 method files` and
`{'control': 189, 'dose': 33, 'idea': 5, 'treatment': 594}`. **The 189 is the number this phase is
measured against.** If the lab has grown since, controls may only be ≥ 189 — a smaller number means
a marker is not firing and the phase is not done.

**Manual check:** read the diff of `control_shape.py` and confirm that the 2026-10-19 marker block
(`DOSE_MARKERS` … `IDEA_MARKERS`, lines 277-309) is untouched, comment for comment, and that no
line inside `kind_of`, `findings`, `refusals` or `format_report` changed.

**Exit criteria:**

1. `role_of` returns one of four roles for every one of the 821 arms, and ≥ 189 of them `control`.
2. Every new marker carries the hit count the implementer's own run printed, on its own line.
3. `lab control`'s output is byte-identical before and after, and `lab/lab.sqlite` is unmodified.
4. `ruff check engine` clean; `pytest engine/tests` green; 55 tests in
   `test_lab_control_shape.py`.
5. `git diff --stat` touches exactly two files.
6. No method id spent, no trial written, no status moved, no `lab run`/`test`/`promote` executed.

**Commit message** (style: the lab's own):

```
lab: role_of -- the 127 control arms kind_of cannot see

`kind_of` answers "is this arm shape-checkable?" and finds 62 placebo arms among the 821 the
lab's 157 method files declare. The rationales contain 189 control arms. The 127 it misses
announce themselves in prose -- "Control:", "Paired control:", "Reaction-negative control:",
"Yardstick:", "...: the control, expected to trail" -- and widening DRAW_MARKERS to reach them
would move D17 on nine dev-eligible methods, so this is a second reader beside kind_of rather
than a change to it.

role_of(arm) -> control | dose | idea | treatment. It asks kind_of first and honours its answer,
so it can never contradict the arm-kind the gate already acts on. Nothing reads it yet: D17's
population, every verdict and every byte `lab control` prints are unchanged, verified by diff.

Measured 2026-10-20 over all 821 arms: 594 treatment / 189 control / 33 dose / 5 idea. Every
marker carries its hit count, per this module's convention. One arm differs from the audit's
prototype classifier -- M0244-STALE30, which the prototype read as treatment and which kind_of
has called dose-response since 2026-10-19; the production answer agrees with kind_of. The
control count, the only one anything will act on, is identical.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

---

## Handoffs

**To phase 2 (D18), and it will need all four of these:**

1. **Import surface.** `from seer_engine.lab import control_shape as cs`, then
   `cs.role_of(arm) == cs.ROLE_CONTROL`. Validate against `cs.ROLES`, never against a literal.
2. **`role_of` takes an `Arm`, not a candidate id.** `store.best_dev_eligible` returns a trial row
   whose `candidate_id` is a string; the rationale lives only in the method file. Phase 2 must
   resolve the id to its `Candidate` the way `control_shape.for_method` does —
   `method.discover()[method_id][0].all_candidates()` — and import `discover` **inside** the
   function, not at module scope, or it imports all 157 method modules on any import of
   `hardgate`. Measured 2026-10-20: the lab database holds 875 distinct dev `candidate_id`s
   against 821 file arms, so **an id with no file arm is a real state** (a sibling worktree's
   method). It has no role, and D18 must fail open on it — silence, not a refusal — for the same
   reason `UNRESOLVED` never refuses here.
3. **The population phase 2 will refuse, measured 2026-10-20 against a scratchpad copy of
   `lab/lab.sqlite`:** 86 dev-eligible methods, whose `best_dev_eligible` arm reads **56
   treatment / 21 control / 9 dose**, with no id missing a file arm. The audit's F4 table said
   46/19/9 of 78 — the lab has grown by eight dev-eligible methods since; the dose count is
   unchanged and the control share is the same. Phase 2 must re-measure before quoting a number,
   and must quote its own.
4. **`dose` is not a sharp bucket, and D18 must act on `control` alone.** `M0174-C40-SW` and
   `M0179-N40-SW` — two of the audit's five flip candidates and the *promoted* arms of their
   methods — read as `dose`, because "a 40-name rung of the low-correlation book" is a width rung
   and `rung of the` is a measured dose marker. Refusing a `dose` promotion would refuse those two
   for a reason no one argued. R3's refusal is about arms registered **to be beaten**, which is
   `ROLE_CONTROL` and nothing else.

**To phase 3 (era edge):** same import surface. The 19 era-edge columns the analysis found
reporting a control arm are identified with `role_of(...) == ROLE_CONTROL` over the arms
`commands/lab.py:_walkforward` already has in hand. Phase 3 owns the column and the label; phase 1
provides no formatting helper and none should be added here.

**Found and deliberately not done** (none of it belongs to R3):

- `DOSE_MARKERS` under-counts too: `rung of the` reaches 21 arms and `kind_of` sees 4 of them.
  Widening `DOSE_MARKERS` itself would re-point `_eligible_targets` and move D17 on nine
  dev-eligible methods, which is a gate change needing its own argument and its own commit. Not
  this phase, and not phase 2 either.
- The module docstring's *"770 candidates in the lab's 271 method files"* does not match today's
  157 files / 280 recorded methods and is probably a method-row count mislabelled as a file count.
  It is a frozen record of a 2026-10-19 measurement. Left exactly as written; the new block carries
  its own date and denominator so the two cannot be confused.
- `DECLARATION_ATTR` would let a method file state its own arm roles outright, which is the
  forward path the module already names for `kind_of`. A `role=` field on `Candidate` is the right
  long-run answer and it is a `backtest.dev` change with a `config_digest` argument attached — see
  the memory note that a shared params field cannot gain a column. Out of scope.

## Rollback

`git revert` the single commit. The two files return to their current contents; nothing else in
the tree referenced `role_of`, no database row, method id, digest, status or recorded verdict was
touched, and `lab control`'s output was already identical, so there is nothing to un-print. If
phases 2 or 3 have landed on top, revert those first — they import `role_of` and will not build
without it.
