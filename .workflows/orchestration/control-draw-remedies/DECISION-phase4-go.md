# Coordinator decision, 2026-10-20 — phase 4 is a GO, and the winner is rule D (G-bottom)

Phase 4's plan contradicts itself. Its **STOP rule** fires only when *no* rule lands M0221's
control inside WARN_BAND on both axes. Its **Handoffs** section says flatly: "Two rules clearing,
or a rule clearing on one axis only, is **S**." Both B and D cleared, so the two lines disagree.

**Resolved: GO, branch key G-bottom (rule D).** Three reasons, in order.

1. The Handoffs line is a *handoff contract*, and the phase's exit criteria — which demand "the
   winning rule's definition, OR the STOP" — outrank it on the precedence ladder.
2. That guard was written under a prediction the measurement falsified. The planner expected the
   best rule near 1.67x and nothing to clear; D measured 1.011x against a shipped 1.900x, closing
   98.8% of the excess. Reporting S ("no rule cleared") about a rule that cleared would publish a
   falsehood, and this lab reports measurements as they land.
3. The guard's PURPOSE was to stop phase 5 inheriting an ambiguous winner. That purpose is served
   here by the coordinator naming the winner explicitly, which is what this note does.

**The tie-break between B and D was checked, not accepted.** They sit 0.001 apart on M0221, which
is noise, and the phase correctly refused to break the tie on it. B acquires "entrants rank below
keeps" as a SIDE EFFECT of `matched_partition` keeping the smallest `keep_key` holdings; D builds
it explicitly from `picks - held`. A chassis with a different keep band does not inherit B's
property, and M0201 is the direct evidence: B degrades to 0.6865 there, D only to 0.7352. D was
also the mechanism-derived rule, pre-registered as "best if the mechanism is right", and the
mechanism is confirmed (entrant weight 1.884x against a re-run excess of 1.900x).

**Carried to phase 5 and phase 6, and it sharpens R1 rather than softening it.** Rule D is a fix
for a chassis that HAS an entrant-rung defect and is harmful where there is none: applied to
M0201 it would take a compliant 0.8008x arm to 0.7352x. So D must not be drawn on M0201, and
phase 6 should record that a weight rule's scope is per-chassis by measurement, not just by
construction — a third measured reason R1 as literally written is unreachable.

**The store-boundary defect is the set's most portable finding and is NOT M0201-specific.**
Verified independently here: every book arm of the honest-control-redraw set was measured on store
`b683da41` and every `-PLC` control on `640fc25e`. So EVERY published shape ratio in that set
divides a control from one store by a book from another. It only changes a verdict where an arm
sits near a band edge, which is M0201 alone (0.7941 published, 0.8008 re-run against re-run,
crossing the 0.80 bar) — but the rule it implies is general: a shape ratio is only a comparison
when both halves come from one sweep.
