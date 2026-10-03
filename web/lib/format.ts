const MINUS = '−';
const sign = (v: number) => (v < 0 ? MINUS : '+');
const idr = new Intl.NumberFormat('id-ID');

/** Bare price, the exact string to paste into Gotrade. */
export const money = (v: number) => Math.abs(v).toFixed(2);
export const usd = (v: number) => '$' + money(v);
export const signedUsd = (v: number) => sign(v) + usd(v);

export const rp = (v: number, rate: number) => 'Rp ' + idr.format(Math.round((Math.abs(v) * rate) / 1000) * 1000);
export const signedRp = (v: number, rate: number) => sign(v) + rp(v, rate);

export const pct = (v: number, digits = 2) => (Math.abs(v) * 100).toFixed(digits) + '%';
export const signedPct = (v: number, digits = 2) => sign(v) + pct(v, digits);

const SHORT = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', weekday: 'short', month: 'short', day: 'numeric' });
const MONTH_DAY = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric' });
const MONTH = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short' });

/** '2026-10-08' -> 'Thu, Oct 8' */
export const shortDate = (ymd: string) => SHORT.format(new Date(`${ymd}T12:00:00Z`));
/** '2026-10-08' -> 'Oct 8' */
export const monthDay = (ymd: string) => MONTH_DAY.format(new Date(`${ymd}T12:00:00Z`));
/** '2026-10-08' -> 'Oct' */
export const monthName = (ymd: string) => MONTH.format(new Date(`${ymd}T12:00:00Z`));
