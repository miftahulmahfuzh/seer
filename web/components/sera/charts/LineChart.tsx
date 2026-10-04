import type { ReactNode } from 'react';
import s from './charts.module.css';
import { HRef } from './parts';
import {
  type Domain, type Format, type Pt, type RefLine, type Tick, type TickSpec,
  areaPath, clamp, colorAt, dateNum, extent, fmtNumber, isNum, linePath, linear, resolveAxis, spread, stepPoints,
  textWidth, yearTicks,
} from './scale';

export type XValue = string | number;
/** [x, y, tip?]. x is an ISO date ('1993-01-29') or a number (a trial number). A null y breaks the line. */
export type LinePoint = readonly [x: XValue, y: number | null, tip?: string];

export type LineSeries = {
  id: string;
  label: string;
  points: readonly LinePoint[];
  /** CSS colour, normally a token: 'var(--coral)'. Default: CHART_COLORS by series index. */
  color?: string;
  /** Stroke width in viewBox units. Default 2.25. */
  width?: number;
  /** stroke-dasharray, e.g. '1 5' dotted (SPY, as on the Leaderboard) or '6 4' dashed. */
  dash?: string;
  opacity?: number;
  /** Fill between the line and y = 0 (drawdown / underwater charts). */
  area?: boolean;
  /** Default 0.16. */
  areaOpacity?: number;
  /** Step-after line: each value holds flat until the next x ("best so far"). */
  step?: boolean;
  /** Draw a dot at every point; each dot's data-tip is the point's tip, else the series tip, else its label. */
  dots?: boolean;
  /** Tooltip on the line. Default: label. */
  tip?: string;
  /** Print the label at the right end of the line (collisions are spread apart). */
  endLabel?: boolean;
};

export type LineChartProps = {
  series: readonly LineSeries[];
  /** Required: the chart is role="img". */
  ariaLabel: string;
  /** Default: 'date' when the first x is a string, else 'number'. */
  x?: 'date' | 'number';
  /** Epoch ms in date mode. Default: the data's extent. */
  xDomain?: Domain;
  /** Default: the data's extent (plus 0 when includeZero, plus refLines), widened to nice ticks. */
  yDomain?: Domain;
  includeZero?: boolean;
  /** Number-mode x labels. Default fmtNumber(0). */
  xFormat?: Format;
  /** Default fmtNumber(0). Use fmtPct(0), fmtMultiple(1)… from ./scale. */
  yFormat?: Format;
  /** Date mode: a number is the max year ticks (default 12). Number mode: target count (default 8). Or explicit ticks. */
  xTicks?: TickSpec;
  /** Target count (default 5) or explicit ticks. */
  yTicks?: TickSpec;
  refLines?: readonly RefLine[];
  xLabel?: string;
  yLabel?: string;
  /** Rendered above the plot, right-aligned (usually <Legend items={legendFromSeries(series)} />). */
  legend?: ReactNode;
  /** viewBox size. Default 960 × 360. */
  width?: number;
  height?: number;
  /** Default 'xMidYMid meet' (text keeps its proportions). */
  preserveAspectRatio?: string;
  className?: string;
};

/** Multi-series line chart: hand-built SVG, server-rendered, year ticks on date axes. */
export function LineChart(props: LineChartProps) {
  const { series, ariaLabel, refLines = [], legend, className } = props;
  const W = props.width ?? 960;
  const H = props.height ?? 360;
  const firstX = series.find(se => se.points.length > 0)?.points[0][0];
  const mode = props.x ?? (typeof firstX === 'string' ? 'date' : 'number');
  const toX = (v: XValue) => (typeof v === 'string' ? dateNum(v) : v);
  const raw = series.map(se => se.points.map(p => [toX(p[0]), p[1]] as const));
  const xsAll = raw.flatMap(r => r.filter(q => isNum(q[1])).map(q => q[0]));
  const ysAll = raw.flatMap(r => r.map(q => q[1]));
  const empty = !raw.some(r => r.some(q => isNum(q[0]) && isNum(q[1])));

  const y = resolveAxis(extent(ysAll, [...(props.includeZero ? [0] : []), ...refLines.map(r => r.value)]), {
    domain: props.yDomain,
    ticks: props.yTicks,
    format: props.yFormat ?? fmtNumber(0),
    count: 5,
  });
  const xDom: Domain = props.xDomain ?? extent(xsAll);
  let xTicks: Tick[];
  if (props.xTicks !== undefined && typeof props.xTicks !== 'number') xTicks = [...props.xTicks];
  else if (mode === 'date') xTicks = yearTicks(xDom[0], xDom[1], props.xTicks ?? 12);
  else xTicks = resolveAxis(xDom, { domain: xDom, ticks: props.xTicks, format: props.xFormat ?? fmtNumber(0), count: 8 }).ticks;

  const ends = series.flatMap((se, i) => (se.endLabel ? [i] : []));
  const m = {
    top: 18,
    right: 20 + (ends.length ? Math.max(...ends.map(i => textWidth(series[i].label))) + 14 : 0),
    bottom: 34 + (props.xLabel ? 24 : 0),
    left: 14 + Math.max(16, ...y.ticks.map(t => textWidth(t.label))) + (props.yLabel ? 26 : 0),
  };
  const sx = linear(xDom, [m.left, W - m.right]);
  const sy = linear(y.domain, [H - m.bottom, m.top]);
  const baseY = sy(clamp(0, y.domain[0], y.domain[1]));

  const drawn = series.map((se, i) => {
    const xy: Array<Pt | null> = raw[i].map(([xv, yv]) => (isNum(xv) && isNum(yv) ? ([sx(xv), sy(yv)] as const) : null));
    const path = se.step ? stepPoints(xy) : xy;
    let last: Pt | null = null;
    for (const q of xy) if (q) last = q;
    return { se, xy, last, color: se.color ?? colorAt(i), d: linePath(path), area: se.area ? areaPath(path, baseY) : '' };
  });
  const endY = spread(ends.map(i => drawn[i].last?.[1] ?? baseY), 16, m.top, H - m.bottom);
  const inX = (v: number) => v >= Math.min(...xDom) && v <= Math.max(...xDom);

  return (
    <figure className={`${s.figure} ${className ?? ''}`}>
      {legend ? <div className={s.legendSlot}>{legend}</div> : null}
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio={props.preserveAspectRatio ?? 'xMidYMid meet'}
        className={s.svg} role="img" aria-label={ariaLabel}>
        {y.ticks.map(t => (
          <g key={`y${t.value}`}>
            <line x1={m.left} x2={W - m.right} y1={sy(t.value)} y2={sy(t.value)} className={s.grid} />
            <text x={m.left - 10} y={sy(t.value)} dy="0.35em" textAnchor="end" className={s.tick}>{t.label}</text>
          </g>
        ))}
        {xTicks.filter(t => inX(t.value)).map(t => (
          <text key={`x${t.value}`} x={sx(t.value)} y={H - m.bottom + 22} textAnchor="middle" className={s.tick}>{t.label}</text>
        ))}
        <line x1={m.left} x2={W - m.right} y1={H - m.bottom} y2={H - m.bottom} className={s.axisLine} />
        {drawn.map(({ se, color, area }) =>
          area ? <path key={`a${se.id}`} d={area} style={{ fill: color, opacity: se.areaOpacity ?? 0.16 }} /> : null,
        )}
        {refLines.map((r, i) => <HRef key={`r${i}`} r={r} y={sy(r.value)} x1={m.left} x2={W - m.right} />)}
        {drawn.map(({ se, color, d }) =>
          d ? (
            <g key={`l${se.id}`}>
              <path d={d} fill="none" style={{ stroke: color, opacity: se.opacity }} strokeWidth={se.width ?? 2.25}
                strokeDasharray={se.dash} strokeLinecap="round" strokeLinejoin="round" />
              <path d={d} className={s.hit} data-tip={se.tip ?? se.label} />
            </g>
          ) : null,
        )}
        {drawn.map(({ se, xy, color }) =>
          se.dots
            ? xy.map((q, j) =>
                q ? (
                  <circle key={`d${se.id}-${j}`} cx={q[0]} cy={q[1]} r={3.5} className={s.dot} style={{ fill: color }}
                    data-tip={se.points[j][2] ?? se.tip ?? se.label} />
                ) : null,
              )
            : null,
        )}
        {ends.map((i, k) =>
          drawn[i].last ? (
            <text key={`e${series[i].id}`} x={W - m.right + 10} y={endY[k]} dy="0.35em" className={s.endLabel}
              style={{ fill: drawn[i].color }}>
              {series[i].label}
            </text>
          ) : null,
        )}
        {props.xLabel ? (
          <text x={(m.left + W - m.right) / 2} y={H - 6} textAnchor="middle" className={s.axisTitle}>{props.xLabel}</text>
        ) : null}
        {props.yLabel ? (
          <text transform={`translate(14 ${(m.top + H - m.bottom) / 2}) rotate(-90)`} textAnchor="middle" className={s.axisTitle}>
            {props.yLabel}
          </text>
        ) : null}
        {empty ? <text x={W / 2} y={H / 2} textAnchor="middle" className={s.empty}>No data yet</text> : null}
      </svg>
    </figure>
  );
}
