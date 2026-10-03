# Seer Web v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship the Seer v2 design (`docs/design/Seer v2.dc.html`) as the real web app on
Vercel, reading Neon, behind Google-only single-email sign-in.

**Architecture:** Next.js App Router app in `web/`. Server components query Neon over HTTP
(`@neondatabase/serverless`, plain SQL, no ORM). v2 tokens become CSS custom properties
switched by `prefers-color-scheme`; CSS modules only (no Tailwind, no component kit).
Until the engine (roadmap P1–P4) exists, a seed script fills the tables with v2's
sample data, flagged `is_demo` so the UI shows a "Demo data" warning.

**Tech Stack:** Next.js 16, React 19, Auth.js v5 (next-auth beta), @neondatabase/serverless,
lucide-react, next/font (Outfit), vitest.

---

### Task 1: Scaffold `web/`
- Create: `web/package.json`, `web/tsconfig.json`, `web/next.config.ts`, `web/.env.local` → symlink to `../.env.local`
- Acceptance: `npm run build` passes on an empty home page.

### Task 2: Database schema + seed
- Create: `db/migrations/001_init.sql`, `web/scripts/migrate.mjs`, `web/scripts/seed-demo.mjs`
- Tables: `strategies` (incl. SPY benchmark row), `runs` (`is_demo`, `session_date`, `data_date`),
  `orders` (one row per pick through its lifecycle: `pending → open → closed | expired`,
  incl. explanation and exit fields), `bars`, `equity_snapshots`, `fx_rates`, `action_dismissals`.
- Seed dates are relative to "now" so the demo isn't stale.
- Acceptance: migrate + seed run twice without error (idempotent); counts match.

### Task 3: Pure logic with tests (TDD)
- Create: `web/lib/format.ts`, `web/lib/metrics.ts`, `web/lib/session.ts` + `*.test.ts`
- `usd`, `rp`, `pct` formatting; strategy metrics (return, win rate, profit factor,
  max drawdown, trades); go-live checklist; `nextUsSession(now)` and `isStale(run, now)`.
- Acceptance: `npm test` green.

### Task 4: Auth
- Create: `web/auth.ts`, `web/app/api/auth/[...nextauth]/route.ts`, `web/lib/allow.ts` (+ test)
- Google provider only; `signIn` callback rejects any email ≠ `ALLOWED_EMAIL`, redirecting to
  `/signin?denied=<email>`. JWT sessions. `(app)/layout.tsx` redirects signed-out users.
- Acceptance: allowlist unit test; local sign-in with the allowed Gmail works.

### Task 5: Design system
- Create: `web/app/globals.css` (tokens light/dark, safe areas), `web/components/*`
  (`IconButton`, `CopyButton`, `TooltipLayer` ported from `seer-ui.js`, `TabBar`, `SideRail`, `AppHeader`)
- Acceptance: every button icon-only with `aria-label` + `data-tip`; long-press tooltip on touch.

### Task 6: Screens
- Sign-in (+ unauthorized), Today (normal / no setups / stale / demo badge / day-5 actions with
  persisted dismiss), Positions, Leaderboard (equity chart + checklist), History (filters via
  search params). Mobile = stacked sheets; ≥1024px = v2 desktop layout.
- Acceptance: all states render against seeded DB in light and dark.

### Task 7: PWA
- Create: `web/app/manifest.ts`, `web/app/icon.svg`, `web/app/apple-icon.tsx`
- Acceptance: iOS "Add to Home Screen" opens standalone, content clears notch + home bar.

### Task 8: Deploy
- Vercel project `seer`: root dir `web`, env vars, deploy; add `seertrade.site` domain.
- Acceptance: production URL serves sign-in; DNS instructions handed to user.
