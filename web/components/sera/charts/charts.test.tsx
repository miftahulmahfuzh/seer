import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { BarChart, barGroups } from './BarChart';
import { Legend, legendFromSeries } from './Legend';
import { LineChart, type LineSeries } from './LineChart';
import { ScatterChart } from './ScatterChart';
import { fmtMultiple, fmtNumber, fmtPct } from './scale';

const DATES = ['1993-01-29', '1999-12-31', '2007-06-29', '2015-10-16'];
const curve = (k: number): [string, number][] => DATES.map((d, i) => [d, 1 + k * i]);
const count = (html: string, needle: string) => html.split(needle).length - 1;

describe('LineChart', () => {
  const series: LineSeries[] = [
    { id: 'a', label: 'M0001 v1', points: curve(0.5), endLabel: true, tip: 'M0001 variant 1' },
    { id: 'spy', label: 'SPY', points: curve(0.4), dash: '1 5', color: 'var(--ink-3)', endLabel: true },
  ];

  it('draws date series with year ticks, a reference line and end labels', () => {
    const html = renderToStaticMarkup(
      <LineChart series={series} ariaLabel="Growth of 1" yFormat={fmtMultiple(1)} refLines={[{ value: 1, label: 'Start' }]} />,
    );
    expect(html).not.toContain('NaN');
    expect(html).toContain('viewBox="0 0 960 360"');
    expect(html).toContain('role="img"');
    expect(html).toContain('aria-label="Growth of 1"');
    expect(html).toContain('>1994<');
    expect(html).toContain('>2014<');
    expect(html).toContain('data-tip="M0001 variant 1"');
    expect(html).toContain('>Start<');
    expect(html).toContain('>SPY<');
    expect(html).toContain('stroke-dasharray="1 5"');
  });

  it('fills an underwater area and breaks the line at nulls', () => {
    const dd: LineSeries = {
      id: 'dd', label: 'Drawdown', area: true, color: 'var(--neg)',
      points: [['1993-01-29', 0], ['2000-01-31', -0.12], ['2003-01-31', null], ['2008-12-31', -0.3], ['2015-10-16', 0]],
    };
    const html = renderToStaticMarkup(<LineChart series={[dd]} ariaLabel="Drawdown" yFormat={fmtPct(0)} includeZero />);
    expect(html).not.toContain('NaN');
    expect(html).toMatch(/d="M[^"]*Z"/);
    expect(html).toContain('>−30%<');
  });

  it('draws numeric step lines with per-point tips', () => {
    const best: LineSeries = { id: 'b', label: 'Best so far', step: true, dots: true, points: [[1, 2], [5, 3, 'Trial 5'], [9, 4]] };
    const html = renderToStaticMarkup(<LineChart series={[best]} ariaLabel="Progress" xLabel="Trial" yLabel="Hurdles" />);
    expect(html).not.toContain('NaN');
    expect(count(html, '<circle')).toBe(3);
    expect(html).toContain('data-tip="Trial 5"');
    expect(html).toContain('>Trial<');
  });

  it('says so when there is no data', () => {
    const html = renderToStaticMarkup(<LineChart series={[]} ariaLabel="Nothing" />);
    expect(html).toContain('No data yet');
    expect(html).not.toContain('NaN');
  });
});

describe('ScatterChart', () => {
  it('shades regions, draws reference lines and links points', () => {
    const html = renderToStaticMarkup(
      <ScatterChart
        ariaLabel="Where every try landed"
        points={[
          { id: 'M0001-a', x: 0.12, y: -0.003, tip: 'M0001 a', href: '/sera/methods/M0001', color: 'var(--coral)' },
          { id: 'H-x', x: 0.42, y: 0.02, ring: true, label: 'best' },
          { id: 'skip', x: null, y: 0.1 },
        ]}
        regions={[{ x1: 0.15, y0: 0, label: 'Pass zone' }]}
        refX={[{ value: 0.15, label: 'Max fall 15%' }]}
        refY={[{ value: 0, label: 'Same as SPY' }]}
        xFormat={fmtPct(0)}
        yFormat={fmtPct(1)}
        xLabel="Worst fall"
        yLabel="Growth vs SPY"
      />,
    );
    expect(html).not.toContain('NaN');
    expect(html).toContain('viewBox="0 0 960 440"');
    expect(html).toContain('href="/sera/methods/M0001"');
    expect(html).toContain('data-tip="M0001 a"');
    expect(html).toContain('>Pass zone<');
    expect(html).toContain('>Max fall 15%<');
    expect(html).toContain('>best<');
    expect(count(html, '<circle')).toBe(2);
  });

  it('says so when no point has both coordinates', () => {
    const html = renderToStaticMarkup(<ScatterChart ariaLabel="Empty" points={[{ id: 'a', x: null, y: 1 }]} />);
    expect(html).toContain('No data yet');
    expect(html).not.toContain('NaN');
  });
});

describe('BarChart', () => {
  it('draws signed grouped vertical bars with a reference line', () => {
    const html = renderToStaticMarkup(
      <BarChart
        ariaLabel="Year by year"
        signed
        format={fmtPct(0)}
        refLines={[{ value: 0.1, label: 'Ten percent' }]}
        groups={[
          { id: '1994', label: '1994', items: [{ key: 'm', value: -0.05, tip: 'Method 1994' }, { key: 'spy', value: 0.012, color: 'var(--ink-3)' }] },
          { id: '1995', label: '1995', items: [{ key: 'm', value: 0.2 }, { key: 'spy', value: 0.37, color: 'var(--ink-3)' }] },
        ]}
      />,
    );
    expect(html).not.toContain('NaN');
    expect(html).toContain('fill:var(--neg)');
    expect(html).toContain('fill:var(--pos)');
    expect(html).toContain('fill:var(--ink-3)');
    expect(html).toContain('>1994<');
    expect(html).toContain('data-tip="Method 1994"');
    expect(html).toContain('>Ten percent<');
  });

  it('draws horizontal bars with values, links and truncated labels', () => {
    const html = renderToStaticMarkup(
      <BarChart
        orientation="horizontal"
        ariaLabel="Hurdles"
        format={fmtNumber(0)}
        maxLabelChars={20}
        groups={barGroups([
          { id: 'spy', label: 'Beats SPY total return over the whole period', value: 12, href: '/sera/methods' },
          { id: 'dd', label: 'Max DD', value: 40 },
          { id: 'none', label: 'Nothing', value: null },
        ])}
      />,
    );
    expect(html).not.toContain('NaN');
    expect(html).toContain('viewBox="0 0 960 148"');
    expect(html).toContain('>12<');
    expect(html).toContain('>40<');
    expect(html).toContain('>—<');
    expect(html).toContain('href="/sera/methods"');
    expect(html).toContain('>Beats SPY total ret…<');
    expect(html).toContain('data-tip="Beats SPY total return over the whole period"');
  });

  it('says so when there are no bars', () => {
    const html = renderToStaticMarkup(<BarChart ariaLabel="Empty" groups={[]} />);
    expect(html).toContain('No data yet');
    expect(html).not.toContain('NaN');
  });
});

describe('Legend', () => {
  it('mirrors the series colours and dashes', () => {
    const items = legendFromSeries([
      { id: 'a', label: 'Method', points: [] },
      { id: 'spy', label: 'SPY', points: [], dash: '1 5', color: 'var(--ink-3)', tip: 'SPY with dividends' },
    ]);
    expect(items).toEqual([
      { label: 'Method', color: 'var(--ink)', shape: 'line', tip: undefined },
      { label: 'SPY', color: 'var(--ink-3)', shape: 'dash', tip: 'SPY with dividends' },
    ]);
    const html = renderToStaticMarkup(<Legend items={[...items, { label: 'Pass zone', color: 'var(--sky)', shape: 'zone' }]} />);
    expect(html).toContain('>Method<');
    expect(html).toContain('data-tip="SPY with dividends"');
    expect(html).toContain('border-color:var(--ink-3)');
    expect(html).toContain('background:var(--sky)');
  });
});
