import { describe, expect, it } from 'vitest';
import { CONDITION_KEYS } from './derive';
import {
  CONDITION_TERM,
  GLOSSARY,
  GLOSSARY_ORDER,
  INSIGHT_KIND_LABEL,
  SOURCE_KIND_LABEL,
  STATUS_LABEL,
} from './glossary';
import { INSIGHT_KINDS, METHOD_STATUSES, SOURCE_KINDS } from './types';

const sentences = (s: string) => s.trim().split(/[.!?](?=\s|$)/).filter((x) => x.trim() !== '');

describe('glossary', () => {
  it('defines every required term in exactly one plain sentence', () => {
    const keys = Object.keys(GLOSSARY).sort();
    expect(keys).toEqual(
      [
        'return',
        'mwr',
        'cagr',
        'maxDrawdown',
        'profitFactor',
        'trades',
        'sharpe',
        'mar',
        'dsr',
        'tries',
        'exposure',
        'turnover',
        'devWindow',
        'testWindow',
        'paperTrading',
        'spyTr',
        'ownerInputs',
      ].sort(),
    );
    for (const entry of Object.values(GLOSSARY)) {
      expect(entry.term.length).toBeGreaterThan(0);
      expect(entry.plain.endsWith('.')).toBe(true);
      expect(sentences(entry.plain)).toHaveLength(1);
      expect(entry.plain).not.toMatch(/\d+(\.\d+)?%/);
    }
  });

  it('orders every term exactly once', () => {
    expect([...GLOSSARY_ORDER].sort()).toEqual(Object.keys(GLOSSARY).sort());
  });

  it('explains every gate condition', () => {
    for (const k of CONDITION_KEYS) expect(GLOSSARY[CONDITION_TERM[k]]).toBeDefined();
  });
});

describe('labels', () => {
  it('covers every method status', () => {
    expect(Object.keys(STATUS_LABEL).sort()).toEqual([...METHOD_STATUSES].sort());
    for (const s of METHOD_STATUSES) {
      expect(STATUS_LABEL[s].label.length).toBeGreaterThan(0);
      expect(STATUS_LABEL[s].meaning.endsWith('.')).toBe(true);
      expect(['good', 'bad', 'wait', 'neutral']).toContain(STATUS_LABEL[s].tone);
    }
  });

  it('covers every insight kind, synthesis included', () => {
    expect(Object.keys(INSIGHT_KIND_LABEL).sort()).toEqual([...INSIGHT_KINDS].sort());
    expect(INSIGHT_KIND_LABEL.synthesis.heading).toBe('Batch summaries');
  });

  it('covers every source kind', () => {
    expect(Object.keys(SOURCE_KIND_LABEL).sort()).toEqual([...SOURCE_KINDS].sort());
  });
});
