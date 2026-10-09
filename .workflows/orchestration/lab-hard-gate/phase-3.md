# Phase 3: Make the gate visible before it bites

**Plan set:** `LAB_HARD_GATE_PLAN.md`
**Analysis:** `docs/analyzer/20261009-161956-K3QD_code_analyzer.md`
**Satisfies:** R7 (`lab status` shows the fold record beside the dev-eligible list), R8 (the explore skill says the gate **refuses**), R9 (`sera-the-explorer` says the same, in the promotion path and the Never table)
**Depends on:** Phase 1 (`lab/hardgate.py` exists and `commands/lab.py:_promote` calls it), Phase 2 (`lab/prereg.py` carries `folds` and `family_state`)
**Difficulty:** NORMAL
**Package:** `engine/commands` (plus `.claude/skills/*`, `engine/package_readme.md`, `docs/plans/`)

---

## Goal

After this phase a reader can answer "why can nothing be promoted?" from `lab status` alone: every
dev-eligible method prints either as taken by `lab promote` with its fold record and kin state on
the line, or under a separate **Refused by the hard gate** block with the gate's own sentence
underneath it. No dev-eligible method is listed as promotable when `lab promote` would exit 2 on
it. And the two skills a Sera child actually reads say the gate **refuses** rather than advises,
name both conditions, state that there is no override, and count the buy signal's conditions
correctly at four instead of three.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** none.

**Renames:** none.

**Creates:**
- `commands.lab._hard_gate_states` (`engine/src/seer_engine/commands/lab.py`, new, inserted
  immediately above `_empty_reason` at `:804`)
- a new `### lab: the hard gate (lab-hard-gate phases 1-2)` section in `engine/package_readme.md`,
  inserted between the `### lab: pre-registration` section and `### lab: the N policy for the luck
  gate` (`:2577`)
- six new tests in `engine/tests/test_lab_status.py`, appended, plus four fixture helpers
  (`_month_ends`, `_curve`, `_method_at`, `_lab_with_a_benchmark`). None of these names exists in
  that module today, and none shadows `_trial` or `_method`, which are left byte-identical

**Signature changes:**
- `commands.lab._empty_reason(conn, status)` -> `_empty_reason(conn, status, gates=None)`
  (`:804`). The new parameter is optional and defaults to computing the states itself, so no
  caller is obliged to change.
- `commands.lab._promotable_now(conn)` -> `_promotable_now(conn, gates=None)` (`:834`), same
  shape, same reason.

Both are module-private with exactly one caller each (`_promotion_path`, `:892` and `:902` — grep
confirms no other). No test calls either one directly; `test_lab_status.py` reaches them only
through the CLI.

**Requires (from earlier phases) — the exact surface this phase calls:**

1. **Phase 1 exports `hardgate.summary(conn, method_id, geo=None) -> str`** — confirmed against
   phase 1's Interface Contract. Its exact shape is **`"<fold record>; kin <state>"`**, e.g.
   `"4 of 4 folds; kin clean"` or `"2 of 4 folds; kin blocked: M0021, M0029 read test-failed"`.
   The first half is `walkforward.Record.summary()` verbatim, which is what this phase's
   `"of 4 folds"` assertion reads; **the second half is already the kin state**, which is why
   Step 3 prints `record` on its own and does **not** append `", kin clean"` — doing so would
   print the kin twice. It takes an optional `geo` so `lab status` cuts the folds once.
2. **Phase 1 must export `hardgate.check(conn, method_id) -> None`**, raising `store.LabError`
   when the gate refuses and returning `None` when it would take the method. The refusal message
   must name the fold record when (F) fails and the kin's method id when (K) fails — this is
   already the plan's exit criteria for phase 1, and two tests here assert the id appears.
3. **A lab with no `REF-SPY-HOLD` dev trial must refuse with a message naming `REF-SPY-HOLD`**
   (plan Decision D7). Every fixture in `test_lab_status.py` is such a lab, so this is the path
   `lab status` takes in eleven of the module's twelve existing tests, and one new test asserts
   the name appears.
4. **Both functions raise only `store.LabError`, never a bare `ValueError` — confirmed, so the
   narrow catch stands.** This phase catches `store.LabError` and turns it into a printed
   sentence. `walkforward.evaluate` does raise `ValueError` from `min()` on an empty curve
   sequence, but phase 1's `_dev_curves` filters every row whose `curve_json` parses to `[]`
   before `evaluate` sees it and raises a `store.LabError` sentence when nothing is left; and
   `hardgate.summary` is lenient by construction, catching `store.LabError` itself and returning
   the reason as text. Reconciliation verified both in phase 1's module code. **The `except
   Exception` fallback this section offered is not taken.**
5. **Neither function may write.** `lab status` is read-only and must stay so.
6. **Settled: phase 1's `check` is silent for every status but `dev-eligible`**, `promoted`
   included — verified in phase 1's module code and pinned by its
   `test_the_gate_is_silent_for_every_status_but_dev_eligible`. So a re-run of `lab promote` on an
   already-promoted method is **not** refused by the gate, and this phase's
   `(already pre-registered)` line is literally and exactly true. This phase also does not re-judge
   a promoted method (Decision D3 — the pre-registration is a promise), so the two agree. Nothing
   to fix.
7. **Phase 2 names its two new `Prereg` fields `folds` and `family_state`** — confirmed against
   phase 2's Interface Contract, which also states it will not rename them. This phase documents
   them in `package_readme.md` by those names.
8. **Line numbers in this plan are read at `origin/main` `7708350`, before phases 1 and 2 land.**
   Phases 1 and 2 both edit `commands/lab.py` above and below this phase's regions, so every
   number here has moved by the time this phase runs. **Anchor on the function names**, which
   neither earlier phase renames: `_empty_reason`, `_promotable_now`, `_promotion_path`,
   `_PROMOTION_STATUSES`, and `_no_dev_eligible_reason` for the insertion point. The regions are
   disjoint from phase 1's (`_promote`, `_regime`, `_walkforward`, the module help block) and from
   phase 2's (two prints inside `_promote`), which is why `1 -> 2 -> 3` is sequential rather than
   concurrent.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/hardgate.py` (Phase 1) — called, never edited
- `engine/src/seer_engine/lab/prereg.py` (Phase 2) — documented, never edited
- `commands/lab.py` `_promote` (`:1148`), `_regime` (`:1700`), `_walkforward` (`:1787`) and the
  module help block (`:16-18`) — Phases 1 and 2. `_trial_deposits` (`:1656`) is **deleted by phase
  1**, which moves its body to `hardgate.trial_deposits`; this phase must not reintroduce a
  reference to it
- `engine/src/seer_engine/lab/runner.py` — **Phase 2** owns the `lab test` kin note (Decision D3);
  this phase adds nothing to `lab test`
- `docs/lab/prereg/README.md` — **Phase 2**
- `engine/tests/test_lab_test_window.py` — Phase 2
- `engine/src/seer_engine/lab/walkforward.py`, `engine/src/seer_engine/backtest/walkforward.py`
- `engine/tests/test_lab_prereg.py`, `engine/tests/test_lab_walkforward.py`,
  `engine/tests/test_lab_hardgate.py`
- every existing test in `engine/tests/test_lab_status.py` — additions only
- `lab/lab.sqlite`, `web/data/lab.json`, `docs/lab/prereg/*.md`

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/commands/lab.py` | modify | new `_hard_gate_states` above `:804`; `_empty_reason` (`:804`) gains the `promoted`-section reason and a `gates` parameter; `_promotable_now` (`:834`) splits its listing into taken / refused; `_PROMOTION_STATUSES` (`:614`) Dev-eligible `why` string; `_promotion_path` (`:882`) computes the states once |
| `engine/tests/test_lab_status.py` | modify (additions only) | four fixture helpers and six tests appended after `:301`, before the committed-database section at `:304`, plus two import lines |
| `.claude/skills/explore-and-experiment-new-method/SKILL.md` | modify | step 0b's `lab walkforward` bullet (`:207-208`) and the buy-signal block (`:210-226`) |
| `.claude/skills/sera-the-explorer/SKILL.md` | modify | the dev-eligible promotion bullet (`:83-90`), the synthesis buy-signal bullet (`:107-114`), three new Never rows after `:140` |
| `engine/package_readme.md` | modify | two new lab package-map lines after `:148`; the `prereg.py` map line (`:145`); the `Prereg` field list (`:2514-2520`); a new hard-gate API section before `:2578` |
| `docs/plans/WALK_FORWARD_EVALUATION_PLAN.md` | modify | status line (`:6`); phase 4 marked done (`:194-197`); the stale cost paragraph replaced (`:217-227`); a new "How the four open questions were answered" section after `:259` carrying D6 |

Six files. No file is created, no file is deleted. **Every line number above is read at
`origin/main` `7708350`**; phases 1 and 2 shift them in `commands/lab.py`. Anchor on the function
and section names, which neither earlier phase renames.

---

## Implementation Steps

### Step 1: `_hard_gate_states` — run the gate once per `lab status`, and never let it raise

**File:** `engine/src/seer_engine/commands/lab.py`, inserted as a new function immediately **above**
`_empty_reason` at `:804` (after `_no_dev_eligible_reason` ends at `:802`).

**Change:** one new module-private function. It is the only place in this phase that imports
`hardgate`, and the only place that catches `store.LabError`.

The two design decisions it encodes, both of which a reviewer will otherwise query:

- **Only `dev-eligible` methods are asked.** A `promoted` method is not re-judged. That is plan
  Decision D3 showing through — the pre-registration is a promise, `lab test` honours it as
  written, and a status block that re-opened it would announce a refusal the lab has already
  decided not to make.
- **It never raises.** Eleven of the twelve existing tests in `test_lab_status.py` build a lab with
  no `REF-SPY-HOLD` dev trial and `curve_json="[]"`. The gate refuses such a lab, correctly — the
  folds are cut from the benchmark curve — and that refusal is a sentence to print, not a reason
  for `lab status` to stop printing.

**Code:**

```python
def _hard_gate_states(conn) -> dict[str, tuple[str, str | None]]:
    """The hard gate's answer for every ``dev-eligible`` method, run once per ``lab status``.

    ``{method_id: (the gate's one-line summary, why `lab promote` would refuse)}``. The first
    element is ``hardgate.summary`` verbatim -- the fold record **and** the kin state, in the shape
    ``"4 of 4 folds; kin clean"`` -- so a caller prints it whole and never re-states the kin. The
    second is ``None`` when the gate would take the method, and otherwise the refusal's own
    sentence collapsed to one line, so it drops straight into an indented status line however the
    gate chose to wrap it.

    The fold geometry is cut **once** here and passed to every ``summary`` (``hardgate.geometry``),
    which is what phase 1's handoff asks for: the folds come from the benchmark curve, not from the
    method, so re-cutting them per method is the same arithmetic seven times over. A lab with no
    benchmark has no geometry, and ``geo`` stays ``None`` -- ``summary`` then says so, per method,
    in its own words.

    **Only ``dev-eligible`` methods are asked.** A ``promoted`` method is not re-judged here, and
    that is Decision D3 showing through rather than an oversight: the pre-registration is a
    promise, ``lab test`` honours it as written, and a status block that re-opened it would be
    announcing a refusal the lab has already decided not to make. A promoted method whose kin
    failed *after* the promise is ``lab test``'s note to print, not this one's.

    **It never raises.** ``lab status`` runs on every lab there is, including one with no
    ``REF-SPY-HOLD`` dev trial and one whose recorded curves are empty -- the shape every fixture
    in ``test_lab_status.py`` builds, and the shape a lab has on its first day. The gate refuses
    such a lab and is right to, because the folds are cut from the benchmark curve; but that
    refusal is information to print, not a reason for ``lab status`` to stop printing. So every
    ``store.LabError`` is caught and becomes the sentence.

    Cost: at most one ``summary`` and one ``check`` per dev-eligible method -- seven on the
    committed database. Neither opens a research store, runs a backtest or writes anything.
    """
    from seer_engine.lab import hardgate

    def one_line(text: object) -> str:
        return " ".join(str(text).split())

    try:
        geo = hardgate.geometry(conn)
    except store.LabError:
        geo = None  # `summary` is lenient and says why, per method, in its own words

    states: dict[str, tuple[str, str | None]] = {}
    for m in conn.execute(
        "SELECT id FROM methods WHERE status = 'dev-eligible' ORDER BY id"
    ).fetchall():
        mid = str(m["id"])
        record = one_line(hardgate.summary(conn, mid, geo))
        try:
            hardgate.check(conn, mid)
        except store.LabError as e:
            states[mid] = (record, one_line(e))
        else:
            states[mid] = (record, None)
    return states
```

**`summary` never raises** -- phase 1's contract, and the reason there is no `try` around it here.
It catches `store.LabError` itself and returns the reason as text, which is exactly what a lab with
no `REF-SPY-HOLD` row needs: `"not scoreable (no REF-SPY-HOLD dev trial ...); kin clean"`. `check`
is the strict one, and its refusal is what the second element carries.

**Impact:** nothing yet — no caller. Step 4 wires it in. The lazy `from seer_engine.lab import
hardgate` follows the file's own idiom for lab submodules used by one handler (`_walkforward` at
`:1795`, `_trial_deposits` at `:1667`), and keeps a circular-import risk at zero if phase 1's
module ever grows an import of `commands`.

### Step 2: `_empty_reason` — stop telling the reader to run a command that will exit 2

**File:** `engine/src/seer_engine/commands/lab.py:804`

**Change:** full replacement of the function. The `promoted` section's sentence today reads
*"4 methods are dev-eligible; `lab promote` has not been run on them yet"*. On the committed lab
that is now a lie in the way that matters: `lab promote` **has** nothing to do, because it would
refuse all seven. The sentence sends the reader to a command that only exits 2.

**Code:**

```python
def _empty_reason(
    conn, status: str, gates: dict[str, tuple[str, str | None]] | None = None
) -> str:
    """Why one promotion-path section is empty.

    Every step but the first is empty for exactly one reason worth printing -- the step before it
    -- and naming the command that would move it is the whole value of the sentence. The first
    step, ``dev-eligible``, is empty because of the gate, and that is the sentence this block
    exists for.

    **The ``promoted`` section has a second reason since 2026-10-09.** "N methods are
    dev-eligible; `lab promote` has not been run on them yet" is false in the way that costs
    somebody an hour when ``lab promote`` would exit 2 on every one of them: it names a command as
    waiting to be run when running it does nothing. So when the hard gate refuses some or all of
    the dev-eligible methods, this says that instead and points at the block above that carries
    each one's fold record and kin.

    ``gates`` is ``_hard_gate_states``'s answer, passed in by ``_promotion_path`` so the gate runs
    once per ``lab status`` rather than once per section; ``None`` means compute it here.
    """
    if status == "dev-eligible":
        return _no_dev_eligible_reason(conn)
    prior = {
        "promoted": "dev-eligible",
        "test-passed": "promoted",
        "test-failed": "promoted",
        "paper": "test-passed",
    }[status]
    cmd = {
        "promoted": "lab promote",
        "test-passed": "lab test",
        "test-failed": "lab test",
        "paper": "python -m seer_engine promote",
    }[status]
    n = int(conn.execute("SELECT count(*) FROM methods WHERE status = ?", (prior,)).fetchone()[0])
    if n == 0:
        return f"nothing is {prior}, so `{cmd}` has nothing to take"
    noun = "1 method is" if n == 1 else f"{n} methods are"
    it = "it" if n == 1 else "them"
    if status == "promoted":
        if gates is None:
            gates = _hard_gate_states(conn)
        refused = sum(1 for _record, why in gates.values() if why is not None)
        if refused >= n:
            return (
                f"{noun} dev-eligible, and the hard gate refuses every one of {it} -- "
                f"`lab promote` would exit 2, not pre-register. Read \"Refused by the hard gate\" "
                f"above for each one's fold record and kin; there is no override, and the only "
                f"way through is a method the folds and its kin have not already judged"
            )
        if refused:
            return (
                f"{noun} dev-eligible, {refused} of which the hard gate refuses (see \"Refused by "
                f"the hard gate\" above); `lab promote` has not been run on the rest yet"
            )
    return f"{noun} {prior}; `{cmd}` has not been run on {it} yet"
```

**Impact:** `refused >= n` rather than `== n` because `gates` is keyed on every `dev-eligible`
method and `n` counts the same set, so they are equal by construction — the `>=` is a guard
against a future where they are not, not a real case. A dev-eligible method with no dev trial at
all makes `hardgate.summary` raise, which counts as refused, which is honest.

### Step 3: `_promotable_now` — never list a method `lab promote` would refuse

**File:** `engine/src/seer_engine/commands/lab.py:834`

**Change:** full replacement. The header `Promotable now (`lab promote` would take these)` becomes
a lie the moment the hard gate exists, so the list it heads is split: taken, with the fold record
and kin state on the same line (R7); or refused, under its own header with the gate's sentence
underneath. The `held by the status machine` block is unchanged.

**The existing tests survive this, deliberately and checkably.**
`test_promotable_now_lists_what_lab_promote_would_take` (`:189`) asserts `"M0001-A" in
out.split("Promotable now")[1]`. M0001 moves from the taken list to the refused list — which is
printed **after** the `Promotable now` header and therefore still inside that split. The new
header is `Refused by the hard gate`, chosen so it does not collide with the
`Dev-eligible (1)` status section a new test splits on.

**Code:**

```python
def _promotable_now(
    conn, gates: dict[str, tuple[str, str | None]] | None = None
) -> list[str]:
    """What ``lab promote`` would take today, and what is holding the rest back.

    ``prereg.promote_method`` wants two things: a method at ``dev-eligible`` (or already
    ``promoted``), and a best dev trial the verdict calls eligible. ``store.best_dev_eligible``
    answers the second under ``store.DSR_POLICY`` (phase 4), so this section says what the gate
    says and cannot drift from it -- which is the point of reading the derived verdict here
    rather than the recorded ``eligible`` column, which was frozen at a 0.95 bar and an N of
    whatever day the trial ran.

    A method whose best trial *is* derived-eligible but whose status still reads ``rejected`` is
    listed separately and by name: it is not promotable now, and the one command that moves it is
    ``lab reevaluate <id>`` (phase 4), which takes the ``rejected -> dev-eligible`` edge. **Not
    ``lab run``** -- that refuses a method whose variants already have dev trials, so telling the
    reader to run it would send them into a refusal.

    Only methods that have a dev trial are asked, so the derivation runs 23 times on the
    committed database rather than 37.

    **Since 2026-10-09 the dev gate is not the last word, and this section says so.**
    ``lab promote`` also refuses a method that lost a majority of its walk-forward folds, or whose
    kin has already failed the test window (``lab/hardgate.py``). Listing such a method under
    "Promotable now (`lab promote` would take these)" would be a lie about exactly the methods
    this section exists to explain. So each dev-eligible method appears in one of two places and
    never both: **taken**, with its fold record and its kin state on the same line; or **refused**,
    with the gate's own sentence on the line beneath it. That is the whole of R7 -- "why can
    nothing be promoted" becomes answerable from ``lab status`` alone, with no second command and
    no reading of the source.
    """
    if gates is None:
        gates = _hard_gate_states(conn)
    ready: list[str] = []
    refused: list[str] = []
    held: list[str] = []
    for m in conn.execute(
        "SELECT * FROM methods m WHERE EXISTS "
        "(SELECT 1 FROM trials t WHERE t.method_id = m.id AND t.window = 'dev') ORDER BY m.id"
    ).fetchall():
        best = store.best_dev_eligible(conn, m["id"])
        if best is None:
            continue
        if m["status"] in ("dev-eligible", "promoted"):
            v = store.verdict(conn, best)
            head = (
                f"    {m['id']:<6} {best['candidate_id']:<28} MAR {fmt_num(best['mar'])}  "
                f"DSR {fmt_num(v.dsr, 3)} at N={v.n} ({v.policy})"
            )
            if m["status"] == "promoted":
                # Already pre-registered: the promise is written and is not re-opened (D3).
                ready.append(f"{head}  (already pre-registered)")
                continue
            record, why = gates.get(m["id"], ("hard gate not evaluated", None))
            if why is None:
                # `record` is `hardgate.summary` whole -- "4 of 4 folds; kin clean" -- so the kin
                # state is already in it. Appending ", kin clean" here would print it twice.
                ready.append(f"{head}  {record}")
            else:
                detail = why if record == why else f"{record}; {why}"
                refused.append(head)
                refused.append(f"           {detail}")
        else:
            held.append(
                f"    {m['id']:<6} {best['candidate_id']:<28} status {m['status']!r}: "
                f"`lab reevaluate {m['id']}` re-judges it and moves it to dev-eligible"
            )
    out = ["  Promotable now (`lab promote` would take these):"]
    out += ready or ["    (none)"]
    if refused:
        out.append(
            "  Refused by the hard gate (dev-eligible, but `lab promote` exits 2 on these -- it "
            "wants a majority of walk-forward folds and no kin that has test-failed; there is no "
            "override):"
        )
        out += refused
    if held:
        out.append("  Eligible on the evidence, held by the status machine:")
        out += held
    return out
```

**Impact:** the continuation line's 11-space indent (`4 + 6 + 1`) aligns the reason under the
candidate-id column. On the committed lab this block grows from 7 lines to 1 + 14 = 15; that is
the R7 content and the reason the phase exists.

**Reconciled against phase 1's `summary`.** The taken branch prints `record` whole and adds
nothing: `hardgate.summary` returns `"<fold record>; kin <state>"`, so the earlier draft's
`f"{head}  {record}, kin clean"` would have rendered
`4 of 4 folds; kin clean, kin clean`. The test below still asserts both `"of 4 folds"` and
`"kin clean"` appear, and both do -- once each.

### Step 4: `_promotion_path` — compute the gate once, and stop the Dev-eligible header promising a promotion

**File:** `engine/src/seer_engine/commands/lab.py:882` (the function) and `:614` (the tuple)

**Change (a):** `_PROMOTION_STATUSES`'s first row says `` "`lab promote` pre-registers these" ``.
It does not, for a method the gate refuses. Replace that one string.

**Code (a)** — full replacement of the tuple at `:613-619`:

```python
_PROMOTION_STATUSES: tuple[tuple[str, str, str], ...] = (
    ("Dev-eligible", "dev-eligible", "the hard gate decides which of these `lab promote` takes"),
    ("Promoted (pre-registered)", "promoted", "`lab test` spends the one look on these"),
    ("Test-passed", "test-passed", "the owner's call: a paper roster entry with its own clock"),
    ("Test-failed", "test-failed", "final; there is no second look at the configuration"),
    ("Paper", "paper", "trading on the paper roster"),
)
```

**Change (b):** `_promotion_path` runs the gate once and hands the answer to both callers.

**Code (b)** — full replacement of `_promotion_path` at `:882-906`:

```python
def _promotion_path(conn) -> list[str]:
    """The whole promotion-path block: always printed, empty sections included.

    The hard gate runs **once** here, not once per section: ``_promotable_now`` needs it to decide
    what to list, and ``_empty_reason`` needs it to say why the Promoted section is empty, and
    both would otherwise re-derive the same seven answers.
    """
    policy = store.DSR_POLICY
    n = _live_n(conn, policy)
    at = f" at N = {n}" if n is not None else ""
    out = [
        f"Promotion path (dev-eligible -> promoted -> test-passed -> paper), luck bar "
        f"DSR >= {store.DSR_MIN} under policy {policy}{at}:"
    ]
    gates = _hard_gate_states(conn)
    out += _ratchet_warning(conn, _dev_var(conn))
    out += _promotable_now(conn, gates)
    for title, status, why in _PROMOTION_STATUSES:
        rows = conn.execute(
            "SELECT * FROM methods WHERE status = ? ORDER BY id", (status,)
        ).fetchall()
        if rows:
            out.append(f"  {title} ({len(rows)}) -- {why}:")
            for m in rows:
                out.append(f"    {m['id']} {m['name']} ({m['family']}, {m['source_kind']})")
        else:
            out.append(f"  {title}: (none) -- {_empty_reason(conn, status, gates)}")
    out.append(
        f"  Test-window looks used: {store.test_looks(conn)}. One look per configuration, "
        f"pre-registered before it is spent, and never given back (design §3)."
    )
    return out
```

**Impact:** R7 is complete at the end of this step. `lab status` on the committed lab now prints
seven methods under **Refused by the hard gate**, each with its fold record and the kin that
blocks it.

### Step 5: `test_lab_status.py` — six tests, appended, nothing edited

**File:** `engine/tests/test_lab_status.py`, inserted **after** `:301` (the end of
`test_sinks_at_finds_the_first_n_below_the_bar`) and **before** the
`# ---- the committed database` comment at `:304`.

**Change:** four fixture helpers (`_month_ends`, `_curve`, `_method_at`, `_lab_with_a_benchmark`)
and six tests. Every existing line in the file is left byte-identical, including `_trial`,
`_method` and the autouse policy fixture; the file is 317 lines today, so everything appended here
lands between the old `:301` and the old `:304`.

Two of the six run against a lab that has a real `REF-SPY-HOLD` benchmark and real monthly curves,
which this module has never built before. The geometry is pinned deliberately: the benchmark curve
spans **1993-02 .. 2015-09**, because `walkforward.folds` cuts the geometry from the *benchmark*
and a curve starting in 1996 yields only **three** folds (the 2015 tail is 9 months, below
`MIN_EVAL_MONTHS = 12`) — which would then be refused on `MIN_FOLDS` and prove nothing about the
fold record. Starting at 1993-02 gives exactly four 36-month evaluation slices, which is the
committed lab's own geometry.

`n_trials_at_run` is set to each fixture lab's own dev row count, for the reason the module's
comment at `:79-83` already gives: `store.verdict` re-evaluates a recorded DSR at the gate's
current N, and the re-evaluation is the identity only while the two agree.

**Code:**

```python
# ------------------------------------------------------------------ the hard gate in `lab status`
#
# R7 (lab-hard-gate phase 3): a dev-eligible method `lab promote` would refuse must not be listed
# as promotable, and the reason must be on the screen. Six tests, nothing above this line edited.
#
# Two of them need a real fold geometry, so they build a `REF-SPY-HOLD` dev trial with a monthly
# curve. The span is 1993-02..2015-09 and not the dev window's 1996-01, because `walkforward.folds`
# cuts the geometry from the *benchmark*: from 1996 the last slice is 9 months, below
# `MIN_EVAL_MONTHS`, and only three folds survive -- which the gate then refuses on MIN_FOLDS, for
# a reason that has nothing to do with what the test is about. From 1993-02 there are exactly four
# 36-month slices, which is the committed lab's own geometry.


def _month_ends(first: date, last: date) -> list[date]:
    """Every month end in ``[first, last]``, the shape a recorded `trials.curve_json` has."""
    out: list[date] = []
    y, m = first.year, first.month
    while True:
        nxt = date(y + (m // 12), (m % 12) + 1, 1)
        end = nxt - timedelta(days=1)
        if end > last:
            return out
        if end >= first:
            out.append(end)
        y, m = nxt.year, nxt.month


def _curve(days: list[date], monthly: float) -> str:
    """A monotone curve compounding at ``monthly``, as `trials.curve_json` stores it.

    Monotone on purpose: `walkforward.measure` gives a slice that never fell an infinite MAR, so
    `pick` ranks it rather than dropping it, and `FoldPick.beat` compares total return, so the
    faster curve wins every fold deterministically. No randomness, no tuning.
    """
    value, points = 1.0, []
    for d in days:
        points.append([d.isoformat(), round(value, 8)])
        value *= 1.0 + monthly
    return json.dumps(points)


def _method_at(c, mid: str, *, status: str, family: str = "fam", trials=()) -> None:
    """Like ``_method``, but reaching the statuses the hard gate cares about.

    ``_method`` above stops at ``dev-eligible``; the gate's (K) condition needs a kin that reads
    ``test-failed``, which is three transitions further along. A separate helper rather than an
    edit to ``_method``, because every test above depends on that one exactly as it is.
    """
    path = {
        "registered": ("registered",),
        "rejected": ("registered", "rejected"),
        "dev-eligible": ("registered", "dev-eligible"),
        "promoted": ("registered", "dev-eligible", "promoted"),
        "test-failed": ("registered", "dev-eligible", "promoted", "test-failed"),
    }[status]
    with c:
        store.add_method(c, id=mid, name=f"name {mid}", family=family,
                         source_kind="knowledge", hypothesis="h")
        if trials:
            store.insert_trials(c, list(trials))
        for s in path:
            store.update_method(c, mid, status=s)


def _lab_with_a_benchmark(c, *, method_monthly: float, kin_failed: bool = False) -> None:
    """A lab the walk-forward can actually score: a benchmark, and one dev-eligible method.

    ``method_monthly`` above the benchmark's 0.004 wins every fold; below it loses every fold.
    ``kin_failed`` adds a sibling in the same family that reads ``test-failed``, which is the
    gate's (K) condition and nothing else.
    """
    days = _month_ends(date(1993, 2, 1), date(2015, 9, 30))
    n = 3 if kin_failed else 2
    _method_at(c, "M0001", status="dev-eligible", family="fam", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a", mar=0.9,
               start="1993-02-28", end="2015-09-30", n_trials_at_run=n,
               curve_json=_curve(days, method_monthly)),
    ])
    _method_at(c, "M0009", status="rejected", family="bench", trials=[
        _trial(method_id="M0009", candidate_id="REF-SPY-HOLD", config_digest="spy",
               start="1993-02-28", end="2015-09-30", n_trials_at_run=n, eligible=False,
               failed=OLD_LUCK_LABEL, dsr=0.10, curve_json=_curve(days, 0.004)),
    ])
    if kin_failed:
        _method_at(c, "M0002", status="test-failed", family="fam", trials=[
            _trial(method_id="M0002", candidate_id="M0002-A", config_digest="b", mar=0.6,
                   start="1993-02-28", end="2015-09-30", n_trials_at_run=n,
                   curve_json=_curve(days, 0.006)),
        ])


def test_a_method_that_clears_the_hard_gate_is_listed_with_its_fold_record(tmp_path, status):
    """R7's positive half: taken, and the line says on what evidence."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _lab_with_a_benchmark(c, method_monthly=0.009)
    c.close()
    out = status(db)
    ready = out.split("Promotable now")[1].split("\n  Dev-eligible")[0]
    assert "M0001" in ready
    assert "of 4 folds" in ready          # `walkforward.Record.summary()`, printed verbatim
    assert "kin clean" in ready
    assert "Refused by the hard gate" not in out


def test_a_method_that_loses_its_folds_is_refused_and_the_record_says_so(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _lab_with_a_benchmark(c, method_monthly=0.001)   # below the benchmark's 0.004, every fold
    c.close()
    out = status(db)
    ready = out.split("Promotable now")[1].split("Refused by the hard gate")[0]
    assert "(none)" in ready and "M0001 " not in ready
    blocked = out.split("Refused by the hard gate")[1].split("\n  Dev-eligible")[0]
    assert "M0001" in blocked
    assert "of 4 folds" in blocked


def test_a_method_whose_kin_test_failed_is_refused_and_the_kin_is_named(tmp_path, status):
    """(K): the folds are won 4 of 4, so the only thing left to refuse on is the sibling."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _lab_with_a_benchmark(c, method_monthly=0.009, kin_failed=True)
    c.close()
    out = status(db)
    blocked = out.split("Refused by the hard gate")[1].split("\n  Dev-eligible")[0]
    assert "M0001" in blocked
    assert "M0002" in blocked      # the kin, named, so the reader does not go looking


def test_lab_status_still_prints_when_the_gate_cannot_score_the_lab(tmp_path, status):
    """The shape every other fixture in this module has: no benchmark, empty curves.

    The gate refuses it and is right to -- the folds are cut from the benchmark curve. What must
    not happen is `lab status` exiting non-zero or printing nothing, which is what a `LabError`
    escaping `_hard_gate_states` would do. The `status` fixture asserts the exit code for us.
    """
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="dev-eligible", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a", mar=0.9),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.7, mar=0.5),
    ])
    c.close()
    out = status(db)
    assert "Promotable now" in out
    blocked = out.split("Refused by the hard gate")[1].split("\n  Dev-eligible")[0]
    assert "M0001" in blocked
    assert "REF-SPY-HOLD" in blocked    # the lab's fixture is wrong, not the method (D7)


def test_the_empty_promoted_section_blames_the_gate_not_an_unrun_command(tmp_path, status):
    """"`lab promote` has not been run on them yet" is false when it would exit 2 on all of them."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _lab_with_a_benchmark(c, method_monthly=0.001)
    c.close()
    out = status(db)
    promoted = out.split("Promoted (pre-registered): (none)")[1].split("\n")[0]
    assert "hard gate refuses" in promoted
    assert "has not been run on" not in promoted
    assert "no override" in promoted


def test_the_dev_eligible_header_no_longer_promises_a_promotion(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _lab_with_a_benchmark(c, method_monthly=0.001)
    c.close()
    out = status(db)
    assert "`lab promote` pre-registers these" not in out
    assert "the hard gate decides which of these `lab promote` takes" in out
```

The file's import block at `:12-20` gains three names. **This is an addition to an import block,
not an edit to a test**; the existing lines are untouched:

```python
import argparse
import json
import shutil
from datetime import date, timedelta
```

(`argparse` and `shutil` are already there; `json` and the `datetime` import are new lines added
beside them, keeping the block alphabetical as it already is.)

**Impact:** `test_lab_status.py` goes from 12 tests to 18. Nothing above line 302 changes except
the two added import lines.

### Step 6: the explore skill — the gate **refuses**, and the buy signal has four conditions

**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md`

**Change (a)** — replace the `lab walkforward` bullet at `:207-208`:

```markdown
   - `lab walkforward MNNNN` -- the fold record, and **the one item on this list that is not
     advice**. Since 2026-10-09 `lab promote` *refuses* (`engine/src/seer_engine/lab/hardgate.py`):
     it exits 2, writes no pre-registration and moves no status, unless **both** hold --
     - **(F) folds.** The method beat the recorded SPY benchmark in a **majority** of its
       scoreable walk-forward folds, **and** it is scoreable on every fold the geometry yields,
       at least 4 of them. Fewer than 4 is refused as thin evidence, not waved through: a strict
       majority of an *odd* fold count is a coin flip at every odd count (n=3 is 0.5000, n=4 is
       0.3125), so "3 or more" would admit evidence weaker than 4 and no stronger than 1.
     - **(K) kin.** **No kin reads `test-failed`** -- kin being the method's `family` *and* its
       transitive ancestors through `parent_id`. A parent that failed out of sample disproves a
       method as surely as a sibling that failed; M0032 is M0007's realistic twin by `parent_id`
       and not by family string.

     **There is no override.** No `--force`, no environment variable, no "promote anyway". If the
     rule proves too strict the answer is an argued commit that changes it, because an override
     path is precisely the mechanism that produced the 0-for-5 roster. Do not look for one, do
     not work around it, and do not treat a refusal as a bug.

     **Read `lab status` before you plan a promotion**, not after the refusal. It prints each
     dev-eligible method's fold record and, under "Refused by the hard gate", the exact reason --
     so you can see a dead end before you spend a cycle walking into it.

     **`lab test` does not re-check (K).** A pre-registration is a promise and is not re-opened:
     if the family fails *after* the promotion but before the look, `lab test` prints a note and
     spends the look anyway. The moment kin matters is before `lab promote`, never after it.
```

**Change (b)** — replace the buy-signal header and quote block at `:210-214`. The conditions are
**four**, not three: the family condition was added in walk-forward phase 3 and is already in
`walkforward.buy_signal`, in this order.

```markdown
   **THE BUY SIGNAL — say it loudly, do not sit on it.** The moment a method clears all four of:

   > **(a)** dev-eligible at the bars in force, **(b)** no method in its family has test-failed,
   > **(c)** a majority of walk-forward folds beaten, and **(d)** a *positive* edge in the
   > highest-coverage era (2009-2015), so the edge is not an artefact of the missing half
```

**Change (c)** — in the paragraph at `:223-224`, replace `name which of (a)(b)(c) it cleared with
the numbers` with `name which of (a)(b)(c)(d) it cleared with the numbers`.

**Change (d)** — append one paragraph after that same block. This is **index Decision D9's one
visible statement**, and it is the whole of this phase's obligation on that decision: the
asymmetry is real, it is deliberately left in the code, and step 0b is the one place a reader hits
it.

```markdown
   **The buy signal's (b) and the hard gate's (K) are not the same test, and that is deliberate.**
   The buy signal checks the `family` string only (`lab/walkforward.py`'s `BUY_CONDITIONS`, and
   `lab walkforward`'s own query); the gate also walks `parent_id`. A method can therefore read
   clean in `lab walkforward` and still be refused by `lab promote` — M0030's family is clean while
   its parent M0029 and grandparent M0021 both read `test-failed`. The gate is the stricter of the
   two and it is the one that decides whether a look is spent. The buy signal is a separate,
   owner-decided rule about when to **buy data**, not about when to promote, so it was left as it
   is rather than quietly widened.
```

**This phase must not edit `engine/src/seer_engine/lab/walkforward.py` or
`commands/lab.py:_walkforward` to say this.** `lab/walkforward.py` is on the plan's do-not-edit
list and is phase 1's read-only dependency; `_walkforward` is phase 1's region. Changing either
would change `lab walkforward`'s printed buy signal, which no requirement in this plan set asks
for. The statement goes in the skill, in prose, and nowhere else.

**Impact:** R8 is satisfied at the end of this step. A child reading step 0b now learns the
refusal, both conditions, the absence of an override, and where to look first.

### Step 7: the Sera skill — the promotion path, the buy signal's count, and three Never rows

**File:** `.claude/skills/sera-the-explorer/SKILL.md`

**Change (a)** — replace the dev-eligible bullet at `:83-90`:

```markdown
   - **dev-eligible:** run the explore skill's **Promotion** yourself, now, in `$REPO`, one at a time.
     Start with its step 0, the fit check, then **step 0b, the durability check** -- `lab regime`,
     `survivorship_coverage.py`, and `lab walkforward`. Four of four test looks have failed on
     `beats SPY TR`; a good twenty-year average is not evidence any more.
     **`lab promote` now refuses, it does not warn.** Since 2026-10-09 it exits 2 unless the method
     beat SPY in a majority of at least four scoreable walk-forward folds **and** no kin reads
     `test-failed` -- kin being its `family` plus every ancestor through `parent_id`. **There is no
     override and no flag.** When it refuses: record it (`lab note`, and a `risk` insight if the
     whole family is now closed), put the reason in the batch report, and move to the next idea.
     You do not ask the owner, you do not pause the batch, and you do not go looking for a way
     round -- the iron rules hold here exactly as everywhere else. `lab status` shows every
     dev-eligible method's fold record and, under "Refused by the hard gate", the reason, so check
     it *before* you plan a promotion.
     Step 0b also carries the buy signal, which you report and never block on. If the eligible
     variant trades whole shares, or is a method from M0030 or earlier measured at the flat 0.1%,
     first run `lab costs` on it and then its fractional, real-fee twin as a one-variant variation
     method. Promote the twin, never the original. The look is spent on the configuration paper
     would trade, or not at all.
```

**Change (b)** — replace the synthesis buy-signal bullet at `:107-114`:

```markdown
   - **the buy signal, every batch, even when the answer is no.** State plainly whether any
     method this batch cleared all four of: dev-eligible at the bars in force; no method in its
     family has test-failed; a majority of walk-forward folds beaten (`lab walkforward`); and a
     *positive* edge in the highest-coverage era 2009-2015
     (`engine/scripts/survivorship_coverage.py`). That conjunction is the only moment
     survivorship-free price history is worth buying -- see the explore skill's Promotion step 0b
     for why, and what it costs. If nothing cleared it, say "no buy signal this batch" and why. If
     something did, it is the FIRST line of the report, not a footnote, and it also goes in as a
     `lab insight --kind risk`. Say too whether the hard gate refused anything this batch, and on
     which of the two conditions -- a batch where every promotion was refused is a finding about
     the lab, and the owner should read it in the synthesis rather than infer it from silence.
```

**Change (c)** — append three rows to the Never table, after `:140`:

```markdown
| "`lab promote` refused it, I'll find a way round" | There is no way round. No `--force`, no environment variable, no editing the method to dodge the kin walk. Record the refusal, report it, take the next idea. |
| "Its fold record is 2 of 4 but the twenty-year numbers are great" | That is the gate's entire point, and the 0-for-5 roster is what the twenty-year numbers bought. `lab promote` exits 2. |
| "Its sibling test-failed, but this variant is genuinely different" | Kin is `family` plus every ancestor through `parent_id`. A disproven family does not get a retry under a new id — that is the mechanism the gate exists to close. |
```

**Impact:** R9 is satisfied. The three rows are three distinct temptations a child will actually
have, not one restated; the first is the one the brief names explicitly.

### Step 8: `engine/package_readme.md` — the package map and an API block

**File:** `engine/package_readme.md`

**Change (a)** — the lab package map. Insert two lines after `name_count.py` (`:148`), in the
chronological order the rest of the block uses. `lab/walkforward.py` is missing from the map
entirely — a gap left by the walk-forward plan's phases 1-3, and `hardgate.py`'s line is
unreadable without it:

```
      walkforward.py        the lab's own walk-forward (walk-forward-evaluation phases 1-2): MIN_TRAIN_YEARS = 10, EVAL_YEARS = 3, MIN_EVAL_MONTHS = 12, Fold, Slice, FoldPick, folds(), measure(), pick(), evaluate(), Record (scored / won / majority / stable / summary()), BUY_CONDITIONS and buy_signal(). Pure: it slices curves the lab already recorded, runs no backtest and tunes nothing. **Not `backtest/walkforward.py`**, which is P3b's anchored walk-forward for Strategy A2 on the bracket engine
      hardgate.py           the hard gate `lab promote` refuses on (lab-hard-gate phase 1): MIN_FOLDS, trial_deposits(), fold_record() -> walkforward.Record, the kin walk over `family` ∪ transitive `parent_id` ancestors, check() raising store.LabError, summary(). SQL plus arithmetic on recorded curves -- no research store, no backtest, no look
```

**Change (b)** — the `prereg.py` map line at `:145`, appending the two fields phase 2 adds:

```
      prereg.py             the docs/lab/prereg/MNNNN.md pre-registration: Prereg, render()/parse(), require_committed(), check_digest(), check_source(), promote_method() (build-promotion-path phase 3); plus `folds` and `family_state`, the hard gate's record of what the method cleared, tolerated-absent on read so the four committed files still parse (lab-hard-gate phase 2)
```

**Change (c)** — the `Prereg` bullet in the pre-registration API section (`:2514-2520`), full
replacement:

```markdown
- `Prereg`: a frozen dataclass of the file's front-matter block — `method`, `candidate`,
  `config_digest`, `rules_id`, `allocator_id`, `dev_trial`, `dev_window`, `test_window`, `gate`,
  `mar`, `dsr`, `n_trials_at_run`, `store_fingerprint`, `git_sha`, `date`, and since
  lab-hard-gate phase 2 `folds` and `family_state`. **Every field is a `str`**: the file is the
  record and this value is a reading of it, not a parallel source of truth, so
  `parse(render(p, name)) == p` exactly with no number formatting in the round trip. `FIELDS` is
  the tuple of names, taken from the dataclass.
- `folds` and `family_state` are **the hard gate's record of what this method cleared**, written
  at promotion and never recomputed afterwards. `folds` is the walk-forward record in
  `Record.summary()`'s own words (`"3 of 4 folds"`, or `"2 of 4 folds, pick changed"`);
  `family_state` is the kin's state at that moment. They are the only two fields `parse`
  tolerates as **absent**, filling them with a stated legacy value, because
  `docs/lab/prereg/{M0002,M0021,M0022,M0029}.md` were committed before the gate existed and a
  pre-registration is written once and never rewritten (Decision D5). Every file written from
  here on carries both, so a reader a year from now sees the bar *this* method cleared rather
  than today's bar.
```

**Change (d)** — a new API section inserted immediately before `### lab: the N policy for the luck
gate (lab-luck-gate phase 1)` at `:2578`:

```markdown
### lab: the hard gate (lab-hard-gate phases 1-2)

`lab/hardgate.py` is the rule `lab promote` refuses on, and the only thing in the lab that can stop
a counted test-window look being spent on a method the evidence has already judged. It opens no
research store, runs no backtest, writes nothing and spends no look: it is two SQL reads and
arithmetic on curves already in `trials.curve_json`, and it runs in under a second.

- **Why it exists.** Five out-of-sample results, five failures — M0021, M0029, M0022 and M0002 on
  `beats SPY TR`, and M0032 losing 415 million rupiah to a deposit-matched SPY. The surviving
  dev-eligible ideas are all cousins of the methods that produced those failures. A lab that keeps
  promoting cousins of disproven families is not learning, and the dev gate cannot see it: a
  twenty-year average and a deflated Sharpe both said yes every time.
- **The rule**, both halves required:
  - **(F) folds** — the method beat the recorded `REF-SPY-HOLD` benchmark in a **majority** of its
    scoreable walk-forward folds (`walkforward.Record.majority`), **and** it is scoreable on every
    fold the geometry yields, at least `MIN_FOLDS = 4`. The second clause is the fail-closed
    answer to thin evidence: under a coin-flip null a strict majority of an *odd* fold count is a
    coin flip at every odd count (n=3 → 0.5000, n=4 → 0.3125, n=5 → 0.5000), so a minimum of 3
    would admit evidence strictly weaker than 4. It is a bound, not a p-value — overlapping folds
    are not independent observations and nothing here may be fed into a DSR.
  - **(K) kin** — no method in the candidate's **`family` ∪ its transitive ancestors through
    `parent_id`** reads `test-failed`. Measured across the lab's 63 methods: `family` alone blocks
    26 and misses M0030, whose family is clean but whose parent M0029 and grandparent M0021 both
    failed; ancestors alone block 10; the union blocks 29; the full connected component blocks 36
    in one 26-method blob and is rejected as too blunt — "cousin of a disproven family" stretched
    four hops through unrelated families stops being a statement about the evidence.
- **Where it is enforced, and where it is not.** `commands/lab.py:_promote` calls it **before**
  `prereg.promote_method`, so a refusal leaves the repository and the database byte-identical: no
  file, no status move, no insight, no analysis row. `lab test` does **not** re-check (K): a
  pre-registration is a promise and is not re-opened, and refusing at `lab test` would strand a
  method in `promoted`, a state with only two exits and both final. What `lab test` adds instead is
  one printed note when the kin has failed since the promotion — a sentence, not a gate, the same
  shape as `_ratchet_warning`.
- **No override exists, in any form.** No `--force`, no environment variable, no "promote anyway".
  If the rule proves too strict the answer is a recorded, argued change to the rule, because an
  override path is precisely the mechanism that produced the 0-for-5 roster.
- **A missing benchmark refuses**, naming `REF-SPY-HOLD`, so the reader knows it is the lab's
  fixture that is wrong rather than their method. With no benchmark curve there is no fold
  geometry, and "no scoreable folds" is refused rather than waved through.
- **Every curve is de-funded before it is measured.** `trial_deposits(conn, row, curve)` moved here
  out of `commands/lab.py` so the gate, `lab regime` and `lab walkforward` share one de-funding
  path. Every trial from M0032 on is funded with the owner's 5,000,000 IDR a month; measuring a
  raw funded curve against a benchmark that received none read as seventy to eighty points a year
  of edge that was the owner's own deposits (insight 72, 75).
- `check(conn, method_id) -> None` raises `store.LabError`, which `commands/lab.py:run` already
  turns into exit 2 — no new `except` anywhere. `summary(conn, method_id) -> str` is the one-line
  fold record `lab status` prints beside each dev-eligible method.
- **What it costs today, measured 2026-10-09.** It refuses all seven dev-eligible methods, which is
  the intended effect and not a side effect. It is not a permanent stop: M0034 and M0035 each win 3
  of 4 folds with clean kin, and read `rejected` only because the bars moved under them.

In `lab status`, `_hard_gate_states` runs the gate once per command over the dev-eligible methods
and catches every `LabError`, so a lab with no benchmark — a new one, or any fixture in
`test_lab_status.py` — prints the refusal as a sentence instead of failing the command. Promoted
methods are not re-judged there: the promise is not re-opened.
```

**Impact:** the readme now describes both new modules and the two new pre-registration fields.
**Reconciliation note:** changes (a) and (d) describe phase 1's module from this plan's interface
contract. Before committing, the implementer must read the real
`engine/src/seer_engine/lab/hardgate.py` and correct any name it got wrong — the readme claims to
be a map and a wrong one is worse than none.

### Step 9: `docs/plans/WALK_FORWARD_EVALUATION_PLAN.md` — phase 4 done, the cost paragraph corrected, D6 recorded

**File:** `docs/plans/WALK_FORWARD_EVALUATION_PLAN.md`

**Change (a)** — `:6`:

```markdown
**Status:** all four phases done 2026-10-09
```

**Change (b)** — the phase 4 list item and the line beneath it, `:194-197`:

```markdown
4. **The hard gate.** Specified in full below. **The owner decided it on 2026-10-09**: a
   majority of folds AND a clean family, enforced as a refusal, not a report.
   **Done 2026-10-09**, as `docs/plans/LAB_HARD_GATE_PLAN.md` — `engine/src/seer_engine/lab/
   hardgate.py`, called from `lab promote` before the pre-registration is written; two new
   pre-registration fields recording what the method cleared; and `lab status`, both skills and
   this plan updated so the gate is visible before it bites.

Phases 1-3 took an afternoon. Phase 4 took the next session, and all four of its open questions
were answered rather than assumed — see below.
```

**Change (c)** — the stale cost paragraph. Replace `:217-227` (the whole `## What it costs`
section through the paragraph ending `produced the 0-for-5 roster in the first place.`):

```markdown
## What it costs, stated before anyone is surprised

**It blocks every promotion in the lab as of today.** Measured 2026-10-09 against a copy of
`lab/lab.sqlite`, on all **seven** dev-eligible methods — and the reason set is split, which is why
only the conjunction gets there:

| method | folds won | (F) majority | (K) kin |
|---|---|---|---|
| M0007 | 3 of 4 | pass | **fail** — family `stock-residual-momentum` (M0022) |
| M0011 | 2 of 4 | **fail** | **fail** — family (M0022) |
| M0019 | 3 of 4 | pass | **fail** — family `stock-momentum-risk-managed` (M0002) |
| M0020 | 3 of 4 | pass | **fail** — family (M0002) |
| M0024 | 2 of 4 | **fail** | pass — kin clean |
| M0030 | 2 of 4 | **fail** | **fail** — family clean, but ancestors M0021 and M0029 both failed |
| M0033 | 3 of 4 | pass | **fail** — family (M0022) |

Four fail on kin alone, one on folds alone, two on both. **M0030 is the live case that decided the
ancestry question** (open question 3): a family-only (K) would let it through the moment it wins a
third fold, while its parent and grandparent have both already failed out of sample.

**This is not a permanent stop, and the earlier draft of this paragraph was more pessimistic than
the evidence.** It said every dev-eligible method was in a family that had already failed, so "the
lab will promote nothing until a genuinely new family appears". That was written when the lab held
four dev-eligible methods; it holds seven now, two of them with clean families. And **M0034 and
M0035 each win 3 of 4 folds with clean kin** — they read `rejected` rather than `dev-eligible`,
which is a bar the lab moves, not a family the evidence closed. The gate blocks everything today
because of what is in the lab today, not because of its shape.

That is the intended effect, not a side effect. Five out-of-sample results, five failures; and the
surviving ideas are mostly cousins of the methods that produced them. A lab that keeps promoting
cousins of disproven families is not learning. If this proves too strict in practice the answer is
a recorded, argued change to the rule -- not an override path, which is precisely the mechanism
that produced the 0-for-5 roster in the first place.
```

**Change (d)** — a new section inserted immediately after the four open questions end (`:259`,
before `## Also update, or the gate is invisible until it bites`):

```markdown
## How the four open questions were answered

Each was answered in `hardgate.py`'s own prose with the reason beside it; this is the summary and
the pointer. The full argument is in `docs/plans/LAB_HARD_GATE_PLAN.md`, Decisions D2, D3, D4, D6.

1. **The minimum is every fold the geometry yields, and at least `MIN_FOLDS = 4`.** The fold
   geometry is cut from the benchmark curve, so it is global: `REF-SPY-HOLD` spans
   1993-02-01..2015-10-16 and yields four folds, and every `M*` method in the lab is scoreable on
   all four — so the minimum costs a real method nothing today. Why not 3: under a coin-flip null
   a strict majority of an **odd** count is a coin flip at every odd count (n=2 → 0.2500,
   n=3 → 0.5000, n=4 → 0.3125, n=5 → 0.5000), so "3 or more" would admit evidence strictly weaker
   than 4 and no stronger than 1. A bound, not a p-value. The second clause is also a tripwire: if
   `MIN_TRAIN_YEARS`, `EVAL_YEARS` or the dev window ever changes the geometry, a changed setting
   cannot silently lower the bar.
2. **(K) is checked at promote only.** The pre-registration is a promise and is not re-opened.
   `promoted` has only two exits and both are final, so a refusal at `lab test` would strand a
   method forever — the exact failure "Why at promote and not at test" rejects. What `lab test`
   adds instead is one printed note when the kin has failed since the promotion: information
   before the look is spent, no new exit code, no new transition.
3. **Yes — (K) walks `parent_id`.** Kin is `family` ∪ transitive ancestors. Not the full connected
   component: that blocks 36 of 63 methods in one 26-method blob and would refuse M0019 on account
   of M0021, a multi-factor blend four hops away in an unrelated family. Descendants are left to
   the `family` string, which by construction holds a variation twin.
4. **No path back is built, and the need is real** — recorded here as plan **Decision D6**.
   `reevaluate` exists for `rejected -> dev-eligible` when the bars move; **nothing equivalent
   exists for a method whose kin is blocked, and nothing was invented here.** Two shapes will
   eventually be wanted and neither is built: a family whose failure is later attributed to
   something other than the idea (a cost model, a fill assumption), and a method whose `parent_id`
   links it to a failure it does not inherit. Both are *arguments*, and this brief's own sentence
   says an argued change to the rule is the mechanism — a commit, in git, not a flag. When the
   need arrives, that is the shape of the work: change the rule and say why, do not add a door.
```

**Impact:** the brief now matches the lab, carries D6 where the next reader of the walk-forward
plan will find it, and no longer carries a list that was true for four hours.

---

## Verification

**Build:**

```
cd /home/miftah/.worktrees/seer/lab-hard-gate/engine && \
  PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -c \
  "import seer_engine.commands.lab as m; print(m._hard_gate_states, m._promotable_now)"
```

**Tests:**

```
cd /home/miftah/.worktrees/seer/lab-hard-gate/engine && \
  PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q tests/test_lab_*.py
```

`PYTHONPATH` is not optional: the worktree has no `.venv` of its own, and without it pytest
silently tests the **main checkout** rather than this branch. Baseline at `origin/main` 7708350 for
`test_lab_prereg.py` + `test_lab_walkforward.py` + `test_lab_status.py` is **68 passed** — quote
the count, never the seconds (8.99s for the analyst, 11.35s for phase 1, the same 68 tests).
`test_lab_status.py` alone is **12 passed**, confirmed in this worktree. After this phase
`test_lab_status.py` must read **18 passed**, and every other `test_lab_*.py` file must be
unchanged in count from what phases 1 and 2 left it at — `test_lab_prereg.py` **42**,
`test_lab_test_window.py` **19**, plus phase 1's own `test_lab_hardgate.py`.

**Manual check** — `lab status` against the real lab, on a copy, because `lab` migrates the
database on connect and even a read dirties the committed file:

```
cp /home/miftah/.worktrees/seer/lab-hard-gate/lab/lab.sqlite "$SCRATCH/lab-copy.sqlite"
cd /home/miftah/.worktrees/seer/lab-hard-gate/engine && \
  PYTHONPATH=$PWD/src SEER_LAB_DB="$SCRATCH/lab-copy.sqlite" \
  /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab status
```

Read for: a **Promotable now** block reading `(none)`; a **Refused by the hard gate** block naming
all seven of M0007, M0011, M0019, M0020, M0024, M0030, M0033, each with a fold record matching the
measured table in step 9(c) and the kin that blocks it (M0022 for M0007/M0011/M0033, M0002 for
M0019/M0020, M0021 and M0029 for M0030, and a folds-only reason for M0024); a
`Promoted (pre-registered): (none)` line that blames the gate rather than an unrun command; and a
whole-command wall time under a second or two. **Do not run any lab command against
`lab/lab.sqlite` itself**, and `git status` must show `lab/lab.sqlite` unmodified afterwards.

Then confirm `git diff --stat` touches exactly six files and none of them is `lab/lab.sqlite`,
`web/data/lab.json`, `docs/lab/prereg/*.md`, `lab/hardgate.py`, `lab/prereg.py`,
`lab/walkforward.py` or `backtest/walkforward.py`.

**Exit criteria:**

1. `lab status` prints every dev-eligible method's fold record, and no method `lab promote` would
   refuse appears under "Promotable now".
2. The Promoted section's empty reason names the hard gate when the gate is what is holding it,
   and no longer says a command "has not been run yet" when running it would exit 2.
3. `lab status` exits 0 on a lab with no `REF-SPY-HOLD` dev trial and empty curves.
4. `tests/test_lab_status.py` reports 18 passed, with every one of the file's 317 existing lines
   byte-identical — the only changes are two added import lines and the block inserted between the
   old `:301` and the old `:304`; the whole `tests/test_lab_*.py` suite passes.
5. The explore skill and the Sera skill both say `lab promote` **refuses**, name both (F) and (K)
   including the ancestry walk, state that no override exists, and count the buy signal's
   conditions at four.
6. `package_readme.md` describes `lab/hardgate.py`, `lab/walkforward.py` and the two new
   pre-registration fields, checked against the modules as phases 1 and 2 actually built them.
7. `WALK_FORWARD_EVALUATION_PLAN.md` reads phase 4 done, carries the measured seven-method table
   instead of the stale four-method list, says the gate is not a permanent stop, and records D6.

## Handoffs

- **`walkforward.buy_signal`'s success string says "cleared all three"** and there are four
  conditions (`lab/walkforward.py:296`). `BUY_CONDITIONS` above it already lists four. This phase
  fixes the count in the two skills but **must not touch `lab/walkforward.py`** — it is on the
  plan's do-not-edit list, and the file is phase 1's read-only dependency. Recorded in the index as
  a **follow-up under Decision D9**, not a change: the one-word fix and the one test that asserts
  that string belong to whoever next opens that module.
- **A `promoted` method whose kin fails afterwards** gets a printed note at `lab test`, owned by
  **phase 2** (plan Decision D3; reconciliation moved it there from nowhere — the index's draft
  left it unowned and this plan had handed it to phase 1). This phase deliberately does not surface
  it in `lab status`: the promise is not re-opened. If the owner later wants it visible there too,
  it is a line in `_promotable_now`'s `(already pre-registered)` branch and a `gates` call widened
  to `status IN ('dev-eligible','promoted')`.
- **No path back for a kin-blocked method** (plan Decision D6, R5 — phase 1's requirement). This
  phase only *records* the need, in the walk-forward plan. Building it is a separate, argued
  change to the rule and explicitly not this plan set's work.
- **`web/data/lab.json` and seertrade.site show nothing of the hard gate.** The site's method
  pages carry the dev gate's checklist and verdict; neither the fold record nor the kin state
  reaches them, so a reader on the web still sees "dev-eligible" with no hint that `lab promote`
  would refuse. That is a real gap and a web-side plan, not an engine one. Out of scope here —
  this phase touches no snapshot and runs no `lab stage`.
- **`lab/walkforward.py` was missing from `package_readme.md`'s package map entirely.** Step 8(a)
  adds it, because `hardgate.py`'s line is unreadable without it. Flagged as the one piece of
  adjacent repair in this phase rather than left silent.

## Rollback

This phase is one commit on `feature/lab-hard-gate`; `git revert` it. Nothing it changes is
persisted outside git: no database row, no snapshot, no pre-registration file, no research store.

To undo it without reverting phases 1 and 2:

```
git checkout origin/main -- \
  .claude/skills/explore-and-experiment-new-method/SKILL.md \
  .claude/skills/sera-the-explorer/SKILL.md \
  docs/plans/WALK_FORWARD_EVALUATION_PLAN.md
```

and hand-revert the four functions in `engine/src/seer_engine/commands/lab.py`
(`_hard_gate_states` deleted, `_empty_reason`, `_promotable_now`, `_promotion_path` and
`_PROMOTION_STATUSES` restored), the two readme blocks, and the six appended tests —
`engine/package_readme.md`, `engine/src/seer_engine/commands/lab.py` and
`engine/tests/test_lab_status.py` all carry phase 1 and phase 2 work too, so a blanket
`git checkout origin/main --` on them would take those with it.

After a revert `lab promote` still refuses — the rule is phase 1's — but `lab status` goes back to
listing refused methods as promotable, which is the invisible-until-it-bites state this phase
exists to end. Revert the whole set, or none of it.
