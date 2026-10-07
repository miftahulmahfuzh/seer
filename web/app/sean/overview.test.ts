import { describe, expect, it } from 'vitest';
import { dateNum } from '../../components/sera/charts/scale';
import type { EquityRow, LatestMark } from '../../lib/sean/overviewData';
import {
  FEES_COLOR,
  holdings,
  monthTicks,
  orderDay,
  overview,
  type OverviewOrder,
  PNL_COLOR,
  pctText,
  priceText,
  sharesText,
  signedPctText,
  signedUsdText,
  sortOrders,
  toCloses,
  usdText,
  usdTick,
} from './overview';

let nextId = 1;
function mk(
  side: 'buy' | 'sell',
  symbol: string,
  executedAt: string,
  price: number,
  shares: number,
  [trading, regulatory, ppn]: [number, number, number],
): OverviewOrder {
  const amount = Math.round(price * shares * 100) / 100;
  const fees = trading + regulatory + ppn;
  const total = Math.round((side === 'buy' ? amount + fees : amount - fees) * 100) / 100;
  return {
    id: nextId++,
    side,
    symbol,
    executedAt,
    price,
    shares,
    amountUsd: amount,
    tradingFeeUsd: trading,
    regulatoryFeeUsd: regulatory,
    ppnUsd: ppn,
    totalUsd: total,
  };
}

const A = mk('buy', 'AAA', '2026-09-01T21:30:00+07:00', 10, 2, [0.1, 0.02, 0.02]);
const B = mk('sell', 'AAA', '2026-09-15T21:30:00+07:00', 12, 1, [0.1, 0.01, 0.01]);
const C = mk('buy', 'BBB', '2026-09-15T22:00:00+07:00', 40, 0.5, [0.1, 0.02, 0.01]);
const D = mk('buy', 'CCC', '2026-10-07T21:00:00+07:00', 5, 1, [0.1, 0.02, 0.01]);
const SELL_ALL = mk('sell', 'AAA', '2026-09-15T21:30:00+07:00', 12, 2, [0.1, 0.02, 0.02]);
const TODAY = '2026-10-07';
const MARK_AAA: LatestMark = { symbol: 'AAA', date: '2026-10-06', close: 13 };

const eqRow = (date: string, pnlUsd: number, feesUsd: number): EquityRow => ({
  date,
  valueUsd: 0,
  costUsd: 0,
  realizedUsd: 0,
  unrealizedUsd: 0,
  pnlUsd,
  feesUsd,
});

const statValue = (v: ReturnType<typeof overview>, key: string) => {
  if (v.empty) throw new Error('expected orders');
  return v.stats.find(s => s.key === key);
};

describe('formatters', () => {
  it('writes dollars with a real minus sign and thousands separators', () => {
    expect(usdText(1234.5)).toBe('$1,234.50');
    expect(usdText(-3.2)).toBe('−$3.20');
    expect(signedUsdText(3.61)).toBe('+$3.61');
    expect(signedUsdText(-0.14)).toBe('−$0.14');
    expect(signedUsdText(0.001)).toBe('$0.00');
  });

  it('writes percentages, shares and prices plainly', () => {
    expect(pctText(0.0075)).toBe('0.75%');
    expect(pctText(null)).toBe('—');
    expect(signedPctText(0.191658)).toBe('+19.2%');
    expect(signedPctText(-0.006458)).toBe('−0.6%');
    expect(signedPctText(0.0001)).toBe('0.0%');
    expect(sharesText(0.5)).toBe('0.5');
    expect(sharesText(12)).toBe('12');
    expect(sharesText(0.035842123)).toBe('0.035842');
    expect(priceText(12)).toBe('$12.00');
    expect(priceText(1063.886)).toBe('$1,063.886');
  });

  it('labels the dollar axis with cents only when the range is small', () => {
    expect(usdTick(2)(1)).toBe('$1.00');
    expect(usdTick(2)(-1)).toBe('−$1.00');
    expect(usdTick(0)(1500)).toBe('$1,500');
    expect(usdTick(0)(-0.2)).toBe('$0');
  });

  it('reads the order day as the New York trade date', () => {
    expect(orderDay({ executedAt: '2026-10-07T21:55:00+07:00' })).toBe('2026-10-07');
    // 03:30 WIB on Oct 8 is 16:30 on Oct 7 in New York: that session's trade
    expect(orderDay({ executedAt: '2026-10-08T03:30:00+07:00' })).toBe('2026-10-07');
  });
});

describe('monthTicks', () => {
  it('spaces month starts so at most eight fit, with the year on the first and on January', () => {
    const ticks = monthTicks('2025-06-12', '2026-10-07');
    expect(ticks.map(t => t.label)).toEqual(['Jul 2025', 'Sep', 'Nov', 'Jan 2026', 'Mar', 'May', 'Jul', 'Sep']);
    expect(ticks[0].value).toBe(Date.UTC(2025, 6, 1));
  });

  it('falls back to the two ends inside one month, and to one tick for one day', () => {
    expect(monthTicks('2026-09-01', '2026-09-15').map(t => t.label)).toEqual(['Sep 1', 'Sep 15']);
    expect(monthTicks('2026-09-01', '2026-09-01')).toEqual([{ value: dateNum('2026-09-01'), label: 'Sep 1' }]);
  });
});

describe('ledger adapter', () => {
  it('sorts orders by time, then by id', () => {
    const late = mk('buy', 'ZZZ', '2026-09-15T21:30:00+07:00', 1, 1, [0.1, 0, 0]);
    expect(sortOrders([late, C, B, A]).map(o => o.id)).toEqual([A.id, B.id, late.id, C.id]);
  });

  it('turns latest marks into the flat closes the ledger takes, oldest first', () => {
    const closes = toCloses([
      { symbol: 'AAA', date: '2026-10-06', close: 13 },
      { symbol: 'AAA', date: '2026-10-05', close: 12.5 },
      { symbol: 'BBB', date: '2026-10-06', close: 41 },
    ]);
    expect(closes).toEqual([
      { symbol: 'AAA', date: '2026-10-05', close: 12.5 },
      { symbol: 'AAA', date: '2026-10-06', close: 13 },
      { symbol: 'BBB', date: '2026-10-06', close: 41 },
    ]);
  });
});

describe('overview', () => {
  it('is empty with no orders', () => {
    expect(overview({ orders: [], equity: [], marks: [], today: TODAY })).toEqual({ empty: true });
  });

  it('one buy and no prices: down by its fees, one dotted point on a one-week axis', () => {
    const v = overview({ orders: [A], equity: [], marks: [], today: TODAY });
    if (v.empty) throw new Error('expected orders');
    expect(statValue(v, 'total')?.value).toBe('−$0.14');
    expect(statValue(v, 'total')?.tone).toBe('neg');
    expect(statValue(v, 'realized')?.value).toBe('$0.00');
    expect(statValue(v, 'realized')?.tone).toBeUndefined();
    expect(statValue(v, 'fees')?.value).toBe('$0.14');
    expect(statValue(v, 'fees')?.sub).toBe('On 1 order');
    expect(v.chart.title).toBe('Down $0.14 since Sep 2026');
    expect(v.chart.source).toBe('orders');
    expect(v.chart.series[0].points).toHaveLength(1);
    expect(v.chart.series[0].dots).toBe(true);
    expect(v.chart.xDomain).toEqual([dateNum('2026-09-01') - 3 * 86_400_000, dateNum('2026-09-01') + 3 * 86_400_000]);
    expect(v.holdings).toHaveLength(1);
    expect(v.holdings[0].estimate).toBe(true);
    expect(v.holdings[0].priceText).toBe('$10.00');
    expect(v.holdings[0].avgCostText).toBe('$10.07');
  });

  it('many orders and no prices: the ledger at order prices on each trading day', () => {
    const v = overview({ orders: [C, B, A], equity: [], marks: [], today: TODAY });
    if (v.empty) throw new Error('expected orders');
    expect(v.orderCount).toBe(3);
    expect(v.firstDay).toBe('2026-09-01');
    expect(v.stats.map(s => s.value)).toEqual(['+$3.61', '+$1.81', '+$1.80', '$0.39', '0.75%']);
    expect(statValue(v, 'feeShare')?.sub).toBe('$52.00 bought and sold in total');

    const pnl = v.chart.series.find(s => s.id === 'pnl');
    const fees = v.chart.series.find(s => s.id === 'fees');
    expect(pnl?.color).toBe(PNL_COLOR);
    expect(fees?.color).toBe(FEES_COLOR);
    expect(fees?.dash).toBe('6 4');
    expect(pnl?.points.map(p => p[0])).toEqual(['2026-09-01', '2026-09-15']);
    expect(pnl?.points[0][1]).toBeCloseTo(-0.14, 2);
    expect(pnl?.points[1][1]).toBeCloseTo(3.61, 2);
    expect(fees?.points[1][1]).toBeCloseTo(0.39, 2);
    expect(pnl?.points[1][2]).toBe('Sep 15, 2026: +$3.61');
    expect(v.chart.refLines).toEqual([expect.objectContaining({ value: 0, label: 'Break-even' })]);
    expect(v.chart.title).toBe('Up $3.61 since Sep 2026');
    expect(v.chart.caption).toContain('no market prices yet');
    expect(v.chart.pricesAsOf).toBeNull();
    expect(v.chart.yFormat(1)).toBe('$1.00');

    expect(v.holdings.map(h => h.symbol)).toEqual(['BBB', 'AAA']);
    const [bbb, aaa] = v.holdings;
    expect(bbb.sharesText).toBe('0.5');
    expect(bbb.avgCostText).toBe('$40.26');
    expect(bbb.valueText).toBe('$20.00');
    expect(bbb.pnlText).toBe('−$0.13');
    expect(bbb.pnlPctText).toBe('−0.6%');
    expect(bbb.tone).toBe('neg');
    expect(aaa.priceText).toBe('$12.00');
    expect(aaa.pnlText).toBe('+$1.93');
    expect(aaa.pnlPctText).toBe('+19.2%');
    expect(aaa.tone).toBe('pos');
    expect(aaa.priceTip).toContain('last order price');
    expect(v.total.value).toBeCloseTo(32, 6);
    expect(v.total.pnl).toBeCloseTo(1.8, 6);
    expect(v.closed).toEqual([]);
  });

  it('a nightly close replaces the order price for that stock only', () => {
    const v = overview({ orders: [A, B, C], equity: [], marks: [MARK_AAA], today: TODAY });
    if (v.empty) throw new Error('expected orders');
    expect(statValue(v, 'total')?.value).toBe('+$4.61');
    expect(statValue(v, 'unrealized')?.value).toBe('+$2.80');
    const aaa = v.holdings.find(h => h.symbol === 'AAA');
    const bbb = v.holdings.find(h => h.symbol === 'BBB');
    expect(aaa?.estimate).toBe(false);
    expect(aaa?.priceText).toBe('$13.00');
    expect(aaa?.priceTip).toBe('Closing price on Oct 6, 2026');
    expect(bbb?.estimate).toBe(true);
  });

  it('holdings keep only the newest mark when several are given', () => {
    const h = holdings(sortOrders([A]), [MARK_AAA, { symbol: 'AAA', date: '2026-10-01', close: 9 }]);
    expect(h.rows[0].priceText).toBe('$13.00');
  });

  it('uses the nightly series when it exists, with no extra point when no order is newer', () => {
    const v = overview({
      orders: [A, B, C],
      equity: [eqRow('2026-10-06', 4.61, 0.39), eqRow('2026-10-05', 4, 0.39)],
      marks: [MARK_AAA],
      today: TODAY,
    });
    if (v.empty) throw new Error('expected orders');
    expect(v.chart.source).toBe('nightly');
    expect(v.chart.live).toBe(false);
    expect(v.chart.pricesAsOf).toBe('2026-10-06');
    expect(v.chart.series[0].points.map(p => p[0])).toEqual(['2026-10-05', '2026-10-06']);
    expect(v.chart.caption).toContain('Prices as of Oct 6, 2026.');
    expect(v.chart.xDomain).toBeUndefined();
  });

  it('adds a point for today when an uploaded order is newer than the nightly prices', () => {
    const v = overview({
      orders: [A, B, C, D],
      equity: [eqRow('2026-10-05', 4, 0.39), eqRow('2026-10-06', 4.61, 0.39)],
      marks: [MARK_AAA],
      today: TODAY,
    });
    if (v.empty) throw new Error('expected orders');
    expect(v.chart.live).toBe(true);
    const pts = v.chart.series[0].points;
    expect(pts[pts.length - 1][0]).toBe(TODAY);
    expect(pts[pts.length - 1][1]).toBeCloseTo(4.48, 2);
    expect(pts[pts.length - 1][2]).toBe('Oct 7, 2026: +$4.48, with your newest orders');
    expect(v.chart.series[1].points[pts.length - 1][1]).toBeCloseTo(0.52, 2);
    expect(statValue(v, 'total')?.value).toBe('+$4.48');
    expect(v.chart.caption).toContain('newer than those prices');
  });

  it('everything sold: realized only, nothing held, the symbol listed as sold out', () => {
    const v = overview({ orders: [A, SELL_ALL], equity: [], marks: [], today: TODAY });
    if (v.empty) throw new Error('expected orders');
    expect(statValue(v, 'realized')?.value).toBe('+$3.72');
    expect(statValue(v, 'unrealized')?.value).toBe('$0.00');
    expect(statValue(v, 'total')?.value).toBe('+$3.72');
    expect(v.holdings).toEqual([]);
    expect(v.total.value).toBe(0);
    expect(v.closed).toEqual(['AAA']);
  });

  it('holdings P&L adds up to the unrealized stat', () => {
    const v = overview({ orders: [A, B, C, D], equity: [], marks: [MARK_AAA], today: TODAY });
    if (v.empty) throw new Error('expected orders');
    expect(signedUsdText(v.total.pnl)).toBe(statValue(v, 'unrealized')?.value);
  });
});
