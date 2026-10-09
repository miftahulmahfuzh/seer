# Handover: the research-store clobber guard is checkout-local

**For:** `/analyze -f RESEARCH_STORE_CLOBBER_GUARD_HANDOVER.md`
**Written:** 2026-10-06, by `orch-build-promotion-path` after that set landed at `9ce5c4e`
**Status:** unplanned. This file is an input to `/analyze`, not a plan — it states the defect,
the evidence, and the constraints a fix must hold. It deliberately does **not** choose a design.

---

## The request

```
research_store's clobber guard compares the --store path against the running checkout's own
research.STORE_DIR, so it does not refuse a dev store belonging to a different checkout or
worktree. Close that gap without weakening the guard that already works.
```

## What is wrong

`engine/src/seer_engine/commands/research_store.py:219` refuses a `--test-window` build aimed at
the dev store:

```python
if test and _same_dir(store, research.STORE_DIR):
    ...  # refuse, exit 2
```

`_same_dir` (`:168`) resolves both paths and compares them. `research.STORE_DIR` (`research.py:68`)
is `config.REPO_ROOT / "engine" / ".research"`, and `REPO_ROOT` (`config.py:17`) is
`Path(__file__).resolve().parents[3]` — **derived from the location of the running module**.

So `STORE_DIR` names *this* checkout's dev store and nothing else. A session running in one
worktree that passes `--store` pointing at another checkout's `engine/.research` compares two
genuinely different paths, `_same_dir` returns `False`, and the guard does not fire.

The guard is doing name equality where the property it means to assert is *"this directory is a
dev store"*. Those coincide only when the operator uses default paths in a single checkout.

## Evidence

Demonstrated on `main` @ `a1d122b`, no build run:

```
this checkout STORE_DIR : /home/miftah/seer/engine/.research

--store /home/miftah/.worktrees/seer/some-other-set/engine/.research
  _same_dir(other, STORE_DIR) = False   <- guard does NOT fire
--store /home/miftah/seer/engine/.research
  _same_dir(same,  STORE_DIR) = True    <- guard DOES fire
```

Independently, the `build-promotion-path` phase-2 session triggered this for real while testing
`--test-window`, killed it within seconds, and confirmed the dev store was untouched. That
session's report is `.workflows/orchestration/build-promotion-path/logs/phase-2.log`.

## Why it matters

The dev store is the measurement baseline for every recorded trial:

| | |
|---|---|
| fingerprint | `399d0d254c7a90b8…` |
| bar rows | 2,490,793 |
| symbols served | 539 |
| window | `1993-01-29 .. 2015-10-16` |
| recorded **dev** trials measured against it | **85** |

The guard's own comment at `:216` states the stake: *"The dev store's fingerprint is the identity
the sync-research-store skill keys on and every recorded lab trial was measured against. Writing
the test window into it would be unrecoverable."* That reasoning is correct; the check under it is
just narrower than the reasoning.

## What already limits the blast radius

A fix should preserve these rather than duplicate them:

1. **`_swap_in` only runs on a successful build.** A killed or failed build leaves the target
   directory intact — confirmed empirically by the phase-2 session.
2. **`research.load_store` refuses a store whose declared window is not the one requested**, in
   both directions, before any data file is read. This is the *authoritative* protection and it is
   unaffected by this defect: a clobbered store would be rejected at load, not silently used.
3. The manifest's `window_name` / `window_start` / `window_end` keys (`OPTIONAL_MANIFEST_KEYS`)
   are what make (2) possible. A dev build writes none of them; absent means dev.

So this is **not** a silent-wrong-numbers bug. The realistic damage is destroying a 2.49M-row
store that costs ~30 minutes plus a yfinance crawl to rebuild, and breaking the
`sync-research-store` skill's content-addressed identity until it is rebuilt.

## Constraints a fix must hold

- **`MANIFEST_KEYS` stays at 9 keys and a dev build writes no window key.** The dev store must
  keep loading bit-identically at fingerprint `399d0d25…`. `test_research_store.py:236` and
  `:622` assert `set(manifest) == research.MANIFEST_KEYS`; both must pass unedited.
- **`DEV_END` keeps the value `2015-10-16`** in `backtest/dev.py:57` and `research.py:64`, and the
  equality `coverage.WINDOW_END == dev.DEV_END == research.DEV_END`
  (`engine/tests/test_fundamentals_coverage.py:107`) holds. That test must not be edited.
- **The existing same-checkout refusals keep working**, both directions (`:219` and `:227`), with
  their current exit code 2 and their current messages naming the right directory.
- **No recorded trial changes and no test-window look is spent.** `lab/lab.sqlite` currently reads
  85 dev trials and **0** test trials; both must be unchanged when the work lands.
- `engine/.research` and `engine/.research-test` are gitignored and must stay so.
- `pytest -q` green in `engine/` (baseline on `main`: **2469 passed, 360 skipped** without
  `PG_TEST_URL`; the skips are all PG-gated and pre-existing).

## Open questions for `/analyze` to decide

These are genuine forks, not rhetorical — each has at least two defensible answers and none is
irreversible:

1. **What identifies a dev store?** Reading the target's `manifest.json` and refusing on its
   declared window is content-based rather than name-based, and would catch any checkout — but it
   has to answer what to do about a directory with no manifest, a partial one, or a path that does
   not exist yet (the legitimate first build).
2. **Should `--store` outside the current checkout be refused outright**, or allowed once the
   content check passes? A blanket refusal is simpler and would have prevented the observed
   trigger, but may break a legitimate cross-checkout workflow — including the
   `sync-research-store` skill. Check whether anything actually relies on it before assuming.
3. **Does the same gap exist on the sibling paths** — `--verify`, `--coverage`,
   `--refresh-fundamentals`, and `lab test --store` — or only on build? They have different
   destructiveness and may warrant different answers.

## Reference list

| Path | Why |
|---|---|
| `engine/src/seer_engine/commands/research_store.py:168` | `_same_dir` |
| `engine/src/seer_engine/commands/research_store.py:211-231` | store resolution and both guards |
| `engine/src/seer_engine/research.py:65-70` | `STORE_START`, `STORE_DIR`, `TEST_STORE_DIR`, `TEST_WINDOW_START` |
| `engine/src/seer_engine/config.py:17` | `REPO_ROOT`, the root cause of the checkout-locality |
| `engine/src/seer_engine/research.py` | `load_store`, `declared_window`, `OPTIONAL_MANIFEST_KEYS` |
| `engine/tests/test_research_test_store.py` | the 28 tests phase 2 added; the dev/test refusals live here |
| `.claude/skills/sync-research-store/SKILL.md` | keys on the dev fingerprint |
| `docs/plans/2026-10-04-method-lab-design.md` §3 | the test window's specification |

## Provenance

Found by the `build-promotion-path` phase-2 session and reported to its coordinator as explicitly
out of scope for that set's exit criteria — correctly, since fixing it there would have been
scope creep into a phase that had already verified green. Recorded in commits `f35ca47` and
`a1d122b`. The set itself landed clean at `9ce5c4e`.
