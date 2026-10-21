# Phase 1 — Re-read the catalogue and correct the journal

**Plan index:** `docs/plans/READ_BACK_CATALOGUE_THROUGH_TIMING_PLAN.md`
**Analysis:** `docs/analyzer/20261021-090230-A7K2_code_analyzer.md`
**Satisfies:** R1, R2, R3, R4
**Depends on:** —
**Status:** executed 2026-10-21 in the planning session

---

## What this phase does

Reads recorded rows with `lab timing`, appends three journal entries — two of them superseding a
row a later row had already made wrong — regenerates the web snapshot, and commits. It changes no
source file and runs no experiment.

## Step 1 — anchor the freeze before anything is written

    cd /home/miftah/seer
    cp lab/lab.sqlite "$SCRATCH/lab.baseline.sqlite"

Then the anchored digest, by the runbook's recipe verbatim
(`docs/runbooks/journal-content-digest.md` — `str(f).encode()`, `\x1f` after every field,
`\x1e` after every row, bounded at `id <= 500`):

    engine/.venv/bin/python - <<'PY'
    import sqlite3, hashlib
    c = sqlite3.connect("file:lab/lab.sqlite?mode=ro", uri=True)
    rows = c.execute(
        "select id,kind,title,body,method_id,added from insights where id<=500 order by id"
    ).fetchall()
    h = hashlib.sha256()
    for r in rows:
        for f in r:
            h.update(b"\x00" if f is None else str(f).encode())
            h.update(b"\x1f")
        h.update(b"\x1e")
    print(h.hexdigest())
    PY

Expected, before and after: `04af46875bef3498f783a3154265b760cd2c4471d018a740d82e0113721673ed`.

## Step 2 — the sweep and the targeted reads (report only)

    engine/.venv/bin/python -m seer_engine lab timing --all --limit 40 --csv "$SCRATCH/timing_all.csv"

Then, for the four methods carrying M0267's shape:

    for a in M0054-ALWAYS-IN M0054-PARK-SPY M0176-BIG M0110-DP20-UP M0201-Y20-MV10-PLC2; do
        engine/.venv/bin/python -m seer_engine lab timing "$a"
    done

And the seven gate/no-gate pairs, which is what separates the safety rule from the picking:

    engine/.venv/bin/python -m seer_engine lab timing M0030-SAT100       --against M0030-SAT100-NOGATE
    engine/.venv/bin/python -m seer_engine lab timing M0054-PARK-SPY     --against M0054-ALWAYS-IN
    engine/.venv/bin/python -m seer_engine lab timing M0203-TF-N20       --against M0203-TF-N20-NOSW
    engine/.venv/bin/python -m seer_engine lab timing M0130-P20-GATE     --against M0130-P20
    engine/.venv/bin/python -m seer_engine lab timing M0080-ANN-S200-T   --against M0080-ANN-S200
    engine/.venv/bin/python -m seer_engine lab timing M0222-TILT2-T      --against M0222-TILT2
    engine/.venv/bin/python -m seer_engine lab timing M0201-Y20-MV10-SW  --against M0201-Y20-MV10

Every one of these is free: no store, no backtest, no journal row, no look. Re-run them at will.

**Do not run `lab survivorship` or `lab costs` anywhere in this phase.** Both journal on every
invocation into an append-only table, and insight 500 is a permanent duplicate of 499 from exactly
that mistake.

## Step 3 — check each reversal's verdict against the money, not against the paper column

    engine/.venv/bin/python - <<'PY'
    import sqlite3
    c = sqlite3.connect("file:lab/lab.sqlite?mode=ro", uri=True); c.row_factory = sqlite3.Row
    for mid in ["M0203","M0125","M0080","M0130","M0201","M0172","M0222"]:
        print("===", mid)
        for t in c.execute(
            "select t.candidate_id, f.mwr, f.spy_tr_mwr from trials t "
            "left join trial_funding f on f.trial_n = t.n "
            "where t.method_id = ? order by t.n", (mid,)
        ):
            m = t["mwr"]
            print("  ", t["candidate_id"], "n/a" if m is None else round(m * 100, 3))
    PY

The claim being tested is narrow: does the recorded verdict assert a positive result **about the
arm that lost money**? It does not, in any of the eight — the detail is in the analysis document,
Finding 1. The expected outcome of this step is therefore **no supersede**, and recording that
clearly is the deliverable.

## Step 4 — write the three entries

Bodies go in files, never inline: a body carrying a backtick or a dollar sign breaks a heredoc, and
a piped `lab insight` hides its exit code, which is how a retried command once double-appended.
Run each one unpiped and read its exit status.

    engine/.venv/bin/python -m seer_engine lab insight \
        --kind observation --method M0201 --supersedes 397 \
        --title "Correcting ourselves: sized by company size the bond-like picks kept their edge, and the random books we judged them against were the problem" \
        --file "$SCRATCH/entryA.txt"

    engine/.venv/bin/python -m seer_engine lab insight \
        --kind observation --method M0267 --supersedes 515 \
        --title "Correcting ourselves: it was this one rule's cheap form that paid early, not crash rules in general" \
        --file "$SCRATCH/entryB.txt"

    engine/.venv/bin/python -m seer_engine lab insight \
        --kind observation \
        --title "The lab measures every result two ways, and on thirty of them the two disagree about who won" \
        --file "$SCRATCH/entryC.txt"

`--method` must match the predecessor's `method_id` or `_check_supersedes` refuses with exit 2:
397 is M0201, 515 is M0267, and the third entry is lab-wide and supersedes nothing.

## Step 5 — prove nothing moved

Re-run Step 1's digest, and widen it to every table a write could have touched. Compare the live
database against the baseline copy, excluding only `insights.supersedes`, which is the one column
the triggers permit to move once:

    engine/.venv/bin/python - <<'PY'
    import sqlite3, hashlib
    def dig(path, sql):
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        h = hashlib.sha256()
        for r in c.execute(sql):
            for f in r:
                h.update(b"\x00" if f is None else str(f).encode()); h.update(b"\x1f")
            h.update(b"\x1e")
        return h.hexdigest()
    checks = {
        "trials": "select * from trials order by n",
        "trial_funding": "select * from trial_funding order by trial_n",
        "trial_moments": "select * from trial_moments order by trial_n",
        "methods": "select * from methods order by id",
        "method_folds": "select * from method_folds order by method_id, seq",
        "insights<=519": "select id,kind,title,body,method_id,added,doc_key from insights "
                         "where id<=519 order by id",
    }
    for name, sql in checks.items():
        a = dig("$SCRATCH/lab.baseline.sqlite", sql)
        b = dig("lab/lab.sqlite", sql)
        print(name, "UNCHANGED" if a == b else "*** MOVED ***")
    PY

And the two counts the brief pins: `trials` at 891 rows, `window='test'` at 4.

## Step 6 — stage, then test, then commit by index

Order matters: `test_lab_snapshot` is red by design until `lab stage` regenerates the JSON, so
testing first reads like a broken frozen record.

    PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab stage
    engine/.venv/bin/python -m pytest engine/tests -q

Then the commit. The message goes in a file — backticks in a heredoc break the shell — and the
commit takes the index, never a pathspec, because a pathspec re-reads the working tree and defeats
`lab stage`:

    git add docs/analyzer/... docs/plans/... .workflows/plan/...
    git commit -F "$SCRATCH/commit-msg.txt"
    git push

On a rejected push: fetch and **merge**, never rebase — a rebase replays a stale `lab.sqlite` over
the live one.

## Exit criteria

- insight rows 520, 521, 522 exist; `520 -> 397` and `521 -> 515` are linked
- the anchored digest is unchanged; all six table digests read UNCHANGED
- `trials` = 891, test-window looks = 4, no new method id
- `lab stage` has run and `web/data/lab.json` agrees with the database row for row
- `pytest engine/tests` green
- one commit on `main`, pushed
