# Phase 1 result: the matched draw, measured on both poles

**Written:** 2026-10-19
**Verdict:** **GO**
**Rule:** `seer_engine.lab.control_draw`, `RULE_ID = "matched-draw-v1"` (Rule A, churn-matched)
**TaskID:** `P1-ENG-K9WR` · **Branch:** `feature/honest-control-redraw`

## The shape, measured by `lab control M0227 M0243`

| method | new control | controls | resolved by | trades x | turnover x | verdict |
|---|---|---|---|---|---|---|
| M0227 | `M0227-S20-PLC` | `M0227-S20` | sibling-stem | **0.99** | **0.99** | **ok** |
| M0243 | `M0243-NEAR20-PLC` | `M0243-NEAR20` | sibling-stem | **1.03** | **1.03** | **ok** |

Band: `WARN_BAND = (0.80, 1.25)` on BOTH axes is the bar, and both arms clear it with room on
both sides. `REFUSE_BAND = (0.50, 2.00)` is not the bar and was not the thing tested.

The two poles the rule was built to close, for comparison: `M0227-R20` sits at 0.07x/0.12x and
`M0243-NEAR20-R` at 3.01x/2.98x. Both are now `superseded by` their re-drawn twin. The lab's
previous best match, M0241's cohort mirror, measures 1.372x/1.131x — the matched draw beats it on
both axes on both poles.

Raw counts, from `trials` read-only: `S20` 608 trades / 3.42 turnover against `S20-PLC`'s 602 /
3.37; `NEAR20` 1285 / 6.92 against `NEAR20-PLC`'s 1325 / 7.11.

**The pre-run shape probe agreed with the recorded number**, which is the useful part for phases
3–7: the free basket-change proxy (Step 5b, no return computed) read **0.994** and **1.034**, and
`lab control` on the recorded trials read 0.99 and 1.03. The probe is worth running before any
`lab run --amend`; on this evidence it predicts the recorded ratio to within a point.

## The margins, in `trial_funding.mwr` (SPY TR on the same deposits: 7.19%/yr)

| arm | mwr | old control | old mwr | old margin | new control | new mwr | **new margin** |
|---|---|---|---|---|---|---|---|
| `M0227-S20` | 12.95 | `M0227-R20` | 7.73 | +5.22 | `M0227-S20-PLC` | **9.05** | **+3.90** |
| `M0243-NEAR20` | 10.45 | `M0243-NEAR20-R` | 4.38 | +6.07 | `M0243-NEAR20-PLC` | **8.83** | **+1.62** |

### M0227 — the pre-registered direction did NOT hold, and that is the finding

Pre-registered: an honest control pays about fifteen times R20's fee bill, so it **earns less**
than R20's 7.73% and S20's lead **widens** beyond +5.22. It earned **more** — 9.05% against
7.73% — and the lead **narrowed** to +3.90.

The amendment's own `expected_failure` (2) named this outcome before the run. What it says, read
back: R20's 41 trades in nineteen years are not a cheap book, they are a **stale** one — twenty
names drawn in 1996 and essentially never revisited, whose concentration drag outweighed the fee
bill it avoided. Paying fifteen times the fees to redraw the same blind book was worth +1.32
points a year, so on this chassis the sticky draw's handicap ran the *opposite* way from the one
the brief assumed. S20 still beats its honest control by 3.90 points, so the direction survives;
the number it is quoted at does not. **The +5.22 sentence is withdrawn and replaced by +3.90.**

### M0243 — the direction held, and the method's own success condition now fails

Pre-registered: the honest control pays about a third of NEAR20-R's fee bill, **earns more** than
4.38%, and NEAR20's lead **narrows from +6.07 or reverses**. It earned 8.83% and the lead narrowed
to **+1.62**. Direction held.

The consequence is larger than the number. M0243's own hypothesis set its success condition (2)
as *"NEAR20 must beat its placebo by 2 or more points a year"*, with `expected_failure` (1)
saying: *"if it does not, the nearness filter is doing all the work and this is M0015 in disguise,
which already lost."* At **+1.62 against an honestly-shaped opponent, that condition FAILS.** The
+6.07 it was passing on was 4.45 points of fee handicap and 1.62 points of everything else. This
is reported, not re-drawn (invariant 4, design §4); the direction closes rather than opening a
tuning exercise, exactly as the file already said it would.

## What phases 3-7 do now

**GO.** Apply `control_draw` exactly as `m0227_net_share_shrinkers.py` and
`m0243_shrinkers_near_high.py` do, and decide nothing:

- no new params dataclass — reuse the **params value** of the arm being replaced, let the new
  allocator id be the whole difference (invariant 12, with M0208's single named exception);
- new allocator id `<METHOD>-A<amendment seq>`; candidate id `<true target>-PLC` so
  `sibling-stem` resolves it (both pilots resolved that way, confirmed above);
- `tag` = the **book's** method id (not the allocator id), `seed=1`, `lookback_for(inner)`;
- `supersedes=("<the mis-shaped arm's id>",)` copied from the index's supersession mapping —
  both pilots' declarations fired correctly and `lab control` printed `superseded by`;
- copy the guard tests at the foot of `test_lab_control_draw.py`;
- **run the Step 5b shape probe before committing anything.** It costs ~90 seconds, computes no
  return, opens no database, and on both pilots predicted the recorded ratio to within 0.01.

Two contract notes worth repeating because they are easy to get wrong:

- `matched_partition` guarantees **fresh names ahead of dropped holdings** in `tail`. Phases 4, 5
  and 7 take the partition and depend on that ordering; it is pinned by
  `test_a_dropped_holding_is_never_re_taken_ahead_of_a_fresh_name`.
- `previous_decision_date` answers the previous **monthly** decision. Right for M0047 (its
  residual arms re-pick monthly); **wrong** for M0201/M0202, which derive their own
  `prev_repick_session` because their basket moves quarterly behind a 40% keep band.

**The margin is not the gate.** Both margins moved and one of them broke its method's own success
condition. Neither is a reason to re-draw. A second amendment on an arm is admissible only when
the **shape** missed `WARN_BAND`, never because a number came out wrong.

## One drift from the plan, recorded

The plan's `test_the_control_enters_and_exits_exactly_as_often_as_the_book_it_controls` ended with
`assert churn > checked`, an anti-vacuity guard on the fixture. It is unreachable: the plan's
selector ranked `labkit.smoke_market`'s eight members by raw close, and those price paths are
smooth and well separated, so that book entered **8 names over 22 monthly decisions** and the
assertions could have passed against a control matching nothing. The selector's own docstring said
it was "deliberately churny", so the selector was fixed rather than the check: it now ranks by the
trailing five-bar price change, which makes the paths cross — **17 entries over the same 22
decisions, moving on 15 of them.** The guard is now a moving majority of decisions plus at least
one multi-name move, both measured. An eight-member universe caps entries below one per decision
whatever the ranking, so the original form could not have been satisfied by any selector.

## Database

`git hash-object lab/lab.sqlite`:

| point | hash |
|---|---|
| before `lab run M0227 --amend` | `3969f1fa5d2066a42ed47716dd05a66050073592` |
| after M0227, before M0243 | `0765ae714ea75af418eed38b1db51adb8b7080fa` |
| after `lab run M0243 --amend` | `9892d3923b12e1013228c8f57b6ab324904922a2` |
| after `lab control` (read-only; unchanged) | `9892d3923b12e1013228c8f57b6ab324904922a2` |

Trials added: **2** (`#841 M0227-S20-PLC`, `#842 M0243-NEAR20-PLC`), both `window='dev'`.
Amendments added: **2** (`M0227` seq 1, `M0243` seq 1 — `method_amendments` now holds M0030/1,
M0053/1, M0225/1, M0227/1, M0243/1).
Luck gate N: **164 (policy methods), unchanged** — an amendment appends under the existing id.
Both methods' status: **dev-eligible, unchanged** — an amendment appends trials, it never moves a
verdict.
**Test-window looks spent: 0 — still 4 lifetime.** `lab test` was never invoked and
`SEER_RESEARCH_TEST_STORE` was never read.
`lab stage` was **not** run and `lab.sqlite` was **not** committed (invariant 8: phase 8 only).
