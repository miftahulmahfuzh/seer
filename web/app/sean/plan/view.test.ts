import { describe, expect, it } from 'vitest';
import type { Reminder } from '../../../lib/sean/reminders';
import {
  aboutUsd, cadenceOf, cashLine, doneLine, joinWords, methodTitle, nextPickWords, outsideLine, parseBudget,
  parseSide, parseSince, parseSymbol, picksLine, planSizeLine, reminderDetail, reminderTitle, todoLabel,
} from './view';

const r = (over: Partial<Reminder>): Reminder => ({
  key: '2026-10-07:MU:buy', action: 'buy', side: 'buy', symbol: 'MU', usd: 28, shares: null, weight: 0.05,
  alsoOutside: false, done: null, ...over,
});

describe('form rules', () => {
  it('parseSince takes real days only', () => {
    expect(parseSince('2026-10-07')).toBe('2026-10-07');
    expect(parseSince(' 2026-10-07 ')).toBe('2026-10-07');
    expect(parseSince('2026-02-30')).toBeNull();
    expect(parseSince('07/10/2026')).toBeNull();
    expect(parseSince('1999-12-31')).toBeNull();
    expect(parseSince(null)).toBeNull();
  });

  it('parseBudget: empty is none, money strings parse, junk fails', () => {
    expect(parseBudget('')).toEqual({ ok: true, value: null });
    expect(parseBudget(null)).toEqual({ ok: true, value: null });
    expect(parseBudget('560')).toEqual({ ok: true, value: 560 });
    expect(parseBudget('$1,000.50')).toEqual({ ok: true, value: 1000.5 });
    expect(parseBudget(' 27.904 ')).toEqual({ ok: true, value: 27.9 });
    expect(parseBudget('0')).toEqual({ ok: false });
    expect(parseBudget('-5')).toEqual({ ok: false });
    expect(parseBudget('abc')).toEqual({ ok: false });
    expect(parseBudget('20000000')).toEqual({ ok: false });
  });

  it('parseSymbol and parseSide', () => {
    expect(parseSymbol('brk.b')).toBe('BRK.B');
    expect(parseSymbol('DROP TABLE')).toBeNull();
    expect(parseSide('buy')).toBe('buy');
    expect(parseSide('add')).toBeNull();
  });
});

describe('words', () => {
  it('aboutUsd keeps cents under $100 and rounds above', () => {
    expect(aboutUsd(27.9)).toBe('$27.90');
    expect(aboutUsd(1045.56)).toBe('$1,046');
  });

  it('methodTitle and joinWords', () => {
    expect(methodTitle('RAW · Unbraked momentum')).toBe('Unbraked momentum');
    expect(methodTitle('SPY')).toBe('SPY');
    expect(joinWords([])).toBe('');
    expect(joinWords(['SPY'])).toBe('SPY');
    expect(joinWords(['SPY', 'NVDA'])).toBe('SPY and NVDA');
    expect(joinWords(['SPY', 'NVDA', 'GE'])).toBe('SPY, NVDA and GE');
  });

  it('cadence words', () => {
    expect(cadenceOf('monthly-hold-frac')).toBe('monthly');
    expect(cadenceOf('weekly-hold')).toBe('weekly');
    expect(cadenceOf('daily-switch')).toBe('daily');
    expect(cadenceOf(null)).toBeNull();
    expect(nextPickWords('monthly-hold-frac')).toBe('at the start of next month');
    expect(nextPickWords('monthly-rank-weekly-resize-frac')).toContain('every week');
  });

  it('picksLine says when the method acts', () => {
    const base = { short: 'RAW', sessionDate: '2026-10-07', count: 20, rulesId: 'monthly-hold-frac' };
    expect(picksLine({ ...base, pending: true })).toBe(
      "RAW picked 20 stocks for Wed, Oct 7. Its paper book buys them at that day's open; you can follow any time from then.",
    );
    expect(picksLine({ ...base, pending: false })).toBe(
      'RAW picked 20 stocks for Wed, Oct 7. It picks again at the start of next month.',
    );
  });

  it('reminderTitle for each action', () => {
    expect(reminderTitle(r({}))).toBe('Buy about $28.00 of MU');
    expect(reminderTitle(r({ usd: null }))).toBe('Buy MU');
    expect(reminderTitle(r({ action: 'add', usd: 12.5 }))).toBe('Buy about $12.50 more of MU');
    expect(reminderTitle(r({ action: 'trim', side: 'sell', usd: 17 }))).toBe('Sell about $17.00 of MU');
    expect(reminderTitle(r({ action: 'sell', side: 'sell', symbol: 'DOW', shares: 0.99077, usd: 27.9 })))
      .toBe('Sell all 0.9908 shares of DOW (about $27.90)');
  });

  it('reminderDetail names the plan, never ids', () => {
    expect(reminderDetail(r({}), 'RAW')).toBe("One of RAW's picks, and not in your plan yet.");
    expect(reminderDetail(r({ usd: null, alsoOutside: true, symbol: 'LLY' }), 'RAW')).toBe(
      "One of RAW's picks, and not in your plan yet. The LLY you bought before this plan is not counted. Set a plan size below to see how much.",
    );
    expect(reminderDetail(r({ action: 'sell', side: 'sell', symbol: 'DOW', alsoOutside: true }), 'RAW')).toBe(
      'RAW no longer picks it. Sell only these; keep the DOW you had before this plan.',
    );
    expect(reminderDetail(r({ action: 'trim', side: 'sell', usd: 17 }), 'RAW')).toBe(
      'In your plan, but about $17.00 above its share.',
    );
  });

  it('doneLine and todoLabel', () => {
    expect(doneLine(r({ done: 'mark' }), '2026-10-07')).toBe('You marked this done.');
    expect(doneLine(r({ done: 'order' }), '2026-10-07')).toBe('You bought MU on or after Wed, Oct 7.');
    expect(doneLine(r({ done: 'order', side: 'sell', action: 'sell' }), '2026-10-07')).toBe('You sold MU on or after Wed, Oct 7.');
    expect(todoLabel(0)).toBe('Nothing to do');
    expect(todoLabel(1)).toBe('1 thing to do');
    expect(todoLabel(4)).toBe('4 things to do');
  });

  it('planSizeLine, cashLine and outsideLine', () => {
    expect(planSizeLine(560, 560, 280.16)).toContain('the amount you set');
    expect(planSizeLine(838.16, null, 280.16)).toContain('$558.00 in stocks and $280.16 in cash');
    expect(planSizeLine(558, null, null)).toContain('what the plan holds now');
    expect(planSizeLine(null, null, null)).toContain('Set how much');

    expect(cashLine(838.16, 280.16, null)).toBe('$558.00 in stocks + $280.16 cash');
    expect(cashLine(838.16, 280.16, 560)).toBeNull(); // the owner typed a size: no split to show
    expect(cashLine(558, null, null)).toBeNull();
    expect(cashLine(null, null, null)).toBeNull();

    // usd() takes an absolute value (format.ts:6): a negative wallet must keep its sign
    // NOTE: the minus below is U+2212 (format.ts:1 MINUS), not a hyphen.
    expect(cashLine(557.91, -0.09, null)).toBe('$558.00 in stocks + −$0.09 cash');
    expect(planSizeLine(557.91, null, -0.09)).toContain('−$0.09 in cash');

    expect(outsideLine([], '2026-10-07')).toBeNull();
    expect(outsideLine(['NVDA', 'SPY'], '2026-10-07')).toBe(
      'You also hold NVDA and SPY from before Wed, Oct 7. They are not part of this plan, so Sean never asks you to sell them.',
    );
  });
});
