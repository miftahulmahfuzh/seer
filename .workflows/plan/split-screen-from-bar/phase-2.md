# Phase 2: The dated owner revision, and the before/after

**Plan set:** `SPLIT_SCREEN_FROM_BAR_PLAN.md`
**Analysis:** `docs/analyzer/20261014-095218-B7QD_code_analyzer.md`
**Satisfies:** R1 (the bar is 25%), R2 (the screen is a separate number), R3 (recorded as a dated owner revision)
**Depends on:** Phase 1
**Difficulty:** NORMAL
**Package:** `docs`

---

## Goal

After this phase the design document carries a `## 18.`, dated 2026-10-14, that records two
decisions the owner made in one sentence: the go-live maximum drawdown is 25%, and the lab's
dev-eligibility screen is no longer the same number as that bar. It preserves the sentence it
replaces verbatim, quotes the owner verbatim, carries the measurement that prompted the change
and the measured before/after, and states the residual risk honestly. Nothing above `## 18.`
changes except one inline pointer on condition 4, which the house convention requires.

---

## Interface Contract

**Deletes:** nothing.

**Renames:** nothing.

**Creates:** `## 18. Revision 2026-10-14 (owner): the go-live drawdown bar is 25%, and the lab's
screen is a separate number` — appended to `docs/plans/2026-10-03-seer-design.md` after the last
line of `## 17.` (currently file line 549).

**Signature changes:** none. No source file, no test, no database, no `web/`.

**Edits above the new section — exactly one line:**
`docs/plans/2026-10-03-seer-design.md:20`, §1 go-live condition 4's inline revision marker.
This is a deliberate, stated exception to "touch nothing above `## 18.`", and it is the house
convention, not an improvisation — see Step 1 for the evidence that §11 and §13 both did it.

**Requires (from earlier phases) — HARD, checked at Step 0:**
- Phase 1 has landed. `tuning.MAX_DRAWDOWN` is 0.25 and `tuning.DEV_MAX_DRAWDOWN` imports and is
  0.50. The screen is **one decision written at four call sites** — `dev.FAILURE_LABELS`,
  `dev.make_row`, `store.owner_failures`, `store._blocking` (index invariant 2, corrected
  2026-10-14) — not one. §18's prose must not claim "exactly one call site".
- Phase 1 has **reported** the measured before/after. The reconciled figures, confirmed
  independently read-only on the committed lab (md5 `00f7ebec1b3134e67e3b087226d308b7`, gate
  `methods` N = 81):

  | | clears the drawdown condition alone | **dev-eligible (full verdict)** |
  |---|---|---|
  | screen 0.20 (before) | 93 trials / 37 methods | **26 trials / 16 methods** |
  | screen 0.50 (after) | 319 trials / 76 methods | **67 trials / 32 methods** |

  **§18's headline is the full-verdict pair (index Decision D8).** The browsable pair may appear
  only beside it and clearly labelled. Step 3 says what to do if phase 1's report disagrees.
- Phase 1's choice of screen value (plan index Decisions D1 and D11: **0.50**, and an implementer
  may argue another value **from measurement**). §18 states it in prose as a fraction ("a fall of
  one half" if 0.50 stood). Step 3 says how to read it off the landed tree.
- Phase 1's Step 5b has landed: `store.py:1904`'s re-evaluation prose names the **screen**. §18
  therefore carries **no** "do not run `lab reevaluate`" caveat — there is nothing to warn about.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/backtest/metrics.py`, `tuning.py`, `lab/store.py` — Phase 1.
- `engine/tests/**` — Phase 1. In particular **`engine/tests/test_dev_trades_bar.py` is Phase 1's**,
  even though its failure message names the design document (see Handoffs).
- `web/**`, `lab/lab.sqlite`, `web/data/lab.json` — Phase 1.
- Everything in `docs/plans/2026-10-03-seer-design.md` above `## 18.`, except file line 20.
- `docs/lab/survivorship/grid.csv` — a closed record, read only.

---

## Files

| File | Action | What changes |
|---|---|---|
| `docs/plans/2026-10-03-seer-design.md` | modify (append) | new `## 18.` after line 549, the last line of `## 17.` |
| `docs/plans/2026-10-03-seer-design.md:20` | modify (one line) | condition 4's inline revision marker now points at §18 |

Two edits, one file. Nothing else in the tree.

---

## Implementation Steps

### Step 0: Confirm Phase 1 has landed, and read its numbers

**File:** none — this is a precondition check.
**Change:** Before writing a word, verify the tree you are on.

**THIS IS A HARD STOP.** If any check below fails, **stop the phase and report**. Do not write a
word of §18, do not "check again later", do not proceed on the draft numbers. §18 is a permanent
owner record; describing a change that has not landed is the one failure this phase cannot recover
from, and it is cheap to avoid.

```bash
set -e
cd /home/miftah/.worktrees/seer/split-screen-from-bar

# 1. the bar moved, the screen exists, and they are two different numbers
PYTHONPATH=/home/miftah/.worktrees/seer/split-screen-from-bar/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -c '
import sys
from seer_engine.backtest import tuning
bar = tuning.MAX_DRAWDOWN
screen = getattr(tuning, "DEV_MAX_DRAWDOWN", None)
print("bar", bar, "screen", screen)
if screen is None:
    sys.exit("STOP: tuning.DEV_MAX_DRAWDOWN does not exist -- phase 1 has not landed")
if bar != 0.25:
    sys.exit("STOP: tuning.MAX_DRAWDOWN is %r, not 0.25 -- phase 1 has not landed" % (bar,))
if screen <= bar:
    sys.exit("STOP: screen %r is not looser than the bar %r -- R2 is not in the tree" % (screen, bar))
'

# 2. phase 1 Step 5b landed: the re-evaluation prose names the screen, not the bar
grep -q "max drawdown screen of" engine/src/seer_engine/lab/store.py

# 3. phase 1 left nothing of its own uncommitted
git status --short
```

Then read phase 1's report — its commit messages are the primary source:

```bash
git log --format='%H%n%B' -5 -- engine/src/seer_engine/backtest/metrics.py
ls .workflows/plan/split-screen-from-bar/
```

**Impact:** none. This is a read, and a gate.

---

### Step 1: Update condition 4's inline revision marker (the one edit above `## 18.`)

**File:** `docs/plans/2026-10-03-seer-design.md:20`

**Why this is allowed, in full.** The phase boundary says §1's text is quoted and never edited.
That rule is about the *conditions themselves*. The inline parenthetical marker is a different
object: it is a pointer to where the condition was last revised, and the house has moved it both
times a condition changed. The evidence, read off the current file:

- Line 16: `1. ≥ 18 months of forward paper trading  *(revised 2026-10-07; was "≥ 3 months … and ≥ 100 closed trades" — see §13)*`
  — §13 rewrote condition 1 **and** its marker.
- Line 20: `4. Max drawdown ≤ 20%  *(revised 2026-10-07; was 15% — see §11)*`
  — §11 rewrote condition 4 **and** its marker.

Leaving line 20 alone would make §1 claim a 20% bar forever while §18 says 25%, which is worse
than the edit. So the marker moves, following the same form.

**Current text, exactly (line 20, two spaces before the italic marker):**

```
  4. Max drawdown ≤ 20%  *(revised 2026-10-07; was 15% — see §11)*
```

**Replacement text, exactly:**

```
  4. Max drawdown ≤ 25%  *(revised 2026-10-14; was 20% — see §18, and §11 for the 15% before that)*
```

The chain is kept because condition 4 is the only condition revised twice, and dropping the §11
pointer would orphan a dated revision that is still the record of the first move.

**What is NOT edited, deliberately.** Line 14 reads `(fixed; moved only by a dated owner revision
— see §11)`. That clause points at §11 because §11 is where the original "fixed now, never moved"
guarantee was weakened into "moved only by a dated owner revision". §18 does not weaken it again;
it exercises it. The pointer stays on §11. Record this as a decision rather than an oversight.

**Impact:** §1 now states the live bar. Nothing reads this file programmatically
(`grep -rn "seer-design" engine/src engine/tests web` returns only prose references and
`test_dev_trades_bar.py`'s `RECORD` string, which names §13, not §1).

---

### Step 2: Append `## 18.`

**File:** `docs/plans/2026-10-03-seer-design.md`, appended after the current last line (549),
which is the closing line of `## 17.`:
`**The uncertainty, stated.** 1996 and 1997 remain under half covered in *both* histories, and 111`
/ `index members are missing from both, so the fuller history is better evidence, not a true one.`

The file ends with a newline. Append one blank line, then the section below.

**Change:** paste the section verbatim, with the marked slots filled from Step 3. Every slot has
the form `‹…›` and Step 3 resolves each one. Nothing else in the section is provisional.

**Code:**

```markdown
## 18. Revision 2026-10-14 (owner): the go-live drawdown bar is 25%, and the lab's screen is a separate number

Two changes arrived in one sentence from the owner, and they are not the same change. One is about
his money. The other is about what the lab is allowed to look at. They had been the same number by
accident, and that accident was the single most expensive constraint in the research programme.

- **Go-live condition #4 is now "Max drawdown ≤ 25%."** The sentence it replaces, preserved:
  *"4. Max drawdown ≤ 20%"*, written 2026-10-07 under §11 — which had itself replaced *"4. Max
  drawdown ≤ 15%"* from 2026-10-03. The bar has now moved twice. Both times the owner moved it,
  both times on the record, and both times the sentence it replaced was kept rather than tidied
  away.

- **The lab's screen is no longer that number.** Until today a single figure answered two
  unrelated questions: how far the owner is prepared to watch his own money fall, and how deep a
  fall the lab will even bother to study. The first is a statement about risk appetite. The second
  is a statement about where research time goes. The second had been quietly inheriting the first.
  They are now two separate figures, and the screen is set at a fall of ‹SCREEN-IN-WORDS›.

- **Who and why.** The owner, 2026-10-14: *"i agree with you. this is what i am afraid of. beating
  SPY is so hard already, yet we still impose these strict constraints . you know what, let's do
  your suggestion, and in fact, raise my risk appetite more to 25%"*

  The suggestion he is agreeing to is the split: keep the figure as the real-money bar, applied at
  the moment a strategy would be funded, and loosen it on the screen, whose job is to surface
  candidates worth understanding. A strategy that falls too far for the owner to hold can still be
  found, measured, argued about and learned from — it simply cannot be given money. Those were
  always two different refusals, and only one of them had to be this strict. He then went further
  than the suggestion and raised the real-money bar itself, from 20% to 25%.

- **The measurement that prompted it.** Of the 399 dev-window trials on record, 257 beat
  total-return SPY — a result the lab exists to find. The 20% drawdown bar then rejected 188 of
  those 257, which is 73% of everything that had already cleared the hardest test in the building.
  Nothing else in the lab rejects at anything like that rate. The bar was not one constraint among
  five; it was *the* constraint, and almost everything the lab had ever found was dying behind it.

- **What the benchmark itself does, for scale.** SPY fell 56.5% peak to trough over the dev window,
  bottoming on 2009-03-09, while returning 7.86% a year. The lab had been requiring its strategies
  to fall less than a third as far as the thing they are measured against. A strategy that fell by
  half would still have fallen less than simply owning the index — which is the reasoning behind
  where the new screen sits, and it is a reason rather than a preference.

- **Measured effect on the lab's own records.** Against the committed dev trials, the number of
  trials that clear every one of the five owner conditions and the luck test moves from
  ‹ELIGIBLE-BEFORE-TRIALS› to ‹ELIGIBLE-AFTER-TRIALS›, across ‹ELIGIBLE-BEFORE-METHODS› distinct
  methods before and ‹ELIGIBLE-AFTER-METHODS› after. Those are candidates that already beat the
  benchmark, already passed the luck test, and were being set aside for one reason only. A looser
  but separate count, which is the one the screen exists to move: the number of trials a person can
  sit down and browse — those that clear the drawdown condition, whatever else they miss — goes
  from ‹BROWSABLE-BEFORE-TRIALS› to ‹BROWSABLE-AFTER-TRIALS›. The two counts answer different
  questions and are not interchangeable.

- **The part of this that argues against the number chosen, stated rather than buried.** Most of
  the gain in the first count arrives by the time the screen reaches 25%: at that setting it
  already reaches ‹ELIGIBLE-AT-25-METHODS› of the ‹ELIGIBLE-AFTER-METHODS› methods, and moving on
  from 40% to one half adds no further method at all. So the case for setting the screen at one
  half is not that it finds more methods than a tighter setting would. It is that the screen must
  not be *the same number* as the money bar, or the separation is cosmetic and quietly closes again
  the next time the bar moves — and that browsing is cheap, which is the second count above.

- **What it does not change.**
  - Conditions 1, 2, 3 and 5 are untouched. Eighteen months of forward paper, beating SPY, a
    profit factor of at least 1.3, and a ten-year backtest all stand exactly as written.
  - **Nothing is promoted and nothing is tested.** This makes more methods worth looking at. It
    does not look at them. Spending a test-window look is a separate act, taken later and by the
    owner; four have been spent and that count is unchanged by this revision.
  - **No recorded trial is edited.** Verdicts are re-derived from the numbers each trial recorded,
    against the bars in force today — which is exactly how the 2026-10-07 move worked, and why
    rows judged under older bars keep the wording of their own day.
  - **The bar still governs money.** The promotion check and the go-live checklist read the
    real-money figure, not the screen. A method that falls 30% can now be studied, written about
    and understood. It can never be funded.
  - **One known rough edge on the site, named rather than discovered.** The lab page prints a
    target beside each condition, and for the fall it prints the money bar — "25% or less" — on
    every trial, including one the lab is now studying at a much deeper fall and correctly marks
    as clearing the screen. The tick is right and the number beside it is the wrong one of the two.
    Nothing is mis-judged and nothing is mis-recorded; the page simply has one figure where there
    are now two. It is left as it is in this revision, and it is written down here so that reading
    it is not mistaken for a verdict that disagrees with itself.
  - §17's rule stands and simply follows the bar. A dev-window drawdown under the bar is still not
    sufficient evidence that a strategy clears it, because the fuller history moves drawdowns by
    as much as fourteen points in either direction. Re-read against the committed survivorship
    grid at the new bar: 49 variants pass on the dev store, and 7 of them cross on the fuller
    history — 14%, where the same count at 20% was 11 of 28, or 39%. The rule bites less often at
    25%, which is a consequence of the bar moving and not a weakening of the rule.

- **The residual risk, stated plainly.** A looser screen means more candidates to look at, and
  every additional look is another chance to be fooled by something that only worked by luck. That
  is not a new danger and it is not unpriced: the luck test and the policy that decides how hard
  it has to be exist for precisely this, and the specific reason this change cannot quietly
  degrade them is that the count feeding that policy counts methods **tried**, not methods that
  passed. Loosening the screen admits more results; it cannot inflate the count, and it cannot
  move any luck score. The honest counterweight is on the other side: 25% is a real increase in
  the fall the owner has said he could sit through, and on the 20,000,000 IDR at stake that is
  5,000,000 IDR of paper loss before a strategy is judged to have broken its promise. That is the
  part of this revision that is a preference rather than a measurement, and it is his to make.

- **A measurement elsewhere that moves with it, noted so it is not mistaken for drift.** §13's
  record of which trials are held out by the dev-window trades bar alone is re-computed against
  the live figures on every test run. It is the **screen** that moves it, not the money bar: a
  trial that used to miss both the fall limit and the trade count now misses only the trade count,
  so it joins that set. Loosening the screen therefore grows it from five trials to
  ‹TRADES-HELD-OUT-AFTER›. §13's load-bearing finding survives: every trial in the larger set still
  sits below the luck bar or carries no luck score at all, so dropping the trades bar would still
  change zero verdicts. §13 is a dated record and is left as it was written; this is where the
  re-measurement lives.

- **Where it is implemented.** `backtest.metrics.MAX_DRAWDOWN`, re-exported as
  `backtest.tuning.MAX_DRAWDOWN`, remains the one Python definition of the real-money bar, and
  `web/lib/golive.ts` the one TypeScript definition, pinned to it by `web/lib/golive.test.ts`
  through `data/lab.json`'s gate. The screen is a second constant,
  `backtest.metrics.DEV_MAX_DRAWDOWN`, re-exported the same way. It is one decision — the lab's
  dev-eligibility check — written at four call sites that must always agree: the label the check
  records, the check applied to a fresh run, the check applied to a recorded row, and the second,
  deliberate repetition of it that guards the write. The two constants are not permitted to
  collapse back into one — that would undo this revision entirely.
```

**Impact:** the design document gains a section. Nothing executes differently.

---

### Step 3: Resolve the four slots

**File:** `docs/plans/2026-10-03-seer-design.md` (the section just pasted)
**Change:** replace each `‹…›` with a measured figure.

**THE ONE TRAP IN THIS STEP — read before running anything.** Every script below must patch
`tuning.DEV_MAX_DRAWDOWN`, **not** `tuning.MAX_DRAWDOWN`. After phase 1, `store.owner_failures` and
`store._blocking` compare against the screen; patching the money bar on the landed tree changes
nothing and every row of the sweep prints the same number. The draft of this phase made exactly
that mistake and reported the held-out trades set growing to **8** — which is the count at a 0.25
*screen*, a screen that does not land. The reconciler re-derived it at the 0.50 screen that does:
the answer is **12**. The scripts below are corrected.

**And do not confuse the two kinds of count.** The `93 → 319` trials / `37 → 76` methods figures are
trials passing the *drawdown condition alone*; the analysis's M3 table is labelled that way and §17
quotes the same 93. Dev-eligibility additionally requires beating SPY, the profit factor, the trades
bar and the luck test, so it is far smaller: **26 → 67 trials, 16 → 32 methods**. §18's headline is
the eligibility pair (index Decision D8); the browsable pair appears beside it, labelled.

**`‹SCREEN-IN-WORDS›`** — read the landed value and write it in prose, not as a decimal:

```bash
PYTHONPATH=/home/miftah/.worktrees/seer/split-screen-from-bar/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -c \
  "from seer_engine.backtest import tuning; print(tuning.DEV_MAX_DRAWDOWN)"
```

If it is `0.50`, write **one half**. If Phase 1 argued another value from measurement, write that
value as a percentage in words (`forty per cent`) or as a plain figure (`40%`), and add one
sentence naming the measurement Phase 1 gave for it. If it is not 0.50, also re-check that the
"a strategy that fell by half would still have fallen less than simply owning the index" sentence
in the scale bullet still reads correctly, and adjust it to the value that landed.

**`‹ELIGIBLE-BEFORE-TRIALS›`, `‹ELIGIBLE-AFTER-TRIALS›`, `‹ELIGIBLE-BEFORE-METHODS›`,
`‹ELIGIBLE-AFTER-METHODS›`, `‹BROWSABLE-BEFORE-TRIALS›`, `‹BROWSABLE-AFTER-TRIALS›`,
`‹ELIGIBLE-AT-25-METHODS›`** — take Phase 1's reported figures first. Read its commit message and
its plan file's exit-criteria report (exit criterion 7 obliges it to report them). If they are
present, quote them and stop.

The reconciled values, confirmed independently read-only at base `49287bb` (lab md5
`00f7ebec1b3134e67e3b087226d308b7` unchanged, gate `methods` N = 81, `test_looks` = 4):

| screen | browsable (drawdown condition alone) | dev-eligible (full verdict) |
|---|---|---|
| 0.20 (before) | **93** trials / 37 methods | **26** trials / **16** methods |
| 0.25 | 196 trials / 61 methods | 60 trials / **30** methods |
| 0.40 | 303 trials / 75 methods | 67 trials / 32 methods |
| **0.50 (after)** | **319** trials / 76 methods | **67** trials / **32** methods |

So: `‹ELIGIBLE-BEFORE-TRIALS›` = 26, `‹ELIGIBLE-AFTER-TRIALS›` = 67,
`‹ELIGIBLE-BEFORE-METHODS›` = 16, `‹ELIGIBLE-AFTER-METHODS›` = 32,
`‹BROWSABLE-BEFORE-TRIALS›` = 93, `‹BROWSABLE-AFTER-TRIALS›` = 319,
`‹ELIGIBLE-AT-25-METHODS›` = 30.

Re-measure on the landed tree anyway and quote what you measure:

```bash
cd /home/miftah/.worktrees/seer/split-screen-from-bar
md5sum lab/lab.sqlite
PYTHONPATH=/home/miftah/.worktrees/seer/split-screen-from-bar/engine/src \
  /home/miftah/seer/engine/.venv/bin/python - <<'PY'
from seer_engine.lab import store
from seer_engine.backtest import tuning

conn = store.connect_readonly(store.COMMITTED_DB)
rows = conn.execute("SELECT * FROM trials WHERE window='dev' ORDER BY n").fetchall()
g = store.gate(conn)
print("gate:", g.policy, "N =", g.n, "| test_looks =", store.test_looks(conn))
for screen in (0.20, 0.25, 0.40, 0.50):
    # THE SCREEN, not the money bar. On the landed tree owner_failures and _blocking read
    # tuning.DEV_MAX_DRAWDOWN; patching tuning.MAX_DRAWDOWN here would change nothing and print
    # the same row four times. That is the draft's bug and it is what produced "8" below.
    tuning.DEV_MAX_DRAWDOWN = screen
    browsable = [t for t in rows
                 if t["max_drawdown"] is not None and float(t["max_drawdown"]) <= screen]
    eligible = [t for t in rows if store.verdict(conn, t, at=g).eligible]
    bm = {str(t["method_id"]) for t in browsable}
    em = {str(t["method_id"]) for t in eligible}
    print(f"screen={screen:.0%}: browsable {len(browsable)} trials / {len(bm)} methods"
          f"  |  dev-eligible {len(eligible)} trials / {len(em)} methods")
conn.close()
PY
md5sum lab/lab.sqlite
```

Measured output, for cross-checking Phase 1's report (reconciler, read-only, hash unchanged):

```
gate: methods N = 81 | test_looks = 4
screen=20%: browsable 93 trials / 37 methods  |  dev-eligible 26 trials / 16 methods
screen=25%: browsable 196 trials / 61 methods  |  dev-eligible 60 trials / 30 methods
screen=40%: browsable 303 trials / 75 methods  |  dev-eligible 67 trials / 32 methods
screen=50%: browsable 319 trials / 76 methods  |  dev-eligible 67 trials / 32 methods
```

So at a 0.50 screen the eligibility sentence reads **"from 26 to 67, across 16 distinct methods
before and 32 after"**, the browsable sentence reads **"from 93 to 319"**, and
`‹ELIGIBLE-AT-25-METHODS›` is **30**. If Phase 1 reports different figures, **Phase 1's figures
win** — it measures the landed
tree, this measured the base — but the gap must be explained in the commit message rather than
papered over, because a disagreement means one of the two measurements is asking a different
question. The script above is read-only (`connect_readonly`, `mode=ro`) and records nothing; the
hash must be identical on both sides.

**`‹TRADES-HELD-OUT-AFTER›`** — the number of recorded dev trials whose *only* miss against the
five owner conditions is the trades bar. **CORRECTED BY RECONCILIATION, 2026-10-14: it is twelve,
not eight.** The draft of this step patched `tuning.MAX_DRAWDOWN`; the drawdown comparison inside
`store.owner_failures` reads `tuning.DEV_MAX_DRAWDOWN` on the landed tree, so the draft measured a
0.25 screen and got 8. The screen that lands is 0.50 and the answer there is **12**. Phase 1
measured the same 12 on the applied change and owns the matching constant list in
`engine/tests/test_dev_trades_bar.py` — **the two numbers must agree, and 12 is the agreed one.**

```bash
cd /home/miftah/.worktrees/seer/split-screen-from-bar
md5sum lab/lab.sqlite
PYTHONPATH=/home/miftah/.worktrees/seer/split-screen-from-bar/engine/src \
  /home/miftah/seer/engine/.venv/bin/python - <<'PY'
from seer_engine.lab import store
from seer_engine.backtest import tuning, dev

conn = store.connect_readonly(store.COMMITTED_DB)
rows = conn.execute("SELECT * FROM trials WHERE window='dev'").fetchall()
conn.close()
_spy, _dd, _pf, trades_label, _owner = dev.FAILURE_LABELS
for screen in (0.20, 0.50):
    tuning.DEV_MAX_DRAWDOWN = screen      # THE SCREEN. Not tuning.MAX_DRAWDOWN -- see the trap above.
    held = sorted(
        (str(r["candidate_id"]), int(r["trades"]), r["dsr"])
        for r in rows
        if store.owner_failures(r) == (trades_label,)
    )
    lucky = [h for h in held if h[2] is not None and float(h[2]) >= store.DSR_MIN]
    print(f"screen={screen:.0%}: held out by the trades bar alone = {len(held)}; clearing the luck bar = {len(lucky)}")
    for name, count, dsr in held:
        print(f"    {name:22s} {count:3d} trades  dsr={dsr}")
PY
md5sum lab/lab.sqlite
```

Measured output (reconciler, read-only, lab md5 `00f7ebec1b3134e67e3b087226d308b7` on both sides):

```
screen=20%: held out by the trades bar alone = 5; clearing the luck bar = 0
    F1-SPY-10MSMA-M         13 trades  dsr=None
    F1-SPY-SMA200-M         11 trades  dsr=None
    M0084-BAND3-W           10 trades  dsr=0.814838264250398
    M0084-FABER-M           13 trades  dsr=0.8372714490694413
    M0084-MONTHLY           11 trades  dsr=0.8837970886760282
screen=50%: held out by the trades bar alone = 12; clearing the luck bar = 0
    F1-QQQ-SMA200-M         17 trades  dsr=None
    F1-QQQ-VT15-W           28 trades  dsr=None
    F1-SPY-10MSMA-M         13 trades  dsr=None
    F1-SPY-ABS12-M           9 trades  dsr=None
    F1-SPY-SMA200-M         11 trades  dsr=None
    F2-SPYQQQ-12M           14 trades  dsr=None
    F2-SPYQQQ-3M            36 trades  dsr=None
    F2-SPYQQQ-6M            28 trades  dsr=None
    M0084-BAND3-M            9 trades  dsr=0.8716890811543487
    M0084-BAND3-W           10 trades  dsr=0.814838264250398
    M0084-FABER-M           13 trades  dsr=0.8372714490694413
    M0084-MONTHLY           11 trades  dsr=0.8837970886760282
```

So `‹TRADES-HELD-OUT-AFTER›` is **twelve trials**, and "clearing the luck bar = 0" at the 0.50
screen is what makes the §13 sentence in the bullet true as written. **If `clearing the luck bar`
is not 0 on the landed tree, stop and rewrite that bullet** — §13's finding would then be wrong as
written, and saying it survives would be a false claim in a document whose whole value is that it
does not make them. **Also cross-check against `HELD_OUT_BY_THE_TRADES_BAR` in
`engine/tests/test_dev_trades_bar.py` as phase 1 left it: the two must list the same twelve. If
they disagree, phase 1's landed list wins and this bullet follows it.**

**Impact:** the section stops being provisional.

---

### Step 4: Verify the file, then commit

**File:** `docs/plans/2026-10-03-seer-design.md`
**Change:** checks, then one commit by explicit pathspec.

```bash
cd /home/miftah/.worktrees/seer/split-screen-from-bar

# section numbering is continuous and 18 is last
grep -n '^## ' docs/plans/2026-10-03-seer-design.md

# no slot survived
grep -n '‹' docs/plans/2026-10-03-seer-design.md && echo "UNFILLED SLOT -- do not commit"

# the diff is the appended section plus exactly one line above it
git diff --stat -- docs/plans/2026-10-03-seer-design.md
git diff -- docs/plans/2026-10-03-seer-design.md | grep -c '^-[^-]'   # must print 1
git diff -- docs/plans/2026-10-03-seer-design.md | grep '^-[^-]'      # must be line 20 only

git commit -m "docs: the drawdown bar is 25% and the lab's screen is a separate number (design §18)" \
  -- docs/plans/2026-10-03-seer-design.md
```

`git reset --hard`, `git clean`, `git checkout .`, `git restore .`, bare `git stash`, `git add .`
and `git add -A` are **BANNED** in this phase, including inside any subagent dispatched from it —
if you dispatch one, say that sentence verbatim in its prompt. The lab database and `web/data`
belong to Phase 1 and must not appear in this commit; `git status --short` before committing and
confirm nothing of Phase 1's is accidentally in the pathspec (it cannot be, the pathspec is one
file, but check that Phase 1 left nothing uncommitted that this phase might be blamed for).

**Impact:** one commit, revertible on its own.

---

## Verification

**Build:** not applicable — this phase changes one markdown file and no code.

**Lint:**

```bash
cd /home/miftah/.worktrees/seer/split-screen-from-bar/engine && \
  /home/miftah/seer/engine/.venv/bin/ruff check engine
```

Expect clean. CI lints bugs only (E9 and F, minus F401).

**Tests:**

```bash
docker start seer-pg 2>/dev/null || true
cd /home/miftah/.worktrees/seer/split-screen-from-bar/engine && \
  PYTHONPATH=/home/miftah/.worktrees/seer/split-screen-from-bar/engine/src \
  PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  /home/miftah/seer/engine/.venv/bin/python -m pytest -q
```

A docs change cannot move the suite, but run it and **quote the skip count beside the pass count**.
**CORRECTED 2026-10-14:** the baseline in *this worktree* is **4756 passed, 4 skipped** (not the
draft's 4757/3 — `test_universe_rank` skips here because the month-end sweep CSV lives only in the
main checkout), and Phase 1 adds one test, so the number you should see on entering this phase is
**4757 passed, 4 skipped**. Whatever Phase 1 left green must still be green, with the same skip
count. If the suite is red when this phase starts,
it is Phase 1's breakage and this phase does not fix it; report and stop.

`PYTHONPATH` is not optional — without it pytest silently tests the main checkout rather than this
branch.

**Does any test pin the design document's content?** Checked while planning:

```bash
grep -rn 'seer-design' engine/src engine/tests web/lib web/app
```

returns `engine/tests/test_dev_trades_bar.py:51,99` (the string `"docs/plans/2026-10-03-seer-design.md §13"`,
used only in failure messages) and `engine/src/seer_engine/backtest/dev_report.py:1137` (prose).
**No test parses, reads or asserts the contents of the design document**, and nothing names §1,
§11, §17 or §18 as data. So no new test case is needed for the revision series, and this phase adds
no test. `test_dev_trades_bar.py` does re-take §13's measurement against the live bars, but it is
Phase 1's to keep green and it asserts against its own constant list, not against the document.

**Manual check:**
- Render or read `docs/plans/2026-10-03-seer-design.md` from §17 to the end: the new section must
  read as one voice with §11, §13, §16 and §17 — bullets with bolded leads, measurements with
  their dates, no code identifiers outside the final "Where it is implemented" bullet.
- Read §1's five conditions top to bottom. Condition 4 must read 25% and point at §18.

**Exit criteria:**
1. `grep -n '^## '` shows `## 17.` then `## 18.` and nothing after.
2. `git diff` on the file shows the appended section and exactly one removed line — file line 20.
3. No `‹` remains in the file.
4. Every number in §18 is either one of the figures carried in the plan index (399, 257, 188, 73%,
   56.5%, 7.86%, 2009-03-09, 20,000,000 IDR, 5,000,000 IDR), one of §17's re-read survivorship
   counts (49, 7, 14%, 11, 28, 39% — all verified), or a figure measured by Step 3 and quoted with
   how it was measured: **26 → 67 trials, 16 → 32 methods (eligibility, the headline), 93 → 319
   trials (browsable, labelled as such), 30 of 32 at a 0.25 screen, and five → twelve for §13's
   trades-bar set.**
4b. **§18 contains no "do not run `lab reevaluate`" caveat.** Phase 1 Step 5b removed the hazard;
   publishing the warning would make the permanent record wrong on the other side.
5. `ruff` clean; pytest green with the skip count quoted beside the pass count.
6. `lab/lab.sqlite` is byte-identical to how Phase 1 left it — this phase never opens it except
   read-only, and `md5sum` is checked on both sides of Step 3.

---

## Handoffs

**To Phase 1 — `engine/tests/test_dev_trades_bar.py` goes red, and its message points here.
RECONCILED 2026-10-14.** This was the one real cross-phase collision in the set, and the two
planners measured different numbers. Settled: it is the **screen** moving 0.20 → 0.50 that grows
the set, not the money bar moving to 0.25, because `store.owner_failures`'s drawdown comparison
reads `tuning.DEV_MAX_DRAWDOWN` after phase 1. The set grows **from five trials to twelve**, and the
seven that join are `F1-QQQ-SMA200-M`, `F1-QQQ-VT15-W`, `F1-SPY-ABS12-M`, `F2-SPYQQQ-12M`,
`F2-SPYQQQ-3M`, `F2-SPYQQQ-6M` and `M0084-BAND3-M`. (This phase's draft said eight and named three;
that was the count at a 0.25 screen, which does not land. Phase 1's twelve is correct and both plans
now say twelve.) The test's failure message instructs the reader to "update both this list and the
one in `docs/plans/2026-10-03-seer-design.md §13`".

- The **constant list** (`HELD_OUT_BY_THE_TRADES_BAR`, `test_dev_trades_bar.py:66`) and its
  comment are **Phase 1's** to re-express, like the other ~40 tests it owns.
- **§13 itself is not edited by anyone.** It is a dated record, and the 2026-10-07 and 2026-10-12
  entries inside it are what §13's own convention produced. The re-measurement lives in §18's
  last-but-one bullet instead, which this phase writes. If Phase 1 has already edited §13, this
  phase must not duplicate the statement — report the overlap to the reconciler rather than
  writing both.
- §13's load-bearing claim survives: all **twelve** sit below the luck bar or carry no luck score
  (`clearing the luck bar = 0`, measured), so dropping the trades bar would still change zero
  verdicts. Phase 1 keeps that assertion and this phase states it in §18.

**Left deliberately undone, for a later session, not for Phase 1:**
- §17's clause 1 ("a variant whose fuller-history drawdown is at or above the bar is not
  promotable") is still **not enforced in code** — §17 says so itself, and the fuller-history
  store is not on this machine. Raising the bar to 25% shrinks the affected set from 11 variants
  to 7 but does not close the gap. §18 records the new count and nothing more; mechanising the
  check remains unrun.
- The §1 preamble's `(fixed; moved only by a dated owner revision — see §11)` pointer is left on
  §11 on purpose (Step 1). A future session that revises the clause itself, rather than a
  condition under it, should move that pointer.
- `docs/plans/SPLIT_SCREEN_FROM_BAR_PLAN.md` is the index and belongs to the coordinator, not to
  this phase. Do not tick it here.

---

## Rollback

```bash
cd /home/miftah/.worktrees/seer/split-screen-from-bar
git revert <sha of this phase's commit>
```

One commit, one file, prose only. It reverts cleanly and in isolation: it has no code dependency
on Phase 1's commits, so reverting it does not require reverting them (the reverse is not true —
reverting Phase 1 without reverting this would leave §1 and §18 claiming a 25% bar the code no
longer sets, which is a stale document rather than a broken build, but should be done together
anyway). No database state, no derived artefact, nothing to unwind. **Never** `git reset --hard`.
