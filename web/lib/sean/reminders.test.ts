import { describe, expect, it } from 'vitest';
import {
  buildReminders, fund, lastPrices, MIN_TRADE_USD, outsideShares, planOrders, resizes, sideOf,
  type PlanOrderLite, type Reminder, type ReminderInput, type Target,
} from './reminders';

const OCT = '2026-10-07';
const NOV = '2026-11-02';

// RAW-FR's real decision for 2026-10-07 (book_targets), rank order.
const PICKS: [string, number][] = [
  ['MRNA', 187.46], ['CNC', 64.61], ['MRVL', 287.01], ['MU', 1045.56], ['FTNT', 191.27],
  ['IT', 184.92], ['INTC', 112.5], ['AMAT', 530.27], ['TER', 430.32], ['DELL', 574],
  ['DOW', 28.16], ['TGT', 154.33], ['UNH', 376.32], ['BAX', 24.36], ['ASML', 1834.1],
  ['UPS', 93.11], ['JBHT', 225.93], ['LLY', 1157.49], ['BMY', 59.59], ['LRCX', 333.89],
];
const RAW: Target[] = PICKS.map(([symbol, last]) => ({ symbol, weight: 0.05, last }));

/** The owner's real follow-through: $27.90 of each pick, Oct 7 evening WIB. */
const followed = (): Map<string, number> => new Map(RAW.map(t => [t.symbol, 27.9 / t.last]));
const octBuys: PlanOrderLite[] = RAW.map(t => ({
  symbol: t.symbol, side: 'buy', executedAt: '2026-10-07T21:55:00+07:00', price: t.last,
}));
/** What he held before RAW existed: never in the plan. */
const PRE_PLAN = new Map<string, number>([
  ['SPY', 2], ['NVDA', 3], ['PLTR', 5.38], ['FUTU', 1], ['GE', 0.5], ['LRCX', 0.4], ['LLY', 0.1], ['WDC', 1],
]);

function input(over: Partial<ReminderInput> = {}): ReminderInput {
  return {
    sessionDate: OCT, targets: RAW, resizes: true, held: new Map(), outside: new Map(), closes: new Map(),
    budgetUsd: null, cashUsd: null, orders: [], marks: [], ...over,
  };
}

/** November's decision: DOW dropped, XYZ picked. */
const NOV_PICKS: Target[] = [...RAW.filter(t => t.symbol !== 'DOW'), { symbol: 'XYZ', weight: 0.05, last: 50 }];

describe('buildReminders: fresh link', () => {
  it('with a plan size: one buy per pick, sized weight × plan size, in rank order', () => {
    const r = buildReminders(input({ budgetUsd: 560 }));
    expect(r.planSize).toBe(560);
    expect(r.planValue).toBe(0);
    expect(r.open).toHaveLength(20);
    expect(r.open.every(x => x.action === 'buy' && x.side === 'buy')).toBe(true);
    expect(r.open[0].symbol).toBe('MRNA');
    expect(r.open[19].symbol).toBe('LRCX');
    for (const x of r.open) expect(x.usd).toBeCloseTo(28, 6);
  });

  it('without a plan size: buys carry no amount', () => {
    const r = buildReminders(input());
    expect(r.planSize).toBeNull();
    expect(r.open).toHaveLength(20);
    expect(r.open.every(x => x.usd === null)).toBe(true);
  });
});

describe('buildReminders: the plan size is holdings plus cash', () => {
  /**
   * 2026-11-02, measured. Deposited by then: 15,000,000 IDR at 17,841 = $840.76. Spent: the 20 real
   * Oct 7 buys, $560.60 including $2.60 of fees. So cash = $280.16, holdings = $558.00, and the
   * plan size is $838.16 -- which is the deposits less the fees, exactly.
   */
  const NOV_CASH = 280.16;

  it('sizes buys from holdings + cash, not holdings alone', () => {
    const r = buildReminders(input({ held: followed(), orders: octBuys, cashUsd: NOV_CASH }));
    expect(r.planValue).toBeCloseTo(558, 6);
    expect(r.cashUsd).toBe(NOV_CASH);
    expect(r.planSize).toBeCloseTo(838.16, 6);
    // the identity: holdings + cash = deposits - fees paid
    expect(r.planValue + NOV_CASH).toBeCloseTo(840.76 - 2.6, 2);
  });

  it('a rotation is funded by the deposit alone: five new names cost less than the cash', () => {
    const picks: Target[] = [
      ...RAW.filter(t => !['DOW', 'BAX', 'UPS', 'BMY', 'TGT'].includes(t.symbol)),
      ...['AAA', 'BBB', 'CCC', 'DDD', 'EEE'].map(symbol => ({ symbol, weight: 0.05, last: 100 })),
    ];
    const r = buildReminders(input({
      sessionDate: NOV, targets: picks, held: followed(), orders: octBuys, cashUsd: NOV_CASH,
    }));
    const sells = r.open.filter(x => x.action === 'sell');
    const buys = r.open.filter(x => x.action === 'buy');
    expect(sells).toHaveLength(5);
    expect(buys).toHaveLength(5);
    // sells come first: ACTION_ORDER, and the owner's own stated sequence
    expect(r.open.slice(0, 5).every(x => x.action === 'sell')).toBe(true);
    const needed = buys.reduce((sum, x) => sum + (x.usd ?? 0), 0);
    expect(needed).toBeCloseTo(209.54, 2);
    // D7: the buys are covered by settled cash, with no sale proceeds reused the same day
    expect(needed).toBeLessThan(NOV_CASH);
  });

  it('cash the owner has spent beyond his deposits reads negative, and still sizes the plan', () => {
    const r = buildReminders(input({ held: followed(), orders: octBuys, cashUsd: -0.09 }));
    expect(r.cashUsd).toBe(-0.09);
    expect(r.planSize).toBeCloseTo(557.91, 6);
  });

  it('the owner’s typed plan size still overrides the derived one', () => {
    const r = buildReminders(input({ held: followed(), orders: octBuys, cashUsd: NOV_CASH, budgetUsd: 1000 }));
    expect(r.planSize).toBe(1000);
  });

  it('without cash it falls back to holdings, exactly as before', () => {
    const r = buildReminders(input({ held: followed(), orders: octBuys, cashUsd: null }));
    expect(r.planSize).toBeCloseTo(558, 6);
  });
});

describe('buildReminders: the real Oct 7 follow-through', () => {
  it('leaves nothing to do, and holdings from before the plan are never sold', () => {
    const r = buildReminders(input({ held: followed(), outside: PRE_PLAN, orders: octBuys }));
    expect(r.reminders).toHaveLength(0);
    expect(r.holdings).toHaveLength(20);
    expect(r.holdings.every(h => h.picked)).toBe(true);
    expect(r.planValue).toBeCloseTo(558, 6);
    expect(r.planSize).toBeCloseTo(558, 6);
  });

  it('stays quiet with a budget a little off the plan value', () => {
    const r = buildReminders(input({ held: followed(), orders: octBuys, budgetUsd: 560.51 }));
    expect(r.reminders).toHaveLength(0);
  });
});

describe('buildReminders: month turnover', () => {
  it('sells a dropped pick in full and buys the new one, sells first', () => {
    const r = buildReminders(input({ sessionDate: NOV, targets: NOV_PICKS, held: followed(), orders: octBuys }));
    expect(r.open.map(x => `${x.action}:${x.symbol}`)).toEqual(['sell:DOW', 'buy:XYZ']);
    const [sell, buy] = r.open;
    expect(sell.shares).toBeCloseTo(27.9 / 28.16, 9);
    expect(sell.usd).toBeCloseTo(27.9, 6);
    expect(sell.alsoOutside).toBe(false);
    expect(buy.usd).toBeCloseTo(0.05 * 558, 6);
    expect(new Set(r.reminders.map(x => x.key)).size).toBe(r.reminders.length);
    expect(sell.key).toBe(`${NOV}:DOW:sell`);
  });

  it('a dropped pick also held from before the plan: says so, sells only the plan shares', () => {
    const outside = new Map([['DOW', 2]]);
    const r = buildReminders(input({ sessionDate: NOV, targets: NOV_PICKS, held: followed(), outside, orders: octBuys }));
    const sell = r.open.find(x => x.symbol === 'DOW')!;
    expect(sell.alsoOutside).toBe(true);
    expect(sell.shares).toBeCloseTo(27.9 / 28.16, 9);
  });

  it('a pre-plan holding the method drops gets no reminder', () => {
    const picks = RAW.filter(t => t.symbol !== 'LLY');
    const held = followed();
    held.delete('LLY');
    const r = buildReminders(input({ sessionDate: NOV, targets: picks, held, outside: PRE_PLAN }));
    expect(r.reminders.find(x => x.symbol === 'LLY')).toBeUndefined();
    expect(r.reminders.find(x => x.symbol === 'SPY')).toBeUndefined();
  });

  it('a pick held only from before the plan gets a buy that says so', () => {
    const held = followed();
    held.delete('LLY');
    // the plan never bought LLY, so no plan order clears the reminder either
    const r = buildReminders(input({ held, outside: PRE_PLAN, orders: octBuys.filter(o => o.symbol !== 'LLY') }));
    expect(r.open).toHaveLength(1);
    expect(r.open[0]).toMatchObject({ action: 'buy', symbol: 'LLY', alsoOutside: true });
  });
});

describe('buildReminders: resizing', () => {
  /** The owner's real 2026-11-02 plan size: $558.00 of stock + $280.16 of cash. Slot: $41.908. */
  const NOV_SIZE = 838.16;
  const SLOT = NOV_SIZE * 0.05; // 41.908

  const drifted = (): Map<string, number> => {
    const held = followed();
    held.set('MU', 80 / 1045.56); // $80 at the decision price: $38.09 above its $41.91 share
    held.set('BAX', 60 / 24.36); // $60: $18.09 above, under the $25 floor
    return held;
  };

  it('trims a pick above its share, ignores gaps under $25', () => {
    const r = buildReminders(input({ held: drifted(), budgetUsd: NOV_SIZE }));
    expect(r.open).toHaveLength(1);
    expect(r.open[0]).toMatchObject({ action: 'trim', side: 'sell', symbol: 'MU' });
    expect(r.open[0].usd).toBeCloseTo(80 - SLOT, 6);
  });

  it('adds to a pick below its share', () => {
    const held = followed();
    held.set('MU', 10 / 1045.56); // $31.91 below its $41.91 share
    const r = buildReminders(input({ held, budgetUsd: NOV_SIZE }));
    expect(r.open).toHaveLength(1);
    expect(r.open[0]).toMatchObject({ action: 'add', side: 'buy', symbol: 'MU' });
    expect(r.open[0].usd).toBeCloseTo(SLOT - 10, 6);
  });

  it('a gap that would have traded at the old $10 floor is left alone at $25', () => {
    const held = followed();
    held.set('MU', 28 / 1045.56); // $13.91 below its share: over $10, under $25
    const r = buildReminders(input({ held, budgetUsd: NOV_SIZE }));
    expect(r.reminders).toHaveLength(0);
  });

  it('never adds or trims for rules that do not resize', () => {
    const r = buildReminders(input({ held: drifted(), budgetUsd: NOV_SIZE, resizes: false }));
    expect(r.reminders).toHaveLength(0);
  });

  it('a big plan uses the engine 1% band, not the $25 floor', () => {
    const held = new Map(RAW.map(t => [t.symbol, 250 / t.last]));
    held.set('MU', 220 / 1045.56); // $30 below its $250 share: under 1% of $5,000
    held.set('DELL', 190 / 574); // $60 below: over the band
    const r = buildReminders(input({ held, budgetUsd: 5000 }));
    expect(r.open.map(x => `${x.action}:${x.symbol}`)).toEqual(['add:DELL']);
    expect(r.open[0].usd).toBeCloseTo(60, 6);
  });
});

describe('buildReminders: done', () => {
  it('partial follow-through: an order on or after the decision day clears that reminder only', () => {
    const held = followed();
    held.set('DOW', 0.5);
    const orders: PlanOrderLite[] = [
      ...octBuys,
      { symbol: 'DOW', side: 'sell', executedAt: '2026-11-02T21:40:00+07:00', price: 28 },
    ];
    const r = buildReminders(input({ sessionDate: NOV, targets: NOV_PICKS, held, orders }));
    expect(r.done.map(x => `${x.symbol}:${x.done}`)).toEqual(['DOW:order']);
    expect(r.open.map(x => x.symbol)).toEqual(['XYZ']);
  });

  it('an order before the decision day does not clear it', () => {
    const held = followed();
    held.set('DOW', 0.5);
    const orders: PlanOrderLite[] = [
      ...octBuys,
      { symbol: 'DOW', side: 'sell', executedAt: '2026-10-30T22:00:00+07:00', price: 28 },
    ];
    const r = buildReminders(input({ sessionDate: NOV, targets: NOV_PICKS, held, orders }));
    expect(r.open.map(x => x.symbol)).toEqual(['DOW', 'XYZ']);
  });

  it('a mark for this decision clears it; a mark for an older decision does not', () => {
    const r = buildReminders(input({
      sessionDate: NOV, targets: NOV_PICKS, held: followed(), orders: octBuys,
      marks: [
        { sessionDate: NOV, symbol: 'XYZ', side: 'buy' },
        { sessionDate: OCT, symbol: 'DOW', side: 'sell' },
      ],
    }));
    expect(r.done.map(x => `${x.symbol}:${x.done}`)).toEqual(['XYZ:mark']);
    expect(r.open.map(x => x.symbol)).toEqual(['DOW']);
  });
});

describe('buildReminders: edges', () => {
  it('no picks: no reminders, holdings still listed', () => {
    const r = buildReminders(input({ targets: [], held: followed(), orders: octBuys }));
    expect(r.reminders).toHaveLength(0);
    expect(r.holdings).toHaveLength(20);
    expect(r.holdings.every(h => !h.picked)).toBe(true);
  });

  it('values a non-pick at the latest close, else its last order price', () => {
    const held = new Map([['AAA', 2], ['BBB', 3]]);
    const orders: PlanOrderLite[] = [
      { symbol: 'AAA', side: 'buy', executedAt: '2026-10-07T21:00:00+07:00', price: 10 },
      { symbol: 'BBB', side: 'buy', executedAt: '2026-10-07T21:00:00+07:00', price: 20 },
    ];
    const r = buildReminders(input({ held, orders, closes: new Map([['AAA', 11]]) }));
    expect(r.holdings.find(h => h.symbol === 'AAA')!.value).toBeCloseTo(22, 9);
    expect(r.holdings.find(h => h.symbol === 'BBB')!.value).toBeCloseTo(60, 9);
    expect(r.holdings[0].symbol).toBe('BBB');
  });

  it('ignores dust below 1e-9 shares', () => {
    const r = buildReminders(input({ held: new Map([['DUST', 1e-12]]) }));
    expect(r.holdings).toHaveLength(0);
  });
});

describe('fund: spending a leftover wallet, rank order, last one partial', () => {
  const r = (over: Partial<Reminder>): Reminder => ({
    key: 'k', action: 'buy', side: 'buy', symbol: 'X', usd: 45, shares: null, weight: 0.05,
    alsoOutside: false, done: null, fundedUsd: null, ...over,
  });
  const three = [
    r({ key: 'a', symbol: 'A' }),
    r({ key: 'b', symbol: 'B' }),
    r({ key: 'c', symbol: 'C' }),
  ];

  it('fills in order and shrinks the one the cash runs out on', () => {
    // $100 over three $45 buys: two whole, $10 left -- under the floor, so nothing forced in.
    expect(fund(three, 100).map(x => x.fundedUsd)).toEqual([45, 45, 0]);
  });

  it('places a partial only when the remainder clears the fee floor', () => {
    // $75: one whole, $30 left, which is over MIN_TRADE_USD, so the second goes in partial.
    expect(fund(three, 75).map(x => x.fundedUsd)).toEqual([45, 30, 0]);
    // $45 + just under the floor: the second is not worth its minimum fee.
    expect(fund(three, 45 + MIN_TRADE_USD - 0.01).map(x => x.fundedUsd)).toEqual([45, 0, 0]);
  });

  it('is rank order, not pro rata: the top picks are whole and the tail goes short', () => {
    const got = fund(three, 90).map(x => x.fundedUsd);
    expect(got).toEqual([45, 45, 0]);
    expect(got).not.toEqual([30, 30, 30]); // what spreading the shortfall would have done
  });

  it('never exceeds the cash it was given', () => {
    for (const cash of [0, 1, 25, 44.99, 45, 46, 89.99, 135, 1000]) {
      const spent = fund(three, cash).reduce((t, x) => t + (x.fundedUsd ?? 0), 0);
      expect(spent).toBeLessThanOrEqual(cash + 1e-9);
    }
  });

  it('leaves sells, trims, done reminders and a missing wallet alone', () => {
    const mixed = [
      r({ key: 's', action: 'sell', side: 'sell', symbol: 'S', usd: 60 }),
      r({ key: 't', action: 'trim', side: 'sell', symbol: 'T', usd: 20 }),
      r({ key: 'd', symbol: 'D', done: 'order' }),
      r({ key: 'o', symbol: 'O' }),
    ];
    expect(fund(mixed, 500).map(x => x.fundedUsd)).toEqual([null, null, null, 45]);
    for (const cash of [null, 0, -5, Number.NaN]) {
      expect(fund(three, cash).every(x => x.fundedUsd === null)).toBe(true);
    }
  });

  it('buildReminders funds the open buys from the wallet it was given', () => {
    // One name is missing from the book, so it is an open buy. Its target is about $28 (5% of a
    // ~$560 plan), so $26 of settled cash is short of it but clears the fee floor: a partial.
    const held = followed();
    held.delete('LRCX');
    const short = buildReminders(input({ held, cashUsd: 26, targets: RAW }));
    const partial = short.reminders.find(x => x.symbol === 'LRCX' && x.action === 'buy');
    expect(partial?.usd).toBeGreaterThan(26);    // the target wants more than the wallet holds
    expect(partial?.fundedUsd).toBe(26);         // so it is shrunk to what the cash affords
    expect(short.reminders.filter(x => x.action === 'sell').every(x => x.fundedUsd === null)).toBe(true);

    // With the target comfortably covered, the buy is funded in full, not to the whole wallet.
    const flush = buildReminders(input({ held, cashUsd: 500, targets: RAW }));
    const whole = flush.reminders.find(x => x.symbol === 'LRCX' && x.action === 'buy');
    expect(whole?.fundedUsd).toBe(whole?.usd);
    expect(whole?.fundedUsd).toBeLessThan(500);
  });
});

describe('helpers', () => {
  it('planOrders keeps orders whose New York trade date is on or after since', () => {
    const orders = [
      { executedAt: '2025-06-10T21:34:00+07:00', id: 1 },
      { executedAt: '2026-10-06T23:59:00+07:00', id: 2 }, // New York: Oct 6, 12:59
      { executedAt: '2026-10-07T00:10:00+07:00', id: 3 }, // New York: Oct 6, 13:10 -- the Oct 6 session
      { executedAt: '2026-10-07T21:55:00+07:00', id: 4 }, // New York: Oct 7, 10:55
      { executedAt: '2026-10-08T03:30:00+07:00', id: 5 }, // New York: Oct 7, 16:30 -- still the Oct 7 session
    ];
    expect(planOrders(orders, OCT).map(o => o.id)).toEqual([4, 5]);
  });

  it('an order after midnight WIB clears a reminder of the session it traded in', () => {
    const held = followed();
    held.set('DOW', 0.5);
    const orders: PlanOrderLite[] = [
      ...octBuys,
      // 03:30 WIB on Nov 3 is 15:30 on Nov 2 in New York: the Nov 2 decision's session
      { symbol: 'DOW', side: 'sell', executedAt: '2026-11-03T03:30:00+07:00', price: 28 },
      // 23:00 WIB on Nov 1 is 11:00 on Nov 1 in New York: before the decision, so it does not count
      { symbol: 'XYZ', side: 'buy', executedAt: '2026-11-01T23:00:00+07:00', price: 50 },
    ];
    const r = buildReminders(input({ sessionDate: NOV, targets: NOV_PICKS, held, orders }));
    expect(r.done.map(x => `${x.symbol}:${x.done}`)).toEqual(['DOW:order']);
    expect(r.open.map(x => x.symbol)).toEqual(['XYZ']);
  });

  it('outsideShares is all minus plan, dropping float noise', () => {
    const all = new Map([['LLY', 0.1 + 0.0241], ['SPY', 2], ['MU', 0.0267]]);
    const plan = new Map([['LLY', 0.0241], ['MU', 0.0267]]);
    const out = outsideShares(all, plan);
    expect([...out.keys()].sort()).toEqual(['LLY', 'SPY']);
    expect(out.get('LLY')).toBeCloseTo(0.1, 9);
  });

  it('lastPrices keeps the latest order price', () => {
    const p = lastPrices([
      { symbol: 'MU', side: 'buy', executedAt: '2026-10-07T21:00:00+07:00', price: 1000 },
      { symbol: 'MU', side: 'buy', executedAt: '2026-10-08T21:00:00+07:00', price: 1010 },
    ]);
    expect(p.get('MU')).toBe(1010);
  });

  it('resizes mirrors the engine presets', () => {
    expect(resizes('monthly-hold-frac')).toBe(true);
    expect(resizes('monthly-rank-weekly-resize-frac')).toBe(true);
    expect(resizes('monthly-hold-frac-gotrade')).toBe(true);
    expect(resizes('monthly-rank-weekly-resize-frac-gotrade')).toBe(true);
    expect(resizes('daily-switch')).toBe(false);
    expect(resizes('swing-t20')).toBe(false);
    expect(resizes(null)).toBe(false);
  });

  it('sideOf', () => {
    expect(sideOf('buy')).toBe('buy');
    expect(sideOf('add')).toBe('buy');
    expect(sideOf('trim')).toBe('sell');
    expect(sideOf('sell')).toBe('sell');
  });
});
