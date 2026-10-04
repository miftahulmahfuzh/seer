import type { ReactNode } from 'react';
import s from './charts.module.css';
import { HRef, VRef } from './parts';
import { type Domain, type Format, type RefLine, type TickSpec, clamp, extent, fmtNumber, isNum, linear, resolveAxis, textWidth } from './scale';

export type ScatterPoint = {
  /** Unique within the chart (React key). */
  id: string;
  /** A null coordinate skips the point. */
  x: number | null;
  y: number | null;
  /** Default 'var(--ink)'. */
  color?: string;
  /** Radius in viewBox units. Default 6. */
  r?: number;
  /** Hollow point (outline only). */
  ring?: boolean;
  /** Tooltip; '\n' breaks lines. */
  tip?: string;
  /** Makes the point a link (e.g. '/sera/methods/M0001'). */
  href?: string;
  /** Text printed beside the point. */
  label?: string;
};

/** A shaded rectangle in data units. A null or missing bound runs to the plot edge. */
export type ScatterRegion = {
  x0?: number | null;
  x1?: number | null;
  y0?: number | null;
  y1?: number | null;
  /** Printed in the region's top-left corner (e.g. 'Pass zone'). */
  label?: string;
  /** Default 'var(--sky)'. */
  color?: string;
  /** Default 1 (the pale tokens are already soft). */
  opacity?: number;
  tip?: string;
};

export type ScatterChartProps = {
  points: readonly ScatterPoint[];
  ariaLabel: string;
  regions?: readonly ScatterRegion[];
  /** Vertical lines at x values. */
  refX?: readonly RefLine[];
  /** Horizontal lines at y values. */
  refY?: readonly RefLine[];
  /** Default: points + finite region bounds + ref lines, widened to nice ticks. */
  xDomain?: Domain;
  yDomain?: Domain;
  includeZeroX?: boolean;
  includeZeroY?: boolean;
  /** Default fmtNumber(1). */
  xFormat?: Format;
  yFormat?: Format;
  /** Target count (x default 8, y default 6) or explicit ticks. */
  xTicks?: TickSpec;
  yTicks?: TickSpec;
  xLabel?: string;
  yLabel?: string;
  legend?: ReactNode;
  /** viewBox size. Default 960 × 440. */
  width?: number;
  height?: number;
  preserveAspectRatio?: string;
  className?: string;
};

/** Scatter plot with shaded regions (the pass zone), reference lines, tooltips and link-able points. */
export function ScatterChart(props: ScatterChartProps) {
  const { points, ariaLabel, regions = [], refX = [], refY = [], legend, className } = props;
  const W = props.width ?? 960;
  const H = props.height ?? 440;
  const live = points.filter((p): p is ScatterPoint & { x: number; y: number } => isNum(p.x) && isNum(p.y));
  const finite = (vs: ReadonlyArray<number | null | undefined>) => vs.filter(isNum);

  const xAxis = resolveAxis(
    extent(live.map(p => p.x), [...(props.includeZeroX ? [0] : []), ...refX.map(r => r.value), ...finite(regions.flatMap(r => [r.x0, r.x1]))]),
    { domain: props.xDomain, ticks: props.xTicks, format: props.xFormat ?? fmtNumber(1), count: 8 },
  );
  const yAxis = resolveAxis(
    extent(live.map(p => p.y), [...(props.includeZeroY ? [0] : []), ...refY.map(r => r.value), ...finite(regions.flatMap(r => [r.y0, r.y1]))]),
    { domain: props.yDomain, ticks: props.yTicks, format: props.yFormat ?? fmtNumber(1), count: 6 },
  );
  const m = {
    top: 16,
    right: 24,
    bottom: 36 + (props.xLabel ? 24 : 0),
    left: 14 + Math.max(16, ...yAxis.ticks.map(t => textWidth(t.label))) + (props.yLabel ? 26 : 0),
  };
  const sx = linear(xAxis.domain, [m.left, W - m.right]);
  const sy = linear(yAxis.domain, [H - m.bottom, m.top]);
  const ex = (v: number | null | undefined, edge: number) => (isNum(v) ? sx(clamp(v, xAxis.domain[0], xAxis.domain[1])) : edge);
  const ey = (v: number | null | undefined, edge: number) => (isNum(v) ? sy(clamp(v, yAxis.domain[0], yAxis.domain[1])) : edge);
  const inX = (v: number) => v >= Math.min(...xAxis.domain) && v <= Math.max(...xAxis.domain);
  const inY = (v: number) => v >= Math.min(...yAxis.domain) && v <= Math.max(...yAxis.domain);

  return (
    <figure className={`${s.figure} ${className ?? ''}`}>
      {legend ? <div className={s.legendSlot}>{legend}</div> : null}
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio={props.preserveAspectRatio ?? 'xMidYMid meet'}
        className={s.svg} role="img" aria-label={ariaLabel}>
        {regions.map((r, i) => {
          const a = ex(r.x0, m.left);
          const b = ex(r.x1, W - m.right);
          const c = ey(r.y0, H - m.bottom);
          const d = ey(r.y1, m.top);
          const x = Math.min(a, b);
          const y = Math.min(c, d);
          return (
            <g key={`z${i}`}>
              <rect x={x} y={y} width={Math.abs(b - a)} height={Math.abs(d - c)} rx={10}
                style={{ fill: r.color ?? 'var(--sky)', opacity: r.opacity ?? 1 }} data-tip={r.tip} />
              {r.label ? <text x={x + 12} y={y + 22} className={s.regionLabel}>{r.label}</text> : null}
            </g>
          );
        })}
        {yAxis.ticks.filter(t => inY(t.value)).map(t => (
          <g key={`y${t.value}`}>
            <line x1={m.left} x2={W - m.right} y1={sy(t.value)} y2={sy(t.value)} className={s.grid} />
            <text x={m.left - 10} y={sy(t.value)} dy="0.35em" textAnchor="end" className={s.tick}>{t.label}</text>
          </g>
        ))}
        {xAxis.ticks.filter(t => inX(t.value)).map(t => (
          <g key={`x${t.value}`}>
            <line x1={sx(t.value)} x2={sx(t.value)} y1={m.top} y2={H - m.bottom} className={s.grid} />
            <text x={sx(t.value)} y={H - m.bottom + 22} textAnchor="middle" className={s.tick}>{t.label}</text>
          </g>
        ))}
        <line x1={m.left} x2={W - m.right} y1={H - m.bottom} y2={H - m.bottom} className={s.axisLine} />
        <line x1={m.left} x2={m.left} y1={m.top} y2={H - m.bottom} className={s.axisLine} />
        {refY.map((r, i) => <HRef key={`ry${i}`} r={r} y={sy(r.value)} x1={m.left} x2={W - m.right} />)}
        {refX.map((r, i) => <VRef key={`rx${i}`} r={r} x={sx(r.value)} y1={m.top} y2={H - m.bottom} right={W - m.right} />)}
        {live.map(p => {
          const color = p.color ?? 'var(--ink)';
          const cx = sx(p.x);
          const cy = sy(p.y);
          const radius = p.r ?? 6;
          const dot = (
            <circle cx={cx} cy={cy} r={radius} className={s.point} data-tip={p.tip}
              style={p.ring
                ? { fill: 'var(--chart-halo, var(--sheet))', stroke: color, strokeWidth: 2 }
                : { fill: color, stroke: 'var(--chart-halo, var(--sheet))', strokeWidth: 1.5 }} />
          );
          const label = p.label ? (
            <text x={cx + radius + 6} y={cy} dy="0.35em" className={s.pointLabel}>{p.label}</text>
          ) : null;
          return p.href ? (
            <a key={p.id} href={p.href} className={s.link} aria-label={p.tip ?? p.label ?? p.id}>{dot}{label}</a>
          ) : (
            <g key={p.id}>{dot}{label}</g>
          );
        })}
        {props.xLabel ? (
          <text x={(m.left + W - m.right) / 2} y={H - 6} textAnchor="middle" className={s.axisTitle}>{props.xLabel}</text>
        ) : null}
        {props.yLabel ? (
          <text transform={`translate(14 ${(m.top + H - m.bottom) / 2}) rotate(-90)`} textAnchor="middle" className={s.axisTitle}>
            {props.yLabel}
          </text>
        ) : null}
        {live.length === 0 ? <text x={W / 2} y={H / 2} textAnchor="middle" className={s.empty}>No data yet</text> : null}
      </svg>
    </figure>
  );
}
