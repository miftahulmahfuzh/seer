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
      viewLabel: 'See the screenshot of the PLTR buy from Jun 10, 2025',
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
    expect(sale.viewLabel).toBe('See the screenshot of the PLTR sale from Oct 7, 2026');
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
