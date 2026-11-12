import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { ChartPanel, type ChartLine, type LegendEntry } from './ChartPanel';

// As buildChart hands them over: board order with the champion (SPY here) last.
const LINES: ChartLine[] = [
  { id: 'A', d: 'M0 100 L340 60', color: 'var(--lav-line)', width: 2, dash: null },
  { id: 'C', d: 'M0 100 L340 120', color: 'var(--rose-line)', width: 2, dash: '6 3' },
  { id: 'SPY', d: 'M0 100 L340 80', color: 'var(--ink-3)', width: 1.75, dash: '1 4' },
];

const ENTRIES: LegendEntry[] = [
  { id: 'SPY', code: 'SPY', tip: 'SPY', retired: false, line: 'var(--ink-3)', stroke: 'dotted', pill: 'var(--chip-plain)' },
  { id: 'A', code: 'A', tip: 'A · Quant', retired: false, line: 'var(--lav-line)', stroke: 'solid', pill: 'var(--lav)' },
  { id: 'C', code: 'C', tip: 'C · Dip buyer · retired oct 30', retired: true, line: 'var(--rose-line)', stroke: 'dashed', pill: 'var(--rose)' },
];

const render = (pickId: string | null) => renderToStaticMarkup(
  <ChartPanel pickId={pickId} entries={ENTRIES} lines={LINES} grid={[14, 87]} zero={120} w={340} h={170}
    labels={['AXIS']} head={<p>HEAD</p>} />,
);

const paths = (html: string) => (html.match(/<path [^>]*>/g) ?? []).map(tag => ({
  tag,
  id: /data-line="([^"]+)"/.exec(tag)?.[1],
  width: /stroke-width="([^"]+)"/.exec(tag)?.[1],
}));
const buttons = (html: string): string[] => html.match(/<button [^>]*>/g) ?? [];
const pressed = (html: string) => buttons(html)
  .filter(t => t.includes('aria-pressed="true"'))
  .map(t => /data-id="([^"]+)"/.exec(t)?.[1]);

describe('ChartPanel', () => {
  it('with nothing pressed, draws every line exactly as given: own colour, width and dash, in order, unfaded', () => {
    const html = render(null);
    const ps = paths(html);
    expect(ps.map(p => p.id)).toEqual(['A', 'C', 'SPY']);
    LINES.forEach((l, i) => {
      expect(ps[i].tag).toContain(`stroke="${l.color}"`);
      expect(ps[i].width).toBe(String(l.width));
      if (l.dash) expect(ps[i].tag).toContain(`stroke-dasharray="${l.dash}"`);
      else expect(ps[i].tag).not.toContain('stroke-dasharray');
      expect(ps[i].tag).not.toContain('data-on');
      expect(ps[i].tag).not.toContain('opacity');
    });
    expect(html).not.toContain('data-focus');
    expect(pressed(html)).toEqual([]);
  });

  it('starts with only the pick pressed, in both legends: its line 1px thicker and drawn last', () => {
    const html = render('A');
    expect(pressed(html)).toEqual(['A', 'A']);
    const ps = paths(html);
    expect(ps.map(p => p.id)).toEqual(['C', 'SPY', 'A']);
    expect(ps[2].width).toBe('3');
    expect(ps[2].tag).toContain('data-on="true"');
    expect(ps[2].tag).toContain('stroke="var(--lav-line)"');
    expect(ps[0].width).toBe('2');
    expect(ps[1].width).toBe('1.75');
    expect(html).toMatch(/<svg [^>]*data-focus="true"/);
  });

  it('lets SPY be pressed like any strategy', () => {
    const ps = paths(render('SPY'));
    expect(ps.map(p => p.id)).toEqual(['A', 'C', 'SPY']);
    expect(ps[2].width).toBe('2.75');
    expect(ps[2].tag).toContain('stroke-dasharray="1 4"');
  });

  it('lights nothing for a pick that is not on the chart', () => {
    const html = render('GONE');
    expect(html).not.toContain('data-focus');
    expect(pressed(html)).toEqual([]);
  });

  it('makes every legend item a named toggle with its full name as the tooltip, in both legends', () => {
    const html = render(null);
    const bs = buttons(html);
    expect(bs).toHaveLength(ENTRIES.length * 2);
    for (const b of bs) {
      expect(b).toContain('type="button"');
      expect(b).toContain('aria-pressed="false"');
      const tip = /data-tip="([^"]+)"/.exec(b)?.[1];
      expect(tip).toBeTruthy();
      expect(b).toContain(`aria-label="${tip}"`);
    }
    expect(html).toContain('data-tip="C · Dip buyer · retired oct 30"');
    // SPY's swatch is the dotted benchmark stroke, and its pressed pill takes the page ground.
    expect(html).toContain('border-top-style:dotted');
    expect(html).toContain('--pill:var(--chip-plain)');
    expect(html).toContain('border-top-style:dashed');
  });

  it('puts the desktop legend under the figures and the phone legend under the axis', () => {
    const html = render(null);
    const at = (needle: string) => html.indexOf(needle);
    const firstButton = at('<button ');
    const lastButton = html.lastIndexOf('<button ');
    expect(at('HEAD')).toBeLessThan(firstButton);
    expect(firstButton).toBeLessThan(at('<svg '));
    expect(at('<svg ')).toBeLessThan(at('AXIS'));
    expect(at('AXIS')).toBeLessThan(lastButton);
  });
});
