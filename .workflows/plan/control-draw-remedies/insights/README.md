# The insights this set journalled, and the exact form that was run

`insights` carries append-only triggers on UPDATE and DELETE (`insights_no_update`,
`insights_no_delete`). **A retried append is permanent.** So: no pipe, redirect stdout to a
capture file, echo `$?` on its own line, and read the new row's id back from that file.
`_insight` prints the new id and nothing else.

**Never re-run an insight whose capture holds an integer** — if a capture holds an integer *and* a
non-zero exit, the row went in; read the journal before deciding anything.

`--dry-run` does **not** protect `lab insight`: only `lab test` and `lab gate-probe` read
`args.dry_run`; `_insight` commits inside `with conn:` regardless. All six below were rehearsed
first against `cp lab/lab.sqlite $CAP/rehearse.sqlite` with `SEER_LAB_DB` pointed at the copy, and
the live `git hash-object lab/lab.sqlite` was confirmed unmoved by the rehearsal.

Run on 2026-10-20 against `lab/lab.sqlite` at `5a4011f1950871364a77cd3744849b0769865cd0`,
one command per shell call. Each exited **0** and printed its id.

| file | kind | id |
|---|---|---|
| `01-matched-control-not-neutral.txt` | synthesis | **479** |
| `02-two-rules-two-axes.txt` | synthesis | **480** |
| `03-margin-of-unknown-sign.txt` | observation | **481** |
| `04-cross-store-ratio.txt` | observation | **482** |
| `05-held-set-shadow.txt` | observation | **483** |
| `06-guards-that-carry-no-information.txt` | risk | **484** |

```bash
MAIN=/home/miftah/seer
PY=$MAIN/engine/.venv/bin/python
SRC=$MAIN/engine/src
CAP=/tmp/control-draw-remedies; mkdir -p "$CAP"
export SEER_LAB_DB=$MAIN/lab/lab.sqlite
D=$MAIN/.workflows/plan/control-draw-remedies/insights

# one of these per shell call -- never two in one command
PYTHONPATH=$SRC "$PY" -m seer_engine lab insight --kind synthesis \
  --title "A control matched on trades and turnover is still not return-neutral: it re-balances monthly and the book it controls never trims" \
  --file "$D/01-matched-control-not-neutral.txt" > "$CAP/50-insight-1.txt" 2>&1
echo "exit=$?" >> "$CAP/50-insight-1.txt"; cat "$CAP/50-insight-1.txt"

# ... 02 synthesis, 03 observation, 04 observation, 05 observation, 06 risk, each the same shape

# then verify, and only then stage
sqlite3 "file:$SEER_LAB_DB?mode=ro" -header \
  "SELECT id, kind, title FROM insights WHERE id > 478 ORDER BY id;"
sqlite3 "file:$SEER_LAB_DB?mode=ro" -noheader \
  "SELECT count(*), count(DISTINCT title) FROM insights WHERE id > 478;"   # must read 6|6
PYTHONPATH=$SRC "$PY" -m seer_engine lab stage
```

## Why these six and not fewer

Phase 5 journalled nothing deliberately, handing every finding of the set to this phase. The
plan's Creates block budgeted "2 to 4 rows"; the close-out brief named seven distinct findings.
Six rows was the grouping that buried none of them — the three process findings share one row
because they are the same shape (a check that carries no information), and the gate's clause order
is in that row for the same reason rather than in a fourth.

## Near-duplicates checked before writing

Rows 471–474 journal the honest-control set's findings and 475–478 journal M0261's. Row **472**
("An over-trading control's handicap is arbitrary, not a fee drag of known sign") is the closest
neighbour to **481**, and 481 **confirms and extends it rather than superseding it**: 472 was drawn
from thirteen arms on the *over*-trading side, and 481 is a fourteenth on the *under*-trading side
where the prediction was pre-registered and then scored against. Row **473** ("D17 now supersedes")
is about supersession, not about the gate's clause order, so **484** does not overlap it. A body
search for `store_fingerprint`, `entrant`, `weight vector`, `fold majority` and `short-circuit`
across every existing row returned nothing on the cross-store, weight-vector or clause-order
findings. No row written here supersedes any earlier row.
