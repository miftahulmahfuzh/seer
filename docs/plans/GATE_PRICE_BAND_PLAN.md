# Plan: M0258 — a price band on the SPY-200 gate, on a book that holds stocks

**Slug:** gate-price-band
**Date:** 2026-10-19 13:55 UTC+7
**Analysis:** `docs/analyzer/20261019-135550-B4K2_code_analyzer.md`
**Worktree:** `~/.worktrees/seer/gate-price-band`
**Branch:** `feature/gate-price-band` (base: `origin/main` @ `84123cb`)
**Phases:** 1
**Status:** complete
**Coordinator:** —

---

## Why

The user's rationale, verbatim:

> Build: one pre-registered lab method (M0258 is the next free id) that carries a PRICE BAND around
> the SPY-200 gate — exit b% below the 200-day average, re-enter b% above — measured on a book that
> actually holds stocks, because every number in the brief is SPY alone and that gap is the single
> biggest reason this might not survive.
>
> It needs, at minimum: (1) the band arm; (2) a bare-gate arm on the SAME book, so the comparison is
> a paired difference and not a comparison against the lab's history; (3) a dose-response ladder
> across the band (the plateau from 1.5% to 6% is the evidence — a monotone response across it is
> far stronger than one good value); and (4) a control arm matched to the book's OWN trade count and
> turnover, or hard gate D17 will refuse the method at promotion. The band cuts turnover sharply, so
> a control drawn at the bare gate's trade count is mis-shaped by construction — read `lab control`
> before drawing it.
>
> The band CANNOT ride on FactorParams.trend: it renders as "SPY:200" in config_text and widening it
> would move every recorded config digest in the lab. It needs a new method file behind a NEW
> ALLOCATOR ID. That costs one method id and that is the correct price.
>
> Do not spend a test-window look. Four are spent and all four failed; the band must clear the dev
> screen and a majority of walk-forward folds before anyone argues for one.

**One concern, stated once, then built around.** The lab has already run R1 + R2 on a stock book:
`M0101-BAND-3` / `M0101-BAND-5` against `M0101-CTRL`, where the band cost **0.18 and 0.52 funded
points a year** and fell **1.68 points deeper**. And the handover's headline compares the band
against a **daily-acting** baseline no lab book runs: measured for this plan, the band's worth is a
monotone function of how often the gate is read and reaches zero at the lab's own monthly cadence.
The lab has even recorded the swing already, on SPY alone — the band is worth **−0.40 pts/yr** when
the gate is read monthly (`M0084-BAND3-M` vs `M0084-MONTHLY`) and **+3.42 pts/yr** when it is read
weekly (`M0084-BAND3-W` vs `M0084-WEEKLY`), a 3.82-point swing from cadence alone.

So the method is built to answer the question that is still open — *is the band's worth a function
of the gate's reading cadence, on a book that holds stocks?* — which carries R1–R4 inside it and
makes a null informative instead of a repeat. See `## Decisions` D1 and D4, and the analysis
document's *Key Considerations* §1–§2.

**One correction inherited by everything below.** `trials.total_return` and `cagr` are not returns
on a funded book — they count the owner's deposits as gains, deliberately (`metrics.py`). Every
figure in this plan set is the **money-weighted** return from `trial_funding.mwr`, which is what
the owner's money actually earned. An early draft of the analysis quoted the curve-shape field as
a percentage; it is corrected.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | A band arm: exit `b%` below the 200-day average, re-enter `b%` above, on a book that holds stocks | 1 |
| R2 | A bare-gate arm on the SAME book, so the comparison is a paired difference | 1 |
| R3 | A dose-response ladder across the band (the 1.5%–6% plateau), not one good value | 1 |
| R4 | A control arm matched to the book's own trade count and turnover, so D17 cannot refuse it | 1 |
| R5 | A new method file behind a NEW allocator id — the band must not ride on `FactorParams.trend` | 1 |
| R6 | No test-window look: the dev screen and a majority of walk-forward folds first | 1 |

## Scope

**In scope**
- `engine/src/seer_engine/lab/methods/m0258_gate_price_band.py` — a new overlay allocator with
  `id = "M0258"` that holds `M0072-Z2-RAWRANK`'s book and replaces only its gate reading, plus
  `METHOD` with six pre-registered candidates.
- `engine/tests/test_lab_m0258_band.py` — the properties the generic contract test cannot see.
- `docs/backtests/2026-10-19-gate-band-cadence.{py,md}` — the cadence grid the hypothesis cites,
  re-runnable, beside the study it corrects.
- The full lab run protocol: commit (the pre-registration) → `lab run M0258` → `lab note` →
  `lab insight` → `lab idea` → `lab stage` → commit the staged pair in the main checkout.
- `docs/plans/HANDOVER_20261019-the-gate-price-band.md`.

**Out of scope, and why**
- `lab test` / any test-window look — R6, and the brief forbids it outright.
- `lab promote` — this method is a measurement; promotion is the next session's call if it earns it.
- Editing `m0101.py`, `m0084.py` or `m0072.py` — frozen against their recorded `source_sha`.
- Widening `FactorParams.trend` — R5; it would move every recorded config digest.
- Adding a rule-set preset to `sim.rules.PRESETS` — the weekly arms are diagnostic and the plan
  says so rather than minting a preset to make them promotable.
- The handover's §6 leftovers (the nine D17-blocked methods, the buyback holdability problem,
  insight 452's correction row, M0157's standing text, P2-ENG-N3LB, P3-ENG-V2KQ) — none is this
  method, and one of them (452's correction) is queued as the next idea instead.

## Invariants

Every one of these is checkable, and a phase that breaks one is not done.

1. **No recorded row moves.** `lab/lab.sqlite`'s `trials`, `methods.source_sha`, `insights` and
   `ideas_seen` are append-only and trigger-protected. `test_every_recorded_configuration_still_digests_to_its_recorded_digest`
   and `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` must stay green.
2. **No existing method file is edited.** `band_on` is **imported** from `m0101`, never copied or
   changed; `ZJUMP`, `ZParams`, `JUMP20` are imported from `m0072`.
3. **`lookback` equals M0072's exactly**, so M0258's dev window starts `1996-01-03` like its host's
   and the `b = 0` arm is a reproduction rather than an approximation. `SCAN` is never added to it.
4. **The method file is pure** — no clock, randomness, network, file or print; it reads only bars
   dated ≤ `data_date`. `test_method_source_is_pure` enforces it.
5. **The commit is the pre-registration.** `hypothesis` and `expected_failure` are written and
   committed *before* `lab run` sees a number, and are never edited afterwards.
6. **No test-window look.** `lab test` is never invoked, not even with `--dry-run`.
7. **The engine suite and `ruff` are green at the end**, and `web/data/lab.json` agrees with
   `lab/lab.sqlite` row for row (`test_lab_snapshot.py`, which is red between a lab write and
   `lab stage` by design).
8. **Never judge a `lab` command by a piped exit code.** Redirect to a file and echo `$?`; a
   `grep`/`head` owns the pipeline's status and this shell also prints a spurious
   `setValueForKeyFakeAssocArray … _encode` line on startup.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | M0258: pre-register, run and record the banded gate | R1, R2, R3, R4, R5, R6 | `engine/src/seer_engine/lab` | 6 | — | HARD | `.workflows/plan/gate-price-band/phase-1.md` | `P1-ENG-IPVX` ✅ (done 2026-10-19) | — |

### Phase 1 — M0258: pre-register, run and record the banded gate
**Satisfies:** R1, R2, R3, R4, R5, R6
**Owns:** the cadence study (script + writeup); the method file and its test module; the commit
that pre-registers it; `lab run M0258`; the analysis, verdict, insight and next idea; `lab stage`
and the staged commit in the main checkout; the handover.
**Does not touch:** any existing method file, `FactorParams`, `sim.rules.PRESETS`,
`lab/hardgate.py`, `lab/control_shape.py`, the test window, or any recorded row.
**Exit criteria:**
- `engine/.venv/bin/pytest engine/tests -n0` green and `engine/.venv/bin/ruff check engine` clean
- `lab run M0258` exited **0** and recorded six dev trials plus one `method_folds` row
- `lab show M0258` prints the six arms; `lab control M0258` reports no `refuse`
- a `lab note` analysis ending in a `My opinion:` paragraph, a verdict line, ≥1 insight, ≥1 queued idea
- `lab stage` run and both `lab/lab.sqlite` and `web/data/lab.json` committed **from the index** in
  the main checkout
- test-window looks still read **4**; `lab status` N moved by exactly one method
- the handover written

## The six arms

All six hold `M0072-Z2-RAWRANK`'s book verbatim — `ZParams(JUMP20, z_min=Decimal("2"),
rank="raw")`: F4's screen, 20 slots at 5%, SPY in the empty ones, fractional at Gotrade's real fees
on the owner's monthly top-ups. Only the gate reading and the cadence differ.

| candidate | rules | `band` | what it is |
|---|---|---|---|
| `M0258-M-B0` | `monthly-hold-frac-gotrade` | `0` | the paired bare gate (R2) and the ladder's zero dose; must reproduce `M0072-Z2-RAWRANK` |
| `M0258-M-B15` | monthly | `0.015` | the plateau's lower edge |
| `M0258-M-B30` | monthly | `0.03` | **the band arm** (R1), the handover's value |
| `M0258-M-B60` | monthly | `0.06` | the plateau's upper edge |
| `M0258-W-B0` | `weekly-hold-frac-gotrade` | `0` | the same book, gate read weekly |
| `M0258-W-B30` | weekly | `0.03` | the same book, band read weekly |

Arms 1–4 are the dose-response ladder (R3) and, with the zero rung, the control (R4 — see D1).
Arms 5–6 turn a predicted null into a measured mechanism.

**The pre-registered prediction**, written before the run:
`(W-B30 − W-B0) ≫ (M-B30 − M-B0) ≈ 0` on both return and worst fall. A band and a slow reading
suppress the same thing — flips shorter than the band is wide, flips shorter than the gap between
readings — so once the gate is only read monthly there is nothing left for the band to suppress.
If instead the monthly pair shows a real gap, the handover's finding survives contact with a book
that holds stocks and the lab has a genuinely better gate.


## Verified against the running system before planning

Nothing below is inferred. Each was run on this machine at `main` @ `84123cb`.

| Claim | Measured |
|---|---|
| `M0258` is the next free id | `lab next-id` → `M0258` |
| the band at `b = 0` is the lab's gate | `band_on(SPY, d, 200, 0.0) == trend_on(...)` on **all 473** smoke sessions, **0** differences, 163 reading on |
| the band is genuinely wired in | against `b = 0`, `b = 0.015` differs on **9** sessions, `b = 0.03` on **22**, `b = 0.06` on **25**, of 473 |
| the arms return targets, so `test_allocator_contract` cannot fail "proved nothing" | every rung non-empty on 4 of 6 probes; the gate reads on 4–5 of 6 |
| the overlay's lookback | `ZJUMP.lookback(BOOK) == 253`, under the 473-bar fixture cap |
| a `trend=None` twin would **not** have broken the lookback | `factor_lookback` / `jump_lookback` / `ZJUMP.lookback` / `ZJUMP.symbols` all identical on the twin — the private-call justification is the recorded configuration, not the lookback |
| D17 never refuses these | `lab control M0101 M0084 M0245 M0197` → one row, `M0245-FALL63`, `dose-response`, `not-checked`; zero refusals |
| the seen keys are free | `lab seen --find` → 0 rows for `gate-cadence-dose-response` and `banded-gate-on-an-event-book`; `concept:banded-trend-switch` is M0101's |
| the cadence axis is clean | `monthly-hold-frac-gotrade` and `weekly-hold-frac-gotrade` differ in exactly two fields, `cadence` and `id` (dataclass diff) |
| the weekly rule set is not promotable | `weekly-hold-frac-gotrade` is absent from `sim.rules.PRESETS` |
| a worktree can run the suite | `PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/pytest` → 9 passed in the worktree |
| the lab baseline to diff against afterwards | 824 dev trials + 4 test looks = 828 rows, contiguous `n` 1..828; 271 methods; 464 insights; DSR N = **162** |

---

## Reconciliation Log

single phase — nothing to reconcile.

---

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| R4 asks for a trade-count-matched control arm, but D17 refuses only *placebo-marked* arms and never refuses a method with no control at all | **No placebo arm.** The `b = 0 / 1.5 / 3 / 6` ladder is the control; `b = 0` is the paired bare gate | 6: verified code behaviour over a stated premise — `hardgate.py` (D17) *"It does not refuse a method with no control arm"*, `control_shape.DOSE_MARKERS` tested before `DRAW_MARKERS`, and `lab control M0101 M0084 M0245 M0197` reporting one `not-checked` row and zero refusals across every gate method the lab holds. A constructible hash-timed placebo lands near **7×** the arm it controls, outside `REFUSE_BAND = (0.5, 2.0)`; a shape-matched one needs the band's realised path, which is look-ahead |
| Which book hosts the band — the user left it to the planner | **`M0072-Z2-RAWRANK`** (standardised earnings-day jumps) | 5: the user's *"Decide for yourself ... whether this rides on an existing book's chassis or a new one"*. It is one of only three kin-clean *Promotable now* books, and the only one whose engine is cadence-robust (its hold is counted in sessions; its parent M0063 ran the identical book weekly **and** monthly). `M0197`'s chooser keys its re-pick on `data_date.month`, so it cannot carry a weekly arm |
| Re-implement the band, or import `m0101.band_on` | **Import it verbatim** | 6: surrounding convention — `m0084` already imports it, so M0258's band is literally the band the lab priced twice, and "you implemented a different band" is removed as an explanation of any difference |
| Six monthly rungs, or four monthly rungs plus a weekly pair | **Four monthly + weekly pair** | 5: the user wrote *"at minimum"*, and the measured cadence ladder (daily +1.82 / weekly +2.52 / monthly −0.12 pts/yr) makes a monthly-only design a predicted null. Two slots convert that null into a difference-in-differences with a sign predicted before the run |
| `family` — the gate family or the book's family | **`stock-event-drift`**, `parent_id="M0072"` | 6: M0101's precedent verbatim (*"It ranks on dividend raises, so the family stays dividend-change-drift"*), and the memory rule *set `parent_id` to the method whose engine actually runs*. Both D4 kin sets read clean: no ancestor or family member is `test-failed` |
| `b = 0` through `band_on`, or through `trend_on` | **`trend_on` on the `b = 0` path**, plus a test asserting `band_on(b=0) ≡ trend_on` over the dev tape | 1: invariant 3 — the reproduction must be exact, and `band_on`'s `isfinite` guard is one edge case away from `trend_on`. The equivalence is then proven by the test rather than assumed by the run |
| One phase or several | **One phase, one `/implement` session, no orchestrator** | 5: the project's own `explore-and-experiment-new-method` skill defines write → test → commit → run → note → stage as **one run**; splitting it across sessions invites the recorded `rebase replays a stale lab.sqlite` hazard on a shared append-only database, and buys no parallelism because every step depends on the last |
| The weekly arms use a rule set that is not in `sim.rules.PRESETS` | **Use `m0063.WEEKLY_HOLD_FRAC_GOTRADE` anyway and say so in the file** | 4: the Requirements table — the weekly arms are diagnostic; the promotable arm is monthly. The preset differs from the monthly one in exactly two fields (`cadence`, `id`), verified by dataclass diff, so the cadence axis stays clean; minting a preset would be scope the user did not ask for |

## Open Questions

None. Every fork above was decided from the ladder and recorded; no branch of any of them is
irreversible (a method id is the only spend, and it is the one the brief authorised).

## Rollback

- Before `lab run`: `git -C ~/.worktrees/seer/gate-price-band checkout -- .` and delete the new
  files; nothing was recorded, no id was spent.
- After `lab run`: **there is no rollback.** `trials`, `method_amendments`, `insights` and
  `ideas_seen` are append-only and trigger-protected, and the method id is spent. That is the
  design, and it is why the pre-registration is committed first. A wrong *verdict* is corrected by
  `lab note` with a new verdict line; a wrong *insight* by appending a correction row, never an edit.
- The worktree and branch: `git worktree remove ~/.worktrees/seer/gate-price-band` and
  `git branch -D feature/gate-price-band`. The method file and the staged lab pair will already be
  on `main` by then, by the lab's own protocol — that is intended, not a leak.

## Next

Execute the single phase:

    /implement -f docs/plans/GATE_PRICE_BAND_PLAN.md --phase 1
