> Adopted from `/home/miftah/seer/.workflows/orchestration/split-screen-from-bar/PLAN.md` phase 1. Source: `.workflows/plan/split-screen-from-bar/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: Two constants, and everything that reads them

**Plan set:** `SPLIT_SCREEN_FROM_BAR_PLAN.md`
**Analysis:** `docs/analyzer/20261014-095218-B7QD_code_analyzer.md`
**Satisfies:** R1 (raise the real-money bar 20% → 25%), R2 (split the dev screen off that bar), R4 (engine and web agree)
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/backtest`, `engine/src/seer_engine/lab`, `web`, `lab/`

---

## Goal

After this phase the lab holds **two** drawdown numbers instead of one. `MAX_DRAWDOWN` is
0.25 and is the owner's real-money bar: §1 go-live condition 4, the P3/P3b/P6a backtest gates,
the hard gate's survivorship rule, the leaderboard. `DEV_MAX_DRAWDOWN` is 0.50 and is the dev
screen: the only thing it decides is whether a recorded trial is worth another hour of study.
A method can now be found, measured and understood while still being refused real money — and
one new test pins exactly that.

---

## READ THIS FIRST — three findings that change the plan index

I made the change on this worktree, ran the suite, measured, and restored every file
(`git diff` clean, `lab/lab.sqlite` still `2c8c9669ad76642741342f8272a629e125c795f9dd0ab09300f44721dc580086`).
Three things the index and the analysis got wrong. **The reconciler must read this section.**

### F1 — the analysis swapped two function names. The line numbers are right.

The index says "the screen … `store.py:1463`, inside `_blocking`" and "`owner_failures`
(`:1801`) … keeps reading the real-money bar". The code says the opposite:

| line | function (measured) | what it actually decides |
|---|---|---|
| `store.py:1411` def, docstring `:1423`, comparison **`:1463`** | **`owner_failures`** | **THE SCREEN.** `verdict()` calls it and sets `eligible = not failed`. This is dev-eligibility. |
| `store.py:1769` def, comparison **`:1801-1802`** | **`_blocking`** | **ALSO THE SCREEN**, written a second time on purpose, guarding the `rejected → dev-eligible` write edge in `reevaluate_method`. |

**Neither is the real-money bar.** `store.py` contains no go-live gate at all. The real-money
readers are `metrics.checklist` (§1 condition 4), `tuning.qualifies`/`gate`,
`walkforward.gate_p3b`, `b_walkforward.gate_p6a`, `hardgate.py:1569` (D16) and the
`snapshot` gate block at `:2894`.

**Resolution:** the phase scope is honoured **by line number**, which is unambiguous and
matches the described role. `owner_failures:1463` is the screen and moves.

### F2 — one call site does not build. Four do. (Index invariant 2 must be amended.)

Index invariant 2 demands exactly one reader of `DEV_MAX_DRAWDOWN` in `lab/`. Measured, that
produces three defects:

1. **`lab reevaluate` crashes on four real methods.** With `owner_failures` at 0.50 and
   `_blocking` at 0.25, 7 recorded trials across **M0050, M0058, M0082, M0085** (all
   `rejected`) read derived-eligible and are then refused by `_blocking`, which raises
   `LabError` by design ("a contradiction inside this module"). `lab reevaluate` with no
   argument sweeps every rejected method, so a shipped command dies. Measured list:
   `M0050-ON` (0.3048), `M0058-ILL20-T` (0.2637), `M0058-ILL30-T` (0.2577),
   `M0082-X-N40` (0.2704), `M0085-HOST-W` (0.2574), `M0085-DECL-W` (0.2600),
   `M0085-EX-W` (0.2546).
2. **The failure label would lie.** `dev.FAILURE_LABELS[1]` is
   `f"max DD <= {tuning.MAX_DRAWDOWN:.0%}"`, and `owner_failures` appends *that string* when
   the screen comparison fails. A trial refused at 0.50 would be labelled `max DD <= 25%`.
   The comment above that line says the label is "interpolated from the bar it names so the
   two can never disagree".
3. **New trials would be born inconsistent.** `dev.make_row` (`dev.py:440`) decides
   `DevRow.eligible` for a *fresh* run. Left at 0.25, a new trial at 0.30 records
   `eligible = 0, failed = "max DD <= 25%"` while `store.verdict` immediately reads it as
   eligible.

**Resolution:** `DEV_MAX_DRAWDOWN` has **four** call sites, all of them the one screen:
`dev.py:96` (its label), `dev.py:440` (the screen for a new row), `store.py:1463`
(the screen for a recorded row), `store.py:1801-1802` (the screen's second, independent no).
The grep at the end proves **two** uses in `lab/` and **two** in `backtest/`, plus the
definition and the re-export. Index invariant 2 needs this amendment.

### F3 — exit criterion 2 as written is impossible, and the measured counts are wrong.

Index exit criterion 2 asks for "a trial at 30% drawdown … dev-eligible **and** still fails
`store.owner_failures`". `owner_failures` *is* what makes a trial dev-eligible
(`eligible = not owner_failures(...)` plus the luck test), so no trial can do both. The test
that actually pins the split asserts the trial is dev-eligible **and** still fails the
real-money bar — `metrics.checklist`'s go-live item 4 and `hardgate`'s D16 bar. Step 10 writes it.

**And the counts.** Analysis M3 said 93 trials / 30 methods → 319 / 64. Measured read-only on
the committed `lab.sqlite` (399 dev rows, hash unchanged, `store.test_looks` = 4 before and after):

| | drawdown filter alone | **full dev-eligible verdict** (`store.verdict`, all five owner conditions + the luck test at the live gate N=81/`methods`) |
|---|---|---|
| screen 0.20 (today) | 93 trials / **37** methods | **26 trials / 16 methods** |
| screen 0.25 | 196 trials / 61 methods | 60 trials / 30 methods |
| screen 0.40 | 303 trials / 75 methods | 67 trials / 32 methods |
| **screen 0.50 (this phase)** | **319 trials / 76 methods** | **67 trials / 32 methods** |

M3's "distinct methods" column (30 → 64) was wrong in both cells; and M3 never reported the
*real* eligibility number, which is far smaller because the DSR, PF and trades conditions bind
too. **Report these honestly to phase 2** — including the uncomfortable part: 0.25 alone
already reaches 30 of the 32 methods, and 0.40 → 0.50 adds nothing at all. The screen's value
still earns its keep on the number a human actually browses (93 → 319 trials), which is what
"worth another hour of study" means, so **D1 stands at 0.50** and the two constants stay split
(index invariant 1). Do not re-litigate it; report it.

**RECONCILED 2026-10-14.** Every cell of this table was re-derived independently by the reconciler,
read-only against the committed `lab/lab.sqlite` (md5 `00f7ebec1b3134e67e3b087226d308b7`, unchanged
before and after; `store.gate` = `methods` N = 81; `store.test_looks` = 4). It matches exactly.
**Phase 2 quotes the FULL-VERDICT pair as its headline — 26 trials / 16 methods → 67 / 32 (index
Decision D8) — and may print the browsable pair (93 / 37 → 319 / 76) only beside it and clearly
labelled as "clears the drawdown condition", never as eligibility.**

---

## Interface Contract

**Creates:**
- `seer_engine.backtest.metrics.DEV_MAX_DRAWDOWN` = `0.50` (`backtest/metrics.py`, new line after
  `MAX_DRAWDOWN`'s docstring, before `EXIT_REASONS`)
- `seer_engine.backtest.tuning.DEV_MAX_DRAWDOWN` (re-export, `backtest/tuning.py:~46`)
- `tests/test_lab_gate_policy.py::test_a_thirty_percent_fall_is_worth_studying_and_is_not_worth_money`
- `tests/test_lab_gate_policy.py::BAR_2026_10_07` = `0.20` (module literal pinning history)

**Value changes (no signature changes anywhere):**
- `metrics.MAX_DRAWDOWN` `0.20` → `0.25` (`backtest/metrics.py:55`). Everything downstream
  follows: `MAX_DRAWDOWN_LABEL` becomes `"Max drawdown ≤ 25%"`, `checklist` item 4,
  `gate_checks`, `tuning._GATE_NAMES`, `tuning.qualifies`, `tuning.gate`,
  `walkforward.gate_p3b`, `b_walkforward.gate_p6a`, `hardgate` D16, `snapshot` `gate.maxDrawdown`.
- `web/lib/golive.ts:21` `MAX_DRAWDOWN` `0.2` → `0.25`; `MAX_DRAWDOWN_LABEL` becomes
  `"Max drawdown ≤ 25%"`.
- `web/data/lab.json` `gate.maxDrawdown` `0.2` → `0.25` (regenerated by `lab stage`).

**Reader changes — `tuning.MAX_DRAWDOWN` → `tuning.DEV_MAX_DRAWDOWN`, exactly four:**
- `backtest/dev.py:96` — `FAILURE_LABELS[1]`, which becomes `"max DD <= 50%"`
- `backtest/dev.py:440` — `make_row`'s drawdown condition
- `lab/store.py:1463` — `owner_failures`
- `lab/store.py:1801-1802` — `_blocking`

**One further reader, not a decision site — `lab/store.py:1904`.** `reevaluate_method` interpolates
the drawdown number into the `analysis` prose it writes through `append_analysis`, describing the
bar it just re-judged against. The re-judgement is `owner_failures`/`_blocking`, i.e. the **screen**,
so after this phase that sentence must name the screen or it writes a false statement into text that
can only ever be appended to. **ADDED BY RECONCILIATION — Step 5b fixes it inside this phase.** It
is not a fifth decision (index invariant 2's four stand); it is the sentence that must agree with
them.

**Deletes:** nothing. No symbol, no test, no recorded row.
**Renames:** nothing.

**Requires (from earlier phases):** none. This phase is first.

**Leaves alone (owned by others, or deliberately):**
- `docs/plans/2026-10-03-seer-design.md` — **Phase 2**. Including §13, which
  `tests/test_dev_trades_bar.py` tells you to update alongside its constant (see Handoffs).
- `store.py:2894` `snapshot` gate — stays `tuning.MAX_DRAWDOWN`. This is what `golive.test.ts`
  pins the TS constant to, and it is R4.
- `hardgate.py:1569` (D16) — stays the real-money bar (Decision D3). It gets looser with the
  owner's appetite, which is correct.
- `metrics.checklist` / `MAX_DRAWDOWN_LABEL`, `npolicy`, `web/lib/cadence.ts`,
  `engine/tests/test_sean_mirrors.py`, every `lab/methods/*` file, every recorded row.

---

## Files

| File | Action | What changes | Line |
|---|---|---|---|
| `engine/src/seer_engine/backtest/metrics.py` | modify | `MAX_DRAWDOWN` → 0.25 + docstring; new `DEV_MAX_DRAWDOWN` | `:55-66` |
| `engine/src/seer_engine/backtest/tuning.py` | modify | re-export `DEV_MAX_DRAWDOWN` beside `MAX_DRAWDOWN` | `:38-46` |
| `engine/src/seer_engine/backtest/dev.py` | modify | `FAILURE_LABELS[1]` and `make_row` read the screen; module docstring | `:23`, `:86-100`, `:440` |
| `engine/src/seer_engine/lab/store.py` | modify | `owner_failures` docstring + comparison; `_blocking` comparison; `reevaluate_method`'s analysis prose | `:1423`, `:1463`, `:1801-1802`, `:1904` |
| `engine/tests/test_lab_gate_policy.py` | modify | pin history to a literal; monkeypatch the screen in 9 tests; **add** the split test | many |
| `engine/tests/test_lab_gate_wording.py` | modify | the prose matcher's live bar | `:284` |
| `engine/tests/test_lab_hardgate.py` | modify | D16 fixture drawdown above the new bar | `:1239-1244` |
| `engine/tests/test_lab_luck.py` | modify | expected label/verdict | `:227` |
| `engine/tests/test_lab_status.py` | modify | fixture drawdown | `:159` |
| `engine/tests/test_lab_prereg.py` | modify | fixture drawdowns | `:247`, `:357` |
| `engine/tests/test_lab_store.py` | modify | fixture drawdown | `:102` |
| `engine/tests/test_lab_test_window.py` | modify | fixture drawdown | `:339` |
| `engine/tests/test_lab_snapshot.py` | — | goes green once `lab stage` runs | — |
| `engine/tests/test_dev_trades_bar.py` | modify | re-measured `HELD_OUT_BY_THE_TRADES_BAR` | `:57-74` |
| `engine/tests/test_backtest_dev.py` | modify | 6 tests: labels/thresholds now the screen | `:200-210`, `:501`, `:518-526`, `:564`, `:783-795` |
| `engine/tests/test_backtest_metrics.py` | modify | label string `20%` → `25%` | `:129` |
| `engine/tests/test_backtest_tuning.py` | modify | 5 tests: label and sentence strings | `:121`, `:159`, `:184` |
| `engine/tests/test_backtest_walkforward.py` | modify | 3 tests: label and sentence strings | — |
| `engine/tests/test_backtest_b_walkforward.py` | modify | 3 tests: label and sentence strings | — |
| `engine/tests/test_backtest_report.py` | modify | 2 tests: checklist prose | — |
| `engine/tests/test_backtest_dev_report.py` | modify | 2 tests: frontier svg, finalist prose | — |
| `engine/tests/test_backtest_wf_report.py` | modify | 1 test: method list prose | — |
| `web/lib/golive.ts` | modify | `MAX_DRAWDOWN` → `0.25`, docstring | `:21`, `:1-18` |
| `web/lib/golive.test.ts` | modify | label assertion `20%` → `25%` | `:14` |
| `web/lib/sera/fixture.ts` | modify (if `npm test` demands) | `GATE.maxDrawdown` → `0.25` | `:5` |
| `web/data/lab.json` | regenerate | `lab stage` | — |
| `lab/lab.sqlite` | regenerate | `lab stage` (migration only; no row written) | — |

---

## Implementation Steps

### Step 1: `MAX_DRAWDOWN` → 0.25, and the new `DEV_MAX_DRAWDOWN`

**File:** `engine/src/seer_engine/backtest/metrics.py:55-66`
**Change:** raise the real-money bar, record the second dated move in its docstring, and add the
screen beside it with the measurement that justifies two numbers.

**Code — replace lines 55 through 66 (`MAX_DRAWDOWN = 0.20` through the closing `"""`, up to but
not including `EXIT_REASONS`) with:**

```python
MAX_DRAWDOWN = 0.25
"""Go-live condition #4 (design §1): the deepest peak-to-trough fall a strategy may show
**before the owner will put real money behind it**.

The single definition in Python. ``tuning.MAX_DRAWDOWN`` re-exports this name, so every caller
that reads the real-money threshold -- ``checklist`` below, ``tuning.qualifies``, ``tuning.gate``,
``walkforward.gate_p3b``, ``b_walkforward.gate_p6a``, ``lab.hardgate``'s D16 survivorship rule
and ``lab.store.snapshot`` -- resolves to this one float. It lives here, not in ``tuning``, only
because ``tuning`` imports ``metrics`` and the dependency cannot run the other way.

0.15 until 2026-10-07, when the owner raised it to 0.20 on stated risk appetite (design §11);
0.20 until 2026-10-14, when he raised it again to 0.25 (design §18). ``web/lib/golive.ts``
carries the same number for the leaderboard and is pinned to it through ``data/lab.json``'s gate
by ``web/lib/golive.test.ts``.

**This is no longer the lab's dev screen.** Until 2026-10-14 this one float also decided what the
lab would even look at. ``DEV_MAX_DRAWDOWN`` below is that job now; see its docstring for why the
two were separated.
"""

DEV_MAX_DRAWDOWN = 0.50
"""The lab's **dev screen**: the deepest fall a recorded dev trial may show and still be worth
another hour of study. Not a statement about money.

``tuning.DEV_MAX_DRAWDOWN`` re-exports it, and exactly four call sites read it -- all of them one
decision written in four places: ``dev.FAILURE_LABELS[1]`` (the label, interpolated from this bar
so the two can never disagree), ``dev.make_row`` (the screen applied to a fresh run),
``lab.store.owner_failures`` (the screen applied to a recorded row) and ``lab.store._blocking``
(the same screen written a second time, on purpose, to guard the ``rejected -> dev-eligible``
write edge).

**Why there are now two numbers.** They answer different questions. The bar asks *could the owner
hold this through its worst month*; the screen asks *is this worth another hour of study*. One
float answered both until 2026-10-14, and the second job was the binding constraint on the whole
research programme. Measured on the 399 recorded dev trials: **257 beat total-return SPY, and the
20% bar rejected 188 of them -- 73%.** Nothing else in the lab rejects at that rate. Meanwhile
**SPY itself fell 56.5%** over the dev window (trough 2009-03-09) while compounding at 7.86%/yr,
so the lab was requiring its strategies to fall less than a third as far as the benchmark they
had to beat.

**Why 0.50 and not SPY's own 0.5665.** A book that falls by half offers no risk control that
buy-and-hold does not already give away free, so the screen is drawn just inside what doing
nothing costs. Measured against the committed lab, the screen admits 319 of 399 trials for a
human to browse where 0.20 admitted 93. Under the *full* dev verdict -- every owner condition
plus the deflated-Sharpe luck test at the live N -- it admits 67 trials over 32 methods against
26 over 16. (Most of that is already reached at 0.25; the screen is loose because browsing is
cheap, not because the extra methods are free. Design §18 carries the table.)

**What a looser screen does not do.** It cannot move N or any DSR: ``lab.npolicy.dev_method_count``
counts distinct methods with *any* dev trial, eligible or not. And it cannot reach the test
window: ``lab.runner.preflight_test`` refuses any method that is not ``promoted``, and promotion
is judged at ``MAX_DRAWDOWN``. The screen widens what is studied; it widens nothing that is spent.
"""
```

**Impact:** `MAX_DRAWDOWN_LABEL` (`:476`) becomes `"Max drawdown ≤ 25%"`, which propagates to
`checklist`, `gate_checks`, `tuning._GATE_NAMES` and every verdict sentence in the backtest
reports. ~21 backtest tests move on this alone.

---

### Step 2: re-export the screen through `tuning`

**File:** `engine/src/seer_engine/backtest/tuning.py:38-46`
**Change:** add `DEV_MAX_DRAWDOWN` beside `MAX_DRAWDOWN`, in the same comment style, and sharpen
`MAX_DRAWDOWN`'s comment so the two cannot be confused by a reader.

**Code — replace the block from `# go-live #4, re-exported from ``metrics``…` through
`MAX_DRAWDOWN = _metrics.MAX_DRAWDOWN` with:**

```python
# go-live #4 -- the REAL-MONEY bar, re-exported from ``metrics`` so ``checklist`` and this module
# cannot drift apart. Every reader of the real-money threshold (lab.store.snapshot, dev_report,
# qualifies, gate, walkforward.gate_p3b, b_walkforward.gate_p6a, lab.hardgate's D16 rule) goes
# through this name; the value lives in ``metrics.MAX_DRAWDOWN``. Raised 0.15 -> 0.20 by the owner
# on 2026-10-07 (design §11) and 0.20 -> 0.25 on 2026-10-14 (design §18).
MAX_DRAWDOWN = _metrics.MAX_DRAWDOWN
# The lab's DEV SCREEN, re-exported for the same reason. NOT the bar above: this one decides what
# the lab studies, not what the owner funds, and it is deliberately far looser. Split off from
# MAX_DRAWDOWN by the owner on 2026-10-14 (design §18); ``metrics.DEV_MAX_DRAWDOWN`` carries the
# measurement. Exactly four call sites read it -- dev.FAILURE_LABELS, dev.make_row,
# lab.store.owner_failures and lab.store._blocking -- and they are one decision written four
# times. Anything that collapses this back into MAX_DRAWDOWN undoes the split.
DEV_MAX_DRAWDOWN = _metrics.DEV_MAX_DRAWDOWN
```

**Impact:** none on its own. `_GATE_NAMES` at `:48` keeps reading `MAX_DRAWDOWN_LABEL`, which is
correct — the P3 gate is a real-money gate.

---

### Step 3: `dev.FAILURE_LABELS` and `dev.make_row` read the screen

**File:** `engine/src/seer_engine/backtest/dev.py:86-100` and `:440`
**Change:** the five D8 labels and `make_row`'s comparison are the dev screen, so both move.
This is **F2 defects 2 and 3**; without it the label names a bar the comparison does not use and
every fresh trial is born contradicting `store.verdict`.

**Code — replace `FAILURE_LABELS` (`:86-100`) with:**

```python
FAILURE_LABELS: tuple[str, ...] = (
    "beats SPY TR",
    # The DEV SCREEN's label, interpolated from the bar it names so the two can never disagree.
    # This is ``tuning.DEV_MAX_DRAWDOWN``, not ``tuning.MAX_DRAWDOWN``: these five labels are the
    # lab's D8 dev-eligibility conditions -- what is worth studying -- and on 2026-10-14 the owner
    # split that screen off from the real-money bar (design §18). ``metrics.DEV_MAX_DRAWDOWN``
    # carries the argument.
    #
    # The number has moved three times and the PREFIX is the stable part. ``trials.failed`` is
    # append-only, so rows judged before 2026-10-07 keep "max DD <= 15%" for ever, rows judged
    # between then and 2026-10-14 keep "max DD <= 20%", and rows judged from now on carry
    # "max DD <= 50%". All three are misses, and every reader -- store.owner_failures and
    # store._blocking in Python, DRAWDOWN_FAILURE_PREFIX in web/lib/sera/derive.ts -- matches on
    # "max DD <= ", never on the whole string. See tests/test_lab_gate_wording.py.
    f"max DD <= {tuning.DEV_MAX_DRAWDOWN:.0%}",
    "PF >= 1.3",
    ">= 100 trades",
    "owner inputs",
)
```

**Code — at `:440`, inside `make_row`'s `passed` tuple, replace the one line:**

```python
        m.max_drawdown is not None and m.max_drawdown <= tuning.DEV_MAX_DRAWDOWN,
```

**Code — the module docstring, `:22-25`, replace the D8 bullet with:**

```python
- **D8.** ``make_row`` applies the dev screen (beating total-return SPY,
  ``tuning.DEV_MAX_DRAWDOWN``, ``tuning.MIN_PROFIT_FACTOR``, 100 closed trades) and the
  owner-input rule; ``finalists`` ranks the eligible rows by MAR and keeps one per family, at
  most three. The drawdown condition is the **screen**, not §1's real-money bar: the two were
  separated on 2026-10-14 (design §18) and ``tuning.MAX_DRAWDOWN`` is the other one.
```

**Impact:** `FAILURE_LABELS[1]` becomes `"max DD <= 50%"`. Measured: 6 tests in
`test_backtest_dev.py` move (`test_constants`, `test_every_failure_in_order`,
`test_thresholds_come_from_tuning`, `test_eligibility_boundaries[kw2]` and `[kw13]`,
`test_finalists_d8`, `test_the_drawdown_label_follows_the_bar_and_keeps_its_prefix`).

---

### Step 4: `store.owner_failures` reads the screen

**File:** `engine/src/seer_engine/lab/store.py:1423` and `:1463`
**Change:** the docstring says plainly this is the screen and not the bar, and the comparison
follows.

**Code — replace `:1423` (one line inside the four-item list) with:**

```
    - ``max DD``        ``max_drawdown <= tuning.DEV_MAX_DRAWDOWN`` -- **the dev SCREEN, not the
                        real-money bar.** 0.15 until 2026-10-07, 0.20 until 2026-10-14, 0.50
                        since (design §18). This function answers "is this trial worth another
                        hour of study", which is why it reads the loose number. The owner's
                        real-money bar is ``tuning.MAX_DRAWDOWN`` (0.25) and nothing in this
                        module reads it as a gate: ``metrics.checklist`` is §1 condition 4,
                        ``lab.hardgate``'s D16 rule is the survivorship refusal, and
                        ``snapshot`` publishes it. ``_blocking`` below repeats *this* comparison,
                        against this same screen, because it guards the same edge.
```

**Code — replace `:1463`:**

```python
    if dd is None or float(dd) > tuning.DEV_MAX_DRAWDOWN:
```

**Impact:** this is the change. 26 recorded dev trials over 16 methods were dev-eligible; 67
over 32 now are. No row is written — `eligible` and `failed` are derived at read time.

---

### Step 5: `store._blocking` reads the same screen

**File:** `engine/src/seer_engine/lab/store.py:1801-1802`
**Change:** `_blocking` is the same screen written a second time on purpose. If it keeps the
real-money number, `reevaluate_method` raises `LabError` on M0050, M0058, M0082 and M0085
(**F2 defect 1**, measured), and `lab reevaluate` dies.

**Code — replace lines 1801-1802:**

```python
    if dd is None or float(dd) > tuning.DEV_MAX_DRAWDOWN:
        out.append(f"max drawdown {dd!r} is outside the {tuning.DEV_MAX_DRAWDOWN:.0%} screen")
```

**Code — append to `_blocking`'s docstring, after the "Phrased as sentences…" paragraph:**

```
    **It reads the dev SCREEN**, ``tuning.DEV_MAX_DRAWDOWN``, because the edge it guards is
    ``rejected -> dev-eligible`` -- a research decision, not a funding one. It must read the same
    number ``owner_failures`` reads or this guard fires on its own module's verdict: measured on
    2026-10-14, holding this at ``MAX_DRAWDOWN`` while the screen moved would have raised
    ``LabError`` for seven recorded trials across M0050, M0058, M0082 and M0085, all of them
    ``rejected``, and ``lab reevaluate`` with no argument sweeps exactly those. The point of the
    repetition is that the comparison is written twice in two places, not that it is written
    against two different bars.
```

**Impact:** breaks `test_lab_gate_policy.py::test_reevaluate_refuses_outright_if_a_verdict_contradicts_the_record`,
whose fixture drawdown of 0.245 no longer blocks. Step 8 re-expresses it.

---

### Step 5b: `reevaluate_method`'s analysis prose must name the number it judged by

**File:** `engine/src/seer_engine/lab/store.py:1904`
**Change:** one interpolation and two words. **Added by reconciliation, 2026-10-14.** This was
originally parked as a follow-up; it is not safe to park. `reevaluate_method` builds its
`# Re-evaluation` text and hands it to `append_analysis`, and `methods.analysis` can only ever be
appended to — a wrong sentence written there is permanent. After Steps 4 and 5 the re-judgement it
describes is made against `tuning.DEV_MAX_DRAWDOWN` (0.50) while this line would still print
`tuning.MAX_DRAWDOWN` (0.25). The first `lab reevaluate` after this phase would therefore record,
irreversibly, that it unblocked a method "against a max drawdown bar of 25%" when it did no such
thing. One line removes the hazard; a comment or a guard does not, because the command is shipped
and takes no argument.

**Code — replace the `REEVALUATION_MARKER` f-string's second line (`:1903-1905`):**

```python
        f"{REEVALUATION_MARKER}`{g.policy}` N policy at N = {g.n}, against `{DSR_LABEL}` and "
        f"a max drawdown screen of {tuning.DEV_MAX_DRAWDOWN:.0%} (the luck bar is the owner's "
        f"risk appetite, set 2026-10-07, LAB_LUCK_GATE_PLAN.md Decisions D1 and D6; the drawdown "
        f"screen was split off the owner's real-money bar on 2026-10-14, design §18).",
```

**Why "screen" and not "bar".** The sentence describes what `owner_failures` and `_blocking` just
compared against, and both read the screen from Step 4 and Step 5. Naming it "bar" here would make
the permanent record claim a re-judgement that never happened.

**Impact:** `lab reevaluate` becomes safe to run again. Any test asserting this prose moves with it
— grep `Re-evaluation` and `a max drawdown bar of` under `engine/tests` before and after, and
re-express rather than delete (invariant 9). Measured at plan time the mid-change run showed no
test pinning this string beyond `test_lab_gate_policy.py`'s reevaluate cases, which Step 8 already
touches; confirm on your tree.

**This retires Handoff 3.** Do not also leave the "do not run `lab reevaluate`" warning standing:
after this step there is nothing to warn about.

---

### Step 6: the web constant and its label

**File:** `web/lib/golive.ts:1-21` and `:41`
**Change:** mirror `metrics.MAX_DRAWDOWN`. `MAX_DRAWDOWN_LABEL` is built from it and follows.

**Code — replace line 21:**

```typescript
export const MAX_DRAWDOWN = 0.25;
```

**Code — replace the final paragraph of the file's leading block comment (the line
`* Raised 0.15 -> 0.2 by the owner on 2026-10-07; design §11 records the revision.`) with:**

```
 * Raised 0.15 -> 0.2 by the owner on 2026-10-07 (design §11) and 0.2 -> 0.25 on 2026-10-14
 * (design §18). This is the REAL-MONEY bar only. On 2026-10-14 the engine split the lab's
 * dev-eligibility screen off it into `backtest.metrics.DEV_MAX_DRAWDOWN` (0.50), which decides
 * what the lab studies rather than what the owner funds. The screen has no mirror here and needs
 * none: the web reads a trial's verdict out of `data/lab.json`'s `failedNow` strings, matching
 * the stable `max DD <= ` prefix in `lib/sera/derive.ts`, never the number.
```

**Impact:** `MAX_DRAWDOWN_LABEL` becomes `Max drawdown ≤ 25%`. `golive.test.ts:10` stays red
until Step 12 regenerates `lab.json`.

---

### Step 7: the web test

**File:** `web/lib/golive.test.ts:14`
**Change:** the label the engine now builds.

**Code — replace line 14 (keep the real `≤`, U+2264):**

```typescript
    expect(MAX_DRAWDOWN_LABEL).toBe('Max drawdown ≤ 25%');
```

**Impact:** with Step 12 done, `npm test` is green. If `web/lib/sera/fixture.ts:5`
(`GATE.maxDrawdown: 0.2`) makes any other vitest red, raise it to `0.25` — it is a unit-test
builder, not a mirror.

---

### Step 8: re-express `test_lab_gate_policy.py` — the historical claims (9 tests)

**File:** `engine/tests/test_lab_gate_policy.py`
**Change:** these tests are about **2026-10-07**, the day the drawdown bar went 15% → 20%. They
currently express "the bar on that day" as `tuning.MAX_DRAWDOWN`, which stops being true the next
time the constant moves. Pin the historical number as a literal, and where a test calls
`store.owner_failures`/`store.verdict` to re-enact that day, monkeypatch the **screen** back to it.
**Nothing is deleted and every historical claim stays asserted.**

**Code — add near the top of the module, beside the other module constants:**

```python
#: The drawdown bar the owner set on 2026-10-07, and the bar every historical claim in this
#: module is about. Pinned as a literal and NOT read from ``tuning``: on 2026-10-14 the owner
#: raised the real-money bar to 0.25 and split the lab's dev screen off at
#: ``tuning.DEV_MAX_DRAWDOWN`` = 0.50 (design §18). The facts below -- that 15% -> 20% unblocked
#: exactly M0022-W-TV14, M0022-W-TV16 and M0020-W-NOSTOP, and that M0007-N20-RAW,
#: M0019-RAW20-S25 and M0001-TV10 stayed out, each for its own reason -- are facts about that
#: day. A test about history that reads a live constant stops being about history the moment the
#: constant moves, and the coverage quietly evaporates instead of going red.
BAR_2026_10_07 = 0.20


@pytest.fixture()
def screen_at_2026_10_07(monkeypatch):
    """Judge as the lab judged on 2026-10-07: the dev screen back at that day's 20%.

    ``store.owner_failures`` and ``store._blocking`` read ``tuning.DEV_MAX_DRAWDOWN``. Setting it
    to ``BAR_2026_10_07`` re-enacts the day without touching a recorded row and without asserting
    anything about today's screen -- which the tests under "the split" assert instead.
    """
    from seer_engine.backtest import tuning

    monkeypatch.setattr(tuning, "DEV_MAX_DRAWDOWN", BAR_2026_10_07)
    return BAR_2026_10_07
```

Then, test by test (measured failures, `--tb=line`):

| test | line | measured failure | fix |
|---|---|---|---|
| `test_owner_failures_rederives_the_four_thresholds_and_carries_owner_inputs` | `:227` | `phase 8 sets the drawdown bar this phase reads / assert 0.25 == 0.2` | take `screen_at_2026_10_07`; change the premise line to `assert tuning.DEV_MAX_DRAWDOWN == BAR_2026_10_07 == 0.20, "the dev screen as it stood on 2026-10-07, which is what this test is about"`; change `:233` to `assert drawdown == f"max DD <= {tuning.DEV_MAX_DRAWDOWN:.0%}"` **and** keep the inequality against the recorded string. Note `drawdown = dev.FAILURE_LABELS[1]` is built at import time, so bind it inside the test as `f"max DD <= {tuning.DEV_MAX_DRAWDOWN:.0%}"` rather than from the tuple. |
| `test_verdict_failed_is_a_tuple_of_labels_in_the_recorded_order` | `:308` | `assert ('DSR >= 0.90',) == ('max DD <= 25%', 'DSR >= 0.90')` | the point is tuple **shape**, not the bar. Raise the fixture drawdown `0.245` → `0.55` (outside today's screen) at `:299`, and the ballast `0.30` → `0.60`. Update the docstring's "24.5% … today's 20% bar" to "55% … today's 50% screen". |
| `test_verdict_rederives_the_luck_label_and_the_four_thresholds` | `:438` | `'max DD <= 25%' in ()` — B now clears | raise `M0001-B`'s `max_drawdown=0.245` → `0.55` at `:430`; update the trailing comment. |
| `test_an_owner_condition_is_never_re_decided_by_the_n_policy` | `:438` area | `assert dev.FAILURE_LABELS[1] in v.failed` | raise the trial's `max_drawdown=0.245` → `0.55` and the ballast `0.30` → `0.60`. |
| `test_best_dev_eligible_keeps_its_contract_on_the_derived_verdict` | `:466` | `'M0001-C' == 'M0001-A'` — C is no longer excluded | raise `M0001-C`'s `max_drawdown=0.245` → `0.55`; update the `# C is kept out by a 24.5% drawdown` comment to 55%. |
| `test_reevaluate_refuses_outright_if_a_verdict_contradicts_the_record` | `:592` | `DID NOT RAISE LabError` | raise `M0003-A`'s `max_drawdown=0.245` → `0.55` and the docstring's "24.5% is outside today's 20% bar" to "55% is outside today's 50% screen". **Keep this test** — it is the guard Step 5 depends on. |
| `test_the_two_moved_bars_unblock_exactly_m0022_and_m0020` | `:799` | `assert (0.9 == 0.9 and 0.25 == 0.2)` | take `screen_at_2026_10_07`; replace the premise with `assert store.DSR_MIN == 0.90 and tuning.DEV_MAX_DRAWDOWN == BAR_2026_10_07`. The rest of the test is unchanged and still asserts exactly three candidates clear. |
| `test_the_three_near_misses_that_still_do_not_qualify` | `:866`, `:990` | `0.2066 > 0.25`; `'max DD <= 25%' in ()` | take `screen_at_2026_10_07`; replace `tuning.MAX_DRAWDOWN` with `BAR_2026_10_07` at both comparison sites; replace `dev.FAILURE_LABELS[1]` with `f"max DD <= {BAR_2026_10_07:.0%}"`. M0019-RAW20-S25 at 20.7% is again outside the bar it was judged by. |
| `test_no_candidate_that_fails_a_condition_at_todays_bars_becomes_eligible` | `:990` | `'max DD <= 25%' in ()` for `M0019-RAW20-S25` | take `screen_at_2026_10_07` and use `f"max DD <= {BAR_2026_10_07:.0%}"` in the `(cid, index)` loop's assertion. The claim — these two are never admitted at any N — is the historical one and stays. |

**Impact:** the 2026-10-07 record stays fully covered and is now immune to the next move of
either constant.

---

### Step 9: the remaining engine tests

**File:** as listed. Measured on the full suite with the Step 1-5 change applied:
**44 failed, 4712 passed, 4 skipped.** Work them in this order.

**9a — `tests/test_lab_hardgate.py:1239-1244`,
`test_the_gate_refuses_a_promoted_variant_that_falls_past_the_bar_on_honest_data`.**
`DID NOT RAISE LabError`: the fixture's survivorship fall of `0.2346` now sits **inside** the
0.25 bar. This test must keep reading the **real-money** bar (Decision D3). Raise the fixture
only:

```python
    g = _grid(tmp_path, [("M0001", "M0001-A", "survivorship", "0.2846")])
    monkeypatch.setattr(survivorship_record, "GRID_PATH", g)
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    msg = str(e.value)
    assert "M0001-A" in msg and "28.46%" in msg and "25%" in msg and "D16" in msg
    assert "grid.csv" in msg
```

**9b — `tests/test_lab_gate_wording.py:284`,
`test_the_prose_matcher_reads_a_superseding_sentence_as_history`.** `_stated_bars` routes every
written percentage in the lab journal to `tuning.MAX_DRAWDOWN`, so insight #27's correct "20%"
reads as stale. The journal row cannot be edited (`insights_no_update` aborts) and the test says
so. The journal's drawdown sentences are about the **screen**, so change the one line:

```python
                if written.endswith("%"):
                    out.append((i, written, float(written[:-1]) / 100, tuning.DEV_MAX_DRAWDOWN))
```

and update `_stated_bars`'s docstring line "the drawdown bar always ``20%``" to
"the drawdown screen always ``50%``". **If that leaves insight #27's "20%" still flagged**, it is
because #27 states the 2026-10-07 bar as current and 2026-10-14 superseded it — in that case the
correct fix is a `SUPERSEDED_BARS = {0.15, 0.20}` set excused by `_stated_bars`, with a comment
naming both revision dates. Do **not** edit the journal. Also re-check
`test_the_web_mirrors_the_engines_drawdown_label_prefix` (`:207-229`): it asserts the prefix, not
the number, and should stay green — confirm, and update its docstring's "`tuning.MAX_DRAWDOWN` is
0.20 since 2026-10-07" to name `DEV_MAX_DRAWDOWN` and 2026-10-14.

**9c — `tests/test_dev_trades_bar.py:57-74`.** Measured: the set grew from 5 to **12**.
**RECONCILED 2026-10-14: 12 is confirmed, and phase 2's draft figure of 8 was wrong.** The
reconciler re-derived this read-only (lab md5 `00f7ebec1b3134e67e3b087226d308b7`, unchanged) and got
this exact list, in this exact order. Phase 2's planner measured 8 because its script patched
`tuning.MAX_DRAWDOWN`, which after Step 4 is **no longer what `owner_failures` compares against** —
8 is the count at a 0.25 *screen*, and the screen that lands is 0.50. At 0.50 the count is 12 and
`clearing the luck bar` is still **0**, so §13's load-bearing finding survives (phase 2 asserts
this, and its own stop-condition is satisfied). The test's own
message tells you to re-take the measurement and update both the list **and** design §13 (that
doc is **phase 2's** — see Handoffs). Replace `HELD_OUT_BY_THE_TRADES_BAR` with the measured set:

```python
#: Re-measured 2026-10-14 against the committed lab database, read-only, with no trial recorded,
#: after the owner split the dev screen off the real-money bar (design §18): the screen moved
#: 0.20 -> 0.50, so trials that previously missed BOTH drawdown and trades now miss trades alone.
HELD_OUT_BY_THE_TRADES_BAR: tuple[tuple[str, int], ...] = (
    ("F1-QQQ-SMA200-M", 17),
    ("F1-QQQ-VT15-W", 28),
    ("F1-SPY-10MSMA-M", 13),
    ("F1-SPY-ABS12-M", 9),
    ("F1-SPY-SMA200-M", 11),
    ("F2-SPYQQQ-12M", 14),
    ("F2-SPYQQQ-3M", 36),
    ("F2-SPYQQQ-6M", 28),
    ("M0084-BAND3-M", 9),
    ("M0084-BAND3-W", 10),
    ("M0084-FABER-M", 13),
    ("M0084-MONTHLY", 11),
)
```

Also update the docstring at `:158-160` — "the owner lowering ``tuning.MAX_DRAWDOWN``" becomes
"``tuning.DEV_MAX_DRAWDOWN``", and "they sit at 18.7% and 18.9% against today's 20% bar" is now a
statement about the 0.50 screen; re-measure or reword rather than leaving a stale number.
**Re-run the measurement yourself** rather than pasting this list, and paste what you measure.

**9d — `tests/test_backtest_dev.py` (7 tests).** All follow `FAILURE_LABELS[1]` = `"max DD <= 50%"`
and `make_row` at 0.50:

- `:208-210` `test_constants` — `f"max DD <= {tuning.MAX_DRAWDOWN:.0%}"` → `tuning.DEV_MAX_DRAWDOWN`.
- `:501` `test_every_failure_in_order` — expected tuple gains/loses the drawdown label; raise the
  fixture drawdown past 0.50 so the label still fires.
- `:518-526` `test_thresholds_come_from_tuning` — monkeypatch `tuning.DEV_MAX_DRAWDOWN` (not
  `MAX_DRAWDOWN`) to `0.05`; rename the local `real_max_dd` to `real_dev_max_dd`.
- `:564` `test_finalists_d8` — ranking changed because more rows are eligible; re-derive the
  expected finalist order from the fixtures and update it.
- `test_eligibility_boundaries[kw2]` and `[kw13]` — the `dd=0.25` case now passes the screen;
  move the boundary cases to `dd=0.50` / `math.nextafter(0.50, 1)`.
- `:783-795` `test_the_drawdown_label_follows_the_bar_and_keeps_its_prefix` — rewrite as:

```python
def test_the_drawdown_label_follows_the_bar_and_keeps_its_prefix() -> None:
    """D13: the label names the bar it enforces, and the prefix is the part that is stable.

    The bar it enforces is now the dev SCREEN (`tuning.DEV_MAX_DRAWDOWN`), split off from the
    owner's real-money `tuning.MAX_DRAWDOWN` on 2026-10-14 (design §18). `trials.failed` is
    append-only, so the 30 committed rows judged at 15% keep that text for ever, the rows judged
    between 2026-10-07 and 2026-10-14 keep 20%, and rows judged from now on carry 50%. All three
    must read as a drawdown miss, which is why every reader matches the prefix and never the
    whole string.
    """
    assert len(FAILURE_LABELS) == 5
    assert FAILURE_LABELS[1] == f"max DD <= {tuning.DEV_MAX_DRAWDOWN:.0%}" == "max DD <= 50%"
    assert FAILURE_LABELS[1] != f"max DD <= {tuning.MAX_DRAWDOWN:.0%}", (
        "the screen and the real-money bar are two numbers and the label names the screen; "
        "a label that follows MAX_DRAWDOWN would name a bar make_row does not compare against"
    )
    assert FAILURE_LABELS[1].startswith("max DD <= ")
    for historical in ("max DD <= 15%", "max DD <= 20%"):
        assert historical.startswith("max DD <= "), "the historical rows share the prefix"
    assert FAILURE_LABELS[0] == "beats SPY TR" and FAILURE_LABELS[-1] == "owner inputs"
```

**9e — the pure-prose cluster (~21 tests), all `20%` → `25%` because `MAX_DRAWDOWN_LABEL` moved.**
No logic changes; substitute the expected strings.

- `test_backtest_metrics.py:129` — `("Max drawdown ≤ 20%", "7.9%")` → `25%`. Also check `:120`
  (`max_drawdown: 0.21` is now a **pass** at 0.25) — raise it to `0.26`.
- `test_backtest_tuning.py:121`, `:159`, `:184` — `"max drawdown ≤ 20%"` → `25%` in the
  sentences and the `[c.label for c in v.checks]` list. `:85` `M(0.30, dd=0.25)`'s comment
  "drawdown too deep" is now wrong at exactly the bar; use `dd=0.26`. `:153`'s `max_drawdown=0.25`
  likewise.
- `test_backtest_walkforward.py` (3), `test_backtest_b_walkforward.py` (3) — the parametrised id
  `max drawdown ≤ 20%` and the `v.sentence.endswith(...)` strings → `25%`.
- `test_backtest_report.py` (2), `test_backtest_dev_report.py` (2, incl. `test_frontier_svg`),
  `test_backtest_wf_report.py` (1) — checklist/report prose → `25%`. `test_frontier_svg` asserts
  a rendered threshold line; re-derive it.
- `test_lab_luck.py:227`, `test_lab_status.py:159`, `test_lab_prereg.py:247` and `:357`,
  `test_lab_store.py:102`, `test_lab_test_window.py:339` — each has a fixture trial at `0.245`
  (or similar) that was meant to miss drawdown and now clears the 0.50 screen. Raise each to
  `0.55` and update the comment that names 24.5%. `test_lab_test_window.py:339` is the five
  go-live conditions on a test row; it reads `published_verdict`, which for a test row is the
  thresholds alone — still the screen, so `0.55` is the fix there too.

**9f — `tests/test_lab_snapshot.py::test_the_committed_snapshot_is_the_export_of_the_committed_database`.**
No edit. It goes green the moment Step 12 runs `lab stage`.

---

### Step 10: the new test — the split itself

**File:** `engine/tests/test_lab_gate_policy.py`, appended after the Step 8 fixtures.
**Runs before the commits:** Steps 11 and 12 come after this one.
**Change:** nothing in the suite asserts the thing this phase exists for. This does.

**Code:**

```python
def test_a_thirty_percent_fall_is_worth_studying_and_is_not_worth_money(conn):
    """**THE SPLIT.** One trial, two answers, and they disagree on purpose.

    This is the whole of R2. Before 2026-10-14 one float decided both "is this worth another hour
    of study" and "may the owner put money behind it", and the second answer was silently
    deciding the first. The owner separated them (design §18): ``tuning.DEV_MAX_DRAWDOWN`` is the
    screen, ``tuning.MAX_DRAWDOWN`` is the bar, and a trial that falls 30% now sits between them.

    It is a real shape, not a hypothetical. ``M0050-ON`` is recorded at a 30.48% fall with a
    money-weighted-irrelevant +823.2% against SPY TR's +257.2%, a profit factor of 2.83, 794
    closed trades and a DSR of 0.973. The fixture below is that trial's shape, built from the
    module's own helpers so this test owns no committed state and spends no test-window look.

    If this test ever goes green by the two constants being equal again, the split is gone and so
    is R2. The first assertion is there to say so out loud.
    """
    from seer_engine.backtest import dev, metrics, tuning

    assert tuning.DEV_MAX_DRAWDOWN > 0.30 > tuning.MAX_DRAWDOWN, (
        "the dev screen and the owner's real-money bar must straddle 30%: the screen admits a "
        "trial for study that the bar refuses funding. If these two numbers have collapsed back "
        "into one, R2 is undone and this is the test that was supposed to notice"
    )

    _method(conn)
    with conn:
        n, _ = store.insert_trials(conn, [
            _trial(candidate_id="M0001-A", config_digest="da",
                   total_return=8.232, spy_tr_return=2.572, cagr=0.102,
                   max_drawdown=0.3048, profit_factor=2.83, trades=794, mar=0.33,
                   failed="max DD <= 20%", eligible=False, n_trials_at_run=2),
            _ballast(candidate_id="M0001-SPREAD", config_digest="spread", max_drawdown=0.60),
        ])
        _moments(conn, n, sr_daily=0.0595, t=3900, var_trials=2.395e-04, n_at_run=2)
    row = conn.execute("SELECT * FROM trials WHERE candidate_id = 'M0001-A'").fetchone()

    # 1. THE SCREEN SAYS YES. It is worth another hour of study: no owner condition misses, and
    #    the drawdown label is not among them even though the row recorded one.
    assert store.owner_failures(row) == (), (
        "a 30.5% fall clears the 50% dev screen, so nothing holds this trial out of the lab's "
        "attention"
    )
    v = store.verdict(conn, row, at=store.Gate(n=2, policy="all-trials"))
    assert v.eligible is True and v.failed == ()
    assert dev.FAILURE_LABELS[1] == "max DD <= 50%"      # the label names the screen it used

    # 2. ...and the recorded string still says what it said on its own day. Nothing was rewritten.
    assert row["failed"] == "max DD <= 20%" and bool(row["eligible"]) is False

    # 3. THE REAL-MONEY BAR SAYS NO. §1 condition 4, the one the owner's money answers to, still
    #    refuses it -- at 25%, which is itself looser than the 20% that judged it.
    m = metrics.Metrics(
        total_return=8.232, win_rate=0.58, profit_factor=2.83, max_drawdown=0.3048,
        trades=794, months=240.0,
    )
    dd_item = {c.label: c for c in metrics.checklist(m, 2.572)}[metrics.MAX_DRAWDOWN_LABEL]
    assert dd_item.label == "Max drawdown ≤ 25%"
    assert dd_item.ok is False, (
        "the go-live checklist must still refuse a 30.5% fall. If this passes, the owner's "
        "real-money bar followed the dev screen and §1 condition 4 means nothing"
    )
    assert float(row["max_drawdown"]) > tuning.MAX_DRAWDOWN   # the D16 survivorship bar too

    # 4. And the second, independent no on the write edge agrees with the SCREEN, not the bar --
    #    because the edge it guards is `rejected -> dev-eligible`, which is research, not money.
    assert store._blocking(row, store.funding_of(conn, row["n"])) == ()
```

**Impact:** this is exit criterion 2, corrected per F3. Check the `_trial` helper's signature
before pasting — adjust keyword names to whatever the module's helper actually accepts, and drop
`cagr`/`mar` if it does not take them.

---

### Step 11: prove the invariants, then commit the source by pathspec

```bash
cd /home/miftah/.worktrees/seer/split-screen-from-bar

# the four DECISION sites, plus docstrings/comments, plus Step 5b's prose interpolation
grep -rn "DEV_MAX_DRAWDOWN" engine/src/seer_engine | grep -v "^engine/src/seer_engine/backtest/metrics.py:" \
  | grep -v "^engine/src/seer_engine/backtest/tuning.py:"
#   Occurrences may appear ONLY in backtest/dev.py and lab/store.py. Confirm by eye that the
#   DECISION sites are exactly four -- dev.FAILURE_LABELS, dev.make_row, store.owner_failures,
#   store._blocking -- and that every other hit is a docstring, a comment, or Step 5b's analysis
#   prose at store.py:1904. Do not pin a count here; pin the four names.

# and the converse: the real-money bar must be GONE from all four decision sites
grep -n "tuning.MAX_DRAWDOWN" engine/src/seer_engine/backtest/dev.py engine/src/seer_engine/lab/store.py
#   expect: nothing inside FAILURE_LABELS, make_row, owner_failures, _blocking or
#   reevaluate_method. store.snapshot (:2894) keeps it -- that one is R4.

# no recorded digest moved
cd engine && PYTHONPATH=../engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q \
  tests/test_lab_methods.py::test_every_recorded_configuration_still_digests_to_its_recorded_digest
```

```bash
git commit -m "lab: the drawdown bar was doing two jobs — 25% for money, 50% for study" -- \
  engine/src/seer_engine/backtest/metrics.py \
  engine/src/seer_engine/backtest/tuning.py \
  engine/src/seer_engine/backtest/dev.py \
  engine/src/seer_engine/lab/store.py \
  engine/tests/ \
  web/lib/golive.ts web/lib/golive.test.ts web/lib/sera/fixture.ts
```

`-m` before `--`. `git reset --hard`, `git clean`, `git checkout .`, `git restore .`, bare
`git stash`, `git add .` and `git add -A` are **banned** — in this session and in any subagent
you dispatch. Say that verbatim in any subagent prompt.

---
### Step 12: regenerate the lab snapshot and commit it bare

**ORDERING — RECONCILED 2026-10-14. This step runs LAST, after Step 11's pathspec commit.** It
was numbered 10 in the draft, which put a BARE `git commit` in front of every uncommitted source
edit from Steps 1-10: a bare commit sweeps all **tracked** modifications, so `metrics.py`,
`tuning.py`, `dev.py`, `store.py`, the ~40 tests and `golive.ts` would all have landed inside the
"restage the snapshot" commit. That breaks invariant 8, the two-commit Rollback story below, and
the revert-them-together rule in the index. Untracked files (the plan set, the analysis) are never
swept by a bare commit, so they are safe either way — tracked modifications are not. **Run Step 11
first; `git status --short` here must then show only `lab/lab.sqlite` and `web/data/lab.json`.**

**Change:** `lab stage` re-exports `web/data/lab.json` from the committed `lab.sqlite` and
git-adds both. `gate.maxDrawdown` moves `0.2` → `0.25`; the per-trial `eligible`/`failedNow`
fields move with the new screen. No row is inserted, updated or deleted.

```bash
cd /home/miftah/.worktrees/seer/split-screen-from-bar

# Nothing else may be swept up by the bare commit.
git status --short

engine/.venv/bin/python -m seer_engine lab stage       # or /home/miftah/seer/engine/.venv/bin/python

# The lab database MIGRATES ON CONNECT, so `lab stage` dirties lab.sqlite even though it writes
# no row. That is expected and is why both files are committed together.
git status --short

# BARE commit, NO pathspec. A pathspec commit re-reads the working tree and defeats `lab stage`.
git commit -m "lab: restage the snapshot at the 25% bar and the 50% dev screen"
```

**Impact:** `golive.test.ts:10` and `test_lab_snapshot.py` both go green.
**Guard:** if `git status --short` shows anything other than `lab/lab.sqlite` and
`web/data/lab.json`, **stop** — Step 11 did not run or did not cover everything. Commit the
stragglers by explicit pathspec, then re-run `lab stage` and the bare commit. Never `git add .`,
never `git add -A`. This guard is the last line of defence, not the plan: the ordering above is.

---


## Verification

**Docker:** `docker start seer-pg` if the container is down.

**Lint:**
```bash
/home/miftah/seer/engine/.venv/bin/ruff check engine
```

**Engine suite** (baseline on this machine, measured today at `49287bb`:
**4756 passed, 4 skipped** — the draft index's "4757 passed, 3 skipped" was measured elsewhere
and the index has since been corrected to agree with this;
`tests/test_universe_rank.py::...` skips here because the month-end sweep is not on this machine.
Re-baseline before you start and quote what *you* measure):
```bash
cd /home/miftah/.worktrees/seer/split-screen-from-bar/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/split-screen-from-bar/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
/home/miftah/seer/engine/.venv/bin/python -m pytest -q
```
Measured mid-change (Steps 1-5 only, no tests touched): **44 failed, 4712 passed, 4 skipped** in
80s. Target at the end: **0 failed**, pass count = baseline + 1 (the new test) = **4757 passed, 4
skipped**, skip count quoted. Step 5b lands after that measurement, so re-grep for tests pinning
`a max drawdown bar of` and fold any into the count you quote. **Phase 2 inherits this number** —
its own verification expects 4757 / 4.

**Web:**
```bash
cd /home/miftah/.worktrees/seer/split-screen-from-bar/web && npx tsc --noEmit && npm test
```

**Manual checks:**
```bash
# 1. the test window is untouched: 4 before, 4 after
PYTHONPATH=/home/miftah/.worktrees/seer/split-screen-from-bar/engine/src \
/home/miftah/seer/engine/.venv/bin/python -c "
from pathlib import Path; from seer_engine.lab import store
print(store.test_looks(store.connect_readonly(Path('lab/lab.sqlite'))))"

# 2. the lab database was not rewritten outside `lab stage`
sha256sum lab/lab.sqlite   # 2c8c9669ad7664... before Step 10; it changes only there, by migration

# 3. the before/after, for phase 2 (venv python; bare python3 has no deps)
PYTHONPATH=/home/miftah/.worktrees/seer/split-screen-from-bar/engine/src \
/home/miftah/seer/engine/.venv/bin/python - <<'PY'
from pathlib import Path
from seer_engine.lab import store
from seer_engine.backtest import tuning
conn = store.connect_readonly(Path("lab/lab.sqlite"))
rows = conn.execute("SELECT * FROM trials WHERE window='dev'").fetchall()
for screen in (0.20, 0.25, 0.50):
    tuning.DEV_MAX_DRAWDOWN = screen
    dd = [r for r in rows if r["max_drawdown"] is not None and float(r["max_drawdown"]) <= screen]
    g = store.gate(conn)
    el = [r for r in rows if store.verdict(conn, r, at=g).eligible]
    print(f"screen {screen:.2f}: browsable {len(dd)} trials / {len({r['method_id'] for r in dd})} methods"
          f" | dev-eligible {len(el)} trials / {len({r['method_id'] for r in el})} methods")
PY

# 4. git is clean
git status --short
```

**Exit criteria:**
1. `tuning.MAX_DRAWDOWN == 0.25`; `tuning.DEV_MAX_DRAWDOWN == 0.50`; the grep in Step 11 shows the
   four decision sites — `dev.FAILURE_LABELS`, `dev.make_row`, `store.owner_failures`,
   `store._blocking` — and no other decision site.
1b. **`store.py:1904`'s analysis prose names the screen** (Step 5b), so `lab reevaluate` can no
   longer write a false sentence into append-only `methods.analysis`. Prove it:
   `grep -n "max drawdown screen of" engine/src/seer_engine/lab/store.py` returns `:1904`, and
   `grep -n "a max drawdown bar of" engine/src/seer_engine/lab/store.py` returns nothing.
2. `metrics.checklist`, `tuning.gate`, `walkforward.gate_p3b`, `b_walkforward.gate_p6a`,
   `hardgate`'s D16 rule and `store.snapshot` all still read `MAX_DRAWDOWN`.
3. `test_a_thirty_percent_fall_is_worth_studying_and_is_not_worth_money` is green: one trial,
   dev-eligible under the screen, refused by the go-live checklist.
4. `web/lib/golive.ts` reads `0.25`, its label reads `Max drawdown ≤ 25%`,
   `web/data/lab.json`'s `gate.maxDrawdown` is `0.25`, `npx tsc --noEmit && npm test` green.
5. Every re-expressed test still asserts its original historical claim. **No test deleted** —
   `git diff --stat engine/tests` shows no file losing a `def test_`.
6. `store.test_looks` reads **4** before and after; the digest tripwire green;
   `git status --short` clean.
7. `ruff` clean; pytest green with the skip count quoted beside the pass count.
8. The measured before/after table is reported to phase 2 (see Return value).

---

## Handoffs

1. **To phase 2 — design §13's held-out measurement. RULED, 2026-10-14.**
   `tests/test_dev_trades_bar.py:51` names `RECORD = "docs/plans/2026-10-03-seer-design.md §13"`
   and its own failure message says to update the test's list **and** §13's together. The ruling
   (index Decision D9) is three-way and all three plans now say the same thing:
   - **Phase 1 owns the constant list** `HELD_OUT_BY_THE_TRADES_BAR` and its comment (Step 9c).
   - **§13 is edited by NOBODY.** It is a dated record of what was true on 2026-10-07; amending
     its list would rewrite history instead of extending it.
   - **Phase 2 records the re-measurement in a §18 bullet**, and nowhere else.
   The set grows **from 5 trials to 12**, not to 8 — the draft figure of 8 is the count at a 0.25
   screen and the screen that lands is 0.50 (Step 9c carries the reconciler's re-derivation and
   the full list). `clearing the luck bar` is 0 at 0.50, so §13's finding survives. Serves R3 in
   phase 2; the test edit itself is R2 here.

2. **To phase 2 — the honest numbers (index Decisions D8 and D11).** §18's **headline is the
   full-verdict pair: 26 trials / 16 methods → 67 / 32.** The browsable pair (93 / 37 → 319 / 76)
   may appear only beside it and explicitly labelled as "clears the drawdown condition". §18 must
   also say plainly that 0.25 alone already reaches 30 of the 32 eligible methods and that
   0.40 → 0.50 adds none. The owner reads this; the measurement that undercuts the chosen number
   belongs in it.

3. **`store.py:1904` — RETIRED. Fixed in this phase, Step 5b.** It was drafted as a follow-up and
   that was wrong: `reevaluate_method` writes its sentence through `append_analysis` into
   `methods.analysis`, which can only be appended to, so the first `lab reevaluate` after this
   phase would have recorded an irreversible falsehood. Step 5b makes the sentence name the
   screen. **There is no longer a "do not run `lab reevaluate`" caveat to carry anywhere**, and
   phase 2 must not publish one.

4. **`web/lib/sera/derive.ts:172` — NOT fixed here, and NOT floating: it is a named rough edge
   that phase 2's §18 states in plain language, and the index records it.** `derive.ts` builds a
   trial's drawdown target from `gate.maxDrawdown`, which stays at the real-money 0.25 because R4
   pins the TS constant to it through `golive.test.ts`. So `/sera` will show "25% or less" beside
   a trial at 40% that it also renders as clearing drawdown. It is cosmetic — no build break, no
   test red, nothing written — but it is **owner-facing**, and the owner reads that page, so it
   is recorded in the revision rather than left in a report. The eventual fix is a
   `gate.devMaxDrawdown` written by `store.snapshot` and read by `derive.ts`, touching `snapshot`
   (`:2894`), `web/lib/sera/types.ts` and `test_lab_snapshot`'s schema pin — none of which is in
   R1/R2/R4 and all of which would widen this phase past shippable. **Phase 1 does not touch it.
   Phase 2's §18 names it. Do not also open a card unless the owner asks.**

5. **Not done, deliberately.** Nothing promoted, nothing tested, no recorded row edited,
   `web/lib/cadence.ts` untouched (its `0.20` is `TARGET_RESIZE_BAND`), `test_sean_mirrors.py`
   not extended, `npolicy` untouched (M4: `dev_method_count` counts methods tried, so the screen
   cannot move N).

---

## Rollback

Two commits, reverted **together, newest first**:

```bash
# newest first: Step 12's lab-stage commit, then Step 11's source commit
git revert --no-commit <lab-stage-sha>
git revert --no-commit <source-sha>
git commit -m "Revert: the drawdown split"
```

Reverting the source alone leaves `web/data/lab.json` claiming a 25% bar the code no longer sets
and `golive.test.ts` goes red; reverting the lab commit alone leaves `test_lab_snapshot` red.

No database state to unwind: `trials`, `methods`, `insights` and `method_folds` are untouched by
this phase, and every verdict is derived at read time — the moment the constants go back, so do
the verdicts. `store.test_looks` is 4 throughout. **Never `git reset --hard`.**
