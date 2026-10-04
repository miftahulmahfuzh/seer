import { describe, expect, it } from 'vitest';
import { method } from '../../../lib/sera/fixture';
import type { LabSeen } from '../../../lib/sera/types';
import { methodsWithStatus, needs, readingList, sourceLabel, sourceLink, urlParts } from './view';

const seen = (key: string, methodId: string | null, note = '', added = '2026-10-04T13:54:48+00:00'): LabSeen =>
  ({ key, methodId, note, added });

describe('methodsWithStatus', () => {
  it('filters by status in numeric id order', () => {
    const ms = [
      method({ id: 'M0010', status: 'idea' }),
      method({ id: 'M0002', status: 'idea' }),
      method({ id: 'M0001', status: 'rejected' }),
      method({ id: 'M0003', status: 'blocked-data' }),
    ];
    expect(methodsWithStatus(ms, 'idea').map(m => m.id)).toEqual(['M0002', 'M0010']);
    expect(methodsWithStatus(ms, 'blocked-data').map(m => m.id)).toEqual(['M0003']);
    expect(methodsWithStatus(ms, 'paper')).toEqual([]);
  });
});

describe('needs', () => {
  it('frames what is missing', () => {
    expect(needs('  quarterly fundamentals ')).toBe('needs: quarterly fundamentals');
    expect(needs('')).toBe('needs: not written down yet');
  });
});

describe('sourceLabel', () => {
  it('uses the glossary label and falls back to the raw kind', () => {
    expect(sourceLabel('paper')).toBe('Research paper');
    expect(sourceLabel('backlog')).toBe('backlog');
  });
});

describe('urlParts / sourceLink', () => {
  it('shortens a URL for display', () => {
    expect(urlParts('https://doi.org/10.1016/j.jfineco.2014.11.010')).toEqual({
      safe: true, host: 'doi.org', display: 'doi.org/10.1016/j.jfineco.2014.11.010',
    });
    expect(urlParts('https://example.com/').display).toBe('example.com');
  });
  it('never links a non-http scheme or garbage', () => {
    expect(urlParts('javascript:alert(1)').safe).toBe(false);
    expect(urlParts('not a url').safe).toBe(false);
    expect(sourceLink('javascript:alert(1)')).toBeNull();
    expect(sourceLink('Barroso & Santa-Clara (2015)')).toBeNull();
    expect(sourceLink(' https://arxiv.org/abs/1 ')).toBe('https://arxiv.org/abs/1');
  });
  it('truncates long URLs', () => {
    const d = urlParts(`https://example.com/${'a'.repeat(100)}`).display;
    expect(d.length).toBe(72);
    expect(d.endsWith('…')).toBe(true);
  });
});

describe('readingList', () => {
  const list = readingList([
    seen('concept:f1-spy-sma200-d', 'H-P7A-F1', 'The classic drawdown cutter'),
    seen('concept:f10-sso-sma200-d', 'H-P7A-F10', '2x S&P only above trend'),
    seen('concept:f2-spyqqq-12m', 'H-P7A-F2'),
    seen('concept:loose', null, 'no method yet'),
    seen('concept:momentum-own-vol-scaling', 'M0001', '', '2026-10-04T13:59:59+00:00'),
    seen('odd-key', 'M0001'),
    seen('url:https://doi.org/10.1016/j.jfineco.2014.11.010', 'M0001', '', '2026-10-04T13:59:59+00:00'),
    seen('url:https://a.example/older', null, 'older', '2026-10-01T00:00:00+00:00'),
  ]);
  it('splits links from concepts', () => {
    expect(list.links.map(l => l.host)).toEqual(['doi.org', 'a.example']);
    expect(list.conceptCount).toBe(6);
  });
  it('groups concepts by method, numeric order, untied last', () => {
    expect(list.groups.map(g => g.methodId)).toEqual(['H-P7A-F1', 'H-P7A-F2', 'H-P7A-F10', 'M0001', null]);
    expect(list.groups[3].concepts.map(c => c.label)).toEqual(['momentum-own-vol-scaling', 'odd-key']);
    expect(list.groups[0].concepts[0]).toEqual({
      key: 'concept:f1-spy-sma200-d', label: 'f1-spy-sma200-d', note: 'The classic drawdown cutter',
    });
  });
});
