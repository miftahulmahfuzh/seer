> Adopted from `DELISTING_STRESS_ROSTER_RULES_PLAN.md` phase 5. Source: `.workflows/plan/delisting-stress-roster-rules/phase-5.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 5: MOM-FR, judged under the rule

**Plan set:** `DELISTING_STRESS_ROSTER_RULES_PLAN.md`
**Analysis:** `20261007-170515-0CU0_code_analyzer.md`
**Satisfies:** R3 — Q3: is `MOM-FR` the weakest of the five, and does a better occupant of that slot exist in the lab?
**Depends on:** Phase 3 (the roster replacement rule, a new section of `docs/plans/2026-10-04-method-lab-design.md`, expected §8)
**Difficulty:** NORMAL
**Package:** `docs/handover`

---

## Goal

After this phase, Q3 has a dated, measured answer in the repository instead of an open thread in a
handover: **keep `MOM-FR`**, decided under phase 3's replacement rule by name and section number,
with the lab evidence that supports it *and* the evidence that cuts against it both written down.
Three facts that were not in the repository before are in it afterwards: that `MVW-FR` scores below
`MOM-FR` on both of the lab's measures, so "the weakest of the five" is not what the numbers say;
that one of Q3's three complaints — the 20.7-month clock — became void when the owner replaced
go-live item 1 on 2026-10-07; and that **every** lab candidate scoring above `MOM-FR` is a
residual-momentum relative of two strategies already on the roster.

The expected code change is **none**. `engine/src/seer_engine/paper/roster.py` is touched only if
the verdict comes out "swap", and on the evidence below it does not.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** *(none)*
**Renames:** *(none)*
**Creates:** `docs/handover/2026-10-07-mom-fr-under-the-replacement-rule.md` (new file, the only
file this phase writes on the expected path)
**Signature changes:** *(none)*
**Requires (from earlier phases):**
- Phase 3 has added a numbered section to `docs/plans/2026-10-04-method-lab-design.md` stating when
  a paper roster entry may be replaced, with **named triggers** and **named refusals**, built on
  18 months flat, and stating that a falling DSR alone is never a reason to replace an entry. This
  phase reads that section and cites it **by its real number**; it never amends it, never quotes
  its wording as if authored here, and never re-derives a rule of its own. The implementing session
  resolves the placeholder token `§<RULE>` (see Step 1) by opening the file. Expected `§8` — the
  document today ends at `### 7.6`, so §8 is free, but **read, do not assume**.
- Nothing else. This phase does not depend on phases 1, 2 or 4 and must not wait for them.

**Requires (from outside this plan set, already landed on `main`):**
- `seer-fc` has already replaced design §1 item 1 with **"≥ 18 months of forward paper trading"**
  and deleted the `≥ 100 closed trades` clause. **Verified 2026-10-07 in the main checkout**:
  `/home/miftah/seer/docs/plans/2026-10-03-seer-design.md:16` reads
  `1. ≥ 18 months of forward paper trading  *(revised 2026-10-07; was "≥ 3 months … and ≥ 100 closed trades" — see §13)*`.
  **Updated 2026-10-07: the worktree copy now carries that text too** — the branch has been merged
  up to `origin/main` @ `ba8a05b`, where §1 item 1 is at line 17 and §13 at line 232. (An earlier
  draft of this plan said the worktree still held the old text; it does not.) The file is still a
  file `seer-fc` claimed and **must not be edited here**. The implementing session re-reads the
  worktree's own line to confirm it is still true before citing it, and cites §13 as the revision
  note.

**Leaves alone (owned by others):**
- `docs/plans/2026-10-04-method-lab-design.md` — **Phase 3.** Read only.
- `docs/plans/2026-10-03-seer-design.md`, `backtest/metrics.py`, `backtest/tuning.py`,
  `backtest/report.py`, `backtest/b_report.py`, `backtest/wf_report.py`, `web/lib/*`,
  `engine/tests/test_backtest_{tuning,metrics,b_walkforward,report,b_report}.py` — **`seer-fc`.**
- `lab/lab.sqlite` — **Phase 2** appends one `insights` row. This phase opens it **read-only by
  URI** and writes nothing: no trial, no insight, N stays 110, 0 test-window looks stay 0.
- `docs/handover/2026-10-07-dev-gate-trades-bar.md` — **Phase 4.**
- `engine/.research` — untouched by every phase; no `config_digest` moves.
- `web/app/(app)/leaderboard/*` — the hero figure. Handover §4 forbids opening work on it without
  re-checking the page first. This phase opens none.

**Correction this phase raised — APPLIED 2026-10-07, nothing left to do:**
The analysis file's M3 and the index's phase-5 exit criterion both said `MOM-FR` ranks
**"7th by MAR"**. Re-measured here through `lab.store.owner_failures` + `lab.store.verdict` at
N = 110: among the 26 candidates that clear all five owner conditions, **seven** have a strictly
higher MAR than `MOM-FR`'s 0.684030 (0.856651, 0.816117, 0.792666, 0.791111, 0.768371, 0.763098,
0.749975), so its rank is **8th of 26**, not 7th. The DSR rank, **12th of 26**, is confirmed
exactly.

**The analysis file, the plan index and `phase-3.md`'s handoff now all read "8th of 26".** The
only remaining occurrences of the string *"7th by MAR"* anywhere in this plan set are **inside this
file**, and every one of them is part of this phase's own account of the slip being corrected —
§3's blockquote, §9, and the two notes above. **Do not "fix" them**: deleting them deletes the
correction. The document this phase ships states 8th.

## Files

| File | Action | What changes |
|---|---|---|
| `docs/handover/2026-10-07-mom-fr-under-the-replacement-rule.md` | **create** | the whole file — the verdict, the evidence, the reasoning, and the case against the verdict |
| `docs/plans/2026-10-04-method-lab-design.md` | **read only** | phase 3's rule section: resolve its real number and its trigger/refusal names |
| `docs/plans/2026-10-03-seer-design.md` (**the worktree's own copy**, post-`ba8a05b`) | **read only** | confirm §1 item 1 still reads "≥ 18 months of forward paper trading" (line 17) and §13 exists (line 232) |
| `lab/lab.sqlite` | **read only (`mode=ro` URI)** | re-judge the 110 recorded dev trials; write nothing |
| `engine/src/seer_engine/paper/roster.py` | **conditional, NOT expected** | only if the verdict is "swap" — see Step 4, which is expected not to fire |
| `engine/tests/test_paper_roster.py` | **conditional, NOT expected** | only if Step 4 fires — a new pinned digest |
| `db/migrations/014_*.sql` | **conditional, NOT expected** | only if Step 4 fires — the new row, byte for byte |

**On the expected path exactly one file changes, and it is a new document.**

## Implementation Steps

### Step 1: Resolve phase 3's rule — read it, do not re-derive it
**File:** `docs/plans/2026-10-04-method-lab-design.md` — read only; the new section phase 3 appended
after `### 7.6 Luck-testing the P7a seed` (today the file's last section; `grep -n '^## ' ` returns
`## 1.` … `## 7. Revision 2026-10-07 (owner): the luck bar at 0.90, and the N left alone`).
**Change:** none to that file. Extract three things and nothing else:

1. the section's **real number and title** (expected `§8`, but read it);
2. the **names** of its trigger conditions — the circumstances under which a roster entry *may* be
   replaced;
3. the **names** of its refusals — the circumstances under which it explicitly may *not*.

Then write them into the document of Step 2 **as phase 3 named them**, each one marked met or not
met for `MOM-FR`, with the evidence beside it. Do not paraphrase a trigger into a different
condition, do not add a trigger phase 3 did not write, and do not soften a refusal that bites.

**If phase 3 has not landed yet:** stop and wait. Do not write a rule here, do not guess §8's
contents, and do not ship the document with the placeholder unresolved. The index's wave structure
is `{1, 3, 4}` then `{2, 5}` precisely so this cannot happen; if it has happened, that is a swarm
sequencing error, not a licence to improvise.

**Placeholder convention used by Step 2's text:** the token `§<RULE>` appears wherever the rule's
section number belongs, and the token `<RULE-TITLE>` wherever its title belongs. The document also
carries one HTML comment naming them. **Both tokens and the comment must be gone from the committed
file.** `grep -n 'RULE' docs/handover/2026-10-07-mom-fr-under-the-replacement-rule.md` returning
nothing is the check.

**Impact:** nothing is written in this step. It is the step that stops phase 5 from quietly
authoring the rule it is supposed to be judged by.

---

### Step 2: Write the handover document
**File:** `docs/handover/2026-10-07-mom-fr-under-the-replacement-rule.md:1` — new file, whole
contents below.
**Change:** create the file with exactly this text, after substituting `§<RULE>`, `<RULE-TITLE>`,
and §2's trigger/refusal names from Step 1. Every number in it was measured during planning by the
command in Step 3 and reproduces exactly; do not re-estimate any of them.

**Code:**

`````markdown
<!-- IMPLEMENTER: replace every `§<RULE>` with the real section number of phase 3's roster
     replacement rule in docs/plans/2026-10-04-method-lab-design.md (expected §8, READ it), and
     every `<RULE-TITLE>` with that section's title. Fill §2's trigger/refusal list with the names
     phase 3 actually used. Then DELETE this comment. `grep -n RULE` on this file must find
     nothing. -->

# Handover: MOM-FR, judged under the roster replacement rule

Written 2026-10-07 on `feature/delisting-stress-roster-rules` (base `3683d7b`), before the first
paper session has ever run. This settles **Q3** of
`docs/handover/2026-10-07-roster-first-night-and-survivorship.md` §5 — *"is `MOM-FR` the weakest of
the five?"* — under the rule written in `docs/plans/2026-10-04-method-lab-design.md` §<RULE>,
*<RULE-TITLE>*.

Q3 said the question was *"worth asking… **but not before** reading the warning in Q4."* That
ordering is honoured: the rule was written first, by a separate session that could not see this
answer, and this document applies it. It does not amend it and it does not add to it.

Read-only against the method lab: no trial recorded, N unmoved at 110, no test-window look spent,
no `config_digest` changed, no roster row edited.

---

## 0. In plain words

Five strategies are paper-trading. One of them, **MOM**, was flagged as the likely weakest and
worth replacing with a better one from the method lab. It was checked properly. The answer is
**keep it**, and the three reasons were measured rather than argued:

- **It is not the weakest.** Of the four non-benchmark quant strategies, **MVW scores lower than
  MOM on both of the measures the lab uses** — the luck test and the return-per-unit-of-worst-fall
  ratio. The premise of the question does not survive the data.
- **One of the three complaints against it has stopped being true.** It was said to need the
  longest wait before anyone could judge it — 20.7 months, against about 15 for two others. That
  was a consequence of a rule the owner has since replaced. Every strategy now reaches its verdict
  at 18 months, flat, whatever its trading rate. The complaint is void.
- **Every better-scoring replacement is a near relative of strategies already on the board.**
  Eleven lab candidates outscore MOM on the luck test. All eleven come from the same family of
  methods — the one RMW and RAW already occupy, two of the five slots. Swapping MOM for the best of
  them would raise the roster's average score and leave it holding three settings of one idea.

And one fact that points the other way, written down because a document that only lists reasons for
its own conclusion is an argument, not evidence: **nothing has traded yet**, so a swap will never
again be as cheap as it is today. That was weighed and did not win. §6 says why.

---

## 1. The verdict

**Keep `MOM-FR`. No roster change, no new paper clock, no code change.**

Decided under the rule in `docs/plans/2026-10-04-method-lab-design.md` §<RULE>. The rule's trigger
conditions are checked one by one in §2; none of them is met. The rule's refusals are listed there
too, and the argument that was actually on the table — *a lab candidate now scores higher* — is one
of the things it refuses.

This verdict is about **MOM-FR only**, because Q3 asked about MOM-FR only. §7 records the one
question it opened and deliberately did not answer.

---

## 2. The rule, condition by condition

<!-- IMPLEMENTER: one row per trigger and one per refusal, using phase 3's own names. Do not invent
     a condition, do not drop one that bites, and do not soften a refusal. Evidence column cites
     §3, §4 or §5 of this document. -->

| §<RULE> condition | kind | met for `MOM-FR`? | evidence |
|---|---|---|---|
| *(phase 3's first named trigger)* | trigger | | |
| *(phase 3's further named triggers, one row each)* | trigger | | |
| *(phase 3's first named refusal)* | refusal | | |
| *(phase 3's further named refusals, one row each)* | refusal | | |

No trigger fires. At least one refusal applies directly to the argument that prompted the question.
That is the whole decision; §§3–6 are the evidence behind the cells.

---

## 3. What the method lab actually says today (measured)

Every one of the 110 recorded dev-window trials was re-judged **at today's bars** — not at the bars
written on the row, which are stale. All 110 rows record the old `DSR >= 0.95` label and the old
15% drawdown limit; the owner moved both on 2026-10-07. The four threshold conditions are
recomputed from each row's recorded numbers against the constants in force now, which is exactly
what `lab.store.owner_failures` and `lab.store.verdict` are for.

Reproduce (read-only, writes nothing, records no trial, does not move N):

```
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules
PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python - <<'PY'
import sqlite3
from seer_engine import config
from seer_engine.lab import store

LAB = config.REPO_ROOT / "lab" / "lab.sqlite"
conn = sqlite3.connect(f"file:{LAB}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
g = store.gate(conn)
rows = conn.execute("SELECT * FROM trials WHERE window='dev'").fetchall()
clear = [(r, store.verdict(conn, r, at=g)) for r in rows if not store.owner_failures(r)]
print(f"N={g.n} policy={g.policy} dev_trials={len(rows)} clear_all_five={len(clear)}")

def key(pair):           # a luck test that could not be evaluated is not a high one: NULL last
    v = pair[1]
    return (v.dsr is None, -(v.dsr or 0.0))

bydsr = sorted(clear, key=key)
bymar = sorted(clear, key=lambda p: -float(p[0]["mar"]))
ids = [r["candidate_id"] for r, _ in bydsr]
mids = [r["candidate_id"] for r, _ in bymar]
print(f"MOM-FR (M0002-REL-85): DSR rank {ids.index('M0002-REL-85')+1} of {len(ids)}, "
      f"MAR rank {mids.index('M0002-REL-85')+1} of {len(mids)}")
for name, cid in (("RMW-FR","M0022-W-TV16"),("RAW-FR","M0007-N20-RAW"),
                  ("MOM-FR","M0002-REL-85"),("MVW-FR","M0008-N30-C07")):
    r, v = next(p for p in clear if p[0]["candidate_id"] == cid)
    print(f"  {name:7s} {cid:22s} dsr={v.dsr:.4f} mar={float(r['mar']):.3f} "
          f"cagr={float(r['cagr'])*100:.2f}% dd={float(r['max_drawdown'])*100:.2f}% "
          f"trades={r['trades']} pf={float(r['profit_factor']):.3f} eligible={v.eligible}")
print("above MOM-FR by the luck test, with the lab method each came from:")
for r, v in bydsr[:ids.index("M0002-REL-85")]:
    print(f"  {r['candidate_id']:22s} {r['method_id']:6s} dsr={v.dsr:.4f} "
          f"mar={float(r['mar']):.3f} eligible={v.eligible}")
PY
```

**Twenty-six of the 110 clear all five owner conditions today.** Of those 26, `MOM-FR` is **12th on
the luck test** and **8th on MAR** — return per unit of worst fall, the lab's one risk-adjusted
ranking.

The four quant roster entries, as the lab reads them now:

| roster entry | lab candidate | luck test (DSR) | MAR | return/yr | worst fall | trades | profit factor |
|---|---|---|---|---|---|---|---|
| `RMW-FR` | `M0022-W-TV16` | **0.9156** | 0.816 | 11.68% | 14.31% | 1,589 | 2.065 |
| `RAW-FR` | `M0007-N20-RAW` | 0.8985 | 0.768 | 15.05% | 19.59% | 1,596 | 2.163 |
| `MOM-FR` | `M0002-REL-85` | 0.8278 | 0.684 | 12.56% | 18.37% | 1,148 | **2.332** |
| `MVW-FR` | `M0008-N30-C07` | **0.7802** | **0.564** | 11.27% | 19.97% | 1,223 | 2.143 |

Three plain readings of that table:

1. **`MVW-FR` is below `MOM-FR` on both measures** — 0.780 against 0.828 on the luck test, 0.564
   against 0.684 on MAR. Whatever "weakest of the five" means, the lab's own numbers do not point
   at MOM.
2. **`MOM-FR` has the highest profit factor of the four** (2.332 — it makes ₂.33 on winners for
   every ₂ lost on losers), and it does it on the fewest trades, which is what a selective book
   looks like rather than what a weak one looks like.
3. **Three of the four are not dev-eligible today, including `RAW-FR` at 0.8985** — 0.0015 below
   the bar. The roster was never admitted on the lab's gate; it was admitted on the owner's
   judgement, with the lab's reading recorded alongside (`paper/roster.py`, `LAB_PROVENANCE`, and
   `docs/plans/2026-10-04-method-lab-design.md` §7.4). That is the standing policy, not an
   exception made for MOM.

> **One correction to the record.** The first drafts of
> `20261007-170515-0CU0_code_analyzer.md` §M3 and of the plan index both said `MOM-FR` ranks
> *7th by MAR*; both were corrected on 2026-10-07 and this note records why. Re-measured by the
> command above, seven candidates have a
> strictly higher MAR (0.8567, 0.8161, 0.7927, 0.7911, 0.7684, 0.7631, 0.7500) against MOM-FR's
> 0.6840, so it ranks **8th of 26**. The luck-test rank, 12th of 26, is confirmed exactly. The
> conclusion is unchanged; the number is.

---

## 4. Q3's three complaints, checked one at a time

### 4.1 "The slowest path to a verdict (20.7 months)" — **void**

This was the strongest-sounding of the three and it no longer exists.

It came from the old go-live item 1, which asked for ≥ 3 months of paper trading **and** ≥ 100
closed trades. The trade count bound, not the months, so each strategy's real wait was set by how
often it trades: about 15 months for RMW and RAW at ~80 trades a year, 19.4 for MVW, and **20.7 for
MOM** at ~58. MOM was being charged for trading less.

**On 2026-10-07 the owner replaced item 1 with "≥ 18 months of forward paper trading" and deleted
the trade-count clause** (`docs/plans/2026-10-03-seer-design.md` §1 item 1, with the revision note
in §13). Every entry now reaches its verdict at the same 18 months regardless of how often it
trades. MOM's wait fell from 20.7 months to 18; RMW's and RAW's *rose* from ~15 to 18.

So the gap this complaint described is gone, and the direction has partly reversed. **Anyone
reading the earlier handover will still believe it, which is why it is stated here in full rather
than quietly dropped.**

### 4.2 "The least stable of the four quant entries" — **true only on the narrowest reading, and it reverses on the obvious one**

The complaint is about the era table in
`docs/handover/2026-10-07-roster-first-night-and-survivorship.md` §3 — how far each strategy was
ahead of SPY in each of three stretches of the backtest. Those published numbers, subtracted:

| | 1996–2001 | 2002–2008 | 2009–2015 | average | spread (best − worst) |
|---|---|---|---|---|---|
| `RMW-FR` | +0.9 | +9.8 | −2.1 | +2.87 | **11.9** |
| `RAW-FR` | +5.9 | +10.8 | +2.6 | **+6.43** | 8.2 |
| `MOM-FR` | +6.2 | +8.2 | **−2.3** | +4.03 | 10.5 |
| `MVW-FR` | +0.7 | +8.8 | −2.1 | +2.47 | 10.9 |

(points per year ahead of SPY's total return; derived by subtraction from §3's published table.)

`MOM-FR` does own the single worst era number, −2.3. But it is worst **by 0.2 points**, over two
entries that are also behind SPY in that stretch for the same stated reason — §3's own finding that
these strategies earn their advantage in crashes and give some back in calm markets, and 2009–2015
was a bull run with no crash.

On spread — the ordinary meaning of "least stable" — `MOM-FR` is **third of four**, steadier than
both `RMW-FR` (11.9) and `MVW-FR` (10.9). And its average era edge, **+4.03 points a year**, is
higher than either of theirs. The complaint survives only if "least stable" is read as "has the
single lowest number in one of three cells", and under that reading it wins by a rounding margin.

### 4.3 "It was admitted as F4's bet inside the drawdown bar" — **true, and not a complaint**

This one is accurate. `MOM-FR` replaced `F4-FR`, which carried the same total-return-momentum bet
(measured at 0.99 correlation with F4's own variant) at a 22.2% worst fall that the owner's revised
20% limit refuses permanently. `MOM-FR` carries that bet at 18.37%.

That is a description of why it is on the roster, not an argument against it. The roster was
assembled as a **set of independent forward experiments**, not as a ranked list — migration
`db/migrations/013_roster_first_night.sql`'s own note says so: *"the slots are not bought for
ensemble performance, which is not on offer; they are bought as independent forward experiments
that could each reach real money."* A slot held for a particular bet is doing its job by holding
that bet.

**Two of the three complaints do not survive measurement, and the third is a description.**

---

## 5. What a swap would cost, which no column in §3 prices

Eleven lab candidates outscore `MOM-FR` on the luck test. Here they are with the method each came
from:

| candidate | lab method | luck test | MAR | dev-eligible today |
|---|---|---|---|---|
| `M0022-W-TV16` *(this is `RMW-FR`, already on the roster)* | M0022 | 0.9156 | 0.816 | yes |
| `M0020-W-NOSTOP` | M0020 | 0.9127 | 0.793 | **yes** |
| `M0022-W-TV14` | M0022 | 0.9122 | 0.857 | **yes** |
| `M0007-N20-RAW` *(this is `RAW-FR`, already on the roster)* | M0007 | 0.8985 | 0.768 | no |
| `M0011-RAW20-TV14-N21` | M0011 | 0.8844 | 0.763 | no |
| `M0020-W-S20` | M0020 | 0.8764 | 0.750 | no |
| `M0019-TV14N21-S20` | M0019 | 0.8684 | 0.791 | no |
| `M0019-RAW20-S15` | M0019 | 0.8540 | 0.680 | no |
| `M0020-W-TV14N21-S20` | M0020 | 0.8492 | 0.614 | no |
| `M0011-RAW20-TV16` | M0011 | 0.8387 | 0.658 | no |
| `M0007-N30` | M0007 | 0.8349 | 0.628 | no |

**All eleven are the same family.** M0007 is residual momentum — ranking stocks on how far they
rose *beyond what the market explains*, rather than on how far they rose. M0011, M0019, M0020 and
M0022 are each a descendant of it: M0011 adds a volatility brake, M0019 adds per-stock stops, M0020
lets a stopped stock come back at the next weekly check, M0022 re-reads M0011's brake every week.
Two of them are already on the roster — `RMW-FR` is M0022 and `RAW-FR` is M0007, held against each
other as the deliberate controlled test of whether the brake pays for itself.

Not one candidate from outside that family scores above `MOM-FR`.

So the two best-scoring alternatives are:

- **`M0022-W-TV14`** — literally `RMW-FR`'s own method with the brake set at 14% instead of 16%.
  Putting it on the board means paper-trading two settings of one dial for 18 months.
- **`M0020-W-NOSTOP`** — the weekly-check branch of the same residual-momentum line, with the stops
  removed. 15.27% a year at a 19.27% worst fall: a genuinely attractive book, and still the same
  underlying bet as two of the four slots.

`MOM-FR` is the roster's **only** strategy that ranks on plain total return *and* varies its
exposure by its own volatility regime — it holds less when it is jumpier than its own normal, and
stays fully invested otherwise. `MVW-FR` also ranks on total return but changes the *weights*
rather than the exposure, and was admitted precisely as the one portfolio-construction bet. Remove
`MOM-FR` and that reading disappears from the board entirely.

The lab can rank books. It cannot price the diversity of a set, because no candidate is scored
against the other four slots. **The swap on offer raises the roster's average lab score and
collapses what the roster was built to measure.**

---

## 6. The case for swapping, stated fairly

This document would be an argument rather than evidence if it listed only reasons for its own
conclusion. The strongest case against the verdict:

1. **A swap will never be cheaper than today.** No roster entry has traded a single paper session.
   There is no track record to discard and no clock to restart — the 18 months has not begun for
   anyone. Once the first session runs, replacing `MOM-FR` costs its accumulated record and resets
   its clock to zero, and that cost only grows. **The cheapest moment to be wrong about this is
   now.**
2. **Two of the alternatives are fully dev-eligible and `MOM-FR` is not.** `M0020-W-NOSTOP` and
   `M0022-W-TV14` clear every owner condition *and* the luck test. `MOM-FR` clears the five owner
   conditions and misses the luck test at 0.828 against 0.90. That is a real difference in what the
   lab is willing to say about them, not a technicality.
3. **`M0020-W-NOSTOP` is better on the numbers that matter most for a real-money decision**:
   15.27% a year against `MOM-FR`'s 12.56%, at a 19.27% worst fall against 18.37% — about 2.7 more
   points of annual return for about 0.9 more points of fall.

**Why it did not win.** The swap argument is, at bottom, *a lab candidate now scores higher than a
roster entry* — which is the exact argument §<RULE> was written to refuse, by a session that wrote
it before seeing these numbers and specifically so that it would not be written to justify a swap
somebody already wanted. §7.3 of the same document is why the refusal exists: the luck test falls
for everything as the lab keeps searching, with no book changing at all. `RMW-FR` itself scores
0.9156 today and drops below 0.90 at **N = 143** — roughly a day and a half of exploration. In a
few nights the same spreadsheet will say `RMW-FR` should be replaced too, and then its replacement,
and nothing in any book will have changed.

The cheapness argument in (1) is real and it cuts the right way, but it argues for *acting now*; it
does not supply a reason to act. The reasons on offer are (2) and (3), and both are lab scores.

---

## 7. What would change this verdict

The named triggers in §<RULE> are the list; this is only where to look for them in `MOM-FR`'s case.
What is **not** on the list: a lab candidate scoring higher, `MOM-FR`'s own luck score falling as
the lab keeps searching, or a better-looking book turning up in the same family.

**One question this document deliberately did not answer.** §3 shows `MVW-FR` scoring below
`MOM-FR` on both measures — 0.780 against 0.828 on the luck test, 0.564 against 0.684 on MAR. That
makes `MVW-FR` the lowest-scoring quant entry on the board, and it was not examined here, because
Q3 asked about `MOM-FR`. It should not be examined on these numbers alone either: `MVW-FR` was
admitted as the roster's only bet on *how much of each stock to hold* rather than on which stocks,
and as the least correlated with `RMW-FR` of anything that passed the five conditions. Whoever picks
this up: start from §<RULE>, not from the ranking.

---

## 8. What this phase did not touch

- **The rule itself** — `docs/plans/2026-10-04-method-lab-design.md` §<RULE> was read and applied,
  never amended.
- **`lab/lab.sqlite`** — opened read-only by URI. No trial, no insight. N is 110 before and after,
  and 0 test-window looks are spent before and after.
- **`engine/src/seer_engine/paper/roster.py`** — unchanged. No entry's `spec_digest` moved and no
  paper clock started or reset.
- **`engine/.research`** — unchanged; no `config_digest` moved.
- **Design §1 and §5**, and every file session `seer-fc` claimed.
- **The leaderboard hero figure** — §4 of the first-night handover says no work may be opened on it
  without re-checking the page first. None was.

## 9. Verification

```
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine
PYTHONPATH=/home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  /home/miftah/seer/engine/.venv/bin/python -m pytest -q      # 0 failed, 0 skipped
```

`pytest` **without** `PG_TEST_URL` reports `2812 passed, 385 skipped` — a confident green missing a
third of the suite, including every test that reads the `strategies` table. Always export it. And
without `PYTHONPATH` pointing at this worktree's `engine/src`, pytest silently tests the main
checkout instead of this branch.

The number that matters is **0 failed and 0 skipped**, not a total: this branch's baseline is 3197
and sibling work adds to it.

The lab, before and after this document: **N = 110 dev trials, 0 test-window looks used.**
`python -m seer_engine lab status` confirms it.
`````

**Impact:** Q3 is answered in the repository, with a reproducible command behind every number. The
20.7-month claim stops propagating. The "7th by MAR" slip is corrected in the one place a reader
will look. No behaviour changes anywhere in the engine or the web app.

---

### Step 3: Verify the numbers before committing the prose
**File:** none — a check, not an edit.
**Change:** run the reproduction block from §3 of the document (it is the exact script this plan was
measured with) and confirm, line for line:

```
N=110 policy=all-trials dev_trials=110 clear_all_five=26
MOM-FR (M0002-REL-85): DSR rank 12 of 26, MAR rank 8 of 26
  RMW-FR  M0022-W-TV16           dsr=0.9156 mar=0.816 cagr=11.68% dd=14.31% trades=1589 pf=2.065 eligible=True
  RAW-FR  M0007-N20-RAW          dsr=0.8985 mar=0.768 cagr=15.05% dd=19.59% trades=1596 pf=2.163 eligible=False
  MOM-FR  M0002-REL-85           dsr=0.8278 mar=0.684 cagr=12.56% dd=18.37% trades=1148 pf=2.332 eligible=False
  MVW-FR  M0008-N30-C07          dsr=0.7802 mar=0.564 cagr=11.27% dd=19.97% trades=1223 pf=2.143 eligible=False
above MOM-FR by the luck test, with the lab method each came from:
  M0022-W-TV16           M0022  dsr=0.9156 mar=0.816 eligible=True
  M0020-W-NOSTOP         M0020  dsr=0.9127 mar=0.793 eligible=True
  M0022-W-TV14           M0022  dsr=0.9122 mar=0.857 eligible=True
  M0007-N20-RAW          M0007  dsr=0.8985 mar=0.768 eligible=False
  M0011-RAW20-TV14-N21   M0011  dsr=0.8844 mar=0.763 eligible=False
  M0020-W-S20            M0020  dsr=0.8764 mar=0.750 eligible=False
  M0019-TV14N21-S20      M0019  dsr=0.8684 mar=0.791 eligible=False
  M0019-RAW20-S15        M0019  dsr=0.8540 mar=0.680 eligible=False
  M0020-W-TV14N21-S20    M0020  dsr=0.8492 mar=0.614 eligible=False
  M0011-RAW20-TV16       M0011  dsr=0.8387 mar=0.658 eligible=False
  M0007-N30              M0007  dsr=0.8349 mar=0.628 eligible=False
```

(Measured 2026-10-07 at base `3683d7b`; **re-run by the reconciler on the branch merged to
`ba8a05b` and reproduced exactly** — `clear_all_five=26`, `DSR rank 12 of 26`, `MAR rank 8 of 26`,
and the seven MARs strictly above `MOM-FR` are 0.856651, 0.816117, 0.792666, 0.791111, 0.768371,
0.763098, 0.749975.) **If `clear_all_five` is not 26, or the rank line is not
`12 of 26` / `8 of 26`, stop.** Something moved the lab's N or its constants, and the document's
whole §3 has to be re-measured before it is written. Do not reconcile by editing the prose toward
a number you did not re-measure.

Then confirm the external fact the document cites:

```
grep -n '18 months of forward paper trading' docs/plans/2026-10-03-seer-design.md
grep -n '^## 13\.' docs/plans/2026-10-03-seer-design.md
```

Expected: a hit on §1 item 1 — **line 17 of the worktree's own copy**, with the
`*(revised 2026-10-07; was "≥ 3 months … and ≥ 100 closed trades" — see §13)*` note — and `## 13.`
at line 232. **Corrected 2026-10-07:** an earlier draft of this step said the worktree still
carried the old text and sent the reader to the main checkout. It no longer does; the branch has
been merged up to `origin/main` @ `ba8a05b` and `seer-fc`'s revision is present here. The file is
still **read-only to this phase** — it belongs to `seer-fc`, and phase 2 owns the one append this
plan set makes to it. If the grep misses, the owner's decision has been reverted: §4.1's "void"
claim must then be re-stated as "being superseded", and the reconciler told.

**Impact:** stops the document from asserting a number or a decision that has drifted.

---

### Step 3b: Commit, with an explicit path allowlist

**File:** none (git)
**Change:** one path, named. **Never `git add -A`** — this worktree is shared with the other phases
of the set, and phase 2 runs concurrently in the same wave with `lab/lab.sqlite` and
`web/data/lab.json` dirty. Sweeping those into this commit would put phase 2's half-finished
insight on this phase's history.

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules
grep -n 'RULE' docs/handover/2026-10-07-mom-fr-under-the-replacement-rule.md   # must print NOTHING
git add docs/handover/2026-10-07-mom-fr-under-the-replacement-rule.md
git commit -F - <<'MSG'
docs(handover): MOM-FR is kept, judged under the roster replacement rule

Q3 of the 2026-10-07 handover, decided under the rule phase 3 wrote rather than under
the leaderboard -- which is what Q4 asked for, and the order the two questions had to
be answered in.

The verdict is keep. No trigger in the rule fires, and the argument that prompted the
question -- a lab candidate now scores higher -- is one of the things the rule refuses
by name. Three facts go on the record: MVW-FR scores below MOM-FR on both of the lab's
measures, so "the weakest of the five" is not what the numbers say; the 20.7-month
complaint became void when the owner made go-live item 1 eighteen months flat; and
every lab candidate above MOM-FR is a residual-momentum relative of two books already
on the roster, so the swap that raises the average score is the swap that collapses the
diversity.

No code, no roster change, no new paper clock. The lab is read-only: N stays 110 and 0
test-window looks stay 0.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
git show --stat --name-only HEAD   # must list exactly that one path
```

**Impact:** the phase's one deliverable lands. If `git show` lists more than that single path, the
allowlist leaked — reset and redo it rather than amending over a peer's work.

---

### Step 4: *(CONDITIONAL — NOT EXPECTED TO FIRE)* the roster edit, if and only if the verdict is "swap"

**This step does not run on the expected path.** The verdict in Step 2 is **keep**, and keep needs
**zero** lines of code: the handover document is the entire deliverable. Step 4 exists so that a
"swap" verdict has a legal shape to take rather than an improvised one, and so the reconciler can
see what this phase *would* claim if it fired.

**Fire this step only if Step 1's rule and Step 3's measurements together produce "swap".** If they
do, record in §1 of the document which named trigger from §<RULE> fired and what evidence met it —
a swap with no named trigger behind it is the exact thing phase 3's rule exists to prevent, and
would be a reason to stop and hand back to the owner instead.

**The only legal shape is a NEW roster id with its own paper clock. Never an edited entry.**
`paper/roster.py`'s module docstring states the contract: *"a changed strategy needs a **new id**
with its own paper clock, never an edited entry (`paper` refuses a started id whose stored digest
differs)"*, and `engine/tests/test_paper_roster.py:198` pins every digest
(`test_digests_are_pinned`). Editing `MOM-FR`'s `RosterRow` in place would move its digest, fail
that pin, and — had it ever traded — be refused by the paper night itself.

What a swap touches, in order:

1. **`engine/src/seer_engine/paper/roster.py:149`** — a new id constant beside the 013 block, e.g.
   `NEW_ID = "NOS-FR"  # lab M0020-W-NOSTOP in fractional shares; replaces MOM-FR (owner, <date>)`.
2. **`engine/src/seer_engine/paper/roster.py` params block (near `MINVAR_PARAMS`, ~line 340)** —
   the new object's params pulled from the lab method, in the existing shape:
   `NOSTOP_PARAMS = next(c.params for c in M0020.candidates if c.id == "M0020-W-NOSTOP")`.
3. **`RESOLVER` (`roster.py:351`)** — one appended entry, `"NOSTOP": Binding(obj=NOSTOP, params=NOSTOP_PARAMS)`,
   with a comment naming the lab method and the promotion date. **Append only.** The docstring is
   explicit: *"Keys are stable forever — a stored spec names one, so renaming a key would move a
   live digest. Append; never rename, never remove a key a started strategy's spec still names."*
4. **`LAB_PROVENANCE` (`roster.py:393`)** — one appended entry for the new id: `method_id`,
   `candidate_id`, the lab status **at admission** (frozen, not live), `basis`, and a plain-prose
   `reason` that names §<RULE>'s trigger. **Do not edit `MOM_ID`'s existing line** — the docstring
   says *"Append; never edit a started entry's line to make it read better."*
5. **`SEED_ROWS` (`roster.py:732`)** — append the new `RosterRow` (new `sort`, `engine="book"`,
   `rules_id="monthly-hold-frac"`, the new `object_name`, `registry_id=None`, a `gate_note` in the
   style of the 013 rows), **and** set `status="retired"` on `MOM-FR`'s existing row with an inline
   comment giving the reason. Retirement is digest-safe and proven so:
   `test_retiring_a_strategy_does_not_move_its_digest` (`test_paper_roster.py:462`).
6. **`engine/tests/test_paper_roster.py` `PINS`** — one new entry. **Compute the digest; never type
   one by hand.** `spec_digest(spec(e))` for the new entry, read out of a run, pasted in. The
   existing ten pins must not move; if any does, something in step 3 or 5 touched a started entry
   and the change is wrong.
7. **`db/migrations/014_<name>.sql`** — the new `strategies` row and the `MOM-FR` retirement, **byte
   for byte** matching the Python row, in migration 013's style, applied to Neon. The 013 rows and
   `SEED_ROWS` agree byte for byte today and that property is load-bearing:
   `test_the_database_rows_rebuild_the_roster_with_the_pinned_digests` (`test_paper_roster.py:483`)
   builds the roster from the database through the same `from_rows` path.

**Verification if Step 4 fires** (beyond §9's suite run):

```
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine
PYTHONPATH=/home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  /home/miftah/seer/engine/.venv/bin/python -m pytest tests/test_paper_roster.py -q
PYTHONPATH=... /home/miftah/seer/engine/.venv/bin/ruff check --no-cache src tests
```

and the `MOM-FR` digest must be **unchanged** in `PINS` — a retired entry keeps its digest.

**If Step 4 fires, tell the reconciler.** It changes this phase's Interface Contract from
"creates one document" to "creates one document, appends to `paper/roster.py`'s two code-side
tables and `SEED_ROWS`, appends one `PINS` entry, adds one migration", and `paper/roster.py` is
listed in the index's invariant 5. No other phase in this set touches `paper/`, so the collision
risk is with `seer-fc` rather than with a sibling phase — but the index assumed "no code" and
would need its Files count corrected.

**Impact on the expected path: none. Nothing in Step 4 runs.**

---

## Verification

**Build:** nothing is compiled; this phase ships one markdown file.

**Tests:**

```
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine
PYTHONPATH=/home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  /home/miftah/seer/engine/.venv/bin/python -m pytest -q
```

Expected: **0 failed, 0 skipped**, at a count no lower than **3197** — the branch baseline,
re-counted by the reconciler at `ba8a05b`. This phase adds no test and touches no code, but it runs
in wave 2 of a shared worktree **after** phases 1 and 4 have landed theirs, so the total will be
3197 plus phase 1's `test_delisting.py` plus phase 4's 3. **Assert `0 failed, 0 skipped`, never a
specific total.** Without `PG_TEST_URL`: `2812 passed, 385 skipped`, which is **not** a pass and
must never be quoted as one.

**One shared-worktree failure that is not this phase's.** Phase 2 runs concurrently in wave 2 and
has a one-command window between writing its `insights` row and regenerating `web/data/lab.json` in
which `test_lab_snapshot.py:449` fails for everyone in the worktree. If that is the only failure,
wait for phase 2's Step 8 and re-run before investigating. If `-n auto` errors with `unrecognized arguments: -n`, reinstall `pytest-xdist` into
`/home/miftah/seer/engine/.venv`; do **not** reach for `-o addopts`.

**Lab, unchanged before and after:**

```
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules
PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab status
```

Expected: **N = 110 dev trials, 0 test-window looks used.** Any other number means this phase wrote
to the lab, which it must not.

**Manual check — the document itself:**

1. `grep -n 'RULE' docs/handover/2026-10-07-mom-fr-under-the-replacement-rule.md` → **no output.**
   Every `§<RULE>` and `<RULE-TITLE>` token resolved, and both HTML implementer comments deleted.
2. The §2 table has one row per trigger and one per refusal that phase 3 actually wrote, using
   phase 3's names, each marked met/not-met with evidence.
3. `git status --short` lists **only** `docs/handover/2026-10-07-mom-fr-under-the-replacement-rule.md`
   as this phase's work. The swarm shares one worktree, so peers' in-flight edits will also show;
   commit with an **explicit path allowlist**, never `git add -A`, and verify afterwards that the
   commit's file list *equals* that allowlist.
4. No jargon left unglossed: "DSR" appears as "the luck test", "MAR" as "return per unit of worst fall",
   "residual momentum" as "how far they rose beyond what the market explains". The owner is not a
   quant.

**Exit criteria:**

- `docs/handover/2026-10-07-mom-fr-under-the-replacement-rule.md` exists and states the verdict
  **keep `MOM-FR`** plainly, in its first screen.
- It cites phase 3's rule by its **real section number and title**, and walks that rule's named
  triggers and refusals one by one. It contains no rule of its own.
- It records the lab evidence: **26 of 110 clear all five owner conditions today; `MOM-FR` is 12th
  of 26 on the luck test and 8th of 26 on MAR**, with the exact read-only command that reproduces
  both.
- It records that **`MVW-FR` scores below `MOM-FR` on both measures**, so "the weakest of the five"
  is not what the lab says.
- It records that Q3's *"slowest path to a verdict (20.7 months)"* is **void** under the owner's new
  go-live item 1, with the citation.
- It weighs family diversity — **all eleven candidates above `MOM-FR` are residual-momentum
  relatives of two entries already on the roster** — against the alternatives' higher scores.
- It states the case **against** its own verdict, including that nothing has traded yet so a swap
  will never be cheaper.
- `paper/roster.py`, `test_paper_roster.py` and `db/migrations/` are **unchanged** (Step 4 did not
  fire).
- `lab status` reports N = 110 and 0 test-window looks, unchanged. (**Insights may read 32 or 33**
  depending on whether phase 2 has landed its row yet; that is phase 2's number, not this phase's,
  and either reading is correct here.)
- The full suite passes: **0 failed, 0 skipped**, at a count no lower than the branch baseline
  of 3197.
- The commit's file list **equals** the one-path allowlist
  `docs/handover/2026-10-07-mom-fr-under-the-replacement-rule.md`.

## Handoffs

- **`MVW-FR` is the lowest-scoring quant entry on the board** (0.7802 luck test, 0.564 MAR — below
  `MOM-FR` on both), and this phase deliberately did not examine it. Q3 asked about `MOM-FR`, and
  R3 is this phase's only requirement; opening `MVW-FR` here would be the churn Q4 warns against,
  decided on exactly the lab-score argument phase 3's rule refuses. §7 of the document records it
  as an open question pointing at §<RULE> rather than at the ranking. **Not assigned to a phase in
  this set.**
- **"7th by MAR" — corrected everywhere, 2026-10-07. No action left.** The index's phase-5 exit
  criterion, the analysis file's M3 and `phase-3.md`'s R3 handoff now all read **8th of 26**; the
  DSR rank of 12th of 26 was confirmed exactly and never changed. The only surviving "7th" strings
  in this plan set are this file's own account of the correction, which must stay. See the
  Interface Contract.
- **`RAW-FR` sits 0.0015 below the luck bar (0.8985 vs 0.90)** and will cross it downward within a
  night or two of further exploration, by the same ratchet lab design §7.3 measures. It will be the
  first roster entry the rule is tested on in anger. Noted, not acted on — no trigger in §<RULE>
  fires on a falling luck score, which is the point.
- **`M0020-W-NOSTOP` (15.27%/yr at a 19.27% worst fall, fully dev-eligible) is the strongest book in
  the lab that is on no roster.** It is left in the lab deliberately. If a slot ever opens for a
  reason the rule names, it is the obvious first candidate — and a reader should know that the slot
  it would most naturally take is a residual-momentum one, not `MOM-FR`'s.
- **Design §1 item 1 and `backtest/dev.py` `_MIN_TRADES` now disagree** (18 months with no trades
  clause, against a dev gate still requiring 100 trades). That asymmetry is **phase 4's** — R2.
  This phase only cites the new item 1; it neither documents nor guards the asymmetry.

## Rollback

`git revert` the single commit, or `git rm docs/handover/2026-10-07-mom-fr-under-the-replacement-rule.md`.

Nothing else is affected: no database migrated, no `config_digest` moved, no lab trial or insight
written, no roster digest touched, no paper clock started. The lab's N is 110 before and after and
its test window stays unspent. Reverting this phase leaves Q3 open — it does not leave anything
broken.

*(If Step 4 had fired, rollback would additionally mean reverting the `roster.py`, `PINS` and
migration changes **and** un-applying `014_*.sql` from Neon — which is the real reason the swap
branch is the one that must be deliberate. It did not fire.)*
