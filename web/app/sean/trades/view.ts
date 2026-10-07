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
  viewLabel: string;
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
    viewLabel: `See the screenshot of ${orderName(r)}`,
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

/* ---- Screenshot ------------------------------------------------------------------------- */

export const SCREENSHOT_LOADING = 'Opening the screenshot…';
export const SCREENSHOT_MISSING = "This screenshot can't be shown right now. Try again in a moment.";
export const SCREENSHOT_CLOSE = 'Close the screenshot';

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
  notKept: "Sean couldn't keep a copy of this screenshot, so nothing was saved. Try this one again.",
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
