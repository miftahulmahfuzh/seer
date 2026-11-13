# Phase 1 — `lab idea` lists recorded controls; skills tell children to cite them

**Satisfies:** R1, R2, R3, R4
**Criteria:** R1.1, R2.1, R2.2, R2.3, R2.4, R3.1, R4.1
**Depends on:** —
**Worktree:** `/home/miftah/.worktrees/seer/lab-cite-recorded-controls` (every path below is relative to it)

**Scope, stated first (CLAUDE.md "state the proposed scope in one line"):** one helper in an existing
file, one call from an existing function, one test block, and wording in four docs. No new module, no
new subcommand, no schema change, no lab row written. `lab run`'s repeat refusal stays the guarantee.

**Does not touch:** `lab/lab.sqlite`, `web/data/lab.json`, `runner.py`, `hardgate.py`, any method file,
`control_shape.py`. The twins module gets a docstring paragraph only.

## Step 1 — `engine/src/seer_engine/commands/lab.py`

After `_IDEA_NEIGHBOURS = 5` add the limit, and add the helper before `_print_idea_neighbours`:

```python
#: Most recorded controls `lab idea` lists. Five neighbours rarely hold more than a handful.
_IDEA_CONTROLS = 8


def _recorded_controls(conn, method_ids: Sequence[str], *, limit: int = _IDEA_CONTROLS) -> list[str]:
    """The control arms of ``method_ids`` the lab already holds, as printable lines, one per book.

    **Why a listing and not a reuse.** A control re-run on a new method's frame prices the treatment,
    and when its book is already recorded the re-run reproduces that trial byte for byte
    (``lab/twins.py``): the same curve, metrics and trade count, a trial row of its own and no new
    evidence. What the new method needs is the recorded numbers, which ``lab show`` prints. So a
    child *cites* the first recording by trial in its hypothesis and spends the arm on a book the
    lab has not recorded. Nothing is copied into a trial row, because a copy would be a twin
    (hardgate D19) and a row nobody measured. The append-only rows are only read; N counts methods
    with a dev trial, so citing moves it by nothing; D17 reads controls inside a method and an
    absent one is UNRESOLVED, never a refusal.

    **One line per book, named by its first recording.** An arm that is a later copy of an earlier
    trial is reported as that earlier trial, once, so M0528-REL-RAND reads as the trial it copies.
    ``current store`` means that book (the recording or any copy of it) was measured on the store the
    lab's newest dev trial used, so it has been shown to reproduce on today's data. ``older store
    only`` means it has not, and the child should re-run it as a declared control. ``rules/allocator``
    are printed so the child can see whether its own control would be the same book: a different
    rule, allocator or params is a different book and is re-run, not cited. The role is read from the
    method files (``_roles``), which return ``{}`` when they cannot be read, so the listing is then
    empty rather than wrong.
    """
    roles = _roles(list(method_ids))
    row = conn.execute(
        "SELECT store_fingerprint FROM trials WHERE window = 'dev' ORDER BY n DESC LIMIT 1"
    ).fetchone()
    current = str(row[0]) if row else ""
    from seer_engine.lab import control_shape, twins

    out: list[str] = []
    seen: set[int] = set()
    for mid in method_ids:
        for (m, cid), role in roles.items():
            if m != mid or role != control_shape.ROLE_CONTROL:
                continue
            own = conn.execute(
                "SELECT n, store_fingerprint FROM trials WHERE candidate_id = ? AND window = 'dev'",
                (cid,),
            ).fetchone()
            if own is None:
                continue
            found = twins.twins_of(conn, cid)
            first_n = found[0].n if found and found[0].earlier else int(own[0])
            if first_n in seen:
                continue
            seen.add(first_n)
            first = conn.execute(
                "SELECT candidate_id, method_id, rules_id, allocator_id FROM trials WHERE n = ?",
                (first_n,),
            ).fetchone()
            on_current = current in {str(own[1]), *(t.store_fingerprint for t in found)}
            out.append(
                f"  {first[0]}  trial {first_n}, {first[1]}, {first[2]}/{first[3]}, "
                f"{'current store' if on_current else 'older store only'}"
            )
            if len(out) >= limit:
                return out
    return out
```

At the end of `_print_idea_neighbours`, after the `for x in near:` loop (inside the function, after the
existing `print(f"         shares: ...")` line), add a second guarded block:

```python
    try:
        held = _recorded_controls(conn, [x.id for x in near])
    except Exception as e:  # noqa: BLE001 -- a hint must never fail a reservation already made
        print(f"Recorded controls: not read ({e}).", file=sys.stderr)
        return
    if held:
        print(
            "Controls those methods already hold, named by first recording. When your own control "
            "would be the same rules, allocator and params, and the book is on the current store, "
            "cite it in your hypothesis (read it with `lab show`) and spend that arm on a book the "
            "lab has not recorded. A different book, or an older-store one, is still run, declared:",
            file=sys.stderr,
        )
        for line in held:
            print(line, file=sys.stderr)
```

`_print_idea_neighbours` already imports nothing heavy at module scope; `_roles` already lazy-imports
`control_shape` and `discover`. The early `return` when `near` is empty stays as it is (no neighbour,
no controls to list).

## Step 2 — `engine/src/seer_engine/lab/twins.py`

Append one paragraph to the module docstring, before the "Connection-agnostic on purpose" paragraph:

```
**A recorded control is cited, not copied (2026-11-13).** Sera batch 20261113-0721 re-ran eight arms
(M0545's SMA200 and ALWAYS, M0561's D3 and D6, four of M0606's) whose books M0084, M0558, M0108,
M0232, M0313 and M0337 had recorded first. Each was a declared control, so ``lab run`` accepted it, and
each cost a simulation and a dev trial row that said nothing new. The recorded trial already holds what
the re-run recomputes, byte for byte, so the next method cites it by first-recorded trial (``lab idea``
lists them) and runs only arms that hold a book the lab has not recorded. Nothing is written for a
citation, so the append-only rows, N (methods with a dev trial), DSR (stamped moments of recorded rows)
and D17/D19 (no twin arm exists) are all untouched. Citing is valid only when the control would be the
same rules, allocator and params on the same window and the book is on the current store; otherwise it
is re-run as a declared control, exactly as before. This refusal logic is unchanged.
```

## Step 3 — tests, `engine/tests/test_lab_repeat_refusal.py`

Append after the existing `lab idea` neighbour tests (the file already imports `store`, `lab_cmd`,
`_arm`, `_method_row`, `capsys`):

```python
def _idea_lab(tmp_path, monkeypatch, *, roles, extra=None):
    """A lab with M0001 (the neighbour) and the arms recorded by ``extra(c)``."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    with c:
        store.add_method(c, id="M0001", name="A brake on the account's own fall",
                         family="drawdown-brake", source_kind="knowledge",
                         hypothesis="Trim in proportion to how far the book is below its own high",
                         status="registered")
    if extra:
        extra(c)
    c.close()
    monkeypatch.setattr(lab_cmd, "_roles", lambda ids: roles)
    return db


def test_lab_idea_lists_a_neighbours_control_by_its_first_recording(tmp_path, monkeypatch, capsys):
    def extra(c):
        _arm(c, "M0001", "CTRL")

    db = _idea_lab(tmp_path, monkeypatch, roles={("M0001", "M0001-CTRL"): "control"}, extra=extra)
    assert lab_cmd.run(_idea_args(db)) == 0
    got = capsys.readouterr()
    assert got.out == "M0002\n"
    assert "  M0001-CTRL  trial 1, M0001, MONTHLY_HOLD/TIMING, " in got.err


def test_a_control_that_copies_an_earlier_book_is_named_by_the_earlier_one_once(
    tmp_path, monkeypatch, capsys
):
    def extra(c):
        _method_row(c, "M0009")
        _arm(c, "M0009", "FIRST")            # n=1, the first recording
        _arm(c, "M0001", "CTRL")             # n=2, same curve and trades

    db = _idea_lab(tmp_path, monkeypatch, roles={("M0001", "M0001-CTRL"): "control"}, extra=extra)
    lab_cmd.run(_idea_args(db))
    err = capsys.readouterr().err
    assert err.count("M0009-FIRST") == 1 and "M0001-CTRL  trial" not in err


def test_the_store_of_the_newest_trial_decides_current_versus_older(tmp_path, monkeypatch, capsys):
    def extra(c):
        _arm(c, "M0001", "OLD", annual=0.10, store_fp="aaaaaaaa00")
        _arm(c, "M0001", "NEW", annual=0.20, store_fp="640fc25e00")

    roles = {("M0001", "M0001-OLD"): "control", ("M0001", "M0001-NEW"): "control"}
    db = _idea_lab(tmp_path, monkeypatch, roles=roles, extra=extra)
    lab_cmd.run(_idea_args(db))
    err = capsys.readouterr().err
    assert "M0001-OLD  trial 1, M0001, MONTHLY_HOLD/TIMING, older store only" in err
    assert "M0001-NEW  trial 2, M0001, MONTHLY_HOLD/TIMING, current store" in err


def test_unreadable_controls_never_fail_the_reservation_and_write_nothing_more(
    tmp_path, monkeypatch, capsys
):
    db = _idea_lab(tmp_path, monkeypatch, roles={})
    monkeypatch.setattr(lab_cmd, "_roles", lambda ids: (_ for _ in ()).throw(RuntimeError("boom")))
    before = store.connect(db).execute("SELECT count(*) FROM trials").fetchone()[0]
    assert lab_cmd.run(_idea_args(db)) == 0
    got = capsys.readouterr()
    assert got.out == "M0002\n" and "Recorded controls: not read (boom)" in got.err
    c = store.connect(db)
    assert c.execute("SELECT count(*) FROM trials").fetchone()[0] == before
    assert c.execute("SELECT status FROM methods WHERE id = 'M0002'").fetchone()[0] == "idea"
```

If `_arm`'s default `store_fp` is already the newest, adjust the two-store test so `NEW` is recorded
last (it is, above). If a test's neighbour ranking drops M0001 (it shares words with `_idea_args`'
defaults: "brake", "drawdown", "own", "high"), keep the same wording as the existing test.

## Step 4 — docs

1. `.claude/skills/sera-the-explorer/SKILL.md`, in step 3 after the "Read the neighbour list" bullet
   (ends `…so the child designs against it.`), add a bullet:

   ```
   - **Cite a recorded control, don't re-run it.** `lab idea …` also lists, on stderr, the
     controls those neighbours already hold, named by first recording (`M0108-DD20  trial 342, …,
     current store`). Put the ones that fit the frame into the reserved hypothesis ("control
     cited: M0108-DD20, trial 342") so the child does not spend an arm re-measuring them. Batch
     0721 re-ran eight such arms (M0545, M0561, M0606): each was accepted as a declared control and
     added a trial row and run time with no new evidence. A listed control is cited only when the
     child's own control would be the same rules, allocator and params and the line says `current
     store`; anything else is run as a declared control, as before. Nothing about `lab run`'s
     repeat refusal changes.
   ```

2. `.claude/skills/explore-and-experiment-new-method/SKILL.md`, after the paragraph ending `…is refused
   however it is labelled.` (line ~205-207), add:

   ```
     **Before you write a control arm, read `lab idea`'s control list** (the reservation printed it;
     `lab twins <neighbour>` shows the same books). If the control you were about to run is already a
     recorded book on the current store with the same rules, allocator and params, **cite it** in
     the hypothesis and the journal by its first-recorded candidate and trial number (`lab show` has
     its numbers) and use the arm for a book the lab has not recorded. A recorded trial is the
     measurement; re-running it records a twin row and no new evidence (M0545, M0561 and M0606 did
     it eight times). Cite only on an exact match; a different frame, a different dial or an
     older-store-only book is still run, declared. Never copy a recorded curve into a row.
   ```

   And in step 9 (queue next idea), after `Read them.` sentence block, append: `The same stderr also
   lists the controls those methods hold; cite them in the next hypothesis instead of re-running.`

3. `CLAUDE.md` "Experiment protocol": replace `run the control arms beside\nthe treatment` with `run the
   control arms beside\nthe treatment (cite a recorded control by trial instead when it is the same
   book on the current store)`.

4. `.claude/skills/verify-seer/features/lab-cli.md`, `lab idea` bullet: after "...on stderr" add
   `, then the control arms those methods already hold, by first recording ("Controls those methods
   already hold ...")`. In the Driving block the `idea` line comment gets `; plus a "Controls those
   methods already hold" block when a neighbour holds a control`.

## Verification

Run from the worktree (`engine/.venv` is per worktree: `python3.11 -m venv engine/.venv &&
engine/.venv/bin/pip install -e 'engine[dev]'`).

- `engine/.venv/bin/ruff check engine`
- `engine/.venv/bin/pytest engine/tests/test_lab_repeat_refusal.py engine/tests/test_lab_twins.py -n0`, then `engine/.venv/bin/pytest engine/tests` (CI needs `PG_TEST_URL`; start the `seer-pg` container per CLAUDE.md if tests would skip).
- Journeys:
  - **J1** · traces R2.1, R2.2, R2.4 — `verify-seer` skill: `$V up --no-web --empty`, then `$V lab RUN idea --name "dd20 shallow drawdown control" --family drawdown-brake --hypothesis "paired control draw gate shallow 20 monthly" --source-kind knowledge` against the committed-lab copy (not `--empty`; use the default demo copy) → stdout is one `M####` line, stderr shows `Controls those methods already hold` with at least one `  M0108-…  trial N, M####, …/…, (current|older) store` line, no candidate printed twice; exit 0 — passes when the listing's first-recorded ids match `engine/.venv/bin/python` read-only `twins.first_recorded` for the same candidate.
  - **J2** · traces R2.3 — the unreadable-roles test above → passes when it is green.
  - **J3** · traces R4.1 — `sha1sum lab/lab.sqlite web/data/lab.json; git status --porcelain lab web/data` before and after J1 on the real checkout → passes when hashes are equal and nothing is listed.
  - **J4** · traces R1.1, R3.1 — `grep -n "cited, not copied" engine/src/seer_engine/lab/twins.py; grep -n "Cite a recorded control" .claude/skills/sera-the-explorer/SKILL.md; grep -n "read \`lab idea\`'s control list" .claude/skills/explore-and-experiment-new-method/SKILL.md` → passes when each prints one line.
- Neighbor-check: `engine/.venv/bin/pytest engine/tests/test_lab_runner.py engine/tests/test_lab_methods.py -n0` stays green (the repeat refusal and N policy are untouched).

## Landing

Update the `lab idea` entry in `lab-cli.md` in the same commit (CLAUDE.md). Commit explicit paths only:
`engine/src/seer_engine/commands/lab.py engine/src/seer_engine/lab/twins.py engine/tests/test_lab_repeat_refusal.py .claude/skills/sera-the-explorer/SKILL.md .claude/skills/explore-and-experiment-new-method/SKILL.md .claude/skills/verify-seer/features/lab-cli.md CLAUDE.md`.
Message: `lab: idea lists the controls neighbours already hold; children cite a recorded control, not re-run it`.
Then land on `main` and push (no lab row, no `lab stage`).
