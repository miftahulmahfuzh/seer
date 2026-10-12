> Adopted from `/home/miftah/seer/.workflows/orchestration/lab-brakes-and-gate/PLAN.md` phase 3. Source: `.workflows/plan/lab-brakes-and-gate/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: M0030's amendment: the satellite at full size, with and without the gate

**Plan set:** `LAB_BRAKES_AND_GATE_PLAN.md`
**Analysis:** `docs/analyzer/20261012-124247-B4K9_code_analyzer.md`
**Satisfies:** R1 (§4.1 — the brakes-off variant on M0030, turned into a real pre-registered
candidate), R2 (§4.2 — the shared SPY 200-day gate interrogated on this book)
**Depends on:** Phase 1 (the `Amendment` mechanism in `lab/method.py`)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab/methods`

---

## !! Read this first — the phase-1 dependency, as reconciled

This plan was written before phase 1's plan file existed, against the index's Decisions D2/D3 and
the analyzer's Impact Point 1. **The reconciler has since aligned it to phase 1's actual
contract.** The four open questions it carried are all settled; nothing below is a guess any more.

| # | What phase 1 ships | Status |
|---|---|---|
| P1-a | `Amendment` exported from `seer_engine.lab.method` | **Confirmed.** The import in Step 1 is correct as written. |
| P1-b | `Amendment(added: date, why: str, hypothesis: str, expected_failure: str, candidates: tuple[Candidate, ...])` — all five required, no defaults | **Changed.** This plan guessed `date=` and `title=`. Step 2's call below has been rewritten to phase 1's signature: `date=` → `added=`, `title=` → `why=`. The three `Candidate(...)` values are byte-identical to what was planned — they are the contract, and no digest moved. |
| P1-c | `Method(..., amendments: tuple[Amendment, ...] = ())`, declared **last**, after `seen_keys` | **Confirmed**, with the keyword moved after `seen_keys` in Step 3 to match the declaration order. |
| P1-d | **The freeze test tolerates a committed amendment that has not been run yet** | **Resolved in phase 1.** See below. |

### P1-d — resolved: phase 1 owns the pre-registration window

`engine/tests/test_lab_methods.py:113 test_a_method_that_ran_is_frozen` asserts
`source_sha(path) == methods.source_sha` for every method the committed `lab/lab.sqlite` records
as having run. M0030 has run (trials #126, #127, #128) and its file hashes to **exactly** its
recorded `source_sha` today. The moment this phase edits
`m0030_spy_core_momentum_satellite.py`, that sha changes — and phase 5, not phase 3, records the
amendment row that would make the new sha "the latest recorded sha" under D2.

So between phase 3 landing and phase 5 running there is a window in which the file legitimately
differs from every recorded sha. **Phase 1's Step 10 now accepts exactly that window**, and only
that window: its replacement test,
`test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha`, tolerates a sha mismatch if and
only if `runner.pending_amendment(conn, method)` resolves — the file declares an `Amendment` the
lab has not recorded, **and** every amendment it has recorded still matches the block it was
written from, field for field. Phase 1 also added
`test_a_committed_but_unrun_amendment_is_the_one_tolerated_sha_mismatch` as a unit proof, and an
exit criterion that the check be exercised against a real amended file before phase 1 hands off.

The second half of the freeze is unchanged and has no window:
`test_every_recorded_configuration_still_digests_to_its_recorded_digest` holds unconditionally,
and Step 4 of this phase pins the same property for M0030 independently.

**Phase 3 still does not edit `test_lab_methods.py`** — phase 1 owns it. If that test is red after
this phase lands, it is a phase 1 defect: report it, do not relax the test here. This phase's own
test file (Step 4) does not depend on it at all.

---

## Goal

`M0030`'s method file carries one `Amendment` dated 2026-10-12 with exactly three new
pre-registered candidates: the residual-momentum satellite alone at full size (`M0030-SAT100`),
the same book with the shared SPY 200-day gate removed (`M0030-SAT100-NOGATE`), and the recorded
50/50 always-on-core book with the gate off on both legs (`M0030-C50A-NOGATE`). All three
configurations are verified free against the committed `lab/lab.sqlite`, all three run and pass
the `allocatorkit` contract, and M0030's three recorded candidates still digest to the exact
`config_digest` values the lab holds for them. No lab command is run here and no trial is
recorded — phase 5 commits this file as the pre-registration and runs it.

---

## Interface Contract

**Creates:**
- `m0030_spy_core_momentum_satellite.AMENDED` — `date(2026, 10, 12)`
- `m0030_spy_core_momentum_satellite.SAT_NOGATE` — `ResidParams(N20_NOTREND, scaled=False)`
- `m0030_spy_core_momentum_satellite._a` — the amendment's `Candidate` helper (module-private)
- `m0030_spy_core_momentum_satellite.AMENDMENT_2026_10_12` — the `Amendment` value, built with
  phase 1's signature `Amendment(added=, why=, hypothesis=, expected_failure=, candidates=)`
  (reconciler, C3: this plan originally guessed `date=` / `title=`)
- `engine/tests/test_lab_m0030_amendment.py` (new file)

**The three candidate configurations phase 5 will see recorded** — these digests are the contract.
Each was computed in this session with `lab/method.config_digest` against the committed
`lab/lab.sqlite` (md5 `4a34ddb823ec88a5e86afeb5d7e1b7c9`, read-only, unchanged afterwards) and is
**free**: no recorded trial, in any window, claims it.

| candidate id | rules | allocator | `config_digest` | status |
|---|---|---|---|---|
| `M0030-SAT100` | `monthly-hold-frac` | `M0007` (`RESIDMOM`) | `542c1b9e439affc6b8faf45413c284bfbbfba8dafe67c060522288baa4a2c313` | free |
| `M0030-SAT100-NOGATE` | `monthly-hold-frac` | `M0007` (`RESIDMOM`) | `5d00ec7cafc022d5cdf734ba2f357ba21b2134f3a38ac9304c91e33ac97a7136` | free |
| `M0030-C50A-NOGATE` | `monthly-hold-frac` | `BLEND` | `b7cdc1211336dc8f137ba7beced6eb12f17b441c89a6aec1e52e9acc4ed74495` | free |

`M0030-C50A-NOGATE`'s digest was **not** pre-verified by the index (D4 says "re-check before
writing"). How it was checked, verbatim — this is the procedure to repeat if any parameter above
is ever changed:

```bash
cd /home/miftah/.worktrees/seer/lab-brakes-and-gate
md5sum lab/lab.sqlite          # 4a34ddb823ec88a5e86afeb5d7e1b7c9 before
PYTHONPATH=/home/miftah/.worktrees/seer/lab-brakes-and-gate/engine/src \
/home/miftah/seer/engine/.venv/bin/python - <<'PY'
import sqlite3
from datetime import date
from decimal import Decimal
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import config_digest
from seer_engine.lab.methods.m0007_residual_momentum import RESIDMOM, ResidParams, N20_NOTREND
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20
from seer_engine.lab.methods.m0030_spy_core_momentum_satellite import ALWAYS_SPY
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC
from seer_engine.strategies.allocator import BLEND, BlendParams, BlendPart
from seer_engine.strategies.f_index import TIMING

NOGATE = ResidParams(N20_NOTREND, scaled=False)
def c(sfx, alloc, params):
    return Candidate(id=f"M0030-{sfx}", family="M0030", rules=MONTHLY_HOLD_FRAC, allocator=alloc,
                     params=params, rationale="probe", added=date(2026, 10, 12), owner_inputs=())
probes = [
    c("SAT100", RESIDMOM, RAW20),
    c("SAT100-NOGATE", RESIDMOM, NOGATE),
    c("C50A-NOGATE", BLEND, BlendParams((BlendPart(TIMING, ALWAYS_SPY, Decimal("0.5")),
                                         BlendPart(RESIDMOM, NOGATE, Decimal("0.5"))))),
]
# read-only URI, NOT a lab command: a lab command migrates lab.sqlite on connect, even for a read
conn = sqlite3.connect("file:lab/lab.sqlite?mode=ro", uri=True)
taken = {r[0]: (r[1], r[2]) for r in conn.execute(
    "select config_digest, candidate_id, window from trials")}
for x in probes:
    d = config_digest(x)
    print(f"{x.id:22s} {d}  {'TAKEN by ' + str(taken[d]) if d in taken else 'FREE'}")
PY
md5sum lab/lab.sqlite          # must still be 4a34ddb823ec88a5e86afeb5d7e1b7c9
```

Measured output on 2026-10-12 — all three `FREE`, and `lab/lab.sqlite` byte-identical afterwards.

**Requires (from earlier phases):**
- `seer_engine.lab.method.Amendment` exists with the exact signature
  `Amendment(added: date, why: str, hypothesis: str, expected_failure: str, candidates: tuple[Candidate, ...])`
  — all five required, no defaults — and `Method` accepts `amendments: tuple[Amendment, ...] = ()`
  declared last, after `seen_keys` (Phase 1; reconciled, P1-a/b/c above)
- Phase 1's replacement freeze check tolerates a committed-but-not-yet-run amendment — its Step 10
  `pending_amendment` branch (Phase 1; reconciled, P1-d above)
- `MAX_VARIANTS` is enforced **per run**: `candidates` keeps its own 1..6 and each `Amendment`
  carries its own 1..6 (Phase 1, Decision D3). M0030 stays at 3 + 3, so even a per-lifetime cap
  of 6 would not refuse this file — but `M0053` needs the per-run reading (Phase 4).

**Does not change — these must digest to exactly what the lab has on file (invariant 3):**

| recorded candidate | trial | `config_digest` |
|---|---|---|
| `M0030-C70T` | #126 dev | `ca034400129d92f04a08cfd2160af56cce13194e05b6f3c10d6e5804838793ad` |
| `M0030-C50T` | #127 dev | `4508e558e3e859be096d8f8f1c4b861e27ae0af5fd25298c0faff617464c7d3a` |
| `M0030-C50A` | #128 dev | `acbab0edfca44c9256428d2c3df51bccc9ed509977a2b2ca6c42b26f252a97ed` |

Verified in this session: the three digests recomputed from the current file equal the three rows
the committed database holds, digit for digit. Step 4's test pins both sides.

**Deletes:** none.
**Renames:** none.
**Signature changes:** none. No `compare=True` field is added, removed or renamed on `ResidParams`,
`FactorParams`, `BlendParams`, `BlendPart` or `TimingParams`; no allocator's `id` changes.

**Leaves alone (owned by others):**
- `lab/method.py`, `lab/store.py`, `lab/runner.py`, `lab/prereg.py`, `lab/remeasure.py`,
  `commands/lab.py` (Phase 1)
- `lab/gate_probe.py` and `lab gate` (Phase 2)
- `m0053_overnight_winners_weekly_brake.py` (Phase 4)
- `m0007_residual_momentum.py`, `m0011_raw_residual_own_vol.py` — **imported, never edited**
- `engine/tests/test_lab_methods.py` and every other existing test (Phase 1)
- `lab/lab.sqlite`, `web/data/lab.json`, the write-up (Phase 5)
- M0030's own `candidates`, `hypothesis`, `expected_failure`, `TIMED_SPY`, `ALWAYS_SPY`,
  `_blend`, `_v`, `ADDED`, `seen_keys`, and the module docstring

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/methods/m0030_spy_core_momentum_satellite.py` | modify | three import lines added (`:16-27`); a new amendment block appended after `_v` (`:42`); `amendments=(AMENDMENT_2026_10_12,)` added to the existing `Method(...)` call after `seen_keys` (`:45-77`). Nothing already in the file is edited. |
| `engine/tests/test_lab_m0030_amendment.py` | create | pins both digest sets, the amendment's shape, the flat-cost exemption, the smoke run and the allocator contract |

---

## Implementation Steps

### Step 1: Import the amendment's vocabulary

**File:** `engine/src/seer_engine/lab/methods/m0030_spy_core_momentum_satellite.py:16-27`

**Change:** the file already imports `RESIDMOM` (from `m0007`) and `RAW20` (from `m0011`), both of
which the amendment reuses. It needs three more names: `Amendment` from `lab.method`,
`N20_NOTREND` and `ResidParams` from `m0007`. Nothing is removed and no existing import line
changes except by gaining names inside an existing `from … import` — the `m0007` line becomes a
parenthesised multi-name import, which is the form `m0011` and `m0053` already use.

**Code** — the complete import block, replacing lines 16-27 exactly:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20_NOTREND,
    RESIDMOM,
    ResidParams,
)
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC
from seer_engine.strategies.allocator import BLEND, BlendParams, BlendPart
from seer_engine.strategies.f_index import TIMING, TimingParams
```

**Impact:** `test_method_source_is_pure` still passes — none of the three names is in
`FORBIDDEN_IMPORT_ROOTS` and no new module root is introduced (`seer_engine.lab.method` is already
imported for `Method`). `m0007` imports nothing from `m0030`, so there is no cycle.

---

### Step 2: The amendment block

**File:** `engine/src/seer_engine/lab/methods/m0030_spy_core_momentum_satellite.py` — appended
immediately after `_v` (currently ends at `:42`) and before `METHOD = Method(` (`:45`).

**Change:** a dated, commented block carrying the amendment's own `Candidate` helper, the one new
params value, and the `Amendment` itself. The prose lives in a banner comment and in the
`hypothesis` / `expected_failure` strings, in the register of the method's originals; the module
docstring above is **not** touched, because it describes the method as it was pre-registered on
2026-10-07 and that text is frozen by its own commit.

Every figure quoted carries what it was measured on (plan invariant 10): the exposure diagnostic
of 2026-10-12, dev window 1996-01-03..2015-10-16, research store `77c37d553508`, prices
`5451195f`, committed as `docs/backtests/2026-10-12-exposure-diagnostic-grid.csv`.

**Code** — the complete block, verbatim:

```python
# --------------------------------------------------------------------------- amendment 2026-10-12
#
# The exposure diagnostic (`lab exposure`, 2026-10-12; dev window 1996-01-03..2015-10-16, research
# store 77c37d553508, prices 5451195f; committed grid docs/backtests/2026-10-12-exposure-diagnostic
# -grid.csv) re-ran each of this method's three recorded versions four ways, and one of its four
# arms -- "its own picks at full size", which drops the parked SPY holding and rescales the
# survivors to fill the book -- lands on the SAME numbers for C70T, C50T and C50A. It has to:
# dropping SPY and rescaling leaves RESIDMOM on RAW20 alone at 100% whatever the core share was.
# That arm is the strongest post-2009 reading anywhere in the grid, and it is the only reason this
# amendment exists. The three candidates below turn it into something the lab can be held to.
#
# What the grid says, so the prediction below can be read against it later:
#   M0030-C50T as recorded     12.7%/yr, lead +4.7 whole / -1.7 for 2009-2015, 18.6% worst fall
#   M0030-*-FULL (all three)   15.4%/yr, lead +7.5 whole / +2.7 for 2009-2015, 20.4% worst fall
#   the parked SPY alone        9.7%/yr, lead +1.8 whole / -5.8 for 2009-2015, 19.0% worst fall
#   share of C50T's book ever in its own picks: 35.6%
#
# EVERY FIGURE IN THAT BLOCK IS UNFUNDED. `lab exposure` re-runs each trial at its own recorded
# capital and funding, and this method's three recorded trials (126, 127, 128) were lump-sum runs
# of 20,000,000 IDR with no monthly top-up -- recorded before the lab runner was funded on
# 2026-10-08, and carrying no trial_funding row at all. The three candidates below run FUNDED, at
# today's INITIAL_IDR of 10,000,000 plus 5,000,000 on the 25th of each month (237 deposits). So
# the 20.4% worst fall is a re-weighted lump-sum number and the funded run may land either side of
# the owner's 20% bar; the hypothesis below says so before the run rather than after it. For the
# same reason these three are NOT comparable column-for-column with C70T/C50T/C50A: the honest
# comparison is money-weighted return against deposit-matched SPY. (M0053's five recorded trials
# ARE funded at 10,000,000 and its amendment is genuinely comparable -- this caveat is this
# method's alone.)
#
# SAT100 is not literally that arm: the diagnostic rescales a blend's surviving sleeve each
# decision, while SAT100 is a plain residual-momentum book from its first day. The two should land
# close; they are not required to agree digit for digit, and the hypothesis says so.

AMENDED = date(2026, 10, 12)

# RAW20 (M0007-N20-RAW's params, imported above) with the shared SPY 200-day gate switched off and
# nothing else changed: FactorParams.trend is the single read every gated book in this lab shares.
SAT_NOGATE = ResidParams(N20_NOTREND, scaled=False)


def _a(suffix: str, allocator, params, rationale: str) -> Candidate:
    """An amendment candidate: the method's own rules and flat cost, dated to the amendment."""
    return Candidate(id=f"M0030-{suffix}", family="M0030", rules=MONTHLY_HOLD_FRAC,
                     allocator=allocator, params=params, rationale=rationale, added=AMENDED,
                     owner_inputs=())


AMENDMENT_2026_10_12 = Amendment(
    added=AMENDED,
    why="The parked market money is the drag, and the gate is one year of value",
    hypothesis=(
        "Measured 2026-10-12 on the dev window with the committed research store (77c37d553508): "
        "re-running all three recorded versions of this method with the parked SPY core dropped "
        "and the satellite rescaled to fill the book gives the same result for every one of them "
        "-- 15.4% a year against deposit-matched SPY's 7.9%, a +7.5-point lead over the whole "
        "window and +2.7 a year after 2009, at a 20.4% worst fall and a profit factor of 2.11. "
        "The post-2009 figure is the strongest reading anywhere in that grid; every other arm of "
        "every other live book is behind the market over that stretch. Only 35.6% of M0030-C50T's "
        "book was ever in its own picks, and the parked market money priced on its own leads by "
        "just +1.8 over the whole window while trailing by 5.8 after 2009. On this book the core "
        "is the drag and the satellite is the edge, which is the inverse of what the dividend "
        "family turned out to be. "
        "SAT100 makes that a candidate instead of a column in a diagnostic: the residual-momentum "
        "satellite alone, filling the book, on the same monthly-hold-frac rules and the same flat "
        "0.1% cost as the three recorded versions. It should land near +15% a year, beat SPY TR "
        "comfortably, hold a profit factor near 2 and trade well over a thousand times. "
        "Every number quoted above is an UNFUNDED one, and this run will not be. The three "
        "recorded versions of this method (trials 126, 127 and 128) were lump-sum runs of "
        "20,000,000 IDR with no monthly top-up, recorded before the lab's runner was funded on "
        "2026-10-08: they carry no funding row at all. The exposure diagnostic re-runs each trial "
        "at its OWN recorded capital and funding, so the 20.4% worst fall quoted for the full-size "
        "arm is that same lump-sum geometry. These three new candidates run funded -- 10,000,000 "
        "IDR to start plus 5,000,000 IDR on the 25th of each month, 237 deposits -- which changes "
        "the shape of the equity curve a drawdown is measured on. The 20.4% is therefore a "
        "re-weighting of an unfunded book, and the funded run may land either side of the 20% bar: "
        "deposits arriving through a fall can deepen a percentage drawdown or cushion it, and "
        "nothing in the grid settles which. "
        "The prediction, stated with that caveat in front of it: SAT100 is expected INELIGIBLE on "
        "max drawdown, because the unfunded re-weighting sits 0.4 points above the limit and "
        "nothing about funding is expected to move it by much more than that -- while clearing "
        "beats-SPY, profit factor and trade count. It is a weak prediction on that one condition "
        "ON PURPOSE, and it is written weak before the run rather than sharpened after it. What "
        "is NOT weak is the reason for recording it: if the drawdown breach holds, the only "
        "post-2009 edge this lab has found is a configuration that exists only above the owner's "
        "risk limit, and the lab will hold that as a pre-registered, recorded trial rather than as "
        "an inference from a re-weighting column in a report. If it clears instead, that is a "
        "bigger finding than the one predicted and it must be reported first and loudly. "
        "Because the funding differs, SAT100's numbers must NEVER be put in the same column as "
        "C70T's, C50T's or C50A's; the comparison that is honest is money-weighted return against "
        "deposit-matched SPY, which is what the write-up will report. "
        "The two NOGATE arms ask the second question: what the shared SPY 200-day gate is worth "
        "on this book. Four of the five live books go to cash on the same 28.3% of decision days "
        "behind the same read of SPY against its 200-day average (67 of 237 monthly decisions), "
        "and that one rule produced an identical +34.8-point lead in 2008 for every one of them: "
        "one trade shared five ways, not five discoveries. The lab's own recorded control -- "
        "M0024-SAME-N20 against M0024-SAME-N20-NOTREND -- prices the gate at +2.7 a year gated "
        "against +1.0 ungated over the whole window, but after 2009 the gated version trails by "
        "5.4 while the ungated one leads by 1.5. SAT100-NOGATE is SAT100 with that gate removed "
        "and nothing else changed, so the gap between the two is the gate's price on THIS book "
        "rather than on the seasonality book. C50A-NOGATE is the recorded C50A with the gate off "
        "on BOTH legs -- the always-held core never had one, so this removes the satellite's -- "
        "and shows what the book as the owner might actually hold it looks like with nothing "
        "braking it at all. Expected: both ungated arms lead after 2009 and lose badly in 2008."
    ),
    expected_failure=(
        "The most likely outcome is the one predicted above, and it is written here before the run "
        "so the result cannot be read afterwards as a success: SAT100 misses the 20% drawdown "
        "limit by a small margin and is ineligible, so this amendment promotes nothing and is "
        "worth running only for what it records. "
        "The drawdown prediction is the WEAKEST claim in this pre-registration and that is stated "
        "here rather than discovered later. The 20.4% it rests on was measured on an unfunded, "
        "20,000,000 IDR lump-sum book -- the capital this method's three recorded trials actually "
        "had -- and SAT100 runs funded at 10,000,000 IDR plus 5,000,000 a month. A margin of 0.4 "
        "points is well inside the distance that change alone could move, in either direction. So "
        "a reading of 19.6% is NOT a refutation of this amendment's thesis and must not be "
        "reported as one, and a reading of 21% is not a confirmation of a sharp prediction; both "
        "are the same finding at a different decimal. The claim worth holding this amendment to is "
        "the one the funding does not touch: whether the satellite alone keeps a positive lead "
        "over deposit-matched SPY after 2009 when it is actually run rather than re-weighted. "
        "Beyond that, the +2.7 post-2009 reading is one stretch of one window measured once, and "
        "the satellite's whole-window lead leans on 1996-2002 (+9.7), the era where the dev "
        "store's survivorship-free coverage is thinnest. SAT100 is a plain residual-momentum book "
        "from its first day, not a blend rescaled each decision, so it need not reproduce the "
        "diagnostic arm digit for digit; if its post-2009 lead comes in materially below +2.7, "
        "then the one encouraging number in the grid was an artefact of the re-weighting and this "
        "is simply M0007-N20-RAW in fractional shares, already recorded and already short of the "
        "bar. "
        "The NOGATE arms are expected to fail harder and for a reason the lab already knows: "
        "without the gate the 2008 fall is taken in full, so both should breach 20% by a wide "
        "margin -- M0024-SAME-N20-NOTREND drew down 61.0% -- and C50A-NOGATE inherits half of "
        "SPY's roughly 55% fall on top of an ungated momentum satellite. Their verdict will most "
        "likely be that the gate buys the drawdown the owner's bar requires and costs the return "
        "he would rather have, which is a trade for him to price, not for the lab to tune away. "
        "No intermediate core split and no intermediate brake setting is in this amendment. The "
        "grid already puts every full-size arm of this method at 20.4%, so a 65/35 or an 80/20 "
        "core would be a search for the split that squeaks under 20% after the result was seen. "
        "The method lab design SS4 forbids exactly that -- never tune after seeing a result within "
        "a method -- and anything chosen that way would have to be a new variation method with its "
        "own pre-registration, not an amendment to this one. These three are fixed before the run "
        "and these three are all that will be run."
    ),
    candidates=(
        _a("SAT100", RESIDMOM, RAW20,
           "The residual-momentum satellite alone at full size: the diagnostic's best post-2009 arm, made real"),
        _a("SAT100-NOGATE", RESIDMOM, SAT_NOGATE,
           "The same book with the shared SPY 200-day gate off: what the gate costs and buys here"),
        _a("C50A-NOGATE", BLEND,
           BlendParams((BlendPart(TIMING, ALWAYS_SPY, Decimal("0.5")),
                        BlendPart(RESIDMOM, SAT_NOGATE, Decimal("0.5")))),
           "The recorded 50/50 always-held core with the gate off on both legs: nothing braking the book"),
    ),
)
```

**Impact:**
- Three new `Candidate` values exist; nothing recorded moves. `SAT_NOGATE` is a *new value* of an
  *existing* dataclass — `ResidParams` gains no field, so invariant 3 holds.
- `M0030-SAT100` reuses `RAW20` (`ResidParams(N20, scaled=False)`) unchanged, which is
  `M0007-N20-RAW`'s params verbatim. `M0007-N20-RAW` ran on `monthly-hold`; this runs on
  `monthly-hold-frac`, so the configuration is new and the digest is free (checked above).
- `ALWAYS_SPY`, `TIMED_SPY`, `_blend` and `_v` are read but not touched; `ADDED` (2026-10-07) stays
  the originals' date and `AMENDED` (2026-10-12) is the amendment's.
- `SS4` in `expected_failure` is the literal text to write: this string is passed through
  `argparse` help formatting nowhere, but the lab's report paths print it and the repo's house
  rule is to avoid non-ASCII section marks in pre-registration text that may reach a `%`-formatted
  string. If phase 1's amendment text never reaches argparse, "§4" is equally acceptable — the
  wording, not the glyph, is the pre-registration. **Do not** introduce a bare `%` anywhere in
  these two strings.

---

### Step 3: Hang the amendment on `METHOD`

**File:** `engine/src/seer_engine/lab/methods/m0030_spy_core_momentum_satellite.py:45-77`

**Change:** one keyword argument is added to the existing `Method(...)` call, after `seen_keys`
(phase 1 declares `amendments` last, after `seen_keys`). Every other argument — `id`, `name`, `family`, `source_kind`, `source_ref`,
`parent_id`, `hypothesis`, `expected_failure`, `candidates`, `seen_keys` — is byte-identical to
what is committed today.

**Code** — the complete `METHOD` assignment as it must read afterwards:

```python
METHOD = Method(
    id="M0030",
    name="Hold the market as the core and add momentum on top: an SPY core with a residual-momentum satellite",
    family="stock-core-satellite",
    source_kind="variation",
    source_ref="M0029's test look; P7a F9-SPY200M70-MOM30; M0007-N20-RAW as the satellite",
    parent_id="M0029",
    hypothesis=(
        "M0029's test look showed the 2016-2026 risk was lagging a few mega-cap leaders, not "
        "crashing. Holding SPY itself as the core owns those leaders by construction, and the "
        "residual-momentum satellite (M0007-N20-RAW, +15.0% a year on dev) adds the edge. On dev, "
        "with the SPY 200-day filter on both parts: 70% core + 30% satellite (C70T) should land "
        "near F9's +12% a year at a worst fall under 20% (F9 had 19.2% with a weaker satellite), "
        "and 50/50 (C50T) near +13% at a similar worst fall, both with a smoother ride than either "
        "part alone and so a luck score above 0.90. The always-on core (C50A, the satellite still "
        "filtered) is evidence for what the filter costs and buys: it should break the 20% limit "
        "in 2008 (SPY fell about 55%; half of that is about 27%)."
    ),
    expected_failure=(
        "A timed SPY core is F1's 200-day rule, whose dev record is a fraction of a point a year "
        "ahead of SPY with whipsaw exits; the satellite carries all of the edge, so the 70% core "
        "dilutes it to barely above SPY and the luck score falls short of 0.90. The 50/50 version "
        "inherits the momentum book's 1998 shock at half weight plus the core's whipsaws and lands "
        "near the 20% limit. C50A breaks the limit in 2008."
    ),
    candidates=(
        _v("C70T", _blend(TIMED_SPY, "0.7"), "70% SPY under its 200-day filter, 30% residual-momentum top 20"),
        _v("C50T", _blend(TIMED_SPY, "0.5"), "50% SPY under its 200-day filter, 50% residual-momentum top 20"),
        _v("C50A", _blend(ALWAYS_SPY, "0.5"),
           "50% SPY always held, 50% residual-momentum top 20 (still filtered): what the core's filter buys"),
    ),
    seen_keys=("concept:spy-core-momentum-satellite", "concept:core-satellite"),
    amendments=(AMENDMENT_2026_10_12,),
)
```

`amendments=` goes **after** `seen_keys`, matching phase 1's declaration order (`amendments` is
the last field of `Method`, declared after `seen_keys`). Both are keyword arguments so either
order runs; writing them in declaration order is what every other method file does and what phase
4 does.

**Impact:** `Method.__post_init__` must accept `amendments` (phase 1). The three recorded
candidates' `config_digest` values are unchanged — `config_text` reads only `rules`,
`allocator.id` and `params`, none of which this step touches. The file's `source_sha` changes,
which is the pre-registration phase 5 commits; see P1-d above for the test consequence.

---

### Step 4: The test that pins both digest sets

**File:** `engine/tests/test_lab_m0030_amendment.py` (new)

**Change:** a module that holds invariant 3 for M0030 independently of phase 1's freeze test, pins
the three amendment digests to the values this plan contracts, proves they are free in the
committed database, proves the flat cost is correct for this method id, and runs the smoke window
and the `allocatorkit` contract over the three new candidates so they are covered even if phase 1
leaves `test_lab_methods.py` reading `METHOD.candidates` rather than `all_candidates()`.

Measured in this session, before this plan was written: all three candidates run the smoke window
to `DEV_END` with 73 snapshots, and `assert_p4_identity` + `assert_no_lookahead` return 8, 8 and
24 non-empty probes respectively — so the `nonempty > 0` assertion below is not a guess.

**Code** — the complete file:

```python
"""M0030's 2026-10-12 amendment: the three pre-registered candidates, and what must not move.

The amendment adds candidates to a method that has already run (trials #126-#128). Two things
have to be true at once for that to be honest, and this module checks both:

- the three configurations the amendment pre-registers are **free** -- no recorded trial, in any
  window, already claims their ``config_digest`` -- so running them is a new measurement and not
  a silent re-run;
- the three configurations the lab already recorded still digest to exactly the values it holds
  on file. ``registry._canon`` enumerates every ``compare=True`` field of a params dataclass, so
  one added field would rewrite the digest of every recorded candidate that uses it and break
  ``prereg.check_digest``, ``remeasure`` and ``lab costs`` at once (plan invariant 3).

The digests below are pinned as literals on purpose. They are the plan's interface contract, and
a test that recomputed both sides from the same code would pass while the history changed under
it. The committed database is read through a read-only URI and never through a lab command,
because a lab command migrates ``lab/lab.sqlite`` on connect even for a read.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal

import pytest
from allocatorkit import assert_no_lookahead, assert_p4_identity, everyone
from labkit import MEMBER_STOCKS, SPY_EX_DATE, smoke_market

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.dev import DEV_END, candidate_owner_inputs, run_candidate
from seer_engine.lab import store
from seer_engine.lab.method import MAX_VARIANTS, config_digest
from seer_engine.lab.methods.m0007_residual_momentum import N20_NOTREND, RESIDMOM
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20
from seer_engine.lab.methods.m0030_spy_core_momentum_satellite import (
    AMENDED,
    AMENDMENT_2026_10_12,
    METHOD,
    SAT_NOGATE,
)
from seer_engine.lab.real_costs import real_cost_problem, requires_real_cost
from seer_engine.strategies.allocator import Allocator

# What the committed lab database holds for M0030 (trials #126, #127, #128), verified
# 2026-10-12 against lab/lab.sqlite md5 4a34ddb823ec88a5e86afeb5d7e1b7c9.
RECORDED: dict[str, str] = {
    "M0030-C70T": "ca034400129d92f04a08cfd2160af56cce13194e05b6f3c10d6e5804838793ad",
    "M0030-C50T": "4508e558e3e859be096d8f8f1c4b861e27ae0af5fd25298c0faff617464c7d3a",
    "M0030-C50A": "acbab0edfca44c9256428d2c3df51bccc9ed509977a2b2ca6c42b26f252a97ed",
}

# The amendment's pre-registration, computed in the same session against the same database.
AMENDMENT: dict[str, str] = {
    "M0030-SAT100": "542c1b9e439affc6b8faf45413c284bfbbfba8dafe67c060522288baa4a2c313",
    "M0030-SAT100-NOGATE": "5d00ec7cafc022d5cdf734ba2f357ba21b2134f3a38ac9304c91e33ac97a7136",
    "M0030-C50A-NOGATE": "b7cdc1211336dc8f137ba7beced6eb12f17b441c89a6aec1e52e9acc4ed74495",
}

NEW = AMENDMENT_2026_10_12.candidates


def _recorded_digests() -> set[str] | None:
    """Every config_digest the committed database holds, or None when it is not in this tree."""
    if not store.COMMITTED_DB.exists():
        return None
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    try:
        return {str(r[0]) for r in conn.execute("SELECT config_digest FROM trials")}
    finally:
        conn.close()


@pytest.fixture(scope="module")
def market():
    return smoke_market({"SPY"})


# --------------------------------------------------------------------------- the freeze


def test_the_recorded_candidates_still_digest_to_their_recorded_values():
    got = {c.id: config_digest(c) for c in METHOD.candidates}
    assert got == RECORDED


def test_the_recorded_digests_are_the_ones_the_lab_holds():
    digests = _recorded_digests()
    if digests is None:
        pytest.skip("no lab database")
    for cid, digest in RECORDED.items():
        assert digest in digests, f"{cid}: the lab no longer holds {digest}"


# --------------------------------------------------------------------------- the amendment


def test_the_amendment_is_dated_and_carries_exactly_three_candidates():
    assert AMENDED == date(2026, 10, 12)
    assert AMENDMENT_2026_10_12.added == AMENDED          # phase 1's field name (reconciler, C3)
    assert AMENDMENT_2026_10_12.why.strip()               # the one-line reason, non-empty
    assert AMENDMENT_2026_10_12.hypothesis.strip()
    assert AMENDMENT_2026_10_12.expected_failure.strip()
    assert len(NEW) == 3
    assert len(NEW) <= MAX_VARIANTS
    assert [c.id for c in NEW] == ["M0030-SAT100", "M0030-SAT100-NOGATE", "M0030-C50A-NOGATE"]
    for c in NEW:
        assert c.family == "M0030"
        assert c.added == AMENDED
        assert c.rules.id == "monthly-hold-frac"
        assert c.owner_inputs == () == candidate_owner_inputs(c)


def test_the_amendment_digests_are_the_preregistered_ones():
    assert {c.id: config_digest(c) for c in NEW} == AMENDMENT


def test_the_amendment_digests_are_free_in_the_committed_lab():
    digests = _recorded_digests()
    if digests is None:
        pytest.skip("no lab database")
    for cid, digest in AMENDMENT.items():
        assert digest not in digests, (
            f"{cid} repeats a configuration the lab has already run; an amendment must be a new "
            "measurement, not a re-run under a new name"
        )


def test_no_two_of_the_six_configurations_collide():
    everything = list(METHOD.candidates) + list(NEW)
    digests = [config_digest(c) for c in everything]
    assert len(set(digests)) == len(digests)
    assert len({c.id for c in everything}) == len(everything)


def test_the_two_satellite_arms_differ_only_by_the_gate():
    # RAW20 is M0007-N20-RAW's params; SAT_NOGATE is the same with FactorParams.trend removed.
    assert RAW20.inner.trend == ("SPY", 200)
    assert SAT_NOGATE.inner is N20_NOTREND
    assert SAT_NOGATE.inner.trend is None
    assert SAT_NOGATE.scaled is RAW20.scaled is False
    for name in ("beta_n", "mom_n", "skip", "market"):
        assert getattr(SAT_NOGATE, name) == getattr(RAW20, name)
    for name in ("rank", "top", "mom_n", "mom_skip", "vol_n", "pool", "sizing",
                 "min_dollar_volume", "min_price"):
        assert getattr(SAT_NOGATE.inner, name) == getattr(RAW20.inner, name)


def test_the_blend_arm_turns_the_gate_off_on_both_legs():
    blend = {c.id: c for c in NEW}["M0030-C50A-NOGATE"].params
    core, satellite = blend.parts
    assert core.allocator.id == "F1" and core.params.rule == "always"
    assert satellite.allocator is RESIDMOM and satellite.params is SAT_NOGATE
    assert core.share == satellite.share == Decimal("0.5")


# --------------------------------------------------------------------------- the lab's rules


def test_the_amendment_stays_at_the_lab_s_flat_cost():
    # real_costs.requires_real_cost is keyed on the METHOD ID and exempts <= M0030, so
    # runner.preflight will not refuse monthly-hold-frac here, and the new candidates stay
    # comparable with the three the lab recorded at the same flat 0.1% (Decision D7).
    assert requires_real_cost("M0030") is False
    assert requires_real_cost("M0031") is True
    assert real_cost_problem(METHOD) is None


# --------------------------------------------------------------------------- the contracts


@pytest.mark.parametrize("c", NEW, ids=[c.id for c in NEW])
def test_an_amendment_candidate_runs_a_smoke_window(market, c):
    amount = Decimal("1.0300")
    result, row = run_candidate(
        market, {"SPY": {SPY_EX_DATE: amount}}, (Dividend(SPY_EX_DATE, amount),), c
    )
    assert row.end == DEV_END
    assert len(result.snapshots) >= 2


@pytest.mark.parametrize("c", NEW, ids=[c.id for c in NEW])
def test_an_amendment_candidate_passes_the_allocator_contract(market, c):
    assert isinstance(c.allocator, Allocator)
    sessions = dates.sessions(date(2014, 12, 1), DEV_END)
    probe = sessions[::40]
    held_sets = [frozenset(), frozenset(MEMBER_STOCKS[:2]) & frozenset(market.history)]
    members = everyone({s: market.history[s] for s in MEMBER_STOCKS})
    nonempty = assert_p4_identity(
        c.allocator, market.history, members,
        [dates.prev_session(s) for s in probe], held_sets, [c.params],
    )
    nonempty += assert_no_lookahead(
        c.allocator, market.history, members, probe, held_sets, [c.params]
    )
    assert nonempty > 0, f"{c.id}: every probe returned no targets, so the check proved nothing"
```

**Impact:** the module imports `AMENDMENT_2026_10_12` and reads `.date` and `.candidates`. Those
two attribute names are the only places phase 1's field naming leaks into the test — if phase 1
named the date field `added`, change those two lines and nothing else. There is deliberately **no**
assertion on `METHOD.amendments` here, so the test file does not break if phase 1 names that field
differently; the plan index's phase-3 exit criterion ("`M0030`'s `METHOD` carries one `Amendment`")
is checked by phase 1's own `Method` validation and by phase 5's `lab run --amend M0030` finding
the candidates at all.

---

## Verification

Postgres must be up or CI fails on the skip, and `PYTHONPATH` must point at **this worktree** or
pytest silently tests `main`:

```bash
docker start seer-pg
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
export PYTHONPATH=/home/miftah/.worktrees/seer/lab-brakes-and-gate/engine/src
cd /home/miftah/.worktrees/seer/lab-brakes-and-gate
```

**Build (import + method validation):**

```bash
/home/miftah/seer/engine/.venv/bin/python -c "
from seer_engine.lab.method import discover
m, p = discover()['M0030']
print(m.id, [c.id for c in m.candidates])
print([a.date for a in m.amendments], [c.id for c in m.amendments[0].candidates])
"
```

**Lint (CI runs bugs only — E9 and F, minus F401):**

```bash
/home/miftah/seer/engine/.venv/bin/ruff check engine
```

**Tests — this phase's own file first, then the lab suite, then the whole suite:**

```bash
/home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests/test_lab_m0030_amendment.py -q
/home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests/test_lab_methods.py -q
/home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests -q
```

Baseline to re-measure, not to carry forward: the index records **4364 passed / 3 skipped** on
`main` @ `d3c1ec4` (the three skips are opt-in live-store tests). This phase adds 10 test items
(3 shape/freeze/digest + 2 parametrised × 3 candidates + the rest), so expect roughly
4364 + 12 + whatever phase 1 added.

**Manual check — `lab/lab.sqlite` must be byte-identical:**

```bash
md5sum lab/lab.sqlite    # 4a34ddb823ec88a5e86afeb5d7e1b7c9, before and after everything above
git status --short lab/ web/data/
```

Neither path may appear. **This phase runs no lab command** (`lab run`, `lab stage`, `lab test`,
`lab exposure`, `lab gate` — none of them), and a lab command migrates the database on connect even
for a read.

**Exit criteria:**

1. `discover()['M0030']` loads and `Method.__post_init__` accepts the file.
2. `M0030`'s `METHOD` carries exactly one `Amendment`, dated 2026-10-12, with the three candidates
   `M0030-SAT100`, `M0030-SAT100-NOGATE`, `M0030-C50A-NOGATE`.
3. Those three digest to `542c1b9e439a…`, `5d00ec7cafc0…`, `b7cdc1211336…` and none appears in
   `trials.config_digest`.
4. `M0030-C70T`, `M0030-C50T`, `M0030-C50A` still digest to `ca034400129d…`, `4508e558e3e8…`,
   `acbab0edfca4…` — the three values trials #126-#128 hold.
5. `real_cost_problem(METHOD) is None`, so `runner.preflight` will not refuse the flat cost.
6. Every amendment candidate runs the smoke window to `DEV_END` and passes the P4 identity and
   no-look-ahead checks with at least one non-empty probe.
7. `ruff check engine` is clean and `pytest engine/tests` is green with Postgres up.
8. `lab/lab.sqlite` and `web/data/lab.json` are untouched in `git status`.

---

## Handoffs

- **Phase 1 — the freeze check tolerates an un-run amendment. RESOLVED upstream (P1-d above).**
  This was the one cross-phase issue this phase could not resolve itself: the moment M0030's file
  is edited, the old `test_a_method_that_ran_is_frozen` would compare the new sha against
  `methods.source_sha` and fail until phase 5 records an amendment row. Phase 1's replacement,
  `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha`, accepts a mismatch **iff**
  `runner.pending_amendment` resolves, and phase 1 carries an exit criterion that the branch be
  exercised against a real amended file. Phase 3 does not touch that test. If it is red after this
  phase lands, report it as a phase 1 defect.
- **Phase 1 — `test_lab_methods.py`'s `CANDIDATES` iterates `all_candidates()`. CONFIRMED.** The
  amendment's three candidates therefore get the purity, smoke, contract and allocator-id-uniqueness
  checks for free, and the duplicated checks in Step 4 are belt and braces rather than the only
  cover. Either way Step 4 stands.
- **Phase 5 — the run, and only phase 5.** `git add` of
  `m0030_spy_core_momentum_satellite.py` is the pre-registration; it must be committed before
  `lab run --amend M0030 --store /home/miftah/seer/engine/.research`. `registry_problem` refuses an
  uncommitted or dirty file, which is the mechanism, not an obstacle. Phase 5 should expect
  `store.pending_gate(conn, 'M0030', 3) == Gate(n=74, policy='methods')` and should check the
  recorded `max_drawdown` for `M0030-SAT100` against the 20.4% this amendment predicted before
  writing a word of the write-up.
- **Phase 5 — the prediction is the headline.** If `M0030-SAT100` comes in ineligible on max
  drawdown alone, that is the pre-registered result, not a disappointment, and the write-up should
  say so in the owner's plain language: the one configuration in this lab that beat the market
  after 2009 is one he has told the lab he will not hold.
- **Phase 6 — not this phase's to raise, but worth the memo:** this amendment records a
  configuration the owner's §1 bar refuses, under a method id that has already run. Whether the lab
  should keep a standing count of how many such "above the limit" configurations it has recorded is
  a policy question for him, beside D8's finding that the `methods` policy charges nothing for an
  amendment.
- **Not done, deliberately:** M0030's module docstring is not extended to describe the amendment.
  It is the method's own pre-registration text from 2026-10-07 and is frozen by that commit; the
  amendment's prose lives in its own banner and in its `hypothesis` / `expected_failure`. If the
  reconciler decides a docstring addendum is wanted, it belongs to phase 6's documentation work,
  not here.

---

## Rollback

This phase is text-only and touches exactly two files.

```bash
cd /home/miftah/.worktrees/seer/lab-brakes-and-gate
git checkout -- engine/src/seer_engine/lab/methods/m0030_spy_core_momentum_satellite.py
rm -f engine/tests/test_lab_m0030_amendment.py
```

Or, once committed, `git revert` this phase's commit. Nothing else depends on it until phase 5
runs `lab run --amend M0030`; after that run the trials are recorded and append-only, and rolling
the amendment back would leave recorded trials whose candidates no longer exist in the file —
so **revert this phase only before phase 5 has run**. After phase 5, the amendment is a record and
stays.
