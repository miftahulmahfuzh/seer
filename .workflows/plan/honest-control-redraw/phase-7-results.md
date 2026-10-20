# Phase 7 result: M0215's sector-capped placebo pair, re-drawn and re-aimed

**Written:** 2026-10-20
**Verdict:** **shape repaired — both arms `ok` on both axes. The margins split: one widened, one narrowed.**
**Rule:** `seer_engine.lab.control_draw`, `RULE_ID = "matched-draw-v1"`, allocator `M0215-A1`
**TaskID:** `P2-ENG-Y3BQ` · **Branch:** `feature/honest-control-redraw`
**Pre-registration:** `c0f9bcf` (`method_amendments` M0215 seq 1, added 2026-10-19)
**Trials:** `#846 M0215-CTRL-PLC`, `#847 M0215-CAP4-PLC`, both `window='dev'`

> Measured on the night of 2026-10-19 by a session the tmux crash killed before it could report.
> The two trials are recorded and `lab run` refuses their digests; this file is the write-up of
> the rows that already exist, not a re-run.

## The shape, measured by `lab control M0215`

| | `M0215-CTRL-PLC` | `M0215-CAP4-PLC` |
|---|---|---|
| resolves to (rung) | `M0215-CTRL` (**sibling-stem**) | `M0215-CAP4` (**sibling-stem**) |
| trades, and the ratio to its target | 524 / 528 = **0.99** | 483 / 500 = **0.97** |
| turnover, and the ratio | 4.704 / 4.780 = **0.98** | 4.385 / 4.562 = **0.96** |
| verdict | **ok** | **ok** |
| `mwr` % | **8.46** | **8.73** |
| worst fall % | 21.6 | 22.3 |
| profit factor | 2.548 | 2.688 |

`WARN_BAND = [0.80, 1.25]` on **both** axes is the bar and both arms clear it on both, comfortably
— the four ratios sit between 0.96 and 0.99. The two arms they replace both sat at 0.34x trades
and 0.43x turnover, outside `REFUSE_BAND = [0.50, 2.00]` on both axes at once, which is the worst
shape of any control in this set. `lab control M0215` now prints:

    M0215-HASH       placebo  M0215-CTRL  first-declared  0.34  0.43  refuse  M0215-CTRL-PLC
    M0215-HASH-CAP4  placebo  M0215-CTRL  first-declared  0.34  0.43  refuse  M0215-CAP4-PLC -> M0215-CAP4
    M0215-CTRL-PLC   placebo  M0215-CTRL  sibling-stem    0.99  0.98      ok  —
    M0215-CAP4-PLC   placebo  M0215-CAP4  sibling-stem    0.97  0.96      ok  —

**Both defects the amendment named are closed.** The *shape* defect was a double stickiness: `draw`
keyed its hash on the calendar **quarter**, so three consecutive decision sessions saw an identical
order, and `choose` sorted held names **first**, so even across a quarter boundary a name already
in the book was re-picked ahead of the whole pool. Between them they held the book to 179 trades in
twenty years against the raise book's 528. The slot count was never wrong — `k = min(len(raisers),
top)` already took it from the real book — so churn is the only thing this amendment changed, and
the trade count moved 179 → 524 (2.93x) and 179 → 483 (2.70x). The *resolution* defect: `M0215-HASH-CAP4`'s
own stem `M0215-HASH` is itself a placebo, so `_eligible_targets` steps past it and the ladder fell
through to `first-declared`, reporting the **capped** placebo against the **uncapped** `M0215-CTRL`.
`<target>-PLC` puts each new arm on `sibling-stem` against the book it actually controls.

**The free shape probe run before the pre-registration predicted this almost exactly.** It
measured 1034 basket changes against `CTRL`'s 1038 (0.996x) and 952 against `CAP4`'s 982 (0.969x);
the realised trade ratios are 0.99 and 0.97. The one-step replay from an empty book — the
estimation risk `expected_failure` named second — cost nothing measurable here.

**Invariant 12 holds byte for byte.** Each new arm's `config_text` `params=` line is character-
identical to the line of the arm it replaces (`cap=None` / `cap=4`, `order='hash'`, `seed=1`, the
same `C63` calm block); the whole of the difference is `allocator=<M0215>` → `allocator=<M0215-A1>`.
No params dataclass was minted and the `hash order` / `placebo` draw markers the old arms carried
are kept, so both new arms classify `KIND_PLACEBO` and **are** shape-checked.

## The margins, in `trial_funding.mwr` (SPY TR on the same deposits: 7.19%/yr)

| arm | mwr | old control | old mwr | old margin | new control | new mwr | **new margin** | move |
|---|---|---|---|---|---|---|---|---|
| `M0215-CTRL` | 10.62 | `M0215-HASH` | 8.66 | +1.96 | `M0215-CTRL-PLC` | **8.46** | **+2.16** | widened 0.20 |
| `M0215-CAP4` | 10.34 | `M0215-HASH-CAP4` | 8.62 | +1.73 | `M0215-CAP4-PLC` | **8.73** | **+1.61** | **narrowed 0.11** |

Unlike M0047, **no published number here was quoted against the wrong arm.** `M0215-HASH-CAP4`
resolved to `CTRL` on the ladder's weakest rung, but the sentence actually written in the method
file pairs `CAP4` with `HASH-CAP4`, which is the intent-correct pairing. So there is one correction
to make per arm, not two: the opponent was handicapped, never mis-identified. The re-aiming matters
for D17 and for the difference-in-differences below, not for a withdrawn sentence.

Both honest controls still **beat SPY TR** on the same deposits — 8.46 and 8.73 against 7.19 — so a
blind hash-drawn book behind this chassis's gate, screen and SPY parking clears the index by
1.3–1.5 points a year before any raise signal is read. `M0215-CTRL`'s +3.44 points over SPY
decomposes as **+1.27 frame, +2.16 signal**.

The MAR lead widens on both arms, and more cleanly than the `mwr` lead does: `CTRL` 0.568 against
0.392 (was 0.395), `CAP4` 0.542 against 0.392 (was 0.409).

The profit-factor column is the second witness that the shape is repaired, and it reads the
opposite way to M0047's. The old placebos recorded PF **4.386** and **4.446** against their books'
3.523 and 3.482 — a control with a *higher* profit factor than the book it controls is the
signature of a book trading a third as often and paying a third of the fee bill. The honest
controls land at **2.548** and **2.688**, *below* their books, which is what a blind book paying
the same fee bill and picking worse is supposed to look like. The frozen-book signature is gone.

### The pre-registered direction held on one arm, under-shot it, and reversed on the other

Pre-registered, in three numbered predictions:

**(1) SHAPE** — both arms inside 0.80–1.25 on both axes, `CTRL-PLC` near 528 trades and 4.78
turnover, `CAP4-PLC` near 500 and 4.56. **Held, and precisely:** 524 / 4.704 and 483 / 4.385.

**(2) DIRECTION** — an honestly-shaped blind book trades about three times as often, pays about
three times the Gotrade fee bill, so both new arms earn **less** than 8.66% and 8.62%, and both
leads **widen by 0.3 to 1.5 points**.

| | predicted | observed | |
|---|---|---|---|
| `CTRL-PLC` earns less than 8.66 | yes | **8.46** | ✓ |
| `CAP4-PLC` earns less than 8.62 | yes | **8.73** | ✗ **earns more** |
| `CTRL` lead widens by 0.3–1.5 | +2.26 to +3.46 | **+2.16** (widened 0.20) | sign ✓, **below the band** |
| `CAP4` lead widens by 0.3–1.5 | +2.03 to +3.23 | **+1.61** (narrowed 0.11) | ✗ **reversed** |

So the fee argument is far weaker on this chassis than it was pre-registered to be. Trebling the
trade count of a twenty-name 1/20 book with the remainder parked in SPY cost `CTRL-PLC` 0.20
points a year and *paid* `CAP4-PLC` 0.11 — net of whatever the fresh monthly draw earned it. That
is the `expected_failure`'s first clause half-vindicated, but **not by the mechanism it named.**

The named mechanism was that the quarter-keyed draw froze a 2008-era book it could not exit (it
fell 21.9% against `CTRL`'s 18.7%) and that a monthly re-draw would ride the recovery out of a
shallower hole. It did not: `CTRL-PLC` fell **21.6%** against `HASH`'s 21.9% — a 0.3-point
improvement, nothing like a recovery — and `CAP4-PLC` fell **22.3%**, *deeper* than
`HASH-CAP4`'s 21.0%. The honest draws are not safer books. Whatever paid for the extra fees came
from the picking, not from the crash.

**(3) THE SUCCESS CONDITION** — see below. The verdict held; the number and the reason did not.

Nothing here promotes anything. `M0215-CTRL-PLC` and `M0215-CAP4-PLC` are placebos and both
recorded `eligible=0` on `DSR >= 0.90` (0.8485 and 0.8712 at N=164), which is what a blind book is
supposed to do and is not a verdict on `CTRL` or `CAP4`.

## M0215's own success condition is a difference between two placebos, and it fails by twice as much

The clause, written in the method file before any of this (`m0215:274-276`):

> "Success: a capped variant beats CTRL funded with the worst fall at or under 20%, a positive or
> less negative 2009-2015 edge and a majority of folds, **and its gain over CTRL is larger than
> HASH-CAP4's over HASH** (so the cap helps the raise book specifically)."

That last clause is a difference-in-differences across the placebo pair — the only method-level
bar in this set that is read **between two controls** rather than between a book and its control.
Re-drawing the pair therefore re-states a verdict, not a margin.

| half | arms | old | new |
|---|---|---|---|
| **real** (untouched; signal arms) | `M0215-CAP4` − `M0215-CTRL` | **−0.28** | **−0.28** |
| **placebo** | old: `HASH-CAP4` − `HASH` · new: `CAP4-PLC` − `CTRL-PLC` | **−0.05** | **+0.27** |
| **condition** `real > placebo` | | −0.28 > −0.05 → **FALSE by 0.23** | −0.28 > +0.27 → **FALSE by 0.55** |

Pre-registered: still FALSE, with the placebo half **within 0.15 points of zero**, because a cap of
four over twenty slots drawn blind from the whole screened pool should bind in far fewer months
than it does on a book that is 25% banks and 19% retailers.

Observed: **the verdict held and the stated reason did not.** The placebo half is **+0.27**, nearly
twice the predicted bound and on the *other side of zero*. The cap does not fail to bind on a blind
book — it binds and it **helps**, by +0.27 points a year, while on the real raise book the same cap
**costs** 0.28 points a year. The two halves of the difference-in-differences have opposite signs,
which is the strongest form the condition can fail in, and the measured gap doubles from 0.23 to
0.55 points.

**M0215's standing verdict survived its honest control — and the honest control made the case
against the cap stronger, not weaker.** The published FALSE at 0.23 points was a FALSE that a
reader could call noise on twenty names. The FALSE at 0.55 points, with the real and blind halves
pulling in opposite directions, is a sign test as well as a magnitude one: an industry cap of four
is worth something *positive* to an arbitrary twenty-name book of this shape and something
*negative* to the raise book specifically, which is the exact reverse of what the method was built
to show.

The one caution the pre-registration already wrote, and which still applies: `expected_failure`'s
third clause says that if the placebo half comes out larger than 0.15 points the honest reading may
be that **twenty names cannot resolve a 0.3-point cap effect at all**. That reading is live. What
the measurement can say without reservation is that the cap's effect on a blind book is not
negligible and not the same sign as its effect on the raise book, so the old −0.05 placebo half was
an artifact of a book that barely moved rather than evidence that a cap does nothing to an
arbitrary draw.

## `M0215-CAP3` and `M0215-CAP5` still have no control, deliberately

Four of M0215's six original arms are signal arms (`CTRL`, `CAP3`, `CAP4`, `CAP5`) and only two of
them were ever controlled. This amendment leaves `CAP3` and `CAP5` exactly where they were: no
placebo, nothing recorded against one, and so nothing for D17 to refuse and nothing to withdraw.
`M0215-CAP3-PLC` and `M0215-CAP5-PLC` are two arms this amendment could have carried and
deliberately does not — pricing the whole cap ladder against matched blind books is new
measurement, outside R2's "re-draw every mis-shaped control arm", and is a separate decision for
the owner. A method arm with no placebo produces an empty findings tuple, which
`control_shape.findings` documents as the correct answer rather than an error.

## The two supersession declarations, verbatim

| new arm | `supersedes=` | the superseded arm's verdict | the superseding arm's own target |
|---|---|---|---|
| `M0215-CTRL-PLC` | `("M0215-HASH",)` | `refuse` | `M0215-CTRL` — same as the superseded arm's |
| `M0215-CAP4-PLC` | `("M0215-HASH-CAP4",)` | `refuse` | **`M0215-CAP4`** — a re-point, printed as such |

Both match the index's supersession mapping row for row, and both fired: `lab control M0215` prints
`2 control arm(s) are superseded`.

**This is the method the reconciler's D17 decision was argued on, and the measurement is what
settles it.** Both old arms resolve to `M0215-CTRL`. Under the draft's target-equality predicate,
`M0215-CTRL-PLC` — a band-clean placebo of `CTRL` — would have excused **both** of them, including
`M0215-HASH-CAP4`, an arm that exists to price what a cap does and was never scored against `CTRL`
in spirit. The report above shows exactly why that would have been wrong: `CAP4-PLC`'s target is
`M0215-CAP4`, it earns 0.27 points more than `CTRL-PLC`, and a reader excusing `HASH-CAP4` on
`CTRL-PLC`'s shape would have retired the capped question on an uncapped answer. The explicit
declaration pairs each old arm with the arm drawn to replace it and with no other, and
`lab control` prints `M0215-CAP4-PLC -> M0215-CAP4` beside the superseded row so the re-point is
visible rather than silent.

## Database

`git hash-object lab/lab.sqlite`:

| point | hash |
|---|---|
| before / after `lab run M0215 --amend` | **not captured** — the session was killed before it could report |
| at the start of this write-up (DB committed on `main` at `fb1af1a`) | `288b7e478ba120145d0aa4189a3756cd75c9a248` |
| after `lab control M0215` (read-only; unchanged) | `288b7e478ba120145d0aa4189a3756cd75c9a248` |

The two run hashes are the one handoff item this phase cannot supply, the same gap phase 4 hit.
What stands in their place is in the database itself:

- both trials carry `run_at = 2026-10-19T12:55:44+00:00`, `store_fingerprint = 640fc25e5c7b8f42…`
  and `allocator_id = M0215-A1`;
- `method_amendments` M0215 seq 1 carries `added = 2026-10-19`, the same `run_at`, and
  `source_sha = ced6fa9b9e35e5a8…`, which is **`sha256` of the committed method file as it stands
  in the worktree right now** — verified this morning, byte for byte. The pre-registration is the
  file that ran.
- both rows carry `git_sha = 4e5359ab130b4ef5…`, which is **phase 5's M0201 pre-registration
  commit, not phase 7's `c0f9bcf`.** That is correct and not a mix-up: `git_sha` records branch
  HEAD at run time, the wave ran all five phases' arms minutes apart, and phase 5's commit had
  landed first. `c0f9bcf` is an ancestor of `4e5359a` (checked with `git merge-base --is-ancestor`),
  so M0215's amendment was committed before the run and `source_sha` pins which file text ran.

Trials added: **2** (`#846`, `#847`), both `window='dev'`.
Amendments added: **1** (`M0215` seq 1).
Luck gate N at run: **164 policy methods, unchanged** — an amendment appends under the existing id.
M0215's status: **unchanged** — an amendment appends trials, it never moves a verdict.
**Test-window looks spent: 0 — still 4 lifetime** (`trials WHERE window='test'` is 4).
`lab test` was never invoked and `SEER_RESEARCH_TEST_STORE` was never read.
`lab stage` was **not** run and `lab.sqlite` was **not** committed from this branch (invariant 8:
phase 8 only, after the merge).

## Tree

`ruff check engine` — **All checks passed!**
`PYTHONPATH=<worktree>/engine/src pytest engine/tests -q` — **5748 passed, 413 skipped** in 86s
(the skips are `PG_TEST_URL` and the live-store opt-ins). The four tests this phase turns on are
green by name: `test_every_recorded_configuration_still_digests_to_its_recorded_digest`,
`test_every_method_file_hashes_to_its_recorded_sha`,
`test_allocator_ids_are_unique_across_methods`, and
`test_allocator_contract[M0215-CTRL-PLC]` / `[M0215-CAP4-PLC]`.

`test_the_committed_snapshot_is_the_export_of_the_committed_database` is **green, and that is
not evidence of anything**: `store.COMMITTED_DB` resolves through `config.REPO_ROOT`, which
follows `PYTHONPATH`, so with the worktree on the path it compared this branch's untouched
`lab/lab.sqlite` against this branch's untouched `web/data/lab.json` — a stale pair that agrees
with itself. The real snapshot check is phase 8's, on the main checkout after `lab stage`
(invariant 8).

## For phase 8

- Both margins, in `mwr`: `CTRL` **+2.16** (was +1.96, widened 0.20), `CAP4` **+1.61** (was +1.73,
  **narrowed 0.11**). Nothing is withdrawn — no M0215 sentence was quoted against the wrong arm,
  only against a handicapped one.
- The pre-registered "both widen by 0.3–1.5" is the clearest **miss** in the set so far: one arm
  widened by a third of the lower bound, the other narrowed. Say so plainly in the close-out. The
  fee argument that drove it is weak on a twenty-slot book that parks its remainder in SPY.
- `expected_failure`'s named mechanism (the frozen 2008 book) did **not** operate: the honest draws
  fall 21.6% and 22.3% against the sticky draws' 21.9% and 21.0%. The monthly re-draw is not a
  safer book; it is a differently-picked one.
- **The headline finding of this phase is the success condition.** M0215's own bar is a difference
  between two placebos; it was FALSE by 0.23 against the handicapped pair and is FALSE by **0.55**
  against the honest one, with the placebo half flipping sign from −0.05 to **+0.27**. A cap of
  four helps an arbitrary blind twenty-name book and hurts the raise book. The verdict survived;
  the support for it changed completely, and in the opposite direction to M0047's.
- Both honest controls beat SPY TR (8.46 and 8.73 against 7.19): **the frame is worth +1.27 to
  +1.54 points a year before any raise signal.** `CTRL`'s +3.44 over SPY is +1.27 frame and +2.16
  signal.
- Profit factor is a clean witness here and reads opposite to M0047's: the old placebos' PF
  (4.39, 4.45) sat *above* their books (3.52, 3.48); the honest ones (2.55, 2.69) sit below.
- The two `supersedes` tuples are in the file as the index's mapping specifies; D17 reports both
  M0215 old arms superseded, so M0215 is unblocked on that axis.
- `M0215-CAP3` and `M0215-CAP5` have no control and that is left as it is, on purpose.
- The two run-time `lab.sqlite` hashes do not exist. Use `source_sha`/`run_at`/`git_sha`, and note
  that `git_sha` on these two rows is phase 5's commit, a descendant of M0215's own `c0f9bcf`.
