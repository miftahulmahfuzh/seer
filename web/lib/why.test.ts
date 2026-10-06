import { describe, expect, it } from 'vitest';
import { parseEvidence, whyContent } from './why';

const MISSING = 'Explanation unavailable for this pick.';

describe('parseEvidence', () => {
  it('keeps an array of strings, in order', () => {
    expect(parseEvidence(['GE closed at $273.18.', 'It was 1st of 6 stocks that qualified tonight.']))
      .toEqual(['GE closed at $273.18.', 'It was 1st of 6 stocks that qualified tonight.']);
  });

  it('reads anything that is not an array as null', () => {
    expect(parseEvidence(null)).toBeNull();
    expect(parseEvidence(undefined)).toBeNull();
    expect(parseEvidence('["a JSON string, not an array"]')).toBeNull();
    expect(parseEvidence({ facts: ['a'] })).toBeNull();
    expect(parseEvidence(42)).toBeNull();
    expect(parseEvidence(true)).toBeNull();
  });

  it('drops non-strings and blank items, and trims the rest', () => {
    expect(parseEvidence(['  rose 48.2%  ', 3, null, { a: 1 }, ['nested'], '', '   ', 'ranks 3rd of 412']))
      .toEqual(['rose 48.2%', 'ranks 3rd of 412']);
  });

  it('reads an array with nothing usable as null', () => {
    expect(parseEvidence([])).toBeNull();
    expect(parseEvidence([1, 2, null])).toBeNull();
    expect(parseEvidence(['', '  '])).toBeNull();
  });
});

describe('whyContent', () => {
  const facts = ['SPY closed at $671.20, 8.3% above its 200-day average.'];

  it('shows the text when there is one, even with facts', () => {
    expect(whyContent('F1 holds SPY because it closed above its long average.', facts, MISSING))
      .toEqual({ kind: 'text', text: 'F1 holds SPY because it closed above its long average.' });
  });

  it('trims the text', () => {
    expect(whyContent('  Short reason.  ', null, MISSING)).toEqual({ kind: 'text', text: 'Short reason.' });
  });

  it('falls back to the facts when the text is null or blank', () => {
    expect(whyContent(null, facts, MISSING)).toEqual({ kind: 'facts', facts });
    expect(whyContent(undefined, facts, MISSING)).toEqual({ kind: 'facts', facts });
    expect(whyContent('   ', facts, MISSING)).toEqual({ kind: 'facts', facts });
  });

  it('cleans the facts it falls back to', () => {
    expect(whyContent(null, ['', ' rose 12.0% '], MISSING)).toEqual({ kind: 'facts', facts: ['rose 12.0%'] });
  });

  it('says unavailable only when there is neither text nor facts', () => {
    expect(whyContent(null, null, MISSING)).toEqual({ kind: 'missing', text: MISSING });
    expect(whyContent(null, [], MISSING)).toEqual({ kind: 'missing', text: MISSING });
    expect(whyContent('', ['  '], MISSING)).toEqual({ kind: 'missing', text: MISSING });
  });

  it('uses the caller\'s missing line', () => {
    expect(whyContent(null, null, 'No reason was stored for this check.'))
      .toEqual({ kind: 'missing', text: 'No reason was stored for this check.' });
  });
});
