# Four insights, written and not journalled

Phase 8 measured and wrote these; it did not run `lab insight`. `insights` carries append-only
triggers on update and delete, and writing a row here would have moved `lab.sqlite` past the
snapshot the coordinator had already staged on `main`, turning
`test_the_committed_snapshot_is_the_export_of_the_committed_database` red with no `lab stage`
available to this phase to repair it. The reversible option was to write the bodies and hand them
over.

**Run them after the merge and BEFORE the final `lab stage`** — `lab stage` must then run once
more to pick the four rows up, which is what the snapshot test enforces.

Rules that are not optional (memory `seer-lab-note-double-append-from-grep-exit-code`): **no
pipe**, redirect stdout to a capture file, echo `$?` on its own line, and read the new row's id
back from that file. `_insight` prints the new id and nothing else. **Never re-run an insight
whose capture holds an integer** — if a capture holds an integer *and* a non-zero exit, read the
journal before deciding, because the row went in.

```bash
MAIN=/home/miftah/seer
PY=$MAIN/engine/.venv/bin/python
CAP=/tmp/honest-control; mkdir -p "$CAP"
export SEER_LAB_DB=$MAIN/lab/lab.sqlite
D=$MAIN/.workflows/plan/honest-control-redraw/insights   # after the merge

PYTHONPATH=$MAIN/engine/src "$PY" -m seer_engine lab insight --kind observation \
  --title "An under-trading control is a cheaper strategy, not a shape-matched one" \
  --file "$D/A-family.txt" > "$CAP/29-insight-A.txt" 2>&1; echo "exit=$?" >> "$CAP/29-insight-A.txt"

PYTHONPATH=$MAIN/engine/src "$PY" -m seer_engine lab insight --kind observation \
  --title "An over-trading control's handicap is arbitrary, not a fee drag of known sign" \
  --file "$D/B-family.txt" > "$CAP/30-insight-B.txt" 2>&1; echo "exit=$?" >> "$CAP/30-insight-B.txt"

PYTHONPATH=$MAIN/engine/src "$PY" -m seer_engine lab insight --kind synthesis \
  --title "D17 now supersedes: an honest control retires the handicapped one it replaced" \
  --file "$D/D17-supersede.txt" > "$CAP/31-insight-D17.txt" 2>&1; echo "exit=$?" >> "$CAP/31-insight-D17.txt"

PYTHONPATH=$MAIN/engine/src "$PY" -m seer_engine lab insight --kind observation \
  --title "A derived churn beats a hand-chosen re-key period, at both poles at once" \
  --file "$D/matched-draw.txt" > "$CAP/32-insight-draw.txt" 2>&1; echo "exit=$?" >> "$CAP/32-insight-draw.txt"

# then verify exactly four new rows, no duplicate title, and re-stage
sqlite3 "file:$SEER_LAB_DB?mode=ro" \
  "SELECT id, kind, title FROM insights WHERE id > 470 ORDER BY id;"
PYTHONPATH=$MAIN/engine/src "$PY" -m seer_engine lab stage
```

**Insight 2's title changed from the phase-8 plan's.** The plan proposed *"An over-trading control
over-pays its fees, and the lead it concedes is fee drag"* — which is the crossover claim the
close-out tested and did **not** support. The title above states what the thirteen arms actually
show. ⚖ Rung 1: invariant 4 and design §4 — a measurement is reported as it landed, and a
pre-registered title that the measurement refutes is not published as if it held.
