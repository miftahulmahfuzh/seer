# Plan: seertrade.site/sera — the method lab, shown

**Slug:** sera-lab-site
**Date:** 2026-10-04 21:17 WIB
**Analysis:** `20261004-211729-H54F_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/sera-lab-site`
**Branch:** `feature/sera-lab-site` (base: `origin/main` @ `c138b08`)
**Phases:** 7
**Status:** complete (7/7)
**Coordinator:** —

---

## Why

> for now, let's optimize the UI for desktop only.
> we need to create another system like seertrade.site/sera . only accept mahfuzh74@gmail.com user to see this system.
> here , we can see every experiment that we have done. as detailed as possible.
> draw all the important graphs / diagram. explain everything concisely and in a non-technical manner, include your analysis on every method, your opinion.
> your insights is really important in every explorations. maybe you think we need another feature, or source of data beside all we have right now. just write it all there, as our food for thought
> make it as comprehensive as possible

Context: the experiment record is the committed `lab/lab.sqlite`, updated by `/explore-and-experiment-new-method` and `/sera-the-explorer` and pushed to `main`; every push to `main` deploys production on Vercel. The web must never need a human step to show new experiments. Iron rules: no human in the loop; Seer v2 design language; every button is icon-only (Lucide) with `aria-label` and a `data-tip` tooltip.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Optimize the UI for desktop only (for now) | 3, 4, 5, 6 |
| R2 | A separate system at seertrade.site/sera, visible only to mahfuzh74@gmail.com | 3 (gate, `requireSera`), applied on every page by 4, 5, 6 |
| R3 | Show every experiment, as detailed as possible, kept current with no human step | 1, 2, 5, 7 |
| R4 | Draw all the important graphs and diagrams | 3, 4, 5, 6 |
| R5 | Concise, non-technical explanations, with analysis and opinion on every method | 2, 4, 5, 6, 7 |
| R6 | Insights from every exploration; food for thought on features and data sources | 1, 6, 7 |
| R7 | As comprehensive as possible (cross-cutting) | 1, 2, 3, 4, 5, 6, 7 |

## Scope

**In scope:**
- the engine snapshot export (`lab export-json` → `web/data/lab.json`; `lab stage` keeps it in sync)
- the `synthesis` insight kind (schema v2)
- the `/sera` section of the Next.js app: gate, desktop shell, charts, Overview, Methods, method detail, Journal, Ideas, How it works
- a Sera link on Seer's desktop rail, and post-sign-in return to `/sera`
- CI path filter, skills, ROADMAP and README docs

**Out of scope:**
- Neon: the lab never goes to Neon. The snapshot rides in git with the deploy.
- A mobile-optimized layout: below 1024 px the pages stack in one column, readable but not designed.
- Any change to the lab's rules, trials, gate thresholds or the explore/sera workflow beyond the snapshot and synthesis kind.
- The test-window store and `lab test`: built on first promotion, per the design.

## Invariants

1. The tree builds and every test passes at the end of each phase: engine `ruff check` + `pytest`, web `npx tsc --noEmit` + `npx vitest run`.
2. `web/data/lab.json` is byte-identical to `lab export-json` of the committed `lab/lab.sqlite` (an engine test guards it). Every commit that changes `lab/lab.sqlite` also changes `web/data/lab.json`, through `lab stage`.
3. `/sera/**` renders only for a signed-in user whose email equals `SERA_EMAIL = 'mahfuzh74@gmail.com'` (case-insensitive, trimmed). Signed out → `/signin?next=/sera…`; any other account → `notFound()`.
4. Seer v2 tokens only (`var(--…)` from `globals.css`), Outfit font. Every control is an icon-only Lucide button or link with `aria-label` and `data-tip`. No text buttons.
5. The web never computes trading results. It only reshapes and draws the snapshot. Gate thresholds come from `snapshot.gate`, never from hard-coded numbers in web code.
6. Plain language on every page: each chart has a one-sentence plain caption saying what it shows and how to read it. Jargon (CAGR, drawdown, profit factor, DSR, MAR) is explained via the shared glossary (`web/lib/sera/glossary.ts`) with a `data-tip` on first use.
7. No new runtime dependency in `web/` (charts are hand-built SVG; markdown is a small in-repo renderer). No new engine dependency.

## Interface Contract — `web/data/lab.json` (phase 1 writes, phases 2–6 read)

Deterministic: same DB → same bytes. `json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)` + `"\n"`. Floats rounded to 6 dp. Non-finite floats become `null`; `profitFactor` infinite → `null` with `pfInfinite: true`. Keys camelCase, in the order listed below. No wall-clock timestamp anywhere: `asOf` is the latest timestamp found in the data, and `""` (never `null`) for an empty lab. Reconciled against phase 1's `snapshot()` code; phase 2's `types.ts` matches it exactly.

```ts
type LabSnapshot = {
  version: 1;
  asOf: string;                       // max of methods.updated, trials.run_at, insights.added, ideas_seen.added (ISO); "" for an empty lab
  gate: { maxDrawdown: number; minProfitFactor: number; minTrades: number; dsrMin: number;   // tuning.MAX_DRAWDOWN, tuning.MIN_PROFIT_FACTOR, dev._MIN_TRADES, store.DSR_MIN
          devStart: '1993-01-29'; devEnd: '2015-10-16'; testStart: '2015-10-19' };           // research.STORE_START, dev.DEV_END, dates.next_session(dev.DEV_END)
  data: { storeStart: '1993-01-29'; membershipStart: '1996-01-02'; fxStart: '1999-01-04';
          fingerprints: string[];     // distinct trials.store_fingerprint, sorted
          barRows: number; symbolsRequested: number; symbolsServed: number; dividendRows: number }; // P7a store facts (seed.py constants)
  summary: { devTrials: number; testLooks: number; methods: number; labMethods: number;
             historicalMethods: number; insights: number;
             byStatus: Record<string, number> };   // all nine statuses, in STATUSES order, zeros included
  benchmark: { spyTr: [string, number][]; spyPrice: [string, number][] };  // month-end 2-element arrays, 1993-01-29 = 1.0, through 2015-10-16 (274 points, from P7A_CURVES)
  methods: LabMethod[];               // ORDER BY id ('H-*' sorts before 'M*')
  trials: LabTrial[];                 // ORDER BY n
  insights: LabInsight[];             // ORDER BY id
  ideasSeen: LabSeen[];               // ORDER BY key
};
type LabMethod = { id: string; name: string; family: string; parentId: string | null;
  sourceKind: 'paper'|'blog'|'github'|'knowledge'|'variation'|'seed'; sourceRef: string;
  hypothesis: string;                 // text before "\n\nExpected failure: "
  expectedFailure: string | null;     // text after it, or null
  status: 'idea'|'registered'|'rejected'|'dev-eligible'|'promoted'|'test-passed'|'test-failed'|'paper'|'blocked-data';
  analysis: string;                   // markdown
  verdict: string; blockedOn: string; created: string; updated: string;
  historical: boolean };              // id starts with 'H-'
type LabTrial = { n: number; methodId: string; candidateId: string; rulesId: string; allocatorId: string;
  configText: string; window: 'dev'|'test'; start: string; end: string; gitSha: string; runAt: string;
  totalReturn: number|null; cagr: number|null; maxDrawdown: number|null; profitFactor: number|null; pfInfinite: boolean;
  trades: number; sharpe: number|null; exposure: number|null; turnover: number|null;
  worstYear: number|null; worstYearReturn: number|null; spyTrReturn: number|null; spyTrCagr: number|null;
  mar: number|null; failed: string[];  // split of trials.failed on "; ", empties dropped
  eligible: boolean; dsr: number|null; nTrialsAtRun: number;
  curve: [string, number][] };        // parsed curve_json (month-end equity / start)
type LabInsight = { id: number; kind: 'observation'|'hypothesis'|'data-wish'|'feature-wish'|'risk'|'synthesis';
  title: string; body: string; methodId: string | null; added: string };
type LabSeen = { key: string; methodId: string | null; note: string; added: string };
```

Failure labels inside `failed` are exactly: `beats SPY TR`, `max DD <= 15%`, `PF >= 1.3`, `>= 100 trades`, `owner inputs`, `DSR >= 0.95`.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | ✓ Lab snapshot export + synthesis kind | R3, R6, R7 | `engine/lab` | 6 | — | NORMAL | `.workflows/plan/sera-lab-site/phase-1.md` | P1-ENG-6QQA | — |
| 2 | ✓ Web data layer for the snapshot | R3, R5, R7 | `web/lib/sera` | 10 | 1 | NORMAL | `.workflows/plan/sera-lab-site/phase-2.md` | P1-WEB-5767 | — |
| 3 | ✓ Sera shell, access gate, chart kit | R1, R2, R4, R7 | `web/app/sera`, `web/components/sera` | 32 | — | HARD | `.workflows/plan/sera-lab-site/phase-3.md` | P1-WEB-EQ4I | — |
| 4 | ✓ Overview page | R1, R4, R5, R7 | `web/app/sera` (page.tsx) | 4 | 2, 3 | HARD | `.workflows/plan/sera-lab-site/phase-4.md` | P1-WEB-RL9Z | — |
| 5 | ✓ Methods list + method detail | R1, R3, R4, R5, R7 | `web/app/sera/methods` | 6 | 2, 3 | HARD | `.workflows/plan/sera-lab-site/phase-5.md` | P1-WEB-9ANC | — |
| 6 | ✓ Journal, Ideas, How it works | R1, R4, R5, R6, R7 | `web/app/sera/{journal,ideas,how}` | 17 | 2, 3 | HARD | `.workflows/plan/sera-lab-site/phase-6.md` | P1-WEB-08WD | — |
| 7 | ✓ Keep it current: CI, skills, docs | R3, R5, R6, R7 | `.github`, `.claude/skills`, `docs`, `web` | 5 | 1, 4, 5, 6 | EASY | `.workflows/plan/sera-lab-site/phase-7.md` | P1-ROOT-MO5N | — |

**Common setup.** Web phases: `cd /home/miftah/.worktrees/seer/sera-lab-site/web && npm ci` (the lockfile is identical to main's; never symlink main's `node_modules`, because `next build` rejects it). Engine commands in the worktree: `env -u SEER_LAB_DB PYTHONPATH=/home/miftah/.worktrees/seer/sera-lab-site/engine/src /home/miftah/seer/engine/.venv/bin/python -m …` (a worktree has no venv; `SEER_LAB_DB` must be unset).

**Reconciler verification.** Phases 2–6's code blocks, as they now stand in the plan files, were extracted into a scratch copy of `web/` at `c138b08` with a `web/data/lab.json` generated by phase 1's `snapshot()` from the committed `lab/lab.sqlite`: `tsc --noEmit` clean, `vitest run` 23 files / 244 tests green, and `next build` compiles `/sera`, `/sera/methods`, `/sera/methods/[id]`, `/sera/journal`, `/sera/ideas`, `/sera/how` (all ƒ).

### Phase 1 — Lab snapshot export + synthesis kind
**Satisfies:** R3, R6, R7
**Owns:**
- `engine/src/seer_engine/lab/store.py`: schema v2. A `synthesis` insight kind, added by a `connect()`-time migration that rebuilds `insights` with the new CHECK, copying rows and recreating triggers, then sets `schema_version='2'`. Plus `snapshot(conn) -> dict` and `snapshot_json(conn) -> str` per the Interface Contract.
- `engine/src/seer_engine/lab/seed.py`: exports the store-fact constants and the benchmark curve reader.
- `engine/src/seer_engine/commands/lab.py`: `lab export-json [--out web/data/lab.json]`; `lab stage` also writes the snapshot under the same exclusive lock and `git add`s both files.
- `engine/tests/test_lab_snapshot.py`: migration, determinism, contract shape, CLI, and the sync guard (committed JSON == export of committed DB, read-only).
- Generated `web/data/lab.json` and the migrated `lab/lab.sqlite`, staged together by `lab stage`.

**Does not touch:** `web/` code, the skills, CI.
**Exit criteria:** `python -m seer_engine lab export-json` reproduces the committed `web/data/lab.json` byte for byte. `lab insight --kind synthesis` works. All engine tests green.

### Phase 2 — Web data layer for the snapshot
**Satisfies:** R3, R5, R7
**Owns:** `web/lib/sera/` (new; every file imports relatively, because vitest has no `@/` alias):
- `types.ts`: the contract types.
- `lab.ts`: loads `../../data/lab.json`, cast once; `methodById`, `trialsOf`, `insightsOf`, `childrenOf`.
- `derive.ts`, pure:
  - gate checks per trial (six conditions with plain labels, value, target, `ok: boolean | null`, null = not measured); pass/fail from the engine's `failed`, no gate argument except for display targets
  - misses; closest-to-eligible
  - per-method best variant; funnel counts
  - progress over trial number (best conditions passed so far, best MAR so far)
  - family aggregates; parent/child method links
  - SPY total-return rebased to a trial's window; drawdown series from a curve; calendar-year returns from a curve
- `glossary.ts`: plain-language definitions and status/kind labels.
- `markdown.ts`: escape-first markdown → HTML for analysis text (headings, paragraphs, bold/italic/code, lists, pipe tables, http(s) links).
- `fixture.ts`: test-only builders. It reuses `web/lib/format.ts`; no `lib/sera/format.ts`.
- `*.test.ts` for each.

**Does not touch:** pages, components, engine.
**Exit criteria:** tsc + vitest green. Every derivation is unit-tested on a small fixture snapshot. `lab.ts` type-checks against the real `web/data/lab.json`.

### Phase 3 — Sera shell, access gate, chart kit
**Satisfies:** R1, R2, R4, R7
**Owns:**
- `web/lib/sera/access.ts` (+ test): `SERA_EMAIL`, `isSeraUser`. `web/lib/sera/gate.ts`: `requireSera(next)` (the gate every `/sera` layout and page calls).
- `web/lib/allow.ts` (+ test): `safeNext`. `web/components/tooltip.ts`: long tips wrap, `\n` breaks.
- `web/app/sera/layout.tsx` + `sera.module.css`: the gate (invariant 3), and the desktop shell (Sera rail with wordmark "Sera.", icon-only tabs Overview `/sera`, Methods `/sera/methods`, Journal `/sera/journal`, Ideas `/sera/ideas`, How it works `/sera/how`, and back to Seer `/`). Content column max-width ~1360 px; single-column fallback below 1024 px.
- `web/components/sera/`: `SeraNav.tsx`; `PageHeader.tsx` (eyebrow, string title, plain lede, as-of date, sign-out); `Section.tsx` (+ `SectionGrid`; sheet with eyebrow, title, plain caption); `Stat.tsx`; `Term.tsx` (`term` + `definition` strings, `data-tip`; never imports the glossary); `charts/`: `scale.ts` (+ test), `parts.tsx`, `LineChart.tsx`, `ScatterChart.tsx`, `BarChart.tsx`, `Legend.tsx` (+ render tests). Hand-built SVG with axes, ticks, gridlines, reference lines and shaded regions, `data-tip` on points, link-able points, Seer v2 colors as CSS strings. Its Interface Contract is the API Phases 4–6 code against.
- `web/components/Nav.tsx` + `web/app/(app)/layout.tsx`: a desktop-rail Sera link (shown when `isSeraUser`).
- `web/app/signin/page.tsx`: honour a safe internal `next` path on sign-in and on the already-signed-in redirect.
- `web/app/sera/not-found.tsx`.

**Does not touch:** `web/lib/sera/{types,lab,derive,glossary,markdown,fixture}.ts` (phase 2); any `/sera` page.tsx (phases 4–6); `web/components/sera/diagrams/` (phase 6).
**Exit criteria:** tsc + vitest green; `next build` compiles. The `/sera` layout gate behaves per invariant 3. Chart components render from plain props (no snapshot import).

### Phase 4 — Overview page
**Satisfies:** R1, R4, R5, R7
**Owns:** `web/app/sera/page.tsx` (calls `requireSera('/sera')`), `web/app/sera/overview.module.css`, and `web/app/sera/overview.ts` (+ test): pure shaping into Phase 3's exact chart props. Sections:
- **State of the search:** the latest `synthesis` insight (fallback: latest insight). KPI tiles: methods tried, trials (N), test looks used, closest result, best excess CAGR at DD ≤ gate.
- **Where every try landed:** scatter of max DD (x) vs CAGR minus SPY (y) for all dev trials, with the pass zone shaded; lab vs historical colours; point tooltips; points link to the method.
- **Which hurdles are hardest:** funnel bars, the count passing each condition.
- **Are we getting closer?:** progress lines over trial number.
- **The luck bar:** each trial's DSR vs N, with the 0.95 line.
- **Families explored:** bars of trials per family, plus best MAR.
- **Latest methods:** cards with verdicts.

**Does not touch:** shell, chart kit, lib (consumes them).
**Exit criteria:** tsc + vitest green. The page builds (`next build` compiles the route). No hard-coded gate number; `requireSera('/sera')` at the top.

### Phase 5 — Methods list + method detail
**Satisfies:** R1, R3, R4, R5, R7
**Owns:** `web/app/sera/methods/page.tsx` + `methods.module.css`; `web/app/sera/methods/[id]/page.tsx` + `method.module.css`; `view.ts` (+ test). Both pages call `requireSera(<own path>)`.
- **List:** every method with status, family, source, best variant (CAGR vs SPY, max DD, PF, trades, DSR, conditions passed n/6), verdict, and a filter by icon-only segmented control (`?show=all|lab|historical|alive`).
- **Detail:**
  - header: status, family, source link, parent and children
  - the idea (hypothesis); what could go wrong (expected failure); the verdict
  - variants table with ✓/✗ per condition
  - growth of 1 vs SPY total return (all variants + rebased SPY); drawdown (underwater); year-by-year bars (best variant vs SPY)
  - where its variants landed vs the gate
  - the analysis and opinion (markdown rendered)
  - related insights
  - full technical detail per trial (config, rules, git sha, window, N at run)
  - `generateStaticParams` over all methods; `notFound()` for unknown ids

**Does not touch:** shell, chart kit, lib.
**Exit criteria:** tsc + vitest green; `next build` compiles both routes. Every method id resolves; an unknown id renders the Sera not-found page.

### Phase 6 — Journal, Ideas, How it works
**Satisfies:** R1, R4, R5, R6, R7
**Owns:** `web/app/sera/journal/page.tsx`, `web/app/sera/ideas/page.tsx`, `web/app/sera/how/page.tsx` (+ one CSS module and one tested `view.ts` each; every page calls `requireSera(<own path>)`), and `web/components/sera/diagrams/` (`geometry.ts` + test, Pipeline, Windows).
- **Journal:** insights grouped by plain headings: Batch summaries (synthesis), What we learned (observation), Ideas worth testing (hypothesis), Data we wish we had (data-wish), Features to build (feature-wish), Risks we see (risk). Filter seg by kind, newest first, links to methods.
- **Ideas:** the backlog (`idea`), blocked-on-data (with what is needed, as a data wishlist), and the reading list from `ideasSeen` (`url:` keys as links, `concept:` keys as tags).
- **How it works:**
  - the pipeline diagram: idea → written down first → tested on 1993–2015 → five hurdles + luck check → one look at 2015–today → 3+ months paper with ≥ 100 trades → real money
  - the time-windows diagram
  - each hurdle explained plainly with its threshold from `snapshot.gate`
  - the honesty rules (append-only, counted tries, one look)
  - the data the lab has and lacks
  - the glossary

**Does not touch:** shell, chart kit, lib, other pages.
**Exit criteria:** tsc + vitest green. The three routes compile in `next build`.

### Phase 7 — Keep it current: CI, skills, docs
**Satisfies:** R3, R5, R6, R7
**Owns:**
- `.github/workflows/engine-ci.yml`: add `lab/**` to both path filters.
- `.claude/skills/explore-and-experiment-new-method/SKILL.md`: solo mode commits through `lab stage` (both files); the full `pytest` runs only after `lab stage`. The analysis is written for the owner in plain language, with an explicit `My opinion:`, because seertrade.site/sera shows it.
- `.claude/skills/sera-the-explorer/SKILL.md`: every `lab stage` commit includes `web/data/lab.json`; preflight tests run after staging; the batch synthesis uses `--kind synthesis`, and the site picks it up automatically.
- `docs/ROADMAP.md`: a P8 entry for the method lab and Sera.
- `web/package_readme.md`: a Sera section matching the reconciled tree (`requireSera`, `SERA_EMAIL`, `?next=`, `/sera/methods?show=`, `/sera/journal?kind=`, `/sera/ideas#…`, `lab export-json`, `lab stage`).

**Does not touch:** code.
**Exit criteria:** docs accurate to the merged code. CI green.

## Reconciliation Log

| # | Conflict | Phases | Resolution |
|---|---|---|---|
| 1 | Unmet assumption / contract drift: Phase 4 coded against assumed Phase 3 props (`Axis` objects, `Tone` tokens, `zones`, `lines`, `bars` + `max`, `Term k`, no point ids) | 3 → 4 | `overview.ts`, its test and `page.tsx` rewritten to Phase 3's exports: `ScatterPoint[]`/`ScatterRegion[]`/`RefLine[]`/`yDomain`, `LineSeries[]` tuples with `step`, `BarGroup[]` + `domain` + `valueText`, `Legend` `color`/`shape`, colour strings; local axis helpers removed in favour of `niceDomain` and `TickSpec`. |
| 2 | Unmet assumption: Phase 4 assumed gate-taking Phase 2 derivations (`conditionsPassed(t, gate)`, `closest(…, gate) → LabTrial`, `funnel.passed`, `progress(…, gate)`, `families.methods`, `statusLabel()`, `misses → string[]`) | 2 → 4 | Aligned to Phase 2's real signatures: no gate argument, `closest(dev, 1)[0]`, `passing`/`measured`, `methodIds.length`, `STATUS_LABEL[s].label`, `misses → ConditionKey[]` mapped through `CONDITION_LABEL`. |
| 3 | Unmet assumption / contract drift: Phase 5 assumed Phase 3 props (`XY` points, `dashed`, `fill: 'zero'`, `zone` with `y1: null`, `faded`, grouped `bars`, ReactNode `PageHeader.title`, `Term k`) | 3 → 5 | Call sites rewritten: ISO-dated tuple points (date mode), `dash`, `area`, `regions`, `ring`, `BarGroup.items`, `legendFromSeries`, string title. `view.ts` drops `XY`, `yearFrac`, `toXY`, `yearLabel`; `CurveLine` carries `Point[]` and `dash`; `SPY_DASH` added; tests updated. |
| 4 | Unmet assumption: Phase 6 assumed `Term({ k })` | 3 → 6 | `how/page.tsx` uses a local `T({ k })` wrapper feeding Phase 3's `Term` from `GLOSSARY`; journal and ideas used no `Term`. |
| 5 | Gap: no page called `requireSera`; Phase 4 named `currentUser()` as the gate | 3 → 4, 5, 6 | All six pages call `await requireSera('<own path>')` first (Phase 3 handoff 1); the layout keeps its own call. |
| 6 | Contract drift: pages set `'X · Sera'` titles under the layout template `'%s · Sera'` (double suffix) | 3 → 4, 5, 6 | Bare titles: `Overview`, `Methods`, `${id} · ${name}`, `Journal`, `Ideas`, `How it works`. |
| 7 | Contract check: Phase 2 types vs Phase 1's actual `snapshot()` (key names, nullability, `pfInfinite`, tuples, `byStatus` zeros, `asOf` `""`) | 1 → 2 | No drift: verified by generating `lab.json` with Phase 1's code and running Phase 2's `lab.test.ts` (6/6). Index contract and Phase 2's handoff now record the refinements. |
| 8 | Unmet assumption: Phase 6's windows diagram sliced `asOf` unconditionally; Phase 1 emits `""` for an empty lab | 1 → 6 | `windowsModel` falls back to `gate.testStart`; a test covers it. |
| 9 | Broken-build risk: Phases 2 and 3 offered a symlinked `node_modules`, which `next build` rejects | 2, 3, 4, 5, 6 | Every web phase's setup is `cd web && npm ci`; symlink text removed. |
| 10 | Contract drift: Phase 7 ran the engine with `engine/.venv` in the worktree (none exists) and without unsetting `SEER_LAB_DB` | 1 → 7 | Step 0 and Verification use `env -u SEER_LAB_DB PYTHONPATH=<wt>/engine/src /home/miftah/seer/engine/.venv/bin/python`. |
| 11 | Contract drift: Phase 7's README said `lab.ts` imports `@/data/lab.json`, omitted `gate.ts`, `fixture.ts`, `Stat`, `safeNext`, the per-page gate, the `#backlog/#blocked/#reading` anchors, and called the pages static | 2–6 → 7 | README text aligned to the reconciled tree, routes and commands. |
| 12 | Gap: Phase 1's handoff (run `pytest` only after `lab stage`, because the sync guard fails on an unstaged DB) was not in the skill text | 1 → 7 | Phase 7 adds it to the explore skill (after the "Run every command" paragraph) and to the sera preflight. |
| 13 | Relative-import check: vitest has no `@/` alias | 2, 4, 5, 6 | Verified: `lib/sera/*`, `overview.ts`, `methods/view.ts`, `{journal,ideas,how}/view.ts` and their tests import relatively; `page.tsx` files import through `@/`. No change needed. |
| 14 | File-ownership check across all 7 phases (`web/lib/sera/*`, `web/components/sera/*`, `web/lib/allow.ts`, `web/components/tooltip.ts`, `Nav.tsx`, `signin/page.tsx`, CSS modules) | all | No collision: Phase 2 owns `lib/sera/{types,lab,derive,glossary,markdown,fixture}` + tests; Phase 3 owns `lib/sera/{access,gate}`, `allow.ts`, `tooltip.ts`, `Nav.*`, `(app)/layout.tsx`, `signin/page.tsx`, `components/sera/**` except `diagrams/` (Phase 6); each page phase scopes its own prose CSS in its own module. |
| 15 | Unowned requirement: R7 was mapped to 1–7 in the index but appeared in no phase's Satisfies line | all | Added as a cross-cutting R7 to every phase's Satisfies line, matching the index. |
| 16 | Stale handoffs: Phase 2 asked Phase 3's `Term` to take `GlossaryKey`; Phase 3's handoffs 1–2 awaited adoption; Phase 7 asked about `engine/package_readme.md` and synthesis reclassification | 2, 3, 7 | Resolved in place: `Term` stays string-based; handoffs marked adopted; `engine/package_readme.md` does not document the lab CLI (no gap); Phase 1 keeps insight kinds unchanged (its migration test asserts it). |

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| How the web gets lab data: Neon sync, sqlite at runtime, or a JSON snapshot in git | JSON snapshot `web/data/lab.json`, generated by `lab stage`, bundled at build | 5: user context ("never need a human step"; every push deploys) + invariant 7 |
| Gate: env var or constant | Constant `SERA_EMAIL = 'mahfuzh74@gmail.com'` on top of the existing `ALLOWED_EMAIL` sign-in | 5: user raw input names the address exactly |
| Other signed-in account on /sera | `notFound()` (does not reveal the section) | 6: convention (private app, `robots: noindex`) |
| Synthesis insights: title prefix or a real kind | A real `synthesis` kind (schema v2 migration) | 4: Requirements R6; the journal and overview need to find it reliably |
| Charts: library or SVG | Hand-built SVG, as the Leaderboard already does | 6: convention + invariant 7 |
| Mobile | Single-column fallback, not designed | 5: R1 "desktop only (for now)" |
| `Term` API: `Term({ k: GlossaryKey })` (Phases 2, 4, 5, 6 drafts) or `Term({ term, definition })` (Phase 3) | `term` + `definition`; each page wraps it in a 3-line local `T({ k })` that reads `GLOSSARY[k]` | 2: Phase 3's exit criterion and Leaves-alone (components never import `lib/sera`), backed by 3: its verified code |
| Chart-kit props (axes, colours, zones, bars) | Phase 3's exported props everywhere; pages and view helpers produce them | 3: Phase 3's code blocks, compiled, tested and built |
| `misses()` returns `ConditionKey[]` (Phase 2, Phase 5) or plain strings (Phase 4 draft) | `ConditionKey[]`; display code maps through `CONDITION_LABEL` | 3: Phase 2's code block; 4: R5 (plain names in tips) |
| Where the gate runs: layout only, or layout and every page | Layout and every page (`requireSera('<own path>')`) | 1: invariant 3 ("`/sera/**` renders only for …"), with Phase 3's note that a layout is not re-run on client navigation |
| Luck-check bar on the Overview funnel: passing of all dev tries, or of the tries it was measured on | Of the measured tries (`passing of measured`), with the unmeasured count in the tip | 3: Phase 2's `GateCheck.ok = null` means "not measured", neither pass nor miss (its deviation 2) |
| Time axes on the method page: fractional years (Phase 5 draft) or ISO dates | ISO dates through `LineChart`'s date mode (year ticks) | 3: Phase 3's `LineChart` code |
| SPY line style: dashed (Phase 5 draft) or dotted | Dotted, `dash: '1 5'`, `var(--ink-3)` | 3: Phase 3's colour conventions; 6: the Leaderboard already draws SPY this way |
| Page titles under the `'%s · Sera'` template | Bare titles | 3: Phase 3's layout code |
| Paper bar (3 months, 100 trades) on How it works: add to `snapshot.gate` or keep as named web constants | Named constants `PAPER_MONTHS` / `PAPER_TRADES` in `how/view.ts`; the snapshot contract is unchanged | 1: invariant 5 covers the lab gate in `snapshot.gate`; this is design §1's real-money bar, and the index puts lab-rule changes out of scope |
| Windows diagram "today" for an empty lab (`asOf = ""`) | `gate.testStart` | 3: Phase 1's code emits `""`; fallback keeps the SVG finite |
| `node_modules` in the worktree: symlink main's or `npm ci` | `npm ci` in every web phase | 2: exit criteria require `next build`, which rejects a symlink (Phase 3, verified) |
| Engine command in the worktree | `env -u SEER_LAB_DB PYTHONPATH=<wt>/engine/src /home/miftah/seer/engine/.venv/bin/python` | 3: Phase 1's Step 8 code block |
| Ideas anchors: `Section id` or wrapping `<div id>` | Wrapping `<div id>` (Phase 6 as written) | 6: no behavioural difference; Phase 6 owns the markup |
| R7 ownership | Cross-cutting: every phase lists R7 | 4: the index Requirements table maps R7 to 1–7 |

## Open Questions

None.

## Rollback

Each phase is its own commit on `feature/sera-lab-site`; revert in reverse order. As a whole: revert the merge commit. `lab/lab.sqlite` schema v2 stays readable by v1 code except for `synthesis` rows (none exist until Sera writes one).

## Next

Run the whole set as a swarm:

    /analyze-orchestrator -f SERA_LAB_SITE_PLAN.md
