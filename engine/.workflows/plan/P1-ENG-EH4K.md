> Adopted from `LAB_LUCK_GATE_PLAN.md` phase 8. Source: `.workflows/plan/lab-luck-gate/phase-8.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 8: The go-live drawdown bar, 15% -> 20%

**Plan set:** `LAB_LUCK_GATE_PLAN.md`
**Analysis:** `20261007-085606-D3K1_code_analyzer.md`
**Satisfies:** R5 — the owner's risk appetite for the worst fall a strategy may take before it
may trade real money
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/backtest` (+ `web/lib`, `docs/plans`)

> **Provenance.** `MAX_DRAWDOWN = 0.15 -> 0.20` is an **owner decision, 2026-10-07**: *"i am
> thinking of my risk appetite, and i think let's set the Max drawdown to 20% instead of 15%"*.
> The scope question — lab screen only, or the real-money go-live bar too — was put to the owner
> explicitly and the owner chose **both**. The owner was told this is a real-money safety setting
> and was shown the blast radius, and reaffirmed. This plan implements it; it does not argue it,
> and no step below re-litigates it.

---

## Goal

The go-live drawdown condition (design §1 item 4) is **20%**, and it is spelled exactly twice in
the whole repo — once in Python, once in TypeScript — with a test that pins the two together
through the committed lab snapshot. Today it is spelled **five** times in live decision code
(`tuning.MAX_DRAWDOWN`, `metrics.checklist`, `web/lib/metrics.ts`'s label, `web/lib/metrics.ts`'s
comparison, `web/data/lab.json`), of which three do not read the constant at all, so changing the
constant alone would leave the P3/P3b/P6a gate and the web leaderboard judging at 15% while the
dev lab judged at 20%.

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Creates:**
- `seer_engine.backtest.metrics.MAX_DRAWDOWN` = `0.20` (`metrics.py`, new, near the module header)
  — the single Python definition of go-live #4.
- `seer_engine.backtest.metrics.MAX_DRAWDOWN_LABEL` = `"Max drawdown ≤ 20%"` (`metrics.py`, new).
- `web/lib/golive.ts` — new file: `MAX_DRAWDOWN = 0.2`, `MAX_DRAWDOWN_LABEL`.
- `web/lib/golive.test.ts` — new file: the engine/web agreement test.

**Value changes (behavioural):**
- `tuning.MAX_DRAWDOWN` `0.15` -> `0.20` (`tuning.py:27`), now by re-export from `metrics`.
- `metrics.checklist` item 5 compares against `MAX_DRAWDOWN` instead of the literal `0.15`
  (`metrics.py:271`) and labels itself `MAX_DRAWDOWN_LABEL` instead of the literal
  `"Max drawdown ≤ 15%"` (`metrics.py:269`).
- `web/lib/metrics.ts:74,76` — label and comparison both read `golive.ts`.
- `web/data/lab.json` — `gate.maxDrawdown` `0.15` -> `0.2`.

**Signature changes:** none. `checklist(m, spy_return)` / `checklist(m, spyReturn, gate)` keep
their exact signatures in both languages, so every caller is untouched.

**Deletes:** none. No symbol is removed or renamed.

**Value changes (behavioural), added by the reconciler — Decision D13:**
- `dev.FAILURE_LABELS[1]` becomes `f"max DD <= {tuning.MAX_DRAWDOWN:.0%}"`, i.e. `"max DD <= 20%"`.
  Five entries, same order, prefix `"max DD <= "` unchanged, and byte-identical to the historical
  string whenever the constant is put back to 0.15. See **Decision 2** (reversed) for the full
  reasoning and the rungs. `engine/src/seer_engine/backtest/dev.py` joins the Files table; no
  other phase in the set modifies that file.

**Does NOT change (explicitly, despite looking in scope):**
- The recorded `trials.failed` strings on the 110 committed rows. They are append-only
  (invariant 3) and state what was true on the night; phase 7's `derive.ts` reads both texts by
  prefix, and phase 4 reaches every verdict from the numeric `max_drawdown` column, never from a
  string.
- `store.DSR_MIN`, `store.DSR_LABEL`, `store.snapshot`'s gate *shape*, `lab/lab.sqlite`,
  `paper/roster.py`, `lab/store.py`, `lab/runner.py`, `lab/npolicy.py`, `commands/lab.py`,
  `backtest/dev.py` code (its `tuning.MAX_DRAWDOWN` read at `dev.py:369` already follows), the
  `deflated_sharpe` formula, `DEV_END`, the D9 guard.

**Requires (from earlier phases):** nothing. This phase has no `depends_on` and lands on
`origin/main` as it stands at `a95126a`.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/store.py` — phase 4 (`DSR_MIN`, `verdict`) and phase 7 (gate dict).
- `engine/src/seer_engine/paper/roster.py:522,537,588,605` — phase 6; those `gate_note` /
  `lab_provenance` strings are **history** (what each book was measured against at the time).
- `engine/src/seer_engine/lab/seed.py:145`, `engine/src/seer_engine/lab/methods/m00*.py` —
  recorded P7a verdicts and recorded method hypotheses. History; not retro-edited.
- `engine/package_readme.md`, `.claude/skills/explore-and-experiment-new-method/SKILL.md`,
  `engine/src/seer_engine/lab/prereg.py`, `docs/lab/prereg/README.md`, `web/lib/sera/types.ts`,
  `web/lib/sera/lab.ts`, `web/lib/sera/derive.ts`, `web/app/sera/overview.ts` — phase 7.
  **See Handoffs H2 and H3: three of these now contradict this phase and must be corrected there.**
- `docs/plans/2026-10-04-method-lab-design.md` §3 — phase 7. §1 of the *seer* design is mine.
- `docs/backtests/*.md` — committed generated reports recording past verdicts. History.

**Shared files — collisions the reconciler must sequence:**

| File | This phase changes | Other phase changes | Collision |
|---|---|---|---|
| `web/lib/sera/fixture.ts` | line 5 `maxDrawdown: 0.15` -> `0.2` | **phase 7**, line 8 `dsrMin: 0.95` -> `0.9` | adjacent lines in the same object literal — textual conflict, trivially resolved; both edits are wanted |
| `web/app/sera/overview.test.ts` | line 87 `maxDrawdown: 0.15` -> `0.2`, line 158 `x1: 0.15` -> `0.2`, line 161 `inZone` `1` -> `2` | **phase 7**, line 89 `dsrMin: 0.95` -> `0.9` | same object literal, lines 87 vs 89 |
| `web/app/sera/how/view.test.ts` | line 61 `'Worst fall ≤ 15%'` -> `20%`, line 63 `maxDrawdown: 0.2` override, line 107 `'Max drawdown ≤ 15%'` -> `20%` | **phase 7**, lines 61/63/64 `dsrMin`/`Luck check ≥ 0.95` | **same three lines.** See Decision 4 |
| `web/lib/sera/derive.test.ts` | line 39 `'15% or less'` -> `'20% or less'`, line 47 `maxDrawdown: 0.2` override | **phase 7**, line 42 `'0.95 or more'` | line 47's override is now a no-op — see Decision 4 |
| `web/app/sera/methods/view.test.ts` | lines 143, 155 and the line-154 fixture | **phase 7**, line 143 `'0.90 < 0.95'` | same `expect` block at 141–147 |
| `engine/tests/test_lab_snapshot.py:170` | `"maxDrawdown": 0.15` -> `0.20` | **phase 4** (`"dsrMin": 0.95` -> `0.90`) and **phase 7** (new gate keys) | same dict literal, same line |
| `web/data/lab.json` | `gate.maxDrawdown` `0.15` -> `0.2` | **phase 4** (`dsrMin`), **phase 7** (new gate keys + regeneration) | same `"gate":{…}` object. See Decision 5 |

---

## Decisions

These are the four judgement calls in this phase. An implementer who disagrees should raise it
rather than quietly diverge, because each one was made against a specific hazard.

### Decision 1 — the Python constant's home moves to `metrics.py`, and `tuning` re-exports it

`metrics.checklist` is a **second, independent implementation of go-live #4 in Python** that does
not read `MAX_DRAWDOWN`: `metrics.py:271` compares against the literal `0.15`. It is not dead
code — `tuning.gate` (P3), `walkforward.gate_p3b` (P3b) and `b_walkforward.gate_p6a` (P6a) all
decide the drawdown condition by `checklist(...)[2:5]`, i.e. **the real-money gate for Strategies
A, A2 and B reads the literal, not the constant.** `tuning.py:27`'s own comment already asserts
the coupling ("equals the threshold in `metrics.checklist`") and is the only thing holding them
together today.

`tuning` imports `metrics` (`tuning.py:17`), so `metrics` cannot import `tuning` — the constant
must live in `metrics` for `checklist` to read it. Therefore:

- `metrics.MAX_DRAWDOWN` is the definition.
- `tuning.MAX_DRAWDOWN = metrics.MAX_DRAWDOWN` is a re-export, so **every existing reader is
  untouched**: `dev.py:369`, `store.py:830`, `dev_report.py:50`, `tuning.qualifies` and
  `test_backtest_tuning.py` all keep reading `tuning.MAX_DRAWDOWN`, and
  `monkeypatch.setattr(tuning, "MAX_DRAWDOWN", …)` in `test_backtest_dev.py` keeps working
  because `dev.py` resolves the attribute at call time.

### Decision 2 — `dev.FAILURE_LABELS[1]` follows the constant: `f"max DD <= {MAX_DRAWDOWN:.0%}"`

> **REVERSED BY THE RECONCILER, 2026-10-07 — Decision D13.** This section originally argued the
> label must stay frozen at `"max DD <= 15%"`. **Its premise no longer holds**, and the reasoning
> is kept below so the reversal can be checked rather than taken on trust.

**The premise that failed.** The argument rested on `web/lib/sera/derive.ts:66` deciding a miss by
`trial.failed.includes(FAILURE_LABEL[key])` — exact string equality. **Phase 7 replaces that with
prefix matching** (`DRAWDOWN_FAILURE_PREFIX = 'max DD <= '`) precisely so both texts read as a
miss, and pins it from the engine side with
`test_the_web_mirrors_the_engines_drawdown_label_prefix`, which asserts that
**both** `dev.FAILURE_LABELS[1]` and the historical `"max DD <= 15%"` start with that prefix —
an assertion that only has content if the two are allowed to differ. So the 30 recorded rows keep
rendering as misses whatever this constant says, and the falsification this section feared cannot
happen.

**What frozen text would cost instead.** Phase 4's `store.owner_failures` re-derives the drawdown
condition from the numeric `max_drawdown` column against `tuning.MAX_DRAWDOWN` and reports the
miss **using the live label text**. Left frozen, a trial that actually missed a **20%** bar would
be told, in `trials.failed` and on the site, that it missed `"max DD <= 15%"` — a false reason,
written into an append-only column for ever. A stale label is not neutral once the verdict beside
it is live.

**The rule, and it cannot drift:**

```python
FAILURE_LABELS: tuple[str, ...] = (
    "beats SPY TR",
    f"max DD <= {tuning.MAX_DRAWDOWN:.0%}",  # follows the constant; see design §11
    "PF >= 1.3",
    ">= 100 trades",
    "owner inputs",
)
```

Five entries, same order, same prefix. At `MAX_DRAWDOWN = 0.15` this reproduces the historical
string **byte-for-byte**, which is what makes the change safe to revert and what keeps
`test_the_old_bars_reproduce_todays_verdicts` honest. `tuning` is already imported in `dev.py`
(`:46`) and `FAILURE_LABELS` is defined after the import block (`:70`), so no import moves.

**Rungs, in the order rule 6 takes them:** the index's phase-8 exit criterion — *"`dev.FAILURE_LABELS[1]`
follows it and stays prefix-stable (`"max DD <= " + the number`)"* — is rung 2 and speaks
directly; phase 7's `derive.ts` prefix matcher and its two engine pins are rung 3 and agree;
phase 4's contract for `owner_failures` ("using the **live** label text") is rung 3 and agrees.
Nothing on a higher rung speaks against.

**What this costs in the diff.** `engine/tests/test_lab_test_window.py:327` keeps one literal
`("max DD <= 15%",)` under the old plan; it must become `(dev.FAILURE_LABELS[1],)` — see Step 10
Code (g), already corrected. Step 10 already refers to the label symbolically as
`FAILURE_LABELS[1]` everywhere else, so no other `15%` literal survives in those tests.

**What is still phase 4's.** The recorded `trials.failed` strings on the 110 committed rows are
never rewritten (invariant 3), and phase 4 reaches every verdict by **number**, not by string.
This decision changes only what the engine writes *next* and what `owner_failures` *names*.

### Decision 3 — the web spells the number once, pinned to the engine by a test

`web/lib/metrics.ts` is reached from `app/(app)/leaderboard/page.tsx`, which is app code;
`web/lib/sera/lab.ts` carries an explicit warning that importing `data/lab.json` outside a server
component ships the whole lab snapshot to the browser. So reading `lab.gate.maxDrawdown` directly
from `lib/metrics.ts` is not acceptable on that path. The brief's sanctioned fallback applies: a
static constant, **pinned with a test that compares it to the committed snapshot's gate value**
(`web/lib/golive.test.ts`). That test is also the VERIFY item "the web leaderboard and the engine
agree on the bar, proven by a test that reads both, not by inspection": `lab.gate.maxDrawdown` is
written by `store.snapshot` from `tuning.MAX_DRAWDOWN`, so the assertion spans both languages.

`web/app/sera/how/view.ts:182` already does the right thing (reads `gate.maxDrawdown`) and needs
no change — it is the model the brief names, and it is left exactly as it is.

### Decision 4 — the "reads the gate, not constants" tests need new override values

Three web tests prove that a threshold is read from the gate rather than hardcoded, and they do it
by overriding the gate to **0.2** — the value the gate is about to become:

- `web/lib/sera/derive.test.ts:47` — `{ ...GATE, maxDrawdown: 0.2, … }`
- `web/app/sera/how/view.test.ts:63` — `{ ...GATE, maxDrawdown: 0.2, dsrMin: 0.9 }`, named `loose`

Once `GATE.maxDrawdown` is `0.2` these overrides are no-ops and the tests stop proving anything —
they would pass even against a hardcoded constant. Both move to a value distinct from the new
default. This is the same trap phase 7 hits with `dsrMin: 0.9`, on the same two lines, which is
why the collision table flags them: **whoever lands second must check the override is still
different from the default, not merely that the file merged.**

### Decision 5 — `web/data/lab.json`'s gate is edited here as a single value

`golive.test.ts` compares `MAX_DRAWDOWN` to `lab.gate.maxDrawdown`, so the committed snapshot must
carry 0.2 or this phase does not pass its own tests. The snapshot is generated by `lab stage` from
`store.snapshot()`, which reads `tuning.MAX_DRAWDOWN` at call time — but regenerating it requires
the lab database, which phase 4 alone may migrate (plan invariant 6). So this phase performs a
**surgical one-key edit** of the committed JSON rather than a regeneration. Phases 4 and 7 edit
sibling keys of the same small object; phase 7's eventual full regeneration supersedes all three
and must produce the same `0.2`.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/metrics.py` | modify | define `MAX_DRAWDOWN` + `MAX_DRAWDOWN_LABEL`; `checklist` reads both (`:269`, `:271`) |
| `engine/src/seer_engine/backtest/tuning.py` | modify | `:27` re-export; `_GATE_NAMES` `:30`; docstrings `:63`, `:68`, `:93`, `:108`, `:125` |
| `engine/src/seer_engine/backtest/dev.py` | modify | `FAILURE_LABELS[1]` becomes `f"max DD <= {tuning.MAX_DRAWDOWN:.0%}"` (`:70-76`) — **Decision D13**, added in round 2. No other phase in the set modifies this file |
| `engine/src/seer_engine/backtest/walkforward.py` | modify | `_GATE_NAMES` `:59`; `gate_p3b` docstring `:354` |
| `engine/src/seer_engine/backtest/b_walkforward.py` | modify | `gate_p6a` docstring `:470` |
| `engine/src/seer_engine/backtest/dev_report.py` | modify | prose `:579`, `:919`, `:964`; heading `:1217` |
| `engine/src/seer_engine/backtest/report.py` | modify | prose `:249`, `:255`, `:291` |
| `engine/src/seer_engine/backtest/wf_report.py` | modify | prose `:433`, `:469` |
| `engine/src/seer_engine/backtest/b_report.py` | modify | prose `:495`, `:498` |
| `engine/tests/test_backtest_metrics.py` | modify | `:126` label |
| `engine/tests/test_backtest_tuning.py` | modify | `:159` label, `:170` boundary, `:184` sentence |
| `engine/tests/test_backtest_dev.py` | modify | `:457`, `:468`, `:491`–`:493`, `:529` |
| `engine/tests/test_backtest_walkforward.py` | modify | `:638`, `:648`, `:659` |
| `engine/tests/test_backtest_b_walkforward.py` | modify | `:585`, `:595`, `:608` |
| `engine/tests/test_backtest_report.py` | modify | `:310`, `:337` labels |
| `engine/tests/test_backtest_wf_report.py` | modify | `:351` prose |
| `engine/tests/test_backtest_dev_report.py` | modify | `:542`, `:579` |
| `engine/tests/test_lab_test_window.py` | modify | `:327` boundary |
| `engine/tests/test_lab_snapshot.py` | modify | `:170` gate dict |
| `web/lib/golive.ts` | **create** | the single TS definition of go-live #4 |
| `web/lib/golive.test.ts` | **create** | pins it to `data/lab.json`'s gate |
| `web/lib/metrics.ts` | modify | `:74`, `:76` |
| `web/lib/metrics.test.ts` | modify | `:44` boundary |
| `web/data/lab.json` | modify | `gate.maxDrawdown` |
| `web/lib/sera/fixture.ts` | modify | `:5` |
| `web/app/sera/overview.test.ts` | modify | `:87`, `:158`, `:161` |
| `web/app/sera/how/view.test.ts` | modify | `:61`, `:63`, `:107` |
| `web/lib/sera/derive.test.ts` | modify | `:39`, `:47` |
| `web/app/sera/methods/view.test.ts` | modify | `:143`, `:154`, `:155` |
| `docs/plans/2026-10-03-seer-design.md` | modify | §1 item 4 + new §11 owner revision |

30 files: 9 engine source, 10 engine test, 2 web source (1 new), 8 web test/data (1 new), 1 doc.

---

## Implementation Steps

### Step 1: Define the Python constant where `checklist` can reach it
**File:** `engine/src/seer_engine/backtest/metrics.py:30` (just after `YEAR_DAYS`)

**Change:** Add the constant next to the other module-level numbers. `MAX_DRAWDOWN_LABEL` cannot
go here because it calls `fmt_pct`, which is defined at `:225`; it goes in Step 2.

**Code:** after the existing

```python
MONTH_DAYS = 30.44
YEAR_DAYS = 365.25
```

insert:

```python
MAX_DRAWDOWN = 0.20
"""Go-live condition #4 (design §1): the deepest peak-to-trough fall a strategy may show.

The single definition in Python. ``tuning.MAX_DRAWDOWN`` re-exports this name, so every caller
that reads the threshold -- ``checklist`` below, ``tuning.qualifies``, ``tuning.gate``,
``walkforward.gate_p3b``, ``b_walkforward.gate_p6a``, ``dev.make_row`` and ``lab.store.snapshot``
-- resolves to this one float. It lives here, not in ``tuning``, only because ``tuning`` imports
``metrics`` and the dependency cannot run the other way.

0.15 until 2026-10-07, when the owner raised it to 0.20 on stated risk appetite; design §11
records the revision. ``web/lib/golive.ts`` carries the same number for the leaderboard and is
pinned to it through ``data/lab.json``'s gate by ``web/lib/golive.test.ts``.
"""
```

**Impact:** No behaviour yet — nothing reads it until Step 2. `metrics.py` gains no import.

---

### Step 2: Make `checklist` read the constant instead of spelling it
**File:** `engine/src/seer_engine/backtest/metrics.py:243` and `:269,271`

**Change:** Add `MAX_DRAWDOWN_LABEL` immediately above the checklist section (it is below
`fmt_pct` at `:225`, so the call is legal), then use both in `checklist`.

**Code:** replace the section marker and the whole `checklist` function, i.e. everything from

```python
# --------------------------------------------------------------------------- go-live checklist
```

to the end of `checklist`, with:

```python
# --------------------------------------------------------------------------- go-live checklist

MAX_DRAWDOWN_LABEL = f"Max drawdown ≤ {fmt_pct(MAX_DRAWDOWN, 0)}"
"""The checklist's label for go-live #4, built from ``MAX_DRAWDOWN`` so it cannot drift from the
threshold it names. ``web/lib/golive.ts`` builds the same string the same way."""


def checklist(m: Metrics, spy_return: float | None) -> list[CheckItem]:
    """``checklist`` from web/lib/metrics.ts: the fixed go-live rules (design §1), same labels and
    value strings."""
    ret = m.total_return if m.total_return is not None else 0.0
    pf = m.profit_factor
    return [
        CheckItem(
            "≥ 3 months forward",
            f"{to_fixed(math.floor(m.months * 10) / 10, 1)} mo",
            m.months >= 3,
        ),
        CheckItem("≥ 100 trades", f"{m.trades} / 100", m.trades >= 100),
        CheckItem(
            "Beats SPY",
            DASH if spy_return is None else f"{_p1(ret)} vs {_p1(spy_return)}",
            m.total_return is not None and spy_return is not None and ret > spy_return,
        ),
        CheckItem(
            "Profit factor ≥ 1.3",
            DASH if pf is None else INFINITY if pf == math.inf else to_fixed(pf, 2),
            (pf if pf is not None else 0.0) >= 1.3,
        ),
        CheckItem(
            MAX_DRAWDOWN_LABEL,
            DASH if m.max_drawdown is None else to_fixed(m.max_drawdown * 100, 1) + "%",
            m.max_drawdown is not None and m.max_drawdown <= MAX_DRAWDOWN,
        ),
    ]
```

**Impact:** **This is the behavioural heart of the phase.** `tuning.gate` (P3),
`walkforward.gate_p3b` (P3b) and `b_walkforward.gate_p6a` (P6a) all decide the drawdown condition
through `checklist(...)[2:5]`, so all three real-money gates move to 20% here. The item's label
becomes `"Max drawdown ≤ 20%"` everywhere it is rendered.

---

### Step 3: Re-export from `tuning` and fix every sentence that spells 15%
**File:** `engine/src/seer_engine/backtest/tuning.py:17,27,30,63,68,93,108,125`

**Change:** import the constant and alias it; update `_GATE_NAMES` and the five prose spellings.

**Code (a)** — replace the existing import at `:16`–`:17` with (**anchor on the quoted text, not the line numbers: the plan's earlier `:17`–`:18` was one line high — verified against the file on disk, where the `metrics` import is `:16` and the `strategies.a` import is `:17`**):

```python
from seer_engine.backtest import metrics as _metrics
from seer_engine.backtest.metrics import (
    MAX_DRAWDOWN_LABEL,
    CheckItem,
    Metrics,
    checklist,
    fmt_pct,
    fmt_signed_pct,
    to_fixed,
)
from seer_engine.strategies.a import DESIGN_PARAMS, AParams
```

Two changes to note: `to_fixed` is new (Code (e) needs it for `MIN_PROFIT_FACTOR`), and the module
is **also** imported under an alias so the constant can be aliased without a self-assignment —
writing `MAX_DRAWDOWN = MAX_DRAWDOWN` after a `from … import MAX_DRAWDOWN` is legal Python but
reads as a typo and Ruff flags it (`PLW0127`).

**Code (b)** — `:27`–`:30`, replace the two constants and `_GATE_NAMES`:

```python
# go-live #4, re-exported from ``metrics`` so ``checklist`` and this module cannot drift apart.
# Every reader of the threshold (dev.make_row, lab.store.snapshot, dev_report, qualifies, gate)
# goes through this name; the value lives in ``metrics.MAX_DRAWDOWN``. Raised 0.15 -> 0.20 by the
# owner on 2026-10-07; design §11.
MAX_DRAWDOWN = _metrics.MAX_DRAWDOWN
MIN_PROFIT_FACTOR = 1.3  # go-live #3; equals the threshold in metrics.checklist

_GATE_NAMES = ("beating total-return SPY", "profit factor ≥ 1.3", MAX_DRAWDOWN_LABEL.lower())
```

`MAX_DRAWDOWN_LABEL.lower()` yields `"max drawdown ≤ 20%"` — the same shape as the old hand-written
third entry of `_GATE_NAMES`, which the failure sentences interpolate.

**Code (c)** — `:63`, the `Verdict` dataclass comment:

```python
@dataclass(frozen=True)
class Verdict:
    passed: bool
    checks: tuple[CheckItem, ...]  # checklist items "Beats SPY", "Profit factor ≥ 1.3", MAX_DRAWDOWN_LABEL
    sentence: str
```

**Code (d)** — `:68`, `qualifies`'s docstring:

```python
def qualifies(m: Metrics) -> bool:
    """A grid run may be selected only if max DD ≤ ``MAX_DRAWDOWN`` and PF ≥ ``MIN_PROFIT_FACTOR``
    (infinite PF qualifies)."""
    return (
        m.total_return is not None
        and m.max_drawdown is not None
        and m.max_drawdown <= MAX_DRAWDOWN
        and m.profit_factor is not None
        and m.profit_factor >= MIN_PROFIT_FACTOR
    )
```

**Code (e)** — `:93`, inside `select`'s no-candidate branch, and `:108`, its reason string. Both
become interpolated:

```python
    if not candidates:
        return Selection(
            params=fallback,
            qualified=False,
            reason=(
                f"No in-sample grid run had max drawdown ≤ {fmt_pct(MAX_DRAWDOWN, 0)} and profit "
                f"factor ≥ {to_fixed(MIN_PROFIT_FACTOR, 1)} (0 of {n}), "
                "so the design values are kept."
            ),
        )
```

and

```python
    reason = (
        f"Grid run #{best_i + 1} has the highest in-sample total return "
        f"({fmt_signed_pct(best.metrics.total_return)}, max drawdown {fmt_pct(best.metrics.max_drawdown)}) "
        f"among the {len(candidates)} of {n} runs with max drawdown ≤ {fmt_pct(MAX_DRAWDOWN, 0)} "
        f"and profit factor ≥ {to_fixed(MIN_PROFIT_FACTOR, 1)}"
    )
```

> `to_fixed` must be added to the `from seer_engine.backtest.metrics import (…)` list for these two
> f-strings.

**Code (f)** — `:125`, `gate`'s docstring:

```python
def gate(oos: Metrics, spy_tr_oos: Metrics) -> Verdict:
    """The P3 gate, decided by out-of-sample results only.

    It passes when total return > total-return SPY (strict), profit factor ≥
    ``MIN_PROFIT_FACTOR`` and max drawdown ≤ ``MAX_DRAWDOWN``. The checks are ``checklist``
    items 3–5, so the labels and value strings match the web.
    """
```

**Impact:** `tuning.qualifies` now admits in-sample grid runs up to 20% drawdown, so a future
Strategy A grid selection may pick a different row than the committed one. **No committed artifact
changes** — `strategies/a.py`'s frozen parameters and `docs/backtests/*.md` record what the
2026-10-02 run actually selected and are not regenerated. See **Risk R2**.

---

### Step 3b: `dev.py` — the failure label follows the constant (Decision D13)

**Added in reconciliation round 2.** This step did not exist in the first draft, which froze the
label; see **Decision 2**, reversed, for why and on which rungs.

**File:** `engine/src/seer_engine/backtest/dev.py:70-76`.
**No other phase in this set modifies this file**, so there is no collision and no sequencing.

**Change:** entry `[1]` is interpolated from the constant instead of spelled. Nothing else in the
tuple moves — same five entries, same order, same `"max DD <= "` prefix.

```diff
 FAILURE_LABELS: tuple[str, ...] = (
     "beats SPY TR",
-    "max DD <= 15%",
+    # go-live #4's label, interpolated from the bar it names so the two can never disagree.
+    # Raised 0.15 -> 0.20 by the owner on 2026-10-07 (design §1 item 4, §11); at 0.15 this
+    # formats to "max DD <= 15%" byte-for-byte, which is what makes the change revertible and
+    # what keeps the 110 recorded rows comparable. The PREFIX is the stable part: `trials.failed`
+    # is append-only, so rows judged before that day keep "max DD <= 15%" for ever and rows
+    # judged after carry "max DD <= 20%". Both are misses, and every reader -- store.owner_failures
+    # in Python, DRAWDOWN_FAILURE_PREFIX in web/lib/sera/derive.ts -- matches on "max DD <= ",
+    # never on the whole string. See tests/test_lab_gate_wording.py (phase 7).
+    f"max DD <= {tuning.MAX_DRAWDOWN:.0%}",
     "PF >= 1.3",
     ">= 100 trades",
     "owner inputs",
 )
```

**Why this is safe where it sits.** `tuning` is already imported at `dev.py:46`, well above
`FAILURE_LABELS` at `:70`, so no import moves and `dev.py`'s purity (no `seer_engine.research`
import; `tests/test_strategy_purity.py` globs this module) is untouched. The tuple is built once
at import, so a test that `monkeypatch.setattr(tuning, "MAX_DRAWDOWN", …)` still gets the live
comparison at `dev.py:369` (resolved at call time) and the import-time label text — which is
exactly what every such test already asserts, because Step 9 and Step 10 refer to the label
symbolically as `FAILURE_LABELS[1]` rather than by literal.

**Add to Step 9's test file** (`engine/tests/test_backtest_dev.py`), one assertion:

```python
def test_the_drawdown_label_follows_the_bar_and_keeps_its_prefix() -> None:
    """D13: the label names the bar it enforces, and the prefix is the part that is stable.

    `trials.failed` is append-only, so the 30 committed rows judged at 15% keep that text for
    ever while rows judged from now on carry 20%. Both must read as a drawdown miss, which is why
    every reader matches the prefix and never the whole string.
    """
    from seer_engine.backtest import dev, tuning

    assert len(dev.FAILURE_LABELS) == 5
    assert dev.FAILURE_LABELS[1] == f"max DD <= {tuning.MAX_DRAWDOWN:.0%}" == "max DD <= 20%"
    assert dev.FAILURE_LABELS[1].startswith("max DD <= ")
    assert "max DD <= 15%".startswith("max DD <= "), "the historical rows share the prefix"
    assert dev.FAILURE_LABELS[0] == "beats SPY TR" and dev.FAILURE_LABELS[-1] == "owner inputs"
```

**Impact:** `store.owner_failures` (phase 4) and `tuning._GATE_NAMES` now name the bar they
actually enforce. Phase 7's `test_the_web_mirrors_the_engines_drawdown_label_prefix` reads
`dev.FAILURE_LABELS[1]` and asserts only the prefix, so it passes before and after.

---

### Step 4: `walkforward.py` — the P3b gate's names and docstring
**File:** `engine/src/seer_engine/backtest/walkforward.py:59,354`

**Change:** `_GATE_NAMES` is imported by `b_walkforward.py:47`, so fixing it here fixes P6a's
failure sentence too.

**Code (a)** — `:59`, with the import at the top of the file extended to pull the label:

```python
_GATE_NAMES = ("beating total-return SPY", "profit factor ≥ 1.3", MAX_DRAWDOWN_LABEL.lower())
```

`walkforward.py` already imports `checklist` from `seer_engine.backtest.metrics`; add
`MAX_DRAWDOWN_LABEL` to that same import list.

**Code (b)** — `:354`, `gate_p3b`'s docstring:

```python
def gate_p3b(wf: Metrics, spy_tr: Metrics, start: date, end: date) -> Verdict:
    """The P3b gate on the walk-forward curve over ``[start, end]``.

    Passes when the walk-forward total return beats total-return SPY (strict), profit factor
    ≥ 1.3 and max drawdown ≤ ``tuning.MAX_DRAWDOWN``: ``checklist`` items 3–5, the same labels
    and values as the web.
    """
```

**Impact:** P3b's failure sentence now names "max drawdown ≤ 20%".

---

### Step 5: `b_walkforward.py` — the P6a docstring
**File:** `engine/src/seer_engine/backtest/b_walkforward.py:470`

**Change:** docstring only; `_GATE_NAMES` is imported from `walkforward` and already fixed.

**Code:**

```python
def gate_p6a(wf: Metrics, spy_tr: Metrics, start: date, end: date, gated: str) -> Verdict:
    """The P6a gate on the gated walk-forward curve over ``[start, end]``.

    The same rule as P3b: the walk-forward total return beats total-return SPY (strict), with
    profit factor ≥ 1.3 and max drawdown ≤ ``tuning.MAX_DRAWDOWN`` (``checklist`` items 3–5, the
    web's labels and values). ``gated`` is ``B``, or ``B_LINEAR`` only when the determinism
    switch fired, and then the sentence's subject says so.
    """
```

**Impact:** None at runtime.

---

### Step 6: `dev_report.py` — the frontier chart's prose and the gate heading
**File:** `engine/src/seer_engine/backtest/dev_report.py:579,919,964,1217`

**Change:** Lines 930, 998, 1002 and 1220 already interpolate `MAX_DRAWDOWN` and are **verified
correct — change nothing there.** Only the four prose spellings move. `MAX_DRAWDOWN` and
`fmt_pct` are already imported at `:50`.

**Code (a)** — `:579`, the figure caption (an element of a list of strings):

```python
        f"Each dot is one candidate on its own window. Dots right of the dashed "
        f"{fmt_pct(MAX_DRAWDOWN, 0)} line fail D8 on drawdown. The diamond is total-return SPY on "
        f"{_span(r.spy_window[0], r.spy_window[1])}. Finalists are labelled.",
```

**Code (b)** — `:919`, `frontier_svg`'s docstring. A docstring cannot interpolate, so it names the
constant:

```python
def frontier_svg(r: DevReport) -> str:
    """CAGR (y) against max drawdown (x), one dot per candidate with both, SPY total-return on
    ``spy_window`` as a diamond, the ``MAX_DRAWDOWN`` limit dashed, finalists labelled.
    Self-contained, light and dark palettes, no script."""
```

**Code (c)** — `:964`, the SVG `<desc>`:

```python
        '<desc id="desc">Scatter of CAGR against max drawdown for every P7a candidate on the '
        f"development window, with total-return SPY and the {fmt_pct(MAX_DRAWDOWN, 0)} drawdown "
        "limit marked. The values are in the rows CSV next to this file.</desc>",
```

**Code (d)** — `:1217`, the heading, which currently claims the thresholds are unchanged and is
now false:

```python
            "## Gate (design §1)",
```

**Impact:** Future P7a reports describe the 20% line they actually draw. Committed reports under
`docs/backtests/` are untouched records of past runs.

---

### Step 7: `report.py` — Strategy A's report prose
**File:** `engine/src/seer_engine/backtest/report.py:249,255,291`

**Change:** three sentences.

**Imports — verified, do not guess:** `report.py:29` already imports `fmt_pct` and `to_fixed` from
`seer_engine.backtest.metrics`. `report.py:44` already has a parenthesised
`from seer_engine.backtest.tuning import (…)` block — add `MAX_DRAWDOWN` to it, in alphabetical
position before `GRID_LIMIT`. Nothing else is needed.

**Code (a)** — `:249`:

```python
        f"  - Selection takes the highest in-sample total return among runs with max drawdown "
        f"≤ {fmt_pct(MAX_DRAWDOWN, 0)} "
```

**Code (b)** — `:255`:

```python
        f"factor ≥ 1.3 and max drawdown ≤ {fmt_pct(MAX_DRAWDOWN, 0)}. In-sample numbers never "
        "decide it.",
```

**Code (c)** — `:291`:

```python
        f"drawdown ≤ {fmt_pct(MAX_DRAWDOWN, 0)} and profit factor ≥ 1.3. Selection reads these "
        "numbers and nothing else.",
```

> Read the surrounding list entries before editing: each of these three is a fragment of an
> adjacent-string concatenation, and the join points must be preserved exactly. Converting only
> the fragment that carries `15%` into an f-string is sufficient.

**Impact:** Generated Strategy A reports state 20%.

---

### Step 8: `wf_report.py` and `b_report.py` — the same prose for A2 and B
**File:** `engine/src/seer_engine/backtest/wf_report.py:433,469` and
`engine/src/seer_engine/backtest/b_report.py:495,498`

**Change:** identical treatment to Step 7 — interpolate `fmt_pct(MAX_DRAWDOWN, 0)` in place of the
`15%` literal.

**Imports — verified, do not guess:**
- `wf_report.py:31` already imports `fmt_pct` from `metrics`; `wf_report.py:69` already has a
  parenthesised `from seer_engine.backtest.tuning import (…)` block — add `MAX_DRAWDOWN` to it.
- `b_report.py:45` already imports `fmt_pct` from `metrics`, but `b_report.py:72` is the
  **single-name** form `from seer_engine.backtest.tuning import Verdict`. Widen it:
  ```python
  from seer_engine.backtest.tuning import MAX_DRAWDOWN, Verdict
  ```

**Code** — `wf_report.py:433`:

```python
        f"combinations with max drawdown ≤ {fmt_pct(MAX_DRAWDOWN, 0)} and profit factor ≥ 1.3. "
        "Ties go to the lower max "
```

`wf_report.py:469`:

```python
        f"same span, with profit factor ≥ 1.3 and max drawdown ≤ {fmt_pct(MAX_DRAWDOWN, 0)}. "
        "Nothing else decides it.",
```

`b_report.py:495,498`:

```python
        f"same span, with profit factor ≥ 1.3 and max drawdown ≤ {fmt_pct(MAX_DRAWDOWN, 0)}. "
        "Nothing else decides it. The "
        …
        f"than that with at most a {fmt_pct(MAX_DRAWDOWN, 0)} drawdown.",
```

**Impact:** Generated A2 and B reports state 20%.

---

### Step 9: Engine tests — the label assertions
**Files:** `engine/tests/test_backtest_metrics.py:126`,
`engine/tests/test_backtest_report.py:310,337`,
`engine/tests/test_backtest_tuning.py:159,184`,
`engine/tests/test_backtest_wf_report.py:351`,
`engine/tests/test_backtest_dev_report.py:542,579`

**Change:** every expected string `15%` for the **go-live drawdown label** becomes `20%`. These
are display assertions; none of them changes meaning.

**Code:**

```python
# test_backtest_metrics.py:126
        ("Max drawdown ≤ 20%", "7.9%"),
```

```python
# test_backtest_report.py:310
    for label in ("≥ 3 months forward", "≥ 100 trades", "Beats SPY", "Profit factor ≥ 1.3", "Max drawdown ≤ 20%"):
# test_backtest_report.py:337
    assert "- Beats SPY: " in v and "- Profit factor ≥ 1.3: " in v and "- Max drawdown ≤ 20%: " in v
```

```python
# test_backtest_tuning.py:159
    assert [c.label for c in v.checks] == ["Beats SPY", "Profit factor ≥ 1.3", "Max drawdown ≤ 20%"]
# test_backtest_tuning.py:184
    assert "fails on beating total-return SPY, profit factor ≥ 1.3 and max drawdown ≤ 20%;" in v3.sentence
```

```python
# test_backtest_wf_report.py:351
    assert "max drawdown ≤ 20% and profit factor ≥ 1.3" in md
```

```python
# test_backtest_dev_report.py:542
    assert any(t and t.startswith("max drawdown 20%") for t in texts)
# test_backtest_dev_report.py:579
    assert "- Max drawdown ≤ 20%." in text and "- Profit factor ≥ 1.3." in text and "- ≥ 100 closed trades." in text
```

**Impact:** None beyond keeping the suite green.

---

### Step 10: Engine tests — the boundary cases that genuinely change
**Files:** `engine/tests/test_backtest_dev.py`, `test_backtest_tuning.py`,
`test_backtest_walkforward.py`, `test_backtest_b_walkforward.py`, `test_lab_test_window.py`

**Change:** these assert that a specific drawdown *fails*. At 20% several of those values now
pass, so each boundary moves. Per **Decision 2**, the expected label text is referenced
symbolically so no `15%` literal survives while `FAILURE_LABELS` itself is left to phase 4.

**Code (a)** — `test_backtest_dev.py`, add near the other imports (the file already imports
`FAILURE_LABELS`; confirm and reuse):

```python
# The recorded drawdown-miss label. Its text still reads "15%" because `trials.failed` is
# append-only and all 110 committed rows carry that exact string; phase 4 re-derives the
# condition from the numeric `max_drawdown` column. The *threshold* is tuning.MAX_DRAWDOWN.
_DD_MISS = FAILURE_LABELS[1]
```

then the parametrize block and the two cases below it:

```python
@pytest.mark.parametrize("kw, failed", [
    (dict(), ()),
    (dict(dd=MAX_DRAWDOWN), ()),
    (dict(dd=math.nextafter(MAX_DRAWDOWN, 1)), (_DD_MISS,)),
    (dict(dd=None), (_DD_MISS,)),
    (dict(pf=1.3), ()),
    (dict(pf=1.2999), ("PF >= 1.3",)),
    (dict(pf=math.inf), ()),
    (dict(pf=None), ("PF >= 1.3",)),
    (dict(trades=100), ()),
    (dict(trades=99), (">= 100 trades",)),
    (dict(total_return=0.4), ("beats SPY TR",)),  # equal is not beating
    (dict(total_return=0.4000001), ()),
    (dict(total_return=None), ("beats SPY TR",)),
    (dict(dd=0.25, trades=10), (_DD_MISS, ">= 100 trades")),
])
def test_eligibility_boundaries(kw, failed):
    r = row("B-1", **kw)
    assert r.failed == failed
    assert r.eligible is (failed == ())
    assert r.beats_spy is ("beats SPY TR" not in failed)
```

> `MAX_DRAWDOWN` must be imported: `from seer_engine.backtest.tuning import MAX_DRAWDOWN`.
> `math.nextafter(MAX_DRAWDOWN, 1)` replaces the old hand-written `0.1500001` and keeps the
> boundary exact for any future value — the old `0.15` / `0.1500001` pair becomes
> `MAX_DRAWDOWN` / the next float up, which is strictly better than respelling `0.2000001`.

**Code (b)** — `test_backtest_dev.py:489`, the threshold-provenance test. The manual restore to
`0.15` becomes a captured value, so the test spells no threshold at all:

```python
def test_thresholds_come_from_tuning(monkeypatch):
    real_max_dd = tuning.MAX_DRAWDOWN
    assert row("T-1").eligible
    monkeypatch.setattr(tuning, "MAX_DRAWDOWN", 0.05)
    assert row("T-1").failed == (_DD_MISS,)
    monkeypatch.setattr(tuning, "MAX_DRAWDOWN", real_max_dd)
    monkeypatch.setattr(tuning, "MIN_PROFIT_FACTOR", 2.0)
    assert row("T-1").failed == ("PF >= 1.3",)
```

**Code (c)** — `test_backtest_dev.py:529`, the finalists fixture. `dd=0.20` now **passes**, which
would make `F4-X` eligible and change the expected finalist list. Push it clear of the bar:

```python
        row("F4-X", "F4", cagr=0.30, dd=0.25),  # MAR 1.2 but DD over the bar: not eligible
```

> `cagr=0.30, dd=0.25` gives MAR 1.2, which ties `F1-A`/`F1-B`. Ineligible rows are filtered
> before ranking, so the tie never arises and `["F1-A", "F2-X", "F3-X"]` still holds. Re-run the
> test to confirm rather than trusting this note.

**Code (d)** — `test_backtest_tuning.py:170`:

```python
    assert gate(M(0.40, dd=math.nextafter(MAX_DRAWDOWN, 1)), spy(0.35)).passed is False
```

**Code (e)** — `test_backtest_walkforward.py:648,659`:

```python
        (M(0.80, pf=1.5, dd=math.nextafter(MAX_DRAWDOWN, 1)), "max drawdown ≤ 20%"),
        …
    assert gate_p3b(M(0.80, pf=1.3, dd=MAX_DRAWDOWN), SPY_TR, WF_START, WF_GATE_END).passed  # inclusive thresholds
```

and `:638`, the failure sentence: `"… and max drawdown ≤ 20%; "`.

**Code (f)** — `test_backtest_b_walkforward.py:595,608` and the `:585` sentence: the identical
three edits against `gate_p6a` / `GATE_START, GATE_END, B`.

**Code (g)** — `test_lab_test_window.py:327`:

```python
    assert _test_row(c, dd=0.25).failed == (dev.FAILURE_LABELS[1],)  # "max DD <= 20%" (D13)
```

> The label literal stays here on purpose (Decision 2): this asserts what gets **written** into
> `trials.failed`, and that string is append-only history phase 4 owns. The drawdown value moves
> from `0.16` to `0.25` because `0.16` now passes.

**Impact:** The suite pins the new bar at both edges — `MAX_DRAWDOWN` passes, the next float up
fails — in the dev row, the P3 gate, the P3b gate, the P6a gate and the lab's test window.

---

### Step 11: The engine's snapshot gate assertion
**File:** `engine/tests/test_lab_snapshot.py:170`

**Change:** one value in the gate dict.

**Code:**

```python
    assert s["gate"] == {"maxDrawdown": 0.20, "minProfitFactor": 1.3, "minTrades": 100, "dsrMin": 0.95,
                         "devStart": "1993-01-29", "devEnd": "2015-10-16", "testStart": "2015-10-19"}
```

> **Collision.** Phase 4 changes `"dsrMin": 0.95` -> `0.90` on this same line and phase 7 adds gate
> keys to this same dict. `LABELS` at `:28` — which contains `"max DD <= 15%"` and `"DSR >= 0.95"`
> — is **not** touched here (Decision 2); phase 4 owns the `DSR` entry.

**Impact:** Proves `store.snapshot` publishes the new bar without `store.py` changing.

---

### Step 12: The web's single definition
**File:** `web/lib/golive.ts` — **new file**

**Change:** create it.

**Code:**

```ts
/**
 * The go-live thresholds the web judges against (design §1), spelled once.
 *
 * The engine owns these numbers. `MAX_DRAWDOWN` is `backtest.metrics.MAX_DRAWDOWN`, re-exported
 * there as `backtest.tuning.MAX_DRAWDOWN`, and it reaches the web twice over: here, for the
 * leaderboard's six-rule checklist in `lib/metrics.ts`, and in `data/lab.json`'s
 * `gate.maxDrawdown`, written by `lab.store.snapshot`. `golive.test.ts` asserts the two are the
 * same number, so an engine change that is not mirrored here fails the build rather than leaving
 * the leaderboard judging at a bar the engine abandoned.
 *
 * Why not read `data/lab.json` directly: `lib/metrics.ts` is reached from the leaderboard's app
 * code, and importing the lab snapshot outside a server component ships the whole lab to the
 * browser (see the warning at the top of `lib/sera/lab.ts`). Pages that already hold a snapshot
 * must read `gate.maxDrawdown` from it instead of importing this -- `app/sera/how/view.ts` is
 * the model.
 *
 * Raised 0.15 -> 0.2 by the owner on 2026-10-07; design §11 records the revision.
 */
import { pct } from './format';

export const MAX_DRAWDOWN = 0.2;

/** Built from the threshold so the label can never name a number the comparison does not use. */
export const MAX_DRAWDOWN_LABEL = `Max drawdown ≤ ${pct(MAX_DRAWDOWN, 0)}`;
```

**Impact:** New module, no importers yet.

---

### Step 13: The web leaderboard's checklist reads it
**File:** `web/lib/metrics.ts:1` and `:74,76`

**Change:** import `golive` and replace both literals. **This is the fix the brief calls "THE
IMPORTANT ONE"** — `web/lib/metrics.ts` is a second, independent implementation of go-live #4 in
TypeScript that never reads the engine, so without it the leaderboard would keep judging every
strategy at 15% while the engine judged at 20%.

**Code (a)** — extend the imports at the top of the file:

```ts
import type { Gate } from './strategy';
import { MAX_DRAWDOWN, MAX_DRAWDOWN_LABEL } from './golive';
```

**Code (b)** — replace the fifth `CheckItem` in `checklist` (currently `:72`–`:77`):

```ts
    {
      label: MAX_DRAWDOWN_LABEL,
      val: m.maxDrawdown === null ? '—' : (m.maxDrawdown * 100).toFixed(1) + '%',
      ok: m.maxDrawdown !== null && m.maxDrawdown <= MAX_DRAWDOWN,
    },
```

**Impact:** The leaderboard's go-live checklist moves to 20% in both its label and its verdict.

---

### Step 14: Pin the web constant to the engine's snapshot
**File:** `web/lib/golive.test.ts` — **new file**

**Change:** create the cross-language agreement test.

**Code:**

```ts
import { describe, expect, it } from 'vitest';
import { MAX_DRAWDOWN, MAX_DRAWDOWN_LABEL } from './golive';
import { lab } from './sera/lab';

describe('go-live thresholds', () => {
  it('matches the engine constant that the committed lab snapshot carries', () => {
    // `data/lab.json`'s gate is written by `lab.store.snapshot` from `tuning.MAX_DRAWDOWN`.
    // If this fails, the engine moved the bar and `lib/golive.ts` did not follow: the
    // leaderboard would judge every strategy at a threshold the engine no longer uses.
    expect(MAX_DRAWDOWN).toBe(lab.gate.maxDrawdown);
  });

  it('labels the threshold it actually compares against', () => {
    expect(MAX_DRAWDOWN_LABEL).toBe('Max drawdown ≤ 20%');
  });
});
```

**Impact:** The VERIFY item "the web leaderboard and the engine agree on the bar, proven by a test
that reads both" is satisfied. This test **fails until Step 15 lands** — they go in together.

---

### Step 15: The committed lab snapshot's gate
**File:** `web/data/lab.json` — the `gate` object

**Change:** one value. The file is minified JSON on a single line; do **not** round-trip it through
a JSON formatter, which would rewrite the whole file and make the diff unreviewable (and would
collide catastrophically with phases 4 and 7).

**Code:** a single exact-text replacement.

```
"gate":{"maxDrawdown":0.15,"minProfitFactor":1.3,"minTrades":100,"dsrMin":0.95,"devStart":"1993-01-29","devEnd":"2015-10-16","testStart":"2015-10-19"}
```
becomes
```
"gate":{"maxDrawdown":0.2,"minProfitFactor":1.3,"minTrades":100,"dsrMin":0.95,"devStart":"1993-01-29","devEnd":"2015-10-16","testStart":"2015-10-19"}
```

> `0.2`, not `0.20` — `json.dumps(0.20)` emits `0.2`, so this is what phase 7's regeneration will
> produce and the diff must match it. Verify afterwards with
> `python3 -c "import json;print(json.load(open('web/data/lab.json'))['gate'])"`.

**Impact:** `lab.gate.maxDrawdown` is `0.2`, so every `/sera` page that reads the gate — the
pass-zone shading, the hurdle targets, the method pages' limit line — moves to 20% with no further
code change. Step 14's test passes.

---

### Step 16: Web test fixtures and expectations
**Files:** `web/lib/sera/fixture.ts`, `web/app/sera/overview.test.ts`,
`web/app/sera/how/view.test.ts`, `web/lib/sera/derive.test.ts`,
`web/app/sera/methods/view.test.ts`, `web/lib/metrics.test.ts`

**Change:** the shared `GATE` fixture, the inline snapshot gate, and every expectation derived from
them. **Read the collision table before editing — phase 7 edits `dsrMin` in four of these six
files, on adjacent or identical lines.**

**Code (a)** — `web/lib/sera/fixture.ts:4`–`:12`, quoted **as it will look after phase 7** (phase 7
owns the `dsrMin` line; this phase owns only `maxDrawdown`):

```ts
export const GATE: Gate = {
  maxDrawdown: 0.2,
  minProfitFactor: 1.3,
  minTrades: 100,
  dsrMin: 0.9,
  devStart: '1993-01-29',
  devEnd: '2015-10-16',
  testStart: '2015-10-19',
};
```

> If this phase lands first, write `dsrMin: 0.95` and leave it; phase 7 changes it. If phase 7
> landed first, change only `maxDrawdown`.

**Code (b)** — `web/app/sera/overview.test.ts:86`–`:94`, likewise after phase 7:

```ts
  gate: {
    maxDrawdown: 0.2,
    minProfitFactor: 1.3,
    minTrades: 100,
    dsrMin: 0.9,
    devStart: '1993-01-29',
    devEnd: '2015-10-16',
    testStart: '2015-10-19',
  },
```

and the two assertions in the pass-zone test (`:155`–`:166`):

```ts
  it('shades the pass zone from the gate and keeps it visible', () => {
    const l = landing(snap());
    expect(l.regions[0]).toMatchObject({ x1: 0.2, y0: 0, label: 'Pass zone' });
    expect(l.refY[0].value).toBe(0);
    expect(l.yDomain[1]).toBeGreaterThan(0);
    // H-B (fall 19%, +0.9pp a year over SPY) enters the pass zone at the 20% bar; at 15% only
    // M0001-C4 was inside. This is the owner's 2026-10-07 change, seen on the landing chart.
    expect(l.inZone).toBe(2);
    const base = snap();
    const none = landing({ ...base, trials: base.trials.filter(t => t.n === 1) });
    expect(none.yDomain[1]).toBeGreaterThan(0);
  });
```

> `inZone` counts dev rows with `dd <= gate.maxDrawdown && ex > 0`. The fixture's trial 2 (`H-B`,
> `maxDrawdown: 0.19`, `cagr: 0.098` vs `spyTrCagr: 0.089`) crosses in. `bestBeat` at `:181`–`:182`
> is **unaffected**: `H-B`'s excess is 0.009, below trial 4's 0.011, so it stays `n: 4`. Leave
> those two lines alone.

**Code (c)** — `web/app/sera/how/view.test.ts:57`–`:66`. Both this phase and phase 7 rewrite these
lines; shown after both, with **Decision 4** applied to the `loose` override:

```ts
    expect(st[3].detail.join(' | ')).toBe(
      'Beat SPY + dividends | Worst fall ≤ 20% | PF ≥ 1.3 · 100+ trades | No owner inputs | Luck check ≥ 0.9',
    );
    // The overrides must differ from GATE's own values, or this stops proving the detail line
    // is read from the gate rather than hardcoded.
    const loose = pipelineStages(snap({ gate: { ...GATE, maxDrawdown: 0.3, dsrMin: 0.8 } }));
    expect(loose[3].detail).toContain('Worst fall ≤ 30%');
    expect(loose[3].detail).toContain('Luck check ≥ 0.8');
```

> The `'Luck check ≥ 0.9'` and `dsrMin: 0.8` halves are **phase 7's**; they are written here only
> so the file is quoted as it will finally look. The `keeps every line short enough for its box`
> test at `:71`–`:77` caps each detail line at 18/26 characters — `'Worst fall ≤ 30%'` is 16, so
> it still fits.

and `:105`–`:109`:

```ts
    expect(h.map(x => x.target)).toEqual([
      'More than SPY total return', 'Max drawdown ≤ 20%', 'Profit factor ≥ 1.3', 'At least 100 trades',
      'Nothing left for the owner to decide', 'Luck check ≥ 0.9',
    ]);
```

> `:39`'s `expect(pctLabel(0.15)).toBe('15%')` is a **pure formatter test**, not a threshold.
> Leave it exactly as it is.

**Code (d)** — `web/lib/sera/derive.test.ts:39` and `:46`–`:51`:

```ts
    expect(checks[1]).toMatchObject({ value: '12.0% at worst', target: '20% or less', ok: true });
```

```ts
  it('reads targets from the gate, not constants', () => {
    // 0.3 rather than 0.2: at 0.2 the override would equal GATE and prove nothing.
    const checks = gateChecks(trial(), { ...GATE, maxDrawdown: 0.3, minProfitFactor: 1.5, minTrades: 50 });
    expect(checks[1].target).toBe('30% or less');
    expect(checks[2].target).toBe('1.5 or more');
    expect(checks[3].target).toBe('50 or more');
  });
```

**Code (e)** — `web/app/sera/methods/view.test.ts:143` and `:153`–`:156`. Line 143 is also
phase 7's (`0.90 < 0.95`); shown after both:

```ts
    expect(w.sentence).toBe(
      'Beats SPY: no (7.6% vs 7.9% a year). Max drawdown: yes (12.9% ≤ 20%). ' +
      'Profit factor: yes (2.27 ≥ 1.3). Trade count: yes (1,130 ≥ 100). ' +
      'Owner inputs: yes (none needed). ' +
      'Luck check: no (0.90 < 0.90, after 58 tries).',
    );
```

> The `Luck check` half is phase 7's and its exact wording is phase 7's to settle — at
> `dsrMin: 0.9` with `dsr: 0.9` the condition no longer misses, so phase 7 must adjust the
> fixture's `dsr` as well. **Do not guess it here**; land the `≤ 20%` half and leave the luck
> clause as this phase found it if phase 7 has not landed.

```ts
  it('flips the comparison sign on a miss', () => {
    // 0.23 rather than 0.18: the sentence says "> 20%", so the value must actually exceed 20%
    // or the rendered sentence contradicts itself.
    const t = trial({ maxDrawdown: 0.23, failed: ['beats SPY TR', 'max DD <= 15%', 'DSR >= 0.95'] });
    expect(conditionSentence('drawdown', false, t, GATE)).toBe('Max drawdown: no (23.0% > 20%).');
  });
```

> The `'max DD <= 15%'` string inside `failed` stays: it is a **recorded label** that
> `derive.conditionOk` matches by equality, and per Decision 2 its text is phase 4's.

**Code (f)** — `web/lib/metrics.test.ts:44`. `0.16` now passes the bar, so the "fails the drawdown
rule" case must exceed 20%:

```ts
    expect(checklist({ ...base, maxDrawdown: 0.21, trades: 120 }, 0.046, PASSED)[4].ok).toBe(false);
```

**Impact:** vitest green, and the gate-provenance tests still prove what they claim.

---

### Step 17: Design §1 — the owner's dated revision
**File:** `docs/plans/2026-10-03-seer-design.md:13`, `:19` and a new §11 at the end (`:138`)

**Change:** This is design §1's go-live condition #4 — the real-money bar. Record it as a dated
owner revision that **preserves the original sentence**, in the style §6 of the method-lab design
uses ("Revision 2026-10-04 (owner)"). Phase 7 owns design §3 of the *method lab* doc and must not
touch §1; §1 is this phase's.

**Code (a)** — `:13`, the preamble clause, and `:19`, item 4:

```markdown
- Benchmark: SPY buy-and-hold over the same period, net of costs.
- A strategy may trade real money only when **all** of these hold (fixed; moved only by a dated
  owner revision — see §11):
  1. ≥ 3 months of forward paper trading **and** ≥ 100 closed trades
  2. Total return beats SPY buy-and-hold over the same forward period
  3. Profit factor ≥ 1.3
  4. Max drawdown ≤ 20%  *(revised 2026-10-07; was 15% — see §11)*
  5. Passed a 10-year backtest under identical rules (quant strategies only)
```

**Code (b)** — append after §10:

```markdown
## 11. Revision 2026-10-07 (owner): the go-live drawdown bar is 20%

- **Go-live condition #4 is now "Max drawdown ≤ 20%."** The original sentence, preserved: *"4. Max
  drawdown ≤ 15%"*, written 2026-10-03 under the clause "fixed now, never moved".
- **Who and why.** The owner, on stated risk appetite: *"i am thinking of my risk appetite, and i
  think let's set the Max drawdown to 20% instead of 15%."* Asked explicitly whether this was a
  lab-screen change or the real-money bar as well, the owner chose **both**, after being told it
  is a real-money safety setting and shown what it touches.
- **What it does not change.** Conditions 1, 2, 3 and 5 are untouched. The no-real-money rule
  stands: nothing trades real money without ≥ 3 months of forward paper and ≥ 100 closed trades.
  The development/test window split, the one-look test-window rule and the lab's luck check are
  separate mechanisms and are not affected by this item.
- **Where it is implemented.** `backtest.metrics.MAX_DRAWDOWN`, re-exported as
  `backtest.tuning.MAX_DRAWDOWN`, is the one Python definition; `web/lib/golive.ts` is the one
  TypeScript definition, pinned to it by `web/lib/golive.test.ts` through `data/lab.json`'s gate.
  It decides the P3, P3b and P6a backtest gates, the dev lab's D8 drawdown condition, the
  in-sample grid's selection rule and the leaderboard's go-live checklist.
- **The clause that said "never moved"** is now "moved only by a dated owner revision". That is a
  weakening of a stated guarantee and is recorded here deliberately rather than edited away: the
  bar has moved exactly once, on this date, by the owner, on the record.
- **Measured effect on the lab's 110 recorded dev trials** (bar alone, holding everything else as
  committed): 30 trials change from missing the drawdown condition to meeting it. Two of them
  clear every other condition and have a recorded DSR above 0.90 — `M0020-W-NOSTOP` (fall 19.3%,
  CAGR +15.3%, MAR 0.79) and `M0007-N20-RAW` (fall 19.6%, MAR 0.77). `M0019-RAW20-S25` (fall
  20.7%) still misses it.
```

**Impact:** The design doc states the bar the code enforces. `docs/plans/2026-10-04-method-lab-design.md:104`
("Design §1 and the no-real-money rule are unchanged") is a **dated record of what the 2026-10-04
revision did** and stays as written — it was true then.

---

## Verification

**Build:**
```
cd engine && python -m compileall -q src/seer_engine/backtest
cd web && npm run build
```

**Tests:**
```
cd engine && pytest -q
cd web && npx vitest run
```

> Per the environment note for this repo: run engine tests with the main checkout's venv and
> `PYTHONPATH` set to `engine/src`, because the swarm's phases share one worktree.

**The sweep (the phase's own acceptance check):**
```
cd /home/miftah/.worktrees/seer/lab-luck-gate
grep -rn -e '0\.15' -e '15%' engine/src/seer_engine/backtest engine/src/seer_engine/lab/store.py
grep -rn -e '0\.15' -e '15%' web/lib web/app --include='*.ts' --include='*.tsx' | grep -v node_modules
```
Every surviving hit must fall in exactly one of these four allowed classes, and the implementer
should be able to name which for each:
1. `dev.FAILURE_LABELS[1]` and the recorded `failed` strings that quote it (Decision 2, phase 4).
2. Recorded history — `seed.py:145`, `lab/methods/m00*.py` hypotheses, `paper/roster.py` notes.
3. Unrelated `0.15` values — `registry.py:146` (a 15% **volatility** target),
   `m0019_…:152` (a 15% **stop-loss**), CSS `transition: transform 0.15s`,
   `charts.test.tsx:72,73` (arbitrary props in a chart-rendering unit test),
   `scale.test.ts:142` (a formatter test), `how/view.test.ts:39` (a formatter test).
4. `docs/backtests/*.md` and `engine/package_readme.md`'s committed verdict sentences.

**Manual check:**
- `python -c "from seer_engine.backtest import tuning, metrics; print(tuning.MAX_DRAWDOWN, metrics.MAX_DRAWDOWN, metrics.MAX_DRAWDOWN_LABEL)"`
  prints `0.2 0.2 Max drawdown ≤ 20%`.
- `python3 -c "import json;print(json.load(open('web/data/lab.json'))['gate'])"` shows
  `'maxDrawdown': 0.2`.
- The two named lab candidates, checked against the recorded columns:

```
python3 - <<'PY'
import sqlite3
from seer_engine.backtest import tuning
c = sqlite3.connect('lab/lab.sqlite')
for cid in ('M0020-W-NOSTOP', 'M0019-RAW20-S25'):
    dd, cagr = c.execute(
        "SELECT max_drawdown, cagr FROM trials WHERE candidate_id = ?", (cid,)).fetchone()
    print(f"{cid}: dd={dd:.4f} cagr={cagr:.4f} passes={dd <= tuning.MAX_DRAWDOWN}")
PY
```
must print `M0020-W-NOSTOP: dd=0.1927 cagr=0.1527 passes=True` and
`M0019-RAW20-S25: dd=0.2066 cagr=0.1425 passes=False`.

**Exit criteria:**
1. `pytest` green in `engine/`; `npm run build` and `vitest` green in `web/`.
2. The go-live drawdown threshold is spelled exactly twice in live decision code —
   `metrics.MAX_DRAWDOWN` and `web/lib/golive.ts` — and `web/lib/golive.test.ts` proves the two
   agree by reading the engine-generated `data/lab.json`.
3. `tuning.gate`, `walkforward.gate_p3b` and `b_walkforward.gate_p6a` all judge at 20%, verified
   by their boundary tests (`MAX_DRAWDOWN` passes, `math.nextafter(MAX_DRAWDOWN, 1)` fails).
4. `M0020-W-NOSTOP` (fall 19.3%) meets the drawdown condition; `M0019-RAW20-S25` (fall 20.7%)
   does not.
5. `lab/lab.sqlite` is byte-identical to `origin/main`; `store.test_looks` is unchanged at 0; no
   recorded `dsr`, `eligible`, `failed` or `n_trials_at_run` is touched.
6. Design §1 item 4 reads 20% and §11 records the owner's dated revision with the original
   sentence preserved.
7. **(D13)** `dev.FAILURE_LABELS` has five entries in the original order;
   `dev.FAILURE_LABELS[1] == f"max DD <= {tuning.MAX_DRAWDOWN:.0%}" == "max DD <= 20%"`; it still
   starts with `"max DD <= "`, and so does the historical `"max DD <= 15%"` on the 30 committed
   rows. Putting the constant back to 0.15 reproduces the old string byte-for-byte.

---

## Handoffs

### H1 — phase 4: the recorded drawdown label, and the three eligible trials

**This is the most important thing in this plan for the reconciler.** Two separate items.

**H1a — the label. CLOSED in round 2, as Decision D13: this phase moves it after all.**
`dev.FAILURE_LABELS[1]` becomes `f"max DD <= {tuning.MAX_DRAWDOWN:.0%}"` in **Step 3b**, so a
failing trial no longer records a reason naming a threshold it was not judged against. The
objection this handoff raised — that `web/lib/sera/derive.ts:66` matches
`FAILURE_LABEL.drawdown` by **exact equality**, which would make 30 committed rows render as
having *passed* — is removed by **phase 7**, which replaces that matcher with
`DRAWDOWN_FAILURE_PREFIX = 'max DD <= '` and pins it from the engine with
`test_the_web_mirrors_the_engines_drawdown_label_prefix`. Both texts read as a miss.

**Nothing is asked of phase 4 here.** Phase 4 keeps re-deriving every condition from the recorded
numeric columns and reporting the miss with the live label text, which is now the true one. Its
`is_luck_label` / `LUCK_LABEL_PREFIX` pair solves the identical problem for `DSR_LABEL`
(`"DSR >= 0.95"` -> `"DSR >= 0.90"` over 110 append-only rows) and is unaffected.

**Ordering note.** This phase is in wave 1 and phase 7 in wave 3, so between them `derive.ts`
still matches the drawdown label by equality. That window is safe: no `trials` row is written in
it, the 30 historical rows still carry the 15% literal and still match, and the site is only
rebuilt at phase 7.

**H1b — the eligibility count, which this phase changes under phase 4's feet. SETTLED: THREE.**

> **Reconciled 2026-10-07.** This section originally reported **four**, reading each trial's
> **recorded** `dsr` column. That reading is arithmetically right and was rejected on semantics.
> Decision **D11**: the gate re-evaluates every recorded DSR **at the current gate N**, never at
> the N it happened to be run under. Rung 4 — the index's Requirements table, R2: *"a trial's
> verdict is frozen at the N of its run date, so verdicts are not comparable across time and the
> leaderboard mixes bars"*. Exactly one trial disagrees between the two readings, and admitting it
> would admit a candidate for having been tried **earlier**, which is the self-deception the lab
> exists to prevent. It is also strictly more conservative and costs nothing: the re-evaluation is
> exact arithmetic on recorded data, with no backtest re-run.

Measured on the committed `lab/lab.sqlite` at `MAX_DRAWDOWN = 0.20`, `DSR_MIN = 0.90`,
`DSR_POLICY = all-trials` (N = 110), the eligible set is **three**:

| Candidate | Max fall | DSR recorded (at its N) | DSR at N = 110 | MAR | Eligible? |
|---|---|---|---|---|---|
| `M0022-W-TV14` | 12.4% | 0.9122 (N=110) | 0.9122 | 0.857 | yes — unchanged |
| `M0022-W-TV16` | 14.3% | 0.9156 (N=110) | 0.9156 | 0.816 | yes — unchanged |
| **`M0020-W-NOSTOP`** | **19.3%** | 0.9144 (N=107) | **0.9127** | **0.793** | **yes — this phase** |
| `M0007-N20-RAW` | 19.6% | 0.9138 (**N=85**) | **0.8985** | 0.768 | **no — fails the luck test** |

`M0007-N20-RAW` is the one case in the lab where the recorded number and the current bar disagree,
and it is worth a named test in phase 4 for exactly that reason: its recorded 0.9138 clears 0.90,
and it was computed at N = 85, when the lab had taken 25 fewer looks. At today's N it is 0.8985.
This phase lets it through the **drawdown** condition and the luck test keeps it out.

Phase 4's exit criterion and index D1 now read **three**, naming all three — already applied.

> **The M0011 figure, settled as Decision D8.** Both numbers are real and neither stands alone:
> `M0011-RAW20-TV14-N21` is **0.8974 recorded at its recorded N = 90** and **0.884 re-evaluated
> at today's N = 110**. The convention for the whole set: the gate always uses the re-evaluated
> value; a recorded value is quoted only when the subject is what the database holds, and is then
> always labelled *recorded*, with its N. The conclusion is unchanged under both — ineligible.

**H1c — the P7a seed trial that must not slip through. SETTLED, and the opposite way round.**

`F9-SPY200M70-MOM30` is a dev trial whose **only** recorded miss is `max DD <= 15%` (fall 19.2%,
MAR 0.635) and whose `dsr` is **NULL** by construction (`seed.py:136`). After this phase its
drawdown condition is met, so it has zero remaining owner-condition misses. **There is a second
such row this section missed:** `F3-SEC-TOP3-6M-TREND` (fall 19.5%, MAR 0.433, method
`H-P7A-F3`), whose recorded `failed` is `"max DD <= 15%; owner inputs"`.

The fix is **not** the fallback-to-recorded-`eligible` rule proposed here. Phase 4 adopted the
rule `runner.trial_rows` already applies to a new trial: **a DSR that cannot be evaluated fails
the luck test** (`if dsr is None or dsr < DSR_MIN: failed.append(DSR_LABEL)`). So both rows stay
ineligible, and each for a reason that is stated rather than inherited:

- `F9-SPY200M70-MOM30` — passes all five owner conditions at 20%; out on the luck test alone.
- `F3-SEC-TOP3-6M-TREND` — out on the luck test **and** on `owner inputs`, which is the one D8
  condition phase 4 carries from the recorded string rather than re-deriving, because it is not a
  threshold and no constant re-decides it.

Both are pinned as named tests in phase 4.

**And the Scope line this section quotes has been overridden.** The index no longer says the 54
P7a seed trials "keep their recorded verdicts forever" — on the owner's instruction (Decision
**D7**) that is now **phase 9**'s subject: `lab remeasure` gains a seed path and a batch mode that
recovers their daily moments so they get a real luck verdict. Invariant 7 binds it to writing
`trial_moments` rows only, never `trials` rows, so N does not move. Phase 4's two seed tests are
annotated as describing the pre-remeasure state, and one skips itself once those rows have
moments — so phase 9 cannot break them by running.

### H2 — phase 7: three documents now contradict this phase

- `.claude/skills/explore-and-experiment-new-method/SKILL.md:176` — the guardrail row reads
  `| "Max DD 16% is basically 15%" | Design §1 is fixed. Never edit §1/§5, `tuning` thresholds or
  the P7a registry. |`. Both halves are now wrong: 16% clears the bar, and §1 item 4 has moved.
  The rule it protects is still right in spirit (an explorer must not move the bar to fit a
  result) and should be restated as "only the owner moves §1, by a dated revision".
  `SKILL.md:86`'s worked example ("at most 13% from a peak, under the 15% limit") needs the same.
- `engine/package_readme.md` — **split the hits carefully.** Lines 1092, 1094, 1211, 1216, 1323
  and 1787 state the *rule* and must move to 20%. Lines 1147, 1240, 1349, 1350–1351 and
  1810–1813 are **committed verdict sentences from past runs** and must not be retro-edited.
- `engine/src/seer_engine/lab/prereg.py` and `docs/lab/prereg/README.md` carry no drawdown
  spelling — verified; nothing to do there for this phase's sake.

### H3 — phase 7: the final `lab stage` regeneration

Phases 4, 7 and 8 each edit a different key of `web/data/lab.json`'s `gate` object by hand.
Phase 7 should regenerate the snapshot properly at the end and confirm the result carries
`maxDrawdown: 0.2`, `dsrMin: 0.9` and phase 7's new policy keys together.

### H4 — not taken: regenerating the committed backtest reports

Steps 6–8 change the *generators* so future reports state 20%, but `docs/backtests/*.md` still
read "Max drawdown ≤ 15%". That is correct — they record what the 2026-10-02 runs were judged
against. Re-running those backtests under the new bar is a separate decision for the owner and is
explicitly **not** part of this plan set.

---

## Risks

**R1 — the gate moved for Strategies A, A2 and B, not just the lab.** Fixing `metrics.checklist`
is what makes the owner's decision real, and it is also the widest-reaching edit here: the P3, P3b
and P6a verdicts are real-money gates. All three currently read **FAILED** by wide margins (max
drawdowns of 33.3%, 29.1% and 57.6%), so no verdict actually flips — but the phase does move the
bar those verdicts are measured against, which is precisely what the owner chose.

**R2 — `tuning.qualifies` widens in-sample grid selection.** `select()` may now pick a grid run
with a drawdown between 15% and 20% that it previously rejected. Nothing is regenerated by this
phase, so no committed artifact changes; but the next Strategy A tuning run may select different
parameters than `strategies/a.py`'s frozen comment describes. The comment at `a.py:97`–`:101` is a
record of what P3 did and is left alone.

**R3 — test-fixture degeneracy.** Three "reads the gate, not constants" tests override the gate to
exactly the value it is becoming. Decision 4 moves them; if a merge resolves them back to `0.2`
they will pass while proving nothing. The reconciler should re-check those two lines after
phases 7 and 8 are both in.

**R4 — `web/data/lab.json` is a three-way hand-edit.** Minified single-line JSON merges badly.
Mitigated by making this phase's edit a single exact-text replacement and by H3's regeneration.

---

## Rollback

This phase is one commit and reverts cleanly on its own: `git revert <sha>`. It depends on no
other phase and no other phase depends on it to build.

- Reverting restores `MAX_DRAWDOWN` to 0.15 in `metrics.py`, deletes `web/lib/golive.ts` and its
  test, restores `web/lib/metrics.ts`'s literals and puts `web/data/lab.json`'s
  `gate.maxDrawdown` back to `0.15`. No data migration to undo: `lab/lab.sqlite` is never opened
  for writing, no recorded trial column is touched, and `test_looks` stays 0.
- The only non-mechanical part is design §11, which should be **struck through or annotated rather
  than deleted** if the revert is a real reversal of the owner's decision, so the record of the
  decision and its reversal both survive.
- If phase 4 has already landed on top, reverting this phase alone drops the eligible set from
  **three back to two** — only `M0020-W-NOSTOP` leaves it — without touching any recorded verdict,
  because phase 4 derives eligibility at evaluation time from the live constants.
  (`M0007-N20-RAW` was never in the set: it fails the luck test at today's N under D11, so
  reverting this phase does not remove it. The count was "four" in a draft written before D11;
  corrected in round 2.) Reverting also restores `dev.FAILURE_LABELS[1]` to `"max DD <= 15%"`
  byte-for-byte, because D13 derives it from this phase's constant.
