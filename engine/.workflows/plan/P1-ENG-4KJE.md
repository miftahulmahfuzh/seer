> Adopted from `docs/plans/FOLD_VERDICT_AND_FALL_LABEL_PLAN.md` phase 2. Source: `.workflows/plan/fold-verdict-and-fall-label/phase-2.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 2: The forward-fall label and the sizing head

**Plan set:** `FOLD_VERDICT_AND_FALL_LABEL_PLAN.md`
**Analysis:** `docs/analyzer/20261013-082101-K09L_code_analyzer.md`
**Satisfies:** R2 — "learn the fall, not the pick": the tree model is re-pointed at forward downside
**as a level** instead of forward return rank, and its output sizes the book instead of picking its
names.
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab` (one module), `engine/tests` (one new module)

---

## Goal

After this phase `lab/tree_rank.py` can be asked a second question. Beside the forward-return-rank
label it carries a **forward-fall** label — the worst peak-to-trough drop, or the realised downside
volatility, over the next quarter, **as a raw level and never a rank** — and beside the
pick-the-top-N head it carries a **sizing head** that turns the predicted fall into *how much of the
book is held*, in whole slots, with the rest in cash. The fall model's feature matrix is the
ranker's seven rank-normalised columns **plus three un-normalised market-level columns**, so the
model has a level to read as well as a level to predict. Every existing public name in the module is
byte-identical, M0130's recorded config digests do not move, and phase 5 has an allocator to
pre-register a method on.

**D13 (set-level, binding, decided by the planning session that reconciled this set): the fall
label is a LEVEL, not a per-date rank.** `tree_rank` already rank-normalises every *feature* per
date (`rank_columns` inside `build_section`). A per-date rank *label* on top of that makes the
prediction distribution near-stationary across dates by construction: a fixed cut would then select
a count that varies only through cross-sectional composition noise, and in October 2008 — when
every stock is about to fall — the per-date ranks are still uniform, so the label literally *cannot*
encode "all of them". That is a selection test wearing a sizing head, which is the exact mistake
the handover is correcting M0130 for. The handover's sentence (section 2 item 2) is *"re-point the
model at **exposure** instead of **selection**: label on forward downside … and let the output size
the book"*, and a per-date rank label cannot satisfy it. **Nothing in this phase applies `rank01`
to the fall measure.**

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** none.

**Renames:** none.

**Creates** (all in `engine/src/seer_engine/lab/tree_rank.py`):

| Name | Kind |
|---|---|
| `tree_rank.QUARTER` (= 63) | module constant |
| `tree_rank.FallMeasure` | `Literal["drawdown", "downside_vol"]` |
| `tree_rank.FALL_MEASURES` | `tuple[str, ...]` |
| `tree_rank._window(h, day, stop)` | private helper |
| `tree_rank.forward_drawdown(history, section, end)` | function |
| `tree_rank.forward_downside_vol(history, section, end)` | function |
| `tree_rank.forward_fall(history, section, end, measure)` | function |
| `tree_rank.MARKET_HIGH_N` (= 252) | module constant (D13) |
| `tree_rank.MARKET_VOL_N` (= 60) | module constant (D13) |
| `tree_rank.MARKET_FEATURES` | `tuple[str, ...]`, the three un-normalised level columns (D13) |
| `tree_rank.FALL_FEATURE_LOOKBACK` | module constant, `== FEATURE_LOOKBACK == 401` (D13) |
| `tree_rank.fall_feature_names(feature_set)` | function: `feature_names(fs) + MARKET_FEATURES` |
| `tree_rank.market_columns(history, day, momentum)` | function: the three level scalars (D13) |
| `tree_rank.build_fall_section(base, history, momentum_col)` | function: composes `build_section`'s `Section` and appends the level columns (D13) |
| `tree_rank.FallSizeParams` | frozen dataclass |
| `tree_rank.FallModel` | frozen dataclass |
| `tree_rank._predict(estimator, X)` | private helper |
| `tree_rank.fit_fall_model(X, y, groups, months, anchor, params)` | function |
| `tree_rank.FallSizeAllocator` | class |
| `tree_rank.FALL_SIZE` | `FallSizeAllocator("price")`, `id == "FALL"` |
| `tree_rank.fall_targets_with_inputs(...)` | function (from-scratch sibling) |
| `TreeRankPrepared._falls` | new field, `dict[tuple[date, date, str], np.ndarray]` |
| `TreeRankPrepared._fall_sections` | new field, `dict[tuple[date, Any], Section]` |
| `TreeRankPrepared._fall_models` | new field, `dict[tuple[Any, ...], FallModel \| None]` |
| `TreeRankPrepared.forward_fall(t, horizon, measure)` | new method |
| `TreeRankPrepared.fall_labels(t, horizon, measure)` | new method — the **raw level**, no `rank01` |
| `TreeRankPrepared.fall_section(t, members=None)` | new method (D13) |
| `TreeRankPrepared.fall_training_set(params, anchor)` | new method, returns `(X, y, groups, months)` |
| `TreeRankPrepared.fall_model(params, anchor)` | new method |
| `TreeRankPrepared.fall_model_on(data_date, params)` | new method |
| `TreeRankPrepared.fall_targets_on(members, data_date, params)` | new method |
| `engine/tests/test_tree_fall.py` | new test module |

**Signature changes:** none (every name above is new in this phase).

**Deliberately NOT created (D14):** there is no `FALL_SIZE_FUND` and no `"FALLF"` allocator id.
D8 bars phase 5 from pre-registering any fundamentals variant — the EDGAR panel starts in 2009, a
panel-gated method is all-cash for 13 of the dev window's 20 years and the method id burns — so a
`FALL_SIZE_FUND` would be an exported allocator no method uses, permanently claiming an allocator
id. No protocol test this phase specifies needs it: `test_lab_methods.py::test_allocator_contract`
and `::test_allocator_ids_are_unique_across_methods` iterate over `backtest.registry.REGISTRY` and
over the candidates of discovered **method files**, and no method file names it. The `"price+fund"`
branch of `FallSizeAllocator.__init__` and of `fall_feature_names` stays reachable and is exercised
by constructing `FallSizeAllocator("price+fund")` inside the one test that needs it; no
module-level singleton is exported and no id is claimed.

**Requires (from earlier phases):** nothing. This phase depends on no other phase and reads no
file another phase in this set edits.

**Leaves alone (owned by others, or frozen):**
- `TreeRankParams` (`tree_rank.py:209`), `TreeRankAllocator` (`:733`), `TREE_RANK` (`:811`),
  `TREE_RANK_FUND` (`:812`), `forward_returns` (`:501`), `TreeRankPrepared.labels` (`:651`),
  `TreeRankPrepared.targets_on` (`:695`), `fit_model` (`:555`), `TreeModel` (`:528`),
  `build_section` (`:457`), `Section`, `FEATURE_LOOKBACK` (`:158`), `SCREEN`, `RESID`,
  `RAISE_EVENT`, `PRICE_FEATURES`, `FUND_FEATURES`, `feature_names`, `rank_columns`, `month_ends`,
  `label_end`, `year_end`, `anchor_for`, `training_dates`, `training_set`, `model`, `model_on`,
  `targets_with_inputs` — **not one byte, not even a reformat**. (`training_dates` is *called* with
  the new params class, `build_section` and `Section` are *composed* by `build_fall_section`, and
  `rank_columns` is *not called at all* on the fall label (D13); calling, composing and not calling
  are none of them editing.)
- `engine/tests/test_tree_rank.py` — left byte-identical. The new tests go in a sibling module.
- `engine/src/seer_engine/lab/methods/*` — phase 5.
- `engine/src/seer_engine/lab/store.py`, `hardgate.py`, `runner.py`,
  `engine/src/seer_engine/commands/lab.py` — phase 1 and phase 4.
- `lab/lab.sqlite`, `web/data/lab.json`, `docs/`, `sim/`, `web/` — untouched by this phase.

---

## Measured facts this plan is built on

Every number below was measured in this worktree on 2026-10-13 at the phase base, not estimated.
Re-measure if a peer phase lands first and you doubt one.

**M1 — D4 is true, and more precisely than stated.** All six of M0130's recorded `config_digest`s
reproduce today. Inserting one compare field into `TreeRankParams` (class name held constant, only
`,fall_horizon=63` appended inside the rendered dataclass text) moves **five** of the six:

```
M0130-P20      381a0d7c17fe -> e7d9e0c2c1f8
M0130-P50      d9678338b21a -> 46655f8fc26d
M0130-P50-REG  02068d1e59ea -> 233f8511e9e9
M0130-P20-GATE 8b85a98458a0 -> 09dfe1f43585
M0130-PF20     1dd163647996 -> 3ae42f83e0fc
M0130-DV20     unmoved — its ControlParams never names TreeRankParams
```

So the plan index's "all six" is five; the conclusion is unchanged and the tripwire
(`test_lab_methods.py::test_every_recorded_configuration_still_digests_to_its_recorded_digest`)
fires either way. **`TreeRankParams` gains no field. The fall model arrives as a new params class.**

**M2 — D5: `FALL` is free** (and so was `FALLF`, which D14 then dropped — see the Interface
Contract; the measurement below is left as it was taken). Across `backtest.registry.REGISTRY` plus every candidate
of every discovered lab method there are **75** distinct allocator ids:

```
A BLEND F1 F11 F7 FAC FND M0001 M0002 M0007 M0008 M0011 M0012 M0013 M0015 M0019 M0020 M0022
M0024 M0028 M0034 M0035 M0036 M0039 M0039-DIV M0044 M0050 M0051 M0052 M0053 M0053-NOBRAKE
M0054 M0056 M0057 M0058 M0059 M0063 M0064 M0066 M0069 M0070 M0071 M0072 M0073 M0076 M0077
M0078 M0079 M0080 M0081 M0082 M0083 M0084 M0085 M0086 M0088 M0091 M0092 M0096 M0097 M0101
M0102 M0107 M0108 M0109 M0117 M0118 M0119 M0120 M0128 M0130 M0130-DV M0130-F ROT VOLTARGET
```

Neither `FALL` nor `FALLF` is among them. `FALL` cannot collide by construction either: every lab
method's own allocator id is either its method id (`M0130`, `M0130-F`, `M0130-DV`) or a short
strategy-family word already in the list, and `lab next-id` only ever mints `MNNNN`. Step 8 of the
tests below pins this as an assertion, so a future collision is a red test rather than a surprise.
**`FALLF` is not claimed** (D14): no module-level `FALL_SIZE_FUND` is exported, so the id stays
free for whoever needs it.

**M3 — D7, the resize band, in numbers.** `MONTHLY_HOLD_FRAC_GOTRADE_TBAND` has
`resize_basis="target"`, and `sim/book.py:462` is `gap * last >= TARGET_RESIZE_BAND * weight * equity`:

| slots | slot weight | band (`0.20 × w × equity`) | entry/exit gap | ratio | smallest tradeable weight nudge |
|---|---|---|---|---|---|
| 10 | 0.100000 | 0.0200 × equity | 0.100 × equity | **5.0×** | 0.0200 (20% of the slot) |
| 20 | 0.050000 | 0.0100 × equity | 0.050 × equity | **5.0×** | 0.0100 (20% of the slot) |
| 25 | 0.040000 | 0.0080 × equity | 0.040 × equity | **5.0×** | 0.0080 (20% of the slot) |

A head that nudged a 5% slot to 4.8% would move `0.002 × equity` against a `0.010 × equity` band
and would **never trade**. Adding or dropping a whole name always moves five times the band. Hence
whole slots at a fixed weight, never a renormalised book. Two further confirmations from
`sim/book.py`: a name absent from `wanted` is a full signal exit at the open and is **not**
band-gated (`:675-694`), and a fresh entry is sized at `budget = min(q(equity * t.weight), ...)` —
the literal target weight, with **no renormalisation**, so targets summing to `k/slots < 1` leave
the remainder in cash (`:741-747`).

**M4 — the quarter horizon costs calendar, not lookback.** `label_end(t, 63)` resolves for every
date tried (`2014-01-31 → 2014-05-02`, `2012-11-30 → 2013-03-05`, `1996-01-31 → 1996-05-01`). With
`train_start=1996-01-31` and `min_train_months=35`:

| horizon | first refit with 35 labelled month-ends | first book year | last labelled dev month-end |
|---|---|---|---|
| 21 (the ranker today) | 1998-12-31 (35 months) | 1999 | 2015-08-31 |
| **63 (the fall label)** | **1999-12-31 (45 months)** | **2000** | **2015-06-30** |

The lookback is unchanged: `FEATURE_LOOKBACK = 401` (`max(factor_lookback(SCREEN)=253,
resid_lookback(RESID), HIGH_N=252)`), because the ranker's seven features are untouched. The smoke
fixture is **473 bars** (`2013-12-02 … 2015-10-16`), so 401 clears the cap by 72 bars — exactly the
margin M0130's six candidates already pass `test_candidate_runs_a_smoke_window` with. The index's
"aim for about 315 of actual reach" cannot be met without changing the frozen feature set, and is
not needed here: for a `MarketAware` allocator `test_allocator_contract` *requires* the history-only
path to target nothing, so the look-ahead probe that matters fires in this phase's own test module,
on a 1510-session synthetic market, where it has 1109 sessions of room. **The index's exit criterion
was corrected to "401 ≤ 473, proved" at reconciliation.**

**M4a — D13's three market-level columns add no reach, and the new constant proves it.** The
columns are SPY's distance from its trailing **252**-session high (`MARKET_HIGH_N`), SPY's realised
volatility over the last **60** sessions (`MARKET_VOL_N`, which needs 61 bars for 60 returns), and
the cross-sectional dispersion of the date's momentum column — which is read straight off
`build_section`'s own output and therefore reaches exactly as far as the momentum feature already
does. So

```
FALL_FEATURE_LOOKBACK = max(FEATURE_LOOKBACK, MARKET_HIGH_N, MARKET_VOL_N + 1)
                      = max(401, 252, 61) = 401
```

**401, unchanged, and 401 ≤ 473.** `FALL_SIZE.lookback(...)` returns `FALL_FEATURE_LOOKBACK`, not
`FEATURE_LOOKBACK`, so the constant is the single place the claim lives and
`test_a_candidate_runs_the_lab_smoke_window` pins it. SPY is already in
`FallSizeAllocator.symbols` (`RESID.market`), so no new symbol is requested and no new bar is
loaded. Each column reads only bars dated on or before the decision date, by the same
`searchsorted(..., side="right")` discipline `_window` and `forward_returns` use, and all three are
covered by the module's existing no-look-ahead probes plus
`test_bars_dividends_and_membership_after_d_change_nothing` in this phase's own test module.

**M5 — SUPERSEDED BY D13. Re-measure; do not carry these numbers forward.** The prototype these
numbers came from used the **rank** label and a cut that was a quantile of the in-sample
*row-level* predictions at `slots / (rows / months)`. D13 removes both. The numbers are kept only
so the implementer can see what was replaced and does not mistake a changed histogram for a
regression:

```
SUPERSEDED (rank label + row-quantile cut, synthetic market, 35 dates 2012-01 … 2014-11)
slots=3 size=True : k histogram {0: 1, 1: 1, 2: 8, 3: 25}
slots=5 size=True : k histogram {3: 2, 4: 11, 5: 22}
slots=3/5 size=False: always full (the control)
```

What *does* carry forward from that prototype, because D13 does not touch it: the fit is
**deterministic** (two independent `prepare_market` → fit runs gave identical 64-char digests), the
prepared path equalled the from-scratch path bit for bit on all six probe dates (5 non-empty), and
both futures of the no-look-ahead probe (bars/dividends/membership mutated and truncated from
`next_session(d)`) left every target list unchanged.

The replacement measurements this phase must take are **M5a** (the synthetic market, in
`test_tree_fall.py`: the head reaches both `k = slots` and `k = 0`, in more than two steps) and
**M5b** (the real research store — the new exit criterion moved here from phase 5: exposure on each
January decision date 2000-2015 is not flat **and** falls in 2008). M5b is in *Verification* below
and is the measurement that decides whether phase 5 may spend a method id at all.

**M6 — the suite baseline at this phase's base commit:** `4640 passed, 3 skipped in 80.67s`
(the 3 skips are the three opt-in live-store sweeps, which also skip in CI).

---

## Design decisions, and why

**D2a (rewritten under D13) — the label is a LEVEL, and that is what forces the head's shape.**
`fall_labels` returns `forward_fall` **as it is computed**: the drawdown fraction, or the realised
downside volatility, in its own units. No `rank01`, no `rank_columns`, no normalisation of any kind.
NaN still means "not known" and is dropped from training exactly as before.

The superseded design applied `rank_columns` to the fall measure. It is removed, not merely
outranked, for the reason D13 states and this phase can restate in its own terms: `build_section`
already rank-normalises every *feature* per date. A per-date rank *label* on top of that makes the
model's prediction distribution near-stationary across dates by construction — so a fixed cut would
select a count that varies only through cross-sectional composition noise, never through a forecast
of the market falling, and in October 2008 the per-date ranks are *still uniform*, so the label
cannot encode "all of them". A head reading that is a selection test wearing a sizing head: exactly
the mistake the handover is correcting M0130 for. A level label can say "every name on this date is
about to fall 30%"; a rank label cannot say it in principle.

**D2a2 (new under D13) — a level label needs level inputs, or it buys nothing.** If every feature
column is a per-date rank, the model has no way to tell October 2008 from October 2005 and the best
it can do with a level label is predict the unconditional mean. So the fall model's feature matrix
is `build_section`'s seven rank-normalised columns **plus three un-normalised, market-level
columns**, appended by a new `build_fall_section` that *composes* `build_section` rather than
replacing it (`build_section`, `Section`, `rank_columns`, `PRICE_FEATURES` and every other existing
name stay byte-identical — D4 is unchanged and still binding):

| Column | What it is | Reach |
|---|---|---|
| `spy_drawdown_from_high` | 1 − SPY's close on `t` ÷ its highest close in the trailing `MARKET_HIGH_N` = 252 sessions | 252 bars |
| `spy_vol_60` | the standard deviation of SPY's last `MARKET_VOL_N` = 60 one-day returns | 61 bars |
| `momentum_dispersion` | the standard deviation of the date's own 12-1 momentum column, read off `build_section`'s **raw** matrix before ranking | the momentum feature's own reach |

All three are **per-date scalars broadcast down the rows**. Within a date they carry no
cross-sectional information at all, so they cannot change which names the model prefers — they can
only shift the whole date's predictions up or down, which is precisely the level the head reads.
They are defensible from data the module already reaches: SPY is already `FallSizeAllocator.symbols`
(`RESID.market`), the momentum column is already computed, and nothing new is loaded. Each reads
only bars dated on or before the decision date; `FALL_FEATURE_LOOKBACK` is `max(401, 252, 61) = 401`
and 401 ≤ the smoke fixture's 473 (M4a).

**D2b — `size: bool` is the built-in control.** `size=False` ignores the cut entirely and holds all
`slots`, so the book is always full. Phase 5 gets "ranking by predicted calm" and "ranking by
predicted calm *plus* sizing" as a paired difference inside one allocator, with no second class.

**D2c (rewritten under D13) — the head reads a market-level quantity, and the cut comes from the
model's own training distribution.** At refit time the model predicts on its own training rows,
takes the **mean predicted fall per training date**, and keeps those date-level means sorted
(`FallModel.levels`). `FallModel.cut` is their median — the scalar the model reports, and the level
at which the book sits at half exposure. At a decision date the head computes the date's
**cross-sectional mean predicted fall** and asks where it falls in that training distribution:

```
danger = searchsorted(levels, level, side="right") / len(levels)   # 0.0 .. 1.0
k      = slots - floor(danger * slots)                             # whole slots
```

Calmer than every training date → `danger = 0` → `k = slots`, a full book. More dangerous than
every training date → `danger = 1` → `k = 0`, all cash. At the median → half the slots. It is
monotone, it reaches both ends, it moves in whole slots, and **not one number in it was chosen**:
the ladder is the empirical CDF of the model's own in-sample date-level predictions. Choosing a
threshold on the dev window instead would be the off-the-books tuning pre-registration forbids.

The names that fill those `k` slots are still the calmest predicted falls first, ties by symbol, so
the ordering mechanic phase 2 already had is kept whole.

**D2c2 (replaces the old D2c) — `slots` is NOT in `model_key()`, and neither is `size`.** Under the
superseded design the cut was a quantile at `slots / (rows / months)`, so `slots` changed the fit.
It no longer does: `levels` and `cut` are properties of the model alone and `slots` is applied at
decision time by the ladder. So `FallSizeParams.model_key()` now excludes both `slots` and `size`,
exactly as `TreeRankParams.model_key()` excludes `top_n` — the fall params no longer differ from the
ranker's in this respect at all, and a variant that only changes the book size costs no extra annual
refit ladder.

**D2d — two measures, one head.** `measure="drawdown"` (the worst peak-to-trough fall) is the
default because it *is* the §1 constraint; `measure="downside_vol"` is the handover's named
alternative and costs one extra function. Both are selected by a params field, so phase 5 can make
the choice a pre-registered variant without a second allocator. Both are levels, in their own units,
and the head reads either one the same way — the ladder is scale-free because it is a CDF position.

**D2e — separate caches, not a wider key.** `_falls`, `_fall_sections` and `_fall_models` are their
own dicts. A fall vector can never be served where a forward return was asked for, whatever the
horizon, because the two never share a container; and a *fall* section (10 columns) can never be
served where a *ranker* section (7 columns) was asked for. The fall label key additionally carries
the measure name.

**D2f (new under D13) — no per-date-rank label survives, not even as a mode.** The reconciliation
considered keeping `label: "level" | "rank"` as a params field so phase 5 could pre-register the
superseded design as a negative control. It is **dropped**: phase 5's own variant rule says every
setting tried counts and that "a sixth would only add a hyperparameter", the index's scope says *a*
forward-fall label (singular), and D13 requires the losing side removed rather than carried. Phase 5
keeps five variants and states the rank-label flatness as a pre-registered *expected failure* in
prose, which is where a prediction belongs when the design that would produce it is not being built.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/tree_rank.py` | modify (additive only) | docstring paragraphs after `:48` (the level label + the market columns) and `:60` (the sizing head, one object); three cache fields after `:601`; seven methods after `:719`; three new sections appended after `:832` (the measures, the market-level columns, the model + head) |
| `engine/tests/test_tree_fall.py` | create | 21 tests: the measures, the **level** label, the **market columns**, the caches, the model, the **exposure ladder**, the head, the identity, the no-look-ahead, the smoke window, the ids |

No other file in the repository is touched.

---

## Implementation Steps

### Step 1: the module docstring — the fall label paragraph

**File:** `engine/src/seer_engine/lab/tree_rank.py:48` (insert *after* the line
`` ``label_end(t)``, and not one day before. ``, keeping line 49's blank line and line 50's
`WALK-FORWARD.` paragraph byte-identical)

**Change:** add one blank line and this paragraph. Every existing line of the docstring stays
exactly as it is; nothing is reflowed.

**Code:**

```
THE FALL LABEL, the second thing this module can be asked to predict, and the one place this
module does NOT rank-normalise. The constraint that binds this lab is not the pick but the fall: of
394 recorded dev trials 65% beat SPY total return and only 23% keep the worst drawdown at or under
20% (handover 2026-10-13, "measure the constraint"). So beside the forward return rank there is a
forward *downside* LEVEL. ``forward_drawdown`` is the worst peak-to-trough fall of a symbol's
closes from ``section.day`` to its last close on or before the label end, as a fraction;
``forward_downside_vol`` is the root mean square of its down days over the same window. Both read
only bars dated on or before that end, and both are NaN where the window cannot be measured and a
measured 0.0 where it was calm -- NaN means "not known", never "no fall".

**``fall_labels`` returns that measure RAW. ``rank01`` is not applied to it, ever.** The return
label is a per-date rank because the ranker's question is "which of these names"; the fall model's
question is "how much of this book", and a per-date rank cannot answer it. Every FEATURE column is
already rank-normalised per date (``rank_columns`` in ``build_section``); a per-date rank LABEL on
top of that would make the prediction distribution near-stationary across dates by construction, so
a cut would select a count that moved only with cross-sectional composition noise, and in October
2008 -- when every name is about to fall -- the per-date ranks would still be uniform and the label
could not encode "all of them" even in principle. That is a selection test wearing a sizing head.
The level can say "every name on this date is about to fall thirty per cent"; the rank cannot.

The horizon is a quarter (``QUARTER``, 63 sessions) rather than the ranker's month, because a fall
is a path and a month of a path is mostly noise. A longer horizon costs label-end calendar, not
lookback: a sample enters training only once ``label_end(t, horizon) <= anchor``, so the first fall
refit with 35 labelled month-ends is 1999-12-31 against the ranker's 1998-12-31, the first book year
is 2000 against 1999, and the last labelled dev month-end is 2015-06-30 against 2015-08-31.
``FEATURE_LOOKBACK`` does not move.

THE MARKET-LEVEL COLUMNS, because a level label needs level inputs. If every feature were a per-date
rank the model could not tell 2008 from 2005 and the best it could do with a level label is predict
the unconditional mean. ``build_fall_section`` therefore COMPOSES ``build_section`` -- which is not
edited, nor is ``Section``, ``rank_columns`` or ``PRICE_FEATURES`` -- and appends three columns that
are deliberately NOT normalised: SPY's distance below its trailing ``MARKET_HIGH_N`` (252) session
high, SPY's realised volatility over the last ``MARKET_VOL_N`` (60) sessions, and the cross-sectional
dispersion of the date's own 12-1 momentum, read off the raw matrix before ranking. All three are
per-date scalars broadcast down the rows: within a date they carry no cross-sectional information
and so cannot change which names the model prefers, only how far the whole date's predictions shift
-- which is exactly the level the head reads. Each reads only bars dated on or before the decision
date. ``FALL_FEATURE_LOOKBACK`` is ``max(FEATURE_LOOKBACK, MARKET_HIGH_N, MARKET_VOL_N + 1)`` = 401,
unchanged, and under the lab smoke fixture's 473-bar cap.
```

**Impact:** documentation only. The AST and fresh-interpreter purity checks in
`tests/test_tree_rank.py` read this file and are unaffected by a docstring.

---

### Step 2: the module docstring — the sizing-head paragraphs

**File:** `engine/src/seer_engine/lab/tree_rank.py:60` (insert *after* the line
`(as F4): a name that falls out of the top set is signal-exited by the book engine.`, keeping
line 61's blank line and line 62's `THE TWO PATHS.` paragraph byte-identical)

**Change:** add one blank line and these three paragraphs.

**Code:**

```
THE SIZING HEAD reads a MARKET-LEVEL quantity, not a per-name one. The names are still read in one
pass -- the calmest predicted falls first, ties by symbol -- but how many of the ``slots`` are
filled is decided by where the WHOLE CROSS-SECTION sits, and the slots that are not filled are cash.
At each refit the model predicts on its own training rows, takes the mean predicted fall per
training date, and keeps those date-level means sorted (``FallModel.levels``); ``FallModel.cut`` is
their median, the level at which the book sits at half exposure. At a decision date the head takes
the date's cross-sectional MEAN predicted fall and asks where it falls in that training
distribution: ``danger`` is the share of training dates that looked no more dangerous, and the book
holds ``slots - floor(danger * slots)`` whole slots. Calmer than every training date and the book is
full; more dangerous than every one of them and the book is entirely cash; at the median, half.
It is monotone, it reaches both ends, and NOT ONE NUMBER IN IT WAS CHOSEN -- the ladder is the
empirical distribution of the model's own in-sample predictions, so nothing here was read off the
dev window, which is what pre-registration requires. ``size=False`` is the control: the same
ordering, the ladder ignored, the book always full, which separates what the sizing adds from what
ranking by predicted calm adds.

WHY WHOLE SLOTS. The weight of a held name is ``equal_weight(slots)`` and never changes with how
many are held: the book is never renormalised onto the names that survived. The measuring tape
(``sim.rules.MONTHLY_HOLD_FRAC_GOTRADE_TBAND``) resizes a holding only once it is off by
``TARGET_RESIZE_BAND``, 20% of its OWN target value, so at 20 slots a weight nudge smaller than 1%
of equity is never traded at all and a head that expressed exposure by nudging weights would be
swallowed whole by the band. An entry or an exit is a gap of a full slot, 5% of equity at 20 slots:
five times the band, every time, at every book size. So exposure moves in whole slots, which is the
only step this tape can hear.

ONE OBJECT, DELIBERATELY. ``FALL_SIZE`` is the fall model's only exported allocator, beside the
ranker's pair ``TREE_RANK`` and ``TREE_RANK_FUND``. There is no ``FALL_SIZE_FUND``: the EDGAR panel
starts in 2009, so a method pre-registered on fundamentals would be learning from four empty columns
for thirteen of the dev window's twenty years and would burn its method id measuring the panel
rather than the hypothesis. An exported allocator that no method may ever use would only claim an
allocator id forever, so the id ``FALLF`` is left free. ``FallSizeAllocator`` still accepts
``"price+fund"`` -- the branch is reachable and tested by constructing one locally -- but the fall
model is built to run on price and dividend features alone, and that is what it is pre-registered on.
```

**Impact:** documentation only.

---

### Step 3: the forward-fall measures

**File:** `engine/src/seer_engine/lab/tree_rank.py` — append at the **end of the file**, after
line 832 (`    return prepared.targets_on(members, data_date, params)`), starting with two blank
lines.

**Change:** a new banner section with the quarter constant, the measure literal, the shared window
helper and the two measures. `forward_returns` at `:501` is not touched; this is its sibling.

**Code:**

```python
# --------------------------------------------------------------- the fall label (R2, 2026-10-13)


QUARTER = 63
"""NYSE sessions in a calendar quarter: the fall label's horizon, the handover's "next quarter"."""

FallMeasure = Literal["drawdown", "downside_vol"]
FALL_MEASURES: tuple[str, ...] = ("drawdown", "downside_vol")


def _window(h: History, day: np.datetime64, stop: np.datetime64) -> np.ndarray | None:
    """``h``'s closes from its bar dated ``day`` through its last bar dated on or before ``stop``.

    None -- "not measurable" -- when ``h`` has no bar dated exactly ``day``, no bar after it by
    ``stop``, or any close in the window is not a finite positive price. The two ``searchsorted``
    calls are ``forward_returns``' discipline verbatim: ``j`` is found with ``side="right"`` on
    ``stop``, so a bar dated after the label end can never enter the window, however far the
    history runs past it.
    """
    i = int(np.searchsorted(h.dates, day, side="left"))
    j = int(np.searchsorted(h.dates, stop, side="right")) - 1
    if i >= len(h) or h.dates[i] != day or j <= i:
        return None
    path = np.asarray(h.close[i : j + 1], dtype=np.float64)
    if not bool(np.isfinite(path).all()) or not bool((path > 0.0).all()):
        return None
    return path


def forward_drawdown(history: Mapping[str, History], section: Section, end: date) -> np.ndarray:
    """Each section symbol's worst peak-to-trough fall from ``section.day`` to ``end``, as a fraction.

    0.0 for a path that never closes below a previous close in the window -- a measured zero, which
    is why "unmeasurable" is NaN and never 0.0. NaN when the window is unmeasurable (``_window``).
    Reads only bars dated on or before ``end``.
    """
    out = np.full(len(section.symbols), NAN, dtype=np.float64)
    day = as_day(section.day)
    stop = as_day(end)
    for k, symbol in enumerate(section.symbols):
        path = _window(history[symbol], day, stop)
        if path is None:
            continue
        fall = float(np.max(1.0 - path / np.maximum.accumulate(path)))
        out[k] = fall if fall > 0.0 else 0.0
    out.setflags(write=False)
    return out


def forward_downside_vol(history: Mapping[str, History], section: Section, end: date) -> np.ndarray:
    """Each section symbol's realised downside volatility from ``section.day`` to ``end``.

    The root mean square of ``min(r, 0)`` over the window's one-day simple returns: up days count
    as zero, so a path that only rises scores 0.0. NaN when the window is unmeasurable
    (``_window``). Reads only bars dated on or before ``end``.
    """
    out = np.full(len(section.symbols), NAN, dtype=np.float64)
    day = as_day(section.day)
    stop = as_day(end)
    for k, symbol in enumerate(section.symbols):
        path = _window(history[symbol], day, stop)
        if path is None:
            continue
        down = np.minimum(path[1:] / path[:-1] - 1.0, 0.0)
        out[k] = float(np.sqrt(float(np.mean(down * down))))
    out.setflags(write=False)
    return out


def forward_fall(
    history: Mapping[str, History], section: Section, end: date, measure: str
) -> np.ndarray:
    """``measure``'s forward fall of ``section`` over (``section.day``, ``end``]."""
    if measure == "drawdown":
        return forward_drawdown(history, section, end)
    if measure == "downside_vol":
        return forward_downside_vol(history, section, end)
    raise ValueError(f"measure must be one of {FALL_MEASURES}, got {measure!r}")


# ------------------------------------------------- the market-level columns (D13, un-normalised)


MARKET_HIGH_N = 252
"""Sessions in the trailing high SPY's drawdown column is measured against (one year)."""

MARKET_VOL_N = 60
"""One-day SPY returns in the realised-volatility column; it needs MARKET_VOL_N + 1 bars."""

MARKET_FEATURES: tuple[str, ...] = (
    "spy_drawdown_from_high",
    "spy_vol_60",
    "momentum_dispersion",
)

MOMENTUM_COL = PRICE_FEATURES.index(MOMENTUM_FEATURE)
"""Where the 12-1 momentum column sits in ``build_section``'s raw matrix.

Looked up from the frozen tuple rather than written as a literal ``0``: if ``PRICE_FEATURES`` is
ever reordered, this raises at import instead of silently computing the dispersion of the wrong
column. ``MOMENTUM_FEATURE`` is the exact string the module already uses for that column -- read it
off ``PRICE_FEATURES`` when writing this line; do not guess the spelling.
"""

FALL_FEATURE_LOOKBACK = max(FEATURE_LOOKBACK, MARKET_HIGH_N, MARKET_VOL_N + 1)
"""How far back the FALL model reads: max(401, 252, 61) = 401, so the ranker's own window.

``FEATURE_LOOKBACK`` is frozen (M0130's recorded digests do not name it, but ``TreeRankAllocator``
does and this module does not edit that path). This constant is the fall allocator's own, written
as a ``max`` so that the claim "the market columns add no reach" is arithmetic a reader can check
rather than a sentence they must trust. The lab's smoke fixture is 473 bars, so 401 clears it.
"""


def fall_feature_names(feature_set: str) -> tuple[str, ...]:
    """The fall model's columns: the ranker's own, then the three un-normalised market columns.

    ``feature_names`` is the ranker's and is not edited. The market columns come last so the
    ranker's column order inside the matrix is the one ``build_section`` produced, byte for byte.
    """
    return tuple(feature_names(feature_set)) + MARKET_FEATURES


def market_columns(
    history: Mapping[str, History], day: date, momentum: np.ndarray
) -> tuple[float, float, float]:
    """The date's three market-level scalars. Reads only bars dated on or before ``day``.

    Per-date SCALARS, not per-name values: broadcast down every row of the section, they carry no
    cross-sectional information and so cannot change which names the model prefers. They can only
    shift the whole date's predictions, which is exactly the level a sizing head has to read (D13).

    - ``spy_drawdown_from_high``: ``1 - close(day) / max(close over the trailing MARKET_HIGH_N
      sessions ending at day)``. 0.0 at a new high, larger the further the market has already
      fallen. NaN when SPY has no bar dated ``day`` or fewer than two bars behind it.
    - ``spy_vol_60``: the sample standard deviation of SPY's last ``MARKET_VOL_N`` one-day simple
      returns ending at ``day``. NaN with fewer than ``MARKET_VOL_N + 1`` bars.
    - ``momentum_dispersion``: the standard deviation of the date's own 12-1 momentum column, taken
      from ``build_section``'s RAW matrix before ``rank_columns`` touched it, over the finite
      entries. NaN when fewer than two are finite.

    The slice is ``searchsorted(dates, day, side="right")`` -- ``forward_returns``' and
    ``_window``'s own discipline -- so a bar dated after ``day`` can never enter, however far the
    history runs past it. NaN is left as NaN: ``fit_model`` bins a missing value into its own bin,
    which is the honest encoding of "this column is not known on this date".
    """
    h = history.get(RESID.market)
    dd = NAN
    vol = NAN
    if h is not None:
        j = int(np.searchsorted(h.dates, as_day(day), side="right"))
        if j > 0 and h.dates[j - 1] == as_day(day):
            hi = np.asarray(h.close[max(0, j - MARKET_HIGH_N) : j], dtype=np.float64)
            if len(hi) >= 2 and bool(np.isfinite(hi).all()) and bool((hi > 0.0).all()):
                peak = float(np.max(hi))
                if peak > 0.0:
                    dd = float(1.0 - float(hi[-1]) / peak)
            win = np.asarray(h.close[max(0, j - MARKET_VOL_N - 1) : j], dtype=np.float64)
            if len(win) >= MARKET_VOL_N + 1 and bool(np.isfinite(win).all()) and bool((win > 0.0).all()):
                vol = float(np.std(win[1:] / win[:-1] - 1.0, ddof=1))
    ok = np.isfinite(momentum)
    disp = float(np.std(momentum[ok], ddof=1)) if int(ok.sum()) >= 2 else NAN
    return dd, vol, disp


def build_fall_section(
    base: Section, history: Mapping[str, History], momentum_index: int
) -> Section:
    """``base`` with the three market-level columns appended, un-normalised.

    COMPOSES ``build_section``'s output; it does not reimplement or edit it. ``base.X`` already
    carries the ranker's seven rank-normalised columns and is copied through untouched, so the
    fall model sees exactly what the ranker sees plus three columns that were never ranked -- which
    is the whole of D13's second requirement. ``Section`` itself is unedited: this constructs one.

    ``momentum_index`` is the position of the 12-1 momentum column in ``base.raw``; the dispersion
    is read from the RAW matrix, because the standard deviation of a rank column is a constant of
    the cross-section's size and would carry no information at all.
    """
    extra = np.array(
        market_columns(history, base.day, np.asarray(base.raw[:, momentum_index], dtype=np.float64)),
        dtype=np.float64,
    )
    block = np.repeat(extra.reshape(1, -1), len(base.symbols), axis=0)
    raw = np.hstack([np.asarray(base.raw, dtype=np.float64), block])
    X = np.hstack([np.asarray(base.X, dtype=np.float64), block])
    raw.setflags(write=False)
    X.setflags(write=False)
    return Section(base.day, base.symbols, base.close, raw, X)
```

**Impact:** six new module-level names plus two helpers. Nothing existing reads them yet, and
nothing existing is edited: `build_section`, `Section`, `rank_columns`, `PRICE_FEATURES`,
`feature_names` and `FEATURE_LOOKBACK` are read and composed, never written.
No new import: `np`, `math`, `Literal`, `Mapping`, `History`, `as_day`, `NAN`, `RESID`, `Section`,
`feature_names`, `FEATURE_LOOKBACK` are already available at `:96-129` / module scope.

> **Two things the implementer must look up rather than assume:** the exact string
> `PRICE_FEATURES` uses for the 12-1 momentum column (written above as `MOMENTUM_FEATURE`), and the
> field order of `Section` (read as `day, symbols, close, raw, X` — confirm it before writing
> `build_fall_section`'s return). Neither is guessed in this plan and neither may be guessed in the
> code: `MOMENTUM_COL` is derived with `.index(...)` precisely so a wrong or reordered name is an
> `ImportError` at module load rather than a silently wrong dispersion column.

---

### Step 4: the fall label path on `TreeRankPrepared` — the two cache fields

**File:** `engine/src/seer_engine/lab/tree_rank.py:601` (insert immediately after
`    _models: dict[tuple[Any, ...], TreeModel | None] = field(default_factory=dict, repr=False)`
and before the blank line preceding `    @staticmethod` at `:603`)

**Change:** three new fields. They go **after** `_models` so `TreeRankPrepared.build`'s four
positional arguments at `:609-614` keep meaning what they meant.

**Code:**

```python
    _falls: dict[tuple[date, date, str], np.ndarray] = field(default_factory=dict, repr=False)
    _fall_sections: dict[tuple[date, Any], Section] = field(default_factory=dict, repr=False)
    _fall_models: dict[tuple[Any, ...], FallModel | None] = field(default_factory=dict, repr=False)
```

`_fall_sections` is keyed exactly as the ranker's own section cache is keyed (the date and the
members key), in its **own** dict, so a 10-column fall section can never be served where a 7-column
ranker section was asked for and the other way round (D2e).

**Impact:** `TreeRankPrepared` gains three empty dicts. `eq=False`, so no equality semantics move;
`build` and `prepare` construct them by default. The class docstring at `:588-592` stays as it is —
the new caches are documented on their own methods, and reflowing that docstring would be the
reformat the scope forbids.

---

### Step 5: the fall label path on `TreeRankPrepared` — the six methods

**File:** `engine/src/seer_engine/lab/tree_rank.py:719` (insert immediately after
`        return tuple(out)` — the last line of `targets_on` — and before the blank lines and the
`# ----- the allocator` banner at `:722`)

**Change:** seven new methods at the end of the class body. `labels`, `training_set`, `model`,
`model_on` and `targets_on` above them are untouched.

**Code:**

```python
    def forward_fall(self, t: date, horizon: int, measure: str) -> np.ndarray:
        """``measure``'s forward fall of the members' cross-section on ``t`` over ``horizon`` sessions.

        Cached in ``_falls``, keyed by (t, label end, measure). That is a different dict from
        ``_returns``, so a fall vector can never be served where a forward return was asked for,
        or the other way round, whatever the horizon -- the two caches cannot reach each other.
        """
        inputs, _ = self._live()
        end = self.end(t, horizon)
        key = (t, end, measure)
        hit = self._falls.get(key)
        if hit is None:
            hit = forward_fall(inputs.history, self.section(t), end, measure)
            self._falls[key] = hit
        return hit

    def fall_labels(self, t: date, horizon: int, measure: str) -> np.ndarray:
        """The fall labels on ``t``: the RAW forward fall. A LEVEL, never a rank (D13).

        ``rank01``/``rank_columns`` is deliberately NOT applied here and must never be added. Every
        FEATURE column is already rank-normalised per date; a per-date rank LABEL on top of that
        makes the prediction distribution near-stationary across dates by construction, so the head
        could only ever select a count that moved with cross-sectional composition noise, and in
        October 2008 the per-date ranks are still uniform -- the label could not encode "all of
        them" even in principle. The level can; that is the whole point of this path.

        NaN is passed through unchanged and still means "not known": ``fall_training_set`` drops
        those rows and ``forward_fall`` never returns 0.0 for an unmeasurable window.
        """
        return self.forward_fall(t, horizon, measure)

    def fall_section(self, t: date, members: AbstractSet[str] | None = None) -> Section:
        """The fall model's section on ``t``: the ranker's, plus the three market-level columns.

        ``self.section(...)`` is the ranker's own cached builder and is called, never copied, so
        the seven rank-normalised columns are byte-identical between the two heads and the feature
        work is paid for once. ``build_fall_section`` appends the un-normalised level columns (D13).
        Cached in ``_fall_sections``, its own dict, so a 10-column fall section can never be served
        where a 7-column ranker section was asked for.
        """
        inputs, _ = self._live()
        key = (t, None if members is None else frozenset(members))
        hit = self._fall_sections.get(key)
        if hit is None:
            base = self.section(t) if members is None else self.section(t, members)
            hit = build_fall_section(base, inputs.history, MOMENTUM_COL)
            self._fall_sections[key] = hit
        return hit

    def fall_training_set(
        self, params: FallSizeParams, anchor: date
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
        """(X, y, groups, labelled month-ends) for a fall refit on ``anchor``.

        Rows are stacked by (t, symbol) exactly as the ranker's ``training_set`` stacks them, and
        ``groups`` carries each row's training-date index, 0 .. months-1. The head's ladder is a
        distribution over DATES, not over rows, so the fit needs to know which rows belong to which
        date; without ``groups`` a date with 500 names would outvote one with 20 (D2c).

        ``training_dates`` is the ranker's own, called and never copied: it reads
        ``params.train_start`` and ``params.horizon``, which this params class carries under the
        same names, so both heads share one calendar by construction rather than by a restated rule.
        """
        k = len(fall_feature_names(self.feature_set))
        xs: list[np.ndarray] = []
        ys: list[np.ndarray] = []
        gs: list[np.ndarray] = []
        months = 0
        for t in self.training_dates(params, anchor):
            y = self.fall_labels(t, params.horizon, params.measure)
            ok = np.isfinite(y)
            if not ok.any():
                continue
            xs.append(self.fall_section(t).X[ok])
            ys.append(y[ok])
            gs.append(np.full(int(ok.sum()), months, dtype=np.int64))
            months += 1
        if not xs:
            return (
                np.empty((0, k), dtype=np.float64),
                np.empty(0, dtype=np.float64),
                np.empty(0, dtype=np.int64),
                0,
            )
        return np.concatenate(xs, axis=0), np.concatenate(ys), np.concatenate(gs), months

    def fall_model(self, params: FallSizeParams, anchor: date) -> FallModel | None:
        """The fall model refit on ``anchor``, or None with fewer than ``min_train_months`` to learn from."""
        if params.feature_set != self.feature_set:
            raise ValueError(f"params.feature_set {params.feature_set!r} != prepared {self.feature_set!r}")
        key = (anchor, params.model_key())
        if key in self._fall_models:
            return self._fall_models[key]
        X, y, groups, months = self.fall_training_set(params, anchor)
        model: FallModel | None = None
        if months >= params.min_train_months and X.shape[0] >= 2:
            model = fit_fall_model(X, y, groups, months, anchor, params)
        self._fall_models[key] = model
        return model

    def fall_model_on(self, data_date: date, params: FallSizeParams) -> FallModel | None:
        """The fall model that decides on ``data_date``: the one refit at ``anchor_for(data_date)``."""
        return self.fall_model(params, anchor_for(data_date))

    def fall_targets_on(
        self, members: AbstractSet[str], data_date: date, params: FallSizeParams
    ) -> tuple[Target, ...]:
        """The book the predicted fall sizes on ``data_date``: the calmest names, cash for the rest.

        TWO DECISIONS, DELIBERATELY SEPARATE (D13, D2c):

        - HOW MANY slots are filled is a MARKET-LEVEL question. The date's cross-sectional MEAN
          predicted fall is located in the model's own training distribution of date-level means
          (``model.levels``, sorted at fit time); ``danger`` is the share of training dates that
          looked no more dangerous, and the book holds ``slots - floor(danger * slots)`` whole
          slots. Calmer than every training date -> a full book; more dangerous than all of them ->
          entirely cash; at the median -> half. Monotone, both ends reachable, and not one number
          in it was chosen: the ladder IS the empirical distribution of the model's own in-sample
          predictions, so nothing was read off the dev window.
        - WHICH names fill them is the ordinary cross-sectional question: predicted fall ascending,
          ties by symbol.

        Every held name is at ``equal_weight(params.slots)`` whatever the count -- the book is NEVER
        renormalised onto the survivors, and the unfilled slots are cash. With ``size`` off the
        ladder is ignored entirely and ``k`` is ``slots``: the always-full control.

        A non-finite prediction is dropped before both the mean and the sort, so no NaN reaches
        either; when nothing is finite the date is all cash.
        """
        if params.feature_set != self.feature_set:
            raise ValueError(f"params.feature_set {params.feature_set!r} != prepared {self.feature_set!r}")
        model = self.fall_model_on(data_date, params)
        if model is None:
            return ()
        sec = self.fall_section(data_date, members)
        if not sec.symbols:
            return ()
        pred = model.predict(sec.X)
        live = [k for k in range(len(sec.symbols)) if math.isfinite(float(pred[k]))]
        if not live:
            return ()
        k_slots = params.slots if not params.size else model.exposure(
            float(np.mean([float(pred[k]) for k in live])), params.slots
        )
        if k_slots <= 0:
            return ()
        order = sorted(live, key=lambda k: (float(pred[k]), sec.symbols[k]))
        weight = equal_weight(params.slots)
        out: list[Target] = []
        for k in order:
            if len(out) == k_slots:
                break
            target = target_from_close(sec.symbols[k], float(sec.close[k]), weight)
            if target is not None:
                out.append(target)
        return tuple(out)
```

**Impact:** `TreeRankPrepared` grows a second, parallel label-and-model path. The first path's
methods are not called by any of these except `self.end`, `self.section` and `self.training_dates`,
all of which are read-only and shared on purpose (one calendar, one base feature matrix, one cache
of cross-sections — so a method that runs both heads pays for the ranker's features once, and the
fall path pays only for its three appended columns).

---

### Step 5a: forward references

`_falls`/`_fall_models` annotate `FallModel`, and `fall_model` calls `fit_fall_model`, both defined
in step 6 at the end of the file. `from __future__ import annotations` is at `:96`, so the
annotations are strings and never evaluated; `fit_fall_model` and `FallModel` are module globals
resolved at call time, exactly as `forward_returns` is resolved from inside
`TreeRankPrepared.forward_returns` today. No reordering is needed and none should be done.

---

### Step 6: the fall params, the fall model and the fit

**File:** `engine/src/seer_engine/lab/tree_rank.py` — append after step 3's block, at the end of
the file.

**Code:**

```python
# ------------------------------------------------------------- the fall model and its sizing head


@dataclass(frozen=True, slots=True)
class FallSizeParams:
    """The fall model's pre-registered knobs. Every field enters the config digest.

    A new class rather than a field on ``TreeRankParams``: ``lab.method.config_text`` writes
    ``params={registry._canon(c.params)}`` over every ``compare`` field of the params dataclass,
    so one more field there would move five of M0130's six recorded ``config_digest``s (measured
    2026-10-13: M0130-P20 381a0d7c -> e7d9e0c2, and four more) and silently rewrite closed records.
    The two classes share ``fit_model``, the calendar, the features and the section cache by reuse.

    At most ``slots`` names are held, each at ``equal_weight(slots)``, and the unfilled slots are
    cash. ``size`` is the sizing switch: on, the model's own exposure ladder decides how many of
    the slots are filled; off, the book is always full and the method is the control that isolates
    what the sizing adds. ``measure`` picks the forward-fall measure (``FALL_MEASURES``) -- both
    are LEVELS, in their own units, never ranks (D13). ``feature_set`` must name the allocator
    object's own set (``FALL_SIZE``: "price"). The five model fields are
    ``HistGradientBoostingRegressor``'s and default to Strategy B's pre-registered ``TREE_PARAMS``,
    as the ranker's do. ``horizon`` is the label's length in sessions and defaults to ``QUARTER``.
    The refit cadence is fixed (annual), not a knob.
    """

    slots: int = 20
    size: bool = True
    feature_set: FeatureSet = "price"
    measure: FallMeasure = "drawdown"
    learning_rate: float = 0.05
    max_iter: int = 300
    max_leaf_nodes: int = 15
    min_samples_leaf: int = 200
    l2: float = 1.0
    train_start: date = date(1996, 1, 31)
    min_train_months: int = 35
    horizon: int = QUARTER
    seed: int = 0

    def __post_init__(self) -> None:
        _check_int("slots", self.slots, 1, MAX_TOP)
        if not isinstance(self.size, bool):
            raise TypeError(f"size must be a bool, got {type(self.size).__name__}")
        if not isinstance(self.feature_set, str):
            raise TypeError(f"feature_set must be a str, got {type(self.feature_set).__name__}")
        feature_names(self.feature_set)
        if not isinstance(self.measure, str):
            raise TypeError(f"measure must be a str, got {type(self.measure).__name__}")
        if self.measure not in FALL_MEASURES:
            raise ValueError(f"measure must be one of {FALL_MEASURES}, got {self.measure!r}")
        object.__setattr__(
            self, "learning_rate", _check_float("learning_rate", self.learning_rate, positive=True, at_most=1.0)
        )
        _check_int("max_iter", self.max_iter, 1, 10_000)
        _check_int("max_leaf_nodes", self.max_leaf_nodes, 2, 4096)
        _check_int("min_samples_leaf", self.min_samples_leaf, 1)
        object.__setattr__(self, "l2", _check_float("l2", self.l2, positive=False))
        _check_date("train_start", self.train_start)
        _check_int("min_train_months", self.min_train_months, 1)
        _check_int("horizon", self.horizon, 1, 252)
        _check_int("seed", self.seed, 0, 2**32 - 1)

    def model_key(self) -> tuple[Any, ...]:
        """Every field a fitted fall model depends on.

        NEITHER ``slots`` NOR ``size`` is in it, exactly as ``TreeRankParams.model_key()`` leaves
        ``top_n`` out, because neither touches the fit. ``levels`` and ``cut`` are the distribution
        of the model's own per-date in-sample predictions; ``slots`` is applied to that
        distribution at DECISION time by the exposure ladder, and ``size`` only decides whether the
        ladder is consulted at all. So two variants differing only in book size share one annual
        refit ladder -- which is both cheaper and the honest statement that they are the same model.
        """
        return (
            self.feature_set,
            self.measure,
            self.learning_rate,
            self.max_iter,
            self.max_leaf_nodes,
            self.min_samples_leaf,
            self.l2,
            self.train_start,
            self.min_train_months,
            self.horizon,
            self.seed,
        )

    def as_dict(self) -> dict[str, str]:
        """Every parameter as a plain string, in a fixed key order (report and pre-registration)."""
        return {
            "slots": str(self.slots),
            "size": "on" if self.size else "off",
            "feature_set": self.feature_set,
            "measure": self.measure,
            "learning_rate": _plain(self.learning_rate),
            "max_iter": str(self.max_iter),
            "max_leaf_nodes": str(self.max_leaf_nodes),
            "min_samples_leaf": str(self.min_samples_leaf),
            "l2": _plain(self.l2),
            "train_start": self.train_start.isoformat(),
            "min_train_months": str(self.min_train_months),
            "horizon": str(self.horizon),
            "seed": str(self.seed),
        }


@dataclass(frozen=True, eq=False)
class FallModel:
    """One fall refit, plus the training distribution of DATE-LEVEL predicted falls its head reads.

    Identity is (anchor, months, rows, n_features, digest, levels); the estimator is the payload,
    as in ``TreeModel``. ``levels`` is in the identity because it is what the head actually
    consults, and ``cut`` is derived from it, so two models with the same estimator and the same
    levels are the same model to every caller.

    ``levels`` is a sorted ``tuple[float, ...]``, not an ndarray: the dataclass is hashable and a
    recorded model must compare by value. One float per labelled training month-end, so a few
    hundred at most.
    """

    anchor: date
    months: int  # labelled month-ends it learned from
    rows: int
    n_features: int
    digest: str  # b_model._tree_digest of the fitted estimator
    levels: tuple[float, ...]  # sorted mean in-sample predicted fall, one per training date
    estimator: HistGradientBoostingRegressor

    @property
    def cut(self) -> float:
        """The median training date-level predicted fall: the half-exposure point.

        Reported and tested as the model's single scalar summary of "what an ordinary date looks
        like to me". The head does not read it directly -- it reads the whole of ``levels`` -- but
        ``exposure(cut, slots)`` is about half of ``slots`` by construction, which is what makes
        this the honest one-number description of the ladder.
        """
        return self.levels[len(self.levels) // 2]

    def exposure(self, level: float, slots: int) -> int:
        """How many whole slots a cross-section at ``level`` is worth: 0 .. ``slots``.

        ``danger`` is the share of this model's training dates that looked NO MORE dangerous than
        ``level``; the book keeps the complement. Calmer than every training date -> ``slots``;
        more dangerous than all of them -> 0; at the median -> half. Monotone non-increasing in
        ``level``, so a more dangerous-looking market can never buy the book more exposure.

        Nothing here is a chosen number: the ladder is the empirical CDF of the model's own
        in-sample date-level predictions. An absolute threshold would have had to be read off the
        dev window, which pre-registration forbids.
        """
        danger = float(np.searchsorted(np.asarray(self.levels), level, side="right")) / float(
            len(self.levels)
        )
        return int(slots - math.floor(danger * slots))

    def _key(self) -> tuple[Any, ...]:
        return (self.anchor, self.months, self.rows, self.n_features, self.digest, self.levels)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FallModel):
            return NotImplemented
        return self._key() == other._key()

    def __hash__(self) -> int:
        return hash(self._key())

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predicted fall per row -- a LEVEL in the label's own units -- float64, one thread."""
        return _predict(self.estimator, X)


def _predict(estimator: HistGradientBoostingRegressor, X: np.ndarray) -> np.ndarray:
    """``estimator``'s predictions, float64, under a one-thread limit (module docstring, DETERMINISM)."""
    with threadpool_limits(limits=1):
        return np.asarray(estimator.predict(X), dtype=np.float64)


def fit_fall_model(
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    months: int,
    anchor: date,
    params: FallSizeParams,
) -> FallModel:
    """``params``' regressor fitted on (X, y), plus the training distribution its head reads.

    The fit is ``fit_model``, shared with the ranker and not modified, so the two heads differ in
    their label and in nothing else -- including the all-blank-column guard, which matters for the
    market columns on a history that does not reach back far enough and is otherwise inert.

    THE LEVELS are the model's own in-sample predictions averaged WITHIN each training date, then
    sorted. A distribution over DATES, not over rows, which is why ``groups`` is a parameter: the
    head asks "how dangerous does this whole cross-section look, against the cross-sections I was
    trained on", and a date with 500 names must not outvote one with 20. ``FallModel.cut`` is their
    median and ``FallModel.exposure`` is the ladder (D13, D2c).

    Nothing in this is a chosen number and nothing was read off the dev window: the ladder is the
    empirical CDF of the model's own training predictions. ``params.slots`` is NOT used here at all
    -- it is applied to this distribution at decision time -- which is why it is out of
    ``model_key()`` and why two variants differing only in book size share one fit.

    Predicting on the caller's ``X`` rather than on ``fit_model``'s internally zeroed copy is
    deliberate and makes no difference: an all-blank column is binned into one bin and never split
    on, which ``tests/test_tree_rank.py::test_an_all_missing_column_fits_as_unsplittable_and_leaves_other_fits_untouched``
    already pins.
    """
    estimator = fit_model(X, y, params)
    rows = int(X.shape[0])
    inside = _predict(estimator, X)
    levels = tuple(
        sorted(float(np.mean(inside[groups == g])) for g in range(months) if bool((groups == g).any()))
    )
    return FallModel(
        anchor,
        months,
        rows,
        int(X.shape[1]),
        _tree_digest(estimator),
        levels,
        estimator,
    )
```

**Impact:** `fit_model` is called with a `FallSizeParams`, which carries every attribute it reads
(`learning_rate`, `max_iter`, `max_leaf_nodes`, `min_samples_leaf`, `l2`, `seed`). `fit_model`'s
annotation still says `TreeRankParams`; annotations are not enforced and the function is not
edited. This is the "reuse `fit_model` unchanged" the scope asks for. `levels` is non-empty
whenever `months >= 1`, which `fall_model` already guarantees before calling (`min_train_months`
is at least 1), so `cut` and `exposure` never index an empty tuple.

---

### Step 7: the allocator and its from-scratch sibling

**File:** `engine/src/seer_engine/lab/tree_rank.py` — append after step 6's block, at the end of
the file.

**Code:**

```python
class FallSizeAllocator:
    """The fall model behind the ``Allocator`` and ``MarketAware`` protocols (module docstring).

    One object per feature set, as ``TreeRankAllocator`` is: ``id`` and ``market_fields`` are what
    ``lab run`` reads, and they depend on whether fundamentals are ranked on. ``FALL`` was free
    across all 75 allocator ids in the registry and every discovered lab method on 2026-10-13, and
    ``tests/test_tree_fall.py`` keeps it free.

    ONLY THE "price" OBJECT IS EXPORTED (D14). The ``"price+fund"`` branch stays reachable and is
    exercised by constructing one locally in the tests, but no module-level ``FALL_SIZE_FUND``
    exists: the EDGAR panel starts in 2009, so no method may pre-register on fundamentals (D8), and
    an exported allocator no method can use would claim the id ``FALLF`` forever for nothing.
    """

    def __init__(self, feature_set: str) -> None:
        feature_names(feature_set)
        self.feature_set = feature_set
        self.id = "FALL" if feature_set == "price" else "FALLF"
        self.market_fields: tuple[str, ...] = (
            ("dividends",) if feature_set == "price" else ("dividends", "fundamentals")
        )

    def _check(self, params: object) -> FallSizeParams:
        if not isinstance(params, FallSizeParams):
            raise TypeError(f"params must be FallSizeParams, got {type(params).__name__}")
        if params.feature_set != self.feature_set:
            raise ValueError(
                f"{self.id} ranks feature_set {self.feature_set!r}; params name {params.feature_set!r}"
            )
        return params

    def lookback(self, params: Any) -> int:
        """``FALL_FEATURE_LOOKBACK`` -- the fall model's own constant, not the ranker's.

        It evaluates to the same 401 today (the market columns reach 252 and 61 sessions, both
        inside the ranker's window), but it is written as its own ``max`` so that the claim is
        arithmetic rather than a coincidence a later edit could quietly break.
        """
        self._check(params)
        return FALL_FEATURE_LOOKBACK

    def symbols(self, params: Any) -> tuple[str, ...]:
        self._check(params)
        return (RESID.market,)

    def holds(self, params: Any) -> tuple[str, ...]:
        self._check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        self._check(params)
        return True

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        """The history-only path: no membership history, no calendar, so no model and no target."""
        self._check(params)
        _check_call(members, data_date, held)
        return ()

    def prepare(self, history: Mapping[str, History]) -> TreeRankPrepared:
        return TreeRankPrepared(self.feature_set)

    def prepare_market(self, market: Any) -> TreeRankPrepared:
        return TreeRankPrepared.build(TreeInputs.from_market(market), self.feature_set)

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = self._check(params)
        _check_call(members, data_date, held)
        if not isinstance(prepared, TreeRankPrepared):
            raise TypeError(f"prepared must be TreeRankPrepared, got {type(prepared).__name__}")
        if prepared.feature_set != self.feature_set:
            raise ValueError(f"{self.id} was handed a prepared value for feature_set {prepared.feature_set!r}")
        if prepared.inputs is None:
            return ()
        return prepared.fall_targets_on(members, data_date, p)


FALL_SIZE = FallSizeAllocator("price")
#: No FALL_SIZE_FUND (D14/D8): the EDGAR panel starts in 2009, no method may pre-register on it,
#: and an exported allocator nothing uses would claim the id "FALLF" for ever. The "price+fund"
#: branch above stays reachable; construct one locally if you need it.


def fall_targets_with_inputs(
    inputs: TreeInputs,
    members: AbstractSet[str],
    data_date: date,
    held: frozenset[str],
    params: FallSizeParams,
) -> tuple[Target, ...]:
    """The fall model's from-scratch path: every feature, label, model and cut rebuilt from
    ``inputs`` cut at ``data_date``.

    Slow by design, and the sibling of ``targets_with_inputs``. The prepared path must equal it bit
    for bit (tests/test_tree_fall.py), which is what proves that the shared section cache, the
    shared calendar and the two private caches never let anything dated after ``data_date`` in.
    """
    if not isinstance(inputs, TreeInputs):
        raise TypeError(f"inputs must be TreeInputs, got {type(inputs).__name__}")
    if not isinstance(params, FallSizeParams):
        raise TypeError(f"params must be FallSizeParams, got {type(params).__name__}")
    _check_call(members, data_date, held)
    prepared = TreeRankPrepared.build(inputs.upto(data_date), params.feature_set)
    return prepared.fall_targets_on(members, data_date, params)
```

**Impact:** **one** new module-level allocator object. `TREE_RANK`/`TREE_RANK_FUND` at `:811-812`
and `targets_with_inputs` at `:815` are untouched and still the ranker's. `FALL_SIZE` is the object
phase 5 imports, and it is the only one.

---

### Step 8: the test module

**File:** `engine/tests/test_tree_fall.py` (new)

**Change:** 21 tests. The synthetic market, the probe dates and the membership helper are
**imported** from `tests/test_tree_rank.py` rather than copied, so the two heads are proved on
exactly the same market and the fixture can never drift. (`test_tree_rank.py` already imports from
a sibling test module, `test_strategy_purity`, so this is the established pattern.)
`test_tree_rank.py` itself is not edited.

**Code:**

```python
"""The forward-fall label and the sizing head (lab/tree_rank.py; R2, handover 2026-10-13).

The ranker's own tests are in tests/test_tree_rank.py and are untouched; this module tests only
what was added beside it. The market, the probe dates and the membership helper are imported from
there so both heads are judged on the same synthetic history.

What is proved here: the two fall measures on hand-built paths, including that an unmeasurable
window is NaN and a calm window is a measured 0.0; that nothing dated after the label end is read;
**that the fall label is the RAW measure and is never rank-normalised (D13)**; **that the three
market-level columns are appended un-normalised, are constant within a date, move across dates, and
read no bar after the decision date**; that the fall caches and the return caches cannot serve each
other; that the fit is deterministic; **that the exposure ladder is monotone in the market level and
reaches both ends**; that the head sizes the book in whole slots at a fixed weight and can go to
cash; that the prepared path equals the from-scratch path bit for bit; that nothing after the
decision date changes a target; that the history-only path targets nothing; that a candidate runs
the lab's smoke window at a reach of 401 ≤ 473; and that `FALL` is free across the whole lab while
`FALLF` is left unclaimed.

The module's purity is already covered: tests/test_tree_rank.py's AST and fresh-interpreter checks
read the whole of lab/tree_rank.py, additions included.
"""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal

import numpy as np
import pytest
from allocatorkit import assert_no_lookahead, assert_p4_identity, assert_valid_targets, everyone
from labkit import SPY_EX_DATE, smoke_market
from stratkit import hist, mutate_from, truncate_before
from test_tree_rank import DAYS, DIVS, MARKET, PANEL, STOCKS, members

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.dev import DEV_END, Candidate, run_candidate
from seer_engine.backtest.market import DividendCalendar, Market, Membership
from seer_engine.backtest.registry import REGISTRY
from seer_engine.lab import runner
from seer_engine.lab.method import discover
from seer_engine.lab.tree_rank import (
    FALL_FEATURE_LOOKBACK,
    FALL_MEASURES,
    FALL_SIZE,
    FEATURE_LOOKBACK,
    MARKET_FEATURES,
    MARKET_HIGH_N,
    MARKET_VOL_N,
    QUARTER,
    TREE_RANK,
    FallSizeAllocator,
    FallSizeParams,
    Section,
    TreeInputs,
    TreeRankPrepared,
    anchor_for,
    fall_feature_names,
    fall_targets_with_inputs,
    feature_names,
    forward_downside_vol,
    forward_drawdown,
    forward_fall,
    market_columns,
    month_ends,
    year_end,
)
from seer_engine.sim.book import equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND, TARGET_RESIZE_BAND
from seer_engine.strategies.allocator import Allocator, MarketAware
from types import SimpleNamespace

# The ranker's SMALL, re-pointed at the fall: a quarter's horizon, three slots, sizing on.
SMALL = FallSizeParams(
    slots=3,
    max_iter=15,
    max_leaf_nodes=7,
    min_samples_leaf=5,
    train_start=date(2010, 2, 1),
    min_train_months=6,
    horizon=QUARTER,
)
FULL = replace(SMALL, size=False)  # the control: always fully invested
VOL = replace(SMALL, measure="downside_vol")
FUND = replace(SMALL, feature_set="price+fund")  # D14: no exported object; built locally below
FALL_FUND = FallSizeAllocator("price+fund")  # local only -- never a module-level name
FUND_MARKET = SimpleNamespace(
    history=MARKET.history, membership=MARKET.membership, dividends=MARKET.dividends, fundamentals=PANEL
)

# 2010-11-30's anchor is 2009-12-31, before the first fall model; the rest trade.
PROBES: tuple[date, ...] = (
    date(2010, 11, 30),
    date(2010, 12, 31),
    date(2011, 6, 30),
    date(2012, 12, 31),
    date(2013, 3, 14),
    date(2014, 11, 28),
)
DECIDE: tuple[date, ...] = month_ends(date(2012, 1, 1), date(2014, 11, 30))


@pytest.fixture(scope="module")
def prepared() -> TreeRankPrepared:
    return FALL_SIZE.prepare_market(MARKET)


def book(prep: TreeRankPrepared, d: date, params: FallSizeParams):
    return FALL_SIZE.targets_prepared(prep, members(d), d, frozenset(), params)


# ---- the two measures, by hand ------------------------------------------------------------------


def _bare_section(day: date, symbols: tuple[str, ...]) -> Section:
    """A Section carrying only what the measures read: the day and the symbols."""
    n = len(symbols)
    return Section(day, symbols, np.zeros(n), np.zeros((n, 1)), np.zeros((n, 1)))


def _tiny_history(closes: dict[str, list[float]], days: list[date]):
    return {s: hist(s, c, days=days[: len(c)], volume=5e6) for s, c in closes.items()}


def test_forward_drawdown_is_the_worst_peak_to_trough_fall():
    days = dates.sessions(date(2014, 1, 2), date(2014, 1, 10))  # 7 sessions
    t, end = days[0], days[3]
    history = _tiny_history(
        {
            "DIP": [100.0, 110.0, 88.0, 99.0, 10.0, 10.0, 10.0],   # 1 - 88/110 = 0.20, crash after end
            "UP": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0],
            "SHORT": [100.0],                                       # no bar after t
            "ZERO": [100.0, 0.0, 90.0, 95.0, 95.0, 95.0, 95.0],     # an unusable close in the window
        },
        days,
    )
    sec = _bare_section(t, ("DIP", "UP", "SHORT", "ZERO"))
    got = forward_drawdown(history, sec, end)
    assert got[0] == pytest.approx(0.20)
    assert got[1] == 0.0 and not math.isnan(got[1])  # measured calm is zero, never NaN
    assert math.isnan(got[2])
    assert math.isnan(got[3])
    assert not got.flags.writeable


def test_forward_downside_vol_is_the_root_mean_square_of_the_down_days():
    days = dates.sessions(date(2014, 1, 2), date(2014, 1, 10))
    t, end = days[0], days[3]
    history = _tiny_history(
        {"DIP": [100.0, 110.0, 88.0, 99.0, 10.0, 10.0, 10.0], "UP": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0]},
        days,
    )
    sec = _bare_section(t, ("DIP", "UP"))
    got = forward_downside_vol(history, sec, end)
    assert got[0] == pytest.approx(math.sqrt((0.2**2) / 3))  # +10%, -20%, +12.5% over three days
    assert got[1] == 0.0


def test_no_bar_after_the_label_end_is_ever_read():
    """The 10.0 crash on the sessions after ``end`` must not reach either measure."""
    days = dates.sessions(date(2014, 1, 2), date(2014, 1, 10))
    t, end = days[0], days[3]
    full = _tiny_history({"DIP": [100.0, 110.0, 88.0, 99.0, 10.0, 10.0, 10.0]}, days)
    cut = _tiny_history({"DIP": [100.0, 110.0, 88.0, 99.0]}, days)
    sec = _bare_section(t, ("DIP",))
    for measure in FALL_MEASURES:
        np.testing.assert_array_equal(
            forward_fall(full, sec, end, measure), forward_fall(cut, sec, end, measure)
        )
    with pytest.raises(ValueError, match="measure"):
        forward_fall(full, sec, end, "variance")


# ---- the label ----------------------------------------------------------------------------------


def test_the_fall_label_is_the_raw_level_and_is_never_rank_normalised(prepared):
    """D13: the label is the measure itself. rank01 is not applied and must never be."""
    t = date(2012, 6, 29)
    raw = prepared.forward_fall(t, QUARTER, "drawdown")
    labels = prepared.fall_labels(t, QUARTER, "drawdown")
    np.testing.assert_array_equal(labels, raw)  # identical, not merely correlated
    finite = np.isfinite(raw)
    assert finite.any()
    assert (np.isfinite(labels) == finite).all()
    # a rank label would be exactly {0, 1/(n-1), ..., 1} on every date. This one is not.
    vals = np.sort(labels[finite])
    assert not (vals[0] == 0.0 and vals[-1] == 1.0 and len(vals) > 2)
    assert prepared.end(t, QUARTER) == date(2012, 9, 28)


def test_two_dates_labels_live_on_a_shared_scale(prepared):
    """The point of a level: a calm date and a violent date are comparable, which ranks are not.

    Pick the two decision dates whose mean finite drawdown differs most and assert the means
    differ. Under the superseded rank label every date's mean is (n-1)/2n ~ 0.5 by construction and
    this test is impossible to pass -- which is exactly why it is here.
    """
    means = {}
    for t in DECIDE:
        y = prepared.fall_labels(t, QUARTER, "drawdown")
        ok = np.isfinite(y)
        if ok.any():
            means[t] = float(np.mean(y[ok]))
    assert len(means) >= 10
    assert max(means.values()) - min(means.values()) > 0.01


def test_the_fall_cache_and_the_return_cache_cannot_serve_each_other(prepared):
    t = date(2012, 6, 29)
    rets = prepared.forward_returns(t, QUARTER)
    dd = prepared.forward_fall(t, QUARTER, "drawdown")
    dv = prepared.forward_fall(t, QUARTER, "downside_vol")
    assert not np.array_equal(rets, dd)
    assert not np.array_equal(dd, dv)
    assert (dd[np.isfinite(dd)] >= 0.0).all()  # a fall is never negative; a return can be
    # the caches are different dicts, keyed differently, and first-use order cannot matter
    assert all(len(k) == 2 for k in prepared._returns)
    assert all(len(k) == 3 for k in prepared._falls)
    a, b = TREE_RANK.prepare_market(MARKET), TREE_RANK.prepare_market(MARKET)
    a.forward_returns(t, QUARTER)
    np.testing.assert_array_equal(a.forward_fall(t, QUARTER, "drawdown"), b.forward_fall(t, QUARTER, "drawdown"))
    b.forward_returns(t, QUARTER)
    np.testing.assert_array_equal(a.forward_returns(t, QUARTER), b.forward_returns(t, QUARTER))


# ---- the market-level columns (D13) ---------------------------------------------------------------


def test_the_market_columns_are_appended_un_normalised_and_constant_within_a_date(prepared):
    t = date(2012, 6, 29)
    base = prepared.section(t)
    fall = prepared.fall_section(t)
    k = len(feature_names("price"))
    assert fall_feature_names("price") == tuple(feature_names("price")) + MARKET_FEATURES
    assert base.X.shape[1] == k == 7
    assert fall.X.shape[1] == k + len(MARKET_FEATURES) == 10
    # the ranker's own columns pass through byte for byte: build_section is composed, not replaced
    np.testing.assert_array_equal(fall.X[:, :k], base.X)
    np.testing.assert_array_equal(fall.raw[:, :k], base.raw)
    assert fall.symbols == base.symbols and fall.day == base.day
    # each appended column is ONE value repeated down the rows: a level, carrying no cross-section
    for c in range(k, fall.X.shape[1]):
        col = fall.X[:, c]
        assert len(np.unique(col[np.isfinite(col)])) <= 1
    # and it is NOT a rank column: rank01 would put it in [0, 1] with the ends hit
    assert not fall.X.flags.writeable


def test_the_market_columns_move_across_dates_which_is_the_whole_point(prepared):
    """A level the model can read. Under per-date ranking alone these would be constants."""
    seen = {c: set() for c in range(len(MARKET_FEATURES))}
    for t in DECIDE:
        sec = prepared.fall_section(t)
        for c in range(len(MARKET_FEATURES)):
            v = float(sec.X[0, len(feature_names("price")) + c])
            if math.isfinite(v):
                seen[c].add(round(v, 9))
    for c, vals in seen.items():
        assert len(vals) >= 5, (MARKET_FEATURES[c], sorted(vals))


def test_the_market_columns_read_no_bar_after_the_decision_date():
    """Same discipline as _window: searchsorted(side='right') on the decision date."""
    days = dates.sessions(date(2012, 1, 3), date(2014, 1, 10))
    closes = [100.0 + i for i in range(len(days))]
    full = {"SPY": hist("SPY", closes, days=days, volume=5e6)}
    cut_at = 400
    cut = {"SPY": hist("SPY", closes[: cut_at + 1], days=days[: cut_at + 1], volume=5e6)}
    mom = np.array([0.1, 0.2, 0.3])
    assert market_columns(full, days[cut_at], mom) == market_columns(cut, days[cut_at], mom)
    # a market with no SPY at all is NaN on the two SPY columns, never an exception
    dd, vol, disp = market_columns({}, days[cut_at], mom)
    assert math.isnan(dd) and math.isnan(vol) and math.isfinite(disp)
    assert FALL_FEATURE_LOOKBACK == max(FEATURE_LOOKBACK, MARKET_HIGH_N, MARKET_VOL_N + 1) == 401


# ---- params and protocol -------------------------------------------------------------------------


def test_params_defaults_validation_and_as_dict():
    assert FallSizeParams().as_dict() == {
        "slots": "20",
        "size": "on",
        "feature_set": "price",
        "measure": "drawdown",
        "learning_rate": "0.05",
        "max_iter": "300",
        "max_leaf_nodes": "15",
        "min_samples_leaf": "200",
        "l2": "1",
        "train_start": "1996-01-31",
        "min_train_months": "35",
        "horizon": "63",
        "seed": "0",
    }
    assert FallSizeParams().horizon == QUARTER == 63
    coerced = FallSizeParams(learning_rate=1, l2=0)
    assert isinstance(coerced.learning_rate, float) and isinstance(coerced.l2, float)
    for bad in (
        dict(slots=0), dict(slots=101), dict(feature_set="fund"), dict(measure="variance"),
        dict(learning_rate=0.0), dict(learning_rate=1.5), dict(max_iter=0), dict(max_leaf_nodes=1),
        dict(min_samples_leaf=0), dict(l2=-1.0), dict(min_train_months=0), dict(horizon=0),
        dict(horizon=253), dict(seed=-1),
    ):
        with pytest.raises(ValueError):
            FallSizeParams(**bad)
    for bad in (dict(slots=True), dict(size=1), dict(measure=1), dict(train_start=datetime(1996, 1, 31))):
        with pytest.raises(TypeError):
            FallSizeParams(**bad)
    # D2c2: neither slots nor size touches the fit, exactly as top_n does not for the ranker
    assert replace(SMALL, size=False).model_key() == SMALL.model_key()
    assert replace(SMALL, slots=5).model_key() == SMALL.model_key()
    assert replace(SMALL, measure="downside_vol").model_key() != SMALL.model_key()


def test_one_fall_allocator_object_and_what_lab_run_reads_off_it():
    assert isinstance(FALL_SIZE, Allocator) and isinstance(FALL_SIZE, MarketAware)
    assert FALL_SIZE.id == "FALL"
    assert runner.market_fields(FALL_SIZE) == ("dividends",)
    assert FALL_SIZE.lookback(SMALL) == FALL_FEATURE_LOOKBACK == 401
    assert FALL_SIZE.symbols(SMALL) == ("SPY",)
    assert FALL_SIZE.holds(SMALL) == ()
    assert FALL_SIZE.uses_members(SMALL) is True
    with pytest.raises(ValueError, match="feature_set"):
        FALL_SIZE.lookback(FUND)
    with pytest.raises(TypeError):
        FALL_SIZE.lookback(object())
    # D14: there is no module-level fundamentals object to import
    import seer_engine.lab.tree_rank as tr

    assert not hasattr(tr, "FALL_SIZE_FUND")


def test_the_new_allocator_id_is_free_and_fallf_is_left_unclaimed():
    """D5: a config digest names the allocator by id, so a collision would merge two methods."""
    taken = {str(c.allocator.id) for c in REGISTRY}
    for _, (method, _) in discover().items():
        taken |= {str(c.allocator.id) for c in method.all_candidates()}
    assert "FALL" not in taken
    assert "FALLF" not in taken  # D14: left free for whoever needs it, claimed by nothing here
    assert len(taken) >= 75


# ---- the model ------------------------------------------------------------------------------------


def test_no_model_before_enough_months_means_cash(prepared):
    early = date(2010, 11, 30)
    assert prepared.fall_model_on(early, SMALL) is None  # its refit is 2009-12-31: no sample yet
    assert book(prepared, early, SMALL) == ()
    model = prepared.fall_model_on(date(2010, 12, 31), SMALL)
    assert model is not None
    assert (model.anchor, model.n_features) == (date(2010, 12, 31), 10)  # 7 ranked + 3 level
    assert model.months >= SMALL.min_train_months
    assert len(model.levels) == model.months  # one date-level mean per labelled month-end
    strict = replace(SMALL, min_train_months=model.months + 1)
    assert prepared.fall_model_on(date(2010, 12, 31), strict) is None


def test_two_prepares_fit_bit_identical_fall_models_and_levels():
    a = FALL_SIZE.prepare_market(MARKET)
    b = FALL_SIZE.prepare_market(MARKET)
    for year in (2011, 2012, 2013):
        ma, mb = a.fall_model(SMALL, year_end(year)), b.fall_model(SMALL, year_end(year))
        assert ma is not None and ma == mb
        assert ma.digest == mb.digest and len(ma.digest) == 64
        assert ma.levels == mb.levels and ma.cut == mb.cut
        assert list(ma.levels) == sorted(ma.levels)  # kept sorted, so searchsorted is valid
    for d in PROBES:
        assert book(a, d, SMALL) == book(b, d, SMALL)


def test_the_book_size_does_not_change_the_fit_only_the_ladder(prepared):
    """D2c2: slots and size are decision-time, not fit-time. One refit serves every book size."""
    anchor = year_end(2012)
    base = prepared.fall_model(SMALL, anchor)
    assert prepared.fall_model(FULL, anchor) is base
    assert prepared.fall_model(replace(SMALL, slots=5), anchor) is base
    assert prepared.fall_model(replace(SMALL, slots=9), anchor) is base


def test_the_exposure_ladder_is_monotone_and_reaches_both_ends(prepared):
    """D13: the head reads a MARKET-LEVEL quantity against the model's training distribution."""
    model = prepared.fall_model(SMALL, year_end(2012))
    assert model is not None
    lo, hi = model.levels[0], model.levels[-1]
    span = hi - lo
    assert span > 0.0  # the training dates did not all look identical: there IS a level to read
    for slots in (3, 5, 20):
        assert model.exposure(lo - span, slots) == slots      # calmer than anything seen -> full
        assert model.exposure(hi + span, slots) == 0          # worse than anything seen -> cash
        assert model.exposure(model.cut, slots) == pytest.approx(slots / 2, abs=1)
        ks = [model.exposure(lo + span * i / 20.0, slots) for i in range(21)]
        assert ks == sorted(ks, reverse=True)                 # monotone non-increasing
        assert all(0 <= k <= slots for k in ks)
    assert model.cut == model.levels[len(model.levels) // 2]


# ---- the head: exposure, not selection ------------------------------------------------------------


def test_the_head_holds_whole_slots_at_a_fixed_weight(prepared):
    weight = equal_weight(SMALL.slots)
    for d in DECIDE:
        got = book(prepared, d, SMALL)
        assert len(got) <= SMALL.slots
        assert all(t.weight == weight for t in got)  # never renormalised onto the survivors
        assert sum((t.weight for t in got), Decimal(0)) == weight * len(got)
        assert_valid_targets(got, MARKET.history, d, frozenset())


def test_the_head_sizes_the_book_and_the_control_does_not(prepared):
    sized = [len(book(prepared, d, SMALL)) for d in DECIDE]
    full = [len(book(prepared, d, FULL)) for d in DECIDE]
    assert max(sized) == SMALL.slots           # it reaches a full book
    assert min(sized) < SMALL.slots            # and it goes below one: this is the sizing
    assert len(set(sized)) >= 3                # in more than one step
    assert set(full) == {SMALL.slots}          # the control is always fully invested
    vol = [len(book(prepared, d, VOL)) for d in DECIDE]
    assert min(vol) < max(vol) == SMALL.slots  # the other measure sizes too


def test_a_cross_section_the_model_reads_as_dangerous_is_all_cash():
    """The k = 0 end of the range, forced rather than waited for: a training distribution that

    makes every real date look catastrophic. Deterministic, and the half of the exposure claim that
    must never be weakened.
    """
    prep = FALL_SIZE.prepare_market(MARKET)
    d = date(2013, 3, 14)
    anchor = anchor_for(d)
    model = prep.fall_model(SMALL, anchor)
    assert model is not None and book(prep, d, SMALL)
    calm = tuple(v - 10.0 for v in model.levels)  # every training date looked far calmer
    prep._fall_models[(anchor, SMALL.model_key())] = replace(model, levels=calm)
    assert book(prep, d, SMALL) == ()
    assert len(book(prep, d, FULL)) == SMALL.slots  # the control ignores the ladder and stays full
    wild = tuple(v + 10.0 for v in model.levels)   # every training date looked far worse
    prep._fall_models[(anchor, SMALL.model_key())] = replace(model, levels=wild)
    assert len(book(prep, d, SMALL)) == SMALL.slots  # ... so today is calm: a full book


def test_one_slot_is_five_times_the_resize_band():
    """D7, in the tape's own arithmetic: an exposure step the measuring tape cannot miss."""
    for slots in (3, 10, 20, 25):
        weight = equal_weight(slots)
        band = TARGET_RESIZE_BAND * weight  # of equity, per sim/book.py:462
        assert weight == band * 5
    assert MONTHLY_HOLD_FRAC_GOTRADE_TBAND.resize_basis == "target"
    assert TARGET_RESIZE_BAND == Decimal("0.20")


# ---- the two paths ---------------------------------------------------------------------------------


def test_market_path_equals_the_from_scratch_path(prepared):
    inputs = TreeInputs.from_market(MARKET)
    nonempty = 0
    for d in PROBES:
        for held in (frozenset(), frozenset({"S01"})):
            for p in (SMALL, FULL, VOL):
                got = FALL_SIZE.targets_prepared(prepared, members(d), d, held, p)
                assert got == fall_targets_with_inputs(inputs, members(d), d, held, p), (d, held, p)
                assert_valid_targets(got, MARKET.history, d, held)
                nonempty += bool(got)
    assert nonempty == 6 * (len(PROBES) - 1)  # every probe but the pre-model one trades


def test_bars_dividends_and_membership_after_d_change_nothing(prepared):
    nonempty = 0
    for d in PROBES[1:]:
        s = dates.next_session(d)
        divs = {k: list(v) for k, v in DIVS.items()}
        divs["S04"] = [(s, Decimal("5.00"))]
        intervals = tuple((sym, a, s if sym == "S07" else b) for sym, a, b in MARKET.membership.intervals)
        futures = (
            Market(
                history={k: mutate_from(h, s) for k, h in MARKET.history.items()},
                membership=Membership(intervals=intervals),
                fx=MARKET.fx,
                dividends=DividendCalendar(divs),
            ),
            Market(
                history={k: truncate_before(h, s) for k, h in MARKET.history.items()},
                membership=MARKET.membership,
                fx=MARKET.fx,
                dividends=MARKET.dividends,
            ),
        )
        before = book(prepared, d, SMALL)
        for future in futures:
            assert book(FALL_SIZE.prepare_market(future), d, SMALL) == before, (d, s)
        nonempty += bool(before)
    assert nonempty == len(PROBES) - 1


def test_the_fund_branch_is_reachable_but_is_not_exported(prepared):
    """D14 + D8: the "price+fund" branch works; no module-level object claims the id "FALLF".

    Built locally, never imported. Phase 5 may not pre-register on it (the EDGAR panel starts in
    2009), so exporting it would claim an allocator id for ever for nothing.
    """
    assert FALL_FUND.id == "FALLF"
    assert runner.market_fields(FALL_FUND) == ("dividends", "fundamentals")
    fund = FALL_FUND.prepare_market(FUND_MARKET)
    t = date(2012, 6, 29)
    assert fund.section(t).raw.shape[1] == 11
    assert fund.fall_section(t).X.shape[1] == 11 + len(MARKET_FEATURES) == 14
    assert fund.fall_model(FUND, year_end(2012)).n_features == 14
    d = date(2013, 7, 31)
    got = FALL_FUND.targets_prepared(fund, members(d), d, frozenset(), FUND)
    assert got == fall_targets_with_inputs(TreeInputs.from_market(FUND_MARKET), members(d), d, frozenset(), FUND)
    with pytest.raises(ValueError, match="feature_set"):
        FALL_FUND.targets_prepared(fund, members(d), d, frozenset(), SMALL)


def test_history_only_path_targets_nothing():
    """test_lab_methods.test_allocator_contract requires exactly this of a market-aware allocator."""
    stocks = everyone({s: MARKET.history[s] for s in STOCKS})
    probe = [dates.next_session(d) for d in PROBES[1:]]
    assert assert_p4_identity(FALL_SIZE, MARKET.history, stocks, PROBES, [frozenset()], [SMALL]) == 0
    assert assert_no_lookahead(FALL_SIZE, MARKET.history, stocks, probe, [frozenset()], [SMALL]) == 0


def test_a_candidate_runs_the_lab_smoke_window():
    """The shape phase 5's method will have, on the tape it will be priced at (473-bar fixture)."""
    params = FallSizeParams()
    market = smoke_market(FALL_SIZE.symbols(params))
    c = Candidate(
        id="M9999-FALL-SMOKE",
        family="M9999",
        rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
        allocator=FALL_SIZE,
        params=params,
        rationale="smoke: the fall model through the dev runner",
        added=date(2026, 10, 13),
        owner_inputs=(),
    )
    amount = Decimal("1.0300")
    result, row = run_candidate(market, {"SPY": {SPY_EX_DATE: amount}}, (Dividend(SPY_EX_DATE, amount),), c)
    assert row.end == DEV_END
    assert len(result.snapshots) >= 2
    # D13/M4a: the market columns add no reach. 401 is the fall allocator's own constant.
    assert FALL_SIZE.lookback(params) == FALL_FEATURE_LOOKBACK == 401
    assert FALL_SIZE.lookback(params) <= len(market.history["SPY"])  # 401 <= 473
```

**Impact:** 21 new tests. Two of them (`test_market_path_equals_the_from_scratch_path` and
`test_bars_dividends_and_membership_after_d_change_nothing`) rebuild models from scratch and are the
slowest; on the measured prototype the whole set ran in a few seconds.

**Note for the implementer on the assertions that depend on the fixture.** The counts
`nonempty == 6 * (len(PROBES) - 1)` and `len(set(sized)) >= 3` were measured on a prototype that
D13 has since replaced (the rank label and the row-quantile cut — see **M5, superseded**). **They
must be re-measured against the level label and the exposure ladder before they are written as
numbers**, and the measured histogram recorded beside them in the commit body. If a future sklearn
shifts them, the correct response is to re-measure and tighten the claim, **not** to delete the
assertion: "the head moves exposure in more than one step and reaches both ends" is the whole point
of the phase. `test_a_cross_section_the_model_reads_as_dangerous_is_all_cash` and
`test_the_exposure_ladder_is_monotone_and_reaches_both_ends` are the deterministic half of that
claim and must never be weakened.

**And `test_two_dates_labels_live_on_a_shared_scale` is D13's tripwire.** Under a per-date rank
label every date's mean label is `(n-1)/2n ≈ 0.5` by construction and that test cannot pass. If
anyone ever re-adds `rank_columns` to the fall label, it goes red — which is the point.

---

## Verification

Run all of this from the worktree. **There is no `engine/.venv` here** — the interpreter is the
main checkout's, and without `PYTHONPATH` pytest imports the main checkout's modules and tests the
wrong code.

**Build / lint:**

```bash
/home/miftah/seer/engine/.venv/bin/ruff check /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine
```

Expected: `All checks passed!` (CI lint is bugs only: `E9` and `F`, minus `F401`.)

**Import smoke (catches a forward-reference mistake from step 5a before the suite does):**

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
/home/miftah/seer/engine/.venv/bin/python -c \
"import seer_engine.lab.tree_rank as tr; \
print(tr.FALL_SIZE.id, tr.QUARTER, tr.FALL_FEATURE_LOOKBACK, tr.MARKET_FEATURES, \
tr.FallSizeParams().as_dict()['measure'], hasattr(tr, 'FALL_SIZE_FUND'))"
```

Expected:
`FALL 63 401 ('spy_drawdown_from_high', 'spy_vol_60', 'momentum_dispersion') drawdown False`

**The frozen-record tripwire, named and run on its own:**

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
/home/miftah/seer/engine/.venv/bin/python -m pytest -q -n0 \
  tests/test_lab_methods.py::test_every_recorded_configuration_still_digests_to_its_recorded_digest \
  tests/test_lab_methods.py::test_allocator_ids_are_unique_across_methods
```

Expected: `2 passed`. Quote this in the commit body: M0130's six recorded digests did not move.

**Targeted:**

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
/home/miftah/seer/engine/.venv/bin/python -m pytest -q tests/test_tree_fall.py tests/test_tree_rank.py tests/test_lab_methods.py
```

Expected: all pass, 0 failures. `test_tree_rank.py` must be green **unchanged** — it is the proof
that no existing name moved.

**Full suite** (`docker start seer-pg` first if the container is down; without `PG_TEST_URL` 385
tests skip silently and CI fails the run):

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
/home/miftah/seer/engine/.venv/bin/python -m pytest -q
```

Expected: **`4640 + 18 = 4658 passed, 3 skipped`** (baseline measured at this phase's base on
2026-10-13: `4640 passed, 3 skipped in 80.67s`). **Quote the skip count beside the pass count.**
The three skips are the opt-in live-store sweeps (`test_lab_name_count.py:240`,
`test_lab_costs.py:314`, `test_lab_survivorship.py:387`) and must stay at three. If a peer phase has
landed in the meantime the pass count will be higher than 4658; the skip count still must be 3.

**Manual check:** `git diff` the module and confirm the only changed regions are the four insertion
points of steps 1-7 and nothing between them:

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label && \
git diff -- engine/src/seer_engine/lab/tree_rank.py | grep -c '^-[^-]'
```

Expected: **`0`** — the diff is pure addition. Any removed line is a frozen name being touched; stop
and undo it.

---

### M5b — the real-store exposure gate (moved here from phase 5 by D13)

**This is an exit criterion of THIS phase, not of phase 5.** Phase 5 cannot give back a method id;
this phase can be reworked for free. So the measurement that decides whether the head carries a
market-wide level at all is taken here, on the real research store, before phase 5 is allowed to
start. Phase 5 keeps its own pre-commit re-check (its Step 3) and **the redundancy is deliberate**:
the id is irreversible, and the two checks run on different days against possibly different code.

`engine/.research/` **does not exist in this worktree** and must never be rebuilt (~30 minutes plus
a yfinance crawl for nothing). Point at the main checkout's store.

Write this to the scratchpad — it is a throwaway, never committed, and it writes nothing anywhere:

```python
"""Does the fall model's head carry a market-wide level? Read-only; writes nothing.

Prints the realised exposure -- the sum of target weights -- on the January decision date of every
year 2000-2015. PASS: at least three distinct values AND 2008 visibly below 2005. FAIL: a flat
column, which means the head has no level to read and phase 5 must not spend a method id.

Only exposure counts are printed: no return, no drawdown, no profit factor. This is a design
sanity check on the DEV window, not a look at a result, and the test window is not touched.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from seer_engine import dates, research
from seer_engine.lab.tree_rank import FALL_SIZE, FallSizeParams

STORE = Path("/home/miftah/seer/engine/.research")


def main() -> None:
    data = research.load_store(STORE)
    market = data.market
    params = FallSizeParams(slots=20)          # the defaults phase 5 will pre-register
    control = FallSizeParams(slots=20, size=False)
    prepared = FALL_SIZE.prepare_market(market)
    print(f"store {data.fingerprint[:12]}  prices {data.price_fingerprint[:12]}")
    print(f"{'date':<12}{'names':>7}{'exposure':>11}{'control':>10}")
    for year in range(2000, 2016):
        d = dates.prev_session(date(year, 2, 1))
        who = market.membership.members_on(d)
        got = FALL_SIZE.targets_prepared(prepared, who, d, frozenset(), params)
        ctl = FALL_SIZE.targets_prepared(prepared, who, d, frozenset(), control)
        w = float(sum(float(t.weight) for t in got))
        c = float(sum(float(t.weight) for t in ctl))
        print(f"{d.isoformat():<12}{len(got):>7}{w:>11.3f}{c:>10.3f}")


if __name__ == "__main__":
    main()
```

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
/home/miftah/seer/engine/.venv/bin/python "$SCRATCHPAD/exposure_probe.py" \
  2>&1 | tee "$SCRATCHPAD/exposure_probe.out"
```

Loading the store from the main checkout was measured at about **13 seconds**; the yearly refits
dominate, so budget a few minutes.

**PASS** — both must hold:

1. the `exposure` column takes **at least three distinct values** across the sixteen lines; and
2. **2008 is visibly lower than 2005.** If the model cannot cut exposure into the one year that
   dominates every whole-window drawdown number in this lab, it has not learned a fall.

The `control` column must read `1.000` on every line — that is `size=False` doing its job and it is
the proof that any variation in the first column came from the ladder and not from the screen.

**FAIL — and this is a HARD STOP for the phase, not for phase 5.** A flat exposure column means the
market-level columns are not reaching the model or the ladder is degenerate. Do **not** improvise a
threshold and do **not** hand the problem downstream: fix it here (the usual causes, in order — the
market columns landed on `raw` but not on `X`; `MOMENTUM_COL` points at a rank column instead of the
raw one; `groups` is wrong so `levels` has one entry per row instead of one per date; SPY is absent
from the prepared market). **Report the outcome either way**, with this output attached, so the
coordinator knows before phase 5 starts whether the method id may be spent. **If it cannot be made
to pass, phase 2 reports that and phase 5 does not run.**

---

**Exit criteria:**

1. `git diff` on `tree_rank.py` removes zero lines.
2. `test_every_recorded_configuration_still_digests_to_its_recorded_digest` and
   `test_allocator_ids_are_unique_across_methods` are green, and the write-up states that M0130's
   six recorded digests were checked and did not move.
3. `FALL_SIZE` satisfies `Allocator` and `MarketAware`, and its history-only `targets` path returns
   `()` (`assert_p4_identity` and `assert_no_lookahead` both return 0). **There is no
   `FALL_SIZE_FUND`** (D14): `hasattr(tree_rank, "FALL_SIZE_FUND")` is `False` and the allocator id
   `FALLF` is claimed by nothing.
4. `prepared == from-scratch` holds bit for bit on six probe dates × two held sets × three params
   values.
5. Nothing dated after the decision date is read: both futures of the look-ahead probe leave every
   target list unchanged, the market columns are unchanged by truncating the history at the decision
   date, and `FALL_SIZE.lookback(...) == FALL_FEATURE_LOOKBACK == 401 <= 473` — **proved by the
   constant's own `max(...)`, not asserted**.
6. **The label is a level (D13):** `fall_labels(...)` is array-equal to `forward_fall(...)`, the
   module contains no call of `rank_columns`/`rank01` on a fall measure, and
   `test_two_dates_labels_live_on_a_shared_scale` is green.
7. **The feature matrix carries three un-normalised market-level columns (D13):** the fall section
   is 10 columns wide against the ranker's 7, its first 7 are byte-identical to `build_section`'s,
   each appended column is one value repeated down the rows, and each takes at least five distinct
   values across the decision dates.
8. The head's exposure reaches both ends — `max(k) == slots`, a forced-level case gives `()` — the
   ladder is monotone non-increasing in the market level, and every held name's weight is
   `equal_weight(slots)` at every count, never renormalised.
9. **M5b passes on the real research store:** exposure on the January decision dates 2000-2015 takes
   at least three distinct values **and** 2008 is below 2005, with the `size=False` control flat at
   `1.000`. The output is quoted in the phase's report. **If it does not pass, this phase reports
   that and phase 5 does not run.**
10. `ruff` clean; the full suite green with the skip count quoted beside the pass count.

---

## Handoffs

**To phase 5 (the pre-registered method, R2) — the interface it imports:**

```python
from seer_engine.lab.tree_rank import (
    FALL_SIZE,          # FallSizeAllocator("price"), id == "FALL" -- the ONLY exported object
    FallSizeParams,
    QUARTER,            # 63
    FALL_FEATURE_LOOKBACK,               # 401
    anchor_for, label_end, month_ends,   # already exported; m0130's model_ready uses them
)
```

**There is no `FALL_SIZE_FUND` to import** (D14). Importing it is an `ImportError`, by design.

```python
FallSizeParams(
    slots: int = 20,               # 1..100; the book's size in whole slots
    size: bool = True,             # False = the always-full control
    feature_set: str = "price",    # must name the allocator object's own set
    measure: str = "drawdown",     # or "downside_vol" -- both are LEVELS, never ranks
    learning_rate: float = 0.05,
    max_iter: int = 300,
    max_leaf_nodes: int = 15,
    min_samples_leaf: int = 200,
    l2: float = 1.0,
    train_start: date = date(1996, 1, 31),
    min_train_months: int = 35,
    horizon: int = 63,             # QUARTER
    seed: int = 0,
)
```

**Field names, settled.** Phase 5's draft assumed `FallParams` with a `top_n`. The real class is
**`FallSizeParams`** and the book-size field is **`slots`**, not `top_n`. Everything else phase 5
listed (`horizon`, `train_start`, `min_train_months`, `max_iter`, `max_leaf_nodes`,
`min_samples_leaf`, `l2`) carries the same name and the same meaning, and `as_dict()` returns
`dict[str, str]` as phase 5 requires. Phase 5's "name reconciliation" step is therefore already
answered by this section; it need only confirm against the landed code.

Six things phase 5 must know and this phase deliberately does not do:

1. **The label is a LEVEL, not a per-date rank (D13).** `fall_labels` returns `forward_fall` raw.
   Phase 5's `hypothesis` and `expected_failure` must describe the method as it is actually built:
   a model that predicts how far a name falls, in fractions, from a feature matrix that carries
   three un-normalised market-level columns beside the seven rank-normalised ones. **A
   pre-registration that still says "rank-normalised label" would be pre-registering a method that
   does not exist.**
2. **The head reads a market-level quantity.** The date's cross-sectional *mean* predicted fall is
   located in the model's own training distribution of date-level means, and the book holds
   `slots - floor(danger * slots)` whole slots. There is no exposure ladder for phase 5 to choose
   and no threshold for it to pre-register: the ladder is the model's own empirical CDF. Phase 5's
   draft asked "if phase 2's head takes an explicit exposure ladder, pre-register it here" — **it
   does not; delete that step.**
3. **Pre-register on `FALL_SIZE` only** (D8/D14). There is no fundamentals object at all.
4. **The first book year is 2000, not 1999** (M4). At `horizon=63` the first refit with 35 labelled
   month-ends is 1999-12-31. If phase 5 copies M0130's "hold SPY until there is a model" wrapper, the
   SPY stretch is 1996-1999 inclusive, one year longer than M0130's, and the wrapper's
   `model_ready(...)` must be called with `horizon=63`. That calendar rule lives in
   `m0130_tree_ranker.model_ready` and is **not** re-exported by this phase — phase 5 either imports
   it from M0130's file or restates it in its own.
5. **`size=False` is the ready-made control**, and it is a stronger one than a dollar-volume book:
   same model, same ordering, same slots, ladder ignored. `FALL_SIZE` with `size=True` minus
   `FALL_SIZE` with `size=False` is exactly what the sizing adds.
6. **The exposure question is already answered before phase 5 starts.** This phase's exit criterion
   **M5b** measures realised exposure on the real store across 2000-2015 and fails the phase if it
   is flat or does not fall in 2008. Phase 5 keeps its own pre-commit re-check and the two are
   deliberately redundant, because the method id is irreversible. Every (`slots`, `measure`, `size`)
   setting still counts as a tried setting; this phase ships no variant list.

**To no phase (found, deliberately not done):**

- The handover's "realised downside vol" is shipped as a *second* measure rather than a replacement.
  No claim is made here about which of the two labels is better; that is an empirical question a
  pre-registered variant answers.
- `TreeRankPrepared`'s class docstring at `:588-592` still lists only the ranker's four caches. It is
  accurate about those four and reflowing it would be a reformat of a frozen region; the three new
  caches document themselves on `forward_fall`, `fall_section` and `fall_model`. If a later phase is
  editing that docstring for another reason, the three lines can be added then.
- `lab/` has no `package_readme.md`. One was not minted here; that is `readme-updater`'s call at the
  end of the set, not this phase's scope.

---

## Commit sequence

This worktree and its git index are **shared by concurrent phase sessions**. Commit by explicit
pathspec, with `-m` **before** `--`, and `git add -- <newfile>` first for a file this phase creates.
**`git reset --hard`, `git clean`, `git checkout .` and every bare-path form are banned** —
including in any subagent you dispatch; say that verbatim in the subagent's prompt. Check
`git status --short` before each commit so nothing of a peer's is swept in, and verify with
`git show --stat HEAD` afterwards that the file list equals the allowlist.

**Commit 1 — the label** (steps 1, 3, 4, and the measure/label/cache tests of step 8):

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label
git status --short
git add -- engine/tests/test_tree_fall.py
git commit -m "lab: tree_rank learns the forward fall as a level, beside the forward return rank

The constraint that binds is the fall, not the pick: 65% of dev trials beat SPY total
return and only 23% keep the worst drawdown at or under 20%. So beside the forward
return rank the ranker now carries a forward downside LEVEL -- the worst peak-to-trough
fall over the next quarter, or the realised downside volatility over it -- on its own
cache, and deliberately NOT rank-normalised.

The label is a level because the question is how much to hold, not which names to hold.
Every feature column is already ranked within its date; a ranked label on top of that
would leave the predictions near-identical on every date, and in October 2008 the ranks
are still uniform, so the label could not say 'all of them' even in principle. To give
the model a level to read as well as one to predict, the fall section appends three
un-normalised market columns to the ranker's seven: the market's distance below its
one-year high, its 60-day realised volatility, and the spread of the day's momentum.
They are per-date scalars, so they cannot change which names are preferred -- only how
far the whole day's forecast moves. Reach is unchanged at 401 sessions.

Additions only. No existing name in the module moved, the diff removes zero lines, and
M0130's six recorded config digests still reproduce.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  -- engine/src/seer_engine/lab/tree_rank.py engine/tests/test_tree_fall.py
git show --stat HEAD
```

**Commit 2 — the head** (steps 2, 5, 6, 7, and the rest of step 8):

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label
git status --short
git commit -m "lab: a head that sizes the book by the fall it forecasts for the whole market

The fall model's output decides how much of the book is held, not which names rank
highest. How many slots are filled is a market-level question: the day's average
forecast fall is located in the model's own training distribution of day-level
forecasts, and the book keeps the share of its slots that the day is calmer than. A day
calmer than anything in training is a full book; a day worse than all of them is cash;
the median day is half. The calmest forecasts fill whichever slots are open, in order.
There is no threshold anyone chose -- the ladder is the model's own in-sample
distribution -- so nothing here was read off the development window.

Exposure moves in whole slots at a fixed weight and the book is never renormalised onto
the survivors: the measuring tape resizes a holding only once it is off by 20% of its
own target value, so at twenty slots a weight nudge under 1% of equity would never be
traded at all, while an entry or an exit is five times the band at every book size.

size=False is the control: same model, same ordering, ladder ignored, book always full.

New types beside the old ones -- TreeRankParams gains no field, because one more compare
field there moves five of M0130's six recorded config digests. One allocator object, not
two: a fundamentals twin could never be pre-registered (the filings panel starts in 2009)
and would claim an id for ever for nothing.

Measured on the real research store: exposure on the January decision dates 2000-2015
takes <N> distinct values and 2008 reads <X> against 2005's <Y>, with the always-full
control flat at 1.000.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  -- engine/src/seer_engine/lab/tree_rank.py engine/tests/test_tree_fall.py
git show --stat HEAD
```

Both commits must be green on their own: run the targeted suite before each. Do **not** stage or
commit `lab/lab.sqlite`, `web/data/lab.json`, `.workflows/todos.md` or any other phase's file.
If this phase mints a todo for itself, commit it separately by its own pathspec.

---

## Rollback

This phase is two commits bounded by an explicit two-file pathspec and touches no database, no
recorded row and no lab method, so it backs out cleanly and alone:

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label
git revert --no-edit <sha of commit 2> <sha of commit 1>
```

**Never `git reset --hard` here** — peers' work in progress lives in the same tree. After the
revert, `git diff <base> -- engine/src/seer_engine/lab/tree_rank.py` must be empty and
`engine/tests/test_tree_fall.py` must be gone. Because every change was additive, reverting restores
the module byte for byte and no recorded digest, trial or published number is affected either way.

If phase 5 has already pre-registered a method on `FALL_SIZE`, reverting this phase breaks that
method file's import and the lab becomes unopenable for `lab run`. Phase 5 is downstream of this one
in the dependency graph for exactly that reason: **once phase 5 has committed its method file, this
phase can no longer be reverted on its own** — the method id is spent and the two must be backed out
together, phase 5 first.
