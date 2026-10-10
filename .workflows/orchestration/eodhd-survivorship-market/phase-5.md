# Phase 5: Run the measurement, journal the answer, update the skills

**Plan set:** `EODHD_SURVIVORSHIP_MARKET_PLAN.md`
**Analysis:** `20261010-181548-E7HD_code_analyzer.md`
**Satisfies:** R5 (run the check on the roster, the near misses and the dividend-date methods, the
long-term-losers method first), R6 (a plain-words insight on how much survivorship flattered
results), R7 (the gate half: decide whether the gate uses the store, which is Decision D1), R8 (the
survivorship-check store's `market_series.csv`, written after the final rebuild, Decision D9)
**Depends on:** Phase 2 (alias fill, final SV store contents), Phase 3 (`market_series --refresh`,
run in Step 2), Phase 4 (`lab survivorship`). Phase 1's code is on the branch through all three; the dev store does **not** carry
`market_series.csv` yet (post-landing L1, Decision D8), and this phase adds it to the SV store after
its final rebuild (Decision D9).
**Difficulty:** NORMAL
**Package:** operational. It writes the lab DB through `SEER_LAB_DB`, plus `docs/lab/survivorship/`
and `.claude/skills/`. No engine code changes.

---

## Goal

Every method on the handover's list has been re-run on the survivorship-check store, starting with
the long-term-losers method, and every dividend-date method that has dev trials has too. Each has
a journaled observation and a row in a committed, derived grid under `docs/lab/survivorship/`. One
plain-words `synthesis` insight tells the owner how much the missing dead companies flattered the
lab's results. It also records the gate decision (D1: cross-check only). The explore and sync
skills name the new store and command. N and the test looks are unchanged by anything this phase
did.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `docs/lab/survivorship/grid.csv`: the full `lab survivorship --csv` grid of the three batches,
  concatenated (derived metrics only, no price rows).
- `docs/lab/survivorship/README.md`: plain-words summary, per-year coverage table, cleaning and
  alias counts, and the per-kind change table.
- `docs/lab/survivorship/insight.md`: the exact text journaled as the synthesis insight.
- One `synthesis` insight row and one `observation` row per measured method in
  `/home/miftah/seer/lab/lab.sqlite`. Phase 4's command writes the observations.
- Run helpers **outside the repo** in `/home/miftah/.cache/seer-sv-run/` (`guard.py`,
  `pick_methods.py`, `run_batches.sh`, `combine.py`, `summarize.py`, logs). They are never committed.

**Signature changes:** none.
**Edits (docs only):**
- `.claude/skills/explore-and-experiment-new-method/SKILL.md:225` and a new bullet after `:237`
  (Promotion step 0b); `:67-70` (market series in "Testable?") and the command block at `:340-346`
  (`lab survivorship`, `lab unblock`).
- `.claude/skills/sync-research-store/SKILL.md:101-107` (a new bullet in "What this does NOT sync").
- `docs/plans/HANDOVER_20261010-eodhd.md:8` (a "Done" line).
- `sync_store.py` is **not** changed. Its `store_dir` (`sync_store.py:66`) is hard-wired to
  `engine/.research`, so the SV store can never be pushed by accident and needs no flag.

**Requires (from earlier phases):**
- Phase 1: `python -m seer_engine survivorship_store --build --out DIR --source DIR --cache DIR`
  and `--report`. The build is cache-only, deterministic, copies `fundamentals.csv` (and any other
  optional file the source manifest lists) byte for byte, **re-matches** `dividend_announcements.csv`
  over the merged dividends (so its bytes differ from the dev store's), and writes manifest key
  `purpose: "survivorship-check"`. It also writes `cleaning_report.csv` and `coverage_report.txt`
  inside the store. `research.load_store(sv)` returns `ResearchData.purpose == "survivorship-check"`.
- Phase 2: `--build` offers the fetched `engine/.cache/eodhd/alias/*.json` series by default (no
  flag; `--no-aliases` turns it off) and writes `alias_report.csv` into the store.
- Phase 3: `python -m seer_engine market_series --refresh --store DIR --cache DIR` (cache only;
  keeps the price fingerprint and the SV store's `purpose`). The dev store is **not** refreshed
  before landing (D8): its manifest still reads `fd2bc190…`, price fingerprint `5451195f…`.
- Phase 4: `python -m seer_engine lab survivorship M… [--store DIR] [--sv-store DIR] [--no-journal]
  [--csv PATH]`. It accepts several method ids in one call and loads each store once per call. It
  journals one `observation` per method with `method_id` set, and writes **one** CSV for all
  named methods. It prints N and test looks before and after, and exits 0 on success.
  **CSV shape (phase 4's `CSV_HEADER`, long, one row per variant per store):** `method_id`,
  `candidate_id`, `store` (`dev` | `survivorship`), `reproduced` (`1`/`0` on dev rows, empty on
  survivorship rows), `yearly_return` (money-weighted when funded, else CAGR), `spy_yearly_return`,
  `max_drawdown`, `profit_factor`, `era_edge`, `wf_won`, `wf_scored`, among others. Returns and
  falls are fractions. `combine.py`'s `METHOD_COL` and `summarize.py`'s `COL` below use these names.

**Leaves alone (owned by others):** engine source and tests (phases 1-4); method files;
`lab/hardgate.py` rules (D1); `engine/.research` (read only); `engine/.cache/eodhd` (read only;
phase 2 owns alias fetches). Network is not used in this phase.

## Files

| File | Action | What changes |
|---|---|---|
| `/home/miftah/seer/engine/.research-sv/` (not in git) | rebuild + refresh | final offline rebuild (alias series included), then `market_series --refresh` |
| `/home/miftah/seer/lab/lab.sqlite` (main checkout) | append | ≈23 `observation` rows (phase 4's command) + 1 `synthesis` row; no trial rows |
| `docs/lab/survivorship/grid.csv` | create | concatenated derived grid |
| `docs/lab/survivorship/README.md` | create | plain-words results page with coverage table |
| `docs/lab/survivorship/insight.md` | create | the journaled synthesis text |
| `.claude/skills/explore-and-experiment-new-method/SKILL.md` | modify | `:225` "three" → "four"; new `lab survivorship` bullet after `:237`; market series in "Testable?" (`:67-70`); `lab survivorship` / `lab unblock` in the command block (`:340-346`) |
| `.claude/skills/sync-research-store/SKILL.md` | modify | new bullet after `:107` |
| `docs/plans/HANDOVER_20261010-eodhd.md` | modify | "Done" line after `:8` |
| `web/data/lab.json` + `lab/lab.sqlite` in the **main checkout, on `main`** | stage + commit (conditional, D6) | only via `lab stage`, only if no `sera-*` window is alive |

---

## Implementation Steps

All commands assume:

```bash
WT=/home/miftah/.worktrees/seer/eodhd-survivorship-market
MAIN=/home/miftah/seer
RUN=/home/miftah/.cache/seer-sv-run
export SEER_LAB_DB=$MAIN/lab/lab.sqlite
unset SEER_RESEARCH_STORE      # every lab command below passes --store explicitly
```

The shell does not keep variables between Bash calls, so repeat these lines in each call. Call
Python as `$WT/engine/.venv/bin/python` (the worktree's own venv, which runs the worktree's code).
Never use `$MAIN/engine/.venv` for anything that imports the new modules.

### Step 0: Environment, freshness and preconditions
**File:** none (environment)
**Change:**

1. Branch and earlier phases present:
   ```bash
   cd $WT && git branch --show-current          # feature/eodhd-survivorship-market
   git status --porcelain                        # nothing staged or modified (untracked symlinks are OK)
   $WT/engine/.venv/bin/python -m seer_engine survivorship_store --help >/dev/null && echo store-ok
   $WT/engine/.venv/bin/python -m seer_engine lab survivorship --help        # read the real flags and --csv columns
   ```
   If `lab survivorship --help` shows different flag names than `--store/--sv-store/--csv/--no-journal`,
   change only the flag names in `run_batches.sh` (Step 3).
2. Phase 1 Step 0's environment recipe, idempotent (venv, read-only symlinks, their exclude lines):
   ```bash
   cd $WT
   [ -x engine/.venv/bin/python ] || { /home/miftah/.pyenv/versions/3.11.0/bin/python -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'; }
   [ -e engine/.research ] || ln -s $MAIN/engine/.research engine/.research
   [ -e engine/.cache ]    || ln -s $MAIN/engine/.cache    engine/.cache
   EXCL=$(git rev-parse --git-path info/exclude)
   for p in engine/.cache engine/.research; do grep -qxF "$p" "$EXCL" || echo "$p" >> "$EXCL"; done
   ```
   Do **not** symlink `engine/.research-sv` (Invariant 4). Stage explicit paths only; never
   `git add -A` or `git add .` in this phase. `SEER_LAB_DB` is set (above): this is the only phase
   that writes lab rows before landing (Invariant 5).
3. Bring the feature branch up to date with `main`, so `lab.method.discover` (which imports method
   files from the worktree's own tree) sees methods committed after the base, and the skill text is
   current before it is edited. **Safe for an unattended run:** only trivial conflicts are resolved
   (plan files: ours; the lab DB and its snapshot, which the branch never writes: theirs); any other
   conflict aborts the merge and the phase continues on the branch as it is. Never ask.
   ```bash
   cd $WT && git fetch origin
   if git merge --no-edit origin/main; then
     echo "MERGED"
   elif git rev-parse -q --verify MERGE_HEAD >/dev/null; then
     for f in $(git diff --name-only --diff-filter=U); do
       case "$f" in
         .workflows/*|*_PLAN.md|*_code_analyzer.md) git checkout --ours -- "$f" && git add "$f" ;;
         lab/lab.sqlite|web/data/lab.json)           git checkout --theirs -- "$f" && git add "$f" ;;
         *) echo "non-trivial conflict: $f" ;;
       esac
     done
     if [ -z "$(git diff --name-only --diff-filter=U)" ]; then git commit --no-edit && echo "MERGED (trivial conflicts resolved)"
     else git merge --abort && echo "MERGE ABORTED: non-trivial conflict; continuing without it"; fi
   else
     echo "MERGE NOT STARTED (e.g. an untracked file in the way); continuing without it"
   fi
   ```
   After a merge, rerun the full test suite (Step 12's command) before going on; if it fails,
   `git reset --hard ORIG_HEAD` (the merge commit is the only thing undone) and continue without
   the merge. Without the merge, `pick_methods.py` warns about any roster method missing from this
   tree and the dividend-date list holds only what the branch has; put that in the completion
   note. The coordinator's landing merges `main` in either way.
4. Create the run directory: `mkdir -p $RUN`.

**Impact:** none on any store or the DB.

### Step 1: Write the run helpers (outside the repo)
**File:** `/home/miftah/.cache/seer-sv-run/pick_methods.py` (new, not committed)
**Change:** reads the lab DB **read-only** and lists the dividend-date methods to measure.
**Code:**
```python
"""Which dividend-date methods phase 5 measures, decided at run time. Read only.

A dividend-date method is any committed method file with at least one candidate whose allocator
reads ``Market.dividends`` (``runner.market_aware_candidates(method, "dividends")``) and at least
one recorded dev trial. The handover's roster list is measured separately and excluded here.
Prints the ids space-separated on stdout; warnings go to stderr.
"""

from __future__ import annotations

import sqlite3
import sys

from seer_engine.lab import runner
from seer_engine.lab.method import discover

DB = "file:/home/miftah/seer/lab/lab.sqlite?mode=ro"
ROSTER = (
    "M0069", "M0007", "M0011", "M0019", "M0020", "M0021", "M0022",
    "M0029", "M0032", "M0033", "M0063", "M0070",
)


def dev_trials(conn: sqlite3.Connection, method_id: str) -> int:
    return int(conn.execute(
        "SELECT count(*) FROM trials WHERE window = 'dev' AND method_id = ?", (method_id,)
    ).fetchone()[0])


def main() -> int:
    conn = sqlite3.connect(DB, uri=True)
    methods = discover()
    for mid in ROSTER:
        if mid not in methods:
            print(f"WARNING: roster method {mid} has no method file in this tree", file=sys.stderr)
        elif dev_trials(conn, mid) == 0:
            print(f"WARNING: roster method {mid} has no dev trial", file=sys.stderr)
    picked = []
    for mid, (method, _path) in methods.items():
        if mid in ROSTER or not runner.market_aware_candidates(method, "dividends"):
            continue
        if dev_trials(conn, mid) > 0:
            picked.append(mid)
        else:
            print(f"skip {mid}: reads dividends but has no dev trial yet", file=sys.stderr)
    print(" ".join(picked))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**File:** `/home/miftah/.cache/seer-sv-run/guard.py` (new, not committed)
**Change:** takes a snapshot of both stores' identities and the lab's counts, and compares two
snapshots. It is the proof for Invariants 1 and 3 across the whole phase. The Sera batch may add
trials for *other* methods while this phase runs. The guard reports those, and only fails on rows
that could have come from this phase.
**Code:**
```python
"""Phase-5 guard: snapshot the stores' identities and the lab's counts, then compare.

    guard.py snap OUT.json METHOD...     write a snapshot
    guard.py check BEFORE.json METHOD... compare the present against BEFORE; exit 1 on a violation

Read only. Fails when: the dev store's manifest changed; its price fingerprint is not 5451195f...;
any measured method gained or lost a dev trial or changed status; any trial recorded after BEFORE
belongs to a measured method or was measured on the survivorship-check store; any trial_moments /
trial_funding / trial_provenance row count changed for trials that existed at BEFORE.
New trials of other methods (a live Sera batch) are reported, not failed.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from seer_engine import research

DEV = Path("/home/miftah/seer/engine/.research")
SV = Path("/home/miftah/seer/engine/.research-sv")
DB = "file:/home/miftah/seer/lab/lab.sqlite?mode=ro"
DEV_PRICE_FP = "5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a"


def store_identity(path: Path) -> dict | None:
    manifest = path / "manifest.json"
    if not manifest.is_file():
        return None
    m = json.loads(manifest.read_text(encoding="utf-8"))
    return {
        "fingerprint": m["fingerprint"],
        "files": m["files"],
        "price_fingerprint": research.price_fingerprint_of(m["files"]),
        "purpose": m.get("purpose"),
    }


def one(conn: sqlite3.Connection, sql: str, args: tuple = ()) -> int:
    return int(conn.execute(sql, args).fetchone()[0] or 0)


def snapshot(methods: list[str]) -> dict:
    conn = sqlite3.connect(DB, uri=True)
    max_n = one(conn, "SELECT max(n) FROM trials")
    per_method = {}
    for mid in methods:
        row = conn.execute("SELECT status FROM methods WHERE id = ?", (mid,)).fetchone()
        per_method[mid] = {
            "dev_trials": one(conn, "SELECT count(*) FROM trials WHERE window='dev' AND method_id=?", (mid,)),
            "status": row[0] if row else None,
        }
    return {
        "dev": store_identity(DEV),
        "sv": store_identity(SV),
        "n": one(conn, "SELECT count(*) FROM trials WHERE window='dev'"),
        "looks": one(conn, "SELECT count(*) FROM trials WHERE window='test'"),
        "max_n": max_n,
        "max_insight": one(conn, "SELECT max(id) FROM insights"),
        "moments": one(conn, "SELECT count(*) FROM trial_moments WHERE trial_n <= ?", (max_n,)),
        "funding": one(conn, "SELECT count(*) FROM trial_funding WHERE trial_n <= ?", (max_n,)),
        "provenance": one(conn, "SELECT count(*) FROM trial_provenance WHERE trial_n <= ?", (max_n,)),
        "methods": per_method,
    }


def check(before: dict, methods: list[str]) -> int:
    now = snapshot(methods)
    bad: list[str] = []
    if now["dev"] != before["dev"]:
        bad.append(f"dev store manifest changed: {before['dev']} -> {now['dev']}")
    if now["dev"] is None or now["dev"]["price_fingerprint"] != DEV_PRICE_FP:
        bad.append("dev store price fingerprint is not 5451195f...")
    for mid in methods:
        if mid in before["methods"] and now["methods"][mid] != before["methods"][mid]:
            bad.append(f"{mid} changed: {before['methods'][mid]} -> {now['methods'][mid]}")
    conn = sqlite3.connect(DB, uri=True)
    for key, table in (("moments", "trial_moments"), ("funding", "trial_funding"),
                       ("provenance", "trial_provenance")):
        count = one(conn, f"SELECT count(*) FROM {table} WHERE trial_n <= ?", (before["max_n"],))
        if count != before[key]:
            bad.append(f"{table} rows for pre-existing trials moved {before[key]} -> {count}")
    sv = now["sv"] or {}
    new = conn.execute(
        "SELECT t.n, t.method_id, t.window, t.store_fingerprint, p.price_fingerprint "
        "FROM trials t LEFT JOIN trial_provenance p ON p.trial_n = t.n WHERE t.n > ? ORDER BY t.n",
        (before["max_n"],),
    ).fetchall()
    for n, mid, window, store_fp, price_fp in new:
        if mid in methods:
            bad.append(f"trial {n} ({mid}, {window}) was recorded for a measured method")
        if sv and (store_fp == sv.get("fingerprint") or price_fp == sv.get("price_fingerprint")):
            bad.append(f"trial {n} ({mid}) was measured on the survivorship-check store")
    others = sorted({mid for _n, mid, _w, _s, _p in new if mid not in methods})
    print(f"N {before['n']} -> {now['n']}   test looks {before['looks']} -> {now['looks']}")
    if new:
        print(f"{len(new)} trial(s) recorded meanwhile by other sessions, methods: {', '.join(others)}")
    else:
        print("no trial recorded anywhere since the snapshot")
    obs = conn.execute(
        "SELECT method_id, count(*) FROM insights WHERE id > ? AND kind = 'observation' "
        "GROUP BY method_id ORDER BY method_id", (before["max_insight"],),
    ).fetchall()
    print("observations journaled since the snapshot: " + (", ".join(f"{m}={c}" for m, c in obs) or "none"))
    print(f"sv store: {now['sv']['price_fingerprint'][:8] if now['sv'] else 'missing'}"
          f" (was {before['sv']['price_fingerprint'][:8] if before['sv'] else 'missing'})")
    for line in bad:
        print("VIOLATION: " + line)
    return 1 if bad else 0


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("snap", "check"):
        print(__doc__)
        return 2
    mode, path, methods = argv[0], Path(argv[1]), argv[2:]
    if mode == "snap":
        path.write_text(json.dumps(snapshot(methods), indent=2), encoding="utf-8")
        print(f"wrote {path}")
        return 0
    return check(json.loads(path.read_text(encoding="utf-8")), methods)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

Then decide the list and take the baseline:
```bash
cd $WT && $WT/engine/.venv/bin/python $RUN/pick_methods.py > $RUN/dividend_methods.txt
cat $RUN/dividend_methods.txt
ROSTER="M0069 M0007 M0011 M0019 M0020 M0021 M0022 M0029 M0032 M0033 M0063 M0070"
echo "$ROSTER $(cat $RUN/dividend_methods.txt)" > $RUN/all_methods.txt
$WT/engine/.venv/bin/python $RUN/guard.py snap $RUN/before.json $(cat $RUN/all_methods.txt)
```
Expected `dividend_methods.txt` on today's DB is
`M0051 M0076 M0077 M0078 M0079 M0081 M0082 M0083 M0085 M0086`. M0051, the dividend-month calendar
book, also reads `Market.dividends` and has 5 dev trials, so the rule includes it. That is
deliberate: it is a dividend-date method too. Any later method added by the Sera batch with dev
trials joins automatically. On today's DB the check counts 276 dev trials and 4 test looks.
**Impact:** read only.

### Step 2: Rebuild the survivorship-check store offline
**File:** `/home/miftah/seer/engine/.research-sv/` (not in git)
**Change:** rebuild once more from the dev store with the final code (phase 2's alias series
included by default), then add `market_series.csv` to the check store with phase 3's command (the
dev store does not carry it before landing, D8/D9). First make sure nothing has the store open,
since `_swap_in` moves the directory (a Monitor until-loop if it is busy, never a foreground sleep):
```bash
pgrep -af "lab survivorship|survivorship_store|market_series" && echo "WAIT: something is using the SV store" \
  || echo clear
cd $WT && $WT/engine/.venv/bin/python -m seer_engine survivorship_store --build \
  --out /home/miftah/seer/engine/.research-sv \
  --source /home/miftah/seer/engine/.research \
  --cache /home/miftah/seer/engine/.cache/eodhd 2>&1 | tee $RUN/build.log
cd $WT && $WT/engine/.venv/bin/python -m seer_engine market_series --refresh \
  --store /home/miftah/seer/engine/.research-sv \
  --cache /home/miftah/seer/engine/.cache/eodhd/market 2>&1 | tee -a $RUN/build.log
#   must print "price fingerprint <sv> (unchanged)" and "purpose survivorship-check"; exit 0
```
Then verify:
```bash
cd $WT && $WT/engine/.venv/bin/python - <<'PY'
import json
from pathlib import Path
from seer_engine import research
dev, sv = Path("/home/miftah/seer/engine/.research"), Path("/home/miftah/seer/engine/.research-sv")
before = json.loads(Path("/home/miftah/.cache/seer-sv-run/before.json").read_text())
dm = json.loads((dev / "manifest.json").read_text())
sm = json.loads((sv / "manifest.json").read_text())
assert dm["fingerprint"] == before["dev"]["fingerprint"], "dev manifest moved"
assert research.price_fingerprint_of(dm["files"]).startswith("5451195f"), "dev price fingerprint moved"
assert sm.get("purpose") == "survivorship-check", sm.get("purpose")
for f in dm["files"]:
    assert f in sm["files"], f"SV store lacks {f}"
assert "market_series.csv" not in dm["files"], "the dev store was refreshed before landing (D8)"
assert "market_series.csv" in sm["files"], "market_series --refresh did not reach the SV store"
assert sm["files"]["fundamentals.csv"] == dm["files"]["fundamentals.csv"], "fundamentals.csv not byte-identical"
# dividend_announcements.csv is re-matched over the merged dividends: present, different bytes
sv_price = research.price_fingerprint_of(sm["files"])
assert not sv_price.startswith("5451195f"), "SV price fingerprint equals the dev store's"
old = before["sv"]["price_fingerprint"] if before["sv"] else None
print("sv price fingerprint", sv_price, "previous", old, "SAME" if old == sv_price else "CHANGED")
for name in ("cleaning_report.csv", "coverage_report.txt", "alias_report.csv"):
    assert (sv / name).is_file(), f"missing {name}"
data = research.load_store(sv)
assert data.purpose == "survivorship-check" and len(data.market.series) == 43317
print("loaded; bars", sm["bar_rows"], "served", sm["symbols_served"], "of", sm["symbols_requested"])
PY
```
If the SV price fingerprint is `CHANGED` relative to phase 2's build, the build is not
deterministic over the same cache and source. That is a phase-1/2 bug: stop, report it, and do
not go on to Step 3 until it is explained. A fix needs a test, per the scope rule.
**Impact:** replaces the SV store directory atomically. The dev store is not written.

### Step 3: Run the long-term-losers method first
**File:** `/home/miftah/.cache/seer-sv-run/run_batches.sh` (new, not committed)
**Code:**
```bash
#!/usr/bin/env bash
# Phase 5 runs of `lab survivorship`. Report only: no trial, N unchanged (guard.py proves it).
# Usage: run_batches.sh first | rest
set -u
WT=/home/miftah/.worktrees/seer/eodhd-survivorship-market
RUN=/home/miftah/.cache/seer-sv-run
PY="$WT/engine/.venv/bin/python"
DEV=/home/miftah/seer/engine/.research
SV=/home/miftah/seer/engine/.research-sv
export SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite
unset SEER_RESEARCH_STORE
cd "$WT" || exit 1

batch() {
  local name=$1
  shift
  echo "== $name start $(date -Is): $*"
  "$PY" -m seer_engine -v lab survivorship "$@" \
    --store "$DEV" --sv-store "$SV" --csv "$RUN/$name.csv" > "$RUN/$name.out" 2>&1
  local rc=$?
  echo "== $name exit $rc $(date -Is)"
  return $rc
}

case "${1:-}" in
  first)
    batch m0069 M0069
    ;;
  rest)
    batch roster M0007 M0011 M0019 M0020 M0021 M0022 M0029 M0032 M0033 M0063 M0070
    # shellcheck disable=SC2046
    batch dividend $(cat "$RUN/dividend_methods.txt")
    ;;
  *)
    echo "usage: $0 first|rest" >&2
    exit 2
    ;;
esac
echo "== all done $(date -Is)"
```
Launch it detached so a tool timeout cannot kill it, using the Bash tool with
`run_in_background: true`:
```bash
chmod +x /home/miftah/.cache/seer-sv-run/run_batches.sh
nohup /home/miftah/.cache/seer-sv-run/run_batches.sh first > /home/miftah/.cache/seer-sv-run/first.log 2>&1
```
Wait on `grep -q '== all done' $RUN/first.log` with Monitor (an until-loop), never with a
foreground sleep. When it finishes:
- `grep '== m0069 exit' $RUN/first.log` must say `exit 0`.
- Read `$RUN/m0069.out` in full. Every dev row must say the recorded result reproduced. If a
  variant did **not** reproduce, the dev-vs-SV gap for that variant is not interpretable. Record
  it, and decide whether it is a bug: same code and same store should always reproduce. If the
  other variants reproduce and only this one doesn't, it is a phase-4 bug. Fix it in phase 4's
  module with a regression test, commit it on the branch with a message saying the run proved it,
  then rerun `first`.
- Sanity-read the numbers. M0069 buys the biggest long-term losers, so its SV column should hold
  names the dev store never had. If the SV column is identical to dev to the last digit, the
  check store was not actually used. Stop and investigate.
- `$WT/engine/.venv/bin/python $RUN/guard.py check $RUN/before.json $(cat $RUN/all_methods.txt)`
  must exit 0 and list `M0069=1` among the observations.

**Impact:** one `observation` insight for M0069 in the main lab DB. No trial row.

### Step 4: Run the roster, the near misses and the dividend-date methods
**File:** none new
**Change:** launch the second invocation the same way (Bash `run_in_background: true`):
```bash
nohup /home/miftah/.cache/seer-sv-run/run_batches.sh rest > /home/miftah/.cache/seer-sv-run/rest.log 2>&1
```
Expect a long run: two batches, 22 methods, about 110 variants, each run on both stores. Monitor
`$RUN/rest.log` until `== all done`. Check that:
- `grep '== .* exit' $RUN/rest.log` shows `exit 0` for both `roster` and `dividend`. A nonzero
  batch is rerun **only for the methods missing from its CSV**, under a new batch name such as
  `roster2`, by calling `batch` from a one-off line. It is never rerun whole, because that would
  journal a second observation for methods already done.
- Every method in `$RUN/all_methods.txt` appears in some CSV (Step 5's `combine.py` asserts it).
- The guard passes again, with one observation per method:
  `$WT/engine/.venv/bin/python $RUN/guard.py check $RUN/before.json $(cat $RUN/all_methods.txt)`.

**Impact:** about 21 more `observation` insights. No trial row, no status change.

### Step 5: Combine the grid into the repo
**File:** `/home/miftah/.cache/seer-sv-run/combine.py` (new, not committed) → writes
`docs/lab/survivorship/grid.csv`
**Code:**
```python
"""Concatenate the batch CSVs into docs/lab/survivorship/grid.csv (one header), in run order,
and assert every measured method has rows. Derived metrics only; never a price row."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

RUN = Path("/home/miftah/.cache/seer-sv-run")
OUT = Path("/home/miftah/.worktrees/seer/eodhd-survivorship-market/docs/lab/survivorship/grid.csv")
BATCHES = ("m0069", "roster", "roster2", "dividend", "dividend2")
METHOD_COL = "method_id"  # phase 4's CSV_HEADER


def main() -> int:
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    for name in BATCHES:
        path = RUN / f"{name}.csv"
        if not path.is_file():
            continue
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if header is None:
                header = list(reader.fieldnames or [])
            elif list(reader.fieldnames or []) != header:
                print(f"{path}: header differs from the first batch's", file=sys.stderr)
                return 1
            rows.extend(reader)
    if header is None:
        print("no batch CSV found", file=sys.stderr)
        return 1
    wanted = (RUN / "all_methods.txt").read_text(encoding="utf-8").split()
    have = {r[METHOD_COL] for r in rows}
    missing = [m for m in wanted if m not in have]
    if missing:
        print(f"methods with no row: {' '.join(missing)}", file=sys.stderr)
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {OUT}: {len(rows)} rows, {len(have)} methods")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```
Run: `$WT/engine/.venv/bin/python $RUN/combine.py`. Then confirm the grid holds no raw vendor
data: `head -3 $WT/docs/lab/survivorship/grid.csv` must show metric columns only, with no `date`,
`open` or `close` columns.
**Impact:** new derived file on the branch.

### Step 6: Summarize the per-kind change
**File:** `/home/miftah/.cache/seer-sv-run/summarize.py` (new, not committed)
**Change:** turns the grid and the store's reports into the numbers the README and the insight
quote. The drawdown bar comes from the code (`metrics.MAX_DRAWDOWN = 0.20`), not from memory.
**Code:**
```python
"""Numbers for docs/lab/survivorship/README.md and the synthesis insight. Read only.

Reads docs/lab/survivorship/grid.csv (long format: one row per variant per store, phase 4's
CSV_HEADER) and the SV store's cleaning_report.csv, alias_report.csv and coverage_report.txt.
Prints markdown.
"""

from __future__ import annotations

import csv
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from seer_engine.backtest.metrics import MAX_DRAWDOWN

GRID = Path("/home/miftah/.worktrees/seer/eodhd-survivorship-market/docs/lab/survivorship/grid.csv")
SV = Path("/home/miftah/seer/engine/.research-sv")
COL = {  # phase 4's survivorship_check.CSV_HEADER names
    "method": "method_id", "variant": "candidate_id", "store": "store", "reproduced": "reproduced",
    "cagr": "yearly_return", "spy": "spy_yearly_return", "dd": "max_drawdown", "pf": "profit_factor",
    "era": "era_edge", "won": "wf_won", "scored": "wf_scored",
}
DEV, SVS = "dev", "survivorship"  # survivorship_check.DEV_LABEL, SV_LABEL
KIND = {
    "M0007": "momentum book", "M0011": "momentum book", "M0019": "momentum book",
    "M0020": "momentum book", "M0022": "momentum book", "M0032": "momentum book",
    "M0033": "momentum book",
    "M0021": "momentum + calm-stock blend", "M0029": "momentum + calm-stock blend",
    "M0069": "buying long-term losers",
    "M0063": "earnings-jump book",
}
DEFAULT_KIND = "dividend-date methods"  # M0051, M0070, M0076-M0086 and any later one
KIND_ORDER = ("buying long-term losers", "momentum book", "momentum + calm-stock blend",
              "earnings-jump book", "dividend-date methods")


def num(row: dict[str, str], key: str) -> float | None:
    text = (row.get(COL[key]) or "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def truthy(text: str | None) -> bool:
    return (text or "").strip().lower() in ("true", "yes", "1", "y")


def pairs() -> list[tuple[str, str, dict[str, str], dict[str, str]]]:
    by: dict[tuple[str, str], dict[str, dict[str, str]]] = defaultdict(dict)
    with GRID.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            by[(row[COL["method"]], row[COL["variant"]])][row[COL["store"]].strip().lower()] = row
    out = []
    for (method, variant), sides in by.items():
        if DEV in sides and SVS in sides:
            out.append((method, variant, sides[DEV], sides[SVS]))
    return out


def beats(row: dict[str, str]) -> bool | None:
    c, s = num(row, "cagr"), num(row, "spy")
    return None if c is None or s is None else c > s


def within_bar(row: dict[str, str]) -> bool | None:
    d = num(row, "dd")
    return None if d is None else abs(d) <= MAX_DRAWDOWN


def sign(x: float | None) -> int | None:
    return None if x is None else (x > 0) - (x < 0)


def pct(x: float) -> str:
    return f"{x * 100:+.1f}"


def kind_table(rows) -> None:
    groups: dict[str, list] = defaultdict(list)
    for item in rows:
        groups[KIND.get(item[0], DEFAULT_KIND)].append(item)
    groups["ALL"] = list(rows)
    print("| kind | methods | variants | not reproduced | CAGR change, mean (pt/yr) | median | worst | best "
          "| beat SPY: dev -> check (lost / gained) | worst fall within 20%: lost / gained "
          "| 2009-15 edge sign flips (+->- / -->+) | worst fall change, mean (pt) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for kind in (*KIND_ORDER, "ALL"):
        items = groups.get(kind, [])
        if not items:
            continue
        deltas, dd_deltas = [], []
        lost = gained = dd_lost = dd_gained = era_down = era_up = unrepro = 0
        beats_dev = beats_sv = 0
        for _m, _v, d, s in items:
            if not truthy(d.get(COL["reproduced"])):
                unrepro += 1
            cd, cs = num(d, "cagr"), num(s, "cagr")
            if cd is not None and cs is not None:
                deltas.append(cs - cd)
            dd_d, dd_s = num(d, "dd"), num(s, "dd")
            if dd_d is not None and dd_s is not None:
                dd_deltas.append(abs(dd_s) - abs(dd_d))
            bd, bs = beats(d), beats(s)
            beats_dev += bool(bd)
            beats_sv += bool(bs)
            lost += bool(bd and bs is False)
            gained += bool(bd is False and bs)
            wd, ws = within_bar(d), within_bar(s)
            dd_lost += bool(wd and ws is False)
            dd_gained += bool(wd is False and ws)
            ed, es = sign(num(d, "era")), sign(num(s, "era"))
            era_down += bool(ed == 1 and es == -1)
            era_up += bool(ed == -1 and es == 1)
        methods = len({m for m, _v, _d, _s in items})
        mean = pct(statistics.fmean(deltas)) if deltas else "n/a"
        med = pct(statistics.median(deltas)) if deltas else "n/a"
        worst = pct(min(deltas)) if deltas else "n/a"
        best = pct(max(deltas)) if deltas else "n/a"
        ddm = pct(statistics.fmean(dd_deltas)) if dd_deltas else "n/a"
        print(f"| {kind} | {methods} | {len(items)} | {unrepro} | {mean} | {med} | {worst} | {best} "
              f"| {beats_dev} -> {beats_sv} ({lost} / {gained}) | {dd_lost} / {dd_gained} "
              f"| {era_down} / {era_up} | {ddm} |")


def method_table(rows) -> None:
    print("\n| method | kind | variant | CAGR dev | CAGR check | SPY | worst fall dev | worst fall check "
          "| 2009-15 edge dev | check | folds dev | folds check | reproduced |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for m, v, d, s in sorted(rows):
        def f(row, key):
            x = num(row, key)
            return "n/a" if x is None else pct(x)
        def folds(row):
            w, n = num(row, "won"), num(row, "scored")
            return "n/a" if w is None or n is None else f"{int(w)}/{int(n)}"
        print(f"| {m} | {KIND.get(m, DEFAULT_KIND)} | {v} | {f(d, 'cagr')} | {f(s, 'cagr')} | {f(d, 'spy')} "
              f"| {f(d, 'dd')} | {f(s, 'dd')} | {f(d, 'era')} | {f(s, 'era')} | {folds(d)} | {folds(s)} "
              f"| {'yes' if truthy(d.get(COL['reproduced'])) else 'NO'} |")


def report_counts() -> None:
    for name in ("cleaning_report.csv", "alias_report.csv"):
        path = SV / name
        if not path.is_file():
            print(f"\n{name}: missing")
            continue
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
            fields = reader.fieldnames or []
        print(f"\n{name}: {len(rows)} rows; columns {', '.join(fields)}")
        for col in ("action", "source", "accepted", "matched_by"):  # cleaning_report / alias_report columns
            if col in fields:
                for value, count in Counter(r[col] for r in rows).most_common():
                    print(f"  {col}={value}: {count}")
    cov = SV / "coverage_report.txt"
    print("\ncoverage_report.txt:\n" + (cov.read_text(encoding="utf-8") if cov.is_file() else "missing"))


def main() -> int:
    rows = pairs()
    print(f"drawdown bar in force: {MAX_DRAWDOWN:.0%}\n")
    kind_table(rows)
    method_table(rows)
    report_counts()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```
Run: `$WT/engine/.venv/bin/python $RUN/summarize.py | tee $RUN/summary.md`.
Folds (`wf_won`/`wf_scored`) are per method and store, repeated on each variant row by phase 4's
`csv_rows`. `reproduced` is `1`/`0` on dev rows (`truthy` reads `1`). The kind table's header
prints "20%" as text; it matches `MAX_DRAWDOWN`, which the first line prints from the code.
**Impact:** read only.

### Step 7: Write `docs/lab/survivorship/README.md`
**File:** `docs/lab/survivorship/README.md` (new)
**Change:** fill every `«…»` from `$RUN/summary.md`, the printed reports and `coverage_report.txt`.
Delete the guidance lines in *italics* once filled. Use derived numbers only, never a price row.
**Code:**
```markdown
# Survivorship check: how much the missing dead companies flattered the lab

*Measured «YYYY-MM-DD». Report only: no trial was recorded, the lab's trial count and its
test-window looks did not move. The grid behind every number here is `grid.csv` in this folder.*

## What was measured

Every lab result was measured on a price history that holds about 59% of the days a company sat
in the S&P 500 or the Nasdaq-100 between 1996 and 2015. Most of what is missing are the companies
that later died: bankruptcies, buyouts and renamed tickers. In October 2026 we bought one month of
EODHD's US price history, cleaned it (split-adjusted; tickers that a different company later reused
were cut to the right company's years; absurd data errors repaired or dropped; real collapses kept),
and built a second copy of the 1996-2015 history with those companies added back. Then every
method below was re-run, variant by variant, on both copies, on the same money and the same
monthly top-ups as its recorded run.

The second copy (the "check" history) lives only on the PC, at `engine/.research-sv`. It is built
offline from the EODHD cache with
`python -m seer_engine survivorship_store --build --out <abs>/engine/.research-sv --source <abs>/engine/.research`.
The raw vendor data is under a personal licence and is never committed.

## How much of the index each history can price

Share of index-member days with a price, by year (from the check store's `coverage_report.txt`):

«paste the per-year table from coverage_report.txt here: year | member-days | dev store covered (%) | check store covered (%)»

- Still missing after the fill: «N» members, worth «M» member-days («p»% of all member-days).
- The alias fill found another code for «a» of the 200 members the first build could not use
  (`alias_report.csv`, `accepted = yes`); «b» had no candidate code at all.
- «39» members the dev store does serve have no price on any of their index days (the code now
  names a later company); they are not repaired here and count as missing.
- Cleaning: «k» series kept as they were, «r» repaired, «t» trimmed to the right company's years,
  «d» dropped (each with its reason in `cleaning_report.csv` inside the store).
- 1996 and 1997 stay thin («x»% and «y»% covered): EODHD's histories for dead companies mostly
  start on 1997-12-31.

## What changed, by kind of method

Change = check history minus dev history, in percentage points a year of funded growth on the
owner's money. The drawdown bar is the lab's «20»%.

«paste the kind table from summary.md»

## Method by method

«paste the method table from summary.md»

## The gate

The check history stays a **cross-check, not a gate** (Decision D1 of
`EODHD_SURVIVORSHIP_MARKET_PLAN.md`). `lab run`, `lab test` and `lab remeasure` refuse it, and the
hard gate in `lab/hardgate.py` never reads it. Making it part of promotion would be a separate,
argued change to the gate, made after reading these numbers. It is not part of this measurement.

## What remains uncertain

- «N» index members still have no usable price history, «names the biggest few by member-days, if
  coverage_report.txt lists them».
- 1996-1997 is still thin, so any edge that lives in those two years is not checked by this.
- «any variant whose dev re-run did not reproduce its recorded result, and why»
```

### Step 8: Write and journal the synthesis insight
**File:** `docs/lab/survivorship/insight.md` (new). Its text is journaled verbatim.
**Change:** fill the template from `$RUN/summary.md`. Rules for the owner, from memory
"plain words for owner": no method ids, variant names, file names, column names, code or backticks;
name methods by what they do; explain every number. Keep it to the facts the numbers support.
Wherever the template offers alternatives `[A | B]`, choose the one the numbers support:
- the mean change across all variants is below −1.0 pt/yr → "flattered … by about X points a year";
- between −1.0 and +1.0 → "barely moved (about X points a year either way)";
- above +1.0 → "if anything, the missing companies made our results look *worse*, by about X".

Remove the bracket markup when filling it in.

**Template:**
```markdown
**The answer: the missing dead companies [flattered our results by about «X» points a year | barely moved our results, about «X» points a year either way | made our results look slightly worse, by about «X» points a year].** Until now every strategy was tested on a price history that was missing about four in ten of the days a company sat in the big US indexes, mostly the companies that later went bankrupt, were bought or disappeared. This month we bought that missing history, cleaned it carefully (real collapses kept in, data errors taken out), and re-ran «V» versions of «M» strategies on both histories with the same money and the same monthly top-ups. Nothing was added to the lab's trial count and no hidden-years look was spent.

**Buying long-term losers was the sharpest test.** This strategy buys the big companies that fell furthest over the past three to five years. If dead companies were hiding anywhere, it would be here, because the worst losers are exactly the ones that went on to die. On the fuller history it earned «a»% a year instead of «b»% (SPY: «s»%), and its worst fall went from «c»% to «d»%. [It still beats SPY | It no longer beats SPY | It still does not beat SPY]. [Its edge in 2009-2015 turned negative | Its 2009-2015 result stayed «sign»].

**The momentum books** («n1» versions) moved by «m1» points a year on average (from «lo1» to «hi1»). «k1» of them stopped beating SPY. [None crossed | «j1» crossed] the 20% worst-fall line.
**The momentum plus calm-stock blends** moved by «m2» points a year; «sentence on beats SPY / worst fall».
**The earnings-jump book** moved by «m3» points a year; «sentence».
**The dividend-date strategies** («n4» versions) moved by «m4» points a year; «sentence». [This confirms | This does not change] the batch's finding that dividend dates add nothing.

**Did any verdict change?** «one sentence per change that matters, in plain words: a strategy that stopped (or started) beating SPY, crossed the 20% worst-fall line, flipped the sign of its 2009-2015 edge, or won a different number of its walk-forward periods. If none changed: "No strategy's verdict changed: every one that beat SPY still does, and none crossed the 20% worst-fall line."»

**How the fuller history looks.** It prices «P»% of the index days instead of 59%. 2009-2015 is now «q»% covered. «R» members are still missing even after we searched for their old ticker codes, so a small part of the hole remains.

**What remains uncertain.** 1996 and 1997 are still thin, because the bought histories for dead companies mostly start on the last day of 1997. Any edge that lives in those two years is not checked. The «R» members still missing are mostly [companies whose ticker a different company now uses | «describe»], so a little survivorship bias is still left in both histories.

**What this changes in how we work.** The fuller history stays a second opinion. It does not decide which strategy may be tried on the hidden years. That rule changes only through a separate, argued change, made after reading these numbers. Every future strategy can be checked against it, and [the next batch should do so before trusting any result built on buying fallen or troubled companies | «what the numbers suggest»].
```

Journal it (main DB via `SEER_LAB_DB`) and record the id it prints:
```bash
cd $WT && SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite $WT/engine/.venv/bin/python -m seer_engine lab insight \
  --kind synthesis \
  --title "Survivorship check: «plain headline, e.g. 'adding back the dead companies cost our strategies about X points a year'»" \
  --file docs/lab/survivorship/insight.md
```
The title carries no ids. `store.add_insight` strips whitespace. Insights are append-only, so
re-read the filled file **before** this command. A mistake afterwards is answered with a
correcting synthesis, as insight 126 did for 125.
**Impact:** one `synthesis` row. Nothing else.

### Step 9: Update the explore skill's Promotion step 0b
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:225` and after `:237`.
Line numbers are those at base `5e5ec5c`; re-locate them by the quoted text after Step 0's merge.

**Edit A, `:225`.** Old:
```
   (insight 58). Before spending a look, run all three. Every one is report only -- no trial, no
```
New:
```
   (insight 58). Before spending a look, run all four. Every one is report only -- no trial, no
```

**Edit B.** Insert after the coverage-script bullet, i.e. after this old text (`:232-237`):
```
   - `engine/.venv/bin/python engine/scripts/survivorship_coverage.py` -- the edge by era of rising
     data coverage. The dev store prices 48% of index members in 1996 and 74% in 2014, and the 522
     it cannot price are disproportionately the companies that died (AABA, AAMRQ...). **A method
     whose edge lives in the low-coverage years and vanishes by 2009-2015 may be reading a hole in
     the data rather than the market.** Three of the four roster strategies were already negative
     in 2009-2015, on dev, years before the test window said so.
```
the new bullet (fill the last sentence from Step 6's numbers):
```
   - `lab survivorship MNNNN` -- the same method re-run on the **survivorship-check store**
     (`engine/.research-sv`): the dev store plus EODHD prices for most of the members the dev
     store cannot price, dead companies included (real collapses kept, data errors cleaned). It
     re-runs every variant with a recorded dev trial, at its recorded capital and funding, on both
     stores and prints them side by side: funded CAGR vs SPY, max DD, PF, the DSR inputs, the
     2009-2015 era and the walk-forward folds. Report only: no trial, no look, N unchanged; it
     journals one plain-words observation per method (`--no-journal` to skip, `--csv PATH` for the
     grid). It answers the coverage script's question directly, where that script can only point
     at it: **an edge that shrinks or flips on the check store was partly the missing dead
     companies.** Read the dev column's "reproduced" first. A dev re-run that does not match the
     recorded trial makes the side-by-side meaningless for that variant. The check store is a
     cross-check, not a gate (`EODHD_SURVIVORSHIP_MARKET_PLAN.md` D1): `lab run`, `lab test` and
     `lab remeasure` refuse it, and `lab promote` never reads it. Making it gate anything is an
     argued commit in `lab/hardgate.py`, like any other rule change. If `engine/.research-sv` is
     missing, build it offline from the EODHD cache, from the main checkout with absolute paths
     and never through a symlink: `engine/.venv/bin/python -m seer_engine survivorship_store
     --build --out "$PWD/engine/.research-sv" --source "$PWD/engine/.research"`.
     `survivorship_store --report` prints its year-by-year coverage. Measured «date» on the roster,
     the near misses and the dividend-date methods: «one sentence: the mean change in funded CAGR
     and which kind of method moved most»; the grid is in `docs/lab/survivorship/`.
```
**Edit C, `:67-70` ("Testable?", phase 3's docs handoff).** Old:
```
   - **Testable?** The store has daily OHLCV for 1993 → 2015-10-16 (~539 stocks plus ETFs,
     no delisted names), cash dividends, and point-in-time S&P 500 / Nasdaq-100 membership. No
     fundamentals, intraday, options, short interest or sentiment. If it isn't testable:
     `lab block <id> --on "<data>"` plus a `data-wish` insight. Solo: choose another idea.
```
New:
```
   - **Testable?** The store has daily OHLCV for 1993 → 2015-10-16 (~539 stocks plus ETFs,
     no delisted names), cash dividends, and point-in-time S&P 500 / Nasdaq-100 membership. No
     fundamentals, intraday, options, short interest or sentiment. Market-wide daily series are
     there too, read point in time through `Market.series` (`value_on(name, data_date)`,
     `upto(name, data_date, last=K)`): VIX, VIX3M (VXV before 2007-11-13), VIX9D, VXN, VVIX in
     index points; T13W, T5Y, T10Y, T30Y Treasury yields in percent; GOLD in USD/oz. An allocator
     that reads them declares `market_fields = ("series",)`, so `lab run` refuses it on a store
     without them. If it isn't testable:
     `lab block <id> --on "<data>"` plus a `data-wish` insight. Solo: choose another idea.
```

**Edit D, the command block (`:340-346`).** After
`lab costs M0007                   # report only: best variant at the flat 0.1% vs Gotrade's real fees; journals it, N unchanged`
insert
```
lab survivorship M0069            # report only: every recorded variant on the dev store vs the survivorship-check store; journals it, N unchanged
```
and after `lab block M0012 --on "quarterly fundamentals"   lab drop M0013 --why "duplicate of M0004"` insert
```
lab unblock M0012 --note "what arrived, how much of the window it covers"   # blocked-data -> idea
```

**Impact:** docs only. The buy-signal paragraph that follows ("that is the moment
survivorship-free price history becomes worth paying for") is left alone. Its wording is the
owner's call, and Handoffs records it.

### Step 10: Update the sync skill
**File:** `.claude/skills/sync-research-store/SKILL.md:101-107`
Old:
```
## What this does NOT sync

- **Neon.** Production is untouched; this is machine-local train/eval state only.
- **`fundamental_facts` or `bars` in a database.** Only the store's CSVs travel. If you want a
  *fresher* store rather than the same one, rebuild it from the database on one laptop
  (`python -m seer_engine research_store --with-fundamentals`) and `push` that.
- **Recorded lab trials.** Those live in the repo and move by git, as they should.
```
New:
```
## What this does NOT sync

- **Neon.** Production is untouched; this is machine-local train/eval state only.
- **`fundamental_facts` or `bars` in a database.** Only the store's CSVs travel. If you want a
  *fresher* store rather than the same one, rebuild it from the database on one laptop
  (`python -m seer_engine research_store --with-fundamentals`) and `push` that.
- **Recorded lab trials.** Those live in the repo and move by git, as they should.
- **The survivorship-check store, `engine/.research-sv/`.** `sync_store.py` moves
  `engine/.research/` and nothing else (`store_dir`), and its Blob key and `LATEST.json` pointer
  belong to the dev store alone. So the check store can never overwrite the dev store's pointer,
  and it never travels by Blob. It is derived, so rebuild it on the other machine instead:
  1. copy the EODHD cache folder `engine/.cache/eodhd/` across by hand (USB or `scp`, about
     215 MB). It is raw vendor data under a personal licence, so **never commit it, never put it
     in Blob and never put it under `web/`**;
  2. `pull` the dev store with this skill;
  3. from the main checkout, build offline with absolute paths (never through a symlink):
     `engine/.venv/bin/python -m seer_engine survivorship_store --build --out "$PWD/engine/.research-sv" --source "$PWD/engine/.research"`.

  The same cache and the same dev store give the same check store. Compare the price fingerprint
  that `survivorship_store --report` prints on both machines.
```
**Impact:** docs only. `sync_store.py` is unchanged, since nothing in it could reach the check
store.

### Step 11: Mark the handover done
**File:** `docs/plans/HANDOVER_20261010-eodhd.md:8`. Insert after line 8, which ends
`… writing to `lab/lab.sqlite`; see §6.`:
```markdown
**Done («YYYY-MM-DD»):** §5.1 and §5.2 are built on `feature/eodhd-survivorship-market`. The
survivorship check's results, coverage table and the journaled answer are in
`docs/lab/survivorship/` (README, grid, insight; lab synthesis insight «id»). The check store stays
a cross-check, not a gate (plan D1).
```

### Step 12: Verify, commit and push the branch
**File:** git (feature branch)
```bash
cd $WT
$WT/engine/.venv/bin/python -m pytest engine/tests -q
$WT/engine/.venv/bin/ruff check engine
$WT/engine/.venv/bin/python $RUN/guard.py check $RUN/before.json $(cat $RUN/all_methods.txt)
git add docs/lab/survivorship/grid.csv docs/lab/survivorship/README.md docs/lab/survivorship/insight.md \
  .claude/skills/explore-and-experiment-new-method/SKILL.md \
  .claude/skills/sync-research-store/SKILL.md \
  docs/plans/HANDOVER_20261010-eodhd.md
git diff --cached --name-only        # exactly these six paths
git commit -m "lab: survivorship check measured and journaled — results in docs/lab/survivorship, skills name the check store

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git push -u origin feature/eodhd-survivorship-market
```
The full suite must pass. The guard must exit 0. If it reports other sessions' trials, put that
line into the completion note.
**Impact:** branch only. Merging to `main` is the completion step of the plan set, not this phase.

### Step 13: Stage the lab DB per Decision D6
**File:** `/home/miftah/seer/lab/lab.sqlite`, `/home/miftah/seer/web/data/lab.json`, on `main` in
the main checkout
```bash
tmux list-windows -a -F '#{window_name}' | grep -E '^sera-' && echo SERA-ALIVE || echo no-sera
pgrep -af "seer_engine.*lab (run|survivorship|remeasure|costs|test)" || echo no-lab-writer
```
- **If a `sera-*` window is alive, or any lab writer is running:** do not stage. The Sera
  coordinator's next `lab stage` carries the new insights, because they are rows in the same
  file. Write in the completion note: "Lab DB not staged: Sera batch «window» was live; its
  coordinator's next `lab stage` commits the survivorship observations and synthesis."
- **Otherwise:**
  ```bash
  cd /home/miftah/seer
  git branch --show-current                         # main
  git diff --cached --name-only                     # must be empty before staging
  engine/.venv/bin/python -m seer_engine lab stage  # main venv is fine: stage needs no new code
  git diff --cached --name-only                     # exactly lab/lab.sqlite and web/data/lab.json
  git commit -m "lab: survivorship check journaled

  Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
  git push origin main
  ```
  Never `git add lab/lab.sqlite` by hand. Never `git pull` in the main checkout here. If the push
  is rejected (non-fast-forward), do **not** pull or rebase. Leave the commit local, and say in
  the completion note that `main` needs a coordinator push.

**Impact:** at most one commit on `main` with the two lab files.

### Step 14: Repeat the post-landing steps in the completion note
**File:** none (the completion note / final report of this phase)
**Change:** this phase does **not** run L0-L3: they need the set merged to `main` first, and the
lander (the `/analyze-orchestrator` coordinator, or the completion handler) runs them in the main
checkout as its final act. So that a human can run them if the lander does not, end the completion
note with the heading "Post-landing L0-L3 (run in /home/miftah/seer after the merge to main)",
the 13a fingerprint phase 3 recorded (from phase 3's completion note, if at hand), and this block
verbatim. It is the plan index's **Post-landing** section; if the two ever differ, the index wins.

**Re-running.** Every step checks its own end state first and is a no-op when already done, so
the whole block may be re-run top to bottom after an interruption. No step asks a question.

```bash
MAIN=/home/miftah/seer
PY=$MAIN/engine/.venv/bin/python
export SEER_LAB_DB=$MAIN/lab/lab.sqlite
```

**L0 — guard: the main checkout carries the landed code.** The live Sera batch loads the dev store
with the main checkout's code, and only the landed code accepts a manifest listing
`market_series.csv`:
```bash
git -C $MAIN fetch origin main
grep -q MARKET_SERIES_FILE $MAIN/engine/src/seer_engine/research.py \
  || git -C $MAIN merge --ff-only origin/main
$PY -c "import seer_engine, sys; from seer_engine import research as r; \
assert seer_engine.__file__.startswith('$MAIN/engine/src/'), seer_engine.__file__; \
assert 'market_series.csv' in r.OPTIONAL_DATA_FILES and hasattr(r, 'SURVIVORSHIP_PURPOSE'); print('READY')" \
  || echo DEFER
```
On `DEFER` (the fast-forward was refused: a dirty file the landing touches, or a diverged local
`main`; or the venv does not import the landed code), skip L1-L3 and write in the close-out note:
"post-landing L1-L3 pending: main checkout not at the landed code". Never force, stash or reset the
main checkout (the Sera batch's lab DB lives there).

**L1 — market series into the real dev store, then push it.** Skip the refresh when the store
already lists the file:
```bash
python3 -c "import json,sys; sys.exit(0 if 'market_series.csv' in json.load(open('$MAIN/engine/.research/manifest.json'))['files'] else 1)" \
  && echo "L1 refresh already done"
```
Otherwise wait for quiet. `_refresh_optional` swaps the directory in place, so a process inside
`load_store` at that moment fails its sha check (no trial is written, but the run is wasted). Use a
Monitor until-loop polling every 60 s, never a foreground sleep:
`until ! pgrep -f '[s]eer_engine.*( lab .*(run|remeasure|costs|survivorship|test|walkforward|regime)| (backtest_dev|survivorship_store|research_store|dividend_announcements|market_series))'; do sleep 60; done`.
After 45 minutes, proceed when every remaining match is older than 10 minutes
(`ps -o etimes= -p <pid>` > 600: it finished loading). Then:
```bash
mkdir -p /tmp/claude-1000/postland
[ -f /tmp/claude-1000/postland/research-manifest-before.json ] \
  || cp $MAIN/engine/.research/manifest.json /tmp/claude-1000/postland/research-manifest-before.json
cd $MAIN && $PY -m seer_engine market_series --refresh --store $MAIN/engine/.research --cache $MAIN/engine/.cache/eodhd/market
#   must print "price fingerprint 5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a (unchanged)"; exit 0
$PY - <<'EOF2'
import json
from seer_engine import research
dev = "/home/miftah/seer/engine/.research"
a = json.load(open("/tmp/claude-1000/postland/research-manifest-before.json"))["files"]
b = json.load(open(f"{dev}/manifest.json"))["files"]
assert all(b[k] == v for k, v in a.items()), "a carried file changed"
d = research.load_store(dev)
assert d.price_fingerprint.startswith("5451195f") and d.purpose is None and len(d.market.series) == 43317
print("L1 OK", d.fingerprint)
EOF2
python3 $MAIN/.claude/skills/sync-research-store/sync_store.py status
python3 $MAIN/.claude/skills/sync-research-store/sync_store.py push
```
The new full fingerprint should equal the one phase 3's completion note recorded for its copy; a
different value with the checks above passing is recorded, not a stop. A failed check: run the
rollback below and record it. No Blob token: record "dev store not pushed: no Blob token"; do not
block. A re-run's push of an unchanged store is a no-op (content-addressed).

**L2 — unblock M0039 and M0038.** First re-read the coverage from the real store (read only):
```bash
cd $MAIN && $PY -m seer_engine market_series --store $MAIN/engine/.research --cache $MAIN/engine/.cache/eodhd/market
#   expect: VIX3M member days 2331 (46.8%), T10Y member days 4966 (99.6%),
#   "differ on 9, by at most 1.05 (2014-10-15)"
```
If a printed number differs from the note below, replace that number in the note with the printed
one before running it (mechanical; no other wording changes). Then:
```bash
$PY -m seer_engine lab unblock M0039 --note \
"The fear index and its three-month version now load from the research store's market series (the store calls them VIX and VIX3M; the three-month series was named VXV until November 2007, and the store uses the newer name wherever both exist). The three-month series starts on 17 July 2006, so this gate can be tested on 2,331 of the 4,984 trading days the dev window holds index members: 46.8%, about 9.3 of 19.8 years, mid-2006 to October 2015. That span includes the 2008 crash, the May 2010 flash crash and the August 2011 downgrade. It does not include the mid-1998 fall this idea was written for, nor 2000-2002. The two names of the three-month series agree on 1,987 of the 1,996 days they overlap and differ by at most 1.05 points (15 October 2014). A fair test compares the gate with the same book over the same 2006-2015 span, not over the whole window."
$PY -m seer_engine lab unblock M0038 --note \
"Only the yield-curve half arrived. The 13-week Treasury bill and the 5-, 10- and 30-year Treasury yields, in percent, now load from the research store's market series (the store calls them T13W, T5Y, T10Y and T30Y). The longer yields start on 2 November 1993 and the bill on 29 January 1993. The 10-year minus 13-week spread exists on 4,966 of the 4,984 trading days the dev window holds index members (99.6%). The 18 missing days are bond-market holidays, where the last published yield carries over, so the spread covers the whole dev window: 19.8 of 19.8 years. Two differences from the idea as written. First, the spread is 10-year minus 13-week bill, not 10-year minus 2-year: no 2-year series was available. Second, the credit-spread half (corporate BAA yield minus the 10-year) and the inflation-protected yield are still unavailable, because the paid data plan has no corporate or inflation-protected bond yields. So only the yield-curve gate is testable, and a test must say it tests that half alone."
```
A method that is no longer `blocked-data` is refused (exit 2) and left as it is; that is the
re-run case. Record it and go on.

**L3 — stage per Decision D6.** Only when no `sera-*` tmux window and no lab writer is alive
(phase 5 Step 13's two checks); then, in `$MAIN` on `main` with an empty index:
`$PY -m seer_engine lab stage`, check `git diff --cached --name-only` is exactly `lab/lab.sqlite`
and `web/data/lab.json`, commit, `git push origin main` (rejected push: leave the commit local and
say so; never pull or rebase here). Otherwise the Sera coordinator's next `lab stage` carries the
rows; record that. Nothing staged when nothing changed: a re-run is a no-op.

---

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/eodhd-survivorship-market && engine/.venv/bin/ruff check engine`
**Tests:** `cd /home/miftah/.worktrees/seer/eodhd-survivorship-market && engine/.venv/bin/python -m pytest engine/tests -q`
**Manual check:**
- `guard.py check` exits 0. N and test looks for the measured methods are unchanged, no trial row
  carries the SV fingerprint, and there is one observation per measured method.
- `docs/lab/survivorship/grid.csv` has rows for all of `all_methods.txt` and no price columns.
- The insight text has no method ids, backticks or file names. This prints nothing:
  ```bash
  grep -nP 'M0[0-9]{3}|\x60|\.csv|\.py|\.sqlite' docs/lab/survivorship/insight.md
  ```
- The dev store's manifest fingerprint equals `before.json`'s, and its price fingerprint is
  `5451195f…`.
**Exit criteria:** every listed method has a journaled observation and a grid row. The synthesis
insight is journaled, with its id recorded in the handover's Done line. Both skills name the check
store and the command. The branch is pushed. Staging is done per D6, or deferred with a stated
reason. The completion note ends with the post-landing L0-L3 block (Step 14).

## Handoffs

- **Merge to `main`** of the feature branch: the plan set's completion step (completion-handler),
  not this phase.
- **Buy-signal wording** in the explore skill ("that is the moment survivorship-free price history
  becomes worth paying for…") and `BUY_CONDITIONS` in `lab/walkforward.py`: the data is now
  partly owned. Rewording is the owner's call (the skill says so) and is left untouched.
- **Gate use of the check store (D1):** if the numbers show large flattery, a follow-up argued
  commit in `lab/hardgate.py` could make `lab survivorship` a promotion condition. That is out of
  scope here by decision, and the insight says so.
- **Post-landing L0-L3 (plan index):** after the set lands, the lander, in the main checkout and
  with its venv, checks `main` carries the code, refreshes the real dev store with
  `market_series.csv`, pushes it with the sync skill, unblocks M0039/M0038 and stages per D6. Not
  this phase: before landing, the main checkout's code cannot load such a store (D8). Step 14
  repeats the block in the completion note.

## Rollback

- Journal rows are append-only. A wrong observation or synthesis is answered with a correcting
  `synthesis` insight that says which entry it replaces, as insight 126 did.
- Docs and skills: `git revert` the phase's branch commit.
- The SV store rebuild: rerun Step 2. Or delete `/home/miftah/seer/engine/.research-sv` and rebuild
  it with the same command. The dev store is never written.
- If the D6 commit landed on `main` and must be undone, `git revert` that commit on `main`. That
  reverts the staged snapshot only. The DB file on disk keeps the rows, which is correct, since
  journal rows are permanent.
