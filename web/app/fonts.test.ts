import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

/** Outfit has no math operators, so these fall through to the 'Sera Math' subset in globals.css.
    Keep in step with the glyphs the app actually emits (pfText, markLabel, lib/metrics, lab.json). */
const MATH = ['∞', '≈', '≤', '≥'];

const css = readFileSync(join(import.meta.dirname, 'globals.css'), 'utf8');

describe('math glyph fallback', () => {
  it('declares a face for every weight the subset ships', () => {
    for (const weight of [400, 500]) {
      expect(css).toContain(`/fonts/sera-math-${weight}.woff2`);
      expect(existsSync(join(import.meta.dirname, '..', 'public', 'fonts', `sera-math-${weight}.woff2`))).toBe(true);
    }
  });

  it('covers every operator Outfit is missing', () => {
    const range = css.match(/unicode-range:\s*([^;]+);/)?.[1] ?? '';
    const points = new Set<number>();
    for (const part of range.split(',')) {
      const [lo, hi] = part.trim().replace(/^U\+/i, '').split('-').map(h => parseInt(h, 16));
      for (let c = lo; c <= (hi ?? lo); c++) points.add(c);
    }
    for (const ch of MATH) expect(points.has(ch.codePointAt(0)!)).toBe(true);
  });

  it('puts the fallback after Outfit, so it can only fill a real gap', () => {
    expect(css).toMatch(/font-family:\s*var\(--font-outfit\),\s*'Sera Math',\s*system-ui/);
  });
});
