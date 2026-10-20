# Coordinator decisions after phase 1, 2026-10-20

## 1. M0201 and M0202 get NO shadow. Phase 1's `shadow_needed = [M0208]` stands.

Phase 1 handed these up rather than absorbing them, correctly: both read **0.920**, inside the
band by exactly 0.020, which is borderline under the plan's own rule, and their **2009-2015 era
reads 0.827 — outside the band on its own**, in the era every owner-facing judgement is made in,
averaged away by a 1.034 in 2003-2008.

Decided: no shadow, for a reason stronger than "borderline". **Their K curve runs BACKWARDS**
(0.966 → 0.947 → 0.946), so a shadow would be an *active harm* on this chassis, not merely
unnecessary. Phase 4 reached the same place independently from the weight axis: M0201's entrant
rung is already 0.966x its book's and it needs no arm at all.

Phase 6 carries the borderline reading as a leftover **with the sentence the plan requires** —
that the verdict would flip on a different window — and with the era split beside it.

## 2. The cross-store defect is promoted from a leftover to a first-class finding of the set.

Phase 4 found it on M0201. Phase 1 added a third store. Measured here across the whole lab:

- **Twelve distinct `store_fingerprint` values across 859 recorded trials**, turning over every few
  days as the store is rebuilt.
- **Ten of the fifteen recorded `-PLC` shape comparisons cross a store boundary** — three different
  book stores (`704a21fc`, `b683da41`, `77c37d55`) against one control store (`640fc25e`).

This is structural, not an accident of one set: **a control is always drawn and run later than the
book it controls**, so D17's shape ratio compares across stores by default. Every shape ratio the
honest-control-redraw set published divides a control measured on one store by a book measured on
another.

**What it does and does not change.** The five unblocked methods read 0.96-0.99 and are not near a
bar, so their verdicts survive. It changes exactly one: M0201's 0.794 is 0.8008 re-run against
re-run, crossing the 0.80 bar, so the "near miss by 0.0059" was measurement error. M0221 moves
1.95 → 1.90 and stays refused.

**Why it is worth more than the verdict it moved:** `store_fingerprint` is recorded on every
trial, so this is mechanically detectable. A shape ratio computed across two fingerprints is not a
comparison, and `control_shape` could refuse or flag one instead of reporting it as a number.
**That is a separate plan set — do not grow this one** — but phase 6 states it as a finding with
these counts, not as a footnote.

## 3. Two smaller corrections phase 1 established, for phase 6 to publish.

- `trials.trades` is **not** an independent check on an entry count for any constant-name-count
  book: `metrics` counts closed round trips, so on a book holding twenty names every entry is one
  round trip and the two agree **by construction**, carrying no information. The 624/624 agreement
  that looked like a conflation risk is a tautology, and the 624 entry count is confirmed by an
  independent forward replay that never reads the trials table.
- The membership convention prices at **0.067 of ratio on M0208, not 0.202** — the plan's raw
  shipped-vs-K=1 method over-counted it threefold by absorbing two other components. The quoted
  "0.034 on M0047" is that chassis's **1996-2002 era**; whole-window it is **0.012**.
