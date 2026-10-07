> Adopted from `SEAN_GOTRADE_TRACKER_PLAN.md` phase 2. Source: `.workflows/plan/sean-gotrade-tracker/phase-2.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 2: Sean section, rail button, Trades upload

**Plan set:** `SEAN_GOTRADE_TRACKER_PLAN.md`
**Analysis:** `20261007-222658-S3AN_code_analyzer.md`
**Satisfies:** R1 (a Sean button above Sera opens a new Sean section), R3 (the owner uploads Gotrade Order Summary screenshots, or the zip, and Sean reads them with glm-4.6v)
**Depends on:** Phase 1 (migration `015_sean.sql`, `web/lib/sean/{types,vision,readOrder,unzip,ledger}.ts`)
**Difficulty:** HARD
**Package:** `web/app/sean`, `web/components/sean`, `web/app/api/sean`, `web/lib/sean` (gate, data, dispatch only)

---

## Goal

After this phase the owner sees a Sean button (Lucide `Wallet`) directly above the Sera button on
the Seer desktop rail, and (on a phone, where the rail is hidden) beside Sign out in the page
header. It opens `/sean`, an owner-only section with its own rail (Overview, Trades,
Plan, Back to Seer). On `/sean/trades` the owner drops Order Summary screenshots or the whole zip;
the browser unzips, re-encodes only what needs it, hashes, and posts three at a time to
`POST /api/sean/orders`, which reads each receipt with Phase 1's `readOrder` and stores it in
`sean_orders`. Saved orders list below, newest first, each deletable. Overview and Plan are
placeholders that Phases 3 and 5 replace. The three `LLM_*` variables exist on the Vercel
project so the route works in production.

## Interface Contract

**Deletes:** CSS class `.sera` in `web/components/Nav.module.css:69-70` (replaced by `.foot`, which now carries `margin-top: auto`, and `.sean`, the Sean link's own class)
**Renames:** none
**Creates:**
- `Nav` prop `showSean?: boolean` (`web/components/Nav.tsx`); the rail's Sean link carries class `s.sean` (`position: relative`, the anchor for Phase 5's coral dot)
- A mobile-only Sean icon button in `web/components/AppHeader.tsx` (owner only, next to Sign out), class `s.sean` in `AppHeader.module.css`; `AppHeader` becomes an `async` server component (its 4 call sites are unchanged)
- `requireSean(next?: string): Promise<User>` and `isSeanCaller(): Promise<boolean>` (`web/lib/sean/gate.ts`)
- `web/lib/sean/data.ts` (server only, owned by this phase alone — Phases 3 and 5 import from it and never edit it): `type OrderRow`, `orders(): Promise<OrderRow[] | null>`, `type LedgerRow` (`LedgerOrder & { amountUsd: number }`), `ledgerOrders(): Promise<LedgerRow[]>` (every order oldest first, `executedAt` ISO with `+07:00`, the shape Phase 1's ledger takes), `ownerSymbols(): Promise<string[]>`, `orderById(id): Promise<OrderRow | null>`, `orderIdBySha(sha): Promise<number | null>`, `saveOrder(order, sha, raw): Promise<{ id: number; duplicate: boolean }>`, `removeOrder(id): Promise<boolean>`
- `dispatchSeanMarks(): Promise<boolean>` (`web/lib/sean/dispatch.ts`): `workflow_dispatch` of `.github/workflows/sean.yml` on `main`, no inputs, never throws
- `SeanNav({ planOpen?: number })` (`web/components/sean/SeanNav.tsx` + `.module.css`)
- `web/app/sean/{layout.tsx, not-found.tsx, sean.module.css, page.tsx (placeholder), plan/page.tsx (placeholder)}`
- `web/app/sean/trades/{page.tsx, Uploader.tsx, DeleteOrder.tsx, actions.ts, view.ts, view.test.ts, upload.ts, upload.test.ts, trades.module.css}`
- Server actions `deleteOrder(prev: FormState, formData: FormData): Promise<FormState>` and `refreshPnl(): Promise<boolean>` (`web/app/sean/trades/actions.ts`)
- Route `POST /api/sean/orders` (`web/app/api/sean/orders/route.ts`), shared contract C, `export const maxDuration = 60`
- Vercel project env vars `LLM_API_KEY` (sensitive), `LLM_VISION_BASE_URL`, `LLM_VISION_MODEL` on production and preview (added only if missing)

**Signature changes:** `Nav({ showSera })` -> `Nav({ showSera, showSean })` (both optional, default `false`; existing callers keep compiling). `AppHeader(props)` -> `async AppHeader(props)` (same props; React 19 server components may be async, and every caller is a server page).

**Requires (from earlier phases):** Phase 1 exports, exactly as listed under **Phase 1 exports this phase binds to** below; table `sean_orders` from `db/migrations/015_sean.sql` (shared contract A).

**Leaves alone (owned by others):**
- `web/lib/sean/{types,money,prompt,extractJson,vision,order,readOrder,ledger,unzip}.ts` and fixtures (Phase 1) — consumed, never edited
- `web/app/sean/page.tsx` body after this phase, `web/app/sean/overview*`, `web/lib/sean/overviewData.ts` (Phase 3)
- `.github/workflows/sean.yml` and the engine `sean` command (Phase 4) — Phase 2 only dispatches it
- `web/app/sean/plan/*` after this phase, `web/lib/sean/{reminders,planData}.ts`, the `planOpen` value fed from `app/sean/layout.tsx`, the coral dot on the Sean buttons in `Nav.tsx` and `AppHeader.tsx` (Phase 5)
- engine, `sim/`, `lab/` (Phases 4, 6, 7)

### Phase 1 exports this phase binds to (reconciled against Phase 1's executed plan)

Phase 1's code was written and tested before reconciliation; these are its real signatures and
this plan's code calls exactly these.

```ts
// web/lib/sean/types.ts
export type OrderSide = 'buy' | 'sell';
export type SeanFill = { shares: number; price: number };
export type SeanOrder = {
  side: OrderSide; orderType: string; status: string; symbol: string;
  executedAt: string;         // ISO 8601 with the +07:00 offset, e.g. '2026-10-07T21:55:00+07:00'
  price: number; shares: number; amountUsd: number;
  tradingFeeUsd: number; regulatoryFeeUsd: number; ppnUsd: number;   // magnitudes, >= 0
  totalUsd: number; netProfitUsd: number | null; fills: SeanFill[];
};

// web/lib/sean/vision.ts
export type VisionConfig = { baseUrl: string; apiKey: string; model: string };
/** null when an LLM_* var is missing or is the /api/anthropic URL. Never throws. */
export function visionConfigFromEnv(env?: Record<string, string | undefined>): VisionConfig | null;

// web/lib/sean/readOrder.ts
export const READ_BUDGET_MS = 55_000;   // vision + the one repair, inside maxDuration = 60
export function visionDeps(cfg: VisionConfig, fetchImpl?: typeof fetch): ReadOrderDeps;
export type ReadOrderCode = 'token_floor' | 'timeout' | 'transport' | 'not_order' | 'not_filled' | 'unreadable';
/** token_floor | timeout | transport: the reader failed (HTTP 502); the rest: the picture (HTTP 422). */
export function isReaderDown(code: ReadOrderCode): boolean;
export type ReadOrderOutcome =
  | { ok: true; order: SeanOrder; raw: unknown; attempts: 1 | 2; promptTokens: number; floor: number }
  | { ok: false; code: ReadOrderCode; message: string; issues: string[]; raw: unknown | null;
      attempts: 1 | 2; promptTokens: number | null; floor: number | null; detail: string | null };
/** Never throws for a model problem; rethrows only an error that is not the vision client's.
 *  The repair call re-sends the image. toOrder already refuses every status but 'Filled'. */
export function readOrder(deps: ReadOrderDeps, imageB64: string, budgetMs?: number): Promise<ReadOrderOutcome>;

// web/lib/sean/ledger.ts (for ledgerOrders() in data.ts)
export type LedgerOrder = { id: number; side: OrderSide; symbol: string; executedAt: string; price: number;
  shares: number; totalUsd: number; tradingFeeUsd: number; regulatoryFeeUsd: number; ppnUsd: number };

// web/lib/sean/unzip.ts (browser: DecompressionStream('deflate-raw'))
export class ZipError extends Error {}                         // message is plain words
export type ZipEntry = { name: string; bytes: Uint8Array };    // name keeps its folder path
export function readZip(input: ArrayBuffer | Uint8Array,
  opts?: { inflateRaw?: InflateRaw; accept?: (name: string) => boolean }): Promise<ZipEntry[]>;
```

Phase 1 handoff honoured here: if the uploader downscales a picture, the short edge stays at or
above 560 px (`MIN_SHORT_PX`, Step 10) — run-insights' measured 108/108 setting, below which
prompt_tokens fall toward the token floor.

## Files

| File | Action | What changes |
|---|---|---|
| `web/components/Nav.tsx` | modify | `showSean` prop; Sean `Wallet` link above Sera inside a new `.foot` wrapper (lines 3, 15-28) |
| `web/components/Nav.module.css` | modify | `.sera` (lines 69-70) -> `.foot` + `.sean` |
| `web/app/(app)/layout.tsx` | modify | pass `showSean` (line 12) |
| `web/components/AppHeader.tsx` | modify | `async`; owner-only, mobile-only Sean icon button beside Sign out |
| `web/components/AppHeader.module.css` | modify (append) | `.sean` |
| `web/lib/sean/gate.ts` | create | `requireSean`, `isSeanCaller` (Sera's predicates) |
| `web/lib/sean/data.ts` | create | server-only reads/writes on `sean_orders`, incl. `ledgerOrders()` for Phases 3 and 5 |
| `web/lib/sean/dispatch.ts` | create | best-effort `sean.yml` dispatch |
| `web/components/sean/SeanNav.tsx` | create | Sean's rail: wordmark, 3 tabs, Back to Seer, `planOpen` badge |
| `web/components/sean/SeanNav.module.css` | create | rail styles (SeraNav's, renamed comments) |
| `web/app/sean/layout.tsx` | create | gate + shell + `SeanNav planOpen={0}` |
| `web/app/sean/sean.module.css` | create | shell styles |
| `web/app/sean/not-found.tsx` | create | not-found inside the Sean shell |
| `web/app/sean/page.tsx` | create | Overview placeholder (Phase 3 replaces) |
| `web/app/sean/plan/page.tsx` | create | Plan placeholder (Phase 5 replaces) |
| `web/app/api/sean/orders/route.ts` | create | shared contract C |
| `web/app/sean/trades/page.tsx` | create | uploader section + order list |
| `web/app/sean/trades/Uploader.tsx` | create | client uploader |
| `web/app/sean/trades/DeleteOrder.tsx` | create | client two-step delete button |
| `web/app/sean/trades/actions.ts` | create | `deleteOrder`, `refreshPnl` |
| `web/app/sean/trades/view.ts` | create | pure words/numbers |
| `web/app/sean/trades/view.test.ts` | create | tests for view.ts |
| `web/app/sean/trades/upload.ts` | create | pure upload rules shared by uploader and route |
| `web/app/sean/trades/upload.test.ts` | create | tests for upload.ts |
| `web/app/sean/trades/trades.module.css` | create | Trades styles |
| Vercel project env | config | add `LLM_API_KEY`, `LLM_VISION_BASE_URL`, `LLM_VISION_MODEL` if missing |

## Implementation Steps

### Step 0: Prepare the worktree
**File:** none (worktree setup)
**Change:** the worktree has no `web/node_modules` and no `web/.env.local`. `next build` imports
`lib/db.ts`, which calls `neon(process.env.DATABASE_URL!)` at import time, so the env file is
needed. Both are gitignored (`.gitignore`: `.env*`, `node_modules/`).
```bash
cd /home/miftah/.worktrees/seer/sean-gotrade-tracker/web
cp /home/miftah/seer/web/.env.local .env.local
npm ci
```
**Impact:** none on the tree.

### Step 1: Sean button above Sera on the Seer rail
**File:** `web/components/Nav.tsx:1-34` (import line 3, doc comment line 15, signature line 16, Sera block lines 23-27)
**Change:** add `Wallet`; add `showSean`; put both buttons in one `.foot` wrapper so the pair sits
at the rail foot with Sean on top. `Tabs` (lines 36-50) is unchanged and repeated here only so
the file is complete.
**Code:**
```tsx
'use client';

import { Briefcase, History, LayoutGrid, Telescope, Trophy, Wallet } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import s from './Nav.module.css';

const TABS = [
  { href: '/', icon: LayoutGrid, tip: 'Today' },
  { href: '/positions', icon: Briefcase, tip: 'Positions' },
  { href: '/leaderboard', icon: Trophy, tip: 'Leaderboard' },
  { href: '/history', icon: History, tip: 'History' },
];

/**
 * Floating pill tab bar on mobile, vertical rail on desktop. Icon-only.
 * `showSean` and `showSera` add the ways into Sean (the owner's real trades) and Sera (the method
 * lab) to the foot of the desktop rail, Sean above Sera.
 */
export function Nav({ showSera = false, showSean = false }: { showSera?: boolean; showSean?: boolean }) {
  const path = usePathname();
  return (
    <>
      <aside className={`${s.rail} desk-only`}>
        <span className={s.wordmark}>Seer.</span>
        <Tabs path={path} vertical />
        {(showSean || showSera) && (
          <div className={s.foot}>
            {showSean && (
              <Link href="/sean" className={`icon-btn ${s.sean}`} data-tip="Sean, your real trades" aria-label="Sean, your real trades">
                <Wallet size={21} strokeWidth={1.5} />
              </Link>
            )}
            {showSera && (
              <Link href="/sera" className="icon-btn" data-tip="Sera, the method lab" aria-label="Sera, the method lab">
                <Telescope size={21} strokeWidth={1.5} />
              </Link>
            )}
          </div>
        )}
      </aside>
      <nav className={`${s.bar} mobile-only`} aria-label="Sections" data-tip-anchor>
        <Tabs path={path} />
      </nav>
    </>
  );
}

function Tabs({ path, vertical }: { path: string; vertical?: boolean }) {
  return (
    <div className={vertical ? s.vtabs : s.tabs}>
      {TABS.map(({ href, icon: Icon, tip }) => {
        const active = href === '/' ? path === '/' : path.startsWith(href);
        return (
          <Link key={href} href={href} className={active ? s.active : s.tab}
            data-tip={tip} aria-label={tip} aria-current={active ? 'page' : undefined}>
            <Icon size={22} strokeWidth={active ? 1.75 : 1.5} />
          </Link>
        );
      })}
    </div>
  );
}
```
**Impact:** `.sera` class no longer referenced; Sera's position is unchanged when Sean is hidden (the wrapper carries the same `margin-top: auto`). The Sean link's own class `s.sean` is where Phase 5 anchors its coral dot.

### Step 2: Rail foot style
**File:** `web/components/Nav.module.css:69-70`
**Change:** replace the two `.sera` lines with:
**Code:**
```css
/* Desktop rail only: the ways into Sean (real trades) and Sera (the lab), at the foot of the
   rail, for the owner account. Sean sits directly above Sera. */
.foot {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

/* The Sean button: positioned so Phase 5 can pin its "you need to act" dot to it. */
.sean { position: relative; }
```
**Impact:** none elsewhere (`.sera` was only used in `Nav.tsx:24`).

### Step 3: Show the button to the owner
**File:** `web/app/(app)/layout.tsx:7-16` (line 12)
**Change:** compute the owner check once, pass it to both props. `currentUser()` already enforces `ALLOWED_EMAIL`, so this is exactly the Sera gate.
**Code:**
```tsx
import { redirect } from 'next/navigation';
import { currentUser } from '@/auth';
import { Nav } from '@/components/Nav';
import { isSeraUser } from '@/lib/sera/access';
import s from './shell.module.css';

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const user = await currentUser();
  if (!user) redirect('/signin');
  // Sean (the owner's real Gotrade trades) and Sera (the lab) share one gate: the owner account.
  const owner = isSeraUser(user.email);
  return (
    <div className={s.shell}>
      <Nav showSera={owner} showSean={owner} />
      <main className={s.main}>{children}</main>
    </div>
  );
}
```

### Step 3b: A way into Sean on the phone
**File:** `web/components/AppHeader.tsx:1-39` (whole file shown) and `web/components/AppHeader.module.css` (append)
**Why here:** the owner's screenshots live on his phone, and below 1024 px the Seer rail is
hidden while the floating tab bar is a fixed 4-column, 276 px pill (`Nav.module.css` `.bar`/`.tabs`)
that holds neither Sera nor Sean. Adding a fifth tab would resize that pill for every user and put
an owner-only control into a shared component; `AppHeader` already carries the page's own icon
controls (Sign out) on every `(app)` page, so the least invasive spot is one more `.icon-btn` there,
shown only below 1024 px (`mobile-only`) and only to the owner. On desktop the rail button from
Step 1 stays the one way in, so the two never show together. `AppHeader` becomes `async` to read the
signed-in user itself (`currentUser()`, the same call `(app)/layout.tsx` makes), so none of its
four call sites (`app/(app)/{page,positions/page,leaderboard/page,history/page}.tsx`) changes.
**Code (`AppHeader.tsx`, whole file):**
```tsx
import { LogOut, Wallet } from 'lucide-react';
import Link from 'next/link';
import { currentUser, signOut } from '@/auth';
import { isSeraUser } from '@/lib/sera/access';
import s from './AppHeader.module.css';

type Props = {
  date: string;
  title: string;
  deskTitle?: string;
  deskAside?: React.ReactNode;
  demo?: boolean;
};

const SEAN_TIP = 'Sean, your real trades';

/**
 * The page header of every Seer (app) page. On a phone it also carries the owner's way into Sean
 * (his real Gotrade trades, whose screenshots live on that phone): the mobile tab bar has no room
 * for it, and on desktop the rail's own Sean button does the job.
 */
export async function AppHeader({ date, title, deskTitle, deskAside, demo }: Props) {
  // Sean's gate (plan invariant 3): the same owner check as the rail button in (app)/layout.tsx.
  const owner = isSeraUser((await currentUser())?.email);
  return (
    <header className={s.header}>
      <span className={`${s.eye} mobile-only`} aria-hidden="true" />
      <div className={s.titles}>
        <span className={s.date}>
          {date}
          {demo && <span className={s.demo} data-tip="Sample data until the engine runs. Do not trade it.">Demo data</span>}
        </span>
        <h1 className={s.title}>
          <span className="mobile-only">{title}</span>
          <span className="desk-only">{deskTitle ?? title}</span>
        </h1>
      </div>
      <div className={s.aside}>
        {deskAside && <span className="desk-only">{deskAside}</span>}
        {owner && (
          <Link href="/sean" className={`icon-btn mobile-only ${s.sean}`} data-tip={SEAN_TIP} aria-label={SEAN_TIP}>
            <Wallet size={21} strokeWidth={1.5} />
          </Link>
        )}
        <form action={async () => { 'use server'; await signOut({ redirectTo: '/signin' }); }}>
          <button type="submit" className="icon-btn" data-tip="Sign out" aria-label="Sign out">
            <LogOut size={21} strokeWidth={1.5} />
          </button>
        </form>
      </div>
    </header>
  );
}
```
**Code (`AppHeader.module.css`, append at the end of the file):**
```css
/* Mobile only, owner only: the way into Sean (the rail has it on desktop). Positioned so Phase 5
   can pin its "you need to act" dot to it. */
.sean { position: relative; }
```
**Impact:** owner's phone shows Wallet then Sign out at the header's right on Today, Positions,
Leaderboard and History; desktop is unchanged (`.mobile-only` hides it at >= 1024 px); other
accounts see nothing new. One extra `auth()` read per page render (a JWT cookie decode, no DB).

### Step 4: The gate
**File:** `web/lib/sean/gate.ts` (new)
**Code:**
```ts
import { notFound, redirect } from 'next/navigation';
import { auth } from '@/auth';
import { isAllowed } from '@/lib/allow';
import { isSeraUser } from '@/lib/sera/access';

/**
 * The /sean gate (plan invariant 3): Sera's exact rule, because Sean shows the owner's real money.
 * Signed out: sign-in, which returns to `next` afterwards. Signed in as anyone but the owner (or
 * outside ALLOWED_EMAIL): 404, so the section is not revealed. Returns the signed-in owner.
 * Every /sean page calls this itself: layouts do not re-run on client navigation.
 */
export async function requireSean(next = '/sean') {
  const session = await auth();
  const user = session?.user;
  if (!user) redirect(`/signin?next=${encodeURIComponent(next)}`);
  if (!isAllowed(user.email, process.env.ALLOWED_EMAIL) || !isSeraUser(user.email)) notFound();
  return user;
}

/**
 * The same gate as a yes/no, for /api/sean/* routes and server actions, where redirect() and
 * notFound() are the wrong answer (a 307 to /signin would tell a stranger the section exists).
 */
export async function isSeanCaller(): Promise<boolean> {
  const session = await auth();
  const email = session?.user?.email;
  return isAllowed(email, process.env.ALLOWED_EMAIL) && isSeraUser(email);
}
```

### Step 5: Server-side data for `sean_orders`
**File:** `web/lib/sean/data.ts` (new; owned by this phase alone. Phases 3 and 5 import from it and put their own reads in `overviewData.ts` / `planData.ts`, so the two parallel phases never edit one file)
**Code:**
```ts
/**
 * Sean's reads and writes on sean_orders. Server only: it opens the connection from lib/db, so
 * client components and tests never import it (they may `import type` from it; types are erased).
 * The Overview's reads live in overviewData.ts and the Plan's in planData.ts; both read the
 * owner's orders through ledgerOrders() here.
 */
import { sql } from '@/lib/db';
import type { LedgerOrder } from './ledger';
import type { SeanOrder } from './types';

type Row = Record<string, any>;

/** One stored order, as the Trades page and the upload route show it. Money in dollars. */
export type OrderRow = {
  id: number;
  side: 'buy' | 'sell';
  orderType: string;
  symbol: string;
  /** Jakarta wall-clock time of the fill, 'YYYY-MM-DDTHH:MM' (the receipt's own WIB time). */
  executedWib: string;
  price: number;
  shares: number;
  amountUsd: number;
  tradingFeeUsd: number;
  regulatoryFeeUsd: number;
  ppnUsd: number;
  /** trading + regulatory + PPN, to the cent. */
  feesUsd: number;
  totalUsd: number;
  /** Gotrade's own 'Net Profit' on a sell; null on buys. */
  netProfitUsd: number | null;
};

const cents = (v: number) => Math.round(v * 100) / 100;
const nn = (v: unknown) => (v === null || v === undefined ? null : Number(v));

function toRow(r: Row): OrderRow {
  const trading = Number(r.trading_fee_usd);
  const regulatory = Number(r.regulatory_fee_usd);
  const ppn = Number(r.ppn_usd);
  return {
    id: Number(r.id),
    side: r.side === 'sell' ? 'sell' : 'buy',
    orderType: String(r.order_type),
    symbol: String(r.symbol),
    executedWib: String(r.executed_wib),
    price: Number(r.price),
    shares: Number(r.shares),
    amountUsd: Number(r.amount_usd),
    tradingFeeUsd: trading,
    regulatoryFeeUsd: regulatory,
    ppnUsd: ppn,
    feesUsd: cents(trading + regulatory + ppn),
    totalUsd: Number(r.total_usd),
    netProfitUsd: nn(r.net_profit_usd),
  };
}

/** Every stored order, newest first. Null when Neon cannot be read, so the page can say so. */
export async function orders(): Promise<OrderRow[] | null> {
  try {
    const rows = await sql`
      SELECT id, side, order_type, symbol,
             to_char(executed_at AT TIME ZONE 'Asia/Jakarta', 'YYYY-MM-DD"T"HH24:MI') AS executed_wib,
             price, shares, amount_usd, trading_fee_usd, regulatory_fee_usd, ppn_usd, total_usd, net_profit_usd
        FROM sean_orders
       ORDER BY executed_at DESC, id DESC`;
    return rows.map(toRow);
  } catch (e) {
    console.error('sean_orders read failed', e);
    return null;
  }
}

/** An order as the shared ledger (lib/sean/ledger.ts) reads it, plus its trade amount. */
export type LedgerRow = LedgerOrder & { amountUsd: number };

/**
 * Every stored order, oldest first (executed_at, then id: the ledger's own order), shaped for
 * buildLedger / pnlSeries / pnlAt. executedAt is ISO 8601 with the receipt's +07:00 offset, so
 * orderSession() reads the New York trade date from it. Throws when the read fails.
 */
export async function ledgerOrders(): Promise<LedgerRow[]> {
  const rows = await sql`
    SELECT id, side, symbol,
           to_char(executed_at AT TIME ZONE 'Asia/Jakarta', 'YYYY-MM-DD"T"HH24:MI:SS') || '+07:00' AS executed_iso,
           price, shares, amount_usd, total_usd, trading_fee_usd, regulatory_fee_usd, ppn_usd
      FROM sean_orders
     ORDER BY sean_orders.executed_at, id`;
  return rows.map((r): LedgerRow => ({
    id: Number(r.id),
    side: r.side === 'sell' ? 'sell' : 'buy',
    symbol: String(r.symbol),
    executedAt: String(r.executed_iso),
    price: Number(r.price),
    shares: Number(r.shares),
    amountUsd: Number(r.amount_usd),
    totalUsd: Number(r.total_usd),
    tradingFeeUsd: Number(r.trading_fee_usd),
    regulatoryFeeUsd: Number(r.regulatory_fee_usd),
    ppnUsd: Number(r.ppn_usd),
  }));
}

/** Every ticker the owner has ever bought or sold, A to Z. Throws when the read fails. */
export async function ownerSymbols(): Promise<string[]> {
  const rows = await sql`SELECT DISTINCT symbol FROM sean_orders ORDER BY symbol`;
  return rows.map(r => String(r.symbol));
}

/** One order by id, or null. Throws when the read fails. */
export async function orderById(id: number): Promise<OrderRow | null> {
  const rows = await sql`
    SELECT id, side, order_type, symbol,
           to_char(executed_at AT TIME ZONE 'Asia/Jakarta', 'YYYY-MM-DD"T"HH24:MI') AS executed_wib,
           price, shares, amount_usd, trading_fee_usd, regulatory_fee_usd, ppn_usd, total_usd, net_profit_usd
      FROM sean_orders
     WHERE id = ${id}`;
  return rows.length > 0 ? toRow(rows[0]) : null;
}

/** The order already read from this exact picture (hex SHA-256), or null. Throws when the read fails. */
export async function orderIdBySha(sha: string): Promise<number | null> {
  const rows = await sql`SELECT id FROM sean_orders WHERE image_sha256 = ${sha} LIMIT 1`;
  return rows.length > 0 ? Number(rows[0].id) : null;
}

/**
 * Stores one read order. Both unique keys dedupe: the same picture (image_sha256) and the same
 * order seen in a different screenshot (symbol, side, executed_at, shares). On either conflict
 * nothing is written and the existing row's id comes back with duplicate = true.
 * Throws when the write fails.
 */
export async function saveOrder(order: SeanOrder, sha: string, raw: unknown): Promise<{ id: number; duplicate: boolean }> {
  const inserted = await sql`
    INSERT INTO sean_orders (
      image_sha256, side, order_type, status, symbol, executed_at, price, shares, amount_usd,
      trading_fee_usd, regulatory_fee_usd, ppn_usd, total_usd, net_profit_usd, fills, raw)
    VALUES (
      ${sha}, ${order.side}, ${order.orderType}, ${order.status}, ${order.symbol},
      ${order.executedAt}::timestamptz, ${order.price}, ${order.shares}, ${order.amountUsd},
      ${order.tradingFeeUsd}, ${order.regulatoryFeeUsd}, ${order.ppnUsd}, ${order.totalUsd},
      ${order.netProfitUsd}, ${JSON.stringify(order.fills)}::jsonb, ${JSON.stringify(raw ?? null)}::jsonb)
    ON CONFLICT DO NOTHING
    RETURNING id`;
  if (inserted.length > 0) return { id: Number(inserted[0].id), duplicate: false };

  const existing = await sql`
    SELECT id FROM sean_orders
     WHERE image_sha256 = ${sha}
        OR (symbol = ${order.symbol} AND side = ${order.side}
            AND executed_at = ${order.executedAt}::timestamptz AND shares = ${order.shares}::numeric)
     ORDER BY id
     LIMIT 1`;
  if (existing.length === 0) throw new Error('sean_orders insert was skipped but no matching row exists');
  return { id: Number(existing[0].id), duplicate: true };
}

/** Deletes one order. False when it was already gone. Throws when the write fails. */
export async function removeOrder(id: number): Promise<boolean> {
  const rows = await sql`DELETE FROM sean_orders WHERE id = ${id} RETURNING id`;
  return rows.length > 0;
}
```
**Impact:** first file reading/writing `sean_orders`; needs migration 015 applied wherever it runs.

### Step 6: Best-effort `sean.yml` dispatch
**File:** `web/lib/sean/dispatch.ts` (new) — the same request as `web/lib/sera/gotrade.ts:102-132`, another workflow.
**Code:**
```ts
/**
 * Asks GitHub to run Sean's engine workflow (.github/workflows/sean.yml, Phase 4) now, so the
 * daily profit-and-loss series catches up with a new or deleted order before the nightly run.
 *
 * Best effort and never throws: no GITHUB_DISPATCH_TOKEN, a missing workflow (404, before Phase 4
 * lands), or any other failure only means the nightly run picks the change up. Returns whether
 * the dispatch was accepted.
 */
export async function dispatchSeanMarks(): Promise<boolean> {
  const token = process.env.GITHUB_DISPATCH_TOKEN;
  if (!token) {
    console.log('sean dispatch skipped: GITHUB_DISPATCH_TOKEN is not set');
    return false;
  }
  try {
    const res = await fetch(
      'https://api.github.com/repos/miftahulmahfuzh/seer/actions/workflows/sean.yml/dispatches',
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/vnd.github+json',
          'Content-Type': 'application/json',
          'X-GitHub-Api-Version': '2022-11-28',
        },
        body: JSON.stringify({ ref: 'main' }),
        signal: AbortSignal.timeout(8000),
      },
    );
    if (res.status === 404) {
      console.log('sean dispatch skipped: sean.yml is not on main yet');
      return false;
    }
    if (!res.ok) {
      console.error('sean dispatch failed', res.status, await res.text().catch(() => ''));
      return false;
    }
    return true;
  } catch (e) {
    console.error('sean dispatch failed', e);
    return false;
  }
}
```

### Step 7: Sean's rail
**File:** `web/components/sean/SeanNav.tsx` (new)
**Code:**
```tsx
'use client';

import { Eye, LayoutDashboard, ListChecks, ReceiptText } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import s from './SeanNav.module.css';

const TABS = [
  { href: '/sean', icon: LayoutDashboard, tip: 'Overview' },
  { href: '/sean/trades', icon: ReceiptText, tip: 'Trades' },
  { href: '/sean/plan', icon: ListChecks, tip: 'Plan' },
];

/** The one tab that carries a count: reminders still open on the Plan. */
const BADGED = '/sean/plan';

/** A count fit to print: a whole number above zero, or 0, which renders no badge at all. */
const badgeCount = (n: number): number => (Number.isFinite(n) && n > 0 ? Math.floor(n) : 0);

/**
 * Sean's rail: wordmark, three icon-only section tabs, and a way back to Seer. A top bar below
 * 1024 px. Same build as SeraNav.
 *
 * `planOpen` is the number of buy/sell reminders still to do, read server-side in
 * app/sean/layout.tsx (Phase 5 feeds it; 0 until then). Zero means no badge.
 */
export function SeanNav({ planOpen = 0 }: { planOpen?: number }) {
  const path = usePathname() ?? '';
  return (
    <aside className={s.rail}>
      <span className={s.wordmark}>
        Sean<span className={s.dot}>.</span>
      </span>
      <nav className={s.tabs} aria-label="Sean sections">
        {TABS.map(({ href, icon: Icon, tip }) => {
          const active = href === '/sean' ? path === '/sean' : path === href || path.startsWith(`${href}/`);
          const n = href === BADGED ? badgeCount(planOpen) : 0;
          const label = n > 0 ? `${tip}, ${n} to do` : tip;
          return (
            <Link key={href} href={href} className={active ? s.active : s.tab}
              data-tip={label} aria-label={label} aria-current={active ? 'page' : undefined}>
              <Icon size={22} strokeWidth={active ? 1.75 : 1.5} />
              {n > 0 && <span className={s.badge} aria-hidden="true">{n > 99 ? '99+' : n}</span>}
            </Link>
          );
        })}
      </nav>
      <Link href="/" className={`icon-btn ${s.back}`} data-tip="Back to Seer" aria-label="Back to Seer">
        <Eye size={21} strokeWidth={1.5} />
      </Link>
    </aside>
  );
}
```
(The tip and the aria-label are the identical string, per the icon-only rule.)

**File:** `web/components/sean/SeanNav.module.css` (new)
**Code:**
```css
/* Same rail as Seer's Nav and Sera's SeraNav, always shown: Sean is desktop-first, not desktop-only. */
.rail {
  position: sticky;
  top: 0;
  height: 100dvh;
  flex: none;
  width: 104px;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 28px 0;
  gap: 28px;
}

.wordmark { font-size: 24px; font-weight: 500; letter-spacing: -0.05em; }
.dot { color: var(--coral); }

.tabs {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
  border-radius: 999px;
  background: var(--bar);
}

.tab, .active {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 52px;
  min-width: 52px;
  border-radius: 999px;
  -webkit-tap-highlight-color: transparent;
  user-select: none;
  transition: background 0.12s;
}
.tab { color: var(--bar-ink); }
.tab:hover { background: rgba(255, 255, 255, 0.1); }
.active { background: var(--coral); color: var(--on-coral); }
.tab:focus-visible, .active:focus-visible { outline: 2px solid var(--coral); outline-offset: 2px; }

.back { margin-top: auto; }

/* Open Plan reminders: coral means "you need to act". Same pill as SeraNav's journal badge. */
.badge {
  position: absolute;
  top: -2px;
  right: -2px;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--coral);
  color: var(--on-coral);
  box-shadow: 0 0 0 2px var(--bar);
  font-size: 11.5px;
  line-height: 20px;
  text-align: center;
  font-variant-numeric: tabular-nums;
  pointer-events: none;
}
.active .badge {
  background: var(--on-coral);
  color: var(--coral);
  box-shadow: 0 0 0 2px var(--coral);
}

/* Below 1024 px: a top bar, so the Trades upload also works from the phone that took the screenshots. */
@media (max-width: 1023.98px) {
  .rail {
    z-index: 40;
    width: 100%;
    height: auto;
    flex-direction: row;
    padding: calc(10px + var(--safe-top)) 16px 10px;
    gap: 16px;
    background: var(--bg);
  }
  .tabs { flex-direction: row; padding: 5px; }
  .tab, .active { height: 44px; min-width: 44px; }
  .back { margin-top: 0; margin-left: auto; }
  .badge {
    top: -3px;
    right: -3px;
    min-width: 18px;
    height: 18px;
    padding: 0 5px;
    font-size: 11px;
    line-height: 18px;
  }
}
```

### Step 8: Section shell
**File:** `web/app/sean/layout.tsx` (new)
**Code:**
```tsx
import type { Metadata } from 'next';
import { SeanNav } from '@/components/sean/SeanNav';
import { requireSean } from '@/lib/sean/gate';
import s from './sean.module.css';

export const metadata: Metadata = { title: { default: 'Sean', template: '%s · Sean' } };

/**
 * Sean, the owner's real Gotrade trades: gated like Sera (plan invariant 3), its own rail.
 * `planOpen` is 0 until Phase 5 reads the open reminder count here.
 */
export default async function SeanLayout({ children }: { children: React.ReactNode }) {
  await requireSean();
  return (
    <div className={s.shell}>
      <SeanNav planOpen={0} />
      <main className={s.main}>
        <div className={s.column}>{children}</div>
      </main>
    </div>
  );
}
```

**File:** `web/app/sean/sean.module.css` (new)
**Code:**
```css
.shell { min-height: 100dvh; display: flex; }

.main { flex: 1; min-width: 0; padding: 0 40px 56px 12px; }

/* The content column: wide but bounded, like Sera's. */
.column {
  width: 100%;
  max-width: 1360px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.notFound { padding-top: 40px; }

@media (max-width: 1023.98px) {
  .shell { flex-direction: column; }
  .main { padding: 0 16px 40px; }
}
```

**File:** `web/app/sean/not-found.tsx` (new)
**Code:**
```tsx
import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { Section } from '@/components/sera/Section';
import s from './sean.module.css';

/** notFound() from a /sean page, inside the Sean shell. (A stranger's 404 comes from the layout's gate, outside it.) */
export default function SeanNotFound() {
  return (
    <div className={s.notFound}>
      <Section
        bg="butter"
        eyebrow="Not found"
        title="Nothing lives at this address."
        caption="The page may have moved. The overview has everything Sean keeps."
        aside={
          <Link href="/sean" className="icon-btn" data-tip="Back to the overview" aria-label="Back to the overview">
            <ArrowLeft size={21} strokeWidth={1.5} />
          </Link>
        }
      />
    </div>
  );
}
```

### Step 9: Placeholders for Overview and Plan
**File:** `web/app/sean/page.tsx` (new; Phase 3 replaces the whole file)
**Code:**
```tsx
import { ReceiptText } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { requireSean } from '@/lib/sean/gate';

export const metadata: Metadata = { title: 'Overview' };

// Placeholder until Phase 3 draws the profit-and-loss graph here.
export default async function SeanOverviewPage() {
  await requireSean('/sean');
  return (
    <>
      <PageHeader
        eyebrow="Overview"
        title="Your real money"
        lede="Sean keeps every trade you make on Gotrade and will show how much you have made or lost, after every fee."
      />
      <Section
        bg="butter"
        eyebrow="Coming next"
        title="Your profit and loss will be drawn here."
        caption="Start by giving Sean your Order Summary screenshots on the Trades tab."
        aside={
          <Link href="/sean/trades" className="icon-btn" data-tip="Go to Trades" aria-label="Go to Trades">
            <ReceiptText size={21} strokeWidth={1.5} />
          </Link>
        }
      />
    </>
  );
}
```

**File:** `web/app/sean/plan/page.tsx` (new; Phase 5 replaces the whole file)
**Code:**
```tsx
import { ReceiptText } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { requireSean } from '@/lib/sean/gate';

export const metadata: Metadata = { title: 'Plan' };

// Placeholder until Phase 5 links a roster method and lists reminders here.
export default async function SeanPlanPage() {
  await requireSean('/sean/plan');
  return (
    <>
      <PageHeader
        eyebrow="Plan"
        title="Follow one of Seer's methods"
        lede="Soon you can pick the method you follow, like RAW, and Sean will tell you what to buy and what to sell to keep up with it."
      />
      <Section
        bg="lav"
        eyebrow="Coming next"
        title="Nothing to follow yet."
        caption="Meanwhile, keep your trades up to date on the Trades tab."
        aside={
          <Link href="/sean/trades" className="icon-btn" data-tip="Go to Trades" aria-label="Go to Trades">
            <ReceiptText size={21} strokeWidth={1.5} />
          </Link>
        }
      />
    </>
  );
}
```

### Step 10: Pure upload rules (shared by browser and route)
**File:** `web/app/sean/trades/upload.ts` (new)
**Code:**
```ts
// Pure upload rules for /sean/trades, shared by the browser uploader (Uploader.tsx) and
// POST /api/sean/orders. No data access, no DOM: tested in upload.test.ts.

/** Shared contract C: the decoded picture may be at most 1.5 MB. */
export const MAX_UPLOAD_BYTES = 1.5 * 1024 * 1024;
/** A JPEG this size or smaller goes up as it is; anything bigger is re-encoded first. */
export const REENCODE_OVER_BYTES = 1_000_000;
/** How many pictures are read at once. Each takes 10-40 s at the model. */
export const CONCURRENCY = 3;
/** Re-encoding also shrinks the long side to at most this many pixels (a phone screenshot is ~1600). */
export const MAX_SIDE_PX = 2400;
/**
 * ...but never takes the short side below this (Phase 1 handoff: run-insights read 108/108 at a
 * 560 px short edge; smaller pictures push prompt_tokens toward the reader's token floor).
 */
export const MIN_SHORT_PX = 560;

export type FileKind = 'zip' | 'image' | 'other';

const IMAGE_NAME = /\.(jpe?g|png|webp)$/i;
const IMAGE_TYPE = /^image\/(jpeg|png|webp)$/;
const ZIP_TYPES = new Set(['application/zip', 'application/x-zip-compressed']);

/** What a picked file (or a zip entry, which has no type) is, by its name and MIME type. */
export function kindOf(name: string, type = ''): FileKind {
  if (/\.zip$/i.test(name) || ZIP_TYPES.has(type)) return 'zip';
  if (IMAGE_NAME.test(name) || IMAGE_TYPE.test(type)) return 'image';
  return 'other';
}

/** 'gotrade/WhatsApp Image 1.jpeg' -> 'WhatsApp Image 1.jpeg'. */
export function baseName(path: string): string {
  const parts = path.split('/').filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : path;
}

/** A JPEG starts with FF D8 FF. */
export function isJpeg(bytes: Uint8Array): boolean {
  return bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
}

/** The model is sent a JPEG: re-encode anything that is not one, or a JPEG over ~1 MB. */
export function needsReencode(bytes: Uint8Array): boolean {
  return !isJpeg(bytes) || bytes.length > REENCODE_OVER_BYTES;
}

/**
 * The size to draw at: unchanged when the long side fits, else scaled down toward `max` on the
 * long side -- but never so far that the short side drops under `minShort`, and never up.
 */
export function fitWithin(
  width: number,
  height: number,
  max = MAX_SIDE_PX,
  minShort = MIN_SHORT_PX,
): { width: number; height: number } {
  const long = Math.max(width, height);
  if (long <= max) return { width, height };
  const short = Math.min(width, height);
  const k = Math.min(1, Math.max(max / long, minShort / short));
  if (k >= 1) return { width, height };
  return { width: Math.max(1, Math.round(width * k)), height: Math.max(1, Math.round(height * k)) };
}

/** Bytes -> base64 (no data: prefix), in chunks so a large picture does not overflow the call stack. */
export function toBase64(bytes: Uint8Array): string {
  let bin = '';
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    bin += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  }
  return btoa(bin);
}

/** A digest as lower-case hex. */
export function hex(buf: ArrayBuffer): string {
  return Array.from(new Uint8Array(buf), b => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Runs `worker` over `items`, at most `limit` at a time, in order of start. Resolves when every
 * item is done; rejects if a worker throws (the uploader's worker never does).
 */
export async function runPool<T>(
  items: readonly T[],
  limit: number,
  worker: (item: T, index: number) => Promise<void>,
): Promise<void> {
  let next = 0;
  const lanes = Math.max(1, Math.min(Math.floor(limit), items.length));
  await Promise.all(
    Array.from({ length: lanes }, async () => {
      while (next < items.length) {
        const i = next++;
        await worker(items[i], i);
      }
    }),
  );
}

/** How many bytes a base64 string decodes to. */
export function decodedLength(b64: string): number {
  const pad = b64.endsWith('==') ? 2 : b64.endsWith('=') ? 1 : 0;
  return Math.floor((b64.length * 3) / 4) - pad;
}

const SHA256_HEX = /^[0-9a-f]{64}$/;
const BASE64 = /^[A-Za-z0-9+/]*={0,2}$/;

export type UploadBody =
  | { ok: true; image: string; sha256: string }
  | { ok: false; status: 400 | 413 };

/**
 * The route's request check (shared contract C): `{ image: base64 without a data: prefix,
 * sha256: hex }`. 413 when the picture is over MAX_UPLOAD_BYTES, 400 for anything malformed.
 * The size is checked before the character scan, so an oversized body is refused cheaply.
 */
export function parseUploadBody(body: unknown): UploadBody {
  if (!body || typeof body !== 'object' || Array.isArray(body)) return { ok: false, status: 400 };
  const { image, sha256 } = body as { image?: unknown; sha256?: unknown };
  if (typeof image !== 'string' || typeof sha256 !== 'string') return { ok: false, status: 400 };
  const sha = sha256.trim().toLowerCase();
  if (!SHA256_HEX.test(sha)) return { ok: false, status: 400 };
  if (image.length === 0 || image.length % 4 !== 0) return { ok: false, status: 400 };
  if (decodedLength(image) > MAX_UPLOAD_BYTES) return { ok: false, status: 413 };
  if (!BASE64.test(image)) return { ok: false, status: 400 };
  return { ok: true, image, sha256: sha };
}
```

**File:** `web/app/sean/trades/upload.test.ts` (new)
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import {
  MAX_UPLOAD_BYTES, MIN_SHORT_PX, REENCODE_OVER_BYTES, baseName, decodedLength, fitWithin, hex, isJpeg, kindOf,
  needsReencode, parseUploadBody, runPool, toBase64,
} from './upload';

const SHA = 'a'.repeat(64);
const jpeg = (n: number) => {
  const b = new Uint8Array(n);
  b[0] = 0xff; b[1] = 0xd8; b[2] = 0xff;
  return b;
};

describe('kindOf', () => {
  it('knows zips by name or type', () => {
    expect(kindOf('gotrade_order_summary_screenshots.zip')).toBe('zip');
    expect(kindOf('archive', 'application/x-zip-compressed')).toBe('zip');
  });
  it('knows pictures by name or type', () => {
    expect(kindOf('WhatsApp Image 2026-10-07 at 10.14.45 PM.jpeg')).toBe('image');
    expect(kindOf('shot.PNG')).toBe('image');
    expect(kindOf('blob', 'image/webp')).toBe('image');
  });
  it('refuses everything else, HEIC included', () => {
    expect(kindOf('IMG_0001.HEIC', 'image/heic')).toBe('other');
    expect(kindOf('notes.txt', 'text/plain')).toBe('other');
  });
});

describe('baseName', () => {
  it('drops the folders a zip keeps', () => {
    expect(baseName('gotrade/WhatsApp Image 1.jpeg')).toBe('WhatsApp Image 1.jpeg');
    expect(baseName('one.jpg')).toBe('one.jpg');
  });
});

describe('isJpeg / needsReencode', () => {
  it('sends a small JPEG as it is', () => {
    expect(isJpeg(jpeg(60_000))).toBe(true);
    expect(needsReencode(jpeg(60_000))).toBe(false);
  });
  it('re-encodes a big JPEG or anything that is not a JPEG', () => {
    expect(needsReencode(jpeg(REENCODE_OVER_BYTES + 1))).toBe(true);
    expect(needsReencode(new Uint8Array([0x89, 0x50, 0x4e, 0x47]))).toBe(true);
    expect(isJpeg(new Uint8Array([0xff, 0xd8]))).toBe(false);
  });
});

describe('fitWithin', () => {
  it('keeps a phone screenshot as it is', () => {
    expect(fitWithin(739, 1600)).toEqual({ width: 739, height: 1600 });
  });
  it('shrinks the long side to the limit', () => {
    expect(fitWithin(3000, 6000, 2400)).toEqual({ width: 1200, height: 2400 });
  });
  it('never takes the short side under 560 px, and never scales up', () => {
    expect(MIN_SHORT_PX).toBe(560);
    // a very tall capture: 2400 on the long side would leave 480 px; stop at 560 instead
    expect(fitWithin(600, 3000, 2400)).toEqual({ width: 560, height: 2800 });
    // already narrower than 560: left as it is
    expect(fitWithin(500, 3000, 2400)).toEqual({ width: 500, height: 3000 });
  });
});

describe('toBase64 / decodedLength / hex', () => {
  it('matches Node for bytes past one chunk', () => {
    const bytes = Uint8Array.from({ length: 70_000 }, (_, i) => (i * 31) % 256);
    const b64 = toBase64(bytes);
    expect(b64).toBe(Buffer.from(bytes).toString('base64'));
    expect(decodedLength(b64)).toBe(70_000);
  });
  it('counts padding', () => {
    expect(decodedLength('QQ==')).toBe(1);
    expect(decodedLength('QUI=')).toBe(2);
    expect(decodedLength('QUJD')).toBe(3);
  });
  it('writes digests as lower-case hex', () => {
    expect(hex(new Uint8Array([0, 15, 255]).buffer)).toBe('000fff');
  });
});

describe('runPool', () => {
  it('runs every item, never more than the limit at once', async () => {
    let live = 0;
    let peak = 0;
    const done: number[] = [];
    await runPool([1, 2, 3, 4, 5, 6, 7], 3, async n => {
      live += 1;
      peak = Math.max(peak, live);
      await new Promise(r => setTimeout(r, 5 + (n % 3)));
      done.push(n);
      live -= 1;
    });
    expect(peak).toBe(3);
    expect(done.sort()).toEqual([1, 2, 3, 4, 5, 6, 7]);
  });
  it('is a no-op on nothing', async () => {
    let calls = 0;
    await runPool([], 3, async () => { calls += 1; });
    expect(calls).toBe(0);
  });
});

describe('parseUploadBody', () => {
  it('accepts a base64 picture and a hex digest, lower-casing the digest', () => {
    expect(parseUploadBody({ image: 'QUJD', sha256: SHA.toUpperCase() })).toEqual({ ok: true, image: 'QUJD', sha256: SHA });
  });
  it('refuses malformed bodies with 400', () => {
    expect(parseUploadBody(null)).toEqual({ ok: false, status: 400 });
    expect(parseUploadBody([])).toEqual({ ok: false, status: 400 });
    expect(parseUploadBody({ image: 'QUJD' })).toEqual({ ok: false, status: 400 });
    expect(parseUploadBody({ image: 'QUJD', sha256: 'abc' })).toEqual({ ok: false, status: 400 });
    expect(parseUploadBody({ image: '', sha256: SHA })).toEqual({ ok: false, status: 400 });
    expect(parseUploadBody({ image: 'data:image/jpeg;base64,QUJD', sha256: SHA })).toEqual({ ok: false, status: 400 });
    expect(parseUploadBody({ image: 'QU*D', sha256: SHA })).toEqual({ ok: false, status: 400 });
  });
  it('refuses a picture over 1.5 MB with 413', () => {
    const big = 'A'.repeat(Math.ceil(((MAX_UPLOAD_BYTES + 3) * 4) / 3 / 4) * 4);
    expect(parseUploadBody({ image: big, sha256: SHA })).toEqual({ ok: false, status: 413 });
  });
});
```

### Step 11: Pure words and numbers for Trades
**File:** `web/app/sean/trades/view.ts` (new)
**Code:**
```ts
// Pure helpers for /sean/trades: the plain sentences and numbers the page, the uploader, the
// upload route and the delete buttons show. No data access, no DOM: tested in view.test.ts.
// The owner is not a trader: no ids, no digests, no status codes in any string here.
import type { OrderRow } from '../../../lib/sean/data';

/* ---- Numbers ---------------------------------------------------------------------------- */

const MINUS = '−';
const USD = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2 });
const PRICE = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 3 });
const DAY = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric', year: 'numeric' });

/** 1063.886 -> '$1,063.89'. Always unsigned. */
export const dollars = (v: number): string => USD.format(Math.abs(v));
/** 22.31 -> '+$22.31', -0.5 -> '−$0.50'. */
export const signedDollars = (v: number): string => (v < 0 ? MINUS : '+') + dollars(v);
/** A price as Gotrade prints it: 1063.886 -> '$1,063.886', 131.47 -> '$131.47'. */
export const priceText = (v: number): string => PRICE.format(v);
/** 5.38 -> '5.38 shares', 1 -> '1 share', 0.026224614 -> '0.026224614 shares'. */
export function sharesText(n: number): string {
  const t = n.toFixed(9).replace(/0+$/, '').replace(/\.$/, '');
  return `${t} ${t === '1' ? 'share' : 'shares'}`;
}
/** '2025-06-10' -> 'Jun 10, 2025'. */
export const dayText = (ymd: string): string => DAY.format(new Date(`${ymd.slice(0, 10)}T12:00:00Z`));
/** '2026-10-07T21:55' -> 'Oct 7, 2026 · 21:55' (Jakarta time, as the receipt prints it). */
export const whenText = (executedWib: string): string => `${dayText(executedWib)} · ${executedWib.slice(11, 16)}`;

/* ---- The order list --------------------------------------------------------------------- */

export type OrderItem = {
  id: number;
  when: string;
  side: 'buy' | 'sell';
  sideLabel: 'Bought' | 'Sold';
  symbol: string;
  detail: string;
  fees: string;
  feesTip: string;
  total: string;
  totalWord: 'paid' | 'received';
  /** Gotrade's own profit figure on a sale; null on buys. */
  profit: { text: string; tone: 'pos' | 'neg' | '' } | null;
  deleteLabel: string;
  confirmLabel: string;
};

function orderName(r: Pick<OrderRow, 'side' | 'symbol' | 'executedWib'>): string {
  return `the ${r.symbol} ${r.side === 'buy' ? 'buy' : 'sale'} from ${dayText(r.executedWib)}`;
}

export function orderItem(r: OrderRow): OrderItem {
  let profit: OrderItem['profit'] = null;
  if (r.side === 'sell' && r.netProfitUsd !== null) {
    profit = r.netProfitUsd > 0
      ? { text: `${signedDollars(r.netProfitUsd)} profit`, tone: 'pos' }
      : r.netProfitUsd < 0
        ? { text: `${signedDollars(r.netProfitUsd)} loss`, tone: 'neg' }
        : { text: 'Broke even', tone: '' };
  }
  return {
    id: r.id,
    when: whenText(r.executedWib),
    side: r.side,
    sideLabel: r.side === 'buy' ? 'Bought' : 'Sold',
    symbol: r.symbol,
    detail: `${sharesText(r.shares)} at ${priceText(r.price)}`,
    fees: `${dollars(r.feesUsd)} fees`,
    feesTip: `Gotrade's fee ${dollars(r.tradingFeeUsd)}, the regulator's fee ${dollars(r.regulatoryFeeUsd)}, tax (PPN) ${dollars(r.ppnUsd)}`,
    total: dollars(r.totalUsd),
    totalWord: r.side === 'buy' ? 'paid' : 'received',
    profit,
    deleteLabel: `Delete ${orderName(r)}`,
    confirmLabel: `Yes, delete ${orderName(r)}`,
  };
}

/** 'No orders' / '1 order' / '30 orders'. */
export const orderCount = (n: number): string => (n === 0 ? 'No orders' : n === 1 ? '1 order' : `${n} orders`);

const count = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** The line under the list. `rows` newest first, as data.orders() returns them. */
export function ordersCaption(rows: OrderRow[]): string | undefined {
  if (rows.length === 0) return undefined;
  const buys = rows.filter(r => r.side === 'buy').length;
  const sales = rows.length - buys;
  const parts = [buys > 0 ? count(buys, 'buy', 'buys') : null, sales > 0 ? count(sales, 'sale', 'sales') : null]
    .filter(Boolean)
    .join(' and ');
  const first = dayText(rows[rows.length - 1].executedWib);
  const last = dayText(rows[0].executedWib);
  const span = first === last ? `on ${first}` : `between ${first} and ${last}`;
  return `${parts} ${span}, newest first. Point at the fees to see what they are made of.`;
}

export const ORDERS_EMPTY = 'No orders yet. Add your first Order Summary screenshot above.';
export const ORDERS_UNREADABLE = "Your orders can't be read right now. Nothing is lost; try again in a moment.";

/* ---- Delete ----------------------------------------------------------------------------- */

export type FormState = { tone: 'idle' | 'ok' | 'error'; message: string };
export const IDLE: FormState = { tone: 'idle', message: '' };
export const NOT_ALLOWED: FormState = { tone: 'error', message: 'Only the owner can change these orders.' };
export const NOT_THERE: FormState = { tone: 'ok', message: 'That order was already gone.' };
export const DELETED: FormState = { tone: 'ok', message: 'Deleted.' };
export const DELETE_FAILED: FormState = { tone: 'error', message: "It couldn't be deleted just now. Try again in a moment." };

/** The hidden `id` field of a delete form: a positive whole number, or null. */
export function parseOrderId(v: unknown): number | null {
  if (typeof v !== 'string' || !/^\d{1,15}$/.test(v)) return null;
  const n = Number(v);
  return n > 0 ? n : null;
}

/* ---- Upload ----------------------------------------------------------------------------- */

export type UploadState = 'waiting' | 'reading' | 'saved' | 'duplicate' | 'failed';
export type UploadOutcome = { state: 'saved' | 'duplicate' | 'failed'; message: string; retry: boolean };
export type UploadItem = { key: string; name: string; state: UploadState; message: string; retry: boolean };

const failed = (message: string, retry: boolean): UploadOutcome => ({ state: 'failed', message, retry });

/**
 * What the upload route says in its own words, and what the uploader falls back to when a body
 * carries none. A refused read (422) or a reader failure (502) says Phase 1's READ_MESSAGES text
 * instead (lib/sean/readOrder.ts: plain words, plus the first problem when there is one).
 */
export const SAY = {
  damaged: 'The picture arrived damaged. Try this one again.',
  tooLarge: 'This picture is too large. A normal phone screenshot is fine.',
  unreadable: "Sean couldn't read this as a Gotrade Order Summary. Make sure the whole receipt is in the picture.",
  notSetUp: "Sean's reader isn't set up yet. Nothing was saved.",
  readerDown: "Sean's reader didn't answer in time. Nothing was saved; try this one again.",
  saveFailed: "The receipt was read but couldn't be saved. Try this one again.",
} as const;

export const WAITING = 'Waiting its turn.';
export const READING = 'Reading the receipt…';
export const OFFLINE = failed("Sean couldn't be reached. Check your connection and try again.", true);
export const NOT_A_PICTURE = failed("This isn't a picture Sean can open. Use a normal screenshot (JPEG or PNG).", false);
export const TOO_LARGE_PICTURE = failed(SAY.tooLarge, false);
export const ZIP_UNREADABLE = failed("This zip couldn't be opened.", false);
export const ZIP_EMPTY = failed('There were no pictures in this zip.', false);
export const SAME_AS_ANOTHER: UploadOutcome = { state: 'duplicate', message: 'The same picture is already in this batch.', retry: false };

/** 'PLTR: bought 5.38 shares for $709.44 on Jun 10, 2025.' */
export function savedLine(o: Pick<OrderRow, 'side' | 'symbol' | 'shares' | 'totalUsd' | 'executedWib'>): string {
  return `${o.symbol}: ${o.side === 'buy' ? 'bought' : 'sold'} ${sharesText(o.shares)} for ${dollars(o.totalUsd)} on ${dayText(o.executedWib)}.`;
}

function isOrderLike(v: unknown): v is OrderRow {
  if (!v || typeof v !== 'object') return false;
  const o = v as Partial<OrderRow>;
  return typeof o.symbol === 'string' && (o.side === 'buy' || o.side === 'sell')
    && typeof o.shares === 'number' && typeof o.totalUsd === 'number' && typeof o.executedWib === 'string';
}

/** Turns the route's answer (shared contract C) into one row of the uploader's list. */
export function readResponse(status: number, body: unknown): UploadOutcome {
  const b = (body && typeof body === 'object' ? body : {}) as { order?: unknown; duplicate?: unknown; error?: unknown };
  if ((status === 200 || status === 201) && isOrderLike(b.order)) {
    return status === 200 || b.duplicate === true
      ? { state: 'duplicate', message: `Already saved. ${savedLine(b.order)}`, retry: false }
      : { state: 'saved', message: savedLine(b.order), retry: false };
  }
  const said = typeof b.error === 'string' && b.error.trim() ? b.error.trim() : null;
  switch (status) {
    case 404: return failed('Only the owner can add trades here.', false);
    case 413: return failed(said ?? SAY.tooLarge, false);
    case 400: return failed(said ?? SAY.damaged, true);
    case 422: return failed(said ?? SAY.unreadable, false);
    case 502: return failed(said ?? SAY.readerDown, true);
    case 504: return failed(SAY.readerDown, true);
    default:
      return status >= 500
        ? failed(said ?? 'Something went wrong on Sean’s side. Try this one again in a moment.', true)
        : failed('Something unexpected came back. Try this one again.', true);
  }
}

/** While a batch runs: '4 of 30 done. Sean reads three at a time, and each takes up to half a minute.' */
export function progressLine(items: UploadItem[]): string {
  const total = items.length;
  if (total === 0) return '';
  const done = items.filter(i => i.state === 'saved' || i.state === 'duplicate' || i.state === 'failed').length;
  if (done === total) return '';
  return `${done} of ${total} done. Sean reads three at a time, and each takes up to half a minute.`;
}

/** When a batch ends: 'Done: 28 saved, 1 already here and 1 couldn't be read.' */
export function batchSummary(c: { saved: number; duplicate: number; failed: number }): string {
  const parts = [
    c.saved > 0 ? `${c.saved} saved` : null,
    c.duplicate > 0 ? `${c.duplicate} already here` : null,
    c.failed > 0 ? `${c.failed} couldn't be read` : null,
  ].filter((p): p is string => p !== null);
  if (parts.length === 0) return 'Nothing to read.';
  const list = parts.length === 1 ? parts[0] : `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`;
  return `Done: ${list}.`;
}
```

**File:** `web/app/sean/trades/view.test.ts` (new)
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import type { OrderRow } from '../../../lib/sean/data';
import {
  batchSummary, dayText, dollars, orderCount, orderItem, ordersCaption, parseOrderId,
  priceText, progressLine, readResponse, SAY, savedLine, sharesText, signedDollars, whenText,
  type UploadItem,
} from './view';

// Real receipts (screenshots_truth.json): the PLTR split buy, the MU fractional buy, the PLTR sell.
const PLTR_BUY: OrderRow = {
  id: 1, side: 'buy', orderType: 'Market Buy', symbol: 'PLTR', executedWib: '2025-06-10T21:34',
  price: 131.47, shares: 5.38, amountUsd: 707.31, tradingFeeUsd: 0, regulatoryFeeUsd: 2.13, ppnUsd: 0,
  feesUsd: 2.13, totalUsd: 709.44, netProfitUsd: null,
};
const MU_BUY: OrderRow = {
  id: 2, side: 'buy', orderType: 'Market Buy', symbol: 'MU', executedWib: '2026-10-07T22:00',
  price: 1063.886, shares: 0.026224614, amountUsd: 27.9, tradingFeeUsd: 0.1, regulatoryFeeUsd: 0.02, ppnUsd: 0.01,
  feesUsd: 0.13, totalUsd: 28.03, netProfitUsd: null,
};
const PLTR_SELL: OrderRow = {
  id: 3, side: 'sell', orderType: 'Market Sell', symbol: 'PLTR', executedWib: '2026-10-07T21:55',
  price: 190.81, shares: 0.38, amountUsd: 72.51, tradingFeeUsd: 0.15, regulatoryFeeUsd: 0.07, ppnUsd: 0.02,
  feesUsd: 0.24, totalUsd: 72.27, netProfitUsd: 22.31,
};

describe('numbers', () => {
  it('formats money with thousands separators', () => {
    expect(dollars(1063.886)).toBe('$1,063.89');
    expect(dollars(-0.5)).toBe('$0.50');
    expect(signedDollars(22.31)).toBe('+$22.31');
    expect(signedDollars(-0.5)).toBe('−$0.50');
  });
  it('prints prices as Gotrade does, up to three decimals', () => {
    expect(priceText(1063.886)).toBe('$1,063.886');
    expect(priceText(131.47)).toBe('$131.47');
    expect(priceText(295.1)).toBe('$295.10');
  });
  it('prints shares without trailing zeros', () => {
    expect(sharesText(5.38)).toBe('5.38 shares');
    expect(sharesText(0.026224614)).toBe('0.026224614 shares');
    expect(sharesText(1)).toBe('1 share');
    expect(sharesText(5)).toBe('5 shares');
  });
  it('prints dates and Jakarta times', () => {
    expect(dayText('2025-06-10')).toBe('Jun 10, 2025');
    expect(whenText('2026-10-07T21:55')).toBe('Oct 7, 2026 · 21:55');
  });
});

describe('orderItem', () => {
  it('describes a buy', () => {
    expect(orderItem(PLTR_BUY)).toEqual({
      id: 1,
      when: 'Jun 10, 2025 · 21:34',
      side: 'buy',
      sideLabel: 'Bought',
      symbol: 'PLTR',
      detail: '5.38 shares at $131.47',
      fees: '$2.13 fees',
      feesTip: "Gotrade's fee $0.00, the regulator's fee $2.13, tax (PPN) $0.00",
      total: '$709.44',
      totalWord: 'paid',
      profit: null,
      deleteLabel: 'Delete the PLTR buy from Jun 10, 2025',
      confirmLabel: 'Yes, delete the PLTR buy from Jun 10, 2025',
    });
  });
  it('describes a fractional buy', () => {
    expect(orderItem(MU_BUY).detail).toBe('0.026224614 shares at $1,063.886');
    expect(orderItem(MU_BUY).fees).toBe('$0.13 fees');
  });
  it('describes a sale with Gotrade’s profit, coloured as profit', () => {
    const sale = orderItem(PLTR_SELL);
    expect(sale.sideLabel).toBe('Sold');
    expect(sale.totalWord).toBe('received');
    expect(sale.profit).toEqual({ text: '+$22.31 profit', tone: 'pos' });
    expect(sale.deleteLabel).toBe('Delete the PLTR sale from Oct 7, 2026');
  });
  it('says loss or broke even', () => {
    expect(orderItem({ ...PLTR_SELL, netProfitUsd: -1.5 }).profit).toEqual({ text: '−$1.50 loss', tone: 'neg' });
    expect(orderItem({ ...PLTR_SELL, netProfitUsd: 0 }).profit).toEqual({ text: 'Broke even', tone: '' });
  });
  it('never shows an id or a digest in any string', () => {
    const strings = Object.values(orderItem(PLTR_BUY)).filter((v): v is string => typeof v === 'string');
    for (const s of strings) expect(s).not.toMatch(/\b[0-9a-f]{16,}\b/);
  });
});

describe('orderCount / ordersCaption', () => {
  it('counts in words', () => {
    expect(orderCount(0)).toBe('No orders');
    expect(orderCount(1)).toBe('1 order');
    expect(orderCount(30)).toBe('30 orders');
  });
  it('summarises buys, sales and the span, newest first', () => {
    expect(ordersCaption([MU_BUY, PLTR_SELL, PLTR_BUY])).toBe(
      '2 buys and 1 sale between Jun 10, 2025 and Oct 7, 2026, newest first. Point at the fees to see what they are made of.',
    );
    expect(ordersCaption([PLTR_BUY])).toBe('1 buy on Jun 10, 2025, newest first. Point at the fees to see what they are made of.');
    expect(ordersCaption([])).toBeUndefined();
  });
});

describe('parseOrderId', () => {
  it('takes a positive whole number only', () => {
    expect(parseOrderId('42')).toBe(42);
    expect(parseOrderId('0')).toBeNull();
    expect(parseOrderId('-1')).toBeNull();
    expect(parseOrderId('1.5')).toBeNull();
    expect(parseOrderId(null)).toBeNull();
    expect(parseOrderId('9'.repeat(16))).toBeNull();
  });
});

describe('savedLine', () => {
  it('says what was saved in one plain sentence', () => {
    expect(savedLine(PLTR_BUY)).toBe('PLTR: bought 5.38 shares for $709.44 on Jun 10, 2025.');
    expect(savedLine(PLTR_SELL)).toBe('PLTR: sold 0.38 shares for $72.27 on Oct 7, 2026.');
  });
});

describe('readResponse', () => {
  it('201 is saved, 200 is already saved', () => {
    expect(readResponse(201, { order: PLTR_BUY })).toEqual({ state: 'saved', message: savedLine(PLTR_BUY), retry: false });
    expect(readResponse(200, { order: PLTR_BUY, duplicate: true })).toEqual({
      state: 'duplicate', message: `Already saved. ${savedLine(PLTR_BUY)}`, retry: false,
    });
  });
  it('uses the route’s own words when it gives them', () => {
    const said = 'Sean only records filled orders. This order says "Cancelled", not "Filled".';
    expect(readResponse(422, { error: said })).toEqual({ state: 'failed', message: said, retry: false });
  });
  it('falls back to plain words and says which ones are worth retrying', () => {
    expect(readResponse(422, null)).toEqual({ state: 'failed', message: SAY.unreadable, retry: false });
    expect(readResponse(413, null)).toEqual({ state: 'failed', message: SAY.tooLarge, retry: false });
    expect(readResponse(502, null)).toEqual({ state: 'failed', message: SAY.readerDown, retry: true });
    expect(readResponse(504, { error: 'FUNCTION_INVOCATION_TIMEOUT' })).toEqual({ state: 'failed', message: SAY.readerDown, retry: true });
    expect(readResponse(404, null).message).toBe('Only the owner can add trades here.');
    expect(readResponse(500, null).retry).toBe(true);
  });
  it('a success without an order is not a success', () => {
    expect(readResponse(201, {}).state).toBe('failed');
  });
  it('never shows a status code', () => {
    for (const status of [400, 404, 413, 418, 422, 500, 502, 503, 504]) {
      expect(readResponse(status, null).message).not.toMatch(/\d{3}/);
    }
  });
});

describe('progressLine / batchSummary', () => {
  const item = (state: UploadItem['state']): UploadItem => ({ key: state, name: 'x.jpeg', state, message: '', retry: false });
  it('counts finished pictures while a batch runs', () => {
    expect(progressLine([item('saved'), item('reading'), item('waiting'), item('failed')])).toBe(
      '2 of 4 done. Sean reads three at a time, and each takes up to half a minute.',
    );
    expect(progressLine([item('saved')])).toBe('');
    expect(progressLine([])).toBe('');
  });
  it('sums up a finished batch', () => {
    expect(batchSummary({ saved: 28, duplicate: 1, failed: 1 })).toBe("Done: 28 saved, 1 already here and 1 couldn't be read.");
    expect(batchSummary({ saved: 3, duplicate: 0, failed: 0 })).toBe('Done: 3 saved.');
    expect(batchSummary({ saved: 0, duplicate: 2, failed: 1 })).toBe("Done: 2 already here and 1 couldn't be read.");
    expect(batchSummary({ saved: 0, duplicate: 0, failed: 0 })).toBe('Nothing to read.');
  });
});
```

### Step 12: The upload route (shared contract C)
**File:** `web/app/api/sean/orders/route.ts` (new)
**Code:**
```ts
import { createHash } from 'node:crypto';
import { orderById, orderIdBySha, saveOrder } from '@/lib/sean/data';
import { isSeanCaller } from '@/lib/sean/gate';
import { isReaderDown, readOrder, visionDeps, type ReadOrderOutcome } from '@/lib/sean/readOrder';
import { visionConfigFromEnv } from '@/lib/sean/vision';
import { parseUploadBody } from '@/app/sean/trades/upload';
import { SAY } from '@/app/sean/trades/view';

// Reads cookies, calls the vision model, writes a row: never cached, never prerendered.
export const dynamic = 'force-dynamic';
// GLM-4.6V takes 5-40 s per picture. Must stay a literal number (read at build time).
export const maxDuration = 60;

const fail = (status: number, error: string) => Response.json({ error }, { status });

/**
 * POST /api/sean/orders -- read one Gotrade Order Summary screenshot and keep the order.
 *
 * Body: {"image": base64 JPEG without a data: prefix, "sha256": hex of the decoded bytes}.
 * 201 {order} new; 200 {order, duplicate: true} same picture or same order already kept;
 * 400 malformed or damaged; 413 over 1.5 MB; 422 not a readable, filled receipt (Phase 1's
 * plain-words message); 502 the reader is missing, unreachable, timed out or did not see the
 * picture; 500 the save failed; 404 to anyone but the owner.
 * The picture itself is never stored: only its SHA-256, for dedupe (plan scope).
 */
export async function POST(req: Request) {
  if (!(await isSeanCaller())) return new Response(null, { status: 404 });

  let body: unknown;
  try {
    body = JSON.parse(await req.text());
  } catch {
    return fail(400, SAY.damaged);
  }
  const upload = parseUploadBody(body);
  if (!upload.ok) return fail(upload.status, upload.status === 413 ? SAY.tooLarge : SAY.damaged);

  // The client's digest must be of the bytes that arrived: it is the dedupe key.
  const sha = createHash('sha256').update(Buffer.from(upload.image, 'base64')).digest('hex');
  if (sha !== upload.sha256) return fail(400, SAY.damaged);

  try {
    const known = await orderIdBySha(sha);
    if (known !== null) {
      const order = await orderById(known);
      if (order) return Response.json({ order, duplicate: true }, { status: 200 });
    }
  } catch (e) {
    console.error('sean_orders read failed', e);
    return fail(500, SAY.saveFailed);
  }

  const config = visionConfigFromEnv();
  if (!config) {
    console.error('sean: LLM_API_KEY, LLM_VISION_BASE_URL or LLM_VISION_MODEL is not set (or is the /api/anthropic URL)');
    return fail(502, SAY.notSetUp);
  }

  // Phase 1's readOrder never throws for a model problem: vision, JSON, the arithmetic checks
  // (toOrder also refuses every status but "Filled") and at most one image-carrying repair, all
  // inside its 55 s budget (READ_BUDGET_MS). It rethrows only an error that is not the reader's.
  let out: ReadOrderOutcome;
  try {
    out = await readOrder(visionDeps(config), upload.image);
  } catch (e) {
    console.error('sean: read failed unexpectedly', e);
    return fail(502, SAY.readerDown);
  }
  if (!out.ok) {
    // detail and issues are for the logs only; out.message is already plain words for the owner.
    console.warn('sean: receipt refused', out.code, out.detail ?? out.issues.join(' | '));
    return fail(isReaderDown(out.code) ? 502 : 422, out.message);
  }

  try {
    const saved = await saveOrder(out.order, sha, out.raw);
    const order = await orderById(saved.id);
    if (!order) throw new Error('the saved order could not be read back');
    return saved.duplicate
      ? Response.json({ order, duplicate: true }, { status: 200 })
      : Response.json({ order }, { status: 201 });
  } catch (e) {
    console.error('sean_orders write failed', e);
    return fail(500, SAY.saveFailed);
  }
}
```
**Impact:** body size: a 1.5 MB picture is ~2 MB of base64 JSON, under Vercel's 4.5 MB function request limit; route handlers have no Next-side body cap (the 1 MB `serverActions.bodySizeLimit` applies to server actions only, which is why the upload is a route and not an action). `maxDuration = 60` is within the Vercel Hobby limit.

### Step 13: Server actions
**File:** `web/app/sean/trades/actions.ts` (new)
**Code:**
```ts
'use server';

import { revalidatePath } from 'next/cache';
import { removeOrder } from '@/lib/sean/data';
import { dispatchSeanMarks } from '@/lib/sean/dispatch';
import { isSeanCaller } from '@/lib/sean/gate';
import { DELETE_FAILED, DELETED, NOT_ALLOWED, NOT_THERE, parseOrderId, type FormState } from './view';

/** Deletes one order (a misread or a mistaken upload), then asks the engine to redo the P&L. */
export async function deleteOrder(_prev: FormState, formData: FormData): Promise<FormState> {
  if (!(await isSeanCaller())) return NOT_ALLOWED;
  const id = parseOrderId(formData.get('id'));
  if (id === null) return NOT_THERE;

  let removed: boolean;
  try {
    removed = await removeOrder(id);
  } catch (e) {
    console.error('sean_orders delete failed', e);
    return DELETE_FAILED;
  }
  if (removed) await dispatchSeanMarks();
  revalidatePath('/sean', 'layout');
  return removed ? DELETED : NOT_THERE;
}

/**
 * Called by the uploader once a batch saved at least one order: asks the engine to fetch prices
 * and redo the daily P&L now instead of tonight. Best effort; returns whether it was asked.
 */
export async function refreshPnl(): Promise<boolean> {
  if (!(await isSeanCaller())) return false;
  const sent = await dispatchSeanMarks();
  revalidatePath('/sean', 'layout');
  return sent;
}
```

### Step 14: The uploader
**File:** `web/app/sean/trades/Uploader.tsx` (new)
**Code:**
```tsx
'use client';

import { CircleAlert, CircleCheck, CircleDashed, CopyCheck, ImagePlus, ListX, LoaderCircle, RotateCcw } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react';
import { ZipError, readZip } from '@/lib/sean/unzip';
import { refreshPnl } from './actions';
import {
  CONCURRENCY, MAX_UPLOAD_BYTES, baseName, fitWithin, hex, kindOf, needsReencode, runPool, toBase64,
} from './upload';
import {
  NOT_A_PICTURE, OFFLINE, READING, SAME_AS_ANOTHER, TOO_LARGE_PICTURE, WAITING, ZIP_EMPTY, ZIP_UNREADABLE,
  batchSummary, progressLine, readResponse, type UploadItem, type UploadOutcome, type UploadState,
} from './view';
import s from './trades.module.css';

type Bytes = Uint8Array<ArrayBuffer>;
type Job = { key: string; name: string; bytes: Bytes };

const ACCEPT = 'image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp,.zip,application/zip,application/x-zip-compressed';
const ADD_LABEL = 'Add Order Summary screenshots or a zip';
const RETRY_LABEL = 'Try the ones that failed again';
const CLEAR_LABEL = 'Clear this list';

/** Draws the picture onto a canvas and writes it back as a JPEG, long side at most MAX_SIDE_PX. */
async function reencode(bytes: Bytes, quality: number): Promise<Bytes> {
  const bitmap = await createImageBitmap(new Blob([bytes]));
  try {
    const { width, height } = fitWithin(bitmap.width, bitmap.height);
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('no 2d canvas');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, width, height);
    ctx.drawImage(bitmap, 0, 0, width, height);
    const blob = await new Promise<Blob | null>(done => canvas.toBlob(done, 'image/jpeg', quality));
    if (!blob) throw new Error('JPEG encode failed');
    return new Uint8Array(await blob.arrayBuffer());
  } finally {
    bitmap.close();
  }
}

/** A small JPEG goes as it is; anything else is re-encoded, a second time smaller if it must. */
async function prepare(bytes: Bytes): Promise<Bytes> {
  if (!needsReencode(bytes)) return bytes;
  const first = await reencode(bytes, 0.85);
  return first.length <= MAX_UPLOAD_BYTES ? first : reencode(bytes, 0.7);
}

async function send(image: string, sha256: string): Promise<UploadOutcome> {
  let res: Response;
  try {
    res = await fetch('/api/sean/orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image, sha256 }),
    });
  } catch {
    return OFFLINE;
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  return readResponse(res.status, body);
}

/** One picture end to end. `seen` holds this batch's digests, so a picture picked twice is sent once. */
async function processJob(job: Job, seen: Set<string>): Promise<UploadOutcome> {
  let bytes: Bytes;
  try {
    bytes = await prepare(job.bytes);
  } catch {
    return NOT_A_PICTURE;
  }
  if (bytes.length > MAX_UPLOAD_BYTES) return TOO_LARGE_PICTURE;
  const sha = hex(await crypto.subtle.digest('SHA-256', bytes));
  if (seen.has(sha)) return SAME_AS_ANOTHER;
  seen.add(sha);
  return send(toBase64(bytes), sha);
}

const rejected = (key: string, name: string, o: UploadOutcome): UploadItem => ({ key, name, ...o });

/** Picked files -> pictures to read (zips opened in the browser) plus the files refused outright. */
async function expand(files: File[], batch: number): Promise<{ jobs: Job[]; rejects: UploadItem[] }> {
  const jobs: Job[] = [];
  const rejects: UploadItem[] = [];
  let n = 0;
  const key = () => `${batch}-${n++}`;
  for (const f of files) {
    const kind = kindOf(f.name, f.type);
    if (kind === 'image') {
      jobs.push({ key: key(), name: f.name, bytes: new Uint8Array(await f.arrayBuffer()) });
    } else if (kind === 'zip') {
      let pictures: Awaited<ReturnType<typeof readZip>>;
      try {
        // Phase 1's reader: skips folders and macOS litter, keeps only picture names, checks CRCs.
        pictures = await readZip(new Uint8Array(await f.arrayBuffer()), { accept: name => kindOf(name) === 'image' });
      } catch (e) {
        // ZipError messages are plain words ("This zip file is damaged."); anything else is generic.
        rejects.push(rejected(key(), f.name, e instanceof ZipError ? { ...ZIP_UNREADABLE, message: e.message } : ZIP_UNREADABLE));
        continue;
      }
      if (pictures.length === 0) rejects.push(rejected(key(), f.name, ZIP_EMPTY));
      for (const e of pictures) jobs.push({ key: key(), name: baseName(e.name), bytes: new Uint8Array(e.bytes) });
    } else {
      rejects.push(rejected(key(), f.name, NOT_A_PICTURE));
    }
  }
  return { jobs, rejects };
}

function StateIcon({ state }: { state: UploadState }) {
  switch (state) {
    case 'reading':
      return <LoaderCircle size={20} strokeWidth={1.75} className={s.spin} aria-hidden="true" />;
    case 'saved':
      return <CircleCheck size={20} strokeWidth={1.75} aria-hidden="true" />;
    case 'duplicate':
      return <CopyCheck size={20} strokeWidth={1.75} aria-hidden="true" />;
    case 'failed':
      return <CircleAlert size={20} strokeWidth={1.75} aria-hidden="true" />;
    default:
      return <CircleDashed size={20} strokeWidth={1.5} aria-hidden="true" />;
  }
}

/**
 * Trades' uploader: pick or drop Order Summary screenshots or the zip; three are read at a time,
 * each with its own status row. When a batch ends the page reloads its order list and the engine
 * is asked (best effort) to redo the daily profit and loss.
 */
export function Uploader() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const retryable = useRef(new Map<string, Job>());
  const batchNo = useRef(0);
  const [items, setItems] = useState<UploadItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const [summary, setSummary] = useState('');

  // Leaving mid-batch drops the pictures not yet read: ask first.
  useEffect(() => {
    if (!busy) return;
    const hold = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener('beforeunload', hold);
    return () => window.removeEventListener('beforeunload', hold);
  }, [busy]);

  const update = (key: string, patch: Partial<UploadItem>) =>
    setItems(prev => prev.map(it => (it.key === key ? { ...it, ...patch } : it)));

  async function run(jobs: Job[], refused: number) {
    const seen = new Set<string>();
    const tally = { saved: 0, duplicate: 0, failed: refused };
    await runPool(jobs, CONCURRENCY, async job => {
      update(job.key, { state: 'reading', message: READING, retry: false });
      let out: UploadOutcome;
      try {
        out = await processJob(job, seen);
      } catch {
        out = OFFLINE;
      }
      tally[out.state] += 1;
      if (out.state === 'failed' && out.retry) retryable.current.set(job.key, job);
      else retryable.current.delete(job.key);
      update(job.key, out);
    });
    setSummary(batchSummary(tally));
    setBusy(false);
    if (tally.saved > 0) {
      router.refresh();
      refreshPnl().catch(() => undefined);
    }
  }

  async function start(files: File[]) {
    if (busy || files.length === 0) return;
    setBusy(true);
    setSummary('');
    retryable.current.clear();
    batchNo.current += 1;
    try {
      const { jobs, rejects } = await expand(files, batchNo.current);
      setItems([
        ...jobs.map((j): UploadItem => ({ key: j.key, name: j.name, state: 'waiting', message: WAITING, retry: false })),
        ...rejects,
      ]);
      await run(jobs, rejects.length);
    } catch {
      setSummary("Those files couldn't be opened. Try picking them again.");
      setBusy(false);
    }
  }

  async function retry() {
    const jobs = [...retryable.current.values()];
    if (busy || jobs.length === 0) return;
    setBusy(true);
    setSummary('');
    for (const j of jobs) update(j.key, { state: 'waiting', message: WAITING, retry: false });
    await run(jobs, 0);
  }

  function clear() {
    retryable.current.clear();
    setItems([]);
    setSummary('');
  }

  function onPick(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    e.target.value = '';
    void start(files);
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setOver(false);
    void start(Array.from(e.dataTransfer.files));
  }

  const canRetry = !busy && items.some(i => i.state === 'failed' && i.retry);
  const status = busy ? progressLine(items) : summary;

  return (
    <div className={s.uploader}>
      <div
        className={`${s.drop} ${over ? s.dropOver : ''}`}
        onDragOver={e => { e.preventDefault(); if (!busy) setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
      >
        <button type="button" className={`icon-btn ${s.add}`} disabled={busy}
          onClick={() => input.current?.click()} aria-label={ADD_LABEL} data-tip={ADD_LABEL}>
          {busy
            ? <LoaderCircle size={24} strokeWidth={1.75} className={s.spin} />
            : <ImagePlus size={24} strokeWidth={1.75} />}
        </button>
        <div className={s.dropText}>
          <p className={s.dropLead}>Drop the screenshots here, or the whole zip.</p>
          <p className={s.dropHint}>As many as you like. Sean reads each one, keeps the numbers and throws the picture away.</p>
        </div>
        <input ref={input} type="file" multiple accept={ACCEPT} className={s.sr}
          tabIndex={-1} aria-hidden="true" onChange={onPick} />
      </div>

      {(status || items.length > 0) && (
        <div className={s.bar}>
          <p className={s.progress} role="status" aria-live="polite">{status}</p>
          <div className={s.barActions}>
            {canRetry && (
              <button type="button" className="icon-btn sm" onClick={() => void retry()}
                aria-label={RETRY_LABEL} data-tip={RETRY_LABEL}>
                <RotateCcw size={18} strokeWidth={1.5} />
              </button>
            )}
            {!busy && items.length > 0 && (
              <button type="button" className="icon-btn sm" onClick={clear}
                aria-label={CLEAR_LABEL} data-tip={CLEAR_LABEL}>
                <ListX size={18} strokeWidth={1.5} />
              </button>
            )}
          </div>
        </div>
      )}

      {items.length > 0 && (
        <ul className={s.items}>
          {items.map(it => (
            <li key={it.key} className={`${s.item} ${it.state === 'failed' ? s.failed : ''}`}>
              <span className={s.itemIcon}><StateIcon state={it.state} /></span>
              <span className={s.itemName}>{it.name}</span>
              <span className={s.itemMsg}>{it.message}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```
**Impact:** client bundle pulls `lib/sean/unzip.ts` (Phase 1, browser-safe) and `view.ts`/`upload.ts` (pure; `view.ts` only `import type`s from `data.ts`, so no DB code reaches the browser).
**Retry (plan Decisions):** Phase 1's live run saw a transient transport failure before a retry
succeeded. Every failure worth another try is marked `retry: true` by `readResponse` — offline,
400, 502 (the reader unreachable, timed out, or it did not see the picture: Phase 1's
`token_floor`/`timeout`/`transport`), 504 and any other 5xx — and the "Try the ones that failed
again" icon button re-sends exactly those files (their bytes are kept in `retryable`), as many
times as the owner presses it. A 422 (a true refusal: not a receipt, not filled, or still
unreadable after Phase 1's own repair) is not offered again; re-uploading the file is.

### Step 15: Two-step delete button
**File:** `web/app/sean/trades/DeleteOrder.tsx` (new)
**Code:**
```tsx
'use client';

import { Check, LoaderCircle, Trash2, X } from 'lucide-react';
import { useActionState, useState } from 'react';
import { deleteOrder } from './actions';
import { IDLE } from './view';
import s from './trades.module.css';

/** Trash, then a coral check to confirm (or X to keep it). Labels name the order in plain words. */
export function DeleteOrder({ id, label, confirmLabel }: { id: number; label: string; confirmLabel: string }) {
  const [state, action, pending] = useActionState(deleteOrder, IDLE);
  const [asking, setAsking] = useState(false);

  return (
    <div className={s.del}>
      {asking ? (
        <form action={action} className={s.delForm}>
          <input type="hidden" name="id" value={id} />
          <button type="button" className="icon-btn sm" disabled={pending} onClick={() => setAsking(false)}
            aria-label="Keep it" data-tip="Keep it">
            <X size={18} strokeWidth={1.5} />
          </button>
          <button type="submit" className={`icon-btn sm ${s.confirm}`} disabled={pending}
            aria-label={confirmLabel} data-tip={confirmLabel}>
            {pending
              ? <LoaderCircle size={18} strokeWidth={1.75} className={s.spin} />
              : <Check size={18} strokeWidth={1.75} />}
          </button>
        </form>
      ) : (
        <button type="button" className="icon-btn sm" onClick={() => setAsking(true)} aria-label={label} data-tip={label}>
          <Trash2 size={18} strokeWidth={1.5} />
        </button>
      )}
      {state.tone === 'error' && <span className={s.rowError} role="status">{state.message}</span>}
    </div>
  );
}
```

### Step 16: The Trades page
**File:** `web/app/sean/trades/page.tsx` (new)
**Code:**
```tsx
import type { Metadata } from 'next';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { orders } from '@/lib/sean/data';
import { requireSean } from '@/lib/sean/gate';
import { DeleteOrder } from './DeleteOrder';
import { Uploader } from './Uploader';
import { ORDERS_EMPTY, ORDERS_UNREADABLE, orderCount, orderItem, ordersCaption, type OrderItem } from './view';
import s from './trades.module.css';

export const metadata: Metadata = { title: 'Trades' };

// Reads Neon on every visit: never prerendered.
export const dynamic = 'force-dynamic';

function OrderList({ items }: { items: OrderItem[] }) {
  return (
    <div className={s.orders}>
      <div className={`${s.head} desk-only`} aria-hidden="true">
        <span>When</span>
        <span>Order</span>
        <span>Shares and price</span>
        <span>Fees</span>
        <span className={s.right}>Total</span>
        <span />
      </div>
      <ul className={s.list}>
        {items.map(o => (
          <li key={o.id} className={s.order}>
            <span className={`num ${s.when}`}>{o.when}</span>
            <span className={s.what}>
              <span className={`${s.side} ${o.side === 'sell' ? s.sold : ''}`}>{o.sideLabel}</span>
              <span className={`num ${s.symbol}`}>{o.symbol}</span>
            </span>
            <span className={`num ${s.detail}`}>{o.detail}</span>
            <span className={`num ${s.fees}`} data-tip={o.feesTip} tabIndex={0}>{o.fees}</span>
            <span className={`num ${s.total}`}>
              <span>{o.total}</span>
              <span className={s.totalWord}>{o.totalWord}</span>
              {o.profit && <span className={`${s.profit} ${o.profit.tone}`}>{o.profit.text}</span>}
            </span>
            <DeleteOrder id={o.id} label={o.deleteLabel} confirmLabel={o.confirmLabel} />
          </li>
        ))}
      </ul>
    </div>
  );
}

export default async function TradesPage() {
  await requireSean('/sean/trades');
  const rows = await orders();

  return (
    <>
      <PageHeader
        eyebrow="Trades"
        title="Your Gotrade orders"
        lede="Every buy and sell you have made on Gotrade, read from its Order Summary screenshot. Add new ones whenever you trade."
      />
      <div className={s.page}>
        <Section
          bg="lav"
          eyebrow="Add receipts"
          title="Hand Sean your screenshots"
          caption="Open an order in Gotrade, screenshot its Order Summary and drop it here. Sending the same one twice is fine: Sean notices and keeps one."
        >
          <Uploader />
        </Section>

        {rows === null ? (
          <Section eyebrow="Orders" title="Everything you have traded">
            <p className={s.empty}>{ORDERS_UNREADABLE}</p>
          </Section>
        ) : (
          <Section eyebrow={orderCount(rows.length)} title="Everything you have traded" caption={ordersCaption(rows)}>
            {rows.length === 0 ? <p className={s.empty}>{ORDERS_EMPTY}</p> : <OrderList items={rows.map(orderItem)} />}
          </Section>
        )}
      </div>
    </>
  );
}
```

### Step 17: Trades styles
**File:** `web/app/sean/trades/trades.module.css` (new)
**Code:**
```css
/* Trades: a drop zone with per-picture status rows, then the order list on hairlines. */
.page { display: flex; flex-direction: column; gap: 12px; }

/* ---- Uploader -------------------------------------------------------------------------- */
.uploader { display: flex; flex-direction: column; gap: 12px; }

.drop {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 22px 24px;
  border-radius: 28px;
  border: 1.5px dashed var(--outline);
  background: transparent;
  transition: background 0.12s, border-color 0.12s;
}
.dropOver { border-color: var(--coral); background: var(--sheet); }

.add { width: 64px; height: 64px; border: 0; background: var(--coral); color: var(--on-coral); }
.add:hover { background: var(--coral); filter: brightness(0.95); }
.add:disabled { cursor: progress; }

.dropText { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.dropLead { font-size: 19px; line-height: 1.35; }
.dropHint { font-size: 15px; line-height: 1.45; color: var(--ink-2); }

.bar { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 44px; }
.progress { font-size: 15px; line-height: 1.45; color: var(--ink-2); padding: 0 8px; }
.barActions { display: flex; gap: 8px; flex: none; }

.items {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  max-height: 440px;
  overflow-y: auto;
  border-radius: 24px;
  background: var(--sheet);
}
.item {
  display: grid;
  grid-template-columns: 28px minmax(0, 0.9fr) minmax(0, 1.6fr);
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  border-bottom: 1px solid var(--hair);
  font-size: 15px;
}
.item:last-child { border-bottom: 0; }
.itemIcon { display: flex; color: var(--ink-2); }
.itemName { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--ink-2); }
.itemMsg { line-height: 1.4; color: var(--ink); }
/* Coral, not red: red means a loss here. A failed read is something to act on. */
.failed .itemIcon { color: var(--coral); }

.spin { animation: spin 0.9s linear infinite; }

/* ---- Orders ---------------------------------------------------------------------------- */
.orders { display: flex; flex-direction: column; }
.list { list-style: none; margin: 0; padding: 0; }

.head, .order {
  display: grid;
  grid-template-columns: 170px minmax(130px, 0.9fr) minmax(200px, 1.4fr) 110px 150px 100px;
  align-items: center;
  gap: 16px;
}
.head {
  padding: 0 8px 10px;
  font-size: 13px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-3);
  border-bottom: 1px solid var(--hair);
}
.right { text-align: right; }
.order { padding: 14px 8px; border-bottom: 1px solid var(--hair); }
.order:last-child { border-bottom: 0; }

.when { font-size: 15px; color: var(--ink-2); }
.what { display: flex; align-items: center; gap: 10px; min-width: 0; }
.side {
  height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--chip);
  display: inline-flex;
  align-items: center;
  font-size: 13.5px;
}
.sold { background: var(--butter); }
.symbol { font-size: 20px; font-weight: 500; letter-spacing: 0.02em; }
.detail { font-size: 15.5px; overflow-wrap: anywhere; }
.fees { justify-self: start; font-size: 15px; color: var(--ink-2); cursor: help; }
.total { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; font-size: 17px; text-align: right; }
.totalWord { font-size: 13px; color: var(--ink-3); }
.profit { font-size: 13.5px; }

.del { position: relative; display: flex; justify-content: flex-end; }
.delForm { display: flex; gap: 6px; }
.confirm { border: 0; background: var(--coral); color: var(--on-coral); }
.confirm:hover { background: var(--coral); filter: brightness(0.95); }
.rowError {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  font-size: 13px;
  white-space: nowrap;
  color: var(--ink);
}

.empty { font-size: 16px; color: var(--ink-2); }

.sr {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden;
  clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
}

@media (max-width: 1023.98px) {
  .drop { flex-direction: column; align-items: flex-start; padding: 20px; }
  .item { grid-template-columns: 24px minmax(0, 1fr); padding: 12px 16px; }
  .itemMsg { grid-column: 2; }
  .order {
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-areas:
      'what total'
      'detail total'
      'when del'
      'fees del';
    row-gap: 4px;
    padding: 16px 4px;
  }
  .what { grid-area: what; }
  .detail { grid-area: detail; }
  .when { grid-area: when; }
  .fees { grid-area: fees; }
  .total { grid-area: total; }
  .del { grid-area: del; align-self: end; }
}
```

### Step 18: Vercel environment for the vision call
**File:** none (Vercel project `seer`, linked through `VERCEL_ORG_ID`/`VERCEL_PROJECT_ID` in `/home/miftah/seer/web/.env.local`; `.vercel/` does not exist and is gitignored)
**Change:** add the three variables to production and preview when `vercel env ls` lacks them.
Values come from `.env.local` through stdin; nothing prints a value (`vercel env ls` shows a
prefix of Config values, so only the first column is kept). `LLM_API_KEY` is stored sensitive.
As of 2026-10-07 the project has none of the three (verified while planning: names present are
`BLOB_*`, `ALLOWED_EMAIL`, `AUTH_*`, `DATABASE_URL`).
**Code:**
```bash
cd /home/miftah/.worktrees/seer/sean-gotrade-tracker/web
ENVF=/home/miftah/seer/web/.env.local
get() { grep -E "^$1=" "$ENVF" | head -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'; }
export VERCEL_ORG_ID="$(get VERCEL_ORG_ID)" VERCEL_PROJECT_ID="$(get VERCEL_PROJECT_ID)"
TOKEN="$(get VERCEL_TOKEN)"

for target in production preview; do
  names="$(vercel env ls "$target" --token "$TOKEN" --non-interactive 2>/dev/null | awk '{print $1}')"
  for name in LLM_API_KEY LLM_VISION_BASE_URL LLM_VISION_MODEL; do
    if printf '%s\n' "$names" | grep -qx "$name"; then
      echo "$name ($target): already set"
      continue
    fi
    kind=--no-sensitive; [ "$name" = LLM_API_KEY ] && kind=--sensitive
    if get "$name" | tr -d '\n' | vercel env add "$name" "$target" "$kind" --yes --non-interactive --token "$TOKEN" >/dev/null 2>&1; then
      echo "$name ($target): added"
    else
      echo "$name ($target): FAILED to add"
    fi
  done
done

# Names only, to confirm:
vercel env ls --token "$TOKEN" --non-interactive 2>/dev/null | awk '{print $1}' | grep -E '^LLM_'
```
**Impact:** the next production/preview deployment has the vision keys. Existing deployments
are not changed (env applies at build/deploy). If `vercel env add ... preview` asks for a
branch despite `--yes`, it applies to all preview branches, which is what is wanted.

## Verification

**Build:**
```bash
cd /home/miftah/.worktrees/seer/sean-gotrade-tracker/web
npx tsc --noEmit && npx next build
```
**Tests:**
```bash
cd /home/miftah/.worktrees/seer/sean-gotrade-tracker/web
npx vitest run
npx vitest run app/sean/trades   # this phase's 2 files
```
**Manual check** (owner account, `npm run dev`, needs migration 015 on the database `DATABASE_URL` points at — `npm run db:migrate` applies it; it is additive, `IF NOT EXISTS`):
1. On `/` at ≥1024 px the rail foot shows Wallet above Telescope; hover shows "Sean, your real trades"; click opens `/sean` with the Sean rail (Overview active). At 390 px the header shows Wallet beside Sign out (owner only); tapping it opens `/sean` with Sean's top bar.
2. `/sean/trades`: pick `/home/miftah/seer/gotrade_order_summary_screenshots.zip` — 30 rows appear "Waiting its turn.", three at a time turn to "Reading the receipt…", each ends saved with a plain line (`PLTR: bought 5.38 shares for $709.44 on Jun 10, 2025.`); the list below fills newest first after the batch.
3. Pick the zip again: every row ends "Already saved. …"; the summary says "Done: 30 already here."
4. Trash one order -> X/check appear -> check removes the row.
5. As a different allowed account (or signed in without the owner email): `/sean`, `/sean/trades` give 404; `curl -X POST localhost:3000/api/sean/orders -d '{}'` (no session) gives 404 with an empty body.
6. Below 1024 px: Sean's top bar shows; the drop zone stacks; order rows reflow to two columns.

**Exit criteria:** `tsc`, `vitest` (including `app/sean/trades/view.test.ts` and `upload.test.ts`) and `next build` are green; the owner sees the Sean button above Sera on desktop and a Sean button in the page header on a phone, and the three tabs; a file that failed for a reader or network reason can be sent again with the retry button; images or the zip upload with per-file status three at a time; duplicates report as already saved; delete works; a non-owner gets 404 on `/sean/*` and `/api/sean/orders`; `vercel env ls` lists `LLM_API_KEY`, `LLM_VISION_BASE_URL`, `LLM_VISION_MODEL` for production and preview.

## Handoffs

- **Phase 1 (R3):** reconciled — this plan calls `readOrder(visionDeps(cfg), image)` with Phase 1's own 55 s budget, maps `isReaderDown(code)` to 502 and the rest to 422 with `out.message`, relies on `toOrder` for the Filled check, and opens zips with `readZip(bytes, { accept })`.
- **Phase 3 (R2):** replaces `web/app/sean/page.tsx` wholesale; reads orders through `ledgerOrders()` from `data.ts` and keeps its own `equity()`/`marks()` in a new `web/lib/sean/overviewData.ts` (never edits `data.ts`).
- **Phase 4 (R2):** `.github/workflows/sean.yml` must accept `workflow_dispatch` with **no required inputs** on `main`; `dispatchSeanMarks()` sends `{ ref: 'main' }` only.
- **Phase 5 (R4):** feeds `planOpen` in `web/app/sean/layout.tsx` (currently the literal `0`); adds the coral dot inside the Sean `<Link>` (class `s.sean`, `position: relative`) in both `Nav.tsx` (rail) and `AppHeader.tsx` (phone), and passes the count from `web/app/(app)/layout.tsx`; replaces `web/app/sean/plan/page.tsx`; reads orders through `ledgerOrders()` and keeps its own reads in `web/lib/sean/planData.ts`. `isSeanCaller()` from `lib/sean/gate.ts` is the gate for Phase 5's server actions.
- **Not in any phase (noted for the owner/reconciler):** the Vercel project has no `GITHUB_DISPATCH_TOKEN`, so `dispatchRepick` (Sera) and `dispatchSeanMarks` (Sean) are skipped in production and the nightly run picks changes up. Adding that token is outside R1/R3.
- **Mobile reach (reconciled):** the mobile tab bar stays the fixed 4-column pill; the owner reaches Sean on the phone through the header button of Step 3b. Sera stays desktop-only, as today.
- **Not in any phase:** `components/sera/PageHeader.tsx`'s sign-out returns to `/signin?next=%2Fsera`, so signing out from a Sean page returns to Sera after sign-in. Cosmetic; changing a Sera component is not this phase's.
- **Production database:** migration 015 must be applied to Neon before the first production upload (the engine's `migrate` in nightly/`sean.yml` does it, or `npm run db:migrate`). Until then the route answers 500 "couldn't be saved" and the Trades list says the orders can't be read.

## Rollback

Revert this phase's commit: Nav, `AppHeader`, `(app)/layout.tsx` and all new files go; nothing else imports
them (Phases 3 and 5 build on top, so revert those first). The Vercel variables are harmless if
left; to remove them: `vercel env rm LLM_API_KEY production --yes --token "$TOKEN"` (and the same
for each name and target).
