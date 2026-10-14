# Phase 2: Hold thirty-five: a new roster entry, and `RAW-FR-GT` retired

**Plan set:** `ROSTER_35_FOUR_METHODS_PLAN.md`
**Analysis:** `docs/analyzer/20261014-150738-B7K4_code_analyzer.md`
**Satisfies:** R1 (change the Seer roster to hold 35 stocks instead of 20), R6 (spend no test-window look)
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/paper`, `db/migrations`, `engine/tests`, `web/lib/sera`

---

## Goal

The roster's unbraked residual-momentum book holds **35 names instead of 20**. It does so as a new
entry, `RAW35-FR-GT`, with its own paper clock and its own frozen spec; `RAW-FR-GT` is retired in
the same transaction. No started entry's spec digest moves, the lab spends no test-window look, and
the owner — who mirrors this roster with his own money — buys 35 names from the next unpaused
paper night onward.

---

## Verified facts this plan rests on

Every one of these was checked against the tree and the committed lab database at `661870d`
(`lab/lab.sqlite` md5 `ba692016a1106551234d774eb524590b`), not taken from the analysis.

| Claim | Verified how | Result |
|---|---|---|
| `M0139-N35-EBAND` runs `monthly-hold-frac-gotrade` — the preset `RAW-FR-GT` runs today | `sqlite3 trials` | `rules_id = monthly-hold-frac-gotrade` ✔ |
| Its recorded dev numbers | `sqlite3 trials` trial `n = 440` | max DD **0.19590**, CAGR **0.36913**, PF **2.0883**, DSR **0.9338**, trades **2548**, `n_trials_at_run` **88**, `failed = ''`, `eligible = 1` |
| Its funded (deposit-matched) numbers | `trial_funding` | mwr **12.824%/yr** against SPY TR mwr **7.188%/yr**, 237 deposits |
| Its params are `M0007-N20-RAW`'s with only `top` moved | read `m0139_names_on_an_invested_tape.py` + `m0011`'s `RAW20` | `ResidParams(inner=FactorParams(rank='momentum', top=35, trend=('SPY',200)), scaled=False)` ✔ |
| `M0139`'s lab status | `sqlite3 methods` | **`dev-eligible`** (so `promotion_basis` → `owner-override`) |
| The check-store 35-name row is the **TBAND** twin | `docs/lab/survivorship/roster-width-curve-2026-10-14.csv` | `35,M0139-N35-TBAND,check,0.201096,…,0.121106` ✔ — the caveat below is real |
| The entry's lookback | `RESIDMOM.lookback(P35)` | **401**, identical to `RAW-FR-GT`. `MAX_LOOKBACK_BARS` stays **426** |
| The new spec digest | built the `RosterRow`, ran `roster.spec_digest` | **`f9def72ae37bd7534807e5957a1e48917fe54322b65a5bbb0cd2898db41c443f`** |
| `RAW-FR-GT`'s digest does not move | same run | `21947eef1b8f1c9060fc3bd0af8be34d764b18041fd8f6c79bd720788575f822` — unchanged ✔ |
| `021` is the next free migration number | `ls db/migrations/` | last is `020_sean_own_orders.sql` ✔ |
| `RAW35` is free everywhere in the repo | `grep -rn RAW35 .` | no hits ✔ |
| The tree's `web/data/lab.json` currently equals the export of `lab/lab.sqlite` | `store.snapshot_json` vs the file | byte-identical, 5,167,880 bytes ✔ |

### The digest depends on two names you may not change casually

`spec_text` includes `"id":"RAW35-FR-GT"` and `"object":"RESIDMOM35"`. Pick a different roster id
or a different `RESOLVER` key and the pin below is wrong. The exact canonical text the pin hashes:

```
{"engine":"book","funding":{"amount_idr":"5000000","cadence":"monthly","day_of_month":"25"},"id":"RAW35-FR-GT","initial_idr":"10000000","object":"RESIDMOM35","object_id":"M0007","params":{"beta_n":"378","inner.min_dollar_volume":"20000000","inner.min_price":"5","inner.mom_n":"252","inner.mom_skip":"21","inner.pool":"50","inner.rank":"momentum","inner.sizing":"equal","inner.top":"35","inner.trend":"SPY:200","inner.vol_n":"60","market":"SPY","mom_n":"252","scaled":"no","skip":"21"},"registry_digest":null,"registry_id":null,"rules":{"cadence":"monthly","cost_model":"gotrade","cost_rate":"0.001","dividends":"true","engine":"book","entry":"open_limit","fractional":"true","id":"monthly-hold-frac-gotrade","idle_symbol":null,"max_positions":null,"resize":"true","time_stop":null},"rules_id":"monthly-hold-frac-gotrade"}
```

---

## Three findings the brief did not anticipate. Read these before writing a line.

### F1 — `promote` CANNOT be used for this change. Proved, not reasoned.

`commands/promote.py:104 object_name_of` inverts `RESOLVER` by object identity and **refuses an
object that two keys name**:

```python
names = sorted(n for n, b in roster.RESOLVER.items() if b.obj is not None and b.obj is obj)
if len(names) == 1:
    return names[0]
...
raise NotPromotable(f"the roster resolver gives <{ident}> ({where}) {len(names)} names ...")
```

A 35-name width needs a second key bound to the **same** `RESIDMOM` object (the binding carries the
params, which is exactly why a new width needs a new key). Run against the tree with the second key
injected, `promote` refuses:

```
REFUSED: the roster resolver gives <M0007>
  (seer_engine.lab.methods.m0007_residual_momentum.ResidualMomentumAllocator) 2 names
  (RESIDMOM, RESIDMOM35); a roster object must have exactly one, because the name is part of
  the frozen spec digest
```

**DECISION (this is the "decide and write down" the brief asked for): the live Neon database is
updated purely by the migration, not by `promote`.** `promote --dry-run` is not available as a
verification and must not be attempted. Consequences, all good:

- `lab.store.record_promotion` is never called, so **this phase writes nothing into `lab.sqlite`**
  and owes no lab commit of its own. The lab-pair invariant 7 serialisation is still needed — but
  for `web/data/lab.json` only (see F3).
- 013's prose ("each row is what `promote …` writes on the live database") becomes, for 021,
  "each row is what `promote` would have written had the resolver let it; here the migration is
  the only writer, and the reason is in the migration's own prose." Say that in 021, honestly.
- The verification that replaces `--dry-run` is the migration-equality pair in
  `tests/test_paper_roster.py` (`test_the_migration_rows_equal_the_seed_rows` and
  `test_the_database_rows_rebuild_the_roster_with_the_pinned_digests`): the migration is applied to
  a scratch Postgres, read back through `store.read_roster_rows` + `roster.from_rows`, and the
  rebuilt entry's digest is compared against the pin. That is strictly the same round trip
  `promote._insert` performs inside its transaction.

### F2 — three existing tests encode "no roster entry ever passed its dev gate". They must move.

1. `engine/tests/test_promote_command.py:155 test_object_name_of_is_the_resolvers_inverse` asserts
   `object_name_of(binding.obj) == name` for **every** binding. A second key on `RESIDMOM` makes it
   red. Rewrite to the now-true invariant (Step 7).
2. `engine/tests/test_paper_roster.py:685 test_every_override_states_its_basis_and_a_reason` asserts
   `{p.lab_status for p in LAB_PROVENANCE.values()} == {"rejected"}`. The new entry is admitted at
   `dev-eligible`. The test's own comment says *"When that stops being true, this assertion is the
   place to say so"* — so say it (Step 6c).
3. `engine/tests/test_paper_roster.py:724 test_every_provenance_matches_the_committed_lab_database`
   asserts, for an `owner-override`, `dev["eligible"] == 0` with the message *"Nothing was
   overridden"*. `M0139-N35-EBAND` has `eligible = 1`. **That assertion is wrong, not the
   admission.** What an override overrides is the lab's own route to paper, which is the **test
   window** (design §3), not the dev gate; every prior entry happened to fail both. Restate it as
   the exact mirror of the `test-passed` branch: an override must have **no passed test-window
   trial** (Step 6d). That keeps the test's teeth — it still catches an entry marked
   `owner-override` that the lab actually passed — and stops it asserting a historical accident.

### F3 — `web/data/lab.json` is coupled to this phase, and the brief's "do not commit it" cannot hold.

`lab/store.py:2967` builds the snapshot's `paper` block from `roster.LAB_PROVENANCE`, filtered to
`roster.active()`:

```python
"paper": [
    {"strategyId": sid, "methodId": p.method_id, "candidateId": p.candidate_id,
     "labStatus": p.lab_status, "basis": p.basis}
    for sid, p in sorted(roster.LAB_PROVENANCE.items())
    if sid in {e.id for e in roster.active()}
],
```

and `engine/tests/test_lab_snapshot.py:1054
test_the_committed_snapshot_is_the_export_of_the_committed_database` compares `web/data/lab.json`
against that export **byte for byte**. So the moment this phase edits `roster.py`, that test is red
until the snapshot is regenerated — and `web/lib/sera/paper.test.ts` reads the same file.

**Resolution, and the item the reconciler must see:** this phase *must* regenerate and commit
`web/data/lab.json`. It does so under the plan's own lab-write lock (index invariants 6–8), using
`lab export-json` — **never `lab stage`**, which `git add`s `lab/lab.sqlite` too and would sweep in
another phase's uncommitted trials. Full protocol in Step 11. If phases 1/3/4/5 have landed lab
rows by then, the regenerated snapshot legitimately carries them; that is why the export happens
inside the lock and is committed immediately.

---

## Why `M0139-N35-EBAND` and not `M0139-N35-TBAND` (state this in the migration too)

`RAW-FR-GT` exists on the roster for one reason: it is `RMW-FR-GT`'s picks **without the
volatility brake**, the controlled forward comparison that answers whether the brake earns what it
costs. That comparison is only readable while the two differ in the brake and nothing else.
`M0139-N35-TBAND` runs `monthly-hold-frac-gotrade-tband` — `resize_basis="target"`, the fix for the
band that never fires. Taking it would move the width **and** the rebalance basis at once and break
the comparison against `RMW-FR-GT`, which still runs the equity basis. The owner asked for a width
change. `M0139-N35-EBAND` is a width change and nothing else.

**The honest caveat, which must travel into the admission note and the migration:** the check-store
numbers quoted to the owner — 20.11% worst fall, 12.11%/yr — were measured on `M0139-N35-TBAND`,
not on the variant being admitted. On the dev store the two differ by **0.012 points of drawdown**
(0.19590 vs 0.19602) and **0.19 points of CAGR** (0.36913 vs 0.37106). The width conclusion
transfers; the check-store reading is the twin's. Say that, rather than implying a measurement
nobody took.

**The second honest caveat — the post-2009 column.** From the same CSV, `era_2009_2015_edge` on the
check store reads **−0.0022 at 20 names and −0.0168 at 35**. Over the years most like today, both
widths lose to SPY on the honest tape, and the wider one loses by more. The width case is a
drawdown case, not a return case, and the migration must not let the 12.11% headline hide it.

**The third, and it is the strongest argument for admitting this on the owner's rule rather than
waiting.** `lab status` (run read-only against the committed database on 2026-10-14) reports:

```
M0139 is not promoted: M0021, M0022, M0029 already read test-failed, and they are kin --
same family ('stock-residual-momentum') ... By behaviour (D14): M0021 (M0139-N35-EBAND moves
with M0021's tested M0021-B70-RAW at 0.95 residual correlation) ...
```

M0139 is **kin-blocked by the hard gate**, permanently, whatever it scores. So "never had a
test-window look" is not "not yet" — the lab will never give this family one, by its own rule. That
is precisely the case the roster's module docstring describes as the deliberate divergence from the
lab's design: *"a lab test pass is a sufficient basis for a paper entry, never a necessary one,
because paper trading is how a near-miss earns the right to be taken seriously."* The admission
note and the migration should say so plainly, because the alternative reading — "we'll test it
later" — is false. **This is also why R6 is satisfied for free: there is no look to spend here,
and this phase runs no `lab` command but a read-only `lab status`.**

---

## Interface Contract

**Creates:**
- `paper.roster.RAW35_GT_ID` = `"RAW35-FR-GT"` (`paper/roster.py`, beside `RAW_GT_ID`)
- `paper.roster.RESIDMOM35_PARAMS` (`paper/roster.py`)
- `paper.roster.RESOLVER["RESIDMOM35"]` → `Binding(obj=RESIDMOM, params=RESIDMOM35_PARAMS)`
- `paper.roster.LAB_PROVENANCE["RAW35-FR-GT"]`
- `paper.roster.SEED_ROWS` entry `RAW35-FR-GT` at `sort=4`
- `strategies.evidence.EVIDENCE["RESIDMOM35"]` → the existing `residmom_evidence`
- `db/migrations/021_roster_width_35.sql`
- `tests/test_paper_roster.py` `PINS["RAW35-FR-GT"] = "f9def72a…c443f"`

**Signature changes:** none.
**Renames:** none. `RESOLVER` keys are stable forever; `"RESIDMOM"` is untouched.
**Deletes:** nothing. `RAW-FR-GT` is **retired**, not removed: its row, its `RESOLVER` key, its
`LAB_PROVENANCE` entry, its `SEED_ROWS` row and its pin all stay exactly as they are.

**Modifies (behaviour visible to other phases):**
- `paper/roster.py` SEED_ROWS: `RAW-FR-GT` → `status="retired"`, `sort` 4 → 20, physically moved to
  the end of the tuple (SEED_ROWS is in `sort` order, and `test_the_migration_rows_equal_the_seed_rows`
  compares it against `ORDER BY sort, id`).
- `web/data/lab.json` `paper` block: `RAW-FR-GT` out, `RAW35-FR-GT` in. **This is the only file
  this phase touches that another phase also writes.** See Step 11.

**Requires (from earlier phases):** nothing. This phase has no `depends_on`.

**Leaves alone (owned by others):**
- `lab/lab.sqlite` — **not written and not staged by this phase** (F1 removed the only writer).
  Phases 1, 3, 4, 5 own it.
- `lab/methods/m0148_*.py`, `m0149_*.py`, `m0155_*.py`, `m0156_*.py` — phases 5, 4, 3, 1.
- `docs/lab/survivorship/grid.csv` and every dated CSV under `docs/lab/survivorship/` — read only.
- `backtest/registry.py` — never appended to, by anything, ever.
- `MOM-FR-GT` (phase 1 owns its width question), `RMW-FR-GT`, `MVW-FR-GT`.
- `M0139`'s frozen verdict row, `M0007`'s and `M0139`'s method files, and every closed lab record.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/paper/roster.py` | modify | `M0139` import (`:131`); `RAW35_GT_ID` (`:186`); `RESIDMOM35_PARAMS` (`:372`); `RESOLVER["RESIDMOM35"]` (`:487`); `LAB_PROVENANCE["RAW35-FR-GT"]` (`:652`); new `SEED_ROWS` row at `sort=4` (`:994`); `RAW-FR-GT` moved to `sort=20`, `status="retired"`, at the tuple's end (`:1324`) |
| `engine/src/seer_engine/strategies/evidence.py` | modify | one `EVIDENCE` key, `:689` |
| `db/migrations/021_roster_width_35.sql` | create | insert `RAW35-FR-GT`, retire `RAW-FR-GT`, renumber `sort` |
| `engine/tests/test_paper_roster.py` | modify | `RAW35_GT` const (`:94`); `RETIRED`/`ACTIVE_IDS` (`:98`); `PINS` (`:133`); `:156` id tuple and `range(1,21)`; `:320` lookbacks; `:592` + `:783` `promoted_from` sets; `:647` `LAB_DERIVED`; `:685`; `:724`; `:806` successor pairs |
| `engine/tests/test_promote_command.py` | modify | `:155` — the resolver-inverse invariant, restated (F1/F2) |
| `engine/tests/test_paper_store.py` | modify | `:59` roster id list |
| `engine/tests/test_paper_check.py` | modify | `:60` `ALL_IDS` |
| `engine/tests/test_migrate.py` | modify | `:292` roster id list |
| `engine/tests/test_evidence.py` | modify | `:450` `LAB_BOOKS` gains `RESIDMOM35` |
| `.claude/skills/calculate-assets/build_audit.py` | modify | `:14` the roster id → lab variant map |
| `docs/runbooks/paper-trading.md` | modify | `:30-37` roster table; `:39` retired count; a dated retirement record |
| `web/lib/sera/paper.test.ts` | modify | `RAW-FR-GT` → retired/null; `RAW35-FR-GT` is the M0139 entry |
| `web/data/lab.json` | regenerate | the `paper` block, via `lab export-json` under the lock (Step 11) |

---

## Implementation Steps

### Step 1: Import `M0139` and name the new roster id
**File:** `engine/src/seer_engine/paper/roster.py:131` (imports) and `:186` (the 017 id block)

**Change:** add the frozen method module beside the other five lab imports, keeping the existing
alphabetical-by-module order, and name the new id where the other `-GT` ids are named.

**Code — insert after the `m0011` import pair (`:131`), before the `m0022` pair:**

```python
from seer_engine.lab.methods.m0139_names_on_an_invested_tape import METHOD as M0139
```

(The file imports `METHOD as MNNNN` and then the allocator object for each method. `M0139` needs
only the `METHOD`: its allocator **is** `RESIDMOM`, already imported from `m0007`.)

**Code — append to the 017 id block, replacing lines `180`–`186`:**

```python
BENCHMARK_GT_ID = "SPY-GT"  # the yardstick pays what the methods pay (resume condition 1)
C_GT_ID = "C-GT"  # the DAILY-TRADING CONTROL, permanently (owner, 2026-10-08; resume condition 2)
RMW_GT_ID = "RMW-FR-GT"
RAW_GT_ID = "RAW-FR-GT"
MOM_GT_ID = "MOM-FR-GT"
MVW_GT_ID = "MVW-FR-GT"

# 021, the width change (owner, 2026-10-14): "let's change our seer roster to hold 35 stocks
# instead of 20". RAW35-FR-GT is RAW-FR-GT's book with only the name count moved -- the same
# screen, the same ranking, the same SPY 200-day filter, the same rule set, the same fees. It is a
# NEW ID and not an edit because `top` is in the frozen spec: moving it on a started entry would
# fail its next night with a SpecMismatch (store.check_digest). RAW-FR-GT is retired in the same
# migration, so the board never shows two widths of one book.
RAW35_GT_ID = "RAW35-FR-GT"
```

**Impact:** no behaviour. `M0139` is read for its frozen params only, exactly as `M0007` and
`M0011` are, and a lab-side edit to that file would be caught by `tests/test_lab_methods.py`'s
`source_sha` pin before it could re-digest anything.

---

### Step 2: The params constant, read from the frozen method file
**File:** `engine/src/seer_engine/paper/roster.py:372` (immediately after `RESIDMOM_PARAMS`)

**Change:** add the 35-name params, read from `M0139`'s candidates by id, in the style of the five
constants above it.

**Code — insert after the existing `RESIDMOM_PARAMS` line:**

```python
#: RAW35's params: lab M0139's N35-EBAND variant -- RAW's residual-momentum book with ONE field
#: moved, ``inner.top`` 20 -> 35, on the SAME rules preset (``monthly-hold-frac-gotrade``).
#: ``M0139-N35-EBAND`` and not ``M0139-N35-TBAND``: the tband twin also moves ``resize_basis`` to
#: "target", and changing two things at once would break the one comparison RAW exists on this
#: roster to provide -- the same picks WITH the brake (RMW-FR-GT) against the same picks without
#: it. The owner asked for a width change; this is a width change and nothing else. Read from the
#: frozen method file like the five above, so the roster can never drift from the trial it records.
RESIDMOM35_PARAMS = next(c.params for c in M0139.candidates if c.id == "M0139-N35-EBAND")
```

**Impact:** none until the binding below references it. Evaluated at import; a typo in the
candidate id raises `StopIteration` at import time, which the whole suite catches immediately.

---

### Step 3: The new `RESOLVER` key
**File:** `engine/src/seer_engine/paper/roster.py:487` (the end of the `RESOLVER` literal)

**Change:** append one key. Do **not** rename, reorder or touch `"RESIDMOM"`.

**Code — replace the tail of the `RESOLVER` literal, from the `"RESIDMOM"` entry to the closing
brace:**

```python
    # Lab M0007's residual-momentum book, its N20-RAW variant: RMW's engine with no brake
    # (promoted 2026-10-07, the controlled comparison against RMW-FR).
    "RESIDMOM": Binding(obj=RESIDMOM, params=RESIDMOM_PARAMS),
    # Lab M0002's regime-scaled momentum, its REL-85 variant (promoted 2026-10-07, replaces F4).
    "REGIME": Binding(obj=REGIME, params=REGIME_PARAMS),
    # Lab M0008's minimum-variance weighting, its N30-C07 variant (promoted 2026-10-07,
    # replaces F1).
    "MINVAR": Binding(obj=MINVAR, params=MINVAR_PARAMS),
    # 021: the SAME allocator object at a different width (lab M0139-N35-EBAND, 35 names). A
    # binding carries the PARAMS as well as the object, and `params` is in the frozen spec, so a
    # new width is a new key -- it cannot ride on "RESIDMOM" without re-digesting a live entry.
    #
    # THE ONE CONSEQUENCE, STATED HERE SO IT IS NOT DISCOVERED LATER. `commands.promote`'s
    # `object_name_of` inverts this table by object identity and refuses an object two keys name,
    # because the name is part of the digest. RESIDMOM now has two names, so `promote` can no
    # longer place ANY variant of this allocator: migration 021 writes the row instead, and a
    # future width of this book takes the same path. That is a cost of widths, not a defect --
    # the alternative is a resolver that cannot tell two widths apart.
    "RESIDMOM35": Binding(obj=RESIDMOM, params=RESIDMOM35_PARAMS),
}
```

**Impact:** `resolver_names()` gains `"RESIDMOM35"`. `promote.object_name_of(RESIDMOM)` now raises
`NotPromotable` — intended, documented, and asserted in Step 7.

---

### Step 4: The `LAB_PROVENANCE` entry
**File:** `engine/src/seer_engine/paper/roster.py:652` (after the `MVW_GT_ID` entry, before the
closing brace of `LAB_PROVENANCE`)

**Change:** add the admission record. `basis` is `owner-override` because `M0139` is
`dev-eligible`, not `test-passed` (`lab.store.promotion_basis` returns `test-passed` only from
`test-passed` or `paper`). The reason is the one line the field exists to force, and it is honest
about M0139's own frozen verdict.

**Code — insert before the closing `}` of `LAB_PROVENANCE`:**

```python
    # 021: the width change. The entry it replaces, RAW-FR-GT, keeps its line above -- a retired
    # entry's provenance is lineage and is never edited.
    RAW35_GT_ID: LabProvenance(
        method_id="M0139",
        candidate_id="M0139-N35-EBAND",
        lab_status="dev-eligible",
        basis="owner-override",
        reason=(
            "the owner moved the roster's width from twenty names to thirty-five (2026-10-14). "
            "It is RAW-FR-GT's own book with one field changed -- the number of names -- on the "
            "same screen, the same ranking, the same market filter, the same rule set and the "
            "same fees, so the forward comparison against RMW-FR-GT (the same picks WITH the "
            "volatility brake) still reads. The variant passes every dev check with nothing "
            "failed -- max DD 19.6%, PF 2.09, 2,548 trades, recorded DSR 0.934 at its recorded "
            "N=88 -- which is new for this roster. It has still never had a test-window look and "
            "it never will: the hard gate blocks M0139 on kin, because M0021, M0022 and M0029 "
            "read test-failed in the same family and this book moves with M0021's tested one at "
            "0.95. So the basis is the owner's rule and not the lab's, and 'not yet tested' would "
            "be the wrong way to read it. The width evidence is "
            "M0152's curve on the survivorship-check store, the price history that keeps the "
            "companies that went bankrupt or were bought: there the twenty-name book falls 25.05%, "
            "outside the owner's own 25% bar, and the thirty-five-name book 20.11% while earning "
            "slightly more. That check-store reading was taken on this variant's target-band twin "
            "M0139-N35-TBAND, which differs from it on the dev store by 0.012 points of drawdown "
            "and 0.19 points of yearly return, so the width conclusion transfers but the "
            "check-store number is the twin's. M0139's own recorded verdict reads 'Twenty names "
            "still wins': it was written on the dev store alone, before M0147 and M0152 showed "
            "that store cannot see the holdings that collapsed and left, and it stays frozen as "
            "the closed record it is"
        ),
    ),
```

**Impact:** `LAB_PROVENANCE` gains a key. Not in the spec, so no digest moves (asserted by
`test_lab_provenance_is_not_in_the_spec`). **It does change `web/data/lab.json`'s `paper` block** —
see Step 11.

---

### Step 5: The `SEED_ROWS` change — one row added at `sort=4`, `RAW-FR-GT` moved to `sort=20`
**File:** `engine/src/seer_engine/paper/roster.py:994–1017` (the `RAW_GT_ID` row) and `:1324` (the
tuple's end)

**Change, in two parts.** `SEED_ROWS` must stay in `sort` order, because
`test_the_migration_rows_equal_the_seed_rows` compares it element-wise against
`SELECT … ORDER BY sort, id`. So the `RAW-FR-GT` `RosterRow` is **physically moved** to the end of
the tuple and the new row takes its place. This is exactly 017's pattern (`SPY` 1 → 7, `C` 2 → 11).

**5a. Replace the whole `RosterRow(id=RAW_GT_ID, …)` block at `:994–1017` with the new entry:**

```python
    RosterRow(
        id=RAW35_GT_ID,
        name="RAW35 · Unbraked momentum",
        sub="Top 35 by rise beyond the market, no brake, monthly, fractional shares, real Gotrade fees",
        icon="zap",
        is_champion=False,
        is_benchmark=False,
        sort=4,
        engine="book",
        rules_id="monthly-hold-frac-gotrade",
        object_name="RESIDMOM35",
        registry_id=None,
        gate_note=(
            "Lab M0139 dev window only (1996-01-03..2015-10-16), already in fractional shares at "
            "Gotrade's measured fees -- the same rule set this entry runs, so nothing is "
            "re-measured here: funded on the owner's own plan it returns +499.9% against a "
            "deposit-matched SPY TR's +257.2% (12.8% a year against 7.2%), max DD 19.6%, PF 2.09 "
            "and 2,548 trades all pass, on a recorded DSR of 0.934 at its recorded N=88. Nothing "
            "failed: it is the first roster entry whose variant clears every dev check. It has "
            "never had a test-window look. It is RAW-FR-GT's book with only the name count moved, "
            "20 to 35, and it replaces it. The width answer is M0152's, measured on the "
            "survivorship-check store, where the twenty-name book falls 25.05% -- outside the "
            "owner's 25% bar -- against 20.11% at thirty-five names for slightly more money; that "
            "check-store reading was taken on the target-band twin M0139-N35-TBAND, which differs "
            "from this variant on dev by 0.012 points of drawdown. Over 2009-2015 on that same "
            "store both widths lose to SPY, and thirty-five loses by more (-1.7 points a year "
            "against -0.2): the width case is a drawdown case, not a return case, and that is the "
            "risk of this admission. On paper as the controlled comparison against RMW-FR-GT: the "
            "same picks without the brake"
        ),
    ),
```

**5b. Append the retired `RAW-FR-GT` row at the end of the tuple**, replacing the closing `)` at
`:1325`. Every field but `sort` and `status` is byte-for-byte what it is today — the `gate_note` in
particular is a closed record of why it was admitted and is **not** rewritten:

```python
    # 021: retired. The owner moved the roster to thirty-five names (2026-10-14) and RAW35-FR-GT
    # is the same book at that width. `status`, `sort` and `paper_end` are outside the frozen
    # spec, so this entry's digest is unchanged and it keeps every row it ever wrote.
    RosterRow(
        id=RAW_GT_ID,
        name="RAW · Unbraked momentum",
        sub="Top 20 by rise beyond the market, no brake, monthly, fractional shares, real Gotrade fees",
        icon="zap",
        is_champion=False,
        is_benchmark=False,
        sort=20,
        engine="book",
        rules_id="monthly-hold-frac-gotrade",
        object_name="RESIDMOM",
        registry_id=None,
        gate_note=(
            "Lab M0007 dev window only (1996-01-03..2015-10-16), in whole shares at the assumed "
            "0.1% a side: beats SPY TR (+1,502.2% vs +351.4%), max DD 19.6%, PF 2.16 and 1,596 "
            "trades all pass, on a recorded DSR of 0.914 at its recorded N=85; its method was "
            "rejected under the older 15% drawdown bar. Never had a test-window "
            "look. Re-measured at Gotrade's real fees (449fa34, report only) it returns +1,126% "
            "against SPY's +350% at the same fees. Successor of RAW-FR, which paid the assumed "
            "rate. On paper as the controlled comparison against RMW-FR-GT: the same book without "
            "the brake"
        ),
        status="retired",  # 021: superseded by RAW35-FR-GT, which holds thirty-five names
    ),
)
```

**Also update the "WHAT DOES NOT CHANGE" paragraph of the 017 block comment** at `:923–926` (four
lines, immediately above the first `RosterRow`), which says *"The books still hold 20 names … if it
is ever answered differently the answer lands as a FURTHER entry under this same rule."* That is
now history, and 021 is the further entry it predicted. Replace those four lines with:

```python
    # WHAT DOES NOT CHANGE HERE. The books still hold 20 names at 017. The fee case for holding
    # fewer is a two-month transient under the funding plan: measured, by month 3 a 20-name book
    # pays 0.614% and an 11-name book 0.612%. How many names to hold is a question about returns
    # and about what one collapsing holding can do, not about fees -- and 021 is the FURTHER entry
    # this paragraph said such an answer would have to be: RAW35-FR-GT at thirty-five names, with
    # RAW-FR-GT retired beside it. Not one digest above moved to do it.
```

**Impact:** `ROSTER` gains one entry; `ROSTER_IDS` becomes 20 ids; `active(ROSTER)` keeps six
entries (`RAW35-FR-GT` replaces `RAW-FR-GT`); `MAX_LOOKBACK_BARS` stays 426 (`RMW-FR-GT`'s 426 is
still the longest, and `RAW35-FR-GT`'s 401 equals `RAW-FR-GT`'s). Not one pinned digest moves —
proved in the Verified Facts table.

---

### Step 6: The evidence key
**File:** `engine/src/seer_engine/strategies/evidence.py:689`

**Change:** one key, mapping the new resolver name to the **existing** `residmom_evidence`.
Verified: `residmom_evidence(market, params, data_date, symbols)` takes `params: Any` and narrows it
with `_typed("RESIDMOM", params, ResidParams)`; the only use of `p.inner.top` is through
`factor_rows`, so it is correct at any width. The `"RESIDMOM"` string in `_typed` is an error-message
label only and is deliberately left as is — it names the *function*, not the key.

**Code — replace the `EVIDENCE` literal's tail:**

```python
    "RESIDMOM": residmom_evidence,
    "RESIDMOM35": residmom_evidence,  # 021: the same book at 35 names; the function is width-agnostic
    "REGIME": regime_evidence,
    "MINVAR": minvar_evidence,
}
```

**Impact:** `test_every_roster_object_but_the_benchmark_has_evidence` (which pins
`set(EVIDENCE) == set(RESOLVER) - {BENCHMARK_OBJECT}`) stays green. `promote`'s `_check_evidence`
would pass — though `promote` never gets that far (F1).

---

### Step 7: The migration
**File:** `db/migrations/021_roster_width_35.sql` (new; `020_sean_own_orders.sql` is the last today)

**Change:** insert the new row, retire `RAW-FR-GT`, renumber `sort`. Argued prose in 013's and
017's style — the migration explains the **decision**, with numbers.

**Code (whole file):**

```sql
-- Seer schema v21: the roster holds thirty-five names, not twenty (owner, 2026-10-14).
--
-- The owner's instruction, verbatim: "let's change our seer roster to hold 35 stocks instead of
-- 20". He mirrors this roster with his own money, so this migration moves what he actually buys.
--
-- THE EVIDENCE. M0152 measured the roster's own picking rule at seven widths on both price
-- histories. On the survivorship-check store -- the history that keeps the companies that went
-- bankrupt, were bought or were renamed -- the roster's twenty-name book falls 25.05%, OUTSIDE the
-- owner's own 25% bar, while a thirty-five-name book falls 20.11% and earns slightly MORE:
-- 12.11% a year against 11.98%. MAR peaks at thirty-five on both stores. The full curve, with
-- trough dates and era columns, is docs/lab/survivorship/roster-width-curve-2026-10-14.csv.
--
-- THE MECHANISM, DATED RATHER THAN INFERRED. Every width's worst fall on both stores is
-- 1998-06 -> 1998-08 with exactly one exception: the twenty-name book on the check store, which
-- troughs 2006-03 -> 2006-07. SPY went 3.71 -> 3.62 in that window -- a 2% dip that made a new
-- high by September -- while the twenty-name book lost 21.8%. By era and by width (20 -> 70):
--     1998     21.6 19.2 19.9 19.7 19.4 18.7 18.0    3.6 pts -- width barely helps
--     dot-com   9.4  6.7  4.3  5.0  6.5  6.6  5.1
--     2006     21.8 18.9 18.8 16.2 15.1 14.8 12.9    8.9 pts -- the ONLY width-sensitive episode
--     2008-09   9.1  9.3  9.5 10.1 10.0  9.7  8.2    the gate's best work is the famous crashes
--     2010-15   9.9 10.2 10.1 10.4 11.1 10.7 10.6
-- The SPY 200-day gate handles MARKET falls and handles them well. Width handles the single
-- holding that collapses while the market is fine, and in twenty years that happened once. What
-- makes it more than a coin flip is that the one episode is the ORDINARY kind of accident -- a
-- company failing in a rising market -- not a crisis that may not repeat.
--
-- WHICH VARIANT, AND WHY NOT THE OTHER ONE. The new entry's params are lab trial M0139-N35-EBAND:
-- M0007-N20-RAW's screen, ranking and SPY 200-day filter verbatim, with ONE field moved,
-- inner.top 20 -> 35, on rules preset monthly-hold-frac-gotrade -- the SAME preset RAW-FR-GT runs
-- today. M0139 also recorded M0139-N35-TBAND, which is the same book on monthly-hold-frac-gotrade-
-- tband (resize_basis = "target"). Taking the tband twin would change the width AND the rebalance
-- basis at once, and would break the one comparison RAW exists on this roster to provide: the same
-- picks WITH the volatility brake (RMW-FR-GT, still on the equity basis) against the same picks
-- without it. The owner asked for a width change. This is a width change and nothing else.
--
-- THE CAVEAT THAT TRAVELS WITH THE HEADLINE NUMBERS. The 20.11% / 12.11% check-store reading above
-- was measured on M0139-N35-TBAND, not on the M0139-N35-EBAND being admitted here. On the dev
-- store the two differ by 0.012 points of drawdown (0.19590 vs 0.19602) and 0.19 points of yearly
-- return (0.36913 vs 0.37106). The width conclusion transfers; the check-store number is the
-- twin's, and this migration says so rather than implying a measurement nobody took.
--
-- THE SECOND CAVEAT, AND THE RISK OF THIS ADMISSION. On the check store over 2009-2015 -- the
-- years most like today -- BOTH widths lose to a deposit-matched SPY, and the wider book loses by
-- more: -0.2 points a year at twenty names, -1.7 at thirty-five. The case for width is a drawdown
-- case, not a return case. The headline 12.11% is a twenty-year average that was earned before
-- 2009, as every edge in this lab was.
--
-- WHAT THE LAB SAYS ABOUT THE VARIANT. M0139-N35-EBAND is DEV-ELIGIBLE: funded on the owner's own
-- plan it returns +499.9% against a deposit-matched SPY TR's +257.2% (12.8% a year against 7.2%),
-- max DD 19.6%, PF 2.09, 2,548 trades, recorded DSR 0.934 at its recorded N=88 -- nothing failed.
-- It is the first roster entry whose variant clears every dev check. It has still never had a
-- test-window look AND IT NEVER WILL: the hard gate blocks M0139 on kin, because M0021, M0022 and
-- M0029 already read test-failed in the same family and this book moves with M0021's tested one at
-- 0.95 residual correlation. "Not tested yet" is the wrong reading; the lab will not spend a look
-- on this line at all. That is exactly the case paper/roster.py's module docstring describes as
-- the deliberate divergence from the lab's design: a lab test pass is a SUFFICIENT basis for a
-- paper entry, never a necessary one, because paper trading is how a near-miss earns the right to
-- be taken seriously. So the admission basis is the owner's (owner-override) and not the lab's,
-- and no test-window look is spent by this migration or anywhere near it.
-- M0139's own recorded verdict reads "Twenty names still wins"; that was written on the dev
-- store alone, before M0147 and M0152 showed the dev store cannot see the holdings that collapsed
-- and left. The verdict is a closed record and is NOT edited; the correction lives here and in
-- paper/roster.py's LAB_PROVENANCE.
--
-- WHY A NEW ID AND NOT AN EDIT. `inner.top` is in the frozen spec (roster.spec -> params), so
-- moving it on a STARTED entry changes its digest and paper/store.py's check_digest refuses the
-- next night with a SpecMismatch -- the whole paper night rolled back, runs.paper_status = failed.
-- docs/runbooks/paper-trading.md states the rule and 010, 011, 013 and 017 are the precedents. The
-- predecessor is RETIRED here, not deleted: a retired entry keeps every row it ever wrote and
-- stays on the leaderboard.
--
-- WHY THE MIGRATION AND NOT `promote`. Every roster row since 007 has been what
-- `promote --method … --candidate … --id … --retire …` writes on the live database, with the
-- migration writing it everywhere else byte for byte. That is not available here, and the reason
-- is mechanical: a new width needs a new paper.roster.RESOLVER key bound to the SAME allocator
-- object (a Binding carries the params, and the params are in the spec), and
-- commands/promote.py's object_name_of refuses an object that two resolver keys name, because the
-- key is part of the frozen digest. So RESIDMOM now has two names and `promote` can place neither;
-- this migration is the only writer of the row, on the live database and everywhere else alike. It
-- also means no lab.store.record_promotion note is written: lab/lab.sqlite is untouched by this
-- change, and the roster states the provenance on its own side as it always has.
--
-- MOM-FR-GT IS NOT WIDENED HERE. It is the roster's other twenty-name book, and it has never been
-- measured at any width on any store. Widening it on M0152's number would apply a measurement of
-- the residual-momentum picking rule to a different picking rule. Its number is being measured
-- separately; if it warrants a width change that is its own argued commit, not a retrofit into
-- this one. RMW-FR-GT (14.3% recorded fall, well inside the bar, no 35-name variant ever run) and
-- MVW-FR-GT (already thirty names) are untouched for the same reason.
--
-- NOT TOUCHED. The §1 real-money bar (18 months of paper, beat SPY, PF >= 1.3, max DD <= 20%, a
-- 10-year backtest), which changes only through a dated owner revision. backtest/registry.py,
-- which is the P7a dev-run candidate set with candidate_digest pinned. Any lab row.
--
-- The row below is byte for byte paper/roster.py's SEED_ROWS (the migration-equality test,
-- tests/test_paper_roster.py::test_the_migration_rows_equal_the_seed_rows). paper_start, the
-- frozen spec and the paper clock are written by the entry's first night, as for every new entry.
INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id,
                        object_name, registry_id, gate_note, gate_applicable, promoted_from) VALUES
  ('RAW35-FR-GT', 'RAW35 · Unbraked momentum', 'Top 35 by rise beyond the market, no brake, monthly, fractional shares, real Gotrade fees', 'zap', false, false, 4, 'book', 'monthly-hold-frac-gotrade', 'RESIDMOM35', NULL, 'Lab M0139 dev window only (1996-01-03..2015-10-16), already in fractional shares at Gotrade''s measured fees -- the same rule set this entry runs, so nothing is re-measured here: funded on the owner''s own plan it returns +499.9% against a deposit-matched SPY TR''s +257.2% (12.8% a year against 7.2%), max DD 19.6%, PF 2.09 and 2,548 trades all pass, on a recorded DSR of 0.934 at its recorded N=88. Nothing failed: it is the first roster entry whose variant clears every dev check. It has never had a test-window look. It is RAW-FR-GT''s book with only the name count moved, 20 to 35, and it replaces it. The width answer is M0152''s, measured on the survivorship-check store, where the twenty-name book falls 25.05% -- outside the owner''s 25% bar -- against 20.11% at thirty-five names for slightly more money; that check-store reading was taken on the target-band twin M0139-N35-TBAND, which differs from this variant on dev by 0.012 points of drawdown. Over 2009-2015 on that same store both widths lose to SPY, and thirty-five loses by more (-1.7 points a year against -0.2): the width case is a drawdown case, not a return case, and that is the risk of this admission. On paper as the controlled comparison against RMW-FR-GT: the same picks without the brake', true, 'M0139')
ON CONFLICT (id) DO NOTHING;

-- Retiring stamps paper_end with the last session the entry actually traded, which is
-- paper_state.last_session -- exactly what paper/store.py's `retire` writes, and NULL for an entry
-- that never started. Nothing else is read or written: no equity_snapshots, orders,
-- book_positions, book_targets, book_fills, book_trades or paper_state row is touched, and
-- RAW-FR-GT keeps its whole track record and stays on the leaderboard.
UPDATE strategies AS s SET
    status = 'retired',
    paper_end = (SELECT ps.last_session FROM paper_state ps WHERE ps.strategy_id = s.id)
WHERE s.id = 'RAW-FR-GT' AND s.status = 'active';

-- Sort is display order: the six that trade come first, then the fourteen that are retired, in the
-- order they were added. RAW35-FR-GT takes the slot RAW-FR-GT held, so the new book sits beside
-- RMW-FR-GT, the braked twin it is the control for. `sort` is not in the frozen spec, so no digest
-- moves -- the same reason 017 could renumber all thirteen.
UPDATE strategies SET sort = 20 WHERE id = 'RAW-FR-GT';
```

**The `gate_note` in the SQL above and the one in Step 5a are byte-identical** (verified: the SQL
literal with `''` collapsed to `'` equals the Python concatenation exactly, 1,260 characters). That
equality is what `test_the_migration_rows_equal_the_seed_rows` compares; if you reword one, reword
the other in the same edit and re-check it before running the suite. The same holds for `name`
(`RAW35 · Unbraked momentum`) and `sub`, neither of which contains an apostrophe.

**Impact:** on a fresh database the roster reads
`SPY-GT, C-GT, RMW-FR-GT, RAW35-FR-GT, MOM-FR-GT, MVW-FR-GT` then the fourteen retired, ending
`MVW-FR, RAW-FR-GT`. On the live Neon database the nightly's **Migrate** step applies it; the
**Paper** step then starts `RAW35-FR-GT`'s clock on its first unpaused night.

---

### Step 8: `tests/test_paper_roster.py` — one new pin, zero moved pins
**File:** `engine/tests/test_paper_roster.py`

**8a. The id constant and the id tuples (`:94`, `:98`).** Replace the 017 id block's tail and the
two tuples:

```python
SPY_GT = "SPY-GT"
C_GT = "C-GT"
RMW_GT = "RMW-FR-GT"
RAW_GT = "RAW-FR-GT"
MOM_GT = "MOM-FR-GT"
MVW_GT = "MVW-FR-GT"
# 021, the width change (owner, 2026-10-14): the same residual-momentum book at 35 names instead
# of 20, on the same rule set, as a NEW id -- `inner.top` is in the frozen spec, so moving it on
# RAW-FR-GT would have failed its next night. RAW-FR-GT is retired beside it.
RAW35_GT = "RAW35-FR-GT"
#: every entry that ever traded under the assumed flat rate, plus the three 013 retired and the one
#: 021 retires; none of them ever stepped a paper session, and every one of them keeps every row it
#: wrote.
RETIRED = (F4, F1, FND, RM, "A", F4_FR, F1_FR, "SPY", "C", RMW, RAW, MOM, MVW, RAW_GT)
ACTIVE_IDS = (SPY_GT, C_GT, RMW_GT, RAW35_GT, MOM_GT, MVW_GT)
```

**8b. The pin (`:133`).** Append to `PINS`, inside the dict, after `MVW_GT`:

```python
    MVW_GT: "f463f4af9aeb3157029979df64e4923a55ea675991d4fddbfe992a3a685f4df2",
    # 021: the width change. ONE new pin and NOT ONE MOVED PIN -- that is the whole point of this
    # block. RAW-FR-GT's digest above is byte-identical to what 017 wrote, because `status`, `sort`
    # and `paper_end` are deliberately outside the frozen spec; retiring it moved nothing. The new
    # entry digests differently from it for exactly one reason: `params["inner.top"]` reads "35".
    RAW35_GT: "f9def72ae37bd7534807e5957a1e48917fe54322b65a5bbb0cd2898db41c443f",
}
```

**8c. `test_the_roster_is_the_handover_entries_in_sort_order` (`:155`).**

```python
def test_the_roster_is_the_handover_entries_in_sort_order():
    assert ROSTER_IDS == (
        SPY_GT, C_GT, RMW_GT, RAW35_GT, MOM_GT, MVW_GT,
        "SPY", "A", F4, F1, "C", FND, F4_FR, F1_FR, RM, RMW, RAW, MOM, MVW, RAW_GT,
    )
    assert [e.sort for e in ROSTER] == list(range(1, 21))
    assert "B" not in ROSTER_IDS
```

**8d. `test_lookbacks` (`:320`).**

```python
def test_lookbacks():
    assert {e.id: e.lookback for e in ROSTER} == {
        SPY_GT: 1, C_GT: 200, RMW_GT: 426, RAW35_GT: 401, MOM_GT: 379, MVW_GT: 253,
        RAW_GT: 401,
        "SPY": 1, "A": 200, F4: 253, F1: 200, "C": 200, FND: 20, F4_FR: 253, F1_FR: 200,
        RM: 401, RMW: 426, RAW: 401, MOM: 379, MVW: 253,
    }
    # FND's lookback is the 20-bar dollar-volume window: a filing's availability is its `filed`
    # date, not a bar count. RMW's 426 is the roster's longest, which is why the night loads 640
    # calendar days, not 550 -- unchanged by 017 (which adds no new object) and unchanged by 021
    # (whose new object is RESIDMOM at a different width: `resid_lookback` does not read `top`).
    assert MAX_LOOKBACK_BARS == 426
```

**8e. The two `promoted_from` sets (`:592` and `:783`).** Both must gain `RAW35_GT`. In
`test_read_roster_rows_reads_the_new_columns_and_defaults_them`:

```python
    assert {r.id for r in rows.values() if r.promoted_from is not None} == {
        FND, RM, RMW, RAW, MOM, MVW, RMW_GT, RAW_GT, MOM_GT, MVW_GT, RAW35_GT,
    }
```

and the identical set literal in `test_lab_provenance_agrees_with_the_promoted_from_column`:

```python
    assert {i for i, r in rows.items() if r.promoted_from is not None} == {
        FND, RM, RMW, RAW, MOM, MVW, RMW_GT, RAW_GT, MOM_GT, MVW_GT, RAW35_GT,
    }
```

`assert all(r.paper_end is None for r in rows.values())` at `:589` **stays as it is**: the scratch
database has no `paper_state` rows, so 021's subselect writes NULL. Leave it — it is a real
assertion about the migrated roster, and it is the thing that proves the retirement did not invent
a date.

**8f. `LAB_DERIVED` (`:647`).**

```python
LAB_DERIVED = (F4, F1, FND, F4_FR, F1_FR, RM, RMW, RAW, MOM, MVW,
               RMW_GT, RAW_GT, MOM_GT, MVW_GT, RAW35_GT)
```

**8g. `test_the_entries_name_the_variants_the_roster_advertises` (`:673`).** Add the new line at the
end of the function body:

```python
    # 021: the width change names M0139's variant, not M0007's -- the 35-name rung is M0139's
    # recorded trial, and the roster must say so rather than claiming M0007 measured a width it
    # never ran.
    assert (entry(RAW35_GT).lab_provenance.method_id,
            entry(RAW35_GT).lab_provenance.candidate_id) == ("M0139", "M0139-N35-EBAND")
    assert entry(RAW_GT).lab_provenance.candidate_id == "M0007-N20-RAW"
```

**8h. `test_every_override_states_its_basis_and_a_reason` (`:685`) — F2(2).** The two set
assertions at the end are replaced; everything above them is unchanged:

```python
def test_every_override_states_its_basis_and_a_reason():
    for sid, p in LAB_PROVENANCE.items():
        assert p.basis in BASES, sid
        assert p.lab_status in lab_store.STATUSES, sid
        if p.basis == "owner-override":
            assert p.reason.strip(), f"{sid}: an override must say why"
    # Every roster entry is still an override: not one of them has had a test-window look, and the
    # lab's own route to paper (design section 3) runs through one. What CHANGED on 2026-10-14 is
    # what they were overridden FROM. The fourteen entries up to 017 were admitted at 'rejected' --
    # they failed the dev gate too. RAW35-FR-GT (021) is the first admitted at 'dev-eligible': its
    # variant M0139-N35-EBAND fails nothing on the dev window, and the only thing the owner is
    # overriding is the missing test-window look. Both statuses are named here rather than
    # collapsed, because the difference is the admission's whole character.
    assert {p.basis for p in LAB_PROVENANCE.values()} == {"owner-override"}
    assert {p.lab_status for p in LAB_PROVENANCE.values()} == {"rejected", "dev-eligible"}
    assert LAB_PROVENANCE[RAW35_GT].lab_status == "dev-eligible"
    assert {sid for sid, p in LAB_PROVENANCE.items() if p.lab_status != "rejected"} == {RAW35_GT}
    assert set(BASES) == set(lab_store.PROMOTION_BASES)
```

**8i. `test_every_provenance_matches_the_committed_lab_database` (`:724`) — F2(3).** Replace the
`if p.basis == "owner-override": … else: …` block (and nothing else in the function) with:

```python
            # What an override OVERRIDES is the lab's own route to this roster, and that route is
            # the TEST window (design section 3), not the dev gate. So the check is the exact
            # mirror of the test-passed branch below: an owner-override must have NO passed
            # test-window trial. (It used to assert the dev trial FAILED, which was true of the
            # fourteen entries admitted up to 017 and is not a property of an override: 021's
            # M0139-N35-EBAND fails nothing on dev and has still never been looked at on test.)
            # `AND method_id = ?` is new: the inherited query filtered on candidate_id alone.
            # Harmless while only the test-passed branch ran it (candidate ids are method-
            # prefixed and the lab refuses a second look), but this restatement runs it for all
            # fifteen entries, so it gets the filter while the line is open.
            passed = conn.execute(
                "SELECT eligible FROM trials WHERE method_id = ? AND candidate_id = ? "
                "AND window = 'test'",
                (p.method_id, p.candidate_id),
            ).fetchone()
            if p.basis == "owner-override":
                assert passed is None or passed["eligible"] == 0, (
                    f"{sid}: the basis says owner-override, but {p.candidate_id} has a PASSED "
                    f"test-window trial -- the lab's own route admitted it, and nothing was "
                    f"overridden. Fix the basis to 'test-passed'"
                )
            else:
                assert passed is not None and passed["eligible"] == 1, (
                    f"{sid}: the basis says test-passed, but no passed test-window trial for "
                    f"{p.candidate_id} is recorded"
                )
```

The `dev` row is still fetched above and still asserted non-`None` ("`{candidate_id}` is not a
recorded dev trial of `{method_id}`"), which is the check that actually binds the roster to the
lab's record — keep it exactly as it is.

**Reconciler's note on what this restatement costs, so it is on the record.** The *cross-database*
teeth on one particular fact — "every entry up to 017 was admitted at `rejected`" — are reduced,
not relocated: today `dev["eligible"] == 0` proves it against `lab/lab.sqlite`, and afterwards it
is proved only by 8h's set assertion over the `LAB_PROVENANCE` literals in `roster.py`. 8h is the
compensating control and it is stronger in the dimension that matters —
`{sid for sid, p in LAB_PROVENANCE.items() if p.lab_status != "rejected"} == {RAW35_GT}` names the
single permitted exception, so a second dev-eligible admission cannot slip in unremarked. Do not
weaken 8h while weakening this. The restatement itself is sound and was checked three ways:
`lab/store.py:216 promotion_basis` already computes `owner-override` for every status but
`test-passed` and `paper`, `dev-eligible` included — so the old assertion contradicted the
implementation; the governing prose (`roster.py` module docstring, `LabProvenance`'s docstring,
`BASES`, and method-lab design §7.4/§8) ties the basis to the **test window** and never to the dev
gate; and the roster already violates the old reading in substance, since `M0007-N20-RAW` passes
the dev gate under the bars in force today and sits on the roster as an override — the assertion
survives for it only because its frozen `trials` row still carries a superseded 15% drawdown label.

**8j. `test_every_active_entry_pays_gotrade_and_nothing_retired_changed` (`:806`).** The
predecessor/successor pair list gains the 021 swap:

```python
    # and the predecessors are retired, not deleted: every one keeps its row and its digest.
    for old, new in (("SPY", SPY_GT), ("C", C_GT), (RMW, RMW_GT), (RAW, RAW_GT),
                     (MOM, MOM_GT), (MVW, MVW_GT), (RAW_GT, RAW35_GT)):
        assert entry(old).status == "retired", old
        assert spec_digest(spec(entry(old))) == PINS[old], old
        assert entry(new).status == "active", new
        assert spec_digest(spec(entry(new))) != PINS[old], new
```

That one added pair is the strongest single statement this phase can make: `RAW-FR-GT` is retired,
its digest is **still the pinned one**, and the new entry's is different.

**Impact:** `test_digests_are_pinned` compares `{e.id: digest}` against `PINS` as a whole dict, so
exactly one key is added and fourteen values are proved unchanged by the comparison itself.

---

### Step 9: `tests/test_promote_command.py` — the resolver-inverse invariant, restated
**File:** `engine/tests/test_promote_command.py:155`

**Change:** `test_object_name_of_is_the_resolvers_inverse` asserts the inverse holds for *every*
binding, which is false once two keys share an object. Replace it with the invariant that is
actually true, plus an explicit test of the refusal and what it costs.

**Code — replace the whole function:**

```python
def test_object_name_of_is_the_resolvers_inverse_where_the_inverse_exists():
    """RESOLVER maps a name to a roster.Binding; the live object is binding.obj, None for the
    benchmark (which has no object to name).

    The inverse is a function only for an object ONE key names. Since 021 that is not every
    object: a width change binds the SAME allocator under a second key, because a Binding carries
    the params and the params are in the frozen spec. For such an object `object_name_of` must
    REFUSE rather than pick one of the two -- the key is part of the digest, so an object with two
    names has two digests, and guessing would silently freeze a strategy under the wrong one.
    """
    by_obj: dict[int, list[str]] = {}
    for name, binding in roster.RESOLVER.items():
        if binding.obj is not None:
            by_obj.setdefault(id(binding.obj), []).append(name)
    assert by_obj, "the resolver names no objects at all"
    for names in by_obj.values():
        if len(names) == 1:
            obj = roster.RESOLVER[names[0]].obj
            assert promote.object_name_of(obj) == names[0]
        else:
            obj = roster.RESOLVER[names[0]].obj
            with pytest.raises(promote.NotPromotable, match="names"):
                promote.object_name_of(obj)


def test_a_second_width_of_one_allocator_takes_promote_off_the_table():
    """021's cost, asserted so it is never rediscovered as a surprise at 23:00.

    RESIDMOM is on the roster twice -- RAW-FR-GT at 20 names (retired) and RAW35-FR-GT at 35 --
    under two resolver keys with two params. `promote` can therefore place NEITHER, and a roster
    row for this allocator is written by a migration instead (db/migrations/021_roster_width_35.sql
    says so in its own prose). The refusal names both keys, which is what tells an operator what
    actually happened.
    """
    residmom = roster.RESOLVER["RESIDMOM"].obj
    assert roster.RESOLVER["RESIDMOM35"].obj is residmom
    assert roster.RESOLVER["RESIDMOM35"].params is not roster.RESOLVER["RESIDMOM"].params
    with pytest.raises(promote.NotPromotable) as exc:
        promote.object_name_of(residmom)
    assert "RESIDMOM" in str(exc.value) and "RESIDMOM35" in str(exc.value)
    assert "exactly one" in str(exc.value)
```

**Impact:** the suite now states the consequence rather than tripping over it.
`test_object_name_of_refuses_an_object_the_resolver_does_not_name` and
`test_the_resolver_must_name_the_allocator_first` are untouched: both use objects with zero or one
name.

---

### Step 10: The three roster id lists
**Files:** `engine/tests/test_paper_store.py:59`, `engine/tests/test_paper_check.py:60`,
`engine/tests/test_migrate.py:292`

**10a. `test_paper_store.py:57–64`:**

```python
def test_read_strategies_returns_the_roster_rows_in_sort_order(pg):
    rows = store.read_strategies(pg)
    # 017 put the six Gotrade-fee successors at the head and moved the thirteen below them.
    # 021 swapped one of the six: RAW35-FR-GT (35 names) takes RAW-FR-GT's slot, and RAW-FR-GT
    # goes to the end of the retired block.
    assert [r.id for r in rows] == [
        "SPY-GT", "C-GT", "RMW-FR-GT", "RAW35-FR-GT", "MOM-FR-GT", "MVW-FR-GT",
        "SPY", "A", BOOK_ID, TIMING_ID, "C", "FND", f"{BOOK_ID}-FR", f"{TIMING_ID}-FR", "RM-FR",
        "RMW-FR", "RAW-FR", "MOM-FR", "MVW-FR", "RAW-FR-GT",
    ]
```

**10b. `test_paper_check.py:58–62`.** `ROSTER_IDS` and `RETIRED_IDS` in that file are its **own**
synthetic world and must **not** change — the file's own comment says so. Only `ALL_IDS`, which is
"every row the board shows, in `sort` order", moves:

```python
#: Every row the board shows, in `sort` order -- including the six 017 added and the one 021 added,
#: which are retired in this world and so are checked but never stepped.
ALL_IDS = ("SPY-GT", "C-GT", "RMW-FR-GT", "RAW35-FR-GT", "MOM-FR-GT", "MVW-FR-GT",
           "SPY", "A", "F4-MOM12-N20-TREND", "F1-SPY-SMA200-M", "C", "FND", F4, F1, "RM-FR",
           "RMW-FR", "RAW-FR", "MOM-FR", "MVW-FR", "RAW-FR-GT")
```

**10c. `test_migrate.py:290–297`:**

```python
    # 017 renumbered `sort`: the six Gotrade-fee successors that trade come first, then the
    # thirteen it and its predecessors retired, in the order they were added. 021 put RAW35-FR-GT
    # in RAW-FR-GT's slot and sent RAW-FR-GT to the end of the retired block.
    assert [r[0] for r in rows] == [
        "SPY-GT", "C-GT", "RMW-FR-GT", "RAW35-FR-GT", "MOM-FR-GT", "MVW-FR-GT",
        "SPY", "A", "F4-MOM12-N20-TREND", "F1-SPY-SMA200-M", "C", "FND",
        "F4-MOM12-N20-TREND-FR", "F1-SPY-SMA200-M-FR", "RM-FR", "RMW-FR",
        "RAW-FR", "MOM-FR", "MVW-FR", "RAW-FR-GT",
    ]
```

The `C` and `FND` sort assertions just below it (`11` and `12`) are unaffected: 021 renumbers only
`RAW-FR-GT`.

**10d. `tests/test_evidence.py:449–453`.** Add the new key so the width is actually exercised
against `labkit.smoke_market()` rather than only type-checked by the table test:

```python
LAB_BOOKS = (
    ("RESIDMOM", roster.RESIDMOM_PARAMS),
    ("RESIDMOM35", roster.RESIDMOM35_PARAMS),
    ("REGIME", roster.REGIME_PARAMS),
    ("MINVAR", roster.MINVAR_PARAMS),
)
```

`test_the_lab_books_explain_every_stock_they_pick` asserts
`set(out) == {t.symbol for t in targets}`, which holds at any width — if the smoke fixture holds
fewer than 35 eligible names the allocator simply targets all of them and every one is explained.
If that parametrisation turns out to pick nothing on `LAB_DATE` (the test's own
`assert targets, f"{name} picked nothing"` would say so), drop this sub-step: it is a bonus check,
not a requirement, and the table test at `:88` is the binding one.

---

### Step 11: Regenerate `web/data/lab.json` — under the lab write lock (F3)

**This is the only step that touches a file another phase also writes. Do it LAST,** after
everything else in this phase is green except the two tests that depend on the snapshot
(`test_the_committed_snapshot_is_the_export_of_the_committed_database` and the `web` suite).

**Why it is unavoidable:** `lab/store.py:2967` builds the snapshot's `paper` block from
`roster.LAB_PROVENANCE` filtered by `roster.active()`. Editing `roster.py` changes that block;
`engine/tests/test_lab_snapshot.py:1054` compares the committed file byte for byte.

#### `web/data/lab.json` — one generator, one commit shape, one recovery

Reconciled 2026-10-14, settling a contradiction between the index's old phase-2 boundary and
phase 2's own measurement. The whole rule, binding on all five phases:

1. **It is never hand-edited, and never `git checkout --`'d back.** It is generated output. The
   only correct copy is the export of the `lab/lab.sqlite` committed beside it.
2. **Lab phases (1, 3, 4, 5) regenerate it with `lab stage`**, which `git add`s it *together with*
   `lab/lab.sqlite`, and commit the pair with a bare `git commit -m …` and nothing else in that
   commit (`seer-lab-stage-commit-needs-the-index`).
3. **Phase 2 regenerates it with `lab export-json` and commits it ALONE by pathspec.**
   `export-json` writes the same bytes to the same path and never touches the git index
   (`commands/lab.py:_export_json` vs `_stage`); `lab stage` would `git add lab/lab.sqlite` too,
   and phase 2 writes no lab row, so staging it would sweep another phase's in-flight trials into
   phase 2's commit. `commands/lab.py:1757-1761` names `export-json` for exactly this situation.
4. **Phase 2 must regenerate it — "phase 2 does not touch the lab's artifacts" cannot hold and is
   withdrawn.** `lab/store.py:2966-2977` builds the snapshot's `paper` block from
   `roster.LAB_PROVENANCE` filtered by `roster.active()`. Retiring `RAW-FR-GT` changes the
   snapshot's bytes (measured: the `paper` array loses one element), and
   `engine/tests/test_lab_snapshot.py:1054` byte-compares the committed file against a live
   export. CI runs that test.
5. **Either generator runs inside the lab write lock**, and the holder has already proved
   `git diff --quiet HEAD -- lab/lab.sqlite`. So the snapshot committed is always the export of
   the database committed.
6. **Finding it ahead of your own commit is normal, not an error.** Another phase landed trials
   after you took your reading. Do not revert it and do not hand-merge it: bring `HEAD` forward
   with `git fetch origin && git merge --ff-only origin/main` — **never `git pull --rebase`**,
   which replays a stale `lab.sqlite` over what the other phases wrote
   (`seer-rebase-replays-stale-lab-sqlite`) — then re-run your generator and commit what comes
   out. If `git diff` is then empty, the other phase's commit already carries your change: commit
   nothing and say so in the close-out. **Whoever lands last is right, and that is by design** —
   the snapshot is a pure function of the database and the roster, so the last regeneration over
   the merged state is the only one that can be correct.

#### The lab write lock — one mechanism, defined, identical in every phase of this set

Reconciled 2026-10-14. Every phase plan and the plan index carry these exact commands. Earlier
drafts said "take the write lock" without ever defining one; `lab stage`'s own `BEGIN EXCLUSIVE`
(`commands/lab.py:2824`) covers only `write_snapshot` + `git add` and is released before the
commit, so it is **not** the lock meant here.

```bash
LAB_LOCK=/home/miftah/seer/.git/seer-lab.lock   # inside .git/: no `git add` can ever reach it

# TAKE IT. fd 9 is the handle; the kernel drops it when this shell exits, even on a crash.
exec 9>"$LAB_LOCK"
flock -w 21600 9 || { echo "lab lock still held after 6h -- find out who has it; do NOT force"; exit 1; }
echo "phase-N pid $$ $(date -Is)" >&9        # who holds it, for a human who opens the file

# PROVE THE PAIR IS CLEAN. When nobody holds the lock this must pass. If it fails, a session
# died inside its window and the tree is in an unknown state -- STOP and report, do not repair.
cd /home/miftah/seer
git fetch origin && git merge --ff-only origin/main
git diff --quiet HEAD -- lab/lab.sqlite web/data/lab.json || {
  echo "the lab pair is dirty and nobody held the lock -- STOP"; flock -u 9; exit 1; }

#   ... the critical section ...

# RELEASE.
flock -u 9
```

**The rule, in one line: you may not release the lock with `lab/lab.sqlite` or
`web/data/lab.json` differing from `HEAD`.**

**What is inside a hold.** Every command that writes a lab row — `lab survivorship` (it journals
an `observation`), `lab run`, `lab note`, `lab insight`, `lab seen`, `lab reevaluate` — plus the
`lab stage` (or, for phase 2, `lab export-json`), `git commit` and `git push` that return the pair
to clean. **`lab run` is inside the hold**, which means the four lab phases' runs queue rather
than overlap. That reverses the draft index's "the runs may overlap", and the reason is
build-green: a run leaves the shared binary `lab/lab.sqlite` dirty for its whole duration, and
while it is dirty (a) no other session can export a snapshot that matches the committed database,
so phase 2's `web/data/lab.json` commit cannot be made correct, and (b) any other phase's
`lab stage` would `git add` the half-finished run's rows into its own commit, because `lab stage`
stages the whole file. Two independent measurements agree: `lab run`s contend on one sqlite file
(phase 1 Step 5), and each run loads a whole research store at ~1 GB
(`seer-research-store-memory-budget`), so four at once is RAM pressure on a 16 GB machine. The
cost is honest and accepted: the four lab runs are serial, and the set takes as long as their sum.

**Take short holds, not one long one.** A hold that spans writing a method file starves every
other session for nothing. Each phase's plan names its own hold boundaries below; where a phase
has two or three DB-writing windows separated by file-writing work, it takes two or three holds,
each ending with a stage, a commit and a push.

**What the lock buys:** when no session holds it,
`git diff --quiet HEAD -- lab/lab.sqlite web/data/lab.json` is true. That is the only condition
under which an exported snapshot matches the database committed beside it — which is exactly what
`engine/tests/test_lab_snapshot.py:1054
test_the_committed_snapshot_is_the_export_of_the_committed_database` byte-compares, and CI runs it.

**Protocol:**

```bash
cd /home/miftah/seer

# 1. Take the lock, exactly as above. Its precondition -- `git diff --quiet HEAD --
#    lab/lab.sqlite web/data/lab.json` -- is what makes this whole step correct: it proves the
#    database on disk IS the committed database, so the snapshot you are about to export is the
#    export of the database that is already in HEAD. If it fails, a lab phase is mid-run; release
#    and retry rather than exporting against a half-written database.
exec 9>/home/miftah/seer/.git/seer-lab.lock
flock -w 21600 9 || { echo "lab lock still held after 6h -- find out who has it; do NOT force"; exit 1; }
echo "phase-2 pid $$ $(date -Is)" >&9
git fetch origin && git merge --ff-only origin/main
git diff --quiet HEAD -- lab/lab.sqlite web/data/lab.json || {
  echo "a lab phase is mid-run -- release, wait, retry"; flock -u 9; exit 1; }

# 2. Hash lab.sqlite first: any `lab` subcommand migrates it on connect, even a read
#    (seer-lab-commands-migrate-lab-sqlite-on-connect).
BEFORE=$(md5sum lab/lab.sqlite | cut -d' ' -f1)

# 3. export-json, NEVER `lab stage`: stage git-adds lab/lab.sqlite too, and this swarm shares one
#    index. commands/lab.py:1758 names export-json for exactly this situation.
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab export-json

# 4. If the hash moved, the read migrated the file. Restore it by path and re-check.
AFTER=$(md5sum lab/lab.sqlite | cut -d' ' -f1)
[ "$BEFORE" = "$AFTER" ] || git checkout -- lab/lab.sqlite

# 5. Confirm the delta is the paper block and nothing else.
git diff --stat -- web/data/lab.json
PYTHONPATH=engine/src engine/.venv/bin/python - <<'PY'
import json, subprocess
new = json.load(open('web/data/lab.json'))['paper']
old = json.loads(subprocess.run(['git','show','HEAD:web/data/lab.json'],
                                capture_output=True, text=True).stdout)['paper']
print('removed:', [p for p in old if p not in new])
print('added  :', [p for p in new if p not in old])
PY

# 6. Commit web/data/lab.json ALONE, by pathspec. lab/lab.sqlite is NOT in this commit:
#    this phase writes no lab row (see F1), so there is nothing of the lab's to carry.
git add -- web/data/lab.json
git commit -m "..."   # see Commits below

# 7. Release the lock.
```

**Expected delta** (verified against the current file, whose `paper` block holds exactly four
entries):

```
removed: [{'strategyId': 'RAW-FR-GT', 'methodId': 'M0007', 'candidateId': 'M0007-N20-RAW',
           'labStatus': 'rejected', 'basis': 'owner-override'}]
added  : [{'strategyId': 'RAW35-FR-GT', 'methodId': 'M0139', 'candidateId': 'M0139-N35-EBAND',
           'labStatus': 'dev-eligible', 'basis': 'owner-override'}]
```

**The diff cannot show more than that, and if it does, stop.** Step 11's lock precondition
already proved `lab/lab.sqlite` is byte-identical to `HEAD`, and the `git merge --ff-only` brought
`HEAD` forward over every lab phase that has landed — so every lab row in the export is already in
the committed database, and the only thing this phase changes is the `paper` block. A larger diff
means the precondition was skipped or the lock was not actually held: release, re-take it, and
start Step 11 again rather than committing a snapshot you cannot account for.
`test_the_committed_snapshot_is_the_export_of_the_committed_database` is exactly the test that
catches getting this wrong, and CI runs it.

**If `git diff -- web/data/lab.json` is empty after the export**, a lab phase regenerated the
snapshot over your already-merged roster change and its commit already carries it. Commit nothing,
and say so in the close-out. Never hand-edit this file and never `git checkout --` it back.

**Impact:** `web/lib/sera/paper.test.ts` and the engine snapshot test both go green. The site's
leaderboard links the new entry's name to `/sera/methods/M0139` instead of `/sera/methods/M0007`.

---

### Step 12: `web/lib/sera/paper.test.ts`
**File:** `web/lib/sera/paper.test.ts`

`LabPaper.labStatus` is typed `string` (`web/lib/sera/types.ts:69`), so `'dev-eligible'` needs no
type change — verified.

**Change:** the first `it` block's `RAW-FR-GT` line, the retired-entry block, and the
variant/basis block.

**Code — replace those three blocks:**

```ts
  it('turns a lab-derived roster entry into its method page', () => {
    // The four lab-derived entries on the live roster. They are the -GT successors since the
    // 2026-10-08 Gotrade rebuild, and since 2026-10-14 the unbraked book is the 35-name one:
    // migration 021 moved the roster's width and retired RAW-FR-GT. The snapshot publishes ACTIVE
    // entries only, so the predecessors are no longer here to be looked up.
    expect(methodHref('RAW35-FR-GT')).toBe('/sera/methods/M0139');
    expect(methodHref('RMW-FR-GT')).toBe('/sera/methods/M0022');
    expect(methodHref('MOM-FR-GT')).toBe('/sera/methods/M0002');
    expect(methodHref('MVW-FR-GT')).toBe('/sera/methods/M0008');
  });

  it('has no answer for a retired entry, even one the lab did produce', () => {
    // The purged predecessors, and RAW-FR-GT, retired by 021 when the roster went to 35 names.
    // `LAB_PROVENANCE` still names all of them -- lineage belongs on the roster -- but the
    // snapshot withholds a retired entry, so the site cannot say it is "on paper".
    expect(methodHref('RAW-FR')).toBeNull();
    expect(paperOf('RMW-FR')).toBeNull();
    expect(methodHref('RAW-FR-GT')).toBeNull();
    expect(paperOf('RAW-FR-GT')).toBeNull();
  });
```

and

```ts
  it('carries the variant and the basis the entry was admitted on', () => {
    // RAW35-FR-GT is the owner-override the roster documents at length: the owner moved the book
    // from twenty names to thirty-five on evidence from the price history that keeps the companies
    // that failed, and the variant has still never had a test-window look -- which is the thing
    // being overridden. It is the first roster entry admitted at 'dev-eligible' rather than
    // 'rejected': M0139-N35-EBAND fails nothing on the dev window.
    expect(paperOf('RAW35-FR-GT')).toEqual({
      strategyId: 'RAW35-FR-GT',
      methodId: 'M0139',
      candidateId: 'M0139-N35-EBAND',
      labStatus: 'dev-eligible',
      basis: 'owner-override',
    });
  });
```

**No other `web/` change is needed.** `paperOf`/`methodHref` are id-agnostic, the leaderboard reads
`strategies` from Neon at request time, and nothing in `web/` hardcodes a roster id outside this
test file (verified by `grep -rn RAW-FR-GT web/`). `web/` is a read-only view; no component or
route is written here, so `node_modules/next/dist/docs/` is not consulted and the
`run-the-web-app` skill is used only for the optional visual check in Verification.

---

### Step 13: `.claude/skills/calculate-assets/build_audit.py`
**File:** `.claude/skills/calculate-assets/build_audit.py:11–21`

**Read this before editing.** The script's `S` constant points at a dead session scratchpad and its
`ROWS` name JSON files that no longer exist, so it cannot run as it stands: it is a one-off report
builder, not a live tool. The brief asks for the roster id → lab variant map to be updated. The
**wrong** way to do that is to rename the row to `RAW35-FR-GT` / `M0139-N35-EBAND` while it still
loads `assets.json` — a measurement that was taken on the 20-name book. That would make the script
label a 20-name result as the 35-name variant.

**Change:** keep the row as the record of the measurement that was actually taken, correct its
label, and add the roster fact. One row, two string edits and a new note line:

```python
# roster id -> (what it is, the json, the lab's formal verdict on this METHOD)
#
# 2026-10-14: migration 021 moved the roster's unbraked momentum book from twenty names to
# thirty-five (RAW35-FR-GT, lab M0139-N35-EBAND) and retired RAW-FR-GT. The row below is LEFT
# NAMING THE VARIANT IT WAS MEASURED ON -- M0007-N20-RAW, from `assets.json` -- because relabelling
# a 20-name measurement as the 35-name variant would be a lie about where the number came from.
# Rebuilding this page for the current roster means re-running calculate-assets on
# M0139-N35-EBAND first and pointing the row at that JSON.
ROWS = [
    ("MVW-FR-GT", "MVW · Steady weights", "M0008-N30-C07", f"{S}/M0008-N30-C07.json",
     "M0008", "rejected — never testable", "Re-evaluated today and still rejected at the current bars, so the lab will not give it a look."),
    ("RAW-FR-GT", "RAW · Unbraked momentum (20 names, retired 2026-10-14)", "M0007-N20-RAW", f"{S}/assets.json",
     "M0007", "dev-eligible — no formal look", "The variant you held until the roster went to thirty-five names. Measured as a report; its method has never spent a counted look."),
    ("MOM-FR-GT", "MOM · Regime momentum", "M0002-REL-85", f"{S}/M0002-REL-85.json",
     "M0002", "test-failed", "Formally tested today on the exact variant you hold. Failed beats SPY TR, max DD and PF."),
    ("RMW-FR-GT", "RMW · Braked momentum", "M0022-W-TV16", f"{S}/M0022-W-TV16.json",
     "M0022", "test-failed", "The lab tested W-TV14, its best variant, not the W-TV16 you hold. It failed three conditions."),
]
```

**Impact:** none at runtime (the script has no test and no caller in CI). The map is no longer
stale about what the roster holds, and it does not claim a measurement that was not taken.

---

### Step 14: The runbook
**File:** `docs/runbooks/paper-trading.md:30–39`

**14a. The roster table.** Replace the `RAW-FR-GT` row and the retired count:

```markdown
| Id | What it is | Engine | Rules | Backtest gate |
|---|---|---|---|---|
| `SPY-GT` | Buy and hold SPY, dividends reinvested at the ex-date close | benchmark | — | champion and yardstick; not a strategy |
| `C-GT` | Strategy C: A's first 10 ranked candidates for the session, minus every symbol whose nightly news check did not say `allow`; 5-day brackets, 4 slots, **daily** | bracket | `design-v0-gotrade` | not applicable: an LLM strategy (design §1 item 5) |
| `RMW-FR-GT` | Top 20 by rise beyond the market, picked monthly; holds less when jumpy, checked weekly | book | `monthly-rank-weekly-resize-frac-gotrade` | not passed: lab M0022 dev window only |
| `RAW35-FR-GT` | The same book as RMW with the volatility brake removed, holding **35** names | book | `monthly-hold-frac-gotrade` | not passed (never looked at): lab M0139-N35-EBAND clears every dev check |
| `MOM-FR-GT` | Top 20 by last year's rise, holding less when jumpy for itself | book | `monthly-hold-frac-gotrade` | not passed: lab M0002 dev window only |
| `MVW-FR-GT` | Top 30 by last year's rise, weighted to swing least together | book | `monthly-hold-frac-gotrade` | not passed: lab M0008 dev window only |

Fourteen earlier entries are **retired**. A retired entry keeps every row it ever wrote and stays on
the leaderboard; it only stops trading. None of the fourteen ever stepped a paper session.
```

**14b. The retirement record.** Insert after the `C-GT` is permanent paragraph (`:46`), before
*"Monthly entries decide only on the first session of a month"*:

```markdown
### 2026-10-14 — the roster went from twenty names to thirty-five

The owner's instruction: *"let's change our seer roster to hold 35 stocks instead of 20"*. He
mirrors this roster with his own money, so the change moves what he buys.

`RAW-FR-GT` is **retired** and `RAW35-FR-GT` replaces it (migration `021_roster_width_35.sql`).
It is the same book — the same screen, the same ranking, the same SPY 200-day filter, the same rule
set, the same fees — with one field moved: 20 names to 35. It is a new id because the name count is
in the frozen spec, so editing the running entry would have failed its next night with a
`SpecMismatch`. `RAW-FR-GT`'s own spec digest did not move and it keeps everything it wrote.

The evidence is M0152's width curve on the survivorship-check store, the price history that keeps
the companies that went bankrupt or were bought: there the 20-name book's worst fall is **25.05%**,
outside the owner's 25% bar, against **20.11%** at 35 names, for slightly more money a year. The
whole effect rests on one dated episode — spring 2006, when a single holding collapsed while the
market dipped 2% and made a new high by September — which is the ordinary kind of accident rather
than a crisis that may not repeat. Over 2009–2015 both widths lose to SPY on that store, and 35
loses by more: the case for width is a case about the worst fall, not about returns.

**Migration, not `promote`.** A new width needs a new `RESOLVER` key bound to the same allocator
object, and `promote`'s `object_name_of` refuses an object that two keys name (the key is part of
the frozen digest). So `promote` can no longer place any variant of this allocator, and 021 writes
the row on the live database itself. No `record_promotion` note was written, so `lab/lab.sqlite` is
untouched by this change. The next width of this book takes the same path.

`MOM-FR-GT` is **not** widened: it is the roster's other 20-name book and has never been measured at
any width on any store. `RMW-FR-GT` and `MVW-FR-GT` are unchanged.
```

**14c. The "Frozen means frozen" checklist (`:72–79`).** Its three steps are still right, but step 2
should now point at the real precedent and name the `promote`-is-unavailable case. Replace step 2
and add a step 4:

```markdown
2. Add a migration `0NN_*.sql` that inserts its row — every column `roster.from_row` reads, not
   just the display ones — and retires its predecessor in the same file, in the style of
   `017_roster_real_fees.sql` and `021_roster_width_35.sql`. The migration explains the decision
   with numbers; the DDL is the smaller half of it.
3. Commit, push, merge. The next nightly writes its spec and `paper_start`.
4. Check whether `promote` can write the live row at all before planning on it. It refuses an
   allocator that two `RESOLVER` keys name — which is every allocator the roster carries at two
   different parameter sets, as `RESIDMOM` has since 021. When it refuses, the migration is the
   only writer, no `record_promotion` note is written, and `lab/lab.sqlite` is untouched.
```

**Impact:** documentation only.

---

## Verification

Run in order. **Steps 1–10 and 12–14 must be complete before the first full run**; Step 11 is the
last edit and the snapshot tests are the last to go green.

**Postgres (CI fails if DB tests skip):**
```bash
docker start seer-pg 2>/dev/null || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
```

**Build / lint:**
```bash
engine/.venv/bin/ruff check engine        # CI lint is bugs only: E9 and F, minus F401
```

**Tests:**
```bash
engine/.venv/bin/pytest engine/tests
cd web && npx tsc --noEmit && npm test
```

**Targeted first, for a fast loop:**
```bash
engine/.venv/bin/pytest engine/tests/test_paper_roster.py engine/tests/test_promote_command.py \
    engine/tests/test_evidence.py engine/tests/test_paper_store.py \
    engine/tests/test_paper_check.py engine/tests/test_migrate.py \
    engine/tests/test_lab_snapshot.py -q
```

**The pin check, stated as its own assertion** — one new pin, zero moved:
```bash
engine/.venv/bin/pytest engine/tests/test_paper_roster.py::test_digests_are_pinned -q
engine/.venv/bin/python -c "
from seer_engine.paper.roster import ROSTER, spec, spec_digest
import engine  # noqa
" 2>/dev/null
git diff -- engine/tests/test_paper_roster.py | grep -E '^-\s+[A-Z_0-9]+: \"[0-9a-f]{64}' && \
  echo 'A PIN WAS REMOVED OR CHANGED — STOP' || echo 'no pin removed'
```

**The test-window look count — R6, before and after:**
```bash
BEFORE=$(md5sum lab/lab.sqlite | cut -d' ' -f1)
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab status | grep -i 'test'
[ "$BEFORE" = "$(md5sum lab/lab.sqlite | cut -d' ' -f1)" ] || git checkout -- lab/lab.sqlite
```
It must read **4** both times. This phase calls no `lab run` and no `lab test`, and points no
`--store` at `engine/.research-test`.

**Manual check (replaces `promote --dry-run`, which F1 ruled out):** the migration is applied to a
scratch Postgres and the row read back through the night's own path. This is
`test_the_migration_rows_equal_the_seed_rows` and
`test_the_database_rows_rebuild_the_roster_with_the_pinned_digests` — the same round trip
`promote._insert` performs inside its transaction. Run them explicitly and read the output:

```bash
engine/.venv/bin/pytest -q \
  'engine/tests/test_paper_roster.py::test_the_migration_rows_equal_the_seed_rows' \
  'engine/tests/test_paper_roster.py::test_the_database_rows_rebuild_the_roster_with_the_pinned_digests' \
  'engine/tests/test_paper_roster.py::test_display_fields_equal_the_migration_rows'
```

**Optional visual check** (`run-the-web-app` skill, per CLAUDE.md, for any change to `web/`): the
leaderboard renders `RAW35 · Unbraked momentum` with the 35-name subtitle, its name links to
`/sera/methods/M0139`, and `RAW · Unbraked momentum` is still present and marked retired. Note that
production renders empty states — use the throwaway demo database
(`seer-screenshots-need-a-throwaway-demo-database`) if the board comes up blank.

**Exit criteria**
1. `test_digests_are_pinned` green with **exactly one new pin and zero moved pins**; the grep above
   prints `no pin removed`.
2. `test_the_migration_rows_equal_the_seed_rows` and
   `test_the_database_rows_rebuild_the_roster_with_the_pinned_digests` green against a migrated
   scratch Postgres.
3. `engine/.venv/bin/ruff check engine` clean; `engine/.venv/bin/pytest engine/tests` green with no
   DB test skipped.
4. `cd web && npx tsc --noEmit && npm test` green.
5. `web/data/lab.json`'s `paper` block holds `RAW35-FR-GT` → `M0139` / `M0139-N35-EBAND` /
   `dev-eligible` and no longer holds `RAW-FR-GT`;
   `test_the_committed_snapshot_is_the_export_of_the_committed_database` green.
6. `lab status` reads **4** test-window looks, and `lab/lab.sqlite` is byte-identical to `HEAD`.
7. `docs/runbooks/paper-trading.md` carries the dated retirement record and the corrected table.

---

## Commits

Three, by explicit pathspec. **Never `git add -A`, never `reset --hard`** — this checkout and index
are shared. **No backticks inside a double-quoted `-m`.**

```bash
# 1. The roster change itself.
git add -- engine/src/seer_engine/paper/roster.py \
           engine/src/seer_engine/strategies/evidence.py \
           db/migrations/021_roster_width_35.sql \
           engine/tests/test_paper_roster.py \
           engine/tests/test_promote_command.py \
           engine/tests/test_paper_store.py \
           engine/tests/test_paper_check.py \
           engine/tests/test_migrate.py \
           engine/tests/test_evidence.py
git commit -m "roster: hold thirty-five, not twenty -- RAW35-FR-GT joins and RAW-FR-GT retires

The owner moved the roster's width on 2026-10-14. RAW35-FR-GT is RAW-FR-GT's own
book with one field changed, the name count, on the same screen, the same ranking,
the same market filter, the same rule set and the same fees -- lab M0139-N35-EBAND,
dev-eligible with nothing failed, and never looked at on the test window.

It is a new id because the name count is in the frozen spec. Not one live digest
moved; RAW-FR-GT keeps the digest 017 pinned for it and every row it ever wrote.

The width answer is M0152's, on the price history that keeps the companies that
failed: twenty names fall 25.05 per cent there, outside the owner's bar, and
thirty-five fall 20.11 per cent for slightly more money. The whole effect is one
dated episode in spring 2006. Over 2009-2015 both widths lose to SPY and the wider
one loses by more, which the migration says in its own prose.

promote cannot write this row: a new width needs a second resolver key on the same
allocator, and object_name_of refuses an object that two keys name. Migration 021
is the only writer, so lab.sqlite carries no promotion note.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

# 2. The snapshot, alone, inside the lab write lock (Step 11).
git add -- web/data/lab.json
git commit -m "web: the lab snapshot's paper block follows the roster to thirty-five names

The snapshot's paper block is built from the roster's own provenance table filtered
to active entries, so retiring one book and admitting another moves it. RAW-FR-GT
leaves and RAW35-FR-GT arrives, pointing at method M0139. Nothing in the lab
database changed.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

# 3. The docs and the audit map.
git add -- docs/runbooks/paper-trading.md .claude/skills/calculate-assets/build_audit.py \
           web/lib/sera/paper.test.ts
git commit -m "docs: record the width change and why promote could not write it

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

(If the `web/lib/sera/paper.test.ts` edit is needed to make commit 2's suite green, move it into
commit 2 — the snapshot and the test that reads it belong together.)

---

## Handoffs

| Left for | What, and why it is not mine |
|---|---|
| **Phase 1 (R3)** | `MOM-FR-GT`'s width. It is the roster's other 20-name book and has never been measured at any width on any store. Widening it on M0152's number would apply a measurement of the residual-momentum rule to a different picking rule. Phase 1 produces its own number; a second roster change is then its own argued commit, never a retrofit into `021`. |
| **Phase 1 (R3)** | If phase 1's check-store read shows `MOM-FR-GT` breaching the owner's 25% bar, that is a live fact about half of what he holds **today**, and it belongs at the top of phase 1's verdict. This phase deliberately does not act on it. |
| **Phase 3 (R2)** | M0155's single-name brake is the alternative answer to the same 2006 hole this phase answers with width. If it lands and wins, that is a **further** roster entry under the rule `017` wrote and `021` followed, not an edit to `RAW35-FR-GT`. The brake must be priced against M0152's recorded width curve at **twenty** names so it is measured against the width answer rather than instead of it. |
| **The reconciler** | **F3 is a cross-phase conflict the brief did not foresee.** The brief told this phase not to commit `web/data/lab.json`, but `lab/store.py:2967` builds the snapshot's `paper` block from `roster.LAB_PROVENANCE` + `roster.active()`, and `test_lab_snapshot.py:1054` compares the committed file byte for byte. This phase must regenerate and commit it, under the plan's lab write lock, with `lab export-json` and never `lab stage`. Plan invariant 7 (the lab phases serialise their stage-and-commit) must be widened to include phase 2's snapshot commit. |
| **The reconciler** | This phase writes **nothing** into `lab/lab.sqlite` — F1 removed the only writer (`record_promotion`). The plan index's phase-2 "Does not touch" line, which allowed for a `record_promotion` note, can be tightened to "none at all". |
| **Nobody — deliberately left undone** | `backtest/registry.py` is never appended to. `docs/lab/survivorship/grid.csv` is never appended to (`survivorship_record.GRID_PATH` points D16 at that exact file). `M0139`'s frozen verdict row is not edited; the correction lives in `LAB_PROVENANCE` and in `021`'s prose. The §1 real-money bar is untouched. |
| **A future session** | `.claude/skills/calculate-assets/build_audit.py` still points `S` at a dead session scratchpad and cannot run. Rebuilding that page for the current roster means re-running `calculate-assets` on `M0139-N35-EBAND` and pointing a new row at that JSON. Step 13 corrects the labels and refuses to relabel an old measurement; it does not fix the script. |

---

## Rollback

Reversible, and the reversal is the same shape as the change — which is the point of making it a
new id.

1. **A further migration** `022_*.sql`: flip `RAW35-FR-GT` to `status='retired'` with its
   `paper_end`, flip `RAW-FR-GT` back to `'active'`, and swap the two `sort` values back.
2. **The matching `paper/roster.py` edit**: move the two `SEED_ROWS` rows back and swap their
   `status`. Neither entry's spec digest moves, because `status`, `sort` and `paper_end` are
   deliberately outside the spec — so `PINS` is untouched by the rollback as it was by the change.
3. The `RESOLVER` key `"RESIDMOM35"`, the `EVIDENCE` key, the `LAB_PROVENANCE` entry and the pin
   **stay**. Keys are stable forever, and a stored spec names one. Removing `"RESIDMOM35"` would be
   the one genuinely destructive act available here.
4. Re-run Step 11 to put `RAW-FR-GT` back in the snapshot's `paper` block.

**What is NOT recoverable:** `RAW35-FR-GT`'s paper clock. Once it has had one unpaused night it has
a `paper_start`, and the runbook forbids resetting a clock by deleting rows. So the cost of being
wrong is **one restarted 18-month paper record, not a corrupted one** — and it is zero for as long
as `nightly.yml`'s `PAPER_PAUSED` reads `true`, because no session is stepped and no `paper_start`
is written.

Nothing here is a schema change and nothing is destructive: the migration is additive plus two
status flips, and `git revert` undoes every code change in this phase cleanly.
