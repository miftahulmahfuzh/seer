# Phase 3: M0396 — ten never-step-aside arms, pre-registered

**Plan set:** `FLOOR_RESERVATION_YARDSTICK_PLAN.md`
**Analysis:** `docs/analyzer/20261027-082613-F3K9_code_analyzer.md`
**Satisfies:** R3 — the lab can read a timing method's bill against an arm that never steps aside
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab/methods`

---

## Goal

Ten of the thirteen timing methods the handover named gain one committed, pre-registered
never-step-aside arm — that method's own chassis with its switch, gate or brake removed, pinned to
that method's own lookback so the yardstick is scored on exactly the sessions its gated arms were.
The other three already carry one, and this phase proves that from the lab database and records the
correction rather than registering a duplicate the runner would refuse. Nothing is run: the commits
are the pre-registration, and a runbook hands the ten-command execution to a later, deliberate
session.

---

## The census, re-measured this session — READ THIS BEFORE ANYTHING ELSE

The brief and the handover both say "thirteen lack a never-step-aside arm", derived from
`max(trials.exposure) < 0.98` over `window='dev'`. **That cutoff produces false negatives**, and
three of the thirteen are among them. Measured from `file:/home/miftah/seer/lab/lab.sqlite?mode=ro`
on 2026-10-27:

| candidate | rationale, verbatim from its method file | trades | turnover | exposure | maxDD | allocator | run_at |
|---|---|---|---|---|---|---|---|
| `M0038-DIV-OPEN` | "Control: the big-dividend-raise book with no gate at all, weekly-resize rules" | 576 | 4.2962 | 0.9746 | 0.5765 | `M0076` | 2026-10-16 |
| `M0173-EXP100` | "Control: the dividend book never stepping aside for the curve watch" | 576 | 4.2962 | 0.9746 | 0.5765 | `M0173` | 2026-10-24 |
| `M0336-NEVER` | "Control: the dividend book never stepping aside for the curve" | 576 | 4.2962 | 0.9746 | 0.5765 | `M0336` | 2026-10-24 |
| `M0338-NOSW` | "no opinion: same book, switch off, always invested" | 1474 | 7.3482 | 0.9713 | 0.6087 | `M0338` | 2026-10-24 |

Three facts follow, and each one changes what this phase builds:

1. **A stock book that never steps aside still reads ~0.97 exposure.** `exposure` is
   `mean(invested / equity)` over the sessions (`backtest/book_runner.py:568, :801`), and a
   20-slot book funded by a monthly deposit always carries a little cash. The 0.98 cutoff only
   identifies a SPY-at-full-weight chassis. **M0173, M0336 and M0338 already carry an explicit
   never-step-aside arm** and must not be amended: `M0173-EXP100` is `DialParams(exposure=1)`,
   `M0336-NEVER` is `WatchParams("never")`, `M0338-NOSW` is `Params(trend=None)`.
2. **`M0038-DIV-OPEN`, `M0173-EXP100` and `M0336-NEVER` are the identical book to every recorded
   digit**, reached through three different allocator ids and run on two different dates eight days
   apart. That is also this phase's answer to the "recorded returns from different runs are not
   comparable" worry M0389 raised: on this chassis, on this store, a re-run reproduces itself
   exactly. The same holds for `M0261-NATIVE` and `M0262-NATIVE` (0.3510 / 0.1871 / 3.523 / 528
   trades, both).
3. **M0038's `div` half already has its yardstick (`DIV-OPEN`); its `spy` half does not.** The same
   `DIV-OPEN` configuration is also the yardstick for `M0039`'s and `M0167`'s `div` arms, because
   all three methods' `div` host is `AnnParams(replace(R25, inner=NOT20), "ex")` on
   `MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE` through `ANNOUNCED` — the same configuration, so
   `store.has_trial` (`lab/store.py:1320`, keyed on `config_digest` and window, **across the whole
   lab**) refuses a second registration of it by design.

**So the deliverable is TEN amendments, not thirteen**, and the three non-amendments are a measured
finding to be recorded, not an omission. **The reconciler has accepted this and the plan index now
states ten**, with the superseded figure and its reason kept beside it: thirteen by the
`exposure >= 0.98` read, ten in fact. A card built from the index therefore says ten.

### What each of the ten gets, and why that configuration is new

| # | Method | Family | Status | What its arms step aside for | The new arm | How it is made never-step-aside | Pinned lookback / window |
|---|---|---|---|---|---|---|---|
| 1 | M0038 | macro-regime-gate | dev-eligible | the 10y-13w curve watch (`spy` host) | `M0038-ALWAYS` | new allocator `M0038-ALWAYS`, no watch | 1 — `SPY-WATCH`'s own; window opens **1993-02-01** |
| 2 | M0039 | volatility-term-structure-gate | rejected | the VIX term-structure / spike gate (`spy` host) | `M0039-ALWAYS` | new allocator `M0039-ALWAYS`, no gate | 1 — `SPY-TS`/`SPY-SPIKE`'s own; **1993-02-01** |
| 3 | M0113 | market-trend-switch | rejected | the fixed 200-day exit | `M0113-ALWAYS` | new allocator `M0113-ALWAYS`, no exit | `LOOKBACK` = 253; **1994-01-28** |
| 4 | M0136 | market-trend-switch | rejected | the same fixed 200-day exit, in rungs | `M0136-ALWAYS` | new allocator `M0136-ALWAYS`, no exit | `LOOKBACK` = 253; **1994-01-28** |
| 5 | M0167 | macro-regime-gate | dev-eligible | the curve watch with an early exit (`spy` host) | `M0167-ALWAYS` | new allocator `M0167-ALWAYS`, no watch | `HIGH_N + 1` = 253; **1994-01-28** |
| 6 | M0245 | market-trend-switch | rejected | the 200-day gate with a confirmation | `M0245-ALWAYS` | new allocator `M0245-ALWAYS`, no gate | `LOOKBACK` = 327; **1994-05-17** |
| 7 | M0260 | market-trend-switch | dev-eligible | M0072's book behind a k-month-anchored SPY-200 gate | `M0260-ALWAYS` | new allocator `M0260-ALWAYS`, gate test deleted | 454; **1996-01-03** |
| 8 | M0261 | market-trend-switch | dev-eligible | M0088's book behind a (k, phase) gate grid | `M0261-ALWAYS` | new allocator `M0261-ALWAYS`, gate test deleted | 454; **1996-01-03** |
| 9 | M0262 | market-trend-switch | dev-eligible | M0088's book behind a session-count gate grid | `M0262-ALWAYS` | new allocator `M0262-ALWAYS`, gate test deleted | 454; **1996-01-03** |
| 10 | M0334 | market-trend-switch | rejected | a graded ramp out as SPY nears its 200-day line | `M0334-ALWAYS` | **the method's own dial**: `Params(flat=100)`, no new code | `max(factor_lookback(PICK), 200)`; **1996-01-03** |

Every one of the ten is `dev-eligible` or `rejected`, every one has a non-NULL `source_sha`, every
one has **0** rows in `method_amendments` and **0** `window='test'` trials — re-measured this
session — so `runner.preflight(..., amend=True)` (`lab/runner.py:261`) can refuse none of them on
status, and `pending_amendment` will resolve `amendments[0]` for each.

### The four design decisions, and why the obvious cheaper routes are wrong

**D3.1 — Each new arm runs through a NEW allocator declared in the method's own file, not through
an existing one.** The cheap route is `f_index.TIMING` with `TimingParams(hold="SPY",
signal="SPY", rule="always")` — `TIMING_RULES` carries `"always"` and it does exactly what is
wanted. It fails twice. (a) `TimingAllocator.lookback` returns **1** for `rule="always"`
(`f_index.py:286-292`), so on M0113, M0136, M0167 and M0245 the yardstick's dev window would open
eleven to sixteen months before the arms it prices — `dev.candidate_window` (`backtest/dev.py:293`)
starts a SPY-only candidate at SPY's `lookback`-th bar, and the recorded starts are 1993-02-01
against 1994-01-28 and 1994-05-17. A bill read across a window mismatch is not a bill. (b) It is
**one configuration**: M0038, M0039 and M0167 all run their `spy` host on
`DAILY_HOLD_FRAC_GOTRADE`, and M0113, M0136 and M0245 all run theirs on
`MONTHLY_HOLD_FRAC_GOTRADE`, so the second method to register it would be refused by
`store.has_trial`. A per-method allocator fixes both: it pins the method's own lookback, and the
allocator id is part of `config_text` (`lab/method.py:42`), so no two can collide.

**D3.2 — A params dataclass may NOT gain a field, and an existing one may not be reused.**
`config_text` canonicalizes `c.params` through `backtest.registry._canon`, which enumerates every
`compare=True` dataclass field and drops a pinned default only for `TradeRules`
(`registry.py:323`). Adding `always: bool` to `ReentryParams` or `ConfirmParams` would move every
recorded digest of that method. Handing an existing params value to a gate-free allocator is the
other trap, and M0260's own `targets()` docstring already names it: *"handing `ZJUMP` a gate-free
twin of its params (`trend=None`) runs, but it would make the recorded row a lie"*. So each new
allocator gets its own small `AlwaysParams`, whose `as_dict()` says `gate: none` outright.

**D3.3 — The only edits above the appended block are the two the mechanism requires.** A method
file is a pre-registration and is append-only in substance; but an `Amendment` is reachable only
through `METHOD.amendments`, and `Method` is a frozen dataclass constructed at the bottom of the
file. The repo's own precedent is commit `7369905` (M0293 amendment 1): **80 insertions, 1
deletion**, the deletion being `from seer_engine.lab.method import Method` ->
`from seer_engine.lab.method import Amendment, Method`, plus one inserted
`amendments=(GATE_OFF,),` line inside the `Method(...)` call. Those two lines, and nothing else
above the block, are what this phase changes in each file. Neither touches any candidate's rules,
allocator or params, so
`test_every_recorded_configuration_still_digests_to_its_recorded_digest`
(`engine/tests/test_lab_methods.py:187`) cannot move.

**D3.4 — This phase PRE-REGISTERS and does not RUN** (plan index **D6**). `lab run --amend` writes to
the shared `lab/lab.sqlite` in the MAIN checkout, a concurrent `lab run` can silently lose trials
with no error, and running from a feature branch would leave the shared database holding rows for
method shas that are not on `main`. The tree is green in exactly the pending state:
`test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha`
(`engine/tests/test_lab_methods.py:134`) tolerates a sha mismatch on the one condition that
`runner.pending_amendment` resolves, and ten committed, unrecorded amendments are that condition.

### Three things that were checked and have nothing to say

- **D17 / `lab/control_shape.py`.** `kind_of` shape-checks an arm only when its rationale contains
  `"placebo"`, `"hash-drawn"` or `"hash order"` (`DRAW_MARKERS`). None of the ten rationales does,
  so every one is `KIND_NONE` and is never given a trade/turnover ratio. That matters: an
  always-invested arm trades far LESS than its gated twin (`M0245-GATE` 10 trades against an
  ungated SPY's 0), and a placebo classification would refuse it as handicapped. Each rationale
  **opens with `Yardstick:`** — `ROLE_CONTROL_OPENERS` carries `"yardstick"` on a word boundary
  (`M0107-NONE` is the one precedent) — so `role_of` reads `control`, which is the honest label for
  an arm that must never be promoted. The phrase **`the yardstick:`** is an `IDEA_MARKER` and is
  deliberately avoided, and so is `rung of the`, which would read as a dose arm.
- **`lab/real_costs.py::real_cost_problem`** reads `all_candidates()` and holds an amendment to
  Gotrade's real fees exactly as the originals. Every new arm reuses its own method's recorded
  `TradeRules` constant (`monthly-hold-frac-gotrade`, `daily-hold-frac-gotrade`), so no arm can
  fail it.
- **`runner.preflight_data`** refuses a method whose store lacks a field its allocators declare.
  Only the `M0261-ALWAYS` and `M0262-ALWAYS` allocators are market-aware, and they declare
  `market_fields = ("dividends",)` — the same field their methods' existing arms declare. Nothing
  new is demanded of any store. No arm names `rules.cash_yield`, so `missing_cash_yield` is empty.
  Every pinned lookback is at most 454, inside the 473-bar smoke-fixture cap.

---

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.

**Creates — allocators** (each in its own method file, each id unique across the lab, checked by
`test_allocator_ids_are_unique_across_methods`, `engine/tests/test_lab_methods.py:108`):

- `M0038-ALWAYS` (`lab/methods/m0038_yield_curve_watch_gate.py`)
- `M0039-ALWAYS` (`lab/methods/m0039_vix_term_structure_gate.py`)
- `M0113-ALWAYS` (`lab/methods/m0113_trend_switch_reentry.py`)
- `M0136-ALWAYS` (`lab/methods/m0136_staged_reentry.py`)
- `M0167-ALWAYS` (`lab/methods/m0167_yield_curve_watch_early_exit.py`)
- `M0245-ALWAYS` (`lab/methods/m0245_gate_confirmation.py`)
- `M0260-ALWAYS` (`lab/methods/m0260_gate_reading_cadence.py`)
- `M0261-ALWAYS` (`lab/methods/m0261_gate_reading_phase.py`)
- `M0262-ALWAYS` (`lab/methods/m0262_gate_reading_sessions.py`)

**Creates — module-level names** (one set per file above, all private to that file):
`AlwaysParams`, `_always`, `AlwaysAllocator`, `ALWAYS`, `ALWAYS_LOOKBACK` (where it is a constant),
`ALWAYS_FULL` (single-instrument files only), `AMEND_ALWAYS`.
In `m0334_gradual_cash_switch.py`: `AMEND_ALWAYS` only — no allocator, no params.

**Creates — candidates** (one per method, declared in that method's `Amendment`):
`M0038-ALWAYS`, `M0039-ALWAYS`, `M0113-ALWAYS`, `M0136-ALWAYS`, `M0167-ALWAYS`, `M0245-ALWAYS`,
`M0260-ALWAYS`, `M0261-ALWAYS`, `M0262-ALWAYS`, `M0334-ALWAYS`.

**Creates — docs:** `docs/runbooks/2026-10-27-m0396-never-step-aside-retrofit.md`.

**Signature changes:** none.

**Modifies, above the appended block, in each of the ten files and nowhere else:**
`from seer_engine.lab.method import Method` -> `from seer_engine.lab.method import Amendment, Method`,
and one `amendments=(AMEND_ALWAYS,),` line inside the `Method(...)` call, placed immediately after
the closing `),` of `candidates=(...)` and before `seen_keys=(`.

**Requires (from earlier phases):** nothing. This phase has no `depends_on`.

**Leaves alone (owned by others):**
`engine/src/seer_engine/strategies/*` (Phase 1 — `price_floor.py`, `f_factor.py`,
`f_fundamental.py`); `engine/src/seer_engine/sim/*` (Phase 2 — `rules.py`, `book.py`);
`engine/tests/test_price_floor.py`, `engine/tests/test_sim_rules.py`,
`engine/tests/test_sim_book.py`. **No file is shared with Phase 1 or Phase 2.**

**Never touched by this phase, by the plan set's invariant 3:** `lab/lab.sqlite`,
`web/data/lab.json`. This phase runs no `lab` subcommand that writes, and no `lab stage`.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/methods/m0038_yield_curve_watch_gate.py` | modify | import line `:56`; append block before `METHOD` at `:217`; `amendments=` line after `:291` |
| `engine/src/seer_engine/lab/methods/m0039_vix_term_structure_gate.py` | modify | import line `:54`; append block before `METHOD` at `:218`; `amendments=` line after `:281` |
| `engine/src/seer_engine/lab/methods/m0113_trend_switch_reentry.py` | modify | import line `:63`; append block before `METHOD` at `:217`; `amendments=` line after `:293` |
| `engine/src/seer_engine/lab/methods/m0136_staged_reentry.py` | modify | import line (`from seer_engine.lab.method import Method`); append block before `METHOD`; `amendments=` line after the `candidates=(...)` close |
| `engine/src/seer_engine/lab/methods/m0167_yield_curve_watch_early_exit.py` | modify | import line; append block before `METHOD`; `amendments=` line |
| `engine/src/seer_engine/lab/methods/m0245_gate_confirmation.py` | modify | import line; append block before `METHOD`; `amendments=` line |
| `engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py` | modify | import line; append block after `_v` / before `METHOD`; `amendments=` line |
| `engine/src/seer_engine/lab/methods/m0261_gate_reading_phase.py` | modify | import line; append block after `_v` / before `METHOD`; `amendments=` line |
| `engine/src/seer_engine/lab/methods/m0262_gate_reading_sessions.py` | modify | import line; append block after `_v` / before `METHOD`; `amendments=` line |
| `engine/src/seer_engine/lab/methods/m0334_gradual_cash_switch.py` | modify | import line; append `AMEND_ALWAYS` before `METHOD`; `amendments=` line. **No allocator** |
| `docs/runbooks/2026-10-27-m0396-never-step-aside-retrofit.md` | create | the ten `lab run --amend` invocations, environment, order, refusals, and the census correction |

Eleven files. `m0173_yield_curve_watch_dial.py`, `m0336_yield_curve_watch_ends_on_steepening.py`
and `m0338_switch_dwell_time.py` are **not** touched: they already carry the arm (see the census),
and a second registration would be a repeated configuration.

---

## Implementation Steps

### Step 0: Re-measure the census before writing a line

**File:** none — this is the claim-verification gate CLAUDE.md requires.
**Change:** reproduce the census table above from the lab database, read-only, so no connect-time
migration can dirty the committed file.
**Code:**
```bash
cd /home/miftah/seer && /home/miftah/seer/engine/.venv/bin/python - <<'PY'
import sqlite3
ids = ["M0038","M0039","M0113","M0136","M0167","M0173","M0245",
       "M0260","M0261","M0262","M0334","M0336","M0338"]
c = sqlite3.connect("file:lab/lab.sqlite?mode=ro", uri=True)
c.row_factory = sqlite3.Row
q = ",".join("?" * len(ids))
for r in c.execute(f"select id,status,source_sha from methods where id in ({q}) order by id", ids):
    na = c.execute("select count(*) from method_amendments where method_id=?", (r["id"],)).fetchone()[0]
    nt = c.execute("select count(*) from trials where method_id=? and window='test'", (r["id"],)).fetchone()[0]
    assert r["status"] in ("dev-eligible", "rejected"), (r["id"], r["status"])
    assert r["source_sha"] is not None and na == 0 and nt == 0, (r["id"], na, nt)
    print(r["id"], r["status"], "amendments", na, "test", nt)
for cid in ("M0038-DIV-OPEN", "M0173-EXP100", "M0336-NEVER", "M0338-NOSW"):
    print(dict(c.execute(
        "select candidate_id,trades,turnover,exposure,max_drawdown,allocator_id,start "
        "from trials where candidate_id=? and window='dev'", (cid,)).fetchone()))
PY
```
**Impact:** if any assertion fires — a status moved, an amendment landed, a test look was spent —
**stop and re-plan**. A peer session may have amended one of these while this plan was being
written.

---

### Step 1: M0038 — the SPY host's yardstick

**File:** `engine/src/seer_engine/lab/methods/m0038_yield_curve_watch_gate.py:56` (import),
`:215` (append after `_v`, before `METHOD = Method(` at `:217`), `:291` (the `amendments=` line).

**Change (a), the import line at `:56`:**
```python
from seer_engine.lab.method import Amendment, Method
```

**Change (b), the appended block — paste between the `_v` helper and `METHOD = Method(`:**
```python
# --------------------------------------------------------------------------- amendment 1

#: The yardstick's lookback, pinned to the SPY-WATCH arms' own. ``CurveGateAllocator.lookback``
#: returns 1 for a ``watch`` gate on the SPY host, and ``dev.candidate_window`` opened both
#: M0038-SPY-WATCH and this arm's window on 1993-02-01 for that reason. Pinning it is the whole
#: point: a bill read off an arm that was scored on eleven extra months of 1993 is not a bill.
#: M0038-SPY-2KEY reads a 200-bar average and already starts 1993-11-15; the gap between those two
#: arms is M0038's own and is not introduced here.
ALWAYS_LOOKBACK = 1

#: Full weight, once, so the target builder below allocates no new Decimal per session.
ALWAYS_FULL = equal_weight(1)


@dataclass(frozen=True, slots=True)
class AlwaysParams:
    """No dial at all: ``hold`` is held on every session and there is no watch to open.

    A separate params type rather than a ``CurveParams`` with the watch disabled, because
    ``CurveParams`` cannot express "no watch" -- ``gate`` is ``watch`` or ``2key`` and
    ``watch_days`` is at least 1 -- and because a recorded row that said ``gate=watch`` while no
    watch ran would be a lie in the one place the lab cannot afford one.
    """

    hold: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.hold, str) or not self.hold or self.hold != self.hold.upper():
            raise ValueError(f"hold must be a non-empty upper-case symbol, got {self.hold!r}")

    def as_dict(self) -> dict[str, str]:
        return {"hold": self.hold, "gate": "none"}


def _always(params: object) -> AlwaysParams:
    if not isinstance(params, AlwaysParams):
        raise TypeError(f"params must be AlwaysParams, got {type(params).__name__}")
    return params


class AlwaysAllocator:
    """M0038's SPY host with the curve watch taken out: held every session, never in cash.

    Not market-aware. The gated arms return no target without ``Market.series`` because their
    decision needs the yield curve; this arm has no decision to make, so it reads no series and
    declares no market field. Everything else -- the instrument, the weight, the rule set, the
    lookback -- is M0038's.
    """

    id = "M0038-ALWAYS"

    def lookback(self, params: Any) -> int:
        _always(params)
        return ALWAYS_LOOKBACK

    def symbols(self, params: Any) -> tuple[str, ...]:
        return (_always(params).hold,)

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_always(params).hold,)

    def uses_members(self, params: Any) -> bool:
        _always(params)
        return False

    def _run(self, history: Mapping[str, History], data_date: date,
             p: AlwaysParams) -> tuple[Target, ...]:
        h = history.get(p.hold)
        if h is None or h.index_of(data_date) is None:  # no bar dated d: never a new target
            return ()
        t = target_from_close(p.hold, last_close(h, data_date), ALWAYS_FULL)
        return () if t is None else (t,)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(history, data_date, _always(params))

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)  # one instrument: nothing to precompute

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, Mapping):
            raise TypeError(f"prepared must be a Mapping, got {type(prepared).__name__}")
        return self._run(prepared, data_date, _always(params))


ALWAYS = AlwaysAllocator()

AMEND_ALWAYS = Amendment(
    added=date(2026, 10, 27),
    why=(
        "M0038's SPY arms are priced against SPY itself and against M0039-SPY-200, both of them "
        "arms that step aside; nothing in this method's run holds SPY on every session, so what "
        "the curve watch COSTS has never been read off directly. This arm is that zero."
    ),
    hypothesis=(
        "M0389 measured that the lab under-charges a step-aside habit by about half when it "
        "prices the habit against another habit rather than against never stepping aside: on one "
        "chassis the switch alone billed 2.90 points a year, the fear-spike brake 5.04 and the "
        "term-structure brake 2.10, while the stacked pairs billed 5.66 and 3.75 rather than the "
        "7.95 and 5.00 that adding them gives. The fix is an arm with no opinion in it, and M0038 "
        "has one for its dividend host (M0038-DIV-OPEN) and none for its SPY host. This arm is "
        "SPY at full weight on every session of the same window, on M0038's own daily rule set at "
        "Gotrade's real fees, at the same one-bar lookback M0038-SPY-WATCH ran on, so the two "
        "open on the same session (1993-02-01) and the difference between them is the watch and "
        "nothing else. It is a measuring stick, not a candidate: SPY minus Gotrade's fees cannot "
        "beat total-return SPY by construction, and it must not be promoted on any showing. "
        "Success is a readable number -- the watch's own bill, in de-funded annual return against "
        "this arm -- plus the difference between that number and the one M0038's analysis quoted "
        "against M0039-SPY-200, which is the size of the error the lab has been making on this "
        "method. Assumed: cash earns nothing in the gated arms, the store is the same dev store "
        "M0038 ran on, and the comparison is de-funded, because trials.curve_json is the funded "
        "curve and annualizing it directly reports deposits as return."
    ),
    expected_failure=(
        "This arm is run in a LATER run than the arms it prices, which is the one structural "
        "weakness of any retrofit and must be reported with the number. The evidence that it is "
        "survivable was measured on 2026-10-27: M0038-DIV-OPEN (run 2026-10-16), M0173-EXP100 "
        "and M0336-NEVER (both run 2026-10-24) are the same configuration through three allocator "
        "ids and reproduce each other exactly -- 576 trades, 4.2962 turnover, 0.9746 exposure, "
        "57.65% worst fall. If this arm's own re-run on a later store disagrees with that kind of "
        "fidelity, the bill is not readable and the analysis must say so rather than quote it. "
        "The second way this fails is that M0038-SPY-WATCH made two trades in twenty-two years "
        "and sat out 24.5% of its sessions, so its bill is two events wearing a twenty-two-year "
        "coat whatever the yardstick says; a one-number answer here would be false precision, and "
        "the era split is the only honest reading. Third, this arm will post the deepest fall in "
        "the method by a wide margin -- it holds SPY through 2000-2002 and 2008 where SPY-WATCH's "
        "recorded worst fall is 18.88% -- and nothing about that makes the watch worth its price. "
        "No arm of this amendment is expected to be eligible, and the one that is most likely to "
        "clear a bar is the one that is a buy-and-hold index book and not a strategy."
    ),
    candidates=(
        Candidate(
            id="M0038-ALWAYS", family="M0038", rules=DAILY_HOLD_FRAC_GOTRADE, allocator=ALWAYS,
            params=AlwaysParams(),
            rationale=("Yardstick: SPY held on every session with no curve watch at all, so what "
                       "standing down for two years after an inversion costs can be read off "
                       "directly instead of inferred from another arm that also steps aside."),
            added=date(2026, 10, 27), owner_inputs=(),
        ),
    ),
)
```

**Change (c), inside `METHOD = Method(`, immediately after the `),` that closes
`candidates=(...)` at `:291` and before `seen_keys=(`:**
```python
    amendments=(AMEND_ALWAYS,),
```

**Impact:** M0038's file hashes to a sha the lab has not recorded until `lab run M0038 --amend`
runs. `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` passes through
`runner.pending_amendment`. No recorded digest moves. `all_candidates()` grows from 6 to 7, so the
suite smoke-runs the new arm.

---

### The single-instrument block, and the five files that paste it

Steps 2 to 6 paste **the same allocator as Step 1**, byte for byte, with four tokens substituted.
Nothing else differs, and nothing else may differ — the whole value of the yardstick is that it is
the method's own chassis with the gate removed and no other change. The four tokens:

| token | M0039 | M0113 | M0136 | M0167 | M0245 |
|---|---|---|---|---|---|
| `id = "M0038-ALWAYS"` | `"M0039-ALWAYS"` | `"M0113-ALWAYS"` | `"M0136-ALWAYS"` | `"M0167-ALWAYS"` | `"M0245-ALWAYS"` |
| `ALWAYS_LOOKBACK = 1` | `= 1` | `= LOOKBACK` | `= LOOKBACK` | `= HIGH_N + 1` | `= LOOKBACK` |
| `ALWAYS_FULL = equal_weight(1)` | same | same | **omit; use `_FULL`** | same | **omit; use `FULL`** |
| `Mapping[str, History]` | same | same | same | **`Mapping[str, Any]`** | same |
| `hold: str = "SPY"` default | `"SPY"` | `BENCH` | `BENCH` | `"SPY"` | `BENCH` |

Why each odd one:

- **M0136** already defines `_FULL` (the full rung of its ladder, `Decimal(1)` through
  `to_weight`) and does **not** import `equal_weight`; adding an import would be a third edit
  above the block for no gain. Use `_FULL` in `_run` and drop the `ALWAYS_FULL` line.
- **M0245** already defines `FULL = equal_weight(1)` at module level. Use it and drop the
  `ALWAYS_FULL` line.
- **M0167** does **not** import `History` from `strategies.base`; its own allocator is typed
  `Mapping[str, Any]`. Match the file, do not add the import.
- **M0113**, **M0136** and **M0245** each define a module constant `BENCH = "SPY"` and a module
  constant `LOOKBACK`. Use the file's own names, which is what makes the lookback pin self-evident
  to a reader: `ALWAYS_LOOKBACK = LOOKBACK` says "the same sessions as every other arm here".
- **M0167**'s pin is `HIGH_N + 1`, which is the expression `EarlyExitAllocator.lookback` returns
  for the `spy` host (`own = HIGH_N + 1`). Both `M0167-SPY-E200S` and `M0167-SPY-EHIGHL` are
  recorded starting 1994-01-28, which is where this arm will start.
- **M0039**'s and **M0038**'s pin is `1`, the literal `GateAllocator.lookback` /
  `CurveGateAllocator.lookback` return for the `spy` host. `M0039-SPY-TS` and `M0039-SPY-SPIKE`
  are recorded starting 1993-02-01.

Each file also needs its import line changed exactly as in Step 1(a):
`from seer_engine.lab.method import Amendment, Method`, and one
`amendments=(AMEND_ALWAYS,),` line inside its `Method(...)` call after `candidates=(...)`.

**Reading Steps 2 to 6.** Each shows the `AlwaysAllocator` class header with its own docstring and
then the comment `# ... the rest of the single-instrument block, unchanged ...`. That comment is
not an abbreviation of something undecided: it means **copy, verbatim, every line of Step 1's block
from `ALWAYS_LOOKBACK = ...` through `ALWAYS = AlwaysAllocator()`**, with the four tokens of the
table above substituted and the class docstring replaced by the one shown in that step. Step 1
carries the complete text; it is written once because six copies of the same forty lines invite
exactly the copy drift the yardstick cannot survive. The same convention applies to Step 9, which
copies Step 8.

---

### Step 2: M0039 — the SPY host's yardstick

**File:** `engine/src/seer_engine/lab/methods/m0039_vix_term_structure_gate.py:54` (import),
`:216` (append after `_v`, before `METHOD = Method(` at `:218`), `:281` (the `amendments=` line).
**Change:** paste the single-instrument block with the Step-2 column substituted
(`id = "M0039-ALWAYS"`, `ALWAYS_LOOKBACK = 1`, `hold: str = "SPY"`), the `AlwaysAllocator`
docstring re-worded for this method, then this `Amendment`.
**Code:**
```python
class AlwaysAllocator:
    """M0039's SPY host with the fear gate taken out: held every session, never in cash.

    Not market-aware. The gated arms return no target without ``Market.series`` because their
    decision needs the fear index; this arm has no decision to make, so it reads no series and
    declares no market field. ``GateParams`` could not express this: ``gate`` is ``ts`` or
    ``spike`` and ``threshold`` is a level, not an off switch, and a row reading
    ``threshold=1000000000.0`` would be a dial abused rather than a gate removed.
    """

    id = "M0039-ALWAYS"
    # ... the rest of the single-instrument block, unchanged ...


ALWAYS = AlwaysAllocator()

AMEND_ALWAYS = Amendment(
    added=date(2026, 10, 27),
    why=(
        "M0039's two fear gates are priced against M0039-SPY-200, which is itself a step-aside "
        "rule, so what either gate costs on its own has never been read. This arm is SPY held on "
        "every session of the same window: the zero both gates and the 200-day switch are "
        "measured from."
    ),
    hypothesis=(
        "M0389 proved on this exact chassis -- SPY at full weight, decided every session, "
        "fractional at Gotrade's real fees -- that two step-aside habits are strongly "
        "sub-additive, and that the lab's habit of quoting stacked-minus-switch as an overlay's "
        "price understates the overlay's own bill by about half: 55% for the fear spike and 40% "
        "for the term structure. M0039 is the method both of those overlays were first registered "
        "on, and it is the one that has never carried the zero. This arm is that zero: SPY at full "
        "weight on every session, M0039's own daily rule set, the same one-bar lookback its "
        "gated arms ran on, so M0039-SPY-TS, M0039-SPY-SPIKE and this arm all open on 1993-02-01 "
        "and every paired difference is the gate alone. M0039-SPY-200 opens 1993-11-12 because it "
        "reads a 200-bar average; that gap is M0039's own and is not introduced here, and the "
        "switch's own bill must therefore be read on the common era rather than whole-window. "
        "Success is three numbers the method could not produce before: the term structure's own "
        "bill, the fear spike's own bill, and the difference between each and the figure M0039's "
        "analysis quoted against the 200-day switch. It is a measuring stick and not a candidate; "
        "it cannot beat total-return SPY because it pays Gotrade's fees to hold the same thing, "
        "and it must not be promoted on any showing."
    ),
    expected_failure=(
        "The first way this fails is coverage, and it is certain rather than likely: VIX3M begins "
        "2006-07-17 in the dev store, so M0039-SPY-TS is this arm trade for trade over the "
        "window's first thirteen years and its whole-window bill is diluted by roughly half. Only "
        "the spike cell reads both bear markets. Any term-structure bill quoted off this arm "
        "without the 2006-2015 split attached is a number wearing a coat that does not fit. "
        "Second, this arm runs in a LATER run than the arms it prices. The fidelity evidence is "
        "the three-way reproduction measured on 2026-10-27 -- M0038-DIV-OPEN, M0173-EXP100 and "
        "M0336-NEVER, one configuration through three allocator ids on two dates eight days "
        "apart, identical to four decimals -- but it is evidence about a different chassis, and "
        "if this arm's numbers do not sit where SPY's own recorded total return says they should, "
        "the bill is unreadable and the analysis must say so. Third, this arm will post by far "
        "the deepest fall in the method: M0039-SPY-SPIKE already records 63.59% and this arm "
        "holds through the whole of 2000-2002 and 2008 with nothing to cut it, so it will fail "
        "the fall screen by a wide margin. That is the arm working, not failing."
    ),
    candidates=(
        Candidate(
            id="M0039-ALWAYS", family="M0039", rules=DAILY_HOLD_FRAC_GOTRADE, allocator=ALWAYS,
            params=AlwaysParams(),
            rationale=("Yardstick: SPY held on every session with no fear gate and no trend "
                       "switch, so each gate's own cost can be read off directly instead of "
                       "inferred from an arm that also steps aside."),
            added=date(2026, 10, 27), owner_inputs=(),
        ),
    ),
)
```
**Impact:** `all_candidates()` grows 6 -> 7. No recorded digest moves. `M0039-ALWAYS` is a new
allocator id and a new configuration; it cannot collide with `M0038-ALWAYS` even though the two
arms hold the same instrument on the same rules, because `config_text` names the allocator by id.

---

### Step 3: M0113 — the fixed 200-day exit's yardstick

**File:** `engine/src/seer_engine/lab/methods/m0113_trend_switch_reentry.py:63` (import),
`:215` (append after `_v`, before `METHOD = Method(` at `:217`), `:293` (the `amendments=` line).
**Change:** paste the single-instrument block with `id = "M0113-ALWAYS"`,
`ALWAYS_LOOKBACK = LOOKBACK`, `hold: str = BENCH`, then this `Amendment`.
**Code:**
```python
class AlwaysAllocator:
    """M0113's frame with the exit taken out: SPY held every session, never in cash.

    ``ReentryParams`` cannot express this. The exit is fixed in every variant by design -- it is
    the half of the switch M0113 was built to hold still -- so "no exit at all" is a new
    allocator, not a new setting. The lookback is M0113's own ``LOOKBACK`` (253, M0084's
    constant), which is what keeps this arm on exactly the sessions the six recorded arms ran on:
    all of them open 1994-01-28.
    """

    id = "M0113-ALWAYS"
    # ... the rest of the single-instrument block, unchanged ...


ALWAYS = AlwaysAllocator()

AMEND_ALWAYS = Amendment(
    added=date(2026, 10, 27),
    why=(
        "Every M0113 arm carries the same 200-day exit, so the six paired differences price the "
        "buy-back trigger and nothing prices the exit. This arm holds SPY on every session of the "
        "same window, which is the only way to read what the exit itself costs."
    ),
    hypothesis=(
        "M0113 holds one exit fixed and moves only the way back in, and that design means the "
        "method cannot see its own largest term. M0084 reported the switch's whole advantage as "
        "three falls sat out and a 6-to-11-point annual loss to holding SPY over 2009-2015, but "
        "that was measured against SPY in a different run on a different allocator. M0389 then "
        "showed that pricing a step-aside habit against another step-aside arm understates it by "
        "roughly half. This arm is SPY at full weight on every session, on M0113's own monthly "
        "rule set at Gotrade's real fees, at M0113's own 253-bar lookback, so it opens 1994-01-28 "
        "with all six recorded arms and every difference against it is the exit plus that arm's "
        "own re-entry. Subtracting the control arm M0113-SMA200 from it gives the exit's own "
        "bill; subtracting each other arm from M0113-SMA200 gives the re-entry's, which is what "
        "M0113 already reported. Success is the two terms separated, with a statement of how much "
        "of M0113's recorded 2009-2015 gap was the exit rather than the trigger. This arm is a "
        "yardstick and not a candidate: a 100%-SPY book paying Gotrade's fees cannot beat "
        "total-return SPY, and it must not be promoted."
    ),
    expected_failure=(
        "M0113's arms trade between 11 and 43 times in twenty-two years, so profit factor and the "
        "luck score are close to meaningless on this method and the yardstick cannot repair that: "
        "whatever the exit's bill turns out to be, it rests on three episodes. The likeliest "
        "disappointing outcome is that the exit's bill comes out so large that it swamps every "
        "re-entry difference M0113 measured, which would mean the method's whole published "
        "ordering is a comparison between arms that all paid the same large bill -- true, useful, "
        "and a flat answer rather than an interesting one. Second, this arm will record the "
        "deepest fall in the method by a very wide margin: the six recorded arms sit between "
        "18.89% and 35.61%, and an unswitched SPY book holds the whole of 2000-2002 and 2008. "
        "Third, the arm runs later than the arms it prices; the evidence that this is survivable "
        "is the exact three-way reproduction of one configuration across two run dates measured "
        "on 2026-10-27 (M0038-DIV-OPEN, M0173-EXP100, M0336-NEVER), and if M0113-ALWAYS does not "
        "reproduce total-return SPY less Gotrade's fees over 1994-2015 to a comparable fidelity, "
        "the bill must be reported as unreadable rather than quoted."
    ),
    candidates=(
        Candidate(
            id="M0113-ALWAYS", family="M0113", rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=ALWAYS,
            params=AlwaysParams(),
            rationale=("Yardstick: SPY held on every session with no exit and no re-entry rule, "
                       "so the 200-day exit's own cost can be separated from the buy-back "
                       "trigger's instead of the two being quoted as one number."),
            added=date(2026, 10, 27), owner_inputs=(),
        ),
    ),
)
```
**Impact:** `all_candidates()` grows 6 -> 7. `M0113-SMA50-W` runs on
`WEEKLY_HOLD_FRAC_GOTRADE` while this arm runs on `MONTHLY_HOLD_FRAC_GOTRADE`; that arm's bill
therefore carries a cadence term as well as the exit, and the amendment's analysis must say so.
A second, weekly yardstick is **not** registered here (one arm per amendment; see Handoffs).

---

### Step 4: M0136 — the staged ladder's yardstick

**File:** `engine/src/seer_engine/lab/methods/m0136_staged_reentry.py` — import line, append after
the `_v` helper and before `METHOD = Method(`, and the `amendments=` line.
**Change:** paste the single-instrument block with `id = "M0136-ALWAYS"`,
`ALWAYS_LOOKBACK = LOOKBACK`, `hold: str = BENCH`, **`_FULL` in place of `ALWAYS_FULL`** and the
`ALWAYS_FULL = equal_weight(1)` line omitted (this file imports `to_weight`, not `equal_weight`).
**Code:**
```python
class AlwaysAllocator:
    """M0136's frame with the ladder and the exit taken out: SPY at full weight, every session.

    The rung this arm sits on is the one ``StagedParams`` has no way to name. ``levels`` chooses
    how many steps there are on the way back in; it never removes the exit, which is fixed in
    every variant by design. The lookback is M0136's own ``LOOKBACK``, the same 253 bars M0084 and
    M0113 use, so this arm opens 1994-01-28 with all six recorded arms.
    """

    id = "M0136-ALWAYS"
    # ... the rest of the single-instrument block, with `_FULL` as the weight ...


ALWAYS = AlwaysAllocator()

AMEND_ALWAYS = Amendment(
    added=date(2026, 10, 27),
    why=(
        "M0136's six arms share one fixed 200-day exit and differ only in how the position is "
        "rebuilt, so the method prices the staging and never the exit. This arm holds SPY on "
        "every session of the same window and is the zero the staging is worth measuring from."
    ),
    hypothesis=(
        "M0136 asks whether coming back in halves beats coming back all at once, and answers it "
        "with six arms that all pay the same exit. M0389 showed that an overlay priced against "
        "another step-aside arm is charged roughly half its true standalone cost, which means "
        "every one of M0136's paired differences is a marginal number sitting on an unmeasured "
        "base. This arm is SPY at full weight on every session, on M0136's own monthly rule set "
        "at Gotrade's real fees, at M0136's own 253-bar lookback, so it opens 1994-01-28 with the "
        "recorded six and the difference against M0136-SMA200 is the exit's own bill on this "
        "chassis. Because M0136-SMA200 and M0113-SMA200 are the same symmetric control and both "
        "record 11 trades and an 18.89% worst fall, the exit bill this arm produces must agree "
        "with the one M0113-ALWAYS produces; two independent arms reaching the same number is the "
        "cheapest available check that the retrofit is measuring what it claims. Success is that "
        "agreement plus a statement of how much of the half-step's recorded advantage survives "
        "once the exit is priced. A yardstick, not a candidate: it must not be promoted."
    ),
    expected_failure=(
        "The two bills may not agree, and the most likely reason would be the retrofit rather "
        "than the method: M0113-ALWAYS and M0136-ALWAYS will be run as separate amendments, "
        "possibly minutes apart but not in one run, so a disagreement larger than rounding points "
        "at the store or the code moving between them and invalidates both numbers. That check "
        "failing is itself the most useful thing this arm can do. Second, M0136's arms trade "
        "between 11 and 19 times, so every number here rests on three episodes and no amount of "
        "yardstick repairs that. Third, this arm will post the deepest fall in the method by a "
        "wide margin -- five of the six recorded arms sit at 18.89% to 19.09% -- and that is the "
        "arm doing its job, not evidence for the ladder. Fourth, this arm runs later than the "
        "arms it prices; the fidelity evidence is the exact three-way reproduction of one "
        "configuration across two run dates measured on 2026-10-27, and anything less than that "
        "fidelity here means the bill is reported as unreadable."
    ),
    candidates=(
        Candidate(
            id="M0136-ALWAYS", family="M0136", rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=ALWAYS,
            params=AlwaysParams(),
            rationale=("Yardstick: SPY held at full weight on every session, with no exit and no "
                       "ladder, so what the fixed 200-day exit costs can be separated from what "
                       "the staged re-entry buys."),
            added=date(2026, 10, 27), owner_inputs=(),
        ),
    ),
)
```
**Impact:** `all_candidates()` grows 6 -> 7. The M0113/M0136 cross-check named in the hypothesis is
the phase's one free correctness test of the retrofit itself.

---

### Step 5: M0167 — the SPY host's yardstick

**File:** `engine/src/seer_engine/lab/methods/m0167_yield_curve_watch_early_exit.py` — import line,
append after the `_v` helper and before `METHOD = Method(`, and the `amendments=` line.
**Change:** paste the single-instrument block with `id = "M0167-ALWAYS"`,
`ALWAYS_LOOKBACK = HIGH_N + 1`, `hold: str = "SPY"`, and **`Mapping[str, Any]` in place of
`Mapping[str, History]`** throughout — this file does not import `History`, and adding the import
would be a third edit above the block.
**Code:**
```python
class AlwaysAllocator:
    """M0167's SPY host with the curve watch taken out: held every session, never in cash.

    Not market-aware: the watch arms return no target without ``Market.series`` because they read
    the yield curve, and this arm reads nothing. ``EarlyParams`` cannot express it -- ``watch_days``
    and ``min_days`` are both at least 1, so the watch is always open on at least the inverted day
    itself. The lookback is the ``HIGH_N + 1`` that ``EarlyExitAllocator.lookback`` returns for
    this host, which is what puts this arm on M0167-SPY-E200S's and M0167-SPY-EHIGHL's own first
    session, 1994-01-28.
    """

    id = "M0167-ALWAYS"
    # ... the rest of the single-instrument block, typed Mapping[str, Any] ...


ALWAYS = AlwaysAllocator()

AMEND_ALWAYS = Amendment(
    added=date(2026, 10, 27),
    why=(
        "M0167's SPY arms made two and three trades in twenty-two years and are priced against "
        "M0038's watch, which also steps aside. Nothing in this method holds SPY on every "
        "session, so the early-exit rule's cost against never standing down has never been read."
    ),
    hypothesis=(
        "M0167 keeps M0038's two-year curve watch and adds a way out of it early, and prices the "
        "result against M0038's arms -- every one of which also sits in cash. M0389 measured that "
        "this style of comparison charges a habit roughly half its standalone price. This arm is "
        "SPY at full weight on every session, on M0167's own daily rule set at Gotrade's real "
        "fees, at this method's own ``HIGH_N + 1`` lookback, so it opens 1994-01-28 with "
        "M0167-SPY-E200S and M0167-SPY-EHIGHL and the paired difference is the watch-plus-exit "
        "and nothing else. Its dividend arms are a separate question and already have their zero: "
        "M0167's DIV host is ``AnnParams(replace(R25, inner=NOT20), 'ex')`` on "
        "monthly-rank-weekly-resize-frac-gotrade, which is the configuration recorded as "
        "M0038-DIV-OPEN, and the lab refuses a second registration of a configuration that has a "
        "dev trial. Success is the bill for standing down on a curve inversion, read directly, "
        "plus the difference between that and the figure M0167's analysis quoted against M0038. "
        "A yardstick, not a candidate: it must not be promoted on any showing."
    ),
    expected_failure=(
        "Two inversions in twenty-two years is two data points, and the yardstick does not add a "
        "third: whatever bill this arm produces for M0167-SPY-E200S and M0167-SPY-EHIGHL, it is "
        "the price of two decisions and must be reported that way. Both recorded SPY arms have an "
        "infinite profit factor on two and three trades, which is the same statement in another "
        "form. Second, this arm will hold through 2000-2002 and 2008 and post a far deeper fall "
        "than M0167-SPY-EHIGHL's recorded 18.92%; that is the arm working. Third, the DIV half of "
        "the method is untouched by this amendment and a reader may expect it to be covered; the "
        "analysis must point at M0038-DIV-OPEN explicitly rather than leave the gap unexplained. "
        "Fourth, the arm runs later than the arms it prices, and the fidelity evidence is the "
        "three-way exact reproduction measured on 2026-10-27; if this arm's recorded numbers do "
        "not sit where total-return SPY less Gotrade's fees says they should over 1994-2015, the "
        "bill is unreadable and must not be quoted."
    ),
    candidates=(
        Candidate(
            id="M0167-ALWAYS", family="M0167", rules=DAILY_HOLD_FRAC_GOTRADE, allocator=ALWAYS,
            params=AlwaysParams(),
            rationale=("Yardstick: SPY held on every session with no curve watch and no early "
                       "exit, so what standing down after an inversion costs can be read off "
                       "directly rather than against another arm that also stands down."),
            added=date(2026, 10, 27), owner_inputs=(),
        ),
    ),
)
```
**Impact:** `all_candidates()` grows 6 -> 7. The DIV half is explicitly not covered and is recorded
in Handoffs.

---

### Step 6: M0245 — the confirmed gate's yardstick

**File:** `engine/src/seer_engine/lab/methods/m0245_gate_confirmation.py` — import line, append
after the `_v` helper and before `METHOD = Method(`, and the `amendments=` line.
**Change:** paste the single-instrument block with `id = "M0245-ALWAYS"`,
`ALWAYS_LOOKBACK = LOOKBACK`, `hold: str = BENCH`, **`FULL` in place of `ALWAYS_FULL`** and the
`ALWAYS_FULL = equal_weight(1)` line omitted (this file already defines `FULL = equal_weight(1)`).
**Code:**
```python
class AlwaysAllocator:
    """M0245's frame with the gate taken out: SPY at full weight, every session, never in cash.

    ``ConfirmParams`` chooses what must AGREE with a 200-day break before the book goes to cash;
    it has no value that means "never go to cash", and ``confirm='rise'`` with the longest slope
    window is still an exit. The lookback is M0245's own ``LOOKBACK`` (``SMA_N + MAX_SLOPE_N + 1``
    = 327), which the file already pins so that all six arms share one window; this arm joins them
    on 1994-05-17.
    """

    id = "M0245-ALWAYS"
    # ... the rest of the single-instrument block, with `FULL` as the weight ...


ALWAYS = AlwaysAllocator()

AMEND_ALWAYS = Amendment(
    added=date(2026, 10, 27),
    why=(
        "M0245's whole argument is that nine of the gate's eleven exits were premiums and two "
        "were claims, and it prices every confirmation rule against M0245-GATE, which is the "
        "insurance policy itself. The premium can only be read against not buying insurance."
    ),
    hypothesis=(
        "M0245 reads the 200-day gate as insurance and measures each confirmation rule against "
        "M0245-GATE, the unconfirmed policy. That answers 'does confirming the exit beat exiting "
        "plainly' and never 'what is the policy worth at all', and M0389 measured that the second "
        "question's answer is about twice what the first style of comparison implies. This arm is "
        "SPY at full weight on every session, on M0245's own monthly rule set at Gotrade's real "
        "fees, at M0245's own 327-bar lookback, so it opens 1994-05-17 with the recorded six. The "
        "difference against it is the total premium paid over twenty-two years, and the "
        "difference between that and each confirmation arm's is what the confirmation saved. "
        "M0245's own episode ledger predicts the shape: nine premium spells costing 52 points of "
        "missed market between them against two claims worth -45.8% and -53.0% of SPY while out, "
        "so this arm should earn more than M0245-GATE and fall far deeper. Success is the premium "
        "and the claims priced in the same run, on the same sessions, for the first time. A "
        "yardstick, not a candidate: it must not be promoted."
    ),
    expected_failure=(
        "The confirmation arms trade four to seven times in twenty-two years and M0245-FALL126 "
        "records a profit factor of 5,985 on four trades; a yardstick does not make numbers like "
        "those into evidence, and the premium this arm prices is still the premium of eleven "
        "episodes, two of which carry the whole result. Second, M0245-RISE21 is the deliberate "
        "disaster mirror (52.41% worst fall, 93.08% exposure) and sits closest to this arm on "
        "exposure; a reader could mistake the two, and the analysis must keep them apart -- "
        "RISE21 steps aside at the worst possible times, this arm never steps aside at all. "
        "Third, this arm will post the deepest fall in the method by far against the recorded "
        "18.85% to 52.41%, and that is the point rather than a failure. Fourth, it runs later "
        "than the arms it prices; the fidelity evidence is the exact three-way reproduction of "
        "one configuration across two run dates measured on 2026-10-27, and a worse reproduction "
        "here means the bill is reported as unreadable rather than quoted."
    ),
    candidates=(
        Candidate(
            id="M0245-ALWAYS", family="M0245", rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=ALWAYS,
            params=AlwaysParams(),
            rationale=("Yardstick: SPY held on every session with no 200-day gate and no "
                       "confirmation, so the total premium the insurance charged over the window "
                       "can be read off directly instead of against the policy itself."),
            added=date(2026, 10, 27), owner_inputs=(),
        ),
    ),
)
```
**Impact:** `all_candidates()` grows 6 -> 7.

---

### Step 7: M0260 — the anchored gate ladder's yardstick

**File:** `engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py` — import line, append
after the `_v` helper (which is after `BOOK = ZParams(...)`, so `BOOK` is in scope) and before
`METHOD = Method(`, and the `amendments=` line.
**Change:** a new allocator that is `SlowGateAllocator`'s own `targets` and `targets_prepared`
with exactly the line `if not self._on(...): return ()` deleted, and the method's own lookback
expression kept verbatim.
**Code:**
```python
# --------------------------------------------------------------------------- amendment 1


@dataclass(frozen=True, slots=True)
class AlwaysParams:
    """M0072-Z2-RAWRANK's book with no gate read at all. ``book`` is the host, carried WHOLE.

    The book is M0260's ``BOOK``, unmodified, for the reason ``SlowGateAllocator.targets``
    already gives: handing the host a gate-free twin of its params runs, but the recorded row
    would then describe a book that is not the one M0258 and M0072 recorded. The gate is removed
    in the ALLOCATOR, where M0260 removes it too, and ``as_dict`` says ``gate: none`` so no reader
    has to infer it from the allocator id.
    """

    book: ZParams = BOOK

    def __post_init__(self) -> None:
        if not isinstance(self.book, ZParams):
            raise TypeError(f"book must be ZParams, got {type(self.book).__name__}")
        if self.book.jump.inner.trend is None:
            raise ValueError(
                "book must carry a trend symbol and length: this arm reads no gate, but it must "
                "declare the same symbols and the same lookback as the rungs it is the zero of"
            )

    def as_dict(self) -> dict[str, str]:
        out = {"gate": "none"}
        for k, v in self.book.as_dict().items():
            out[f"book.{k}"] = v
        return out


def _always(params: object) -> AlwaysParams:
    if not isinstance(params, AlwaysParams):
        raise TypeError(f"params must be AlwaysParams, got {type(params).__name__}")
    return params


class AlwaysAllocator:
    """M0072's book with its 200-day gate removed: the arm this ladder's rungs are measured from.

    ``CadenceParams`` cannot express it -- its ``__post_init__`` requires the book to carry a
    trend, because an anchored reading needs something to read, and ``gate_months`` runs from 1 to
    12 with no "never" rung. So the zero is a separate allocator. Everything except the gate test
    is ``SlowGateAllocator``'s own code, including the 454-bar lookback, which is what keeps this
    arm on exactly the sessions the six recorded rungs ran on (all of them open 1996-01-03).
    """

    id = "M0260-ALWAYS"

    def lookback(self, params: Any) -> int:
        p = _always(params)
        return max(ZJUMP.lookback(p.book), p.book.jump.inner.trend[1] + MAX_ANCHOR_GAP)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ZJUMP.symbols(_always(params).book)

    def holds(self, params: Any) -> tuple[str, ...]:
        return ZJUMP.holds(_always(params).book)

    def uses_members(self, params: Any) -> bool:
        return ZJUMP.uses_members(_always(params).book)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """``SlowGateAllocator.targets``, with the gate test and nothing else removed."""
        p = _always(params)
        rows = factor_rows(history, members, data_date, p.book.jump.inner)
        return ZJUMP._targets(ZPrepared(history, None), rows, data_date, held, p.book)

    def prepare(self, history: Mapping[str, History]) -> ZPrepared:
        return ZJUMP.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ZPrepared) or prepared.factor is None:
            raise TypeError(f"prepared must be a prepared ZPrepared, got {type(prepared).__name__}")
        p = _always(params)
        rows = prepared.factor.rows_on(members, data_date, p.book.jump.inner)
        return ZJUMP._targets(prepared, rows, data_date, held, p.book)


ALWAYS = AlwaysAllocator()

AMEND_ALWAYS = Amendment(
    added=date(2026, 10, 27),
    why=(
        "M0260's ladder runs from a gate read weekly to a gate read yearly and stops there. The "
        "end of the ladder -- a gate never read at all -- is the one rung that prices the gate "
        "itself, and it was never registered."
    ),
    hypothesis=(
        "M0260 measured that reading the SPY-200 gate monthly beat reading it weekly by 7.01 "
        "points a year of the owner's money and 11.69 points of worst fall on M0072's book, and "
        "that past monthly the axis stops behaving like a speed. Every one of those numbers is a "
        "difference between two gated arms, so the ladder prices the READING and never the GATE. "
        "M0389 then measured that a step-aside habit priced against another step-aside arm is "
        "charged roughly half its standalone cost. This arm is the ladder's missing end: M0072's "
        "book exactly as the six rungs carry it, on M0260's own monthly rule set at Gotrade's "
        "real fees, at M0260's own 454-bar lookback, with the gate test deleted and nothing else "
        "changed, so it opens 1996-01-03 with every recorded rung. The difference against "
        "M0260-M-NATIVE is the gate's own bill on this book; the differences already published "
        "between the rungs are then readable as fractions of it. Success is that bill plus a "
        "statement of whether the 7.01-point cadence effect is large or small against it -- the "
        "method's own headline claim is that the cadence is worth about twice the gate, and this "
        "is the first arm that can check that sentence rather than assert it."
    ),
    expected_failure=(
        "The headline the method rests on may simply be wrong once the gate is priced: if the "
        "gate's own bill on this book turns out to be well above the 3.6 points a year the lab "
        "has quoted elsewhere, then the 7.01-point cadence gap is a smaller fraction of the whole "
        "than M0260 claimed, and the method's sentence 'the cadence is worth roughly twice the "
        "gate itself' has to be withdrawn or restated. That is the most valuable outcome "
        "available here and it is also the one that costs the method its headline. Second, this "
        "arm covers only the monthly cadence; M0260-W-NATIVE and M0260-W-G1 run on "
        "weekly-hold-frac-gotrade and their bills against a monthly yardstick carry a cadence "
        "term as well as a gate term, so the two weekly rungs stay unpriced by this amendment and "
        "the analysis must say so rather than quote a number for them. Third, this arm will post "
        "by far the deepest fall in the method against the recorded 23.80% to 35.49%, holding "
        "M0072's book through 2000-2002 and 2008 with nothing to cut it. Fourth, it runs later "
        "than the rungs it prices; the fidelity evidence is the exact three-way reproduction of "
        "one configuration across two run dates measured on 2026-10-27, and anything worse means "
        "the bill is reported as unreadable."
    ),
    candidates=(
        Candidate(
            id="M0260-ALWAYS", family="M0260", rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=ALWAYS,
            params=AlwaysParams(),
            rationale=("Yardstick: M0072's book held on every decision session with the 200-day "
                       "gate removed entirely, so the gate's own cost can be read off instead of "
                       "inferred from the difference between two readings of it."),
            added=date(2026, 10, 27), owner_inputs=(),
        ),
    ),
)
```
**Impact:** `all_candidates()` grows 6 -> 7. `ZJUMP._targets` is a private call into a frozen
method file; that is the same call `SlowGateAllocator.targets` already makes, and M0260's own
docstring records why it is safe (`m0072.py` is frozen against its recorded source sha, and M0258
set the precedent). `factor_rows` ignores `FactorParams.trend` — verified this session at
`strategies/f_factor.py:193`, where the gate is applied by the CALLER (`FactorAllocator.targets`)
and never inside `factor_rows` — so deleting the gate test genuinely ungates the arm, and
`ZJUMP._targets` contains no `trend_on` call of its own (verified).

---

### Step 8: M0261 — the phase grid's yardstick

**File:** `engine/src/seer_engine/lab/methods/m0261_gate_reading_phase.py` — import line, append
after the `_v` helper (so `BOOK` and `LADDER` are in scope) and before `METHOD = Method(`, and the
`amendments=` line.
**Change:** a new market-aware allocator that is `PhaseGateAllocator`'s own `_run` with exactly
`if not self._on(prepared.history, data_date, p): return ()` deleted.
**Code:**
```python
# --------------------------------------------------------------------------- amendment 1


@dataclass(frozen=True, slots=True)
class AlwaysParams:
    """M0088-C-LIVE-63's book with no gate read at all. ``book`` is the host, carried WHOLE.

    Unmodified for the reason ``PhaseGateAllocator`` already gives: the recorded row must describe
    the book M0088, M0101, M0107 and M0122 recorded, and the gate is removed in the allocator,
    which is where this method removes it too. ``as_dict`` says ``gate: none`` outright.
    """

    book: CalmParams = BOOK

    def __post_init__(self) -> None:
        if not isinstance(self.book, CalmParams):
            raise TypeError(f"book must be CalmParams, got {type(self.book).__name__}")
        if self.book.ann.base.inner.trend is None:
            raise ValueError(
                "book must carry a trend symbol and length: this arm reads no gate, but it must "
                "declare the same symbols and the same lookback as the rungs it is the zero of"
            )

    def as_dict(self) -> dict[str, str]:
        out = {"gate": "none"}
        for k, v in self.book.as_dict().items():
            out[f"book.{k}"] = v
        return out


def _always(params: object) -> AlwaysParams:
    if not isinstance(params, AlwaysParams):
        raise TypeError(f"params must be AlwaysParams, got {type(params).__name__}")
    return params


class AlwaysAllocator:
    """M0088's calm-raisers book with its 200-day gate removed: this grid's zero.

    ``PhaseParams`` cannot express it: its ``__post_init__`` requires the book to carry a trend,
    because an anchored reading needs something to read, and there is no (k, phase) pair that
    means "never". Everything except the gate test is ``PhaseGateAllocator``'s own code, the
    454-bar lookback included, which is what keeps this arm on the sessions the six recorded arms
    ran on (all of them open 1996-01-03).
    """

    id = "M0261-ALWAYS"
    market_fields = ("dividends",)

    def lookback(self, params: Any) -> int:
        return max(CALM.lookback(_always(params).book), TREND_N + MAX_ANCHOR_GAP)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return CALM.symbols(_always(params).book)

    def holds(self, params: Any) -> tuple[str, ...]:
        return CALM.holds(_always(params).book)

    def uses_members(self, params: Any) -> bool:
        return CALM.uses_members(_always(params).book)

    def _run(self, prepared: RaisePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: AlwaysParams) -> tuple[Target, ...]:
        """``PhaseGateAllocator._run``, with the gate test and nothing else removed."""
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
            return ()
        inner = p.book.ann.base.inner
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, inner)
        return choose(prepared.history, rows, prepared.calendar, data_date, held, p.book)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar, so no event and no target."""
        return self._run(RaisePrepared(history, None, EMPTY_DIVIDENDS), members, data_date, held,
                         _always(params))

    def prepare(self, history: Mapping[str, History]) -> RaisePrepared:
        return CALM.prepare(history)

    def prepare_market(self, market: Any) -> RaisePrepared:
        return CALM.prepare_market(market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, RaisePrepared):
            raise TypeError(f"prepared must be RaisePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _always(params))


ALWAYS = AlwaysAllocator()

AMEND_ALWAYS = Amendment(
    added=date(2026, 10, 27),
    why=(
        "M0261 measured that two equally frequent readings of the same gate differ by 3.21 points "
        "a year of the owner's money depending only on WHICH months they read. Nothing in the "
        "method says what the gate is worth at all, because every arm reads it."
    ),
    hypothesis=(
        "M0261's finding is that past monthly a gate's reading interval is a lottery over which "
        "calendar months get read, and that the prize money in that lottery is larger than the "
        "whole weekly-to-yearly interval ladder M0260 measured. Both of those are differences "
        "between gated arms. M0389 measured that pricing a step-aside habit against another "
        "step-aside arm understates it by roughly half, so the lottery's prize money has never "
        "been put beside the thing it is a lottery over. This arm is M0088-C-LIVE-63's book "
        "exactly as the six arms carry it, on M0261's own monthly rule set at Gotrade's real "
        "fees, at M0261's own 454-bar lookback, with the gate test deleted and nothing else "
        "changed, so it opens 1996-01-03 with every recorded arm. The difference against "
        "M0261-NATIVE is the gate's own bill on this book, and the 3.21-point phase spread and "
        "the 8.2-point fall spread become readable as fractions of it. Success is the bill, plus "
        "a one-line answer to the question M0261 could not ask: is the choice of which months to "
        "read worth more or less than the choice to read at all?"
    ),
    expected_failure=(
        "The arm may make the method's finding less interesting rather than more: if the gate's "
        "own bill is several times the 3.21-point phase spread, the honest summary becomes 'the "
        "phase matters, but it is a second-order term inside a first-order decision', which is a "
        "quieter sentence than the one M0261 wrote. Second, this arm is behaviourally identical "
        "to M0262-ALWAYS, registered in the next amendment, because M0261 and M0262 share one "
        "host book and one rule set; that duplication is deliberate and has the method's own "
        "precedent -- M0261-NATIVE and M0262-NATIVE are already the same configuration under two "
        "allocator ids and reproduce each other to the digit (0.1871 worst fall, 3.523 profit "
        "factor, 528 trades, both) -- but a reader who meets both rows without that sentence will "
        "think one of them is a mistake. Third, this arm will post the deepest fall in the method "
        "against the recorded 18.71% to 27.41%, holding the book through 2000-2002 and 2008. "
        "Fourth, it runs later than the arms it prices, and the three-way exact reproduction "
        "measured on 2026-10-27 is the only evidence that this is survivable; anything worse and "
        "the bill is reported as unreadable."
    ),
    candidates=(
        Candidate(
            id="M0261-ALWAYS", family="M0261", rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=ALWAYS,
            params=AlwaysParams(),
            rationale=("Yardstick: M0088's calm big-raisers book held on every decision session "
                       "with the 200-day gate removed entirely, so what reading the gate at all "
                       "is worth can be put beside what reading it on different months is worth."),
            added=date(2026, 10, 27), owner_inputs=(),
        ),
    ),
)
```
**Impact:** `all_candidates()` grows 6 -> 7. `choose` is M0088's PUBLIC function and is already
imported by this file; no private call is added. `choose` contains no `trend_on` (verified this
session), so deleting the gate test genuinely ungates the arm.

---

### Step 9: M0262 — the session grid's yardstick

**File:** `engine/src/seer_engine/lab/methods/m0262_gate_reading_sessions.py` — import line,
append after the `_v` helper and before `METHOD = Method(`, and the `amendments=` line.
**Change:** paste **Step 8's block verbatim**, with exactly two substitutions:
`id = "M0262-ALWAYS"`, and `SessionParams` named in place of `PhaseParams` in the `AlwaysAllocator`
docstring (the sentence becomes: *"`SessionParams` cannot express it: its `__post_init__` requires
the book to carry a trend, and there is no (period, offset) pair that means 'never'"*). The
`lookback` expression, `MAX_ANCHOR_GAP` and `TREND_N` are this file's own constants and resolve to
the same 454. Then this `Amendment`:
**Code:**
```python
AMEND_ALWAYS = Amendment(
    added=date(2026, 10, 27),
    why=(
        "M0262 asks whether the slow-reading spread is the calendar's fault or rarity's, and "
        "answers it with six arms that all read the gate. The arm that reads it never -- the zero "
        "both answers are measured from -- was never registered."
    ),
    hypothesis=(
        "M0262 replaced M0261's calendar coordinate with a session count and found the free "
        "grid's pair gap (2.90 points unfunded) wider than the locked pair's (1.86), which is "
        "evidence that rarity and not the calendar carries the spread. Every number in that "
        "comparison is a difference between two gated arms. M0389 measured that this style of "
        "comparison charges a step-aside habit about half its standalone price, so neither answer "
        "has ever been put beside what the gate costs. This arm is M0088-C-LIVE-63's book exactly "
        "as the six arms carry it, on M0262's own monthly rule set at Gotrade's real fees, at "
        "M0262's own 454-bar lookback, with the gate test deleted and nothing else changed, so it "
        "opens 1996-01-03 with every recorded arm. It is registered separately from M0261-ALWAYS "
        "on purpose and with this method's own precedent: M0261-NATIVE and M0262-NATIVE are "
        "already one configuration under two allocator ids, because a ladder needs its zero rung "
        "inside its own run. Success is the gate's bill on this book, measured in M0262's run, "
        "and its agreement with the figure M0261-ALWAYS produces -- two arms that must agree, "
        "which is the cheapest check the retrofit can buy."
    ),
    expected_failure=(
        "If M0262-ALWAYS and M0261-ALWAYS disagree by more than rounding, the retrofit is broken "
        "rather than the method: the two arms are the same book on the same rules over the same "
        "sessions, and the only things that can differ between their runs are the store and the "
        "code. That check failing is the most useful thing this amendment can do and it must be "
        "reported before any bill is quoted. Second, as in M0261, the gate's own bill may dwarf "
        "both grid spreads and leave the calendar-versus-rarity question looking like a "
        "second-order detail. Third, this arm will post the deepest fall in the method against "
        "the recorded 18.71% to 41.77%, which is the arm working. Fourth, it runs later than the "
        "arms it prices; the fidelity evidence is the exact three-way reproduction of one "
        "configuration across two run dates measured on 2026-10-27, and anything worse means the "
        "bill is reported as unreadable rather than quoted."
    ),
    candidates=(
        Candidate(
            id="M0262-ALWAYS", family="M0262", rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=ALWAYS,
            params=AlwaysParams(),
            rationale=("Yardstick: M0088's calm big-raisers book held on every decision session "
                       "with the 200-day gate removed entirely, so the grid's spreads can be read "
                       "as fractions of what the gate itself costs."),
            added=date(2026, 10, 27), owner_inputs=(),
        ),
    ),
)
```
**Impact:** `all_candidates()` grows 6 -> 7. One duplicate book is deliberately registered; the
precedent and the reason are in the amendment's own prose, where a reader will meet them.

---

### Step 10: M0334 — the ramp's full rung, from the method's own dial

**File:** `engine/src/seer_engine/lab/methods/m0334_gradual_cash_switch.py` — import line, append
after the `_g` helper and before `METHOD = Method(`, and the `amendments=` line.
**Change:** **no allocator and no params type.** M0334's author already built the dial: `Params`
documents *"``flat`` > 0 holds that percent always (no opinion)"*, `exposure()` returns
`Decimal(p.flat) / 100` without reading a bar, and `GradAlloc._scale` at `f = 1` returns
`FACTOR`'s targets with their weights unchanged. `Params(flat=100)` is therefore the full book held
on every decision session, through the method's own allocator, at the method's own lookback
(`max(factor_lookback(PICK), params.sma_n)`), and it is a configuration no arm of this method or
any other holds. Smallest change that satisfies the request.
**Code:**
```python
# --------------------------------------------------------------------------- amendment 1

AMEND_ALWAYS = Amendment(
    added=date(2026, 10, 27),
    why=(
        "M0334 registered a flat half-weight book as its no-opinion arm and never registered the "
        "flat full-weight one, so the three ramps are priced against a book that is already "
        "half out of the market. The full rung of the method's own dial is the missing zero."
    ),
    hypothesis=(
        "M0334's hypothesis names M0332-M12-1-NOSW as the always-invested reference and reads it "
        "from the lab rather than re-running it, which was correct under the no-re-rolls rule and "
        "leaves the method's own run without a zero in it. M0389 then measured that a step-aside "
        "habit priced against another step-aside arm -- and a half-weight book is one -- is "
        "charged roughly half its standalone cost. This arm is the same picker, the same screen, "
        "the same monthly fractional Gotrade chassis and the same lookback as UP, DOWN, MID and "
        "HALF, at the one rung of the method's own exposure dial that never steps aside: "
        "``Params(flat=100)``, invested fraction 1 on every decision session, no bar read to "
        "decide it. It opens 1996-01-03 with the recorded four. The difference against it is what "
        "each ramp's cash time costs; the difference between that and M0334-HALF's is how much of "
        "the recorded safety was the ramp and how much was simply holding less. Success is those "
        "two terms separated, plus a check that this arm reproduces M0332-M12-1-NOSW -- the same "
        "book through a different allocator id -- which is the same reproduction check M0113-"
        "SMA200 was built to make against M0084-MONTHLY."
    ),
    expected_failure=(
        "The reproduction check may fail, and if it does the fault is almost certainly the "
        "scaling path rather than the picker: ``_scale`` rebuilds every target through "
        "``to_weight(t.weight * f)`` even at f = 1, and a rounding difference there would show up "
        "as a small, persistent drift against M0332-M12-1-NOSW. A drift of that kind invalidates "
        "every bill read off this arm and must be reported before any of them is quoted. Second, "
        "M0334's expected_failure already predicted that a partial exit fails the fall bar, and "
        "this arm will fail it by much more: M0332 recorded 61-67% worst falls for the unswitched "
        "20-name momentum book against the recorded 22.32% to 35.29% here. That is the arm "
        "working. Third, M0334-HALF is also an always-invested arm -- always invested at half "
        "weight, 49.48% exposure, 1474 trades -- and a reader could take it for the zero; the "
        "analysis must keep the two apart, because the whole point is that holding less is itself "
        "a safety device with a price. Fourth, this arm runs later than the arms it prices, and "
        "the fidelity evidence is the exact three-way reproduction of one configuration across "
        "two run dates measured on 2026-10-27."
    ),
    candidates=(
        _g("ALWAYS", Params(flat=100),
           "Yardstick: the same 12-1 top-20 book held at full weight on every decision session, "
           "no ramp and no opinion about the market, so what the ramps' cash time costs can be "
           "read off directly instead of against a book that is already half out"),
    ),
)
```
**Change (c), inside `METHOD = Method(`, after the `),` closing `candidates=(...)`:**
```python
    amendments=(AMEND_ALWAYS,),
```
**Impact:** `all_candidates()` grows 4 -> 5. No new allocator, no new params type, no new import
beyond `Amendment`. `Params` has no `__post_init__`, so `flat=100` needs no validation change, and
`as_dict()` records `flat_pct: "100"`, which is exactly what ran.

---

### Step 11: the runbook

**File:** `docs/runbooks/2026-10-27-m0396-never-step-aside-retrofit.md` (create).
**Change:** the whole execution procedure for the later, deliberate session. Write it verbatim:

````markdown
# Runbook — M0396: running the ten never-step-aside amendments

Pre-registered on 2026-10-27 by the `floor-reservation-yardstick` plan set, phase 3. **Nothing in
that phase ran.** This runbook is how the arms get run, later, deliberately, by one session.

## Before anything

1. **The amendments must be on `main`.** `lab run --amend` records a row against the file's
   current sha, and `lab stage` targets the MAIN checkout even from a worktree. Running these from
   a feature branch leaves the shared `lab/lab.sqlite` holding rows for shas that are not on
   `main` — the stale-lab.sqlite trap. Merge phase 3 to `main` first, and run from
   `/home/miftah/seer`.
2. **No other `lab run` may be in flight.** A concurrent `lab run` can silently lose trials with
   no error, and it also reddens three lab tests in a way that reads like a broken frozen record.
   Check first, and run these **one at a time, never concurrently**. A wave of concurrent lab
   phases has taken this laptop down twice.
3. **Environment.** The research store is not in worktrees; point `--store` at the main checkout.
   ```bash
   export SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite
   export SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research
   ```

## The ten commands, in this order

Run each on its own, check `$?`, and **never pipe a lab command through `grep`** — the pipe owns
the exit code, and a retry on `lab note` double-appends permanently. Redirect to a file instead.

```bash
cd /home/miftah/seer
for M in M0038 M0039 M0113 M0136 M0167 M0245 M0260 M0261 M0262 M0334; do
  echo "=== $M ==="   # run these ONE AT A TIME, by hand; the loop is the ORDER, not a script
done

engine/.venv/bin/python -m seer_engine lab run M0038 --amend --store engine/.research > /tmp/m0038.log 2>&1; echo $?
engine/.venv/bin/python -m seer_engine lab run M0039 --amend --store engine/.research > /tmp/m0039.log 2>&1; echo $?
engine/.venv/bin/python -m seer_engine lab run M0113 --amend --store engine/.research > /tmp/m0113.log 2>&1; echo $?
engine/.venv/bin/python -m seer_engine lab run M0136 --amend --store engine/.research > /tmp/m0136.log 2>&1; echo $?
engine/.venv/bin/python -m seer_engine lab run M0167 --amend --store engine/.research > /tmp/m0167.log 2>&1; echo $?
engine/.venv/bin/python -m seer_engine lab run M0245 --amend --store engine/.research > /tmp/m0245.log 2>&1; echo $?
engine/.venv/bin/python -m seer_engine lab run M0260 --amend --store engine/.research > /tmp/m0260.log 2>&1; echo $?
engine/.venv/bin/python -m seer_engine lab run M0261 --amend --store engine/.research > /tmp/m0261.log 2>&1; echo $?
engine/.venv/bin/python -m seer_engine lab run M0262 --amend --store engine/.research > /tmp/m0262.log 2>&1; echo $?
engine/.venv/bin/python -m seer_engine lab run M0334 --amend --store engine/.research > /tmp/m0334.log 2>&1; echo $?
```

The order is deliberate: the six single-instrument arms first (they are seconds each), then the
three book arms and M0334 (minutes each). M0113 and M0136 must be run back to back, and M0261 and
M0262 must be run back to back, because each pair's two arms are supposed to produce the same
number and a long gap between them weakens that check.

## Exit codes

- **0** — the amendment ran and one `method_amendments` row was appended. The method's status is
  explicitly unchanged, and the lab's N does not move: `store.DSR_POLICY` counts methods.
- **2** — the lab's rules refused the request. Read the message; it is one of:
  - the method file is uncommitted or dirty — the commit **is** the pre-registration;
  - the method has not run, or its status is `promoted`, `test-passed`, `test-failed` or `paper`
    (none of the ten is, as of 2026-10-27);
  - the method already has a `window='test'` trial (none of the ten does);
  - the amendment has already run, or a recorded amendment no longer matches the file;
  - a candidate repeats a configuration that already has a dev trial — **stop and re-measure**,
    because that means something changed since this was planned;
  - a variant is not priced at Gotrade's real fees.
- **1** — an error. Not a refusal. Read the traceback.

## After all ten

```bash
engine/.venv/bin/python -m seer_engine lab stage
```
`lab stage` writes `web/data/lab.json` and git-adds it with `lab.sqlite`. Commit **by index**, not
by pathspec: `git commit -- <paths>` re-reads the tree and defeats `lab stage`. Write the message
to a file and use `git commit -F`; backticks in a `-m` string are shell-substituted and silently
delete words, which has destroyed commits in this repo twice.

## Reading the result

- The bill of a step-aside habit is **ALWAYS's de-funded annual return minus that arm's**.
  `trials.curve_json` is the FUNDED curve and `trials.cagr` is deposit-contaminated; annualizing
  either directly reports deposits as return. De-fund with `regime.defunded(curve, deposits)`,
  deposits from `hardgate.trial_deposits`; `dressing.leg_of(conn, row)` hands you both.
- Check **M0113-ALWAYS against M0136-ALWAYS** and **M0261-ALWAYS against M0262-ALWAYS** first.
  Each pair is the same book on the same rules over the same sessions, so a disagreement larger
  than rounding means the retrofit is broken and no bill from this batch is readable.
- Check **M0334-ALWAYS against the recorded M0332-M12-1-NOSW**, which is the same book through a
  different allocator id.
- None of these arms may be promoted. Each is a buy-and-hold book, not a strategy, and
  `lab promote` has no role filter: it can select a declared diagnostic arm. Every one of the ten
  rationales opens with `Yardstick:`, which `control_shape.role_of` reads as `control`.

## The three methods that are NOT in this list, and why

`M0173`, `M0336` and `M0338` already carry a never-step-aside arm — `M0173-EXP100`
(*"Control: the dividend book never stepping aside for the curve watch"*), `M0336-NEVER` and
`M0338-NOSW` (*"no opinion: same book, switch off, always invested"*). The handover's census used
`max(trials.exposure) < 0.98`, and a stock book that never steps aside still reads about 0.97
because it always carries a little cash. `M0038`'s dividend half is covered the same way by
`M0038-DIV-OPEN`, which is also the yardstick for `M0039`'s and `M0167`'s dividend arms: all three
methods' DIV host is one configuration, and the lab refuses a second registration of a
configuration that already has a dev trial.
````

**Impact:** no code. The runbook is the one artefact that makes D3.4 safe to act on later.

---

## Verification

**The worktree venv is already built and working** — re-verified 2026-10-27 by the reconciler:
`engine/.venv/bin/python` is **CPython 3.12.7**, numpy 2.5.4, pytest 9.1.1, `import seer_engine`
ok. A worktree needs its own, or pytest silently tests the main checkout. **`python3.11` does not
exist on this machine**; `CLAUDE.md` says `python3.11 -m venv` but the real interpreter is
`python3` → CPython 3.12.7 from `/home/miftah/miniconda3/bin`. Confirm, and rebuild only on
failure:
```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
engine/.venv/bin/python -c "import numpy, pytest, seer_engine; print('venv ok')" \
  || (python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]')
```

**Postgres and `PG_TEST_URL` — before *every* pytest run below, not only the full suite.**
`PG_TEST_URL` is not exported by default in this shell, and the `seer-pg` container had been
stopped for 26 hours before this plan set started. CI fails if the DB tests skip, so a silent
local skip is a failure that reaches CI:
```bash
docker start seer-pg 2>/dev/null \
  || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
docker ps --filter name=seer-pg --format '{{.Names}} {{.Status}}'   # must print "seer-pg Up ..."
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
```

**Build / lint:**
```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
engine/.venv/bin/ruff check engine
```

**Targeted test — this is the phase's exit gate.** `engine/tests/test_lab_methods.py` builds
`CANDIDATES` from `m.all_candidates()`, so every one of the ten new arms is purity-checked,
`allocatorkit`-contract-checked (P4 identity, no look-ahead, and the market-aware "no panel, no
target" contract for `M0261-ALWAYS` and `M0262-ALWAYS`) and smoke-run through `dev.run_candidate`
by the ordinary run, with no lab state spent:
```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
PYTHONPATH=engine/src engine/.venv/bin/pytest engine/tests/test_lab_methods.py -n0
```

**Full suite:**
```bash
docker start seer-pg 2>/dev/null || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
PYTHONPATH=engine/src engine/.venv/bin/pytest engine/tests -n auto
```

**A failure a peer reports is not a failure until you re-run that test file yourself.** A
concurrent `lab run` in the shared main checkout reddens three lab tests in a way that reads
exactly like a broken frozen record. Re-run the suspect file alone before reporting anything.

**Manual check — the three assertions that matter, none of which spends lab state:**
```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick && PYTHONPATH=engine/src \
engine/.venv/bin/python - <<'PY'
import sqlite3
from seer_engine.lab.method import config_digest, discover
from seer_engine.lab import runner
mids = ["M0038","M0039","M0113","M0136","M0167","M0245","M0260","M0261","M0262","M0334"]
methods = discover()
conn = sqlite3.connect("file:/home/miftah/seer/lab/lab.sqlite?mode=ro", uri=True)
seen = {}
for mid in mids:
    m, _ = methods[mid]
    assert len(m.amendments) == 1, (mid, len(m.amendments))
    a = m.amendments[0]
    assert len(a.candidates) == 1, (mid, len(a.candidates))
    c = a.candidates[0]
    assert c.id == f"{mid}-ALWAYS", c.id
    assert c.rationale.lower().startswith("yardstick:"), c.id
    for bad in ("placebo", "hash-drawn", "hash order", "rung of the"):
        assert bad not in c.rationale.lower(), (c.id, bad)
    d = config_digest(c)
    hit = conn.execute("select candidate_id, window from trials where config_digest = ?", (d,)).fetchone()
    assert hit is None, (c.id, "repeats", hit)          # new everywhere in the lab
    assert d not in seen, (c.id, "repeats", seen.get(d))  # and new against the other nine
    seen[d] = c.id
    # the pending-amendment window the freeze test tolerates
    runner.pending_amendment(conn, m)
    print(f"{c.id:<16} digest {d[:8]}  lookback {c.allocator.lookback(c.params)}  rules {c.rules.id}")
for mid in ("M0173", "M0336", "M0338"):
    assert methods[mid][0].amendments == (), f"{mid} must not be amended: it already carries one"
print("ok: 10 pending amendments, 10 new digests, 3 correctly untouched")
PY
```

**Exit criteria:**

1. Ten method files each declare exactly one `Amendment` carrying exactly one candidate named
   `<MID>-ALWAYS`, and `M0173`, `M0336` and `M0338` declare none.
2. `engine/tests/test_lab_methods.py` is green: the sha freeze passes through
   `runner.pending_amendment` for all ten, every recorded configuration still digests to its
   recorded digest, allocator ids are unique, and all ten new arms smoke-run.
3. The full engine suite is green and `ruff check engine` is clean.
4. Every new arm's `config_digest` is absent from `trials` in any window, and the ten differ from
   each other.
5. `docs/runbooks/2026-10-27-m0396-never-step-aside-retrofit.md` exists and names the ten
   commands, the environment, the exit codes and the three untouched methods.
6. **No `lab run`, no `lab stage`, no write to `lab/lab.sqlite` or `web/data/lab.json`.**
   `git status` shows neither file modified.

---

## Commits

One commit per method, in the repo's own idiom (`git log --oneline -40` for the style), **naming
explicit file paths only** — never `git commit -a`, never a broad pathspec, because other sessions
share this checkout. Write every message to a file and apply it with `git commit -F`: backticks in
a `-m` string are shell-substituted and silently delete words, which has destroyed commits in this
repo twice.

```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
cat > /tmp/msg-m0038.txt <<'MSG'
lab: M0038 amendment 1 pre-registered — the SPY host's never-step-aside arm

M0038's SPY arms are priced against SPY itself and against M0039-SPY-200, both
of which step aside, so what the two-year curve watch costs has never been read
off directly. M0389 measured that this style of comparison charges a step-aside
habit roughly half its standalone price.

One arm: SPY at full weight on every session, on M0038's own daily rule set at
Gotrade's real fees, pinned to the one-bar lookback M0038-SPY-WATCH ran on so
both open 1993-02-01 and the difference between them is the watch alone.

The dividend half already has its zero: M0038-DIV-OPEN.

An amendment appends trials under M0038's own id, so this costs no method id and
does not move the lab's N. Not run: see
docs/runbooks/2026-10-27-m0396-never-step-aside-retrofit.md.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
git add engine/src/seer_engine/lab/methods/m0038_yield_curve_watch_gate.py
git commit -F /tmp/msg-m0038.txt
```

Repeat for `M0039`, `M0113`, `M0136`, `M0167`, `M0245`, `M0260`, `M0261`, `M0262`, `M0334`, each
`git add`-ing only that one file, then an eleventh commit for
`docs/runbooks/2026-10-27-m0396-never-step-aside-retrofit.md`.

---

## Handoffs

- **The census correction belongs in the lab's record, not only in this plan.** `M0173`,
  `M0336` and `M0338` already carry a never-step-aside arm and the handover's 8/13 split is
  therefore 11/10 under a correct reading. (Thirteen by the `exposure >= 0.98` read, ten in fact,
  because `exposure` is `mean(invested/equity)` and a long-only stock book that never steps aside
  still reads ~0.97 from its residual cash.) Recording that is a `lab note` against M0389 or a
  journal line, and `lab note` writes to the shared database — so it belongs to the later,
  deliberate session that runs the amendments, not to this phase. Hand it over with the runbook.
- **M0260's two weekly rungs stay unpriced.** `M0260-W-NATIVE` and `M0260-W-G1` run on
  `weekly-hold-frac-gotrade`; this amendment registers one monthly yardstick, so their bills would
  carry a cadence term as well as a gate term. A second arm (`M0260-W-ALWAYS`, the same allocator
  on `WEEKLY_HOLD_FRAC_GOTRADE`) is a clean follow-up amendment and costs nothing but a run.
  Same for `M0113-SMA50-W` on the weekly rule set.
- **M0039's and M0167's dividend arms are priced by M0038-DIV-OPEN**, which is correct and is not
  recorded anywhere a reader of those methods' pages will find it. A `lab note` on each is the fix,
  and it is a database write, so it goes with the runbook.
- **`lab dressing` cannot see a 2x2 and misreads an ALWAYS arm** (handover, insight 766: it exits 2
  and reports "declares no control or placebo arm" when ALWAYS is exactly that). This phase does
  not repair it. The forward fix is `control_shape.DECLARATION_ATTR` (`"controls"`), which
  `backtest.dev.Candidate` has no field for; adding a defaulted `controls: tuple[str, ...] = ()`
  field is safe for digests (`config_text` names its fields by hand and never passes a `Candidate`
  to `_canon`) but is a `backtest/` change and belongs to its own plan.
- **`lab promote` still has no role filter** and can select a declared diagnostic arm. Every arm
  here opens `Yardstick:` so `role_of` reads `control`, but nothing refuses on that. Carried over
  from the previous batch; not fixed here.
- **R1's printed-price floor touches `f_factor.factor_rows`**, which `M0260-ALWAYS`,
  `M0261-ALWAYS`, `M0262-ALWAYS` and (through `FACTOR`) `M0334-ALWAYS` all reach. This is no
  longer only a risk this phase carries: it is now **plan-set invariant I8**, stated in the index
  and guaranteed by phase 1's own Interface Contract — `factor_rows`'s default stays
  `price_basis="adjusted"`, `FactorParams` gains no field, and the printed basis arrives only as a
  keyword-only argument no caller passes. These arms are therefore unaffected. The guarantee is
  load-bearing rather than incidental: these arms must be RUN against the same screen the recorded
  rungs ran against, so if phase 1's default ever moved this retrofit would be void and would have
  to be re-planned. A later session that changes that default must re-plan R3 in the same breath.
- **No params dataclass may gain a field** — plan-set invariant **I9**, and decision D3.2 above is
  this phase's half of it. `backtest/registry.py:323` applies the pinned-default drop-out to
  `TradeRules` only, which is why phase 2 may append a `TradeRules` lever while this phase gives
  every new allocator its own fresh `AlwaysParams` instead of adding `always: bool` to an existing
  one. Phases 1 and 3 found this independently; the index now states it once.

---

## Rollback

This phase is eleven commits touching eleven files that no other phase touches, so
`git revert <sha>` backs out any one of them, and reverting all eleven returns every method file
to the sha the lab has recorded for it. Because **no amendment is run**, there is no
`method_amendments` row, no trial, no `lab.sqlite` change and no `web/data/lab.json` change to
undo: the revert is complete, and `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha`
goes from "tolerated via `pending_amendment`" straight back to "exact sha match".

**After an amendment HAS been run, a revert is no longer available for that method**:
`method_amendments` is append-only and `pending_amendment` refuses a file that declares fewer
amendments than the lab has recorded, with the message *"an amendment that has run is part of the
record and is never taken back out: restore the file from git"*. That asymmetry is the reason
D3.4 stops this phase at the pre-registration.
