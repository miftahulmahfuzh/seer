import { describe, expect, it } from 'vitest';
import { cardBg, slotBg, slotCount, slotLetter } from './slots';

describe('slots', () => {
  it('spells SEER across slots 1..4 and wraps', () => {
    expect([1, 2, 3, 4].map(slotLetter).join('')).toBe('SEER');
    expect(slotLetter(5)).toBe('S');
    expect(slotBg(4)).toBe('bg-stone');
    expect(slotBg(0)).toBe('bg-stone');
  });
  it('gives only bracket strategies slots', () => {
    expect(slotCount('bracket')).toBe(4);
    expect(slotCount('book')).toBe(0);
    expect(slotCount('benchmark')).toBe(0);
  });
  it('colours slotless cards by their place in the list', () => {
    expect(cardBg(null, 0)).toBe('bg-lav');
    expect(cardBg(null, 5)).toBe('bg-butter');
    expect(cardBg(null, 19)).toBe('bg-stone');
    expect(cardBg(3, 0)).toBe('bg-sky');
  });
});
