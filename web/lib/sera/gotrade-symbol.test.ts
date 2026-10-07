import { describe, expect, it } from 'vitest';
import { MAX_NOTE, normalizeNote, normalizeSymbol } from './gotrade-symbol';

describe('normalizeSymbol', () => {
  it('trims and uppercases', () => {
    expect(normalizeSymbol('  aapl ')).toBe('AAPL');
  });
  it('turns a dash or slash share class into a dot', () => {
    expect(normalizeSymbol('brk-b')).toBe('BRK.B');
    expect(normalizeSymbol('BRK/B')).toBe('BRK.B');
    expect(normalizeSymbol('brk.b')).toBe('BRK.B');
  });
  it('keeps digits after the first letter', () => {
    expect(normalizeSymbol('a2m')).toBe('A2M');
  });
  it('rejects anything that is not a ticker', () => {
    for (const bad of ['', '   ', '1AB', 'AB C', 'BRK.BB', 'BRK..B', '.B', 'AB.', 'AB.1', '$AAPL', 'BRK-B-C', 'ÄPPL']) {
      expect(normalizeSymbol(bad), bad).toBeNull();
    }
  });
  it('rejects non-strings', () => {
    expect(normalizeSymbol(null)).toBeNull();
    expect(normalizeSymbol(undefined)).toBeNull();
    expect(normalizeSymbol(42)).toBeNull();
  });
});

describe('normalizeNote', () => {
  it('is null when empty or missing', () => {
    expect(normalizeNote('')).toBeNull();
    expect(normalizeNote('   \n ')).toBeNull();
    expect(normalizeNote(null)).toBeNull();
  });
  it('collapses whitespace and trims', () => {
    expect(normalizeNote('  not  in\nthe app ')).toBe('not in the app');
  });
  it('caps the length', () => {
    expect(normalizeNote('x'.repeat(500))).toHaveLength(MAX_NOTE);
  });
});
