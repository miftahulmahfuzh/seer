# Phase 8 result: the close-out — measured, reconciled, written; not landed

**Written:** 2026-10-20
**Verdict:** **the set's deliverable is `docs/plans/HANDOVER_20261019-the-honest-control.md`.**
**TaskID:** `P3-ROOT-D7MX` · **Branch:** `feature/honest-control-redraw`
**Database:** read-only throughout. `git hash-object lab/lab.sqlite` was
`58d9601887db8e9b57ecf90b2f6e26fe22431767` before this phase's first read and after its last.
**Trials added: 0 · amendments added: 0 · insights added: 0 · test-window looks: 4 → 4.**

This phase ran no `lab run`, no `lab promote`, no `lab test`, no `lab stage`, and edited no source
file. It read the six results files, re-measured every claim in them against the database, settled
the set's one open reconciliation, and wrote the close-out.

## What was verified, not taken on trust

Every state the resume brief asserted was re-checked against `lab control` and `hardgate` on
2026-10-20, read-only. All of it held:

- **Five of nine unblocked** (M0047, M0202, M0215, M0227, M0243) — `mis_shaped_controls` returns
  `[]` for each. **Four still blocked**: M0201 (`['M0201-PLC1-MV10']`, warn at 0.79 turnover),
  M0208 (`['M0208-HASH-N20']`, warn at 0.73/0.76), M0221 (`['M0221-R50']`, warn at 1.95 turnover),
  M0225 (`['M0225-R50']`, no honest control drawn).
- **`lab control` on the nine: exit 0, ten arms superseded, four refusals live.** Thirteen `-PLC`
  arms recorded; `M0225-C50-PLC` absent, as phase 3 intended.
- **Phase 6 is right that M0208 must not be counted among the cleared.** `lab promote M0208` is
  refused exactly as before.
- Counts: dev trials **849** (836 + 13), amendments **11** (3 + 8), methods **275**, insights
  **470**, N **164** (`npolicy.effective_n`, policy `methods`), trial ids **1..853 contiguous**.

## The two things this phase measured that no earlier phase could

**1. The crossover is not supported, and the close-out says so.** Phase 6 proposed that phase 5's
"every lead widened" and its own "the lead narrowed" are one mechanism either side of a crossover
where churn stops paying for itself. Tested on all thirteen arms:

- The **sign split on the over-trading side is clean** — five arms at 2.25–2.27× all widened, both
  arms at 3.01× and above narrowed, crossover between 2.27× and 3.01×. Within-family correlations
  are −0.621 (B) and +0.903 (A), both the sign a single-peaked curve predicts.
- But it **fails three independent checks**. (a) Family A's *signs* contradict it 4 times in 6:
  M0227-R20 at 0.07×, where one curve demands the largest positive move of all thirteen, moved
  **−1.318**; M0047's arms place the peak below 0.55× while M0202's place it above 2.25×. (b) The
  **seed noise at a fixed handicap is as large as the effect** — M0202's two seeds differ by 1.55
  points of move and M0201's by 2.11, against a between-group gap of 2.24. (c) It is a
  **two-chassis-versus-two-chassis** split, p ≈ 1/6 under a random assignment. Pooled over all
  thirteen, `corr(handicap, Δmargin) = −0.215` and `corr(ln handicap, Δmargin) = +0.043`.
- **What all thirteen do support is a collapse of variance**: handicapped controls 4.381–11.381 %
  (sd 1.918), honest ones 6.047–9.532 % (sd 0.988), **3.77× less variance**; seed spreads 2.190 →
  0.079 and 1.737 → 0.187 (**27.6× and 9.3×**). A handicapped control is not a weaker or stronger
  opponent — it is an arbitrary one, arbitrary to within more than any margin in the set.

**2. `hardgate.check` tests the folds before D17, so three of the four live D17 refusals are
inert.** For M0201, M0221 and M0225 the fold-majority clause raises first and D17 is never the
sentence `lab promote` prints. **M0208 is the only method of the nine whose operative clause is
D17** — it clears the fold majority 3 of 4, its promoted variant `M0208-CGO-N40` 3 of 4, and the
survivorship drawdown bar — and behind D17 stands the **kin rule**, `failed_kin(M0208) =
('M0002',)`. So the gate takes none of the nine, and for eight of them D17 was never the blocker.

## The reconciliations the close-out carries

- **Four causes of a missing supersession, not five.** The set's running count numbered rows in a
  table that included two methods with *no* missing supersession, and never numbered M0225. The
  four are: structural (M0221), near miss (M0201), estimator (M0208), never drawn (M0225).
- **Four conditions moved FAIL → PASS on three methods — and one moved PASS → FAIL.** M0243's own
  2-point bar passed at +6.068 against a 3.01× opponent and **fails at +1.619** against an honest
  one. Phases 4, 5 and 6 each wrote that honest controls were the rare thing that improves a
  verdict; none put M0243 beside it. With M0215 made worse (FALSE by 0.235 → 0.550, placebo half
  flipping −0.047 → +0.268) and M0208 unchanged, the honest scoreboard is **3 better, 1 worse,
  1 made-worse-same-verdict, 1 unchanged**.

## Four published sentences the phases missed

The six results files named four withdrawals. A sweep of `methods.analysis` and `methods.verdict`
found four more, three of them in the **verdict** string — which is what the owner reads first:

1. **M0201's verdict**: *"did no better than random picks of the same shape"* — the book is above
   **both** honest seeds by +2.395 and +2.475, seeds 0.079 apart. With its analysis twin (*"now
   sits inside the placebo's range … below placebo seed 1"*), this is M0201's central published
   claim and the honest control reverses it.
2. **M0202's verdict** carries both withdrawn claims at once (*"a meaningless book … passed it
   too"*, *"only 1.4 points a year"*).
3. **M0208's verdict**: *"beat … a meaningless book by 6 points"* — the +5.87 rounded; needs the
   same `provisional` flag as the +4.35.
4. **M0243's analysis**: *"A blind draw from the same pool, **paying the same fees**, loses by six
   points a year. That is the strongest control result in this family."* It traded **3.01×** and
   turned over **2.98×**; the honest gap is **+1.619**, the weakest band-clean margin in the set.

Plus one correction to a phase's own claim: phase 4 recorded M0047's +1.28 as *"a number no
published sentence ever used."* `methods.analysis` for M0047 says *"beat the random picks sized the
same way by 1.3 points a year … under size weights the ranking adds less than the bar demands"* —
so that conclusion is **reversed**, not merely unquoted. One sentence **survived**: M0215's "about
two points a year" (+1.962 → +2.163), and M0215's analysis is the only one of the nine that wrote
its own handicap caveat down at the time.

## Carried, not applied

Both recorded as leftovers 2 and 3 of the handover, with the numbers that make each case:

- **`control_draw.matched_names` should carry a shadow of the real held set forward** rather than
  re-deriving `real_prev` from the plain top-N (phase 6; measured 0.487× on M0208, uniform across
  eras). It is phase 1's module and **five recorded arms depend on its contract**.
- **The weight-vector remedy for weight-varying chassis** (phase 3): `E50` 1.60× on identical
  names and identical trades vs `C50-PLC`'s 1.95× on matched churn. It is a *second* mechanism for
  three of nine chassis, so a rule needing it has already failed R1.

## The forks this phase settled

⚖ **Do not land the set.** The phase-8 plan has this phase merge, stage twice, journal, commit and
push. **Rung 5** — the invoking instruction, and `/implement` Step 5a's own rule: `swarm.py find`
returns `{"swarm": true, "coordinator": "orch-honest-control-redraw"}`, and the merge belongs to
the set's coordinator. Nothing was merged, pushed or deleted.

⚖ **Do not journal the four insights; write them and hand them over.** `insights` is append-only,
and a row written here would move `lab.sqlite` past the snapshot the coordinator has already
staged on `main`, turning `test_the_committed_snapshot_is_the_export_of_the_committed_database`
red with no `lab stage` available to this phase (invariant 8) to repair it. **Rung: the tie-break
"take the reversible option"** — the bodies are on the branch at
`.workflows/plan/honest-control-redraw/insights/`, measurement slots filled, with the exact
no-pipe commands in that directory's `README.md`, to run **after the merge and before the final
`lab stage`**.

⚖ **Insight 2's pre-registered title is not published.** The plan proposed *"An over-trading
control over-pays its fees, and the lead it concedes is fee drag"*, which is the crossover claim
the measurement refutes. **Rung 1, invariant 4 and design §4**: a measurement is reported as it
landed. The title is now *"An over-trading control's handicap is arbitrary, not a fee drag of
known sign."*

⚖ **The task card's exit criteria cannot be met and are not force-fit.** They ask for "all
fourteen new arms `ok`", "all fourteen old arms superseded" and "D17 no longer refuses any of the
nine". Thirteen arms exist, ten are superseded, and four refusals stand. **Rung 1, invariant 13**:
a shape miss is a recorded STOP, and the close-out reports it as the set's headline rather than as
a footnote. The phase-8 plan's own Step 9 anticipated exactly this and prescribes the partial-set
document, which is what was written.

## Files

- `docs/plans/HANDOVER_20261019-the-honest-control.md` (new) — the close-out
- `.workflows/plan/honest-control-redraw/insights/{A-family,B-family,D17-supersede,matched-draw}.txt`
  and `README.md` (new) — written, not journalled
- `.workflows/plan/honest-control-redraw/phase-8-results.md` (this file)
- `docs/plans/HONEST_CONTROL_REDRAW_PLAN.md` — Phases table TaskIDs and `**Status:**`, which
  phases 1 and 4 deliberately left to this phase
- `.workflows/todos.md` — `P3-ROOT-D7MX`

**Not** `lab/lab.sqlite`, **not** `web/data/lab.json` (invariant 8).

## Tree

`ruff check engine` — **All checks passed!**
`PYTHONPATH=<worktree>/engine/src pytest engine/tests -q` — **5748 passed, 413 skipped** (the
skips are `PG_TEST_URL` and the live-store opt-ins). This phase changed no code, so the suite is
phase 6's tree unchanged; it was re-run to confirm.
