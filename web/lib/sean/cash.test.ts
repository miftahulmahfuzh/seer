import { describe, expect, it } from 'vitest';
import {
  cashUsd, depositDates, depositedIdr, depositedUsd, netSpentUsd, OWNER_MONTHLY, OWNER_USD_IDR,
  type CashFlowOrder, type ContributionSchedule,
} from './cash';

/** The owner's own plan, started the day he first followed RAW. */
const OWNER: ContributionSchedule = { ...OWNER_MONTHLY, startDate: '2026-10-07' };

describe('depositDates', () => {
  it('the start day, then every 25th after it', () => {
    expect(depositDates(OWNER, '2026-11-02')).toEqual(['2026-10-07', '2026-10-25']);
    expect(depositDates(OWNER, '2027-01-04')).toEqual([
      '2026-10-07', '2026-10-25', '2026-11-25', '2026-12-25',
    ]);
  });

  it('rolls the year over', () => {
    expect(depositDates(OWNER, '2027-02-01')).toContain('2027-01-25');
  });

  it('nothing before the start day, one deposit on it', () => {
    expect(depositDates(OWNER, '2026-10-06')).toEqual([]);
    expect(depositDates(OWNER, '2026-10-07')).toEqual(['2026-10-07']);
    expect(depositDates(OWNER, '2026-10-24')).toEqual(['2026-10-07']);
    expect(depositDates(OWNER, '2026-10-25')).toEqual(['2026-10-07', '2026-10-25']);
  });

  it('a start day that is itself the 25th gets one deposit, not two', () => {
    const s: ContributionSchedule = { ...OWNER, startDate: '2026-10-25' };
    expect(depositDates(s, '2026-11-01')).toEqual(['2026-10-25']);
    expect(depositDates(s, '2026-11-25')).toEqual(['2026-10-25', '2026-11-25']);
  });

  it('refuses a schedule it cannot honour every month', () => {
    expect(() => depositDates({ ...OWNER, dayOfMonth: 31 }, '2027-01-01')).toThrow(/1 to 28/);
    expect(() => depositDates({ ...OWNER, startDate: '7 Oct 2026' }, '2027-01-01')).toThrow(/YYYY-MM-DD/);
  });
});

describe('depositedIdr and depositedUsd', () => {
  it('the owner’s real rupiah: 10M to start, +5M on each 25th', () => {
    expect(depositedIdr(OWNER, '2026-10-24')).toBe(10_000_000);
    expect(depositedIdr(OWNER, '2026-11-02')).toBe(15_000_000);
    expect(depositedIdr(OWNER, '2026-12-01')).toBe(20_000_000);
  });

  it('converts at the rate it is given, to the cent', () => {
    // 17,841 IDR/USD: the rate paper_state.initial_cash_usd = 560.5067 was written at
    expect(depositedUsd(OWNER, '2026-10-24', OWNER_USD_IDR)).toBeCloseTo(560.51, 2);
    expect(depositedUsd(OWNER, '2026-11-02', OWNER_USD_IDR)).toBeCloseTo(840.76, 2);
  });

  it('refuses a rate that is not a positive number', () => {
    expect(() => depositedUsd(OWNER, '2026-11-02', 0)).toThrow(/usdIdr/);
    expect(() => depositedUsd(OWNER, '2026-11-02', Number.NaN)).toThrow(/usdIdr/);
  });
});

describe('netSpentUsd', () => {
  it('buys take money out, sells put it back, fees already inside totalUsd', () => {
    const orders: CashFlowOrder[] = [
      { side: 'buy', totalUsd: 28.03 },
      { side: 'buy', totalUsd: 28.03 },
      { side: 'sell', totalUsd: 10.0 },
    ];
    expect(netSpentUsd(orders)).toBeCloseTo(46.06, 2);
    expect(netSpentUsd([])).toBe(0);
  });
});

describe('cashUsd: the owner’s real wallet', () => {
  /** His real 7 Oct follow-through: 20 buys of $27.90 of stock + $0.13 of fees each. */
  const OCT_BUYS: CashFlowOrder[] = Array.from({ length: 20 }, () => ({ side: 'buy' as const, totalUsd: 28.03 }));

  it('on 2 November the wallet holds the 25 October deposit', () => {
    const cash = cashUsd({ schedule: OWNER, through: '2026-11-02', usdIdr: OWNER_USD_IDR, orders: OCT_BUYS });
    expect(cash).toBeCloseTo(280.16, 2);
  });

  it('holdings + cash equals the deposits less the fees paid', () => {
    const cash = cashUsd({ schedule: OWNER, through: '2026-11-02', usdIdr: OWNER_USD_IDR, orders: OCT_BUYS });
    const holdings = 558.0; // 20 x $27.90 of stock
    const fees = 2.6; // 20 x $0.13
    expect(holdings + cash).toBeCloseTo(840.76 - fees, 2);
  });

  it('on 8 October he had spent 9 cents more than he had deposited', () => {
    const cash = cashUsd({ schedule: OWNER, through: '2026-10-08', usdIdr: OWNER_USD_IDR, orders: OCT_BUYS });
    expect(cash).toBeCloseTo(-0.09, 2);
  });

  it('a sale after the start day funds the plan, as the real PLTR sale did', () => {
    const withSale: CashFlowOrder[] = [...OCT_BUYS, { side: 'sell', totalUsd: 100 }];
    const cash = cashUsd({ schedule: OWNER, through: '2026-10-08', usdIdr: OWNER_USD_IDR, orders: withSale });
    expect(cash).toBeCloseTo(99.91, 2);
  });
});
