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
