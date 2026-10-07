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
