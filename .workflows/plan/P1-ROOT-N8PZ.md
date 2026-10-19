> Adopted from `/home/miftah/seer/.workflows/orchestration/gate-reading-cadence/PLAN.md` phase 3. Source: `.workflows/plan/gate-reading-cadence/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: Run and record the verdict

**Plan set:** `GATE_READING_CADENCE_PLAN.md`
**Analysis:** `docs/analyzer/20261019-152028-SSYJ_code_analyzer.md`
**Satisfies:** R1 (sweep the gate's reading cadence weekly→yearly as a dose-response ladder, and
find where it turns), R2 (read the walk-forward folds arm by arm), R5 (quote `trial_funding.mwr`
throughout), R7 (spend no test-window look)
**Depends on:** Phase 2 — its two files must exist, be green, and be **already committed in phase
2's pre-registration commit** when this phase starts. Phase 1 is a soft dependency: its anchor
probe is the diagnostic this phase reaches for when an arm misbehaves, and its committed `.md` is
the citable record behind the method file's prior grid.
**Difficulty:** HARD
**Package:** `lab/` in the **main checkout** (`/home/miftah/seer/lab/lab.sqlite`,
`/home/miftah/seer/web/data/lab.json`). This phase writes no source code at all.

---

## Goal

After this phase the lab holds **six** recorded dev trials under M0260 — the SPY-200 gate read at
its native cadence and at three-, six- and twelve-month anchors on a monthly book, plus a weekly
book read natively and a weekly book reading the monthly anchor — together with a recorded
verdict, a plain-language analysis in the owner's register, and at least one journalled insight.

**Six, not seven.** `lab/method.py:40` sets `MAX_VARIANTS = 6` and `Method.__post_init__` raises
outside `1..6`, so the `k = 2` rung the plan index originally listed is **not an arm**: phase 1
measures it as a prior and it is deferred to an `Amendment` under the same method id, which costs
no method id. The monthly ladder here has **four** rungs — native, 3, 6, 12.
M0258's unexplained +7.01 pts/yr is split, for the first time, into a re-pick-frequency term and a
gate-cadence term that sum to it by construction. The test-window look count is still 4.

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts.

**Deletes:** none.
**Renames:** none.
**Creates:**
- six rows in `trials` (method `M0260`), the next free `n` after 830 — expected `#831..#836`
  **only if no other session records a trial first**; the actual numbers are read back, never
  assumed
- six rows in `trial_funding`, six in `trial_provenance`, up to six in `trial_moments`
- one `method_analysis` append and one `methods.verdict` on `M0260`
- `methods.M0260`: `status` `idea` -> `registered` -> (`dev-eligible` | `rejected`);
  `methods.source_sha` set once; `name`, `family`, `source_kind`, `source_ref`, `parent_id`,
  `hypothesis` **overwritten from phase 2's method file** (`runner.py:756-762`)
- 1-3 `insights` rows; 2-3 journal observations from `lab costs`; 0-1 `methods` row from `lab idea`
- `web/data/lab.json` regenerated in the **main checkout**

**Signature changes:** none.

**Requires (from earlier phases):**
- Phase 2: `engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py` exists, exports
  `METHOD = Method(id="M0260", ...)` with exactly the **six** candidates of Appendix A
  (`M0260-M-NATIVE`, `M0260-M-G3`, `M0260-M-G6`, `M0260-M-G12`, `M0260-W-NATIVE`, `M0260-W-G1`),
  and `engine/tests/test_lab_m0260_cadence.py` exists and passes. **Both already committed by
  phase 2 in the pre-registration commit** — this phase verifies that commit and runs against it;
  it does not create, amend or rebase it.
- Phase 2: **every one of the six** candidate `rationale` strings carries a
  `control_shape.DOSE_MARKERS` phrase — the literal lowercase `dose-response` is the one that
  matches in this lab today (`lab/control_shape.py:191-200`; `kind_of` searches the lowercased
  `rationale`). Phase 2's decision D-B2 put it in all six, the two weekly arms included. Without
  it D17 does not read the ladder as its own control at all.
- Phase 2: `lookback` is **454**, not M0072's 253 (phase 2 decision D-B, measured), and therefore
  the first scored session of every arm is **1996-01-03** — identical to M0072 and M0258 at
  lookback 253, because `dev.candidate_window` binds on `MEMBERSHIP_START` (1996-01-02) for any
  `lookback <= 739`. Step 3's probe prints `row.start`; it must read `1996-01-03` or the two
  reproduction arms are not reproductions.
- Phase 2: `as_dict` renders every params field, or two arms collide on one `config_digest` and
  `lab run` exits 2 on the second (Invariant 10).
- Phase 1: `docs/backtests/2026-10-19-gate-reading-cadence.py` is committed and runnable — it is
  the diagnostic for the "an arm fell back to `data_date`" branch.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py` and
  `engine/tests/test_lab_m0260_cadence.py` — **frozen the instant this phase's step 3 commit
  lands.** This phase commits them and never edits them.
- `docs/backtests/2026-10-19-gate-reading-cadence.{py,md}` (Phase 1)
- `docs/plans/HANDOVER_20261019-the-gate-reading-cadence.md`, `.workflows/todos.md`, the memory
  file, and the merge of `feature/gate-reading-cadence` to `main` (Phase 4)
- `lab test`, `SEER_RESEARCH_TEST_STORE`, `engine/.research-test` — **never touched** (R7)
- every existing method file, `sim/rules.py`, `web/` source

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py` | verify only (phase 2 committed it) | **no edit, no commit, no amend** |
| `engine/tests/test_lab_m0260_cadence.py` | verify only (phase 2 committed it) | **no edit, no commit, no amend** |
| `/home/miftah/seer/lab/lab.sqlite` | append (main checkout) | 6 trials + funding + provenance + moments, status, verdict, analysis, insights |
| `/home/miftah/seer/web/data/lab.json` | regenerate (main checkout) | `lab stage` |
| `/tmp/m0260/*` | create | capture files; **never committed** |

Nothing under `engine/src` or `engine/tests` is created, modified **or committed** by this phase.
Phase 2 wrote those two files and made the pre-registration commit; this phase verifies that
commit and then writes only to the lab database.

---

## The environment, inline, every time

Each Bash call is a fresh shell — exports do not survive between tool calls. **Every command below
carries its environment inline.** Copy them whole.

| variable | value | why |
|---|---|---|
| `PYTHONPATH` | `/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src` | **the single most dangerous trap in this phase.** Without it `lab run` loads the MAIN checkout's `seer_engine`, discovers no `m0260_*.py`, and either refuses or — worse, after phase 4 merges — pre-registers one file and runs another |
| `SEER_LAB_DB` | `/home/miftah/seer/lab/lab.sqlite` | the shared, append-only lab. A worktree copy must never be written |
| `SEER_RESEARCH_STORE` | `/home/miftah/seer/engine/.research` | the dev store. The worktree has none. **Never rebuild it** — 30 minutes for nothing |
| `PY` | `/home/miftah/seer/engine/.venv/bin/python` | the worktree has no venv |
| `CAP` | `/tmp/m0260` | capture directory. A session with its own scratchpad may point this there instead; nothing else changes |

Two more facts that bite:

- **`config.REPO_ROOT` follows `PYTHONPATH`.** `config.py:17` is
  `Path(__file__).resolve().parents[3]`, so with the worktree on `PYTHONPATH` the `git_sha`
  stamped into every trial is the **worktree's** HEAD. That is what makes step 6's verification
  exact.
- **`lab stage`'s `git add` runs with `cwd = <the lab DB's parent>`** (`commands/lab.py:3134`),
  which is `/home/miftah/seer/lab`. So it stages into the **main checkout's** index no matter
  where the command was invoked from.

**Never judge a `lab` command by a piped exit code.** Redirect to a capture file and `echo $?` on
the next statement. A `grep`, `head` or `tee` owns the pipeline's status and will hide a refusal.
Exit **0** = ok, **2** = the lab's rules refused the request, **1** = an error. This shell prints
a spurious `setValueForKeyFakeAssocArray:27: command not found: _encode` line at the head of every
captured file; ignore it, and never let it make you think a command failed.

### Capture files

| file | written by | holds |
|---|---|---|
| `$CAP/00-pretest.txt` | `pytest -n0` | the green tree before the pre-registration commit |
| `$CAP/00-ruff.txt` | `ruff check engine` | lint, bugs-only |
| `$CAP/00-arms.txt` | the arm dump | the six ids, their rule sets, their digests and the `dose=` column |
| `$CAP/01-prereg.txt` | `git log -1` on phase 2's commit | the pre-registration commit and its sha |
| `$CAP/02-probe.txt` | the one-arm timing + reproduction probe | **M-NATIVE's metrics before any trial is recorded**, its `row.start`, and the wall clock for one arm |
| `$CAP/02-probe-w.txt` | the same probe on `W-NATIVE` | the second reproduction arm, checked before the run |
| `$CAP/03-run.txt` | `lab run M0260` | the six trials as the runner printed them |
| `$CAP/04-show.txt` | `lab show M0260` | the recorded rows, the ladder, the funded lines |
| `$CAP/05-verify.txt` | sqlite + `sha256sum` | `source_sha`, `git_sha`, trial numbers, test-look count |
| `$CAP/06-ladder.tsv` | sqlite | the ladder at full precision — the table phase 4 quotes |
| `$CAP/07-walkforward.txt` | `lab walkforward M0260` | the headline: folds won, stable, 2009-15 edge, verdict |
| `$CAP/08-folds.txt` | the per-fold reader | **which arm each fold picked and whether it won** (R2) |
| `$CAP/09-control.txt` | `lab control M0260` | D17: dose-response rows, `not-checked`, no refuse |
| `$CAP/10-costs-*.txt` | `lab costs` | real Gotrade fees vs the flat 0.1%, per arm |
| `$CAP/11-note.txt` | `lab note M0260` | the verdict and the analysis, recorded once |
| `$CAP/12-insight-*.txt` | `lab insight` | what generalises |
| `$CAP/13-idea.txt` | `lab idea` | the queued follow-up, if the result implies one |
| `$CAP/14-stage.txt` | `lab stage` | the two staged paths |
| `$CAP/15-commit.txt` | `git -C /home/miftah/seer commit` | the result commit |
| `$CAP/16-final.txt` | `lab show` + `lab status` | the closing state phase 4 reads |

**These paths are the contract with phase 4**, which quotes every number in its handover out of
them by name. Do not move them. `$CAP` defaults to `/tmp/m0260`, and **`/tmp` does not survive a
reboot** — so either phase 4 runs in the same uptime as this phase, or this phase copies the whole
directory somewhere durable before it closes out:

```bash
cp -a /tmp/m0260 /home/miftah/.cache/seer-captures-m0260 && echo "EXIT=$?"; \
ls /home/miftah/.cache/seer-captures-m0260
```

If the captures are gone when phase 4 runs, phase 4 has a read-only fallback that re-reads the lab
and restores the database by path — but it is strictly worse, because `02-probe*.txt`,
`06-decomp.txt` and `08-folds.txt` cannot be re-derived from the database alone without re-running
the probe and the fold reader.

---

## What is being reproduced, at full precision

Read from the lab on 2026-10-19 (`trials` joined to `trial_funding`, read-only). These are the
numbers the two reproduction arms must return, and the ones phase 4 quotes.

| recorded arm | mwr (`trial_funding.mwr`) | worst fall | trades | turnover | exposure | PF | DSR |
|---|---|---|---|---|---|---|---|
| `M0258-M-B0` ( = `M0072-Z2-RAWRANK`, trial #283/#829) | **12.3314 %** | **23.8026 %** | **1208** | **6.5288** | **0.6949** | **1.9781** | 0.928 @ N=163 |
| `M0258-W-B0` (trial #833) | **5.3178 %** | **35.4908 %** | **1923** | **10.0021** | **0.6855** | **1.2767** | 0.4156 @ N=163 |
| the deposits in SPY TR | 7.188 % | — | — | — | — | — | — |

`M0260-M-NATIVE` must return the first row and `M0260-W-NATIVE` the second, on **mwr, worst fall,
trades, turnover, exposure and PF**.

**DSR is deliberately excluded from the reproduction check.** The N policy counts *methods*
(`store.pending_gate`, `store.py:1402-1405`): N is `gate(conn).n + 1` when the method has no dev
trial yet. M0258 ran at N=163; M0260 is a new method, so **M0260's trials are scored at N=164**
and the native arm's DSR will read slightly *below* 0.928. That is the luck gate doing its job,
not a reproduction failure. Say so in the analysis; do not present it as drift.

**Why a drift anywhere else is a stop condition.** M0258's own `M-B0` came back bit-identical to
M0072's recorded row — the lab's standing note that a re-run of a recorded row drifts did not
apply, because the overlay passes the host's own params to the host's own target builder and only
the gate line differs. M0260 is built the same way. So a difference here is evidence that
something in the chassis, the store or the method file moved, and it must be chased before any
comparison in this method is quoted.

## The decomposition, and why it must sum

With **A** = `M0260-M-NATIVE`, **B** = `M0260-W-NATIVE`, **C** = `M0260-W-G1`:

```
(A - B)        =   (A - C)                 +   (C - B)
 the total         re-pick frequency           gate reading cadence
 +7.0136 pts/yr    (gate held at the month)    (re-pick held weekly)
 11.6882 pts fall
```

`(A − B)` is a prediction, not a free parameter: it is `12.3314 − 5.3178 = 7.0136` pts/yr and
`35.4908 − 23.8026 = 11.6882` points of fall, and it lands there automatically once the two
reproduction arms reproduce. **The two halves sum to the total by construction**, because C is
defined to share A's gate reading and B's re-pick calendar. So a failure to sum is an arithmetic
slip or an arm-definition error — not a result. Chase it; never report it.

Report the split on **both** axes: money-weighted return *and* worst fall.

---

## Implementation Steps

### Step 0: Set up the capture directory and photograph the lab

**File:** none — environment only.
**Change:** one directory and one baseline hash. The hash exists so that, if steps 1-2 are the
only commands run and the database file changes, you can tell a *migration-on-connect* (harmless,
restore it) from a *write* (never restore it).

```bash
mkdir -p /tmp/m0260 && \
sha256sum /home/miftah/seer/lab/lab.sqlite | tee /tmp/m0260/lab-before.sha256 && \
sqlite3 "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" \
  "select 'dev', count(*) from trials where window='dev' union all \
   select 'test', count(*) from trials where window='test' union all \
   select 'insights', count(*) from insights union all \
   select 'M0260', status from methods where id='M0260';" \
  > /tmp/m0260/lab-before.txt 2>&1; echo "EXIT=$?"; cat /tmp/m0260/lab-before.txt
```

**Expected:** `dev|830`, `test|4`, `insights|465`, `M0260|idea`.

**Impact:** nothing is written. The `?mode=ro` URI is deliberate — it is the one way to read the
lab without the connect-time migration dirtying the file.

**The restore rule, stated once.** If a read-only intent leaves
`sha256sum /home/miftah/seer/lab/lab.sqlite` different from `lab-before.sha256` *and no write
command has been run yet*, restore it by path and only by path:

```bash
git -C /home/miftah/seer checkout -- lab/lab.sqlite && echo "EXIT=$?"
```

**After step 4 (`lab run`) this rule is dead.** From then on the hash must move, and restoring it
would destroy recorded trials. Never run that checkout again in this phase.

---

### Step 1: Verify phase 2's files are present, green and already committed

**File:** `engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py`,
`engine/tests/test_lab_m0260_cadence.py`
**Change:** verification only. **Phase 2 made the pre-registration commit; this phase does not.**
That commit froze these files forever, so anything still wrong with them goes back to phase 2 as a
new commit on top — never an amend, never a rebase — and it must be fixed before step 4 runs.

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
git status --short && \
ls -l engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py \
      engine/tests/test_lab_m0260_cadence.py && \
sha256sum engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py \
  | tee /tmp/m0260/method.sha256; echo "EXIT=$?"
```

Then the two gates, in order. Postgres first — CI fails if the DB tests skip:

```bash
docker start seer-pg > /tmp/m0260/00-docker.txt 2>&1; echo "EXIT=$?"
```

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
/home/miftah/seer/engine/.venv/bin/python -m pytest -n0 engine/tests \
  > /tmp/m0260/00-pretest.txt 2>&1; echo "EXIT=$?"; tail -25 /tmp/m0260/00-pretest.txt
```

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
/home/miftah/seer/engine/.venv/bin/ruff check engine \
  > /tmp/m0260/00-ruff.txt 2>&1; echo "EXIT=$?"; cat /tmp/m0260/00-ruff.txt
```

Then confirm the method file declares the six arms this plan expects, and nothing else. This is
the last chance to catch an arm-table mismatch before the run:

```bash
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
/home/miftah/seer/engine/.venv/bin/python - <<'PYEOF' > /tmp/m0260/00-arms.txt 2>&1
from seer_engine.lab.method import discover, config_digest, config_text
m, path = discover()["M0260"]
print("file:", path)
print("name:", m.name)
print("family:", m.family, "| source_kind:", m.source_kind, "| parent:", m.parent_id)
print("candidates:", len(m.candidates))
seen = {}
for c in m.candidates:
    d = config_digest(c)
    print(f"  {c.id:<20} rules={c.rules.id:<28} digest={d[:12]} dose={'dose-response' in str(c.rationale).lower()}")
    seen.setdefault(d, []).append(c.id)
dupes = {d: ids for d, ids in seen.items() if len(ids) > 1}
print("DIGEST COLLISIONS:", dupes if dupes else "none")
PYEOF
echo "EXIT=$?"; cat /tmp/m0260/00-arms.txt
```

**Expected:** `candidates: 6`; the ids `M0260-M-NATIVE`, `M0260-M-G3`, `M0260-M-G6`,
`M0260-M-G12`, `M0260-W-NATIVE`, `M0260-W-G1`; **four** on `monthly-hold-frac-gotrade` and two on
`weekly-hold-frac-gotrade`; `dose=True` on **every one of the six rows**; `DIGEST COLLISIONS:
none`.

`candidates: 7` cannot happen: `lab/method.py:40` sets `MAX_VARIANTS = 6` and
`Method.__post_init__` raises outside `1..6`, so a seventh arm would fail at import, not here. The
`k = 2` rung is phase 1's prior and a future `Amendment`, not a trial.

**Impact:** a `False` in the `dose` column means D17 does not read that arm as part of the
dose-response ladder at step 9. A digest collision means `lab run` will exit 2 at step 4. Both are
phase-2 bugs and **the method file is already frozen by phase 2's commit** — report them to the
coordinator; the fix is a new phase-2 commit before step 4, never an edit or an amend here.

---

### Step 2: Verify the pre-registration commit — **phase 2 made it; this phase does not**

**File:** both of phase 2's files, already committed together in one commit by phase 2's step 3.
**Change:** verification only. That commit **is** the pre-registration. `runner.preflight` calls
`registry_problem(path)` (`commands/backtest_dev.py:486-515`), which runs
`git status --porcelain -- <basename>` with `cwd = <the method file's directory>` and
`git ls-files --error-unmatch`. It refuses a file that is untracked, modified or staged.

**Why phase 2 and not phase 3 owns it.** Phase 2's exit criterion 7 requires the commit to exist
and to be unamended, and phase 2's rollback section is written around it; phase 3's exit criteria
never claimed it. Two phases cannot both author the same commit, and an unamendable commit belongs
with the phase that can still fix the file. This phase's job is to prove it governed the run —
step 6 asserts `methods.source_sha` against the committed file's bytes and `trials.git_sha`
against this commit.

**Does the commit have to be pushed? No, a local commit suffices.** `registry_problem` consults
only the working tree and the index. It never calls `rev-list @{u}..`, never asks for a remote, and
never resolves an upstream. Nothing anywhere in `runner.preflight` does either. **Do not push
before the run** — `feature/gate-reading-cadence` reaches `origin` in phase 4, as part of the merge
to `main`, and pushing a half-finished branch here only invites the rebase trap (see Rollback).

Capture the commit phase 2 made, and its sha:

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
git log -1 --stat > /tmp/m0260/01-prereg.txt 2>&1; echo "EXIT=$?"; \
cat /tmp/m0260/01-prereg.txt; \
git -C /home/miftah/.worktrees/seer/gate-reading-cadence rev-parse HEAD \
  | tee /tmp/m0260/prereg-sha.txt
```

**Expected:** `01-prereg.txt` shows a commit whose subject begins
`lab: M0260 pre-registered` and whose diffstat is **exactly** the two files
`engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py` and
`engine/tests/test_lab_m0260_cadence.py` — nothing else, and no `lab/lab.sqlite`.

If that commit is not there, **stop**: phase 2 is not finished and this phase has nothing to run
against. Do not make it here. (If the coordinator has nonetheless told this session to make it,
use phase 2's step-3 message verbatim, and say "six arms", never seven.)

Then confirm the tree is clean for those two paths — `registry_problem` refuses on *any*
porcelain output for the file, staged included:

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
git status --porcelain -- engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py \
  > /tmp/m0260/01-clean.txt 2>&1; echo "EXIT=$?"; \
echo "---porcelain must be empty above---"; wc -c /tmp/m0260/01-clean.txt
```

**Expected:** `0 /tmp/m0260/01-clean.txt`.

**Impact:** the method file is now frozen. From this point an edit to it is an `Amendment` with
its own pre-registration commit, not a fix — and this phase makes neither.

---

### Step 3: Probe one arm — the pre-run reproduction check and the runtime measurement

**File:** `/tmp/m0260/probe.py` (throwaway; never committed)
**Change:** run **`M0260-M-NATIVE` alone**, outside the lab, on the real dev store, timed. This
is the single most valuable step in the phase and it costs nothing: it writes no trial, consumes
no config digest, moves no status, and touches the lab database not at all.

It answers the three questions that must be settled before six arms are committed to:

1. **Does the native arm reproduce `M0258-M-B0`?** If it does not, the stop is here — *before*
   any trial is recorded and before the method id is spent. After step 4 the trials are
   append-only and a drift can only be written up, never prevented.
2. **How long does one arm take?** `lab run` has no `--only`: it runs every candidate the method
   declares, all six, in one call. The only way to price that call before making it is to run one
   arm by hand.
3. **Did the widened lookback move the window?** Phase 2 sets `lookback = 454`, not M0072's 253,
   because a twelve-month anchor sits up to 253 sessions behind the data date and still needs its
   200-bar average (phase 2 decision D-B, measured). The probe prints `row.start`, and **it must
   read `1996-01-03`** — the same first scored session M0072 and M0258 recorded at lookback 253,
   because `dev.candidate_window` checks only the candidate's fixed symbols (`ZJUMP.symbols(BOOK)`
   is `("SPY",)`) and index members are floored separately at `MEMBERSHIP_START = 1996-01-02`;
   SPY's 454th bar on this store is 1994-11-14 and its 739th is 1996-01-02, so any
   `lookback <= 739` leaves `ready` at the membership floor. A start of anything other than
   `1996-01-03` means the paired comparison with M0258's recorded rows is broken and **nothing in
   this method may be quoted as a reproduction** — stop before step 4.

```bash
cat > /tmp/m0260/probe.py <<'PYEOF'
"""One arm of M0260, outside the lab: reproduction check and wall clock.

Writes nothing. Opens no lab database. Uses exactly the funding lab.runner.run_method uses
(OWNER_MONTHLY on INITIAL_IDR), so its metrics are the metrics `lab run` would record.
"""
import os, sys, time
from pathlib import Path

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.runner import INITIAL_IDR
from seer_engine.lab.method import discover
from seer_engine.sim.contributions import OWNER_MONTHLY

want = sys.argv[1] if len(sys.argv) > 1 else "M0260-M-NATIVE"
store_dir = Path(os.environ["SEER_RESEARCH_STORE"])

t0 = time.monotonic()
data = research.load_store(store_dir)
t_load = time.monotonic() - t0
print(f"store loaded in {t_load:.1f}s  fingerprint={data.fingerprint}")

method, path = discover()["M0260"]
print(f"method file: {path}")
cands = [c for c in method.candidates if c.id == want]
if not cands:
    raise SystemExit(f"no candidate {want}; have {[c.id for c in method.candidates]}")

t1 = time.monotonic()
rows = dev.run_registry(
    data.market, data.dividends, data.spy_dividends, cands,
    contributions=OWNER_MONTHLY, initial_idr=INITIAL_IDR,
)
t_run = time.monotonic() - t1
row = rows[0]
m = row.stats.metrics
print(f"\n{row.candidate.id}  {row.start}..{row.end}")
print(f"  mwr          {float(m.mwr) * 100:.4f} %      (SPY TR {float(row.spy_tr.mwr) * 100:.4f} %)")
print(f"  max_drawdown {float(m.max_drawdown) * 100:.4f} %")
print(f"  trades       {m.trades}")
# turnover and exposure live on RunStats, NOT on Metrics (book_runner.py:588-590)
print(f"  turnover     {float(row.stats.turnover):.4f}")
print(f"  exposure     {float(row.stats.exposure):.4f}")
print(f"  profit_factor {float(m.profit_factor):.4f}")
print(f"\nONE ARM: {t_run:.1f}s   STORE LOAD: {t_load:.1f}s")
print(f"SIX ARMS projected: {t_load + 6 * t_run:.0f}s "
      f"({(t_load + 6 * t_run) / 60:.1f} min) — the store loads once per `lab run`")
PYEOF
echo "wrote probe"; echo "EXIT=$?"
```

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
/home/miftah/seer/engine/.venv/bin/python /tmp/m0260/probe.py M0260-M-NATIVE \
  > /tmp/m0260/02-probe.txt 2>&1; echo "EXIT=$?"; cat /tmp/m0260/02-probe.txt
```

**Expected:** `row.start` **`1996-01-03`**, then `mwr 12.3314 %`, `max_drawdown 23.8026 %`,
`trades 1208`, `turnover 6.5288`, `exposure 0.6949`, `profit_factor 1.9781`, `SPY TR 7.1880 %`.

**These six figures are expected to reproduce AT lookback 454**, not in spite of it. The lookback
changes which bars the allocator is handed, not which sessions are scored, and the scored sessions
are identical because the window still opens at `next_session(MEMBERSHIP_START)`. The gate reading
itself is the host's own `trend_on(history, data_date, inner)` at `gate_months = None` — the host's
code path verbatim, not an anchor computed to equal it. So `M-NATIVE` at 454 is `M0258-M-B0` run
again, bar for bar.

**This script was validated while this plan was written**, by running it verbatim against
`M0258`/`M0258-M-B0` on the real dev store (`PYTHONPATH=/home/miftah/seer/engine/src`, since
M0260 did not exist yet). It printed exactly those six figures and wrote nothing. **Measured
runtime: store load 11.2 s, one arm 4.9 s — so six arms project to about 40 seconds.** The
store, not the simulator, is the expensive part, and `lab run` loads it once. Treat that as the
expectation: an arm taking minutes rather than seconds is itself a signal that something is
wrong, not a reason to wait.

**Impact:** if those six figures match, the chassis is sound and step 4 is safe. If any of them
does not, **stop — do not run step 4.** See *Failure branch B*.

Run the second reproduction arm through the same probe as well — it is five seconds and it moves
the *other* stop condition before the run rather than after it. The weekly arm is the slowest in
the set (1923 trades against 1208):

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
/home/miftah/seer/engine/.venv/bin/python /tmp/m0260/probe.py M0260-W-NATIVE \
  > /tmp/m0260/02-probe-w.txt 2>&1; echo "EXIT=$?"; cat /tmp/m0260/02-probe-w.txt
```

**Expected:** `row.start` **`1996-01-03`** again, then `mwr 5.3178 %`, `max_drawdown 35.4908 %`,
`trades 1923`, `turnover 10.0021`, `exposure 0.6855`, `profit_factor 1.2767`.

---

### Step 4: `lab run M0260` — the one irreversible command in this phase

**File:** `/home/miftah/seer/lab/lab.sqlite`
**Change:** six dev trials, their funding, moments and provenance, and
`methods.M0260` `idea` -> `registered` -> `dev-eligible`|`rejected`, all in one transaction
(`runner.run_method`, `runner.py:704-860`).

Note what the runner does with the existing `idea` row: because `methods.M0260.status` is
`idea`, `runner.py:756-762` **overwrites `name`, `family`, `source_kind`, `source_ref`,
`parent_id` and `hypothesis` from the method file.** Phase 2's file is authoritative for all six;
the row queued by M0258's run (family `market-trend-switch`, parent `M0258`) is not.

No `--allow-coverage`. M0258 ran this same host book without it and the fundamentals coverage
floor did not fire; lowering it here would be an unacknowledged change of conditions.

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine -v lab run M0260 \
  > /tmp/m0260/03-run.txt 2>&1; echo "EXIT=$?"; tail -60 /tmp/m0260/03-run.txt
```

**Expected:** exit `0`, and six `[n/6] M0260-...` progress lines in the capture, each printing
`money-weighted ... vs DCA SPY TR ...`.

**If the exit code is 2, STOP and read *Failure branch A*.** Nothing has been written — every
refusal in `preflight` is raised before the data loads.

**Impact:** irreversible. `trials` is append-only and trigger-enforced; `methods.source_sha` is
written once and `methods_source_sha_once` refuses to let it move. There is no `git revert` for
this step; the rollback is the lab's own (see *Rollback*).

---

### Step 5: Read the rows back

**File:** none — reads only.

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab show M0260 \
  > /tmp/m0260/04-show.txt 2>&1; echo "EXIT=$?"; cat /tmp/m0260/04-show.txt
```

And the ladder at full precision — this is the table phase 4 quotes, and the only place the
decomposition can be computed honestly:

```bash
sqlite3 -header -column "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" \
"select t.n,
        t.candidate_id,
        round(f.mwr*100, 4)            as mwr_pct,
        round(f.spy_tr_mwr*100, 4)     as spy_pct,
        round(t.max_drawdown*100, 4)   as fall_pct,
        t.trades,
        round(t.turnover, 4)           as turnover,
        round(t.exposure, 4)           as exposure,
        round(t.profit_factor, 4)      as pf,
        round(t.dsr, 4)                as dsr,
        t.n_trials_at_run              as n_at_run,
        t.failed
   from trials t left join trial_funding f on f.trial_n = t.n
  where t.method_id = 'M0260'
  order by t.n;" > /tmp/m0260/06-ladder.tsv 2>&1; echo "EXIT=$?"; cat /tmp/m0260/06-ladder.tsv
```

Then the two reproduction checks and the decomposition, computed rather than eyeballed:

```bash
/home/miftah/seer/engine/.venv/bin/python - <<'PYEOF' > /tmp/m0260/06-decomp.txt 2>&1
import sqlite3
db = sqlite3.connect("file:/home/miftah/seer/lab/lab.sqlite?mode=ro", uri=True)
db.row_factory = sqlite3.Row
rows = {r["candidate_id"]: r for r in db.execute(
    "select t.candidate_id, f.mwr, t.max_drawdown, t.trades, t.turnover, t.exposure, "
    "t.profit_factor from trials t left join trial_funding f on f.trial_n=t.n "
    "where t.method_id='M0260'")}

TARGET = {
    "M0260-M-NATIVE": ("M0258-M-B0", 12.3314, 23.8026, 1208, 6.5288, 0.6949, 1.9781),
    "M0260-W-NATIVE": ("M0258-W-B0",  5.3178, 35.4908, 1923, 10.0021, 0.6855, 1.2767),
}
ok = True
for cid, (twin, mwr, dd, tr, to, ex, pf) in TARGET.items():
    r = rows.get(cid)
    if r is None:
        print(f"{cid}: MISSING"); ok = False; continue
    got = (round(r["mwr"]*100, 4), round(r["max_drawdown"]*100, 4), r["trades"],
           round(r["turnover"], 4), round(r["exposure"], 4), round(r["profit_factor"], 4))
    want = (mwr, dd, tr, to, ex, pf)
    match = got == want
    ok &= match
    print(f"{cid} vs recorded {twin}: {'REPRODUCES' if match else '*** DRIFT ***'}")
    for lbl, g, w in zip(("mwr%", "fall%", "trades", "turnover", "exposure", "pf"), got, want):
        flag = "" if g == w else "   <-- differs"
        print(f"    {lbl:<9} got {g:<12} recorded {w}{flag}")

A, B, C = rows.get("M0260-M-NATIVE"), rows.get("M0260-W-NATIVE"), rows.get("M0260-W-G1")
if A and B and C:
    for lbl, key, sign in (("money-weighted return (pts/yr)", "mwr", +1),
                           ("worst fall (points shallower)", "max_drawdown", -1)):
        a, b, c = A[key]*100, B[key]*100, C[key]*100
        total, repick, cadence = sign*(a-b), sign*(a-c), sign*(c-b)
        print(f"\n{lbl}")
        print(f"  A - B   total                 {total:+.4f}")
        print(f"  A - C   re-pick frequency     {repick:+.4f}")
        print(f"  C - B   gate reading cadence  {cadence:+.4f}")
        print(f"  sum check: {repick + cadence:+.4f} vs {total:+.4f}  "
              f"residual {repick + cadence - total:+.2e}")
print("\nREPRODUCTION:", "CLEAN" if ok else "DRIFTED — STOP AND REPORT")
PYEOF
echo "EXIT=$?"; cat /tmp/m0260/06-decomp.txt
```

**Expected:** both arms `REPRODUCES`; `A - B` **exactly** `+7.0136` on money and `+11.6882` on
fall (they are differences of the two reproduced rows, so once both reproduce these follow); the
sum residual at machine epsilon, never larger.

**This script was validated while this plan was written**, run verbatim against M0258's recorded
rows with `M0258-M-B0 / W-B0 / W-B30` substituted for A / B / C. It printed
`M0258-M-B0 vs recorded M0072-Z2-RAWRANK: REPRODUCES` on all six fields,
`A - B total +7.0136` on money and `+11.6882` on fall, and a sum residual of exactly `+0.00e+00`.
So the arithmetic and the column names are known-good; only the candidate ids change.

**Impact:** a non-zero residual is an arithmetic or arm-definition error, not a finding. Chase it
before anything is written up. A `DRIFTED` verdict is *Failure branch B*, now in its
post-recording form.

---

### Step 6: Verify the pre-registration actually governed the run

**File:** none — reads only. This is the step that proves `lab run` pre-registered the file it
ran, and it is the one R7/R1 guard that nothing else performs.

```bash
echo "== committed file sha256 (this is what methods.source_sha must equal) ==" \
  > /tmp/m0260/05-verify.txt && \
sha256sum /home/miftah/.worktrees/seer/gate-reading-cadence/engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py \
  >> /tmp/m0260/05-verify.txt && \
echo "== worktree HEAD (this is what trials.git_sha must equal) ==" >> /tmp/m0260/05-verify.txt && \
git -C /home/miftah/.worktrees/seer/gate-reading-cadence rev-parse HEAD >> /tmp/m0260/05-verify.txt && \
echo "== recorded ==" >> /tmp/m0260/05-verify.txt && \
sqlite3 -header -column "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" \
  "select id, status, source_sha, family, source_kind, parent_id from methods where id='M0260';" \
  >> /tmp/m0260/05-verify.txt 2>&1 && \
sqlite3 -header -column "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" \
  "select n, candidate_id, git_sha, substr(config_digest,1,12) as digest from trials where method_id='M0260' order by n;" \
  >> /tmp/m0260/05-verify.txt 2>&1 && \
echo "== test looks (MUST still be 4) ==" >> /tmp/m0260/05-verify.txt && \
sqlite3 "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" \
  "select count(*) from trials where window='test';" >> /tmp/m0260/05-verify.txt 2>&1 && \
echo "== files the method file was NOT allowed to touch ==" >> /tmp/m0260/05-verify.txt && \
git -C /home/miftah/.worktrees/seer/gate-reading-cadence status --porcelain -- \
  engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py \
  engine/src/seer_engine/lab/methods/m0258_gate_price_band.py \
  engine/src/seer_engine/lab/methods/m0072_standardised_earnings_jump.py \
  engine/src/seer_engine/sim/rules.py >> /tmp/m0260/05-verify.txt 2>&1
echo "EXIT=$?"; cat /tmp/m0260/05-verify.txt
```

**Expected, and each is a hard assertion:**

1. `methods.M0260.source_sha` **equals** the `sha256sum` of the committed method file. (It is a
   sha256 of the file's bytes — `lab/method.py:234-235` — not a git blob id, so these are
   directly comparable.)
2. Every `trials.git_sha` for M0260 **equals** the worktree's HEAD, which equals the
   pre-registration commit from step 2. (`git_head(config.REPO_ROOT)`, and `REPO_ROOT` follows
   `PYTHONPATH` — `config.py:17`. If this shows `5210f35` or any main-checkout sha, the run used
   the wrong `PYTHONPATH` and **the whole run is void**; see *Failure branch D*.)
3. Six distinct `config_digest` prefixes.
4. `methods.M0260.status` is `dev-eligible` or `rejected`, `family` and `parent_id` as phase 2's
   file declares.
5. **Test-window trial count is still `4`.** (R7.)
6. The porcelain block is empty — nothing was edited.

**Impact:** if (2) fails, nothing in this method means what it says. Stop.

---

### Step 7: The walk-forward headline

**File:** none — report only. `lab walkforward` opens no research store; every fold is a date
slice of recorded monthly curves.

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab walkforward M0260 \
  > /tmp/m0260/07-walkforward.txt 2>&1; echo "EXIT=$?"; cat /tmp/m0260/07-walkforward.txt
```

**Expected:** one row — `M0260  <w> of 4   <yes|no>   <edge>   <verdict>` — and possibly a
`*** BUY SIGNAL ***` block. Read a buy signal the way M0258's handover had to: the arm that
cleared may be `M0260-M-NATIVE`, which is `M0072-Z2-RAWRANK` a third time under a third allocator
id. The cadence would then have earned none of it, and saying so is part of the analysis.

**Impact:** this records nothing. The fold verdict that *is* recorded was computed inside step 4's
transaction (`runner.py`, the `fold_record` block).

---

### Step 8: The folds, arm by arm — R2

**File:** `/tmp/m0260/folds.py` (throwaway)
**Change:** `lab walkforward` prints only the per-method headline (`commands/lab.py:2585-2637`):
folds won, stable, 2009-15 edge, verdict. **Which arm each fold picked is not printed anywhere.**
R2 requires it, so read it from the same `walkforward` API the command uses, against the same
recorded curves and the same benchmark.

Why it matters, stated before the number is seen: each fold picks its variant by MAR, so the
procedure structurally favours whichever arm trades least — here, the slowest gate. M0245's folds
picked its slowest rung in three of four. M0258's did **not** drift that way: two of its four
folds chose the zero rung. So this is a thing to check, not to assume in either direction. A fold
majority won by `M0260-M-G12` is, first of all, evidence about turnover.

```bash
cat > /tmp/m0260/folds.py <<'PYEOF'
"""Which arm each walk-forward fold picked for M0260, and whether it won. Reads only."""
import json, sqlite3
from datetime import date

from seer_engine.backtest import regime
from seer_engine.lab import hardgate
from seer_engine.lab import walkforward as wf

HIGH = (date(2009, 1, 1), date(2015, 10, 16))
db = sqlite3.connect("file:/home/miftah/seer/lab/lab.sqlite?mode=ro", uri=True)
db.row_factory = sqlite3.Row
# `start` and `end` are NOT decoration: hardgate.trial_deposits reads them off the row
# (hardgate.py:712) and raises IndexError without them.
rows = list(db.execute(
    "select n, method_id, candidate_id, start, end, curve_json from trials "
    "where window='dev' and curve_json is not null order by method_id, n"))

def curve_of(r):
    return [(date.fromisoformat(d), float(v)) for d, v in json.loads(r["curve_json"])]

bench_row = next(r for r in rows if r["candidate_id"] == regime.BENCH_CANDIDATE)
bench = curve_of(bench_row)
mine = [r for r in rows if r["method_id"] == "M0260"]
curves = {r["candidate_id"]: curve_of(r) for r in mine}
deps = {r["candidate_id"]: hardgate.trial_deposits(db, r, curves[r["candidate_id"]]) for r in mine}

the_folds = wf.folds([d for d, _ in bench])
rec = wf.Record("M0260", wf.evaluate(curves, bench, the_folds, deps))

print(f"{len(the_folds)} folds, {the_folds[0].eval_start} to {the_folds[-1].eval_end}\n")
hdr = f"{'fold':<5}{'train end':<12}{'evaluate':<24}{'picked':<18}{'train MAR':>10}{'its return':>12}{'bench':>10}  won?"
print(hdr); print("-" * len(hdr))
for p in rec.picks:
    got = "-" if p.got is None or p.got.total_return is None else f"{p.got.total_return*100:+.2f}%"
    bch = "-" if p.bench is None or p.bench.total_return is None else f"{p.bench.total_return*100:+.2f}%"
    tm = "-" if p.train_mar is None else f"{p.train_mar:.3f}"
    won = {True: "WON", False: "lost", None: "-"}[p.beat]
    print(f"{p.fold.index:<5}{str(p.fold.train_end):<12}"
          f"{str(p.fold.eval_start) + '..' + str(p.fold.eval_end):<24}"
          f"{str(p.picked):<18}{tm:>10}{got:>12}{bch:>10}  {won}")

print(f"\n{rec.won} of {len(rec.scored)} folds won; majority = {rec.majority}; stable = {rec.stable}")
picks = [p.picked for p in rec.picks if p.picked]
print("picks by arm:", {a: picks.count(a) for a in sorted(set(picks))})
print("\nwhole-arm 2009-2015, for the turnover reading:")
for cid in sorted(curves):
    s = wf.measure(curves[cid], HIGH[0], HIGH[1], deps[cid])
    if s:
        print(f"  {cid:<18} cagr {s.cagr*100:+.2f}%  fall {s.max_drawdown*100:.2f}%  MAR {s.mar:.3f}")
b = wf.measure(bench, *HIGH)
print(f"  {'(SPY hold)':<18} cagr {b.cagr*100:+.2f}%  fall {b.max_drawdown*100:.2f}%  MAR {b.mar:.3f}")
PYEOF
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
/home/miftah/seer/engine/.venv/bin/python /tmp/m0260/folds.py \
  > /tmp/m0260/08-folds.txt 2>&1; echo "EXIT=$?"; cat /tmp/m0260/08-folds.txt
```

**Expected:** four rows, each naming an arm. The `picks by arm` line is the R2 answer and it goes
into the analysis verbatim — in plain words, no candidate ids.

**Invariant 4 applies inside this table, and it is easy to miss.** `08-folds.txt`'s `its return`
and `bench` columns are `walkforward`'s `total_return` over a fold slice, and its whole-arm block
prints `cagr` and `MAR`. **None of those is the owner's money.** They are curve-shape numbers on a
deposit-matched curve, and quoting one as "what your money earned" is exactly the error invariant 4
exists to stop. Report the folds as **which arm each fold picked and whether it beat the benchmark
over that stretch** — won or lost, not a percentage — and keep every percentage in the analysis
and the handover on `trial_funding.mwr`. If a fold's size has to be given at all, say in the same
sentence that it is a curve-shape figure over a date slice and not a return on his deposits.

**This script was validated while this plan was written**, run verbatim against `M0258`. It
reproduced the handover's fold account exactly:

```
fold train end   evaluate                picked             train MAR  its return     bench  won?
1    2003-01-01  2003-01-31..2005-12-30  M0258-M-B30            0.592     +33.47%   +52.06%  lost
2    2006-01-01  2006-01-31..2008-12-31  M0258-M-B60            0.585      -6.52%   -24.63%  WON
3    2009-01-01  2009-01-30..2011-12-30  M0258-M-B0             0.435     +80.00%   +60.82%  WON
4    2012-01-01  2012-01-31..2014-12-31  M0258-M-B0             0.531     +75.27%   +65.91%  WON

3 of 4 folds won; majority = True; stable = False
picks by arm: {'M0258-M-B0': 2, 'M0258-M-B30': 1, 'M0258-M-B60': 1}
```

The folds are the same four date splits for every method (they come from the recorded SPY
buy-and-hold curve, not from the method), so M0260's table will carry these same four rows with
M0260's arm names in the `picked` column.

**Impact:** reads only; `?mode=ro` keeps the database untouched.

---

### Step 9: The control shape — D17

**File:** none — pure arithmetic over recorded rows. `lab control` opens no store and writes
nothing at all, so `web/data/lab.json` does not move and `lab stage` is not needed for it.

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab control M0260 \
  > /tmp/m0260/09-control.txt 2>&1; echo "EXIT=$?"; cat /tmp/m0260/09-control.txt
```

**Expected:** **six** rows classified `dose-response`, verdict `not-checked`, **no ratio and no
refuse**, closing with *"every control arm shown matches the shape of the arm it controls"*. Six
because phase 2's decision D-B2 put the literal phrase `dose-response` in all six rationales, the
two weekly arms included; step 1's `dose=` column already confirmed it before the run.
A ladder whose fastest rung is its own control has no drawn arm by design (`control_shape.py`:
`kind_of` reads `DOSE_MARKERS` out of each arm's `rationale`; a dose arm is listed and never
flagged).

**If D17 refuses anything, that is a finding to record, not to work around.** It would mean an
arm's rationale does not carry a dose marker and the shape checker read it as a drawn control —
and since the method file is frozen, the only honest response is to say so in the analysis and in
an insight. Do not edit the method file. Do not re-run. Nine dev-eligible methods already sit
D17-blocked for exactly this reason; the standing remedy is an amendment under the existing id,
which is phase 4's leftovers list, not this phase's work.

---

### Step 10: `lab costs` — the fee-versus-timing reading

**File:** `/home/miftah/seer/lab/lab.sqlite` (one journal observation per call)
**Change:** the primary fee-versus-timing reading comes free from the ladder itself: plot money
against turnover across `M-NATIVE, M-G3, M-G6, M-G12`. **A pure fee story improves
monotonically as the gate slows and the book trades less; a timing story peaks and turns.** That
shape is already in `06-ladder.tsv` and costs nothing.

`lab costs` adds the thing the ladder cannot show: what the slowdown is worth *at Gotrade's real
fee schedule against the lab's flat 0.1%*. It re-runs the named variant twice on the dev store, so
each call costs roughly two arms of wall clock (use step 3's measured figure), and it **appends
one observation to the lab journal** — there is no `--no-journal` on this subcommand
(`commands/lab.py:324-348`). Keep it to the two endpoints, plus the turning rung if the ladder
turns at an interior one.

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab costs M0260 --candidate M0260-M-NATIVE \
  > /tmp/m0260/10-costs-M-NATIVE.txt 2>&1; echo "EXIT=$?"; cat /tmp/m0260/10-costs-M-NATIVE.txt
```

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab costs M0260 --candidate M0260-M-G12 \
  > /tmp/m0260/10-costs-M-G12.txt 2>&1; echo "EXIT=$?"; cat /tmp/m0260/10-costs-M-G12.txt
```

Run a third only if the ladder's money peaks at an interior rung — substitute that arm's id:

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab costs M0260 --candidate M0260-M-G3 \
  > /tmp/m0260/10-costs-M-G3.txt 2>&1; echo "EXIT=$?"; cat /tmp/m0260/10-costs-M-G3.txt
```

**Expected:** each prints the variant at the flat 0.1% beside the same variant at Gotrade's real
fees. The comparison that matters is how the **real-minus-flat gap** moves along the ladder: if
the gap shrinks steadily as the gate slows, slowing the gate is partly a fee saving; if it barely
moves while the money swings points, the ladder is timing.

**Impact:** 2-3 journal rows and 4-6 book runs of wall clock. No trial, no status, no look.

---

### Step 11: Write the analysis and record it — one call, never piped

**File:** `/tmp/m0260/analysis.md` (input; the database is the record, so this file is not
committed), then `/home/miftah/seer/lab/lab.sqlite`.

**The register is M0258's, exactly.** The owner reads this. Plain language; **no method ids, no
candidate ids, no digests, no code, no column names**. Money is always
`trial_funding.mwr` — "what your money earned" — against the same deposits put into the index
(7.2% a year over this window). `total_return` and `cagr` are not quoted as returns anywhere; if
one has to be mentioned, say in the same sentence that it counts the owner's deposits as gains.

Required sections, in this order (M0258's shape):

1. `### <today's date>` then `## What was asked, and what was done` — the question, the six
   versions in plain words ("checks once a month", "checks once every three months", "checks twice
   a year", "checks once a year", "checks weekly", "checks weekly but only acts on the monthly
   reading"), and the benchmark sentence.
2. `## The comparisons that matter` — the paired differences, each on both money and worst fall.
3. `## The ladder` — a table: *how often it checks | your money earned | worst fall | trades*,
   for the **four** monthly rungs in order (monthly, quarterly, half-yearly, yearly). Then say in
   one sentence whether it is **humped, monotone or flat, and where it turns**. That sentence is
   the method's answer to R1; it is the headline. Say in the same place that the two-month rung
   was not run — it is phase 1's measured prior and a future amendment — so a reader does not read
   a four-rung ladder as a five-rung one with a hole in it.
4. `## Splitting the seven points` — the decomposition in plain words: of the seven points a year
   that checking monthly beat checking weekly, X came from picking stocks less often and Y came
   from reading the safety rule less often. Same split on the worst fall. Say that the two halves
   add to the whole by construction, so the split is a decomposition, not a second measurement.
5. `## The prediction written down before the run` — quote phase 2's pre-registered prediction and
   say plainly whether it held.
6. `## The reproduction check` — "the fastest version is the host book run again under a new name,
   and it came back ..." Name the six figures that matched. **Add the one sentence about the luck
   score**: the lab has now tried one more method, so the luck score is computed against a
   slightly larger pile of attempts and reads a touch lower than the recorded twin's; that is the
   bar moving, not the book changing.
7. `## What the out-of-sample stretches said` — step 8's `picks by arm`, in words, with the
   warning about picking by MAR stated and then answered by what actually happened.
8. `## The shape check` — step 9, in words.
9. `## Why` — the mechanism. Why a slower reading helps or stops helping, and what the turn point
   means.
10. `## What this does not settle` — the two slow crashes in this window; the sub-monthly rung's
    inseparable confound; the two weekly versions' schedule not being one a book can be promoted
    on; and that no part of the untouched window was spent.
11. `## My opinion` — the owner's own section. Say which checking speed you would actually run,
    whether it is worth a follow-up method id, and what you would not spend one on.

Write the file, then make **one** call. This is the trap: a `lab note --file` that is retried
double-appends an analysis the append-only triggers then make permanent, and a piped command hides
the exit code that would have told you the first call succeeded.

```bash
# (write /tmp/m0260/analysis.md first — Write tool or heredoc — then exactly this, once)
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab note M0260 \
  --file /tmp/m0260/analysis.md \
  --verdict "<ONE plain sentence, no ids: what reading the safety rule less often is worth on a book that holds stocks, and where it stops paying>" \
  > /tmp/m0260/11-note.txt 2>&1; echo "EXIT=$?"; cat /tmp/m0260/11-note.txt
```

Then verify it landed **once** — on the capture file, not on a pipe of the command:

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab show M0260 \
  > /tmp/m0260/11-show-after-note.txt 2>&1; echo "EXIT=$?"; \
grep -c "What was asked, and what was done" /tmp/m0260/11-show-after-note.txt; \
grep -c "My opinion" /tmp/m0260/11-show-after-note.txt
```

**Expected:** both counts are `1`. A `2` means the note was appended twice and the triggers make
that permanent — the only remedy is a further `lab note` saying so, and it must be reported to
phase 4 for the handover.

**Impact:** `methods.verdict` and one `method_analysis` row. Append-only.

---

### Step 12: Insights — what generalises past this method

**File:** `/home/miftah/seer/lab/lab.sqlite`
**Change:** one `synthesis` insight is mandatory; the others are conditional on what was measured.

Mandatory — the generalising claim about cadence:

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab insight \
  --kind synthesis --method M0260 \
  --title "<one line: where the gate's reading cadence turns, and what it is worth>" \
  --file /tmp/m0260/insight-cadence.md \
  > /tmp/m0260/12-insight-cadence.txt 2>&1; echo "EXIT=$?"; cat /tmp/m0260/12-insight-cadence.txt
```

Its body must carry, in plain language: the ladder's shape and turn point; the decomposition's two
halves; the fact that **every book in the lab inherits its gate cadence from however often it
happens to re-pick stocks, and the measured cost of that accident**; and the limit — the
sub-monthly rung is inseparably confounded on this chassis.

Conditional, and only if the thing happened:

- **`risk`** — if a fold majority was won by the slowest rung. The folds pick by MAR, so that is
  first of all evidence about turnover, and a reader who takes it as evidence for slow gating is
  reading it wrong. Record the warning beside the result.
- **`feature-wish`** — **only if a weekly arm wins something a promotable arm does not.**
  `sim.rules.PRESETS` holds `monthly-hold-frac-gotrade` but **not** `weekly-hold-frac-gotrade`
  (`m0063_earnings_day_jump.py:64`), so both weekly arms are diagnostic forever. Every slow rung
  lives in the allocator's params on the monthly preset and **is** promotable, so no
  quarterly/yearly preset wish is needed — say that explicitly rather than filing a wish for
  something the design deliberately avoided.
- **`observation`** — if D17 refused anything at step 9, or if a reproduction arm drifted.

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab insight \
  --kind risk --method M0260 \
  --title "<one line>" --file /tmp/m0260/insight-folds.md \
  > /tmp/m0260/12-insight-folds.txt 2>&1; echo "EXIT=$?"; cat /tmp/m0260/12-insight-folds.txt
```

Valid `--kind` values and nothing else: `observation`, `hypothesis`, `data-wish`, `feature-wish`,
`risk`, `synthesis` (`lab/store.py:136-138`).

---

### Step 13: Queue the follow-up idea — only if the result implies one

**File:** `/home/miftah/seer/lab/lab.sqlite` (one `methods` row at `idea`)
**Change:** `lab idea` mints the next free id. **Run it only if the measurement actually implies a
next question.** Do not queue one reflexively; an idea row is a claim on a future method id.

It is implied when, for instance: the ladder turns at an interior rung and the turn is worth
chasing on a *second* book (the relative-strength book wants different widths from this one, so it
may want a different cadence too); or the cadence effect survives on the slow rungs and the next
question is whether a second host reproduces it.

It is **not** implied when the ladder is flat — that closes the question, and the right record is
the insight plus a line in phase 4's "what is now dead" list.

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab idea \
  --name "<plain-language name>" \
  --family "<family>" \
  --source-kind variation \
  --parent M0260 \
  --source-ref "variation of M0260-<the winning rung>" \
  --hypothesis "<the question, in the register of a pre-registration>" \
  > /tmp/m0260/13-idea.txt 2>&1; echo "EXIT=$?"; cat /tmp/m0260/13-idea.txt
```

`--source-kind` must be one of `paper`, `blog`, `github`, `knowledge`, `variation` (`seed` is
refused by the parser).

---

### Step 14: `lab stage`, then the result commit from the main checkout with no pathspec

**File:** `/home/miftah/seer/lab/lab.sqlite`, `/home/miftah/seer/web/data/lab.json`
**Change:** `lab stage` regenerates the web snapshot beside the database's own repo and
`git add`s both, under an exclusive lock, with `cwd = /home/miftah/seer/lab`
(`commands/lab.py:3120-3142`). **It targets the MAIN checkout, from wherever it is invoked.**

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab stage \
  > /tmp/m0260/14-stage.txt 2>&1; echo "EXIT=$?"; cat /tmp/m0260/14-stage.txt
```

**Expected:** `staged /home/miftah/seer/lab/lab.sqlite` and
`staged /home/miftah/seer/web/data/lab.json`.

Confirm the main checkout's index holds exactly those two, and nothing else:

```bash
git -C /home/miftah/seer status --short > /tmp/m0260/14-status.txt 2>&1; echo "EXIT=$?"; \
cat /tmp/m0260/14-status.txt
```

Then commit **with no pathspec**. A pathspec re-reads the working tree and defeats the staging —
`lab stage` staged a snapshot taken under the write lock, and `git commit -- <paths>` would throw
it away and re-read whatever the file looks like at commit time.

```bash
git -C /home/miftah/seer commit -F - <<'MSGEOF' > /tmp/m0260/15-commit.txt 2>&1
lab: M0260 <dev-eligible|rejected> — <one plain sentence: what reading the safety gate less often is worth, and where it stops paying>

Six arms on M0072-Z2-RAWRANK's book, nothing moving but the rule set's cadence and the gate's
month-end reading anchor. The fastest monthly rung reproduced the host's recorded row on money,
worst fall, trades, turnover, exposure and profit factor; the weekly rung reproduced M0258's.

The headline is the split: of the <X> points a year and <Y> points of worst fall that reading the
gate monthly beat reading it weekly, <A> points came from re-picking stocks less often and <B>
from reading the gate less often. The two halves sum to the whole by construction.

The ladder is <humped|monotone|flat>, turning at <rung>.

No test-window look was spent; the count is still 4.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSGEOF
echo "EXIT=$?"; cat /tmp/m0260/15-commit.txt
```

**Impact:** the lab's record reaches git. The method file and its test are already committed on
the branch (step 2); this commit carries only the database and the web snapshot, in the main
checkout, which is where they live.

**Do not push.** `/home/miftah/seer` is on `main`; phase 4 merges the branch and pushes both.
Leave the commit local and tell phase 4 it exists.

---

### Step 15: Close out — the state phase 4 quotes

**File:** none.

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab status \
  > /tmp/m0260/16-final.txt 2>&1; echo "EXIT=$?"; \
sqlite3 -header -column "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" \
  "select 'dev trials', count(*) from trials where window='dev' union all \
   select 'test looks', count(*) from trials where window='test' union all \
   select 'methods', count(*) from methods union all \
   select 'insights', count(*) from insights;" >> /tmp/m0260/16-final.txt 2>&1; \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab next-id >> /tmp/m0260/16-final.txt 2>&1
cat /tmp/m0260/16-final.txt
```

And the tree is still green with the branch's code — Invariant 1 at the end of the phase:

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
/home/miftah/seer/engine/.venv/bin/python -m pytest -n0 engine/tests \
  > /tmp/m0260/16-posttest.txt 2>&1; echo "EXIT=$?"; tail -20 /tmp/m0260/16-posttest.txt
```

**Expected:** `test looks | 4`. `dev trials | 836` (830 + 6) if nothing else ran concurrently.
Green pytest.

---

## Failure branches

### A — `lab run M0260` exits 2 (the lab refused)

Nothing was written: every refusal in `preflight` (`runner.py:261-338`) is raised before
`research.load_store` is called. Read the **last line** of `/tmp/m0260/03-run.txt`; the messages
are distinct enough to tell them apart without guessing.

| message contains | cause | fix |
|---|---|---|
| `has uncommitted changes (...)` | phase 2's commit never landed, or something touched the method file after it | `git -C <worktree> status --porcelain -- m0260_gate_reading_cadence.py`; if it is a *modification*, it is a phase-2 escape — report it, do not amend the commit silently |
| `is not tracked by git` | the file was never `git add`ed, or `PYTHONPATH` points at a checkout where it does not exist | re-check step 6's `git_sha` logic: run `python -c "from seer_engine.lab.method import discover; print(discover()['M0260'][1])"` with the worktree's PYTHONPATH and confirm the path is under the worktree |
| `repeats <id>, which already ran on the dev window` | **two arms share one `config_digest`** — Invariant 10: `as_dict` does not render a params field, so e.g. `M-G3` and `M-G6` canonicalise identically. Or an arm is byte-identical to a recorded M0258/M0072 config | rerun step 1's arm dump; the collision is printed there. This is a phase-2 bug and the method file is **already frozen** — report to the coordinator; the resolution is phase 2's, not an edit here |
| `M0260 is already registered` / `dev-eligible` / `rejected` | the run already happened (a retry, or a parallel session) | **do not re-run.** `lab show M0260` and continue from step 5 |
| `parent M0258 is not in the lab` | phase 2's `parent_id` is wrong | phase-2 bug; report |
| `not priced at Gotrade's real fees` | `real_cost_problem` — a candidate's rules carry the lab's flat 0.1% | phase-2 bug; report |
| anything naming `coverage` | the fundamentals coverage floor fired | **do not reach for `--allow-coverage`.** M0258 ran this host book without it; a changed floor is a changed experiment. Report |
| anything naming `survivorship` / `purpose` / `window` | `SEER_RESEARCH_STORE` points at the wrong store | re-check it is `/home/miftah/seer/engine/.research`; **never rebuild** |

In every case: `lab run` wrote nothing, so the lab's N and the test-look count have not moved.
Verify that with step 0's read-only query before doing anything else.

### B — a reproduction arm does not reproduce

**This is a stop-and-report condition, not something to explain away in the analysis.**

M0258's own `M-B0` came back bit-identical to M0072's recorded row because the overlay hands the
host's own params to the host's own target builder and only the gate line differs. M0260 is built
the same way. A drift therefore means something moved — the store, the chassis, or the method
file's delegation.

- **If step 3's probe drifts (before the run):** stop. No trial has been recorded, the method id
  is unspent, and the pre-registration commit is the only thing that exists. Report to the
  coordinator with `/tmp/m0260/02-probe.txt`. The three things to check, in order:
  1. the store fingerprint printed by the probe, against `trial_provenance.price_fingerprint` for
     trial #829 — `sqlite3 "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" "select price_fingerprint from trial_provenance where trial_n=829;"`
  2. whether the allocator actually delegates to the host's own target builder with the host's own
     params (a phase-2 question, read-only here)
  3. whether `PYTHONPATH` resolved the worktree's `seer_engine` — a main-checkout `m0072` and a
     worktree `m0260` is a mixed run
- **If the drift only shows after step 4:** the trials are recorded and append-only. Then the
  drift **is** the finding. Record it as the headline of the `lab note`, record an `observation`
  insight naming the three checks above and their answers, and **do not quote the decomposition or
  the ladder as clean measurements** — every paired difference in the method rests on the
  reproduction. Report it to phase 4 so the handover leads with it.

Either way: do not re-run, do not edit the method file, do not spend a second method id.

### C — an arm errors or the anchor fell back mid-run

The symptom is not an exception; it is a silent all-cash stretch.
`f_factor.trend_on(history, data_date, params)` returns `False` when the symbol has no bar dated
exactly at the reading date or when fewer than 200 bars sit behind it
(`strategies/f_factor.py:234-253`), and the anchor falls back to `data_date` when no qualifying
month end is on hand (Appendix C). Either makes an arm quietly hold cash.

**How to see it:** read `exposure` in `/tmp/m0260/06-ladder.tsv`. The host book's is `0.6949`. An
arm materially below that — and especially a *slow* arm below a *fast* one, which the mechanism
cannot produce — is the tell. Trades far below 1208 on a monthly arm is the second tell.

**The diagnostic is phase 1's probe**, which exists for this:

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
/home/miftah/seer/engine/.venv/bin/python \
  docs/backtests/2026-10-19-gate-reading-cadence.py \
  --store /home/miftah/seer/engine/.research \
  > /tmp/m0260/C-anchor-probe.txt 2>&1; echo "EXIT=$?"; tail -40 /tmp/m0260/C-anchor-probe.txt
```

**Run it from the WORKTREE, with `--store` and `PYTHONPATH`.** Phase 1's script deliberately takes
an **absolute** `--store` (defaulting to `$SEER_RESEARCH_STORE`), unlike M0258's cadence study,
which hard-coded a relative `engine/.research` and so had to be run from the main checkout. That is
a correction of the precedent, and it is in phase 1's handoffs. It imports `seer_engine`, so
`PYTHONPATH` is not optional. Exit `0` means every structural check passed; exit `1` names the
failed check.

If the probe reports fallbacks or a minimum SPY bar count below 200 at some rung, that rung's
recorded trial is a measurement of a crippled arm. **It is still a recorded trial.** Report it in
the analysis as exactly that, exclude it from the ladder's shape claim, and record an
`observation` insight. Do not re-run and do not hide it.

### D — the run used the wrong `PYTHONPATH`

Caught by step 6, assertion (2): `trials.git_sha` for M0260 equals the **main checkout's** HEAD
rather than the worktree's pre-registration commit. That means `lab run` discovered — and
pre-registered — a method file other than the one on the branch.

If the main checkout has no `m0260_*.py`, the run would have refused with "no method M0260" and
nothing was written; redo step 4 with the environment line copied verbatim. If it somehow found
one, the recorded trials describe a file this plan did not pre-register: **stop, record nothing
further, and report to the coordinator immediately.** The method id is spent and the resolution is
an owner-level decision, not a phase decision.

### E — the run is much slower than expected

`lab run` has no `--only`; it runs all six candidates in one call. **Price it before paying it**:
step 3's probe is exactly that measurement, and it prints a projection
(`store load + 6 × one arm`).

**The measured baseline on this machine is 11.2 s to load the store and 4.9 s for one arm** (taken
while this plan was written, on `M0258-M-B0`, which is the same book). Six arms project to about
**40 seconds**. `lab run` adds the DSR moments, the funding and the fold record on top, so a
couple of minutes end to end is the honest expectation.

So a projection in the tens of minutes is not a scheduling problem — it is evidence that something
is wrong. Check, in order: that `SEER_RESEARCH_STORE` points at `/home/miftah/seer/engine/.research`
and not at a store being rebuilt; that the allocator is not doing per-session work the host book
does not (phase 2's `prepare` should delegate wholly to `ZJUMP`); and that nothing else is
competing for the one core.

If it genuinely is slow, run `lab run` in the background and wait on `/tmp/m0260/03-run.txt`
rather than on a foreground timeout. Do **not** split the run — there is no way to, and a partial
run would record a partial method.

One core: never add `-n auto` anywhere, and never override pytest's `addopts`.

---

## Verification

**Build:** nothing is built. `/home/miftah/seer/engine/.venv/bin/ruff check engine` from the
worktree, clean (CI lint is bugs only: E9 and F, minus F401).

**Tests:**
```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
docker start seer-pg >/dev/null 2>&1; \
PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
/home/miftah/seer/engine/.venv/bin/python -m pytest -n0 engine/tests \
  > /tmp/m0260/16-posttest.txt 2>&1; echo "EXIT=$?"; tail -20 /tmp/m0260/16-posttest.txt
```
Green, with no DB tests skipped. Run once before step 2's commit and once at step 15.

**Manual check:**
- `/tmp/m0260/05-verify.txt`: `methods.source_sha` == `sha256sum` of the committed method file;
  every `trials.git_sha` == the worktree's pre-registration commit (phase 2's); six distinct
  digests; test trials still `4`.
- `/tmp/m0260/06-decomp.txt`: both reproduction arms read `REPRODUCES`; the decomposition's sum
  residual is at machine epsilon.
- `/tmp/m0260/08-folds.txt`: four folds, each naming the arm it picked.
- `/tmp/m0260/09-control.txt`: `not-checked`, no refuse.
- `/tmp/m0260/11-show-after-note.txt`: the analysis appears **exactly once**.
- `git -C /home/miftah/seer log -1 --stat`: exactly `lab/lab.sqlite` and `web/data/lab.json`.

**Exit criteria:**
1. **Six** trials recorded under M0260, one per Appendix A arm, with six distinct config digests.
   (`MAX_VARIANTS = 6`; the `k = 2` rung is phase 1's prior and a future `Amendment`, not a trial.)
2. `M0260-M-NATIVE` reproduces `M0258-M-B0` and `M0260-W-NATIVE` reproduces `M0258-W-B0` on mwr,
   worst fall, trades, turnover, exposure and PF — or the drift is recorded as the method's
   headline finding.
3. The decomposition is computed and reported on both axes, with `(A−C) + (C−B) = (A−B)` to
   machine precision and `(A−B)` landing at M0258's measured `+7.0136` pts/yr and `11.6882` points
   of fall.
4. The ladder is reported arm by arm on money-weighted return, worst fall, trades, turnover,
   exposure, PF and DSR, with an explicit sentence saying whether it is humped, monotone or flat
   and where it turns.
5. The walk-forward folds are reported **arm by arm** (R2), with the MAR-selection caveat stated.
6. `lab control M0260` is read and its verdict recorded.
7. A verdict and a plain-language analysis are recorded, quoting `trial_funding.mwr` only (R5).
   **No `total_return`, `cagr` or `MAR` figure from `07-walkforward.txt` or `08-folds.txt` is
   quoted as a return on the owner's money**; the folds are reported as won/lost by arm.
8. At least one insight is journalled.
9. `lab stage` run; `lab/lab.sqlite` and `web/data/lab.json` committed from the main checkout with
   **no pathspec**.
10. Test-window trial count is **4** (R7); `lab test` was never invoked and
    `SEER_RESEARCH_TEST_STORE` was never read.
11. `pytest -n0 engine/tests` green and `ruff check engine` clean on the worktree.

---

## Handoffs

- **R4 — promotability in the handover (Phase 4).** This phase reads `sim.rules.PRESETS` only far
  enough to say which arms could ever be promoted; the handover's explicit paragraph — every slow
  rung is promotable because it lives in the allocator's params on `monthly-hold-frac-gotrade`,
  and **both weekly arms can never be, because `weekly-hold-frac-gotrade` is not in `PRESETS`** —
  is phase 4's to write. Phase 3 hands it `/tmp/m0260/06-ladder.tsv` and the fold table.
- **The handover's lab-state table (Phase 4).** `/tmp/m0260/16-final.txt` holds the four counts
  and the next free id. Phase 3 does not write the handover.
- **The merge and the push (Phase 4).** `feature/gate-reading-cadence` is never pushed by this
  phase, and the main checkout's result commit is left **local**. Phase 4 merges and pushes both.
  If phase 4's push is rejected, it must **not** `pull --rebase` over the live shared
  `lab.sqlite`: a rebase replays a stale database over rows other sessions are writing. Re-stage
  after any rebase and check that `trials.n` is contiguous.
- **`.workflows/todos.md` and the memory write (Phase 4).**
- **The nine D17-blocked dev-eligible methods** (M0047, M0201, M0202, M0208, M0215, M0221, M0225,
  M0227, M0243). Carried forward from M0258's handover; the remedy costs no method id. Not this
  phase's work even if step 9 touches the same machinery — it belongs to phase 4's leftovers list.
- **A `quarterly`/`yearly` member of `sim.rules.Cadence`.** Explicitly out of scope for the whole
  plan set: it would move `_CADENCE_ORDER`, `_first_of`, every `TradeRules` canonical text and the
  web mirror. The slow rungs live in allocator params precisely so this is never needed.
- **Any `lab reevaluate`, `lab promote`, `lab kin`, `lab exposure` or `lab survivorship` read.**
  Out of scope; none is required by any requirement this phase satisfies.

---

## Rollback

**Steps 0-3 are fully reversible.** Nothing has been written to the lab. Undo the pre-registration
commit with `git -C /home/miftah/.worktrees/seer/gate-reading-cadence reset --soft HEAD~1` (soft,
never `--hard` — this worktree shares an index with other sessions). The probe wrote only to
`/tmp/m0260`.

**Step 4 onward is not reversible by git.** `lab/lab.sqlite` is append-only and
trigger-enforced: `trials`, `trial_funding`, `insights` and `method_analysis` all refuse UPDATE
and DELETE, and `methods_source_sha_once` refuses to let `source_sha` move. A recorded trial stays
recorded.

**The rollback for a mis-run is the lab's own.** Leave the trials where they are, record a
correcting `lab note` and an `observation` insight saying exactly what went wrong, and **spend no
second method id**. This is a property of the lab, not a defect in the plan — and it is precisely
why the method file is frozen before the run rather than after, and why step 3 runs the
reproduction check *outside* the lab, where a stop still costs nothing.

**Never run `git -C /home/miftah/seer checkout -- lab/lab.sqlite` after step 4.** Before step 4 it
is the correct way to undo a connect-time migration; after step 4 it destroys recorded trials.

The step 14 commit alone can be undone with
`git -C /home/miftah/seer reset --soft HEAD~1` followed by a fresh `lab stage` — the database
content is unaffected either way.
