> Adopted from `SEAN_GOTRADE_TRACKER_PLAN.md` phase 1. Source: `.workflows/plan/sean-gotrade-tracker/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: Sean core: schema, screenshot reader, ledger

**Plan set:** `SEAN_GOTRADE_TRACKER_PLAN.md`
**Analysis:** `20261007-222658-S3AN_code_analyzer.md`
**Satisfies:** R2, R3 (R2: the ledger that the P&L graph stands on; R3: the glm-4.6v screenshot reader and the zip reader the upload uses)
**Depends on:** none
**Difficulty:** HARD
**Package:** `web/lib/sean` (plus `db/migrations`)

---

## Goal

After this phase the repo has Sean's tables (`015_sean.sql`, contract A verbatim) and a pure, fully
tested core under `web/lib/sean/`: a glm-4.6v client that reads one Gotrade Order Summary screenshot
into a checked `SeanOrder` (run-insights' measured transport, a text-aware token floor, one
image-carrying repair), a browser zip reader, and the TS ledger (contract B) with a shared fixture
the engine's Python ledger will be tested against. Nothing user-visible changes: no page, route or
engine code imports these modules yet.

**Verified while planning, not just designed.** Every code block below was written to a scratch
copy of `web/` (same `tsconfig.json`, main's `node_modules`) and checked: `tsc --noEmit` clean,
`vitest run lib/sean` 92/92 green, the migration applied on top of 001-014 (twice, idempotent) in a
throwaway schema on the local `postgres:16`, `toOrder` accepted all 30 hand-transcribed receipts in
`screenshots_truth.json`, and **the live smoke script read all 30 real screenshots from the owner's
zip with glm-4.6v, 30/30 matching the truth file on the first try** (no repair needed;
prompt_tokens 2,351 each against a floor of 1,141; 4.7-10.5 s per receipt).

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.

**Creates:**

- `db/migrations/015_sean.sql` — tables `sean_orders`, `sean_link`, `sean_reminder_marks`, `sean_marks`, `sean_equity`, index `sean_orders_executed_at` (contract A, byte-for-byte, plus a header comment).
- `web/lib/sean/types.ts` — `OrderSide`, `SeanFill`, `SeanOrder`, `RawFill`, `RawReceipt`.
- `web/lib/sean/money.ts` — `asText`, `roundHalfUp(x, dp)`, `cents`, `fixed(x, dp)`, `UsdParts`, `parseUsdParts`, `parseUsd`, `parseShares`, `parseReceiptDate(date, time)`.
- `web/lib/sean/extractJson.ts` — `extractJsonObject` (verbatim port).
- `web/lib/sean/prompt.ts` — `VisionContentPart`, `ORDER_SYSTEM_PROMPT`, `ORDER_SHAPE`, `jpegDataUri`, `buildOrderUserContent(imageB64)`, `buildRepairNote(issues)`.
- `web/lib/sean/vision.ts` — `VisionConfig`, `visionConfigFromEnv(env = process.env): VisionConfig | null`, `TOKEN_FLOOR_PER_IMAGE = 150`, `FLOOR_CHARS_PER_TOKEN = 3`, `MAX_TOKENS`, `tokenFloor`, `VisionTokenFloorError(promptTokens, floor, imageCount)`, `VisionTransportError(message, detail)`, `VisionResult` (`{text, promptTokens, completionTokens, floor, finishReason, raw}`), `callVisionWithFetch`, `readOrderWithFetch(fetchImpl, imageB64, cfg, {timeoutMs})`, `repairOrderWithFetch(fetchImpl, imageB64, cfg, {malformedText, issues}, {timeoutMs})`.
- `web/lib/sean/order.ts` — `toOrder(raw: unknown): ToOrderResult`, `ToOrderResult = {ok:true, order} | {ok:false, kind:'not_order'|'not_filled'|'unreadable', issues: string[]}`, `OrderRefusal`, `sideOf`, tolerance constants.
- `web/lib/sean/readOrder.ts` — `readOrder(deps, imageB64, budgetMs = READ_BUDGET_MS): Promise<ReadOrderOutcome>`, `visionDeps(cfg, fetchImpl?)`, `ReadOrderDeps`, `ReadOrderCode`, `READ_MESSAGES`, `isReaderDown(code)`, `ReadOrderOutcome`, `READ_BUDGET_MS = 55_000`, `PRIMARY_TIMEOUT_MS`, `REPAIR_TIMEOUT_MS`, `MIN_REPAIR_BUDGET_MS`.
- `web/lib/sean/ledger.ts` — `LedgerOrder`, `Close`, `DUST_SHARES`, `Holding`, `LedgerBook`, `PnlPoint`, `orderSession(executedAt)`, `buildLedger(orders, through?)`, `pnlSeries(orders, closes, dates)`, `pnlAt(orders, closes, date)`.
- `web/lib/sean/unzip.ts` — `ZipError`, `ZipEntry = {name, bytes}`, `InflateRaw`, `inflateRawWeb`, `IMAGE_NAME`, `baseName`, `isJunkEntry`, `crc32`, `readZip(input, {inflateRaw?, accept?})`.
- `web/lib/sean/fixtures/ledger.json` (shared with Phase 4), `web/lib/sean/fixtures/receipts.json`.
- Tests: `web/lib/sean/{money,extractJson,vision,order,readOrder,ledger,unzip}.test.ts`.
- `web/scripts/sean-vision-smoke.mjs` (live, never in CI).

**Signature changes:** none (all new).

**Requires (from earlier phases):** none. Reads the existing `web/lib/sera/gotrade-symbol.ts` `normalizeSymbol` (unchanged) and the existing `strategies` table (FK from `sean_link`).

**Leaves alone (owned by others):** every page, route, component, `Nav`, `web/lib/sean/{gate,data,reminders}.ts` (Phases 2, 3, 5); `web/package.json` (no new dependency); all of `engine/` and `.github/` (Phases 4, 6, 7).

### How later phases call this phase (exact, for the reconciler)

Phase 2's route (contract C). A sketch of the call pattern only; Phase 2 owns and writes the real route:

````ts
import { readOrder, visionDeps, isReaderDown } from '@/lib/sean/readOrder';
import { visionConfigFromEnv } from '@/lib/sean/vision';

const cfg = visionConfigFromEnv();             // null when a LLM_* var is missing or is the /api/anthropic URL
if (cfg === null) return 502 { error: 'The reader is not set up.' }
const out = await readOrder(visionDeps(cfg), imageB64);   // never throws for a model problem; budget 55 s
if (!out.ok) {
  console.error(out.code, out.detail);          // detail is for logs only
  return isReaderDown(out.code) ? 502 { error: out.message } : 422 { error: out.message };
}
// INSERT out.order.* into sean_orders; raw = out.raw (the model's JSON object); fills = out.order.fills
````

`out.order` field -> column: `side`, `orderType`->`order_type`, `status`, `symbol`, `executedAt`->`executed_at`, `price`, `shares`, `amountUsd`->`amount_usd`, `tradingFeeUsd`, `regulatoryFeeUsd`, `ppnUsd`, `totalUsd`, `netProfitUsd`, `fills` (JSON), plus `out.raw` -> `raw`. `toOrder` already refuses every status other than `Filled` (`code: 'not_filled'`, HTTP 422), so the route needs no status check of its own.

Phase 2's uploader (browser): `readZip(new Uint8Array(await file.arrayBuffer()), { accept: name => IMAGE_NAME.test(name) })` returns `{ name, bytes }[]` (default inflater = `DecompressionStream('deflate-raw')`; the owner's real zip is all *stored* entries, so it never even inflates); `baseName(e.name)` for display; failures throw `ZipError` with a plain-words `message`.

Phase 3: `buildLedger(orders: LedgerOrder[], through?)`, `pnlSeries(orders, closes: Close[], dates)`, `pnlAt(orders, closes, date)`. A `LedgerOrder` is a `SeanOrder` subset **plus `id: number`** (ties at equal timestamps replay by id), so the page maps its DB rows as `{ id, side, symbol, executedAt, price, shares, totalUsd, tradingFeeUsd, regulatoryFeeUsd, ppnUsd }`. `Close = { symbol, date, close }` (a flat array, not a map). `PnlPoint = { date, valueUsd, costUsd, realizedUsd, unrealizedUsd, pnlUsd, feesUsd }`, every figure already rounded to cents. `Holding = { symbol, shares, costUsd, avgPrice, lastOrderPrice }`, open positions only, sorted by symbol.

Phase 4: `web/lib/sean/fixtures/ledger.json` uses exactly the schema Phase 4's plan asked for — `orders[]` with `sean_orders` column names (`id` integer, `executed_at` ISO with offset, every number a string), `closes` as `{ SYMBOL: [{date, close}] }`, `expected.positions[] = {symbol, shares (9 dp), cost_usd}`, `expected.realized_usd`, `expected.fees_usd`, `expected.points[] = {date, value_usd, cost_usd, realized_usd, unrealized_usd, pnl_usd, fees_usd}` — plus one extra top-level key `sessions[] = {executed_at, session}` (New York trade dates, including a DST-day case) that Phase 4 may use or ignore.

### Contract B, made exact (both ledgers must do exactly this)

The plan index left five points open. Decided here, implemented in `ledger.ts`, and fixed in the fixture:

1. **Trade date** = the America/New_York calendar date of `executed_at` (a 03:30 WIB fill is the previous US session). Agrees with Phase 4's plan.
2. **Rounding** half up, ties away from zero (Python `ROUND_HALF_UP`), each output figure on its own from unrounded values. Agrees with Phase 4.
3. **Last order price** = the price of the latest order replayed so far in that symbol, used only when the symbol has no close dated on or before `d`. Agrees with Phase 4.
4. **Closing** = shares `< 1e-9` after an order -> shares = cost = 0, the symbol leaves the holdings. Agrees with Phase 4.
5. **Oversell — DIFFERS from Phase 4's assumption; Phase 4 must follow this.** `s = min(receipt shares, held)`; `proceeds = total_usd` when `s` is the whole receipt, else `total_usd * s / receipt shares` (multiply first, then divide — the order matters for Decimal exactness); `realized += proceeds - s * avg`. A sell with nothing held therefore adds **nothing** to realized (only its fees count). Phase 4 assumed the whole `total_usd` is proceeds and `avg = 0` when nothing is held, which books the full proceeds of any pre-Sean holding the owner sells as profit — e.g. selling the 10 NVDA bought in June 2025 without uploading that receipt would add ~$2,300 of invented "profit". The plan index's wording ("clamps to the held shares … the extra is ignored") reads as: the extra shares *and their money* are ignored. Fixture rows `id 5` (oversell) and `id 10` (sell of a never-bought stock) pin this down.

### Deviations from the plan index's Phase 1 text (decided here, with reasons)

- **The repair carries the image again (not text-only).** `ReadOrderDeps.callRepair(imageB64, {malformedText, issues}, {timeoutMs})`. run-insights' failure was a wrong *shape*; here the checks are arithmetic, so the likely failure is a misread digit, and a model that cannot see the picture can only "fix" it by inventing a number that adds up. Measured cost of one call: 5-10 s, so a second one fits the 55 s budget. The repair is floored like the first call.
- **Token floor is text-aware: `ceil(text chars / 3) + 150 per image`**, not run-insights F04's flat `500 x images`. See Step 6 for the measurement.
- **Trade-amount tolerance is `$0.01 + shares x $0.005`**, not "$0.02 or 0.1%". 0.1% of $1,832.90 is $1.83, which would let a transposed SPY price (`$610.695` for `$610.965`, $0.81 off) through; the new bound is what cent rounding of the amount plus price-display rounding can actually produce, and it still passes all 30 real receipts.
- **The model transcribes strings; code converts.** The JSON shape asks for the printed text (`"$1,063.886"`, `"+$0.10"`, `"October 07, 2026"`), and `money.ts` parses it. That is why `prompt.ts` has no conversion rules.
- **Shape adds `isOrderSummary` and `netProfitColor`** so "not a receipt" is a true answer (no repair) and an unsigned red Net Profit reads as a loss.
- **No `server-only` import anywhere in `lib/sean/`.** Seer web has no `server-only` package (nothing in `web/` imports it; it is a comment convention, see `lib/sera/gotrade.ts`). `vision.ts` takes its config as an argument and reads `process.env` only through `visionConfigFromEnv`, so vitest and the smoke script import it directly. The secret never reaches a client bundle because only Phase 2's route imports `readOrder`.
- **No zod.** Validation is hand-rolled in `order.ts`, matching Seer web's style (`lib/sera/gotrade-symbol.ts`); `web/package.json` is untouched.

## Files

| File | Action | What changes |
|---|---|---|
| `db/migrations/015_sean.sql` | create (line 1) | contract A verbatim + header comment |
| `web/lib/sean/types.ts` | create (line 1) | order types |
| `web/lib/sean/money.ts` | create (line 1) | receipt text -> numbers, half-up rounding |
| `web/lib/sean/money.test.ts` | create (line 1) | parsing and rounding cases |
| `web/lib/sean/extractJson.ts` | create (line 1) | verbatim port from run-insights |
| `web/lib/sean/extractJson.test.ts` | create (line 1) | fence / chatter / malformed |
| `web/lib/sean/prompt.ts` | create (line 1) | system prompt, JSON shape, user turn, repair note |
| `web/lib/sean/vision.ts` | create (line 1) | glm-4.6v client, token floor, errors, env config |
| `web/lib/sean/vision.test.ts` | create (line 1) | transport shape, floor, errors, config (fake fetch) |
| `web/lib/sean/order.ts` | create (line 1) | `toOrder` with arithmetic checks |
| `web/lib/sean/order.test.ts` | create (line 1) | fixture receipts + every refusal |
| `web/lib/sean/fixtures/receipts.json` | create (line 1) | 4 real receipts: raw model shape + expected order |
| `web/lib/sean/readOrder.ts` | create (line 1) | vision -> JSON -> toOrder -> one repair |
| `web/lib/sean/readOrder.test.ts` | create (line 1) | flow with injected calls and clock |
| `web/lib/sean/ledger.ts` | create (line 1) | contract B ledger |
| `web/lib/sean/ledger.test.ts` | create (line 1) | shared fixture + rules |
| `web/lib/sean/fixtures/ledger.json` | create (line 1) | shared TS/Python ledger fixture |
| `web/lib/sean/unzip.ts` | create (line 1) | browser zip reader |
| `web/lib/sean/unzip.test.ts` | create (line 1) | real-tool zip + edge cases |
| `web/scripts/sean-vision-smoke.mjs` | create (line 1) | live check against real screenshots (not CI) |

20 files, all new. No existing file is modified.

## Implementation Steps

Write the files exactly as below. Every import inside `web/lib/sean/` is relative (vitest has no
`@/` alias, plan invariant 7). The worktree has no `node_modules`; run `cd web && npm ci` first.

### Step 1: The migration
**File:** `db/migrations/015_sean.sql:1` (new)
**Change:** contract A byte-for-byte (as finalized in the plan index; the reconciler reworded only the `sean_link.since` column comment to "New York trade date"), after a header comment in the style of `014_unavailable.sql`. `sean_link.strategy_id` references `strategies(id)` (text PK, `001_init.sql:3`). Everything is `IF NOT EXISTS`, so both runners (`web/scripts/migrate.mjs`, `engine commands/migrate.py`) can apply it and a re-run is a no-op.
**Code:**
````sql
-- Seer schema v15: Sean, the owner's real Gotrade trades (owner, 2026-10-07).
--
-- Everything Seer stored before this was simulated: paper fills priced at an assumed 0.1% cost.
-- The owner trades for real on Gotrade, following RAW, and every order leaves an "Order Summary"
-- receipt. Sean reads those screenshots (glm-4.6v, web/lib/sean/readOrder.ts), keeps one row per
-- order here, marks the holdings to market every night (engine, `seer_engine sean marks`) and
-- shows the profit and loss; it can also follow one roster method and remind the owner what to
-- buy or sell.
--
-- sean_orders     one row per receipt. The screenshot itself is never stored: image_sha256 only
--                 dedupes a re-upload of the same file, and UNIQUE (symbol, side, executed_at,
--                 shares) dedupes the same order from two different screenshots. Fee columns hold
--                 magnitudes; the receipt's +/- sign only restates the side. executed_at is the
--                 receipt's Date + Time read as WIB. raw keeps the model's JSON for audit.
-- sean_link       the one roster method Sean follows, if any (singleton row, id = 1).
-- sean_reminder_marks  reminders the owner ticked off by hand.
-- sean_marks      daily closes for every symbol the owner has held (engine-written).
-- sean_equity     the owner's daily P&L series (engine-written, replaced whole on each run).
--
-- The ledger math behind sean_equity lives in two places that must agree:
-- web/lib/sean/ledger.ts and engine/src/seer_engine/sean/ledger.py, both tested against
-- web/lib/sean/fixtures/ledger.json. Additive only: nothing outside Sean reads these tables.
CREATE TABLE IF NOT EXISTS sean_orders (
  id                  bigserial PRIMARY KEY,
  image_sha256        text UNIQUE,                    -- hex SHA-256 of the uploaded bytes; NULL never written by the app today
  side                text NOT NULL CHECK (side IN ('buy', 'sell')),
  order_type          text NOT NULL,                  -- as printed: 'Market Buy', 'Limit Sell', ...
  status              text NOT NULL,                  -- as printed: 'Filled'
  symbol              text NOT NULL,
  executed_at         timestamptz NOT NULL,           -- receipt Date + Time, read as WIB (+07:00)
  price               numeric(18,6) NOT NULL,         -- 'Average price' or 'Execution price'
  shares              numeric(24,9) NOT NULL,
  amount_usd          numeric(14,2) NOT NULL,         -- 'Trade amount'
  trading_fee_usd     numeric(10,2) NOT NULL CHECK (trading_fee_usd >= 0),     -- magnitudes; the receipt's +/- sign is the side
  regulatory_fee_usd  numeric(10,2) NOT NULL CHECK (regulatory_fee_usd >= 0),
  ppn_usd             numeric(10,2) NOT NULL CHECK (ppn_usd >= 0),
  total_usd           numeric(14,2) NOT NULL,         -- buy: amount + fees; sell: amount - fees
  net_profit_usd      numeric(14,2),                  -- the sell receipt's 'Net Profit', NULL on buys
  fills               jsonb NOT NULL DEFAULT '[]',    -- [{shares, price}] partial-fill lines, [] when none printed
  raw                 jsonb,                          -- the model's JSON, kept for audit
  created_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (symbol, side, executed_at, shares)          -- same order from two different screenshots
);
CREATE INDEX IF NOT EXISTS sean_orders_executed_at ON sean_orders (executed_at);

-- One followed roster method at most (singleton row).
CREATE TABLE IF NOT EXISTS sean_link (
  id           smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  strategy_id  text NOT NULL REFERENCES strategies(id),
  since        date NOT NULL,                         -- orders whose New York trade date is on/after this belong to the plan
  budget_usd   numeric(14,2),                         -- owner's intended plan size; NULL = the plan's current value
  linked_at    timestamptz NOT NULL DEFAULT now()
);

-- A reminder the owner marked done by hand (uploaded orders clear reminders on their own).
CREATE TABLE IF NOT EXISTS sean_reminder_marks (
  strategy_id   text NOT NULL,
  session_date  date NOT NULL,                        -- the method's decision session
  symbol        text NOT NULL,
  action        text NOT NULL CHECK (action IN ('buy', 'sell')),
  marked_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (strategy_id, session_date, symbol, action)
);

-- Daily closes for every symbol the owner has held (written by the engine, Phase 4).
CREATE TABLE IF NOT EXISTS sean_marks (
  symbol  text NOT NULL,
  date    date NOT NULL,
  close   numeric(18,4) NOT NULL,
  PRIMARY KEY (symbol, date)
);

-- The owner's daily P&L series (written by the engine, Phase 4; read by the Overview, Phase 3).
CREATE TABLE IF NOT EXISTS sean_equity (
  date            date PRIMARY KEY,                   -- NYSE session
  value_usd       numeric(14,2) NOT NULL,             -- holdings marked at that session's close
  cost_usd        numeric(14,2) NOT NULL,             -- open cost basis (fees included)
  realized_usd    numeric(14,2) NOT NULL,             -- cumulative
  unrealized_usd  numeric(14,2) NOT NULL,             -- value - cost
  pnl_usd         numeric(14,2) NOT NULL,             -- realized + unrealized
  fees_usd        numeric(14,2) NOT NULL,             -- cumulative trading + regulatory + PPN
  computed_at     timestamptz NOT NULL DEFAULT now()
);
````
**Impact:** five new tables, nothing else reads them yet. `engine/tests/test_migrate.py::test_applies_all_then_nothing` picks the file up automatically (it compares against the directory listing), and every engine test using the `pg` fixture now applies it — a SQL error here fails engine CI, which is the "applies on a fresh DB" check.

### Step 2: Types
**File:** `web/lib/sean/types.ts:1` (new)
**Change:** the order type every phase shares, and the raw shape the model returns.
**Code:**
````ts
// Sean's shared types. No imports and no data access, so routes, client islands, tests and the
// live smoke script can all read this file.

export type OrderSide = 'buy' | 'sell';

/** One partial-fill line printed under "Average price": "· 0.38 shares   @ $131.47". */
export type SeanFill = { shares: number; price: number };

/**
 * One Gotrade order, as its Order Summary sheet printed it. Mirrors table sean_orders
 * (db/migrations/015_sean.sql). Money is US dollars, already rounded to cents; the three fee
 * fields are magnitudes, because the receipt's + / - sign only restates the side.
 */
export type SeanOrder = {
  side: OrderSide;
  /** As printed, spaces collapsed: 'Market Buy', 'Limit Sell'. */
  orderType: string;
  /** As printed: 'Filled' (toOrder accepts nothing else). */
  status: string;
  /** Canonical ticker, the way the engine stores it: 'PLTR', 'BRK.B'. */
  symbol: string;
  /** ISO 8601 with the WIB offset: '2026-10-07T21:55:00+07:00'. */
  executedAt: string;
  /** 'Average price' or 'Execution price', up to 6 decimals. */
  price: number;
  /** 'Filled shares', up to 9 decimals. */
  shares: number;
  /** 'Trade amount'. */
  amountUsd: number;
  tradingFeeUsd: number;
  regulatoryFeeUsd: number;
  ppnUsd: number;
  /** Buy: amount + fees. Sell: amount - fees. */
  totalUsd: number;
  /** The sell receipt's 'Net Profit' (Gotrade's own figure); null on buys. */
  netProfitUsd: number | null;
  /** Partial-fill lines, [] when none were printed. */
  fills: SeanFill[];
};

/** A partial-fill line as the model transcribes it: printed text, not numbers. */
export type RawFill = { shares: string | null; price: string | null };

/**
 * What the model is asked to return (prompt.ts ORDER_SHAPE). Every value is the printed text;
 * money.ts turns it into numbers and order.ts checks the arithmetic. toOrder accepts `unknown`,
 * so this type documents the shape and types the fixtures; it is not trusted.
 */
export type RawReceipt = {
  isOrderSummary: boolean | null;
  status: string | null;
  date: string | null;
  time: string | null;
  orderType: string | null;
  ticker: string | null;
  priceLabel: string | null;
  price: string | null;
  fills: RawFill[];
  filledShares: string | null;
  tradeAmount: string | null;
  tradingFee: string | null;
  regulatoryFee: string | null;
  ppn: string | null;
  total: string | null;
  netProfit: string | null;
  netProfitColor: 'green' | 'red' | null;
};
````
**Impact:** none.

### Step 3: Money parsing and rounding
**File:** `web/lib/sean/money.ts:1` (new)
**Change:** parse what the receipt prints; round half up the way Python's `ROUND_HALF_UP` does (the TS and Python ledgers must agree to the cent). `toPrecision(15)` first removes binary noise so `1.005` rounds to `1.01`.
**Code:**
````ts
// Turning the text printed on a Gotrade Order Summary into numbers, and rounding money the one
// way Sean rounds it. Pure: no imports, safe for tests, client islands and the smoke script.

/** Text the model returned for one field: trimmed with inner spaces collapsed, or null. */
export function asText(v: unknown): string | null {
  if (typeof v === 'number') return Number.isFinite(v) ? String(v) : null;
  if (typeof v !== 'string') return null;
  const s = v.replace(/\s+/g, ' ').trim();
  return s === '' ? null : s;
}

/**
 * Round half up (ties away from zero) to `dp` decimals -- Python's ROUND_HALF_UP, so the web
 * ledger and the engine ledger (engine/src/seer_engine/sean/ledger.py) round identically.
 * toPrecision(15) first drops binary noise (26.125 arrives as 26.124999999999996), which would
 * otherwise turn a tie into a round-down.
 */
export function roundHalfUp(x: number, dp: number): number {
  if (!Number.isFinite(x)) return x;
  const f = 10 ** dp;
  const scaled = Number((Math.abs(x) * f).toPrecision(15));
  const r = (Math.sign(x) * Math.floor(scaled + 0.5)) / f;
  return r === 0 ? 0 : r;
}

/** Dollars to cents, half up. */
export const cents = (x: number): number => roundHalfUp(x, 2);

/** Rounded and printed with exactly `dp` decimals: fixed(26.125, 2) === '26.13'. */
export function fixed(x: number, dp: number): string {
  return roundHalfUp(x, dp).toFixed(dp);
}

/** A dollar amount split into its printed sign and its size. */
export type UsdParts = { sign: '+' | '-' | null; magnitude: number };

const MINUS = new Set(['-', '−', '–']);
const USD = /^([+\-−–])?\s*(?:US)?\$?\s*([+\-−–])?\s*(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?$/;

/**
 * "$1,063.886" -> {sign: null, magnitude: 1063.886}; "+$0.10" -> {'+', 0.1}; "-$0.15" and
 * "$-0.15" -> {'-', 0.15}. A bare number (the model sometimes drops the $) is accepted too; the
 * arithmetic checks in order.ts catch a number read into the wrong field. Null when it is not money.
 */
export function parseUsdParts(v: unknown): UsdParts | null {
  const s = asText(v);
  if (s === null) return null;
  const m = USD.exec(s);
  if (!m) return null;
  const [, before, after, int, frac] = m;
  if (before && after) return null;
  const mark = before ?? after;
  const magnitude = Number(`${int.replace(/,/g, '')}.${frac ?? '0'}`);
  if (!Number.isFinite(magnitude)) return null;
  return { sign: mark === undefined ? null : MINUS.has(mark) ? '-' : '+', magnitude };
}

/** A dollar amount with its sign applied, or null. */
export function parseUsd(v: unknown): number | null {
  const p = parseUsdParts(v);
  if (p === null) return null;
  return p.sign === '-' && p.magnitude !== 0 ? -p.magnitude : p.magnitude;
}

const SHARES = /^(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,9}))?$/;

/**
 * "0.026224614" -> 0.026224614; "· 0.38 shares" -> 0.38; "5 shares" -> 5. Gotrade prints at most
 * 9 decimals, so a 10th means a misread and the answer is null.
 */
export function parseShares(v: unknown): number | null {
  const s0 = asText(v);
  if (s0 === null) return null;
  const s = s0
    .replace(/^[·•*]\s*/, '')
    .replace(/\s*shares?$/i, '')
    .trim();
  const m = SHARES.exec(s);
  if (!m) return null;
  const n = Number(`${m[1].replace(/,/g, '')}.${m[2] ?? '0'}`);
  return Number.isFinite(n) ? n : null;
}

const MONTHS = [
  'january', 'february', 'march', 'april', 'may', 'june',
  'july', 'august', 'september', 'october', 'november', 'december',
];
const DATE = /^([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})$/;
const TIME = /^(\d{1,2})[:.](\d{2})(?:[:.](\d{2}))?\s*([AaPp])?\.?\s*(?:[Mm]\.?)?\s*(WIB)?$/;

const pad = (n: number) => String(n).padStart(2, '0');

/**
 * The receipt's Date and Time lines -> one ISO timestamp in WIB.
 * ("October 07, 2026", "21:55 WIB") -> '2026-10-07T21:55:00+07:00'. Month names may be full or
 * abbreviated ("Oct", "Sept"); a 12-hour time with AM/PM is converted; a missing "WIB" is read as
 * WIB (Gotrade prints every time in WIB). Null for anything else, including an impossible date.
 */
export function parseReceiptDate(dateText: unknown, timeText: unknown): string | null {
  const d = asText(dateText);
  const t = asText(timeText);
  if (d === null || t === null) return null;
  const dm = DATE.exec(d);
  const tm = TIME.exec(t);
  if (!dm || !tm) return null;

  const word = dm[1].toLowerCase();
  if (word.length < 3) return null;
  const month = MONTHS.findIndex(name => name.startsWith(word));
  if (month < 0) return null;
  const day = Number(dm[2]);
  const year = Number(dm[3]);
  if (new Date(Date.UTC(year, month, day)).getUTCDate() !== day || day < 1) return null;

  let hour = Number(tm[1]);
  const minute = Number(tm[2]);
  const second = tm[3] === undefined ? 0 : Number(tm[3]);
  const meridiem = tm[4]?.toLowerCase();
  if (meridiem !== undefined) {
    if (hour < 1 || hour > 12) return null;
    hour = (hour % 12) + (meridiem === 'p' ? 12 : 0);
  }
  if (hour > 23 || minute > 59 || second > 59) return null;

  return `${year}-${pad(month + 1)}-${pad(day)}T${pad(hour)}:${pad(minute)}:${pad(second)}+07:00`;
}
````

**File:** `web/lib/sean/money.test.ts:1` (new)
**Code:**
````ts
import { describe, expect, it } from 'vitest';
import { asText, cents, fixed, parseReceiptDate, parseShares, parseUsd, parseUsdParts, roundHalfUp } from './money';

describe('roundHalfUp', () => {
  it('rounds ties away from zero, like Python ROUND_HALF_UP', () => {
    expect(roundHalfUp(26.125, 2)).toBe(26.13);
    expect(roundHalfUp(-26.125, 2)).toBe(-26.13);
    expect(roundHalfUp(0.005, 2)).toBe(0.01);
    expect(roundHalfUp(1.0049, 2)).toBe(1);
  });
  it('ignores binary noise that would turn a tie into a round-down', () => {
    expect(Math.round(1.005 * 100) / 100).toBe(1); // the naive way rounds this tie down
    expect(cents(1.005)).toBe(1.01);
    expect(cents(24.13 + 1.995)).toBe(26.13);
  });
  it('never returns negative zero', () => {
    expect(Object.is(roundHalfUp(-0.0001, 2), 0)).toBe(true);
  });
  it('keeps nine decimals for shares', () => {
    expect(roundHalfUp(0.0262246144, 9)).toBe(0.026224614);
    expect(roundHalfUp(0.0262246145, 9)).toBe(0.026224615);
  });
  it('prints fixed decimals', () => {
    expect(fixed(26.125, 2)).toBe('26.13');
    expect(fixed(1.5, 9)).toBe('1.500000000');
    expect(fixed(0, 2)).toBe('0.00');
  });
});

describe('asText', () => {
  it('trims, collapses spaces, and accepts finite numbers', () => {
    expect(asText('  Market   Buy ')).toBe('Market Buy');
    expect(asText(5.38)).toBe('5.38');
    expect(asText('')).toBeNull();
    expect(asText(Number.NaN)).toBeNull();
    expect(asText(null)).toBeNull();
    expect(asText({})).toBeNull();
  });
});

describe('parseUsd', () => {
  it('reads every money format the receipts print', () => {
    expect(parseUsd('$1,063.886')).toBe(1063.886);
    expect(parseUsd('$1,832.90')).toBe(1832.9);
    expect(parseUsd('$27.90')).toBe(27.9);
    expect(parseUsd('+$0.10')).toBe(0.1);
    expect(parseUsd('-$0.15')).toBe(-0.15);
    expect(parseUsd('−$0.15')).toBe(-0.15);
    expect(parseUsd('$-0.15')).toBe(-0.15);
    expect(parseUsd('+$0.00')).toBe(0);
    expect(parseUsd('$ 72.27')).toBe(72.27);
    expect(parseUsd('US$5')).toBe(5);
    expect(parseUsd('72.27')).toBe(72.27);
    expect(parseUsd(72.27)).toBe(72.27);
  });
  it('keeps the printed sign apart from the size', () => {
    expect(parseUsdParts('+$0.10')).toEqual({ sign: '+', magnitude: 0.1 });
    expect(parseUsdParts('-$0.15')).toEqual({ sign: '-', magnitude: 0.15 });
    expect(parseUsdParts('$22.31')).toEqual({ sign: null, magnitude: 22.31 });
  });
  it('refuses what is not money', () => {
    for (const bad of ['', 'Filled', '$', '$1,06.88', '+-$1', '-$-1', '1.2.3', '$12a', 'Rp 10.000']) {
      expect(parseUsd(bad), bad).toBeNull();
    }
    expect(parseUsd(null)).toBeNull();
    expect(parseUsd(undefined)).toBeNull();
  });
});

describe('parseShares', () => {
  it('reads share counts with up to nine decimals', () => {
    expect(parseShares('0.026224614')).toBe(0.026224614);
    expect(parseShares('7.084773035')).toBe(7.084773035);
    expect(parseShares('3')).toBe(3);
    expect(parseShares('1,000.5')).toBe(1000.5);
    expect(parseShares(5.38)).toBe(5.38);
  });
  it('reads a partial-fill line as printed', () => {
    expect(parseShares('· 0.38 shares')).toBe(0.38);
    expect(parseShares('5 shares')).toBe(5);
    expect(parseShares('1 share')).toBe(1);
  });
  it('refuses a tenth decimal, signs and words', () => {
    for (const bad of ['0.0262246141', '-1', '+1', 'five', '', '1e-7', '$5']) {
      expect(parseShares(bad), bad).toBeNull();
    }
  });
});

describe('parseReceiptDate', () => {
  it('turns the printed date and WIB time into one ISO timestamp', () => {
    expect(parseReceiptDate('October 07, 2026', '21:55 WIB')).toBe('2026-10-07T21:55:00+07:00');
    expect(parseReceiptDate('June 10, 2025', '21:34 WIB')).toBe('2025-06-10T21:34:00+07:00');
  });
  it('accepts abbreviated months, a missing comma or WIB, and dotted times', () => {
    expect(parseReceiptDate('Oct 7 2026', '21:55')).toBe('2026-10-07T21:55:00+07:00');
    expect(parseReceiptDate('Sept 1, 2026', '09.05 WIB')).toBe('2026-09-01T09:05:00+07:00');
  });
  it('converts a 12-hour time', () => {
    expect(parseReceiptDate('March 25, 2026', '8:30 PM')).toBe('2026-03-25T20:30:00+07:00');
    expect(parseReceiptDate('March 25, 2026', '12:15 AM')).toBe('2026-03-25T00:15:00+07:00');
    expect(parseReceiptDate('March 25, 2026', '12:15 PM')).toBe('2026-03-25T12:15:00+07:00');
  });
  it('refuses impossible dates, other time zones and junk', () => {
    expect(parseReceiptDate('February 30, 2026', '21:55 WIB')).toBeNull();
    expect(parseReceiptDate('October 07, 2026', '25:00 WIB')).toBeNull();
    expect(parseReceiptDate('October 07, 2026', '21:55 ET')).toBeNull();
    expect(parseReceiptDate('October 07, 2026', '21:55 PM')).toBeNull();
    expect(parseReceiptDate('Oc 07, 2026', '21:55 WIB')).toBeNull();
    expect(parseReceiptDate('2026-10-07', '21:55 WIB')).toBeNull();
    expect(parseReceiptDate(null, '21:55 WIB')).toBeNull();
    expect(parseReceiptDate('October 07, 2026', null)).toBeNull();
  });
});
````
**Impact:** none.

### Step 4: JSON extraction (verbatim port)
**File:** `web/lib/sean/extractJson.ts:1` (new)
**Change:** `~/run-insights/lib/llm/extractJson.ts`, unchanged in behaviour (semicolons for Seer's style).
**Code:**
````ts
/**
 * Pull a JSON object out of whatever the model actually said.
 *
 * Ported verbatim from ~/run-insights lib/llm/extractJson.ts, which is proven against real
 * glm-4.6v output: strip a ```json fence if there is one, then take the FIRST `{` to the LAST `}`.
 * Chatter before or after the object is dropped by construction; nested braces survive because
 * the slice is outermost-to-outermost. Returns null -- never throws -- for no braces, malformed
 * JSON, or a value that is not a plain object, so readOrder treats "no object" and "an object
 * that failed the checks" the same way: both are repairable.
 */

const FENCE_RE = /```(?:json)?\s*([\s\S]*?)```/;

export function extractJsonObject(text: string | null | undefined): unknown | null {
  if (!text) return null;
  let s = text.trim();

  const fence = s.match(FENCE_RE);
  if (fence?.[1]) s = fence[1].trim();

  const open = s.indexOf('{');
  const close = s.lastIndexOf('}');
  if (open === -1 || close === -1 || close < open) return null;

  try {
    const parsed: unknown = JSON.parse(s.slice(open, close + 1));
    return parsed !== null && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}
````

**File:** `web/lib/sean/extractJson.test.ts:1` (new)
**Code:**
````ts
import { describe, expect, it } from 'vitest';
import { extractJsonObject } from './extractJson';

describe('extractJsonObject', () => {
  it('reads a bare object', () => {
    expect(extractJsonObject('{"ticker":"MU"}')).toEqual({ ticker: 'MU' });
  });
  it('strips a ```json fence', () => {
    expect(extractJsonObject('```json\n{"ticker":"MU"}\n```')).toEqual({ ticker: 'MU' });
  });
  it('drops chatter before and after, keeping nested braces', () => {
    expect(extractJsonObject('Here it is: {"fills":[{"shares":"5"}]} Let me know!')).toEqual({
      fills: [{ shares: '5' }],
    });
  });
  it('returns null for nothing, malformed JSON, arrays and scalars', () => {
    expect(extractJsonObject('')).toBeNull();
    expect(extractJsonObject(null)).toBeNull();
    expect(extractJsonObject('no json here')).toBeNull();
    expect(extractJsonObject('{"ticker": "MU",}')).toBeNull();
    expect(extractJsonObject('[1, 2]')).toBeNull();
    expect(extractJsonObject('} {')).toBeNull();
  });
});
````
**Impact:** none.

### Step 5: The prompt
**File:** `web/lib/sean/prompt.ts:1` (new)
**Change:** run-insights' structure (numbered rules opening with "transcribe ONLY what is literally visible", labelled image, shape last, "Return ONLY a JSON object"), written for Gotrade's sheet as seen in the real screenshots: the white "Order Summary" card over a dimmed screen, a phone status-bar clock that is *not* the order time, "Average price" with "· 0.38 shares / @ $131.47" lines or "Execution price", signed fee rows, a green "Net Profit" on sells. Measured: 30/30 correct on the first try with exactly this text.
**Code:**
````ts
/**
 * The prompt that turns one Gotrade "Order Summary" screenshot into JSON.
 *
 * Built on the rules that measured best in ~/run-insights (lib/llm/prompts/extraction.ts): a
 * system prompt of numbered rules that opens with "transcribe ONLY what is literally visible",
 * one user turn with a labelled image followed by the exact JSON shape LAST, and "Return ONLY a
 * JSON object" at the end. Unlike run-insights, the model converts NOTHING here: every value is
 * the printed text, and money.ts parses it. Copying "$1,063.886" is what a vision model does
 * best; turning it into 1063.886 is code's job, where it can be tested.
 *
 * If you change ORDER_SYSTEM_PROMPT or ORDER_SHAPE, re-run the live smoke script against the real
 * receipts before shipping (web/scripts/sean-vision-smoke.mjs).
 */

type VisionTextPart = { type: 'text'; text: string };
type VisionImagePart = { type: 'image_url'; image_url: { url: string } };
export type VisionContentPart = VisionTextPart | VisionImagePart;

export const ORDER_SYSTEM_PROMPT = `You transcribe ONE screenshot of the Gotrade app's "Order Summary" sheet into JSON.

RULES -- these matter more than anything else:
1. Transcribe ONLY what is literally visible. Never infer, never compute, never fill a
   plausible value. If a field is not visible, use null.
2. Read ONLY the white "Order Summary" card. Ignore the phone's status bar (its clock is not
   the order time), the dimmed screen behind the card, and the "Got it" button.
3. Copy every money value EXACTLY as printed, as a string: keep the "$", the "+" or "-" sign
   when one is printed, the thousands commas and EVERY decimal digit. "$1,063.886" stays
   "$1,063.886"; "-$0.15" stays "-$0.15". Never round, never drop a digit, never add one.
4. Copy share counts EXACTLY as printed, as a string, with every decimal digit:
   "0.026224614" stays "0.026224614"; "5" stays "5".
5. Copy "Date" and "Time" exactly as printed: "October 07, 2026" and "21:55 WIB".
6. The price row is labelled either "Average price" or "Execution price". Put that label in
   "priceLabel" and its value in "price".
7. Under "Average price" the sheet may list partial fills, one line each, like
   "· 0.38 shares" on the left and "@ $131.47" on the right. Copy every such line, in order,
   into "fills" as {"shares": "0.38", "price": "$131.47"}. When no such lines are printed,
   "fills" is an empty array [].
8. "Trading fee", "Regulatory fee" and "PPN" are three separate rows. Copy each with its sign.
9. "Net Profit" is printed only on some sells, below "Total". Copy its value with its sign if
   one is printed, and put the colour of that value's text in "netProfitColor" ("green" or
   "red"). When there is no Net Profit row, both are null.
10. If the picture is not a Gotrade Order Summary sheet, set "isOrderSummary" to false and every
   other field to null (fills: []).

Return ONLY a JSON object. No markdown fences, no commentary, no text before or after the
JSON object.`;

export const ORDER_SHAPE = `{
  "isOrderSummary": boolean,
  "status": string|null,          // "Filled"
  "date": string|null,            // "October 07, 2026"
  "time": string|null,            // "21:55 WIB"
  "orderType": string|null,       // "Market Buy", "Market Sell", "Limit Buy", ...
  "ticker": string|null,          // "PLTR"
  "priceLabel": string|null,      // "Average price" or "Execution price"
  "price": string|null,           // "$131.47"
  "fills": [ { "shares": string, "price": string } ],   // [] when no partial-fill lines
  "filledShares": string|null,    // "5.38"
  "tradeAmount": string|null,     // "$707.31"
  "tradingFee": string|null,      // "+$0.00"
  "regulatoryFee": string|null,   // "+$2.13"
  "ppn": string|null,             // "+$0.00"
  "total": string|null,           // "$709.44"
  "netProfit": string|null,       // "$22.31", sells only
  "netProfitColor": "green"|"red"|null
}`;

/** `data:image/jpeg;base64,...` from bare base64 (a data: prefix already there is kept). */
export function jpegDataUri(imageB64: string): string {
  return imageB64.startsWith('data:') ? imageB64 : `data:image/jpeg;base64,${imageB64}`;
}

/** The user turn: the labelled image, then the request and the shape, last. */
export function buildOrderUserContent(imageB64: string): VisionContentPart[] {
  return [
    { type: 'text', text: 'IMAGE -- Gotrade Order Summary screenshot:' },
    { type: 'image_url', image_url: { url: jpegDataUri(imageB64) } },
    {
      type: 'text',
      text: `This is ONE Gotrade Order Summary screenshot.\n\nReturn one JSON object with exactly this shape:\n${ORDER_SHAPE}`,
    },
  ];
}

/**
 * The repair note, sent after the model's first reply in the SAME conversation, with the image
 * still in it (vision.ts repairOrderWithFetch re-sends the user turn above). Deliberately NOT
 * run-insights' text-only repair: there the measured failure was a wrong shape, here the likely
 * failure is a misread digit that the arithmetic checks caught, and a model that cannot see the
 * picture again can only "fix" that by inventing a number that adds up. One receipt costs ~2,400
 * prompt tokens and 5-10 s (measured); a made-up fee in the owner's ledger costs more.
 */
export function buildRepairNote(issues: string): string {
  return (
    'Your last reply did not match the required JSON shape, or its numbers do not add up the way ' +
    'a Gotrade Order Summary always does. Look at the screenshot again and reply with ONLY the ' +
    'corrected JSON object, in exactly the same shape. Re-read the values the problems below ' +
    'point at, digit by digit, and copy them exactly as printed. Never change a value just to ' +
    'make the numbers add up.\n\nProblems found:\n' +
    issues
  );
}
````
**Impact:** none. Changing `ORDER_SYSTEM_PROMPT` or `ORDER_SHAPE` changes the token floor (it counts the text) and must be re-checked with Step 11's script.

### Step 6: The vision client and the token floor
**File:** `web/lib/sean/vision.ts:1` (new)
**Change:** run-insights `lib/llm/vision.ts` transport, exactly: `POST {baseUrl}/chat/completions`, `Bearer`, `model`, `max_tokens`, `thinking: {type:'disabled'}`, no `response_format`/temperature/stream, `AbortSignal.timeout`, floor checked before `res.ok` and before any read of `choices`, missing `usage` = 0. Config is injected (`VisionConfig`) instead of read from a server env module.

**Choosing the floor (the brief asked for this to be justified).**
- run-insights F04: flat `500 x images`. Safe there only because its drop signature was measured with a short probe prompt (141 tokens).
- run-insights Nina: re-calibrated to **text-aware** `ceil(chars / 3) + 150 x images` after the flat 500 refused a delivered 612x862 photo. `prompt_tokens` counts the system prompt, so a long prompt plus a dropped image can clear a flat floor; and the per-image term only needs to be positive once the text is covered.
- Sean's prompt is ~3,000 characters, so Nina's form applies: floor = `ceil(2,973 / 3) + 150` = **1,141**. Measured on all 30 real receipts (739x1600, sent as is): **prompt_tokens = 2,351** every time, a 1,210-token margin. A dropped image loses the ~1,400 image tokens, leaving the text alone (fewer than the floor's pessimistic ~990 estimate), so it trips.
- The repair call carries the image, so it is floored too (its floor also counts the first reply and the issues, which are real prompt text).
**Code:**
````ts
/**
 * The glm-4.6v client for Sean's screenshot reader. One `fetch`, no SDK, copied from the measured
 * transport in ~/run-insights lib/llm/vision.ts:
 *
 *   POST {LLM_VISION_BASE_URL}/chat/completions, Authorization: Bearer LLM_API_KEY,
 *   { model: LLM_VISION_MODEL, max_tokens, thinking: { type: 'disabled' }, messages },
 *   the image as an OpenAI-shaped { type: 'image_url', image_url: { url: 'data:image/jpeg;base64,...' } }.
 *
 * NEVER point it at z.ai's /api/anthropic base URL: that endpoint answers HTTP 200, silently drops
 * the image, and returns invented numbers (run-insights IMPLEMENTATION_PLAN.md §1.1).
 * visionConfigFromEnv refuses such a URL.
 *
 * Pure apart from `fetch`, which every function takes as an argument: the config is passed in
 * rather than read from a server env module, so vitest and the smoke script call it directly.
 * The route that uses it (Phase 2) is the server-only part.
 */
import { ORDER_SYSTEM_PROMPT, buildOrderUserContent, buildRepairNote, type VisionContentPart } from './prompt';

export type VisionConfig = { baseUrl: string; apiKey: string; model: string };

/**
 * The reader's settings from the environment (LLM_API_KEY, LLM_VISION_BASE_URL,
 * LLM_VISION_MODEL), or null when one is missing or the base URL is the Anthropic-shaped one.
 */
export function visionConfigFromEnv(env: Record<string, string | undefined> = process.env): VisionConfig | null {
  const apiKey = env.LLM_API_KEY?.trim();
  const baseUrl = env.LLM_VISION_BASE_URL?.trim().replace(/\/+$/, '');
  const model = env.LLM_VISION_MODEL?.trim();
  if (!apiKey || !baseUrl || !model) return null;
  if (/\/anthropic(\/|$)/i.test(baseUrl)) return null;
  return { baseUrl, apiKey, model };
}

/**
 * THE TOKEN FLOOR. A request whose response reports fewer prompt tokens than this cannot have
 * delivered its image, and its text is not read.
 *
 * TEXT-AWARE, like run-insights' Nina floor (lib/nina/vision.ts), not flat like its F04 floor of
 * 500 x images. prompt_tokens counts the system prompt and the shape too -- about 3,000
 * characters here -- so a dropped image would still report several hundred tokens of text, and a
 * flat floor sized for the image alone would have to guess that number. So the floor is the text
 * we actually sent, estimated at a deliberately pessimistic 3 characters per token (real BPE runs
 * nearer 4, which raises the floor: it errs toward "the reader could not see it", never toward
 * believing an invented receipt), PLUS a per-image term.
 *
 * Per image: 150, Nina's re-calibrated number. With the text already covered, the per-image term
 * only has to be positive -- a dropped image adds zero image tokens -- and a big one outlaws real
 * small images (Nina's 500 refused a delivered 612x862 card).
 *
 * MEASURED 2026-10-07 with web/scripts/sean-vision-smoke.mjs on all 30 of the owner's receipts
 * (739x1600 JPEGs sent as is): prompt_tokens = 2,351 for every one, floor 1,141, so a delivered
 * image clears the floor by 1,210 tokens, and the ~1,400 image tokens are what a dropped image
 * would lose -- the text alone (~990 tokens at 3 characters each, fewer in reality) stays below
 * 1,141. 30/30 read and matched the hand-checked transcription on the first try.
 *
 * MULTIPLIED by the image count. A text-only request (imageCount 0) is not floored at all.
 */
export const TOKEN_FLOOR_PER_IMAGE = 150;
export const FLOOR_CHARS_PER_TOKEN = 3;

/** The reply is ~250 tokens of JSON; 2048 leaves room for chatter without truncating. */
export const MAX_TOKENS = 2048;

type Message =
  | { role: 'system'; content: string }
  | { role: 'user'; content: string | VisionContentPart[] }
  | { role: 'assistant'; content: string };

/** prompt_tokens a response must report for this request to count as delivered. */
export function tokenFloor(messages: Message[], imageCount: number): number {
  if (imageCount <= 0) return 0;
  let chars = 0;
  for (const m of messages) {
    if (typeof m.content === 'string') chars += m.content.length;
    else for (const part of m.content) if (part.type === 'text') chars += part.text.length;
  }
  return Math.ceil(chars / FLOOR_CHARS_PER_TOKEN) + TOKEN_FLOOR_PER_IMAGE * imageCount;
}

/**
 * The floor tripped: the image cannot have reached the model. Never repaired -- a repair would
 * send the same request shape to the same misbehaving endpoint.
 */
export class VisionTokenFloorError extends Error {
  constructor(
    readonly promptTokens: number,
    readonly floor: number,
    readonly imageCount: number,
  ) {
    super(
      `vision response reported prompt_tokens=${promptTokens} for ${imageCount} image(s); ` +
        `expected >= ${floor}. The endpoint may have dropped the image -- refusing to read a ` +
        `response that may have invented its numbers.`,
    );
    this.name = 'VisionTokenFloorError';
  }
}

/** Network failure, timeout, a body that is not JSON, or a non-200 that cleared the floor. */
export class VisionTransportError extends Error {
  constructor(
    message: string,
    readonly detail?: unknown,
  ) {
    super(message);
    this.name = 'VisionTransportError';
  }
}

export type VisionResult = {
  text: string;
  promptTokens: number;
  completionTokens: number;
  /** The floor this response had to clear (0 for a text-only request). */
  floor: number;
  finishReason: string | null;
  /** The vendor's body, untouched. */
  raw: unknown;
};

type FetchLike = typeof fetch;

/** The injectable core: one POST, the floor, then the text. */
export async function callVisionWithFetch(
  fetchImpl: FetchLike,
  cfg: VisionConfig,
  messages: Message[],
  opts: { timeoutMs: number; imageCount: number },
): Promise<VisionResult> {
  const floor = tokenFloor(messages, opts.imageCount);

  let res: Response;
  try {
    res = await fetchImpl(`${cfg.baseUrl}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${cfg.apiKey}` },
      body: JSON.stringify({
        model: cfg.model,
        max_tokens: MAX_TOKENS,
        // MEASURED in run-insights: thinking doubles latency (73 s vs 33.7 s) for an identical
        // score. Never remove.
        thinking: { type: 'disabled' },
        messages,
      }),
      signal: AbortSignal.timeout(opts.timeoutMs),
    });
  } catch (cause) {
    throw new VisionTransportError('vision request failed or timed out', cause);
  }

  let json: unknown;
  try {
    json = await res.json();
  } catch (cause) {
    throw new VisionTransportError(`vision response (HTTP ${res.status}) was not valid JSON`, cause);
  }

  const body = json as {
    usage?: { prompt_tokens?: number; completion_tokens?: number };
    choices?: Array<{ message?: { content?: string }; finish_reason?: string }>;
  };
  const promptTokens = body.usage?.prompt_tokens ?? 0;
  const completionTokens = body.usage?.completion_tokens ?? 0;

  // THE GUARD sits above every read of `choices`: nothing downstream may see the text of a
  // response that fails it, because that text is exactly where invented numbers live. A missing
  // usage block counts as 0 and fails closed. Checked before res.ok on purpose: the measured
  // failure was itself an HTTP 200.
  if (promptTokens < floor) {
    throw new VisionTokenFloorError(promptTokens, floor, opts.imageCount);
  }

  if (!res.ok) {
    throw new VisionTransportError(`vision endpoint returned ${res.status}: ${JSON.stringify(json).slice(0, 300)}`);
  }

  const choice = body.choices?.[0];
  return {
    text: choice?.message?.content ?? '',
    promptTokens,
    completionTokens,
    floor,
    finishReason: choice?.finish_reason ?? null,
    raw: json,
  };
}

/** The first read of one receipt. `imageB64` is bare base64 JPEG (a data: prefix is tolerated). */
export function readOrderWithFetch(
  fetchImpl: FetchLike,
  imageB64: string,
  cfg: VisionConfig,
  opts: { timeoutMs: number },
): Promise<VisionResult> {
  return callVisionWithFetch(
    fetchImpl,
    cfg,
    [
      { role: 'system', content: ORDER_SYSTEM_PROMPT },
      { role: 'user', content: buildOrderUserContent(imageB64) },
    ],
    { timeoutMs: opts.timeoutMs, imageCount: 1 },
  );
}

/**
 * The one repair: the same conversation (image included, so the floor applies again), the
 * model's first reply, and the list of problems the checks found.
 */
export function repairOrderWithFetch(
  fetchImpl: FetchLike,
  imageB64: string,
  cfg: VisionConfig,
  input: { malformedText: string; issues: string },
  opts: { timeoutMs: number },
): Promise<VisionResult> {
  return callVisionWithFetch(
    fetchImpl,
    cfg,
    [
      { role: 'system', content: ORDER_SYSTEM_PROMPT },
      { role: 'user', content: buildOrderUserContent(imageB64) },
      { role: 'assistant', content: input.malformedText },
      { role: 'user', content: buildRepairNote(input.issues) },
    ],
    { timeoutMs: opts.timeoutMs, imageCount: 1 },
  );
}
````

**File:** `web/lib/sean/vision.test.ts:1` (new)
**Change:** no network: every case injects `fetch` (run-insights' pattern). Proves the request body (`thinking` disabled, model, bearer, data-URI image, shape last), that a dropped image whose text alone clears a flat 500 still trips the floor, that a delivered image passes, missing usage fails closed, floor-before-status, repair floored, transport errors, and that `visionConfigFromEnv` refuses the `/api/anthropic` URL.
**Code:**
````ts
import { describe, expect, it, vi } from 'vitest';
import { ORDER_SHAPE, ORDER_SYSTEM_PROMPT, buildOrderUserContent } from './prompt';
import {
  FLOOR_CHARS_PER_TOKEN,
  TOKEN_FLOOR_PER_IMAGE,
  VisionTokenFloorError,
  VisionTransportError,
  readOrderWithFetch,
  repairOrderWithFetch,
  tokenFloor,
  visionConfigFromEnv,
  type VisionConfig,
} from './vision';

// No network anywhere in this file: every case injects `fetch`.

const CFG: VisionConfig = { baseUrl: 'https://api.z.ai/api/coding/paas/v4', apiKey: 'test-key', model: 'glm-4.6v' };
const IMG = '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA==';

/** What the primary request's text costs at the floor's pessimistic 3 characters per token. */
const PRIMARY_TEXT_CHARS =
  ORDER_SYSTEM_PROMPT.length +
  buildOrderUserContent(IMG).reduce((n, p) => n + (p.type === 'text' ? p.text.length : 0), 0);
const PRIMARY_FLOOR = Math.ceil(PRIMARY_TEXT_CHARS / FLOOR_CHARS_PER_TOKEN) + TOKEN_FLOOR_PER_IMAGE;

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function fakeFetch(body: unknown, status = 200) {
  return vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(body, status));
}

const reply = (content: string, promptTokens: number) => ({
  choices: [{ message: { content }, finish_reason: 'stop' }],
  usage: { prompt_tokens: promptTokens, completion_tokens: 250 },
});

/** A dropped image: the endpoint counts only our text (~chars / 4) and invents a receipt. */
const DROPPED = reply('{"ticker":"AAPL","total":"$5.00"}', Math.ceil(PRIMARY_TEXT_CHARS / 4));

describe('the request', () => {
  it('copies run-insights transport: URL, bearer key, model, thinking disabled, data-URI image', async () => {
    const doFetch = fakeFetch(reply('{}', 2400));
    await readOrderWithFetch(doFetch, IMG, CFG, { timeoutMs: 5_000 });

    expect(doFetch).toHaveBeenCalledOnce();
    const [url, init] = doFetch.mock.calls[0];
    expect(url).toBe('https://api.z.ai/api/coding/paas/v4/chat/completions');
    expect(init?.method).toBe('POST');
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer test-key');
    const body = JSON.parse(String(init?.body));
    expect(body.model).toBe('glm-4.6v');
    expect(body.thinking).toEqual({ type: 'disabled' });
    expect(body.response_format).toBeUndefined();
    expect(body.messages[0]).toEqual({ role: 'system', content: ORDER_SYSTEM_PROMPT });
    const parts = body.messages[1].content;
    expect(parts.filter((p: { type: string }) => p.type === 'image_url')).toEqual([
      { type: 'image_url', image_url: { url: `data:image/jpeg;base64,${IMG}` } },
    ]);
    expect(parts.at(-1).text).toContain(ORDER_SHAPE);
  });

  it('keeps a data: prefix the caller already added', () => {
    const parts = buildOrderUserContent(`data:image/jpeg;base64,${IMG}`);
    expect(parts[1]).toEqual({ type: 'image_url', image_url: { url: `data:image/jpeg;base64,${IMG}` } });
  });

  it('repairs in the same conversation, with the image, the first reply and the problems', async () => {
    const doFetch = fakeFetch(reply('{}', 2600));
    await repairOrderWithFetch(doFetch, IMG, CFG, { malformedText: '{"ticker":"MU"}', issues: '- Total is missing.' }, { timeoutMs: 5_000 });
    const body = JSON.parse(String(doFetch.mock.calls[0][1]?.body));
    expect(body.messages.map((m: { role: string }) => m.role)).toEqual(['system', 'user', 'assistant', 'user']);
    expect(body.messages[1].content.some((p: { type: string }) => p.type === 'image_url')).toBe(true);
    expect(body.messages[2].content).toBe('{"ticker":"MU"}');
    expect(body.messages[3].content).toContain('- Total is missing.');
  });
});

describe('the token floor', () => {
  it('is the text we sent at 3 characters a token plus 150 per image', () => {
    expect(tokenFloor([{ role: 'system', content: 'x'.repeat(300) }], 1)).toBe(100 + TOKEN_FLOOR_PER_IMAGE);
    expect(tokenFloor([{ role: 'system', content: 'x'.repeat(300) }], 0)).toBe(0);
  });

  it('refuses a dropped image even though the text alone clears a flat 500', async () => {
    expect(DROPPED.usage.prompt_tokens).toBeGreaterThan(500);
    const doFetch = fakeFetch(DROPPED);
    const error = await readOrderWithFetch(doFetch, IMG, CFG, { timeoutMs: 5_000 }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(VisionTokenFloorError);
    expect((error as VisionTokenFloorError).floor).toBe(PRIMARY_FLOOR);
    expect((error as VisionTokenFloorError).message).toContain(String(PRIMARY_FLOOR));
  });

  it('passes a delivered receipt image (text plus ~1,000 image tokens)', async () => {
    const real = Math.ceil(PRIMARY_TEXT_CHARS / 4) + 1_000;
    const doFetch = fakeFetch(reply('{"ticker":"MU"}', real));
    const result = await readOrderWithFetch(doFetch, IMG, CFG, { timeoutMs: 5_000 });
    expect(result.text).toBe('{"ticker":"MU"}');
    expect(result.promptTokens).toBe(real);
    expect(result.floor).toBe(PRIMARY_FLOOR);
  });

  it('treats a missing usage block as zero', async () => {
    const doFetch = fakeFetch({ choices: [{ message: { content: '{}' } }] });
    await expect(readOrderWithFetch(doFetch, IMG, CFG, { timeoutMs: 5_000 })).rejects.toThrow(VisionTokenFloorError);
  });

  it('checks the floor before the HTTP status (the measured drop was a 200)', async () => {
    const doFetch = fakeFetch({ error: 'bad' }, 500);
    await expect(readOrderWithFetch(doFetch, IMG, CFG, { timeoutMs: 5_000 })).rejects.toThrow(VisionTokenFloorError);
  });

  it('floors the repair too, because it carries the image again', async () => {
    const doFetch = fakeFetch(DROPPED);
    await expect(
      repairOrderWithFetch(doFetch, IMG, CFG, { malformedText: '{}', issues: '- x' }, { timeoutMs: 5_000 }),
    ).rejects.toThrow(VisionTokenFloorError);
  });
});

describe('transport errors', () => {
  it('wraps a non-200 that cleared the floor', async () => {
    const doFetch = fakeFetch({ error: { message: 'rate limited' }, usage: { prompt_tokens: 5_000 } }, 429);
    const error = await readOrderWithFetch(doFetch, IMG, CFG, { timeoutMs: 5_000 }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(VisionTransportError);
    expect((error as Error).message).toContain('429');
  });

  it('wraps a network failure and keeps the cause', async () => {
    const cause = Object.assign(new Error('timed out'), { name: 'TimeoutError' });
    const doFetch = vi.fn<typeof fetch>().mockRejectedValue(cause);
    const error = await readOrderWithFetch(doFetch, IMG, CFG, { timeoutMs: 5_000 }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(VisionTransportError);
    expect((error as VisionTransportError).detail).toBe(cause);
  });

  it('wraps a body that is not JSON', async () => {
    const doFetch = vi.fn<typeof fetch>().mockResolvedValue(new Response('<html>', { status: 502 }));
    await expect(readOrderWithFetch(doFetch, IMG, CFG, { timeoutMs: 5_000 })).rejects.toThrow(VisionTransportError);
  });
});

describe('visionConfigFromEnv', () => {
  const env = { LLM_API_KEY: 'k', LLM_VISION_BASE_URL: 'https://api.z.ai/api/coding/paas/v4/', LLM_VISION_MODEL: 'glm-4.6v' };

  it('reads the three variables and drops a trailing slash', () => {
    expect(visionConfigFromEnv(env)).toEqual({ apiKey: 'k', baseUrl: 'https://api.z.ai/api/coding/paas/v4', model: 'glm-4.6v' });
  });
  it('is null when one is missing', () => {
    expect(visionConfigFromEnv({ ...env, LLM_API_KEY: '' })).toBeNull();
    expect(visionConfigFromEnv({ ...env, LLM_VISION_MODEL: undefined })).toBeNull();
  });
  it('refuses the Anthropic-shaped endpoint that silently drops images', () => {
    expect(visionConfigFromEnv({ ...env, LLM_VISION_BASE_URL: 'https://api.z.ai/api/anthropic' })).toBeNull();
    expect(visionConfigFromEnv({ ...env, LLM_VISION_BASE_URL: 'https://api.z.ai/api/anthropic/v1' })).toBeNull();
  });
});
````
**Impact:** none until Phase 2 imports it.

### Step 7: From the model's JSON to a checked order
**File:** `web/lib/sean/order.ts:1` (new)
**Change:** `toOrder(raw)`. Refusals come in three kinds: `not_order` (the model said so), `not_filled` (status other than `Filled` — a true answer, never repaired: a partially filled or cancelled order could later be re-uploaded as Filled with different shares and slip past the unique key), `unreadable` (a field missing/unparseable or the arithmetic fails; repairable). Ticker goes through Seer's own `normalizeSymbol` (`web/lib/sera/gotrade-symbol.ts:14`, `BRK-B` -> `BRK.B`) so `sean_orders.symbol` matches the universe's spelling.
**Code:**
````ts
/**
 * The model's JSON -> one checked SeanOrder, or the plain-words reasons it is not one.
 *
 * Hand-rolled instead of zod (Seer web has no zod, and these checks are arithmetic, not shape):
 * a Gotrade receipt always adds up, so a misread digit almost always shows as a sum that does not.
 *   - Total = trade amount + fees (buy) or - fees (sell), within $0.01.
 *   - Trade amount = price x filled shares, within $0.01 + shares x $0.005: the amount is printed
 *     rounded to the cent (SPY 610.965 x 3 = 1832.895 printed as $1,832.90) and the price to the
 *     cent or finer, so each printed share can carry half a cent of price rounding. Tight enough
 *     to catch a transposed price ($610.695 x 3 is $0.81 off) or a slipped decimal point.
 *   - Partial fills add up to the filled shares within 0.0001 (the lines are printed rounded:
 *     NVDA "1.08477" + "6" for 7.084773035) and average to the price within 1 cent or 0.1%.
 *   - A fee printed with the other side's sign is a misread.
 * Issues are written for two readers at once: the model in the repair turn, and the owner when
 * the upload is refused.
 *
 * Pure: relative imports only, so vitest (no @/ alias) can load it.
 */
import { normalizeSymbol } from '../sera/gotrade-symbol';
import { asText, cents, parseReceiptDate, parseShares, parseUsd, parseUsdParts, roundHalfUp } from './money';
import type { OrderSide, SeanFill, SeanOrder } from './types';

export const TOTAL_TOLERANCE_USD = 0.01;
export const AMOUNT_TOLERANCE_USD = 0.01;
export const AMOUNT_TOLERANCE_PER_SHARE = 0.005;
export const FILL_SHARES_TOLERANCE = 0.0001;
const EPS = 1e-9;

export type OrderRefusal = 'not_order' | 'not_filled' | 'unreadable';

export type ToOrderResult =
  | { ok: true; order: SeanOrder }
  | { ok: false; kind: OrderRefusal; issues: string[] };

const usd = (n: number) => `$${n.toFixed(2)}`;
const price$ = (n: number) => `$${roundHalfUp(n, 6)}`;
const num = (n: number) => String(roundHalfUp(n, 9));
const quoted = (v: unknown) => (asText(v) === null ? 'nothing' : `"${asText(v)}"`);

/** 'Market Buy' -> 'buy', 'Limit Sell' -> 'sell'; null when it names neither or both. */
export function sideOf(orderType: string): OrderSide | null {
  const buy = /\bbuy\b/i.test(orderType);
  const sell = /\bsell\b/i.test(orderType);
  if (buy === sell) return null;
  return buy ? 'buy' : 'sell';
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

/** A positive dollar amount, or an issue. */
function positiveUsd(v: unknown, label: string, issues: string[]): number {
  const n = parseUsd(v);
  if (n === null || n <= 0) {
    issues.push(`${label} should be a dollar amount like "$27.90", but it was ${quoted(v)}.`);
    return 0;
  }
  return n;
}

/** A fee's size. Its printed sign must agree with the side: "+" on a buy, "-" on a sell. */
function fee(v: unknown, label: string, side: OrderSide | null, issues: string[]): number {
  const p = parseUsdParts(v);
  if (p === null) {
    issues.push(`${label} should be a dollar amount like "+$0.10", but it was ${quoted(v)}.`);
    return 0;
  }
  if (p.magnitude > 0 && side === 'buy' && p.sign === '-') {
    issues.push(`${label} ${quoted(v)} has a minus sign, but buy receipts print fees with "+".`);
  }
  if (p.magnitude > 0 && side === 'sell' && p.sign === '+') {
    issues.push(`${label} ${quoted(v)} has a plus sign, but sell receipts print fees with "-".`);
  }
  return p.magnitude;
}

function parseFills(v: unknown, issues: string[]): SeanFill[] {
  if (v === null || v === undefined) return [];
  if (!Array.isArray(v)) {
    issues.push('fills should be a list of partial-fill lines (an empty list when none are printed).');
    return [];
  }
  const out: SeanFill[] = [];
  v.forEach((line, i) => {
    const shares = isRecord(line) ? parseShares(line.shares) : null;
    const price = isRecord(line) ? parseUsd(line.price) : null;
    if (shares === null || shares <= 0 || price === null || price <= 0) {
      issues.push(`Partial fill line ${i + 1} should read like "0.38 shares @ $131.47".`);
      return;
    }
    out.push({ shares, price });
  });
  return out;
}

export function toOrder(raw: unknown): ToOrderResult {
  if (!isRecord(raw)) {
    return { ok: false, kind: 'unreadable', issues: ['The reply was not a JSON object.'] };
  }
  if (raw.isOrderSummary === false) {
    return { ok: false, kind: 'not_order', issues: ['This picture is not a Gotrade order summary.'] };
  }

  const issues: string[] = [];

  const status = asText(raw.status);
  if (status === null) {
    issues.push('Status is missing.');
  } else if (!/^filled$/i.test(status)) {
    return {
      ok: false,
      kind: 'not_filled',
      issues: [`This order says "${status}", not "Filled".`],
    };
  }

  const orderType = asText(raw.orderType);
  const side = orderType === null ? null : sideOf(orderType);
  if (orderType === null) issues.push('Order type is missing.');
  else if (side === null) issues.push(`Order type "${orderType}" should say Buy or Sell.`);

  const symbol = normalizeSymbol(raw.ticker);
  if (symbol === null) issues.push(`Ticker should be a stock symbol like "PLTR", but it was ${quoted(raw.ticker)}.`);

  const executedAt = parseReceiptDate(raw.date, raw.time);
  if (executedAt === null) {
    issues.push(
      `Date ${quoted(raw.date)} and time ${quoted(raw.time)} should read like "October 07, 2026" and "21:55 WIB".`,
    );
  }

  const price = positiveUsd(raw.price, 'Price', issues);
  const shares = parseShares(raw.filledShares);
  if (shares === null || shares <= 0) {
    issues.push(`Filled shares should be a number like "0.026224614", but it was ${quoted(raw.filledShares)}.`);
  }
  const amount = positiveUsd(raw.tradeAmount, 'Trade amount', issues);
  const total = positiveUsd(raw.total, 'Total', issues);
  const trading = fee(raw.tradingFee, 'Trading fee', side, issues);
  const regulatory = fee(raw.regulatoryFee, 'Regulatory fee', side, issues);
  const ppn = fee(raw.ppn, 'PPN', side, issues);
  const fills = parseFills(raw.fills, issues);

  let netProfit: number | null = null;
  if (asText(raw.netProfit) !== null) {
    if (side === 'buy') {
      issues.push('A buy receipt has no Net Profit row, but one was read.');
    } else {
      const p = parseUsdParts(raw.netProfit);
      if (p === null) {
        issues.push(`Net Profit should be a dollar amount like "$22.31", but it was ${quoted(raw.netProfit)}.`);
      } else {
        const negative = p.sign === '-' || (p.sign === null && raw.netProfitColor === 'red');
        netProfit = negative && p.magnitude !== 0 ? -p.magnitude : p.magnitude;
      }
    }
  }

  if (issues.length > 0 || side === null || symbol === null || executedAt === null || shares === null) {
    return { ok: false, kind: 'unreadable', issues };
  }

  const fees = trading + regulatory + ppn;
  const expected = side === 'buy' ? amount + fees : amount - fees;
  if (Math.abs(total - expected) > TOTAL_TOLERANCE_USD + EPS) {
    issues.push(
      `Total ${usd(total)} should equal the trade amount ${usd(amount)} ${side === 'buy' ? 'plus' : 'minus'} ` +
        `the fees ${usd(fees)}, which is ${usd(expected)}.`,
    );
  }

  const gross = price * shares;
  if (Math.abs(amount - gross) > AMOUNT_TOLERANCE_USD + AMOUNT_TOLERANCE_PER_SHARE * shares + EPS) {
    issues.push(
      `Trade amount ${usd(amount)} should be about the price ${price$(price)} times the filled shares ${num(shares)}, which is ${usd(gross)}.`,
    );
  }

  if (fills.length > 0) {
    const fillShares = fills.reduce((s, f) => s + f.shares, 0);
    if (Math.abs(fillShares - shares) > FILL_SHARES_TOLERANCE + EPS) {
      issues.push(`The partial fills add up to ${num(fillShares)} shares, but Filled shares says ${num(shares)}.`);
    } else {
      const avg = fills.reduce((s, f) => s + f.shares * f.price, 0) / fillShares;
      if (Math.abs(avg - price) > Math.max(0.01, 0.001 * price) + EPS) {
        issues.push(`The partial fills average ${price$(avg)} a share, but the price says ${price$(price)}.`);
      }
    }
  }

  if (issues.length > 0) return { ok: false, kind: 'unreadable', issues };

  return {
    ok: true,
    order: {
      side,
      orderType: orderType as string,
      status: status as string,
      symbol,
      executedAt,
      price: roundHalfUp(price, 6),
      shares: roundHalfUp(shares, 9),
      amountUsd: cents(amount),
      tradingFeeUsd: cents(trading),
      regulatoryFeeUsd: cents(regulatory),
      ppnUsd: cents(ppn),
      totalUsd: cents(total),
      netProfitUsd: netProfit === null ? null : cents(netProfit),
      fills: fills.map(f => ({ shares: roundHalfUp(f.shares, 9), price: roundHalfUp(f.price, 6) })),
    },
  };
}
````

**File:** `web/lib/sean/fixtures/receipts.json:1` (new)
**Change:** four of the owner's real receipts from `.workflows/plan/sean-gotrade-tracker/screenshots_truth.json` in the model's shape, each with the order `toOrder` must produce: PLTR split buy (average price, two partial fills, June 2025, $0 trading fee), MU fractional $27.90 slot at a four-figure price, SPY whole-share buy whose amount is rounded from 1832.895, PLTR sell (minus-signed fees, green Net Profit).
**Code:**
````json
{
  "about": "Four of the owner's real Gotrade Order Summary receipts, transcribed by hand and checked (2026-10-07), in the shape the model is asked to return (prompt.ts ORDER_SHAPE), each with the SeanOrder toOrder must produce. The screenshots themselves are not in the repo.",
  "receipts": [
    {
      "label": "PLTR buy, average price with two partial fills, June 2025 (no trading fee yet)",
      "raw": {
        "isOrderSummary": true,
        "status": "Filled",
        "date": "June 10, 2025",
        "time": "21:34 WIB",
        "orderType": "Market Buy",
        "ticker": "PLTR",
        "priceLabel": "Average price",
        "price": "$131.47",
        "fills": [
          { "shares": "0.38", "price": "$131.47" },
          { "shares": "5", "price": "$131.47" }
        ],
        "filledShares": "5.38",
        "tradeAmount": "$707.31",
        "tradingFee": "+$0.00",
        "regulatoryFee": "+$2.13",
        "ppn": "+$0.00",
        "total": "$709.44",
        "netProfit": null,
        "netProfitColor": null
      },
      "expected": {
        "side": "buy",
        "orderType": "Market Buy",
        "status": "Filled",
        "symbol": "PLTR",
        "executedAt": "2025-06-10T21:34:00+07:00",
        "price": 131.47,
        "shares": 5.38,
        "amountUsd": 707.31,
        "tradingFeeUsd": 0,
        "regulatoryFeeUsd": 2.13,
        "ppnUsd": 0,
        "totalUsd": 709.44,
        "netProfitUsd": null,
        "fills": [
          { "shares": 0.38, "price": 131.47 },
          { "shares": 5, "price": 131.47 }
        ]
      }
    },
    {
      "label": "MU buy, $27.90 fractional slot at a four-figure price, October 2026",
      "raw": {
        "isOrderSummary": true,
        "status": "Filled",
        "date": "October 07, 2026",
        "time": "22:00 WIB",
        "orderType": "Market Buy",
        "ticker": "MU",
        "priceLabel": "Execution price",
        "price": "$1,063.886",
        "fills": [],
        "filledShares": "0.026224614",
        "tradeAmount": "$27.90",
        "tradingFee": "+$0.10",
        "regulatoryFee": "+$0.02",
        "ppn": "+$0.01",
        "total": "$28.03",
        "netProfit": null,
        "netProfitColor": null
      },
      "expected": {
        "side": "buy",
        "orderType": "Market Buy",
        "status": "Filled",
        "symbol": "MU",
        "executedAt": "2026-10-07T22:00:00+07:00",
        "price": 1063.886,
        "shares": 0.026224614,
        "amountUsd": 27.9,
        "tradingFeeUsd": 0.1,
        "regulatoryFeeUsd": 0.02,
        "ppnUsd": 0.01,
        "totalUsd": 28.03,
        "netProfitUsd": null,
        "fills": []
      }
    },
    {
      "label": "SPY buy, whole shares, amount rounded from 1832.895, June 2025",
      "raw": {
        "isOrderSummary": true,
        "status": "Filled",
        "date": "June 26, 2025",
        "time": "23:12 WIB",
        "orderType": "Market Buy",
        "ticker": "SPY",
        "priceLabel": "Execution price",
        "price": "$610.965",
        "fills": [],
        "filledShares": "3",
        "tradeAmount": "$1,832.90",
        "tradingFee": "+$5.50",
        "regulatoryFee": "+$0.10",
        "ppn": "+$0.62",
        "total": "$1,839.12",
        "netProfit": null,
        "netProfitColor": null
      },
      "expected": {
        "side": "buy",
        "orderType": "Market Buy",
        "status": "Filled",
        "symbol": "SPY",
        "executedAt": "2025-06-26T23:12:00+07:00",
        "price": 610.965,
        "shares": 3,
        "amountUsd": 1832.9,
        "tradingFeeUsd": 5.5,
        "regulatoryFeeUsd": 0.1,
        "ppnUsd": 0.62,
        "totalUsd": 1839.12,
        "netProfitUsd": null,
        "fills": []
      }
    },
    {
      "label": "PLTR sell, fees printed with minus signs, Net Profit in green, October 2026",
      "raw": {
        "isOrderSummary": true,
        "status": "Filled",
        "date": "October 07, 2026",
        "time": "21:55 WIB",
        "orderType": "Market Sell",
        "ticker": "PLTR",
        "priceLabel": "Execution price",
        "price": "$190.81",
        "fills": [],
        "filledShares": "0.38",
        "tradeAmount": "$72.51",
        "tradingFee": "-$0.15",
        "regulatoryFee": "-$0.07",
        "ppn": "-$0.02",
        "total": "$72.27",
        "netProfit": "$22.31",
        "netProfitColor": "green"
      },
      "expected": {
        "side": "sell",
        "orderType": "Market Sell",
        "status": "Filled",
        "symbol": "PLTR",
        "executedAt": "2026-10-07T21:55:00+07:00",
        "price": 190.81,
        "shares": 0.38,
        "amountUsd": 72.51,
        "tradingFeeUsd": 0.15,
        "regulatoryFeeUsd": 0.07,
        "ppnUsd": 0.02,
        "totalUsd": 72.27,
        "netProfitUsd": 22.31,
        "fills": []
      }
    }
  ]
}
````

**File:** `web/lib/sean/order.test.ts:1` (new)
**Change:** every fixture receipt converts to its expected order; NVDA's rounded partial-fill lines (1.08477 + 6 for 7.084773035) pass; every refusal path has an exact plain-words message.
**Code:**
````ts
import { describe, expect, it } from 'vitest';
import fixture from './fixtures/receipts.json';
import { sideOf, toOrder } from './order';
import type { RawReceipt } from './types';

const receipts = fixture.receipts as { label: string; raw: RawReceipt; expected: unknown }[];
const [pltrBuy, muBuy, , pltrSell] = receipts.map(r => r.raw);

/** A fixture receipt with some fields changed. */
const edit = (raw: RawReceipt, change: Partial<Record<keyof RawReceipt, unknown>>) => ({ ...raw, ...change });

function issuesOf(raw: unknown): string[] {
  const r = toOrder(raw);
  if (r.ok) throw new Error('expected a refusal');
  return r.issues;
}

describe('toOrder on the real receipts', () => {
  for (const r of receipts) {
    it(r.label, () => {
      expect(toOrder(r.raw)).toEqual({ ok: true, order: r.expected });
    });
  }

  it('reads NVDA, whose partial-fill lines are printed rounded (1.08477 + 6 for 7.084773035)', () => {
    const r = toOrder(
      edit(muBuy, {
        date: 'October 05, 2026',
        time: '20:30 WIB',
        ticker: 'NVDA',
        priceLabel: 'Average price',
        price: '$236.16',
        fills: [
          { shares: '1.08477', price: '$236.16' },
          { shares: '6', price: '$236.16' },
        ],
        filledShares: '7.084773035',
        tradeAmount: '$1,673.14',
        tradingFee: '+$3.35',
        regulatoryFee: '+$0.11',
        ppn: '+$0.38',
        total: '$1,676.98',
      }),
    );
    expect(r.ok && r.order.shares).toBe(7.084773035);
    expect(r.ok && r.order.fills).toHaveLength(2);
  });

  it('accepts numbers where the model dropped the quotes', () => {
    const r = toOrder(edit(muBuy, { filledShares: 0.026224614 as unknown as string }));
    expect(r.ok).toBe(true);
  });

  it('normalizes the ticker the way the engine stores it', () => {
    const r = toOrder(edit(muBuy, { ticker: ' mu ' }));
    expect(r.ok && r.order.symbol).toBe('MU');
  });

  it('reads an unsigned red Net Profit as a loss', () => {
    const r = toOrder(edit(pltrSell, { netProfit: '$3.10', netProfitColor: 'red' }));
    expect(r.ok && r.order.netProfitUsd).toBe(-3.1);
    const signed = toOrder(edit(pltrSell, { netProfit: '-$3.10', netProfitColor: 'red' }));
    expect(signed.ok && signed.order.netProfitUsd).toBe(-3.1);
  });

  it('keeps a sell without a Net Profit row', () => {
    const r = toOrder(edit(pltrSell, { netProfit: null, netProfitColor: null }));
    expect(r.ok && r.order.netProfitUsd).toBeNull();
  });

  it('treats a missing fills list as no partial fills', () => {
    const { fills: _drop, ...rest } = muBuy;
    const r = toOrder(rest);
    expect(r.ok && r.order.fills).toEqual([]);
  });
});

describe('toOrder refusals', () => {
  it('says plainly when the picture is not an order summary', () => {
    expect(toOrder({ isOrderSummary: false })).toEqual({
      ok: false,
      kind: 'not_order',
      issues: ['This picture is not a Gotrade order summary.'],
    });
  });

  it('refuses an order that is not filled, without calling it a misread', () => {
    const r = toOrder(edit(muBuy, { status: 'Cancelled' }));
    expect(r).toEqual({ ok: false, kind: 'not_filled', issues: ['This order says "Cancelled", not "Filled".'] });
  });

  it('refuses something that is not an object', () => {
    expect(toOrder([1, 2])).toMatchObject({ ok: false, kind: 'unreadable' });
    expect(toOrder(null)).toMatchObject({ ok: false, kind: 'unreadable' });
  });

  it('names every missing or unreadable field', () => {
    const issues = issuesOf({ isOrderSummary: true });
    expect(issues).toEqual([
      'Status is missing.',
      'Order type is missing.',
      'Ticker should be a stock symbol like "PLTR", but it was nothing.',
      'Date nothing and time nothing should read like "October 07, 2026" and "21:55 WIB".',
      'Price should be a dollar amount like "$27.90", but it was nothing.',
      'Filled shares should be a number like "0.026224614", but it was nothing.',
      'Trade amount should be a dollar amount like "$27.90", but it was nothing.',
      'Total should be a dollar amount like "$27.90", but it was nothing.',
      'Trading fee should be a dollar amount like "+$0.10", but it was nothing.',
      'Regulatory fee should be a dollar amount like "+$0.10", but it was nothing.',
      'PPN should be a dollar amount like "+$0.10", but it was nothing.',
    ]);
  });

  it('catches a total that does not add up', () => {
    expect(issuesOf(edit(muBuy, { total: '$28.30' }))).toEqual([
      'Total $28.30 should equal the trade amount $27.90 plus the fees $0.13, which is $28.03.',
    ]);
    expect(issuesOf(edit(pltrSell, { total: '$72.75' }))).toEqual([
      'Total $72.75 should equal the trade amount $72.51 minus the fees $0.24, which is $72.27.',
    ]);
  });

  it('tolerates what cent rounding hides, and catches a slipped decimal point or a transposed price', () => {
    expect(toOrder(edit(muBuy, { filledShares: '0.0262246' })).ok).toBe(true);
    expect(issuesOf(edit(muBuy, { filledShares: '0.26224614' }))).toEqual([
      'Trade amount $27.90 should be about the price $1063.886 times the filled shares 0.26224614, which is $279.00.',
    ]);
    const spy = receipts[2].raw;
    expect(issuesOf(edit(spy, { price: '$610.695' }))).toEqual([
      'Trade amount $1832.90 should be about the price $610.695 times the filled shares 3, which is $1832.09.',
    ]);
  });

  it('catches partial fills that do not add up to the filled shares', () => {
    expect(
      issuesOf(edit(pltrBuy, { fills: [{ shares: '0.38', price: '$131.47' }, { shares: '4', price: '$131.47' }] })),
    ).toEqual(['The partial fills add up to 4.38 shares, but Filled shares says 5.38.']);
  });

  it('catches partial fills whose prices do not average to the price', () => {
    expect(
      issuesOf(edit(pltrBuy, { fills: [{ shares: '0.38', price: '$131.47' }, { shares: '5', price: '$113.47' }] })),
    ).toEqual(['The partial fills average $114.741375 a share, but the price says $131.47.']);
  });

  it('catches a fee printed with the wrong side sign', () => {
    expect(issuesOf(edit(muBuy, { tradingFee: '-$0.10', total: '$28.03' }))).toEqual([
      'Trading fee "-$0.10" has a minus sign, but buy receipts print fees with "+".',
    ]);
    expect(issuesOf(edit(pltrSell, { ppn: '+$0.02' }))).toEqual([
      'PPN "+$0.02" has a plus sign, but sell receipts print fees with "-".',
    ]);
  });

  it('catches a Net Profit read on a buy', () => {
    expect(issuesOf(edit(muBuy, { netProfit: '$1.00' }))).toEqual([
      'A buy receipt has no Net Profit row, but one was read.',
    ]);
  });

  it('catches an order type that is neither buy nor sell, and a bad partial-fill line', () => {
    expect(issuesOf(edit(muBuy, { orderType: 'Market' }))).toEqual(['Order type "Market" should say Buy or Sell.']);
    expect(issuesOf(edit(pltrBuy, { fills: [{ shares: 'some', price: '$131.47' }] }))).toEqual([
      'Partial fill line 1 should read like "0.38 shares @ $131.47".',
    ]);
    expect(issuesOf(edit(pltrBuy, { fills: 'none' }))).toEqual([
      'fills should be a list of partial-fill lines (an empty list when none are printed).',
    ]);
  });
});

describe('sideOf', () => {
  it('reads the side from the order type', () => {
    expect(sideOf('Market Buy')).toBe('buy');
    expect(sideOf('Limit Sell')).toBe('sell');
    expect(sideOf('market buy')).toBe('buy');
    expect(sideOf('Buy Sell')).toBeNull();
    expect(sideOf('Market')).toBeNull();
  });
});
````
**Impact:** none.

### Step 8: The read flow
**File:** `web/lib/sean/readOrder.ts:1` (new)
**Change:** run-insights `lib/llm/extract.ts`'s contract (never throws for a model problem, one repair, budget-gated, never repairs a floor trip or a reply cut off at `max_tokens`) with the calls and clock injected. Budget: 55 s total for the route's `maxDuration = 60`; first call capped at 40 s; the repair gets what is left, and is skipped under 12 s. `READ_MESSAGES` are the owner-facing texts (no ids, no jargon); `detail` carries the raw error for logs only.
**Code:**
````ts
/**
 * One screenshot -> one checked order: vision call -> JSON -> toOrder -> at most one repair.
 *
 * THE CONTRACT (run-insights lib/llm/extract.ts): this never throws for a model problem. Every
 * failure comes back as `{ ok: false, code, message }` with a plain-words message the Trades page
 * can show as is. It re-throws only an error that is not one of the vision client's own.
 *
 * Which failures get the one repair: only "unreadable" -- the reply was not JSON, a field could
 * not be parsed, or the numbers did not add up. Never the token floor (the same request to the
 * same endpoint fails the same way), never a timeout or transport error, never "not an order
 * summary" or "not filled" (those are true answers, not misreads), never a reply cut off by
 * max_tokens, and never when the time left is too short for a second call.
 *
 * The calls and the clock are injected (ReadOrderDeps), so the whole flow is unit-tested with no
 * network and no timers. Production builds them with visionDeps(cfg).
 */
import { extractJsonObject } from './extractJson';
import { toOrder, type ToOrderResult } from './order';
import type { SeanOrder } from './types';
import {
  VisionTokenFloorError,
  VisionTransportError,
  readOrderWithFetch,
  repairOrderWithFetch,
  type VisionConfig,
  type VisionResult,
} from './vision';

/** The whole read must finish inside the route's 60 s maxDuration, with room to write the row. */
export const READ_BUDGET_MS = 55_000;
export const PRIMARY_TIMEOUT_MS = 40_000;
export const REPAIR_TIMEOUT_MS = 30_000;
/** A repair is skipped when less than this is left: one receipt took 4.7-10.5 s (30 measured). */
export const MIN_REPAIR_BUDGET_MS = 12_000;

export type ReadOrderDeps = {
  callPrimary: (imageB64: string, opts: { timeoutMs: number }) => Promise<VisionResult>;
  callRepair: (
    imageB64: string,
    input: { malformedText: string; issues: string },
    opts: { timeoutMs: number },
  ) => Promise<VisionResult>;
  now: () => number;
};

/** The production wiring: the real glm-4.6v calls with `cfg`, the real clock. */
export function visionDeps(cfg: VisionConfig, fetchImpl: typeof fetch = (input, init) => fetch(input, init)): ReadOrderDeps {
  return {
    callPrimary: (imageB64, opts) => readOrderWithFetch(fetchImpl, imageB64, cfg, opts),
    callRepair: (imageB64, input, opts) => repairOrderWithFetch(fetchImpl, imageB64, cfg, input, opts),
    now: () => Date.now(),
  };
}

export type ReadOrderCode = 'token_floor' | 'timeout' | 'transport' | 'not_order' | 'not_filled' | 'unreadable';

/** What the owner reads when a picture is refused. No ids, no jargon. */
export const READ_MESSAGES: Record<ReadOrderCode, string> = {
  token_floor: 'The reader could not see this picture. Try it again in a minute.',
  timeout: 'The reader took too long with this picture. Try it again.',
  transport: 'The reader could not be reached. Try again in a minute.',
  not_order: 'This picture is not a Gotrade order summary.',
  not_filled: 'Sean only records filled orders.',
  unreadable: 'Sean could not read this order summary clearly.',
};

/** The reader itself failed (HTTP 502 in the route), as opposed to the picture (HTTP 422). */
export function isReaderDown(code: ReadOrderCode): boolean {
  return code === 'token_floor' || code === 'timeout' || code === 'transport';
}

export type ReadOrderOutcome =
  | {
      ok: true;
      order: SeanOrder;
      /** The model's JSON that produced the order, for sean_orders.raw. */
      raw: unknown;
      attempts: 1 | 2;
      promptTokens: number;
      floor: number;
    }
  | {
      ok: false;
      code: ReadOrderCode;
      /** READ_MESSAGES[code], plus the first issue when there is one. */
      message: string;
      issues: string[];
      raw: unknown | null;
      attempts: 1 | 2;
      promptTokens: number | null;
      floor: number | null;
      /** For logs only, never shown: the vision error's own message when the reader failed. */
      detail: string | null;
    };

type Failure = Extract<ReadOrderOutcome, { ok: false }>;

/** Said to the model in the repair turn; never shown to the owner. */
const NO_JSON = 'The reply contained no JSON object at all. Return ONLY the JSON object.';

function failure(
  code: ReadOrderCode,
  issues: string[],
  raw: unknown | null,
  attempts: 1 | 2,
  tokens: { promptTokens: number | null; floor: number | null },
  detail: string | null = null,
): Failure {
  const shown = isReaderDown(code) || code === 'not_order' ? undefined : issues.find(i => i !== NO_JSON);
  const message = shown === undefined ? READ_MESSAGES[code] : `${READ_MESSAGES[code]} ${shown}`;
  return { ok: false, code, message, issues, raw, attempts, ...tokens, detail };
}

/** A thrown vision error -> its code; null means "not ours, rethrow". */
function codeForVisionError(cause: unknown): ReadOrderCode | null {
  if (cause instanceof VisionTokenFloorError) return 'token_floor';
  if (cause instanceof VisionTransportError) {
    const inner = cause.detail;
    const isTimeout = inner instanceof Error && (inner.name === 'TimeoutError' || inner.name === 'AbortError');
    return isTimeout ? 'timeout' : 'transport';
  }
  return null;
}

function detailOf(cause: unknown): string {
  const inner = cause instanceof VisionTransportError && cause.detail instanceof Error ? ` (${cause.detail.message})` : '';
  return `${cause instanceof Error ? cause.message : String(cause)}${inner}`;
}

function thrownTokens(cause: unknown): { promptTokens: number | null; floor: number | null } {
  return cause instanceof VisionTokenFloorError
    ? { promptTokens: cause.promptTokens, floor: cause.floor }
    : { promptTokens: null, floor: null };
}

export async function readOrder(
  deps: ReadOrderDeps,
  imageB64: string,
  budgetMs: number = READ_BUDGET_MS,
): Promise<ReadOrderOutcome> {
  const startedAt = deps.now();

  let primary: VisionResult;
  try {
    primary = await deps.callPrimary(imageB64, { timeoutMs: Math.min(PRIMARY_TIMEOUT_MS, budgetMs) });
  } catch (cause) {
    const code = codeForVisionError(cause);
    if (code === null) throw cause;
    return failure(code, [], null, 1, thrownTokens(cause), detailOf(cause));
  }

  const firstJson = extractJsonObject(primary.text);
  const first: ToOrderResult | null = firstJson === null ? null : toOrder(firstJson);
  const firstTokens = { promptTokens: primary.promptTokens, floor: primary.floor };

  if (first?.ok) {
    return { ok: true, order: first.order, raw: firstJson, attempts: 1, ...firstTokens };
  }
  if (first && first.kind !== 'unreadable') {
    return failure(first.kind, first.issues, firstJson, 1, firstTokens);
  }

  const firstIssues = first === null ? [NO_JSON] : first.issues;
  const budgetLeft = budgetMs - (deps.now() - startedAt);
  if (primary.finishReason === 'length' || budgetLeft < MIN_REPAIR_BUDGET_MS) {
    return failure('unreadable', firstIssues, firstJson, 1, firstTokens);
  }

  let repair: VisionResult;
  try {
    repair = await deps.callRepair(
      imageB64,
      { malformedText: primary.text, issues: firstIssues.map(i => `- ${i}`).join('\n') },
      { timeoutMs: Math.min(REPAIR_TIMEOUT_MS, budgetLeft) },
    );
  } catch (cause) {
    const code = codeForVisionError(cause);
    if (code === null) throw cause;
    return failure(code, firstIssues, firstJson, 2, thrownTokens(cause), detailOf(cause));
  }

  const secondJson = extractJsonObject(repair.text);
  const second: ToOrderResult | null = secondJson === null ? null : toOrder(secondJson);
  const secondTokens = { promptTokens: repair.promptTokens, floor: repair.floor };

  if (second?.ok) {
    return { ok: true, order: second.order, raw: secondJson, attempts: 2, ...secondTokens };
  }
  if (second === null) return failure('unreadable', [NO_JSON], firstJson, 2, secondTokens);
  return failure(second.kind, second.issues, secondJson, 2, secondTokens);
}
````

**File:** `web/lib/sean/readOrder.test.ts:1` (new)
**Code:**
````ts
import { describe, expect, it, vi } from 'vitest';
import fixture from './fixtures/receipts.json';
import {
  MIN_REPAIR_BUDGET_MS,
  READ_MESSAGES,
  isReaderDown,
  readOrder,
  visionDeps,
  type ReadOrderDeps,
} from './readOrder';
import { VisionTokenFloorError, VisionTransportError, type VisionResult } from './vision';

const IMG = '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA==';
const MU = fixture.receipts[1];

const result = (text: string, finishReason: string | null = 'stop'): VisionResult => ({
  text,
  promptTokens: 2_400,
  completionTokens: 250,
  floor: 1_450,
  finishReason,
  raw: { text },
});

/** Fake calls and a clock that moves only when a test says so. */
function deps(primary: () => Promise<VisionResult>, repair?: () => Promise<VisionResult>, clock = { t: 0 }) {
  const d: ReadOrderDeps = {
    callPrimary: vi.fn(primary),
    callRepair: vi.fn(repair ?? (() => Promise.reject(new Error('repair not expected')))),
    now: () => clock.t,
  };
  return d;
}

describe('readOrder', () => {
  it('returns the order on a clean first read', async () => {
    const d = deps(() => Promise.resolve(result(JSON.stringify(MU.raw))));
    const out = await readOrder(d, IMG);
    expect(out).toEqual({ ok: true, order: MU.expected, raw: MU.raw, attempts: 1, promptTokens: 2_400, floor: 1_450 });
    expect(d.callRepair).not.toHaveBeenCalled();
  });

  it('repairs once, with the image and the issues, when the numbers do not add up', async () => {
    const bad = { ...MU.raw, total: '$28.30' };
    const d = deps(
      () => Promise.resolve(result(JSON.stringify(bad))),
      () => Promise.resolve(result(JSON.stringify(MU.raw))),
    );
    const out = await readOrder(d, IMG);
    expect(out.ok && out.attempts).toBe(2);
    expect(out.ok && out.order).toEqual(MU.expected);
    const [image, input] = vi.mocked(d.callRepair).mock.calls[0];
    expect(image).toBe(IMG);
    expect(input.malformedText).toBe(JSON.stringify(bad));
    expect(input.issues).toBe(
      '- Total $28.30 should equal the trade amount $27.90 plus the fees $0.13, which is $28.03.',
    );
  });

  it('repairs a reply with no JSON in it, and says so to the model only', async () => {
    const d = deps(
      () => Promise.resolve(result('I cannot help with that.')),
      () => Promise.resolve(result('still nothing')),
    );
    const out = await readOrder(d, IMG);
    expect(vi.mocked(d.callRepair).mock.calls[0][1].issues).toContain('no JSON object');
    expect(out).toMatchObject({ ok: false, code: 'unreadable', attempts: 2, message: READ_MESSAGES.unreadable });
  });

  it('gives up after one repair and shows the owner the first problem', async () => {
    const bad = { ...MU.raw, total: '$28.30' };
    const d = deps(
      () => Promise.resolve(result(JSON.stringify(bad))),
      () => Promise.resolve(result(JSON.stringify(bad))),
    );
    const out = await readOrder(d, IMG);
    expect(out).toMatchObject({
      ok: false,
      code: 'unreadable',
      attempts: 2,
      raw: bad,
      message: `${READ_MESSAGES.unreadable} Total $28.30 should equal the trade amount $27.90 plus the fees $0.13, which is $28.03.`,
    });
    expect(d.callRepair).toHaveBeenCalledOnce();
  });

  it('never repairs a token-floor trip', async () => {
    const d = deps(() => Promise.reject(new VisionTokenFloorError(900, 1_450, 1)));
    const out = await readOrder(d, IMG);
    expect(out).toMatchObject({ ok: false, code: 'token_floor', promptTokens: 900, floor: 1_450, attempts: 1 });
    expect(out.ok === false && out.message).toBe(READ_MESSAGES.token_floor);
    expect(d.callRepair).not.toHaveBeenCalled();
  });

  it('tells a timeout from an unreachable reader', async () => {
    const timeout = Object.assign(new Error('t'), { name: 'TimeoutError' });
    const a = await readOrder(deps(() => Promise.reject(new VisionTransportError('x', timeout))), IMG);
    const b = await readOrder(deps(() => Promise.reject(new VisionTransportError('x', new TypeError('fetch failed')))), IMG);
    expect(a).toMatchObject({ ok: false, code: 'timeout' });
    expect(b).toMatchObject({ ok: false, code: 'transport' });
  });

  it('does not repair a true answer: not an order summary, or not filled', async () => {
    const notOrder = deps(() => Promise.resolve(result('{"isOrderSummary": false}')));
    expect(await readOrder(notOrder, IMG)).toMatchObject({
      ok: false,
      code: 'not_order',
      message: READ_MESSAGES.not_order,
    });
    const cancelled = deps(() => Promise.resolve(result(JSON.stringify({ ...MU.raw, status: 'Cancelled' }))));
    expect(await readOrder(cancelled, IMG)).toMatchObject({
      ok: false,
      code: 'not_filled',
      message: 'Sean only records filled orders. This order says "Cancelled", not "Filled".',
    });
    expect(notOrder.callRepair).not.toHaveBeenCalled();
    expect(cancelled.callRepair).not.toHaveBeenCalled();
  });

  it('does not repair a reply cut off by max_tokens', async () => {
    const d = deps(() => Promise.resolve(result('{"ticker": "MU", "tot', 'length')));
    expect(await readOrder(d, IMG)).toMatchObject({ ok: false, code: 'unreadable', attempts: 1 });
    expect(d.callRepair).not.toHaveBeenCalled();
  });

  it('skips the repair when the first call ate the budget', async () => {
    const clock = { t: 0 };
    const d = deps(
      async () => {
        clock.t = 50_000 - MIN_REPAIR_BUDGET_MS + 1;
        return result(JSON.stringify({ ...MU.raw, total: '$28.30' }));
      },
      undefined,
      clock,
    );
    expect(await readOrder(d, IMG, 50_000)).toMatchObject({ ok: false, code: 'unreadable', attempts: 1 });
    expect(d.callRepair).not.toHaveBeenCalled();
  });

  it('gives the repair only the time that is left', async () => {
    const clock = { t: 0 };
    const d = deps(
      async () => {
        clock.t = 30_000;
        return result(JSON.stringify({ ...MU.raw, total: '$28.30' }));
      },
      () => Promise.resolve(result(JSON.stringify(MU.raw))),
      clock,
    );
    await readOrder(d, IMG, 50_000);
    expect(vi.mocked(d.callRepair).mock.calls[0][2]).toEqual({ timeoutMs: 20_000 });
  });

  it('reports a failed repair call by its own code', async () => {
    const d = deps(
      () => Promise.resolve(result(JSON.stringify({ ...MU.raw, total: '$28.30' }))),
      () => Promise.reject(new VisionTransportError('down')),
    );
    expect(await readOrder(d, IMG)).toMatchObject({ ok: false, code: 'transport', attempts: 2 });
  });

  it('rethrows an error that is not the vision client’s', async () => {
    await expect(readOrder(deps(() => Promise.reject(new RangeError('bug'))), IMG)).rejects.toThrow(RangeError);
  });
});

describe('isReaderDown', () => {
  it('splits reader failures (502) from picture failures (422)', () => {
    expect(['token_floor', 'timeout', 'transport'].every(c => isReaderDown(c as never))).toBe(true);
    expect(['not_order', 'not_filled', 'unreadable'].some(c => isReaderDown(c as never))).toBe(false);
  });
});

describe('visionDeps', () => {
  it('wires the real calls to the injected fetch', async () => {
    const doFetch = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          choices: [{ message: { content: JSON.stringify(MU.raw) }, finish_reason: 'stop' }],
          usage: { prompt_tokens: 3_000, completion_tokens: 250 },
        }),
        { status: 200 },
      ),
    );
    const out = await readOrder(
      visionDeps({ baseUrl: 'https://example.test/v4', apiKey: 'k', model: 'glm-4.6v' }, doFetch),
      IMG,
    );
    expect(out.ok && out.order).toEqual(MU.expected);
    expect(doFetch.mock.calls[0][0]).toBe('https://example.test/v4/chat/completions');
  });
});
````
**Impact:** none until Phase 2's route calls `readOrder`.

### Step 9: The ledger and its shared fixture
**File:** `web/lib/sean/ledger.ts:1` (new)
**Change:** contract B as made exact in the Interface Contract above. One `Replay` walks the sorted orders once; `pnlSeries` advances it date by date (trade date is monotonic in `executed_at`, so a prefix walk is exact); closes are looked up by binary search. Session dates come from `Intl.DateTimeFormat` in `America/New_York` (Node ships full ICU; browsers too).
**Code:**
````ts
/**
 * The owner's real ledger: positions, realized and unrealized profit, fees -- from Gotrade orders
 * and daily closes only (receipts never show the cash balance).
 *
 * ONE LEDGER, TWO LANGUAGES. engine/src/seer_engine/sean/ledger.py (Phase 4) does the same math
 * and both pass web/lib/sean/fixtures/ledger.json. Change the math here and you change it there.
 *
 * The math (plan contract B, made exact):
 *  - Orders replay sorted by executedAt (as an instant), then id.
 *  - An order belongs to the NYSE session of its executedAt read in America/New_York: a buy at
 *    03:30 WIB on Jan 8 filled at 15:30 New York time on Jan 7, so it is in Jan 7's session.
 *  - Per symbol, average cost, fees inside the cost:
 *      buy:  shares += s; cost += totalUsd (amount + fees).
 *      sell: s = min(receipt shares, held). If s > 0: avg = cost / held;
 *            proceeds = totalUsd when s is the whole receipt, else totalUsd * s / receipt shares
 *            (the shares sold beyond what Sean knows of, and their money, are ignored);
 *            realized += proceeds - s * avg; cost -= s * avg; shares -= s.
 *            So a sell of a stock Sean never saw bought (held before the owner started
 *            uploading) changes nothing but the fees: booking its whole proceeds as profit
 *            would invent gains the size of the position.
 *      Shares below 1e-9 close the position: shares = cost = 0.
 *  - fees += trading + regulatory + PPN on every order, the clamped part included.
 *  - At date d: value = sum of shares x (the symbol's last close on or before d, else the price of
 *    its last order replayed so far); unrealized = value - sum of cost; pnl = realized + unrealized.
 *  - Money is rounded to cents only at output, each figure on its own (half up); shares keep 9
 *    decimals. So pnlUsd can differ from realizedUsd + unrealizedUsd by a cent.
 *  - Gotrade's own "Net Profit" on a sell (no buy fees in its basis) is NOT this ledger's realized
 *    figure; the Trades page shows it on the sell row.
 *
 * Pure: relative imports only.
 */
import { cents, roundHalfUp } from './money';
import type { OrderSide } from './types';

/** The fields of a stored order the ledger reads. `id` breaks ties between equal timestamps. */
export type LedgerOrder = {
  id: number;
  side: OrderSide;
  symbol: string;
  executedAt: string;
  price: number;
  shares: number;
  totalUsd: number;
  tradingFeeUsd: number;
  regulatoryFeeUsd: number;
  ppnUsd: number;
};

/** One daily close (sean_marks). */
export type Close = { symbol: string; date: string; close: number };

export const DUST_SHARES = 1e-9;

export type Holding = {
  symbol: string;
  /** 9 decimals. */
  shares: number;
  /** Open cost basis, fees included, in cents. */
  costUsd: number;
  /** costUsd / shares, 6 decimals. */
  avgPrice: number;
  /** The price on the last order in this symbol. */
  lastOrderPrice: number;
};

export type LedgerBook = {
  /** Open positions only, by symbol. */
  holdings: Holding[];
  realizedUsd: number;
  feesUsd: number;
};

/** One day of the P&L series; mirrors a sean_equity row. */
export type PnlPoint = {
  date: string;
  valueUsd: number;
  costUsd: number;
  realizedUsd: number;
  unrealizedUsd: number;
  pnlUsd: number;
  feesUsd: number;
};

const NEW_YORK = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

/** The NYSE session date (YYYY-MM-DD, New York calendar) an order filled in. */
export function orderSession(executedAt: string): string {
  const ms = Date.parse(executedAt);
  if (Number.isNaN(ms)) throw new Error(`not a timestamp: ${executedAt}`);
  const parts = Object.fromEntries(NEW_YORK.formatToParts(ms).map(p => [p.type, p.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}

type Position = { shares: number; cost: number; lastPrice: number };
type Queued = LedgerOrder & { ms: number; session: string };

/** Replays orders once, in order, as far as asked. */
class Replay {
  readonly positions = new Map<string, Position>();
  realized = 0;
  fees = 0;
  private readonly queue: Queued[];
  private next = 0;

  constructor(orders: LedgerOrder[]) {
    this.queue = orders
      .map(o => ({ ...o, ms: Date.parse(o.executedAt), session: orderSession(o.executedAt) }))
      .sort((a, b) => a.ms - b.ms || a.id - b.id);
  }

  /** Apply every order whose session is on or before `date` (all of them when null). */
  advanceThrough(date: string | null): void {
    while (this.next < this.queue.length && (date === null || this.queue[this.next].session <= date)) {
      this.apply(this.queue[this.next]);
      this.next += 1;
    }
  }

  private apply(o: Queued): void {
    this.fees += o.tradingFeeUsd + o.regulatoryFeeUsd + o.ppnUsd;
    const p = this.positions.get(o.symbol) ?? { shares: 0, cost: 0, lastPrice: o.price };
    p.lastPrice = o.price;
    if (o.side === 'buy') {
      p.shares += o.shares;
      p.cost += o.totalUsd;
    } else {
      const held = p.shares;
      const s = Math.min(o.shares, held);
      if (s > 0 && o.shares > 0) {
        const avg = p.cost / held;
        const proceeds = s === o.shares ? o.totalUsd : (o.totalUsd * s) / o.shares;
        this.realized += proceeds - s * avg;
        p.cost -= s * avg;
        p.shares -= s;
      }
    }
    if (p.shares < DUST_SHARES) {
      p.shares = 0;
      p.cost = 0;
    }
    this.positions.set(o.symbol, p);
  }
}

type CloseIndex = Map<string, { dates: string[]; closes: number[] }>;

function indexCloses(closes: Close[]): CloseIndex {
  const bySymbol = new Map<string, Close[]>();
  for (const c of closes) {
    const list = bySymbol.get(c.symbol) ?? [];
    list.push(c);
    bySymbol.set(c.symbol, list);
  }
  const index: CloseIndex = new Map();
  for (const [symbol, list] of bySymbol) {
    list.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
    index.set(symbol, { dates: list.map(c => c.date), closes: list.map(c => c.close) });
  }
  return index;
}

/** The symbol's last close on or before `date`, or null. */
function closeOnOrBefore(index: CloseIndex, symbol: string, date: string): number | null {
  const s = index.get(symbol);
  if (!s) return null;
  let lo = 0;
  let hi = s.dates.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (s.dates[mid] <= date) {
      found = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return found < 0 ? null : s.closes[found];
}

function point(replay: Replay, index: CloseIndex, date: string): PnlPoint {
  let value = 0;
  let cost = 0;
  for (const [symbol, p] of replay.positions) {
    if (p.shares === 0) continue;
    value += p.shares * (closeOnOrBefore(index, symbol, date) ?? p.lastPrice);
    cost += p.cost;
  }
  const unrealized = value - cost;
  return {
    date,
    valueUsd: cents(value),
    costUsd: cents(cost),
    realizedUsd: cents(replay.realized),
    unrealizedUsd: cents(unrealized),
    pnlUsd: cents(replay.realized + unrealized),
    feesUsd: cents(replay.fees),
  };
}

/** The book after every order whose session is on or before `through` (all orders when omitted). */
export function buildLedger(orders: LedgerOrder[], through?: string): LedgerBook {
  const replay = new Replay(orders);
  replay.advanceThrough(through ?? null);
  const holdings: Holding[] = [];
  for (const [symbol, p] of replay.positions) {
    if (p.shares === 0) continue;
    holdings.push({
      symbol,
      shares: roundHalfUp(p.shares, 9),
      costUsd: cents(p.cost),
      avgPrice: roundHalfUp(p.cost / p.shares, 6),
      lastOrderPrice: p.lastPrice,
    });
  }
  holdings.sort((a, b) => (a.symbol < b.symbol ? -1 : a.symbol > b.symbol ? 1 : 0));
  return { holdings, realizedUsd: cents(replay.realized), feesUsd: cents(replay.fees) };
}

/** One P&L point per date (YYYY-MM-DD), ascending, duplicates dropped. */
export function pnlSeries(orders: LedgerOrder[], closes: Close[], dates: string[]): PnlPoint[] {
  const replay = new Replay(orders);
  const index = indexCloses(closes);
  const days = [...new Set(dates)].sort();
  return days.map(date => {
    replay.advanceThrough(date);
    return point(replay, index, date);
  });
}

/** The P&L at one date. */
export function pnlAt(orders: LedgerOrder[], closes: Close[], date: string): PnlPoint {
  return pnlSeries(orders, closes, [date])[0];
}
````

**File:** `web/lib/sean/fixtures/ledger.json:1` (new)
**Change:** synthetic orders (not the owner's), in Phase 4's requested schema. Expected values were computed with Python `Decimal` and `ROUND_HALF_UP` by the script in the Appendix, then reproduced by `ledger.ts` to the cent. Covers: after-midnight-WIB fill (id 3 -> Jan 7), oversell (id 5, pro-rata proceeds, realized hits the 26.125 tie -> 26.13 on Jan 12), sell of a never-bought stock (id 10, fees only), a holding with no closes (CCC at its last order price), same-instant orders replayed by id (8 listed before 7), a weekend date, a date before any order, and a DST-day session in `sessions`.
**Code:**
````json
{
  "about": "Shared ledger fixture (contract B): web/lib/sean/ledger.test.ts and engine/tests/test_sean_ledger.py both replay it. Synthetic orders, not the owner's. Keys are sean_orders / sean_equity column names; every number is a string so Python reads it as Decimal. Expected values were computed with Decimal and ROUND_HALF_UP. Covers: an after-midnight-WIB fill that belongs to the previous New York session (id 3), a sell of more shares than held (id 5), a sell of a stock never seen bought (id 10), a holding with no closes (CCC, valued at its last order price), two orders at the same instant replayed by id (7 before 8), a weekend date (2026-01-10), a date before any order, and a half-cent tie in realized (26.125 -> 26.13 on 2026-01-12).",
  "orders": [
    {
      "id": 1,
      "side": "buy",
      "symbol": "AAA",
      "executed_at": "2026-01-05T21:30:00+07:00",
      "price": "100",
      "shares": "2",
      "amount_usd": "200.00",
      "trading_fee_usd": "0.40",
      "regulatory_fee_usd": "0.05",
      "ppn_usd": "0.05",
      "total_usd": "200.50"
    },
    {
      "id": 2,
      "side": "buy",
      "symbol": "BBB",
      "executed_at": "2026-01-06T22:00:00+07:00",
      "price": "50.5",
      "shares": "0.5",
      "amount_usd": "25.25",
      "trading_fee_usd": "0.10",
      "regulatory_fee_usd": "0.02",
      "ppn_usd": "0.01",
      "total_usd": "25.38"
    },
    {
      "id": 3,
      "side": "buy",
      "symbol": "AAA",
      "executed_at": "2026-01-08T03:30:00+07:00",
      "price": "110",
      "shares": "1",
      "amount_usd": "110.00",
      "trading_fee_usd": "0.22",
      "regulatory_fee_usd": "0.05",
      "ppn_usd": "0.03",
      "total_usd": "110.30"
    },
    {
      "id": 4,
      "side": "sell",
      "symbol": "AAA",
      "executed_at": "2026-01-09T21:45:00+07:00",
      "price": "120",
      "shares": "1.5",
      "amount_usd": "180.00",
      "trading_fee_usd": "0.36",
      "regulatory_fee_usd": "0.06",
      "ppn_usd": "0.05",
      "total_usd": "179.53"
    },
    {
      "id": 5,
      "side": "sell",
      "symbol": "BBB",
      "executed_at": "2026-01-12T21:40:00+07:00",
      "price": "55",
      "shares": "0.6",
      "amount_usd": "33.00",
      "trading_fee_usd": "0.10",
      "regulatory_fee_usd": "0.04",
      "ppn_usd": "0.01",
      "total_usd": "32.85"
    },
    {
      "id": 6,
      "side": "buy",
      "symbol": "CCC",
      "executed_at": "2026-01-12T21:50:00+07:00",
      "price": "10.123456",
      "shares": "2.963",
      "amount_usd": "29.99",
      "trading_fee_usd": "0.10",
      "regulatory_fee_usd": "0.02",
      "ppn_usd": "0.01",
      "total_usd": "30.12"
    },
    {
      "id": 8,
      "side": "sell",
      "symbol": "DDD",
      "executed_at": "2026-01-13T22:00:00+07:00",
      "price": "20",
      "shares": "1",
      "amount_usd": "20.00",
      "trading_fee_usd": "0.10",
      "regulatory_fee_usd": "0.02",
      "ppn_usd": "0.01",
      "total_usd": "19.87"
    },
    {
      "id": 7,
      "side": "buy",
      "symbol": "DDD",
      "executed_at": "2026-01-13T22:00:00+07:00",
      "price": "20",
      "shares": "1",
      "amount_usd": "20.00",
      "trading_fee_usd": "0.10",
      "regulatory_fee_usd": "0.02",
      "ppn_usd": "0.01",
      "total_usd": "20.13"
    },
    {
      "id": 10,
      "side": "sell",
      "symbol": "ZZZ",
      "executed_at": "2026-01-13T21:35:00+07:00",
      "price": "15",
      "shares": "2",
      "amount_usd": "30.00",
      "trading_fee_usd": "0.10",
      "regulatory_fee_usd": "0.02",
      "ppn_usd": "0.01",
      "total_usd": "29.87"
    },
    {
      "id": 9,
      "side": "buy",
      "symbol": "EEE",
      "executed_at": "2026-01-13T23:00:00+07:00",
      "price": "33.333",
      "shares": "0.300003",
      "amount_usd": "10.00",
      "trading_fee_usd": "0.10",
      "regulatory_fee_usd": "0.01",
      "ppn_usd": "0.01",
      "total_usd": "10.12"
    }
  ],
  "closes": {
    "AAA": [
      {
        "date": "2026-01-05",
        "close": "101"
      },
      {
        "date": "2026-01-06",
        "close": "102.5"
      },
      {
        "date": "2026-01-07",
        "close": "108"
      },
      {
        "date": "2026-01-08",
        "close": "115"
      },
      {
        "date": "2026-01-09",
        "close": "119.25"
      },
      {
        "date": "2026-01-12",
        "close": "121"
      },
      {
        "date": "2026-01-13",
        "close": "118.4"
      }
    ],
    "BBB": [
      {
        "date": "2026-01-06",
        "close": "51"
      },
      {
        "date": "2026-01-07",
        "close": "50"
      },
      {
        "date": "2026-01-08",
        "close": "52"
      },
      {
        "date": "2026-01-09",
        "close": "53.3"
      }
    ],
    "EEE": [
      {
        "date": "2026-01-13",
        "close": "34.1"
      }
    ]
  },
  "sessions": [
    {
      "executed_at": "2026-01-05T21:30:00+07:00",
      "session": "2026-01-05"
    },
    {
      "executed_at": "2026-01-06T22:00:00+07:00",
      "session": "2026-01-06"
    },
    {
      "executed_at": "2026-01-08T03:30:00+07:00",
      "session": "2026-01-07"
    },
    {
      "executed_at": "2026-01-09T21:45:00+07:00",
      "session": "2026-01-09"
    },
    {
      "executed_at": "2026-01-12T21:40:00+07:00",
      "session": "2026-01-12"
    },
    {
      "executed_at": "2026-01-12T21:50:00+07:00",
      "session": "2026-01-12"
    },
    {
      "executed_at": "2026-01-13T22:00:00+07:00",
      "session": "2026-01-13"
    },
    {
      "executed_at": "2026-01-13T22:00:00+07:00",
      "session": "2026-01-13"
    },
    {
      "executed_at": "2026-01-13T21:35:00+07:00",
      "session": "2026-01-13"
    },
    {
      "executed_at": "2026-01-13T23:00:00+07:00",
      "session": "2026-01-13"
    },
    {
      "executed_at": "2026-03-09T03:59:00+07:00",
      "session": "2026-03-08"
    },
    {
      "executed_at": "2026-07-01T20:30:00+07:00",
      "session": "2026-07-01"
    }
  ],
  "expected": {
    "positions": [
      {
        "symbol": "AAA",
        "shares": "1.500000000",
        "cost_usd": "155.40"
      },
      {
        "symbol": "CCC",
        "shares": "2.963000000",
        "cost_usd": "30.12"
      },
      {
        "symbol": "EEE",
        "shares": "0.300003000",
        "cost_usd": "10.12"
      }
    ],
    "realized_usd": "25.87",
    "fees_usd": "2.19",
    "points": [
      {
        "date": "2026-01-02",
        "value_usd": "0.00",
        "cost_usd": "0.00",
        "realized_usd": "0.00",
        "unrealized_usd": "0.00",
        "pnl_usd": "0.00",
        "fees_usd": "0.00"
      },
      {
        "date": "2026-01-05",
        "value_usd": "202.00",
        "cost_usd": "200.50",
        "realized_usd": "0.00",
        "unrealized_usd": "1.50",
        "pnl_usd": "1.50",
        "fees_usd": "0.50"
      },
      {
        "date": "2026-01-06",
        "value_usd": "230.50",
        "cost_usd": "225.88",
        "realized_usd": "0.00",
        "unrealized_usd": "4.62",
        "pnl_usd": "4.62",
        "fees_usd": "0.63"
      },
      {
        "date": "2026-01-07",
        "value_usd": "349.00",
        "cost_usd": "336.18",
        "realized_usd": "0.00",
        "unrealized_usd": "12.82",
        "pnl_usd": "12.82",
        "fees_usd": "0.93"
      },
      {
        "date": "2026-01-08",
        "value_usd": "371.00",
        "cost_usd": "336.18",
        "realized_usd": "0.00",
        "unrealized_usd": "34.82",
        "pnl_usd": "34.82",
        "fees_usd": "0.93"
      },
      {
        "date": "2026-01-09",
        "value_usd": "205.53",
        "cost_usd": "180.78",
        "realized_usd": "24.13",
        "unrealized_usd": "24.75",
        "pnl_usd": "48.88",
        "fees_usd": "1.40"
      },
      {
        "date": "2026-01-10",
        "value_usd": "205.53",
        "cost_usd": "180.78",
        "realized_usd": "24.13",
        "unrealized_usd": "24.75",
        "pnl_usd": "48.88",
        "fees_usd": "1.40"
      },
      {
        "date": "2026-01-12",
        "value_usd": "211.50",
        "cost_usd": "185.52",
        "realized_usd": "26.13",
        "unrealized_usd": "25.98",
        "pnl_usd": "52.10",
        "fees_usd": "1.68"
      },
      {
        "date": "2026-01-13",
        "value_usd": "217.83",
        "cost_usd": "195.64",
        "realized_usd": "25.87",
        "unrealized_usd": "22.19",
        "pnl_usd": "48.05",
        "fees_usd": "2.19"
      }
    ]
  }
}
````

**File:** `web/lib/sean/ledger.test.ts:1` (new)
**Code:**
````ts
import { describe, expect, it } from 'vitest';
import fixture from './fixtures/ledger.json';
import { buildLedger, orderSession, pnlAt, pnlSeries, type Close, type LedgerOrder } from './ledger';
import { fixed } from './money';

// The fixture is shared with the engine (Phase 4's pytest): snake_case keys, numbers as strings.
const orders: LedgerOrder[] = fixture.orders.map(o => ({
  id: o.id,
  side: o.side as LedgerOrder['side'],
  symbol: o.symbol,
  executedAt: o.executed_at,
  price: Number(o.price),
  shares: Number(o.shares),
  totalUsd: Number(o.total_usd),
  tradingFeeUsd: Number(o.trading_fee_usd),
  regulatoryFeeUsd: Number(o.regulatory_fee_usd),
  ppnUsd: Number(o.ppn_usd),
}));
const closes: Close[] = Object.entries(fixture.closes as Record<string, { date: string; close: string }[]>).flatMap(
  ([symbol, rows]) => rows.map(r => ({ symbol, date: r.date, close: Number(r.close) })),
);

describe('the shared ledger fixture', () => {
  it('places every order in its New York session', () => {
    for (const s of fixture.sessions) expect(orderSession(s.executed_at), s.executed_at).toBe(s.session);
  });

  it('reproduces the daily points to the cent', () => {
    const dates = fixture.expected.points.map(p => p.date);
    const got = pnlSeries(orders, closes, dates).map(p => ({
      date: p.date,
      value_usd: fixed(p.valueUsd, 2),
      cost_usd: fixed(p.costUsd, 2),
      realized_usd: fixed(p.realizedUsd, 2),
      unrealized_usd: fixed(p.unrealizedUsd, 2),
      pnl_usd: fixed(p.pnlUsd, 2),
      fees_usd: fixed(p.feesUsd, 2),
    }));
    expect(got).toEqual(fixture.expected.points);
  });

  it('reproduces the open positions and totals after every order', () => {
    const book = buildLedger(orders);
    expect(book.holdings.map(h => ({ symbol: h.symbol, shares: fixed(h.shares, 9), cost_usd: fixed(h.costUsd, 2) }))).toEqual(
      fixture.expected.positions,
    );
    expect(fixed(book.realizedUsd, 2)).toBe(fixture.expected.realized_usd);
    expect(fixed(book.feesUsd, 2)).toBe(fixture.expected.fees_usd);
  });
});

describe('buildLedger', () => {
  it('stops at a session date and reports average and last prices', () => {
    expect(buildLedger(orders, '2026-01-09')).toEqual({
      holdings: [
        { symbol: 'AAA', shares: 1.5, costUsd: 155.4, avgPrice: 103.6, lastOrderPrice: 120 },
        { symbol: 'BBB', shares: 0.5, costUsd: 25.38, avgPrice: 50.76, lastOrderPrice: 50.5 },
      ],
      realizedUsd: 24.13,
      feesUsd: 1.4,
    });
  });

  it('rounds the average price to 6 decimals', () => {
    const ccc = buildLedger(orders).holdings.find(h => h.symbol === 'CCC');
    expect(ccc).toEqual({ symbol: 'CCC', shares: 2.963, costUsd: 30.12, avgPrice: 10.165373, lastOrderPrice: 10.123456 });
  });
});

describe('ledger rules', () => {
  const buy = (id: number, symbol: string, at: string, shares: number, total: number, price = 10): LedgerOrder => ({
    id, side: 'buy', symbol, executedAt: at, price, shares, totalUsd: total, tradingFeeUsd: 0.1, regulatoryFeeUsd: 0.02, ppnUsd: 0.01,
  });
  const sell = (id: number, symbol: string, at: string, shares: number, total: number, price = 10): LedgerOrder => ({
    ...buy(id, symbol, at, shares, total, price), side: 'sell',
  });

  it('is all zeros with no orders', () => {
    expect(buildLedger([])).toEqual({ holdings: [], realizedUsd: 0, feesUsd: 0 });
    expect(pnlAt([], [], '2026-10-07')).toEqual({
      date: '2026-10-07', valueUsd: 0, costUsd: 0, realizedUsd: 0, unrealizedUsd: 0, pnlUsd: 0, feesUsd: 0,
    });
  });

  it('ignores a sell of a stock Sean never saw bought, except for its fees', () => {
    const book = buildLedger([sell(1, 'XYZ', '2026-10-07T21:00:00+07:00', 1, 9.87)]);
    expect(book).toEqual({ holdings: [], realizedUsd: 0, feesUsd: 0.13 });
  });

  it('closes a position when a full sell leaves only dust', () => {
    const book = buildLedger([
      buy(1, 'XYZ', '2026-10-07T21:00:00+07:00', 0.1 + 0.2, 3.13),
      sell(2, 'XYZ', '2026-10-07T22:00:00+07:00', 0.3, 3.5),
    ]);
    expect(book.holdings).toEqual([]);
    expect(book.realizedUsd).toBe(0.37);
  });

  it('values a holding at its last order price until a close exists', () => {
    const orders1 = [buy(1, 'XYZ', '2026-10-07T21:00:00+07:00', 2, 20.13, 10)];
    expect(pnlAt(orders1, [], '2026-10-07').valueUsd).toBe(20);
    expect(pnlAt(orders1, [{ symbol: 'XYZ', date: '2026-10-07', close: 11 }], '2026-10-07').valueUsd).toBe(22);
    expect(pnlAt(orders1, [{ symbol: 'XYZ', date: '2026-10-08', close: 11 }], '2026-10-07').valueUsd).toBe(20);
  });

  it('sorts dates and drops duplicates in a series', () => {
    const s = pnlSeries([], [], ['2026-10-08', '2026-10-07', '2026-10-08']);
    expect(s.map(p => p.date)).toEqual(['2026-10-07', '2026-10-08']);
  });

  it('refuses a timestamp it cannot read', () => {
    expect(() => orderSession('yesterday')).toThrow('not a timestamp');
  });
});
````
**Impact:** Phase 4's `engine/tests/test_sean_ledger.py` reads `REPO_ROOT/web/lib/sean/fixtures/ledger.json`; changing this file changes that test's expectations.

### Step 10: The zip reader
**File:** `web/lib/sean/unzip.ts:1` (new)
**Change:** central-directory zip reader, no dependency. The inflater is injectable because **Node 20.11 (this machine) has no `DecompressionStream('deflate-raw')`** (verified: `ERR_INVALID_ARG_VALUE`); browsers do. Tests and the smoke script pass `node:zlib`'s `inflateRawSync`. Every entry is size- and CRC-checked.
**Code:**
````ts
/**
 * Read a .zip of screenshots in the browser, with no dependency: the owner can hand Sean the zip
 * WhatsApp gave him (gotrade_order_summary_screenshots.zip: 30 JPEGs, stored) as is.
 *
 * Reads the central directory (so entries written with a trailing data descriptor work), then
 * each entry: method 0 (stored) is copied, method 8 (deflate) goes through `inflateRaw`, which
 * defaults to the browser's DecompressionStream('deflate-raw'). Tests and the smoke script pass
 * node:zlib's inflateRawSync instead (Node 20.11 has no 'deflate-raw' DecompressionStream).
 * Every entry's size and CRC-32 are checked. Directories, __MACOSX/, AppleDouble "._" files and
 * .DS_Store are skipped. Zip64, encryption and other methods are refused in plain words.
 *
 * Pure: no imports.
 */

export class ZipError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ZipError';
  }
}

export type ZipEntry = { name: string; bytes: Uint8Array };
export type InflateRaw = (data: Uint8Array) => Promise<Uint8Array>;

/** Raw-deflate with the browser's own DecompressionStream. */
export const inflateRawWeb: InflateRaw = async data => {
  const stream = new Blob([data.slice()]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
  return new Uint8Array(await new Response(stream).arrayBuffer());
};

/** Files Sean can read as a receipt. */
export const IMAGE_NAME = /\.(jpe?g|png|webp)$/i;

/** The file name without its folders: 'shots/a.jpeg' -> 'a.jpeg'. */
export function baseName(name: string): string {
  return name.slice(name.lastIndexOf('/') + 1);
}

/** Entries that are never content: folders and macOS litter. */
export function isJunkEntry(name: string): boolean {
  const base = baseName(name);
  return name.endsWith('/') || name.startsWith('__MACOSX/') || base.startsWith('._') || base === '.DS_Store';
}

let CRC_TABLE: Uint32Array | null = null;

/** CRC-32 (IEEE), as zip stores it. */
export function crc32(bytes: Uint8Array): number {
  if (CRC_TABLE === null) {
    CRC_TABLE = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      CRC_TABLE[n] = c >>> 0;
    }
  }
  let c = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

const SIG_EOCD = 0x06054b50;
const SIG_CENTRAL = 0x02014b50;
const SIG_LOCAL = 0x04034b50;
const DAMAGED = 'This zip file is damaged.';
const ZIP64 = 'This zip is too large to open here.';

function findEndOfCentralDirectory(view: DataView): number {
  const last = view.byteLength - 22;
  const first = Math.max(0, last - 0xffff);
  for (let i = last; i >= first; i--) {
    if (view.getUint32(i, true) === SIG_EOCD) return i;
  }
  throw new ZipError('This is not a zip file.');
}

/**
 * Every content entry `accept` keeps (all of them by default), in the zip's own order.
 * Throws ZipError with a plain-words message when the zip cannot be read.
 */
export async function readZip(
  input: ArrayBuffer | Uint8Array,
  opts: { inflateRaw?: InflateRaw; accept?: (name: string) => boolean } = {},
): Promise<ZipEntry[]> {
  const buf = input instanceof Uint8Array ? input : new Uint8Array(input);
  if (buf.byteLength < 22) throw new ZipError('This is not a zip file.');
  const view = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  const inflate = opts.inflateRaw ?? inflateRawWeb;
  const accept = opts.accept ?? (() => true);
  const utf8 = new TextDecoder('utf-8');

  const eocd = findEndOfCentralDirectory(view);
  const count = view.getUint16(eocd + 10, true);
  const dirSize = view.getUint32(eocd + 12, true);
  const dirOffset = view.getUint32(eocd + 16, true);
  if (count === 0xffff || dirSize === 0xffffffff || dirOffset === 0xffffffff) throw new ZipError(ZIP64);
  if (dirOffset + dirSize > eocd) throw new ZipError(DAMAGED);

  const out: ZipEntry[] = [];
  let p = dirOffset;
  for (let i = 0; i < count; i++) {
    if (p + 46 > eocd || view.getUint32(p, true) !== SIG_CENTRAL) throw new ZipError(DAMAGED);
    const flags = view.getUint16(p + 8, true);
    const method = view.getUint16(p + 10, true);
    const crc = view.getUint32(p + 16, true);
    const compressedSize = view.getUint32(p + 20, true);
    const size = view.getUint32(p + 24, true);
    const nameLength = view.getUint16(p + 28, true);
    const extraLength = view.getUint16(p + 30, true);
    const commentLength = view.getUint16(p + 32, true);
    const localOffset = view.getUint32(p + 42, true);
    const name = utf8.decode(buf.subarray(p + 46, p + 46 + nameLength));
    p += 46 + nameLength + extraLength + commentLength;

    if (isJunkEntry(name) || !accept(name)) continue;
    if (flags & 1) throw new ZipError(`${baseName(name)} is password-protected.`);
    if (compressedSize === 0xffffffff || size === 0xffffffff || localOffset === 0xffffffff) throw new ZipError(ZIP64);
    if (localOffset + 30 > buf.byteLength || view.getUint32(localOffset, true) !== SIG_LOCAL) {
      throw new ZipError(DAMAGED);
    }
    const start = localOffset + 30 + view.getUint16(localOffset + 26, true) + view.getUint16(localOffset + 28, true);
    const end = start + compressedSize;
    if (end > buf.byteLength) throw new ZipError(DAMAGED);
    const data = buf.subarray(start, end);

    let bytes: Uint8Array;
    if (method === 0) bytes = data.slice();
    else if (method === 8) {
      try {
        bytes = await inflate(data);
      } catch {
        throw new ZipError(`${baseName(name)} is damaged inside the zip.`);
      }
    } else throw new ZipError(`${baseName(name)} is packed in a way this page cannot open.`);

    if (bytes.length !== size || crc32(bytes) !== crc) throw new ZipError(`${baseName(name)} is damaged inside the zip.`);
    out.push({ name, bytes });
  }
  return out;
}
````

**File:** `web/lib/sean/unzip.test.ts:1` (new)
**Change:** a zip written by Python's `zipfile` (so reader and writer cannot share a bug) plus a tiny in-test writer for the cases Python will not produce on demand (data descriptor, corruption, encryption flag, unknown method, truncation).
**Code:**
````ts
import { deflateRawSync, inflateRawSync } from 'node:zlib';
import { describe, expect, it } from 'vitest';
import { IMAGE_NAME, ZipError, baseName, crc32, isJunkEntry, readZip, type InflateRaw } from './unzip';

// Node 20.11 has no DecompressionStream('deflate-raw'); the browser does. Tests inject zlib.
const inflateRaw: InflateRaw = async data => new Uint8Array(inflateRawSync(data));
const text = (b: Uint8Array) => new TextDecoder().decode(b);
const bytes = (s: string) => new TextEncoder().encode(s);

/**
 * Written by Python's zipfile (not by this file's own writer below, so reader and writer cannot
 * share a mistake): a folder entry, receipts/a.jpeg (deflate, 'JPEG-ONE ' x 40), receipts/b.png
 * (stored, 'PNG-TWO'), __MACOSX/receipts/._a.jpeg, .DS_Store, notes.txt (deflate, 'hello').
 */
const PYTHON_ZIP = Uint8Array.from(
  atob(
    'UEsDBBQAAAAAAAAAIQAAAAAAAAAAAAAAAAAJAAAAcmVjZWlwdHMvUEsDBBQAAAAIADa2R11VJYDKEAAAAGgBAAAPAAAAcmVjZWlwdHMvYS5qcGVn8wpwddf193NV8Bpl0JIBAFBLAwQUAAAAAAA2tkddkb9MSwcAAAAHAAAADgAAAHJlY2VpcHRzL2IucG5nUE5HLVRXT1BLAwQUAAAAAAA2tkddOZz7BgQAAAAEAAAAGgAAAF9fTUFDT1NYL3JlY2VpcHRzLy5fYS5qcGVnanVua1BLAwQUAAAAAAA2tkddOZz7BgQAAAAEAAAACQAAAC5EU19TdG9yZWp1bmtQSwMEFAAAAAgANrZHXYamEDYHAAAABQAAAAkAAABub3Rlcy50eHTLSM3JyQcAUEsBAhQDFAAAAAAAAAAhAAAAAAAAAAAAAAAAAAkAAAAAAAAAAAAAAIABAAAAAHJlY2VpcHRzL1BLAQIUAxQAAAAIADa2R11VJYDKEAAAAGgBAAAPAAAAAAAAAAAAAACAAScAAAByZWNlaXB0cy9hLmpwZWdQSwECFAMUAAAAAAA2tkddkb9MSwcAAAAHAAAADgAAAAAAAAAAAAAAgAFkAAAAcmVjZWlwdHMvYi5wbmdQSwECFAMUAAAAAAA2tkddOZz7BgQAAAAEAAAAGgAAAAAAAAAAAAAAgAGXAAAAX19NQUNPU1gvcmVjZWlwdHMvLl9hLmpwZWdQSwECFAMUAAAAAAA2tkddOZz7BgQAAAAEAAAACQAAAAAAAAAAAAAAgAHTAAAALkRTX1N0b3JlUEsBAhQDFAAAAAgANrZHXYamEDYHAAAABQAAAAkAAAAAAAAAAAAAAIAB/gAAAG5vdGVzLnR4dFBLBQYAAAAABgAGAGYBAAAsAQAAAAA=',
  ),
  c => c.charCodeAt(0),
);

type Spec = { name: string; data: Uint8Array; method: 0 | 8; descriptor?: boolean; flags?: number };

/** A minimal zip writer for the edge cases Python will not produce on demand. */
function makeZip(files: Spec[]): Uint8Array {
  const chunks: Uint8Array[] = [];
  const central: Uint8Array[] = [];
  let offset = 0;
  for (const f of files) {
    const name = bytes(f.name);
    const packed = f.method === 8 ? new Uint8Array(deflateRawSync(f.data)) : f.data;
    const crc = crc32(f.data);
    const flags = (f.flags ?? 0) | (f.descriptor ? 8 : 0);
    const local = new DataView(new ArrayBuffer(30));
    local.setUint32(0, 0x04034b50, true);
    local.setUint16(4, 20, true);
    local.setUint16(6, flags, true);
    local.setUint16(8, f.method, true);
    local.setUint32(14, f.descriptor ? 0 : crc, true);
    local.setUint32(18, f.descriptor ? 0 : packed.length, true);
    local.setUint32(22, f.descriptor ? 0 : f.data.length, true);
    local.setUint16(26, name.length, true);
    const head = new Uint8Array(local.buffer);
    const descriptor = new DataView(new ArrayBuffer(f.descriptor ? 16 : 0));
    if (f.descriptor) {
      descriptor.setUint32(0, 0x08074b50, true);
      descriptor.setUint32(4, crc, true);
      descriptor.setUint32(8, packed.length, true);
      descriptor.setUint32(12, f.data.length, true);
    }
    const cen = new DataView(new ArrayBuffer(46));
    cen.setUint32(0, 0x02014b50, true);
    cen.setUint16(4, 20, true);
    cen.setUint16(6, 20, true);
    cen.setUint16(8, flags, true);
    cen.setUint16(10, f.method, true);
    cen.setUint32(16, crc, true);
    cen.setUint32(20, packed.length, true);
    cen.setUint32(24, f.data.length, true);
    cen.setUint16(28, name.length, true);
    cen.setUint32(42, offset, true);
    central.push(new Uint8Array(cen.buffer), name);
    for (const c of [head, name, packed, new Uint8Array(descriptor.buffer)]) {
      chunks.push(c);
      offset += c.length;
    }
  }
  const dirSize = central.reduce((n, c) => n + c.length, 0);
  const end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true);
  end.setUint16(8, files.length, true);
  end.setUint16(10, files.length, true);
  end.setUint32(12, dirSize, true);
  end.setUint32(16, offset, true);
  const all = [...chunks, ...central, new Uint8Array(end.buffer)];
  const out = new Uint8Array(all.reduce((n, c) => n + c.length, 0));
  let p = 0;
  for (const c of all) {
    out.set(c, p);
    p += c.length;
  }
  return out;
}

describe('readZip', () => {
  it('reads a zip written by a real tool, skipping folders and macOS litter', async () => {
    const entries = await readZip(PYTHON_ZIP, { inflateRaw });
    expect(entries.map(e => e.name)).toEqual(['receipts/a.jpeg', 'receipts/b.png', 'notes.txt']);
    expect(text(entries[0].bytes)).toBe('JPEG-ONE '.repeat(40));
    expect(text(entries[1].bytes)).toBe('PNG-TWO');
    expect(text(entries[2].bytes)).toBe('hello');
  });

  it('keeps only what `accept` keeps', async () => {
    const entries = await readZip(PYTHON_ZIP.buffer, { inflateRaw, accept: n => IMAGE_NAME.test(n) });
    expect(entries.map(e => baseName(e.name))).toEqual(['a.jpeg', 'b.png']);
  });

  it('reads entries whose sizes live in a trailing data descriptor', async () => {
    const zip = makeZip([{ name: 'r.jpg', data: bytes('x'.repeat(500)), method: 8, descriptor: true }]);
    const [entry] = await readZip(zip, { inflateRaw });
    expect(text(entry.bytes)).toBe('x'.repeat(500));
  });

  it('refuses a corrupted entry by its CRC', async () => {
    const zip = makeZip([{ name: 'r.jpg', data: bytes('receipt'), method: 0 }]);
    zip[30 + 'r.jpg'.length] ^= 0xff;
    await expect(readZip(zip, { inflateRaw })).rejects.toThrow('r.jpg is damaged inside the zip.');
  });

  it('refuses a deflate stream that does not inflate', async () => {
    const zip = makeZip([{ name: 'r.jpg', data: bytes('receipt receipt'), method: 8 }]);
    zip.fill(0xff, 30 + 5, 30 + 5 + 4);
    await expect(readZip(zip, { inflateRaw })).rejects.toThrow(ZipError);
  });

  it('refuses password-protected entries and unknown methods in plain words', async () => {
    const locked = makeZip([{ name: 'r.jpg', data: bytes('a'), method: 0, flags: 1 }]);
    await expect(readZip(locked, { inflateRaw })).rejects.toThrow('r.jpg is password-protected.');
    const odd = makeZip([{ name: 'r.jpg', data: bytes('a'), method: 0 }]);
    new DataView(odd.buffer).setUint16(odd.length - 22 - 46 - 5 + 10, 12, true);
    await expect(readZip(odd, { inflateRaw })).rejects.toThrow('r.jpg is packed in a way this page cannot open.');
  });

  it('refuses something that is not a zip', async () => {
    await expect(readZip(bytes('just a jpeg, honestly'), { inflateRaw })).rejects.toThrow('This is not a zip file.');
    await expect(readZip(new Uint8Array(4), { inflateRaw })).rejects.toThrow('This is not a zip file.');
  });

  it('refuses a truncated zip', async () => {
    const zip = makeZip([{ name: 'r.jpg', data: bytes('receipt'), method: 0 }]);
    const cut = zip.slice(10);
    await expect(readZip(cut, { inflateRaw })).rejects.toThrow(ZipError);
  });
});

describe('helpers', () => {
  it('computes the standard CRC-32', () => {
    expect(crc32(bytes('123456789'))).toBe(0xcbf43926);
    expect(crc32(new Uint8Array(0))).toBe(0);
  });
  it('knows junk entries and image names', () => {
    expect(['a/', '__MACOSX/a.jpg', 'x/._a.jpg', '.DS_Store', 'x/.DS_Store'].every(isJunkEntry)).toBe(true);
    expect(isJunkEntry('shots/WhatsApp Image 2026-10-07 at 10.14.45 PM.jpeg')).toBe(false);
    expect(['a.jpg', 'a.JPEG', 'a.png', 'a.webp'].every(n => IMAGE_NAME.test(n))).toBe(true);
    expect(IMAGE_NAME.test('a.txt')).toBe(false);
  });
});
````
**Impact:** none until Phase 2's uploader calls `readZip`.

### Step 11: The live smoke script
**File:** `web/scripts/sean-vision-smoke.mjs:1` (new)
**Change:** runs the real `readOrder` on real screenshots (a zip, a folder, or files) and, with `--truth`, compares each result to the hand-checked transcription. Node 20 cannot import TypeScript, so it runs under **`npx vite-node`** (shipped with vitest 3 as a dependency; no `package.json` change). It loads `.env.local` itself (Node 20.11 has no `process.loadEnvFile`). `web/tsconfig.json` excludes `scripts/`, so `tsc` never sees it; nothing in CI runs it.
**Code:**
````js
// Live check of Sean's screenshot reader against real Gotrade Order Summary screenshots.
//
// NOT run in CI: it calls glm-4.6v (spends tokens) and needs the reader's keys. It runs the very
// modules the upload route runs (lib/sean/readOrder.ts and friends), through vite-node, which
// ships with vitest and understands TypeScript and the extensionless imports Node 20 cannot.
//
// From web/:
//   npx vite-node scripts/sean-vision-smoke.mjs -- <zip | folder | image ...> \
//       [--truth ../.workflows/plan/sean-gotrade-tracker/screenshots_truth.json] \
//       [--env .env.local] [--limit N]
//
// Example, the owner's 30 receipts:
//   npx vite-node scripts/sean-vision-smoke.mjs -- ../../gotrade_order_summary_screenshots.zip \
//       --truth ../.workflows/plan/sean-gotrade-tracker/screenshots_truth.json
//
// Prints one line per picture (what was read, prompt tokens against the floor, tries, seconds),
// then a summary. With --truth it compares symbol, side, date/time, shares, amount, the three
// fees and total to the hand-checked transcription. Exits 1 on any failure or mismatch.
import { readFile, readdir, stat } from 'node:fs/promises';
import { basename, join, resolve } from 'node:path';
import { inflateRawSync } from 'node:zlib';
import { readOrder, visionDeps } from '../lib/sean/readOrder.ts';
import { IMAGE_NAME, baseName, readZip } from '../lib/sean/unzip.ts';
import { visionConfigFromEnv } from '../lib/sean/vision.ts';

const CONCURRENCY = 3;

function parseArgs(argv) {
  const out = { inputs: [], truth: null, env: '.env.local', limit: Infinity };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--') continue;
    else if (a === '--truth') out.truth = argv[++i];
    else if (a === '--env') out.env = argv[++i];
    else if (a === '--limit') out.limit = Number(argv[++i]);
    else out.inputs.push(a);
  }
  return out;
}

/** KEY=value lines into process.env, without overriding what is already set. */
async function loadEnvFile(path) {
  let text;
  try {
    text = await readFile(path, 'utf8');
  } catch {
    return;
  }
  for (const line of text.split(/\r?\n/)) {
    const m = /^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/.exec(line);
    if (!m || line.trimStart().startsWith('#')) continue;
    const value = m[2].replace(/^(['"])(.*)\1$/, '$2');
    if (process.env[m[1]] === undefined) process.env[m[1]] = value;
  }
}

/** Every picture named by the arguments, as { name, bytes }. */
async function collect(inputs) {
  const pictures = [];
  for (const input of inputs) {
    const path = resolve(input);
    const info = await stat(path);
    if (info.isDirectory()) {
      for (const name of (await readdir(path)).sort()) {
        if (IMAGE_NAME.test(name)) pictures.push({ name, bytes: new Uint8Array(await readFile(join(path, name))) });
      }
    } else if (path.toLowerCase().endsWith('.zip')) {
      const entries = await readZip(new Uint8Array(await readFile(path)), {
        inflateRaw: async data => new Uint8Array(inflateRawSync(data)),
        accept: name => IMAGE_NAME.test(name),
      });
      for (const e of entries) pictures.push({ name: baseName(e.name), bytes: e.bytes });
    } else {
      pictures.push({ name: basename(path), bytes: new Uint8Array(await readFile(path)) });
    }
  }
  return pictures;
}

const near = (a, b, tol) => typeof a === 'number' && typeof b === 'number' && Math.abs(a - b) <= tol;

/** Differences between what was read and the hand-checked row. */
function compare(order, t) {
  const diffs = [];
  const want = {
    symbol: t.ticker,
    side: t.side,
    executedAt: `${t.date}T${t.time_hhmm}:00+07:00`,
  };
  for (const [k, v] of Object.entries(want)) if (order[k] !== v) diffs.push(`${k} ${order[k]} != ${v}`);
  const nums = [
    ['shares', order.shares, t.shares_num, 1e-9],
    ['price', order.price, t.price_num, 1e-6],
    ['amountUsd', order.amountUsd, t.amount_num, 0.001],
    ['tradingFeeUsd', order.tradingFeeUsd, Math.abs(t.trading_fee_num), 0.001],
    ['regulatoryFeeUsd', order.regulatoryFeeUsd, Math.abs(t.regulatory_fee_num), 0.001],
    ['ppnUsd', order.ppnUsd, Math.abs(t.ppn_num), 0.001],
    ['totalUsd', order.totalUsd, t.total_num, 0.001],
  ];
  for (const [k, got, exp, tol] of nums) if (!near(got, exp, tol)) diffs.push(`${k} ${got} != ${exp}`);
  if ((order.netProfitUsd ?? null) !== (t.net_profit_num ?? null)) diffs.push(`netProfitUsd ${order.netProfitUsd} != ${t.net_profit_num}`);
  if (order.fills.length !== t.partial_fills.length) diffs.push(`fills ${order.fills.length} != ${t.partial_fills.length}`);
  return diffs;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.inputs.length === 0) {
    console.error('usage: npx vite-node scripts/sean-vision-smoke.mjs -- <zip|folder|image...> [--truth file] [--env file] [--limit N]');
    process.exit(2);
  }
  await loadEnvFile(resolve(args.env));
  const cfg = visionConfigFromEnv(process.env);
  if (cfg === null) {
    console.error('LLM_API_KEY, LLM_VISION_BASE_URL and LLM_VISION_MODEL must be set (and not the /api/anthropic URL).');
    process.exit(2);
  }
  const truth = args.truth ? new Map(JSON.parse(await readFile(resolve(args.truth), 'utf8')).map(r => [r.filename, r])) : null;
  const pictures = (await collect(args.inputs)).slice(0, args.limit);
  console.log(`${pictures.length} picture(s), model ${cfg.model}, ${CONCURRENCY} at a time`);

  const deps = visionDeps(cfg);
  const results = new Array(pictures.length);
  let next = 0;
  async function worker() {
    while (next < pictures.length) {
      const i = next++;
      const p = pictures[i];
      const started = Date.now();
      const out = await readOrder(deps, Buffer.from(p.bytes).toString('base64'));
      const seconds = ((Date.now() - started) / 1000).toFixed(1);
      const tokens = out.promptTokens === null ? 'tokens ?' : `tokens ${out.promptTokens} (floor ${out.floor})`;
      let diffs = [];
      if (out.ok && truth) {
        const t = truth.get(p.name);
        diffs = t ? compare(out.order, t) : ['no truth row for this file'];
      }
      results[i] = { ok: out.ok && diffs.length === 0, out };
      if (out.ok) {
        const o = out.order;
        console.log(
          `${diffs.length ? 'DIFF' : 'ok  '} ${o.symbol.padEnd(5)} ${o.side.padEnd(4)} ${String(o.shares).padEnd(12)} ` +
            `total $${o.totalUsd.toFixed(2).padStart(9)}  ${tokens}  ${out.attempts} try  ${seconds}s  ${p.name}`,
        );
        for (const d of diffs) console.log(`       ${d}`);
      } else {
        console.log(`FAIL ${out.code.padEnd(11)} ${tokens}  ${out.attempts} try  ${seconds}s  ${p.name}`);
        console.log(`       ${out.message}`);
        if (out.detail) console.log(`       ${out.detail}`);
        for (const issue of out.issues.slice(1)) console.log(`       ${issue}`);
      }
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));

  const good = results.filter(r => r.ok).length;
  const repaired = results.filter(r => r.out.ok && r.out.attempts === 2).length;
  const margins = results.filter(r => r.out.ok).map(r => r.out.promptTokens - r.out.floor);
  console.log(
    `\n${good}/${results.length} read${truth ? ' and matched' : ''}; ${repaired} needed the repair; ` +
      (margins.length ? `smallest margin over the token floor: ${Math.min(...margins)} tokens` : 'no token margins'),
  );
  process.exit(good === results.length ? 0 : 1);
}

await main();
````
**Impact:** spends ~2,600 glm-4.6v tokens per picture when run by hand. Never run by CI.

## Verification

**Build:** `cd web && npm ci && npx tsc --noEmit && npx next build`
**Tests:**
- `cd web && npx vitest run` — the new `lib/sean` suites add 92 tests (7 files) to the existing suite; all green.
- `cd engine && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]' && PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres .venv/bin/pytest tests/test_migrate.py` — applies 001-015 on a fresh schema (the migration's only automated check; no engine code changes in this phase).
**Manual check (live, optional, costs tokens):**
````
cd web
cp /home/miftah/seer/web/.env.local .env.local   # the worktree has no .env.local; it is gitignored
npx vite-node scripts/sean-vision-smoke.mjs -- /home/miftah/seer/gotrade_order_summary_screenshots.zip \
    --truth ../.workflows/plan/sean-gotrade-tracker/screenshots_truth.json
````
Expected (measured while planning): `30/30 read and matched; 0 needed the repair; smallest margin over the token floor: 1210 tokens`. `npm run db:migrate` against Neon is **not** part of this phase.
**Exit criteria:**
- `tsc --noEmit` clean; `vitest run` green, including all 4 fixture receipts converting to their expected `SeanOrder` and the ledger reproducing `fixtures/ledger.json` to the cent.
- `015_sean.sql` applies after 001-014 on a fresh schema and re-applies as a no-op.
- `next build` green (no page imports the new modules yet).
- No file outside `db/migrations/015_sean.sql`, `web/lib/sean/` and `web/scripts/sean-vision-smoke.mjs` changed.

## Handoffs

**Reconciled (round 1):** every handoff below has been applied to the dependent plan; this phase's
exports are the binding contract and did not change. The only edit made to this file at
reconciliation is the `sean_link.since` column comment in Step 1 (a comment, no DDL change): the
plan's start date is compared with an order's New York trade date (`orderSession`), the same date
the ledger uses (index Decisions, "Which date an order counts on").

- **Phase 2 (R1, R3) — interface differs from what its plan assumed; the reconciler should adjust Phase 2, not this phase:**
  - `readOrder(deps, imageB64, budgetMs?)` with `deps = visionDeps(cfg)` — not `readOrder(imageB64, { config, fetchImpl, timeoutMs })`. The budget (default 55 s) already covers vision + repair.
  - Result is `ReadOrderOutcome` (`ok`, `code`, `message`, `raw`, `detail`), never a throw for model problems; use `isReaderDown(code)` for 502 vs 422 instead of catching `VisionTokenFloorError`/`VisionTransportError` in the route.
  - Zip: `readZip(bytes, { accept: n => IMAGE_NAME.test(n) })`, not `readZipEntries(zip)`; returns `{ name, bytes }[]`.
  - `toOrder` already refuses non-Filled statuses; the route's own status check is unnecessary.
  - Copy `LLM_API_KEY`, `LLM_VISION_BASE_URL`, `LLM_VISION_MODEL` to Vercel (already Phase 2's job).
  - Image re-encoding in the browser is optional: the owner's JPEGs are ~60 KB and were read 30/30 as is. If Phase 2 downscales, keep the short edge >= 560 px (run-insights' measured 108/108 setting) and re-run Step 11's script; a smaller image lowers prompt_tokens toward the floor.
- **Phase 3 (R2) — interface differs from what its plan assumed:** `buildLedger`/`pnlSeries`/`pnlAt` take `LedgerOrder[]` (needs `id`), closes are `Close[]` (flat `{symbol, date, close}`), and `PnlPoint` fields are `valueUsd, costUsd, realizedUsd, unrealizedUsd, pnlUsd, feesUsd` (not `pnl`, `fees`). Holdings come from `buildLedger(...).holdings` with `costUsd`, `avgPrice`, `lastOrderPrice`. The last-order-price fallback Phase 3 relies on is implemented and tested.
- **Phase 4 (R2):** mirror contract B exactly as written in this plan, **including point 5 (pro-rata oversell; a sell of a never-bought stock adds only fees)**, which differs from Phase 4's current assumption. The fixture already has Phase 4's schema; `orders[]` rows carry no `net_profit_usd` key (the ledger never reads it). The Appendix script is a working Decimal reference.
- **Phase 7 (R5):** `sean_orders` stores fee magnitudes and `amount_usd` per order, which is all `calibrate` needs.
- **Not done anywhere (flag, not scope):** `web/package_readme.md` gains a Sean section at completion (completion-handler / readme-updater).

## Risks

- **vite-node is a transitive dependency.** If vitest stops shipping it, the smoke script needs `tsx` or Node >= 22.18 (type stripping). It is a manual tool only, so nothing breaks in CI.
- **Partially filled orders are refused.** If Gotrade ever shows a *cancelled* partially-filled limit order (real shares bought, status not "Filled"), the owner cannot record it. Refusing is the safe default (a still-open order would otherwise be stored twice with different share counts); revisit with a real receipt.
- **The first live run in the sandbox failed with `transport`** before succeeding on retry (likely the network sandbox warming up); every later call worked. Phase 2's uploader should let the owner retry a failed file.
- **TS floats vs Python Decimal.** The TS ledger rounds float results; a value within ~1e-12 of a half-cent could round one cent differently from Python. `sean_equity` (Python) is the source of truth for the graph; the TS series is only the fallback before the first nightly run.

## Rollback

Delete the 20 new files. Nothing imports them in this phase, so the tree builds as before. If the migration was already applied anywhere: `DROP TABLE sean_equity, sean_marks, sean_reminder_marks, sean_link, sean_orders; DELETE FROM schema_migrations WHERE name = '015_sean.sql';` (no other table references them).

## Appendix: how the ledger fixture's expected values were computed

A Decimal reference for contract B (also a working model for Phase 4's `ledger.py`). Run with
`python3 -I make_ledger_fixture.py web/lib/sean/fixtures/ledger.json` to regenerate the fixture
byte for byte. Not committed.

````python
import json, sys
from decimal import Decimal as D, ROUND_HALF_UP
from datetime import datetime
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York")

orders = [
 dict(id=1, side="buy", symbol="AAA", executed_at="2026-01-05T21:30:00+07:00", price="100", shares="2", amount_usd="200.00", trading_fee_usd="0.40", regulatory_fee_usd="0.05", ppn_usd="0.05", total_usd="200.50"),
 dict(id=2, side="buy", symbol="BBB", executed_at="2026-01-06T22:00:00+07:00", price="50.5", shares="0.5", amount_usd="25.25", trading_fee_usd="0.10", regulatory_fee_usd="0.02", ppn_usd="0.01", total_usd="25.38"),
 dict(id=3, side="buy", symbol="AAA", executed_at="2026-01-08T03:30:00+07:00", price="110", shares="1", amount_usd="110.00", trading_fee_usd="0.22", regulatory_fee_usd="0.05", ppn_usd="0.03", total_usd="110.30"),
 dict(id=4, side="sell", symbol="AAA", executed_at="2026-01-09T21:45:00+07:00", price="120", shares="1.5", amount_usd="180.00", trading_fee_usd="0.36", regulatory_fee_usd="0.06", ppn_usd="0.05", total_usd="179.53"),
 dict(id=5, side="sell", symbol="BBB", executed_at="2026-01-12T21:40:00+07:00", price="55", shares="0.6", amount_usd="33.00", trading_fee_usd="0.10", regulatory_fee_usd="0.04", ppn_usd="0.01", total_usd="32.85"),
 dict(id=6, side="buy", symbol="CCC", executed_at="2026-01-12T21:50:00+07:00", price="10.123456", shares="2.963", amount_usd="29.99", trading_fee_usd="0.10", regulatory_fee_usd="0.02", ppn_usd="0.01", total_usd="30.12"),
 # same instant: the buy (id 7) must replay before the sell (id 8); listed sell-first on purpose
 dict(id=8, side="sell", symbol="DDD", executed_at="2026-01-13T22:00:00+07:00", price="20", shares="1", amount_usd="20.00", trading_fee_usd="0.10", regulatory_fee_usd="0.02", ppn_usd="0.01", total_usd="19.87"),
 dict(id=7, side="buy", symbol="DDD", executed_at="2026-01-13T22:00:00+07:00", price="20", shares="1", amount_usd="20.00", trading_fee_usd="0.10", regulatory_fee_usd="0.02", ppn_usd="0.01", total_usd="20.13"),
 # a sell of a stock Sean never saw bought (bought before the owner started uploading): only its fees count
 dict(id=10, side="sell", symbol="ZZZ", executed_at="2026-01-13T21:35:00+07:00", price="15", shares="2", amount_usd="30.00", trading_fee_usd="0.10", regulatory_fee_usd="0.02", ppn_usd="0.01", total_usd="29.87"),
 dict(id=9, side="buy", symbol="EEE", executed_at="2026-01-13T23:00:00+07:00", price="33.333", shares="0.300003", amount_usd="10.00", trading_fee_usd="0.10", regulatory_fee_usd="0.01", ppn_usd="0.01", total_usd="10.12"),
]
closes = [
 ("AAA","2026-01-05","101"),("AAA","2026-01-06","102.5"),("AAA","2026-01-07","108"),("AAA","2026-01-08","115"),
 ("AAA","2026-01-09","119.25"),("AAA","2026-01-12","121"),("AAA","2026-01-13","118.4"),
 ("BBB","2026-01-06","51"),("BBB","2026-01-07","50"),("BBB","2026-01-08","52"),("BBB","2026-01-09","53.3"),
 ("EEE","2026-01-13","34.1"),
]
dates = ["2026-01-02","2026-01-05","2026-01-06","2026-01-07","2026-01-08","2026-01-09","2026-01-10","2026-01-12","2026-01-13"]

def session(ts): return datetime.fromisoformat(ts).astimezone(NY).date().isoformat()
def c(x): return str(x.quantize(D("0.01"), rounding=ROUND_HALF_UP))
def q(x, dp): return str(x.quantize(D(1).scaleb(-dp), rounding=ROUND_HALF_UP))

q_orders = sorted(orders, key=lambda o: (datetime.fromisoformat(o["executed_at"]), o["id"]))
def replay(through):
    pos = {}; realized = D(0); fees = D(0)
    for o in q_orders:
        if through is not None and session(o["executed_at"]) > through: break
        fees += D(o["trading_fee_usd"]) + D(o["regulatory_fee_usd"]) + D(o["ppn_usd"])
        p = pos.setdefault(o["symbol"], {"shares": D(0), "cost": D(0), "last": D(o["price"])})
        p["last"] = D(o["price"])
        s_r = D(o["shares"]); tot = D(o["total_usd"])
        if o["side"] == "buy":
            p["shares"] += s_r; p["cost"] += tot
        else:
            held = p["shares"]; s = min(s_r, held)
            if s > 0 and s_r > 0:
                avg = p["cost"] / held
                proceeds = tot if s == s_r else tot * s / s_r
                realized += proceeds - s * avg
                p["cost"] -= s * avg; p["shares"] -= s
        if p["shares"] < D("1e-9"):
            p["shares"] = D(0); p["cost"] = D(0)
    return pos, realized, fees

def close_at(sym, d):
    best = None
    for s, dd, cl in closes:
        if s == sym and dd <= d and (best is None or dd > best[0]): best = (dd, D(cl))
    return None if best is None else best[1]

series = []
for d in dates:
    pos, realized, fees = replay(d)
    value = D(0); cost = D(0)
    for sym, p in pos.items():
        if p["shares"] == 0: continue
        cl = close_at(sym, d)
        value += p["shares"] * (cl if cl is not None else p["last"])
        cost += p["cost"]
    unreal = value - cost
    series.append(dict(date=d, value_usd=c(value), cost_usd=c(cost), realized_usd=c(realized), unrealized_usd=c(unreal), pnl_usd=c(realized+unreal), fees_usd=c(fees)))

pos, realized, fees = replay(None)
holdings = []
for sym in sorted(pos):
    p = pos[sym]
    if p["shares"] == 0: continue
    holdings.append(dict(symbol=sym, shares=q(p["shares"],9), cost_usd=c(p["cost"]), avg_price=q(p["cost"]/p["shares"],6), last_order_price=str(p["last"])))
pos9, r9, f9 = replay("2026-01-09")
h9 = []
for sym in sorted(pos9):
    p = pos9[sym]
    if p["shares"] == 0: continue
    h9.append(dict(symbol=sym, shares=q(p["shares"],9), cost_usd=c(p["cost"]), avg_price=q(p["cost"]/p["shares"],6), last_order_price=str(p["last"])))

sessions = [dict(executed_at=o["executed_at"], session=session(o["executed_at"])) for o in orders]
sessions += [dict(executed_at="2026-03-09T03:59:00+07:00", session="2026-03-08"), dict(executed_at="2026-07-01T20:30:00+07:00", session="2026-07-01")]
for s in sessions: assert session(s["executed_at"]) == s["session"], s

closes_map = {}
for s_, d_, cl_ in closes:
    closes_map.setdefault(s_, []).append(dict(date=d_, close=cl_))
fx = {
 "about": "Shared ledger fixture (contract B): web/lib/sean/ledger.test.ts and engine/tests/test_sean_ledger.py both replay it. Synthetic orders, not the owner's. Keys are sean_orders / sean_equity column names; every number is a string so Python reads it as Decimal. Expected values were computed with Decimal and ROUND_HALF_UP. Covers: an after-midnight-WIB fill that belongs to the previous New York session (id 3), a sell of more shares than held (id 5), a sell of a stock never seen bought (id 10), a holding with no closes (CCC, valued at its last order price), two orders at the same instant replayed by id (7 before 8), a weekend date (2026-01-10), a date before any order, and a half-cent tie in realized (26.125 -> 26.13 on 2026-01-12).",
 "orders": orders,
 "closes": closes_map,
 "sessions": sessions,
 "expected": {
   "positions": [dict(symbol=h["symbol"], shares=h["shares"], cost_usd=h["cost_usd"]) for h in holdings],
   "realized_usd": c(realized),
   "fees_usd": c(fees),
   "points": series,
 },
}
json.dump(fx, open(sys.argv[1], "w"), indent=2); open(sys.argv[1],"a").write("\n")
for s in series: print(s)
print(holdings, c(realized), c(fees)); print(h9, c(r9), c(f9))
````
