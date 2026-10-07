import { describe, expect, it } from 'vitest';
import { addedState, removedState, repickLine, stockCount, whenRepicked } from './view';

describe('whenRepicked / repickLine', () => {
  it('says minutes when the re-pick can be asked for, else the nightly run', () => {
    expect(whenRepicked(true)).toBe('within a few minutes');
    expect(whenRepicked(false)).toBe('at the next nightly run');
    expect(repickLine(true)).toContain('within a few minutes');
    expect(repickLine(false)).toContain('at the next nightly run');
  });
});

describe('addedState', () => {
  it('says the stock is skipped and when picks change', () => {
    const s = addedState('BRK.B', 'added', true);
    expect(s.tone).toBe('ok');
    expect(s.message).toContain('BRK.B is on the list');
    expect(s.message).toContain('within a few minutes');
  });
  it('says so when it was already listed', () => {
    expect(addedState('AAPL', 'already', false).message).toBe('AAPL is already on the list.');
  });
});

describe('removedState', () => {
  it('says it is back on Gotrade', () => {
    expect(removedState('AAPL', true, false).message).toContain('back on Gotrade');
    expect(removedState('AAPL', true, false).message).toContain('nightly run');
  });
  it('says so when it was not listed', () => {
    expect(removedState('AAPL', false, true).message).toBe('AAPL was not on the list.');
  });
});

describe('stockCount', () => {
  it('counts in words', () => {
    expect(stockCount(0)).toBe('No stocks');
    expect(stockCount(1)).toBe('1 stock');
    expect(stockCount(4)).toBe('4 stocks');
  });
});
