import { describe, expect, it } from 'vitest';
import { checkedLine, headlinesLabel, noCheckLine, parseVerdict, vetoSheet, type Veto } from './vetoes';

const v = (rank: number, symbol: string, verdict: Veto['verdict'], reason = 'r'): Veto => ({
  rank, symbol, verdict, reason, headlineCount: 3, earningsDate: null, decidedAt: '2026-10-05T23:10:00.000Z',
});

describe('parseVerdict', () => {
  it('keeps allow and veto and reads anything else as failed', () => {
    expect(parseVerdict('allow')).toBe('allow');
    expect(parseVerdict('veto')).toBe('veto');
    expect(parseVerdict('failed')).toBe('failed');
    expect(parseVerdict('ALLOW')).toBe('failed');
    expect(parseVerdict(null)).toBe('failed');
  });
});

describe('vetoSheet', () => {
  it('is missing when there are no rows (A had no candidates, or the check did not run)', () => {
    expect(vetoSheet([])).toEqual({ state: 'missing' });
  });
  it('shows one shared reason when every check failed the same way', () => {
    const why = 'LLM_API_KEY, LLM_BASE_URL or LLM_MODEL is not set';
    expect(vetoSheet([v(2, 'B', 'failed', why), v(1, 'A', 'failed', why)]))
      .toEqual({ state: 'failed', checked: 2, reason: why });
  });
  it('lists vetoed and failed candidates by rank, with the counts', () => {
    const sheet = vetoSheet([v(3, 'C', 'allow'), v(2, 'B', 'failed', 'timeout'), v(1, 'A', 'veto', 'earnings')]);
    expect(sheet).toEqual({
      state: 'listed', checked: 3, allowed: 1,
      rows: [v(1, 'A', 'veto', 'earnings'), v(2, 'B', 'failed', 'timeout')],
    });
  });
  it('lists every failed row when the reasons differ', () => {
    const sheet = vetoSheet([v(1, 'A', 'failed', 'timeout'), v(2, 'B', 'failed', 'HTTP 502')]);
    expect(sheet.state).toBe('listed');
    if (sheet.state === 'listed') expect(sheet.rows.map(r => r.symbol)).toEqual(['A', 'B']);
  });
  it('lists nothing when every candidate was allowed', () => {
    expect(vetoSheet([v(1, 'A', 'allow'), v(2, 'B', 'allow')])).toEqual({ state: 'listed', checked: 2, allowed: 2, rows: [] });
  });
});

describe('labels', () => {
  it('counts checks and headlines', () => {
    expect(checkedLine(8, 5)).toBe('8 checked · 5 allowed');
    expect(headlinesLabel(0)).toBe('No headlines');
    expect(headlinesLabel(1)).toBe('1 headline');
    expect(headlinesLabel(12)).toBe('12 headlines');
  });
  it('says honestly what no rows can mean', () => {
    expect(noCheckLine('Mon, Oct 5', 'C')).toBe(
      'No news check for Mon, Oct 5: A had no candidates, or the check did not run. C buys nothing this session.',
    );
  });
});
