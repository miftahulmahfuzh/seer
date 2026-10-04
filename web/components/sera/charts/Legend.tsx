import type { CSSProperties } from 'react';
import s from './charts.module.css';
import type { LineSeries } from './LineChart';
import { colorAt } from './scale';

export type LegendShape = 'line' | 'dash' | 'dot' | 'ring' | 'zone';
export type LegendItem = {
  label: string;
  /** CSS colour, normally a token: 'var(--coral)'. */
  color: string;
  /** Default 'line'. 'zone' is a soft rectangle for shaded regions. */
  shape?: LegendShape;
  tip?: string;
};

const SHAPE: Record<LegendShape, string> = {
  line: s.sw_line,
  dash: s.sw_dash,
  dot: s.sw_dot,
  ring: s.sw_ring,
  zone: s.sw_zone,
};

const swatchStyle = (it: LegendItem): CSSProperties =>
  it.shape === 'dash' || it.shape === 'ring' ? { borderColor: it.color } : { background: it.color };

/** Key for a chart. Plain HTML, so it can sit in a chart's legend slot or anywhere in a Section. */
export function Legend({ items, className }: { items: readonly LegendItem[]; className?: string }) {
  return (
    <ul className={`${s.legend} ${className ?? ''}`}>
      {items.map((it, i) => (
        <li key={`${i}-${it.label}`} className={s.legendItem} data-tip={it.tip}>
          <span aria-hidden="true" className={`${s.swatch} ${SHAPE[it.shape ?? 'line']}`} style={swatchStyle(it)} />
          {it.label}
        </li>
      ))}
    </ul>
  );
}

/** Legend items matching LineChart's own colour and dash choices. */
export function legendFromSeries(series: readonly LineSeries[]): LegendItem[] {
  return series.map((se, i) => ({
    label: se.label,
    color: se.color ?? colorAt(i),
    shape: se.dash ? 'dash' : 'line',
    tip: se.tip,
  }));
}
