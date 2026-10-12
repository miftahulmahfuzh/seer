# Phase 4: M0053's amendment: the weekly brake off, and the gate off

**Plan set:** `LAB_BRAKES_AND_GATE_PLAN.md`
**Analysis:** `docs/analyzer/20261012-124247-B4K9_code_analyzer.md`
**Satisfies:** R1 (§4.1, the brakes-off variant on M0053), R2 (§4.2, the shared SPY 200-day gate interrogated on M0053)
**Depends on:** Phase 1 (the `Amendment` mechanism in `lab/method.py`, `lab/store.py`, `lab/runner.py`, `lab/prereg.py`, `lab/remeasure.py`, `--amend` on `commands/lab.py`)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab/methods`

---

## !! Phase 1's contract, as reconciled

This plan was written before `.workflows/plan/lab-brakes-and-gate/phase-1.md` existed, against the
shape the plan index's **Decisions D2 and D3** describe. **The reconciler has since aligned it to
phase 1's actual contract** (C3). One thing changed, in Step 3's `Amendment(...)` call site only:

- phase 1's `Amendment` has **five** required fields, not four —
  `Amendment(added: date, why: str, hypothesis: str, expected_failure: str, candidates: tuple[Candidate, ...])`,
  all positional-or-keyword with no defaults. This plan proposed four and omitted `why`. The call
  in Step 3 now supplies a real `why` line.
- `added` is the right keyword (this plan guessed correctly); `Method.amendments` is the right
  field name, declared **last**, after `seen_keys`, which is where Step 3 already puts it.

Steps 1 and 2 (the new params type and the new allocator) are phase-1-independent, and so are all
three digests, which do **not** include the amendment wrapper (`config_digest` reads `rules`, the
allocator `id` and `params` only — `lab/method.py:35-41`). Adding `why` therefore moved no digest.

---

## Goal

`M0053`'s method file gains a second, dated pre-registration — an `Amendment` of 2026-10-12 with
three candidates — without touching one byte of the five configurations the lab has already
recorded. Two of the three run a **new** allocator that is `WEEKLYON` with the volatility brake's
scalar removed and nothing else changed, so the exposure diagnostic's `-FULL` column stops being an
inferred re-weighting and becomes a real, pre-registered, recorded trial. The third runs the
**existing** `WEEKLYON` with the shared SPY 200-day gate switched off and every other parameter
held fixed. After this phase the file is ready for phase 5 to commit and run; nothing is run here.

## Interface Contract

**Creates** (all inside `engine/src/seer_engine/lab/methods/m0053_overnight_winners_weekly_brake.py`):

- `m0053.AMENDED` — `date(2026, 10, 12)`, the amendment's `added` date (module constant, new)
- `m0053.NoBrakeOnParams` — new frozen, slotted params dataclass; fields `inner: OnParams`,
  `pool_by: PoolBy = "total"`. **Exactly two `compare=True` fields.** The class name and the field
  list are frozen by the two digests below the moment phase 5 commits.
- `m0053.FullOvernightAllocator` — new allocator class
- `m0053.FULLON` — its single instance, `id = "M0053-NOBRAKE"`
- `m0053._check_full` — the params type guard for the new allocator
- `m0053._a` — the amendment's candidate factory (the amendment's twin of `_v`)
- `m0053.NOBRAKE_AMENDMENT` — the `Amendment` value, built with phase 1's five-field signature
  `Amendment(added=, why=, hypothesis=, expected_failure=, candidates=)` and passed to
  `Method(..., amendments=(NOBRAKE_AMENDMENT,))` as that call's **last** keyword, after
  `seen_keys` (reconciler, C3: this plan originally omitted `why`)
- `engine/tests/test_m0053_amendment.py` — new test module (6 tests)

**Candidate ids and their `config_digest`s** — computed 2026-10-12 in this session against the
committed `lab/lab.sqlite` (md5 `4a34ddb823ec88a5e86afeb5d7e1b7c9`, read through a read-only
`sqlite3` URI so the file was never migrated; md5 re-checked identical afterwards). All three are
**free**: no row of `trials` claims them. These are the digests phase 5 will see recorded:

| candidate | allocator | params | `config_digest` |
|---|---|---|---|
| `M0053-TOTON20-NOBRAKE` | `FULLON` | `NoBrakeOnParams(TOTON20)` | `d8e94b628e3fa7a7cc27260e357f70a562686b15649bbfc7dce2eb4cd78e77b6` |
| `M0053-RESON20-NOBRAKE` | `FULLON` | `NoBrakeOnParams(TOTON20, pool_by="residual")` | `150eb2516cbcb122529736c2e4c966d7fbcd6f516df6f3911488c55fd8149de1` |
| `M0053-RESON20-TV16-NOGATE` | `WEEKLYON` (unchanged) | `WeeklyOnParams(OnParams(N20_NOTREND, rank="total-overnight", pool=40), Decimal("0.16"), 21, pool_by="residual")` | `76de74aab1781b28f9494d66ead5f7e7d7d4bf4f73fe4663e51b64558bd65089` |

**Deletes:** none.
**Renames:** none.
**Signature changes:** none. No existing symbol in this file is edited.

**Requires (from earlier phases):**

1. **Phase 1 — `lab/method.py` exports `Amendment` and `Method` accepts `amendments`.**
   Confirmed by the reconciler against phase 1's own Interface Contract. This is what phase 1
   ships, and Step 3's call site below is written to it:

   ```python
   @dataclass(frozen=True)
   class Amendment:
       added: date
       why: str                            # <- this plan originally omitted it (reconciler, C3)
       hypothesis: str
       expected_failure: str
       candidates: tuple[Candidate, ...]   # 1..MAX_VARIANTS, per Decision D3
   ```

   and `Method(..., amendments: tuple[Amendment, ...] = ())` declared **last**, after `seen_keys`,
   with `Method.all_candidates()` returning the originals then each amendment's, in declaration
   order. Phase 1 also validates `added` is a `date`, that `why` / `hypothesis` /
   `expected_failure` are non-empty strings, and that `candidates` is a tuple of 1..6.

2. **Phase 1 — `MAX_VARIANTS` stays a PER-RUN cap (Decision D3).** `METHOD.candidates` keeps its
   five recorded entries and the amendment carries three of its own. A per-lifetime cap of 6 makes
   this phase impossible: 5 + 3 = 8. Phase 1 must validate each `Amendment.candidates` against
   `1 <= len <= MAX_VARIANTS` on its own, and must validate candidate-id and `config_digest`
   uniqueness **across `candidates` + every amendment** (the amendment's three digests above are
   distinct from each other and from all five recorded ones — verified).

3. **Phase 1 — the freeze test must tolerate a committed-but-unrun amendment. RESOLVED.**
   Measured today: `M0053`'s file sha is
   `2289c49024dfa7007ccc4be06b02616804cd8d8cb3e60ff1d2564bd23f020335` and
   `methods.source_sha` for `M0053` holds **exactly that value** (status `dev-eligible`). Any edit
   to this file would fail the old `test_a_method_that_ran_is_frozen` assert immediately, and D2's
   "the file hashes to the **latest** recorded sha" is not enough on its own, because the
   amendment's sha is only recorded when **phase 5** runs `lab run --amend M0053` — between this
   phase landing and phase 5 running there is no row to hash against.

   Phase 1's Step 10 now carries exactly that tolerance, and only that one: its replacement test
   `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` accepts a sha mismatch **iff**
   `runner.pending_amendment(conn, method)` resolves — i.e. the file declares an `Amendment` the
   lab has not recorded **and** every amendment it has recorded still matches its block field for
   field. The strong half — every recorded trial's configuration still digesting to its recorded
   `config_digest` — is a separate test with no window at all. Phase 1 also ships
   `test_a_committed_but_unrun_amendment_is_the_one_tolerated_sha_mismatch` as a unit proof.

   Phase 3 (M0030) depends on the same tolerance and gets it from the same place. **This was the
   single hard cross-phase dependency in the set; it is now implemented in phase 1 rather than
   assumed here.** If `test_lab_methods.py` is red after this phase lands, it is a phase 1 defect:
   report it, and do not relax the test from here.

4. **Phase 1 — `test_lab_methods.py`'s `CANDIDATES` list becomes `m.all_candidates()`.**
   Confirmed: phase 1's Step 10 does exactly that, so the smoke-window, purity, `allocatorkit`
   contract and unique-allocator-id checks cover the three new candidates lab-wide. This phase
   does **not** rely on it — Step 4's own test module runs both checks against the new allocator
   directly — so the coverage is doubled rather than conflicting.

5. **Phase 1 — every reader of "what variants does this method have" asks `all_candidates()`.**
   Confirmed and widened by the reconciler (C6): `runner`, `prereg`, `remeasure`, `real_costs`,
   `exposure`, `survivorship_check` and `commands/promote` all read `all_candidates()` after phase
   1. So `lab exposure M0053` and `lab costs M0053` will see this amendment's three variants once
   phase 5 has recorded them, rather than silently reporting only the five recorded ones.

**Leaves alone (owned by others):**

- `engine/src/seer_engine/lab/methods/m0030_spy_core_momentum_satellite.py` — Phase 3. (Both this
  phase and phase 3 **import** `N20_NOTREND` from `m0007_residual_momentum.py`; that symbol
  already exists at `m0007_residual_momentum.py:346` and **neither phase adds it**.)
- `lab/method.py`, `lab/store.py`, `lab/runner.py`, `lab/prereg.py`, `lab/remeasure.py`,
  `commands/lab.py` — Phase 1.
- `lab/gate_probe.py` and `lab gate` — Phase 2. This phase does not use it and it does not use
  the new allocator.
- `engine/tests/test_lab_methods.py` — Phase 1 (it owns every test that pins the freeze).
- `lab/lab.sqlite`, `web/data/lab.json`, `docs/backtests/` — Phase 5. **This phase runs no lab
  command and commits nothing to the database.**
- Inside this phase's own file, frozen and untouched: `WeeklyOnParams`, `WeeklyOnPrepared`,
  `WeeklyOvernightAllocator`, `WEEKLYON`, `TOTON20`, `TOTON30`, `PoolBy`, `ADDED`, `_check`,
  `_resid`, `choose`, `_basket`, `_braked`, `_v`, the five `candidates`, `hypothesis`,
  `expected_failure`, `seen_keys`, and every existing import.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/methods/m0053_overnight_winners_weekly_brake.py` | modify | docstring gets a dated amendment paragraph (after line 24); imports grow by `Amendment`, `N20_NOTREND`, `_refreshed`'s module already imported (line 48), `resid_lookback` already imported (line 44); a new section appended after line 222 (`TOTON30 = ...`) holding `AMENDED`, `NoBrakeOnParams`, `_check_full`, `FullOvernightAllocator`, `FULLON`, `_a` and `NOBRAKE_AMENDMENT`; `METHOD` (line 231) gains `amendments=(NOBRAKE_AMENDMENT,)` as its last field |
| `engine/tests/test_m0053_amendment.py` | create | 6 tests: the five recorded digests, the three new digests, the brake-is-the-only-difference equivalence, the `allocatorkit` contract, the smoke window, and the allocator-id/params-type guards |

Nothing else in the repository changes.

## Implementation Steps

### Step 1: the module docstring records the amendment, and the imports grow

**File:** `engine/src/seer_engine/lab/methods/m0053_overnight_winners_weekly_brake.py:1-67`

**Change:** append one dated paragraph to the module docstring, immediately after the
"Assumptions written before the run" paragraph that ends at line 24, keeping the closing `"""` on
line 25. Then add the two new imports. Every other import line is untouched.

**Code — the docstring paragraph to insert between line 24 and line 25:**

```
Amendment, 2026-10-12 — the brake off, and the gate off. The exposure diagnostic
(``docs/backtests/2026-10-12-exposure-diagnostic.md``, measured on the dev store 77c37d553508 with
prices 5451195fd552) re-weighted every recorded version of this book to its own picks at full size
and found the brake is the most expensive one in the lab. ``NoBrakeOnParams`` and ``FULLON`` below
make that arm a real pre-registered candidate instead of a column in a diagnostic: ``FULLON`` is
``WEEKLYON`` with ``_braked``'s scalar removed and nothing else — the basket is still chosen once a
month on the anchor date and still refreshed to today's closes every week. The brake is removed,
not the weekly cadence. They are a new params type and a new allocator rather than a field on
``WeeklyOnParams`` or a sentinel ``target_vol``, because ``registry._canon`` enumerates every
``compare=True`` field of a dataclass, so one added field would silently rewrite the
``config_digest`` of all five candidates above, which the lab has recorded.
```

**Code — the import block, lines 39-67, with the two additions (complete, final text):**

```python
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0001_momentum_own_vol_scaling import _scaled, basket_scale
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    N20_NOTREND,
    N30,
    ReturnGrid,
    build_grid,
    resid_lookback,
    residual_scores,
)
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20
from seer_engine.lab.methods.m0020_stop_with_weekly_reentry import _refreshed, anchor_date
from seer_engine.lab.methods.m0050_overnight_momentum import (
    LegGrid,
    OnParams,
    build_legs,
    leg_sums,
    on_lookback,
    targets_from_rows,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorPrepared,
    FactorRow,
    factor_rows,
    prepare_factor,
    trend_on,
)
```

(The only two edits: `from seer_engine.lab.method import Method` becomes
`import Amendment, Method` on line 37, and `N20_NOTREND` joins the `m0007` import list. Line 36,
`from seer_engine.backtest.dev import Candidate`, is unchanged and shown for position.)

**Impact:** the docstring now states why the no-brake arm is shaped the way it is. No behaviour
changes; no digest moves.

### Step 2: the new params type and the new allocator

**File:** `engine/src/seer_engine/lab/methods/m0053_overnight_winners_weekly_brake.py` — appended
immediately after line 222 (`TOTON30 = OnParams(N30, rank="total-overnight", pool=60)`) and before
the existing `_v` helper at line 225.

**Change:** add the amendment's section. `NoBrakeOnParams` carries exactly the two fields the
selection needs; `FullOvernightAllocator` is `WeeklyOvernightAllocator` with `_braked` replaced by
the bare `_refreshed`.

**Code (complete, final text):**

```python
# --------------------------------------------------------------------------- the amendment, 2026-10-12
#
# Everything above this line is frozen: the five candidates have run and the lab holds their
# config digests. `registry._canon` renders a dataclass by enumerating every `compare=True`
# field, so adding a field to `WeeklyOnParams` would rewrite all five of them. The no-brake arm
# therefore gets its own params type and its own allocator, side by side with the originals.

AMENDED = date(2026, 10, 12)


@dataclass(frozen=True, slots=True)
class NoBrakeOnParams:
    """``WeeklyOnParams`` with the brake taken out — not turned down, and not widened away.

    There is no ``target_vol`` and no ``n`` here, because with no scalar there is nothing to read a
    volatility for; a sentinel like ``Decimal("99")`` would say the same thing and be unreadable a
    year from now. ``inner`` and ``pool_by`` mean exactly what they mean on ``WeeklyOnParams``, so
    the selection helpers above — ``choose``, ``_resid`` and ``_basket`` — read this type unchanged.
    They touch ``.inner`` and ``.pool_by`` and nothing else, which is why they are shared rather
    than copied: the two params types must pick the identical basket or the comparison this
    amendment makes is not a comparison.
    """

    inner: OnParams
    pool_by: PoolBy = "total"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, OnParams):
            raise TypeError(f"inner must be OnParams, got {type(self.inner).__name__}")
        if self.inner.rank != "total-overnight":
            raise ValueError(f"inner.rank must be 'total-overnight', got {self.inner.rank!r}")
        if self.pool_by not in ("total", "residual"):
            raise ValueError(f"pool_by must be 'total' or 'residual', got {self.pool_by!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"pool_by": self.pool_by}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check_full(params: object) -> NoBrakeOnParams:
    if not isinstance(params, NoBrakeOnParams):
        raise TypeError(f"params must be NoBrakeOnParams, got {type(params).__name__}")
    return params


class FullOvernightAllocator:
    """The month's overnight-picked winners at full size: ``WEEKLYON`` without the brake's scalar.

    Exactly ``WeeklyOvernightAllocator`` minus ``_braked``'s ``_scaled(...)`` call. The basket is
    still chosen once a month on the anchor date, through the same ``trend_on`` gate, the same
    ``factor_rows`` screen and the same ``_basket``; it is still re-issued on every weekly decision
    through ``_refreshed`` — the month's weights at today's closes. **This is the brake removed,
    not the weekly cadence removed.** The exposure diagnostic's ``-FULL`` arm rescales the braked
    basket back to a full book, so it undoes the scalar and never the weekly refresh; an allocator
    that also dropped the refresh would not be the arm that diagnostic priced.

    Its ``id`` is its own, ``"M0053-NOBRAKE"``: a config digest names its allocator by id, and one
    object owns each id across the whole lab (``tests/test_lab_methods.py``).
    """

    id = "M0053-NOBRAKE"

    def lookback(self, params: Any) -> int:
        p = _check_full(params)
        need = on_lookback(p.inner)
        if p.pool_by == "residual":
            need = max(need, resid_lookback(_resid(p)))
        return need + 25  # the anchor can be a month behind data_date; no brake window to cover

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check_full(params)
        fixed = {p.inner.market}
        if p.inner.inner.trend is not None:
            fixed.add(p.inner.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check_full(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check_full(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check_full(params)
        anchor = anchor_date(data_date)
        cut = {s: h.upto(anchor) for s, h in history.items()}
        if not trend_on(cut, anchor, p.inner.inner):
            return ()
        rows = factor_rows(cut, members, anchor, p.inner.inner)
        grid = build_grid(cut, p.inner.market) if p.pool_by == "residual" else None
        basket = _basket(rows, build_legs(cut, p.inner.market), grid, anchor, p)
        return _refreshed(basket, history, data_date, None)

    def prepare(self, history: Mapping[str, History]) -> WeeklyOnPrepared:
        return WeeklyOnPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, WeeklyOnPrepared):
            raise TypeError(f"prepared must be WeeklyOnPrepared, got {type(prepared).__name__}")
        p = _check_full(params)
        anchor = anchor_date(data_date)
        if not trend_on(prepared.history, anchor, p.inner.inner):
            return ()
        rows = prepared.factor.rows_on(members, anchor, p.inner.inner)
        grid = prepared.return_grid(p.inner.market) if p.pool_by == "residual" else None
        basket = _basket(rows, prepared.leg_grid(p.inner.market), grid, anchor, p)
        return _refreshed(basket, prepared.history, data_date, None)


FULLON = FullOvernightAllocator()
NOGATE20 = OnParams(N20_NOTREND, rank="total-overnight", pool=40)  # TOTON20 with the SPY-200 gate off


def _a(suffix: str, allocator: Any, params: Any, rationale: str) -> Candidate:
    """The amendment's twin of ``_v``: same rules, same family, the amendment's date."""
    return Candidate(id=f"M0053-{suffix}", family="M0053", rules=MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=rationale, added=AMENDED,
                     owner_inputs=())
```

**Impact:** two new module-level names in the lab's allocator-id namespace (`"M0053-NOBRAKE"` —
verified free against both `REGISTRY` and every `allocator_id` recorded in `trials`), and a new
params type whose canonical text begins `NoBrakeOnParams(inner=OnParams(...),pool_by=...)`. No
existing object is read, written or re-rendered differently.

**Argument order matters and is easy to get wrong:** `_refreshed(basket, history, data_date,
stop_pct)` takes the **basket first**, unlike `_braked(history, basket, ...)` which it is replacing.
Getting it backwards raises `AttributeError: 'tuple' object has no attribute 'get'` on the prepared
path only, which the module-level smoke test does not reach — `assert_p4_identity` does. (This was
measured: the first draft of this allocator had exactly that bug in `targets_prepared`, and only
the contract check caught it.)

### Step 3: the amendment block and `METHOD`

**File:** `engine/src/seer_engine/lab/methods/m0053_overnight_winners_weekly_brake.py` — appended
after `_v` (line 228) and before `METHOD = Method(` (line 231); then `METHOD` gains one field.

**Change:** the `Amendment` value, with its own dated `why`, hypothesis and expected failure,
written before any result is seen and frozen by phase 5's commit. `why` is phase 1's one-line
summary field, for a reader who later finds two batches of trials under one id and needs to know
why the second exists; the full argument stays in `hypothesis`.

**On comparability — unlike M0030, this book is clean.** M0053's five recorded trials (167..171)
are all funded at 10,000,000 IDR plus 5,000,000 on the 25th of each month, 237 deposits, exactly
what these three amendment candidates will run at, and all eight share
`MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE` at Gotrade's real fees. The diagnostic's `-FULL` figures
quoted below were therefore measured on the same funding geometry the amendment runs under, and
the 22.4-22.8% drawdown prediction is a like-for-like one. (M0030's is not; its three recorded
trials are unfunded 20,000,000 lump sums, which is why phase 3's amendment text carries a funding
caveat this one does not need. Do not copy that caveat here — it would be false.)

**Code (complete, final text — insert between `_v` and `METHOD`):**

```python
NOBRAKE_AMENDMENT = Amendment(
    added=AMENDED,
    why="The brake sells the jumpiness that pays, and the gate is a 2008 trade this book keeps paying for",
    hypothesis=(
        "The brake sells the jumpiness that pays, and the gate is a 2008 trade this book keeps "
        "paying for. M0053's own recorded analysis already priced the first half: the weekly brake "
        "took 4.0 points off the worst fall (22.8% to 18.8% at a 16% target) and cost 4.6 points of "
        "yearly return (15.1% to 10.5%), against the roughly one point per point every other brake "
        "in this lab has cost, because the overnight book picks stocks that jump on news and a "
        "volatility brake reads that as risk in ordinary months too. That analysis closed by asking "
        "for exactly this measurement: 'the lab should check how the unbraked overnight book did in "
        "2009-2015. If it also lost to SPY there, drop the family.' The exposure diagnostic of "
        "2026-10-12 answered it by re-weighting, not by running: with the brake off, every one of "
        "TOTON20's three targets lands on one number, 14.9% a year funded against deposit-matched "
        "SPY's 7.2% (+7.7 points), at a 22.8% worst fall, and +0.8 points a year over 2009-2015; "
        "RESON20-TV16 goes to 14.4% a year (+7.2) at a 22.4% fall and +0.5 after 2009. Those are "
        "the only two arms in the whole grid besides M0030's that are above the market after 2009. "
        "A re-weighted column is not a trial, so this amendment runs them: TOTON20-NOBRAKE and "
        "RESON20-NOBRAKE keep every pick, the monthly anchor and the weekly refresh of the five "
        "versions above, and remove only the scalar. The third candidate asks the other question. "
        "Four of the lab's five live books go to cash on the same 28.3% of decision days behind the "
        "same SPY 200-day read -- 67 of 237 monthly decisions, the identical dates -- so the +34.8 "
        "point lead all of them show in 2008 is one trade shared five ways, not five discoveries. "
        "The lab's recorded control prices that gate at +2.7 points a year gated against +1.0 "
        "ungated over the whole window, but after 2009 the gated version trails by 5.4 while the "
        "ungated one leads by 1.5. RESON20-TV16-NOGATE is the recorded headline version with "
        "N20_NOTREND in place of N20 and everything else -- pool, rank, target, window, pool_by, "
        "rules, funding -- held fixed. "
        "What I expect: both NOBRAKE arms land near 14-15% a year funded at a 22.4-22.8% worst "
        "fall, clearing beats-SPY, clearing the 1.3 profit-factor bar comfortably (the diagnostic's "
        "re-weighted arms read 2.37 and 2.02) and clearing 100 trades by an order of magnitude, and "
        "then failing the owner's 20% drawdown rule by 2.4 to 2.8 points. They are predicted "
        "INELIGIBLE, and that is the point of running them: it records, rather than infers from a "
        "diagnostic column, that the only post-2009 edge this book has exists only above the "
        "owner's risk limit. I expect the real runs to differ a little from the diagnostic's "
        "columns in fees and trade count, because with constant weights the weekly resize band "
        "fires less often than it does under a moving brake; the direction of that difference is "
        "fewer trades and slightly more return, not less. For RESON20-TV16-NOGATE I expect the "
        "ordering flip the seasonality control showed: most of the whole-window lead gone with "
        "2008's +34.8 removed, a worst fall far past 20% (the brake clamps but 2008 fell for a "
        "year, and the ungated seasonality control fell 61%), and 2009-2015 improved by roughly "
        "five points from -4.9 toward flat. Also predicted ineligible, on the same rule. "
        "Success for this amendment is not a passing version. It is three recorded answers: how "
        "much return the brake really costs when it is removed rather than re-weighted, whether "
        "the unbraked book's post-2009 edge survives a real run, and how much of this family's "
        "whole-window record is the shared gate's one year."
    ),
    expected_failure=(
        "The most likely outcome is that all three fail, and two of them fail in the way written "
        "above: 22.4-22.8% against a 20% bar is not close, and no version here is built to pass. "
        "**No intermediate brake target is added, and none will be.** TV20 or TV22 might squeak a "
        "version under 20%, and looking for one after seeing these numbers is precisely what design "
        "section 4 forbids -- never tune after seeing a result within a method. The grid this "
        "amendment is built on is already a result; the honest move is to record what it implies "
        "and let the drawdown rule refuse it, not to search the gap between 18 and 22 for a number "
        "that passes. If the owner ever wants a braked version that clears 20%, it is a new method "
        "with a new pre-registration and a new line in the luck budget. "
        "The other ways this goes wrong. The two NOBRAKE arms may not reproduce the diagnostic's "
        "numbers at all: the diagnostic re-weighted a recorded run's snapshots, while these are "
        "fresh simulations whose weekly resize places real orders at Gotrade's real fees on a book "
        "funded 5M IDR a month, so the 0.10 USD floor lands on slices worth tens of dollars and "
        "could cost a point or more that the re-weighting never charged. If so, 14.9% becomes 13-14% "
        "and the arm is ineligible on two conditions instead of one. TOTON20-NOBRAKE is also very "
        "close to M0050-TOT-ON, the parent, which recorded 15.1% a year at a 22.8% fall on "
        "monthly-hold-frac-gotrade; it differs only in running on "
        "monthly-rank-weekly-resize-frac-gotrade, which adds weekly resize trades to hold the "
        "weights equal. If the two land on the same number, the honest reading is that this "
        "amendment has re-measured the parent at a different cadence and learned nothing new about "
        "the picks -- a real risk worth naming before the run. The NOGATE arm may fail to teach "
        "anything either: with the gate off the book is invested through 2008, the brake is the "
        "only thing standing between it and a 2008 that the ungated seasonality control took as a "
        "61% fall, and a worst fall in the thirties would swamp every other difference and leave "
        "the 2009-2015 reading as the only usable column. And the 2009-2015 improvement may simply "
        "not appear: the diagnostic's +0.5 and +0.8 are small, measured on a window whose last five "
        "years are also the lab's most complete data, and M0053's walk-forward record is already 2 "
        "of 4 folds. If the unbraked book also loses to SPY after 2009 in a real run, the recorded "
        "analysis's own instruction applies and the family should be dropped."
    ),
    candidates=(
        _a("TOTON20-NOBRAKE", FULLON, NoBrakeOnParams(TOTON20),
           "M0050-TOT-ON's selection, chosen monthly and refreshed weekly, with the brake removed"),
        _a("RESON20-NOBRAKE", FULLON, NoBrakeOnParams(TOTON20, pool_by="residual"),
           "RESON20-TV16's selection with the brake removed: the headline version's full-size arm"),
        _a("RESON20-TV16-NOGATE", WEEKLYON,
           WeeklyOnParams(NOGATE20, Decimal("0.16"), 21, pool_by="residual"),
           "RESON20-TV16 with the shared SPY 200-day gate off and everything else held fixed"),
    ),
)
```

**Change to `METHOD`:** the existing call at line 231 keeps every field exactly as it is and gains
one line. Only the last two lines of the call are edited:

```python
    seen_keys=("concept:overnight-momentum-weekly-brake", "concept:residual-overnight-momentum"),
    amendments=(NOBRAKE_AMENDMENT,),
)
```

**Impact:** `METHOD.candidates` is byte-for-byte what it was, so all five recorded digests are
untouched. `METHOD.all_candidates()` returns eight. `seen_keys` is deliberately not extended: the
amendment is the same idea, which is the whole reason it is free in the gate's N (Decision D1).

**On `NOGATE20`:** written as a named module constant rather than inline so the candidate's
rationale and the params read the same way `TOTON20` does. It is `TOTON20` with `N20_NOTREND`
substituted for `N20`; `_resid` already handles a non-`N20` inner by building
`ResidParams(N20_NOTREND, scaled=False)` (`m0053:110`), which is the same residual ranking with the
gate off, so the residual pool and the overnight sort both see the ungated screen. Verified: the
resulting `config_digest` is `76de74aab178…`, free.

### Step 4: the test module

**File:** `engine/tests/test_m0053_amendment.py` (new)

**Change:** six tests. Three of them are regression locks on the record; three prove the new
allocator does what the amendment says it does.

**Code (complete, final text):**

```python
"""M0053's 2026-10-12 amendment: the brake-off allocator, and what must not have moved.

The amendment adds a second params type and a second allocator to a method file whose five
original configurations the lab has already recorded. Two things have to be true at once and
neither is checked anywhere else:

- the five recorded candidates still digest to the exact ``config_digest`` the committed
  ``lab/lab.sqlite`` holds for them (``registry._canon`` enumerates every ``compare=True``
  field, so a field added to ``WeeklyOnParams`` would have rewritten all five silently); and
- ``FULLON`` is ``WEEKLYON`` with the brake's scalar removed and **nothing else** -- same monthly
  basket, same weekly refresh -- which is what makes the amendment's arm the exposure
  diagnostic's ``-FULL`` arm rather than a different book that resembles it.

``test_lab_methods`` drives every lab candidate generically; this module pins the two facts that
are specific to this amendment, so a future edit to either params type fails here by name.
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
from seer_engine.backtest.dev import DEV_END, run_candidate
from seer_engine.lab import store
from seer_engine.lab.method import config_digest
from seer_engine.lab.methods.m0001_momentum_own_vol_scaling import _scaled, basket_scale
from seer_engine.lab.methods.m0053_overnight_winners_weekly_brake import (
    FULLON,
    METHOD,
    NOGATE20,
    TOTON20,
    NoBrakeOnParams,
    WeeklyOnParams,
)

# Measured 2026-10-12 against the committed lab/lab.sqlite (md5 4a34ddb823ec88a5e86afeb5d7e1b7c9),
# read through a read-only sqlite3 URI so no lab command migrated it.
RECORDED: dict[str, str] = {
    "M0053-TOTON20-TV14": "3cd337abbd6c2a614e5c3f426844cde8e4f7eb78c1cc3865b8a456cc5c2a73da",
    "M0053-TOTON20-TV16": "5a5b4828aa2d79acd0c796e1c4f776a455ef44c0d80beadc37eaffe83b26d5f0",
    "M0053-TOTON20-TV18": "104311d5dc64a877edd6742d437a4c451a224423dae897f53b8bce3c5014587e",
    "M0053-TOTON30-TV16": "cc2510f542be9ebac011262812fdb04e795ab27bf5d3afcaf60bd84e03a18e1f",
    "M0053-RESON20-TV16": "f25490aec16eb1d6c69baed0e4d5598b919fb26fa8b91ba640f14888232f3356",
}

# Free in the committed database on 2026-10-12: no trials row claims any of them. Phase 5's
# `lab run --amend M0053` is what records them, and it refuses a digest that is not free.
AMENDED_DIGESTS: dict[str, str] = {
    "M0053-TOTON20-NOBRAKE": "d8e94b628e3fa7a7cc27260e357f70a562686b15649bbfc7dce2eb4cd78e77b6",
    "M0053-RESON20-NOBRAKE": "150eb2516cbcb122529736c2e4c966d7fbcd6f516df6f3911488c55fd8149de1",
    "M0053-RESON20-TV16-NOGATE": "76de74aab1781b28f9494d66ead5f7e7d7d4bf4f73fe4663e51b64558bd65089",
}

NOBRAKE_PARAMS = [NoBrakeOnParams(TOTON20), NoBrakeOnParams(TOTON20, pool_by="residual")]

# (no-brake params, the braked params whose only difference is the scalar)
PAIRS = [
    (NoBrakeOnParams(TOTON20), WeeklyOnParams(TOTON20, Decimal("0.16"), 21)),
    (NoBrakeOnParams(TOTON20, pool_by="residual"),
     WeeklyOnParams(TOTON20, Decimal("0.16"), 21, pool_by="residual")),
]


@pytest.fixture(scope="module")
def market():
    return smoke_market(set(FULLON.symbols(NOBRAKE_PARAMS[0])))


def _by_id() -> dict[str, object]:
    return {c.id: c for c in METHOD.all_candidates()}


def test_the_five_recorded_candidates_still_digest_to_what_the_lab_holds():
    found = _by_id()
    for cid, digest in RECORDED.items():
        assert cid in found, f"{cid} is gone from METHOD"
        assert config_digest(found[cid]) == digest, (
            f"{cid}'s configuration moved; the lab has a trial on the old digest and "
            "prereg.check_digest, remeasure and `lab costs` all read it"
        )


def test_the_recorded_digests_match_the_committed_database():
    """The constants above are a copy of the record; this proves the copy is still true."""
    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT candidate_id, config_digest FROM trials WHERE method_id = 'M0053'"
        ).fetchall()
    finally:
        conn.close()
    assert {cid: d for cid, d in rows} == RECORDED


def test_the_amendment_carries_the_three_pre_registered_configurations():
    found = _by_id()
    assert len(METHOD.candidates) == 5
    assert len(METHOD.all_candidates()) == 8
    for cid, digest in AMENDED_DIGESTS.items():
        assert cid in found, f"{cid} is missing from the amendment"
        assert config_digest(found[cid]) == digest, (
            f"{cid}'s configuration is not the one that was checked free against the committed "
            "database; re-check it before phase 5 commits"
        )
    assert found["M0053-RESON20-TV16-NOGATE"].params == WeeklyOnParams(
        NOGATE20, Decimal("0.16"), 21, pool_by="residual"
    )
    assert NOGATE20.inner.trend is None, "the NOGATE arm must have no SPY-200 gate"
    assert TOTON20.inner.trend == ("SPY", 200), "the NOBRAKE arms keep the gate"


def test_the_brake_is_the_only_difference(market):
    """WEEKLYON's targets are exactly FULLON's, scaled by the basket's own brake."""
    members = everyone({s: market.history[s] for s in MEMBER_STOCKS})
    nonempty = 0
    for d in dates.sessions(date(2013, 1, 1), DEV_END)[::17]:
        for nb, wk in PAIRS:
            full = FULLON.targets(market.history, members(d), d, frozenset(), nb)
            braked = WEEKLYON.targets(market.history, members(d), d, frozenset(), wk)
            scale = basket_scale(market.history, full, d, wk.n, wk.target_vol)
            assert braked == _scaled(full, scale), f"{d}: the two allocators chose different baskets"
            nonempty += 1 if full else 0
    assert nonempty > 0, "every probe returned no targets, so this proved nothing"


def test_the_new_allocator_passes_the_contract(market):
    sessions = dates.sessions(date(2014, 12, 1), DEV_END)
    probe = sessions[::40]
    held_sets = [frozenset(), frozenset(MEMBER_STOCKS[:2]) & frozenset(market.history)]
    members = everyone({s: market.history[s] for s in MEMBER_STOCKS})
    nonempty = assert_p4_identity(FULLON, market.history, members,
                                  [dates.prev_session(s) for s in probe], held_sets, NOBRAKE_PARAMS)
    nonempty += assert_no_lookahead(FULLON, market.history, members, probe, held_sets, NOBRAKE_PARAMS)
    assert nonempty > 0, "every probe returned no targets, so the contract check proved nothing"


def test_every_amended_candidate_runs_a_smoke_window(market):
    amount = Decimal("1.0300")
    amended = {c.id for c in METHOD.all_candidates()} - {c.id for c in METHOD.candidates}
    assert amended == set(AMENDED_DIGESTS)
    found = _by_id()
    for cid in sorted(amended):
        result, row = run_candidate(market, {"SPY": {SPY_EX_DATE: amount}},
                                    (Dividend(SPY_EX_DATE, amount),), found[cid])
        assert row.end == DEV_END
        assert len(result.snapshots) >= 2


def test_the_new_params_type_refuses_what_it_cannot_run():
    with pytest.raises(TypeError):
        NoBrakeOnParams(TOTON20.inner)              # a FactorParams where an OnParams belongs
    with pytest.raises(ValueError):
        NoBrakeOnParams(OnParams(TOTON20.inner, rank="overnight", pool=40))
    with pytest.raises(ValueError):
        NoBrakeOnParams(TOTON20, pool_by="whatever")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        FULLON.lookback(WeeklyOnParams(TOTON20, Decimal("0.16"), 21))
```

The import list needs `WEEKLYON` and `OnParams` too; the final import block is:

```python
from seer_engine.lab.methods.m0050_overnight_momentum import OnParams
from seer_engine.lab.methods.m0053_overnight_winners_weekly_brake import (
    FULLON,
    METHOD,
    NOGATE20,
    TOTON20,
    WEEKLYON,
    NoBrakeOnParams,
    WeeklyOnParams,
)
```

**Impact:** `test_the_five_recorded_candidates_still_digest_to_what_the_lab_holds` is plan
invariant 3 made executable for this file; `test_the_brake_is_the_only_difference` is the claim the
amendment's hypothesis makes, made executable.

**Measured, not assumed:** every one of these six behaviours was run in this session against a
scratch copy of the Step 2 allocator (same code, same imports) on `labkit.smoke_market`, using the
main checkout's venv and the worktree on `PYTHONPATH`. `assert_p4_identity` + `assert_no_lookahead`
returned **16 non-empty cases**; the equivalence test found **10 non-empty cases**; both smoke
windows reached `DEV_END` (195 and 48 snapshots). `test_the_amendment_carries_...` depends on
phase 1's `all_candidates()` and was checked only for its digests, which were computed directly.

## Verification

Run every command from the worktree root. **Nothing here touches `lab/lab.sqlite`, and no `lab`
subcommand is run at all** — a lab command migrates the database on connect even for a read, and
phase 5 owns the database. The one test that opens it uses a read-only `sqlite3` URI.

**Build (import and validate the method, which runs `Method.__post_init__`):**

```bash
cd /home/miftah/.worktrees/seer/lab-brakes-and-gate
PYTHONPATH=/home/miftah/.worktrees/seer/lab-brakes-and-gate/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -c \
  "from seer_engine.lab.method import discover; m,_ = discover()['M0053']; \
   print(len(m.candidates), len(m.all_candidates()), [c.id for a in m.amendments for c in a.candidates])"
```

Expected: `5 8 ['M0053-TOTON20-NOBRAKE', 'M0053-RESON20-NOBRAKE', 'M0053-RESON20-TV16-NOGATE']`

**Lint:**

```bash
/home/miftah/seer/engine/.venv/bin/ruff check engine
```

**Tests — the new module first, then the lab-method suite, then the whole suite:**

```bash
docker start seer-pg
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres

cd /home/miftah/.worktrees/seer/lab-brakes-and-gate
export PYTHONPATH=/home/miftah/.worktrees/seer/lab-brakes-and-gate/engine/src

/home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests/test_m0053_amendment.py -q
/home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests/test_lab_methods.py engine/tests/test_registry.py -q
/home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests -q
```

`PYTHONPATH` is not optional: without it pytest silently tests the **main checkout**, not this
branch. CI fails if the DB tests skip, so Postgres must be up before the full run.

**Manual check — the committed database was not touched:**

```bash
cd /home/miftah/.worktrees/seer/lab-brakes-and-gate
md5sum lab/lab.sqlite   # must still be 4a34ddb823ec88a5e86afeb5d7e1b7c9
git status --porcelain  # only the two files this phase owns, plus the plan/analysis files
```

**Manual check — the three digests are still free** (re-run this if any parameter above changed):

```bash
cd /home/miftah/.worktrees/seer/lab-brakes-and-gate
PYTHONPATH=/home/miftah/.worktrees/seer/lab-brakes-and-gate/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -c "
import sqlite3
from seer_engine.lab.method import config_digest, discover
m, _ = discover()['M0053']
c = sqlite3.connect('file:lab/lab.sqlite?mode=ro', uri=True)
taken = {r[0] for r in c.execute('SELECT config_digest FROM trials')}
for a in m.amendments:
    for x in a.candidates:
        d = config_digest(x)
        print(x.id, d, 'FREE' if d not in taken else 'TAKEN -- STOP')
"
md5sum lab/lab.sqlite   # unchanged: a read-only URI never migrates
```

**Exit criteria:**

- `M0053`'s `METHOD` carries exactly one `Amendment` dated 2026-10-12 with the three candidates
  `M0053-TOTON20-NOBRAKE`, `M0053-RESON20-NOBRAKE` and `M0053-RESON20-TV16-NOGATE`, and their
  `config_digest`s are the three values pinned in the Interface Contract.
- `METHOD.candidates` still holds its five entries and each still digests to the value
  `lab/lab.sqlite` records for it, proved by two tests (one against constants, one against the
  database).
- `FULLON.id == "M0053-NOBRAKE"` and no other object in the lab or in `REGISTRY` claims that id.
- `allocatorkit`'s `assert_p4_identity` and `assert_no_lookahead` pass for `FULLON` on both params
  values with a non-zero non-empty count.
- `WEEKLYON.targets(...) == _scaled(FULLON.targets(...), basket_scale(...))` on every probed
  session for both pool modes — the brake is the only difference.
- `ruff check engine` is clean, `md5sum lab/lab.sqlite` is `4a34ddb823ec88a5e86afeb5d7e1b7c9`, and
  `pytest engine/tests` is green with Postgres up and no skipped DB tests.
- No lab command was run; `web/data/lab.json` is unchanged.

## Handoffs

- **Phase 1 — the freeze test. RESOLVED upstream.** See Interface Contract → Requires item 3.
  Editing this file would have broken the old `test_a_method_that_ran_is_frozen`, because
  `M0053`'s file sha equals its recorded `methods.source_sha` exactly. Phase 1's replacement
  accepts exactly the "pre-registered, not yet run" state, gated on `runner.pending_amendment`
  resolving. Phase 3 gets the same tolerance for M0030 from the same place. If that test is red
  after this phase lands, report it as a phase 1 defect; do not relax it here.
- **Phase 1 — `test_lab_methods.py`'s `CANDIDATES` iterates `m.all_candidates()`. CONFIRMED.**
  That extends the lab-wide purity, smoke and contract checks to the three new candidates. Not
  required by this phase, which carries its own copies.
- **Phase 2 — `lab gate`.** The gate-off transformation this phase hard-codes for one candidate
  (`N20` → `N20_NOTREND`) is what phase 2 does generically and report-only across the lab. Neither
  consumes the other; `lab gate`'s prices and this amendment's recorded trial should agree on
  `RESON20-TV16` and disagreeing would be worth a journal line in phase 5.
- **Phase 5 — the run.** `lab run --amend M0053` must be preceded by a commit of this file (the
  commit is the pre-registration; `registry_problem` refuses a dirty file). `real_costs.
  real_cost_problem` will pass: all three candidates are on
  `MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE`, which is `engine="book"`, `cost_model="gotrade"` —
  and that rule set is fractional, not bracket, so M0053's whole-share constraint does not apply
  (`sim/rules.py:209`, `is_bracket` at `sim/rules.py:264`).
- **Phase 5 — the write-up's framing.** The recorded analysis of 2026-10-09 ends: *"the lab should
  check how the unbraked overnight book did in 2009-2015. If it also lost to SPY there, drop the
  family."* The amendment is the answer to that sentence and the write-up should say so.
- **Not done, deliberately:** no intermediate brake target (TV20, TV22) is added (Decision D5);
  `seen_keys` is not extended; `METHOD.hypothesis`, `METHOD.expected_failure` and the five recorded
  candidates are not touched; no `lab` command is run; `m0050`'s parent numbers are quoted but
  `m0050_overnight_momentum.py` is not edited.
- **Measurement drift.** Every figure in the amendment's prose carries its measurement date and
  what it was measured on (plan invariant 10). The grid rows were measured on store
  `77c37d553508` / prices `5451195fd552`; if phase 5 runs on a different store fingerprint the
  predicted numbers in the hypothesis are still the pre-registration and must **not** be edited —
  the write-up records the difference instead.

## Rollback

Two files, both text, neither committed to the database:

```bash
cd /home/miftah/.worktrees/seer/lab-brakes-and-gate
git checkout -- engine/src/seer_engine/lab/methods/m0053_overnight_winners_weekly_brake.py
rm -f engine/tests/test_m0053_amendment.py
```

Or, once committed on `feature/lab-brakes-and-gate`, `git revert` this phase's commit. The revert
is clean and independent of phases 2, 3 and 6. It is **not** independent of phase 5: if phase 5 has
already run `lab run --amend M0053`, the lab holds three trials whose `config_digest`s point at a
`NoBrakeOnParams` that no longer exists, and `trials` is append-only — reverting phase 4 after
phase 5 means reverting phase 5 first (which restores the previous `lab/lab.sqlite` blob wholesale)
and re-running `lab stage` so `web/data/lab.json` agrees row for row again.
