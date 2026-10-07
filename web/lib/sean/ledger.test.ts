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
