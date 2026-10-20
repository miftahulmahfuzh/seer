# Phase 2: D18 — refuse a promotion whose pre-registered variant is a control

**Plan set:** `docs/plans/FOLD_SELECTOR_AUDIT_PLAN.md`
**Analysis:** `docs/analyzer/20261020-162754-F0LD_code_analyzer.md` (finding **F4**)
**Satisfies:** R3 — *a recommendation on `hardgate.py` with the argument written out*, in code
**Depends on:** Phase 1 (`control_shape.role_of`)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab/`

---

## Goal

After this phase `hardgate.check()` asks what the variant `lab promote` would pre-register **is**,
not only whether it won its folds. A promotion whose pre-registered arm is a **control** — an arm
registered to be beaten — is refused by name, with the arm's own pre-registered rationale quoted
back and the way back named. Nineteen dev-eligible methods are inside that rule today, three of
them (M0033, M0035, M0044) currently stopped only by the kin clause, which is luck. The fold
selector is not touched: this is the opposite road from the (A) the audit refused.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `hardgate.promoted_arm_role(method_id, candidate_id) -> tuple[str, str] | None`
  (`engine/src/seer_engine/lab/hardgate.py`, new function inserted at ~`:922`, between
  `mis_shaped_controls` and `mismatches`)
- a new refusal clause inside `hardgate.check()` (`hardgate.py:1823`), between the D11b
  own-variant clause and the D16 survivorship clause, both of which stay byte-identical
- the **(D18)** section of the `hardgate` module docstring (`hardgate.py:666`, immediately before
  the closing `"""` at `:667`)
- test section `(D18)` in `engine/tests/test_lab_hardgate.py` (appended after `:1726`), with
  module-level constants `R_CONTROL`, `CONTROL_PROMOTED` and `DOSE_PROMOTED`, and helper
  `_arm_row`

**Signature changes:** none. `check(conn, method_id) -> None` is unchanged; it raises
`store.LabError` in one more case.

**Requires (from earlier phases):**
- `control_shape.role_of(arm) -> str` — Phase 1
- `control_shape.ROLE_CONTROL` (the `"control"` value of the `ROLE_*` vocabulary) — Phase 1
- `control_shape.ROLE_DOSE` — read by one test only, as the negative control on `M0174-C40-SW`
  and `M0179-N40-SW`. `ROLE_IDEA` and `ROLE_TREATMENT` are not read at all. Only `ROLE_CONTROL`
  refuses.
- `role_of` must keep `kind_of`'s dose-before-draw ordering, so a dose rung is never `control`.

**Leaves alone (owned by others):**
- `hardgate._dev_curves` (`:850`), `walkforward.pick` (`walkforward.py:176`),
  `hardgate.fold_record` (`:1045`), `hardgate.variant_record` (`:1096`),
  `store.best_dev_eligible` (`store.py:1234`) — the fold selector and the promotion ranking.
  Verdict (B); the plan index's *"The argument for (B)"* is the reason, and D18's prose restates
  it so the refusal can explain why it did not go the other way.
- `commands/lab.py:_walkforward` and the `2009-15 edge` column, `walkforward.buy_signal`,
  `walkforward.BUY_CONDITIONS` — **Phase 3** (R4).
- `control_shape.kind_of`, `findings`, `refusals`, `REFUSE_BAND`, `WARN_BAND` — Phase 1 keeps
  D17's population exactly as it is, and this phase reads none of them.
- `lab/lab.sqlite`, `web/data/lab.json`, every recorded trial, verdict, digest and method file.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/hardgate.py` | modify | `(D18)` prose at `:666`; new `promoted_arm_role` at `:922`; new clause in `check()` at `:1823` |
| `engine/tests/test_lab_hardgate.py` | modify | new `(D18)` section appended after `:1726` — 14 tests, 1 helper, 3 constants |

Nothing else. No migration, no lab row, no method file, no `web/`.

---

## Implementation Steps

### Step 1: Write the (D18) decision into the module docstring

**File:** `engine/src/seer_engine/lab/hardgate.py:666`
**Change:** insert the block below between line 666 (`…rather than after the sentence is
published.`, the last line of D17) and line 667 (the closing `"""`). Leave one blank line either
side, as every other decision has.

**Trap — `test_there_is_no_override` (`test_lab_hardgate.py:671`) greps `inspect.getsource(hardgate)`
for the bare substrings `force`, `override`, `skip_gate`, `SEER_SKIP`, `getenv`, `environ`, after
deleting the literals `"no override"` and `"There is no override"`.** So the prose and the refusal
below must not contain the substring `force` **at all** — not in *enforce*, *reinforce*, *in
force*, *forced* — and may use `override` only inside the phrase `no override`. Both blocks below
are already written to that rule; keep it when editing them.

**Code:**

```
**(D18) Does the gate check WHAT the variant it is about to pre-register IS? -- Yes, and from
2026-10-20 ``check`` REFUSES a promotion whose pre-registered variant is a control arm.**

(D11) asks whether the variant ``lab promote`` would pre-register won its own folds. It never asks
what that variant *is*. ``store.best_dev_eligible`` -- the very call ``prereg.promote_method``
makes -- is ``ORDER BY mar DESC, n ASC`` over the method's dev trials with an eligibility filter
and **no role filter**, so the arm that takes the pre-registration, the counted look and later the
owner's money is simply the highest-MAR eligible arm of the family. A **control arm** -- an arm
the method registered in order to beat it -- is ranked there like any other.

It is worse than an oversight, because the two facts lean the same way. A control is
systematically the lowest-turnover and the shallowest-falling arm a method holds, and MAR is
return over fall: the property that makes an arm a good control is the property that wins this
ranking. The audit that produced this rule predicted *"fewer than a third"* and measured 55%
on the neighbouring question, for exactly that reason.

Measured 2026-10-20 over the 78 dev-eligible methods, the role -- read by ``control_shape.role_of``
from the arm's own pre-registered rationale -- of the arm ``lab promote`` would pre-register:

=====================  =========  ===============================================================
role of that arm       methods    treated how
=====================  =========  ===============================================================
treatment              46         promoted as before; this clause is silent
**control**            **19**     **refused here**
dose-response          9          the rung **is** the measurement (D17); never refused here
no eligible variant    4          nothing to pre-register; (D11) is already silent, and so is this
=====================  =========  ===============================================================

**Why 78 and not 86.** ``store.best_dev_eligible`` returns a row for 86 methods, and 21 of those
rows are control arms. The extra twelve -- M0012, M0021, M0022, M0029, M0075, M0077, M0156, M0161,
M0176, M0180, M0203, M0213 -- are nine ``rejected`` and three ``test-failed``, and ``check`` is
silent for every status but ``dev-eligible``: ``store.TRANSITIONS`` admits exactly one edge into
``promoted`` and it starts there. Quoting the wider number would claim this clause stops a
promotion the status machine has already stopped, which is a count nobody earned. The other
direction is the same discipline. Four dev-eligible methods -- M0007, M0011, M0019, M0020 -- hold
no trial the current gate and N call eligible, so ``best_dev_eligible`` names nothing for them and
this clause is silent for the reason (D11)'s own *"Silent when ``best_dev_eligible`` names
nothing"* paragraph gives. All of it measured against the live lab at sha1 ``f2ff9ce6``, 280
methods and 879 trials.

The nineteen, each with the arm it would have pre-registered:

=========  =====================  =========  =====================  =========  =================
method     arm                    method     arm                    method     arm
=========  =====================  =========  =====================  =========  =================
M0033      M0033-TV22-N21         M0101      M0101-CTRL             M0193      M0193-S2-SW
M0035      M0035-CTRL             M0107      M0107-HOST             M0202      M0202-PLC1-HALF
M0044      M0044-NOBRAKE          M0122      M0122-CALM-EQ          M0215      M0215-CTRL
M0047      M0047-EQ               M0137      M0137-EXP              M0223      M0223-TOP20
M0076      M0076-X-M-D            M0168      M0168-CTRL             M0242      M0242-R-H6
M0083      M0083-X-UP-D           M0169      M0169-L20-SW
M0085      M0085-EX-M             M0187      M0187-H3-SW
=========  =====================  =========  =====================  =========  =================

**Why the fold clauses do not already catch it.** Three of the nineteen -- M0033, M0035 and M0044
-- clear **both** (D11) clauses at 3 of 4 and are stopped only by (K). That is luck. Kin is a
statement about the company a method keeps; it has nothing to say about which of the method's own
arms was chosen, and the next method of this shape with a clean family is promotable today. M0202
is the case that says the problem out loud: its pre-registered arm would be ``M0202-PLC1-HALF`` --
*"Placebo: the same scoreable names in a fixed hash order (seed 1), same guard"* -- and (D11b) was
asking in earnest whether that hash order won its folds.

**What the refusal means, and why it is not a technicality.** When a method's control out-MARs
every treatment arm it holds, the control has beaten the idea on the dev window. That is a result,
and it is the result the control was drawn to look for. Promoting it would spend one of the lab's
counted looks on the null and then hand the owner a book of hash-ordered names. The gate exists
because four of four looks have already failed on *beats SPY TR*; it may not spend the fifth on an
arm nobody is proposing.

**Why in ``check`` and not in ``best_dev_eligible``.** A role filter in the ranking would be silent
and retroactive. ``best_dev_eligible`` is what every recorded sentence in this lab means by "its
best version" -- ``lab survivorship``'s *"the numbers below are for its best version"*, ``lab
status``'s closest-to-eligible block, every insight that quoted a method's number. Re-ranking would
move what all of them refer to, with no line of output anywhere saying so. A gate clause measures
nothing new and moves no recorded row: it refuses, by name, with the arm and its author's own
sentence quoted back, and it is argued in git where a reader can disagree with it. That is the only
mechanism this module has ever offered.

**Why this is not the selector change the same audit refused.** The audit asked whether
``walkforward.pick`` should stop ranking controls inside each fold, and answered **no**. The fold's
stated question is *"which variant would the lab's own rule have named at this point in time"*, and
the lab's own rule ranks the whole family; a selector that excluded controls would simulate a
promotion rule the lab does not have and report a cleaner out-of-sample record than the lab's real
behaviour has earned. Measured over the 44 kin-clean fold-refused methods, constraining it left 31
records unchanged, flipped exactly two complete verdicts -- M0174 and M0178, both to *promotable*
on a **negative** 2009-2015 era edge (-0.6% and -2.1%) -- and made M0107 worse, 2 of 4 -> 1 of 4,
because the arms it had been winning on were its own controls. Four methods (M0187, M0193, M0260,
M0261) hold no treatment arm at all, so the restriction is undefined for them. This clause takes
the opposite road deliberately: leave the simulation honest about what the lab does, and refuse
what the lab does.

**Absence is not evidence, here as everywhere.** The role is read from the arm's one-line rationale
in the method's own ``lab/methods/mNNNN_*.py`` file. When no file declares the method, or the file
declares no arm carrying the recorded candidate id, ``promoted_arm_role`` returns **None and
nothing is refused**. That is (D16)'s sentence and (D17)'s behaviour, and it costs nothing real: a
method with no file cannot be promoted at all -- ``prereg`` refuses it on ``methods.source_sha``
long before anything reaches this clause -- so deleting a file is not a way past this rule, it is a
way out of ``lab promote`` altogether. The alternative, refusing every arm whose prose could not be
read, would turn a reader's limitation into a verdict about a method, which is the mechanism by
which a rule stops being about the thing it was written for. (D10) fails *closed* on an unknown and
this one fails open, and the difference is what the unknown is about: there, a missing price
fingerprint would let two curves be compared across two histories, so the unknown corrupts a
measurement the gate is making; here there is simply no claim to make, and the other clauses still
run.

**A dose rung is not a control, and neither is an idea arm.** ``control_shape.role_of`` tests dose
before draw for (D17)'s reason -- ``M0241-STALE``'s rationale carries the word "control" and is a
dose-response arm, and a permanent false alarm on a correct arm is how a rule gets switched off.
Nine of the 78 would pre-register a dose rung; the rung **is** the measurement, so they pass to the
clauses below without comment. Only ``ROLE_CONTROL`` refuses.

**The way back, and it costs no method id.** Register an arm that is actually the idea, run it as
an amendment -- an amendment appends trials under the method's existing id -- and let it out-MAR
the control. ``best_dev_eligible`` then names it and this clause goes silent. If no treatment arm
the method can write will out-MAR its own placebo, the method has its answer already and should not
be spending a look to confirm it. Same shape of remedy as (D17)'s re-draw, for the same reason: a
refusal that named no way back would be a dead end.

**M0044 is in (D11)'s table and in this one, and the arm has changed.** (D11) was measured on
2026-10-09, when ``M0044-TV14-N21`` was M0044's only eligible variant. Today ``best_dev_eligible``
names ``M0044-NOBRAKE`` -- *"Control: M0036-BLEND re-stated under this allocator, no brake"*.
Nothing in (D11)'s argument moves. What the change shows is that "the arm that gets the money" is a
live query over a growing trial set and not a fact anybody wrote down, which is exactly why this
clause asks it at promote time rather than recording an answer.

**Where it sits in ``check``, and why.** After (D11)'s two clauses and before (D16). The fold
clauses are about evidence and read first; (D16) and (D17) are both statements about *this same
arm*, so "what is this arm" belongs in front of "is its fall honest" and "is its control shaped
right". It is one dictionary lookup and one string scan over a module (D17) already imports, so the
order is about the sentence a refused researcher reads, not about cost.

**What it does not reach.** ``walkforward.buy_signal``, for (D13)'s reason exactly: the signal
follows (K) through its caller and does not follow (D11)'s own-variant clause either, and whether
it should follow this one is an edit to ``walkforward.py`` and the owner's to decide. It does not
reach ``lab run`` (D15): a second gate at run time would only spend method ids to say what this one
already says. And it moves no band, no recorded row and no closed verdict.

**Who it stops today, measured.** Nineteen dev-eligible methods, every one of them already refused
by the gate on another clause -- three of them (M0033, M0035, M0044) by (K) alone -- so **no
promotion that would happen today stops happening** and ``lab status``'s ``Promotable now:`` line
does not move. As with (D12), (D14) and (D17), the point is forward: the next method whose placebo
out-MARs its idea is stopped before the look is spent, rather than after the owner is holding the
book.
```

> **Measurement the implementer MUST take before committing.** The last paragraph's claim —
> *"every one of them already refused … `Promotable now:` does not move"* — is the invariant this
> phase promises, and it must be **measured**, not assumed (see **Verification**, the before/after
> sweep). If the sweep shows a method that passes the gate today and is refused by D18 after, do
> **not** soften the rule: rewrite that paragraph to name the method and say that the promotable
> set shrinks by one, which is the rule working. If the sweep shows any method moving from refused
> to passing, stop — that is a bug in this phase, not a finding.

**Impact:** `test_the_module_answers_the_four_open_questions` and the other docstring tests keep
passing (they assert presence, never absence). `test_there_is_no_override` keeps passing provided
the `force`/`override` rule above is honoured.

---

### Step 2: Add `promoted_arm_role` beside `mis_shaped_controls`

**File:** `engine/src/seer_engine/lab/hardgate.py:922`
**Change:** insert the complete function below between `mis_shaped_controls`'s last line
(`    return control_shape.refusals(found)`, line 920) and `def mismatches(` (line 923). Keep the
two blank lines on each side that the module uses between top-level definitions.

**Code:**

```python
def promoted_arm_role(method_id: str, candidate_id: str) -> tuple[str, str] | None:
    """``candidate_id``'s declared role and the one line its author wrote for it. See (D18).

    ``(role, rationale)``, where ``role`` is one of ``control_shape``'s ``ROLE_*`` values, or
    **None** when the arm cannot be read at all -- no method file declares ``method_id``, or the
    file declares no arm carrying that id.

    **None is not a verdict, and the gate refuses nothing on it.** A method with no file cannot be
    promoted anyway: ``prereg`` refuses it on ``methods.source_sha`` long before anything reaches
    this clause, which is the same reason ``control_shape.for_method``'s docstring gives for
    reading the file here. And a recorded candidate id that no arm in the file carries is the
    reader failing, not the method failing -- absence is not evidence (D16), and the clauses below
    still run on it. Refusing on a role nobody could read is the mechanism by which a rule stops
    being about the thing it was written for.

    It takes no connection. The role is the author's prose, pre-registered in the method file and
    outside ``config_text``, so no recorded row is consulted and no digest can move by reading it.

    Both imports are inside the body. ``control_shape`` for ``mis_shaped_controls``' reason -- a
    module-level import would make the next edit to either module a fifty-fifty bet on an import
    cycle, exactly as ``Run``'s docstring in ``lab/runner.py`` says about this module. ``discover``
    for ``for_method``'s reason: at module scope it would import all 271 method modules on any
    import of this one.

    ``discover``'s own ``ValueError`` -- two modules claiming one id -- is deliberately **not**
    caught. ``mis_shaped_controls`` one clause later does not catch it either, and a checkout whose
    method package cannot be enumerated is a broken tree, not a promotion question.
    """
    from seer_engine.lab import control_shape
    from seer_engine.lab.method import discover

    entry = discover().get(method_id)
    if entry is None:
        return None
    method, _path = entry
    for arm in method.all_candidates():
        if str(arm.id) == candidate_id:
            return control_shape.role_of(arm), str(arm.rationale)
    return None
```

**Impact:** a new public symbol. Nothing calls it yet after this step, so the tree still builds and
the suite is still green between step 2 and step 3.

---

### Step 3: Add the clause to `check()`

**File:** `engine/src/seer_engine/lab/hardgate.py:1823`
**Change:** insert the block below **inside** the `if candidate is not None:` body, after the
closing `)` of the D11b `if not own.majority:` raise (line 1822) and the blank line that follows
it, and **before** `sv_dd = survivorship_record.over_bar(...)` (line 1824). Indentation is eight
spaces — it is inside `if candidate is not None:`, not at function level. Leave a blank line after
the new block so `sv_dd = …` keeps its spacing.

**Code:**

```python
        # (D18) `best_dev_eligible` ranks every eligible arm by MAR with no role filter, so the
        # arm that takes the pre-registration, the look and the money can be the arm the method
        # registered in order to beat it -- 19 of the 78 dev-eligible methods, measured. A control
        # is systematically the lowest-turnover, shallowest-falling arm a method holds, which is
        # what MAR rewards, so this is the ranking's own tendency rather than an accident.
        #
        # Only a role the method file actually declares refuses. An arm `promoted_arm_role` cannot
        # find comes back None and is left to the clauses below, because absence is not evidence
        # (D16) and a method with no file is refused by `prereg` on its source sha anyway. A dose
        # rung is not a control -- the rung IS the measurement (D17) -- and neither is an idea arm.
        arm_role = promoted_arm_role(method_id, candidate)
        if arm_role is not None:
            from seer_engine.lab import control_shape

            role, rationale = arm_role
            if role == control_shape.ROLE_CONTROL:
                raise store.LabError(
                    f"{method_id} is not promoted: {candidate} -- the variant `lab promote` "
                    f"would pre-register -- is a control arm, one this method registered in "
                    f"order to beat it: {rationale!r}. `store.best_dev_eligible` ranks every "
                    f"eligible arm by MAR with no role filter, and a control is systematically "
                    f"the lowest-turnover, shallowest-falling arm a method holds, which is what "
                    f"MAR rewards. So when a method's control out-ranks its idea, the finding is "
                    f"that the idea did not beat its own placebo on the dev window -- not that "
                    f"the placebo is ready for a counted look and the owner's money (D18). The "
                    f"way back: register an arm that is the idea and run it as an amendment, "
                    f"which costs no method id because an amendment appends trials under this "
                    f"id; once it out-MARs this one, `best_dev_eligible` names it instead and "
                    f"this clause is silent. Nothing was written and no status moved. There is "
                    f"no override -- if the rule is wrong, change it in "
                    f"seer_engine/lab/hardgate.py and argue for it in the commit"
                )

```

**Impact:**
- `commands/lab.py:_promote` (`:1863`) refuses one more class of method, exit code 2, nothing
  written — the refusal is before `prereg.promote_method`, so the repository and the database stay
  byte-identical.
- `commands/lab.py:_gate_states` (`:1274`), which `lab status` uses to compute `Promotable now:`,
  picks the new reason up with no edit. That is the intended path and is why the message has to
  read as one printable line.
- Every clause before and after it is untouched, so a method refused today by D11, D16, D17 or (K)
  is still refused, with the same sentence, except where D18 now speaks first (only possible for a
  method whose promoted arm is a control — which was already refused, by something).

**Also update the `check` docstring** at `hardgate.py:1762-1765`. Replace the sentence

```
    whether the variant actually chosen won its folds itself. All of it is cheap -- SQL and
    arithmetic on recorded curves -- so the order is about the message, not the cost.
```

with

```
    whether the variant actually chosen won its folds itself. (D18) then asks what that variant
    *is* and refuses a control arm, before (D16) and (D17) ask whether its fall is honest and its
    own control is shaped right -- all three are statements about the same one arm, and "what is
    it" reads in front of the other two. All of it is cheap -- SQL, arithmetic on recorded curves
    and one read of the method file -- so the order is about the message, not the cost.
```

---

### Step 4: Tests

**File:** `engine/tests/test_lab_hardgate.py` — append after line 1726 (end of file).

The seam is the same one the D17 section's header describes: `_declare` is the only way a
synthetic method's arms can be read at all. Without it `discover()` finds the *real* `M0001`
file, which declares `TV10`/`TV12`/`TV10-W`/`TV10-NOTREND` and no `M0001-A`, so the role comes
back `None` and this clause correctly does nothing — which is itself one of the tests below.

**Code:**

```python
# --- (D18): the arm that takes the money may not be the arm registered to be beaten ------------
#
# Same seam as (D17) above and for the same reason: `_declare` is what lets a synthetic arm's
# rationale be read at all. These tests turn on which arm `store.best_dev_eligible` names, which
# is MAR then `n`, so they move MAR -- `_control_arm` records at the fixture default and loses the
# tie-break to the book itself.

R_CONTROL = "Control: the same book with the brake taken out, nothing else changed"

# The nineteen dev-eligible methods whose pre-registered arm reads `control`, measured read-only
# on 2026-10-20 against this tree's committed lab. Named in (D18)'s own text.
CONTROL_PROMOTED: tuple[tuple[str, str], ...] = (
    ("M0033", "M0033-TV22-N21"), ("M0035", "M0035-CTRL"), ("M0044", "M0044-NOBRAKE"),
    ("M0047", "M0047-EQ"), ("M0076", "M0076-X-M-D"), ("M0083", "M0083-X-UP-D"),
    ("M0085", "M0085-EX-M"), ("M0101", "M0101-CTRL"), ("M0107", "M0107-HOST"),
    ("M0122", "M0122-CALM-EQ"), ("M0137", "M0137-EXP"), ("M0168", "M0168-CTRL"),
    ("M0169", "M0169-L20-SW"), ("M0187", "M0187-H3-SW"), ("M0193", "M0193-S2-SW"),
    ("M0202", "M0202-PLC1-HALF"), ("M0215", "M0215-CTRL"), ("M0223", "M0223-TOP20"),
    ("M0242", "M0242-R-H6"),
)

# The negative control, on real arms. Both of these pre-register a DOSE-RESPONSE rung, and both
# are methods the audit's refused fork (A) would have flipped to promotable -- so they are exactly
# the pair a careless widening of ROLE_CONTROL would catch. The rung IS the measurement (D17).
DOSE_PROMOTED: tuple[tuple[str, str], ...] = (
    ("M0174", "M0174-C40-SW"), ("M0179", "M0179-N40-SW"),
)


def _arm_row(conn, mid: str, suffix: str, *, mar: float, trades: int = 252,
             turnover: float = 1.08, annual: float = 0.15) -> None:
    """One more recorded dev arm of ``mid``, at a MAR of its own.

    `_control_arm` above records at the fixture's default MAR, which ties with the book's and then
    loses the `n ASC` tie-break, so it can never be the promoted variant. (D18) turns on exactly
    which arm `store.best_dev_eligible` names, so these tests move MAR rather than trade counts.
    The default shape -- 252 trades, 1.08 turnover against the book's 250 and 1.1 -- is inside
    `WARN_BAND`, so (D17) stays silent and only the clause under test can speak.
    """
    with conn:
        ns = store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-{suffix}", config_digest=f"d-{mid}-{suffix}",
            mar=mar, trades=trades, turnover=turnover,
            curve_json=_curve(_months(*DEV_SPAN), annual),
        )])
        stamp_provenance(conn, ns, price_fingerprint=SAME_PRICES)


def test_the_module_records_the_promoted_arm_role_decision():
    """(D18) is argued where the other seventeen are, with its measurement and its live case."""
    doc = hardgate.__doc__ or ""
    assert "(D18)" in doc
    assert "M0202-PLC1-HALF" in doc                        # the live case, named
    assert "best_dev_eligible" in doc and "no role filter" in doc
    # The three the fold clauses already clear, stopped only by the kin rule -- the luck.
    assert "M0033" in doc and "M0035" in doc and "M0044" in doc
    assert "M0044-NOBRAKE" in doc
    # The fork the same audit refused, recorded beside the one it took.
    assert "M0174" in doc and "M0178" in doc and "walkforward.pick" in doc
    # Fails open, and says whose sentence that is.
    assert "absence is not evidence" in doc.lower()
    # The way back, and that it is free.
    assert "amendment" in doc and "costs no method id" in doc


def test_a_promotion_whose_variant_is_a_control_is_refused_and_quotes_the_rationale(
    conn, monkeypatch
):
    """M0202's shape: the highest-MAR eligible arm is the placebo, so the placebo takes the look."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)                    # M0001-A, the idea, MAR 0.8
    _arm_row(conn, "M0001", "PLC1", mar=0.95)              # the placebo, higher MAR
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-PLC1", R_DRAW)])

    assert hardgate.promoted_variant(conn, "M0001") == "M0001-PLC1"
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    said = str(e.value)
    assert "M0001-PLC1" in said
    assert "control arm" in said and "registered in order to beat it" in said
    assert "hash-drawn names" in said                      # the author's own sentence, quoted back
    assert "D18" in said
    assert "Nothing was written and no status moved" in said
    assert "There is no override" in said
    assert "amendment" in said and "costs no method id" in said


def test_a_control_arm_that_is_not_the_promoted_one_does_not_refuse(conn, monkeypatch):
    """The ordinary method: it holds a placebo and its idea out-MARs it. (D18) is silent.

    This is the half of the rule that matters most -- most of the lab holds a control arm, and a
    clause that refused all of them would be a stopped lab rather than a stricter one.
    """
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)                    # MAR 0.8
    _arm_row(conn, "M0001", "PLC1", mar=0.50)              # the placebo, lower MAR
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-PLC1", R_DRAW)])

    assert hardgate.promoted_variant(conn, "M0001") == "M0001-A"
    hardgate.check(conn, "M0001")                          # returns: no refusal


def test_a_promoted_dose_rung_is_not_a_control(conn, monkeypatch):
    """(D17)'s dose-before-draw ordering, carried into this clause: the rung IS the measurement.

    `M0244-STALE30` is the live shape. A permanent false alarm on a correct arm is how a rule gets
    switched off, so the dose arms have to pass here as they pass the shape check.
    """
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _arm_row(conn, "M0001", "STALE30", mar=0.95)
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-STALE30", R_DOSE)])

    assert hardgate.promoted_variant(conn, "M0001") == "M0001-STALE30"
    hardgate.check(conn, "M0001")


def test_a_plain_treatment_arm_promotes_exactly_as_before(conn, monkeypatch):
    """A method whose only arm is the book itself: no role to object to, nothing refused."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_PLAIN)])

    hardgate.check(conn, "M0001")


def test_an_arm_the_method_file_does_not_declare_does_not_refuse(conn, monkeypatch):
    """Fails OPEN, for (D16)'s reason: absence is not evidence.

    The recorded id is `M0001-A` and the file declares only `M0001-Z`, so the role cannot be read
    at all. A reader's limitation is not a verdict about a method, and the clauses below still run.
    """
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _declare(monkeypatch, M0001=[_Arm("M0001-Z", R_DRAW)])

    assert hardgate.promoted_arm_role("M0001", "M0001-A") is None
    hardgate.check(conn, "M0001")


def test_a_method_with_no_file_does_not_refuse(conn, monkeypatch):
    """And deleting the file is not a way past the rule: `prereg` refuses a method with no file on
    its source sha long before this clause, so an empty answer here is a missing role, not a
    waiver."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _declare(monkeypatch)                                   # discover() -> {}

    assert hardgate.promoted_arm_role("M0001", "M0001-A") is None
    hardgate.check(conn, "M0001")


def test_the_role_is_read_from_the_prose_and_never_from_the_id(conn, monkeypatch):
    """`control_shape`'s founding rule, asserted at the gate: `M0005-ALL-R`'s `-R` is a
    rank-weighting variant, not a control. An id-suffix rule would refuse this promotion."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _arm_row(conn, "M0001", "R", mar=0.95)
    _declare(monkeypatch, M0001=[
        _Arm("M0001-A", R_IDEA),
        _Arm("M0001-R", "The same composite with linear rank weights: does conviction pay"),
    ])

    assert hardgate.promoted_variant(conn, "M0001") == "M0001-R"
    hardgate.check(conn, "M0001")


def test_a_perfectly_shaped_control_is_still_a_control(conn, monkeypatch):
    """(D17) and (D18) ask different questions of one arm, and both have to be asked.

    A placebo drawn at exactly the book's trade count and turnover clears the shape band -- and is
    still the wrong thing to spend a counted look on.
    """
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _arm_row(conn, "M0001", "PLC1", mar=0.95, trades=250, turnover=1.1)
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-PLC1", R_DRAW)])

    assert not hardgate.mis_shaped_controls(conn, "M0001")   # 1.00x / 1.00x: (D17) is content
    with pytest.raises(store.LabError, match="D18"):
        hardgate.check(conn, "M0001")


def test_the_fold_clauses_still_speak_first(conn, monkeypatch):
    """Order inside `check`: evidence before identity.

    A control arm that also loses its own folds is refused by (D11b), which is the more basic thing
    wrong with it, and the researcher reads that sentence rather than this one.
    """
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _arm_row(conn, "M0001", "PLC1", mar=0.95, annual=0.02)  # promoted, and loses every fold
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-PLC1", R_DRAW)])

    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    said = str(e.value)
    assert "(D11)" in said and "D18" not in said


def test_a_control_prefixed_rationale_is_a_control_here(conn, monkeypatch):
    """M0044's live shape -- "Control: M0036-BLEND re-stated under this allocator, no brake".

    Phase 1 widened `control_shape`'s vocabulary to the `Control:` prefix that most of the lab's
    control arms actually use; this is the gate asserting it reads one.
    """
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _arm_row(conn, "M0001", "NOBRAKE", mar=0.95)
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-NOBRAKE", R_CONTROL)])

    with pytest.raises(store.LabError, match="D18"):
        hardgate.check(conn, "M0001")


def test_lab_promote_exits_2_and_writes_nothing_when_the_variant_is_a_control(
    tmp_path, monkeypatch
):
    db, prereg_dir = tmp_path / "lab.sqlite", tmp_path / "prereg"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", annual=0.15)
    _arm_row(c, "M0001", "PLC1", mar=0.95)
    before = db.read_bytes()
    c.close()
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-PLC1", R_DRAW)])

    assert _cli(tmp_path, db, prereg_dir) == 2
    assert not prereg_dir.exists()
    assert db.read_bytes() == before


def test_the_nineteen_are_still_the_nineteen_or_have_moved_on(monkeypatch):
    """(D18)'s population, on the committed lab, allowed exactly two states and never neither.

    Each named method either still pre-registers the control arm (D18)'s text names, or has since
    amended an arm that out-MARs it -- the way back, working. Pinning only "still a control" would
    go red the day a method takes the remedy the refusal asks for, which is the wrong direction for
    a test to fail in.

    `store.COMMITTED_DB` opened `mode=ro` and never through `store.connect`, which migrates and so
    dirties the file on a read. The bytes are hashed either side. `DSR_POLICY` is put back to the
    lab's real default, because this module's autouse fixture pins it to the one its own synthetic
    rows were recorded under and the committed lab is not judged under that one.
    """
    from seer_engine.lab import npolicy

    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    monkeypatch.setattr(store, "DSR_POLICY", npolicy.DEFAULT_POLICY)
    store._GATE_CACHE.clear()

    before = hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest()
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        from seer_engine.lab import control_shape as cs

        for mid, named_arm in CONTROL_PROMOTED:
            if store.get_method(conn, mid) is None:
                pytest.skip(f"{mid} is not in this tree's lab")
            arm = hardgate.promoted_variant(conn, mid)
            if arm is None:
                pytest.skip(f"{mid} has no eligible dev variant in this tree")
            role = hardgate.promoted_arm_role(mid, arm)
            if role is None:
                pytest.skip(f"{mid} has no method file in this tree")
            if arm == named_arm:
                assert role[0] == cs.ROLE_CONTROL, f"{mid}: {arm} no longer reads as a control"
            else:
                # It moved. The only acceptable direction is away from a control arm.
                assert role[0] != cs.ROLE_CONTROL, (
                    f"{mid} now pre-registers {arm}, a different control arm"
                )
    finally:
        conn.close()
    assert hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest() == before


def test_a_dose_rung_on_the_committed_lab_is_not_refused(monkeypatch):
    """The negative control, on real arms rather than on a fixture's prose.

    M0174 and M0179 pre-register a dose-response rung. They are also the two methods the audit's
    refused fork (A) would have flipped to promotable, so they are precisely the pair that a
    widened `ROLE_CONTROL` would sweep up by accident -- and a permanent false alarm on a correct
    arm is how a rule gets switched off (D17). Nine of the 78 pre-register a rung; none of them may
    be refused here.

    Same read-only discipline as the test above: `mode=ro`, never `store.connect`, bytes hashed
    either side, and `DSR_POLICY` put back to the lab's real default.
    """
    from seer_engine.lab import control_shape as cs
    from seer_engine.lab import npolicy

    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    monkeypatch.setattr(store, "DSR_POLICY", npolicy.DEFAULT_POLICY)
    store._GATE_CACHE.clear()

    before = hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest()
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for mid, named_arm in DOSE_PROMOTED:
            if store.get_method(conn, mid) is None:
                pytest.skip(f"{mid} is not in this tree's lab")
            arm = hardgate.promoted_variant(conn, mid)
            if arm != named_arm:
                pytest.skip(f"{mid} now pre-registers {arm}, not {named_arm}")
            role = hardgate.promoted_arm_role(mid, arm)
            if role is None:
                pytest.skip(f"{mid} has no method file in this tree")
            assert role[0] == cs.ROLE_DOSE, f"{mid}: {arm} reads {role[0]}, not a dose rung"
            assert role[0] != cs.ROLE_CONTROL
    finally:
        conn.close()
    assert hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest() == before


def test_this_rule_retires_no_promotion_that_already_happened():
    """(D3): a pre-registration is a promise, and `check` is silent for any status but
    `dev-eligible`. None of the nineteen is `promoted`, so nothing already committed to is
    re-judged -- asserted rather than reasoned about, because a rule that retroactively unpicked a
    promise would be the worst available outcome of this edit."""
    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    before = hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest()
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for mid, _arm in CONTROL_PROMOTED:
            row = store.get_method(conn, mid)
            if row is None:
                continue
            assert str(row["status"]) != "promoted", mid
    finally:
        conn.close()
    assert hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest() == before
```

**Impact:** 14 new tests, no existing test edited. `hashlib` and `sqlite3` are already imported at
the top of the module (`:10`, `:12`); `pytest`, `store`, `hardgate` likewise. No new import is
needed at module scope.

---

## Verification

**Build / lint**

```bash
cd /home/miftah/seer
engine/.venv/bin/ruff check engine
engine/.venv/bin/python -c "from seer_engine.lab import hardgate; print(hardgate.promoted_arm_role)"
```

**Tests — the modules that can see this clause**

```bash
cd /home/miftah/seer
PYTHONPATH=engine/src engine/.venv/bin/pytest -q \
  engine/tests/test_lab_hardgate.py \
  engine/tests/test_lab_control_shape.py \
  engine/tests/test_lab_status.py \
  engine/tests/test_lab_prereg.py \
  engine/tests/test_promote_command.py \
  engine/tests/test_lab_fold_verdict.py \
  engine/tests/test_lab_amendments.py
```

**Tests — the whole engine suite** (CI's own command; DB tests need Postgres):

```bash
cd /home/miftah/seer
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
PYTHONPATH=engine/src engine/.venv/bin/pytest engine/tests
```

**The invariant, measured — "this clause may only ever REFUSE more."**

Write this read-only script to the scratchpad. It opens the committed lab `mode=ro` (never
`store.connect`, which migrates and dirties the file) and hashes the bytes either side. Run it
**at HEAD before any edit**, then again after step 3, and diff.

```python
# d18_sweep.py  --  read-only. No store, no backtest, no look, no write.
import hashlib
import json
import sqlite3
import sys

from seer_engine.lab import hardgate, store

db = store.COMMITTED_DB
before = hashlib.sha256(db.read_bytes()).hexdigest()
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
out = {}
for r in conn.execute("SELECT id FROM methods WHERE status='dev-eligible' ORDER BY id"):
    mid = str(r["id"])
    try:
        hardgate.check(conn, mid)
        out[mid] = "PASSES"
    except store.LabError as e:
        out[mid] = " ".join(str(e).split())[:160]
conn.close()
assert hashlib.sha256(db.read_bytes()).hexdigest() == before, "the sweep moved the lab file"
json.dump(out, open(sys.argv[1], "w"), indent=1, sort_keys=True)
print(f"{len(out)} dev-eligible; {sum(v == 'PASSES' for v in out.values())} pass the gate")
```

```bash
cd /home/miftah/seer
S=/tmp/claude-1000/-home-miftah-seer/*/scratchpad
git stash list >/dev/null                      # the tree must be clean at HEAD for the first run
PYTHONPATH=engine/src engine/.venv/bin/python $S/d18_sweep.py $S/before.json
# ... apply steps 1-3 ...
PYTHONPATH=engine/src engine/.venv/bin/python $S/d18_sweep.py $S/after.json
diff -u $S/before.json $S/after.json
```

**What the diff must show, and what it must not:**

- Every changed line is a method whose `before` value was a refusal and whose `after` value is the
  D18 sentence. That is the clause speaking first for an arm that was already refused.
- **`PASSES` -> a refusal** is allowed only if the method's promoted arm is a control; if it
  happens, Step 1's last paragraph must be rewritten to name that method and say the promotable
  set shrinks. Do not soften the rule.
- **A refusal -> `PASSES` is a bug in this phase.** Stop and fix it. This clause only ever refuses.
- The count on the final line must not rise.

**Manual check:** read the refusal once, as a researcher would.

```bash
cd /home/miftah/seer
PYTHONPATH=engine/src engine/.venv/bin/python - <<'PY'
import sqlite3
from seer_engine.lab import hardgate, store
c = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True); c.row_factory = sqlite3.Row
try:
    hardgate.check(c, "M0202")
except store.LabError as e:
    print(" ".join(str(e).split()))
PY
```

It must name `M0202-PLC1-HALF`, quote *"Placebo: the same scoreable names in a fixed hash order
(seed 1), same guard"*, say `D18`, say `Nothing was written and no status moved`, say
`There is no override`, and name the amendment as the way back — in one printable line, because
`lab status` prints it through `one_line`.

**Do NOT run, in this phase or to verify it:** `lab test`, `lab promote`, `lab run`,
`lab survivorship` (it journals on every invocation and the journal is append-only — journal 500 is
already a duplicate of 499 from exactly that mistake). Test-window looks read **4** before this
phase and must read **4** after it.

**Exit criteria**

1. `engine/.venv/bin/pytest engine/tests` is green, with the 14 new tests passing.
2. `ruff check engine` is clean.
3. The before/after sweep shows only refusals gaining the D18 sentence, and no refusal becoming
   `PASSES`.
4. `lab status` still prints the same `Promotable now:` line it printed before the edit (or, if
   not, Step 1's prose names the method that left and the commit message says so).
5. The committed `lab/lab.sqlite` hashes identically before and after every verification run.
6. The commit message carries the argument, as the brief requires.

---

## Commit message

Single commit, both files. The brief's sentence — *"Any change to
engine/src/seer_engine/lab/hardgate.py must be argued in the commit message"* — is what this is
for, so the argument is in the body rather than a pointer to it.

```
lab: D18 -- the arm that takes the money may not be the arm registered to be beaten

`store.best_dev_eligible` is `ORDER BY mar DESC, n ASC` with an eligibility filter and no role
filter. It is the call `prereg.promote_method` makes, so it names the variant that takes the
pre-registration, the counted look and later the owner's real money. Measured 2026-10-20 over the
78 dev-eligible methods, that arm is a CONTROL -- an arm the method registered in order to beat it
-- for 19 of them. M0202's would be `M0202-PLC1-HALF`: "Placebo: the same scoreable names in a
fixed hash order (seed 1), same guard".

This is the ranking's own tendency and not an accident. A control is systematically the
lowest-turnover and shallowest-falling arm a method holds, and MAR is return over fall: what makes
an arm a good control is what makes it win this ranking.

The gate already asked whether the pre-registered variant won its own folds (D11b). It never asked
what that variant was. Three of the nineteen -- M0033, M0035, M0044 -- clear BOTH fold clauses at
3 of 4 and are stopped only by the kin rule. Kin is a statement about the company a method keeps
and has nothing to say about which of its own arms was chosen, so that is luck: the next method of
this shape with a clean family is promotable today. `check` now refuses it, after D11b and before
D16, naming the arm and quoting its author's own sentence back.

WHY NOT THE FOLD SELECTOR. The same audit asked whether `walkforward.pick` should stop ranking
controls inside each fold and answered no, and this commit deliberately does not do that. The
fold's question is "which variant would the lab's own rule have named at this point in time", and
the lab's own rule ranks the whole family; a selector that excluded controls would simulate a
promotion rule the lab does not have and report a cleaner out-of-sample record than the lab's real
behaviour has earned. Measured over the 44 kin-clean fold-refused methods, constraining it left 31
unchanged, flipped exactly two verdicts -- M0174 and M0178, both to promotable on a NEGATIVE
2009-2015 era edge, -0.6% and -2.1% -- and made M0107 worse (2 of 4 -> 1 of 4) because the arms it
was winning on were its own controls. Four methods have no treatment arm at all, so the
restriction is undefined for them. The selector stays honest about what the lab does; this clause
refuses what the lab does.

WHY IN `check` AND NOT IN `best_dev_eligible`. A role filter in the ranking would be silent and
retroactive: `best_dev_eligible` is what every recorded sentence in this lab means by "its best
version", so re-ranking would move what all of them refer to with no output anywhere saying so. A
gate clause measures nothing new, moves no recorded row, refuses by name, and is argued in git
where a reader can disagree with it.

IT FAILS OPEN. The role is read from the arm's pre-registered rationale in the method file. No
file, or no arm carrying the recorded id, returns None and refuses nothing -- D16's sentence,
absence is not evidence. It costs nothing real: `prereg` refuses a method with no file on its
source sha long before this clause, so deleting a file is a way out of `lab promote` entirely, not
a way past this rule. A dose-response rung is not a control (the rung IS the measurement, D17) and
neither is an idea arm; only ROLE_CONTROL refuses.

IT ONLY EVER REFUSES, and that was measured rather than argued. A read-only sweep of every
dev-eligible method's `check` result, taken either side of this change against the committed lab
opened mode=ro and hashed both ways, shows only refusals gaining the new sentence: no method moved
from refused to promotable, and `lab status`'s `Promotable now:` line does not move. All nineteen
were already refused by another clause. None of them is `promoted`, so no pre-registration that
was already made is re-judged (D3).

THE WAY BACK, and it costs no method id. Register an arm that is actually the idea and run it as
an amendment -- an amendment appends trials under the existing id -- and let it out-MAR the
control. `best_dev_eligible` then names it and this clause goes silent. If no treatment arm the
method can write will out-MAR its own placebo, the method already has its answer and should not
spend a look confirming it.

No flag, no environment variable, no "promote anyway" was added, and none exists. The refusal
invites an argued change to this file in git and offers nothing else. This commit is that
mechanism being used, not bypassed.

Nothing ran and nothing was recorded: no store, no backtest, no trial, no method id.
Test-window looks read 4 before and 4 after.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

---

## Assumptions

1. **Phase 1 has landed** and `control_shape` exports `role_of(arm) -> str` plus the `ROLE_*`
   vocabulary, with `ROLE_CONTROL` as the `"control"` value. If Phase 1 names the constant
   differently, `hardgate.py:check` and the `CONTROL_PROMOTED` test are the only two places to
   re-point — one symbol each. **Reconciler: confirm the spelling against Phase 1's contract.**
2. **`role_of` keeps `kind_of`'s dose-before-draw ordering**, so `M0241-STALE`-shaped arms come
   back `ROLE_DOSE` and never `ROLE_CONTROL`. Two tests assert it from this side:
   `test_a_promoted_dose_rung_is_not_a_control` on a fixture, and
   `test_a_dose_rung_on_the_committed_lab_is_not_refused` on `M0174-C40-SW` and `M0179-N40-SW`,
   the two real arms a careless widening would sweep up — and the same two methods fork (A) would
   have flipped to promotable.
3. **`role_of` recognises the `Control:` / `Paired control:` / `Yardstick:` prefixes** Phase 1 was
   written to add — `test_a_control_prefixed_rationale_is_a_control_here` asserts it from this
   side, and M0044-NOBRAKE's real rationale is one of them.
4. **The population is the 78 `dev-eligible` methods, never the 86 for which
   `best_dev_eligible` returns a row.** The extra twelve are nine `rejected` and three
   `test-failed`; `check` returns before any of this for them. Phase 1's handoff note says
   21 of 86 — that number is wrong for this clause and must not reach the D18 prose. The
   nineteen are as the audit measured them on 2026-10-20.** The implementer re-measures with
   The implementer re-measures with the sweep before committing and corrects `CONTROL_PROMOTED`
   and the D18 table together if the lab has moved. The two-state test is written so a method taking the remedy does not turn it red.
5. `store.COMMITTED_DB` exists in the tree; the two committed-lab tests skip cleanly when it does
   not.

## Handoffs

- **R4 / Phase 3** — the `2009-15 edge` column (`commands/lab.py:2620`) and the
  `high_coverage_edge` handed to `walkforward.buy_signal`. For 19 of 74 methods that column is
  measured on a **control** arm (M0201 reports +1.82 pts on `M0201-PLC2-MV10` while its promoted
  arm is at −7.82). This phase deliberately does not touch it: `check()` has no era clause, so
  nothing here reads or moves that number.
- **`walkforward.buy_signal` does not follow D18**, exactly as D13 records that it does not follow
  D11's own-variant clause. The signal could still fire on a method whose pre-registered arm is a
  control. That is an edit to `walkforward.py` and the owner's call; D18's prose says so and
  Phase 3 is the phase that is already in that file.
- **`lab run` prints no D18 line.** D15's reason: a second gate at run time only spends method ids
  to say what this one says. If the owner later wants the role printed beside the fold verdict at
  run time, that is a `runner.py` change, not this one.
- **`control_shape.kind_of` still under-counts** (11 found vs 62 real over the audited picks) for
  every caller that is not `role_of`. Phase 1 owns the vocabulary; D17's population is deliberately
  frozen so no promotion moves on Phase 1 alone.
- **M0044 now has two different arms named across the docstring** — `M0044-TV14-N21` in D11 (2026-10-09)
  and `M0044-NOBRAKE` in D18 (2026-10-20). D18 explains the difference rather than editing D11,
  because D11's table is a dated measurement and this lab does not retouch those.

## Rollback

`git revert <sha>` restores the prior behaviour exactly. One commit, two files, no migration, no
recorded row, no lab state, no method id, no counted look. Reverting cannot retroactively promote
anything: nothing is promoted without a human running `lab promote`, and this clause only ever
refuses one. The nineteen simply go back to being refused by whichever clause spoke before.
