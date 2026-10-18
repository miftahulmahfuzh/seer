# Plan: company size for firms with more than one share class

**Slug:** multi-class-company-size
**Date:** 2026-10-18 17:14
**Analysis:** `20261018-171434-MCS7_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/multi-class-company-size`
**Branch:** `feature/multi-class-company-size` (base: `origin/main` @ `1297681`)
**Phases:** 3
**Status:** phase 3/3 complete — landing and the Step 11 store cutover owed by the coordinator
**Coordinator:** —

---

## Why

From `docs/plans/HANDOVER_20261018-company-size-for-multi-class-firms.md`, verbatim:

> **The key finding is about the data, not the market (insight 398).** The plainest market copy
> (M0221) trailed SPY ~2 pts/yr, 5-6 in 2009-2015, even fee-free, because the store has no size for
> several of that decade's biggest winners. So the ruler is bent, and every member book starts
> 2009-2015 behind SPY before it picks anything.

> 1. Companies that tag `dei:EntityCommonStockSharesOutstanding` **per class** (class-axis
>    dimension) in XBRL go unknown — Alphabet from 2014, Meta, Visa, Mastercard, Ford, ~20 more in
>    2012. Sum the classes (or use the cover total), point in time, from the filing date.
> 2. **BRK.B 2010-11** counts class A only. Convert: 1 A = 1,500 B (1 A = 30 B before the 2010
>    50:1 B split). Value the company once.
> 3. Two listed classes (GOOG/GOOGL, FOX/FOXA, NWS/NWSA) each answer whole-company count × that
>    class's price. Better: each listed class valued at its own count × its own price, so a
>    method can weight the company once without a hand-kept list.

> **No purchase needed.** The source is free SEC EDGAR.

> **Done means:** META/V/MA/GOOGL/BRK.B have continuous point-in-time counts 2009-2015 with the
> right magnitude (spot-check Apple ≈ $560B and Meta ≈ $200B on 2014-06-30, Visa ≈ $130B,
> Berkshire ≈ $310B); `shares store-report` coverage of 2009-2015 member-days rises; then
> `lab unblock M0225` and record a `lab note` with the new coverage. Running M0225 itself is a
> lab run (pre-register first) and can go to the next Sera batch.

**Root cause found in analysis:** the 2009+ counts come only from SEC's `companyfacts` API,
which drops every dimensional (class-axis) fact. The fix reads the filings' own XBRL instance
documents from the EDGAR Archives.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Per-class XBRL share counts summed (or the tagged total), point in time from the filing date | 1, 2 |
| R2 | Berkshire valued once: class A in B units (×1,500; ×30 before 2010-01-21) | 2 |
| R3 | Each listed class valued at its own count × its own price, so methods weight a company once with no list of their own | 2 |
| R4 | `.research`, `.research-sv`, `.research-test` refreshed, price fingerprint unchanged, pushed via `sync-research-store`, fingerprint move stated in the commit | 3 |
| R5 | Spot checks at the right magnitude, 2009-2015 coverage up, `lab unblock M0225`, a plain-words note with the coverage (recorded through `lab unblock --note`) | 3 |

## Scope

**In scope:** reading `dei:EntityCommonStockSharesOutstanding` (and `us-gaap:CommonStockSharesOutstanding`
as fallback) **with its class-axis members** from each 10-K/10-Q XBRL instance of every index-member
filer whose 2009+ count is missing or multi-class; a committed per-class csv; a small hand-kept
class table in the data layer (sibling listed classes, non-1:1 conversions, classes with no
economic interest); class-aware attribution in `SharesHistory`; Berkshire's conversion applied to
its pre-2010 cover rows too; refreshing the three stores; the lab unblock and note.

**Out of scope:** foreign filers on 20-F/40-F (BIDU, CHKP, VOD, INFY, TEVA, …: no dei count in
those forms); successor tickers whose CIK history does not reach back (PSKY, VTRS, DXC); members
with no prices (CELG, ESRX, … — by design in the dev store); running M0225 (a lab run for the next
Sera batch); editing any existing method file or recorded lab row (frozen); the handover's other
leftovers.

## Invariants

1. The tree builds, `ruff check engine` is clean and `pytest engine/tests` passes at the end of every phase.
2. No look-ahead: every count is readable only from its **filing date**; `as_of` is the context instant.
3. `research.refresh_shares` is the only writer of store size files; the **price fingerprint never moves**. Only `shares.csv` (and `splits.csv`, regenerated from the same cache) change.
4. Tests never reach the network or production (the autouse fixture stays as is); network code is tested with fakes.
5. A single-class filer's answers are unchanged: the 2014-06-30 Apple value stays $560.3B. A per-class row exists only for a filing companyfacts has no cover count for, or a filer with several classes (pre-2010 cover classes, several companyfacts values, or a class-table filer read with `--cik`); where both exist for one accession the per-class reading wins the same-day tie (`history.SOURCE_RANK`: `xbrl-class` > `xbrl` > `edgar-cover`).
6. Closed records are frozen: no edit to `lab/methods/*.py`, `backtest/registry.py`, past reports, or existing lab rows.
7. The worktree has no stores, caches or venv: create `engine/.venv` in the worktree (`python3.11 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'`), pass stores/caches by **absolute path** under `/home/miftah/seer/engine/`, and set `SEER_ENV_FILE=/home/miftah/seer/.env.local` for any command that needs `SEC_CONTACT_EMAIL`.
8. Module docstrings explain *why*; argparse help escapes `%` as `%%`; owner-facing lab text is plain language (no ids, digests or code).
9. **Stage, then cut over after the merge.** Main's code refuses an `xbrl-class` row (`read_shares`: unknown source), and parallel Sera sessions read the main checkout's stores. Phase 3 refreshes `cp -a` copies under `/home/miftah/seer-stage/mcs/`; the live stores under `/home/miftah/seer/engine/` change only in Step 11, run by whichever session lands the branch on `origin/main`, right after the push, followed by the Blob push.
10. One company, one size: a multi-class filer with **no** class-table row on a count's date sums its classes 1:1 and each of its symbols answers the whole company (listed by `shares store`, never refused); a filer the table speaks for fails loud on any class it cannot attribute (unknown, listed by `shares store`).

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Per-class counts from XBRL instances | R1 | `seer_engine.shares` | 8 | — | HARD | `.workflows/plan/multi-class-company-size/phase-1.md` | P1-ENG-O3MU (done 2026-10-18) | — |
| 2 | Class-aware share history | R1, R2, R3 | `seer_engine.shares`, `backtest` | 8 | 1 | HARD | `.workflows/plan/multi-class-company-size/phase-2.md` | P1-ENG-IEFK (done 2026-10-18) | — |
| 3 | Refresh the stores, verify, unblock M0225 | R4, R5 | stores, lab, docs | 9 (+ 3 stores, Blob) | 1, 2 | NORMAL | `.workflows/plan/multi-class-company-size/phase-3.md` | P1-ENG-7CWT (done 2026-10-18) | — |

Phase 2 spans R1-R3 because one attribution function decides all three (summing classes,
converting Berkshire, and splitting siblings are the same per-class arithmetic); splitting it
would put two phases in the same function.

### Phase 1 — Per-class counts from XBRL instances
**Satisfies:** R1
**Owns:** `shares/instance.py` (new, pure: dei share facts and their contexts out of an instance
XML, then one per-filing reading: `as_of`, tagged total if any, per-class counts by axis member;
a class axis beside a tracking-group axis (`GROUP_AXES`) is kept, labelled `memberA+memberB`; an
undimensioned figure that is not the classes' total is dropped when it equals one class and
otherwise counted as the class `NoClassAxisMember`); instance download in `shares/fetch.py`
(filing `index.json` → instance file → only the parsed dei facts cached as gzip JSON under
`<cache>/xbrl-instance/<cik>/<accession>.json.gz`, `.missing` markers, resumable, paced);
`edgar_index` able to list 2009Q1..the last **closed** quarter; a new `shares/classes.py` with the
filing selection (every 10-K/10-Q of an S&P 500 or Nasdaq-100 member filer, 2009-01-01..today,
whose accession has no dei count in the dev store's `fundamentals.csv`, plus every such filing of
a filer whose pre-2010 cover rows or companyfacts show more than one class, plus every such filing
of a filer named with the repeatable `--cik`), the vendored csv's writer/reader and dataclass,
and two CLI actions `shares download-classes --fundamentals <csv> [--cache --through --cik
--workers --limit]` (network) and `shares build-classes [--cache --through --cik --out]` (no
network → `engine/data/shares_xbrl_classes.csv`, every set-aside figure printed);
`commands/shares.py` wiring; the `SOURCES.md` section for `shares_xbrl_classes.csv` (appended at
the end of the file, placeholder cells for phase 3); tests with fakes and a trimmed real-instance
fixture.
**Interface it publishes (phase 2 imports it):** `classes.ClassRow(cik, symbol, filed, as_of, form,
accession, shares, classes: tuple[tuple[str, int], ...], tagged_total: bool)`; `classes.load_rows(path)
-> list[ClassRow]`; `classes.CLASSES_FILE = "shares_xbrl_classes.csv"`; csv header
`cik,symbol,filed,as_of,form,accession,shares,classes,tagged_total`; `classes` as
`member=count;...` with the XBRL member's local name (`CommonClassAMember`), `A+B` for a
tracking-group context, `NoClassAxisMember` for a bare class, empty when the instance carries
only an axis-less figure.
**Does not touch:** `history.py`, `store.py`, `integrate.py`, `backtest/market.py`,
`engine/data/share_classes.csv`, `shares/__init__.py`, `engine/package_readme.md`, any store.
It may run a small live `download-classes --cik 1326801 --limit 12` for a sanity check but does
**not** commit a full csv (phase 3 does).
**Exit criteria:** ruff clean, full suite green; on a live sample (Meta 2014-07-24 10-Q)
`build-classes` writes a row with `CommonClassAMember=2015048077;CommonClassBMember=585003514`,
`shares=2600051591`, `as_of=2014-07-22`; no `engine/data/shares_xbrl_classes.csv` in the commit.

### Phase 2 — Class-aware share history
**Satisfies:** R1, R2, R3
**Owns:** `shares/class_table.py` (new, pure) and `engine/data/share_classes.csv` (new, hand-kept,
99 rows, 14 filers, each row citing its filing): `cik,member,symbol,ratio,from,to,note` — which
listed symbol a class trades as, its ratio into that symbol's share units over a span of **count
dates**, ratio 0 for a class with no economic interest; classes matched by their words
(`class_key`), so cover text, XBRL member names and `+`-joined tracking-group labels share rows.
Seeded with Alphabet/Google, Fox and Fox Corp, News Corp, Comcast 2015, Discovery, Liberty
Global/LiLAC, Liberty Media, Liberty Interactive, Under Armour, Berkshire (A→BRK.B at 30 before
2010-01-21, 1,500 from), Visa (B, B-1..B-3, C at their dated as-converted ratios) and Accenture
(class X ratio 0). `shares/history.py`: the per-class rows as a third source `"xbrl-class"`
(later filing wins; same-day tie `xbrl-class` > `xbrl` > `edgar-cover`); per-symbol attribution
(no table row on the count date: classes summed 1:1, the whole company on each symbol, filer
recorded in `SharesHistory.summed`; table rows: each symbol answers its classes × ratio, and any
class without a row, a figure without a breakdown or a symbol without a class makes the answer
unknown, recorded in `SharesHistory.problems`); the same table applied to pre-2010 cover rows.
`shares/store.py`: `SOURCES`, `_candidates` over the new rows, `history_for(..., class_rows=)`.
`shares/integrate.py`: `shares store` refuses (exit 2) until `engine/data/shares_xbrl_classes.csv`
exists, reads it (`--classes` override), prints `problems` and `summed`; `store-report --symbols`.
`backtest/market.py`: docstrings only. The `SOURCES.md` section for `share_classes.csv`, appended
after phase 1's. Tests (`test_share_class_table.py`; none reads the committed per-class csv).
**Does not touch:** `instance.py`, `fetch.py`, `edgar_index.py`, `classes.py` (lazy import only),
`commands/shares.py`, `shares/__init__.py`, `engine/package_readme.md`, any store, the lab.
**Exit criteria:** ruff clean, full suite green, including: Meta-like class-axis rows answer the
sum; a multi-class filer with no table row is summed and listed in `summed`, not `problems`;
GOOGL/GOOG answer A+B and C separately and sum to the company; BRK.B answers A×1,500+B after
2010-01-21 and A×30+B before; Visa A + B×0.4254 + C on 2012-07-30; a filer with no table rows and
no class rows answers exactly as before; `change_points` stays exact.

### Phase 3 — Refresh the stores, verify, unblock M0225
**Satisfies:** R4, R5
**Owns:** staging (`cp -a` of `.research`, `.research-sv`, `.research-test` into
`/home/miftah/seer-stage/mcs/`; every write goes to the copies); `shares download-classes
--fundamentals <staged dev>/fundamentals.csv`, then the same with one `--cik` per filer of
`engine/data/share_classes.csv`, then `build-classes`, reviewing every `set aside:` line, and
committing `engine/data/shares_xbrl_classes.csv`; `shares store` on the staged dev store
(`--evidence-store` the staged test store) and test store (`--xbrl` the dev store's
`fundamentals.csv`), resolving every `problems` entry (a cited `share_classes.csv` row, e.g.
Berkshire's bare class A, as a Step 6 data fix with a test, or recorded); `survivorship_store
--refresh-shares` for the staged check store; each price fingerprint unchanged; before/after
coverage 2009-2015 and the spot checks (Apple 2014-06-30 $540-580B and unchanged, Meta $160-190B,
Visa $120-140B, Berkshire $290-335B, GOOGL+GOOG $360-420B); continuity (META/FB, V, MA, GOOGL,
GOOG, BRK.B: no 2009-2015 member-day with a close and no count); `lab unblock M0225 --note` (the
plain-words note, no separate `lab note`), `lab stage`; docs: the skill's size-accessor caveats,
the `shares/__init__.py` docstring (module map gains `instance`, `classes`, `class_table`),
`engine/package_readme.md`, the runbook recipe (three class commands, stage-then-cut-over), the
placeholder cells of phase 1's `SOURCES.md` section, the handover close-out; the commit naming old
and new store fingerprints; **Step 11 cutover**: after the branch is on `origin/main`, move the
staged stores into `/home/miftah/seer/engine/`, keep the old ones in
`/home/miftah/seer-stage/mcs/old/`, and `sync_store.py push` dev, sv and test.
**Does not touch:** engine source beyond fixes a real run proves necessary (each with a test and
its own commit); the live stores before the merge.
**Exit criteria:** every number above recorded in the lab note, the commit and the close-out;
price fingerprints unchanged on all three stores; M0225 back to `idea`. **Cutover is part of
done:** whichever session lands the branch on `origin/main` (this phase's, the completion handler
or the swarm coordinator) runs Step 11 right after the push; the set is finished only when the
three live stores carry the new `shares.csv` and Blob reports `in_sync: true` for dev, sv and test.

## Reconciliation Log

Round 1.

| # | Conflict | Class | Resolution |
|---|---|---|---|
| 1 | Index/phase-2 boundary said "no table rows → sum 1:1"; phase 2's Decision 3 prose said "no 1:1 fallback for single-listed filers either". The seed table covers 14 filers and none of META, MA, UPS, F, EL, TSN, RL, BF.B, MKC, LEN, STZ, EXPE, CME, TAP, HRL, GHC, MOS, KMI, PRU, UHS, TRIP, SPG, REGN (CMCSA only 2015, UAA only from 2016) | Contract drift (2 vs index) | Phase 2's code already returned the total when no row covers the count date; the prose was wrong. Decision 3, the `class_table` docstring and the `SOURCES.md` text rewritten: fail loud only inside a tabled filer; untabled multi-class filers summed 1:1 and recorded in a new `SharesHistory.summed`, printed by `shares store`; test asserts it. Decision row 7 |
| 2 | A filer tagging one class bare and the others on the axis: phase 1 kept only the axised classes (bare figure "set aside"), undercounting the company; phase 1's own handoff flagged it, and Berkshire's companyfacts figures for 2010-2011 are such a bare class A | Gap (R5 magnitude) | Phase 1 `instance._read` rule 4: a bare figure equal to one class is dropped (tagged twice); any other is counted as class `NoClassAxisMember`; `build-classes` prints every set-aside figure; two tests replace the old one. Phase 2 sums it for untabled filers and fails loud for tabled ones until a cited row names the class (phase 3 Step 3/6, Berkshire = class A). Decision row 8 |
| 3 | Phase 2 required every filing of each class-table filer; phase 1 selected only companyfacts-missing accessions plus pre-2010 multi-class filers (Alphabet 0001652044, Fox Corp 0001754301, Liberty Media 0001560385 not selected), and phase 1 cannot read phase 2's file | Unmet assumption | Phase 1's repeatable `--cik` now reads **every** member filing of the named filer; phase 3 Step 2 runs a second `download-classes` with one `--cik` per CIK of `share_classes.csv`; the runbook recipe and `SOURCES.md` carry the same command. Phase 2's Requires/Handoffs updated |
| 4 | Two-axis (tracking group + class) contexts: phase 2 required both member names in one label; phase 1 dropped every context with more than one dimension | Unmet assumption | Phase 1: new `GROUP_AXES` (`TrackingStockAxis`, `EconomicPerformanceGroupAxis`, `StatementBusinessSegmentsAxis`), labels joined by `GROUP_JOIN = "+"` in axis-name order; class-only facts beside group facts dropped as the same shares; other second axes still refused; new test. Phase 2's conditional Requires made firm |
| 5 | Phase 3 assumed `download-classes --cache --xbrl --limit`, `build-classes --cache [--out]` | Contract drift (3 vs 1) | Phase 3 Requires, Step 0 help checks, Step 2 commands, readme bullet and runbook recipe rewritten to `--fundamentals`, `--cik` (repeatable), `--through`, `--workers`, `--limit`, `--out`; the "use the landed name" escape hatch removed |
| 6 | `shares store` refuses without `shares_xbrl_classes.csv` (phase 2) | Ordering check | Confirmed: phase 3 Step 2 builds the csv before Step 3's `shares store`; no phase 2 test drives `integrate.write` or reads the committed csv; `history.load()`/`history_for` callers (`build.py`, `test_shares.py`) read the default data dir, where phase 2 commits `share_classes.csv`. Phase 3's Verification note corrected |
| 7 | `SOURCES.md`: phases 1 and 2 both "append after line 470" | File collision | Phase 1 appends first (end of file); phase 2 appends after phase 1's section; phase 3 fills phase 1's placeholder cells (Fetched, Scope, Rows, sha256) in place instead of appending at end of file |
| 8 | `shares/__init__.py` module map: phase 3's 8b hedged on phase 1 having edited it; phase 2's handoff asked for a `class_table` bullet phase 3 lacked | Duplicate work / gap | Phases 1 and 2 list it under Does not touch; phase 3 owns it, the hedge removed, `class_table` bullet added. `engine/package_readme.md`, the runbook and the skill notes: phase 3 only |
| 9 | Staging/cutover existed only in phase 3; the index's Phase 3 section and Invariants did not carry it, and phase 3's exit criteria demanded live stores that its own session may not be allowed to touch | Contract drift | Invariant 9 added; index Phase 3 section rewritten; phase 3 exit criteria split into before-merge (staged) and after-merge (Step 11 by whichever session lands the branch) |
| 10 | GOOGL/GOOG (2014-04-03) and UAA (2016-04-07) count the company twice for ~3 weeks after a class C dividend | Behavioural fork | Accepted as a recorded known limitation (Decision row 9); phase 2 `SOURCES.md` already documents it; phase 3's close-out template now states it |
| 11 | Index R5 says `lab note`; phase 3 records the note through `lab unblock --note` and forbids a second same-day `lab note` (duplicate heading) | Contract drift (index vs 3) | Index R5 and Phase 3 text follow phase 3 (Decision row 10) |
| 12 | Invariant 5 described a "differs only by a class split" rule no phase implements | Contract drift (index vs 2) | Invariant 5 restated as phase 2's same-day rank and phase 1's selection |

Standard checks after the edits: nothing is deleted or renamed in any phase; every `Requires`
points backward (2 → 1, 3 → 1, 2); each phase builds green on its own (phase 1 adds code nothing
else reads; phase 2 imports `classes` lazily and its tests write their own rows; phase 3 changes
code only through run-proven fixes); every impact point in the analysis has one owner (1-4, 11, 12
→ phase 1; 6-10, 12 → phase 2; 5 split by format/data; 13 → phase 3); R1-R5 each served.

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| Where the per-class counts come from | Each filing's XBRL instance from the EDGAR Archives (exact, free); not the cover-page text parser past 2010, not a paid feed | 5: user input ("free SEC EDGAR", "sum the classes (or use the cover total)") |
| Per-class line vs whole company per symbol | Per listed class (R3); unlisted classes attributed to the listed class they convert into, so each company's lines sum to the whole company and single-listed firms (META, V, BRK.B) answer the whole-company magnitudes the spot checks expect | 5: user input (R3 "Better" + Done-means spot checks) |
| A hand-kept list | Kept in the **data layer** only (`share_classes.csv`, small, cited); methods need none | 5: user input ("so a *method* can weight the company once without a hand-kept list") |
| Meta's spot-check magnitude | ≈ $175B (2.600B shares × $67.29 from Meta's own 10-Q) — band $160-190B; the handover's "≈ $200B" was a round figure | 1: invariant 2 / the filing itself |
| Existing methods' "identical share count" class dedupe (M0221 etc.) | Left as is (frozen); with per-class counts GOOG/GOOGL no longer collapse, which is the SPY-like shape | 1: invariant 6 |
| Store fingerprint movement | Expected and stated in the commit; price fingerprint must not move | 1: invariant 3 |
| Multi-class filer with no class-table row: 1:1 sum vs fail loud (phase 2 prose vs index) | Sum 1:1, whole company on each symbol, recorded in `SharesHistory.summed` and printed; fail loud only inside a filer the table speaks for on the count date | 2: exit criteria (phase 3's continuity and spot checks for META/MA, which the table does not list) and 4: index Requirements (R5 Done-means) |
| Bare (axis-less) figure beside axised classes that is not their total | Equal to one class → dropped (tagged twice); otherwise counted as class `NoClassAxisMember`; every case printed by `build-classes`; a tabled filer needs a cited row saying which class it is | 2: exit criteria (BRK.B continuous at ≈ $310B; Berkshire's 2010-2011 companyfacts figures are a bare class A, analysis) over phase 1's code block, which dropped it |
| GOOGL/GOOG and UAA ~3-week double count after a class C dividend | Accepted and recorded (phase 2 `SOURCES.md` Known limits, phase 3 close-out); not fixed by starting the table earlier, which would leave GOOG with no count for those weeks | 2: exit criteria (phase 3 requires GOOG to have no gap day 2009-2015) |
| How phase 1 reaches every filing of the class-table filers | Repeatable `--cik` reads every member filing; phase 3 (and the runbook) pass the table's CIKs. Phase 1 never reads `share_classes.csv` | 3: plans' code blocks (phase 1 already had a repeatable `--cik`; phase 2's handoff named the `--cik` run) |
| Two-axis tracking-group labels | Kept with both member names joined by `+`, axis-name order, group axes allow-listed; class-only facts beside group facts dropped | 3: plans' code blocks (phase 2's `class_key` test already parses `LiLACGroupMember+ClassBOrdinarySharesMember`) |
| `lab note` vs `lab unblock --note` | One `lab unblock M0225 --note` carries the plain-words note; no separate same-day `lab note` | 3: phase 3's code block (`store.append_analysis` would print a second identical dated heading) |

## Open Questions

(none)

## Rollback

Per phase: revert the phase's commit. Phase 3's store refreshes are reversible by re-running
`shares store` / `survivorship_store --refresh-shares` from the previous commit (the stores'
Blob mirror also keeps the old content-addressed copy). The lab rows written in phase 3 are
append-only; a mistaken unblock is undone with `lab block M0225 --on "..."` and a correcting note.

## Next

    /implement -f MULTI_CLASS_COMPANY_SIZE_PLAN.md --phase 1

Or run the whole set as a swarm:

    /analyze-orchestrator -f MULTI_CLASS_COMPANY_SIZE_PLAN.md
