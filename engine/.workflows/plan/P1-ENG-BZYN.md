> Adopted from `WHY_THIS_PICK_PIPELINE_PLAN.md` phase 4. Source: `.workflows/plan/why-this-pick-pipeline/phase-4.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 4: Promote requires evidence

**Plan set:** `WHY_THIS_PICK_PIPELINE_PLAN.md`
**Analysis:** `20261006-213425-W7P3_code_analyzer.md`
**Satisfies:** R7 — a lab method cannot reach the site unless it can say, per pick, why it picked
**Depends on:** Phase 1 (`strategies/evidence.py`: `EVIDENCE`, `has_evidence`)
**Difficulty:** EASY
**Package:** `engine/src/seer_engine/commands`

---

## Goal

`python -m seer_engine promote …` refuses (exit 2, `NotPromotable`) a candidate whose allocator's
roster name has no entry in `strategies.evidence.EVIDENCE`, with one line naming the file and dict
to extend. The refusal fires before any database write, dry-run included. The explore skill's
promotion steps tell the agent that a new allocator needs both a `RESOLVER` entry and an
`EVIDENCE` entry before it can be promoted.

## Interface Contract

**Deletes:** nothing
**Renames:** nothing
**Creates:** `seer_engine.commands.promote._check_evidence(object_name: str) -> None` (`engine/src/seer_engine/commands/promote.py`, placed after `_check_rules`, ~line 138)
**Signature changes:** none (`build_promotion` keeps its signature; it now also raises `NotPromotable` for a missing evidence entry)
**Requires (from earlier phases):**
- Phase 1: module `seer_engine.strategies.evidence` exists, importable from `commands/promote.py` with no import cycle (it must not import `seer_engine.commands`).
- Phase 1: `EVIDENCE: dict[str, EvidenceFn]` is a **module-level dict** and `has_evidence(object_name)` reads it **at call time** (`return isinstance(object_name, str) and object_name in EVIDENCE`), so `monkeypatch.delitem(evidence.EVIDENCE, "FUNDAMENTAL")` changes the answer. Pinned by the reconciler: phase 1's contract states it and its code does exactly this.
- Phase 1: `EVIDENCE` contains key `"FUNDAMENTAL"` (K1), so every existing promote test (which promotes M0005-ALL → `FUNDAMENTAL`) stays green.
**Leaves alone (owned by others):** `strategies/evidence.py` (Phase 1), `paper/roster.py` (nobody), `lab/methods/*` (nobody), `paper/store.py`, `commands/paper.py`, migration 009 (Phase 2), `commands/explain.py`, runbook, `engine/package_readme.md` (Phase 3 — it also documents this phase's third promotable condition in the readme's `promote` section, step 6h, so this phase does not edit that file), `web/**` (Phase 5).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/commands/promote.py` | modify | docstring lines 10–16 (three promotable conditions); import `evidence` (~line 63); new `_check_evidence` after `_check_rules` (~line 138); `build_promotion` (lines 210–243) resolves the name once and gates on evidence |
| `engine/tests/test_promote_command.py` | modify | import `evidence` (~line 22); two new tests after `test_check_lookback_refuses_more_bars_than_the_night_loads` (~line 188) and one DB test after `test_a_rejected_method_needs_the_acknowledgement` (~line 299) |
| `.claude/skills/explore-and-experiment-new-method/SKILL.md` | modify | Promotion "Then:" step 4 (lines 154–158): one added sentence on RESOLVER + EVIDENCE |

## Implementation Steps

### Step 1: Docstring — promotable means three things
**File:** `engine/src/seer_engine/commands/promote.py:10-16`
**Change:** replace the "two things" paragraph.
**Code:** (replaces lines 10–16 exactly)
```python
**Promotable** means three things, and this command refuses anything that is not all three:

1. the method file exposes the variant as a ``Candidate`` -- a frozen (rules, allocator, params)
   triple. The roster entry is that triple unchanged; nothing here invents a parameter.
2. the variant's allocator is a value ``paper.roster.RESOLVER`` names. A ``strategies`` row
   cannot hold a live Python object, and the object's *name* is part of the frozen spec, so an
   object the resolver cannot name has no roster identity. The refusal says which line to add.
3. that name has an entry in ``strategies.evidence.EVIDENCE``: the plain-English facts behind
   each pick, which the paper night stores and ``explain`` turns into the site's "Why this
   pick". A strategy that cannot say why it picked a stock does not go on the site.
```
**Impact:** documentation only.

### Step 2: Import the evidence module
**File:** `engine/src/seer_engine/commands/promote.py:63` (after `from seer_engine.sim.rules import TradeRules`)
**Change:** add one import. Import the **module**, not the function, so tests can patch `evidence.EVIDENCE`.
**Code:**
```python
from seer_engine.sim.rules import TradeRules
from seer_engine.strategies import evidence
```
**Impact:** promote now imports phase 1's module; fails to import until phase 1 lands (hence the dependency).

### Step 3: Add `_check_evidence`
**File:** `engine/src/seer_engine/commands/promote.py`, insert after `_check_rules` (after line 137, before `def find_candidate` at line 140)
**Code:**
```python
def _check_evidence(object_name: str) -> None:
    """NotPromotable when ``object_name`` has no entry in ``strategies.evidence.EVIDENCE``.

    The paper night stores each pick's evidence and ``explain`` writes the site's "Why this pick"
    from it, using only those facts. A roster object without an evidence function would put picks
    on the site with no reason at all, so the gap is refused here rather than discovered there.
    """
    if not evidence.has_evidence(object_name):
        raise NotPromotable(
            f"{object_name} has no per-pick evidence, so the site could not say why it picked a "
            f"stock. Add an entry \"{object_name}\": <its evidence function> to EVIDENCE in "
            f"seer_engine/strategies/evidence.py (2-6 plain-English facts per pick, numbers "
            f"formatted), commit it, then promote again."
        )
```
**Impact:** new private helper; no caller yet.

### Step 4: Gate `build_promotion` on evidence
**File:** `engine/src/seer_engine/commands/promote.py:210-243`
**Change:** resolve the object name once, right after the rules check, then gate on evidence before lookback and entry construction. `object_name_of` is still the first thing that can refuse an unnamed object, so the RESOLVER refusal keeps precedence over the evidence one (an object with no name cannot be looked up in `EVIDENCE`). `build_promotion` is called in `_run` (line 448) before `db.transaction` opens (line 451), so the refusal precedes every write, dry-run included; `run` maps `PromoteError` to exit 2 and logs the message.
**Code:** (full replacement of `build_promotion`)
```python
def build_promotion(args: argparse.Namespace, data_date: date, sort: int) -> Promotion:
    """The roster entry and its contract-C2 params, from the named method variant. No I/O."""
    _method, _path, candidate = find_candidate(args.method, args.candidate)
    obj = candidate.allocator
    _check_rules(candidate.rules)
    object_name = object_name_of(obj)
    _check_evidence(object_name)
    engine = "bracket" if candidate.rules.engine == "bracket_v0" else "book"
    lookback = obj.lookback if engine == "bracket" else obj.lookback(candidate.params)
    check_lookback(int(lookback), data_date)
    entry = roster.RosterEntry(
        id=args.id,
        name=args.name,
        sub=args.sub,
        icon=args.icon,
        is_champion=False,  # the champion is SPY (handover D2); a promotion never takes it
        is_benchmark=False,
        sort=sort,
        engine=engine,
        rules=candidate.rules,
        obj=obj,
        object_name=object_name,
        params=candidate.params,
        registry_id=None,  # D1: a promoted entry is never a REGISTRY entry
        lookback=int(lookback),
        gate_note=args.gate_note,
        gate_applicable=not args.gate_not_applicable,
    )
    return Promotion(
        entry=entry,
        params=roster.strategy_params(entry),
        method_id=args.method,
        candidate_id=candidate.id,
        retire_id=args.retire,
        sort=sort,
    )
```
**Impact:** `object_name_of` now runs before `check_lookback` instead of inside the `RosterEntry(...)` call; both are pure refusals, so only the order in which two simultaneous refusals are reported changes. No existing test depends on that order.

### Step 5: Tests
**File:** `engine/tests/test_promote_command.py`

5a. Import (after line 22, `from seer_engine.strategies.f_fundamental import ...`):
```python
from seer_engine.strategies import evidence
```

5b. Pure tests, inserted after `test_check_lookback_refuses_more_bars_than_the_night_loads` (after line 187):
```python
def test_check_evidence_refuses_an_object_without_evidence(monkeypatch):
    promote._check_evidence("FUNDAMENTAL")  # phase 1 gives the real roster object its facts
    monkeypatch.delitem(evidence.EVIDENCE, "FUNDAMENTAL")
    with pytest.raises(promote.NotPromotable, match="FUNDAMENTAL has no per-pick evidence"):
        promote._check_evidence("FUNDAMENTAL")
    with pytest.raises(promote.NotPromotable, match="seer_engine/strategies/evidence.py"):
        promote._check_evidence("FUNDAMENTAL")


def test_every_resolver_object_has_evidence():
    """The roster today is promotable by this rule: every named object can explain its picks."""
    for name, binding in roster.RESOLVER.items():
        if binding.obj is not None:
            promote._check_evidence(name)
```

5c. Command-level test (exit 2, one-line message, nothing written, dry-run too), inserted after `test_a_rejected_method_needs_the_acknowledgement` (after line 298):
```python
@pytest.mark.parametrize("dry_run", [False, True])
def test_an_allocator_without_evidence_is_refused_before_writing(
    pg, monkeypatch, lab, tmp_path, caplog, dry_run
):
    """R7: no evidence entry -> exit 2 with the file and dict to extend, and neither database moves."""
    monkeypatch.delitem(evidence.EVIDENCE, "FUNDAMENTAL")
    _wire(monkeypatch, pg=pg, lab=lab)
    caplog.set_level(logging.ERROR, logger=promote.__name__)
    assert promote.run(_args(dry_run=dry_run, lab_db=tmp_path / "lab.sqlite")) == 2
    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert "\n" not in errors[0]
    assert "EVIDENCE" in errors[0] and "seer_engine/strategies/evidence.py" in errors[0]
    pg.rollback()
    assert pg.execute("SELECT count(*) FROM strategies WHERE id = 'TEST-FND'").fetchone()[0] == 0
    assert lab_store.PROMOTION_MARKER not in lab_store.get_method(lab, METHOD)["analysis"]
```
Add `import logging` to the imports block (line 11, alphabetically after `import argparse`):
```python
import argparse
import logging
from datetime import date
```

Notes for the implementer:
- The autouse `resolver_entry` fixture keeps `FUNDAMENTAL` in `RESOLVER`, so `object_name_of` passes and the evidence gate is what refuses.
- Monkeypatch ordering: `monkeypatch.delitem(evidence.EVIDENCE, ...)` is undone at teardown with the other patches; the `_Borrowed` wrapper already keeps `pg.close` real (see the class docstring), so no new hang risk.
- Existing tests stay green only because phase 1's `EVIDENCE` contains `"FUNDAMENTAL"`.

### Step 6: Skill — promotion needs RESOLVER and EVIDENCE
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:154-158` (Promotion, "Then:" step 4)
**Change:** add one sentence after "**Run it** — you do not ask anyone (design §6)." Replace step 4 with:
```markdown
4. **Pass:** `lab test` prints the exact `python -m seer_engine promote …` command, every argument
   filled in from the two recorded trials. **Run it** — you do not ask anyone (design §6). A new
   allocator is refused until it has two committed entries: a name in `RESOLVER`
   (`paper/roster.py`) and an evidence function under that name in `EVIDENCE`
   (`strategies/evidence.py`) — 2–6 plain-English facts per pick, the numbers its formula used,
   which become the site's "Why this pick". Add both, commit, then run it. It
   writes the roster row with no `paper_start`, so the next paper night freezes the spec and
   starts its own clock. Then `lab stage`, commit, push, verify. **Real money stays out of
   scope:** design §1 needs ≥ 3 months and ≥ 100 closed paper trades of forward paper first.
```
**Impact:** agent guidance only.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/why-this-pick-pipeline/engine && .venv/bin/python -c "import seer_engine.commands.promote"` (the worktree needs its own venv; main's venv tests the wrong tree)
**Tests:** fast loop `cd /home/miftah/.worktrees/seer/why-this-pick-pipeline/engine && .venv/bin/python -m pytest tests/test_promote_command.py tests/test_evidence.py -q`, then invariant 1 in full:
```
docker start seer-pg
cd /home/miftah/.worktrees/seer/why-this-pick-pipeline
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q
engine/.venv/bin/ruff check engine
cd web && npx vitest run && npx tsc --noEmit
```
The pytest run passes except the two known Python-3.12-only failures (`test_f_fundamental.py::test_allocator_shape`, `test_market_fundamentals.py::test_adding_the_hook_does_not_change_the_allocator_check`).
**Manual check:** none required; optionally `python -m seer_engine promote --method M0005 --candidate M0005-ALL --id X --name x --sub x --gate-note x --lab-status-stays --dry-run` after temporarily removing `FUNDAMENTAL` from `EVIDENCE` shows the one-line refusal and exit 2.
**Exit criteria:** promote of a candidate whose object has no `EVIDENCE` entry exits 2 with a one-line reason naming `seer_engine/strategies/evidence.py` and `EVIDENCE`, writes nothing (dry-run or not); all pre-existing promote tests pass.

## Handoffs

- None required by other phases. (Reconciled: phase 1's `has_evidence` reads the live `EVIDENCE` dict, so Step 5's `monkeypatch.delitem` works as written. Phase 3 documents this gate in `engine/package_readme.md`.)
- Not done here (out of scope, nobody asked): the stale `resolver_entry` fixture docstring in `test_promote_command.py` says FUNDAMENTAL is not in RESOLVER on main; it is now (`paper/roster.py:238`). Drive-by cleanup for a later task.

## Rollback

Revert the three files: `git checkout origin/main -- engine/src/seer_engine/commands/promote.py engine/tests/test_promote_command.py .claude/skills/explore-and-experiment-new-method/SKILL.md`. No data, schema or roster change to undo.
