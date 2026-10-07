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
